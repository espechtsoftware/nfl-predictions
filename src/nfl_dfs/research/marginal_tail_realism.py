"""Marginal upper-tail realism (C lane, 2026-08-19): rank-preserving
per-player tail recalibration machinery.

The winner anatomy audit measured that 49/51 deep-world optima depend on
at least one player exceeding his realized corpus maximum (median 3
players, +19.3 never-realized points per optimum), while actual winners
carry a third of that mass in the same worlds. Jointly with the
book-tail factor-of-two (book-level tails too THIN), the law appears to
misallocate tail mass: too much on independent single-player spikes that
never happen, too little on joint co-booms that do.

This module implements the intervention's mechanical half: a monotone,
rank-preserving shrink of each player's draw distribution ABOVE a high
anchor quantile, targeted so the transformed extreme quantile lands on a
point-in-time ceiling estimate. Because every transform is strictly
monotone per player, the copula (all co-movement structure) is untouched
— only marginal upper tails move. Draws below the anchor are bitwise
unchanged.

Ceiling estimation is deliberately walk-forward: the estimator consumes
only realized history strictly BEFORE the target week. Fitting ceilings
on the same weeks later scored would be outcome leakage dressed as a law
repair; the design doc freezes this discipline before any scored run.

Diagnostic/experimental machinery only: nothing here is wired into
production paths, no lever exists, and any adoption runs through the
standard frozen fixed-budget discipline.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

ANCHOR_QUANTILE = 0.95
TARGET_QUANTILE = 0.999
# Headroom above the best point-in-time evidence: realized history is a
# finite sample of the realizable ceiling, so the target sits a frozen
# 10% above it rather than exactly on it.
CEILING_HEADROOM = 0.10
MIN_HISTORY_ROWS = 1


class TailRealismError(ValueError):
    """Fail-closed contract violation."""


def fit_tail_shrink(
    draws: np.ndarray,
    ceiling: float,
    *,
    anchor_q: float = ANCHOR_QUANTILE,
    target_q: float = TARGET_QUANTILE,
) -> dict:
    """One player's shrink factor so quantile(target_q) lands on ceiling.

    Piecewise-linear transform: below the anchor quantile the draws are
    unchanged; above it, excess over the anchor is scaled by
    ``s = (ceiling - anchor) / (q_target - anchor)``, clipped to (0, 1]
    — the transform only ever SHRINKS toward realism, never inflates a
    thin tail (that direction is the dependence lane's job, not this
    one's). Degenerate tails (target quantile at or below the anchor)
    and ceilings above the simulated target keep ``s = 1.0``.
    """
    values = np.asarray(draws, dtype=np.float64)
    if values.ndim != 1 or len(values) < 100:
        raise TailRealismError("tail fit needs a 1-D draw vector (>=100)")
    if not np.isfinite(values).all() or not np.isfinite(float(ceiling)):
        raise TailRealismError("draws and ceiling must be finite")
    if not 0.5 < anchor_q < target_q < 1.0:
        raise TailRealismError("need 0.5 < anchor_q < target_q < 1")
    anchor = float(np.quantile(values, anchor_q))
    target = float(np.quantile(values, target_q))
    if target <= anchor:
        shrink = 1.0
    else:
        shrink = float(np.clip(
            (float(ceiling) - anchor) / (target - anchor), None, 1.0))
        if shrink <= 0.0:
            # Ceiling at or below the anchor: collapse the tail onto the
            # anchor rather than inverting order.
            shrink = 0.0
    return {
        "anchor": anchor,
        "sim_target": target,
        "ceiling": float(ceiling),
        "shrink": shrink,
    }


def apply_tail_shrink(
    draws: np.ndarray,
    anchors: np.ndarray,
    shrinks: np.ndarray,
) -> np.ndarray:
    """Shrink every player's draws above his anchor; ranks preserved.

    ``draws`` is (players, worlds); ``anchors`` and ``shrinks`` are
    per-player vectors. With shrink in [0, 1] the map
    ``x -> anchor + s * (x - anchor)`` for x > anchor is monotone
    non-decreasing, so within-player world ordering — and therefore the
    joint copula — is unchanged (ties can only be created at s = 0).
    """
    values = np.asarray(draws, dtype=np.float64)
    anchor = np.asarray(anchors, dtype=np.float64).reshape(-1, 1)
    shrink = np.asarray(shrinks, dtype=np.float64).reshape(-1, 1)
    if values.ndim != 2 or len(anchor) != values.shape[0] or \
            len(shrink) != values.shape[0]:
        raise TailRealismError("draws/anchors/shrinks are misaligned")
    if ((shrink < 0.0) | (shrink > 1.0)).any():
        raise TailRealismError("shrink factors must lie in [0, 1]")
    excess = values - anchor
    return np.where(excess > 0.0, anchor + shrink * excess, values)


def assert_ranks_preserved(
    before: np.ndarray, after: np.ndarray,
) -> None:
    """Fail closed unless every player's world ordering is unchanged.

    Strictly increasing pairs must never invert; equality after the
    transform is permitted (a fully collapsed tail ties at the anchor).
    """
    a = np.asarray(before, dtype=np.float64)
    b = np.asarray(after, dtype=np.float64)
    if a.shape != b.shape or a.ndim != 2:
        raise TailRealismError("rank check needs matching 2-D matrices")
    order = np.argsort(a, axis=1, kind="stable")
    sorted_after = np.take_along_axis(b, order, axis=1)
    if (np.diff(sorted_after, axis=1) < -1e-12).any():
        raise TailRealismError("tail transform inverted a world ordering")


def point_in_time_ceiling(
    history: pd.DataFrame,
    *,
    season: int,
    week: int,
    headroom: float = CEILING_HEADROOM,
    position_quantile: float = 0.999,
) -> dict[str, float]:
    """Walk-forward per-player ceilings from realized history only.

    ``history`` carries season/week/id/pos/actual rows. Only rows
    strictly BEFORE (season, week) are consumed — passing later rows is
    allowed (the caller may hold the full corpus) and they are dropped
    here, which keeps the leakage boundary in one audited place. Each
    player's ceiling is ``(1 + headroom) * max(own realized max,
    position-level realized quantile)``; players with no prior history
    fall back to the position component alone.
    """
    needed = {"season", "week", "id", "pos", "actual"}
    if missing := needed - set(history.columns):
        raise TailRealismError(f"history lacks {sorted(missing)}")
    if not 0.0 <= float(headroom) <= 1.0:
        raise TailRealismError("headroom must lie in [0, 1]")
    frame = history.copy()
    frame["season"] = frame.season.astype(int)
    frame["week"] = frame.week.astype(int)
    prior = frame[
        (frame.season < int(season))
        | ((frame.season == int(season)) & (frame.week < int(week)))
    ]
    if prior.empty:
        raise TailRealismError(
            f"no realized history before {season} week {week}")
    prior = prior.drop_duplicates(["season", "week", "id"])
    actual = pd.to_numeric(prior.actual, errors="raise")
    by_pos = actual.groupby(prior.pos.astype(str)).quantile(
        position_quantile).to_dict()
    own_max = actual.groupby(prior.id.astype(str)).max()
    pos_of = prior.drop_duplicates("id").set_index(
        prior.drop_duplicates("id").id.astype(str)).pos.astype(str)
    scale = 1.0 + float(headroom)
    return {
        str(pid): scale * max(
            float(own_max.get(pid, -np.inf)),
            float(by_pos[pos_of[pid]]),
        )
        for pid in pos_of.index
    }


def effect_census(
    before: np.ndarray,
    after: np.ndarray,
    shrinks: Mapping[str, float] | np.ndarray,
) -> dict:
    """Outcome-blind disclosure of how much the transform moved."""
    a = np.asarray(before, dtype=np.float64)
    b = np.asarray(after, dtype=np.float64)
    if a.shape != b.shape:
        raise TailRealismError("effect census needs matching matrices")
    shrink_values = np.asarray(
        list(shrinks.values()) if isinstance(shrinks, Mapping)
        else shrinks, dtype=np.float64)
    moved = np.abs(b - a)
    return {
        "n_players": int(a.shape[0]),
        "n_worlds": int(a.shape[1]),
        "fraction_draws_changed": float((moved > 1e-12).mean()),
        "mean_abs_change": float(moved.mean()),
        "max_abs_change": float(moved.max()),
        "shrink_median": float(np.median(shrink_values)),
        "shrink_q10": float(np.quantile(shrink_values, 0.10)),
        "fraction_players_shrunk": float((shrink_values < 1.0).mean()),
        "fraction_players_collapsed": float((shrink_values == 0.0).mean()),
    }
