"""Tasmota utility functions."""
from __future__ import annotations

import json
import logging
import operator
import re
from collections.abc import Mapping
from functools import reduce
from typing import Any, Dict, cast

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
from .mqtt import ReceivePayloadType

_LOGGER = logging.getLogger(__name__)

ConfigType = Dict[str, str]


def get_by_path(root: dict, items: list[str | int]) -> dict:
    """Access a nested object in root by item sequence."""
    return reduce(operator.getitem, items, root)


def set_by_path(root: dict, items: list[str | int], value: Any) -> None:
    """Set a value in a nested object in root by item sequence."""
    get_by_path(root, items[:-1])[items[-1]] = value


def del_by_path(root: dict, items: list[str | int]) -> None:
    """Delete a key-value in a nested object in root by item sequence."""
    del get_by_path(root, items[:-1])[items[-1]]


def _get_topic(config: ConfigType, prefix: str) -> str:
    topic = config[CONF_FULLTOPIC]
    topic = topic.replace("%hostname%", config[CONF_HOSTNAME])
    topic = topic.replace("%id%", config[CONF_MAC][-6:])
    topic = topic.replace("%prefix%", prefix)
    topic = topic.replace("%topic%", config[CONF_TOPIC])
    return topic


def _get_topic_cmnd(config: ConfigType) -> str:
    return _get_topic(config, config[CONF_PREFIX][PREFIX_CMND])


def _get_topic_stat(config: ConfigType) -> str:
    return _get_topic(config, config[CONF_PREFIX][PREFIX_STAT])


def _get_topic_tele(config: ConfigType) -> str:
    return _get_topic(config, config[CONF_PREFIX][PREFIX_TELE])


def get_topic_command(config: ConfigType) -> str:
    """Get command topic."""
    return _get_topic_cmnd(config)


def get_topic_command_state(config: ConfigType) -> str:
    """Get topic for command power."""
    return _get_topic_cmnd(config) + "STATE"


def get_topic_command_status(config: ConfigType) -> str:
    """Get topic for command power."""
    return _get_topic_cmnd(config) + "STATUS"


def get_topic_stat_button_trigger(config: ConfigType, idx: int) -> str:
    """Get topic for tele state."""
    return _get_topic_stat(config) + f"BUTTON{idx+1}"


def get_topic_stat_result(config: ConfigType) -> str:
    """Get topic for tele state."""
    return _get_topic_stat(config) + "RESULT"


def get_topic_stat_status(config: ConfigType, idx: int | None = None) -> str:
    """Get topic for tele state."""
    if idx is None:
        return _get_topic_stat(config) + "STATUS"
    return _get_topic_stat(config) + f"STATUS{idx}"


def get_topic_stat_switch(config: ConfigType, idx: int) -> str:
    """Get topic for tele state."""
    return _get_topic_stat(config) + f"SWITCH{idx+1}"


def get_topic_stat_switch_trigger(config: ConfigType, idx: int) -> str:
    """Get topic for tele state."""
    return _get_topic_stat(config) + f"SWITCH{idx+1}"


def get_topic_tele_sensor(config: ConfigType) -> str:
    """Get topic for tele state."""
    return _get_topic_tele(config) + "SENSOR"


def get_topic_tele_state(config: ConfigType) -> str:
    """Get topic for tele state."""
    return _get_topic_tele(config) + "STATE"


def get_topic_tele_will(config: ConfigType) -> str:
    """Get topic for tele will."""
    return _get_topic_tele(config) + "LWT"


def config_get_state_power_on(config: ConfigType) -> str:
    """Get command/result on."""
    return config[CONF_STATE][STATE_ON]


def config_get_state_power_off(config: ConfigType) -> str:
    """Get command/result off."""
    return config[CONF_STATE][STATE_OFF]


def config_get_state_offline(config: ConfigType) -> str:
    """Get state offline."""
    return config[CONF_OFFLINE]


def config_get_state_online(config: ConfigType) -> str:
    """Get state online."""
    return config[CONF_ONLINE]


def get_value(
    _status: str, key: str, idx: int | None = None, idx_optional: bool = False
) -> Any:
    """Get status from JSON formatted status or result."""
    try:
        status = json.loads(_status)
    except json.decoder.JSONDecodeError:
        _LOGGER.debug("Invalid JSON '%s'", _status)
        return None
    if idx is None:
        return status.get(key)
    if key in status and idx_optional and idx == 0:
        return status[key]
    key = f"{key}{idx+1}"
    return status[key] if key in status else None


def get_value_by_path(status: dict | ReceivePayloadType, path: list[str | int]) -> Any:
    """Get status from JSON formatted status or result by path."""
    try:
        if not isinstance(status, Mapping):
            status = json.loads(status)
        return get_by_path(cast(dict, status), path)
    except (json.decoder.JSONDecodeError, KeyError):
        return None


def get_state_power(status: str, idx: int) -> Any:
    """Get state power."""
    return get_value(status, RSLT_POWER, idx=idx, idx_optional=True)


def get_state_state(status: str) -> Any:
    """Get state of switch."""
    return get_value(status, RSLT_STATE)


def get_state_button_trigger(status: str) -> Any:
    """Get state of button."""
    return get_value(status, RSLT_ACTION)


def config_get_friendlyname(config: ConfigType, platform: str, idx: int) -> str:
    """Get config friendly name."""
    friendly_names = config[CONF_FRIENDLYNAME]

    if idx >= len(friendly_names) or friendly_names[idx] is None:
        return f"{config[CONF_DEVICENAME]} {platform} {idx+1}"
    return friendly_names[idx]


def config_get_switchfriendlyname(config: ConfigType, platform: str, idx: int) -> str:
    """Get config friendly name."""
    switch_names = config[CONF_SWITCHNAME]

    if idx >= len(switch_names) or switch_names[idx] is None:
        return f"{config[CONF_DEVICENAME]} {platform} {idx+1}"
    return switch_names[idx]


def config_get_switchname(config: ConfigType, idx: int) -> str:
    """Get switch name."""
    switch_names = config[CONF_SWITCHNAME]

    if idx >= len(switch_names) or switch_names[idx] is None:
        return f"Switch{idx+1}"
    return switch_names[idx]


TOPIC_MATCHER = re.compile(r"^(?P<mac>[A-Z0-9_-]+)\/(?:config|sensors)$")


def discovery_topic_get_mac(topic: str, discovery_topic: str) -> str | None:
    """Get MAC from discovery topic."""
    topic_trimmed = topic.replace(f"{discovery_topic}/", "", 1)
    match = TOPIC_MATCHER.match(topic_trimmed)

    if not match:
        return None

    (mac,) = match.groups()
    return mac


def discovery_topic_is_device_config(topic: str) -> bool:
    """Return True if the discovery topic is device configuration."""
    return topic.endswith("config")
