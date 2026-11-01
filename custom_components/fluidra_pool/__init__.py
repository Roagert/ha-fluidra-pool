"""The Fluidra Pool integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FluidraApi
from .auth import FluidraAuth
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .coordinator import FluidraPoolDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Read all devices of the account, then listen for their pushes in the background."""
    session = async_get_clientsession(hass)
    auth = FluidraAuth(session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = FluidraPoolDataUpdateCoordinator(hass, entry, FluidraApi(auth, session))
    await coordinator.async_config_entry_first_refresh()  # cloud errors: retry or reauth
    entry.runtime_data = coordinator

    # --- compat shim for pre-T10/T11 entities; delete in T10/T11 ---
    if coordinator.device_id is None:
        _LOGGER.error("No devices found on this Fluidra account")
        return False
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "device_id": coordinator.device_id,
    }
    # --- end compat shim ---

    # A background task does not hold up HA startup (issue #9); unloading cancels it.
    # It subscribes the devices found now: entities exist for those only, until a reload.
    entry.async_create_background_task(
        hass,
        coordinator.api.async_listen(list(coordinator.data), coordinator.async_handle_push),
        "fluidra_pool_ws",
    )

    async def handle_dump_api_data(call: ServiceCall) -> None:
        """Log the latest data (T09 replaces this with a redacted diagnostics download)."""
        dump = {"devices": coordinator.data, "uiconfig": coordinator.uiconfig}
        _LOGGER.info("[Fluidra Diagnostic] Dumping latest API data: %s", dump)

    hass.services.async_register(DOMAIN, "dump_api_data", handle_dump_api_data)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the platforms; the coordinator and the WebSocket task stop with the entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)  # compat shim; delete in T10/T11
    return unload_ok
