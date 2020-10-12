"""Tasmota switch."""
import logging

import attr

from .const import CONF_MAC, CONF_OPTIONS, OPTION_HASS_LIGHT
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .utils import (
    config_get_friendlyname,
    config_get_state_offline,
    config_get_state_online,
    config_get_state_power_off,
    config_get_state_power_on,
    get_state_power,
    get_topic_command_power,
    get_topic_command_state,
    get_topic_tele_state,
    get_topic_tele_will,
)

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class TasmotaRelayConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota relay configuation."""

    command_power_topic: str = attr.ib()
    is_light: bool = attr.ib()
    poll_topic = attr.ib()
    state_power_off: str = attr.ib()
    state_power_on: str = attr.ib()
    state_topic: str = attr.ib()

    @classmethod
    def from_discovery_message(cls, config, idx, platform):
        """Instantiate from discovery message."""
        return cls(
            endpoint="relay",
            idx=idx,
            friendly_name=config_get_friendlyname(config, platform, idx),
            mac=config[CONF_MAC],
            platform=platform,
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            command_power_topic=get_topic_command_power(config, idx),
            is_light=config[CONF_OPTIONS][OPTION_HASS_LIGHT] == 1,
            poll_topic=get_topic_command_state(config),
            state_power_off=config_get_state_power_off(config),
            state_power_on=config_get_state_power_on(config),
            state_topic=get_topic_tele_state(config),
        )


class TasmotaRelay(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota relay."""

    def __init__(self, **kwds):
        """Initialize."""
        self._on_state_callback = None
        self._sub_state = None
        self.light_type = None
        super().__init__(**kwds)

    def poll_status(self):
        """Poll for status."""
        payload = ""
        self._mqtt_client.publish_debounced(self._cfg.poll_topic, payload)

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
                "event_loop_safe": True,
                "topic": self._cfg.state_topic,
                "msg_callback": state_message_received,
            }
        }
        topics = {**topics, **availability_topics}

        self._sub_state = await self._mqtt_client.subscribe(
            self._sub_state,
            topics,
        )

    async def unsubscribe_topics(self):
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    def set_state(self, state):
        """Turn the relay on or off."""
        payload = self._cfg.state_power_on if state else self._cfg.state_power_off
        self._mqtt_client.publish(
            self._cfg.command_power_topic,
            payload,
        )
