# Fantasy Points same-season QB shell-fit protocol

Status: queued and frozen on 2026-08-13 before collecting the complete
Offense Coverage Matrix window grid or joining this treatment to a target-week
outcome. This is an operator-directed follow-up prompted after other paid-data
results were known; it is not an independent discovery claim.

## Question

Does a team's quarterback efficiency against Man/Zone and one-high/two-high
shells over the last four completed weeks interact with the upcoming
opponent's recent defensive shell mix strongly enough to improve held-out
30-point QB-tail forecasts?

This is distinct from the closed Advanced Passing family: it tests a
predeclared offense-by-defense schematic interaction rather than adding a
broad block of QB process rates. It is also distinct from the closed WR/TE
coverage-fit mechanisms. No receiver feature or result is reopened.

## Honest historical construction

Use the tracked 56-export plan
`automation/fantasy_points/plans/same-season-qb-shell-fit-last-four-v1.json`.
For target Week W in 2022--2025, it exports the Offense view of Coverage
Matrix for exactly Weeks W-4 through W-1. Pair it with the already accepted
Defense Coverage Matrix window for the same season, target week and source
weeks. Every file must preserve group headers and independently pass exact
Season, `G<=4`, context, manifest, SHA-256 and source-week checks. Week W or
later is forbidden.

The vendor QB Coverage Matchup export is not an input. That page has no
historical-season selector, and the available sample combines completed 2025
inputs with the 2025 Week 1 schedule. It cannot honestly replay 2022--2025.

## Frozen population, support and features

Use QB rows from the corrected accepted point-in-time replay snapshots for
target Weeks 5--18. Evaluation requires an authoritative actual and non-null
pre-lock `mean_projection`. Derive team and opponent from the project snapshot
and schedule, never the vendor matchup field.

An offense/defense window is supported only when both team rows have at least
80 dropbacks, all required deployment rates and conditional FP/DB values are
finite, Man+Zone rate is positive for both rows, and one-high+two-high rate is
positive for both rows. Normalize each two-shell pair over its own observed
sum; missing is never zero.

Freeze exactly two treatment features:

1. `fp_qb_shell_mz_grade`: opponent-defense-weighted offensive FP/DB against
   Man/Zone divided by the same offense's own recent faced-mix-weighted FP/DB,
   minus one; and
2. `fp_qb_shell_mof_grade`: the analogous value for one-high/two-high.

The offense-conditioned FP/DB fields are assigned by their group-qualified
column positions because the CSV repeats the bare `FP/DB` header. Raw defense
FP/DB allowed, raw scheme rates, Cover 0/1/2/2-Man/3/4/6 rates, absolute
expected FP/DB, Advanced Passing fields and unlisted interactions are excluded.
This isolates schematic fit rather than re-testing opponent strength or
recent QB quality already represented in the control.

## Frozen walk-forward comparison

Use the same control, preprocessing and estimators as the completed
same-season Advanced Passing diagnostic:

- held-out 2023 trains on target-season 2022;
- held-out 2024 trains on 2022--2023;
- held-out 2025 trains on 2022--2024;
- control inputs are `mean_projection`, salary, `target_share_last`,
  `target_share_jump`, `snap_share_last`, `snap_share_jump`,
  `team_vacated_target_share`, `depth_rank`, and `games_played_prior`;
- residual regression uses `Ridge(alpha=10.0)`; and
- 20- and 30-point classification use
  `LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)` with
  training-fold median imputation and standardization.

Report fold and aggregate Brier loss, residual MAE, event counts, identity and
support coverage, missingness, calibration deciles, and each grade's Spearman
projection-residual and point-biserial 30-point correlations. Descriptive
correlations cannot select a feature, transform, threshold or subset.

## Frozen gate and consequence

The player-level mechanism passes only if supported coverage is at least 70%
in every held-out fold and aggregate 30-point Brier loss is strictly lower for
the treatment. Season-specific 30-point Brier, aggregate 20-point Brier and
residual MAE are mandatory diagnostics but are not vetoes, matching the
operator's aggregate extreme-tail objective.

A pass licenses one separately preregistered exact-80 QB candidate-union test;
it does not directly change projections or production. A valid failure closes
this exact two-grade, last-four-week team-shell mechanism. Do not retry a
window, field subset, support threshold, transform, estimator or gate on its
observed result.

## Prospective 2026 counterpart

Continue the existing pre-lock capture contract for QB Coverage Matchup and
WR Coverage Matchup once the site passes the exact 2026 schedule-pair gate.
Those captures remain collection-only. Before the first 2026 outcome is
available, freeze a separate prospective grading protocol using the vendor's
published `EXP FP/DB`/`COV GRADE` and receiver matchup fields. Historical
results from this team-level proxy may inform that protocol only if their
adaptive provenance is disclosed; they may not turn the stale offseason
samples into training data.

## Next action

After the active effective-rank/TD-ledger queue reaches a safe launch or wait
boundary, collect the 56 offense windows with the tracked Playwright plan.
Then implement a manifest-locked offense-matrix importer, reuse the accepted
defense windows, run an outcome-blind support audit, and execute the frozen
walk-forward diagnostic once from an immutable full-test Cloud image.
