"""Water heater entity for the NeoRé hot water tank."""
from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_SETPOINT_MAX,
    CONF_SETPOINT_MIN,
    DEFAULT_SETPOINT_MAX,
    DEFAULT_SETPOINT_MIN,
)
from .coordinator import NeoreConfigEntry
from .entity import NeoreEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: NeoreConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([NeoreWaterHeater(entry.runtime_data)])


class NeoreWaterHeater(NeoreEntity, WaterHeaterEntity):
    _attr_translation_key = "hot_water"
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = [STATE_HEAT_PUMP]
    _attr_current_operation = STATE_HEAT_PUMP
    _attr_precision = 1.0
    _attr_target_temperature_step = 1.0  # the controller panel only supports whole degrees

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "water_heater")
        options = coordinator.config_entry.options
        self._attr_min_temp = options.get(CONF_SETPOINT_MIN, DEFAULT_SETPOINT_MIN)
        self._attr_max_temp = options.get(CONF_SETPOINT_MAX, DEFAULT_SETPOINT_MAX)

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.get("hot_water_temperature")

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.data.get("hot_water_target")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_set_parameter(
                "hot_water_target", float(round(temperature))
            )
