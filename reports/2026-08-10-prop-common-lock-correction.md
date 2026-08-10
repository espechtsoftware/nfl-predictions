# Historical prop common-lock correction

Status: point-in-time defect confirmed and reader correction validated;
immutable K3/K1 true-80 revalidation is in progress.

## Defect

`models.prop_market.market_points()` currently excludes Tuesday opening rows
and consumes the historical two-hours-before-kickoff snapshot for every game.
That is valid for an individual sportsbook wager, but not for a DraftKings
Sunday-main lineup. The entire roster locks at the first 1 p.m. Eastern game.
A 4:05/4:25 p.m. player's historical prop close was collected around
2:05/2:25 p.m.—more than an hour after the DFS slate locked.

The accepted replay player snapshots persist the resulting blended means, so
this is not a display-only issue. It affects all historical score evidence in
prop-covered seasons, including the current K=1/CE/role v2 comparison. Shared
projection leakage does not make a relative lineup result automatically safe:
changed player means alter candidate feasibility/ranking, simulated worlds
and portfolio selection.

The live policy mechanism itself is not declared unusable: an early/late
freezer executed before the common lock sees legitimately current lines. The
historical evidence used to choose that policy must nevertheless be rebuilt,
and live reads must fail closed against any snapshot written after lock.

## Availability-only audit

No realized player score or lineup result was queried to define the repair.
The audit joined standard prop names to the accepted K=1 source snapshot and
computed the common lock independently from `raw.schedules`, using the exact
corrected replay universe: regular-season Sunday games starting from 1 p.m.
through before 7 p.m. Eastern.

| Season | old covered player-weeks | used post-lock close | honest pre-lock coverage | lose all market rows |
|---:|---:|---:|---:|---:|
| 2023 | 5,359 | 1,842 | 3,518 | 1,841 |
| 2024 | 5,256 | 1,788 | 3,639 | 1,617 |
| 2025 | 5,141 | 1,716 | 3,826 | 1,315 |

The table contains a usable earlier snapshot for only 1/171/401 of the
affected player-weeks in 2023/2024/2025. Most late-game players therefore
need the existing model-only fallback unless a separately approved historical
common-lock backfill is acquired. Reduced historical market coverage is less
faithful to 2026 live availability but is honest; post-lock lines are not an
acceptable substitute.

## Frozen correction

The standard prop reader will:

1. derive each season/week's common lock from `raw.schedules` with the same
   regular-season, Sunday, `13:00 <= gametime < 19:00` predicate as replay;
2. parse every prop `snapshot_ts` as a timestamp and retain only rows strictly
   earlier than that common lock;
3. among those rows, select the latest row per season/week/bookmaker/market/
   player/point/outcome, so a valid closer supersedes an opening row without
   using arbitrary input order;
4. preserve the existing de-vig, book averaging, name resolution and
   model-only fallback, while consolidating multiple prop aliases that resolve
   to one GSIS id by averaging within market and then summing distinct markets;
   and
5. expose source snapshot/cutoff counts in logs so future coverage drift is
   visible.

The Sunday 1 p.m. lower bound is required: a London game must not become the
common lock for the domestic main slate. The strict `<` rule also applies to
live reads, preventing a post-lock ingest from changing an already locked
book.

The implementation audit also exposed 21 duplicate `(season, week, gsis_id)`
outputs across 2023--2025: alternate name spellings were resolved only after
market totals were aggregated, and replay then kept one by input order. The
corrected reader now fulfills its documented unique player-week contract and
combines those aliases deterministically without looking at outcomes.

Offline fixtures must cover early, late, London, opening/closing, no-coverage,
TD-only and name-resolution cases. Full Cloud Build validation and an
immutable one-week replay smoke precede any panel.

## Revalidation order

All pre-correction historical score panels remain preserved but are
point-in-time-ineligible for new decisions. On one immutable corrected image:

1. rebuild mechanically accepted true-80 K=3 and K=1 base controls;
2. apply the current highest-tail law to K=1 versus K=3 without restoring the
   superseded season-sign veto;
3. rebuild the K=1 CE12/boom28 fallback only if K=1 remains the tail-first
   base; and
4. rebuild the twelve-role added-budget union against that corrected CE
   source before retaining v2 as the Week 1 policy.

Every panel must use all six corrected Sunday-main seasons, exact 80-entry
books, immutable inputs/artifacts and the existing mechanism audits. Do not
copy unaffected old-season rows into a new panel or infer a corrected score
from projection deltas. If K=1 or the role union no longer wins the revised
tail-first comparison, update the live policy to the strongest corrected arm.

The tracked runner freezes panel IDs and settings in
`scripts/prop_lock_rebaseline.sh`: corrected K3/K1 controls first, followed
only after acceptance by K1 CE12/boom28 and then its twelve-role added-budget
union. Every preflight uses 2024 so it exercises the corrected market reader.

No Odds API quota is authorized by this repair. A future common-lock backfill
would be a separate costed data-acquisition decision.

## Validation and execution log

Exact generation commit `8677d21` passed Cloud Build
`3470d0d4-df09-4776-96e8-eaf5a76d0243`: 729 tests passed, 2 skipped. The
validated immutable digest is
`sha256:215a6729b66980310cfad3f63b06a7c25ce4dcf2fa2b6949a04a5c9afa337221`.

Corrected K3 2024 preflight `replay-lockk3-smoke-tmjcp` passed from that
digest. It logged 15,007 excluded post-lock rows, 30,310 retained pre-lock
rows and 3,613/9,601 replay players receiving an honest market blend, then
completed the full one-week 80-entry path. The six K3 executions are
`replay-lockk3-2019-mf5jk`, `replay-lockk3-2021-b8w7x`,
`replay-lockk3-2022-zsjcj`, `replay-lockk3-2023-dzhqz`,
`replay-lockk3-2024-7dqbl`, and `replay-lockk3-2025-n95bb`.

K1 2024 preflight `replay-lockk1-smoke-zgm9n` passed from the same digest and
reproduced the exact common-lock coverage audit. Its six executions are
`replay-lockk1-2019-65m5t`, `replay-lockk1-2021-qwvqg`,
`replay-lockk1-2022-gsddd`, `replay-lockk1-2023-75d9m`,
`replay-lockk1-2024-9hlf4`, and `replay-lockk1-2025-nj6sn`. Both control
panels are now fully launched. Durable manifests are tracked under the
corresponding `reports/panel-runs/` panel directories; do not inspect partial
scores.
