import pandas as pd, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
d = pd.read_parquet("field_model_input.parquet")
d["proj_pct2"] = d.proj_pct ** 2; d["own_pct2"] = d.own_pct ** 2; d["proj_x_own"] = d.proj_pct * d.own_pct
SHAPE = ["proj_pct", "proj_pct2", "stack", "bring_back", "max_game", "qb_sal", "te_sal", "rb_sal", "sal_left", "flex_te", "flex_rb", "qb_game_total"]
FULL = SHAPE + ["own_pct", "own_pct2", "proj_x_own"]
def lifts(te, s, target):
    base = te[target].mean(); te = te.assign(s=s)
    return {f"top1%": te[te.s >= te.s.quantile(.99)][target].mean() / base, "top5%": te[te.s >= te.s.quantile(.95)][target].mean() / base, "top10%": te[te.s >= te.s.quantile(.90)][target].mean() / base}
rows = []
for tw in (1, 3):
    tr, te = d[d.week != tw], d[d.week == tw]
    for label, feats in (("shape only (pre-lock safe)", SHAPE), ("shape + ownership", FULL)):
        for target in ("top1", "top100"):
            m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000)).fit(tr[feats], tr[target])
            r = lifts(te, m.predict_proba(te[feats])[:, 1], target); r.update(model=label, target=target, test_week=tw); rows.append(r)
pd.set_option("display.width", 220)
print("walk-forward lift (fit on the other two weeks); Week 2 excluded as a test week (our projection defect)")
print(pd.DataFrame(rows).pivot_table(index=["target", "model"], columns="test_week", values=["top1%", "top5%", "top10%"]).round(2).to_string())

# apply the W1+W2-fitted models to OUR Week-3 pool
f = pd.read_parquet("run/frame.parquet"); c = pd.read_parquet("run/cands_scored.parquet")
own = pd.read_parquet("own_w3.parquet"); meta = pd.read_csv("contest_meta.csv"); milly = int(meta.loc[meta.entries_dk.idxmax(), "contest_id"])
f["field_own"] = f.display_name.map(own[own.contest_id.astype(int) == milly].groupby("display_name").pct_drafted.sum()).fillna(0)
F = f.set_index("id")
feat = []
for s in c.players:
    ids = s.split(","); r = F.loc[ids]
    qb = r[r.pos == "QB"].iloc[0]; tes = r[r.pos == "TE"].sort_values("salary", ascending=False)
    games = r.game_id.value_counts()
    feat.append({"proj_sum": r.mean_projection.sum(), "own_sum": r.field_own.sum(), "stack": int(((r.team == qb.team) & r.pos.isin(["WR", "TE"])).sum()), "bring_back": int(((r.team == qb.opp) & r.pos.isin(["RB", "WR", "TE"])).sum()),
                 "max_game": int(games.max()), "qb_sal": float(qb.salary), "te_sal": float(tes.salary.iloc[0]), "rb_sal": float(r[r.pos == "RB"].salary.sum()), "sal_left": float(50000 - r.salary.sum()),
                 "flex_te": float(len(tes) >= 2), "flex_rb": float((r.pos == "RB").sum() >= 3), "qb_game_total": float(qb.game_total)})
X = pd.DataFrame(feat); w3 = d[d.week == 3]
X["proj_pct"] = np.searchsorted(np.sort(w3.proj_sum.to_numpy()), X.proj_sum) / len(w3); X["own_pct"] = np.searchsorted(np.sort(w3.own_sum.to_numpy()), X.own_sum) / len(w3)
X["proj_pct2"] = X.proj_pct ** 2; X["own_pct2"] = X.own_pct ** 2; X["proj_x_own"] = X.proj_pct * X.own_pct
tr = d[d.week != 3]; act = c.act.to_numpy()
print("\nOUR Week-3 pool (12,559 rows), scored by models fitted on the Week-1 and Week-2 fields:")
for label, feats in (("shape only (pre-lock safe)", SHAPE), ("shape + ownership (post-lock own, illustration)", FULL)):
    for target in ("top1", "top100"):
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000)).fit(tr[feats], tr[target]); s = m.predict_proba(X[feats])[:, 1]
        o = np.argsort(-s)
        print(f"  {label:<48} target {target:<6}: top-2 rows realized {act[o[:2]].round(1).tolist()} | top-10 mean {act[o[:10]].mean():.1f} max {act[o[:10]].max():.1f} | top-40 mean {act[o[:40]].mean():.1f} max {act[o[:40]].max():.1f} | >=190 in top-40: {int((act[o[:40]] >= 190).sum())}")
print(f"  reference: pool mean {act.mean():.1f}; EMAX book top-2 {act[np.array(c.index[c.book_rank <= 2])].round(1).tolist()}; pool rows >= 190: {int((act >= 190).sum())} of 12559; the simulator's P(>=210) picks scored 128/110/137 (post-mortem)")

# fair comparison at K = 40 and 144 with the overlap cap: class model (shape only, W1+W2 fields) vs projected sum
rosters = [frozenset(s.split(",")) for s in c.players]
def top_by(score, k, max_shared=7):
    chosen, taken = [], []
    for i in np.argsort(-score, kind="stable"):
        r = rosters[i]
        if any(len(r & t) > max_shared for t in taken): continue
        chosen.append(i); taken.append(r)
        if len(chosen) == k: break
    return np.array(chosen)
lines = {"169": 169.4, "174": 173.8, "177": 176.6, "190": 189.5, "193": 193.0, "206": 205.5}
m1 = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000)).fit(tr[SHAPE], tr.top1); s1 = m1.predict_proba(X[SHAPE])[:, 1]
m100 = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000)).fit(tr[SHAPE], tr.top100); s100 = m100.predict_proba(X[SHAPE])[:, 1]
print("\nK-row books from the Week-3 pool with the overlap cap (in-sample realized; the class models were fitted on Weeks 1-2):")
out = []
for K in (40, 144):
    for label, sc in (("projected sum (mean track)", c.mean_proj.to_numpy()), ("class model, target top-1%", s1), ("class model, target top-100", s100)):
        b = top_by(sc, K); r = act[b]
        row = {"K": K, "book": label, "realized": r.mean(), "best": r.max(), "distinct": len(set(p for i in b for p in rosters[i])), "max expo %": 100 * max(pd.Series([p for i in b for p in rosters[i]]).value_counts()) / K}
        for k_, L in lines.items(): row[f">={k_} %"] = 100 * (r >= L).mean()
        out.append(row)
print(pd.DataFrame(out).set_index(["K", "book"]).round(1).to_string())
