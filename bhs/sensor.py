"""Read-only BHS controller health and event-polling diagnostics."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import BHSCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator: BHSCoordinator = entry.runtime_data
    async_add_entities(BHSDiagnosticSensor(coordinator, entry.entry_id, key)
                       for key in ("connection", "last_response", "last_event", "last_full_sync",
                                   "events_received", "full_sync_count", "communication_errors",
                                   "fresh_resync_requests"))


class BHSDiagnosticSensor(CoordinatorEntity[BHSCoordinator], SensorEntity):
    """Read-only statistics on the controller, independent of member states."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False
    _LABELS = {
        "connection": "Connection status",
        "last_response": "Last successful response",
        "last_event": "Last event received",
        "last_full_sync": "Last full state sync",
        "events_received": "Events received",
        "full_sync_count": "Full synchronizations",
        "communication_errors": "Communication errors",
        "fresh_resync_requests": "Fresh resync requests",
    }

    def __init__(self, coordinator: BHSCoordinator, entry_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = self._LABELS[key]
        self._attr_unique_id = f"{entry_id}_diag_{key}"
        if key.startswith("last_"):
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        if key in ("events_received", "full_sync_count", "communication_errors",
                   "fresh_resync_requests"):
            self._attr_native_unit_of_measurement = "events" if key == "events_received" else None
            self._attr_state_class = SensorStateClass.TOTAL

    @property
    def device_info(self) -> DeviceInfo:
        guid = str(self.coordinator.info.get("serverGUID") or "unknown")
        version = self.coordinator.info.get("serverVersion")
        return DeviceInfo(identifiers={(DOMAIN, guid)}, name="BHS Controller",
                          manufacturer="B-Logicx", model="BHS Home Server",
                          sw_version=str(version) if version else None,
                          configuration_url=f"http://{self.coordinator.api.host}:{self.coordinator.api.port}")

    @property
    def available(self) -> bool:
        # Health indicators must remain readable during an API outage.
        return True

    @property
    def native_value(self) -> str | int | datetime | None:
        c = self.coordinator
        if self._key == "connection":
            return "Connected" if c.last_update_success else "Disconnected"
        return getattr(c, self._key if self._key not in ("last_response", "last_event", "last_full_sync")
                       else self._key + "_at", None)
