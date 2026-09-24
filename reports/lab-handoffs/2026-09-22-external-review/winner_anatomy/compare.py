import numpy as np, pandas as pd
exec(open(__import__("os").path.join(__import__("os").path.dirname(__file__), "tiers.py")).read().split("tiers = [")[0])        # bins()
f = pd.read_parquet("lineups.parquet")
pool = pd.read_parquet("pool_w2.parquet"); pool["sal_left"] = 50000 - pool.salary; pool["flex_pos"] = "?"
f["sal_left"] = 50000 - f.salary
rows = []
def shares(df):
    return {k: v.value_counts(normalize=True) for k, v in bins(df).items()}
for w, cid in ((1, "193028206"), (2, "195648007")):
    g = f[f.contest_id == cid]
    S = {"field": shares(g), "top 0.1%": shares(g[g.pct <= 0.001])}
    ours = f[(f.week == w) & f.ours]
    S["our entered book"] = shares(ours)
    if w == 2:
        S["our pool (12,555)"] = shares(pool)
    for feat in S["field"]:
        for val in S["field"][feat].index:
            rows.append({"week": w, "feature": feat, "value": str(val), **{k: S[k][feat].get(val, 0) for k in S}})
r = pd.DataFrame(rows)
pd.set_option("display.width", 220)
for w in (1, 2):
    x = r[r.week == w].drop(columns="week").set_index(["feature", "value"])
    x = x[~x.index.get_level_values(0).isin(["FLEX position"])]
    print(f"\n=== Week {w} Millionaire: share of lineups (field / top 0.1% / ours)")
    print((100 * x).round(1).to_string())
