"""End-to-end setup test with the Fellow API mocked."""
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fellow_espresso.const import CONF_DEVICE_ID, DOMAIN

DEV = {
    "id": "FS_x", "deviceType": "Solo", "displayName": "Espresso Series 1",
    "sku": "1SMB-EU", "isConnected": True, "descaleRem": 200, "backflushRem": 60,
    "showerRem": 180, "totalDescaleCount": 0, "activeProfileId": "ZWorb3ReS3",
    "firmwareVersion": "2.5.15", "firmwareUpgradeRequired": False,
    "missingWater": None, "waterHardness": 2.5, "autoStop": "volume",
    "preheat": "Default",
}
PROFILES = [{"id": "ZWorb3ReS3", "title": "House Blend", "roasterName": "Honey Moon",
             "dose": 18, "ratio": 2, "temperature": 93.5, "grindSize": 1.2}]
API = "custom_components.fellow_espresso.api.FellowEspressoApi"


def _patch_api():
    return (
        patch(f"{API}.login", AsyncMock()),
        patch(f"{API}.get_espresso_devices", AsyncMock(return_value=[DEV])),
        patch(f"{API}.get_device", AsyncMock(return_value=DEV)),
        patch(f"{API}.get_profiles", AsyncMock(return_value=PROFILES)),
    )


async def test_config_flow_creates_entry(hass):
    p = _patch_api()
    with p[0], p[1], p[2], p[3]:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "a@b.c", CONF_PASSWORD: "pw"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == "FS_x"
    assert result["title"] == "Espresso Series 1"


async def test_no_devices_error(hass):
    with patch(f"{API}.login", AsyncMock()), patch(
        f"{API}.get_espresso_devices", AsyncMock(return_value=[])
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "a@b.c", CONF_PASSWORD: "pw"}
        )
    assert result["errors"] == {"base": "no_devices"}


async def test_entities(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="FS_x",
        data={CONF_EMAIL: "a@b.c", CONF_PASSWORD: "pw", CONF_DEVICE_ID: "FS_x"},
    )
    entry.add_to_hass(hass)
    p = _patch_api()
    with p[0], p[1], p[2], p[3]:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = {s.entity_id: s for s in hass.states.async_all()}
    for eid, s in sorted(states.items()):
        print(eid, "=", s.state)
    descale = states["sensor.espresso_series_1_descale_interval"]
    assert descale.state == "200" and descale.attributes["unit_of_measurement"] == "drinks"
    backflush = states["sensor.espresso_series_1_backflush_interval"]
    assert backflush.state == "60" and backflush.attributes["unit_of_measurement"] == "shots"
    assert states["sensor.espresso_series_1_shower_screen_clean_interval"].state == "180"
    active = states["sensor.espresso_series_1_active_profile"]
    assert active.state == "House Blend"
    assert active.attributes["dose"] == 18
    assert states["sensor.espresso_series_1_profiles"].state == "1"
    assert states["binary_sensor.espresso_series_1_connected"].state == "on"
    assert "binary_sensor.espresso_series_1_water_tank_empty" not in states

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_profile_select(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="FS_x",
        data={CONF_EMAIL: "a@b.c", CONF_PASSWORD: "pw", CONF_DEVICE_ID: "FS_x"},
    )
    entry.add_to_hass(hass)
    dev = {**DEV, "activeProfileId": "6_modernarc"}
    set_profile = AsyncMock()
    with patch(f"{API}.login", AsyncMock()), patch(
        f"{API}.get_device", AsyncMock(return_value=dev)
    ), patch(f"{API}.get_profiles", AsyncMock(return_value=PROFILES)), patch(
        f"{API}.set_active_profile", set_profile
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        sel = hass.states.get("select.espresso_series_1_profile")
        print("options:", sel.attributes["options"], "current:", sel.state)
        assert sel.state == "Modern Arc"
        assert sel.attributes["options"][:3] == ["Classic 9-Bar", "Lever", "Modern Arc"]
        assert "House Blend" in sel.attributes["options"]
        assert hass.states.get("sensor.espresso_series_1_active_profile").state == "Modern Arc"

        await hass.services.async_call(
            "select", "select_option",
            {"entity_id": "select.espresso_series_1_profile", "option": "House Blend"},
            blocking=True,
        )
        set_profile.assert_awaited_once_with("FS_x", "ZWorb3ReS3")
        assert hass.states.get("select.espresso_series_1_profile").state == "House Blend"
        assert hass.states.get("sensor.espresso_series_1_active_profile").state == "House Blend"

        await hass.services.async_call(
            "select", "select_option",
            {"entity_id": "select.espresso_series_1_profile", "option": "Lever"},
            blocking=True,
        )
        set_profile.assert_awaited_with("FS_x", "5_lever")
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_unknown_builtin_is_kept_as_option(hass):
    from custom_components.fellow_espresso.profiles import profile_options
    opts = profile_options(PROFILES, {"1_lightroast", "6_modernarc"})
    assert opts["Lightroast"] == "1_lightroast"
    assert opts["Modern Arc"] == "6_modernarc"
    dup = profile_options(PROFILES + [{"id": "z", "title": "House Blend", "roasterName": "Other"}])
    assert dup["House Blend"] == "ZWorb3ReS3" and dup["House Blend (Other)"] == "z"
