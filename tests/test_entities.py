"""Sensor, switch and binary sensor tests: values from components, commands, unique ids."""
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.fluidra_pool.api import FluidraApi
from custom_components.fluidra_pool.const import API_ENDPOINT_SET_COMPONENT_VALUE, DOMAIN

from .conftest import DEVICE_ID, DEVICES

OTHER_ID = "TEST000002"
WATER, AIR, TARGET, RSSI, ERROR, POWER, NO_FLOW = (
    "sensor.test_heat_pump_water_temperature",
    "sensor.test_heat_pump_air_temperature",
    "sensor.test_heat_pump_target_temperature",
    "sensor.test_heat_pump_wi_fi_signal",
    "sensor.test_heat_pump_error_information",
    "switch.test_heat_pump_power",
    "binary_sensor.test_heat_pump_no_flow",
)
ENTITIES = {  # entity_id: (unique id suffix, state from the fixture components)
    "climate.test_heat_pump_pool_heat_pump": ("climate_heatpump", "heat"),
    WATER: ("water_temperature", "26.5"),
    AIR: ("air_temperature", "18.2"),
    TARGET: ("target_temperature", "28.0"),
    RSSI: ("wifi_rssi", "-58"),
    ERROR: ("error_information", "ok"),
    POWER: ("power", STATE_ON),
    NO_FLOW: ("no_flow", STATE_OFF),
}


@pytest.fixture
async def coordinator(hass: HomeAssistant, config_entry, mock_api, mock_ws):
    """Set up the fixture heat pump."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry.runtime_data


def set_component(coordinator, component_id: int, value) -> None:
    """Make the heat pump report value for the component (None: stop reporting it)."""
    components = coordinator.data[DEVICE_ID]["components"]
    if value is None:
        components.pop(component_id)
    else:
        components[component_id] = {"id": component_id, "reportedValue": value, "ts": 0}
    coordinator.async_set_updated_data(coordinator.data)


def without_components(monkeypatch, device_id: str, *component_ids: int) -> None:
    """Make the cloud not report these components for the device."""
    real = FluidraApi.async_get_components

    async def components(self, polled_id):
        found = await real(self, polled_id)
        return {k: v for k, v in found.items() if polled_id != device_id or k not in component_ids}

    monkeypatch.setattr(FluidraApi, "async_get_components", components)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities_and_values(hass: HomeAssistant, config_entry, coordinator) -> None:
    """Exactly these entities, with these unique ids and values (no button, no '* Data')."""
    entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    assert {entry.entity_id: entry.unique_id for entry in entries} == {
        entity_id: f"fluidra_{DEVICE_ID}_{suffix}" for entity_id, (suffix, _) in ENTITIES.items()
    }
    assert {entity_id: hass.states.get(entity_id).state for entity_id in ENTITIES} == {
        entity_id: state for entity_id, (_, state) in ENTITIES.items()
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "component_id", "value", "state"),
    [(WATER, 19, 270, "27.0"), (AIR, 62, -35, "-3.5"), (TARGET, 15, 300, "30.0"),
     (RSSI, 1, -70, "-70"), (POWER, 13, 0, STATE_OFF), (NO_FLOW, 28, 1, STATE_ON),
     # implausible °C (#4 showed 404.2 °C): unavailable; -30...80 °C is shown
     (WATER, 19, 4042, STATE_UNAVAILABLE), (WATER, 19, 801, STATE_UNAVAILABLE),
     (WATER, 19, 800, "80.0"), (AIR, 62, -301, STATE_UNAVAILABLE), (AIR, 62, -300, "-30.0"),
     (TARGET, 15, 4042, STATE_UNAVAILABLE)],
)
async def test_value_follows_component(
    hass: HomeAssistant, coordinator, entity_id, component_id, value, state
) -> None:
    set_component(coordinator, component_id, value)
    assert hass.states.get(entity_id).state == state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "component_id"),
    [(WATER, 19), (AIR, 62), (TARGET, 15), (RSSI, 1), (POWER, 13), (NO_FLOW, 28)],
)
async def test_unavailable_without_component(
    hass: HomeAssistant, coordinator, entity_id, component_id
) -> None:
    set_component(coordinator, component_id, None)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_error_information_shows_alarms(hass: HomeAssistant, coordinator) -> None:
    alarm = {"type": "error", "errorCode": "E03"}  # the alarm format is unverified
    coordinator.data[DEVICE_ID]["info"]["alarms"] = [alarm]
    coordinator.async_set_updated_data(coordinator.data)
    state = hass.states.get(ERROR)
    assert (state.state, state.attributes["alarms"]) == ("alarm", [alarm])


async def test_wifi_rssi_is_disabled_diagnostic(hass: HomeAssistant, coordinator) -> None:
    entry = er.async_get(hass).async_get(RSSI)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


def put_url(component_id: int) -> str:
    return API_ENDPOINT_SET_COMPONENT_VALUE.format(device_id=DEVICE_ID, component_id=component_id)


@pytest.mark.parametrize(
    ("before", "service", "value"), [(1, SERVICE_TURN_OFF, 0), (0, SERVICE_TURN_ON, 1)]
)
async def test_power_switch(
    hass: HomeAssistant, coordinator, mock_api, before, service, value
) -> None:
    sent = []
    mock_api.put(put_url(13), payload={}, callback=lambda url, **kw: sent.append(kw["json"]))
    set_component(coordinator, 13, before)
    await hass.services.async_call(SWITCH, service, {ATTR_ENTITY_ID: POWER}, blocking=True)
    assert sent == [{"desiredValue": value}]
    assert hass.states.get(POWER).state == (STATE_ON if value else STATE_OFF)  # optimistic


async def test_power_switch_failure_raises(hass: HomeAssistant, coordinator, mock_api) -> None:
    mock_api.put(put_url(13), status=500)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: POWER}, blocking=True
        )
    assert hass.states.get(POWER).state == STATE_ON


async def test_device_info(hass: HomeAssistant, coordinator) -> None:
    device = dr.async_get(hass).async_get_device({(DOMAIN, DEVICE_ID)})
    assert (device.manufacturer, device.name, device.model, device.model_id) == (
        "Fluidra", "Test Heat Pump", "amt", "1441"
    )
    assert (device.sw_version, device.serial_number) == ("2.5.0", DEVICE_ID)


async def test_existing_entity_ids_kept(
    hass: HomeAssistant, config_entry, mock_api, mock_ws
) -> None:
    """The registry entries of the pre-1.0 sensors are reused, with their (renamed) ids."""
    registry = er.async_get(hass)
    for suffix in ("water_temperature", "error_information"):
        registry.async_get_or_create(
            "sensor", DOMAIN, f"fluidra_{DEVICE_ID}_{suffix}",
            suggested_object_id=f"old_{suffix}", config_entry=config_entry,
        )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.old_water_temperature").state == "26.5"
    assert hass.states.get("sensor.old_error_information").state == "ok"
    assert hass.states.get(WATER) is None and hass.states.get(ERROR) is None


async def test_no_flow_only_with_component_28(
    hass: HomeAssistant, config_entry, mock_api, mock_ws, monkeypatch
) -> None:
    without_components(monkeypatch, DEVICE_ID, 28)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(POWER).state == STATE_ON
    assert hass.states.get(NO_FLOW) is None


TWO_DEVICES = [*DEVICES, {**DEVICES[0], "id": OTHER_ID, "sn": OTHER_ID}]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("cloud_devices", [TWO_DEVICES])
async def test_other_device_gets_generic_sensors(
    hass: HomeAssistant, config_entry, mock_api, mock_ws, monkeypatch
) -> None:
    """Heat-pump entities need components 13/14/15/19; any other device gets the alarm sensor,
    a component count and a raw sensor per numeric component (more in test_other_devices)."""
    without_components(monkeypatch, OTHER_ID, 13, 14)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    numeric = (1, 11, 15, 19, 28, 62)  # 2, 3, 4 and 6 report strings
    suffixes = ["error_information", "component_count", *(f"component_{i}" for i in numeric)]
    assert [e.unique_id for e in entries if OTHER_ID in e.unique_id] == [
        f"fluidra_{OTHER_ID}_{suffix}" for suffix in suffixes
    ]
    assert len(entries) == len(ENTITIES) + len(suffixes)


@pytest.mark.parametrize("cloud_devices", [[]])
async def test_account_without_devices_loads(
    hass: HomeAssistant, config_entry, mock_api, mock_ws
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id) == []
    assert await hass.config_entries.async_unload(config_entry.entry_id)
