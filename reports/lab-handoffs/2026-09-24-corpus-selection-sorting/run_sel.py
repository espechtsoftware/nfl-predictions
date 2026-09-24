"""Selection and sorting experiments on 107 historical replay pools (exploratory; already-examined slates)."""
import glob, re, json, numpy as np, pandas as pd
from scipy import stats
K = 80
P = pd.read_parquet("players_bed.parquet")
C = pd.read_parquet("cands.parquet")
REG = __import__("os").environ["WIN"] + "/registry_features.csv"   # winner_anatomy/registry3.py output
win = pd.read_csv(REG).set_index(["season", "week"]).pts
files = {tuple(int(x) for x in re.match(r".*/(\d{4})_w(\d+)_", f).groups()): f for f in glob.glob("npz/*.npz")}

def demax(T, k, pen=None, allowed=None):
    n, W = T.shape
    X = T if pen is None else T - pen[:, None]
    m = np.full(W, -1e9, dtype=np.float32); chosen = []
    avail = np.ones(n, bool) if allowed is None else allowed.copy()
    for _ in range(k):
        if not avail.any():
            avail = np.ones(n, bool); avail[chosen] = False     # fill from the rest
        idx = np.flatnonzero(avail)
        gain = np.maximum(X[idx], m).mean(axis=1)
        j = idx[int(np.argmax(gain))]
        chosen.append(j); avail[j] = False; m = np.maximum(m, X[j])
    return chosen

rows, sort_rows, cand_rows = [], [], []
for (S, Wk), fn in sorted(files.items()):
    z = np.load(fn); ix = z["cand_ix"]; T = z["totals"].astype(np.float32)
    c = C[(C.season == S) & (C.week == Wk)].set_index("cand_ix").loc[ix].reset_index()
    p = P[(P.season == S) & (P.week == Wk)].set_index("id")
    sk = p.pos != "DST"
    # LOW / CHALK by predicted ownership rank (mirrors the sleeve's rank sets): CHALK = top 15 predicted; LOW = skill
    # players outside the top 10.1% of the slate's skill players by predicted ownership
    rk = p.own_pred.rank(ascending=False, method="first")
    chalk = set(p.index[(rk <= 15)])
    n_hi = int(round(0.101 * int(sk.sum())))          # production's live rule: the top 10.1% of skill players are not LOW
    low_pred = set(p.index[sk & (p[sk].own_pred.rank(ascending=False, method="first").reindex(p.index) > max(n_hi, 1)).fillna(False)])
    low_act = set(p.index[sk & (p.own_act < 5)]) if p.own_act.notna().any() else None
    players = [str(x).split(",") for x in c.players]
    c["n_low"] = [sum(q in low_pred for q in pl) for pl in players]
    c["n_chalk"] = [sum(q in chalk for q in pl) for pl in players]
    c["n_low_act"] = [sum(q in low_act for q in pl) for pl in players] if low_act is not None else np.nan
    c["own_sum_pred"] = [p.own_pred.reindex(pl).fillna(0).sum() for pl in players]
    c["proj_sum"] = [p.mean_projection.reindex(pl).fillna(0).sum() for pl in players]
    real = c.actual_score.to_numpy(float)
    # selectors
    books = {"PANEL": list(np.flatnonzero(c.selected.to_numpy()))[:K],
             "DEMAX": demax(T, K),
             "MEAN": list(np.argsort(-c.sim_mean.to_numpy())[:K]),
             "DEMAX_LOWPEN3": demax(T, K, pen=3.0 * c.n_low.to_numpy(np.float32)),
             "DEMAX_LOW<=2": demax(T, K, allowed=(c.n_low <= 2).to_numpy()),
             "DEMAX_CHALKCORE": demax(T, K, allowed=((c.n_low <= 2) & (c.n_chalk >= 1) & (c.salary >= 49500)).to_numpy())}
    # the panel's own selected order, for sorting
    sel_order = c[c.selected].sort_values("selected_rank").index.to_numpy()
    for name, b in books.items():
        r = real[b]
        rows.append({"season": S, "week": Wk, "sel": name, "best": r.max(), "mean": r.mean(), "n194": int((r >= 194).sum()),
                     "n200": int((r >= 200).sum()), "top10mean": np.sort(r)[-10:].mean(),
                     "winner_gap": r.max() - win.get((S, Wk), np.nan), "low_mean": c.n_low.to_numpy()[b].mean(),
                     "n_eligible_chalkcore": int(((c.n_low <= 2) & (c.n_chalk >= 1) & (c.salary >= 49500)).sum())})
    # sorting within the DEMAX book
    b = np.array(books["DEMAX"]); r = real[b]
    orders = {"greedy (DEMAX order)": np.arange(K),
              "sim mean": np.argsort(-c.sim_mean.to_numpy()[b], kind="stable"),
              "projection sum": np.argsort(-c.proj_sum.to_numpy()[b], kind="stable"),
              "sim q99": np.argsort(-c.sim_q99.to_numpy()[b], kind="stable"),
              "P(>=194)": np.argsort(-c.p_line.to_numpy()[b], kind="stable"),
              "fewest LOW, then greedy": np.lexsort((np.arange(K), c.n_low.to_numpy()[b])),
              "fewest LOW, then sim mean": np.lexsort((-c.sim_mean.to_numpy()[b], c.n_low.to_numpy()[b])),
              "predicted ownership sum": np.argsort(-c.own_sum_pred.to_numpy()[b], kind="stable"),
              "salary used": np.argsort(-c.salary.to_numpy()[b], kind="stable")}
    for name, o in orders.items():
        rr = r[o]
        sort_rows.append({"season": S, "week": Wk, "order": name, **{f"first{n}": rr[:n].mean() for n in (1, 5, 10, 20, 30)},
                          "best_in_first10": float(rr[:10].max() == r.max()), "best_in_first30": float(rr[:30].max() == r.max()),
                          "spearman": stats.spearmanr(np.arange(K), rr).correlation * -1})
    c2 = c[["season", "week", "cand_ix", "tag", "selected", "sim_mean", "sim_q99", "p_line", "salary", "n_low", "n_chalk", "n_low_act", "own_sum_pred", "proj_sum", "actual_score"]].copy()
    c2["in_demax"] = np.isin(np.arange(len(c)), b)
    cand_rows.append(c2)
R = pd.DataFrame(rows); SR = pd.DataFrame(sort_rows); CC = pd.concat(cand_rows)
R.to_csv("sel_results.csv", index=False); SR.to_csv("sort_results.csv", index=False); CC.to_parquet("cand_features.parquet")
print("slates", R.groupby(["season", "week"]).ngroups)
