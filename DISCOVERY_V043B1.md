# BHS v0.4.3b1 — member-type discovery preview

This **beta** is intended for a controlled test, not a stable public release.
It builds on v0.4.2 and preserves the existing REST polling, dimmer memory,
per-cover travel time and EXU controls.

## What's new

- RLM_4 `memberType=1` relays are discovered independent of naming; their default
  HA type is a switch, except legacy `VER_` outputs retained as lights.
- DIM1K_15 `memberType=2` channels on verified REST group 5 are exposed as lights
  without a `DIM_` name requirement. Absolute brightness still needs a validated
  DATAW/TIMER pair in the selected dimmer export.
- `memberType=20` RLM_4 paired shutter outputs can be identified without
  `_OP`/`_NEER`; unknown direction pairs require explicit confirmation.
- `memberType=17` EXU_192 and `memberType=4` SoftM can be opted into controls
  by member ID. Previously tested legacy members remain enabled automatically.
- Configuration -> Member roles or Shutter directions controls these mappings.
  Mappings are stored in config entry options by BHS member ID.

## Critical safety rules

- **Confirm shutter motor wiring before enabling pairs**. A wrongly assigned
  direction can issue the wrong motor command. Unrecognized pairs stay disabled.
- Generic relay switches are visible but REST Set/Reset commands remain blocked
  unless the member has an explicit light/switch mapping or a legacy tested
  `VER_`/`SK_` group-2 identity. Set the mapping before controlling new relays.
- EXU_192 and SoftM controls remain disabled by default on unrecognized hardware.
  Enabling them opts into their Set/Reset operation; confirm device behavior.
- DIM1K brightness and cyclic dimming are currently limited to known-compatible
  group-5 commands; other group configurations require protocol validation.
- SDim special scene/reset/record behavior still relies on known command names.

## Upgrade behavior

- Unchanged members keep their existing entity unique IDs.
- Changing a relay from a switch to light (or vice versa) changes the HA domain
  and may create a new entity ID; update any automations or dashboard references.
- Reversing an existing shutter pair changes the cover's constructed unique ID;
  treat that as an explicit migration, not a cosmetic change.
- A new unrecognized shutter pair has no cover entity until you confirm its
  direction in Configure -> Shutter direction mapping.
- Configuring options reloads the integration. This briefly interrupts polling.
- All previous brightness/travel time settings remain in config entry options.

## Recommended smoke tests

1. Back up your Home Assistant configuration and integration.
2. Check existing `VER_` lights and `SK_` switches retain names/entities.
3. Check one DIM1K brightness slider and stored minimum brightness.
4. Check existing EXU manual/automatic mode controls.
5. Check existing shutter travel timers and interrupt/unknown behavior.
6. Open Configure -> Member roles; find a relay with an arbitrary name and map it.
7. Open Configure -> Shutter direction mapping; verify the displayed channels.
8. Examine log errors and verify that changing the role doesn't permit unexpected commands.

This version has passed Python syntax compilation and pure classification tests,
not an end-to-end Home Assistant installation test.

### v0.4.3b3 shutter pairing UI
Choose **Configure → Shutter direction mapping**, select a named shutter pair, then choose which relay opens it (or Disabled). Saved values use member IDs. The selection UI does not itself move the shutter.
