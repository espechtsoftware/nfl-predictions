# PFR secondary production-feature ablation protocol

Status: frozen 2026-08-13 after adjacent Fantasy Points coverage results were
known, but before any treatment cache, forecast metric or lineup score from
this ablation exists. This is an adaptive provenance disclosure, not an
independent discovery claim.

## Question

Do four point-in-time-safe but never isolated production inputs earn their
places in the terminal active-only stack?

The inputs are not coverage-shell variables. Three measure recent opponent
secondary quality from PFR nearest-defender charting:

- `cb_ypt_allowed_l6`;
- `cb_comp_rate_allowed_l6`; and
- `db_ypt_allowed_l6`.

The fourth, `top_cb_out`, is a distinct current-week availability flag for the
opponent's prior-snap-leading cornerback.

## Frozen arms

Use the unchanged terminal active-only training law, training panel, target
keys, model hyperparameters, context cap, seed, fitted
`K=28.154043586960896`, 45/55 final-served blend and position calibration
method. Generate the following same-image, write-once TabPFN caches before
reading any treatment output:

1. `CONTROL`: drop nothing and reproduce accepted cache
   `tabpfn_active_label_treatment_v2` exactly;
2. `DROP_RATES`: drop the three PFR rate fields together;
3. `DROP_TOP_CB`: drop only `top_cb_out`; and
4. `DROP_ALL`: drop all four fields.

The combined arm is declared now rather than being constructed conditionally
after the two component results. No single-rate, position-specific, window,
imputation, interaction or replacement arm is permitted.

For each treatment, `DROP_FEATURES` must apply consistently to every affected
mean/component model and to the TabPFN feature contract. The later lineup stage
must apply the same drop to both the baseline K=1 and role12 generation paths;
removing a column only from TabPFN or only from one candidate arm is invalid.

## Mechanical gate

Before any outcome metric:

- all four caches use one immutable source table identity, code/image,
  active-only context, target key universe, folds, seed and hyperparameters;
- control reproduces every accepted-cache mean and quantile exactly;
- treatment feature contracts equal control minus exactly their declared
  fields;
- each cache has 52,307 unique 2022--2025 target keys with finite ordered
  quantiles; and
- each treatment changes at least one prediction while preserving keys.

A failure is operational and permits only a mechanism-preserving repair before
outcomes, never a feature or gate change.

## Frozen score-free gate and branch choice

Use 2022 solely to fit each arm's own walk-forward position spread factors and
evaluate final-served active QB/RB/WR/TE rows on held-out 2023--2025. Apply the
same terminal market blend and usage law to all arms. Report by fold, position
and aggregate:

- 20- and 30-point Brier/reliability;
- MAE, empirical CRPS and q90/q95/q99 pinball/calibration;
- support, event counts and mean-preservation drift; and
- control-versus-treatment paired slate-cluster intervals.

An arm is score-free eligible only if its aggregate active-player 30-point
Brier is strictly lower than control and all terminal PIT, coverage,
mean-preservation and identity invariants pass. Other metrics and season signs
are mandatory diagnostics, not vetoes, consistent with the operator's
aggregate extreme-tail objective.

If no treatment is eligible, retain all four fields and close this ablation.
If multiple treatments are eligible, preselect exactly one for the lineup
stage by lowest unrounded aggregate 30-point Brier; an exact numeric tie breaks
in fixed order `DROP_RATES`, `DROP_TOP_CB`, `DROP_ALL`. Report the three-arm
multiplicity and do not promote from the score-free result alone.

## Conditional exact-80 consequence

Only the preselected eligible branch may receive one separately checksummed
same-code exact-80 control/treatment regeneration under adopted policy
`classic-k1-role12-boom40-poscal-v3`. Both books must use the same seeds,
slates, salaries, legal rules, fitted K, role quota, candidate budgets, world
counts, 194 coverage selector and exactly 80 final lineups; only the declared
feature removal and its downstream learned predictions may differ.

The historical decision uses the operator's terminal lexicographic weekly-max
grid: treatment-minus-control week counts at
`240,230,220,210,200,194,187`, stopping at the first nonzero difference. A
positive first difference adopts the drop; a negative first difference rejects
it; only a complete count tie consults unrounded mean weekly maximum. Per-season
signs, top-3/top-5/top-10 entry scores and candidate-pool oracles are mandatory
diagnostics rather than vetoes. Mechanism/key/legality/80-entry failure rejects
the comparison. No branch, selector or threshold may change after scores.

## Kill-list consequence

The result updates only the PFR secondary-quality/availability rows in
`reports/2026-08-13-coverage-grain-bind-and-kill-list.md`. It cannot reopen a
Fantasy Points shell arm or close named WR/CB assignment data. If the selected
drop wins, production removal still requires coordinated registry/cache
retraining, UI/fallback identity updates, Week-1 rehearsal and rollback
verification; editing `NUMERIC_FEATURES` alone is forbidden.
