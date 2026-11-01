"""Smoke test: a config entry sets up and unloads with all network mocked."""
import asyncio

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.fluidra_pool.const import DOMAIN

from .conftest import DEVICE_ID


def ws_tasks() -> list[asyncio.Task]:
    return [task for task in asyncio.all_tasks() if task.get_name() == "fluidra_pool_ws"]


async def test_setup_and_unload(hass: HomeAssistant, config_entry, mock_api, mock_ws) -> None:
    """Real async_setup_entry/async_unload_entry against canned REST data and a fake socket."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    # Issue #9: the WebSocket listener never returns. Started with hass.async_create_task it
    # would make this wait forever (HA startup blocked); as a background task it must not.
    async with asyncio.timeout(5):
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert mock_ws.subscribed == [DEVICE_ID]  # the real listener is connected and waiting
    assert len(ws_tasks()) == 1
    # Compatibility invariant: these unique IDs must survive every rewrite.
    registry = er.async_get(hass)
    for platform, suffix in (
        ("climate", "climate_heatpump"),
        ("sensor", "water_temperature"),
        ("sensor", "error_information"),
    ):
        unique_id = f"fluidra_{DEVICE_ID}_{suffix}"
        assert registry.async_get_entity_id(platform, DOMAIN, unique_id), unique_id
    assert not hass.services.has_service(DOMAIN, "dump_api_data")  # replaced by diagnostics

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_ws.closed and not ws_tasks()  # unload cancelled the listener
