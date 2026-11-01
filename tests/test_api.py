"""Tests for the Fluidra REST + WebSocket client. Fake ids and tokens only."""
import asyncio
import json
import logging
import time

import aiohttp
from aiohttp import web
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from yarl import URL

from custom_components.fluidra_pool import api as api_module
from custom_components.fluidra_pool.api import FluidraApi
from custom_components.fluidra_pool.auth import (
    COGNITO_URL,
    FluidraAuth,
    FluidraAuthError,
    FluidraConnectionError,
)
from custom_components.fluidra_pool.const import (
    API_DEVICES_URL,
    API_ENDPOINT_DEVICE_COMPONENTS,
    API_ENDPOINT_DEVICE_UICONFIG,
    API_ENDPOINT_SET_COMPONENT_VALUE,
)

from .conftest import DEVICE_ID, DEVICES, load_fixture

ACCESS, ACCESS_2 = "test-access-token-1", "test-access-token-2"
DEVICES_URL = f"{API_DEVICES_URL}?deviceType=connected"
COMPONENTS_URL = API_ENDPOINT_DEVICE_COMPONENTS.format(device_id=DEVICE_ID)
UICONFIG_URL = API_ENDPOINT_DEVICE_UICONFIG.format(device_id=DEVICE_ID)
SET_URL = API_ENDPOINT_SET_COMPONENT_VALUE.format(device_id=DEVICE_ID, component_id=15)
DEVICE_IDS = [DEVICE_ID, "TEST000002"]
SUBSCRIBE = [{"action": "subsDevice", "deviceType": "connected", "deviceId": d} for d in DEVICE_IDS]
MAX_SLEEPS = 8


# ── REST ─────────────────────────────────────────────────────────────────────


def tokens(access):
    """A successful Cognito auth response."""
    result = {"AccessToken": access, "ExpiresIn": 3600, "RefreshToken": "test-refresh-token"}
    return {"payload": {"AuthenticationResult": result}}


def calls(mock, method, url):
    """Recorded aioresponses calls for one method + URL."""
    return mock.requests.get((method, URL(url)), [])


@pytest.fixture
def cloud():
    """aioresponses where Cognito hands out ACCESS, then ACCESS_2."""
    with aioresponses() as mock:
        mock.post(COGNITO_URL, **tokens(ACCESS))
        mock.post(COGNITO_URL, **tokens(ACCESS_2))
        yield mock


@pytest.fixture
async def api(hass: HomeAssistant):
    """FluidraApi on HA's shared session with a real FluidraAuth."""
    session = async_get_clientsession(hass)
    return FluidraApi(FluidraAuth(session, "test-username", "test-password"), session)


async def test_get_devices(api, cloud) -> None:
    cloud.get(DEVICES_URL, payload=DEVICES)
    assert await api.async_get_devices() == DEVICES
    (call,) = calls(cloud, "GET", DEVICES_URL)
    headers = dict(call.kwargs["headers"])
    assert headers.pop("User-Agent").startswith("HomeAssistant/")  # HA session default
    assert headers == {
        "Authorization": f"Bearer {ACCESS}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    assert call.kwargs["timeout"].total == 15


async def test_get_components_keyed_by_int(api, cloud) -> None:
    cloud.get(COMPONENTS_URL, payload=load_fixture("components_amt.json"))
    components = await api.async_get_components(DEVICE_ID)
    assert sorted(components) == [1, 2, 3, 4, 11, 13, 14, 15, 19, 28, 62]
    assert components[15] == {"id": 15, "reportedValue": 280, "desiredValue": 280, "ts": 1758877765}


async def test_get_uiconfig_none_on_http_error(api, cloud) -> None:
    cloud.get(UICONFIG_URL, payload={"groups": []})
    cloud.get(UICONFIG_URL, status=500, body="<html>error</html>")
    assert await api.async_get_uiconfig(DEVICE_ID) == {"groups": []}
    assert await api.async_get_uiconfig(DEVICE_ID) is None


async def test_set_component_body(api, cloud) -> None:
    cloud.put(SET_URL, payload={"id": 15, "desiredValue": 300})
    assert await api.async_set_component(DEVICE_ID, 15, 300) == {"id": 15, "desiredValue": 300}
    (call,) = calls(cloud, "PUT", SET_URL)
    assert call.kwargs["json"] == {"desiredValue": 300}


async def test_401_renews_token_and_retries_once(api, cloud, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    cloud.get(DEVICES_URL, status=401)
    cloud.get(DEVICES_URL, payload=DEVICES)
    assert await api.async_get_devices() == DEVICES
    bearers = [c.kwargs["headers"]["Authorization"] for c in calls(cloud, "GET", DEVICES_URL)]
    assert bearers == [f"Bearer {ACCESS}", f"Bearer {ACCESS_2}"]
    flows = [c.kwargs["json"]["AuthFlow"] for c in calls(cloud, "POST", COGNITO_URL)]
    assert flows == ["USER_PASSWORD_AUTH", "REFRESH_TOKEN_AUTH"]  # the refresh token survived
    assert "HTTP 401" in caplog.text
    assert ACCESS not in caplog.text and ACCESS_2 not in caplog.text


async def test_401_twice_raises_auth_error(api, cloud) -> None:
    cloud.get(DEVICES_URL, status=401, repeat=True)
    with pytest.raises(FluidraAuthError):
        await api.async_get_devices()
    assert len(calls(cloud, "GET", DEVICES_URL)) == 2


@pytest.mark.parametrize(
    "response",
    [
        {"status": 500, "body": "<html>error</html>"},
        {"status": 403},
        {"exception": asyncio.TimeoutError()},
        {"exception": aiohttp.ClientConnectionError()},
        {"body": "not json"},
    ],
    ids=["http500", "http403", "timeout", "network", "bad-json"],
)
async def test_failures_raise_connection_error(api, cloud, response) -> None:
    cloud.get(COMPONENTS_URL, **response)
    with pytest.raises(FluidraConnectionError):
        await api.async_get_components(DEVICE_ID)


# ── WebSocket ────────────────────────────────────────────────────────────────


class FakeAuth:
    """Hands out a new token per call: test-ws-token-1, test-ws-token-2, ..."""

    calls = 0

    async def async_get_access_token(self) -> str:
        self.calls += 1
        return f"test-ws-token-{self.calls}"


@pytest.fixture
def ws_server(aiohttp_server, socket_enabled, monkeypatch):
    """Start a local WebSocket server running handler and point the client at it."""

    async def start(handler):
        app = web.Application()
        app.router.add_get("/", handler)
        server = await aiohttp_server(app, access_log=None)  # its access log shows the token
        monkeypatch.setattr(api_module, "WS_URL", str(server.make_url("/")))

    return start


@pytest.fixture
def backoff(monkeypatch):
    """Record reconnect delays instead of sleeping; park the loop after MAX_SLEEPS."""
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)
        if len(delays) >= MAX_SLEEPS:
            await asyncio.Event().wait()  # until the test cancels the task

    monkeypatch.setattr(api_module, "_sleep", fake_sleep)
    return delays


async def test_listen_subscribes_pushes_reconnects_and_cancels(
    hass: HomeAssistant, ws_server, backoff
) -> None:
    seen = []  # (token, subscribe messages) per connection
    closed = asyncio.Event()

    async def handler(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        seen.append((request.query["token"], [await ws.receive_json() for _ in DEVICE_IDS]))
        if len(seen) == 1:
            body = {"deviceId": DEVICE_ID, "deviceType": "connected", "message": "OK"}
            await ws.send_json({"statusCode": 200, "action": "subsDevice", "body": json.dumps(body)})
            await ws.send_str("not json")
            await ws.send_json(
                {"action": "command", "deviceId": DEVICE_ID, "componentId": "13", "reportedValue": 1, "ts": 1700000000}
            )
            await ws.close()  # dropped: the client must reconnect
        else:
            body = {"deviceId": "TEST000002", "componentId": 15, "reportedValue": 280}
            await ws.send_json({"action": "command", "body": json.dumps(body)})
            await ws.receive()  # open until the client goes away
            closed.set()
        return ws

    await ws_server(handler)
    updates = []
    got_both = asyncio.Event()

    def on_update(*update):
        updates.append(update)
        if len(updates) == 2:
            got_both.set()

    api = FluidraApi(FakeAuth(), async_get_clientsession(hass))
    task = hass.async_create_background_task(api.async_listen(DEVICE_IDS, on_update), "ws")
    await asyncio.wait_for(got_both.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(closed.wait(), 5)  # cancel closed the socket

    assert seen == [("test-ws-token-1", SUBSCRIBE), ("test-ws-token-2", SUBSCRIBE)]
    assert updates[0] == (DEVICE_ID, 13, 1, 1700000000)
    assert updates[1][:3] == ("TEST000002", 15, 280)
    assert abs(updates[1][3] - time.time()) < 60  # no ts in the message: now
    assert backoff == [5]


@pytest.mark.parametrize(
    ("accept", "stable_after", "expected"),
    [
        (False, 60, [5, 10, 20, 40, 80, 160, 300, 300]),  # handshake rejected: double, cap
        (True, 0, [5] * MAX_SLEEPS),  # every connection counts as stable: reset
    ],
    ids=["rejected", "stable"],
)
async def test_reconnect_backoff_and_no_token_in_logs(
    hass: HomeAssistant, ws_server, backoff, monkeypatch, caplog, accept, stable_after, expected
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(api_module, "STABLE_AFTER", stable_after)

    async def handler(request):
        if not accept:
            return web.Response(status=403)
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.receive_json()
        await ws.close()
        return ws

    await ws_server(handler)
    api = FluidraApi(FakeAuth(), async_get_clientsession(hass))
    task = hass.async_create_background_task(api.async_listen([DEVICE_ID], lambda *u: None), "ws")
    async with asyncio.timeout(5):
        while len(backoff) < MAX_SLEEPS:
            await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert backoff == expected
    assert ("WebSocket failed: WSServerHandshakeError" in caplog.text) is not accept
    assert "test-ws-token" not in caplog.text
