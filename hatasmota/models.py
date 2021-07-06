"""Tasmota types."""
from typing import Awaitable, Callable, List, Tuple, TypedDict, Union

import attr

from .entity import TasmotaAvailabilityConfig, TasmotaEntityConfig


@attr.s(slots=True, frozen=True)
class TasmotaBaseSensorConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota Base Sensor configuration."""


DiscoveryHashType = Tuple[str, str, str, Union[str, int]]
DeviceDiscoveredCallback = Callable[[dict, str], Awaitable[None]]
SensorsDiscoveredCallback = Callable[
    [List[Tuple[TasmotaBaseSensorConfig, DiscoveryHashType]], str], Awaitable[None]
]


class TasmotaDeviceConfig(TypedDict, total=False):
    """Tasmota device config."""

    ip: str
    mac: str
    manufacturer: str
    md: str
    name: str
    sw: str
