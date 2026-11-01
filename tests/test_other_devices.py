"""Devices we have no mapping for (#3 #4 #5 #8): no crash, no bogus values, generic sensors.

The fixtures are made up after the issue reports (#8: pH raw 254; #4: component 19 = 4042;
#5: no component 13), not captured: the real component ids of these devices are unknown.
"""
import logging

from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from .conftest import DEVICE_ID, DEVICES

OTHER_DEVICES = [  # fixture tests/fixtures/components_<type>.json
    {**DEVICES[0], "id": device_id, "sn": device_id, "type": kind, "info": {"name": f"Test {kind}"}}
    for device_id, kind in (
        ("TEST000002", "chlorinator"),
        ("TEST000003", "blueconnect"),
        ("TEST000004", "no13"),
        ("TEST000005", "empty"),
    )
]
UNAVAILABLE = STATE_UNAVAILABLE
STATES = {  # type: {unique id suffix: state}; no climate, no temperature, no str/bool/dict sensor
    "chlorinator": {
        "component_count": "12", "component_1": "-61", "component_19": "0",
        "component_172": UNAVAILABLE, "component_173": UNAVAILABLE,  # 254: "no data"
        "component_177": "650", "component_178": UNAVAILABLE, "component_179": UNAVAILABLE,
        "component_180": "7.2",
    },
    "blueconnect": {  # raw, unitless: not shown as 404.2 °C
        "component_count": "4", "component_1": "-70", "component_19": "4042", "component_20": "712"
    },
    "no13": {
        "component_count": "5", "component_1": "-58", "component_14": "0", "component_15": "280",
        "component_19": "265",
    },
    "empty": {"component_count": "0"},
}


def warnings(caplog) -> list[str]:
    """Warnings and errors, except HA's notice that a custom integration is loaded."""
    return [
        r.getMessage() for r in caplog.records
        if r.levelno >= logging.WARNING and "custom integration" not in r.getMessage()
    ]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("cloud_devices", [[*DEVICES, *OTHER_DEVICES]])
async def test_other_devices(
    hass: HomeAssistant, config_entry, mock_api, mock_ws, caplog
) -> None:
    """Setup succeeds next to a heat pump; no warning, no climate, generic sensors."""
    caplog.set_level(logging.DEBUG)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    assert [e.unique_id for e in entries if e.domain == CLIMATE] == [
        f"fluidra_{DEVICE_ID}_climate_heatpump"
    ]
    for device in OTHER_DEVICES:
        prefix = f"fluidra_{device['id']}_"
        states = {
            e.unique_id.removeprefix(prefix): hass.states.get(e.entity_id).state
            for e in entries if e.unique_id.startswith(prefix)
        }
        assert states == {"error_information": "ok", **STATES[device["type"]]}, device["type"]
    assert warnings(caplog) == []

    chlorinator = OTHER_DEVICES[0]["id"]
    coordinator.async_handle_push(chlorinator, 172, 72, 2e9)  # real data after "no data"
    coordinator.async_handle_push(chlorinator, 177, 65535, 2e9)
    assert hass.states.get("sensor.test_chlorinator_component_172").state == "72"
    assert hass.states.get("sensor.test_chlorinator_component_177").state == UNAVAILABLE


@pytest.mark.parametrize("cloud_devices", [OTHER_DEVICES[:1]])
async def test_component_count_enabled_generic_disabled(
    hass: HomeAssistant, config_entry, mock_api, mock_ws
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    count = registry.async_get("sensor.test_chlorinator_components")
    assert (count.disabled_by, count.entity_category) == (None, EntityCategory.DIAGNOSTIC)
    assert hass.states.get("sensor.test_chlorinator_components").state == "12"
    generic = registry.async_get("sensor.test_chlorinator_component_177")
    assert generic.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert generic.original_name == "Component 177"
    assert hass.states.get("sensor.test_chlorinator_component_177") is None
