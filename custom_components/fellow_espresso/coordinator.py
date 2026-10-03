"""Polling coordinator for Fellow Espresso Series 1."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FellowAuthError, FellowError, FellowEspressoApi
from .const import CONF_DEVICE_ID, DEFAULT_SCAN_INTERVAL, DOMAIN
from .profiles import builtin_name, profile_options

_LOGGER = logging.getLogger(__name__)

PROFILE_REFRESH_EVERY = 10  # fetch profiles every Nth poll


class FellowEspressoCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches device state, and profiles less often."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: FellowEspressoApi
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.api = api
        self.device_id: str = entry.data[CONF_DEVICE_ID]
        self._polls = 0
        self._profiles: list[dict[str, Any]] = []
        # Built-in profile ids seen as active (they are not in the profile list).
        self.seen_profile_ids: set[str] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            device = await self.api.get_device(self.device_id)
            if self._polls % PROFILE_REFRESH_EVERY == 0 or not self._profiles:
                self._profiles = await self.api.get_profiles(self.device_id)
        except FellowAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FellowError as err:
            raise UpdateFailed(str(err)) from err
        self._polls += 1
        active_id = device.get("activeProfileId")
        if active_id:
            self.seen_profile_ids.add(active_id)
        return {"device": device, "profiles": self._profiles}

    def active_profile(self) -> dict[str, Any] | None:
        data = self.data or {}
        active_id = (data.get("device") or {}).get("activeProfileId")
        for profile in data.get("profiles") or []:
            if profile.get("id") == active_id:
                return profile
        return None

    def active_profile_id(self) -> str | None:
        return ((self.data or {}).get("device") or {}).get("activeProfileId")

    def active_profile_name(self) -> str | None:
        active_id = self.active_profile_id()
        if not active_id:
            return None
        profile = self.active_profile()
        if profile:
            return profile.get("title") or active_id
        return builtin_name(active_id)

    def profile_options(self) -> dict[str, str]:
        """{display name: profile id} for every selectable profile."""
        return profile_options(
            (self.data or {}).get("profiles") or [], self.seen_profile_ids
        )

    async def async_set_active_profile(self, profile_id: str) -> None:
        """Switch profile and show it right away; the next poll confirms it."""
        try:
            await self.api.set_active_profile(self.device_id, profile_id)
        except FellowAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FellowError as err:
            raise HomeAssistantError(f"Could not change profile: {err}") from err
        data = dict(self.data or {})
        data["device"] = {**(data.get("device") or {}), "activeProfileId": profile_id}
        self.seen_profile_ids.add(profile_id)
        self.async_set_updated_data(data)
