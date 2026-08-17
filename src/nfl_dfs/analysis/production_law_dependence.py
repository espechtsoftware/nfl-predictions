"""Decision layer for the exact production-law dependence remeasurement.

The underlying nine-cell estimators remain the frozen G0 implementation in
``final_served_dependence``.  This module only combines the five registered
production-multinomial blocks and the aligned 50,000-world aggregate under the
predeclared sparse-ledger premise rule.
"""

from __future__ import annotations

from collections.abc import Mapping
import math


VERSION = "production-law-dependence-remeasurement-v1"
REGISTERED_BLOCKS = ("R0", "R1", "R2", "R3", "R4")
PRIMARY_CELLS = {
    "qb_wr_under_coupled": ("qb_wr", -1),
    "multiplicity_ge3_over_coupled": ("multiplicity_ge3", 1),
}


def _cell(report: Mapping[str, object], name: str) -> Mapping[str, object]:
    cells = report.get("cells")
    if not isinstance(cells, Mapping) or not isinstance(cells.get(name), Mapping):
        raise ValueError(f"production-law dependence report lacks {name}")
    row = cells[name]
    if not isinstance(row.get("supported"), bool) or row.get("classification") not in {
        "unsupported", "equivalent", "material-miss", "inconclusive",
    }:
        raise ValueError(f"production-law dependence {name} contract differs")
    value = row.get("log_simulated_to_realized")
    if value is not None and (
        not isinstance(value, (int, float)) or not math.isfinite(float(value))
    ):
        raise ValueError(f"production-law dependence {name} gap is invalid")
    return row


def _directional_material(
    report: Mapping[str, object], cell: str, direction: int,
) -> bool:
    row = _cell(report, cell)
    value = row.get("log_simulated_to_realized")
    return bool(
        row["supported"]
        and row["classification"] == "material-miss"
        and value is not None
        and direction * float(value) > 0.0
    )


def _classifiable(report: Mapping[str, object], cell: str) -> bool:
    row = _cell(report, cell)
    return bool(
        row["supported"]
        and row["classification"] in {"equivalent", "material-miss"}
    )


def aggregate_remeasurement(
    blocks: Mapping[str, Mapping[str, object]],
    aggregate: Mapping[str, object],
) -> dict[str, object]:
    """Apply the frozen two-mechanism, three-of-five premise decision."""
    if tuple(sorted(blocks)) != REGISTERED_BLOCKS:
        raise ValueError("production-law dependence requires exact R0--R4")
    for name, report in [*blocks.items(), ("aggregate", aggregate)]:
        population = report.get("population")
        if not isinstance(population, Mapping):
            raise ValueError(f"production-law dependence {name} population differs")
        expected_worlds = 50_000 if name == "aggregate" else 10_000
        if population.get("n_sims") != expected_worlds or \
                population.get("slates") != 54:
            raise ValueError(f"production-law dependence {name} world grid differs")
        for cell, _direction in PRIMARY_CELLS.values():
            _cell(report, cell)
        # >=4 remains mandatory reporting even though it cannot gate.
        _cell(report, "multiplicity_ge4")

    mechanisms: dict[str, dict[str, object]] = {}
    for mechanism, (cell, direction) in PRIMARY_CELLS.items():
        block_success = {
            name: _directional_material(blocks[name], cell, direction)
            for name in REGISTERED_BLOCKS
        }
        block_classifiable = {
            name: _classifiable(blocks[name], cell)
            for name in REGISTERED_BLOCKS
        }
        aggregate_success = _directional_material(aggregate, cell, direction)
        success_count = sum(block_success.values())
        classifiable_count = sum(block_classifiable.values())
        clears = aggregate_success and success_count >= 3
        mechanisms[mechanism] = {
            "cell": cell,
            "required_gap_sign": "negative" if direction < 0 else "positive",
            "aggregate_directional_material_miss": aggregate_success,
            "block_directional_material_miss": block_success,
            "directional_material_blocks": success_count,
            "block_classifiable": block_classifiable,
            "classifiable_blocks": classifiable_count,
            "requires_at_least_blocks": 3,
            "clears": clears,
        }

    cleared = sum(bool(value["clears"]) for value in mechanisms.values())
    classifiable = all(
        _classifiable(aggregate, str(value["cell"]))
        and int(value["classifiable_blocks"]) >= 3
        for value in mechanisms.values()
    )
    if cleared == 2:
        disposition = (
            "production-law-shape-reproduced-ledger-prototype-licensed"
        )
    elif cleared == 1:
        disposition = "partial-production-law-shape-requires-reframe"
    elif not classifiable:
        disposition = "production-law-dependence-inconclusive"
    else:
        disposition = (
            "production-law-shape-not-reproduced-ledger-dropped-or-reframed"
        )

    conditions = {
        "aggregate_qb_wr_under_coupled": mechanisms[
            "qb_wr_under_coupled"
        ]["aggregate_directional_material_miss"],
        "qb_wr_under_coupled_in_at_least_three_blocks": mechanisms[
            "qb_wr_under_coupled"
        ]["directional_material_blocks"] >= 3,
        "aggregate_multiplicity_ge3_over_coupled": mechanisms[
            "multiplicity_ge3_over_coupled"
        ]["aggregate_directional_material_miss"],
        "multiplicity_ge3_over_coupled_in_at_least_three_blocks": mechanisms[
            "multiplicity_ge3_over_coupled"
        ]["directional_material_blocks"] >= 3,
    }
    licensed = all(bool(value) for value in conditions.values())
    if licensed != (disposition.endswith("prototype-licensed")):
        raise AssertionError("production-law dependence disposition is inconsistent")
    return {
        "version": VERSION,
        "uses_realized_outcomes": True,
        "candidate_or_lineup_scores_read": False,
        "production_change_licensed": False,
        "exact80_scoring_licensed": False,
        "sparse_ledger_prototype_licensed": licensed,
        "blocks_are_independent_historical_replications": False,
        "mandatory_diagnostic_non_gating_cells": ["multiplicity_ge4"],
        "mechanisms": mechanisms,
        "gate": {
            "conditions": conditions,
            "passes": licensed,
            "disposition": disposition,
        },
        "blocks": {name: blocks[name] for name in REGISTERED_BLOCKS},
        "aggregate": aggregate,
    }


__all__ = [
    "PRIMARY_CELLS", "REGISTERED_BLOCKS", "VERSION",
    "aggregate_remeasurement",
]
