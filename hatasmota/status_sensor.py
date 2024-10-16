"""Tasmota status sensor."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any

from .const import (
    CONF_BATTERY,
    CONF_DEEP_SLEEP,
    CONF_IP,
    CONF_MAC,
    PERCENTAGE,
    SENSOR_BATTERY,
    SENSOR_STATUS_BATTERY_PERCENTAGE,
    SENSOR_STATUS_IP,
    SENSOR_STATUS_LAST_RESTART_TIME,
    SENSOR_STATUS_LINK_COUNT,
    SENSOR_STATUS_MQTT_COUNT,
    SENSOR_STATUS_RESTART_REASON,
    SENSOR_STATUS_RSSI,
    SENSOR_STATUS_SIGNAL,
    SENSOR_STATUS_SSID,
    SENSOR_STATUS_VERSION,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from .entity import TasmotaAvailability, TasmotaEntity
from .mqtt import ReceiveMessage
from .sensor import TasmotaBaseSensorConfig
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
#  "BatteryPercentage":60,                     stat/STATUS11:"StatusSTS":"BatteryPercentage"; tele/STATE: "BatteryPercentage"
#  "Hostname":"tasmota_B94927",                stat/STATUS5:"StatusNET":"Hostname"
#  "IPAddress":"192.168.0.114",                stat/STATUS5:"StatusNET":"IPAddress"
#  "RSSI":"100",                               stat/STATUS11:"StatusSTS":"RSSI"; tele/STATE:"RSSI"
#  "Signal (dBm)":"-49",                       stat/STATUS11:"StatusSTS":"Signal"; tele/STATE:"Signal"
#  "WiFi LinkCount":1,                         stat/STATUS11:"StatusSTS":"LinkCount"; tele/STATE:"LinkCount"
#  "WiFi Downtime":"0T00:00:03",               stat/STATUS11:"StatusSTS":"Downtime"; tele/STATE:"Downtime"
#  "MqttCount":1,                              stat/STATUS11:"StatusSTS":"MqttCount"; tele/STATE:"MqttCount"
#  "LoadAvg":19                                stat/STATUS11:"StatusSTS":"LoadAvg"; tele/STATE:"LoadAvg"
# }

SENSORS = [
    SENSOR_STATUS_IP,
    SENSOR_STATUS_LAST_RESTART_TIME,
    SENSOR_STATUS_LINK_COUNT,
    SENSOR_STATUS_MQTT_COUNT,
    SENSOR_STATUS_RESTART_REASON,
    SENSOR_STATUS_RSSI,
    SENSOR_STATUS_SIGNAL,
    SENSOR_STATUS_SSID,
    SENSOR_STATUS_VERSION,
]

NAMES = {
    SENSOR_STATUS_IP: "IP",
    SENSOR_STATUS_LAST_RESTART_TIME: "Last Restart Time",
    SENSOR_STATUS_LINK_COUNT: "WiFi Connect Count",
    SENSOR_STATUS_MQTT_COUNT: "MQTT Connect Count",
    SENSOR_STATUS_RESTART_REASON: "Restart Reason",
    SENSOR_STATUS_BATTERY_PERCENTAGE: "Battery Level",
    SENSOR_STATUS_RSSI: "RSSI",
    SENSOR_STATUS_SIGNAL: "Signal",
    SENSOR_STATUS_SSID: "SSID",
    SENSOR_STATUS_VERSION: "Firmware Version",
}

SINGLE_SHOT = [
    SENSOR_STATUS_LAST_RESTART_TIME,
    SENSOR_STATUS_RESTART_REASON,
    SENSOR_STATUS_VERSION,
]

STATE_PATHS: dict[str, list[str | int]] = {
    SENSOR_STATUS_LINK_COUNT: ["Wifi", "LinkCount"],
    SENSOR_STATUS_MQTT_COUNT: ["MqttCount"],
    SENSOR_STATUS_BATTERY_PERCENTAGE: ["BatteryPercentage"],
    SENSOR_STATUS_RSSI: ["Wifi", "RSSI"],
    SENSOR_STATUS_SIGNAL: ["Wifi", "Signal"],
}

STATUS_PATHS: dict[str, list[str | int]] = {
    SENSOR_STATUS_LAST_RESTART_TIME: ["StatusSTS", "UptimeSec"],
    SENSOR_STATUS_LINK_COUNT: ["StatusSTS", "Wifi", "LinkCount"],
    SENSOR_STATUS_MQTT_COUNT: ["StatusSTS", "MqttCount"],
    SENSOR_STATUS_RESTART_REASON: ["StatusPRM", "RestartReason"],
    SENSOR_STATUS_RSSI: ["StatusSTS", "Wifi", "RSSI"],
    SENSOR_STATUS_SIGNAL: ["StatusSTS", "Wifi", "Signal"],
    SENSOR_STATUS_SSID: ["StatusSTS", "Wifi", "SSId"],
    SENSOR_STATUS_VERSION: ["StatusFWR", "Version"],
    SENSOR_STATUS_BATTERY_PERCENTAGE: ["StatusSTS", "BatteryPercentage"],
}

STATUS_TOPICS = {
    SENSOR_STATUS_LAST_RESTART_TIME: 11,
    SENSOR_STATUS_LINK_COUNT: 11,
    SENSOR_STATUS_MQTT_COUNT: 11,
    SENSOR_STATUS_RESTART_REASON: 1,
    SENSOR_STATUS_RSSI: 11,
    SENSOR_STATUS_SIGNAL: 11,
    SENSOR_STATUS_SSID: 11,
    SENSOR_STATUS_VERSION: 2,
    SENSOR_STATUS_BATTERY_PERCENTAGE: 11,
}

QUANTITY = {
    SENSOR_STATUS_IP: SENSOR_STATUS_IP,
    SENSOR_STATUS_LAST_RESTART_TIME: SENSOR_STATUS_LAST_RESTART_TIME,
    SENSOR_STATUS_LINK_COUNT: SENSOR_STATUS_LINK_COUNT,
    SENSOR_STATUS_MQTT_COUNT: SENSOR_STATUS_MQTT_COUNT,
    SENSOR_STATUS_RESTART_REASON: SENSOR_STATUS_RESTART_REASON,
    SENSOR_STATUS_BATTERY_PERCENTAGE: SENSOR_BATTERY,
    SENSOR_STATUS_RSSI: SENSOR_STATUS_RSSI,
    SENSOR_STATUS_SIGNAL: SENSOR_STATUS_SIGNAL,
    SENSOR_STATUS_SSID: SENSOR_STATUS_SSID,
    SENSOR_STATUS_VERSION: SENSOR_STATUS_VERSION,
}

UNITS = {
    SENSOR_STATUS_IP: None,
    SENSOR_STATUS_LAST_RESTART_TIME: None,
    SENSOR_STATUS_LINK_COUNT: None,
    SENSOR_STATUS_MQTT_COUNT: None,
    SENSOR_STATUS_RESTART_REASON: None,
    SENSOR_STATUS_BATTERY_PERCENTAGE: PERCENTAGE,
    SENSOR_STATUS_RSSI: PERCENTAGE,
    SENSOR_STATUS_SIGNAL: SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    SENSOR_STATUS_SSID: None,
    SENSOR_STATUS_VERSION: None,
}


@dataclass(frozen=True, kw_only=True)
class TasmotaStatusSensorConfig(TasmotaBaseSensorConfig):
    """Tasmota Status Sensor configuration."""

    poll_topic: str
    sensor: str
    state: str | None
    state_topic: str
    status_topic: str

    @classmethod
    def from_discovery_message(
        cls, config: dict, platform: str
    ) -> list[TasmotaStatusSensorConfig]:
        """Instantiate from discovery message."""
        sensor_types = list(SENSORS)
        if config[CONF_BATTERY] == 1:
            sensor_types.append(SENSOR_STATUS_BATTERY_PERCENTAGE)
        sensors = [
            cls(
                endpoint="status_sensor",
                idx=None,
                friendly_name=NAMES[sensor],
                mac=config[CONF_MAC],
                platform=platform,
                poll_payload=str(STATUS_TOPICS.get(sensor)),
                poll_topic=get_topic_command_status(config),
                availability_topic=get_topic_tele_will(config),
                availability_offline=config_get_state_offline(config),
                availability_online=config_get_state_online(config),
                deep_sleep_enabled=config[CONF_DEEP_SLEEP],
                sensor=sensor,
                state=config[CONF_IP] if sensor == SENSOR_STATUS_IP else None,
                state_topic=get_topic_tele_state(config),
                status_topic=get_topic_stat_status(config, STATUS_TOPICS.get(sensor)),
            )
            for sensor in sensor_types
        ]
        return sensors

    @property
    def unique_id(self) -> str:
        """Return unique_id."""
        return f"{self.mac}_{self.platform}_{self.endpoint}_{self.sensor}"


class TasmotaStatusSensor(TasmotaAvailability, TasmotaEntity):
    """Tasmota Status sensors."""

    _cfg: TasmotaStatusSensorConfig

    def __init__(self, **kwds: Any):
        """Initialize."""
        self._sub_state: dict | None = None
        self._sub_state_lock = asyncio.Lock()
        super().__init__(**kwds)

    async def _poll_status(self) -> None:
        """Poll for status."""
        await self.subscribe_topics()
        await self._mqtt_client.publish_debounced(
            self._cfg.poll_topic, self._cfg.poll_payload
        )

    async def poll_status(self) -> None:
        """Poll for status."""
        await self._poll_status()

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

            state = None
            if msg.topic == self._cfg.state_topic:
                state = get_value_by_path(payload, STATE_PATHS[self._cfg.sensor])
            else:
                state = get_value_by_path(payload, STATUS_PATHS[self._cfg.sensor])
            if state is not None:
                if self._cfg.sensor in SINGLE_SHOT:
                    asyncio.create_task(self._unsubscribe_state_topics())
                if self._cfg.sensor == SENSOR_STATUS_LAST_RESTART_TIME:
                    state = datetime.now(timezone.utc) - timedelta(seconds=int(state))
                self._on_state_callback(state)

        availability_topics = self.get_availability_topics()
        topics = {}
        if self._cfg.sensor in STATE_PATHS:
            # Periodic state update (tele/STATE)
            topics["state_topic"] = {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic,
                "msg_callback": state_message_received,
            }
        if self._cfg.sensor in STATUS_PATHS:
            # Polled state update (stat/STATUS#)
            topics["status_topic"] = {
                "event_loop_safe": True,
                "topic": self._cfg.status_topic,
                "msg_callback": state_message_received,
            }
        topics = {**topics, **availability_topics}

        async with self._sub_state_lock:
            self._sub_state = await self._mqtt_client.subscribe(
                self._sub_state,
                topics,
            )
        if self._cfg.state and self._on_state_callback:
            self._on_state_callback(self._cfg.state)

    async def _unsubscribe_state_topics(self) -> None:
        """Unsubscribe from state topics."""
        availability_topics = self.get_availability_topics()
        async with self._sub_state_lock:
            self._sub_state = await self._mqtt_client.subscribe(
                self._sub_state,
                availability_topics,
            )

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe from all MQTT topics."""
        async with self._sub_state_lock:
            self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    @property
    def discovered_as_numeric(self) -> bool:
        """Return if the sensor was discovered with a numeric value.

        Not needed for status sensors.
        """
        return False

    @property
    def quantity(self) -> str:
        """Return the sensor's quantity (speed, mass, etc.)."""
        return QUANTITY[self._cfg.sensor]

    @property
    def unit(self) -> str | None:
        """Return the unit this state is expressed in."""
        return UNITS[self._cfg.sensor]
