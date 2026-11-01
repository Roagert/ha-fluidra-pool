"""Binary sensor platform: no-flow error (component 28) of each heat pump that reports it."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FluidraPoolDataUpdateCoordinator
from .entity import FluidraEntity, heat_pumps

# 0 flow OK, else no-flow error: per ha-fluidra-local's README ("verified components");
# not in this repo's PROTOCOL_FINDINGS.md, so UNVERIFIED here.
NO_FLOW = 28


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[FluidraPoolDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a no-flow sensor for every heat pump that reports component 28."""
    coordinator = entry.runtime_data
    async_add_entities(
        FluidraNoFlow(coordinator, device_id)
        for device_id in heat_pumps(coordinator)
        if NO_FLOW in coordinator.data[device_id]["components"]
    )


class FluidraNoFlow(FluidraEntity, BinarySensorEntity):
    """On (problem) while the heat pump reports a no-flow error."""

    _attr_translation_key = "no_flow"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: FluidraPoolDataUpdateCoordinator, device_id: str) -> None:
        """Serve the device with this id."""
        super().__init__(coordinator, device_id, "no_flow")

    @property
    def available(self) -> bool:
        """Unavailable while the device does not report component 28."""
        return super().available and self._value(NO_FLOW) is not None

    @property
    def is_on(self) -> bool:
        """On for any value but 0."""
        return self._value(NO_FLOW) != 0
