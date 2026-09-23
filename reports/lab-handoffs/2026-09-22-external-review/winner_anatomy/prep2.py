from google.cloud import bigquery
import pandas as pd
P = "nfl-predictions-503414"; c = bigquery.Client(project=P); T = f"`{P}.nfl_raw.contest_entries`"
acct = c.query(f"""SELECT REGEXP_REPLACE(entry_name, r' \\(.*\\)$', '') nm FROM {T} WHERE season=2026 AND week=2
   GROUP BY 1 HAVING COUNT(DISTINCT contest_id)=12 AND COUNT(*)=97""").to_dataframe()
assert len(acct) == 1
open("acct.txt", "w").write(acct.nm[0])        # scratch only; never printed or committed
sch = c.query(f"""SELECT week, game_id, home_team, away_team, gameday, gametime, total_line, spread_line
   FROM `{P}.nfl_raw.schedules` WHERE season=2026 AND week IN (1,2) AND game_type='REG'""").to_dataframe()
sch.to_parquet("sched.parquet"); print("games", len(sch))
# box scores (DK points) and schedules for the winner-registry seasons; the Week-1 ownership shadow
DK = """0.04*IFNULL(passing_yards,0)+4*IFNULL(passing_tds,0)-IFNULL(passing_interceptions,0)+IF(IFNULL(passing_yards,0)>=300,3,0)
 +0.1*IFNULL(rushing_yards,0)+6*IFNULL(rushing_tds,0)+IF(IFNULL(rushing_yards,0)>=100,3,0)
 +IFNULL(receptions,0)+0.1*IFNULL(receiving_yards,0)+6*IFNULL(receiving_tds,0)+IF(IFNULL(receiving_yards,0)>=100,3,0)
 -IFNULL(fumbles_lost_total,0)+2*(IFNULL(passing_2pt_conversions,0)+IFNULL(rushing_2pt_conversions,0)+IFNULL(receiving_2pt_conversions,0))
 +6*IFNULL(special_teams_tds,0)+6*IFNULL(fumble_recovery_tds,0)"""
c.query(f"""SELECT season, week, player_display_name, position, team, opponent_team, {DK} AS dk FROM `{P}.nfl_raw.weekly_stats`
   WHERE season IN (2019,2023,2024,2025) AND season_type="REG" AND position IN ("QB","RB","WR","TE","FB")""").to_dataframe().to_csv("ws_hist.csv", index=False)
c.query(f"""SELECT season, week, home_team, away_team, total_line, spread_line, gametime, weekday FROM `{P}.nfl_raw.schedules`
   WHERE season IN (2019,2023,2024,2025) AND game_type="REG" """).to_dataframe().to_csv("sched_hist.csv", index=False)
c.query(f"""SELECT name, pos, salary, pred_own, generated_at FROM `{P}.nfl_predictions.own_shadow` WHERE season=2026 AND week=1
   QUALIFY generated_at = MAX(generated_at) OVER ()""").to_dataframe().to_csv("own_shadow_w1.csv", index=False)
print("box scores, schedules and own_shadow written")
