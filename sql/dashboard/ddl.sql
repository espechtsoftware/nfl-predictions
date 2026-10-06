-- Dashboard v2 dataset (2026-10-03). Applied once by the operator; render the
-- placeholders first:
--   python -c "from nfl_dfs.dashboard.data import render; print(render('ddl'))" \
--     | bq query --use_legacy_sql=false
-- Only scripts/publish_dashboard_week.py --apply writes these tables; the app
-- only reads them. Rows are compact derived numbers: no entry keys, no stake
-- plan, no licensed vendor rows.
CREATE SCHEMA IF NOT EXISTS `${dashboard}`
OPTIONS (location = 'US', description = 'Dashboard v2: published pool exposure and arm results');

-- One row per player per published run: how often the player appears in our
-- candidate pool and in the book the week used.
CREATE TABLE IF NOT EXISTS `${dashboard}.pool_exposure` (
  season INT64 NOT NULL,
  week INT64 NOT NULL,
  run_id STRING NOT NULL,          -- lab live run directory name
  built_utc TIMESTAMP,             -- the run receipt's built_utc
  player STRING,                   -- DraftKings display name
  dk_player_id INT64,
  position STRING,
  team STRING,                     -- canonical nflverse code (LA, not LAR)
  pool_share FLOAT64,              -- n_pool / pool lineups
  book_share FLOAT64,              -- n_book / book lineups
  n_pool INT64,
  n_book INT64,
  book_source STRING,              -- which book book_share describes (played | book), with its files
  published_utc TIMESTAMP          -- readers take the newest publication per week
)
CLUSTER BY season, week;

-- One row per arm (book, shadow, ordering, upload file) per week.
CREATE TABLE IF NOT EXISTS `${dashboard}.arms_weekly` (
  season INT64 NOT NULL,
  week INT64 NOT NULL,
  arm STRING NOT NULL,
  kind STRING,                     -- pool | book (pre-R4 union book.csv) | played (upload files after
                                   -- R4/swap) | vetted | shadow | cash_shadow | paper | ordering | upload
  contest_id STRING,               -- set for per-contest upload files
  n_lineups INT64,
  mean_points FLOAT64,             -- realized DK points; NULL before the games are scored
  best_points FLOAT64,
  best_rank INT64,                 -- 1 + Millionaire entries scoring above best_points
  cash_rate FLOAT64,               -- share >= the cash line: the arm's own contest for upload
                                   -- files, else the Millionaire's; NULL without contest details
  source_file STRING,              -- path relative to the snapshot root
  source_sha256 STRING,
  published_utc TIMESTAMP
)
CLUSTER BY season, week;

-- One row per contest in the week's DraftKings contest details (snapshotted
-- by the publisher): paid places from the payout ladder, and the cash line =
-- the points at the last paid rank in the imported standings (NULL when the
-- standings or the details are missing).
CREATE TABLE IF NOT EXISTS `${dashboard}.contest_lines` (
  season INT64 NOT NULL,
  week INT64 NOT NULL,
  contest_id STRING NOT NULL,
  contest_name STRING,
  draft_group_id INT64,
  field_size INT64,
  paid_places INT64,
  cash_line FLOAT64,
  source_file STRING,
  source_sha256 STRING,
  published_utc TIMESTAMP
)
CLUSTER BY season, week;
