"""Base entity: one device of the account, read from the coordinator."""
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HEAT_PUMP_COMPONENTS, FluidraPoolDataUpdateCoordinator

# Identity components of the amt heat pump (PROTOCOL.md); unverified on other devices.
SERIAL, FIRMWARE, SKU = 3, 4, 6


def heat_pumps(coordinator: FluidraPoolDataUpdateCoordinator) -> list[str]:
    """Ids of the devices that have the heat-pump components."""
    return [
        device_id
        for device_id, device in coordinator.data.items()
        if HEAT_PUMP_COMPONENTS <= device["components"].keys()
    ]


class FluidraEntity(CoordinatorEntity[FluidraPoolDataUpdateCoordinator]):
    """An entity of one device, with unique id fluidra_<device id>_<key>."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: FluidraPoolDataUpdateCoordinator, device_id: str, key: str
    ) -> None:
        """Serve the device with this id."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"fluidra_{device_id}_{key}"
        info = coordinator.data[device_id]["info"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Fluidra",
            name=info.get("info", {}).get("name"),
            model=info.get("type"),
            model_id=self._value(SKU),
            sw_version=self._value(FIRMWARE),
            serial_number=self._value(SERIAL),
        )

    @property
    def available(self) -> bool:
        """Unavailable after a failed poll, when the account no longer lists the device, or
        while the cloud reports it offline (it keeps the last values and accepts commands).

        UNVERIFIED: connectivity.connected is read as the device's online state; confirm in U03.
        """
        device = self.coordinator.data.get(self._device_id)
        return (
            super().available
            and device is not None
            and bool((device["info"].get("connectivity") or {}).get("connected", True))
        )

    def _value(self, component_id: int) -> Any:
        """The reported value of a component; None while the device does not report it."""
        components = self.coordinator.data.get(self._device_id, {}).get("components", {})
        return components.get(component_id, {}).get("reportedValue")
