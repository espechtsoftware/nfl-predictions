import numpy as np, pandas as pd
CF = pd.read_parquet("cand_features.parquet")
CF["slate"] = CF.season.astype(str) + "-" + CF.week.astype(str)
CF["real_d"] = CF.actual_score - CF.groupby("slate").actual_score.transform("mean")
CF["sim_d"] = CF.sim_mean - CF.groupby("slate").sim_mean.transform("mean")
CF["q99_d"] = CF.sim_q99 - CF.groupby("slate").sim_q99.transform("mean")
CF["top5"] = CF.groupby("slate").actual_score.rank(ascending=False) <= 5          # the pool's 5 best realized
CF["sal_left"] = 50000 - CF.salary
CF["lowb"] = pd.cut(CF.n_low, [-1, 2, 3, 4, 5, 9], labels=["0-2", "3", "4", "5", "6+"])
print(f"candidates {len(CF)}; slates {CF.slate.nunique()}; share by predicted-LOW count:", (100*CF.lowb.value_counts(normalize=True).sort_index()).round(1).to_dict())
# within-slate OLS with slate-clustered se
def ols(y, cols, df):
    X = np.column_stack([df[c].to_numpy(float) for c in cols] + [np.ones(len(df))]); Y = df[y].to_numpy(float)
    b = np.linalg.lstsq(X, Y, rcond=None)[0]; e = Y - X @ b; bread = np.linalg.inv(X.T @ X)
    meat = sum(np.outer(X[i].T @ e[i], X[i].T @ e[i]) for i in df.groupby("slate").indices.values())
    se = np.sqrt(np.diag(bread @ meat @ bread)); return dict(zip(cols, zip(b, se)))
for y in ("real_d", "top5"):
    r = ols(y, ["sim_d", "q99_d", "n_low", "n_chalk", "sal_left"], CF)
    print(f"\n{y} ~ " + "  ".join(f"{k} {v[0]:+.4f} (se {v[1]:.4f})" for k, v in r.items()))
print("\nby predicted-LOW count, within-slate realized minus slate mean, and the share of each slate's top-5 realized:")
t = CF.groupby("lowb", observed=True).agg(n=("real_d", "size"), sim=("sim_d", "mean"), real=("real_d", "mean"), top5_rate=("top5", "mean"))
t["top5_lift"] = t.top5_rate / CF.top5.mean()
print(t.round(3).to_string())
print("\nby generator tag:")
t2 = CF.groupby("tag").agg(n=("real_d", "size"), sim=("sim_d", "mean"), real=("real_d", "mean"), top5_rate=("top5", "mean"), low=("n_low", "mean"), demax_share=("in_demax", "mean"))
t2["top5_lift"] = t2.top5_rate / CF.top5.mean()
print(t2.sort_values("n", ascending=False).round(3).to_string())
