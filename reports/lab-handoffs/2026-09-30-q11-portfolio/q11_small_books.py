"""Q11 part 2 (production, 2026-09-30): small books (users with 2-10 entries) in the three 2026 Millionaire fields.

Per user-week: the CORE = players common to every row (|intersection|), the mean pairwise overlap, the portfolio mean,
whether the best row reached the week's top-1% line, the cash share (top 20%), and the chalk level = the rows' mean
REALIZED Millionaire ownership sum (a covariate: cores may simply be chalkier). Descriptive, post-lock, hindsight.
Tiers: DUP (all rows identical), CORE5 (|core| >= 5), PART (2-4), DIVERSE (0-1). Comparisons are within entry-count
buckets and within chalk terciles, plus a linear-probability / OLS fit with week and entry-count fixed effects
(numpy; heteroskedasticity-robust HC1 errors). Also, pre-lock-computable for Week 5: in OUR pools, is the single row
better taken as the top-mean row or a chalk-core row (the near-top-mean row with the most predicted ownership)?
Prints aggregates only (no user names)."""
import itertools, json, os, sys
import numpy as np, pandas as pd
os.environ.setdefault("OMP_NUM_THREADS", "1")
Q = os.path.expanduser("~/q11-study")
MILLY = {1: "193028206", 2: "195648007", 3: "195905122"}


def ols(y, X, names):
    X = np.column_stack([np.ones(len(y)), X]); n, k = X.shape
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    XtXi = np.linalg.pinv(X.T @ X)
    V = XtXi @ (X.T * (e ** 2)) @ X @ XtXi * n / (n - k)
    se = np.sqrt(np.diag(V))
    return {nm: dict(coef=round(float(b[i + 1]), 4), se=round(float(se[i + 1]), 4)) for i, nm in enumerate(names)}


def main():
    d = pd.read_parquet(os.path.join(Q, "q11", "small_books.parquet"))
    fq = {int(r.week): dict(qs=np.array(r.qs), mean=float(r.mean)) for r in pd.read_pickle(os.path.join(Q, "q11", "field_quantiles.pkl")).itertuples()}
    o = pd.read_csv(os.path.join(Q, "q", "B", "data", "contest_ownership_2026.csv"))
    o = o[o.contest_id.astype(str).isin(MILLY.values())]
    own = {(int(w), n): p for (w, n), p in o.groupby(["week", "display_name"]).pct_drafted.sum().items()}
    d["pset"] = d.players_key.map(lambda s: frozenset(s.split("|")))
    d["own_sum"] = [sum(own.get((w, p), 0.0) for p in ps) for w, ps in zip(d.week, d.pset)]
    rows = []
    for (w, u), g in d.groupby(["week", "user"], sort=False):
        sets = list(g.pset)
        core = len(frozenset.intersection(*sets))
        pairs = [len(a & b) for a, b in itertools.combinations(sets, 2)]
        top1, cash = fq[w]["qs"][990], fq[w]["qs"][800]
        rows.append(dict(week=w, n=len(g), core=core, overlap=float(np.mean(pairs)), all_same=len(set(sets)) == 1,
                         mean_pts=float(g.points.mean()) - fq[w]["mean"], best_top1=float(g.points.max() >= top1),
                         cash=float((g.points >= cash).mean()), own=float(g.own_sum.mean())))
    U = pd.DataFrame(rows)
    U["tier"] = np.select([U.all_same, U.core >= 5, U.core >= 2], ["DUP", "CORE5", "PART"], "DIVERSE")
    U["nb"] = pd.cut(U.n, [1, 3, 5, 10], labels=["2-3", "4-5", "6-10"])
    U["chalk"] = U.groupby("week").own.transform(lambda x: pd.qcut(x, 3, labels=["low", "mid", "high"]))
    out = {}
    agg = dict(users=("n", "size"), mean_vs_field=("mean_pts", "mean"), p_best_top1=("best_top1", "mean"), cash_share=("cash", "mean"),
               own=("own", "mean"), overlap=("overlap", "mean"))
    out["tier_share_by_nb"] = U.groupby(["nb", "tier"], observed=True).size().unstack(fill_value=0).to_dict(orient="index")
    out["by_nb_tier"] = U.groupby(["nb", "tier"], observed=True).agg(**agg).round(4).reset_index().to_dict(orient="records")
    out["by_chalk_tier"] = U.groupby(["chalk", "tier"], observed=True).agg(**agg).round(4).reset_index().to_dict(orient="records")
    out["by_week_tier"] = U.groupby(["week", "tier"], observed=True).agg(**agg).round(4).reset_index().to_dict(orient="records")
    X = pd.get_dummies(U[["tier"]], drop_first=False).drop(columns="tier_DIVERSE").astype(float)
    fe = pd.get_dummies(U.week.astype(str) + "_" + U.n.astype(str), prefix="fe", drop_first=True).astype(float)
    Xm = pd.concat([X, U[["own"]] / 10.0, fe], axis=1)
    names = list(Xm.columns)
    for y in ("best_top1", "mean_pts", "cash"):
        r = ols(U[y].to_numpy(float), Xm.to_numpy(float), names)
        out[f"fit_{y}"] = {k: v for k, v in r.items() if not k.startswith("fe_")}
        r0 = ols(U[y].to_numpy(float), pd.concat([X, fe], axis=1).to_numpy(float), list(X.columns) + list(fe.columns))
        out[f"fit_{y}_no_chalk"] = {k: v for k, v in r0.items() if not k.startswith("fe_")}
    out["n_user_weeks"] = int(len(U))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
