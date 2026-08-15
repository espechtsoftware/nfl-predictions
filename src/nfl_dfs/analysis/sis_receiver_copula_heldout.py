"""Held-out 2023--2025 gate for the frozen SIS receiver copula."""

from __future__ import annotations

import base64
from hashlib import sha256
import json
import os
import re
from typing import Any

import numpy as np
import pandas as pd

from . import final_served_dependence as g0
from . import g1_archetype_topology as g1
from . import g2_qb_gumbel_factor as g2
from . import sis_receiver_copula as gate
from . import sis_receiver_copula_calibration as calibration
from ..research import sis_receiver_copula as treatment


OUTPUT_META_PREFIX = "SIS_RECEIVER_COPULA_HELDOUT_META="
OUTPUT_CHUNK_PREFIX = "SIS_RECEIVER_COPULA_HELDOUT_CHUNK="
VERSION = "sis-receiver-copula-heldout-v1"
HELDOUT_SEASONS = (2023, 2024, 2025)


def _runtime_identity() -> dict[str, str]:
    run_id = os.environ.get("SIS_RECEIVER_COPULA_HELDOUT_RUN_ID", "").strip()
    code_sha = os.environ.get("SIS_RECEIVER_COPULA_HELDOUT_CODE_SHA", "").strip()
    if not run_id or not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise ValueError("receiver-copula held-out identity is missing")
    return {"run_id": run_id, "code_sha": code_sha}


def _attestation(name: str) -> dict[str, Any]:
    encoded = os.environ.get(f"SIS_RECEIVER_COPULA_{name}_ATTESTATION_B64", "").strip()
    expected = os.environ.get(
        f"SIS_RECEIVER_COPULA_{name}_ATTESTATION_SHA256", "",
    ).strip()
    if not encoded or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError(f"receiver-copula {name.lower()} attestation is missing")
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        content = base64.b64decode(padded, validate=True)
        value = json.loads(content)
    except Exception as exc:
        raise ValueError(
            f"receiver-copula {name.lower()} attestation is invalid"
        ) from exc
    if sha256(content).hexdigest() != expected:
        raise ValueError(f"receiver-copula {name.lower()} attestation hash differs")
    return value


def _validate_attestations(
    reference: dict[str, Any], calibration_report: dict[str, Any], panel_id: str,
) -> float:
    hashes = ("report_sha256", "manifest_sha256")
    if (
        reference.get("version")
        != "sis-receiver-copula-reference-attestation-v1"
        or reference.get("historical_panel") != panel_id
        or reference.get("evaluation_panel") != gate.REFERENCE_EVALUATION_PANEL
        or reference.get("disposition")
        != "sis-receiver-copula-reference-passes"
        or reference.get("heldout_treatment_licensed") is not True
        or not all(re.fullmatch(r"[0-9a-f]{64}", reference.get(key, ""))
                   for key in (*hashes, "score_sha256", "frame_sha256",
                               "draws_sha256", "terminal_sha256"))
    ):
        raise ValueError("receiver-copula reference attestation differs")
    selected = calibration_report.get("selected", {})
    strength = float(selected.get("strength", np.nan))
    if (
        calibration_report.get("version")
        != "sis-receiver-copula-calibration-attestation-v1"
        or calibration_report.get("panel") != panel_id
        or calibration_report.get("disposition")
        != "sis-receiver-copula-calibration-passes"
        or calibration_report.get("heldout_evaluation_licensed") is not True
        or calibration_report.get("protocols") != {
            "parent_protocol_sha256": calibration.PARENT_PROTOCOL_SHA256,
            "calibration_amendment_sha256": calibration.AMENDMENT_SHA256,
        }
        or strength not in gate.STRENGTH_GRID
        or selected.get("required_support") is not True
        or not all(re.fullmatch(
            r"[0-9a-f]{64}", calibration_report.get(key, "")
        ) for key in hashes)
    ):
        raise ValueError("receiver-copula calibration attestation differs")
    return strength


def _canonical_sha256(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def score_season(
    frame: pd.DataFrame, draws: np.ndarray, games: pd.DataFrame,
) -> dict[str, Any]:
    """Produce mandatory per-season scores without imposing aggregate support."""
    full_g0 = g0.evaluate_dependence(frame, draws)
    mask = (
        frame.position.isin(g1.POSITIONS)
        & frame.mean_projection.ge(g0.MIN_MEAN)
    ).to_numpy(bool)
    supported = frame.loc[mask].reset_index(drop=True)
    supported_draws = np.asarray(draws)[mask]
    supported, archetype_audit = g1.attach_walk_forward_archetypes(
        supported, games,
    )
    pairs = g1.build_pair_book(supported)
    thresholds = np.quantile(supported_draws, 0.90, axis=1)
    actual_flags = supported.actual.to_numpy(float) > thresholds
    simulated_flags = supported_draws > thresholds[:, None]
    contributions = g1.pair_contributions(
        pairs, actual_flags, simulated_flags,
    )
    _cells, broad = g1.summarize_cells(contributions)
    scorecard = g1.pair_scorecard(pairs, supported, supported_draws)
    g0_abs, g0_cells = g2._g0_abs_log_error(full_g0)
    g1_cells = {}
    for relationship, weight in g2.PRIMARY_WEIGHTS.items():
        row = broad.get(relationship, {})
        value = row.get("log_simulated_to_realized")
        if row.get("supported") and value is not None and np.isfinite(value):
            g1_cells[relationship] = {
                "absolute_log_error": abs(float(value)),
                "weight": float(weight),
            }
    return {
        "population": {
            "rows": int(len(supported)),
            "slates": int(supported[["season", "week"]].drop_duplicates().shape[0]),
            "pairs": int(len(pairs)),
        },
        "archetypes": archetype_audit,
        "g0": full_g0,
        "broad_relationships": broad,
        "scorecard": scorecard,
        "primary": {
            "joint_q90_brier": g2._weighted_score(
                scorecard, "joint_q90_brier",
            ),
            "variogram_p0_5": g2._weighted_score(
                scorecard, "variogram_p0_5",
            ),
            "g0_absolute_log_error_sum": g0_abs,
            "g0_cell_errors": g0_cells,
            "g1_weighted_absolute_log_error_sum": float(sum(
                row["weight"] * row["absolute_log_error"]
                for row in g1_cells.values()
            )),
            "g1_relationship_errors": g1_cells,
        },
    }


def _emit(report: dict[str, Any]) -> None:
    meta, chunks = g1.encode_report_transport(report)
    print(OUTPUT_META_PREFIX + json.dumps(meta, sort_keys=True), flush=True)
    for index, chunk in enumerate(chunks):
        print(f"{OUTPUT_CHUNK_PREFIX}{index}/{len(chunks)}:{chunk}", flush=True)


def run(panel_id: str) -> dict[str, Any]:
    expected_panel = os.environ.get("SIS_RECEIVER_COPULA_HELDOUT_PANEL", "").strip()
    evaluation_panel = os.environ.get(
        "SIS_RECEIVER_COPULA_HELDOUT_EVALUATION_PANEL", "",
    ).strip()
    if (
        panel_id != expected_panel
        or panel_id != gate.REFERENCE_HISTORICAL_PANEL
        or evaluation_panel != gate.REFERENCE_EVALUATION_PANEL
    ):
        raise ValueError("receiver-copula held-out panels differ")
    runtime = _runtime_identity()
    reference = _attestation("REFERENCE")
    calibration_attestation = _attestation("CALIBRATION")
    strength = _validate_attestations(
        reference, calibration_attestation, panel_id,
    )

    games = g2._load_games()
    frame, control, terminal = g1._load_terminal_book(panel_id)
    control_score = g2.score_heldout(frame, control, games)
    control_reproduction = {
        "score_sha256": _canonical_sha256(control_score),
        "frame_sha256": gate._frame_sha256(frame),
        "draws_sha256": gate._draw_sha256(control),
        "terminal_sha256": _canonical_sha256(terminal),
    }
    reference_reproduced = bool(all(
        control_reproduction[key] == reference[f"{key}"]
        for key in control_reproduction
    ))
    profiles, defense, source_audit = calibration.load_context(HELDOUT_SEASONS)
    receiver_scores, eligible, context_audit = treatment.build_receiver_context(
        frame, profiles, defense,
    )
    treated, treatment_audit = treatment.apply_receiver_copula(
        control, frame, receiver_scores, eligible, strength=strength,
    )
    repeated, repeated_audit = treatment.apply_receiver_copula(
        control, frame, receiver_scores, eligible, strength=strength,
    )
    changed = np.not_equal(control, treated)
    target_week = frame.week.astype(int).isin(calibration.TARGET_WEEKS).to_numpy(bool)
    invariants = {
        "fresh_reference_reproduced": reference_reproduced,
        "finite_output": bool(np.isfinite(treated).all()),
        "exact_sorted_marginals": calibration._marginals_equal(control, treated),
        "ineligible_rows_unchanged": bool(np.array_equal(
            control[~eligible], treated[~eligible],
        )),
        "only_eligible_wrs_change": bool(
            not changed[~eligible].any()
            and not changed[~frame.position.eq("WR").to_numpy(bool)].any()
        ),
        "only_weeks_5_18_change": bool(not changed[~target_week].any()),
        "treatment_bit_exact_on_repeat": bool(
            np.array_equal(treated, repeated)
            and treatment_audit == repeated_audit
        ),
        "maximum_mean_delta_at_most_1e_10": bool(
            treatment_audit["maximum_mean_delta"] <= 1e-10
        ),
        "strictly_prior_sources": bool(source_audit.get("strictly_prior")),
    }
    invariants["passes"] = bool(all(invariants.values()))
    treatment_score = g2.score_heldout(frame, treated, games)
    decision = gate.gate_decision(
        control_score, treatment_score,
        invariants_pass=invariants["passes"],
        selected_strength=strength,
        treatment_audit=treatment_audit,
    )
    by_season = {}
    for season in HELDOUT_SEASONS:
        mask = frame.season.astype(int).eq(season).to_numpy(bool)
        season_frame = frame.loc[mask].reset_index(drop=True)
        by_season[str(season)] = {
            "control": score_season(season_frame, control[mask], games),
            "treatment": score_season(season_frame, treated[mask], games),
        }
    report = {
        "version": VERSION,
        "run_identity": runtime,
        "historical_panel": panel_id,
        "evaluation_panel": evaluation_panel,
        "reference_attestation": reference,
        "calibration_attestation": calibration_attestation,
        "selected_strength": strength,
        "sources": source_audit,
        "context": context_audit,
        "control_reproduction": control_reproduction,
        "control": control_score,
        "treatment": treatment_score,
        "treatment_audit": treatment_audit,
        "invariants": invariants,
        "by_season": by_season,
        "paired_whole_slate_bootstrap": g2.paired_primary_bootstrap(
            frame, control, treated, games,
        ),
        **decision,
    }
    _emit(report)
    return report


__all__ = ["run", "score_season"]
