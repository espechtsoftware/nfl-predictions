"""QB game-total rank of the W2-4 replay books at the Week-5 settings (live, cheap +2, cheap +4), their candidate pools,
and the entered T-70 books; plus each week's realized best stacking game (QB + top-2 teammates + top opponent)."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); RD = Path.home() / "rehearsals/outside-cblocks-20261007T153309Z"
act = BQ.query("""SELECT a.week, a.gsis_id, a.team, r.position, a.dk_points FROM `nfl_features.player_week_actuals` a JOIN `nfl_features.player_week_role` r
  ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week WHERE a.season = 2026 AND a.week BETWEEN 1 AND 4 AND r.position IN ('QB','RB','WR','TE')""").to_dataframe()
act["dk_points"] = act.dk_points.astype(float)
rows = []
for w in (1, 2, 3, 4):
    t70 = Path(CFG["weeks"][str(w)]["t70_run"]); fr = pd.read_parquet(t70 / "frame.parquet").drop_duplicates("dk_player_id")
    gt = fr.groupby("game_id").game_total.max().astype(float); kmap = gt.rank(ascending=False, method="first").astype(int).to_dict(); ng = len(gt)
    team_game = dict(zip(fr.team, fr.game_id))
    a = act[act.week == w].copy(); a["game_id"] = a.team.map(team_game); a = a[a.game_id.notna()]
    best = {}
    for gid, g in a.groupby("game_id"):
        vals = []
        for tm, t in g.groupby("team"):
            qb = t[t.position == "QB"].dk_points.max(); qb = 0.0 if np.isnan(qb) else qb
            mates = np.sort(t[t.position != "QB"].dk_points.values)[::-1][:2].sum()
            opp = g[(g.team != tm) & (g.position != "QB")].dk_points.max(); opp = 0.0 if np.isnan(opp) else opp
            vals.append(qb + mates + opp)
        best[gid] = max(vals)
    bg = max(best, key=best.get); bk = kmap[bg]
    qbk = {str(int(i)): kmap.get(g) for i, g, p in zip(pd.to_numeric(fr.dk_player_id, errors="coerce"), fr.game_id, fr.pos) if p == "QB" and not np.isnan(i)}
    books = {"T-70 entered": t70 / "book.csv"}
    if w >= 2:
        books.update({"W5 live": RD / f"w{w}-live/book.csv", "W5 cheap+2": RD / f"w{w}-cblock2/book.csv", "W5 cheap+4": RD / f"w{w}-cblock4/book.csv"})
    for tag, p in books.items():
        if not p.exists(): continue
        b = pd.read_csv(p, dtype=str); ks = [next((qbk[v] for v in r if v in qbk), np.nan) for r in b.values]
        rows.append({"week": w, "book": tag, "rows": len(ks), "games": ng, "best_game_rank": bk, "rows_in_best_game": int(sum(k == bk for k in ks)),
                     "top4": np.mean([k <= 4 for k in ks]), "rank6plus": np.mean([k >= 6 for k in ks]), "k1": np.mean([k == 1 for k in ks]), "k2": np.mean([k == 2 for k in ks]),
                     "k3": np.mean([k == 3 for k in ks]), "k4": np.mean([k == 4 for k in ks])})
    if w >= 2:
        c = pd.read_parquet(RD / f"w{w}-live/candidates.parquet"); qcol = [x for x in c.columns if x.upper() in ("QB", "QB_ID", "QB_DK_ID")]
        if qcol:
            ks = c[qcol[0]].astype(str).map(qbk); rows.append({"week": w, "book": "W5 pool", "rows": len(c), "games": ng, "best_game_rank": bk, "rows_in_best_game": int((ks == bk).sum()),
                     "top4": (ks <= 4).mean(), "rank6plus": (ks >= 6).mean(), "k1": (ks == 1).mean(), "k2": (ks == 2).mean(), "k3": (ks == 3).mean(), "k4": (ks == 4).mean()})
        else:
            print("pool columns:", list(c.columns)[:30])
R = pd.DataFrame(rows); pd.set_option("display.width", 220)
print(R.round(2).to_string(index=False))
print("\nmean over W2-4 by book: top-4 share / rank 6+ share (history: top-4 games hold the best stack 55% of slates, 2020-25 60%; rank 6+ 38%):")
print(R[R.week >= 2].groupby("book")[["top4", "rank6plus", "k1", "k2", "k3", "k4"]].mean().round(2).to_string())
