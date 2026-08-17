"""Strict outcome-free completion contract for capacity book generation."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from .same_law_capacity_curve import BASE_FAMILIES
from .same_law_capacity_receipts import validate_attempt_ledgers


FORBIDDEN_KEYS = {
    "actual",
    "actual_score",
    "actual_rank",
    "candidate_score",
    "candidate_total",
    "capacity_metric",
    "distinct_yield",
    "minimum_replacement_distance",
    "ownership",
    "payout",
    "projection",
    "score",
    "selected",
    "support",
    "winnings",
}
EXPECTED_FAMILIES = tuple(sorted(BASE_FAMILIES))


def _reject_forbidden(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"capacity completion forbidden field {path}.{key}")
            _reject_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden(child, f"{path}[{index}]")


def _expected_cells(manifest: Mapping[str, Any]) -> dict[tuple[str, int, int], dict]:
    schedule = manifest.get("schedule")
    if not isinstance(schedule, list) or len(schedule) != 135:
        raise ValueError("capacity completion manifest schedule differs")
    result = {}
    for cell in schedule:
        if not isinstance(cell, Mapping):
            raise ValueError("capacity completion manifest cell differs")
        replicate = str(cell.get("replicate", ""))
        season = int(cell.get("season", -1))
        panel = str(cell.get("panel_run_id", ""))
        for week in range(1, 19):
            key = replicate, season, week
            if key in result:
                raise ValueError("capacity completion expected cell repeats")
            result[key] = {"panel_run_id": panel}
    if len(result) != 2430:
        raise ValueError("capacity completion expected population differs")
    return result


def validate_generation_completion(
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a complete 45-book generation before curve analysis."""
    _reject_forbidden(receipt)
    fixed = {
        "version": "same-law-capacity-generation-completion-v1",
        "run_id": "20260817-same-law-capacity-curve-v1",
        "disposition": "valid-complete-generation-population",
        "new_books": 45,
        "book_season_cells": 135,
        "book_slate_cells": 2430,
        "uses_realized_outcomes": False,
        "candidate_scores_inspected": False,
        "capacity_statistics_computed": False,
        "production_change_licensed": False,
    }
    exact_receipt_keys = set(fixed) | {
        "primary_executions",
        "retry_executions",
        "accepted_executions",
        "artifact_receipts",
        "candidate_mechanics",
    }
    if set(receipt) != exact_receipt_keys:
        raise ValueError("capacity generation completion fields differ")
    if any(receipt.get(key) != value for key, value in fixed.items()):
        raise ValueError("capacity generation completion identity differs")
    primary = receipt.get("primary_executions")
    retries = receipt.get("retry_executions")
    accepted = receipt.get("accepted_executions")
    if not all(isinstance(rows, list) for rows in (primary, retries, accepted)):
        raise ValueError("capacity generation attempt ledgers are missing")
    attempt = validate_attempt_ledgers(manifest, primary, retries, accepted)

    expected = _expected_cells(manifest)
    artifacts = receipt.get("artifact_receipts")
    mechanics = receipt.get("candidate_mechanics")
    if not isinstance(artifacts, list) or len(artifacts) != 2430 or \
            not isinstance(mechanics, list) or len(mechanics) != 2430:
        raise ValueError("capacity generation book/slate receipt count differs")
    artifact_by_cell = {}
    for row in artifacts:
        if not isinstance(row, Mapping):
            raise ValueError("capacity generation artifact receipt differs")
        exact = {
            "replicate", "season", "week", "panel_run_id", "uri",
            "generation", "bytes", "sha256",
        }
        if set(row) != exact:
            raise ValueError("capacity generation artifact receipt differs")
        key = str(row.get("replicate", "")), int(row.get("season", -1)), int(
            row.get("week", -1)
        )
        if key not in expected or key in artifact_by_cell:
            raise ValueError("capacity generation artifact cell differs")
        panel = expected[key]["panel_run_id"]
        uri = str(row.get("uri", ""))
        pattern = re.compile(
            rf"^gs://nfl-predictions-503414-raw/cand_scores/"
            rf"{re.escape(panel)}/{key[1]}_w{key[2]}_[0-9a-f]{{12}}\.npz$"
        )
        generation = str(row.get("generation", ""))
        sha = str(row.get("sha256", ""))
        if row.get("panel_run_id") != panel or pattern.fullmatch(uri) is None or \
                not generation.isdigit() or int(generation) <= 0 or \
                int(row.get("bytes", 0)) <= 0 or \
                re.fullmatch(r"[0-9a-f]{64}", sha) is None:
            raise ValueError("capacity generation artifact metadata differs")
        artifact_by_cell[key] = row
    if set(artifact_by_cell) != set(expected):
        raise ValueError("capacity generation artifact grid differs")

    mechanics_by_cell = {}
    for row in mechanics:
        if not isinstance(row, Mapping):
            raise ValueError("capacity generation mechanics receipt differs")
        key = str(row.get("replicate", "")), int(row.get("season", -1)), int(
            row.get("week", -1)
        )
        if key not in expected or key in mechanics_by_cell:
            raise ValueError("capacity generation mechanics cell differs")
        candidate_rows = int(row.get("candidate_rows", 0))
        exact = {
            "replicate", "season", "week", "panel_run_id", "candidate_rows",
            "minimum_cand_ix", "maximum_cand_ix", "distinct_cand_ix",
            "families_present", "all_rosters_nine_unique", "all_rosters_legal",
        }
        if set(row) != exact or row.get("panel_run_id") != \
                expected[key]["panel_run_id"] or candidate_rows <= 0 or \
                int(row.get("minimum_cand_ix", -1)) != 0 or \
                int(row.get("maximum_cand_ix", -1)) != candidate_rows - 1 or \
                int(row.get("distinct_cand_ix", -1)) != candidate_rows or \
                tuple(sorted(map(str, row.get("families_present", [])))) != \
                EXPECTED_FAMILIES or row.get("all_rosters_nine_unique") is not True or \
                row.get("all_rosters_legal") is not True:
            raise ValueError("capacity generation candidate mechanics differ")
        mechanics_by_cell[key] = row
    if set(mechanics_by_cell) != set(expected):
        raise ValueError("capacity generation mechanics grid differs")

    return {
        "version": "same-law-capacity-generation-validation-v1",
        "run_id": fixed["run_id"],
        "new_books": 45,
        "book_season_cells": 135,
        "book_slate_cells": 2430,
        "candidate_rows": int(sum(
            row["candidate_rows"] for row in mechanics_by_cell.values()
        )),
        "retry_executions": attempt["retry_executions"],
        "uses_realized_outcomes": False,
        "candidate_scores_inspected": False,
        "capacity_statistics_computed": False,
        "disposition": "valid-complete-generation-population",
    }


__all__ = [
    "EXPECTED_FAMILIES",
    "FORBIDDEN_KEYS",
    "validate_generation_completion",
]
