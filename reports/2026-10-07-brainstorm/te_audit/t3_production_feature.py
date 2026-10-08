"""Task 3: the production feature epa_per_dropback_allowed_l6, recomputed for 2014-2025 in its two production forms
  in6   = training-table definition (sql/features/017): previous 6 games WITHIN the season, strictly before the game (= the reviewer's EPA measure)
  stale = live/frame definition (sql/features/023 as-of join): the in6 value of the defense's latest PLAYED row, i.e. it skips the most recent
          game (W3 frame = week-1 game only, W4 frame = weeks 1-2); verified 50/50 against the W3/W4 T-70 frames (t3_frame_check.txt)
plus a cross-season variant x6 (previous 6 games regardless of season) that also covers weeks 1-3.
Team codes normalized. Outcomes in two definitions: 'max' (reviewer: best scorer at the position) and 'sal' (pre-lock: highest DK salary
at the position among players who played). Thirds within season-week; low EPA allowed = strong pass defense."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from hist_lib import *
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
P0 = prep("panel.parquet"); P0 = P0[(P0.season >= 2014) & (P0.season <= 2025)].copy()
KEY = ["TE1", "te_share", "te_boom", "WR1", "te_beats_wr", "qbte45", "qbwr45", "qbrbte60", "qbwrwr60"]

print("=== (0) how well does each pre-game measure predict the defense's EPA per dropback allowed IN the game? (corr; 2014-2025)")
rows = []
for wk, lab in ((range(3, 4), "week 3"), (range(4, 5), "week 4"), (range(5, 19), "weeks 5+"), (range(4, 19), "weeks 4+"), (range(1, 4), "weeks 1-3")):
    S = P0[P0.week.isin(list(wk))]
    r = {"weeks": lab, "n": len(S)}
    for c in ("epa_stale", "epa_in6", "epa_x6"):
        ok = S[c].notna() & S.opp_epa_this_game.notna()
        r[c] = f"{S.loc[ok, c].corr(S.loc[ok, 'opp_epa_this_game']):.3f} (n {ok.sum()})"
    rows.append(r)
print(pd.DataFrame(rows).to_string(index=False))
print("   (stale in week 3 = ONE prior game, week 4 = two; this is what the 2026 W3/W4 frames carried)")
print("   agreement of thirds (weeks 4+): share of team-games where stale-third == in6-third:",
      round(float((thirds(P0[P0.week >= 4].dropna(subset=['epa_stale']), 'epa_stale') == thirds(P0[P0.week >= 4].dropna(subset=['epa_stale']), 'epa_in6')).mean()), 3))

for defn in ("max", "sal"):
    P = add_outcomes(P0, defn)
    P["rel_boom"] = P.qbte45 - P.qbwr45
    P["te_minus_wr"] = P.TE1 - P.WR1
    need = ["QB", "TE1", "WR1", "WR2", "RB1"]
    P = P.dropna(subset=need + ["itt"])
    for meas, wsel, nmin, lab in (("epa_in6", P.week >= 1, 3, "in6 (training def), 3+ prior games in season"),
                                  ("epa_stale", P.week >= 3, 1, "stale (live/frame def), 1+ games"),
                                  ("epa_stale", P.week.isin([3, 4]), 1, "stale, weeks 3-4 only (the 2026 test's weeks: 1-2 game samples)"),
                                  ("epa_x6", P.week >= 1, 3, "x6 cross-season, all weeks"),
                                  ("epa_x6", P.week <= 3, 3, "x6 cross-season, weeks 1-3 only (prior-season data)")):
        ncol = {"epa_in6": "n_in6", "epa_stale": "n_stale", "epa_x6": "n_x6"}[meas]
        D = P[wsel & (P[ncol] >= nmin) & P[meas].notna()].copy()
        D["third"] = thirds(D, meas)
        print(f"\n################ outcomes='{defn}' | measure {lab} | team-games {len(D):,}")
        raw, wit = third_tables(D, "third", KEY + ["te_minus_wr", "rel_boom"])
        print("raw:"); print(raw.round(3).to_string())
        print("within offense-season:"); print(wit.round(3).to_string())
        print("within offense-season regression, thirds as dummies + implied total, SE clustered by defense-season:")
        print(third_dummy_reg(D, "third", ["TE1", "te_share", "te_boom", "te_beats_wr", "te_minus_wr", "qbte45", "qbwr45", "rel_boom", "qbrbte60", "qbwrwr60"]).to_string(index=False))
        g = D.groupby("third", observed=True)
        rr = pd.DataFrame({"P(QB+TE1>=45)": g.qbte45.mean(), "P(QB+WR1>=45)": g.qbwr45.mean()})
        rr["ratio TE/WR"] = rr.iloc[:, 0] / rr.iloc[:, 1]
        rr["odds ratio TE vs WR"] = (rr.iloc[:, 0] / (1 - rr.iloc[:, 0])) / (rr.iloc[:, 1] / (1 - rr.iloc[:, 1]))
        rr["P(QB+RB+TE>=60)"] = g.qbrbte60.mean(); rr["P(QB+WR+WR>=60)"] = g.qbwrwr60.mean()
        rr["odds ratio RBTE vs WRWR"] = (rr.iloc[:, 4] / (1 - rr.iloc[:, 4])) / (rr.iloc[:, 5] / (1 - rr.iloc[:, 5]))
        print("stack boom odds ratios by third (the history analogue of the real-field odds ratio):"); print(rr.round(3).to_string())
