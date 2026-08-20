"""Mocked contract tests for the contingent exact-one-stack k=8 arm."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

from nfl_dfs.research.single_stack_k8_arm import (
    A2A_PASS_DISPOSITION,
    CONTROL_LEVERS,
    EXPECTED_CARVED_ADDITIONS,
    LATTICE,
    PROTOCOL_ID,
    PROTOCOL_STATUS,
    RECOVERY_CELL,
    TREATMENT_LEVERS,
    SingleStackArmError,
    canonical_json,
    evaluate_payload,
    treatment_environment,
)


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_single_stack_k8_arm as runner  # noqa: E402


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _identity(label: str) -> dict:
    return {
        "uri": f"mock://{label}",
        "generation": "123",
        "sha256": _digest(label),
        "bytes": 100,
    }


def _census(n: int) -> dict:
    return {
        "n": n,
        "qb_stack_counts": {"0": 0, "1": n, "2+": 0},
        "minimum_bring_back": 1 if n else None,
        "bring_back_zero": 0,
        "constraint_violations": 0,
        "primary_boom_tags": n,
        "secondary_single_stack_tags": n,
    }


def _block(season: int, week: int, block: int) -> dict:
    prefix = f"{season}-{week}-R{block}"
    return {
        "block": block,
        "source_identity": _identity(prefix),
        "control_a2a_draw_sha256": _digest(f"draw-{prefix}"),
        "treatment_a2a_draw_sha256": _digest(f"draw-{prefix}"),
        "control_environment_without_arm_sha256": _digest(f"env-{prefix}"),
        "treatment_environment_without_arm_sha256": _digest(f"env-{prefix}"),
        "control_candidate_count": 255,
        "treatment_candidate_count": 255,
        "single_stack_attempts": 8,
        "single_stack_added": 8,
        "single_stack_distinct": 8,
        "single_stack_roster_sha256s": [
            _digest(f"roster-{prefix}-{index}") for index in range(8)
        ],
        "single_stack_census": _census(8),
    }


def _exact80(selected: int = 1, intersection: int = 79) -> dict:
    return {
        "control_entry_count": 80,
        "treatment_entry_count": 80,
        "control_unique_entries": 80,
        "treatment_unique_entries": 80,
        "selected_book_intersection": intersection,
        "single_stack_selected_count": selected,
        "selected_single_stack_census": _census(selected),
    }


def _a2a_result() -> dict:
    return {
        "passes": True,
        "disposition": A2A_PASS_DISPOSITION,
        "licenses": {
            "uses_realized_outcomes": True,
            "actual_outcomes_queried": True,
            "candidate_or_lineup_scores_read": False,
            "single_stack_protocol_licensed": True,
            "single_stack_arm_licensed": False,
            "exact80_scoring_licensed": False,
            "prospective_shadow_licensed": False,
            "production_change_licensed": False,
        },
    }


def _payload(mode: str = "outcome-blind") -> dict:
    cells = []
    scored_index = 0
    for season, week in LATTICE:
        key = (season, week)
        blocks = (0, 1, 2, 4) if key == RECOVERY_CELL else (0, 1, 2, 3, 4)
        cell = {
            "season": season,
            "week": week,
            "blocks": [_block(season, week, block) for block in blocks],
            "exact80": None if key == RECOVERY_CELL else _exact80(),
        }
        if mode == "historical":
            if key == RECOVERY_CELL:
                cell["outcome"] = None
            else:
                control = 199.0 if scored_index < 2 else 180.0
                treatment = 200.0 if scored_index < 2 else 180.0
                cell["outcome"] = {
                    "actual_parity_max_delta": 0.0,
                    "control_candidate_max": 205.0,
                    "treatment_candidate_max": 205.0,
                    "control_weekly_max": control,
                    "treatment_weekly_max": treatment,
                }
                scored_index += 1
        cells.append(cell)
    return {
        "protocol_id": PROTOCOL_ID,
        "protocol_status": PROTOCOL_STATUS,
        "mode": mode,
        "a2a_result": _a2a_result(),
        "a2a_result_identity": _identity("a2a-result"),
        "control_levers": dict(CONTROL_LEVERS),
        "treatment_levers": dict(TREATMENT_LEVERS),
        "cells": cells,
    }


def test_treatment_environment_changes_only_single_stack_lever() -> None:
    control = {"N_BOOM": "40", "STACK_BRING_BACK": "1"}
    treatment = treatment_environment(control)
    assert control == {"N_BOOM": "40", "STACK_BRING_BACK": "1"}
    assert treatment == {
        "N_BOOM": "40",
        "STACK_BRING_BACK": "1",
        "OPEN_BOOM_SOLVES": "0",
        "SINGLE_STACK_BOOM_SOLVES": "8",
    }
    with pytest.raises(SingleStackArmError, match="OPEN_BOOM_SOLVES"):
        treatment_environment({"OPEN_BOOM_SOLVES": "1"})
    with pytest.raises(SingleStackArmError, match="SINGLE_STACK_BOOM_SOLVES"):
        treatment_environment({"SINGLE_STACK_BOOM_SOLVES": "8"})


def test_complete_outcome_blind_mechanics_are_accounted_without_license() -> None:
    report = evaluate_payload(_payload())
    assert report["disposition"] == "single-stack-outcome-blind-mechanics-pass"
    assert report["population"] == {
        "cells": 54,
        "scored_exact80_slates": 53,
        "block_cells": 269,
        "entries_per_book": 80,
        "dose_per_block": 8,
    }
    assert report["mechanism"]["exact_candidate_additions"] == (
        EXPECTED_CARVED_ADDITIONS
    )
    assert report["historical_gate"] is None
    assert not any(report["licenses"].values())


def test_outcome_blind_payload_rejects_outcome_field_recursively() -> None:
    payload = _payload()
    payload["cells"][0]["blocks"][0]["actual_score"] = 200.0
    with pytest.raises(SingleStackArmError, match="forbidden field"):
        evaluate_payload(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda block: block.update(single_stack_added=7), "k=8"),
        (
            lambda block: block["single_stack_census"]["qb_stack_counts"].update(
                {"0": 1, "1": 7}
            ),
            "not exact-one-stack",
        ),
        (
            lambda block: block["single_stack_census"].update(
                minimum_bring_back=0, bring_back_zero=8
            ),
            "bring-back",
        ),
        (lambda block: block.update(treatment_candidate_count=254), "budgets differ"),
        (
            lambda block: block.update(
                treatment_a2a_draw_sha256=_digest("different-draw")
            ),
            "different A2a draws",
        ),
        (
            lambda block: block.update(
                treatment_environment_without_arm_sha256=_digest("different-env")
            ),
            "differ outside",
        ),
    ],
)
def test_mechanical_defects_fail_closed(mutation, message: str) -> None:
    payload = _payload()
    mutation(payload["cells"][0]["blocks"][0])
    with pytest.raises(SingleStackArmError, match=message):
        evaluate_payload(payload)


def test_a2a_literal_pass_and_license_are_mandatory() -> None:
    payload = _payload()
    payload["a2a_result"]["passes"] = "true"
    with pytest.raises(SingleStackArmError, match="did not license"):
        evaluate_payload(payload)

    payload = _payload()
    payload["a2a_result"]["licenses"]["single_stack_protocol_licensed"] = False
    with pytest.raises(SingleStackArmError, match="literal True"):
        evaluate_payload(payload)


def test_historical_pass_requires_mean_two_200s_and_protected_tail() -> None:
    report = evaluate_payload(_payload("historical"))
    assert report["historical_gate"]["passes"] is True
    assert report["scores"]["control"]["threshold_counts"]["200"] == 0
    assert report["scores"]["treatment"]["threshold_counts"]["200"] == 2
    assert report["disposition"] == (
        "single-stack-historical-positive-shadow-design-licensed"
    )
    assert report["licenses"] == {
        "historical_arm_launch": False,
        "prospective_shadow_design": True,
        "prospective_shadow_run": False,
        "production": False,
        "dose_sweep": False,
    }


def test_one_lost_240_closes_the_historical_dose() -> None:
    payload = _payload("historical")
    scored = [
        cell for cell in payload["cells"]
        if (cell["season"], cell["week"]) != RECOVERY_CELL
    ]
    scored[2]["outcome"]["control_weekly_max"] = 240.0
    scored[2]["outcome"]["treatment_weekly_max"] = 239.0
    report = evaluate_payload(payload)
    assert report["historical_gate"]["mean_weekly_max_improves"] is True
    assert report["historical_gate"]["selected_ge240_noninferior"] is False
    assert report["historical_gate"]["passes"] is False
    assert report["licenses"]["prospective_shadow_design"] is False


def test_score_gain_without_selected_single_stack_fails_mechanism() -> None:
    payload = _payload("historical")
    for cell in payload["cells"]:
        if cell["exact80"] is not None:
            cell["exact80"] = _exact80(selected=0, intersection=80)
    report = evaluate_payload(payload)
    assert report["mechanism"]["reaches_selected_book"] is False
    assert report["historical_gate"]["mechanism_reaches_selected_book"] is False
    assert report["historical_gate"]["passes"] is False


def test_selected_single_and_changed_book_must_occur_on_same_slate() -> None:
    payload = _payload("historical")
    scored = [cell for cell in payload["cells"] if cell["exact80"] is not None]
    for cell in scored:
        cell["exact80"] = _exact80(selected=0, intersection=80)
    scored[0]["exact80"] = _exact80(selected=1, intersection=80)
    scored[1]["exact80"] = _exact80(selected=0, intersection=79)
    report = evaluate_payload(payload)
    assert report["mechanism"]["single_stack_selected_total"] == 1
    assert report["mechanism"]["changed_exact80_slates"] == 1
    assert report["mechanism"]["changed_slates_with_single_stack_selected"] == 0
    assert report["mechanism"]["reaches_selected_book"] is False
    assert report["historical_gate"]["passes"] is False


def test_lattice_is_exact_and_ordered() -> None:
    payload = _payload()
    payload["cells"][0], payload["cells"][1] = (
        payload["cells"][1], payload["cells"][0]
    )
    with pytest.raises(SingleStackArmError, match="lattice order"):
        evaluate_payload(payload)


def test_offline_runner_requires_canonical_local_input_and_create_only_output(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "report.json"
    input_path.write_bytes(canonical_json(_payload()))
    report = runner.run(input_path, output_path)
    assert json.loads(output_path.read_bytes()) == report
    with pytest.raises(FileExistsError):
        runner.run(input_path, output_path)

    noncanonical = tmp_path / "pretty.json"
    noncanonical.write_text(json.dumps(_payload(), indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="not canonical"):
        runner.run(noncanonical)
    with pytest.raises(ValueError, match="local path"):
        runner._local_path("gs://bucket/object", label="input")
