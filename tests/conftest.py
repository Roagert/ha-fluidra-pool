"""Shared fixtures for Fluidra Pool tests. Fake ids and credentials only."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from custom_components.fluidra_pool.auth import FluidraAuth
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
def mock_auth():
    """Bypass Cognito: authenticate() just stores a fake token."""

    async def _authenticate(self):
        self.access_token = "test-access-token"
        self.token_expiry = datetime.now() + timedelta(hours=1)
        return True

    with patch.object(FluidraAuth, "authenticate", _authenticate):
        yield


@pytest.fixture
def mock_api(mock_auth):
    """Canned Fluidra REST responses for one heat pump (DEVICE_ID)."""
    with aioresponses() as mock:
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
