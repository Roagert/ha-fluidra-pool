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

from .const import DOMAIN, CONF_DEVICE_ID, CONF_COMPONENT_ID

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
    _attr_max_temp = 40.0
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
        """Build mode mapping from API component states or use clear, HA-compatible names."""
        self._log_all_components()
        # Fixed mapping for Fluidra Pool heat pump modes (component 14)
        self._mode_mapping = {
            "Smart Auto": 2,           # Smart Heating / Cooling (Auto)
            "Smart Heating": 0,      # Energy-saving heating
            "Boost Heating": 3,      # Fast heating
            "Silence Heating": 4,   # Quiet heating
            "Smart Cooling": 1,     # Energy-saving cooling
            "Boost Cooling": 5,      # Fast cooling
            "Silence Cooling": 6    # Quiet cooling
        }
        self._reverse_mode_mapping = {v: k for k, v in self._mode_mapping.items()}
        _LOGGER.info("Final mode mapping: %s", self._mode_mapping)
        _LOGGER.info("Component IDs - mode: %s, temp: %s, target: %s, power: %s", \
                    self._component_id, self._temperature_component_id, \
                    self._target_temp_component_id, self._power_component_id)
    
    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature (component 19)."""
        actual_device_id = self._get_actual_device_id()
        if self.coordinator.device_components_data and actual_device_id:
            device_components = self.coordinator.device_components_data.get(actual_device_id, {})
            component_data = device_components.get(19) or device_components.get("19")
            if isinstance(component_data, dict):
                reported_value = component_data.get('reportedValue')
                if reported_value is not None:
                    return float(reported_value) / 10.0
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
                if reported_value is not None:
                    return float(reported_value) / 10.0
        return self._attr_target_temperature
    
    @property
    def hvac_mode(self) -> str:
        """Return hvac operation mode."""
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
        return {
            "component_id": self._component_id,
            "temperature_component_id": self._temperature_component_id,
            "target_temp_component_id": self._target_temp_component_id,
            "power_component_id": self._power_component_id,
            "available_modes": self._mode_mapping,
            "device_id": self.device_id,
            "last_update": self.coordinator.last_update_success,
        }
    
    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature (component 15)."""
        if ATTR_TEMPERATURE in kwargs:
            new_temp = kwargs[ATTR_TEMPERATURE]
            self._attr_target_temperature = new_temp
            _LOGGER.info("Setting target temperature to %s", new_temp)
            desired_value = int(new_temp * 10)
            
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
                # The coordinator will automatically fetch fresh data and notify all entities
                _LOGGER.info("Temperature set successfully, coordinator will update all entities")
            else:
                _LOGGER.error("Failed to set target temperature to %s", new_temp)
    
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
                # The coordinator will automatically fetch fresh data and notify all entities
                _LOGGER.info("Power off successful, coordinator will update all entities")
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
                # The coordinator will automatically fetch fresh data and notify all entities
                _LOGGER.info("Power on successful, coordinator will update all entities")
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
                # The coordinator will automatically fetch fresh data and notify all entities
                _LOGGER.info("Preset mode set successfully, coordinator will update all entities")
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
            _LOGGER.info("Turn on successful, coordinator will update all entities")
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
            _LOGGER.info("Turn off successful, coordinator will update all entities")
        else:
            _LOGGER.error("Failed to turn off the heat pump via turn_off (device: %s)", actual_device_id)

    def turn_on(self) -> None:
        """Sync wrapper for turn_on."""
        return self.hass.async_create_task(self.async_turn_on())

    def turn_off(self) -> None:
        """Sync wrapper for turn_off."""
        return self.hass.async_create_task(self.async_turn_off()) 