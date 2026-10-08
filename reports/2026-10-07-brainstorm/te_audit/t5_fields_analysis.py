"""Task 5b: reproduce the real-field result (within-user Mantel-Haenszel OR of a top-1%/5% finish, QB+TE vs QB+WR lineups, by the QB
opponent's pre-lock pass-defense third) and decompose it by game / QB-TE pair."""
import sys, json; sys.path.insert(0, ".")
from pathlib import Path
import numpy as np, pandas as pd
from bqh import q
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
F = pd.read_parquet("fields_w3w4.parquet")
F["n_user"] = F.groupby(["week", "u"]).entry_id.transform("size")
F = F[F.matched == 9].copy()
F["top1"] = F["rank"] <= 0.01 * F.n_entries; F["top5"] = F["rank"] <= 0.05 * F.n_entries
F["qb_te"] = (F.te_m >= 1) & (F.wr_m == 0); F["qb_wr"] = (F.wr_m >= 1) & (F.te_m == 0)
F["qb_rb_te"] = (F.rb_m >= 1) & (F.te_m >= 1) & (F.wr_m == 0); F["qb_wr_wr"] = (F.wr_m >= 2) & (F.te_m == 0) & (F.rb_m == 0)
F["uw"] = F.week.astype(str) + "|" + F.u.astype(str)
F["game"] = F.apply(lambda r: f"W{r.week} " + "-".join(sorted([r.qbt, r.qbo])), axis=1)
# defense thirds from the frames
TH_R, TH_A, EPA = {}, {}, {}
for w in (3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    fr = fr[pd.to_numeric(fr.salary, errors="coerce").notna()]
    qb = fr[fr.pos == "QB"].copy(); qb["v"] = pd.to_numeric(qb.epa_per_dropback_allowed_l6, errors="coerce"); qb = qb[qb.v.notna()]
    # (R) the reviewer's: qcut over the QB ROWS (teams with more listed QBs weigh more in the cut points)
    lab = pd.qcut(qb.v.rank(method="first"), 3, labels=["strong", "middle", "weak"]).astype(str)
    TH_R.update({(w, n): l for n, l in zip(qb.display_name, lab)})
    # (A) auditor's: one value per defense, thirds over the slate's defenses
    dv = qb.groupby("opp").v.first().sort_values()
    la = pd.qcut(dv.rank(method="first"), 3, labels=["strong", "middle", "weak"]).astype(str)
    TH_A.update({(w, d): l for d, l in zip(dv.index, la)})
    EPA.update({(w, d): v for d, v in dv.items()})
    print(f"W{w} defenses by frame value (low = strong): " + ", ".join(f"{d} {v:+.2f} [{la[d][0].upper()}]" for d, v in dv.items()))
    # disagreement of the two cut methods
    m = {d: TH_R[(w, n)] for n, d in zip(qb.display_name, qb.opp)}
    print(f"   defenses whose third differs between the QB-row cut and the per-defense cut: {[d for d in dv.index if m[d] != la[d]]}")
F["third_R"] = [TH_R.get((w, n), "") for w, n in zip(F.week, F.qb)]
F["third_A"] = [TH_A.get((w, d), "") for w, d in zip(F.week, F.qbo)]
F["opp_epa"] = [EPA.get((w, d), np.nan) for w, d in zip(F.week, F.qbo)]

def mh(X, ex, ref, out):
    X = X[ex | ref].assign(E=ex[ex | ref].astype(int), o=X[out].astype(int))
    g = X.groupby(["uw", "E"]).o.agg(["size", "sum"]).unstack(fill_value=0)
    a = g[("sum", 1)] if ("sum", 1) in g else 0; n1 = g[("size", 1)] if ("size", 1) in g else 0
    c = g[("sum", 0)] if ("sum", 0) in g else 0; n0 = g[("size", 0)] if ("size", 0) in g else 0
    b = n1 - a; d = n0 - c; n = n1 + n0
    num = (a * d / n).sum(); den = (b * c / n).sum()
    return (num / den if den > 0 else np.nan), int(X[X.E == 1].o.sum()), int((X.E == 1).sum()), int(X[X.E == 0].o.sum()), int((X.E == 0).sum())

def table(X, third_col, label):
    rows = []
    for th in ("strong", "middle", "weak"):
        T = X[X[third_col] == th]
        for name, ex, ref in (("QB+TE vs QB+WR", T.qb_te, T.qb_wr), ("QB+RB+TE vs QB+WR+WR", T.qb_rb_te, T.qb_wr_wr)):
            r = {"QB faces": th, "contrast": name}
            for k in (1, 5):
                est, ev, nexp, evr, nref = mh(T, ex, ref, f"top{k}")
                r[f"top{k} MH OR"] = round(est, 2); r[f"top{k} events exp/ref"] = f"{ev}/{nexp} vs {evr}/{nref}"
            rows.append(r)
    print(f"\n{label}"); print(pd.DataFrame(rows).to_string(index=False))

M = F[F.n_user >= 20]
table(M, "third_R", "(1) REPRODUCTION, reviewer's cut (QB rows), users with 20+ entries, W3+W4:")
table(M, "third_A", "(2) per-defense cut, users 20+, W3+W4:")
for w in (3, 4):
    table(M[M.week == w], "third_R", f"(3) week {w} alone, reviewer's cut, users 20+:")
table(F, "third_R", "(4) ALL users (crude, still stratified by user-week), reviewer's cut:")

# ---- decomposition of the strong-defense QB+TE result
S = M[(M.third_R == "strong") & (M.qb_te | M.qb_wr)].copy()
S["stack"] = np.where(S.qb_te, "QB+TE", "QB+WR")
print("\n(5) strong-pass-D lineups (users 20+): by game and stack: lineups, top-1% and top-5% counts and rates")
g = S.groupby(["game", "qbt", "stack"]).agg(lineups=("entry_id", "size"), top1=("top1", "sum"), top5=("top5", "sum")).reset_index()
g["top1 rate"] = (g.top1 / g.lineups).round(4); g["top5 rate"] = (g.top5 / g.lineups).round(4)
print(g.sort_values(["game", "qbt", "stack"]).to_string(index=False))
E = S[S.qb_te & S.top1]
print(f"\n(6) the {len(E)} top-1% QB+TE lineups vs strong pass D, by QB and TE stacked:")
print(E.groupby(["week", "qb", "te_mates"]).size().sort_values(ascending=False).rename("top1 lineups").head(15).to_string())
print("by game:"); print(E.groupby("game").size().sort_values(ascending=False).to_string())
tot = E.groupby("game").size().sort_values(ascending=False); print("cumulative share:", (tot.cumsum() / tot.sum()).round(3).to_dict())

print("\n(7) leave-one-game-out: the strong-third QB+TE vs QB+WR MH OR (top 1% / top 5%) after removing every lineup whose QB plays in game g")
T = M[M.third_R == "strong"]
rows = []
for gm in sorted(T.game.unique()):
    X = T[T.game != gm]
    o1 = mh(X, X.qb_te, X.qb_wr, "top1"); o5 = mh(X, X.qb_te, X.qb_wr, "top5")
    rows.append({"drop game": gm, "top1 OR": round(o1[0], 2), "top1 events exp": o1[1], "top5 OR": round(o5[0], 2), "top5 events exp": o5[1]})
print(pd.DataFrame(rows).to_string(index=False))
# leave two out: drop the two biggest contributors
big2 = tot.index[:2].tolist(); X = T[~T.game.isin(big2)]
print(f"drop the two largest contributors {big2}: top1 OR {mh(X, X.qb_te, X.qb_wr, 'top1')[0]:.2f}, top5 OR {mh(X, X.qb_te, X.qb_wr, 'top5')[0]:.2f}")
F.to_parquet("fields_w3w4_tagged.parquet")
