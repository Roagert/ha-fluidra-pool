"""The Fluidra Pool integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FluidraApi
from .auth import FluidraAuth
from .const import CONF_PASSWORD, CONF_REFRESH_TOKEN, CONF_USERNAME
from .coordinator import FluidraPoolDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR
]


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
    """Version 1 also stored a device, a component and polling options: keep the login only.

    Its title held the e-mail, which Home Assistant logs; a title the user chose is kept.
    """
    if entry.version == 1:
        data = {key: entry.data[key] for key in (CONF_USERNAME, CONF_PASSWORD)}
        title = entry.title
        if title == f"Fluidra Pool ({data[CONF_USERNAME]})":
            title = "Fluidra Pool"
        hass.config_entries.async_update_entry(entry, data=data, title=title, version=2)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the platforms; the coordinator and the WebSocket task stop with the entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
