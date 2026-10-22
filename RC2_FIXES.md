# v0.4.3rc2 verification

1. Trigger a shutter to travel fully: it should transition to open/closed without Home Assistant thread-safety errors.
2. Stop shutter mid-travel: estimated endpoint remains unknown.
3. Ensure buttons **Stop dimming (BHS group 5)** and **Stop dimming (BHS group 6)** appear.
4. Group 6 Stop Dim action is now permitted only for a uniquely discovered SDim member at address 220; cyclic dimming starts outside group 5 remain blocked.
5. Confirm scene activation/reset, dimmer sliders and existing entity IDs still work.

Never use a Start Dim button for a different dimming group before its behavior has been verified.
