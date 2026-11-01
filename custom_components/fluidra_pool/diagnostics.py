"""Diagnostics download: what the cloud reports for each device, without secrets or identity."""
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

LAN_IP_COMPONENT = 2
# Login secrets, and keys that can carry the owner's identity or home network details.
TO_REDACT = {
    "password", "refresh_token", "access_token", "id_token", "token", "udpKey",
    "username", "email", "name", "owner", "userId", "sub",
    "ip", "lan_ip", "mac", "bluetoothMacAddress", "ssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Info, components and UI config of every device; device ids and component values stay."""
    coordinator = entry.runtime_data
    devices = {}
    for device_id, device in coordinator.data.items():
        components = {**device["components"]}
        if LAN_IP_COMPONENT in components:
            components[LAN_IP_COMPONENT] = async_redact_data(
                components[LAN_IP_COMPONENT], {"reportedValue", "desiredValue"}
            )
        devices[device_id] = {
            **async_redact_data({"info": device["info"], "components": components}, TO_REDACT),
            # In the UI config "name" holds component labels, not people: keep it.
            "uiconfig": async_redact_data(coordinator.uiconfig.get(device_id), TO_REDACT - {"name"}),
        }
    return {"entry": async_redact_data(entry.data, TO_REDACT), "devices": devices}
