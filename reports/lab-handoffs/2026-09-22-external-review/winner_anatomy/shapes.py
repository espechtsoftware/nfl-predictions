import numpy as np, pandas as pd
f = pd.read_parquet("lineups.parquet"); pool = pd.read_parquet("pool_w2.parquet")
def tag(d):
    d = d.copy()
    d["house"] = (d["stack"] >= 2) & (d.bringback >= 1) & (d.salary >= 49000)
    d["chalkcore"] = (d.n_own_lt5 <= 2) & (d.n_own_ge20 >= 1)
    d["chalkcore_strict"] = (d.n_own_lt5 <= 1) & (d.n_own_ge20 >= 2)
    d["full_sal"] = d.salary >= 49500
    d["studs2"] = d.n_7k >= 2
    d["target"] = d.chalkcore & d.full_sal & d.studs2 & (d["stack"] >= 1)
    return d
rows = []
for w, cid in ((1, "193028206"), (2, "195648007"), (1, "193028208"), (2, "195661344")):
    g = tag(f[f.contest_id == cid])
    for lab, sub in (("field", g), ("top 1%", g[g.pct <= 0.01]), ("top 0.1%", g[g.pct <= 0.001]), ("top 100", g[g["rank"] <= 100]), ("our entries", g[g.ours])):
        rows.append({"contest": f"W{w} {cid[-4:]}", "group": lab, "n": len(sub), **{c: sub[c].mean() for c in ["house", "chalkcore", "chalkcore_strict", "full_sal", "studs2", "target"]}})
p = tag(pool)
rows.append({"contest": "W2 pool", "group": "our 12,555 candidates", "n": len(p), **{c: p[c].mean() for c in ["house", "chalkcore", "chalkcore_strict", "full_sal", "studs2", "target"]}})
r = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print((r.set_index(["contest", "group"]).assign(**{c: lambda x, c=c: (100 * x[c]).round(1) for c in ["house", "chalkcore", "chalkcore_strict", "full_sal", "studs2", "target"]})).to_string())
# realized in our pool by target flag
print("\nour W2 pool by 'target' shape:", p.groupby("target").agg(n=("pts_check", "size"), proj=("proj", "mean"), mean=("pts_check", "mean"), p99=("pts_check", lambda x: np.quantile(x, .99))).round(1).to_dict())
