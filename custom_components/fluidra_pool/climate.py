"""Climate platform for Fluidra Pool integration."""
import logging
from typing import Any, Optional, Dict

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import (
    UnitOfTemperature,
    ATTR_TEMPERATURE,
)
from homeassistant.components.climate.const import (
    HVACMode,
    HVACAction,
)

from .const import (
    DOMAIN, 
    CONF_DEVICE_ID, 
    CONF_COMPONENT_ID,
    ERROR_CODES,
    CRITICAL_ERROR_CODES,
    FLOW_ERROR_CODES,
    SMART_AUTO_DEADBAND,
    SMART_AUTO_MODE_VALUE
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fluidra Pool climate entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_id = hass.data[DOMAIN][config_entry.entry_id]["device_id"]
    
    if not device_id:
        _LOGGER.error("No device ID available for climate entity setup")
        return
    
    _LOGGER.info("Setting up climate entity with device ID: %s", device_id)
    _LOGGER.info("Available devices in coordinator: %s", list(coordinator.devices.keys()) if coordinator.devices else "None")
    _LOGGER.info("Available device components data: %s", list(coordinator.device_components_data.keys()) if coordinator.device_components_data else "None")
    
    # Create climate entities
    entities = [
        FluidraClimatePlaceholder(coordinator, device_id),
    ]
    async_add_entities(entities)

class FluidraBaseClimate:
    """Base class for Fluidra Pool climate entities."""
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        """Initialize the climate entity."""
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
        _LOGGER.debug("[Fluidra Debug] Climate entity received coordinator update - writing HA state")
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
        if not self.coordinator.devices:
            return self.device_id
            
        # The device_id in the config entry could be a serial number
        # Try to find the actual device ID from the devices data
        for dev_id, dev_data in self.coordinator.devices.items():
            # Check if this device matches our configured device_id
            if (dev_id == self.device_id or 
                dev_data.get("serial_number") == self.device_id or
                dev_data.get("sn") == self.device_id):
                _LOGGER.debug("Found actual device ID: %s for configured device: %s", dev_id, self.device_id)
                return dev_id
        
        # Fallback to original device_id
        return self.device_id

    def _get_device_error_info(self) -> Dict[str, Any]:
        """Get current error information from the device."""
        actual_device_id = self._get_actual_device_id()
        if not actual_device_id or not self.coordinator.devices:
            return {}
        
        # Find the device in coordinator data
        device_data = self.coordinator.devices.get(actual_device_id)
        if not device_data:
            return {}
        
        error_info = {
            "has_error": False,
            "has_critical_error": False,
            "has_flow_error": False,
            "error_code": None,
            "error_message": None,
            "warning_code": None,
            "warning_message": None,
            "alarm_status": "normal"
        }
        
        # Check for alarm status from coordinator processing
        alarm_status = device_data.get("alarm_status")
        if alarm_status:
            error_info["alarm_status"] = alarm_status
            
            if alarm_status == "error":
                error_info["has_error"] = True
                error_code = device_data.get("error_code")
                error_message = device_data.get("error_message")
                
                if error_code:
                    error_info["error_code"] = error_code
                    error_info["error_message"] = error_message or ERROR_CODES.get(error_code, "Unknown error")
                    
                    # Check if it's a critical error
                    if error_code in CRITICAL_ERROR_CODES:
                        error_info["has_critical_error"] = True
                        _LOGGER.warning("Critical error detected: %s - %s", error_code, error_info["error_message"])
                    
                    # Check if it's a flow error
                    if error_code in FLOW_ERROR_CODES:
                        error_info["has_flow_error"] = True
                        _LOGGER.warning("Flow error detected: %s - %s", error_code, error_info["error_message"])
                        
            elif alarm_status == "warning":
                warning_code = device_data.get("warning_code")
                warning_message = device_data.get("warning_message")
                if warning_code:
                    error_info["warning_code"] = warning_code
                    error_info["warning_message"] = warning_message or "Warning condition detected"
        
        if error_info["has_error"]:
            _LOGGER.info("Device %s error status: %s", actual_device_id, error_info)
        
        return error_info

    def _is_device_operationally_off(self) -> bool:
        """Check if device should be considered 'off' due to errors or actual power state."""
        error_info = self._get_device_error_info()
        
        # Critical errors should show device as off
        if error_info.get("has_critical_error"):
            _LOGGER.info("Device considered off due to critical error: %s", error_info.get("error_message"))
            return True
        
        # Check actual power state (component 13)
        actual_device_id = self._get_actual_device_id()
        if self.coordinator.device_components_data and actual_device_id:
            device_components = self.coordinator.device_components_data.get(actual_device_id, {})
            power_component = device_components.get(13) or device_components.get("13")
            if isinstance(power_component, dict):
                power_value = power_component.get('reportedValue')
                if power_value is not None and power_value == 0:
                    return True
        
        return False

    def _determine_smart_auto_mode(self) -> str:
        """Determine heat/cool mode for Smart Auto based on temperature comparison."""
        current_temp = self.current_temperature
        target_temp = self.target_temperature
        
        if current_temp is None or target_temp is None:
            _LOGGER.debug("Smart Auto: Missing temperature data (current=%s, target=%s)", current_temp, target_temp)
            return "heat"  # Default to heat if we can't determine
        
        temp_diff = target_temp - current_temp
        _LOGGER.debug("Smart Auto: current=%.1f°C, target=%.1f°C, diff=%.1f°C, deadband=%.1f°C", 
                     current_temp, target_temp, temp_diff, SMART_AUTO_DEADBAND)
        
        # Use deadband to prevent rapid switching
        if temp_diff > SMART_AUTO_DEADBAND:
            _LOGGER.debug("Smart Auto: Need heating (diff=%.1f°C > deadband=%.1f°C)", temp_diff, SMART_AUTO_DEADBAND)
            return "heat"
        elif temp_diff < -SMART_AUTO_DEADBAND:
            _LOGGER.debug("Smart Auto: Need cooling (diff=%.1f°C < -deadband=%.1f°C)", temp_diff, SMART_AUTO_DEADBAND)
            return "cool"
        else:
            # Within deadband - maintain current mode or default to heat
            _LOGGER.debug("Smart Auto: Within deadband (%.1f°C), maintaining current state", SMART_AUTO_DEADBAND)
            
            # Check if we can determine what the device is currently doing
            hvac_action = self.hvac_action
            if hvac_action == "heating":
                return "heat"
            elif hvac_action == "cooling":
                return "cool"
            else:
                return "heat"  # Default to heat when idle

    def _log_all_components(self):
        actual_device_id = self._get_actual_device_id()
        _LOGGER.info("[Fluidra Debug] Device ID mapping: %s -> %s", self.device_id, actual_device_id)
        
        if self.coordinator.device_components_data and actual_device_id:
            device_components = self.coordinator.device_components_data.get(actual_device_id, {})
            _LOGGER.info("[Fluidra Debug] Available device components for %s (actual device ID: %s):", self.device_id, actual_device_id)
            _LOGGER.info("Total components found: %d", len(device_components))
            
            # Log all available component IDs first
            available_component_ids = list(device_components.keys())
            _LOGGER.info("[Fluidra Debug] All available component IDs: %s", available_component_ids)
            
            # Log specific components we're looking for
            for component_id in [13, 14, 15, 19]:
                component_data = device_components.get(str(component_id)) or device_components.get(component_id)
                if component_data:
                    _LOGGER.info("  Component %s: %s", component_id, component_data)
                else:
                    _LOGGER.warning("  Component %s: NOT FOUND", component_id)
            
            # Log all components for debugging
            for cid, cdata in device_components.items():
                _LOGGER.debug("  Component %s: %s", cid, cdata)
        else:
            _LOGGER.warning("[Fluidra Debug] No device components data available for device %s (actual device ID: %s)", 
                          self.device_id, actual_device_id)
            _LOGGER.warning("device_components_data: %s", self.coordinator.device_components_data)
            _LOGGER.warning("device_id: %s", self.device_id)

class FluidraClimatePlaceholder(FluidraBaseClimate, ClimateEntity):
    """Climate entity for Fluidra Pool heat pump control."""
    
    _attr_name = "Pool Heat Pump"
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.PRESET_MODE |
        ClimateEntityFeature.TURN_ON |
        ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = ["heat", "cool", "off"]
    _attr_min_temp = 8.1  # From UI config: component 81 = 7°C + factor
    _attr_max_temp = 40.0  # From UI config: component 82 = 40°C
    _attr_target_temperature_step = 0.1
    _attr_icon = "mdi:heat-pump"
    
    def __init__(self, coordinator, device_id: Optional[str] = None):
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._get_unique_id("climate_heatpump")
        self._attr_current_temperature = None
        self._attr_target_temperature = 25.0
        self._attr_hvac_mode = "off"
        self._attr_hvac_action = "off"
        self._attr_preset_mode = None
        self._component_id = None
        self._mode_mapping = {}
        self._reverse_mode_mapping = {}
        self._temperature_component_id = None
        self._target_temp_component_id = None
        self._power_component_id = None
    
    def _build_mode_mapping(self):
        """Build mode mapping from actual API component states (verified from live data)."""
        self._log_all_components()
        # Verified mapping from UI Config and live device data (component 14)
        self._mode_mapping = {
            "Smart Auto": 2,           # Smart Heating / Cooling (Auto) - VERIFIED
            "Smart Heating": 0,        # Energy-saving heating - VERIFIED  
            "Smart Cooling": 1,        # Energy-saving cooling - VERIFIED
            "Boost Heating": 3,        # Fast heating - VERIFIED
            "Silence Heating": 4,      # Quiet heating - VERIFIED
            "Boost Cooling": 5,        # Fast cooling - VERIFIED
            "Silence Cooling": 6       # Quiet cooling - VERIFIED
        }
        self._reverse_mode_mapping = {v: k for k, v in self._mode_mapping.items()}
        _LOGGER.info("Final mode mapping (verified from live data): %s", self._mode_mapping)
        _LOGGER.info("Component IDs - power: 13, mode: 14, target temp: 15, current temp: 19")
    
    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature (component 19)."""
        actual_device_id = self._get_actual_device_id()
        if self.coordinator.device_components_data and actual_device_id:
            device_components = self.coordinator.device_components_data.get(actual_device_id, {})
            component_data = device_components.get(19) or device_components.get("19")
            if isinstance(component_data, dict):
                reported_value = component_data.get('reportedValue')
                if reported_value is not None and reported_value != 0:
                    # Based on live data: 228 = 22.8°C, so factor is 0.1
                    temp = float(reported_value) * 0.1
                    _LOGGER.debug("Current temperature: raw=%s, converted=%.1f°C", reported_value, temp)
                    return temp
        return self._attr_current_temperature
    
    @property
    def target_temperature(self) -> Optional[float]:
        """Return the target temperature (component 15)."""
        actual_device_id = self._get_actual_device_id()
        if self.coordinator.device_components_data and actual_device_id:
            device_components = self.coordinator.device_components_data.get(actual_device_id, {})
            component_data = device_components.get(15) or device_components.get("15")
            if isinstance(component_data, dict):
                reported_value = component_data.get('reportedValue')
                if reported_value is not None and reported_value != 0:
                    # Based on live data: 300 = 30.0°C, so factor is 0.1
                    temp = float(reported_value) * 0.1
                    _LOGGER.debug("Target temperature: raw=%s, converted=%.1f°C", reported_value, temp)
                    return temp
        return self._attr_target_temperature
    
    @property
    def hvac_mode(self) -> str:
        """Return hvac operation mode."""
        # First check if device is operationally off due to errors
        if self._is_device_operationally_off():
            return "off"
        
        # Check power status (component ID 13)
        actual_device_id = self._get_actual_device_id()
        if self.coordinator.device_components_data and actual_device_id:
            device_components = self.coordinator.device_components_data.get(actual_device_id, {})
            component_data = device_components.get(13) or device_components.get("13")
            
            if isinstance(component_data, dict):
                reported_value = component_data.get('reportedValue')
                if reported_value == 0:
                    return "off"
        
        # If powered on and no critical errors, check preset mode
        current_preset = self.preset_mode
        if current_preset:
            # Handle Smart Auto mode with temperature-based logic
            if current_preset == "Smart Auto":
                return self._determine_smart_auto_mode()
            elif "heating" in current_preset.lower():
                return "heat"
            elif "cooling" in current_preset.lower():
                return "cool"
        return "off"
    
    @property
    def hvac_action(self) -> str:
        """Return the current running hvac operation."""
        # Check power status first (component ID 13)
        actual_device_id = self._get_actual_device_id()
        if self.coordinator.device_components_data and actual_device_id:
            device_components = self.coordinator.device_components_data.get(actual_device_id, {})
            component_data = device_components.get(13) or device_components.get("13")
            
            if isinstance(component_data, dict):
                reported_value = component_data.get('reportedValue')
                if reported_value == 0:
                    return "off"
        
        # If powered on, check preset mode
        current_preset = self.preset_mode
        if current_preset:
            if "heating" in current_preset.lower():
                return "heating"
            elif "cooling" in current_preset.lower():
                return "cooling"
        return "off"
    
    @property
    def preset_modes(self) -> list:
        """Return available preset modes from API data."""
        if not self._mode_mapping:
            self._build_mode_mapping()
        return list(self._mode_mapping.keys())
    
    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode."""
        if not self._reverse_mode_mapping:
            self._build_mode_mapping()
        
        actual_device_id = self._get_actual_device_id()
        if self.coordinator.device_components_data and actual_device_id:
            device_components = self.coordinator.device_components_data.get(actual_device_id, {})
            component_data = device_components.get(14) or device_components.get("14")
            if isinstance(component_data, dict):
                current_value = component_data.get('reportedValue')
                if current_value is not None:
                    return self._reverse_mode_mapping.get(current_value, f"Unknown ({current_value})")
        
        return self._attr_preset_mode
    
    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return additional state attributes."""
        attributes = {
            "component_id": self._component_id,
            "temperature_component_id": self._temperature_component_id,
            "target_temp_component_id": self._target_temp_component_id,
            "power_component_id": self._power_component_id,
            "available_modes": self._mode_mapping,
            "device_id": self.device_id,
            "last_update": self.coordinator.last_update_success,
        }
        
        # Add error information to attributes
        error_info = self._get_device_error_info()
        if error_info:
            attributes.update({
                "alarm_status": error_info.get("alarm_status", "normal"),
                "has_error": error_info.get("has_error", False),
                "has_critical_error": error_info.get("has_critical_error", False),
                "has_flow_error": error_info.get("has_flow_error", False),
            })
            
            # Only add error details if there are actual errors
            if error_info.get("error_code"):
                attributes["error_code"] = error_info["error_code"]
                attributes["error_message"] = error_info["error_message"]
            
            if error_info.get("warning_code"):
                attributes["warning_code"] = error_info["warning_code"]
                attributes["warning_message"] = error_info["warning_message"]
        
        # Add Smart Auto mode information
        current_preset = self.preset_mode
        if current_preset == "Smart Auto":
            current_temp = self.current_temperature
            target_temp = self.target_temperature
            if current_temp is not None and target_temp is not None:
                temp_diff = target_temp - current_temp
                smart_auto_mode = self._determine_smart_auto_mode()
                attributes.update({
                    "smart_auto_active": True,
                    "temperature_difference": round(temp_diff, 1),
                    "smart_auto_mode": smart_auto_mode,
                    "deadband": SMART_AUTO_DEADBAND,
                })
        else:
            attributes["smart_auto_active"] = False
        
        return attributes
    
    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature (component 15)."""
        if ATTR_TEMPERATURE in kwargs:
            new_temp = kwargs[ATTR_TEMPERATURE]
            self._attr_target_temperature = new_temp
            _LOGGER.info("Setting target temperature to %.1f°C", new_temp)
            # Convert to raw value: 30.0°C = 300, so multiply by 10
            desired_value = int(new_temp * 10)
            _LOGGER.debug("Temperature conversion: %.1f°C -> raw value %d", new_temp, desired_value)
            
            actual_device_id = self._get_actual_device_id()
            if not actual_device_id:
                _LOGGER.error("No actual device ID found for device %s", self.device_id)
                return
                
            success = await self.coordinator.set_temperature_value(
                actual_device_id,
                15,
                desired_value
            )
            if success:
                # Schedule immediate refresh to show temperature change
                await self.coordinator.schedule_quick_update()
                _LOGGER.info("Temperature set successfully to %.1f°C, quick update scheduled", new_temp)
            else:
                _LOGGER.error("Failed to set target temperature to %.1f°C", new_temp)
    
    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        self._attr_hvac_mode = hvac_mode
        _LOGGER.info("Setting HVAC mode to %s", hvac_mode)
        
        actual_device_id = self._get_actual_device_id()
        if not actual_device_id:
            _LOGGER.error("No actual device ID found for device %s", self.device_id)
            return
        
        # Handle power on/off via component ID 13
        if hvac_mode == "off":
            # Turn off the unit by setting desiredValue to 0
            success = await self.coordinator.set_power_value(
                actual_device_id,
                13,  # Component ID 13 for power
                0  # desiredValue = 0 to turn off
            )
            
            if success:
                # Schedule immediate refresh to show power state change
                await self.coordinator.schedule_quick_update()
                _LOGGER.info("Power off successful, quick update scheduled")
            else:
                _LOGGER.error("Failed to turn off the heat pump")
        elif hvac_mode in ["heat", "cool"]:
            # Turn on the unit by setting desiredValue to 1
            success = await self.coordinator.set_power_value(
                actual_device_id,
                13,  # Component ID 13 for power
                1  # desiredValue = 1 to turn on
            )
            
            if success:
                # Schedule immediate refresh to show power state change
                await self.coordinator.schedule_quick_update()
                _LOGGER.info("Power on successful, quick update scheduled")
            else:
                _LOGGER.error("Failed to turn on the heat pump")
    
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if not self._mode_mapping:
            self._build_mode_mapping()
        
        if preset_mode in self._mode_mapping:
            mode_value = self._mode_mapping[preset_mode]
            _LOGGER.info("Setting preset mode to %s (value: %s)", preset_mode, mode_value)
            
            actual_device_id = self._get_actual_device_id()
            if not actual_device_id:
                _LOGGER.error("No actual device ID found for device %s", self.device_id)
                return
            
            success = await self.coordinator.set_component_value(
                actual_device_id,
                14,
                mode_value
            )
            
            if success:
                self._attr_preset_mode = preset_mode
                # Schedule immediate refresh to show mode change
                await self.coordinator.schedule_quick_update()
                _LOGGER.info("Preset mode set successfully, quick update scheduled")
            else:
                _LOGGER.error("Failed to set preset mode to %s", preset_mode)
        else:
            _LOGGER.error("Invalid preset mode: %s", preset_mode)
            # Fallback: set to Smart Auto
            fallback = "Smart Auto"
            if fallback in self._mode_mapping:
                await self.async_set_preset_mode(fallback)

    async def async_turn_on(self) -> None:
        """Turn the entity on (power on)."""
        actual_device_id = self._get_actual_device_id()
        if not actual_device_id:
            _LOGGER.error("No actual device ID found for device %s", self.device_id)
            return
        _LOGGER.debug("[Fluidra Debug] Sending turn ON command to device %s", actual_device_id)
        success = await self.coordinator.set_power_value(
            actual_device_id,
            13,  # Component ID 13 for power
            1  # desiredValue = 1 to turn on
        )
        if success:
            await self.coordinator.schedule_quick_update()
            _LOGGER.info("Turn on successful, quick update scheduled")
        else:
            _LOGGER.error("Failed to turn on the heat pump via turn_on (device: %s)", actual_device_id)

    async def async_turn_off(self) -> None:
        """Turn the entity off (power off)."""
        actual_device_id = self._get_actual_device_id()
        if not actual_device_id:
            _LOGGER.error("No actual device ID found for device %s", self.device_id)
            return
        _LOGGER.debug("[Fluidra Debug] Sending turn OFF command to device %s", actual_device_id)
        success = await self.coordinator.set_power_value(
            actual_device_id,
            13,  # Component ID 13 for power
            0  # desiredValue = 0 to turn off
        )
        if success:
            await self.coordinator.schedule_quick_update()
            _LOGGER.info("Turn off successful, quick update scheduled")
        else:
            _LOGGER.error("Failed to turn off the heat pump via turn_off (device: %s)", actual_device_id)

    def turn_on(self) -> None:
        """Sync wrapper for turn_on."""
        return self.hass.async_create_task(self.async_turn_on())

    def turn_off(self) -> None:
        """Sync wrapper for turn_off."""
        return self.hass.async_create_task(self.async_turn_off()) 