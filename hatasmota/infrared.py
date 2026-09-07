"""Tasmota infrared."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypeAlias

from .const import (
    COMMAND_IRSEND,
    CONF_DEEP_SLEEP,
    CONF_MAC,
)
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .utils import (
    config_get_state_offline,
    config_get_state_online,
    get_topic_command,
    get_topic_command_state,
    get_topic_stat_result,
    get_topic_tele_will,
)


def _validate_non_empty_string(value: str | None, field_name: str) -> str:
    """Validate a non-empty string field."""
    if value is None:
        raise ValueError(f"{field_name} is required")
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    return value


def _validate_non_negative_int(value: int | None, field_name: str) -> int | None:
    """Validate a non-negative integer field."""
    if value is None:
        return None
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _validate_positive_int(value: int | None, field_name: str) -> int | None:
    """Validate a positive integer field."""
    if value is None:
        return None
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _validate_send_times(send_times: int | None) -> None:
    """Validate send_times is non-negative if provided."""
    _validate_non_negative_int(send_times, "send_times")


def _normalize_send_times(send_times: int | None) -> int | None:
    """Normalize IRSend<x> suffix: values <= 1 map to None (send once, no suffix)."""
    if send_times is None:
        return None
    _validate_send_times(send_times)
    if send_times <= 1:
        return None
    return send_times


def _command_name(base_command: str, send_times: int | None) -> str:
    """Return a Tasmota command name with optional repeat suffix."""
    normalized_send_times = _normalize_send_times(send_times)
    if normalized_send_times is None:
        return base_command
    return f"{base_command}{normalized_send_times}"


def _normalize_json_payload(payload: dict[str, Any]) -> str:
    """Serialize a compact JSON payload."""
    return json.dumps(payload, separators=(",", ":"))


def _normalize_ir_data_value(value: str | int, field_name: str) -> str | int:
    """Normalize protocol-form IR data values."""
    if isinstance(value, str):
        return _validate_non_empty_string(value, field_name)
    return value


@dataclass(frozen=True, kw_only=True)
class TasmotaInfraredConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota infrared configuration."""

    command_topic: str
    result_topic: str | None
    supports_irsend: bool
    supports_irsend_raw: bool
    supports_irhvac: bool
    supports_receive: bool

    @classmethod
    def from_discovery_message(
        cls,
        config: dict,
        platform: str = "infrared",
        *,
        supports_irsend: bool = True,
        supports_irsend_raw: bool = True,
        supports_irhvac: bool = True,
        supports_receive: bool = False,
    ) -> TasmotaInfraredConfig:
        """Instantiate from discovery message."""
        return cls(
            endpoint="infrared",
            idx="infrared",
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
            supports_irsend=supports_irsend,
            supports_irsend_raw=supports_irsend_raw,
            supports_irhvac=supports_irhvac,
            supports_receive=supports_receive,
        )


@dataclass(frozen=True, kw_only=True)
class TasmotaIRSendCommand:
    """Compact protocol-form IRSend command."""

    bits: int
    protocol: str | None = None
    vendor: str | None = None
    data: str | int | None = None
    data_lsb: str | int | None = None
    repeat: int | None = None
    channel: int | None = None
    send_times: int | None = None


@dataclass(frozen=True, kw_only=True)
class TasmotaIRSendRawTimingsCommand:
    """Raw IRSend timings command."""

    frequency: int | None = None
    timings: tuple[int, ...] | None = None
    compact_timings: str | None = None
    send_times: int | None = None


@dataclass(frozen=True, kw_only=True)
class TasmotaIRSendRawBitstreamCommand:
    """Raw IRSend bitstream command."""

    zero_space: int
    bit_stream: str
    frequency: int | None = None
    header_mark: int | None = None
    header_space: int | None = None
    bit_mark: int | None = None
    one_multiple: int | None = None
    one_space: int | None = None
    send_times: int | None = None


TasmotaIRSendRawCommand: TypeAlias = (
    TasmotaIRSendRawTimingsCommand | TasmotaIRSendRawBitstreamCommand
)


class TasmotaInfraredEmitter(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota infrared emitter."""

    _cfg: TasmotaInfraredConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._sub_state: dict | None = None
        super().__init__(**kwds)

    async def subscribe_topics(self) -> None:
        """Subscribe to topics."""
        availability_topics = self.get_availability_topics()
        self._sub_state = await self._mqtt_client.subscribe(
            self._sub_state, availability_topics
        )

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe from all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    async def send_irsend(self, command: TasmotaIRSendCommand) -> None:
        """Send a compact protocol-form IRSend command."""
        if not self._cfg.supports_irsend:
            raise ValueError("Device does not support protocol-form IRSend")

        payload = _serialize_irsend_command(command)
        topic = self._cfg.command_topic + _command_name(
            COMMAND_IRSEND, command.send_times
        )
        await self._mqtt_client.publish(topic, payload)

    async def send_irsend_raw(self, command: TasmotaIRSendRawCommand) -> None:
        """Send a raw IRSend command."""
        if not self._cfg.supports_irsend_raw:
            raise ValueError("Device does not support raw IRSend")

        payload = _serialize_irsend_raw_command(command)
        topic = self._cfg.command_topic + _command_name(
            COMMAND_IRSEND, command.send_times
        )
        await self._mqtt_client.publish(topic, payload)


def _serialize_irsend_command(command: TasmotaIRSendCommand) -> str:
    """Serialize a compact protocol-form IRSend command."""
    protocol = command.protocol.strip() if command.protocol is not None else None
    vendor = command.vendor.strip() if command.vendor is not None else None
    if bool(protocol) == bool(vendor):
        raise ValueError("Exactly one of protocol or vendor must be set")
    if not 1 <= command.bits <= 64:
        raise ValueError("bits must be between 1 and 64")
    if command.data is None and command.data_lsb is None:
        raise ValueError("Either data or data_lsb must be set")
    if command.channel is not None and not 1 <= command.channel <= 16:
        raise ValueError("channel must be between 1 and 16")

    repeat = _validate_non_negative_int(command.repeat, "repeat")
    _validate_send_times(command.send_times)

    payload: dict[str, Any] = {"Bits": command.bits}
    if protocol is not None:
        payload["Protocol"] = _validate_non_empty_string(protocol, "protocol")
    if vendor is not None:
        payload["Vendor"] = _validate_non_empty_string(vendor, "vendor")
    if command.data is not None:
        payload["Data"] = _normalize_ir_data_value(command.data, "data")
    if command.data_lsb is not None:
        payload["DataLSB"] = _normalize_ir_data_value(command.data_lsb, "data_lsb")
    if repeat is not None:
        payload["Repeat"] = repeat
    if command.channel is not None:
        payload["Channel"] = command.channel

    return _normalize_json_payload(payload)


def _serialize_irsend_raw_command(command: TasmotaIRSendRawCommand) -> str:
    """Serialize a raw IRSend command."""
    _validate_send_times(command.send_times)
    if isinstance(command, TasmotaIRSendRawTimingsCommand):
        return _serialize_irsend_raw_timings_command(command)
    return _serialize_irsend_raw_bitstream_command(command)


def _serialize_irsend_raw_timings_command(
    command: TasmotaIRSendRawTimingsCommand,
) -> str:
    """Serialize a timings-form raw IRSend command."""
    frequency = _validate_non_negative_int(command.frequency or 0, "frequency")
    has_timings = command.timings is not None
    has_compact_timings = command.compact_timings is not None
    if has_timings == has_compact_timings:
        raise ValueError("Exactly one of timings or compact_timings must be set")

    if command.timings is not None:
        if len(command.timings) < 2:
            raise ValueError("timings must include at least two entries")
        normalized_timings = []
        for timing in command.timings:
            if timing <= 0:
                raise ValueError("timings entries must be positive")
            normalized_timings.append(str(timing))
        return f"{frequency}," + ",".join(normalized_timings)

    compact_timings = _validate_non_empty_string(
        command.compact_timings, "compact_timings"
    )
    return f"{frequency},{compact_timings}"


def _serialize_irsend_raw_bitstream_command(
    command: TasmotaIRSendRawBitstreamCommand,
) -> str:
    """Serialize a bitstream-form raw IRSend command."""
    frequency = _validate_non_negative_int(command.frequency or 0, "frequency")
    zero_space = _validate_positive_int(command.zero_space, "zero_space")
    if zero_space is None:
        raise ValueError("zero_space is required")

    bit_stream = _validate_non_empty_string(command.bit_stream, "bit_stream")
    if any(bit not in {"0", "1"} for bit in bit_stream):
        raise ValueError("bit_stream must contain only 0 and 1")

    header_values = (command.header_mark, command.header_space, command.bit_mark)
    if any(value is not None for value in header_values) and any(
        value is None for value in header_values
    ):
        raise ValueError(
            "header_mark, header_space, and bit_mark must be provided together"
        )
    for field_name, value in (
        ("header_mark", command.header_mark),
        ("header_space", command.header_space),
        ("bit_mark", command.bit_mark),
        ("one_multiple", command.one_multiple),
        ("one_space", command.one_space),
    ):
        if value is not None:
            _validate_positive_int(value, field_name)

    if command.one_multiple is not None and command.one_space is not None:
        raise ValueError("Only one of one_multiple or one_space may be set")

    payload_parts: list[str] = ["raw", str(frequency)]
    if command.header_mark is not None:
        payload_parts.extend(
            [
                str(command.header_mark),
                str(command.header_space),
                str(command.bit_mark),
            ]
        )
    payload_parts.append(str(zero_space))
    if command.one_multiple is not None:
        payload_parts.append(str(command.one_multiple))
    elif command.one_space is not None:
        payload_parts.append(str(command.one_space))
    payload_parts.append(bit_stream)
    return ",".join(payload_parts)
