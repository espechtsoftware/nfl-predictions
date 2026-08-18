"""Null-calibrated construction floor (S1, operator-approved 2026-08-18).

The observed forensic decomposition on the 54-slate corpus is
H−P ≈ 4.06, P−C ≈ 68.91, C−S ≈ 5.01 — measured against ONE realized
outcome per slate. P is a hindsight maximum over an astronomically larger
lineup space than the candidate pool, so even a generator holding the TRUE
outcome law would show a large P−C gap from order statistics alone.
Nothing currently distinguishes "beliefs are wrong by ~69 points" from
"any finite candidate set loses ~55 points to the hindsight max under
perfect beliefs."

This module computes the same H/P/C/S chain with the realized outcome
replaced by held-out simulated worlds drawn from the frozen production law
itself. The distribution of the resulting self-law gaps is the noise
floor: observed-minus-floor is the winnable part of the construction gap,
and its size decides whether the next heavy slots belong to construction
(residual columns, union admission) or to the law (DST/OT/dependence).

Score-free: no realized outcome is ever read. Oracles reuse the frozen
forensic solver under the exact production stack contract (QB+2, one
bring-back, $49k floor). Execution protocol:
reports/2026-08-18-null-gap-floor-protocol.md — the held-out worlds MUST
come from a fresh-seed world block generated on the frozen production
image (selection-visible worlds would bias C upward and understate the
floor), and the world count W is frozen there before any number is seen.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from .final_forensic import _solve_oracle

PROTOCOL_ID = "20260818-null-gap-floor-v1"
# Exact production construction contract (exact-stack addendum).
QB_STACK_MIN = 2
BRING_BACK_MIN = 1
MIN_SALARY = 49_000
SALARY_CAP = 50_000
# The observed 54-slate exact-stack gaps this floor calibrates.
OBSERVED_GAPS = {
    "h_minus_p": 4.057,
    "p_minus_c": 68.914,
    "c_minus_s": 5.007,
}


class NullGapError(ValueError):
    """Fail-closed contract violation."""


def _roster_sum(
    roster: Sequence[str], values: Mapping[str, float],
) -> float:
    ids = [str(pid) for pid in roster]
    if len(ids) != 9 or len(set(ids)) != 9:
        raise NullGapError("roster must hold nine unique player ids")
    missing = [pid for pid in ids if pid not in values]
    if missing:
        raise NullGapError(f"roster players missing world values: {missing}")
    return float(sum(values[pid] for pid in ids))


def slate_null_gaps(
    players: pd.DataFrame,
    candidate_rosters: Sequence[Sequence[str]],
    selected_indices: Sequence[int],
    world_values: Mapping[str, float],
) -> dict:
    """One held-out world's H/P/C/S under the production stack contract.

    ``players``: slate frame (id/pos/team/opp/game_id/salary; any
    ``actual`` column is ignored and replaced by the world values).
    ``candidate_rosters``: every generated roster as nine player ids.
    ``selected_indices``: positions of the selected book inside the
    candidate list. ``world_values``: player id -> simulated score in the
    held-out world (every slate player must be present).
    """
    if not candidate_rosters:
        raise NullGapError("candidate pool is empty")
    selected_indices = [int(i) for i in selected_indices]
    if not selected_indices:
        raise NullGapError("selected book is empty")
    if not set(selected_indices) <= set(range(len(candidate_rosters))):
        raise NullGapError("selected index outside the candidate pool")

    frame = players.copy()
    frame["id"] = frame.id.astype(str)
    missing = set(frame.id) - set(map(str, world_values))
    if missing:
        raise NullGapError(
            f"world values missing for slate players: {sorted(missing)[:5]}")
    frame["actual"] = frame.id.map(
        {str(k): float(v) for k, v in world_values.items()})

    values = {str(k): float(v) for k, v in world_values.items()}
    candidate_scores = [
        _roster_sum(roster, values) for roster in candidate_rosters]
    c_score = max(candidate_scores)
    s_score = max(candidate_scores[i] for i in selected_indices)

    h_oracle = _solve_oracle(
        frame, qb_stack_min=QB_STACK_MIN, bring_back_min=BRING_BACK_MIN,
        min_salary=MIN_SALARY, salary_cap=SALARY_CAP)
    support = {str(pid) for roster in candidate_rosters for pid in roster}
    p_oracle = _solve_oracle(
        frame, allowed_ids=support,
        qb_stack_min=QB_STACK_MIN, bring_back_min=BRING_BACK_MIN,
        min_salary=MIN_SALARY, salary_cap=SALARY_CAP)
    h_score = float(h_oracle["actual_score"])
    p_score = float(p_oracle["actual_score"])
    if p_score < c_score - 1e-6:
        raise NullGapError(
            "support oracle below best candidate: oracle contract defect")
    return {
        "h": h_score,
        "p": p_score,
        "c": float(c_score),
        "s": float(s_score),
        "h_minus_p": h_score - p_score,
        "p_minus_c": p_score - float(c_score),
        "c_minus_s": float(c_score) - float(s_score),
        "support_size": len(support),
    }


def aggregate_null_floor(
    world_results: Sequence[dict],
    observed: Mapping[str, float] = OBSERVED_GAPS,
) -> dict:
    """Distribution of the self-law gaps plus the observed comparison.

    ``winnable`` per gap = observed − null median: the part of the
    observed gap NOT explained by order statistics under a perfect law.
    """
    if not world_results:
        raise NullGapError("no world results to aggregate")
    frame = pd.DataFrame(world_results)
    report: dict = {
        "protocol_id": PROTOCOL_ID,
        "n_worlds": int(len(frame)),
        "gaps": {},
        "uses_realized_outcomes": False,
        "fit_performed": False,
        "gate_decision": None,
    }
    for gap in ("h_minus_p", "p_minus_c", "c_minus_s"):
        series = frame[gap].astype(float)
        obs = float(observed[gap])
        report["gaps"][gap] = {
            "null_mean": float(series.mean()),
            "null_median": float(series.median()),
            "null_p05": float(series.quantile(0.05)),
            "null_p95": float(series.quantile(0.95)),
            "observed": obs,
            "winnable_vs_null_median": float(obs - series.median()),
            "fraction_null_at_or_above_observed": float(
                (series >= obs).mean()),
        }
    return report
