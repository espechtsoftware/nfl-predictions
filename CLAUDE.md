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


## Handoff state (2026-07-25, written after local machine instability)

Local box crashes under load (HYPERVISOR_ERROR; .wslconfig caps applied,
unproven). Strategy: BigQuery queries and tests run locally; ANY heavy compute
(model training, replays, ablations) runs on Cloud Run ONLY — local
LightGBM training has frozen the machine repeatedly (2026-07-26).

- **Tournament construction is the ONLY mode** (user plays GPPs only,
  35-40 entries): every lineup (classic + showdown) requires >=1 sub-$4k
  punt valued at p90; chalk-fade penalty (LEVERAGE_PENALTY x naive
  ownership) applies to OUR objective only, never the simulated field
  (proj_tourney vs proj in replay slates); stack defaults QB+2 catchers
  +1 bring-back; replay prints winning-line tail (>=237 avg / >=194 min
  2025 Milly lines, reports/2025-milly-winners.csv). PUNT_BOOM=2 is an
  adopted default on both replay and app paths (Addendum 37: archetype
  punt tilt, the only all-metric win of the program; 0 disables).
- **Committed but UNVALIDATED**: the tournament-mode replays (classic
  gpp + showdown, season 2025) never completed — machine crashed. First
  task: run `nfl-dfs replay --season 2025 --contest gpp` and
  `nfl-dfs replay-showdown --season 2025 --entries 40`; compare tail vs
  pre-tournament baseline (best mean 158.5, 2/17 weeks >=190).
- **Open analysis — DONE 2026-08-01** (Addendum 24 in
  reports/2026-07-25-system-study.md): next-man-up detector flags ~1/3 of
  player punt booms; dominant winning-punt archetypes are cheap starting
  TEs (depth_rank 1, nothing vacated) and DSTs (7/17). Follow-up ideas
  recorded there (depth-rank transition signal; punt-pool composition).
- Everything else: reports/2026-07-25-system-study.md (addenda 1-4) and
  the README deficiency log are current.
