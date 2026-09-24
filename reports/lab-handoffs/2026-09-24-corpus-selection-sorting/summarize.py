import numpy as np, pandas as pd
R = pd.read_csv("sel_results.csv"); SR = pd.read_csv("sort_results.csv")
pd.set_option("display.width", 220)
print("=== SELECTION (K=80 from ~240-candidate historical pools, 107 slates) ===")
print(R.groupby("sel")[["best", "mean", "top10mean", "n194", "n200", "winner_gap", "low_mean"]].mean().round(2).to_string())
base = R[R.sel == "DEMAX"].set_index(["season", "week"])
print("\npaired vs DEMAX (mean diff, slate-level t, slates better/worse, seasons with positive mean):")
for s in R.sel.unique():
    if s == "DEMAX": continue
    x = R[R.sel == s].set_index(["season", "week"])
    for m in ("best", "mean", "top10mean", "n194"):
        d = (x[m] - base[m]).dropna()
        t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) if d.std() > 0 else 0
        seas = d.groupby(level=0).mean()
        print(f"  {s:<16} {m:<10} {d.mean():+7.2f}  t {t:+5.1f}  +{int((d>0).sum()):>3}/-{int((d<0).sum()):>3}  seasons+ {int((seas>0).sum())}/{len(seas)}")
print("\nchalk-core supply in these pools (candidates eligible, of ~240):", R[R.sel == "DEMAX"].n_eligible_chalkcore.describe()[["mean", "min", "50%", "max"]].round(0).to_dict())
print("\n=== SORTING within the DEMAX book (realized mean of the first n rows; book mean for reference) ===")
S = SR.groupby("order")[["first1", "first5", "first10", "first20", "first30", "best_in_first10", "best_in_first30", "spearman"]].mean()
bm = R[R.sel == "DEMAX"]["mean"].mean()
print(f"(book mean {bm:.2f}; random order expects first-n mean = book mean, best_in_first10 = 0.125, best_in_first30 = 0.375)")
print(S.round(3).sort_values("first10", ascending=False).to_string())
g = SR[SR.order == "greedy (DEMAX order)"].set_index(["season", "week"])
print("\npaired vs greedy order, first10 / first30 means:")
for o in SR.order.unique():
    if o.startswith("greedy"): continue
    x = SR[SR.order == o].set_index(["season", "week"])
    for m in ("first10", "first30"):
        d = x[m] - g[m]; t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))
        seas = d.groupby(level=0).mean()
        print(f"  {o:<28} {m}: {d.mean():+6.2f}  t {t:+5.1f}  seasons+ {int((seas>0).sum())}/{len(seas)}")
