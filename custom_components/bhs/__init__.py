"""BHS Home Assistant integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import BHSApi
from .rest_api import BHSRestApi
from .const import (CONF_SCAN_INTERVAL, CONF_DEVICE_ID, CONF_PROTOCOL,
                    DEFAULT_SCAN_INTERVAL_SECONDS, PLATFORMS, PROTOCOL_REST,
                    CONF_DIMMER_MIN_BRIGHTNESS, DEFAULT_DIMMER_MIN_BRIGHTNESS,
                    CONF_DIMMER_EXPORT_ID, CONF_EXU_EXPORT_ID,
                    DEFAULT_DIMMER_EXPORT_ID, DEFAULT_EXU_EXPORT_ID,
                    CONF_COVER_TRAVEL_TIMES, DEFAULT_COVER_TRAVEL_SECONDS)
from .coordinator import BHSCoordinator


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BHS from a config entry."""
    settings = {**entry.data, **entry.options}
    if settings.get(CONF_PROTOCOL) == PROTOCOL_REST:
        api = BHSRestApi(async_get_clientsession(hass),
                         str(settings[CONF_HOST]), int(settings[CONF_PORT]),
                         str(settings[CONF_DEVICE_ID]),
                         dimmer_export_id=int(settings.get(CONF_DIMMER_EXPORT_ID, DEFAULT_DIMMER_EXPORT_ID)),
                         exu_export_id=int(settings.get(CONF_EXU_EXPORT_ID, DEFAULT_EXU_EXPORT_ID)))
    else:
        api = BHSApi(async_get_clientsession(hass),
                     str(settings[CONF_HOST]), int(settings[CONF_PORT]))
    scan_interval = int(
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
    )
    coordinator = BHSCoordinator(hass, api, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    # Shared per-dimmer configuration, persisted in config-entry options.
    configured = entry.options.get(CONF_DIMMER_MIN_BRIGHTNESS, {})
    if not isinstance(configured, dict):
        configured = {}
    coordinator.dimmer_min_brightness = {
        str(member_id): max(1, min(100, int(value)))
        for member_id, value in configured.items()
        if isinstance(value, int) and not isinstance(value, bool)
    }
    coordinator.dimmer_min_default = DEFAULT_DIMMER_MIN_BRIGHTNESS
    configured_times = entry.options.get(CONF_COVER_TRAVEL_TIMES, {})
    if not isinstance(configured_times, dict):
        configured_times = {}
    coordinator.cover_travel_times = {
        str(key): int(value) for key, value in configured_times.items()
        if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 300
    }
    coordinator.cover_travel_default = DEFAULT_COVER_TRAVEL_SECONDS
    coordinator.cover_entities = {}
    # Persist only successfully commanded levels. This is not measured feedback.
    coordinator.brightness_memory_store = Store(
        hass, 1, f"bhs_{entry.entry_id}_brightness_memory"
    )
    coordinator.brightness_memory_lock = asyncio.Lock()
    try:
        stored = await coordinator.brightness_memory_store.async_load()
    except (OSError, ValueError) as err:
        _LOGGER.warning("Unable to load BHS brightness memory: %s", err)
        stored = None
    values = stored.get("levels", {}) if isinstance(stored, dict) else {}
    coordinator.brightness_memory = {
        str(member_id): int(percent)
        for member_id, percent in values.items()
        if isinstance(member_id, str)
        and isinstance(percent, int) and not isinstance(percent, bool)
        and 1 <= percent <= 100
    } if isinstance(values, dict) else {}
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a BHS config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
