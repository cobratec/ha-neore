"""Controller settings as switch entities."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NeoreConfigEntry, NeoreCoordinator
from .entity import NeoreEntity

SWITCHES = (
    "heating_follow_tariff",
    "hot_water_follow_tariff",
    "disinfection_enabled",
    "circulation_enabled",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: NeoreConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(NeoreSwitch(entry.runtime_data, key) for key in SWITCHES)


class NeoreSwitch(NeoreEntity, SwitchEntity):
    """A controller setting. Writes go to the controller's parameter memory,
    so avoid toggling these from frequent automations."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: NeoreCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._attr_translation_key = key

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self._key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_switch(self._key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_switch(self._key, False)
