"""Task 6 support: is there a TE effect in the recent era, or against good CORNERBACK play (the literal 'can't throw to the WRs' mechanism),
or against strong defenses overall (points allowed)? Same within-offense-season method, pre-lock salary definitions and hindsight ones."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from bqh import q
from hist_lib import *
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
cov = q("SELECT team opp, season, week, cb_ypt_allowed_l6, db_ypt_allowed_l6 FROM `nfl_features.defense_week_coverage` WHERE season BETWEEN 2014 AND 2025")
pa = q("""WITH s AS (SELECT season, week, CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC' WHEN 'STL' THEN 'LA' ELSE home_team END h,
                 CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC' WHEN 'STL' THEN 'LA' ELSE away_team END a, home_score, away_score
                 FROM `nfl_raw.schedules` WHERE game_type = 'REG' AND season BETWEEN 2014 AND 2025 AND result IS NOT NULL),
      l AS (SELECT season, week, h d, away_score pts FROM s UNION ALL SELECT season, week, a, home_score FROM s)
      SELECT season, week, d opp, AVG(pts) OVER (PARTITION BY d, season ORDER BY week ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) pts_al,
             COUNT(*) OVER (PARTITION BY d, season ORDER BY week ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) n_pa FROM l""")
P0 = prep("panel.parquet"); P0 = P0[(P0.season >= 2014) & (P0.season <= 2025)].merge(cov, on=["opp", "season", "week"], how="left").merge(pa, on=["opp", "season", "week"], how="left")
KEYS = ["TE1", "te_share", "te_boom", "te_beats_wr", "qbte45", "qbwr45", "rel_boom"]
for defn in ("sal", "max"):
    P = add_outcomes(P0, defn).dropna(subset=["QB", "TE1", "WR1", "WR2", "RB1", "itt"]); P["rel_boom"] = P.qbte45 - P.qbwr45
    print(f"==================== outcome definition '{defn}'")
    for lab, sel, meas, nmin in (("EPA in6, 2014-2017", P.season <= 2017, "epa_in6", ("n_in6", 3)),
                                 ("EPA in6, 2018-2021", P.season.between(2018, 2021), "epa_in6", ("n_in6", 3)),
                                 ("EPA in6, 2022-2025", P.season >= 2022, "epa_in6", ("n_in6", 3)),
                                 ("CB yards/target allowed l6 (production 017a), 2018-2025", P.season >= 2018, "cb_ypt_allowed_l6", ("n_in6", 3)),
                                 ("points allowed per game, season to date", P.season >= 2014, "pts_al", ("n_pa", 3))):
        D = P[sel & P[meas].notna() & (P[nmin[0]] >= nmin[1])].copy(); D["third"] = thirds(D, meas)
        g = D.groupby("third", observed=True)
        print(f"\n--- {lab}: {len(D):,} team-games; raw TE1 by third {g.TE1.mean().round(2).to_dict()}, "
              f"P(QB+TE>=45) {g.qbte45.mean().round(3).to_dict()}, P(QB+WR>=45) {g.qbwr45.mean().round(3).to_dict()}")
        print(third_dummy_reg(D, "third", KEYS).to_string(index=False))
