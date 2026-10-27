# BHS — Home Assistant custom integration

A local Home Assistant custom integration for the B-Logicx Home Server (BHS), supporting the new REST API and legacy DataSnap.

## Supported functionality

- **Discovery and states:** member discovery and state mapping by stable `memberID`. In REST mode, `/api/members/getChanges` is polled every 1–2 seconds, with a full state snapshot on startup, on `fresh: true`, after polling failure, and approximately every 60 seconds.
- **Lights:** memberType 2 DIM1K channels and RLM_4 relays explicitly classified as lights (legacy `VER_*` mapping retained). Brightness sliders require a validated DATAW/TIMER export.
- **Switches:** memberType 1 RLM_4 outputs; new relays default to generic switches until classified. REST writes require explicit opt-in or a legacy vetted mapping. Legacy `SK_*` mappings are preserved.
- **Covers:** memberType 20 paired shutter/screen relays, with named direction-mapping options; reset opposite relay before activating a direction. Per-cover configurable travel time estimates completed opening/closing from continuous `_OP`/`_NEER` relay activation. An interrupted travel cycle leaves the endpoint unknown; the controller does not report actual physical position.
- **DIM1K dimming:** group-5 Start Dim and Stop Dim actions; stop dimming explicitly. No automatic timeout is guaranteed.
- **Scenes:** SDim memberType 19 scene slots (221–228), grouped with address 219 reset and 220 Stop Dim; name-independent classification. Supported scene on/off with group-reset semantics. Off may reset other scenes in the same group. Scene recording is excluded.
- **EXU motion detectors (REST):** export-discovered EXU_192 (memberType 17) Manual/Automatic switches with live configuration feedback; writable motion hold-time (0–255) and seconds/minutes controls. Detectors with incomplete configuration or `manual: null` are not exposed. These are *configuration/operating-mode controls*, not live PIR occupancy sensors.
- **SoftM:** previously vetted member controls and explicitly opted-in SoftM switches; unknown SoftM commands stay blocked. Legacy DataSnap behavior is preserved.
- **Diagnostics:** connection status, timestamps, event and synchronization counts, error counts, and privacy-conscious diagnostics export.

## Device registration (v0.4.5 beta)

New REST installations can choose **Register a new device** during setup.
Home Assistant generates a new UUID v4 and RSA-2048 key pair, then submits the
device name, `platf: android`, and PEM public key using
`POST /api/device/register`. If BHS responds `Approved`, setup validates
the connection and stores the registered UUID and private key in the Home
Assistant config entry. If BHS responds `Pending`, an administrator must
approve the device and assign required mobile exports before setup continues.

The **Use registered UUID** path remains available for existing registered
clients; updates to existing installations do not automatically reregister.
The RSA key is retained locally but **encrypted BHS REST traffic remains
unsupported**. Store Home Assistant backups securely because they may contain
the private key. Do not share the UUID or private key.

**Beta limitation:** Pending-registration credentials are held in the active
setup flow and are not durable until approval completes. Keep the wizard open
while awaiting approval; do not restart Home Assistant during registration.
A registration timeout may have succeeded server-side: check the device list
before attempting to register a different UUID.

## Requirements and configuration

- Home Assistant **2026.8.0 or newer** (as specified in `hacs.json`; this is a package minimum, not a full compatibility matrix).
- For REST: BHS REST endpoint (tested on port `10014`), an **already registered and approved UUID v4**, and BHS `isSecure: false`. Registration is not performed by this integration. Keep the associated private key and UUID safe.
- For existing installations: install over the existing `custom_components/bhs` directory and **do not delete/re-add** the configured BHS entry. Use its Configure/Options flow to select `rest`, port `10014` and the registered UUID.
- Legacy `datasnap` remains selectable.

### DIM1K brightness controls

- For compatible DIM1K members discovered in the **configured BHS dimmer export**, a Home Assistant brightness slider sends absolute levels via two ordered `/api/bus/send` actions (DATAW followed by TIMER). Other dimmers keep existing on/off behavior.
- Each brightness-capable dimmer has a **Minimum brightness** configuration entity (default **5%**, adjustable 1–100%). Nonzero requests below this threshold are clamped; Off still works normally.
- The last successfully commanded nonzero level is remembered separately for each dimmer, persists across restarts, and is restored on a plain On request.
- Brightness reflects the **last command sent by Home Assistant**, not a measured level; wall-switch dimming and scenes may make the reported level inaccurate.
- The dimmer export ID is configurable under BHS Configure/Options (default 2). It must reference an export containing matching DATAW/TIMER actions. Do not issue guessed raw bus commands.

### EXU_192 motion detector control (v0.4.4, REST only)

- Configure a BHS **EXU export ID** in **BHS → Configure/Options** (default **7**). The export must actually contain the motion detector modules, and your registered device must have access to that export.
- The integration discovers supported EXU motion detectors using `POST /api/members/getMotionDetectorsByExport`. Discovery uses the stable `memberID`, not names such as `BWM_*`. Unsupported/incomplete entries and entries with `manual: null` (such as an unconfigured reserve module) are skipped.
- Existing **Manual mode** switches retain their Home Assistant unique IDs. **On = Manual** and **Off = Automatic**. The switch reads the API-reported `manual` setting; writes use `POST /api/members/setMotionDetector`, rather than generic Set/Reset.
- Two additional configuration entities per exported EXU:
  - **Motion timer**: numeric value **0–255**.
  - **Timer in minutes**: switch (**Off = seconds**, **On = minutes**).
- These entities use `POST /api/members/setMotionDetectorTimer`. Only the changed field is sent: changing `timer` preserves `inMinutes`, and changing `inMinutes` preserves `timer`.
- The integration refreshes exported motion detector settings approximately **every 15 seconds**, independently of the `getChanges` event queue; changes made elsewhere can therefore be reflected in Home Assistant.
- `followInput` is exposed as a **read-only attribute**. When enabled, the timer can still be saved but **does not affect** that detector's behavior.
- **Timer writes program module configuration/EEPROM**. Avoid frequent automated writes. HTTP 500 or 503 (including `programming the module failed`) is treated as a **failed operation**, even though BHS may already have saved the setting. Timer entities expose `bhs_module_programming_failed`; verify/reprogram in BLConfig if necessary.
- These settings **do not provide a live motion-detected (PIR occupancy) binary sensor**. A Manual mode switch is not a motion sensor.

### Cover travel time

- Each confirmed memberType 20 cover pair has a **Travel time** configuration number (default 30 seconds). A relay staying Set for the full duration results in an estimated Open/Closed state; stopping early gives Unknown. No actual position measurement or partial-position estimation is available.

### Manual upgrade

1. Make a Home Assistant backup and back up `/config/custom_components/bhs`.
2. Upload the ZIP into `/config` and extract it from that directory:

```sh
cd /config
cp -a custom_components/bhs custom_components/bhs_backup_pre_v044
# If downloading a GitHub source ZIP, first extract its top-level folder:
unzip -o bhs-homeassistant-0.4.4.zip
cp -a bhs-homeassistant-0.4.4/custom_components/bhs/. /config/custom_components/bhs/
ha core restart
```

3. Check Settings → Devices & Services → BHS; confirm your existing entities, event updates, commands and diagnostic sensors.

### HACS

Repository layout includes `custom_components/bhs`, `hacs.json`, this README and a changelog. To distribute updates through HACS, place these files at the root of your GitHub custom-integration repository, commit them, and create a GitHub release tagged `v0.4.4` from `main`. For a stable release, leave **Set as a pre-release** unchecked. A locally created ZIP alone does **not** publish a HACS update. Public HACS catalog submission requires additional validation; adding the repository as a custom HACS repository does not require public catalog acceptance.

## Known limitations

- Encrypted BHS REST mode (`isSecure: true`) is **not supported**.
- REST commands remain deliberately restricted to physically tested categories. Group-6 continuous dimming, arbitrary SoftM control, scene recording and additional sensors/thermostats are not included.
- Diagnostic entities may be unavailable if the integration cannot initialize during setup; recovery after a network failure without reload has not been independently validated in a controlled outage test.
- A registered UUID should have only **one `getChanges` consumer**. Do not poll it simultaneously from a separate script.
- Integration counters reset on reload, and event updates may lag up to the configured polling interval (2 seconds by default).
- EXU export configuration is refreshed periodically (about 15 seconds), rather than via instantaneous motion events. Module timer programming failures may leave BHS stored settings differing from module settings.

For changes by release, see [CHANGELOG.md](CHANGELOG.md).

## v0.4.4 upgrade validation

1. Create a full Home Assistant backup; copy `/config/custom_components/bhs` before replacing it.
2. Install over the existing integration **without deleting/re-adding the BHS config entry**.
3. Confirm lights, sockets, exported dimmers, shutter entity IDs, travel-time numbers, EXU mode switches, EXU timer values/units, and SDim scenes.
4. Test one representative command per device category and check BHS diagnostic sensors.
5. On a fresh installation, assign ambiguous relay roles and shutter opening direction explicitly in **BHS → Configure** before commanding hardware.

**Safety boundary:** An unknown RLM relay can appear as a generic switch but will not receive REST Set/Reset writes until mapped. EXU writes require membership in the selected export and valid motion-detector configuration; unknown SoftM modules require explicit opt-in. Record Scene (SDim address 229) remains blocked. Group-5-only cyclic dimming has not been generalized.
