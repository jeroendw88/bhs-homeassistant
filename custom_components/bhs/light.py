"""Light platform for BHS."""

from __future__ import annotations

from typing import Any

import logging

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BHSCoordinator
from .rest_api import BHSRestApi
from .entity import BHSEntity

_LOGGER = logging.getLogger(__name__)


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
    """BHS relay or DIM1K light with optional requested-level control."""

    def __init__(self, coordinator: BHSCoordinator, member: dict[str, Any]) -> None:
        super().__init__(coordinator, member)
        self._has_brightness = (
            isinstance(coordinator.api, BHSRestApi)
            and coordinator.api.supports_brightness(self.member_id)
        )
        self._attr_supported_color_modes = (
            {ColorMode.BRIGHTNESS} if self._has_brightness else {ColorMode.ONOFF}
        )
        self._attr_color_mode = (
            ColorMode.BRIGHTNESS if self._has_brightness else ColorMode.ONOFF
        )
        # Restore last successfully commanded level; this is not bus feedback.
        self._requested_brightness: int | None = None
        stored = coordinator.brightness_memory.get(self.member_id)
        if self._has_brightness and stored is not None:
            self._requested_brightness = round(
                max(stored, self._minimum_brightness) * 255 / 100
            )

    @property
    def _minimum_brightness(self) -> int:
        return self.coordinator.dimmer_min_brightness.get(
            self.member_id, self.coordinator.dimmer_min_default
        )

    @property
    def is_on(self) -> bool | None:
        status = self.coordinator.data.get(self.member_id)
        if status is None:
            return None
        return status.casefold() in {"set", "dimmer"}

    @property
    def brightness(self) -> int | None:
        return self._requested_brightness if self._has_brightness else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes = dict(super().extra_state_attributes)
        if self._has_brightness:
            attributes["bhs_brightness_feedback"] = "last_commanded_only"
            attributes["bhs_min_brightness_percent"] = self._minimum_brightness
            attributes["bhs_last_commanded_brightness_percent"] = (
                self.coordinator.brightness_memory.get(self.member_id)
            )
        return attributes

    async def _remember_brightness(self, percent: int) -> None:
        """Persist only a successful absolute brightness command."""
        async with self.coordinator.brightness_memory_lock:
            self.coordinator.brightness_memory[self.member_id] = percent
            try:
                await self.coordinator.brightness_memory_store.async_save(
                    {"levels": dict(self.coordinator.brightness_memory)}
                )
            except (OSError, ValueError) as err:
                # Switching worked; a storage issue should not report bus failure.
                _LOGGER.warning("Could not persist BHS brightness memory: %s", err)

    async def async_turn_on(self, **kwargs: Any) -> None:
        requested = kwargs.get("brightness")
        if self._has_brightness:
            percent: int | None = None
            if requested is not None:
                if not isinstance(requested, (int, float)):
                    raise ValueError("Invalid brightness value")
                value = max(0, min(255, int(requested)))
                if value == 0:
                    await self.async_turn_off()
                    return
                percent = max(self._minimum_brightness, round(value * 100 / 255))
            else:
                # Plain On: restore the previous successful setting, if any.
                last = self.coordinator.brightness_memory.get(self.member_id)
                if last is not None:
                    percent = max(self._minimum_brightness, last)

            if percent is not None:
                await self.coordinator.api.set_brightness(self.member_id, percent)
                self._requested_brightness = round(percent * 255 / 100)
                await self._remember_brightness(percent)
                self.async_write_ha_state()
            else:
                # No historical level yet: retain the previously tested On behavior.
                await self.coordinator.api.command_member(self.member_id, "set")
        else:
            await self.coordinator.api.command_member(self.member_id, "set")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.command_member(self.member_id, "reset")
        # Intentionally retain last commanded brightness for the next On.
        await self.coordinator.async_request_refresh()
