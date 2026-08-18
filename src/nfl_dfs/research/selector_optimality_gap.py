"""Greedy selector optimality-gap audit (A3, 2026-08-18).

Measures how far the production greedy coverage selector sits from the
EXACT optimum of its own objective on a given candidate-totals matrix.
One-swap refinements recover nothing on the historical misses, which
suggests the gap is ~zero; proving that closes the selector-ALGORITHM
family permanently and redirects all remaining selection attention to the
objective (the SELECT_LADDER family) and the pool (union admission,
residual columns). A material gap instead licenses an exact/beam
selection upgrade as a frozen arm.

Score-free: operates on simulated candidate totals only, reads no realized
outcome, and licenses nothing by itself.
"""
from __future__ import annotations

import numpy as np
import pulp

from ..optimizer.lineup import select_tail_entries

PROTOCOL_ID = "20260818-selector-optimality-gap-v1"
CBC_TIME_LIMIT_SECONDS = 600


class OptimalityGapError(ValueError):
    """Fail-closed contract violation."""


def greedy_coverage(totals: np.ndarray, n_entries: int, line: float) -> dict:
    """Worlds covered by the unchanged production greedy selection."""
    totals = np.asarray(totals, dtype=float)
    picked = select_tail_entries(totals, n_entries, line)
    covered = int((totals[picked] >= line).any(axis=0).sum())
    return {"selected": [int(i) for i in picked], "covered_worlds": covered}


def exact_coverage_optimum(
    totals: np.ndarray,
    n_entries: int,
    line: float,
    *,
    time_limit_seconds: int = CBC_TIME_LIMIT_SECONDS,
) -> dict:
    """Exact max-coverage optimum via CBC over the coverable worlds.

    Only worlds cleared by at least one candidate carry a variable; the
    result is citable ONLY when the solver status is Optimal — a timeout
    yields a bound, never a gap claim.
    """
    totals = np.asarray(totals, dtype=float)
    if totals.ndim != 2 or not len(totals):
        raise OptimalityGapError("totals must be (candidates, worlds)")
    clears = totals >= line
    coverable = np.flatnonzero(clears.any(axis=0))
    n_entries = min(int(n_entries), len(totals))
    if n_entries <= 0:
        raise OptimalityGapError("entry count must be positive")
    problem = pulp.LpProblem("exact_max_coverage", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x_{c}", cat="Binary") for c in range(len(totals))]
    y = {int(w): pulp.LpVariable(f"y_{w}", cat="Binary") for w in coverable}
    problem += pulp.lpSum(y.values())
    problem += pulp.lpSum(x) == n_entries
    for w, y_w in y.items():
        problem += y_w <= pulp.lpSum(
            x[c] for c in np.flatnonzero(clears[:, w]))
    solver = pulp.PULP_CBC_CMD(
        msg=False, timeLimit=int(time_limit_seconds))
    problem.solve(solver)
    status = pulp.LpStatus[problem.status]
    covered = int(round(pulp.value(problem.objective) or 0.0))
    selected = [c for c in range(len(totals)) if (x[c].value() or 0) > 0.5]
    return {
        "status": status,
        "covered_worlds": covered,
        "selected": selected,
        "coverable_worlds": int(len(coverable)),
    }


def optimality_gap_report(
    totals: np.ndarray,
    n_entries: int,
    line: float,
    *,
    time_limit_seconds: int = CBC_TIME_LIMIT_SECONDS,
) -> dict:
    """Greedy versus exact on one slate's totals; gap is citable only on
    an Optimal exact status."""
    greedy = greedy_coverage(totals, n_entries, line)
    exact = exact_coverage_optimum(
        totals, n_entries, line, time_limit_seconds=time_limit_seconds)
    gap = (
        exact["covered_worlds"] - greedy["covered_worlds"]
        if exact["status"] == "Optimal" else None
    )
    if gap is not None and gap < 0:
        raise OptimalityGapError(
            "exact optimum below greedy: solver or contract defect")
    return {
        "protocol_id": PROTOCOL_ID,
        "n_entries": int(min(n_entries, len(np.asarray(totals)))),
        "line": float(line),
        "greedy": greedy,
        "exact": exact,
        "gap_worlds": gap,
        "gap_citable": exact["status"] == "Optimal",
    }
