"""Tasmota discovery."""
import json
import logging

import voluptuous as vol

from . import config_validation as cv
from .button import TasmotaButtonTrigger, TasmotaButtonTriggerConfig
from .const import (
    CONF_BUTTON,
    CONF_DEVICENAME,
    CONF_FRIENDLYNAME,
    CONF_FULLTOPIC,
    CONF_HOSTNAME,
    CONF_IFAN,
    CONF_IP,
    CONF_LIGHT_SUBTYPE,
    CONF_LINK_RGB_CT,
    CONF_MAC,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_NAME,
    CONF_OFFLINE,
    CONF_ONLINE,
    CONF_OPTIONS,
    CONF_PREFIX,
    CONF_RELAY,
    CONF_SENSOR,
    CONF_STATE,
    CONF_SW_VERSION,
    CONF_SWITCH,
    CONF_SWITCHNAME,
    CONF_TOPIC,
    CONF_TUYA,
    CONF_VERSION,
    OPTION_BUTTON_SINGLE,
    OPTION_BUTTON_SWAP,
    OPTION_DECIMAL_TEXT,
    OPTION_HASS_LIGHT,
    OPTION_MQTT_BUTTONS,
    OPTION_MQTT_RESPONSE,
    OPTION_MQTT_SWITCHES,
    OPTION_NOT_POWER_LINKED,
    OPTION_PWM_MULTI_CHANNELS,
    OPTION_REDUCED_CT_RANGE,
    OPTION_SHUTTER_MODE,
    RL_LIGHT,
    RL_RELAY,
)
from .light import TasmotaLight, TasmotaLightConfig
from .relay import TasmotaRelay, TasmotaRelayConfig
from .sensor import TasmotaSensor, get_sensor_entities
from .status_sensor import TasmotaStatusSensor, TasmotaStatusSensorConfig
from .switch import (
    TasmotaSwitch,
    TasmotaSwitchConfig,
    TasmotaSwitchTrigger,
    TasmotaSwitchTriggerConfig,
)
from .utils import discovery_topic_get_mac, discovery_topic_is_device_config

TASMOTA_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            OPTION_MQTT_RESPONSE, default=0
        ): cv.bit,  # Added in Tasmota 9.0.0.4
        OPTION_BUTTON_SWAP: cv.bit,
        OPTION_BUTTON_SINGLE: cv.bit,
        OPTION_DECIMAL_TEXT: cv.bit,
        OPTION_NOT_POWER_LINKED: cv.bit,
        OPTION_HASS_LIGHT: cv.bit,
        OPTION_PWM_MULTI_CHANNELS: cv.bit,
        OPTION_MQTT_BUTTONS: cv.bit,
        vol.Optional(
            OPTION_SHUTTER_MODE, default=0
        ): cv.bit,  # Removed in Tasmota 9.0.0.3
        OPTION_REDUCED_CT_RANGE: cv.bit,
        vol.Optional(
            OPTION_MQTT_SWITCHES, default=0
        ): cv.bit,  # Added in Tasmota 9.0.0.4
    },
    required=True,
)

TASMOTA_DISCOVERY_SCHEMA = vol.Schema(
    {
        CONF_BUTTON: vol.All(cv.ensure_list, [cv.positive_int]),
        CONF_DEVICENAME: cv.string,
        CONF_FRIENDLYNAME: vol.All(cv.ensure_list, [cv.optional_string]),
        CONF_FULLTOPIC: cv.string,
        CONF_HOSTNAME: cv.string,
        vol.Optional(CONF_IFAN, default=0): cv.bit,  # Added in Tasmota 9.0.0.4
        CONF_IP: cv.string,
        CONF_LIGHT_SUBTYPE: cv.positive_int,
        CONF_LINK_RGB_CT: cv.bit,
        CONF_MAC: cv.string,
        CONF_MODEL: cv.string,
        CONF_OFFLINE: cv.string,
        CONF_ONLINE: cv.string,
        CONF_OPTIONS: TASMOTA_OPTIONS_SCHEMA,
        CONF_PREFIX: vol.All(cv.ensure_list, [cv.string]),
        CONF_STATE: vol.All(cv.ensure_list, [cv.string]),
        CONF_SW_VERSION: cv.string,
        CONF_SWITCH: vol.All(cv.ensure_list, [int]),
        vol.Optional(CONF_SWITCHNAME, default=[]): vol.All(
            cv.ensure_list, [cv.optional_string]
        ),  # Added in Tasmota 9.0.0.4
        CONF_RELAY: vol.All(cv.ensure_list, [cv.positive_int]),
        CONF_TOPIC: cv.string,
        CONF_TUYA: cv.bit,
        CONF_VERSION: 1,
    },
    required=True,
)

TASMOTA_SENSOR_DISCOVERY_SCHEMA = vol.Schema(
    {
        CONF_SENSOR: dict,
        CONF_VERSION: 1,
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
        self._devices = {}
        self._sensors = {}
        self._discovery_topic = discovery_topic
        self._mqtt_client = mqtt_client
        self._sub_state = None

    async def start_discovery(self, device_discovered, sensors_discovered):
        """Start receiving discovery messages."""
        await self._subscribe_discovery_topic(device_discovered, sensors_discovered)

    async def stop_discovery(self):
        """Stop receiving discovery messages."""
        self._sub_state = await self._mqtt_client.subscribe(self._sub_state, {})

    async def _subscribe_discovery_topic(self, device_discovered, sensors_discovered):
        """Subscribe to discovery messages."""

        async def discovery_message_received(msg):
            """Validate a received discovery message."""
            payload = msg.payload
            topic = msg.topic

            mac = discovery_topic_get_mac(topic, self._discovery_topic)
            if not mac:
                _LOGGER.warning("Invalid discovery topic %s:", topic)
                return

            device_discovery = discovery_topic_is_device_config(topic)

            if device_discovery:
                if payload:
                    try:
                        payload = TasmotaDiscoveryMsg(json.loads(payload))
                    except ValueError:
                        _LOGGER.warning(
                            "Invalid discovery message %s: '%s'", mac, payload
                        )
                        return
                    if mac != payload[CONF_MAC]:
                        _LOGGER.warning(
                            "MAC mismatch between topic and payload, '%s' != '%s'",
                            mac,
                            payload[CONF_MAC],
                        )
                        return
                    self._devices[mac] = payload
                else:
                    self._devices.pop(mac, None)
                    payload = {}

                await device_discovered(payload, mac)
                if mac in self._devices and mac in self._sensors:
                    sensors = get_sensor_entities(
                        self._sensors[mac], self._devices[mac]
                    )
                    sensors.extend(get_status_sensor_entities(self._devices[mac]))
                    if sensors_discovered:
                        await sensors_discovered(sensors, mac)
            else:
                if payload:
                    try:
                        payload = json.loads(payload)
                    except ValueError:
                        _LOGGER.warning(
                            "Invalid discovery message %s: '%s'", mac, payload
                        )
                        return
                    self._sensors[mac] = payload
                else:
                    self._sensors.pop(mac, None)
                    payload = {}

                if mac not in self._devices:
                    return

                sensors = []
                if payload:
                    sensors = get_sensor_entities(payload, self._devices[mac])
                    sensors.extend(get_status_sensor_entities(self._devices[mac]))
                if sensors_discovered:
                    await sensors_discovered(sensors, mac)

        topics = {
            "discovery_topic": {
                "topic": f"{self._discovery_topic}/#",
                "msg_callback": discovery_message_received,
            }
        }
        self._sub_state = await self._mqtt_client.subscribe(self._sub_state, topics)


def clear_discovery_topic(mac, discovery_prefix, mqtt_client):
    """Clear retained discovery topic."""
    mac = mac.replace(":", "")
    mac = mac.upper()
    device_discovery_topic = f"{discovery_prefix}/{mac}/config"
    mqtt_client.publish(device_discovery_topic, "", retain=True)
    sensor_discovery_topic = f"{discovery_prefix}/{mac}/sensors"
    mqtt_client.publish(sensor_discovery_topic, "", retain=True)


def get_device_config_helper(discovery_msg):
    """Generate device configuration."""
    if not discovery_msg:
        return {}

    device_config = {
        CONF_MAC: discovery_msg[CONF_MAC],
        CONF_MANUFACTURER: "Tasmota",
        CONF_MODEL: discovery_msg[CONF_MODEL],
        CONF_NAME: discovery_msg[CONF_DEVICENAME],
        CONF_SW_VERSION: discovery_msg[CONF_SW_VERSION],
    }
    return device_config


def get_device_config(discovery_msg):
    """Generate device configuration."""
    return get_device_config_helper(discovery_msg)


def get_binary_sensor_entities(discovery_msg):
    """Generate binary sensor configuration."""
    entities = []
    for (idx, value) in enumerate(discovery_msg[CONF_SWITCH]):
        entity = None
        discovery_hash = (discovery_msg[CONF_MAC], "binary_sensor", "switch", idx)
        if value:
            entity = TasmotaSwitchConfig.from_discovery_message(
                discovery_msg, idx, "binary_sensor"
            )
        entities.append((entity, discovery_hash))

    return entities


def get_switch_entities(discovery_msg):
    """Generate switch configuration."""
    switch_entities = []
    for (idx, value) in enumerate(discovery_msg[CONF_RELAY]):
        entity = None
        discovery_hash = (discovery_msg[CONF_MAC], "switch", "relay", idx)
        if value == RL_RELAY:
            entity = TasmotaRelayConfig.from_discovery_message(
                discovery_msg, idx, "switch"
            )
            if entity.is_light:
                entity = None
        switch_entities.append((entity, discovery_hash))

    return switch_entities


def get_light_entities(discovery_msg):
    """Generate light configuration."""
    light_entities = []

    for (idx, value) in enumerate(discovery_msg[CONF_RELAY]):
        entity = None
        discovery_hash = (discovery_msg[CONF_MAC], "light", "light", idx)
        if value == RL_LIGHT:
            entity = TasmotaLightConfig.from_discovery_message(
                discovery_msg, idx, "light"
            )
        light_entities.append((entity, discovery_hash))
    for (idx, value) in enumerate(discovery_msg[CONF_RELAY]):
        entity = None
        discovery_hash = (discovery_msg[CONF_MAC], "light", "relay", idx)
        if value == RL_RELAY:
            entity = TasmotaRelayConfig.from_discovery_message(
                discovery_msg, idx, "light"
            )
            if not entity.is_light:
                entity = None
        light_entities.append((entity, discovery_hash))

    return light_entities


def get_status_sensor_entities(discovery_msg):
    """Generate Status sensors."""
    status_sensor_entities = []

    entities = TasmotaStatusSensorConfig.from_discovery_message(
        discovery_msg, "status_sensor"
    )
    for entity in entities:
        discovery_hash = (
            discovery_msg[CONF_MAC],
            "status_sensor",
            "status_sensor",
            entity.sensor,
        )
        status_sensor_entities.append((entity, discovery_hash))

    return status_sensor_entities


def get_entities_for_platform(discovery_msg, platform):
    """Generate configuration for the given platform."""
    if platform == "binary_sensor":
        return get_binary_sensor_entities(discovery_msg)
    if platform == "light":
        return get_light_entities(discovery_msg)
    if platform == "sensor":
        return get_status_sensor_entities(discovery_msg)
    if platform == "switch":
        return get_switch_entities(discovery_msg)
    return []


def has_entities_with_platform(discovery_msg, platform):
    """Return True if any entity for given platform is enabled."""
    entities = get_entities_for_platform(discovery_msg, platform)
    return any(x is not None for (x, _) in entities)


def get_entity(config, mqtt_client, create_task):
    """Create entity for the given platform."""
    platform = config.platform
    if platform == "binary_sensor":
        return TasmotaSwitch(
            config=config, mqtt_client=mqtt_client, create_task=create_task
        )
    if platform == "light":
        return TasmotaLight(
            config=config, mqtt_client=mqtt_client, create_task=create_task
        )
    if platform == "sensor":
        return TasmotaSensor(
            config=config, mqtt_client=mqtt_client, create_task=create_task
        )
    if platform == "status_sensor":
        return TasmotaStatusSensor(
            config=config, mqtt_client=mqtt_client, create_task=create_task
        )
    if platform == "switch":
        return TasmotaRelay(
            config=config, mqtt_client=mqtt_client, create_task=create_task
        )
    return None


def get_button_triggers(discovery_msg):
    """Generate binary sensor configuration."""
    triggers = []
    for (idx, _) in enumerate(discovery_msg[CONF_BUTTON]):
        trigger = TasmotaButtonTriggerConfig.from_discovery_message(discovery_msg, idx)
        triggers.extend(trigger)

    return triggers


def get_switch_triggers(discovery_msg):
    """Generate binary sensor configuration."""
    triggers = []
    for (idx, _) in enumerate(discovery_msg[CONF_SWITCH]):
        trigger = TasmotaSwitchTriggerConfig.from_discovery_message(discovery_msg, idx)
        triggers.extend(trigger)

    return triggers


def get_triggers(discovery_msg):
    """Generate trigger configurations."""
    triggers = []
    if CONF_BUTTON in discovery_msg:
        triggers.extend(get_button_triggers(discovery_msg))
    if CONF_SWITCH in discovery_msg:
        triggers.extend(get_switch_triggers(discovery_msg))
    return triggers


def get_trigger(config, mqtt_client):
    """Create entity for the given platform."""
    if config.source == "button":
        return TasmotaButtonTrigger(config=config, mqtt_client=mqtt_client)
    if config.source == "switch":
        return TasmotaSwitchTrigger(config=config, mqtt_client=mqtt_client)
    return None


def unique_id_from_hash(discovery_hash):
    """Generate unique_id from discovery_hash."""
    return "_".join(discovery_hash[0:3] + (str(discovery_hash[3]),))
