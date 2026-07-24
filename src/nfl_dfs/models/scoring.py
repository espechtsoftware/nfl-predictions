"""DraftKings NFL Classic scoring (guide §6.1).

Vectorized: every StatLine field accepts a scalar or an ndarray, and
`dk_points` broadcasts — the simulator scores (players, sims) arrays of
draws in one call. The yardage bonuses are why the distribution matters:
they are discontinuous at 100/300 and only the draws see that.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class StatLine:
    pass_yards: float | np.ndarray = 0.0
    pass_tds: float | np.ndarray = 0.0
    interceptions: float | np.ndarray = 0.0
    rush_yards: float | np.ndarray = 0.0
    rush_tds: float | np.ndarray = 0.0
    receptions: float | np.ndarray = 0.0
    rec_yards: float | np.ndarray = 0.0
    rec_tds: float | np.ndarray = 0.0
    fumbles_lost: float | np.ndarray = 0.0
    two_point_conversions: float | np.ndarray = 0.0
    return_tds: float | np.ndarray = 0.0


def dk_points(s: StatLine) -> float | np.ndarray:
    """DK Classic points for a stat line. Bonus thresholds are inclusive
    (100 receiving yards is 100+, per DK's rules)."""
    pass_yards = np.asarray(s.pass_yards, dtype=float)
    rush_yards = np.asarray(s.rush_yards, dtype=float)
    rec_yards = np.asarray(s.rec_yards, dtype=float)

    pts = (
        0.04 * pass_yards
        + 4.0 * np.asarray(s.pass_tds, dtype=float)
        - 1.0 * np.asarray(s.interceptions, dtype=float)
        + 3.0 * (pass_yards >= 300.0)
        + 0.1 * rush_yards
        + 6.0 * np.asarray(s.rush_tds, dtype=float)
        + 3.0 * (rush_yards >= 100.0)
        + 1.0 * np.asarray(s.receptions, dtype=float)
        + 0.1 * rec_yards
        + 6.0 * np.asarray(s.rec_tds, dtype=float)
        + 3.0 * (rec_yards >= 100.0)
        - 1.0 * np.asarray(s.fumbles_lost, dtype=float)
        + 2.0 * np.asarray(s.two_point_conversions, dtype=float)
        + 6.0 * np.asarray(s.return_tds, dtype=float)
    )
    return float(pts) if pts.ndim == 0 else pts
