import pandas as pd, numpy as np
f = pd.read_parquet("frame.parquet"); c = pd.read_parquet("cands_scored.parquet")
idx = {i: n for n, i in enumerate(f.id)}; rows = [[idx[p] for p in s.split(",")] for s in c.players]; rosters = [frozenset(r) for r in rows]
R = np.zeros((len(c), len(f)), dtype=np.float32)
for i, r in enumerate(rows): R[i, r] = 1
inc = np.load("incumbent_player_scores.npy").astype(np.float32); hs = np.load("corrected_hsim_player_scores.npy").astype(np.float32)
Ti, Th = R @ inc, R @ hs
act = c.act.to_numpy(); mean_proj = c.mean_proj.to_numpy(); npunt = c.npunt.to_numpy()
print("per-player mean of the incumbent bank vs mean_projection: max |diff|", round(float(np.abs(inc.mean(axis=1) - f.mean_projection.to_numpy()).max()), 3),
      "| hsim bank vs mean_projection: mean diff", round(float((hs.mean(axis=1) - f.mean_projection.to_numpy()).mean()), 3), "max |diff|", round(float(np.abs(hs.mean(axis=1) - f.mean_projection.to_numpy()).max()), 2))
lines = {"$2 sat 169": 169.4, "594ss 174": 173.8, "FFWC 177": 176.6, "wildcat 190": 189.5, "190ss 191": 190.5, "2378ss 193": 193.0, "$4444 206": 205.5}
def top_by(score, k=144, max_shared=7, cap=None):
    chosen, taken, cnt = [], [], {}
    for i in np.argsort(-score, kind="stable"):
        r = rosters[i]
        if any(len(r & t) > max_shared for t in taken): continue
        if cap is not None and any(cnt.get(p, 0) + 1 > cap * k for p in r): continue
        chosen.append(i); taken.append(r)
        for p in r: cnt[p] = cnt.get(p, 0) + 1
        if len(chosen) == k: break
    return np.array(chosen)
books = {"EMAX (entered)": np.array(c.index[c.book_rank.notna()])[np.argsort(c.book_rank.dropna().to_numpy())],
         "top projected sum (production's rule)": top_by(mean_proj), "top incumbent-bank mean": top_by(Ti.mean(axis=1)), "top hsim-bank mean": top_by(Th.mean(axis=1)),
         "top projected sum, exposure<=50%": top_by(mean_proj, cap=0.5), "top projected sum, exposure<=35%": top_by(mean_proj, cap=0.35),
         "top projected sum, punts<=1": top_by(np.where(npunt <= 1, mean_proj, -1e9)), "top projected sum, boom only": top_by(np.where(c.tag == "boom", mean_proj, -1e9)),
         "top inc P(>=190)": top_by((Ti >= 190).mean(axis=1)), "top hsim P(>=190)": top_by((Th >= 190).mean(axis=1)), "top inc P(>=175)": top_by((Ti >= 175).mean(axis=1))}
out = []
for name, b in books.items():
    r = act[b]; row = {"book": name, "realized": r.mean(), "best": r.max(), "proj": mean_proj[b].mean(), "punts": npunt[b].mean(), "distinct": len(set(p for i in b for p in rosters[i])),
                       "max expo %": 100 * max(pd.Series([p for i in b for p in rosters[i]]).value_counts()) / len(b), "lev share %": 100 * (c.tag.to_numpy()[b] == "lev").mean()}
    for k, L in lines.items(): row[k] = 100 * (r >= L).mean()
    out.append(row)
pd.set_option("display.width", 300); print(pd.DataFrame(out).set_index("book").round(1).to_string())
# the pool's own top rows by projected sum vs the pool percentile (optimizer's curse inside the pool)
c["pp"] = c.mean_proj.rank(pct=True)
print("\nrealized by pool percentile of PROJECTED SUM:"); print(c.groupby(pd.cut(c.pp, [0, .5, .8, .9, .95, .98, .99, 1.0]), observed=True).agg(n=("act", "size"), proj=("mean_proj", "mean"), realized=("act", "mean"), ge175=("act", lambda x: 100 * (x >= 175).mean()), ge190=("act", lambda x: 100 * (x >= 190).mean())).round(1).to_string())
top = c.sort_values("mean_proj", ascending=False)
print("\npool top-30 by projected sum: proj", round(top.head(30).mean_proj.mean(), 1), "(row1", round(top.mean_proj.max(), 1), ") realized", round(top.head(30).act.mean(), 1), "punts", round(top.head(30).npunt.mean(), 2))
print("pool top-144 by projected sum (no cap): proj", round(top.head(144).mean_proj.mean(), 1), "realized", round(top.head(144).act.mean(), 1))
