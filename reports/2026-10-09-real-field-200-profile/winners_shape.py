"""Descriptive (aggregates only): what the real 200+ lineups in his W1-4 fields look like, vs all field lineups and the field's
top 1%. Features: QB stack size (his own team's WR/TE/RB), bring-back count (players from the QB's opponent), the most players
from one game, distinct games, an RB with his own QB, and a DST from the QB's game."""
import sys, collections
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, "/home/erich/projects/nfl-predictions/scripts"); sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
import moneygate_score as MS
cfg = MS.load_config()
rows = []
for w in (1, 2, 3, 4):
    e = cfg["weeks"][str(w)]
    fr = pd.read_parquet(Path(e["t70_run"]) / "frame.parquet")
    info = {}
    for r in fr.itertuples():
        nm = MS.canon(r.display_name)
        info[nm] = (str(r.pos), str(r.team), str(r.opp), str(r.game_id))
    W = MS.load_week(cfg, w)
    f = W.field
    pts = f.points.astype(float).to_numpy() / 100.0
    thr1 = np.quantile(pts, 0.99)
    miss = 0
    for names, p in zip(f.names, pts):
        pl = [info.get(n) for n in (names if isinstance(names, (tuple, list)) else str(names).split("|"))]
        if any(x is None for x in pl):
            miss += 1; continue
        qbs = [x for x in pl if x[0] == "QB"]
        if len(qbs) != 1:
            continue
        qb = qbs[0]
        mates = sum(1 for x in pl if x[1] == qb[1] and x[0] in ("WR", "TE"))
        rbmate = any(x[1] == qb[1] and x[0] == "RB" for x in pl)
        bb = sum(1 for x in pl if x[1] == qb[2] and x[0] in ("WR", "TE", "RB"))
        games = collections.Counter(x[3] for x in pl if x[0] != "DST")
        rows.append((w, p >= 200, p >= thr1, mates, bb, max(games.values()), len(games), rbmate))
    print(f"W{w}: lineups {len(f):,}; unmapped {miss:,}", flush=True)
d = pd.DataFrame(rows, columns=["w", "ge200", "top1", "mates", "bb", "maxgame", "ngames", "rbmate"])
def prof(g):
    return pd.Series({"n": len(g), "QB+0": np.mean(g.mates == 0), "QB+1": np.mean(g.mates == 1), "QB+2": np.mean(g.mates == 2),
                      "QB+3+": np.mean(g.mates >= 3), "bring-back>=1": np.mean(g.bb >= 1), "bring-back>=2": np.mean(g.bb >= 2),
                      "5+ from one game": np.mean(g.maxgame >= 5), "mean max from one game": g.maxgame.mean(),
                      "RB with his QB": np.mean(g.rbmate), "games": g.ngames.mean()})
out = []
for w in (1, 2, 3, 4, "all"):
    g = d if w == "all" else d[d.w == w]
    for lab, sel in (("all lineups", g), ("top 1%", g[g.top1]), ("200+", g[g.ge200])):
        r = prof(sel); r["week"] = w; r["group"] = lab; out.append(r)
t = pd.DataFrame(out).set_index(["week", "group"])
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
print(t.round(3).to_string())

# our own real entries (W.ours), the same features
ours = []
for w in (1, 2, 3, 4):
    e = cfg["weeks"][str(w)]
    fr = pd.read_parquet(Path(e["t70_run"]) / "frame.parquet")
    info = {MS.canon(r.display_name): (str(r.pos), str(r.team), str(r.opp), str(r.game_id)) for r in fr.itertuples()}
    W = MS.load_week(cfg, w)
    f = W.field[W.field.entry_id.isin(W.ours)]
    for names, p in zip(f.names, f.points.astype(float) / 100.0):
        pl = [info.get(n) for n in (names if isinstance(names, (tuple, list)) else str(names).split("|"))]
        if any(x is None for x in pl): continue
        qbs = [x for x in pl if x[0] == "QB"]
        if len(qbs) != 1: continue
        qb = qbs[0]
        mates = sum(1 for x in pl if x[1] == qb[1] and x[0] in ("WR", "TE"))
        rbmate = any(x[1] == qb[1] and x[0] == "RB" for x in pl)
        bb = sum(1 for x in pl if x[1] == qb[2] and x[0] in ("WR", "TE", "RB"))
        games = collections.Counter(x[3] for x in pl if x[0] != "DST")
        ours.append((w, p >= 200, False, mates, bb, max(games.values()), len(games), rbmate))
o = pd.DataFrame(ours, columns=["w", "ge200", "top1", "mates", "bb", "maxgame", "ngames", "rbmate"])
print("\nOUR real entries W1-4:"); print(prof(o).round(3).to_string())
