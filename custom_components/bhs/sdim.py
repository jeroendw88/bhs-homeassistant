"""Name-independent SDim subtype discovery from documented/observed addresses."""

from __future__ import annotations

from collections import Counter
from typing import Any


def sdim_role(member: dict[str, Any]) -> str | None:
    """Classify an SDim member by bus address, never by its display name."""
    if (not member.get("memberID") or member.get("memberType") != 19
            or str(member.get("version") or "").casefold() != "sdim"):
        return None
    address = member.get("address")
    if not isinstance(address, int) or isinstance(address, bool):
        return None
    if address == 219:
        return "group_reset"
    if address == 220:
        return "stop_dim"
    if 221 <= address <= 228:
        return "scene"
    if address == 229:
        return "record_scene"
    return None


def validated_sdim_members(members: list[dict[str, Any]]) -> dict[tuple[int, int], dict[str, Any]]:
    """Return only unambiguous (group, address) SDim members.

    Duplicated addresses are excluded; they must never accidentally become
    writable or produce multiple overlapping scene entities.
    """
    relevant = [m for m in members if sdim_role(m) is not None
                and isinstance(m.get("group"), int)
                and not isinstance(m.get("group"), bool)]
    counts = Counter((m["group"], m["address"]) for m in relevant)
    return {(m["group"], m["address"]): m for m in relevant
            if counts[(m["group"], m["address"])] == 1}
