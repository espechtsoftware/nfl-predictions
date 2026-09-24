import hashlib, numpy as np, pandas as pd
from scipy import stats
e = pd.read_parquet("entries.parquet", columns=["week", "contest_id", "entry_name"])
f = pd.read_parquet("lineups.parquet")
MIL = {"193028206", "195648007"}
e = e[e.contest_id.isin(MIL)].reset_index(drop=True)
# lineups.parquet rows are in the same order as entries within each contest (all matched); rebuild the alignment
f = f[f.contest_id.isin(MIL)].reset_index(drop=True)
e = e.sort_values(["week", "contest_id"], kind="stable").reset_index(drop=True)
f = f.sort_values(["week", "contest_id"], kind="stable").reset_index(drop=True)
assert len(e) == len(f)
f["uid"] = e.entry_name.astype(str).str.replace(r" \(.*\)$", "", regex=True).map(lambda s: hashlib.sha1(s.encode()).hexdigest()[:12])
f["lt5_3p"] = f.n_own_lt5 >= 3
u = f.groupby(["uid", "week"]).agg(n=("pct", "size"), pct=("pct", "mean"), own_sum=("own_sum", "mean"), lt5=("n_own_lt5", "mean"),
      lt5_3p=("lt5_3p", "mean"), stack=("stack", "mean"), bb=("bringback", "mean"), n7k=("n_7k", "mean"),
      sal_left=("salary", lambda x: (50000 - x).mean()), maxg=("max_game", "mean"), naked=("stack", lambda x: (x == 0).mean())).reset_index()
p = u.pivot(index="uid", columns="week")
both = p[(p[("n", 1)] >= 20) & (p[("n", 2)] >= 20)]
print(f"users with 20+ Millionaire entries in both weeks: {len(both)}")
r = stats.spearmanr(both[("pct", 1)], both[("pct", 2)])
print(f"persistence of mean finish percentile, W1 vs W2: Spearman {r.correlation:+.3f} (p {r.pvalue:.2g})")
q = pd.qcut(both[("pct", 1)], 5, labels=["best W1 quintile", "2", "3", "4", "worst W1 quintile"])
print("W2 mean finish percentile (lower = better) by W1 quintile:", both[("pct", 2)].groupby(q, observed=True).mean().round(3).to_dict())
# construction of persistent skill: define skill on one week, describe the other week
for dw, ow in ((1, 2), (2, 1)):
    sk = both[("pct", dw)] <= both[("pct", dw)].quantile(0.2)
    rest = ~sk
    cols = ["own_sum", "lt5", "lt5_3p", "naked", "stack", "bb", "n7k", "sal_left", "maxg", "pct"]
    print(f"\nskilled on W{dw} (top 20% by mean finish, n={sk.sum()}) vs other multi-entry users, described on W{ow}:")
    print(pd.DataFrame({"skilled": both.loc[sk, [(c, ow) for c in cols]].mean().values,
                        "others": both.loc[rest, [(c, ow) for c in cols]].mean().values}, index=cols).round(3).to_string())
fld = f.groupby("week").agg(own_sum=("own_sum", "mean"), lt5=("n_own_lt5", "mean"), lt5_3p=("lt5_3p", "mean"))
print("\nwhole field:", fld.round(3).to_dict())
ours = f[f.ours].groupby("week").agg(own_sum=("own_sum", "mean"), lt5=("n_own_lt5", "mean"), lt5_3p=("lt5_3p", "mean"), n=("pct", "size"))
print("our entries:", ours.round(3).to_dict())
