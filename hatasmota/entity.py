"""Tasmota discovery."""
import logging

import attr

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class TasmotaEntityConfig:
    """Base class for Tasmota configuation."""

    idx: int = attr.ib()
    friendly_name: str = attr.ib()
    mac: str = attr.ib()


@attr.s(slots=True, frozen=True)
class TasmotaAvailabilityConfig(TasmotaEntityConfig):
    """Tasmota availability configuation."""

    availability_topic: str = attr.ib()
    availability_offline: str = attr.ib()
    availability_online: str = attr.ib()


class TasmotaEntity:
    """Base class for Tasmota entities."""

    def __init__(self, config, mqtt_client):
        """Initialize."""
        self._cfg = config
        self._mqtt_client = mqtt_client
        super().__init__()

    def config_same(self, new_config):
        """Return if updated config is same as current config."""
        return self._cfg == new_config

    def config_update(self, new_config):
        """Update config."""
        self._cfg = new_config

    @property
    def mac(self):
        """Return MAC."""
        return self._cfg.mac

    @property
    def name(self):
        """Return friendly name."""
        return self._cfg.friendly_name


class TasmotaAvailability(TasmotaEntity):
    """Availability mixin for Tasmota entities."""

    def __init__(self, **kwds):
        """Initialize."""
        self._on_availability_callback = None
        super().__init__(**kwds)

    def get_availability_topics(self):
        """Return MQTT topics to subscribe to for availability state."""

        def availability_message_received(msg):
            """Handle a new received MQTT availability message."""
            if msg.payload == self._cfg.availability_online:
                self._on_availability_callback(True)
            if msg.payload == self._cfg.availability_offline:
                self._on_availability_callback(False)

        topics = {
            "availability_topic": {
                "event_loop_safe": True,
                "msg_callback": availability_message_received,
                "topic": self._cfg.availability_topic,
            }
        }
        return topics

    def set_on_availability_callback(self, on_availability_callback):
        """Set callback for availability state change."""
        self._on_availability_callback = on_availability_callback
