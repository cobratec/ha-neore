"""Base entity for the NeoRé heat pump."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import NeoreCoordinator


class NeoreEntity(CoordinatorEntity[NeoreCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: NeoreCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model="Heat pump",
            name=entry.title,
        )
