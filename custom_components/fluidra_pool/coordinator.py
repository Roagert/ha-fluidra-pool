"""Fluidra Pool coordinator: every device of the account, polled by REST, pushed by WebSocket."""
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FluidraApi
from .auth import FluidraAuthError, FluidraConnectionError
from .const import QUICK_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(minutes=5)  # the WebSocket keeps values fresh in between
HEAT_PUMP_COMPONENTS = {13, 14, 15, 19}  # power, mode, setpoint, water temperature

# {device_id: {"info": device dict from the cloud, "components": {component id: component dict}}}
type FluidraData = dict[str, dict[str, Any]]


class FluidraPoolDataUpdateCoordinator(DataUpdateCoordinator[FluidraData]):
    """Devices and component values of one Fluidra account."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: FluidraApi) -> None:
        """Poll every POLL_INTERVAL; a requested refresh waits for a command to apply."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Fluidra Pool",
            update_interval=POLL_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=QUICK_UPDATE_INTERVAL.total_seconds(), immediate=False
            ),
        )
        self.api = api
        self.uiconfig: dict[str, dict[str, Any] | None] = {}  # fetched once per device

    async def _async_update_data(self) -> FluidraData:
        """Read all devices and their components; keep pushed values newer than the poll."""
        old = self.data or {}
        data: FluidraData = {}
        failed: FluidraConnectionError | None = None
        try:
            for info in await self.api.async_get_devices():
                device_id = info["id"]
                if device_id not in self.uiconfig:
                    self.uiconfig[device_id] = await self.api.async_get_uiconfig(device_id)
                try:
                    components = await self.api.async_get_components(device_id)
                except FluidraConnectionError as err:  # one bad device must not hide the others
                    _LOGGER.debug("Reading device %s failed: %s", device_id, err)
                    failed = err
                    continue
                stored = old.get(device_id, {}).get("components", {})
                for component_id, component in components.items():
                    if stored.get(component_id, {}).get("ts", 0) > component.get("ts", 0):
                        components[component_id] = stored[component_id]
                data[device_id] = {"info": info, "components": components}
        except FluidraAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FluidraConnectionError as err:
            raise UpdateFailed(str(err)) from err
        if failed and not data:
            raise UpdateFailed(str(failed)) from failed
        return data

    @callback
    def async_handle_push(self, device_id: str, component_id: int, value: Any, ts: float) -> None:
        """Apply a WebSocket update unless it is older than the value we have."""
        if (device := self.data.get(device_id)) is None:
            return
        stored = device["components"].get(component_id, {})
        if ts < stored.get("ts", 0):
            _LOGGER.debug("Ignored an outdated push for %s component %s", device_id, component_id)
            return
        device["components"][component_id] = {
            **stored, "id": component_id, "reportedValue": value, "ts": ts
        }
        self.async_set_updated_data(self.data)

    async def async_set_component(self, device_id: str, component_id: int, value: Any) -> None:
        """Send a command, show the new value at once, re-read the device shortly after."""
        try:
            await self.api.async_set_component(device_id, component_id, value)
        except (FluidraAuthError, FluidraConnectionError) as err:
            raise HomeAssistantError(f"Setting component {component_id} failed: {err}") from err
        components = self.data[device_id]["components"]
        # Keep the old ts: the next poll or push replaces this guess with what the device reports.
        components[component_id] = {**components.get(component_id, {}), "reportedValue": value}
        self.async_set_updated_data(self.data)  # this cancels a pending refresh, so request after
        await self.async_request_refresh()
