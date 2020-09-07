"""Tasmota utility functions."""

import json
import logging
import re

from hatasmota.const import (
    CONF_FRIENDLYNAME,
    CONF_FULLTOPIC,
    CONF_HOSTNAME,
    CONF_ID,
    CONF_PREFIX,
    CONF_STATE,
    CONF_TOPIC,
    PREFIX_CMND,
    PREFIX_STAT,
    PREFIX_TELE,
    STATE_OFF,
    STATE_ON,
    CONF_ONLINE,
    CONF_OFFLINE,
    RSLT_POWER,
    CONF_MODEL,
    CONF_DEVICENAME,
    CONF_SW_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def _get_topic(config, prefix):
    topic = config[CONF_FULLTOPIC]
    topic = topic.replace("%hostname%", config[CONF_HOSTNAME])
    topic = topic.replace("%id%", config[CONF_ID])
    topic = topic.replace("%prefix%", prefix)
    topic = topic.replace("%topic%", config[CONF_TOPIC])
    return topic


def _get_topic_cmnd(config):
    return _get_topic(config, config[CONF_PREFIX][PREFIX_CMND])


def _get_topic_stat(config):
    return _get_topic(config, config[CONF_PREFIX][PREFIX_STAT])


def _get_topic_tele(config):
    return _get_topic(config, config[CONF_PREFIX][PREFIX_TELE])


def get_topic_command_power(config, idx):
    """Get topic for command power."""
    return _get_topic_cmnd(config) + f"POWER{idx+1}"


def get_topic_tele_state(config):
    """Get topic for tele state."""
    return _get_topic_tele(config) + "STATE"


def get_topic_tele_will(config):
    """Get topic for tele will."""
    return _get_topic_tele(config) + "LWT"


def get_state_power_on(config):
    """Get command/result on."""
    return config[CONF_STATE][STATE_ON]


def get_state_power_off(config):
    """Get command/result off."""
    return config[CONF_STATE][STATE_OFF]


def get_state_offline(config):
    """Get state offline."""
    return config[CONF_OFFLINE]


def get_state_online(config):
    """Get state online."""
    return config[CONF_ONLINE]


def get_state_power(status, idx):
    """Get state power."""
    try:
        status = json.loads(status)
    except json.decoder.JSONDecodeError:
        _LOGGER.info("Invalid JSON '%s'", status)
        return None
    if idx == 0 and RSLT_POWER in status:
        return status[RSLT_POWER]
    powerdevice = f"{RSLT_POWER}{idx+1}"
    return status[powerdevice] if powerdevice in status else None


def get_config_friendlyname(config, idx):
    """Get config friendly name."""
    if idx >= len(config[CONF_FRIENDLYNAME]):
        return f"{config[CONF_FRIENDLYNAME][0]} {idx}"
    return config[CONF_FRIENDLYNAME][idx]


def get_device_id(config):
    """Get device ID."""
    return config[CONF_ID]


def get_device_model(config):
    """Get device name."""
    return config[CONF_MODEL]


def get_device_name(config):
    """Get device name."""
    return config[CONF_DEVICENAME]


def get_device_sw(config):
    """Get device SW version."""
    return config[CONF_SW_VERSION]


TOPIC_MATCHER = re.compile(r"^(?P<serial_number>[A-Z0-9_-]+)\/config$")


def get_serial_number_from_discovery_topic(topic, discovery_topic):
    """Get serial number from discovery topic."""
    topic_trimmed = topic.replace(f"{discovery_topic}/", "", 1)
    match = TOPIC_MATCHER.match(topic_trimmed)

    if not match:
        return None

    (serial_number,) = match.groups()
    return serial_number
