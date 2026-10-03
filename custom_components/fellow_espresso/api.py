"""Minimal async client for the Fellow cloud API (Espresso Series 1 / "Solo").

Endpoints confirmed working for deviceType "Solo":
  POST /auth/login                   -> {accessToken, refreshToken} (HTTP 201)
  POST /auth/refresh-token           -> {accessToken[, refreshToken]}
  GET  /devices?dataType=real        -> list of all devices on the account
  GET  /solo/devices/{id}            -> device state/settings
  GET  /solo/devices/{id}/profiles   -> espresso profiles
  PATCH /solo/devices/{id}/active-profile
        {"profileId": "...", "settingsVersion": <unix seconds>} -> 204
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from .const import DEVICE_TYPE_SOLO

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://l8qtmnc692.execute-api.us-west-2.amazonaws.com/v2"
USER_AGENT = "Fellow/5 CFNetwork/1568.300.101 Darwin/24.2.0"
TIMEOUT = aiohttp.ClientTimeout(total=20)


class FellowError(Exception):
    """Base error."""


class FellowAuthError(FellowError):
    """Wrong credentials."""


class FellowConnectionError(FellowError):
    """Network or server problem."""


class FellowEspressoApi:
    """Talks to the Fellow cloud for one account."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        timezone: str = "UTC",
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._timezone = timezone
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._lock = asyncio.Lock()

    # -- low level -------------------------------------------------------

    def _headers(self, auth: bool) -> dict[str, str]:
        headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _raw(
        self, method: str, path: str, *, auth: bool = True, **kwargs: Any
    ) -> tuple[int, Any]:
        try:
            async with self._session.request(
                method,
                BASE_URL + path,
                headers=self._headers(auth),
                timeout=TIMEOUT,
                **kwargs,
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    data = await resp.text()
                return resp.status, data
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise FellowConnectionError(str(err)) from err

    # -- auth ------------------------------------------------------------

    async def login(self) -> None:
        status, data = await self._raw(
            "post",
            "/auth/login",
            auth=False,
            json={
                "email": self._email,
                "password": self._password,
                "timezone": self._timezone,
            },
        )
        if status in (400, 401, 403):
            raise FellowAuthError("Invalid email or password")
        if not 200 <= status < 300 or not isinstance(data, dict) or "accessToken" not in data:
            raise FellowConnectionError(f"Login failed: HTTP {status}")
        self._token = data["accessToken"]
        self._refresh_token = data.get("refreshToken")

    async def _refresh(self) -> bool:
        if not self._refresh_token:
            return False
        status, data = await self._raw(
            "post",
            "/auth/refresh-token",
            auth=False,
            json={"refreshToken": self._refresh_token},
        )
        if not 200 <= status < 300 or not isinstance(data, dict) or "accessToken" not in data:
            return False
        self._token = data["accessToken"]
        self._refresh_token = data.get("refreshToken", self._refresh_token)
        return True

    async def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        """Authenticated request; refreshes or re-logs in once on HTTP 401."""
        async with self._lock:
            if not self._token:
                await self.login()
        status, data = await self._raw(method, path, **kwargs)
        if status == 401:
            async with self._lock:
                refreshed = await self._refresh()
                if not refreshed:
                    await self.login()
            status, data = await self._raw(method, path, **kwargs)
            if status == 401 and refreshed:
                async with self._lock:
                    await self.login()
                status, data = await self._raw(method, path, **kwargs)
        if status == 401:
            raise FellowAuthError("Not authorized")
        if not 200 <= status < 300:
            raise FellowConnectionError(
                f"{method.upper()} {path} failed: HTTP {status}: {data}"
            )
        return data

    async def _get(self, path: str) -> Any:
        return await self._call("get", path, params={"dataType": "real"})

    # -- endpoints -------------------------------------------------------

    async def get_espresso_devices(self) -> list[dict[str, Any]]:
        data = await self._get("/devices")
        if not isinstance(data, list):
            raise FellowConnectionError("Unexpected /devices payload")
        return [
            d
            for d in data
            if isinstance(d, dict)
            and d.get("deviceType") == DEVICE_TYPE_SOLO
            and not d.get("deletedAt")
        ]

    async def get_device(self, device_id: str) -> dict[str, Any]:
        data = await self._get(f"/solo/devices/{device_id}")
        if not isinstance(data, dict):
            raise FellowConnectionError("Unexpected device payload")
        return data

    async def get_profiles(self, device_id: str) -> list[dict[str, Any]]:
        data = await self._get(f"/solo/devices/{device_id}/profiles")
        if not isinstance(data, list):
            return []
        return [p for p in data if isinstance(p, dict) and not p.get("deletedAt")]

    async def set_active_profile(self, device_id: str, profile_id: str) -> None:
        """Switch the machine's active profile, as the Fellow app does.

        The app sends the current Unix time (seconds) as settingsVersion.
        """
        await self._call(
            "patch",
            f"/solo/devices/{device_id}/active-profile",
            json={"profileId": profile_id, "settingsVersion": int(time.time())},
        )
