"""Tasmota discovery."""
import logging

import attr

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class TasmotaEntityConfig:
    """Base class for Tasmota configuation."""

    id: str = attr.ib()
    idx: int = attr.ib()
    friendly_name: str = attr.ib()


@attr.s(slots=True, frozen=True)
class TasmotaAvailabilityConfig(TasmotaEntityConfig):
    """Tasmota availability configuation."""

    availability_topic: str = attr.ib()
    availability_offline: str = attr.ib()
    availability_online: str = attr.ib()


class TasmotaEntity:
    """Base class for Tasmota entities."""

    def __init__(self, config):
        """Initialize."""
        self._cfg = config
        super().__init__()

    def config_same(self, new_config):
        """Return if updated config is same as current config."""
        return self._cfg == new_config

    def config_update(self, new_config):
        """Update config."""
        self._cfg = new_config

    @property
    def device_id(self):
        """Return friendly name."""
        return self._cfg.id

    @property
    def name(self):
        """Return friendly name."""
        return self._cfg.friendly_name


class TasmotaAvailability(TasmotaEntity):
    """Availability mixin for Tasmota entities."""

    def __init__(self, config):
        """Initialize."""
        self._on_availability_callback = None
        super().__init__(config)

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
                "topic": self._cfg.availability_topic,
                "msg_callback": availability_message_received,
            }
        }
        return topics

    def set_on_availability_callback(self, on_availability_callback):
        """Set callback for availability state change."""
        self._on_availability_callback = on_availability_callback
