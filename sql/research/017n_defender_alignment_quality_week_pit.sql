-- Defender/alignment prior quality and workload (matchup plan §5.3, P2 v1).
--
-- RESEARCH TABLE, outside the production build glob; executed by
-- scripts/build_receiver_matchup_features.py.
--
-- Source: `${raw}.sis_receiver_copula_player_game` — per defender-game
-- Wide/Slot coverage snaps, targets, completions, yards and TDs. These
-- rows identify the defender and alignment but NOT which receiver he
-- covered; nothing here is an assignment claim (plan §2.1).
-- `defender_exposure_weight` is defined ONLY as the defender's share of
-- his defense's prior coverage workload for that alignment: evidence
-- grain `sis-defender-alignment`, inferred-from-prior-alignment-workload.
--
-- PIT construction: windows are computed per defender THROUGH each of his
-- own games (7 PRECEDING..CURRENT ROW), then AS-OF joined to every later
-- defense game week within the defense's last-eight-game horizon. Row
-- existence for target week W therefore requires only that the defender
-- played for this defense inside its prior eight games — never that he
-- played week W itself, which is not pre-lock knowledge. Week-W injury/
-- roster state joins at P3 from the injury snapshots.
--
-- Efficiency rates are ratio-of-sums with the frozen pseudo-count-16
-- shrinkage toward the league cumulative same-alignment prior strictly
-- before the target week. Receiving DK allowed at defender grain is
-- completions + 0.1*yards + 6*TDs (the 100-yard bonus is not
-- attributable to a single defender and is deliberately absent).
--
-- Identity note (plan §5.3): defender ids are SIS ids with vendor names;
-- the SIS/PFR/GSIS crosswalk with resolved/ambiguous/unresolved states is
-- P3 work — nothing is guessed here.

CREATE OR REPLACE TABLE `${features}.defender_alignment_quality_week_pit` AS
WITH defender_games AS (
  SELECT
    defender_player_id,
    defender_name,
    defense,
    season,
    week,
    LOWER(alignment) AS alignment,
    coverage_snaps,
    targets,
    completions,
    yards,
    touchdowns,
    completions * 1.0 + yards * 0.1 + touchdowns * 6.0 AS receiving_dk
  FROM `${raw}.sis_receiver_copula_player_game`
  WHERE defender_player_id IS NOT NULL
    AND coverage_snaps IS NOT NULL
),
-- Windows THROUGH each defender game (inclusive): as-of values for any
-- strictly later target week.
through_games AS (
  SELECT
    d.*,
    COUNT(d.week) OVER through_8 AS games_through_8,
    SUM(d.coverage_snaps) OVER through_8 AS coverage_snaps_l8,
    SUM(d.targets) OVER through_8 AS targets_l8,
    SUM(d.completions) OVER through_8 AS completions_l8,
    SUM(d.yards) OVER through_8 AS yards_l8,
    SUM(d.touchdowns) OVER through_8 AS touchdowns_l8,
    SUM(d.receiving_dk) OVER through_8 AS receiving_dk_l8
  FROM defender_games d
  WINDOW through_8 AS (
    PARTITION BY d.defender_player_id, d.alignment
    ORDER BY d.season, d.week
    ROWS BETWEEN 7 PRECEDING AND CURRENT ROW
  )
),
defense_weeks AS (
  SELECT DISTINCT defense, season, week FROM defender_games
),
defense_seq AS (
  SELECT
    defense,
    season,
    week,
    ROW_NUMBER() OVER (
      PARTITION BY defense ORDER BY season, week
    ) AS defense_game_ordinal
  FROM defense_weeks
),
-- As-of join: for each target defense week, each defender's most recent
-- through-game row from this defense's prior eight game weeks.
asof AS (
  SELECT
    target.defense,
    target.season,
    target.week,
    target.defense_game_ordinal AS target_defense_ordinal,
    g.alignment,
    g.defender_player_id,
    g.defender_name,
    g.season * 100 + g.week AS max_source_season_week,
    g.games_through_8 AS prior_games_l8,
    g.coverage_snaps_l8,
    g.targets_l8,
    g.completions_l8,
    g.yards_l8,
    g.touchdowns_l8,
    g.receiving_dk_l8
  FROM defense_seq target
  JOIN defense_seq source_game
    ON source_game.defense = target.defense
   AND source_game.defense_game_ordinal
       BETWEEN target.defense_game_ordinal - 8
           AND target.defense_game_ordinal - 1
  JOIN through_games g
    ON g.defense = source_game.defense
   AND g.season = source_game.season
   AND g.week = source_game.week
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY target.defense, target.season, target.week,
      g.alignment, g.defender_player_id
    ORDER BY g.season DESC, g.week DESC
  ) = 1
),
league_week AS (
  SELECT
    alignment,
    season,
    week,
    SUM(targets) AS week_targets,
    SUM(completions) AS week_completions,
    SUM(yards) AS week_yards,
    SUM(touchdowns) AS week_touchdowns,
    SUM(receiving_dk) AS week_dk,
    SUM(coverage_snaps) AS week_snaps
  FROM defender_games
  GROUP BY alignment, season, week
),
league_prior AS (
  SELECT
    alignment,
    season,
    week,
    SUM(week_targets) OVER league_window AS league_targets_prior,
    SUM(week_completions) OVER league_window AS league_completions_prior,
    SUM(week_yards) OVER league_window AS league_yards_prior,
    SUM(week_touchdowns) OVER league_window AS league_touchdowns_prior,
    SUM(week_dk) OVER league_window AS league_dk_prior,
    SUM(week_snaps) OVER league_window AS league_snaps_prior
  FROM league_week
  WINDOW league_window AS (
    PARTITION BY alignment ORDER BY season, week
    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
  )
),
with_team AS (
  SELECT
    a.*,
    SUM(a.coverage_snaps_l8) OVER defense_week
      AS defense_alignment_snaps_l8,
    RANK() OVER (
      PARTITION BY a.defense, a.season, a.week, a.alignment
      ORDER BY a.coverage_snaps_l8 DESC, a.defender_player_id ASC
    ) AS workload_rank
  FROM asof a
  WINDOW defense_week AS (
    PARTITION BY a.defense, a.season, a.week, a.alignment
  )
)
SELECT
  t.defense,
  t.season,
  t.week,
  t.alignment,
  t.defender_player_id,
  t.defender_name,
  t.max_source_season_week,
  t.prior_games_l8,
  t.coverage_snaps_l8,
  t.targets_l8,
  t.completions_l8,
  t.yards_l8,
  t.touchdowns_l8,
  t.receiving_dk_l8,
  SAFE_DIVIDE(t.targets_l8, t.coverage_snaps_l8)
    AS target_rate_per_snap_raw_l8,
  SAFE_DIVIDE(t.completions_l8, t.targets_l8)
    AS completion_rate_allowed_raw_l8,
  SAFE_DIVIDE(t.yards_l8, t.targets_l8)
    AS yards_per_target_allowed_raw_l8,
  SAFE_DIVIDE(t.receiving_dk_l8, t.targets_l8)
    AS dk_per_target_allowed_raw_l8,
  SAFE_DIVIDE(
    t.completions_l8
      + 16 * SAFE_DIVIDE(lp.league_completions_prior, lp.league_targets_prior),
    t.targets_l8 + 16
  ) AS completion_rate_allowed_shrunk_l8,
  SAFE_DIVIDE(
    t.yards_l8
      + 16 * SAFE_DIVIDE(lp.league_yards_prior, lp.league_targets_prior),
    t.targets_l8 + 16
  ) AS yards_per_target_allowed_shrunk_l8,
  SAFE_DIVIDE(
    t.touchdowns_l8
      + 16 * SAFE_DIVIDE(lp.league_touchdowns_prior, lp.league_targets_prior),
    t.targets_l8 + 16
  ) AS tds_per_target_allowed_shrunk_l8,
  SAFE_DIVIDE(
    t.receiving_dk_l8
      + 16 * SAFE_DIVIDE(lp.league_dk_prior, lp.league_targets_prior),
    t.targets_l8 + 16
  ) AS dk_per_target_allowed_shrunk_l8,
  SAFE_DIVIDE(lp.league_dk_prior, lp.league_targets_prior)
    AS league_dk_per_target_prior,
  SAFE_DIVIDE(lp.league_targets_prior, lp.league_snaps_prior)
    AS league_target_rate_per_snap_prior,
  t.defense_alignment_snaps_l8,
  SAFE_DIVIDE(t.coverage_snaps_l8, t.defense_alignment_snaps_l8)
    AS defender_exposure_weight,
  'inferred-from-prior-alignment-workload' AS exposure_weight_semantics,
  'sis-defender-alignment' AS source_grain,
  t.workload_rank,
  (t.workload_rank <= 2) AS top_two_workload_defender,
  (t.prior_games_l8 >= 4 AND t.coverage_snaps_l8 > 0)
    AS defender_supported,
  IF(t.prior_games_l8 >= 4 AND t.coverage_snaps_l8 > 0, NULL,
     'below-support-threshold') AS defender_support_reason
FROM with_team t
LEFT JOIN league_prior lp
  ON lp.alignment = t.alignment
 AND lp.season = t.season
 AND lp.week = t.week
