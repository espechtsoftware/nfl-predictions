# Point-in-time/join audit reconciliation

Date: 2026-08-11. This is the tracked project disposition of the read-only
outside review `reports/2026-08-11-pit-join-and-accuracy-code-audit.md`. The
outside document remains unmodified and untracked.

## Decision summary

The review found two genuine plumbing defects, one important test-coverage
gap, and two already-queued accuracy questions. It also overstates two
mechanisms. None invalidates an already completed production arm, but the
plumbing repairs must land before any affected candidate can be served live
or before the next normal feature rebuild.

## Finding dispositions

### 1. Candidate team-context rows are absent live — confirmed and repaired

`team_week_pace`, `defense_week_blitz`,
`team_week_target_concentration`, and `team_week_ftn_offense` are built only
from completed-game sources, while inference joins them on the exact target
week. Their five candidate outputs would therefore be null on a live upcoming
row even though replays see them.

Each table now appends only the distinct upcoming team-week from
`player_week_role`, with null current observations, before its strictly-prior
window. This preserves every historical row and emits the correct as-of value
at the target key. A mandatory post-build gap query checks all four tables
against every upcoming team-week and fails closed if a row is absent. Offline
SQL guards require the upcoming union permanently. The feature tables are not
being rebuilt while immutable experiments are in progress.

### 2. Dynamic leakage coverage is incomplete — direction confirmed, count corrected

The outside report's “7 of 54” count omits the two recomputed defense EPA
checks, first-row invariants for four opponent-adjusted fields, the Route
source-order contract, and the static test that rejects every model-table
window not ending at `1 PRECEDING`. The current dynamic source recomputation
still covers too little of the rolling feature surface, so the central process
recommendation is valid.

This is not a mechanical extension of one existing source query: efficiency,
advanced receiving, team context, injuries/vacancy, NGS and smoothed usage
have different grains and eligibility rules. Expand it by source family,
starting with active production fields, and require each reference query to
reconstruct the transform's actual spine and missingness semantics. Do not
claim coverage merely by checking first-row nulls.

The first source-family expansion is now implemented for the active production
trail. `dk_points_l4`, `dk_points_std` and `dk_points_vol` are independently
reconstructed from `player_week_actuals`, preserving the transform's rule that
salary-retained inactive zero labels are not played observations. The pure
reference adds BigQuery-compatible sample-standard-deviation semantics and a
negative include-current test. A read-only live check passed all three fields
on the exact same deterministic 11,686 built/source sample rows. Advanced
opportunity/NGS fields are the next family; they are not claimed covered yet.

### 3. Team CPOE is computed but unused — confirmed and already frozen

The unused `qb_quality` CTE in `015_player_week_efficiency.sql` corroborates
the missing QB-to-pass-catcher channel. BigQuery may optimize an unused CTE
away, so “evaluated and discarded” is not guaranteed; the meaningful issue is
that it never reaches an output. The independently frozen
`reports/2026-08-11-tabpfn-team-qb-quality-protocol.md` already defines the
correct repair: dropback-weighted, six strictly prior team games on a schedule
spine, broadcast only to RB/WR/TE, after the active-label and SCHED sequences.
Do not wire the same-week CTE directly or jump that queue.

### 4. Season-final position — real but narrower than reported; repaired

The direct model `position` in `player_week_usage` comes from the exact
salary/player week (or the exact upcoming role row), so week-18 position does
not directly overwrite the training feature as the review claims. The
season-final lookup is a genuine future leak in
`defense_week_allowed`, where it assigns historical player points to
positional opponent aggregates.

An outcome-free warehouse audit found exact weekly roster coverage for every
2019--2025 actual row except nine zero-point, unsalaried 2020 rows from one
unrostered ID, with no ambiguous exact player-week position. Final-season
position differs from the exact week on 403 actual rows: 0.53%, 0.64%, 0.17%,
0.22%, 0.11%, 0.19%, and 0.13% by season 2019--2025. The modeled defense SQL
now uses only exact `(gsis_id, season, week)` roster position. The rear-view
UI table may be cleaned separately but is not a model input. Because this
changes historical active feature values, the next rebuild requires normal
full retraining and validation; do not mutate the warehouse mid-panel.

### 5. Sparse QB NGS field — useful diagnostic, imputation claim dismissed

The tracked TabPFN generator performs no imputation: it converts the column to
float and passes NaNs directly to `tabpfn==2.2.1`. It cannot turn the field into
a near-constant through a nonexistent generator imputer. The broader concern
remains valid: `qb_cpoe_l6` is sparse and may partly proxy qualifying-starter
status. The next cache stage must report support and prediction behavior split
by position, active status and feature presence. This is a diagnostic, not a
license to drop, fill or broadcast the field; the separately frozen team-QB
experiment answers the pass-catcher question.

## Ordered work

1. Land the four upcoming-row repairs, exact-week defense position and the
   mandatory live-row gap gate. Do not rebuild until active immutable gates
   finish.
2. Complete the active-label → SCHED → team-QB marginal sequence in its frozen
   order. Add the sparse-feature support report during the next cache build.
3. Continue source-recomputed leakage checks one feature family at a time.
   Active efficiency is complete; advanced and team-context fields are next.
   Every new query must have synthetic positive and negative tests.
4. On the next coordinated feature rebuild, prove historical row-count/key
   stability, quantify the intended defense-feature deltas, retrain all live
   registries and rerun deployment verification before serving Week 1.

## Validation completed before commit

- All changed feature SQL dry-runs successfully against the live BigQuery
  schemas.
- Focused feature-SQL and leakage suites pass, including the new exact-week
  position and upcoming-row guards.
- The first active-efficiency expansion passes its synthetic include-current
  test and a read-only 11,686-row live source/built comparison.
- `git diff --check` and Python compilation are clean.
