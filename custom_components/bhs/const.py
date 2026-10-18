"""Constants for the BHS integration."""

from datetime import timedelta

DOMAIN = "bhs"
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
