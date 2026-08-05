"""Effect-model stub for the evidence pipeline (Workstream D, §8.6).

Magnitudes live HERE, not in the extractor: given historically labeled
events (what was reported, what component change actually realized), fit
a partial-pooling estimate per (event_type, position) and return a
DISTRIBUTION over the component adjustment. v0 is empirical-Bayes
normal-normal shrinkage toward the event-type mean — deliberately
simple; the full hierarchical model with source reliability, teammate
absences, and time-to-lock covariates is a September build gated on real
labeled history (§8.5). The interface is the contract: `fit_effect_model`
consumes LabeledEvents, `EffectModel.predict` returns (mean, sd).

Deltas are FRACTIONAL component changes (+0.20 = the component realized
20% above its pre-event baseline), matching how notes.apply_notes scales
opportunity columns — the eventual consumer multiplies the baseline
component by (1 + delta-draw), with sd further inflated by
ActiveAdjustment.variance_inflation when reports conflict (§8.7).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

__all__ = ["LabeledEvent", "EffectEstimate", "EffectModel",
           "fit_effect_model", "WIDE_PRIOR_SD"]

# Fallback for event types with no labeled history: mean 0 (no evidence
# of effect), sd wide enough that the mixed prior barely moves the
# baseline until data accrues.
WIDE_PRIOR_SD = 0.30
_MIN_SD = 0.02          # never report false certainty from tiny samples
_TAU2_FLOOR = 1e-4      # between-cell variance floor (keeps pooling on)


@dataclass(frozen=True)
class LabeledEvent:
    """One historically labeled event (§8.5 backfill fixture format):
    the pre-lock report and the realized fractional component delta.
    Non-events and false reports belong in the history too (delta ~ 0)
    — dropping them is survivorship bias."""

    event_type: str
    position: str
    component: str
    realized_delta: float


@dataclass(frozen=True)
class EffectEstimate:
    """Distribution over the component adjustment for one event."""

    mean: float
    sd: float
    n: int              # labeled events behind the cell (0 for prior)
    basis: str          # "cell" | "type" | "prior"


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def _var(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


class EffectModel:
    """Normal-normal empirical Bayes per (event_type, position).

    Within each event type: cell means (by position) are shrunk toward
    the type mean with weight n / (n + sigma2 / tau2) — few observations
    means heavy pooling, many means the cell speaks for itself.
    """

    def __init__(self,
                 cells: dict[tuple[str, str], EffectEstimate],
                 types: dict[str, EffectEstimate]):
        self._cells = cells
        self._types = types

    def predict(self, event_type: str, position: str) -> EffectEstimate:
        est = self._cells.get((event_type, position))
        if est is not None:
            return est
        est = self._types.get(event_type)
        if est is not None:
            return est
        return EffectEstimate(0.0, WIDE_PRIOR_SD, 0, "prior")


def fit_effect_model(history: Iterable[LabeledEvent]) -> EffectModel:
    """Fit the v0 partial-pooling model from labeled history."""
    by_type: dict[str, list[float]] = {}
    by_cell: dict[tuple[str, str], list[float]] = {}
    for ev in history:
        by_type.setdefault(ev.event_type, []).append(ev.realized_delta)
        by_cell.setdefault((ev.event_type, ev.position),
                           []).append(ev.realized_delta)

    # Pooled within-cell (observation) variance across all cells with
    # replication; wide fallback when history is too thin to estimate.
    ss, dof = 0.0, 0
    for deltas in by_cell.values():
        if len(deltas) >= 2:
            ss += _var(deltas) * (len(deltas) - 1)
            dof += len(deltas) - 1
    sigma2 = ss / dof if dof else WIDE_PRIOR_SD ** 2

    types: dict[str, EffectEstimate] = {}
    cells: dict[tuple[str, str], EffectEstimate] = {}
    for etype, all_deltas in by_type.items():
        mu_t = _mean(all_deltas)
        cell_items = [(k, v) for k, v in by_cell.items() if k[0] == etype]
        # Between-cell variance: how much positions genuinely differ
        # within this event type (method-of-moments, floored). Estimated
        # from REPLICATED cells when possible — a single-observation cell
        # is exactly what shrinkage exists to protect against, so its
        # outlier must not inflate tau2 and thereby unshrink itself.
        basis = ([(k, v) for k, v in cell_items if len(v) >= 2]
                 or cell_items)
        if len(basis) >= 2:
            cell_means = [_mean(v) for _, v in basis]
            mean_n = _mean([len(v) for _, v in basis])
            tau2 = max(_var(cell_means) - sigma2 / mean_n, _TAU2_FLOOR)
        else:
            tau2 = max(sigma2, _TAU2_FLOOR)
        types[etype] = EffectEstimate(
            mu_t, max(math.sqrt(tau2 + sigma2 / len(all_deltas)), _MIN_SD),
            len(all_deltas), "type")
        for (etype_, pos), deltas in cell_items:
            n = len(deltas)
            precision = 1.0 / tau2 + n / sigma2
            post_mean = ((mu_t / tau2 + n * _mean(deltas) / sigma2)
                         / precision)
            post_sd = max(math.sqrt(1.0 / precision), _MIN_SD)
            cells[(etype_, pos)] = EffectEstimate(post_mean, post_sd, n,
                                                  "cell")
    return EffectModel(cells, types)
