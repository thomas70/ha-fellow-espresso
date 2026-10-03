"""Profile selector for Fellow Espresso Series 1."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FellowEspressoConfigEntry
from .coordinator import FellowEspressoCoordinator
from .entity import FellowEspressoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FellowEspressoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([ProfileSelect(entry.runtime_data)])


class ProfileSelect(FellowEspressoEntity, SelectEntity):
    """Pick the machine's active espresso profile."""

    _attr_name = "Profile"
    _attr_icon = "mdi:coffee-maker-outline"

    def __init__(self, coordinator: FellowEspressoCoordinator) -> None:
        super().__init__(coordinator, "profile_select")

    @property
    def options(self) -> list[str]:
        return list(self.coordinator.profile_options())

    @property
    def current_option(self) -> str | None:
        active_id = self.coordinator.active_profile_id()
        for name, pid in self.coordinator.profile_options().items():
            if pid == active_id:
                return name
        return None

    async def async_select_option(self, option: str) -> None:
        profile_id = self.coordinator.profile_options().get(option)
        if profile_id is None:
            raise ServiceValidationError(f"Unknown profile: {option}")
        if profile_id == self.coordinator.active_profile_id():
            return
        await self.coordinator.async_set_active_profile(profile_id)
