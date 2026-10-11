"""Writable setpoints as number entities."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_SETPOINT_MAX,
    CONF_SETPOINT_MIN,
    DEFAULT_SETPOINT_MAX,
    DEFAULT_SETPOINT_MIN,
    CURVE_LIMITS,
    ROOM_LIMITS,
)
from .coordinator import NeoreConfigEntry, NeoreCoordinator
from .entity import NeoreEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: NeoreConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    options = entry.options
    async_add_entities(
        [
            NeoreSetpoint(
                coordinator,
                "hot_water_target",
                "hot_water_setpoint",
                options.get(CONF_SETPOINT_MIN, DEFAULT_SETPOINT_MIN),
                options.get(CONF_SETPOINT_MAX, DEFAULT_SETPOINT_MAX),
                1.0,  # the controller panel only supports whole degrees
            ),
            NeoreSetpoint(
                coordinator, "room_target", "room_setpoint", ROOM_LIMITS[0], ROOM_LIMITS[1], 0.1
            ),
            *(
                NeoreSetpoint(
                    coordinator,
                    key,
                    key,
                    CURVE_LIMITS[0],
                    CURVE_LIMITS[1],
                    1.0,
                    EntityCategory.CONFIG,
                )
                for key in ("curve_m20", "curve_m7", "curve_p6", "curve_p19")
            ),
        ]
    )


class NeoreSetpoint(NeoreEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: NeoreCoordinator,
        key: str,
        translation_key: str,
        minimum: float,
        maximum: float,
        step: float,
        category: EntityCategory | None = None,
    ) -> None:
        super().__init__(coordinator, translation_key)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_entity_category = category

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.get(self._key)
        return None if value is None else round(value, 1)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_parameter(self._key, round(value, 1))
