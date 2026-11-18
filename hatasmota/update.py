"""Tasmota firmware update.

Helpers to tell whether a device runs an official Tasmota release build, and an
entity which reads the firmware details (STATUS2) and drives an OTA upgrade.

The download URL is never built here. Every official build is compiled with the
URL of its own variant as default OtaUrl, and ``OtaUrl 1`` restores that default.
The device therefore reports the right image for its chip, variant and language,
and the caller only has to verify that URL before sending ``Upgrade 1``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import json
import logging
import re
from typing import Any

from .const import COMMAND_OTA_URL, COMMAND_UPGRADE, CONF_DEEP_SLEEP, CONF_MAC
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
    get_topic_command,
    get_topic_command_status,
    get_topic_stat,
    get_topic_stat_result,
    get_topic_stat_status,
    get_topic_tele,
    get_topic_tele_will,
    get_value_by_path,
)

_LOGGER = logging.getLogger(__name__)

FAMILY_ESP32 = "esp32"
FAMILY_ESP8266 = "esp8266"
# Prefixes of STATUS2 "Hardware", see GetDeviceHardware in
# tasmota/tasmota_support/support_esp8266.ino and support_esp32.ino. Some
# ESP32-C3 packages report ESP8685 or ESP8686.
HARDWARE_PREFIXES = {
    FAMILY_ESP8266: ("ESP8266", "ESP8285"),
    FAMILY_ESP32: ("ESP32", "ESP8685", "ESP8686"),
}

# OTA updates from older versions need Tasmota's manual migration path.
MIN_OTA_VERSION = (9, 1, 0)
# Official builds only carry the "release-" marker in their version string since
# 14.0.0. Release binaries 9.1.0 to 13.4.0 from ota.tasmota.com report e.g.
# "13.4.0(tasmota)", exactly like a self-built firmware.
MIN_MARKED_RELEASE_VERSION = (14, 0, 0)

# STATUS2 "StatusFWR"."Version" and INFO1 "Info1"."Version", see
# tasmota/tasmota.ino (image_name), CmndStatus in
# tasmota/tasmota_support/support_command.ino and MqttConnected in
# tasmota/tasmota_xdrv_driver/xdrv_02_9_mqtt.ino:
# "<version>(<marker>-<image>)<cores>", for example
#   "15.2.0(release-tasmota)"            official release build
#   "15.2.0(release-solo1)single-core"   official release build for ESP32 solo1
#   "15.2.0.3(85cff52-tasmota32)"        development build, marker is the commit
#   "15.2.0(tasmota)"                    self-built, no marker
VERSION_PATTERN = re.compile(
    r"^(?P<version>\d+(?:\.\d+){2,3})\((?P<build>[^()]*)\)(?P<cores>.*)$"
)
RELEASE_MARKER = "release-"
COMMIT_MARKER_PATTERN = re.compile(r"^(?P<commit>[0-9a-f]{7,40})-(?P<image>.+)$")

# Official release images per chip family: image name (CODE_IMAGE_STR) mapped to
# the file name the build's compile-time OTA_URL points to. Derived from the
# Tasmota sources (arendst/Tasmota, development branch, November 2026):
# - .github/workflows/Tasmota_build_master.yml: the envs built for a release
# - platformio_tasmota_env.ini, platformio_tasmota_env32.ini: -DOTA_URL and
#   -DCODE_IMAGE_STR of each env
# - tasmota/include/tasmota_configurations.h, tasmota_configurations_ESP32.h:
#   CODE_IMAGE_STR set by the FIRMWARE_* define of each env
# Not listed on purpose: "minimal" and "safeboot" (intermediate images, see
# InstallBlocker). The OTA_URL of env tasmota-AD contains the typo "tasmot-AD";
# it does not match and is rejected.
_LANGUAGE = r"(?:-[A-Z]{2})?"
OFFICIAL_RELEASE_IMAGES: dict[str, dict[str, str]] = {
    FAMILY_ESP8266: {
        "tasmota": rf"tasmota{_LANGUAGE}",
        "tasmota-4M": r"tasmota-4M",
        "display": r"tasmota-display",
        "ir": r"tasmota-ir",
        "knx": r"tasmota-knx",
        "lite": r"tasmota-lite",
        "sensors": r"tasmota-sensors",
        "zbbridge": r"tasmota-zbbridge",
        "zigbee": r"tasmota-zigbee",
    },
    FAMILY_ESP32: {
        "tasmota32": rf"tasmota32(?:c2|c3|c5|c6|c61|p4|p4r3|s2|s2cdc|s3)?|tasmota32{_LANGUAGE}",
        "solo1": r"tasmota32solo1",
        "bluetooth": r"tasmota32-bluetooth",
        "display": r"tasmota32-display",
        "ir": r"tasmota32-ir",
        "lvgl-haspmota": r"tasmota32-lvgl",
        "nspanel": r"tasmota32-nspanel",
        "webcam": r"tasmota32-webcam",
        "zbbrdgpro": r"tasmota32-zbbrdgpro",
    },
}
# Directory and file extension on ota.tasmota.com per chip family
OTA_URL_PATTERN = re.compile(
    r"^https?://ota\.tasmota\.com/(?P<directory>tasmota|tasmota32)/release/"
    r"(?P<file>[A-Za-z0-9-]+)\.(?P<extension>bin\.gz|bin)$"
)
OTA_DIRECTORY = {FAMILY_ESP8266: "tasmota", FAMILY_ESP32: "tasmota32"}
OTA_EXTENSION = {FAMILY_ESP8266: "bin.gz", FAMILY_ESP32: "bin"}

# JSON texts of the Upgrade command and of the OTA result, see CmndUpgrade in
# support_command.ino and the OTA handling in support_tasmota.ino. The D_JSON_*
# texts are not translated.
UPGRADE_STARTED_PREFIX = "Version "
UPGRADE_SUCCESSFUL_PREFIX = "Successful"
UPGRADE_FAILED_PREFIX = "Failed"
UPGRADE_REJECTED_PREFIX = "1 or >"
UPGRADE_URL_SEPARATOR = " from "
# Images a device runs only during its own upgrade: ESP8266 devices without
# enough flash first install tasmota-minimal, ESP32 devices with a single
# OTA partition restart into safeboot to download the new image.
INTERMEDIATE_IMAGES = ("minimal", "safeboot")


class InstallBlocker(StrEnum):
    """Reason why a firmware must not be upgraded automatically."""

    # No STATUS2 received yet, or the version string can't be parsed
    UNKNOWN_FIRMWARE = "unknown_firmware"
    # Older than 9.1.0, needs Tasmota's manual migration path
    VERSION_TOO_OLD = "version_too_old"
    # Development build (four part version or commit marker)
    DEVELOPMENT_BUILD = "development_build"
    # 9.1.0 to 13.x: official builds are not marked, can't tell from self-built
    RELEASE_NOT_IDENTIFIABLE = "release_not_identifiable"
    # Intermediate images which are not meant to stay on a device
    MINIMAL_BUILD = "minimal_build"
    SAFEBOOT_BUILD = "safeboot_build"
    # No release marker: self-built firmware
    CUSTOM_BUILD = "custom_build"
    # Release marker, but image or chip family unknown to this library
    UNSUPPORTED_VARIANT = "unsupported_variant"


class UpgradeState(StrEnum):
    """State reported by the device for an OTA upgrade."""

    STARTED = "started"
    REJECTED = "rejected"
    SUCCESSFUL = "successful"
    FAILED = "failed"


@dataclass(frozen=True)
class UpgradeResult:
    """Upgrade state and the text reported by the device.

    For STARTED, url is the URL the device downloads from.
    """

    state: UpgradeState
    message: str
    url: str | None = None


@dataclass(frozen=True, kw_only=True)
class TasmotaFirmware:
    """Firmware details parsed from STATUS2."""

    version: str
    image: str
    marker: str | None
    cores: str
    hardware: str | None

    @property
    def version_tuple(self) -> tuple[int, ...]:
        """Return the version as tuple of ints."""
        return tuple(int(part) for part in self.version.split("."))

    @property
    def is_release(self) -> bool:
        """Return True if the firmware carries the release marker."""
        return self.marker == "release"

    @property
    def is_development(self) -> bool:
        """Return True for a development build."""
        return len(self.version_tuple) > 3 or (
            self.marker is not None and not self.is_release
        )

    @property
    def is_intermediate(self) -> bool:
        """Return True for an image which only runs during an upgrade."""
        return self.image in INTERMEDIATE_IMAGES

    @property
    def family(self) -> str | None:
        """Return the chip family reported in "Hardware"."""
        if self.hardware is None:
            return None
        for family, prefixes in HARDWARE_PREFIXES.items():
            if self.hardware.startswith(prefixes):
                return family
        return None


def parse_firmware(version: str, hardware: str | None = None) -> TasmotaFirmware | None:
    """Parse a Tasmota version string like "15.2.0(release-tasmota)"."""
    if not (match := VERSION_PATTERN.match(version)):
        return None
    build = match.group("build")
    marker: str | None = None
    image = build
    if build.startswith(RELEASE_MARKER):
        marker = "release"
        image = build[len(RELEASE_MARKER) :]
    elif commit_match := COMMIT_MARKER_PATTERN.match(build):
        marker = commit_match.group("commit")
        image = commit_match.group("image")
    if not image:
        return None
    return TasmotaFirmware(
        version=match.group("version"),
        image=image,
        marker=marker,
        cores=match.group("cores"),
        hardware=hardware,
    )


def parse_status_firmware(payload: dict | ReceivePayloadType) -> TasmotaFirmware | None:
    """Parse the "StatusFWR" object of a STATUS2 message."""
    version = get_value_by_path(payload, ["StatusFWR", "Version"])
    hardware = get_value_by_path(payload, ["StatusFWR", "Hardware"])
    if not isinstance(version, str):
        return None
    return parse_firmware(version, hardware if isinstance(hardware, str) else None)


def get_install_blocker(firmware: TasmotaFirmware | None) -> InstallBlocker | None:
    """Return why the firmware must not be upgraded, None if it may be."""
    if firmware is None:
        return InstallBlocker.UNKNOWN_FIRMWARE
    version = firmware.version_tuple
    if version[:3] < MIN_OTA_VERSION:
        return InstallBlocker.VERSION_TOO_OLD
    if firmware.is_development:
        return InstallBlocker.DEVELOPMENT_BUILD
    if version < MIN_MARKED_RELEASE_VERSION:
        return InstallBlocker.RELEASE_NOT_IDENTIFIABLE
    if firmware.image == INTERMEDIATE_IMAGES[0]:
        return InstallBlocker.MINIMAL_BUILD
    if firmware.image == INTERMEDIATE_IMAGES[1]:
        return InstallBlocker.SAFEBOOT_BUILD
    if not firmware.is_release:
        return InstallBlocker.CUSTOM_BUILD
    if (family := firmware.family) is None or firmware.image not in (
        OFFICIAL_RELEASE_IMAGES[family]
    ):
        return InstallBlocker.UNSUPPORTED_VARIANT
    return None


def is_official_ota_url(url: str, firmware: TasmotaFirmware) -> bool:
    """Return True if url is the official release image for the firmware.

    The url is expected to be the compile-time default OtaUrl of the firmware, as
    reported after ``OtaUrl 1``. Only use it if get_install_blocker returns None.
    """
    if get_install_blocker(firmware) is not None:
        return False
    if not (match := OTA_URL_PATTERN.match(url)):
        return False
    family = firmware.family
    assert family is not None
    if (
        match.group("directory") != OTA_DIRECTORY[family]
        or match.group("extension") != OTA_EXTENSION[family]
    ):
        return False
    file_pattern = OFFICIAL_RELEASE_IMAGES[family][firmware.image]
    return re.fullmatch(file_pattern, match.group("file")) is not None


def parse_upgrade_result(message: str) -> UpgradeResult | None:
    """Parse the text of an Upgrade response or OTA result."""
    if message.startswith(UPGRADE_STARTED_PREFIX):
        url = message.partition(UPGRADE_URL_SEPARATOR)[2] or None
        return UpgradeResult(UpgradeState.STARTED, message, url)
    if message.startswith(UPGRADE_SUCCESSFUL_PREFIX):
        return UpgradeResult(UpgradeState.SUCCESSFUL, message)
    if message.startswith(UPGRADE_FAILED_PREFIX):
        return UpgradeResult(UpgradeState.FAILED, message)
    if message.startswith(UPGRADE_REJECTED_PREFIX):
        return UpgradeResult(UpgradeState.REJECTED, message)
    return None


@dataclass(frozen=True, kw_only=True)
class TasmotaUpdateConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota firmware update configuration."""

    command_topic: str
    info_topic: str
    result_topic: str
    stat_topic: str
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
            command_topic=get_topic_command(config),
            info_topic=get_topic_tele(config) + "INFO1",
            result_topic=get_topic_stat_result(config),
            stat_topic=get_topic_stat(config),
            status_topic=get_topic_stat_status(config, 2),
        )


class TasmotaUpdate(TasmotaAvailability, TasmotaEntity):
    """Tasmota firmware update.

    Commands only go to the device's own command topic, never to a group topic.
    The state callback is called with a TasmotaFirmware for each STATUS2 message,
    the restart callback with a TasmotaFirmware when the device has booted, and
    the upgrade callback with an UpgradeResult.
    """

    _cfg: TasmotaUpdateConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._sub_state: dict | None = None
        self._firmware: TasmotaFirmware | None = None
        self._ota_url_future: asyncio.Future[str] | None = None
        self._ota_url_lock = asyncio.Lock()
        self._on_upgrade_callback: Callable[[UpgradeResult], None] | None = None
        self._on_restart_callback: Callable[[TasmotaFirmware], None] | None = None
        super().__init__(**kwds)

    @property
    def command_topic(self) -> str:
        """Return the device's command topic, e.g. "cmnd/tasmota_49A3BC/"."""
        return self._cfg.command_topic

    @property
    def firmware(self) -> TasmotaFirmware | None:
        """Return the firmware details from the last STATUS2 or INFO1 message."""
        return self._firmware

    def set_on_upgrade_callback(
        self, on_upgrade_callback: Callable[[UpgradeResult], None] | None
    ) -> None:
        """Set callback for upgrade state changes."""
        self._on_upgrade_callback = on_upgrade_callback

    def set_on_restart_callback(
        self, on_restart_callback: Callable[[TasmotaFirmware], None] | None
    ) -> None:
        """Set callback for a device which has booted."""
        self._on_restart_callback = on_restart_callback

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""

        def status_message_received(msg: ReceiveMessage) -> None:
            """Handle a STATUS2 message."""
            if (firmware := parse_status_firmware(msg.payload)) is None:
                return
            self._firmware = firmware
            if self._on_state_callback:
                self._on_state_callback(firmware)

        def info_message_received(msg: ReceiveMessage) -> None:
            """Handle INFO1, which Tasmota only sends once after it has booted.

            A retained INFO1 (InfoRetain) is not a new boot.
            """
            if msg.retain:
                return
            version = get_value_by_path(msg.payload, ["Info1", "Version"])
            if not isinstance(version, str):
                return
            hardware = self._firmware.hardware if self._firmware else None
            if (firmware := parse_firmware(version, hardware)) is None:
                return
            self._firmware = firmware
            if self._on_restart_callback:
                self._on_restart_callback(firmware)
            if self._on_state_callback:
                self._on_state_callback(firmware)

        def result_message_received(msg: ReceiveMessage) -> None:
            """Handle a command result (RESULT, or OTAURL/UPGRADE with SetOption4)."""
            try:
                payload = json.loads(msg.payload)
            except json.decoder.JSONDecodeError:
                return
            if not isinstance(payload, dict):
                return
            ota_url = payload.get(COMMAND_OTA_URL)
            if (
                isinstance(ota_url, str)
                and self._ota_url_future is not None
                and not self._ota_url_future.done()
            ):
                self._ota_url_future.set_result(ota_url)
            upgrade = payload.get(COMMAND_UPGRADE)
            if isinstance(upgrade, str) and (result := parse_upgrade_result(upgrade)):
                _LOGGER.debug("[%s] Upgrade: %s", self._cfg.mac, upgrade)
                if self._on_upgrade_callback:
                    self._on_upgrade_callback(result)

        topics: dict[str, dict[str, Any]] = {
            "status_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.status_topic,
                "msg_callback": status_message_received,
            },
            "info_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.info_topic,
                "msg_callback": info_message_received,
            },
            "result_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.result_topic,
                "msg_callback": result_message_received,
            },
            "ota_url_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.stat_topic + COMMAND_OTA_URL.upper(),
                "msg_callback": result_message_received,
            },
            # Upgrade response with SetOption4, and the OTA result in any case
            "upgrade_topic": {
                "event_loop_safe": True,
                "topic": self._cfg.stat_topic + COMMAND_UPGRADE.upper(),
                "msg_callback": result_message_received,
            },
        }
        topics.update(self.get_availability_topics())

        self._sub_state = await self._mqtt_client.subscribe(self._sub_state, topics)

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe from all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    async def _ota_url_command(self, payload: str, timeout: float) -> str:
        """Send OtaUrl and return the OtaUrl reported in the response."""
        async with self._ota_url_lock:
            self._ota_url_future = asyncio.get_running_loop().create_future()
            try:
                await self._mqtt_client.publish(
                    self._cfg.command_topic + COMMAND_OTA_URL, payload
                )
                async with asyncio.timeout(timeout):
                    return await self._ota_url_future
            finally:
                self._ota_url_future = None

    async def get_ota_url(self, timeout: float = 10) -> str:
        """Return the OtaUrl configured on the device, without changing it.

        Raises TimeoutError if the device doesn't answer.
        """
        return await self._ota_url_command("", timeout)

    async def reset_ota_url(self, timeout: float = 10) -> str:
        """Reset OtaUrl to the firmware's compile-time default and return it.

        Raises TimeoutError if the device doesn't answer.
        """
        return await self._ota_url_command("1", timeout)

    async def set_ota_url(self, url: str, timeout: float = 10) -> str:
        """Set OtaUrl, e.g. to restore the value read with get_ota_url.

        Raises ValueError for an empty url or one with whitespace, and
        TimeoutError if the device doesn't answer.
        """
        if not url or any(char.isspace() for char in url) or url in ("0", "1"):
            raise ValueError(f"Invalid OtaUrl {url!r}")
        return await self._ota_url_command(url, timeout)

    async def start_upgrade(self) -> None:
        """Send ``Upgrade 1``, the device downloads the image from its OtaUrl."""
        await self._mqtt_client.publish(self._cfg.command_topic + COMMAND_UPGRADE, "1")
