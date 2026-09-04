# PREREG-064 corrected market extract and receiver/defender role-field audit

**Date:** 2026-09-03  
**Audience:** lab team and production  
**Status:** market input released; role-field question answered from retained
schemas and files  
**Scope:** inputs for the frozen PREREG-064 / experiment 092 development
scoreboard. This changes no scoring law, live book, deployment, or experiment
queue.

## Decision summary

Production has released the corrected common-lock player-prop extract needed
for the market half of 092a. The lab can proceed now.

The role-field audit has a narrower answer than the theoretical vendor
capabilities suggest:

- The **current retained Fantasy Points data** supports receiver Wide/Slot
  alignment, receiver results versus man/zone, opponent team man/zone rates,
  and a receiver-versus-defense matchup grade. It does not contain a defender
  identity on a receiver row.
- The **current retained SIS data** supports defender identity, Wide/Slot
  alignment, coverage workload, and outcomes on targets aggregated against an
  offense. It does not contain the targeted receiver's identity.
- Therefore, current data supports `derived-role`, `team-scheme`, and
  `alignment-workload` evidence. It does **not** support `vendor-role`,
  `vendor-shadow`, observed receiver-defender target pairs, or observed
  receiver-defender route pairs.

The companion machine-readable disposition is
`reports/2026-09-03-prereg064-market-extract-and-role-field-audit.csv`.

## Released market artifact

### Data object

- URI:
  `gs://nfl-2-506823-lab/inputs/prereg064/092a-market-20260903-3ff68e3a/prereg064_common_lock_market_extract.parquet`
- GCS generation: `1788481012223199`
- bytes: `1,073,811`
- SHA-256:
  `59537232cbcaea8fe05de34d83ad4fbbd15c3d3996f75859c350821b1eed5131`
- schema: `prereg064_common_lock_market_extract_v1`
- executable production commit:
  `3ff68e3a2518f3e585c36385c162e04a3189adb5`

### Root manifest

- URI:
  `gs://nfl-2-506823-lab/inputs/prereg064/092a-market-20260903-3ff68e3a/manifest.json`
- GCS generation: `1788481014639648`
- bytes: `3,432`
- SHA-256:
  `a04676c12c97442b5a813ab0ae1ecea6929421371954bc25c13d24d44a438c14`

The manifest binds the exact BigQuery table etags/modification times and query
job IDs, the frozen player-snapshot generation and SHA-256, the executable
commit, cutoff/mapping counts, output identity, and actual-label comparison.
Both objects were created with `if_generation_match=0`.

## What the extract contains

One row represents a source player, bookmaker, market, line, and latest
available snapshot horizon. It includes:

- season, week, Sunday-main slate ID, and common lock in UTC;
- GSIS ID and name-resolution method;
- player position, team, opponent, game, and salary;
- bookmaker, market, line, over/under prices, and side-specific timestamps;
- latest-pre-common-lock tag and hours before lock;
- alternate-ladder flag;
- de-vigged over probability and a per-book statistic/DK-component forecast
  where the available sides support the frozen conversion;
- frozen incumbent projection, model-only projection, and incumbent market
  component; and
- canonical realized component statistics and DraftKings points.

The artifact is outcome-bearing and is only for the already-frozen historical
092 development scoreboard. It must not be used as a pre-lock feature object.

## Boundary and coverage audit

The release reads 2023-2024 because historical props begin in 2023. It contains
DraftKings and FanDuel only.

| Check | Result |
|---|---:|
| Raw source rows | 188,927 |
| Rows retained by the latest-before-common-lock operation | 119,659 |
| Rows excluded at or after common lock | 65,375 |
| Paired output rows | 74,291 |
| Development slates | 36 |
| Player-weeks | 7,270 |
| Alternate-ladder rows | 45,332 |
| Complete two-way pairs | 18,705 |
| Rows with a derived statistic forecast | 32,412 |
| DK actual-label comparisons | 74,291 |
| DK label disagreements | 0 |
| Non-pre-lock output rows | 0 |

The retained snapshot is typically two hours before common lock. For later
games, the latest valid stored observation can be substantially older because
the event-relative close occurs after the shared DFS lock. The
`hours_before_common_lock` field makes that staleness explicit.

This is a 36-slate market read, not a 72-slate market read. The already-running
paid-feature ledger may use 72 slates, but source comparisons must use the
covered cohort and a declared full-policy fallback exactly as PREREG-064 says.

Historical bookmaker-level game-odds snapshots are not available in the same
form: `nfl_raw.odds_snapshots` begins in 2026 and does not retain bookmaker;
the historical schedule table has consolidated game lines without a source
snapshot timestamp. Do not present game-odds source rankings over 2023-2024 as
if this release supports them. The player-prop source/consensus questions are
supported.

## Role-field audit evidence

### Fantasy Points currently retained

The warehouse schemas provide:

- `fantasy_points_alignment_player_l4`: `wide_routes`, `slot_routes`,
  `inline_routes`, `player_wide_share`, source weeks, and support;
- `fantasy_points_receiver_coverage_l4`: receiver results split across overall,
  man, and zone, plus separation;
- `fantasy_points_defense_coverage_l4`: defense man/zone rates; and
- the retained `wrCoverageMatchupExport.csv`: receiver, opponent, routes,
  expected FP/route, coverage grade, and coverage-family splits.

The retained WR coverage matchup file has no cornerback name or identifier and
no receiver-to-corner exposure weight. Even if the vendor's web tool internally
uses hand-charted left/right/slot alignment to derive a WR/CB overlap, those
fields are not present in the file available to the pipeline.

### SIS currently retained

`sis_receiver_copula_player_game` provides `defender_player_id`, defender
name/team, defense, offense, Wide/Slot alignment, coverage snaps, targets,
completions, yards, and touchdowns. The source CSVs show the same grain. They
do not provide the receiver ID/name on a target and do not provide a per-route
receiver-defender assignment.

Consequently, a proposal to calibrate a Fantasy Points receiver-defender prior
using SIS observed pair frequency is not executable from current files. It
would require at least `(receiver_id, defender_id, target/play_id)` from SIS and
a retained `(receiver_id, defender_id, expected_exposure)` from Fantasy Points.
Neither side of that join exists today.

### Production-derived fields already available

The current pipeline does construct:

- `receiver_week_role_pit`: pre-lock WR1/WR2/WR3+ and TE roles based on prior
  opportunity and depth information;
- `defense_receiver_role_concession_pit`: how much an opponent has allowed to
  those derived roles in prior games;
- `defender_alignment_quality_week_pit`: individual SIS defender quality and
  share of the defense's prior Wide/Slot workload, with shrinkage and support;
  and
- `player_matchup_week_pit`: receiver-alignment-weighted defense context and a
  top-two workload-defender summary.

The SQL is explicit that a defender's alignment workload share is not the
probability that the defender covers a named receiver. That distinction must
survive the lab transformation.

## What the lab can evaluate now

Do not wait for per-route data. In 092a-frames, retain three distinct feature
families rather than collapsing them into a fictional assignment:

1. **Team scheme interaction:** receiver prior performance against man/zone ×
   opponent prior man/zone rate. This is supported by current Fantasy Points
   exports.
2. **Receiver-role concession:** pre-lock WR1/WR2/WR3+ role × opponent prior
   concession to that role. This is a production-derived, point-in-time team
   matchup.
3. **Alignment-weighted defender context:** receiver Wide/Slot share × the
   opponent defenders' prior alignment workload and shrunk target results.
   Label `assignment_basis=alignment-workload`; never label it shadow or named
   coverage probability.

These groups can be tested conditionally on incumbent and market forecasts
under PREREG-064's frozen partial-association gate. They should not be summed
into one hand-designed matchup score before that test.

The suggested man-rate-gated named-CB formula is not currently supported
because the retained SIS defender rows do not include defender coverage scheme.
Use the team scheme interaction and alignment-weighted defender context as
separate terms unless a new source supplies the missing joint fields.

## Acquisition path, without blocking 092

An operator-provided research memo reports that richer Fantasy Points web-tool
overlaps may be derived rather than observed, SIS may expose more target-level
detail by commercial agreement, PFF offers per-snap assignment feeds, and FTN
offers WR/CB and shadow products. Those are source leads, not facts established
by the current warehouse audit.

If acquisition is pursued, request a sample schema before paying. The minimum
useful fields are receiver ID, defender ID, game/play or target ID, assignment
or exposure weight, Wide/Slot/left/right, man/zone, shadow/travel indicator,
timestamp/as-of semantics, and sample window. A new source must first pass
identity, point-in-time, coverage, and missingness audits; it does not reopen or
delay 092a.

## Lab action

1. Reopen the exact Parquet and manifest generations above and verify their
   SHA-256 values.
2. Run 092a-market on the 36 covered development slates, co-reporting coverage
   and the declared fallback policy.
3. Record the role audit as `vendor-role=unsupported` and
   `vendor-shadow=unsupported` for current data.
4. Keep the three supported scheme/role/alignment groups separate in the paid
   metric ledger and apply the frozen conditional gate.
5. Do not wait for PFF/FTN/SIS/FP commercial follow-up to complete 092a.

This closes both items production owed the lab: the corrected extract and the
role-field audit.
