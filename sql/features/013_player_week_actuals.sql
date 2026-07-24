-- Realized per-player-week stat lines and DK classic points (labels).
-- Sourced from nflverse weekly_stats; DK scoring incl. yardage bonuses.
CREATE OR REPLACE TABLE `${features}.player_week_actuals` AS
SELECT
  player_id AS gsis_id,
  season, week,
  team,
  targets, receptions,
  receiving_yards   AS rec_yards,
  receiving_tds     AS rec_tds,
  carries,
  rushing_yards     AS rush_yards,
  rushing_tds       AS rush_tds,
  attempts          AS pass_attempts,
  completions,
  passing_yards     AS pass_yards,
  passing_tds       AS pass_tds,
  passing_interceptions AS interceptions,
  sack_fumbles_lost + rushing_fumbles_lost + receiving_fumbles_lost AS fumbles_lost,
  passing_2pt_conversions + rushing_2pt_conversions + receiving_2pt_conversions AS two_pt,
  special_teams_tds,

  -- DK classic scoring (see guide §6.1)
  0.04 * passing_yards
    + 4 * passing_tds
    + IF(passing_yards >= 300, 3, 0)
    - 1 * passing_interceptions
    + 0.1 * rushing_yards
    + 6 * rushing_tds
    + IF(rushing_yards >= 100, 3, 0)
    + 1 * receptions
    + 0.1 * receiving_yards
    + 6 * receiving_tds
    + IF(receiving_yards >= 100, 3, 0)
    - 1 * (sack_fumbles_lost + rushing_fumbles_lost + receiving_fumbles_lost)
    + 2 * (passing_2pt_conversions + rushing_2pt_conversions + receiving_2pt_conversions)
    + 6 * special_teams_tds
  AS dk_points
FROM `${raw}.weekly_stats`
WHERE season_type = 'REG';
