"""Tasmota light."""
import logging

import attr

from hatasmota.const import (
    CONF_MAC,
    CONF_LIGHT_SUBTYPE,
    CONF_OPTIONS,
    OPTION_PWM_MULTI_CHANNELS,
    CONF_LINK_RGB_CT,
    LST_COLDWARM,
    LST_NONE,
    LST_RGB,
    LST_RGBCW,
    LST_RGBW,
    LST_SINGLE,
    COMMAND_COLOR,
    COMMAND_CT,
    COMMAND_SCHEME,
    COMMAND_WHITE,
)
from hatasmota.entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from hatasmota.utils import (
    config_get_friendlyname,
    get_state_power,
    get_topic_command_channel,
    get_topic_command_color,
    get_topic_command_color_temp,
    get_topic_command_dimmer,
    get_topic_command_effect,
    get_topic_command_power,
    get_topic_command_state,
    get_topic_command_white_value,
    get_topic_tele_state,
    get_topic_tele_will,
    get_value_by_path,
    config_get_state_offline,
    config_get_state_online,
    config_get_state_power_off,
    config_get_state_power_on,
)

LIGHT_TYPE_NONE = 0
LIGHT_TYPE_DIMMER = 1
LIGHT_TYPE_COLDWARM = 2
LIGHT_TYPE_RGB = 3
LIGHT_TYPE_RGBW = 4
LIGHT_TYPE_RGBCW = 5

LIGHT_TYPE_MAP = {
    LIGHT_TYPE_NONE: LST_NONE,
    LIGHT_TYPE_DIMMER: LST_SINGLE,
    LIGHT_TYPE_COLDWARM: LST_COLDWARM,
    LIGHT_TYPE_RGB: LST_RGB,
    LIGHT_TYPE_RGBW: LST_RGBW,
    LIGHT_TYPE_RGBCW: LST_RGBCW,
}

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class TasmotaLightConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota relay configuation."""

    brightness_path: str = attr.ib()
    command_channel_topic: str = attr.ib()
    command_color_topic: str = attr.ib()
    command_color_temp_topic: str = attr.ib()
    command_dimmer_topic: str = attr.ib()
    command_effect_topic: str = attr.ib()
    command_power_topic: str = attr.ib()
    command_white_value_topic: str = attr.ib()
    control_by_channel: bool = attr.ib()
    dimmer_idx: int = attr.ib()
    light_type: int = attr.ib()
    poll_topic: str = attr.ib()
    power_offset: int = attr.ib()
    state_power_off: str = attr.ib()
    state_power_on: str = attr.ib()
    state_topic: str = attr.ib()

    @classmethod
    def from_discovery_message(cls, config, idx, power_offset, platform):
        """Instantiate from discovery message."""
        brightness_path = ["Dimmer"]
        control_by_channel = False  # Use Channel<n> command to control the light
        dimmer_idx = 0  # Use Dimmer<n> to control brightness
        tasmota_light_sub_type = config[CONF_LIGHT_SUBTYPE]
        light_type = LIGHT_TYPE_MAP[tasmota_light_sub_type]

        if config[CONF_OPTIONS][OPTION_PWM_MULTI_CHANNELS]:
            # Multi-channel PWM instead of a single light, each light controlled by CHANNEL<n>
            brightness_path = [f"Channel{idx+power_offset+1}"]
            control_by_channel = True
            light_type = LIGHT_TYPE_DIMMER
        elif not config[CONF_LINK_RGB_CT] and tasmota_light_sub_type >= LST_RGBW:
            # Split light in RGB (idx==0) + White/CT (idx==1)
            if idx == 0:
                dimmer_idx = 1  # Brightness controlled by DIMMER2
                light_type = LIGHT_TYPE_RGB
            if idx == 1:
                dimmer_idx = 2  # Brightness controlled by DIMMER2
                if tasmota_light_sub_type == LST_RGBW:
                    light_type = LIGHT_TYPE_DIMMER
                else:
                    light_type = LIGHT_TYPE_COLDWARM
            brightness_path = [f"Dimmer{dimmer_idx}"]

        return cls(
            endpoint="light",
            idx=idx,
            friendly_name=config_get_friendlyname(config, platform, idx + power_offset),
            mac=config[CONF_MAC],
            platform=platform,
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            brightness_path=brightness_path,
            command_channel_topic=get_topic_command_channel(config, idx + power_offset),
            command_color_topic=get_topic_command_color(config),
            command_color_temp_topic=get_topic_command_color_temp(config),
            command_dimmer_topic=get_topic_command_dimmer(config, dimmer_idx),
            command_effect_topic=get_topic_command_effect(config),
            command_power_topic=get_topic_command_power(config, idx + power_offset),
            command_white_value_topic=get_topic_command_white_value(config),
            control_by_channel=control_by_channel,
            dimmer_idx=dimmer_idx,
            light_type=light_type,
            poll_topic=get_topic_command_state(config),
            power_offset=power_offset,
            state_power_off=config_get_state_power_off(config),
            state_power_on=config_get_state_power_on(config),
            state_topic=get_topic_tele_state(config),
        )


class TasmotaLight(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota light."""

    def __init__(self, **kwds):
        """Initialize."""
        self._on_state_callback = None
        self._sub_state = None
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
            attributes = {}
            idx = self._cfg.idx

            if self._cfg.endpoint == "light":
                idx = idx + self._cfg.power_offset
                if self._cfg.light_type != LIGHT_TYPE_NONE:

                    brightness = get_value_by_path(
                        msg.payload, self._cfg.brightness_path
                    )
                    if brightness is not None:
                        attributes["brightness"] = brightness

                    color = get_value_by_path(msg.payload, [COMMAND_COLOR])
                    if color is not None:
                        color = color.split(",", 3)
                        color = [float(color[0]), float(color[1]), float(color[2])]
                        attributes["color"] = color

                    color_temp = get_value_by_path(msg.payload, [COMMAND_CT])
                    if color_temp is not None:
                        attributes["color_temp"] = color_temp

                    scheme = get_value_by_path(msg.payload, [COMMAND_SCHEME])
                    if scheme is not None:
                        try:
                            attributes["effect"] = self.effect_list[scheme]
                        except IndexError:
                            attributes["effect"] = f"Scheme {scheme}"
                            _LOGGER.debug("Unknown scheme %s", scheme)

                    white_value = get_value_by_path(msg.payload, [COMMAND_WHITE])
                    if white_value is not None:
                        attributes["white_value"] = white_value

            state = get_state_power(msg.payload, idx)

            if state == self._cfg.state_power_on:
                self._on_state_callback(True, attributes=attributes)
            elif state == self._cfg.state_power_off:
                self._on_state_callback(False, attributes=attributes)

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

    @property
    def effect_list(self):
        """Return effect list."""
        if self._cfg.endpoint == "light":
            return ["None", "Wake up", "Cycle up", "Cycle down", "Random"]
        return None

    @property
    def light_type(self):
        """Return light type."""
        if self._cfg.endpoint == "light":
            return self._cfg.light_type
        return LIGHT_TYPE_NONE

    @property
    def unique_id(self):
        """Return unique_id."""
        return self._cfg.unique_id

    def set_state(self, state, attributes):
        """Turn the relay on or off."""
        argument = self._cfg.state_power_on if state else self._cfg.state_power_off
        command = self._cfg.command_power_topic
        if "brightness" in attributes:
            argument = attributes["brightness"]
            if self._cfg.control_by_channel:
                command = self._cfg.command_channel_topic
            else:
                command = self._cfg.command_dimmer_topic
        self._mqtt_client.publish(
            command,
            argument,
        )
        if "color" in attributes:
            color = attributes["color"]
            argument = f"{color[0]},{color[1]},{color[2]}"
            command = self._cfg.command_color_topic
            self._mqtt_client.publish(
                command,
                argument,
            )
        if "color_temp" in attributes:
            argument = attributes["color_temp"]
            command = self._cfg.command_color_temp_topic
            self._mqtt_client.publish(
                command,
                argument,
            )
        if "effect" in attributes:
            try:
                effect = attributes["effect"]
                argument = self.effect_list.index(effect)
                command = self._cfg.command_effect_topic
                self._mqtt_client.publish(
                    command,
                    argument,
                )
            except ValueError:
                _LOGGER.debug("Unknown effect %s", effect)
        if "white_value" in attributes:
            argument = attributes["white_value"]
            command = self._cfg.command_white_value_topic
            self._mqtt_client.publish(
                command,
                argument,
            )
