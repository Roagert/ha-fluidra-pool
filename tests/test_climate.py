"""Climate tests: state from components 11/13/14/15/19, the PUTs each service sends."""
from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as CLIMATE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from yarl import URL

from custom_components.fluidra_pool.api import FluidraApi
from custom_components.fluidra_pool.const import API_ENDPOINT_SET_COMPONENT_VALUE, DOMAIN

from .conftest import DEVICE_ID, DEVICES

ENTITY = "climate.test_heat_pump_pool_heat_pump"  # entity_id of the pre-rewrite entity
OTHER_ID, SENSOR_ID = "TEST000002", "TEST000003"
HEAT, COOL, AUTO, OFF = HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF


def put_url(component_id: int) -> str:
    return API_ENDPOINT_SET_COMPONENT_VALUE.format(device_id=DEVICE_ID, component_id=component_id)


@pytest.fixture
async def climate(hass: HomeAssistant, config_entry, mock_api, mock_ws):
    """Set up the fixture heat pump (on, mode 0, setpoint 28.0, water 26.5, comp 11 = 1)."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry.runtime_data


@pytest.fixture
def puts(mock_api) -> list[tuple[int, int]]:
    """Accept PUTs to components 13/14/15; record (component, desiredValue) in send order."""
    sent: list[tuple[int, int]] = []
    for cid in (13, 14, 15):
        mock_api.put(
            put_url(cid),
            payload={},
            repeat=True,
            callback=lambda url, cid=cid, **kw: sent.append((cid, kw["json"]["desiredValue"])),
        )
    return sent


def set_components(coordinator, **values) -> None:
    """Make the heat pump report c<id>=value (None removes the component)."""
    components = coordinator.data[DEVICE_ID]["components"]
    for key, value in values.items():
        cid = int(key[1:])
        if value is None:
            components.pop(cid)
        else:
            components[cid] = {"id": cid, "reportedValue": value, "ts": 0}
    coordinator.async_set_updated_data(coordinator.data)


async def call(hass: HomeAssistant, service: str, **data) -> None:
    await hass.services.async_call(
        CLIMATE, service, {ATTR_ENTITY_ID: ENTITY, **data}, blocking=True
    )


MODES = {0: (HEAT, "smart"), 1: (COOL, "smart"), 2: (AUTO, "smart"), 3: (HEAT, "boost"),
         4: (HEAT, "silence"), 5: (COOL, "boost"), 6: (COOL, "silence")}


@pytest.mark.parametrize("power", [0, 1])
@pytest.mark.parametrize("mode", list(MODES))
async def test_state_from_power_and_mode(hass: HomeAssistant, climate, power, mode) -> None:
    set_components(climate, c13=power, c14=mode)
    state = hass.states.get(ENTITY)
    family, preset = MODES[mode]
    assert state.state == (family if power else OFF)
    assert state.attributes[ATTR_PRESET_MODE] == preset  # the device keeps its mode while off
    presets = ["smart"] if family == AUTO else ["smart", "boost", "silence"]
    assert state.attributes[ATTR_PRESET_MODES] == presets


async def test_unavailable_when_device_gone(hass: HomeAssistant, climate) -> None:
    climate.async_set_updated_data({})  # a later poll no longer lists the device
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE


async def test_temperatures(hass: HomeAssistant, climate) -> None:
    attributes = hass.states.get(ENTITY).attributes
    assert (attributes["current_temperature"], attributes[ATTR_TEMPERATURE]) == (26.5, 28.0)
    assert (attributes["min_temp"], attributes["max_temp"]) == (15.0, 40.0)
    assert attributes["target_temp_step"] == 0.5


@pytest.mark.parametrize(
    ("hvac_mode", "expected"),
    [(OFF, [(13, 0)]), (HEAT, [(14, 0), (13, 1)]), (COOL, [(14, 1), (13, 1)]),
     (AUTO, [(14, 2), (13, 1)])],
)
async def test_set_hvac_mode(hass: HomeAssistant, climate, puts, hvac_mode, expected) -> None:
    set_components(climate, c13=0, c14=5)  # off, boost cooling
    await call(hass, SERVICE_SET_HVAC_MODE, **{ATTR_HVAC_MODE: hvac_mode})
    assert puts == expected
    assert hass.states.get(ENTITY).state == hvac_mode  # optimistic until the re-read


@pytest.mark.parametrize(("service", "expected"), [(SERVICE_TURN_ON, 1), (SERVICE_TURN_OFF, 0)])
async def test_turn_on_off(hass: HomeAssistant, climate, puts, service, expected) -> None:
    await call(hass, service)
    assert puts == [(13, expected)]  # power only: the mode is kept


@pytest.mark.parametrize(
    ("mode", "preset", "expected"),
    [(0, "boost", 3), (0, "silence", 4), (3, "smart", 0), (1, "boost", 5), (6, "boost", 5),
     (1, "silence", 6), (5, "smart", 1), (2, "smart", 2)],
)
async def test_set_preset(hass: HomeAssistant, climate, puts, mode, preset, expected) -> None:
    set_components(climate, c14=mode)
    await call(hass, SERVICE_SET_PRESET_MODE, **{ATTR_PRESET_MODE: preset})
    assert puts == [(14, expected)]  # within the current heat/cool family


async def test_auto_has_no_boost(hass: HomeAssistant, climate, puts) -> None:
    set_components(climate, c14=2)
    with pytest.raises(ServiceValidationError):
        await call(hass, SERVICE_SET_PRESET_MODE, **{ATTR_PRESET_MODE: "boost"})
    assert puts == []


async def test_set_temperature(hass: HomeAssistant, climate, puts) -> None:
    await call(hass, SERVICE_SET_TEMPERATURE, **{ATTR_TEMPERATURE: 26.5})
    assert puts == [(15, 265)]


async def test_failed_put_raises_and_stops(hass: HomeAssistant, climate, mock_api) -> None:
    mock_api.put(put_url(14), status=500)
    with pytest.raises(HomeAssistantError):
        await call(hass, SERVICE_SET_HVAC_MODE, **{ATTR_HVAC_MODE: COOL})
    assert ("PUT", URL(put_url(14))) in mock_api.requests
    assert ("PUT", URL(put_url(13))) not in mock_api.requests  # no power-on after a failed mode


@pytest.mark.parametrize(
    ("components", "expected"),
    [
        ({"c13": 0}, HVACAction.OFF),
        ({"c11": None}, None),  # component 11 absent: unknown
        ({"c11": 0}, HVACAction.IDLE),
        ({"c14": 0}, HVACAction.HEATING),
        ({"c14": 4}, HVACAction.HEATING),
        ({"c14": 1}, HVACAction.COOLING),
        ({"c14": 6}, HVACAction.COOLING),
        ({"c14": 2, "c19": 265}, HVACAction.HEATING),  # auto, water below the setpoint 28.0
        ({"c14": 2, "c19": 300}, HVACAction.COOLING),  # auto, water above it
        ({"c14": 2, "c19": None}, None),  # auto without a water temperature: unknown, no crash
    ],
)
async def test_hvac_action(hass: HomeAssistant, climate, components, expected) -> None:
    set_components(climate, **components)
    assert hass.states.get(ENTITY).attributes.get(ATTR_HVAC_ACTION) == expected


THREE_DEVICES = [*DEVICES, *({**DEVICES[0], "id": i, "sn": i} for i in (OTHER_ID, SENSOR_ID))]


@pytest.mark.parametrize("cloud_devices", [THREE_DEVICES])
async def test_one_entity_per_heat_pump(
    hass: HomeAssistant, config_entry, mock_api, mock_ws, monkeypatch
) -> None:
    real = FluidraApi.async_get_components

    async def components(self, device_id):  # SENSOR_ID lacks the heat-pump controls
        found = await real(self, device_id)
        return {k: v for k, v in found.items() if device_id != SENSOR_ID or k not in (13, 14)}

    monkeypatch.setattr(FluidraApi, "async_get_components", components)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    climates = {e.unique_id: e for e in entities if e.domain == CLIMATE}
    assert set(climates) == {f"fluidra_{i}_climate_heatpump" for i in (DEVICE_ID, OTHER_ID)}
    entry = climates[f"fluidra_{DEVICE_ID}_climate_heatpump"]
    assert entry.entity_id == ENTITY
    device = dr.async_get(hass).async_get(entry.device_id)
    assert device.identifiers == {(DOMAIN, DEVICE_ID)}
    assert hass.states.get("climate.test_heat_pump_pool_heat_pump_2").state == HEAT
