## v0.4.4b1 — Export-backed EXU controls (beta)

- Built from the published **v0.4.3** GitHub tag, preserving its SDim, shutter and DIM1K fixes.
- Discover motion detectors from the configured EXU mobile export using `getMotionDetectorsByExport`.
- Read the Manual mode state from the API's `manual` setting, not last observed bus Set/Reset; retain existing EXU switch unique IDs.
- Switch mode using `setMotionDetector`.
- Add a 0–255 Motion timer number and Timer in minutes configuration switch; write only the changed setting via `setMotionDetectorTimer`.
- Reject module-programming failures (including HTTP 500/503) and expose a diagnostic failure attribute on timer entities.
- Poll EXU export settings every 15 seconds separately from normal `getChanges` events.
- Skip EXU members with null `manual` and unsupported timer values; leave `followInput` read-only.

**Beta / caution:** Timer writes program device configuration (EEPROM). The BHS server may save settings even when it reports failed module programming; resolve failed operations in BLConfig before relying on them. BHS secured/encrypted REST mode remains unsupported.

## v0.4.3 — Universal member discovery (stable)

- Promote the user-tested v0.4.3rc2 implementation without changing control logic.
- Discover supported members primarily from BHS MemberType and module metadata.
- Classify relays and configure optional EXU/SoftM controls by member name, storing member IDs.
- Configure shutter direction by discovered relay names while preserving cover IDs and travel-time settings.
- Identify SDim group reset (219), Stop Dim (220), scene slots (221–228), and record slot (229) by address.
- Use validated mobile export DATAW/TIMER actions for absolute DIM1K brightness; keep existing safety checks.
- Include release-candidate fixes for group-6 Stop Dim and event-loop-safe cover timer updates.

**Compatibility note:** Alternative hardware groups, untested EXU/SoftM behaviors, and new BHS installations have not been physically verified. Keep a Home Assistant backup before upgrading.

## v0.4.3rc2 — Cover timer safety and group Stop Dim fix

- Fix shutter completion timer callback running in a worker thread; register it as an event-loop callback to safely update Home Assistant state.
- Restore Stop Dim buttons for validated SDim groups beyond group 5 (including group 6).
- Allow REST Stop Dim for unambiguous MemberType 19 / SDim address 220 members, while restricting cyclic Start Dim to the previously validated group 5.
- Preserve unique IDs, scene and shutter mappings, dimmer brightness settings and existing feature behavior.

## v0.4.3rc1 — Release candidate for universal member discovery

- Carry forward all tested v0.4.3b1–b7 discovery, member role options, shutter pairing/identities, SDim address classification and export-validated DIM1K brightness controls.
- Fix non-group-5 export-validated DIM1K lights missing from entity creation; unvalidated, untested non-group-5 dimmers are not exposed for REST control.
- Report the correct integration version in diagnostics instead of a stale `0.4.0`.
- Remove unused legacy name-gating helpers and switch Stop Dim/Group Reset button discovery to validated SDim addresses; retain the group-5 restriction for cyclic dimming.
- Update README for release-candidate deployment, memberType mapping and validation precautions.
- Static and standalone regression tests included with release package (see `tests/`).

**Not yet physically validated:** other DIM1K groups, new EXU/SoftM wiring or brand-new installations. Publish as a prerelease until field-tested.

## v0.4.3b7 — Export-driven DIM1K brightness (beta)

- Discover DIM1K channels from `memberType=2` and module metadata without DIM_ naming.
- Match brightness commands using memberID, group/address metadata and the configured, authorized BHS mobile export.
- Require a validated DATAW/TIMER sequence (actions, functions, registers, flanks and byte bounds) but load TIMER MSB from the export instead of assuming 101.
- Remove group-5 limitation on absolute-brightness commands; cyclic dimming remains restricted to the existing group-5 implementation.
- Reject duplicate or ambiguous exported command mappings.
- Unexported channels (e.g., DIM_0_RESERVE) have no absolute-brightness slider; no raw bus commands are invented for them.
- Preserve member-based entity IDs, minimum brightness settings and persisted last-commanded levels.
- Other features unchanged from v0.4.3b6.

## v0.4.3b6 — Address-based SDim discovery (beta)

- Identify SDim group reset (219), stop dim (220), scene slots (221–228), and record scene (229) by `memberType=19`, version `SDim`, group and address rather than by display names.
- Support scene discovery in any BHS group with an unambiguous group-reset member; preserve scene member-based entity unique IDs.
- Never expose record-scene as an automatically writable entity.
- Refuse ambiguous duplicate SDim addresses; only unambiguous groups get scene control.
- Retain existing group-5 restriction for cyclic DIM1K commands and stop-dim.
- Based on v0.4.3b5; existing shutter identity, mapping, travel-time and member-role changes retained.

## 0.4.3b5 — Direction-independent shutter names (preview)

- Preserve a shutter’s displayed name when its Open/Close relay mapping is reversed.
- Identify `_OP` / `_NEER` suffixes on either member, regardless of assigned direction.
- Keep direction-independent fallback labels stable if no naming convention is used.
- Keep entity IDs, travel-time settings, and command logic unchanged.

## 0.4.3b4 — Stable shutter identity (preview)

- Preserve existing Home Assistant cover and travel-time number unique IDs when reversing Open/Close relays.
- Resolve a pair's identity from the existing entity registry, independent of current direction.
- Carry forward the previously configured travel time if its old orientation-specific key differs.
- Keep BHS member command validation and the working shutter movement logic unchanged.
- Upgrade note: after installing, verify one cover and its travel-time number before changing any live relay direction.

## 0.4.3b3 — Named shutter pairing

- Shutter mapping now selects a pair by both BHS member names and bus address.
- Separate direction step identifies opening relay by name; opposite relay becomes closing relay.
- Existing mapping is preselected and remains stored by immutable member IDs.
- Invalid or incomplete pairs are not made writable.

## v0.4.3b2 — Named member selection

- Member mapping now selects a member from a human-readable drop-down (BHS name, category, group and address).
- A separate role screen shows the member name and stores the assignment using the immutable memberID.
- No changes to entity discovery, controls or persisted mappings.

## 0.4.2 — EXU controls, configurable exports and cover timing

- Add `EXU_192` Manual/Automatic mode switches for known `BWM_*` members, with Set/Reset command and state support.
- Make dimmer export ID (default 2) and EXU export ID (default 7) configurable in integration options. EXU mode switching remains independent of exports.
- Add per-cover persistent **Travel time** configuration numbers. After `_OP` or `_NEER` stays Set continuously for the configured duration, infer Open or Closed respectively; interrupted movement becomes Unknown. This is estimated, not measured position.
- Fix BHS configuration options flow error caused by malformed `dict.get()` usage in the first beta.
- Preserve v0.4.1 dimmer brightness, minimum brightness and brightness memory, plus existing REST, events, and DataSnap support.

## v0.4.2b2 — Configurable exports and cover travel-time estimation

- Configure dimmer/EXU export IDs via integration options; replace hard-coded dimmer export ID 2.
- Per-cover persisted travel-time configuration numbers.
- Infer fully open/closed after direction relay remains Set for travel duration.
- Preserve v0.4.2b1 EXU modes, v0.4.1 brightness and memory, and earlier REST behavior.

## 0.4.2b1 — EXU_192 manual/automatic mode preview

- Discover tested outdoor EXU_192 members (group 1, addresses 101–104) as dedicated operating-mode switches in REST mode.
- On sends Set (manual mode); Off sends Reset (automatic mode), using `/api/members/command`.
- States reflect the last observed BHS Set/Reset telegram via the existing coordinator, including event updates and periodic snapshots.
- Unknown is retained until the BHS server knows the member state. These are not motion-activity sensors.
- Exclude EXU_RESERVE and unrelated EXU/SoftM members. No timer changes, export-specific endpoints or raw bus writes.
- Keep 0.4.1 brightness, scene, cover, legacy and diagnostic code otherwise unchanged.

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

## 0.4.3b1 (preview)
- Added memberType/module-version discovery and persisted member-ID role mappings.
- Removed `DIM_` naming requirement for supported group-5 DIM1K channels.
- Added options UI to configure relay, EXU and SoftM roles.
- Added options UI to confirm direction for unnamed type-20 shutter relay pairs.
- Preserved legacy classification and command restrictions for existing installations.
- Kept unrecognized relay commands blocked until explicit classification and
  EXU/SoftM commands opt-in only.
