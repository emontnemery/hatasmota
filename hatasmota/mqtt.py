"""Tasmota MQTT."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from .const import COMMAND_BACKLOG

DEBOUNCE_TIMEOUT = 1

_LOGGER = logging.getLogger(__name__)


class Timer:
    """Simple timer."""

    def __init__(
        self, timeout: float, callback: Callable[[], Coroutine[Any, Any, None]]
    ):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self) -> None:
        await asyncio.sleep(self._timeout)
        await self._callback()

    def cancel(self) -> None:
        """Cancel the timer."""
        self._task.cancel()


PublishPayloadType = str | bytes | int | float | None
ReceivePayloadType = str | bytes


@dataclass(frozen=True)
class PublishMessage:
    """MQTT Message."""

    topic: str
    payload: PublishPayloadType
    qos: int | None
    retain: bool | None


@dataclass(frozen=True)
class ReceiveMessage:
    """MQTT Message."""

    topic: str
    payload: ReceivePayloadType
    qos: int
    retain: bool


class TasmotaMQTTClient:
    """Helper class to sue an external MQTT client."""

    def __init__(
        self,
        publish: Callable[
            [str, PublishPayloadType, int | None, bool | None],
            Coroutine[Any, Any, None],
        ],
        subscribe: Callable[[dict | None, dict], Coroutine[Any, Any, dict]],
        unsubscribe: Callable[[dict | None], Coroutine[Any, Any, dict]],
    ):
        """Initialize."""
        self._pending_messages: dict[PublishMessage, Timer] = {}
        self._publish = publish
        self._subscribe = subscribe
        self._unsubscribe = unsubscribe

    async def publish(
        self,
        topic: str,
        payload: PublishPayloadType,
        qos: int | None = 0,
        retain: bool | None = False,
    ) -> None:
        """Publish a message."""
        return await self._publish(topic, payload, qos, retain)

    async def publish_debounced(
        self,
        topic: str,
        payload: PublishPayloadType,
        qos: int | None = 0,
        retain: bool | None = False,
    ) -> None:
        """Publish a message, with debounce."""
        msg = PublishMessage(topic, payload, qos, retain)

        async def publish_callback() -> None:
            _LOGGER.debug("publish_debounced: publishing %s", msg)
            self._pending_messages.pop(msg)
            await self.publish(msg.topic, msg.payload, qos=msg.qos, retain=msg.retain)

        if msg in self._pending_messages:
            timer = self._pending_messages.pop(msg)
            timer.cancel()
        timer = Timer(DEBOUNCE_TIMEOUT, publish_callback)
        self._pending_messages[msg] = timer

    async def subscribe(self, sub_state: dict | None, topics: dict) -> dict:
        """Subscribe to topics."""
        return await self._subscribe(sub_state, topics)

    async def unsubscribe(self, sub_state: dict | None) -> dict:
        """Unsubscribe from topics."""
        return await self._unsubscribe(sub_state)


async def send_commands(
    mqtt_client: TasmotaMQTTClient,
    command_topic: str,
    commands: list[tuple[str, str | float]],
) -> None:
    """Send a sequence of commands."""
    backlog_topic = command_topic + COMMAND_BACKLOG
    backlog = ";".join([f"NoDelay;{command[0]} {command[1]}" for command in commands])
    await mqtt_client.publish(backlog_topic, backlog)
