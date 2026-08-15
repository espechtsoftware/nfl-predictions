"""Frozen calibration selection and held-out gate for SIS receiver copula."""

from __future__ import annotations

from hashlib import sha256
import json
import math
import os
import re
from typing import Any

import numpy as np
import pandas as pd


STRENGTH_GRID = (0.0, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00)
FLOAT_TOLERANCE = 1e-12
REQUIRED_RELATIONSHIPS = ("QB_WR", "QB_TE", "WR_WR", "RB_RB")
REQUIRED_G0_CELLS = ("qb_wr", "qb_te", "wr_wr", "rb_rb")
MULTIPLICITY_CELLS = (
    "multiplicity_ge2", "multiplicity_ge3", "multiplicity_ge4",
)
CALIBRATION_G1_CELLS = ("QB_WR", "WR_WR")
CALIBRATION_G0_CELLS = (
    "qb_wr", "wr_wr", "multiplicity_ge2", "multiplicity_ge3",
)
REFERENCE_META_PREFIX = "SIS_RECEIVER_COPULA_REFERENCE_META="
REFERENCE_CHUNK_PREFIX = "SIS_RECEIVER_COPULA_REFERENCE_CHUNK="
REFERENCE_VERSION = "sis-receiver-copula-reference-v1"
REFERENCE_HISTORICAL_PANEL = "20260811-pitclean-e80-k1-role12union-a12ab31"
REFERENCE_EVALUATION_PANEL = "20260812-pitclean-e80-selected-tabpfn-active-v2"
REFERENCE_CACHE_TABLE = "tabpfn_active_label_treatment_v2"
REFERENCE_DIRICHLET_K = "28.154043586960896"
REFERENCE_ROWS = 7_848
REFERENCE_SLATES = 54
REFERENCE_WORLDS = 10_000
REFERENCE_POSITION_SCHEDULE = {
    2023: {"factors": {"QB": 0.965, "RB": 0.99, "TE": 0.945, "WR": 1.03}},
    2024: {"factors": {"QB": 0.905, "RB": 0.97, "TE": 0.95, "WR": 1.06}},
    2025: {"factors": {"QB": 0.925, "RB": 0.96, "TE": 0.94, "WR": 1.04}},
}
REFERENCE_FRAME_COLUMNS = (
    "season", "week", "gsis_id", "position", "team", "opp", "game_id",
    "actual", "mean_projection",
)


def _canonical_sha256(value: Any) -> str:
    content = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()
    return sha256(content).hexdigest()


def _runtime_identity() -> dict[str, str]:
    run_id = os.environ.get("SIS_RECEIVER_COPULA_REFERENCE_RUN_ID", "").strip()
    code_sha = os.environ.get("SIS_RECEIVER_COPULA_REFERENCE_CODE_SHA", "").strip()
    if not run_id or not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise ValueError("receiver-copula immutable reference identity is missing")
    return {"run_id": run_id, "code_sha": code_sha}


def _draw_sha256(draws: np.ndarray) -> str:
    values = np.asarray(draws)
    if not values.flags.c_contiguous:
        values = np.ascontiguousarray(values)
    return sha256(memoryview(values).cast("B")).hexdigest()


def _frame_sha256(frame: pd.DataFrame) -> str:
    content = frame[list(REFERENCE_FRAME_COLUMNS)].to_csv(
        index=False, lineterminator="\n", float_format="%.17g",
    ).encode()
    return sha256(content).hexdigest()


def _emit_reference(report: dict[str, Any]) -> None:
    from . import g1_archetype_topology as g1

    meta, chunks = g1.encode_report_transport(report)
    print(REFERENCE_META_PREFIX + json.dumps(meta, sort_keys=True), flush=True)
    for index, chunk in enumerate(chunks):
        print(
            f"{REFERENCE_CHUNK_PREFIX}{index}/{len(chunks)}:{chunk}",
            flush=True,
        )


def reference_invariants(
    frame: pd.DataFrame,
    draws: np.ndarray,
    terminal: dict[str, Any],
    repeat_frame: pd.DataFrame,
    repeat_draws: np.ndarray,
    repeat_terminal: dict[str, Any],
    *,
    expected_rows: int = REFERENCE_ROWS,
    expected_slates: int = REFERENCE_SLATES,
    expected_worlds: int = REFERENCE_WORLDS,
) -> dict[str, Any]:
    """Verify that a fresh repaired-path reference is exact and complete."""
    missing_columns = sorted(set(REFERENCE_FRAME_COLUMNS) - set(frame.columns))
    repeat_missing = sorted(
        set(REFERENCE_FRAME_COLUMNS) - set(repeat_frame.columns)
    )
    exact_frame = bool(
        not missing_columns
        and not repeat_missing
        and frame[list(REFERENCE_FRAME_COLUMNS)].equals(
            repeat_frame[list(REFERENCE_FRAME_COLUMNS)]
        )
    )
    keys = ["season", "week", "gsis_id"]
    key_unique = bool(not missing_columns and not frame.duplicated(keys).any())
    metadata_complete = bool(
        not missing_columns
        and not frame[["team", "opp", "game_id"]].isna().any().any()
    )
    finite_outcomes_and_means = bool(
        not missing_columns
        and np.isfinite(frame[["actual", "mean_projection"]].to_numpy(float)).all()
    )
    slate_count = (
        int(frame[["season", "week"]].drop_duplicates().shape[0])
        if not missing_columns else -1
    )
    draw_shape = tuple(np.asarray(draws).shape)
    repeat_draw_shape = tuple(np.asarray(repeat_draws).shape)
    complete_population = bool(
        len(frame) == expected_rows
        and slate_count == expected_slates
        and draw_shape == (expected_rows, expected_worlds)
        and repeat_draw_shape == draw_shape
        and set(frame["season"].astype(int)) == {2023, 2024, 2025}
    ) if not missing_columns else False
    finite_draws = bool(
        np.isfinite(np.asarray(draws)).all()
        and np.isfinite(np.asarray(repeat_draws)).all()
    )
    draws_bit_exact = bool(np.array_equal(draws, repeat_draws))
    terminal_exact = terminal == repeat_terminal
    expected_usage = {
        "mode": "data-fitted-dirichlet",
        "game_sim_usage": "dirichlet",
        "k": REFERENCE_DIRICHLET_K,
    }
    terminal_contract = bool(
        terminal.get("cache_table") == REFERENCE_CACHE_TABLE
        and terminal.get("cache_rows") == 52_307
        and terminal.get("usage_law") == expected_usage
        and terminal.get("schedule") == REFERENCE_POSITION_SCHEDULE
        and np.isfinite(float(terminal.get("maximum_mean_delta", np.nan)))
    )
    checks = {
        "required_frame_columns_present": not missing_columns and not repeat_missing,
        "frame_bit_exact_on_repeat": exact_frame,
        "player_keys_unique": key_unique,
        "game_metadata_complete": metadata_complete,
        "outcomes_and_means_finite": finite_outcomes_and_means,
        "complete_population": complete_population,
        "draws_finite": finite_draws,
        "draws_bit_exact_on_repeat": draws_bit_exact,
        "terminal_identity_exact_on_repeat": terminal_exact,
        "terminal_contract_exact": terminal_contract,
    }
    return {
        **checks,
        "passes": bool(all(checks.values())),
        "missing_frame_columns": missing_columns,
        "repeat_missing_frame_columns": repeat_missing,
        "rows": int(len(frame)),
        "slates": slate_count,
        "draw_shape": list(draw_shape),
        "frame_sha256": _frame_sha256(frame) if not missing_columns else None,
        "repeat_frame_sha256": (
            _frame_sha256(repeat_frame) if not repeat_missing else None
        ),
        "draws_sha256": _draw_sha256(draws),
        "repeat_draws_sha256": _draw_sha256(repeat_draws),
        "control_terminal": terminal,
        "repeat_control_terminal": repeat_terminal,
    }


def run_reference(panel_id: str) -> dict[str, Any]:
    """Build a fresh control scorebook without consulting an older score."""
    expected_panel = os.environ.get(
        "SIS_RECEIVER_COPULA_REFERENCE_PANEL", "",
    ).strip()
    evaluation_panel = os.environ.get(
        "SIS_RECEIVER_COPULA_REFERENCE_EVALUATION_PANEL", "",
    ).strip()
    if (
        panel_id != expected_panel
        or panel_id != REFERENCE_HISTORICAL_PANEL
        or evaluation_panel != REFERENCE_EVALUATION_PANEL
    ):
        raise ValueError("receiver-copula fresh reference panels differ")
    runtime_identity = _runtime_identity()

    from . import g1_archetype_topology as g1
    from . import g2_qb_gumbel_factor as g2

    games = g2._load_games()
    frame, draws, terminal = g1._load_terminal_book(panel_id)
    repeat_frame, repeat_draws, repeat_terminal = g1._load_terminal_book(panel_id)
    invariants = reference_invariants(
        frame, draws, terminal, repeat_frame, repeat_draws, repeat_terminal,
    )
    score = g2.score_heldout(frame, draws, games)
    repeat_score = g2.score_heldout(repeat_frame, repeat_draws, games)
    score_sha = _canonical_sha256(score)
    repeat_score_sha = _canonical_sha256(repeat_score)
    invariants["score_bit_exact_on_repeat"] = score_sha == repeat_score_sha
    invariants["score_population_exact"] = bool(
        score.get("population", {}).get("rows") == REFERENCE_ROWS
        and score.get("population", {}).get("slates") == REFERENCE_SLATES
    )
    invariants["passes"] = bool(
        invariants["passes"]
        and invariants["score_bit_exact_on_repeat"]
        and invariants["score_population_exact"]
    )
    disposition = (
        "sis-receiver-copula-reference-passes"
        if invariants["passes"]
        else "sis-receiver-copula-reference-invalid-or-inconclusive"
    )
    report = {
        "version": REFERENCE_VERSION,
        "historical_panel": panel_id,
        "evaluation_panel": evaluation_panel,
        "run_identity": runtime_identity,
        "fresh_post_repair_reference": True,
        "prior_numeric_reference_consulted": False,
        "settings": {
            "cache_table": REFERENCE_CACHE_TABLE,
            "dirichlet_k": REFERENCE_DIRICHLET_K,
            "model_market_blend": "0.45/0.55",
            "worlds": REFERENCE_WORLDS,
            "seed": 0,
            "position_schedule": REFERENCE_POSITION_SCHEDULE,
        },
        "score_sha256": score_sha,
        "repeat_score_sha256": repeat_score_sha,
        "score": score,
        "invariants": invariants,
        "disposition": disposition,
        "heldout_treatment_licensed": (
            disposition == "sis-receiver-copula-reference-passes"
        ),
        "retrospective_exact80_licensed": False,
    }
    _emit_reference(report)
    return report


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


def calibration_grid_row(score: dict[str, Any], strength: float) -> dict[str, Any]:
    """Reduce one complete 2022 scorebook to the frozen selector fields."""
    try:
        g0_errors = _g0_errors(score)
        g1_errors = _g1_errors(score)
        required_support = bool(
            set(CALIBRATION_G0_CELLS).issubset(g0_errors)
            and set(CALIBRATION_G1_CELLS).issubset(g1_errors)
        )
        if not required_support:
            return {
                "strength": float(strength),
                "required_support": False,
                "support_failure": "registered calibration cells unsupported",
                "registered_absolute_log_error_sum": None,
                "joint_q90_brier": None,
                "variogram_p0_5": None,
                "registered_absolute_log_errors": {
                    "g0": {
                        name: g0_errors.get(name)
                        for name in CALIBRATION_G0_CELLS
                    },
                    "g1": {
                        name: g1_errors.get(name)
                        for name in CALIBRATION_G1_CELLS
                    },
                },
            }
        primary = score["primary"]
        brier = float(primary["joint_q90_brier"])
        variogram = float(primary["variogram_p0_5"])
        registered = float(sum(
            g0_errors[name] for name in CALIBRATION_G0_CELLS
        ) + sum(
            g1_errors[name] for name in CALIBRATION_G1_CELLS
        ))
        if not np.isfinite([strength, registered, brier, variogram]).all():
            raise ValueError("receiver-copula calibration score is nonfinite")
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "strength": float(strength),
            "required_support": False,
            "support_failure": str(exc),
            "registered_absolute_log_error_sum": None,
            "joint_q90_brier": None,
            "variogram_p0_5": None,
        }
    return {
        "strength": float(strength),
        "required_support": required_support,
        "support_failure": None,
        "registered_absolute_log_error_sum": registered,
        "joint_q90_brier": brier,
        "variogram_p0_5": variogram,
        "registered_absolute_log_errors": {
            "g0": {name: g0_errors.get(name) for name in CALIBRATION_G0_CELLS},
            "g1": {name: g1_errors.get(name) for name in CALIBRATION_G1_CELLS},
        },
    }


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
    "CALIBRATION_G0_CELLS", "CALIBRATION_G1_CELLS", "FLOAT_TOLERANCE",
    "MULTIPLICITY_CELLS", "REQUIRED_G0_CELLS",
    "REQUIRED_RELATIONSHIPS", "STRENGTH_GRID", "gate_decision",
    "calibration_grid_row", "multiplicity_diagnostic", "reference_invariants",
    "run_reference", "select_calibration_grid",
]
