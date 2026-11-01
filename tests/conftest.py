"""Shared fixtures for Fluidra Pool tests. Fake ids and credentials only."""
import asyncio
import json
from pathlib import Path
from unittest.mock import PropertyMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fluidra_pool.auth import COGNITO_URL
from custom_components.fluidra_pool.const import (
    API_DEVICES_URL,
    API_ENDPOINT_DEVICE_COMPONENTS,
    API_ENDPOINT_DEVICE_UICONFIG,
    DOMAIN,
)

DEVICE_ID = "TEST000001"
FIXTURES = Path(__file__).parent / "fixtures"
DEVICES_URL = f"{API_DEVICES_URL}?deviceType=connected"
COGNITO_OK = {
    "AuthenticationResult": {
        "AccessToken": "test-access-token",
        "ExpiresIn": 3600,
        "RefreshToken": "test-refresh-token",
    }
}

DEVICES = [
    {
        "id": DEVICE_ID,
        "sn": DEVICE_ID,
        "type": "amt",
        "vr": "2.5.0",
        "info": {"name": "Test Heat Pump"},
        "connectivity": {"connected": True},
    }
]


def load_fixture(name: str):
    """Return parsed JSON from tests/fixtures/<name>."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let HA load custom_components/ in every test."""
    yield


@pytest.fixture
def entity_registry_enabled_by_default():
    """Create disabled-by-default entities enabled (as HA core's fixture of this name does)."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        new_callable=PropertyMock,
        return_value=True,
    ):
        yield


@pytest.fixture
def config_entry(hass) -> MockConfigEntry:
    """A config entry for the fake account, added to hass but not set up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="fluidra_pool_test-user",
        data={"username": "test-user", "password": "test-password"},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def cloud_devices() -> list[dict]:
    """The fake account's devices (parametrize to change)."""
    return DEVICES


@pytest.fixture
def mock_api(cloud_devices):
    """Canned Cognito login + Fluidra REST. Each device reports the components of fixture
    components_<type>.json; only DEVICE_ID has a uiconfig, the others answer 500 (as some
    real ones do)."""
    with aioresponses() as mock:
        mock.post(COGNITO_URL, payload=COGNITO_OK, repeat=True)
        mock.get(DEVICES_URL, payload=cloud_devices, repeat=True)
        for device in cloud_devices:
            device_id = device["id"]
            mock.get(
                API_ENDPOINT_DEVICE_COMPONENTS.format(device_id=device_id),
                payload=load_fixture(f"components_{device['type']}.json"),
                repeat=True,
            )
            uiconfig = {"payload": {}} if device_id == DEVICE_ID else {"status": 500}
            mock.get(
                API_ENDPOINT_DEVICE_UICONFIG.format(device_id=device_id), repeat=True, **uiconfig
            )
        yield mock


class FakeWebSocket:
    """Stands in for ClientSession.ws_connect: one open socket that yields what tests push."""

    def __init__(self) -> None:
        self.subscribed: list[str] = []
        self.closed = False
        self._inbox: asyncio.Queue[aiohttp.WSMessage] = asyncio.Queue()

    def __call__(self, *args, **kwargs) -> "FakeWebSocket":
        return self

    async def __aenter__(self) -> "FakeWebSocket":
        return self

    async def __aexit__(self, *exc_info) -> None:
        self.closed = True

    async def send_json(self, message: dict) -> None:
        self.subscribed.append(message["deviceId"])

    def __aiter__(self) -> "FakeWebSocket":
        return self

    async def __anext__(self) -> aiohttp.WSMessage:
        return await self._inbox.get()  # waits until a test pushes: the listener stays pending

    def push(self, **event) -> None:
        """Deliver a server message to the listener."""
        self._inbox.put_nowait(aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, json.dumps(event), None))


@pytest.fixture
def mock_ws():
    """Route the real WebSocket listener to a FakeWebSocket."""
    ws = FakeWebSocket()
    with patch.object(aiohttp.ClientSession, "ws_connect", ws):
        yield ws
