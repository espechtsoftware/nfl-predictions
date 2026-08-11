# Fantasy Points 2026 live matchup capture contract

Status: frozen on 2026-08-11 before Fantasy Points exposed a verified 2026
regular-season matchup snapshot. This is prospective data collection, not a
license to replay the stale offseason samples or add a production feature.

## Scope

Capture exactly three no-history tools once per target week:

1. QB Coverage Matchup;
2. WR Coverage Matchup; and
3. OL/DL Matchups.

The existing offseason files are schema samples only. They pair completed 2025
inputs with the 2025 Week 1 schedule and cannot be used for 2026 projections,
training, correlation claims or backtests.

## Point-in-time and schedule gate

For target season/week, derive the expected games and first kickoff from
`nfl_raw.schedules`, not from the vendor `OPP` field. A capture is eligible only
when all of the following hold:

- retrieval completed before the project-derived target week's **first
  kickoff** (stronger than Sunday-main lock, so Thursday results cannot enter
  a later capture);
- the vendor's rendered schedule week is the requested target week;
- every exported team/opponent pair maps uniquely to the target-season
  schedule, with no stale, missing or extra matchup silently accepted;
- the CSV bytes, schema, row count, source URL, retrieval time and SHA-256 are
  recorded in a complete manifest; and
- exact bytes are copied to a hash-addressed create-only GCS object before any
  normalized append.

Failure produces a labeled unavailable snapshot and leaves the incumbent
projection/lineup path untouched. It never falls back to the offseason sample.

## Interpretation and use

Fantasy Points documents that the coverage tools use the prior season until
Week 4 and are not fully trusted until then. Preserve that regime label on
every row. Weeks 1--3 are still worth capturing prospectively, but they are not
equivalent to mature in-season inputs.

The first objective is to accumulate a legal dataset that can eventually be
tested. Captures are collection-only: no `EXTRA_FEATURES`, manual boost,
candidate arm or production selection may consume them during 2026 unless a
separate protocol is frozen before outcomes and passes its distribution and
exact-80 lineup gates. Opponents must always be re-derived from the project
schedule at consumption time.

## Operating target

Implemented automation uses the existing authenticated Playwright profile,
presses Apply after selecting the schedule week, verifies the rendered
selection and response scope, downloads sequentially, archives immutably and
surfaces the operating command in the Weekly guide and the capture status in a
durable manifest. This can be built and dry-run against the current schema,
but the first accepted snapshot must wait until the schedule gate proves the
site has actually rolled to 2026.

The command is `fantasy-points-matchups --season 2026 --week W --archive`.
It is frozen to the three named reports and 2026 Weeks 1--18. The stale
offseason samples are useful for parser tests only and are never accepted by
the target-schedule gate.
