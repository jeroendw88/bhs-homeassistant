"""Data coordinator for the legacy BHS and new event-based REST APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from time import monotonic
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BHSApi
from .rest_api import BHSRestApi
from .const import DOMAIN
from .exceptions import BHSApiError

_LOGGER = logging.getLogger(__name__)
_FULL_SYNC_SECONDS = 60


class BHSCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Maintain state from bus events with periodic full snapshot validation."""

    def __init__(self, hass: HomeAssistant, api: BHSApi | BHSRestApi, scan_interval: int) -> None:
        self._rest_events = isinstance(api, BHSRestApi)
        # Events should be collected every 1-2 seconds. A long legacy interval
        # is still accepted but does not slow the REST event consumer.
        effective_interval = min(scan_interval, 2) if self._rest_events else scan_interval
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=effective_interval),
        )
        self.api = api
        self.members: list[dict[str, Any]] = []
        self.info: dict[str, Any] = {}
        self._needs_snapshot = self._rest_events
        self._last_snapshot = 0.0
        # Volatile diagnostics: reset on integration reload, never persisted.
        self.last_response_at: datetime | None = None
        self.last_event_at: datetime | None = None
        self.last_full_sync_at: datetime | None = None
        self.events_received = 0
        self.full_sync_count = 0
        self.communication_errors = 0
        self.fresh_resync_requests = 0

    async def _async_setup(self) -> None:
        """Discover controller and member metadata on startup."""
        try:
            self.info = await self.api.get_bhs_info()
            self.members = await self.api.get_members()
        except BHSApiError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_data(self) -> dict[str, str]:
        """Legacy: full poll. REST: consume changes before taking snapshots."""
        if not self._rest_events:
            try:
                states = await self.api.get_member_states()
                self.last_response_at = datetime.now(timezone.utc)
                self.last_full_sync_at = self.last_response_at
                self.full_sync_count += 1
                return states
            except BHSApiError as err:
                self.communication_errors += 1
                raise UpdateFailed(str(err)) from err

        try:
            # Order matters: subscribe/consume first, snapshot second. Events
            # occurring during the snapshot are replayed on the next cycle.
            events = await self.api.get_changes()
            self.last_response_at = datetime.now(timezone.utc)
            self.events_received += len(events["changes"])
            if events["changes"]:
                self.last_event_at = self.last_response_at
            if events["fresh"]:
                self.fresh_resync_requests += 1
                self._needs_snapshot = True

            now = monotonic()
            if (self._needs_snapshot or self.data is None
                    or now - self._last_snapshot >= _FULL_SYNC_SECONDS):
                snapshot = await self.api.get_member_states()
                self._last_snapshot = monotonic()
                self.last_response_at = datetime.now(timezone.utc)
                self.last_full_sync_at = self.last_response_at
                self.full_sync_count += 1
                self._needs_snapshot = False
                return snapshot

            states = dict(self.data)
            for change in events["changes"]:
                if not isinstance(change, dict):
                    self._needs_snapshot = True
                    continue
                if change.get("type") != "state":
                    # Sensor events are reserved for a future version; the
                    # existing HA entity model uses only binary state data.
                    continue
                member_id = change.get("memberID")
                is_on = change.get("on")
                if not isinstance(member_id, str) or not isinstance(is_on, bool):
                    self._needs_snapshot = True
                    continue
                # Ignore members outside this integration's discovery set,
                # including events belonging to other exports.
                if member_id in self._known_member_ids:
                    states[member_id] = "Set" if is_on else "Reset"
            return states
        except BHSApiError as err:
            # A consumed event response may have been lost: always take a new
            # snapshot after reconnection, rather than trusting cached state.
            self._needs_snapshot = True
            self.communication_errors += 1
            raise UpdateFailed(str(err)) from err

    @property
    def _known_member_ids(self) -> set[str]:
        return {str(member["memberID"]) for member in self.members
                if isinstance(member, dict) and member.get("memberID")}
