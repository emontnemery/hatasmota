"""Tasmota discovery."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from .mqtt import ReceiveMessage, TasmotaMQTTClient

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TasmotaEntityConfig:
    """Base class for Tasmota configuation."""

    endpoint: str
    idx: int | str | None
    friendly_name: str | None
    mac: str
    platform: str
    poll_payload: str
    poll_topic: str

    @property
    def unique_id(self) -> str:
        """Return unique_id."""
        return f"{self.mac}_{self.platform}_{self.endpoint}_{self.idx}"


@dataclass(frozen=True, kw_only=True)
class TasmotaAvailabilityConfig(TasmotaEntityConfig):
    """Tasmota availability configuation."""

    availability_topic: str
    availability_offline: str
    availability_online: str
    deep_sleep_enabled: bool


class TasmotaEntity:
    """Base class for Tasmota entities."""

    def __init__(self, config: TasmotaEntityConfig, mqtt_client: TasmotaMQTTClient):
        """Initialize."""
        self._cfg = config
        self._mqtt_client = mqtt_client
        self._on_state_callback: Callable | None = None
        super().__init__()

    def config_same(self, new_config: TasmotaEntityConfig) -> bool:
        """Return if updated config is same as current config."""
        return self._cfg == new_config

    def config_update(self, new_config: TasmotaEntityConfig) -> None:
        """Update config."""
        self._cfg = new_config

    async def poll_status(self) -> None:
        """Poll for status."""
        await self._mqtt_client.publish_debounced(
            self._cfg.poll_topic, self._cfg.poll_payload
        )

    def set_on_state_callback(self, on_state_callback: Callable) -> None:
        """Set callback for state change."""
        self._on_state_callback = on_state_callback

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe to all MQTT topics."""

    @property
    def mac(self) -> str:
        """Return MAC."""
        return self._cfg.mac

    @property
    def name(self) -> str | None:
        """Return friendly name."""
        return self._cfg.friendly_name

    @property
    def unique_id(self) -> str:
        """Return unique_id."""
        return self._cfg.unique_id


class TasmotaAvailability(TasmotaEntity):
    """Availability mixin for Tasmota entities."""

    _cfg: TasmotaAvailabilityConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._on_availability_callback: (
            Callable[[bool], Coroutine[Any, Any, None]] | None
        ) = None
        super().__init__(**kwds)

    def get_availability_topics(self) -> dict:
        """Return MQTT topics to subscribe to for availability state."""
        if self.deep_sleep_enabled:
            return {}

        async def availability_message_received(msg: ReceiveMessage) -> None:
            """Handle a new received MQTT availability message."""
            if msg.payload == self._cfg.availability_online:
                await self.poll_status()
            if not self._on_availability_callback:
                return
            if msg.payload == self._cfg.availability_online:
                await self._on_availability_callback(True)
            if msg.payload == self._cfg.availability_offline:
                await self._on_availability_callback(False)

        topics = {
            "availability_topic": {
                "event_loop_safe": True,
                "msg_callback": availability_message_received,
                "topic": self._cfg.availability_topic,
            }
        }
        return topics

    def set_on_availability_callback(self, on_availability_callback: Callable) -> None:
        """Set callback for availability state change."""
        self._on_availability_callback = on_availability_callback

    @property
    def deep_sleep_enabled(self) -> bool:
        """Return if deep sleep is enabled."""
        return self._cfg.deep_sleep_enabled
