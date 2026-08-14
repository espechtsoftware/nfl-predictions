"""Terminal score-free TD-ledger rank-coupling repair."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

import numpy as np

from . import final_served_dependence as g0
from . import g1_archetype_topology as g1
from . import g2_qb_gumbel_factor as g2
from . import td_ledger_final_served as prior


OUTPUT_META_PREFIX = "TD_LEDGER_RANK_COUPLING_META="
OUTPUT_CHUNK_PREFIX = "TD_LEDGER_RANK_COUPLING_CHUNK="


def rank_couple_marginals(
    control_draws: np.ndarray,
    rank_source_draws: np.ndarray,
) -> np.ndarray:
    """Permute each control marginal by stable rank-source world order."""
    control = np.asarray(control_draws)
    source = np.asarray(rank_source_draws)
    if control.ndim != 2 or control.shape != source.shape:
        raise ValueError("control and rank-source draws differ")
    if not np.isfinite(control).all() or not np.isfinite(source).all():
        raise ValueError("control or rank-source draws are nonfinite")
    treatment = np.empty_like(control)
    for row in range(len(control)):
        world_order = np.argsort(source[row], kind="stable")
        treatment[row, world_order] = np.sort(control[row], kind="stable")
    return treatment


def _load_reference(path: Path, environment_name: str) -> dict:
    expected = os.environ.get(environment_name, "").strip()
    if not expected:
        raise ValueError(f"rank-coupling environment {environment_name} is missing")
    if sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"rank-coupling prerequisite {path.name} hash differs")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _remap_decision(decision: dict) -> dict:
    mapping = {
        "td-ledger-dependence-gate-passes": "td-ledger-rank-coupling-gate-passes",
        "td-ledger-dependence-gate-fails": "td-ledger-rank-coupling-gate-fails",
        "td-ledger-invalid-or-inconclusive": (
            "td-ledger-rank-coupling-invalid-or-inconclusive"
        ),
    }
    disposition = mapping[decision["disposition"]]
    return {
        **decision,
        "disposition": disposition,
        "exact80_licensed": disposition == "td-ledger-rank-coupling-gate-passes",
    }


def run(panel_id: str) -> dict:
    expected_panel = os.environ.get("TD_LEDGER_RANK_PANEL_ID", "").strip()
    if not expected_panel or panel_id != expected_panel:
        raise ValueError("rank-coupling panel differs from terminal selection")
    root = Path(os.environ.get("TD_LEDGER_REFERENCE_ROOT", "/app/reports"))
    g0_reference = _load_reference(
        root / "g0-dependence-runs/20260812-g0-final-served-dependence-v2/report.json",
        "TD_LEDGER_RANK_G0_REPORT_SHA256",
    )
    g1_reference = _load_reference(
        root / "g1-topology-runs/20260812-g1-archetype-topology-v3/report.json",
        "TD_LEDGER_RANK_G1_REPORT_SHA256",
    )
    if g1_reference.get("disposition") != "stable-qb-hub-confirmed":
        raise ValueError("rank-coupling lacks the terminal G1 premise")

    games = g2._load_games()
    control_frame, control_draws, control_terminal = g1._load_terminal_book(panel_id)
    control = g2.score_heldout(control_frame, control_draws, games)
    reproduction_failures = g2.validate_control_reproduction(
        control, g0_reference, g1_reference
    )

    source_frame, source_draws, source_terminal = g1._load_terminal_book(
        panel_id, simulator_overrides={"TD_LEDGER": "1"}
    )
    repeat_frame, repeat_draws, repeat_terminal = g1._load_terminal_book(
        panel_id, simulator_overrides={"TD_LEDGER": "1"}
    )
    alignment_failures = prior._frame_alignment_failures(control_frame, source_frame)
    alignment_failures.extend(
        f"repeat:{failure}"
        for failure in prior._frame_alignment_failures(source_frame, repeat_frame)
    )
    treatment_draws = rank_couple_marginals(control_draws, source_draws)
    repeated_treatment = rank_couple_marginals(control_draws, repeat_draws)
    exact_multisets = bool(all(
        np.array_equal(np.sort(control_row), np.sort(treatment_row))
        for control_row, treatment_row in zip(control_draws, treatment_draws)
    ))
    changed = np.not_equal(control_draws, treatment_draws)
    changed_rows = int(np.count_nonzero(changed.any(axis=1)))
    changed_cells = int(np.count_nonzero(changed))
    maximum_mean_delta = float(np.max(np.abs(
        np.asarray(control_draws).mean(axis=1, dtype=np.float64)
        - treatment_draws.mean(axis=1, dtype=np.float64)
    ), initial=0.0))
    deterministic = bool(
        np.array_equal(treatment_draws, repeated_treatment)
        and source_terminal == repeat_terminal
    )
    invariants = {
        "control_reproduction_failures": reproduction_failures,
        "frame_alignment_failures": alignment_failures,
        "control_terminal": control_terminal,
        "rank_source_terminal": source_terminal,
        "repeat_rank_source_terminal": repeat_terminal,
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

    treatment = g2.score_heldout(control_frame, treatment_draws, games)
    bootstrap = g2.paired_primary_bootstrap(
        control_frame, control_draws, treatment_draws, games
    )
    decision = _remap_decision(prior.gate_decision(
        control,
        treatment,
        invariants_pass=invariants["passes"],
        changed_rows=changed_rows,
    ))
    report = {
        "version": "td-ledger-rank-coupling-v1",
        "panel": panel_id,
        "adaptive_retrospective": True,
        "intervention": {
            "rank_source": {"TD_LEDGER": "1", "td_alloc_k": None},
            "marginal_source": "unchanged_incumbent_final_served",
            "rank_tie_rule": "stable_ascending_world_index",
        },
        "control": control,
        "treatment": treatment,
        "season_disclosures": {
            "control": prior._season_disclosures(control_frame, control_draws, games),
            "treatment": prior._season_disclosures(
                control_frame, treatment_draws, games
            ),
        },
        "bootstrap": bootstrap,
        "invariants": invariants,
        "material_regression_tolerance_abs_log": prior.MATERIAL_REGRESSION_TOLERANCE,
        **decision,
    }
    meta, chunks = g1.encode_report_transport(report)
    print(OUTPUT_META_PREFIX + json.dumps(meta, sort_keys=True), flush=True)
    for index, chunk in enumerate(chunks):
        print(f"{OUTPUT_CHUNK_PREFIX}{index}/{len(chunks)}:{chunk}", flush=True)
    return report


__all__ = ["rank_couple_marginals", "run"]
