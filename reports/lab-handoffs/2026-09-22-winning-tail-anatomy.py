"""Winning-tail anatomy, any 2026 week: which players did the Millionaire's top lineups use that our pool
lacked or under-held, and were those supply misses (never generated) or projection misses (served low)?
Declared before running: winners = Millionaire lineups with points >= WIN (W2: 200, the top ~0.1%). For each
winner-player: share of winning lineups, share of the field, share of our 12,555-candidate pool, served
projection (frame proj), realized DK points, rank of his served projection within position. Also, per
winning lineup: the max number of its 9 players contained in any single pool candidate."""
import sys, numpy as np, pandas as pd
from nfl_dfs.bq import query_df
C, WK, WIN = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])   # run dir, week, winner threshold (W2: 200)
c = pd.read_parquet(f"{C}/candidates.parquet"); fr = pd.read_parquet(f"{C}/frame.parquet"); fr["id"] = fr["id"].astype(str)
nm = dict(zip(fr.id, fr.display_name.astype(str))); P = fr.drop_duplicates("display_name").set_index("display_name")
T = "`nfl-predictions-503414.nfl_raw.contest_entries`"
MID = query_df(f"SELECT contest_id FROM {T} WHERE season=2026 AND week={WK} AND contest_name LIKE '%Millionaire%' GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1").contest_id.iloc[0]
field = query_df(f"SELECT points, players_key FROM {T} WHERE season=2026 AND week={WK} AND contest_id='{MID}'")
own = query_df(f"""SELECT display_name, MAX(pct_drafted) o, MAX(fpts) f FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
                  WHERE season=2026 AND week={WK} AND contest_id='{MID}' GROUP BY 1""").set_index("display_name")
win = field[field.points >= WIN]; print(f"winners (>={WIN}): {len(win)} of {len(field)}; max {field.points.max():.2f}")
pool_sets = [frozenset(nm[p] for p in s.split(",")) for s in c.players]
pool_exp = pd.Series([p for s in pool_sets for p in s]).value_counts() / len(pool_sets)
wp = pd.Series([p for k in win.players_key for p in k.split("|")]).value_counts() / len(win)
P["pos_rank"] = P.groupby("pos").proj.rank(ascending=False, method="min")
rows = []
for p, share in wp.items():
    rows.append({"player": p, "pos": P.pos.get(p, "?"), "win_share": round(100 * share, 1),
                 "field_own": round(float(own.o.get(p, np.nan)), 1), "pool_share": round(100 * pool_exp.get(p, 0.0), 1),
                 "salary": P.salary.get(p, np.nan), "proj": round(float(P.proj.get(p, np.nan)), 1),
                 "proj_pos_rank": P.pos_rank.get(p, np.nan), "real": round(float(own.f.get(p, np.nan)), 1)})
t = pd.DataFrame(rows)
t["lift_vs_pool"] = (t.win_share / t.pool_share.replace(0, np.nan)).round(1)
print("\nPlayers in >= 10% of winning lineups:")
print(t[t.win_share >= 10].to_string(index=False))
key = t[t.win_share >= 10]
print(f"\nof {len(key)} key winner-players: in pool at all {int((key.pool_share > 0).sum())}; "
      f"pool share < 1/4 of win share {int((key.pool_share < key.win_share / 4).sum())}")
# coverage: best overlap of each winning lineup with any pool candidate
idx = {p: i for i, p in enumerate(sorted({p for s in pool_sets for p in s} | {p for k in win.players_key for p in k.split('|')}))}
Pm = np.zeros((len(pool_sets), len(idx)), dtype=np.int8)
for r, s in enumerate(pool_sets): Pm[r, [idx[p] for p in s]] = 1
best = [int(Pm[:, [idx[p] for p in k.split("|")]].sum(1).max()) for k in win.players_key]
print("\nmax players shared with any pool candidate, per winning lineup:", pd.Series(best).value_counts().sort_index().to_dict())
fb = field.sample(3000, random_state=1)
bf = [int(Pm[:, [idx.get(p, 0) for p in k.split("|") if p in idx]].sum(1).max()) if all(p in idx for p in k.split("|")) else -1 for k in fb.players_key]
print("same, random field lineups (baseline):", pd.Series(bf).value_counts().sort_index().to_dict())
# --- whole-slate, non-hindsight: is the pool's divergence from the field a good or bad bet? ---
from scipy.stats import spearmanr
allp = pd.DataFrame({"pool": pool_exp}).join(own, how="outer").fillna({"pool": 0.0})
allp = allp[(allp.pool >= 0.005) | (allp.o >= 0.5)].dropna(subset=["f"])
allp["pos"] = [P.pos.get(p, "?") for p in allp.index]
allp["tilt"] = np.log((100 * allp.pool + 0.5) / (allp.o + 0.5))   # >0: pool holds him more than the field
rng = np.random.default_rng(3)
print("\n=== whole slate: Spearman(pool tilt vs field, realized points), by position; permutation p ===")
for pz, g in [("ALL", allp)] + list(allp.groupby("pos")):
    if len(g) < 8: continue
    r = spearmanr(g.tilt, g.f).correlation
    nul = np.array([spearmanr(g.tilt, rng.permutation(g.f.values)).correlation for _ in range(3000)])
    print(f"  {pz:4s} n={len(g):3d} rho {r:+.3f} p {float((np.abs(nul) >= abs(r)).mean()):.3f}")
qb = allp[allp.pos == "QB"].sort_values("pool", ascending=False)
qb["proj"] = [P.proj.get(p, np.nan) for p in qb.index]
print("\nQBs: pool share vs field ownership (top 14 by pool share)")
print(qb.head(14)[["pool", "o", "proj", "f"]].assign(pool=lambda x: (100 * x.pool).round(1)).rename(columns={"pool": "pool%", "o": "field%", "f": "real"}).to_string())
