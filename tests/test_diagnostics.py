"""Diagnostics must not leak account, machine or user-written data."""
import json
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fellow_espresso.const import CONF_DEVICE_ID, DOMAIN
from custom_components.fellow_espresso.diagnostics import (
    async_get_config_entry_diagnostics,
)

API = "custom_components.fellow_espresso.api.FellowEspressoApi"
CUSTOM_ID = "SecretProfileId"

PROFILE = {
    "id": CUSTOM_ID, "title": "secret title", "roasterName": "secret roaster",
    "notes": "secret notes", "sharedFrom": "secret sharer", "folder": "custom",
    "dose": 18, "infusion": [{"duration": 25, "pressure": 9, "extra": "secret stage"}],
    "device": {"serialNumber": "secret-serial", "timezone": "secret/zone"},
}
DEVICE = {
    "id": "FS_secret", "displayName": "secret name", "serialNumber": "secret-serial",
    "firmwareVersion": "2.5.15", "chime": "high", "activeProfileId": CUSTOM_ID,
    "profiles": [PROFILE], "somethingNew": "secret unknown",
    "nested": {"token": "secret token"},
}


async def test_diagnostics_redaction(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="FS_secret",
        data={
            CONF_EMAIL: "secret@example.com", CONF_PASSWORD: "secret-password",
            CONF_DEVICE_ID: "FS_secret",
        },
    )
    entry.add_to_hass(hass)
    builtin = {"id": "5_lever", "title": "Lever", "folder": "fellow"}
    with patch(f"{API}.get_device", AsyncMock(return_value=DEVICE)), patch(
        f"{API}.get_profiles", AsyncMock(return_value=[PROFILE, builtin])
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        result = await async_get_config_entry_diagnostics(hass, entry)
        assert await hass.config_entries.async_unload(entry.entry_id)

    text = json.dumps(result).lower()
    assert "secret@" not in text
    for leaked in ("secret", "fs_"):
        assert leaked not in text, text

    # Still useful for debugging.
    assert result["device"]["firmwareVersion"] == "2.5.15"
    assert result["device"]["chime"] == "high"
    assert result["device"]["somethingNew"] == "<str>"
    assert "token" in result["device"]["nested"]
    assert result["device"]["activeProfileId"] == "profile-1"
    assert result["device"]["profiles"][0]["id"] == "profile-1"
    assert result["profiles"][0]["id"] == "profile-1"
    assert result["profiles"][0]["infusion"] == [{"duration": 25, "pressure": 9}]
    assert result["profiles"][1]["id"] == "5_lever"
