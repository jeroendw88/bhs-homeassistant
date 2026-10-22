"""Cover platform for BHS roller shutters and screens."""

from __future__ import annotations

import asyncio
from time import monotonic
from homeassistant.helpers.event import async_call_later
from collections import defaultdict
from typing import Any

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BHSCoordinator
from .entity import BHSEntity
from .const import DEFAULT_COVER_TRAVEL_SECONDS
from .member_registry import cover_pairs
from .cover_identity import pair_identity


def _is_cover_member(member: dict[str, Any]) -> bool:
    """Return True for BHS rolluik/screen relay members."""
    return bool(member.get("memberID")) and member.get("memberType") == 20


def _cover_pairs(members: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Pair BHS UP/DOWN members.

    BLConfig allocates roller shutter relays in consecutive address pairs. Pairing
    by group + address pair also tolerates minor differences/typos in member names.
    """
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for member in members:
        if not _is_cover_member(member):
            continue
        try:
            group = int(member.get("group"))
            address = int(member.get("address"))
        except (TypeError, ValueError):
            continue
        grouped[(group, (address + 1) // 2)].append(member)

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for pair_members in grouped.values():
        if len(pair_members) != 2:
            continue

        def is_open(member: dict[str, Any]) -> bool:
            name = str(member.get("name") or "").casefold()
            return name.endswith("_op") or "_op_" in name

        open_member = next((m for m in pair_members if is_open(m)), None)
        close_member = next((m for m in pair_members if m is not open_member), None)

        # Fall back to odd address = first/up relay, even address = second/down relay.
        if open_member is None or close_member is None:
            sorted_members = sorted(pair_members, key=lambda m: int(m.get("address", 0)))
            open_member, close_member = sorted_members[0], sorted_members[1]

        pairs.append((open_member, close_member))

    return pairs


def _cover_name(open_member: dict[str, Any], close_member: dict[str, Any]) -> str:
    """Build a cover name from physical member names, independent of direction.

    The user's direction mapping may swap which relay opens the cover. The
    physical names (_OP / _NEER) must not be interpreted as direction mapping.
    """
    members = (open_member, close_member)
    for suffix in ("_OP", "_NEER"):
        for member in members:
            name = str(member.get("name") or "")
            if name.upper().endswith(suffix):
                return name[: -len(suffix)]
    # A deterministic fallback for installations without naming conventions.
    first = min(members, key=lambda m: (int(m.get("group") or 0), int(m.get("address") or 0)))
    return f"Cover {first.get('group')}.{first.get('address')}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BHS covers."""
    coordinator: BHSCoordinator = entry.runtime_data
    async_add_entities(
        BHSCover(coordinator, open_member, close_member,
                 pair_identity(hass, open_member, close_member))
        for open_member, close_member in cover_pairs(coordinator.members, coordinator.cover_directions)
    )


class BHSCover(BHSEntity, CoverEntity):
    """Paired BHS cover with elapsed-time endpoint inference.

    Completion is inferred, not hardware position feedback. Only a continuously
    observed Set relay for the configured travel time establishes an endpoint.
    """

    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_assumed_state = True
    _attr_icon = "mdi:window-shutter"

    def __init__(self, coordinator: BHSCoordinator, open_member: dict[str, Any],
                 close_member: dict[str, Any], stable_unique_id: str) -> None:
        super().__init__(coordinator, open_member)
        self.open_member = open_member
        self.close_member = close_member
        self.open_member_id = str(open_member["memberID"])
        self.close_member_id = str(close_member["memberID"])
        self._attr_unique_id = stable_unique_id
        self._attr_name = _cover_name(open_member, close_member)
        self._command_lock = asyncio.Lock()
        self._active_direction: str | None = None
        self._started_at: float | None = None
        self._completed_position: str | None = None
        self._timer_unsub = None

    @property
    def travel_seconds(self) -> int:
        return self.coordinator.cover_travel_times.get(
            self.unique_id, self.coordinator.cover_travel_default
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.cover_entities[self.unique_id] = self
        self._reconcile_relays()

    async def async_will_remove_from_hass(self) -> None:
        self._cancel_timer()
        self.coordinator.cover_entities.pop(self.unique_id, None)
        await super().async_will_remove_from_hass()

    def _cancel_timer(self) -> None:
        if self._timer_unsub is not None:
            self._timer_unsub()
            self._timer_unsub = None

    def _relay_direction(self) -> str | None:
        if not self.coordinator.last_update_success:
            return None
        up = self.coordinator.data.get(self.open_member_id, "").casefold() == "set"
        down = self.coordinator.data.get(self.close_member_id, "").casefold() == "set"
        if up and not down:
            return "open"
        if down and not up:
            return "closed"
        return None

    def _schedule_completion(self) -> None:
        self._cancel_timer()
        if self._active_direction is None or self._started_at is None:
            return
        remaining = self.travel_seconds - (monotonic() - self._started_at)
        if remaining <= 0:
            self._complete_if_still_active()
        else:
            self._timer_unsub = async_call_later(self.hass, remaining, self._timer_finished)

    @callback
    def _timer_finished(self, _now) -> None:
        self._timer_unsub = None
        self._complete_if_still_active()

    def _complete_if_still_active(self) -> None:
        if (self._active_direction is not None
                and self._relay_direction() == self._active_direction
                and self._started_at is not None
                and monotonic() - self._started_at >= self.travel_seconds):
            self._completed_position = self._active_direction
            self.async_write_ha_state()

    def _reconcile_relays(self) -> None:
        if not self.coordinator.last_update_success:
            return
        direction = self._relay_direction()
        if direction == self._active_direction:
            if direction is not None:
                self._complete_if_still_active()
            return
        self._cancel_timer()
        previous = self._active_direction
        if direction is None:
            # A relay may have reset between polls after completing travel.
            if (previous is not None and self._started_at is not None
                    and monotonic() - self._started_at >= self.travel_seconds):
                self._completed_position = previous
            elif previous is not None and self._completed_position != previous:
                self._completed_position = None
            self._active_direction = None
            self._started_at = None
        else:
            self._active_direction = direction
            self._started_at = monotonic()
            self._completed_position = None
            self._schedule_completion()

    def _handle_coordinator_update(self) -> None:
        self._reconcile_relays()
        super()._handle_coordinator_update()

    def travel_time_changed(self) -> None:
        if self._active_direction is not None:
            self._schedule_completion()
        self.async_write_ha_state()

    @property
    def is_opening(self) -> bool:
        return self._active_direction == "open" and self._completed_position != "open"

    @property
    def is_closing(self) -> bool:
        return self._active_direction == "closed" and self._completed_position != "closed"

    @property
    def is_closed(self) -> bool | None:
        if self.is_opening or self.is_closing:
            return None
        if self._completed_position == "closed":
            return True
        if self._completed_position == "open":
            return False
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        async with self._command_lock:
            self._completed_position = None
            await self.coordinator.api.command_member(self.close_member_id, "reset")
            await self.coordinator.api.command_member(self.open_member_id, "set")
            await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        async with self._command_lock:
            self._completed_position = None
            await self.coordinator.api.command_member(self.open_member_id, "reset")
            await self.coordinator.api.command_member(self.close_member_id, "set")
            await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        async with self._command_lock:
            self._cancel_timer()
            self._completed_position = None
            await self.coordinator.api.command_member(self.open_member_id, "reset")
            await self.coordinator.api.command_member(self.close_member_id, "reset")
            await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        attrs.update({
            "bhs_open_member_id": self.open_member_id,
            "bhs_close_member_id": self.close_member_id,
            "bhs_open_status": self.coordinator.data.get(self.open_member_id),
            "bhs_close_status": self.coordinator.data.get(self.close_member_id),
            "bhs_travel_seconds": self.travel_seconds,
            "bhs_position_feedback": "inferred_from_relay_duration",
        })
        return attrs
