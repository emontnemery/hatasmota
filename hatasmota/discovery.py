"""Tasmota discovery."""
from __future__ import annotations

import json
import logging
from itertools import chain

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
    CONF_BATTERY,
    CONF_DEEPSLEEP,
    CONF_SHUTTER_OPTIONS,
    CONF_SHUTTER_TILT,
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
    OPTION_FADE_FIXED_DURATION,
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
    RL_SHUTTER,
)
from .entity import TasmotaEntity, TasmotaEntityConfig
from .fan import TasmotaFan, TasmotaFanConfig
from .light import TasmotaLight, TasmotaLightConfig
from .models import (
    DeviceDiscoveredCallback,
    DiscoveryHashType,
    SensorsDiscoveredCallback,
    TasmotaDeviceConfig,
)
from .mqtt import ReceiveMessage, TasmotaMQTTClient
from .relay import TasmotaRelay, TasmotaRelayConfig
from .sensor import TasmotaBaseSensorConfig, TasmotaSensor, get_sensor_entities
# from .deepsleep import TasmotaDeepSleep
from .shutter import TasmotaShutter, TasmotaShutterConfig
from .status_sensor import TasmotaStatusSensor, TasmotaStatusSensorConfig
from .switch import (
    TasmotaSwitch,
    TasmotaSwitchConfig,
    TasmotaSwitchTrigger,
    TasmotaSwitchTriggerConfig,
)
from .trigger import TasmotaTrigger, TasmotaTriggerConfig
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
        vol.Optional(
            OPTION_FADE_FIXED_DURATION, default=0
        ): cv.bit,  # Added in Tasmota 9.3.0
    },
    required=True,
    extra=vol.ALLOW_EXTRA,
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
        vol.Optional(CONF_BATTERY, default=0): cv.positive_int, # Added in Tasmota 13.0.0.3
        vol.Optional(CONF_DEEPSLEEP, default=0): cv.positive_int, # Added in Tasmota 13.0.0.3
        vol.Optional(CONF_SHUTTER_OPTIONS, default=[]): vol.All(
            cv.ensure_list, [cv.positive_int]
        ),  
        vol.Optional(CONF_SHUTTER_TILT, default=[]): vol.All(
            cv.ensure_list, [[int]]
        ),  # Added in Tasmota 11.x
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
    extra=vol.ALLOW_EXTRA,
)

TASMOTA_SENSOR_DISCOVERY_SCHEMA = vol.Schema(
    {
        CONF_SENSOR: dict,
        CONF_VERSION: 1,
    },
    required=True,
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


class TasmotaDiscoveryMsg(dict):
    """Dummy class to allow adding attributes."""

    def __init__(self, config: dict, validate: bool = True):
        """Validate config."""
        if validate:
            config = TASMOTA_DISCOVERY_SCHEMA(config)
        super().__init__(config)


class TasmotaDiscovery:
    """Help class to store discovery status."""

    def __init__(self, discovery_topic: str, mqtt_client: TasmotaMQTTClient):
        """Initialize."""
        self._devices: dict[str, dict] = {}
        self._sensors: dict[str, dict] = {}
        self._discovery_topic = discovery_topic
        self._mqtt_client = mqtt_client
        self._sub_state: dict | None = None

    async def start_discovery(
        self,
        device_discovered: DeviceDiscoveredCallback,
        sensors_discovered: SensorsDiscoveredCallback,
    ) -> None:
        """Start receiving discovery messages."""
        await self._subscribe_discovery_topic(device_discovered, sensors_discovered)

    async def stop_discovery(self) -> None:
        """Stop receiving discovery messages."""
        self._sub_state = await self._mqtt_client.subscribe(self._sub_state, {})

    async def _subscribe_discovery_topic(
        self,
        device_discovered: DeviceDiscoveredCallback,
        sensors_discovered: SensorsDiscoveredCallback,
    ) -> None:
        """Subscribe to discovery messages."""

        async def discovery_message_received(msg: ReceiveMessage) -> None:
            """Validate a received discovery message."""
            _payload = msg.payload
            payload: dict
            topic = msg.topic

            mac = discovery_topic_get_mac(topic, self._discovery_topic)
            if not mac:
                _LOGGER.warning("Invalid discovery topic %s:", topic)
                return

            device_discovery = discovery_topic_is_device_config(topic)

            if device_discovery:
                if _payload:
                    try:
                        payload = TasmotaDiscoveryMsg(json.loads(_payload))
                    except ValueError:
                        _LOGGER.warning(
                            "Invalid discovery message %s: '%s'", mac, _payload
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
                    if mac not in self._devices:
                        return

                    self._devices.pop(mac, None)
                    payload = {}

                await device_discovered(payload, mac)
                if mac in self._devices and mac in self._sensors:
                    sensors: list[tuple[TasmotaBaseSensorConfig, DiscoveryHashType]]
                    sensors = get_sensor_entities(
                        self._sensors[mac], self._devices[mac]
                    )
                    sensors.extend(get_status_sensor_entities(self._devices[mac]))
                    if sensors_discovered:
                        await sensors_discovered(sensors, mac)
            else:
                if _payload:
                    try:
                        payload = json.loads(_payload)
                    except ValueError:
                        _LOGGER.warning(
                            "Invalid discovery message %s: '%s'", mac, _payload
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

    async def clear_discovery_topic(self, mac: str, discovery_prefix: str) -> None:
        """Clear retained discovery topic."""
        mac = mac.replace(":", "")
        mac = mac.upper()
        device_discovery_topic = None
        sensor_discovery_topic = None
        if mac in self._devices:
            device_discovery_topic = f"{discovery_prefix}/{mac}/config"
            self._devices.pop(mac)
        if mac in self._sensors:
            sensor_discovery_topic = f"{discovery_prefix}/{mac}/sensors"
            self._sensors.pop(mac)
        if device_discovery_topic:
            await self._mqtt_client.publish(device_discovery_topic, "", retain=True)
        if sensor_discovery_topic:
            await self._mqtt_client.publish(sensor_discovery_topic, "", retain=True)


def get_device_config_helper(discovery_msg: dict) -> TasmotaDeviceConfig:
    """Generate device configuration."""
    if not discovery_msg:
        return {}

    device_config: TasmotaDeviceConfig = {
        CONF_IP: discovery_msg[CONF_IP],
        CONF_MAC: discovery_msg[CONF_MAC],
        CONF_MANUFACTURER: "Tasmota",
        CONF_MODEL: discovery_msg[CONF_MODEL],
        CONF_NAME: discovery_msg[CONF_DEVICENAME],
        CONF_SW_VERSION: discovery_msg[CONF_SW_VERSION],
    }
    return device_config


def get_device_config(discovery_msg: dict) -> TasmotaDeviceConfig:
    """Generate device configuration."""
    return get_device_config_helper(discovery_msg)


def get_binary_sensor_entities(
    discovery_msg: dict,
) -> list[tuple[TasmotaSwitchConfig | None, DiscoveryHashType]]:
    """Generate binary sensor configuration."""
    entities: list[tuple[TasmotaSwitchConfig | None, DiscoveryHashType]] = []
    for idx, value in enumerate(discovery_msg[CONF_SWITCH]):
        entity = None
        discovery_hash = (discovery_msg[CONF_MAC], "binary_sensor", "switch", idx)
        if value:
            entity = TasmotaSwitchConfig.from_discovery_message(
                discovery_msg, idx, "binary_sensor"
            )
        entities.append((entity, discovery_hash))

    return entities


def get_cover_entities(
    discovery_msg: dict,
) -> list[tuple[TasmotaShutterConfig | None, DiscoveryHashType]]:
    """Generate cover configuration."""
    relays = discovery_msg[CONF_RELAY]
    shutter_entities: list[tuple[TasmotaShutterConfig | None, DiscoveryHashType]] = []
    shutter_indices = []

    # Tasmota supports up to 4 shutters, each shutter is assigned two consecutive relays
    for idx, value in enumerate(chain(relays, [-1])):
        if idx - 1 in shutter_indices:
            # This is the 2nd half of a pair, skip
            continue

        if value == RL_SHUTTER:
            if relays[idx + 1] == RL_SHUTTER:
                shutter_indices.append(idx)
                _LOGGER.debug("Found shutter pair %s + %s", idx, idx + 1)
            else:
                # The 2nd half of the pair is missing, abort
                _LOGGER.error(
                    "Invalid shutter configuration, relay %s is shutter but %s is not",
                    idx + 1,
                    idx + 2,
                )
                shutter_indices = []
                break

    # pad / truncate the shutter index list to 4
    shutter_indices = shutter_indices[:4] + [-1] * (4 - len(shutter_indices))

    for idx, relay_idx in enumerate(shutter_indices):
        entity = None
        discovery_hash = (discovery_msg[CONF_MAC], "cover", "shutter", idx)
        if relay_idx != -1:
            entity = TasmotaShutterConfig.from_discovery_message(
                discovery_msg, idx, "cover"
            )
        shutter_entities.append((entity, discovery_hash))

    return shutter_entities


def get_fan_entities(
    discovery_msg: dict,
) -> list[tuple[TasmotaFanConfig | None, DiscoveryHashType]]:
    """Generate fan configuration."""
    fan_entities: list[tuple[TasmotaFanConfig | None, DiscoveryHashType]] = []

    entity = None
    discovery_hash = (discovery_msg[CONF_MAC], "fan", "fan", "ifan")
    if discovery_msg[CONF_IFAN]:
        entity = TasmotaFanConfig.from_discovery_message(discovery_msg, "fan")
    fan_entities.append((entity, discovery_hash))

    return fan_entities


def get_switch_entities(
    discovery_msg: dict,
) -> list[tuple[TasmotaRelayConfig | None, DiscoveryHashType]]:
    """Generate switch configuration."""
    force_light = discovery_msg[CONF_OPTIONS][OPTION_HASS_LIGHT] == 1
    switch_entities: list[tuple[TasmotaRelayConfig | None, DiscoveryHashType]] = []
    for idx, value in enumerate(discovery_msg[CONF_RELAY]):
        entity = None
        discovery_hash = (discovery_msg[CONF_MAC], "switch", "relay", idx)
        if value == RL_RELAY and not force_light:
            entity = TasmotaRelayConfig.from_discovery_message(
                discovery_msg, idx, "switch"
            )
        switch_entities.append((entity, discovery_hash))

    return switch_entities


def get_light_entities(
    discovery_msg: dict,
) -> list[tuple[TasmotaLightConfig | TasmotaRelayConfig | None, DiscoveryHashType]]:
    """Generate light configuration."""
    entity: TasmotaLightConfig | TasmotaRelayConfig | None
    force_light = discovery_msg[CONF_OPTIONS][OPTION_HASS_LIGHT] == 1
    light_entities: list[
        tuple[TasmotaLightConfig | TasmotaRelayConfig | None, DiscoveryHashType]
    ] = []
    relays = list(discovery_msg[CONF_RELAY])

    if discovery_msg[CONF_IFAN] and relays[0] == RL_LIGHT:
        # Special case for iFan: Single, non dimmable light
        relays[0] = RL_RELAY

    for idx, value in enumerate(relays):
        entity = None
        discovery_hash = (discovery_msg[CONF_MAC], "light", "light", idx)
        if value == RL_LIGHT:
            entity = TasmotaLightConfig.from_discovery_message(
                discovery_msg, idx, "light"
            )
        light_entities.append((entity, discovery_hash))
    for idx, value in enumerate(relays):
        entity = None
        discovery_hash = (discovery_msg[CONF_MAC], "light", "relay", idx)
        if value == RL_RELAY:
            if force_light or (discovery_msg[CONF_IFAN] and idx == 0):
                entity = TasmotaRelayConfig.from_discovery_message(
                    discovery_msg, idx, "light"
                )
        light_entities.append((entity, discovery_hash))

    return light_entities


def get_status_sensor_entities(
    discovery_msg: dict,
) -> list[tuple[TasmotaStatusSensorConfig, DiscoveryHashType]]:
    """Generate Status sensors."""
    status_sensor_entities: list[
        tuple[TasmotaStatusSensorConfig, DiscoveryHashType]
    ] = []

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


def get_entities_for_platform(
    discovery_msg: dict, platform: str
) -> list[tuple[TasmotaEntityConfig | None, DiscoveryHashType]]:
    """Generate configuration for the given platform."""
    entities: list[tuple[TasmotaEntityConfig | None, DiscoveryHashType]] = []
    if platform == "binary_sensor":
        entities.extend(get_binary_sensor_entities(discovery_msg))
    elif platform == "cover":
        entities.extend(get_cover_entities(discovery_msg))
    elif platform == "fan":
        entities.extend(get_fan_entities(discovery_msg))
    elif platform == "light":
        entities.extend(get_light_entities(discovery_msg))
    elif platform == "sensor":
        entities.extend(get_status_sensor_entities(discovery_msg))
    elif platform == "switch":
        entities.extend(get_switch_entities(discovery_msg))
    return entities


def has_entities_with_platform(discovery_msg: dict, platform: str) -> bool:
    """Return True if any entity for given platform is enabled."""
    entities = get_entities_for_platform(discovery_msg, platform)
    return any(x is not None for (x, _) in entities)


def get_entity(
    config: TasmotaEntityConfig, mqtt_client: TasmotaMQTTClient
) -> TasmotaEntity | None:
    """Create entity for the given platform."""
    platform = config.platform
    if platform == "binary_sensor":
        return TasmotaSwitch(config=config, mqtt_client=mqtt_client)
    if platform == "cover":
        return TasmotaShutter(config=config, mqtt_client=mqtt_client)
    if platform == "fan":
        return TasmotaFan(config=config, mqtt_client=mqtt_client)
    if platform == "light":
        return TasmotaLight(config=config, mqtt_client=mqtt_client)
    if platform == "sensor":
        return TasmotaSensor(config=config, mqtt_client=mqtt_client)
    if platform == "status_sensor":
        return TasmotaStatusSensor(config=config, mqtt_client=mqtt_client)
    if platform == "switch":
        return TasmotaRelay(config=config, mqtt_client=mqtt_client)
    return None


def get_button_triggers(discovery_msg: dict) -> list[TasmotaButtonTriggerConfig]:
    """Generate binary sensor configuration."""
    triggers = []
    for idx, _ in enumerate(discovery_msg[CONF_BUTTON]):
        trigger = TasmotaButtonTriggerConfig.from_discovery_message(discovery_msg, idx)
        triggers.extend(trigger)

    return triggers


def get_switch_triggers(discovery_msg: dict) -> list[TasmotaSwitchTriggerConfig]:
    """Generate binary sensor configuration."""
    triggers = []
    for idx, _ in enumerate(discovery_msg[CONF_SWITCH]):
        trigger = TasmotaSwitchTriggerConfig.from_discovery_message(discovery_msg, idx)
        triggers.extend(trigger)

    return triggers


def get_triggers(discovery_msg: dict) -> list[TasmotaTriggerConfig]:
    """Generate trigger configurations."""
    triggers: list[TasmotaTriggerConfig] = []
    if CONF_BUTTON in discovery_msg:
        triggers.extend(get_button_triggers(discovery_msg))
    if CONF_SWITCH in discovery_msg:
        triggers.extend(get_switch_triggers(discovery_msg))
    return triggers


def get_trigger(
    config: TasmotaTriggerConfig, mqtt_client: TasmotaMQTTClient
) -> TasmotaTrigger | None:
    """Create entity for the given platform."""
    if config.source == "button":
        return TasmotaButtonTrigger(config=config, mqtt_client=mqtt_client)
    if config.source == "switch":
        return TasmotaSwitchTrigger(config=config, mqtt_client=mqtt_client)
    return None


def unique_id_from_hash(discovery_hash: DiscoveryHashType) -> str:
    """Generate unique_id from discovery_hash."""
    return "_".join(discovery_hash[0:3] + (str(discovery_hash[3]),))
