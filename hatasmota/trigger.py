"""Tasmota binary sensor."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from .const import AUTOMATION_TYPE_TRIGGER
from .mqtt import ReceiveMessage, TasmotaMQTTClient

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TasmotaTriggerConfig(ABC):
    """Tasmota trigger configuation."""

    event: str
    idx: int
    mac: str
    subtype: str
    source: str
    trigger_topic: str
    type: str

    @property
    @abstractmethod
    def is_active(self) -> int:
        """Return if the trigger is active."""

    @property
    @abstractmethod
    def trigger_id(self) -> str:
        """Return trigger id."""


class TasmotaTrigger:
    """Representation of a Tasmota trigger."""

    def __init__(
        self, config: TasmotaTriggerConfig, mqtt_client: TasmotaMQTTClient, **_kwds: Any
    ):
        """Initialize."""
        self._sub_state: dict | None = None
        self.cfg = config
        self._mqtt_client = mqtt_client
        self._on_trigger_callback: Callable | None = None

    def config_same(self, new_config: TasmotaTriggerConfig) -> bool:
        """Return if updated config is same as current config."""
        return self.cfg == new_config

    def config_update(self, new_config: TasmotaTriggerConfig) -> None:
        """Update config."""
        self.cfg = new_config

    def set_on_trigger_callback(self, on_trigger_callback: Callable) -> None:
        """Set callback for triggere."""
        self._on_trigger_callback = on_trigger_callback

    def _trig_message_received(self, msg: ReceiveMessage) -> None:
        """Handle new MQTT messages."""

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""

        topics = {
            "trigger_topic": {
                "event_loop_safe": True,
                "topic": self.cfg.trigger_topic,
                "msg_callback": lambda msg: self._trig_message_received(  # pylint: disable=unnecessary-lambda
                    msg
                ),
            }
        }

        self._sub_state = await self._mqtt_client.subscribe(
            self._sub_state,
            topics,
        )

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    @property
    def automation_type(self) -> str:
        """Return the automation type."""
        return AUTOMATION_TYPE_TRIGGER
