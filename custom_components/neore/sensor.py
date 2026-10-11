"""Sensors for the NeoRé heat pump."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NeoreConfigEntry
from .entity import NeoreEntity


@dataclass(frozen=True, kw_only=True)
class NeoreSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


def _temp(key: str, **kwargs: Any) -> NeoreSensorDescription:
    kwargs.setdefault("device_class", SensorDeviceClass.TEMPERATURE)
    kwargs.setdefault("state_class", SensorStateClass.MEASUREMENT)
    return NeoreSensorDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda d, k=key: d.get(k),
        **kwargs,
    )


SENSORS: tuple[NeoreSensorDescription, ...] = (
    _temp("outdoor_temperature"),
    _temp("indoor_temperature"),
    _temp("output_temperature"),
    _temp("return_temperature"),
    _temp("hot_water_temperature"),
    _temp("heating_water_target"),
    _temp("iq_correction", device_class=None),
    NeoreSensorDescription(
        key="circulation_pump",
        translation_key="circulation_pump",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda d: d.get("circulation_pump"),
    ),
    NeoreSensorDescription(
        key="flow",
        translation_key="flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        suggested_display_precision=2,
        value_fn=lambda d: d.get("flow"),
    ),
    NeoreSensorDescription(
        key="water_pressure",
        translation_key="water_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=2,
        value_fn=lambda d: d.get("water_pressure"),
    ),
    NeoreSensorDescription(
        key="thermal_power",
        translation_key="thermal_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        value_fn=lambda d: d.get("thermal_power"),
    ),
    NeoreSensorDescription(
        key="heat_energy",
        translation_key="heat_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda d: d.get("heat_energy"),
    ),
    NeoreSensorDescription(
        key="operating_hours",
        translation_key="operating_hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("operating_hours"),
    ),
    NeoreSensorDescription(
        key="compressor_output",
        translation_key="compressor_output",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda d: d.get("compressor_output"),
    ),
    _temp(
        "hot_water_hysteresis",
        device_class=None,
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _temp(
        "disinfection_temperature",
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NeoreSensorDescription(
        key="heater_delay",
        translation_key="heater_delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("heater_delay"),
    ),
    NeoreSensorDescription(
        key="status_code",
        translation_key="status_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("status_code"),
    ),
    NeoreSensorDescription(
        key="status_text",
        translation_key="status_text",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: None
        if d.get("status_texts") is None
        else ("; ".join(d["status_texts"]) or "OK")[:255],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: NeoreConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        (
            NeoreTotalSensor
            if desc.state_class is SensorStateClass.TOTAL_INCREASING
            else NeoreSensor
        )(coordinator, desc)
        for desc in SENSORS
    )


class NeoreSensor(NeoreEntity, SensorEntity):
    entity_description: NeoreSensorDescription

    def __init__(self, coordinator, description: NeoreSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)


class NeoreTotalSensor(NeoreSensor, RestoreSensor):
    """Counter that keeps its last value while the heat pump is unreachable.

    Avoids gaps in long-term statistics and the energy dashboard.
    """

    _last: Any = None

    @property
    def available(self) -> bool:
        return self._last is not None or super().available

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None:
            self._last = last.native_value

    @property
    def native_value(self) -> Any:
        if self.coordinator.last_update_success and self.coordinator.data:
            value = self.entity_description.value_fn(self.coordinator.data)
            if value is not None:
                self._last = value
        return self._last
