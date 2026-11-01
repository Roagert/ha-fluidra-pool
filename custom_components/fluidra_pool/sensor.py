"""Sensor platform: temperatures and Wi-Fi signal of each heat pump, alarms of every device."""
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FluidraPoolDataUpdateCoordinator
from .entity import FluidraEntity, heat_pumps


@dataclass(frozen=True, kw_only=True)
class FluidraSensorDescription(SensorEntityDescription):
    """A sensor showing one component; tenths: the component reports °C × 10."""

    component: int
    tenths: bool = False


CELSIUS_TENTHS: dict[str, Any] = {
    "tenths": True,
    "device_class": SensorDeviceClass.TEMPERATURE,
    "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
}
SENSORS = (
    FluidraSensorDescription(
        key="water_temperature", component=19, state_class=SensorStateClass.MEASUREMENT,
        **CELSIUS_TENTHS,
    ),
    FluidraSensorDescription(
        key="air_temperature", component=62, state_class=SensorStateClass.MEASUREMENT,
        **CELSIUS_TENTHS,
    ),
    FluidraSensorDescription(key="target_temperature", component=15, **CELSIUS_TENTHS),
    FluidraSensorDescription(
        key="wifi_rssi",
        component=1,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[FluidraPoolDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the component sensors of every heat pump and the alarm sensor of every device."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            FluidraSensor(coordinator, device_id, description)
            for device_id in heat_pumps(coordinator)
            for description in SENSORS
        ]
        + [FluidraErrorSensor(coordinator, device_id) for device_id in coordinator.data]
    )


class FluidraSensor(FluidraEntity, SensorEntity):
    """The value of one component."""

    entity_description: FluidraSensorDescription

    def __init__(
        self,
        coordinator: FluidraPoolDataUpdateCoordinator,
        device_id: str,
        description: FluidraSensorDescription,
    ) -> None:
        """Unique id and translation key are the description's key."""
        super().__init__(coordinator, device_id, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def available(self) -> bool:
        """Unavailable while the device does not report the component."""
        return super().available and self._value(self.entity_description.component) is not None

    @property
    def native_value(self) -> float | None:
        """The reported value; tenths are converted to °C."""
        value = self._value(self.entity_description.component)
        return value / 10 if self.entity_description.tenths and value is not None else value


class FluidraErrorSensor(FluidraEntity, SensorEntity):
    """State "ok", or "alarm" while the cloud lists alarms for the device (raw list attribute).

    UNVERIFIED: no error component is known. Like the pre-1.0 sensor, this reads the "alarms"
    list of the cloud's device record, which no capture has shown yet.
    """

    _attr_translation_key = "error_information"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FluidraPoolDataUpdateCoordinator, device_id: str) -> None:
        """The unique id is the one of the pre-1.0 entity."""
        super().__init__(coordinator, device_id, "error_information")

    @property
    def _alarms(self) -> list[Any]:
        return self.coordinator.data.get(self._device_id, {}).get("info", {}).get("alarms") or []

    @property
    def native_value(self) -> str:
        """Alarm while any alarm is listed, else ok."""
        return "alarm" if self._alarms else "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The alarms as the cloud reports them."""
        return {"alarms": self._alarms}
