# Advanced Receiving support-window collection protocol

Frozen on 2026-08-11 CDT after the served-tail Stage B result and before any
new Advanced Receiving window was joined to a target-week outcome. This phase
licenses collection and an outcome-blind support/redundancy audit only. It does
not license a predictive diagnostic, feature, lineup arm or production change.

## Why this is the next collection

The exact last-four Advanced Passing, receiver coverage and route-shape
families failed. The post-window program review correctly notes that the
last-four policy also limited support, and ranks same-season Advanced Receiving
as the remaining historical vendor family with the clearest ceiling mechanism.
The earlier outcome-blind audit found its target share, air-yard share and
XFP/game largely duplicate existing inputs, but first-read rate and XFP per
route remain plausible distinct process measures. No target-week outcome may
be used to choose between them in this phase.

## Immutable collection

Use only
`automation/fantasy_points/plans/same-season-advanced-receiving-support-windows-v1.json`.
It contains 108 grouped-header Player exports:

- 56 cumulative-prior windows for seasons 2022--2025, target Weeks 5--18,
  using exact source Weeks 1 through W-1; and
- 52 last-four-prior windows for the same seasons, target Weeks 6--18,
  using exact source Weeks W-4 through W-1.

Target Week 5 needs no duplicate last-four export because it is identical to
the cumulative Weeks 1--4 window. Every artifact must pass the downloader's
catalog, Apply-response, rendered filter, Season, target/source-week, grouped
header, row-width and `G <= source-window length` checks. Same-week/future
weeks, postseason, vendor opponent fields and artifacts outside the one final
complete manifest are forbidden.

## Outcome-blind audit only

Before any outcome join, re-hash and parse the final manifest, resolve players
against point-in-time accepted snapshots, and report by season/target week:

- player and resolved-player counts by position;
- route-count distributions and coverage at fixed descriptive route floors;
- availability of the six already-registered receiving fields: TPRR, aDOT,
  air-yard share, YPRR, first-read rate and XFP per route;
- exact cumulative versus last-four overlap and deltas; and
- redundancy against the existing strictly-prior feature panel without any
  actual score, residual, event label, selected lineup or placement column.

This audit may determine whether the family has enough support for one test.
It may not select a field because it correlates with an outcome. If support is
adequate, freeze one coefficient-free support/shrinkage rule, one complete
feature contract, walk-forward folds, all-row CRPS/tail calibration gate,
paired uncertainty/MDE and consequence before querying outcomes. If support is
not adequate, stop; do not sweep windows or thresholds.

Any later historical result is operator-directed evidence because this path
was prioritized after other outcomes were known. Production adoption would
still require an independently frozen 2026 prospective shadow.
