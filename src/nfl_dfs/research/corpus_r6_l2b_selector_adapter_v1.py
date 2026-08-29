"""Outcome-blind selector and grade adapter for the frozen R6 L2b bank.

The L2b panel contains alternate player-world matrices but intentionally stops
before lineup selection.  This module closes that gap without regenerating a
corpus or touching realized outcomes:

* exact-open the immutable L2b panel root;
* exact-open the already-frozen current-bank projection bundles, which carry
  the accepted full-union candidate rows for every rotated R-block fold;
* cross-score those unchanged rosters under each L2b fraction;
* run the existing grouped-native, exact-rank-150, and DPP selectors at their
  frozen 4/14/80/100/150 budgets;
* add exact 80/100/150 books for overlap caps four and five plus the strict-200
  evil-twin order; preserve cap three as an unregistered follow-up because a
  real 250-lineup preflight cannot support 150 entries without relaxing it;
  and
* publish one create-last 54-slate terminal root whose normalized slate
  surface is consumable by the common novel-roster realized-score machinery.

No public function accepts a realized outcome, outcome reader, lineup score,
winner label, graph client, optimizer, or production mutation capability.
The optional realized-grade function first exact-replays the terminal root and
then delegates the score/aggregate work to the generic grader's shared
implementation.  Merely importing or executing the selector path cannot read
an outcome.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as projection_contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as control_runtime,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_evaluation_v1 as evaluator,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_diversity_selector_v1 as diversity,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_v1 as rank150,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)
from nfl_dfs.research import (
    corpus_r6_selector_diversity_challengers_v1 as diversity_challengers,
)
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as l2b_panel
from nfl_dfs.research import corpus_r6_l2b_panel_operator_v1 as l2b_operator
from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as grader
from nfl_dfs.research import lr8_later_period_source as later


CONTRACT_ID: Final = "20260829-r6-l2b-selector-adapter-v1"
ADAPTER_ID: Final = "l2b-current-union-selectors-v1"
NORMALIZED_GRADER_BOUNDARY: Final = (
    grader.EXTERNAL_NORMALIZED_TERMINAL_BOUNDARY
)
TASK_MANIFEST_SCHEMA: Final = "corpus-r6-l2b-selector-task-manifest/v1"
TASK_RESULT_SCHEMA: Final = "corpus-r6-l2b-selector-slate-result/v1"
FOLD_RESULT_SCHEMA: Final = "corpus-r6-l2b-selector-fold-result/v1"
FRACTION_RESULT_SCHEMA: Final = "corpus-r6-l2b-selector-fraction-result/v1"
TERMINAL_ROOT_SCHEMA: Final = "corpus-r6-l2b-selector-terminal-root/v1"
REALIZED_GRADE_SCHEMA: Final = grader.REALIZED_GRADE_SCHEMA

TASK_COUNT: Final = l2b_panel.TASK_COUNT
WORLD_BLOCKS: Final = l2b_panel.WORLD_BLOCKS
WORLDS_PER_BLOCK: Final = l2b_panel.WORLDS_PER_BLOCK
FRACTION_IDS: Final = tuple(
    str(row["fraction_id"]) for row in l2b_panel.FRACTION_REGISTRY
)
TAIL_DIVERSITY_FOLLOWUP_STRATEGY_ID: Final = (
    "tail-ladder-roster-overlap-cap-3-v1"
)
TAIL_DIVERSITY_ACTIVE_STRATEGY_IDS: Final = (
    "tail-ladder-roster-overlap-cap-4-v1",
    "tail-ladder-roster-overlap-cap-5-v1",
    "tail-ladder-evil-twin-strict-200-v1",
)
SELECTOR_FAMILIES: Final = (
    "grouped-native-rank80",
    "exact-rank150-continuation",
    "effective-independent-tail-shots",
    "tail-ladder-diversity-challengers",
)
SELECTOR_COUNT_PER_FRACTION_FOLD: Final = 10
BOOK_COUNT_PER_FRACTION_FOLD: Final = 30
SELECTOR_LATTICE: Final = {
    "grouped_native_selector_count": 3,
    "grouped_native_entry_budgets": list(successor.PREFIX_SIZES),
    "exact_rank150_selector_count": 3,
    "exact_rank150_entry_budgets": list(rank150.ENTRY_BUDGETS),
    "dpp_selector_count": 1,
    "dpp_entry_budgets": list(diversity.PREFIX_SIZES),
    "tail_ladder_diversity_source_selector_count": 4,
    "tail_ladder_diversity_active_selector_count": 3,
    "tail_ladder_diversity_entry_budgets": list(
        diversity_challengers.ENTRY_BUDGETS
    ),
    "tail_ladder_diversity_active_strategy_ids": list(
        TAIL_DIVERSITY_ACTIVE_STRATEGY_IDS
    ),
    "tail_ladder_diversity_followup_strategy_ids": [
        TAIL_DIVERSITY_FOLLOWUP_STRATEGY_ID
    ],
    "tail_ladder_diversity_activation_gate": {
        "required_status": "exact-rank-150",
        "required_entry_budgets": list(diversity_challengers.ENTRY_BUDGETS),
        "failure_law": "fail-fraction-before-publication-never-relax-cap",
        "uses_realized_outcomes": False,
    },
    "tail_ladder_diversity_contract_sha256": (
        diversity_challengers.diversity_challenger_contract_v1()[
            "contract_sha256"
        ]
    ),
    "selector_count_per_fraction_fold": SELECTOR_COUNT_PER_FRACTION_FOLD,
    "book_count_per_fraction_fold": BOOK_COUNT_PER_FRACTION_FOLD,
}

FIXED_GCP_PROJECT: Final = l2b_panel.FIXED_GCP_PROJECT
FIXED_STORAGE_ENDPOINT: Final = l2b_panel.FIXED_STORAGE_ENDPOINT
OUTPUT_NAMESPACE: Final = l2b_panel.OUTPUT_NAMESPACE
REUSED_JOB_NAME: Final = l2b_panel.REUSED_JOB_NAME
REUSED_JOB_UID: Final = l2b_panel.REUSED_JOB_UID
TASK0_SCOPE: Final = l2b_panel.TASK0_SCOPE
FULL54_SCOPE: Final = l2b_panel.FULL54_SCOPE
EXECUTION_SCOPES: Final = (TASK0_SCOPE, FULL54_SCOPE)
MAXIMUM_PANEL_ROOT_BYTES: Final = l2b_panel.MAXIMUM_PANEL_ROOT_BYTES
MAXIMUM_TASK_MANIFEST_BYTES: Final = 32_000_000
MAXIMUM_PROJECTION_BUNDLE_BYTES: Final = 256_000_000
MAXIMUM_LATER_SOURCE_BYTES: Final = 16_000_000
MAXIMUM_TASK_RESULT_BYTES: Final = 256_000_000
MAXIMUM_TERMINAL_ROOT_BYTES: Final = 16_000_000
MAXIMUM_REALIZED_GRADE_BYTES: Final = grader.MAXIMUM_REALIZED_GRADE_BYTES
TASK0_SMOKE_SCHEMA: Final = "corpus-r6-l2b-selector-task0-smoke-receipt/v1"

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]

_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IMAGE_URI = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}\Z")
_PROVIDER_UID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,127}\Z")
_FALSE_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "heldout_scores_available_to_selectors": False,
    "candidate_population_regenerated": False,
    "graph_mutation_performed": False,
    "production_change_licensed": False,
    "promotion_authority": False,
    "decision_authority": False,
}


class CorpusR6L2BSelectorAdapterV1Error(ValueError):
    """The fixed L2b-to-selector boundary failed closed."""


@dataclass(frozen=True, slots=True)
class L2BSelectorTaskExecutionV1:
    result: Mapping[str, object]
    result_identity: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class L2BGenericGraderTerminalV1:
    adapter_id: str
    task_manifest: Mapping[str, object]
    task_manifest_identity: Mapping[str, object]
    task_manifest_sha256: str
    task_result_descriptors: tuple[Mapping[str, object], ...]
    slates: tuple[Mapping[str, object], ...]
    later_source_identity: Mapping[str, object]
    terminal_root: Mapping[str, object]
    terminal_root_identity: Mapping[str, object]


def _fail(message: str) -> None:
    raise CorpusR6L2BSelectorAdapterV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(str(exc)) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _canonical_json_object_v1(
    value: object, *, label: str,
) -> dict[str, object]:
    """Normalize tuples and other JSON arrays to their persisted list form."""
    raw = canonical_json_bytes_v1(value)
    try:
        normalized = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(str(exc)) from exc
    return _mapping(normalized, label=label)


def _selector_lattice_v1() -> dict[str, object]:
    return _canonical_json_object_v1(
        SELECTOR_LATTICE, label="L2b selector lattice"
    )


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA64.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    body[field] = canonical_sha256_v1(body)
    return body


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    retained = value.get(field)
    if (
        type(retained) is not str
        or _SHA64.fullmatch(retained) is None
        or retained != canonical_sha256_v1({
            key: row for key, row in value.items() if key != field
        })
    ):
        _fail(f"{label} self-hash differs")


def _validate_task0_execution_status_v1(value: object) -> dict[str, object]:
    """Validate the provider-derived terminal status sealed by the smoke."""
    status = _mapping(value, label="task0 provider terminal status")
    expected_fields = {
        "schema_version", "scope", "project_id", "location", "job_name",
        "job_uid", "execution_name", "execution_uid",
        "execution_generation", "expected_task_count", "succeeded_count",
        "failed_count", "cancelled_count", "terminal_state", "logs_read",
        "scientific_outputs_read", "outcomes_read", "status_sha256",
    }
    if set(status) != expected_fields:
        _fail("task0 provider terminal-status fields differ")
    try:
        l2b_operator._self_hash(
            status,
            field="status_sha256",
            label="task0 provider terminal status",
        )
        execution_name = l2b_operator._execution_name(
            status.get("execution_name")
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "task0 provider terminal-status identity differs"
        ) from exc
    execution_uid = status.get("execution_uid")
    generation = status.get("execution_generation")
    if (
        status.get("schema_version") != l2b_operator.STATUS_SCHEMA
        or status.get("scope") != TASK0_SCOPE
        or status.get("project_id") != l2b_operator.PROJECT
        or status.get("location") != l2b_operator.REGION
        or status.get("job_name") != REUSED_JOB_NAME
        or status.get("job_uid") != REUSED_JOB_UID
        or execution_name != status.get("execution_name")
        or type(execution_uid) is not str
        or _PROVIDER_UID.fullmatch(execution_uid) is None
        or type(generation) is not str
        or not generation.isdigit()
        or int(generation) < 1
        or status.get("expected_task_count") != 1
        or status.get("succeeded_count") != 1
        or status.get("failed_count") != 0
        or status.get("cancelled_count") != 0
        or status.get("terminal_state") != "SUCCEEDED"
        or status.get("logs_read") is not False
        or status.get("scientific_outputs_read") is not False
        or status.get("outcomes_read") is not False
    ):
        _fail("task0 provider terminal-status authority differs")
    return status


def _validate_task0_smoke_receipt_shape_v1(
    value: object,
) -> dict[str, object]:
    """Validate every non-null identity and digest before authority replay."""
    receipt = _mapping(value, label="task0 smoke receipt")
    expected_fields = {
        "schema_version", "adapter_id", "execution_scope",
        "task0_manifest_identity", "task0_manifest_sha256",
        "l2b_panel_root_identity", "control_projection_receipt_identity",
        "terminal_build_receipt_identity", "source_commit_sha",
        "immutable_image_digest", "reused_job_uid", "task0_launch_result",
        "task0_execution_status", "task_result_identity", "task_result_sha256",
        "uses_realized_outcomes", "complete", "smoke_receipt_sha256",
    }
    if set(receipt) != expected_fields:
        _fail("task0 smoke receipt fields differ")
    _validate_self_hash(
        receipt, field="smoke_receipt_sha256", label="task0 smoke receipt"
    )
    for field in (
        "task0_manifest_identity", "l2b_panel_root_identity",
        "control_projection_receipt_identity", "terminal_build_receipt_identity",
        "task_result_identity",
    ):
        if receipt.get(field) != _identity(receipt.get(field), label=field):
            _fail(f"task0 smoke {field} is not canonical")
    for field in ("task0_manifest_sha256", "task_result_sha256"):
        _digest(receipt.get(field), label=f"task0 smoke {field}")
    status = _validate_task0_execution_status_v1(
        receipt.get("task0_execution_status")
    )
    try:
        launch = l2b_operator.validate_launch_result_v1(
            receipt.get("task0_launch_result")
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "task0 smoke launch authority differs"
        ) from exc
    if (
        receipt.get("schema_version") != TASK0_SMOKE_SCHEMA
        or receipt.get("adapter_id") != ADAPTER_ID
        or receipt.get("execution_scope") != TASK0_SCOPE
        or _SHA40.fullmatch(str(receipt.get("source_commit_sha", ""))) is None
        or _IMAGE_DIGEST.fullmatch(
            str(receipt.get("immutable_image_digest", ""))
        ) is None
        or receipt.get("reused_job_uid") != REUSED_JOB_UID
        or status.get("job_uid") != receipt.get("reused_job_uid")
        or launch.get("scope") != TASK0_SCOPE
        or launch.get("job_uid") != receipt.get("reused_job_uid")
        or launch.get("execution_name") != status.get("execution_name")
        or receipt.get("uses_realized_outcomes") is not False
        or receipt.get("complete") is not True
    ):
        _fail("task0 smoke receipt fixed law differs")
    return receipt


def _exact_read_bytes(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds its byte ceiling")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            f"{label} exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-read content identity differs")
    return raw, identity


def _exact_read_json(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, identity = _exact_read_bytes(
        identity_value,
        read_exact=read_exact,
        label=label,
        maximum_bytes=maximum_bytes,
    )
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(str(exc)) from exc
    body = _mapping(value, label=label)
    if canonical_json_bytes_v1(body) != raw:
        _fail(f"{label} is not canonical JSON")
    return body, identity


def _publish_json(
    *,
    uri: str,
    value: Mapping[str, object],
    maximum_bytes: int,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    if type(uri) is not str or not uri.startswith("gs://") or uri.endswith("/"):
        _fail(f"{label} URI must name one exact GCS object")
    raw = canonical_json_bytes_v1(value)
    if not raw or len(raw) > maximum_bytes:
        _fail(f"{label} exceeds its byte ceiling")
    try:
        published = publish_create_once(uri, raw)
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _identity(published, label=f"published {label}")
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} publisher identity differs")
    reopened, reopened_identity = _exact_read_json(
        identity,
        read_exact=read_exact,
        label=f"published {label}",
        maximum_bytes=maximum_bytes,
    )
    if reopened_identity != identity or canonical_json_bytes_v1(reopened) != raw:
        _fail(f"{label} exact reopen differs")
    return identity


def _output_prefix(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith(OUTPUT_NAMESPACE)
        or not value.endswith("/")
        or "?" in value
        or "#" in value
        or "//" in value[5:]
        or any(part in {"", ".", ".."} for part in value[5:-1].split("/"))
    ):
        _fail("L2b selector output prefix differs")
    return value


def _matrix_sha256(value: np.ndarray, *, label: str) -> str:
    matrix = np.asarray(value)
    if (
        matrix.dtype != np.dtype(np.float64)
        or matrix.ndim != 2
        or not matrix.flags.c_contiguous
        or not np.isfinite(matrix).all()
    ):
        _fail(f"{label} must be one finite C-contiguous float64 matrix")
    digest = sha256()
    digest.update(canonical_json_bytes_v1({
        "label": label,
        "dtype": "float64-le",
        "shape": [int(size) for size in matrix.shape],
        "row_order": "projection-candidate-order",
        "column_order": "block-registry-then-world-ordinal",
    }))
    digest.update(b"\0")
    little = np.ascontiguousarray(matrix, dtype="<f8")
    digest.update(memoryview(little).cast("B"))
    return digest.hexdigest()


def _validate_panel_root_v1(
    value: object,
) -> dict[str, object]:
    root = _mapping(value, label="L2b panel root")
    expected_fields = {
        "schema_version", "contract_id", "manifest_identity",
        "manifest_sha256", "calibration_release_identity",
        "calibration_release_sha256", "pit_target_panel_identity",
        "pit_target_panel_sha256", "terminal_build_receipt_identity",
        "terminal_build_receipt_sha256", "terminal_build_id",
        "source_commit_sha", "immutable_image_digest", "reused_job_name",
        "reused_job_uid", "task_count", "task_results",
        "fraction_registry", "control_reference", "world_blocks",
        "worlds_per_block", "cell_count", "cells", "downstream_adapter",
        "selector_evaluator_chain_reusable",
        "all_task_and_world_receipts_exactly_validated", "complete",
        *l2b_panel._FALSE_AUTHORITY_FIELDS, "panel_root_sha256",
    }
    if set(root) != expected_fields:
        _fail("L2b panel root fields differ")
    _validate_self_hash(root, field="panel_root_sha256", label="L2b panel root")
    task_results = [
        _mapping(row, label=f"L2b panel task result[{index}]")
        for index, row in enumerate(
            _sequence(root.get("task_results"), label="L2b panel task results")
        )
    ]
    cells = [
        _mapping(row, label=f"L2b panel cell[{index}]")
        for index, row in enumerate(
            _sequence(root.get("cells"), label="L2b panel cells")
        )
    ]
    if (
        root.get("schema_version") != l2b_panel.PANEL_ROOT_SCHEMA
        or root.get("contract_id") != l2b_panel.CONTRACT_ID
        or root.get("task_count") != TASK_COUNT
        or len(task_results) != TASK_COUNT
        or [row.get("task_index") for row in task_results] != list(range(TASK_COUNT))
        or root.get("fraction_registry")
        != [dict(row) for row in l2b_panel.FRACTION_REGISTRY]
        or root.get("control_reference") != l2b_panel.CONTROL_REFERENCE
        or root.get("world_blocks") != list(WORLD_BLOCKS)
        or root.get("worlds_per_block") != WORLDS_PER_BLOCK
        or root.get("cell_count") != TASK_COUNT * len(FRACTION_IDS) * len(WORLD_BLOCKS)
        or len(cells) != root.get("cell_count")
        or root.get("selector_evaluator_chain_reusable") is not True
        or root.get("all_task_and_world_receipts_exactly_validated") is not True
        or root.get("complete") is not True
        or any(root.get(field) is not False for field in l2b_panel._FALSE_AUTHORITY_FIELDS)
    ):
        _fail("L2b panel root fixed authority differs")
    for index, row in enumerate(task_results):
        if set(row) != {
            "task_index", "slate_id", "task_result_identity",
            "task_result_sha256",
        }:
            _fail("L2b panel task-result descriptor fields differ")
        _identity(row.get("task_result_identity"), label="L2b task result")
        _digest(row.get("task_result_sha256"), label="L2b task-result SHA")
        season, week = l2b_panel.EXPECTED_SLATES[index]
        if row.get("slate_id") != f"{season}-w{week:02d}":
            _fail("L2b panel task-result slate order differs")
    expected_cell_keys = [
        (task_index, f"{season}-w{week:02d}", fraction_id, block)
        for task_index, (season, week) in enumerate(l2b_panel.EXPECTED_SLATES)
        for block in WORLD_BLOCKS
        for fraction_id in FRACTION_IDS
    ]
    observed_cell_keys = [
        (
            row.get("task_index"), row.get("slate_id"),
            row.get("fraction_id"), row.get("block"),
        )
        for row in cells
    ]
    if observed_cell_keys != expected_cell_keys:
        _fail("L2b panel cell lattice differs")
    for row in cells:
        if set(row) != {
            "task_index", "slate_id", "fraction_id", "block",
            "world_artifact_identity", "world_artifact_receipt_identity",
            "world_artifact_receipt_sha256",
        }:
            _fail("L2b panel cell fields differ")
        _identity(row["world_artifact_identity"], label="L2b world artifact")
        _identity(
            row["world_artifact_receipt_identity"], label="L2b world receipt"
        )
        _digest(row["world_artifact_receipt_sha256"], label="L2b receipt SHA")
    return root


def _open_panel_root_v1(
    *, panel_root_identity: object, read_exact: ReadExact,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object], dict[str, object]
]:
    root_body, root_identity = _exact_read_json(
        panel_root_identity,
        read_exact=read_exact,
        label="L2b panel root",
        maximum_bytes=MAXIMUM_PANEL_ROOT_BYTES,
    )
    root = _validate_panel_root_v1(root_body)
    try:
        manifest, manifest_identity = l2b_panel._open_manifest(
            manifest_identity=root["manifest_identity"], read_exact=read_exact
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "L2b panel manifest exact replay failed"
        ) from exc
    if (
        manifest_identity != root["manifest_identity"]
        or manifest["task_manifest_sha256"] != root["manifest_sha256"]
        or manifest["calibration_release_identity"]
        != root["calibration_release_identity"]
        or manifest["calibration_release_sha256"]
        != root["calibration_release_sha256"]
        or manifest["pit_target_panel_identity"]
        != root["pit_target_panel_identity"]
        or manifest["pit_target_panel_sha256"]
        != root["pit_target_panel_sha256"]
        or manifest["terminal_build_receipt_identity"]
        != root["terminal_build_receipt_identity"]
        or manifest["terminal_build_receipt_sha256"]
        != root["terminal_build_receipt_sha256"]
        or manifest["source_commit_sha"] != root["source_commit_sha"]
        or manifest["immutable_image_digest"] != root["immutable_image_digest"]
    ):
        _fail("L2b panel root/manifest binding differs")
    return root, root_identity, manifest, manifest_identity


def _open_projection_bundle_v1(
    identity_value: object, *, read_exact: ReadExact, label: str,
    topology: object | None = None, topology_identity: object | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    body, identity = _exact_read_json(
        identity_value,
        read_exact=read_exact,
        label=label,
        maximum_bytes=MAXIMUM_PROJECTION_BUNDLE_BYTES,
    )
    try:
        bundle = (
            projection_contract.validate_projection_bundle_v1(body)
            if topology is None
            else projection_contract.validate_projection_bundle_authority_v1(
                body,
                publication_identity=identity,
                topology=topology,
                topology_identity=topology_identity,
            )
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            f"{label} validation failed"
        ) from exc
    if canonical_json_bytes_v1(bundle) != canonical_json_bytes_v1(body):
        _fail(f"{label} canonical replay differs")
    return bundle, identity


def _open_control_projection_authority_v1(
    *, receipt_identity: object, read_exact: ReadExact,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    dict[str, object], dict[str, object], list[dict[str, object]],
]:
    """Exact-replay layer 00 and derive its topology-owned projections."""
    receipt_body, retained_receipt_identity = _exact_read_json(
        receipt_identity,
        read_exact=read_exact,
        label="control projection layer receipt",
        maximum_bytes=control_runtime.MAXIMUM_LAYER_EXECUTION_RECEIPT_BYTES,
    )
    try:
        compact = control_runtime.validate_layer_execution_receipt_v1(
            receipt_body
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "control projection receipt validation failed"
        ) from exc
    manifest_body, manifest_identity = _exact_read_json(
        compact["manifest_identity"],
        read_exact=read_exact,
        label="control projection task manifest",
        maximum_bytes=control_runtime.MAXIMUM_MANIFEST_BYTES,
    )
    try:
        control_manifest = control_runtime.validate_task_manifest_v1(
            manifest_body
        )
        receipt = control_runtime.validate_layer_execution_receipt_authority_v1(
            receipt_body,
            manifest=control_manifest,
            manifest_identity=manifest_identity,
            read_exact=read_exact,
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "control projection receipt exact authority replay failed"
        ) from exc
    if (
        receipt.get("layer_id") != "projection"
        or control_manifest.get("layer_id") != "projection"
        or receipt.get("all_tasks_completed") is not True
        or len(receipt.get("task_records", [])) != 1
    ):
        _fail("control projection authority is not terminal layer 00")
    design_body, design_identity = _exact_read_json(
        control_manifest["design_identity"],
        read_exact=read_exact,
        label="control design authority",
        maximum_bytes=control_runtime.MAXIMUM_MANIFEST_BYTES,
    )
    try:
        design = projection_contract.validate_design_authority_v1(
            design_body, publication_identity=design_identity
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "control design/topology authority replay failed"
        ) from exc
    topology = design["topology"]
    if (
        design_identity != control_manifest["design_identity"]
        or design["design_sha256"] != control_manifest["design_sha256"]
        or design["topology_identity"] != control_manifest["topology_identity"]
        or topology["topology_sha256"] != control_manifest["topology_sha256"]
    ):
        _fail("control design, topology, and layer receipt differ")
    publications = [
        _mapping(row, label=f"control projection publication[{index}]")
        for index, row in enumerate(
            receipt["task_records"][0]["publication_records"]
        )
    ]
    if (
        len(publications) != TASK_COUNT
        or any(
            set(row) != {"topology_ordinal", "role", "identity"}
            or row["role"] != "projection"
            for row in publications
        )
    ):
        _fail("control projection publication lattice differs")
    identities = [
        _identity(row["identity"], label=f"control projection[{index}]")
        for index, row in enumerate(publications)
    ]
    expected_descriptors = [
        row for row in topology["objects"] if row["role"] == "projection"
    ]
    if (
        len(expected_descriptors) != TASK_COUNT
        or [row["topology_ordinal"] for row in publications]
        != [row["ordinal"] for row in expected_descriptors]
        or [identity["uri"] for identity in identities]
        != [row["uri"] for row in expected_descriptors]
    ):
        _fail("control projection receipt/topology order differs")
    return (
        receipt,
        retained_receipt_identity,
        control_manifest,
        manifest_identity,
        design,
        identities,
    )


def prepare_selector_manifest_v1(
    *,
    l2b_panel_root_identity: object,
    control_projection_receipt_identity: object,
    terminal_build_receipt_identity: object,
    source_commit_sha: str,
    immutable_image_digest: str,
    reused_job_name: str,
    reused_job_uid: str,
    execution_scope: str,
    task0_smoke_receipt_identity: object | None,
    output_prefix: str,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Bind the L2b banks to the frozen 54-slate candidate-union projections."""
    if (
        _SHA40.fullmatch(source_commit_sha) is None
        or _IMAGE_DIGEST.fullmatch(immutable_image_digest) is None
        or reused_job_name != REUSED_JOB_NAME
        or reused_job_uid != REUSED_JOB_UID
        or execution_scope not in EXECUTION_SCOPES
    ):
        _fail("L2b selector code/image/job/scope authority differs")
    prefix = _output_prefix(output_prefix)
    smoke_receipt: dict[str, object] | None = None
    retained_smoke_identity: dict[str, object] | None = None
    if execution_scope == TASK0_SCOPE:
        if task0_smoke_receipt_identity is not None:
            _fail("task0 preparation cannot consume a prior smoke receipt")
    else:
        smoke_body, retained_smoke_identity = _exact_read_json(
            task0_smoke_receipt_identity,
            read_exact=read_exact,
            label="L2b selector task0 smoke receipt",
            maximum_bytes=1_000_000,
        )
        smoke_receipt = _validate_task0_smoke_receipt_shape_v1(smoke_body)
        if (
            smoke_receipt["l2b_panel_root_identity"]
            != _identity(l2b_panel_root_identity, label="L2b panel root")
            or smoke_receipt["control_projection_receipt_identity"]
            != _identity(control_projection_receipt_identity, label="control receipt")
            or smoke_receipt["terminal_build_receipt_identity"]
            != _identity(terminal_build_receipt_identity, label="build receipt")
            or smoke_receipt["source_commit_sha"] != source_commit_sha
            or smoke_receipt["immutable_image_digest"] != immutable_image_digest
            or smoke_receipt["reused_job_uid"] != reused_job_uid
        ):
            _fail("full54 preparation lacks its exact successful task0 authority")
        _replay_task0_smoke_authority_v1(
            smoke_receipt=smoke_receipt,
            smoke_receipt_identity=retained_smoke_identity,
            expected_l2b_panel_root_identity=l2b_panel_root_identity,
            expected_control_projection_receipt_identity=(
                control_projection_receipt_identity
            ),
            expected_terminal_build_receipt_identity=(
                terminal_build_receipt_identity
            ),
            expected_source_commit_sha=source_commit_sha,
            expected_immutable_image_digest=immutable_image_digest,
            expected_reused_job_uid=reused_job_uid,
            expected_output_prefix=prefix,
            read_exact=read_exact,
        )
    try:
        build_receipt, build_identity = l2b_panel._read_terminal_build_receipt(
            terminal_build_receipt_identity,
            source_commit_sha=source_commit_sha,
            immutable_image_digest=immutable_image_digest,
            read_exact=read_exact,
            label="L2b selector terminal build receipt",
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "L2b selector terminal build receipt replay failed"
        ) from exc
    image_tag = str(build_receipt.get("image_tag", ""))
    image_repository, separator, _tag = image_tag.rpartition(":")
    immutable_image_uri = f"{image_repository}@{immutable_image_digest}"
    if (
        separator != ":"
        or not image_repository
        or "@" in image_repository
        or _IMAGE_URI.fullmatch(immutable_image_uri) is None
    ):
        _fail("L2b selector terminal build image authority differs")
    root, root_identity, l2b_manifest, _ = _open_panel_root_v1(
        panel_root_identity=l2b_panel_root_identity, read_exact=read_exact
    )
    (
        control_receipt,
        control_receipt_identity,
        control_manifest,
        control_manifest_identity,
        control_design,
        identities,
    ) = _open_control_projection_authority_v1(
        receipt_identity=control_projection_receipt_identity,
        read_exact=read_exact,
    )
    task_rows: list[dict[str, object]] = []
    for index, (projection_identity, l2b_task) in enumerate(
        zip(identities, root["task_results"], strict=True)
    ):
        bundle, retained_identity = _open_projection_bundle_v1(
            projection_identity,
            read_exact=read_exact,
            label=f"projection bundle[{index}]",
            topology=control_design["topology"],
            topology_identity=control_manifest["topology_identity"],
        )
        expected_slate = str(l2b_task["slate_id"])
        unique_roster_count_by_fold = [
            len({
                tuple(str(player_id) for player_id in row["roster_player_ids"])
                for row in projection["candidates"]
            })
            for projection in bundle["fold_projections"]
        ]
        if (
            retained_identity != projection_identity
            or bundle["source_ordinal"] != index
            or bundle["slate_id"] != expected_slate
            or any(
                projection["later_source_identity"]
                != l2b_manifest["later_source_freeze_identity"]
                for projection in bundle["fold_projections"]
            )
            or any(count < rank150.RANKING_DEPTH for count in unique_roster_count_by_fold)
        ):
            _fail(
                "L2b selector projection/panel authority or unique-roster depth differs"
            )
        selector_candidate_count_by_fold = [
            len(_selector_candidate_view_v1(projection))
            for projection in bundle["fold_projections"]
        ]
        task_rows.append({
            "source_ordinal": index,
            "slate_id": expected_slate,
            "projection_bundle_identity": retained_identity,
            "projection_bundle_sha256": bundle["projection_bundle_sha256"],
            "unique_roster_count_by_fold": unique_roster_count_by_fold,
            "selector_candidate_count_by_fold": selector_candidate_count_by_fold,
            "l2b_task_result_identity": l2b_task["task_result_identity"],
            "l2b_task_result_sha256": l2b_task["task_result_sha256"],
            "result_uri": (
                f"{prefix}{execution_scope}/selector-results/"
                f"{index:02d}-{expected_slate}.json"
            ),
        })
    body = {
        "schema_version": TASK_MANIFEST_SCHEMA,
        "contract_id": CONTRACT_ID,
        "adapter_id": ADAPTER_ID,
        "l2b_panel_root_identity": root_identity,
        "l2b_panel_root_sha256": root["panel_root_sha256"],
        "l2b_task_manifest_identity": root["manifest_identity"],
        "l2b_task_manifest_sha256": root["manifest_sha256"],
        "control_projection_receipt_identity": control_receipt_identity,
        "control_projection_receipt_sha256": control_receipt[
            "layer_execution_receipt_sha256"
        ],
        "control_projection_manifest_identity": control_manifest_identity,
        "control_projection_manifest_sha256": control_manifest[
            "task_manifest_sha256"
        ],
        "control_design_identity": control_manifest["design_identity"],
        "control_design_sha256": control_design["design_sha256"],
        "control_topology_identity": control_manifest["topology_identity"],
        "control_topology_sha256": control_manifest["topology_sha256"],
        "terminal_build_receipt_identity": build_identity,
        "terminal_build_receipt_sha256": canonical_sha256_v1(build_receipt),
        "terminal_build_id": build_receipt["build_id"],
        "source_commit_sha": source_commit_sha,
        "immutable_image_digest": immutable_image_digest,
        "immutable_image_uri": immutable_image_uri,
        "reused_job_name": reused_job_name,
        "reused_job_uid": reused_job_uid,
        "execution_scope": execution_scope,
        "execution_task_count": 1 if execution_scope == TASK0_SCOPE else TASK_COUNT,
        "task0_smoke_receipt_identity": retained_smoke_identity,
        "task0_smoke_receipt_sha256": (
            None if smoke_receipt is None else smoke_receipt["smoke_receipt_sha256"]
        ),
        "later_source_freeze_identity": l2b_manifest[
            "later_source_freeze_identity"
        ],
        "task_count": TASK_COUNT,
        "task_rows": task_rows,
        "fraction_registry": [dict(row) for row in l2b_panel.FRACTION_REGISTRY],
        "world_blocks": list(WORLD_BLOCKS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "selector_lattice": _selector_lattice_v1(),
        "candidate_population_law": SELECTOR_CANDIDATE_VIEW_LAW,
        "output_prefix": prefix,
        "terminal_root_uri": f"{prefix}terminal-selector-root.json",
        **_FALSE_POLICY,
    }
    manifest = validate_selector_manifest_v1(
        _with_hash(body, field="task_manifest_sha256")
    )
    identity = _publish_json(
        uri=f"{prefix}selector-task-manifest-{execution_scope}.json",
        value=manifest,
        maximum_bytes=MAXIMUM_TASK_MANIFEST_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="L2b selector task manifest",
    )
    return {
        "schema_version": "corpus-r6-l2b-selector-preparation/v1",
        "task_manifest_identity": identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "task_count": TASK_COUNT,
        "complete": True,
        **_FALSE_POLICY,
    }


def validate_selector_manifest_v1(value: object) -> dict[str, object]:
    manifest = _mapping(value, label="L2b selector manifest")
    expected_fields = {
        "schema_version", "contract_id", "adapter_id",
        "l2b_panel_root_identity", "l2b_panel_root_sha256",
        "l2b_task_manifest_identity", "l2b_task_manifest_sha256",
        "control_projection_receipt_identity",
        "control_projection_receipt_sha256",
        "control_projection_manifest_identity",
        "control_projection_manifest_sha256", "control_design_identity",
        "control_design_sha256", "control_topology_identity",
        "control_topology_sha256", "terminal_build_receipt_identity",
        "terminal_build_receipt_sha256", "terminal_build_id",
        "source_commit_sha", "immutable_image_digest", "immutable_image_uri",
        "reused_job_name",
        "reused_job_uid", "execution_scope", "execution_task_count",
        "task0_smoke_receipt_identity", "task0_smoke_receipt_sha256",
        "later_source_freeze_identity", "task_count", "task_rows",
        "fraction_registry", "world_blocks", "worlds_per_block",
        "selector_lattice", "candidate_population_law", "output_prefix",
        "terminal_root_uri", *_FALSE_POLICY, "task_manifest_sha256",
    }
    if set(manifest) != expected_fields:
        _fail("L2b selector manifest fields differ")
    _validate_self_hash(
        manifest, field="task_manifest_sha256", label="L2b selector manifest"
    )
    rows = [
        _mapping(row, label=f"selector task row[{index}]")
        for index, row in enumerate(
            _sequence(manifest.get("task_rows"), label="selector task rows")
        )
    ]
    prefix = _output_prefix(manifest.get("output_prefix"))
    if (
        manifest.get("schema_version") != TASK_MANIFEST_SCHEMA
        or manifest.get("contract_id") != CONTRACT_ID
        or manifest.get("adapter_id") != ADAPTER_ID
        or manifest.get("task_count") != TASK_COUNT
        or len(rows) != TASK_COUNT
        or manifest.get("fraction_registry")
        != [dict(row) for row in l2b_panel.FRACTION_REGISTRY]
        or manifest.get("world_blocks") != list(WORLD_BLOCKS)
        or manifest.get("worlds_per_block") != WORLDS_PER_BLOCK
        or _canonical_json_object_v1(
            manifest.get("selector_lattice"), label="manifest selector lattice"
        ) != _selector_lattice_v1()
        or manifest.get("candidate_population_law")
        != SELECTOR_CANDIDATE_VIEW_LAW
        or _SHA40.fullmatch(str(manifest.get("source_commit_sha", ""))) is None
        or _IMAGE_DIGEST.fullmatch(
            str(manifest.get("immutable_image_digest", ""))
        ) is None
        or _IMAGE_URI.fullmatch(str(manifest.get("immutable_image_uri", "")))
        is None
        or not str(manifest.get("immutable_image_uri", "")).endswith(
            "@" + str(manifest.get("immutable_image_digest", ""))
        )
        or manifest.get("reused_job_name") != REUSED_JOB_NAME
        or manifest.get("reused_job_uid") != REUSED_JOB_UID
        or manifest.get("execution_scope") not in EXECUTION_SCOPES
        or manifest.get("execution_task_count") != (
            1 if manifest.get("execution_scope") == TASK0_SCOPE else TASK_COUNT
        )
        or (
            manifest.get("execution_scope") == TASK0_SCOPE
            and (manifest.get("task0_smoke_receipt_identity") is not None
                 or manifest.get("task0_smoke_receipt_sha256") is not None)
        )
        or (
            manifest.get("execution_scope") == FULL54_SCOPE
            and (not isinstance(manifest.get("task0_smoke_receipt_identity"), Mapping)
                 or _SHA64.fullmatch(str(manifest.get("task0_smoke_receipt_sha256", "")))
                 is None)
        )
        or type(manifest.get("terminal_build_id")) is not str
        or not manifest.get("terminal_build_id")
        or manifest.get("terminal_root_uri")
        != f"{prefix}terminal-selector-root.json"
        or any(manifest.get(field) is not False for field in _FALSE_POLICY)
    ):
        _fail("L2b selector manifest fixed law differs")
    for name in (
        "l2b_panel_root_identity", "l2b_task_manifest_identity",
        "later_source_freeze_identity", "control_projection_receipt_identity",
        "control_projection_manifest_identity", "control_design_identity",
        "control_topology_identity", "terminal_build_receipt_identity",
    ):
        _identity(manifest.get(name), label=name)
    for name in (
        "l2b_panel_root_sha256", "l2b_task_manifest_sha256",
        "control_projection_receipt_sha256",
        "control_projection_manifest_sha256", "control_design_sha256",
        "control_topology_sha256", "terminal_build_receipt_sha256",
    ):
        _digest(manifest.get(name), label=name)
    seen_projection_ids: set[bytes] = set()
    for index, (row, (season, week)) in enumerate(
        zip(rows, l2b_panel.EXPECTED_SLATES, strict=True)
    ):
        slate_id = f"{season}-w{week:02d}"
        if set(row) != {
            "source_ordinal", "slate_id", "projection_bundle_identity",
            "projection_bundle_sha256", "unique_roster_count_by_fold",
            "selector_candidate_count_by_fold",
            "l2b_task_result_identity",
            "l2b_task_result_sha256", "result_uri",
        }:
            _fail("L2b selector task-row fields differ")
        projection_identity = _identity(
            row.get("projection_bundle_identity"), label="projection bundle"
        )
        projection_key = canonical_json_bytes_v1(projection_identity)
        if (
            row.get("source_ordinal") != index
            or row.get("slate_id") != slate_id
            or projection_key in seen_projection_ids
            or row.get("result_uri")
            != (
                f"{prefix}{manifest['execution_scope']}/selector-results/"
                f"{index:02d}-{slate_id}.json"
            )
            or not isinstance(row.get("unique_roster_count_by_fold"), list)
            or len(row["unique_roster_count_by_fold"]) != len(WORLD_BLOCKS)
            or any(
                type(count) is not int or count < rank150.RANKING_DEPTH
                for count in row["unique_roster_count_by_fold"]
            )
            or not isinstance(row.get("selector_candidate_count_by_fold"), list)
            or len(row["selector_candidate_count_by_fold"]) != len(WORLD_BLOCKS)
            or any(
                type(count) is not int
                or not rank150.RANKING_DEPTH <= count <= successor.MAX_CANDIDATES
                for count in row["selector_candidate_count_by_fold"]
            )
        ):
            _fail("L2b selector task-row order or URI differs")
        seen_projection_ids.add(projection_key)
        _digest(row.get("projection_bundle_sha256"), label="projection SHA")
        _identity(row.get("l2b_task_result_identity"), label="L2b task result")
        _digest(row.get("l2b_task_result_sha256"), label="L2b task-result SHA")
    return manifest


def _open_selector_manifest_v1(
    *, manifest_identity: object, read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    body, identity = _exact_read_json(
        manifest_identity,
        read_exact=read_exact,
        label="L2b selector manifest",
        maximum_bytes=MAXIMUM_TASK_MANIFEST_BYTES,
    )
    manifest = validate_selector_manifest_v1(body)
    if identity["uri"] != (
        f"{manifest['output_prefix']}selector-task-manifest-"
        f"{manifest['execution_scope']}.json"
    ):
        _fail("selector manifest publication URI differs")
    try:
        build, build_identity = l2b_panel._read_terminal_build_receipt(
            manifest["terminal_build_receipt_identity"],
            source_commit_sha=manifest["source_commit_sha"],
            immutable_image_digest=manifest["immutable_image_digest"],
            read_exact=read_exact,
            label="selector manifest terminal build receipt",
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "selector manifest build authority replay failed"
        ) from exc
    (
        receipt,
        receipt_identity,
        control_manifest,
        control_manifest_identity,
        design,
        projection_identities,
    ) = _open_control_projection_authority_v1(
        receipt_identity=manifest["control_projection_receipt_identity"],
        read_exact=read_exact,
    )
    if (
        build_identity != manifest["terminal_build_receipt_identity"]
        or canonical_sha256_v1(build)
        != manifest["terminal_build_receipt_sha256"]
        or build["build_id"] != manifest["terminal_build_id"]
        or (
            f"{str(build.get('image_tag', '')).rpartition(':')[0]}@"
            f"{manifest['immutable_image_digest']}"
        ) != manifest["immutable_image_uri"]
        or receipt_identity != manifest["control_projection_receipt_identity"]
        or receipt["layer_execution_receipt_sha256"]
        != manifest["control_projection_receipt_sha256"]
        or control_manifest_identity
        != manifest["control_projection_manifest_identity"]
        or control_manifest["task_manifest_sha256"]
        != manifest["control_projection_manifest_sha256"]
        or control_manifest["design_identity"] != manifest["control_design_identity"]
        or design["design_sha256"] != manifest["control_design_sha256"]
        or control_manifest["topology_identity"]
        != manifest["control_topology_identity"]
        or control_manifest["topology_sha256"]
        != manifest["control_topology_sha256"]
        or projection_identities
        != [row["projection_bundle_identity"] for row in manifest["task_rows"]]
    ):
        _fail("selector manifest frozen-control/build authority differs")
    for index, (projection_identity, task_row) in enumerate(
        zip(projection_identities, manifest["task_rows"], strict=True)
    ):
        projection, retained_projection_identity = _open_projection_bundle_v1(
            projection_identity, read_exact=read_exact,
            label=f"selector manifest projection[{index}]",
            topology=design["topology"],
            topology_identity=control_manifest["topology_identity"],
        )
        exact_counts = [
            len(_selector_candidate_view_v1(fold_projection))
            for fold_projection in projection["fold_projections"]
        ]
        if (
            retained_projection_identity != projection_identity
            or exact_counts != task_row["selector_candidate_count_by_fold"]
        ):
            _fail("selector manifest executable candidate view replay differs")
    if manifest["execution_scope"] == FULL54_SCOPE:
        smoke_body, smoke_identity = _exact_read_json(
            manifest["task0_smoke_receipt_identity"],
            read_exact=read_exact,
            label="selector manifest task0 smoke receipt",
            maximum_bytes=1_000_000,
        )
        smoke = _validate_task0_smoke_receipt_shape_v1(smoke_body)
        if (
            smoke_identity != manifest["task0_smoke_receipt_identity"]
            or smoke.get("smoke_receipt_sha256")
            != manifest["task0_smoke_receipt_sha256"]
            or smoke.get("l2b_panel_root_identity")
            != manifest["l2b_panel_root_identity"]
            or smoke.get("control_projection_receipt_identity")
            != manifest["control_projection_receipt_identity"]
            or smoke.get("terminal_build_receipt_identity")
            != manifest["terminal_build_receipt_identity"]
            or smoke.get("source_commit_sha") != manifest["source_commit_sha"]
            or smoke.get("immutable_image_digest")
            != manifest["immutable_image_digest"]
            or smoke.get("reused_job_uid") != manifest["reused_job_uid"]
        ):
            _fail("selector manifest task0 smoke authority replay differs")
        _replay_task0_smoke_authority_v1(
            smoke_receipt=smoke,
            smoke_receipt_identity=smoke_identity,
            expected_l2b_panel_root_identity=manifest["l2b_panel_root_identity"],
            expected_control_projection_receipt_identity=manifest[
                "control_projection_receipt_identity"
            ],
            expected_terminal_build_receipt_identity=manifest[
                "terminal_build_receipt_identity"
            ],
            expected_source_commit_sha=str(manifest["source_commit_sha"]),
            expected_immutable_image_digest=str(
                manifest["immutable_image_digest"]
            ),
            expected_reused_job_uid=str(manifest["reused_job_uid"]),
            expected_output_prefix=str(manifest["output_prefix"]),
            read_exact=read_exact,
        )
    return manifest, identity


def _scoring_players_v1(
    *, source: Mapping[str, object], source_ordinal: int,
) -> tuple[evaluator.ScoringPlayerV1, ...]:
    try:
        frozen = later.validate_source_freeze(
            source,
            expected_freeze_sha256=str(source.get("freeze_sha256", "")),
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "later-source freeze validation failed"
        ) from exc
    slates = _sequence(frozen.get("slates"), label="later-source slates")
    if len(slates) != TASK_COUNT:
        _fail("later-source slate count differs")
    row = _mapping(slates[source_ordinal], label="later-source slate")
    players = tuple(
        evaluator._scoring_player_v1(value)
        for value in _sequence(row.get("catalog"), label="later-source catalog")
    )
    if not players or len({player.player_id for player in players}) != len(players):
        _fail("later-source scoring-player catalog differs")
    return players


def _open_l2b_task_worlds_v1(
    *,
    source_ordinal: int,
    task_result_identity: Mapping[str, object],
    root: Mapping[str, object],
    l2b_manifest: Mapping[str, object],
    l2b_manifest_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, dict[str, evaluator.ScoringWorldBlockV1]]:
    body, retained_identity = _exact_read_json(
        task_result_identity,
        read_exact=read_exact,
        label=f"L2b task result[{source_ordinal}]",
        maximum_bytes=l2b_panel.MAXIMUM_TASK_RESULT_BYTES,
    )
    try:
        result = l2b_panel._validate_task_result_v1(body)
        l2b_panel._validate_task_result_lineage_v1(
            manifest=l2b_manifest,
            retained_manifest_identity=l2b_manifest_identity,
            task_index=source_ordinal,
            task_result_identity=retained_identity,
            result=result,
            read_exact=read_exact,
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            f"L2b task result[{source_ordinal}] exact replay failed"
        ) from exc
    descriptor = root["task_results"][source_ordinal]
    if (
        retained_identity != descriptor["task_result_identity"]
        or result["task_result_sha256"] != descriptor["task_result_sha256"]
    ):
        _fail("L2b task result/root binding differs")
    worlds: dict[str, dict[str, evaluator.ScoringWorldBlockV1]] = {
        fraction_id: {} for fraction_id in FRACTION_IDS
    }
    for artifact in result["artifacts"]:
        fraction_id = str(artifact["fraction_id"])
        block = str(artifact["block"])
        receipt_body, receipt_identity = _exact_read_json(
            artifact["world_artifact_receipt_identity"],
            read_exact=read_exact,
            label=f"{fraction_id}/{block} receipt",
            maximum_bytes=l2b_panel.MAXIMUM_TASK_RESULT_BYTES,
        )
        try:
            receipt = l2b_panel._validate_world_receipt(receipt_body)
        except Exception as exc:
            raise CorpusR6L2BSelectorAdapterV1Error(
                f"{fraction_id}/{block} receipt validation failed"
            ) from exc
        raw, artifact_identity = _exact_read_bytes(
            artifact["world_artifact_identity"],
            read_exact=read_exact,
            label=f"{fraction_id}/{block} artifact",
            maximum_bytes=l2b_panel.MAXIMUM_WORLD_ARTIFACT_BYTES,
        )
        if (
            receipt_identity != artifact["world_artifact_receipt_identity"]
            or receipt["receipt_sha256"]
            != artifact["world_artifact_receipt_sha256"]
            or receipt["world_artifact_identity"] != artifact_identity
        ):
            _fail("L2b task artifact/receipt binding differs")
        try:
            loaded = l2b_panel.load_l2b_world_artifact_v1(receipt, raw)
        except Exception as exc:
            raise CorpusR6L2BSelectorAdapterV1Error(
                f"{fraction_id}/{block} world load failed"
            ) from exc
        worlds[fraction_id][block] = loaded
    if any(tuple(by_block) != WORLD_BLOCKS for by_block in worlds.values()):
        _fail("L2b task world lattice differs")
    return worlds


def _aligned_draws_v1(
    *,
    players: Sequence[evaluator.ScoringPlayerV1],
    world: evaluator.ScoringWorldBlockV1,
) -> np.ndarray:
    player_ids = tuple(player.player_id for player in players)
    if (
        set(world.player_ids) != set(player_ids)
        or len(world.player_ids) != len(player_ids)
    ):
        _fail("L2b world player universe differs from candidate catalog")
    index = {player_id: ordinal for ordinal, player_id in enumerate(world.player_ids)}
    draws = np.ascontiguousarray(
        world.player_draws[[index[player_id] for player_id in player_ids]],
        dtype=np.float32,
    )
    if draws.shape != (len(player_ids), WORLDS_PER_BLOCK):
        _fail("aligned L2b player-world matrix differs")
    draws.flags.writeable = False
    return draws


def _cross_score_projection_block_v1(
    *,
    players: Sequence[evaluator.ScoringPlayerV1],
    projection: Mapping[str, object],
    world: evaluator.ScoringWorldBlockV1,
    candidate_rows: Sequence[Mapping[str, object]] | None = None,
) -> np.ndarray:
    retained_candidates = (
        projection["candidates"] if candidate_rows is None else candidate_rows
    )
    rosters = [row["roster_player_ids"] for row in retained_candidates]
    try:
        return evaluator._cross_score_full_union_v1(
            players,
            _aligned_draws_v1(players=players, world=world),
            rosters,
            expected_worlds=WORLDS_PER_BLOCK,
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "L2b full-union cross-score failed"
        ) from exc


def _selector_sources_v1(
    *, grouped: Mapping[str, object], ranked: Mapping[str, object],
    dpp: Mapping[str, object], challengers: Mapping[str, object],
) -> list[tuple[str, int, str, str, Sequence[object], Sequence[int]]]:
    sources: list[
        tuple[str, int, str, str, Sequence[object], Sequence[int]]
    ] = []
    for raw in _sequence(grouped.get("selectors"), label="grouped selectors"):
        row = _mapping(raw, label="grouped selector")
        sources.append((
            SELECTOR_FAMILIES[0], int(row.get("ordinal", -1)),
            str(row.get("preset_id")), str(row.get("selector_result_sha256")),
            _sequence(row.get("prefixes"), label="grouped prefixes"),
            successor.PREFIX_SIZES,
        ))
    for raw in _sequence(ranked.get("selectors"), label="rank150 selectors"):
        row = _mapping(raw, label="rank150 selector")
        sources.append((
            SELECTOR_FAMILIES[1], int(row.get("ordinal", -1)),
            str(row.get("preset_id")), str(row.get("selector_result_sha256")),
            _sequence(row.get("entry_books"), label="rank150 books"),
            rank150.ENTRY_BUDGETS,
        ))
    dpp_contract = _mapping(dpp.get("strategy_contract"), label="DPP contract")
    sources.append((
        SELECTOR_FAMILIES[2], 0, str(dpp_contract.get("strategy_id")),
        str(dpp.get("result_sha256")),
        _sequence(dpp.get("prefixes"), label="DPP prefixes"),
        diversity.PREFIX_SIZES,
    ))
    for raw in _sequence(
        challengers.get("selectors"), label="tail-ladder diversity selectors"
    ):
        row = _mapping(raw, label="tail-ladder diversity selector")
        if row.get("strategy_id") not in TAIL_DIVERSITY_ACTIVE_STRATEGY_IDS:
            continue
        normalized_books = []
        for raw_book in _sequence(
            row.get("entry_books"), label="tail-ladder diversity books"
        ):
            book = _mapping(raw_book, label="tail-ladder diversity book")
            normalized_books.append({
                "prefix_size": book.get("entry_budget"),
                "selected_lineup_ids": book.get("selected_lineup_ids"),
                "selected_lineup_ids_sha256": book.get(
                    "selected_lineup_ids_sha256"
                ),
                "selected_rosters_sha256": book.get(
                    "selected_rosters_sha256"
                ),
                "prefix_sha256": book.get("book_sha256"),
            })
        sources.append((
            SELECTOR_FAMILIES[3], int(row.get("ordinal", -1)),
            str(row.get("strategy_id")),
            str(row.get("selector_result_sha256")), normalized_books,
            diversity_challengers.ENTRY_BUDGETS,
        ))
    if len(sources) != SELECTOR_COUNT_PER_FRACTION_FOLD:
        _fail("L2b selector lattice differs")
    return sources


_PREFIX_FIELDS: Final = {
    "prefix_size", "selected_lineup_ids", "selected_lineup_ids_sha256",
    "selected_rosters_sha256", "prefix_sha256",
}
_DPP_PREFIX_FIELDS: Final = _PREFIX_FIELDS | {
    "compact_diagnostics", "compact_diagnostics_sha256",
}
_GROUPED_RESULT_FIELDS: Final = {
    "schema_version", "implementation", "implementation_sha256",
    "preset_registry", "preset_registry_sha256", "input_binding",
    "input_binding_sha256", "shared_preprocessing",
    "shared_preprocessing_sha256", "selector_count", "selectors",
    "selector_result_sha256s", "entry_budget", "prefix_sizes", "policy",
    "result_sha256",
}
_GROUPED_SELECTOR_FIELDS: Final = {
    "ordinal", "preset_id", "preset_sha256", "adapter_id",
    "parameters_sha256", "executable_fingerprint_sha256",
    "selected_canonical_indices", "selected_lineup_ids",
    "selected_lineup_ids_sha256", "selected_rosters_sha256", "prefixes",
    "compact_diagnostics", "compact_diagnostics_sha256",
    "selector_result_sha256",
}
_RANKED_RESULT_FIELDS: Final = {
    "schema_version", "implementation", "implementation_sha256",
    "preset_registry", "preset_registry_sha256", "input_binding",
    "input_binding_sha256", "shared_preprocessing",
    "shared_preprocessing_sha256", "selector_count", "selectors",
    "selector_result_sha256s", "entry_budgets", "ranking_depth",
    "exact_prefix_consistency_verified", "score_extrapolation_performed",
    "policy", "result_sha256",
}
_RANKED_SELECTOR_FIELDS: Final = {
    "ordinal", "preset_id", "preset_sha256", "adapter_id",
    "executable_fingerprint_sha256", "ranked_canonical_indices",
    "ranked_lineup_ids", "ranked_lineup_ids_sha256", "entry_books",
    "entry_book_sha256s", "budget_diagnostics", "continuation_diagnostics",
    "continuation_diagnostics_sha256", "selector_result_sha256",
}
_DPP_RESULT_FIELDS: Final = {
    "schema_version", "strategy_contract", "strategy_contract_sha256",
    "input_binding", "input_binding_sha256", "preprocessing",
    "preprocessing_sha256", "selected_canonical_indices",
    "selected_lineup_ids", "selected_lineup_ids_sha256",
    "selected_rosters_sha256", "selection_trace", "selection_trace_sha256",
    "entry_budget", "prefix_sizes", "prefixes", "prefix_sha256s", "policy",
    "result_sha256",
}
_TAIL_DIVERSITY_RESULT_FIELDS: Final = {
    "schema_version", "contract", "contract_sha256", "input_binding",
    "input_binding_sha256", "selector_count", "selectors",
    "selector_result_sha256s", "entry_budgets", "ranking_depth",
    "heldout_evaluation_performed", "policy", "result_sha256",
}
_TAIL_DIVERSITY_SELECTOR_FIELDS: Final = {
    "schema_version", "ordinal", "strategy_id", "selector_kind",
    "base_strategy_id", "base_strategy_sha256", "status",
    "greedy_prefix_count", "ranked_canonical_indices", "ranked_lineup_ids",
    "ranked_lineup_ids_sha256", "selection_trace_sha256",
    "selector_summary", "entry_budgets_available", "entry_books",
    "entry_book_sha256s", "exact_prefix_consistency_verified", "policy",
    "selector_result_sha256",
}
_TAIL_DIVERSITY_BOOK_FIELDS: Final = {
    "schema_version", "entry_budget", "selected_lineup_ids",
    "selected_lineup_ids_sha256", "selected_rosters_sha256",
    "fit_book_maximum_mean_micro", "roster_overlap_diagnostics",
    "effective_tail_shots", "effective_tail_shots_sha256",
    "heldout_evaluation_performed", "uses_realized_outcomes", "book_sha256",
}


def _validate_exact_tail_diversity_shapes_v1(
    *, challengers: object, candidate_rows: Sequence[Mapping[str, object]],
) -> None:
    """Require four exact nested books and independently recheck hard caps."""
    result = _mapping(challengers, label="tail-ladder diversity result")
    if set(result) != _TAIL_DIVERSITY_RESULT_FIELDS:
        _fail("persisted tail-ladder diversity result fields differ")
    _validate_self_hash(
        result, field="result_sha256", label="tail-ladder diversity result"
    )
    contract = diversity_challengers.diversity_challenger_contract_v1()
    selectors = [
        _mapping(row, label="tail-ladder diversity selector")
        for row in _sequence(
            result.get("selectors"), label="tail-ladder diversity selectors"
        )
    ]
    expected_strategy_ids = [
        *[
            f"tail-ladder-roster-overlap-cap-{gamma}-v1"
            for gamma in diversity_challengers.OVERLAP_CAPS
        ],
        "tail-ladder-evil-twin-strict-200-v1",
    ]
    roster_by_lineup = {
        str(row["lineup_id"]): tuple(
            str(player_id) for player_id in row["roster_player_ids"]
        )
        for row in candidate_rows
    }
    if (
        result.get("schema_version") != diversity_challengers.RESULT_SCHEMA
        or result.get("contract") != contract
        or result.get("contract_sha256") != contract["contract_sha256"]
        or result.get("selector_count") != len(expected_strategy_ids)
        or len(selectors) != len(expected_strategy_ids)
        or result.get("selector_result_sha256s")
        != [row.get("selector_result_sha256") for row in selectors]
        or result.get("entry_budgets")
        != list(diversity_challengers.ENTRY_BUDGETS)
        or result.get("ranking_depth") != diversity_challengers.RANKING_DEPTH
        or result.get("heldout_evaluation_performed") is not False
        or result.get("policy") != diversity_challengers._FALSE_POLICY
    ):
        _fail("tail-ladder diversity fixed result law differs")
    for ordinal, (selector, strategy_id) in enumerate(
        zip(selectors, expected_strategy_ids, strict=True)
    ):
        if set(selector) != _TAIL_DIVERSITY_SELECTOR_FIELDS:
            _fail("persisted tail-ladder diversity selector fields differ")
        _validate_self_hash(
            selector,
            field="selector_result_sha256",
            label="tail-ladder diversity selector",
        )
        ranked = [
            str(value) for value in _sequence(
                selector.get("ranked_lineup_ids"),
                label="tail-ladder diversity ranked lineups",
            )
        ]
        books = [
            _mapping(row, label="tail-ladder diversity book")
            for row in _sequence(
                selector.get("entry_books"),
                label="tail-ladder diversity books",
            )
        ]
        available_budgets = [
            int(value) for value in _sequence(
                selector.get("entry_budgets_available"),
                label="tail-ladder diversity available budgets",
            )
        ]
        active = strategy_id in TAIL_DIVERSITY_ACTIVE_STRATEGY_IDS
        if (
            selector.get("ordinal") != ordinal
            or selector.get("strategy_id") != strategy_id
            or selector.get("base_strategy_id")
            != diversity_challengers.BASE_STRATEGY_ID
            or selector.get("base_strategy_sha256")
            != diversity_challengers.BASE_STRATEGY_SHA256
            or selector.get("greedy_prefix_count") != len(ranked)
            or not 1 <= len(ranked) <= diversity_challengers.RANKING_DEPTH
            or len(set(ranked)) != len(ranked)
            or not set(ranked) <= set(roster_by_lineup)
            or selector.get("ranked_lineup_ids_sha256")
            != canonical_sha256_v1(ranked)
            or [book.get("entry_budget") for book in books]
            != available_budgets
            or available_budgets
            != [
                budget for budget in diversity_challengers.ENTRY_BUDGETS
                if budget <= len(ranked)
            ]
            or selector.get("entry_book_sha256s")
            != [book.get("book_sha256") for book in books]
            or selector.get("exact_prefix_consistency_verified") is not True
            or selector.get("policy") != diversity_challengers._FALSE_POLICY
        ):
            _fail("tail-ladder diversity selector support law differs")
        if active and (
            selector.get("status") != "exact-rank-150"
            or len(ranked) != diversity_challengers.RANKING_DEPTH
            or available_budgets
            != list(diversity_challengers.ENTRY_BUDGETS)
        ):
            _fail("active tail-ladder diversity selector lacks exact rank-150")
        for book in books:
            if set(book) != _TAIL_DIVERSITY_BOOK_FIELDS:
                _fail("persisted tail-ladder diversity book fields differ")
            _validate_self_hash(
                book, field="book_sha256", label="tail-ladder diversity book"
            )
            budget = int(book["entry_budget"])
            selected = [str(value) for value in book["selected_lineup_ids"]]
            rosters = [list(roster_by_lineup[lineup_id]) for lineup_id in selected]
            if (
                selected != ranked[:budget]
                or book.get("selected_lineup_ids_sha256")
                != canonical_sha256_v1(selected)
                or book.get("selected_rosters_sha256")
                != canonical_sha256_v1(rosters)
                or book.get("heldout_evaluation_performed") is not False
                or book.get("uses_realized_outcomes") is not False
            ):
                _fail("tail-ladder diversity book differs from its exact prefix")
        if ordinal < len(diversity_challengers.OVERLAP_CAPS):
            gamma = diversity_challengers.OVERLAP_CAPS[ordinal]
            summary = _mapping(
                selector.get("selector_summary"),
                label="tail-ladder overlap-cap summary",
            )
            if (
                summary.get("overlap_cap") != gamma
                or summary.get("ranking_depth_reached")
                != (len(ranked) == diversity_challengers.RANKING_DEPTH)
                or summary.get("cap_relaxed") is not False
            ):
                _fail("tail-ladder diversity overlap-cap summary differs")
            for left in range(len(ranked)):
                left_roster = set(roster_by_lineup[ranked[left]])
                for right in range(left + 1, len(ranked)):
                    if len(
                        left_roster & set(roster_by_lineup[ranked[right]])
                    ) > gamma:
                        _fail("tail-ladder diversity selected roster violates cap")


def _validate_persisted_selector_shapes_v1(
    *, grouped: object, ranked: object, dpp: object, challengers: object,
    candidate_rows: Sequence[Mapping[str, object]],
) -> None:
    """Reject unregistered nested fields after pure selector replay."""
    grouped_item = _mapping(grouped, label="grouped selector result")
    ranked_item = _mapping(ranked, label="rank150 selector result")
    dpp_item = _mapping(dpp, label="DPP selector result")
    if (
        set(grouped_item) != _GROUPED_RESULT_FIELDS
        or set(ranked_item) != _RANKED_RESULT_FIELDS
        or set(dpp_item) != _DPP_RESULT_FIELDS
    ):
        _fail("persisted selector result fields differ")
    _validate_self_hash(grouped_item, field="result_sha256", label="grouped result")
    _validate_self_hash(ranked_item, field="result_sha256", label="rank150 result")
    _validate_self_hash(dpp_item, field="result_sha256", label="DPP result")
    groups = (
        (grouped_item["selectors"], _GROUPED_SELECTOR_FIELDS, "prefixes"),
        (ranked_item["selectors"], _RANKED_SELECTOR_FIELDS, "entry_books"),
    )
    for raw_selectors, expected_fields, prefix_field in groups:
        for raw_selector in _sequence(raw_selectors, label="selector rows"):
            selector = _mapping(raw_selector, label="selector row")
            if set(selector) != expected_fields:
                _fail("persisted selector row fields differ")
            _validate_self_hash(
                selector,
                field="selector_result_sha256",
                label="persisted selector row",
            )
            for raw_prefix in _sequence(
                selector[prefix_field], label="selector prefixes"
            ):
                prefix = _mapping(raw_prefix, label="selector prefix")
                if set(prefix) != _PREFIX_FIELDS:
                    _fail("persisted selector prefix fields differ")
                _validate_self_hash(
                    prefix, field="prefix_sha256", label="selector prefix"
                )
    for raw_prefix in _sequence(dpp_item["prefixes"], label="DPP prefixes"):
        prefix = _mapping(raw_prefix, label="DPP prefix")
        if set(prefix) != _DPP_PREFIX_FIELDS:
            _fail("persisted DPP prefix fields differ")
        _validate_self_hash(prefix, field="prefix_sha256", label="DPP prefix")
    _validate_exact_tail_diversity_shapes_v1(
        challengers=challengers, candidate_rows=candidate_rows
    )


def _book_descriptors_v1(
    *,
    fraction_id: str,
    heldout_block: str,
    population_id: str,
    candidate_rows: Sequence[Mapping[str, object]],
    grouped: Mapping[str, object],
    ranked: Mapping[str, object],
    dpp: Mapping[str, object],
    challengers: Mapping[str, object],
) -> list[dict[str, object]]:
    roster_by_lineup = {
        str(row["lineup_id"]): tuple(
            str(player_id) for player_id in row["roster_player_ids"]
        )
        for row in candidate_rows
    }
    sampled = set(roster_by_lineup)
    rows: list[dict[str, object]] = []
    for family, ordinal, selector_id, source_sha, prefixes, budgets in (
        _selector_sources_v1(
            grouped=grouped, ranked=ranked, dpp=dpp,
            challengers=challengers,
        )
    ):
        normalized_prefixes = [
            _mapping(value, label=f"{family} prefix") for value in prefixes
        ]
        if [row.get("prefix_size") for row in normalized_prefixes] != list(budgets):
            _fail("L2b selector prefix budget lattice differs")
        for prefix in normalized_prefixes:
            selected = [
                str(value) for value in _sequence(
                    prefix.get("selected_lineup_ids"),
                    label="selected lineup IDs",
                )
            ]
            entry_budget = int(prefix["prefix_size"])
            if (
                len(selected) != entry_budget
                or len(set(selected)) != entry_budget
                or not set(selected) <= sampled
                or len({roster_by_lineup[lineup_id] for lineup_id in selected})
                != entry_budget
                or prefix.get("selected_lineup_ids_sha256")
                != canonical_sha256_v1(selected)
            ):
                _fail("L2b selected book differs from its candidate population")
            coordinate = {
                "adapter_id": ADAPTER_ID,
                "metric_kind": "selected-book",
                "fraction_id": fraction_id,
                "heldout_block": heldout_block,
                "selector_family": family,
                "selector_ordinal": ordinal,
                "selector_id": selector_id,
                "entry_budget": entry_budget,
            }
            rows.append(_with_hash({
                "coordinate": coordinate,
                "coordinate_sha256": canonical_sha256_v1(coordinate),
                "population_id": population_id,
                "selected_lineup_ids": selected,
                "selected_lineup_ids_sha256": canonical_sha256_v1(selected),
                "source_selector_result_sha256": source_sha,
                "source_prefix_sha256": prefix["prefix_sha256"],
            }, field="book_descriptor_sha256"))
    if (
        len(rows) != BOOK_COUNT_PER_FRACTION_FOLD
        or len({row["coordinate_sha256"] for row in rows}) != len(rows)
    ):
        _fail("L2b normalized book lattice differs")
    return rows


def _unique_roster_candidates_v1(
    candidates_value: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Keep the first frozen lineup identity for each exact roster."""
    retained: list[dict[str, object]] = []
    seen_lineups: set[str] = set()
    seen_rosters: set[tuple[str, ...]] = set()
    for ordinal, raw in enumerate(candidates_value):
        row = _mapping(raw, label=f"candidate[{ordinal}]")
        lineup_id = str(row.get("lineup_id", ""))
        roster = tuple(
            str(player_id) for player_id in _sequence(
                row.get("roster_player_ids"), label=f"candidate[{ordinal}] roster"
            )
        )
        if (
            not lineup_id
            or lineup_id in seen_lineups
            or len(roster) != 9
            or len(set(roster)) != 9
        ):
            _fail("L2b candidate lineup/roster identity differs")
        seen_lineups.add(lineup_id)
        if roster in seen_rosters:
            continue
        seen_rosters.add(roster)
        retained.append(dict(row))
    if len(retained) < rank150.RANKING_DEPTH:
        _fail("L2b fold lacks 150 unique rosters")
    return retained


SELECTOR_CANDIDATE_VIEW_LAW: Final = (
    "frozen-v7-broad-screen-u-replicate-0-unique-roster/v1"
)


def _selector_candidate_view_v1(
    projection: Mapping[str, object],
) -> list[dict[str, object]]:
    """Derive the registered exact selector-sized view from projection authority."""
    sample = projection_contract.deterministic_equal_count_samples_from_projection_v1(
        projection, phase=projection_contract.BROAD_SCREEN_PHASE
    )
    replicate = _mapping(sample["replicates"][0], label="broad-screen replicate 0")
    u_views = [
        _mapping(row, label="broad-screen U view")
        for row in replicate["views"] if row.get("view_id") == "U"
    ]
    if len(u_views) != 1:
        _fail("L2b frozen broad-screen sample omits exact U view")
    sampled_ids = [str(value) for value in u_views[0]["sampled_lineup_ids"]]
    by_id = {str(row["lineup_id"]): dict(row) for row in projection["candidates"]}
    if len(sampled_ids) > successor.MAX_CANDIDATES or not set(sampled_ids) <= set(by_id):
        _fail("L2b frozen U sample differs from projection authority")
    retained: list[dict[str, object]] = []
    seen_rosters: set[tuple[str, ...]] = set()
    for lineup_id in sampled_ids:
        candidate = by_id[lineup_id]
        roster = tuple(str(value) for value in candidate["roster_player_ids"])
        if roster not in seen_rosters:
            retained.append(candidate)
            seen_rosters.add(roster)
    if not rank150.RANKING_DEPTH <= len(retained) <= successor.MAX_CANDIDATES:
        _fail("L2b authority-derived selector view is not executable")
    return retained


def _run_selectors_v1(
    *,
    fraction_id: str,
    heldout_block: str,
    projection: Mapping[str, object],
    players: Sequence[evaluator.ScoringPlayerV1],
    worlds: Mapping[str, evaluator.ScoringWorldBlockV1],
) -> dict[str, object]:
    candidates = _selector_candidate_view_v1(projection)
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    training_blocks = [str(block) for block in projection["training_blocks"]]
    if (
        projection.get("heldout_block") != heldout_block
        or training_blocks != [block for block in WORLD_BLOCKS if block != heldout_block]
        or not rank150.RANKING_DEPTH <= len(lineup_ids) <= successor.MAX_CANDIDATES
        or lineup_ids != sorted(set(lineup_ids))
    ):
        _fail("L2b selector projection candidate/fold law differs")

    training = np.empty(
        (len(lineup_ids), len(training_blocks) * WORLDS_PER_BLOCK),
        dtype=np.float64,
        order="C",
    )
    for block_ordinal, block in enumerate(training_blocks):
        start = block_ordinal * WORLDS_PER_BLOCK
        stop = start + WORLDS_PER_BLOCK
        training[:, start:stop] = _cross_score_projection_block_v1(
            players=players, projection=projection, world=worlds[block],
            candidate_rows=candidates,
        )
    training.flags.writeable = False
    kwargs = {
        "sampled_lineup_ids": lineup_ids,
        "training_score_matrix": training,
        "candidate_rows": candidates,
        "training_blocks": training_blocks,
        "worlds_per_block": WORLDS_PER_BLOCK,
    }
    presets = successor.frozen_native_preset_registry_v1()
    try:
        grouped = successor.run_grouped_native_selectors_v1(
            **kwargs, preset_registry=presets
        )
        ranked = rank150.run_exact_rank150_continuation_v1(
            **kwargs, preset_registry=presets
        )
        dpp = diversity.run_effective_independent_shots_selector_v1(**kwargs)
        tail_diversity = (
            diversity_challengers.run_diversity_challengers_v1(**kwargs)
        )
        successor.validate_grouped_native_selector_result_v1(
            grouped, **kwargs, preset_registry=presets
        )
        rank150.validate_exact_rank150_continuation_v1(
            ranked, **kwargs, preset_registry=presets
        )
        diversity.validate_effective_independent_shots_result_v1(
            dpp, **kwargs
        )
        diversity_challengers.validate_diversity_challengers_v1(
            tail_diversity, **kwargs
        )
        _validate_persisted_selector_shapes_v1(
            grouped=grouped, ranked=ranked, dpp=dpp,
            challengers=tail_diversity, candidate_rows=candidates,
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "L2b frozen selector execution failed"
        ) from exc

    training_sha = _matrix_sha256(
        training, label=f"{fraction_id}-{heldout_block}-training"
    )
    population_id = f"full-union/holdout-{heldout_block}"
    books = _book_descriptors_v1(
        fraction_id=fraction_id,
        heldout_block=heldout_block,
        population_id=population_id,
        candidate_rows=candidates,
        grouped=grouped,
        ranked=ranked,
        dpp=dpp,
        challengers=tail_diversity,
    )
    body = {
        "schema_version": FRACTION_RESULT_SCHEMA,
        "fraction_id": fraction_id,
        "heldout_block": heldout_block,
        "training_blocks": training_blocks,
        "candidate_lineup_count": len(lineup_ids),
        "candidate_lineup_ids_sha256": canonical_sha256_v1(lineup_ids),
        "candidate_rows_sha256": canonical_sha256_v1(candidates),
        "training_score_shape": list(training.shape),
        "training_score_matrix_sha256": training_sha,
        "grouped_result": grouped,
        "grouped_result_sha256": grouped["result_sha256"],
        "rank150_result": ranked,
        "rank150_result_sha256": ranked["result_sha256"],
        "dpp_result": dpp,
        "dpp_result_sha256": dpp["result_sha256"],
        "tail_diversity_result": tail_diversity,
        "tail_diversity_result_sha256": tail_diversity["result_sha256"],
        "selector_results_exact_pure_replayed": True,
        "book_count": len(books),
        "books": books,
        "books_sha256": canonical_sha256_v1(books),
        "heldout_cross_score_executed": False,
        **_FALSE_POLICY,
    }
    return _with_hash(body, field="fraction_result_sha256")


def _lineups_from_candidates_v1(
    candidates: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        roster = [str(value) for value in candidate["roster_player_ids"]]
        rows.append({
            "lineup_id": str(candidate["lineup_id"]),
            "roster_player_ids": roster,
            "roster_sha256": canonical_sha256_v1(roster),
        })
    return rows


def build_slate_result_v1(
    *,
    source_ordinal: int,
    manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    projection_bundle: Mapping[str, object],
    players: Sequence[evaluator.ScoringPlayerV1],
    worlds_by_fraction: Mapping[str, Mapping[str, evaluator.ScoringWorldBlockV1]],
) -> dict[str, object]:
    """Cross-score and select one slate while persisting no score values."""
    retained_manifest = validate_selector_manifest_v1(manifest)
    if type(source_ordinal) is not int or not 0 <= source_ordinal < TASK_COUNT:
        _fail("L2b selector source ordinal differs")
    task_row = retained_manifest["task_rows"][source_ordinal]
    try:
        bundle = projection_contract.validate_projection_bundle_v1(
            projection_bundle
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "L2b selector projection validation failed"
        ) from exc
    if (
        bundle["source_ordinal"] != source_ordinal
        or bundle["slate_id"] != task_row["slate_id"]
        or bundle["projection_bundle_sha256"]
        != task_row["projection_bundle_sha256"]
        or tuple(worlds_by_fraction) != FRACTION_IDS
        or any(tuple(worlds_by_fraction[fraction_id]) != WORLD_BLOCKS
               for fraction_id in FRACTION_IDS)
        or task_row["unique_roster_count_by_fold"] != [
            len({
                tuple(str(player_id) for player_id in row["roster_player_ids"])
                for row in projection["candidates"]
            })
            for projection in bundle["fold_projections"]
        ]
        or task_row["selector_candidate_count_by_fold"] != [
            len(_selector_candidate_view_v1(projection))
            for projection in bundle["fold_projections"]
        ]
    ):
        _fail("L2b selector slate authority differs")

    folds: list[dict[str, object]] = []
    normalized_populations: list[dict[str, object]] = []
    normalized_books: list[dict[str, object]] = []
    for fold_ordinal, (heldout_block, projection) in enumerate(
        zip(WORLD_BLOCKS, bundle["fold_projections"], strict=True)
    ):
        candidates = _selector_candidate_view_v1(projection)
        population_id = f"full-union/holdout-{heldout_block}"
        population = {
            "population_id": population_id,
            "dimensions": {
                "fold_ordinal": fold_ordinal,
                "heldout_block": heldout_block,
                "population_law": (
                    SELECTOR_CANDIDATE_VIEW_LAW
                ),
            },
            "lineups": _lineups_from_candidates_v1(candidates),
        }
        normalized_populations.append(population)
        fraction_results: list[dict[str, object]] = []
        for fraction_id in FRACTION_IDS:
            result = _run_selectors_v1(
                fraction_id=fraction_id,
                heldout_block=heldout_block,
                projection=projection,
                players=players,
                worlds=worlds_by_fraction[fraction_id],
            )
            fraction_results.append(result)
            normalized_books.extend({
                "coordinate": dict(book["coordinate"]),
                "coordinate_sha256": str(book["coordinate_sha256"]),
                "population_id": str(book["population_id"]),
                "selected_lineup_ids": list(book["selected_lineup_ids"]),
            } for book in result["books"])
        fold_body = {
            "schema_version": FOLD_RESULT_SCHEMA,
            "fold_ordinal": fold_ordinal,
            "heldout_block": heldout_block,
            "training_blocks": [
                block for block in WORLD_BLOCKS if block != heldout_block
            ],
            "projection_sha256": projection["projection_sha256"],
            "population_id": population_id,
            "candidate_lineup_count": len(candidates),
            "candidate_lineup_ids": [row["lineup_id"] for row in candidates],
            "candidate_lineup_ids_sha256": canonical_sha256_v1([
                row["lineup_id"] for row in candidates
            ]),
            "candidate_rows": candidates,
            "candidate_rows_sha256": canonical_sha256_v1(candidates),
            "fraction_results": fraction_results,
            "fraction_result_sha256s": [
                row["fraction_result_sha256"] for row in fraction_results
            ],
            "heldout_scores_available_to_selectors": False,
            "uses_realized_outcomes": False,
        }
        folds.append(_with_hash(fold_body, field="fold_result_sha256"))
    if len({row["coordinate_sha256"] for row in normalized_books}) != len(
        normalized_books
    ):
        _fail("L2b slate normalized book coordinates repeat")
    body = {
        "schema_version": TASK_RESULT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "adapter_id": ADAPTER_ID,
        "source_ordinal": source_ordinal,
        "slate_id": task_row["slate_id"],
        "task_manifest_identity": dict(manifest_identity),
        "task_manifest_sha256": retained_manifest["task_manifest_sha256"],
        "l2b_panel_root_identity": retained_manifest["l2b_panel_root_identity"],
        "l2b_panel_root_sha256": retained_manifest["l2b_panel_root_sha256"],
        "l2b_task_result_identity": task_row["l2b_task_result_identity"],
        "l2b_task_result_sha256": task_row["l2b_task_result_sha256"],
        "projection_bundle_identity": task_row["projection_bundle_identity"],
        "projection_bundle_sha256": task_row["projection_bundle_sha256"],
        "later_source_freeze_identity": retained_manifest[
            "later_source_freeze_identity"
        ],
        "fold_count": len(folds),
        "fold_order": list(WORLD_BLOCKS),
        "fold_results": folds,
        "fold_result_sha256s": [row["fold_result_sha256"] for row in folds],
        "fraction_registry": [dict(row) for row in l2b_panel.FRACTION_REGISTRY],
        "selector_lattice": _selector_lattice_v1(),
        "normalized_population_count": len(normalized_populations),
        "normalized_populations": normalized_populations,
        "normalized_populations_sha256": canonical_sha256_v1(
            normalized_populations
        ),
        "normalized_book_count": len(normalized_books),
        "normalized_books": normalized_books,
        "normalized_books_sha256": canonical_sha256_v1(normalized_books),
        "all_score_matrices_reduced_to_digests": True,
        "score_values_persisted": False,
        "complete": True,
        **_FALSE_POLICY,
    }
    return validate_slate_result_v1(
        _with_hash(body, field="slate_result_sha256"),
        projection_bundle=bundle,
    )


def validate_slate_result_v1(
    value: object, *, projection_bundle: object,
) -> dict[str, object]:
    result = _mapping(value, label="L2b selector slate result")
    expected_fields = {
        "schema_version", "contract_id", "adapter_id", "source_ordinal",
        "slate_id", "task_manifest_identity", "task_manifest_sha256",
        "l2b_panel_root_identity", "l2b_panel_root_sha256",
        "l2b_task_result_identity", "l2b_task_result_sha256",
        "projection_bundle_identity", "projection_bundle_sha256",
        "later_source_freeze_identity", "fold_count", "fold_order",
        "fold_results", "fold_result_sha256s", "fraction_registry",
        "selector_lattice", "normalized_population_count",
        "normalized_populations", "normalized_populations_sha256",
        "normalized_book_count", "normalized_books",
        "normalized_books_sha256", "all_score_matrices_reduced_to_digests",
        "score_values_persisted", "complete", *_FALSE_POLICY,
        "slate_result_sha256",
    }
    if set(result) != expected_fields:
        _fail("L2b selector slate-result fields differ")
    _validate_self_hash(
        result, field="slate_result_sha256", label="L2b selector slate result"
    )
    try:
        bundle = projection_contract.validate_projection_bundle_v1(
            projection_bundle
        )
    except Exception as exc:
        raise CorpusR6L2BSelectorAdapterV1Error(
            "L2b selector result projection validation failed"
        ) from exc
    folds = [
        _mapping(row, label=f"L2b selector fold[{index}]")
        for index, row in enumerate(
            _sequence(result.get("fold_results"), label="selector folds")
        )
    ]
    if (
        result.get("schema_version") != TASK_RESULT_SCHEMA
        or result.get("contract_id") != CONTRACT_ID
        or result.get("adapter_id") != ADAPTER_ID
        or result.get("source_ordinal") != bundle["source_ordinal"]
        or result.get("slate_id") != bundle["slate_id"]
        or result.get("projection_bundle_sha256")
        != bundle["projection_bundle_sha256"]
        or result.get("fold_count") != len(WORLD_BLOCKS)
        or len(folds) != len(WORLD_BLOCKS)
        or result.get("fold_order") != list(WORLD_BLOCKS)
        or result.get("fraction_registry")
        != [dict(row) for row in l2b_panel.FRACTION_REGISTRY]
        or _canonical_json_object_v1(
            result.get("selector_lattice"), label="result selector lattice"
        ) != _selector_lattice_v1()
        or result.get("all_score_matrices_reduced_to_digests") is not True
        or result.get("score_values_persisted") is not False
        or result.get("complete") is not True
        or any(result.get(field) is not False for field in _FALSE_POLICY)
    ):
        _fail("L2b selector slate-result fixed law differs")
    for name in (
        "task_manifest_identity", "l2b_panel_root_identity",
        "l2b_task_result_identity", "projection_bundle_identity",
        "later_source_freeze_identity",
    ):
        _identity(result.get(name), label=name)
    for name in (
        "task_manifest_sha256", "l2b_panel_root_sha256",
        "l2b_task_result_sha256", "projection_bundle_sha256",
    ):
        _digest(result.get(name), label=name)
    normalized_populations: list[dict[str, object]] = []
    normalized_books: list[dict[str, object]] = []
    for fold_ordinal, (heldout_block, fold, projection) in enumerate(
        zip(WORLD_BLOCKS, folds, bundle["fold_projections"], strict=True)
    ):
        _validate_self_hash(
            fold, field="fold_result_sha256", label="L2b selector fold"
        )
        candidates = _selector_candidate_view_v1(projection)
        candidate_ids = [str(row["lineup_id"]) for row in candidates]
        fraction_results = [
            _mapping(row, label="L2b fraction result")
            for row in _sequence(
                fold.get("fraction_results"), label="fraction results"
            )
        ]
        if (
            set(fold) != {
                "schema_version", "fold_ordinal", "heldout_block",
                "training_blocks", "projection_sha256", "population_id",
                "candidate_lineup_count", "candidate_lineup_ids",
                "candidate_lineup_ids_sha256", "candidate_rows",
                "candidate_rows_sha256", "fraction_results",
                "fraction_result_sha256s", "heldout_scores_available_to_selectors",
                "uses_realized_outcomes", "fold_result_sha256",
            }
            or fold.get("schema_version") != FOLD_RESULT_SCHEMA
            or fold.get("fold_ordinal") != fold_ordinal
            or fold.get("heldout_block") != heldout_block
            or fold.get("training_blocks")
            != [block for block in WORLD_BLOCKS if block != heldout_block]
            or fold.get("projection_sha256") != projection["projection_sha256"]
            or fold.get("population_id") != f"full-union/holdout-{heldout_block}"
            or fold.get("candidate_lineup_count") != len(candidates)
            or fold.get("candidate_lineup_ids") != candidate_ids
            or fold.get("candidate_lineup_ids_sha256")
            != canonical_sha256_v1(candidate_ids)
            or fold.get("candidate_rows") != candidates
            or fold.get("candidate_rows_sha256")
            != canonical_sha256_v1(candidates)
            or len(fraction_results) != len(FRACTION_IDS)
            or [row.get("fraction_id") for row in fraction_results]
            != list(FRACTION_IDS)
            or fold.get("fraction_result_sha256s")
            != [row.get("fraction_result_sha256") for row in fraction_results]
            or fold.get("heldout_scores_available_to_selectors") is not False
            or fold.get("uses_realized_outcomes") is not False
        ):
            _fail("L2b selector fold binding differs")
        normalized_populations.append({
            "population_id": fold["population_id"],
            "dimensions": {
                "fold_ordinal": fold_ordinal,
                "heldout_block": heldout_block,
                "population_law": (
                    SELECTOR_CANDIDATE_VIEW_LAW
                ),
            },
            "lineups": _lineups_from_candidates_v1(candidates),
        })
        for fraction_id, fraction in zip(
            FRACTION_IDS, fraction_results, strict=True
        ):
            _validate_self_hash(
                fraction,
                field="fraction_result_sha256",
                label="L2b fraction result",
            )
            books = [
                _mapping(row, label="L2b book descriptor")
                for row in _sequence(fraction.get("books"), label="L2b books")
            ]
            if (
                set(fraction) != {
                    "schema_version", "fraction_id", "heldout_block",
                    "training_blocks", "candidate_lineup_count",
                    "candidate_lineup_ids_sha256", "candidate_rows_sha256",
                    "training_score_shape", "training_score_matrix_sha256",
                    "grouped_result", "grouped_result_sha256",
                    "rank150_result", "rank150_result_sha256", "dpp_result",
                    "dpp_result_sha256", "tail_diversity_result",
                    "tail_diversity_result_sha256",
                    "selector_results_exact_pure_replayed",
                    "book_count", "books", "books_sha256",
                    "heldout_cross_score_executed", *_FALSE_POLICY,
                    "fraction_result_sha256",
                }
                or fraction.get("schema_version") != FRACTION_RESULT_SCHEMA
                or fraction.get("fraction_id") != fraction_id
                or fraction.get("heldout_block") != heldout_block
                or fraction.get("training_blocks")
                != [block for block in WORLD_BLOCKS if block != heldout_block]
                or fraction.get("candidate_lineup_count") != len(candidates)
                or fraction.get("candidate_lineup_ids_sha256")
                != canonical_sha256_v1(candidate_ids)
                or fraction.get("candidate_rows_sha256")
                != canonical_sha256_v1(candidates)
                or fraction.get("training_score_shape")
                != [len(candidates), 4 * WORLDS_PER_BLOCK]
                or _SHA64.fullmatch(str(
                    fraction.get("training_score_matrix_sha256", "")
                )) is None
                or fraction.get("book_count") != BOOK_COUNT_PER_FRACTION_FOLD
                or len(books) != BOOK_COUNT_PER_FRACTION_FOLD
                or fraction.get("books_sha256") != canonical_sha256_v1(books)
                or fraction.get("heldout_cross_score_executed") is not False
                or fraction.get("selector_results_exact_pure_replayed") is not True
                or any(fraction.get(field) is not False for field in _FALSE_POLICY)
            ):
                _fail("L2b selector fraction-result law differs")
            _validate_persisted_selector_shapes_v1(
                grouped=fraction["grouped_result"],
                ranked=fraction["rank150_result"],
                dpp=fraction["dpp_result"],
                challengers=fraction["tail_diversity_result"],
                candidate_rows=candidates,
            )
            if (
                fraction["grouped_result_sha256"]
                != fraction["grouped_result"]["result_sha256"]
                or fraction["rank150_result_sha256"]
                != fraction["rank150_result"]["result_sha256"]
                or fraction["dpp_result_sha256"]
                != fraction["dpp_result"]["result_sha256"]
                or fraction["tail_diversity_result_sha256"]
                != fraction["tail_diversity_result"]["result_sha256"]
            ):
                _fail("L2b nested selector hash binding differs")
            expected_books = _book_descriptors_v1(
                fraction_id=fraction_id,
                heldout_block=heldout_block,
                population_id=str(fold["population_id"]),
                candidate_rows=candidates,
                grouped=fraction["grouped_result"],
                ranked=fraction["rank150_result"],
                dpp=fraction["dpp_result"],
                challengers=fraction["tail_diversity_result"],
            )
            if books != expected_books:
                _fail("L2b persisted books differ from exact selector prefixes")
            selector_prefix_pairs = {
                (source_sha, prefix["prefix_sha256"])
                for _family, _ordinal, _selector_id, source_sha, prefixes, _budgets
                in _selector_sources_v1(
                    grouped=fraction["grouped_result"],
                    ranked=fraction["rank150_result"],
                    dpp=fraction["dpp_result"],
                    challengers=fraction["tail_diversity_result"],
                )
                for prefix in prefixes
            }
            for book in books:
                _validate_self_hash(
                    book,
                    field="book_descriptor_sha256",
                    label="L2b book descriptor",
                )
                selected = [str(value) for value in book["selected_lineup_ids"]]
                coordinate = _mapping(book["coordinate"], label="book coordinate")
                if (
                    set(book) != {
                        "coordinate", "coordinate_sha256", "population_id",
                        "selected_lineup_ids", "selected_lineup_ids_sha256",
                        "source_selector_result_sha256", "source_prefix_sha256",
                        "book_descriptor_sha256",
                    }
                    or set(coordinate) != {
                        "adapter_id", "metric_kind", "fraction_id",
                        "heldout_block", "selector_family", "selector_ordinal",
                        "selector_id", "entry_budget",
                    }
                    or coordinate.get("adapter_id") != ADAPTER_ID
                    or coordinate.get("fraction_id") != fraction_id
                    or coordinate.get("heldout_block") != heldout_block
                    or book.get("coordinate_sha256")
                    != canonical_sha256_v1(coordinate)
                    or book.get("population_id") != fold["population_id"]
                    or book.get("selected_lineup_ids_sha256")
                    != canonical_sha256_v1(selected)
                    or (
                        book.get("source_selector_result_sha256"),
                        book.get("source_prefix_sha256"),
                    ) not in selector_prefix_pairs
                    or len(selected) != coordinate.get("entry_budget")
                    or len(set(selected)) != len(selected)
                    or not set(selected) <= set(candidate_ids)
                    or len({
                        tuple(row["roster_player_ids"])
                        for row in candidates if row["lineup_id"] in set(selected)
                    }) != len(selected)
                ):
                    _fail("L2b normalized book descriptor differs")
                normalized_books.append({
                    "coordinate": coordinate,
                    "coordinate_sha256": book["coordinate_sha256"],
                    "population_id": book["population_id"],
                    "selected_lineup_ids": selected,
                })
    if (
        result.get("fold_result_sha256s")
        != [fold["fold_result_sha256"] for fold in folds]
        or result.get("normalized_population_count") != len(normalized_populations)
        or result.get("normalized_populations") != normalized_populations
        or result.get("normalized_populations_sha256")
        != canonical_sha256_v1(normalized_populations)
        or result.get("normalized_book_count") != len(normalized_books)
        or result.get("normalized_books") != normalized_books
        or result.get("normalized_books_sha256")
        != canonical_sha256_v1(normalized_books)
        or len({row["coordinate_sha256"] for row in normalized_books})
        != len(normalized_books)
    ):
        _fail("L2b normalized generic-grader surface differs")
    return result


def execute_selector_task_v1(
    *,
    manifest_identity: object,
    task_index: int,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> L2BSelectorTaskExecutionV1:
    """Execute one score-free L2b selector task and publish it create-once."""
    manifest, retained_manifest_identity = _open_selector_manifest_v1(
        manifest_identity=manifest_identity, read_exact=read_exact
    )
    if (
        type(task_index) is not int
        or not 0 <= task_index < int(manifest["execution_task_count"])
    ):
        _fail("L2b selector task index differs from execution scope")
    panel_root, panel_root_identity, panel_manifest, panel_manifest_identity = (
        _open_panel_root_v1(
            panel_root_identity=manifest["l2b_panel_root_identity"],
            read_exact=read_exact,
        )
    )
    if (
        panel_root_identity != manifest["l2b_panel_root_identity"]
        or panel_root["panel_root_sha256"] != manifest["l2b_panel_root_sha256"]
        or panel_manifest_identity != manifest["l2b_task_manifest_identity"]
        or panel_manifest["task_manifest_sha256"]
        != manifest["l2b_task_manifest_sha256"]
    ):
        _fail("L2b terminal finalization panel authority differs")
    task_row = manifest["task_rows"][task_index]
    root, root_identity, l2b_manifest, l2b_manifest_identity = _open_panel_root_v1(
        panel_root_identity=manifest["l2b_panel_root_identity"],
        read_exact=read_exact,
    )
    if (
        root_identity != manifest["l2b_panel_root_identity"]
        or root["panel_root_sha256"] != manifest["l2b_panel_root_sha256"]
        or l2b_manifest_identity != manifest["l2b_task_manifest_identity"]
        or l2b_manifest["task_manifest_sha256"]
        != manifest["l2b_task_manifest_sha256"]
    ):
        _fail("L2b selector manifest/panel binding differs")
    projection, projection_identity = _open_projection_bundle_v1(
        task_row["projection_bundle_identity"],
        read_exact=read_exact,
        label=f"projection bundle[{task_index}]",
    )
    if (
        projection_identity != task_row["projection_bundle_identity"]
        or projection["projection_bundle_sha256"]
        != task_row["projection_bundle_sha256"]
    ):
        _fail("L2b selector task projection binding differs")
    worlds = _open_l2b_task_worlds_v1(
        source_ordinal=task_index,
        task_result_identity=task_row["l2b_task_result_identity"],
        root=root,
        l2b_manifest=l2b_manifest,
        l2b_manifest_identity=l2b_manifest_identity,
        read_exact=read_exact,
    )
    source, source_identity = _exact_read_json(
        manifest["later_source_freeze_identity"],
        read_exact=read_exact,
        label="later-source freeze",
        maximum_bytes=MAXIMUM_LATER_SOURCE_BYTES,
    )
    if source_identity != manifest["later_source_freeze_identity"]:
        _fail("L2b selector later-source identity differs")
    players = _scoring_players_v1(source=source, source_ordinal=task_index)
    result = build_slate_result_v1(
        source_ordinal=task_index,
        manifest=manifest,
        manifest_identity=retained_manifest_identity,
        projection_bundle=projection,
        players=players,
        worlds_by_fraction=worlds,
    )
    result_identity = _publish_json(
        uri=str(task_row["result_uri"]),
        value=result,
        maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label=f"L2b selector result[{task_index}]",
    )
    return L2BSelectorTaskExecutionV1(result=result, result_identity=result_identity)


def _normalized_slate_v1(result: Mapping[str, object]) -> dict[str, object]:
    return {
        "source_ordinal": int(result["source_ordinal"]),
        "slate_id": str(result["slate_id"]),
        "populations": [dict(row) for row in result["normalized_populations"]],
        "books": [dict(row) for row in result["normalized_books"]],
        "later_source_identity": dict(result["later_source_freeze_identity"]),
    }


def _exact_replay_persisted_slate_v1(
    *, persisted: Mapping[str, object], source_ordinal: int,
    manifest: Mapping[str, object], manifest_identity: Mapping[str, object],
    projection: Mapping[str, object], players: Sequence[evaluator.ScoringPlayerV1],
    worlds_by_fraction: Mapping[str, Mapping[str, evaluator.ScoringWorldBlockV1]],
) -> None:
    """Recompute every selector and require exact persisted canonical equality."""
    expected = build_slate_result_v1(
        source_ordinal=source_ordinal, manifest=manifest,
        manifest_identity=manifest_identity, projection_bundle=projection,
        players=players, worlds_by_fraction=worlds_by_fraction,
    )
    if canonical_json_bytes_v1(persisted) != canonical_json_bytes_v1(expected):
        _fail("L2b persisted slate differs from exact selector pure replay")


def _open_and_replay_task0_result_v1(
    *,
    task0_manifest: Mapping[str, object],
    task0_manifest_identity: Mapping[str, object],
    task_result_identity: object,
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    """Exact-open and pure-replay the one real-artifact smoke result."""
    manifest = validate_selector_manifest_v1(task0_manifest)
    manifest_identity = _identity(
        task0_manifest_identity, label="task0 selector manifest"
    )
    if (
        manifest["execution_scope"] != TASK0_SCOPE
        or manifest["execution_task_count"] != 1
        or manifest_identity["uri"]
        != f"{manifest['output_prefix']}selector-task-manifest-{TASK0_SCOPE}.json"
    ):
        _fail("task0 smoke manifest scope/publication topology differs")
    task_row = manifest["task_rows"][0]
    expected_result_uri = (
        f"{manifest['output_prefix']}{TASK0_SCOPE}/selector-results/"
        f"00-{task_row['slate_id']}.json"
    )
    if task_row["result_uri"] != expected_result_uri:
        _fail("task0 smoke result publication URI differs")

    panel_root, panel_identity, panel_manifest, panel_manifest_identity = (
        _open_panel_root_v1(
            panel_root_identity=manifest["l2b_panel_root_identity"],
            read_exact=read_exact,
        )
    )
    if (
        panel_identity != manifest["l2b_panel_root_identity"]
        or panel_root["panel_root_sha256"] != manifest["l2b_panel_root_sha256"]
        or panel_manifest_identity != manifest["l2b_task_manifest_identity"]
        or panel_manifest["task_manifest_sha256"]
        != manifest["l2b_task_manifest_sha256"]
    ):
        _fail("task0 smoke panel authority differs")
    later_source, later_identity = _exact_read_json(
        manifest["later_source_freeze_identity"],
        read_exact=read_exact,
        label="task0 smoke later-source freeze",
        maximum_bytes=MAXIMUM_LATER_SOURCE_BYTES,
    )
    projection, projection_identity = _open_projection_bundle_v1(
        task_row["projection_bundle_identity"],
        read_exact=read_exact,
        label="task0 smoke projection bundle",
    )
    requested_result_identity = _identity(
        task_result_identity, label="task0 selector result"
    )
    if requested_result_identity["uri"] != expected_result_uri:
        _fail("task0 smoke result publication URI differs")
    result_body, retained_result_identity = _exact_read_json(
        requested_result_identity,
        read_exact=read_exact,
        label="task0 selector result",
        maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
    )
    result = validate_slate_result_v1(
        result_body, projection_bundle=projection
    )
    worlds = _open_l2b_task_worlds_v1(
        source_ordinal=0,
        task_result_identity=task_row["l2b_task_result_identity"],
        root=panel_root,
        l2b_manifest=panel_manifest,
        l2b_manifest_identity=panel_manifest_identity,
        read_exact=read_exact,
    )
    _exact_replay_persisted_slate_v1(
        persisted=result,
        source_ordinal=0,
        manifest=manifest,
        manifest_identity=manifest_identity,
        projection=projection,
        players=_scoring_players_v1(source=later_source, source_ordinal=0),
        worlds_by_fraction=worlds,
    )
    if (
        later_identity != manifest["later_source_freeze_identity"]
        or projection_identity != task_row["projection_bundle_identity"]
        or projection["projection_bundle_sha256"]
        != task_row["projection_bundle_sha256"]
        or retained_result_identity != requested_result_identity
        or retained_result_identity["uri"] != expected_result_uri
        or result["source_ordinal"] != 0
        or result["slate_id"] != task_row["slate_id"]
        or result["task_manifest_identity"] != manifest_identity
        or result["task_manifest_sha256"] != manifest["task_manifest_sha256"]
        or result["l2b_panel_root_identity"]
        != manifest["l2b_panel_root_identity"]
        or result["l2b_panel_root_sha256"] != manifest["l2b_panel_root_sha256"]
        or result["l2b_task_result_identity"]
        != task_row["l2b_task_result_identity"]
        or result["l2b_task_result_sha256"]
        != task_row["l2b_task_result_sha256"]
        or result["projection_bundle_identity"]
        != task_row["projection_bundle_identity"]
        or result["projection_bundle_sha256"]
        != task_row["projection_bundle_sha256"]
    ):
        _fail("task0 selector result/manifest authority differs")
    return result, retained_result_identity


def _replay_task0_smoke_authority_v1(
    *,
    smoke_receipt: object,
    smoke_receipt_identity: object,
    expected_l2b_panel_root_identity: object,
    expected_control_projection_receipt_identity: object,
    expected_terminal_build_receipt_identity: object,
    expected_source_commit_sha: str,
    expected_immutable_image_digest: str,
    expected_reused_job_uid: str,
    expected_output_prefix: str,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Prove that full54 is causally gated by this run's exact task0 smoke."""
    smoke = _validate_task0_smoke_receipt_shape_v1(smoke_receipt)
    smoke_identity = _identity(
        smoke_receipt_identity, label="task0 smoke receipt"
    )
    prefix = _output_prefix(expected_output_prefix)
    raw = canonical_json_bytes_v1(smoke)
    if (
        smoke_identity["uri"] != f"{prefix}task0-selector-smoke-receipt.json"
        or smoke_identity["sha256"] != sha256(raw).hexdigest()
        or smoke_identity["bytes"] != len(raw)
    ):
        _fail("task0 smoke receipt publication identity differs")
    task0_manifest, retained_manifest_identity = _open_selector_manifest_v1(
        manifest_identity=smoke["task0_manifest_identity"],
        read_exact=read_exact,
    )
    if (
        retained_manifest_identity != smoke["task0_manifest_identity"]
        or task0_manifest["task_manifest_sha256"]
        != smoke["task0_manifest_sha256"]
        or task0_manifest["execution_scope"] != TASK0_SCOPE
        or task0_manifest["execution_task_count"] != 1
        or task0_manifest["output_prefix"] != prefix
        or task0_manifest["l2b_panel_root_identity"]
        != _identity(
            expected_l2b_panel_root_identity, label="expected L2b panel root"
        )
        or task0_manifest["control_projection_receipt_identity"]
        != _identity(
            expected_control_projection_receipt_identity,
            label="expected control projection receipt",
        )
        or task0_manifest["terminal_build_receipt_identity"]
        != _identity(
            expected_terminal_build_receipt_identity,
            label="expected terminal build receipt",
        )
        or task0_manifest["source_commit_sha"] != expected_source_commit_sha
        or task0_manifest["immutable_image_digest"]
        != expected_immutable_image_digest
        or task0_manifest["reused_job_uid"] != expected_reused_job_uid
        or smoke["l2b_panel_root_identity"]
        != task0_manifest["l2b_panel_root_identity"]
        or smoke["control_projection_receipt_identity"]
        != task0_manifest["control_projection_receipt_identity"]
        or smoke["terminal_build_receipt_identity"]
        != task0_manifest["terminal_build_receipt_identity"]
        or smoke["source_commit_sha"] != task0_manifest["source_commit_sha"]
        or smoke["immutable_image_digest"]
        != task0_manifest["immutable_image_digest"]
        or smoke["reused_job_uid"] != task0_manifest["reused_job_uid"]
    ):
        _fail("task0 smoke/full54 manifest authority differs")
    result, result_identity = _open_and_replay_task0_result_v1(
        task0_manifest=task0_manifest,
        task0_manifest_identity=retained_manifest_identity,
        task_result_identity=smoke["task_result_identity"],
        read_exact=read_exact,
    )
    if (
        result_identity != smoke["task_result_identity"]
        or result["slate_result_sha256"] != smoke["task_result_sha256"]
    ):
        _fail("task0 smoke result identity/digest differs")
    return smoke


def finalize_terminal_root_v1(
    *,
    manifest_identity: object,
    task_result_identities: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> tuple[dict[str, object], dict[str, object]]:
    """Exact-open all 54 selector results and publish the terminal root last."""
    manifest, retained_manifest_identity = _open_selector_manifest_v1(
        manifest_identity=manifest_identity, read_exact=read_exact
    )
    if manifest["execution_scope"] != FULL54_SCOPE:
        _fail("L2b terminal root requires the full54 execution scope")
    panel_root, _, panel_manifest, panel_manifest_identity = _open_panel_root_v1(
        panel_root_identity=manifest["l2b_panel_root_identity"],
        read_exact=read_exact,
    )
    later_source, _ = _exact_read_json(
        manifest["later_source_freeze_identity"], read_exact=read_exact,
        label="L2b selector later-source freeze",
        maximum_bytes=MAXIMUM_LATER_SOURCE_BYTES,
    )
    identities = [
        _identity(value, label=f"selector task result[{index}]")
        for index, value in enumerate(task_result_identities)
    ]
    if (
        len(identities) != TASK_COUNT
        or len({canonical_json_bytes_v1(row) for row in identities}) != TASK_COUNT
    ):
        _fail("L2b terminal root requires 54 unique task results")
    descriptors: list[dict[str, object]] = []
    for index, (identity, task_row) in enumerate(
        zip(identities, manifest["task_rows"], strict=True)
    ):
        body, retained_identity = _exact_read_json(
            identity,
            read_exact=read_exact,
            label=f"selector task result[{index}]",
            maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        )
        projection, _ = _open_projection_bundle_v1(
            task_row["projection_bundle_identity"],
            read_exact=read_exact,
            label=f"projection bundle[{index}]",
        )
        result = validate_slate_result_v1(body, projection_bundle=projection)
        worlds = _open_l2b_task_worlds_v1(
            source_ordinal=index,
            task_result_identity=task_row["l2b_task_result_identity"],
            root=panel_root, l2b_manifest=panel_manifest,
            l2b_manifest_identity=panel_manifest_identity,
            read_exact=read_exact,
        )
        _exact_replay_persisted_slate_v1(
            persisted=result, source_ordinal=index, manifest=manifest,
            manifest_identity=retained_manifest_identity, projection=projection,
            players=_scoring_players_v1(
                source=later_source, source_ordinal=index
            ),
            worlds_by_fraction=worlds,
        )
        if (
            retained_identity["uri"] != task_row["result_uri"]
            or result["source_ordinal"] != index
            or result["slate_id"] != task_row["slate_id"]
            or result["task_manifest_identity"] != retained_manifest_identity
            or result["task_manifest_sha256"] != manifest["task_manifest_sha256"]
            or result["l2b_task_result_identity"]
            != task_row["l2b_task_result_identity"]
            or result["projection_bundle_identity"]
            != task_row["projection_bundle_identity"]
        ):
            _fail("L2b terminal task-result binding differs")
        descriptors.append({
            "source_ordinal": index,
            "slate_id": result["slate_id"],
            "task_result_identity": retained_identity,
            "task_result_sha256": result["slate_result_sha256"],
        })
    body = {
        "schema_version": TERMINAL_ROOT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "adapter_id": ADAPTER_ID,
        "task_manifest_identity": retained_manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "control_projection_receipt_identity": manifest[
            "control_projection_receipt_identity"
        ],
        "control_projection_receipt_sha256": manifest[
            "control_projection_receipt_sha256"
        ],
        "terminal_build_receipt_identity": manifest[
            "terminal_build_receipt_identity"
        ],
        "terminal_build_receipt_sha256": manifest[
            "terminal_build_receipt_sha256"
        ],
        "source_commit_sha": manifest["source_commit_sha"],
        "immutable_image_digest": manifest["immutable_image_digest"],
        "immutable_image_uri": manifest["immutable_image_uri"],
        "reused_job_name": manifest["reused_job_name"],
        "reused_job_uid": manifest["reused_job_uid"],
        "execution_scope": manifest["execution_scope"],
        "l2b_panel_root_identity": manifest["l2b_panel_root_identity"],
        "l2b_panel_root_sha256": manifest["l2b_panel_root_sha256"],
        "later_source_freeze_identity": manifest["later_source_freeze_identity"],
        "source_slate_count": TASK_COUNT,
        "task_results": descriptors,
        "task_results_sha256": canonical_sha256_v1(descriptors),
        "fraction_registry": [dict(row) for row in l2b_panel.FRACTION_REGISTRY],
        "selector_lattice": _selector_lattice_v1(),
        "generic_grader_adapter": {
            "adapter_id": ADAPTER_ID,
            "boundary": NORMALIZED_GRADER_BOUNDARY,
            "gradeability_validator": (
                "corpus_r6_novel_roster_realized_grader_v1."
                "validate_external_normalized_terminal_v1"
            ),
            "normalized_surface": "novel-roster-populations-and-books-v1",
            "realized_grade_schema": grader.REALIZED_GRADE_SCHEMA,
        },
        "all_task_results_exact_opened": True,
        "root_built_after_all_task_results": True,
        "terminal_before_first_outcome_read": True,
        "complete": True,
        **_FALSE_POLICY,
    }
    root = validate_terminal_root_v1(
        _with_hash(body, field="terminal_root_sha256")
    )
    identity = _publish_json(
        uri=str(manifest["terminal_root_uri"]),
        value=root,
        maximum_bytes=MAXIMUM_TERMINAL_ROOT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="L2b selector terminal root",
    )
    return root, identity


def validate_terminal_root_v1(value: object) -> dict[str, object]:
    root = _mapping(value, label="L2b selector terminal root")
    expected_fields = {
        "schema_version", "contract_id", "adapter_id",
        "task_manifest_identity", "task_manifest_sha256",
        "control_projection_receipt_identity",
        "control_projection_receipt_sha256", "terminal_build_receipt_identity",
        "terminal_build_receipt_sha256", "source_commit_sha",
        "immutable_image_digest", "immutable_image_uri", "reused_job_name",
        "reused_job_uid",
        "execution_scope",
        "l2b_panel_root_identity", "l2b_panel_root_sha256",
        "later_source_freeze_identity", "source_slate_count", "task_results",
        "task_results_sha256", "fraction_registry", "selector_lattice",
        "generic_grader_adapter", "all_task_results_exact_opened",
        "root_built_after_all_task_results", "terminal_before_first_outcome_read",
        "complete", *_FALSE_POLICY, "terminal_root_sha256",
    }
    if set(root) != expected_fields:
        _fail("L2b selector terminal-root fields differ")
    _validate_self_hash(
        root, field="terminal_root_sha256", label="L2b selector terminal root"
    )
    descriptors = [
        _mapping(row, label=f"terminal task result[{index}]")
        for index, row in enumerate(
            _sequence(root.get("task_results"), label="terminal task results")
        )
    ]
    if (
        root.get("schema_version") != TERMINAL_ROOT_SCHEMA
        or root.get("contract_id") != CONTRACT_ID
        or root.get("adapter_id") != ADAPTER_ID
        or root.get("execution_scope") != FULL54_SCOPE
        or root.get("reused_job_name") != REUSED_JOB_NAME
        or root.get("reused_job_uid") != REUSED_JOB_UID
        or _SHA40.fullmatch(str(root.get("source_commit_sha", ""))) is None
        or _IMAGE_DIGEST.fullmatch(
            str(root.get("immutable_image_digest", ""))
        ) is None
        or _IMAGE_URI.fullmatch(str(root.get("immutable_image_uri", ""))) is None
        or not str(root.get("immutable_image_uri", "")).endswith(
            "@" + str(root.get("immutable_image_digest", ""))
        )
        or root.get("source_slate_count") != TASK_COUNT
        or len(descriptors) != TASK_COUNT
        or root.get("task_results_sha256") != canonical_sha256_v1(descriptors)
        or root.get("fraction_registry")
        != [dict(row) for row in l2b_panel.FRACTION_REGISTRY]
        or _canonical_json_object_v1(
            root.get("selector_lattice"), label="terminal selector lattice"
        ) != _selector_lattice_v1()
        or root.get("generic_grader_adapter") != {
            "adapter_id": ADAPTER_ID,
            "boundary": NORMALIZED_GRADER_BOUNDARY,
            "gradeability_validator": (
                "corpus_r6_novel_roster_realized_grader_v1."
                "validate_external_normalized_terminal_v1"
            ),
            "normalized_surface": "novel-roster-populations-and-books-v1",
            "realized_grade_schema": grader.REALIZED_GRADE_SCHEMA,
        }
        or root.get("all_task_results_exact_opened") is not True
        or root.get("root_built_after_all_task_results") is not True
        or root.get("terminal_before_first_outcome_read") is not True
        or root.get("complete") is not True
        or any(root.get(field) is not False for field in _FALSE_POLICY)
    ):
        _fail("L2b selector terminal-root fixed law differs")
    for name in (
        "control_projection_receipt_identity", "terminal_build_receipt_identity",
    ):
        _identity(root.get(name), label=name)
    for name in (
        "control_projection_receipt_sha256", "terminal_build_receipt_sha256",
    ):
        _digest(root.get(name), label=name)
    for index, descriptor in enumerate(descriptors):
        season, week = l2b_panel.EXPECTED_SLATES[index]
        if (
            set(descriptor) != {
                "source_ordinal", "slate_id", "task_result_identity",
                "task_result_sha256",
            }
            or descriptor.get("source_ordinal") != index
            or descriptor.get("slate_id") != f"{season}-w{week:02d}"
        ):
            _fail("L2b terminal task-result descriptor differs")
        _identity(descriptor.get("task_result_identity"), label="task result")
        _digest(descriptor.get("task_result_sha256"), label="task-result SHA")
    return root


def reopen_generic_grader_terminal_v1(
    *, terminal_root_identity: object, read_exact: ReadExact,
) -> L2BGenericGraderTerminalV1:
    """Replay the terminal graph and expose the generic grader slate surface."""
    root_body, root_identity = _exact_read_json(
        terminal_root_identity,
        read_exact=read_exact,
        label="L2b selector terminal root",
        maximum_bytes=MAXIMUM_TERMINAL_ROOT_BYTES,
    )
    root = validate_terminal_root_v1(root_body)
    manifest, manifest_identity = _open_selector_manifest_v1(
        manifest_identity=root["task_manifest_identity"], read_exact=read_exact
    )
    if (
        root_identity["uri"] != manifest["terminal_root_uri"]
        or manifest_identity != root["task_manifest_identity"]
        or manifest["task_manifest_sha256"] != root["task_manifest_sha256"]
        or manifest["l2b_panel_root_identity"] != root["l2b_panel_root_identity"]
        or manifest["later_source_freeze_identity"]
        != root["later_source_freeze_identity"]
        or manifest["control_projection_receipt_identity"]
        != root["control_projection_receipt_identity"]
        or manifest["control_projection_receipt_sha256"]
        != root["control_projection_receipt_sha256"]
        or manifest["terminal_build_receipt_identity"]
        != root["terminal_build_receipt_identity"]
        or manifest["terminal_build_receipt_sha256"]
        != root["terminal_build_receipt_sha256"]
        or manifest["source_commit_sha"] != root["source_commit_sha"]
        or manifest["immutable_image_digest"] != root["immutable_image_digest"]
        or manifest["immutable_image_uri"] != root["immutable_image_uri"]
        or manifest["reused_job_name"] != root["reused_job_name"]
        or manifest["reused_job_uid"] != root["reused_job_uid"]
        or manifest["execution_scope"] != root["execution_scope"]
    ):
        _fail("L2b terminal root/manifest binding differs")
    panel_root, panel_root_identity, panel_manifest, panel_manifest_identity = (
        _open_panel_root_v1(
            panel_root_identity=root["l2b_panel_root_identity"],
            read_exact=read_exact,
        )
    )
    if (
        panel_root_identity != root["l2b_panel_root_identity"]
        or panel_root["panel_root_sha256"] != root["l2b_panel_root_sha256"]
        or panel_manifest_identity != manifest["l2b_task_manifest_identity"]
        or panel_manifest["task_manifest_sha256"]
        != manifest["l2b_task_manifest_sha256"]
    ):
        _fail("L2b terminal panel-root replay differs")
    later_source, _ = _exact_read_json(
        manifest["later_source_freeze_identity"], read_exact=read_exact,
        label="L2b terminal later-source freeze",
        maximum_bytes=MAXIMUM_LATER_SOURCE_BYTES,
    )
    slates: list[dict[str, object]] = []
    for index, (descriptor, task_row) in enumerate(
        zip(root["task_results"], manifest["task_rows"], strict=True)
    ):
        descriptor_identity = _identity(
            descriptor["task_result_identity"],
            label=f"L2b terminal task descriptor[{index}]",
        )
        if descriptor_identity["uri"] != task_row["result_uri"]:
            _fail("L2b terminal task-result replay differs")
        body, result_identity = _exact_read_json(
            descriptor_identity,
            read_exact=read_exact,
            label=f"L2b selector task result[{index}]",
            maximum_bytes=MAXIMUM_TASK_RESULT_BYTES,
        )
        projection, _ = _open_projection_bundle_v1(
            task_row["projection_bundle_identity"],
            read_exact=read_exact,
            label=f"projection bundle[{index}]",
        )
        result = validate_slate_result_v1(body, projection_bundle=projection)
        worlds = _open_l2b_task_worlds_v1(
            source_ordinal=index,
            task_result_identity=task_row["l2b_task_result_identity"],
            root=panel_root, l2b_manifest=panel_manifest,
            l2b_manifest_identity=panel_manifest_identity,
            read_exact=read_exact,
        )
        _exact_replay_persisted_slate_v1(
            persisted=result, source_ordinal=index, manifest=manifest,
            manifest_identity=manifest_identity, projection=projection,
            players=_scoring_players_v1(
                source=later_source, source_ordinal=index
            ),
            worlds_by_fraction=worlds,
        )
        if (
            descriptor_identity["uri"] != task_row["result_uri"]
            or result_identity != descriptor_identity
            or result_identity["uri"] != task_row["result_uri"]
            or result["slate_result_sha256"] != descriptor["task_result_sha256"]
            or result["source_ordinal"] != index
            or result["slate_id"] != task_row["slate_id"]
        ):
            _fail("L2b terminal task-result replay differs")
        slates.append(_normalized_slate_v1(result))
    gradeable_slates = grader.validate_external_normalized_terminal_v1(
        adapter_id=ADAPTER_ID, slates=slates
    )
    return L2BGenericGraderTerminalV1(
        adapter_id=ADAPTER_ID,
        task_manifest=manifest,
        task_manifest_identity=manifest_identity,
        task_manifest_sha256=str(manifest["task_manifest_sha256"]),
        task_result_descriptors=tuple(root["task_results"]),
        slates=gradeable_slates,
        later_source_identity=dict(root["later_source_freeze_identity"]),
        terminal_root=root,
        terminal_root_identity=root_identity,
    )


def grade_l2b_selector_experiment_realized_v1(
    *,
    terminal_root_identity: object,
    outcome_snapshot_identity: object,
    read_terminal_exact: ReadExact,
    read_outcome_exact: ReadExact,
) -> dict[str, object]:
    """Replay terminality first, then use the generic direct-roster grader."""
    opened = reopen_generic_grader_terminal_v1(
        terminal_root_identity=terminal_root_identity,
        read_exact=read_terminal_exact,
    )
    gradeable_slates = grader.validate_external_normalized_terminal_v1(
        adapter_id=ADAPTER_ID, slates=opened.slates
    )
    # The separately injected outcome reader is intentionally unreachable
    # until the complete root, manifest, 54 results, and 54 projections replay.
    snapshot, snapshot_identity, player_scores, slate_keys = (
        grader.open_outcome_snapshot_surface_v1(
            outcome_snapshot_identity=outcome_snapshot_identity,
            read_outcome_exact=read_outcome_exact,
        )
    )
    if snapshot.get("later_source_freeze_identity") != opened.later_source_identity:
        _fail("L2b terminal/outcome later-source identity differs")
    for source_ordinal, slate in enumerate(opened.slates):
        if slate_keys[source_ordinal][2] != slate["slate_id"]:
            _fail("L2b terminal/outcome slate identity differs")
    slate_grades = grader.score_normalized_slates_v1(
        slates=gradeable_slates, player_scores=player_scores
    )
    aggregate_cells = grader.aggregate_normalized_slate_grades_v1(slate_grades)
    body = {
        "schema_version": REALIZED_GRADE_SCHEMA,
        "adapter_id": ADAPTER_ID,
        "terminal_root_identity": opened.terminal_root_identity,
        "terminal_root_sha256": opened.terminal_root["terminal_root_sha256"],
        "task_manifest_identity": opened.task_manifest_identity,
        "task_manifest_sha256": opened.task_manifest_sha256,
        "outcome_snapshot_identity": snapshot_identity,
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "later_source_freeze_identity": opened.later_source_identity,
        "score_unit": "micro_dk",
        "micro_dk_per_point": grader.MICRO_DK_PER_POINT,
        "threshold_registry": [{
            "threshold_dk": threshold,
            "threshold_micro": threshold * grader.MICRO_DK_PER_POINT,
            "operator": ">=",
        } for threshold in grader.THRESHOLDS_DK],
        "source_slate_count": TASK_COUNT,
        "slate_grade_count": len(slate_grades),
        "slate_grades": slate_grades,
        "slate_grades_sha256": canonical_sha256_v1(slate_grades),
        "aggregate_cell_count": len(aggregate_cells),
        "aggregate_cells": aggregate_cells,
        "aggregate_cells_sha256": canonical_sha256_v1(aggregate_cells),
        "roster_sum_operation_count": sum(
            int(row["roster_sum_operation_count"]) for row in slate_grades
        ),
        "every_distinct_roster_scored_once_per_slate": True,
        "terminal_before_first_outcome_read": True,
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "decision_authority": False,
        "complete": True,
    }
    return grader._with_hash(body, field="realized_grade_sha256")


def grade_and_publish_l2b_selector_experiment_realized_v1(
    *,
    terminal_root_identity: object,
    outcome_snapshot_identity: object,
    target_uri: str,
    read_terminal_exact: ReadExact,
    read_outcome_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> tuple[dict[str, object], dict[str, object]]:
    grade = grade_l2b_selector_experiment_realized_v1(
        terminal_root_identity=terminal_root_identity,
        outcome_snapshot_identity=outcome_snapshot_identity,
        read_terminal_exact=read_terminal_exact,
        read_outcome_exact=read_outcome_exact,
    )
    identity = _publish_json(
        uri=target_uri,
        value=grade,
        maximum_bytes=MAXIMUM_REALIZED_GRADE_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_terminal_exact,
        label="L2b selector realized scorecard",
    )
    return grade, identity


__all__ = [
    "ADAPTER_ID",
    "BOOK_COUNT_PER_FRACTION_FOLD",
    "CONTRACT_ID",
    "CorpusR6L2BSelectorAdapterV1Error",
    "FRACTION_IDS",
    "L2BGenericGraderTerminalV1",
    "L2BSelectorTaskExecutionV1",
    "REALIZED_GRADE_SCHEMA",
    "SELECTOR_LATTICE",
    "TASK_COUNT",
    "TASK_MANIFEST_SCHEMA",
    "TASK_RESULT_SCHEMA",
    "TERMINAL_ROOT_SCHEMA",
    "build_slate_result_v1",
    "canonical_json_bytes_v1",
    "canonical_sha256_v1",
    "execute_selector_task_v1",
    "finalize_terminal_root_v1",
    "grade_and_publish_l2b_selector_experiment_realized_v1",
    "grade_l2b_selector_experiment_realized_v1",
    "prepare_selector_manifest_v1",
    "reopen_generic_grader_terminal_v1",
    "validate_selector_manifest_v1",
    "validate_slate_result_v1",
    "validate_terminal_root_v1",
]
