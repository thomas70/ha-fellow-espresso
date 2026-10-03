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
        [ConnectedSensor(c), FirmwareUpgradeSensor(c), MissingWaterSensor(c)]
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


class MissingWaterSensor(FellowEspressoEntity, BinarySensorEntity):
    """The API reported null for this while idle; may populate when empty."""

    _attr_name = "Water tank empty"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:water-off"

    def __init__(self, coordinator: FellowEspressoCoordinator) -> None:
        super().__init__(coordinator, "missing_water")

    @property
    def is_on(self) -> bool | None:
        value = self.device.get("missingWater")
        return None if value is None else bool(value)
