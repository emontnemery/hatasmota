"""Tasmota discovery."""
import logging

import attr
import voluptuous as vol

import hatasmota.config_validation as cv
from hatasmota.const import (
    CONF_DEVICENAME,
    CONF_FULLTOPIC,
    CONF_HOSTNAME,
    CONF_ID,
    CONF_LIGHT,
    CONF_FRIENDLYNAME,
    CONF_MANUFACTURER,
    CONF_NAME,
    CONF_OFFLINE,
    CONF_ONLINE,
    CONF_PREFIX,
    CONF_SENSOR,
    CONF_STATE,
    CONF_RELAY,
    CONF_TOPIC,
    CONF_VERSION,
    CONF_MODEL,
    CONF_SW_VERSION,
)
from hatasmota.utils import (
    get_config_friendlyname,
    get_device_id,
    get_device_model,
    get_device_name,
    get_device_sw,
    get_state_power,
    get_topic_command_power,
    get_topic_tele_state,
    get_topic_tele_will,
    get_state_offline,
    get_state_online,
    get_state_power_off,
    get_state_power_on,
)

TASMOTA_DISCOVERY_SCHEMA = vol.Schema(
    {
        CONF_DEVICENAME: cv.string,
        CONF_FRIENDLYNAME: vol.All(cv.ensure_list, [cv.string]),
        CONF_FULLTOPIC: cv.string,
        CONF_HOSTNAME: cv.string,
        CONF_ID: cv.string,
        CONF_LIGHT: vol.All(cv.ensure_list, [cv.positive_int]),
        CONF_MODEL: cv.string,
        CONF_OFFLINE: cv.string,
        CONF_ONLINE: cv.string,
        CONF_PREFIX: vol.All(cv.ensure_list, [cv.string]),
        CONF_SENSOR: vol.All(cv.ensure_list, [cv.positive_int]),
        CONF_STATE: vol.All(cv.ensure_list, [cv.string]),
        CONF_SW_VERSION: cv.string,
        CONF_RELAY: vol.All(cv.ensure_list, [cv.positive_int]),
        CONF_TOPIC: cv.string,
        CONF_VERSION: cv.positive_int,
    },
    required=True,
)

_LOGGER = logging.getLogger(__name__)


class TasmotaDiscoveryMsg(dict):
    """Dummy class to allow adding attributes."""

    def __init__(self, config, validate=True):
        """Validate config."""
        if validate:
            config = TASMOTA_DISCOVERY_SCHEMA(config)
        super().__init__(config)


@attr.s(slots=True, frozen=True)
class TasmotaEntityConfig:
    """Base class for Tasmota configuation."""

    id: str = attr.ib()
    idx: int = attr.ib()
    friendly_name: str = attr.ib()


@attr.s(slots=True, frozen=True)
class TasmotaAvailabilityConfig(TasmotaEntityConfig):
    """Tasmota availability configuation."""

    availability_topic: str = attr.ib()
    availability_offline: str = attr.ib()
    availability_online: str = attr.ib()


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


class TasmotaEntity:
    """Base class for Tasmota entities."""

    def __init__(self, config):
        """Initialize."""
        self._cfg = config
        super().__init__()

    def config_same(self, new_config):
        """Return if updated config is same as current config."""
        return self._cfg == new_config

    def config_update(self, new_config):
        """Update config."""
        self._cfg = new_config

    @property
    def device_id(self):
        """Return friendly name."""
        return self._cfg.id

    @property
    def name(self):
        """Return friendly name."""
        return self._cfg.friendly_name


class TasmotaAvailability(TasmotaEntity):
    """Availability mixin for Tasmota entities."""

    def __init__(self, config):
        """Initialize."""
        self._on_availability_callback = None
        super().__init__(config)

    def get_availability_topics(self):
        """Return MQTT topics to subscribe to for availability state."""

        def availability_message_received(msg):
            """Handle a new received MQTT availability message."""
            if msg.payload == self._cfg.availability_online:
                self._on_availability_callback(True)
            if msg.payload == self._cfg.availability_offline:
                self._on_availability_callback(False)

        topics = {
            "availability_topic": {
                "topic": self._cfg.availability_topic,
                "msg_callback": availability_message_received,
            }
        }
        return topics

    def set_on_availability_callback(self, on_availability_callback):
        """Set callback for availability state change."""
        self._on_availability_callback = on_availability_callback


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


def get_device_config_helper(discovery_msg):
    """Generate device configuration."""
    if not discovery_msg:
        return {}

    device_config = {
        CONF_ID: get_device_id(discovery_msg),
        CONF_MANUFACTURER: "Tasmota",
        CONF_MODEL: get_device_model(discovery_msg),
        CONF_NAME: get_device_name(discovery_msg),
        CONF_SW_VERSION: get_device_sw(discovery_msg),
    }
    return device_config


def get_device_config(discovery_msg):
    """Generate device configuration."""
    return get_device_config_helper(discovery_msg)


def has_entities_with_platform(discovery_msg, platform):
    """Return True if any entity for given platform is enabled."""
    return platform in discovery_msg and any(x != 0 for x in discovery_msg[platform])


def get_switch_entities(discovery_msg):
    """Generate switch configuration."""
    switch_entities = []
    for (idx, value) in enumerate(discovery_msg[CONF_RELAY]):
        entity = None
        if value:
            entity = TasmotaRelayConfig.from_discovery_message(discovery_msg, idx)
        switch_entities.append(entity)

    return switch_entities


def get_entities_for_platform(discovery_msg, platform):
    """Generate configuration for the given platform."""
    if platform in discovery_msg and platform == CONF_RELAY:
        return get_switch_entities(discovery_msg)
    return []


def get_entity(config, platform):
    """Create entity for the given platform."""
    if platform == CONF_RELAY:
        return TasmotaRelay(config)
    return None
