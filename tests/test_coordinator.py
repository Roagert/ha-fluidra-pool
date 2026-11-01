"""Coordinator + setup tests: boot failures, poll failures, pushes, all devices, commands."""
from datetime import timedelta
from unittest.mock import patch

from aioresponses import aioresponses
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from yarl import URL

from custom_components.fluidra_pool.api import FluidraApi
from custom_components.fluidra_pool.auth import COGNITO_URL, FluidraConnectionError
from custom_components.fluidra_pool.const import (
    API_ENDPOINT_DEVICE_UICONFIG,
    API_ENDPOINT_SET_COMPONENT_VALUE,
    DOMAIN,
)

from .conftest import COGNITO_OK, DEVICE_ID, DEVICES, DEVICES_URL

OTHER_ID = "TEST000002"
TS = 1758877765  # the fixture components' ts
COMPAT_ENTITIES = (
    ("climate", "climate_heatpump"),
    ("sensor", "water_temperature"),
    ("sensor", "error_information"),
)


def entity_id(hass: HomeAssistant, platform: str, suffix: str) -> str:
    unique_id = f"fluidra_{DEVICE_ID}_{suffix}"
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)


@pytest.mark.parametrize("cognito_up", [False, True], ids=["all-unreachable", "rest-500"])
async def test_cloud_down_at_boot_retries(hass: HomeAssistant, config_entry, cognito_up) -> None:
    with aioresponses() as mock:  # an unmocked request fails to connect
        if cognito_up:
            mock.post(COGNITO_URL, payload=COGNITO_OK)
            mock.get(DEVICES_URL, status=500)
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_bad_credentials_start_reauth(hass: HomeAssistant, config_entry) -> None:
    with aioresponses() as mock:
        mock.post(COGNITO_URL, status=400, payload={"__type": "NotAuthorizedException"})
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [(flow["context"]["source"], flow["step_id"]) for flow in flows] == [
        (SOURCE_REAUTH, "reauth_confirm")
    ]
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id


async def test_poll_failure_makes_entities_unavailable(
    hass: HomeAssistant, config_entry, mock_api, mock_ws
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    coordinator = config_entry.runtime_data
    entity_ids = [entity_id(hass, *entity) for entity in COMPAT_ENTITIES]

    with patch.object(FluidraApi, "async_get_components", side_effect=FluidraConnectionError):
        await coordinator.async_refresh()
    assert [hass.states.get(e).state for e in entity_ids] == [STATE_UNAVAILABLE] * 3

    await coordinator.async_refresh()
    assert STATE_UNAVAILABLE not in [hass.states.get(e).state for e in entity_ids]


async def test_push_applied_unless_older(
    hass: HomeAssistant, config_entry, mock_api, mock_ws
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    water = entity_id(hass, "sensor", "water_temperature")
    assert hass.states.get(water).state == "26.5"

    mock_ws.push(deviceId=DEVICE_ID, componentId="19", reportedValue=270, ts=TS - 1)
    await hass.async_block_till_done()
    assert hass.states.get(water).state == "26.5"  # older than the polled value: ignored

    mock_ws.push(deviceId=DEVICE_ID, componentId="19", reportedValue=270, ts=TS + 1)
    await hass.async_block_till_done()
    assert hass.states.get(water).state == "27.0"

    await config_entry.runtime_data.async_refresh()  # the poll's value (ts=TS) is older
    assert hass.states.get(water).state == "27.0"


TWO_DEVICES = [*DEVICES, {**DEVICES[0], "id": OTHER_ID, "sn": OTHER_ID}]


@pytest.mark.parametrize("cloud_devices", [TWO_DEVICES])
async def test_all_devices_polled_and_subscribed(
    hass: HomeAssistant, config_entry, mock_api, mock_ws
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()

    assert list(coordinator.data) == [DEVICE_ID, OTHER_ID]
    assert coordinator.data[OTHER_ID]["info"]["id"] == OTHER_ID
    assert coordinator.data[OTHER_ID]["components"][15]["reportedValue"] == 280
    assert coordinator.uiconfig == {DEVICE_ID: {}, OTHER_ID: None}  # a 500 uiconfig is tolerated
    for device_id in (DEVICE_ID, OTHER_ID):  # fetched once, not every poll
        url = URL(API_ENDPOINT_DEVICE_UICONFIG.format(device_id=device_id))
        assert len(mock_api.requests[("GET", url)]) == 1
    assert mock_ws.subscribed == [DEVICE_ID, OTHER_ID]


async def test_set_component(hass: HomeAssistant, config_entry, mock_api, mock_ws) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    coordinator = config_entry.runtime_data
    set_url = API_ENDPOINT_SET_COMPONENT_VALUE.format(device_id=DEVICE_ID, component_id=15)
    mock_api.put(set_url, payload={})
    polls = mock_api.requests[("GET", URL(DEVICES_URL))]
    polls_before = len(polls)

    await coordinator.async_set_component(DEVICE_ID, 15, 300)
    (put,) = mock_api.requests[("PUT", URL(set_url))]
    assert put.kwargs["json"] == {"desiredValue": 300}
    assert coordinator.data[DEVICE_ID]["components"][15]["reportedValue"] == 300  # optimistic
    assert len(polls) == polls_before  # the device gets a moment to apply it

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    assert len(polls) == polls_before + 1  # re-read shortly after the command
    assert coordinator.data[DEVICE_ID]["components"][15]["reportedValue"] == 280  # what it reports

    mock_api.put(set_url, status=500)
    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_component(DEVICE_ID, 15, 310)


@pytest.mark.parametrize("cloud_devices", [TWO_DEVICES])
async def test_one_failing_device_does_not_take_down_the_others(
    hass: HomeAssistant, config_entry, mock_api, mock_ws
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    coordinator = config_entry.runtime_data
    real = FluidraApi.async_get_components

    async def other_fails(self, device_id):
        if device_id == OTHER_ID:
            raise FluidraConnectionError
        return await real(self, device_id)

    with patch.object(FluidraApi, "async_get_components", other_fails):
        await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert list(coordinator.data) == [DEVICE_ID]  # the failing device's entities go unavailable
    assert hass.states.get(entity_id(hass, "sensor", "water_temperature")).state == "26.5"
