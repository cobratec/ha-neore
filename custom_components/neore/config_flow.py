"""Config flow for the NeoRé heat pump."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from modbus_connection import ModbusError, ModbusTcpParams

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_SETPOINT_MAX,
    CONF_SETPOINT_MIN,
    CONF_UNIT_ID,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SETPOINT_MAX,
    DEFAULT_SETPOINT_MIN,
    DEFAULT_UNIT_ID,
    DOMAIN,
    HOT_WATER_LIMITS,
    MIN_SCAN_INTERVAL,
)
from .device import NeoreDevice

_LOGGER = logging.getLogger(__name__)


async def _validate(hass: HomeAssistant, host: str, port: int, unit_id: int) -> None:
    """Probe the heat pump over a temporary unit on the shared Modbus connection."""
    async with async_get_temporary_unit(
        hass, ModbusTcpParams(host=host, port=port), unit_id
    ) as unit:
        await NeoreDevice(unit).async_validate()


def _box(minimum: float, maximum: float, step: float = 1, unit: str | None = None) -> NumberSelector:
    """Number entered in a text box with up/down arrows (no slider)."""
    config = NumberSelectorConfig(
        min=minimum, max=maximum, step=step, mode=NumberSelectorMode.BOX
    )
    if unit is not None:  # None is rejected by the selector schema
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


class NeoreConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_PORT] = int(user_input[CONF_PORT])
            user_input[CONF_UNIT_ID] = int(user_input[CONF_UNIT_ID])
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(f"{host}:{user_input[CONF_PORT]}:{user_input[CONF_UNIT_ID]}")
            self._abort_if_unique_id_configured()
            try:
                await _validate(self.hass, host, user_input[CONF_PORT], user_input[CONF_UNIT_ID])
            except (ModbusError, ValueError) as err:
                _LOGGER.warning("Cannot connect to NeoRé heat pump: %s", err)
                errors["base"] = "cannot_connect"
            except HomeAssistantError as err:
                _LOGGER.warning("Modbus connection conflict: %s", err)
                errors["base"] = "connection_conflict"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_HOST: host,
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_UNIT_ID: user_input[CONF_UNIT_ID],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): _box(1, 65535),
                vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): _box(0, 255),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> NeoreOptionsFlow:
        return NeoreOptionsFlow()


class NeoreOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            if user_input[CONF_SETPOINT_MIN] >= user_input[CONF_SETPOINT_MAX]:
                errors["base"] = "invalid_range"
            else:
                return self.async_create_entry(data=user_input)

        opts = self.config_entry.options
        temp = _box(HOT_WATER_LIMITS[0], HOT_WATER_LIMITS[1], 1, "°C")
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): _box(MIN_SCAN_INTERVAL, 600, 1, "s"),
                vol.Required(
                    CONF_SETPOINT_MIN, default=opts.get(CONF_SETPOINT_MIN, DEFAULT_SETPOINT_MIN)
                ): temp,
                vol.Required(
                    CONF_SETPOINT_MAX, default=opts.get(CONF_SETPOINT_MAX, DEFAULT_SETPOINT_MAX)
                ): temp,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
