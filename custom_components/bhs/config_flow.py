"""Config flow for BHS."""

from __future__ import annotations

import logging
from uuid import UUID
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BHSApi
from .rest_api import BHSRestApi
from .registration import create_device_credentials, register_bhs_device
from .const import (
    CONF_DIMMER_EXPORT_ID, CONF_EXU_EXPORT_ID,
    DEFAULT_DIMMER_EXPORT_ID, DEFAULT_EXU_EXPORT_ID,
    CONF_SCAN_INTERVAL,
    CONF_DEVICE_ID,
    CONF_PROTOCOL,
    PROTOCOL_LEGACY,
    PROTOCOL_REST,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
)
from .exceptions import BHSApiError
from .member_registry import (CONF_MEMBER_ROLES, CONF_COVER_DIRECTIONS,
    is_relay, is_exu, is_soft, cover_pairs, resolve_role,
    ROLE_LIGHT, ROLE_SWITCH, ROLE_DISABLED, ROLE_SOFT, ROLE_EXU)

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the controller and return identifying information."""
    if data.get(CONF_PROTOCOL) == PROTOCOL_REST:
        api = BHSRestApi(async_get_clientsession(hass),
                         str(data[CONF_HOST]), int(data[CONF_PORT]),
                         str(data[CONF_DEVICE_ID]),
                         dimmer_export_id=int(data.get(CONF_DIMMER_EXPORT_ID, DEFAULT_DIMMER_EXPORT_ID)),
                         exu_export_id=int(data.get(CONF_EXU_EXPORT_ID, DEFAULT_EXU_EXPORT_ID)))
    else:
        api = BHSApi(async_get_clientsession(hass),
                     str(data[CONF_HOST]), int(data[CONF_PORT]))
    info = await api.get_bhs_info()
    guid = info.get("serverGUID")
    if not guid:
        raise BHSApiError("BHS controller did not return serverGUID")
    return info


class BHSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BHS."""

    VERSION = 1

    def __init__(self) -> None:
        self._registration_settings: dict[str, Any] | None = None
        self._registration_credentials: tuple[str, str, str] | None = None

    async def async_step_registration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose between a pre-registered ID and a fresh device registration."""
        if user_input is not None:
            if user_input["registration_method"] == "existing":
                return await self.async_step_existing_device()
            return await self.async_step_new_device()
        return self.async_show_form(
            step_id="registration",
            data_schema=vol.Schema({
                vol.Required("registration_method", default="existing"):
                    vol.In({"existing": "Use registered UUID", "new": "Register a new device"}),
            }),
        )

    async def async_step_new_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Register a new device without losing its generated credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            settings = {
                CONF_HOST: str(user_input[CONF_HOST]).strip(),
                CONF_PORT: int(user_input[CONF_PORT]),
                CONF_PROTOCOL: PROTOCOL_REST,
                CONF_DIMMER_EXPORT_ID: int(user_input[CONF_DIMMER_EXPORT_ID]),
                CONF_EXU_EXPORT_ID: int(user_input[CONF_EXU_EXPORT_ID]),
            }
            # Don't generate another UUID on retries in the same config flow.
            if self._registration_credentials is None:
                self._registration_credentials = await self.hass.async_add_executor_job(
                    create_device_credentials
                )
            self._registration_settings = settings
            device_id, private_key, public_key = self._registration_credentials
            try:
                status = await register_bhs_device(
                    async_get_clientsession(self.hass),
                    settings[CONF_HOST], settings[CONF_PORT],
                    device_id, public_key,
                    str(user_input.get("device_name") or "Home Assistant"),
                )
            except BHSApiError:
                _LOGGER.exception("BHS device registration failed")
                errors["base"] = "registration_failed"
            else:
                if status == "Pending":
                    return await self.async_step_await_approval()
                return await self._finish_registered_device(settings, device_id, private_key)
        return self.async_show_form(
            step_id="new_device",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required("device_name", default="Home Assistant"): str,
                vol.Required(CONF_DIMMER_EXPORT_ID, default=DEFAULT_DIMMER_EXPORT_ID):
                    vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(CONF_EXU_EXPORT_ID, default=DEFAULT_EXU_EXPORT_ID):
                    vol.All(vol.Coerce(int), vol.Range(min=1)),
            }),
            errors=errors,
        )

    async def async_step_await_approval(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for administrator approval without registering again."""
        if self._registration_credentials is None or self._registration_settings is None:
            return self.async_abort(reason="registration_session_lost")
        device_id, private_key, _ = self._registration_credentials
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return await self._finish_registered_device(
                    self._registration_settings, device_id, private_key
                )
            except BHSApiError:
                errors["base"] = "pending_approval"
        return self.async_show_form(
            step_id="await_approval",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"device_id": device_id},
        )

    async def _finish_registered_device(
        self, settings: dict[str, Any], device_id: str, private_key: str
    ) -> ConfigFlowResult:
        """Only create the integration entry once its API access is validated."""
        data = {**settings, CONF_DEVICE_ID: device_id,
                "registration_private_key": private_key}
        info = await _validate_input(self.hass, data)
        guid = str(info["serverGUID"])
        await self.async_set_unique_id(guid)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"BHS {settings[CONF_HOST]}", data=data,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer registration or existing UUID setup."""
        return await self.async_step_registration(user_input)

    async def async_step_existing_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a previously registered device without modifying it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await _validate_input(self.hass, user_input)
            except BHSApiError:
                _LOGGER.exception("Unable to connect to BHS controller")
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - keep config flow resilient
                _LOGGER.exception("Unexpected exception validating BHS controller")
                errors["base"] = "unknown"
            else:
                guid = str(info["serverGUID"])
                await self.async_set_unique_id(guid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"BHS {user_input[CONF_HOST]}",
                    data={
                        CONF_HOST: str(user_input[CONF_HOST]).strip(),
                        CONF_PORT: int(user_input[CONF_PORT]),
                        CONF_PROTOCOL: user_input.get(CONF_PROTOCOL, PROTOCOL_LEGACY),
                        CONF_DIMMER_EXPORT_ID: int(user_input.get(CONF_DIMMER_EXPORT_ID, DEFAULT_DIMMER_EXPORT_ID)),
                        CONF_EXU_EXPORT_ID: int(user_input.get(CONF_EXU_EXPORT_ID, DEFAULT_EXU_EXPORT_ID)),
                        **({CONF_DEVICE_ID: user_input[CONF_DEVICE_ID]}
                           if user_input.get(CONF_PROTOCOL) == PROTOCOL_REST else {}),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PROTOCOL, default=PROTOCOL_LEGACY): vol.In(
                    [PROTOCOL_LEGACY, PROTOCOL_REST]),
                vol.Optional(CONF_DEVICE_ID, default=""): str,
                vol.Required(CONF_DIMMER_EXPORT_ID, default=DEFAULT_DIMMER_EXPORT_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(CONF_EXU_EXPORT_ID, default=DEFAULT_EXU_EXPORT_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
            }
        )
        return self.async_show_form(step_id="existing_device", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlowWithReload:
        """Return the BHS options flow."""
        return BHSOptionsFlow()


class BHSOptionsFlow(OptionsFlowWithReload):
    """Handle BHS integration options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select options group."""
        return self.async_show_menu(step_id="init", menu_options=[
            "general", "member_mapping", "cover_mapping",
        ])

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage connectivity and export options."""
        if user_input is not None:
            # Keep per-entity settings saved by number entities.
            return self.async_create_entry(data={**self.config_entry.options, **user_input})

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_PROTOCOL, default=current.get(CONF_PROTOCOL, PROTOCOL_LEGACY)):
                    vol.In([PROTOCOL_LEGACY, PROTOCOL_REST]),
                vol.Required(CONF_PORT, default=current.get(CONF_PORT, DEFAULT_PORT)):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Optional(CONF_DEVICE_ID, default=current.get(CONF_DEVICE_ID, "")): str,
                vol.Required(CONF_DIMMER_EXPORT_ID, default=current.get(CONF_DIMMER_EXPORT_ID, DEFAULT_DIMMER_EXPORT_ID)): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(CONF_EXU_EXPORT_ID, default=current.get(CONF_EXU_EXPORT_ID, DEFAULT_EXU_EXPORT_ID)): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=MIN_SCAN_INTERVAL_SECONDS,
                        max=MAX_SCAN_INTERVAL_SECONDS,
                    ),
                )
            }
        )
        return self.async_show_form(step_id="general", data_schema=schema)

    async def async_step_member_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a member by its friendly BHS name, not its identifier."""
        coordinator = self.config_entry.runtime_data
        members = [m for m in coordinator.members
                   if is_relay(m) or is_exu(m) or is_soft(m)]
        if not members:
            return self.async_abort(reason="no_members")

        # The selected ID remains stable even when a member is renamed.
        members.sort(key=lambda m: (str(m.get("name") or "").casefold(),
                                    str(m["memberID"])))
        options = {}
        for member in members:
            mid = str(member["memberID"])
            label = str(member.get("name") or f"Member {mid}")
            group, address = member.get("group"), member.get("address")
            category = ("Relay" if is_relay(member) else
                        "EXU" if is_exu(member) else "SoftM")
            options[mid] = f"{label} ({category} · G{group} A{address})"

        if user_input is not None:
            chosen = str(user_input.get("member", ""))
            if chosen in options:
                self._selected_member_id = chosen
                return await self.async_step_member_role()

        return self.async_show_form(
            step_id="member_mapping",
            data_schema=vol.Schema({vol.Required("member"): vol.In(options)}),
        )

    async def async_step_member_role(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit one selected role while keeping memberID as the storage key."""
        member_id = getattr(self, "_selected_member_id", None)
        member = next((m for m in self.config_entry.runtime_data.members
                       if str(m.get("memberID")) == member_id), None)
        if member is None or not (is_relay(member) or is_exu(member) or is_soft(member)):
            return self.async_abort(reason="no_members")

        if is_relay(member):
            choices = {ROLE_LIGHT: "Light", ROLE_SWITCH: "Switch / socket",
                       ROLE_DISABLED: "Disabled"}
        elif is_exu(member):
            choices = {ROLE_EXU: "EXU manual/automatic mode (enable writes)",
                       ROLE_DISABLED: "Disabled"}
        else:
            choices = {ROLE_SOFT: "SoftM switch (enable writes)",
                       ROLE_DISABLED: "Disabled"}

        current = dict(self.config_entry.options.get(CONF_MEMBER_ROLES, {}))
        if user_input is not None:
            role = user_input.get("role")
            if role in choices:
                current[member_id] = role
                return self.async_create_entry(
                    data={**self.config_entry.options, CONF_MEMBER_ROLES: current}
                )

        name = str(member.get("name") or member_id)
        return self.async_show_form(
            step_id="member_role",
            data_schema=vol.Schema({
                vol.Required("role", default=resolve_role(member, current)):
                    vol.In(choices)
            }),
            description_placeholders={
                "member_name": name,
                "member_id": member_id,
                "group": str(member.get("group", "?")),
                "address": str(member.get("address", "?")),
            },
        )

    async def async_step_cover_mapping(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a shutter by friendly channel names before changing directions."""
        coordinator = self.config_entry.runtime_data
        # Include disabled and unconfirmed pairs so they can be enabled later.
        pairs = cover_pairs(coordinator.members, {}, include_unconfirmed=True)
        choices: dict[str, str] = {}
        for first, second in pairs:
            low, high = sorted((first, second), key=lambda m: m["address"])
            pair_key = str(low["memberID"])
            first_name = str(low.get("name") or pair_key)
            second_name = str(high.get("name") or high["memberID"])
            # Use both real channel names even without a _OP/_NEER convention.
            choices[pair_key] = (
                f"{first_name} / {second_name} "
                f"(G{low['group']} A{low['address']}–{high['address']})"
            )
        if not choices:
            return self.async_abort(reason="no_covers")
        if user_input is not None:
            selected = str(user_input.get("cover", ""))
            if selected in choices:
                self._selected_cover_key = selected
                return await self.async_step_cover_direction()
        return self.async_show_form(
            step_id="cover_mapping",
            data_schema=vol.Schema({vol.Required("cover"): vol.In(choices)}),
        )

    async def async_step_cover_direction(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose which physical relay opens the selected shutter."""
        key = getattr(self, "_selected_cover_key", None)
        pairs = cover_pairs(self.config_entry.runtime_data.members, {},
                            include_unconfirmed=True)
        pair = next((sorted((a, b), key=lambda m: m["address"])
                     for a, b in pairs
                     if str(min((a, b), key=lambda m: m["address"])["memberID"]) == key), None)
        if pair is None:
            return self.async_abort(reason="no_covers")
        low, high = pair
        low_id, high_id = str(low["memberID"]), str(high["memberID"])
        options = {
            "disabled": "Disabled / do not control",
            low_id: f"{low.get('name') or low_id} (address {low['address']}) opens",
            high_id: f"{high.get('name') or high_id} (address {high['address']}) opens",
        }
        stored = dict(self.config_entry.options.get(CONF_COVER_DIRECTIONS, {}))
        if user_input is not None:
            selected = str(user_input.get("opening_relay", ""))
            if selected in options:
                stored[low_id] = selected
                return self.async_create_entry(data={
                    **self.config_entry.options, CONF_COVER_DIRECTIONS: stored,
                })

        # Preserve the previously inferred direction for pre-0.4.3 installs.
        default = stored.get(low_id)
        if default not in options:
            inferred = cover_pairs([low, high], {}, include_unconfirmed=False)
            default = str(inferred[0][0]["memberID"]) if inferred else "disabled"
        return self.async_show_form(
            step_id="cover_direction",
            data_schema=vol.Schema({
                vol.Required("opening_relay", default=default): vol.In(options)
            }),
            description_placeholders={
                "first_name": str(low.get("name") or low_id),
                "second_name": str(high.get("name") or high_id),
                "group": str(low["group"]),
                "first_address": str(low["address"]),
                "second_address": str(high["address"]),
            },
        )
