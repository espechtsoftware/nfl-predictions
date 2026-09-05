# SD-B terminal adjudication and production monitor repair

Date: 2026-09-05 UTC  
Production branch: `codex/week1-pmix-live-certification`  
Lab merge-release commit: `ca9673f`

## Outcome

SD-B run `sdb095r1-20260904T223841Z` is terminal-clean and its production
merge gate is released. Cloud Run execution `lab-run-6v6sx` completed at
`2026-09-05T00:51:26.590545Z` with 48 succeeded, zero failed, zero cancelled,
and zero retried tasks. A metadata-only GCS census found exactly the required
48 nonempty names, `shard-0.json` through `shard-47.json`, and no extras.
Production did not open any shard content.

The lab-facing release is committed on lab `main` as
`handoffs/PRODUCTION-TO-LAB-SDB-TERMINAL-AND-MERGE-RELEASE-2026-09-05.md`
at `ca9673f`. The lab now owns the strict merge and first read.

## Orphaned launcher adjudication

The initial shell-detached launcher parent PID `1694314` died, although its
isolated registered child and bound coordinator continued to terminal success.
The terminal log is:

- path:
  `/home/erich/projects/nfl2-sdb-binding/.tmp/sdb095-launch-20260904T223820Z.log`
- SHA-256:
  `d5391f4fe6abae98aae42520302fedc4033da18e59a6448485c371e0943c8a2f`
- terminal statement:
  `terminal success sdb095r1-20260904T223841Z execution=lab-run-6v6sx shards=48`

The original launcher receipt was preserved byte-for-byte at:

`/home/erich/.local/state/nfl-dfs/lab-launcher-registry/adjudicated-launcher-receipts/queue_sdb095_registered.sh-1694314.orphaned-20260905T014417Z.json`

Its key is
`c151bcd5faef1a8f7fae2d90ac1155294d0ad1bc7236ad6c1f54ea7e822d625c`.

The exact restart-safe registered wrapper was then run in the foreground. It
found the one existing claim, performed no Cloud Run job update or execution,
revalidated the provider envelope and exact object-name census, and exited
zero. Its authentic completion key is
`735044340b7c61c4db96cc2be5b976d0bb2a2e570b46abce3172a641ad4e93d6`;
the completion-record SHA-256 is
`8e0ee17a7851f54bab5fb70fa40fb66551694c4a602753a5ec1a26fac639e591`.

The original dead-parent key was then manually adjudicated against the
preserved receipt and the successful restart-safe reconciliation. Its
completion-record SHA-256 is
`3425be543aaf7385a91c5c8953582ef030dda6058c3faadee393b4a4c533429d`.
This is explicitly a manual production adjudication; it is not represented as
a file written by the dead parent. Both completion records reconstruct their
bound receipts and pass the strict schema.

## What monitoring got wrong

The provider poll itself was timely: it observed the 48/48 completion at
`2026-09-05T00:52:17Z`, 51 seconds after the provider completion time. Two
separate control problems delayed action:

1. The coordinator had already been marked orphaned, and that alert had been
   delivered at launch. Provider terminal transitions were intentionally not
   notifiable, so the terminal event generated no new wake-up.
2. During manual receipt adjudication, the monitor observed the newly written
   completion file in a transient non-`0600` state before its mode was fixed.
   The registry correctly failed closed, but `collect_status` incorrectly
   treated the resulting unavailable scan as an authoritative empty ledger.
   It latched every prior completion as missing and then mislabeled all of the
   unchanged records as changed when the next scan succeeded.

The first issue explains why polling could be current while production still
failed to act. The second made the monitor state itself untrustworthy until it
was repaired.

## Repair

`scripts/cloud_run_lane_monitor.py` now:

- preserves the last valid completion inventory and hashes when a registry
  scan fails, while still raising the fail-closed `launcher-registry` alert;
- suppresses completion new/change/missing deltas during that unknown scan;
- retains coordinator identity but makes acceptance unverifiable until the
  registry validates again;
- emits one event-only notification when the provider cohort reaches success
  but coordinator acceptance has not been obtained, including an already
  orphaned coordinator;
- distinguishes pending acceptance from failed/orphaned adjudication in alert
  text and gives a later successful acceptance precedence over a stale queued
  notification; and
- reports an integrity failure's real reason instead of falsely saying
  `nonzero coordinator exit` when `exit_status` is zero.

The poisoned status and attention snapshots were moved, not deleted, to:

`/home/erich/.local/state/nfl-dfs/cloud-run-lane-monitor/recovery-20260905T015701Z/`

Their pre-repair SHA-256 values are:

- status:
  `fcc862aa74ee156e1eff87787390f46aafae5ba1bf9262404b1e5f4948612a73`
- attention:
  `53d895fc8cc1c113e308a764a1e9095ea54041de54dd405003e56b784c957b28`

The append-only event ledger was retained. The service now executes the
repaired source from the clean production worktree rather than the dirty,
156-commit-behind primary checkout.

## Validation

- `pytest -q tests/test_cloud_run_lane_monitor.py`: 38 passed
- `python -m py_compile` on implementation and tests: passed
- `git diff --check`: passed
- live systemd service: active, zero restarts
- live snapshot at `2026-09-05T02:00:21Z`:
  - provider cohort `succeeded`
  - coordinator acceptance `succeeded`
  - effective cohort `succeeded`
  - completion-integrity failures: 0
  - completion-ledger alerts: 0
  - notification backlog: empty

Ruff was not available in the active Python environment, so no Ruff result is
claimed.

## Durable operating rule

Long-running registered coordinators must run in a persistent service context,
not as children of an ordinary detached command session. The OS monitors poll
and persist metadata even when chat is idle, but they cannot independently
start a new Codex turn. Therefore each active cohort needs both a durable
coordinator that can finish census/release autonomously and event-only
notification for exceptional operator action. Open-ended chat-side polling is
not a substitute and should remain disabled.
