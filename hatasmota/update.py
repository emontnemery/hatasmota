"""Tasmota firmware version.

Splits the version string a device reports in STATUS2 into the numeric version
and the build tag, and tells whether the device runs an official Tasmota release
build. Meant for an update entity, which should only be offered for official
release builds: for self-built or development firmware the latest Tasmota
release is not relevant.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any

from .const import CONF_DEEP_SLEEP, CONF_MAC
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .mqtt import ReceiveMessage, ReceivePayloadType
from .utils import (
    config_get_state_offline,
    config_get_state_online,
    get_topic_command_status,
    get_topic_stat_status,
    get_topic_tele_will,
    get_value_by_path,
)

_LOGGER = logging.getLogger(__name__)

# STATUS2 "StatusFWR"."Version", see CmndStatus in
# tasmota/tasmota_support/support_command.ino and image_name in tasmota/tasmota.ino:
# "<version>(<build tag>)<cores>", for example
#   "15.2.0(release-tasmota)"            official release build
#   "15.2.0(release-solo1)single-core"   official release build for ESP32 solo1
#   "15.2.0.3(85cff52-tasmota32)"        development build, the tag starts with
#                                        the commit
#   "15.2.0(tasmota)"                    self-built
VERSION_PATTERN = re.compile(
    r"^(?P<version>\d+(?:\.\d+){2,3})\((?P<build_tag>[^()]+)\)(?P<cores>.*)$"
)
# Only the release workflow of the Tasmota repository puts "release-" into the
# build tag (TASMOTA_SHA_SHORT in .github/workflows/Tasmota_build_master.yml).
# It does so since 14.0.0: the release binaries 9.1.0 to 13.4.0 on
# ota.tasmota.com report e.g. "13.4.0(tasmota)", exactly like a self-built
# firmware, so they are not recognized as release builds.
RELEASE_MARKER = "release-"


@dataclass(frozen=True, kw_only=True)
class TasmotaFirmware:
    """Firmware version reported by a device."""

    # Numeric version, e.g. "15.2.0", or "15.2.0.3" for a development build
    version: str
    # Build tag, e.g. "release-tasmota", "85cff52-tasmota32" or "tasmota"
    build_tag: str

    @property
    def is_release(self) -> bool:
        """Return True for an official Tasmota release build."""
        return self.build_tag.startswith(RELEASE_MARKER)


def parse_firmware(version: str) -> TasmotaFirmware | None:
    """Parse a Tasmota version string like "15.2.0(release-tasmota)"."""
    if not (match := VERSION_PATTERN.match(version)):
        return None
    return TasmotaFirmware(
        version=match.group("version"), build_tag=match.group("build_tag")
    )


def parse_status_firmware(payload: ReceivePayloadType) -> TasmotaFirmware | None:
    """Parse the "StatusFWR" object of a STATUS2 message."""
    version = get_value_by_path(payload, ["StatusFWR", "Version"])
    if not isinstance(version, str):
        return None
    return parse_firmware(version)


@dataclass(frozen=True, kw_only=True)
class TasmotaUpdateConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota firmware update configuration."""

    status_topic: str

    @classmethod
    def from_discovery_message(cls, config: dict) -> TasmotaUpdateConfig:
        """Instantiate from discovery message."""
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
            status_topic=get_topic_stat_status(config, 2),
        )


class TasmotaUpdate(TasmotaAvailability, TasmotaEntity):
    """Tasmota firmware update.

    STATUS2 is polled when the device comes online, which includes every restart.
    The state callback is called with a TasmotaFirmware for each STATUS2 message.
    """

    _cfg: TasmotaUpdateConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._sub_state: dict | None = None
        self._firmware: TasmotaFirmware | None = None
        super().__init__(**kwds)

    @property
    def firmware(self) -> TasmotaFirmware | None:
        """Return the firmware from the last STATUS2 message."""
        return self._firmware

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""

        def status_message_received(msg: ReceiveMessage) -> None:
            """Handle a STATUS2 message."""
            if (firmware := parse_status_firmware(msg.payload)) is None:
                _LOGGER.debug("[%s] Unknown firmware version", self._cfg.mac)
                return
            self._firmware = firmware
            if self._on_state_callback:
                self._on_state_callback(firmware)

        topics: dict[str, dict[str, Any]] = {
            "status_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.status_topic,
                "msg_callback": status_message_received,
            },
        }
        topics.update(self.get_availability_topics())

        self._sub_state = await self._mqtt_client.subscribe(self._sub_state, topics)

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe from all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)
