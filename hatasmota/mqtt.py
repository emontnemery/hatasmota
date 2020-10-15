"""Tasmota MQTT."""
import asyncio
import logging
from typing import Union

import attr

from .const import COMMAND_BACKLOG

DEBOUNCE_TIMEOUT = 1

_LOGGER = logging.getLogger(__name__)


class Timer:
    """Simple timer."""

    def __init__(self, timeout, callback):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._timeout)
        self._callback()

    def cancel(self):
        """Cancel the timer."""
        self._task.cancel()


PublishPayloadType = Union[str, bytes, int, float, None]


@attr.s(slots=True, frozen=True)
class Message:
    """MQTT Message."""

    topic: str = attr.ib()
    payload: PublishPayloadType = attr.ib()
    qos: int = attr.ib()
    retain: bool = attr.ib()


class TasmotaMQTTClient:
    """Helper class to sue an external MQTT client."""

    def __init__(self, publish, subscribe, unsubscribe):
        """Initialize."""
        self._pending_messages = {}
        self._publish = publish
        self._subscribe = subscribe
        self._unsubscribe = unsubscribe

    def publish(self, *args, **kwds):
        """Publish a message."""
        return self._publish(*args, **kwds)

    def publish_debounced(self, topic, payload, qos=None, retain=None):
        """Publish a message, with debounce."""
        msg = Message(topic, payload, qos, retain)

        def publish_callback():
            _LOGGER.debug("publish_debounced: publishing %s", msg)
            self._pending_messages.pop(msg)
            self.publish(msg.topic, msg.payload, qos=msg.qos, retain=msg.retain)

        if msg in self._pending_messages:
            timer = self._pending_messages.pop(msg)
            timer.cancel()
        timer = Timer(DEBOUNCE_TIMEOUT, publish_callback)
        self._pending_messages[msg] = timer

    async def subscribe(self, sub_state, topics):
        """Subscribe to topics."""
        return await self._subscribe(sub_state, topics)

    async def unsubscribe(self, sub_state):
        """Unsubscribe from topics."""
        return await self._unsubscribe(sub_state)


def send_commands(mqtt_client, command_topic, commands):
    """Send a sequence of commands."""
    backlog_topic = command_topic + COMMAND_BACKLOG
    backlog = ";".join(["NoDelay;%s %s" % command for command in commands])
    mqtt_client.publish(backlog_topic, backlog)
