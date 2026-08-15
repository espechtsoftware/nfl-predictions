"""Outcome-free cardinality-aware selectors for small Classic DFS books."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


ENTRY_TARGET_LINES = {1: 230.0, 3: 230.0, 20: 210.0, 40: 200.0}
REPORT_LINES = (194.0, 200.0, 210.0, 230.0)


def _validate_totals(
    candidate_totals: np.ndarray,
    *,
    world_blocks: int,
) -> tuple[np.ndarray, int]:
    totals = np.asarray(candidate_totals, dtype=float)
    if (
        totals.ndim != 2
        or not len(totals)
        or world_blocks != 5
        or totals.shape[1] % world_blocks
        or not np.isfinite(totals).all()
    ):
        raise ValueError("exact-N candidate worlds are invalid")
    return totals, totals.shape[1] // world_blocks


def select_cardinality_tail_book(
    candidate_totals: np.ndarray,
    n_entries: int,
    *,
    world_blocks: int = 5,
) -> list[int]:
    """Select exactly N with the frozen cardinality-specific robust tail law."""
    if n_entries not in ENTRY_TARGET_LINES:
        raise ValueError("exact-N selector supports only 1/3/20/40 entries")
    totals, block_worlds = _validate_totals(
        candidate_totals, world_blocks=world_blocks,
    )
    if n_entries > len(totals):
        raise ValueError("exact-N candidate pool is smaller than requested book")
    primary_line = ENTRY_TARGET_LINES[n_entries]
    primary = totals >= primary_line
    clears_210 = totals >= 210.0
    clears_194 = totals >= 194.0
    block_slices = tuple(
        slice(block * block_worlds, (block + 1) * block_worlds)
        for block in range(world_blocks)
    )
    individual_primary = np.asarray([
        primary[:, block_slice].mean(axis=1) for block_slice in block_slices
    ])
    individual_210 = np.asarray([
        clears_210[:, block_slice].mean(axis=1) for block_slice in block_slices
    ])
    individual_194 = np.asarray([
        clears_194[:, block_slice].mean(axis=1) for block_slice in block_slices
    ])
    covered = [np.zeros(block_worlds, dtype=bool) for _ in block_slices]
    remaining = set(range(len(totals)))
    selected: list[int] = []
    while len(selected) < n_entries:
        def key(candidate: int) -> tuple[Any, ...]:
            marginal = tuple(
                int(np.count_nonzero(
                    primary[candidate, block_slice] & ~covered[block]
                ))
                for block, block_slice in enumerate(block_slices)
            )
            return (
                min(marginal), sum(marginal),
                float(individual_primary[:, candidate].min()),
                float(individual_primary[:, candidate].mean()),
                float(individual_210[:, candidate].min()),
                float(individual_210[:, candidate].mean()),
                float(individual_194[:, candidate].min()),
                float(individual_194[:, candidate].mean()),
                float(totals[candidate].mean()),
                -candidate,
            )

        chosen = max(remaining, key=key)
        selected.append(chosen)
        remaining.remove(chosen)
        for block, block_slice in enumerate(block_slices):
            covered[block] |= primary[chosen, block_slice]
    return selected


def book_scorefree_metrics(
    totals: np.ndarray,
    selected: Sequence[int],
    *,
    world_blocks: int = 5,
) -> dict[str, Any]:
    """Report the registered score-free metrics for one ordered book."""
    totals, block_worlds = _validate_totals(
        totals, world_blocks=world_blocks,
    )
    indices = np.asarray(selected, dtype=int)
    if (
        indices.ndim != 1
        or not len(indices)
        or len(set(indices.tolist())) != len(indices)
        or int(indices.min()) < 0
        or int(indices.max()) >= len(totals)
    ):
        raise ValueError("exact-N selected book is invalid")
    chosen = totals[indices]
    metrics = {}
    for line in REPORT_LINES:
        clears = chosen >= line
        per_block = [
            float(np.any(
                clears[:, block * block_worlds:(block + 1) * block_worlds],
                axis=0,
            ).mean())
            for block in range(5)
        ]
        metrics[str(int(line))] = {
            "aggregate_coverage": float(np.any(clears, axis=0).mean()),
            "per_block_coverage": per_block,
            "maximum_individual_probability": float(
                clears.mean(axis=1).max(initial=0.0)
            ),
        }
    return {
        "selected": [int(value) for value in selected],
        "entries": len(selected),
        "simulated_mean_average": float(chosen.mean(axis=1).mean()),
        "tail": metrics,
    }


def exact_n_scorefree_diagnostic(
    candidate_totals: np.ndarray,
    incumbent_order: Sequence[int],
    n_entries: int,
    *,
    world_blocks: int = 5,
) -> dict[str, Any]:
    """Compare one frozen exact-N treatment with the incumbent prefix."""
    totals, block_worlds = _validate_totals(
        candidate_totals, world_blocks=world_blocks,
    )
    incumbent = [int(value) for value in incumbent_order]
    if len(incumbent) < 80 or len(set(incumbent[:80])) != 80:
        raise ValueError("exact-N incumbent order lacks 80 unique entries")
    if min(incumbent[:80]) < 0 or max(incumbent[:80]) >= len(totals):
        raise ValueError("exact-N incumbent order is outside candidate pool")
    treatment = select_cardinality_tail_book(
        totals, n_entries, world_blocks=world_blocks,
    )
    control = incumbent[:n_entries]
    control_metrics = book_scorefree_metrics(
        totals, control, world_blocks=world_blocks,
    )
    treatment_metrics = book_scorefree_metrics(
        totals, treatment, world_blocks=world_blocks,
    )
    target = str(int(ENTRY_TARGET_LINES[n_entries]))
    target_control = control_metrics["tail"][target]
    target_treatment = treatment_metrics["tail"][target]
    control_194 = control_metrics["tail"]["194"]["aggregate_coverage"]
    treatment_194 = treatment_metrics["tail"]["194"]["aggregate_coverage"]
    conditions = {
        "exact_n_unique": len(treatment) == n_entries
        and len(set(treatment)) == n_entries,
        "primary_aggregate_improves": (
            target_treatment["aggregate_coverage"]
            > target_control["aggregate_coverage"]
        ),
        "primary_improves_at_least_three_blocks": sum(
            treatment_value > control_value
            for treatment_value, control_value in zip(
                target_treatment["per_block_coverage"],
                target_control["per_block_coverage"],
                strict=True,
            )
        ) >= 3,
        "p194_retains_at_least_90pct": (
            treatment_194 >= 0.90 * control_194
        ),
    }
    return {
        "version": "exact-n-scorefree-v1",
        "uses_realized_outcomes": False,
        "n_entries": int(n_entries),
        "primary_target": float(ENTRY_TARGET_LINES[n_entries]),
        "control": control_metrics,
        "treatment": treatment_metrics,
        "identity_overlap": len(set(control) & set(treatment)),
        "conditions": conditions,
        "passes_scorefree_falsifier": bool(all(conditions.values())),
        "consequence": (
            "score-free prospective-shadow admission only; cannot promote "
            "or score a historical money lineup"
        ),
    }


__all__ = [
    "ENTRY_TARGET_LINES", "REPORT_LINES", "book_scorefree_metrics",
    "exact_n_scorefree_diagnostic", "select_cardinality_tail_book",
]
