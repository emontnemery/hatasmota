"""Tasmota light."""
import logging

import attr

from .const import (
    COMMAND_CHANNEL,
    COMMAND_COLOR,
    COMMAND_CT,
    COMMAND_DIMMER,
    COMMAND_FADE,
    COMMAND_POWER,
    COMMAND_SCHEME,
    COMMAND_SPEED,
    COMMAND_WHITE,
    CONF_LIGHT_SUBTYPE,
    CONF_LINK_RGB_CT,
    CONF_MAC,
    CONF_OPTIONS,
    CONF_RELAY,
    CONF_TUYA,
    LST_COLDWARM,
    LST_NONE,
    LST_RGB,
    LST_RGBCW,
    LST_RGBW,
    LST_SINGLE,
    OPTION_FADE_FIXED_DURATION,
    OPTION_NOT_POWER_LINKED,
    OPTION_PWM_MULTI_CHANNELS,
    OPTION_REDUCED_CT_RANGE,
    RL_LIGHT,
)
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .mqtt import send_commands
from .utils import (
    config_get_friendlyname,
    config_get_state_offline,
    config_get_state_online,
    config_get_state_power_off,
    config_get_state_power_on,
    get_state_power,
    get_topic_command,
    get_topic_command_state,
    get_topic_stat_result,
    get_topic_tele_state,
    get_topic_tele_will,
    get_value_by_path,
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

DEFAULT_MIN_MIREDS = 153
DEFAULT_MAX_MIREDS = 500
REDUCED_MIN_MIREDS = 200
REDUCED_MAX_MIREDS = 380

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class TasmotaLightConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota light configuation."""

    dimmer_cmd: str = attr.ib()
    dimmer_state: str = attr.ib()
    command_topic: str = attr.ib()
    control_by_channel: bool = attr.ib()
    fade_fixed_duration: bool = attr.ib()
    light_type: int = attr.ib()
    max_mireds: int = attr.ib()
    min_mireds: int = attr.ib()
    not_power_linked: bool = attr.ib()
    poll_topic: str = attr.ib()
    result_topic: str = attr.ib()
    state_power_off: str = attr.ib()
    state_power_on: str = attr.ib()
    state_topic: str = attr.ib()
    tuya: bool = attr.ib()

    @classmethod
    def from_discovery_message(cls, config, idx, platform):
        """Instantiate from discovery message."""
        dimmer_cmd = COMMAND_DIMMER
        dimmer_state = COMMAND_DIMMER
        control_by_channel = False  # Use Channel<n> command to control the light
        if config[CONF_TUYA]:
            dimmer_idx = 3  # Brightness controlled by DIMMER3
            dimmer_cmd = f"{COMMAND_DIMMER}{dimmer_idx}"
        tasmota_light_sub_type = config[CONF_LIGHT_SUBTYPE]
        light_type = LIGHT_TYPE_MAP[tasmota_light_sub_type]

        if config[CONF_OPTIONS][OPTION_PWM_MULTI_CHANNELS]:
            # Multi-channel PWM instead of a single light, each light controlled by CHANNEL<n>
            dimmer_state = f"{COMMAND_CHANNEL}{idx+1}"
            control_by_channel = True
            light_type = LIGHT_TYPE_DIMMER
        elif not config[CONF_LINK_RGB_CT] and tasmota_light_sub_type >= LST_RGBW:
            # Split light in RGB (idx==0) + White/CT (idx==1)
            first_light = config[CONF_RELAY].index(RL_LIGHT)
            if idx - first_light == 0:
                dimmer_idx = 1  # Brightness controlled by DIMMER1
                light_type = LIGHT_TYPE_RGB
            if idx - first_light == 1:
                dimmer_idx = 2  # Brightness controlled by DIMMER2
                if tasmota_light_sub_type == LST_RGBW:
                    light_type = LIGHT_TYPE_DIMMER
                else:
                    light_type = LIGHT_TYPE_COLDWARM
            dimmer_cmd = f"{COMMAND_DIMMER}{dimmer_idx}"
            dimmer_state = f"{COMMAND_DIMMER}{dimmer_idx}"

        min_mireds = DEFAULT_MIN_MIREDS
        max_mireds = DEFAULT_MAX_MIREDS
        if config[CONF_OPTIONS][OPTION_REDUCED_CT_RANGE]:
            min_mireds = REDUCED_MIN_MIREDS
            max_mireds = REDUCED_MAX_MIREDS

        return cls(
            endpoint="light",
            idx=idx,
            friendly_name=config_get_friendlyname(config, platform, idx),
            mac=config[CONF_MAC],
            platform=platform,
            poll_payload="",
            poll_topic=get_topic_command_state(config),
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            dimmer_cmd=dimmer_cmd,
            dimmer_state=dimmer_state,
            command_topic=get_topic_command(config),
            control_by_channel=control_by_channel,
            fade_fixed_duration=config[CONF_OPTIONS][OPTION_FADE_FIXED_DURATION],
            light_type=light_type,
            max_mireds=max_mireds,
            min_mireds=min_mireds,
            not_power_linked=config[CONF_OPTIONS][OPTION_NOT_POWER_LINKED],
            result_topic=get_topic_stat_result(config),
            state_power_off=config_get_state_power_off(config),
            state_power_on=config_get_state_power_on(config),
            state_topic=get_topic_tele_state(config),
            tuya=config[CONF_TUYA],
        )


class TasmotaLight(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota light."""

    def __init__(self, **kwds):
        """Initialize."""
        self._brightness = None
        self._color = None
        self._color_temp = None
        self._state = None
        self._sub_state = None
        super().__init__(**kwds)

    async def subscribe_topics(self):
        """Subscribe to topics."""

        def state_message_received(msg):
            """Handle new MQTT state messages."""
            attributes = {}
            idx = self._cfg.idx

            if self._cfg.endpoint == "light":
                if self._cfg.light_type != LIGHT_TYPE_NONE:

                    brightness = get_value_by_path(
                        msg.payload, [self._cfg.dimmer_state]
                    )
                    if brightness is not None:
                        self._brightness = brightness
                        attributes["brightness"] = brightness

                    color = get_value_by_path(msg.payload, [COMMAND_COLOR])
                    if color is not None:
                        if color.find(",") != -1:
                            color = color.split(",", 3)
                        else:
                            color = [
                                int(color[i : i + 2], 16)
                                for i in range(0, len(color), 2)
                            ]
                        if len(color) >= 3:
                            color = [float(color[0]), float(color[1]), float(color[2])]
                            self._color = color
                            attributes["color"] = color

                    color_temp = get_value_by_path(msg.payload, [COMMAND_CT])
                    if color_temp is not None:
                        self._color_temp = color_temp
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
                self._state = True
                self._on_state_callback(True, attributes=attributes)
            elif state == self._cfg.state_power_off:
                self._state = False
                self._on_state_callback(False, attributes=attributes)

        availability_topics = self.get_availability_topics()
        topics = {
            "result_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.result_topic,
                "msg_callback": state_message_received,
            },
            "state_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic,
                "msg_callback": state_message_received,
            },
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
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self._cfg.min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self._cfg.max_mireds

    def set_state(self, state, attributes):
        """Turn the light on or off."""
        if self._cfg.endpoint == "relay":
            self._set_state_relay(state)
        else:
            self._set_state_light(state, attributes)

    @property
    def supports_transition(self):
        """Return if the light supports transitions."""
        return self.light_type != LIGHT_TYPE_NONE and not self._cfg.tuya

    def _set_state_relay(self, state):
        """Turn the relay on or off."""
        payload = self._cfg.state_power_on if state else self._cfg.state_power_off
        command = f"{COMMAND_POWER}{self._cfg.idx+1}"
        self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    def _set_state_light(self, state, attributes):
        idx = self._cfg.idx

        commands = []
        transition = attributes.get("transition", 0)
        do_transition = transition > 0

        # Set fade
        if self.supports_transition:
            command = COMMAND_FADE
            argument = 1 if do_transition else 0
            commands.append((command, argument))

        if do_transition:
            speed = self._calculate_speed(state, attributes)

            # Clamp speed to the range 1..40
            speed = min(max(speed, 1), 40)
            command = COMMAND_SPEED
            commands.append((command, speed))

        argument = self._cfg.state_power_on if state else self._cfg.state_power_off
        command = f"{COMMAND_POWER}{idx+1}"
        if "brightness" in attributes:
            argument = attributes["brightness"]
            if self._cfg.control_by_channel:
                command = f"{COMMAND_CHANNEL}{idx+1}"
            else:
                command = self._cfg.dimmer_cmd

        commands.append((command, argument))

        if "color" in attributes:
            color = attributes["color"]
            argument = f"{color[0]},{color[1]},{color[2]}"
            command = f"{COMMAND_COLOR}2"
            commands.append((command, argument))
        if "color_temp" in attributes:
            argument = attributes["color_temp"]
            command = COMMAND_CT
            commands.append((command, argument))
        if "effect" in attributes:
            try:
                effect = attributes["effect"]
                argument = self.effect_list.index(effect)
                command = COMMAND_SCHEME
                commands.append((command, argument))
            except ValueError:
                _LOGGER.debug("Unknown effect %s", effect)
        if "white_value" in attributes:
            argument = attributes["white_value"]
            command = COMMAND_WHITE
            commands.append((command, argument))

        if self._cfg.not_power_linked and "brightness" in attributes:
            # Always send power
            argument = self._cfg.state_power_on if state else self._cfg.state_power_off
            command = f"{COMMAND_POWER}{idx+1}"
            commands.append((command, argument))

        send_commands(self._mqtt_client, self._cfg.command_topic, commands)

    def _calculate_speed(self, state, attributes):
        # Calculate speed:
        # Home Assistant's transition is the transition time in seconds.
        # Tasmota's speed command is the number of half-seconds, scaled for a 100% fade
        # if fade_fixed_duration (SetOption117) is not set
        transition = attributes.get("transition", 0)

        if self._cfg.fade_fixed_duration:
            # Fading at fixed duration
            return round(transition * 2)

        old_brightness = self._brightness if self._brightness is not None else 100
        now_brightness = old_brightness if self._state else 0

        new_brightness = attributes.get("brightness", old_brightness if state else 0)

        now_channels = []
        new_channels = []
        # Calculate normalized brightness for all channels
        if self.light_type >= LIGHT_TYPE_COLDWARM:
            if self.light_type >= LIGHT_TYPE_RGB and self._color:
                now_color = [x / 255 for x in self._color]
                new_color = [x / 255 for x in attributes.get("color", self._color)]
                now_channels.extend(now_color)
                new_channels.extend(new_color)
            if self.light_type >= LIGHT_TYPE_COLDWARM and self._color_temp:
                now_color_temp = self._color_temp
                new_color_temp = attributes.get("color_temp", self._color_temp)
                mired_range = self.max_mireds - self.min_mireds
                now_ct_ratio = (now_color_temp - self.min_mireds) / mired_range
                new_ct_ratio = (new_color_temp - self.min_mireds) / mired_range
                now_channels.append(now_ct_ratio)
                new_channels.append(new_ct_ratio)
            now_channels = [x * now_brightness / 100 for x in now_channels]
            new_channels = [x * new_brightness / 100 for x in new_channels]

        # 1-channel dimmer, or color / color_temp unknown
        if not new_channels:
            new_channels = [new_brightness / 100]
            now_channels = [now_brightness / 100]

        # Scale transition to the channel with the largest brightness change
        delta_ratio = max(
            map(abs, [x1 - x2 for (x1, x2) in zip(now_channels, new_channels)])
        )
        if delta_ratio == 0:
            speed = 0
        else:
            speed = round(transition * 2 / delta_ratio)
        return speed
