from google.cloud import bigquery
import pandas as pd, numpy as np
P = "nfl-predictions-503414"; c = bigquery.Client(project=P)
sql = f"""
WITH grp AS (SELECT 1 AS week, 151307 AS dg, '193028206' AS cid, TIMESTAMP('2026-09-13 17:00:00') AS lk UNION ALL SELECT 2, 153427, '195648007', TIMESTAMP('2026-09-20 17:00:00') UNION ALL SELECT 3, 153769, '195905122', TIMESTAMP('2026-09-27 17:00:00')),
sal AS (SELECT g.week, s.display_name, s.position, s.salary, s.status, s.pulled_at,
          ROW_NUMBER() OVER (PARTITION BY g.week, s.display_name ORDER BY s.pulled_at DESC) rn_last,
          ROW_NUMBER() OVER (PARTITION BY g.week, s.display_name ORDER BY ABS(TIMESTAMP_DIFF(s.pulled_at, TIMESTAMP_SUB(g.lk, INTERVAL 22 HOUR), MINUTE))) rn_sat
        FROM `{P}.nfl_raw.dk_salaries` s JOIN grp g ON s.draft_group_id = g.dg AND s.season = 2026 AND s.pulled_at < g.lk),
last AS (SELECT week, display_name, position, salary, status status_last FROM sal WHERE rn_last = 1),
satp AS (SELECT week, display_name, status status_sat, pulled_at pulled_sat FROM sal WHERE rn_sat = 1),
pj AS (SELECT p.week, p.display_name, p.proj_points, p.generated_at, ROW_NUMBER() OVER (PARTITION BY p.week, p.display_name ORDER BY p.generated_at DESC) rn
       FROM `{P}.nfl_predictions.player_projections` p JOIN grp g ON p.week = g.week WHERE p.season = 2026 AND p.generated_at < g.lk),
own AS (SELECT o.week, o.display_name, SUM(o.pct_drafted) own, MAX(o.fpts) fpts FROM (
          SELECT o.week, o.display_name, o.roster_position, o.pct_drafted, o.fpts FROM `{P}.nfl_raw.contest_ownership` o JOIN grp g ON o.contest_id = g.cid AND o.week = g.week WHERE o.season = 2026
          QUALIFY ROW_NUMBER() OVER (PARTITION BY o.week, o.display_name, o.roster_position ORDER BY o.imported_at DESC) = 1) o GROUP BY 1, 2)
SELECT l.week, l.display_name, l.position, l.salary, l.status_last, s.status_sat, pj.proj_points proj, own.own, own.fpts
FROM last l LEFT JOIN satp s ON s.week = l.week AND s.display_name = l.display_name LEFT JOIN pj ON pj.week = l.week AND pj.display_name = l.display_name AND pj.rn = 1
LEFT JOIN own ON own.week = l.week AND own.display_name = l.display_name
WHERE l.position IN ('QB','RB','WR','TE')"""
d = c.query(sql).to_dataframe(); d.to_parquet("qactive.parquet")
d["fpts"] = d.fpts.fillna(0); d["own"] = d.own.fillna(0)
d["q_sat"] = d.status_sat.astype(str) == "Q"; d["active_last"] = ~d.status_last.astype(str).isin(["O", "OUT", "D", "IR"])
pd.set_option("display.width", 220)
print("2026 Weeks 1-3, skill players on the main slate; 'Q Saturday' = DK status Q at the pull nearest Saturday 11:00 CT; 'active at last pull' = not O/OUT/D/IR at the last pre-lock pull")
g = d[(d.proj >= 6)].groupby(["week", "q_sat", "active_last"]).agg(n=("fpts", "size"), proj=("proj", "mean"), actual=("fpts", "mean"), own=("own", "mean"), pts_per_own=("fpts", lambda x: x.sum() / max(d.loc[x.index, "own"].sum(), 1e-9))).round(2)
print(g.to_string())
qa = d[d.q_sat & d.active_last & (d.proj >= 6)]
print("\nQ-Saturday players still active at the last pull, proj >= 6, all three weeks:", len(qa), "| actual/proj", round(qa.fpts.sum() / qa.proj.sum(), 3), "| mean own", round(qa.own.mean(), 2),
      "| share scoring >= 15:", round((qa.fpts >= 15).mean(), 3), "| share scoring 0:", round((qa.fpts == 0).mean(), 3))
h = d[~d.q_sat & d.active_last & (d.proj >= 6)]
print("healthy comparison, proj >= 6:", len(h), "| actual/proj", round(h.fpts.sum() / h.proj.sum(), 3), "| mean own", round(h.own.mean(), 2), "| share >= 15:", round((h.fpts >= 15).mean(), 3))
print("\nown by projection band, Q-active vs healthy:")
d["band"] = pd.cut(d.proj, [6, 9, 12, 15, 40])
print(d[d.active_last & (d.proj >= 6)].groupby(["band", "q_sat"], observed=True).agg(n=("own", "size"), own=("own", "mean"), actual_over_proj=("fpts", lambda x: x.sum() / d.loc[x.index, "proj"].sum())).round(2).to_string())
