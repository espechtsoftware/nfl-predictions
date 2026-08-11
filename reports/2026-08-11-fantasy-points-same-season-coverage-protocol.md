# Fantasy Points same-season coverage-fit diagnostic protocol

Preregistered on 2026-08-10 CDT after exact-window semantics and redundancy
were established, and before any row from this treatment was joined to a
realized target-week outcome.

## Question

Does a receiver's performance during the last four completed weeks against
Man and Zone coverage, matched to the upcoming opponent's last-four-week
defensive Man/Zone deployment, improve walk-forward forecasts of a 30-point
DraftKings performance beyond the corrected pre-lock feature set?

This is a timing extension of the completed prior-season coverage-fit
diagnostic. It is not permission to search the newly available report grid.

## Immutable collection surface

Use the tracked Playwright plan
`automation/fantasy_points/plans/same-season-coverage-last-four-v1.json`.
It contains exactly three report families for seasons 2022--2025 and target
Weeks 5--18:

- Receiving Man vs. Zone, Player view;
- Receiving Separation by Coverage, Player view; and
- Coverage Matrix, Defense view.

For target Week W, select exactly Weeks W-4 through W-1, press `Apply`, and
reopen the Week(s) control to prove that exact set before export. Every
manifest record must name W, contain only source weeks `< W`, preserve group
headers, record SHA-256/shape/retrieval time, and pass the report-specific
game-count/schema checks. Licensed CSVs remain ignored and outside Git.

Weeks 1--4 are excluded from this diagnostic. Production continues to use
the existing prior-season/fallback behavior there; no target-week data is
ever allowed.

## Frozen population and support

Evaluate WR and TE target rows from the corrected accepted K1 snapshot only.
Resolve identities without outcomes using normalized name, position and team,
and derive the target opponent from the project's point-in-time schedule.

A receiver-window is supported only with:

- at least 50 Overall routes;
- at least 10 Man routes; and
- at least 25 Zone routes.

These are the prior diagnostic's 200/25/100 full-season thresholds scaled to
a four-game window and rounded upward. Both conditional values must be
populated. Defense Man and Zone rates are divided by their sum because the
vendor categories need not total 100 after unclassified plays and rounding.
Missing is never zero. The outcome-blind audit found 43.9% and 38.2% support
among active target-Week 5 and Week 9 WR/TE salary rows respectively.

## Frozen treatment features

Use exactly four features:

1. `fp_cov_l4_matchup_tprr_edge`: opponent-weighted Man/Zone TPRR minus
   Overall TPRR;
2. `fp_cov_l4_matchup_yprr_edge`: opponent-weighted Man/Zone YPRR minus
   Overall YPRR;
3. `fp_cov_l4_matchup_fprr_edge`: opponent-weighted Man/Zone FP/RR minus
   Overall FP/RR; and
4. `fp_cov_l4_matchup_sep_edge`: opponent-weighted Man/Zone Separation Score
   minus Overall Separation Score.

The expected conditional value for metric M is
`man_weight * man_M + zone_weight * zone_M`, where weights come from the
target opponent's matching four-week Defense Coverage Matrix.

Do not include raw scheme rates, Cover 2/3/4/6, red zone, single-/two-high,
alignment, win rate, route breaks, individual routes, Offense Matrix,
Advanced, Efficiency, Snaps, or the vendor opponent column. Do not change
support thresholds or feature definitions after seeing results.

## Frozen walk-forward evaluation

Use held-out target seasons 2023, 2024 and 2025:

- held-out 2023 trains on target-season 2022;
- held-out 2024 trains on target-seasons 2022--2023; and
- held-out 2025 trains on target-seasons 2022--2024.

Use only target Weeks 5--18. The control rows, median imputation,
standardization and models match the completed prior-season diagnostic:

- residual regression with `Ridge(alpha=10.0)`;
- 20- and 30-point classification with
  `LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)`; and
- control inputs `mean_projection`, salary, `target_share_last`,
  `target_share_jump`, `snap_share_last`, `snap_share_jump`,
  `team_vacated_target_share`, `depth_rank`, `games_played_prior`, and
  position one-hot encoding.

Report fold and aggregate Brier loss for 20/30 points, residual MAE,
calibration deciles, event counts, source/support/identity coverage, and each
feature's Spearman projection-residual and point-biserial 30-point
correlations. Descriptive correlations cannot select fields.

## Frozen gate

This tail-first mechanism passes only if:

1. supported coverage is at least 30% in every held-out fold; and
2. aggregate 30-point Brier loss is strictly lower for treatment.

Season-specific 30-point Brier, aggregate 20-point Brier and residual MAE are
mandatory diagnostics but are not vetoes. This deliberately reflects the
operator's stated objective that aggregate access to exceptional weekly
lineups matters more than small average or individual-season declines.

A pass licenses one separately preregistered candidate-union test; it does
not directly change projections or production. A valid failure closes this
exact mechanism. No threshold, position, feature subset, window, model,
coefficient, fold or gate retry is licensed on these outcomes.

## Pre-outcome implementation status

The manifest-locked importer is
`ingest/fantasy_points_same_season_coverage.py`; it requires the full frozen
168-export grid, validates every file hash/shape/window/context, enforces
`G<=4`, resolves players without outcomes, requires all 32 defenses per
window, suppresses duplicate identities, and materializes the frozen support
flag. The diagnostic is
`analysis/fantasy_points_same_season_coverage.py`; it enforces exact
same-season W-4:W-1 receiver and opponent-defense joins and implements only
the four registered features and aggregate tail gate.

Focused tests cover complete-manifest and target-week rejection, opponent
joins, support behavior, and the tail-first gate. The two private raw table
names are explicit members of the daily backup job as well as covered by its
future `fantasy_points_*` discovery. Historical collection began only after
this protocol was committed; no new treatment outcome has been read.
