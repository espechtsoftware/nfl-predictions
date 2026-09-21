# Fantasy Points live matchup capture: incident note and repair (2026-09-21)

Branch `research/2026-09-paid-source-preflight` (workstation agent, implementation owner;
lab agent reviews). Nothing here edits production `main`, the Route Share path, or
`sql/features/`. Licensed vendor bytes stay under `fantasy-points/` and GCS; none are
committed.

## 1. What happened

**Week 1 (2026-09-09, nine capture runs, every run-level status `failed`).** The vendor
answered the same "2026 Week 1" request with two different schedules minutes apart. In
the raw exports on disk, Arizona's QBs (Brissett, Murray) carry `OPP = CAR` at 19:01Z,
19:31Z and 19:40Z and `OPP = LAC` at 19:37Z; Carolina's QBs flip between `ARZ` and
`CHI` the same way. The schedule gate (`validate_matchup_pairs`) rejected each stale
response correctly. Because the three reports are fetched one after another, a run
could pass one report and fail the next, so no single run ever produced three
passing reports. The seal `reports/2026-09-09-week1-fantasy-points-live-matchup-
capture-seal.json` later assembled a complete set from independently validated
members (QB from run 193712Z, WR and OL/DL from 193116Z), all archived to
`gs://nfl-predictions-503414-raw/licensed/fantasy-points/live-matchups/season=2026/
week=01/sha256=.../`. Nothing ever loaded them into BigQuery: the collector had no
staging path. The 2026-09-18 workstation trace read the run-level status and reported
"0 ok"; the per-report state was `captured` with `schedule_gate.passes = true` for
the sealed members.

The team-code aliasing was not the cause. `ARZ/BLT/CLV/HST` map through the existing
`TEAM_MAP`; the twelve composite cells per WR export (`"DAL, ARZ"`, `"NO, BUF"`, ...)
reconcile whenever the single-team pair exists and surfaced only when Arizona's
vendor opponent was itself wrong.

**Week 3 (2026-09-21 02:54Z, the Wednesday-style run executed on Sunday night).**
`Schedule Week` offered `3`, the selection was accepted, and after Apply the control
showed `2` again: the vendor had not opened Week 3. The old manifest recorded only
`RuntimeError: Schedule Week control does not show 3`, with `reports: []`, so it
could not be told apart from a missing option or a changed label.

## 2. Repair (this branch)

### Capture `src/nfl_dfs/ops/fantasy_points_matchups.py` (manifest schema 2)

* **Bounded re-apply per report** (`--max-attempts`, default 3). A schedule-gate
  rejection re-navigates and re-applies; every attempt's export stays on disk as
  `{key}.attempt-NN.csv` with its own record (`rejected` with `failure_class` and the
  gate output, or `validated`/`archived`). Other failure classes stop immediately.
* **Vendor control state recorded** per attempt: `on_load`, `after_select`,
  `after_apply` (selected week, history scope). Typed `failure_class` on the run:
  `vendor-week-unavailable` (option absent, options listed), `vendor-week-not-retained`
  (Week-3 case), `control-missing`, `history-scope-not-default`, `values-contract`,
  `no-rows`, `schedule-gate` (the only retriable rejection), `export-contract` (the
  export could not be parsed: vendor header drift, unknown team, empty table; no
  re-download), `source-regime`, `archive`, `after-kickoff`, `browser`. The manifest's
  `rejected_reports` carries the terminal class and the real attempt count per report.
* **One clock** drives the start gate, every attempt's `retrieved_at_utc` and the two
  kickoff gates (`clock` parameter), so the offline suite is frozen in time rather than
  expiring at the fixture's kickoff.
* **Team aliases** extended for matchup exports only (`JAC->JAX`, `WSH->WAS`,
  `LAR->LA`) on top of the untouched Route Share `TEAM_MAP`.
* **Retention ledger** `status-ledger.json` per run with the order
  `downloaded -> validated -> staged -> consumed`; a status cannot be recorded before
  the previous one, `downloaded` accumulates attempts, the later statuses bind to one
  hash. `manifest.status_counts` and `validated_reports` summarise the run.
* The browser surface is a driver object (`PlaywrightMatchupDriver`); tests inject a
  scripted fake. The gate, regime, kickoff and archive laws are unchanged.

### Staging loader `src/nfl_dfs/ingest/fantasy_points_matchups_weekly.py` (new)

* Input: a schema-2 run directory, or a seal (Week 1). **The first kickoff and the
  scheduled pairs come from `nfl_raw.schedules` at load time**; the manifest's or
  seal's copies must agree or the import stops (the first review found the loader
  comparing two manifest fields to each other). Every other gate is re-derived from
  the bytes: hash, byte count, frozen group-qualified headers, schedule pairs, source
  regime, retrieval strictly before kickoff. Retrieval time has no warehouse authority,
  so it is cross-checked against the export file's own modification time (written
  before kickoff, not after the recorded retrieval; a copy must preserve mtime) and,
  for active-season exports, the games-played column (no more than target week − 1).
  A schema-1 run directory is refused with a pointer to the seal path.
* Tables (`nfl_raw`): `fantasy_points_qb_coverage_matchup_weekly`,
  `fantasy_points_wr_coverage_matchup_weekly`, `fantasy_points_line_matchup_weekly`.
  Columns: identity (`season`, `target_week`, `report`, `identity`, `team`,
  `opponent`, `gsis_id`, `resolution_status`, vendor fields), the vendor metrics as
  `group__metric` floats, and lineage (`source_sha256`, `source_run_id`,
  `source_attempt`, `source_retrieved_at`, `first_kickoff_utc`, `archive_uri`,
  `capture_ref`, `ingested_at`).
* Append key `(season, target_week, report, source_sha256, source_row)`, a pure
  function of the bytes: re-running on the same export appends nothing even when the
  roster snapshot has changed; a second capture of the same week appends beside the
  first (every pre-lock snapshot kept). Loads carry a deterministic BigQuery job id per
  (report, week, hash) so an ambiguous client return resumes rather than
  double-appends. `--write` requires the archive URI to be the hash-addressed object
  for these exact bytes **and** to exist in GCS (generation compared when the seal
  names one); a report without an archive is refused, or skipped and listed under
  `--allow-partial`. Ledger transitions are prepared before any load, so a seal whose
  members share one run directory (the real Week-1 shape) stages cleanly.
* Player resolution reuses the Route Share resolver against `rosters_weekly`
  (weeks <= target) and is stored as an attribute of the staged row (as of staging);
  the shadow join re-resolves from one snapshot at build time. Unresolved identities
  stay `UNRESOLVED:name:pos:teams`, never guessed. Ledger -> `staged` (bound to the
  validated hash); a `staging-receipt-{report}.json` is written beside the manifest.

* **Typed DDL is the contract:** `sql/raw/010_fantasy_points_matchups_weekly.sql` (applied by
  `deploy/setup_gcp.sh` and by the loader before its first load; the loader never autodetects a
  schema; integer columns load as nullable Int64). `tests/test_fp_matchup_ddl.py` asserts the DDL
  columns equal the loader's output columns, in order. Both DDL scripts dry-run compile in BigQuery.
  The reviewable contract in one page: `reports/2026-09-21-fantasy-points-matchup-staging-contract.md`.

### Shadow join `src/nfl_dfs/research/fp_matchup_shadow.py` (new, not activated)

* Reads the three staging tables for one target week, keeps the latest capture per
  **vendor identity** (report, team, opponent, normalized name, position; stable across
  captures) strictly before that week's first kickoff (from `nfl_raw.schedules`, never
  from the rows), resolves player ids once from one roster snapshot, and writes
  `nfl_features.fp_matchup_shadow_{qb_coverage,wr_coverage,line}_week` with
  `pit_lag_hours` and `captures_available`. A row at/after kickoff raises
  `MatchupLeakageError`; nothing is dropped silently. Append-once on
  (season, week, report, hash, source row). With `--output-root`, the ledger of each
  capture the join actually selected records `consumed` (bound to that run's own
  validated hash); without it the audit says the ledgers were not touched.
* `featureset.py`, `sql/features/*.sql` and `inference/` do not reference any of
  these tables (a test asserts it). Activation is a separate reviewed change. Typed DDL:
  `sql/research/fp_matchup_shadow_tables.sql` (under `sql/research/`, which the feature build does
  not glob; applied by the join before its first load; columns asserted equal to the builder's).

### Status view `src/nfl_dfs/ops/fantasy_points_matchup_status.py` (new, read-only)

Walks every `*__2026-live-matchups-v1__week-NN` run directory and reports, per report,
the furthest stage reached: `downloaded` (bytes on disk), `gate_passed` (the run's own
schedule-gate record), `validated` (schema-2 `validated_reports` or a ledger entry),
`staged`, `consumed` (ledger entries). A failed run is never counted as a capture and a
schema-1 `captured` record counts as `gate_passed` only. On this host tonight:
Week 1, 9 runs all failed, downloads 8/7/5 (QB/WR/OL), gate passes 3/2/2, validated/
staged/consumed 0; Week 3, 1 run failed, nothing downloaded. This is the PAID-001
separation the lab audit asked for.

### Adversarial review (2026-09-21, four lenses, two skeptics per finding)

22 raw findings, 15 survived refutation, all fixed above and each covered by a test:
loader trusted manifest kickoff/pairs (now schedule authority + file-time + games
checks); real Week-1 seal would have failed after loading (ledger prepared before
loads, per member); append key depended on roster resolution (now bytes only);
`archive_uri` trusted verbatim (layout + existence + generation checks); source-regime
and parse failures misfiled as schedule-gate and retried (typed `export-contract`,
terminal class and true attempt count); wall-clock leaks in the capture (one clock);
shadow stamped the operator's run dir `consumed` regardless of selection (selected
captures' ledgers, bound hash); identity drift across captures duplicated shadow rows
(vendor identity + build-time resolution); ledger de-duplicated attempts by hash
(keyed by attempt); the vendor-week-unavailable classification was only exercised by
the fake (driver unit tests with a stubbed page). Seven findings were refuted.

## 3. Evidence

* Tests (offline, mocked driver and warehouse): `tests/test_fantasy_points_matchups.py`
  21, `tests/test_fantasy_points_matchups_weekly.py` 15, `tests/test_fp_matchup_shadow.py`
  7, `tests/test_fantasy_points_matchup_status.py` 1; neighbours
  `test_weekly_vendor_data.py` 6, `test_fantasy_points_route_weekly.py` 5,
  `test_fantasy_points_downloads.py` 26 still pass.
* Reality contact (read-only, `--write` not passed) against the real Week-1 seal and
  the member runs on this host: all three members re-validate; QB 61 rows (58
  resolved, 3 unresolved: Russell Wilson, Philip Rivers, Jake Browning), WR/TE 284
  rows (250 resolved, 34 unresolved, all prior-season players absent from the 2026
  Week-1 rosters, e.g. Tyreek Hill, DeAndre Hopkins, Zach Ertz), OL/DL 32 rows;
  32 teams in each; 12 multi-team cells reconciled; kickoff 2026-09-10T00:20Z read from
  `nfl_raw.schedules`; every export file's modification time equals its recorded
  retrieval to the second; no table existed; nothing written.

## 4. Operator steps (none run by me)

```
# Retention status of every capture on disk (read-only):
python -m nfl_dfs.ops.fantasy_points_matchup_status --output-root fantasy-points/automated
# Stage the sealed Week-1 set (from a checkout of this branch):
python -m nfl_dfs.ingest.fantasy_points_matchups_weekly \
  --input reports/2026-09-09-week1-fantasy-points-live-matchup-capture-seal.json \
  --target-week 1 --output-root fantasy-points/automated --write
# Week 3, once the vendor opens the week (the failure class tells you when it has not):
nfl-weekly-data run --week 3 --skip-odds --no-login-if-needed   # capture, archive=True
python -m nfl_dfs.ingest.fantasy_points_matchups_weekly \
  --input fantasy-points/automated/<run id> --target-week 3 --write
python -m nfl_dfs.research.fp_matchup_shadow --week 3 --write \
  --output-root fantasy-points/automated
```

## 5. Open items (lab agent)

* Review the schema contract above and the append key before the first `--write`.
* Decide whether the weekly runner should call the loader after the capture step
  (`ops/weekly_vendor_data.py` is unchanged here on purpose).
* Whether the shadow join should be graded against Week-3 outcomes, and by whom.
