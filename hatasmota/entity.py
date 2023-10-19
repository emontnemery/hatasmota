"""Tasmota discovery."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any
import time
import json
from .utils import (
    get_value_by_path,
)

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
    sleep_state_topic: str


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
        self._on_availability_callback: Callable[
            [bool], Coroutine[Any, Any, None]
        ] | None = None
        self.uses_deep_sleep = False
        self.deep_sleep_interval = None
        self.last_up=0
        self.available=None
        super().__init__(**kwds)

    def get_availability_topics(self) -> dict:
        """Return MQTT topics to subscribe to for availability state."""

        async def availability_message_received(msg: ReceiveMessage) -> None:
            """Handle a new received MQTT availability message."""
            last_up_retain=self.last_up
            if msg.payload == self._cfg.availability_online:
                if self.last_up and self.deep_sleep_interval is None:
                    self.deep_sleep_interval = int(time.time() - self.last_up)
                await self.poll_status()
            else:
                self.last_up=time.time()
            available=self.available
            if msg.payload == self._cfg.availability_online:
                available=True
            if msg.payload == self._cfg.availability_offline and not(self.uses_deep_sleep):
                if not(self.uses_deep_sleep):
                    available=False
                else:
                    _LOGGER.debug("inhibit deep sleep %s", msg.topic)
            if not self._on_availability_callback:
                self.available=available
                return
            if self.available != available: 
                await self._on_availability_callback(available)
                self.available=available

        async def sleep_state_message_received(msg: ReceiveMessage) -> None:
            """Handle state messages to indicate deep sleep."""
            #try:
            #    payload = json.loads(msg.payload)
            #except json.decoder.JSONDecodeError:
            #    return
            _LOGGER.debug("sleep state %s -> %s", msg.topic, msg.payload)
            state = get_value_by_path(msg.payload, ["StatusPRM","RestartReason"])
            if state is not None:
                state=str(state).lower()
                if state.startswith('deep sleep'):
                    if not(self.uses_deep_sleep):
                        _LOGGER.debug("switching to deep sleep mode %s", msg.topic)
                        self.deep_sleep_interval=None
                        self.uses_deep_sleep=True
                    
        topics = {
            "availability_topic": {
                "event_loop_safe": True,
                "msg_callback": availability_message_received,
                "topic": self._cfg.availability_topic,
            },
            "sleep_state_topic": {
                "event_loop_safe": True,
                "msg_callback": sleep_state_message_received,
                "topic": self._cfg.sleep_state_topic,
            }
        }
        return topics

    def set_on_availability_callback(self, on_availability_callback: Callable) -> None:
        """Set callback for availability state change."""
        self._on_availability_callback = on_availability_callback
