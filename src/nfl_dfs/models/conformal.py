"""Rolling conformal calibration for live confidence (external review
3.1, built 2026-08-04; VALIDATES LIVE — no historical backtest exists
because stored weekly projections only accrue in-season).

The lineup cards' confidence% comes from a normal approximation whose
sigma is known-miscalibrated (three independent 2026-08 studies:
conformal, market, kNN — our tails under-cover). Once >= MIN_ROWS of
recent (projection, actual) pairs exist, `sigma_scale` returns the
multiplier that makes the last-N-weeks' q90 coverage exact; before
that it returns 1.0 (today's behavior, unchanged). Env CQR_CONF=0
disables.
"""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)

MIN_ROWS = 100
N_WEEKS = 3
CLIP = (0.6, 1.8)
Z90 = 1.2816


def sigma_scale(season: int, week: int) -> float:
    """Multiplier for the confidence sigma, from the last N completed
    weeks' calibration error. 1.0 whenever data is thin or unavailable."""
    import os

    if os.environ.get("CQR_CONF", "1") in ("0", ""):
        return 1.0
    try:
        from ..bq import query_df
        from ..config import settings

        d = query_df(f"""
          SELECT p.proj_points, p.proj_std, a.dk_points AS actual
          FROM `{settings.predictions}.player_projections` p
          JOIN `{settings.features}.player_week_actuals` a
            ON a.gsis_id = p.gsis_id AND a.season = p.season
           AND a.week = p.week
          WHERE p.season = {int(season)}
            AND p.week BETWEEN {max(int(week) - N_WEEKS, 1)} AND {int(week) - 1}
            AND p.proj_std IS NOT NULL AND p.proj_std > 0""")
        if len(d) < MIN_ROWS:
            return 1.0
        z = (d.actual - d.proj_points) / d.proj_std
        emp_z90 = float(np.quantile(z, 0.9))
        scale = float(np.clip(emp_z90 / Z90, *CLIP))
        log.info("conformal sigma scale (wk %s, %d rows): %.3f",
                 week, len(d), scale)
        return scale
    except Exception:
        log.exception("conformal scale unavailable; neutral 1.0")
        return 1.0
