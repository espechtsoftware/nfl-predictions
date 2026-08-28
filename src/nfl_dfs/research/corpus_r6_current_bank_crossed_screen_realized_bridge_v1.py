"""Outcome-gated no-rescore bridge for the R6 current-bank finalists.

The crossed-screen terminal does not contain an all-block final-fit book.
For every confirmed ``(view_id, strategy_id)`` it contains five rotated-fold
books for each of 32 confirmation-sensitivity replicates.  This module keeps
all 160 paths.  It never chooses a path, unions books, refits a selector, or
scores a player.

The first reader capability can open only exact current-bank terminal
authorities.  Only after the root, aggregate, finalist publication, and all 54
confirmation selection/evaluation pairs validate is the second reader called
with an explicitly supplied, generation-pinned full-union attribution-release
identity.  Lineup scores are projected from that release's already-persisted
``realized_score_micro`` rows.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_realized_score_authority_adapter_v1 as score_authority,
)


BRIDGE_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-realized-bridge/v1"
)
BOOK_PATH_SCHEMA: Final = (
    "corpus-r6-current-bank-confirmation-realized-book-path/v1"
)
STRATEGY_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-confirmation-realized-strategy/v1"
)
MODE_ONE_SLATE_SMOKE: Final = "one-slate-smoke"
MODE_FULL_PANEL: Final = "full-54"
SMOKE_SOURCE_ORDINAL: Final = 0
CONFIRMATION_PATH_COUNT_PER_STRATEGY: Final = (
    contract.FOLDS_PER_SLATE * contract.SUBSAMPLE_REPLICATES
)
DISCLOSED_ALL_BLOCK_BASELINE_MEAN_MICRO: Final = 176_882_000
GT_200_MICRO: Final = 200_000_000
BOOTSTRAP_RESAMPLES: Final = 10_000
MAXIMUM_ROOT_BYTES: Final = 16_000_000
MAXIMUM_DESIGN_BYTES: Final = 4_000_000
MAXIMUM_AGGREGATE_BYTES: Final = 256_000_000
MAXIMUM_FINALIST_BYTES: Final = 16_000_000
MAXIMUM_SELECTION_BYTES: Final = contract.CONFIRMATION_SELECTION_RECEIPT_MAX_BYTES
MAXIMUM_EVALUATION_BYTES: Final = 768_000_000
MAXIMUM_ATTRIBUTION_ROOT_BYTES: Final = 4_000_000
MAXIMUM_ATTRIBUTION_SHARD_BYTES: Final = 512_000_000
MAXIMUM_REPORT_BYTES: Final = 512_000_000

ReadExact = Callable[[Mapping[str, object]], bytes]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_ROOT_FIELDS = frozenset({
    "schema_version", "contract_id", "design_publication_identity",
    "topology_sha256", "aggregate_publication_identity",
    "aggregate_mechanics_sha256", "finalist_publication_identity",
    "finalist_publication_sha256", "broad_logical_fold_selection_count",
    "broad_selector_os_process_count",
    "confirmation_logical_fold_selection_count",
    "confirmation_selector_os_process_count",
    "broad_child_execution_evidence_ledger_sha256",
    "confirmation_child_execution_evidence_ledger_sha256",
    "predecessor_count", "predecessors", "predecessors_sha256",
    "predecessor_opener_call_count", "retained_full_evaluation_body_count",
    "retained_compact_evaluation_record_count",
    "retained_compact_evaluation_state_bytes",
    "streaming_body_list_accepted", "terminal_reconstruction_law",
    "publication_order_law", "policy", "root_sha256",
})

_SELECTION_RECEIPT_FIELDS = frozenset({
    "schema_version", "contract_id", "phase", "source_ordinal", "slate_id",
    "projection_bundle_identity", "projection_bundle_sha256",
    "logical_fold_selection_count", "logical_fold_selection_ordinals",
    "selector_os_process_count", "child_execution_evidence",
    "child_execution_evidence_sha256s",
    "child_execution_evidence_set_sha256", "bootstrap_manifest_identity",
    "bootstrap_manifest_sha256", "launch_intent_identity", "fold_receipts",
    "fold_receipt_sha256s", "fold_receipts_sha256",
    "full_view_registry_sha256s", "fit_count",
    "nomination_publication_identity", "nomination_publication_sha256",
    "nomination_sha256", "broad_phase_authority_sha256", "topology_identity",
    "assembler_artifact_body_read_count", "assembler_selector_execution_count",
    "immutable_before_heldout_read", "policy", "selection_receipt_sha256",
})

_FOLD_FIELDS = frozenset({
    "schema_version", "contract_id", "source_ordinal", "fold_ordinal",
    "selector_process_ordinal", "selector_process_count", "slate_id",
    "fit_scope_id", "heldout_block", "phase", "projection_sha256",
    "training_blocks", "training_artifact_roles", "training_artifact_identities",
    "training_artifact_count", "heldout_artifact_addressable",
    "heldout_artifact_read", "full_candidate_score_row_ledger",
    "subsample_sha256", "full_view_registry_sha256", "nomination_sha256",
    "broad_phase_authority_sha256", "cell_count", "cells", "cells_sha256",
    "policy", "selection_fold_receipt_sha256",
})

_CELL_FIELDS = frozenset({
    "replicate", "view_id", "sampled_lineup_ids",
    "sampled_lineup_ids_sha256", "rank_seed_sha256", "strategy_ordinal",
    "strategy_id", "strategy_sha256", "executable_fingerprint_sha256",
    "training_score_row_ledger", "selected_lineup_ids",
    "selected_lineup_ids_sha256", "selected_rosters_sha256", "prefixes",
    "selection_trace", "selection_trace_sha256", "selection_cell_sha256",
})

_CHILD_EVIDENCE_FIELDS = frozenset({
    "schema_version", "phase", "source_ordinal", "fold_ordinal",
    "heldout_block", "process_ordinal", "logical_fold_process_count",
    "os_process_count", "ordered_process_chain",
    "ordered_process_chain_sha256", "broker_command",
    "broker_entrypoint_sha256", "matrix_command",
    "matrix_entrypoint_sha256", "broker_runtime_evidence",
    "broker_runtime_evidence_sha256", "matrix_runtime_evidence",
    "matrix_runtime_evidence_sha256", "training_artifact_read_ledger",
    "training_artifact_read_ledger_sha256", "training_artifact_read_count",
    "bootstrap_manifest_identity", "bootstrap_manifest_sha256",
    "process_budget_identity", "launch_intent_identity", "fit_count",
    "matrix_capability_sha256", "matrix_response_sha256",
    "matrix_response_bytes", "child_output_bytes",
    "child_output_byte_ceiling", "selection_fold_receipt_sha256",
    "runtime_evidence_strength", "outer_launch_authority_binding_required",
    "outer_launch_authority_identity",
    "transport_capability_reached_matrix_process",
    "heldout_identity_reached_matrix_process",
    "child_execution_evidence_sha256",
})

_RUNTIME_EVIDENCE_FIELDS = frozenset({
    "schema_version", "contract_id", "project_id", "code_commit",
    "image_digest", "job_name", "execution_id", "task_index",
    "process_ordinal", "mode", "redirect_environment_present",
    "storage_endpoint", "evidence_strength",
    "outer_launch_authority_binding_required", "pid", "parent_pid",
    "python_executable", "python_version", "entrypoint_path",
    "entrypoint_sha256", "command", "command_sha256",
    "runtime_evidence_sha256",
})


class CorpusR6CurrentBankRealizedBridgeV1Error(ValueError):
    """The terminal-first, no-rescore bridge failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankRealizedBridgeV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankRealizedBridgeV1Error(str(exc)) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _integer(
    value: object, *, label: str, minimum: int = 0, maximum: int | None = None,
) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    if maximum is not None and value > maximum:
        _fail(f"{label} exceeds {maximum}")
    return value


def _signed_integer(value: object, *, label: str) -> int:
    if type(value) is not int:
        _fail(f"{label} must be one exact integer")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankRealizedBridgeV1Error(str(exc)) from exc


def _policy(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=f"{label} policy")
    if item != contract.POLICY_CLAIMS:
        _fail(f"{label} policy differs")
    return item


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> str:
    retained = _digest(value.get(field), label=f"{label} {field}")
    if canonical_sha256_v1({key: item for key, item in value.items() if key != field}) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _open_json_v1(
    identity_value: object, *, read_exact: ReadExact, maximum_bytes: int,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} identity exceeds its role byte ceiling before read")
    if not callable(read_exact):
        _fail(f"{label} exact reader must be callable")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ from identity")
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankRealizedBridgeV1Error(str(exc)) from exc
    return _mapping(value, label=label), identity


def _descriptor_by_role(
    topology: Mapping[str, object], *, role: str,
) -> list[dict[str, object]]:
    return [
        _mapping(row, label=f"topology {role} descriptor")
        for row in _sequence(topology["objects"], label="topology objects")
        if isinstance(row, Mapping) and row.get("role") == role
    ]


def _validate_root_structure_v1(
    root: object, *, root_identity: object, design: object,
    design_identity: object,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    item = _mapping(root, label="terminal root")
    if frozenset(item) != _ROOT_FIELDS:
        _fail("terminal root fields differ")
    _self_hash(item, field="root_sha256", label="terminal root")
    _policy(item["policy"], label="terminal root")
    retained_root_identity = _identity(root_identity, label="terminal root identity")
    retained_design_identity = _identity(design_identity, label="terminal design identity")
    try:
        retained_design = contract.validate_design_authority_v1(
            design, publication_identity=retained_design_identity,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankRealizedBridgeV1Error(str(exc)) from exc
    topology = _mapping(retained_design["topology"], label="terminal topology")
    descriptors = [
        _mapping(row, label=f"topology descriptor[{index}]")
        for index, row in enumerate(_sequence(topology["objects"], label="topology objects"))
    ]
    if len(descriptors) != contract.OUTPUT_OBJECT_COUNT:
        _fail("terminal topology object count differs")
    root_descriptor = descriptors[-1]
    if (
        root_descriptor.get("role") != "root"
        or retained_root_identity["uri"] != root_descriptor.get("uri")
        or item.get("schema_version") != contract.ROOT_SCHEMA
        or item.get("contract_id") != contract.CONTRACT_ID
        or item.get("design_publication_identity") != retained_design_identity
        or item.get("topology_sha256") != topology.get("topology_sha256")
    ):
        _fail("terminal root design/topology authority differs")
    rows = [
        _mapping(row, label=f"terminal predecessor[{index}]")
        for index, row in enumerate(_sequence(item["predecessors"], label="terminal predecessors"))
    ]
    expected_descriptors = descriptors[:-1]
    if (
        len(rows) != contract.OUTPUT_OBJECT_COUNT - 1
        or item["predecessor_count"] != len(rows)
        or item["predecessor_opener_call_count"] != len(rows)
        or item["predecessors_sha256"] != canonical_sha256_v1(rows)
    ):
        _fail("terminal predecessor census/hash differs")
    for expected, row in zip(expected_descriptors, rows, strict=True):
        if frozenset(row) != {"ordinal", "role", "identity"}:
            _fail("terminal predecessor row fields differ")
        identity = _identity(row["identity"], label="terminal predecessor identity")
        if (
            row["ordinal"] != expected["ordinal"]
            or row["role"] != expected["role"]
            or identity["uri"] != expected["uri"]
            or row["identity"] != identity
        ):
            _fail("terminal predecessor order/URI differs")
    if (
        item["aggregate_publication_identity"]
        != next(row["identity"] for row in rows if row["role"] == "aggregate")
        or item["finalist_publication_identity"]
        != next(row["identity"] for row in rows if row["role"] == "confirmed-finalists")
        or item["broad_logical_fold_selection_count"]
        != contract.LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE
        or item["confirmation_logical_fold_selection_count"]
        != contract.LOGICAL_FOLD_SELECTION_COUNT_PER_PHASE
        or item["broad_selector_os_process_count"]
        != contract.SELECTOR_OS_PROCESS_COUNT_PER_PHASE
        or item["confirmation_selector_os_process_count"]
        != contract.SELECTOR_OS_PROCESS_COUNT_PER_PHASE
        or item["retained_full_evaluation_body_count"] != 0
        or item["retained_compact_evaluation_record_count"] != 108
        or _integer(
            item["retained_compact_evaluation_state_bytes"],
            label="terminal compact state bytes", minimum=2,
            maximum=contract.MAX_IDENTITY_BYTES,
        ) < 2
        or item["streaming_body_list_accepted"] is not False
        or item["terminal_reconstruction_law"]
        != "stream-exact-ordinal-reduce-evaluations-rebuild-aggregate-finalist"
        or item["publication_order_law"] != "strict-ordinal-create-once-root-last"
    ):
        _fail("terminal root completion/resource law differs")
    for field in (
        "aggregate_mechanics_sha256", "finalist_publication_sha256",
        "broad_child_execution_evidence_ledger_sha256",
        "confirmation_child_execution_evidence_ledger_sha256",
    ):
        _digest(item[field], label=f"terminal {field}")
    return item, retained_design, retained_root_identity


def _validate_full_score_row_ledger_v1(
    value: object, *, label: str,
) -> dict[str, object]:
    ledger = _mapping(value, label=label)
    expected_fields = {
        "dtype", "world_count", "row_count", "lineup_ids_sha256", "rows",
        "rows_sha256", "score_matrix_shape", "score_matrix_sha256",
    }
    if set(ledger) != expected_fields:
        _fail(f"{label} fields differ")
    rows = [
        _mapping(row, label=f"{label} row[{index}]")
        for index, row in enumerate(_sequence(ledger["rows"], label=f"{label} rows"))
    ]
    if any(set(row) != {"lineup_id", "score_row_sha256"} for row in rows):
        _fail(f"{label} row fields differ")
    if any(type(row["lineup_id"]) is not str for row in rows):
        _fail(f"{label} lineup identifiers differ")
    ids = [str(row["lineup_id"]) for row in rows]
    for row in rows:
        _digest(row["score_row_sha256"], label=f"{label} score-row SHA")
    if (
        ledger["dtype"] != "float64-le"
        or ledger["world_count"] != 4 * contract.WORLDS_PER_BLOCK
        or ledger["row_count"] != len(ids)
        or [row["lineup_id"] for row in rows] != ids
        or ids != sorted(set(ids))
        or ledger["lineup_ids_sha256"] != canonical_sha256_v1(ids)
        or ledger["rows_sha256"] != canonical_sha256_v1(rows)
        or ledger["score_matrix_shape"]
        != [len(ids), 4 * contract.WORLDS_PER_BLOCK]
    ):
        _fail(f"{label} binding differs")
    _digest(ledger["score_matrix_sha256"], label=f"{label} matrix SHA")
    return ledger


def _validate_sampled_score_row_ledger_v1(
    value: object, *, sampled_ids: Sequence[str],
    full_ledger: Mapping[str, object], label: str,
) -> dict[str, object]:
    ledger = _mapping(value, label=label)
    expected_fields = {
        "dtype", "world_count", "row_count", "lineup_ids_sha256", "rows",
        "rows_sha256", "source_full_rows_sha256",
        "source_full_score_matrix_sha256",
    }
    if set(ledger) != expected_fields:
        _fail(f"{label} fields differ")
    ids = [str(value) for value in sampled_ids]
    full_rows = [
        _mapping(row, label=f"{label} full row[{index}]")
        for index, row in enumerate(
            _sequence(full_ledger["rows"], label=f"{label} full rows")
        )
    ]
    full_by_id = {str(row["lineup_id"]): row for row in full_rows}
    if ids != sorted(set(ids)) or not set(ids) <= set(full_by_id):
        _fail(f"{label} sampled IDs differ from full ledger")
    expected_rows = [full_by_id[lineup_id] for lineup_id in ids]
    expected = {
        "dtype": "float64-le",
        "world_count": 4 * contract.WORLDS_PER_BLOCK,
        "row_count": len(ids),
        "lineup_ids_sha256": canonical_sha256_v1(ids),
        "rows": expected_rows,
        "rows_sha256": canonical_sha256_v1(expected_rows),
        "source_full_rows_sha256": full_ledger["rows_sha256"],
        "source_full_score_matrix_sha256": full_ledger["score_matrix_sha256"],
    }
    if canonical_json_bytes_v1(ledger) != canonical_json_bytes_v1(expected):
        _fail(f"{label} differs from exact full-ledger subset")
    return ledger


def _validate_cell_v1(
    value: object, *, expected_replicate: int,
    expected_strategy_by_id: Mapping[str, Mapping[str, object]],
    expected_full_score_row_ledger: Mapping[str, object],
) -> dict[str, object]:
    cell = _mapping(value, label="confirmation selection cell")
    if frozenset(cell) != _CELL_FIELDS:
        _fail("confirmation selection cell fields differ")
    _self_hash(cell, field="selection_cell_sha256", label="confirmation selection cell")
    replicate = _integer(
        cell["replicate"], label="confirmation replicate",
        maximum=contract.SUBSAMPLE_REPLICATES - 1,
    )
    if replicate != expected_replicate:
        _fail("confirmation replicate order differs")
    strategy_id = cell.get("strategy_id")
    if type(strategy_id) is not str or strategy_id not in expected_strategy_by_id:
        _fail("confirmation strategy is outside the frozen registry")
    strategy = expected_strategy_by_id[strategy_id]
    if (
        cell["strategy_ordinal"] != strategy["ordinal"]
        or cell["strategy_sha256"] != strategy["strategy_sha256"]
        or cell["executable_fingerprint_sha256"]
        != contract.strategy_executable_fingerprint_v1(strategy)
    ):
        _fail("confirmation selector identity differs")
    sampled_raw = _sequence(cell["sampled_lineup_ids"], label="sampled lineup IDs")
    selected_raw = _sequence(cell["selected_lineup_ids"], label="selected lineup IDs")
    if any(type(value) is not str for value in [*sampled_raw, *selected_raw]):
        _fail("confirmation lineup identifiers must be strings")
    sampled = list(sampled_raw)
    selected = list(selected_raw)
    if (
        not contract.ENTRY_BUDGET <= len(sampled) <= contract.MAX_EQUAL_COUNT_SAMPLE
        or sampled != sorted(set(sampled))
        or len(selected) != contract.ENTRY_BUDGET
        or len(set(selected)) != contract.ENTRY_BUDGET
        or not set(selected) <= set(sampled)
        or cell["sampled_lineup_ids_sha256"] != canonical_sha256_v1(sampled)
        or cell["selected_lineup_ids_sha256"] != canonical_sha256_v1(selected)
    ):
        _fail("confirmation selection is missing/extra/duplicate/outside sample")
    for lineup_id in [*sampled, *selected]:
        if (
            not lineup_id
            or len(lineup_id.encode("utf-8")) > contract.MAX_LINEUP_ID_UTF8_BYTES
        ):
            _fail("confirmation lineup identifier differs")
    _digest(cell["rank_seed_sha256"], label="confirmation rank seed")
    _digest(cell["selected_rosters_sha256"], label="confirmation selected rosters")
    sampled_ledger = _validate_sampled_score_row_ledger_v1(
        cell["training_score_row_ledger"], sampled_ids=sampled,
        full_ledger=expected_full_score_row_ledger,
        label="confirmation training score-row ledger",
    )
    prefixes = [
        _mapping(row, label=f"selection prefix[{index}]")
        for index, row in enumerate(_sequence(cell["prefixes"], label="selection prefixes"))
    ]
    if len(prefixes) != len(contract.PREFIX_SIZES):
        _fail("confirmation prefix lattice differs")
    for size, row in zip(contract.PREFIX_SIZES, prefixes, strict=True):
        if set(row) != {
            "prefix_size", "selected_lineup_ids_sha256",
            "selected_rosters_sha256", "prefix_payload_sha256",
        }:
            _fail("confirmation prefix fields differ")
        if (
            row["prefix_size"] != size
            or row["selected_lineup_ids_sha256"]
            != canonical_sha256_v1(selected[:size])
        ):
            _fail("confirmation prefix lineup binding differs")
        _digest(row["selected_rosters_sha256"], label="confirmation prefix rosters")
        _digest(row["prefix_payload_sha256"], label="confirmation prefix payload")
    if prefixes[-1]["selected_rosters_sha256"] != cell["selected_rosters_sha256"]:
        _fail("confirmation exact-80 roster binding differs")
    trace = [
        _mapping(row, label=f"selection trace[{index}]")
        for index, row in enumerate(_sequence(cell["selection_trace"], label="selection trace"))
    ]
    sampled_ordinal = {lineup_id: index for index, lineup_id in enumerate(sampled)}
    if len(trace) != contract.ENTRY_BUDGET:
        _fail("confirmation selection trace count differs")
    for index, (row, lineup_id) in enumerate(zip(trace, selected, strict=True)):
        if set(row) != {
            "selection_ordinal", "lineup_id", "sampled_lineup_ordinal",
            "score_row_sha256",
        } or (
            row["selection_ordinal"] != index
            or row["lineup_id"] != lineup_id
            or row["sampled_lineup_ordinal"] != sampled_ordinal[lineup_id]
            or row["score_row_sha256"]
            != sampled_ledger["rows"][sampled_ordinal[lineup_id]]["score_row_sha256"]
        ):
            _fail("confirmation selection trace differs")
        _digest(row["score_row_sha256"], label="confirmation trace score-row")
    if cell["selection_trace_sha256"] != canonical_sha256_v1(trace):
        _fail("confirmation selection trace hash differs")
    return cell


def _validate_child_runtime_v1(
    value: object, *, label: str, expected_mode: str,
    expected_process_ordinal: int, expected_task_index: int,
    expected_command: Sequence[object], expected_entrypoint_sha256: object,
    expected_code_commit: object, expected_image_digest: object,
) -> dict[str, object]:
    runtime = _mapping(value, label=label)
    if frozenset(runtime) != _RUNTIME_EVIDENCE_FIELDS:
        _fail(f"{label} fields differ")
    _self_hash(runtime, field="runtime_evidence_sha256", label=label)
    command = list(expected_command)
    if len(command) != 2 or any(type(token) is not str or not token for token in command):
        _fail(f"{label} expected command differs")
    entrypoint_sha = _digest(
        expected_entrypoint_sha256, label=f"{label} expected entrypoint",
    )
    if (
        runtime["schema_version"]
        != "corpus-r6-current-bank-observed-process-runtime/v1"
        or runtime["contract_id"] != contract.CONTRACT_ID
        or runtime["project_id"] != "nfl-predictions-503414"
        or runtime["code_commit"] != expected_code_commit
        or runtime["image_digest"] != expected_image_digest
        or runtime["task_index"] != expected_task_index
        or runtime["process_ordinal"] != expected_process_ordinal
        or runtime["mode"] != expected_mode
        or runtime["redirect_environment_present"] is not False
        or runtime["storage_endpoint"] != "https://storage.googleapis.com"
        or runtime["evidence_strength"]
        != "process-environment-observation-only"
        or runtime["outer_launch_authority_binding_required"] is not True
        or runtime["command"] != command
        or runtime["python_executable"] != command[0]
        or runtime["entrypoint_path"] != command[1]
        or runtime["entrypoint_sha256"] != entrypoint_sha
        or runtime["command_sha256"] != canonical_sha256_v1({
            "command": command, "entrypoint_sha256": entrypoint_sha,
        })
    ):
        _fail(f"{label} process/image/command authority differs")
    for field in ("task_index", "process_ordinal", "pid", "parent_pid"):
        _integer(runtime[field], label=f"{label} {field}")
    for field in ("job_name", "execution_id", "python_version"):
        if type(runtime[field]) is not str or not runtime[field]:
            _fail(f"{label} {field} differs")
    return runtime


def _validate_child_evidence_v1(
    value: object, *, evidence_hash: object, fold: Mapping[str, object],
    source_ordinal: int, fold_ordinal: int,
    bootstrap_manifest: Mapping[str, object], bootstrap_identity: object,
    launch_identity: object, expected_process_chain: Sequence[object],
) -> dict[str, object]:
    evidence = _mapping(value, label="confirmation child execution evidence")
    if frozenset(evidence) != _CHILD_EVIDENCE_FIELDS:
        _fail("confirmation child execution evidence fields differ")
    retained_hash = _self_hash(
        evidence, field="child_execution_evidence_sha256",
        label="confirmation child execution evidence",
    )
    if retained_hash != evidence_hash:
        _fail("confirmation child execution evidence hash differs")
    process_ordinal = source_ordinal * contract.FOLDS_PER_SLATE + fold_ordinal
    chain = [
        _mapping(row, label=f"confirmation process chain[{index}]")
        for index, row in enumerate(expected_process_chain)
    ]
    if len(chain) != 2:
        _fail("confirmation selector process chain differs")
    broker = _validate_child_runtime_v1(
        evidence["broker_runtime_evidence"], label="confirmation broker runtime",
        expected_mode="fold-broker", expected_process_ordinal=process_ordinal,
        expected_task_index=source_ordinal, expected_command=chain[0]["command"],
        expected_entrypoint_sha256=chain[0]["entrypoint_sha256"],
        expected_code_commit=bootstrap_manifest["code_commit"],
        expected_image_digest=bootstrap_manifest["image_digest"],
    )
    matrix = _validate_child_runtime_v1(
        evidence["matrix_runtime_evidence"], label="confirmation matrix runtime",
        expected_mode="matrix-selector", expected_process_ordinal=process_ordinal,
        expected_task_index=source_ordinal, expected_command=chain[1]["command"],
        expected_entrypoint_sha256=chain[1]["entrypoint_sha256"],
        expected_code_commit=bootstrap_manifest["code_commit"],
        expected_image_digest=bootstrap_manifest["image_digest"],
    )
    reads = [
        _mapping(row, label=f"confirmation training read[{index}]")
        for index, row in enumerate(_sequence(
            evidence["training_artifact_read_ledger"],
            label="confirmation training read ledger",
        ))
    ]
    expected_read_roles = [
        f"training-world-{block}" for block in contract.WORLD_BLOCKS
        if block != contract.WORLD_BLOCKS[fold_ordinal]
    ]
    if any(frozenset(row) != {"ordinal", "channel", "role", "identity"} for row in reads):
        _fail("confirmation training read fields differ")
    normalized_read_identities = [
        _identity(row["identity"], label="confirmation child training identity")
        for row in reads
    ]
    child_bytes = _integer(
        evidence["child_output_bytes"], label="confirmation child output bytes",
        minimum=1,
    )
    child_ceiling = _integer(
        evidence["child_output_byte_ceiling"],
        label="confirmation child output ceiling", minimum=1,
    )
    response_bytes = _integer(
        evidence["matrix_response_bytes"],
        label="confirmation matrix response bytes", minimum=1,
    )
    if (
        evidence["schema_version"]
        != "corpus-r6-current-bank-child-execution-evidence/v1"
        or evidence["phase"] != contract.CONFIRMATION_PHASE
        or evidence["source_ordinal"] != source_ordinal
        or evidence["fold_ordinal"] != fold_ordinal
        or evidence["heldout_block"] != contract.WORLD_BLOCKS[fold_ordinal]
        or evidence["process_ordinal"] != process_ordinal
        or evidence["logical_fold_process_count"] != 1
        or evidence["os_process_count"] != 2
        or evidence["ordered_process_chain"] != chain
        or evidence["ordered_process_chain_sha256"] != canonical_sha256_v1(chain)
        or evidence["broker_command"] != chain[0]["command"]
        or evidence["broker_entrypoint_sha256"] != chain[0]["entrypoint_sha256"]
        or evidence["matrix_command"] != chain[1]["command"]
        or evidence["matrix_entrypoint_sha256"] != chain[1]["entrypoint_sha256"]
        or evidence["broker_runtime_evidence_sha256"]
        != broker["runtime_evidence_sha256"]
        or evidence["matrix_runtime_evidence_sha256"]
        != matrix["runtime_evidence_sha256"]
        or broker["execution_id"] != matrix["execution_id"]
        or [row["ordinal"] for row in reads] != list(range(4))
        or any(row["channel"] != "process-budget" for row in reads)
        or [row["role"] for row in reads] != expected_read_roles
        or normalized_read_identities != fold["training_artifact_identities"]
        or evidence["training_artifact_read_count"] != 4
        or evidence["training_artifact_read_ledger_sha256"]
        != canonical_sha256_v1(reads)
        or evidence["bootstrap_manifest_identity"] != bootstrap_identity
        or evidence["bootstrap_manifest_sha256"]
        != bootstrap_manifest["bootstrap_manifest_sha256"]
        or evidence["launch_intent_identity"] != launch_identity
        or evidence["outer_launch_authority_identity"] != launch_identity
        or evidence["fit_count"] != fold["cell_count"]
        or child_bytes > child_ceiling
        or response_bytes > child_ceiling
        or evidence["selection_fold_receipt_sha256"]
        != fold["selection_fold_receipt_sha256"]
        or evidence["runtime_evidence_strength"]
        != "process-environment-observation-only"
        or evidence["outer_launch_authority_binding_required"] is not True
        or evidence["transport_capability_reached_matrix_process"] is not False
        or evidence["heldout_identity_reached_matrix_process"] is not False
    ):
        _fail("confirmation child execution authority differs")
    _identity(evidence["process_budget_identity"], label="confirmation child budget")
    _digest(evidence["matrix_capability_sha256"], label="confirmation matrix capability")
    _digest(evidence["matrix_response_sha256"], label="confirmation matrix response")
    return evidence


def _validate_selection_receipt_v1(
    value: object, *, identity: object, source_ordinal: int,
    expected_uri: str, expected_projection_identity: object,
    expected_topology_identity: object,
    expected_bootstrap_manifest: Mapping[str, object],
    expected_bootstrap_identity: object, expected_launch_identity: object,
) -> tuple[dict[str, object], list[list[dict[str, object]]]]:
    receipt = _mapping(value, label="confirmation selection receipt")
    if frozenset(receipt) != _SELECTION_RECEIPT_FIELDS:
        _fail("confirmation selection receipt fields differ")
    _self_hash(receipt, field="selection_receipt_sha256", label="confirmation selection receipt")
    _policy(receipt["policy"], label="confirmation selection receipt")
    retained_identity = _identity(identity, label="confirmation selection receipt identity")
    bootstrap_identity = _identity(
        expected_bootstrap_identity, label="confirmation bootstrap identity",
    )
    launch_identity = _identity(
        expected_launch_identity, label="confirmation launch identity",
    )
    process_spec = contract.bootstrap_process_spec_v1(
        expected_bootstrap_manifest,
        process_role="confirmation-fold-selector",
    )
    process_chain = _sequence(
        process_spec["process_chain"], label="confirmation selector process chain",
    )
    if retained_identity["uri"] != expected_uri:
        _fail("confirmation selection receipt URI differs")
    folds = [
        _mapping(fold, label=f"confirmation fold receipt[{index}]")
        for index, fold in enumerate(_sequence(receipt["fold_receipts"], label="confirmation fold receipts"))
    ]
    if (
        receipt["schema_version"] != contract.SELECTION_RECEIPT_SCHEMA
        or receipt["contract_id"] != contract.CONTRACT_ID
        or receipt["phase"] != contract.CONFIRMATION_PHASE
        or receipt["source_ordinal"] != source_ordinal
        or receipt["projection_bundle_identity"] != expected_projection_identity
        or receipt["topology_identity"] != expected_topology_identity
        or receipt["bootstrap_manifest_identity"] != bootstrap_identity
        or receipt["bootstrap_manifest_sha256"]
        != expected_bootstrap_manifest["bootstrap_manifest_sha256"]
        or receipt["launch_intent_identity"] != launch_identity
        or receipt["logical_fold_selection_count"] != contract.FOLDS_PER_SLATE
        or receipt["logical_fold_selection_ordinals"]
        != [source_ordinal * contract.FOLDS_PER_SLATE + fold for fold in range(contract.FOLDS_PER_SLATE)]
        or receipt["selector_os_process_count"] != 2 * contract.FOLDS_PER_SLATE
        or len(folds) != contract.FOLDS_PER_SLATE
        or receipt["fold_receipts_sha256"] != canonical_sha256_v1(folds)
        or receipt["assembler_artifact_body_read_count"] != 0
        or receipt["assembler_selector_execution_count"] != 0
        or receipt["immutable_before_heldout_read"] is not True
        or receipt["nomination_publication_identity"] is None
    ):
        _fail("confirmation selection receipt authority/lattice differs")
    _identity(receipt["nomination_publication_identity"], label="confirmation nomination identity")
    for field in (
        "projection_bundle_sha256", "bootstrap_manifest_sha256",
        "nomination_publication_sha256", "nomination_sha256",
        "broad_phase_authority_sha256",
    ):
        _digest(receipt[field], label=f"confirmation receipt {field}")
    fold_hashes = [
        _digest(value, label=f"confirmation fold hash[{index}]")
        for index, value in enumerate(_sequence(receipt["fold_receipt_sha256s"], label="fold receipt hashes"))
    ]
    registry_hashes = [
        _digest(value, label=f"confirmation registry hash[{index}]")
        for index, value in enumerate(_sequence(receipt["full_view_registry_sha256s"], label="registry hashes"))
    ]
    evidence = [
        _mapping(row, label=f"confirmation child evidence[{index}]")
        for index, row in enumerate(_sequence(receipt["child_execution_evidence"], label="child evidence"))
    ]
    evidence_hashes = [
        _digest(value, label=f"confirmation child evidence hash[{index}]")
        for index, value in enumerate(_sequence(receipt["child_execution_evidence_sha256s"], label="child evidence hashes"))
    ]
    if (
        len(fold_hashes) != contract.FOLDS_PER_SLATE
        or len(registry_hashes) != contract.FOLDS_PER_SLATE
        or len(evidence) != contract.FOLDS_PER_SLATE
        or len(evidence_hashes) != contract.FOLDS_PER_SLATE
        or len(set(evidence_hashes)) != contract.FOLDS_PER_SLATE
        or receipt["child_execution_evidence_set_sha256"] != canonical_sha256_v1(evidence)
    ):
        _fail("confirmation fold/evidence ledger differs")
    strategies = contract.frozen_strategies_v1()
    strategy_by_id = {
        str(row["strategy_id"]): row for row in strategies
    }
    normalized_cells: list[list[dict[str, object]]] = []
    expected_nominee_order: list[tuple[str, str]] | None = None
    total_fit_count = 0
    for fold_ordinal, fold in enumerate(folds):
        if frozenset(fold) != _FOLD_FIELDS:
            _fail("confirmation fold receipt fields differ")
        _self_hash(fold, field="selection_fold_receipt_sha256", label="confirmation fold receipt")
        _policy(fold["policy"], label="confirmation fold receipt")
        full_ledger = _validate_full_score_row_ledger_v1(
            fold["full_candidate_score_row_ledger"],
            label="confirmation full candidate score-row ledger",
        )
        cells_raw = _sequence(fold["cells"], label="confirmation fold cells")
        cells: list[dict[str, object]] = []
        if len(cells_raw) % contract.SUBSAMPLE_REPLICATES != 0:
            _fail("confirmation fold cell count differs")
        nominee_count = len(cells_raw) // contract.SUBSAMPLE_REPLICATES
        if not contract.MINIMUM_CONFIRMATION_NOMINEES <= nominee_count <= contract.MAXIMUM_CONFIRMATION_NOMINEES:
            _fail("confirmation nominee count differs")
        for index, raw in enumerate(cells_raw):
            cells.append(_validate_cell_v1(
                raw, expected_replicate=index // nominee_count,
                expected_strategy_by_id=strategy_by_id,
                expected_full_score_row_ledger=full_ledger,
            ))
        base_keys = [
            (str(cell["view_id"]), str(cell["strategy_id"]))
            for cell in cells[:nominee_count]
        ]
        expected_keys = [
            (view_id, strategy_id)
            for _replicate in range(contract.SUBSAMPLE_REPLICATES)
            for view_id, strategy_id in base_keys
        ]
        observed_keys = [
            (str(cell["view_id"]), str(cell["strategy_id"])) for cell in cells
        ]
        if (
            len(set(base_keys)) != nominee_count
            or observed_keys != expected_keys
            or (expected_nominee_order is not None and base_keys != expected_nominee_order)
        ):
            _fail("confirmation nominee/cell order differs")
        expected_nominee_order = base_keys
        if (
            fold["schema_version"] != contract.SELECTION_FOLD_RECEIPT_SCHEMA
            or fold["contract_id"] != contract.CONTRACT_ID
            or fold["phase"] != contract.CONFIRMATION_PHASE
            or fold["source_ordinal"] != source_ordinal
            or fold["fold_ordinal"] != fold_ordinal
            or fold["selector_process_ordinal"]
            != source_ordinal * contract.FOLDS_PER_SLATE + fold_ordinal
            or fold["selector_process_count"]
            != contract.FOLD_SELECTOR_SUBPROCESS_COUNT
            or fold["slate_id"] != receipt["slate_id"]
            or fold["fit_scope_id"] != f"holdout-{contract.WORLD_BLOCKS[fold_ordinal]}"
            or fold["heldout_block"] != contract.WORLD_BLOCKS[fold_ordinal]
            or fold["training_blocks"]
            != [
                block for block in contract.WORLD_BLOCKS
                if block != contract.WORLD_BLOCKS[fold_ordinal]
            ]
            or fold["training_artifact_roles"]
            != [
                f"world_artifact_{block.lower()}"
                for block in contract.WORLD_BLOCKS
                if block != contract.WORLD_BLOCKS[fold_ordinal]
            ]
            or fold["training_artifact_count"] != 4
            or len(_sequence(
                fold["training_artifact_identities"],
                label="confirmation training artifact identities",
            )) != 4
            or fold["heldout_artifact_addressable"] is not False
            or fold["heldout_artifact_read"] is not False
            or fold["cell_count"] != len(cells)
            or fold["cells_sha256"] != canonical_sha256_v1(cells)
            or fold["selection_fold_receipt_sha256"] != fold_hashes[fold_ordinal]
            or fold["full_view_registry_sha256"] != registry_hashes[fold_ordinal]
            or fold["nomination_sha256"] != receipt["nomination_sha256"]
            or fold["broad_phase_authority_sha256"]
            != receipt["broad_phase_authority_sha256"]
        ):
            _fail("confirmation fold receipt authority differs")
        for identity_value in _sequence(
            fold["training_artifact_identities"],
            label="confirmation training artifact identities",
        ):
            _identity(identity_value, label="confirmation training artifact identity")
        _digest(fold["projection_sha256"], label="confirmation fold projection")
        _digest(fold["subsample_sha256"], label="confirmation fold subsample")
        _validate_child_evidence_v1(
            evidence[fold_ordinal], evidence_hash=evidence_hashes[fold_ordinal],
            fold=fold, source_ordinal=source_ordinal,
            fold_ordinal=fold_ordinal,
            bootstrap_manifest=expected_bootstrap_manifest,
            bootstrap_identity=bootstrap_identity,
            launch_identity=launch_identity,
            expected_process_chain=process_chain,
        )
        normalized_cells.append(cells)
        total_fit_count += len(cells)
    if receipt["fit_count"] != total_fit_count:
        _fail("confirmation receipt fit count differs")
    return receipt, normalized_cells


def _finalist_registry_v1(finalists: object) -> list[dict[str, object]]:
    raw = _sequence(finalists, label="confirmed finalists")
    strategy_registry = {
        strategy_id: (ordinal, digest)
        for ordinal, strategy_id, digest in contract.STRATEGY_IDENTITIES
    }
    profile_registry = {
        profile_id: (ordinal, digest)
        for ordinal, profile_id, digest in contract.PROFILE_IDENTITIES
    }
    retained: list[dict[str, object]] = []
    keys: set[tuple[str, str]] = set()
    for index, value in enumerate(raw):
        row = _mapping(value, label=f"confirmed finalist[{index}]")
        view_id = row.get("view_id")
        profile_id = row.get("profile_id")
        profile_ordinal = row.get("profile_ordinal")
        strategy_id = row.get("strategy_id")
        strategy_ordinal = row.get("strategy_ordinal")
        if type(view_id) is not str or type(strategy_id) is not str:
            _fail("confirmed finalist identity differs")
        if strategy_id not in strategy_registry:
            _fail("confirmed finalist selector is outside frozen registry")
        expected_strategy_ordinal, strategy_sha = strategy_registry[strategy_id]
        strategy = contract.frozen_strategies_v1()[expected_strategy_ordinal]
        if strategy_ordinal != expected_strategy_ordinal:
            _fail("confirmed finalist selector ordinal differs")
        if view_id == "U":
            if profile_id != "all-profiles" or profile_ordinal != -1:
                _fail("confirmed union finalist profile differs")
            profile_sha: str | None = None
        else:
            if type(profile_id) is not str or profile_id not in profile_registry:
                _fail("confirmed finalist profile is outside frozen registry")
            expected_profile_ordinal, profile_sha = profile_registry[profile_id]
            if (
                profile_ordinal != expected_profile_ordinal
                or view_id != contract.isolated_view_id_v1(expected_profile_ordinal)
            ):
                _fail("confirmed finalist view/profile differs")
        key = (view_id, strategy_id)
        if key in keys:
            _fail("confirmed finalist repeats")
        keys.add(key)
        retained.append({
            "finalist_ordinal": index,
            "view_id": view_id,
            "profile_id": profile_id,
            "profile_ordinal": profile_ordinal,
            "profile_sha256": profile_sha,
            "profile_registry_sha256": contract.PROFILE_REGISTRY_SHA256,
            "strategy_id": strategy_id,
            "strategy_ordinal": strategy_ordinal,
            "strategy_sha256": strategy_sha,
            "strategy_executable_fingerprint_sha256": (
                contract.strategy_executable_fingerprint_v1(strategy)
            ),
            "strategy_registry_sha256": contract.STRATEGY_REGISTRY_SHA256,
            "prefix_size": contract.ENTRY_BUDGET,
            "roles": list(_sequence(row.get("roles"), label="finalist roles")),
            "passes_simulated_p200_noninferiority": row.get(
                "passes_simulated_p200_noninferiority"
            ),
        })
    if not contract.MINIMUM_CONFIRMATION_NOMINEES <= len(retained) <= contract.MAXIMUM_CONFIRMATION_NOMINEES:
        _fail("confirmed finalist count differs")
    return retained


def _cross_evaluation_v1(
    *, evaluation: object, evaluation_identity: object,
    selection: Mapping[str, object], selection_identity: object,
    cells_by_fold: Sequence[Sequence[Mapping[str, object]]],
    source_ordinal: int, slate_id: str, design: Mapping[str, object],
    projection_identity: object, expected_uri: str,
    finalists: Sequence[Mapping[str, object]],
) -> dict[tuple[str, str, int, int], dict[str, object]]:
    try:
        item = contract.validate_evaluation_result_v1(evaluation)
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankRealizedBridgeV1Error(str(exc)) from exc
    retained_identity = _identity(evaluation_identity, label="confirmation evaluation identity")
    retained_selection_identity = _identity(selection_identity, label="confirmation selection identity")
    if (
        retained_identity["uri"] != expected_uri
        or item["phase"] != contract.CONFIRMATION_PHASE
        or item["publication_role"] != "confirmation-evaluation-result"
        or item["source_ordinal"] != source_ordinal
        or item["slate_id"] != slate_id
        or item["design_publication_identity"] != design["_identity"]
        or item["design_sha256"] != design["design_sha256"]
        or item["topology_identity"] != design["topology_identity"]
        or item["projection_bundle_identity"] != projection_identity
        or item["projection_bundle_sha256"]
        != selection["projection_bundle_sha256"]
        or item["selection_receipt_identity"] != retained_selection_identity
        or item["selection_receipt_sha256"] != selection["selection_receipt_sha256"]
        or item["bootstrap_manifest_identity"]
        != selection["bootstrap_manifest_identity"]
        or item["bootstrap_manifest_sha256"]
        != selection["bootstrap_manifest_sha256"]
        or item["launch_intent_identity"] != selection["launch_intent_identity"]
        or item["child_execution_evidence_sha256s"]
        != selection["child_execution_evidence_sha256s"]
        or item["child_execution_evidence_set_sha256"]
        != selection["child_execution_evidence_set_sha256"]
    ):
        _fail("confirmation evaluation terminal/selection binding differs")
    finalist_keys = {
        (str(row["view_id"]), str(row["strategy_id"])) for row in finalists
    }
    extracted: dict[tuple[str, str, int, int], dict[str, object]] = {}
    folds = _sequence(item["folds"], label="confirmation evaluation folds")
    if len(folds) != contract.FOLDS_PER_SLATE:
        _fail("confirmation evaluation fold count differs")
    for fold_ordinal, (fold_value, cell_values) in enumerate(
        zip(folds, cells_by_fold, strict=True)
    ):
        fold = _mapping(fold_value, label="confirmation evaluation fold")
        cells = [dict(cell) for cell in cell_values]
        if fold["selection_fold_receipt_sha256"] != selection["fold_receipt_sha256s"][fold_ordinal]:
            _fail("confirmation evaluation fold receipt binding differs")
        book_rows = [
            _mapping(row, label=f"confirmation book metric[{index}]")
            for index, row in enumerate(_sequence(fold["book_metric_rows"], label="confirmation book metrics"))
        ]
        if len(book_rows) != len(cells) * len(contract.PREFIX_SIZES):
            _fail("confirmation evaluation book/cell lattice differs")
        for cell_ordinal, cell in enumerate(cells):
            prefix_rows = book_rows[
                cell_ordinal * len(contract.PREFIX_SIZES):
                (cell_ordinal + 1) * len(contract.PREFIX_SIZES)
            ]
            prefixes = _sequence(cell["prefixes"], label="confirmation cell prefixes")
            for prefix_ordinal, (metric, prefix_value) in enumerate(
                zip(prefix_rows, prefixes, strict=True)
            ):
                prefix = _mapping(prefix_value, label="confirmation prefix")
                if (
                    metric["cell_ordinal"] != cell_ordinal
                    or metric["prefix_ordinal"] != prefix_ordinal
                    or metric["prefix_size"] != prefix["prefix_size"]
                    or metric["replicate"] != cell["replicate"]
                    or metric["view_id"] != cell["view_id"]
                    or metric["strategy_id"] != cell["strategy_id"]
                    or metric["selection_cell_sha256"] != cell["selection_cell_sha256"]
                    or metric["selected_lineup_ids_sha256"]
                    != prefix["selected_lineup_ids_sha256"]
                    or metric["selected_rosters_sha256"]
                    != prefix["selected_rosters_sha256"]
                    or metric["prefix_payload_sha256"]
                    != prefix["prefix_payload_sha256"]
                ):
                    _fail("confirmation evaluation differs from frozen selection cell")
            key = (str(cell["view_id"]), str(cell["strategy_id"]))
            if key in finalist_keys:
                coordinate = (
                    key[0], key[1], fold_ordinal, int(cell["replicate"]),
                )
                if coordinate in extracted:
                    _fail("confirmed finalist book coordinate repeats")
                extracted[coordinate] = {
                    "selection_receipt_identity": retained_selection_identity,
                    "selection_receipt_sha256": selection["selection_receipt_sha256"],
                    "selection_fold_receipt_sha256": selection["fold_receipt_sha256s"][fold_ordinal],
                    "selection_cell_sha256": cell["selection_cell_sha256"],
                    "selected_lineup_ids": list(cell["selected_lineup_ids"]),
                    "selected_lineup_ids_sha256": cell["selected_lineup_ids_sha256"],
                    "evaluation_identity": retained_identity,
                    "evaluation_result_sha256": item["evaluation_result_sha256"],
                }
    expected_coordinates = {
        (str(finalist["view_id"]), str(finalist["strategy_id"]), fold, replicate)
        for finalist in finalists
        for fold in range(contract.FOLDS_PER_SLATE)
        for replicate in range(contract.SUBSAMPLE_REPLICATES)
    }
    if set(extracted) != expected_coordinates:
        _fail("confirmed finalist is outside/missing from frozen confirmation selection")
    return extracted


def reopen_terminal_confirmation_books_v1(
    *, terminal_root_identity: object, read_terminal_exact: ReadExact,
) -> dict[str, object]:
    """Validate the complete terminal-facing bridge surface, outcome-blind."""
    root_identity = _identity(terminal_root_identity, label="terminal root identity")
    expected_prefix = contract.OUTPUT_NAMESPACE
    if (
        not str(root_identity["uri"]).startswith(expected_prefix)
        or not str(root_identity["uri"]).endswith("/root.json")
    ):
        _fail("terminal root URI is outside the current-bank root namespace")
    root, root_identity = _open_json_v1(
        root_identity, read_exact=read_terminal_exact,
        maximum_bytes=MAXIMUM_ROOT_BYTES, label="terminal root",
    )
    output_prefix = str(root_identity["uri"])[:-len("root.json")]
    design_identity = _identity(
        root.get("design_publication_identity"), label="terminal design identity",
    )
    if design_identity["uri"] != f"{output_prefix}design.json":
        _fail("terminal design URI differs before design read")
    design_body, design_identity = _open_json_v1(
        design_identity, read_exact=read_terminal_exact,
        maximum_bytes=MAXIMUM_DESIGN_BYTES, label="terminal design",
    )
    root, design, root_identity = _validate_root_structure_v1(
        root, root_identity=root_identity, design=design_body,
        design_identity=design_identity,
    )
    topology = _mapping(design["topology"], label="terminal topology")
    descriptors = _sequence(topology["objects"], label="terminal topology objects")
    predecessor_by_role: dict[str, list[dict[str, object]]] = {}
    for row in _sequence(root["predecessors"], label="terminal predecessors"):
        retained = _mapping(row, label="terminal predecessor")
        predecessor_by_role.setdefault(str(retained["role"]), []).append(retained)
    aggregate_identity = _identity(
        root["aggregate_publication_identity"], label="terminal aggregate identity",
    )
    aggregate_descriptor = _descriptor_by_role(topology, role="aggregate")
    if len(aggregate_descriptor) != 1 or aggregate_identity["uri"] != aggregate_descriptor[0]["uri"]:
        _fail("terminal aggregate URI differs before aggregate read")
    aggregate_body, aggregate_identity = _open_json_v1(
        aggregate_identity, read_exact=read_terminal_exact,
        maximum_bytes=MAXIMUM_AGGREGATE_BYTES, label="terminal aggregate",
    )
    try:
        aggregate = contract.validate_aggregate_mechanics_authority_v1(
            aggregate_body, publication_identity=aggregate_identity,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankRealizedBridgeV1Error(str(exc)) from exc
    if (
        aggregate["design_publication_identity"] != design_identity
        or aggregate["design_sha256"] != design["design_sha256"]
        or aggregate["topology"] != topology
        or aggregate["aggregate_mechanics_sha256"] != root["aggregate_mechanics_sha256"]
    ):
        _fail("terminal aggregate design/root binding differs")
    finalist_identity = _identity(
        root["finalist_publication_identity"], label="terminal finalist identity",
    )
    finalist_descriptor = _descriptor_by_role(topology, role="confirmed-finalists")
    if len(finalist_descriptor) != 1 or finalist_identity["uri"] != finalist_descriptor[0]["uri"]:
        _fail("terminal finalist URI differs before finalist read")
    finalist_body, finalist_identity = _open_json_v1(
        finalist_identity, read_exact=read_terminal_exact,
        maximum_bytes=MAXIMUM_FINALIST_BYTES, label="terminal finalist publication",
    )
    try:
        finalist_publication = contract.validate_finalist_publication_authority_v1(
            finalist_body, publication_identity=finalist_identity,
            aggregate=aggregate, aggregate_publication_identity=aggregate_identity,
        )
    except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
        raise CorpusR6CurrentBankRealizedBridgeV1Error(str(exc)) from exc
    if finalist_publication["finalist_publication_sha256"] != root["finalist_publication_sha256"]:
        _fail("terminal finalist root hash differs")
    finalist_function = _mapping(
        finalist_publication["finalists"], label="terminal finalist function",
    )
    finalists = _finalist_registry_v1(finalist_function["finalists"])
    projection_rows = predecessor_by_role.get("projection", [])
    selection_rows = predecessor_by_role.get("confirmation-selection-receipt", [])
    evaluation_rows = predecessor_by_role.get("confirmation-evaluation-result", [])
    if any(len(rows) != contract.PANEL_SLATE_COUNT for rows in (
        projection_rows, selection_rows, evaluation_rows,
    )):
        _fail("terminal confirmation predecessor lattice is incomplete")
    aggregate_selection_layer = _mapping(
        aggregate["confirmation_selection_layer"], label="aggregate confirmation selection layer",
    )
    aggregate_evaluation_layer = _mapping(
        aggregate["confirmation_evaluation_layer"], label="aggregate confirmation evaluation layer",
    )
    selection_entries = _sequence(aggregate_selection_layer["entries"], label="aggregate selection entries")
    evaluation_entries = _sequence(aggregate_evaluation_layer["entries"], label="aggregate evaluation entries")
    if len(selection_entries) != contract.PANEL_SLATE_COUNT or len(evaluation_entries) != contract.PANEL_SLATE_COUNT:
        _fail("aggregate confirmation layer count differs")
    selected_books: list[dict[str, object]] = []
    slate_ids: list[str] = []
    terminal_open_count = 4  # root, design, aggregate, finalist
    design_for_cross = dict(design)
    design_for_cross["_identity"] = design_identity
    for source in range(contract.PANEL_SLATE_COUNT):
        projection_identity = _identity(
            projection_rows[source]["identity"], label=f"projection identity[{source}]",
        )
        selection_identity = _identity(
            selection_rows[source]["identity"], label=f"confirmation selection identity[{source}]",
        )
        evaluation_identity = _identity(
            evaluation_rows[source]["identity"], label=f"confirmation evaluation identity[{source}]",
        )
        selection_descriptor = _descriptor_by_role(
            topology, role="confirmation-selection-receipt",
        )[source]
        evaluation_descriptor = _descriptor_by_role(
            topology, role="confirmation-evaluation-result",
        )[source]
        if (
            selection_identity["uri"] != selection_descriptor["uri"]
            or evaluation_identity["uri"] != evaluation_descriptor["uri"]
        ):
            _fail("terminal confirmation URI differs before pair read")
        selection_body, selection_identity = _open_json_v1(
            selection_identity, read_exact=read_terminal_exact,
            maximum_bytes=MAXIMUM_SELECTION_BYTES,
            label=f"confirmation selection[{source}]",
        )
        terminal_open_count += 1
        selection, cells = _validate_selection_receipt_v1(
            selection_body, identity=selection_identity, source_ordinal=source,
            expected_uri=str(selection_descriptor["uri"]),
            expected_projection_identity=projection_identity,
            expected_topology_identity=design["topology_identity"],
            expected_bootstrap_manifest=_mapping(
                design["bootstrap_manifest"], label="terminal bootstrap manifest",
            ),
            expected_bootstrap_identity=design["bootstrap_manifest_identity"],
            expected_launch_identity=design["bootstrap_manifest"]["run_identity"],
        )
        evaluation_body, evaluation_identity = _open_json_v1(
            evaluation_identity, read_exact=read_terminal_exact,
            maximum_bytes=MAXIMUM_EVALUATION_BYTES,
            label=f"confirmation evaluation[{source}]",
        )
        terminal_open_count += 1
        slate_id = str(selection["slate_id"])
        if not slate_id or slate_id in slate_ids:
            _fail("terminal confirmation slate is missing/duplicate")
        slate_ids.append(slate_id)
        extracted = _cross_evaluation_v1(
            evaluation=evaluation_body, evaluation_identity=evaluation_identity,
            selection=selection, selection_identity=selection_identity,
            cells_by_fold=cells, source_ordinal=source, slate_id=slate_id,
            design=design_for_cross, projection_identity=projection_identity,
            expected_uri=str(evaluation_descriptor["uri"]), finalists=finalists,
        )
        selection_entry = _mapping(selection_entries[source], label="aggregate selection entry")
        evaluation_entry = _mapping(evaluation_entries[source], label="aggregate evaluation entry")
        if (
            selection_entry.get("source_ordinal") != source
            or selection_entry.get("slate_id") != slate_id
            or selection_entry.get("identity") != selection_identity
            or evaluation_entry.get("source_ordinal") != source
            or evaluation_entry.get("slate_id") != slate_id
            or evaluation_entry.get("identity") != evaluation_identity
        ):
            _fail("aggregate confirmation layer differs from exact pair")
        selected_books.append({
            "source_ordinal": source,
            "slate_id": slate_id,
            "books": extracted,
        })
    if terminal_open_count != 112:
        _fail("terminal bridge opener count differs")
    return {
        "terminal_root": root,
        "terminal_root_identity": root_identity,
        "design_identity": design_identity,
        "aggregate_identity": aggregate_identity,
        "finalist_identity": finalist_identity,
        "finalist_function_sha256": finalist_function["finalist_function_sha256"],
        "finalists": finalists,
        "slate_ids": slate_ids,
        "selected_books": selected_books,
        "terminal_exact_open_count": terminal_open_count,
        "terminal_confirmation_pair_count": contract.PANEL_SLATE_COUNT,
        "terminal_proof_complete": True,
        "outcome_capability_used": False,
    }


def _bind_attribution_root_v1(
    value: object, *, identity: object,
) -> dict[str, object]:
    try:
        root = score_authority.validate_attribution_release_score_authority_v1(value)
    except score_authority.CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error as exc:
        raise CorpusR6CurrentBankRealizedBridgeV1Error(str(exc)) from exc
    retained_identity = _identity(identity, label="attribution release identity")
    raw = canonical_json_bytes_v1(root)
    if (
        root["target_uri"] != retained_identity["uri"]
        or len(raw) != retained_identity["bytes"]
        or sha256(raw).hexdigest() != retained_identity["sha256"]
    ):
        _fail("attribution release root differs from exact identity")
    return root


def _bind_attribution_shard_v1(
    value: object, *, identity: object, descriptor: Mapping[str, object],
    source_ordinal: int, slate_id: str,
) -> dict[str, object]:
    try:
        shard = score_authority.validate_slate_score_row_authority_v1(value)
    except score_authority.CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error as exc:
        raise CorpusR6CurrentBankRealizedBridgeV1Error(str(exc)) from exc
    retained_identity = _identity(identity, label="attribution shard identity")
    raw = canonical_json_bytes_v1(shard)
    if (
        descriptor.get("source_ordinal") != source_ordinal
        or descriptor.get("slate_id") != slate_id
        or descriptor.get("slate_attribution_identity") != retained_identity
        or descriptor.get("slate_attribution_sha256")
        != shard["slate_attribution_sha256"]
        or descriptor.get("slate_freeze_identity")
        != shard.get("slate_freeze_identity")
        or descriptor.get("task_result_identity")
        != shard.get("task_result_identity")
        or descriptor.get("task_result_sha256") != shard.get("task_result_sha256")
        or descriptor.get("slate_grade_identity")
        != shard.get("slate_grade_identity")
        or descriptor.get("slate_grade_sha256") != shard.get("slate_grade_sha256")
        or descriptor.get("lineup_count") != shard.get("lineup_count")
        or descriptor.get("scope_membership_count")
        != shard.get("scope_membership_count")
        or descriptor.get("book_count") != shard.get("book_count")
        or descriptor.get("selection_count") != shard.get("selection_count")
        or shard["source_ordinal"] != source_ordinal
        or shard["slate_id"] != slate_id
        or len(raw) != retained_identity["bytes"]
        or sha256(raw).hexdigest() != retained_identity["sha256"]
    ):
        _fail("attribution shard descriptor/slate binding differs")
    return shard


def _fraction(numerator: int, denominator: int) -> dict[str, int]:
    if denominator < 1:
        _fail("fraction denominator differs")
    return {"numerator": numerator, "denominator": denominator}


def _interpolated_fraction(
    sorted_values: Sequence[int], numerator: int, denominator: int, *,
    value_denominator: int = 1,
) -> dict[str, int]:
    if not sorted_values:
        _fail("quantile requires values")
    span = len(sorted_values) - 1
    scaled = span * numerator
    lower, remainder = divmod(scaled, denominator)
    upper = min(lower + 1, span)
    result_numerator = (
        int(sorted_values[lower]) * (denominator - remainder)
        + int(sorted_values[upper]) * remainder
    )
    return _fraction(result_numerator, denominator * value_denominator)


def _bootstrap_ci_v1(
    slate_path_sums: Sequence[int], *, path_count: int, seed_material: object,
) -> dict[str, object]:
    slate_count = len(slate_path_sums)
    if slate_count != contract.PANEL_SLATE_COUNT:
        _fail("full bootstrap requires 54 slates")
    seed = canonical_json_bytes_v1(seed_material)
    rejection_limit = (1 << 256) - ((1 << 256) % slate_count)
    estimates: list[int] = []
    common_denominator = slate_count * path_count
    for replicate in range(BOOTSTRAP_RESAMPLES):
        total = 0
        for draw in range(slate_count):
            nonce = 0
            while True:
                digest = sha256(
                    seed
                    + replicate.to_bytes(4, "big")
                    + draw.to_bytes(2, "big")
                    + nonce.to_bytes(4, "big")
                ).digest()
                integer = int.from_bytes(digest, "big")
                if integer < rejection_limit:
                    total += int(slate_path_sums[integer % slate_count])
                    break
                nonce += 1
        estimates.append(total)
    estimates.sort()
    return {
        "schema_version": "corpus-r6-current-bank-slate-cluster-bootstrap-ci/v1",
        "resample_count": BOOTSTRAP_RESAMPLES,
        "cluster_count": slate_count,
        "fixed_path_count_per_cluster": path_count,
        "seed_material": seed_material,
        "seed_material_sha256": sha256(seed).hexdigest(),
        "lower_95_mean_micro": _interpolated_fraction(
            estimates, 1, 40, value_denominator=common_denominator,
        ),
        "upper_95_mean_micro": _interpolated_fraction(
            estimates, 39, 40, value_denominator=common_denominator,
        ),
        "common_denominator": common_denominator,
        "interpretation": (
            "descriptive-slate-cluster-uncertainty-with-fixed-correlated-"
            "confirmation-path-grid-not-promotion-authority"
        ),
    }


def _score_strategy_paths_v1(
    *, finalist: Mapping[str, object], terminal: Mapping[str, object],
    scored_slates: Mapping[int, Mapping[str, object]], mode: str,
    outcome_identity: Mapping[str, object], outcome_root_sha256: str,
) -> dict[str, object]:
    view_id = str(finalist["view_id"])
    strategy_id = str(finalist["strategy_id"])
    source_ordinals = (
        [SMOKE_SOURCE_ORDINAL]
        if mode == MODE_ONE_SLATE_SMOKE
        else list(range(contract.PANEL_SLATE_COUNT))
    )
    paths: list[dict[str, object]] = []
    slate_path_sums = {source: 0 for source in source_ordinals}
    gt_200_count = 0
    all_maxima: list[int] = []
    for fold in range(contract.FOLDS_PER_SLATE):
        for replicate in range(contract.SUBSAMPLE_REPLICATES):
            slate_rows: list[dict[str, object]] = []
            maxima: list[int] = []
            for source in source_ordinals:
                terminal_slate = terminal["selected_books"][source]
                coordinate = (view_id, strategy_id, fold, replicate)
                selected = terminal_slate["books"][coordinate]
                score_rows = scored_slates[source]["scores"]
                selected_ids = list(selected["selected_lineup_ids"])
                missing = [lineup_id for lineup_id in selected_ids if lineup_id not in score_rows]
                if missing:
                    _fail("frozen confirmation lineup is missing from no-rescore authority")
                scores = [int(score_rows[lineup_id]) for lineup_id in selected_ids]
                maximum = max(scores)
                maximum_ids = [
                    lineup_id for lineup_id, score in zip(selected_ids, scores, strict=True)
                    if score == maximum
                ]
                maxima.append(maximum)
                all_maxima.append(maximum)
                slate_path_sums[source] += maximum
                if maximum > GT_200_MICRO:
                    gt_200_count += 1
                slate_rows.append({
                    "source_ordinal": source,
                    "slate_id": terminal_slate["slate_id"],
                    "no_rescore_score_authority_identity": scored_slates[source]["identity"],
                    "no_rescore_score_authority_sha256": scored_slates[source][
                        "slate_attribution_sha256"
                    ],
                    "no_rescore_lineup_rows_sha256": scored_slates[source][
                        "lineup_rows_sha256"
                    ],
                    "selection_receipt_identity": selected["selection_receipt_identity"],
                    "selection_receipt_sha256": selected["selection_receipt_sha256"],
                    "selection_fold_receipt_sha256": selected["selection_fold_receipt_sha256"],
                    "selection_cell_sha256": selected["selection_cell_sha256"],
                    "confirmation_evaluation_identity": selected["evaluation_identity"],
                    "confirmation_evaluation_sha256": selected["evaluation_result_sha256"],
                    "selected_lineup_count": contract.ENTRY_BUDGET,
                    "selected_lineup_ids": selected_ids,
                    "selected_lineup_ids_sha256": selected["selected_lineup_ids_sha256"],
                    "weekly_maximum_realized_score_micro": maximum,
                    "weekly_maximum_lineup_ids": maximum_ids,
                    "weekly_maximum_lineup_ids_sha256": canonical_sha256_v1(maximum_ids),
                    "strictly_gt_200": maximum > GT_200_MICRO,
                })
            path_sum = sum(maxima)
            path = {
                "schema_version": BOOK_PATH_SCHEMA,
                "fold_ordinal": fold,
                "heldout_block": contract.WORLD_BLOCKS[fold],
                "replicate": replicate,
                "slate_count": len(slate_rows),
                "slates": slate_rows,
                "slates_sha256": canonical_sha256_v1(slate_rows),
                "weekly_maximum_sum_micro": path_sum,
                "mean_weekly_maximum_micro": _fraction(path_sum, len(maxima)),
                "strictly_gt_200_count": sum(value > GT_200_MICRO for value in maxima),
                "strictly_gt_200_rate": _fraction(
                    sum(value > GT_200_MICRO for value in maxima), len(maxima),
                ),
                "disclosed_all_block_baseline_mean_micro": (
                    DISCLOSED_ALL_BLOCK_BASELINE_MEAN_MICRO
                ),
                "mean_delta_from_disclosed_baseline_micro": _fraction(
                    path_sum - DISCLOSED_ALL_BLOCK_BASELINE_MEAN_MICRO * len(maxima),
                    len(maxima),
                ),
                "baseline_design_matches_this_path": False,
                "promotion_comparison_licensed": False,
            }
            path["book_path_sha256"] = canonical_sha256_v1(path)
            paths.append(path)
    if len(paths) != CONFIRMATION_PATH_COUNT_PER_STRATEGY:
        _fail("strategy confirmation path count differs")
    sorted_path_sums = sorted(int(path["weekly_maximum_sum_micro"]) for path in paths)
    slate_count = len(source_ordinals)
    book_count = len(paths) * slate_count
    total = sum(all_maxima)
    distribution = {
        "path_count": len(paths),
        "path_mean_minimum_micro": _fraction(sorted_path_sums[0], slate_count),
        "path_mean_q25_micro": _interpolated_fraction(
            sorted_path_sums, 1, 4, value_denominator=slate_count,
        ),
        "path_mean_median_micro": _interpolated_fraction(
            sorted_path_sums, 1, 2, value_denominator=slate_count,
        ),
        "path_mean_q75_micro": _interpolated_fraction(
            sorted_path_sums, 3, 4, value_denominator=slate_count,
        ),
        "path_mean_maximum_micro": _fraction(sorted_path_sums[-1], slate_count),
        "headline_path_selected": False,
    }
    ci = None
    if mode == MODE_FULL_PANEL:
        ci = _bootstrap_ci_v1(
            [slate_path_sums[source] for source in source_ordinals],
            path_count=len(paths),
            seed_material={
                "schema_version": "corpus-r6-current-bank-realized-bootstrap-seed/v1",
                "terminal_root_sha256": terminal["terminal_root"]["root_sha256"],
                "outcome_authority_sha256": outcome_identity["sha256"],
                "outcome_root_self_sha256": outcome_root_sha256,
                "view_id": view_id,
                "strategy_id": strategy_id,
                "path_count": len(paths),
                "slate_count": slate_count,
            },
        )
    result = {
        "schema_version": STRATEGY_RESULT_SCHEMA,
        **dict(finalist),
        "confirmation_path_count": len(paths),
        "scored_slate_count": slate_count,
        "scored_book_count": book_count,
        "book_paths": paths,
        "book_paths_sha256": canonical_sha256_v1(paths),
        "primary_mean_weekly_maximum_micro": _fraction(total, book_count),
        "primary_estimand": (
            "unweighted-mean-of-160-exact-confirmation-path-weekly-maxima-"
            "with-equal-slate-weight"
        ),
        "path_mean_distribution": distribution,
        "slate_cluster_bootstrap_95_ci": ci,
        "strictly_gt_200_book_count": gt_200_count,
        "strictly_gt_200_book_rate": _fraction(gt_200_count, book_count),
        "mean_delta_from_disclosed_all_block_baseline_micro": _fraction(
            total - DISCLOSED_ALL_BLOCK_BASELINE_MEAN_MICRO * book_count,
            book_count,
        ),
        "disclosed_all_block_baseline_mean_micro": (
            DISCLOSED_ALL_BLOCK_BASELINE_MEAN_MICRO
        ),
        "baseline_design_mismatch": (
            "disclosed-baseline-is-one-all-block-final-fit-book-per-slate-"
            "while-this-result-averages-160-rotated-fold-sensitivity-paths"
        ),
        "final_all_block_fit_book_absent": True,
        "no_path_choice_or_union_performed": True,
        "lineup_rescore_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    result["strategy_result_sha256"] = canonical_sha256_v1(result)
    return result


def build_realized_score_bridge_v1(
    *, terminal_root_identity: object, outcome_authority_identity: object,
    mode: str, read_terminal_exact: ReadExact, read_outcome_exact: ReadExact,
) -> dict[str, object]:
    """Build one smoke or complete 54-slate report without rescoring.

    ``read_outcome_exact`` is deliberately not invoked until
    :func:`reopen_terminal_confirmation_books_v1` returns a complete 54-pair
    proof.
    """
    if mode not in {MODE_ONE_SLATE_SMOKE, MODE_FULL_PANEL}:
        _fail("realized bridge mode differs")
    if not callable(read_outcome_exact):
        _fail("outcome exact reader must be callable")
    terminal = reopen_terminal_confirmation_books_v1(
        terminal_root_identity=terminal_root_identity,
        read_terminal_exact=read_terminal_exact,
    )
    if terminal.get("terminal_proof_complete") is not True:
        _fail("terminal proof is incomplete before outcome boundary")
    # This is the first point at which the outcome reader may be called.
    outcome_identity = _identity(
        outcome_authority_identity, label="explicit no-rescore outcome authority",
    )
    outcome_root_body, outcome_identity = _open_json_v1(
        outcome_identity, read_exact=read_outcome_exact,
        maximum_bytes=MAXIMUM_ATTRIBUTION_ROOT_BYTES,
        label="no-rescore attribution release root",
    )
    outcome_open_count = 1
    outcome_root = _bind_attribution_root_v1(
        outcome_root_body, identity=outcome_identity,
    )
    if (
        outcome_root["panel_freeze_identity"] != contract.PANEL_IDENTITY
        or outcome_root["panel_freeze_sha256"] != contract.PANEL_SELF_SHA256
    ):
        _fail("no-rescore outcome authority corpus differs from current-bank panel")
    descriptors = [
        _mapping(row, label=f"attribution descriptor[{index}]")
        for index, row in enumerate(
            _sequence(outcome_root["slate_attribution_objects"], label="attribution descriptors")
        )
    ]
    if (
        len(descriptors) != contract.PANEL_SLATE_COUNT
        or [row["source_ordinal"] for row in descriptors]
        != list(range(contract.PANEL_SLATE_COUNT))
        or [row["slate_id"] for row in descriptors] != terminal["slate_ids"]
    ):
        _fail("outcome authority slate lattice differs from terminal")
    source_ordinals = (
        [SMOKE_SOURCE_ORDINAL]
        if mode == MODE_ONE_SLATE_SMOKE
        else list(range(contract.PANEL_SLATE_COUNT))
    )
    scored_slates: dict[int, dict[str, object]] = {}
    for source in source_ordinals:
        descriptor = descriptors[source]
        shard_identity = _identity(
            descriptor["slate_attribution_identity"],
            label=f"attribution shard identity[{source}]",
        )
        shard_body, shard_identity = _open_json_v1(
            shard_identity, read_exact=read_outcome_exact,
            maximum_bytes=MAXIMUM_ATTRIBUTION_SHARD_BYTES,
            label=f"no-rescore attribution shard[{source}]",
        )
        outcome_open_count += 1
        shard = _bind_attribution_shard_v1(
            shard_body, identity=shard_identity, descriptor=descriptor,
            source_ordinal=source, slate_id=str(terminal["slate_ids"][source]),
        )
        if shard["panel_freeze_identity"] != contract.PANEL_IDENTITY:
            _fail("no-rescore attribution shard corpus differs")
        rows = _sequence(shard["lineup_rows"], label="attribution lineup rows")
        scores: dict[str, int] = {}
        for row_value in rows:
            row = _mapping(row_value, label="attribution lineup row")
            lineup_id = str(row["lineup_id"])
            if lineup_id in scores:
                _fail("outcome authority lineup repeats")
            scores[lineup_id] = _signed_integer(
                row["realized_score_micro"], label="realized lineup score",
            )
        scored_slates[source] = {
            "identity": shard_identity,
            "slate_attribution_sha256": shard["slate_attribution_sha256"],
            "lineup_rows_sha256": shard["lineup_rows_sha256"],
            "scores": scores,
        }
    strategy_results = [
        _score_strategy_paths_v1(
            finalist=finalist, terminal=terminal,
            scored_slates=scored_slates, mode=mode,
            outcome_identity=outcome_identity,
            outcome_root_sha256=str(outcome_root["attribution_release_sha256"]),
        )
        for finalist in terminal["finalists"]
    ]
    report = {
        "schema_version": BRIDGE_SCHEMA,
        "contract_id": contract.CONTRACT_ID,
        "mode": mode,
        "terminal_root_identity": terminal["terminal_root_identity"],
        "terminal_root_sha256": terminal["terminal_root"]["root_sha256"],
        "terminal_design_identity": terminal["design_identity"],
        "terminal_aggregate_identity": terminal["aggregate_identity"],
        "terminal_finalist_identity": terminal["finalist_identity"],
        "terminal_finalist_function_sha256": terminal["finalist_function_sha256"],
        "terminal_confirmation_pair_count": terminal["terminal_confirmation_pair_count"],
        "terminal_exact_open_count_before_outcome": terminal["terminal_exact_open_count"],
        "terminal_proof_complete_before_outcome_open": True,
        "outcome_authority_identity": outcome_identity,
        "outcome_authority_sha256": outcome_root["attribution_release_sha256"],
        "outcome_grade_completion_identity": outcome_root[
            "grade_completion_identity"
        ],
        "outcome_persisted_grade_root_identity": outcome_root[
            "persisted_grade_root_identity"
        ],
        "panel_freeze_identity": contract.PANEL_IDENTITY,
        "panel_freeze_sha256": contract.PANEL_SELF_SHA256,
        "outcome_exact_open_count": outcome_open_count,
        "outcome_source_read": False,
        "bigquery_client_constructed": False,
        "lineup_rescore_performed": False,
        "score_row_authority": (
            "persisted-full-union-attribution-lineup-realized-score-micro"
        ),
        "scored_source_ordinals": source_ordinals,
        "scored_slate_count": len(source_ordinals),
        "finalist_count": len(strategy_results),
        "confirmation_path_count_per_finalist": (
            CONFIRMATION_PATH_COUNT_PER_STRATEGY
        ),
        "strategy_results": strategy_results,
        "strategy_results_sha256": canonical_sha256_v1(strategy_results),
        "disclosed_all_block_baseline_mean_micro": (
            DISCLOSED_ALL_BLOCK_BASELINE_MEAN_MICRO
        ),
        "disclosed_baseline_design_matches": False,
        "final_all_block_fit_book_absent": True,
        "historical_retune_licensed": False,
        "promotion_authority": False,
        "decision_authority": False,
        "graph_mutation_performed": False,
    }
    report["realized_bridge_sha256"] = canonical_sha256_v1(report)
    raw = canonical_json_bytes_v1(report)
    if len(raw) > MAXIMUM_REPORT_BYTES:
        _fail("realized bridge report exceeds its byte ceiling")
    return report


__all__ = [
    "BOOTSTRAP_RESAMPLES",
    "BRIDGE_SCHEMA",
    "CONFIRMATION_PATH_COUNT_PER_STRATEGY",
    "CorpusR6CurrentBankRealizedBridgeV1Error",
    "DISCLOSED_ALL_BLOCK_BASELINE_MEAN_MICRO",
    "GT_200_MICRO",
    "MODE_FULL_PANEL",
    "MODE_ONE_SLATE_SMOKE",
    "SMOKE_SOURCE_ORDINAL",
    "build_realized_score_bridge_v1",
    "canonical_json_bytes_v1",
    "canonical_sha256_v1",
    "reopen_terminal_confirmation_books_v1",
]
