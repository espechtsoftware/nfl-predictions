"""Does the 2026 W2-4 'hot player' pattern hold under study 109's exact flag? Two definitions per player:
  MINE (the 10-10 screen): last game >= 2x the mean of up to 8 prior games (2025-26), >= 3 prior games, mean floor 3.
  LAB (study 65 / 109):   last regular-season game THIS season before W; prior = up to 4 games just before it (this season
                          and the previous season); >= 2 prior games; last >= 2.0 x max(mean, 5).
Within-user MH odds (users with 20+ Millionaire entries) of a top-1% / top-4% finish for '1+ hot vs 0', by week, both flags;
and the group means. Aggregates only; user names fingerprinted server-side."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery

OUT = Path(__file__).resolve().parent / "hot_check_out"; OUT.mkdir(exist_ok=True)
BQ = bigquery.Client(project="nfl-predictions-503414")
CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
log = open(OUT / "run.log", "w")
def say(*a): print(*a, flush=True); print(*a, file=log, flush=True)

def flags(fr, w):
    ids = fr.gsis_id.dropna().astype(str).unique().tolist()
    a = BQ.query("""SELECT gsis_id, season, week, dk_points FROM `nfl_features.player_week_actuals`
                    WHERE gsis_id IN UNNEST(@ids) AND has_stat_line AND ((season = 2025) OR (season = 2026 AND week < @w))
                    ORDER BY gsis_id, season, week""",
                 job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("ids", "STRING", ids),
                                                                       bigquery.ScalarQueryParameter("w", "INT64", w)])).to_dataframe()
    mine, lab = {}, {}
    for gid, g in a.groupby("gsis_id"):
        pts = g.dk_points.astype(float).tolist(); seasons = g.season.astype(int).tolist()
        if len(pts) >= 4:
            last, prior = pts[-1], pts[-9:-1]; avg = float(np.mean(prior))
            if avg >= 3: mine[gid] = int(last >= 2.0 * avg)
        if seasons[-1] == 2026 and len(pts) >= 3:          # the last game is this season's; >= 2 prior games
            last, prior = pts[-1], pts[-5:-1]; avg = float(np.mean(prior))
            lab[gid] = int(last >= 2.0 * max(avg, 5.0))
    return mine, lab

SQL = """WITH m AS (SELECT n, h1, h2 FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@hm) h1 WITH OFFSET j ON i=j JOIN UNNEST(@hl) h2 WITH OFFSET k ON i=k),
e0 AS (SELECT DISTINCT contest_id, entry_id, rank, FARM_FINGERPRINT(TRIM(SPLIT(entry_name,' (')[OFFSET(0)])) u, players_key
       FROM `nfl_raw.contest_entries` WHERE season=2026 AND week=@w AND contest_id = @c AND points IS NOT NULL),
e AS (SELECT *, COUNT(*) OVER () cnt FROM e0),
x AS (SELECT e.u, e.entry_id, ANY_VALUE(e.rank) rank, ANY_VALUE(e.cnt) cnt, SUM(m.h1) hot_mine, SUM(m.h2) hot_lab, COUNT(m.n) matched
      FROM e, UNNEST(SPLIT(e.players_key,'|')) nm LEFT JOIN m ON m.n = nm GROUP BY 1,2)
SELECT u, rank, cnt, hot_mine, hot_lab FROM x WHERE matched = 9"""

rows = []
for w in (2, 3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    fr = fr[pd.to_numeric(fr.salary, errors="coerce").notna()].drop_duplicates("display_name").copy()
    mine, lab = flags(fr, w)
    hm = fr.gsis_id.astype(str).map(mine).fillna(0).astype(int); hl = fr.gsis_id.astype(str).map(lab).fillna(0).astype(int)
    say(f"W{w}: frame {len(fr)}; hot players MINE {int(hm.sum())} LAB {int(hl.sum())}; both {int(((hm==1)&(hl==1)).sum())}; mine-only {int(((hm==1)&(hl==0)).sum())}; lab-only {int(((hm==0)&(hl==1)).sum())}")
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("w", "INT64", w),
        bigquery.ScalarQueryParameter("c", "STRING", CFG["weeks"][str(w)]["millionaire_contest"]),
        bigquery.ArrayQueryParameter("names", "STRING", fr.display_name.astype(str).tolist()),
        bigquery.ArrayQueryParameter("hm", "INT64", hm.tolist()), bigquery.ArrayQueryParameter("hl", "INT64", hl.tolist())])
    d = BQ.query(SQL, job_config=cfg).to_dataframe(); d["week"] = w; rows.append(d)
D = pd.concat(rows, ignore_index=True)
for c in ("rank", "cnt", "hot_mine", "hot_lab"): D[c] = pd.to_numeric(D[c])
D["pct"] = D["rank"] / D["cnt"]; D["uw"] = D.week.astype(str) + "|" + D.u.astype(str)
say("\n=== group means per lineup (field / top 1% / top 0.1%) ===")
for w, X in D.groupby("week"):
    for name, mask in {"field": X.pct <= 1, "top 1%": X.pct <= 0.01, "top 0.1%": X.pct <= 0.001}.items():
        g = X[mask]; say(f"W{w} {name:>8}: n {len(g):>7,}  hot MINE {g.hot_mine.mean():.2f} (share>=1 {float((g.hot_mine>=1).mean()):.3f})  hot LAB {g.hot_lab.mean():.2f} (share>=1 {float((g.hot_lab>=1).mean()):.3f})")

def mh(X, ex, ref, out):
    Z = X[ex | ref].assign(E=ex[ex | ref].astype(int), o=X.loc[ex | ref, out].astype(int))
    g = Z.groupby(["uw", "E"]).o.agg(["size", "sum"]).reset_index()
    s = g.pivot_table(index="uw", columns="E", values=["size", "sum"], fill_value=0)
    for col in (("size", 0), ("size", 1), ("sum", 0), ("sum", 1)):
        if col not in s.columns: s[col] = 0
    a = s[("sum", 1)]; b = s[("size", 1)] - a; c = s[("sum", 0)]; d_ = s[("size", 0)] - c; n = a + b + c + d_
    num = (a * d_ / n.replace(0, np.nan)).fillna(0); den = (b * c / n.replace(0, np.nan)).fillna(0)
    return num.sum() / den.sum() if den.sum() > 0 else np.nan
big = D.groupby("uw").uw.transform("size") >= 20; M = D[big].copy()
say("\n=== within-user MH odds, users with 20+ entries: '1+ hot vs 0' ===")
for w, X in M.groupby("week"):
    X = X.copy(); X["t1"] = (X.pct <= 0.01).astype(int); X["t4"] = (X.pct <= 0.04).astype(int); X["t10"] = (X.pct <= 0.10).astype(int)
    r = {}
    for lab_, col in (("MINE", "hot_mine"), ("LAB", "hot_lab")):
        ex = X[col] >= 1; ref = X[col] == 0
        r[lab_] = tuple(round(mh(X, ex, ref, o), 2) for o in ("t1", "t4", "t10"))
    say(f"W{w}: MINE top1/top4/top10 {r['MINE']} | LAB {r['LAB']}  (n {len(X):,})")
say("done")
