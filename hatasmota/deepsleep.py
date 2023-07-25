"""Tasmota deepsleep."""
from __future__ import annotations

import logging
from typing import Any

import attr

from .const import (
    CONF_DEEPSLEEP,
    CONF_DEEPSLEEP_REPORTTIME,
    CONF_DEEPSLEEP_SLEEPTIME,
    CONF_DEEPSLEEP_WAKEUPTIME,
)
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .mqtt import ReceiveMessage
from .utils import (
    config_get_state_offline,
    config_get_state_online,
    get_topic_command,
    get_topic_command_status,
    get_topic_stat_result,
    get_topic_stat_status,
    get_topic_tele_sensor,
    get_topic_tele_will,
    get_value_by_path,
)

_LOGGER = logging.getLogger(__name__)

# 07:08:40.513 MQT: hm/tele/ESP_3284D1/DEEPSLEEP = {"DeepSleep":{"Time":"2023-07-18T07:09:03","DeepSleep":1689664120,"Wakeup":1689664143}} (retained)

@attr.s(slots=True, frozen=True)
class TasmotaShutterConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota shutter configuation."""

    idx: int = attr.ib()
    command_topic: str = attr.ib()
    inverted_shutter: bool = attr.ib()
    state_topic1: str = attr.ib()
    state_topic2: str = attr.ib()
    state_topic3: str = attr.ib()
    tilt_min: int = attr.ib()
    tilt_max: int = attr.ib()
    tilt_dur: int = attr.ib()

    @classmethod
    def from_discovery_message(
        cls, config: dict, idx: int, platform: str
    ) -> TasmotaShutterConfig:
        """Instantiate from discovery message."""
        shutter_options = config[CONF_SHUTTER_OPTIONS]
        shutter_options = shutter_options[idx] if idx < len(shutter_options) else 0
        shutter_tilt = config[CONF_SHUTTER_TILT]
        shutter_tilt = shutter_tilt[idx] if idx < len(shutter_tilt) else [0, 0, 0]
        return cls(
            endpoint="shutter",
            idx=idx,
            friendly_name=f"{config[CONF_DEVICENAME]} {platform} {idx+1}",
            mac=config[CONF_MAC],
            platform=platform,
            poll_payload="10",
            poll_topic=get_topic_command_status(config),
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            command_topic=get_topic_command(config),
            inverted_shutter=shutter_options & SHUTTER_OPTION_INVERT,
            state_topic1=get_topic_stat_result(config),
            state_topic2=get_topic_tele_sensor(config),
            state_topic3=get_topic_stat_status(config, 10),
            tilt_min=shutter_tilt[0],
            tilt_max=shutter_tilt[1],
            tilt_dur=shutter_tilt[2],
        )


class TasmotaShutter(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota shutter."""

    _cfg: TasmotaShutterConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._sub_state: dict | None = None
        super().__init__(**kwds)

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""

        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT state messages."""
            if not self._on_state_callback:
                return

            shutter = f"{RSLT_SHUTTER}{self._cfg.idx+1}"
            prefix: list[str | int] = []
            if msg.topic == self._cfg.state_topic3:
                prefix = [STATUS_SENSOR]

            direction = get_value_by_path(
                msg.payload, prefix + [shutter, SHUTTER_DIRECTION]
            )
            if direction is not None and self._cfg.inverted_shutter:
                direction = direction * -1

            position = get_value_by_path(
                msg.payload, prefix + [shutter, SHUTTER_POSITION]
            )
            if position is not None and self._cfg.inverted_shutter:
                position = 100 - position

            tilt = get_value_by_path(msg.payload, prefix + [shutter, SHUTTER_TILT])
            ha_tilt = None
            if tilt is not None:
                ha_tilt_range = 100
                tasmota_tilt_range = self._cfg.tilt_max - self._cfg.tilt_min
                if tasmota_tilt_range:
                    ha_tilt = (
                        (tilt - self._cfg.tilt_min) * ha_tilt_range / tasmota_tilt_range
                    )

            if direction is not None or position is not None or ha_tilt is not None:
                self._on_state_callback(
                    None, direction=direction, position=position, tilt=ha_tilt
                )

        availability_topics = self.get_availability_topics()
        topics = {
            "state_topic1": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic1,
                "msg_callback": state_message_received,
            },
            "state_topic2": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic2,
                "msg_callback": state_message_received,
            },
            "state_topic3": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic3,
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

    async def open(self) -> None:
        """Open the shutter."""
        payload = ""
        command = f"{COMMAND_SHUTTER_OPEN}{self._cfg.idx+1}"
        await self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    async def close(self) -> None:
        """Close the shutter."""
        payload = ""
        command = f"{COMMAND_SHUTTER_CLOSE}{self._cfg.idx+1}"
        await self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    async def set_position(self, position: int) -> None:
        """Set the shutter's position.

        0 is closed, 100 is fully open.
        """
        if self._cfg.inverted_shutter:
            position = 100 - position
        payload = position
        command = f"{COMMAND_SHUTTER_POSITION}{self._cfg.idx+1}"
        await self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    async def stop(self) -> None:
        """Stop the shutter."""
        payload = ""
        command = f"{COMMAND_SHUTTER_STOP}{self._cfg.idx+1}"
        await self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    @property
    def supports_tilt(self) -> bool:
        """Return if the shutter supports tilt."""
        return self._cfg.tilt_dur != 0 and (self._cfg.tilt_min != self._cfg.tilt_max)

    async def open_tilt(self) -> None:
        """Open the shutter tilt."""
        payload = "OPEN"
        command = f"{COMMAND_SHUTTER_TILT}{self._cfg.idx+1}"
        await self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    async def close_tilt(self) -> None:
        """Close the shutter tilt."""
        payload = "CLOSE"
        command = f"{COMMAND_SHUTTER_TILT}{self._cfg.idx+1}"
        await self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )

    async def set_tilt_position(self, tilt: int) -> None:
        """Set the shutter's tilt position.

        0 is closed, 100 is fully open.
        """
        ha_tilt_range = 100
        tasmota_tilt_range = self._cfg.tilt_max - self._cfg.tilt_min
        tasmota_tilt = self._cfg.tilt_min + (tilt * tasmota_tilt_range / ha_tilt_range)
        payload = round(tasmota_tilt)
        command = f"{COMMAND_SHUTTER_TILT}{self._cfg.idx+1}"
        await self._mqtt_client.publish(
            self._cfg.command_topic + command,
            payload,
        )
