"""Tasmota binary sensor."""
import logging

import attr

from .const import (
    CONF_MAC,
    CONF_STATE,
    CONF_SWITCH,
    RSLT_ACTION,
    STATE_HOLD,
    STATE_TOGGLE,
    STATUS_SENSOR,
    SWITCHMODE_FOLLOW,
    SWITCHMODE_FOLLOW_INV,
    SWITCHMODE_FOLLOWMULTI,
    SWITCHMODE_FOLLOWMULTI_INV,
    SWITCHMODE_NONE,
    SWITCHMODE_PUSHBUTTON,
    SWITCHMODE_PUSHBUTTON_INV,
    SWITCHMODE_PUSHBUTTON_TOGGLE,
    SWITCHMODE_PUSHBUTTONHOLD,
    SWITCHMODE_PUSHBUTTONHOLD_INV,
    SWITCHMODE_PUSHHOLDMULTI,
    SWITCHMODE_PUSHHOLDMULTI_INV,
    SWITCHMODE_PUSHON,
    SWITCHMODE_PUSHON_INV,
    SWITCHMODE_TOGGLE,
    SWITCHMODE_TOGGLEMULTI,
)
from .entity import (
    TasmotaAvailability,
    TasmotaAvailabilityConfig,
    TasmotaEntity,
    TasmotaEntityConfig,
)
from .trigger import TasmotaTrigger
from .utils import (
    config_get_state_offline,
    config_get_state_online,
    config_get_state_power_off,
    config_get_state_power_on,
    config_get_switchfriendlyname,
    config_get_switchname,
    get_topic_command_status,
    get_topic_stat_result,
    get_topic_stat_status,
    get_topic_tele_sensor,
    get_topic_tele_will,
    get_value_by_path,
)

_LOGGER = logging.getLogger(__name__)

# switch matrix for triggers and binary sensor generation when switchtopic is set as custom (default index is 0,0 - TOGGLE, TOGGLE):
#  SWITCHMODE    INTERNAL              BINARY        STATE -> PRESS                STATE -> DOUBLE PRESS       STATE -> LONG_PRESS         T,H
#  0             TOGGLE                NO            TOGGLE (button_short_press)   NONE                        NONE                        1,0
#  1             FOLLOW                YES           NONE                          NONE                        NONE                        0,0
#  2             FOLLOW_INV            YES           NONE                          NONE                        NONE                        0,0
#  3             PUSHBUTTON            YES           TOGGLE (button_short_press)   NONE                        NONE                        1,0
#  4             PUSHBUTTON_INV        YES           TOGGLE (button_short_press)   NONE                        NONE                        1,0
#  5             PUSHBUTTONHOLD        YES           TOGGLE (button_short_press)   NONE                        HOLD (button_long_press)    1,2
#  6             PUSHBUTTONHOLD_INV    YES           TOGGLE (button_short_press)   NONE                        HOLD (button_long_press)    1,2
#  7             PUSHBUTTON_TOGGLE     NO            TOGGLE (button_short_press)   NONE                        NONE                        1,0
#  8             TOGGLEMULTI           NO            TOGGLE (button_short_press)   HOLD (button_double_press)  NONE                        1,3
#  9             FOLLOWMULTI           YES           NONE                          HOLD (button_double_press)  NONE                        0,3
# 10             FOLLOWMULTI_INV       YES           NONE                          HOLD (button_double_press)  NONE                        0,3
# 11             PUSHHOLDMULTI         NO            TOGGLE (button_short_press)   NONE                        INC_DEC (button_long_press) 1,0
#                                                    INV (not available)                                       CLEAR (not available)
# 12             PUSHHOLDMULTI_INV     NO            TOGGLE (button_short_press)   NONE                        CLEAR (button_long_press)   1,0
#                                                    INV (not available)                                       INC_DEC (not available)
# 13             PUSHON                YES (PIR)     NONE                          NONE                        NONE                        0,0
# 14             PUSHON_INV            YES (PIR)     NONE                          NONE                        NONE                        0,0
# Please note: SwitchMode11 and 12 will register just TOGGLE (button_short_press)
# Trigger types: "0 = none | 1 = button_short_press | 2 = button_long_press | 3 = button_double_press";
# PIR: automatic off after 1 second

SW_TRIG_DOUBLE = "button_double_press"
SW_TRIG_LONG = "button_long_press"
SW_TRIG_NONE = "none"
SW_TRIG_SHORT = "button_short_press"

SWITCHMODE_MAP = {
    SWITCHMODE_NONE: (
        False,
        None,
        {STATE_TOGGLE: SW_TRIG_NONE, STATE_HOLD: SW_TRIG_NONE},
    ),
    SWITCHMODE_TOGGLE: (
        False,
        None,
        {STATE_TOGGLE: SW_TRIG_SHORT, STATE_HOLD: SW_TRIG_NONE},
    ),
    SWITCHMODE_FOLLOW: (
        True,
        None,
        {STATE_TOGGLE: SW_TRIG_NONE, STATE_HOLD: SW_TRIG_NONE},
    ),
    SWITCHMODE_FOLLOW_INV: (
        True,
        None,
        {STATE_TOGGLE: SW_TRIG_NONE, STATE_HOLD: SW_TRIG_NONE},
    ),
    SWITCHMODE_PUSHBUTTON: (
        True,
        None,
        {STATE_TOGGLE: SW_TRIG_SHORT, STATE_HOLD: SW_TRIG_NONE},
    ),
    SWITCHMODE_PUSHBUTTON_INV: (
        True,
        None,
        {STATE_TOGGLE: SW_TRIG_SHORT, STATE_HOLD: SW_TRIG_NONE},
    ),
    SWITCHMODE_PUSHBUTTONHOLD: (
        True,
        None,
        {STATE_TOGGLE: SW_TRIG_SHORT, STATE_HOLD: SW_TRIG_LONG},
    ),
    SWITCHMODE_PUSHBUTTONHOLD_INV: (
        True,
        None,
        {STATE_TOGGLE: SW_TRIG_SHORT, STATE_HOLD: SW_TRIG_LONG},
    ),
    SWITCHMODE_PUSHBUTTON_TOGGLE: (
        False,
        None,
        {STATE_TOGGLE: SW_TRIG_SHORT, STATE_HOLD: SW_TRIG_NONE},
    ),
    SWITCHMODE_TOGGLEMULTI: (
        False,
        None,
        {STATE_TOGGLE: SW_TRIG_SHORT, STATE_HOLD: SW_TRIG_DOUBLE},
    ),
    SWITCHMODE_FOLLOWMULTI: (
        True,
        None,
        {STATE_TOGGLE: SW_TRIG_NONE, STATE_HOLD: SW_TRIG_DOUBLE},
    ),
    SWITCHMODE_FOLLOWMULTI_INV: (
        True,
        None,
        {STATE_TOGGLE: SW_TRIG_NONE, STATE_HOLD: SW_TRIG_DOUBLE},
    ),
    SWITCHMODE_PUSHHOLDMULTI: (
        False,
        None,
        {STATE_TOGGLE: SW_TRIG_SHORT, STATE_HOLD: SW_TRIG_NONE},
    ),
    SWITCHMODE_PUSHHOLDMULTI_INV: (
        False,
        None,
        {STATE_TOGGLE: SW_TRIG_SHORT, STATE_HOLD: SW_TRIG_NONE},
    ),
    SWITCHMODE_PUSHON: (
        True,
        1,
        {STATE_TOGGLE: SW_TRIG_NONE, STATE_HOLD: SW_TRIG_NONE},
    ),
    SWITCHMODE_PUSHON_INV: (
        True,
        1,
        {STATE_TOGGLE: SW_TRIG_NONE, STATE_HOLD: SW_TRIG_NONE},
    ),
}

NO_POLL_SWITCHMODES = [SWITCHMODE_PUSHON, SWITCHMODE_PUSHON_INV]


@attr.s(slots=True, frozen=True)
class TasmotaSwitchTriggerConfig:
    """Tasmota switch configuation."""

    event: str = attr.ib()
    idx: int = attr.ib()
    mac: str = attr.ib()
    source: str = attr.ib()
    subtype: str = attr.ib()
    switchname: str = attr.ib()
    trigger_topic: str = attr.ib()
    type: str = attr.ib()

    @classmethod
    def from_discovery_message(cls, config, idx):
        """Instantiate from discovery message."""
        switchmode = config[CONF_SWITCH][idx]
        _, _, triggers = SWITCHMODE_MAP[switchmode]
        configs = []
        for event, trigger_type in triggers.items():
            configs.append(
                cls(
                    mac=config[CONF_MAC],
                    event=config[CONF_STATE][event],
                    idx=idx,
                    source="switch",
                    subtype=f"switch_{idx+1}",
                    switchname=config_get_switchname(config, idx),
                    trigger_topic=get_topic_stat_result(config),
                    type=trigger_type,
                )
            )
        return configs

    @property
    def is_active(self):
        """Return if the trigger is active."""
        return self.type != SW_TRIG_NONE

    @property
    def trigger_id(self):
        """Return trigger id."""
        return f"{self.mac}_switch_{self.idx+1}_{self.event}"


class TasmotaSwitchTrigger(TasmotaTrigger):
    """Representation of a Tasmota switch trigger."""

    def _trig_message_received(self, msg):
        """Handle new MQTT messages."""
        event = get_value_by_path(msg.payload, [self.cfg.switchname, RSLT_ACTION])
        if event == self.cfg.event:
            self._on_trigger_callback()


@attr.s(slots=True, frozen=True)
class TasmotaSwitchConfig(TasmotaAvailabilityConfig, TasmotaEntityConfig):
    """Tasmota switch configuation."""

    off_delay: int = attr.ib()
    poll_topic: str = attr.ib()
    state_power_off: str = attr.ib()
    state_power_on: str = attr.ib()
    state_topic1: str = attr.ib()
    state_topic2: str = attr.ib()
    state_topic3: str = attr.ib()
    switchname: str = attr.ib()

    @classmethod
    def from_discovery_message(cls, config, idx, platform):
        """Instantiate from discovery message."""
        switchmode = config[CONF_SWITCH][idx]
        state_topic1 = get_topic_stat_result(config)
        state_topic2 = None
        state_topic3 = None
        if switchmode not in NO_POLL_SWITCHMODES:
            state_topic2 = get_topic_tele_sensor(config)
            state_topic3 = get_topic_stat_status(config, 10)
        binary_sensor, off_delay, _ = SWITCHMODE_MAP[switchmode]
        if not binary_sensor:
            return None

        return cls(
            endpoint="switch",
            idx=idx,
            friendly_name=config_get_switchfriendlyname(config, platform, idx),
            mac=config[CONF_MAC],
            platform=platform,
            poll_payload="10",
            poll_topic=get_topic_command_status(config),
            availability_topic=get_topic_tele_will(config),
            availability_offline=config_get_state_offline(config),
            availability_online=config_get_state_online(config),
            off_delay=off_delay,
            state_power_off=config_get_state_power_off(config),
            state_power_on=config_get_state_power_on(config),
            state_topic1=state_topic1,
            state_topic2=state_topic2,
            state_topic3=state_topic3,
            switchname=config_get_switchname(config, idx),
        )


class TasmotaSwitch(TasmotaAvailability, TasmotaEntity):
    """Representation of a Tasmota switch."""

    def __init__(self, **kwds):
        """Initialize."""
        self._sub_state = None
        super().__init__(**kwds)

    async def subscribe_topics(self):
        """Subscribe to topics."""

        def state_message_received(msg):
            """Handle new MQTT state messages."""
            state = None
            # tasmota_0848A2/stat/RESULT  / {"Switch1":{"Action":"ON"}}
            if msg.topic == self._cfg.state_topic1:
                state = get_value_by_path(
                    msg.payload, [self._cfg.switchname, RSLT_ACTION]
                )
            # tasmota_0848A2/tele/SENSOR  / {"Time":"2020-09-20T09:41:28","Switch1":"ON"}
            if msg.topic == self._cfg.state_topic2:
                state = get_value_by_path(msg.payload, [self._cfg.switchname])
            # tasmota_0848A2/stat/STATUS10 / {"StatusSNS":{"Time":"2020-09-20T09:41:00","Switch1":"ON"}}
            if msg.topic == self._cfg.state_topic3:
                state = get_value_by_path(
                    msg.payload, [STATUS_SENSOR, self._cfg.switchname]
                )
            if state == self._cfg.state_power_on:
                self._on_state_callback(True)
            elif state == self._cfg.state_power_off:
                self._on_state_callback(False)

        availability_topics = self.get_availability_topics()
        # tasmota_0848A2/stat/RESULT  / {"Switch1":{"Action":"ON"}}
        # tasmota_0848A2/tele/SENSOR  / {"Time":"2020-09-20T09:41:28","Switch1":"ON"}
        # tasmota_0848A2/stat/STATUS10 / {"StatusSNS":{"Time":"2020-09-20T09:41:00","Switch1":"ON"}}
        topics = {
            "state_topic1": {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic1,
                "msg_callback": state_message_received,
            },
        }
        if self._cfg.state_topic2:
            topics["state_topic2"] = {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic2,
                "msg_callback": state_message_received,
            }
        if self._cfg.state_topic3:
            topics["state_topic3"] = {
                "event_loop_safe": True,
                "topic": self._cfg.state_topic3,
                "msg_callback": state_message_received,
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
    def off_delay(self):
        """Return off delay."""
        return self._cfg.off_delay
