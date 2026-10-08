# PRO METHODS, analysis F (W1-4): per-regular methodology profiles. PRIVATE (usernames).
# For each of the 117 regulars: OLS of his tilt (his share - rest share, pp) on a fixed set of pre-lock data points
# (z within week x position; prop-covered pool, >= 0.2% field-owned) with week x position fixed effects. Which
# dimensions are stable person-traits (split-half by weeks: W1+W2 vs W3+W4, correlation across users)? Styles = k-means
# on the stable dimensions; results by style (top-1% rate and mean finish percentile over W1-4: four weeks, suggestive).
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path.home() / "private" / "pro-methods"
pan = pd.read_parquet(OUT / "panel.parquet")
for c in pan.columns:
    if pd.api.types.is_numeric_dtype(pan[c]) and not pd.api.types.is_bool_dtype(pan[c]):
        pan[c] = pan[c].astype(float)
ux = pd.read_parquet(OUT / "user_exposure.parquet"); ur = pd.read_parquet(OUT / "user_results.parquet")
d = pan[pan.pos.isin(["QB", "RB", "WR", "TE"]) & (pan.field_own >= 0.002) & pan.props.notna()].copy()
d["wp"] = d.week.astype(str) + d.pos


def edge(df, col):
    out = pd.Series(np.nan, index=df.index)
    for _, g in df.groupby("wp"):
        ok = g[col].notna() & g.salary.notna()
        if ok.sum() < 6:
            continue
        b = np.polyfit(g.salary[ok] / 1000.0, g[col][ok], 1)
        r = g[col] - np.polyval(b, g.salary / 1000.0)
        out[g.index] = (r - r[ok].mean()) / r[ok].std()
    return out


d["market"] = edge(d, "props")
d["log_own"] = np.log(d.field_own.clip(lower=1e-3))
d["usage"] = d.fp_route_share_l4.fillna(d.snap_share_l4)
DIMS = {"market projection": "market", "recency (last week pts)": "dk_w1", "salary change": "sal_change",
        "route/snap volume": "usage", "volatility (pts sd)": "dk_points_std", "2026 matchup (DvP)": "dvp26",
        "crowd ownership": "log_own", "team implied total": "implied_team_total", "salary level": "salary"}
for k, col in DIMS.items():
    d[k] = d.groupby("wp")[col].transform(lambda x: ((x - x.mean()) / x.std()).fillna(0) if x.std() > 0 else x * 0)
K = list(DIMS)
d[K] = d[K].fillna(0.0)
D = pd.get_dummies(d.wp).astype(float)
regs = ur[ur.is_reg].u.unique()
uxp = ux[ux.u.isin(regs)]


def profile(rows, u):
    sh = uxp[(uxp.u == u)].set_index(["week", "key"]).share
    s = pd.Series([sh.get((w, k), 0.0) for w, k in zip(rows.week, rows.key)], index=rows.index)
    y = (s - rows.exp_rest).values * 100
    X = np.column_stack([rows[K].values, D.loc[rows.index].values])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b[:len(K)]


full, h1, h2 = {}, {}, {}
for u in regs:
    full[u] = profile(d, u)
    h1[u] = profile(d[d.week.isin([1, 2])], u)
    h2[u] = profile(d[d.week.isin([3, 4])], u)
F = pd.DataFrame(full, index=K).T
A = pd.DataFrame(h1, index=K).T; B = pd.DataFrame(h2, index=K).T
rel = {k: np.corrcoef(A[k], B[k])[0, 1] for k in K}
print("stability of each methodology dimension across users (W1+W2 vs W3+W4 profiles, r):")
for k in K:
    print(f"   {k:26s} r {rel[k]:+.2f}   pooled mean {F[k].mean():+.2f} pp/sd   share of regulars > 0: {(F[k] > 0).mean():.0%}")
stable = [k for k in K if rel[k] >= 0.3]
print("stable dimensions (r >= 0.3):", stable)

res = ur[ur.is_reg].groupby("u").agg(n=("n", "sum"), top1=("top1", "sum"), top01=("top01", "sum"), mean_pr=("mean_pr", "mean")).reindex(F.index)
Z = (F[stable] - F[stable].mean()) / F[stable].std()
from sklearn.cluster import KMeans   # noqa: E402
best = None
for k in (3, 4):
    km = KMeans(n_clusters=k, n_init=50, random_state=0).fit(Z.values)
    print(f"\nk={k}: inertia {km.inertia_:.1f}")
    lab = pd.Series(km.labels_, index=Z.index)
    tab = F.groupby(lab).mean()[stable].round(2)
    tab["regulars"] = lab.value_counts().sort_index()
    tab["top1 rate W1-4"] = (res.groupby(lab).top1.sum() / res.groupby(lab).n.sum()).round(4)
    tab["mean finish pct (lower better)"] = res.groupby(lab).mean_pr.mean().round(3)
    print(tab.to_string())
    if k == 4:
        best = lab
# correlation of each dimension with results across the 117 (four weeks: suggestive)
print("\nacross the 117: Spearman of each profile dimension with results (W1-4)")
for k in K:
    print(f"   {k:26s} with top-1% rate {pd.Series(F[k]).corr(res.top1 / res.n, method='spearman'):+.2f}   "
          f"with mean finish pct {pd.Series(F[k]).corr(res.mean_pr, method='spearman'):+.2f}")
F.assign(style=best).join(res).to_parquet(OUT / "f_profiles.parquet")
