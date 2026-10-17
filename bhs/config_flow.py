"""Config flow for BHS."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BHSApi
from .rest_api import BHSRestApi
from .const import (
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

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the controller and return identifying information."""
    if data.get(CONF_PROTOCOL) == PROTOCOL_REST:
        api = BHSRestApi(async_get_clientsession(hass),
                         str(data[CONF_HOST]), int(data[CONF_PORT]),
                         str(data[CONF_DEVICE_ID]))
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user setup."""
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
                        **({CONF_DEVICE_ID: user_input[CONF_DEVICE_ID]}
                           if user_input.get(CONF_PROTOCOL) == PROTOCOL_REST else {}),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default="192.168.10.7"): str,
                vol.Required(CONF_PROTOCOL, default=PROTOCOL_LEGACY): vol.In(
                    [PROTOCOL_LEGACY, PROTOCOL_REST]),
                vol.Optional(CONF_DEVICE_ID, default=""): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

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
        """Manage BHS options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_PROTOCOL, default=current.get(CONF_PROTOCOL, PROTOCOL_LEGACY)):
                    vol.In([PROTOCOL_LEGACY, PROTOCOL_REST]),
                vol.Required(CONF_PORT, default=current.get(CONF_PORT, DEFAULT_PORT)):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Optional(CONF_DEVICE_ID, default=current.get(CONF_DEVICE_ID, "")): str,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=MIN_SCAN_INTERVAL_SECONDS,
                        max=MAX_SCAN_INTERVAL_SECONDS,
                    ),
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
