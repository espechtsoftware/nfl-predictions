"""Repaired reference and score-free competitive-WR TD allocation gate."""

from __future__ import annotations

import base64
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd

from . import final_served_dependence as g0
from . import g1_archetype_topology as g1
from . import g2_qb_gumbel_factor as g2
from . import td_ledger_final_served as prior


REFERENCE_META_PREFIX = "TD_COMPETITIVE_WR_REFERENCE_META="
REFERENCE_CHUNK_PREFIX = "TD_COMPETITIVE_WR_REFERENCE_CHUNK="
TREATMENT_META_PREFIX = "TD_COMPETITIVE_WR_ALLOCATION_META="
TREATMENT_CHUNK_PREFIX = "TD_COMPETITIVE_WR_ALLOCATION_CHUNK="
FLOAT_TOLERANCE = 1e-12
PRIOR_RELATIVE_PATH = (
    "td-ledger-rank-coupling-runs/"
    "20260814-td-ledger-rank-coupling-v1/report.json"
)
UNCHANGED_G1_RELATIONSHIPS = ("QB_TE", "QB_RB", "RB_RB")
UNCHANGED_G0_CELLS = ("qb_te", "qb_rb", "rb_rb")


def _runtime_identity(run_environment: str, code_environment: str) -> dict:
    run_id = os.environ.get(run_environment, "").strip()
    code_sha = os.environ.get(code_environment, "").strip()
    if not run_id or not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise ValueError("competitive-WR immutable runtime identity is missing")
    return {"run_id": run_id, "code_sha": code_sha}


def _canonical_sha256(value: Any) -> str:
    content = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()
    return sha256(content).hexdigest()


def _load_reference_attestation(panel_id: str) -> dict:
    encoded = os.environ.get("TD_COMP_WR_REFERENCE_ATTESTATION_B64", "").strip()
    expected = os.environ.get(
        "TD_COMP_WR_REFERENCE_ATTESTATION_SHA256", "",
    ).strip()
    if not encoded or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("competitive-WR reference attestation is missing")
    try:
        content = base64.b64decode(encoded, validate=True)
        attestation = json.loads(content)
    except Exception as exc:
        raise ValueError("competitive-WR reference attestation is invalid") from exc
    if sha256(content).hexdigest() != expected:
        raise ValueError("competitive-WR reference attestation hash differs")
    expected_identity = _runtime_identity(
        "TD_COMP_WR_REFERENCE_RUN_ID", "TD_COMP_WR_REFERENCE_CODE_SHA",
    )
    expected_report_sha = os.environ.get(
        "TD_COMP_WR_REFERENCE_REPORT_SHA256", "",
    ).strip()
    if (
        attestation.get("version") != "td-competitive-wr-reference-v1"
        or attestation.get("disposition") != "td-competitive-wr-reference-passes"
        or attestation.get("treatment_licensed") is not True
        or attestation.get("panel") != panel_id
        or attestation.get("run_identity") != expected_identity
        or attestation.get("report_sha256") != expected_report_sha
        or not re.fullmatch(r"[0-9a-f]{64}", attestation.get("score_sha256", ""))
    ):
        raise ValueError("competitive-WR reference attestation differs")
    return attestation


def _load_hashed_json(
    path: Path,
    environment_name: str,
    *,
    label: str,
) -> dict:
    expected = os.environ.get(environment_name, "").strip()
    if not expected:
        raise ValueError(f"{label} environment {environment_name} is missing")
    if sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"{label} prerequisite {path.name} hash differs")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def nested_reproduction_failures(
    current: Any,
    expected: Any,
    *,
    tolerance: float = FLOAT_TOLERANCE,
    path: str = "root",
) -> list[str]:
    """Return exact-structure/nonnumeric and tolerance-numeric differences."""
    if isinstance(expected, dict):
        if not isinstance(current, dict):
            return [f"{path}:type"]
        failures = []
        if set(current) != set(expected):
            failures.append(f"{path}:keys")
        for key in sorted(set(current) & set(expected)):
            failures.extend(nested_reproduction_failures(
                current[key], expected[key], tolerance=tolerance,
                path=f"{path}.{key}",
            ))
        return failures
    if isinstance(expected, list):
        if not isinstance(current, list) or len(current) != len(expected):
            return [f"{path}:list"]
        failures = []
        for index, (observed, wanted) in enumerate(zip(current, expected)):
            failures.extend(nested_reproduction_failures(
                observed, wanted, tolerance=tolerance,
                path=f"{path}[{index}]",
            ))
        return failures
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        return [] if current == expected and type(current) is type(expected) else [path]
    if isinstance(expected, int):
        return [] if isinstance(current, int) and current == expected else [path]
    if isinstance(expected, float):
        if not isinstance(current, (int, float)) or isinstance(current, bool):
            return [f"{path}:type"]
        observed = float(current)
        if math.isnan(expected) or math.isnan(observed):
            return [] if math.isnan(expected) and math.isnan(observed) else [path]
        if math.isinf(expected) or math.isinf(observed):
            return [] if expected == observed else [path]
        if abs(observed - expected) > tolerance:
            return [f"{path}:delta={observed - expected:+.17g}"]
        return []
    return [] if current == expected and type(current) is type(expected) else [path]


def _exact_frame_failures(left: pd.DataFrame, right: pd.DataFrame) -> list[str]:
    failures = []
    for column in (
        "season", "week", "gsis_id", "position", "team", "opp", "game_id",
    ):
        if column not in left or column not in right or not left[column].equals(
                right[column]):
            failures.append(f"frame:{column}")
    for column in ("actual", "mean_projection"):
        if (
            column not in left
            or column not in right
            or not np.array_equal(
                left[column].to_numpy(), right[column].to_numpy(),
                equal_nan=True,
            )
        ):
            failures.append(f"frame:{column}")
    return failures


def stable_percentile_ranks(values: np.ndarray) -> np.ndarray:
    """Stable ascending ranks scaled to [0, 1], with world index breaking ties."""
    row = np.asarray(values)
    if row.ndim != 1 or not np.isfinite(row).all():
        raise ValueError("competitive-WR rank row is invalid")
    order = np.argsort(row, kind="stable")
    ranks = np.empty(len(row), dtype=np.float64)
    ranks[order] = np.arange(len(row), dtype=np.float64)
    if len(row) > 1:
        ranks /= float(len(row) - 1)
    return ranks


def apply_competitive_wr_allocation(
    control_draws: np.ndarray,
    td_source_draws: np.ndarray,
    frame: pd.DataFrame,
) -> tuple[np.ndarray, dict, np.ndarray]:
    """Permute eligible WR marginals by the frozen centered allocation rank."""
    control = np.asarray(control_draws)
    source = np.asarray(td_source_draws)
    if control.ndim != 2 or control.shape != source.shape or len(frame) != len(control):
        raise ValueError("competitive-WR draws or frame differ")
    if not np.isfinite(control).all() or not np.isfinite(source).all():
        raise ValueError("competitive-WR draws are nonfinite")
    required = {
        "season", "week", "game_id", "team", "gsis_id", "position",
        "mean_projection",
    }
    if not required.issubset(frame):
        raise ValueError("competitive-WR frame lacks required columns")

    supported = (
        frame.position.isin(g1.POSITIONS)
        & frame.mean_projection.ge(g0.MIN_MEAN)
    ).to_numpy(bool)
    eligible = np.zeros(len(frame), dtype=bool)
    treatment = control.copy()
    group_columns = ["season", "week", "game_id", "team"]
    eligible_keys: list[tuple[str, ...]] = []

    grouped = frame.loc[supported].groupby(
        group_columns, sort=True, dropna=False,
    )
    for key, group in grouped:
        qb_rows = group.index[group.position.eq("QB")].to_numpy(int)
        wr_rows = group.index[group.position.eq("WR")].to_numpy(int)
        if len(qb_rows) != 1 or len(wr_rows) < 2:
            continue
        wr_rows = np.asarray(sorted(
            wr_rows.tolist(), key=lambda row: (str(frame.at[row, "gsis_id"]), row)
        ), dtype=int)
        qb_rank = stable_percentile_ranks(control[qb_rows[0]])
        wr_ranks = np.vstack([
            stable_percentile_ranks(source[row]) for row in wr_rows
        ])
        centered = wr_ranks - wr_ranks.mean(axis=0, dtype=np.float64)
        for offset, row in enumerate(wr_rows):
            priority = qb_rank + centered[offset]
            world_order = np.argsort(priority, kind="stable")
            treatment[row, world_order] = np.sort(control[row], kind="stable")
        eligible[wr_rows] = True
        if not isinstance(key, tuple):
            key = (key,)
        eligible_keys.append(tuple(str(value) for value in key))

    encoded_keys = json.dumps(
        eligible_keys, sort_keys=True, separators=(",", ":"),
    ).encode()
    audit = {
        "formula": (
            "qb_control_percentile+(wr_td_percentile-team_wr_mean_percentile)"
        ),
        "rank_tie_rule": "stable_ascending_world_index",
        "eligible_groups": int(len(eligible_keys)),
        "eligible_wr_rows": int(eligible.sum()),
        "eligible_group_keys_sha256": sha256(encoded_keys).hexdigest(),
    }
    return treatment, audit, eligible


def _emit(report: dict, meta_prefix: str, chunk_prefix: str) -> None:
    meta, chunks = g1.encode_report_transport(report)
    print(meta_prefix + json.dumps(meta, sort_keys=True), flush=True)
    for index, chunk in enumerate(chunks):
        print(f"{chunk_prefix}{index}/{len(chunks)}:{chunk}", flush=True)


def run_reference(panel_id: str) -> dict:
    expected_panel = os.environ.get("TD_COMP_WR_PANEL_ID", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("competitive-WR reference panel differs")
    root = Path(os.environ.get("TD_COMP_WR_REFERENCE_ROOT", "/app/reports"))
    prior_report = _load_hashed_json(
        root / PRIOR_RELATIVE_PATH,
        "TD_COMP_WR_PRIOR_REPORT_SHA256",
        label="competitive-WR reference",
    )
    if "control" not in prior_report:
        raise ValueError("competitive-WR prior lacks repaired control payload")
    runtime_identity = _runtime_identity(
        "TD_COMP_WR_RUN_ID", "TD_COMP_WR_CODE_SHA",
    )

    games = g2._load_games()
    frame, draws, terminal = g1._load_terminal_book(panel_id)
    repeat_frame, repeat_draws, repeat_terminal = g1._load_terminal_book(panel_id)
    score = g2.score_heldout(frame, draws, games)
    frame_failures = _exact_frame_failures(frame, repeat_frame)
    reproduction_failures = nested_reproduction_failures(
        score, prior_report["control"], path="score",
    )
    invariants = {
        "frame_alignment_failures": frame_failures,
        "prior_control_reproduction_failures": reproduction_failures,
        "draws_bit_exact_on_repeat": bool(np.array_equal(draws, repeat_draws)),
        "terminal_identity_exact_on_repeat": terminal == repeat_terminal,
        "finite_draws": bool(np.isfinite(draws).all()),
        "control_terminal": terminal,
        "repeat_control_terminal": repeat_terminal,
        "passes": False,
    }
    invariants["passes"] = bool(
        not frame_failures
        and not reproduction_failures
        and invariants["draws_bit_exact_on_repeat"]
        and invariants["terminal_identity_exact_on_repeat"]
        and invariants["finite_draws"]
    )
    disposition = (
        "td-competitive-wr-reference-passes"
        if invariants["passes"]
        else "td-competitive-wr-reference-invalid-or-inconclusive"
    )
    report = {
        "version": "td-competitive-wr-reference-v1",
        "panel": panel_id,
        "adaptive_retrospective": True,
        "run_identity": runtime_identity,
        "prior_treatment_and_disposition_ignored": True,
        "reference_tolerance": FLOAT_TOLERANCE,
        "score_sha256": _canonical_sha256(score),
        "score": score,
        "invariants": invariants,
        "disposition": disposition,
        "treatment_licensed": disposition == "td-competitive-wr-reference-passes",
    }
    _emit(report, REFERENCE_META_PREFIX, REFERENCE_CHUNK_PREFIX)
    return report


def _absolute_error(score: dict, family: str, key: str) -> float:
    primary = score["primary"]
    if family == "g1":
        value = primary["g1_relationship_errors"][key]["absolute_log_error"]
    elif family == "g0":
        value = primary["g0_cell_errors"][key]
    else:
        raise ValueError("competitive-WR error family is invalid")
    value = float(value)
    if not np.isfinite(value):
        raise ValueError(f"competitive-WR required {family}:{key} is unsupported")
    return value


def gate_decision(
    control: dict,
    treatment: dict,
    *,
    invariants_pass: bool,
    changed_rows: int,
) -> dict:
    """Apply the frozen shape-aware scientific gate."""
    try:
        values = {
            "g1_qb_wr": (
                _absolute_error(control, "g1", "QB_WR"),
                _absolute_error(treatment, "g1", "QB_WR"),
            ),
            "g1_wr_wr": (
                _absolute_error(control, "g1", "WR_WR"),
                _absolute_error(treatment, "g1", "WR_WR"),
            ),
            "g0_qb_wr": (
                _absolute_error(control, "g0", "qb_wr"),
                _absolute_error(treatment, "g0", "qb_wr"),
            ),
            "g0_wr_wr": (
                _absolute_error(control, "g0", "wr_wr"),
                _absolute_error(treatment, "g0", "wr_wr"),
            ),
            "g0_multiplicity_ge3": (
                _absolute_error(control, "g0", "multiplicity_ge3"),
                _absolute_error(treatment, "g0", "multiplicity_ge3"),
            ),
            "g0_multiplicity_ge2": (
                _absolute_error(control, "g0", "multiplicity_ge2"),
                _absolute_error(treatment, "g0", "multiplicity_ge2"),
            ),
        }
        negative_control_failures = []
        for relationship in UNCHANGED_G1_RELATIONSHIPS:
            negative_control_failures.extend(nested_reproduction_failures(
                treatment["scorecard"][relationship],
                control["scorecard"][relationship],
                path=f"scorecard.{relationship}",
            ))
            negative_control_failures.extend(nested_reproduction_failures(
                treatment["broad_relationships"][relationship],
                control["broad_relationships"][relationship],
                path=f"broad.{relationship}",
            ))
        for cell in UNCHANGED_G0_CELLS:
            negative_control_failures.extend(nested_reproduction_failures(
                treatment["g0"]["cells"][cell],
                control["g0"]["cells"][cell],
                path=f"g0.{cell}",
            ))
    except (KeyError, TypeError, ValueError):
        required_support = False
        values = {}
        negative_control_failures = ["required-score-book"]
    else:
        required_support = True

    cp = control.get("primary", {})
    tp = treatment.get("primary", {})
    gates = {
        "all_invariants_pass": bool(invariants_pass),
        "treatment_changes_eligible_wr_ranks": int(changed_rows) > 0,
        "required_cells_supported": required_support,
        "primary_joint_q90_brier_improves": (
            tp.get("joint_q90_brier", np.inf)
            < cp.get("joint_q90_brier", -np.inf)
        ),
        "primary_variogram_improves": (
            tp.get("variogram_p0_5", np.inf)
            < cp.get("variogram_p0_5", -np.inf)
        ),
        "g1_qb_wr_error_improves": bool(
            required_support and values["g1_qb_wr"][1] < values["g1_qb_wr"][0]
        ),
        "g1_wr_wr_error_improves": bool(
            required_support and values["g1_wr_wr"][1] < values["g1_wr_wr"][0]
        ),
        "g0_qb_wr_error_improves": bool(
            required_support and values["g0_qb_wr"][1] < values["g0_qb_wr"][0]
        ),
        "g0_wr_wr_error_improves": bool(
            required_support and values["g0_wr_wr"][1] < values["g0_wr_wr"][0]
        ),
        "g0_multiplicity_ge3_error_improves": bool(
            required_support
            and values["g0_multiplicity_ge3"][1]
            < values["g0_multiplicity_ge3"][0]
        ),
        "g0_multiplicity_ge2_error_not_worse": bool(
            required_support
            and values["g0_multiplicity_ge2"][1]
            <= values["g0_multiplicity_ge2"][0] + FLOAT_TOLERANCE
        ),
        "g0_absolute_log_error_sum_improves": (
            tp.get("g0_absolute_log_error_sum", np.inf)
            < cp.get("g0_absolute_log_error_sum", -np.inf)
        ),
        "g1_weighted_absolute_log_error_sum_improves": (
            tp.get("g1_weighted_absolute_log_error_sum", np.inf)
            < cp.get("g1_weighted_absolute_log_error_sum", -np.inf)
        ),
        "unchanged_qb_rb_te_negative_controls_pass": (
            not negative_control_failures
        ),
    }
    if not invariants_pass or not required_support:
        disposition = "td-competitive-wr-allocation-invalid-or-inconclusive"
    elif all(gates.values()):
        disposition = "td-competitive-wr-allocation-gate-passes"
    else:
        disposition = "td-competitive-wr-allocation-gate-fails"
    return {
        "disposition": disposition,
        "exact80_licensed": disposition == "td-competitive-wr-allocation-gate-passes",
        "gate": {**gates, "passes": all(gates.values())},
        "registered_error_values": {
            key: {"control": pair[0], "treatment": pair[1]}
            for key, pair in values.items()
        },
        "negative_control_failures": negative_control_failures,
    }


def multiplicity_ge4_diagnostic(control: dict, treatment: dict) -> dict:
    """Mandatory disclosure for the unsupported but extreme >=4 cell."""
    control_row = control["g0"]["cells"]["multiplicity_ge4"]
    treatment_row = treatment["g0"]["cells"]["multiplicity_ge4"]
    realized = float(control_row["realized_estimate"])
    if not math.isclose(
        realized, float(treatment_row["realized_estimate"]),
        rel_tol=0, abs_tol=FLOAT_TOLERANCE,
    ):
        raise ValueError("competitive-WR >=4 realized reference changed")
    control_simulated = float(control_row["simulated_estimate"])
    treatment_simulated = float(treatment_row["simulated_estimate"])
    control_error = abs(math.log(control_simulated / realized))
    treatment_error = abs(math.log(treatment_simulated / realized))
    if treatment_error < control_error:
        movement = "toward-realized"
    elif treatment_error > control_error:
        movement = "away-from-realized"
    else:
        movement = "unchanged"
    support = control_row.get("support", {})
    return {
        "mandatory_report": True,
        "gated": False,
        "supported": bool(control_row.get("supported")),
        "realized_events": int(support["realized_events"]),
        "independence_expected_events": float(
            support["poisson_binomial_expected_events"]
        ),
        "realized_estimate": realized,
        "control_simulated_estimate": control_simulated,
        "treatment_simulated_estimate": treatment_simulated,
        "control_absolute_log_error": control_error,
        "treatment_absolute_log_error": treatment_error,
        "treatment_minus_control_simulated": (
            treatment_simulated - control_simulated
        ),
        "movement": movement,
    }


def run_treatment(panel_id: str) -> dict:
    expected_panel = os.environ.get("TD_COMP_WR_PANEL_ID", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("competitive-WR treatment panel differs")
    reference = _load_reference_attestation(panel_id)
    expected_reference_identity = reference["run_identity"]

    games = g2._load_games()
    control_frame, control_draws, control_terminal = g1._load_terminal_book(panel_id)
    repeat_frame, repeat_draws, repeat_terminal = g1._load_terminal_book(panel_id)
    source_frame, source_draws, source_terminal = g1._load_terminal_book(
        panel_id, simulator_overrides={"TD_LEDGER": "1"},
    )
    source_repeat_frame, source_repeat_draws, source_repeat_terminal = (
        g1._load_terminal_book(
            panel_id, simulator_overrides={"TD_LEDGER": "1"},
        )
    )
    alignment_failures = _exact_frame_failures(control_frame, repeat_frame)
    alignment_failures.extend(
        f"source:{failure}"
        for failure in _exact_frame_failures(control_frame, source_frame)
    )
    alignment_failures.extend(
        f"source-repeat:{failure}"
        for failure in _exact_frame_failures(source_frame, source_repeat_frame)
    )

    control = g2.score_heldout(control_frame, control_draws, games)
    observed_score_sha = _canonical_sha256(control)
    reference_failures = (
        [] if observed_score_sha == reference["score_sha256"]
        else [
            "control:score_sha256:"
            f"observed={observed_score_sha}:expected={reference['score_sha256']}"
        ]
    )
    treatment_draws, allocation_audit, eligible = apply_competitive_wr_allocation(
        control_draws, source_draws, control_frame,
    )
    repeated_treatment, repeated_audit, repeated_eligible = (
        apply_competitive_wr_allocation(
            control_draws, source_repeat_draws, control_frame,
        )
    )
    changed = np.not_equal(control_draws, treatment_draws)
    changed_rows_mask = changed.any(axis=1)
    changed_rows = int(changed_rows_mask.sum())
    exact_multisets = bool(all(
        np.array_equal(np.sort(before), np.sort(after))
        for before, after in zip(control_draws, treatment_draws)
    ))
    maximum_mean_delta = float(np.max(np.abs(
        control_draws.mean(axis=1, dtype=np.float64)
        - treatment_draws.mean(axis=1, dtype=np.float64)
    ), initial=0.0))
    invariants = {
        "reference_reproduction_failures": reference_failures,
        "frame_alignment_failures": alignment_failures,
        "control_draws_bit_exact_on_repeat": bool(
            np.array_equal(control_draws, repeat_draws)
        ),
        "control_terminal_exact_on_repeat": control_terminal == repeat_terminal,
        "source_draws_bit_exact_on_repeat": bool(
            np.array_equal(source_draws, source_repeat_draws)
        ),
        "source_terminal_exact_on_repeat": source_terminal == source_repeat_terminal,
        "allocation_audit_exact_on_repeat": bool(
            allocation_audit == repeated_audit
            and np.array_equal(eligible, repeated_eligible)
        ),
        "treatment_bit_exact_on_repeat": bool(
            np.array_equal(treatment_draws, repeated_treatment)
        ),
        "exact_sorted_draw_multisets": exact_multisets,
        "finite_output": bool(np.isfinite(treatment_draws).all()),
        "maximum_mean_delta": maximum_mean_delta,
        "only_eligible_wr_rows_changed": bool(
            np.all(np.logical_or(~changed_rows_mask, eligible))
        ),
        "all_ineligible_rows_bit_exact": bool(
            np.array_equal(treatment_draws[~eligible], control_draws[~eligible])
        ),
        "eligible_groups": allocation_audit["eligible_groups"],
        "eligible_wr_rows": allocation_audit["eligible_wr_rows"],
        "changed_rows": changed_rows,
        "changed_world_cells": int(changed.sum()),
        "control_terminal": control_terminal,
        "repeat_control_terminal": repeat_terminal,
        "source_terminal": source_terminal,
        "repeat_source_terminal": source_repeat_terminal,
        "passes": False,
    }
    invariants["passes"] = bool(
        not reference_failures
        and not alignment_failures
        and invariants["control_draws_bit_exact_on_repeat"]
        and invariants["control_terminal_exact_on_repeat"]
        and invariants["source_draws_bit_exact_on_repeat"]
        and invariants["source_terminal_exact_on_repeat"]
        and invariants["allocation_audit_exact_on_repeat"]
        and invariants["treatment_bit_exact_on_repeat"]
        and exact_multisets
        and invariants["finite_output"]
        and maximum_mean_delta <= 1e-10
        and invariants["only_eligible_wr_rows_changed"]
        and invariants["all_ineligible_rows_bit_exact"]
        and allocation_audit["eligible_groups"] > 0
        and allocation_audit["eligible_wr_rows"] > 0
        and changed_rows > 0
    )

    treatment = g2.score_heldout(control_frame, treatment_draws, games)
    multiplicity_ge4 = multiplicity_ge4_diagnostic(control, treatment)
    bootstrap = g2.paired_primary_bootstrap(
        control_frame, control_draws, treatment_draws, games,
    )
    decision = gate_decision(
        control, treatment,
        invariants_pass=invariants["passes"], changed_rows=changed_rows,
    )
    report = {
        "version": "td-competitive-wr-allocation-v1",
        "panel": panel_id,
        "adaptive_retrospective": True,
        "reference_identity": expected_reference_identity,
        "reference_attestation": reference,
        "intervention": {
            "changed_positions": ["WR"],
            "rank_source": {"TD_LEDGER": "1", "td_alloc_k": None},
            "priority": allocation_audit["formula"],
            "rank_tie_rule": allocation_audit["rank_tie_rule"],
            "coefficients": {"qb_control_percentile": 1.0, "centered_wr_td": 1.0},
            "minimum_supported_mean": float(g0.MIN_MEAN),
            "required_qbs_per_group": 1,
            "minimum_wrs_per_group": 2,
        },
        "allocation_audit": allocation_audit,
        "control": control,
        "treatment": treatment,
        "season_disclosures": {
            "control": prior._season_disclosures(
                control_frame, control_draws, games,
            ),
            "treatment": prior._season_disclosures(
                control_frame, treatment_draws, games,
            ),
        },
        "bootstrap": bootstrap,
        "multiplicity_ge4_diagnostic": multiplicity_ge4,
        "invariants": invariants,
        **decision,
    }
    _emit(report, TREATMENT_META_PREFIX, TREATMENT_CHUNK_PREFIX)
    return report


__all__ = [
    "apply_competitive_wr_allocation",
    "gate_decision",
    "multiplicity_ge4_diagnostic",
    "nested_reproduction_failures",
    "run_reference",
    "run_treatment",
    "stable_percentile_ranks",
]
