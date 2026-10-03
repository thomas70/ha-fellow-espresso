"""Config flow for Fellow Espresso Series 1."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FellowAuthError, FellowConnectionError, FellowEspressoApi
from .const import CONF_DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


class FellowEspressoConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._creds: dict[str, str] = {}
        self._devices: list[dict[str, Any]] = []

    async def _fetch_devices(self, email: str, password: str) -> list[dict[str, Any]]:
        api = FellowEspressoApi(
            async_get_clientsession(self.hass), email, password,
            self.hass.config.time_zone or "UTC",
        )
        await api.login()
        return await api.get_espresso_devices()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                devices = await self._fetch_devices(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except FellowAuthError:
                errors["base"] = "auth"
            except FellowConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during login")
                errors["base"] = "unknown"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    self._creds = user_input
                    self._devices = devices
                    if len(devices) == 1:
                        return await self._create(devices[0])
                    return await self.async_step_pick()
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            device = next(d for d in self._devices if d["id"] == user_input[CONF_DEVICE_ID])
            return await self._create(device)
        options = {d["id"]: d.get("displayName") or d["id"] for d in self._devices}
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_ID): vol.In(options)}),
        )

    async def _create(self, device: dict[str, Any]) -> ConfigFlowResult:
        await self.async_set_unique_id(device["id"])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=device.get("displayName") or "Espresso Series 1",
            data={**self._creds, CONF_DEVICE_ID: device["id"]},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await self._fetch_devices(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            except FellowAuthError:
                errors["base"] = "auth"
            except FellowConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, {CONF_EMAIL: entry.data.get(CONF_EMAIL)}
            ),
            errors=errors,
        )
