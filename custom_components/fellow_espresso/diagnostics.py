"""Diagnostics for Fellow Espresso Series 1.

Fellow's API is undocumented and may return fields nobody has looked at, so this
works from an allowlist: only the values named here are included. Every other
field is listed by name and type, never by value.
"""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import FellowEspressoConfigEntry
from .profiles import is_builtin_id

REDACTED = "**REDACTED**"

DEVICE_VALUES = frozenset(
    {
        "deviceType", "sku", "firmwareVersion", "firmwareUpgradeRequired",
        "isConnected", "settingsVersion", "version", "enabledFlags",
        "descaleRem", "backflushRem", "showerRem", "totalDescaleCount",
        "totalBackflushCount", "totalShowerCount", "missingWater",
        "waterHardness", "autoStop", "preheat", "groupRinse", "chime",
        "brewGuidance", "metricUnit", "preciseUnit", "dvolUnit", "tempUnit",
        "bvolUnit", "whUnit", "htUnit", "showDrops",
    }
)

PROFILE_VALUES = frozenset(
    {
        "folder", "dose", "ratio", "temperature", "grindSize",
        "preInfusionEnabled", "preInfusionDuration", "preInfusionHoldPressure",
        "preInfusionFillFlowRate", "transition", "decliningTemp",
        "rampDownEnabled", "rampDownEndPressure", "rampDownDuration",
        "adaptive", "synced", "version", "settingsVersion",
    }
)


def _describe(value: Any) -> str:
    """What a value is, without saying what it holds."""
    if isinstance(value, dict):
        return f"<object with keys: {', '.join(sorted(map(str, value)))}>"
    return f"<{type(value).__name__}>"


class _ProfileIds:
    """Keeps built-in ids; replaces account ids with stable placeholders."""

    def __init__(self) -> None:
        self._aliases: dict[str, str] = {}

    def __call__(self, profile_id: Any) -> Any:
        if not isinstance(profile_id, str):
            return None if profile_id is None else _describe(profile_id)
        if is_builtin_id(profile_id):
            return profile_id
        return self._aliases.setdefault(profile_id, f"profile-{len(self._aliases) + 1}")


def _profile(profile: Any, ids: _ProfileIds) -> Any:
    if not isinstance(profile, dict):
        return _describe(profile)
    out: dict[str, Any] = {}
    for key, value in profile.items():
        if key == "id":
            out[key] = ids(value)
        elif key == "infusion" and isinstance(value, list):
            out[key] = [
                {k: stage.get(k) for k in ("duration", "pressure")}
                if isinstance(stage, dict) else _describe(stage)
                for stage in value
            ]
        elif key in PROFILE_VALUES:
            out[key] = value
        else:
            out[key] = _describe(value)
    return out


def _device(device: dict[str, Any], ids: _ProfileIds) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in device.items():
        if key == "activeProfileId":
            out[key] = ids(value)
        elif key == "profiles" and isinstance(value, list):
            out[key] = [_profile(p, ids) for p in value]
        elif key in DEVICE_VALUES:
            out[key] = value
        else:
            out[key] = _describe(value)
    return out


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FellowEspressoConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    ids = _ProfileIds()
    error = coordinator.last_exception
    return {
        "entry": {key: REDACTED for key in entry.data},
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            # The type only: messages can contain the device id.
            "last_error_type": type(error).__name__ if error else None,
        },
        "profiles": [_profile(p, ids) for p in data.get("profiles") or []],
        "device": _device(data.get("device") or {}, ids),
    }
