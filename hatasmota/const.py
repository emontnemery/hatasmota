"""Tasmota constants."""
from typing import Final

AUTOMATION_TYPE_TRIGGER: Final = "trigger"

COMMAND_BACKLOG: Final = "Backlog"
COMMAND_CHANNEL: Final = "Channel"
COMMAND_COLOR: Final = "Color"
COMMAND_CT: Final = "CT"
COMMAND_DIMMER: Final = "Dimmer"
COMMAND_FADE: Final = "Fade2"
COMMAND_FANSPEED: Final = "FanSpeed"
COMMAND_POWER: Final = "Power"
COMMAND_SCHEME: Final = "Scheme"
COMMAND_SHUTTER_CLOSE: Final = "ShutterClose"
COMMAND_SHUTTER_OPEN: Final = "ShutterOpen"
COMMAND_SHUTTER_POSITION: Final = "ShutterPosition"
COMMAND_SHUTTER_STOP: Final = "ShutterStop"
COMMAND_SHUTTER_TILT: Final = "ShutterTilt"
COMMAND_SPEED: Final = "Speed2"
COMMAND_WHITE: Final = "White"

CONF_BUTTON: Final = "btn"
CONF_DEVICENAME: Final = "dn"
CONF_FRIENDLYNAME: Final = "fn"
CONF_FULLTOPIC: Final = "ft"
CONF_IFAN: Final = "if"
CONF_IP: Final = "ip"
CONF_HOSTNAME: Final = "hn"
CONF_MAC: Final = "mac"
CONF_LIGHT_SUBTYPE: Final = "lt_st"
CONF_LINK_RGB_CT: Final = "lk"  # RGB + white channels linked to a single light
CONF_MODEL: Final = "md"
CONF_OFFLINE: Final = "ofln"
CONF_ONLINE: Final = "onln"
CONF_OPTIONS: Final = "so"
CONF_PREFIX: Final = "tp"
CONF_SENSOR: Final = "sn"
CONF_SHUTTER_OPTIONS: Final = "sho"
CONF_SHUTTER_TILT: Final = "sht"
CONF_STATE: Final = "state"
CONF_RELAY: Final = "rl"
CONF_SW_VERSION: Final = "sw"
CONF_SWITCH: Final = "swc"
CONF_SWITCHNAME: Final = "swn"
CONF_TOPIC: Final = "t"
CONF_TUYA: Final = "ty"
CONF_VERSION: Final = "ver"

CONF_MANUFACTURER: Final = "manufacturer"
CONF_NAME: Final = "name"

FAN_SPEED_OFF: Final = 0
FAN_SPEED_LOW: Final = 1
FAN_SPEED_MEDIUM: Final = 2
FAN_SPEED_HIGH: Final = 3

LST_NONE: Final = 0
LST_SINGLE: Final = 1
LST_COLDWARM: Final = 2
LST_RGB: Final = 3
LST_RGBW: Final = 4
LST_RGBCW: Final = 5

# fmt: off
OPTION_MQTT_RESPONSE: Final = "4"          # Return MQTT response as RESULT or %COMMAND%
OPTION_BUTTON_SWAP: Final = "11"           # Swap button single and double press functionality
OPTION_BUTTON_SINGLE: Final = "13"         # Allow immediate action on single button press
OPTION_DECIMAL_TEXT: Final = "17"          # Show Color string as hex or comma-separated
OPTION_NOT_POWER_LINKED: Final = "20"      # Update of Dimmer/Color/CT without turning power on
OPTION_HASS_LIGHT: Final = "30"            # Enforce Home Assistant auto-discovery as light
OPTION_PWM_MULTI_CHANNELS: Final = "68"    # Multi-channel PWM instead of a single light
OPTION_MQTT_BUTTONS: Final = "73"          # Enable Buttons decoupling and send multi-press and hold MQTT messages
OPTION_SHUTTER_MODE: Final = "80"          # Blinds and shutters support; removed in Tasmota 9.0.0.4
OPTION_REDUCED_CT_RANGE: Final = "82"      # Reduce the CT range from 153..500 to 200.380
OPTION_MQTT_SWITCHES: Final = "114"        # Enable sending switch MQTT messages
OPTION_FADE_FIXED_DURATION: Final = "117"  # Run fading at fixed duration instead of fixed slew rate
# fmt: on

PREFIX_CMND: Final = 0
PREFIX_STAT: Final = 1
PREFIX_TELE: Final = 2

RL_NONE: Final = 0
RL_RELAY: Final = 1
RL_LIGHT: Final = 2
RL_SHUTTER: Final = 3

RSLT_ACTION: Final = "Action"
RSLT_POWER: Final = "POWER"
RSLT_SHUTTER: Final = "Shutter"
RSLT_STATE: Final = "STATE"
RSLT_TRIG: Final = "TRIG"

SENSOR_ATTRIBUTE_RSSI: Final = "RSSI"
SENSOR_ATTRIBUTE_UPTIME: Final = "Uptime"
SENSOR_ATTRIBUTE_SIGNAL: Final = "Signal"
SENSOR_ATTRIBUTE_WIFI_LINKCOUNT: Final = "LinkCount"
SENSOR_ATTRIBUTE_WIFI_DOWNTIME: Final = "Downtime"
SENSOR_ATTRIBUTE_MQTTCOUNT: Final = "MqttCount"

SENSOR_TEMPERATURE: Final = "Temperature"
SENSOR_DEWPOINT: Final = "DewPoint"
SENSOR_PRESSURE: Final = "Pressure"
SENSOR_PRESSUREATSEALEVEL: Final = "SeaPressure"
SENSOR_APPARENT_POWERUSAGE: Final = "ApparentPower"
SENSOR_BATTERY: Final = "Battery"
SENSOR_CURRENT: Final = "Current"
SENSOR_CURRENTNEUTRAL: Final = "CurrentNeutral"
SENSOR_DISTANCE: Final = "Distance"
SENSOR_FREQUENCY: Final = "Frequency"
SENSOR_HUMIDITY: Final = "Humidity"
SENSOR_ILLUMINANCE: Final = "Illuminance"
SENSOR_MOISTURE: Final = "Moisture"
SENSOR_PB0_3: Final = "PB0.3"
SENSOR_PB0_5: Final = "PB0.5"
SENSOR_PB1: Final = "PB1"
SENSOR_PB2_5: Final = "PB2.5"
SENSOR_PB5: Final = "PB5"
SENSOR_PB10: Final = "PB10"
SENSOR_PM1: Final = "PM1"
SENSOR_PM2_5: Final = "PM2.5"
SENSOR_PM10: Final = "PM10"
SENSOR_CF1: Final = "CF1"
SENSOR_CF2_5: Final = "CF2.5"
SENSOR_CF10: Final = "CF10"
SENSOR_PHASEANGLE: Final = "PhaseAngle"
SENSOR_POWERFACTOR: Final = "Factor"
SENSOR_POWERUSAGE: Final = "Power"
SENSOR_SPEED: Final = "Speed"
SENSOR_TOTAL_START_TIME: Final = "TotalStartTime"
SENSOR_ACTIVE_POWERUSAGE: Final = "ActivePower"
SENSOR_REACTIVE_POWERUSAGE: Final = "ReactivePower"
SENSOR_TODAY: Final = "Today"
SENSOR_TOTAL: Final = "Total"
SENSOR_VOLTAGE: Final = "Voltage"
SENSOR_WEIGHT: Final = "Weight"
SENSOR_YESTERDAY: Final = "Yesterday"
SENSOR_ENERGY: Final = "Energy"
SENSOR_ACTIVE_ENERGYEXPORT: Final = "ExportActive"
SENSOR_ACTIVE_ENERGYIMPORT: Final = "ImportActive"
SENSOR_REACTIVE_ENERGYEXPORT: Final = "ExportReactive"
SENSOR_REACTIVE_ENERGYIMPORT: Final = "ImportReactive"
SENSOR_CO2: Final = "CarbonDioxide"
SENSOR_ECO2: Final = "eCO2"
SENSOR_TVOC: Final = "TVOC"
SENSOR_COLOR_RED: Final = "Red"
SENSOR_COLOR_GREEN: Final = "Green"
SENSOR_COLOR_BLUE: Final = "Blue"
SENSOR_CCT: Final = "CCT"
SENSOR_PROXIMITY: Final = "Proximity"
SENSOR_AMBIENT: Final = "Ambient"
SENSOR_SWITCH: Final = "Switch"
SENSOR_STATUS_IP: Final = "status_ip"
SENSOR_STATUS_LAST_RESTART_TIME: Final = "last_restart_time"
SENSOR_STATUS_LINK_COUNT: Final = "status_link_count"
SENSOR_STATUS_MQTT_COUNT: Final = "status_mqtt_count"
SENSOR_STATUS_RESTART_REASON: Final = "status_restart_reason"
SENSOR_STATUS_RSSI: Final = "status_rssi"
SENSOR_STATUS_SIGNAL: Final = "status_signal"
SENSOR_STATUS_SSID: Final = "status_ssid"
SENSOR_STATUS_VERSION: Final = "status_version"

SENSOR_UNIT_PRESSURE: Final = "PressureUnit"
SENSOR_UNIT_SPEED: Final = "SpeedUnit"
SENSOR_UNIT_TEMPERATURE: Final = "TempUnit"

SHUTTER_DIRECTION: Final = "Direction"
SHUTTER_DIRECTION_DOWN: Final = -1
SHUTTER_DIRECTION_STOP: Final = 0
SHUTTER_DIRECTION_UP: Final = 1
SHUTTER_POSITION: Final = "Position"
SHUTTER_TILT: Final = "Tilt"

SHUTTER_OPTION_INVERT: Final = 1

# #### UNITS OF MEASUREMENT ####
# Power units
POWER_WATT: Final = "W"

# Voltage units
VOLT: Final = "V"

# Energy units
ENERGY_WATT_HOUR: Final = f"{POWER_WATT}h"
ENERGY_KILO_WATT_HOUR: Final = f"k{ENERGY_WATT_HOUR}"

# Electrical units
ELECTRICAL_CURRENT_AMPERE: Final = "A"
ELECTRICAL_VOLT_AMPERE: Final = f"{VOLT}{ELECTRICAL_CURRENT_AMPERE}"

# Temperature units
TEMP_CELSIUS: Final = "C"
TEMP_FAHRENHEIT: Final = "F"
TEMP_KELVIN: Final = "K"

# Degree units
DEGREE: Final = "°"

# Time units
TIME_SECONDS: Final = "s"
TIME_HOURS: Final = "h"

# Length units
LENGTH_CENTIMETERS: Final = "cm"
LENGTH_METERS: Final = "m"
LENGTH_KILOMETERS: Final = "km"

# Frequency units
FREQUENCY_HERTZ: Final = "Hz"

# Pressure units
PRESSURE_HPA: Final = "hPa"
PRESSURE_MMHG: Final = "mmHg"

# Volume units
VOLUME_CUBIC_METERS: Final = f"{LENGTH_METERS}³"

# Mass units
MASS_KILOGRAMS: Final = "kg"
MASS_MICROGRAMS: Final = "µg"

# Light units
LIGHT_LUX: Final = "lux"

# Percentage units
PERCENTAGE: Final = "%"

# Concentration units
CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = (
    f"{MASS_MICROGRAMS}/{VOLUME_CUBIC_METERS}"
)
CONCENTRATION_PARTS_PER_MILLION: Final = "ppm"
CONCENTRATION_PARTS_PER_BILLION: Final = "ppb"

# Speed units
SPEED_METERS_PER_SECOND: Final = f"{LENGTH_METERS}/{TIME_SECONDS}"
SPEED_KILOMETERS_PER_HOUR: Final = f"{LENGTH_KILOMETERS}/{TIME_HOURS}"
SPEED_KNOT: Final = "kn"
SPEED_MILES_PER_HOUR: Final = "mph"
SPEED_FEET_PER_SECOND: Final = "ft/s"
SPEED_YARDS_PER_SECOND: Final = "yd/s"

# Signal_strength units
SIGNAL_STRENGTH_DECIBELS: Final = "dB"
SIGNAL_STRENGTH_DECIBELS_MILLIWATT: Final = "dBm"

STATE_OFF: Final = 0
STATE_ON: Final = 1
STATE_TOGGLE: Final = 2
STATE_HOLD: Final = 3

STATUS_SENSOR: Final = "StatusSNS"

SWITCHMODE_NONE: Final = -1
SWITCHMODE_TOGGLE: Final = 0
SWITCHMODE_FOLLOW: Final = 1
SWITCHMODE_FOLLOW_INV: Final = 2
SWITCHMODE_PUSHBUTTON: Final = 3
SWITCHMODE_PUSHBUTTON_INV: Final = 4
SWITCHMODE_PUSHBUTTONHOLD: Final = 5
SWITCHMODE_PUSHBUTTONHOLD_INV: Final = 6
SWITCHMODE_PUSHBUTTON_TOGGLE: Final = 7
SWITCHMODE_TOGGLEMULTI: Final = 8
SWITCHMODE_FOLLOWMULTI: Final = 9
SWITCHMODE_FOLLOWMULTI_INV: Final = 10
SWITCHMODE_PUSHHOLDMULTI: Final = 11
SWITCHMODE_PUSHHOLDMULTI_INV: Final = 12
SWITCHMODE_PUSHON: Final = 13
SWITCHMODE_PUSHON_INV: Final = 14
SWITCHMODE_PUSH_IGNORE: Final = 15
