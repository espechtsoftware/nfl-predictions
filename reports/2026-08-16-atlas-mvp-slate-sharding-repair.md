# ATLAS MVP slate-sharding compute repair

Date frozen: 2026-08-16, after the repair1 executions were cancelled and
before any matched-diversity slate or effect output existed

## Mechanical failure

The immutable repair1 season executions were healthy but computationally
nonviable:

- `atlas-matched-diversity-2023-v1-repair1-hwj79`
- `atlas-matched-diversity-2024-v1-repair1-ghvxk`
- `atlas-matched-diversity-2025-v1-repair1-qmnmq`

Each ran one task from 2026-08-16 08:20 UTC until cancellation at
12:04 UTC. None emitted the non-metric `ATLAS_MVP_SLATE_COMPLETE` marker for
its first of 18 slates. The runner's newly added interaction MILPs use CBC,
which is single-threaded in the shared optimizer, so the allocated eight CPUs
did not provide within-solve parallelism. At the observed rate, an eight-hour
season task could not complete all 18 slates.

All three executions were cancelled before timeout to stop wasting compute.
Their terminal reason is `Cancelled`, and all four create-only repair1 objects
(`season-2023.json`, `season-2024.json`, `season-2025.json`, `report.json`)
are absent. This is a mechanical execution failure with no effect disposition.
No partial metric or candidate output was opened.

## Licensed repair

The scientific computation is unchanged. Only its transport may be sharded:

1. run the exact existing `_run_slate` calculation as one immutable task per
   registered `(season, week)` cell;
2. retain exact source panels, artifacts, code paths, solver objectives,
   cluster order, global seed order, 40-per-seed/200-per-slate count,
   P0/P1/P2 construction, selector, summaries and frozen gate;
3. write one create-only score-free object for each of the exact 54 slates
   under a new `v1-repair2` prefix;
4. add only non-metric seed/slate completion markers for compute monitoring;
5. run at one CPU because CBC is single-threaded, with 4 GiB memory and
   a 12-hour no-retry timeout per slate;
6. read no slate object until every one of the 54 executions is terminal
   successful; and
7. have one strict finisher validate all execution image, command,
   environment, resource, account and source receipts, group exact Weeks
   1--18 into the unchanged season-report schema, and invoke the unchanged
   three-season aggregate/gate.

No parameter, seed, source, mechanism, candidate budget, threshold, effect
rule or consequence may change. Failure of any one slate invalidates the
repair2 set; it may not be omitted or rerun under another scientific choice.

## New immutable identities

- Output prefix:
  `gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair2`
- Slate object shape: `slate-{season}-{week}.json` for exact seasons
  2023--2025 and Weeks 1--18.
- Final objects: `season-2023.json`, `season-2024.json`,
  `season-2025.json`, and `report.json` under the same prefix.
- Each slate task: one CPU, 4 GiB memory, one task, one parallelism, zero
  retries and 12-hour timeout.

This repair must be bound by SHA-256 in the runner, launcher and finisher and
must use a new clean-archive image and new job/execution identities.
