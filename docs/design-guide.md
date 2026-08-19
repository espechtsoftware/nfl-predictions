# NFL DFS design guide (§0–§14)

Preserved verbatim from the original `README.md` build guide when the README
was rewritten as a practical entry point on 2026-08-19. This is the reference
design document: principles, data sources, warehouse schema, ingestion,
features, modeling, graphs/trends, optimization, backtesting, orchestration,
roadmap, pitfalls, and links.

In-code comments that cite a bare "§N" or "design guide §N" refer to the
sections of this document.

Operational truth lives elsewhere and supersedes this document wherever they
disagree: [`../HANDOFF.md`](../HANDOFF.md) for current state,
[`../README.md`](../README.md) for setup and commands, and the code itself.

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

Filter draft groups by `sport == "NFL"` and inspect `draftGroupState` / `startTimeSuffix` to identify the main slate versus showdown/single-game slates. Showdown slates use different roster rules and should be a separate pipeline branch. (`cfb_draft_groups()` filters CFB slates by the top-level `sportId` field instead — see the deficiency log entry below on why.)

**Cadence:** pull at slate lock minus 48h, then hourly through lock. Salaries are set once, but the *player pool* changes as inactives are announced, and that's the signal you care about.

**Historical DK salaries** — the real gap. Options, in order of preference:

1. `rotoguru1.com/cgi-bin/fyday.pl?week=N&year=YYYY&game=dk&scsv=1` — semicolon-separated, ugly, complete, free, back to 2014. Includes actual DK points scored. This is the standard answer.
2. `github.com/Brian-Doucet/nfldfs` — Python package that scrapes DK salary and points by season into a DataFrame.
3. Start logging your own from day one. In three seasons you'll have the best copy.

**Ownership percentages** are the one genuinely hard-to-get-free item. They matter a lot for GPPs and not at all for cash games. Options: scrape contest results pages post-hoc (DK exposes contest standings for completed contests), or accept a paid source later. Build the system to work without ownership, with a clean slot to add it.

**College football (collection-only scaffold, added 2026-07-31).** DK now runs CFB DFS (QB/2RB/3WR/FLEX/Superflex, 8 slots). `ingest/cfb_job.py` (`nfl-dfs ingest-cfb`, gated by `INGEST_CFB_ENABLED`) polls the same two endpoints above for CFB draft groups/draftables into `nfl_raw.cfb_dk_salaries`, plus `getcontests?sport=CFB` into `nfl_raw.dk_contest_fills` (now carrying a `sport` column, reused from the NFL overlay scaffold rather than a twin table). This is deliberately collection-only — no features, models, or optimizer work reads it — so a full 2026 CFB season's worth of slates/salaries/contest fills accumulates for a 2027 go/no-go call on building the rest of the pipeline. See §3.1 and the *Known gaps* section below.

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

Practical advice: skip paid odds in v1. Use nflverse closing lines for training and scrape the DK sportsbook's own public endpoints for live game lines, since you're already hitting DK. Add a props provider only once your model is good enough that the marginal edge justifies $99/month. *(Superseded 2026-07-31: the DK sportsbook endpoint Akamai-blocks non-browser clients — see the deficiency log — so live game lines come from The Odds API's game-odds endpoint pinned to `bookmakers=draftkings`, which costs ~3 credits/run from the quota the props history already pays for.)*

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

Other raw tables: `weekly_stats`, `snap_counts`, `depth_charts` (2001–2024 weekly format), `depth_charts_snapshots` (2025– dated-snapshot format; see the deficiency log), `rosters_weekly`, `injuries`, `injury_snapshots` (append-only collector-time PIT evidence), `schedules`, `ngs_receiving`, `ngs_rushing`, `ngs_passing`, `ftn_charting`, `player_ids`, `dk_salaries`, `dk_slates`, `odds_snapshots`, `odds_api_requests` (secret-free request/quota telemetry), `prop_lines_shadow` (live-only collection data, excluded from production consumers), `dk_contest_fills` (overlay-detection scaffold, §11; now carries a `sport` column so NFL and CFB polls share one table), `cfb_dk_salaries` (CFB collection-only scaffold, same shape as `dk_salaries` below but kept as a separate table since CFB's roster shape differs from DK NFL Classic's — see *Known gaps*).

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

### 6.4 As-built (2026-08-04): the production distribution stack

Sections 6.2-6.3 describe the original design; this is what actually
ships after the July-August experiment program (every stage
replay-validated on six-season panels — the verdicts live in
reports/2026-07-25-system-study.md). The chain, in execution order:

1. **Component means — LightGBM** (`models/components.py`): the 11
   component models of §6.2, trained walk-forward weekly, sorted feature
   columns (order-luck law, Addendum 34). The feature list includes the
   adopted `qb_cpoe_l6`, `net_rest_diff`, `body_clock_hour`; candidates
   are `EXTRA_FEATURES`-gated (`models/featureset.py`).
2. **Correlation structure — possession-Markov game engine**
   (`models/game_sim.py`, `GAME_SIM_MODE=possession`): drive-state
   Markov chain fit on 48.5k drives supplies per-team game factors, so
   teammate/opponent correlation is mechanistic, not a copula matrix.
   `SCRIPT_FEEDBACK` (two-half deficit-driven pace response) is an
   off-default lever with a recorded panel verdict.
3. **Draw shaping — EW + TabPFN marginals**
   (`backtest/replay.py:apply_draw_shape`, shared by replays AND live):
   fitted variance widening, then each player's draws are QUANTILE-
   MAPPED (rank-reorder — the correlation survives untouched) onto
   **TabPFN-v2 walk-forward quantiles** cached in
   `features.tabpfn_projections` (GPU job `tabpfn-gen`, weekly +
   post-rebuild; `TABPFN_UPCOMING=season:week` adds the live week).
   Missing cache falls back to the EW empirical (position, tier)
   families WITH a UI warning. TabPFN was adopted because three
   independent studies showed our GBM tails under-cover while TabPFN
   arrives calibrated — and it then won +6 tail weeks on the panel.
   Deeper TabPFN insertions (mean blend `TABPFN_MEAN`, full component
   swap `TABPFN_COMPONENTS` from `features.tabpfn_components`) are
   levers with panel verdicts in the ledger.
4. **Market blend** (§7.7, `models/blend.py` + `models/prop_market.py`):
   additive mean shift from de-vigged prop lines; the draw SHAPE stays
   the validated one. The market's own implied quantiles
   (`inference/market_implied.py`) are a WATCHLIST signal
   (`/api/market-tails`) — model-vs-market tail disagreement predicts
   market error in both directions (Addendum 45).
5. **Tournament objective** (`backtest/replay.py:build_slates` and the
   live mirror `inference/live_lineups.py`): punt ceiling valuation,
   PUNT_BOOM archetype boost, and the chalk fade — which uses the
   **trained ownership booster** (LightGBM on `raw.contest_ownership`,
   OOS corr .727 vs naive .548; `OWN_MODEL=fade`) while the naive
   softmax remains the field-simulation yardstick. Showdown has its own
   naive-fade lever (`SHOWDOWN_FADE`).
6. **Construction + selection** (§9-§10): boom-draw candidate solves,
   QB-variant batches, thesis constraints, then greedy tail-coverage
   selection of N entries on P(best-of-N ≥ contest line).
7. **Confidence calibration** (`models/conformal.py`): the lineup-card
   confidence sigma is scaled by a rolling 3-week conformal factor once
   ≥100 scored rows accrue in-season (neutral 1.0 before) — external
   review 3.1.

Adjacent research models with recorded status: **LEM** (factored
next-event transformer, `scripts/lem_train/` — beat its bigram gate;
rollout-realism gate decides `GAME_SIM_MODE=lem` work), **persona
ownership** (LLM field simulation — beat naive, September live shadow),
and the **captain board** (per-player CPT/FLEX-optimal rates computed
from the showdown build's own draws).

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

**Pricing-lag model (issue #13 item 3).** The changepoint alert above catches a *recent* role change DK hasn't repriced yet. A complementary, longer-horizon signal: regress salary directly on trailing-production features (Ridge, per position, walk-forward by season — `src/nfl_dfs/models/pricing_lag.py`, `nfl-dfs pricing-lag --season S --week W`). The residual (actual salary minus what the trailing role implies) flags players DK has been *structurally* underpricing for a while, not just this week — a candidate input to the ownership-residual work in issue #11, since public ownership tends to track salary/narrative rather than underlying role. Writes `nfl_features.salary_pricing_lag`.

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
- Swappability: `Lineup.slot_order()` (`optimizer/lineup.py`) assigns FLEX
  at export time, not construction time — slot labels don't change DK
  scoring, so among the position with a roster surplus it labels the
  **latest-kickoff** player FLEX (the only slot any of RB/WR/TE can fill)
  rather than the lowest-projected one, preserving the most late-swap
  optionality. Requires every player to carry a `kickoff` time (populated
  from `dk_salaries.game_start` when a slate is chosen); falls back to
  the old lowest-projection pick otherwise.

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
- **Portfolio map after every build**: the Lineups page summarizes unique-player count, average/max roster overlap, top-five-player concentration and exact duplicates. Its lineup-family map groups entries that share at least 55% of the family seed's roster; the player network connects frequently co-occurring players and sizes them by exposure. Clicking a lineup or player highlights the matching lineup cards. These are descriptive diversification diagnostics computed from the generated portfolio only—not an additional score selector and never a reader of future outcomes.

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
> **Live-deployment note (2026-07-31):** the actually-deployed schedulers run sparser than this table — nflverse/features/train/projections are weekly (Tuesdays), DK slates 1×/day — see the WARNING in `deploy/deploy_jobs.sh`. `status.py`'s freshness thresholds follow the live cadences; the daily `check-freshness` job emails (via the Cloud Run failed-execution alert) when any active feed goes stale.

**TabPFN projection cache (adopted 2026-08-04, Addendum 50).** The sim's
default marginals come from `nfl_features.tabpfn_projections`, generated
by the `tabpfn-gen` Cloud Run GPU job (L4, ~64s/season, ~$0.05/run).
Regenerate after EVERY feature-table rebuild and weekly in-season
(Wednesday, after `s-train`): `gcloud run jobs execute tabpfn-gen
--region us-central1`. A missing/stale cache is safe — the sim falls
back to the EW empirical marginals with a logged warning — but the
validated default is the TabPFN shapes.

**Off-season pause / season-start runbook (2026 edition).** Twenty-seven schedulers are PAUSED for the off-season because they only re-process a finished season or require a live Sunday slate: `s-nflverse`, `s-features`, `s-features-route`, `s-train`, `s-train-k1`, `s-train-k1-role`, `s-train-k1-route`, `s-train-k1-route-role`, `s-project-tu`, `s-project-su`, `s-shadow-k1-early`, `s-shadow-k1-late`, `s-shadow-k1-nofloor-early`, `s-shadow-k1-nofloor-late`, `s-shadow-k3-early`, `s-shadow-k3-late`, `s-shadow-k1-roleunion-early`, `s-shadow-k1-roleunion-late`, `s-shadow-k1-route-roleunion-early`, `s-shadow-k1-route-roleunion-late`, `s-shadow-archetype-paired-early`, `s-shadow-archetype-paired-late`, `s-tabpfn-sis-pass-tail-control`, `s-tabpfn-sis-pass-tail-treatment`, `s-shadow-sis-pass-tail-paired`, `s-freeze-tail-early`, `s-freeze-tail-late`. Everything else (odds, DK poll, CFB scaffold, weather, freshness check) stays live year-round. The season-start sequence:

**Backups (updated 2026-08-15).** `s-backup` runs `backup-tables` daily at 07:00 UTC: BigQuery snapshots of the irreplaceable tables (LineStar ownership backfill, standings imports, notes/watchlist, entered lineups, ID overrides, collector-time injury snapshots, and licensed Fantasy Points/SIS imports) into the `nfl_backups` dataset, 30-day retention, delta-billed (~pennies). The current `injury_snapshots`, `fantasy_points_route_share`, `fantasy_points_advanced_prior`, `fantasy_points_receiver_coverage_l4`, `fantasy_points_defense_coverage_l4`, `fantasy_points_advanced_passing_l4`, `fantasy_points_route_shape_l4`, and `fantasy_points_qb_shell_l4` tables are explicit members; every future base table in `nfl_raw` named `fantasy_points_*` or `sis_*` is also discovered automatically, while views and external tables are excluded. Everything else is re-ingestable from source, and BigQuery time travel covers the last 7 days on all tables regardless. Restore: `CREATE TABLE <dataset>.<table> CLONE nfl_backups.<table>_<YYYYMMDD>`. New irreplaceable tables outside those licensed namespaces must still be added to `backup.TABLES` (same discipline as `status.FEEDS`). Runs year-round; never pause it.

| When (2026) | Do |
|---|---|
| **Every Wed 10:00am CT — paid data + Odds API** | Run `source .venv/bin/activate && nfl-weekly-data run --week W`. The command verifies Fantasy Points, deliberately forces a fresh SIS logout/login, verifies the replacement session, then can be left unattended. It triggers the secret-backed Cloud Run `ingest-odds` job and captures the three prospective matchup reports before first kickoff. From Week 2 it downloads only Fantasy Points source Week W-1 Route Share and performs its guarded hash-addressed archive/append. From Week 5 it additionally downloads the exact W-4…W-1 Fantasy Points alignment window and the five frozen SIS pass-tail views, archives their licensed bytes, and appends only provenance-identical/novel rows. Week 5 bootstraps SIS Weeks 1-4; Weeks 6-18 retrieve only W-1. If completed data has not posted, retry Wednesday evening; finish before the Thursday pass-tail caches at 9:15/9:20am CT. The cloud Odds API schedules remain independent: game lines at 9:00am/3:00pm CT Wed-Sun and props Thursday 11:00am CT. `--sis-plan` remains only for a separately approved declarative plan; never point it at closed historical tranches. Never use Week W results to predict Week W. Full behavior is in `automation/fantasy_points/README.md`. |
| **Before Mon Aug 24 — projected ownership collector** | Implement and smoke-test the frozen Fantasy Points ownership protocol in `reports/2026-08-11-fantasy-points-projected-ownership-protocol.md`. Confirm the current subscription can open/export the Premium ownership page; the standalone Data Suite purchase may not include it. Capture DraftKings Classic Sunday Main when first posted, Saturday evening, and twice before the early/final Sunday freezes. Archive bytes/hash/context and append to `nfl_raw.fantasy_points_ownership_snapshots`, which the existing `fantasy_points_*` backup discovery will protect. Use projected ownership for opponent-field simulation, duplication and payout-aware portfolio research—not as a generic penalty to projected player points. Grade every pre-lock snapshot against exact-contest realized ownership after settlement. |
| **Before Mon Aug 24 — calibrated tail-first promotion (completed Aug 14)** | Policy `classic-k1-role12-boom40-poscal-cbwu-v4` uses the frozen 12-candidate role / 40-boom book, the post-TabPFN/post-market mean-invariant position factors QB 0.970, RB 1.005, TE 0.940 and WR 1.070, and the fixed-budget five-search/five-world `CBWU` portfolio. It still returns at most the licensed 80-entry book and fails closed if any registered search/world block is absent. Isolated registry `tail_k1_role` is trained and verified; the prior CE12/boom28 identity-scale fallback remains labeled and single-seed. Keep all role-union and baseline shadows plus both freezers paused until the season-start resume. The authenticated UI → 80 lineups → DKEntries smoke requires the first real slate. Durable validation, revisions, and execution IDs are in `HANDOFF.md`. |
| **Before Mon Aug 24 — cross-environment CBWU determinism gate** | Implement and run the score-free deployment check frozen in `reports/2026-08-16-cbwu-book-instability-and-tie-break-opportunity-reconciliation.md`. Rebuild canonical production CBWU from one immutable source bundle on both the validated replay image and the live serving image/runtime; require byte-identical ordered candidate and exact-80 identities, support masks, p-line counts and mean-total tie-break values. Any mismatch fails closed and blocks scheduler resume until explained. This checks deployment reproducibility only; it must not substitute CBWU-OI, query realized scores or change the money policy. |
| **Before Mon Aug 24 — remove the forensic review corpus** | After the independent review is finished, delete the exact eight-table union of the repair3 manifest (the live unsuffixed four tables) and authoritative repair4 manifest (the four `_repair4` tables) from the production-inaccessible `nfl_forensic_review` dataset with `python scripts/cleanup_final_forensic_warehouse.py --manifest reports/final-forensic-runs/20260814-final-preseason-forensic-v1/freeze_manifest_repair3.json --confirm-manifest-sha 122303a1fc14ae76c9379010eb632b8c4ae837408d4726fe47611ec88be20ce7 --manifest reports/final-forensic-runs/20260814-final-preseason-forensic-v1/freeze_manifest_repair4.json --confirm-manifest-sha 51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02 --receipt reports/final-forensic-runs/20260814-final-preseason-forensic-v1/warehouse_cleanup_receipt.json --delete`; then run the same command with `--verify-only` instead of `--delete`, commit/push the immutable receipt, and only then resume the production schedulers. Before deleting anything, the command requires the isolation dataset's complete inventory to equal those eight exact identities and verifies every schema, manifest label/description and expiration. Afterward the dataset inventory must be empty; the receipt binds both internal manifest SHAs, both manifest-file SHAs, and the exact before/deleted/after identities. The tables have a 90-day automatic expiry only as a backstop—retaining them into the regular-season production window is forbidden. Production code reads only `nfl_raw`, `nfl_features` and `nfl_predictions`; it never reads this isolated dataset. |
| **Mon Aug 24** | Resume only through the fail-closed gate: `python scripts/resume_2026_production_schedulers.py --manifest reports/final-forensic-runs/20260814-final-preseason-forensic-v1/freeze_manifest_repair3.json --confirm-manifest-sha 122303a1fc14ae76c9379010eb632b8c4ae837408d4726fe47611ec88be20ce7 --manifest reports/final-forensic-runs/20260814-final-preseason-forensic-v1/freeze_manifest_repair4.json --confirm-manifest-sha 51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02 --receipt reports/final-forensic-runs/20260814-final-preseason-forensic-v1/warehouse_cleanup_receipt.json` first performs a no-mutation preflight; repeat with `--resume` only after it passes. The command re-verifies the aggregate zero-after receipt and empty isolation-dataset inventory, requires the exact cleanup receipt in pushed `origin/main`, and requires all 27 schedulers to be `PAUSED` with the exact tracked resource name, cadence, `America/Chicago` timezone, POST method, default-compute OAuth identity and Cloud Run v2 target URI before resuming any. Do not use the old raw scheduler loop because it bypasses this cleanup gate. Incumbent training first runs Tue Aug 25 and the isolated Route treatment first runs Thu Aug 27. Baseline/no-floor/K3 pools freeze Sunday-main at 10:30 and 11:20 CT; the role-union control and Route Share treatment freeze at 10:20 and 11:10 CT, then the delayed jobs freeze the predeclared incumbent selector memberships. |
| **Before target Week 5 — SIS pass-tail recurring inputs** | The bounded weekly Fantasy Points W-4…W-1 alignment and five-view SIS acquisition/import are implemented, locally contract-tested, and part of `nfl-weekly-data run --week W`. Perform the first authenticated live smoke when 2026 Weeks 1-4 have posted; verify the run manifest, GCS archives and new 2026 rows in `fantasy_points_alignment_player_l4`, `fantasy_points_alignment_team_l4`, `sis_team_context_game`, and `sis_alignment_attempt_game`. The existing daily licensed-table backup discovers all four automatically. Until that smoke and every downstream source/cache gate pass, the prospective pass-tail jobs fail closed and produce no substitute data. Once available, the GPU control/treatment caches run Thursday at 9:15/9:20am CT and the isolated ten-book paired shadow runs Sunday at 6:00am CT. The money lineup path remains unchanged. |
| **Sat Aug 29** (CFB week 0) | Nothing to start — `ingest-cfb` is already live and self-activating. Verify it caught real slates: System status popup → "CFB slates/salaries" shows rows (or query `nfl_raw.cfb_dk_salaries`). If still 0 after slates exist on DK, the `sportId == 5` filter guess was wrong — check the `ingest-cfb` logs. |
| **Tue-Wed Sep 8-9** | Use Fantasy Points' DraftKings main-slate ownership first if the subscription entitlement and collector check pass. Do **not** automatically buy the previously scheduled ETR weekly pass. Purchase ETR only as a deliberately measured independent second source, or if Fantasy Points ownership is unavailable; if purchased, preserve its own pre-lock snapshot and compare it prospectively rather than silently blending vendors. External point/ceiling divergences remain watchlist evidence, while ownership belongs in field/duplication/payout modeling. |
| **~Thu Sep 3** (week-1 slates post) | The dead-filter check from the deficiency log (2026-07-31): `python -c "import requests; from nfl_dfs.ingest import dk_client; print(len(dk_client.nfl_draft_groups(requests.Session())))"`. Nonzero → close the log row, done. Zero → in `dk_client.py`'s `nfl_draft_groups`, change the filter line to `if g.get("sportId") == 1 and g.get("draftGroupState") == "Upcoming"` (mirror `cfb_draft_groups`), commit, then rebuild+redeploy: `gcloud builds submit --tag us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:latest .` and `gcloud run jobs deploy ingest-dk --image <that tag> --region us-central1 --command nfl-dfs --args ingest-dk --set-env-vars "GCP_PROJECT=nfl-predictions-503414" --memory 2Gi --cpu 1`, then re-run the check via the deployed job and confirm `dk_salaries` gains rows. |
| **Thu Sep 10** (NFL kickoff) | Status popup should be fully green: salaries/odds/props/weather flowing, projections present. Any red is real — the daily check will also have emailed. |
| **Sun Sep 13** (first main slate) | Normal weekly guide flow. First end-to-end test of lineups → CSV → upload. |
| **Every Sunday 9:15am and 10:30am CT — paired construction/recourse shadow** | The paused-until-season schedulers `s-shadow-archetype-paired-early` and `s-shadow-archetype-paired-late` run `nfl-dfs shadow-archetype-paired`. Each invocation uses one salary/projection snapshot to build the incumbent and structural-archetype candidate books from the same five native seed books and player worlds; it freezes exact 20/40/80 memberships plus checksum-bound, create-only control/treatment recourse artifacts and a checksummed manifest under `gs://nfl-predictions-503414-raw/recourse_worlds/`. Confirm the final manifest exists before relying on the UI shadow preview. Neither job changes the money policy or emits an upload. At the late-afternoon decision, load the control artifact matching the submitted incumbent entries, provide timestamped game-status/points-to-date data, preview the changes, then run **Rehearse fill + validation**. The rehearsal binds assignments to exact Entry IDs and returns validation/byte hashes while withholding the generated CSV. Until a later upload route is explicitly licensed, keep the original entries; any missing manifest, stale status, checksum mismatch, validation error, or missed deadline also means no swap. |
| **Every Mon/Tue after settlement** | Download DraftKings **Entry History CSV** and upload it on the Season page. Also download the **full standings CSV for one target GPP per slate while DraftKings still offers it**, save it in the project, and import it with `nfl-dfs import-ownership`; winner-only summaries cannot recover places 2--5, portfolio ranks, payout tiers, or realized ROI. Confirm the standings import retains ordered entries before deleting the source file. |

If resuming is forgotten: the Tuesday-chain feeds are `nfl`-seasonal in `status.py` and go **active Sep 1**, so the daily `check-freshness` starts emailing about their staleness — the system nags you itself. Reverse direction (next off-season, ~mid-February): pause the same twenty-four schedulers again.

| `ingest_nflverse` | Daily 06:00 CT | Year-round; nightly refresh matters in-season |
| `ingest_dk_slate` | Hourly | Thu 00:00 – Mon 04:00 CT |
| `ingest_contests` | Not yet scheduled — opt-in via `INGEST_CONTESTS_ENABLED` (see *Known gaps*: overlay detection scaffold) | Thu 00:00 – Mon 04:00 CT once adopted; denser near each slate's lock for real fill-rate signal |
| `ingest_cfb` | 3× daily (10/14/18 CT) + hourly Sat 08–13 CT (`s-cfb`/`s-cfb-sat`, deployed 2026-07-31 with `INGEST_CFB_ENABLED=1`) | Self-activating: no-ops (one lobby GET) until DK posts CFB draft groups (~late Aug, before NFL week 1); Sat density captures fill-rate trajectory into the main-slate lock |
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
