"""SPO+ structured loss for player projections (research-only).

The rejected reranker learned on a frozen candidate pool. This is a genuinely
different intervention point: train player scores against the legal lineup
decision they induce. The optimizer callback can be the existing MILP or a
small brute-force fixture. Nothing imports this module in production.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


Optimizer = Callable[[np.ndarray], np.ndarray]


def spo_plus_loss_and_gradient(
    predicted_scores: np.ndarray,
    actual_scores: np.ndarray,
    optimize: Optimizer,
) -> tuple[float, np.ndarray]:
    """SPO+ loss/subgradient for a maximization decision problem.

    ``optimize(values)`` returns a 0/1 incidence vector for the legal lineup
    maximizing ``values @ lineup``. The returned gradient is with respect to
    the predicted player scores and can train a differentiable projection
    model while leaving salary/roster legality inside the real optimizer.
    """
    pred = np.asarray(predicted_scores, dtype=float)
    actual = np.asarray(actual_scores, dtype=float)
    if pred.shape != actual.shape or pred.ndim != 1:
        raise ValueError("predicted_scores and actual_scores must be equal 1-D arrays")
    oracle = np.asarray(optimize(actual), dtype=float)
    adversarial = np.asarray(optimize(2.0 * pred - actual), dtype=float)
    if oracle.shape != pred.shape or adversarial.shape != pred.shape:
        raise ValueError("optimizer must return an incidence vector matching scores")
    loss = float((2.0 * pred - actual) @ (adversarial - oracle))
    gradient = 2.0 * (adversarial - oracle)
    return max(loss, 0.0), gradient


def realized_decision_regret(
    predicted_scores: np.ndarray,
    actual_scores: np.ndarray,
    optimize: Optimizer,
) -> float:
    """Actual oracle score minus score of the prediction-chosen lineup."""
    pred = np.asarray(predicted_scores, dtype=float)
    actual = np.asarray(actual_scores, dtype=float)
    picked = np.asarray(optimize(pred), dtype=float)
    oracle = np.asarray(optimize(actual), dtype=float)
    return float(actual @ oracle - actual @ picked)
