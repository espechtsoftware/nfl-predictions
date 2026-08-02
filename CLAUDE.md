# CLAUDE.md

DraftKings NFL DFS prediction and lineup-construction system on free data +
GCP. [README.md](README.md) is the authoritative document: the full design
guide (§0–§14), the Quick start (install, env vars, local usage, deploy),
and the section-to-code map at the top. Don't duplicate it — read it.

## Commands

```bash
source .venv/bin/activate
pytest                      # full suite, runs offline (no GCP needed)
nfl-dfs --help              # every pipeline job as a CLI subcommand
nfl-dfs build-features      # feature SQL + leakage checks (needs GCP auth)
```

Install: `pip install -e ".[dev,app]"` for code work; add `gcp` for
pipeline work. BigQuery is the only database — there is no local-data mode.
Config is env vars only, all read in `src/nfl_dfs/config.py`.

## Layout

- `src/nfl_dfs/` — `ingest/` → `features/` (+ `sql/features/`) → `models/`
  → `inference/` → `optimizer/` / `backtest/`, plus `app/` (FastAPI),
  `graph/`, `trends/`, `analysis/` (archetype clustering), `cli.py`.
  Map with guide sections: README top.
- `sql/` — BigQuery DDL/transforms. `${raw}`, `${features}`,
  `${predictions}`, `${prior_k}` are substituted by `bq.run_sql_file`.
- `tests/` — offline; synthetic player-week panel in `conftest.py`.

## Rules

- **Point-in-time is sacred.** A feature row for week W may only see data
  from weeks < W (windows end at `1 PRECEDING`). The leakage checks in
  `features/leakage.py` run on every `build-features` and must pass; never
  weaken a check to make a build go green — first prove the build is
  actually point-in-time correct.
- **Walk-forward validation only** (by season). Never random splits.
- **Data deficiency log.** Every time we find a gap or quality problem in
  source data (missing seasons, schema drift, unmatchable rows, absent
  fields), add a row to the "Data deficiency log" table in README.md's
  *Known gaps and future enhancements* section — date, deficiency, impact,
  status. It's an append-only decision aid for what to fix or accept later.
- **nflverse schema drifts.** Column renames upstream have already broken
  feature SQL once (see the log). When a build fails on an unknown column,
  check the live BigQuery schema before assuming the SQL is wrong.
- `.gitignore` patterns must stay root-anchored (`/models/`, not
  `models/`) — an unanchored pattern once silently kept
  `src/nfl_dfs/models/` out of git and the package had to be rebuilt from
  its tests.
- Season semantics: `config.current_season()` rolls over in March
  (planning clock); nflverse serves data only for started seasons — clamp
  with `nfl.get_current_season()` when loading (see `ingest/nflverse_job.py`).


## Handoff state (2026-08-03, end of pre-season program)

Local box crashes under load (HYPERVISOR_ERROR): BigQuery queries and
tests run locally; ANY heavy compute (training, replays, panels) runs on
Cloud Run ONLY. The full experiment ledger is
reports/2026-07-25-system-study.md (40 addenda); the September runbook
calendar is in README (season-start table). Auto-memory carries the
user-facing plans (contest mix, week-1 checks, in-season queue).

- **Tournament construction is the ONLY mode** (user plays GPPs: ~40x $5
  qualifier + ~40x $3 tourney + ~4 Milly weekly, generated as separate
  runs per contest field size): mandatory sub-$4k punt valued at p90,
  chalk-fade on OUR objective only, QB+2 catchers + bring-back, punt-boom
  archetype tilt (PUNT_BOOM=2 adopted, both paths). Tail metric = real
  per-week Milly lines (backtest/real_lines.py), not the 194/237 anchors.
- **Validation laws** (hard-won, do not relax): panels or nothing
  (six-season, never single-season); replays are deterministic BUT
  feature-table REBUILDS are not (BQ tie-breaking) — after ANY
  build-features run, every panel must co-run its own CONTROL arm on the
  same table build (2026-08-03 incident: a rebuild silently shifted the
  baseline and nearly mis-judged nine arms); adding ANY feature column
  reshuffles LightGBM tie-breaks (~±5 mean-best "order luck").
- **Env-lever registry**: adopted defaults live in code; every tested
  lever and its verdict is in the study report. Notable off-by-default
  levers validated for QUALIFIER contests (not Milly): SELECT_OBJ=dollars,
  LEV_POS_WEIGHTS (empirical QB:2.08), MAX_QBS/N_QB_VARIANTS, LEV_SHAPE=sqrt.
  Untested-inert: PUNT_VALUE=tail, BIGPLAY (equal tails/+ROI), SIMS 30k
  (live-only candidate).
- **September machinery is pre-built, data-gated**: import-ownership now
  captures per-entry lineups (contest_entries; DK purges exports ~4
  DAYS — download standings Mon/Tue after every slate, non-negotiable);
  `nfl-dfs field-calibration` scores field-sim dupe realism vs real
  entries (RTS benchmarks 0.43/0.72); /market has external-projection
  consensus diff (ETR weekly pass planned Sep 8-9) + accuracy grading;
  lineup cards show Lev% and watch notes; daily backups (s-backup) cover
  all irreplaceable tables.
- Reference clones of public DFS repos live in
  /home/erich/projects/other-nfl-projects (analysis in addenda/memory).
