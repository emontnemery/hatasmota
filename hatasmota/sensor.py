"""Tasmota sensor."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import string
from typing import Any

from .const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_DEEP_SLEEP,
    CONF_MAC,
    CONF_SENSOR,
    DEGREE,
    ELECTRICAL_CURRENT_AMPERE,
    ELECTRICAL_VOLT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    LENGTH_CENTIMETERS,
    LIGHT_LUX,
    MASS_KILOGRAMS,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    PRESSURE_MMHG,
    REACTIVE_ENERGY_KILO_VOLT_AMPERE_HOUR,
    REACTIVE_POWER,
    SENSOR_ACTIVE_ENERGYEXPORT,
    SENSOR_ACTIVE_ENERGYIMPORT,
    SENSOR_ACTIVE_POWERUSAGE,
    SENSOR_AMBIENT,
    SENSOR_APPARENT_POWERUSAGE,
    SENSOR_BATTERY,
    SENSOR_CCT,
    SENSOR_CF1,
    SENSOR_CF2_5,
    SENSOR_CF10,
    SENSOR_CO2,
    SENSOR_COLOR_BLUE,
    SENSOR_COLOR_GREEN,
    SENSOR_COLOR_RED,
    SENSOR_CURRENT,
    SENSOR_CURRENTNEUTRAL,
    SENSOR_DEWPOINT,
    SENSOR_DISTANCE,
    SENSOR_ECO2,
    SENSOR_ENERGY,
    SENSOR_ENERGY_OTHER,
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
    SENSOR_PHASEANGLE,
    SENSOR_PM1,
    SENSOR_PM2_5,
    SENSOR_PM10,
    SENSOR_POWERFACTOR,
    SENSOR_POWERUSAGE,
    SENSOR_PRESSURE,
    SENSOR_PRESSUREATSEALEVEL,
    SENSOR_PROXIMITY,
    SENSOR_REACTIVE_ENERGYEXPORT,
    SENSOR_REACTIVE_ENERGYIMPORT,
    SENSOR_REACTIVE_POWERUSAGE,
    SENSOR_SPEED,
    SENSOR_TEMPERATURE,
    SENSOR_TODAY,
    SENSOR_TOTAL,
    SENSOR_TOTAL_START_TIME,
    SENSOR_TVOC,
    SENSOR_UNIT_PRESSURE,
    SENSOR_UNIT_SPEED,
    SENSOR_UNIT_TEMPERATURE,
    SENSOR_VOLTAGE,
    SENSOR_WEIGHT,
    SENSOR_YESTERDAY,
    SPEED_FEET_PER_SECOND,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_KNOT,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    SPEED_YARDS_PER_SECOND,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    VOLT,
)
from .entity import TasmotaAvailability, TasmotaEntity
from .models import DiscoveryHashType, TasmotaBaseSensorConfig
from .mqtt import ReceiveMessage
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
# SENSOR_AMBIENT                  LX              "dev_cla":"illuminance"
# SENSOR_APPARENT_POWERUSAGE      VA              "dev_cla":"power"
# SENSOR_BATTERY                  %               "dev_cla":"battery"
# SENSOR_CCT                      K               "ic":"mdi:temperature-kelvin"
# SENSOR_CO2                      ppm             "ic":"mdi:molecule-co2"
# SENSOR_COLOR_BLUE               B               "ic":"mdi:palette"
# SENSOR_COLOR_GREEN              G               "ic":"mdi:palette"
# SENSOR_COLOR_RED                R               "ic":"mdi:palette"
# SENSOR_CURRENT                  A               "ic":"mdi:alpha-a-circle-outline"
# SENSOR_DEWPOINT                                 "ic":"mdi:weather-rainy"
# SENSOR_DISTANCE                 Cm              "ic":"mdi:leak"
# SENSOR_ECO2                     ppm             "ic":"mdi:molecule-co2"
# SENSOR_FREQUENCY                Hz              "ic":"mdi:current-ac"
# SENSOR_HUMIDITY                 %               "dev_cla":"humidity"
# SENSOR_ILLUMINANCE              LX              "dev_cla":"illuminance"
# SENSOR_MOISTURE                 %               "ic":"mdi:cup-water"
# SENSOR_PB0_3                    ppd             "ic":"mdi:flask"
# SENSOR_PB0_5                    ppd             "ic":"mdi:flask"
# SENSOR_PB1                      ppd             "ic":"mdi:flask"
# SENSOR_PB10                     ppd             "ic":"mdi:flask"
# SENSOR_PB2_5                    ppd             "ic":"mdi:flask"
# SENSOR_PB5                      ppd             "ic":"mdi:flask"
# SENSOR_PM1                      µg/m³           "ic":"mdi:air-filter"
# SENSOR_PM10                     µg/m³           "ic":"mdi:air-filter"
# SENSOR_PM2_5                    µg/m³           "ic":"mdi:air-filter"
# SENSOR_POWERFACTOR              Cos φ           "ic":"mdi:alpha-f-circle-outline"
# SENSOR_POWERUSAGE               W               "dev_cla":"power"
# SENSOR_PRESSURE                                 "dev_cla":"pressure"
# SENSOR_PRESSUREATSEALEVEL                       "dev_cla":"pressure"
# SENSOR_PROXIMITY                                "ic":"mdi:ruler"
# SENSOR_REACTIVE_POWERUSAGE      VAr             "dev_cla":"power"
# SENSOR_TEMPERATURE                              "dev_cla":"temperature"
# SENSOR_TODAY                    kWh             "dev_cla":"power"
# SENSOR_TOTAL                    kWh             "dev_cla":"power"
# SENSOR_TOTAL_START_TIME                         "ic":"mdi:progress-clock"
# SENSOR_TVOC                     ppb             "ic":"mdi:air-filter"
# SENSOR_VOLTAGE                  V               "ic":"mdi:alpha-v-circle-outline"
# SENSOR_WEIGHT                   Kg              "ic":"mdi:scale"
# SENSOR_YESTERDAY                kWh             "dev_cla":"power"


SENSOR_UNIT_MAP = {
    SENSOR_ACTIVE_ENERGYEXPORT: ENERGY_KILO_WATT_HOUR,
    SENSOR_ACTIVE_ENERGYIMPORT: ENERGY_KILO_WATT_HOUR,
    SENSOR_ACTIVE_POWERUSAGE: POWER_WATT,
    SENSOR_AMBIENT: LIGHT_LUX,
    SENSOR_APPARENT_POWERUSAGE: ELECTRICAL_VOLT_AMPERE,
    SENSOR_BATTERY: PERCENTAGE,
    SENSOR_CCT: TEMP_KELVIN,
    SENSOR_CF1: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SENSOR_CF10: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SENSOR_CF2_5: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SENSOR_CO2: CONCENTRATION_PARTS_PER_MILLION,
    SENSOR_COLOR_BLUE: "B",
    SENSOR_COLOR_GREEN: "G",
    SENSOR_COLOR_RED: "R",
    SENSOR_CURRENT: ELECTRICAL_CURRENT_AMPERE,
    SENSOR_CURRENTNEUTRAL: ELECTRICAL_CURRENT_AMPERE,
    SENSOR_DISTANCE: LENGTH_CENTIMETERS,
    SENSOR_ECO2: CONCENTRATION_PARTS_PER_MILLION,
    SENSOR_ENERGY: ENERGY_KILO_WATT_HOUR,
    SENSOR_FREQUENCY: FREQUENCY_HERTZ,
    SENSOR_HUMIDITY: PERCENTAGE,
    SENSOR_ILLUMINANCE: LIGHT_LUX,
    SENSOR_MOISTURE: PERCENTAGE,
    SENSOR_PB0_3: "ppd",
    SENSOR_PB0_5: "ppd",
    SENSOR_PB1: "ppd",
    SENSOR_PB10: "ppd",
    SENSOR_PB2_5: "ppd",
    SENSOR_PB5: "ppd",
    SENSOR_PHASEANGLE: DEGREE,
    SENSOR_PM1: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SENSOR_PM10: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SENSOR_PM2_5: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SENSOR_POWERFACTOR: None,
    SENSOR_POWERUSAGE: POWER_WATT,
    SENSOR_PROXIMITY: " ",
    SENSOR_REACTIVE_ENERGYEXPORT: REACTIVE_ENERGY_KILO_VOLT_AMPERE_HOUR,
    SENSOR_REACTIVE_ENERGYIMPORT: REACTIVE_ENERGY_KILO_VOLT_AMPERE_HOUR,
    SENSOR_REACTIVE_POWERUSAGE: REACTIVE_POWER,
    SENSOR_TODAY: ENERGY_KILO_WATT_HOUR,
    SENSOR_TOTAL_START_TIME: None,
    SENSOR_TOTAL: ENERGY_KILO_WATT_HOUR,
    SENSOR_TVOC: CONCENTRATION_PARTS_PER_BILLION,
    SENSOR_VOLTAGE: VOLT,
    SENSOR_WEIGHT: MASS_KILOGRAMS,
    SENSOR_YESTERDAY: ENERGY_KILO_WATT_HOUR,
}

SUPPORTED_PRESSURE_UNITS = [PRESSURE_HPA, PRESSURE_MMHG]
SUPPORTED_SPEED_UNITS = [
    SPEED_METERS_PER_SECOND,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_KNOT,
    SPEED_MILES_PER_HOUR,
    SPEED_FEET_PER_SECOND,
    SPEED_YARDS_PER_SECOND,
]
SUPPORTED_TEMPERATURE_UNITS = [TEMP_CELSIUS, TEMP_FAHRENHEIT]

SENSOR_DYNAMIC_UNIT_MAP = {
    SENSOR_DEWPOINT: (SENSOR_UNIT_TEMPERATURE, SUPPORTED_TEMPERATURE_UNITS),
    SENSOR_PRESSURE: (SENSOR_UNIT_PRESSURE, SUPPORTED_PRESSURE_UNITS),
    SENSOR_PRESSUREATSEALEVEL: (SENSOR_UNIT_PRESSURE, SUPPORTED_PRESSURE_UNITS),
    SENSOR_SPEED: (SENSOR_UNIT_SPEED, SUPPORTED_SPEED_UNITS),
    SENSOR_TEMPERATURE: (SENSOR_UNIT_TEMPERATURE, SUPPORTED_TEMPERATURE_UNITS),
}

LAST_RESET_SENSOR_MAP = {SENSOR_TOTAL: SENSOR_TOTAL_START_TIME}

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TasmotaSensorConfig(TasmotaBaseSensorConfig):
    """Tasmota Status Sensor configuration."""

    last_reset_path: list[str | int] | None
    poll_topic: str
    quantity: str
    unit: str | None
    state_topic1: str
    state_topic2: str
    value_path: list[str | int]

    @classmethod
    def from_discovery_message(
        cls,
        device_config: dict,
        sensor_config: dict,
        platform: str,
        sensor_name: str,
        value_path: list[str | int],
        parent_path: list[str | int],
        quantity: str,
    ) -> TasmotaSensorConfig:
        """Instantiate from discovery message."""
        unit = SENSOR_UNIT_MAP.get(quantity)
        if quantity in SENSOR_DYNAMIC_UNIT_MAP:
            key, supported_units = SENSOR_DYNAMIC_UNIT_MAP[quantity]
            if (unit := sensor_config[CONF_SENSOR].get(key)) not in supported_units:
                _LOGGER.warning("Unknown unit %s for %s", unit, quantity)

        if last_reset_key := LAST_RESET_SENSOR_MAP.get(quantity):
            last_reset_path = list(parent_path)
            last_reset_path.append(last_reset_key)
        else:
            last_reset_path = None

        return cls(
            endpoint="sensor",
            idx=None,
            friendly_name=sensor_name,
            last_reset_path=last_reset_path,
            mac=device_config[CONF_MAC],
            platform=platform,
            poll_payload="10",
            poll_topic=get_topic_command_status(device_config),
            availability_topic=get_topic_tele_will(device_config),
            availability_offline=config_get_state_offline(device_config),
            availability_online=config_get_state_online(device_config),
            deep_sleep_enabled=device_config[CONF_DEEP_SLEEP],
            quantity=quantity,
            state_topic1=get_topic_tele_sensor(device_config),
            state_topic2=get_topic_stat_status(device_config, 10),
            unit=unit,
            value_path=value_path,
        )

    @property
    def unique_id(self) -> str:
        """Return unique_id."""
        sensor_id = "_".join([str(i) for i in self.value_path])
        return f"{self.mac}_{self.platform}_{self.endpoint}_{sensor_id}"


class TasmotaSensor(TasmotaAvailability, TasmotaEntity):
    """Representation of Tasmota Status Sensors."""

    _cfg: TasmotaSensorConfig

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

            last_reset_path = self._cfg.last_reset_path
            if msg.topic == self._cfg.state_topic1:
                state = get_value_by_path(msg.payload, self._cfg.value_path[:-1])
                last_node = self._cfg.value_path[-1]
            if msg.topic == self._cfg.state_topic2:
                prefix: list[str | int] = ["StatusSNS"]
                value_path = prefix + self._cfg.value_path
                state = get_value_by_path(msg.payload, value_path[:-1])
                last_node = value_path[-1]
                if self._cfg.last_reset_path:
                    last_reset_path = prefix + self._cfg.last_reset_path
            if state is not None:
                # Indexed sensors may be announced with more indices than present in
                # the status. Handle this gracefully wihtout throwing. This is a
                # workaround for energy sensors which are announced with multiple phases
                # but where the actual sensor sends updates with fewer phases.
                kwargs = {}
                try:
                    if hasattr(state, "__getitem__"):
                        state = state[last_node]
                    elif last_node != 0:
                        return
                except (IndexError, KeyError):
                    return
                if last_reset_path:
                    if last_reset := get_value_by_path(msg.payload, last_reset_path):
                        kwargs["last_reset"] = last_reset
                self._on_state_callback(state, **kwargs)

        availability_topics = self.get_availability_topics()
        topics = {
            # Periodic state update (tele/Sensor)
            "state_topic1": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic1,
                "msg_callback": state_message_received,
            },
            # Polled state update (stat/STATUS10)
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

    async def unsubscribe_topics(self) -> None:
        """Unsubscribe to all MQTT topics."""
        self._sub_state = await self._mqtt_client.unsubscribe(self._sub_state)

    @property
    def quantity(self) -> str:
        """Return the sensor's quantity (speed, mass, etc.)."""
        return self._cfg.quantity

    @property
    def unit(self) -> str | None:
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
def _get_sensor_entity(
    sensor_discovery_message: dict,
    device_discovery_msg: dict,
    sensor_path: list[str | int],
    parent_path: list[str | int],
    quantity: str,
) -> tuple[TasmotaSensorConfig, DiscoveryHashType]:
    sensorname = " ".join([str(i) for i in sensor_path])
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
        sensor_path,
        parent_path,
        quantity,
    )
    return (sensor_config, discovery_hash)


def _get_quantity(
    sensorkey: str,
    subsensorkey: str,
    subsubsensorkey: str | None,
) -> str:
    """Get quantity, for example temperature, of a sensor."""
    if sensorkey in ["AS3935", "LD2410"] and subsensorkey == SENSOR_ENERGY:
        # The AS3935 and LD2410 sensor have energy readings which are not in kWh
        # LD2410: Energy in a range 0..100
        # AS3935: Lightning energy in no specified unit
        return SENSOR_ENERGY_OTHER
    if subsubsensorkey in SENSOR_UNIT_MAP:
        # Handle cases where the types of the inner sensors differ
        # {"ANALOG": {"CTEnergy1": {"Power":2300,"Voltage":230,"Current":10}}}
        return subsubsensorkey
    if sensorkey == "ANALOG":
        # Sensors under ANALOG are suffixed by ADC pin number on the ESP32
        if subsensorkey[-1] in string.digits:
            return subsensorkey[0:-1]
    return subsensorkey


def get_sensor_entities(
    sensor_discovery_message: dict, device_discovery_msg: dict
) -> list[tuple[TasmotaBaseSensorConfig, DiscoveryHashType]]:
    """Generate sensor configuration."""
    sensor_configs: list[tuple[TasmotaBaseSensorConfig, DiscoveryHashType]] = []
    for sensorkey, sensor in sensor_discovery_message[CONF_SENSOR].items():
        sensorpath = [sensorkey]
        if sensorkey in IGNORED_SENSORS or not isinstance(sensor, dict):
            continue
        for subsensorkey, subsensor in sensor.items():
            subsensorpath = list(sensorpath)
            subsensorpath.append(subsensorkey)
            if isinstance(subsensor, dict):
                # Nested sensor
                for subsubsensorkey in subsensor.keys():
                    subsubsensorpath = list(subsensorpath)
                    subsubsensorpath.append(subsubsensorkey)
                    sensor_configs.append(
                        _get_sensor_entity(
                            sensor_discovery_message,
                            device_discovery_msg,
                            subsubsensorpath,
                            subsubsensorpath[:-1],
                            _get_quantity(sensorkey, subsensorkey, subsubsensorkey),
                        )
                    )
            elif isinstance(subsensor, list):
                # Array sensor
                for idx, _ in enumerate(subsensor):
                    subsubsensorpath = list(subsensorpath)
                    subsubsensorpath.append(idx)
                    sensor_configs.append(
                        _get_sensor_entity(
                            sensor_discovery_message,
                            device_discovery_msg,
                            subsubsensorpath,
                            subsensorpath[:-1],
                            _get_quantity(sensorkey, subsensorkey, None),
                        )
                    )
            else:
                # Simple sensor
                sensor_configs.append(
                    _get_sensor_entity(
                        sensor_discovery_message,
                        device_discovery_msg,
                        subsensorpath,
                        subsensorpath[:-1],
                        _get_quantity(sensorkey, subsensorkey, None),
                    )
                )

    return sensor_configs
