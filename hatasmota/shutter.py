"""Tasmota shutter."""
import logging

import attr

from .const import (
    COMMAND_SHUTTER_CLOSE,
    COMMAND_SHUTTER_OPEN,
    COMMAND_SHUTTER_POSITION,
    COMMAND_SHUTTER_STOP,
    CONF_DEVICENAME,
    CONF_MAC,
    CONF_SHUTTER_OPTIONS,
    RSLT_SHUTTER,
    SHUTTER_DIRECTION,
    SHUTTER_OPTION_INVERT,
    SHUTTER_POSITION,
    STATUS_SENSOR,
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
    get_topic_command_status,
    get_topic_stat_result,
    get_topic_stat_status,
    get_topic_tele_sensor,
    get_topic_tele_will,
    get_value_by_path,
)

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class TasmotaShutterConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota shutter configuation."""

    command_topic: str = attr.ib()
    inverted_shutter = attr.ib()
    state_topic1: str = attr.ib()
    state_topic2: str = attr.ib()
    state_topic3: str = attr.ib()

    @classmethod
    def from_discovery_message(cls, config, idx, platform):
        """Instantiate from discovery message."""
        shutter_options = config[CONF_SHUTTER_OPTIONS]
        shutter_options = shutter_options[idx] if idx < len(shutter_options) else 0
        return cls(
            endpoint="shutter",
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
            inverted_shutter=shutter_options & SHUTTER_OPTION_INVERT,
            state_topic1=get_topic_stat_result(config),
            state_topic2=get_topic_tele_sensor(config),
            state_topic3=get_topic_stat_status(config, 10),
        )


class TasmotaShutter(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota shutter."""

    def __init__(self, **kwds):
        """Initialize."""
        self._sub_state = None
        self.light_type = None
        super().__init__(**kwds)

    async def subscribe_topics(self):
        """Subscribe to topics."""

        def state_message_received(msg):
            """Handle new MQTT state messages."""
            shutter = f"{RSLT_SHUTTER}{self._cfg.idx+1}"
            prefix = []
            if msg.topic == self._cfg.state_topic3:
                prefix = [STATUS_SENSOR]

            direction = get_value_by_path(
                msg.payload, prefix + [shutter, SHUTTER_DIRECTION]
            )
            if direction is not None and self._cfg.inverted_shutter:
                direction = direction * -1

            position = get_value_by_path(
                msg.payload, prefix + [shutter, SHUTTER_POSITION]
            )
            if position is not None and self._cfg.inverted_shutter:
                position = 100 - position

            if direction is not None or position is not None:
                self._on_state_callback(None, direction=direction, position=position)

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

    async def unsubscribe_topics(self):
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    def open(self):
        """Open the shutter."""
        payload = ""
        command = f"{COMMAND_SHUTTER_OPEN}{self._cfg.idx+1}"
        self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    def close(self):
        """Close the shutter."""
        payload = ""
        command = f"{COMMAND_SHUTTER_CLOSE}{self._cfg.idx+1}"
        self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    def set_position(self, position):
        """Set the shutter's position.

        0 is closed, 100 is fully open.
        """
        if self._cfg.inverted_shutter:
            position = 100 - position
        payload = position
        command = f"{COMMAND_SHUTTER_POSITION}{self._cfg.idx+1}"
        self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    def stop(self):
        """Stop the shutter."""
        payload = ""
        command = f"{COMMAND_SHUTTER_STOP}{self._cfg.idx+1}"
        self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )
