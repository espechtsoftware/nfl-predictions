"""Candidate-v2 aligned, discovery-only matrix freezer for Experiment 5.

The freezer consumes exactly two already-published score-free authorities:
the fixed-G0 candidate-v2 terminal and the LR8 later-source freeze.  For each
of the 54 canonical slates it sums the nine candidate players over R0--R3 in
that order using the production selector's float64 accumulation law.  R4 is
bound as the held-out artifact and is never opened by matrix construction.

Large matrix bodies use a file boundary.  One task opens one NPZ block at a
time and writes directly into a disk-backed memmap; neither a five-block
player matrix nor multiple slate matrices are retained in memory.  Storage
adapters are intentionally injected.  This module has no listing, overwrite,
delete, outcome, graph, deployment, contest-entry, or policy-promotion API.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Final

import numpy as np

from . import corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate_release
from . import corpus_r6_construction_allocation_cross_operator_v1 as runtime_contract
from . import corpus_r6_matchup_source_v2 as source
from . import lr8_later_period_source as later


MANIFEST_SCHEMA: Final = "corpus-r6-paid-source-discovery-matrix-manifest/v1"
TASK_BINDING_SCHEMA: Final = (
    "corpus-r6-paid-source-discovery-matrix-task-binding/v1"
)
LOCAL_MATRIX_SCHEMA: Final = (
    "corpus-r6-paid-source-discovery-matrix-local-materialization/v1"
)
TASK0_SCHEMA: Final = "corpus-r6-paid-source-discovery-matrix-task0/v1"
TASK0_GATE_SCHEMA: Final = (
    "corpus-r6-paid-source-discovery-matrix-task0-gate/v1"
)
TASK_RESULT_SCHEMA: Final = "corpus-r6-paid-source-discovery-matrix-task-result/v1"
PROVIDER_EXECUTION_SCHEMA: Final = (
    "corpus-r6-paid-source-discovery-matrix-provider-execution/v1"
)
RUNTIME_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-paid-source-discovery-matrix-runtime-authority/v1"
)
TERMINAL_SCHEMA: Final = "corpus-r6-paid-source-discovery-matrix-terminal/v1"
REOPEN_SCHEMA: Final = (
    "corpus-r6-paid-source-discovery-matrix-independent-reopen/v1"
)
LOCAL_REOPEN_AUDIT_SCHEMA: Final = (
    "corpus-r6-paid-source-discovery-matrix-local-reopen-audit/v1"
)
REGISTRY_REOPEN_SCHEMA: Final = (
    "corpus-r6-paid-source-discovery-matrix-registry-reopen/v1"
)
REOPEN_TASK_SCHEMA: Final = (
    "corpus-r6-paid-source-discovery-matrix-reopen-task/v1"
)
MATRIX_ENVELOPE_SCHEMA: Final = "r6-paid-source-discovery-world-matrix-bytes/v2"
SCORING_LAW_ID: Final = "candidate-roster-r0-r3-float64-sum/v1"

TASK_COUNT: Final = 54
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
DISCOVERY_BLOCKS: Final = WORLD_BLOCKS[:4]
HELDOUT_BLOCK: Final = "R4"
WORLDS_PER_BLOCK: Final = 10_000
DISCOVERY_WORLD_COUNT: Final = 40_000
MATRIX_DTYPE: Final = np.dtype("<f8")
MAX_MATRIX_BYTES: Final = 2 * 1024 * 1024 * 1024
ROW_CHUNK: Final = 64
PROJECT_ID: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
JOB_NAME: Final = "atlas-cbc-32g-full-2023-w8-v1"
JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
SERVICE_ACCOUNT: Final = "817589974517-compute@developer.gserviceaccount.com"
# Cloud Run normalizes ``--task-timeout 21600s`` to this integer-seconds
# string in provider execution JSON.  Receipts bind the observed provider
# representation, not the caller's CLI spelling.
TASK_TIMEOUT_SECONDS: Final = "21600"
CPU_LIMIT: Final = "8"
MEMORY_LIMIT: Final = "32Gi"
CONTAINER_COMMAND: Final = ("/bin/bash",)
CONTAINER_SCRIPT: Final = (
    "/app/scripts/cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.sh"
)

OUTPUT_PREFIX: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-paid-source-discovery-matrices"
)
CANDIDATE_ROOT_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-fixed-g0-candidate-authorities-v2/"
        "20260830-fixed-g0-candidate-authority-v2/"
        "candidate-authority-release-v2.json"
    ),
    "generation": "1788081739195827",
    "sha256": "ae6d0ba73ac627f652f2cfc542da3f43885f4b9090885457fa313ecb6a7faea8",
    "bytes": 216_639,
}
LATER_SOURCE_FREEZE_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-source/research/source/"
        "20260821-corpus-artifact-source-authority-v3/source/"
        "later-source-freeze.json"
    ),
    "generation": "1787367678830738",
    "sha256": "c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a",
    "bytes": 4_566_802,
}

ReadExact = Callable[[Mapping[str, object]], bytes]
FetchExactToFile = Callable[[Mapping[str, object], Path], None]

_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{7,80}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_BUILD_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_IMAGE = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}\Z"
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_EXECUTION = re.compile(r"[a-z][a-z0-9-]{2,100}\Z")


class CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error(ValueError):
    """One exact parent, matrix, or score-free publication fact differed."""


@dataclass(frozen=True, slots=True)
class ReopenedPaidSourceDiscoveryMatrixFreezeV1:
    """Deep-reopened freezer root and its ordered consumer registry."""

    terminal: dict[str, object]
    terminal_identity: dict[str, object]
    manifest: dict[str, object]
    manifest_identity: dict[str, object]
    matrix_registry: tuple[dict[str, object], ...]
    reopen_receipt: dict[str, object]


def _fail(message: str) -> None:
    raise CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return source.canonical_json_bytes(value)
    except Exception as exc:
        raise CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error(
            "canonical JSON differs"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except Exception as exc:
        raise CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error(str(exc)) from exc


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        _fail(f"{field} must not be supplied before hashing")
    result = dict(value)
    result[field] = canonical_sha256(result)
    return result


def _validate_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    digest = value.get(field)
    if type(digest) is not str or _SHA.fullmatch(digest) is None:
        _fail(f"{label} self-hash differs")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256(body) != digest:
        _fail(f"{label} self-hash differs")


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "promotion_authority": False,
        "graph_mutation_licensed": False,
    }


def _read_exact(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if not callable(read_exact):
        _fail("exact reader differs")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error(
            f"{label} generation-exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ")
    return raw, identity


def _parse_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error(
            f"{label} JSON differs"
        ) from exc
    item = _mapping(value, label=label)
    if canonical_json_bytes(item) != raw:
        _fail(f"{label} bytes are not canonical JSON")
    return item


def _artifact_identity(receipt_value: object, *, label: str) -> dict[str, object]:
    receipt = _mapping(receipt_value, label=label)
    return _identity(
        {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")},
        label=f"{label} object",
    )


def _scoring_law() -> dict[str, object]:
    return {
        "scoring_law_id": SCORING_LAW_ID,
        "candidate_roster_player_order": "ascending-player-id",
        "source_player_draw_dtype": "float32",
        "accumulation_dtype": "float64",
        "matrix_dtype": MATRIX_DTYPE.str,
        "block_order": list(DISCOVERY_BLOCKS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "world_count": DISCOVERY_WORLD_COUNT,
        "matrix_representation": "candidate-by-simulated-world-dk-points",
        "matrix_byte_representation": MATRIX_ENVELOPE_SCHEMA,
    }


def validate_provider_execution_receipt_v1(
    value: object,
    *,
    expected_execution_id: str,
    expected_mode: str,
    expected_task_count: int,
    expected_payload_identity: Mapping[str, object],
    manifest_value: object,
) -> dict[str, object]:
    """Validate one provider-observed execution and its exact launch payload."""

    manifest = validate_manifest_v1(manifest_value)
    receipt = _mapping(value, label="matrix provider execution receipt")
    _validate_hash(
        receipt,
        field="provider_execution_sha256",
        label="matrix provider execution receipt",
    )
    payload_identity = _identity(
        receipt.get("payload_identity"), label="matrix execution payload"
    )
    if (
        type(expected_execution_id) is not str
        or _EXECUTION.fullmatch(expected_execution_id) is None
        or expected_mode not in {"task0", "task", "reopen-task"}
        or type(expected_task_count) is not int
        or expected_task_count not in {1, TASK_COUNT}
        or expected_task_count
        != (1 if expected_mode == "task0" else TASK_COUNT)
        or receipt.get("schema_version") != PROVIDER_EXECUTION_SCHEMA
        or receipt.get("execution_id") != expected_execution_id
        or type(receipt.get("execution_uid")) is not str
        or not receipt["execution_uid"]
        or receipt.get("job_name") != JOB_NAME
        or receipt.get("job_uid") != JOB_UID
        or receipt.get("mode") != expected_mode
        or receipt.get("payload_identity") != _identity(
            expected_payload_identity, label="expected execution payload"
        )
        or payload_identity != receipt.get("payload_identity")
        or type(receipt.get("payload_sha256")) is not str
        or _SHA.fullmatch(str(receipt.get("payload_sha256"))) is None
        or receipt.get("task_count") != expected_task_count
        or receipt.get("parallelism")
        != (1 if expected_mode == "task0" else TASK_COUNT)
        or receipt.get("succeeded_count") != expected_task_count
        or receipt.get("failed_count") != 0
        or receipt.get("cancelled_count") != 0
        or receipt.get("running_count") != 0
        or receipt.get("max_retries") != 0
        or receipt.get("timeout_seconds") != TASK_TIMEOUT_SECONDS
        or receipt.get("service_account") != SERVICE_ACCOUNT
        or receipt.get("immutable_image") != manifest["immutable_image"]
        or receipt.get("command") != list(CONTAINER_COMMAND)
        or receipt.get("args")
        != [CONTAINER_SCRIPT, "container-run", expected_mode]
        or receipt.get("resources")
        != {"cpu": CPU_LIMIT, "memory": MEMORY_LIMIT}
        or receipt.get("code_sha") != manifest["code_sha"]
        or receipt.get("build_id") != manifest["build_id"]
        or (
            expected_mode == "task"
            and (
                type(receipt.get("task0_execution_id")) is not str
                or _EXECUTION.fullmatch(str(receipt.get("task0_execution_id")))
                is None
                or type(receipt.get("task0_gate_sha256")) is not str
                or _SHA.fullmatch(str(receipt.get("task0_gate_sha256"))) is None
            )
        )
        or (
            expected_mode != "task"
            and (
                receipt.get("task0_execution_id") != "none"
                or receipt.get("task0_gate_sha256") != "none"
            )
        )
        or receipt.get("outcomes_allowed") is not False
        or type(receipt.get("environment_sha256")) is not str
        or _SHA.fullmatch(str(receipt.get("environment_sha256"))) is None
        or receipt.get("terminal") is not True
        or receipt.get("complete") is not True
    ):
        _fail("matrix provider execution receipt differs")
    embedded_gate = receipt.get("task0_gate_receipt")
    if expected_mode == "task":
        gate = validate_task0_gate_v1(
            embedded_gate,
            manifest_value=manifest,
            manifest_identity=payload_identity,
            expected_execution_id=str(receipt["task0_execution_id"]),
        )
        if gate["task0_gate_sha256"] != receipt["task0_gate_sha256"]:
            _fail("matrix provider task0 gate receipt differs")
    elif embedded_gate is not None:
        _fail("matrix provider task0 gate receipt differs")
    return receipt


def validate_task0_gate_v1(
    value: object,
    *,
    manifest_value: object,
    manifest_identity: Mapping[str, object],
    expected_execution_id: str,
) -> dict[str, object]:
    """Validate the complete task0 launch proof carried by the full cohort."""

    manifest = validate_manifest_v1(manifest_value)
    retained_manifest_identity = _identity(
        manifest_identity, label="task0 gate matrix manifest"
    )
    gate = _mapping(value, label="matrix task0 gate")
    _validate_hash(gate, field="task0_gate_sha256", label="matrix task0 gate")
    task0_receipt = validate_task0_receipt_v1(
        gate.get("task0_receipt"),
        manifest_value=manifest,
        manifest_identity=retained_manifest_identity,
        expected_execution_id=expected_execution_id,
    )
    provider_receipt = validate_provider_execution_receipt_v1(
        gate.get("provider_execution_receipt"),
        expected_execution_id=expected_execution_id,
        expected_mode="task0",
        expected_task_count=1,
        expected_payload_identity=retained_manifest_identity,
        manifest_value=manifest,
    )
    if (
        retained_manifest_identity["uri"]
        != f"{manifest['output_prefix']}manifest.json"
        or retained_manifest_identity["sha256"] != canonical_sha256(manifest)
        or retained_manifest_identity["bytes"] != len(canonical_json_bytes(manifest))
        or gate.get("schema_version") != TASK0_GATE_SCHEMA
        or gate.get("manifest_identity") != retained_manifest_identity
        or gate.get("manifest_sha256") != manifest["manifest_sha256"]
        or gate.get("execution_id") != expected_execution_id
        or gate.get("task0_receipt_sha256")
        != task0_receipt["task0_receipt_sha256"]
        or gate.get("provider_execution_sha256")
        != provider_receipt["provider_execution_sha256"]
        or task0_receipt["runtime_authority"]["execution_id"]
        != provider_receipt["execution_id"]
        or task0_receipt["runtime_authority"]["code_sha"]
        != provider_receipt["code_sha"]
        or task0_receipt["runtime_authority"]["immutable_image"]
        != provider_receipt["immutable_image"]
        or task0_receipt["runtime_authority"]["build_id"]
        != provider_receipt["build_id"]
        or gate.get("exactly_one_canonical_stdout_receipt") is not True
        or gate.get("full_cohort_execution_launched") is not False
        or gate.get("complete") is not True
    ):
        _fail("matrix task0 gate differs")
    return gate


def _task_binding(
    *, run_id: str, descriptor: Mapping[str, object], source_slate: Mapping[str, object],
) -> dict[str, object]:
    ordinal = descriptor.get("source_task_ordinal")
    slate = _mapping(descriptor.get("slate"), label="candidate descriptor slate")
    if (
        type(ordinal) is not int
        or not 0 <= ordinal < TASK_COUNT
        or source_slate.get("slate_id") != slate.get("slate_id")
        or source_slate.get("season") != slate.get("season")
        or source_slate.get("week") != slate.get("week")
    ):
        _fail("candidate/later-source slate lattice differs")
    receipts = [
        _mapping(row, label=f"world receipt[{ordinal}]")
        for row in _sequence(
            source_slate.get("artifact_receipts"), label="source artifacts"
        )
    ]
    if [row.get("block") for row in receipts] != list(WORLD_BLOCKS):
        _fail("later-source world block order differs")
    discovery = []
    for block, receipt in zip(DISCOVERY_BLOCKS, receipts[:4], strict=True):
        identity = _artifact_identity(receipt, label=f"{block} receipt")
        discovery.append({
            "block": block,
            "identity": identity,
            "source_artifact_receipt": receipt,
            "source_artifact_receipt_sha256": canonical_sha256(receipt),
        })
    heldout_receipt = receipts[4]
    heldout = {
        "block": HELDOUT_BLOCK,
        "identity": _artifact_identity(heldout_receipt, label="R4 receipt"),
        "source_artifact_receipt_sha256": canonical_sha256(heldout_receipt),
        "heldout": True,
        "read_by_matrix_task": False,
    }
    base = (
        f"{OUTPUT_PREFIX}/{run_id}/source-task-{ordinal:02d}-"
        f"{slate['slate_id']}/"
    )
    body: dict[str, object] = {
        "schema_version": TASK_BINDING_SCHEMA,
        "source_task_ordinal": ordinal,
        "task_id": descriptor.get("task_id"),
        "slate": slate,
        "candidate_artifact_identity": _identity(
            descriptor.get("candidate_artifact_identity"),
            label="candidate artifact",
        ),
        "candidate_artifact_sha256": descriptor.get("candidate_artifact_sha256"),
        "candidate_count": descriptor.get("candidate_count"),
        "ordered_candidate_ids_sha256": descriptor.get(
            "ordered_candidate_ids_sha256"
        ),
        "discovery_world_artifacts": discovery,
        "discovery_world_identity_manifest_sha256": canonical_sha256(
            [row["identity"] for row in discovery]
        ),
        "heldout_world_artifact": heldout,
        "scoring_law": _scoring_law(),
        "matrix_uri": f"{base}candidate-discovery-matrix.bin",
        "task_result_uri": f"{base}task-result.json",
        "reopen_task_uri": f"{base}reopen-task-result.json",
        **_policy(),
    }
    if (
        type(body["task_id"]) is not str
        or type(body["candidate_artifact_sha256"]) is not str
        or _SHA.fullmatch(str(body["candidate_artifact_sha256"])) is None
        or type(body["candidate_count"]) is not int
        or int(body["candidate_count"]) < 80
        or type(body["ordered_candidate_ids_sha256"]) is not str
        or _SHA.fullmatch(str(body["ordered_candidate_ids_sha256"])) is None
    ):
        _fail("candidate descriptor binding differs")
    expected_bytes = (
        int(body["candidate_count"])
        * DISCOVERY_WORLD_COUNT
        * MATRIX_DTYPE.itemsize
    )
    if expected_bytes >= MAX_MATRIX_BYTES:
        _fail("candidate discovery matrix exceeds the one-slate byte ceiling")
    return _with_hash(body, field="task_binding_sha256")


def prepare_manifest_v1(
    *,
    run_id: str,
    code_sha: str,
    immutable_image: str,
    build_id: str,
    runtime_build_attestation_identity: Mapping[str, object],
    read_exact: ReadExact,
    candidate_root_identity: Mapping[str, object] = CANDIDATE_ROOT_IDENTITY,
    later_source_freeze_identity: Mapping[str, object] = LATER_SOURCE_FREEZE_IDENTITY,
) -> dict[str, object]:
    """Open both exact roots and freeze all 54 score-free task bindings."""

    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("matrix-freeze run ID differs")
    if type(code_sha) is not str or _COMMIT.fullmatch(code_sha) is None:
        _fail("matrix-freeze code SHA differs")
    if type(immutable_image) is not str or _IMAGE.fullmatch(immutable_image) is None:
        _fail("matrix-freeze immutable image differs")
    if type(build_id) is not str or _BUILD_ID.fullmatch(build_id) is None:
        _fail("matrix-freeze build ID differs")
    candidate_identity = _identity(candidate_root_identity, label="candidate-v2 root")
    source_identity = _identity(
        later_source_freeze_identity, label="later-source freeze"
    )
    if candidate_identity != CANDIDATE_ROOT_IDENTITY:
        _fail("candidate-v2 root is not the frozen production authority")
    if source_identity != LATER_SOURCE_FREEZE_IDENTITY:
        _fail("later-source freeze is not the frozen production authority")
    candidate_raw, _ = _read_exact(
        candidate_identity, read_exact=read_exact, label="candidate-v2 root"
    )
    source_raw, _ = _read_exact(
        source_identity, read_exact=read_exact, label="later-source freeze"
    )
    build_raw, build_identity = _read_exact(
        runtime_build_attestation_identity,
        read_exact=read_exact,
        label="runtime build attestation",
    )
    try:
        candidate_root = (
            candidate_release.validate_fixed_g0_candidate_authority_release_structure_v2(
                _parse_canonical(candidate_raw, label="candidate-v2 root")
            )
        )
        source_freeze_raw = _parse_canonical(
            source_raw, label="later-source freeze"
        )
        source_freeze = later.validate_source_freeze(
            source_freeze_raw,
            expected_freeze_sha256=str(source_freeze_raw.get("freeze_sha256")),
        )
        build_attestation = runtime_contract.validate_runtime_build_attestation_v1(
            _parse_canonical(build_raw, label="runtime build attestation"),
            expected_code_sha=code_sha,
            expected_image_digest=immutable_image.rsplit("@", 1)[1],
        )
    except Exception as exc:
        raise CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error(
            f"matrix-freeze parent validation failed: {exc}"
        ) from exc
    if build_attestation.get("build_id") != build_id:
        _fail("runtime build attestation provider ID differs")
    descriptors = [
        _mapping(row, label=f"candidate descriptor[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(candidate_root.get("objects"), label="candidate objects")
        )
    ]
    source_slates = [
        _mapping(row, label=f"source slate[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(source_freeze.get("slates"), label="source slates")
        )
    ]
    if len(descriptors) != TASK_COUNT or len(source_slates) != TASK_COUNT:
        _fail("matrix-freeze parent slate count differs")
    tasks = [
        _task_binding(
            run_id=run_id, descriptor=descriptor, source_slate=source_slates[ordinal]
        )
        for ordinal, descriptor in enumerate(descriptors)
    ]
    prefix = f"{OUTPUT_PREFIX}/{run_id}/"
    body: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "run_id": run_id,
        "code_sha": code_sha,
        "immutable_image": immutable_image,
        "image_digest": immutable_image.rsplit("@", 1)[1],
        "build_id": build_id,
        "runtime_build_attestation_identity": build_identity,
        "runtime_build_attestation_sha256": build_attestation[
            "runtime_build_attestation_sha256"
        ],
        "candidate_authority_root_identity": candidate_identity,
        "candidate_authority_release_sha256": candidate_root.get(
            "candidate_authority_release_sha256"
        ),
        "later_source_freeze_identity": source_identity,
        "later_source_freeze_sha256": source_freeze.get("freeze_sha256"),
        "task_count": TASK_COUNT,
        "discovery_blocks": list(DISCOVERY_BLOCKS),
        "heldout_block": HELDOUT_BLOCK,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "discovery_world_count": DISCOVERY_WORLD_COUNT,
        "scoring_law": _scoring_law(),
        "tasks": tasks,
        "task_binding_manifest_sha256": canonical_sha256(tasks),
        "output_prefix": prefix,
        "terminal_uri": f"{prefix}terminal.json",
        "reopen_terminal_uri": f"{prefix}reopen-terminal.json",
        "task0_required_before_full_execution": True,
        "task0_publication_allowed": False,
        "root_published_last": True,
        "bounded_memory_law": (
            "one-slate-one-npz-block-at-a-time-disk-backed-float64-memmap"
        ),
        "r4_heldout_bound_but_not_read": True,
        **_policy(),
    }
    return _with_hash(body, field="manifest_sha256")


def validate_manifest_v1(value: object) -> dict[str, object]:
    manifest = _mapping(value, label="matrix-freeze manifest")
    _validate_hash(manifest, field="manifest_sha256", label="matrix-freeze manifest")
    tasks = [
        _mapping(row, label=f"matrix task[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(manifest.get("tasks"), label="matrix tasks")
        )
    ]
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("candidate_authority_root_identity")
        != CANDIDATE_ROOT_IDENTITY
        or manifest.get("later_source_freeze_identity")
        != LATER_SOURCE_FREEZE_IDENTITY
        or manifest.get("task_count") != TASK_COUNT
        or len(tasks) != TASK_COUNT
        or manifest.get("discovery_blocks") != list(DISCOVERY_BLOCKS)
        or manifest.get("heldout_block") != HELDOUT_BLOCK
        or manifest.get("worlds_per_block") != WORLDS_PER_BLOCK
        or manifest.get("discovery_world_count") != DISCOVERY_WORLD_COUNT
        or manifest.get("scoring_law") != _scoring_law()
        or manifest.get("task_binding_manifest_sha256") != canonical_sha256(tasks)
        or manifest.get("task0_required_before_full_execution") is not True
        or manifest.get("task0_publication_allowed") is not False
        or manifest.get("root_published_last") is not True
        or manifest.get("r4_heldout_bound_but_not_read") is not True
        or any(manifest.get(key) != value for key, value in _policy().items())
    ):
        _fail("matrix-freeze manifest differs")
    for ordinal, task in enumerate(tasks):
        _validate_hash(task, field="task_binding_sha256", label="matrix task")
        discovery = _sequence(
            task.get("discovery_world_artifacts"), label="task discovery worlds"
        )
        heldout = _mapping(task.get("heldout_world_artifact"), label="task heldout")
        if (
            task.get("schema_version") != TASK_BINDING_SCHEMA
            or task.get("source_task_ordinal") != ordinal
            or [
                _mapping(row, label="discovery row").get("block")
                for row in discovery
            ] != list(DISCOVERY_BLOCKS)
            or heldout.get("block") != HELDOUT_BLOCK
            or heldout.get("heldout") is not True
            or heldout.get("read_by_matrix_task") is not False
            or task.get("scoring_law") != _scoring_law()
            or any(task.get(key) != value for key, value in _policy().items())
        ):
            _fail(f"matrix task[{ordinal}] differs")
    return manifest


def _hash_file(path: Path, *, offset: int = 0) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        if offset:
            handle.seek(offset)
        while True:
            chunk = handle.read(4 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def build_task_matrix_file_v1(
    *,
    manifest_value: object,
    source_task_ordinal: int,
    read_exact: ReadExact,
    destination: Path,
) -> dict[str, object]:
    """Build one candidate x 40,000 float64 envelope with bounded memory."""

    manifest = validate_manifest_v1(manifest_value)
    if type(source_task_ordinal) is not int or not 0 <= source_task_ordinal < TASK_COUNT:
        _fail("matrix task ordinal differs")
    task = _mapping(
        manifest["tasks"][source_task_ordinal], label="selected matrix task"
    )
    destination = Path(destination)
    if not destination.is_absolute() or destination.exists() or destination.is_symlink():
        _fail("matrix destination must be one absent absolute path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    candidate_raw, candidate_identity = _read_exact(
        task["candidate_artifact_identity"],
        read_exact=read_exact,
        label="candidate artifact",
    )
    try:
        candidate_artifact = source.validate_accepted_candidate_artifact_v1(
            _parse_canonical(candidate_raw, label="candidate artifact")
        )
    except Exception as exc:
        raise CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error(
            f"candidate artifact validation failed: {exc}"
        ) from exc
    rows = [
        _mapping(row, label=f"candidate row[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(candidate_artifact.get("rows"), label="candidate rows")
        )
    ]
    candidate_ids = [str(row.get("candidate_id")) for row in rows]
    rosters = [tuple(str(value) for value in row.get("player_ids", [])) for row in rows]
    if (
        candidate_identity != task["candidate_artifact_identity"]
        or candidate_artifact.get("candidate_artifact_sha256")
        != task["candidate_artifact_sha256"]
        or candidate_artifact.get("candidate_count") != task["candidate_count"]
        or candidate_artifact.get("ordered_candidate_ids_sha256")
        != task["ordered_candidate_ids_sha256"]
        or canonical_sha256(candidate_ids) != task["ordered_candidate_ids_sha256"]
        or len(candidate_ids) != len(set(candidate_ids))
        or any(len(roster) != 9 or len(set(roster)) != 9 for roster in rosters)
        or any(tuple(sorted(roster)) != roster for roster in rosters)
    ):
        _fail("candidate artifact/order differs from matrix task")
    header = {
        "schema_version": MATRIX_ENVELOPE_SCHEMA,
        "candidate_ids": candidate_ids,
        "candidate_artifact_identity": task["candidate_artifact_identity"],
        "candidate_ids_sha256": task["ordered_candidate_ids_sha256"],
        "dtype": MATRIX_DTYPE.str,
        "shape": [len(candidate_ids), DISCOVERY_WORLD_COUNT],
        "block_order": list(DISCOVERY_BLOCKS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "source_world_artifact_identities": [
            row["identity"] for row in task["discovery_world_artifacts"]
        ],
        "source_world_artifact_manifest_sha256": task[
            "discovery_world_identity_manifest_sha256"
        ],
        "r4_heldout_not_read": True,
    }
    header_raw = canonical_json_bytes(header) + b"\n"
    body_bytes = len(candidate_ids) * DISCOVERY_WORLD_COUNT * MATRIX_DTYPE.itemsize
    total_bytes = len(header_raw) + body_bytes
    if body_bytes <= 0 or total_bytes > MAX_MATRIX_BYTES:
        _fail("candidate discovery matrix byte size differs")
    descriptor = os.open(
        destination, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    try:
        os.write(descriptor, header_raw)
        os.ftruncate(descriptor, total_bytes)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    matrix = np.memmap(
        destination,
        dtype=MATRIX_DTYPE,
        mode="r+",
        offset=len(header_raw),
        shape=(len(candidate_ids), DISCOVERY_WORLD_COUNT),
        order="C",
    )
    discovery = [
        _mapping(row, label=f"discovery block[{ordinal}]")
        for ordinal, row in enumerate(task["discovery_world_artifacts"])
    ]
    try:
        for block_ordinal, (block, binding) in enumerate(
            zip(DISCOVERY_BLOCKS, discovery, strict=True)
        ):
            receipt = _mapping(
                binding.get("source_artifact_receipt"), label=f"{block} receipt"
            )
            if (
                binding.get("block") != block
                or binding.get("identity")
                != _artifact_identity(receipt, label=f"{block} receipt")
                or binding.get("source_artifact_receipt_sha256")
                != canonical_sha256(receipt)
            ):
                _fail(f"{block} task receipt binding differs")
            raw, _ = _read_exact(
                binding["identity"], read_exact=read_exact, label=f"{block} NPZ"
            )
            try:
                world = later.load_artifact_worlds(receipt, raw)
            except Exception as exc:
                raise CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error(
                    f"{block} world artifact validation failed: {exc}"
                ) from exc
            del raw
            player_index = {
                player_id: row for row, player_id in enumerate(world.player_ids)
            }
            unknown = sorted({
                player_id
                for roster in rosters
                for player_id in roster
                if player_id not in player_index
            })
            if unknown:
                _fail(f"candidate roster players absent from {block}: {unknown[:5]}")
            candidate_player_indices = np.asarray(
                [[player_index[player] for player in roster] for roster in rosters],
                dtype=np.intp,
                order="C",
            )
            start = block_ordinal * WORLDS_PER_BLOCK
            stop = start + WORLDS_PER_BLOCK
            for row_start in range(0, len(rosters), ROW_CHUNK):
                row_stop = min(row_start + ROW_CHUNK, len(rosters))
                matrix[row_start:row_stop, start:stop] = world.player_draws[
                    candidate_player_indices[row_start:row_stop]
                ].sum(axis=1, dtype=np.float64)
            matrix.flush()
            del candidate_player_indices
            del world
        for row_start in range(0, len(candidate_ids), ROW_CHUNK):
            row_stop = min(row_start + ROW_CHUNK, len(candidate_ids))
            if not np.isfinite(matrix[row_start:row_stop]).all():
                _fail("candidate discovery matrix contains a non-finite value")
    finally:
        matrix.flush()
        del matrix
    body: dict[str, object] = {
        "schema_version": LOCAL_MATRIX_SCHEMA,
        "manifest_sha256": manifest["manifest_sha256"],
        "task_binding_sha256": task["task_binding_sha256"],
        "source_task_ordinal": source_task_ordinal,
        "slate": task["slate"],
        "candidate_artifact_identity": task["candidate_artifact_identity"],
        "candidate_count": len(candidate_ids),
        "ordered_candidate_ids_sha256": task["ordered_candidate_ids_sha256"],
        "discovery_world_identity_manifest_sha256": task[
            "discovery_world_identity_manifest_sha256"
        ],
        "heldout_world_artifact": task["heldout_world_artifact"],
        "matrix_uri": task["matrix_uri"],
        "matrix_bytes": total_bytes,
        "matrix_sha256": _hash_file(destination),
        "matrix_body_sha256": _hash_file(destination, offset=len(header_raw)),
        "matrix_header_sha256": sha256(header_raw[:-1]).hexdigest(),
        "matrix_shape": [len(candidate_ids), DISCOVERY_WORLD_COUNT],
        "matrix_dtype": MATRIX_DTYPE.str,
        "scoring_law": _scoring_law(),
        "npz_body_read_count": 4,
        "r4_body_read": False,
        "bounded_memory_law_applied": True,
        "publication_performed": False,
        **_policy(),
    }
    return _with_hash(body, field="local_materialization_sha256")


def build_task0_receipt_v1(
    *,
    manifest_value: object,
    manifest_identity: Mapping[str, object],
    local_materialization_value: object,
    runtime_authority: Mapping[str, object],
) -> dict[str, object]:
    manifest = validate_manifest_v1(manifest_value)
    retained_manifest_identity = _identity(
        manifest_identity, label="task0 matrix manifest"
    )
    local = _mapping(local_materialization_value, label="task0 local matrix")
    _validate_hash(local, field="local_materialization_sha256", label="task0 local")
    runtime = _mapping(runtime_authority, label="task0 runtime authority")
    _validate_hash(
        runtime, field="runtime_authority_sha256", label="task0 runtime authority"
    )
    if (
        retained_manifest_identity["uri"]
        != f"{manifest['output_prefix']}manifest.json"
        or retained_manifest_identity["sha256"] != canonical_sha256(manifest)
        or retained_manifest_identity["bytes"] != len(canonical_json_bytes(manifest))
        or local.get("source_task_ordinal") != 0
        or local.get("manifest_sha256") != manifest["manifest_sha256"]
        or local.get("publication_performed") is not False
        or local.get("r4_body_read") is not False
        or runtime.get("schema_version") != RUNTIME_AUTHORITY_SCHEMA
        or runtime.get("runtime_mode") != "task0"
        or runtime.get("project_id") != PROJECT_ID
        or runtime.get("region") != REGION
        or runtime.get("job_name") != JOB_NAME
        or type(runtime.get("execution_id")) is not str
        or _EXECUTION.fullmatch(str(runtime.get("execution_id"))) is None
        or runtime.get("source_task_ordinal") != 0
        or runtime.get("task_count") != 1
        or runtime.get("scientific_task_count") != TASK_COUNT
        or runtime.get("task_attempt") != 0
        or runtime.get("manifest_sha256") != manifest["manifest_sha256"]
        or runtime.get("code_sha") != manifest["code_sha"]
        or runtime.get("immutable_image") != manifest["immutable_image"]
        or runtime.get("build_id") != manifest["build_id"]
        or runtime.get("task0_execution_id") != "none"
        or runtime.get("task0_gate_sha256") != "none"
        or runtime.get("outcomes_allowed") is not False
    ):
        _fail("task0 local materialization differs")
    body = {
        "schema_version": TASK0_SCHEMA,
        "manifest_identity": retained_manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "source_task_ordinal": 0,
        "task_binding_sha256": local["task_binding_sha256"],
        "local_materialization_sha256": local["local_materialization_sha256"],
        "matrix_sha256": local["matrix_sha256"],
        "matrix_shape": local["matrix_shape"],
        "matrix_dtype": local["matrix_dtype"],
        "runtime_authority": runtime,
        "runtime_authority_sha256": runtime["runtime_authority_sha256"],
        "publication_performed": False,
        "task0_storage_adapter_write_api_present": False,
        "service_account": SERVICE_ACCOUNT,
        "service_account_write_capability_absence_asserted": False,
        "ambient_service_account_write_capability_restricted": False,
        "write_boundary_is_adapter_not_iam": True,
        "write_api_invoked": False,
        "full_cohort_execution_launched": False,
        "mechanical_launch_gate_passed": True,
        "r4_body_read": False,
        "complete": True,
        **_policy(),
    }
    return _with_hash(body, field="task0_receipt_sha256")


def validate_task0_receipt_v1(
    value: object,
    *,
    manifest_value: object,
    manifest_identity: Mapping[str, object],
    expected_execution_id: str,
) -> dict[str, object]:
    """Replay the one canonical stdout receipt used to open the full cohort."""

    manifest = validate_manifest_v1(manifest_value)
    receipt = _mapping(value, label="matrix task0 receipt")
    _validate_hash(receipt, field="task0_receipt_sha256", label="matrix task0 receipt")
    runtime = _mapping(
        receipt.get("runtime_authority"), label="matrix task0 runtime authority"
    )
    _validate_hash(
        runtime,
        field="runtime_authority_sha256",
        label="matrix task0 runtime authority",
    )
    retained_manifest_identity = _identity(
        manifest_identity, label="expected task0 manifest"
    )
    if (
        receipt.get("schema_version") != TASK0_SCHEMA
        or receipt.get("manifest_identity") != retained_manifest_identity
        or receipt.get("manifest_sha256") != manifest["manifest_sha256"]
        or receipt.get("source_task_ordinal") != 0
        or receipt.get("task_binding_sha256")
        != manifest["tasks"][0]["task_binding_sha256"]
        or receipt.get("matrix_shape")
        != [manifest["tasks"][0]["candidate_count"], DISCOVERY_WORLD_COUNT]
        or receipt.get("matrix_dtype") != MATRIX_DTYPE.str
        or receipt.get("runtime_authority_sha256")
        != runtime["runtime_authority_sha256"]
        or runtime.get("schema_version") != RUNTIME_AUTHORITY_SCHEMA
        or runtime.get("runtime_mode") != "task0"
        or runtime.get("project_id") != PROJECT_ID
        or runtime.get("region") != REGION
        or runtime.get("job_name") != JOB_NAME
        or runtime.get("execution_id") != expected_execution_id
        or runtime.get("source_task_ordinal") != 0
        or runtime.get("task_count") != 1
        or runtime.get("scientific_task_count") != TASK_COUNT
        or runtime.get("task_attempt") != 0
        or runtime.get("manifest_sha256") != manifest["manifest_sha256"]
        or runtime.get("code_sha") != manifest["code_sha"]
        or runtime.get("immutable_image") != manifest["immutable_image"]
        or runtime.get("build_id") != manifest["build_id"]
        or runtime.get("task0_execution_id") != "none"
        or runtime.get("task0_gate_sha256") != "none"
        or runtime.get("outcomes_allowed") is not False
        or type(receipt.get("local_materialization_sha256")) is not str
        or _SHA.fullmatch(str(receipt.get("local_materialization_sha256"))) is None
        or type(receipt.get("matrix_sha256")) is not str
        or _SHA.fullmatch(str(receipt.get("matrix_sha256"))) is None
        or receipt.get("publication_performed") is not False
        or receipt.get("task0_storage_adapter_write_api_present") is not False
        or receipt.get("service_account") != SERVICE_ACCOUNT
        or receipt.get("service_account_write_capability_absence_asserted")
        is not False
        or receipt.get("ambient_service_account_write_capability_restricted")
        is not False
        or receipt.get("write_boundary_is_adapter_not_iam") is not True
        or receipt.get("write_api_invoked") is not False
        or receipt.get("full_cohort_execution_launched") is not False
        or receipt.get("mechanical_launch_gate_passed") is not True
        or receipt.get("r4_body_read") is not False
        or receipt.get("complete") is not True
        or any(receipt.get(key) != expected for key, expected in _policy().items())
    ):
        _fail("matrix task0 receipt differs")
    return receipt


def build_task_result_v1(
    *,
    manifest_value: object,
    local_materialization_value: object,
    matrix_identity: Mapping[str, object],
    runtime_authority: Mapping[str, object],
) -> dict[str, object]:
    manifest = validate_manifest_v1(manifest_value)
    local = _mapping(local_materialization_value, label="local matrix")
    _validate_hash(local, field="local_materialization_sha256", label="local matrix")
    ordinal = local.get("source_task_ordinal")
    if type(ordinal) is not int or not 0 <= ordinal < TASK_COUNT:
        _fail("published task ordinal differs")
    task = _mapping(manifest["tasks"][ordinal], label="published matrix task")
    identity = _identity(matrix_identity, label="published matrix")
    runtime = _mapping(runtime_authority, label="matrix runtime authority")
    _validate_hash(
        runtime, field="runtime_authority_sha256", label="matrix runtime authority"
    )
    if (
        runtime.get("schema_version") != RUNTIME_AUTHORITY_SCHEMA
        or runtime.get("runtime_mode") != "task"
        or runtime.get("project_id") != PROJECT_ID
        or runtime.get("region") != REGION
        or runtime.get("job_name") != JOB_NAME
        or type(runtime.get("execution_id")) is not str
        or _EXECUTION.fullmatch(str(runtime.get("execution_id"))) is None
        or runtime.get("source_task_ordinal") != ordinal
        or runtime.get("task_count") != TASK_COUNT
        or runtime.get("scientific_task_count") != TASK_COUNT
        or runtime.get("task_attempt") != 0
        or runtime.get("manifest_sha256") != manifest["manifest_sha256"]
        or runtime.get("code_sha") != manifest["code_sha"]
        or runtime.get("immutable_image") != manifest["immutable_image"]
        or runtime.get("build_id") != manifest["build_id"]
        or type(runtime.get("task0_execution_id")) is not str
        or _EXECUTION.fullmatch(str(runtime.get("task0_execution_id"))) is None
        or type(runtime.get("task0_gate_sha256")) is not str
        or _SHA.fullmatch(str(runtime.get("task0_gate_sha256"))) is None
        or runtime.get("outcomes_allowed") is not False
    ):
        _fail("matrix runtime authority differs")
    if (
        local.get("manifest_sha256") != manifest["manifest_sha256"]
        or local.get("task_binding_sha256") != task["task_binding_sha256"]
        or identity["uri"] != task["matrix_uri"]
        or identity["sha256"] != local.get("matrix_sha256")
        or identity["bytes"] != local.get("matrix_bytes")
        or local.get("publication_performed") is not False
        or local.get("r4_body_read") is not False
    ):
        _fail("published matrix differs from local materialization")
    lineage = {
        "candidate_artifact_identity": task["candidate_artifact_identity"],
        "candidate_artifact_sha256": task["candidate_artifact_sha256"],
        "candidate_count": task["candidate_count"],
        "ordered_candidate_ids_sha256": task["ordered_candidate_ids_sha256"],
        "discovery_world_artifacts": [
            {"block": row["block"], "identity": row["identity"]}
            for row in task["discovery_world_artifacts"]
        ],
        "discovery_world_identity_manifest_sha256": task[
            "discovery_world_identity_manifest_sha256"
        ],
        "heldout_world_artifact": task["heldout_world_artifact"],
        "scoring_law": task["scoring_law"],
        "matrix_shape": local["matrix_shape"],
        "matrix_dtype": local["matrix_dtype"],
        "matrix_body_sha256": local["matrix_body_sha256"],
    }
    body = {
        "schema_version": TASK_RESULT_SCHEMA,
        "manifest_sha256": manifest["manifest_sha256"],
        "source_task_ordinal": ordinal,
        "task_id": task["task_id"],
        "slate": task["slate"],
        "task_binding_sha256": task["task_binding_sha256"],
        "runtime_authority": runtime,
        "runtime_authority_sha256": runtime["runtime_authority_sha256"],
        "matrix_identity": identity,
        "matrix_lineage": lineage,
        "matrix_lineage_sha256": canonical_sha256(lineage),
        "matrix_published_create_once": True,
        "matrix_exact_reopened_after_publication": True,
        "r4_body_read": False,
        "complete": True,
        **_policy(),
    }
    return _with_hash(body, field="task_result_sha256")


def validate_task_result_v1(
    value: object, *, manifest_value: object, expected_ordinal: int,
) -> dict[str, object]:
    manifest = validate_manifest_v1(manifest_value)
    result = _mapping(value, label="matrix task result")
    _validate_hash(result, field="task_result_sha256", label="matrix task result")
    if type(expected_ordinal) is not int or not 0 <= expected_ordinal < TASK_COUNT:
        _fail("expected matrix task ordinal differs")
    task = _mapping(manifest["tasks"][expected_ordinal], label="expected task")
    identity = _identity(result.get("matrix_identity"), label="task matrix")
    lineage = _mapping(result.get("matrix_lineage"), label="matrix lineage")
    expected_lineage = {
        "candidate_artifact_identity": task["candidate_artifact_identity"],
        "candidate_artifact_sha256": task["candidate_artifact_sha256"],
        "candidate_count": task["candidate_count"],
        "ordered_candidate_ids_sha256": task["ordered_candidate_ids_sha256"],
        "discovery_world_artifacts": [
            {"block": row["block"], "identity": row["identity"]}
            for row in task["discovery_world_artifacts"]
        ],
        "discovery_world_identity_manifest_sha256": task[
            "discovery_world_identity_manifest_sha256"
        ],
        "heldout_world_artifact": task["heldout_world_artifact"],
        "scoring_law": task["scoring_law"],
        "matrix_shape": [task["candidate_count"], DISCOVERY_WORLD_COUNT],
        "matrix_dtype": MATRIX_DTYPE.str,
        "matrix_body_sha256": lineage.get("matrix_body_sha256"),
    }
    runtime = _mapping(result.get("runtime_authority"), label="task runtime authority")
    _validate_hash(
        runtime, field="runtime_authority_sha256", label="task runtime authority"
    )
    if (
        result.get("schema_version") != TASK_RESULT_SCHEMA
        or result.get("manifest_sha256") != manifest["manifest_sha256"]
        or result.get("source_task_ordinal") != expected_ordinal
        or result.get("task_id") != task["task_id"]
        or result.get("slate") != task["slate"]
        or result.get("task_binding_sha256") != task["task_binding_sha256"]
        or runtime.get("schema_version") != RUNTIME_AUTHORITY_SCHEMA
        or runtime.get("runtime_mode") != "task"
        or runtime.get("project_id") != PROJECT_ID
        or runtime.get("region") != REGION
        or runtime.get("job_name") != JOB_NAME
        or type(runtime.get("execution_id")) is not str
        or _EXECUTION.fullmatch(str(runtime.get("execution_id"))) is None
        or runtime.get("source_task_ordinal") != expected_ordinal
        or runtime.get("task_count") != TASK_COUNT
        or runtime.get("scientific_task_count") != TASK_COUNT
        or runtime.get("task_attempt") != 0
        or runtime.get("manifest_sha256") != manifest["manifest_sha256"]
        or runtime.get("code_sha") != manifest["code_sha"]
        or runtime.get("immutable_image") != manifest["immutable_image"]
        or runtime.get("build_id") != manifest["build_id"]
        or type(runtime.get("task0_execution_id")) is not str
        or _EXECUTION.fullmatch(str(runtime.get("task0_execution_id"))) is None
        or type(runtime.get("task0_gate_sha256")) is not str
        or _SHA.fullmatch(str(runtime.get("task0_gate_sha256"))) is None
        or runtime.get("outcomes_allowed") is not False
        or result.get("runtime_authority_sha256")
        != runtime["runtime_authority_sha256"]
        or identity["uri"] != task["matrix_uri"]
        or lineage != expected_lineage
        or type(lineage.get("matrix_body_sha256")) is not str
        or _SHA.fullmatch(str(lineage.get("matrix_body_sha256"))) is None
        or result.get("matrix_lineage_sha256") != canonical_sha256(lineage)
        or result.get("matrix_published_create_once") is not True
        or result.get("matrix_exact_reopened_after_publication") is not True
        or result.get("r4_body_read") is not False
        or result.get("complete") is not True
        or any(result.get(key) != value for key, value in _policy().items())
    ):
        _fail(f"matrix task result[{expected_ordinal}] differs")
    return result


def build_terminal_v1(
    *,
    manifest_value: object,
    manifest_identity: Mapping[str, object],
    task_results: Sequence[Mapping[str, object]],
    task_result_identities: Sequence[Mapping[str, object]],
    provider_execution_receipt: Mapping[str, object],
) -> dict[str, object]:
    manifest = validate_manifest_v1(manifest_value)
    retained_manifest_identity = _identity(manifest_identity, label="matrix manifest")
    if (
        retained_manifest_identity["uri"]
        != f"{manifest['output_prefix']}manifest.json"
        or retained_manifest_identity["sha256"] != canonical_sha256(manifest)
        or retained_manifest_identity["bytes"] != len(canonical_json_bytes(manifest))
    ):
        _fail("matrix manifest identity differs")
    raw_results = _sequence(task_results, label="matrix task results")
    raw_identities = _sequence(task_result_identities, label="task result identities")
    if len(raw_results) != TASK_COUNT or len(raw_identities) != TASK_COUNT:
        _fail("matrix terminal task census differs")
    rows = []
    registry = []
    for ordinal, (raw_result, raw_identity) in enumerate(
        zip(raw_results, raw_identities, strict=True)
    ):
        result = validate_task_result_v1(
            raw_result, manifest_value=manifest, expected_ordinal=ordinal
        )
        identity = _identity(raw_identity, label=f"task result[{ordinal}]")
        raw = canonical_json_bytes(result)
        if (
            identity["uri"] != manifest["tasks"][ordinal]["task_result_uri"]
            or identity["sha256"] != sha256(raw).hexdigest()
            or identity["bytes"] != len(raw)
        ):
            _fail(f"task result identity[{ordinal}] differs")
        rows.append({
            "source_task_ordinal": ordinal,
            "task_result_identity": identity,
            "task_result_sha256": result["task_result_sha256"],
            "matrix_identity": result["matrix_identity"],
            "matrix_lineage_sha256": result["matrix_lineage_sha256"],
            "runtime_authority_sha256": result["runtime_authority_sha256"],
        })
        lineage = _mapping(result["matrix_lineage"], label="terminal lineage")
        registry.append({
            "source_task_ordinal": ordinal,
            "slate": result["slate"],
            "matrix_identity": result["matrix_identity"],
            "candidate_artifact_identity": lineage["candidate_artifact_identity"],
            "candidate_ids_sha256": lineage["ordered_candidate_ids_sha256"],
            "source_world_artifact_identities": [
                row["identity"] for row in lineage["discovery_world_artifacts"]
            ],
            "source_world_artifact_manifest_sha256": lineage[
                "discovery_world_identity_manifest_sha256"
            ],
            "block_order": list(DISCOVERY_BLOCKS),
            "worlds_per_block": WORLDS_PER_BLOCK,
            "world_count": DISCOVERY_WORLD_COUNT,
            "dtype": MATRIX_DTYPE.str,
            "scoring_law_id": SCORING_LAW_ID,
            "r4_heldout_identity": lineage["heldout_world_artifact"]["identity"],
            "r4_heldout_not_read": True,
            "matrix_lineage_sha256": result["matrix_lineage_sha256"],
            "matrix_body_sha256": lineage["matrix_body_sha256"],
        })
    execution_ids = {
        _mapping(result, label="terminal result runtime")["runtime_authority"][
            "execution_id"
        ]
        for result in raw_results
    }
    if len(execution_ids) != 1:
        _fail("matrix terminal execution identity differs")
    task0_bindings = {
        (
            _mapping(result, label="terminal result task0 binding")[
                "runtime_authority"
            ]["task0_execution_id"],
            _mapping(result, label="terminal result task0 binding")[
                "runtime_authority"
            ]["task0_gate_sha256"],
        )
        for result in raw_results
    }
    if len(task0_bindings) != 1:
        _fail("matrix terminal task0 predecessor binding differs")
    execution_id = next(iter(execution_ids))
    provider_receipt = validate_provider_execution_receipt_v1(
        provider_execution_receipt,
        expected_execution_id=execution_id,
        expected_mode="task",
        expected_task_count=TASK_COUNT,
        expected_payload_identity=retained_manifest_identity,
        manifest_value=manifest,
    )
    task0_execution_id, task0_gate_sha256 = next(iter(task0_bindings))
    if (
        provider_receipt["task0_execution_id"] != task0_execution_id
        or provider_receipt["task0_gate_sha256"] != task0_gate_sha256
    ):
        _fail("matrix provider/task task0 predecessor binding differs")
    body = {
        "schema_version": TERMINAL_SCHEMA,
        "run_id": manifest["run_id"],
        "manifest_identity": retained_manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "candidate_authority_root_identity": manifest[
            "candidate_authority_root_identity"
        ],
        "later_source_freeze_identity": manifest["later_source_freeze_identity"],
        "task_count": TASK_COUNT,
        "execution_id": execution_id,
        "provider_execution_receipt": provider_receipt,
        "provider_execution_sha256": provider_receipt[
            "provider_execution_sha256"
        ],
        "task0_execution_id": task0_execution_id,
        "task0_gate_sha256": task0_gate_sha256,
        "task_results": rows,
        "task_result_manifest_sha256": canonical_sha256(rows),
        "matrix_registry": registry,
        "matrix_registry_sha256": canonical_sha256(registry),
        "scoring_law": _scoring_law(),
        "r4_heldout_bound_but_not_read": True,
        "every_matrix_candidate_and_parent_lineage_bound": True,
        "root_published_last": True,
        "consumer_must_deep_reopen_terminal": True,
        "complete": True,
        **_policy(),
    }
    return _with_hash(body, field="terminal_sha256")


def validate_matrix_file_v1(
    *, path: Path, identity_value: object, candidate_ids: Sequence[str],
    task_binding_value: object,
) -> dict[str, object]:
    path = Path(path)
    identity = _identity(identity_value, label="matrix file")
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        _fail("matrix reopen path differs")
    if path.stat().st_size != identity["bytes"] or _hash_file(path) != identity["sha256"]:
        _fail("matrix reopen exact identity differs")
    with path.open("rb") as handle:
        header_raw = handle.readline(MAX_MATRIX_BYTES)
    if not header_raw.endswith(b"\n"):
        _fail("matrix reopen header delimiter differs")
    header = _parse_canonical(header_raw[:-1], label="matrix reopen header")
    ids = [str(value) for value in candidate_ids]
    task = _mapping(task_binding_value, label="matrix reopen task binding")
    _validate_hash(task, field="task_binding_sha256", label="matrix reopen task")
    expected = {
        "schema_version": MATRIX_ENVELOPE_SCHEMA,
        "candidate_ids": ids,
        "candidate_artifact_identity": task["candidate_artifact_identity"],
        "candidate_ids_sha256": task["ordered_candidate_ids_sha256"],
        "dtype": MATRIX_DTYPE.str,
        "shape": [len(ids), DISCOVERY_WORLD_COUNT],
        "block_order": list(DISCOVERY_BLOCKS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "source_world_artifact_identities": [
            row["identity"] for row in task["discovery_world_artifacts"]
        ],
        "source_world_artifact_manifest_sha256": task[
            "discovery_world_identity_manifest_sha256"
        ],
        "r4_heldout_not_read": True,
    }
    body_bytes = len(ids) * DISCOVERY_WORLD_COUNT * MATRIX_DTYPE.itemsize
    if header != expected or identity["bytes"] != len(header_raw) + body_bytes:
        _fail("matrix reopen envelope differs")
    matrix = np.memmap(
        path, dtype=MATRIX_DTYPE, mode="r", offset=len(header_raw),
        shape=(len(ids), DISCOVERY_WORLD_COUNT), order="C",
    )
    try:
        for start in range(0, len(ids), ROW_CHUNK):
            if not np.isfinite(matrix[start : start + ROW_CHUNK]).all():
                _fail("matrix reopen contains a non-finite value")
    finally:
        del matrix
    return {
        "identity": identity,
        "candidate_count": len(ids),
        "ordered_candidate_ids_sha256": canonical_sha256(ids),
        "shape": expected["shape"],
        "dtype": MATRIX_DTYPE.str,
        "matrix_body_sha256": _hash_file(path, offset=len(header_raw)),
    }


def reopen_terminal_registry_v1(
    *,
    terminal_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> ReopenedPaidSourceDiscoveryMatrixFreezeV1:
    """Deep-open root/manifest/task/candidate lineage without matrix bodies.

    This is the bounded consumer seam.  A downstream worker calls it once,
    selects its one row from ``matrix_registry``, and then exact-fetches only
    that row's matrix.  It never resolves a current object name or lists a
    prefix.
    """

    terminal_raw, retained_terminal_identity = _read_exact(
        terminal_identity, read_exact=read_exact, label="matrix terminal"
    )
    terminal = _parse_canonical(terminal_raw, label="matrix terminal")
    _validate_hash(terminal, field="terminal_sha256", label="matrix terminal")
    manifest_raw, manifest_identity = _read_exact(
        terminal.get("manifest_identity"), read_exact=read_exact,
        label="matrix manifest",
    )
    manifest = validate_manifest_v1(
        _parse_canonical(manifest_raw, label="matrix manifest")
    )
    execution_id = terminal.get("execution_id")
    provider_receipt = validate_provider_execution_receipt_v1(
        terminal.get("provider_execution_receipt"),
        expected_execution_id=str(execution_id),
        expected_mode="task",
        expected_task_count=TASK_COUNT,
        expected_payload_identity=manifest_identity,
        manifest_value=manifest,
    )
    if (
        terminal.get("schema_version") != TERMINAL_SCHEMA
        or terminal.get("run_id") != manifest["run_id"]
        or terminal.get("manifest_sha256") != manifest["manifest_sha256"]
        or terminal.get("candidate_authority_root_identity")
        != manifest["candidate_authority_root_identity"]
        or terminal.get("later_source_freeze_identity")
        != manifest["later_source_freeze_identity"]
        or terminal.get("task_count") != TASK_COUNT
        or terminal.get("provider_execution_sha256")
        != provider_receipt["provider_execution_sha256"]
        or terminal.get("task0_execution_id")
        != provider_receipt["task0_execution_id"]
        or terminal.get("task0_gate_sha256")
        != provider_receipt["task0_gate_sha256"]
        or terminal.get("scoring_law") != _scoring_law()
        or terminal.get("r4_heldout_bound_but_not_read") is not True
        or terminal.get("every_matrix_candidate_and_parent_lineage_bound") is not True
        or terminal.get("root_published_last") is not True
        or terminal.get("consumer_must_deep_reopen_terminal") is not True
        or terminal.get("complete") is not True
        or any(terminal.get(key) != value for key, value in _policy().items())
    ):
        _fail("matrix terminal fields differ")
    rows = _sequence(terminal.get("task_results"), label="terminal tasks")
    registry = _sequence(
        terminal.get("matrix_registry"), label="terminal matrix registry"
    )
    if (
        len(rows) != TASK_COUNT
        or len(registry) != TASK_COUNT
        or terminal.get("task_result_manifest_sha256") != canonical_sha256(rows)
        or terminal.get("matrix_registry_sha256") != canonical_sha256(registry)
    ):
        _fail("matrix terminal manifests differ")
    candidate_reopens = []
    for ordinal, (raw_row, raw_registry) in enumerate(
        zip(rows, registry, strict=True)
    ):
        row = _mapping(raw_row, label=f"terminal task[{ordinal}]")
        registry_row = _mapping(
            raw_registry, label=f"terminal matrix registry[{ordinal}]"
        )
        result_raw, result_identity = _read_exact(
            row.get("task_result_identity"), read_exact=read_exact,
            label=f"task result[{ordinal}]",
        )
        result = validate_task_result_v1(
            _parse_canonical(result_raw, label=f"task result[{ordinal}]"),
            manifest_value=manifest,
            expected_ordinal=ordinal,
        )
        if (
            row.get("source_task_ordinal") != ordinal
            or row.get("task_result_sha256") != result["task_result_sha256"]
            or row.get("matrix_identity") != result["matrix_identity"]
            or row.get("matrix_lineage_sha256") != result["matrix_lineage_sha256"]
            or result_identity != row.get("task_result_identity")
            or row.get("runtime_authority_sha256")
            != result["runtime_authority_sha256"]
            or result["runtime_authority"]["execution_id"] != execution_id
            or result["runtime_authority"]["task0_execution_id"]
            != terminal["task0_execution_id"]
            or result["runtime_authority"]["task0_gate_sha256"]
            != terminal["task0_gate_sha256"]
        ):
            _fail(f"terminal task lineage[{ordinal}] differs")
        lineage = _mapping(result["matrix_lineage"], label="reopened lineage")
        expected_registry = {
            "source_task_ordinal": ordinal,
            "slate": result["slate"],
            "matrix_identity": result["matrix_identity"],
            "candidate_artifact_identity": lineage["candidate_artifact_identity"],
            "candidate_ids_sha256": lineage["ordered_candidate_ids_sha256"],
            "source_world_artifact_identities": [
                item["identity"] for item in lineage["discovery_world_artifacts"]
            ],
            "source_world_artifact_manifest_sha256": lineage[
                "discovery_world_identity_manifest_sha256"
            ],
            "block_order": list(DISCOVERY_BLOCKS),
            "worlds_per_block": WORLDS_PER_BLOCK,
            "world_count": DISCOVERY_WORLD_COUNT,
            "dtype": MATRIX_DTYPE.str,
            "scoring_law_id": SCORING_LAW_ID,
            "r4_heldout_identity": lineage["heldout_world_artifact"]["identity"],
            "r4_heldout_not_read": True,
            "matrix_lineage_sha256": result["matrix_lineage_sha256"],
            "matrix_body_sha256": lineage["matrix_body_sha256"],
        }
        if registry_row != expected_registry:
            _fail(f"terminal matrix registry[{ordinal}] differs")
        candidate_raw, _ = _read_exact(
            manifest["tasks"][ordinal]["candidate_artifact_identity"],
            read_exact=read_exact,
            label=f"candidate artifact[{ordinal}]",
        )
        candidate = source.validate_accepted_candidate_artifact_v1(
            _parse_canonical(candidate_raw, label=f"candidate artifact[{ordinal}]")
        )
        candidate_ids = [str(item["candidate_id"]) for item in candidate["rows"]]
        if (
            candidate.get("candidate_artifact_sha256")
            != lineage["candidate_artifact_sha256"]
            or candidate.get("candidate_count") != lineage["candidate_count"]
            or candidate.get("ordered_candidate_ids_sha256")
            != lineage["ordered_candidate_ids_sha256"]
            or canonical_sha256(candidate_ids)
            != lineage["ordered_candidate_ids_sha256"]
        ):
            _fail(f"candidate lineage[{ordinal}] differs")
        candidate_reopens.append({
            "source_task_ordinal": ordinal,
            "candidate_artifact_identity": lineage["candidate_artifact_identity"],
            "candidate_ids_sha256": lineage["ordered_candidate_ids_sha256"],
        })
    receipt = _with_hash({
        "schema_version": REGISTRY_REOPEN_SCHEMA,
        "terminal_identity": retained_terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "task_count": TASK_COUNT,
        "construction_execution_id": terminal["execution_id"],
        "construction_provider_execution_sha256": terminal[
            "provider_execution_sha256"
        ],
        "candidate_reopens": candidate_reopens,
        "candidate_reopen_manifest_sha256": canonical_sha256(candidate_reopens),
        "matrix_registry_sha256": terminal["matrix_registry_sha256"],
        "all_task_results_generation_exact_reopened": True,
        "all_candidate_orders_generation_exact_reopened": True,
        "matrix_bodies_read": False,
        "r4_body_read": False,
        "bounded_consumer_registry_reopen": True,
        "complete": True,
        **_policy(),
    }, field="registry_reopen_sha256")
    return ReopenedPaidSourceDiscoveryMatrixFreezeV1(
        terminal=terminal,
        terminal_identity=retained_terminal_identity,
        manifest=manifest,
        manifest_identity=manifest_identity,
        matrix_registry=tuple(
            _mapping(row, label=f"consumer matrix registry[{ordinal}]")
            for ordinal, row in enumerate(registry)
        ),
        reopen_receipt=receipt,
    )


def reopen_terminal_v1(
    *,
    terminal_identity: Mapping[str, object],
    read_exact: ReadExact,
    fetch_exact_to_file: FetchExactToFile,
    workspace: Path,
) -> dict[str, object]:
    """Locally audit every matrix body without producing a release terminal.

    The authoritative reopen terminal is emitted only by
    :func:`collect_reopen_tasks_v1`, where all 54 task runtime authorities and
    the provider-observed execution receipt are available.
    """

    reopened_root = reopen_terminal_registry_v1(
        terminal_identity=terminal_identity,
        read_exact=read_exact,
    )
    terminal = reopened_root.terminal
    manifest = reopened_root.manifest
    retained_terminal_identity = reopened_root.terminal_identity
    manifest_identity = reopened_root.manifest_identity
    rows = _sequence(terminal.get("task_results"), label="terminal tasks")
    workspace = Path(workspace)
    if not workspace.is_absolute() or workspace.is_symlink():
        _fail("matrix reopen workspace differs")
    workspace.mkdir(parents=True, exist_ok=True)
    matrix_reopens = []
    for ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"terminal task[{ordinal}]")
        result_raw, _ = _read_exact(
            row.get("task_result_identity"), read_exact=read_exact,
            label=f"task result[{ordinal}] matrix reopen",
        )
        result = validate_task_result_v1(
            _parse_canonical(
                result_raw, label=f"task result[{ordinal}] matrix reopen"
            ),
            manifest_value=manifest,
            expected_ordinal=ordinal,
        )
        candidate_raw, _ = _read_exact(
            manifest["tasks"][ordinal]["candidate_artifact_identity"],
            read_exact=read_exact,
            label=f"candidate artifact[{ordinal}] matrix reopen",
        )
        candidate = source.validate_accepted_candidate_artifact_v1(
            _parse_canonical(
                candidate_raw, label=f"candidate artifact[{ordinal}] matrix reopen"
            )
        )
        candidate_ids = [str(item["candidate_id"]) for item in candidate["rows"]]
        matrix_path = workspace / f"matrix-{ordinal:02d}.bin"
        if matrix_path.exists() or matrix_path.is_symlink():
            _fail("matrix reopen destination already exists")
        try:
            fetch_exact_to_file(result["matrix_identity"], matrix_path)
            reopened = validate_matrix_file_v1(
                path=matrix_path,
                identity_value=result["matrix_identity"],
                candidate_ids=candidate_ids,
                task_binding_value=manifest["tasks"][ordinal],
            )
            if (
                reopened["matrix_body_sha256"]
                != result["matrix_lineage"]["matrix_body_sha256"]
            ):
                _fail(f"matrix body lineage[{ordinal}] differs")
            matrix_reopens.append({
                "source_task_ordinal": ordinal,
                "matrix_identity": result["matrix_identity"],
                "matrix_body_sha256": reopened["matrix_body_sha256"],
            })
        finally:
            if matrix_path.exists() and matrix_path.is_file():
                matrix_path.unlink()
    body = {
        "schema_version": LOCAL_REOPEN_AUDIT_SCHEMA,
        "terminal_identity": retained_terminal_identity,
        "terminal_sha256": terminal["terminal_sha256"],
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "task_count": TASK_COUNT,
        "matrix_reopens": matrix_reopens,
        "matrix_reopen_manifest_sha256": canonical_sha256(matrix_reopens),
        "registry_reopen_sha256": reopened_root.reopen_receipt[
            "registry_reopen_sha256"
        ],
        "all_task_results_generation_exact_reopened": True,
        "all_matrix_bytes_generation_exact_reopened": True,
        "all_candidate_orders_replayed": True,
        "all_parent_lineages_replayed": True,
        "r4_body_read": False,
        "bounded_one_slate_reopen": True,
        "provider_execution_bound": False,
        "publishable_as_reopen_terminal": False,
        "complete": True,
        **_policy(),
    }
    return _with_hash(body, field="reopen_sha256")


def reopen_matrix_task_v1(
    *,
    reopened_root: ReopenedPaidSourceDiscoveryMatrixFreezeV1,
    source_task_ordinal: int,
    read_exact: ReadExact,
    fetch_exact_to_file: FetchExactToFile,
    destination: Path,
    runtime_authority: Mapping[str, object],
) -> dict[str, object]:
    """Deep-open one matrix body for a 54-way independent reopen cohort."""

    if not isinstance(reopened_root, ReopenedPaidSourceDiscoveryMatrixFreezeV1):
        _fail("matrix reopen root differs")
    if (
        type(source_task_ordinal) is not int
        or not 0 <= source_task_ordinal < TASK_COUNT
    ):
        _fail("matrix reopen task ordinal differs")
    registry = reopened_root.matrix_registry[source_task_ordinal]
    if registry.get("source_task_ordinal") != source_task_ordinal:
        _fail("matrix reopen registry order differs")
    task = _mapping(
        reopened_root.manifest["tasks"][source_task_ordinal],
        label="matrix reopen task binding",
    )
    runtime = _mapping(runtime_authority, label="matrix reopen runtime authority")
    _validate_hash(
        runtime,
        field="runtime_authority_sha256",
        label="matrix reopen runtime authority",
    )
    if (
        runtime.get("schema_version") != RUNTIME_AUTHORITY_SCHEMA
        or runtime.get("runtime_mode") != "reopen-task"
        or runtime.get("project_id") != PROJECT_ID
        or runtime.get("region") != REGION
        or runtime.get("job_name") != JOB_NAME
        or type(runtime.get("execution_id")) is not str
        or _EXECUTION.fullmatch(str(runtime.get("execution_id"))) is None
        or runtime.get("source_task_ordinal") != source_task_ordinal
        or runtime.get("task_count") != TASK_COUNT
        or runtime.get("scientific_task_count") != TASK_COUNT
        or runtime.get("task_attempt") != 0
        or runtime.get("manifest_sha256")
        != reopened_root.manifest["manifest_sha256"]
        or runtime.get("code_sha") != reopened_root.manifest["code_sha"]
        or runtime.get("immutable_image")
        != reopened_root.manifest["immutable_image"]
        or runtime.get("build_id") != reopened_root.manifest["build_id"]
        or runtime.get("task0_execution_id") != "none"
        or runtime.get("task0_gate_sha256") != "none"
        or runtime.get("outcomes_allowed") is not False
    ):
        _fail("matrix reopen runtime authority differs")
    candidate_raw, _ = _read_exact(
        registry["candidate_artifact_identity"], read_exact=read_exact,
        label=f"candidate artifact[{source_task_ordinal}] body reopen",
    )
    candidate = source.validate_accepted_candidate_artifact_v1(
        _parse_canonical(
            candidate_raw,
            label=f"candidate artifact[{source_task_ordinal}] body reopen",
        )
    )
    candidate_ids = [str(row["candidate_id"]) for row in candidate["rows"]]
    destination = Path(destination)
    if (
        not destination.is_absolute()
        or destination.exists()
        or destination.is_symlink()
    ):
        _fail("matrix body reopen destination differs")
    try:
        fetch_exact_to_file(registry["matrix_identity"], destination)
        reopened = validate_matrix_file_v1(
            path=destination,
            identity_value=registry["matrix_identity"],
            candidate_ids=candidate_ids,
            task_binding_value=task,
        )
        if reopened["matrix_body_sha256"] != registry["matrix_body_sha256"]:
            _fail("matrix body reopen lineage differs")
    finally:
        if destination.exists() and destination.is_file():
            destination.unlink()
    body = {
        "schema_version": REOPEN_TASK_SCHEMA,
        "terminal_identity": reopened_root.terminal_identity,
        "terminal_sha256": reopened_root.terminal["terminal_sha256"],
        "manifest_sha256": reopened_root.manifest["manifest_sha256"],
        "source_task_ordinal": source_task_ordinal,
        "construction_execution_id": reopened_root.terminal["execution_id"],
        "reopen_execution_id": runtime["execution_id"],
        "matrix_identity": registry["matrix_identity"],
        "matrix_body_sha256": registry["matrix_body_sha256"],
        "matrix_registry_entry_sha256": canonical_sha256(registry),
        "runtime_authority": runtime,
        "runtime_authority_sha256": runtime["runtime_authority_sha256"],
        "generation_exact_matrix_body_reopened": True,
        "r4_body_read": False,
        "bounded_one_slate_reopen": True,
        "complete": True,
        **_policy(),
    }
    return _with_hash(body, field="reopen_task_sha256")


def collect_reopen_tasks_v1(
    *,
    reopened_root: ReopenedPaidSourceDiscoveryMatrixFreezeV1,
    task_receipts: Sequence[Mapping[str, object]],
    task_receipt_identities: Sequence[Mapping[str, object]],
    provider_execution_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Collect 54 exact per-slate reopen receipts into one root-last proof."""

    if not isinstance(reopened_root, ReopenedPaidSourceDiscoveryMatrixFreezeV1):
        _fail("matrix reopen root differs")
    receipts = _sequence(task_receipts, label="matrix reopen task receipts")
    identities = _sequence(
        task_receipt_identities, label="matrix reopen task receipt identities"
    )
    if len(receipts) != TASK_COUNT or len(identities) != TASK_COUNT:
        _fail("matrix reopen task census differs")
    rows = []
    execution_ids: set[str] = set()
    for ordinal, (raw_receipt, raw_identity) in enumerate(
        zip(receipts, identities, strict=True)
    ):
        receipt = _mapping(raw_receipt, label=f"matrix reopen receipt[{ordinal}]")
        _validate_hash(
            receipt, field="reopen_task_sha256",
            label=f"matrix reopen receipt[{ordinal}]",
        )
        identity = _identity(
            raw_identity, label=f"matrix reopen receipt identity[{ordinal}]"
        )
        registry = reopened_root.matrix_registry[ordinal]
        runtime = _mapping(
            receipt.get("runtime_authority"),
            label=f"matrix reopen runtime authority[{ordinal}]",
        )
        _validate_hash(
            runtime,
            field="runtime_authority_sha256",
            label=f"matrix reopen runtime authority[{ordinal}]",
        )
        raw = canonical_json_bytes(receipt)
        if (
            receipt.get("schema_version") != REOPEN_TASK_SCHEMA
            or receipt.get("terminal_identity") != reopened_root.terminal_identity
            or receipt.get("terminal_sha256")
            != reopened_root.terminal["terminal_sha256"]
            or receipt.get("manifest_sha256")
            != reopened_root.manifest["manifest_sha256"]
            or receipt.get("source_task_ordinal") != ordinal
            or receipt.get("construction_execution_id")
            != reopened_root.terminal["execution_id"]
            or receipt.get("reopen_execution_id") != runtime.get("execution_id")
            or receipt.get("matrix_identity") != registry["matrix_identity"]
            or receipt.get("matrix_body_sha256")
            != registry["matrix_body_sha256"]
            or receipt.get("matrix_registry_entry_sha256")
            != canonical_sha256(registry)
            or receipt.get("runtime_authority_sha256")
            != runtime.get("runtime_authority_sha256")
            or runtime.get("schema_version") != RUNTIME_AUTHORITY_SCHEMA
            or runtime.get("runtime_mode") != "reopen-task"
            or runtime.get("project_id") != PROJECT_ID
            or runtime.get("region") != REGION
            or runtime.get("job_name") != JOB_NAME
            or type(runtime.get("execution_id")) is not str
            or _EXECUTION.fullmatch(str(runtime.get("execution_id"))) is None
            or runtime.get("source_task_ordinal") != ordinal
            or runtime.get("task_count") != TASK_COUNT
            or runtime.get("scientific_task_count") != TASK_COUNT
            or runtime.get("task_attempt") != 0
            or runtime.get("manifest_sha256")
            != reopened_root.manifest["manifest_sha256"]
            or runtime.get("code_sha") != reopened_root.manifest["code_sha"]
            or runtime.get("immutable_image")
            != reopened_root.manifest["immutable_image"]
            or runtime.get("build_id") != reopened_root.manifest["build_id"]
            or runtime.get("task0_execution_id") != "none"
            or runtime.get("task0_gate_sha256") != "none"
            or runtime.get("outcomes_allowed") is not False
            or receipt.get("generation_exact_matrix_body_reopened") is not True
            or receipt.get("r4_body_read") is not False
            or receipt.get("bounded_one_slate_reopen") is not True
            or receipt.get("complete") is not True
            or any(receipt.get(key) != value for key, value in _policy().items())
            or identity["sha256"] != sha256(raw).hexdigest()
            or identity["bytes"] != len(raw)
            or identity["uri"]
            != reopened_root.manifest["tasks"][ordinal]["reopen_task_uri"]
        ):
            _fail(f"matrix reopen receipt[{ordinal}] differs")
        execution_ids.add(str(runtime.get("execution_id")))
        rows.append({
            "source_task_ordinal": ordinal,
            "reopen_execution_id": runtime["execution_id"],
            "reopen_task_identity": identity,
            "reopen_task_sha256": receipt["reopen_task_sha256"],
            "matrix_identity": registry["matrix_identity"],
            "matrix_body_sha256": registry["matrix_body_sha256"],
            "runtime_authority_sha256": runtime["runtime_authority_sha256"],
        })
    if len(execution_ids) != 1:
        _fail("matrix reopen execution identity differs")
    execution_id = next(iter(execution_ids))
    if execution_id == reopened_root.terminal.get("execution_id"):
        _fail("matrix reopen execution must differ from matrix construction")
    provider_receipt = validate_provider_execution_receipt_v1(
        provider_execution_receipt,
        expected_execution_id=execution_id,
        expected_mode="reopen-task",
        expected_task_count=TASK_COUNT,
        expected_payload_identity=reopened_root.terminal_identity,
        manifest_value=reopened_root.manifest,
    )
    body = {
        "schema_version": REOPEN_SCHEMA,
        "terminal_identity": reopened_root.terminal_identity,
        "terminal_sha256": reopened_root.terminal["terminal_sha256"],
        "manifest_identity": reopened_root.manifest_identity,
        "manifest_sha256": reopened_root.manifest["manifest_sha256"],
        "task_count": TASK_COUNT,
        "execution_id": execution_id,
        "construction_execution_id": reopened_root.terminal["execution_id"],
        "reopen_execution_id": execution_id,
        "provider_execution_receipt": provider_receipt,
        "provider_execution_sha256": provider_receipt[
            "provider_execution_sha256"
        ],
        "matrix_reopens": rows,
        "matrix_reopen_manifest_sha256": canonical_sha256(rows),
        "registry_reopen_sha256": reopened_root.reopen_receipt[
            "registry_reopen_sha256"
        ],
        "all_task_results_generation_exact_reopened": True,
        "all_matrix_bytes_generation_exact_reopened": True,
        "all_candidate_orders_replayed": True,
        "all_parent_lineages_replayed": True,
        "r4_body_read": False,
        "bounded_54_way_one_slate_reopen": True,
        "complete": True,
        **_policy(),
    }
    return _with_hash(body, field="reopen_sha256")


__all__ = [
    "CANDIDATE_ROOT_IDENTITY",
    "CorpusR6PaidSourceDiscoveryMatrixFreezeV1Error",
    "DISCOVERY_BLOCKS",
    "DISCOVERY_WORLD_COUNT",
    "HELDOUT_BLOCK",
    "LATER_SOURCE_FREEZE_IDENTITY",
    "LOCAL_REOPEN_AUDIT_SCHEMA",
    "MANIFEST_SCHEMA",
    "MATRIX_DTYPE",
    "MATRIX_ENVELOPE_SCHEMA",
    "MAX_MATRIX_BYTES",
    "OUTPUT_PREFIX",
    "PROVIDER_EXECUTION_SCHEMA",
    "REGISTRY_REOPEN_SCHEMA",
    "REOPEN_SCHEMA",
    "REOPEN_TASK_SCHEMA",
    "ReopenedPaidSourceDiscoveryMatrixFreezeV1",
    "RUNTIME_AUTHORITY_SCHEMA",
    "SCORING_LAW_ID",
    "TASK0_GATE_SCHEMA",
    "TASK0_SCHEMA",
    "TASK_COUNT",
    "TASK_RESULT_SCHEMA",
    "TERMINAL_SCHEMA",
    "WORLD_BLOCKS",
    "WORLDS_PER_BLOCK",
    "build_task0_receipt_v1",
    "build_task_matrix_file_v1",
    "build_task_result_v1",
    "build_terminal_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "collect_reopen_tasks_v1",
    "prepare_manifest_v1",
    "reopen_terminal_registry_v1",
    "reopen_matrix_task_v1",
    "reopen_terminal_v1",
    "validate_manifest_v1",
    "validate_matrix_file_v1",
    "validate_provider_execution_receipt_v1",
    "validate_task0_gate_v1",
    "validate_task0_receipt_v1",
    "validate_task_result_v1",
]
