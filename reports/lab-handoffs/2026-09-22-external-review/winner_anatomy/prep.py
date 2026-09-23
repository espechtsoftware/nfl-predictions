from google.cloud import bigquery
import pandas as pd
P = "nfl-predictions-503414"; c = bigquery.Client(project=P)
CONTESTS = {1: ["193028206", "193028208"], 2: ["195648007", "195661344", "195661326", "195661380", "195661365"]}
ids = ",".join(f'"{x}"' for v in CONTESTS.values() for x in v)
e = c.query(f"""SELECT week, contest_id, contest_name, rank, entry_name, points, lineup_slots_json
  FROM `{P}.nfl_raw.contest_entries` WHERE season=2026 AND contest_id IN ({ids})""").to_dataframe()
e.to_parquet("entries.parquet"); print("entries", len(e))
s = c.query(f"""SELECT draft_group_id, display_name, team_abbr, position, salary, game_start, dk_player_id, status, pulled_at
  FROM `{P}.nfl_raw.dk_salaries` WHERE draft_group_id IN (151307, 153428)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY draft_group_id, dk_player_id ORDER BY pulled_at DESC) = 1""").to_dataframe()
s["week"] = s.draft_group_id.map({151307: 1, 153428: 2}); s.to_parquet("salaries.parquet"); print("salaries", len(s))
o = c.query(f"""WITH d AS (SELECT DISTINCT week, contest_id, display_name, roster_position, pct_drafted, fpts
  FROM `{P}.nfl_raw.contest_ownership` WHERE season=2026 AND contest_id IN ({ids}))
  SELECT week, contest_id, display_name, SUM(pct_drafted) own, MAX(fpts) fpts FROM d GROUP BY 1,2,3""").to_dataframe()
o.to_parquet("ownership.parquet"); print("ownership", len(o), o.groupby("contest_id").own.sum().round(0).to_dict())
