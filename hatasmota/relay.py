"""Tasmota switch."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, cast

from .const import COMMAND_POWER, CONF_MAC
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .mqtt import ReceiveMessage
from .utils import (
    config_get_friendlyname,
    config_get_state_offline,
    config_get_state_online,
    config_get_state_power_off,
    config_get_state_power_on,
    get_state_power,
    get_topic_command,
    get_topic_command_state,
    get_topic_stat_result,
    get_topic_tele_state,
    get_topic_tele_will,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TasmotaRelayConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota relay configuation."""

    idx: int

    command_topic: str
    result_topic: str
    state_power_off: str
    state_power_on: str
    state_topic: str

    @classmethod
    def from_discovery_message(
        cls, config: dict, idx: int, platform: str
    ) -> TasmotaRelayConfig:
        """Instantiate from discovery message."""
        return cls(
            endpoint="relay",
            idx=idx,
            friendly_name=config_get_friendlyname(config, platform, idx),
            mac=config[CONF_MAC],
            platform=platform,
            poll_payload="",
            poll_topic=get_topic_command_state(config),
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            command_topic=get_topic_command(config),
            result_topic=get_topic_stat_result(config),
            state_power_off=config_get_state_power_off(config),
            state_power_on=config_get_state_power_on(config),
            state_topic=get_topic_tele_state(config),
        )


class TasmotaRelay(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota relay."""

    _cfg: TasmotaRelayConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._sub_state: dict | None = None
        self.light_type = None
        super().__init__(**kwds)

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""

        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT state messages."""
            if not self._on_state_callback:
                return

            state = get_state_power(cast(str, msg.payload), self._cfg.idx)
            if state == self._cfg.state_power_on:
                self._on_state_callback(True)
            elif state == self._cfg.state_power_off:
                self._on_state_callback(False)

        availability_topics = self.get_availability_topics()
        topics = {
            "result_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.result_topic,
                "msg_callback": state_message_received,
            },
            "state_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic,
                "msg_callback": state_message_received,
            },
        }
        topics = {**topics, **availability_topics}

        self._sub_state = await self._mqtt_client.subscribe(
            self._sub_state,
            topics,
        )

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    async def set_state(self, state: bool) -> None:
        """Turn the relay on or off."""
        payload = self._cfg.state_power_on if state else self._cfg.state_power_off
        command = f"{COMMAND_POWER}{self._cfg.idx+1}"
        await self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )
