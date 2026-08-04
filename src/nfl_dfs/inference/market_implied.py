"""Market-implied player distributions from alternate prop lines.

De-vigs DK's alternate-line ladders (raw.prop_lines) into implied
P(over x) curves and quantiles. Validated 2026-08-03 (study report
Addendum 45, scripts/prop_implied_study.py): on 2023-25 matched
player-weeks the market's implied q90 arrives calibrated (coverage
0.92) and beats/ties our LGB quantiles on pinball loss — and
model-vs-market tail disagreement predicts the direction of market
error BOTH ways. Usage contract mirrors the ETR rule: disagreement
FLAG for the watchlist/market page, not a silent model input, until a
replay arm judges it as a feature.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ALT_MARKETS = {
    "player_reception_yds_alternate": "rec_yards",
    "player_rush_yds_alternate": "rush_yards",
    "player_pass_yds_alternate": "pass_yards",
}


def american_implied(price: float) -> float:
    """Implied probability of American odds (vig included)."""
    a = float(price)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def implied_curve(ladder: pd.DataFrame) -> tuple[np.ndarray, np.ndarray] | None:
    """De-vigged, monotone P(over x) from one player's alt-line ladder.

    ladder: columns point, outcome_name ('Over'/'Under'), price
    (American). Pairwise de-vig where both sides exist; single-sided
    rows assume ~5% one-way margin. Needs >=3 points.
    """
    pts = []
    for pt, g in ladder.groupby("point"):
        inv = {r.outcome_name: american_implied(r.price)
               for r in g.itertuples()}
        if "Over" in inv and "Under" in inv:
            p = inv["Over"] / (inv["Over"] + inv["Under"])
        elif "Over" in inv:
            p = inv["Over"] / 1.05
        else:
            continue
        pts.append((float(pt), float(np.clip(p, 1e-4, 1 - 1e-4))))
    if len(pts) < 3:
        return None
    pts.sort()
    x = np.array([p[0] for p in pts])
    y = np.minimum.accumulate(np.array([p[1] for p in pts]))
    return x, y


def curve_quantile(x: np.ndarray, y: np.ndarray, q: float) -> float:
    """Smallest x with P(X<=x) >= q; mild linear tail extrapolation."""
    tgt = 1.0 - q
    if y[-1] > tgt:
        return float(x[-1] + (x[-1] - x[0]) * 0.15)
    if y[0] <= tgt:
        return float(x[0])
    return float(np.interp(tgt, y[::-1], x[::-1]))


def market_quantiles(props: pd.DataFrame,
                     quantiles: tuple[float, ...] = (0.5, 0.9)) -> pd.DataFrame:
    """One row per (season, week, market, player) with implied quantiles.

    props: prop_lines rows (already filtered to latest pre-kick snapshot
    and one bookmaker).
    """
    rows = []
    for key, g in props.groupby(["season", "week", "market", "player"]):
        c = implied_curve(g)
        if c is None:
            continue
        x, y = c
        row = dict(zip(["season", "week", "market", "player"], key))
        row["n_points"] = len(x)
        for q in quantiles:
            row[f"q{int(q * 100)}"] = curve_quantile(x, y, q)
        rows.append(row)
    return pd.DataFrame(rows)
