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

The source-family expansions are now implemented. For the active
production trail, `dk_points_l4`, `dk_points_std` and `dk_points_vol` are
independently reconstructed from `player_week_actuals`, preserving the rule
that salary-retained inactive zero labels are not played observations. The
pure reference adds BigQuery-compatible sample-standard-deviation semantics
and a negative include-current test. For advanced opportunity/NGS,
`ez_targets_l4`, `deep_targets_l4`, `separation_l4` and `stacked_box_l4` are
reconstructed from PBP/NGS on the exact complete usage spine. Exact null-
support parity is mandatory so missing observations continue to occupy bounded
`ROWS` windows. The adopted neutral-pass field is independently recomputed as
its actual ratio of rolling sums, and both QB NGS fields preserve their
deliberate cross-season window. Read-only live checks passed on identical
11,686-row efficiency, 4,975-row advanced, 1,336-row neutral-pass and 253-row
QB NGS built/source samples.

The final expansion exposed two real common-data defects before the
active-label exact-80 score query. First, the empirical-Bayes red-zone fields
used one all-history position average, so early historical rows borrowed later
seasons. The repaired transform constructs position-week sufficient statistics
and windows them through `1 PRECEDING`. Its independent reference now
reconstructs all 29 usage-family outputs: bounded averages, last values, sums,
counts, jumps, trends, WOPR, expanding fields and both smoothed opportunities.
On the current warehouse the 4,975 sampled keys are identical and every field
except the two known contaminated smoothers matches exactly; 3,625
`rz20_targets_smoothed` and 3,640 `gl3_carries_smoothed` values change, with
maximum absolute deltas `0.0673186` and `0.0571626`.

Second, `raw.injuries` contains 65,866 rows on 65,862 player-week keys and the
old transform neither deduplicated revisions nor enforced the common Sunday-
main lock. Among deterministic latest revisions, 24 are post-lock and four of
those say `Out`. The repaired table chooses exactly one latest pre-lock row,
persists both source and lock timestamps, and independently reconstructs the
status, practice trend, prior missed games and downstream player-level vacated
shares with exact key/null/value parity. These repairs change active historical
features, so they require one coordinated rebuild/retrain and invalidate the
old active-label cache gate as production evidence. No active-label lineup
outcome was queried; the exact-80 launch is blocked cleanly pending identical-
law PIT-clean cache regeneration and final-served revalidation.

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

1. Land all PIT repairs and the complete dynamic source-family gate; do not
   launch the already-frozen exact-80 books from stale caches.
2. Run one coordinated feature rebuild, prove row-count/key stability, quantify
   intended deltas and retrain every live registry on the repaired tables.
3. Regenerate both active-label research caches under their unchanged frozen
   training laws, including the sparse-QB support report, then repeat the same
   score-free final-served gate. Only a clean pass may release exact-80.
4. Resume the active-label → SCHED → team-QB sequence in its frozen order and
   rerun deployment verification before serving Week 1.

## Validation completed before commit

- All changed feature SQL dry-runs successfully against the live BigQuery
  schemas.
- Focused feature-SQL and leakage suites pass, including the new exact-week
  position and upcoming-row guards.
- Active-efficiency, advanced, neutral-pass and QB-NGS expansions pass
  synthetic include-current/null/key/value tests and read-only
  11,686-/4,975-/1,336-/253-row live comparisons.
- The complete 29-field usage reference dry-runs at 33,165,826 bytes and has
  exact key/value parity on all uncontaminated current fields; injury and
  vacancy references dry-run at 5,541,943 and 10,198,069 bytes. The focused
  suite passes 94 tests with one expected dashboard-window skip.
- `git diff --check` and Python compilation are clean.
