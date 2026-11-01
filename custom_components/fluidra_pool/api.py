"""Fluidra cloud client (REST + WebSocket push): the seam a local transport can replace."""
import asyncio
from collections.abc import Callable, Iterable
import json
import logging
import math
import time
from typing import Any
from urllib.parse import quote

import aiohttp

from .auth import TIMEOUT, FluidraAuth, FluidraAuthError, FluidraConnectionError
from .const import (
    API_DEVICES_URL,
    API_ENDPOINT_DEVICE_COMPONENTS,
    API_ENDPOINT_DEVICE_UICONFIG,
    API_ENDPOINT_SET_COMPONENT_VALUE,
    WS_URL,
)

_LOGGER = logging.getLogger(__name__)

HEARTBEAT = 30  # seconds between WebSocket pings
BACKOFF_MIN, BACKOFF_MAX = 5, 300  # seconds between WebSocket reconnects
STABLE_AFTER = 60  # a connection that stayed up this long resets the backoff
SUBSCRIBE = {"action": "subsDevice", "deviceType": "connected"}  # + "deviceId"
_sleep = asyncio.sleep  # patched by tests

OnUpdate = Callable[[str, int, Any, float], None]


class FluidraApi:
    """Read and set Fluidra device components; stream their changes."""

    def __init__(self, auth: FluidraAuth, session: aiohttp.ClientSession) -> None:
        self._auth = auth
        self._session = session

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return the account's connected devices."""
        return await self._json("GET", f"{API_DEVICES_URL}?deviceType=connected")

    async def async_get_components(self, device_id: str) -> dict[int, dict[str, Any]]:
        """Return {component id: {"id", "reportedValue", "desiredValue"?, "ts"}}."""
        url = API_ENDPOINT_DEVICE_COMPONENTS.format(device_id=quote(device_id, safe=""))
        components = await self._json("GET", url)
        return {int(component["id"]): component for component in components}

    async def async_get_uiconfig(self, device_id: str) -> dict[str, Any] | None:
        """Return the device's UI config, or None when the cloud answers 4xx/5xx for it."""
        url = API_ENDPOINT_DEVICE_UICONFIG.format(device_id=quote(device_id, safe=""))
        status, data = await self._request("GET", url)
        if status >= 400:  # e.g. 500 for some non-heat-pump devices (#4 #5)
            _LOGGER.debug("No UI config for %s: HTTP %d", device_id, status)
            return None
        return data

    async def async_set_component(
        self, device_id: str, component_id: int, value: Any
    ) -> dict[str, Any]:
        """Ask the device to set a component to value; return the cloud's reply."""
        url = API_ENDPOINT_SET_COMPONENT_VALUE.format(
            device_id=quote(device_id, safe=""), component_id=component_id
        )
        return await self._json("PUT", url, {"desiredValue": value}) or {}

    async def async_listen(self, device_ids: Iterable[str], on_update: OnUpdate) -> None:
        """Call on_update(device_id, component_id, value, ts) for every push, until cancelled.

        device_ids is iterated again on every (re)connect.
        """
        delay, warned = BACKOFF_MIN, False
        while True:
            connected_at = None
            try:
                token = await self._auth.async_get_access_token()
                async with self._session.ws_connect(
                    WS_URL, params={"token": token}, heartbeat=HEARTBEAT
                ) as ws:
                    connected_at = time.monotonic()
                    _LOGGER.debug("WebSocket connected")
                    if warned:
                        _LOGGER.info("Fluidra WebSocket push restored")
                        warned = False
                    for device_id in device_ids:
                        await ws.send_json({**SUBSCRIBE, "deviceId": device_id})
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT and (update := _parse_push(msg.data)):
                            try:
                                on_update(*update)
                            except Exception:
                                _LOGGER.exception("Fluidra push update failed")
                _LOGGER.debug("WebSocket closed")
            except FluidraAuthError:
                # Retrying could lock the account. The poll starts reauth; its reload restarts this.
                _LOGGER.debug("WebSocket stopped: login rejected")
                return
            except (aiohttp.ClientError, TimeoutError, FluidraConnectionError) as err:
                # Never log err itself: aiohttp errors can carry the URL, which holds the token.
                _LOGGER.debug("WebSocket failed: %s", type(err).__name__)
            if connected_at is not None and time.monotonic() - connected_at >= STABLE_AFTER:
                delay = BACKOFF_MIN
            _LOGGER.debug("WebSocket reconnecting in %d s", delay)
            await _sleep(delay)
            if delay < BACKOFF_MAX <= delay * 2:  # the delay reaches the maximum
                _LOGGER.warning(
                    "Fluidra WebSocket push unavailable; retrying every %d s; "
                    "values update by polling",
                    BACKOFF_MAX,
                )
                warned = True
            delay = min(delay * 2, BACKOFF_MAX)

    async def _json(self, method: str, url: str, payload: Any = None) -> Any:
        """Return the JSON reply of a successful call; any HTTP error is a connection error."""
        status, data = await self._request(method, url, payload)
        if status >= 400:
            raise FluidraConnectionError(f"{method} {url}: HTTP {status}")
        return data

    async def _request(self, method: str, url: str, payload: Any = None) -> tuple[int, Any]:
        """Return (status, JSON or None); a 401 renews the token and retries once."""
        status, data = await self._send(method, url, payload)
        if status == 401:
            _LOGGER.debug("%s %s: HTTP 401, renewing the access token", method, url)
            self._auth.invalidate_access_token()
            status, data = await self._send(method, url, payload)
            if status == 401:
                raise FluidraAuthError(f"{method} {url}: HTTP 401 with a fresh token")
        return status, data

    async def _send(self, method: str, url: str, payload: Any) -> tuple[int, Any]:
        """Make one call with the current token; the body is only read on success."""
        token = await self._auth.async_get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with self._session.request(
                method, url, json=payload, headers=headers, timeout=TIMEOUT
            ) as resp:
                if resp.status >= 400:
                    return resp.status, None
                return resp.status, await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise FluidraConnectionError(f"{method} {url}: {type(err).__name__}") from err


def _parse_push(raw: str) -> tuple[str, int, Any, float] | None:
    """Return (device_id, component_id, value, ts) of a component update, else None."""
    try:
        event = json.loads(raw)
        if isinstance(event.get("body"), str):  # e.g. subscribe replies wrap a JSON string
            event = {**event, **json.loads(event["body"])}
        ts = float(event.get("ts") or time.time())
        if ts > 1e11:  # milliseconds (push format unverified); REST ts is in seconds
            ts /= 1000
        if not math.isfinite(ts) or ts > time.time() + 60:  # would outrank every later value
            ts = time.time()
        if isinstance(device_id := event["deviceId"], str):
            return device_id, int(event["componentId"]), event["reportedValue"], ts
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        pass
    _LOGGER.debug("WebSocket message ignored (not a component update)")
    return None
