# Week-1 `us_dfs` capture implementation

Date: 2026-09-04 UTC

Status: implemented and locally validated; deployment/capture receipt pending

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

## Next actions

1. Commit and push the exact implementation.
2. Build the scoped collection image from that exact pushed source.
3. Create the raw table, deploy only `ingest-us-dfs`, and create/update its two
   schedulers without changing the existing odds/prop jobs.
4. Run one bounded Week-1 capture, verify request cost and table row counts,
   and publish a redacted coverage summary for the lab.
5. Continue prospective snapshots; do not start a historical backfill or a
   scoring experiment unless D7's already-frozen calibration gate licenses it.
