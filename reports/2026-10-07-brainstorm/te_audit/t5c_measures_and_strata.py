"""Task 5c: does the real-field result survive (i) better pre-lock defense measures than the frame's stale 1-2 game value and
(ii) comparing QB+TE with QB+WR lineups of the SAME QB (same offense-game)? Plus 2026 team-game outcomes by defense third."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from hist_lib import prep, add_outcomes
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
F = pd.read_parquet("fields_w3w4_tagged.parquet")
P = prep("panel.parquet")
P26 = P[P.season == 2026].copy()
# defense value per (week, defense) from the auditor's panel (row where opp == defense)
dv = P26.groupby(["week", "opp"])[["epa_stale", "epa_in6", "epa_x6", "n_in6", "opp_epa_this_game"]].first().reset_index()
# hindsight: the defense's 2026 W1-W4 mean per-game EPA/dropback EXCLUDING the game itself (diagnostic only; not knowable pre-lock)
g = P26[["week", "opp", "opp_epa_this_game"]].rename(columns={"opp": "d", "opp_epa_this_game": "e"})
tot = g.groupby("d").e.agg(["sum", "count"])
dv["epa_hind_loo"] = [(tot.loc[d, "sum"] - e) / (tot.loc[d, "count"] - 1) for d, e in zip(dv.opp, dv.opp_epa_this_game)]
slate = F.groupby("week").qbo.unique()
_CUT = {}
def cut(week, col):
    if (week, col) not in _CUT:
        s = dv[(dv.week == week) & dv.opp.isin(slate[week])].set_index("opp")[col].sort_values()
        _CUT[(week, col)] = dict(zip(s.index, pd.qcut(s.rank(method="first"), 3, labels=["strong", "middle", "weak"]).astype(str)))
    return _CUT[(week, col)]
print("defense thirds on the Milly slates under each measure (S = strong):")
for w in (3, 4):
    t = pd.DataFrame({c: pd.Series(cut(w, c)) for c in ("epa_stale", "epa_in6", "epa_x6", "epa_hind_loo")})
    t = t.join(dv[dv.week == w].set_index("opp")[["epa_stale", "epa_in6", "epa_x6", "epa_hind_loo", "opp_epa_this_game"]].round(2), rsuffix="_v")
    print(f"--- W{w}"); print(t.sort_values("epa_stale_v").to_string())

def mh(X, ex, ref, out, strata):
    X = X[ex | ref].assign(E=ex[ex | ref].astype(int), o=X[out].astype(int))
    gg = X.groupby([strata, "E"]).o.agg(["size", "sum"]).unstack(fill_value=0)
    a = gg[("sum", 1)]; n1 = gg[("size", 1)]; c = gg[("sum", 0)]; n0 = gg[("size", 0)]
    b = n1 - a; d = n0 - c; n = n1 + n0
    den = (b * c / n).sum()
    return ((a * d / n).sum() / den if den > 0 else np.nan), int(X[X.E == 1].o.sum()), int((X.E == 1).sum())

M = F[F.n_user >= 20].copy()
M["uq"] = M.uw + "|" + M.qb.astype(str)            # user-week x QB: same user, same QB
M["wq"] = M.week.astype(str) + "|" + M.qb.astype(str)  # same QB (offense-game), pooled over users
rows = []
for col in ("epa_stale", "epa_in6", "epa_x6", "epa_hind_loo"):
    M["th"] = ""
    for w in (3, 4):
        M.loc[M.week == w, "th"] = M.loc[M.week == w, "qbo"].map(cut(w, col)).fillna("")
    for th in ("strong", "middle", "weak"):
        T = M[M.th == th]
        r = {"measure": col, "third": th}
        for strata, lab in (("uw", "user"), ("uq", "user x QB"), ("wq", "QB only")):
            o1 = mh(T, T.qb_te, T.qb_wr, "top1", strata); o5 = mh(T, T.qb_te, T.qb_wr, "top5", strata)
            r[f"top1 OR [{lab}]"] = f"{o1[0]:.2f} ({o1[1]})"; r[f"top5 OR [{lab}]"] = f"{o5[0]:.2f} ({o5[1]})"
        rows.append(r)
print("\nQB+TE vs QB+WR, users 20+, W3+W4: MH odds ratio (exposed top-finish events) by the QB opponent's third under each measure and stratification")
print("  [user] = the reviewer's strata; [user x QB] and [QB only] compare TE and WR stacks of the SAME quarterback")
print(pd.DataFrame(rows).to_string(index=False))

# 2026 team-game outcomes (the history method applied to 2026)
print("\n2026 team-game outcomes by the opponent's third (all 2026 games, thirds within week; TE1/WR1 = best scorer, *_sal = top-salaried who played)")
D = add_outcomes(P26, "max"); Ds = add_outcomes(P26, "sal")
D["TE1_sal"] = Ds.TE1; D["WR1_sal"] = Ds.WR1; D["te_beats_wr_sal"] = Ds.te_beats_wr
for col, wk in (("epa_stale", [3, 4]), ("epa_in6", [2, 3, 4]), ("epa_x6", [1, 2, 3, 4]), ("epa_x6", [2, 3, 4])):
    X = D[D.week.isin(wk) & D[col].notna()].copy()
    X["third"] = pd.cut(X.groupby("week")[col].rank(pct=True), [0, 1 / 3, 2 / 3, 1], labels=["strong", "middle", "weak"])
    t = X.groupby("third", observed=True).agg(n=("team", "size"), TE1=("TE1", "mean"), TE1_sal=("TE1_sal", "mean"), te_share=("te_share", "mean"),
            te_boom=("te_boom", "mean"), WR1=("WR1", "mean"), WR1_sal=("WR1_sal", "mean"), te_beats_wr=("te_beats_wr", "mean"),
            te_beats_wr_sal=("te_beats_wr_sal", "mean"), qbte45=("qbte45", "mean"), qbwr45=("qbwr45", "mean"), itt=("itt", "mean"))
    print(f"--- measure {col}, weeks {wk}"); print(t.round(3).to_string())
# Milly-slate team-games in W3/W4 with the frame's (stale) third: the games themselves
print("\nW3/W4 Milly-slate offenses facing a frame-'strong' pass defense: what their TE1 and WR1 actually scored")
rows = []
for w in (3, 4):
    cs = cut(w, "epa_stale")
    X = D[(D.week == w) & D.opp.isin(slate[w])]
    for r in X.itertuples():
        rows.append({"week": w, "offense": r.team, "vs D": r.opp, "frame third": cs.get(r.opp, ""), "proper-measure third (in6)": cut(w, "epa_in6").get(r.opp, ""),
                     "QB": r.QB, "TE1 (best)": r.TE1, "WR1 (best)": r.WR1, "TE1>WR1": r.TE1 > r.WR1, "te_share": round(r.te_share, 2), "itt": r.itt})
R = pd.DataFrame(rows)
print(R[R["frame third"] == "strong"].sort_values(["week", "offense"]).to_string(index=False))
print("\nmeans by frame third over the Milly-slate offenses:")
print(R.groupby("frame third")[["TE1 (best)", "WR1 (best)", "TE1>WR1", "te_share", "QB", "itt"]].mean().round(2).to_string())
