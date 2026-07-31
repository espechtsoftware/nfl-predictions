# NFL DFS Prediction System — Build Guide

A complete blueprint for a DraftKings NFL daily-fantasy prediction and lineup-construction system, built on free data and Google Cloud.

> **This repository implements the guide.** Map from guide section to code:
>
> | Guide | Code |
> |---|---|
> | §2/§4 Ingestion | `src/nfl_dfs/ingest/` (nflverse, DK slates, RotoGuru backfill, odds, weather) |
> | §3 Warehouse schema | `sql/raw/`, `sql/predictions/` |
> | §4.3/§5 Features + ID crosswalk | `sql/features/`, `src/nfl_dfs/features/` (incl. leakage checks) |
> | §6/§7 Models | `src/nfl_dfs/models/` (baseline, components, simulation, blending, cold start, registry, monitoring, tuning) |
> | §8.5 Trend detection | `src/nfl_dfs/trends/` (BOCPD, CUSUM, salary-lag alerts) |
> | §8.2–8.4, §8.7 Graph + news | `src/nfl_dfs/graph/` (build, injury cascade, LLM extraction); cascade wired into live projections by `src/nfl_dfs/inference/cascade_adjust.py` |
> | §9 Optimizer | `src/nfl_dfs/optimizer/` (PuLP, stacking, multi-entry, DK CSV; §9.5 Showdown Captain Mode in `showdown.py`) |
> | §10 Backtesting | `src/nfl_dfs/backtest/` (field simulation, payouts, ROI) |
> | §11 Orchestration | `deploy/` (GCP setup, Cloud Run Jobs + Scheduler), `Dockerfile` |
> | Phase 7 Interface | `src/nfl_dfs/app/` (FastAPI), `src/nfl_dfs/cli.py` (`nfl-dfs` command) |
> | §8.6 GNN | intentionally not implemented (see the section for why) |
>
> One deliberate correction to the guide: the BOCPD snippet's `P(run length = 0)` readout is constant by construction; `src/nfl_dfs/trends/changepoint.py` reports `P(run length ≤ 2)` instead (see its docstring).

---

## Quick start

### Do I need to deploy to GCP to try this?

No — nothing ever has to be *deployed*. Every job that runs in production (ingestion, feature builds, training, projections, the web app) is also a local CLI command, and the normal way to use the system is to run everything from your own machine.

What you *do* need is a **GCP project**, because BigQuery is the system's database: the pipeline writes raw data and features there, and the web app reads projections from there. There is no local-database mode. A fresh project on the free tier is generally enough for development-scale usage.

The full path from zero to lineups in the browser:

```bash
# 0. One-time: auth + create datasets/bucket/tables
gcloud auth application-default login
export GCP_PROJECT=your-project-id
deploy/setup_gcp.sh

# 1. Install with the data + app extras
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[gcp,app,dev]"

# 2. Load data (backfills 2014-present by default; FIRST_SEASON=1999 for deep history)
nfl-dfs ingest-nflverse --full
nfl-dfs backfill-rotoguru
nfl-dfs ingest-dk           # needs an active DK slate — in-season only
nfl-dfs ingest-odds
nfl-dfs ingest-weather

# 3. Features -> model -> projections
nfl-dfs build-features
nfl-dfs train
nfl-dfs project

# 4. Serve it
nfl-dfs serve --port 8080   # then open http://localhost:8080/docs
```

The interactive API docs at `/docs` are the UI: browse projections, then POST to `/lineups` to optimize and `/lineups.csv` for a file you can import at [draftkings.com/lineup/upload](https://www.draftkings.com/lineup/upload). For contests you've already entered, download DKEntries.csv from DK's Lineups → Edit Entries screen, POST it to `/lineups/entries.csv`, and re-upload the response — one generated lineup per entry. Deploying to Cloud Run (§ Deploying below) only automates steps 2–3 on a schedule — it adds nothing you can't do locally.

One seasonal caveat: `ingest-dk` and `project` need an active DraftKings slate, so end-to-end projections only work in-season (roughly September–January). Out of season you can still backfill history, build features, train, and run the backtest engine.

### Prerequisites

- Python 3.11+
- For anything that touches data (ingestion, features, training, projections): a GCP project with BigQuery and GCS, plus the `gcloud` CLI authenticated with application-default credentials (`gcloud auth application-default login`)

### Install and run the tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,app]"
pytest
```

The venv is required on Debian/Ubuntu (including WSL), where the system Python is externally managed (PEP 668) and refuses bare `pip install`. The `app` extra is needed because the test suite exercises the FastAPI service.

The test suite runs entirely offline — no GCP account, credentials, or network access required. This is the fastest way to verify the code works on your machine.

Optional dependency groups (combine as needed, e.g. `pip install -e ".[gcp,app,dev]"`):

| Extra | What it enables |
|---|---|
| `dev` | `pytest` + `httpx` (FastAPI test client) |
| `gcp` | BigQuery/GCS clients + `nflreadpy` — required for all `nfl-dfs` data commands |
| `app` | FastAPI + uvicorn for the web service (`nfl-dfs serve`) |
| `tuning` | Optuna, for walk-forward hyperparameter tuning |

### Configuration

All configuration is via environment variables, read in `src/nfl_dfs/config.py` (nothing else touches `os.environ`):

| Variable | Default | Purpose |
|---|---|---|
| `GCP_PROJECT` | `nfl-dfs-prod` | GCP project holding the datasets |
| `BQ_LOCATION` | `US` | BigQuery location |
| `BQ_RAW_DATASET` | `nfl_raw` | Landed source data |
| `BQ_FEATURES_DATASET` | `nfl_features` | Derived feature tables |
| `BQ_PREDICTIONS_DATASET` | `nfl_predictions` | Projections + registry metadata |
| `GCS_BUCKET` | `nfl-dfs-prod-raw` | Raw snapshots + model registry |
| `MODEL_REGISTRY_PREFIX` | `models` | GCS prefix for registered models |
| `FIRST_SEASON` | `2014` | Earliest season to backfill. Training only uses 2015+ (DK salaries don't exist earlier), so the default backfills just one run-up season before that; set `1999` for the full play-by-play history if you want it for exploration |
| `TRAIN_FIRST_SEASON` | `2015` | Earliest season used in training (DK salaries only go back to 2014) |

### One-time GCP setup

```bash
export GCP_PROJECT=your-project-id   # defaults to nfl-dfs-prod
deploy/setup_gcp.sh                  # enables APIs, creates datasets/bucket, applies DDL
```

### Running the pipeline locally

Every job that Cloud Scheduler runs in production can also be run by hand through the `nfl-dfs` CLI (installed by `pip install -e .`). In dependency order:

```bash
nfl-dfs ingest-nflverse --full        # backfill play-by-play etc., 2014–present (one-time; omit --full for nightly refresh)
nfl-dfs backfill-rotoguru             # one-time historical DK salary backfill (2014+)
nfl-dfs ingest-dk                     # snapshot current DK slates/salaries
nfl-dfs ingest-odds                   # snapshot DK sportsbook game lines
nfl-dfs ingest-weather                # Open-Meteo forecasts for upcoming games
nfl-dfs build-features                # run feature SQL + leakage checks
nfl-dfs train                         # weekly retrain + registry write
nfl-dfs project                       # project the upcoming slate
nfl-dfs trends                        # changepoint detection + salary-lag watchlist
```

Run `nfl-dfs --help` (or `nfl-dfs <command> --help`) for flags.

### Running the web app

```bash
pip install -e ".[gcp,app]"
nfl-dfs serve --port 8080
```

Endpoints: `GET /health`, `GET /slates`, `GET /classic/slates` (upcoming classic slates with labels like `Sun 1:00 PM–4:25 PM · 12 games`; the Sunday main slate is flagged `main`), `GET /projections`, `POST /lineups` (optimize; pass `draft_group_id` from `/classic/slates` to build for a specific slate — Sunday main, full Thu–Mon, etc. — restricting the pool to that slate's players at its salaries and draftable IDs; omit it for the whole projected week pool), `POST /lineups.csv` (DK upload file), `POST /lineups/entries.csv` (fill a downloaded DKEntries.csv, one lineup per entry; both accept `draft_group_id` too, as does `POST /lineups/core`), `GET /showdown/slates` and `POST /showdown/lineups[.csv]` / `POST /showdown/lineups/entries.csv` (Captain Mode single-game lineups, default filtered to the Thursday/Monday night games — see §9.5).

Classic projections cover the union of every upcoming classic draft group (deduped per player), so any slate DK lists is buildable; `run_projections.upcoming_slate_features` used to key on a single `MAX(pulled_at)`, which silently served whichever classic group the hourly ingest happened to fetch last.

DK's import formats match on **draftable IDs** — the slate-specific `ID` column of DKSalaries.csv, not the stable `playerId` — so upload files are only generatable for slates ingested after the IDs were added to `ingest-dk` (see the deficiency log). Showdown CPT cells additionally require the CPT-slot draftable ID; `to_dk_showdown_csv` handles that.

### Docker

The image is what Cloud Run runs; the default command serves the web app, and Cloud Run Jobs override it per job.

```bash
docker build -t nfl-dfs .
docker run -p 8080:8080 -e GCP_PROJECT=your-project-id nfl-dfs
```

### Deploying to GCP

```bash
deploy/deploy_jobs.sh   # builds the image via Cloud Build, creates Cloud Run Jobs + Scheduler triggers
                        # REGION defaults to us-central1
```

See §11 for the production schedule each job runs on.

---

## Known gaps and future enhancements

Repo-specific items, distinct from the guide's roadmap (§12).

**Historical DK salary gap, 2022–2025.** RotoGuru stopped publishing DraftKings salary data after the 2021 season, so `backfill-rotoguru` covers 2014–2021 only. Training rows for 2022–2025 have null `salary` / `salary_delta_wow` features — LightGBM handles missing values natively and leans on usage/Vegas features for those seasons, so training works, but backtests over 2022–2025 can't use salary-based lineup construction at realistic prices. From the 2026 season onward this heals itself: the hourly `ingest-dk` snapshots become our own append-only salary log. Closing the historical gap would require a paid data source or a community archive; decide whether it's worth it only if recent-season backtests become important.

**Local demo mode (no GCP).** The web app reads projections from BigQuery; there is no local-database path today. The seam already exists — `app/store.py` defines the `ProjectionStore` protocol and an `InMemoryStore` used by the tests — so a `nfl-dfs serve --demo` flag that loads a projections parquet/CSV from disk would let someone try the UI and optimizer without a GCP project. Small change, unimplemented.

**Possession-level game simulator — engine landed, not yet adopted (2026-07-31, issue #13 item 6).** `models/game_sim.py` is a drive-state Markov chain (field-position zone x terminal outcome — TD/FG/punt/turnover/downs/safety) meant to replace `simulate.py`'s shared lognormal game factor with one derived from how drives actually end, so game-script correlation (leading team runs more, trailing team airs it out) and possession-count variance emerge instead of being imposed by a single multiplicative dial. Design: `reports/possession-simulator-design.md`. Gated by `GAME_SIM_MODE=possession` (default off, unchanged behavior); its transition probabilities are a **placeholder** hand-calibrated to plausible NFL aggregates, not fit from real `nfl_raw.pbp` — that fit, the `backtest/replay.py` A/B wiring, and the 2025-replay validation against the 184.2-mean-best/6-of-17 baseline all need GCP and are next.

**Live-slate features, depth charts, and the injury cascade (2026-07-25).** Three formerly-disconnected pieces now reach production projections:

- *Upcoming-week feature rows.* Live inference used to join `player_week_training` at the upcoming week — rows that can't exist until the games are played (the table inner-joins actuals) — so every live projection silently fell back to cold-start fills plus the market blend. 014/015/016 now emit synthetic rows for each team's next unplayed game (`is_upcoming`; all source metrics NULL, so the strictly-prior windows produce as-of-now rollups), and `023_player_week_inference.sql` assembles them into `player_week_inference`, which `run_projections` joins instead. Training is untouched: 021 filters `NOT is_upcoming` and still requires actuals.
- *Depth charts activate the cold-start priors.* `coldstart.ROLE_PRIORS` always keyed on `depth_rank`/`is_rookie`/`draft_round`, but nothing populated them, so every cold-start player got the depth-3 default. `003_player_week_role.sql` now derives a per-week depth rank from the (two-format) depth chart data plus rookie/draft capital from rosters and draft picks, joined into both 021 and 023. `depth_rank` is also a model feature.
- *Next-man-up, in two layers.* `team_week_vacated` (018) sums the trailing-window target/carry shares of teammates listed Out on the week's report — point-in-time on both sides — and feeds `team_vacated_target_share`/`team_vacated_carry_share` model features, so the GBDTs learn redistribution from history. For status flips after the feature build (the starter ruled out Sunday morning), `inference/cascade_adjust.py` zeroes O/IR players and hands their opportunity to slate teammates via `graph.cascade.project_vacated_usage` (measured with/without splits when absence history exists, usage-weighted fallback otherwise), applied on top of the cold-start fill during the hourly pass.

Known edges, accepted for now: Doubtful players are projected, not zeroed (their depressed practice features carry the signal); on multi-day slates, players whose game already happened lose their upcoming-week feature row and fall back to cold-start (they're not late-swappable anyway); a registry model trained before a featureset addition keeps predicting — `predict_components` slices to each booster's own feature list — and picks up new features at the next weekly retrain. After deploying this change, run `nfl-dfs ingest-nflverse --full` once so the split depth chart raw tables exist before the next `build-features`.

**Cornerback coverage metrics (2026-07-25).** WR/TE projections previously saw the opposing pass defense only at team level (EPA/dropback allowed, positional FP allowed). `pfr_advstats_def` (new nflverse ingest, PFR advanced defense stats 2018+) now feeds `017a_defense_week_coverage.sql`: yards per target and completion rate allowed by the opponent's CB group as nearest defenders, the secondary-wide yards per target, and `top_cb_out` — the opponent's coverage-snap-leading corner (identified from strictly-prior snaps) listed Out on this week's report. Built on the schedule spine so the upcoming week has a real row (exact-week join in 023, no as-of staleness), joined into training/inference, added to the model featureset, and covered by the leakage checker (recompute-and-compare on the l6 windows + first-row-null). True WR-vs-CB assignment data remains paid-only and modest in value (§2.5); this is deliberately group-level. After deploying, run `nfl-dfs ingest-nflverse --full` once so the new raw table exists before the next `build-features`.

**Showdown Captain Mode (2026-07-25).** Single-game Captain Mode lineups for the Thursday/Monday night slates are built by `optimizer/showdown.py` + the `/showdown/*` endpoints (see §9.5), reusing classic-pipeline projections joined by DK player id. Deliberately deferred: (a) K and DST ride on DK's `dk_ppg` figure rather than a model — a trailing-average kicker/DST model like the replay's `DST_FALLBACK_PROJ` approach would be the natural upgrade if showdown becomes a priority; (b) no showdown backtest — `backtest/` replays classic contests only, so showdown lineup quality is unvalidated beyond the optimizer's unit invariants; (c) no simulated-outcomes mode (`simulate_lineups` equivalent) — captain leverage from correlated draws would be the next construction improvement.

**Archetype clustering — deferred pieces.** `nfl-dfs archetypes` (see `src/nfl_dfs/analysis/archetypes.py`) clusters players into scoring-consistency archetypes, stamps them on graph nodes for the injury cascade, and adds `SIMILAR_TO` edges for profile-based pivots. Deliberately left out of v1: (a) graph-derived clustering inputs — QB-attachment stability via `TARGETED_BY` edges and target-room crowding via `COMPETES_WITH` — the least value for the most work; (b) salary/ownership-aware pivot ranking ("cheaper, same profile, lower owned") — needs live slate salaries and an ownership source (see the deficiency log); (c) a scheduled refresh — the table is CLI-only, not in `deploy_jobs.sh`; weekly in-season would be the natural cadence.

**Replay findings (2026-07-24, first full-season replays).** `nfl-dfs replay --season N` trains on strictly-prior seasons and scores every week of season N; see `src/nfl_dfs/backtest/replay.py`. Results (2019/2021/2025): projection MAE beats the naive trailing-average baseline by ~5% every season; within-position rank correlation 0.43–0.64. Both weaknesses found in the first replays were addressed same day:

- *Quantile calibration.* The raw simulated distribution was too narrow (p10 coverage 13–24% vs. a 10% target, worst for QB/RB where TD variance dominates). `models/calibration.py` now applies per-position widen factors fit on pooled 2019+2021 replays (`QB 1.5, RB 1.45, TE 1.05, WR 1.1`) — verified out-of-sample on 2025: overall coverage moved to 8.6%/88.9% against 10%/90% targets. Applied in production inference and by default in replays; refit with `calibration.fit_widen_factors` after any simulator change.
- *Field realism.* The simulated field now includes optimizer-built entrants (`--sharp`, default 15%): distinct optimal lineups from jittered projections, duplicated the way sharp lineups duplicate in real large-field contests. On 2021 this compressed double-up ROI from +63% to +51% and median finish from 17.8% to 22.9% — more honest, still an upper bound until the field runs on real ownership (deficiency below). Treat double-up ROI as the meaningful signal; GPP ROI remains tail-inflated.

Four-season double-up evidence with the sharp field (15%): 2018 +69%, 2019 +61%, 2020 +53%, 2021 +51% — consistently positive across every replayable season, median weekly finish in the top 20–25% of the simulated field. Next fidelity step is real ownership (groundwork in place, see log).

### Data deficiency log

Append-only. Whenever a gap or quality problem is found in source data, add a row here (see CLAUDE.md) so future decisions about fixing vs. accepting are made from a complete list.

| Found | Deficiency | Impact | Status |
|---|---|---|---|
| 2026-07-24 | RotoGuru DK salary history ends after the 2021 season (site stopped updating) | `salary`/`salary_delta_wow` null on 2022–2025 training rows; recent-season backtests can't price lineups. Also degrades salary as a *model feature* in the null era: the 2025 ablation showed removing it helped (−0.013 MAE) while the full-coverage 2021 ablation showed it helps (+0.010, rank corr 0.611 vs 0.599) — see reports/2026-07-25-system-study.md | **2025 closed** (2026-07-25): DiscoveryLab free tier serves real salaries for the most recent season — 13,406 rows imported + Captain Mode slates, verified 100% $100-multiples (`import-discoverylab`, `import-discoverylab-showdown`). Remaining gap: 2022–2024 (their paid personal tiers may cover; unverified). Earlier vendor trail: SportsDataIO trial serves scrambled salaries and no historical access; their commercial API quotes several thousand dollars — declined. Their personal-use DiscoveryLab tier is unverified for DFS salaries (asked). A tested importer for their DfsSlatesByWeek endpoint lives in git history at commit 7d17bd8 (removed after the trial dead-end) — one revert away if a viable key appears |
| 2026-07-24 | ~2–4% of 2014–2021 RotoGuru rows can't be safely matched to a GSIS ID (ambiguous duplicate names, team defenses) | Small salary-coverage holes in otherwise ~98%-covered seasons | Accepted — dropping beats guessing between same-name players |
| 2026-07-24 | No historical market projection exists: RotoGuru has no `dk_ppg`, and we have no prop-line archive | `dk_ppg` is null before 2026, so walk-forward "beats the market" comparisons have no market baseline until our own DK snapshots accumulate | Open — consider a props archive if market-relative validation matters before mid-2026 |
| 2026-07-24 | nflverse `weekly_stats` schema drift: `recent_team` → `team`, `interceptions` → `passing_interceptions` | Broke `013_player_week_actuals.sql` on first real build | Fixed in SQL — treat unknown-column build failures as possible upstream renames |
| 2026-07-24 | nflverse `injuries` ships `season`/`week` as FLOAT (null-driven upcast) | BigQuery refuses FLOAT64 in window `PARTITION BY`; type-inconsistent join keys | Fixed — cast to INT64 in `018_player_week_injury.sql` |
| 2026-07-24 | Advanced-source history is shorter than the 2014+ panel: snap counts 2012+, NGS 2016+, FTN charting 2022+ | Features derived from these are null in early seasons of the training window | Accepted — LightGBM handles missing natively |
| 2026-07-25 | No free source for routes run / targets-per-route-run (TPRR) — PFF and FTN paid tiers only | TPRR is among the most predictive receiver metrics; snap share + WOPR are our best free proxies | Open — revisit if a paid data budget ever exists; everything else worth having from the research pass is implemented (see reports/2026-07-25-system-study.md addendum) |
| 2026-07-24 | No nflverse data for a season until its games begin (loaders reject the planning-clock season) | Offseason ingest crashed until clamped | Fixed — `ingest/nflverse_job.py` clamps to `nfl.get_current_season()` |
| 2026-07-24 | No ownership data source, projected or historical — `player_projections.proj_ownership` is a NULL placeholder | GPP leverage decisions and "same profile, lower owned" pivot ranking have no ownership signal; field simulation in backtests leans on salary-based heuristics instead | Open, groundwork in place — `nfl_raw.contest_ownership` table + `nfl-dfs import-ownership` (DK contest-standings CSV parser) exist; export one GPP + one cash contest weekly in-season and a regression can replace the naive proxy behind `backtest/field.py`'s `ownership` parameter |
| 2026-07-24 | `017_defense_week_allowed.sql`: the opponent-strength normalizer (`off_strength`) averaged over the full season, so `*_fp_allowed_adj_l6` saw future weeks | Mild optimistic bias in backtests through the four positional defense features; originally not caught by leakage checks (they only covered usage features) | Fixed same day — offense strength is now a trailing average through the prior week, and the leakage checker gained a defense pass (EPA-allowed recomputed from pbp at team grain + first-row-null invariant on all six defense features) |
| 2026-07-24 | FTN charting (2022+) is ingested but unused by any feature SQL — pressure (`n_pass_rushers`, `n_blitzers`), box counts, play-action flags | Defense assessment leans on EPA-allowed only; pressure rate allowed is the strongest free upgrade for QB/pass projections. Also the reason paid DVOA was evaluated and deferred — most of its marginal signal is derivable here | Open — candidate features: pressure rate allowed l6, box-count vs. run efficiency, success/explosive-play rate allowed from pbp |
| 2026-07-25 | nflverse depth charts changed format in 2025: weekly `season`/`week`/`depth_team` rows became dated snapshots (`dt`, `pos_rank`, `pos_grp`) sharing almost no columns with the old schema | A single raw table can't hold both eras; naive multi-season loads mix schemas | Fixed — ingest lands `depth_charts` (2001–2024) and `depth_charts_snapshots` (2025–) separately; `003_player_week_role.sql` normalizes both, mapping snapshots to weeks point-in-time (latest snapshot on/before gameday). Requires one `ingest-nflverse --full` to materialize |
| 2026-07-25 | `draft_picks.gsis_id` is empty or non-GSIS-formatted for recent draft classes | Draft-round lookup by ID fails for exactly the rookies who need the cold-start discount | Fixed — 003 falls back to matching the roster's overall pick number (`draft_number`) within the player's `entry_year` draft |
| 2026-07-25 | Legacy depth charts list alignment starters with equal `depth_team` (two WR "1" rows) and occasional garbage in `depth_position` | No true global WR pecking order before 2025; ranks 1–3 all mean "starter tier" | Accepted — deterministic ROW_NUMBER tiebreak (depth_team, jersey); the 2025+ snapshot format publishes a real global `pos_rank` |
| 2026-07-25 | PFR advanced defense stats start in 2018, and "nearest defender" target attribution is charting-derived — noisy at the single-play level | CB coverage features (`017a`) are NULL on 2014–2017 training rows; per-game group aggregates carry attribution noise | Accepted — LightGBM handles missing natively; summing to the CB group per game averages the attribution noise out |
| 2026-07-25 | No in-season coverage-scheme data: NGS stopped publishing participation (`defense_man_zone_type`/`defense_coverage_type`) after 2022; FTN's replacement lands only after each season ends | Team man/zone rates would be a season stale at inference — training on them would create train/serve skew, so they're not built | Accepted for now — revisit if FTN ever ships participation in-season |
| 2026-07-25 | The `player_ids` crosswalk (dynastyprocess) has thinner coverage for defensive players; a CB1 whose `pfr_id` is unmatched can't be joined to the injury report | `top_cb_out` silently reads FALSE for unmatched corners (treated as playing) | Accepted — affects the indicator only, not the coverage-quality windows, which never leave PFR keys |
| 2026-07-25 | DK showdown draftables repeat each player as CPT (1.5x salary) and FLEX; `draftables_frame` used to keep whichever row came first, so `dk_salaries` showdown rows ingested before this date may carry the CPT price | Historical showdown salary snapshots are ambiguous (off by up to 1.5x); classic rows unaffected (slot repeats share one salary) | Fixed — dedup now keeps the cheaper FLEX row and the optimizer derives CPT cost as 1.5x; old showdown rows are unused by any pipeline |
| 2026-07-25 | DK's lineup import matches on slate-specific draftable IDs (the DKSalaries `ID` column), which `ingest-dk` discarded — it kept only the stable `playerId`, and upload CSVs were built from that, so DK would reject them. Verified against the live draftgroups API vs. `getavailableplayerscsv` for the same group; showdown CPT slots need the CPT-row draftable ID, which differs from FLEX | `dk_salaries` rows pulled before this date can't produce importable files (upload only matters for live slates, so the loss is historical-only); pre-fix "DK upload" CSVs were never actually importable | Fixed — ingest now lands `dk_draftable_id` + `dk_cpt_draftable_id` (DDL migration in `sql/raw/002_dk_salaries.sql`), exports use them with player-ID fallback + warning |

---

## 0. Design principles

Read these before writing code. They save the most time.

1. **Derive, don't scrape.** Almost every "advanced" stat you want (red zone targets, air yards share, opportunity share, goal-line carries) is a `GROUP BY` over free play-by-play. Scraping a site's pre-aggregated table locks you into their definitions and their uptime.
2. **Store raw, transform later.** Land the source data verbatim in a `raw` dataset. Build features as views/tables downstream. When you discover a bug in your red-zone definition in week 9, you re-run a query instead of re-scraping a season.
3. **Point-in-time correctness is everything.** Your model must only see what was knowable before kickoff. This is the #1 way DFS backtests lie to you. Every feature table gets an `as_of_week` column and every join respects it.
4. **The market is your baseline.** Vegas implied team totals and player prop lines encode enormous information. If your model can't beat "project everyone at their prop line," you don't have a model yet.
5. **Projections and lineups are separate problems.** Get point projections right first. Ownership, correlation, and GPP vs cash strategy are a second, distinct layer.

---

## 1. Architecture

```
                    ┌──────────────────────────────────────┐
                    │  Cloud Scheduler (cron triggers)     │
                    └───────────────┬──────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
      ┌───────────────┐    ┌────────────────┐    ┌────────────────┐
      │ ingest_nflverse│   │ ingest_dk_slate│    │  ingest_odds   │
      │ (Cloud Run Job)│   │ (Cloud Run Job)│    │ (Cloud Run Job)│
      │  nightly       │   │  hourly Th–Sun │    │  hourly Th–Sun │
      └───────┬────────┘   └───────┬────────┘    └───────┬────────┘
              │                    │                     │
              └────────────────────┼─────────────────────┘
                                   ▼
                      ┌─────────────────────────┐
                      │   GCS bucket (parquet)  │  ← raw landing zone
                      └────────────┬────────────┘
                                   ▼
                      ┌─────────────────────────┐
                      │  BigQuery: nfl_raw       │
                      └────────────┬────────────┘
                                   ▼
                      ┌─────────────────────────┐
                      │  dbt / SQL transforms    │
                      │  BigQuery: nfl_features  │
                      └────────────┬────────────┘
                                   ▼
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
   ┌────────────────────┐                   ┌──────────────────────┐
   │  Model training    │                   │  Weekly inference    │
   │  (Vertex AI or     │                   │  (Cloud Run Job)     │
   │   local + GCS)     │                   │  → nfl_predictions   │
   └────────────────────┘                   └──────────┬───────────┘
                                                       ▼
                                            ┌──────────────────────┐
                                            │  Optimizer + UI      │
                                            │  (Cloud Run service) │
                                            └──────────────────────┘
```

**Why these components**

| Need | Service | Rationale |
|---|---|---|
| Scheduled ingestion | Cloud Run Jobs + Cloud Scheduler | Cheaper and simpler than Composer/Airflow for <20 tasks. Runs to completion, no idle cost. |
| Warehouse | BigQuery | Free tier covers 1 TB query/month and 10 GB storage. Full nflverse PBP for 25 seasons is ~2 GB. You will not pay for this. |
| Raw landing | GCS standard bucket | Parquet files, partitioned by season. Pennies. |
| Transforms | dbt-bigquery (or plain SQL scripts) | dbt gives you lineage, tests, and incremental models. Worth it by month two. |
| Model training | Local first, Vertex AI if you outgrow it | LightGBM on 200k rows trains in seconds on a laptop. Don't over-engineer. |
| Serving/UI | Cloud Run service | Scales to zero. FastAPI + a simple React front end, or Streamlit if you want it done in a day. |
| Secrets | Secret Manager | API keys for odds providers. |

**Cost estimate:** roughly $0–5/month if you stay inside free tiers and don't scan the full PBP table carelessly. Partition and cluster your tables (see §3).

---

## 2. Data sources

### 2.1 Primary — nflverse (free, permissive, no scraping)

The nflverse project publishes clean NFL data as versioned GitHub releases in parquet, csv, and rds. Updated nightly during the season.

- **Repo:** `github.com/nflverse/nflverse-data` (releases hold the actual data)
- **Python client:** `nflreadpy` — this is the maintained package. `nfl_data_py` is deprecated and will not receive updates.
- **R client:** `nflreadr`
- **Docs:** `nflreadr.nflverse.com`, `nflfastr.com`

| Dataset | `nflreadpy` function | What you get | Coverage |
|---|---|---|---|
| Play-by-play | `load_pbp(seasons)` | ~370 columns per play: EPA, WPA, air yards, YAC, CPOE, yardline, down/distance, personnel, drive & series info, player IDs for passer/rusher/receiver | 1999– |
| Player weekly stats | `load_player_stats(seasons)` | Pre-aggregated weekly box + advanced (target share, air yards share, WOPR, racr) | 1999– |
| Snap counts | `load_snap_counts(seasons)` | Offense/defense/ST snaps and pct by player-game | 2012– |
| Depth charts | `load_depth_charts(seasons)` | Weekly positional depth | 2001– |
| Rosters | `load_rosters_weekly(seasons)` | Active/inactive, position, jersey, ID crosswalks | 1999– |
| Injuries | `load_injuries(seasons)` | Practice participation + game status by week | 2009– |
| Schedules | `load_schedules(seasons)` | **Includes closing spread, total, moneyline** — free Vegas history | 1999– |
| Participation | `load_participation(seasons)` | Personnel groupings, offense/defense players on field per play | 2016–2023 |
| FTN charting | `load_ftn_charting(seasons)` | Play action, screen, QB pressure, no-huddle, motion — manual charting | 2022– |
| Next Gen Stats | `load_nextgen_stats(...)` | Separation, cushion, time to throw, expected rush yards | 2016– |
| PFR advanced stats | `load_pfr_advstats(seasons, stat_type, summary_level)` | With `stat_type="def"`: per-defender coverage — targets, completions/yards/TDs allowed as nearest defender, passer rating when targeted, missed tackles. Weekly or season grain | 2018– |
| ID crosswalk | `load_ff_playerids()` | Maps GSIS ↔ PFR ↔ ESPN ↔ Sleeper ↔ Yahoo ↔ DraftKings-ish names | current |

**Licensing note:** nflverse data is generally free to use; the FTN charting subset is CC-BY-SA 4.0 and requires attribution to FTN Data via nflverse. If you ever make the app public, put that attribution in the footer.

**The ID crosswalk is not optional.** DraftKings gives you display names like "Marvin Harrison Jr." while nflverse gives you `00-0039337`. Name matching alone will fail on suffixes, Jr./Sr., apostrophes, and the roughly two dozen name collisions per season. Build the mapping table in week one.

### 2.2 DraftKings salaries and slates (free, undocumented public API)

No authentication required. Two endpoints:

```
# 1. List current draft groups (slates) for NFL
GET https://api.draftkings.com/draftgroups/v1/

# 2. Get the player pool + salaries for a specific draft group
GET https://api.draftkings.com/draftgroups/v1/draftgroups/{draftGroupId}/draftables
```

The `draftables` response gives you, per player: `displayName`, `salary`, `position`, `rosterSlotId`, `teamAbbreviation`, `competition` (the game), `status`, and a `draftStatAttributes` array that sometimes carries DK's own points-per-game figure.

Filter draft groups by `sport == "NFL"` and inspect `draftGroupState` / `startTimeSuffix` to identify the main slate versus showdown/single-game slates. Showdown slates use different roster rules and should be a separate pipeline branch.

**Cadence:** pull at slate lock minus 48h, then hourly through lock. Salaries are set once, but the *player pool* changes as inactives are announced, and that's the signal you care about.

**Historical DK salaries** — the real gap. Options, in order of preference:

1. `rotoguru1.com/cgi-bin/fyday.pl?week=N&year=YYYY&game=dk&scsv=1` — semicolon-separated, ugly, complete, free, back to 2014. Includes actual DK points scored. This is the standard answer.
2. `github.com/Brian-Doucet/nfldfs` — Python package that scrapes DK salary and points by season into a DataFrame.
3. Start logging your own from day one. In three seasons you'll have the best copy.

**Ownership percentages** are the one genuinely hard-to-get-free item. They matter a lot for GPPs and not at all for cash games. Options: scrape contest results pages post-hoc (DK exposes contest standings for completed contests), or accept a paid source later. Build the system to work without ownership, with a clean slot to add it.

### 2.3 Vegas odds

**Free and sufficient for most of it:** nflverse `load_schedules()` carries the closing spread and total for every game back to 1999. Derive implied team totals:

```
implied_home = total/2 - spread_home/2
implied_away = total/2 + spread_home/2
```

That single feature will do more for your projections than any three advanced metrics.

**For live in-week lines and player props**, you need a provider. Current landscape:

| Provider | Free tier | NFL props? | Notes |
|---|---|---|---|
| The Odds API | 25 req/day, NBA + MLB only, h2h only | Paid tiers only ($99/mo Business for props) | Well-established, clean API, historical archive on top tier |
| SportsGameOdds | Free plan with limited books and ~10-min delay | Yes, on paid | Paid from ~$99/mo |
| OddsPapi | Free tier claims historical included | Yes | Newer, verify before depending on it |
| Pinnacle | Free live odds + fixtures | Sharp reference pricing | Paid from ~$10/mo; sharpest lines, fewest props |

Practical advice: skip paid odds in v1. Use nflverse closing lines for training and scrape the DK sportsbook's own public endpoints for live game lines, since you're already hitting DK. Add a props provider only once your model is good enough that the marginal edge justifies $99/month.

### 2.4 Weather

`github.com/nflverse/nfldata` carries stadium metadata including roof type. For game-time conditions, Open-Meteo's free API takes lat/long + timestamp with no key. Weather matters less than people think — mostly wind above ~15 mph suppressing passing volume and kicker scoring.

### 2.5 What you cannot get free

Be honest about the ceiling. These require PFF, Fantasy Points Data Suite, or SIS:

- **Routes run** (and therefore true targets-per-route-run / YPRR)
- **Target separation and coverage matchup** (NGS gives partial separation data)
- **WR-vs-CB assignments** — who shadowed whom, per-route matchup targets. Before paying for this, note the signal is smaller than it sounds: most teams keep corners on sides or play zone on a majority of snaps, and true shadow situations are a handful of player-weeks per season
- **Snap-level offensive line grades**
- **Route depth/type charting at scale**

Serviceable free proxies:
- Routes run ≈ `offense_snaps × team_pass_rate` — correlation is around 0.9 for WRs, weaker for RBs
- Coverage matchup ≈ opponent's EPA-per-dropback allowed to that alignment, from PBP
- Cornerback quality ≈ PFR advanced defense stats (2018+): per-CB yards/completions allowed as nearest defender, rolled up to the opposing CB group per week (implemented — `defense_week_coverage`, §5.3). Plus a "top corner out" flag from prior-week coverage snaps × the injury report
- Separation ≈ NGS `avg_separation`, available 2016–present

One coverage-scheme source deliberately not used: `load_participation()` carries per-play `defense_man_zone_type` / `defense_coverage_type`, but NGS stopped publishing after 2022 and FTN's replacement (2023–) lands only after each season ends — a season stale at inference time, so team man/zone rates would train on data that can't be served live.

### 2.6 Where Playwright/Browserbase is actually warranted

Almost nowhere in v1 — and that's a feature, not a limitation. Headless browsers are slow, fragile, and a maintenance burden. Reserve them for:

- **DK UI fallback** if the JSON API shape changes mid-season. Build it, keep it disabled behind a flag.
- **Contest results pages** for ownership backfill, if DK's results endpoints require a session.
- **Beat-writer / practice-report aggregation** if you ever want news-driven late-swap signals.

Pro-Football-Reference has red zone tables at `/years/{YYYY}/redzone-receiving.htm` that `pandas.read_html` parses without a browser — but check their terms, rate-limit yourself to one request every few seconds, and understand they ban aggressively. You shouldn't need it once nflverse is running.

---

## 3. Warehouse schema

Three BigQuery datasets: `nfl_raw`, `nfl_features`, `nfl_predictions`.

### 3.1 `nfl_raw`

Land source data with minimal transformation. Partition on `season`, cluster on the natural key.

```sql
CREATE TABLE nfl_raw.pbp (
  game_id STRING, play_id INT64, season INT64, week INT64, season_type STRING,
  posteam STRING, defteam STRING,
  yardline_100 INT64, down INT64, ydstogo INT64, qtr INT64,
  game_seconds_remaining INT64, score_differential INT64,
  play_type STRING, pass_attempt INT64, rush_attempt INT64,
  complete_pass INT64, touchdown INT64, pass_touchdown INT64, rush_touchdown INT64,
  passer_player_id STRING, rusher_player_id STRING, receiver_player_id STRING,
  air_yards FLOAT64, yards_after_catch FLOAT64, yards_gained INT64,
  epa FLOAT64, wpa FLOAT64, cpoe FLOAT64,
  shotgun INT64, no_huddle INT64, qb_dropback INT64,
  drive INT64, series INT64, fixed_drive_result STRING
  -- plus whatever else you need; PBP has ~370 columns
)
PARTITION BY RANGE_BUCKET(season, GENERATE_ARRAY(1999, 2040, 1))
CLUSTER BY game_id, posteam;
```

Other raw tables: `weekly_stats`, `snap_counts`, `depth_charts` (2001–2024 weekly format), `depth_charts_snapshots` (2025– dated-snapshot format; see the deficiency log), `rosters_weekly`, `injuries`, `schedules`, `ngs_receiving`, `ngs_rushing`, `ngs_passing`, `ftn_charting`, `player_ids`, `dk_salaries`, `dk_slates`, `odds_snapshots`.

`dk_salaries` deserves care — it's an append-only log, not a snapshot:

```sql
CREATE TABLE nfl_raw.dk_salaries (
  pulled_at TIMESTAMP,          -- when YOU fetched it
  draft_group_id INT64,
  slate_type STRING,            -- 'classic' | 'showdown'
  season INT64, week INT64,
  dk_player_id INT64,
  dk_draftable_id INT64,        -- slate-specific ID DK's lineup upload wants
  dk_cpt_draftable_id INT64,    -- showdown only: the CPT-slot draftable ID
  display_name STRING,
  team_abbr STRING,
  position STRING,
  salary INT64,
  roster_slot STRING,
  game_start TIMESTAMP,
  status STRING                 -- 'None' | 'O' | 'Q' | 'D' ...
)
PARTITION BY DATE(pulled_at)
CLUSTER BY season, week, dk_player_id;
```

Never overwrite. The history of how a player's status changed before lock is itself a valuable feature.

### 3.2 `nfl_features`

Point-in-time feature tables. The cardinal rule: **row for (player, season, week) contains only data from weeks strictly before `week`.**

Core tables:
- `player_week_usage` — volume and opportunity features
- `player_week_efficiency` — rate stats
- `team_week_context` — pace, pass rate over expected, implied total
- `defense_week_allowed` — opponent-adjusted concessions by position
- `defense_week_coverage` — CB-group coverage quality + top-corner availability (schedule spine, so the upcoming week has a servable row)
- `player_week_training` — the joined, model-ready wide table

### 3.3 `nfl_predictions`

```sql
CREATE TABLE nfl_predictions.player_projections (
  generated_at TIMESTAMP,
  model_version STRING,
  season INT64, week INT64, slate_id INT64,
  gsis_id STRING, dk_player_id INT64,
  display_name STRING, position STRING, team STRING, opponent STRING,
  salary INT64,
  proj_points FLOAT64,          -- mean
  proj_p10 FLOAT64,             -- 10th percentile
  proj_p50 FLOAT64,
  proj_p90 FLOAT64,             -- ceiling — what matters for GPP
  proj_std FLOAT64,
  value FLOAT64,                -- proj_points / (salary/1000)
  proj_ownership FLOAT64        -- nullable until you have a source
)
PARTITION BY DATE(generated_at)
CLUSTER BY season, week;
```

---

## 4. Ingestion

### 4.1 nflverse loader

```python
# ingest/nflverse_job.py
import nflreadpy as nfl
import pandas as pd
from google.cloud import bigquery
from datetime import date

PROJECT = "your-project"
RAW = f"{PROJECT}.nfl_raw"
bq = bigquery.Client(project=PROJECT)

def load_table(df: pd.DataFrame, table: str, partition_field: str | None = None):
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        autodetect=True,
    )
    if partition_field:
        job_config.time_partitioning = bigquery.TimePartitioning(field=partition_field)
    bq.load_table_from_dataframe(df, f"{RAW}.{table}", job_config=job_config).result()

def current_season() -> int:
    t = date.today()
    # NFL season year rolls over in March
    return t.year if t.month >= 3 else t.year - 1

def run(full_refresh: bool = False):
    season = current_season()
    seasons = list(range(1999, season + 1)) if full_refresh else [season]

    # nflreadpy returns polars by default; .to_pandas() for the BQ client
    load_table(nfl.load_pbp(seasons).to_pandas(), "pbp")
    load_table(nfl.load_player_stats(seasons).to_pandas(), "weekly_stats")
    load_table(nfl.load_snap_counts(seasons).to_pandas(), "snap_counts")
    load_table(nfl.load_depth_charts(seasons).to_pandas(), "depth_charts")
    load_table(nfl.load_rosters_weekly(seasons).to_pandas(), "rosters_weekly")
    load_table(nfl.load_injuries(seasons).to_pandas(), "injuries")
    load_table(nfl.load_schedules().to_pandas(), "schedules")
    load_table(nfl.load_ff_playerids().to_pandas(), "player_ids")

    if season >= 2022:
        load_table(nfl.load_ftn_charting(seasons).to_pandas(), "ftn_charting")

if __name__ == "__main__":
    import sys
    run(full_refresh="--full" in sys.argv)
```

Schedule: nightly at 06:00 CT during the season (nflverse updates overnight), weekly in the offseason. Run once with `--full` to backfill.

### 4.2 DraftKings slate loader

```python
# ingest/dk_job.py
import requests, pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery

DK_GROUPS = "https://api.draftkings.com/draftgroups/v1/"
DK_DRAFTABLES = "https://api.draftkings.com/draftgroups/v1/draftgroups/{gid}/draftables"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def nfl_draft_groups():
    r = requests.get(DK_GROUPS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return [
        g for g in r.json().get("draftGroups", [])
        if g.get("sport") == "NFL" and g.get("draftGroupState") == "Upcoming"
    ]

def draftables(gid: int) -> pd.DataFrame:
    r = requests.get(DK_DRAFTABLES.format(gid=gid), headers=HEADERS, timeout=30)
    r.raise_for_status()
    payload = r.json()

    # Games in this slate — needed to map players to opponents
    comps = {c["competitionId"]: c for c in payload.get("competitions", [])}

    rows = []
    seen = set()
    for d in payload.get("draftables", []):
        pid = d["playerId"]
        if pid in seen:          # DK repeats players across roster slots
            continue
        seen.add(pid)
        comp = comps.get(d.get("competition", {}).get("competitionId"), {})
        rows.append({
            "pulled_at": datetime.now(timezone.utc),
            "draft_group_id": gid,
            "dk_player_id": pid,
            "display_name": d["displayName"],
            "team_abbr": d.get("teamAbbreviation"),
            "position": d.get("position"),
            "salary": d.get("salary"),
            "roster_slot": d.get("rosterSlotId"),
            "game_start": comp.get("startTime"),
            "status": d.get("status"),
        })
    return pd.DataFrame(rows)

def run():
    frames = [draftables(g["draftGroupId"]) for g in nfl_draft_groups()]
    if not frames:
        return
    df = pd.concat(frames, ignore_index=True)
    bigquery.Client().load_table_from_dataframe(
        df, "your-project.nfl_raw.dk_salaries",
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND", autodetect=True),
    ).result()
```

Schedule: hourly Thursday through Sunday. Be a good citizen — this is an undocumented endpoint and hammering it is how it gets locked down.

### 4.3 Player ID resolution

```sql
-- nfl_features.player_id_map
CREATE OR REPLACE TABLE nfl_features.player_id_map AS
WITH dk AS (
  SELECT DISTINCT dk_player_id, display_name, team_abbr, position
  FROM nfl_raw.dk_salaries
  WHERE pulled_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
),
norm_dk AS (
  SELECT *,
    REGEXP_REPLACE(UPPER(display_name), r"[^A-Z ]", "") AS clean_name,
    -- strip common suffixes
    REGEXP_REPLACE(UPPER(display_name), r"\s+(JR|SR|II|III|IV)\.?$", "") AS base_name
  FROM dk
),
norm_nfl AS (
  SELECT gsis_id, name, team, position,
    REGEXP_REPLACE(UPPER(name), r"[^A-Z ]", "") AS clean_name
  FROM nfl_raw.player_ids
  WHERE gsis_id IS NOT NULL
)
SELECT d.dk_player_id, n.gsis_id, d.display_name, d.team_abbr, d.position
FROM norm_dk d
JOIN norm_nfl n
  ON d.clean_name = n.clean_name
 AND d.team_abbr  = n.team
 AND d.position   = n.position;
```

Then build an unmatched report and maintain a small manual override table. Expect 10–30 manual entries per season, mostly rookies and practice-squad call-ups. Fail loudly on unmatched players in your slate rather than silently dropping them — a dropped player is a lineup you can't build.

---

## 5. Feature engineering

### 5.1 Red zone usage — the query you came for

```sql
-- Red zone receiving usage by player-game, with inside-10 and inside-5 splits
CREATE OR REPLACE TABLE nfl_features.rz_receiving AS
WITH plays AS (
  SELECT
    game_id, season, week, posteam, receiver_player_id,
    yardline_100,
    pass_attempt, complete_pass, pass_touchdown, air_yards
  FROM nfl_raw.pbp
  WHERE pass_attempt = 1
    AND receiver_player_id IS NOT NULL
    AND season_type IN ('REG','POST')
),
player_level AS (
  SELECT
    game_id, season, week, posteam AS team, receiver_player_id AS gsis_id,
    COUNTIF(yardline_100 <= 20) AS rz20_targets,
    COUNTIF(yardline_100 <= 10) AS rz10_targets,
    COUNTIF(yardline_100 <=  5) AS rz5_targets,
    COUNTIF(yardline_100 <= 20 AND pass_touchdown = 1) AS rz20_tds,
    COUNTIF(yardline_100 <= 10 AND complete_pass = 1)  AS rz10_receptions,
    COUNT(*) AS total_targets,
    SUM(air_yards) AS total_air_yards
  FROM plays
  GROUP BY 1,2,3,4,5
),
team_level AS (
  SELECT
    game_id, posteam AS team,
    COUNTIF(yardline_100 <= 20) AS team_rz20_targets,
    COUNTIF(yardline_100 <= 10) AS team_rz10_targets,
    COUNT(*) AS team_targets,
    SUM(air_yards) AS team_air_yards
  FROM plays
  GROUP BY 1,2
)
SELECT
  p.*,
  SAFE_DIVIDE(p.rz20_targets, t.team_rz20_targets) AS rz20_target_share,
  SAFE_DIVIDE(p.rz10_targets, t.team_rz10_targets) AS rz10_target_share,
  SAFE_DIVIDE(p.total_targets, t.team_targets)     AS target_share,
  SAFE_DIVIDE(p.total_air_yards, t.team_air_yards) AS air_yards_share
FROM player_level p
JOIN team_level t USING (game_id, team);
```

Equivalent for rushing — swap `rusher_player_id` and `rush_attempt`, and add a goal-line split at `yardline_100 <= 3`, which is where RB touchdown equity actually lives.

### 5.2 Point-in-time rolling features

This is the step most homemade DFS models get wrong. Use windowed aggregates that **exclude the current row**:

```sql
CREATE OR REPLACE TABLE nfl_features.player_week_usage AS
SELECT
  gsis_id, season, week, team,

  -- Trailing 4-week averages, EXCLUDING current week (1 PRECEDING is the key)
  AVG(rz20_targets) OVER w4 AS rz20_targets_l4,
  AVG(rz10_targets) OVER w4 AS rz10_targets_l4,
  AVG(target_share) OVER w4 AS target_share_l4,
  AVG(air_yards_share) OVER w4 AS air_yards_share_l4,

  -- Season-to-date, also excluding current
  AVG(rz20_targets) OVER wstd AS rz20_targets_std,
  AVG(target_share) OVER wstd AS target_share_std,

  -- Trend: recent form vs season baseline
  SAFE_DIVIDE(AVG(target_share) OVER w4, AVG(target_share) OVER wstd) AS target_share_trend,

  COUNT(*) OVER wstd AS games_played_prior

FROM nfl_features.rz_receiving
WINDOW
  w4   AS (PARTITION BY gsis_id, season ORDER BY week
           ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
  wstd AS (PARTITION BY gsis_id, season ORDER BY week
           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING);
```

**Small-sample smoothing.** Red zone targets are high-signal but noisy — a WR might see 4 one week and 0 the next. Shrink toward a positional prior:

```sql
-- Empirical-Bayes style shrinkage; k is the prior weight in "games"
SAFE_DIVIDE(
  rz20_targets_sum + (k * position_prior_rz20_per_game),
  games_played_prior + k
) AS rz20_targets_smoothed
```

Tune `k` on validation data. Typical values land around 3–5 games for red zone metrics.

### 5.3 Feature inventory

**Volume / opportunity (the highest-value block)**
- Target share, air yards share, WOPR (1.5 × target share + 0.7 × air yards share)
- Red zone target share (20/10/5), goal-line carry share (inside 3)
- Snap share, route proxy (`snaps × team_pass_rate`)
- Team plays per game, seconds per play (pace), pass rate over expected

**Efficiency**
- Yards per target, yards per route proxy, aDOT
- YAC over expected, CPOE of the target's passer
- Broken tackle rate proxy from PBP

**Game context**
- Vegas implied team total ← *the single strongest feature*
- Spread, total, moneyline
- Expected game script: `implied_total - opponent_implied_total`
- Pace-adjusted expected plays
- Roof, surface, wind, temperature

**Opponent**
- EPA/dropback and EPA/rush allowed, last 6 weeks
- Positional fantasy points allowed, opponent-adjusted (raw "points allowed to WRs" is badly confounded by schedule — regress it against opponent strength)
- Blitz rate, pressure rate from FTN
- Red zone TD rate allowed
- Cornerback-group coverage quality (`017a_defense_week_coverage.sql`, from PFR advstats 2018+): yards per target and completion rate allowed by the opponent's CBs as nearest defenders, plus the whole secondary's yards per target, trailing 6 games. Group-level on purpose — free data can't say who covers whom (§2.5), but "this secondary gives up 9.1 yards/target" doesn't need to
- Top corner availability: `top_cb_out` flags the opponent's coverage-snap-leading CB (prior weeks only) listed Out on this week's injury report — the WR-side analogue of the next-man-up signal

**Player state**
- Injury designation and practice participation trend
- Games missed in prior 4 weeks
- Depth chart position and change from prior week
- Days of rest, travel distance, time zone shift

**DFS-specific**
- Salary, salary change from prior week
- Value (projected points per $1k)
- Slate size, number of games
- Teammate salaries (for correlation/stacking)

### 5.4 The strongest single derived feature

If you build only one thing beyond volume: **expected touchdowns from red zone opportunity**, smoothed.

```
xTD_receiving = rz10_target_share_smoothed
              × expected_team_rz10_pass_attempts
              × league_avg_rz10_target_TD_rate
```

where `expected_team_rz10_pass_attempts` comes from the implied team total and the team's historical red-zone pass rate. This decomposes TD scoring into a stable part (opportunity) and a noisy part (conversion), and lets you project the stable part while regressing the noisy part to league mean.

---

## 6. Modeling

### 6.1 Target variable

DraftKings NFL classic scoring:

| Event | Points |
|---|---|
| Passing yard | 0.04 |
| Passing TD | 4 |
| 300+ passing yards | +3 (bonus) |
| Interception thrown | −1 |
| Rushing yard | 0.1 |
| Rushing TD | 6 |
| 100+ rushing yards | +3 (bonus) |
| Reception | 1 (full PPR) |
| Receiving yard | 0.1 |
| Receiving TD | 6 |
| 100+ receiving yards | +3 (bonus) |
| Fumble lost | −1 |
| 2-pt conversion | 2 |
| Punt/kick/FG return TD | 6 |

The yardage bonuses are why you must model the **distribution**, not just the mean. A player projected at 85 receiving yards has meaningful probability mass above 100, and that bonus is worth 3 points roughly 30% of the time.

### 6.2 Recommended approach — component models

Don't predict DK points directly. Predict the components, then compose:

```
Model 1: expected targets           → Poisson / negative binomial
Model 2: catch rate | targets       → Beta regression or gradient-boosted classifier
Model 3: yards per reception        → Gamma regression
Model 4: TD probability             → Binary classifier on red zone features
Model 5: rush attempts, YPC, rush TD (parallel set for RBs)

→ Monte Carlo simulate 10,000 draws from the fitted distributions
→ Apply DK scoring to each draw, including bonuses
→ Report mean, p10, p50, p90, std, and P(20+ points)
```

This gives you ceilings and floors for free, which direct DK-points regression cannot. Ceiling is what wins GPPs; floor is what wins cash games.

**Algorithm:** LightGBM for each component. It handles the mixed feature types, missing values, and non-linearities without fuss, trains in seconds, and gives you SHAP values for free so you can sanity-check that the model is learning football and not artifacts.

### 6.3 Validation — the part that determines whether any of this works

**Walk-forward, never random split.** Random k-fold on NFL data leaks future information through team-season effects and will overstate your performance dramatically.

```
Train: 2015–2020  → Validate: 2021
Train: 2015–2021  → Validate: 2022
Train: 2015–2022  → Validate: 2023
Train: 2015–2023  → Validate: 2024
Train: 2015–2024  → Test: 2025 (touch once, at the very end)
```

**Metrics that matter, in order:**
1. **MAE vs. the market baseline.** Compare against "project each player at their prop line" or, absent props, at DK's own points-per-game figure. If you can't beat that, stop and fix features.
2. **Calibration of the distribution.** Do 10% of actuals fall below your p10? Plot it. Miscalibrated ceilings destroy GPP performance even with a good mean.
3. **Rank correlation within position.** Spearman on projected vs. actual within QB/RB/WR/TE. Lineup optimization only cares about ordering.
4. **Simulated contest ROI.** The only metric that pays. See §10.

**Expected performance, honestly:** a good public-data NFL DFS model achieves RMSE around 7–9 DK points for skill positions. The market's own implied projections are around 6.5–8. You are trying to close a small gap, and most of your edge will come from ownership leverage and correlation rather than raw projection accuracy. Set expectations accordingly.

---

## 7. Model training in depth

### 7.1 Assembling the training set

```sql
CREATE OR REPLACE TABLE nfl_features.player_week_training AS
SELECT
  -- Keys
  u.gsis_id, u.season, u.week, u.team, s.opponent, r.position,

  -- Features (all point-in-time; see §5.2)
  u.* EXCEPT (gsis_id, season, week, team),
  e.* EXCEPT (gsis_id, season, week),
  t.implied_team_total, t.spread, t.game_total, t.pace_l4, t.proe_l4,
  d.epa_per_dropback_allowed_l6, d.pos_fp_allowed_adj_l6, d.rz_td_rate_allowed_l6,
  i.injury_status, i.practice_participation_trend, i.games_missed_l4,
  w.wind_mph, w.temp_f, w.is_dome,
  dk.salary, dk.salary_delta_wow,

  -- Labels (multiple, for the component models)
  a.targets       AS y_targets,
  a.receptions    AS y_receptions,
  a.rec_yards     AS y_rec_yards,
  a.rec_tds       AS y_rec_tds,
  a.carries       AS y_carries,
  a.rush_yards    AS y_rush_yards,
  a.rush_tds      AS y_rush_tds,
  a.dk_points     AS y_dk_points

FROM nfl_features.player_week_usage u
JOIN nfl_features.player_week_actuals   a USING (gsis_id, season, week)
JOIN nfl_features.player_week_efficiency e USING (gsis_id, season, week)
JOIN nfl_features.team_week_context      t ON t.team = u.team AND t.season = u.season AND t.week = u.week
JOIN nfl_features.defense_week_allowed   d ON d.team = s.opponent AND d.season = u.season AND d.week = u.week
LEFT JOIN nfl_features.player_week_injury i USING (gsis_id, season, week)
LEFT JOIN nfl_features.game_weather        w USING (game_id)
LEFT JOIN nfl_features.dk_salary_week     dk USING (gsis_id, season, week)
JOIN nfl_features.schedule_long           s ON s.team = u.team AND s.season = u.season AND s.week = u.week
JOIN nfl_features.roster_position         r USING (gsis_id, season, week)
WHERE u.games_played_prior >= 1;
```

**Sample sizes you'll actually have** (2015–2025, regular season, players with ≥1 prior game):

| Position | Approx. rows | Notes |
|---|---|---|
| QB | ~7,000 | Small. Pool hyperparameters aggressively or use a single model with position as a feature. |
| RB | ~22,000 | |
| WR | ~38,000 | Largest and best-behaved |
| TE | ~16,000 | Bimodal — a handful of real receiving threats, a long tail of blockers |
| DST | ~6,000 | Model separately; features are entirely different |

**Positional models vs. one pooled model.** Start pooled with `position` as a categorical feature — you get regularization from cross-position signal and avoid QB's tiny sample. Split out per-position models only when you can demonstrate the split improves walk-forward validation. In practice WR and RB usually justify their own models; QB and TE usually don't.

### 7.2 Loss functions

Match the loss to the distribution of the label. This matters more than architecture choice.

| Label | Distribution | LightGBM objective |
|---|---|---|
| Targets, carries | Count, overdispersed | `poisson`, or `tweedie` with `tweedie_variance_power≈1.2` |
| Receptions given targets | Bounded count | `poisson` on receptions with `log(targets)` as offset |
| Receiving/rushing yards | Continuous, right-skewed, zero-inflated | `tweedie` (`variance_power≈1.5`) handles the zero mass properly |
| TDs | Rare count | `binary` on P(≥1 TD), then a separate multiplier for multi-TD games |
| DK points directly | Continuous, skewed | `tweedie`, or `quantile` for ceiling/floor models |

```python
import lightgbm as lgb

params_targets = dict(
    objective="poisson",
    metric="poisson",
    learning_rate=0.03,
    num_leaves=31,
    min_data_in_leaf=50,      # NFL data is small; guard against overfit leaves
    feature_fraction=0.7,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=5.0,
    verbosity=-1,
)

params_yards = dict(
    objective="tweedie",
    tweedie_variance_power=1.5,
    metric="tweedie",
    learning_rate=0.03,
    num_leaves=31,
    min_data_in_leaf=50,
    lambda_l2=5.0,
    verbosity=-1,
)
```

### 7.3 Quantile models — the cheap route to ceilings

If Monte Carlo composition (§6.2) feels like too much machinery for v1, train three quantile regressors on DK points directly and you get a usable distribution immediately:

```python
quantile_models = {}
for q in (0.10, 0.50, 0.90):
    quantile_models[q] = lgb.train(
        dict(objective="quantile", alpha=q, learning_rate=0.03,
             num_leaves=31, min_data_in_leaf=50, verbosity=-1),
        train_set, num_boost_round=800,
    )
```

This is strictly worse than component simulation — quantile models can produce crossing quantiles and don't respect DK's bonus thresholds — but it's ~30 lines and gives you a real GPP ceiling estimate in an afternoon. Ship this in Phase 3, replace it in Phase 4.

### 7.4 Recency weighting

NFL is non-stationary: rule changes, scheme evolution, and league-wide pass rate all drift. Weight training rows by exponential recency decay on season distance:

```python
import numpy as np

def sample_weights(df, target_season, half_life_seasons=3.0):
    age = target_season - df["season"].values
    return 0.5 ** (age / half_life_seasons)
```

Tune `half_life_seasons` on validation — typical optimum lands between 2 and 4. Shorter than 2 and you throw away signal; longer than 5 and you're modeling the 2015 NFL.

Do **not** apply recency weighting *within* a season at the row level in addition to your rolling features — you'd be double-counting recency and the model will chase noise.

### 7.5 Walk-forward hyperparameter tuning

```python
import optuna, numpy as np, lightgbm as lgb

FOLDS = [
    (range(2015, 2021), 2021),
    (range(2015, 2022), 2022),
    (range(2015, 2023), 2023),
    (range(2015, 2024), 2024),
]  # 2025 held out entirely as final test

def objective(trial):
    params = dict(
        objective="tweedie",
        tweedie_variance_power=trial.suggest_float("tvp", 1.1, 1.9),
        learning_rate=trial.suggest_float("lr", 0.01, 0.1, log=True),
        num_leaves=trial.suggest_int("leaves", 15, 63),
        min_data_in_leaf=trial.suggest_int("min_leaf", 20, 200),
        feature_fraction=trial.suggest_float("ff", 0.5, 1.0),
        lambda_l2=trial.suggest_float("l2", 0.1, 20.0, log=True),
        verbosity=-1,
    )
    maes = []
    for train_seasons, val_season in FOLDS:
        tr = df[df.season.isin(train_seasons)]
        va = df[df.season == val_season]
        m = lgb.train(
            params,
            lgb.Dataset(tr[FEATURES], tr[LABEL],
                        weight=sample_weights(tr, val_season)),
            num_boost_round=2000,
            valid_sets=[lgb.Dataset(va[FEATURES], va[LABEL])],
            callbacks=[lgb.early_stopping(100, verbose=False)],
        )
        maes.append(np.abs(m.predict(va[FEATURES]) - va[LABEL]).mean())
    return float(np.mean(maes))

study = optuna.create_study(direction="minimize")
study.optimize(objective, n_trials=150)
```

150 trials on 40k rows runs in a few minutes on a laptop. There is no reason to reach for Vertex AI training until you're doing something substantially heavier.

### 7.6 Cold starts: rookies and role changes

Every week you must project players with no usable history — rookies in week 1, a backup RB in his first start, a WR3 promoted after an injury. Your rolling features are all null and the model will do something arbitrary.

Handle explicitly with a fallback hierarchy:

1. **Depth chart + team context prior.** Project the *role*, not the player: "the WR1 on a team with a 25.5-point implied total, given this team's historical WR1 target share." This is usually within a point or two of a proper projection.
2. **Draft capital prior** for rookies. Round and pick number are decent predictors of rookie-year opportunity share. `load_draft_picks()` gives you this free.
3. **Athletic/combine prior** as a tiebreaker. Weak signal, but better than nothing. `load_combine()`.
4. **Explicit `is_cold_start` feature** so the model can learn to regress harder on these rows rather than trusting garbage nulls.

Never impute a cold-start player's rolling features with the league mean silently. Flag them, project them through the role-based path, and widen their variance.

### 7.7 Blending with the market

Your model and the market both contain information. Blending almost always beats either alone:

```python
final = w * model_projection + (1 - w) * market_implied_projection
```

Fit `w` on validation data via simple least squares. Realistic values land around 0.3–0.5 — meaning the market is carrying more than half the weight, which is a useful reality check on how much edge you actually have.

Where the market implied projection comes from prop lines: convert an over/under with a hit probability to an expected value assuming a reasonable distribution (Poisson for receptions, normal for yards). If you have no props, use DK's own `draftStatAttributes` points-per-game figure as a crude stand-in.

### 7.8 Monitoring and retraining

**Retrain weekly**, Tuesday, adding the completed week. Full retrain, not incremental — training is cheap and incremental updates accumulate drift.

**Model registry:** write every trained model to GCS as `models/{position}/{label}/{iso_week}/model.txt` plus a JSON sidecar with hyperparameters, feature list, training seasons, and validation metrics. Stamp `model_version` on every prediction row. When a week goes badly you need to be able to answer "which model made this call and what did it see."

**Drift alarms** — check weekly and alert:

| Signal | Threshold | Meaning |
|---|---|---|
| Rolling 4-week MAE vs. training MAE | > 1.3× | Model degrading; investigate before trusting |
| p10/p90 empirical coverage | outside 7–13% / 87–93% | Calibration broken; ceilings unreliable |
| Feature distribution PSI vs. training | > 0.2 on any top-10 feature | Upstream data change or genuine league shift |
| Null rate on any feature | > 2× baseline | Ingestion bug — check first, always |

**SHAP audit, monthly.** Pull global SHAP importances and eyeball the top 20. If `salary` or `week` is dominating your projections, the model has found a shortcut rather than learning football. If red zone target share and implied team total are near the top, it's learning the right things.

---

## 8. Knowledge graphs and trend detection

### 8.1 Honest framing

A knowledge graph will not improve your point projections. Gradient-boosted trees on tabular features are the right tool for that, and no graph structure changes it. Anyone selling you "knowledge graph DFS predictions" is selling you a vocabulary, not an edge.

What a graph genuinely gives you is four things trees can't:

1. **Entity resolution** across messy sources — the ID crosswalk problem from §4.3, generalized.
2. **Cascade reasoning** — "WR1 is out; who inherits his red zone targets, and by how much?" This is a traversal, not a regression.
3. **Relational features** that are awkward as columns — coaching lineage, scheme inheritance, quarterback-receiver pairing history.
4. **Explanation** — a chain of relationships you can show yourself when deciding whether to trust a projection.

Build it as a *feature source and a reasoning layer*, not as a predictor. Given the scale involved (~2,000 active players, 32 teams, ~285 games/season), the entire graph fits comfortably in memory. You do not need a graph database on day one; NetworkX in a Cloud Run job is genuinely sufficient. Reach for Neo4j Aura (free tier) or Spanner Graph only when you want persistent ad-hoc Cypher queries.

### 8.2 Schema

**Nodes**

| Type | Key properties |
|---|---|
| `Player` | gsis_id, name, position, draft_year, draft_pick, height, weight, age |
| `Team` | abbr, conference, division |
| `Game` | game_id, season, week, total, spread, roof, surface |
| `Coach` | name, role (HC/OC/DC), scheme_family |
| `Season` | year, league_pass_rate, league_pace |
| `Injury` | type, body_part, severity |
| `Scheme` | name (e.g. Shanahan wide zone, Air Raid, Erhardt-Perkins) |

**Edges**

| Relationship | From → To | Properties |
|---|---|---|
| `PLAYS_FOR` | Player → Team | season, week_start, week_end, depth_rank |
| `TARGETED_BY` | Player → Player (WR ← QB) | season, targets, rz_targets, air_yards, tds |
| `COMPETES_WITH` | Player → Player | same team, same position, target_share_correlation |
| `COACHED_BY` | Team → Coach | seasons |
| `LEARNED_FROM` | Coach → Coach | coaching tree lineage |
| `RUNS_SCHEME` | Coach → Scheme | |
| `PLAYED_IN` | Player → Game | snaps, targets, dk_points |
| `FACED` | Team → Team | game_id |
| `INJURED_WITH` | Player → Injury | date, games_missed, return_week |
| `REPLACED` | Player → Player | inherited_target_share, weeks |

The `COMPETES_WITH` and `REPLACED` edges are the ones that earn their keep. Target share is zero-sum within a team — that constraint is naturally a graph property and awkward as a tabular feature.

### 8.3 Building it from what you already have

```python
# graph/build.py
import networkx as nx
from google.cloud import bigquery

bq = bigquery.Client()

def build_graph(season: int, through_week: int) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()

    players = bq.query(f"""
        SELECT DISTINCT gsis_id, name, position, team
        FROM nfl_raw.rosters_weekly
        WHERE season = {season} AND week <= {through_week}
    """).to_dataframe()
    for r in players.itertuples():
        G.add_node(r.gsis_id, kind="Player", name=r.name, position=r.position)
        G.add_node(r.team, kind="Team")
        G.add_edge(r.gsis_id, r.team, key="PLAYS_FOR")

    # QB → receiver connections, weighted by red zone volume
    conn = bq.query(f"""
        SELECT passer_player_id AS qb, receiver_player_id AS wr, posteam AS team,
               COUNT(*) AS targets,
               COUNTIF(yardline_100 <= 20) AS rz_targets,
               SUM(air_yards) AS air_yards,
               COUNTIF(pass_touchdown = 1) AS tds
        FROM nfl_raw.pbp
        WHERE season = {season} AND week <= {through_week}
          AND pass_attempt = 1 AND receiver_player_id IS NOT NULL
        GROUP BY 1,2,3
    """).to_dataframe()
    for r in conn.itertuples():
        G.add_edge(r.qb, r.wr, key="TARGETED_BY",
                   targets=r.targets, rz_targets=r.rz_targets,
                   air_yards=r.air_yards, tds=r.tds)

    # Intra-team, intra-position competition edges
    for team, grp in players.groupby("team"):
        for pos, sub in grp.groupby("position"):
            ids = list(sub.gsis_id)
            for i, a in enumerate(ids):
                for b in ids[i+1:]:
                    G.add_edge(a, b, key="COMPETES_WITH", team=team, position=pos)
    return G
```

### 8.4 The query that actually pays: injury cascade

When a starter is ruled out Sunday morning, you have minutes to decide who absorbs his usage. This is the highest-value thing in this section.

```python
def project_vacated_usage(G, out_player_id, bq):
    """Who inherits an injured player's opportunity, and how much?"""
    team = next(t for _, t, k in G.out_edges(out_player_id, keys=True)
                if k == "PLAYS_FOR")
    pos  = G.nodes[out_player_id]["position"]

    # Vacated volume
    vac = bq.query(f"""
        SELECT AVG(rz20_targets) AS rz, AVG(total_targets) AS tgt,
               AVG(target_share) AS share
        FROM nfl_features.rz_receiving
        WHERE gsis_id = '{out_player_id}' AND season = @season
    """).to_dataframe().iloc[0]

    # Candidates: same team, same position group
    candidates = [b for _, b, k in G.out_edges(out_player_id, keys=True)
                  if k == "COMPETES_WITH"]

    # Historical redistribution: what happened the LAST time this player missed?
    prior = bq.query(f"""
        WITH absences AS (
          SELECT season, week FROM nfl_raw.injuries
          WHERE gsis_id = '{out_player_id}' AND game_status = 'Out'
        )
        SELECT r.gsis_id,
               AVG(IF(a.week IS NOT NULL, r.target_share, NULL)) AS share_without,
               AVG(IF(a.week IS NULL,     r.target_share, NULL)) AS share_with
        FROM nfl_features.rz_receiving r
        LEFT JOIN absences a USING (season, week)
        WHERE r.gsis_id IN UNNEST(@candidates)
        GROUP BY 1
    """, job_config=...).to_dataframe()

    prior["delta"] = prior.share_without - prior.share_with
    return prior.sort_values("delta", ascending=False)
```

This "what happened last time he was out" query is one of the few genuine free-data edges available, because it requires joining injury history to usage history in a way that no public site does for you. It works best for players with 3+ prior absences; below that, fall back to depth chart position and prior-season role.

### 8.5 Trend and regime-change detection

This is where you'll get more value than from the graph itself. The core insight: **rolling averages are lagging indicators of role change.** A WR promoted to WR1 in week 8 still has six weeks of WR3 usage dragging down his 4-week average. Detecting the *break* beats smoothing across it.

**Bayesian online changepoint detection** on target share:

```python
import numpy as np
from scipy import stats

def changepoint_probabilities(series, hazard=1/8, alpha=1.0, beta=1.0):
    """
    Online changepoint detection on a usage series (e.g. weekly target share).
    Returns P(run length = 0) per week — a spike means the role changed.
    hazard: prior probability of a change in any given week (1/8 ≈ twice a season)
    """
    T = len(series)
    R = np.zeros((T + 1, T + 1))
    R[0, 0] = 1.0
    mu, kappa, a, b = 0.0, 1.0, alpha, beta
    mus, kappas, as_, bs = [mu], [kappa], [a], [b]
    cp = np.zeros(T)

    for t, x in enumerate(series):
        pred = stats.t.pdf(
            x,
            df=2 * np.array(as_),
            loc=np.array(mus),
            scale=np.sqrt(np.array(bs) * (np.array(kappas) + 1)
                          / (np.array(as_) * np.array(kappas))),
        )
        R[1:t+2, t+1] = R[:t+1, t] * pred * (1 - hazard)
        R[0, t+1] = np.sum(R[:t+1, t] * pred * hazard)
        R[:, t+1] /= R[:, t+1].sum()
        cp[t] = R[0, t+1]

        # Conjugate updates
        mus_new    = [mu] + list((np.array(kappas) * np.array(mus) + x) / (np.array(kappas) + 1))
        kappas_new = [kappa] + list(np.array(kappas) + 1)
        as_new     = [a] + list(np.array(as_) + 0.5)
        bs_new     = [b] + list(np.array(bs) + (np.array(kappas) * (x - np.array(mus))**2)
                                / (2 * (np.array(kappas) + 1)))
        mus, kappas, as_, bs = mus_new, kappas_new, as_new, bs_new

    return cp
```

Use it two ways:

- **As a feature:** `weeks_since_changepoint` and `changepoint_prob_current_week`. Feed both to the model. It learns to discount stale history on its own.
- **As an alert:** flag every player with `cp > 0.5` this week. That list is your "somebody's role just changed" watchlist, and it is exactly where DFS value hides before salaries adjust.

**Simpler alternatives** if the above is more machinery than you want:

- **CUSUM** on target share with a tuned threshold — ~15 lines, catches most of the same breaks
- **Two-window t-test:** compare last 2 weeks against prior 6, flag `p < 0.05`
- **Slope of a rolling linear fit** on usage — crude but interpretable

**Salary lag as the actual edge.** DK sets salaries partly on recent production, which means salary responds to role change with roughly a one-to-two-week lag. A detected changepoint with a flat salary is the highest-value signal this system can produce. Build a specific alert for it:

```sql
SELECT p.display_name, p.team, c.changepoint_prob, c.weeks_since_change,
       dk.salary, dk.salary_delta_wow,
       u.target_share_l4, u.target_share_std
FROM nfl_features.changepoints c
JOIN nfl_features.dk_salary_week dk USING (gsis_id, season, week)
JOIN nfl_features.player_week_usage u USING (gsis_id, season, week)
JOIN nfl_features.player_id_map p USING (gsis_id)
WHERE c.changepoint_prob > 0.5
  AND c.weeks_since_change <= 2
  AND dk.salary_delta_wow < 500          -- salary hasn't caught up yet
ORDER BY c.changepoint_prob DESC;
```

### 8.6 Graph neural networks — probably not

You will be tempted. The honest assessment: GNNs on player-team-game graphs are a real research area and published results show modest gains over gradient boosting on NFL projection tasks — typically a few percent RMSE, sometimes nothing, and inconsistently across seasons. The cost is a large increase in complexity, a much harder debugging story, and a model you can't explain to yourself at 11am Sunday.

If you want to try it after everything in §7 is working, the sensible experiment is a small GraphSAGE over the team-week subgraph, using node features from your existing tabular pipeline, with the tabular GBDT prediction as an additional input feature. Evaluate on the same walk-forward folds. If it doesn't beat the GBDT by a margin you'd bet on, delete it. That's a Phase 8 project, not a Phase 4 one.

### 8.7 LLM-assisted news ingestion

The one place modern tooling adds something genuinely hard to replicate with SQL: unstructured beat-writer reporting. "Coach said they want to get him more involved in the red zone" is a real signal that appears nowhere in play-by-play, and it appears *before* the usage change shows up in your changepoint detector.

Practical pipeline:

1. Pull team beat-writer RSS feeds and official injury reports (Playwright is genuinely warranted here — many are JS-rendered).
2. Pass each item through an LLM with a strict extraction schema: `{player, entity_resolved_gsis_id, claim_type, direction, confidence, source_credibility}` where `claim_type` ∈ {role_change, snap_count, injury_status, scheme_change, depth_chart}.
3. Write extracted claims as edges into the graph with a timestamp and a decay.
4. Feed as a small number of aggregate features: `positive_role_signals_l7d`, `injury_concern_signals_l7d`.

Keep the LLM strictly in the extraction role. Do not let it generate projections — it will produce confident, fluent, uncalibrated numbers, which is the worst possible failure mode in a system where calibration is the whole game. Extraction is a task it does well; forecasting is not.

---

## 9. Lineup optimization

### 9.1 Constraints (DK NFL Classic)

- Roster: 1 QB, 2 RB, 3 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 DST = 9 players
- Salary cap: $50,000
- Minimum 2 different games represented
- No more than 8 players from one team (rarely binding)

### 9.2 Base optimizer

```python
import pulp

def optimize(players, budget=50000, locks=None, bans=None, banned_lineups=None):
    """players: list of dicts with keys id, name, pos, team, opp, salary, proj."""
    prob = pulp.LpProblem("dfs", pulp.LpMaximize)
    x = {p["id"]: pulp.LpVariable(f"x_{p['id']}", cat="Binary") for p in players}

    prob += pulp.lpSum(x[p["id"]] * p["proj"] for p in players)
    prob += pulp.lpSum(x[p["id"]] * p["salary"] for p in players) <= budget
    prob += pulp.lpSum(x.values()) == 9

    def count(pos):
        return pulp.lpSum(x[p["id"]] for p in players if p["pos"] == pos)

    prob += count("QB") == 1
    prob += count("DST") == 1
    prob += count("RB") >= 2
    prob += count("RB") <= 3
    prob += count("WR") >= 3
    prob += count("WR") <= 4
    prob += count("TE") >= 1
    prob += count("TE") <= 2

    for pid in (locks or []):
        prob += x[pid] == 1
    for pid in (bans or []):
        prob += x[pid] == 0

    # Uniqueness for multi-entry: forbid previously generated lineups
    for prev in (banned_lineups or []):
        prob += pulp.lpSum(x[pid] for pid in prev) <= 8

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    return [p for p in players if x[p["id"]].value() == 1]
```

### 9.3 Correlation and stacking

Optimizing on independent projections is the classic beginner error. DK is a winner-take-most format; you need correlated upside, not the highest expected value.

- **QB + 1–2 pass catchers from the same team.** A QB's ceiling game *requires* his receivers to score.
- **Bring-back:** add one player from the opposing team. Shootouts lift both sides.
- **Avoid:** RB + opposing DST (negatively correlated), and two RBs from the same team.

Implement as constraints:

```python
# If QB from team T is rostered, require ≥1 WR/TE from team T
for team in teams:
    qbs = [p["id"] for p in players if p["pos"] == "QB" and p["team"] == team]
    catchers = [p["id"] for p in players if p["pos"] in ("WR","TE") and p["team"] == team]
    prob += pulp.lpSum(x[i] for i in catchers) >= pulp.lpSum(x[i] for i in qbs)
```

Better still: run the optimizer against **simulated outcomes** rather than point projections. Generate 10,000 correlated game simulations (correlate within team via a shared game-environment factor), optimize a lineup for each simulation, and keep the lineups that appear most often. This bakes in correlation without hand-coded rules.

### 9.4 Cash vs. GPP

| | Cash (50/50, double-up) | GPP (tournament) |
|---|---|---|
| Objective | Maximize median | Maximize P(top 0.1%) |
| Use | `proj_p50`, minimize variance | `proj_p90`, maximize ceiling |
| Stacking | Minimal | Heavy — QB + 2 + bring-back |
| Ownership | Ignore | Critical — need leverage |
| Lineups | 1 | 20–150 with uniqueness constraints |

Without ownership data, approximate it: ownership correlates strongly with value (`proj / salary`) and with public narrative. A simple `predicted_ownership ~ f(value, salary_rank, team_total, recent_media_volume)` regression trained on any ownership data you can scrape post-hoc gets you most of the way.

### 9.5 Showdown Captain Mode (single-game slates)

DK's single-game format, offered for every game but most interesting for the standalone prime-time slates (Thursday and Monday night), where it's the only game in town. Rules, verified against DK's contest rules and the major strategy references:

- Roster: 6 spots — 1 **Captain (CPT)** + 5 **FLEX** — drawn from the two teams in one game.
- The captain scores **1.5x fantasy points** and costs **1.5x his FLEX salary**; the cap stays $50,000.
- At least one player from each team (5-1, 4-2, 3-3 splits all legal).
- Every position is FLEX- and CPT-eligible, **including K and DST** — kickers exist on showdown slates even though DK Classic dropped them. Scoring is otherwise identical to Classic (including the 100-yard and 40/50-yard FG bonuses).

Implementation (`optimizer/showdown.py`, endpoints in `app/main.py`):

- **Captain choice is part of the MILP**, not a post-hoc promotion: each player gets a CPT and a FLEX binary, the objective weights CPT picks 1.5x, and the cap constraint charges them 1.5x. The best captain is usually *not* the highest-projected player — the premium matters (there's a test asserting the optimizer benches an overpriced stud into FLEX).
- **Lineup identity includes the captain**: the same six players under a different captain is a distinct DK entry, and the multi-entry uniqueness constraint treats it that way (`max_overlap=5` default allows captain-swap variants; lower forces player-set diversity).
- **No stack rules** — in a single game everything is already correlated with the game environment; entry-to-entry diversity does the leverage work. Classic's `StackRules` deliberately don't apply.
- **Projections are reused from the classic pipeline** — no separate showdown inference job. The showdown player pool (latest `ingest-dk` snapshot, `slate_type='showdown'`, FLEX salaries) is joined to `player_projections` by `dk_player_id`; players the model doesn't project (K, DST) fall back to DK's own `dk_ppg` figure and are tagged `proj_source='dk_ppg'` in responses. Salaries always come from the showdown slate — DK prices the same player differently there than on classic slates.
- `GET /showdown/slates` lists upcoming Captain Mode games, filtered by kickoff day in US/Eastern (default `thu,mon`); `POST /showdown/lineups` defaults to the next upcoming Thursday/Monday game, and supports `locks`/`bans`, a forced `captain`, and the same `proj_points|p50|p90` objectives; `POST /showdown/lineups.csv` emits the `CPT,FLEX,FLEX,FLEX,FLEX,FLEX` DK upload format (CPT cells carry the CPT-slot draftable ID DK requires); `POST /showdown/lineups/entries.csv` fills a downloaded DKEntries.csv for contests already entered.
- **In the UI**: the Lineups page's slate dropdown lists every upcoming showdown game (all kickoff days, not just Thu/Mon) under a "Showdown (Captain Mode)" group alongside the classic slates. Choosing one builds Captain Mode entries — cards show the CPT slot at its 1.5x cost/projection — and the DK CSV button downloads the showdown upload file.

Strategy note baked into the defaults: cash-game showdown wants the chalk captain and `proj_points`; GPPs want `proj_p90` and captain diversity across entries, since captain leverage is where showdown tournaments are won.

---

## 10. Backtesting

The step that separates a model from a hobby.

1. **Reconstruct historical slates.** For each past week, take the DK player pool and salaries as they were.
2. **Generate projections** using only point-in-time features — verify no leakage by asserting that every feature's source rows have `week < target_week`.
3. **Build lineups** with your optimizer.
4. **Score** against actual DK points.
5. **Simulate contest outcomes.** Approximate the field: generate ~10,000 opposing lineups using ownership-weighted random selection from the player pool. Compute where your lineup would have placed. Apply the contest payout curve.
6. **Report ROI, not accuracy.** A model with worse RMSE can have better ROI if it's better calibrated on ceilings.

Run this over at least three full seasons. Single-season results are noise — the variance in DFS outcomes is enormous, and a bad model looks great over 17 weeks about as often as it looks bad.

---

## 11. Orchestration schedule

| Job | Cadence | Window |
|---|---|---|
| `ingest_nflverse` | Daily 06:00 CT | Year-round; nightly refresh matters in-season |
| `ingest_dk_slate` | Hourly | Thu 00:00 – Mon 04:00 CT |
| `ingest_odds` | Hourly | Thu 00:00 – Mon 04:00 CT |
| `ingest_weather` | 3× daily | Fri–Sun |
| `build_features` (dbt) | Daily 07:00 CT, and after each DK pull | |
| `run_projections` | Tue (initial), then hourly Sat–Sun | Late-swap requires fresh runs |
| `retrain_models` | Weekly, Tuesday | Add the completed week to training |

Cloud Scheduler cron → Cloud Run Jobs. Alert on job failure via Cloud Monitoring; a silently failing salary pull on Sunday morning is how you enter lineups with stale data.

---

## 12. Build roadmap

**Phase 1 — Data foundation (weekend 1–2)**
- GCP project, BigQuery datasets, GCS bucket
- nflverse full backfill 1999–present
- DK slate ingestion running hourly
- Player ID crosswalk with an unmatched report

*Done when:* you can query "top 20 WRs by red zone target share, last 4 weeks, with their current DK salary" in one SQL statement.

**Phase 2 — Features (weekend 3–4)**
- Red zone tables, rolling point-in-time features, opponent adjustments
- Vegas implied totals from schedules
- Automated leakage test in CI

*Done when:* `player_week_training` builds end to end and passes leakage assertions.

**Phase 3 — Baseline model (weekend 5–6)**
- LightGBM on DK points directly — deliberately crude
- Walk-forward validation vs. the market baseline
- This is your floor; everything after must beat it

*Done when:* you have an honest MAE number and know whether you're beating the market.

**Phase 4 — Component models + simulation (weekend 7–9)**
- Separate target/catch/yards/TD models
- Monte Carlo composition with DK bonuses
- Calibration plots for p10/p50/p90

**Phase 4.5 — Trend detection (weekend 9)**
- Changepoint detection on target share and snap share (§8.5)
- `weeks_since_changepoint` fed back as a model feature
- Salary-lag alert query

*Done when:* your Tuesday report names 5–10 players whose role just changed, and you recognize most of them as correct.

**Phase 5 — Optimizer (weekend 10)**
- PuLP constraints, stacking rules, multi-lineup uniqueness

**Phase 6 — Backtest (weekend 11–12)**
- Field simulation, payout curves, ROI over 3+ seasons
- **Do not risk money before this phase completes.**

**Phase 7 — Interface**
- Cloud Run + FastAPI, or Streamlit for speed
- Slate view, projections table, lineup builder, exposure summary
- CSV export in DK's upload format

**Phase 8 — Optional extensions, in value order**
1. Graph-based injury cascade projection (§8.4) — highest ROI of the three
2. LLM news extraction into graph edges (§8.7)
3. GNN experiment (§8.6) — only if 1 and 2 are done and you're bored

---

## 13. Pitfalls

| Pitfall | Consequence | Fix |
|---|---|---|
| Random train/test split | Backtest looks 30% better than reality | Walk-forward only |
| Rolling features including current week | Catastrophic leakage; near-perfect backtest, useless live | Window with `1 PRECEDING` upper bound |
| Name-based player joins | Silent drops, wrong salaries | ID crosswalk + fail loudly on unmatched |
| Optimizing on independent projections | Uncorrelated lineups, no ceiling | Stack constraints or simulation-based optimization |
| Ignoring the market | Reinventing a worse version of the closing line | Always benchmark against Vegas/props |
| Overweighting last week | Chasing noise | Shrinkage toward positional priors |
| Trusting a single season backtest | False confidence | 3+ seasons minimum |
| Forgetting DK bonuses | Systematic underprojection of high-yardage players | Simulate the distribution |
| Hammering the DK endpoint | Endpoint locked down for everyone | Reasonable rate limits, real User-Agent, caching |
| Not logging your own DK pulls | Permanently missing historical salary data | Append-only log from day one |

---

## 14. Reference links

**Data**
- nflverse data releases — `github.com/nflverse/nflverse-data/releases`
- nflreadpy — `github.com/nflverse/nflreadpy`
- nflreadr docs (field descriptions apply to both) — `nflreadr.nflverse.com`
- nflfastR field descriptions — `nflfastr.com/articles/field_descriptions.html`
- RotoGuru historical DFS salaries — `rotoguru1.com/cgi-bin/fyday.pl`
- nfldfs package — `github.com/Brian-Doucet/nfldfs`
- Open-Meteo (free weather, no key) — `open-meteo.com`

**Learning**
- Open Source Football — `opensourcefootball.com` (nflverse community analytics writeups)
- nflfastR beginner's guide — linked from `nflfastr.com`

**Legal / ToS reminder**
DK's public JSON endpoints are undocumented, not licensed. Personal analytical use is the norm; redistributing the data or building a commercial product on it is a different question. Check your state's DFS regulations, and if this ever becomes a product rather than a project, talk to a lawyer — I'm not one.

---

## 15. Quick start

```bash
# Local dev
python -m venv .venv && source .venv/bin/activate
pip install nflreadpy pandas polars google-cloud-bigquery google-cloud-storage \
            lightgbm scikit-learn pulp requests pyarrow dbt-bigquery

# GCP setup
gcloud projects create nfl-dfs-prod
gcloud config set project nfl-dfs-prod
gcloud services enable bigquery.googleapis.com run.googleapis.com \
                       cloudscheduler.googleapis.com secretmanager.googleapis.com
bq mk --dataset --location=US nfl_raw
bq mk --dataset --location=US nfl_features
bq mk --dataset --location=US nfl_predictions
gsutil mb -l US gs://nfl-dfs-prod-raw

# First backfill (takes ~15 min, ~2 GB)
python ingest/nflverse_job.py --full
```

Then write the red zone query from §5.1 and look at the output. If the names at the top of that list look like the players you'd expect to be scoring touchdowns, your pipeline is correct and everything else is refinement.
