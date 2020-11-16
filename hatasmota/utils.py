"""Tasmota utility functions."""
import collections
import json
import logging
import operator
import re
from functools import reduce

from .const import (
    CONF_DEVICENAME,
    CONF_FRIENDLYNAME,
    CONF_FULLTOPIC,
    CONF_HOSTNAME,
    CONF_MAC,
    CONF_OFFLINE,
    CONF_ONLINE,
    CONF_PREFIX,
    CONF_STATE,
    CONF_SWITCHNAME,
    CONF_TOPIC,
    PREFIX_CMND,
    PREFIX_STAT,
    PREFIX_TELE,
    RSLT_ACTION,
    RSLT_POWER,
    RSLT_STATE,
    STATE_OFF,
    STATE_ON,
)

_LOGGER = logging.getLogger(__name__)


def get_by_path(root, items):
    """Access a nested object in root by item sequence."""
    return reduce(operator.getitem, items, root)


def set_by_path(root, items, value):
    """Set a value in a nested object in root by item sequence."""
    get_by_path(root, items[:-1])[items[-1]] = value


def del_by_path(root, items):
    """Delete a key-value in a nested object in root by item sequence."""
    del get_by_path(root, items[:-1])[items[-1]]


def _get_topic(config, prefix):
    topic = config[CONF_FULLTOPIC]
    topic = topic.replace("%hostname%", config[CONF_HOSTNAME])
    topic = topic.replace("%id%", config[CONF_MAC][-6:])
    topic = topic.replace("%prefix%", prefix)
    topic = topic.replace("%topic%", config[CONF_TOPIC])
    return topic


def _get_topic_cmnd(config):
    return _get_topic(config, config[CONF_PREFIX][PREFIX_CMND])


def _get_topic_stat(config):
    return _get_topic(config, config[CONF_PREFIX][PREFIX_STAT])


def _get_topic_tele(config):
    return _get_topic(config, config[CONF_PREFIX][PREFIX_TELE])


def get_topic_command(config):
    """Get command topic."""
    return _get_topic_cmnd(config)


def get_topic_command_state(config):
    """Get topic for command power."""
    return _get_topic_cmnd(config) + "STATE"


def get_topic_command_status(config):
    """Get topic for command power."""
    return _get_topic_cmnd(config) + "STATUS"


def get_topic_stat_button_trigger(config, idx):
    """Get topic for tele state."""
    return _get_topic_stat(config) + f"BUTTON{idx+1}"


def get_topic_stat_result(config):
    """Get topic for tele state."""
    return _get_topic_stat(config) + "RESULT"


def get_topic_stat_status(config, idx=None):
    """Get topic for tele state."""
    if idx is None:
        return _get_topic_stat(config) + "STATUS"
    return _get_topic_stat(config) + f"STATUS{idx}"


def get_topic_stat_switch(config, idx):
    """Get topic for tele state."""
    return _get_topic_stat(config) + f"SWITCH{idx+1}"


def get_topic_stat_switch_trigger(config, idx):
    """Get topic for tele state."""
    return _get_topic_stat(config) + f"SWITCH{idx+1}"


def get_topic_tele_sensor(config):
    """Get topic for tele state."""
    return _get_topic_tele(config) + "SENSOR"


def get_topic_tele_state(config):
    """Get topic for tele state."""
    return _get_topic_tele(config) + "STATE"


def get_topic_tele_will(config):
    """Get topic for tele will."""
    return _get_topic_tele(config) + "LWT"


def config_get_state_power_on(config):
    """Get command/result on."""
    return config[CONF_STATE][STATE_ON]


def config_get_state_power_off(config):
    """Get command/result off."""
    return config[CONF_STATE][STATE_OFF]


def config_get_state_offline(config):
    """Get state offline."""
    return config[CONF_OFFLINE]


def config_get_state_online(config):
    """Get state online."""
    return config[CONF_ONLINE]


def get_value(status, key, idx=None, idx_optional=False):
    """Get status from JSON formatted status or result."""
    try:
        status = json.loads(status)
    except json.decoder.JSONDecodeError:
        _LOGGER.debug("Invalid JSON '%s'", status)
        return None
    if idx is None:
        return status.get(key)
    if key in status and idx_optional and idx == 0:
        return status[key]
    key = f"{key}{idx+1}"
    return status[key] if key in status else None


def get_value_by_path(status, path):
    """Get status from JSON formatted status or result by path."""
    try:
        if not isinstance(status, collections.Mapping):
            status = json.loads(status)
        return get_by_path(status, path)
    except (json.decoder.JSONDecodeError, KeyError):
        return None


def get_state_power(status, idx):
    """Get state power."""
    return get_value(status, RSLT_POWER, idx=idx, idx_optional=True)


def get_state_state(status):
    """Get state of switch."""
    return get_value(status, RSLT_STATE)


def get_state_button_trigger(status):
    """Get state of button."""
    return get_value(status, RSLT_ACTION)


def config_get_friendlyname(config, platform, idx):
    """Get config friendly name."""
    friendly_names = config[CONF_FRIENDLYNAME]

    if idx >= len(friendly_names) or friendly_names[idx] is None:
        return f"{config[CONF_DEVICENAME]} {platform} {idx+1}"
    return friendly_names[idx]


def config_get_switchfriendlyname(config, platform, idx):
    """Get config friendly name."""
    switch_names = config[CONF_SWITCHNAME]

    if idx >= len(switch_names) or switch_names[idx] is None:
        return f"{config[CONF_DEVICENAME]} {platform} {idx+1}"
    return switch_names[idx]


def config_get_switchname(config, idx):
    """Get switch name."""
    switch_names = config[CONF_SWITCHNAME]

    if idx >= len(switch_names) or switch_names[idx] is None:
        return f"Switch{idx+1}"
    return switch_names[idx]


TOPIC_MATCHER = re.compile(r"^(?P<mac>[A-Z0-9_-]+)\/(?:config|sensors)$")


def discovery_topic_get_mac(topic, discovery_topic):
    """Get MAC from discovery topic."""
    topic_trimmed = topic.replace(f"{discovery_topic}/", "", 1)
    match = TOPIC_MATCHER.match(topic_trimmed)

    if not match:
        return None

    (mac,) = match.groups()
    return mac


def discovery_topic_is_device_config(topic):
    """Return True if the discovery topic is device configuration."""
    return topic.endswith("config")
