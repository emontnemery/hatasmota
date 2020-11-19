"""Tasmota fan."""
import logging

import attr

from .const import (
    COMMAND_FANSPEED,
    CONF_DEVICENAME,
    CONF_MAC,
    FAN_SPEED_HIGH,
    FAN_SPEED_LOW,
    FAN_SPEED_MEDIUM,
    FAN_SPEED_OFF,
)
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .utils import (
    config_get_state_offline,
    config_get_state_online,
    get_topic_command,
    get_topic_command_state,
    get_topic_stat_result,
    get_topic_tele_state,
    get_topic_tele_will,
    get_value_by_path,
)

SUPPORTED_FAN_SPEEDS = [FAN_SPEED_OFF, FAN_SPEED_LOW, FAN_SPEED_MEDIUM, FAN_SPEED_HIGH]

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class TasmotaFanConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota fan configuation."""

    command_topic: str = attr.ib()
    result_topic: str = attr.ib()
    state_topic: str = attr.ib()

    @classmethod
    def from_discovery_message(cls, config, platform):
        """Instantiate from discovery message."""
        return cls(
            endpoint="fan",
            idx="ifan",
            friendly_name=config[CONF_DEVICENAME],
            mac=config[CONF_MAC],
            platform=platform,
            poll_payload="",
            poll_topic=get_topic_command_state(config),
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            command_topic=get_topic_command(config),
            result_topic=get_topic_stat_result(config),
            state_topic=get_topic_tele_state(config),
        )


class TasmotaFan(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota fan."""

    def __init__(self, **kwds):
        """Initialize."""
        self._sub_state = None
        self.light_type = None
        super().__init__(**kwds)

    async def subscribe_topics(self):
        """Subscribe to topics."""

        def state_message_received(msg):
            """Handle new MQTT state messages."""
            fanspeed = get_value_by_path(msg.payload, [COMMAND_FANSPEED])
            if fanspeed in SUPPORTED_FAN_SPEEDS:
                self._on_state_callback(fanspeed)

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

    async def unsubscribe_topics(self):
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    def set_speed(self, fanspeed):
        """Set the fan's speed."""
        payload = fanspeed
        command = COMMAND_FANSPEED
        self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )
