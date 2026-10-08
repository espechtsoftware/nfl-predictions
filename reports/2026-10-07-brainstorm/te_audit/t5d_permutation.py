"""Task 5d: how unusual is the real-field pattern if the defense label carried no information? Permute the frame's pass-defense
thirds across the slate's DEFENSES within each week (the unit that carries the label), recompute the within-user MH odds ratios."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
F = pd.read_parquet("fields_w3w4_tagged.parquet")
M = F[(F.n_user >= 20) & (F.qb_te | F.qb_wr) & (F.third_R != "")].copy()
M["E"] = M.qb_te.astype(int)
# pre-aggregate: per user-week x defense x exposure: lineups and top-1% / top-5% events
A = M.groupby(["uw", "week", "qbo", "E"]).agg(n=("entry_id", "size"), t1=("top1", "sum"), t5=("top5", "sum")).reset_index()
defs = {w: sorted(A[A.week == w].qbo.unique()) for w in (3, 4)}
obs_lab = M.groupby(["week", "qbo"]).third_R.first().to_dict()
def mh_from(A, lab, third, ev):
    S = A[[lab.get((w, d)) == third for w, d in zip(A.week, A.qbo)]]
    g = S.groupby(["uw", "E"])[["n", ev]].sum().unstack(fill_value=0)
    n1, n0 = g[("n", 1)], g[("n", 0)]; a, c = g[(ev, 1)], g[(ev, 0)]; b, d = n1 - a, n0 - c; n = n1 + n0
    den = (b * c / n).sum(); return (a * d / n).sum() / den if den > 0 else np.nan
obs = {ev: {th: mh_from(A, obs_lab, th, ev) for th in ("strong", "middle", "weak")} for ev in ("t1", "t5")}
print("observed MH OR (frame thirds):", {ev: {k: round(v, 2) for k, v in d.items()} for ev, d in obs.items()})
rng = np.random.default_rng(20261007); R = []
counts = {w: pd.Series([obs_lab[(w, d)] for d in defs[w]]).value_counts().to_dict() for w in (3, 4)}
for i in range(2000):
    lab = {}
    for w in (3, 4):
        labels = np.array(sum([[k] * v for k, v in counts[w].items()], [])); rng.shuffle(labels)
        lab.update({(w, d): l for d, l in zip(defs[w], labels)})
    r = {}
    for ev in ("t1", "t5"):
        s, wk = mh_from(A, lab, "strong", ev), mh_from(A, lab, "weak", ev)
        r[ev + "_strong"] = s; r[ev + "_contrast"] = np.log(s) - np.log(wk) if s > 0 and wk > 0 else np.nan
    R.append(r)
R = pd.DataFrame(R)
for ev in ("t1", "t5"):
    o_s = obs[ev]["strong"]; o_c = np.log(obs[ev]["strong"]) - np.log(obs[ev]["weak"])
    print(f"{ev}: strong-third OR observed {o_s:.2f}; permutation median {R[ev + '_strong'].median():.2f}, 90th pct {R[ev + '_strong'].quantile(.9):.2f}, "
          f"share >= observed {np.mean(R[ev + '_strong'] >= o_s):.3f}")
    print(f"{ev}: log OR(strong) - log OR(weak) observed {o_c:.2f}; permutation 95th pct {R[ev + '_contrast'].quantile(.95):.2f}, "
          f"share >= observed {np.mean(R[ev + '_contrast'] >= o_c):.3f}")
print("note: the permutation keeps every lineup and every game outcome fixed and only reshuffles which defenses are called strong/middle/weak;"
      " with 50 defense-weeks it measures how often a random labelling of a handful of games yields a pattern this strong.")
