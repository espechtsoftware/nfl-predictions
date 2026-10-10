"""The operator's game-script questions (10-09 evening), on seasons 2018-22 + 2025 (2023-24 left out: the harness's read seasons).
Pre-game lines only define the scenario: margin = 2 x the team's implied total - the game total (> 0 = expected to win)."""
import numpy as np, pandas as pd
D = pd.read_csv(__import__("sys").argv[1])
D = D.dropna(subset=["rb_dk", "margin", "gt"])
D["mb"] = pd.cut(D.margin, [-99, -7, -3, 3, 7, 99], labels=["dog 7+", "dog 3-7", "pick-em", "fav 3-7", "fav 7+"])
tq = D["gt"].quantile([1/3, 2/3]).values
D["tb"] = pd.cut(D["gt"], [0, tq[0], tq[1], 99], labels=["low total", "mid total", "high total"])
print(f"team-games {len(D)}; seasons {sorted(D.season.unique())}; total terciles {tq.round(1)}")
def summary(g):
    return pd.Series({"n": len(g), "RB1 carries": g.rb_car.mean(), "RB1 GL carries (<=5)": g.rb_gl5.fillna(0).mean(),
                      "RB1 share of team GL": (g.rb_gl5.fillna(0).sum() / max(g.team_gl5.sum(), 1)), "RB1 rush TD": g.rb_rtd.mean(),
                      "RB1 DK": g.rb_dk.mean(), "RB1 P(DK>=20)": (g.rb_dk >= 20).mean(), "RB1 P(DK>=25)": (g.rb_dk >= 25).mean(),
                      "team pass rate": (g.team_pass / (g.team_pass + g.team_rush)).mean(),
                      "QB att": g.qb_att.mean(), "QB DK": g.qb_dk.mean(), "QB P(DK>=25)": (g.qb_dk >= 25).mean(),
                      "WR1 tgt": g.wr_tgt.mean(), "WR1 DK": g.wr_dk.mean(),
                      "corr QB-RB1": g.qb_dk.corr(g.rb_dk), "corr QB-WR1": g.qb_dk.corr(g.wr_dk)})
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print("\n== by expected margin (all totals)")
print(D.groupby("mb", observed=True).apply(summary).round(3).T.to_string())
print("\n== by game total (all margins)")
print(D.groupby("tb", observed=True).apply(summary).round(3).T.to_string())
D["scen"] = np.select([(D.margin >= 3) & (D.tb == "high total"), (D.margin <= -3) & (D.tb == "high total"),
                       (D.margin >= 7), (D.margin <= -3) & (D.tb != "high total")],
                      ["fav in shootout", "dog in shootout", "big fav (7+), not high", "dog, not shootout"], "other")
print("\n== the operator's scenarios")
print(D.groupby("scen").apply(summary).round(3).T.to_string())
# the stack question directly: a QB + own RB1 pair and a QB + WR1 pair, their combined DK and its ceiling
D["qr"] = D.qb_dk + D.rb_dk; D["qw"] = D.qb_dk + D.wr_dk
print("\n== stack pairs: mean and P(pair >= 45 DK) by scenario")
print(D.groupby("scen").agg(n=("qr", "size"), qb_rb=("qr", "mean"), qb_rb_p45=("qr", lambda s: (s >= 45).mean()),
                            qb_wr=("qw", "mean"), qb_wr_p45=("qw", lambda s: (s >= 45).mean())).round(3).to_string())
print("\n== per season (fav 7+ RB1 carries / dog-in-shootout QB att): stability")
print(D.assign(f7=D.margin >= 7, ds=(D.margin <= -3) & (D.tb == "high total")).groupby("season").apply(
    lambda g: pd.Series({"fav7 RB1 car": g[g.f7].rb_car.mean(), "rest RB1 car": g[~g.f7].rb_car.mean(),
                         "fav7 RB1 GL5": g[g.f7].rb_gl5.fillna(0).mean(), "rest RB1 GL5": g[~g.f7].rb_gl5.fillna(0).mean(),
                         "dog-shootout QB att": g[g.ds].qb_att.mean(), "rest QB att": g[~g.ds].qb_att.mean()})).round(2).to_string())
