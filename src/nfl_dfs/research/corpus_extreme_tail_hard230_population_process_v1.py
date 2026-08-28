"""Create-once process seam for the native hard-230 population successor.

The seam is intentionally cloud-SDK-free: a consolidated immutable image can
inject generation-pinned reads and create-once writes.  Evidence is packed in
deterministic bounded zlib shards, an index is published after every shard,
and one root receipt is published last.  An identical retry is recoverable
only when the publisher returns and the reader reopens byte-identical objects.

This module does not discover buckets, list prefixes, resolve current
generations, decode an undocumented production artifact, launch compute or
read outcomes.  Loaded scientific inputs must already have been exact-opened
by the image entrypoint and are revalidated by the successor contract.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Final, Protocol
import zlib

import numpy as np

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_population_successor_v1 as successor,
)


PROCESS_CONTRACT_ID: Final = "20260828-hard230-population-process-v1"
PROCESS_BUDGET_SCHEMA: Final = "hard230-population-process-budget/v1"
PROCESS_REQUEST_SCHEMA: Final = "hard230-population-process-request/v1"
TASK_MANIFEST_SCHEMA: Final = "hard230-population-54-task-manifest/v1"
EVIDENCE_SHARD_SCHEMA: Final = "hard230-population-evidence-shard/v1"
EVIDENCE_INDEX_SCHEMA: Final = "hard230-population-evidence-index/v1"
PROCESS_RECEIPT_SCHEMA: Final = "hard230-population-process-receipt/v1"

EXACT_CONSOLIDATED_SLATE_COUNT: Final = 54
EVIDENCE_RECORDS_PER_SHARD: Final = 32
EVIDENCE_UNCOMPRESSED_BYTES_PER_SHARD: Final = 16_000_000
MAX_EVIDENCE_RECORD_BYTES: Final = 2_000_000
EVIDENCE_MIN_RECORDS_PER_SHARD_PRECHARGE: Final = 7
MAX_ROOT_BYTES: Final = 16_000_000
MAX_INDEX_BYTES: Final = 4_000_000
MAX_COMPRESSED_EVIDENCE_SHARD_BYTES: Final = 16_100_000

_FALSE_AUTHORITY_FIELDS: Final = (
    "uses_realized_outcomes",
    "uses_heldout_scores",
    "historical_scoring_licensed",
    "selector_authority",
    "publication_authority",
    "promotion_authority",
    "decision_authority",
    "production_change_licensed",
    "graph_mutation_licensed",
)


class Hard230PopulationProcessV1Error(ValueError):
    """An exact process budget, request or publication failed closed."""


class CreateOncePublisher(Protocol):
    def __call__(self, uri: str, payload: bytes) -> Mapping[str, object]: ...


class ExactReader(Protocol):
    def __call__(self, identity: Mapping[str, object]) -> bytes: ...


SolverCallback = Callable[[legal.SolveRequest], legal.SolveOutcome]


@dataclass(frozen=True, slots=True)
class Hard230PopulationProcessResult:
    process_receipt: Mapping[str, object]
    process_receipt_identity: Mapping[str, object]
    evidence_index: Mapping[str, object]
    evidence_index_identity: Mapping[str, object]
    scientific_result: successor.Hard230PopulationSuccessorResult


def _fail(message: str) -> None:
    raise Hard230PopulationProcessV1Error(message)


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return legal.canonical_json_bytes(value)
    except (TypeError, ValueError, legal.CorpusLegalFeasibilityError) as exc:
        raise Hard230PopulationProcessV1Error(
            f"{label} is not finite canonical JSON"
        ) from exc


def _sha(value: object, *, label: str) -> str:
    return hashlib.sha256(_canonical(value, label=label)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one array")
    return list(value)


def _nonempty(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be one nonempty exact string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _sha256(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    if field in result:
        _fail(f"{field} cannot already be present")
    result[field] = _sha(result, label=field)
    return result


def _self_hash_valid(value: object, *, field: str, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    retained = _sha256(item.pop(field, None), label=f"{label} SHA-256")
    if retained != _sha(item, label=f"{label} body"):
        _fail(f"{label} self-hash differs")
    return {**item, field: retained}


def _object_identity(
    value: object, *, label: str, payload: bytes | None = None
) -> dict[str, object]:
    try:
        return successor._object_identity(value, label=label, payload=payload)
    except successor.Hard230PopulationSuccessorV1Error as exc:
        raise Hard230PopulationProcessV1Error(str(exc)) from exc


def _bind(
    body: Mapping[str, object], identity: Mapping[str, object], *, label: str
) -> dict[str, object]:
    return _object_identity(
        identity, label=f"{label} identity", payload=_canonical(body, label=label)
    )


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _prefix(value: object) -> str:
    prefix = _nonempty(value, label="output prefix").rstrip("/")
    if not prefix.startswith("gs://") or prefix.count("/") < 3:
        _fail("output prefix must be one non-root GCS prefix")
    return prefix


def build_process_budget_v1(
    *,
    slate_id: str,
    candidate_origin_id: str,
    heldout_block: str | None,
    p0_target_authority: Mapping[str, object],
    p0_target_authority_identity: Mapping[str, object],
    world_permutation_authority: Mapping[str, object],
    world_permutation_authority_identity: Mapping[str, object],
    output_prefix: str,
    execution_mode: str = successor.RELEASE_EXECUTION_MODE,
) -> dict[str, object]:
    p0 = successor.validate_p0_target_authority_v1(p0_target_authority)
    p0_identity = successor.bind_authority_identity_v1(
        p0, p0_target_authority_identity, label="P0 target authority"
    )
    permutation = successor.validate_world_permutation_authority_v1(
        world_permutation_authority
    )
    permutation_identity = successor.bind_authority_identity_v1(
        permutation,
        world_permutation_authority_identity,
        label="world permutation authority",
    )
    mode = successor._execution_mode(execution_mode)
    common = {
        "slate_id": _nonempty(slate_id, label="slate ID"),
        "candidate_origin_id": _nonempty(
            candidate_origin_id, label="candidate origin"
        ),
        "heldout_block": heldout_block,
    }
    if any(p0.get(key) != value for key, value in common.items()) or any(
        permutation.get(key) != value for key, value in common.items()
    ):
        _fail("budget authorities do not describe the requested cell")
    target = int(p0["retained_count"])
    width = int(permutation["worlds_per_block"])
    computed = min(
        successor.MAXIMUM_SOLVER_CALL_CEILING,
        max(
            successor.MINIMUM_SOLVER_CALL_CEILING,
            successor.SOLVER_CALLS_PER_TARGET * target,
        ),
    )
    effective = min(width, computed)
    if target > effective:
        _fail("P0 target exceeds the process solver-call ceiling")
    max_records = 2 * effective
    max_shards = math.ceil(
        max_records / EVIDENCE_MIN_RECORDS_PER_SHARD_PRECHARGE
    )
    prefix = _prefix(output_prefix)
    body = {
        "schema_version": PROCESS_BUDGET_SCHEMA,
        "process_contract_id": PROCESS_CONTRACT_ID,
        "scientific_contract_id": successor.CONTRACT_ID,
        "process_role": "hard230-native-population-cell",
        "slate_id": common["slate_id"],
        "candidate_origin_id": common["candidate_origin_id"],
        "fit_scope_id": p0["fit_scope_id"],
        "heldout_block": heldout_block,
        "training_blocks": list(p0["training_blocks"]),
        "execution_mode": mode,
        "p0_target_authority_identity": p0_identity,
        "world_permutation_authority_identity": permutation_identity,
        "target_retained_count": target,
        "worlds_per_block": width,
        "maximum_player_count": successor.MAX_PLAYER_COUNT,
        "computed_solver_call_ceiling": computed,
        "effective_solver_call_ceiling": effective,
        "maximum_solver_call_count": effective,
        "maximum_evidence_record_count": max_records,
        "evidence_records_per_shard": EVIDENCE_RECORDS_PER_SHARD,
        "evidence_uncompressed_bytes_per_shard": (
            EVIDENCE_UNCOMPRESSED_BYTES_PER_SHARD
        ),
        "maximum_evidence_record_bytes": MAX_EVIDENCE_RECORD_BYTES,
        "maximum_evidence_shard_count": max_shards,
        "maximum_write_object_count": max_shards + 2,
        "maximum_compressed_evidence_shard_bytes": (
            MAX_COMPRESSED_EVIDENCE_SHARD_BYTES
        ),
        "maximum_write_bytes": (
            max_shards * MAX_COMPRESSED_EVIDENCE_SHARD_BYTES
            + MAX_INDEX_BYTES
            + MAX_ROOT_BYTES
        ),
        "score_matrix_byte_ceiling": (
            successor.MAX_PLAYER_COUNT
            * len(successor.WORLD_BLOCKS)
            * successor.PRODUCTION_WORLDS_PER_BLOCK
            * np.dtype("<i8").itemsize
        ),
        "output_prefix": prefix,
        "evidence_shard_uri_template": (
            f"{prefix}/evidence/shard-{{ordinal:04d}}.json.zlib"
        ),
        "evidence_index_uri": f"{prefix}/evidence-index.json",
        "process_receipt_uri": f"{prefix}/process-receipt.json",
        "publication_order": "evidence-shards-then-index-then-root",
        "create_once_required": True,
        "bucket_listing_allowed": False,
        "current_generation_lookup_allowed": False,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    return _self_hash(body, "process_budget_sha256")


def validate_process_budget_v1(value: object) -> dict[str, object]:
    item = _self_hash_valid(
        value, field="process_budget_sha256", label="process budget"
    )
    if (
        item.get("schema_version") != PROCESS_BUDGET_SCHEMA
        or item.get("process_contract_id") != PROCESS_CONTRACT_ID
        or item.get("scientific_contract_id") != successor.CONTRACT_ID
        or item.get("maximum_player_count") != successor.MAX_PLAYER_COUNT
        or item.get("evidence_records_per_shard")
        != EVIDENCE_RECORDS_PER_SHARD
        or item.get("evidence_uncompressed_bytes_per_shard")
        != EVIDENCE_UNCOMPRESSED_BYTES_PER_SHARD
        or item.get("maximum_evidence_record_bytes")
        != MAX_EVIDENCE_RECORD_BYTES
        or item.get("maximum_compressed_evidence_shard_bytes")
        != MAX_COMPRESSED_EVIDENCE_SHARD_BYTES
        or item.get("process_role") != "hard230-native-population-cell"
        or item.get("publication_order")
        != "evidence-shards-then-index-then-root"
        or item.get("create_once_required") is not True
        or item.get("bucket_listing_allowed") is not False
        or item.get("current_generation_lookup_allowed") is not False
        or any(item.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("process budget fixed law or false-authority boundary differs")
    target = _integer(
        item.get("target_retained_count"), label="budget target", minimum=1
    )
    width = _integer(
        item.get("worlds_per_block"), label="budget world width", minimum=1
    )
    computed = min(
        successor.MAXIMUM_SOLVER_CALL_CEILING,
        max(
            successor.MINIMUM_SOLVER_CALL_CEILING,
            successor.SOLVER_CALLS_PER_TARGET * target,
        ),
    )
    effective = min(width, computed)
    max_records = 2 * effective
    max_shards = math.ceil(
        max_records / EVIDENCE_MIN_RECORDS_PER_SHARD_PRECHARGE
    )
    prefix = _prefix(item.get("output_prefix"))
    if (
        item.get("computed_solver_call_ceiling") != computed
        or item.get("effective_solver_call_ceiling") != effective
        or item.get("maximum_solver_call_count") != effective
        or item.get("maximum_evidence_record_count") != max_records
        or item.get("maximum_evidence_shard_count") != max_shards
        or item.get("maximum_write_object_count") != max_shards + 2
        or item.get("maximum_write_bytes")
        != (
            max_shards * MAX_COMPRESSED_EVIDENCE_SHARD_BYTES
            + MAX_INDEX_BYTES
            + MAX_ROOT_BYTES
        )
        or item.get("score_matrix_byte_ceiling")
        != (
            successor.MAX_PLAYER_COUNT
            * len(successor.WORLD_BLOCKS)
            * successor.PRODUCTION_WORLDS_PER_BLOCK
            * np.dtype("<i8").itemsize
        )
        or item.get("evidence_shard_uri_template")
        != f"{prefix}/evidence/shard-{{ordinal:04d}}.json.zlib"
        or item.get("evidence_index_uri") != f"{prefix}/evidence-index.json"
        or item.get("process_receipt_uri") != f"{prefix}/process-receipt.json"
    ):
        _fail("process budget arithmetic or deterministic output plan differs")
    successor._execution_mode(item.get("execution_mode"))
    return item


def build_process_request_v1(
    *,
    task_index: int,
    process_budget: Mapping[str, object],
    process_budget_identity: Mapping[str, object],
    source_member_identity: Mapping[str, object],
    score_block_identities: Sequence[Mapping[str, object]],
    player_registry_sha256: str,
    score_matrix_identity: Mapping[str, object],
    p0_target_authority_identity: Mapping[str, object],
    world_permutation_authority_identity: Mapping[str, object],
    runtime_authority_identity: Mapping[str, object],
    require_production_width: bool = True,
) -> dict[str, object]:
    budget = validate_process_budget_v1(process_budget)
    budget_identity = _bind(
        budget, process_budget_identity, label="process budget"
    )
    if type(require_production_width) is not bool:
        _fail("require_production_width must be an exact boolean")
    blocks = [_mapping(row, label="score block identity") for row in score_block_identities]
    matrix_identity = _mapping(score_matrix_identity, label="score matrix identity")
    body = {
        "schema_version": PROCESS_REQUEST_SCHEMA,
        "process_contract_id": PROCESS_CONTRACT_ID,
        "task_index": _integer(task_index, label="task index"),
        "slate_id": budget["slate_id"],
        "candidate_origin_id": budget["candidate_origin_id"],
        "fit_scope_id": budget["fit_scope_id"],
        "heldout_block": budget["heldout_block"],
        "training_blocks": list(budget["training_blocks"]),
        "worlds_per_block": budget["worlds_per_block"],
        "execution_mode": budget["execution_mode"],
        "require_production_width": require_production_width,
        "source_member_identity": _mapping(
            source_member_identity, label="source member identity"
        ),
        "score_block_identities": blocks,
        "score_block_identities_sha256": _sha(
            blocks, label="score block identities"
        ),
        "player_registry_sha256": _sha256(
            player_registry_sha256, label="player registry SHA-256"
        ),
        "score_matrix_identity": matrix_identity,
        "score_matrix_identity_sha256": _sha(
            matrix_identity, label="score matrix identity"
        ),
        "p0_target_authority_identity": _object_identity(
            p0_target_authority_identity, label="P0 target authority"
        ),
        "world_permutation_authority_identity": _object_identity(
            world_permutation_authority_identity,
            label="world permutation authority",
        ),
        "runtime_authority_identity": _object_identity(
            runtime_authority_identity, label="runtime authority"
        ),
        "process_budget_identity": budget_identity,
        "output_prefix": budget["output_prefix"],
        "input_payload_decoder_authority_required": True,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    if (
        body["p0_target_authority_identity"]
        != budget["p0_target_authority_identity"]
        or body["world_permutation_authority_identity"]
        != budget["world_permutation_authority_identity"]
    ):
        _fail("request authority identities differ from the process budget")
    return _self_hash(body, "process_request_sha256")


def validate_process_request_v1(value: object) -> dict[str, object]:
    item = _self_hash_valid(
        value, field="process_request_sha256", label="process request"
    )
    if (
        item.get("schema_version") != PROCESS_REQUEST_SCHEMA
        or item.get("process_contract_id") != PROCESS_CONTRACT_ID
        or item.get("input_payload_decoder_authority_required") is not True
        or item.get("outcome_columns_read") != []
        or any(item.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("process request fixed law or false-authority boundary differs")
    if type(item.get("require_production_width")) is not bool:
        _fail("process request production-width flag must be an exact boolean")
    _integer(item.get("task_index"), label="task index")
    _sha256(item.get("player_registry_sha256"), label="player registry SHA-256")
    blocks = _sequence(item.get("score_block_identities"), label="score blocks")
    if item.get("score_block_identities_sha256") != _sha(
        blocks, label="score blocks"
    ):
        _fail("process request score-block identity hash differs")
    matrix = _mapping(item.get("score_matrix_identity"), label="score matrix identity")
    if item.get("score_matrix_identity_sha256") != _sha(
        matrix, label="score matrix identity"
    ):
        _fail("process request score-matrix identity hash differs")
    for field in (
        "p0_target_authority_identity",
        "world_permutation_authority_identity",
        "runtime_authority_identity",
        "process_budget_identity",
    ):
        _object_identity(item.get(field), label=field)
    _prefix(item.get("output_prefix"))
    return item


def build_consolidated_54_task_manifest_v1(
    *,
    immutable_image_digest: str,
    task_rows: Sequence[Mapping[str, object]],
    launch_intent_identity: Mapping[str, object],
) -> dict[str, object]:
    """Predeclare exactly 54 task request URIs for one immutable image."""
    image = _nonempty(immutable_image_digest, label="immutable image digest")
    if not image.startswith("sha256:") or len(image) != 71:
        _fail("immutable image digest must be one sha256 registry digest")
    _sha256(image[7:], label="immutable image digest body")
    raw_rows = _sequence(task_rows, label="task rows")
    if len(raw_rows) != EXACT_CONSOLIDATED_SLATE_COUNT:
        _fail("consolidated task manifest requires exactly 54 slate tasks")
    normalized: list[dict[str, object]] = []
    slates: list[str] = []
    request_uris: list[str] = []
    for ordinal, raw in enumerate(raw_rows):
        row = _mapping(raw, label=f"task row[{ordinal}]")
        if set(row) != {
            "task_index",
            "slate_id",
            "process_budget_identity",
            "request_uri",
            "output_prefix",
        }:
            _fail(f"task row[{ordinal}] fields differ")
        if row["task_index"] != ordinal:
            _fail("task indices must be contiguous 0..53")
        slate = _nonempty(row["slate_id"], label="task slate ID")
        request_uri = _nonempty(row["request_uri"], label="task request URI")
        if not request_uri.startswith("gs://") or not request_uri.endswith(".json"):
            _fail("task request URI must be one exact GCS JSON URI")
        normalized.append(
            {
                "task_index": ordinal,
                "slate_id": slate,
                "process_budget_identity": _object_identity(
                    row["process_budget_identity"], label="process budget"
                ),
                "request_uri": request_uri,
                "output_prefix": _prefix(row["output_prefix"]),
            }
        )
        slates.append(slate)
        request_uris.append(request_uri)
    if len(set(slates)) != len(slates) or len(set(request_uris)) != len(request_uris):
        _fail("consolidated task slates and request URIs must be unique")
    body = {
        "schema_version": TASK_MANIFEST_SCHEMA,
        "process_contract_id": PROCESS_CONTRACT_ID,
        "scientific_contract_id": successor.CONTRACT_ID,
        "immutable_image_digest": image,
        "task_count": EXACT_CONSOLIDATED_SLATE_COUNT,
        "one_consolidated_image": True,
        "task_rows": normalized,
        "task_rows_sha256": _sha(normalized, label="consolidated task rows"),
        "launch_intent_identity": _object_identity(
            launch_intent_identity, label="launch intent"
        ),
        "task_request_publication_required_before_launch": True,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    return _self_hash(body, "task_manifest_sha256")


def validate_consolidated_54_task_manifest_v1(value: object) -> dict[str, object]:
    item = _self_hash_valid(
        value, field="task_manifest_sha256", label="task manifest"
    )
    expected = build_consolidated_54_task_manifest_v1(
        immutable_image_digest=item.get("immutable_image_digest"),
        task_rows=item.get("task_rows"),
        launch_intent_identity=item.get("launch_intent_identity"),
    )
    if _canonical(expected, label="expected task manifest") != _canonical(
        item, label="task manifest"
    ):
        _fail("task manifest fields differ")
    return expected


def _publish_exact(
    *,
    uri: str,
    payload: bytes,
    publisher: CreateOncePublisher,
    reader: ExactReader,
) -> dict[str, object]:
    try:
        raw_identity = publisher(uri, payload)
    except Exception as exc:
        raise Hard230PopulationProcessV1Error(
            f"create-once publication failed for {uri}"
        ) from exc
    identity = _object_identity(
        raw_identity, label=f"published {uri}", payload=payload
    )
    if identity["uri"] != uri:
        _fail("publisher returned a different output URI")
    try:
        reopened = reader(identity)
    except Exception as exc:
        raise Hard230PopulationProcessV1Error(
            f"exact reopen failed for {uri}"
        ) from exc
    if type(reopened) is not bytes or reopened != payload:
        _fail("create-once object exact reopen differs")
    return identity


class _ShardedEvidenceRecorder:
    def __init__(
        self,
        *,
        budget: Mapping[str, object],
        runtime_authority_identity: Mapping[str, object],
        publisher: CreateOncePublisher,
        reader: ExactReader,
    ) -> None:
        self.budget = budget
        self.runtime_identity = runtime_authority_identity
        self.publisher = publisher
        self.reader = reader
        self.pending: list[dict[str, object]] = []
        self.pending_bytes = 0
        self.records: list[dict[str, object]] = []
        self.shards: list[dict[str, object]] = []

    def __call__(
        self, *, role: str, deterministic_key: str, payload: bytes
    ) -> None:
        if type(payload) is not bytes or not payload:
            _fail("evidence payload must be nonempty exact bytes")
        if len(payload) > int(self.budget["maximum_evidence_record_bytes"]):
            _fail("one evidence record exceeds its precommitted byte ceiling")
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Hard230PopulationProcessV1Error(
                "evidence payload is not canonical JSON"
            ) from exc
        if _canonical(parsed, label="evidence payload") != payload:
            _fail("evidence payload bytes are not canonical JSON")
        ordinal = len(self.records)
        digest = hashlib.sha256(payload).hexdigest()
        reference = {
            "schema_version": successor.EVIDENCE_RECORD_SCHEMA,
            "record_ordinal": ordinal,
            "role": _nonempty(role, label="evidence role"),
            "deterministic_key": _nonempty(
                deterministic_key, label="evidence deterministic key"
            ),
            "payload_sha256": digest,
            "payload_bytes": len(payload),
            "record_id": f"hard230-evidence-{ordinal:05d}-{digest[:24]}",
        }
        if any(
            row["deterministic_key"] == deterministic_key for row in self.records
        ):
            _fail("evidence deterministic key repeats")
        encoded_row_size = len(payload) + 1_024
        if self.pending and (
            len(self.pending) >= int(self.budget["evidence_records_per_shard"])
            or self.pending_bytes + encoded_row_size
            > int(self.budget["evidence_uncompressed_bytes_per_shard"])
        ):
            self._flush()
        self.pending.append({"record_reference": reference, "payload": parsed})
        self.pending_bytes += encoded_row_size
        self.records.append(reference)
        if len(self.records) > int(self.budget["maximum_evidence_record_count"]):
            _fail("evidence record count exceeds the process precharge")

    def _flush(self) -> None:
        if not self.pending:
            return
        ordinal = len(self.shards)
        if ordinal >= int(self.budget["maximum_evidence_shard_count"]):
            _fail("evidence shard count exceeds the process precharge")
        body = {
            "schema_version": EVIDENCE_SHARD_SCHEMA,
            "process_contract_id": PROCESS_CONTRACT_ID,
            "runtime_authority_identity": self.runtime_identity,
            "shard_ordinal": ordinal,
            "first_record_ordinal": self.pending[0]["record_reference"][
                "record_ordinal"
            ],
            "record_count": len(self.pending),
            "records": self.pending,
            "records_sha256": _sha(self.pending, label="evidence shard records"),
            "outcome_columns_read": [],
            **_false_authorities(),
        }
        raw = _canonical(body, label="evidence shard")
        if len(raw) > int(
            self.budget["evidence_uncompressed_bytes_per_shard"]
        ):
            _fail("evidence shard exceeds its uncompressed byte ceiling")
        compressed = zlib.compress(raw, level=9)
        if len(compressed) > int(
            self.budget["maximum_compressed_evidence_shard_bytes"]
        ):
            _fail("compressed evidence shard exceeds its byte ceiling")
        uri = str(self.budget["evidence_shard_uri_template"]).format(
            ordinal=ordinal
        )
        identity = _publish_exact(
            uri=uri,
            payload=compressed,
            publisher=self.publisher,
            reader=self.reader,
        )
        self.shards.append(
            {
                "shard_ordinal": ordinal,
                "first_record_ordinal": body["first_record_ordinal"],
                "record_count": len(self.pending),
                "uncompressed_bytes": len(raw),
                "uncompressed_sha256": hashlib.sha256(raw).hexdigest(),
                "compression": "zlib-level-9",
                "object_identity": identity,
            }
        )
        self.pending = []
        self.pending_bytes = 0

    def finalize(
        self, expected_records: Sequence[Mapping[str, object]]
    ) -> tuple[dict[str, object], dict[str, object]]:
        expected = [dict(row) for row in expected_records]
        if _canonical(expected, label="expected evidence records") != _canonical(
            self.records, label="recorded evidence records"
        ):
            _fail("scientific evidence references differ from recorder order")
        self._flush()
        index_body = {
            "schema_version": EVIDENCE_INDEX_SCHEMA,
            "process_contract_id": PROCESS_CONTRACT_ID,
            "runtime_authority_identity": self.runtime_identity,
            "evidence_record_count": len(self.records),
            "ordered_evidence_records_sha256": successor._ordered_records_sha256(
                self.records, label="hard230 successor evidence records"
            ),
            "evidence_shard_count": len(self.shards),
            "evidence_shards": self.shards,
            "evidence_shards_sha256": _sha(
                self.shards, label="evidence shard identities"
            ),
            "all_records_create_once_published": True,
            "outcome_columns_read": [],
            **_false_authorities(),
        }
        index = _self_hash(index_body, "evidence_index_sha256")
        raw = _canonical(index, label="evidence index")
        if len(raw) > MAX_INDEX_BYTES:
            _fail("evidence index exceeds its byte ceiling")
        identity = _publish_exact(
            uri=str(self.budget["evidence_index_uri"]),
            payload=raw,
            publisher=self.publisher,
            reader=self.reader,
        )
        return index, identity


def execute_and_publish_process_v1(
    *,
    process_request: Mapping[str, object],
    process_request_identity: Mapping[str, object],
    process_budget: Mapping[str, object],
    process_budget_identity: Mapping[str, object],
    player_registry: Sequence[Mapping[str, object]],
    score_matrix: np.ndarray,
    p0_target_authority: Mapping[str, object],
    world_permutation_authority: Mapping[str, object],
    runtime_authority: Mapping[str, object],
    publisher: CreateOncePublisher,
    reader: ExactReader,
    solver_callback: SolverCallback = legal.default_cbc_solver,
) -> Hard230PopulationProcessResult:
    """Run one exact-open cell and publish shards, index, then root."""
    request = validate_process_request_v1(process_request)
    request_identity = _bind(
        request, process_request_identity, label="process request"
    )
    budget = validate_process_budget_v1(process_budget)
    budget_identity = _bind(
        budget, process_budget_identity, label="process budget"
    )
    if request["process_budget_identity"] != budget_identity:
        _fail("process request does not bind the supplied process budget")
    if any(
        request.get(field) != budget.get(field)
        for field in (
            "slate_id",
            "candidate_origin_id",
            "fit_scope_id",
            "heldout_block",
            "training_blocks",
            "worlds_per_block",
            "execution_mode",
            "output_prefix",
            "p0_target_authority_identity",
            "world_permutation_authority_identity",
        )
    ):
        _fail("process request and budget cell bindings differ")
    p0 = successor.validate_p0_target_authority_v1(p0_target_authority)
    permutation = successor.validate_world_permutation_authority_v1(
        world_permutation_authority
    )
    runtime = successor.validate_runtime_authority_v1(runtime_authority)
    p0_identity = successor.bind_authority_identity_v1(
        p0, request["p0_target_authority_identity"], label="P0 target authority"
    )
    permutation_identity = successor.bind_authority_identity_v1(
        permutation,
        request["world_permutation_authority_identity"],
        label="world permutation authority",
    )
    runtime_identity = successor.bind_authority_identity_v1(
        runtime, request["runtime_authority_identity"], label="runtime authority"
    )
    if runtime["process_budget_identity"] != budget_identity:
        _fail("runtime authority does not bind the supplied process budget")
    if runtime["process_source_sha256"] != hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest():
        _fail("runtime process source SHA-256 differs from the executing module")
    if _sha(player_registry, label="loaded player registry") != request[
        "player_registry_sha256"
    ]:
        _fail("loaded player registry differs from the process request")
    recorder = _ShardedEvidenceRecorder(
        budget=budget,
        runtime_authority_identity=runtime_identity,
        publisher=publisher,
        reader=reader,
    )
    scientific = successor.run_hard230_population_successor_v1(
        slate_id=str(request["slate_id"]),
        candidate_origin_id=str(request["candidate_origin_id"]),
        heldout_block=request["heldout_block"],
        worlds_per_block=int(request["worlds_per_block"]),
        source_member_identity=request["source_member_identity"],
        score_block_identities=request["score_block_identities"],
        player_registry=player_registry,
        score_matrix=score_matrix,
        score_matrix_identity=request["score_matrix_identity"],
        p0_target_authority=p0,
        p0_target_authority_identity=p0_identity,
        world_permutation_authority=permutation,
        world_permutation_authority_identity=permutation_identity,
        runtime_authority=runtime,
        runtime_authority_identity=runtime_identity,
        evidence_recorder=recorder,
        execution_mode=str(request["execution_mode"]),
        require_production_width=bool(request["require_production_width"]),
        solver_callback=solver_callback,
    )
    if (
        scientific.receipt["actual_shared_solver_call_count"]
        > budget["maximum_solver_call_count"]
        or scientific.receipt["evidence_record_count"]
        > budget["maximum_evidence_record_count"]
    ):
        _fail("scientific execution exceeded the process precharge")
    evidence_index, evidence_index_identity = recorder.finalize(
        scientific.evidence_records
    )
    if (
        evidence_index["ordered_evidence_records_sha256"]
        != scientific.receipt["ordered_evidence_records_sha256"]
    ):
        _fail("evidence index differs from the scientific receipt")
    body = {
        "schema_version": PROCESS_RECEIPT_SCHEMA,
        "process_contract_id": PROCESS_CONTRACT_ID,
        "scientific_contract_id": successor.CONTRACT_ID,
        "task_index": request["task_index"],
        "slate_id": request["slate_id"],
        "candidate_origin_id": request["candidate_origin_id"],
        "fit_scope_id": request["fit_scope_id"],
        "process_request_identity": request_identity,
        "process_budget_identity": budget_identity,
        "runtime_authority_identity": runtime_identity,
        "scientific_receipt": scientific.receipt,
        "scientific_receipt_sha256": scientific.receipt[
            "successor_receipt_sha256"
        ],
        "evidence_index_identity": evidence_index_identity,
        "evidence_index_sha256": evidence_index["evidence_index_sha256"],
        "publication_order_completed": (
            "evidence-shards-then-index-then-root"
        ),
        "create_once_exact_reopen_completed": True,
        "terminal_execution_attestation_present": False,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    process_receipt = _self_hash(body, "process_receipt_sha256")
    raw = _canonical(process_receipt, label="process receipt")
    if len(raw) > MAX_ROOT_BYTES:
        _fail("process receipt exceeds its byte ceiling")
    root_identity = _publish_exact(
        uri=str(budget["process_receipt_uri"]),
        payload=raw,
        publisher=publisher,
        reader=reader,
    )
    return Hard230PopulationProcessResult(
        process_receipt=process_receipt,
        process_receipt_identity=root_identity,
        evidence_index=evidence_index,
        evidence_index_identity=evidence_index_identity,
        scientific_result=scientific,
    )


def validate_process_receipt_v1(value: object) -> dict[str, object]:
    item = _self_hash_valid(
        value, field="process_receipt_sha256", label="process receipt"
    )
    if (
        item.get("schema_version") != PROCESS_RECEIPT_SCHEMA
        or item.get("process_contract_id") != PROCESS_CONTRACT_ID
        or item.get("scientific_contract_id") != successor.CONTRACT_ID
        or item.get("publication_order_completed")
        != "evidence-shards-then-index-then-root"
        or item.get("create_once_exact_reopen_completed") is not True
        or item.get("terminal_execution_attestation_present") is not False
        or any(item.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("process receipt fixed law or false-authority boundary differs")
    scientific = successor.validate_successor_receipt_v1(
        item.get("scientific_receipt")
    )
    if item.get("scientific_receipt_sha256") != scientific[
        "successor_receipt_sha256"
    ]:
        _fail("process receipt scientific binding differs")
    return item


__all__ = [
    "EVIDENCE_RECORDS_PER_SHARD",
    "EXACT_CONSOLIDATED_SLATE_COUNT",
    "Hard230PopulationProcessResult",
    "Hard230PopulationProcessV1Error",
    "PROCESS_BUDGET_SCHEMA",
    "PROCESS_REQUEST_SCHEMA",
    "TASK_MANIFEST_SCHEMA",
    "build_consolidated_54_task_manifest_v1",
    "build_process_budget_v1",
    "build_process_request_v1",
    "execute_and_publish_process_v1",
    "validate_consolidated_54_task_manifest_v1",
    "validate_process_budget_v1",
    "validate_process_receipt_v1",
    "validate_process_request_v1",
]
