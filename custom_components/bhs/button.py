"""Button platform for BHS dimming controls."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BHSCoordinator
from .entity import BHSEntity
from .member_registry import is_dimmer
from .rest_api import BHSRestApi
from .sdim import sdim_role, validated_sdim_members


def _is_dimmer(member: dict[str, Any]) -> bool:
    """Return True for physical DIM1K dimmer channels."""
    return is_dimmer(member)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BHS dimming-control buttons."""
    coordinator: BHSCoordinator = entry.runtime_data
    entities: list[ButtonEntity] = []

    # Reuse the exact same validated, name-independent SDim mapping as
    # scene discovery and the REST command allowlists.
    validated = validated_sdim_members(coordinator.members)
    for member in coordinator.members:
        if _is_dimmer(member) and (
            not isinstance(coordinator.api, BHSRestApi) or member.get("group") == 5
        ):
            entities.append(BHSStartDimButton(coordinator, member))

        role = sdim_role(member)
        if role not in ("stop_dim", "group_reset"):
            continue
        key = (member.get("group"), member.get("address"))
        if validated.get(key) is not member:
            continue
        if role == "stop_dim":
            # A validated SDim Stop member is safe to expose per group.
            # Starting cyclic dimming remains restricted to vetted channels.
            entities.append(BHSStopDimButton(coordinator, member))
        elif role == "group_reset":
            # Same-group scene OFF already uses the validated reset member.
            entities.append(BHSGroupResetDimButton(coordinator, member))

    async_add_entities(entities)


class BHSStartDimButton(BHSEntity, ButtonEntity):
    """Start the BHS cyclic dimming behavior for one DIM1K channel."""

    _attr_icon = "mdi:brightness-6"

    def __init__(self, coordinator: BHSCoordinator, member: dict[str, Any]) -> None:
        super().__init__(coordinator, member)
        self._attr_unique_id = f"{self.member_id}_start_dimming"
        self._attr_name = f"{member.get('name') or self.member_id} Start dimming"

    async def async_press(self) -> None:
        """Start cyclic dimming."""
        await self.coordinator.api.command_member(self.member_id, "dimmer")
        await self.coordinator.async_request_refresh()


class BHSStopDimButton(BHSEntity, ButtonEntity):
    """Stop active dimmers in one BHS SDim group."""

    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, coordinator: BHSCoordinator, member: dict[str, Any]) -> None:
        super().__init__(coordinator, member)
        group = member.get("group")
        self._attr_unique_id = f"{self.member_id}_stop_dimming"
        self._attr_name = f"Stop dimming (BHS group {group})"

    async def async_press(self) -> None:
        """Stop cyclic dimming at each active channel's current level."""
        await self.coordinator.api.command_member(self.member_id, "dimmer")
        await self.coordinator.async_request_refresh()


class BHSGroupResetDimButton(BHSEntity, ButtonEntity):
    """Reset all active SDim scenes in one BHS group."""

    _attr_icon = "mdi:lightbulb-group-off-outline"

    def __init__(self, coordinator: BHSCoordinator, member: dict[str, Any]) -> None:
        super().__init__(coordinator, member)
        group = member.get("group")
        self._attr_unique_id = f"{self.member_id}_group_reset_dim"
        self._attr_name = f"Reset dim scenes (BHS group {group})"

    async def async_press(self) -> None:
        """Reset all SDim scenes in this group."""
        await self.coordinator.api.command_member(self.member_id, "dimmer")
        await self.coordinator.async_request_refresh()
