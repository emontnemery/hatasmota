"""Tasmota binary sensor."""
import logging

from .const import AUTOMATION_TYPE_TRIGGER

_LOGGER = logging.getLogger(__name__)


class TasmotaTrigger:
    """Representation of a Tasmota trigger."""

    def __init__(self, config, mqtt_client, **kwds):
        """Initialize."""
        self._sub_state = None
        self.cfg = config
        self._mqtt_client = mqtt_client
        self._on_trigger_callback = None
        super().__init__(**kwds)

    def config_same(self, new_config):
        """Return if updated config is same as current config."""
        return self.cfg == new_config

    def config_update(self, new_config):
        """Update config."""
        self.cfg = new_config

    def set_on_trigger_callback(self, on_trigger_callback):
        """Set callback for triggere."""
        self._on_trigger_callback = on_trigger_callback

    def _trig_message_received(self, msg):
        """Handle new MQTT messages."""

    async def subscribe_topics(self):
        """Subscribe to topics."""

        topics = {
            "trigger_topic": {
                "event_loop_safe": True,
                "topic": self.cfg.trigger_topic,
                "msg_callback": lambda msg: self._trig_message_received(  # pylint: disable=unnecessary-lambda
                    msg
                ),
            }
        }

        self._sub_state = await self._mqtt_client.subscribe(
            self._sub_state,
            topics,
        )

    async def unsubscribe_topics(self):
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    @property
    def automation_type(self):
        """Return the automation type."""
        return AUTOMATION_TYPE_TRIGGER
