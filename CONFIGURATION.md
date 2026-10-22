# BHS v0.4.2b2 — configuration and covers preview

Changes based on v0.4.2b1 EXU preview:

- The REST dimmer export ID is configurable in BHS integration options (default 2).
  A valid, allowed export containing matching DATAW/TIMER actions remains required for brightness sliders.
- The EXU export ID is configurable in the same options (default 7). Existing EXU
  Manual/Automatic switches still use `/api/members/command` and do **not**
  require any export; the setting is reserved for optional export-based EXU calls.
- Each cover has a **Travel time** configuration number entity (1–300 seconds,
  default 30 seconds). These settings persist across restarts.
- A cover reports `opening`/`closing` while the appropriate relay is Set. If the
  same direction remains Set for at least the configured travel time, the cover
  reports `open` or `closed`. If the relay resets earlier, it retains an unknown
  position. After a completed movement, the inferred endpoint is retained when
  the relay resets. Stop and reversing direction clear the previous endpoint.
- Cover positions are estimates **not measured feedback**; a motor stall, an
  interrupted run that is not observed in the event stream, or any operation
  outside BHS can make the estimate incorrect. Endpoint estimates are not
  persisted across HA restarts.

## How to configure

Go to Settings > Devices & Services > BHS > Configure (Options), set the
**Dimmer export ID** and **EXU export ID**, and save. Existing integration
settings remain. Find each cover's **Travel time** number entity in the BHS
Controller device, possibly under the configuration section, and set the
complete opening/closing duration in seconds.

**Caution:** A single travel-time setting is shared by opening and closing for
that cover. Keep travel times conservative and physically test the resulting
state for a full opening and closing cycle. No actual position slider is offered.

The existing EXU_192 Manual/Automatic switches, brightness memory, BHS polling,
and other commands remain unchanged. No physical devices are operated by
installing the update.
