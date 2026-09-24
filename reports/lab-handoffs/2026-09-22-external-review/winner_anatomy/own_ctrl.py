import numpy as np, pandas as pd
f = pd.read_parquet("lineups.parquet")
pool = pd.read_parquet("pool_w2.parquet")
for w, cid in ((1, "193028206"), (2, "195648007"), (1, "193028208"), (2, "195661344")):
    g = f[f.contest_id == cid].copy()
    g["pdec"] = pd.qcut(g.proj.rank(method="first"), 5, labels=False)
    g["lt5"] = pd.cut(g.n_own_lt5, [-1, 0, 1, 2, 9], labels=["0", "1", "2", "3+"])
    base = g.groupby("pdec").apply(lambda x: (x.pct <= 0.01).mean(), include_groups=False)
    t = g.groupby(["pdec", "lt5"], observed=True).apply(lambda x: (x.pct <= 0.01).mean(), include_groups=False).unstack()
    lift = t.div(base, axis=0)
    print(f"\nweek {w} contest {cid}: top-1% rate lift by # players <5% owned, WITHIN projection-sum quintile (0=lowest)")
    print(lift.round(2).to_string())
    print("  top-1% rate by projection quintile:", (100 * base).round(2).to_dict())
print("\nOur W2 pool: realized by # players <5% owned")
pool["lt5"] = pd.cut(pool.n_own_lt5, [-1, 0, 1, 2, 3, 4, 9], labels=["0", "1", "2", "3", "4", "5+"])
print(pool.groupby("lt5", observed=True).agg(n=("pts_check", "size"), proj=("proj", "mean"), realized=("pts_check", "mean"),
      p99=("pts_check", lambda x: np.quantile(x, .99)), ge160=("pts_check", lambda x: (x >= 160).mean())).round(2).to_string())
