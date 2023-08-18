"""Tasmota types."""
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypedDict

from .entity import TasmotaAvailabilityConfig, TasmotaEntityConfig


@dataclass(frozen=True, kw_only=True)
class TasmotaBaseSensorConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota Base Sensor configuration."""


DiscoveryHashType = tuple[str, str, str, str | int]
DeviceDiscoveredCallback = Callable[[dict, str], Coroutine[Any, Any, None]]
SensorsDiscoveredCallback = Callable[
    [list[tuple[TasmotaBaseSensorConfig, DiscoveryHashType]], str],
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
