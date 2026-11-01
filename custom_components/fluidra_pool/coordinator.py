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
from .const import ERROR_CODES, QUICK_UPDATE_INTERVAL

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
        try:
            for info in await self.api.async_get_devices():
                device_id = info["id"]
                if device_id not in self.uiconfig:
                    self.uiconfig[device_id] = await self.api.async_get_uiconfig(device_id)
                components = await self.api.async_get_components(device_id)
                stored = old.get(device_id, {}).get("components", {})
                for component_id, component in components.items():
                    if stored.get(component_id, {}).get("ts", 0) > component.get("ts", 0):
                        components[component_id] = stored[component_id]
                data[device_id] = {"info": info, "components": components}
        except FluidraAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FluidraConnectionError as err:
            raise UpdateFailed(str(err)) from err
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

    # --- compat shim for pre-T10/T11 entities; delete in T10/T11 ---
    # sensor.py and button.py still read the old coordinator's attributes.
    consumer_data = user_profile_data = pool_status_data = user_pools_data = {}  # fetches gone

    @property
    def device_id(self) -> str | None:
        """The one device the old entities serve: the first heat pump, else the first device."""
        heat_pumps = [
            device_id
            for device_id, dev in self.data.items()
            if HEAT_PUMP_COMPONENTS <= dev["components"].keys()
        ]
        return next(iter(heat_pumps or self.data), None)

    @property
    def devices(self) -> dict[str, dict[str, Any]]:
        """Old-style device dicts; empty after a failed poll so the old entities go unavailable."""
        if not self.last_update_success:
            return {}
        return {device_id: _legacy_device(dev["info"]) for device_id, dev in self.data.items()}

    @property
    def device_components_data(self) -> dict[str, dict[int, dict[str, Any]]]:
        """{device_id: components}."""
        return {device_id: dev["components"] for device_id, dev in self.data.items()}

    @property
    def device_uiconfig_data(self) -> dict[str, dict[str, Any]]:
        """{device_id: uiconfig} for the devices that have one."""
        return {device_id: ui for device_id, ui in self.uiconfig.items() if ui is not None}

    @property
    def error_information(self) -> dict[str, Any]:
        """Alarm summary of the device the old entities serve."""
        if not (device := self.devices.get(self.device_id)):
            return {}
        keys = ("error_code", "error_message", "alarm_status", "alarm_count")
        return {
            **{key: device[key] for key in keys},
            "device_id": self.device_id,
            "error_description": ERROR_CODES.get(device["error_code"], "Unknown error"),
        }


def _legacy_device(info: dict[str, Any]) -> dict[str, Any]:
    """The fields the old entities read from the old coordinator's processed device."""
    alarms = info.get("alarms", [])
    errors = [alarm for alarm in alarms if alarm.get("type") == "error"]
    warnings = [alarm for alarm in alarms if alarm.get("type") == "warning"]
    device = {
        "serial_number": info.get("sn") or info.get("serialNumber") or info.get("SerialNumber"),
        "device_name": info.get("info", {}).get("name"),
        "device_model": info.get("info", {}).get("family"),
        "device_firmware": info.get("vr") or info.get("currentFirmwareVersion"),
        "status": info.get("status"),
        "alarm_count": len(alarms),
        "alarm_status": (
            "error" if errors else "warning" if warnings else "unknown" if alarms else "normal"
        ),
        "error_code": None,
        "error_message": None,
    }
    if errors:
        code = device["error_code"] = errors[0].get("errorCode") or errors[0].get("code")
        device["error_message"] = _alarm_text(errors[0]) or ERROR_CODES.get(code, "Unknown error")
    elif warnings:
        device["warning_code"] = warnings[0].get("warningCode") or warnings[0].get("code")
        device["warning_message"] = _alarm_text(warnings[0]) or "Warning condition detected"
    return device


def _alarm_text(alarm: dict[str, Any]) -> str | None:
    return alarm.get("message") or alarm.get("text") or alarm.get("default", {}).get("text")
# --- end compat shim ---
