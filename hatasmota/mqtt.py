"""Tasmota MQTT."""


class TasmotaMQTTClient:
    """Helper class to sue an external MQTT client."""

    def __init__(self, publish, subscribe, unsubscribe):
        """Initialize."""
        self._publish = publish
        self._subscribe = subscribe
        self._unsubscribe = unsubscribe

    def publish(self, *args, **kwds):
        """Publish a message."""
        return self._publish(*args, **kwds)

    async def subscribe(self, sub_state, topics):
        """Subscribe to topics."""
        return await self._subscribe(sub_state, topics)

    async def unsubscribe(self, sub_state):
        """Unsubscribe from topics."""
        return await self._unsubscribe(sub_state)
