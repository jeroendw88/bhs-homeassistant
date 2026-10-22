# v0.4.3b7 — DIM1K validation

This is a preview. The user-validated export 2 has nine DATAW/TIMER buttons, targeting member addresses 1–9 in group 5. Address 10 (`DIM_0_RESERVE`) is not in the export and is not granted absolute-brightness control.

The integration discovers all DIM1K members (`memberType=2`) independent of naming. Absolute brightness is enabled only if the configured export contains exactly one recognized DATAW+TIMER pair targeting that memberID, with a TIMER LSB matching the member address. The TIMER MSB is taken verbatim from the exported action, and the DATAW LSB is replaced by the requested percentage.

Group 5 remains the only group permitted to use the separately implemented cyclic dimming control. The newly enabled Set/Reset operations on other groups depend on a validated brightness export mapping.

**Testing:** verify a known channel at 20% and 70%, then check OFF and ON with persisted brightness memory. Confirm the unexported reserve channel has no brightness slider. Check that configured minimum brightness still clamps low nonzero values.

Safety: A matching export action is required, but the behavior of alternative TIMER MSB values outside the tested installation has not yet been physically verified. Test with a noncritical load and confirm the export is correct.
