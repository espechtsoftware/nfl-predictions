# Fantasy Points prior-season receiver coverage-fit diagnostic

Status: preregistered before any Man-vs.-Zone, receiver-separation, or
Coverage Matrix value was joined to a realized target-season outcome. File
schemas, hashes, identities, numeric ranges, and point-in-time availability
only have been inspected.

## Question

Does a receiver's prior-season performance against coverage types interact
with the target opponent's prior-season coverage deployment strongly enough
to improve held-out forecasts of 30-point DraftKings performances?

This is a matchup-fit hypothesis, not a retry of the failed broad Advanced
prior. The treatment varies by the target week's opponent and uses only
coverage-conditional receiver metrics. Alignment and individual-route grids
are excluded to avoid an outcome-driven field search.

## Immutable sources

Use corrected accepted K1 player snapshots from panel
`20260810-lockfix-e80-k1-8677d21` and only the following untouched licensed
exports. Originals remain under ignored `fantasy-points/` and must never be
committed or renamed.

| Family | 2022 SHA-256 | 2023 SHA-256 | 2024 SHA-256 |
|---|---|---|---|
| Receiving Man vs. Zone | `8033f7b539335a1d4bf4590ac7bcb0994c19eaf66b69a749803dbbf4f686e26d` | `aef16ffb479911bbdfeb072dba8edf5fa4fc3ba6ec8aad8caf029009e8e850f5` | `53e22d570a89c0e5578928cf7ca3634d94e6378fd3a896f67500e86361c0585c` |
| Receiving Separation by Coverage | `6eaf9e0d63794f39679f048c24f409b79c0b798611708cdc71fadfe84328ea1c` | `11538dfee6662572ab5502993a36fcb45e15a8d15f6ea7e288cd1082125c0787` | `2d97db23f9452118c4b16da70e7eb024c161625f84778d701d4f84b6fd033db0` |
| Defense Coverage Matrix | `45ff5738d28c19b0dd098f07de438d335a1be229c32066fc19eb90ad58b740bf` | `52af5f92251eec85b34b875a24bccaa1e4d1b44196bf68b2e4e14ff65e35a394` | `7270273e2e3ee400865c4c9c69b96d0b7eba2f0f005526942b5324a8fbe9606a` |

The 2025 files are retained for a future 2026 prior but cannot enter either
held-out fold. Exact 2025 hashes remain in the intake report. Offense Coverage
Matrix, Separation by Alignment, Route Breaks, and individual Routes are not
part of this diagnostic.

## Non-negotiable point-in-time construction

For a target in season N, attach receiver and opponent-defense values from
season N-1 only. The target's opponent comes from the corrected pre-lock
snapshot. Every populated treatment row must satisfy
`receiver_source_season == defense_source_season == target_season - 1`.

- Held-out 2024 trains on target-season 2023 rows, using 2022 source data.
- Held-out 2025 trains on target-season 2023--2024 rows, using 2022--2023
  source data.
- No 2024 source value may enter the held-out 2024 fold, and no 2025 source
  value may enter either fold.

Use WR and TE rows only. Exclude QB because the vendor's receiving FP/RR has
a documented semantic defect, and exclude RB because this hypothesis is
receiver coverage fit rather than total rushing-plus-receiving ceiling.
Resolve players without outcomes using normalized name, position, and team;
map opponent defenses with the repository's explicit team bridge. Preserve
unresolved/ambiguous rows and the four documented 2024 Denver unclassified
routes without inventing a coverage label.

## Frozen support and features

A receiver-season is eligible only with at least 200 Overall routes, at least
25 Man routes, and at least 100 Zone routes. A Man/Zone expected metric is
available only when both conditional values are populated. Defense Man and
Zone rates are divided by their sum before weighting because vendor rates do
not necessarily total exactly 100 after unclassified snaps and rounding.

For Cover 2/3/4/6 separation, use a receiver split only when it has at least
20 routes. Renormalize the opponent's prior-season Cover 2/3/4/6 weights over
the supported splits and require the retained splits to represent at least
50% of those four defensive rates. Missing is never zero.

Freeze exactly four treatment features:

1. `fp_cov_matchup_tprr_edge`: opponent-weighted Man/Zone TPRR minus Overall
   TPRR;
2. `fp_cov_matchup_yprr_edge`: opponent-weighted Man/Zone YPRR minus Overall
   YPRR;
3. `fp_cov_matchup_fprr_edge`: opponent-weighted Man/Zone FP/RR minus Overall
   FP/RR; and
4. `fp_cov_matchup_sep_edge`: opponent-weighted Cover 2/3/4/6 separation
   score minus the receiver's Zone separation score.

Persist source seasons, component route counts, retained shell weight, source
file/hash, and opponent for audit, but do not add them to the model. No raw
coverage rate, alignment, route-break, individual-route, red-zone, win-rate,
single-/two-high, or offense-matrix feature may enter this test.

## Frozen correlation and predictive reports

Evaluation rows are corrected K1 WR/TE snapshots with authoritative actuals,
a non-null pre-lock `mean_projection`, and all four supported treatment
features. Control and treatment use identical rows.

Before fitting, report for each feature and held-out fold:

- Spearman correlation with `actual - mean_projection`;
- point-biserial/Pearson correlation with `actual >= 30`; and
- 30-point event rate and mean projection residual in the bottom, middle
  three, and top feature quintiles fitted from that fold's distribution.

These are descriptive diagnostics, not a field-selection mechanism.

The predictive comparison exactly follows the prior paid-data diagnostics:

- regression target `actual - mean_projection`, with `Ridge(alpha=10.0)` and
  residual MAE;
- classification targets `actual >= 20` and `actual >= 30`, each with
  `LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)` and Brier loss;
- training-fold median imputation and standardization for numeric inputs;
  and
- the frozen control inputs `mean_projection`, salary,
  `target_share_last`, `target_share_jump`, `snap_share_last`,
  `snap_share_jump`, `team_vacated_target_share`, `depth_rank`, and
  `games_played_prior`, plus position one-hot encoding.

Report both folds, aggregate metrics, event counts, support/identity coverage,
missingness, correlation tables, and 30-point calibration deciles.

## Frozen gate

An outcome-blind implementation audit after preregistration found 1,709/5,927
supported 2024 WR/TE snapshot rows (28.83%) and 1,683/5,775 in 2025
(29.14%). The minimum route thresholds are working as intended by excluding
low-support splits, and each fold still has roughly 1,700 evaluation rows.
Before any actual score was queried, the availability gate was therefore
amended from 50% to 25%; no feature, support threshold, model, outcome gate,
or target population changed.

The coverage-fit mechanism passes only if:

1. supported prior-season coverage is at least 25% of eligible corrected
   WR/TE snapshot rows in both held-out seasons;
2. aggregate 30-point Brier is lower for treatment;
3. treatment 30-point Brier is no more than 1% worse in either held-out
   season; and
4. aggregate 20-point Brier is no more than 1% worse.

Residual MAE and individual correlations are mandatory diagnostics but not
vetoes. A pass licenses one separately preregistered twelve-candidate
coverage-fit union after the already-licensed Route Share union resolves its
incumbent. It does not directly alter production projections. A valid failure
closes this exact mechanism for pre-Week-1 adoption; do not retry a support
threshold, field subset, position group, interaction, model strength, fold,
or gate on these outcomes.

## Pre-outcome implementation status

The hash-locked importer is
`ingest/fantasy_points_coverage.py`; it resolves player identities without
outcomes, suppresses the known split 2022 Brock Wright row, maps all 32
defenses explicitly, and writes separate private receiver/defense prior
tables only under `WRITE_EMPTY`/byte-provenance guards. CLI command
`import-fantasy-points-coverage` is audit-only unless passed `--write`.

The diagnostic is `analysis/fantasy_points_coverage_fit.py`, CLI command
`fantasy-points-coverage-diagnostic`. It enforces source season N-1 for both
the receiver and target opponent, computes only the four registered features,
and emits the frozen correlation, quintile, calibration, fold and gate
reports. Audit-only import produced 2,093 receiver rows (2,044 resolved, 48
unresolved, one ambiguous, one known duplicate suppressed) plus 128/128
mapped defense rows. Sixteen focused Coverage/Advanced/Route tests pass;
Python compilation and whitespace checks are clean. No raw coverage table has
been written and no target outcome has been joined at this milestone.
