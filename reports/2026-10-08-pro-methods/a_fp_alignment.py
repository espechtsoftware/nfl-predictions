# PRO METHODS, analysis A (W4): who follows Fantasy Points, who doesn't, and when. PRIVATE (usernames in output).
# Each source's "edge" on a player = its projection minus the salary-implied projection (a within-position linear fit of
# that source on salary), z-scored within position: what the source says beyond the price. A user's tilt on a player =
# his share of the user's lineups minus the rest of the field's share (percentage points). Per user, a joint OLS of tilt
# on the FP, props and our-model edges (prop-covered pool) gives each source's weight; FP_SHARE = b_fp / (b_fp + b_props
# + b_model) over positive parts. Pooled groups use the same fit on the group's pooled share.
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path.home() / "private" / "pro-methods"
pan = pd.read_parquet(OUT / "panel.parquet")
for _c in pan.columns:
    if pd.api.types.is_numeric_dtype(pan[_c]) and not pd.api.types.is_bool_dtype(pan[_c]):
        pan[_c] = pan[_c].astype(float)
ux = pd.read_parquet(OUT / "user_exposure.parquet")
ur = pd.read_parquet(OUT / "user_results.parquet")
W = 4
d = pan[(pan.week == W) & pan.pos.isin(["QB", "RB", "WR", "TE"])].copy()
d = d[(d.field_own >= 0.002) | (d.fp_own >= 0.005)]


def edge(df, col):
    out = pd.Series(np.nan, index=df.index)
    for p, g in df.groupby("pos"):
        ok = g[col].notna() & g.salary.notna()
        if ok.sum() < 8:
            continue
        b = np.polyfit(g.salary[ok] / 1000.0, g[col][ok], 1)
        r = g[col] - np.polyval(b, g.salary / 1000.0)
        out[g.index] = (r - r[ok].mean()) / r[ok].std()
    return out


for s, col in (("fp", "fp"), ("props", "props"), ("model", "model_points_pre"), ("ours", "mean_projection")):
    d[f"e_{s}"] = edge(d, col)
d["own_z"] = d.groupby("pos").fp_own.transform(lambda x: (np.log(x.clip(lower=1e-3)) - np.log(x.clip(lower=1e-3)).mean()) / np.log(x.clip(lower=1e-3)).std())
pc = d[d.props.notna() & d.fp.notna() & d.model_points_pre.notna()].copy()
print(f"W4 pool: {len(d)} skill players; prop-covered with FP + model: {len(pc)}")
print("edge correlations (prop-covered):\n", pc[["e_fp", "e_props", "e_model", "own_z"]].corr().round(2))


def fit(y, X):
    y = np.asarray(y, dtype=float); X = np.asarray(X, dtype=float)
    X1 = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(X1, y, rcond=None)
    res = y - X1 @ b
    s2 = res @ res / max(1, len(y) - X1.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.pinv(X1.T @ X1)))
    r2 = 1 - (res @ res) / ((y - y.mean()) @ (y - y.mean()))
    return b[1:], se[1:], r2


SRC = ["e_fp", "e_props", "e_model"]
rows = []
users = ur[ur.week == W][["u", "n", "is_reg", "top1", "top01", "mean_pr", "best"]]
uxw = ux[ux.week == W].pivot_table(index="key", columns="u", values="share", fill_value=0.0)
for _, u in users.iterrows():
    sh = pc.key.map(uxw[u.u]).fillna(0.0) if u.u in uxw else pd.Series(0.0, index=pc.index)
    y = (sh - pc.exp_rest).values * 100
    b, se, r2 = fit(y, pc[SRC].values)
    bo, _, r2o = fit(y, pc[SRC + ["own_z"]].values)
    pos = np.clip(b, 0, None)
    rows.append({"u": u.u, "n": u.n, "is_reg": u.is_reg, "top1": u.top1, "top01": u.top01, "mean_pr": u.mean_pr,
                 "b_fp": b[0], "b_props": b[1], "b_model": b[2], "se_fp": se[0], "se_props": se[1], "r2": r2,
                 "fp_share": pos[0] / pos.sum() if pos.sum() > 0 else np.nan, "b_own": bo[3], "r2_own": r2o,
                 "corr_fp": np.corrcoef(y, pc.e_fp)[0, 1], "corr_props": np.corrcoef(y, pc.e_props)[0, 1],
                 "corr_model": np.corrcoef(y, pc.e_model)[0, 1]})
U = pd.DataFrame(rows)
U.to_parquet(OUT / "a_users_w4.parquet")

def grp(name, m):
    g = U[m]
    return {"group": name, "users": len(g), "median_fp_share": g.fp_share.median(),
            "mean_b_fp": g.b_fp.mean(), "mean_b_props": g.b_props.mean(), "mean_b_model": g.b_model.mean(),
            "share_fp_dominant": (g.b_fp > g[["b_props", "b_model"]].max(axis=1)).mean(),
            "share_props_dominant": (g.b_props > g[["b_fp", "b_model"]].max(axis=1)).mean(),
            "share_model_dominant": (g.b_model > g[["b_fp", "b_props"]].max(axis=1)).mean(),
            "share_props_sig": (g.b_props / g.se_props > 2).mean(), "share_fp_sig": (g.b_fp / g.se_fp > 2).mean(),
            "median_r2": g.r2.median(), "mean_b_own": g.b_own.mean(), "top1_rate": g.top1.sum() / g.n.sum()}

print("\n== per-user source weights, W4 (tilt in pp per 1 sd of edge; prop-covered pool) ==")
G = pd.DataFrame([grp("regulars (117)", U.is_reg), grp("W4 20-149 entries, not regulars", ~U.is_reg & (U.n < 150)),
                  grp("W4 150 entries, not regulars", ~U.is_reg & (U.n >= 150)), grp("all W4 >= 20", U.n >= 20)])
print(G.round(3).to_string(index=False))

# pooled groups: regulars, top 0.1% / 1% (outcome-selected leaders), and the field's own ownership
print("\n== pooled groups (tilt vs rest of field) ==")
for name, col in (("regulars pooled", "exp_reg"), ("top 1% lineups (leaders)", "exp_top1"), ("top 0.1% lineups (leaders)", "exp_top01")):
    y = (pc[col] - pc.exp_rest).values * 100
    b, se, r2 = fit(y, pc[SRC].values)
    print(f"  {name:28s} b_fp {b[0]:+.2f} ({se[0]:.2f})  b_props {b[1]:+.2f} ({se[1]:.2f})  b_model {b[2]:+.2f} ({se[2]:.2f})  R2 {r2:.2f}")
y = np.log(pc.field_own.clip(lower=1e-3)).values
b, se, r2 = fit(y, pc[SRC].values)
print(f"  {'field log-ownership':28s} b_fp {b[0]:+.2f} ({se[0]:.2f})  b_props {b[1]:+.2f} ({se[1]:.2f})  b_model {b[2]:+.2f} ({se[2]:.2f})  R2 {r2:.2f}")
y = np.log(pc.fp_own.clip(lower=1e-3)).values
b, se, r2 = fit(y, pc[SRC].values)
print(f"  {'FP projected log-own':28s} b_fp {b[0]:+.2f} ({se[0]:.2f})  b_props {b[1]:+.2f} ({se[1]:.2f})  b_model {b[2]:+.2f} ({se[2]:.2f})  R2 {r2:.2f}")

# results by FP reliance among regulars (W4 and W1-4): terciles of fp_share
R = U[U.is_reg].copy()
R["tercile"] = pd.qcut(R.fp_share.rank(method="first"), 3, labels=["least FP", "middle", "most FP"])
allw = ur[ur.is_reg].groupby("u").agg(n=("n", "sum"), top1=("top1", "sum"), mean_pr=("mean_pr", "mean")).reset_index()
R = R.merge(allw.rename(columns={"n": "n14", "top1": "top1_14", "mean_pr": "mean_pr14"}), on="u")
print("\n== regulars by FP-reliance tercile (W4 weights) ==")
print(R.groupby("tercile").agg(users=("u", "size"), fp_share=("fp_share", "median"), b_props=("b_props", "mean"), b_own=("b_own", "mean"),
                               w4_top1_rate=("top1", lambda s: s.sum() / R.loc[s.index, "n"].sum()),
                               w4_mean_pct=("mean_pr", "mean"), w14_top1_rate=("top1_14", lambda s: s.sum() / R.loc[s.index, "n14"].sum()),
                               w14_mean_pct=("mean_pr14", "mean")).round(4).to_string())
json.dump(G.to_dict("records"), open(OUT / "a_groups_w4.json", "w"), indent=1, default=float)
