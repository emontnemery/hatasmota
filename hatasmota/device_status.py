"""Tasmota status sensor."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

from .const import (
    CONF_MAC,
    SENSOR_STATUS_RSSI,
    SENSOR_STATUS_SIGNAL,
    SENSOR_STATUS_SSID,
)
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
    get_topic_command_status,
    get_topic_stat_status,
    get_topic_tele_state,
    get_topic_tele_will,
    get_value_by_path,
)

_LOGGER = logging.getLogger(__name__)

# 14:45:37 MQT: tasmota_B94927/tele/HASS_STATE = {
#  "Version":"9.0.0.1(tasmota)",               stat/STATUS2:"StatusFWR"."Version"
#  "BuildDateTime":"2020-10-08T21:38:21",      stat/STATUS2:"StatusFWR"."BuildDateTime"
#  "Module or Template":"Generic",             <NONE>
#  "RestartReason":"Software/System restart",  stat/STATUS1:"StatusPRM"."RestartReason"
#  "Uptime":"1T17:04:28",                      stat/STATUS11:"StatusSTS"."Uptime"; tele/STATE:"Uptime"
#  "BatteryPercentage":60,                     stat/STATUS11:"StatusSTS"."BatteryPercentage"; tele/STATE: "BatteryPercentage"
#  "Hostname":"tasmota_B94927",                stat/STATUS5:"StatusNET":"Hostname"
#  "IPAddress":"192.168.0.114",                stat/STATUS5:"StatusNET":"IPAddress"
#  "RSSI":"100",                               stat/STATUS11:"StatusSTS":"RSSI"; tele/STATE:"RSSI"
#  "Signal (dBm)":"-49",                       stat/STATUS11:"StatusSTS":"Signal"; tele/STATE:"Signal"
#  "WiFi LinkCount":1,                         stat/STATUS11:"StatusSTS":"LinkCount"; tele/STATE:"LinkCount"
#  "WiFi Downtime":"0T00:00:03",               stat/STATUS11:"StatusSTS":"Downtime"; tele/STATE:"Downtime"
#  "MqttCount":1,                              stat/STATUS11:"StatusSTS":"MqttCount"; tele/STATE:"MqttCount"
#  "LoadAvg":19                                stat/STATUS11:"StatusSTS":"LoadAvg"; tele/STATE:"LoadAvg"
# }

ATTRIBUTES = [
    SENSOR_STATUS_RSSI,
    SENSOR_STATUS_SIGNAL,
    SENSOR_STATUS_SSID,
]

STATE_PATHS: dict[str, list[str | int]] = {
    SENSOR_STATUS_RSSI: ["Wifi", "RSSI"],
    SENSOR_STATUS_SIGNAL: ["Wifi", "Signal"],
}

STATUS_PATHS: dict[str, list[str | int]] = {
    SENSOR_STATUS_RSSI: ["StatusSTS", "Wifi", "RSSI"],
    SENSOR_STATUS_SIGNAL: ["StatusSTS", "Wifi", "Signal"],
    SENSOR_STATUS_SSID: ["StatusSTS", "Wifi", "SSId"],
}

STATUS_TOPICS = {
    SENSOR_STATUS_RSSI: 11,
    SENSOR_STATUS_SIGNAL: 11,
    SENSOR_STATUS_SSID: 11,
}


@dataclass(frozen=True, kw_only=True)
class TasmotaDeviceStatusConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota Status Sensor configuration."""

    poll_topic: str
    state_topic: str
    status_topics: dict[int, str]

    @classmethod
    def from_discovery_message(cls, config: dict) -> TasmotaDeviceStatusConfig:
        """Instantiate from discovery message."""
        status_topics = {}
        for sensor in ATTRIBUTES:
            if sensor not in STATUS_TOPICS:
                continue
            topic = STATUS_TOPICS[sensor]
            status_topics[topic] = get_topic_stat_status(config, topic)
        return cls(
            endpoint="device_status",
            idx=None,
            friendly_name=None,
            mac=config[CONF_MAC],
            platform="device_status",
            poll_payload=str(STATUS_TOPICS.get(sensor)),
            poll_topic=get_topic_command_status(config),
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            state_topic=get_topic_tele_state(config),
            status_topics=status_topics,
        )


class TasmotaDeviceStatus(TasmotaAvailability, TasmotaEntity):
    """Tasmota device status."""

    _cfg: TasmotaDeviceStatusConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._sub_state: dict | None = None
        super().__init__(**kwds)

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

            attributes = {}
            for attribute in ATTRIBUTES:
                state = None
                if msg.topic == self._cfg.state_topic and attribute in STATE_PATHS:
                    state = get_value_by_path(payload, STATE_PATHS[attribute])
                elif msg.topic != self._cfg.state_topic and attribute in STATUS_PATHS:
                    state = get_value_by_path(payload, STATUS_PATHS[attribute])
                if state:
                    attributes[attribute] = state
            self._on_state_callback(attributes)

        availability_topics = self.get_availability_topics()
        topics = {}
        # Periodic state update (tele/STATE)
        topics["state_topic"] = {
            "event_loop_safe": True,
            "topic": self._cfg.state_topic,
            "msg_callback": state_message_received,
        }
        for suffix in self._cfg.status_topics:
            # Polled state update (stat/STATUS#)
            topics[f"status_topic_{suffix}"] = {
                "event_loop_safe": True,
                "topic": self._cfg.status_topics[suffix],
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
