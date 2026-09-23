import re, numpy as np, pandas as pd
exec(open(__import__("os").path.join(__import__("os").path.dirname(__file__), "hist_own.py")).read().split('L = rl.assign')[0])
pr = pd.read_csv("own_pred_hist.csv").groupby(["season", "week", "key"]).pred.max()
rl["mown"] = [pr.get((s, w, k), 0.0) for s, w, k in zip(rl.season, rl.week, rl.key)]
sk = rl.pos != "DST"
L = rl.assign(m=(rl.mown < 5) & sk, mhi=rl.mown >= 20).groupby(["season", "week", "entry_ix"]).agg(
    pts=("actual", "sum"), proj=("proj", "sum"), m=("m", "sum"), mhi=("mhi", "sum")).reset_index()
L["pts_d"] = L.pts - L.groupby(["season", "week"]).pts.transform("mean")
L["proj_d"] = L.proj - L.groupby(["season", "week"]).proj.transform("mean")
def ols(col, bins_, labels, ref):
    b = pd.cut(L[col], bins_, labels=labels)
    X = pd.get_dummies(b, dtype=float).drop(columns=ref); X["proj"] = L.proj_d
    A = np.column_stack([X.to_numpy(), np.ones(len(X))]); y = L.pts_d.to_numpy()
    beta = np.linalg.lstsq(A, y, rcond=None)[0]; e = y - A @ beta; bread = np.linalg.inv(A.T @ A)
    groups = L.groupby(["season", "week"]).indices.values()
    meat = sum(np.outer(A[i].T @ e[i], A[i].T @ e[i]) for i in groups); se = np.sqrt(np.diag(bread @ meat @ bread))
    share = (100 * b.value_counts(normalize=True)).round(1).to_dict()
    print(f"  {col}: share of book {share}")
    for k, c in enumerate(X.columns[:-1]):
        print(f"     {c} vs {ref}: {beta[k]:+.2f} (se {se[k]:.2f})")
print("Predicted (pre-lock, walk-forward) ownership, 72 slates of replay books, realized vs slate mean, projection held fixed")
ols("m", [-1, 1, 2, 9], ["0-1", "2", "3+"], "3+")
ols("mhi", [-1, 0, 1, 9], ["0", "1", "2+"], "0")
