# Changelog

## 0.4.1 — 2026-10-18

- Adds native brightness sliders to group-5 DIM1K dimmers whose DATAW/TIMER commands are validated against BHS export ID 2.
- Adds a per-dimmer, persistent minimum brightness (default 5%) to prevent low nonzero levels from switching the light off.
- Remembers each dimmer’s last successfully commanded brightness across On/Off cycles and Home Assistant restarts.
- Preserves v0.4.0 REST control, event polling, DataSnap compatibility, diagnostics and entity identities.
- Brightness is last-commanded only: BHS does not provide measured absolute brightness feedback.

## 0.4.1b3 — Per-dimmer brightness memory

- Persist the last successfully commanded nonzero absolute brightness per DIM1K channel in Home Assistant storage, keyed by integration entry and member ID.
- A normal On command restores that level using the tested DATAW/TIMER sequence; if no level has ever been sent, it preserves the prior Set behavior.
- Off preserves the stored level, while explicit 0 brightness still performs Off.
- Apply the configured minimum brightness to restored levels; keep the memory separate from actual bus brightness feedback.
- Do not change legacy DataSnap control, scenes, covers, sockets, SoftM, or event polling.

## v0.4.1b2 — Per-dimmer minimum brightness

- Adds a persisted configuration number entity for each REST DIM1K brightness-capable light (default 5%, configurable 1–100%).
- Clamps positive brightness requests to the configured minimum; explicit Off remains Off.
- Displays the effective last-commanded brightness and exposes the configured minimum as a light attribute.
- Existing REST commands, discovery and polling remain unchanged.

## 0.4.1b1 — DIM1K brightness preview

- Add native brightness sliders for group-5 DIM1K channels whose DATAW and TIMER actions are validated against BHS export ID 2 at startup.
- Serialize paired press/release raw telegrams; preserve all existing relay, dimming and scene operations.
- Brightness reflects last requested level only, not measured bus feedback.
- No brightness slider appears if the export cannot be read or its actions do not match.


## 0.4.0 — 2026-10-17

Stable release based on the live-tested `0.4.0b8.post1` integration:

- Added BHS REST API client using a pre-registered UUID in unsecured (`isSecure: false`) mode, preserving DataSnap support.
- Migrated discovery and state polling, and added event-backed updates with periodic full-state reconciliation.
- Enabled tested REST commands for VER lighting, SK sockets, group-3 shutters/screens, DIM1K on/off, group-5 start/stop dimming, supported SDim scenes, and selected BWM SoftM members.
- Added controller health and event diagnostics, fixed diagnostic sensor registration and counter metadata.
- Corrected diagnostic export's REST protocol identification and updated release documentation.
- Preserved existing member-based unique IDs and configuration-entry migration path.

### Limitations

Encrypted REST operation, additional SoftM categories, and group-6 continuous dimming are deferred. Initial setup failure can make diagnostic sensors unavailable; simulated network recovery was not independently tested.

---

## 0.4.0b8.post1
- Fix diagnostic sensor registration using EntityCategory.DIAGNOSTIC enum.
- Use TOTAL state class for counters that reset after reload.
- No changes to event polling or device commands.

## 0.4.0b8
- Read-only connection health and event statistics sensors.
- Diagnostic export includes last successful API response and counters.
- Existing commands and polling behavior unchanged.

## 0.4.0b7 — REST event-backed state updates (preview)
- Polls `/api/members/getChanges` every 1–2 seconds in REST mode.
- Starts event consumption before taking the first state snapshot.
- Merges ordered state events into the existing coordinator state map.
- Resynchronizes on `fresh: true`, API failures, malformed events, and every 60 seconds.
- Keeps DataSnap polling and all v0.4.0b6 controls unchanged.
- Sensor events are intentionally ignored until dedicated entities are added.

## 0.4.0b5 — Group-5 cyclic dimming buttons
- Allow REST `dimmer` function for discovered group-5 DIM1K channels.
- Allow REST `dimmer` on group-5 SDim Stop Dim (address 220).
- Require valid group-5 Stop Dim discovery before enabling Start.
- Preserve prior relay, cover, DIM1K on/off and scene functionality.
- Group 6 continuous dimming remains blocked pending live testing.

## 0.4.0b4
- Enable scoped DIM1K Set/Reset and SDim scene activation/group reset in REST mode.
- Keep cyclic dimming and record functions blocked.

# Changelog

## 0.3.1

- Added all remaining `RLM_4` relay outputs (`memberType == 1`) as Home Assistant switches.
- Existing `VER_` relay lights remain lights and shutter/screen relay pairs remain covers, preventing duplicate entities.
- `SK_` socket relays use a power-socket icon; other relay outputs use a generic electric-switch icon.

## 0.3.0

- Added configurable 1–60 second polling interval through the integration options flow.
- Added privacy-safe Home Assistant diagnostics.
- Added richer BHS controller device metadata and configuration URL.
- Preserved all v0.2.2 control semantics and entity unique IDs.
- Refreshed English and Dutch config/options translations.
- Updated HACS metadata and repository documentation.

## 0.2.2

- Changed SDim stored scenes from buttons to stateful switches.
- Scene ON calls `Dimmer` on the scene member.
- Scene OFF calls `Dimmer` on the group's `GroepsReset Dim` member.

## 0.2.1

- Made cover direction changes safe by resetting the opposite relay before setting the requested direction.

## 0.2.0

- Added INM inputs, SoftM members, covers and SDim controls.

## 0.1.0

- Initial BHS integration with relay and DIM1K lights.

## 0.4.0b6
- Enable narrowly allowlisted BWM SoftM bypass/down Set/Reset commands in REST mode.
- Preserve all previously tested REST and legacy operations.
