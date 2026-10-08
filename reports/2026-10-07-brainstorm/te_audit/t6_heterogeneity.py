"""Task 6 support: (a) cluster-bootstrap CI for the history 'relative boom' contrast (strong vs weak pass D); (b) elite-TE subgroup;
(c) the funnel versions of the operator's idea: defenses strong vs WRs but weak vs TEs, and pass-strong/run-weak defenses (QB+RB+TE)."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from bqh import q
from hist_lib import *
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
sal = q("""SELECT a.season, a.week, a.team, MAX(IF(r.position = 'TE', s.salary, NULL)) te1_salary, MAX(IF(r.position = 'WR', s.salary, NULL)) wr1_salary
           FROM `nfl_features.player_week_actuals` a JOIN `nfl_features.player_week_role` r USING (gsis_id, season, week)
           JOIN `nfl_features.dk_salary_week` s USING (gsis_id, season, week)
           WHERE a.has_stat_line AND a.season BETWEEN 2014 AND 2025 GROUP BY 1, 2, 3""")
P0 = prep("panel.parquet"); P0 = P0[(P0.season >= 2014) & (P0.season <= 2025)].merge(sal, on=["season", "week", "team"], how="left")
P0["te1_salary"] = pd.to_numeric(P0.te1_salary); P0["te_sal_rank"] = P0.groupby(["season", "week"]).te1_salary.rank(ascending=False, method="first")
for defn in ("max", "sal"):
    P = add_outcomes(P0, defn).dropna(subset=["QB", "TE1", "WR1", "WR2", "RB1", "itt"])
    D = P[(P.n_in6 >= 3)].copy(); D["third"] = thirds(D, "epa_in6")
    # (a) bootstrap over defense-season clusters of the ratio-of-ratios [P(QB+TE>=45)/P(QB+WR>=45)]_strong / [..]_weak
    rng = np.random.default_rng(7); cl = D.ds.unique(); idx = {c: np.where(D.ds.values == c)[0] for c in cl}
    def ror(X):
        g = X.groupby("third", observed=True)[["qbte45", "qbwr45"]].mean(); r = g.qbte45 / g.qbwr45
        return r["strong"] / r["weak"]
    bs = [ror(D.iloc[np.concatenate([idx[c] for c in rng.choice(cl, len(cl))])]) for _ in range(500)]
    print(f"[{defn}] history (in6 measure, {len(D):,} team-games): [P(QB+TE1>=45)/P(QB+WR1>=45)] strong / weak = {ror(D):.2f}, "
          f"95% cluster-bootstrap CI {np.percentile(bs, 2.5):.2f}-{np.percentile(bs, 97.5):.2f}")
    # (b) elite TEs: the TE1 salary is top-8 among the week's TEs
    E = D[D.te_sal_rank <= 8]
    print(f"[{defn}] elite TE (top-8 TE salary that week), n={len(E)}:")
    print(E.groupby("third", observed=True)[["TE1", "te_share", "te_boom", "WR1", "te_beats_wr", "qbte45", "qbwr45"]].mean().round(3).assign(
        n=E.groupby("third", observed=True).size()).to_string())
    print(third_dummy_reg(E, "third", ["TE1", "te_share", "te_boom", "te_beats_wr", "qbte45", "qbwr45"]).to_string(index=False))
    # (c1) funnel: strong vs WR (DK allowed to WRs, season to date) AND weak vs TE (DK allowed to TEs)
    F = P[(P.n_al >= 3)].copy()
    F["wr_t"] = thirds(F, "wr_al"); F["te_t"] = thirds(F, "te_al")
    F["funnel"] = np.select([(F.wr_t == "strong") & (F.te_t == "weak"), (F.wr_t == "strong") & (F.te_t != "weak"), (F.wr_t != "strong") & (F.te_t == "weak")],
                            ["strong vs WR & weak vs TE", "strong vs WR, not weak vs TE", "weak vs TE, not strong vs WR"], "neither")
    W = F.copy(); outs = ["TE1", "te_share", "te_boom", "WR1", "te_beats_wr", "qbte45", "qbwr45", "itt"]
    W[outs] = within(F, outs)
    print(f"[{defn}] funnel groups (DK allowed, season to date, 3+ games), within offense-season means (raw n):")
    print(W.groupby("funnel")[outs].mean().round(3).assign(n=F.groupby("funnel").size()).to_string())
    # (c2) pass-strong (EPA in6 strong third) and run-weak (DK allowed to RBs top third): QB+RB+TE vs QB+WR+WR
    G = P[(P.n_in6 >= 3) & (P.n_al >= 3)].copy(); G["pt"] = thirds(G, "epa_in6"); G["rt"] = thirds(G, "rb_al")
    G["grp"] = np.where((G.pt == "strong") & (G.rt == "weak"), "pass-strong & run-weak", np.where(G.pt == "strong", "pass-strong, other run", "other"))
    W = G.copy(); outs = ["qbrbte60", "qbwrwr60", "rbte_beats_wrwr", "RB1", "TE1", "itt"]; W[outs] = within(G, outs)
    print(f"[{defn}] run-funnel groups, within offense-season means:")
    print(W.groupby("grp")[outs].mean().round(3).assign(n=G.groupby("grp").size(), raw_qbrbte60=G.groupby("grp").qbrbte60.mean().round(3),
                                                        raw_qbwrwr60=G.groupby("grp").qbwrwr60.mean().round(3)).to_string())
    print()
