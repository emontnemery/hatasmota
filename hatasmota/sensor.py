"""Tasmota sensor."""
import logging

import attr

from .const import (
    CONF_MAC,
    CONF_SENSOR,
    SENSOR_AMBIENT,
    SENSOR_APPARENT_POWERUSAGE,
    SENSOR_BATTERY,
    SENSOR_CCT,
    SENSOR_CO2,
    SENSOR_COLOR_BLUE,
    SENSOR_COLOR_GREEN,
    SENSOR_COLOR_RED,
    SENSOR_CURRENT,
    SENSOR_DEWPOINT,
    SENSOR_DISTANCE,
    SENSOR_ECO2,
    SENSOR_FREQUENCY,
    SENSOR_HUMIDITY,
    SENSOR_ILLUMINANCE,
    SENSOR_MOISTURE,
    SENSOR_PB0_3,
    SENSOR_PB0_5,
    SENSOR_PB1,
    SENSOR_PB2_5,
    SENSOR_PB5,
    SENSOR_PB10,
    SENSOR_PM1,
    SENSOR_PM2_5,
    SENSOR_PM10,
    SENSOR_POWERFACTOR,
    SENSOR_POWERUSAGE,
    SENSOR_PRESSURE,
    SENSOR_PRESSUREATSEALEVEL,
    SENSOR_PROXIMITY,
    SENSOR_REACTIVE_POWERUSAGE,
    SENSOR_TEMPERATURE,
    SENSOR_TODAY,
    SENSOR_TOTAL,
    SENSOR_TOTAL_START_TIME,
    SENSOR_TVOC,
    SENSOR_UNIT_PRESSURE,
    SENSOR_UNIT_TEMPERATURE,
    SENSOR_VOLTAGE,
    SENSOR_WEIGHT,
    SENSOR_YESTERDAY,
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
    get_topic_command_status,
    get_topic_stat_status,
    get_topic_tele_sensor,
    get_topic_tele_will,
    get_value_by_path,
)

IGNORED_SENSORS = ["Time", "PN532", "RDM6300"]

# QUANTITY                        UNIT            CLASS/ICON
# SENSOR_TEMPERATURE                              "dev_cla":"temperature"
# SENSOR_DEWPOINT                                 "ic":"mdi:weather-rainy"
# SENSOR_PRESSURE                                 "dev_cla":"pressure"
# SENSOR_PRESSUREATSEALEVEL                       "dev_cla":"pressure"
# SENSOR_APPARENT_POWERUSAGE      VA              "dev_cla":"power"
# SENSOR_BATTERY                  %               "dev_cla":"battery"
# SENSOR_CURRENT                  A               "ic":"mdi:alpha-a-circle-outline"
# SENSOR_DISTANCE                 Cm              "ic":"mdi:leak"
# SENSOR_FREQUENCY                Hz              "ic":"mdi:current-ac"
# SENSOR_HUMIDITY                 %               "dev_cla":"humidity"
# SENSOR_ILLUMINANCE              LX              "dev_cla":"illuminance"
# SENSOR_MOISTURE                 %               "ic":"mdi:cup-water"
# SENSOR_PB0_3                    ppd             "ic":"mdi:flask"
# SENSOR_PB0_5                    ppd             "ic":"mdi:flask"
# SENSOR_PB1                      ppd             "ic":"mdi:flask"
# SENSOR_PB2_5                    ppd             "ic":"mdi:flask"
# SENSOR_PB5                      ppd             "ic":"mdi:flask"
# SENSOR_PB10                     ppd             "ic":"mdi:flask"
# SENSOR_PM1                      µg/m³           "ic":"mdi:air-filter"
# SENSOR_PM2_5                    µg/m³           "ic":"mdi:air-filter"
# SENSOR_PM10                     µg/m³           "ic":"mdi:air-filter"
# SENSOR_POWERFACTOR              Cos φ           "ic":"mdi:alpha-f-circle-outline"
# SENSOR_POWERUSAGE               W               "dev_cla":"power"
# SENSOR_TOTAL_START_TIME                         "ic":"mdi:progress-clock"
# SENSOR_REACTIVE_POWERUSAGE      VAr             "dev_cla":"power"
# SENSOR_TODAY                    kWh             "dev_cla":"power"
# SENSOR_TOTAL                    kWh             "dev_cla":"power"
# SENSOR_VOLTAGE                  V               "ic":"mdi:alpha-v-circle-outline"
# SENSOR_WEIGHT                   Kg              "ic":"mdi:scale"
# SENSOR_YESTERDAY                kWh             "dev_cla":"power"
# SENSOR_CO2                      ppm             "ic":"mdi:molecule-co2"
# SENSOR_ECO2                     ppm             "ic":"mdi:molecule-co2"
# SENSOR_TVOC                     ppb             "ic":"mdi:air-filter"
# SENSOR_COLOR_RED                R               "ic":"mdi:palette"
# SENSOR_COLOR_GREEN              G               "ic":"mdi:palette"
# SENSOR_COLOR_BLUE               B               "ic":"mdi:palette"
# SENSOR_CCT                      K               "ic":"mdi:temperature-kelvin"
# SENSOR_PROXIMITY                                "ic":"mdi:ruler"
# SENSOR_AMBIENT                  LX              "dev_cla":"illuminance"


SENSOR_UNIT_MAP = {
    SENSOR_APPARENT_POWERUSAGE: "VA",
    SENSOR_BATTERY: "%",
    SENSOR_CURRENT: "A",
    SENSOR_DISTANCE: "cm",
    SENSOR_FREQUENCY: "Hz",
    SENSOR_HUMIDITY: "%",
    SENSOR_ILLUMINANCE: "lux",
    SENSOR_MOISTURE: "%",
    SENSOR_PB0_3: "ppd",
    SENSOR_PB0_5: "ppd",
    SENSOR_PB1: "ppd",
    SENSOR_PB2_5: "ppd",
    SENSOR_PB5: "ppd",
    SENSOR_PB10: "ppd",
    SENSOR_PM1: "µg/m³",
    SENSOR_PM2_5: "µg/m³",
    SENSOR_PM10: "µg/m³",
    SENSOR_POWERFACTOR: "Cos φ",
    SENSOR_POWERUSAGE: "W",
    SENSOR_TOTAL_START_TIME: " ",
    SENSOR_REACTIVE_POWERUSAGE: "VAr",
    SENSOR_TODAY: "kWh",
    SENSOR_TOTAL: "kWh",
    SENSOR_VOLTAGE: "V",
    SENSOR_WEIGHT: "kg",
    SENSOR_YESTERDAY: "kWh",
    SENSOR_CO2: "ppm",
    SENSOR_ECO2: "ppm",
    SENSOR_TVOC: "ppb",
    SENSOR_COLOR_RED: "R",
    SENSOR_COLOR_GREEN: "G",
    SENSOR_COLOR_BLUE: "B",
    SENSOR_CCT: "K",
    SENSOR_PROXIMITY: " ",
    SENSOR_AMBIENT: "lux",
}

SENSOR_DYNAMIC_UNIT_MAP = {
    SENSOR_TEMPERATURE: SENSOR_UNIT_TEMPERATURE,
    SENSOR_DEWPOINT: SENSOR_UNIT_TEMPERATURE,
    SENSOR_PRESSURE: SENSOR_UNIT_PRESSURE,
    SENSOR_PRESSUREATSEALEVEL: SENSOR_UNIT_PRESSURE,
}

_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class TasmotaSensorConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota switch configuation."""

    poll_topic: str = attr.ib()
    quantity: str = attr.ib()
    unit: str = attr.ib()
    state_topic1: str = attr.ib()
    state_topic2: str = attr.ib()
    value_path: str = attr.ib()

    @classmethod
    def from_discovery_message(
        cls, device_config, sensor_config, platform, sensor_name, value_path
    ):
        """Instantiate from discovery message."""
        quantity = value_path[-1]
        unit = SENSOR_UNIT_MAP.get(quantity)
        if quantity in SENSOR_DYNAMIC_UNIT_MAP:
            unit = sensor_config[CONF_SENSOR].get(SENSOR_DYNAMIC_UNIT_MAP[quantity])

        return cls(
            endpoint="sensor",
            idx=None,
            friendly_name=sensor_name,
            mac=device_config[CONF_MAC],
            platform=platform,
            poll_payload="8",
            poll_topic=get_topic_command_status(device_config),
            availability_topic=get_topic_tele_will(device_config),
            availability_offline=config_get_state_offline(device_config),
            availability_online=config_get_state_online(device_config),
            quantity=quantity,
            state_topic1=get_topic_tele_sensor(device_config),
            state_topic2=get_topic_stat_status(device_config, 8),
            unit=unit,
            value_path=value_path,
        )

    @property
    def unique_id(self):
        """Return unique_id."""
        sensor_id = "_".join(self.value_path)
        return f"{self.mac}_{self.platform}_{self.endpoint}_{sensor_id}"


class TasmotaSensor(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota switch."""

    def __init__(self, **kwds):
        """Initialize."""
        self._sub_state = None
        super().__init__(**kwds)

    async def subscribe_topics(self):
        """Subscribe to topics."""

        def state_message_received(msg):
            """Handle new MQTT state messages."""
            if msg.topic == self._cfg.state_topic1:
                state = get_value_by_path(msg.payload, self._cfg.value_path)
            if msg.topic == self._cfg.state_topic2:
                value_path = ["StatusSNS"] + self._cfg.value_path
                state = get_value_by_path(msg.payload, value_path)
            if state is not None:
                self._on_state_callback(state)

        availability_topics = self.get_availability_topics()
        topics = {
            # Periodic state update (tele/Sensor)
            "state_topic1": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic1,
                "msg_callback": state_message_received,
            },
            # Polled state update (stat/STATUS8)
            "state_topic2": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic2,
                "msg_callback": state_message_received,
            },
        }
        topics = {**topics, **availability_topics}

        self._sub_state = await self._mqtt_client.subscribe(
            self._sub_state,
            topics,
        )

    async def unsubscribe_topics(self):
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    @property
    def quantity(self):
        """Return the sensors quantity (speed, mass, etc.)."""
        return self._cfg.quantity

    @property
    def unit(self):
        """Return the unit this state is expressed in."""
        return self._cfg.unit


# Simple sensor:
# {"INA219":{"Voltage":4.494,"Current":0.020,"Power":0.089}}
# Array sensor:
# {"ENERGY":
#   {
#     "TotalStartTime":"2018-11-23T15:33:47",
#     "Total":0.017,
#     "TotalTariff":[0.000,0.017],
#     "Yesterday":0.000,
#     "Today":0.002,
#     "ExportActive":0.000,
#     "ExportTariff":[0.000,0.000],
#     "Period":0.00,
#     "Power":0.00,
#     "ApparentPower":7.84,
#     "ReactivePower":-7.21,
#     "Factor":0.39,
#     "Frequency":50.0,
#     "Voltage":234.31,
#     "Current":0.039,
#     "ImportActive":12.580,
#     "ImportReactive":0.002,
#     "ExportReactive":39.131,
#     "PhaseAngle":290.45}}
# Nested sensor:
# {
#   "Time":"2020-03-03T00:00:00+00:00",
#   "TX23":{
#     "Speed":{"Act":14.8,"Avg":8.5,"Min":12.2,"Max":14.8},
#     "Dir":{"Card":"WSW","Deg":247.5,"Avg":266.1,"AvgCard":"W","Min":247.5,"Max":247.5,"Range":0}
#   },
#   "SpeedUnit":"km/h"
# }
def get_sensor_entities(sensor_discovery_message, device_discovery_msg):
    """Generate sensor configuration."""
    sensor_configs = []
    for sensorkey, sensor in sensor_discovery_message[CONF_SENSOR].items():
        sensorpath = [sensorkey]
        if sensorkey in IGNORED_SENSORS or not isinstance(sensor, dict):
            continue
        for subsensorkey, subsensor in sensor.items():
            subsensorpath = list(sensorpath)
            subsensorpath.append(subsensorkey)
            if isinstance(subsensor, dict):
                # Nested sensor
                pass
            elif isinstance(subsensor, list):
                # Array sensor
                pass
            else:
                # Quantity
                sensorname = " ".join(subsensorpath)
                discovery_hash = (
                    device_discovery_msg[CONF_MAC],
                    "sensor",
                    "sensor",
                    sensorname,
                )
                sensor_config = TasmotaSensorConfig.from_discovery_message(
                    device_discovery_msg,
                    sensor_discovery_message,
                    "sensor",
                    sensorname,
                    subsensorpath,
                )
                sensor_configs.append((sensor_config, discovery_hash))

    return sensor_configs
