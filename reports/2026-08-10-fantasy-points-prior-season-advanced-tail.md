# Fantasy Points prior-season Advanced player-tail diagnostic

Status: preregistered before any Advanced Passing/Receiving/Rushing value was
joined to a realized target-season outcome. File schemas, hashes, identities
and outcome-blind coverage only have been inspected.

## Question

Do previous-season process traits from Fantasy Points Advanced Passing,
Receiving and Rushing improve held-out 30-point player-tail forecasts beyond
the corrected pre-lock projection and existing point-in-time role/context
features?

This diagnostic targets returning-player priors, especially Week 1 and early
season. It does not treat a final season aggregate as if it were available
during that season. It is separate from the passed true Route Share mechanism,
which uses strictly lagged weekly route opportunity.

## Immutable sources

Use only the files and exact hashes recorded under Advanced Passing,
Receiving and Rushing in
`reports/2026-08-10-fantasy-points-data-intake.md`. Licensed source rows remain
ignored and must not be committed. Passing and Rushing require their two-row
grouped headers; reject any ungrouped file or duplicate group-qualified key.

Resolve player identities without outcomes using normalized name, position
and team against the corrected K1 snapshot universe. Map FB to RB. Preserve
unresolved and ambiguous rows; never pick a duplicate by input order. For the
known split 2022 Brock Wright receiving rows, sum additive counts and recompute
rates from their documented numerators/denominators or mark a rate missing;
never add rates or choose one half.

## Non-negotiable point-in-time join

For every target in season N, attach values from season N-1 only. Season N's
Advanced file is forbidden for every week of season N, including Week 18.
Values older than N-1 are not carried forward. Persist source season and
assert `source_season == target_season - 1` for every non-null feature.

The target seasons are 2023--2025. This creates the frozen walk-forward folds:

- held-out 2024 trains only on target-season 2023 rows, whose source is 2022;
- held-out 2025 trains on target-season 2023--2024 rows, whose sources are
  2022--2023.

No 2025 Advanced value enters either held-out fold. It is retained only as a
future 2026 prior after live identity/roster resolution.

Outcome-blind prior-season coverage of corrected candidate-snapshot
appearances is sufficient for a measured diagnostic:

| Target | QB Passing | RB Receiving+Rushing | WR Receiving | TE Receiving |
|---:|---:|---:|---:|---:|
| 2023 | 66.59% | 65.98% | 61.52% | 62.22% |
| 2024 | 66.87% | 60.63% | 63.04% | 61.31% |
| 2025 | 64.04% | 61.08% | 63.62% | 60.27% |

## Frozen feature blocks

Fit three independent position-group models so irrelevant missing columns are
not median-imputed across positions.

QB treatment adds only:

- `Passing Advanced::CPOE`;
- `Passing Advanced::aDOT`;
- `Passing Advanced::Deep Throw %`;
- `Passing Advanced::TWT %`;
- `Passing Advanced::PRESS SK %`; and
- prior scramble rate, derived as `Scrambles::SCRM / Passing::DB`.

WR/TE treatment adds only:

- `TPRR`;
- `aDOT`;
- `AY Share`;
- `YPRR`;
- `1READ %`; and
- `XFP/RR`.

RB treatment adds the same six receiving fields plus:

- `Advanced::i5 %`;
- `Advanced::MTF/ATT`;
- `Advanced::YACO/ATT`; and
- `Advanced::STUFF %`.

Percentage fields are converted consistently to fractions. Non-finite ratios
are missing, not zero. No field subset, transform, interaction, alignment
slice, zone/gap slice, winsorization or regularization sweep may follow.

## Frozen comparison

Evaluation uses corrected accepted K1 snapshot rows for QB/RB/WR/TE with a
non-null authoritative actual, non-null pre-lock `mean_projection`, and the
complete applicable prior-season source family (Passing for QB, Receiving for
WR/TE, and both Receiving and Rushing for RB). Control and treatment use the
same rows.

Within each position group and fold:

- regression target is `actual - mean_projection`, modeled by
  `Ridge(alpha=10.0)` and reported as residual MAE;
- classification targets are `actual >= 20` and `actual >= 30`, modeled by
  `LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)` and reported as
  Brier loss; and
- numeric inputs use training-fold median imputation and standardization.

The frozen control inputs are `mean_projection`, salary,
`target_share_last`, `target_share_jump`, `snap_share_last`,
`snap_share_jump`, `team_vacated_target_share`, `depth_rank`, and
`games_played_prior`. Missing control fields remain missing for imputation.
Report both held-out folds, all three position groups, combined metrics,
coverage, missingness, event counts and 30-point calibration deciles.

## Frozen gate

The mechanism passes only if:

1. prior-season coverage is at least 60% for QB, RB, WR and TE separately in
   both held-out seasons;
2. combined held-out 30-point Brier is lower for treatment;
3. at least two of QB, RB and WR/TE have lower combined 30-point Brier;
4. no position group's combined 30-point Brier is more than 1% worse; and
5. neither held-out season's combined 30-point Brier is more than 1% worse.

20-point Brier and residual MAE are mandatory diagnostics, not vetoes. A pass
licenses one separately preregistered candidate-union experiment after the
corrected generator and already-licensed Route union resolve their incumbent.
It does not directly change production features. A valid failure closes this
exact Advanced prior mechanism for pre-Week-1 adoption; do not retry fields,
positions, folds, model strength or missingness rules on these outcomes.

## Implementation status

Commit `b014748` implements the hash-locked importer, exact N-1 join, three
position-group comparisons, frozen gate and mandatory event-count,
missingness and calibration reporting. Audit-only import completed without
reading outcomes: 3,772 source rows became 3,771 normalized player-family-
season rows, including 3,705 resolved rows, 64 unresolved source rows, two
ambiguous source rows and the one known coalesced duplicate group. Twelve
focused Advanced/Route tests pass; compilation, shell parsing and whitespace
checks are clean. No Advanced table write or outcome diagnostic had run at
this milestone.
