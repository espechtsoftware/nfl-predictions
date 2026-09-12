# R6 matchup seven-pack outcome-blind support preflight

**Date:** 2026-08-27  
**Disposition:** support/schema evidence only; no source-pack or analysis authority

## Boundary

This preflight inspected BigQuery schema metadata and aggregate source support
only. It did not select a player-stat value, matchup value, lineup, realized
lineup score, contest result, winner label, selector result, or treatment
effect. It performed no create/update/delete, GCS publication, graph mutation,
deployment, IAM census, scoring, promotion, or production-policy action.

The target is the frozen seven-pack registry in
`corpus_r6_matchup_source_v2.py`:

1. schedules, 2022--2025;
2. weekly player stats, 2022--2025;
3. legacy depth, 2022--2024;
4. dated depth snapshots, 2025;
5. PFR defense plus snap counts, 2022--2025;
6. normalized Fantasy Points inputs, 2022--2025; and
7. normalized SIS inputs, 2022--2025.

All reads used project `nfl-predictions-503414`, location `US`, dataset
`nfl_raw`, GoogleSQL, and the current warehouse relations. These mutable
relations remain retrospective inputs. This preflight does not upgrade them
to immutable source authority or contemporaneous-prelock evidence.

## Required-column support

The schema-only check compared every direct raw column needed by the frozen
positive-row schemas with `nfl_raw.INFORMATION_SCHEMA.COLUMNS`. All twelve
relations were present and every required direct column was present:

| Relation | Required direct columns | Current columns | Missing |
|---|---:|---:|---|
| `depth_charts` | 9 | 15 | none |
| `depth_charts_snapshots` | 5 | 12 | none |
| `fantasy_points_alignment_player_l4` | 7 | 25 | none |
| `fantasy_points_defense_coverage_prior` | 4 | 13 | none |
| `fantasy_points_receiver_coverage_prior` | 5 | 38 | none |
| `fantasy_points_route_share` | 5 | 16 | none |
| `pfr_advstats_def` | 12 | 29 | none |
| `schedules` | 8 | 46 | none |
| `sis_receiver_copula_player_game` | 11 | 16 | none |
| `sis_team_run_context_game` | 9 | 79 | none |
| `snap_counts` | 7 | 16 | none |
| `weekly_stats` | 18 | 150 | none |

`kickoff_time_utc` is intentionally derived from `gameday` and `gametime`
under the fixed `America/New_York` conversion already validated by the
component producer. `weekly_stats.fumbles_lost_total` is directly present;
the component columns `sack_fumbles_lost`, `rushing_fumbles_lost`, and
`receiving_fumbles_lost` are also present for an independent equality audit.

## Aggregate period support

The counts below used only `COUNT`, `MIN(season/week)`, and
`MAX(season/week)` after the registry period filters. They disclose no source
values or outcome effects.

| Relation | Rows | Minimum | Maximum |
|---|---:|---|---|
| `schedules` regular season | 1,087 | 2022 W1 | 2025 W18 |
| `weekly_stats` regular season | 72,455 | 2022 W1 | 2025 W18 |
| `depth_charts` | 100,004 | 2022 W1 | 2024 W18 |
| `pfr_advstats_def` | 30,279 | 2022 W1 | 2025 W18 |
| `snap_counts` | 101,290 | 2022 W1 | 2025 W18 |
| `fantasy_points_route_share` | 27,305 | 2022 W1 | 2025 W18 |
| `fantasy_points_alignment_player_l4` | 16,482 | 2022 W5 | 2025 W18 |
| `fantasy_points_receiver_coverage_prior` | 2,093 | 2022 | 2025 |
| `fantasy_points_defense_coverage_prior` | 128 | 2022 | 2025 |
| `sis_receiver_copula_player_game` | 15,477 | 2022 W1 | 2025 W18 |
| `sis_team_run_context_game` | 2,174 | 2022 W1 | 2025 W18 |

The W5 minimum for Fantasy Points alignment is expected and preserves the
registered W1--W4 unavailable law. The 2025 dated depth relation contains
356,931 rows from `2025-08-03T10:09:07Z` through
`2025-12-30T07:19:09Z`; 4,231 rows lack `gsis_id`. The capture must therefore
retain the dated history required for target-game as-of selection while
filtering or explicitly accounting for unresolved IDs. It must not interpret
those missing IDs as players with zero evidence.

## Durable BigQuery job evidence

| Purpose | Job ID | Created UTC | Bytes processed | Cache | Query SHA-256 |
|---|---|---|---:|---|---|
| required-column compatibility | `bqjob_r4ce5dbeed0f7f654_000001a044f5c4f5_1` | 2026-08-27T20:42:32Z | 10,485,760 | false | `f74ad143e5bcddc2260433bc8c16a394d914b687cb38d1af9fd8ebff32656530` |
| kickoff/fumble derivation columns | `bqjob_r793f08176477038_000001a044f6ed6f_1` | 2026-08-27T20:43:48Z | 10,485,760 | false | `b3d37a395f5c24ccf87148a96f3ca1d31d745b7f4341ba9abb3e07e99df514f6` |
| registry-period aggregate support | `bqjob_r1149970383b5b01b_000001a044f7169f_1` | 2026-08-27T20:43:59Z | 10,485,760 | false | `9889dce453ecac829e66719b40ebe5878d90b4bf5bf76e1cbac27f7a418c5908` |
| 2025 dated-depth support | `bqjob_r3bb1db42be82eeb5_000001a044f78548_1` | 2026-08-27T20:44:27Z | 17,972,312 | false | `3a9c3ff05f6c2f20c0d2508df8bf7857acc50527b8dfb6ad2f7a6f3e67ef29f3` |

All four jobs completed with `error_result = null` and `state = DONE`.

## Decision and next gate

There is no schema- or gross-support blocker to constructing the seven global
packs. The next step is not another census. It is a fixed, reviewed capture
operator that:

- renders and records the exact five warehouse extracts;
- projects the two artifact-backed FP/SIS packs with their frozen manifests;
- publishes canonical row objects create-once and exact-reopens them;
- labels every value `retrospective-prior-period-reconstruction` or the more
  restrictive registered evidence class; and
- publishes the upstream release last only after all seven row objects and
  provenance receipts are generation-exact reopened.

This preflight grants no authority to skip the fixed-G0 catalog/candidate
root, real-artifact smoke, exact source capture, or downstream independent
reopen gates.
