"""Tasmota discovery."""
from __future__ import annotations

import logging
from typing import Any, Callable

import attr

from .mqtt import ReceiveMessage, TasmotaMQTTClient

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class TasmotaEntityConfig:
    """Base class for Tasmota configuation."""

    endpoint: str = attr.ib()
    idx: int | str | None = attr.ib()
    friendly_name: str | None = attr.ib()
    mac: str = attr.ib()
    platform: str = attr.ib()
    poll_payload: str = attr.ib()
    poll_topic: str = attr.ib()

    @property
    def unique_id(self) -> str:
        """Return unique_id."""
        return f"{self.mac}_{self.platform}_{self.endpoint}_{self.idx}"


@attr.s(slots=True, frozen=True)
class TasmotaAvailabilityConfig(TasmotaEntityConfig):
    """Tasmota availability configuation."""

    availability_topic: str = attr.ib()
    availability_offline: str = attr.ib()
    availability_online: str = attr.ib()


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

    def poll_status(self) -> None:
        """Poll for status."""
        self._mqtt_client.publish_debounced(
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
        self._on_availability_callback: Callable | None = None
        super().__init__(**kwds)

    def get_availability_topics(self) -> dict:
        """Return MQTT topics to subscribe to for availability state."""

        def availability_message_received(msg: ReceiveMessage) -> None:
            """Handle a new received MQTT availability message."""
            if msg.payload == self._cfg.availability_online:
                self.poll_status()
            if not self._on_availability_callback:
                return
            if msg.payload == self._cfg.availability_online:
                self._on_availability_callback(True)
            if msg.payload == self._cfg.availability_offline:
                self._on_availability_callback(False)

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
