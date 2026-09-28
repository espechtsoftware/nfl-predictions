"""Fit a median-anchored skewed yardage law on 2023-24 (shape = exp(a + b ln line)); pick the family by tail calibration."""
import sys, numpy as np, pandas as pd
from scipy import stats, optimize
d = pd.read_parquet(sys.argv[1]); d = d[(d.line > 0) & d.p_over.between(0.02, 0.98)]
TH = (50.0, 75.0, 100.0, 125.0)

def law(fam, line, p, a, b):
    sh = np.exp(a + b * np.log(line))
    if fam == "lognormal":
        med = line * np.exp(sh * stats.norm.ppf(p))
        return med * np.exp(sh ** 2 / 2), (lambda t: stats.norm.sf((np.log(t) - np.log(med)) / sh))
    theta = line / stats.gamma.isf(p, sh)
    return sh * theta, (lambda t: stats.gamma.sf(t / theta, sh))

def normal(line, p):
    sig = 0.30 * np.maximum(line, 1); mu = line + stats.norm.ppf(p) * sig
    return mu, (lambda t: stats.norm.sf(t, mu, sig))

fits = {}
for m, gm in d.groupby("market"):
    tr, te = gm[gm.season <= 2024], gm[gm.season == 2025]
    for fam, x0 in (("lognormal", (0.0, -0.2)), ("gamma", (0.0, 0.5))):
        obj = lambda ab: np.mean((tr.actual - law(fam, tr.line.values, tr.p_over.values, *ab)[0]) ** 2)
        r = optimize.minimize(obj, x0, method="Nelder-Mead"); fits[(m, fam)] = r.x
    for split, g in (("fit 2023-24", tr), ("OOS 2025", te)):
        g = g.copy(); g["band"] = pd.qcut(g.line, 4, labels=False, duplicates="drop")
        models = {"normal(line=mean)": normal(g.line.values, g.p_over.values),
                  **{fam: law(fam, g.line.values, g.p_over.values, *fits[(m, fam)]) for fam in ("lognormal", "gamma")}}
        print(f"\n{m} {split} n {len(g)}  actual mean {g.actual.mean():.2f}")
        for name, (mean, sf) in models.items():
            gap = g.actual - mean
            cal = {t: (sf(t).mean(), (g.actual >= t).mean()) for t in TH}
            brier = np.mean([np.mean((sf(t) - (g.actual >= t)) ** 2) for t in TH])
            print(f"  {name:18s} gap {gap.mean():+.2f}  by band {gap.groupby(g.band.values).mean().round(2).tolist()}  "
                  f"P(>=t) pred/real {' '.join(f'{int(t)}:{p:.3f}/{r:.3f}' for t, (p, r) in cal.items())}  brier {brier:.4f}")
for k, v in fits.items():
    print(k, np.round(v, 4), "shape at line 10/30/60:", np.round(np.exp(v[0] + v[1] * np.log([10, 30, 60])), 3))
