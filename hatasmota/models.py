"""Tasmota types."""
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Callable, List, Tuple, TypedDict, Union

from .entity import TasmotaAvailabilityConfig, TasmotaEntityConfig


@dataclass(frozen=True, kw_only=True)
class TasmotaBaseSensorConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota Base Sensor configuration."""


DiscoveryHashType = Tuple[str, str, str, Union[str, int]]
DeviceDiscoveredCallback = Callable[[dict, str], Coroutine[Any, Any, None]]
SensorsDiscoveredCallback = Callable[
    [List[Tuple[TasmotaBaseSensorConfig, DiscoveryHashType]], str],
    Coroutine[Any, Any, None],
]


class TasmotaDeviceConfig(TypedDict, total=False):
    """Tasmota device config."""

    ip: str
    mac: str
    manufacturer: str
    md: str
    name: str
    sw: str
