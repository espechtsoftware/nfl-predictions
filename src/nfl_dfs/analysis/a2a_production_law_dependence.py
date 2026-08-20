"""Pure decision layer for the one-shot A2a dependence remeasurement.

The intervention itself remains byte-for-byte in
``nfl_dfs.research.a2a_rank_factor_split``.  This module contains only the
preregistered realized targets, coverage accounting, and the exhaustive
law-shape disposition.  It has no storage, warehouse, lineup, optimizer, or
scoring imports.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

import pandas as pd


VERSION = "a2a-production-law-dependence-remeasurement-v1"
REGISTERED_BLOCKS = ("R0", "R1", "R2", "R3", "R4")
REGISTERED_CELLS = (
    "multiplicity_ge2",
    "multiplicity_ge3",
    "multiplicity_ge4",
    "qb_wr",
    "qb_te",
    "qb_rb",
    "wr_wr",
    "rb_rb",
    "te_te",
)

# Exact JSON values from the immutable production-law control report
# (SHA-256 5b92339b2a9118727d41a8f4b91e982c5478318029c216652d66b7cdd113e696).
# The remeasurement must reproduce these realized estimands exactly.  They are
# targets, not values that may be refit after the treatment is read.
REALIZED_TARGETS = {
    "multiplicity_ge2": 0.8209974371834499,
    "multiplicity_ge3": 0.9970062534524585,
    "multiplicity_ge4": 1.0884346795425752,
    "qb_wr": 3.3392156862745095,
    "qb_te": 1.8521140513621719,
    "qb_rb": 0.9106858054226474,
    "wr_wr": 0.9905119347301017,
    "rb_rb": 0.49414928618430465,
    "te_te": 0.42028985507246375,
}
EQUIVALENCE_BANDS = {
    "multiplicity_ge2": 0.09531017980432493,
    "multiplicity_ge3": 0.13976194237515863,
    "multiplicity_ge4": 0.22314355131420976,
    "qb_wr": 0.13976194237515863,
    "qb_te": 0.13976194237515863,
    "qb_rb": 0.13976194237515863,
    "wr_wr": 0.13976194237515863,
    "rb_rb": 0.13976194237515863,
    "te_te": 0.13976194237515863,
}
CONTROL_POINT_GAPS = {
    "multiplicity_ge2": 0.2586212580069155,
    "multiplicity_ge3": 0.7436982933488568,
    "multiplicity_ge4": 1.6476273247486672,
    "qb_wr": -0.2611202585756975,
    "qb_te": 0.23917750548480823,
    "qb_rb": 1.166946980838297,
    "wr_wr": 0.6912856504946393,
    "rb_rb": 1.4883141634549988,
    "te_te": 1.3425354176099444,
}
CONTROL_CLASSIFICATIONS = {
    "multiplicity_ge2": "material-miss",
    "multiplicity_ge3": "material-miss",
    "multiplicity_ge4": "material-miss",
    "qb_wr": "material-miss",
    "qb_te": "inconclusive",
    "qb_rb": "material-miss",
    "wr_wr": "material-miss",
    "rb_rb": "material-miss",
    "te_te": "material-miss",
}

# RB and TE rows receive only generic-factor attenuation.  They have no
# pair-specific re-coupling term in A2a; the report and disposition must never
# imply otherwise.
MECHANISM_ROLES = {
    "qb_wr": "targeted-one-hot-qb-wr-recoupling-plus-generic-attenuation",
    "multiplicity_ge2": "generic-team-factor-attenuation",
    "multiplicity_ge3": "generic-team-factor-attenuation",
    "multiplicity_ge4": "generic-team-factor-attenuation",
    "wr_wr": "generic-team-factor-attenuation-plus-competitive-wr-allocation",
    "qb_rb": "attenuation-only-no-qb-rb-recoupling",
    "qb_te": "attenuation-only-no-qb-te-recoupling",
    "rb_rb": "attenuation-only-no-rb-rb-recoupling",
    "te_te": "attenuation-only-no-te-te-recoupling",
}

_VALID_CLASSIFICATIONS = {
    "unsupported", "equivalent", "material-miss", "inconclusive",
}
_ACCOUNTING_FIELDS = {
    "season", "week", "player_id", "position", "team", "mean_projection",
}


def support_accounting(
    catalog_rows: pd.DataFrame | Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    """Report mutually exclusive A2a coverage and skip reasons.

    This is accounting only.  It neither selects a QB nor changes which rows
    the frozen transform touches.
    """
    frame = (
        catalog_rows.copy()
        if isinstance(catalog_rows, pd.DataFrame)
        else pd.DataFrame(list(catalog_rows))
    )
    if set(frame.columns) != _ACCOUNTING_FIELDS or frame.empty:
        raise ValueError("A2a coverage catalog schema differs")
    if frame[["season", "week", "player_id", "position", "team"]].isna().any().any():
        raise ValueError("A2a coverage catalog identity contains nulls")
    means = pd.to_numeric(frame.mean_projection, errors="raise")
    if not means.map(math.isfinite).all():
        raise ValueError("A2a coverage catalog mean is nonfinite")
    frame = frame.assign(
        position=frame.position.astype(str).str.upper(),
        team=frame.team.astype(str).str.upper(),
        mean_projection=means.astype(float),
    )
    eligible = frame[
        frame.position.isin({"QB", "RB", "WR", "TE"})
        & frame.mean_projection.ge(4.0)
    ]
    if eligible.empty or eligible.duplicated(
        ["season", "week", "player_id"]
    ).any():
        raise ValueError("A2a coverage population is empty or duplicated")

    reasons = {
        "zero_eligible_qb": 0,
        "multiple_eligible_qbs": 0,
        "fewer_than_two_eligible_wrs": 0,
    }
    covered_groups = 0
    covered_qb_anchors = 0
    directly_transformed_non_qb_rows = 0
    skipped_eligible_rows = 0
    total_groups = 0
    for _key, group in eligible.groupby(["season", "week", "team"], sort=True):
        total_groups += 1
        qb_count = int(group.position.eq("QB").sum())
        wr_count = int(group.position.eq("WR").sum())
        if qb_count == 0:
            reasons["zero_eligible_qb"] += 1
            skipped_eligible_rows += len(group)
        elif qb_count > 1:
            reasons["multiple_eligible_qbs"] += 1
            skipped_eligible_rows += len(group)
        elif wr_count < 2:
            reasons["fewer_than_two_eligible_wrs"] += 1
            skipped_eligible_rows += len(group)
        else:
            covered_groups += 1
            covered_qb_anchors += 1
            directly_transformed_non_qb_rows += len(group) - 1

    skipped_groups = sum(reasons.values())
    eligible_rows = int(len(eligible))
    if covered_groups + skipped_groups != total_groups or \
            covered_qb_anchors + directly_transformed_non_qb_rows \
            + skipped_eligible_rows != eligible_rows:
        raise AssertionError("A2a coverage accounting does not reconcile")
    return {
        "reporting_only_not_a_mechanism_or_gate": True,
        "eligible_team_slate_groups": total_groups,
        "covered_groups": covered_groups,
        "skipped_groups": skipped_groups,
        "skipped_group_reasons": reasons,
        "covered_group_fraction": covered_groups / total_groups,
        "eligible_rows": eligible_rows,
        "covered_qb_anchor_rows_unchanged": covered_qb_anchors,
        "directly_transformed_non_qb_rows": directly_transformed_non_qb_rows,
        "skipped_group_eligible_rows_unchanged": skipped_eligible_rows,
        "direct_row_transform_fraction": (
            directly_transformed_non_qb_rows / eligible_rows
        ),
    }


def _report_cells(
    report: Mapping[str, object], *, label: str, expected_worlds: int,
) -> dict[str, Mapping[str, object]]:
    population = report.get("population")
    cells = report.get("cells")
    if not isinstance(population, Mapping) or not isinstance(cells, Mapping):
        raise ValueError(f"A2a remeasurement {label} report schema differs")
    if population.get("rows") != 9_469 or population.get("slates") != 54 or \
            population.get("n_sims") != expected_worlds or \
            set(cells) != set(REGISTERED_CELLS):
        raise ValueError(f"A2a remeasurement {label} population differs")
    result: dict[str, Mapping[str, object]] = {}
    for cell in REGISTERED_CELLS:
        row = cells[cell]
        if not isinstance(row, Mapping) or \
                not isinstance(row.get("supported"), bool) or \
                row.get("classification") not in _VALID_CLASSIFICATIONS:
            raise ValueError(f"A2a remeasurement {label} {cell} contract differs")
        for field in ("realized_estimate", "equivalence_band_abs_log"):
            value = row.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or \
                    not math.isfinite(float(value)):
                raise ValueError(
                    f"A2a remeasurement {label} {cell} {field} is invalid"
                )
        if float(row["realized_estimate"]) != REALIZED_TARGETS[cell] or \
                float(row["equivalence_band_abs_log"]) != EQUIVALENCE_BANDS[cell]:
                raise ValueError(
                    f"A2a remeasurement {label} {cell} realized target differs"
                )
        optional_numeric = {}
        for field in (
            "simulated_estimate", "log_simulated_to_realized",
            "cluster_ci95_low", "cluster_ci95_high",
        ):
            value = row.get(field)
            if value is None:
                optional_numeric[field] = None
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or \
                    not math.isfinite(float(value)):
                raise ValueError(
                    f"A2a remeasurement {label} {cell} {field} is invalid"
                )
            else:
                optional_numeric[field] = float(value)

        point = optional_numeric["log_simulated_to_realized"]
        ci_low = optional_numeric["cluster_ci95_low"]
        ci_high = optional_numeric["cluster_ci95_high"]
        simulated = optional_numeric["simulated_estimate"]
        if simulated is not None and simulated < 0.0:
            raise ValueError(
                f"A2a remeasurement {label} {cell} simulated estimate is invalid"
            )
        if ci_low is not None and ci_high is not None and ci_low > ci_high:
            raise ValueError(
                f"A2a remeasurement {label} {cell} confidence interval differs"
            )
        band = EQUIVALENCE_BANDS[cell]
        supported = bool(row["supported"])
        if not supported or point is None or ci_low is None or ci_high is None:
            expected_classification = "unsupported"
        elif ci_low >= -band and ci_high <= band:
            expected_classification = "equivalent"
        elif abs(point) > band and (ci_low > 0.0 or ci_high < 0.0):
            expected_classification = "material-miss"
        else:
            expected_classification = "inconclusive"
        if row["classification"] != expected_classification:
            raise ValueError(
                f"A2a remeasurement {label} {cell} classification differs"
            )
        if point is not None and simulated is not None and simulated > 0.0:
            reproduced = math.log(simulated / REALIZED_TARGETS[cell])
            if not math.isclose(reproduced, point, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(
                    f"A2a remeasurement {label} {cell} log gap differs"
                )
        elif point is not None:
            raise ValueError(
                f"A2a remeasurement {label} {cell} log gap lacks an estimand"
            )
        elif supported and row["classification"] != "unsupported":
            raise ValueError(
                f"A2a remeasurement {label} {cell} supported estimand is absent"
            )
        result[cell] = row
    return result


def _same_side_improvement_or_equivalent(
    row: Mapping[str, object], cell: str,
) -> bool:
    if not bool(row["supported"]) or row["classification"] == "unsupported":
        return False
    if row["classification"] == "equivalent":
        return True
    gap = float(row["log_simulated_to_realized"])
    control = CONTROL_POINT_GAPS[cell]
    return abs(gap) < abs(control) and gap * control > 0.0


def _qb_wr_location(row: Mapping[str, object]) -> str:
    if not bool(row["supported"]) or row["classification"] == "unsupported":
        return "unsupported"
    gap = float(row["log_simulated_to_realized"])
    band = EQUIVALENCE_BANDS["qb_wr"]
    if gap > band:
        return "overshoot-above-realized-equivalence"
    if gap < -band:
        return "undershoot-below-realized-equivalence"
    if row["classification"] == "equivalent":
        return "equivalent"
    return "inside-point-band-but-uncertain"


def evaluate_remeasurement(
    blocks: Mapping[str, Mapping[str, object]],
    aggregate: Mapping[str, object],
) -> dict[str, Any]:
    """Apply the frozen A2a law-shape gate to treatment-only G0 reports."""
    if tuple(sorted(blocks)) != REGISTERED_BLOCKS:
        raise ValueError("A2a remeasurement requires exact R0--R4")
    block_cells = {
        block: _report_cells(blocks[block], label=block, expected_worlds=10_000)
        for block in REGISTERED_BLOCKS
    }
    aggregate_cells = _report_cells(
        aggregate, label="aggregate", expected_worlds=50_000,
    )

    all_supported = all(
        bool(row["supported"]) and row["classification"] != "unsupported"
        for cells in [*block_cells.values(), aggregate_cells]
        for row in cells.values()
    )
    qb_wr_location = _qb_wr_location(aggregate_cells["qb_wr"])
    qb_wr_equivalent_blocks = sum(
        cells["qb_wr"]["classification"] == "equivalent"
        for cells in block_cells.values()
    )
    ge3_equivalent_blocks = sum(
        cells["multiplicity_ge3"]["classification"] == "equivalent"
        for cells in block_cells.values()
    )
    per_cell_guard = {
        cell: _same_side_improvement_or_equivalent(aggregate_cells[cell], cell)
        for cell in REGISTERED_CELLS
    }
    targeted_conditions = {
        "aggregate_qb_wr_equivalent": qb_wr_location == "equivalent",
        "qb_wr_equivalent_in_at_least_three_blocks": (
            qb_wr_equivalent_blocks >= 3
        ),
    }
    generic_conditions = {
        "aggregate_multiplicity_ge3_equivalent": (
            aggregate_cells["multiplicity_ge3"]["classification"] == "equivalent"
        ),
        "multiplicity_ge3_equivalent_in_at_least_three_blocks": (
            ge3_equivalent_blocks >= 3
        ),
        "every_registered_cell_equivalent_or_strictly_closer_without_crossing": (
            all(per_cell_guard.values())
        ),
        "qb_te_attenuation_only_guard": per_cell_guard["qb_te"],
        "qb_rb_attenuation_only_guard": per_cell_guard["qb_rb"],
        "rb_rb_attenuation_only_guard": per_cell_guard["rb_rb"],
        "te_te_attenuation_only_guard": per_cell_guard["te_te"],
    }
    conditions = {
        "all_registered_cells_supported": all_supported,
        **targeted_conditions,
        **generic_conditions,
    }
    passes = all(conditions.values())

    if not all_supported:
        disposition = "a2a-law-shape-inconclusive"
    elif qb_wr_location == "overshoot-above-realized-equivalence":
        disposition = "a2a-law-shape-miss-qb-wr-overshoot"
    elif not all(targeted_conditions.values()):
        disposition = "a2a-law-shape-miss-qb-wr-not-equivalent"
    elif not all(generic_conditions.values()):
        disposition = "a2a-law-shape-miss-attenuation-or-protected-cell"
    else:
        disposition = "a2a-law-shape-passes-single-stack-protocol-licensed"

    licenses = {
        "uses_realized_outcomes": True,
        "actual_outcomes_queried": True,
        "candidate_or_lineup_scores_read": False,
        "single_stack_protocol_licensed": passes,
        "single_stack_arm_licensed": False,
        "exact80_scoring_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }
    if passes != disposition.endswith("protocol-licensed") or \
            passes != licenses["single_stack_protocol_licensed"]:
        raise AssertionError("A2a remeasurement disposition is inconsistent")
    return {
        "version": VERSION,
        "passes": passes,
        "disposition": disposition,
        "conditions": conditions,
        "qb_wr_location": qb_wr_location,
        "qb_wr_equivalent_blocks": qb_wr_equivalent_blocks,
        "multiplicity_ge3_equivalent_blocks": ge3_equivalent_blocks,
        "aggregate_cell_guards": per_cell_guard,
        "mechanism_roles": dict(MECHANISM_ROLES),
        "licenses": licenses,
        "blocks_are_independent_historical_replications": False,
        "blocks": {block: blocks[block] for block in REGISTERED_BLOCKS},
        "aggregate": aggregate,
    }


__all__ = [
    "CONTROL_CLASSIFICATIONS",
    "CONTROL_POINT_GAPS",
    "EQUIVALENCE_BANDS",
    "MECHANISM_ROLES",
    "REALIZED_TARGETS",
    "REGISTERED_BLOCKS",
    "REGISTERED_CELLS",
    "VERSION",
    "evaluate_remeasurement",
    "support_accounting",
]
