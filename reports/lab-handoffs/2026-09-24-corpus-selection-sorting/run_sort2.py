"""Sorting and slice layout on the DEMAX books of 107 historical pools: prefix means, prefix maxima, disjoint slices."""
import glob, re, numpy as np, pandas as pd
exec(open(__import__("os").path.join(__import__("os").path.dirname(__file__), "run_sel.py")).read().split("rows, sort_rows, cand_rows = [], [], []")[0])     # loaders + demax()
CF = pd.read_parquet("cand_features.parquet")
out = []
for (S, Wk), fn in sorted(files.items()):
    z = np.load(fn); T = z["totals"].astype(np.float32)
    c = CF[(CF.season == S) & (CF.week == Wk)].reset_index(drop=True)
    b = np.array(demax(T, K)); r = c.actual_score.to_numpy(float)[b]
    sm = c.sim_mean.to_numpy()[b]; low = c.n_low.to_numpy()[b]
    Tb = T[b]
    orders = {"greedy": np.arange(K),
              "sim mean": np.argsort(-sm, kind="stable"),
              "fewest LOW, then greedy": np.lexsort((np.arange(K), low)),
              "fewest LOW, then sim mean": np.lexsort((-sm, low))}
    for name, o in orders.items():
        rr = r[o]; To = Tb[o]
        row = {"season": S, "week": Wk, "order": name}
        for n in (1, 5, 10, 20, 40):
            row[f"real_max{n}"] = rr[:n].max(); row[f"real_mean{n}"] = rr[:n].mean()
            row[f"sim_emax{n}"] = To[:n].max(axis=0).mean()        # simulated E[max] of the prefix (in-sample worlds)
        for a, z_ in ((0, 20), (20, 40), (40, 60), (60, 80)):
            row[f"slice{a+1}-{z_}_mean"] = rr[a:z_].mean(); row[f"slice{a+1}-{z_}_max"] = rr[a:z_].max()
        out.append(row)
D = pd.DataFrame(out)
pd.set_option("display.width", 250)
print("realized prefix MAX and simulated prefix E[max] (mean over 107 slates):")
print(D.groupby("order")[[f"real_max{n}" for n in (1, 5, 10, 20, 40)] + [f"sim_emax{n}" for n in (5, 10, 20)]].mean().round(2).to_string())
print("\ndisjoint 20-row slices (what the sequential layout hands successive contests): realized mean / max")
print(D.groupby("order")[[c for c in D.columns if c.startswith("slice")]].mean().round(2).to_string())
g = D[D.order == "greedy"].set_index(["season", "week"])
for o in ("fewest LOW, then greedy", "fewest LOW, then sim mean", "sim mean"):
    x = D[D.order == o].set_index(["season", "week"])
    for m in ("real_max5", "real_max10", "real_max20"):
        d = x[m] - g[m]; t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))
        print(f"  {o:<26} {m}: {d.mean():+5.2f} (t {t:+4.1f}, seasons+ {int((d.groupby(level=0).mean()>0).sum())}/6)")
D.to_csv("sort2_results.csv", index=False)
