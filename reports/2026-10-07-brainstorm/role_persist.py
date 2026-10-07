"""(1) Cheap-tier value among players with a real PRE-GAME role (player_week_role depth_rank: WR <= 3, TE = 1, RB <= 2),
Sunday main-slate games, weeks 1-4, 2018-2026 -- the same population definition in every season. (2) QB-stack size in our
W2-4 Week-5-settings replay books vs the real field. Aggregates only."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); RD = Path.home() / "rehearsals/outside-cblocks-20261007T153309Z"
NORM = "REGEXP_REPLACE(REGEXP_REPLACE(LOWER({x}), r'\\b(jr|sr|ii|iii|iv|v)\\b\\.?', ''), r'[^a-z]', '')"
H = BQ.query(f"""WITH s AS (SELECT season, week, {NORM.format(x='display_name')} k, MAX(salary) salary FROM `nfl_raw.dk_salaries_historical`
                WHERE season BETWEEN 2018 AND 2025 AND week <= 17 AND salary > 0 AND position IN ('RB','WR','TE') GROUP BY 1, 2, 3),
  r AS (SELECT DISTINCT season, week, {NORM.format(x='full_name')} k, gsis_id FROM `nfl_raw.rosters_weekly` WHERE season BETWEEN 2018 AND 2025 AND week <= 17 AND gsis_id IS NOT NULL),
  g AS (SELECT season, week, home_team team FROM `nfl_raw.schedules` WHERE game_type = 'REG' AND weekday = 'Sunday' AND gametime BETWEEN '13:00' AND '16:30'
        UNION ALL SELECT season, week, away_team FROM `nfl_raw.schedules` WHERE game_type = 'REG' AND weekday = 'Sunday' AND gametime BETWEEN '13:00' AND '16:30')
  SELECT s.season, s.week, w.position, w.depth_rank, s.salary, IFNULL(a.dk_points, 0) dk_points FROM s JOIN r USING (season, week, k)
  JOIN `nfl_features.player_week_role` w ON w.gsis_id = r.gsis_id AND w.season = s.season AND w.week = s.week
  JOIN g ON g.season = s.season AND g.week = s.week AND g.team = w.team
  LEFT JOIN `nfl_features.player_week_actuals` a ON a.gsis_id = r.gsis_id AND a.season = s.season AND a.week = s.week""").to_dataframe()
P = []
for w in (1, 2, 3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id")
    fr = fr[fr.pos.isin(["RB", "WR", "TE"]) & fr.gsis_id.notna()]; P.append(pd.DataFrame({"week": w, "salary": pd.to_numeric(fr.salary).values, "gsis_id": fr.gsis_id.astype(str).values}))
P = pd.concat(P)
x = BQ.query("""SELECT w.gsis_id, w.week, w.position, w.depth_rank, IFNULL(a.dk_points, 0) dk_points FROM `nfl_features.player_week_role` w
  LEFT JOIN `nfl_features.player_week_actuals` a ON a.gsis_id = w.gsis_id AND a.season = w.season AND a.week = w.week WHERE w.season = 2026 AND w.week BETWEEN 1 AND 4""").to_dataframe()
P = P.merge(x, on=["gsis_id", "week"], how="inner").drop(columns="gsis_id"); P["season"] = 2026
D = pd.concat([H, P], ignore_index=True); D["dk_points"] = pd.to_numeric(D.dk_points, errors="coerce").fillna(0); D["depth_rank"] = pd.to_numeric(D.depth_rank, errors="coerce")
D["starter"] = ((D.position == "WR") & (D.depth_rank <= 3)) | ((D.position == "TE") & (D.depth_rank == 1)) | ((D.position == "RB") & (D.depth_rank <= 2))
S = D[D.starter].copy(); S["cheap"] = S.salary < 4000; S["x4"] = S.dk_points >= 4 * S.salary / 1000
S["block"] = pd.cut(S.week, [0, 4, 8, 12, 17], labels=["W1-4", "W5-8", "W9-12", "W13-17"])
C = S[S.cheap].groupby(["season", "block"], observed=True).apply(lambda z: pd.Series({"n": len(z), "ppk": 1000 * z.dk_points.sum() / z.salary.sum(), "x4": z.x4.mean()}))
pd.set_option("display.width", 200)
print("cheap (<$4k) depth-chart starters, by season and block of weeks: points per $1k / 4x-salary rate / n")
print(C.ppk.unstack().round(2).to_string()); print(C.x4.unstack().round(3).to_string()); print(C.n.unstack().fillna(0).astype(int).to_string())
h = C.ppk.unstack().drop(index=2026, errors="ignore")
print("\nacross 2018-2025: correlation of W1-4 with W5-8 cheap value (ppk) %.2f; with the rest of the season (W5-17 mean) %.2f" % (h["W1-4"].corr(h["W5-8"]), h["W1-4"].corr(h[["W5-8", "W9-12", "W13-17"]].mean(1))))
x = C.x4.unstack().drop(index=2026, errors="ignore")
print("same for the 4x rate: W1-4 vs W5-8 %.2f; vs W5-17 %.2f" % (x["W1-4"].corr(x["W5-8"]), x["W1-4"].corr(x[["W5-8", "W9-12", "W13-17"]].mean(1))))
wk = S[S.cheap].groupby(["season", "week"]).apply(lambda z: 1000 * z.dk_points.sum() / z.salary.sum()).rename("ppk").reset_index()
wk["lag4"] = wk.groupby("season").ppk.transform(lambda v: v.shift(1).rolling(4, min_periods=4).mean())
hh = wk[(wk.season <= 2025) & wk.lag4.notna()]
print("week level 2018-2025: correlation of a week's cheap ppk with the previous 4 weeks' mean %.2f (n %d weeks)" % (hh.ppk.corr(hh.lag4), len(hh)))
