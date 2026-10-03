"""Sensors for Fellow Espresso Series 1."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FellowEspressoConfigEntry
from .coordinator import FellowEspressoCoordinator
from .entity import FellowEspressoEntity


@dataclass(frozen=True, kw_only=True)
class FellowSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


def _field(name: str) -> Callable[[dict[str, Any]], Any]:
    return lambda dev: dev.get(name)


SENSORS: tuple[FellowSensorDescription, ...] = (
    # Maintenance intervals as configured on the machine (Settings → Maintenance
    # → Cleaning interval). The machine's progress toward them (e.g. 33/200)
    # is not sent to Fellow's cloud.
    FellowSensorDescription(
        key="descale_interval", name="Descale interval",
        icon="mdi:water-alert", native_unit_of_measurement="drinks",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("descaleRem"),
    ),
    FellowSensorDescription(
        key="backflush_interval", name="Backflush interval",
        icon="mdi:backup-restore", native_unit_of_measurement="shots",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("backflushRem"),
    ),
    FellowSensorDescription(
        key="shower_interval", name="Shower screen clean interval",
        icon="mdi:shower-head",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("showerRem"),
    ),
    # Lifetime counters
    FellowSensorDescription(
        key="total_descales", name="Total descales", icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("totalDescaleCount"),
    ),
    FellowSensorDescription(
        key="total_backflushes", name="Total backflushes", icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("totalBackflushCount"),
    ),
    FellowSensorDescription(
        key="total_showers", name="Total shower screen cleans", icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("totalShowerCount"),
    ),
    # Settings / diagnostics
    FellowSensorDescription(
        key="water_hardness", name="Water hardness", icon="mdi:water-opacity",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("waterHardness"),
    ),
    FellowSensorDescription(
        key="firmware", name="Firmware", icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("firmwareVersion"),
    ),
    FellowSensorDescription(
        key="auto_stop", name="Auto stop", icon="mdi:stop-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("autoStop"),
    ),
    FellowSensorDescription(
        key="preheat", name="Preheat", icon="mdi:fire",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_field("preheat"),
    ),
)

PROFILE_ATTRS = (
    "roasterName", "dose", "ratio", "temperature", "grindSize",
    "preInfusionEnabled", "preInfusionDuration", "preInfusionHoldPressure",
    "infusion", "rampDownEnabled", "adaptive", "folder",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FellowEspressoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        FellowSensor(coordinator, desc) for desc in SENSORS
    ]
    entities += [ActiveProfileSensor(coordinator), ProfilesSensor(coordinator)]
    async_add_entities(entities)


class FellowSensor(FellowEspressoEntity, SensorEntity):
    entity_description: FellowSensorDescription

    def __init__(
        self, coordinator: FellowEspressoCoordinator, description: FellowSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.device)


class ActiveProfileSensor(FellowEspressoEntity, SensorEntity):
    _attr_name = "Active profile"
    _attr_icon = "mdi:coffee"

    def __init__(self, coordinator: FellowEspressoCoordinator) -> None:
        super().__init__(coordinator, "active_profile")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.active_profile_name()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {"profile_id": self.device.get("activeProfileId")}
        profile = self.coordinator.active_profile()
        if profile:
            attrs.update({k: profile.get(k) for k in PROFILE_ATTRS})
        return attrs


class ProfilesSensor(FellowEspressoEntity, SensorEntity):
    _attr_name = "Profiles"
    _attr_icon = "mdi:format-list-bulleted"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: FellowEspressoCoordinator) -> None:
        super().__init__(coordinator, "profiles")

    @property
    def native_value(self) -> int:
        return len((self.coordinator.data or {}).get("profiles") or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        profiles = (self.coordinator.data or {}).get("profiles") or []
        return {
            "profiles": [
                {
                    "id": p.get("id"),
                    "title": p.get("title"),
                    "roaster": p.get("roasterName"),
                    "dose": p.get("dose"),
                    "ratio": p.get("ratio"),
                    "temperature": p.get("temperature"),
                    "grind_size": p.get("grindSize"),
                }
                for p in profiles
            ]
        }
