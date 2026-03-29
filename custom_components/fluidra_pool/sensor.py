"""Sensor platform for Fluidra Pool integration."""
import logging
from typing import Any, Optional, Dict
from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
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
    
    # Create sensor entities only if they have data
    entities = []
    
    # Always create core entities that should exist
    entities.append(FluidraDevicesSensor(coordinator, device_id))  # Always needed for device management
    entities.append(FluidraErrorSensor(coordinator, device_id))    # Always needed for error monitoring
    
    # Conditionally create entities based on data availability
    if coordinator.user_profile_data:
        entities.append(FluidraUserProfileSensor(coordinator, device_id))
        _LOGGER.info("Adding User Profile sensor - data available")
    
    if coordinator.pool_status_data:
        entities.append(FluidraPoolStatusSensor(coordinator, device_id))
        _LOGGER.info("Adding Pool Status sensor - data available")
    
    if coordinator.user_pools_data:
        entities.append(FluidraUserPoolsSensor(coordinator, device_id))
        _LOGGER.info("Adding User Pools sensor - data available")
    
    if coordinator.device_components_data:
        entities.append(FluidraDeviceComponentsSensor(coordinator, device_id))
        _LOGGER.info("Adding Device Components sensor - data available")
    
    if coordinator.device_uiconfig_data:
        entities.append(FluidraDeviceUIConfigSensor(coordinator, device_id))
        _LOGGER.info("Adding Device UI Config sensor - data available")

    # Always add water temperature sensor (component 19)
    entities.append(FluidraWaterTemperatureSensor(coordinator, device_id))

    # Add chlorinator sensors when component data is available
    if coordinator.device_components_data:
        entities.extend([
            FluidraChlorinatorSensor(coordinator, device_id, "pH", "ph_key", None, None),
            FluidraChlorinatorSensor(coordinator, device_id, "ORP", "orp_key", "mV", SensorDeviceClass.VOLTAGE),
            FluidraChlorinatorSensor(coordinator, device_id, "Salinity", "salinity_key", "g/L", None),
            FluidraChlorinatorSensor(coordinator, device_id, "Free Chlorine", "free_chlorine_key", "ppm", None),
        ])

    _LOGGER.info("Creating %d sensor entities based on available data", len(entities))
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
        # Entity is available if we have device data, regardless of current update status
        # This prevents entities from showing as unavailable during updates
        return bool(self.coordinator.devices or self.coordinator.last_update_success)
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._coordinator_updated)
        )
    
    def _coordinator_updated(self) -> None:
        """Handle coordinator data update."""
        _LOGGER.debug("[Fluidra Debug] Sensor entity received coordinator update - writing HA state")
        self.async_write_ha_state()
    
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
        attrs = {
            "device_count": len(self.coordinator.devices) if self.coordinator.devices else 0,
            "last_update": self.coordinator.last_update_success,
        }
        
        # Add only essential device summary info (not full data to avoid 16KB limit)
        if self.coordinator.devices:
            devices_summary = {}
            for device_id, device_data in self.coordinator.devices.items():
                devices_summary[device_id] = {
                    "name": device_data.get("device_name", "Unknown"),
                    "model": device_data.get("device_model", "Unknown"),
                    "serial": device_data.get("serial_number", "Unknown"),
                    "status": device_data.get("status", "Unknown"),
                    "alarm_status": device_data.get("alarm_status", "normal"),
                    "error_code": device_data.get("error_code"),
                    "error_message": device_data.get("error_message"),
                }
            attrs["devices_summary"] = devices_summary
        
        return attrs

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
        attrs = {
            "last_update": self.coordinator.last_update_success,
        }
        
        # Add only essential user profile summary (not full data to avoid 16KB limit)
        if self.coordinator.user_profile_data:
            profile_data = self.coordinator.user_profile_data
            attrs["profile_summary"] = {
                "has_data": True,
                "has_name": bool(profile_data.get("name")),
                "has_email": bool(profile_data.get("email")),
                "has_preferences": bool(profile_data.get("preferences")),
            }
        else:
            attrs["profile_summary"] = {"has_data": False}
        
        return attrs

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
        attrs = {
            "last_update": self.coordinator.last_update_success,
        }
        
        # Add only essential pool status summary (not full data to avoid 16KB limit)
        if self.coordinator.pool_status_data:
            status_data = self.coordinator.pool_status_data
            attrs["status_summary"] = {
                "has_data": True,
                "status_available": bool(status_data),
            }
        else:
            attrs["status_summary"] = {"has_data": False}
        
        return attrs

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
        attrs = {
            "last_update": self.coordinator.last_update_success,
        }
        
        # Add only essential pools summary (not full data to avoid 16KB limit)
        if self.coordinator.user_pools_data:
            pools_data = self.coordinator.user_pools_data
            if isinstance(pools_data, list):
                attrs["pools_summary"] = {
                    "has_data": True,
                    "pool_count": len(pools_data),
                    "pools": [{"id": pool.get("id"), "name": pool.get("name", "Unnamed")} for pool in pools_data[:5]]  # Limit to 5 pools
                }
            else:
                attrs["pools_summary"] = {"has_data": True, "pool_count": 1}
        else:
            attrs["pools_summary"] = {"has_data": False, "pool_count": 0}
        
        return attrs

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
        attrs = {
            "last_update": self.coordinator.last_update_success,
        }
        
        # Add only essential component summary info (not full data to avoid 16KB limit)
        if self.coordinator.device_components_data:
            components_summary = {}
            for device_id, components in self.coordinator.device_components_data.items():
                device_components = {}
                for comp_id, comp_data in components.items():
                    if isinstance(comp_data, dict):
                        device_components[comp_id] = {
                            "type": comp_data.get("type"),
                            "status": comp_data.get("status"),
                            "value": comp_data.get("reportedValue"),
                            "unit": comp_data.get("unit"),
                            "writable": comp_data.get("writable", False),
                        }
                components_summary[device_id] = device_components
            attrs["components_summary"] = components_summary
            attrs["total_components"] = sum(len(comps) for comps in self.coordinator.device_components_data.values())
        
        return attrs

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
        attrs = {
            "last_update": self.coordinator.last_update_success,
        }
        
        # Add only essential UI config summary (not full data to avoid 16KB limit)
        if self.coordinator.device_uiconfig_data:
            uiconfig_summary = {}
            for device_id, config_data in self.coordinator.device_uiconfig_data.items():
                if isinstance(config_data, dict):
                    uiconfig_summary[device_id] = {
                        "config_available": True,
                        "has_temperature_config": "temperature" in str(config_data).lower(),
                        "has_mode_config": "mode" in str(config_data).lower(),
                        "config_keys": list(config_data.keys()) if isinstance(config_data, dict) else [],
                    }
            attrs["uiconfig_summary"] = uiconfig_summary
        
        return attrs

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


class FluidraWaterTemperatureSensor(FluidraBaseEntity, SensorEntity):
    """Standalone water temperature sensor (component 19)."""

    _attr_name = "Water Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("water_temperature")

    def _get_component_value(self, component_id: int) -> Optional[float]:
        actual_device_id = self._get_actual_device_id()
        if not self.coordinator.device_components_data or not actual_device_id:
            return None
        components = self.coordinator.device_components_data.get(actual_device_id, {})
        data = components.get(component_id) or components.get(str(component_id))
        if isinstance(data, dict):
            raw = data.get("reportedValue")
            if raw is not None:
                return round(raw / 10.0, 1)
        return None

    @property
    def native_value(self) -> Optional[float]:
        """Return water temperature in °C (component 19, raw × 0.1)."""
        return self._get_component_value(19)


# Map from sensor name → (i18n key prefix, unit, device_class)
_CHLORINATOR_COMPONENT_MAP = {
    "ph_key": (None, "pH"),
    "orp_key": (None, "mV"),
    "salinity_key": (None, "g/L"),
    "free_chlorine_key": (None, "ppm"),
}


class FluidraChlorinatorSensor(FluidraBaseEntity, SensorEntity):
    """Sensor for a single chlorinator measurement (pH, ORP, salinity, free chlorine).

    Component IDs are resolved at runtime from the UI config data, keyed by
    i18n key (e.g. 'ph_key').  If the device does not have the component the
    sensor will remain unavailable rather than raising an error.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator,
        device_id: Optional[str],
        friendly_name: str,
        i18n_key: str,
        unit: Optional[str],
        device_class: Optional[str],
    ):
        super().__init__(coordinator, device_id)
        self._friendly_name = friendly_name
        self._i18n_key = i18n_key
        self._attr_name = friendly_name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_unique_id = self._get_unique_id(f"chlorinator_{i18n_key}")
        self._resolved_component_id: Optional[int] = None

    def _resolve_component_id(self) -> Optional[int]:
        """Find component ID from uiconfig by matching the i18n key."""
        if self._resolved_component_id is not None:
            return self._resolved_component_id
        if not self.coordinator.device_uiconfig_data:
            return None
        actual_device_id = self._get_actual_device_id()
        if not actual_device_id:
            return None
        uiconfig = self.coordinator.device_uiconfig_data.get(actual_device_id, {})
        # Walk all UI components looking for a matching i18n key
        for item in uiconfig.get("components", []) if isinstance(uiconfig, dict) else []:
            i18n = item.get("i18n", {})
            if isinstance(i18n, dict):
                for lang_data in i18n.values():
                    if isinstance(lang_data, dict) and lang_data.get("key") == self._i18n_key:
                        comp_id = item.get("componentRead") or item.get("readId")
                        if comp_id is not None:
                            self._resolved_component_id = int(comp_id)
                            return self._resolved_component_id
        return None

    @property
    def available(self) -> bool:
        """Only available when we can resolve the component ID."""
        return super().available and self._resolve_component_id() is not None

    @property
    def native_value(self) -> Optional[float]:
        """Return the sensor value from the components data."""
        comp_id = self._resolve_component_id()
        if comp_id is None:
            return None
        actual_device_id = self._get_actual_device_id()
        if not self.coordinator.device_components_data or not actual_device_id:
            return None
        components = self.coordinator.device_components_data.get(actual_device_id, {})
        data = components.get(comp_id) or components.get(str(comp_id))
        if isinstance(data, dict):
            raw = data.get("reportedValue")
            if raw is not None:
                # pH and ORP are typically reported as raw × 0.01 or × 0.1 — return raw for now
                # and let the user see the actual value; can be adjusted once live data is captured
                return raw
        return None