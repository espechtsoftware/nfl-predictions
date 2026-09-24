import re, numpy as np, pandas as pd
exec(open(__import__("os").path.join(__import__("os").path.dirname(__file__), "reach_registry.py")).read().split("rows = []")[0])
out = []
for (s, k), g in w.groupby(["season", "week"]):
    p = P[(P.season == s) & (P.week == k)]
    if p.empty or p.own_pred.isna().all(): continue
    sk = p[p.pos != "DST"].copy(); n_hi = int(round(0.101 * len(sk)))
    sk["rk"] = sk.own_pred.rank(ascending=False, method="first"); sk["prk"] = sk.mean_projection.rank(ascending=False)
    sk["key"] = sk["last"] + "|" + sk.team.astype(str)
    m = sk.set_index("key")
    for r in g[g.pos != "DST"].itertuples():
        kk = f"{r.last}|{r.team}"
        if kk in m.index:
            row = m.loc[kk] if not isinstance(m.loc[kk], pd.DataFrame) else m.loc[kk].iloc[0]
            out.append({"season": s, "own_act": r.own, "pred": row.own_pred, "pred_low": row.rk > n_hi, "proj": row.mean_projection,
                        "own_act_spf": row.own_act, "n_hi": n_hi, "n_sk": len(sk)})
O = pd.DataFrame(out)
print(f"winner skill players matched: {len(O)}")
print("share labelled LOW (prod rule) by actual ownership band:")
O["band"] = pd.cut(O.own_act, [-1, 5, 10, 20, 100], labels=["<5", "5-10", "10-20", "20+"])
print(O.groupby("band", observed=True).agg(n=("pred_low", "size"), labelled_low=("pred_low", "mean"), mean_pred=("pred", "mean"), mean_act=("own_act", "mean")).round(3).to_string())
print("by season:", O.groupby("season").pred_low.mean().round(2).to_dict(), "| non-LOW slots per slate:", O.groupby("season").n_hi.mean().round(0).to_dict(), "skill players:", O.groupby("season").n_sk.mean().round(0).to_dict())
print("registry own vs panel's actual ownership for the same player (sanity):", np.corrcoef(O.dropna(subset=['own_act_spf']).own_act, O.dropna(subset=['own_act_spf']).own_act_spf)[0,1].round(3))
