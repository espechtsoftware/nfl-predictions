# SIS team-context intake

Completed 2026-08-13 from the paid NFL-only SIS DataHub subscription. Raw
licensed CSVs and their local identity manifests remain under gitignored
`sis/team-context-tranche-1/`; no vendor rows are committed to Git.

## Acquisition and completeness

The tracked plan `automation/sis/plans/team-context-tranche-1.json` completed
all 108 planned normal-UI exports using 440 of its hard 500-request ceiling.
It covers 2019 and 2021--2025, three six-week windows per season, and team
Pass Defense, Pass Rush and Blocking Totals/Value. Every artifact passed the
exact submitted API scope, rendered-table row count, downloaded CSV scope,
hash and stable SIS identity checks. No exact-200 capped response was accepted.

The audit-only importer combines the six families into 3,230 team-game rows
covering 1,615 games. Expected rows by season are 2019 `512`, 2021 `544`,
2022 `542`, and 2023--2025 `544` each. Every game has exactly two team rows;
all six report families have the same team-game universe. The importer uses
positional schemas for SIS Blocking because its CSV repeats visible names
such as `Snaps`, `BB`, `Holds`, and `Points Earned`; a normal dictionary CSV
parser would silently discard distinct overall/pass/run columns.

## Private table and recovery

Explicit write-once import created
`nfl-predictions-503414.nfl_raw.sis_team_context_game` with exactly 3,230
rows. It retains numeric SIS team/opponent IDs, human-readable names,
canonical team abbreviations, a two-sided game key, every source SHA-256 and
the source run ID. The table is immutable under this importer unless an
existing table has exactly the same row/run/hash identity.

Daily backup discovery now includes every base table whose name begins
`sis_`. A verification backup created snapshot
`nfl-predictions-503414.nfl_backups.sis_team_context_game_20260813_sisctx`.
The full backup invocation reported no failed tables.

## Modeling contract

For target Week W, only completed SIS game rows with source week strictly less
than W may be aggregated. Same-week rows are outcomes and are forbidden. The
first analysis should compare lagged/shrunk team defense, pressure and
blocking summaries against existing features without outcomes, then measure
walk-forward incremental calibration/tail association. Only small mechanistic
bundles may advance to a preregistered model arm; the raw column set must not
be added wholesale to TabPFN.
