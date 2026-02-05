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

VERSION_VARIANT_PATTERN = re.compile(r"^(?P<version>[0-9.]+)\((?P<variant>.*)\)$")
MIN_SAFE_VERSION = (9, 1, 0)

OFFICIAL_VARIANTS = {
    # ESP8266 / ESP8285
    "tasmota",
    "lite",
    "knx",
    "sensors",
    "ir",
    "display",
    "zbbridge",
    "zigbee",
    # ESP32 Family
    "tasmota32",
    "tasmota32solo1",
    "tasmota32c2",
    "tasmota32c3",
    "tasmota32c5",
    "tasmota32c6",
    "tasmota32p4",
    "tasmota32s2",
    "tasmota32s2cdc",
    "tasmota32s3",
    # ESP32 Feature Builds
    "bluetooth",
    "lvgl",
    "nspanel",
    "webcam",
    "zbbridgepro",
}


def is_stock_build(version_str: str) -> bool:
    """Return True if the version string indicates a stock build and is safe to update."""
    if not (match := VERSION_VARIANT_PATTERN.match(version_str)):
        return False

    version_num_str = match.group("version")
    variant = match.group("variant")

    # Safety check: Versions older than 9.1.0 require manual migration paths
    try:
        version_parts = tuple(int(p) for p in version_num_str.split("."))
        if version_parts < MIN_SAFE_VERSION:
            _LOGGER.warning(
                "Tasmota version %s is too old for auto-update. "
                "Please follow the manual migration path to 9.1.0 first.",
                version_num_str,
            )
            return False
    except ValueError:
        return False

    if variant in ["minimal", "tasmota-minimal", "battery", "tasmota-battery"]:
        return False

    if variant in OFFICIAL_VARIANTS:
        return True
    # Localized language builds (e.g., tasmota-DE, tasmota32-DE)
    if re.match(r"^(tasmota|tasmota32)-[A-Z]{2}$", variant):
        return True
    # Prefixed official variants (e.g., tasmota-sensors, tasmota32-display)
    if variant.startswith("tasmota-") and variant[8:] in OFFICIAL_VARIANTS:
        return True
    if variant.startswith("tasmota32-") and variant[10:] in OFFICIAL_VARIANTS:
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
            if version := get_value_by_path(payload, ["StatusFWR", "Version"]):
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
