# Fantasy Points live matchup staging contract (for review as one set)

Branch `research/2026-09-paid-source-preflight`. Review set: this document,
`sql/raw/010_fantasy_points_matchups_weekly.sql`, `sql/research/fp_matchup_shadow_tables.sql`,
`src/nfl_dfs/ops/fantasy_points_matchups.py`, `src/nfl_dfs/ingest/fantasy_points_matchups_weekly.py`,
`src/nfl_dfs/research/fp_matchup_shadow.py`, `src/nfl_dfs/ops/fantasy_points_matchup_status.py`,
and the tests `tests/test_fantasy_points_matchups.py`, `tests/test_fantasy_points_matchups_weekly.py`,
`tests/test_fp_matchup_shadow.py`, `tests/test_fantasy_points_matchup_status.py`,
`tests/test_fp_matchup_ddl.py` (DDL and code columns asserted equal). Background and root causes:
`reports/2026-09-21-fantasy-points-matchup-capture-incident.md`.

## 1. Stages and statuses

| Stage | Writer | Status recorded | Where |
|---|---|---|---|
| download | capture | `downloaded` (one entry per attempt) | run `status-ledger.json`, manifest attempt record |
| validate | capture | `validated` / `archived`; `rejected` with a class | manifest attempt record, ledger |
| stage | loader | `staged` (bound to the validated hash) | ledger, `staging-receipt-{report}.json`, `nfl_raw` rows |
| consume | shadow join | `consumed` (bound to the validated hash) | ledger of each capture the join selected |

A run-level `failed` manifest is never a capture; a report is stageable only if it is in the
manifest's `validated_reports` (schema 2) or a seal names it (Week 1). The ledger refuses to skip a
stage and refuses a later status whose hash differs from `validated`.

## 2. Capture manifest (schema 2)

Per attempt: `key`, `attempt`, `status` in {`downloaded`, `rejected`, `validated`, `archived`},
`path` (`{key}.attempt-NN.csv`), `sha256`, `bytes`, `retrieved_at_utc`, `vendor_schedule_week_control`
(`on_load`/`after_select`/`after_apply`: selected week and Week(s) scope), `values_request`,
`schedule_gate`, `source_seasons`, `source_regime`, optional `rejection {failure_class, detail}`,
optional `archive_uri`/`archive_error`. Run level: `validated_reports`, `rejected_reports`
(terminal class and attempts), `schedule_gate_failures`, `status_counts`, `status`, `failure_class`,
`failure_detail`. Failure classes: `vendor-week-unavailable`, `vendor-week-not-retained`,
`control-missing`, `history-scope-not-default`, `values-contract`, `no-rows`, `schedule-gate`
(the only retriable rejection), `export-contract`, `source-regime`, `archive`, `after-kickoff`,
`browser`.

## 3. Staging tables (`nfl_raw`, DDL `sql/raw/010_fantasy_points_matchups_weekly.sql`)

`fantasy_points_qb_coverage_matchup_weekly`, `fantasy_points_wr_coverage_matchup_weekly`,
`fantasy_points_line_matchup_weekly`. One row per vendor row per capture.

* **Append key** `(season, target_week, report, source_sha256, source_row)`: a pure function of the
  export bytes. Re-running the loader on the same export appends nothing; a second capture of the
  same target week (different bytes) appends beside the first. Loads use a deterministic BigQuery
  job id per (report, week, hash) so an ambiguous client return resumes instead of double-appending.
* **Identity columns:** `team`, `opponent` (normalized, reconciled to the scheduled pair),
  `identity` (gsis id or `UNRESOLVED:name:pos:teams`, as of staging), `gsis_id`,
  `resolution_status`, `vendor_name`, `normalized_name`, `vendor_team`, `canonical_teams`,
  `vendor_pos`, `pos`, `games`, `source_season`, `source_regime`.
* **Metrics:** the vendor's grouped headers as `group__metric` FLOAT64 (QB 25, WR/TE 31, OL/DL 12);
  blank or `-` cells are NULL; any other non-numeric cell fails the import; header drift fails the
  import (frozen `EXPECTED_HEADERS`).
* **Lineage:** `source_file`, `source_retrieved_at`, `source_run_id`, `source_attempt`,
  `first_kickoff_utc`, `capture_ref` (run id or seal file name), `archive_uri`, `ingested_at`.
* **Gates re-derived at load time, never trusted from the manifest:** kickoff and scheduled pairs
  from `nfl_raw.schedules`; sha256 and byte count of the file; frozen headers; schedule pairs; source
  regime; retrieval strictly before kickoff; the export file's modification time before kickoff and
  not after the recorded retrieval (a copy must keep mtime); in the active-season regime, games played
  ≤ target week − 1; `archive_uri` equal to the hash-addressed object for the derived digest and, on
  write, present in GCS with the sealed generation when one is named.
* **Inputs:** a schema-2 run directory, or the Week-1 seal (`--output-root` locates member runs).
  `--allow-partial` stages the accepted reports only and lists the rest with a reason; without it a
  missing or unarchived report refuses the whole import.
* **Types:** DDL is applied (`CREATE TABLE IF NOT EXISTS`) before the first load; the loader never
  autodetects. Integer columns are loaded as nullable Int64.

## 4. Shadow tables (`nfl_features`, DDL `sql/research/fp_matchup_shadow_tables.sql`)

`fp_matchup_shadow_qb_coverage_week`, `fp_matchup_shadow_wr_coverage_week`,
`fp_matchup_shadow_line_week`. One row per vendor identity per target week.

* **Selection:** among staged rows for (season, target_week), keep the latest capture per vendor
  identity `(report, team, opponent, normalized_name, vendor_pos)` whose `source_retrieved_at` is
  strictly before the week's first kickoff read from `nfl_raw.schedules`. A row at/after kickoff
  raises `MatchupLeakageError`; nothing is dropped silently. `pit_lag_hours` and
  `captures_available` are recorded.
* **Identity resolution** happens once here from one `rosters_weekly` snapshot (weeks ≤ target), so
  a player who becomes resolvable between captures is one row, never two.
* **Append key** `(season, week, report, source_sha256, source_row)`; append-once.
* **Not activated:** `models/featureset.py`, `sql/features/*.sql` and `inference/` do not name any of
  the six tables (test-asserted); the DDL lives under `sql/research/`, which the feature build does
  not glob. Activation is a separate reviewed change with a frozen efficacy study.
* `--output-root` makes the join record `consumed` on the ledgers of the captures it selected;
  without it the audit says the ledgers were left alone.

## 5. Status view

`python -m nfl_dfs.ops.fantasy_points_matchup_status --output-root fantasy-points/automated` reads
every run directory and reports per report the furthest stage reached (`downloaded`, `gate_passed`,
`validated`, `staged`, `consumed`) and the rejection classes; failed runs never count as captures.

## 6. Unchanged

`ingest/fantasy_points_route*.py` (Route Share), `ops/weekly_vendor_data.py`, production `main`.
