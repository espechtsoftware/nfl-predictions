"""What the armed main-book form should be expected to return in each kind of contest (descriptive; 36 historical slates,
rows' percentiles against a 200k-lineup field sampled from real ownership; real 2026 payout ladders)."""
import json, glob, numpy as np, pandas as pd
from scipy.stats import binom
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)
det = {}
for f in ("contest-details-2026-w01.json", "contest-details-2026-w02.json", "contest-details-2026-w03.json"): det.update({str(k): v for k, v in json.load(open(f)).items()})
def ladder(cid):
    d = det[cid]; n = int(d["entries"]); prize = np.zeros(n + 2)
    for t in d.get("payoutSummary") or []:
        v = sum(float(p.get("value") or 0) * float(p.get("quantity") or 1) for p in t.get("payoutDescriptions", []))
        prize[int(t["minPosition"]):min(int(t["maxPosition"]), n) + 1] = v
    return {"n": n, "fee": float(d["fee"]), "prize": prize, "name": d["name"]}
def by_name(sub, entries=None, week_file=None):
    for cid, d in det.items():
        if sub in d["name"] and (entries is None or int(d["entries"]) == entries): return cid
    raise KeyError(sub)
# contest types: (ladder id, field-strength offset in points vs the Millionaire field, measured on the 2026 fields at the relevant depth)
T = {"Millionaire $20":            (by_name("$2.75M Fantasy Football Millionaire"), 0.0),
     "Single-entry $5 (Huddle)":   (by_name("Huddle"), -1.5),
     "Single-entry $3 (Pylon)":    (by_name("Pylon"), -0.5),
     "20-max $3 (Play-Action)":    (by_name("Play-Action"), 0.0),
     "5-max $5 (Nickel)":          (by_name("Nickel"), 3.5),
     "150-max $5 (Flea Flicker)":  (by_name("Flea Flicker"), 3.0),
     "FFWC qualifier $18":         (by_name("World Championship Qualifier #42"), 6.0),
     "SuperSat 594 ($1, 25 tickets)":   (by_name("SUPERSat", 594), 2.0),
     "SuperSat 2,378 ($0.25, 25 tickets)": (by_name("SUPERSat", 2378), 1.0),
     "SuperSat 190 ($0.25, 2 tickets)": (by_name("SUPERSat", 190), 0.0),
     "$333 wildcat sat ($5, 79)":  (by_name("$333 Wildcat"), 0.0),
     "$4,444 sat ($13, 402)":      (by_name("$4,444 Fantasy Football"), 4.7),
     "$20 Milly sat ($2, 11)":     (by_name("Satellite to $20"), 6.0)}
L = {k: ladder(v[0]) for k, v in T.items()}
S = [json.load(open(f)) for f in sorted(glob.glob("pct/*.json"))]
print("slates:", len(S))
def cdf(s, x):                       # the slate's field CDF from its stored quantile grid (linear interpolation, flat tails)
    q = sorted((float(k) / 100, v) for k, v in s["field_q"].items()); qs = np.array([a for a, _ in q]); vs = np.array([b for _, b in q])
    return np.interp(x, vs, qs, left=0.0, right=1.0)
def exp_prize(p_below, lad):
    """expected prize of one entry whose score beats a share p_below of an N-entry field (the others binomial)."""
    n = lad["n"]; pr = lad["prize"]
    if n > 3000:                                                     # deterministic position
        pos = np.minimum(np.floor((1 - p_below) * n).astype(int) + 1, n); return pr[pos]
    paid = int((pr > 0).sum()); out = np.zeros(len(p_below))
    for i, p in enumerate(p_below):                                  # P(exactly j others above) for j < paid
        pm = binom.pmf(np.arange(paid), n - 1, 1 - p); out[i] = float((pm * pr[1:paid + 1]).sum())
    return out
rows = []
for book in ("K36", "K144"):
    for name, (cid, off) in T.items():
        lad = L[name]; ev, paid, ev0 = [], [], []
        for s in S:
            sc = np.array(s[book]["score"]); 
            p = cdf(s, sc - off); p0 = cdf(s, sc)
            e = exp_prize(p, lad); ev.append(e); ev0.append(exp_prize(p0, lad))
            thresh = (lad["prize"] > 0).sum() / lad["n"]
            paid.append(binom.cdf((lad["prize"] > 0).sum() - 1, lad["n"] - 1, 1 - p) if lad["n"] <= 3000 else (1 - p <= thresh).astype(float))
        ev, ev0, paid = np.array(ev), np.array(ev0), np.array(paid)            # slates x rows
        base = (lad["prize"] > 0).sum() / lad["n"]
        rows.append({"book": book, "contest": name, "fee": lad["fee"], "field": lad["n"], "paid share of field": base, "our entries paid": paid.mean(), "x field": paid.mean() / base,
                     "ROI per entry": ev.mean() / lad["fee"] - 1, "ROI if the field were the Millionaire's": ev0.mean() / lad["fee"] - 1, "field-average ROI (= -rake)": lad["prize"][1:lad["n"] + 1].sum() / (lad["fee"] * lad["n"]) - 1,
                     "weeks with no paid entry among the top 5 rows": float(np.prod(1 - paid[:, :5], axis=1).mean()), "strength offset": off})
R = pd.DataFrame(rows); R.to_csv("expect_by_contest.csv", index=False)
for book in ("K36", "K144"):
    print(f"\n=== {book}: the capped optimizer book, every row entered once in the contest, averaged over slates and rows")
    print(R[R.book == book].drop(columns=["book"]).round(3).to_string(index=False))
