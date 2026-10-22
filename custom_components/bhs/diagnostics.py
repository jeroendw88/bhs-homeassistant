"""Diagnostics support for BHS."""

from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS, INTEGRATION_VERSION
from .rest_api import BHSRestApi
from .coordinator import BHSCoordinator


def _member_summary(members: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a privacy-safe summary of configured BHS members."""
    by_type = Counter(str(member.get("memberType")) for member in members)
    by_version = Counter(
        str(member.get("version") or "unknown") for member in members
    )
    return {
        "total": len(members),
        "by_member_type": dict(sorted(by_type.items())),
        "by_version": dict(sorted(by_version.items())),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a BHS config entry without personal/network data."""
    coordinator: BHSCoordinator = entry.runtime_data
    states = coordinator.data or {}
    status_counts = Counter(str(status).casefold() for status in states.values())

    return {
        "integration": {
            "version": INTEGRATION_VERSION,
            "protocol": "rest" if isinstance(coordinator.api, BHSRestApi) else "datasnap",
            "scan_interval_seconds": int(
                entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
            ),
        },
        "controller": {
            "server_version": coordinator.info.get("serverVersion"),
            "guardian_version": coordinator.info.get("guardianVersion"),
            "bus_connected": coordinator.info.get("busConnected"),
            "safe_protocol": coordinator.info.get("safeProtocol"),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "state_count": len(states),
            "last_response": coordinator.last_response_at.isoformat() if coordinator.last_response_at else None,
            "last_event": coordinator.last_event_at.isoformat() if coordinator.last_event_at else None,
            "last_full_sync": coordinator.last_full_sync_at.isoformat() if coordinator.last_full_sync_at else None,
            "events_received": coordinator.events_received,
            "full_sync_count": coordinator.full_sync_count,
            "communication_errors": coordinator.communication_errors,
            "fresh_resync_requests": coordinator.fresh_resync_requests,
            "status_counts": dict(sorted(status_counts.items())),
        },
        "members": _member_summary(coordinator.members),
    }
