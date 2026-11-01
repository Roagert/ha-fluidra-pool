"""Diagnostics download: component values stay, every secret in the fixture is gone."""
import json
import re
from unittest.mock import patch

from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.fluidra_pool.api import FluidraApi
from custom_components.fluidra_pool.auth import (
    COGNITO_URL,
    FluidraAuthError,
    FluidraConnectionError,
)
from custom_components.fluidra_pool.const import (
    API_ENDPOINT_DEVICE_COMPONENTS,
    API_ENDPOINT_DEVICE_UICONFIG,
    DOMAIN,
)
from custom_components.fluidra_pool.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)

from .conftest import COGNITO_OK, DEVICE_ID, DEVICES, DEVICES_URL, load_fixture

HA_HTTP = "http://127.0.0.1"  # the test client calling HA's diagnostics view


async def test_diagnostics_redacts_secrets(hass: HomeAssistant, hass_client, mock_ws) -> None:
    """The cloud returns fake secrets in every redacted field; none reach the download."""
    fake = load_fixture("diagnostics_secrets.json")
    fake_json = json.dumps(fake)
    assert TO_REDACT <= set(re.findall(r'"(\w+)": "secret-', fake_json))  # each key has a secret
    components = [c for c in load_fixture("components_amt.json") if c["id"] != 2]
    components.append(fake["lan_ip_component"])
    # Cognito hands back the same refresh token, so the entry keeps the fake one.
    tokens = {**COGNITO_OK["AuthenticationResult"], "RefreshToken": fake["entry"]["refresh_token"]}
    login = {"AuthenticationResult": tokens}
    entry = MockConfigEntry(domain=DOMAIN, version=2, unique_id="fluidra_pool_x", data=fake["entry"])
    entry.add_to_hass(hass)
    with aioresponses(passthrough=[HA_HTTP]) as cloud:
        cloud.post(COGNITO_URL, payload=login, repeat=True)
        cloud.get(DEVICES_URL, payload=[fake["device"]], repeat=True)
        cloud.get(API_ENDPOINT_DEVICE_COMPONENTS.format(device_id=DEVICE_ID), payload=components)
        cloud.get(API_ENDPOINT_DEVICE_UICONFIG.format(device_id=DEVICE_ID), payload=fake["uiconfig"])
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    secrets = set(re.findall(r"secret-[\w-]+", fake_json))
    coordinator = entry.runtime_data
    loaded = json.dumps([dict(entry.data), coordinator.data])
    assert [secret for secret in secrets if secret not in loaded] == []  # all reached HA
    dumped = json.dumps(diagnostics)
    assert [secret for secret in secrets if secret in dumped] == []
    device = diagnostics["devices"][DEVICE_ID]
    assert device["info"]["sn"] == DEVICE_ID
    assert device["components"]["2"]["reportedValue"] == "**REDACTED**"
    assert device["components"]["3"]["reportedValue"] == DEVICE_ID
    assert device["components"]["15"] == {
        "id": 15, "reportedValue": 280, "desiredValue": 280, "ts": 1758877765
    }
    assert device["uiconfig"]["groups"][0]["components"] == [13, 15]
    # UI labels are what reporters of other devices must send us (#3 #4 #5 #8): keep them.
    assert device["uiconfig"]["groups"][0]["name"] == "Water temperature"
    assert diagnostics["entry"]["password"] == "**REDACTED**"


OTHER_ID = "TEST000002"


@pytest.mark.parametrize("cloud_devices", [[*DEVICES, {**DEVICES[0], "id": OTHER_ID, "sn": OTHER_ID}]])
async def test_diagnostics_uiconfig_on_demand(
    hass: HomeAssistant, config_entry, mock_api, mock_ws
) -> None:
    """The UI config is read for the download only; a failing one is None, not an error."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert not [url for _, url in mock_api.requests if "uiconfig" in url.path]  # not polled
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert {d: v["uiconfig"] for d, v in diagnostics["devices"].items()} == {
        DEVICE_ID: {}, OTHER_ID: None  # OTHER_ID answers HTTP 500
    }

    for error in (FluidraConnectionError, FluidraAuthError):
        with patch.object(FluidraApi, "async_get_uiconfig", side_effect=error):
            diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
        assert diagnostics["devices"][DEVICE_ID]["uiconfig"] is None
