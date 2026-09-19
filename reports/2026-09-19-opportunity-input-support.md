# Practice-trajectory support: useful new captures, insufficient historical training

The warehouse preserves genuine changes in this season's practice reports, but
does **not** contain a historical Wednesday-to-Friday trajectory panel. The
trajectory version of E1 therefore needs more data before an honest historical
model test. This is an input census, with no outcome labels read and no model fit.

## What is present

All four read-only queries use the same warehouse time-travel cutoff, recorded in
the [source and query receipt](reviews/evidence/2026-09-19-opportunity-support-census.json).
No source table was written. Each query was dry-run and capped at 100 MB billed.

| Source | Support |
|---|---|
| Historical raw injuries, 2014–2024 | Essentially one report per player/week. Only three player/weeks have multiple source dates across all these years; these exceptions do not constitute trajectory coverage. |
| Historical raw injuries, 2025 | 5,783 regular-season player/weeks, all missing source modification timestamps. No historical collector captures establish their prelock availability. |
| 2026 Week 1 collector, before common Sunday lock | 182 reported players; 167 observed on multiple dates; 64 with more than one practice status; up to six captures per player. |
| 2026 Week 2 collector, by census time | 230 reported players; 194 observed on multiple dates; 48 with more than one practice status; up to two captures per player. |

These counts include all reported positions and scheduled teams, not just the
fantasy-eligible Sunday-main skill-player cohort. Repeated observations do not
constitute independent outcomes. The Week-1 prelock subset excludes its five
later daily captures; those later captures cannot be backdated into decisions.
All captured rows lack provider modification timestamps, so their collector
observation times establish availability. None has a malformed source timestamp
later than its capture.

The workstation agent reports no exclusive historical trajectory archive beyond
the shared sources. The existing saved vendor files do not, by themselves,
establish a daily injury-report history.

## What the existing feature actually means

[`018_player_week_injury.sql`](../sql/features/018_player_week_injury.sql) first
encodes each report's one practice status, then selects the latest admissible
player/week report. Its `AVG` operates on a **single-element array**. Consequently,
`practice_level` is not an average of Wednesday, Thursday and Friday practice,
despite a comment and PREREG-100's prose describing it that way.

`practice_participation_trend` subtracts the previous retained weekly report's
level, using `LAG` over report weeks. That earlier report need not be the immediately
preceding calendar week. It is not a within-week progression feature. This is a
semantic clarification, not evidence that PREREG-100's numeric result is invalid:
that experiment used the actual stored values. No feature behavior is changed.

The materialized Week-2 injury feature currently has 194 rows from September17
10:03 UTC, while raw collection already has 230 from September18 10:03 UTC. This
is a freshness difference to verify after the scheduled Saturday refresh, not a
claim that the future build has already consumed stale values. The actual next
capture and feature refresh must be checked before building.

## Next bounded work

Keep collecting and preserving the timestamped 2026 reports. They can support a
prospective within-week trajectory study as the season develops; do not manufacture
earlier trajectories from final weekly files. The capture series still needs a
complete healthy-player universe and explicit absence semantics before modeling.

A separate support question remains feasible now: whether the historical prelock
injury **type**, combined with existing designation, practice level and prior role,
adds information about opportunities conditional on playing. Injury type is in the
raw schema but is absent from the current injury feature output and model feature
list. That is a potentially new input, not evidence of value. First census its
timestamp-valid coverage and categories on the training universe, then freeze a
single incremental opportunity test if support is adequate. Repeating P(active),
applying another generic Questionable cap, or changing final score scaling would
not answer that question.

The first two query drafts failed dry-run syntax validation (a reserved SQL alias
and time-travel alias order); all four actual census queries succeeded after those
mechanical corrections. No outcome-bearing query or partial model read occurred.
