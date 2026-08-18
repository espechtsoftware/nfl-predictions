# D0 gate 5: odds/weather covariates are prospective-only

Date: 2026-08-18. **No realized DFS outcome was read. No production change.**

D0 gate 5 asks to "implement reusable common-lock odds/weather selectors and
their `pulled_at <= lock` assertions before those covariates can enter D1/D2."

Before writing the selectors I checked what they would select from. **The answer
changes the gate's purpose.**

## Finding: neither covariate has historical coverage

| source | rows | coverage |
|---|---:|---|
| `nfl_raw.weather` | **0** | none, ever |
| `nfl_raw.odds_snapshots` | 44,064 | **2026-07-31 to 2026-08-16 only** |

**Weather can never be backfilled.** `weather_job.upcoming_games()` selects games
`BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 4 DAY)` and calls a
forecast API. It is a forward-looking collector by construction; there is no
historical forecast to recover for 2019-2025. The table is empty today only
because no games fall in the window in mid-August — the job runs on `s-weather`
(`0 8 * * 5-7`, ENABLED), succeeded on 2026-08-09/14/15/16, and exits zero. **Not
a defect.**

`odds_snapshots` likewise begins at the current collector's start date and
carries no `season`/`week` keys — only `event_id`, `event_name`, a STRING
`start_time`, `market_type`, `selection`, `line`, `odds_american`, `pulled_at`.

## Consequence

**Odds and weather covariates cannot enter any DST model fit on the historical
panel.** Both the 54-slate (2023-2025) and 107-slate (2019, 2021-2025) panels
predate all available data. A D1/D2 event model that consumes them is
**2026-forward only**, and its first evaluable evidence arrives during the
season.

This does not block D1/D2. The DST event components the world model actually
needs — sacks, interceptions, fumble recoveries, safeties, blocked kicks, return
TDs, points-allowed tiers, and their strictly-prior L4/L16 windows — are all
present in the rebuilt `team_defense_week` frame for 2014-2025 and are
point-in-time clean (zero window overruns across 6,302 rows). **Build D1/D2 on
those, and treat odds/weather as a prospective enhancement rather than a
prerequisite.**

## Recommended gate 5 restatement

The gate as written implies odds/weather are needed before D1/D2 can proceed.
They are not available to be needed. Suggested replacement:

1. Factor the canonical common Sunday-main lock — currently duplicated inline in
   `sql/features/018_player_week_injury.sql:6-20` (min Sunday REG kickoff with
   `gametime` in `[13:00, 19:00)` Eastern) — into **one reusable definition**, so
   the odds, weather, injury and any future covariate paths cannot drift apart.
   That refactor is worth doing on its own merits today.
2. Write the `pulled_at <= slate_lock_at` selectors against that shared lock, and
   mark them **prospective-only** with an explicit assertion that they return
   zero rows for any season before 2026.
3. Remove odds/weather from the D1/D2 critical path.

## Related

The same live-only, non-reconstructible property motivated deploying the DK
contest-fills collector today
(`reports/2026-08-18-contest-fills-collector-deployment.md`). Weather and odds
snapshots are already collecting; contest fills were not. All three share the
rule that **acquisition not running during the season is permanent data loss.**
