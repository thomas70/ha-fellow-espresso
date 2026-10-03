"""Binary sensors for Fellow Espresso Series 1."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FellowEspressoConfigEntry
from .coordinator import FellowEspressoCoordinator
from .entity import FellowEspressoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FellowEspressoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    c = entry.runtime_data
    async_add_entities(
        [ConnectedSensor(c), FirmwareUpgradeSensor(c)]
    )


class ConnectedSensor(FellowEspressoEntity, BinarySensorEntity):
    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FellowEspressoCoordinator) -> None:
        super().__init__(coordinator, "connected")

    @property
    def is_on(self) -> bool | None:
        return self.device.get("isConnected")


class FirmwareUpgradeSensor(FellowEspressoEntity, BinarySensorEntity):
    _attr_name = "Firmware upgrade required"
    _attr_device_class = BinarySensorDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FellowEspressoCoordinator) -> None:
        super().__init__(coordinator, "firmware_upgrade_required")

    @property
    def is_on(self) -> bool | None:
        return self.device.get("firmwareUpgradeRequired")

