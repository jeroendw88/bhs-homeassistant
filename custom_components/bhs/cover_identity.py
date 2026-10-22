"""Stable identity for paired BHS shutter channels.

Retain pre-0.4.3 Home Assistant unique IDs (which depended on relay direction).
The physical pair is keyed by its members, independent of the open direction.
"""
from __future__ import annotations

from homeassistant.helpers import entity_registry as er
from .const import DOMAIN


def pair_identity(hass, first: dict, second: dict) -> str:
    """Resolve one shared, direction-independent identity for cover and timer.

    Existing entity registry entries take precedence, so earlier installations
    keep their entity IDs even if they already reversed direction in b3.
    """
    low, high = sorted((first, second), key=lambda m: int(m["address"]))
    low_id, high_id = str(low["memberID"]), str(high["memberID"])
    normal = f"{low_id}_{high_id}_cover"
    reversed_id = f"{high_id}_{low_id}_cover"
    registry = er.async_get(hass)
    for domain, suffix in (("cover", ""), ("number", "_travel_time")):
        for identity in (normal, reversed_id):
            if registry.async_get_entity_id(domain, DOMAIN, identity + suffix):
                return identity

    # The old integration preferred the _OP member, otherwise the first address.
    low_name = str(low.get("name") or "").casefold()
    high_name = str(high.get("name") or "").casefold()
    low_op = low_name.endswith("_op") or "_op_" in low_name
    high_op = high_name.endswith("_op") or "_op_" in high_name
    if high_op and not low_op:
        return reversed_id
    return normal
