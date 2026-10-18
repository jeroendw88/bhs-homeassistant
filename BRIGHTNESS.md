# DIM1K brightness control (v0.4.1)

On REST installations, BHS export ID 2 must be accessible to the registered device and contain the validated DATAW press and TIMER release actions for the dimmer. The integration sends the requested level as ordered raw bus telegrams.

Each supported light exposes a Home Assistant brightness slider. Each has a separate Minimum brightness setting (default 5%, adjustable 1–100%). A nonzero request below the minimum is clamped, while an explicit Off continues to switch the light off.

The integration stores the last successfully commanded nonzero brightness per member ID across restarts and restores it on a plain On command. The stored level does not represent physical feedback; scenes and wall switches can change actual light brightness without updating it.

**Caution:** The bus actions involve two separate requests; the BHS API does not guarantee the two commands are atomic. The integration serializes its own writes but cannot prevent other bus clients from interleaving. Export ID 2 and bus actions are installation-specific.
