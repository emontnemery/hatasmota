"""Tasmota discovery."""
import json
import logging

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
from hatasmota.switch import TasmotaRelay, TasmotaRelayConfig
from hatasmota.utils import (
    get_device_id,
    get_device_model,
    get_device_name,
    get_device_sw,
    get_serial_number_from_topic,
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


class TasmotaDiscovery:
    """Help class to store discovery status."""

    def __init__(self, discovery_topic, mqtt_client):
        """Initialize."""
        self._discovery_topic = discovery_topic
        self._mqtt_client = mqtt_client
        self._sub_state = None

    async def start_discovery(self, discovery_callback):
        """Start receiving discovery messages."""
        await self._subscribe_discovery_topic(discovery_callback)

    async def _subscribe_discovery_topic(self, discovery_callback):
        """Subscribe to discovery messages."""

        async def discovery_message_received(msg):
            """Validate a received discovery message."""
            payload = msg.payload
            topic = msg.topic

            serial_number = get_serial_number_from_topic(topic, self._discovery_topic)
            if not serial_number:
                _LOGGER.warning("Invalid discovery topic %s:", topic)
                return

            if payload:
                try:
                    payload = TasmotaDiscoveryMsg(json.loads(payload))
                except ValueError:
                    _LOGGER.warning(
                        "Invalid discovery message %s: '%s'", serial_number, payload
                    )
                    return
                if serial_number != payload[CONF_ID]:
                    _LOGGER.warning(
                        "Serial number mismatch between topic and payload, '%s' != '%s'",
                        serial_number,
                        payload[CONF_ID],
                    )
                    return
            else:
                payload = {}

            await discovery_callback(payload, serial_number)

        topics = {
            "state_topic": {
                "topic": f"{self._discovery_topic}/#",
                "msg_callback": discovery_message_received,
            }
        }
        self._sub_state = await self._mqtt_client.subscribe(self._sub_state, topics)


def clear_discovery_topic(serial_number, discovery_prefix, mqtt_client):
    """Clear retained discovery topic."""
    discovery_topic = f"{discovery_prefix}/{serial_number}/config"
    mqtt_client.publish(
        discovery_topic,
        "",
        retain=True,
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


def get_entity(config, platform, mqtt_client):
    """Create entity for the given platform."""
    if platform == CONF_RELAY:
        return TasmotaRelay(config=config, mqtt_client=mqtt_client)
    return None
