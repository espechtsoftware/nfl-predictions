"""Outcome-free exact tie diagnostics for the production tail selector."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def stable_identity_tail_selection(
    candidate_totals: np.ndarray,
    candidate_keys: Sequence[str],
    n_entries: int,
    line: float,
) -> dict[str, Any]:
    """Select with the production objective and a stable roster-ID final tie-break.

    The primary marginal-world and p-line comparisons are integer counts. The
    simulated mean remains the production tertiary criterion. Candidate
    identity is consulted only when all three production values are exactly
    equal, making row-permutation behavior observable without changing the
    primary objective.
    """
    totals = np.asarray(candidate_totals, dtype=float)
    keys = tuple(map(str, candidate_keys))
    if (
        totals.ndim != 2
        or not len(totals)
        or totals.shape[1] == 0
        or not np.isfinite(totals).all()
        or len(keys) != len(totals)
        or len(set(keys)) != len(keys)
        or not 0 < int(n_entries) <= len(totals)
        or not np.isfinite(line)
    ):
        raise ValueError("selector tie census inputs are invalid")

    clears = totals >= float(line)
    p_counts = clears.sum(axis=1, dtype=np.int64)
    means = totals.mean(axis=1, dtype=np.float64)
    covered = np.zeros(totals.shape[1], dtype=bool)
    remaining = set(range(len(totals)))
    selected: list[int] = []
    trace: list[dict[str, Any]] = []

    while len(selected) < int(n_entries) and remaining:
        ordered = sorted(remaining, key=lambda index: keys[index])
        gains = {
            index: int(np.count_nonzero(clears[index] & ~covered))
            for index in ordered
        }
        best_gain = max(gains.values())
        if best_gain == 0:
            break
        gain_ties = [index for index in ordered if gains[index] == best_gain]
        best_p = max(int(p_counts[index]) for index in gain_ties)
        support_ties = [
            index for index in gain_ties if int(p_counts[index]) == best_p
        ]
        best_mean = max(float(means[index]) for index in support_ties)
        numeric_ties = [
            index for index in support_ties if float(means[index]) == best_mean
        ]
        chosen = min(numeric_ties, key=lambda index: keys[index])
        trace.append({
            "slot": len(selected) + 1,
            "stage": "marginal",
            "best_marginal_worlds": best_gain,
            "best_p_line_worlds": best_p,
            "best_mean_total": best_mean,
            "marginal_tie_candidates": len(gain_ties),
            "marginal_and_p_line_tie_candidates": len(support_ties),
            "full_numeric_tie_candidates": len(numeric_ties),
            "selected_key": keys[chosen],
        })
        selected.append(chosen)
        remaining.remove(chosen)
        covered |= clears[chosen]

    while len(selected) < int(n_entries):
        ordered = sorted(remaining, key=lambda index: keys[index])
        best_p = max(int(p_counts[index]) for index in ordered)
        support_ties = [
            index for index in ordered if int(p_counts[index]) == best_p
        ]
        best_mean = max(float(means[index]) for index in support_ties)
        numeric_ties = [
            index for index in support_ties if float(means[index]) == best_mean
        ]
        chosen = min(numeric_ties, key=lambda index: keys[index])
        trace.append({
            "slot": len(selected) + 1,
            "stage": "fill",
            "best_marginal_worlds": 0,
            "best_p_line_worlds": best_p,
            "best_mean_total": best_mean,
            "marginal_tie_candidates": len(ordered),
            "marginal_and_p_line_tie_candidates": len(support_ties),
            "full_numeric_tie_candidates": len(numeric_ties),
            "selected_key": keys[chosen],
        })
        selected.append(chosen)
        remaining.remove(chosen)

    return {
        "version": "selector-exact-tie-census-v1",
        "uses_realized_outcomes": False,
        "entries": int(n_entries),
        "line": float(line),
        "selected_indices": selected,
        "selected_keys": [keys[index] for index in selected],
        "covered_worlds": int(np.count_nonzero(covered)),
        "steps_with_marginal_ties": int(sum(
            row["stage"] == "marginal"
            and row["marginal_tie_candidates"] > 1
            for row in trace
        )),
        "steps_with_marginal_and_p_line_ties": int(sum(
            row["stage"] == "marginal"
            and row["marginal_and_p_line_tie_candidates"] > 1
            for row in trace
        )),
        "steps_with_full_numeric_ties": int(sum(
            row["full_numeric_tie_candidates"] > 1 for row in trace
        )),
        "trace": trace,
    }


__all__ = ["stable_identity_tail_selection"]

