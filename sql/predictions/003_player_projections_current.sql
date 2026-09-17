-- Current projections per slate week (2026-09-17, defect 27 follow-up).
--
-- `player_projections` is APPEND-ONLY: every `project-slate` run adds a full
-- generation for the week, which is deliberate — the history is what let us
-- prove that the 2026-W2 10:36Z generation was a DK-points-per-game echo of
-- Week 1 and that the 15:02Z generation (prop-market blended) was not.  The
-- cost is that a naive `WHERE season=.. AND week=..` mixes generations and
-- silently doubles the row count.
--
-- Every consumer that wants "the projections in force" must read THIS VIEW.
-- It exposes exactly the newest generation per (season, week), which is the
-- same row set the live builder selects (`MAX(generated_at)`), plus the
-- provenance a reader needs to judge it:
--   generations_for_week  how many runs exist for that week (1 = no re-run)
--   generated_at          the generation in force
-- The market source of a generation is NOT in the table; it lives in the
-- job log ("market blend source: props" vs "dk_ppg").  At week <= 3 a
-- dk_ppg generation is last week's box score and must never feed a money
-- build — see the operating handoff's defect 27.
--
-- Applied by hand on 2026-09-17 (`bq query` of this file with ${predictions}
-- substituted); nothing globs sql/predictions/ automatically (build-features
-- applies sql/features/ only), so re-run this file if the dataset is recreated.
CREATE OR REPLACE VIEW `${predictions}.player_projections_current` AS
WITH gens AS (
  SELECT season, week,
         MAX(generated_at) AS latest,
         COUNT(DISTINCT generated_at) AS generations_for_week
  FROM `${predictions}.player_projections`
  GROUP BY season, week
)
SELECT p.*, g.generations_for_week
FROM `${predictions}.player_projections` p
JOIN gens g
  ON g.season = p.season AND g.week = p.week AND g.latest = p.generated_at;
