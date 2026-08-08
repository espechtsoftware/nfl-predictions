"""Walk-forward DST ceiling model experiment.

Production DST means are already modeled separately. The remaining finding is
tail coverage: cheap defenses were disproportionately absent from known winner
pools. This module estimates P(DST score >= threshold) from strictly-prior
pressure/takeaway form and opponent vulnerability. It writes only a research
table and cannot alter live projections or candidate generation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = (
    "implied_opponent_total", "team_spread", "dst_points_l4",
    "dst_points_l16", "sacks_l4", "takeaways_l4", "return_tds_l16",
    "opp_sack_rate_l4", "opp_giveaway_rate_l4",
)

DST_TAIL_SQL = """
WITH opp_game AS (
  SELECT posteam AS team, season, week,
         SAFE_DIVIDE(COUNTIF(sack = 1), NULLIF(COUNTIF(qb_dropback = 1), 0))
           AS sack_rate,
         SAFE_DIVIDE(
           COUNTIF(interception = 1 OR fumble_lost = 1),
           NULLIF(COUNTIF(qb_dropback = 1 OR rush_attempt = 1), 0))
           AS giveaway_rate
  FROM `{raw}.pbp`
  WHERE season_type = 'REG' AND posteam IS NOT NULL
  GROUP BY 1, 2, 3
),
opp_roll AS (
  SELECT team, season, week,
         AVG(sack_rate) OVER w4 AS opp_sack_rate_l4,
         AVG(giveaway_rate) OVER w4 AS opp_giveaway_rate_l4
  FROM opp_game
  WINDOW w4 AS (PARTITION BY team, season ORDER BY week
                ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
),
def_roll AS (
  SELECT d.*,
         AVG(sacks) OVER w4 AS sacks_l4,
         AVG(interceptions + fumble_recoveries) OVER w4 AS takeaways_l4,
         AVG(return_tds) OVER w16 AS return_tds_l16
  FROM `{features}.team_defense_week` d
  WINDOW
    w4 AS (PARTITION BY team, season ORDER BY week
           ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
    w16 AS (PARTITION BY team ORDER BY season, week
            ROWS BETWEEN 16 PRECEDING AND 1 PRECEDING)
)
SELECT d.season, d.week, d.team, s.opponent, d.dst_dk_points,
       s.implied_opponent_total, s.team_spread,
       d.dst_points_l4, d.dst_points_l16, d.sacks_l4, d.takeaways_l4,
       d.return_tds_l16, o.opp_sack_rate_l4, o.opp_giveaway_rate_l4
FROM def_roll d
JOIN `{features}.schedule_long` s
  ON s.team=d.team AND s.season=d.season AND s.week=d.week
LEFT JOIN opp_roll o
  ON o.team=s.opponent AND o.season=d.season AND o.week=d.week
"""


def walk_forward_probabilities(
    frame: pd.DataFrame, threshold: float = 15.0, min_train_seasons: int = 2
) -> pd.DataFrame:
    """Season walk-forward logistic estimates; no random split is allowed."""
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    missing = (set(FEATURES) | {"season", "dst_dk_points"}) - set(frame.columns)
    if missing:
        raise ValueError(f"DST tail frame missing {sorted(missing)}")
    df = frame.copy()
    df["tail_actual"] = pd.to_numeric(df.dst_dk_points, errors="coerce").ge(threshold)
    seasons = sorted(int(s) for s in df.season.dropna().unique())
    rows = []
    for season in seasons:
        prior = [s for s in seasons if s < season]
        if len(prior) < min_train_seasons:
            continue
        train = df[df.season < season]
        test = df[df.season == season].copy()
        if train.tail_actual.nunique() < 2 or test.empty:
            continue
        model = make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(),
            LogisticRegression(C=0.25, max_iter=500, class_weight="balanced"),
        )
        model.fit(train[list(FEATURES)], train.tail_actual.astype(int))
        test["tail_probability"] = model.predict_proba(test[list(FEATURES)])[:, 1]
        rows.append(test)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def tail_metrics(scored: pd.DataFrame) -> dict[str, float | int]:
    if scored.empty:
        return {"rows": 0, "brier": float("nan"), "top_decile_lift": float("nan")}
    y = scored.tail_actual.astype(float)
    p = scored.tail_probability.astype(float)
    cutoff = p.quantile(0.9)
    base = y.mean()
    return {
        "rows": int(len(scored)),
        "brier": float(np.mean((p - y) ** 2)),
        "base_tail_rate": float(base),
        "top_decile_tail_rate": float(y[p >= cutoff].mean()),
        "top_decile_lift": float(y[p >= cutoff].mean() - base),
    }
