"""The Fluidra Pool integration."""
import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ConfigEntryAuthFailed
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_ID, CONF_COMPONENT_ID
from .coordinator import FluidraPoolDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms for Fluidra Pool integration
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.CLIMATE]

# Import platforms
from . import sensor

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fluidra Pool from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create coordinator
    coordinator = FluidraPoolDataUpdateCoordinator(
        hass, 
        entry.data[CONF_USERNAME], 
        entry.data[CONF_PASSWORD],
        entry
    )
    
    # Store coordinator temporarily
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "device_id": None,  # Will be resolved after first update
        "component_id": entry.data.get(CONF_COMPONENT_ID),
    }
    
    # Register diagnostic service
    async def handle_dump_api_data(call):
        data = {
            "consumer": coordinator.consumer_data,
            "devices": coordinator.devices,
            "user_profile": coordinator.user_profile_data,
            "pool_status": coordinator.pool_status_data,
            "user_pools": coordinator.user_pools_data,
            "device_components": coordinator.device_components_data,
            "device_uiconfig": coordinator.device_uiconfig_data,
        }
        _LOGGER.info("[Fluidra Diagnostic] Dumping latest API data: %s", data)
    hass.services.async_register(DOMAIN, "dump_api_data", handle_dump_api_data)
    
    # Verify we can connect to the API and get initial data
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.async_shutdown()
        raise
    except ConfigEntryAuthFailed:
        _LOGGER.error("Authentication failed for Fluidra Pool API")
        await coordinator.async_shutdown()
        raise
    except Exception as err:
        _LOGGER.error("Failed to connect to Fluidra Pool API: %s", err)
        await coordinator.async_shutdown()
        return False
    
    # Now resolve the device ID after coordinator has fetched data
    device_id = None
    if coordinator.devices:
        # Always use the first device's actual device ID (from 'id' field)
        first_device_id = next(iter(coordinator.devices.keys()))
        device_id = first_device_id
        _LOGGER.info("Using actual device ID from Devices Data: %s", device_id)
    
    if not device_id:
        _LOGGER.error("No device ID available after coordinator update")
        await coordinator.async_shutdown()
        return False

    # Update the stored device ID (this will be the actual device ID for all entities)
    hass.data[DOMAIN][entry.entry_id]["device_id"] = device_id

    # Set up device registry entries
    await _setup_device_registry(hass, entry, coordinator, device_id)
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Listen for config entry updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True

async def _setup_device_registry(hass: HomeAssistant, entry: ConfigEntry, coordinator: FluidraPoolDataUpdateCoordinator, device_id: str) -> None:
    """Set up device registry entries."""
    device_registry = dr.async_get(hass)
    
    # Find the device data that matches our device_id (could be serial number or device ID)
    device_data = None
    actual_device_id = None
    
    if coordinator.devices:
        # First try to find by serial number
        for dev_id, dev_data in coordinator.devices.items():
            serial_number = dev_data.get("serial_number") or dev_data.get("SerialNumber")
            if serial_number == device_id:
                device_data = dev_data
                actual_device_id = dev_id  # This is the ID used for API calls
                break
        
        # If not found by serial number, try by device ID
        if not device_data and device_id in coordinator.devices:
            device_data = coordinator.devices[device_id]
            actual_device_id = device_id
    
    # Create device info using device_firmware for firmware version
    device_name = "Fluidra Pool Heat Pump"
    firmware_version = "Unknown"
    if device_data:
        # Use device name from data if available
        device_name = (device_data.get("device_name") or 
                      device_data.get("name") or 
                      device_data.get("info", {}).get("name") or 
                      "Fluidra Pool Heat Pump")
        # Use device_firmware for firmware version
        firmware_version = (
            device_data.get("device_firmware") or
            device_data.get("currentFirmwareVersion") or
            device_data.get("vr") or
            device_data.get("info", {}).get("vr") or
            "Unknown"
        )
        _LOGGER.info("[Fluidra Debug] Firmware version used for device registry: %s", firmware_version)
        # Use serial number for device identifier
        serial_number = (device_data.get("serial_number") or 
                        device_data.get("SerialNumber") or 
                        device_id)
    else:
        serial_number = device_id
    device_info = {
        "identifiers": {(DOMAIN, device_id)},
        "name": device_name,
        "manufacturer": "Fluidra",
        "model": "Pool Heat Pump",
        "sw_version": firmware_version,
        "serial_number": serial_number,
        "via_device": None,
    }
    
    # Register the device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **device_info
    )
    
    _LOGGER.info("Registered device: %s (Serial: %s, Firmware: %s, API Device ID: %s)", 
                device_name, serial_number, firmware_version, actual_device_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id) 