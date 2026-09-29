"""The armed main-book form with and without the ownership term, by contest type (36 slates; real ladders; measured field strength)."""
import json, glob, numpy as np, pandas as pd
from scipy.stats import binom
exec(open(__import__("os").path.join(__import__("os").path.dirname(__file__), "31_expect_by_contest.py")).read().split("rows = []")[0])
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
S1 = {(s["season"], s["week"]): s for s in (json.load(open(f)) for f in sorted(glob.glob("tilt/*.json")))}
S2 = {(s["season"], s["week"]): s for s in (json.load(open(f)) for f in sorted(glob.glob("tilt2/*.json")))}
G = {(s["season"], s["week"]): s for s in S}
def paid_prob(p_below, lad):
    n = lad["n"]; k = int((lad["prize"] > 0).sum())
    return binom.cdf(k - 1, n - 1, 1 - p_below) if n <= 3000 else ((1 - p_below) * n < k).astype(float)
arms = {"as armed": (S1, "base"), "+ our ownership model (0.10)": (S1, "lag10"), "+ blended ownership (0.20)": (S2, "blend20"), "+ realized ownership (0.10), the ceiling": (S1, "oracle10")}
out = []
for contest, (cid, off) in T.items():
    lad = L[contest]; row = {"contest": contest, "field's rate": (lad["prize"] > 0).sum() / lad["n"], "break-even rate (ticket contests)": lad["fee"] / lad["prize"][1] if (lad["prize"] > 0).sum() <= 25 else np.nan}
    for name, (src, a) in arms.items():
        pp, ev = [], []
        for k, s in src.items():
            sc = np.array(s["arms"][a]["score"]); p = cdf(G[k], sc - off); pp.append(paid_prob(p, lad)); ev.append(exp_prize(p, lad))
        row[name] = float(np.mean(pp))
        if (lad["prize"] > 0).sum() <= 25: row["ROI " + name] = float(np.mean(ev)) / lad["fee"] - 1
    out.append(row)
R = pd.DataFrame(out)
print("share of entries paid (36 rows entered once each):")
print(R[["contest", "field's rate", "break-even rate (ticket contests)"] + list(arms)].round(4).to_string(index=False))
print("\nreturn per entry, ticket contests only (tickets at face value):")
c = [x for x in R.columns if x.startswith("ROI")]
print(R[R[c[0]].notna()][["contest"] + c].round(3).to_string(index=False))
R.to_csv("expect_tilt.csv", index=False)
