# PIT-clean fitted-usage exact-80 retry

Frozen 2026-08-12 before the repaired usage-concentration report or any
finite-K PIT-clean lineup outcome was read. This is the lineup stage licensed
only by a pass of the unchanged score-free estimator and gate in
`reports/2026-08-11-data-fitted-dirichlet-usage.md`.

## Inputs and branches

- Use generation image digest `ad50fe19...`, application code `a12ab31`, and
  canonical cache `tabpfn_projections_pit_v2`.
- Derive the full historical source, K1/K3 law, direct-role selection and
  served-position law mechanically from the terminal repaired Tier-1 and
  position-selection records. No old panel ID, old position factor or old
  fitted K may be reused.
- If the repaired likelihood gate fails, no finite-K lineup is licensed and
  the selected allocation is the production multinomial (`K -> infinity`).
- If the likelihood gate passes, use its sole unrounded global fitted K. The
  fixed exact-80 IDs are
  `20260812-pitclean-e80-selected-usage-control-v2` and
  `20260812-pitclean-e80-selected-usage-fitted-v2`.
- If the licensed exact-80 treatment loses or ties under the rule below, the
  selected allocation is also the production multinomial. If it wins, the
  selected allocation is the sole fitted finite K.

This branching also freezes the later G3/graph target before the K result:
use the terminal selected usage law—finite K only after both gates pass,
otherwise multinomial. There is no undefined shrinkage target and no
post-result choice.

## Same-image exact-80 comparison

Both books run only untouched 2023--2025 slates with the selected base/role
candidate law, selected position law, canonical-v2 cache, 80 entries, boom 40
and frozen seeds. The control uses production conditional multinomial usage.
The treatment's sole lever change is
`GAME_SIM_USAGE=dirichlet, DIRICHLET_K=<unrounded repaired fit>`.

The comparator must prove:

- the chosen evaluation source exactly reproduces under the identity control;
- complete player keys, invariant point-in-time inputs, seeds, actuals and
  pre-simulation means;
- only the seven registered distribution-derived player fields may change
  after fitted-K allocation; and
- the fitted allocation changes candidate membership and still returns
  exactly 80 selected lineups per slate.

The 2019/2021/2022 selected-source scores remain identical history in both
books. The decision order is `240,230,220,210,200,194,187`; the first nonzero
weekly-maximum count delta wins. If all seven counts tie, mean weekly maximum
wins; an exact tie retains multinomial. Season signs and average lineup scores
are diagnostics, not vetoes.

The terminal selection record must contain the full historical source,
evaluation source, base/role/position laws, likelihood-report hash,
comparison hash, and either `allocation=multinomial, K=infinity` or
`allocation=dirichlet, K=<unrounded fit>`.
