# Fantasy Points matchup staging and loader incident plan

Branch: `fix/fantasy-points-matchup-staging-20260921`.

The Week 1/Week 2 evidence uses several different words for a vendor export.
This implementation makes the states explicit:

| State | Meaning | Allowed downstream action |
|---|---|---|
| downloaded | Playwright wrote vendor bytes and recorded a file hash | inspect only |
| validated | CSV identity, source season, target schedule, and pre-lock cutoff passed | eligible for staging |
| staged | all three validated reports were copied to an immutable local run with a source-manifest hash | eligible for loader audit |
| consumed | normalized rows were loaded to `nfl_raw.fantasy_points_matchups_live` with a deterministic BigQuery job ID | eligible for a shadow SQL build |
| failed | any gate failed; raw files and failure receipt remain | never consumed |

The prior production matcher already failed closed when any schedule gate did
not pass, but the downloaded CSV could be mistaken for a successful capture.
The new loader preserves that raw artifact and writes `staging-failure.json`;
it never marks a failed report as staged. The destination table is a separate
shadow table and cannot affect Route Share or current model features.

## Contract

`sql/raw/010_fantasy_points_matchups.sql` defines the destination. Each row is
bound to `source_run_id`, target and source season/week, report and row number,
source file/hash, capture time, raw row JSON, and raw team/opponent identity.
The loader uses a deterministic job ID derived from source run and row count;
repeating an identical run is a no-op, while a same logical row with a changed
source hash fails.

`sql/features/017m_fantasy_points_matchups_shadow.sql` is a deliberate identity
surface only. No current `featureset.py`, `project-slate`, or model query reads
it. Activation requires a separately frozen point-in-time efficacy experiment.

## Evidence and tests

The existing capture evidence showed all nine historical Week 1/Week 2-era
matchup runs failed schedule validation. Those downloads must therefore be
described as downloaded bytes, not accepted captures, until their schedule
identity is repaired and the complete three-report set passes. The new fixture
tests cover all three reports, safe staging, hash preservation, failed-run
retention, and idempotent staging. No provider call, BigQuery write, or Route
Share import was run.
