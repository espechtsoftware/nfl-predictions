# Week-1 `us_dfs` capture implementation

Date: 2026-09-04 UTC

Status: deployed; first bounded Week-1 capture completed successfully

## Purpose

The D5 selection-gap diagnostic found that rescue-decisive players are
disproportionately wide receivers while their pre-lock market coverage is
sparse. The lab's D7 contract therefore needs repeated, timestamped Week-1
observations from pick'em/DFS platforms before it can assess listing breadth,
line disagreement, quote freshness, or multiplier coverage.

This implementation adds collection only. It does not add a feature to a
model, change a projection, score a lineup, revive held experiment 091, or
alter experiments 092/093.

## Implemented boundary

- New default-off command: `nfl-dfs ingest-us-dfs`.
- Required enable switch: `ODDS_US_DFS_ENABLED=1`.
- Frozen market bundle: passing yards, passing touchdowns, rushing yards,
  receiving yards, receptions, and anytime touchdowns.
- Provider region: `us_dfs`, with displayed multipliers requested and retained
  verbatim. They are never interpreted as SGP probabilities.
- Event population: only the next regular-season week's domestic Sunday
  afternoon window. Preseason, Thursday, Sunday-night, Monday, and non-main
  international windows are excluded before any paid event request.
- Quota boundary: each event request is refused unless the provider's latest
  response header is present and the six-market cost preserves at least 5,000
  credits. Cloud Run retries are zero.
- Raw destination: `nfl_raw.prop_lines_us_dfs`, partitioned by `pulled_at` and
  clustered by season, week, market, and platform.

Each raw row retains event/kickoff/team identity, batch snapshot time,
platform identity and update time, market identity and update time, provider
player reference, outcome label, line, price, displayed multiplier, and pull
time. Provider request/quota telemetry continues to flow through the existing
`odds_api_requests` audit table.

## Schedule

The declarative schedule captures once at 10:30 America/Chicago Wednesday
through Saturday and at 06:30, 08:30, 10:30, and 11:30 Sunday. The last Sunday
snapshot is 30 minutes before the frozen Week-1 17:00Z lock. Daily and Sunday
schedules do not overlap.

At the current 13-game Week-1 Sunday-main population, the maximum planned
request cost is 78 credits per snapshot, plus the zero-cost events request.
The actual request audit remains authoritative if platform/market billing
differs.

## Validation

- `tests/test_oddsapi_import.py`: 11/11 pass, including default-off behavior,
  quota fail-closed behavior, event filtering, platform/line/multiplier
  preservation, and isolated BigQuery loading.
- `tests/test_cfb_cloudbuild_contract.py`: 4/4 pass after adding the collector
  to the scoped collection-image gate.
- `tests/test_cfb_deployment_contract.py`: 4/4 pass, including the zero-retry
  job and non-overlapping pre-lock schedules.
- Focused import/F checks, Python compilation, shell syntax, and whitespace
  checks pass before commit.

The scoped image build includes the runtime, raw-table contract, exact focused
tests, and an offline disabled-command smoke. It does not include reports,
large research artifacts, or a Git checkout.

## Deployment and first-capture receipt

- Exact source: `3e1dd916bb118ee9e179acca19b5319aba49d12f`.
- Scoped Cloud Build: `00cae15f-ba06-4e0a-82bb-f3a97a4f662c`, `SUCCESS`.
- Immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:590dfe12b81b80a34cf3a449ab4fac1d827575ec45112cb590f2801326974ea3`.
- Cloud Run job: `ingest-us-dfs`, generation 3, one task, 1 vCPU, 2 GiB,
  900-second timeout, zero retries.
- Schedulers: `s-us-dfs` and `s-us-dfs-sun`, both enabled in
  `America/Chicago` with the schedules above.
- Successful execution: `ingest-us-dfs-d9fqp`, one of one tasks successful,
  zero failures and zero retries, completed at 2026-09-04T03:27:25Z.

The first launch attempt, `ingest-us-dfs-6m7qq`, failed before making any
provider request because the direct deployment command omitted `GCP_PROJECT`.
The job was corrected in place to the declarative contract, then the single
bounded capture was run once. This was a deployment configuration defect, not
a provider or data failure, and it consumed no API credits.

Creating the new job also encountered the project's 1,000-job-definition
limit. Production verified that `atlas-minimal-c-smoke-inj` was an unscheduled,
terminal-success, one-off smoke definition last used on 2026-08-18 and removed
that job definition before creating `ingest-us-dfs`. Its historical execution
logs and immutable image remain the reproducibility sources; no active or
scheduled scientific job was removed.

## Redacted first-capture findings

The 2026-09-04T03:27:03Z snapshot contains:

- 934 quote rows covering all 12 eligible Week-1 Sunday-afternoon games;
- 143 distinct player references, two platforms, and five returned markets;
- 416 rows with displayed multipliers and all 934 rows with a price value;
- median market age 0.60 minutes, mean 0.63, and p95 1.82 at ingestion;
- 13 successful provider requests (one event census plus 12 event requests),
  no request errors, and 55 provider-reported credits consumed;
- 99,721 credits remaining after the capture, safely above the 5,000 reserve.

Returned market breadth was:

| Market | Events | Players | Rows | Platforms |
|---|---:|---:|---:|---:|
| Passing yards | 12 | 24 | 96 | 2 |
| Passing touchdowns | 7 | 9 | 22 | 2 |
| Rushing yards | 12 | 54 | 204 | 2 |
| Receiving yards | 12 | 118 | 460 | 2 |
| Receptions | 12 | 60 | 152 | 2 |

The requested anytime-touchdown market was absent in this snapshot. Of 265
event/market/player quote groups, 202 appeared on both platforms and 110 of
those multi-platform groups had different lines. The median nonzero line range
was 1.0 and the mean was 1.627 in each market's native unit. These are raw
coverage/disagreement facts, not evidence that either platform is more
accurate or that a line should enter scoring.

For licensing-safe coordination, platform identities are represented only as
stable aliases. `P01` supplied 518 rows across 140 players and all five markets
with no displayed-multiplier values. `P02` supplied 416 rows across 140 players
and all five markets, with displayed multipliers on every row. No player or
event identity is included in this report.

## Next actions

1. Give the lab this redacted schema/coverage receipt for its D7 work.
2. Continue the prospective schedules and measure stability, additions,
   removals, freshness, and cross-platform disagreement across snapshots.
3. Join coverage to the Week-1 candidate universe only inside the governed
   lineage path; missing platform rows remain explicit missingness, never zero.
4. Do not start a historical backfill or change scoring/selection unless the
   already-frozen D7 calibration gate licenses a later experiment.
