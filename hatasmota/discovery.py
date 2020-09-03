"""Tasmota discovery."""
import voluptuous as vol

import hatasmota.config_validation as cv
from hatasmota.const import (
    CONF_AVAILABILITY_TOPIC,
    CONF_DEVICE_ID,
    CONF_COMMAND_TOPIC,
    CONF_STATE_POWER_OFF,
    CONF_STATE_POWER_ON,
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
    CONF_QOS,
    CONF_RETAIN,
    CONF_SENSOR,
    CONF_STATE,
    CONF_RELAY,
    CONF_TOPIC,
    CONF_VERSION,
    CONF_MODEL,
    CONF_SW_VERSION,
    CONF_UNIQUE_ID,
    CONF_STATE_TOPIC,
)
from hatasmota.utils import (
    get_config_friendlyname,
    get_device_id,
    get_device_model,
    get_device_name,
    get_device_sw,
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


class TasmotaDiscoveryMsg(dict):
    """Dummy class to allow adding attributes."""

    def __init__(self, config, validate=True):
        """Validate config."""
        if validate:
            config = TASMOTA_DISCOVERY_SCHEMA(config)
        super().__init__(config)


def get_device_config(discovery_msg):
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


def has_entities_with_platform(discovery_msg, platform):
    """Return True if any entity for given platform is enabled."""
    return platform in discovery_msg and any(x != 0 for x in discovery_msg[platform])


def get_switch_entities(discovery_msg):
    """Generate switch configuration."""
    switch_entities = []
    for (idx, value) in enumerate(discovery_msg[CONF_RELAY]):
        availability_topic = get_topic_tele_will(discovery_msg)
        offline = get_state_offline(discovery_msg)
        online = get_state_online(discovery_msg)
        command_topic = get_topic_command_power(discovery_msg, idx)
        friendly_name = get_config_friendlyname(discovery_msg, idx)
        state_power_off = get_state_power_off(discovery_msg)
        state_power_on = get_state_power_on(discovery_msg)
        state_topic = get_topic_tele_state(discovery_msg)
        unique_id = f"{discovery_msg[CONF_ID]}_switch_{idx}"
        entity_config = {}
        if value:
            entity_config[CONF_AVAILABILITY_TOPIC] = availability_topic
            entity_config[CONF_DEVICE_ID] = discovery_msg[CONF_ID]
            entity_config[CONF_OFFLINE] = offline
            entity_config[CONF_ONLINE] = online
            entity_config[CONF_COMMAND_TOPIC] = command_topic
            entity_config[CONF_NAME] = friendly_name
            entity_config[CONF_QOS] = 0
            entity_config[CONF_RETAIN] = False
            entity_config[CONF_STATE_POWER_OFF] = state_power_off
            entity_config[CONF_STATE_POWER_ON] = state_power_on
            entity_config[CONF_STATE_TOPIC] = state_topic
            entity_config[CONF_UNIQUE_ID] = unique_id
        switch_entities.append(entity_config)

    return switch_entities


def get_entities_for_platform(discovery_msg, platform):
    """Generate configuration for the given platform."""
    if platform in discovery_msg and platform == CONF_RELAY:
        return get_switch_entities(discovery_msg)
    return []
