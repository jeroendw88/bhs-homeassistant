"""Switch platform for BHS software members and SDim scenes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BHSCoordinator
from .entity import BHSEntity
from .rest_api import BHSRestApi
from .sdim import sdim_role, validated_sdim_members
from .member_registry import (is_relay, is_soft, is_exu, resolve_role,
                              ROLE_SWITCH, ROLE_SOFT, ROLE_EXU)



def _is_scene(member: dict[str, Any]) -> bool:
    """Recognize SDim scene slots 221-228, independent of scene name."""
    return sdim_role(member) == "scene"


def _group_reset_members(members: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Find an unambiguous SDim reset (address 219) for each group."""
    return {group: member for (group, address), member
            in validated_sdim_members(members).items() if address == 219}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BHS software-member and SDim scene switches."""
    coordinator: BHSCoordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        BHSRelaySwitch(coordinator, member)
        for member in coordinator.members
        if is_relay(member) and resolve_role(member, coordinator.member_roles) == ROLE_SWITCH
    ]
    entities.extend(
        BHSSoftMemberSwitch(coordinator, member)
        for member in coordinator.members
        if is_soft(member) and resolve_role(member, coordinator.member_roles) == ROLE_SOFT
    )

    if isinstance(coordinator.api, BHSRestApi):
        entities.extend(
            BHSExuModeSwitch(coordinator, member)
            for member in coordinator.members
            if is_exu(member) and str(member.get('memberID')) in coordinator.exu_detectors
        )

    if isinstance(coordinator.api, BHSRestApi):
        entities.extend(
            BHSExuTimerUnitsSwitch(coordinator, member)
            for member in coordinator.members
            if is_exu(member) and str(member.get("memberID")) in coordinator.exu_detectors
        )

    validated = validated_sdim_members(coordinator.members)
    group_resets = _group_reset_members(coordinator.members)
    for member in coordinator.members:
        if not _is_scene(member):
            continue
        group = member.get("group")
        if validated.get((group, member.get("address"))) is not member:
            continue
        reset_member = group_resets.get(group) if isinstance(group, int) else None
        if reset_member is not None:
            entities.append(BHSSDimSceneSwitch(coordinator, member, reset_member))

    async_add_entities(entities)


class BHSRelaySwitch(BHSEntity, SwitchEntity):
    """BHS RLM_4 relay output controlled using Set and Reset."""

    @property
    def icon(self) -> str:
        """Return a socket icon for SK_ members and a generic relay icon otherwise."""
        name = str(self.member.get("name") or "")
        if name.startswith("SK_"):
            return "mdi:power-socket-eu"
        return "mdi:electric-switch"

    @property
    def is_on(self) -> bool | None:
        """Return whether this relay reports Set."""
        status = self.coordinator.data.get(self.member_id)
        if status is None:
            return None
        return status.casefold() == "set"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Energize the relay."""
        await self.coordinator.api.command_member(self.member_id, "set")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """De-energize the relay."""
        await self.coordinator.api.command_member(self.member_id, "reset")
        await self.coordinator.async_request_refresh()


class BHSSoftMemberSwitch(BHSEntity, SwitchEntity):
    """BHS software member controlled using Set and Reset."""

    _attr_icon = "mdi:state-machine"

    @property
    def is_on(self) -> bool | None:
        """Return whether this software member reports Set."""
        status = self.coordinator.data.get(self.member_id)
        if status is None:
            return None
        return status.casefold() == "set"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send Set to the SoftwareMember."""
        await self.coordinator.api.command_member(self.member_id, "set")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send Reset to the SoftwareMember."""
        await self.coordinator.api.command_member(self.member_id, "reset")
        await self.coordinator.async_request_refresh()


class BHSSDimSceneSwitch(BHSEntity, SwitchEntity):
    """BHS stored SDim scene represented as a stateful switch."""

    _attr_icon = "mdi:palette-outline"

    def __init__(
        self,
        coordinator: BHSCoordinator,
        member: dict[str, Any],
        group_reset_member: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, member)
        self._group_reset_member_id = str(group_reset_member["memberID"])
        self._attr_unique_id = f"{self.member_id}_sdim_scene"
        self._attr_name = str(member.get("name") or self.member_id)

    @property
    def is_on(self) -> bool | None:
        """Return whether BHS reports this scene as active."""
        status = self.coordinator.data.get(self.member_id)
        if status is None:
            return None
        return status.casefold() == "set"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate this scene using the BHS Dimmer function."""
        await self.coordinator.api.command_member(self.member_id, "dimmer")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate active scenes by triggering this group's GroepsReset Dim."""
        await self.coordinator.api.command_member(self._group_reset_member_id, "dimmer")
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose BHS metadata plus the group reset member used for OFF."""
        attrs = dict(super().extra_state_attributes)
        attrs["bhs_group_reset_member_id"] = self._group_reset_member_id
        return attrs


class BHSExuModeSwitch(BHSEntity, SwitchEntity):
    """API-reported EXU operating mode: On = manual, Off = automatic."""

    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: BHSCoordinator, member: dict[str, Any]) -> None:
        super().__init__(coordinator, member)
        self._attr_unique_id = f"{self.member_id}_exu_manual_mode"
        self._attr_name = f"{member.get('name') or self.member_id} Manual mode"

    @property
    def is_on(self) -> bool | None:
        detector = self.coordinator.exu_detectors.get(self.member_id)
        return detector.get("manual") if detector else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.set_motion_detector_mode(self.member_id, True)
        await self.coordinator.async_refresh_exu()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.set_motion_detector_mode(self.member_id, False)
        await self.coordinator.async_refresh_exu()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = dict(super().extra_state_attributes)
        detector = self.coordinator.exu_detectors.get(self.member_id, {})
        attrs["bhs_follow_input"] = detector.get("followInput")
        attrs["bhs_mode_source"] = "getMotionDetectorsByExport"
        return attrs


class BHSExuTimerUnitsSwitch(BHSEntity, SwitchEntity):
    """On = minutes; Off = seconds. Updates the BHS module configuration."""

    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: BHSCoordinator, member: dict[str, Any]) -> None:
        super().__init__(coordinator, member)
        self._attr_unique_id = f"{self.member_id}_exu_timer_minutes"
        self._attr_name = f"{member.get('name') or self.member_id} Timer in minutes"

    @property
    def is_on(self) -> bool | None:
        detector = self.coordinator.exu_detectors.get(self.member_id, {})
        timer = detector.get("timer")
        return timer.get("inMinutes") if isinstance(timer, dict) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_exu_timer(self.member_id, in_minutes=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_exu_timer(self.member_id, in_minutes=False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = dict(super().extra_state_attributes)
        detector = self.coordinator.exu_detectors.get(self.member_id, {})
        attrs["bhs_follow_input"] = detector.get("followInput")
        attrs["bhs_module_programming_failed"] = self.member_id in self.coordinator.exu_programming_failed
        return attrs
