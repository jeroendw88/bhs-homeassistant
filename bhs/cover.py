"""Cover platform for BHS roller shutters and screens."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BHSCoordinator
from .entity import BHSEntity


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
    """Build a readable cover name from the pair."""
    for member, suffix in ((open_member, "_OP"), (close_member, "_NEER")):
        name = str(member.get("name") or "")
        if name.upper().endswith(suffix):
            return name[: -len(suffix)]
    return f"Cover {open_member.get('group')}.{open_member.get('address')}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BHS covers."""
    coordinator: BHSCoordinator = entry.runtime_data
    async_add_entities(
        BHSCover(coordinator, open_member, close_member)
        for open_member, close_member in _cover_pairs(coordinator.members)
    )


class BHSCover(BHSEntity, CoverEntity):
    """A paired BHS roller shutter/screen.

    BHS exposes two RLM members (up/open and down/close). Its configured roller
    shutter mode turns an actuation into a timed movement. No position feedback
    is exposed through the REST API, therefore this entity intentionally uses
    assumed state and exposes no position slider.
    """

    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_assumed_state = True
    _attr_icon = "mdi:window-shutter"

    def __init__(
        self,
        coordinator: BHSCoordinator,
        open_member: dict[str, Any],
        close_member: dict[str, Any],
    ) -> None:
        """Initialize a paired BHS cover."""
        super().__init__(coordinator, open_member)
        self.open_member = open_member
        self.close_member = close_member
        self.open_member_id = str(open_member["memberID"])
        self.close_member_id = str(close_member["memberID"])
        self._attr_unique_id = f"{self.open_member_id}_{self.close_member_id}_cover"
        self._attr_name = _cover_name(open_member, close_member)
        self._command_lock = asyncio.Lock()

    @property
    def is_opening(self) -> bool:
        """Return whether the open/up relay currently reports Set."""
        status = self.coordinator.data.get(self.open_member_id, "")
        return status.casefold() == "set"

    @property
    def is_closing(self) -> bool:
        """Return whether the close/down relay currently reports Set."""
        status = self.coordinator.data.get(self.close_member_id, "")
        return status.casefold() == "set"

    @property
    def is_closed(self) -> None:
        """Position/end-state is not available from BHS REST."""
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Start opening/up movement after de-energizing the down relay."""
        async with self._command_lock:
            await self.coordinator.api.command_member(self.close_member_id, "reset")
            await self.coordinator.api.command_member(self.open_member_id, "set")
            await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Start closing/down movement after de-energizing the up relay."""
        async with self._command_lock:
            await self.coordinator.api.command_member(self.open_member_id, "reset")
            await self.coordinator.api.command_member(self.close_member_id, "set")
            await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Reset both direction members to request a stop."""
        async with self._command_lock:
            await self.coordinator.api.command_member(self.open_member_id, "reset")
            await self.coordinator.api.command_member(self.close_member_id, "reset")
            await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose metadata for both paired BHS members."""
        attrs = super().extra_state_attributes
        attrs.update(
            {
                "bhs_open_member_id": self.open_member_id,
                "bhs_close_member_id": self.close_member_id,
                "bhs_open_status": self.coordinator.data.get(self.open_member_id),
                "bhs_close_status": self.coordinator.data.get(self.close_member_id),
            }
        )
        return attrs
