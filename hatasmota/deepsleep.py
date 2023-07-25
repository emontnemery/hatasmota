"""Tasmota deepsleep."""
from __future__ import annotations

import logging
from typing import Any

import attr

from .const import (
    CONF_DEEPSLEEP,
    DEEPSLEEP_REPORTTIME,
    DEEPSLEEP_SLEEPTIME,
    DEEPSLEEP_WAKEUPTIME,
)
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .mqtt import ReceiveMessage
from .utils import (
    config_get_state_offline,
    config_get_state_online,
    get_topic_command,
    get_topic_command_status,
    get_topic_stat_result,
    get_topic_stat_status,
    get_topic_tele_sensor,
    get_topic_tele_will,
    get_value_by_path,
)

_LOGGER = logging.getLogger(__name__)

""" 07:08:40.513 MQT: hm/tele/ESP_3284D1/DEEPSLEEP = {"DeepSleep":{"Time":"2023-07-18T07:09:03","DeepSleep":1689664120,"Wakeup":1689664143}} (retained) """

@attr.s(slots=True, frozen=True)
class TasmotaDeepSleepConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota Deepsleep configuation."""

    idx: int = attr.ib()
    command_topic: str = attr.ib()
    state_topic1: str = attr.ib()
    state_topic2: str = attr.ib()
    state_topic3: str = attr.ib()
    reporttime: str = attr.ib()
    startsleep: int = attr.ib()
    endsleep: int = attr.ib()

    @classmethod
    def from_discovery_message(
        cls, config: dict, idx: int, platform: str
    ) -> TasmotaDeepSleepConfig:
        """Instantiate from discovery message."""
        deepsleep_enabled = config[CONF_DEEPSLEEP]
        return cls(
            endpoint="deepsleep",
            idx=idx,
            friendly_name=f"{config[CONF_DEVICENAME]} {platform} {idx+1}",
            mac=config[CONF_MAC],
            platform=platform,
            poll_payload="10",
            poll_topic=get_topic_command_status(config),
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            command_topic=get_topic_command(config),
            state_topic1=get_topic_stat_result(config),
            state_topic2=get_topic_tele_sensor(config),
            state_topic3=get_topic_stat_status(config, 10),
"""  ??? Maybe we need some more here for sleep and wakeup time????"""            
        )

class TasmotaDeepSleep(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota DeepSleep device."""

    _cfg: TasmotaDeepSleepConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._sub_state: dict | None = None
        super().__init__(**kwds)

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""

        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT state messages."""
            if not self._on_state_callback:
                return
""" ?????
            shutter = f"{RSLT_SHUTTER}{self._cfg.idx+1}"
            prefix: list[str | int] = []
            if msg.topic == self._cfg.state_topic3:
                prefix = [STATUS_SENSOR]
"""
            deepsleeptime = get_value_by_path(
                msg.payload, prefix + [shutter, DEEPSLEEP_SLEEPTIME]
            )
            if direction is not None and self._cfg.inverted_shutter:
                direction = direction * -1

            wakeuptime = get_value_by_path(
                msg.payload, prefix + [shutter, DEEPSLEEP_WAKEUPTIME]
            )

        availability_topics = self.get_availability_topics()
        topics = {
            "state_topic1": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic1,
                "msg_callback": state_message_received,
            },
            "state_topic2": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic2,
                "msg_callback": state_message_received,
            },
            "state_topic3": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic3,
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

    @property
    def supports_deepsleep(self) -> bool:
        """Return if the deepsleep is supported."""
        return self._cfg.deepsleep_enabled != 0 
