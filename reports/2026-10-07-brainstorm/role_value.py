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
                WHERE season BETWEEN 2018 AND 2025 AND week <= 4 AND salary > 0 AND position IN ('RB','WR','TE') GROUP BY 1, 2, 3),
  r AS (SELECT DISTINCT season, week, {NORM.format(x='full_name')} k, gsis_id FROM `nfl_raw.rosters_weekly` WHERE season BETWEEN 2018 AND 2025 AND week <= 4 AND gsis_id IS NOT NULL),
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
S = D[D.starter].copy(); S["cheap"] = S.salary < 4000; S["x4"] = S.dk_points >= 4 * S.salary / 1000; S["mid"] = S.salary.between(6000, 7999)
t = S.groupby("season").apply(lambda z: pd.Series({"starters": len(z), "share priced <$4k": z.cheap.mean(), "cheap: mean pts": z[z.cheap].dk_points.mean(),
     "cheap: pts per $1k": 1000 * z[z.cheap].dk_points.sum() / z[z.cheap].salary.sum(), "cheap: 4x rate": z[z.cheap].x4.mean(),
     "6-8k: pts per $1k": 1000 * z[z.mid].dk_points.sum() / z[z.mid].salary.sum(), "6-8k: 4x rate": z[z.mid].x4.mean()}))
pd.set_option("display.width", 220); print("(1) depth-chart starters (WR <= 3, TE 1, RB <= 2), Sunday main-slate games, weeks 1-4:"); print(t.round(3).to_string())
# (2) stack size in our replay books vs field
rows = []
for w in (2, 3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id")
    m = {str(int(i)): (p, t) for i, p, t in zip(pd.to_numeric(fr.dk_player_id, errors="coerce").fillna(-1), fr.pos, fr.team)}
    for tag, p in (("W5 live", RD / f"w{w}-live/book.csv"), ("entered T-70", Path(CFG["weeks"][str(w)]["t70_run"]) / "book.csv")):
        b = pd.read_csv(p, dtype=str)
        for r in b.values:
            pl = [m.get(v) for v in r if v in m]; qbt = next((t for p_, t in pl if p_ == "QB"), None)
            rows.append({"week": w, "book": tag, "stack_n": sum(1 for p_, t in pl if t == qbt and p_ not in ("QB", "DST"))})
R = pd.DataFrame(rows); R["s"] = R.stack_n.clip(upper=3)
print("\n(2) QB-stack size (teammates of the QB; 3 = 3+), share of rows, W2-4:"); print(R.groupby(["book", "s"]).size().unstack(fill_value=0).pipe(lambda z: z.div(z.sum(1), axis=0)).round(2).to_string())
print("    the real field (multi-entry users, W1-4, from the 10-07 structure screen): QB+1 ~52%, QB+2 ~33%, QB+3+ ~15% of stacked lineups (shares among the compared pairs)")
