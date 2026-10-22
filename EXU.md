# BHS v0.4.2b1 — EXU manual/automatic switches

Install the `custom_components/bhs` folder over the existing v0.4.1 code and restart Home Assistant. Back up your working installation first.

Four new **REST-only** switches should be created under the BHS Controller:

- BWM_parking Manual mode
- BWM_terras Manual mode
- BWM_voordeur Manual mode
- BWM_garage Manual mode

ON = Set = manual mode; OFF = Reset = automatic mode. The state reflects the last observed bus command, **not independently measured hardware mode**, and is initially unknown if the server has not yet recorded a Set/Reset. Physical motion events are not represented by these switches.

Check the BWM_parking switch first, which was previously tested using both commands. Changing this switch may alter parking lighting behavior. Return it to the intended automatic setting after testing. The reserve EXU is excluded. Timer configuration and getMotionDetectorsByExport remain unsupported.

The code is syntax-checked but has not been run against a live Home Assistant instance.
