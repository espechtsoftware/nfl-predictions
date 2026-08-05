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



## Handoff state (2026-08-05 final, Fable program complete — Opus operates from here)

Local box crashes under load (HYPERVISOR_ERROR, 5x): BQ queries and
SINGLE targeted test runs are fine locally; NEVER run parallel agents,
parallel pytest, or local sims — ALL heavy compute on Cloud Run. /tmp
dies on reboot — durable driver scripts + state files live in
~/nfl-panels/ (rerun any driver after a crash; state files resume).
The experiment ledger is reports/2026-07-25-system-study.md (89
addenda — READ THE LAST FIFTEEN before proposing anything; most "new"
ideas are already tested, and several early verdicts were RETRACTED
by later audits, so never cite an addendum without checking for a
correction in a later one).

- **SHIPPING BASELINE (HARVEST-FINAL-2, Addendum 87): 27/107 weeks
  best-of-40 >= 194, mean best 179.5, median percentile 14.2%** —
  per-season {2019:5, 2021:3, 2022:3, 2023:4, 2024:6, 2025:6},
  byte-identical to its validating arm across an image rebuild. Every
  future arm is judged against THIS on a same-code-image co-run.
- **ADOPTED STACK (all code defaults, no envs)**: EW draw shaping +
  QF construction (N_QB_VARIANTS=4) + NAIVE-ownership chalk fade
  (OWN_MODEL default "" — the fade itself is +2 twice-proven; the
  trained booster added nothing and left the construction path) + NO
  punt mandate, NO punt-boom boost (deleted at +1/+2; the p90 punt
  VALUATION and $49k salary floor and stack mandate all KEPT —
  true-deletion tests cost tails) + SCHED features + TabPFN marginals
  + MODEL_ENSEMBLE=3 + prop-market blend, now props-first in LIVE
  paths too (parity fix; DK-PPG fallback). Tournament-only
  construction unchanged: chalk-fade on OUR objective,
  QB+2+bring-back, mandatory sim-mode.
- **VALIDATION LAWS (never relax)**: six-season panels, co-run
  control on the SAME image build (RNG stream order changes rebase
  everything — golden-hash parity tests in tests/test_sbi.py now pin
  default draws); LOSO >=4-of-6 with <=1 negative; vacuity checks
  (byte-identical arms = dead lever; env-name typos and column-gated
  levers both happened); post-ensemble AND post-selection law:
  verdicts don't transfer across a changed downstream stage; AUDIT
  BEFORE VERDICT — the fade mislabel, GREEN2 env typo, and TDLEDGER
  season-pooling defect were all caught by instrument/code audit,
  never by the panel number; deletion tests need the env to actually
  gate what its name claims.
- **THE MEASURED FRONTIER (Addenda 83, 87)**: the candidate pool's
  oracle clears 30/107 vs the selected book's 22 (same build) — ~8
  recoverable weeks exist in the pool; the sim cannot rank candidates
  (actual-best at median sim-rank 53/168), so ALL sim-informed
  selector variants are a dead end (LSE/SHARP/coverage triple-null).
  Capture paths: more entries per slate (pool outproduces the book),
  or the decision-focused reranker (needs a non-sim signal).
  cand-oracle log line + candidate persistence
  (predictions.live_candidates) accumulate the training set live.
- **RESEARCH PROGRAM (reports/emerging-technologies-plan.md is the
  spec; reports/september-research-designs.md the queue)**: six
  workstreams BUILT under src/nfl_dfs/research/, adopt-only-as-proven.
  Verdicts so far: GFlowNet GATED OUT (its own cheap-diversity
  baselines beat it — world-argmax +7.9 / Gumbel-MILP +6.8 vs GFN
  +5.4 at equal count); parametric TD coupling BURIED VALIDLY
  (TDLEDGER2 19 vs 27 after all defects fixed); Chronos baselines-win
  (EWM/Kalman better everywhere, worst at cold start); SBI 2-of-3
  params identifiable (synthetic gate passed; walk-forward real-data
  inference is the next step, §6.8 needs listed in ledger); tracking
  v0 SHIPPED (1,384-player trait table + 96.3% high-confidence gsis
  crosswalk at ~/projects/other-nfl-projects/nfl-big-data-bowl-2026/;
  next gate = shadow features on thin-history players; free in-season
  refresh = nflverse NGS weekly aggregates); evidence + online
  conformal built and fixture-proven, data-gated on September news /
  scored rows. September dependence build #1 = Schaake shuffle, gated
  on the variogram instrument (src/nfl_dfs/research/dependence.py).
  PENDING ARM: GUMBEL (N_GUMBEL=20 vs HF2 27) — collect and judge.
- **SHADOW COLLECTORS (all automatic, best-effort, deliberately NOT
  in status.FEEDS)**: predictions.div_shadow (prop-market divergence,
  writes only when props exist; grade with scripts/div_shadow_grade.py
  after 4-6 weeks — pre-registered bar inside), predictions.own_shadow
  (build-time predicted ownership incl. booster column),
  predictions.live_candidates (reranker training set). The config
  manifest (src/nfl_dfs/research/config_manifest.py) must show ZERO
  discrepancies (tests enforce).
- **GPU on Cloud Run works and is cheap** (L4, us-central1,
  --no-gpu-zonal-redundancy, 1h cap, ~$0.70/hr): jobs tabpfn-gen
  (TABPFN_UPCOMING=season:week — run WEEKLY Wed + after every
  build-features), tabpfn-comp, lem-train, lem-rollout. Sources
  versioned under scripts/.
- **September cadence (run-only; NO new code should be needed)**:
  Mon/Tue standings downloads (DK purges ~4 days) → import-ownership;
  Wed tabpfn-gen with TABPFN_UPCOMING; weekly ETR CSV to /market
  (paid pass Sep 8-9); persona shadow + env-forecast logged weekly and
  GRADED before any adoption; CQR auto-activates at >=100 scored
  rows; field-calibration after 2-3 weeks of standings; DIV_TILT
  shadow auto-collects (grade at week 4-6); entries per contest-mix
  memory (3 qualifiers x 14 + 4 Milly week 1; never <15 per contest).
- External reviews: 5 rounds (Gemini x4, Sol/GPT-5.6 with code
  access). Every actionable finding implemented and tested; review
  packages archived in reports/review-archive/ (superseded — the
  ledger is authoritative). The audit-before-verdict law is their
  legacy: reviews caught three invalid arms the panel would have
  sworn were real.
