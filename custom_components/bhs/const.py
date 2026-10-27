"""Constants for the BHS integration."""

from datetime import timedelta

DOMAIN = "bhs"
INTEGRATION_VERSION = "0.4.5b1"
DEFAULT_PORT = 10014
DEFAULT_SCAN_INTERVAL_SECONDS = 2
MIN_SCAN_INTERVAL_SECONDS = 1
MAX_SCAN_INTERVAL_SECONDS = 60
DEFAULT_SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS)

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PROTOCOL = "protocol"
CONF_DEVICE_ID = "device_id"
PROTOCOL_LEGACY = "datasnap"
PROTOCOL_REST = "rest"

PLATFORMS = ["light", "button", "binary_sensor", "switch", "cover", "sensor", "number"]

CONF_DIMMER_MIN_BRIGHTNESS = "dimmer_min_brightness"
DEFAULT_DIMMER_MIN_BRIGHTNESS = 5

CONF_DIMMER_EXPORT_ID = "dimmer_export_id"
CONF_EXU_EXPORT_ID = "exu_export_id"
DEFAULT_DIMMER_EXPORT_ID = 2
DEFAULT_EXU_EXPORT_ID = 7
CONF_COVER_TRAVEL_TIMES = "cover_travel_times"
DEFAULT_COVER_TRAVEL_SECONDS = 30
