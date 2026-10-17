"""Binary sensor platform for BHS input modules."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BHSCoordinator
from .entity import BHSEntity


def _is_input(member: dict[str, Any]) -> bool:
    """Return True for physical BHS input members."""
    return bool(member.get("memberID")) and member.get("memberType") == 3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BHS input binary sensors."""
    coordinator: BHSCoordinator = entry.runtime_data
    async_add_entities(
        BHSInputBinarySensor(coordinator, member)
        for member in coordinator.members
        if _is_input(member)
    )


class BHSInputBinarySensor(BHSEntity, BinarySensorEntity):
    """A BHS INM input exposed as a generic binary sensor."""

    _attr_icon = "mdi:electric-switch"

    @property
    def is_on(self) -> bool | None:
        """Return whether the BHS input reports Set."""
        status = self.coordinator.data.get(self.member_id)
        if status is None:
            return None
        return status.casefold() == "set"
