"""Opposing-QB experience adjustment for DST projections.

Defenses facing inexperienced QBs outscore their own trailing form by a
large, monotonic margin — measured 2026-07-26 on 3,428 DST-weeks
(2014-2021 + 2025 real-salary seasons), residual vs the defense's own
trailing 4-week average:

    <=3 career starts  +2.19 DK pts     11-30  -0.51
    4-10               +1.48            >30    -0.72

A DST projection built only from its own trailing average can't see who
plays QB on the other side; this module supplies the correction.

Point-in-time note: the week-W starter is identified as the team's QB
with the most attempts that week. In production the starter is announced
publicly before lock, so using the actual starter in replays is a fair
approximation of pre-lock knowledge, not an answer-key leak.
"""

from __future__ import annotations

import pandas as pd

# (upper bound on prior starts, DK-point adjustment) — from the study above
BUCKETS = ((3, 2.2), (10, 1.5), (30, -0.5), (float("inf"), -0.7))


def adjustment(prior_starts: pd.Series) -> pd.Series:
    """DK-point adjustment to a DST's projection given the OPPOSING
    starter's career starts. Unknown starter (NaN) -> 0."""
    out = pd.Series(0.0, index=prior_starts.index)
    prev = -1.0
    for ub, adj in BUCKETS:
        out[(prior_starts > prev) & (prior_starts <= ub)] = adj
        prev = ub
    out[prior_starts.isna()] = 0.0
    return out


def starter_prior_starts() -> pd.DataFrame:
    """(season, week, team, prior_starts) for each team-week's starting QB
    — career starts strictly before that week."""
    from ..bq import query_df
    from ..config import settings

    return query_df(
        f"""
        WITH starters AS (
          SELECT season, week, team, player_id,
                 ROW_NUMBER() OVER (PARTITION BY season, week, team
                                    ORDER BY attempts DESC) AS rk
          FROM `{settings.raw}.weekly_stats`
          WHERE position = 'QB' AND attempts > 0
        )
        SELECT season, week, team,
               COUNT(*) OVER (PARTITION BY player_id ORDER BY season, week
                              ROWS BETWEEN UNBOUNDED PRECEDING
                              AND 1 PRECEDING) AS prior_starts
        FROM starters WHERE rk = 1
        """
    )
