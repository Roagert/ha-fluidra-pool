"""Smoke test: a config entry sets up and unloads with all network mocked."""
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fluidra_pool.const import DOMAIN
from custom_components.fluidra_pool.coordinator import FluidraPoolDataUpdateCoordinator

from .conftest import DEVICE_ID


async def test_setup_and_unload(hass: HomeAssistant, mock_api) -> None:
    """Real async_setup_entry/async_unload_entry against canned REST data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="fluidra_pool_test-user",
        data={"username": "test-user", "password": "test-password"},
    )
    entry.add_to_hass(hass)

    # T07: the WS listener is started with hass.async_create_task and loops for
    # minutes, so async_block_till_done() would hang (issue #9). Remove this patch in T07.
    with patch.object(FluidraPoolDataUpdateCoordinator, "_start_websocket") as ws_start:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    ws_start.assert_called_once()
    # Compatibility invariant: these unique IDs must survive every rewrite.
    registry = er.async_get(hass)
    for platform, suffix in (
        ("climate", "climate_heatpump"),
        ("sensor", "water_temperature"),
        ("sensor", "error_information"),
    ):
        unique_id = f"fluidra_{DEVICE_ID}_{suffix}"
        assert registry.async_get_entity_id(platform, DOMAIN, unique_id), unique_id

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
