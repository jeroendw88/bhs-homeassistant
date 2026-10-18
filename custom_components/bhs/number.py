"""Per-dimmer minimum brightness settings for BHS."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DIMMER_MIN_BRIGHTNESS
from .coordinator import BHSCoordinator
from .entity import BHSEntity
from .rest_api import BHSRestApi


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose a persisted minimum level for each supported REST dimmer."""
    coordinator: BHSCoordinator = entry.runtime_data
    if not isinstance(coordinator.api, BHSRestApi):
        return
    async_add_entities(
        BHSMinimumBrightness(coordinator, entry, member)
        for member in coordinator.members
        if coordinator.api.supports_brightness(str(member.get("memberID") or ""))
    )


class BHSMinimumBrightness(BHSEntity, NumberEntity):
    """Configure the lowest nonzero brightness sent to a DIM1K channel."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:brightness-percent"

    def __init__(self, coordinator: BHSCoordinator, entry: ConfigEntry, member: dict) -> None:
        super().__init__(coordinator, member)
        self._entry = entry
        self._attr_unique_id = f"{self.member_id}_minimum_brightness"
        self._attr_name = f"{member.get('name', self.member_id)} Minimum brightness"

    @property
    def native_value(self) -> int:
        return self.coordinator.dimmer_min_brightness.get(
            self.member_id, self.coordinator.dimmer_min_default
        )

    async def async_set_native_value(self, value: float) -> None:
        percent = int(value)
        if not 1 <= percent <= 100:
            raise ValueError("Minimum brightness must be between 1 and 100%")
        current = dict(self._entry.options.get(CONF_DIMMER_MIN_BRIGHTNESS, {}))
        current[self.member_id] = percent
        self.coordinator.dimmer_min_brightness[self.member_id] = percent
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_DIMMER_MIN_BRIGHTNESS: current},
        )
        self.async_write_ha_state()
