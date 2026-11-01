"""Switch platform: power (component 13) of each heat pump."""
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FluidraPoolDataUpdateCoordinator
from .entity import FluidraEntity, heat_pumps

POWER = 13  # 0 off, 1 on


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[FluidraPoolDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a power switch for every heat pump."""
    coordinator = entry.runtime_data
    async_add_entities(FluidraPower(coordinator, dev_id) for dev_id in heat_pumps(coordinator))


class FluidraPower(FluidraEntity, SwitchEntity):
    """Powers the heat pump on or off in its current mode."""

    _attr_translation_key = "power"

    def __init__(self, coordinator: FluidraPoolDataUpdateCoordinator, device_id: str) -> None:
        """Serve the device with this id."""
        super().__init__(coordinator, device_id, "power")

    @property
    def available(self) -> bool:
        """Unavailable while the device does not report its power state."""
        return super().available and self._value(POWER) is not None

    @property
    def is_on(self) -> bool:
        """On unless the device reports 0."""
        return self._value(POWER) != 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send 13=1; shown at once, HomeAssistantError on failure."""
        await self.coordinator.async_set_component(self._device_id, POWER, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send 13=0; shown at once, HomeAssistantError on failure."""
        await self.coordinator.async_set_component(self._device_id, POWER, 0)
