import pandas as pd
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
R = pd.read_parquet("rb_returners.parquet")
ws = query_df(f"""SELECT player_id gsis_id, season, week FROM `{settings.raw}.weekly_stats` WHERE season BETWEEN 2014 AND 2025 AND season_type='REG'""")
wsk = set(zip(ws.gsis_id, ws.season, ws.week))
sn = query_df(f"""SELECT i.gsis_id, CAST(n.season AS INT64) season, CAST(n.week AS INT64) week, MAX(n.offense_snaps) snaps
                  FROM `{settings.raw}.snap_counts` n JOIN `{settings.raw}.player_ids` i ON i.pfr_id = n.pfr_player_id
                  WHERE i.gsis_id IS NOT NULL AND CAST(n.season AS INT64) BETWEEN 2014 AND 2025 GROUP BY 1,2,3""")
snk = {(g, s, w): x for g, s, w, x in zip(sn.gsis_id, sn.season, sn.week, sn.snaps)}
R["played_prev"] = [((g, s, w - 1) in wsk) or (snk.get((g, s, w - 1), 0) or 0) > 0 for g, s, w in zip(R.gsis_id, R.season, R.week)]
R["pos_ctrl"] = [((g, s, w) in wsk) or (snk.get((g, s, w), 0) or 0) > 0 for g, s, w in zip(R.gsis_id, R.season, R.week)]
print(f"RB returners {len(R)}: played W-1 per box/snaps {int(R.played_prev.sum())}; positive control at W {R.pos_ctrl.mean():.3f}")
print(R.groupby(R.season >= 2022).agg(n=("gsis_id", "size"), false=("played_prev", "sum")).rename(index={False: "2014-21", True: "2022-24"}).to_string())
