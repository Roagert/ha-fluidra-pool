"""Shared fixtures for Fluidra Pool tests. Fake ids and credentials only."""
import json
from pathlib import Path

import pytest
from aioresponses import aioresponses

from custom_components.fluidra_pool.auth import COGNITO_URL
from custom_components.fluidra_pool.const import (
    API_CONSUMER_URL,
    API_DEVICES_URL,
    API_ENDPOINT_DEVICE_COMPONENTS,
    API_ENDPOINT_DEVICE_UICONFIG,
    API_ENDPOINT_USER_POOLS,
    API_ENDPOINT_USER_PROFILE,
)

DEVICE_ID = "TEST000001"
FIXTURES = Path(__file__).parent / "fixtures"

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
def mock_api():
    """Canned Cognito login + Fluidra REST responses for one heat pump (DEVICE_ID)."""
    with aioresponses() as mock:
        mock.post(
            COGNITO_URL,
            payload={
                "AuthenticationResult": {
                    "AccessToken": "test-access-token",
                    "ExpiresIn": 3600,
                    "RefreshToken": "test-refresh-token",
                }
            },
            repeat=True,
        )
        mock.get(API_DEVICES_URL, payload=DEVICES, repeat=True)
        mock.get(
            API_ENDPOINT_DEVICE_COMPONENTS.format(device_id=DEVICE_ID),
            payload=load_fixture("components_amt.json"),
            repeat=True,
        )
        mock.get(
            API_ENDPOINT_DEVICE_UICONFIG.format(device_id=DEVICE_ID),
            payload={},
            repeat=True,
        )
        # Legacy endpoints the current coordinator still polls (dropped in T07).
        # Non-empty payloads avoid its retry-with-sleep on empty data.
        mock.get(API_CONSUMER_URL, payload={"id": "test-consumer"}, repeat=True)
        mock.get(API_ENDPOINT_USER_PROFILE, payload={"id": "test-user"}, repeat=True)
        mock.get(API_ENDPOINT_USER_POOLS, payload=[{"poolId": "test-pool"}], repeat=True)
        yield mock
