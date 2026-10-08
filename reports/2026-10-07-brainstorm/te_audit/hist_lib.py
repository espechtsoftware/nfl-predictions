"""Auditor's own analysis helpers for the TE-vs-pass-defense history test."""
import numpy as np, pandas as pd

def prep(path):
    D = pd.read_parquet(path)
    for c in D.columns:
        if c not in ("game_id", "weekday", "team", "opp", "te1_sal_id", "wr_max2", "wr_sal2"):
            D[c] = pd.to_numeric(D[c], errors="coerce")
    D["wr1_max"] = D.wr_max2.map(lambda a: a[0] if a is not None and len(a) > 0 else np.nan)
    D["wr2_max"] = D.wr_max2.map(lambda a: a[1] if a is not None and len(a) > 1 else np.nan)
    D["wr1_sal"] = D.wr_sal2.map(lambda a: a[0] if a is not None and len(a) > 0 else np.nan)
    D["wr2_sal"] = D.wr_sal2.map(lambda a: a[1] if a is not None and len(a) > 1 else np.nan)
    D["te_share"] = D.te_tgt / D.tm_tgt
    D["rb_touch_share"] = (D.rb_car + D.rb_tgt) / (D.tm_car + D.tm_tgt)
    D["os"] = D.season.astype(int).astype(str) + D.team
    D["ds"] = D.season.astype(int).astype(str) + D.opp
    D["gid"] = D.game_id
    return D

def add_outcomes(D, defn="max"):
    """defn='max': the reviewer's hindsight best-scorer definitions; 'sal': the highest-salaried player at the position who played."""
    D = D.copy()
    if defn == "max":
        D["QB"], D["TE1"], D["WR1"], D["WR2"], D["RB1"] = D.qb_max, D.te1_max, D.wr1_max, D.wr2_max, D.rb1_max
    else:
        D["QB"], D["TE1"], D["WR1"], D["WR2"], D["RB1"] = D.qb_sal, D.te1_sal, D.wr1_sal, D.wr2_sal, D.rb1_sal
    D["te_boom"] = (D.TE1 >= 20).astype(float)
    D["te_beats_wr"] = (D.TE1 > D.WR1).astype(float)
    D["qbte45"] = (D.QB + D.TE1 >= 45).astype(float)
    D["qbwr45"] = (D.QB + D.WR1 >= 45).astype(float)
    D["qbrbte60"] = (D.QB + D.RB1 + D.TE1 >= 60).astype(float)
    D["qbwrwr60"] = (D.QB + D.WR1 + D.WR2 >= 60).astype(float)
    D["rbte_beats_wrwr"] = (D.RB1 + D.TE1 > D.WR1 + D.WR2).astype(float)
    return D

def thirds(D, col, labels=("strong", "middle", "weak")):
    pct = D.groupby(["season", "week"])[col].rank(pct=True)
    return pd.cut(pct, [0, 1 / 3, 2 / 3, 1.0], labels=list(labels))

def within(D, cols, by="os"):
    X = D[cols].astype(float)
    return X - X.groupby(D[by]).transform("mean")

def ols_cluster(y, X, groups):
    """OLS with an intercept; returns coef, naive SE, cluster-robust (CR1) SE."""
    X = np.column_stack([X, np.ones(len(X))]); n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X); b = XtX_inv @ X.T @ y; e = y - X @ b
    se_naive = np.sqrt(np.diag(XtX_inv * (e @ e) / (n - k)))
    g = pd.Series(groups).astype("category").cat.codes.values; G = g.max() + 1
    S = np.zeros((G, k)); np.add.at(S, g, X * e[:, None])
    meat = S.T @ S; c = G / (G - 1) * (n - 1) / (n - k)
    se_cl = np.sqrt(np.diag(c * XtX_inv @ meat @ XtX_inv))
    return b[:-1], se_naive[:-1], se_cl[:-1]

def zsw(D, col):
    g = D.groupby(["season", "week"])[col]
    return (D[col] - g.transform("mean")) / g.transform("std")

OUT = ["TE1", "te_share", "te_boom", "WR1", "RB1", "QB", "te_beats_wr", "qbte45", "qbwr45", "qbrbte60", "qbwrwr60"]

def third_tables(D, third_col, outs=OUT):
    raw = D.groupby(third_col, observed=True)[outs + ["itt"]].mean()
    raw.insert(0, "n", D.groupby(third_col, observed=True).size())
    W = D.copy(); W[outs + ["itt"]] = within(D, outs + ["itt"])
    wit = W.groupby(third_col, observed=True)[outs + ["itt"]].mean()
    return raw, wit

def third_dummy_reg(D, third_col, outs, cluster="ds"):
    """Within offense-season LPM/OLS: y ~ strong + weak (middle omitted) + itt; cluster-robust SE by defense-season."""
    Z = D.dropna(subset=["itt"]).copy()
    Z["is_strong"] = (Z[third_col] == "strong").astype(float); Z["is_weak"] = (Z[third_col] == "weak").astype(float)
    X = within(Z, ["is_strong", "is_weak", "itt"]).values
    rows = []
    for y in outs:
        yy = within(Z, [y]).values[:, 0]
        b, sn, sc = ols_cluster(yy, X, Z[cluster].values)
        rows.append({"outcome": y, "strong-minus-middle": f"{b[0]:+.3f} (t {b[0]/sc[0]:+.1f})", "weak-minus-middle": f"{b[1]:+.3f} (t {b[1]/sc[1]:+.1f})",
                     "strong-minus-weak": f"{b[0]-b[1]:+.3f}"})
    return pd.DataFrame(rows)

def cont_reg(D, defcols, outs, cluster="ds"):
    """The reviewer's regression form: within offense-season, z-scored (in season-week) defense measures + implied total."""
    Z = D.dropna(subset=defcols + ["itt"]).copy()
    zc = []
    for c in defcols + ["itt"]:
        Z[c + "_z"] = zsw(Z, c); zc.append(c + "_z")
    X = within(Z, zc).values
    rows = []
    for y in outs:
        yy = within(Z, [y]).values[:, 0]
        b, sn, sc = ols_cluster(yy, X, Z[cluster].values)
        r = {"outcome": y}
        for i, c in enumerate(defcols + ["itt"]):
            r[f"per sd {c}"] = f"{b[i]:+.3f} (t {b[i]/sn[i]:+.1f} naive, {b[i]/sc[i]:+.1f} clustered)"
        rows.append(r)
    return pd.DataFrame(rows), len(Z)
