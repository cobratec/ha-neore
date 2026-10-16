"""Data update coordinator for the NeoRé heat pump."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from modbus_connection import ModbusError, ModbusTimeoutError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .device import NeoreDevice

_LOGGER = logging.getLogger(__name__)

type NeoreConfigEntry = ConfigEntry[NeoreCoordinator]

# consecutive timeouts after which the (possibly wedged) link is dropped
MAX_TIMEOUTS = 3


class NeoreCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the heat pump and performs writes."""

    config_entry: NeoreConfigEntry

    def __init__(self, hass: HomeAssistant, entry: NeoreConfigEntry, device: NeoreDevice) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.device = device
        self._timeouts = 0

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.device.async_update()
        except ModbusTimeoutError as err:
            self._timeouts += 1
            if self._timeouts >= MAX_TIMEOUTS:
                self._timeouts = 0
                await self.device.unit.disconnect()
            raise UpdateFailed(f"Heat pump did not answer: {err}") from err
        except ModbusError as err:
            raise UpdateFailed(f"Communication with heat pump failed: {err}") from err
        self._timeouts = 0
        return data

    async def async_set_parameter(self, key: str, value: float) -> None:
        """Write a float parameter (only when it changes) and verify the read-back."""
        current = (self.data or {}).get(key)
        if current is not None and abs(current - value) < 0.01:
            return  # avoid needless writes to the controller's parameter memory

        try:
            readback = await self.device.async_write_float(key, value)
        except (ModbusError, ValueError) as err:
            raise HomeAssistantError(f"Writing {key} failed: {err}") from err

        await asyncio.sleep(0.5)
        await self.async_refresh()
        if readback is None or abs(readback - value) > 0.01:
            raise HomeAssistantError(
                f"Heat pump did not accept {key} = {value} (reads {readback})"
            )

    async def async_set_switch(self, key: str, on: bool) -> None:
        """Write a setting bit (only when it changes) and verify the read-back."""
        if (self.data or {}).get(key) is on:
            return

        try:
            readback = await self.device.async_write_bit(key, on)
        except (ModbusError, ValueError) as err:
            raise HomeAssistantError(f"Writing {key} failed: {err}") from err

        await asyncio.sleep(0.5)
        await self.async_refresh()
        if readback is not on:
            raise HomeAssistantError(
                f"Heat pump did not accept {key} = {on} (reads {readback})"
            )
