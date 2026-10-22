"""Per-dimmer minimum brightness settings for BHS."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DIMMER_MIN_BRIGHTNESS, CONF_COVER_TRAVEL_TIMES
from .coordinator import BHSCoordinator
from .entity import BHSEntity
from .rest_api import BHSRestApi
from .cover import _cover_pairs, _cover_name


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose a persisted minimum level for each supported REST dimmer."""
    coordinator: BHSCoordinator = entry.runtime_data
    if not isinstance(coordinator.api, BHSRestApi):
        return
    entities = [
        BHSMinimumBrightness(coordinator, entry, member)
        for member in coordinator.members
        if coordinator.api.supports_brightness(str(member.get("memberID") or ""))
    ]
    entities.extend(
        BHSCoverTravelTime(coordinator, entry, up, down)
        for up, down in _cover_pairs(coordinator.members)
    )
    async_add_entities(entities)


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


class BHSCoverTravelTime(BHSEntity, NumberEntity):
    """Per-cover full-travel duration, stored in the config entry options."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 300
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, entry, open_member, close_member):
        super().__init__(coordinator, open_member)
        self._entry = entry
        self._cover_unique_id = (
            f"{open_member['memberID']}_{close_member['memberID']}_cover"
        )
        self._attr_unique_id = f"{self._cover_unique_id}_travel_time"
        self._attr_name = f"{_cover_name(open_member, close_member)} Travel time"

    @property
    def native_value(self) -> int:
        return self.coordinator.cover_travel_times.get(
            self._cover_unique_id, self.coordinator.cover_travel_default
        )

    async def async_set_native_value(self, value: float) -> None:
        seconds = int(value)
        if not 1 <= seconds <= 300:
            raise ValueError("Travel time must be between 1 and 300 seconds")
        current = dict(self._entry.options.get(CONF_COVER_TRAVEL_TIMES, {}))
        current[self._cover_unique_id] = seconds
        self.coordinator.cover_travel_times[self._cover_unique_id] = seconds
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, CONF_COVER_TRAVEL_TIMES: current},
        )
        cover = self.coordinator.cover_entities.get(self._cover_unique_id)
        if cover is not None:
            cover.travel_time_changed()
        self.async_write_ha_state()
