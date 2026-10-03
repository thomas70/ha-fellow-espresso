"""Fellow Espresso Series 1 integration (read-only, cloud polling)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FellowEspressoApi
from .coordinator import FellowEspressoCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type FellowEspressoConfigEntry = ConfigEntry[FellowEspressoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FellowEspressoConfigEntry) -> bool:
    api = FellowEspressoApi(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        hass.config.time_zone or "UTC",
    )
    coordinator = FellowEspressoCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FellowEspressoConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
