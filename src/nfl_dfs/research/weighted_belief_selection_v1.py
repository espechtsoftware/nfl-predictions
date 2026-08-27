"""Research-only world-weighted tail-portfolio selection.

The production selector remains untouched.  Uniform world weights delegate to
the existing implementation exactly; nonuniform weights replace world counts
with probability mass for coverage, tail probabilities, means, and ladder
utility.  Candidate and world axes are never reordered internally.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

import numpy as np

from ..optimizer import lineup as production_lineup


class WeightedBeliefSelectionError(ValueError):
    """Weighted selection inputs do not define a finite probability bank."""


def normalize_world_weights(
    world_weights: Sequence[float], *, expected_worlds: int,
) -> np.ndarray:
    """Return a finite, nonnegative probability vector over exact worlds."""
    weights = np.asarray(world_weights, dtype=np.float64)
    if weights.ndim != 1 or weights.shape != (expected_worlds,):
        raise WeightedBeliefSelectionError(
            "world weights must align one-to-one with world columns"
        )
    if not np.isfinite(weights).all() or np.any(weights < 0.0):
        raise WeightedBeliefSelectionError(
            "world weights must be finite and nonnegative"
        )
    maximum = float(weights.max(initial=0.0))
    if maximum <= 0.0:
        raise WeightedBeliefSelectionError("world weights have no positive mass")
    scaled = weights / maximum
    total = math.fsum(float(value) for value in scaled)
    if not math.isfinite(total) or total <= 0.0:
        raise WeightedBeliefSelectionError("world weights cannot be normalized")
    normalized = scaled / total
    normalized /= normalized.sum(dtype=np.float64)
    return normalized


def _finite_totals(cand_totals: np.ndarray) -> np.ndarray:
    totals = np.asarray(cand_totals, dtype=np.float64)
    if totals.ndim != 2 or not totals.size or not np.isfinite(totals).all():
        raise WeightedBeliefSelectionError(
            "candidate totals must be a nonempty finite 2-D matrix"
        )
    return totals


def _is_uniform(weights: np.ndarray) -> bool:
    return bool(np.all(weights == weights[0]))


def _weighted_sum(values: np.ndarray, weights: np.ndarray) -> float:
    """Accurate scalar product whose result is stable under world reordering."""
    return math.fsum(
        float(value) * float(weight)
        for value, weight in zip(values, weights, strict=True)
    )


def _weighted_boolean_mass(mask: np.ndarray, weights: np.ndarray) -> float:
    return math.fsum(
        float(weight)
        for hit, weight in zip(mask, weights, strict=True)
        if bool(hit)
    )


def select_weighted_tail_entries(
    cand_totals: np.ndarray,
    n_entries: int,
    line: float,
    world_weights: Sequence[float],
) -> list[int]:
    """Greedy weighted max-coverage with weighted probability/mean ties.

    With uniform weights this calls production ``select_from_support`` rather
    than maintaining a second nominal implementation.  With nonuniform
    weights, ties resolve by weighted P(clear), weighted mean, then lower
    candidate index.
    """
    totals = _finite_totals(cand_totals)
    if type(n_entries) is not int or n_entries < 0:
        raise WeightedBeliefSelectionError("n_entries must be an integer >= 0")
    if not math.isfinite(float(line)):
        raise WeightedBeliefSelectionError("tail line must be finite")
    weights = normalize_world_weights(
        world_weights, expected_worlds=totals.shape[1]
    )
    clears = totals >= float(line)
    if _is_uniform(weights):
        return production_lineup.select_from_support(
            clears,
            clears.mean(axis=1),
            totals.mean(axis=1),
            n_entries,
        )

    n_entries = min(n_entries, len(totals))
    p_line = np.array(
        [_weighted_boolean_mass(row, weights) for row in clears],
        dtype=np.float64,
    )
    mean_total = np.array(
        [_weighted_sum(row, weights) for row in totals], dtype=np.float64
    )
    covered = np.zeros(totals.shape[1], dtype=bool)
    remaining = set(range(len(totals)))
    selected: list[int] = []
    while len(selected) < n_entries and remaining:
        scored = []
        for index in sorted(remaining):
            gain = _weighted_boolean_mass(clears[index] & ~covered, weights)
            scored.append((gain, p_line[index], mean_total[index], -index, index))
        gain, _p, _mean, _tie, best = max(scored)
        if gain <= 0.0:
            break
        selected.append(best)
        covered |= clears[best]
        remaining.remove(best)
    fill = sorted(
        remaining,
        key=lambda index: (p_line[index], mean_total[index], -index),
        reverse=True,
    )
    selected.extend(fill[: n_entries - len(selected)])
    return selected


def _validate_ladder(
    ladder: Mapping[float, float], mean_weight: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    if not isinstance(ladder, Mapping):
        raise WeightedBeliefSelectionError("ladder must be a threshold mapping")
    try:
        pairs = sorted((float(key), float(value)) for key, value in ladder.items())
        mean_weight = float(mean_weight)
    except (TypeError, ValueError) as exc:
        raise WeightedBeliefSelectionError("ladder values must be numeric") from exc
    if (
        any(
            not math.isfinite(threshold)
            or threshold <= 0.0
            or not math.isfinite(weight)
            or weight < 0.0
            for threshold, weight in pairs
        )
        or not math.isfinite(mean_weight)
        or mean_weight < 0.0
    ):
        raise WeightedBeliefSelectionError("ladder thresholds or weights are invalid")
    if mean_weight <= 0.0 and not any(weight > 0.0 for _, weight in pairs):
        raise WeightedBeliefSelectionError("ladder has no positive utility term")
    return (
        np.asarray([threshold for threshold, _ in pairs], dtype=np.float64),
        np.asarray([weight for _, weight in pairs], dtype=np.float64),
        mean_weight,
    )


def select_weighted_ladder_entries(
    cand_totals: np.ndarray,
    n_entries: int,
    ladder: Mapping[float, float],
    world_weights: Sequence[float],
    *,
    mean_weight: float = 0.0,
) -> list[int]:
    """Greedy weighted ``E[u(max)]`` for the sparse tail-utility ladder."""
    totals = _finite_totals(cand_totals)
    if type(n_entries) is not int or n_entries < 0:
        raise WeightedBeliefSelectionError("n_entries must be an integer >= 0")
    thresholds, utility_weights, mean_weight = _validate_ladder(
        ladder, mean_weight
    )
    if mean_weight > 0.0 and np.any(totals < 0.0):
        raise WeightedBeliefSelectionError(
            "ladder mean utility requires nonnegative candidate totals"
        )
    weights = normalize_world_weights(
        world_weights, expected_worlds=totals.shape[1]
    )
    if _is_uniform(weights):
        return production_lineup.select_ladder_entries(
            totals,
            n_entries,
            {float(key): float(value) for key, value in ladder.items()},
            mean_weight=mean_weight,
        )

    n_entries = min(n_entries, len(totals))
    mean_total = np.array(
        [_weighted_sum(row, weights) for row in totals], dtype=np.float64
    )
    best_by_world = np.zeros(totals.shape[1], dtype=np.float64)
    cleared = np.zeros((len(thresholds), totals.shape[1]), dtype=bool)
    remaining = set(range(len(totals)))
    selected: list[int] = []
    while len(selected) < n_entries and remaining:
        scored = []
        for index in sorted(remaining):
            gain = 0.0
            for threshold_index, threshold in enumerate(thresholds):
                newly = (
                    (totals[index] >= threshold)
                    & ~cleared[threshold_index]
                )
                gain += float(utility_weights[threshold_index]) * (
                    _weighted_boolean_mass(newly, weights)
                )
            if mean_weight > 0.0:
                improvement = np.maximum(totals[index] - best_by_world, 0.0)
                gain += mean_weight * _weighted_sum(improvement, weights)
            scored.append((gain, mean_total[index], -index, index))
        _gain, _mean, _tie, best = max(scored)
        selected.append(best)
        np.maximum(best_by_world, totals[best], out=best_by_world)
        cleared |= totals[best] >= thresholds[:, None]
        remaining.remove(best)
    return selected


__all__ = [
    "WeightedBeliefSelectionError",
    "normalize_world_weights",
    "select_weighted_ladder_entries",
    "select_weighted_tail_entries",
]
