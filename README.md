# NFL DFS — prediction and lineup construction

A DraftKings NFL daily-fantasy system built on free data and Google Cloud:
it ingests public NFL and slate data into BigQuery, engineers strictly
point-in-time features, trains per-position distribution models, simulates
correlated game outcomes, and constructs tournament lineup portfolios
optimized for the extreme upper tail rather than for average points.

The program's objective is unusual and shapes every design choice: it is
tuned to maximize the **weekly best lineup score** in large-field
tournaments, not expected value or cash-game win rate. Operator target is a
mean weekly maximum near 194 DK points.

> **Resuming work, changing machines, or picking up someone else's thread?**
> Read [`HANDOFF.md`](HANDOFF.md) first — it is the tracked, authoritative
> record of current state, in-flight work, and the next concrete action.
> This README describes how the system is built and run; it does not track
> what is running right now.

**Document map**

| Document | Purpose |
|---|---|
| `README.md` (this file) | Overview, architecture, setup, orchestration, CLI |
| [`HANDOFF.md`](HANDOFF.md) | Authoritative current state — read before any work |
| [`CLAUDE.md`](CLAUDE.md) | Working rules for agents and humans: validation laws, frozen-chain lessons, hard constraints |
| [`docs/design-guide.md`](docs/design-guide.md) | The original §0–§14 design guide: data sources, schema, feature/model theory, optimizer and backtest design |
| [`reports/`](reports/) | Experiment protocols, run receipts, and result records. **Not all of it is adopted** — many documents are proposals or superseded analyses. Code and `HANDOFF.md` win on any conflict |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│ SOURCES (free / licensed-by-operator)                                    │
│  nflverse (pbp, rosters, injuries, depth charts, NGS, PFR advanced)      │
│  DraftKings public endpoints (slates, salaries, contests)                │
│  The Odds API (game lines, props) · Open-Meteo (weather)                 │
│  Operator-supplied vendor CSVs (SIS, FantasyPoints, contest standings)   │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  src/nfl_dfs/ingest/   (nfl-dfs ingest-*)
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ BIGQUERY — the only database. No local-data mode.                        │
│                                                                          │
│   nfl_raw          landed source tables, append-only where possible      │
│        │  sql/features/*.sql  +  src/nfl_dfs/features/leakage.py         │
│        ▼                                                                 │
│   nfl_features     point-in-time panels: usage, roles, defense, market,  │
│                    weather, archetypes, injury/vacated-opportunity       │
│        │           ── LAW: week W sees only weeks < W (windows end at    │
│        │              1 PRECEDING); leakage checks gate every build      │
│        ▼                                                                 │
│   nfl_predictions  projections, candidate pools, portfolios, shadows,    │
│                    research panels, contest/ownership imports            │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
┌────────────────┐   ┌──────────────────────┐   ┌────────────────────────┐
│ MODELS         │   │ INFERENCE            │   │ RESEARCH               │
│ models/        │   │ inference/           │   │ research/, analysis/   │
│ per-position   │   │ market blend (45/55) │   │ frozen one-shot arms,  │
│ components,    │──▶│ cold-start fills,    │   │ audits, censuses,      │
│ ensembling,    │   │ injury cascade,      │   │ law/dependence studies │
│ conformal/CQR, │   │ conformal intervals  │   │ (adopt only on proof)  │
│ registry       │   └───────────┬──────────┘   └────────────────────────┘
└────────────────┘               │
        │                        ▼
        │            ┌──────────────────────────────────────────────┐
        └───────────▶│ SIMULATION — models/game_sim.py              │
                     │ drive-state possession engine → correlated   │
                     │ player draws (worlds). Tail behavior of the  │
                     │ whole program rides on this joint law.       │
                     └───────────────────┬──────────────────────────┘
                                         ▼
                     ┌──────────────────────────────────────────────┐
                     │ CONSTRUCTION — optimizer/ + backtest/        │
                     │ candidate families (boom / lev / role / qbvar│
                     │ / game / dark) solved per world under DK     │
                     │ rules + stack mandates and a $49k floor;     │
                     │ CBWU selects an 80-entry book across five    │
                     │ 10,000-world blocks for line-194 coverage    │
                     └───────────────────┬──────────────────────────┘
                                         ▼
        ┌────────────────────────────────┴─────────────────────────┐
        ▼                                                          ▼
┌────────────────────────┐                        ┌────────────────────────┐
│ APP — app/ (FastAPI)   │                        │ BACKTEST / REPLAY      │
│ slate views, lineups,  │                        │ backtest/replay.py     │
│ market/defense pages,  │                        │ walk-forward panels,   │
│ DK CSV export, chat    │                        │ 54/107-slate corpora   │
└────────────────────────┘                        └────────────────────────┘
```

**Package layout** (`src/nfl_dfs/`, 284 modules):

| Path | Contents |
|---|---|
| `ingest/` | Source loaders: nflverse, DK slates/contests, odds, weather, vendor CSV importers |
| `features/` | Feature build driver and the leakage checker that gates every build |
| `models/` | Component models, ensembling, calibration, conformal, registry, possession simulator, pricing lag |
| `inference/` | Live projection assembly: market blend, cold start, cascade adjustment, market-implied quantiles |
| `optimizer/` | PuLP lineup solving, stacking rules, portfolio selection, DK CSV, showdown |
| `backtest/` | Replay engine, candidate generation, field simulation, payouts; the score-relevant lever registry |
| `research/` | Frozen experimental machinery — world models, dependence, evidence, tail studies, governance leases |
| `analysis/` | Audits and diagnostics: archetypes, winner-law audits, attribution, censuses |
| `graph/`, `trends/` | Player/team graph with injury cascade; changepoint and salary-lag detection |
| `app/` | FastAPI service and static UI (52 routes) |
| `ops/` | Vendor download helpers and operational utilities |

`sql/` holds BigQuery DDL and transforms (`raw/`, `features/` — 31 files,
`predictions/`, `audits/`). The tokens `${raw}`, `${features}`,
`${predictions}`, and `${prior_k}` are substituted by `bq.run_sql_file`.
`tests/` holds 292 offline test modules; `scripts/` holds 493 files (316 of
them shell) — research runners, cloud chain drivers, and watchers.

---

## Local setup

### Requirements

- **Python 3.11+** (the container image is `python:3.11-slim`).
- **A GCP project with BigQuery** for anything touching data. BigQuery is
  the only database — there is no local-data mode. Code work and the full
  test suite run entirely offline.
- **`gcloud` / `bq` / `gsutil`** authenticated for pipeline and cloud work.
- **libgomp** for LightGBM on Linux (`apt install libgomp1`).

### Install

```bash
python -m venv .venv && source .venv/bin/activate

pip install -e ".[dev,app]"      # code work + tests + the web app
pip install -e ".[dev,app,gcp]"  # add BigQuery/GCS/nflverse for pipeline work
```

Optional extras: `browser` (Playwright), `tuning` (Optuna).

### Run the tests

```bash
source .venv/bin/activate
pytest                       # entire suite, offline, no GCP needed
pytest tests/test_sbi.py     # a single targeted module
```

The suite is fully offline: `tests/conftest.py` builds a synthetic
player-week panel, and golden-hash parity tests pin the default simulation
draws so an accidental RNG-order change fails loudly.

> **Machine constraint (see `CLAUDE.md`):** this workstation has crashed
> under parallel load. Run **one** targeted test module or query at a time;
> never run parallel agents, parallel pytest, or local simulations. All
> heavy compute belongs on Cloud Run.

### Configuration

All configuration is environment variables, read in
[`src/nfl_dfs/config.py`](src/nfl_dfs/config.py). A gitignored `.env` in the
working directory is loaded automatically and never overrides real
environment variables.

| Variable | Default | Purpose |
|---|---|---|
| `GCP_PROJECT` | `nfl-dfs-prod` | Project id |
| `BQ_LOCATION` | `US` | Dataset location |
| `BQ_RAW_DATASET` / `BQ_FEATURES_DATASET` / `BQ_PREDICTIONS_DATASET` | `nfl_raw` / `nfl_features` / `nfl_predictions` | Dataset names |
| `GCS_BUCKET` | `${GCP_PROJECT}-raw` | Artifacts, model registry, research receipts |
| `MODEL_REGISTRY_PREFIX` | `models` | Registry prefix within the bucket |
| `FIRST_SEASON` / `TRAIN_FIRST_SEASON` | `2014` / `2015` | Backfill start; training start |
| `ODDS_API_KEY`, `SPORTSDATA_API_KEY` | empty | Vendor keys — keep in `.env`, never in the repo |

Research and simulation levers are the deliberate exception: they are read
from the environment at their call sites, and **every score-relevant lever
must be registered in `backtest.engine._lever_keys`** so that treatments are
self-identifying in the warehouse. `tests/test_lever_registry.py` enforces
that partition.

### One-time GCP setup

```bash
export GCP_PROJECT=your-project
bash deploy/setup_gcp.sh       # enables APIs, creates datasets + bucket, applies raw DDL
bash deploy/deploy_jobs.sh     # builds the image, deploys Cloud Run Jobs + Scheduler
```

### First run

```bash
nfl-dfs ingest-nflverse --full   # backfill (FIRST_SEASON onward)
nfl-dfs build-features           # feature SQL + leakage checks (must pass)
nfl-dfs train                    # weekly retrain + registry write
nfl-dfs project                  # project the upcoming slate
nfl-dfs serve                    # FastAPI app on localhost
```

---

## The `nfl-dfs` CLI

`nfl-dfs` is the single entry point: every pipeline job, importer,
diagnostic, and shadow-portfolio freeze is a subcommand, defined in
[`src/nfl_dfs/cli.py`](src/nfl_dfs/cli.py) and dispatched to a module under
`src/nfl_dfs/`. Cloud Run Jobs invoke exactly these subcommands, so anything
that runs in production can be reproduced locally by name.

```bash
nfl-dfs --help                 # every subcommand
nfl-dfs build-features --help  # flags for one subcommand
```

There are 116 subcommands. They fall into families:

| Family | Examples | What they do |
|---|---|---|
| **Ingest** | `ingest-nflverse`, `ingest-dk`, `ingest-odds`, `ingest-weather`, `ingest-contests` | Land source data in `nfl_raw` |
| **Import** (operator-supplied) | `capture-dk-standings`, `import-ownership`, `import-prop-lines`, `import-sis-*`, `import-fantasy-points-*` | Validate/archive manual source files and load them into the warehouse |
| **Build / train / project** | `build-features`, `train`, `project` | The weekly production path |
| **Shadow freezes** | `shadow-k1`, `shadow-k3`, `shadow-cbwu-oi-paired`, `shadow-*-paired` | Freeze pre-lock prospective portfolios for later grading — the only legitimate route to adopting a change |
| **Grade / score** | `grade-tail-portfolios`, `score-entries`, `field-calibration` | Score frozen books once actuals land |
| **Backtest** | `replay`, `replay-showdown` | Walk-forward replay over historical seasons |
| **Diagnostics** | `*-diagnostic`, `*-audit`, `leaderboard-analysis`, `missed-player-analysis` | Read-only measurement; adopt nothing by themselves |
| **Ops** | `check-freshness`, `backup-tables`, `check-odds-quota`, `trends` | Health, backups, quota, alerting |
| **Serve** | `serve` | FastAPI app (slate views, lineups, market/defense pages, DK CSV export) |

Separate console scripts exist for operator-side vendor downloads:
`fantasy-points-download`, `fantasy-points-matchups`,
`fantasy-points-ownership`, `sis-download`, `nfl-weekly-data`.

---

## How development and orchestration work

Two loops run side by side: a **production cadence** that must stay boring
and reproducible, and a **research program** that must never contaminate it.

### Production cadence (Cloud Run Jobs + Cloud Scheduler)

`deploy/deploy_jobs.sh` defines every job and schedule; jobs are thin
wrappers around `nfl-dfs` subcommands on one immutable container image.
The in-season weekly rhythm:

| When | Job | Purpose |
|---|---|---|
| Daily (in-season) | `s-nflverse` | Pull nflverse, giving the injury collector real pre-lock observation times |
| Tue 06:30 | `s-features` | Rebuild feature tables (leakage checks gate it) |
| Tue 07:30+ | `s-train*` | Retrain the production and isolated-treatment registries |
| Thu | `s-features-route`, `s-train-k1-route*` | Rebuild after licensed Route Share lands |
| Tue 09:30 / Sun hourly | `s-project-tu`, `s-project-su` | Project the upcoming slate |
| Sun ~10:30 and ~11:20 | `s-shadow-*` | Freeze pre-lock portfolios twice — the early run survives a late failure, the late run sees inactives |
| After actuals | grading jobs | Score the frozen books |

Schedulers are **paused in the off-season** and resumed before Week 1.
Pausing or resuming them is an operator decision.

### Research program (frozen one-shot experiments)

Research runs as isolated, preregistered arms — never as edits to the
production path. The standard chain, encoded in `scripts/*.sh`:

1. **Design and implement** the mechanism under `research/` or `analysis/`
   with offline unit tests.
2. **Outcome-blind reality smoke** against the real artifacts the runner
   will consume — required *before* freezing (`CLAUDE.md` frozen-chain
   rule 1; synthetic contract tests alone have shipped three schema
   defects into a frozen runner).
3. **Freeze** a protocol document pinning file SHAs, inputs, the fixed
   budget, and the preregistered reading of every possible outcome.
4. **Build** a clean-archive image from the exact commit
   (`gcloud builds submit` with an `_IMAGE` tag binding image to code).
5. **Launch** by *reusing* an existing Cloud Run job via
   `gcloud run jobs deploy` plus per-execution `--args` — never creating
   per-cell jobs (us-central1 sits at the JobsPerProject=1000 quota).
6. **Watch** with a detached watcher writing a durable log in
   `~/nfl-panels/`, so a crashed workstation never loses the run.
7. **Aggregate** create-only, then record the verdict in `reports/` and
   `HANDOFF.md`.

Governance that keeps this honest:

- **One active historical-outcome experiment at a time**, enforced by a
  durable GCS lease (`research/historical_outcome_lease.py`) with
  generation-matched acquire/release/abandon.
- **Fixed budgets and exact pairing** — a treatment may never spend more
  candidates than its control.
- **Audit before verdict** — instrument and code audits have caught three
  invalid arms that the panel numbers would have sworn were real.
- **Content-identity receipts** (`research/object_identity.py`): compare
  artifacts by uri/generation/sha256/bytes, never by representation.
- **Walk-forward only**, never random splits; no retrospective tuning on
  historical corpora.

`bash scripts/chain_status.sh` prints a one-shot status of every chain
(live processes, logs, cell grids, builds, job executions, lease, recent
events); `--watch` is the same view as a live full-screen dashboard where
`1-6` streams a build's log, `a-h` streams a job execution's log (the
experiment cells themselves), and `x` opens a browser over the retained
result JSONs in `reports/*-runs/` — every score-affecting run commits its
receipts there, so the browser doubles as the review tool for past
experiments (`--experiments` / `--result <substr>` are the scriptable
forms).

### Working rules

[`CLAUDE.md`](CLAUDE.md) is binding for humans and agents alike. The
non-negotiables:

- **Point-in-time is sacred.** Week W sees only weeks < W. Never weaken a
  leakage check to make a build go green.
- **Keep the handoff in the repository.** Update `HANDOFF.md` at every
  material milestone and before any pause or machine move; commit it with
  the code it describes.
- **Log every data deficiency** in the table below.
- **Never put credentials in the repo or the handoff.**
- Frozen-chain lessons 1–5 (reality smokes, content identity, no
  self-hash pinning, sweep the whole defect class, reuse cloud jobs).

---

## Known gaps and future enhancements

Repo-specific items, distinct from the design guide's roadmap (§12).

**User-supplied lineup analyzer — future task (requested 2026-08-08).** Add a
UI workflow that accepts a lineup either by selecting players from the active
slate or by uploading a DraftKings-exported CSV/spreadsheet. Resolve players
by slate-specific draftable ID where available, preserve the source slate and
upload provenance, and hard-check roster shape, salary cap, matchup/slate,
duplicate-player, and lock-time legality before analysis. Report the lineup's
model projection and simulated distribution, threshold/tail probabilities,
stack and bring-back structure, ownership/leverage, correlation and game
concentration, estimated duplication risk, weak links, and clearly explained
pivot opportunities. Keep analysis separate from contest entry or lineup
mutation, and test both UI-selected and uploaded-lineup paths against the same
analysis contract.

**Historical DK salary gap, 2022–2024** *(2026-08-01 audit: 2025 is now covered — 18 weeks in `dk_salaries_historical` via the DiscoveryLab import — so the gap is three seasons, not four)*. RotoGuru stopped publishing DraftKings salary data after the 2021 season, so `backfill-rotoguru` covers 2014–2021 only. Training rows for 2022–2024 have null `salary` / `salary_delta_wow` features — LightGBM handles missing values natively and leans on usage/Vegas features for those seasons, so training works, but backtests over 2022–2025 can't use salary-based lineup construction at realistic prices. From the 2026 season onward this heals itself: the hourly `ingest-dk` snapshots become our own append-only salary log. Closing the historical gap would require a paid data source or a community archive; decide whether it's worth it only if recent-season backtests become important.

**Contest entry rosters never landed (2026-08-19).** `contest_entries` has never received a row — only `contest_ownership` is populated (2022–2025, 18 weeks per season). DK purges standings exports after ~4 days, so historical field rosters are unrecoverable; the 51 tracked Millionaire winners are the entire observation of the field for those seasons. The September Monday/Tuesday standings downloads are therefore load-bearing: they are the only path to a measured effective field size, a field model, and a winner set larger than the tracked first-place rosters. The 2026 manual workflow is now hardened but still unexercised: [`capture-dk-standings`](docs/dk-full-field-capture.md) validates exact field size and settlement by default, then only with explicit settlement/full-field confirmations plus `--apply` archives the raw CSV create-only and uses retry-safe warehouse loads. The gap stays open until the first real settled contest passes capture and backup verification.

**Local demo mode (no GCP).** The web app reads projections from BigQuery; there is no local-database path today. The seam already exists — `app/store.py` defines the `ProjectionStore` protocol and an `InMemoryStore` used by the tests — so a `nfl-dfs serve --demo` flag that loads a projections parquet/CSV from disk would let someone try the UI and optimizer without a GCP project. Small change, unimplemented.

**Showdown Captain Mode.** Single-game Captain Mode lineups are built by `optimizer/showdown.py` + the `/showdown/*` endpoints, reusing classic-pipeline projections joined by DK player id. Deliberately deferred: (a) K and DST ride on DK's `dk_ppg` figure rather than a model; (b) no showdown backtest — `backtest/` replays classic contests only, so showdown lineup quality is unvalidated beyond the optimizer's unit invariants; (c) no simulated-outcomes mode — captain leverage from correlated draws would be the next construction improvement.

**Overlay detection — polling scaffold, unvalidated.** `ingest/contest_job.py` (`nfl-dfs ingest-contests`, gated by `INGEST_CONTESTS_ENABLED`) polls DK's lobby contest list and lands fill-rate/overlay snapshots in `nfl_raw.dk_contest_fills` (NFL analysis should read the `dk_contest_fills_nfl` view — the table also holds CFB rows, discriminated by `sport`). This is infrastructure only: a single poll can't distinguish overlay from a contest that fills late the way real GPPs do, so it isn't wired into the Scheduler cadence. Before adopting, poll by hand through a live slate's approach to lock and see whether `overlay_dollars` tracks anything an experienced player would recognize as real overlay.

**CFB data collection — scaffold only, no adoption decision.** `ingest/cfb_job.py` (`nfl-dfs ingest-cfb`, gated by `INGEST_CFB_ENABLED`) polls DK's CFB draft groups/contests into `nfl_raw.cfb_dk_salaries` and `dk_contest_fills`. Collection only, by request: no CFB feature SQL, no model changes, no optimizer roster-shape support (CFB's QB/2RB/3WR/FLEX/Superflex is not DK NFL Classic). The intent is to leave behind a backtestable dataset for a later go/no-go call.

**Archetype clustering — deferred pieces.** `nfl-dfs archetypes` (`analysis/archetypes.py`) clusters players into scoring-consistency archetypes, stamps them on graph nodes for the injury cascade, and adds `SIMILAR_TO` edges for profile-based pivots. Left out of v1: graph-derived clustering inputs (QB-attachment stability, target-room crowding); salary/ownership-aware pivot ranking; and a scheduled refresh — the table is CLI-only.

### Data deficiency log

Append-only. Whenever a gap or quality problem is found in source data, add a
row here (see `CLAUDE.md`) so future decisions about fixing versus accepting
are made from a complete list. Rows below are preserved verbatim across the
2026-08-19 README rewrite.

<!-- DATA-DEFICIENCY-LOG:START -->
| Found | Deficiency | Impact | Status |
|---|---|---|---|
| 2026-08-22 | The Millionaire winner source files are not one clean source of truth: `milly-winners-2019-2023-2024.csv` duplicates 2024 Week 9 (a copy of Week 7), has one missing salary and five raw salary totals above $50,000; `milly_rosters_2023_2024.csv` (31 article-derived winners) agrees with the canonical user-supplied file on only 18 of 30 shared slate-key winning scores; the 2025 summary companion lacks `salary_used` in three weeks; older consumers that skip the dedup can expose 69 keys while a stale README statement cited 65. The canonical loader `real_winner_overlap.py` (68 winners, 17 per covered season) is the only current analytical authority, and no winner row carries source URL, contest ID, capture time, or an immutable source receipt | Different model paths can silently learn from different winner populations, and winner-based fill/retrieval work (winner-support density, matched-control enrichment) cannot be receipted or reproduced against provenanced inputs | **Open — Phase 0 of the offseason roadmap** (`reports/2026-08-22-offseason-corpus-fill-and-selection-roadmap.md` §12.1, adapted in `reports/2026-08-22-foundry-roadmap-adaptation.md`): reconcile into one canonical 68-contest registry with contest ID, slate universe, canonical player IDs, score/salary/ownership provenance and immutable receipts; preserve the governed 51-winner cohort as a versioned subset |
| 2026-08-18 | The authoritative DST DK-score source has **zero coverage for 2022, 2023 and 2024** (0 of 1,630 team-game rows) and 16 missing rows in 2025; where it does exist, it disagrees with the nflfastR event reconstruction on a stable ~2.3% of rows (37/1,584 panel-season rows; 162/4,656 overall, 2014 an outlier at 11.7%). Deltas are 97% +/-1..3; points-allowed tier boundaries are refuted as the cause (mean distance to tier edge 1.62 mismatched vs 1.66 matched) and excluded non-DST points explain only 3 of 41 | Phase D0 gate 3 ("explain or repair every authoritative/reconstruction mismatch") cannot pass as written: three of six panel seasons have nothing to reconcile against, and the residual disagreement has no identified single cause. Blocks the DST world-model work that would give the 9th roster slot non-zero variance | **Open — gate 3 requires a protocol decision**, either accepting a bounded mismatch rate with a named canonical source, or per-row play-by-play forensics. Gates 1, 2 and 4 passed; receipts in `reports/dst-d0-runs/20260818-dst-d0-rebuild-v1/` |
| 2026-08-15 | The inherited G1 terminal loader queried accepted panel rows without an `ORDER BY`, then used that undefined BigQuery result order as both frame and player-world row order | Within-execution repeats could pass from query caching while independent immutable executions produced different frame/draw byte hashes and sub-`1e-15` reduction-order noise, defeating the SIS reference's cross-run identity gate | **Repair2 frozen before treatment/calibration** — canonically sort `(season, week, gsis_id, position)` and apply the same permutation to draws; preserve the original and first repair as invalid, require exact internal repetition plus a strict `1e-12` structural cross-report comparison before calibration |
| 2026-08-15 | nflverse's completed 2025 injury file has 6,068 rows and 2,783 report-status rows, but `date_modified` is NULL on every row; the strict common-lock repair therefore correctly admits no 2025 injury status | Completed-season rows cannot be reconstructed as pre-lock observations, and the same upstream behavior in 2026 would silently remove the practice/injury-vacancy signal unless the system preserves its own observation times | **Prospective repair implemented without backdating** — `ingest-nflverse` appends only the active planning season to collector-time `injury_snapshots`; the feature and independent leakage reference admit a snapshot only when `pulled_at <=` the common Sunday-main lock and reject a source timestamp later than the observation. The in-season collector now runs daily, freshness pages after 36 hours, and daily backups preserve this irrecoverable table. Completed 2025 remains unavailable rather than being stamped with a 2026 pull time |
| 2026-08-13 | SIS Team Passing Value submits the correct `MetricGroupSubType=1.3` and its API response contains Value metrics, but the split-by-game rendered table and Download revert to the Passing Totals schema; 14 acquired Passing Totals/Value pairs are byte-identical | Those 14 files cannot supply lagged passing Boom%/Bust% or value metrics and would silently duplicate volume if trusted by filename; other tranche-2 families and the earlier QB-line source are unaffected | **Failed closed and quarantined** — the exporter now verifies exact subtype plus report-specific rendered/CSV columns. The merged run-context importer requires the exact original/recovery plans and states, proves the stale-view hashes, explicitly excludes every Passing Value artifact, and accepts only Passing Totals, Rushing Totals/Value, and Run Defense Totals/Value. Passing Value remains unavailable at game grain until a distinct normal-UI workflow passes both rendered and downloaded schema guards |
| 2026-08-13 | SIS DataHub Pro trial Pass Defense CSV is capped at 20 rows, exports `Rank` as literal `[object Object]`, and has no stable player/game ID. A first retry remained full-season only because Submit was not pressed; the correctly submitted full-2025 Split-by-Game CSV adds `Week`/`Opp.`, has `Games=1`, and differs from the aggregate | The successful file proves filterable game-level/PIT grain and useful defender volume/outcome fields, but its 20 top-ranked player-games cannot form a complete training panel; identity must bridge through player/team/week/opponent unless paid/API output adds IDs | **Trial schema/grain check passed; completeness open** — `/sis/` and `/sis-trial/` are root-gitignored. Always press Submit and verify the rendered table before Download. Determine whether paid CSV is only top 200 and whether an API/full export can return every qualifier before purchase/model work |
| 2026-08-11 | `player_week_usage` shrank red-zone opportunity toward one all-history positional average, so early seasons borrowed later-season position data; `player_week_injury` also retained duplicate revisions and the final same-week status without enforcing the common Sunday-main lock | Both adopted smoothed red-zone inputs were PIT-contaminated on 3,625/3,640 rows of the deterministic 5% audit sample (maximum absolute changes 0.0673/0.0572). The raw injury feed has 65,866 rows on 65,862 keys; 24 latest revisions occurred after lock, including four `Out` statuses, and could distort same-week vacancy features | **Code repaired; coordinated rebuild and PIT-clean cache revalidation pending** — position priors are now cumulative only through the previous season/week; injury rows choose one deterministic latest pre-lock revision and retain source/lock timestamps. The permanent dynamic gate independently reconstructs all 29 usage-family fields plus injury/vacancy key, null and value parity. No active-label exact-80 outcomes were queried; stale caches are blocked until features, models and both caches are rebuilt under the unchanged frozen laws |
| 2026-08-11 | The referee tendency window ordered only by `(season, week)` even though the raw officials source assigns Scott Novak to two distinct 2024 Week 8 game ids | A rebuild could reverse those tied rows and changed the active `ref_flags_prior` input on 144 training player-weeks by as much as 0.55; the strict warehouse reconciliation stopped before training or scoring | **Repaired before revalidation** — the bounded window now uses total order `(season, week, game_id)`. The second outcome-free reconciliation separately verifies every registered material delta and caps floating rebuild noise at `1e-12`; all accepted/dependent lineages already require fresh training, so unrelated closed treatments remain closed |
| 2026-08-11 | Four post-game candidate team-context transforms (`team_week_pace`, `defense_week_blitz`, `team_week_target_concentration`, `team_week_ftn_offense`) had no synthetic upcoming-week key despite exact-week inference joins; modeled positional-defense aggregation also assigned actuals with each player's season-final roster position | Replays could populate five candidate fields that would be null live, and 403 actual rows over 2019--2025 were attributed to a different positional bucket than their exact weekly roster designation | **Code repaired; coordinated rebuild pending** — all four transforms append a null target observation before the strictly-prior window, a post-build gate requires every upcoming team-week in all four outputs, and positional defense now joins exact `(gsis_id, season, week)` roster position. Dry-runs and focused tests pass; do not mutate the warehouse until immutable gates finish, then rebuild/retrain with key and delta reconciliation |
| 2026-08-11 | Several Fantasy Points grids split frozen identity cells and scrolling metric cells into separate DOM rows; Routes Run also places many hidden menu copies of its title before the visible report heading, while Fantasy Points Scored uses Rank/Name/POS/G rather than the usual player Rank/Name/Team/POS/G identity layout | A generic visible-table guard could misread metric totals as games played, wait forever on a hidden title, or reject a correctly scoped team-by-position grid | **Guarded before catalog completion** — rendered game counts now require a recognized identity layout and a nonnumeric team name for team rows; readiness selects an actually visible title/Season pair. The failed artifacts were never accepted, focused tests plus live regressions passed, and immutable resumed run `20260811T062906Z__remaining-catalog-window-semantics-v1` completed all 18 remaining-catalog exports with exact Season/G validation |
| 2026-08-11 | The first same-season coverage table write succeeded, but its required repeat check treated BigQuery repeated-field results as scalar booleans; NumPy correctly rejected the ambiguous truth test | Idempotence could not be proven even though the created tables had the expected 16,482/1,792 rows; no overwrite or outcome query occurred | **Fixed before diagnostic** — repeated fields are converted explicitly to lists before comparing the single run id and complete source-hash set. The same shared write-once helper now protects the queued Advanced Passing table; rerun must return `already-identical` for both coverage tables |
| 2026-08-11 | The post-Apply rendered-table scope guard recognized player rows but assumed the Coverage Matrix visibly rendered its Season column; the live team grid actually freezes only Rank/Name/G before metrics | The corrected 168-export run safely stopped before its first defense export even though the exact Apply payload and visible `G=4` rows were valid | **Operational parser fixed; no unsafe artifact accepted** — the team-row guard now reads the visible Rank/Name/G layout while season remains independently enforced in the Apply payload and downloaded CSV. The 112 completed receiver exports are retained only through the new plan/hash/scope-validated prefix reuse path; a live matrix regression must pass before resuming |
| 2026-08-10 | Fantasy Points keeps the selected Season/Week controls visible while the report table is still rendering the previous response; a fixed 500 ms post-Apply delay allowed the export action to serialize stale full-2025 data for requests labeled as earlier four-week windows | UI controls and filenames alone can falsely claim point-in-time safety even when the downloaded rows contain `Season=2025` and `G=17/18` | **Fixed with three independent gates; affected run rejected** — Apply now awaits the exact report `values` response and asserts its POST contract contains the requested season/weeks, waits until rendered game counts fit the requested window, and rejects the downloaded CSV unless every Season is exact and every `G` is from 1 through the selected-window length. Regression run `20260811T042431Z__apply-scope-regression-check` returned 299 2022 rows with `G=1..4` |
| 2026-08-10 | Fantasy Points report context links can reset selected Season/Week filters when clicked after filtering; the first broad automation attempt therefore produced full-season rows even though the Week(s) widget had previously shown a four-week selection | A filename can claim a safe prior window while its CSV contains future weeks, creating silent replay leakage if only the UI state or filename is trusted | **Fixed and fail-closed in the downloader; affected audit artifacts rejected** — context is now established before filters, `Apply` is mandatory, the widget is reopened to assert the exact selected weeks, and every intake must still enforce exported `G`/schema/hash semantics. Corrected two-window exports prove exact-window `G<=4` behavior for Advanced Passing/Receiving/Rushing, Man-vs-Zone, Separation by Coverage/Alignment, RB+WR Efficiency, detailed Snaps and both Coverage Matrix views |
| 2026-08-10 | **Correction to the earlier Advanced-export row below:** although the exported Advanced CSV has no week column, the Data Suite `Week(s)` filter changes its aggregate values and can therefore produce same-season prior-week windows | Treating all Advanced data as necessarily N-1 would discard potentially useful current-season information; assuming the filter is cumulative versus exact-window without checking could silently attach the wrong history | **Prior product-limitation classification superseded; filter semantics still unverified** — first preserve 2025 Advanced Receiving exports for Weeks 1--4 and 5--8, compare game counts/values, and permit no replay join until the source window is mechanically proven `< target week`. The tracked Playwright plan and manifest contract automate these two audit exports without storing credentials or licensed CSVs in Git |
| 2026-08-10 | **Correction to the earlier QB/WR Coverage Matchup row below:** schedule verification shows those exports and the OL/DL sample reproduce 2025 Week 1 matchups while carrying completed 2025 (`G=17`) inputs; they are not current 2026 Week 1 snapshots | Treating them as prospective would apply a stale schedule, while treating them as historical would leak end-of-season information into Week 1 | **Prior classification superseded; files isolated as schema samples only** — forbid all three exports from replay, diagnostics and live projection. A future export is prospective only after its team/opponent pairs match the target-season schedule and it is frozen before the shared slate lock |
| 2026-08-10 | Fantasy Points 2024 Receiving Separation by Coverage leaves one route unclassified by Man/Zone/Red Zone for each of Courtland Sutton, Devaughn Vele, Troy Franklin and Lucas Krull, while all other player-seasons partition exactly | Recomputing coverage shares from an assumed exhaustive partition would silently assign four Denver routes to the wrong shell or slightly distort rates | **Accepted and guarded at intake** — preserve vendor split counts and missing classification, never impute the residual route, require support-aware group-qualified fields, and attach these full-season aggregates only as season N-1 priors |
| 2026-08-10 | Fantasy Points Coverage Matrix repeats the bare header `FP/DB` twice inside each of the Man/Zone and Middle-of-Field groups even when group headers are enabled | Ordinary name-based CSV parsing would silently overwrite Man with Zone and 1-High with 2-High efficiency | **Guarded at intake** — hash-lock each schema and assign the four repeated fields by their frozen adjacent rate column/position; reject any reordered layout. Coverage Matrix season aggregates remain N-1-only acquisition data until a separate protocol is frozen |
| 2026-08-10 | Fantasy Points Receiving Man-vs.-Zone exports include QB rows with one receiving route but `FP/RR` as high as 336.46, apparently incorporating full passing/rushing fantasy production; low-route coverage splits are also inherently unstable | Treating every row/rate as receiving efficiency would create extreme false QB signals and noisy skill-player priors | **Guarded at intake** — any future coverage-split diagnostic must exclude QBs, require preregistered minimum route support, use group-qualified columns and attach only season N-1; these fields are not part of the already-frozen Advanced diagnostic |
| 2026-08-10 | Fantasy Points QB/WR Coverage Matchup pages expose no historical-season selector; the vendor uses previous-season inputs through Week 3 and active-season inputs thereafter | A current export combines prior/active performance with the upcoming matchup and cannot reconstruct honest historical matchup features for 2022--2025 | **Prospective-only collection** — the first QB export is hash-locked as a 2026 Week 1 snapshot with forecast week and retrieval time supplied separately. It is excluded from every historical replay and promotion gate; collect before the common slate lock and grade only after outcomes become available |
| 2026-08-10 | Fantasy Points Data Suite Advanced Receiving/Rushing/Passing Player exports are full-season aggregates with no week column; Advanced Rushing and Passing contain repeated bare column names whose meaning depends on group headers | Same-season use would leak future games, and parsing ungrouped repeated headers by name can silently overwrite one subgroup or assign it the wrong meaning | **Guarded at intake** — all Advanced families are eligible only as strict prior-season features; weekly Route/Target/Snap remain the same-season sources. Rushing and Passing were exported with group headers and all files are hash-locked; import must use group-qualified names and reject an ungrouped layout |
| 2026-08-10 | `harvest_accept.py` promoted candidate rows with positional `INSERT ... SELECT *`; staging gained the preregistered 210/220 support masks while the older accepted table still had 42 columns | The first corrected K3 promotion failed safely after all acceptance checks with `Has 44, expected 42`; no candidate or snapshot rows were committed, but the corrected comparison chain paused | **Fixed before retry** — promotion makes one schema API update containing only missing nullable fields, names every target/source column explicitly, and keeps candidate plus snapshot eligibility in one transaction; a regression test forbids positional promotion. The first repair's per-field `ALTER TABLE IF NOT EXISTS` loop was also rejected before DML because BigQuery counts no-op ALTERs toward its metadata rate limit |
| 2026-08-10 | `prop_market.market_points()` resolved player-name aliases only after aggregating each spelling, so multiple prop spellings mapping to one GSIS id produced 21 duplicate player-weeks in 2023--2025; replay dropped one by input order and live joins could fan out | A small number of market means were nondeterministic or could duplicate live projection rows even after the common-lock correction | **Fixed in common-lock implementation; revalidation pending** — resolve aliases at the per-market layer, average same-player/same-market aliases, then sum distinct markets to one asserted `(season, week, gsis_id)` row; offline alias fixture and live warehouse read return zero duplicates |
| 2026-08-10 | Historical standard props were imported at each game's kickoff minus two hours, while `models.prop_market.market_points()` excluded openings and did not enforce the shared Sunday-main DFS lock. Late-afternoon players therefore used 2:05/2:25 p.m. line information after the 1 p.m. roster lock | Accepted 2023--2025 replay projections include post-lock market means for 1,842/1,788/1,716 covered player-weeks; candidate worlds and selected portfolio evidence can change even when both arms shared the same leaked inputs | **Confirmed; correction/rebaseline in progress** — select the latest snapshot strictly before the schedule-derived domestic main-slate lock, fall back to model-only when unavailable, hard-test London/early/late snapshots, then rebuild K=3→K=1→CE→role true-80 evidence on one immutable image. Protocol: `reports/2026-08-10-prop-common-lock-correction.md` |
| 2026-08-10 | DraftKings alternate-yardage ladders in `nfl_raw.prop_lines` have no useful 2019/2021/2022 coverage and cover only four 2023 Sunday-main slates; complete common-lock coverage begins in 2024. Historical snapshots are event-close oriented, so late-afternoon players can have an older available ladder at the common 1 p.m. slate lock | A market-tail replay cannot support a six-season arm or use player-kickoff cutoffs without leakage; blindly combining all seasons would make the mechanism active only in recent years | **Accepted and guarded** — the preregistered market-tail diagnostic and any licensed candidate union are limited to all 18 slates in each of 2024/2025, enforce one common main-slate cutoff, report per-slate coverage, and require 2019--2023 candidate books to reproduce the incumbent exactly |
| 2026-08-08 | `raw.player_ids` is not unique on `gsis_id`; the replay's display-name join duplicated 31 otherwise unique 2014--2015 training player-weeks. Separately, the adopted marginal shapers ranked the simulator's many tied outcomes with NumPy's unstable default quicksort; CPU-dispatched implementations could assign equal outcomes to different world columns even when component hashes and every player's marginal distribution were exact | Duplicate rows slightly reweighted old training observations. Unstable tie ranks preserved all per-player summaries but changed the joint candidate worlds, threshold masks and sometimes candidate/selection results across same-image Cloud Run executions | **Fixed; exact revalidation required** — replay selects one deterministic display name per GSIS id and orders DST rows; the shared simulator canonicalizes and fingerprints component means; both TabPFN and empirical marginal shaping now use the original simulation-column index as an explicit stable tie-breaker. Same-image exact-world proof remains mandatory before any arm verdict |
| 2026-08-07 | NFLverse's 2014--2015 weekly rosters use legacy team codes (`ARZ`, `BLT`, `CLV`, `HST`, `SL`) absent from the historical identity normalizer; RotoGuru also lists Corey Brown by his nickname “Philly” | Weekly-roster identity failed for older ambiguous names, omitting scored main-slate rows for Steve Smith, Chris Givens, Jacoby Jones, Rob Housler and Corey Brown | **Fixed before rebuild** — the five roster aliases are canonicalized before identity matching and the reviewed Philly/Corey alias is explicit; an independently reconstructed raw-source gate requires every schedule- and roster-valid historical salary row to reach the salary spine |
| 2026-08-07 | Historical NFL-week salary feeds can retain the same player under old and new teams, and the problem also exists in RotoGuru—not only LineStar. Because both teams may coincidentally play the listed opponents, schedule validation alone allowed false identities (for example Chris Givens on Baltimore before his trade, Percy Harvin on the Jets before his trade, Isaiah Ford on New England before his trade and DeSean Jackson on Las Vegas before signing) | Trade-week players could be assigned to the wrong team/game, while a correct row could disappear (also observed with Tyler Huntley, Bailey Zappe, T.J. Hockenson, Nyheim Hines and Zack Moss) | **Fixed before rebuild** — every historical row requires a unique normalized weekly-roster identity on the salary-side team/week. A salary/player-id football name may bridge to a different roster legal name only when the same GSIS id is independently present on that exact team/week; the unvalidated global fallback was deleted after all 148 rows relying on it had zero weekly-stat matches on their claimed teams |
| 2026-08-07 | Salary, player-id and weekly-roster sources do not consistently choose legal versus football names (for example Jeff/Jeffery Wilson, Dee/D'Wayne Eskridge, Tank/Nathaniel Dell and Matt/Matthew Slater); roster names can also contain repeated spaces | Requiring the salary spelling to equal the roster spelling omitted legitimate selectable and sometimes scoring players from the 2022+ universe | **Fixed before rebuild** — normalized whitespace plus the roster-validated GSIS bridge resolves name variants while still requiring the exact player id on the salary team/week; audited vendor aliases remain explicit where the id map has no bridge |
| 2026-08-07 | Historical salary identity fell back directly to the global name map, so recycled names such as Mike Williams remained ambiguous even when the salary row's historical team/week uniquely identified the active player | Legitimate main-slate players could disappear from replay and model training despite a valid salary; current-team fields could not safely resolve them | **Fixed before rebuild** — unique regular-season weekly-roster identity by normalized name/team/week/position is mandatory; the global map may bridge name variants only when its exact GSIS result is independently rostered on that team/week |
| 2026-08-07 | LineStar's 2024 Week 10 period combines multiple DK contest salary blocks; Mike Williams and Jonathan Mingo retain two different prices even after team/opponent validation | A post-validation `MAX` would use $4,200/$3,700 instead of the Millionaire block's $4,100/$3,200, so legal-roster reconstruction could still be wrong | **Fixed before rebuild** — the two audited main-contest prices are frozen explicitly from the live SalaryContainer/ownership ID block; all other valid-match duplicates were verified to have identical prices, avoiding an unjustified blanket `MIN` rule |
| 2026-08-07 | RotoGuru records the hurricane-rescheduled 2017 MIA-TB game at its played Week 11 but uses `opponent='-'` for every scored salary row | A blanket opponent-match requirement would remove all skill players and both exact DST labels from a legitimate regular-season game | **Fixed before rebuild** — the transform permits only this named season/week/team pair after validating both sides against the canonical schedule; other missing-opponent rows remain excluded |
| 2026-08-07 | RotoGuru uses `SDG` for the San Diego Chargers, while the historical alias map handled only `SD`; the new schedule-validating salary join exposed the missing alias before deployment | Without correction, most Chargers and Chargers-opponent salary rows from 2014--2016 would be dropped from model training | **Fixed before rebuild** — `SDG -> LAC` is included in skill salary, DST exact-label and replay normalization; the post-join salary audit checks season counts and duplicate keys |
| 2026-08-09 | The live Odds API props job assigned every currently listed NFL event to the next regular-season week; during August that could label preseason props as regular-season Week 1 | Preseason players/markets could pollute the production `prop_lines` table and any live market blend that selects the latest Week 1 snapshot | **Fixed before the 2026 season** — the job now resolves the next regular-season week's exact game-date window and ignores events outside it before making either paid prop request. Offline tests cover a mixed preseason/regular-season response and the US-local-date boundary |
| 2026-08-07 | Historical replay treated the LineStar/RotoGuru NFL-week salary feed as a DraftKings draft-group snapshot, so Thursday, Friday, Sunday-night and Monday players were mixed into the Sunday main slate | Every prior six-season lineup panel used the wrong contest universe; even a salary-legal lineup could not have been entered in the historical main-slate contest | **Code fixed; rebaseline required** — target-season skill rows and DST salaries are restricted independently to regular-season Sunday starts from 13:00 through the late-afternoon window; acceptance rejects any snapshot matchup outside that schedule and requires exact DST coverage. All prior panels are non-citable pending a newly accepted baseline |
| 2026-08-07 | Historical skill-player salary construction aggregated by player/week before validating the listed opponent; adjacent-Thursday LineStar rows could therefore contribute the next game's price, and `MAX(salary)` selected the larger value | Candidate feasibility and salary-derived model inputs could use a price from the wrong matchup (for example, Zay Flowers 2024 W9 was $7,000 vs DEN but the old table chose $7,200 from the mislabeled CIN row) | **Code fixed; feature rebuild and rebaseline required** — team and opponent are normalized and joined to the canonical schedule before per-player aggregation; the distinct 2025 DiscoveryLab skill source omits opponent and is instead validated on its unique team/week rows; SQL guards ban the former pre-validation `MAX(CAST(salary...))` path |
| 2026-08-07 | The replay-local post-2021 DST scorer grouped recoveries/TDs by `defteam`, omitted safeties, blocked kicks and defensive conversions, and bracketed the opponent's final score even when points were surrendered by the offense | Some historical lineup actual scores were wrong even when all skill-player labels were correct; this is another reason prior threshold counts cannot be trusted | **Code fixed; feature rebuild and rebaseline required** — one canonical scorer credits the event team, excludes offensive defensive-TD/safety points from the PA bracket, and uses matchup-validated exact DK labels when the historical feed supplies them. The raw-PBP fallback exactly reproduces all 17 known 2025 winning-DST scores; acceptance rechecks every immutable player label against the canonical actual tables |
| 2026-08-06 | `017b_referee_tendency.sql` used a stale `officials.name` field in its deterministic tie-break; the live schema exposes `official_name` and `official_id` | The first production build of the replay-universe repair stopped after updating salary/actuals/usage but before rebuilding training, temporarily leaving feature tables on opposite sides of the new contract | **Fixed immediately** — tie-break now uses `(official_name, official_id)` from the inspected live schema; a regression assertion pins those names; the coordinated feature build was rerun before training |
| 2026-08-06 | `017g_target_concentration.sql` grouped weekly stats by `player_id` but its deterministic rank tie-break referenced nonexistent `gsis_id` | The next production build passed the referee repair but stopped before training, exposing a second stale-name defect in an older candidate transform | **Fixed immediately** — tie-break now uses the live `weekly_stats.player_id`; every remaining feature SQL was dry-run compiled against live schemas before the next coordinated build |
| 2026-08-06 | Historical `player_week_usage` was spined by same-week receiving/rushing activity, and the historical DK salary crosswalk did not strip name suffixes | Legitimate salary-listed replay options could disappear before training/generation. Across the six-season panel audit, 204 omitted salary-listed player-weeks scored 20+ DK points and 40 scored 30+; this makes prior replay universes incomplete even though the live salary-spined projection path is unaffected | **Implemented and production-reconciled; rebaseline pending** — salary now builds ahead of actuals/usage; matching is suffix-aware and source-prioritized per player-week; usage/zero labels are salary-spined; `was_active` keeps listed inactives out of model fitting; exact post-build reconciliation fails on future drops. Production execution `build-features-gk966` reproduced 98,717 training/replay rows and zero eligible salary gaps, and passed leakage checks. Full corrected-universe replays must run on Cloud Run before interpreting any score delta |
| 2026-08-06 | Candidate persistence tried `git rev-parse` inside a production image without `.git`; the command returned blank stdout and nonzero status without raising, so the exception-only fallback did not use the supplied `CODE_SHA` | A replay panel could retain masks and config but have blank code provenance, weakening the immutable-build claim during promotion | **Fixed before corrected rebaseline** — candidate persistence uses a nonblank `CODE_SHA` fallback, otherwise records `unknown`; the audited baseline runner requires an explicit SHA and the acceptance gate rejects blank or unknown code provenance |
| 2026-08-06 | The salary-spined replay introduced rows with nullable roster metadata; cold-start filling called `bool()` directly on nullable `is_rookie` | The first corrected-universe baseline attempt failed before projection in five seasons (the sixth was cancelled), so it produced no citable score | **Fixed; fresh panel required** — nullable cold-start flags default false and unknown rookie status uses the ordinary role prior; a regression fixture reproduces the production row shape, and the failed panel is durably marked invalid rather than reused |
| 2026-08-06 | `harvest_accept.py` promoted accepted candidate rows but left their immutable `slate_player_features` snapshots marked research-ineligible | `missed-player-analysis` required both eligible tables and therefore could not analyze a supposedly accepted new panel | **Fixed before corrected panel promotion** — acceptance requires exact candidate/snapshot slate-run parity and valid provenance, then promotes both sides atomically in one BigQuery transaction; the script is included in the container for remote execution |
| 2026-08-06 | Candidate `lever_env` used a short allow-list that omitted `EXTRA_FEATURES` and several generation/model controls | A feature treatment could have the same warehouse config identity as baseline even when the repository runner manifest differed | **Fixed before the full corrected panel** — the second preflight was cancelled after two weeks and marked non-citable; candidate rows now record the complete effective modeling/construction lever set, and acceptance requires exactly one code SHA, config hash, lever record, and seed record per panel |
| 2026-08-06 | LineStar historical DST salary rows can label the adjacent Thursday slate with the prior display week; replay joined only team/week and silently dropped duplicate team ids by input order | Some 2022+ replays could roster a defense at the next opponent's salary rather than the actual NFL week's salary, corrupting lineup feasibility and score comparisons | **Fixed; affected panel cancelled** — DST salaries must match canonical `schedule_long` on season/week/team/opponent (3,024 unique current team-weeks, zero duplicates); remaining team-week or slate-id duplicates hard-fail; the cloud smoke defaults to the 2022 LineStar path. Panel `20260806-universe-baseline-525ddb1` is incomplete, staging-only, and non-citable |
| 2026-08-06 | Only winner rosters and aggregate ownership were retained for historical Milly contests; historical top-20 entry rows are absent. The standings importer suppressed entry-block failures after importing ownership | The requested player-by-player top-20 lineup analysis cannot be reconstructed for old contests, and silent parser failures could repeat during the season while DK exports are still ephemeral | **Prospective fix implemented** — entry parsing is now a required import contract; ordered slot structure, roster-size/top-20 validation, and deterministic import IDs are retained; safe retries are deduplicated by consumers; `leaderboard-analysis` and `missed-player-analysis` provide the new analyses. Existing 65 winner rosters remain winner-only evidence; old top-20 entries cannot be recovered from current project data |
| 2026-07-24 | RotoGuru DK salary history ends after the 2021 season (site stopped updating) | `salary`/`salary_delta_wow` null on 2022–2025 training rows; recent-season backtests can't price lineups. Also degrades salary as a *model feature* in the null era: the 2025 ablation showed removing it helped (−0.013 MAE) while the full-coverage 2021 ablation showed it helps (+0.010, rank corr 0.611 vs 0.599) — see reports/2026-07-25-system-study.md | **2025 closed** (2026-07-25): DiscoveryLab free tier serves real salaries for the most recent season — 13,406 rows imported + Captain Mode slates, verified 100% $100-multiples (`import-discoverylab`, `import-discoverylab-showdown`). Remaining gap: 2022–2024 (their paid personal tiers may cover; unverified). Earlier vendor trail: SportsDataIO trial serves scrambled salaries and no historical access; their commercial API quotes several thousand dollars — declined. Their personal-use DiscoveryLab tier is unverified for DFS salaries (asked). A tested importer for their DfsSlatesByWeek endpoint lives in git history at commit 7d17bd8 (removed after the trial dead-end) — one revert away if a viable key appears |
| 2026-07-24 | ~2–4% of 2014–2021 RotoGuru rows can't be safely matched to a GSIS ID (ambiguous duplicate names, team defenses) | Small salary-coverage holes in otherwise ~98%-covered seasons | Accepted — dropping beats guessing between same-name players |
| 2026-07-24 | No historical market projection exists: RotoGuru has no `dk_ppg`, and we have no prop-line archive | `dk_ppg` is null before 2026, so walk-forward "beats the market" comparisons have no market baseline until our own DK snapshots accumulate | Open — consider a props archive if market-relative validation matters before mid-2026 |
| 2026-07-24 | nflverse `weekly_stats` schema drift: `recent_team` → `team`, `interceptions` → `passing_interceptions` | Broke `013_player_week_actuals.sql` on first real build | Fixed in SQL — treat unknown-column build failures as possible upstream renames |
| 2026-07-24 | nflverse `injuries` ships `season`/`week` as FLOAT (null-driven upcast) | BigQuery refuses FLOAT64 in window `PARTITION BY`; type-inconsistent join keys | Fixed — cast to INT64 in `018_player_week_injury.sql` |
| 2026-07-24 | Advanced-source history is shorter than the 2014+ panel: snap counts 2012+, NGS 2016+, FTN charting 2022+ | Features derived from these are null in early seasons of the training window | Accepted — LightGBM handles missing natively |
| 2026-07-25 | No free source for routes run / targets-per-route-run (TPRR) — paid charting is required | TPRR is among the most predictive receiver metrics; accepted-panel winner misses are concentrated at WR/TE and fast-role/vacancy states consistently beat matched controls | **Paid-data pilot purchased/imported 2026-08-10** — the operator purchased the $200 standalone Fantasy Points Data Suite after the frozen free participation proxy supported a true-route trial. All four 2022–2025 Route Share CSVs are validated and hash-locked; a narrow private import contains 27,305 weekly rows/26,881 resolved rows, while the remaining Weekly Report and Advanced Receiving acquisition continues. Preserve licensed exports under ignored `fantasy-points/`, then follow the preregistered walk-forward player-tail → candidate-union → fixed-budget gates in `reports/2026-08-10-fantasy-points-route-share-experiment.md`; no bulk feature addition is authorized |
| 2026-07-24 | No nflverse data for a season until its games begin (loaders reject the planning-clock season) | Offseason ingest crashed until clamped | Fixed — `ingest/nflverse_job.py` clamps to `nfl.get_current_season()` |
| 2026-08-02 | LineStar `contest_ownership.fpts` is 100% NULL (source never returned points; backfill stored the column empty) | Any analysis joining ownership to scoring must route through `player_week_actuals` by normalized name (~85% match rate; DSTs unmatched) | Accepted — empirical position leverage weights (Addendum 39 audit) derived via the actuals join; column kept for schema stability |
| 2026-08-03 | `schedule_long` kept historical team codes (OAK/SD/STL) while stats tables normalize to LV/LAC/LA — the 021 inner join silently dropped ~1,500 relocated-franchise training rows (2014-19; Derek Carr had NO training rows pre-2020) and NULLed opponent-defense features on 1,458 more | Walk-forward folds 2015-2020 trained on incomplete data | **Fixed** — codes normalized in 012 (data audit, Addendum 42); features rebuild + post-fix baseline follow the running panels |
| 2026-08-03 | 2025 DK salary coverage dips in weeks 13/17/18 (19-28% of training rows NULL salary vs ~7% other weeks) | Slight feature degradation those replay weeks | Open — check dk_salaries_historical/DiscoveryLab for those slates |
| 2026-08-03 | nflverse `schedules.wind` largely missing for 2022 (96/271 games) and partial 2023 (150/272) | wind_mph feature NULL for ~half of 2022 non-dome rows | Accepted — upstream gap; LightGBM handles |
| 2026-08-03 | 2022+ salary sources price the full DK pool incl. inactives (53% of salary rows have no actuals match vs 11-15% pre-2022) | Salary-side denominators inflated in analyses; training unaffected (inner join) | Accepted — source-breadth regime change, documented |
| 2026-08-03 | `nfl_raw.weather` has 0 rows ever (live forecast feed never landed) | Live wind/temp features would silently NULL in-season | Open — verify ingest-weather on first in-season run (added to week-1 checks) |
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
| 2026-07-31 | `bq.SQL_DIR` resolved checkout-relative (`parents[2]/sql`), which is `/usr/local/lib/python3.11/sql` inside the container — nonexistent — so every scheduled `build-features` run died on FileNotFoundError (and `project-slate` failed downstream; `predictions.player_projections` never materialized on this infra) | No feature refresh or projections from the scheduled pipeline; went unnoticed because job failures alerted no one (see the monitoring row below) | Fixed — `bq._sql_dir()` falls back to CWD/sql (the Dockerfile ships sql/ into WORKDIR); `tests/test_sql_dir.py` guards it; first green scheduled-infra `build-features` run 2026-07-31 |
| 2026-07-31 | **Data loss:** the scheduled `ingest-nflverse` run loads only the current season but `_load` used WRITE_TRUNCATE unconditionally — its first scheduled run (2026-07-28) silently wiped the 2014–2024 backfill from every season-scoped raw table (`pbp`, `weekly_stats`, `rosters_weekly`, `snap_counts`, `injuries`, `ngs_*`, `ftn_charting`, `pfr_advstats_def`; legacy `depth_charts` survived only because the incremental path skips it) | Training/replay data reduced to one season; masked until the SQL_DIR fix let `build-features` succeed and shrink `player_week_training` 52,422 → 4,687 rows. All recoverable — nflverse serves full history on demand | Fixed — incremental loads now delete-the-loaded-seasons + append (`tests/test_nflverse_job.py`); restored via `ingest-nflverse --full` on Cloud Run 2026-07-31, then `build-features` rerun |
| 2026-07-31 | The DK sportsbook game-lines scrape (`odds_job.py` → `sportsbook-nash.draftkings.com` league 88808) is 403-Forbidden (Akamai) from both Cloud Run and a local box, and `nfl_raw.odds_snapshots` contains zero rows ever — the hourly odds job has never landed data since deployment | The intended live in-week line-movement signal doesn't exist. No silent corruption: nothing downstream reads `odds_snapshots` (training uses nflverse closing lines; the market blend reads `prop_lines` from The Odds API), so this is a dead limb, not a bad input | Fixed same day — `odds_job.py` rewritten to The Odds API's live game-odds endpoint (`americanfootball_nfl`, `bookmakers=draftkings` so lines stay DK-aligned), same `odds_snapshots` schema/market_type values. 3 credits/run (1 per market), trivial vs. the props-history quota. First-ever rows landed 2026-07-31: 1,632 across 272 events (full 2026 schedule) with sane spreads/totals |
| 2026-08-20 | Running the real `ingest-dk` job end to end (preseason slates live) found THREE defects that each independently broke the hourly slate/salary ingest — the core of the live pipeline: (1) the draft-group filter matched zero groups (the 2026-07-31 row below, now confirmed: 0 of 198 live groups carry a top-level `sport`, while 94 are NFL by `sportId`); (2) DK serializes competition start times with seven fractional-second digits, which pyarrow cannot cast to a BigQuery TIMESTAMP, raising `ArrowInvalid` on the load; (3) the load omitted the live table's clustering spec and BigQuery rejected it outright. `dk_salaries` held zero rows as a result | Week-1 fatal: no slate ingest means no salaries, no projections, and no lineups on Sunday. Undetectable from tests alone — all three only appear against the real endpoint and the real table | **Closed 2026-08-20.** Filter switched to `sportId`, Madden `SIM` leagues and non-salary-cap products (Best Ball/Snake/Pick6) excluded, game-type names resolved from the payload's `gameTypes` array so showdown slates classify correctly, timestamps parsed, clustering passed. Verified live: 17 slates ingested (8 classic / 9 showdown), 2,413 rows landed. Regression test pins the real payload shape |
| 2026-07-31 | `dk_client.nfl_draft_groups()` filters `/draftgroups/v1/` entries on a top-level `g["sport"] == "NFL"` string. Live-fetched against the real endpoint while building the CFB scaffold (issue #13 item 7): 0 of 180 draft groups sampled carried a top-level `sport` key at all — the reliable fields are the per-group `sportId` int (1=NFL, 5=CFB, cross-checked against DK's `/sites/US-DK/sports/v1/sports`) and the nested `contestType.sport` string. `cfb_draft_groups()` uses `sportId` instead. Unverified whether `nfl_draft_groups()`'s filter actually matches real (non-Madden-sim) NFL draft groups once the season is live — this session has no GCP access and it's currently the off-season, so every live-fetched group under the NFL tag was a Madden simulation or Best Ball entry, not a real NFL slate, and none of those carry `sport` either way | If the top-level `sport` field is genuinely never populated, `nfl_draft_groups()` — and therefore `dk_job.py`'s hourly slate/salary ingest, the core of the whole pipeline — would return zero groups even in-season. Could not be confirmed or ruled out offline | Open — the owner's local/in-season session should re-run `dk_client.nfl_draft_groups(requests.Session())` against a live NFL week and check whether it returns the real slate; if empty, switch the filter to `sportId == 1` (mirroring `cfb_draft_groups()`) — do not change this from an offline session with no real NFL slate to validate against |
<!-- DATA-DEFICIENCY-LOG:END -->
