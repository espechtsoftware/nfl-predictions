"""Frozen score-free final-served evaluation of the existing TD ledger."""

from __future__ import annotations

from hashlib import sha256
import json
from math import log
import os
from pathlib import Path

import numpy as np
import pandas as pd

from . import final_served_dependence as g0
from . import g1_archetype_topology as g1
from . import g2_qb_gumbel_factor as g2


OUTPUT_META_PREFIX = "TD_LEDGER_FINAL_SERVED_META="
OUTPUT_CHUNK_PREFIX = "TD_LEDGER_FINAL_SERVED_CHUNK="
FLOAT_TOLERANCE = 1e-12
MATERIAL_REGRESSION_TOLERANCE = log(1.05)
NAMED_G1_GUARDS = ("QB_TE", "RB_RB")
NAMED_G0_GUARDS = ("multiplicity_ge2", "multiplicity_ge3")


def _load_reference(path: Path, environment_name: str) -> dict:
    expected = os.environ.get(environment_name, "").strip()
    if not expected:
        raise ValueError(f"TD-ledger environment {environment_name} is missing")
    if sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"TD-ledger prerequisite {path.name} hash differs")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _absolute_g1_error(score: dict, relationship: str) -> float:
    row = score["primary"]["g1_relationship_errors"].get(relationship)
    if not row or not np.isfinite(row.get("absolute_log_error", np.nan)):
        raise ValueError(f"TD-ledger required G1 cell {relationship} is unsupported")
    return float(row["absolute_log_error"])


def _absolute_g0_error(score: dict, cell: str) -> float:
    row = score["primary"]["g0_cell_errors"].get(cell)
    if row is None or not np.isfinite(row):
        raise ValueError(f"TD-ledger required G0 cell {cell} is unsupported")
    return float(row)


def gate_decision(
    control: dict,
    treatment: dict,
    *,
    invariants_pass: bool,
    changed_rows: int,
) -> dict:
    """Apply the fixed score-free gate without inspecting lineup outcomes."""
    cp = control["primary"]
    tp = treatment["primary"]
    try:
        qb_wr_control = _absolute_g1_error(control, "QB_WR")
        qb_wr_treatment = _absolute_g1_error(treatment, "QB_WR")
        wr_wr_control = _absolute_g1_error(control, "WR_WR")
        wr_wr_treatment = _absolute_g1_error(treatment, "WR_WR")
        guard_values = {
            relationship: (
                _absolute_g1_error(control, relationship),
                _absolute_g1_error(treatment, relationship),
            )
            for relationship in NAMED_G1_GUARDS
        }
        guard_values.update({
            cell: (
                _absolute_g0_error(control, cell),
                _absolute_g0_error(treatment, cell),
            )
            for cell in NAMED_G0_GUARDS
        })
    except ValueError:
        required_support = False
        qb_wr_control = qb_wr_treatment = np.nan
        wr_wr_control = wr_wr_treatment = np.nan
        guard_values = {}
    else:
        required_support = True

    gates = {
        "terminal_and_exact_marginal_invariants_pass": bool(invariants_pass),
        "treatment_changes_world_ranks": int(changed_rows) > 0,
        "required_cells_supported": required_support,
        "primary_joint_q90_brier_improves": (
            tp["joint_q90_brier"] < cp["joint_q90_brier"]),
        "primary_variogram_improves": (
            tp["variogram_p0_5"] < cp["variogram_p0_5"]),
        "qb_wr_absolute_log_error_improves": (
            qb_wr_treatment < qb_wr_control),
        "g0_absolute_log_error_improves": (
            tp["g0_absolute_log_error_sum"]
            < cp["g0_absolute_log_error_sum"]),
        "g1_weighted_absolute_log_error_improves": (
            tp["g1_weighted_absolute_log_error_sum"]
            < cp["g1_weighted_absolute_log_error_sum"]),
        "wr_wr_absolute_log_error_not_worse": (
            wr_wr_treatment <= wr_wr_control + FLOAT_TOLERANCE),
        "named_material_regression_guards_pass": bool(
            required_support and all(
                treatment_value <= control_value + MATERIAL_REGRESSION_TOLERANCE
                for control_value, treatment_value in guard_values.values()
            )
        ),
    }
    if not invariants_pass or not required_support:
        disposition = "td-ledger-invalid-or-inconclusive"
    elif all(gates.values()):
        disposition = "td-ledger-dependence-gate-passes"
    else:
        disposition = "td-ledger-dependence-gate-fails"
    return {
        "disposition": disposition,
        "exact80_licensed": disposition == "td-ledger-dependence-gate-passes",
        "gate": {**gates, "passes": all(gates.values())},
        "guard_values": {
            key: {"control": value[0], "treatment": value[1]}
            for key, value in guard_values.items()
        },
    }


def _season_disclosures(
    frame: pd.DataFrame,
    draws: np.ndarray,
    games: pd.DataFrame,
) -> dict:
    disclosures = {}
    for season in g2.EVALUATION_SEASONS:
        mask = frame.season.eq(season).to_numpy(bool)
        season_frame = frame.loc[mask].reset_index(drop=True)
        season_draws = np.asarray(draws)[mask]
        support = (
            season_frame.position.isin(g1.POSITIONS)
            & season_frame.mean_projection.ge(g0.MIN_MEAN)
        ).to_numpy(bool)
        supported = season_frame.loc[support].reset_index(drop=True)
        supported_draws = season_draws[support]
        supported, _ = g1.attach_walk_forward_archetypes(supported, games)
        pairs = g1.build_pair_book(supported)
        scorecard = g1.pair_scorecard(pairs, supported, supported_draws)
        thresholds = np.quantile(supported_draws, 0.90, axis=1)
        actual_flags = supported.actual.to_numpy(float) > thresholds
        simulated_flags = supported_draws > thresholds[:, None]
        contributions = g1.pair_contributions(
            pairs, actual_flags, simulated_flags)
        _cells, broad = g1.summarize_cells(contributions)
        g0_report = g0.evaluate_dependence(
            season_frame, season_draws, n_bootstraps=200,
            bootstrap_seed=1_800 + season)
        disclosures[str(season)] = {
            "rows": int(len(supported)),
            "slates": int(supported[["season", "week"]].drop_duplicates().shape[0]),
            "primary_joint_q90_brier": g2._weighted_score(
                scorecard, "joint_q90_brier"),
            "primary_variogram_p0_5": g2._weighted_score(
                scorecard, "variogram_p0_5"),
            "g1_absolute_log_errors": {
                relationship: (
                    abs(float(broad[relationship]["log_simulated_to_realized"]))
                    if broad[relationship].get("log_simulated_to_realized") is not None
                    else None
                )
                for relationship in ("QB_WR", "QB_TE", "WR_WR", "RB_RB")
            },
            "g0_absolute_log_errors": {
                cell: (
                    abs(float(g0_report["cells"][cell]["log_simulated_to_realized"]))
                    if g0_report["cells"][cell].get("log_simulated_to_realized")
                    is not None else None
                )
                for cell in NAMED_G0_GUARDS
            },
        }
    return disclosures


def _frame_alignment_failures(control: pd.DataFrame, treatment: pd.DataFrame) -> list[str]:
    failures = []
    for column in ("season", "week", "gsis_id", "position", "team", "opp", "game_id"):
        if column not in control or column not in treatment or not control[column].equals(
                treatment[column]):
            failures.append(f"frame:{column}")
    # Actual outcomes are input identity and must reproduce exactly. The
    # protocol deliberately audits simulated means separately with a 1e-10
    # tolerance, so requiring bitwise frame equality for mean_projection here
    # would contradict that frozen tolerance and could reject harmless
    # floating-point summation drift before the intended audit runs.
    if (
        "actual" not in control
        or "actual" not in treatment
        or not np.array_equal(
            control["actual"].to_numpy(), treatment["actual"].to_numpy())
    ):
        failures.append("frame:actual")
    return failures


def run(panel_id: str) -> dict:
    expected_panel = os.environ.get("TD_LEDGER_PANEL_ID", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("TD-ledger panel differs from terminal selection")
    root = Path(os.environ.get("TD_LEDGER_REFERENCE_ROOT", "/app/reports"))
    g0_reference = _load_reference(
        root / "g0-dependence-runs/20260812-g0-final-served-dependence-v2/report.json",
        "TD_LEDGER_G0_REPORT_SHA256",
    )
    g1_reference = _load_reference(
        root / "g1-topology-runs/20260812-g1-archetype-topology-v3/report.json",
        "TD_LEDGER_G1_REPORT_SHA256",
    )
    if g1_reference.get("disposition") != "stable-qb-hub-confirmed":
        raise ValueError("TD-ledger lacks the terminal G1 premise")

    games = g2._load_games()
    control_frame, control_draws, control_terminal = g1._load_terminal_book(panel_id)
    control = g2.score_heldout(control_frame, control_draws, games)
    reproduction_failures = g2.validate_control_reproduction(
        control, g0_reference, g1_reference)

    treatment_frame, treatment_draws, treatment_terminal = g1._load_terminal_book(
        panel_id, simulator_overrides={"TD_LEDGER": "1"})
    repeated_frame, repeated_draws, repeated_terminal = g1._load_terminal_book(
        panel_id, simulator_overrides={"TD_LEDGER": "1"})
    alignment_failures = _frame_alignment_failures(control_frame, treatment_frame)
    alignment_failures.extend(
        f"repeat:{value}" for value in
        _frame_alignment_failures(treatment_frame, repeated_frame))

    exact_multisets = bool(all(
        np.array_equal(np.sort(before), np.sort(after))
        for before, after in zip(control_draws, treatment_draws)
    ))
    changed = np.not_equal(control_draws, treatment_draws)
    changed_rows = int(np.count_nonzero(changed.any(axis=1)))
    changed_cells = int(np.count_nonzero(changed))
    maximum_mean_delta = float(np.max(np.abs(
        control_draws.mean(axis=1, dtype=np.float64)
        - treatment_draws.mean(axis=1, dtype=np.float64)), initial=0.0))
    deterministic = bool(
        np.array_equal(treatment_draws, repeated_draws)
        and treatment_terminal == repeated_terminal
    )
    invariants = {
        "control_reproduction_failures": reproduction_failures,
        "frame_alignment_failures": alignment_failures,
        "control_terminal": control_terminal,
        "treatment_terminal": treatment_terminal,
        "exact_sorted_draw_multisets": exact_multisets,
        "finite_output": bool(np.isfinite(treatment_draws).all()),
        "deterministic_output": deterministic,
        "maximum_mean_delta": maximum_mean_delta,
        "changed_rows": changed_rows,
        "changed_world_cells": changed_cells,
        "passes": False,
    }
    invariants["passes"] = bool(
        not reproduction_failures
        and not alignment_failures
        and exact_multisets
        and invariants["finite_output"]
        and deterministic
        and maximum_mean_delta <= 1e-10
        and changed_rows > 0
    )

    treatment = g2.score_heldout(treatment_frame, treatment_draws, games)
    bootstrap = g2.paired_primary_bootstrap(
        control_frame, control_draws, treatment_draws, games)
    decision = gate_decision(
        control, treatment,
        invariants_pass=invariants["passes"], changed_rows=changed_rows)
    report = {
        "version": "v1",
        "panel": panel_id,
        "adaptive_retrospective": True,
        "intervention": {"TD_LEDGER": "1", "td_alloc_k": None},
        "control": control,
        "treatment": treatment,
        "season_disclosures": {
            "control": _season_disclosures(control_frame, control_draws, games),
            "treatment": _season_disclosures(
                treatment_frame, treatment_draws, games),
        },
        "bootstrap": bootstrap,
        "invariants": invariants,
        "material_regression_tolerance_abs_log": MATERIAL_REGRESSION_TOLERANCE,
        **decision,
    }
    meta, chunks = g1.encode_report_transport(report)
    print(OUTPUT_META_PREFIX + json.dumps(meta, sort_keys=True), flush=True)
    for index, chunk in enumerate(chunks):
        print(f"{OUTPUT_CHUNK_PREFIX}{index}/{len(chunks)}:{chunk}", flush=True)
    return report


__all__ = [
    "MATERIAL_REGRESSION_TOLERANCE", "gate_decision", "run",
]
