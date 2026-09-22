"""Which generation mechanisms reach the ceiling? Week-2 2026 pool (12,555 unique candidates, run built
2026-09-19 15:30Z, draft group 153428: lev x2560 = optimize_many on proj_tourney; boom x10240 = one
optimal lineup per simulated world, worlds visited in 'total' order).
Declared before running: per batch report pool share, mean / best / p99 realized, and share of the
pool's top-1% realized lineups with lift = top-1% share / pool share (null = 1.0) and a hypergeometric
two-sided p. Batches: tag; lev solve-order quintile; boom world-order quintile; structure (QB stack
size, bring-back, RB in stack, salary left). Realized = sum of each player's DK points from the real
Millionaire ownership file."""
import sys, numpy as np, pandas as pd
from scipy.stats import hypergeom
from nfl_dfs.bq import query_df
C = sys.argv[1]
c = pd.read_parquet(f"{C}/candidates.parquet"); fr = pd.read_parquet(f"{C}/frame.parquet")
own = query_df("""SELECT display_name, MAX(fpts) f FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
                  WHERE season=2026 AND week=2 AND contest_id='195648007' GROUP BY 1""")
lut = dict(zip(own.display_name.astype(str), own.f.astype(float)))
fr["id"] = fr["id"].astype(str); F = fr.set_index("id")
names = F.display_name.astype(str).to_dict(); pos = F.pos.astype(str).to_dict(); team = F.team.astype(str).to_dict(); opp = F.opp.astype(str).to_dict()
miss = sorted({names[p] for ps in c.players for p in ps.split(",") if names[p] not in lut})
print("players with no realized points (scored 0):", miss)
def feats(ps):
    ids = ps.split(","); qb = [p for p in ids if pos[p] == "QB"][0]; t = team[qb]
    mates = [p for p in ids if p != qb and team[p] == t and pos[p] != "DST"]
    bb = [p for p in ids if team[p] == opp[qb] and pos[p] != "DST"]
    return (sum(lut.get(names[p], 0.0) for p in ids), len(mates), len(bb) > 0, any(pos[p] == "RB" for p in mates))
X = pd.DataFrame([feats(p) for p in c.players], columns=["real", "stk", "bringback", "rb_in_stack"])
c = pd.concat([c.reset_index(drop=True), X], axis=1); c["left"] = 50000 - c.salary
N = len(c); top = c.real >= c.real.quantile(0.99); K = int(top.sum())
print(f"pool {N}; top-1% cut {c.real.quantile(.99):.2f} (K={K}); pool best {c.real.max():.2f}; pool mean {c.real.mean():.2f}")
c["lev_q"] = np.where(c.tag == "lev", "lev solve-order Q" + (pd.qcut(c.cand.where(c.tag == "lev"), 5, labels=False) + 1).astype("Int64").astype(str), None)
b = c.cand.where(c.tag == "boom")
c["boom_q"] = np.where(c.tag == "boom", "boom world-order Q" + (pd.qcut(b, 5, labels=False) + 1).astype("Int64").astype(str), None)
c["stack_s"] = "QB+" + c.stk.clip(upper=3).astype(str) + np.where(c.stk >= 3, "+", "")
c["bb_s"] = np.where(c.bringback, "bring-back", "no bring-back"); c["rb_s"] = np.where(c.rb_in_stack, "RB in QB stack", "no RB in QB stack")
c["left_s"] = pd.cut(c.left, [-1, 0, 300, 1000, 50000], labels=["$0 left", "$100-300", "$400-1000", ">$1000"]).astype(str)
rows = []
for col in ("tag", "lev_q", "boom_q", "stack_s", "bb_s", "rb_s", "left_s"):
    for k, g in c[c[col].notna()].groupby(col):
        n = len(g); h = int(top[g.index].sum()); ex = K * n / N
        p = min(1.0, 2 * min(hypergeom.cdf(h, N, K, n), hypergeom.sf(h - 1, N, K, n)))
        rows.append({"batch": k, "n": n, "pool_share": f"{100*n/N:.1f}%", "mean": round(g.real.mean(), 1), "p99": round(g.real.quantile(.99), 1),
                     "best": round(g.real.max(), 1), "top1%_hits": h, "expected": round(ex, 1), "lift": round(h / ex, 2) if ex else np.nan, "p": round(p, 4)})
    rows.append({"batch": "—"})
print(pd.DataFrame(rows).fillna("").to_string(index=False))
t = c[top]; print("\ntop-1% composition: tag", t.tag.value_counts().to_dict(), "| stack", t.stack_s.value_counts().to_dict(), "| bring-back", int(t.bringback.sum()))
print("QB of the top-1%:", t.players.map(lambda s: names[[p for p in s.split(',') if pos[p]=='QB'][0]]).value_counts().head(6).to_dict())
print("QB of the pool:  ", c.players.map(lambda s: names[[p for p in s.split(',') if pos[p]=='QB'][0]]).value_counts().head(6).to_dict())
# --- contamination check: dead QBs (QB took zero offensive snaps) and any zero-snap player ---
sn = query_df("""SELECT player nn, SUM(COALESCE(offense_snaps,0)) off FROM `nfl-predictions-503414.nfl_raw.snap_counts`
                 WHERE season=2026 AND week=2 GROUP BY 1""")
import re
_SUF = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")
def _norm(s): return re.sub(r"[^a-z]", "", _SUF.sub(" ", re.sub(r"[^a-z ]", " ", str(s).lower())))
snl = {_norm(k): v for k, v in zip(sn.nn, sn.off)}
def dead_qb(ps):
    qb = [p for p in ps.split(",") if pos[p] == "QB"][0]; return snl.get(_norm(names[qb]), 0) == 0
def any_dead(ps): return any(pos[p] != "DST" and snl.get(_norm(names[p]), 0) == 0 for p in ps.split(","))
c["dead_qb"] = c.players.map(dead_qb); c["any_dead"] = c.players.map(any_dead)
print("\n=== contamination by tag ===")
print(c.groupby("tag").agg(n=("real", "size"), dead_qb=("dead_qb", "mean"), any_dead=("any_dead", "mean")).round(3).to_string())
cl = c[~c.any_dead]; topc = cl.real >= c.real.quantile(0.99)
print(f"\nCLEAN pool (no zero-snap player): {len(cl)}; top-1% hits kept {int(topc.sum())} of {K}")
for t, g in cl.groupby("tag"):
    n = len(g); h = int(topc[g.index].sum()); ex = topc.sum() * n / len(cl)
    print(f"  {t:5s} n={n:5d} share {100*n/len(cl):5.1f}%  mean {g.real.mean():6.1f}  p99 {g.real.quantile(.99):6.1f}  best {g.real.max():6.1f}  "
          f"top1% hits {h} (expected {ex:.1f}, lift {h/ex:.2f})")
print("lev QBs:", c[c.tag=="lev"].players.map(lambda s: names[[p for p in s.split(',') if pos[p]=='QB'][0]]).value_counts().head(8).to_dict())
print("lev mean salary left:", round(c[c.tag=='lev'].left.mean()), " boom:", round(c[c.tag=='boom'].left.mean()))
print("\n=== salary left, CLEAN pool (boom only, so the tag cannot confound it) ===")
cb = cl[cl.tag == "boom"]; tb = cb.real >= c.real.quantile(0.99)
for k, g in cb.groupby("left_s"):
    n = len(g); h = int(tb[g.index].sum()); ex = tb.sum() * n / len(cb)
    p = min(1.0, 2 * min(hypergeom.cdf(h, len(cb), int(tb.sum()), n), hypergeom.sf(h - 1, len(cb), int(tb.sum()), n)))
    print(f"  {k:10s} n={n:5d} mean {g.real.mean():6.1f} hits {h:3d} expected {ex:5.1f} lift {h/ex:.2f} p {p:.3f}")
for col in ("stack_s", "rb_s"):
    for k, g in cb.groupby(col):
        n = len(g); h = int(tb[g.index].sum()); ex = tb.sum() * n / len(cb); print(f"  {k:18s} n={n:5d} hits {h:3d} expected {ex:5.1f} lift {h/ex:.2f}")
