import re, numpy as np, pandas as pd
IN = __import__("os").environ["REVIEW_INPUTS"]          # the external-review pull_inputs.py output dir
def norm(s):
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()); return re.sub(r"[^a-z]", "", s)
rl = pd.read_csv(f"{IN}/replay_books.csv"); rl["key"] = rl.player.map(norm)
own = pd.read_csv(f"{IN}/milly_own.csv"); own["key"] = own.display_name.map(norm)
own = own.groupby(["season", "week", "key"]).pct_drafted.max()
ls = pd.read_csv(f"{IN}/linestar.csv"); ls["key"] = ls.name.map(norm)
ls = ls[ls.ls_proj_own.notna()].groupby(["season", "week", "key"]).ls_proj_own.max()
rl["own"] = [own.get((s, w, k), 0.0) for s, w, k in zip(rl.season, rl.week, rl.key)]
rl["pown"] = [ls.get((s, w, k), 0.0) for s, w, k in zip(rl.season, rl.week, rl.key)]
rl = rl[rl.season.isin(own.index.get_level_values(0).unique())]
sk = rl.pos != "DST"
L = rl.assign(lt5=(rl.own < 5) & sk, plt5=(rl.pown < 5) & sk, ge20=rl.own >= 20, pge20=rl.pown >= 20) \
      .groupby(["season", "week", "entry_ix"]).agg(pts=("actual", "sum"), proj=("proj", "sum"), lt5=("lt5", "sum"),
                                                   plt5=("plt5", "sum"), ge20=("ge20", "sum"), pge20=("pge20", "sum")).reset_index()
L["pts_d"] = L.pts - L.groupby(["season", "week"]).pts.transform("mean")      # within-slate
print(f"replay books: {L.groupby(['season','week']).ngroups} slates, {len(L)} lineups")
for col, lab in (("lt5", "actual ownership"), ("plt5", "LineStar projected ownership")):
    b = pd.cut(L[col], [-1, 1, 2, 9], labels=["0-1", "2", "3+"])
    print(f"\n# players under 5% ({lab}): share of replay-book lineups and realized points vs slate mean")
    per = L.assign(b=b).groupby(["season", "week", "b"], observed=True).pts_d.mean().unstack()
    share = b.value_counts(normalize=True).sort_index()
    for k in ["0-1", "2", "3+"]:
        v = per[k].dropna()
        print(f"  {k:>4}: share {100*share.get(k,0):5.1f}%   mean within-slate diff {v.mean():+6.2f}  (slates {len(v)}, positive {int((v>0).sum())})")
    d = (per["0-1"] - per["3+"]).dropna()
    print(f"  0-1 minus 3+: {d.mean():+.2f} points per lineup, t {d.mean()/(d.std(ddof=1)/np.sqrt(len(d))):+.1f}, 0-1 better in {int((d>0).sum())}/{len(d)} slates")

print("\nControlling for the lineup's projection (within-slate OLS: realized ~ projection + bucket dummies)")
for col in ("lt5", "plt5"):
    b = pd.cut(L[col], [-1, 1, 2, 9], labels=["0-1", "2", "3+"])
    X = pd.get_dummies(b, dtype=float)[["0-1", "2"]]
    X["proj"] = L.proj - L.groupby(["season", "week"]).proj.transform("mean")
    y = L.pts_d.to_numpy(); A = np.column_stack([X.to_numpy(), np.ones(len(X))])
    beta = np.linalg.lstsq(A, y, rcond=None)[0]
    # slate-clustered se
    e = y - A @ beta; bread = np.linalg.inv(A.T @ A)
    meat = sum(np.outer(A[m].T @ e[m], A[m].T @ e[m]) for m in [((L.season == s) & (L.week == w)).to_numpy() for s, w in L[["season","week"]].drop_duplicates().to_numpy()])
    se = np.sqrt(np.diag(bread @ meat @ bread))
    print(f"  {col}: 0-1 vs 3+ {beta[0]:+.2f} (se {se[0]:.2f}), 2 vs 3+ {beta[1]:+.2f} (se {se[1]:.2f}), per projected point {beta[2]:+.2f}")
