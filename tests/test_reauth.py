"""Signing in again must be for the same machine."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fellow_espresso.const import CONF_DEVICE_ID, DOMAIN

API = "custom_components.fellow_espresso.api.FellowEspressoApi"
OLD_DATA = {CONF_EMAIL: "a@b.c", CONF_PASSWORD: "old", CONF_DEVICE_ID: "FS_x"}


async def _reauth(hass, devices):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="FS_x", data=dict(OLD_DATA))
    entry.add_to_hass(hass)
    with patch(f"{API}.login", AsyncMock()), patch(
        f"{API}.get_espresso_devices", devices
    ), patch(
        "custom_components.fellow_espresso.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "new@b.c", CONF_PASSWORD: "new"}
        )
        await hass.async_block_till_done()
    return entry, result


@pytest.mark.parametrize("found", [[], [{"id": "FS_other"}]])
async def test_account_without_this_machine_is_rejected(hass, found):
    entry, result = await _reauth(hass, AsyncMock(return_value=found))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_account"}
    assert dict(entry.data) == OLD_DATA


async def test_account_with_this_machine_is_accepted(hass):
    devices = AsyncMock(return_value=[{"id": "FS_other"}, {"id": "FS_x"}])
    entry, result = await _reauth(hass, devices)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"
    assert entry.data[CONF_DEVICE_ID] == "FS_x"


async def test_unexpected_error_is_reported(hass):
    entry, result = await _reauth(hass, AsyncMock(side_effect=RuntimeError("boom")))
    assert result["errors"] == {"base": "unknown"}
    assert dict(entry.data) == OLD_DATA
