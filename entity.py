"""Base entity for BHS."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BHSCoordinator


class BHSEntity(CoordinatorEntity[BHSCoordinator]):
    """Base BHS entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BHSCoordinator, member: dict[str, Any]) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.member = member
        self.member_id = str(member["memberID"])
        self._attr_unique_id = self.member_id
        self._attr_name = str(member.get("name") or self.member_id)

    @property
    def available(self) -> bool:
        """An absent state is not a failure for stateless input members."""
        return super().available

    @property
    def device_info(self) -> DeviceInfo:
        """Return the BHS controller device."""
        guid = str(self.coordinator.info.get("serverGUID") or "unknown")
        version = self.coordinator.info.get("serverVersion")
        host = self.coordinator.api.host
        port = self.coordinator.api.port
        return DeviceInfo(
            identifiers={(DOMAIN, guid)},
            name="BHS Controller",
            manufacturer="B-Logicx",
            model="BHS Home Server",
            sw_version=str(version) if version else None,
            configuration_url=f"http://{host}:{port}",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose useful BHS metadata for testing v0.1."""
        return {
            "bhs_member_id": self.member_id,
            "bhs_member_key": self.member.get("memberKey"),
            "bhs_member_type": self.member.get("memberType"),
            "bhs_group": self.member.get("group"),
            "bhs_address": self.member.get("address"),
            "bhs_version": self.member.get("version"),
            "bhs_status": self.coordinator.data.get(self.member_id),
        }
