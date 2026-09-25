"""Integrity checks 5.2 / 5.3 of the outside-the-box plan (laptop, 2026-09-24). Read-only BigQuery.

5.3: anytime-TD rows by outcome side in nfl_raw.prop_lines.
5.2: refit the Vegas-first DST model (intercept + opponent implied total + trailing) with the last-4 vs last-16 trailing
     input (fit <= 2020, evaluate 2021 + 2025), and score the live coefficients (14.33, -0.385, 0.118) on each input.
    PYTHONPATH=src python reports/lab-handoffs/2026-09-25-dst-coef-and-td-side-check.py
"""
import numpy as np

from nfl_dfs.bq import query_df

P = "nfl-predictions-503414"
print(query_df(f"""SELECT season, outcome_name, COUNT(*) n, COUNT(DISTINCT bookmaker) books
                   FROM `{P}.nfl_raw.prop_lines` WHERE market='player_anytime_td' GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False))
d = query_df(f"""
SELECT t.season, t.dst_dk_points y, t.dst_points_l4 l4, t.dst_points_l16 l16,
  CASE WHEN s.home_team = t.team THEN (s.total_line - s.spread_line)/2 ELSE (s.total_line + s.spread_line)/2 END opp_implied
FROM `{P}.nfl_features.team_defense_week` t
JOIN `{P}.nfl_raw.schedules` s ON s.season=t.season AND s.week=t.week AND (s.home_team=t.team OR s.away_team=t.team)
WHERE s.total_line IS NOT NULL AND s.game_type='REG'""").dropna()
tr, te = d[d.season <= 2020], d[d.season.isin([2021, 2025])]
for col in ("l4", "l16"):
    b = np.linalg.lstsq(np.column_stack([np.ones(len(tr)), tr.opp_implied, tr[col]]), tr.y, rcond=None)[0]
    r = np.corrcoef(np.column_stack([np.ones(len(te)), te.opp_implied, te[col]]) @ b, te.y)[0, 1]
    live = np.corrcoef(np.column_stack([np.ones(len(te)), te.opp_implied, te[col]]) @ np.array([14.33, -0.385, 0.118]), te.y)[0, 1]
    print(f"{col}: refit trailing {b[2]:.3f} implied {b[1]:.3f} OOS r {r:.3f}; live coefficients on {col}: OOS r {live:.3f}")
