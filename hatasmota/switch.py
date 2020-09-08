"""Tasmota discovery."""
import logging

import attr

from hatasmota.const import CONF_ID
from hatasmota.entity import TasmotaAvailability, TasmotaAvailabilityConfig, TasmotaEntity, TasmotaEntityConfig
from hatasmota.utils import (
    get_config_friendlyname,
    get_state_power,
    get_topic_command_power,
    get_topic_tele_state,
    get_topic_tele_will,
    get_state_offline,
    get_state_online,
    get_state_power_off,
    get_state_power_on,
)

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class TasmotaRelayConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota relay configuation."""

    command_topic: str = attr.ib()
    state_power_off: str = attr.ib()
    state_power_on: str = attr.ib()
    state_topic: str = attr.ib()
    unique_id: str = attr.ib()

    @classmethod
    def from_discovery_message(cls, config, idx):
        """Instantiate from discovery message."""
        return cls(
            id=config[CONF_ID],
            idx=idx,
            friendly_name=get_config_friendlyname(config, idx),
            availability_topic=get_topic_tele_will(config),
            availability_offline=get_state_offline(config),
            availability_online=get_state_online(config),
            command_topic=get_topic_command_power(config, idx),
            state_power_off=get_state_power_off(config),
            state_power_on=get_state_power_on(config),
            state_topic=get_topic_tele_state(config),
            unique_id=f"{config[CONF_ID]}_switch_{idx}",
        )


class TasmotaRelay(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota relay."""

    def __init__(self, config):
        """Initialize."""
        self._on_state_callback = None
        self._publish_message = None
        self._sub_state = None
        self._subscribe_topics = None
        self._unsubscribe_topics = None
        super().__init__(config)

    def set_mqtt_callbacks(self, publish_message, subscribe_topics, unsubscribe_topics):
        """Set callbacks to publish MQTT messages and subscribe to MQTT topics."""
        self._publish_message = publish_message
        self._subscribe_topics = subscribe_topics
        self._unsubscribe_topics = unsubscribe_topics

    def set_on_state_callback(self, on_state_callback):
        """Set callback for state change."""
        self._on_state_callback = on_state_callback

    async def subscribe_topics(self):
        """Subscribe to topics."""

        def state_message_received(msg):
            """Handle new MQTT state messages."""
            state = get_state_power(msg.payload, self._cfg.idx)
            if state == self._cfg.state_power_on:
                self._on_state_callback(True)
            elif state == self._cfg.state_power_off:
                self._on_state_callback(False)

        availability_topics = self.get_availability_topics()
        topics = {
            "state_topic": {
                "topic": self._cfg.state_topic,
                "msg_callback": state_message_received,
            }
        }
        topics = {**topics, **availability_topics}

        self._sub_state = await self._subscribe_topics(
            self._sub_state,
            topics,
        )

    async def unsubscribe_topics(self):
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._unsubscribe_topics(self._sub_state)

    @property
    def unique_id(self):
        """Return unique_id."""
        return f"{self._cfg.id}_switch_{self._cfg.idx}"

    def set_state(self, state):
        """Turn the relay on or off."""
        payload = self._cfg.state_power_on if state else self._cfg.state_power_off
        self._publish_message(
            self._cfg.command_topic,
            payload,
        )
