"""When the profile list is fetched."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fellow_espresso.api import FellowConnectionError
from custom_components.fellow_espresso.const import CONF_DEVICE_ID, DOMAIN

API = "custom_components.fellow_espresso.api.FellowEspressoApi"
OLD = {"id": "OldProfile01", "title": "Old"}
NEW = {"id": "NewProfile02", "title": "New"}
SELECT = "select.espresso_series_1_profile"
ACTIVE = "sensor.espresso_series_1_active_profile"


@pytest.fixture
async def setup(hass):
    """A configured entry with controllable device and profile responses."""
    device = {"id": "FS_x", "displayName": "Espresso Series 1", "activeProfileId": OLD["id"]}
    get_device = AsyncMock(side_effect=lambda *_: dict(device))
    listed = [OLD]
    get_profiles = AsyncMock(side_effect=lambda *_: list(listed))
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="FS_x",
        data={CONF_EMAIL: "a@b.c", CONF_PASSWORD: "pw", CONF_DEVICE_ID: "FS_x"},
    )
    entry.add_to_hass(hass)
    with patch(f"{API}.get_device", get_device), patch(
        f"{API}.get_profiles", get_profiles
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        get_profiles.reset_mock(side_effect=False)
        yield entry.runtime_data, device, listed, get_profiles
        assert await hass.config_entries.async_unload(entry.entry_id)


async def _poll(hass, coordinator, times=1):
    for _ in range(times):
        await coordinator.async_refresh()
    await hass.async_block_till_done()


async def test_periodic_fetch_every_tenth_poll(hass, setup):
    coordinator, _, _, get_profiles = setup
    await _poll(hass, coordinator, 9)
    assert get_profiles.await_count == 0
    await _poll(hass, coordinator)
    assert get_profiles.await_count == 1


async def test_new_active_profile_is_named_at_once(hass, setup):
    coordinator, device, listed, get_profiles = setup
    listed.append(NEW)
    device["activeProfileId"] = NEW["id"]
    await _poll(hass, coordinator)
    assert get_profiles.await_count == 1
    assert hass.states.get(ACTIVE).state == "New"
    assert hass.states.get(SELECT).state == "New"
    await _poll(hass, coordinator, 3)
    assert get_profiles.await_count == 1


async def test_switching_back_to_a_listed_profile_fetches_once(hass, setup):
    coordinator, device, listed, get_profiles = setup
    listed.append(NEW)
    device["activeProfileId"] = NEW["id"]
    await _poll(hass, coordinator)
    listed[0] = {**OLD, "title": "Old, edited"}
    device["activeProfileId"] = OLD["id"]
    await _poll(hass, coordinator, 2)
    assert get_profiles.await_count == 2
    assert hass.states.get(ACTIVE).state == "Old, edited"


async def test_unlisted_profile_retries_then_stops(hass, setup):
    coordinator, device, _, get_profiles = setup
    device["activeProfileId"] = NEW["id"]
    await _poll(hass, coordinator, 6)
    assert get_profiles.await_count == 3
    assert hass.states.get(ACTIVE).state == NEW["id"]
    assert hass.states.get(SELECT).state == "unknown"


async def test_late_listing_is_picked_up_by_a_retry(hass, setup):
    coordinator, device, listed, _ = setup
    device["activeProfileId"] = NEW["id"]
    await _poll(hass, coordinator)
    listed.append(NEW)
    await _poll(hass, coordinator)
    assert hass.states.get(ACTIVE).state == "New"


async def test_failed_fetch_is_retried(hass, setup):
    coordinator, device, listed, get_profiles = setup
    listed.append(NEW)
    device["activeProfileId"] = NEW["id"]
    working = get_profiles.side_effect
    get_profiles.side_effect = FellowConnectionError("down")
    await _poll(hass, coordinator)
    assert not coordinator.last_update_success
    get_profiles.side_effect = working
    await _poll(hass, coordinator)
    assert hass.states.get(ACTIVE).state == "New"


async def test_update_entity_fetches_edited_profiles(hass, setup):
    _, _, listed, get_profiles = setup
    assert await async_setup_component(hass, "homeassistant", {})
    listed[0] = {**OLD, "title": "Old, edited"}
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ACTIVE}, blocking=True
    )
    await hass.async_block_till_done()
    assert get_profiles.await_count == 1
    assert hass.states.get(ACTIVE).state == "Old, edited"


def _custom(profile_id, version, title):
    return {"id": profile_id, "settingsVersion": version, "title": title}


async def _with_custom_profiles(hass, setup):
    """Machine record and list agree on two custom profiles."""
    coordinator, device, listed, get_profiles = setup
    first = _custom(OLD["id"], 100, "Old")
    second = _custom("Second000003", 200, "Second")
    listed[:] = [first, second]
    device["profiles"] = [dict(first), dict(second)]
    await _poll(hass, coordinator)
    get_profiles.reset_mock(side_effect=False)
    return coordinator, device, listed, get_profiles


def _titles(hass):
    attrs = hass.states.get("sensor.espresso_series_1_profiles").attributes
    return [p["title"] for p in attrs["profiles"]]


async def test_unchanged_custom_profiles_cost_nothing(hass, setup):
    coordinator, _, _, get_profiles = await _with_custom_profiles(hass, setup)
    await _poll(hass, coordinator, 9)
    assert get_profiles.await_count == 0


@pytest.mark.parametrize("change", ["edit", "add", "remove"])
async def test_custom_profile_change_is_picked_up_next_poll(hass, setup, change):
    coordinator, device, listed, get_profiles = await _with_custom_profiles(hass, setup)
    if change == "edit":
        listed[1] = _custom("Second000003", 201, "Edited")
        expected = ["Old", "Edited"]
    elif change == "add":
        listed.append(_custom("Third0000004", 300, "Third"))
        expected = ["Old", "Second", "Third"]
    else:
        listed.pop()
        expected = ["Old"]
    device["profiles"] = [dict(p) for p in listed]
    await _poll(hass, coordinator)
    assert get_profiles.await_count == 1
    assert _titles(hass) == expected
    await _poll(hass, coordinator, 3)
    assert get_profiles.await_count == 1


async def test_lagging_list_is_retried_then_left_alone(hass, setup):
    coordinator, device, _, get_profiles = await _with_custom_profiles(hass, setup)
    device["profiles"][1]["settingsVersion"] = 201
    await _poll(hass, coordinator, 6)
    assert get_profiles.await_count == 3


async def test_lagging_list_catches_up(hass, setup):
    coordinator, device, listed, get_profiles = await _with_custom_profiles(hass, setup)
    device["profiles"][1]["settingsVersion"] = 201
    await _poll(hass, coordinator)
    listed[1] = _custom("Second000003", 201, "Edited")
    await _poll(hass, coordinator, 3)
    assert get_profiles.await_count == 2
    assert _titles(hass) == ["Old", "Edited"]


@pytest.mark.parametrize(
    "embedded",
    [None, "unexpected", [None, {"title": "no id"}],
     [{"id": "Gone00000009", "settingsVersion": 1, "deletedAt": "2026-01-01"}]],
)
async def test_odd_machine_records_cause_no_repeat_fetches(hass, setup, embedded):
    coordinator, device, _, get_profiles = setup
    device["profiles"] = embedded
    await _poll(hass, coordinator, 5)
    assert coordinator.last_update_success
    assert get_profiles.await_count <= 1
