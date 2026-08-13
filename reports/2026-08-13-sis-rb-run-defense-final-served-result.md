# SIS RB opponent run-defense final-served result

Frozen disposition: **fails the score-free gate; no lineup score was read.**

Cloud Run execution `tabpfn-sis-rb-rdef-final-served-v1-lmb74` completed
successfully from immutable audit image
`sha256:e86c6f963bbceca71d8f6cbd15f28c25651b1be75c4947494b604df3dcdee0e0`.
The complete machine report is under
`reports/tabpfn-sis-rb-rdef-runs/20260813-tabpfn-sis-rb-rdef-final-served-v1/`.

## Registered decision

On 3,961 active-RB rows across 54 evaluation slates, treatment Brier-30 was
`0.0188536595` versus control `0.0188522320`, a treatment-minus-control change
of `+0.0000014275`. Lower is better, so the frozen strict-improvement condition
did not pass. Both arms preserved row means within the registered `1e-10`
tolerance; maximum absolute mean drift was approximately `7.11e-15`.

The paired slate-cluster 95% interval for the Brier-30 delta was
`[-0.0000234100, +0.0000262650]`, spanning zero. The fold deltas were favorable
in 2023 (`-0.0000369259`) and unfavorable in 2024 (`+0.0000226338`) and 2025
(`+0.0000189788`).

## Diagnostics

The treatment slightly improved point MAE, `3.8366509 -> 3.8268668`, but
worsened the other aggregate distribution and tail diagnostics:

- CRPS: `2.7430215 -> 2.7457060`
- Brier-20: `0.06218636 -> 0.06219765`
- q90 pinball: `1.1614819 -> 1.1648056`
- q95 pinball: `0.7480473 -> 0.7496077`
- q99 pinball: `0.2307905 -> 0.2315444`

## Interpretation and scope

Lagged opponent SIS Run Defense Points Saved/play is not inert and modestly
improves RB point accuracy, but it does not improve the registered extreme-tail
event or the broader distributional diagnostics. The exact one-column arm is
closed historically. Do not run the conditionally frozen exact-80 comparison,
inspect lineup outcomes for this arm, or retune its window/support/feature after
this result.

This does not close SIS player-level alignment or competitive-allocation work.
That mechanism targets joint receiver outcome structure rather than a marginal
RB adjustment and remains a distinct future path once its bounded acquisition
workflow can be completed safely.
