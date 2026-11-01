"""Climate platform: one entity per Fluidra heat pump."""
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HEAT_PUMP_COMPONENTS, FluidraPoolDataUpdateCoordinator

RUNNING, POWER, MODE, SETPOINT, WATER = 11, 13, 14, 15, 19  # component ids; °C values are ×10
MODES = {  # component 14 value -> (HVAC mode, preset)
    0: (HVACMode.HEAT, "smart"), 3: (HVACMode.HEAT, "boost"), 4: (HVACMode.HEAT, "silence"),
    1: (HVACMode.COOL, "smart"), 5: (HVACMode.COOL, "boost"), 6: (HVACMode.COOL, "silence"),
    2: (HVACMode.AUTO, "smart"),
}
MODE_VALUES = {mode_preset: value for value, mode_preset in MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[FluidraPoolDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a climate entity for every device that has the heat-pump components."""
    coordinator = entry.runtime_data
    async_add_entities(
        FluidraHeatPump(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if HEAT_PUMP_COMPONENTS <= device["components"].keys()
    )


class FluidraHeatPump(CoordinatorEntity[FluidraPoolDataUpdateCoordinator], ClimateEntity):
    """Power (13), mode (14), setpoint (15) and water temperature (19) of a heat pump."""

    _attr_has_entity_name = True
    _attr_translation_key = "heat_pump"
    _attr_icon = "mdi:heat-pump"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 15.0
    _attr_max_temp = 40.0

    def __init__(self, coordinator: FluidraPoolDataUpdateCoordinator, device_id: str) -> None:
        """Serve the device with this id; the unique id is the one of the pre-1.0 entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"fluidra_{device_id}_climate_heatpump"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Fluidra",
            name=coordinator.data[device_id]["info"].get("info", {}).get("name"),
        )

    @property
    def available(self) -> bool:
        """Unavailable after a failed poll or when the account no longer lists the device."""
        return super().available and self._device_id in self.coordinator.data

    def _value(self, component_id: int) -> Any:
        components = self.coordinator.data.get(self._device_id, {}).get("components", {})
        return components.get(component_id, {}).get("reportedValue")

    def _celsius(self, component_id: int) -> float | None:
        value = self._value(component_id)
        return None if value is None else value / 10

    @property
    def _mode(self) -> tuple[HVACMode | None, str | None]:
        return MODES.get(self._value(MODE), (None, None))

    @property
    def current_temperature(self) -> float | None:
        """Water temperature."""
        return self._celsius(WATER)

    @property
    def target_temperature(self) -> float | None:
        """Setpoint."""
        return self._celsius(SETPOINT)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Off when powered off, else the heat/cool/auto family of the mode."""
        return HVACMode.OFF if self._value(POWER) == 0 else self._mode[0]

    @property
    def preset_mode(self) -> str | None:
        """Smart, boost or silence; kept while powered off."""
        return self._mode[1]

    @property
    def preset_modes(self) -> list[str]:
        """The presets of the current family: auto has only smart."""
        return [preset for mode, preset in MODE_VALUES if mode == self._mode[0]]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Off, idle, heating or cooling; None while component 11 is not reported."""
        if self._value(POWER) == 0:
            return HVACAction.OFF
        # Component 11 = 0 idle / 1 running: UNVERIFIED reading of PROTOCOL_FINDINGS.md.
        if (running := self._value(RUNNING)) is None:
            return None
        if running == 0:
            return HVACAction.IDLE
        mode = self._mode[0]
        if mode == HVACMode.AUTO:  # running in auto: heating up to the setpoint, else cooling
            water, target = self.current_temperature, self.target_temperature
            if water is None or target is None:
                return None
            mode = HVACMode.HEAT if water <= target else HVACMode.COOL
        return {HVACMode.HEAT: HVACAction.HEATING, HVACMode.COOL: HVACAction.COOLING}.get(mode)

    async def _send(self, *commands: tuple[int, int]) -> None:
        """PUT the components in order; a failure raises HomeAssistantError and skips the rest."""
        for component_id, value in commands:
            await self.coordinator.async_set_component(self._device_id, component_id, value)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Off: power off. Heat/cool/auto: the smart mode of that family, then power on."""
        if hvac_mode == HVACMode.OFF:
            await self._send((POWER, 0))
        else:
            await self._send((MODE, MODE_VALUES[hvac_mode, "smart"]), (POWER, 1))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Switch to the preset within the current family (HA checks it is in preset_modes)."""
        await self._send((MODE, MODE_VALUES[self._mode[0], preset_mode]))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the setpoint (HA checks the 15.0-40.0 °C range)."""
        await self._send((SETPOINT, round(kwargs[ATTR_TEMPERATURE] * 10)))

    async def async_turn_on(self) -> None:
        """Power on in the current mode (HA's default would set heat). Off: set_hvac_mode."""
        await self._send((POWER, 1))
