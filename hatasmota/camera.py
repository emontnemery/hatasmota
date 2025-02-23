"""Tasmota camera."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
import logging
from typing import Any

from aiohttp import ClientResponse, ClientSession

from .const import CONF_DEEP_SLEEP, CONF_IP, CONF_MAC
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .utils import (
    config_get_state_offline,
    config_get_state_online,
    get_topic_command_state,
    get_topic_tele_will,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TasmotaCameraConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota camera configuation."""

    ip_address: str

    @classmethod
    def from_discovery_message(cls, config: dict, platform: str) -> TasmotaCameraConfig:
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
            ip_address=config[CONF_IP],
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

        availability_topics = self.get_availability_topics()
        topics = {**availability_topics}

        self._sub_state = await self._mqtt_client.subscribe(
            self._sub_state,
            topics,
        )

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    def get_still_image_stream(
        self, websession: ClientSession
    ) -> Awaitable[ClientResponse]:
        """Get the io stream to read the static image."""
        still_image_url = f"http://{self._cfg.ip_address}/snapshot.jpg"
        return websession.get(still_image_url)

    def get_mjpeg_stream(self, websession: ClientSession) -> Awaitable[ClientResponse]:
        """Get the io stream to read the mjpeg stream."""
        mjpeg_url = f"http://{self._cfg.ip_address}:81/cam.mjpeg"
        return websession.get(mjpeg_url)
