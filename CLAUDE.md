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


## Handoff state (2026-08-04, Fable program complete — Opus operates from here)

Local box crashes under load (HYPERVISOR_ERROR, 3x on 2026-08-04): BQ
queries and tests run locally; ALL heavy compute on Cloud Run. /tmp dies
on reboot — durable driver scripts + state files live in ~/nfl-panels/
(rerun any driver after a crash; state files make them resume). The full
experiment ledger is reports/2026-07-25-system-study.md (50+ addenda —
READ THE LAST TEN before proposing anything; most "new" ideas are
already tested there). September calendar: README season-start table +
"TabPFN projection cache" runbook block.

- **ADOPTED STACK (all code defaults, no envs needed)**: EW draw shaping
  + PUNT_BOOM=2 + QF (N_QB_VARIANTS=4, OWN_MODEL=fade — fade uses the
  trained ownership booster live) + SCHED features (net_rest_diff,
  body_clock_hour in NUMERIC_FEATURES) + TabPFN marginals
  (TABPFN_MARGINALS default-on; cache = features.tabpfn_projections,
  GPU job `tabpfn-gen`, falls back to EW empirical marginals WITH a UI
  warning when the cache is missing). Tournament-only construction:
  sub-$4k punt at p90, chalk-fade on OUR objective, QB+2+bring-back,
  mandatory sim-mode (503 on failure; sim=false explicit escape).
- **VALIDATION LAWS (hard-won, never relax)**: six-season panels with a
  CO-RUN CONTROL on the same table build (rebuilds shift baselines ±5;
  2026-08-04: 23→18); deterministic replays; walk-forward only; sorted
  feature columns; NEW 2026-08-04: (a) LOSO — adopt only if positive in
  ≥4 of 6 seasons with ≤1 negative (QF FAILED this retroactively — it
  stays on cross-build replication but MUST be re-judged against real
  qualifier standings ~week 3); (b) vacuity checks — byte-identical A/B
  arms mean the lever never fired (stale image, wrong code path, or
  infeasible constraint: MPG3, showdown-fade x2 all caught this way);
  (c) showdown A/Bs need SHOWDOWN_SIM=1 in BOTH arms (the replay
  default is MILP; live default is sim — they diverge); (d) verify the
  deployed image contains the lever (img-probe pattern) before trusting
  an A/B.
- **GPU on Cloud Run works and is cheap** (L4, us-central1,
  --no-gpu-zonal-redundancy, 1h task cap, ~$0.70/hr): jobs `tabpfn-gen`
  (marginal quantiles; TABPFN_UPCOMING=season:week adds the live week —
  run WEEKLY Wed + after every build-features), `tabpfn-comp`
  (component-mean cache, TABPFN_SEASONS + TABPFN_WRITE=append for the
  1h cap), `lem-train`, `lem-rollout`. Sources: scripts/tabpfn_gen/,
  scripts/lem_train/ (versioned after /tmp losses).
- **Off-default levers with pending-or-recorded verdicts**: check
  ~/nfl-panels/review_results.txt + showdown_fade.txt + the ledger's
  final addenda for SCRIPT_FEEDBACK, DIV_TILT, TABPFN_MEAN,
  TABPFN_COMPONENTS, ALT_CEIL (revived post-audit), SHOWDOWN_FADE
  verdicts before touching them. Qualifier-validated-but-HELD:
  SELECT_OBJ=dollars, MAX_QBS — recalibrate on real standings first.
- **September cadence (NO new code should be needed)**: Mon/Tue after
  every slate download contest standings (DK purges ~4 days) →
  import-ownership; Wed tabpfn-gen with TABPFN_UPCOMING; weekly ETR
  CSV to /market (paid pass Sep 8-9); persona shadow
  (scripts/persona_ownership_experiment.py) + env-forecast
  (scripts/env_forecast.py) logged weekly and GRADED before any
  adoption; CQR confidence auto-activates at ≥100 scored rows;
  field-calibration after 2-3 weeks of standings; entries plan per
  contest-mix memory (split entries across 2-4 contests at 30-50 each,
  never <15 — sweet-spot study, reports/entries_study/).
- **September projects that DO need code (design docs only, build only
  if September evidence warrants)**: LEM v2 / GAME_SIM_MODE=lem (gate
  result in lem-rollout logs; road map in ledger), market-implied
  DISTRIBUTIONAL composition (yardage→DK-points convolution — the
  reason MARKET_MARGINALS wasn't shipped), showdown ownership model
  (data too thin until standings accrue), TabPFN ownership/synthetic.
- External review artifacts: reports/external-review-package.md (+
  code companion) — regenerate and re-run the Gemini review after
  meaningful changes; its LOSO rule and fallback-warning finding are
  now law/shipped.
