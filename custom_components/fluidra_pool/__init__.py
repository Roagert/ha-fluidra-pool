"""The Fluidra Pool integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FluidraApi
from .auth import FluidraAuth
from .const import CONF_PASSWORD, CONF_REFRESH_TOKEN, CONF_USERNAME, DOMAIN
from .coordinator import FluidraPoolDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Read all devices of the account, then listen for their pushes in the background."""
    session = async_get_clientsession(hass)
    auth = FluidraAuth(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_REFRESH_TOKEN),  # absent in entries migrated from version 1
    )
    coordinator = FluidraPoolDataUpdateCoordinator(hass, entry, FluidraApi(auth, session))
    await coordinator.async_config_entry_first_refresh()  # cloud errors: retry or reauth
    entry.runtime_data = coordinator

    @callback
    def async_store_refresh_token() -> None:
        """Keep the newest refresh token (after a password login, or when Cognito rotates it)."""
        if auth.refresh_token and auth.refresh_token != entry.data.get(CONF_REFRESH_TOKEN):
            # No update listener is registered, so this does not reload the entry.
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_REFRESH_TOKEN: auth.refresh_token}
            )

    async_store_refresh_token()
    entry.async_on_unload(coordinator.async_add_listener(async_store_refresh_token))

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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Version 1 also stored a device, a component and polling options: keep the login only."""
    if entry.version == 1:
        data = {key: entry.data[key] for key in (CONF_USERNAME, CONF_PASSWORD)}
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the platforms; the coordinator and the WebSocket task stop with the entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)  # compat shim; delete in T10/T11
    return unload_ok
