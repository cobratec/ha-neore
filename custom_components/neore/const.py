"""Constants for the NeoRé heat pump integration."""
from __future__ import annotations

DOMAIN = "neore"
MANUFACTURER = "NeoRé"

CONF_UNIT_ID = "unit_id"
CONF_SETPOINT_MIN = "setpoint_min"
CONF_SETPOINT_MAX = "setpoint_max"

DEFAULT_NAME = "NeoRé heat pump"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 10
DEFAULT_SETPOINT_MIN = 40.0
DEFAULT_SETPOINT_MAX = 55.0


# absolute limits for writable parameters (options can narrow the hot water range)
HOT_WATER_LIMITS = (30.0, 65.0)
ROOM_LIMITS = (10.0, 30.0)
CURVE_LIMITS = (15.0, 55.0)
