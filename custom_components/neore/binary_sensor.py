"""Binary sensors for the NeoRé heat pump."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

try:  # newer Home Assistant versions
    from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
except ImportError:  # pragma: no cover
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NeoreConfigEntry, NeoreCoordinator
from .entity import NeoreEntity

R = BinarySensorDeviceClass.RUNNING
D = EntityCategory.DIAGNOSTIC


@dataclass(frozen=True, kw_only=True)
class NeoreBinaryDescription(BinarySensorEntityDescription):
    pass


def _d(key: str, device_class=None, category=None, enabled=True) -> NeoreBinaryDescription:
    return NeoreBinaryDescription(
        key=key,
        translation_key=key,
        device_class=device_class,
        entity_category=category,
        entity_registry_enabled_default=enabled,
    )


BINARY_SENSORS: tuple[NeoreBinaryDescription, ...] = (
    _d("error", BinarySensorDeviceClass.PROBLEM),
    _d("running", R),
    _d("hot_water_heating", R),
    _d("hot_water_electric", R),
    _d("bivalence", R),
    _d("bivalence_stage_1", R, D),
    _d("bivalence_stage_2", R, D),
    _d("circulation_pump_running", R),
    _d("hot_water_circulation_running", R),
    _d("high_tariff"),
    _d("hot_water_high_tariff", None, D),
    _d("hot_water_time_blocked", None, D),
    _d("economy"),
    _d("setback"),
    # Split units (Fujitsu) defrost on their own; without the MX communication
    # module the controller never sets this bit, so it is disabled by default.
    _d("defrost", R, enabled=False),
    _d("disinfection_running", R),
    _d("heating_enabled", None, D),
    _d("hot_water_enabled", None, D),
    _d("warm_up", R, D),
    _d("frost_protection", R, D),
    _d("venting", R, D),
    _d("outdoor_too_cold", None, D),
    _d("secondary_source", R, D),
    _d("floor_drying", R, D),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: NeoreConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(NeoreBinarySensor(entry.runtime_data, d) for d in BINARY_SENSORS)


class NeoreBinarySensor(NeoreEntity, BinarySensorEntity):
    entity_description: NeoreBinaryDescription

    def __init__(self, coordinator: NeoreCoordinator, description: NeoreBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self.entity_description.key)
