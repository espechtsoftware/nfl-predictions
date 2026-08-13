# PFR secondary control-parity operational repair

Status: frozen 2026-08-13 after failed execution
`tabpfn-pfr-secondary-final-served-v1-rgvmc`, before any structured forecast
report or treatment metric existed. The traceback showed only
`Route control post-shaper mean differs`; the job aborted in 2022 control
alignment before any treatment arm was replayed or scored.

## Defect

The outcome-blind parity addendum accidentally required the active-only
control replay to equal the earlier historical source panel
`20260811-pitclean-e80-k1-role12union-a12ab31`. That panel predates adoption of
the active-only cache and is not the active-label projection lineage. The
accepted active-label final-served gate deliberately set
`control_parity_required=false` for both arms; its recorded differences from
that source panel reach multiple points and therefore prove the new assertion
was structurally impossible rather than newly diagnostic.

## Narrow repair

Remove only this invalid panel-mean assertion by restoring
`require_control_parity=false`, matching the accepted active-label, SCHED,
team-QB and SIS cache evaluators. Preserve the valid stronger same-cache
identity already passed mechanically: the new control cache is bit-for-bit
equal to accepted `tabpfn_active_label_treatment_v2`, with the same 52,307
keys. Preserve all arms, feature drops, rows, seasons, simulations, fitted K,
blend, position-factor procedure, Brier gate and branch choice unchanged.

Record the failed execution and its error log. Build a new immutable
full-test image and launch one repaired execution. Do not reuse the failed
image and do not read partial output.
