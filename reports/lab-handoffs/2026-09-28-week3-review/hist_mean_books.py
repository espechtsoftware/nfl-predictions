import pandas as pd, numpy as np
C = pd.read_parquet("cands.parquet"); S = pd.read_parquet("spf_full.parquet")
S = S.set_index(["season", "week", "id"]); mp = S.mean_projection.to_dict(); sal = S.salary.to_dict()
K = 40; rows = []
for (sn, wk), c in C.groupby(["season", "week"]):
    c = c.reset_index(drop=True); pl = [str(x).split(",") for x in c.players]
    tm = np.array([sum(mp.get((sn, wk, p), 0.0) for p in q) for q in pl])
    npunt = np.array([sum(sal.get((sn, wk, p), 9999) <= 4000 for p in q) for q in pl])
    act = c.actual_score.to_numpy(); slate_mean = act.mean()
    def book(order, cap=None):
        chosen, cnt = [], {}
        for i in order:
            if cap is not None and any(cnt.get(p, 0) + 1 > cap * K for p in pl[i]): continue
            chosen.append(i)
            for p in pl[i]: cnt[p] = cnt.get(p, 0) + 1
            if len(chosen) == K: break
        return chosen
    o_sim = np.argsort(-c.sim_mean.to_numpy(), kind="stable"); o_true = np.argsort(-tm, kind="stable")
    o_emax = np.argsort(c.selected_rank.fillna(9e9).to_numpy(), kind="stable")   # the panel's own (coverage) book order
    for name, o, cap in [("panel book", o_emax, None), ("sim_mean", o_sim, None), ("true_mean", o_true, None), ("true_mean cap50", o_true, 0.5), ("true_mean cap35", o_true, 0.35), ("true_mean cap25", o_true, 0.25)]:
        b = book(o, cap); r = act[b]
        rows.append({"season": sn, "week": wk, "book": name, "mean": r.mean(), "best": r.max(), "vs_slate": r.mean() - slate_mean, "proj_mean": tm[b].mean(),
                     "n_punt": npunt[b].mean(), "distinct": len(set(p for i in b for p in pl[i])), "top_share": max(pd.Series([p for i in b for p in pl[i]]).value_counts()) / K})
D = pd.DataFrame(rows); D.to_csv("meanbook_results.csv", index=False)
pd.set_option("display.width", 220)
print("107 historical pools, K=40 books, realized:")
print(D.groupby("book").agg(mean=("mean", "mean"), sd_across_slates=("mean", "std"), p10=("mean", lambda x: x.quantile(0.1)), best=("best", "mean"),
      proj_mean=("proj_mean", "mean"), n_punt=("n_punt", "mean"), distinct=("distinct", "mean"), max_exposure=("top_share", "mean")).round(2).to_string())
base = D[D.book == "sim_mean"].set_index(["season", "week"])["mean"]
for bk in D.book.unique():
    if bk == "sim_mean": continue
    x = D[D.book == bk].set_index(["season", "week"])["mean"]; d = x - base
    print(f"  {bk:<16} vs sim_mean book mean: {d.mean():+.2f} (t {d.mean()/(d.std(ddof=1)/np.sqrt(len(d))):+.1f}, seasons+ {int((d.groupby(level=0).mean()>0).sum())}/6)")
