"""Sensor platform for Fluidra Pool integration."""
import logging
from typing import Any, Optional, Dict
from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
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
    """Set up Fluidra Pool sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_id = hass.data[DOMAIN][config_entry.entry_id]["device_id"]
    
    # Create all sensor entities (removed FluidraPoolsSensor)
    entities = [
        FluidraConsumerSensor(coordinator, device_id),
        FluidraDevicesSensor(coordinator, device_id),
        FluidraUserProfileSensor(coordinator, device_id),
        FluidraPoolStatusSensor(coordinator, device_id),
        FluidraUserPoolsSensor(coordinator, device_id),
        FluidraDeviceComponentsSensor(coordinator, device_id),
        FluidraDeviceUIConfigSensor(coordinator, device_id),
        FluidraErrorSensor(coordinator, device_id),
    ]
    
    async_add_entities(entities)

class FluidraBaseEntity:
    """Base class for Fluidra Pool entities."""
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        """Initialize the entity."""
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

# ============================================================================
# API ENDPOINT SENSORS (8 sensors)
# ============================================================================

class FluidraConsumerSensor(FluidraBaseEntity, SensorEntity):
    """Sensor containing all consumer API data."""
    
    _attr_name = "Consumer Data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("consumer_data")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.consumer_data:
            return "Available"
        return "Not Available"
    
    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        attrs = {
            "data": self.coordinator.consumer_data if hasattr(self, 'coordinator') and hasattr(self.coordinator, 'consumer_data') else None,
            "last_update": self.coordinator.last_update_success,
            "last_refreshed": datetime.now(timezone.utc).isoformat(),
        }
        return attrs

class FluidraDevicesSensor(FluidraBaseEntity, SensorEntity):
    """Sensor containing all devices API data."""
    
    _attr_name = "Devices Data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("devices_data")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.devices:
            device_count = len(self.coordinator.devices)
            return f"{device_count} Device(s)"
        return "No Devices"
    
    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        return {
            "data": self.coordinator.devices,
            "device_count": len(self.coordinator.devices) if self.coordinator.devices else 0,
            "last_update": self.coordinator.last_update_success,
        }

class FluidraUserProfileSensor(FluidraBaseEntity, SensorEntity):
    """Sensor containing all user profile API data."""
    
    _attr_name = "User Profile Data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("user_profile_data")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.user_profile_data:
            return "Available"
        return "Not Available"
    
    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        return {
            "data": self.coordinator.user_profile_data,
            "last_update": self.coordinator.last_update_success,
        }

class FluidraPoolStatusSensor(FluidraBaseEntity, SensorEntity):
    """Sensor containing all pool status API data."""
    
    _attr_name = "Pool Status Data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("pool_status_data")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.pool_status_data:
            return "Available"
        return "Not Available"
    
    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        return {
            "data": self.coordinator.pool_status_data,
            "last_update": self.coordinator.last_update_success,
        }

class FluidraUserPoolsSensor(FluidraBaseEntity, SensorEntity):
    """Sensor containing all user pools API data."""
    
    _attr_name = "User Pools Data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("user_pools_data")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.user_pools_data:
            return "Available"
        return "Not Available"
    
    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        return {
            "data": self.coordinator.user_pools_data,
            "last_update": self.coordinator.last_update_success,
        }

class FluidraDeviceComponentsSensor(FluidraBaseEntity, SensorEntity):
    """Sensor containing all device components API data."""
    
    _attr_name = "Device Components Data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("device_components_data")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.device_components_data:
            return "Available"
        return "Not Available"
    
    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        return {
            "data": self.coordinator.device_components_data,
            "last_update": self.coordinator.last_update_success,
        }

class FluidraDeviceUIConfigSensor(FluidraBaseEntity, SensorEntity):
    """Sensor containing all device UI config API data."""
    
    _attr_name = "Device UI Config Data"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("device_uiconfig_data")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.device_uiconfig_data:
            return "Available"
        return "Not Available"
    
    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        return {
            "data": self.coordinator.device_uiconfig_data,
            "last_update": self.coordinator.last_update_success,
        }

class FluidraErrorSensor(FluidraBaseEntity, SensorEntity):
    """Sensor containing error information."""
    
    _attr_name = "Error Information"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:exclamation"
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("error_information")
    
    @property
    def native_value(self) -> str:
        """Return the error code as the main value."""
        if self.coordinator.error_information:
            error_code = self.coordinator.error_information.get('error_code')
            if error_code:
                return str(error_code)
            # If no error code but there's an error message, show "Error"
            if self.coordinator.error_information.get('error_message'):
                return "Error"
        return "No Error"
    
    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes with title and text data."""
        if self.coordinator.error_information:
            return {
                "title": self.coordinator.error_information.get('error_description', 'Unknown Error'),
                "text": self.coordinator.error_information.get('error_message', 'No error message available'),
                "error_code": self.coordinator.error_information.get('error_code'),
                "alarm_status": self.coordinator.error_information.get('alarm_status'),
                "alarm_count": self.coordinator.error_information.get('alarm_count'),
                "device_id": self.coordinator.error_information.get('device_id'),
                "timestamp": self.coordinator.error_information.get('timestamp'),
                "last_update": self.coordinator.last_update_success,
            }
        return {
            "title": "No Error",
            "text": "System is operating normally",
            "last_update": self.coordinator.last_update_success,
        } 