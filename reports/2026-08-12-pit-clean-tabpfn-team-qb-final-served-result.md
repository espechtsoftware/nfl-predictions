# PIT-clean team-passing final-served result

The frozen amended team-passing feature bundle is **not selected**. Cloud Run
execution `tabpfn-team-qb-final-served-v1-q9tsq` completed cleanly from image
digest `sha256:df3de60e08f6e88d8f3d4dba551f01e9fc37d7c7de7de2ba41496a43396d5bfd`
and source `83192ca`.

All point-in-time, key, cache-coverage, market-blend and mean-preservation
invariants passed. The frozen primary aggregate active RB/WR/TE 30-point Brier
score nevertheless moved from `0.0140065605` for the inherited control to
`0.0140127100` for treatment, a worsening of `0.0000061495`. The paired
slate-cluster 95% interval for that difference was
`[-0.0000060903, 0.0000183893]`. Treatment also slightly worsened aggregate
CRPS and the q90/q95/q99 pinball losses, although point MAE improved from
`3.63282` to `3.61681`.

Per the preregistered branch, no exact-80 lineup or score comparison was
licensed. The terminal fallback retains active-only labels, shared-33
features, cache `tabpfn_active_label_treatment_v2`, fitted
`K=28.154043586960896`, and historical/evaluation panel
`20260811-pitclean-e80-k1-role12union-a12ab31`. The immutable machine report
and selection are under
`reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-final-served-v1-pit-clean/`
and
`reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-exact80-v1-pit-clean/`.

This closes the registered marginal-feature queue. The next action is the
already-preregistered G0 final-served teammate-dependence premise diagnostic;
it is score-free and is mechanically pinned to this terminal selection.
