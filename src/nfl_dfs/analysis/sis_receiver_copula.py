"""Frozen calibration selection and held-out gate for SIS receiver copula."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


STRENGTH_GRID = (0.0, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00)
FLOAT_TOLERANCE = 1e-12
REQUIRED_RELATIONSHIPS = ("QB_WR", "QB_TE", "WR_WR", "RB_RB")
REQUIRED_G0_CELLS = ("qb_wr", "qb_te", "wr_wr", "rb_rb")
MULTIPLICITY_CELLS = (
    "multiplicity_ge2", "multiplicity_ge3", "multiplicity_ge4",
)


def select_calibration_grid(grid: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the frozen 2022 lexicographic selection without held-out data."""
    if {float(row.get("strength", np.nan)) for row in grid} != set(STRENGTH_GRID):
        raise ValueError("receiver-copula calibration grid differs")
    eligible = [row for row in grid if row.get("required_support") is True]
    if not eligible:
        raise ValueError("receiver-copula calibration has no supported cell")

    def narrow(rows: list[dict], key: str) -> list[dict]:
        values = [float(row[key]) for row in rows]
        if not np.isfinite(values).all():
            raise ValueError(f"receiver-copula calibration {key} is nonfinite")
        best = min(values)
        return [
            row for row in rows
            if float(row[key]) <= best + FLOAT_TOLERANCE
        ]

    tied = narrow(eligible, "registered_absolute_log_error_sum")
    tied = narrow(tied, "joint_q90_brier")
    tied = narrow(tied, "variogram_p0_5")
    return min(tied, key=lambda row: float(row["strength"]))


def _absolute_log_error(row: dict) -> float:
    if not row.get("supported"):
        raise ValueError("receiver-copula required score cell is unsupported")
    value = row.get("log_simulated_to_realized")
    if value is None or not np.isfinite(float(value)):
        raise ValueError("receiver-copula required score cell is nonfinite")
    return abs(float(value))


def _g0_errors(score: dict) -> dict[str, float]:
    return {
        name: _absolute_log_error(row)
        for name, row in score["g0"]["cells"].items()
        if row.get("supported")
    }


def _g1_errors(score: dict) -> dict[str, float]:
    return {
        name: _absolute_log_error(row)
        for name, row in score["broad_relationships"].items()
        if row.get("supported")
    }


def _unchanged_failures(control: Any, treatment: Any, path: str) -> list[str]:
    if isinstance(control, dict):
        if not isinstance(treatment, dict) or set(control) != set(treatment):
            return [f"{path}:structure"]
        failures: list[str] = []
        for key in sorted(control):
            failures.extend(_unchanged_failures(
                control[key], treatment[key], f"{path}.{key}"
            ))
        return failures
    if isinstance(control, list):
        if not isinstance(treatment, list) or len(control) != len(treatment):
            return [f"{path}:structure"]
        failures = []
        for index, (left, right) in enumerate(zip(control, treatment, strict=True)):
            failures.extend(_unchanged_failures(
                left, right, f"{path}[{index}]"
            ))
        return failures
    if isinstance(control, bool) or control is None or isinstance(control, str):
        return [] if type(control) is type(treatment) and control == treatment else [path]
    if isinstance(control, (int, float)) and not isinstance(control, bool):
        if not isinstance(treatment, (int, float)) or isinstance(treatment, bool):
            return [f"{path}:type"]
        left, right = float(control), float(treatment)
        if math.isnan(left) or math.isnan(right):
            return [] if math.isnan(left) and math.isnan(right) else [path]
        return [] if abs(left - right) <= FLOAT_TOLERANCE else [path]
    return [] if type(control) is type(treatment) and control == treatment else [path]


def multiplicity_diagnostic(control: dict, treatment: dict) -> dict:
    output = {}
    for name in MULTIPLICITY_CELLS:
        left = control["g0"]["cells"][name]
        right = treatment["g0"]["cells"][name]
        if not math.isclose(
            float(left["realized_estimate"]),
            float(right["realized_estimate"]),
            rel_tol=0.0, abs_tol=FLOAT_TOLERANCE,
        ):
            raise ValueError(f"receiver-copula {name} realized reference changed")
        supported = bool(left.get("supported"))
        output[name] = {
            "mandatory_report": True,
            "supported": supported,
            "gated": supported,
            "control_absolute_log_error": (
                _absolute_log_error(left) if supported else None
            ),
            "treatment_absolute_log_error": (
                _absolute_log_error(right) if supported else None
            ),
            "realized_estimate": float(left["realized_estimate"]),
            "control_simulated_estimate": float(left["simulated_estimate"]),
            "treatment_simulated_estimate": float(right["simulated_estimate"]),
            "support": left.get("support"),
        }
    return output


def gate_decision(
    control: dict,
    treatment: dict,
    *,
    invariants_pass: bool,
    selected_strength: float,
    treatment_audit: dict,
) -> dict:
    """Apply the frozen two-sided, no-regression held-out dependence gate."""
    try:
        control_g0 = _g0_errors(control)
        treatment_g0 = _g0_errors(treatment)
        control_g1 = _g1_errors(control)
        treatment_g1 = _g1_errors(treatment)
        if set(control_g0) != set(treatment_g0):
            raise ValueError("G0 supported cell set changed")
        if set(control_g1) != set(treatment_g1):
            raise ValueError("G1 supported cell set changed")
        if not set(REQUIRED_G0_CELLS).issubset(control_g0):
            raise ValueError("required G0 teammate support is incomplete")
        if not set(REQUIRED_RELATIONSHIPS).issubset(control_g1):
            raise ValueError("required G1 teammate support is incomplete")
        if not {"multiplicity_ge2", "multiplicity_ge3"}.issubset(control_g0):
            raise ValueError("required multiplicity support is incomplete")
        multiplicity = multiplicity_diagnostic(control, treatment)
    except (KeyError, TypeError, ValueError) as exc:
        support_failure = str(exc)
        control_g0 = treatment_g0 = control_g1 = treatment_g1 = {}
        multiplicity = {}
    else:
        support_failure = None

    unchanged_failures: list[str] = []
    if support_failure is None:
        for relationship in ("QB_TE", "RB_RB"):
            unchanged_failures.extend(_unchanged_failures(
                control["scorecard"][relationship],
                treatment["scorecard"][relationship],
                f"scorecard.{relationship}",
            ))
            unchanged_failures.extend(_unchanged_failures(
                control["broad_relationships"][relationship],
                treatment["broad_relationships"][relationship],
                f"broad.{relationship}",
            ))
        for cell in ("qb_te", "rb_rb"):
            unchanged_failures.extend(_unchanged_failures(
                control["g0"]["cells"][cell],
                treatment["g0"]["cells"][cell],
                f"g0.{cell}",
            ))

    cp = control.get("primary", {})
    tp = treatment.get("primary", {})
    g0_not_worse = bool(
        support_failure is None
        and all(
            treatment_g0[name] <= value + FLOAT_TOLERANCE
            for name, value in control_g0.items()
        )
    )
    g1_not_worse = bool(
        support_failure is None
        and all(
            treatment_g1[name] <= value + FLOAT_TOLERANCE
            for name, value in control_g1.items()
        )
    )
    gates = {
        "all_invariants_pass": bool(invariants_pass),
        "required_cells_supported": support_failure is None,
        "selected_strength_is_active": float(selected_strength) > 0,
        "eligible_wr_ranks_change": int(treatment_audit.get("changed_rows", 0)) > 0,
        "joint_q90_brier_strictly_improves": (
            float(tp.get("joint_q90_brier", np.inf))
            < float(cp.get("joint_q90_brier", -np.inf))
        ),
        "variogram_strictly_improves": (
            float(tp.get("variogram_p0_5", np.inf))
            < float(cp.get("variogram_p0_5", -np.inf))
        ),
        "g1_qb_wr_strictly_improves": bool(
            support_failure is None
            and treatment_g1["QB_WR"] < control_g1["QB_WR"]
        ),
        "g0_qb_wr_strictly_improves": bool(
            support_failure is None
            and treatment_g0["qb_wr"] < control_g0["qb_wr"]
        ),
        "g1_wr_wr_does_not_worsen": bool(
            support_failure is None
            and treatment_g1["WR_WR"]
            <= control_g1["WR_WR"] + FLOAT_TOLERANCE
        ),
        "g0_wr_wr_does_not_worsen": bool(
            support_failure is None
            and treatment_g0["wr_wr"]
            <= control_g0["wr_wr"] + FLOAT_TOLERANCE
        ),
        "qb_te_and_rb_rb_remain_unchanged": not unchanged_failures,
        "all_supported_g0_cells_do_not_worsen": g0_not_worse,
        "all_supported_g1_relationships_do_not_worsen": g1_not_worse,
        "g0_absolute_log_error_sum_strictly_improves": (
            float(tp.get("g0_absolute_log_error_sum", np.inf))
            < float(cp.get("g0_absolute_log_error_sum", -np.inf))
        ),
        "g1_weighted_absolute_log_error_sum_strictly_improves": (
            float(tp.get("g1_weighted_absolute_log_error_sum", np.inf))
            < float(cp.get("g1_weighted_absolute_log_error_sum", -np.inf))
        ),
    }
    if not invariants_pass or support_failure is not None:
        disposition = "sis-receiver-copula-invalid-or-inconclusive"
    elif all(gates.values()):
        disposition = "sis-receiver-copula-gate-passes"
    else:
        disposition = "sis-receiver-copula-gate-fails"
    return {
        "disposition": disposition,
        "prospective_2026_shadow_licensed": (
            disposition == "sis-receiver-copula-gate-passes"
        ),
        "retrospective_exact80_licensed": False,
        "gate": {**gates, "passes": all(gates.values())},
        "support_failure": support_failure,
        "unchanged_negative_control_failures": unchanged_failures,
        "absolute_log_errors": {
            "control": {"g0": control_g0, "g1": control_g1},
            "treatment": {"g0": treatment_g0, "g1": treatment_g1},
        },
        "multiplicity": multiplicity,
    }


__all__ = [
    "FLOAT_TOLERANCE", "MULTIPLICITY_CELLS", "REQUIRED_G0_CELLS",
    "REQUIRED_RELATIONSHIPS", "STRENGTH_GRID", "gate_decision",
    "multiplicity_diagnostic", "select_calibration_grid",
]
