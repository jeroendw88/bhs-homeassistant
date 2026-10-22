"""Type-based BHS discovery and persistent, member-ID keyed overrides.

Names are only used to preserve classifications from installations predating 0.4.3.
A new BHS relay defaults to a generic switch until explicitly classified.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

CONF_MEMBER_ROLES = "member_roles"
CONF_COVER_DIRECTIONS = "cover_directions"
ROLE_LIGHT = "light"
ROLE_SWITCH = "switch"
ROLE_DISABLED = "disabled"
ROLE_EXU = "exu_mode"
ROLE_SOFT = "soft_switch"


def is_relay(member: dict[str, Any]) -> bool:
    return (bool(member.get("memberID")) and member.get("memberType") == 1
            and str(member.get("version") or "").casefold() == "rlm_4")


def is_dimmer(member: dict[str, Any]) -> bool:
    return (bool(member.get("memberID")) and member.get("memberType") == 2
            and str(member.get("version") or "").casefold() == "dim1k_15")


def is_exu(member: dict[str, Any]) -> bool:
    return (bool(member.get("memberID")) and member.get("memberType") == 17
            and str(member.get("version") or "").casefold() == "exu_192")


def is_soft(member: dict[str, Any]) -> bool:
    return (bool(member.get("memberID")) and member.get("memberType") == 4
            and str(member.get("version") or "").casefold() == "softm")


def is_cover_channel(member: dict[str, Any]) -> bool:
    return (bool(member.get("memberID")) and member.get("memberType") == 20
            and str(member.get("version") or "").casefold() == "rlm_4")


def legacy_role(member: dict[str, Any]) -> str:
    """Compatibility fallback ONLY; never a requirement for new installations."""
    name = str(member.get("name") or "")
    if is_relay(member):
        return ROLE_LIGHT if name.startswith("VER_") else ROLE_SWITCH
    if is_exu(member):
        if (member.get("group") == 1
                and member.get("address") in (101, 102, 103, 104)
                and name.casefold() in {"bwm_parking", "bwm_terras", "bwm_voordeur", "bwm_garage"}):
            return ROLE_EXU
    if is_soft(member):
        if (member.get("group") == 10 and name.casefold().startswith("bwm_")
                and name.casefold().endswith(("_bypass", "_down"))):
            return ROLE_SOFT
    return ROLE_DISABLED


def resolve_role(member: dict[str, Any], roles: dict[str, str]) -> str:
    member_id = str(member.get("memberID") or "")
    assigned = roles.get(member_id)
    if is_relay(member) and assigned in (ROLE_LIGHT, ROLE_SWITCH, ROLE_DISABLED):
        return assigned
    if is_exu(member) and assigned in (ROLE_EXU, ROLE_DISABLED):
        return assigned
    if is_soft(member) and assigned in (ROLE_SOFT, ROLE_DISABLED):
        return assigned
    return legacy_role(member)


def cover_pairs(members: list[dict[str, Any]], directions: dict[str, str] | None = None,
                include_unconfirmed: bool = False) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Pair physical channels by group/address; optional explicit open member ID.

    Odd->open and even->close is a proposed BHS convention. Never pair across
    groups or nonadjacent addresses. The override must identify one of the pair.
    """
    directions = directions or {}
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for member in members:
        if not is_cover_channel(member):
            continue
        group, address = member.get("group"), member.get("address")
        if type(group) is not int or type(address) is not int or address < 1:
            continue
        grouped[(group, (address + 1) // 2)].append(member)
    pairs = []
    for group_pair, pair_members in grouped.items():
        if len(pair_members) != 2:
            continue
        members_sorted = sorted(pair_members, key=lambda m: m["address"])
        if members_sorted[1]["address"] != members_sorted[0]["address"] + 1:
            continue
        # Use the original pair's first (odd-address) ID as the stable key.
        key = str(members_sorted[0]["memberID"])
        preferred_open = directions.get(key)
        if preferred_open == "disabled":
            continue
        if preferred_open == str(members_sorted[1]["memberID"]):
            pairs.append((members_sorted[1], members_sorted[0]))
            continue
        if preferred_open == key:
            pairs.append((members_sorted[0], members_sorted[1]))
            continue
        # Backward compatibility for conventional names, if present.
        named_open = next((m for m in members_sorted
                           if str(m.get("name") or "").casefold().endswith("_op")
                           or "_op_" in str(m.get("name") or "").casefold()), None)
        if named_open is not None:
            pairs.append((named_open, next(m for m in members_sorted if m is not named_open)))
        elif include_unconfirmed:
            pairs.append(tuple(members_sorted))
    return pairs
