"""Button platform for Fluidra Pool integration."""
import logging
from typing import Any, Optional, Dict

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_DEVICE_ID, CONF_COMPONENT_ID

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fluidra Pool buttons from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_id = hass.data[DOMAIN][config_entry.entry_id]["device_id"]
    
    # Create button entities
    entities = [
        FluidraRefreshButton(coordinator, device_id),
    ]
    
    async_add_entities(entities)

class FluidraBaseButton:
    """Base class for Fluidra Pool buttons."""
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        """Initialize the button."""
        self.coordinator = coordinator
        self.device_id = device_id
        self._attr_has_entity_name = True
        self._attr_should_poll = False
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
    
    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Return device info for this entity."""
        if not self.device_id:
            return None
        
        device_data = self._get_device_data()
        
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": device_data.get("device_name", f"Fluidra Pool {self.device_id}") if device_data else f"Fluidra Pool {self.device_id}",
            "manufacturer": "Fluidra",
            "model": device_data.get("device_model", "Pool Heat Pump") if device_data else "Pool Heat Pump",
            "sw_version": device_data.get("device_firmware", "Unknown") if device_data else "Unknown",
            "serial_number": device_data.get("serial_number") if device_data else None,
        }
    
    def _get_unique_id(self, base_id: str) -> str:
        """Generate unique ID with device_id if available."""
        if self.device_id:
            return f"fluidra_{self.device_id}_{base_id}"
        return f"fluidra_{base_id}"
    
    def _get_device_data(self) -> Optional[Dict[str, Any]]:
        """Get device data from coordinator."""
        if self.coordinator.devices and self.device_id:
            # First try to find by serial number
            for dev_id, dev_data in self.coordinator.devices.items():
                serial_number = dev_data.get("serial_number") or dev_data.get("SerialNumber")
                if serial_number == self.device_id:
                    return dev_data
            
            # If not found by serial number, try by device ID
            return self.coordinator.devices.get(self.device_id, {})
        return None

    def _get_actual_device_id(self) -> Optional[str]:
        """Return the actual device ID for all lookups and commands."""
        return self.device_id

class FluidraRefreshButton(FluidraBaseButton, ButtonEntity):
    """Button to refresh all Fluidra Pool data."""
    
    _attr_name = "Refresh All Data"
    _attr_entity_category = EntityCategory.CONFIG
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("refresh_all_data")
    
    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("[Fluidra Debug] Manual refresh requested for all Fluidra Pool data (button pressed)")
        try:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("[Fluidra Debug] Coordinator async_request_refresh completed successfully")
        except Exception as e:
            _LOGGER.error("[Fluidra Debug] Exception during async_request_refresh: %s", e) 