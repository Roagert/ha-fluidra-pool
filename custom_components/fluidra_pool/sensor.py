"""Sensor platform: heat-pump temperatures and Wi-Fi signal, alarms of every device, and raw
component values of the devices we have no mapping for yet (#3 #4 #5 #8)."""
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


CELSIUS_MIN, CELSIUS_MAX = -30, 80  # a reading outside this is wrong (#4 showed 404.2 °C)
SENTINELS = (254, 255, 65535)  # raw values that probably mean "no data" (#8: pH 2.54 = raw 254)


def celsius(tenths: int | None) -> float | None:
    """°C from a component reporting °C × 10; None (unavailable) when out of range."""
    if tenths is None or not CELSIUS_MIN <= tenths / 10 <= CELSIUS_MAX:
        return None
    return tenths / 10


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
    """Add the sensors of every heat pump, the alarm sensor of every device, and for each other
    device a component count and a raw sensor per numeric component (disabled by default)."""
    coordinator = entry.runtime_data
    pumps = heat_pumps(coordinator)
    others = [device_id for device_id in coordinator.data if device_id not in pumps]
    async_add_entities(
        [
            FluidraSensor(coordinator, device_id, description)
            for device_id in pumps
            for description in SENSORS
        ]
        + [FluidraErrorSensor(coordinator, device_id) for device_id in coordinator.data]
        + [FluidraComponentCountSensor(coordinator, device_id) for device_id in others]
        + [
            FluidraComponentSensor(coordinator, device_id, component_id)
            for device_id in others
            for component_id, component in coordinator.data[device_id]["components"].items()
            if type(component.get("reportedValue")) in (int, float)  # a number, not a bool
        ]
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
        """Unavailable while the device does not report the component, or an implausible °C."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> float | None:
        """The reported value; tenths are converted to °C."""
        value = self._value(self.entity_description.component)
        return celsius(value) if self.entity_description.tenths else value


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


class FluidraComponentCountSensor(FluidraEntity, SensorEntity):
    """How many components the cloud reports for a device we have no mapping for."""

    _attr_translation_key = "component_count"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FluidraPoolDataUpdateCoordinator, device_id: str) -> None:
        """Unique id fluidra_<device id>_component_count."""
        super().__init__(coordinator, device_id, "component_count")

    @property
    def native_value(self) -> int:
        """The number of components."""
        return len(self.coordinator.data.get(self._device_id, {}).get("components", {}))


class FluidraComponentSensor(FluidraEntity, SensorEntity):
    """The raw value of one component of a device we have no mapping for: no scaling, no unit.

    Disabled by default; the meaning of each component waits for reporters' diagnostics.
    """

    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: FluidraPoolDataUpdateCoordinator, device_id: str, component_id: int
    ) -> None:
        """Unique id fluidra_<device id>_component_<component id>."""
        super().__init__(coordinator, device_id, f"component_{component_id}")
        self._component = component_id
        self._attr_name = f"Component {component_id}"

    @property
    def available(self) -> bool:
        """Unavailable while the component is not reported or reports a sentinel."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> Any:
        """The reported value; None for a sentinel."""
        value = self._value(self._component)
        return None if value in SENTINELS else value
