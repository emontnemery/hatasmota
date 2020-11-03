"""Tasmota binary sensor."""
import logging

import attr

from .const import (
    CONF_BUTTON,
    CONF_MAC,
    CONF_OPTIONS,
    OPTION_BUTTON_SINGLE,
    OPTION_BUTTON_SWAP,
    OPTION_MQTT_BUTTONS,
    RSLT_ACTION,
)
from .trigger import TasmotaTrigger
from .utils import get_topic_stat_result, get_value_by_path

_LOGGER = logging.getLogger(__name__)

# Button matrix for triggers generation when SetOption73 is enabled:
# N  SetOption1  SetOption11 SetOption13 SINGLE PRESS                        DOUBLE PRESS  MULTI PRESS                     HOLD
# 1  0           0           0           SINGLE (10 - button_short_press)    DOUBLE        DOUBLE to PENTA                 YES (button_long_press)
# 2  1           0           0           SINGLE (10 - button_short_press)    DOUBLE        DOUBLE to PENTA                 YES (button_long_press)
# 3  0           1           0           DOUBLE (11 - button_short_press)    SINGLE        SINGLE then TRIPLE TO PENTA     YES (button_long_press)
# 4  1           1           0           DOUBLE (11 - button_short_press)    SINGLE        SINGLE then TRIPLE TO PENTA     YES (button_long_press)
# 5  0           0           1           SINGLE (10 - button_short_press)    NONE          NONE                            NONE
# 6  1           0           1           SINGLE (10 - button_short_press)    NONE          NONE                            NONE
# 7  0           1           1           SINGLE (10 - button_short_press)    NONE          NONE                            NONE
# 8  1           1           1           SINGLE (10 - button_short_press)    NONE          NONE                            NONE
# Trigger types:  10 = button_short_press | 11 = button_double_press | 12 = button_triple_press | 13 = button_quadruple_press | 14 = button_quintuple_press | 3 = button_long_press

# SetOption11: Swap button single and double press functionality
# SetOption13: Immediate action on button press, just SINGLE trigger

BUTTONMODE_NONE = "none"
BUTTONMODE_NORMAL = "normal"
BUTTONMODE_SWAP = "swap"
BUTTONMODE_SINGLE = "single"

BTN_SINGLE = "SINGLE"
BTN_DOUBLE = "DOUBLE"
BTN_TRIPLE = "TRIPLE"
BTN_QUAD = "QUAD"
BTN_PENTA = "PENTA"
BTN_HOLD = "HOLD"

BTN_TRIG_NONE = "none"
BTN_TRIG_SINGLE = "button_short_press"
BTN_TRIG_DOUBLE = "button_double_press"
BTN_TRIG_TRIPLE = "button_triple_press"
BTN_TRIG_QUAD = "button_quadruple_press"
BTN_TRIG_PENTA = "button_quintuple_press"
BTN_TRIG_HOLD = "button_long_press"

BUTTONMODE_MAP = {
    BUTTONMODE_NONE: {
        BTN_SINGLE: BTN_TRIG_NONE,
        BTN_DOUBLE: BTN_TRIG_NONE,
        BTN_TRIPLE: BTN_TRIG_NONE,
        BTN_QUAD: BTN_TRIG_NONE,
        BTN_PENTA: BTN_TRIG_NONE,
        BTN_HOLD: BTN_TRIG_NONE,
    },
    BUTTONMODE_NORMAL: {
        BTN_SINGLE: BTN_TRIG_SINGLE,
        BTN_DOUBLE: BTN_TRIG_DOUBLE,
        BTN_TRIPLE: BTN_TRIG_TRIPLE,
        BTN_QUAD: BTN_TRIG_QUAD,
        BTN_PENTA: BTN_TRIG_PENTA,
        BTN_HOLD: BTN_TRIG_HOLD,
    },
    BUTTONMODE_SWAP: {
        BTN_SINGLE: BTN_TRIG_DOUBLE,
        BTN_DOUBLE: BTN_TRIG_SINGLE,
        BTN_TRIPLE: BTN_TRIG_TRIPLE,
        BTN_QUAD: BTN_TRIG_QUAD,
        BTN_PENTA: BTN_TRIG_PENTA,
        BTN_HOLD: BTN_TRIG_HOLD,
    },
    BUTTONMODE_SINGLE: {
        BTN_SINGLE: BTN_TRIG_SINGLE,
        BTN_DOUBLE: BTN_TRIG_NONE,
        BTN_TRIPLE: BTN_TRIG_NONE,
        BTN_QUAD: BTN_TRIG_NONE,
        BTN_PENTA: BTN_TRIG_NONE,
        BTN_HOLD: BTN_TRIG_NONE,
    },
}


@attr.s(slots=True, frozen=True)
class TasmotaButtonTriggerConfig:
    """Tasmota switch configuation."""

    event: str = attr.ib()
    idx: int = attr.ib()
    mac: str = attr.ib()
    source: str = attr.ib()
    subtype: str = attr.ib()
    trigger_topic: str = attr.ib()
    type: str = attr.ib()

    @classmethod
    def from_discovery_message(cls, config, idx):
        """Instantiate from discovery message."""
        mqtt_buttons = config[CONF_OPTIONS][OPTION_MQTT_BUTTONS]
        single_buttons = config[CONF_OPTIONS][OPTION_BUTTON_SINGLE]
        swap_buttons = config[CONF_OPTIONS][OPTION_BUTTON_SWAP]
        buttonmode = BUTTONMODE_NONE
        if mqtt_buttons and config[CONF_BUTTON][idx]:
            if single_buttons:
                buttonmode = BUTTONMODE_SINGLE
            elif swap_buttons:
                buttonmode = BUTTONMODE_SWAP
            else:
                buttonmode = BUTTONMODE_NORMAL

        triggers = BUTTONMODE_MAP[buttonmode]
        configs = []
        for event, trigger_type in triggers.items():
            configs.append(
                cls(
                    mac=config[CONF_MAC],
                    event=event,
                    idx=idx,
                    source="button",
                    subtype=f"button_{idx+1}",
                    trigger_topic=get_topic_stat_result(config),
                    type=trigger_type,
                )
            )
        return configs

    @property
    def is_active(self):
        """Return if the trigger is active."""
        return self.type != BTN_TRIG_NONE

    @property
    def trigger_id(self):
        """Return trigger id."""
        return f"{self.mac}_button_{self.idx+1}_{self.event}"


class TasmotaButtonTrigger(TasmotaTrigger):
    """Representation of a Tasmota button trigger."""

    def _trig_message_received(self, msg):
        """Handle new MQTT messages."""
        event = get_value_by_path(msg.payload, [f"Button{self.cfg.idx+1}", RSLT_ACTION])
        if event == self.cfg.event:
            self._on_trigger_callback()
