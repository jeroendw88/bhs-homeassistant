"""BHS Home Assistant integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BHSApi
from .rest_api import BHSRestApi
from .const import (CONF_SCAN_INTERVAL, CONF_DEVICE_ID, CONF_PROTOCOL,
                    DEFAULT_SCAN_INTERVAL_SECONDS, PLATFORMS, PROTOCOL_REST)
from .coordinator import BHSCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BHS from a config entry."""
    settings = {**entry.data, **entry.options}
    if settings.get(CONF_PROTOCOL) == PROTOCOL_REST:
        api = BHSRestApi(async_get_clientsession(hass),
                         str(settings[CONF_HOST]), int(settings[CONF_PORT]),
                         str(settings[CONF_DEVICE_ID]))
    else:
        api = BHSApi(async_get_clientsession(hass),
                     str(settings[CONF_HOST]), int(settings[CONF_PORT]))
    scan_interval = int(
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
    )
    coordinator = BHSCoordinator(hass, api, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a BHS config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
