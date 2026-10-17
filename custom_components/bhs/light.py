"""Light platform for BHS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BHSCoordinator
from .entity import BHSEntity


def _is_supported_light(member: dict[str, Any]) -> bool:
    """Return True for known lighting members in v0.1."""
    member_id = str(member.get("memberID") or "")
    name = str(member.get("name") or "")
    member_type = member.get("memberType")
    return bool(member_id) and (
        (member_type == 1 and name.startswith("VER_"))
        or (member_type == 2 and name.startswith("DIM_"))
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BHS lights."""
    coordinator: BHSCoordinator = entry.runtime_data
    async_add_entities(
        BHSLight(coordinator, member)
        for member in coordinator.members
        if _is_supported_light(member)
    )


class BHSLight(BHSEntity, LightEntity):
    """BHS relay or DIM1K light.

    DIM1K lights intentionally expose ON/OFF only. The REST API does not expose
    brightness, dimming direction, or brightness retention.
    """

    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self) -> bool | None:
        """Return whether the BHS light is on."""
        status = self.coordinator.data.get(self.member_id)
        if status is None:
            return None
        return status.casefold() in {"set", "dimmer"}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on at the BHS module's Set level (full for DIM1K)."""
        await self.coordinator.api.command_member(self.member_id, "set")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.api.command_member(self.member_id, "reset")
        await self.coordinator.async_request_refresh()
