"""Pure accounting for the contingent exact-one-stack k=8 arm.

This module deliberately has no warehouse, object-store, optimizer, lineup,
or cloud imports.  A later transport may reconstruct paired candidate books
under the repaired A2a law and hand their accounting to this module.  Until
then it is only a fail-closed contract and decision scaffold.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import math
import re
from statistics import median
from typing import Any

from nfl_dfs.research.paired_max_stats import paired_weekly_max_report


PROTOCOL_ID = "20260820-single-stack-k8-under-a2a-v1"
PROTOCOL_STATUS = "READY-AWAITING-A2A"
A2A_PASS_DISPOSITION = (
    "a2a-law-shape-passes-single-stack-protocol-licensed"
)
DOSE = 8
ENTRIES = 80
THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)
LATTICE = tuple(
    (season, week)
    for season in (2023, 2024, 2025)
    for week in range(1, 19)
)
RECOVERY_CELL = (2025, 1)
SCORED_LATTICE = tuple(cell for cell in LATTICE if cell != RECOVERY_CELL)
EXPECTED_BLOCK_CELLS = 53 * 5 + 4
EXPECTED_CARVED_ADDITIONS = EXPECTED_BLOCK_CELLS * DOSE

CONTROL_LEVERS = {
    "OPEN_BOOM_SOLVES": "0",
    "SINGLE_STACK_BOOM_SOLVES": "0",
}
TREATMENT_LEVERS = {
    "OPEN_BOOM_SOLVES": "0",
    "SINGLE_STACK_BOOM_SOLVES": str(DOSE),
}

_SHA256 = re.compile(r"[0-9a-f]{64}")
_OUTCOME_KEYS = {
    "actual",
    "actual_score",
    "candidate_max",
    "contest_rank",
    "outcome",
    "payout",
    "settled_score",
    "weekly_max",
    "winner",
}


class SingleStackArmError(ValueError):
    """A fail-closed contract violation."""


def canonical_json(value: object) -> bytes:
    """Canonical JSON bytes used by local receipts and tests."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json(value)).hexdigest()


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise SingleStackArmError(f"{label} must be an exact integer >= {minimum}")
    return value


def _finite(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SingleStackArmError(f"{label} must be finite numeric")
    number = float(value)
    if not math.isfinite(number):
        raise SingleStackArmError(f"{label} must be finite numeric")
    return number


def _require_keys(
    value: Mapping[str, object], expected: set[str], *, label: str,
) -> None:
    if set(value) != expected:
        raise SingleStackArmError(
            f"{label} fields differ: expected {sorted(expected)}, "
            f"got {sorted(value)}"
        )


def _identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise SingleStackArmError(f"{label} is not an object identity")
    _require_keys(
        value, {"uri", "generation", "sha256", "bytes"}, label=label,
    )
    uri = value["uri"]
    generation = value["generation"]
    digest = value["sha256"]
    size = value["bytes"]
    if not isinstance(uri, str) or not uri or \
            not isinstance(generation, str) or not generation.isdigit() or \
            not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise SingleStackArmError(f"{label} identity differs")
    _exact_int(size, label=f"{label}.bytes", minimum=1)
    return dict(value)


def _require_bool(value: object, *, label: str, expected: bool) -> None:
    if not isinstance(value, bool) or value is not expected:
        raise SingleStackArmError(f"{label} must be literal {expected}")


def validate_a2a_prerequisite(
    result: object, result_identity: object,
) -> dict[str, object]:
    """Require the sole A2a disposition that may unlock this protocol.

    The A2a result is outcome-facing dependence evidence, but it is explicitly
    forbidden from having read candidate or lineup scores.  Its identity is
    supplied separately so a later transport can generation-pin the body.
    """
    _identity(result_identity, label="a2a_result_identity")
    if not isinstance(result, Mapping):
        raise SingleStackArmError("a2a_result is not an object")
    if result.get("disposition") != A2A_PASS_DISPOSITION or \
            result.get("passes") is not True:
        raise SingleStackArmError("A2a did not license the single-stack protocol")
    licenses = result.get("licenses")
    if not isinstance(licenses, Mapping):
        raise SingleStackArmError("A2a licenses are absent")
    expected = {
        "uses_realized_outcomes": True,
        "actual_outcomes_queried": True,
        "candidate_or_lineup_scores_read": False,
        "single_stack_protocol_licensed": True,
        "single_stack_arm_licensed": False,
        "exact80_scoring_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
    }
    if set(licenses) != set(expected):
        raise SingleStackArmError("A2a license fields differ")
    for key, wanted in expected.items():
        _require_bool(licenses.get(key), label=f"a2a licenses.{key}", expected=wanted)
    return {
        "disposition": A2A_PASS_DISPOSITION,
        "result_identity": dict(result_identity),
    }


def treatment_environment(control_environment: Mapping[str, str]) -> dict[str, str]:
    """Return the one-lever treatment environment without mutating input."""
    if not isinstance(control_environment, Mapping) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in control_environment.items()
    ):
        raise SingleStackArmError("control environment must map strings to strings")
    for key in CONTROL_LEVERS:
        raw = control_environment.get(key, "0")
        if raw != "0":
            raise SingleStackArmError(f"incumbent {key} must be exactly zero")
    treatment = dict(control_environment)
    treatment.update(TREATMENT_LEVERS)
    return treatment


def _find_outcome_key(value: object, path: str = "cells") -> str | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            child = f"{path}.{key}"
            if key_text in _OUTCOME_KEYS:
                return child
            found = _find_outcome_key(item, child)
            if found:
                return found
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            found = _find_outcome_key(item, f"{path}[{index}]")
            if found:
                return found
    return None


def _validate_census(
    value: object, *, expected_n: int, label: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise SingleStackArmError(f"{label} is not a census")
    _require_keys(value, {
        "n", "qb_stack_counts", "minimum_bring_back", "bring_back_zero",
        "constraint_violations", "primary_boom_tags",
        "secondary_single_stack_tags",
    }, label=label)
    if _exact_int(value["n"], label=f"{label}.n") != expected_n:
        raise SingleStackArmError(f"{label}.n differs")
    counts = value["qb_stack_counts"]
    if counts != {"0": 0, "1": expected_n, "2+": 0}:
        raise SingleStackArmError(f"{label} is not exact-one-stack")
    minimum_bring_back = value["minimum_bring_back"]
    if expected_n == 0:
        if minimum_bring_back is not None:
            raise SingleStackArmError(f"{label} empty minimum bring-back differs")
    elif _exact_int(
        minimum_bring_back, label=f"{label}.minimum_bring_back",
    ) < 1:
        raise SingleStackArmError(f"{label} drops the incumbent bring-back")
    for field in (
        "bring_back_zero", "constraint_violations",
    ):
        if _exact_int(value[field], label=f"{label}.{field}") != 0:
            raise SingleStackArmError(f"{label}.{field} must be zero")
    for field in ("primary_boom_tags", "secondary_single_stack_tags"):
        if _exact_int(value[field], label=f"{label}.{field}") != expected_n:
            raise SingleStackArmError(f"{label}.{field} differs")
    return dict(value)


def _validate_block(value: object, *, expected_block: int, label: str) -> dict:
    if not isinstance(value, Mapping):
        raise SingleStackArmError(f"{label} is not a block")
    _require_keys(value, {
        "block", "source_identity", "control_a2a_draw_sha256",
        "treatment_a2a_draw_sha256",
        "control_environment_without_arm_sha256",
        "treatment_environment_without_arm_sha256",
        "control_candidate_count", "treatment_candidate_count",
        "single_stack_attempts", "single_stack_added",
        "single_stack_distinct", "single_stack_roster_sha256s",
        "single_stack_census",
    }, label=label)
    if _exact_int(value["block"], label=f"{label}.block") != expected_block:
        raise SingleStackArmError(f"{label}.block differs")
    _identity(value["source_identity"], label=f"{label}.source_identity")
    for field in (
        "control_a2a_draw_sha256", "treatment_a2a_draw_sha256",
        "control_environment_without_arm_sha256",
        "treatment_environment_without_arm_sha256",
    ):
        digest = value[field]
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise SingleStackArmError(f"{label}.{field} differs")
    if value["control_a2a_draw_sha256"] != value["treatment_a2a_draw_sha256"]:
        raise SingleStackArmError(f"{label} arms use different A2a draws")
    if value["control_environment_without_arm_sha256"] != \
            value["treatment_environment_without_arm_sha256"]:
        raise SingleStackArmError(f"{label} arms differ outside the treatment lever")
    control_n = _exact_int(
        value["control_candidate_count"],
        label=f"{label}.control_candidate_count", minimum=1,
    )
    treatment_n = _exact_int(
        value["treatment_candidate_count"],
        label=f"{label}.treatment_candidate_count", minimum=1,
    )
    if control_n != treatment_n:
        raise SingleStackArmError(f"{label} candidate budgets differ")
    for field in (
        "single_stack_attempts", "single_stack_added", "single_stack_distinct",
    ):
        if _exact_int(value[field], label=f"{label}.{field}") != DOSE:
            raise SingleStackArmError(f"{label}.{field} differs from k={DOSE}")
    roster_hashes = value["single_stack_roster_sha256s"]
    if not isinstance(roster_hashes, list) or len(roster_hashes) != DOSE or \
            len(set(roster_hashes)) != DOSE or any(
                not isinstance(item, str) or _SHA256.fullmatch(item) is None
                for item in roster_hashes
            ):
        raise SingleStackArmError(f"{label} carved roster identities differ")
    _validate_census(
        value["single_stack_census"], expected_n=DOSE,
        label=f"{label}.single_stack_census",
    )
    return dict(value)


def _validate_exact80(value: object, *, label: str) -> dict:
    if not isinstance(value, Mapping):
        raise SingleStackArmError(f"{label} is not an exact-80 receipt")
    _require_keys(value, {
        "control_entry_count", "treatment_entry_count",
        "control_unique_entries", "treatment_unique_entries",
        "selected_book_intersection", "single_stack_selected_count",
        "selected_single_stack_census",
    }, label=label)
    for field in (
        "control_entry_count", "treatment_entry_count",
        "control_unique_entries", "treatment_unique_entries",
    ):
        if _exact_int(value[field], label=f"{label}.{field}") != ENTRIES:
            raise SingleStackArmError(f"{label}.{field} is not exact {ENTRIES}")
    intersection = _exact_int(
        value["selected_book_intersection"],
        label=f"{label}.selected_book_intersection",
    )
    if intersection > ENTRIES:
        raise SingleStackArmError(f"{label}.selected_book_intersection exceeds 80")
    selected = _exact_int(
        value["single_stack_selected_count"],
        label=f"{label}.single_stack_selected_count",
    )
    if selected > ENTRIES:
        raise SingleStackArmError(f"{label}.single_stack_selected_count exceeds 80")
    _validate_census(
        value["selected_single_stack_census"], expected_n=selected,
        label=f"{label}.selected_single_stack_census",
    )
    return dict(value)


def _expected_blocks(cell: tuple[int, int]) -> tuple[int, ...]:
    return (0, 1, 2, 4) if cell == RECOVERY_CELL else (0, 1, 2, 3, 4)


def _validate_cell(value: object, *, mode: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SingleStackArmError("cell is not an object")
    expected_fields = {"season", "week", "blocks", "exact80"}
    if mode == "historical":
        expected_fields.add("outcome")
    _require_keys(value, expected_fields, label="cell")
    season = _exact_int(value["season"], label="cell.season")
    week = _exact_int(value["week"], label="cell.week", minimum=1)
    key = (season, week)
    if key not in LATTICE:
        raise SingleStackArmError(f"cell {key} is outside the registered lattice")
    expected_blocks = _expected_blocks(key)
    blocks = value["blocks"]
    if not isinstance(blocks, list) or len(blocks) != len(expected_blocks):
        raise SingleStackArmError(f"cell {key} block population differs")
    validated_blocks = [
        _validate_block(block, expected_block=expected, label=f"cell {key} R{expected}")
        for block, expected in zip(blocks, expected_blocks, strict=True)
    ]

    if key == RECOVERY_CELL:
        if value["exact80"] is not None:
            raise SingleStackArmError("recovery cell must not claim an exact-80 book")
    else:
        _validate_exact80(value["exact80"], label=f"cell {key}.exact80")

    if mode == "historical":
        outcome = value["outcome"]
        if key == RECOVERY_CELL:
            if outcome is not None:
                raise SingleStackArmError("recovery cell must not read outcomes")
        else:
            if not isinstance(outcome, Mapping):
                raise SingleStackArmError(f"cell {key} historical outcome is absent")
            _require_keys(outcome, {
                "actual_parity_max_delta", "control_candidate_max",
                "treatment_candidate_max", "control_weekly_max",
                "treatment_weekly_max",
            }, label=f"cell {key}.outcome")
            if abs(_finite(
                outcome["actual_parity_max_delta"],
                label=f"cell {key}.actual_parity_max_delta",
            )) > 1e-9:
                raise SingleStackArmError(f"cell {key} actual-score parity failed")
            for field in (
                "control_candidate_max", "treatment_candidate_max",
                "control_weekly_max", "treatment_weekly_max",
            ):
                _finite(outcome[field], label=f"cell {key}.{field}")
    return {
        "key": key,
        "blocks": validated_blocks,
        "exact80": value["exact80"],
        "outcome": value.get("outcome"),
    }


def _score_summary(values: Sequence[float]) -> dict[str, object]:
    if len(values) != len(SCORED_LATTICE):
        raise SingleStackArmError("historical score population differs")
    return {
        "n": len(values),
        "mean_weekly_max": sum(values) / len(values),
        "median_weekly_max": median(values),
        "threshold_counts": {
            str(line): sum(value >= line for value in values)
            for line in THRESHOLDS
        },
    }


def evaluate_payload(payload: object) -> dict[str, Any]:
    """Validate and summarize one complete outcome-blind or historical body."""
    if not isinstance(payload, Mapping):
        raise SingleStackArmError("single-stack payload is not an object")
    _require_keys(payload, {
        "protocol_id", "protocol_status", "mode", "a2a_result",
        "a2a_result_identity", "control_levers", "treatment_levers", "cells",
    }, label="payload")
    if payload["protocol_id"] != PROTOCOL_ID or \
            payload["protocol_status"] != PROTOCOL_STATUS:
        raise SingleStackArmError("single-stack protocol identity/status differs")
    mode = payload["mode"]
    if mode not in {"outcome-blind", "historical"}:
        raise SingleStackArmError("single-stack mode differs")
    if payload["control_levers"] != CONTROL_LEVERS or \
            payload["treatment_levers"] != TREATMENT_LEVERS:
        raise SingleStackArmError("single-stack lever contrast differs")
    prerequisite = validate_a2a_prerequisite(
        payload["a2a_result"], payload["a2a_result_identity"],
    )
    cells = payload["cells"]
    if not isinstance(cells, list) or len(cells) != len(LATTICE):
        raise SingleStackArmError("single-stack cell population differs")
    if mode == "outcome-blind":
        found = _find_outcome_key(cells)
        if found:
            raise SingleStackArmError(
                f"outcome-blind payload contains forbidden field {found}"
            )
    validated = [_validate_cell(cell, mode=mode) for cell in cells]
    keys = [cell["key"] for cell in validated]
    if tuple(keys) != LATTICE:
        raise SingleStackArmError("single-stack lattice order/population differs")
    block_cells = sum(len(cell["blocks"]) for cell in validated)
    carved = block_cells * DOSE
    if block_cells != EXPECTED_BLOCK_CELLS or carved != EXPECTED_CARVED_ADDITIONS:
        raise SingleStackArmError("single-stack support accounting differs")

    scored_cells = [cell for cell in validated if cell["key"] != RECOVERY_CELL]
    selected_total = sum(
        int(cell["exact80"]["single_stack_selected_count"])
        for cell in scored_cells
    )
    selected_slates = sum(
        int(cell["exact80"]["single_stack_selected_count"]) > 0
        for cell in scored_cells
    )
    changed_slates = sum(
        int(cell["exact80"]["selected_book_intersection"]) < ENTRIES
        for cell in scored_cells
    )
    linked_slates = sum(
        int(cell["exact80"]["single_stack_selected_count"]) > 0
        and int(cell["exact80"]["selected_book_intersection"]) < ENTRIES
        for cell in scored_cells
    )
    mechanism = {
        "exact_candidate_additions": carved,
        "expected_candidate_additions": EXPECTED_CARVED_ADDITIONS,
        "single_stack_selected_total": selected_total,
        "slates_with_single_stack_selected": selected_slates,
        "changed_exact80_slates": changed_slates,
        "changed_slates_with_single_stack_selected": linked_slates,
        "exact_one_and_bring_back_preserved": True,
        "reaches_selected_book": linked_slates > 0,
    }
    base = {
        "protocol_id": PROTOCOL_ID,
        "protocol_status": PROTOCOL_STATUS,
        "mode": mode,
        "a2a_prerequisite": prerequisite,
        "population": {
            "cells": len(validated),
            "scored_exact80_slates": len(scored_cells),
            "block_cells": block_cells,
            "entries_per_book": ENTRIES,
            "dose_per_block": DOSE,
        },
        "support_gates": {
            "exact_54_cell_lattice": True,
            "exact_269_block_cells": True,
            "equal_candidate_budget_every_block": True,
            "exact_8_distinct_additions_every_block": True,
            "exact_one_stack_every_addition": True,
            "incumbent_bring_back_and_protected_constraints_preserved": True,
            "exact_80_both_arms_on_53_scored_slates": True,
            "recovery_cell_has_no_outcome_or_exact80_claim": True,
        },
        "mechanism": mechanism,
        "production_change_licensed": False,
    }
    if mode == "outcome-blind":
        return {
            **base,
            "disposition": (
                "single-stack-outcome-blind-mechanics-pass"
                if mechanism["reaches_selected_book"]
                else "single-stack-outcome-blind-selector-vacuity"
            ),
            "historical_gate": None,
            "licenses": {
                "historical_arm_launch": False,
                "prospective_shadow_design": False,
                "prospective_shadow_run": False,
                "production": False,
                "dose_sweep": False,
            },
        }

    control = [float(cell["outcome"]["control_weekly_max"])
               for cell in scored_cells]
    treatment = [float(cell["outcome"]["treatment_weekly_max"])
                 for cell in scored_cells]
    control_candidate = [float(cell["outcome"]["control_candidate_max"])
                         for cell in scored_cells]
    treatment_candidate = [float(cell["outcome"]["treatment_candidate_max"])
                           for cell in scored_cells]
    control_summary = _score_summary(control)
    treatment_summary = _score_summary(treatment)
    c_counts = control_summary["threshold_counts"]
    t_counts = treatment_summary["threshold_counts"]
    gates = {
        "mechanism_reaches_selected_book": mechanism["reaches_selected_book"],
        "mean_weekly_max_improves": (
            treatment_summary["mean_weekly_max"]
            > control_summary["mean_weekly_max"]
        ),
        "selected_ge200_adds_at_least_two": t_counts["200"] >= c_counts["200"] + 2,
        "selected_ge194_noninferior": t_counts["194"] >= c_counts["194"],
        "selected_ge210_noninferior": t_counts["210"] >= c_counts["210"],
        "selected_ge220_noninferior": t_counts["220"] >= c_counts["220"],
        "selected_ge230_noninferior": t_counts["230"] >= c_counts["230"],
        "selected_ge240_noninferior": t_counts["240"] >= c_counts["240"],
        "candidate_ge200_noninferior": sum(
            value >= 200 for value in treatment_candidate
        ) >= sum(value >= 200 for value in control_candidate),
    }
    passed = all(gates.values())
    disposition = (
        "single-stack-historical-positive-shadow-design-licensed"
        if passed
        else "single-stack-historical-not-supported-closed-at-k8"
    )
    return {
        **base,
        "disposition": disposition,
        "scores": {
            "control": control_summary,
            "treatment": treatment_summary,
            "paired": paired_weekly_max_report(
                control, treatment, slate_keys=[f"{s}-{w}" for s, w in SCORED_LATTICE],
            ),
            "candidate_ge200": {
                "control": sum(value >= 200 for value in control_candidate),
                "treatment": sum(value >= 200 for value in treatment_candidate),
            },
        },
        "historical_gate": {**gates, "passes": passed},
        "licenses": {
            "historical_arm_launch": False,
            "prospective_shadow_design": passed,
            "prospective_shadow_run": False,
            "production": False,
            "dose_sweep": False,
        },
    }
