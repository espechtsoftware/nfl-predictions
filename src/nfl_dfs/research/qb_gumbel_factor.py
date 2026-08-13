"""Exact-marginal QB-rooted upper-tail Gumbel rank overlay for frozen G2."""

from __future__ import annotations

import numpy as np
import pandas as pd


MIN_QB_MEAN = 4.0
_EPS = np.finfo(float).eps * 16


def _midranks(values: np.ndarray) -> np.ndarray:
    """Stable ordinal mid-ranks in the open unit interval."""
    row = np.asarray(values, dtype=float)
    if row.ndim != 1 or not np.isfinite(row).all():
        raise ValueError("G2 ranks require one finite draw row")
    order = np.argsort(row, kind="stable")
    ranks = np.empty(len(row), dtype=int)
    ranks[order] = np.arange(len(row))
    return (ranks + 0.5) / len(row)


def gumbel_conditional_cdf(
    receiver_u: np.ndarray,
    qb_u: np.ndarray,
    theta: float,
) -> np.ndarray:
    """P(V <= v | U=u) for a bivariate Gumbel copula."""
    if not np.isfinite(theta) or theta < 1.0:
        raise ValueError("G2 Gumbel theta must be finite and at least one")
    v = np.clip(np.asarray(receiver_u, dtype=float), _EPS, 1.0 - _EPS)
    u = np.clip(np.asarray(qb_u, dtype=float), _EPS, 1.0 - _EPS)
    if v.shape != u.shape or v.ndim != 1:
        raise ValueError("G2 conditional uniforms must be aligned vectors")
    if theta == 1.0:
        return v.copy()
    x = -np.log(u)
    y = -np.log(v)
    total = x ** theta + y ** theta
    copula = np.exp(-(total ** (1.0 / theta)))
    result = (
        copula
        * total ** (1.0 / theta - 1.0)
        * x ** (theta - 1.0)
        / u
    )
    return np.clip(result, 0.0, 1.0)


def invert_gumbel_conditional(
    innovation_u: np.ndarray,
    qb_u: np.ndarray,
    theta: float,
    *,
    iterations: int = 56,
) -> np.ndarray:
    """Invert the receiver conditional CDF by deterministic vector bisection."""
    target = np.clip(np.asarray(innovation_u, dtype=float), _EPS, 1.0 - _EPS)
    root = np.clip(np.asarray(qb_u, dtype=float), _EPS, 1.0 - _EPS)
    if target.shape != root.shape or target.ndim != 1:
        raise ValueError("G2 innovations and QB ranks must align")
    if theta == 1.0:
        return target.copy()
    low = np.full_like(target, _EPS)
    high = np.full_like(target, 1.0 - _EPS)
    for _ in range(iterations):
        middle = (low + high) / 2.0
        below = gumbel_conditional_cdf(middle, root, theta) < target
        low = np.where(below, middle, low)
        high = np.where(below, high, middle)
    return (low + high) / 2.0


def _reorder_exact(row: np.ndarray, scores: np.ndarray) -> np.ndarray:
    order = np.argsort(np.asarray(scores, dtype=float), kind="stable")
    ranks = np.empty(len(order), dtype=int)
    ranks[order] = np.arange(len(order))
    return np.sort(np.asarray(row, dtype=float), kind="stable")[ranks]


def apply_qb_gumbel_factor(
    draws: np.ndarray,
    frame: pd.DataFrame,
    *,
    theta_wr: float,
    theta_te: float,
    min_qb_mean: float = MIN_QB_MEAN,
) -> tuple[np.ndarray, dict]:
    """Apply G2 to same-team WR/TE ranks while preserving every row multiset."""
    values = np.asarray(draws, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(frame):
        raise ValueError("G2 draws and frame are misaligned")
    if not np.isfinite(values).all() or values.shape[1] < 100:
        raise ValueError("G2 requires finite rows and at least 100 worlds")
    required = {"season", "week", "team", "position", "mean_projection"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"G2 frame missing columns {sorted(missing)}")
    for theta in (theta_wr, theta_te):
        if not np.isfinite(theta) or theta < 1.0:
            raise ValueError("G2 theta values must be finite and at least one")

    meta = frame.reset_index(drop=True).copy()
    meta["position"] = meta.position.astype(str).str.upper()
    meta["team"] = meta.team.astype(str).str.upper()
    meta["_row"] = np.arange(len(meta), dtype=int)
    out = values.copy()
    groups = targets = changed = ambiguous = unsupported = 0

    for _keys, group in meta.groupby(["season", "week", "team"], sort=True):
        eligible_qbs = group[
            group.position.eq("QB")
            & pd.to_numeric(group.mean_projection, errors="coerce").ge(min_qb_mean)
        ]
        if len(eligible_qbs) != 1:
            if len(eligible_qbs) > 1:
                ambiguous += 1
            else:
                unsupported += 1
            continue
        root_index = int(eligible_qbs._row.iloc[0])
        root = _midranks(values[root_index])
        groups += 1
        for index, position in group[["_row", "position"]].itertuples(
                index=False, name=None):
            theta = theta_wr if position == "WR" else (
                theta_te if position == "TE" else None)
            if theta is None:
                continue
            index = int(index)
            innovation = _midranks(values[index])
            score = invert_gumbel_conditional(innovation, root, float(theta))
            reordered = _reorder_exact(values[index], score)
            out[index] = reordered
            targets += 1
            changed += int(not np.array_equal(reordered, values[index]))

    maximum_mean_delta = float(np.max(
        np.abs(out.mean(axis=1) - values.mean(axis=1)), initial=0.0))
    return out, {
        "eligible_qb_team_weeks": groups,
        "ambiguous_qb_team_weeks": ambiguous,
        "unsupported_qb_team_weeks": unsupported,
        "target_rows": targets,
        "changed_rank_rows": changed,
        "theta_wr": float(theta_wr),
        "theta_te": float(theta_te),
        "maximum_mean_delta": maximum_mean_delta,
    }


__all__ = [
    "MIN_QB_MEAN",
    "apply_qb_gumbel_factor",
    "gumbel_conditional_cdf",
    "invert_gumbel_conditional",
]
