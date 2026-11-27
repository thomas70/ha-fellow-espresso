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
from .profiles import BUILTIN_PROFILES, builtin_name, profile_options

_LOGGER = logging.getLogger(__name__)

PROFILE_REFRESH_EVERY = 10  # fetch profiles at least every Nth poll
# Fetches after a change while the list still lags behind the machine record.
PROFILE_CATCH_UP_TRIES = 3


def _custom_profile_stamps(device: dict[str, Any]) -> frozenset[tuple[str, str]]:
    """(id, settingsVersion) of the custom profiles held in the machine record.

    The record is polled every time, and an edited, added or removed custom
    profile shows up here without fetching the profile list.
    """
    profiles = device.get("profiles")
    if not isinstance(profiles, list):
        return frozenset()
    return frozenset(
        (p["id"], str(p.get("settingsVersion")))
        for p in profiles
        if isinstance(p, dict)
        and isinstance(p.get("id"), str)
        and not p.get("deletedAt")
    )


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
        self._profiles: list[dict[str, Any]] = []
        self._polls_since_profiles = 0
        self._force_profiles = False
        # Active profile id and custom profile stamps at the last good poll.
        self._last_seen: tuple[str | None, frozenset[tuple[str, str]]] | None = None
        self._catch_up_tries = 0
        # Built-in profile ids seen as active (they are not in the profile list).
        self.seen_profile_ids: set[str] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            device = await self.api.get_device(self.device_id)
            active_id = device.get("activeProfileId")
            stamps = _custom_profile_stamps(device)
            self._polls_since_profiles += 1
            changed = (active_id, stamps) != self._last_seen
            if changed:
                self._catch_up_tries = 0
            if self._profiles_due(active_id, stamps, changed):
                self._profiles = await self.api.get_profiles(self.device_id)
                self._polls_since_profiles = 0
                self._force_profiles = False
                if self._is_behind(active_id, stamps):
                    self._catch_up_tries += 1
        except FellowAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FellowError as err:
            raise UpdateFailed(str(err)) from err
        # Only after a successful poll, so a failed profile fetch is retried.
        self._last_seen = (active_id, stamps)
        if active_id:
            self.seen_profile_ids.add(active_id)
        return {"device": device, "profiles": self._profiles}

    def _profiles_due(
        self,
        active_id: str | None,
        stamps: frozenset[tuple[str, str]],
        changed: bool,
    ) -> bool:
        """Whether this poll should also fetch the profile list."""
        return (
            not self._profiles
            or self._force_profiles
            or changed
            or self._polls_since_profiles >= PROFILE_REFRESH_EVERY
            or (
                self._catch_up_tries < PROFILE_CATCH_UP_TRIES
                and self._is_behind(active_id, stamps)
            )
        )

    def _is_behind(
        self, active_id: str | None, stamps: frozenset[tuple[str, str]]
    ) -> bool:
        """Whether the cached list lacks something the machine record shows."""
        listed = {p.get("id"): str(p.get("settingsVersion")) for p in self._profiles}
        if active_id and active_id not in BUILTIN_PROFILES and active_id not in listed:
            return True
        return any(listed.get(pid) != version for pid, version in stamps)

    async def async_request_refresh(self) -> None:
        """Manual refresh (homeassistant.update_entity): fetch profiles too."""
        self._force_profiles = True
        await super().async_request_refresh()

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
