"""Tasmota light."""
from __future__ import annotations

import colorsys
from dataclasses import dataclass
import logging
from typing import Any, cast

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
from .mqtt import ReceiveMessage, send_commands
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
    get_topic_sleep_state,
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


@dataclass(frozen=True, kw_only=True)
class TasmotaLightConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota light configuation."""

    idx: int

    dimmer_cmd: str
    dimmer_state: str
    color_suffix: str
    command_topic: str
    control_by_channel: bool
    fade_fixed_duration: bool
    light_type: int
    max_mireds: int
    min_mireds: int
    not_power_linked: bool
    poll_topic: str
    result_topic: str
    state_power_off: str
    state_power_on: str
    state_topic: str
    tuya: bool

    @classmethod
    def from_discovery_message(
        cls, config: dict, idx: int, platform: str
    ) -> TasmotaLightConfig:
        """Instantiate from discovery message."""
        color_suffix = ""
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
                color_suffix = "="
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
            sleep_state_topic=get_topic_sleep_state(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            dimmer_cmd=dimmer_cmd,
            dimmer_state=dimmer_state,
            color_suffix=color_suffix,
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

    _cfg: TasmotaLightConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._brightness = None
        self._color: list[float] | None = None
        self._color_temp: int | None = None
        self._state: bool | None = None
        self._sub_state: dict | None = None
        super().__init__(**kwds)

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""

        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT state messages."""
            if not self._on_state_callback:
                return

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

                    if (
                        color := get_value_by_path(msg.payload, [COMMAND_COLOR])
                    ) is not None:
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

                    if (
                        color_hsb := get_value_by_path(msg.payload, ["HSBColor"])
                    ) is not None:
                        color_hsb = color_hsb.split(",", 3)
                        if len(color_hsb) == 3:
                            color_hs = [float(color_hsb[0]), float(color_hsb[1])]
                            attributes["color_hs"] = color_hs

                    if (
                        color_temp := get_value_by_path(msg.payload, [COMMAND_CT])
                    ) is not None:
                        self._color_temp = color_temp
                        attributes["color_temp"] = color_temp

                    scheme = get_value_by_path(msg.payload, [COMMAND_SCHEME])
                    if scheme is not None and self.effect_list:
                        try:
                            attributes["effect"] = self.effect_list[scheme]
                        except IndexError:
                            attributes["effect"] = f"Scheme {scheme}"
                            _LOGGER.debug("Unknown scheme %s", scheme)

                    if (
                        white_value := get_value_by_path(msg.payload, [COMMAND_WHITE])
                    ) is not None:
                        attributes["white_value"] = white_value

            state = get_state_power(cast(str, msg.payload), idx)

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

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    @property
    def effect_list(self) -> list[str] | None:
        """Return effect list."""
        if self._cfg.endpoint == "light":
            return ["Solid", "Wake up", "Cycle up", "Cycle down", "Random"]
        return None

    @property
    def light_type(self) -> int:
        """Return light type."""
        if self._cfg.endpoint == "light":
            return self._cfg.light_type
        return LIGHT_TYPE_NONE

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return self._cfg.min_mireds

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return self._cfg.max_mireds

    async def set_state(self, state: bool, attributes: dict[str, Any]) -> None:
        """Turn the light on or off."""
        if self._cfg.endpoint == "relay":
            await self._set_state_relay(state)
        else:
            await self._set_state_light(state, attributes)

    @property
    def supports_transition(self) -> bool:
        """Return if the light supports transitions."""
        return self.light_type != LIGHT_TYPE_NONE and not self._cfg.tuya

    async def _set_state_relay(self, state: bool) -> None:
        """Turn the relay on or off."""
        payload = self._cfg.state_power_on if state else self._cfg.state_power_off
        command = f"{COMMAND_POWER}{self._cfg.idx+1}"
        await self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    async def _set_state_light(self, state: bool, attributes: dict[str, Any]) -> None:
        idx = self._cfg.idx

        commands: list[tuple[str, str | float]] = []
        transition = attributes.get("transition", 0)
        do_transition = transition > 0

        argument: str | float

        # Set fade
        if self.supports_transition and "transition" in attributes:
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
            argument = f"{color[0]},{color[1]},{color[2]}{self._cfg.color_suffix}"
            command = f"{COMMAND_COLOR}2"
            commands.append((command, argument))
        if "color_hs" in attributes:
            argument = round(attributes["color_hs"][0])
            command = "HsbColor1"  # Hue
            commands.append((command, argument))
            argument = round(attributes["color_hs"][1])
            command = "HsbColor2"  # Saturation
            commands.append((command, argument))
        if "color_temp" in attributes:
            argument = attributes["color_temp"]
            command = COMMAND_CT
            commands.append((command, argument))
        if "effect" in attributes and self.effect_list:
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

        await send_commands(self._mqtt_client, self._cfg.command_topic, commands)

    def _calculate_speed(self, state: bool, attributes: dict[str, Any]) -> float:
        # Calculate speed:
        # Home Assistant's transition is the transition time in seconds.
        # Tasmota's speed command is the number of half-seconds, scaled for a 100% fade
        # if fade_fixed_duration (SetOption117) is not set
        transition: int = attributes.get("transition", 0)

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
                if "color" in attributes:
                    new_color = attributes["color"]
                elif "color_hs" in attributes:
                    # Convert hs_color to color
                    color_hs = attributes["color_hs"]
                    rgb = colorsys.hsv_to_rgb(color_hs[0] / 360, color_hs[1] / 100, 1)
                    rgb = (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
                    new_color = rgb
                else:
                    new_color = self._color
                now_color = [x / 255 for x in self._color]
                new_color = [x / 255 for x in new_color]
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
        abs_changes = map(
            abs, [x1 - x2 for (x1, x2) in zip(now_channels, new_channels)]
        )
        # Mypy is confused about the map, override the inferred typing
        if (delta_ratio := max(abs_changes)) == 0:  # type:ignore[type-var]
            speed = 0
        else:
            speed = round(transition * 2 / delta_ratio)  # type:ignore[operator]
        return speed
