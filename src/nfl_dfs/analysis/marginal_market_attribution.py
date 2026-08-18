"""Marginal-vs-dependence attribution audit (S4, operator-approved
2026-08-18, q95/q99 descriptive until the instrument validates there).

The book tail is under-predicted at 210+ while walk-forward TabPFN
exceedance says ordinary players' marginal q90 is, if anything, too WIDE.
Those two facts together indict dependence, not marginal width — but only
by inference. This audit pins it: compare the production shaped marginals
(the archived player-by-world draw rows — exactly what the selector saw)
against the market-implied quantiles from alternate-line ladders
(validated calibrated at q90, Addendum 45) and realized outcomes,
walk-forward, stratified by position and breakout state.

Reading, frozen before any number: if marginal upper tails verify while
the book tail stays thin, dependence is confirmed as the deficit and
marginal work stays closed; if specific strata fail (e.g. ordinary
veterans wide, thin-history narrow), that licenses a TARGETED marginal
protocol, never the rejected generic widening. Distinct from the CLOSED
player-level market-tail feature gate: here the market curve is the
calibration instrument; nothing feeds a model, a candidate, or a
selector.

Pure computation on prepared frames; the runner supplies honest pre-lock
market quantiles (the repaired pre-lock snapshot rule) and archived draw
rows. Diagnostic-only; licenses nothing.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

PROTOCOL_ID = "20260818-marginal-market-attribution-v1"
QUANTILES = (0.90, 0.95, 0.99)
VALIDATED_QUANTILES = (0.90,)
DESCRIPTIVE_QUANTILES = (0.95, 0.99)
MIN_STRATUM_ROWS = 25


class AttributionError(ValueError):
    """Fail-closed contract violation."""


def model_quantiles_from_draws(
    draws_row: np.ndarray, quantiles: Sequence[float] = QUANTILES,
) -> dict[str, float]:
    """Per-player shaped-marginal quantiles from an archived draw row."""
    row = np.asarray(draws_row, dtype=float)
    if row.ndim != 1 or len(row) < 100:
        raise AttributionError(
            "draw row must be one-dimensional with at least 100 worlds")
    if not np.isfinite(row).all():
        raise AttributionError("draw row must be finite")
    return {
        _q_key(q): float(np.quantile(row, q)) for q in quantiles
    }


def _q_key(q: float) -> str:
    return f"q{int(round(float(q) * 100))}"


def pinball_loss(realized: np.ndarray, predicted: np.ndarray, q: float
                 ) -> float:
    realized = np.asarray(realized, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    delta = realized - predicted
    return float(np.mean(np.where(delta >= 0, q * delta, (q - 1) * delta)))


def _stratum_block(group: pd.DataFrame) -> dict:
    block: dict = {"n": int(len(group))}
    for q in QUANTILES:
        key = _q_key(q)
        model_col = f"model_{key}"
        market_col = f"market_{key}"
        nominal = 1.0 - q
        model_exceed = float((group.actual > group[model_col]).mean())
        market_exceed = float((group.actual > group[market_col]).mean())
        block[key] = {
            "nominal_exceedance": nominal,
            "model_exceedance": model_exceed,
            "market_exceedance": market_exceed,
            "model_pinball": pinball_loss(
                group.actual.to_numpy(), group[model_col].to_numpy(), q),
            "market_pinball": pinball_loss(
                group.actual.to_numpy(), group[market_col].to_numpy(), q),
            "instrument_status": (
                "validated" if q in VALIDATED_QUANTILES else "descriptive"),
        }
        block[key]["model_minus_market_pinball"] = (
            block[key]["model_pinball"] - block[key]["market_pinball"])
    return block


def attribution_report(frame: pd.DataFrame) -> dict:
    """The frozen report over one prepared common-support panel.

    ``frame`` rows are player-weeks WITH market alt-ladder coverage
    (common-support law: model and market are compared on identical
    rows), carrying: season, week, player_id, position, stratum
    (breakout-state label or "ordinary"), actual, model_q90/95/99,
    market_q90/95/99.
    """
    required = {
        "season", "week", "player_id", "position", "stratum", "actual",
    } | {f"{side}_{_q_key(q)}" for side in ("model", "market")
         for q in QUANTILES}
    if missing := required - set(frame.columns):
        raise AttributionError(f"panel lacks columns {sorted(missing)}")
    if frame.empty:
        raise AttributionError("attribution panel is empty")
    numeric = frame[[c for c in required
                     if c not in ("player_id", "position", "stratum")]]
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise AttributionError("panel contains non-finite values")
    if frame.duplicated(["season", "week", "player_id"]).any():
        raise AttributionError("panel repeats a player-week")

    report: dict = {
        "protocol_id": PROTOCOL_ID,
        "n_rows": int(len(frame)),
        "overall": _stratum_block(frame),
        "by_position": {},
        "by_stratum": {},
        "uses_realized_outcomes": True,
        "fit_performed": False,
        "tuning_performed": False,
        "gate_decision": None,
    }
    for name, target in (("by_position", "position"),
                         ("by_stratum", "stratum")):
        for value, group in frame.groupby(target, observed=True):
            block = (
                _stratum_block(group)
                if len(group) >= MIN_STRATUM_ROWS
                else {"n": int(len(group)),
                      "suppressed_below_min_rows": MIN_STRATUM_ROWS}
            )
            report[name][str(value)] = block
    return report
