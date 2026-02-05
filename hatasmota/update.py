"""Tasmota update."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from .const import COMMAND_BACKLOG, COMMAND_UPGRADE, CONF_DEEP_SLEEP, CONF_MAC
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
    get_topic_stat_status,
    get_topic_tele_state,
    get_topic_tele_will,
    get_value_by_path,
)

_LOGGER = logging.getLogger(__name__)

VERSION_VARIANT_PATTERN = re.compile(r"^[0-9.]+\((?P<variant>.*)\)$")

OFFICIAL_VARIANTS = {
    "allsensors",
    "br",
    "displays",
    "energy",
    "ircube",
    "knx",
    "lite",
    "matter",
    "mega",
    "platinum",
    "sensors",
    "tasmota",
    "teleinfo",
    "titanium",
    "zbbridge",
    "zigbee",
}


def is_stock_build(version: str) -> bool:
    """Return True if the version string indicates a stock build."""
    match = VERSION_VARIANT_PATTERN.match(version)
    if not match:
        return False
    variant = match.group("variant")

    if variant in ["minimal", "tasmota-minimal", "battery", "tasmota-battery"]:
        return False

    if variant in OFFICIAL_VARIANTS:
        return True
    if variant.startswith("tasmota-") or variant.startswith("tasmota32"):
        return True
    return False


@dataclass(frozen=True, kw_only=True)
class TasmotaUpdateConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota Update configuration."""

    poll_topic: str
    state_topic: str
    status_topic: str
    command_topic: str
    backlog_topic: str  # For Backlog command (OtaUrl + Upgrade)

    @classmethod
    def from_discovery_message(cls, config: dict) -> TasmotaUpdateConfig:
        """Instantiate from discovery message."""
        base_cmd = get_topic_command(config)
        return cls(
            endpoint="update",
            idx=None,
            friendly_name=None,
            mac=config[CONF_MAC],
            platform="update",
            poll_payload="2",
            poll_topic=get_topic_command_status(config),
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            deep_sleep_enabled=config[CONF_DEEP_SLEEP],
            state_topic=get_topic_tele_state(config),
            status_topic=get_topic_stat_status(config, 2),
            command_topic=base_cmd + COMMAND_UPGRADE,
            backlog_topic=base_cmd + COMMAND_BACKLOG,
        )


class TasmotaUpdate(TasmotaAvailability, TasmotaEntity):
    """Tasmota Update."""

    _cfg: TasmotaUpdateConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._sub_state: dict | None = None
        super().__init__(**kwds)

    async def update_firmware(self, url: str | None = None) -> None:
        """Update firmware.

        If url is provided, uses Backlog to first set OtaUrl, then trigger Upgrade 1.
        This is required for newer Tasmota versions where Upgrade <url> doesn't work.
        """
        if url:
            # Use Backlog to set OtaUrl and then trigger upgrade
            # Backlog command format: "OtaUrl http://...; Upgrade 1"
            payload = f"OtaUrl {url}; Upgrade 1"
            await self._mqtt_client.publish(
                self._cfg.backlog_topic,
                payload,
            )
        else:
            # No URL - just send Upgrade 1 to use pre-configured OtaUrl
            await self._mqtt_client.publish(
                self._cfg.command_topic,
                "1",
            )

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""

        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT state messages."""
            if not self._on_state_callback:
                return

            try:
                payload = json.loads(msg.payload)
            except json.decoder.JSONDecodeError:
                return

            # Status 2: {"StatusFWR":{"Version":"12.3.1(tasmota)","BuildDateTime":"..."}}
            # We look for StatusFWR.Version
            version = get_value_by_path(payload, ["StatusFWR", "Version"])
            if version:
                if is_stock_build(version):
                    self._on_state_callback(version)
                else:
                    match = VERSION_VARIANT_PATTERN.match(version)
                    variant = match.group("variant") if match else "unknown"
                    _LOGGER.debug(
                        "[%s] Custom firmware build detected (variant: %s). Skipping update check.",
                        self._cfg.mac,
                        variant,
                    )

        availability_topics = self.get_availability_topics()
        topics = {}
        # Periodic state update (tele/STATE) - usually doesn't contain version
        # but we might as well listen if we needed it. For now, we rely on polling Status 2.

        # Polled state update (stat/STATUS2)
        topics["status_topic"] = {
            "event_loop_safe": True,
            "topic": self._cfg.status_topic,
            "msg_callback": state_message_received,
        }

        topics = {**topics, **availability_topics}

        self._sub_state = await self._mqtt_client.subscribe(
            self._sub_state,
            topics,
        )

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe from all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    async def poll_status(self) -> None:
        """Poll for status."""
        await self.subscribe_topics()
        await self._mqtt_client.publish_debounced(
            self._cfg.poll_topic, self._cfg.poll_payload
        )
