"""Diagnostics for the NeoRé heat pump."""
from __future__ import annotations

from typing import Any

from modbus_connection import ModbusError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import NeoreConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NeoreConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    try:
        registers: dict[str, Any] = {
            "holding": await coordinator.device.async_read_raw()
        }
    except ModbusError as err:
        registers = {"error": str(err)}
    return {
        "entry": async_redact_data(dict(entry.data), {CONF_HOST}),
        "options": dict(entry.options),
        "data": coordinator.data,
        "registers": registers,
    }
