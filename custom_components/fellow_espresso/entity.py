"""Base entity for Fellow Espresso Series 1."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FellowEspressoCoordinator


class FellowEspressoEntity(CoordinatorEntity[FellowEspressoCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: FellowEspressoCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        dev = self.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer="Fellow",
            model="Espresso Series 1",
            model_id=dev.get("sku"),
            name=dev.get("displayName") or "Espresso Series 1",
            sw_version=dev.get("firmwareVersion"),
        )

    @property
    def device(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("device") or {}
