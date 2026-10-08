"""Task 5e: the four games behind the real-field result: who scored, and what the defenses looked like game by game in 2026."""
import sys; sys.path.insert(0, ".")
import pandas as pd
from bqh import q
pd.set_option("display.width", 220)
print(q("""
WITH pw AS (SELECT a.season, a.week, a.team, r.position pos, p.full_name nm, a.dk_points dk, a.targets
            FROM `nfl_features.player_week_actuals` a JOIN `nfl_features.player_week_role` r USING (gsis_id, season, week)
            LEFT JOIN (SELECT gsis_id, ANY_VALUE(full_name) full_name FROM `nfl_raw.rosters_weekly` WHERE season = 2026 GROUP BY 1) p USING (gsis_id)
            WHERE a.season = 2026 AND a.has_stat_line AND r.position IN ('QB', 'TE', 'WR'))
SELECT week, team, pos, nm, ROUND(dk, 1) dk, targets FROM pw
WHERE (week = 3 AND team IN ('SF', 'NO', 'ARI')) OR (week = 4 AND team IN ('LV', 'JAX'))
QUALIFY ROW_NUMBER() OVER (PARTITION BY week, team, pos ORDER BY dk DESC) <= IF(pos = 'WR', 2, 1)
ORDER BY week, team, pos""").to_string(index=False))
print("\n2026 game-by-game EPA per dropback allowed (pbp) for the defenses involved, and the frame value used:")
print(q("""SELECT defteam d, week, ROUND(AVG(epa), 3) epa_db, COUNT(*) dropbacks FROM `nfl_raw.pbp`
           WHERE season = 2026 AND season_type = 'REG' AND qb_dropback = 1 AND epa IS NOT NULL AND defteam IN ('ARI', 'SF', 'LV', 'KC', 'CIN')
           GROUP BY 1, 2 ORDER BY 1, 2""").pivot(index="d", columns="week", values="epa_db").to_string())
print("frame values: W3 ARI -0.19 (=week 1 only), W3 SF -0.35 (=wk1), W3 LV -0.21 (=wk1), W4 KC -0.16 (=mean wk1-2), W4 CIN -0.20 (=mean wk1-2)")
