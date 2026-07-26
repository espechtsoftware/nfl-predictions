"""Market blending (guide §7.7): the market carries real information, and
`final = w*model + (1-w)*market` almost always beats either alone. The
weight is fit by least squares on validation; realistic values land around
0.3–0.5, which is a useful reality check on how much edge exists.

Also: prop-line → expected-value conversions and American-odds utilities
for building the market projection in the first place.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats


BLEND_W = 0.45  # model weight; refit on validation


def fit_blend_weight(
    truth: np.ndarray, model: np.ndarray, market: np.ndarray
) -> float:
    """Least-squares w for truth ≈ w*model + (1-w)*market, clipped to [0, 1].
    Equivalent to regressing (truth - market) on (model - market)."""
    truth = np.asarray(truth, dtype=float)
    model = np.asarray(model, dtype=float)
    market = np.asarray(market, dtype=float)
    ok = ~(np.isnan(truth) | np.isnan(model) | np.isnan(market))
    dm = model[ok] - market[ok]
    dt = truth[ok] - market[ok]
    denom = float(dm @ dm)
    if denom == 0.0:
        return 0.5
    return float(np.clip(dm @ dt / denom, 0.0, 1.0))


def blend(model: np.ndarray, market: np.ndarray, w: float) -> np.ndarray:
    """Weighted blend, falling back to the model where the market is NaN —
    a player with no prop line still needs a projection."""
    model = np.asarray(model, dtype=float)
    market = np.asarray(market, dtype=float)
    out = w * model + (1.0 - w) * market
    return np.where(np.isnan(market), model, out)


def market_projection_frame(feats: pd.DataFrame) -> pd.Series:
    """Market implied projection per row. Prop-derived means would slot in
    here; absent props this is DK's own points-per-game figure (crude but
    documented as the stand-in, §7.7)."""
    if "dk_ppg" not in feats.columns:
        return pd.Series(np.nan, index=feats.index, name="market")
    return pd.to_numeric(feats["dk_ppg"], errors="coerce").rename("market")


def american_to_prob(odds: float) -> float:
    """Implied probability of American odds (vig included)."""
    if odds < 0:
        return -odds / (-odds + 100.0)
    return 100.0 / (odds + 100.0)


def devig_two_way(p_over: float, p_under: float) -> tuple[float, float]:
    """Strip the vig from a two-way market by normalizing."""
    total = p_over + p_under
    return p_over / total, p_under / total


def prop_line_to_mean(line: float, over_prob: float, dist: str) -> float:
    """Expected value implied by an over/under line and its (de-vigged)
    over probability. Normal for yardage props, Poisson for counts."""
    if dist == "normal":
        # Yardage-prop sigma scales roughly with the line itself.
        sigma = 0.30 * max(line, 1.0)
        return float(line + stats.norm.ppf(over_prob) * sigma)
    if dist == "poisson":
        k = int(np.ceil(line))  # over hits at k or more for a half-point line

        def gap(lam: float) -> float:
            return stats.poisson.sf(k - 1, lam) - over_prob

        return float(optimize.brentq(gap, 1e-6, max(4.0 * line + 10.0, 20.0)))
    raise ValueError(f"unknown distribution {dist!r}")
