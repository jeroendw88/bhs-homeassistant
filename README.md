# BHS — Home Assistant custom integration

**Release: 0.4.0**  
A local Home Assistant custom integration for the B-Logicx Home Server (BHS), supporting the new REST API and legacy DataSnap.

## Supported functionality

- **Discovery and states:** member discovery and state mapping by stable `memberID`. In REST mode, `/api/members/getChanges` is polled every 1–2 seconds, with a full state snapshot on startup, on `fresh: true`, after polling failure, and approximately every 60 seconds.
- **Lights:** `VER_*` RLM_4 lights and `DIM_*` DIM1K on/off controls. Numeric brightness is not supported.
- **Switches:** `SK_*` sockets and other mapped RLM_4 outputs. REST writes are limited to the tested `SK_*` class, not every discovered relay.
- **Covers:** paired `_OP` and `_NEER` shutter/screen relays; reset opposite relay before activating a direction. The controller does not report physical cover position.
- **DIM1K dimming:** group-5 Start Dim and Stop Dim actions; stop dimming explicitly. No automatic timeout is guaranteed.
- **Scenes:** supported SDim scene on/off with group-reset semantics. Off may reset other scenes in the same group. Scene recording is excluded.
- **SoftM:** selected `BWM_*_bypass` and `BWM_*_down` commands in REST mode; other SoftM commands stay blocked. Legacy DataSnap behavior is preserved.
- **Diagnostics:** connection status, timestamps, event and synchronization counts, error counts, and privacy-conscious diagnostics export.

## Requirements and configuration

- Home Assistant **2026.8.0 or newer** (as specified in `hacs.json`; this is a package minimum, not a full compatibility matrix).
- For REST: BHS REST endpoint (tested on port `10014`), an **already registered and approved UUID v4**, and BHS `isSecure: false`. Registration is not performed by this integration. Keep the associated private key and UUID safe.
- For existing installations: install over the existing `custom_components/bhs` directory and **do not delete/re-add** the configured BHS entry. Use its Configure/Options flow to select `rest`, port `10014` and the registered UUID.
- Legacy `datasnap` remains selectable.

### Manual upgrade

1. Make a Home Assistant backup and back up `/config/custom_components/bhs`.
2. Upload the ZIP into `/config` and extract it from that directory:

```sh
cd /config
cp -a custom_components/bhs custom_components/bhs_backup_pre_040
unzip -o bhs-hacs-v0.4.0.zip 'custom_components/*' -d /config/
ha core restart
```

3. Check Settings → Devices & Services → BHS; confirm your existing entities, event updates, commands and diagnostic sensors.

### HACS

Repository layout includes `custom_components/bhs`, `hacs.json`, this README and a changelog. To distribute updates through HACS, place these files at the root of your GitHub custom-integration repository, commit them, and create a GitHub release/tag `v0.4.0`. A locally created ZIP alone does **not** publish a HACS update. Public HACS catalog submission requires additional validation; adding the repository as a custom HACS repository does not require public catalog acceptance.

## Known limitations

- Encrypted BHS REST mode (`isSecure: true`) is **not supported**.
- REST commands remain deliberately restricted to physically tested categories. Group-6 continuous dimming, arbitrary SoftM control, scene recording and additional sensors/thermostats are not included.
- Diagnostic entities may be unavailable if the integration cannot initialize during setup; recovery after a network failure without reload has not been independently validated in a controlled outage test.
- A registered UUID should have only **one `getChanges` consumer**. Do not poll it simultaneously from a separate script.
- Integration counters reset on reload, and event updates may lag up to the configured 1–2-second REST polling interval.

For changes by release, see [CHANGELOG.md](CHANGELOG.md).
