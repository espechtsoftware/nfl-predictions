"""Paired outcome-unseen runner for the 2026 boom-first candidate shadow.

The two arms intentionally run the complete live pipeline independently.  The
only candidate-generation change is the requested split of the same 200 core
optimizer solves: 160 leverage + 40 boom for control and 40 leverage + 160
boom for treatment.  Candidate deduplication is allowed to produce different
pool sizes; the simulated player worlds and every selection setting remain
paired.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from dataclasses import replace
from datetime import datetime, timezone
from numbers import Integral
from typing import Mapping, Sequence

import numpy as np

from ..backtest.engine import CandidateBatch, _validate_candidate_batch
from ..config import settings
from ..optimizer.lineup import (
    MAX_FROM_TEAM,
    INCUMBENT_MIN_GAMES,
    ROSTER_SIZE,
    SALARY_CAP,
    Lineup,
    StackRules,
    select_tail_entries,
)
from .production_policy import ADOPTED_CLASSIC_POLICY
from .prospective_shadow import _canonical_dk_roster, _validated_code_sha
from .recourse_worlds import persist_recourse_world_artifact


VERSION = "prospective-boom-first-paired-shadow-v1"
TERMINAL_SCHEMA = "prospective-boom-first-paired-terminal/v1"
PAIRED_NATIVE_INPUT_AUTHORITY_SCHEMA = (
    "prospective-generation-paired-native-input-authority/v1"
)
NATIVE_INPUT_SOURCE_PROJECTION_SCHEMA = (
    "prospective-generation-native-input-source-projection/v1"
)
ENTRIES = 80
TAIL_LINE = 194.0
CONTROL_ALLOCATION = {
    "leverage_requested": 160,
    "boom_requested": 40,
    "core_requested": 200,
    "ce_requested": 0,
    "role_or_epistemic_requested": 12,
    "gumbel_requested": 0,
    "total_requested_with_replacement_families": 212,
}
TREATMENT_ALLOCATION = {
    "leverage_requested": 40,
    "boom_requested": 160,
    "core_requested": 200,
    "ce_requested": 0,
    "role_or_epistemic_requested": 12,
    "gumbel_requested": 0,
    "total_requested_with_replacement_families": 212,
}
_SEED_LABELS = ("R0", "R1", "R2", "R3", "R4")
_IMAGE_URI = re.compile(
    r"^[a-z0-9.-]+/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CLOUD_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_ARM_ENV_DIFFERENCES = frozenset({
    "N_LEV",
    "N_BOOM",
    "GEN_TOTAL_BUDGET",
    "PROSPECTIVE_SHADOW_ID",
    "BOOM_FIRST_ARM",
})


def _validated_image_uri(value: object) -> str:
    image_uri = str(value or "").strip()
    if _IMAGE_URI.fullmatch(image_uri) is None:
        raise ValueError(
            "boom-first paired shadow requires an immutable IMAGE_URI"
        )
    return image_uri


def _validated_cloud_execution_context(env: Mapping[str, str]) -> dict[str, object]:
    """Bind one non-retried Cloud Run task to its immutable result root."""
    job = str(env.get("CLOUD_RUN_JOB") or "").strip()
    execution = str(env.get("CLOUD_RUN_EXECUTION") or "").strip()
    task_index = str(env.get("CLOUD_RUN_TASK_INDEX") or "").strip()
    task_attempt = str(env.get("CLOUD_RUN_TASK_ATTEMPT") or "").strip()
    if _CLOUD_NAME.fullmatch(job) is None:
        raise ValueError("boom-first paired shadow requires CLOUD_RUN_JOB")
    if _CLOUD_NAME.fullmatch(execution) is None:
        raise ValueError("boom-first paired shadow requires CLOUD_RUN_EXECUTION")
    if task_index != "0" or task_attempt != "0":
        raise ValueError(
            "boom-first paired shadow requires task index 0 and attempt 0"
        )
    return {
        "cloud_run_job": job,
        "cloud_run_execution": execution,
        "cloud_run_task_index": 0,
        "cloud_run_task_attempt": 0,
    }


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _array_receipt(value: np.ndarray) -> dict[str, object]:
    array = np.ascontiguousarray(value)
    header = json.dumps({
        "dtype": array.dtype.str,
        "shape": list(array.shape),
    }, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload = header + b"\n" + array.tobytes(order="C")
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "bytes": int(array.nbytes),
    }


def selected_model_receipt(
    control_lineups: Sequence[Lineup],
    treatment_lineups: Sequence[Lineup],
) -> dict[str, str]:
    """Bind the exact main and role registries loaded by both arms."""
    per_arm: dict[str, dict[str, str]] = {}
    for arm, lineups in (
        ("control", control_lineups),
        ("treatment", treatment_lineups),
    ):
        main = {
            str(getattr(lineup, "model_version", "") or "")
            for lineup in lineups
        }
        role = {
            str(getattr(lineup, "role_model_version", "") or "")
            for lineup in lineups
        }
        if len(main) != 1 or not next(iter(main)):
            raise ValueError(f"boom-first {arm} main model version is not singular")
        if len(role) != 1 or not next(iter(role)):
            raise ValueError(f"boom-first {arm} role model version is not singular")
        per_arm[arm] = {
            "model_version": next(iter(main)),
            "role_model_version": next(iter(role)),
        }
    if per_arm["control"] != per_arm["treatment"]:
        raise ValueError("boom-first control/treatment model versions differ")
    return per_arm["control"]


def _slate_identity(store, draft_group_id: int):
    salaries = store.classic_salaries(draft_group_id).drop_duplicates(
        "dk_player_id"
    )
    required = {"dk_player_id", "dk_draftable_id", "salary"}
    if salaries.empty or required - set(salaries.columns):
        raise RuntimeError("boom-first salary snapshot is incomplete")
    if salaries[list(required)].isna().any().any():
        raise RuntimeError("boom-first salary identity is incomplete")
    allowed = {int(value) for value in salaries.dk_player_id}
    salary_overrides = {
        int(row.dk_player_id): int(row.salary) for row in salaries.itertuples()
    }
    dk_mapping = {
        int(row.dk_player_id): str(int(row.dk_draftable_id))
        for row in salaries.itertuples()
    }
    return allowed, salary_overrides, dk_mapping


def _canonical_nonnegative_int(value: object, label: str) -> int:
    if not isinstance(value, Integral) or isinstance(value, bool):
        raise ValueError(f"{label} is not an integer")
    resolved = int(value)
    if resolved < 0:
        raise ValueError(f"{label} is negative")
    return resolved


def _validated_input_receipt(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not a mapping")
    if set(value) != {"sha256", "rows", "columns"}:
        raise ValueError(f"{label} fields differ")
    digest = str(value.get("sha256") or "").strip().lower()
    rows = _canonical_nonnegative_int(value.get("rows"), f"{label} rows")
    raw_columns = value.get("columns")
    if _SHA256.fullmatch(digest) is None or rows < 1:
        raise ValueError(f"{label} identity differs")
    if (
        not isinstance(raw_columns, list)
        or not raw_columns
        or any(not isinstance(column, str) or not column for column in raw_columns)
        or len(set(raw_columns)) != len(raw_columns)
        or raw_columns != sorted(raw_columns)
    ):
        raise ValueError(f"{label} columns differ")
    return {
        "sha256": digest,
        "rows": rows,
        "columns": list(raw_columns),
    }


def _source_authority_sha256(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("native input authority is not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _validated_construction_preset_receipt(
    value: object, label: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not a mapping")
    receipt = dict(value)
    if set(receipt) != {
        "schema_version", "base_preset_id", "stack", "min_salary",
        "min_games", "punt_min", "punt_max_salary", "punt_strict",
        "value2_min", "value2_max", "own_barbell", "own_barbell_low",
        "own_barbell_high", "own_barbell_nlow", "own_barbell_nhigh",
        "max_per_game", "min_lowown", "max_overlap", "effective_id",
        "sha256",
    }:
        raise ValueError(f"{label} fields differ")
    digest = str(receipt.pop("sha256", "")).strip().lower()
    effective_id = str(receipt.pop("effective_id", "")).strip()
    preset_id = str(receipt.get("base_preset_id") or "").strip()
    if (
        receipt.get("schema_version") != "classic-construction-preset-v1"
        or _SHA256.fullmatch(digest) is None
        or not preset_id
        or effective_id != f"{preset_id}@sha256:{digest}"
        or _source_authority_sha256(receipt) != digest
    ):
        raise ValueError(f"{label} identity differs")
    return {**receipt, "effective_id": effective_id, "sha256": digest}


def native_input_source_projection(
    value: object, *, label: str = "native generation receipt",
) -> dict[str, object]:
    """Normalize the score-blind model/player/construction source identity."""

    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not a mapping")
    model_version = str(value.get("model_version") or "").strip()
    role_model_version = str(value.get("role_model_version") or "").strip()
    if not model_version or not role_model_version:
        raise ValueError(f"{label} model source identity is incomplete")
    candidate_input = _validated_input_receipt(
        value.get("candidate_input_receipt"),
        f"{label} candidate input receipt",
    )
    role_candidate_input = _validated_input_receipt(
        value.get("role_candidate_input_receipt"),
        f"{label} role candidate input receipt",
    )
    if "id" not in candidate_input["columns"] or "id" not in (
        role_candidate_input["columns"]
    ):
        raise ValueError(f"{label} player input receipt lacks id")
    construction = _validated_construction_preset_receipt(
        value.get("construction_preset_receipt"),
        f"{label} construction preset receipt",
    )
    return {
        "schema_version": NATIVE_INPUT_SOURCE_PROJECTION_SCHEMA,
        "model_version": model_version,
        "role_model_version": role_model_version,
        "candidate_input_receipt": candidate_input,
        "role_candidate_input_receipt": role_candidate_input,
        "construction_preset_receipt": construction,
    }


def validate_paired_native_input_authority(
    value: object,
    *,
    expected_arm_order: Sequence[str] | None = None,
    expected_block_labels: Sequence[str] | None = None,
) -> dict[str, object]:
    """Validate one self-hashed all-arm/all-block input-source authority."""

    if not isinstance(value, Mapping):
        raise ValueError("paired native input authority is not a mapping")
    item = dict(value)
    fields = {
        "schema_version", "arm_order", "block_labels",
        "native_source_projection", "native_source_projection_sha256",
        "native_source_projection_sha256_by_arm",
        "effective_player_source_identity", "effective_model_source_identity",
        "effective_construction_source_identity",
        "all_arm_blocks_byte_identical_inputs", "uses_realized_outcomes",
        "post_lock_data_read", "authority_sha256",
    }
    if set(item) != fields:
        raise ValueError("paired native input authority fields differ")
    retained_hash = str(item.pop("authority_sha256", "")).strip().lower()
    if (
        item.get("schema_version") != PAIRED_NATIVE_INPUT_AUTHORITY_SCHEMA
        or _SHA256.fullmatch(retained_hash) is None
        or _source_authority_sha256(item) != retained_hash
    ):
        raise ValueError("paired native input authority hash differs")
    arms = item.get("arm_order")
    blocks = item.get("block_labels")
    if (
        not isinstance(arms, list)
        or not arms
        or any(not isinstance(arm, str) or not arm for arm in arms)
        or len(set(arms)) != len(arms)
        or not isinstance(blocks, list)
        or not blocks
        or any(not isinstance(block, str) or not block for block in blocks)
        or len(set(blocks)) != len(blocks)
    ):
        raise ValueError("paired native input authority grid differs")
    if expected_arm_order is not None and arms != list(expected_arm_order):
        raise ValueError("paired native input authority arm order differs")
    if expected_block_labels is not None and blocks != list(
        expected_block_labels
    ):
        raise ValueError("paired native input authority block order differs")
    projection = native_input_source_projection(
        item.get("native_source_projection"),
        label="paired native reference source",
    )
    projection_hash = _source_authority_sha256(projection)
    if item.get("native_source_projection_sha256") != projection_hash:
        raise ValueError("paired native reference source hash differs")
    grid = item.get("native_source_projection_sha256_by_arm")
    if not isinstance(grid, Mapping) or set(grid) != set(arms):
        raise ValueError("paired native input authority arm grid differs")
    for arm in arms:
        arm_grid = grid.get(arm)
        if not isinstance(arm_grid, Mapping) or set(arm_grid) != set(blocks):
            raise ValueError(f"paired native input authority {arm} grid differs")
        if any(value != projection_hash for value in arm_grid.values()):
            raise ValueError(f"paired native input authority {arm} source drift")
    player = item.get("effective_player_source_identity")
    expected_player = {
        "candidate_input_receipt": projection["candidate_input_receipt"],
        "role_candidate_input_receipt": projection[
            "role_candidate_input_receipt"
        ],
    }
    if not isinstance(player, Mapping) or set(player) != {
        *expected_player,
        "player_count", "internal_player_id_order_sha256",
        "artifact_player_id_order_sha256",
    }:
        raise ValueError("paired effective player source identity differs")
    if (
        player.get("candidate_input_receipt")
        != expected_player["candidate_input_receipt"]
        or player.get("role_candidate_input_receipt")
        != expected_player["role_candidate_input_receipt"]
        or type(player.get("player_count")) is not int
        or int(player["player_count"]) < 1
        or int(player["player_count"])
        != projection["candidate_input_receipt"]["rows"]
        or int(player["player_count"])
        != projection["role_candidate_input_receipt"]["rows"]
        or any(
            _SHA256.fullmatch(str(player.get(field) or "")) is None
            for field in (
                "internal_player_id_order_sha256",
                "artifact_player_id_order_sha256",
            )
        )
    ):
        raise ValueError("paired effective player source identity is incomplete")
    if item.get("effective_model_source_identity") != {
        "model_version": projection["model_version"],
        "role_model_version": projection["role_model_version"],
    }:
        raise ValueError("paired effective model source identity differs")
    construction = projection["construction_preset_receipt"]
    if item.get("effective_construction_source_identity") != {
        "effective_id": construction["effective_id"],
        "sha256": construction["sha256"],
    }:
        raise ValueError("paired effective construction source identity differs")
    if (
        item.get("all_arm_blocks_byte_identical_inputs") is not True
        or item.get("uses_realized_outcomes") is not False
        or item.get("post_lock_data_read") is not False
    ):
        raise ValueError("paired native input authority fixed law differs")
    return {**item, "authority_sha256": retained_hash}


def build_paired_native_input_authority(
    batches: Mapping[str, CandidateBatch],
    *,
    arm_order: Sequence[str],
    block_labels: Sequence[str],
    artifact_player_id_by_player_id: Mapping[object, str | int],
) -> dict[str, object]:
    """Prove every native arm/block used one byte-identical input source."""

    arms = list(arm_order)
    blocks = list(block_labels)
    if set(batches) != set(arms):
        raise ValueError("paired native input batch arm grid differs")
    reference: dict[str, object] | None = None
    reference_internal_order: list[str] | None = None
    reference_artifact_order: list[str] | None = None
    grid: dict[str, dict[str, str]] = {}
    for arm in arms:
        batch = batches[arm]
        _validate_candidate_batch(batch)
        internal_order = [str(player_id) for player_id in batch.player_ids]
        try:
            artifact_order = [
                str(artifact_player_id_by_player_id[player_id])
                for player_id in batch.player_ids
            ]
        except KeyError as exc:
            raise ValueError(
                f"paired native input authority {arm} lacks artifact player ID"
            ) from exc
        if (
            any(not value for value in artifact_order)
            or len(set(artifact_order)) != len(artifact_order)
        ):
            raise ValueError(f"paired native input authority {arm} player IDs differ")
        if reference_internal_order is None:
            reference_internal_order = internal_order
            reference_artifact_order = artifact_order
        elif (
            internal_order != reference_internal_order
            or artifact_order != reference_artifact_order
        ):
            raise ValueError(f"paired native input authority {arm} player order drift")
        receipts = batch.metadata.get("native_generation_receipts")
        if not isinstance(receipts, Mapping) or set(receipts) != set(blocks):
            raise ValueError(f"paired native input authority {arm} block grid differs")
        grid[arm] = {}
        for block in blocks:
            projection = native_input_source_projection(
                receipts[block], label=f"{arm}/{block} native generation receipt",
            )
            if projection["candidate_input_receipt"]["rows"] != len(
                batch.player_ids
            ) or projection["role_candidate_input_receipt"]["rows"] != len(
                batch.player_ids
            ):
                raise ValueError(f"paired native input authority {arm}/{block} row drift")
            if reference is None:
                reference = projection
            elif projection != reference:
                raise ValueError(
                    f"paired native input authority {arm}/{block} source drift"
                )
            grid[arm][block] = _source_authority_sha256(projection)
    if (
        reference is None
        or reference_internal_order is None
        or reference_artifact_order is None
    ):
        raise ValueError("paired native input authority is empty")
    projection_hash = _source_authority_sha256(reference)
    construction = reference["construction_preset_receipt"]
    body: dict[str, object] = {
        "schema_version": PAIRED_NATIVE_INPUT_AUTHORITY_SCHEMA,
        "arm_order": arms,
        "block_labels": blocks,
        "native_source_projection": reference,
        "native_source_projection_sha256": projection_hash,
        "native_source_projection_sha256_by_arm": grid,
        "effective_player_source_identity": {
            "candidate_input_receipt": reference["candidate_input_receipt"],
            "role_candidate_input_receipt": reference[
                "role_candidate_input_receipt"
            ],
            "player_count": len(reference_internal_order),
            "internal_player_id_order_sha256": _source_authority_sha256(
                reference_internal_order
            ),
            "artifact_player_id_order_sha256": _source_authority_sha256(
                reference_artifact_order
            ),
        },
        "effective_model_source_identity": {
            "model_version": reference["model_version"],
            "role_model_version": reference["role_model_version"],
        },
        "effective_construction_source_identity": {
            "effective_id": construction["effective_id"],
            "sha256": construction["sha256"],
        },
        "all_arm_blocks_byte_identical_inputs": True,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["authority_sha256"] = _source_authority_sha256(body)
    return validate_paired_native_input_authority(
        body, expected_arm_order=arms, expected_block_labels=blocks,
    )


def validate_native_generation_receipts(
    batch: CandidateBatch,
    expected_allocation: Mapping[str, int],
) -> dict:
    """Validate exact native solve requests when the five receipts exist.

    Older candidate batches do not carry these receipts, so absence is
    explicit and permitted for compatibility.  The production runner rejects
    that state. Once present, every R0--R4 block must prove exact requested
    work, zero solver shortfall, and the model/player inputs it actually used.
    """
    expected_keys = (
        "leverage_requested",
        "boom_requested",
        "core_requested",
        "ce_requested",
        "role_or_epistemic_requested",
        "gumbel_requested",
        "total_requested_with_replacement_families",
    )
    expected = {key: int(expected_allocation[key]) for key in expected_keys}
    if expected["core_requested"] != (
        expected["leverage_requested"] + expected["boom_requested"]
    ):
        raise ValueError("boom-first expected core allocation is inconsistent")
    if expected["total_requested_with_replacement_families"] != (
        expected["core_requested"]
        + expected["ce_requested"]
        + expected["role_or_epistemic_requested"]
        + expected["gumbel_requested"]
    ):
        raise ValueError("boom-first expected family allocation is inconsistent")
    receipts = batch.metadata.get("native_generation_receipts")
    if receipts is None:
        return {
            "available": False,
            "expected_requested_solves": expected,
            "seed_labels": list(_SEED_LABELS),
        }
    if not isinstance(receipts, Mapping) or set(receipts) != set(_SEED_LABELS):
        raise ValueError("boom-first native generation receipt grid is incomplete")

    normalized = {}
    for label in _SEED_LABELS:
        item = receipts[label]
        if not isinstance(item, Mapping):
            raise ValueError(f"boom-first {label} native receipt is malformed")
        counts = {
            key: _canonical_nonnegative_int(
                item.get(key), f"boom-first {label} {key}"
            )
            for key in expected
        }
        if counts != expected:
            raise ValueError(
                f"boom-first {label} requested solve allocation differs: "
                f"{counts} != {expected}"
            )
        telemetry_keys = (
            "leverage_unique",
            "leverage_solve_attempts",
            "leverage_solver_errors",
            "leverage_infeasible",
            "leverage_successful",
            "boom_attempted",
            "boom_successful",
            "boom_solver_errors",
            "boom_infeasible",
            "boom_duplicates",
            "boom_failures",
            "boom_unique_added",
            "unique_candidates_after_all_families",
        )
        telemetry = {
            key: _canonical_nonnegative_int(
                item.get(key), f"boom-first {label} {key}"
            )
            for key in telemetry_keys
        }
        if item.get("boom_unique_fill") is not False:
            raise ValueError(f"boom-first {label} enabled boom unique-fill")
        if (
            telemetry["leverage_solve_attempts"]
            != expected["leverage_requested"]
            or telemetry["leverage_solver_errors"] != 0
            or telemetry["leverage_infeasible"] != 0
            or telemetry["leverage_successful"]
            != expected["leverage_requested"]
            or telemetry["leverage_unique"]
            != telemetry["leverage_successful"]
        ):
            raise ValueError(
                f"boom-first {label} leverage solver work is incomplete"
            )
        if (
            telemetry["boom_attempted"] != expected["boom_requested"]
            or telemetry["boom_successful"] != expected["boom_requested"]
            or telemetry["boom_solver_errors"] != 0
            or telemetry["boom_infeasible"] != 0
            or telemetry["boom_failures"] != 0
            or telemetry["boom_unique_added"] + telemetry["boom_duplicates"]
            != telemetry["boom_successful"]
        ):
            raise ValueError(
                f"boom-first {label} boom solver work is incomplete"
            )
        model_version = str(item.get("model_version") or "").strip()
        role_model_version = str(item.get("role_model_version") or "").strip()
        if not model_version or not role_model_version:
            raise ValueError(f"boom-first {label} model receipt is incomplete")
        candidate_input_receipt = _validated_input_receipt(
            item.get("candidate_input_receipt"),
            f"boom-first {label} candidate input receipt",
        )
        role_candidate_input_receipt = _validated_input_receipt(
            item.get("role_candidate_input_receipt"),
            f"boom-first {label} role candidate input receipt",
        )
        timing = item.get("timing_seconds", {})
        if not isinstance(timing, Mapping):
            raise ValueError(f"boom-first {label} timing receipt is malformed")
        normalized_timing = {}
        for name, value in timing.items():
            try:
                seconds = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"boom-first {label} timing {name!r} is invalid"
                ) from exc
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError(
                    f"boom-first {label} timing {name!r} is invalid"
                )
            normalized_timing[str(name)] = seconds
        normalized[label] = {
            **counts,
            **telemetry,
            "boom_unique_fill": False,
            "model_version": model_version,
            "role_model_version": role_model_version,
            "candidate_input_receipt": candidate_input_receipt,
            "role_candidate_input_receipt": role_candidate_input_receipt,
            "timing_seconds": normalized_timing,
        }
    return {
        "available": True,
        "expected_requested_solves": expected,
        "seed_labels": list(_SEED_LABELS),
        "receipts": normalized,
    }


def validate_paired_native_provenance(
    generation_receipts: Mapping[str, Mapping[str, object]],
    selected_receipt: Mapping[str, str],
) -> dict[str, object]:
    """Prove all ten native books used one identical score-blind slate."""
    reference: dict[str, object] | None = None
    native_books = 0
    for arm in ("control", "treatment"):
        arm_receipt = generation_receipts.get(arm)
        if not isinstance(arm_receipt, Mapping):
            raise ValueError(f"boom-first {arm} generation receipt is absent")
        receipts = arm_receipt.get("receipts")
        if not isinstance(receipts, Mapping):
            raise ValueError(f"boom-first {arm} native receipts are absent")
        for label in _SEED_LABELS:
            item = receipts.get(label)
            if not isinstance(item, Mapping):
                raise ValueError(f"boom-first {arm}/{label} receipt is absent")
            current = {
                "model_version": item["model_version"],
                "role_model_version": item["role_model_version"],
                "candidate_input_receipt": item["candidate_input_receipt"],
                "role_candidate_input_receipt": (
                    item["role_candidate_input_receipt"]
                ),
            }
            if reference is None:
                reference = current
            elif current != reference:
                raise ValueError(
                    f"boom-first {arm}/{label} model or player inputs differ"
                )
            native_books += 1
    if reference is None or native_books != 10:
        raise ValueError("boom-first native provenance grid is incomplete")
    expected_selected = {
        "model_version": reference["model_version"],
        "role_model_version": reference["role_model_version"],
    }
    if dict(selected_receipt) != expected_selected:
        raise ValueError("boom-first selected-lineup model receipt differs")
    return {
        **reference,
        "native_book_count": native_books,
        "all_native_books_identical_inputs": True,
        "control_treatment_identical_inputs": True,
    }


def validate_constraint_contract(stack: StackRules) -> dict:
    """Freeze the exact construction domain shared by both paired arms."""
    expected_stack = {
        "qb_stack_min": 2,
        "bring_back_min": 1,
        "forbid_rb_vs_dst": True,
        "forbid_two_rb_same_team": True,
        "qb_stack_max": None,
        "bring_back_max": None,
        "require_rb_vs_dst": False,
        "require_two_rb_same_team": False,
    }
    observed = {
        key: getattr(stack, key)
        for key in expected_stack
    }
    if observed != expected_stack:
        raise ValueError(
            f"boom-first stack contract differs: {observed} != {expected_stack}"
        )
    return {
        "stack_rules": observed,
        "salary_cap": SALARY_CAP,
        "salary_floor": 49_000,
        "roster_size": ROSTER_SIZE,
        "position_bounds": {
            "QB": [1, 1],
            "RB": [2, 3],
            "WR": [3, 4],
            "TE": [1, 2],
            "DST": [1, 1],
        },
        "max_from_team": MAX_FROM_TEAM,
        "minimum_games": INCUMBENT_MIN_GAMES,
        "punt_min": 0,
        "punt_max_salary": 4_000,
    }


def validate_boom_first_environments(
    control: Mapping[str, str], treatment: Mapping[str, str],
) -> dict:
    """Fail closed unless the pair preserves the frozen production law."""
    common = {
        "MODEL_ENSEMBLE": "1",
        "MODEL_REGISTRY_VARIANT": "tail_k1",
        "MULTISEED_PORTFOLIO": "CBWU",
        "MULTISEED_WORLDS_PER_BLOCK": "10000",
        "MULTISEED_CANDIDATE_ENTRY_BASIS": "80",
        "CAND_MULT": "2",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "EPISTEMIC_FAMILY": "role_draws",
        "N_GUMBEL": "0",
        "N_QB_VARIANTS": "4",
        "N_GAMESTACK": "4",
        "N_DARKGAME": "10",
        "MIN_LINEUP_SALARY": "49000",
        "PUNT_MIN": "0",
        "PUNT_MAX": "4000",
        "PUNT_STRICT": "",
        "MAX_PER_GAME": "0",
        "SELECT_OBJ": "",
        "SELECT_LSE": "0",
        "SELECT_LADDER": "",
        "M4_QBLOCK": "0",
        "MAX_QBS": "0",
    }
    for arm, environment in (("control", control), ("treatment", treatment)):
        for key, expected in common.items():
            if str(environment.get(key, "")) != expected:
                raise ValueError(
                    f"boom-first {arm} {key} differs from {expected!r}"
                )
        if str(environment.get("BOOM_UNIQUE_FILL", "") or "0") != "0":
            raise ValueError(f"boom-first {arm} enables boom unique-fill")

    expected_arms = {
        "control": CONTROL_ALLOCATION,
        "treatment": TREATMENT_ALLOCATION,
    }
    for arm, environment in (("control", control), ("treatment", treatment)):
        expected = expected_arms[arm]
        for env_key, receipt_key in (
            ("N_LEV", "leverage_requested"),
            ("N_BOOM", "boom_requested"),
        ):
            if str(environment.get(env_key, "")) != str(expected[receipt_key]):
                raise ValueError(
                    f"boom-first {arm} {env_key} allocation differs"
                )

    for key in sorted(set(control) | set(treatment)):
        if key in _ARM_ENV_DIFFERENCES:
            continue
        if control.get(key) != treatment.get(key):
            raise ValueError(
                f"boom-first environments differ outside allocation at {key}"
            )
    return {
        "control": dict(CONTROL_ALLOCATION),
        "treatment": dict(TREATMENT_ALLOCATION),
        "model_components": 1,
        "candidate_entry_basis": ENTRIES,
        "tail_line": TAIL_LINE,
        "portfolio": "CBWU",
        "world_blocks": len(_SEED_LABELS),
        "worlds_per_block": 10_000,
        "boom_unique_fill": False,
        "requested_core_per_native_book": 200,
        "requested_role_per_native_book": 12,
        "requested_family_slots_per_native_book": 212,
        "requested_core_per_five_book_arm": 1_000,
        "requested_role_per_five_book_arm": 60,
        "requested_family_slots_per_five_book_arm": 1_060,
        "requested_auxiliary_per_native_book": 54,
        "requested_auxiliary_per_five_book_arm": 270,
        "nominal_all_requested_per_native_book": 266,
        "nominal_all_requested_per_five_book_arm": 1_330,
        "nominal_all_requested_scope": (
            "leverage-boom-role-qbvar-game-dark; excludes retries, "
            "infeasibility and deduplication"
        ),
    }


def player_identity_bridge(
    batch: CandidateBatch,
    dk_id_by_player_id: Mapping[object, str | int],
) -> list[dict[str, object]]:
    """Bind internal, DK and outcome-grading identities before lock."""
    rows: list[dict[str, object]] = []
    for player_id, player in zip(
        batch.player_ids, batch.player_rows, strict=True,
    ):
        if player_id not in dk_id_by_player_id:
            raise ValueError(
                f"boom-first identity bridge lacks DK id for {player_id}"
            )
        position = str(player.get("pos") or "")
        team = str(player.get("team") or "")
        gsis_id = str(player.get("gsis_id") or "")
        if position == "DST":
            if not team:
                raise ValueError("boom-first DST identity lacks team")
        elif not gsis_id:
            raise ValueError(
                f"boom-first {position or 'player'} identity lacks gsis_id"
            )
        rows.append({
            "internal_player_id": str(player_id),
            "dk_draftable_id": str(dk_id_by_player_id[player_id]),
            "gsis_id": gsis_id or None,
            "position": position,
            "team": team,
            "dst_team": team if position == "DST" else None,
            "salary": int(player.get("salary", 0)),
        })
    if len({row["dk_draftable_id"] for row in rows}) != len(rows):
        raise ValueError("boom-first identity bridge repeats a DK id")
    return rows


def _artifact_batch_without_runtime_timing(
    batch: CandidateBatch,
) -> CandidateBatch:
    """Keep wall-clock telemetry in the manifest, not world-artifact bytes."""
    metadata = dict(batch.metadata)
    raw_receipts = metadata.get("native_generation_receipts")
    if isinstance(raw_receipts, Mapping):
        metadata["native_generation_receipts"] = {
            str(label): {
                str(key): value
                for key, value in dict(receipt).items()
                if key != "timing_seconds"
            }
            for label, receipt in raw_receipts.items()
        }
    metadata.pop("generation_timing_seconds", None)
    return replace(batch, metadata=metadata)


def _selected_lineups(
    arm: str,
    batch: CandidateBatch,
    returned: Sequence[Lineup],
    selector_env: Mapping[str, str],
    *,
    n_entries: int,
    tail_line: float,
) -> list[Lineup]:
    if len(batch.candidates) < n_entries:
        raise ValueError(
            f"boom-first {arm} has {len(batch.candidates)} candidates, "
            f"below exact-{n_entries}"
        )
    picked = select_tail_entries(
        batch.candidate_totals, n_entries, tail_line, env=selector_env
    )
    expected = [batch.candidates[index] for index in picked]
    if len(expected) != n_entries:
        raise ValueError(f"boom-first {arm} selector is not exact-{n_entries}")
    if len(returned) != n_entries:
        raise ValueError(
            f"boom-first {arm} returned {len(returned)} entries, "
            f"expected {n_entries}"
        )
    expected_ids = [lineup.ids for lineup in expected]
    returned_ids = [lineup.ids for lineup in returned]
    if returned_ids != expected_ids or len(set(returned_ids)) != n_entries:
        raise ValueError(
            f"boom-first {arm} returned membership/order differs from selector"
        )
    return expected


def paired_boom_first_receipt(
    control: CandidateBatch,
    treatment: CandidateBatch,
    control_lineups: Sequence[Lineup],
    treatment_lineups: Sequence[Lineup],
    dk_id_by_player_id: Mapping[object, str | int],
    *,
    control_selector_env: Mapping[str, str],
    treatment_selector_env: Mapping[str, str],
    n_entries: int = ENTRIES,
    tail_line: float = TAIL_LINE,
) -> dict:
    """Validate a same-world, potentially unequal-candidate paired book."""
    _validate_candidate_batch(control)
    _validate_candidate_batch(treatment)
    if n_entries != ENTRIES or float(tail_line) != TAIL_LINE:
        raise ValueError("boom-first v1 is frozen to exact-80 coverage at 194")
    if control.metadata.get("portfolio") != "CBWU":
        raise ValueError("boom-first control is not a CBWU batch")
    if treatment.metadata.get("portfolio") != "CBWU":
        raise ValueError("boom-first treatment is not a CBWU batch")
    for arm, batch in (("control", control), ("treatment", treatment)):
        if batch.metadata.get("world_blocks") != len(_SEED_LABELS):
            raise ValueError(f"boom-first {arm} is not a five-block CBWU batch")
        if batch.metadata.get("worlds_per_block") != [10_000] * 5:
            raise ValueError(
                f"boom-first {arm} CBWU world-block sizes differ"
            )
        if batch.row_draws.shape[1] != 50_000:
            raise ValueError(f"boom-first {arm} is not exact-50,000 worlds")
    if control.player_ids != treatment.player_ids:
        raise ValueError("boom-first player order differs")
    if not np.array_equal(control.row_draws, treatment.row_draws):
        raise ValueError("boom-first player worlds differ")
    if not np.isfinite(control.row_draws).all():
        raise ValueError("boom-first player worlds are nonfinite")
    if (
        not np.isfinite(control.candidate_totals).all()
        or not np.isfinite(treatment.candidate_totals).all()
    ):
        raise ValueError("boom-first candidate worlds are nonfinite")

    selected_control = _selected_lineups(
        "control",
        control,
        control_lineups,
        control_selector_env,
        n_entries=n_entries,
        tail_line=tail_line,
    )
    selected_treatment = _selected_lineups(
        "treatment",
        treatment,
        treatment_lineups,
        treatment_selector_env,
        n_entries=n_entries,
        tail_line=tail_line,
    )
    control_dk = [
        _canonical_dk_roster(lineup, dict(dk_id_by_player_id))
        for lineup in selected_control
    ]
    treatment_dk = [
        _canonical_dk_roster(lineup, dict(dk_id_by_player_id))
        for lineup in selected_treatment
    ]
    memberships = {
        str(size): {
            "control": control_dk[:size],
            "treatment": treatment_dk[:size],
        }
        for size in (20, 40, 80)
    }
    control_candidates = {lineup.ids for lineup in control.candidates}
    treatment_candidates = {lineup.ids for lineup in treatment.candidates}
    control_count = len(control.candidates)
    treatment_count = len(treatment.candidates)
    candidate_orders = {
        "control": [
            _canonical_dk_roster(lineup, dict(dk_id_by_player_id))
            for lineup in control.candidates
        ],
        "treatment": [
            _canonical_dk_roster(lineup, dict(dk_id_by_player_id))
            for lineup in treatment.candidates
        ],
    }
    return {
        "shadow_version": VERSION,
        "tail_line": float(tail_line),
        "entries": int(n_entries),
        "control_candidate_count": control_count,
        "treatment_candidate_count": treatment_count,
        "candidate_counts": {
            "control": control_count,
            "treatment": treatment_count,
        },
        "candidate_budget_identical": control_count == treatment_count,
        "worlds": int(control.row_draws.shape[1]),
        "players": len(control.player_ids),
        "player_worlds_identical": True,
        "candidate_overlap": len(control_candidates & treatment_candidates),
        "candidate_union": len(control_candidates | treatment_candidates),
        "memberships": memberships,
        "memberships_sha256": _canonical_json_sha256(memberships),
        "player_worlds_receipt": _array_receipt(control.row_draws),
        "candidate_matrix_receipts": {
            "control": _array_receipt(control.candidate_totals),
            "treatment": _array_receipt(treatment.candidate_totals),
        },
        "candidate_order_sha256": {
            arm: _canonical_json_sha256(rosters)
            for arm, rosters in candidate_orders.items()
        },
        "uses_post_lock_outcomes": False,
        "uses_fantasy_or_lineup_outcomes": False,
        "production_enabled": False,
    }


def run(
    *,
    store=None,
    season: int | None = None,
    week: int | None = None,
    draft_group_id: int | None = None,
    generated_at: datetime | None = None,
    storage_client=None,
    bucket_name: str | None = None,
) -> dict:
    """Build, pair-check, and create-only persist both boom-first arms."""
    runner_started = time.perf_counter()
    code_sha = _validated_code_sha(os.environ.get("CODE_SHA"))
    image_source_commit_sha = str(
        os.environ.get("IMAGE_SOURCE_COMMIT_SHA") or ""
    ).strip().lower()
    if (
        len(code_sha) != 40
        or re.fullmatch(r"[0-9a-f]{40}", image_source_commit_sha) is None
        or image_source_commit_sha != code_sha
    ):
        raise ValueError(
            "boom-first image source commit does not match full CODE_SHA"
        )
    image_uri = _validated_image_uri(os.environ.get("IMAGE_URI"))
    cloud_context = _validated_cloud_execution_context(os.environ)
    if store is None:
        from ..app.store import BigQueryStore

        store = BigQueryStore()
    if season is None or week is None or draft_group_id is None:
        from .tail_shadow import upcoming_season_week, sunday_main_group

        found_season, found_week, sunday = upcoming_season_week()
        season = found_season if season is None else season
        week = found_week if week is None else week
        if draft_group_id is None:
            draft_group_id = sunday_main_group(store.classic_slates(), sunday)
    season, week, draft_group_id = int(season), int(week), int(draft_group_id)
    if season != 2026 or not 1 <= week <= 18:
        raise ValueError("boom-first paired shadow v1 is frozen to 2026")
    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("boom-first generated_at must be timezone-aware")
    stamp = stamp.astimezone(timezone.utc)
    run_id = (
        f"prospective-boom-first-{season}w{week:02d}-"
        f"{cloud_context['cloud_run_execution']}"
    )
    bucket = bucket_name or settings.gcs_bucket
    root = f"boom_first_shadow/{season}/week-{week:02d}/{run_id}"
    allowed, salary_overrides, dk_mapping = _slate_identity(
        store, draft_group_id
    )
    policy = ADOPTED_CLASSIC_POLICY
    if int(policy.model_ensemble) != 1:
        raise ValueError("boom-first paired shadow requires production K=1")
    construction = policy.construction_preset()
    stack = construction.stack
    constraint_contract = validate_constraint_contract(stack)
    common = {
        "season": season,
        "week": week,
        "n_entries": ENTRIES,
        "stack": stack,
        "tail_line": TAIL_LINE,
        "lev_scale": 1.0,
        "allowed_ids": allowed,
        "salary_overrides": salary_overrides,
        "apply_notes": False,
        "model_variant": policy.model_variant,
        "cand_log_table": f"{settings.predictions}.live_candidates_shadow",
        "cand_log_async": False,
        "cand_log_required": True,
        "expected_model_k": policy.model_ensemble,
        "belief_model_variant": policy.role_model_variant,
        "construction_preset_receipt": construction.receipt(),
    }
    control_env = policy.boom_first_control_environment(os.environ)
    treatment_env = policy.boom_first_shadow_environment(os.environ)
    environment_contract = validate_boom_first_environments(
        control_env, treatment_env
    )

    from .live_lineups import build_sim_lineups

    control_capture: list[CandidateBatch] = []
    control_started = time.perf_counter()
    control_lineups = build_sim_lineups(
        **common,
        panel_run_id=f"{run_id}-control",
        candidate_run_type="prospective_boom_first_control",
        policy_env=control_env,
        _candidate_capture=control_capture.append,
    )
    control_build_seconds = time.perf_counter() - control_started

    treatment_capture: list[CandidateBatch] = []
    treatment_started = time.perf_counter()
    treatment_lineups = build_sim_lineups(
        **common,
        panel_run_id=f"{run_id}-treatment",
        candidate_run_type="prospective_boom_first_treatment",
        policy_env=treatment_env,
        _candidate_capture=treatment_capture.append,
    )
    treatment_build_seconds = time.perf_counter() - treatment_started
    if len(control_capture) != 1 or len(treatment_capture) != 1:
        raise RuntimeError("boom-first paired shadow did not capture both books")

    validation_started = time.perf_counter()
    control_batch, treatment_batch = control_capture[0], treatment_capture[0]
    paired = paired_boom_first_receipt(
        control_batch,
        treatment_batch,
        control_lineups,
        treatment_lineups,
        dk_mapping,
        control_selector_env=control_env,
        treatment_selector_env=treatment_env,
    )
    generation_receipts = {
        "control": validate_native_generation_receipts(
            control_batch, CONTROL_ALLOCATION
        ),
        "treatment": validate_native_generation_receipts(
            treatment_batch, TREATMENT_ALLOCATION
        ),
    }
    if not all(
        receipt.get("available") is True
        for receipt in generation_receipts.values()
    ):
        raise RuntimeError("boom-first paired shadow lacks native solve receipts")
    identity_bridge = player_identity_bridge(control_batch, dk_mapping)
    model_receipt = selected_model_receipt(control_lineups, treatment_lineups)
    native_provenance = validate_paired_native_provenance(
        generation_receipts, model_receipt
    )
    validation_seconds = time.perf_counter() - validation_started

    context = {
        "shadow_version": VERSION,
        "run_id": run_id,
        "season": season,
        "week": week,
        "draft_group_id": draft_group_id,
        "code_sha": code_sha,
        "image_source_commit_sha": image_source_commit_sha,
        "image_uri": image_uri,
        **cloud_context,
        "production_policy": policy.policy_id,
        "strategy_ids": {
            "control": control_env["PROSPECTIVE_SHADOW_ID"],
            "treatment": treatment_env["PROSPECTIVE_SHADOW_ID"],
        },
    }
    control_persist_started = time.perf_counter()
    control_artifact = persist_recourse_world_artifact(
        _artifact_batch_without_runtime_timing(control_batch),
        dk_mapping,
        generated_at=stamp,
        bucket_name=bucket,
        object_name=f"{root}/control.npz",
        context={**context, "arm": "control"},
        storage_client=storage_client,
    )
    control_persist_seconds = time.perf_counter() - control_persist_started
    treatment_persist_started = time.perf_counter()
    treatment_artifact = persist_recourse_world_artifact(
        _artifact_batch_without_runtime_timing(treatment_batch),
        dk_mapping,
        generated_at=stamp,
        bucket_name=bucket,
        object_name=f"{root}/treatment.npz",
        context={**context, "arm": "treatment"},
        storage_client=storage_client,
    )
    treatment_persist_seconds = time.perf_counter() - treatment_persist_started
    if (
        control_artifact.get("create_only") is not True
        or treatment_artifact.get("create_only") is not True
    ):
        raise RuntimeError("boom-first world artifacts are not create-only")

    timings = {
        "control_build": float(control_build_seconds),
        "treatment_build": float(treatment_build_seconds),
        "pair_validation": float(validation_seconds),
        "control_artifact_persist": float(control_persist_seconds),
        "treatment_artifact_persist": float(treatment_persist_seconds),
        "elapsed_before_manifest": float(time.perf_counter() - runner_started),
    }
    counts = {
        "control_candidates": paired["control_candidate_count"],
        "treatment_candidates": paired["treatment_candidate_count"],
        "control_selected": ENTRIES,
        "treatment_selected": ENTRIES,
        "players": paired["players"],
        "worlds": paired["worlds"],
        "candidate_overlap": paired["candidate_overlap"],
        "candidate_union": paired["candidate_union"],
    }
    manifest = {
        **context,
        **paired,
        "generated_at": stamp.isoformat(),
        "environment_contract": environment_contract,
        "environment_receipts": {
            "control": {
                "sha256": _canonical_json_sha256(control_env),
                "values": dict(sorted(control_env.items())),
            },
            "treatment": {
                "sha256": _canonical_json_sha256(treatment_env),
                "values": dict(sorted(treatment_env.items())),
            },
        },
        "constraint_contract": constraint_contract,
        "native_generation_receipts": generation_receipts,
        "model_receipt": model_receipt,
        "native_provenance_receipt": native_provenance,
        "player_identity_bridge": identity_bridge,
        "player_identity_bridge_sha256": _canonical_json_sha256(
            identity_bridge
        ),
        "counts": counts,
        "timings_seconds": timings,
        "control_artifact": control_artifact,
        "treatment_artifact": treatment_artifact,
        "uses_post_lock_outcomes": False,
        "uses_fantasy_or_lineup_outcomes": False,
        "production_enabled": False,
    }
    payload = json.dumps(
        manifest, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    name = f"{root}/manifest.json"
    manifest_started = time.perf_counter()
    storage_client.bucket(bucket).blob(name).upload_from_string(
        payload,
        content_type="application/json",
        if_generation_match=0,
    )
    manifest_persist_seconds = float(time.perf_counter() - manifest_started)
    terminal_body = {
        "schema_version": TERMINAL_SCHEMA,
        "complete": True,
        "run_id": run_id,
        "season": season,
        "week": week,
        "draft_group_id": draft_group_id,
        "code_sha": code_sha,
        "image_source_commit_sha": image_source_commit_sha,
        "image_uri": image_uri,
        **cloud_context,
        "manifest": {
            "uri": f"gs://{bucket}/{name}",
            "sha256": digest,
            "bytes": len(payload),
            "create_only": True,
        },
        "world_artifacts": {
            arm: {
                key: receipt[key]
                for key in ("uri", "sha256", "bytes", "create_only")
            }
            for arm, receipt in (
                ("control", control_artifact),
                ("treatment", treatment_artifact),
            )
        },
        "counts": counts,
        "uses_post_lock_outcomes": False,
        "uses_fantasy_or_lineup_outcomes": False,
        "production_enabled": False,
    }
    terminal_body["terminal_receipt_sha256"] = _canonical_json_sha256(
        terminal_body
    )
    terminal_payload = json.dumps(
        terminal_body, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    terminal_digest = hashlib.sha256(terminal_payload).hexdigest()
    terminal_name = f"{root}/terminal.json"
    terminal_started = time.perf_counter()
    storage_client.bucket(bucket).blob(terminal_name).upload_from_string(
        terminal_payload,
        content_type="application/json",
        if_generation_match=0,
    )
    return {
        **manifest,
        "manifest_uri": f"gs://{bucket}/{name}",
        "manifest_sha256": digest,
        "manifest_bytes": len(payload),
        "manifest_create_only": True,
        "manifest_persist_seconds": manifest_persist_seconds,
        "terminal_uri": f"gs://{bucket}/{terminal_name}",
        "terminal_sha256": terminal_digest,
        "terminal_bytes": len(terminal_payload),
        "terminal_create_only": True,
        "terminal_persist_seconds": float(
            time.perf_counter() - terminal_started
        ),
        "complete": True,
    }


def main() -> None:
    result = run()
    print(json.dumps({
        "complete": result["complete"],
        "run_id": result["run_id"],
        "cloud_run_job": result["cloud_run_job"],
        "cloud_run_execution": result["cloud_run_execution"],
        "code_sha": result["code_sha"],
        "image_uri": result["image_uri"],
        "manifest_uri": result["manifest_uri"],
        "manifest_sha256": result["manifest_sha256"],
        "terminal_uri": result["terminal_uri"],
        "terminal_sha256": result["terminal_sha256"],
        "candidate_counts": result["candidate_counts"],
        "production_enabled": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "CONTROL_ALLOCATION",
    "ENTRIES",
    "TAIL_LINE",
    "TREATMENT_ALLOCATION",
    "VERSION",
    "paired_boom_first_receipt",
    "run",
    "selected_model_receipt",
    "validate_constraint_contract",
    "validate_boom_first_environments",
    "validate_native_generation_receipts",
    "validate_paired_native_provenance",
]
