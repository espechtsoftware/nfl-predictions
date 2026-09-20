# Production paid-source update review

**Reviewed:** production `origin/main` at `9afb1784` and its preceding SIS/Fantasy Points commits (`cf336fe5`,
`ee5c9085`, `594a8741`, `c4e7a9ad`). This is a static code and handoff review. I did not read current-week outcomes or
change production.

## What the updates actually do

The Fantasy Points correction is valid and useful: the Week-1 collector's run-level `failed` status had been read as
if every report failed, although the per-report state was `captured`. The durable Week-1 seal says the WR and OL/DL
reports passed the 32-pair schedule gate and the QB report remained short one directional pair. The capture is archived
as hash-addressed CSVs in GCS. The collector has no BigQuery load path and no production feature join for these live
matchup reports; `src/nfl_dfs/ops/fantasy_points_matchups.py` only validates and archives them. They therefore do not
affect the Sunday scores or selection. This is consistent with the existing paid-source ladder finding that the
annotations reshuffled selected rosters without improving points, but the live matchup capture itself has not been
tested as a production feature.

The new SIS loader is a sensible separation from the frozen historical importer. It reuses the audited position-based
parser, verifies each artifact's manifest hash and identity universe, requires all six report families, joins them
one-to-one, and refuses a pre-existing `(season, week)` row set. The production handoff reports 32 Week-1 team-game
rows and six per-report source hashes in BigQuery. A source table read is used by research SIS analyses and TabPFN
shadow generators; no `sql/features/` query reads it, so this load does not alter the current Sunday build.

## Findings to fix before relying on the weekly SIS load

1. **The new loader drops the table's normal source identity.** The frozen `read_tranche` path adds
   `source_run_id = "sis-team-context-tranche-1-v1"` and `ingested_at` through its write-once helper. The new
   `scripts/sis_load_inseason_week.py::build` path returns the merged frame without either column and calls a raw
   `WRITE_APPEND`. If the existing columns are nullable, the 2026 rows have null `source_run_id`; if they are required,
   the claimed load would fail. Either outcome needs an explicit check. A weekly capture should have a distinct,
   content-bound run ID (for example, a run ID derived from season/week and the six manifest hashes), an ingestion
   timestamp, and a durable load receipt.

2. **Completeness is not enforced.** The six reports must agree with one another, but the code never checks that their
   common universe is the expected Week-1 32 team-game keys (or a trusted schedule-derived universe for later weeks).
   Six exports with the same missing team would pass. Require and record the expected schedule universe before writing.

3. **The append is not create-once under a race or ambiguous client return.** A count query followed by
   `WRITE_APPEND` can be interleaved by two invocations, and the loader does not pass a deterministic BigQuery `job_id`
   or verify the inserted key/hash identity after the write. The existing write-once helper and `bq.load_dataframe` job
   retry contract provide the needed pattern; reuse or adapt it for a per-week identity rather than relying on the
   preflight count.

4. **The promised weekly cadence is not wired to a caller.** A repository search finds the new loader only in its own
   script and the defect/handoff prose. The Wednesday `weekly_vendor_data` workflow still captures the vendors and skips
   the historical SIS pass-tail until its documented start; it does not invoke this post-game loader. Either add an
   explicit after-games invocation and receipt to the cadence, or describe this as a manual research load instead of
   saying it is part of the weekly cadence.

These are provenance and operations issues, not evidence that the Week-1 rows are numerically wrong. They should be
closed before using the table as a source-bound experiment.

## Recommended next tests and product decisions

- Add a fixture test for six synthetic Week-1 artifacts: one missing common team-game key must fail; all six manifests
  must produce a distinct run ID, non-null source identity, exact 32-key universe, and per-report hash set.
- Add a mocked BigQuery test for dry-run, successful create-once load, ambiguous retry, and second identical invocation.
  The receipt should include table, season/week, input hashes, job ID, output rows, and post-write key/hash counts.
- Keep the live Fantasy Points matchup CSVs in the raw archive, but do not imply they influence lineups until a separate
  point-in-time feature join is built. The next paid-source shadow should run three arms on the same books: current
  production, SIS team context joined with a strict prior window, and the Fantasy Points matchup features where the
  report passed its schedule gate. Compare player-level forecast residuals, candidate admission, book membership, and
  first-entry order; evaluate all arms on held-out slates before any adoption.
- Do not change this Sunday's production path for either source. The current evidence supports treating SIS and Fantasy
  Points live matchups as research/archive inputs while the lineage and consumer paths are repaired. Renewal should be
  decided from the existing paid-source ladder plus the outcome of that properly wired shadow, not from successful
  browser capture alone.
