"""Tasmota camera."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from .const import (
    CONF_IP,
    CONF_MAC,
    CONF_DEEP_SLEEP,

    COMMAND_CAMERA_STREAM,
    COMMAND_CAMERA_FLIP_VERTICAL,
    COMMAND_CAMERA_FLIP_HORIZONTAL,
    COMMAND_CAMERA_RESOLUTION,
    COMMAND_CAMERA_BRIGHTNESS,
    COMMAND_CAMERA_CONTRAST,
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
    get_topic_command_state,
    get_topic_stat_result,
    get_topic_tele_state,
    get_topic_tele_sensor,
    get_topic_tele_will,
    get_value_by_path,
)

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class TasmotaCameraConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota camera configuation."""

    idx: int

    command_topic: str
    result_topic: str
    state_topic: str
    sensor_topic: str
    ip_address: str

    @classmethod
    def from_discovery_message(
        cls, config: dict, platform: str
    ) -> TasmotaCameraConfig:
        """Instantiate from discovery message."""
        return cls(
            endpoint="camera",
            idx=0,
            friendly_name=None,
            mac=config[CONF_MAC],
            platform=platform,
            poll_payload="",
            poll_topic=get_topic_command_state(config),
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            deep_sleep_enabled=config[CONF_DEEP_SLEEP],
            command_topic=get_topic_command(config),
            result_topic=get_topic_stat_result(config),
            state_topic=get_topic_tele_state(config),
            sensor_topic=get_topic_tele_sensor(config),
            ip_address=config[CONF_IP]
        )


class TasmotaCamera(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota camera."""

    _cfg: TasmotaCameraConfig

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

            if msg.topic == self._cfg.sensor_topic:
                state = get_value_by_path(msg.payload, ["CAMERA"])
                if state:
                    self._on_state_callback(state)


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
            "sensor_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.sensor_topic,
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

    def get_still_image_stream(self, websession:aiohttp.ClientSession) -> web.StreamResponse | None:
        """Get the io stream to read the static image."""
        still_image_url = f"http://{self._cfg.ip_address}/snapshot.jpg"
        return websession.get(still_image_url)

    def get_mjpeg_stream(self, websession:aiohttp.ClientSession) -> web.StreamResponse | None:
        """Get the io stream to read the mjpeg stream."""
        mjpeg_url = f"http://{self._cfg.ip_address}:81/cam.mjpeg"
        return websession.get(mjpeg_url)

