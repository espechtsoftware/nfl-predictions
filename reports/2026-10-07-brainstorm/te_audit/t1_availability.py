"""Task 1: data availability by season for the inputs of the TE-vs-defense study (read-only BigQuery)."""
import sys; sys.path.insert(0, ".")
from bqh import q
print("== nfl_raw.pbp, regular season: dropbacks with EPA, defenses, defense-weeks ==")
print(q("""
SELECT season, COUNT(*) plays, COUNTIF(qb_dropback = 1) dropbacks, COUNTIF(qb_dropback = 1 AND epa IS NOT NULL) dropbacks_with_epa,
       COUNT(DISTINCT defteam) n_def, COUNT(DISTINCT CONCAT(defteam, '-', CAST(week AS STRING))) def_weeks,
       MIN(week) wk_min, MAX(week) wk_max, COUNT(DISTINCT game_id) games
FROM `nfl_raw.pbp` WHERE season_type = 'REG' AND season >= 2012 GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("\n== nfl_raw.schedules REG: games, lines present, games with result ==")
print(q("""
SELECT season, COUNT(*) games, COUNTIF(total_line IS NOT NULL AND spread_line IS NOT NULL) with_lines, COUNTIF(result IS NOT NULL) with_result, MAX(week) max_week
FROM `nfl_raw.schedules` WHERE game_type = 'REG' AND season >= 2012 GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("\n== nfl_features.player_week_actuals x player_week_role, by season and position (player-weeks) ==")
print(q("""
SELECT a.season, COUNT(*) all_rows, COUNTIF(r.position = 'QB') qb, COUNTIF(r.position = 'RB') rb, COUNTIF(r.position = 'WR') wr, COUNTIF(r.position = 'TE') te,
       COUNTIF(r.gsis_id IS NULL) no_role_row, COUNT(DISTINCT CONCAT(a.team, '-', CAST(a.week AS STRING))) team_weeks, MAX(a.week) max_week
FROM `nfl_features.player_week_actuals` a LEFT JOIN `nfl_features.player_week_role` r ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week
WHERE a.season >= 2012 GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("\n== production nfl_features.defense_week_allowed: rows and non-null epa_per_dropback_allowed_l6 ==")
print(q("""
SELECT season, COUNT(*) rows_, COUNTIF(epa_per_dropback_allowed_l6 IS NOT NULL) epa_l6_nonnull, COUNTIF(te_fp_allowed_adj_l6 IS NOT NULL) te_adj_nonnull, MAX(week) max_week
FROM `nfl_features.defense_week_allowed` WHERE season >= 2012 GROUP BY 1 ORDER BY 1""").to_string(index=False))
print("\n== player_week_training: rows with non-null epa_per_dropback_allowed_l6 (the feature the models train on) ==")
print(q("""
SELECT season, COUNT(*) rows_, COUNTIF(epa_per_dropback_allowed_l6 IS NOT NULL) epa_l6_nonnull
FROM `nfl_features.player_week_training` WHERE season >= 2012 GROUP BY 1 ORDER BY 1""").to_string(index=False))
