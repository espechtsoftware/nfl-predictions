#!/usr/bin/env python3
"""Default-off transport for the frozen corpus parametric batch.

This module owns transport and publication only.  A worker cannot construct a
cloud client or import the score-producing core until both the literal
``--execute`` flag and ``CORPUS_PARAMETRIC_RESEARCH_ENABLED=1`` are present.
Cloud Run launch, execution-name recovery, watching, and terminal acceptance
remain separate operator actions; no function here invokes Cloud Run.

Canonical GCS objects are authoritative.  The worker writes only create-once
objects, never lists a bucket, never reads outcomes, and never writes a graph.
An operator-side finisher accepts a task only after strict Cloud Run terminal
success, complete solver-evidence publication, and the independent raw-byte
verifier all pass.  Batch completion is separate and requires every task.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Final, Protocol


PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
EXPECTED_CODE_REPOSITORY: Final = (
    "https://github.com/espechtsoftware/nfl-predictions.git"
)
ENABLE_ENV: Final = "CORPUS_PARAMETRIC_RESEARCH_ENABLED"
IMAGE_ENV: Final = "CORPUS_PARAMETRIC_IMAGE"
BUILD_ENV: Final = "CORPUS_PARAMETRIC_BUILD_ID"
CODE_ENV: Final = "CODE_SHA"
PARKED_COMMAND: Final = ["python"]
PARKED_ARGS: Final = ["scripts/run_corpus_parametric_transport.py", "parked"]
EXPECTED_TASK_COUNT: Final = 1
EXPECTED_PARALLELISM: Final = 1
EXPECTED_MAX_RETRIES: Final = 0
EXPECTED_TIMEOUT_SECONDS: Final = "86400s"
EXPECTED_RESOURCES: Final = {"cpu": "8000m", "memory": "32Gi"}
COMMON_LAW_BODY_ROLES: Final = (
    "code_source",
    "world_schedule",
    "objective",
    "generator_families",
    "unique_fill",
    "deduplication",
    "admission",
    "cbwu",
    "selector",
    "line_194",
    "exact_80",
)
AUTHORITY_OBJECT_ROLES: Final = (
    "source_binding",
    "registered_law",
    "attempt_ledger",
    "matrix_authority",
    "content_task_evidence_root",
    "published_task_evidence_root",
    "draft_authority_bundle",
    "authority_bundle",
    "batch_result",
)
TRANSPORT_CONTRACT_SCHEMA: Final = "corpus-parametric-transport-contract/v1"
PREFIX_CLAIM_SCHEMA: Final = "corpus-parametric-transport-prefix-claim/v1"
LAUNCH_INTENT_SCHEMA: Final = "corpus-parametric-transport-launch-intent/v1"
LAUNCH_LEDGER_SCHEMA: Final = "corpus-parametric-transport-launch-ledger/v1"
EXECUTION_NAME_SCHEMA: Final = (
    "corpus-parametric-transport-execution-name-ledger/v1"
)
WORKER_COMPLETION_SCHEMA: Final = "corpus-parametric-worker-completion/v1"
TASK_ACCEPTANCE_SCHEMA: Final = "corpus-parametric-task-acceptance/v1"
BATCH_ACCEPTANCE_SCHEMA: Final = "corpus-parametric-batch-acceptance/v1"
RETRIEVAL_PREREQUISITE_SCHEMA: Final = (
    "corpus-retrieval-task0-accepted-prerequisite/v1"
)
TASK_TERMINAL_SCHEMA: Final = "corpus-legal-feasibility-task-terminal/v1"
MAX_JSON_BYTES: Final = 512 * 1024 * 1024
EXECUTION_NAME_WAIT_SECONDS: Final = 900

_SHA = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_BUILD = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_GENERATION = re.compile(r"[1-9][0-9]*")
_ID = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?")
_JOB = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")
_EXECUTION = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")
_SERVICE_ACCOUNT = re.compile(
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,61}"
    r"[a-z0-9]\.iam\.gserviceaccount\.com"
)
_IMAGE = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


class CorpusParametricTransportError(RuntimeError):
    """The governed parametric transport failed closed."""


@dataclass(frozen=True, slots=True)
class ObjectIdentity:
    uri: str
    generation: str
    sha256: str
    bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "generation": self.generation,
            "sha256": self.sha256,
            "bytes": self.bytes,
        }


class ObjectStore(Protocol):
    def read(self, identity: Mapping[str, object]) -> bytes: ...

    def publish(
        self, uri: str, raw: bytes, media_type: str = "application/json"
    ) -> dict[str, object]: ...

    def publish_or_reopen(
        self, uri: str, raw: bytes, media_type: str = "application/json"
    ) -> dict[str, object]: ...

    def resolve_current(self, uri: str) -> tuple[dict[str, object], bytes]: ...

    def inventory(self, prefix: str) -> list[dict[str, object]]: ...


def canonical_json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusParametricTransportError("value is not canonical JSON") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _reject_constant(value: str) -> object:
    raise CorpusParametricTransportError(f"non-finite JSON constant {value!r}")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CorpusParametricTransportError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def strict_json_bytes(raw: bytes, *, label: str) -> object:
    if type(raw) is not bytes or not raw or len(raw) > MAX_JSON_BYTES:
        raise CorpusParametricTransportError(f"{label} bytes are absent/oversized")
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusParametricTransportError(f"{label} is not strict JSON") from exc
    if canonical_json_bytes(value) != raw:
        raise CorpusParametricTransportError(f"{label} is not canonical JSON")
    return value


def external_json_bytes(raw: bytes, *, label: str) -> object:
    if type(raw) is not bytes or not raw or len(raw) > MAX_JSON_BYTES:
        raise CorpusParametricTransportError(f"{label} bytes are absent/oversized")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusParametricTransportError(f"{label} is not JSON") from exc


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusParametricTransportError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if type(value) not in (list, tuple):
        raise CorpusParametricTransportError(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    if frozenset(value) != expected:
        raise CorpusParametricTransportError(f"{label} fields differ")


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        raise CorpusParametricTransportError(f"{label} must be a nonempty string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CorpusParametricTransportError(
            f"{label} must be an integer >= {minimum}"
        )
    return value


def _finite_float(value: object, *, label: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise CorpusParametricTransportError(f"{label} must be a finite float")
    return value


def _sha(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _SHA.fullmatch(result) is None:
        raise CorpusParametricTransportError(f"{label} must be SHA-256")
    return result


def _timestamp(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _UTC.fullmatch(result) is None:
        raise CorpusParametricTransportError(f"{label} must be UTC second precision")
    try:
        datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise CorpusParametricTransportError(f"{label} is not a UTC timestamp") from exc
    return result


def _gcs_uri(value: object, *, label: str, prefix: bool = False) -> str:
    result = _string(value, label=label)
    tail = result.removeprefix("gs://")
    bucket, marker, name = tail.partition("/")
    if (
        not result.startswith("gs://")
        or not bucket
        or not marker
        or not name
        or "//" in name
        or any(token in result for token in ("\\", "?", "#", "\0"))
        or (prefix and not result.endswith("/"))
        or (not prefix and result.endswith("/"))
    ):
        raise CorpusParametricTransportError(f"{label} must be a canonical GCS URI")
    return result


def object_identity(value: object, *, label: str) -> ObjectIdentity:
    item = _mapping(value, label=label)
    _exact_keys(
        item, frozenset({"uri", "generation", "sha256", "bytes"}), label=label
    )
    generation = _string(item["generation"], label=f"{label}.generation")
    if _GENERATION.fullmatch(generation) is None:
        raise CorpusParametricTransportError(f"{label}.generation differs")
    return ObjectIdentity(
        uri=_gcs_uri(item["uri"], label=f"{label}.uri"),
        generation=generation,
        sha256=_sha(item["sha256"], label=f"{label}.sha256"),
        bytes=_integer(item["bytes"], label=f"{label}.bytes", minimum=1),
    )


def identity_for_bytes(*, uri: str, generation: str, raw: bytes) -> ObjectIdentity:
    return object_identity(
        {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        label="constructed identity",
    )


def _self_hash(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in body:
        raise CorpusParametricTransportError("self-hash field already exists")
    return {**body, field: canonical_sha256(body)}


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> None:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: value[key] for key in value if key != field}
    if retained != canonical_sha256(body):
        raise CorpusParametricTransportError(f"{label} self-hash differs")


def _write_once(path: Path, raw: bytes) -> None:
    if not isinstance(path, Path) or path.exists() or path.is_symlink():
        raise CorpusParametricTransportError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except OSError as exc:
        raise CorpusParametricTransportError(f"cannot create output {path}") from exc


def _load_json(path: Path, *, label: str) -> object:
    if path.is_symlink() or not path.is_file():
        raise CorpusParametricTransportError(f"{label} file is absent/unsafe")
    return strict_json_bytes(path.read_bytes(), label=label)


def require_execute_gate(*, execute: bool, environ: Mapping[str, str]) -> None:
    if execute is not True:
        raise CorpusParametricTransportError("literal --execute is required")
    if environ.get(ENABLE_ENV) != "1":
        raise CorpusParametricTransportError(f"{ENABLE_ENV}=1 is required")


def _modules() -> tuple[object, object, object, object]:
    from nfl_dfs.research import corpus_batch_evidence_contract as evidence
    from nfl_dfs.research import corpus_legal_feasibility as core
    from nfl_dfs.research import corpus_legal_feasibility_verifier as verifier
    from nfl_dfs.research import corpus_parametric_batch as batch

    return batch, evidence, core, verifier


def _retrieval_module() -> object:
    """Import the frozen retrieval validator only after the execution gate.

    Callers reach this seam only while reopening an already generation-pinned
    task-0 prerequisite.  Keeping the import lazy preserves the parked/default-
    off command's no-science-import property and gives tests a narrow seam for
    exercising the outer semantic binding without constructing 50,000-world
    fixtures.
    """
    from nfl_dfs.research import corpus_retrieval_engine as retrieval

    return retrieval


def _identity_matches_raw(identity: ObjectIdentity, raw: bytes, *, label: str) -> None:
    if len(raw) != identity.bytes or sha256(raw).hexdigest() != identity.sha256:
        raise CorpusParametricTransportError(f"{label} bytes differ from identity")


def _identity_key(value: object) -> tuple[str, str, str, int]:
    identity = object_identity(value, label="identity key")
    return (identity.uri, identity.generation, identity.sha256, identity.bytes)


def _read_identity(
    storage: ObjectStore, value: object, *, label: str
) -> tuple[ObjectIdentity, bytes]:
    identity = object_identity(value, label=label)
    raw = storage.read(identity.as_dict())
    _identity_matches_raw(identity, raw, label=label)
    return identity, raw


def _image_uri(value: object, *, label: str) -> str:
    item = _mapping(value, label=label)
    _exact_keys(item, frozenset({"uri", "digest"}), label=label)
    uri = _string(item["uri"], label=f"{label}.uri")
    digest = _string(item["digest"], label=f"{label}.digest")
    if (
        not digest.startswith("sha256:")
        or _SHA.fullmatch(digest.removeprefix("sha256:")) is None
        or uri != f"{uri.split('@', 1)[0]}@{digest}"
        or _IMAGE.fullmatch(uri) is None
    ):
        raise CorpusParametricTransportError(f"{label} is not immutable")
    return uri


def _parse_batch_manifest(raw: bytes) -> tuple[object, dict[str, object]]:
    batch, _, _, _ = _modules()
    try:
        parsed = batch.parse_canonical_json_bytes(raw, label="batch manifest")
        manifest = batch.validate_batch_manifest(parsed)
    except Exception as exc:
        raise CorpusParametricTransportError(
            "batch manifest does not satisfy frozen v2"
        ) from exc
    if manifest.get("schema_version") != "corpus-parametric-batch-manifest-v2":
        raise CorpusParametricTransportError("batch manifest is not frozen v2")
    return batch, manifest


def _validate_manifest_identity(
    batch: object,
    manifest: Mapping[str, object],
    identity: ObjectIdentity,
) -> None:
    try:
        normalized = batch.validate_json_identity(
            manifest, identity.as_dict(), label="batch manifest identity"
        )
    except Exception as exc:
        raise CorpusParametricTransportError(
            "batch manifest identity differs"
        ) from exc
    if normalized["uri"] != manifest["manifest_uri"]:
        raise CorpusParametricTransportError("batch manifest URI differs")


_RETRIEVAL_PREREQUISITE_KEYS: Final = frozenset({
    "schema_version",
    "accepted_at_utc",
    "task_index",
    "suite_manifest_identity",
    "snapshot_manifest_identity",
    "task_result_object",
    "terminal_receipt",
    "completion_receipt",
    "accepted",
    "complete_result",
    "partial_result",
    "partial_object_count",
    "every_unique_lineup_scored_in_every_world",
    "generation_pinned_replay",
    "uses_realized_outcomes",
    "corpus_fill_licensed",
    "acceptance_sha256",
})

_RETRIEVAL_TERMINAL_KEYS: Final = frozenset({
    "schema_version",
    "finished_at_utc",
    "execution_contract",
    "prefix_claim",
    "runtime_iam_evidence",
    "launch_intent",
    "launch_ledger",
    "execution_name_ledger",
    "execution",
    "suite_manifest_identity",
    "snapshot_manifest_identity",
    "task_index",
    "task_id",
    "result_object",
    "task_result_sha256",
    "batch_completion",
    "batch_completion_sha256",
    "post_terminal_job",
    "output_inventory_before_terminal",
    "output_inventory_before_terminal_sha256",
    "one_execution",
    "attempt_zero",
    "retry_count",
    "generation_pinned_replay",
    "successful_deployment_remains_parked",
    "uses_realized_outcomes",
    "bigquery_access_licensed",
    "corpus_fill_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "terminal_receipt_sha256",
})

_RETRIEVAL_TERMINAL_GOVERNANCE_FIELDS: Final = (
    "execution_contract",
    "prefix_claim",
    "runtime_iam_evidence",
    "launch_intent",
    "launch_ledger",
    "execution_name_ledger",
)


def validate_retrieval_task0_prerequisite(value: object) -> dict[str, object]:
    """Validate the immutable, accepted retrieval task-0 launch prerequisite.

    This is intentionally a consumer-only schema.  The parametric transport
    cannot construct, replace, reinterpret, or repair retrieval task 0.
    """
    item = dict(_mapping(value, label="retrieval task-0 prerequisite"))
    _exact_keys(
        item,
        _RETRIEVAL_PREREQUISITE_KEYS,
        label="retrieval task-0 prerequisite",
    )
    _validate_self_hash(
        item,
        field="acceptance_sha256",
        label="retrieval task-0 prerequisite",
    )
    if (
        item["schema_version"] != RETRIEVAL_PREREQUISITE_SCHEMA
        or item["task_index"] != 0
        or item["accepted"] is not True
        or item["complete_result"] is not True
        or item["partial_result"] is not False
        or item["partial_object_count"] != 0
        or item["every_unique_lineup_scored_in_every_world"] is not True
        or item["generation_pinned_replay"] is not True
        or item["uses_realized_outcomes"] is not False
        or item["corpus_fill_licensed"] is not False
    ):
        raise CorpusParametricTransportError(
            "retrieval task-0 prerequisite is not complete accepted coverage"
        )
    _timestamp(item["accepted_at_utc"], label="retrieval acceptance timestamp")
    for key in (
        "suite_manifest_identity",
        "snapshot_manifest_identity",
        "task_result_object",
        "terminal_receipt",
        "completion_receipt",
    ):
        object_identity(item[key], label=f"retrieval prerequisite {key}")
    if len({
        _identity_key(item[key])
        for key in (
            "suite_manifest_identity",
            "snapshot_manifest_identity",
            "task_result_object",
            "terminal_receipt",
            "completion_receipt",
        )
    }) != 5:
        raise CorpusParametricTransportError(
            "retrieval prerequisite identities repeat"
        )
    return item


def reopen_retrieval_task0_prerequisite(
    *, storage: ObjectStore, prerequisite_identity: object
) -> tuple[dict[str, object], bytes]:
    """Reopen and semantically replay the immutable retrieval task-0 graph."""
    identity, raw = _read_identity(
        storage,
        prerequisite_identity,
        label="retrieval task-0 prerequisite identity",
    )
    prerequisite = validate_retrieval_task0_prerequisite(
        strict_json_bytes(raw, label="retrieval task-0 prerequisite")
    )
    transitive: dict[str, tuple[ObjectIdentity, bytes]] = {}
    for key in (
        "suite_manifest_identity", "snapshot_manifest_identity",
        "task_result_object", "terminal_receipt", "completion_receipt",
    ):
        transitive[key] = _read_identity(
            storage, prerequisite[key],
            label=f"reopened retrieval prerequisite {key}",
        )
    if identity.as_dict() != object_identity(
        prerequisite_identity, label="retrieval task-0 prerequisite"
    ).as_dict():
        raise CorpusParametricTransportError(
            "retrieval task-0 acceptance identity changed"
        )

    retrieval = _retrieval_module()
    parse = getattr(retrieval, "parse_canonical_json_bytes", None)
    validate_suite = getattr(retrieval, "validate_suite_manifest", None)
    validate_snapshot = getattr(retrieval, "validate_snapshot_manifest", None)
    validate_result = getattr(retrieval, "validate_retrieval_task_result", None)
    validate_completion = getattr(
        retrieval, "validate_retrieval_batch_completion", None
    )
    core_bytes = getattr(retrieval, "canonical_json_bytes", None)
    core_sha = getattr(retrieval, "canonical_sha256", None)
    if not all(callable(value) for value in (
        parse, validate_suite, validate_snapshot, validate_result,
        validate_completion, core_bytes, core_sha,
    )):
        raise CorpusParametricTransportError(
            "retrieval core lacks its frozen replay API"
        )
    try:
        suite_raw = transitive["suite_manifest_identity"][1]
        snapshot_raw = transitive["snapshot_manifest_identity"][1]
        result_raw = transitive["task_result_object"][1]
        completion_raw = transitive["completion_receipt"][1]
        terminal_raw = transitive["terminal_receipt"][1]
        suite = validate_suite(parse(suite_raw, label="retrieval suite"))
        snapshot = validate_snapshot(
            parse(snapshot_raw, label="retrieval snapshot")
        )
        if (
            core_bytes(suite) != suite_raw
            or core_bytes(snapshot) != snapshot_raw
            or len(suite["tasks"]) != 1
            or len(snapshot["tasks"]) != 1
            or suite["tasks"][0]["task_index"] != 0
            or snapshot["tasks"][0]["task_index"] != 0
            or suite["snapshot_manifest_identity"]
            != prerequisite["snapshot_manifest_identity"]
        ):
            raise CorpusParametricTransportError(
                "retrieval prerequisite is not the exact one-task task-0 smoke"
            )
        result_value = parse(result_raw, label="retrieval task result")
        result = validate_result(
            published_result={
                "authority": result_value,
                "object_identity": prerequisite["task_result_object"],
            },
            suite_manifest=suite,
            suite_manifest_identity=prerequisite["suite_manifest_identity"],
            snapshot_manifest=snapshot,
            snapshot_manifest_identity=prerequisite["snapshot_manifest_identity"],
            read_object=storage.read,
            replay=True,
        )
        if core_bytes(result) != result_raw:
            raise CorpusParametricTransportError(
                "retrieval task-result canonical replay differs"
            )
        coverage = _mapping(result["coverage"], label="retrieval result coverage")
        licenses = _mapping(result["licenses"], label="retrieval result licenses")
        if (
            result["task_index"] != 0
            or coverage.get("every_unique_lineup_scored_in_every_world") is not True
            or coverage.get("lineup_world_score_count")
            != coverage.get("unique_lineup_count") * coverage.get("world_count")
            or coverage.get("world_count") != 50_000
            or licenses.get("corpus_fill_authority") is not False
        ):
            raise CorpusParametricTransportError(
                "retrieval task-0 result lacks complete all-world coverage"
            )
        completion_value = parse(
            completion_raw, label="retrieval batch completion"
        )
        completion = validate_completion(
            completion_value,
            suite_manifest=suite,
            suite_manifest_identity=prerequisite["suite_manifest_identity"],
            snapshot_manifest=snapshot,
            snapshot_manifest_identity=prerequisite["snapshot_manifest_identity"],
            published_results=[{
                "authority": result,
                "object_identity": prerequisite["task_result_object"],
            }],
            read_object=storage.read,
        )
        completion_coverage = _mapping(
            completion["coverage"], label="retrieval completion coverage"
        )
        completion_results = _sequence(
            completion["task_results"], label="retrieval completion task results"
        )
        if (
            core_bytes(completion) != completion_raw
            or completion_coverage.get("task_count") != 1
            or completion_coverage.get("all_tasks_complete") is not True
            or len(completion_results) != 1
            or _mapping(
                completion_results[0], label="retrieval completion task result"
            ).get("task_result_object") != prerequisite["task_result_object"]
        ):
            raise CorpusParametricTransportError(
                "retrieval task-0 completion replay is incomplete"
            )

        terminal_value = parse(terminal_raw, label="retrieval terminal receipt")
        terminal = _mapping(terminal_value, label="retrieval terminal receipt")
        _exact_keys(
            terminal, _RETRIEVAL_TERMINAL_KEYS,
            label="retrieval terminal receipt",
        )
        terminal_body = {
            key: terminal[key]
            for key in terminal if key != "terminal_receipt_sha256"
        }
        execution = _mapping(
            terminal["execution"], label="retrieval terminal execution"
        )
        counters = _mapping(
            execution.get("counters"), label="retrieval terminal counters"
        )
        post_job = _mapping(
            terminal["post_terminal_job"], label="retrieval terminal job"
        )
        terminal_inventory = _sequence(
            terminal["output_inventory_before_terminal"],
            label="retrieval terminal inventory",
        )
        inventory_rows: list[dict[str, object]] = []
        for ordinal, raw_row in enumerate(terminal_inventory):
            row = _mapping(raw_row, label=f"retrieval terminal inventory[{ordinal}]")
            _exact_keys(
                row, frozenset({"uri", "generation", "bytes"}),
                label=f"retrieval terminal inventory[{ordinal}]",
            )
            inventory_rows.append({
                "uri": _gcs_uri(row["uri"], label="retrieval inventory URI"),
                "generation": _string(
                    row["generation"], label="retrieval inventory generation"
                ),
                "bytes": _integer(
                    row["bytes"], label="retrieval inventory bytes", minimum=1
                ),
            })
        required_inventory = _inventory_rows([
            prerequisite["suite_manifest_identity"],
            prerequisite["task_result_object"],
            prerequisite["completion_receipt"],
        ])
        if (
            terminal["schema_version"]
            != "corpus-retrieval-transport-terminal/v1"
            or terminal["terminal_receipt_sha256"] != core_sha(terminal_body)
            or terminal["suite_manifest_identity"]
            != prerequisite["suite_manifest_identity"]
            or terminal["snapshot_manifest_identity"]
            != prerequisite["snapshot_manifest_identity"]
            or terminal["result_object"] != prerequisite["task_result_object"]
            or terminal["batch_completion"] != prerequisite["completion_receipt"]
            or terminal["task_index"] != 0
            or terminal["task_id"] != suite["tasks"][0]["task_id"]
            or terminal["task_result_sha256"] != result["task_result_sha256"]
            or terminal["batch_completion_sha256"]
            != completion["batch_completion_sha256"]
            or terminal["output_inventory_before_terminal_sha256"]
            != core_sha(list(terminal_inventory))
            or inventory_rows != sorted(
                inventory_rows, key=lambda row: (row["uri"], row["generation"])
            )
            or len(inventory_rows) != len({
                (row["uri"], row["generation"]) for row in inventory_rows
            })
            or any(row not in inventory_rows for row in required_inventory)
            or terminal["one_execution"] is not True
            or terminal["attempt_zero"] is not True
            or terminal["retry_count"] != 0
            or terminal["generation_pinned_replay"] is not True
            or terminal["successful_deployment_remains_parked"] is not True
            or any(terminal[field] is not False for field in (
                "uses_realized_outcomes", "bigquery_access_licensed",
                "corpus_fill_licensed", "live_policy_access_licensed",
                "production_change_licensed",
            ))
            or execution.get("task_count") != 1
            or execution.get("attempt") != 0
            or execution.get("retry_count") != 0
            or execution.get("state") != "True"
            or counters != {
                "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
            }
            or post_job.get("uid") != execution.get("job_uid")
            or post_job.get("generation") != execution.get("job_generation")
            or post_job.get("observed_generation") != post_job.get("generation")
        ):
            raise CorpusParametricTransportError(
                "retrieval terminal receipt is not exact accepted task-0 success"
            )
        _timestamp(terminal["finished_at_utc"], label="retrieval terminal timestamp")
        for field in _RETRIEVAL_TERMINAL_GOVERNANCE_FIELDS:
            _read_identity(
                storage, terminal[field],
                label=f"retrieval terminal {field}",
            )
    except CorpusParametricTransportError:
        raise
    except Exception as exc:
        raise CorpusParametricTransportError(
            "retrieval task-0 semantic replay failed"
        ) from exc
    return prerequisite, raw


_RUNTIME_IAM_KEYS: Final = frozenset({
    "schema_version",
    "captured_at_utc",
    "project",
    "service_account",
    "input_object_identity_set_sha256",
    "output_prefix",
    "all_input_gets_conditionally_authorized",
    "output_get_create_conditionally_authorized",
    "project_level_roles_absent",
    "object_list_granted",
    "object_delete_granted",
    "bucket_uniform_access",
    "public_access_prevention",
    "iam_evidence_sha256",
})


def validate_runtime_iam_evidence(
    value: object,
    *,
    service_account: str,
    input_identities: Sequence[object],
    output_prefix: str,
) -> dict[str, object]:
    item = dict(_mapping(value, label="runtime IAM evidence"))
    _exact_keys(item, _RUNTIME_IAM_KEYS, label="runtime IAM evidence")
    _validate_self_hash(item, field="iam_evidence_sha256", label="runtime IAM")
    normalized_inputs = sorted(
        [object_identity(row, label="runtime IAM input").as_dict()
         for row in input_identities],
        key=_identity_key,
    )
    if (
        item["schema_version"] != "corpus-parametric-runtime-iam-evidence/v1"
        or item["project"] != PROJECT
        or item["service_account"] != service_account
        or _SERVICE_ACCOUNT.fullmatch(service_account) is None
        or item["input_object_identity_set_sha256"]
        != canonical_sha256(normalized_inputs)
        or item["output_prefix"] != output_prefix
        or item["all_input_gets_conditionally_authorized"] is not True
        or item["output_get_create_conditionally_authorized"] is not True
        or item["project_level_roles_absent"] is not True
        or item["object_list_granted"] is not False
        or item["object_delete_granted"] is not False
        or item["bucket_uniform_access"] is not True
        or item["public_access_prevention"] is not True
    ):
        raise CorpusParametricTransportError(
            "runtime IAM evidence is incomplete or overbroad"
        )
    _timestamp(item["captured_at_utc"], label="runtime IAM timestamp")
    _gcs_uri(item["output_prefix"], label="runtime IAM output", prefix=True)
    return item


def _task_spec(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        task = value["spec"]["template"]["spec"]["template"]["spec"]  # type: ignore[index]
    except (KeyError, TypeError):
        try:
            task = value["spec"]["template"]["spec"]  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise CorpusParametricTransportError("Cloud Run task spec differs") from exc
    return _mapping(task, label="Cloud Run task spec")


def _outer_spec(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        return _mapping(
            value["spec"]["template"]["spec"],  # type: ignore[index]
            label="Cloud Run outer spec",
        )
    except (KeyError, TypeError) as exc:
        raise CorpusParametricTransportError("Cloud Run outer spec differs") from exc


def _container_environment(container: Mapping[str, object]) -> dict[str, str]:
    rows = container.get("env", [])
    if type(rows) is not list or any(
        not isinstance(row, Mapping)
        or frozenset(row) != frozenset({"name", "value"})
        or type(row["name"]) is not str
        or type(row["value"]) is not str
        for row in rows
    ):
        raise CorpusParametricTransportError("job environment differs")
    result = {str(row["name"]): str(row["value"]) for row in rows}
    if len(result) != len(rows):
        raise CorpusParametricTransportError("job environment repeats")
    return result


def job_identity(value: object, *, label: str = "job") -> dict[str, str]:
    item = _mapping(value, label=label)
    metadata = _mapping(item.get("metadata"), label=f"{label}.metadata")
    status = _mapping(item.get("status"), label=f"{label}.status")
    name = _string(metadata.get("name"), label=f"{label}.name")
    if _JOB.fullmatch(name) is None:
        raise CorpusParametricTransportError(f"{label} name differs")
    generation = _string(metadata.get("generation"), label=f"{label}.generation")
    observed = _string(
        status.get("observedGeneration"), label=f"{label}.observedGeneration"
    )
    conditions = status.get("conditions")
    if (
        _GENERATION.fullmatch(generation) is None
        or observed != generation
        or type(conditions) is not list
        or not any(
            isinstance(row, Mapping)
            and row.get("type") == "Ready"
            and row.get("status") == "True"
            for row in conditions
        )
    ):
        raise CorpusParametricTransportError(f"{label} is not reconciled Ready")
    return {
        "name": name,
        "uid": _string(metadata.get("uid"), label=f"{label}.uid"),
        "generation": generation,
        "observed_generation": observed,
        "spec_sha256": canonical_sha256(
            _mapping(item.get("spec"), label=f"{label}.spec")
        ),
    }


def _completion_state(value: Mapping[str, object]) -> str:
    status = _mapping(value.get("status", {}), label="execution.status")
    conditions = status.get("conditions", [])
    if type(conditions) is not list:
        raise CorpusParametricTransportError("execution conditions differ")
    rows = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if not rows:
        return "Unknown"
    if len(rows) != 1 or rows[0].get("status") not in {"Unknown", "True", "False"}:
        raise CorpusParametricTransportError("execution Completed state differs")
    return str(rows[0]["status"])


def execution_census_names(value: object) -> list[str]:
    if type(value) is not list:
        raise CorpusParametricTransportError("execution census differs")
    names: list[str] = []
    for ordinal, row in enumerate(value):
        item = _mapping(row, label=f"execution census[{ordinal}]")
        metadata = _mapping(item.get("metadata"), label="execution metadata")
        name = _string(metadata.get("name"), label="execution census name").rsplit("/", 1)[-1]
        if _EXECUTION.fullmatch(name) is None:
            raise CorpusParametricTransportError("execution census name differs")
        names.append(name)
    if len(names) != len(set(names)):
        raise CorpusParametricTransportError("execution census repeats a name")
    return sorted(names)


def _require_no_active_executions(value: object) -> None:
    if type(value) is not list:
        raise CorpusParametricTransportError("execution census differs")
    for row in value:
        item = _mapping(row, label="execution census row")
        if _completion_state(item) == "Unknown":
            raise CorpusParametricTransportError("active execution forbids launch")


def validate_scheduler_census(
    schedulers: object, *, job_name: str, all_regions_complete: bool
) -> None:
    if all_regions_complete is not True or type(schedulers) is not list:
        raise CorpusParametricTransportError(
            "all-region scheduler census is required"
        )
    needle = f"/jobs/{job_name}:run"
    for row in schedulers:
        item = _mapping(row, label="scheduler census row")
        target = item.get("httpTarget", {})
        if isinstance(target, Mapping) and needle in str(target.get("uri", "")):
            raise CorpusParametricTransportError("scheduler targets reused job")


def validate_build_metadata(
    value: object,
    *,
    build_id: str,
    code_sha: str,
    image: str,
) -> dict[str, str]:
    item = _mapping(value, label="build metadata")
    if (
        _BUILD.fullmatch(build_id) is None
        or _COMMIT.fullmatch(code_sha) is None
        or _IMAGE.fullmatch(image) is None
        or item.get("id") != build_id
        or item.get("status") != "SUCCESS"
    ):
        raise CorpusParametricTransportError("immutable build identity differs")
    try:
        requested = item["source"]["gitSource"]  # type: ignore[index]
        resolved = item["sourceProvenance"]["resolvedGitSource"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise CorpusParametricTransportError("direct-Git provenance is absent") from exc
    if (
        requested.get("revision") != code_sha
        or resolved.get("revision") != code_sha
        or requested.get("url") != EXPECTED_CODE_REPOSITORY
        or resolved.get("url") != EXPECTED_CODE_REPOSITORY
    ):
        raise CorpusParametricTransportError("build source commit differs")
    digest = image.rsplit("@", 1)[1]
    results = item.get("results", {})
    images = results.get("images", []) if isinstance(results, Mapping) else []
    steps = item.get("steps")
    if (
        type(images) is not list
        or not any(isinstance(row, Mapping) and row.get("digest") == digest for row in images)
        or type(steps) is not list
        or not steps
        or any(
            not isinstance(row, Mapping)
            or row.get("status") != "SUCCESS"
            or int(row.get("exitCode", 0) or 0) != 0
            for row in steps
        )
    ):
        raise CorpusParametricTransportError("build image/steps differ")
    return {
        "build_id": build_id,
        "code_repository": EXPECTED_CODE_REPOSITORY,
        "code_sha": code_sha,
        "image": image,
    }


def validate_parked_job(
    value: object,
    *,
    job_name: str,
    expected_uid: str,
    build: Mapping[str, object],
    service_account: str,
) -> dict[str, str]:
    item = _mapping(value, label="parked job")
    identity = job_identity(item, label="parked job")
    outer = _outer_spec(item)
    task = _task_spec(item)
    containers = task.get("containers")
    if type(containers) is not list or len(containers) != 1:
        raise CorpusParametricTransportError("parked container differs")
    container = _mapping(containers[0], label="parked container")
    expected_env = {
        ENABLE_ENV: "1",
        IMAGE_ENV: str(build["image"]),
        BUILD_ENV: str(build["build_id"]),
        CODE_ENV: str(build["code_sha"]),
    }
    if (
        identity["name"] != job_name
        or identity["uid"] != expected_uid
        or _SERVICE_ACCOUNT.fullmatch(service_account) is None
        or outer.get("taskCount") != EXPECTED_TASK_COUNT
        or outer.get("parallelism") != EXPECTED_PARALLELISM
        or task.get("maxRetries") != EXPECTED_MAX_RETRIES
        or task.get("timeoutSeconds") != EXPECTED_TIMEOUT_SECONDS
        or task.get("serviceAccountName") != service_account
        or task.get("volumes", []) != []
        or container.get("image") != build["image"]
        or container.get("command") != PARKED_COMMAND
        or container.get("args") != PARKED_ARGS
        or container.get("volumeMounts", []) != []
        or _container_environment(container) != expected_env
        or _mapping(container.get("resources", {}), label="parked resources").get("limits")
        != EXPECTED_RESOURCES
    ):
        raise CorpusParametricTransportError(
            "job is not the exact default-off parked contract"
        )
    return identity


class GenerationPinnedStorage:
    """GCS implementation with exact-generation reads and create-only writes."""

    def __init__(
        self,
        *,
        execute: bool,
        environ: Mapping[str, str],
        project: str = PROJECT,
    ) -> None:
        require_execute_gate(execute=execute, environ=environ)
        from google.cloud import storage

        self._client = storage.Client(project=project)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        candidate = _gcs_uri(uri, label="GCS object URI")
        return tuple(candidate.removeprefix("gs://").split("/", 1))  # type: ignore[return-value]

    def read(self, value: Mapping[str, object]) -> bytes:
        identity = object_identity(value, label="GCS read identity")
        bucket, name = self._parts(identity.uri)
        blob = self._client.bucket(bucket).blob(
            name, generation=int(identity.generation)
        )
        raw = blob.download_as_bytes(if_generation_match=int(identity.generation))
        _identity_matches_raw(identity, raw, label="GCS read")
        return raw

    def read_generation(self, *, uri: str, generation: str) -> bytes:
        bucket, name = self._parts(uri)
        if _GENERATION.fullmatch(generation) is None:
            raise CorpusParametricTransportError("read generation differs")
        return self._client.bucket(bucket).blob(
            name, generation=int(generation)
        ).download_as_bytes(if_generation_match=int(generation))

    def publish(
        self, uri: str, raw: bytes, media_type: str = "application/json"
    ) -> dict[str, object]:
        _gcs_uri(uri, label="publish URI")
        if type(raw) is not bytes or not raw:
            raise CorpusParametricTransportError("published body must be bytes")
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        blob.upload_from_string(
            raw, content_type=_string(media_type, label="media type"),
            if_generation_match=0,
        )
        generation = _string(blob.generation, label="published generation")
        identity = identity_for_bytes(uri=uri, generation=generation, raw=raw)
        if self.read(identity.as_dict()) != raw:
            raise CorpusParametricTransportError("published object reopen differs")
        return identity.as_dict()

    def resolve_current(self, uri: str) -> tuple[dict[str, object], bytes]:
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        blob.reload()
        generation = _string(blob.generation, label="current generation")
        if _GENERATION.fullmatch(generation) is None:
            raise CorpusParametricTransportError("current generation differs")
        raw = self._client.bucket(bucket).blob(
            name, generation=int(generation)
        ).download_as_bytes(if_generation_match=int(generation))
        if not raw:
            raise CorpusParametricTransportError("current object is empty")
        identity = identity_for_bytes(uri=uri, generation=generation, raw=raw)
        return identity.as_dict(), raw

    def publish_or_reopen(
        self, uri: str, raw: bytes, media_type: str = "application/json"
    ) -> dict[str, object]:
        try:
            return self.publish(uri, raw, media_type)
        except Exception as publish_error:
            try:
                identity, reopened = self.resolve_current(uri)
            except Exception:
                raise CorpusParametricTransportError(
                    "create-once publication cannot be recovered"
                ) from publish_error
            if reopened != raw:
                raise CorpusParametricTransportError(
                    "existing create-once object differs"
                ) from publish_error
            return identity

    def inventory(self, prefix: str) -> list[dict[str, object]]:
        _gcs_uri(prefix, label="inventory prefix", prefix=True)
        bucket, name = prefix.removeprefix("gs://").split("/", 1)
        rows: list[dict[str, object]] = []
        for blob in self._client.list_blobs(bucket, prefix=name, versions=True):
            generation = _string(blob.generation, label="inventory generation")
            if _GENERATION.fullmatch(generation) is None or blob.size is None:
                raise CorpusParametricTransportError("inventory row differs")
            rows.append({
                "uri": f"gs://{bucket}/{blob.name}",
                "generation": generation,
                "bytes": int(blob.size),
            })
        return sorted(rows, key=lambda row: (row["uri"], row["generation"]))


def _manifest_input_identities(
    manifest: Mapping[str, object],
) -> list[dict[str, object]]:
    common = _mapping(manifest["common_law"], label="manifest common law")
    rows: list[dict[str, object]] = []
    for role in COMMON_LAW_BODY_ROLES:
        rows.append(
            object_identity(common[role], label=f"common law {role}").as_dict()
        )
    rows.extend([
        object_identity(
            common["artifact_source_authority_completion"],
            label="artifact source authority completion",
        ).as_dict(),
        object_identity(
            common["effective_policy_inventory_identity"],
            label="effective policy inventory",
        ).as_dict(),
        object_identity(
            _mapping(common["source_receipts"], label="source receipts")[
                "later_source_freeze"
            ],
            label="later source freeze",
        ).as_dict(),
    ])
    for task_index, raw_task in enumerate(
        _sequence(manifest["tasks"], label="manifest tasks")
    ):
        task = _mapping(raw_task, label=f"manifest task[{task_index}]")
        artifacts = _mapping(
            task["world_artifact_receipts"],
            label=f"task[{task_index}] world artifacts",
        )
        for role in sorted(artifacts):
            rows.append(
                object_identity(
                    artifacts[role],
                    label=f"task[{task_index}] {role}",
                ).as_dict()
            )
    by_key = {_identity_key(row): row for row in rows}
    if len(by_key) != len(rows):
        raise CorpusParametricTransportError(
            "manifest source identities repeat"
        )
    return sorted(by_key.values(), key=_identity_key)


def _validate_code_source_build_binding(
    *,
    batch: object,
    raw: bytes,
    identity: ObjectIdentity,
    manifest: Mapping[str, object],
    build: Mapping[str, object],
) -> dict[str, object]:
    try:
        parsed = batch.parse_canonical_json_bytes(raw, label="code source")
    except Exception as exc:
        raise CorpusParametricTransportError("code-source bytes differ") from exc
    item = dict(_mapping(parsed, label="code source"))
    _exact_keys(
        item,
        frozenset({
            "schema",
            "source_commit_sha",
            "cloud_build_id",
            "implementation_sha256",
            "build_definition_sha256",
            "immutable_image",
            "terminal_verification",
        }),
        label="code source",
    )
    expected_identity = object_identity(
        _mapping(manifest["common_law"], label="manifest common law")[
            "code_source"
        ],
        label="manifest code-source identity",
    )
    expected_image = _image_uri(
        _mapping(manifest["common_law"], label="manifest common law")[
            "immutable_image"
        ],
        label="manifest immutable image",
    )
    if (
        identity != expected_identity
        or item["schema"] != "corpus-legal-feasibility-code-source/v1"
        or item["source_commit_sha"] != build["code_sha"]
        or item["cloud_build_id"] != build["build_id"]
        or item["immutable_image"]
        != _mapping(manifest["common_law"], label="manifest common law")[
            "immutable_image"
        ]
        or build["image"] != expected_image
        or item["terminal_verification"] != {
            "authority": "external-terminal-execution-receipt",
            "required": True,
            "verifies": [
                "cloud_build_id",
                "immutable_image",
                "source_commit_sha",
            ],
        }
    ):
        raise CorpusParametricTransportError(
            "code source, image, commit, or build binding differs"
        )
    return item


def _task_transport_paths(task: Mapping[str, object]) -> dict[str, object]:
    prefix = _gcs_uri(
        task["variant_output_prefix"], label="task variant prefix", prefix=True
    )
    transport = f"{prefix}transport/"
    result: dict[str, object] = {
        "task_index": task["task_index"],
        "task_sha256": task["task_sha256"],
        "variant_output_prefix": prefix,
        "result_receipt_uri": task["result_receipt_uri"],
        "science_terminal_uri": f"{prefix}task-terminal.json",
        "producer_close_uri": f"{transport}producer-close.json",
        "independent_verification_uri": (
            f"{transport}independent-verification.json"
        ),
        "accepted_terminal_uri": f"{transport}accepted-terminal.json",
    }
    for phase in ("producer", "verifier"):
        result[f"{phase}_launch_intent_uri"] = (
            f"{transport}{phase}-launch-intent.json"
        )
        result[f"{phase}_launch_ledger_uri"] = (
            f"{transport}{phase}-launch-ledger.json"
        )
        result[f"{phase}_execution_name_uri"] = (
            f"{transport}{phase}-execution-name.json"
        )
        result[f"{phase}_worker_completion_uri"] = (
            f"{transport}{phase}-worker-completion.json"
        )
    return result


def _transport_contract_uri(manifest: Mapping[str, object]) -> str:
    return f"{manifest['output_prefix']}governance/parametric-transport-contract.json"


def _runtime_iam_uri(manifest: Mapping[str, object]) -> str:
    return f"{manifest['output_prefix']}governance/runtime-iam-evidence.json"


def _batch_completion_uri(manifest: Mapping[str, object]) -> str:
    return f"{manifest['output_prefix']}governance/batch-completion.json"


def _batch_acceptance_uri(manifest: Mapping[str, object]) -> str:
    return f"{manifest['output_prefix']}governance/batch-acceptance.json"


def build_prefix_claim(
    *,
    created_at_utc: str,
    manifest: Mapping[str, object],
    manifest_identity: ObjectIdentity,
    evidence_contract_identity: ObjectIdentity,
    retrieval_prerequisite_identity: ObjectIdentity,
    runtime_iam_identity: ObjectIdentity,
    build: Mapping[str, object],
    job: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "schema_version": PREFIX_CLAIM_SCHEMA,
        "created_at_utc": _timestamp(created_at_utc, label="claim timestamp"),
        "batch_manifest_identity": manifest_identity.as_dict(),
        "evidence_contract_identity": evidence_contract_identity.as_dict(),
        "retrieval_task0_prerequisite_identity": (
            retrieval_prerequisite_identity.as_dict()
        ),
        "runtime_iam_evidence_identity": runtime_iam_identity.as_dict(),
        "build": dict(build),
        "job": dict(job),
        "output_prefix": manifest["output_prefix"],
        "create_once": True,
        "uses_realized_outcomes": False,
        "corpus_fill_licensed": False,
        "production_change_licensed": False,
    }
    return _self_hash(body, field="prefix_claim_sha256")


def build_transport_contract(
    *,
    created_at_utc: str,
    manifest: Mapping[str, object],
    manifest_identity: ObjectIdentity,
    evidence_contract_identity: ObjectIdentity,
    retrieval_prerequisite_identity: ObjectIdentity,
    runtime_iam_identity: ObjectIdentity,
    prefix_claim_identity: ObjectIdentity,
    build: Mapping[str, object],
    job: Mapping[str, object],
    service_account: str,
) -> dict[str, object]:
    tasks = [
        _task_transport_paths(_mapping(task, label=f"manifest task[{index}]"))
        for index, task in enumerate(
            _sequence(manifest["tasks"], label="manifest tasks")
        )
    ]
    if len(tasks) not in {1, 54}:
        raise CorpusParametricTransportError(
            "transport requires a one-task smoke or complete 54-task batch"
        )
    batch_mode = "one-task-smoke" if len(tasks) == 1 else "complete-54-task"
    inputs = _manifest_input_identities(manifest)
    body = {
        "schema_version": TRANSPORT_CONTRACT_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="transport contract timestamp"
        ),
        "project": PROJECT,
        "region": REGION,
        "batch_id": manifest["batch_id"],
        "output_prefix": manifest["output_prefix"],
        "batch_manifest_identity": manifest_identity.as_dict(),
        "batch_manifest_sha256": manifest["batch_manifest_sha256"],
        "evidence_contract_identity": evidence_contract_identity.as_dict(),
        "retrieval_task0_prerequisite_identity": (
            retrieval_prerequisite_identity.as_dict()
        ),
        "runtime_iam_evidence_identity": runtime_iam_identity.as_dict(),
        "prefix_claim_identity": prefix_claim_identity.as_dict(),
        "build": dict(build),
        "service_account": service_account,
        "job": dict(job),
        "manifest_input_identity_set_sha256": canonical_sha256(inputs),
        "task_count": len(tasks),
        "batch_mode": batch_mode,
        "matrix_cell_count": len(tasks) * 7,
        "complete_batch_acceptance_required": True,
        "tasks": tasks,
        "cloud_run_task_count": 1,
        "cloud_run_parallelism": 1,
        "max_retries": 0,
        "task_attempt": 0,
        "default_command": PARKED_COMMAND,
        "default_args": PARKED_ARGS,
        "literal_execute_flag_required": True,
        "environment_execute_gate_required": True,
        "producer_and_verifier_separate_executions": True,
        "automatic_retry_licensed": False,
        "create_once": True,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
    }
    return _self_hash(body, field="transport_contract_sha256")


_CONTRACT_KEYS: Final = frozenset({
    "schema_version", "created_at_utc", "project", "region", "batch_id",
    "output_prefix", "batch_manifest_identity", "batch_manifest_sha256",
    "evidence_contract_identity", "retrieval_task0_prerequisite_identity",
    "runtime_iam_evidence_identity", "prefix_claim_identity", "build",
    "service_account", "job", "manifest_input_identity_set_sha256",
    "task_count", "batch_mode", "matrix_cell_count",
    "complete_batch_acceptance_required", "tasks", "cloud_run_task_count",
    "cloud_run_parallelism",
    "max_retries", "task_attempt", "default_command", "default_args",
    "literal_execute_flag_required", "environment_execute_gate_required",
    "producer_and_verifier_separate_executions", "automatic_retry_licensed",
    "create_once", "uses_realized_outcomes", "historical_scoring_licensed",
    "corpus_fill_licensed", "graph_mutation_licensed",
    "production_change_licensed", "transport_contract_sha256",
})


def validate_transport_contract(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="transport contract"))
    _exact_keys(item, _CONTRACT_KEYS, label="transport contract")
    _validate_self_hash(
        item, field="transport_contract_sha256", label="transport contract"
    )
    false_fields = (
        "automatic_retry_licensed",
        "uses_realized_outcomes",
        "historical_scoring_licensed",
        "corpus_fill_licensed",
        "graph_mutation_licensed",
        "production_change_licensed",
    )
    if (
        item["schema_version"] != TRANSPORT_CONTRACT_SCHEMA
        or item["project"] != PROJECT
        or item["region"] != REGION
        or item["cloud_run_task_count"] != 1
        or item["cloud_run_parallelism"] != 1
        or item["max_retries"] != 0
        or item["task_attempt"] != 0
        or item["default_command"] != PARKED_COMMAND
        or item["default_args"] != PARKED_ARGS
        or item["literal_execute_flag_required"] is not True
        or item["environment_execute_gate_required"] is not True
        or item["producer_and_verifier_separate_executions"] is not True
        or item["complete_batch_acceptance_required"] is not True
        or item["create_once"] is not True
        or any(item[key] is not False for key in false_fields)
    ):
        raise CorpusParametricTransportError(
            "transport execution/license law differs"
        )
    _timestamp(item["created_at_utc"], label="contract timestamp")
    _gcs_uri(item["output_prefix"], label="contract output", prefix=True)
    _sha(item["batch_manifest_sha256"], label="contract manifest SHA")
    _sha(
        item["manifest_input_identity_set_sha256"],
        label="contract input-set SHA",
    )
    for key in (
        "batch_manifest_identity",
        "evidence_contract_identity",
        "retrieval_task0_prerequisite_identity",
        "runtime_iam_evidence_identity",
        "prefix_claim_identity",
    ):
        object_identity(item[key], label=f"contract {key}")
    build = _mapping(item["build"], label="contract build")
    _exact_keys(
        build,
        frozenset({"build_id", "code_repository", "code_sha", "image"}),
        label="contract build",
    )
    if (
        _BUILD.fullmatch(str(build["build_id"])) is None
        or build["code_repository"] != EXPECTED_CODE_REPOSITORY
        or _COMMIT.fullmatch(str(build["code_sha"])) is None
        or _IMAGE.fullmatch(str(build["image"])) is None
        or _SERVICE_ACCOUNT.fullmatch(str(item["service_account"])) is None
    ):
        raise CorpusParametricTransportError("contract build/principal differs")
    job = _mapping(item["job"], label="contract job")
    _exact_keys(
        job,
        frozenset({
            "name", "uid", "generation", "observed_generation", "spec_sha256"
        }),
        label="contract job",
    )
    if (
        _JOB.fullmatch(str(job["name"])) is None
        or job["generation"] != job["observed_generation"]
        or _GENERATION.fullmatch(str(job["generation"])) is None
    ):
        raise CorpusParametricTransportError("contract job differs")
    _sha(job["spec_sha256"], label="contract job spec SHA")
    tasks = _sequence(item["tasks"], label="contract tasks")
    if (
        item["task_count"] != len(tasks)
        or len(tasks) not in {1, 54}
        or item["batch_mode"]
        != ("one-task-smoke" if len(tasks) == 1 else "complete-54-task")
        or item["matrix_cell_count"] != len(tasks) * 7
    ):
        raise CorpusParametricTransportError("contract task count differs")
    for index, raw_task in enumerate(tasks):
        task = _mapping(raw_task, label=f"contract task[{index}]")
        if task.get("task_index") != index:
            raise CorpusParametricTransportError("contract task order differs")
        _sha(task.get("task_sha256"), label=f"contract task[{index}] SHA")
        prefix = _gcs_uri(
            task.get("variant_output_prefix"),
            label=f"contract task[{index}] prefix",
            prefix=True,
        )
        for key, uri in task.items():
            if key.endswith("_uri"):
                retained = _gcs_uri(uri, label=f"contract task[{index}] {key}")
                if key != "result_receipt_uri" and not retained.startswith(prefix):
                    raise CorpusParametricTransportError(
                        "task transport URI is outside task prefix"
                    )
    return item


def _validate_prefix_claim(
    value: object,
    *,
    contract: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="prefix claim"))
    _validate_self_hash(item, field="prefix_claim_sha256", label="prefix claim")
    if (
        item.get("schema_version") != PREFIX_CLAIM_SCHEMA
        or item.get("batch_manifest_identity")
        != contract["batch_manifest_identity"]
        or item.get("evidence_contract_identity")
        != contract["evidence_contract_identity"]
        or item.get("retrieval_task0_prerequisite_identity")
        != contract["retrieval_task0_prerequisite_identity"]
        or item.get("runtime_iam_evidence_identity")
        != contract["runtime_iam_evidence_identity"]
        or item.get("build") != contract["build"]
        or item.get("job") != contract["job"]
        or item.get("output_prefix") != contract["output_prefix"]
        or item.get("create_once") is not True
        or item.get("uses_realized_outcomes") is not False
        or item.get("corpus_fill_licensed") is not False
        or item.get("production_change_licensed") is not False
    ):
        raise CorpusParametricTransportError("prefix claim binding differs")
    return item


def _inventory_rows(identities: Sequence[object]) -> list[dict[str, object]]:
    rows = []
    for value in identities:
        identity = object_identity(value, label="inventory identity")
        rows.append({
            "uri": identity.uri,
            "generation": identity.generation,
            "bytes": identity.bytes,
        })
    return sorted(rows, key=lambda row: (row["uri"], row["generation"]))


def _require_exact_inventory(
    storage: ObjectStore,
    *,
    prefix: str,
    identities: Sequence[object],
    label: str,
) -> None:
    expected = _inventory_rows(identities)
    observed = storage.inventory(prefix)
    if observed != expected:
        raise CorpusParametricTransportError(f"{label} inventory differs")


def _require_inventory_allowing_current(
    storage: ObjectStore,
    *,
    prefix: str,
    identities: Sequence[object],
    optional_uris: Sequence[str],
    label: str,
) -> dict[str, dict[str, object]]:
    """Require exact versions, permitting at most one current known finisher URI."""
    expected = _inventory_rows(identities)
    observed = storage.inventory(prefix)
    retained: dict[str, dict[str, object]] = {}
    for raw_uri in optional_uris:
        uri = _gcs_uri(raw_uri, label=f"{label} optional URI")
        matching = [row for row in observed if row.get("uri") == uri]
        if not matching:
            continue
        if len(matching) != 1:
            raise CorpusParametricTransportError(
                f"{label} optional URI has multiple generations"
            )
        identity_raw, raw = _resolve_current_required(
            storage, uri, label=f"{label} optional object"
        )
        identity = object_identity(identity_raw, label=f"{label} optional identity")
        _identity_matches_raw(identity, raw, label=f"{label} optional object")
        row = _inventory_rows([identity.as_dict()])[0]
        if matching[0] != row:
            raise CorpusParametricTransportError(
                f"{label} optional current generation differs"
            )
        expected.append(row)
        retained[uri] = identity.as_dict()
    expected.sort(key=lambda row: (row["uri"], row["generation"]))
    if observed != expected:
        raise CorpusParametricTransportError(f"{label} inventory differs")
    return retained


def configure_transport(
    *,
    storage: ObjectStore,
    batch_manifest_identity: object,
    evidence_contract_identity: object,
    retrieval_prerequisite_identity: object,
    runtime_iam_evidence_raw: bytes,
    build_metadata: object,
    build_id: str,
    code_sha: str,
    image: str,
    service_account: str,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    created_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Validate and publish the immutable outer transport authority once."""
    require_execute_gate(execute=execute, environ=environ)
    manifest_identity, manifest_raw = _read_identity(
        storage, batch_manifest_identity, label="batch manifest"
    )
    batch, manifest = _parse_batch_manifest(manifest_raw)
    _validate_manifest_identity(batch, manifest, manifest_identity)
    evidence_identity, evidence_raw = _read_identity(
        storage, evidence_contract_identity, label="evidence contract"
    )
    _, evidence, _, _ = _modules()
    try:
        evidence_value = evidence.validate_corpus_batch_evidence_contract_bytes(
            evidence_raw,
            batch_manifest=manifest,
            batch_manifest_identity=manifest_identity.as_dict(),
        )
        evidence.validate_corpus_batch_evidence_contract_identity(
            evidence_value,
            evidence_identity.as_dict(),
            batch_manifest=manifest,
            batch_manifest_identity=manifest_identity.as_dict(),
        )
    except Exception as exc:
        raise CorpusParametricTransportError(
            "evidence contract binding differs"
        ) from exc
    prerequisite_identity = object_identity(
        retrieval_prerequisite_identity,
        label="retrieval task-0 prerequisite identity",
    )
    reopen_retrieval_task0_prerequisite(
        storage=storage, prerequisite_identity=prerequisite_identity.as_dict()
    )
    build = validate_build_metadata(
        build_metadata,
        build_id=build_id,
        code_sha=code_sha,
        image=image,
    )
    code_identity = object_identity(
        _mapping(manifest["common_law"], label="manifest common law")[
            "code_source"
        ],
        label="code-source identity",
    )
    code_raw = storage.read(code_identity.as_dict())
    _identity_matches_raw(code_identity, code_raw, label="code source")
    _validate_code_source_build_binding(
        batch=batch,
        raw=code_raw,
        identity=code_identity,
        manifest=manifest,
        build=build,
    )
    planned_job = job_identity(parked_job, label="planned parked job")
    job = validate_parked_job(
        parked_job,
        job_name=planned_job["name"],
        expected_uid=planned_job["uid"],
        build=build,
        service_account=service_account,
    )
    _require_no_active_executions(executions)
    validate_scheduler_census(
        schedulers,
        job_name=job["name"],
        all_regions_complete=all_regions_complete,
    )
    inputs = _manifest_input_identities(manifest)
    parsed_iam = strict_json_bytes(
        runtime_iam_evidence_raw, label="runtime IAM evidence"
    )
    validate_runtime_iam_evidence(
        parsed_iam,
        service_account=service_account,
        input_identities=inputs,
        output_prefix=str(manifest["output_prefix"]),
    )
    initial_identities: list[object] = [
        manifest_identity.as_dict(), evidence_identity.as_dict()
    ]
    if prerequisite_identity.uri.startswith(str(manifest["output_prefix"])):
        initial_identities.append(prerequisite_identity.as_dict())
    _require_exact_inventory(
        storage,
        prefix=str(manifest["output_prefix"]),
        identities=initial_identities,
        label="preconfigure",
    )
    iam_identity = object_identity(
        storage.publish_or_reopen(
            _runtime_iam_uri(manifest), runtime_iam_evidence_raw
        ),
        label="runtime IAM identity",
    )
    claim = build_prefix_claim(
        created_at_utc=created_at_utc,
        manifest=manifest,
        manifest_identity=manifest_identity,
        evidence_contract_identity=evidence_identity,
        retrieval_prerequisite_identity=prerequisite_identity,
        runtime_iam_identity=iam_identity,
        build=build,
        job=job,
    )
    claim_identity = object_identity(
        storage.publish_or_reopen(
            str(manifest["create_once_prefix_claim_uri"]),
            canonical_json_bytes(claim),
        ),
        label="prefix claim identity",
    )
    contract = build_transport_contract(
        created_at_utc=created_at_utc,
        manifest=manifest,
        manifest_identity=manifest_identity,
        evidence_contract_identity=evidence_identity,
        retrieval_prerequisite_identity=prerequisite_identity,
        runtime_iam_identity=iam_identity,
        prefix_claim_identity=claim_identity,
        build=build,
        job=job,
        service_account=service_account,
    )
    validate_transport_contract(contract)
    contract_identity = object_identity(
        storage.publish_or_reopen(
            _transport_contract_uri(manifest), canonical_json_bytes(contract)
        ),
        label="transport contract identity",
    )
    _require_exact_inventory(
        storage,
        prefix=str(manifest["output_prefix"]),
        identities=[
            *initial_identities,
            iam_identity.as_dict(),
            claim_identity.as_dict(),
            contract_identity.as_dict(),
        ],
        label="configured transport",
    )
    return {
        "schema_version": "corpus-parametric-transport-configured/v1",
        "batch_manifest": manifest_identity.as_dict(),
        "evidence_contract": evidence_identity.as_dict(),
        "retrieval_task0_prerequisite": prerequisite_identity.as_dict(),
        "runtime_iam_evidence": iam_identity.as_dict(),
        "prefix_claim": claim_identity.as_dict(),
        "transport_contract": contract_identity.as_dict(),
        "task_count": len(manifest["tasks"]),
        "batch_mode": contract["batch_mode"],
        "matrix_cell_count": contract["matrix_cell_count"],
        "default_off": True,
        "launch_permitted": False,
    }


def _reopen_contract_graph(
    *,
    storage: ObjectStore,
    contract_identity: object,
) -> tuple[ObjectIdentity, dict[str, object], object, dict[str, object]]:
    retained_contract_identity, contract_raw = _read_identity(
        storage, contract_identity, label="transport contract"
    )
    contract = validate_transport_contract(
        strict_json_bytes(contract_raw, label="transport contract")
    )
    manifest_identity, manifest_raw = _read_identity(
        storage, contract["batch_manifest_identity"], label="batch manifest"
    )
    batch, manifest = _parse_batch_manifest(manifest_raw)
    _validate_manifest_identity(batch, manifest, manifest_identity)
    if (
        contract["batch_manifest_sha256"]
        != manifest["batch_manifest_sha256"]
        or contract["batch_id"] != manifest["batch_id"]
        or contract["output_prefix"] != manifest["output_prefix"]
        or contract["task_count"] != len(manifest["tasks"])
        or contract["tasks"] != [
            _task_transport_paths(_mapping(task, label="manifest task"))
            for task in manifest["tasks"]
        ]
        or contract["manifest_input_identity_set_sha256"]
        != canonical_sha256(_manifest_input_identities(manifest))
    ):
        raise CorpusParametricTransportError(
            "transport contract no longer binds exact manifest"
        )
    evidence_identity, evidence_raw = _read_identity(
        storage, contract["evidence_contract_identity"], label="evidence contract"
    )
    _, evidence, _, _ = _modules()
    try:
        evidence_value = evidence.validate_corpus_batch_evidence_contract_bytes(
            evidence_raw,
            batch_manifest=manifest,
            batch_manifest_identity=manifest_identity.as_dict(),
        )
        evidence.validate_corpus_batch_evidence_contract_identity(
            evidence_value,
            evidence_identity.as_dict(),
            batch_manifest=manifest,
            batch_manifest_identity=manifest_identity.as_dict(),
        )
    except Exception as exc:
        raise CorpusParametricTransportError(
            "reopened evidence contract differs"
        ) from exc
    reopen_retrieval_task0_prerequisite(
        storage=storage,
        prerequisite_identity=contract[
            "retrieval_task0_prerequisite_identity"
        ],
    )
    iam_identity, iam_raw = _read_identity(
        storage, contract["runtime_iam_evidence_identity"], label="runtime IAM"
    )
    validate_runtime_iam_evidence(
        strict_json_bytes(iam_raw, label="runtime IAM evidence"),
        service_account=str(contract["service_account"]),
        input_identities=_manifest_input_identities(manifest),
        output_prefix=str(manifest["output_prefix"]),
    )
    claim_identity, claim_raw = _read_identity(
        storage, contract["prefix_claim_identity"], label="prefix claim"
    )
    _validate_prefix_claim(
        strict_json_bytes(claim_raw, label="prefix claim"), contract=contract
    )
    if (
        evidence_identity.as_dict() != contract["evidence_contract_identity"]
        or iam_identity.as_dict() != contract["runtime_iam_evidence_identity"]
        or claim_identity.as_dict() != contract["prefix_claim_identity"]
    ):
        raise CorpusParametricTransportError("contract authority identity differs")
    code_identity, code_raw = _read_identity(
        storage,
        _mapping(manifest["common_law"], label="manifest common law")[
            "code_source"
        ],
        label="code source",
    )
    _validate_code_source_build_binding(
        batch=batch,
        raw=code_raw,
        identity=code_identity,
        manifest=manifest,
        build=_mapping(contract["build"], label="contract build"),
    )
    return retained_contract_identity, contract, batch, manifest


def _task_contract(
    contract: Mapping[str, object], task_index: int
) -> Mapping[str, object]:
    index = _integer(task_index, label="task index")
    tasks = _sequence(contract["tasks"], label="contract tasks")
    if index >= len(tasks):
        raise CorpusParametricTransportError("task index is outside contract")
    task = _mapping(tasks[index], label=f"contract task[{index}]")
    if task["task_index"] != index:
        raise CorpusParametricTransportError("contract task index differs")
    return task


def _phase(value: object) -> str:
    phase = _string(value, label="execution phase")
    if phase not in {"producer", "verifier"}:
        raise CorpusParametricTransportError("execution phase differs")
    return phase


def _identity_argv(prefix: str, value: object) -> list[str]:
    identity = object_identity(value, label=f"{prefix} identity")
    option = prefix.replace("_", "-")
    return [
        f"--{option}-uri", identity.uri,
        f"--{option}-generation", identity.generation,
        f"--{option}-sha256", identity.sha256,
        f"--{option}-bytes", str(identity.bytes),
    ]


def cloud_worker_args(
    *,
    phase: str,
    contract_identity: object,
    task_index: int,
) -> list[str]:
    retained_phase = _phase(phase)
    return [
        "scripts/run_corpus_parametric_transport.py",
        "execute-task" if retained_phase == "producer" else "verify-task",
        *_identity_argv("contract", contract_identity),
        "--task-index", str(_integer(task_index, label="task index")),
        "--execute",
    ]


def _validate_current_job(
    value: object, *, contract: Mapping[str, object]
) -> dict[str, str]:
    retained = _mapping(contract["job"], label="contract job")
    identity = validate_parked_job(
        value,
        job_name=str(retained["name"]),
        expected_uid=str(retained["uid"]),
        build=_mapping(contract["build"], label="contract build"),
        service_account=str(contract["service_account"]),
    )
    if identity != retained:
        raise CorpusParametricTransportError("current parked job changed")
    return identity


def _resolve_optional(
    storage: ObjectStore, uri: str
) -> tuple[dict[str, object], bytes] | None:
    try:
        return storage.resolve_current(uri)
    except Exception:
        return None


def _resolve_current_required(
    storage: ObjectStore, uri: str, *, label: str
) -> tuple[dict[str, object], bytes]:
    try:
        identity_raw, raw = storage.resolve_current(uri)
        identity = object_identity(identity_raw, label=f"{label} identity")
        _identity_matches_raw(identity, raw, label=label)
    except CorpusParametricTransportError:
        raise
    except Exception as exc:
        raise CorpusParametricTransportError(
            f"{label} is absent or unreadable"
        ) from exc
    return identity.as_dict(), raw


def _publish_consumption_ledger(
    storage: ObjectStore, *, uri: str, raw: bytes
) -> tuple[dict[str, object], bool]:
    try:
        return storage.publish(uri, raw), True
    except Exception as publish_error:
        try:
            identity, reopened = storage.resolve_current(uri)
        except Exception:
            raise CorpusParametricTransportError(
                "one-shot launch ledger cannot be recovered"
            ) from publish_error
        if reopened != raw:
            raise CorpusParametricTransportError(
                "existing launch ledger differs; never relaunch"
            ) from publish_error
        return identity, False


def _validate_launch_intent(
    value: object,
    *,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    task_index: int,
    phase: str,
) -> dict[str, object]:
    item = dict(_mapping(value, label="launch intent"))
    _validate_self_hash(
        item, field="launch_intent_sha256", label="launch intent"
    )
    args = cloud_worker_args(
        phase=phase,
        contract_identity=contract_identity.as_dict(),
        task_index=task_index,
    )
    if (
        item.get("schema_version") != LAUNCH_INTENT_SCHEMA
        or item.get("transport_contract") != contract_identity.as_dict()
        or item.get("retrieval_task0_prerequisite_identity")
        != contract["retrieval_task0_prerequisite_identity"]
        or item.get("task_index") != task_index
        or item.get("phase") != phase
        or item.get("job") != contract["job"]
        or item.get("worker_args") != args
        or item.get("worker_args_sha256") != canonical_sha256(args)
        or item.get("one_execution") is not True
        or item.get("max_retries") != 0
        or item.get("automatic_retry_licensed") is not False
        or item.get("uses_realized_outcomes") is not False
        or item.get("corpus_fill_licensed") is not False
    ):
        raise CorpusParametricTransportError("launch intent binding differs")
    _timestamp(item.get("created_at_utc"), label="launch intent timestamp")
    return item


def _validate_launch_ledger(
    value: object,
    *,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    intent_identity: Mapping[str, object],
    task_index: int,
    phase: str,
) -> dict[str, object]:
    item = dict(_mapping(value, label="launch ledger"))
    _validate_self_hash(
        item, field="launch_ledger_sha256", label="launch ledger"
    )
    names = item.get("execution_names_before")
    if (
        item.get("schema_version") != LAUNCH_LEDGER_SCHEMA
        or item.get("transport_contract") != contract_identity.as_dict()
        or item.get("launch_intent") != intent_identity
        or item.get("retrieval_task0_prerequisite_identity")
        != contract["retrieval_task0_prerequisite_identity"]
        or item.get("task_index") != task_index
        or item.get("phase") != phase
        or item.get("job") != contract["job"]
        or type(names) is not list
        or names != sorted(names)
        or len(names) != len(set(names))
        or item.get("launch_authority_consumed") is not True
        or item.get("one_execution") is not True
        or item.get("automatic_retry_licensed") is not False
        or item.get("uses_realized_outcomes") is not False
    ):
        raise CorpusParametricTransportError("launch ledger binding differs")
    _timestamp(item.get("created_at_utc"), label="launch ledger timestamp")
    return item


def _reopen_phase_launch(
    *,
    storage: ObjectStore,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    task_index: int,
    phase: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    task = _task_contract(contract, task_index)
    intent_identity, intent_raw = _resolve_current_required(
        storage,
        str(task[f"{phase}_launch_intent_uri"]),
        label=f"{phase} launch intent",
    )
    intent = _validate_launch_intent(
        strict_json_bytes(intent_raw, label="launch intent"),
        contract=contract,
        contract_identity=contract_identity,
        task_index=task_index,
        phase=phase,
    )
    ledger_identity, ledger_raw = _resolve_current_required(
        storage,
        str(task[f"{phase}_launch_ledger_uri"]),
        label=f"{phase} launch ledger",
    )
    ledger = _validate_launch_ledger(
        strict_json_bytes(ledger_raw, label="launch ledger"),
        contract=contract,
        contract_identity=contract_identity,
        intent_identity=intent_identity,
        task_index=task_index,
        phase=phase,
    )
    return intent_identity, ledger_identity, ledger


def consume_phase_launch(
    *,
    storage: ObjectStore,
    contract_identity: object,
    task_index: int,
    phase: str,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    created_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Consume one phase authority.  This function never invokes Cloud Run."""
    require_execute_gate(execute=execute, environ=environ)
    retained_phase = _phase(phase)
    retained_contract_identity, contract, _, manifest = _reopen_contract_graph(
        storage=storage, contract_identity=contract_identity
    )
    task = _task_contract(contract, task_index)
    _validate_current_job(parked_job, contract=contract)
    names = execution_census_names(executions)
    _require_no_active_executions(executions)
    validate_scheduler_census(
        schedulers,
        job_name=str(_mapping(contract["job"], label="contract job")["name"]),
        all_regions_complete=all_regions_complete,
    )
    # The prerequisite is deliberately reopened immediately before each phase.
    reopen_retrieval_task0_prerequisite(
        storage=storage,
        prerequisite_identity=contract[
            "retrieval_task0_prerequisite_identity"
        ],
    )
    accepted = _resolve_optional(storage, str(task["accepted_terminal_uri"]))
    if accepted is not None:
        raise CorpusParametricTransportError("accepted task cannot be relaunched")
    retained_ledger = _resolve_optional(
        storage, str(task[f"{retained_phase}_launch_ledger_uri"])
    )
    if retained_ledger is not None:
        _, ledger_identity, _ = _reopen_phase_launch(
            storage=storage,
            contract=contract,
            contract_identity=retained_contract_identity,
            task_index=task_index,
            phase=retained_phase,
        )
        return {
            "schema_version": "corpus-parametric-phase-launch-ready/v1",
            "task_index": task_index,
            "phase": retained_phase,
            "launch_intent": storage.resolve_current(
                str(task[f"{retained_phase}_launch_intent_uri"])
            )[0],
            "launch_ledger": ledger_identity,
            "worker_args": [],
            "launch_permitted": False,
            "launch_authority_consumed": True,
            "automatic_retry_licensed": False,
            "recovery_action": "census-only-never-relaunch",
        }
    if retained_phase == "producer":
        if storage.inventory(str(task["variant_output_prefix"])):
            raise CorpusParametricTransportError(
                "producer task namespace is not pristine"
            )
    else:
        _reopen_producer_close(
            storage=storage,
            contract=contract,
            contract_identity=retained_contract_identity,
            manifest=manifest,
            task_index=task_index,
        )
        if _resolve_optional(storage, str(task["independent_verification_uri"])):
            raise CorpusParametricTransportError(
                "verifier output already exists; never relaunch"
            )
    args = cloud_worker_args(
        phase=retained_phase,
        contract_identity=retained_contract_identity.as_dict(),
        task_index=task_index,
    )
    intent_body = _self_hash({
        "schema_version": LAUNCH_INTENT_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="launch intent timestamp"
        ),
        "transport_contract": retained_contract_identity.as_dict(),
        "retrieval_task0_prerequisite_identity": contract[
            "retrieval_task0_prerequisite_identity"
        ],
        "task_index": task_index,
        "phase": retained_phase,
        "job": contract["job"],
        "worker_args": args,
        "worker_args_sha256": canonical_sha256(args),
        "one_execution": True,
        "max_retries": 0,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "corpus_fill_licensed": False,
    }, field="launch_intent_sha256")
    intent_identity = storage.publish_or_reopen(
        str(task[f"{retained_phase}_launch_intent_uri"]),
        canonical_json_bytes(intent_body),
    )
    _validate_launch_intent(
        intent_body,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase=retained_phase,
    )
    ledger_body = _self_hash({
        "schema_version": LAUNCH_LEDGER_SCHEMA,
        "created_at_utc": intent_body["created_at_utc"],
        "transport_contract": retained_contract_identity.as_dict(),
        "launch_intent": intent_identity,
        "retrieval_task0_prerequisite_identity": contract[
            "retrieval_task0_prerequisite_identity"
        ],
        "task_index": task_index,
        "phase": retained_phase,
        "job": contract["job"],
        "execution_names_before": names,
        "launch_authority_consumed": True,
        "one_execution": True,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
    }, field="launch_ledger_sha256")
    ledger_identity, created = _publish_consumption_ledger(
        storage,
        uri=str(task[f"{retained_phase}_launch_ledger_uri"]),
        raw=canonical_json_bytes(ledger_body),
    )
    _validate_launch_ledger(
        ledger_body,
        contract=contract,
        contract_identity=retained_contract_identity,
        intent_identity=intent_identity,
        task_index=task_index,
        phase=retained_phase,
    )
    return {
        "schema_version": "corpus-parametric-phase-launch-ready/v1",
        "task_index": task_index,
        "phase": retained_phase,
        "launch_intent": intent_identity,
        "launch_ledger": ledger_identity,
        "worker_args": args if created else [],
        "launch_permitted": created,
        "launch_authority_consumed": True,
        "automatic_retry_licensed": False,
        "recovery_action": (
            "invoke-exactly-once-now"
            if created
            else "census-only-never-relaunch"
        ),
    }


def _validate_execution_spec(
    value: object,
    *,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    task_index: int,
    phase: str,
    require_terminal_success: bool,
) -> dict[str, object]:
    item = _mapping(value, label="execution metadata")
    metadata = _mapping(item.get("metadata"), label="execution metadata.identity")
    spec = _mapping(item.get("spec"), label="execution spec")
    status = _mapping(item.get("status", {}), label="execution status")
    full_name = _string(metadata.get("name"), label="execution name")
    execution_id = full_name.rsplit("/", 1)[-1]
    if _EXECUTION.fullmatch(execution_id) is None:
        raise CorpusParametricTransportError("execution name differs")
    job = _mapping(contract["job"], label="contract job")
    labels = _mapping(metadata.get("labels"), label="execution labels")
    if (
        labels.get("run.googleapis.com/job") != job["name"]
        or labels.get("run.googleapis.com/jobUid") != job["uid"]
        or str(labels.get("run.googleapis.com/jobGeneration"))
        != str(job["generation"])
        or spec.get("taskCount") != 1
        or spec.get("parallelism") != 1
    ):
        raise CorpusParametricTransportError("execution job binding differs")
    task_spec = _mapping(
        _mapping(spec.get("template"), label="execution template").get("spec"),
        label="execution task spec",
    )
    containers = task_spec.get("containers")
    if type(containers) is not list or len(containers) != 1:
        raise CorpusParametricTransportError("execution container differs")
    container = _mapping(containers[0], label="execution container")
    build = _mapping(contract["build"], label="contract build")
    expected_env = {
        ENABLE_ENV: "1",
        IMAGE_ENV: str(build["image"]),
        BUILD_ENV: str(build["build_id"]),
        CODE_ENV: str(build["code_sha"]),
    }
    if (
        task_spec.get("maxRetries") != 0
        or task_spec.get("timeoutSeconds") != EXPECTED_TIMEOUT_SECONDS
        or task_spec.get("serviceAccountName") != contract["service_account"]
        or task_spec.get("volumes", []) != []
        or container.get("image") != build["image"]
        or container.get("command") != PARKED_COMMAND
        or container.get("args") != cloud_worker_args(
            phase=phase,
            contract_identity=contract_identity.as_dict(),
            task_index=task_index,
        )
        or container.get("volumeMounts", []) != []
        or _container_environment(container) != expected_env
        or _mapping(container.get("resources", {}), label="execution resources").get("limits")
        != EXPECTED_RESOURCES
    ):
        raise CorpusParametricTransportError("execution override differs")
    state = _completion_state(item)
    counts = {
        "succeeded": _integer(status.get("succeededCount", 0), label="succeeded"),
        "failed": _integer(status.get("failedCount", 0), label="failed"),
        "cancelled": _integer(status.get("cancelledCount", 0), label="cancelled"),
        "retried": _integer(status.get("retriedCount", 0), label="retried"),
    }
    if require_terminal_success and (
        state != "True"
        or counts != {"succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0}
    ):
        raise CorpusParametricTransportError("execution is not strict terminal success")
    return {
        "execution_id": execution_id,
        "execution_name": full_name,
        "execution_uid": _string(metadata.get("uid"), label="execution UID"),
        "task_index": task_index,
        "phase": phase,
        "state": state,
        "counters": counts,
        "metadata_sha256": canonical_sha256(item),
    }


def _validate_execution_name_ledger(
    value: object,
    *,
    contract_identity: ObjectIdentity,
    launch_ledger_identity: Mapping[str, object],
    runtime: Mapping[str, object],
    task_index: int,
    phase: str,
) -> dict[str, object]:
    item = dict(_mapping(value, label="execution-name ledger"))
    _validate_self_hash(
        item,
        field="execution_name_ledger_sha256",
        label="execution-name ledger",
    )
    if (
        item.get("schema_version") != EXECUTION_NAME_SCHEMA
        or item.get("transport_contract") != contract_identity.as_dict()
        or item.get("launch_ledger") != launch_ledger_identity
        or item.get("task_index") != task_index
        or item.get("phase") != phase
        or item.get("execution_id") != runtime["execution_id"]
        or item.get("execution_name") != runtime["execution_name"]
        or item.get("execution_uid") != runtime["execution_uid"]
        or item.get("execution_metadata_sha256") != runtime["metadata_sha256"]
        or item.get("exactly_one_new_execution") is not True
        or item.get("task_attempt") != 0
        or item.get("max_retries") != 0
        or item.get("automatic_retry_licensed") is not False
    ):
        raise CorpusParametricTransportError(
            "execution-name ledger binding differs"
        )
    _timestamp(item.get("created_at_utc"), label="execution-name timestamp")
    return item


def bind_phase_execution(
    *,
    storage: ObjectStore,
    contract_identity: object,
    task_index: int,
    phase: str,
    execution_metadata: object,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    created_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Census-only launch recovery; never invokes or retries an execution."""
    require_execute_gate(execute=execute, environ=environ)
    retained_phase = _phase(phase)
    retained_contract_identity, contract, _, _ = _reopen_contract_graph(
        storage=storage, contract_identity=contract_identity
    )
    _validate_current_job(parked_job, contract=contract)
    validate_scheduler_census(
        schedulers,
        job_name=str(_mapping(contract["job"], label="contract job")["name"]),
        all_regions_complete=all_regions_complete,
    )
    intent_identity, launch_identity, launch = _reopen_phase_launch(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase=retained_phase,
    )
    del intent_identity
    before = set(_sequence(launch["execution_names_before"], label="names before"))
    after_names = execution_census_names(executions)
    after = set(after_names)
    new = after - before
    if before - after or len(new) != 1:
        raise CorpusParametricTransportError(
            "launch outcome is ambiguous; repeat census only; never relaunch"
        )
    runtime = _validate_execution_spec(
        execution_metadata,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase=retained_phase,
        require_terminal_success=False,
    )
    if runtime["execution_id"] != next(iter(new)):
        raise CorpusParametricTransportError("recovered execution name differs")
    body = _self_hash({
        "schema_version": EXECUTION_NAME_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="execution-name timestamp"
        ),
        "transport_contract": retained_contract_identity.as_dict(),
        "launch_ledger": launch_identity,
        "task_index": task_index,
        "phase": retained_phase,
        "execution_id": runtime["execution_id"],
        "execution_name": runtime["execution_name"],
        "execution_uid": runtime["execution_uid"],
        "execution_metadata_sha256": runtime["metadata_sha256"],
        "exactly_one_new_execution": True,
        "task_attempt": 0,
        "max_retries": 0,
        "automatic_retry_licensed": False,
    }, field="execution_name_ledger_sha256")
    _validate_execution_name_ledger(
        body,
        contract_identity=retained_contract_identity,
        launch_ledger_identity=launch_identity,
        runtime=runtime,
        task_index=task_index,
        phase=retained_phase,
    )
    task = _task_contract(contract, task_index)
    identity = storage.publish_or_reopen(
        str(task[f"{retained_phase}_execution_name_uri"]),
        canonical_json_bytes(body),
    )
    return {
        "schema_version": "corpus-parametric-execution-bound/v1",
        "task_index": task_index,
        "phase": retained_phase,
        "execution_id": runtime["execution_id"],
        "execution_name": runtime["execution_name"],
        "execution_uid": runtime["execution_uid"],
        "execution_name_ledger": identity,
        "automatic_retry_licensed": False,
    }


def recover_phase_execution_name(
    *,
    storage: ObjectStore,
    contract_identity: object,
    task_index: int,
    phase: str,
    executions: object,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Read-only census recovery of the one candidate execution name."""
    require_execute_gate(execute=execute, environ=environ)
    retained_phase = _phase(phase)
    retained_contract_identity, contract, _, _ = _reopen_contract_graph(
        storage=storage, contract_identity=contract_identity
    )
    _, _, launch = _reopen_phase_launch(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase=retained_phase,
    )
    before = set(_sequence(launch["execution_names_before"], label="names before"))
    after = set(execution_census_names(executions))
    new = after - before
    if before - after or len(new) != 1:
        raise CorpusParametricTransportError(
            "execution-name recovery is ambiguous; never relaunch"
        )
    return {
        "schema_version": "corpus-parametric-execution-recovery-candidate/v1",
        "task_index": task_index,
        "phase": retained_phase,
        "execution_id": next(iter(new)),
        "automatic_retry_licensed": False,
        "cloud_call_made": False,
    }


def _runtime_execution(
    environ: Mapping[str, str],
    *,
    contract: Mapping[str, object],
    task_index: int,
    phase: str,
) -> dict[str, object]:
    job = _mapping(contract["job"], label="contract job")
    expected = {
        "CLOUD_RUN_JOB": str(job["name"]),
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
    }
    wrong = {
        key: (environ.get(key), retained)
        for key, retained in expected.items()
        if environ.get(key) != retained
    }
    execution_name = _string(
        environ.get("CLOUD_RUN_EXECUTION"), label="runtime execution name"
    )
    execution_id = execution_name.rsplit("/", 1)[-1]
    qualified_prefix = (
        f"projects/{PROJECT}/locations/{REGION}/jobs/{job['name']}/executions/"
    )
    if (
        wrong
        or _EXECUTION.fullmatch(execution_id) is None
        or (
            execution_name != execution_id
            and not execution_name.startswith(qualified_prefix)
        )
    ):
        raise CorpusParametricTransportError("runtime execution ID differs")
    return {
        "execution_id": execution_id,
        "execution_name": execution_name,
        "manifest_task_index": task_index,
        "cloud_run_task_index": 0,
        "task_attempt": 0,
        "phase": phase,
    }


def _wait_for_execution_name(
    *,
    storage: ObjectStore,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    task_index: int,
    phase: str,
    runtime: Mapping[str, object],
    wait_seconds: int = EXECUTION_NAME_WAIT_SECONDS,
) -> dict[str, object]:
    task = _task_contract(contract, task_index)
    _, launch_identity, _ = _reopen_phase_launch(
        storage=storage,
        contract=contract,
        contract_identity=contract_identity,
        task_index=task_index,
        phase=phase,
    )
    deadline = time.monotonic() + _integer(
        wait_seconds, label="execution-name wait seconds"
    )
    last_error: Exception | None = None
    while True:
        try:
            identity, raw = storage.resolve_current(
                str(task[f"{phase}_execution_name_uri"])
            )
            item = dict(
                _mapping(
                    strict_json_bytes(raw, label="execution-name ledger"),
                    label="execution-name ledger",
                )
            )
            _validate_self_hash(
                item,
                field="execution_name_ledger_sha256",
                label="execution-name ledger",
            )
            if (
                item.get("transport_contract") != contract_identity.as_dict()
                or item.get("launch_ledger") != launch_identity
                or item.get("task_index") != task_index
                or item.get("phase") != phase
                or item.get("execution_id") != runtime["execution_id"]
                or item.get("task_attempt") != 0
                or item.get("max_retries") != 0
                or item.get("automatic_retry_licensed") is not False
            ):
                raise CorpusParametricTransportError(
                    "worker execution-name binding differs"
                )
            del identity
            return item
        except Exception as exc:
            last_error = exc
        if time.monotonic() >= deadline:
            raise CorpusParametricTransportError(
                "execution-name ledger was not bound before worker deadline"
            ) from last_error
        time.sleep(min(5.0, max(0.01, deadline - time.monotonic())))


def _validate_worker_build_environment(
    *, contract: Mapping[str, object], environ: Mapping[str, str]
) -> None:
    build = _mapping(contract["build"], label="contract build")
    if (
        environ.get(IMAGE_ENV) != build["image"]
        or environ.get(BUILD_ENV) != build["build_id"]
        or environ.get(CODE_ENV) != build["code_sha"]
    ):
        raise CorpusParametricTransportError(
            "worker image/build/code environment differs"
        )


def _task_request(
    *,
    batch: object,
    manifest: Mapping[str, object],
    contract: Mapping[str, object],
    task_index: int,
) -> tuple[dict[str, object], bytes]:
    try:
        request = batch.build_task_request(
            batch_manifest=manifest,
            batch_manifest_identity=contract["batch_manifest_identity"],
            task_index=task_index,
        )
        raw = batch.canonical_json_bytes(request)
        batch.bind_task_request_to_manifest(
            request,
            batch.canonical_json_bytes(manifest),
        )
    except Exception as exc:
        raise CorpusParametricTransportError("task request binding differs") from exc
    return request, raw


def _read_science_inputs(
    *,
    storage: ObjectStore,
    manifest: Mapping[str, object],
    task_index: int,
) -> dict[str, object]:
    common = _mapping(manifest["common_law"], label="manifest common law")
    task = _mapping(
        _sequence(manifest["tasks"], label="manifest tasks")[task_index],
        label="manifest task",
    )
    common_bodies = {
        role: _read_identity(
            storage, common[role], label=f"common law {role}"
        )[1]
        for role in COMMON_LAW_BODY_ROLES
    }
    artifacts = _mapping(
        task["world_artifact_receipts"], label="task world artifacts"
    )
    world_bodies = {
        role: _read_identity(
            storage, artifacts[role], label=f"task world artifact {role}"
        )[1]
        for role in sorted(artifacts)
    }
    return {
        "effective_policy_inventory_bytes": _read_identity(
            storage,
            common["effective_policy_inventory_identity"],
            label="effective-policy inventory",
        )[1],
        "artifact_source_authority_completion_bytes": _read_identity(
            storage,
            common["artifact_source_authority_completion"],
            label="artifact-source-authority completion",
        )[1],
        "later_source_freeze_bytes": _read_identity(
            storage,
            _mapping(common["source_receipts"], label="source receipts")[
                "later_source_freeze"
            ],
            label="later source freeze",
        )[1],
        "world_artifact_bodies": world_bodies,
        "common_law_bodies": common_bodies,
    }


def validate_task_inputs(
    *,
    storage: ObjectStore,
    contract_identity: object,
    task_index: int,
    repository_root: Path,
) -> dict[str, object]:
    """Read-only no-solve validation for the exact manifest/task inputs."""
    retained_contract_identity, contract, batch, manifest = _reopen_contract_graph(
        storage=storage, contract_identity=contract_identity
    )
    del retained_contract_identity
    request, _ = _task_request(
        batch=batch,
        manifest=manifest,
        contract=contract,
        task_index=task_index,
    )
    inputs = _read_science_inputs(
        storage=storage, manifest=manifest, task_index=task_index
    )
    _, _, core, _ = _modules()
    loader = getattr(core, "_load_authoritative_inputs", None)
    if not callable(loader):
        raise CorpusParametricTransportError("science input validator is absent")
    try:
        loaded = loader(
            task_request=request,
            batch_manifest_bytes=batch.canonical_json_bytes(manifest),
            repository_root=repository_root,
            **inputs,
        )
    except Exception as exc:
        raise CorpusParametricTransportError(
            "authoritative task input validation failed"
        ) from exc
    return {
        "schema_version": "corpus-parametric-input-validation/v1",
        "task_index": task_index,
        "slate_id": loaded.task["slate_id"],
        "batch_manifest_sha256": manifest["batch_manifest_sha256"],
        "artifact_source_authority_task_sha256": loaded.task[
            "artifact_source_authority_task_sha256"
        ],
        "input_identity_count": len(_manifest_input_identities(manifest)),
        "solve_invoked": False,
        "uses_realized_outcomes": False,
    }


def _publish_draft(
    *,
    storage: ObjectStore,
    draft: object,
    finalizer: Callable[..., object],
    task: Mapping[str, object],
    parameter_sets: Sequence[object],
) -> dict[str, object]:
    prefix = str(task["variant_output_prefix"])
    shard_rows: list[dict[str, object]] = []
    shards = tuple(getattr(draft, "solver_evidence_shards"))
    if len(shards) != 70:
        raise CorpusParametricTransportError("producer did not emit 70 shards")
    for expected, shard in enumerate(shards):
        ordinal = getattr(shard, "global_shard_ordinal")
        if ordinal != expected:
            raise CorpusParametricTransportError("evidence shard order differs")
        compressed_path = Path(getattr(shard, "compressed_path"))
        index_path = Path(getattr(shard, "index_path"))
        compressed_raw = compressed_path.read_bytes()
        index_raw = index_path.read_bytes()
        compressed_identity = storage.publish_or_reopen(
            f"{prefix}solver-evidence/shard-{ordinal:03d}.zlib",
            compressed_raw,
            "application/zlib",
        )
        index_identity = storage.publish_or_reopen(
            f"{prefix}solver-evidence/shard-{ordinal:03d}.index.json",
            index_raw,
        )
        shard_rows.append({
            "global_shard_ordinal": ordinal,
            "compressed_object_identity": compressed_identity,
            "index_object_identity": index_identity,
        })
    try:
        bundle = finalizer(
            draft, solver_evidence_object_identities=shard_rows
        )
    except Exception as exc:
        raise CorpusParametricTransportError(
            "published shard finalization failed"
        ) from exc
    authority_payloads = {
        "source_binding": getattr(draft, "source_binding_payload"),
        "registered_law": getattr(draft, "registered_law_payload"),
        "attempt_ledger": getattr(draft, "attempt_ledger_payload"),
        "matrix_authority": getattr(draft, "matrix_authority_payload"),
        "content_task_evidence_root": getattr(
            draft, "solver_evidence_task_root_payload"
        ),
        "published_task_evidence_root": getattr(
            bundle, "published_task_evidence_root_payload"
        ),
        "draft_authority_bundle": getattr(draft, "canonical_draft_payload"),
        "authority_bundle": getattr(bundle, "canonical_bundle_payload"),
        "batch_result": getattr(draft, "batch_result_payload"),
    }
    if tuple(authority_payloads) != AUTHORITY_OBJECT_ROLES:
        raise CorpusParametricTransportError("authority role mapping differs")
    authorities = {
        role: storage.publish_or_reopen(
            f"{prefix}authorities/{role.replace('_', '-')}.json", raw
        )
        for role, raw in authority_payloads.items()
    }
    runtime_payloads = tuple(getattr(draft, "runtime_policy_payloads"))
    variant_payloads = tuple(getattr(draft, "variant_result_payloads"))
    if len(runtime_payloads) != 7 or len(variant_payloads) != 7:
        raise CorpusParametricTransportError("producer variant coverage differs")
    runtime_rows: list[dict[str, object]] = []
    result_rows: list[dict[str, object]] = []
    variant_results: list[dict[str, object]] = []
    for ordinal, (raw_parameter_set, runtime_raw, result_raw) in enumerate(zip(
        parameter_sets, runtime_payloads, variant_payloads, strict=True
    )):
        parameter_set = _mapping(
            raw_parameter_set, label=f"parameter set[{ordinal}]"
        )
        parameter_set_id = str(parameter_set["parameter_set_id"])
        policy_identity = storage.publish_or_reopen(
            f"{prefix}{parameter_set_id}/effective-policy.json", runtime_raw
        )
        result_identity = storage.publish_or_reopen(
            f"{prefix}{parameter_set_id}/result.json", result_raw
        )
        runtime_rows.append({
            "ordinal": ordinal,
            "parameter_set_id": parameter_set_id,
            "object_identity": policy_identity,
        })
        result_rows.append({
            "ordinal": ordinal,
            "parameter_set_id": parameter_set_id,
            "object_identity": result_identity,
        })
        variant_results.append({
            "ordinal": ordinal,
            "parameter_set_id": parameter_set_id,
            "parameter_set_sha256": parameter_set["parameter_set_sha256"],
            "effective_policy_receipt": policy_identity,
            "result_object": result_identity,
        })
    return {
        "solver_evidence_shards": shard_rows,
        "authorities": authorities,
        "runtime_policy_objects": runtime_rows,
        "variant_result_objects": result_rows,
        "variant_results": variant_results,
    }


def _validate_producer_completion(
    value: object,
    *,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    task_index: int,
) -> dict[str, object]:
    item = dict(_mapping(value, label="producer worker completion"))
    _validate_self_hash(
        item, field="worker_completion_sha256", label="producer completion"
    )
    if (
        item.get("schema_version") != WORKER_COMPLETION_SCHEMA
        or item.get("phase") != "producer"
        or item.get("transport_contract") != contract_identity.as_dict()
        or item.get("retrieval_task0_prerequisite_identity")
        != contract["retrieval_task0_prerequisite_identity"]
        or item.get("task_index") != task_index
        or item.get("task_attempt") != 0
        or item.get("max_retries") != 0
        or item.get("complete") is not True
        or item.get("partial_result") is not False
        or item.get("evidence_object_count") != 140
        or item.get("uses_realized_outcomes") is not False
        or item.get("corpus_fill_licensed") is not False
    ):
        raise CorpusParametricTransportError("producer completion law differs")
    execution = _mapping(item.get("execution"), label="producer execution")
    if (
        execution.get("task_attempt") != 0
        or execution.get("phase") != "producer"
    ):
        raise CorpusParametricTransportError("producer runtime binding differs")
    shards = _sequence(
        item.get("solver_evidence_shards"), label="producer evidence shards"
    )
    authorities = _mapping(item.get("authorities"), label="producer authorities")
    runtime_rows = _sequence(
        item.get("runtime_policy_objects"), label="producer runtime objects"
    )
    result_rows = _sequence(
        item.get("variant_result_objects"), label="producer result objects"
    )
    variant_results = _sequence(
        item.get("variant_results"), label="producer variant results"
    )
    if (
        len(shards) != 70
        or frozenset(authorities) != frozenset(AUTHORITY_OBJECT_ROLES)
        or len(runtime_rows) != 7
        or len(result_rows) != 7
        or len(variant_results) != 7
    ):
        raise CorpusParametricTransportError("producer output coverage differs")
    return item


def execute_producer_task(
    *,
    storage: ObjectStore,
    contract_identity: object,
    task_index: int,
    repository_root: Path,
    execute: bool,
    environ: Mapping[str, str],
    wait_seconds: int = EXECUTION_NAME_WAIT_SECONDS,
    producer: Callable[..., object] | None = None,
    finalizer: Callable[..., object] | None = None,
) -> dict[str, object]:
    """Cloud worker: run one complete seven-arm producer task, without LIST."""
    require_execute_gate(execute=execute, environ=environ)
    retained_contract_identity, contract, batch, manifest = _reopen_contract_graph(
        storage=storage, contract_identity=contract_identity
    )
    _validate_worker_build_environment(contract=contract, environ=environ)
    reopen_retrieval_task0_prerequisite(
        storage=storage,
        prerequisite_identity=contract[
            "retrieval_task0_prerequisite_identity"
        ],
    )
    runtime = _runtime_execution(
        environ, contract=contract, task_index=task_index, phase="producer"
    )
    execution_binding = _wait_for_execution_name(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase="producer",
        runtime=runtime,
        wait_seconds=wait_seconds,
    )
    runtime = {
        **runtime,
        "execution_uid": execution_binding["execution_uid"],
    }
    request, _ = _task_request(
        batch=batch,
        manifest=manifest,
        contract=contract,
        task_index=task_index,
    )
    inputs = _read_science_inputs(
        storage=storage, manifest=manifest, task_index=task_index
    )
    _, _, core, _ = _modules()
    retained_producer = producer or core.run_authoritative_corpus_legal_feasibility
    retained_finalizer = finalizer or core.finalize_authoritative_corpus_bundle
    task = _mapping(manifest["tasks"][task_index], label="manifest task")
    with tempfile.TemporaryDirectory(
        prefix=f"corpus-parametric-task-{task_index:03d}-"
    ) as temp_name:
        try:
            draft = retained_producer(
                task_request=request,
                batch_manifest_bytes=batch.canonical_json_bytes(manifest),
                repository_root=repository_root,
                evidence_directory=Path(temp_name).resolve(),
                **inputs,
            )
        except Exception as exc:
            raise CorpusParametricTransportError(
                "authoritative producer failed"
            ) from exc
        published = _publish_draft(
            storage=storage,
            draft=draft,
            finalizer=retained_finalizer,
            task=task,
            parameter_sets=_sequence(
                manifest["parameter_sets"], label="parameter sets"
            ),
        )
    body = _self_hash({
        "schema_version": WORKER_COMPLETION_SCHEMA,
        "phase": "producer",
        "transport_contract": retained_contract_identity.as_dict(),
        "retrieval_task0_prerequisite_identity": contract[
            "retrieval_task0_prerequisite_identity"
        ],
        "task_index": task_index,
        "task_request_sha256": request["task_request_sha256"],
        "execution": runtime,
        "task_attempt": 0,
        "max_retries": 0,
        "solver_evidence_shards": published["solver_evidence_shards"],
        "evidence_object_count": 140,
        "authorities": published["authorities"],
        "runtime_policy_objects": published["runtime_policy_objects"],
        "variant_result_objects": published["variant_result_objects"],
        "variant_results": published["variant_results"],
        "complete": True,
        "partial_result": False,
        "uses_realized_outcomes": False,
        "corpus_fill_licensed": False,
    }, field="worker_completion_sha256")
    _validate_producer_completion(
        body,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
    )
    task_contract = _task_contract(contract, task_index)
    identity = storage.publish_or_reopen(
        str(task_contract["producer_worker_completion_uri"]),
        canonical_json_bytes(body),
    )
    return {
        "schema_version": "corpus-parametric-producer-published/v1",
        "task_index": task_index,
        "worker_completion": identity,
        "evidence_object_count": 140,
        "complete": True,
        "terminal_acceptance": False,
    }


def _producer_output_identities(
    completion: Mapping[str, object],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ordinal, raw_shard in enumerate(
        _sequence(
            completion["solver_evidence_shards"],
            label="producer evidence shards",
        )
    ):
        shard = _mapping(raw_shard, label=f"evidence shard[{ordinal}]")
        if shard.get("global_shard_ordinal") != ordinal:
            raise CorpusParametricTransportError("evidence shard order differs")
        rows.extend([
            object_identity(
                shard.get("compressed_object_identity"),
                label=f"evidence shard[{ordinal}] compressed",
            ).as_dict(),
            object_identity(
                shard.get("index_object_identity"),
                label=f"evidence shard[{ordinal}] index",
            ).as_dict(),
        ])
    authorities = _mapping(
        completion["authorities"], label="producer authorities"
    )
    for role in AUTHORITY_OBJECT_ROLES:
        rows.append(
            object_identity(
                authorities[role], label=f"producer authority {role}"
            ).as_dict()
        )
    for collection in ("runtime_policy_objects", "variant_result_objects"):
        for ordinal, raw_row in enumerate(
            _sequence(completion[collection], label=collection)
        ):
            row = _mapping(raw_row, label=f"{collection}[{ordinal}]")
            if row.get("ordinal") != ordinal:
                raise CorpusParametricTransportError(
                    f"{collection} order differs"
                )
            rows.append(
                object_identity(
                    row.get("object_identity"),
                    label=f"{collection}[{ordinal}] identity",
                ).as_dict()
            )
    if len(rows) != 163 or len({_identity_key(row) for row in rows}) != 163:
        raise CorpusParametricTransportError(
            "producer durable object coverage/uniqueness differs"
        )
    return rows


def _reopen_producer_completion(
    *,
    storage: ObjectStore,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    task_index: int,
) -> tuple[dict[str, object], dict[str, object]]:
    task = _task_contract(contract, task_index)
    identity, raw = storage.resolve_current(
        str(task["producer_worker_completion_uri"])
    )
    retained_identity = object_identity(identity, label="producer completion")
    _identity_matches_raw(retained_identity, raw, label="producer completion")
    completion = _validate_producer_completion(
        strict_json_bytes(raw, label="producer worker completion"),
        contract=contract,
        contract_identity=contract_identity,
        task_index=task_index,
    )
    for ordinal, output_identity in enumerate(
        _producer_output_identities(completion)
    ):
        _read_identity(
            storage,
            output_identity,
            label=f"producer output[{ordinal}]",
        )
    return retained_identity.as_dict(), completion


def _reopen_execution_name_binding(
    *,
    storage: ObjectStore,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    task_index: int,
    phase: str,
) -> tuple[dict[str, object], dict[str, object]]:
    task = _task_contract(contract, task_index)
    _, launch_identity, _ = _reopen_phase_launch(
        storage=storage,
        contract=contract,
        contract_identity=contract_identity,
        task_index=task_index,
        phase=phase,
    )
    identity, raw = _resolve_current_required(
        storage,
        str(task[f"{phase}_execution_name_uri"]),
        label=f"{phase} execution-name ledger",
    )
    item = dict(
        _mapping(
            strict_json_bytes(raw, label="execution-name ledger"),
            label="execution-name ledger",
        )
    )
    _validate_self_hash(
        item,
        field="execution_name_ledger_sha256",
        label="execution-name ledger",
    )
    if (
        item.get("schema_version") != EXECUTION_NAME_SCHEMA
        or item.get("transport_contract") != contract_identity.as_dict()
        or item.get("launch_ledger") != launch_identity
        or item.get("task_index") != task_index
        or item.get("phase") != phase
        or item.get("task_attempt") != 0
        or item.get("max_retries") != 0
        or item.get("automatic_retry_licensed") is not False
    ):
        raise CorpusParametricTransportError(
            "execution-name binding differs"
        )
    return identity, item


def _validate_terminal_governance_census(
    *,
    storage: ObjectStore,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    task_index: int,
    phase: str,
    terminal: Mapping[str, object],
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
) -> dict[str, object]:
    """Prove the job stayed parked and exactly one governed launch occurred."""
    retained_phase = _phase(phase)
    current_job = _validate_current_job(parked_job, contract=contract)
    validate_scheduler_census(
        schedulers,
        job_name=str(_mapping(contract["job"], label="contract job")["name"]),
        all_regions_complete=all_regions_complete,
    )
    _, _, launch = _reopen_phase_launch(
        storage=storage,
        contract=contract,
        contract_identity=contract_identity,
        task_index=task_index,
        phase=retained_phase,
    )
    before = set(_sequence(
        launch["execution_names_before"], label="terminal names before"
    ))
    after_names = execution_census_names(executions)
    after = set(after_names)
    if (
        before - after
        or after - before != {terminal["execution_id"]}
        or terminal["execution_id"] not in after
    ):
        raise CorpusParametricTransportError(
            "terminal census does not prove exactly one governed execution"
        )
    _require_no_active_executions(executions)
    census_rows = _sequence(executions, label="terminal execution census")
    retained_rows: list[object] = []
    for raw_row in census_rows:
        row = _mapping(raw_row, label="terminal execution census row")
        metadata = _mapping(
            row.get("metadata"), label="terminal execution census metadata"
        )
        name = _string(
            metadata.get("name"), label="terminal execution census name"
        )
        if name.rsplit("/", 1)[-1] == terminal["execution_id"]:
            retained_rows.append(raw_row)
    if len(retained_rows) != 1:
        raise CorpusParametricTransportError(
            "terminal execution is absent/repeated in census"
        )
    census_terminal_row = _mapping(
        retained_rows[0], label="retained terminal census row"
    )
    census_metadata = _mapping(
        census_terminal_row.get("metadata"), label="retained terminal metadata"
    )
    census_status = _mapping(
        census_terminal_row.get("status"), label="retained terminal status"
    )
    census_counts = {
        "succeeded": _integer(
            census_status.get("succeededCount", 0), label="census succeeded"
        ),
        "failed": _integer(
            census_status.get("failedCount", 0), label="census failed"
        ),
        "cancelled": _integer(
            census_status.get("cancelledCount", 0), label="census cancelled"
        ),
        "retried": _integer(
            census_status.get("retriedCount", 0), label="census retried"
        ),
    }
    if (
        census_metadata.get("uid") != terminal["execution_uid"]
        or _completion_state(census_terminal_row) != "True"
        or census_counts
        != {"succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0}
    ):
        raise CorpusParametricTransportError(
            "terminal execution describe differs from terminal census"
        )
    return {
        "job": current_job,
        "phase": retained_phase,
        "task_index": task_index,
        "execution_id": terminal["execution_id"],
        "execution_uid": terminal["execution_uid"],
        "execution_names": after_names,
        "execution_census_sha256": canonical_sha256(executions),
        "scheduler_census_sha256": canonical_sha256(schedulers),
        "all_regions_complete": True,
        "exactly_one_new_execution": True,
        "no_active_executions": True,
        "job_remains_parked": True,
    }


_TERMINAL_CENSUS_KEYS: Final = frozenset({
    "job", "phase", "task_index", "execution_id", "execution_uid",
    "execution_names", "execution_census_sha256", "scheduler_census_sha256",
    "all_regions_complete", "exactly_one_new_execution",
    "no_active_executions", "job_remains_parked",
})


def _validate_terminal_census_receipt(
    value: object,
    *,
    contract: Mapping[str, object],
    task_index: int,
    phase: str,
    terminal: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="terminal governance census receipt"))
    _exact_keys(item, _TERMINAL_CENSUS_KEYS, label="terminal census receipt")
    names = execution_census_names([
        {"metadata": {"name": name}}
        for name in _sequence(item["execution_names"], label="terminal names")
    ])
    if (
        item["job"] != contract["job"]
        or item["phase"] != _phase(phase)
        or item["task_index"] != task_index
        or item["execution_id"] != terminal["execution_id"]
        or item["execution_uid"] != terminal["execution_uid"]
        or item["execution_id"] not in names
        or any(item[field] is not True for field in (
            "all_regions_complete", "exactly_one_new_execution",
            "no_active_executions", "job_remains_parked",
        ))
    ):
        raise CorpusParametricTransportError(
            "terminal governance census receipt differs"
        )
    _sha(item["execution_census_sha256"], label="execution census SHA")
    _sha(item["scheduler_census_sha256"], label="scheduler census SHA")
    return item


def _science_terminal_body(
    *,
    contract: Mapping[str, object],
    manifest: Mapping[str, object],
    evidence_contract: Mapping[str, object],
    evidence_contract_identity: Mapping[str, object],
    request: Mapping[str, object],
    task_index: int,
    execution: Mapping[str, object],
    completion: Mapping[str, object],
) -> dict[str, object]:
    task = _mapping(manifest["tasks"][task_index], label="manifest task")
    build = _mapping(contract["build"], label="contract build")
    body = {
        "schema": TASK_TERMINAL_SCHEMA,
        "batch_manifest_sha256": manifest["batch_manifest_sha256"],
        "evidence_contract_identity": dict(evidence_contract_identity),
        "evidence_contract_sha256": evidence_contract[
            "evidence_contract_sha256"
        ],
        "task_request_sha256": request["task_request_sha256"],
        "task_index": task_index,
        "task_sha256": task["task_sha256"],
        "execution_id": execution["execution_id"],
        "execution_uid": execution["execution_uid"],
        "task_attempt": 0,
        "max_retries": 0,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "retried_count": 0,
        "completed_condition": "True",
        "strict_terminal_success": True,
        "runtime_image_terminal_verification": {
            "source_commit_sha": build["code_sha"],
            "cloud_build_id": build["build_id"],
            "immutable_image": _mapping(
                manifest["common_law"], label="manifest common law"
            )["immutable_image"],
            "terminal_verification_required": True,
        },
        "ambient_score_relevant_keys_present": [],
        "authorities": completion["authorities"],
        "runtime_policy_objects": completion["runtime_policy_objects"],
        "variant_result_objects": completion["variant_result_objects"],
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    # The science verifier uses the batch module's no-newline canonical hash.
    batch, _, _, _ = _modules()
    return {
        **body,
        "terminal_receipt_sha256": batch.canonical_sha256(body),
    }


def close_producer_task(
    *,
    storage: ObjectStore,
    contract_identity: object,
    task_index: int,
    terminal_execution_metadata: object,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    created_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Operator close: terminal producer → science terminal → task result."""
    require_execute_gate(execute=execute, environ=environ)
    retained_contract_identity, contract, batch, manifest = _reopen_contract_graph(
        storage=storage, contract_identity=contract_identity
    )
    task = _task_contract(contract, task_index)
    _, name_binding = _reopen_execution_name_binding(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase="producer",
    )
    terminal = _validate_execution_spec(
        terminal_execution_metadata,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase="producer",
        require_terminal_success=True,
    )
    if (
        terminal["execution_id"] != name_binding["execution_id"]
        or terminal["execution_uid"] != name_binding["execution_uid"]
    ):
        raise CorpusParametricTransportError(
            "producer terminal execution differs from name binding"
        )
    terminal_census = _validate_terminal_governance_census(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase="producer",
        terminal=terminal,
        parked_job=parked_job,
        executions=executions,
        schedulers=schedulers,
        all_regions_complete=all_regions_complete,
    )
    completion_identity, completion = _reopen_producer_completion(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
    )
    runtime = _mapping(completion["execution"], label="producer runtime")
    if (
        runtime["execution_id"] != terminal["execution_id"]
        or runtime["execution_uid"] != terminal["execution_uid"]
    ):
        raise CorpusParametricTransportError(
            "producer output execution differs from terminal metadata"
        )
    _, evidence, _, _ = _modules()
    evidence_identity, evidence_raw = _read_identity(
        storage, contract["evidence_contract_identity"], label="evidence contract"
    )
    try:
        evidence_value = evidence.validate_corpus_batch_evidence_contract_bytes(
            evidence_raw,
            batch_manifest=manifest,
            batch_manifest_identity=contract["batch_manifest_identity"],
        )
    except Exception as exc:
        raise CorpusParametricTransportError(
            "evidence contract cannot be reopened at producer close"
        ) from exc
    request, _ = _task_request(
        batch=batch,
        manifest=manifest,
        contract=contract,
        task_index=task_index,
    )
    science_terminal = _science_terminal_body(
        contract=contract,
        manifest=manifest,
        evidence_contract=evidence_value,
        evidence_contract_identity=evidence_identity.as_dict(),
        request=request,
        task_index=task_index,
        execution=terminal,
        completion=completion,
    )
    terminal_raw = batch.canonical_json_bytes(science_terminal)
    terminal_identity = storage.publish_or_reopen(
        str(task["science_terminal_uri"]), terminal_raw
    )
    execution = {
        "execution_id": terminal["execution_id"],
        "execution_uid": terminal["execution_uid"],
        "task_index": task_index,
        "attempt": 1,
        "retry_count": 0,
        "terminal_status": "succeeded",
        "terminal_receipt": terminal_identity,
    }
    try:
        task_result = batch.build_task_result_receipt(
            batch_manifest=manifest,
            batch_manifest_identity=contract["batch_manifest_identity"],
            task_index=task_index,
            execution=execution,
            variant_results=completion["variant_results"],
        )
        batch.validate_task_result_receipt(
            task_result,
            batch_manifest=manifest,
            batch_manifest_identity=contract["batch_manifest_identity"],
        )
    except Exception as exc:
        raise CorpusParametricTransportError(
            "task-result binding failed at producer close"
        ) from exc
    result_identity = storage.publish_or_reopen(
        str(task["result_receipt_uri"]), batch.canonical_json_bytes(task_result)
    )
    close = _self_hash({
        "schema_version": "corpus-parametric-producer-close/v1",
        "created_at_utc": _timestamp(
            created_at_utc, label="producer close timestamp"
        ),
        "transport_contract": retained_contract_identity.as_dict(),
        "retrieval_task0_prerequisite_identity": contract[
            "retrieval_task0_prerequisite_identity"
        ],
        "task_index": task_index,
        "producer_worker_completion": completion_identity,
        "science_terminal": terminal_identity,
        "task_result": result_identity,
        "producer_terminal_execution": terminal,
        "terminal_governance_census": terminal_census,
        "complete_evidence_receipt": True,
        "partial_result": False,
        "independent_verification_complete": False,
        "terminal_acceptance": False,
        "uses_realized_outcomes": False,
        "corpus_fill_licensed": False,
    }, field="producer_close_sha256")
    close_identity = storage.publish_or_reopen(
        str(task["producer_close_uri"]), canonical_json_bytes(close)
    )
    return {
        "schema_version": "corpus-parametric-producer-closed/v1",
        "task_index": task_index,
        "producer_close": close_identity,
        "science_terminal": terminal_identity,
        "task_result": result_identity,
        "independent_verification_complete": False,
        "terminal_acceptance": False,
    }


def _reopen_producer_close(
    *,
    storage: ObjectStore,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    manifest: Mapping[str, object],
    task_index: int,
) -> tuple[dict[str, object], dict[str, object]]:
    task = _task_contract(contract, task_index)
    identity, raw = storage.resolve_current(str(task["producer_close_uri"]))
    close = dict(
        _mapping(
            strict_json_bytes(raw, label="producer close"),
            label="producer close",
        )
    )
    _validate_self_hash(
        close, field="producer_close_sha256", label="producer close"
    )
    if (
        close.get("schema_version") != "corpus-parametric-producer-close/v1"
        or close.get("retrieval_task0_prerequisite_identity")
        != contract["retrieval_task0_prerequisite_identity"]
        or close.get("task_index") != task_index
        or close.get("complete_evidence_receipt") is not True
        or close.get("partial_result") is not False
        or close.get("independent_verification_complete") is not False
        or close.get("terminal_acceptance") is not False
        or close.get("uses_realized_outcomes") is not False
        or close.get("corpus_fill_licensed") is not False
    ):
        raise CorpusParametricTransportError("producer close law differs")
    close_contract_identity = object_identity(
        close.get("transport_contract"), label="producer close contract"
    )
    if close_contract_identity != contract_identity:
        raise CorpusParametricTransportError(
            "producer close transport contract differs"
        )
    producer_terminal = _mapping(
        close.get("producer_terminal_execution"),
        label="producer terminal execution receipt",
    )
    terminal_census = _validate_terminal_census_receipt(
        close.get("terminal_governance_census"),
        contract=contract,
        task_index=task_index,
        phase="producer",
        terminal=producer_terminal,
    )
    completion_identity, completion = _reopen_producer_completion(
        storage=storage,
        contract=contract,
        contract_identity=close_contract_identity,
        task_index=task_index,
    )
    if completion_identity != close["producer_worker_completion"]:
        raise CorpusParametricTransportError(
            "producer close completion identity differs"
        )
    science_identity, science_raw = _read_identity(
        storage, close["science_terminal"], label="science terminal"
    )
    result_identity, result_raw = _read_identity(
        storage, close["task_result"], label="task result"
    )
    if (
        science_identity.uri != task["science_terminal_uri"]
        or result_identity.uri != task["result_receipt_uri"]
    ):
        raise CorpusParametricTransportError("producer close URI differs")
    batch, _, _, _ = _modules()
    try:
        science = batch.parse_canonical_json_bytes(
            science_raw, label="science terminal"
        )
        task_result_value = batch.parse_canonical_json_bytes(
            result_raw, label="task result"
        )
        task_result = batch.validate_task_result_receipt(
            task_result_value,
            batch_manifest=manifest,
            batch_manifest_identity=contract["batch_manifest_identity"],
        )
    except Exception as exc:
        raise CorpusParametricTransportError(
            "producer close science/task-result replay failed"
        ) from exc
    science_map = _mapping(science, label="science terminal")
    science_body = {
        key: science_map[key]
        for key in science_map
        if key != "terminal_receipt_sha256"
    }
    if (
        science_map.get("terminal_receipt_sha256")
        != batch.canonical_sha256(science_body)
        or science_map.get("strict_terminal_success") is not True
        or science_map.get("task_index") != task_index
        or _mapping(task_result["execution"], label="task execution")[
            "terminal_receipt"
        ] != science_identity.as_dict()
    ):
        raise CorpusParametricTransportError(
            "producer science terminal binding differs"
        )
    return identity, {
        "close": close,
        "completion": completion,
        "science_terminal": science_map,
        "science_terminal_identity": science_identity.as_dict(),
        "task_result": task_result,
        "task_result_identity": result_identity.as_dict(),
        "terminal_governance_census": terminal_census,
    }


class _VerifierReader:
    def __init__(self, storage: ObjectStore) -> None:
        self._storage = storage

    def read_generation(self, *, uri: str, generation: str) -> bytes:
        method = getattr(self._storage, "read_generation", None)
        if not callable(method):
            raise CorpusParametricTransportError(
                "storage lacks exact-generation verifier read"
            )
        return method(uri=uri, generation=generation)


def _validate_verifier_completion(
    value: object,
    *,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    task_index: int,
) -> dict[str, object]:
    item = dict(_mapping(value, label="verifier worker completion"))
    _validate_self_hash(
        item, field="worker_completion_sha256", label="verifier completion"
    )
    if (
        item.get("schema_version") != WORKER_COMPLETION_SCHEMA
        or item.get("phase") != "verifier"
        or item.get("transport_contract") != contract_identity.as_dict()
        or item.get("retrieval_task0_prerequisite_identity")
        != contract["retrieval_task0_prerequisite_identity"]
        or item.get("task_index") != task_index
        or item.get("task_attempt") != 0
        or item.get("max_retries") != 0
        or item.get("independent_verification_complete") is not True
        or item.get("complete_evidence_receipt") is not True
        or item.get("partial_result") is not False
        or item.get("terminal_acceptance") is not False
        or item.get("uses_realized_outcomes") is not False
        or item.get("corpus_fill_licensed") is not False
    ):
        raise CorpusParametricTransportError("verifier completion law differs")
    object_identity(
        item.get("independent_verification"),
        label="independent verification identity",
    )
    return item


def execute_verifier_task(
    *,
    storage: ObjectStore,
    contract_identity: object,
    task_index: int,
    repository_root: Path,
    execute: bool,
    environ: Mapping[str, str],
    wait_seconds: int = EXECUTION_NAME_WAIT_SECONDS,
    verifier_call: Callable[..., object] | None = None,
) -> dict[str, object]:
    """Independent zero-retry verifier worker; never invokes the producer."""
    require_execute_gate(execute=execute, environ=environ)
    retained_contract_identity, contract, batch, manifest = _reopen_contract_graph(
        storage=storage, contract_identity=contract_identity
    )
    _validate_worker_build_environment(contract=contract, environ=environ)
    runtime = _runtime_execution(
        environ, contract=contract, task_index=task_index, phase="verifier"
    )
    execution_binding = _wait_for_execution_name(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase="verifier",
        runtime=runtime,
        wait_seconds=wait_seconds,
    )
    runtime = {
        **runtime,
        "execution_uid": execution_binding["execution_uid"],
    }
    producer_close_identity, closed = _reopen_producer_close(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        manifest=manifest,
        task_index=task_index,
    )
    _, request_raw = _task_request(
        batch=batch,
        manifest=manifest,
        contract=contract,
        task_index=task_index,
    )
    _, _, _, verifier_module = _modules()
    call = verifier_call or verifier_module.verify_corpus_legal_feasibility_authority
    try:
        verification = call(
            task_request_bytes=request_raw,
            task_result_identity=closed["task_result_identity"],
            evidence_contract_identity=contract["evidence_contract_identity"],
            object_reader=_VerifierReader(storage),
            repository_root=repository_root,
        )
        verification_raw = bytes(getattr(verification, "canonical_payload"))
    except Exception as exc:
        raise CorpusParametricTransportError(
            "independent verification failed"
        ) from exc
    _parse_independent_verification(
        storage=storage,
        raw=verification_raw,
        batch=batch,
        contract=contract,
        manifest=manifest,
        task_index=task_index,
        closed=closed,
    )
    task = _task_contract(contract, task_index)
    verification_identity = storage.publish_or_reopen(
        str(task["independent_verification_uri"]), verification_raw
    )
    body = _self_hash({
        "schema_version": WORKER_COMPLETION_SCHEMA,
        "phase": "verifier",
        "transport_contract": retained_contract_identity.as_dict(),
        "retrieval_task0_prerequisite_identity": contract[
            "retrieval_task0_prerequisite_identity"
        ],
        "task_index": task_index,
        "execution": runtime,
        "task_attempt": 0,
        "max_retries": 0,
        "producer_close": producer_close_identity,
        "science_terminal": closed["science_terminal_identity"],
        "task_result": closed["task_result_identity"],
        "independent_verification": verification_identity,
        "independent_verification_complete": True,
        "complete_evidence_receipt": True,
        "partial_result": False,
        "terminal_acceptance": False,
        "uses_realized_outcomes": False,
        "corpus_fill_licensed": False,
    }, field="worker_completion_sha256")
    _validate_verifier_completion(
        body,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
    )
    completion_identity = storage.publish_or_reopen(
        str(task["verifier_worker_completion_uri"]), canonical_json_bytes(body)
    )
    return {
        "schema_version": "corpus-parametric-independent-verification-published/v1",
        "task_index": task_index,
        "independent_verification": verification_identity,
        "verifier_worker_completion": completion_identity,
        "terminal_acceptance": False,
    }


_INDEPENDENT_VERIFICATION_KEYS: Final = frozenset({
    "schema", "task_index", "season", "week", "slate_id",
    "source_binding_sha256", "registered_law_sha256",
    "attempt_ledger_sha256", "matrix_authority_sha256",
    "solver_evidence_task_root_sha256",
    "published_task_evidence_root_sha256", "draft_sha256",
    "authority_bundle_sha256",
    "artifact_source_authority_completion_object_sha256",
    "artifact_source_authority_completion_sha256",
    "artifact_source_authority_task_sha256", "evidence_contract_sha256",
    "task_result_sha256", "terminal_receipt_sha256",
    "variant_result_sha256s", "batch_result_sha256",
    "candidate_score_sha256s", "selected_score_sha256s",
    "paired_primary_optimum_summary", "outside_incumbent_law_summaries",
    "score_free_endpoint_summaries", "score_matrix_coverage_summaries",
    "verified_cell_count", "verified_solver_stage_count",
    "verified_unique_candidate_count", "verified_selected_entry_count",
    "verified_gate_ids", "outcome_columns_read", "uses_realized_outcomes",
    "historical_scoring_licensed", "production_change_licensed",
    "decision_authority", "verification_sha256",
})

_VERIFIER_GATE_IDS: Final = (
    "gate:corpus:batch-manifest-seven-set-identity",
    "gate:corpus:source-world-compute-pairing",
    "gate:corpus:effective-policy-runtime-replay",
    "gate:corpus:solver-terminal-zero-retry-proof",
    "gate:corpus:paired-objective-relaxation-monotonicity",
    "gate:corpus:outside-incumbent-law-nonvacuity",
    "gate:corpus:dk-legality-and-exact80",
    "gate:corpus:independent-scorefree-replay",
    "gate:corpus:simulated-score-matrix-exact-roster-world-coverage",
)

_SCORE_MATRIX_COVERAGE_KEYS: Final = frozenset({
    "schema", "parameter_set_id", "dtype",
    "generated_unique_roster_count", "candidate_score_row_count",
    "selected_roster_count", "selected_score_row_count", "world_count",
    "ordered_world_lattice", "ordered_world_lattice_sha256",
    "generated_unique_roster_identity_sha256",
    "selected_roster_identity_sha256", "candidate_score_sha256",
    "selected_score_sha256", "complete_generated_unique_roster_row_coverage",
    "complete_selected_roster_row_coverage",
    "selected_rows_are_exact_candidate_subset", "coverage_sha256",
})
_SCORE_FREE_ENDPOINT_KEYS: Final = frozenset({
    "schema", "parameter_set_id", "world_count",
    "simulated_candidate_ceiling_c", "simulated_exact80_maximum_s",
    "simulated_conversion_gap_c_minus_s", "candidate_world_max_sha256",
    "selected_world_max_sha256", "score_matrix_coverage_sha256",
    "endpoint_summary_sha256",
})
_OUTSIDE_LAW_SUMMARY_KEYS: Final = frozenset({
    "schema", "variant_ordinal", "parameter_set_id", "predicate",
    "removed_rule", "generated_unique_count",
    "outside_incumbent_law_unique_count", "required_witness_count",
    "qualifying_witness_count", "independent_five_rule_violation_counts",
    "generated_unique_roster_identity_sha256",
    "outside_roster_violation_rows_sha256", "passed",
    "outside_law_nonvacuity_sha256",
})
_PAIRED_SUMMARY_KEYS: Final = frozenset({
    "schema", "incumbent_variant_ordinal", "incumbent_parameter_set_id",
    "challenger_count", "visits_per_challenger", "aligned_comparison_count",
    "pairing_order", "ordered_world_schedule_sha256",
    "challenger_summaries", "all_deltas_nonnegative",
    "paired_monotonicity_sha256",
})

_AUTHORITY_RECEIPT_BINDINGS: Final = {
    "source_binding": (
        "corpus-authoritative-task-source/v1",
        "binding_sha256",
        "source_binding_sha256",
    ),
    "registered_law": (
        "corpus-authoritative-registered-law/v1",
        "binding_sha256",
        "registered_law_sha256",
    ),
    "attempt_ledger": (
        "corpus-legal-feasibility-attempt-ledger/v1",
        "attempt_ledger_sha256",
        "attempt_ledger_sha256",
    ),
    "matrix_authority": (
        "corpus-legal-feasibility-matrix-authority/v1",
        "matrix_authority_sha256",
        "matrix_authority_sha256",
    ),
    "content_task_evidence_root": (
        "corpus-cbc-evidence-task-root/v1",
        "task_evidence_root_sha256",
        "solver_evidence_task_root_sha256",
    ),
    "published_task_evidence_root": (
        "corpus-cbc-published-task-evidence-root/v1",
        "published_task_evidence_root_sha256",
        "published_task_evidence_root_sha256",
    ),
    "draft_authority_bundle": (
        "corpus-legal-feasibility-draft-authority-bundle/v1",
        "draft_sha256",
        "draft_sha256",
    ),
    "authority_bundle": (
        "corpus-legal-feasibility-authority-bundle/v1",
        "bundle_sha256",
        "authority_bundle_sha256",
    ),
    "batch_result": (
        "corpus-legal-feasibility-batch-result/v1",
        "result_sha256",
        "batch_result_sha256",
    ),
}


def _parse_core_self_hashed(
    *,
    storage: ObjectStore,
    identity: object,
    batch: object,
    schema: str,
    hash_field: str,
    label: str,
) -> dict[str, object]:
    _, raw = _read_identity(storage, identity, label=label)
    try:
        parsed = batch.parse_canonical_json_bytes(raw, label=label)
    except Exception as exc:
        raise CorpusParametricTransportError(
            f"{label} canonical replay failed"
        ) from exc
    item = dict(_mapping(parsed, label=label))
    retained = _sha(item.get(hash_field), label=f"{label} SHA")
    body = {key: item[key] for key in item if key != hash_field}
    if item.get("schema") != schema or retained != batch.canonical_sha256(body):
        raise CorpusParametricTransportError(f"{label} self-hash/schema differs")
    return item


def _validate_summary_self_hash(
    value: object,
    *,
    batch: object,
    schema: str,
    hash_field: str,
    expected_keys: frozenset[str],
    label: str,
) -> dict[str, object]:
    item = dict(_mapping(value, label=label))
    _exact_keys(item, expected_keys, label=label)
    retained = _sha(item.get(hash_field), label=f"{label} SHA")
    body = {key: item[key] for key in item if key != hash_field}
    if item.get("schema") != schema or retained != batch.canonical_sha256(body):
        raise CorpusParametricTransportError(f"{label} self-hash/schema differs")
    return item


def _parse_independent_verification(
    *,
    storage: ObjectStore,
    raw: bytes,
    batch: object,
    contract: Mapping[str, object],
    manifest: Mapping[str, object],
    task_index: int,
    closed: Mapping[str, object],
) -> dict[str, object]:
    try:
        parsed = batch.parse_canonical_json_bytes(
            raw, label="independent verification"
        )
    except Exception as exc:
        raise CorpusParametricTransportError(
            "independent verification bytes differ"
        ) from exc
    item = dict(_mapping(parsed, label="independent verification"))
    _exact_keys(
        item, _INDEPENDENT_VERIFICATION_KEYS,
        label="independent verification",
    )
    retained_sha = _sha(
        item.get("verification_sha256"), label="verification SHA"
    )
    body = {key: item[key] for key in item if key != "verification_sha256"}
    task_result = _mapping(closed["task_result"], label="closed task result")
    science_terminal = _mapping(
        closed["science_terminal"], label="closed science terminal"
    )
    task = _mapping(
        _sequence(manifest["tasks"], label="manifest tasks")[task_index],
        label="manifest task",
    )
    completion = _mapping(closed["completion"], label="closed completion")
    authorities = _mapping(
        completion["authorities"], label="closed producer authorities"
    )
    authority_bodies: dict[str, dict[str, object]] = {}
    for role, (schema, hash_field, receipt_field) in (
        _AUTHORITY_RECEIPT_BINDINGS.items()
    ):
        authority = _parse_core_self_hashed(
            storage=storage,
            identity=authorities[role],
            batch=batch,
            schema=schema,
            hash_field=hash_field,
            label=f"independent verification {role}",
        )
        authority_bodies[role] = authority
        if item[receipt_field] != authority[hash_field]:
            raise CorpusParametricTransportError(
                f"independent verification {role} binding differs"
            )

    parameter_sets = _sequence(
        manifest["parameter_sets"], label="manifest parameter sets"
    )
    parameter_ids = [
        _mapping(value, label=f"parameter set[{ordinal}]")["parameter_set_id"]
        for ordinal, value in enumerate(parameter_sets)
    ]
    variant_bodies: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(_sequence(
        completion["variant_result_objects"], label="variant result objects"
    )):
        row = _mapping(raw_row, label=f"variant result object[{ordinal}]")
        if row.get("ordinal") != ordinal or row.get("parameter_set_id") != (
            parameter_ids[ordinal]
        ):
            raise CorpusParametricTransportError(
                "variant result identity order differs"
            )
        variant = _parse_core_self_hashed(
            storage=storage,
            identity=row.get("object_identity"),
            batch=batch,
            schema="corpus-legal-feasibility-variant-result/v2",
            hash_field="result_sha256",
            label=f"independent verification variant[{ordinal}]",
        )
        profile = _mapping(variant.get("profile"), label="variant profile")
        if (
            profile.get("ordinal") != ordinal
            or profile.get("parameter_set_id") != parameter_ids[ordinal]
        ):
            raise CorpusParametricTransportError(
                "variant result profile binding differs"
            )
        variant_bodies.append(variant)

    variant_hashes = [value["result_sha256"] for value in variant_bodies]
    candidate_hashes = [value["candidate_score_sha256"] for value in variant_bodies]
    selected_hashes = [value["selected_score_sha256"] for value in variant_bodies]
    variant_coverages = [
        _mapping(value["coverage"], label=f"variant coverage[{ordinal}]")
        for ordinal, value in enumerate(variant_bodies)
    ]
    batch_result = authority_bodies["batch_result"]
    batch_rows = _sequence(
        batch_result.get("variant_results"), label="batch variant results"
    )
    if len(batch_rows) != 7 or any(
        _mapping(row, label=f"batch variant[{ordinal}]").get("result_sha256")
        != variant_hashes[ordinal]
        for ordinal, row in enumerate(batch_rows)
    ):
        raise CorpusParametricTransportError(
            "batch result variant binding differs"
        )

    coverage_summaries = _sequence(
        item["score_matrix_coverage_summaries"],
        label="score matrix coverage summaries",
    )
    endpoint_summaries = _sequence(
        item["score_free_endpoint_summaries"],
        label="score-free endpoint summaries",
    )
    outside_summaries = _sequence(
        item["outside_incumbent_law_summaries"],
        label="outside-law summaries",
    )
    if not (
        len(coverage_summaries) == len(endpoint_summaries)
        == len(outside_summaries) == 7
    ):
        raise CorpusParametricTransportError(
            "independent verification seven-arm summary coverage differs"
        )
    for ordinal, parameter_id in enumerate(parameter_ids):
        coverage_summary = _validate_summary_self_hash(
            coverage_summaries[ordinal],
            batch=batch,
            schema="corpus-score-matrix-coverage/v1",
            hash_field="coverage_sha256",
            expected_keys=_SCORE_MATRIX_COVERAGE_KEYS,
            label=f"score matrix coverage[{ordinal}]",
        )
        endpoint_summary = _validate_summary_self_hash(
            endpoint_summaries[ordinal],
            batch=batch,
            schema="corpus-score-free-endpoint-summary/v1",
            hash_field="endpoint_summary_sha256",
            expected_keys=_SCORE_FREE_ENDPOINT_KEYS,
            label=f"score-free endpoint[{ordinal}]",
        )
        outside_summary = _validate_summary_self_hash(
            outside_summaries[ordinal],
            batch=batch,
            schema="corpus-outside-incumbent-law-nonvacuity/v1",
            hash_field="outside_law_nonvacuity_sha256",
            expected_keys=_OUTSIDE_LAW_SUMMARY_KEYS,
            label=f"outside-law summary[{ordinal}]",
        )
        variant_coverage = variant_coverages[ordinal]
        candidate_ceiling = _finite_float(
            endpoint_summary.get("simulated_candidate_ceiling_c"),
            label=f"score-free endpoint[{ordinal}] candidate ceiling",
        )
        selected_maximum = _finite_float(
            endpoint_summary.get("simulated_exact80_maximum_s"),
            label=f"score-free endpoint[{ordinal}] selected maximum",
        )
        conversion_gap = _finite_float(
            endpoint_summary.get("simulated_conversion_gap_c_minus_s"),
            label=f"score-free endpoint[{ordinal}] conversion gap",
        )
        if (
            coverage_summary.get("parameter_set_id") != parameter_id
            or coverage_summary.get("dtype") != "float64-le"
            or coverage_summary.get("world_count") != 50_000
            or coverage_summary.get("candidate_score_sha256")
            != candidate_hashes[ordinal]
            or coverage_summary.get("selected_score_sha256")
            != selected_hashes[ordinal]
            or coverage_summary.get("generated_unique_roster_count")
            != variant_coverage.get("unique_candidates")
            or coverage_summary.get("candidate_score_row_count")
            != variant_coverage.get("unique_candidates")
            or coverage_summary.get("selected_roster_count") != 80
            or coverage_summary.get("selected_score_row_count") != 80
            or variant_coverage.get("selected_entries") != 80
            or any(coverage_summary.get(field) is not True for field in (
                "complete_generated_unique_roster_row_coverage",
                "complete_selected_roster_row_coverage",
                "selected_rows_are_exact_candidate_subset",
            ))
            or endpoint_summary.get("parameter_set_id") != parameter_id
            or endpoint_summary.get("world_count") != 50_000
            or endpoint_summary.get("score_matrix_coverage_sha256")
            != coverage_summary["coverage_sha256"]
            or conversion_gap != candidate_ceiling - selected_maximum
            or conversion_gap < 0
            or outside_summary.get("variant_ordinal") != ordinal
            or outside_summary.get("parameter_set_id") != parameter_id
            or outside_summary.get("generated_unique_count")
            != variant_coverage.get("unique_candidates")
            or outside_summary.get("passed") is not True
        ):
            raise CorpusParametricTransportError(
                f"independent verification summary[{ordinal}] binding differs"
            )

    paired = _validate_summary_self_hash(
        item["paired_primary_optimum_summary"],
        batch=batch,
        schema="corpus-paired-primary-optimum-monotonicity/v1",
        hash_field="paired_monotonicity_sha256",
        expected_keys=_PAIRED_SUMMARY_KEYS,
        label="paired primary optimum summary",
    )
    _, _, _, verifier_module = _modules()
    paired_replay = getattr(
        verifier_module, "_paired_primary_optimum_summary", None
    )
    attempts = _sequence(
        authority_bodies["attempt_ledger"].get("attempts"),
        label="attempt ledger attempts",
    )
    if (
        not callable(paired_replay)
        or paired_replay(attempts) != paired
        or paired.get("challenger_count") != 6
        or paired.get("visits_per_challenger") != 1_000
        or paired.get("aligned_comparison_count") != 6_000
        or paired.get("all_deltas_nonnegative") is not True
    ):
        raise CorpusParametricTransportError(
            "paired primary-optimum summary replay differs"
        )

    common = _mapping(manifest["common_law"], label="manifest common law")
    completion_object = object_identity(
        common["artifact_source_authority_completion"],
        label="artifact-source completion",
    )
    expected_unique_count = sum(
        _integer(value.get("unique_candidates"), label="unique candidate count")
        for value in variant_coverages
    )
    if (
        item.get("schema")
        != "corpus-legal-feasibility-independent-verification/v2"
        or retained_sha != batch.canonical_sha256(body)
        or item.get("task_index") != task_index
        or item.get("task_result_sha256")
        != task_result["task_result_sha256"]
        or item.get("terminal_receipt_sha256")
        != science_terminal["terminal_receipt_sha256"]
        or item.get("season") != task["season"]
        or item.get("week") != task["week"]
        or item.get("slate_id") != task["slate_id"]
        or item.get("artifact_source_authority_completion_object_sha256")
        != completion_object.sha256
        or item.get("artifact_source_authority_completion_sha256")
        != common["artifact_source_authority_completion_sha256"]
        or item.get("artifact_source_authority_task_sha256")
        != task["artifact_source_authority_task_sha256"]
        or item.get("evidence_contract_sha256")
        != science_terminal["evidence_contract_sha256"]
        or science_terminal.get("evidence_contract_identity")
        != contract["evidence_contract_identity"]
        or item.get("variant_result_sha256s") != variant_hashes
        or item.get("batch_result_sha256") != batch_result["result_sha256"]
        or item.get("candidate_score_sha256s") != candidate_hashes
        or item.get("selected_score_sha256s") != selected_hashes
        or item.get("verified_cell_count") != 7_000
        or item.get("verified_solver_stage_count") != 14_000
        or item.get("verified_unique_candidate_count") != expected_unique_count
        or item.get("verified_selected_entry_count") != 560
        or item.get("verified_gate_ids") != list(_VERIFIER_GATE_IDS)
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
        or item.get("historical_scoring_licensed") is not False
        or item.get("production_change_licensed") is not False
        or item.get("decision_authority") is not False
    ):
        raise CorpusParametricTransportError(
            "independent verification coverage/binding differs"
        )
    return item


def _reopen_verifier_completion(
    *,
    storage: ObjectStore,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    manifest: Mapping[str, object],
    batch: object,
    task_index: int,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    task = _task_contract(contract, task_index)
    identity, raw = storage.resolve_current(
        str(task["verifier_worker_completion_uri"])
    )
    completion = _validate_verifier_completion(
        strict_json_bytes(raw, label="verifier worker completion"),
        contract=contract,
        contract_identity=contract_identity,
        task_index=task_index,
    )
    producer_close_identity, closed = _reopen_producer_close(
        storage=storage,
        contract=contract,
        contract_identity=contract_identity,
        manifest=manifest,
        task_index=task_index,
    )
    if (
        completion["producer_close"] != producer_close_identity
        or
        completion["science_terminal"] != closed["science_terminal_identity"]
        or completion["task_result"] != closed["task_result_identity"]
    ):
        raise CorpusParametricTransportError(
            "verifier completion producer binding differs"
        )
    verification_identity, verification_raw = _read_identity(
        storage,
        completion["independent_verification"],
        label="independent verification",
    )
    if verification_identity.uri != task["independent_verification_uri"]:
        raise CorpusParametricTransportError(
            "independent verification URI differs"
        )
    verification = _parse_independent_verification(
        storage=storage,
        raw=verification_raw,
        batch=batch,
        contract=contract,
        manifest=manifest,
        task_index=task_index,
        closed=closed,
    )
    return identity, completion, verification


def _task_prefix_identity_set_before_acceptance(
    *,
    storage: ObjectStore,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    manifest: Mapping[str, object],
    task_index: int,
) -> list[dict[str, object]]:
    identities: list[dict[str, object]] = []
    for phase in ("producer", "verifier"):
        intent_identity, ledger_identity, _ = _reopen_phase_launch(
            storage=storage,
            contract=contract,
            contract_identity=contract_identity,
            task_index=task_index,
            phase=phase,
        )
        name_identity, _ = _reopen_execution_name_binding(
            storage=storage,
            contract=contract,
            contract_identity=contract_identity,
            task_index=task_index,
            phase=phase,
        )
        identities.extend([intent_identity, ledger_identity, name_identity])
    producer_completion_identity, producer_completion = (
        _reopen_producer_completion(
            storage=storage,
            contract=contract,
            contract_identity=contract_identity,
            task_index=task_index,
        )
    )
    identities.extend(_producer_output_identities(producer_completion))
    identities.append(producer_completion_identity)
    producer_close_identity, closed = _reopen_producer_close(
        storage=storage,
        contract=contract,
        contract_identity=contract_identity,
        manifest=manifest,
        task_index=task_index,
    )
    identities.extend([
        closed["science_terminal_identity"],
        producer_close_identity,
    ])
    verifier_completion_identity, verifier_completion, _ = (
        _reopen_verifier_completion(
            storage=storage,
            contract=contract,
            contract_identity=contract_identity,
            manifest=manifest,
            batch=_modules()[0],
            task_index=task_index,
        )
    )
    identities.extend([
        verifier_completion["independent_verification"],
        verifier_completion_identity,
    ])
    if len({_identity_key(row) for row in identities}) != len(identities):
        raise CorpusParametricTransportError(
            "task evidence/governance identities repeat"
        )
    return identities


def accept_verified_task(
    *,
    storage: ObjectStore,
    contract_identity: object,
    task_index: int,
    terminal_execution_metadata: object,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    created_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Publish the sole accepted terminal, only after verifier success."""
    require_execute_gate(execute=execute, environ=environ)
    retained_contract_identity, contract, batch, manifest = _reopen_contract_graph(
        storage=storage, contract_identity=contract_identity
    )
    task = _task_contract(contract, task_index)
    _, name_binding = _reopen_execution_name_binding(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase="verifier",
    )
    terminal = _validate_execution_spec(
        terminal_execution_metadata,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase="verifier",
        require_terminal_success=True,
    )
    if (
        terminal["execution_id"] != name_binding["execution_id"]
        or terminal["execution_uid"] != name_binding["execution_uid"]
    ):
        raise CorpusParametricTransportError(
            "verifier terminal execution differs from name binding"
        )
    terminal_census = _validate_terminal_governance_census(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        task_index=task_index,
        phase="verifier",
        terminal=terminal,
        parked_job=parked_job,
        executions=executions,
        schedulers=schedulers,
        all_regions_complete=all_regions_complete,
    )
    verifier_completion_identity, verifier_completion, verification = (
        _reopen_verifier_completion(
            storage=storage,
            contract=contract,
            contract_identity=retained_contract_identity,
            manifest=manifest,
            batch=batch,
            task_index=task_index,
        )
    )
    verifier_runtime = _mapping(
        verifier_completion["execution"], label="verifier runtime"
    )
    if (
        verifier_runtime["execution_id"] != terminal["execution_id"]
        or verifier_runtime["execution_uid"] != terminal["execution_uid"]
    ):
        raise CorpusParametricTransportError(
            "verifier output execution differs from terminal metadata"
        )
    producer_close_identity, closed = _reopen_producer_close(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        manifest=manifest,
        task_index=task_index,
    )
    expected_prefix_identities = _task_prefix_identity_set_before_acceptance(
        storage=storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        manifest=manifest,
        task_index=task_index,
    )
    _require_exact_inventory(
        storage,
        prefix=str(task["variant_output_prefix"]),
        identities=expected_prefix_identities,
        label="preacceptance task",
    )
    acceptance = _self_hash({
        "schema_version": TASK_ACCEPTANCE_SCHEMA,
        "accepted_at_utc": _timestamp(
            created_at_utc, label="task acceptance timestamp"
        ),
        "transport_contract": retained_contract_identity.as_dict(),
        "retrieval_task0_prerequisite_identity": contract[
            "retrieval_task0_prerequisite_identity"
        ],
        "task_index": task_index,
        "task_sha256": task["task_sha256"],
        "producer_close": producer_close_identity,
        "science_terminal": closed["science_terminal_identity"],
        "task_result": closed["task_result_identity"],
        "verifier_worker_completion": verifier_completion_identity,
        "independent_verification": verifier_completion[
            "independent_verification"
        ],
        "independent_verification_sha256": verification[
            "verification_sha256"
        ],
        "verifier_terminal_execution": terminal,
        "terminal_governance_census": terminal_census,
        "evidence_object_count": 140,
        "complete_evidence_receipt": True,
        "independent_verification_complete": True,
        "strict_verifier_terminal_success": True,
        "accepted": True,
        "partial_result": False,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, field="task_acceptance_sha256")
    acceptance_identity = storage.publish_or_reopen(
        str(task["accepted_terminal_uri"]), canonical_json_bytes(acceptance)
    )
    _require_exact_inventory(
        storage,
        prefix=str(task["variant_output_prefix"]),
        identities=[*expected_prefix_identities, acceptance_identity],
        label="accepted task",
    )
    return {
        "schema_version": "corpus-parametric-task-accepted/v1",
        "task_index": task_index,
        "task_acceptance": acceptance_identity,
        "task_result": closed["task_result_identity"],
        "independent_verification": verifier_completion[
            "independent_verification"
        ],
        "accepted": True,
        "partial_result": False,
    }


def _reopen_task_acceptance(
    *,
    storage: ObjectStore,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    manifest: Mapping[str, object],
    batch: object,
    task_index: int,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    task = _task_contract(contract, task_index)
    identity, raw = storage.resolve_current(str(task["accepted_terminal_uri"]))
    acceptance = dict(
        _mapping(
            strict_json_bytes(raw, label="task acceptance"),
            label="task acceptance",
        )
    )
    _validate_self_hash(
        acceptance,
        field="task_acceptance_sha256",
        label="task acceptance",
    )
    if (
        acceptance.get("schema_version") != TASK_ACCEPTANCE_SCHEMA
        or acceptance.get("transport_contract") != contract_identity.as_dict()
        or acceptance.get("retrieval_task0_prerequisite_identity")
        != contract["retrieval_task0_prerequisite_identity"]
        or acceptance.get("task_index") != task_index
        or acceptance.get("task_sha256") != task["task_sha256"]
        or acceptance.get("evidence_object_count") != 140
        or acceptance.get("complete_evidence_receipt") is not True
        or acceptance.get("independent_verification_complete") is not True
        or acceptance.get("strict_verifier_terminal_success") is not True
        or acceptance.get("accepted") is not True
        or acceptance.get("partial_result") is not False
        or any(acceptance.get(key) is not False for key in (
            "automatic_retry_licensed",
            "uses_realized_outcomes",
            "historical_scoring_licensed",
            "corpus_fill_licensed",
            "graph_mutation_licensed",
            "production_change_licensed",
            "decision_authority",
        ))
    ):
        raise CorpusParametricTransportError("task acceptance law differs")
    _, closed = _reopen_producer_close(
        storage=storage,
        contract=contract,
        contract_identity=contract_identity,
        manifest=manifest,
        task_index=task_index,
    )
    _, verifier_completion, verification = _reopen_verifier_completion(
        storage=storage,
        contract=contract,
        contract_identity=contract_identity,
        manifest=manifest,
        batch=batch,
        task_index=task_index,
    )
    verifier_terminal = _mapping(
        acceptance.get("verifier_terminal_execution"),
        label="accepted verifier terminal execution",
    )
    _validate_terminal_census_receipt(
        acceptance.get("terminal_governance_census"),
        contract=contract,
        task_index=task_index,
        phase="verifier",
        terminal=verifier_terminal,
    )
    if (
        acceptance["task_result"] != closed["task_result_identity"]
        or acceptance["science_terminal"] != closed["science_terminal_identity"]
        or acceptance["independent_verification"]
        != verifier_completion["independent_verification"]
        or acceptance["independent_verification_sha256"]
        != verification["verification_sha256"]
    ):
        raise CorpusParametricTransportError(
            "task acceptance transitive identity differs"
        )
    return identity, acceptance, closed


def finish_batch(
    *,
    storage: ObjectStore,
    contract_identity: object,
    created_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Publish completion only after every ordered task is independently accepted."""
    require_execute_gate(execute=execute, environ=environ)
    retained_contract_identity, contract, batch, manifest = _reopen_contract_graph(
        storage=storage, contract_identity=contract_identity
    )
    retained_results: list[dict[str, object]] = []
    acceptance_identities: list[dict[str, object]] = []
    output_identities: list[dict[str, object]] = [
        object_identity(
            contract["batch_manifest_identity"], label="output manifest"
        ).as_dict(),
        object_identity(
            contract["evidence_contract_identity"], label="output evidence contract"
        ).as_dict(),
        object_identity(
            contract["runtime_iam_evidence_identity"], label="output runtime IAM"
        ).as_dict(),
        object_identity(
            contract["prefix_claim_identity"], label="output prefix claim"
        ).as_dict(),
        retained_contract_identity.as_dict(),
    ]
    prerequisite_identity = object_identity(
        contract["retrieval_task0_prerequisite_identity"],
        label="retrieval task-0 prerequisite output",
    )
    if prerequisite_identity.uri.startswith(str(manifest["output_prefix"])):
        output_identities.append(prerequisite_identity.as_dict())
    for task_index in range(int(contract["task_count"])):
        acceptance_identity, _, closed = _reopen_task_acceptance(
            storage=storage,
            contract=contract,
            contract_identity=retained_contract_identity,
            manifest=manifest,
            batch=batch,
            task_index=task_index,
        )
        acceptance_identities.append(acceptance_identity)
        task_prefix_identities = _task_prefix_identity_set_before_acceptance(
            storage=storage,
            contract=contract,
            contract_identity=retained_contract_identity,
            manifest=manifest,
            task_index=task_index,
        )
        output_identities.extend([
            *task_prefix_identities,
            acceptance_identity,
            object_identity(
                closed["task_result_identity"],
                label=f"task[{task_index}] result output",
            ).as_dict(),
        ])
        retained_results.append({
            "receipt": closed["task_result"],
            "object_identity": closed["task_result_identity"],
        })
    try:
        completion = batch.build_batch_completion_receipt(
            batch_manifest=manifest,
            batch_manifest_identity=contract["batch_manifest_identity"],
            retained_task_results=retained_results,
        )
        batch.validate_batch_completion_receipt(
            completion,
            batch_manifest=manifest,
            batch_manifest_identity=contract["batch_manifest_identity"],
            retained_task_results=retained_results,
        )
    except Exception as exc:
        raise CorpusParametricTransportError(
            "complete batch matrix cannot be finalized"
        ) from exc
    if len({_identity_key(value) for value in output_identities}) != len(
        output_identities
    ):
        raise CorpusParametricTransportError(
            "complete batch output identity set repeats"
        )
    completion_uri = _batch_completion_uri(manifest)
    acceptance_uri = _batch_acceptance_uri(manifest)
    optional_finishers = _require_inventory_allowing_current(
        storage,
        prefix=str(manifest["output_prefix"]),
        identities=output_identities,
        optional_uris=[completion_uri, acceptance_uri],
        label="batch precompletion",
    )
    if acceptance_uri in optional_finishers and completion_uri not in (
        optional_finishers
    ):
        raise CorpusParametricTransportError(
            "batch acceptance exists without its completion; refusing repair"
        )
    completion_identity = storage.publish_or_reopen(
        completion_uri, batch.canonical_json_bytes(completion)
    )
    before_acceptance_identities = [*output_identities, completion_identity]
    _require_inventory_allowing_current(
        storage,
        prefix=str(manifest["output_prefix"]),
        identities=before_acceptance_identities,
        optional_uris=[acceptance_uri],
        label="batch preacceptance",
    )
    before_acceptance_inventory = _inventory_rows(before_acceptance_identities)
    acceptance = _self_hash({
        "schema_version": BATCH_ACCEPTANCE_SCHEMA,
        "accepted_at_utc": _timestamp(
            created_at_utc, label="batch acceptance timestamp"
        ),
        "transport_contract": retained_contract_identity.as_dict(),
        "retrieval_task0_prerequisite_identity": contract[
            "retrieval_task0_prerequisite_identity"
        ],
        "batch_mode": contract["batch_mode"],
        "batch_completion": completion_identity,
        "task_acceptances": acceptance_identities,
        "task_count": contract["task_count"],
        "parameter_set_count": 7,
        "matrix_cell_count": contract["matrix_cell_count"],
        "output_inventory_before_batch_acceptance": before_acceptance_inventory,
        "output_inventory_before_batch_acceptance_sha256": canonical_sha256(
            before_acceptance_inventory
        ),
        "output_object_count_before_batch_acceptance": len(
            before_acceptance_inventory
        ),
        "complete": True,
        "accepted": True,
        "partial_result": False,
        "independent_verification_complete_for_every_task": True,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, field="batch_acceptance_sha256")
    acceptance_identity = storage.publish_or_reopen(
        acceptance_uri, canonical_json_bytes(acceptance)
    )
    final_identities = [*before_acceptance_identities, acceptance_identity]
    _require_exact_inventory(
        storage,
        prefix=str(manifest["output_prefix"]),
        identities=final_identities,
        label="accepted complete batch",
    )
    final_inventory = _inventory_rows(final_identities)
    return {
        "schema_version": "corpus-parametric-batch-accepted/v1",
        "batch_mode": contract["batch_mode"],
        "task_count": contract["task_count"],
        "matrix_cell_count": contract["matrix_cell_count"],
        "batch_completion": completion_identity,
        "batch_acceptance": acceptance_identity,
        "final_output_inventory_sha256": canonical_sha256(final_inventory),
        "final_output_object_count": len(final_inventory),
        "complete": True,
        "accepted": True,
    }


def _identity_from_args(args: argparse.Namespace, prefix: str) -> ObjectIdentity:
    return object_identity(
        {
            "uri": getattr(args, f"{prefix}_uri"),
            "generation": getattr(args, f"{prefix}_generation"),
            "sha256": getattr(args, f"{prefix}_sha256"),
            "bytes": getattr(args, f"{prefix}_bytes"),
        },
        label=f"{prefix} CLI identity",
    )


def _add_identity_arguments(parser: argparse.ArgumentParser, prefix: str) -> None:
    option = prefix.replace("_", "-")
    parser.add_argument(f"--{option}-uri", required=True)
    parser.add_argument(f"--{option}-generation", required=True)
    parser.add_argument(f"--{option}-sha256", required=True)
    parser.add_argument(f"--{option}-bytes", required=True, type=int)


def _existing_absolute_directory(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise argparse.ArgumentTypeError(
            "repository root must be an existing absolute nonsymlink directory"
        )
    return path.resolve(strict=True)


def _read_external_file(path: Path, *, label: str) -> object:
    if path.is_symlink() or not path.is_file():
        raise CorpusParametricTransportError(f"{label} file is absent/unsafe")
    return external_json_bytes(path.read_bytes(), label=label)


def _print_json(value: object) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(value))


def _base_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Default-off governed corpus parametric transport"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("parked", help="safe default; performs no work")

    canonicalize = sub.add_parser(
        "canonicalize-external-json", help="canonicalize one captured JSON file"
    )
    canonicalize.add_argument("--input", required=True, type=Path)
    canonicalize.add_argument("--output", required=True, type=Path)

    validate_contract = sub.add_parser(
        "validate-local-contract", help="validate a local canonical contract"
    )
    validate_contract.add_argument("--contract-file", required=True, type=Path)

    dry = sub.add_parser(
        "dry-run-worker-args", help="render exact worker argv without cloud access"
    )
    dry.add_argument("--contract-file", required=True, type=Path)
    _add_identity_arguments(dry, "contract")
    dry.add_argument("--task-index", required=True, type=int)
    dry.add_argument("--phase", required=True, choices=("producer", "verifier"))

    configure = sub.add_parser(
        "configure", help="publish immutable create-once governance"
    )
    for prefix in ("manifest", "evidence_contract", "retrieval_prerequisite"):
        _add_identity_arguments(configure, prefix)
    configure.add_argument("--runtime-iam-file", required=True, type=Path)
    configure.add_argument("--build-metadata-file", required=True, type=Path)
    configure.add_argument("--job-file", required=True, type=Path)
    configure.add_argument("--executions-file", required=True, type=Path)
    configure.add_argument("--schedulers-file", required=True, type=Path)
    configure.add_argument("--build-id", required=True)
    configure.add_argument("--code-sha", required=True)
    configure.add_argument("--image", required=True)
    configure.add_argument("--service-account", required=True)
    configure.add_argument("--created-at-utc", required=True)
    configure.add_argument("--all-regions-complete", action="store_true")
    configure.add_argument("--execute", action="store_true")

    validate = sub.add_parser(
        "validate-only", help="reopen and validate one task without solving"
    )
    _add_identity_arguments(validate, "contract")
    validate.add_argument("--task-index", required=True, type=int)
    validate.add_argument(
        "--repository-root", required=True, type=_existing_absolute_directory
    )
    validate.add_argument("--execute", action="store_true")

    consume = sub.add_parser(
        "consume-launch", help="consume one producer/verifier launch authority"
    )
    _add_identity_arguments(consume, "contract")
    consume.add_argument("--task-index", required=True, type=int)
    consume.add_argument("--phase", required=True, choices=("producer", "verifier"))
    consume.add_argument("--job-file", required=True, type=Path)
    consume.add_argument("--executions-file", required=True, type=Path)
    consume.add_argument("--schedulers-file", required=True, type=Path)
    consume.add_argument("--all-regions-complete", action="store_true")
    consume.add_argument("--created-at-utc", required=True)
    consume.add_argument("--execute", action="store_true")

    bind = sub.add_parser(
        "bind-execution", help="census-only execution-name recovery"
    )
    _add_identity_arguments(bind, "contract")
    bind.add_argument("--task-index", required=True, type=int)
    bind.add_argument("--phase", required=True, choices=("producer", "verifier"))
    bind.add_argument("--execution-metadata-file", required=True, type=Path)
    bind.add_argument("--job-file", required=True, type=Path)
    bind.add_argument("--executions-file", required=True, type=Path)
    bind.add_argument("--schedulers-file", required=True, type=Path)
    bind.add_argument("--all-regions-complete", action="store_true")
    bind.add_argument("--created-at-utc", required=True)
    bind.add_argument("--execute", action="store_true")

    recover = sub.add_parser(
        "recover-name", help="read-only census recovery of one execution name"
    )
    _add_identity_arguments(recover, "contract")
    recover.add_argument("--task-index", required=True, type=int)
    recover.add_argument("--phase", required=True, choices=("producer", "verifier"))
    recover.add_argument("--executions-file", required=True, type=Path)
    recover.add_argument("--execute", action="store_true")

    producer = sub.add_parser(
        "execute-task", help="Cloud Run producer worker"
    )
    _add_identity_arguments(producer, "contract")
    producer.add_argument("--task-index", required=True, type=int)
    producer.add_argument(
        "--repository-root",
        default=str(Path(__file__).resolve().parents[1]),
        type=_existing_absolute_directory,
    )
    producer.add_argument("--execute", action="store_true")

    verifier = sub.add_parser(
        "verify-task", help="independent Cloud Run verifier worker"
    )
    _add_identity_arguments(verifier, "contract")
    verifier.add_argument("--task-index", required=True, type=int)
    verifier.add_argument(
        "--repository-root",
        default=str(Path(__file__).resolve().parents[1]),
        type=_existing_absolute_directory,
    )
    verifier.add_argument("--execute", action="store_true")

    close = sub.add_parser(
        "close-producer", help="publish science terminal and task result"
    )
    _add_identity_arguments(close, "contract")
    close.add_argument("--task-index", required=True, type=int)
    close.add_argument("--execution-metadata-file", required=True, type=Path)
    close.add_argument("--job-file", required=True, type=Path)
    close.add_argument("--executions-file", required=True, type=Path)
    close.add_argument("--schedulers-file", required=True, type=Path)
    close.add_argument("--all-regions-complete", action="store_true")
    close.add_argument("--created-at-utc", required=True)
    close.add_argument("--execute", action="store_true")

    accept = sub.add_parser(
        "accept-task", help="publish final accepted terminal after verification"
    )
    _add_identity_arguments(accept, "contract")
    accept.add_argument("--task-index", required=True, type=int)
    accept.add_argument("--execution-metadata-file", required=True, type=Path)
    accept.add_argument("--job-file", required=True, type=Path)
    accept.add_argument("--executions-file", required=True, type=Path)
    accept.add_argument("--schedulers-file", required=True, type=Path)
    accept.add_argument("--all-regions-complete", action="store_true")
    accept.add_argument("--created-at-utc", required=True)
    accept.add_argument("--execute", action="store_true")

    finish = sub.add_parser(
        "finish-batch", help="accept only the complete ordered task matrix"
    )
    _add_identity_arguments(finish, "contract")
    finish.add_argument("--created-at-utc", required=True)
    finish.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "parked":
            _print_json({
                "schema_version": "corpus-parametric-transport-parked/v1",
                "enabled": False,
                "cloud_client_constructed": False,
                "solve_invoked": False,
                "automatic_retry_licensed": False,
            })
            return 0
        if args.command == "canonicalize-external-json":
            source = Path(args.input)
            value = external_json_bytes(source.read_bytes(), label="external JSON")
            raw = canonical_json_bytes(value)
            _write_once(Path(args.output), raw)
            _print_json({
                "output": str(Path(args.output)),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            })
            return 0
        if args.command == "validate-local-contract":
            contract = validate_transport_contract(
                _load_json(Path(args.contract_file), label="local contract")
            )
            _print_json({
                "valid": True,
                "batch_mode": contract["batch_mode"],
                "task_count": contract["task_count"],
                "matrix_cell_count": contract["matrix_cell_count"],
            })
            return 0
        if args.command == "dry-run-worker-args":
            contract = validate_transport_contract(
                _load_json(Path(args.contract_file), label="local contract")
            )
            _task_contract(contract, args.task_index)
            rendered = cloud_worker_args(
                phase=args.phase,
                contract_identity=_identity_from_args(args, "contract").as_dict(),
                task_index=args.task_index,
            )
            _print_json({
                "phase": args.phase,
                "task_index": args.task_index,
                "worker_args": rendered,
                "worker_args_sha256": canonical_sha256(rendered),
                "cloud_call_made": False,
                "launch_authority_consumed": False,
            })
            return 0

        execute = bool(args.execute)
        require_execute_gate(execute=execute, environ=os.environ)
        store = GenerationPinnedStorage(execute=execute, environ=os.environ)
        if args.command == "configure":
            result = configure_transport(
                storage=store,
                batch_manifest_identity=_identity_from_args(args, "manifest").as_dict(),
                evidence_contract_identity=_identity_from_args(
                    args, "evidence_contract"
                ).as_dict(),
                retrieval_prerequisite_identity=_identity_from_args(
                    args, "retrieval_prerequisite"
                ).as_dict(),
                runtime_iam_evidence_raw=Path(args.runtime_iam_file).read_bytes(),
                build_metadata=_read_external_file(
                    Path(args.build_metadata_file), label="build metadata"
                ),
                build_id=args.build_id,
                code_sha=args.code_sha,
                image=args.image,
                service_account=args.service_account,
                parked_job=_read_external_file(Path(args.job_file), label="job"),
                executions=_read_external_file(
                    Path(args.executions_file), label="executions"
                ),
                schedulers=_read_external_file(
                    Path(args.schedulers_file), label="schedulers"
                ),
                all_regions_complete=args.all_regions_complete,
                created_at_utc=args.created_at_utc,
                execute=execute,
                environ=os.environ,
            )
        elif args.command == "validate-only":
            result = validate_task_inputs(
                storage=store,
                contract_identity=_identity_from_args(args, "contract").as_dict(),
                task_index=args.task_index,
                repository_root=args.repository_root,
            )
        elif args.command == "consume-launch":
            result = consume_phase_launch(
                storage=store,
                contract_identity=_identity_from_args(args, "contract").as_dict(),
                task_index=args.task_index,
                phase=args.phase,
                parked_job=_read_external_file(Path(args.job_file), label="job"),
                executions=_read_external_file(
                    Path(args.executions_file), label="executions"
                ),
                schedulers=_read_external_file(
                    Path(args.schedulers_file), label="schedulers"
                ),
                all_regions_complete=args.all_regions_complete,
                created_at_utc=args.created_at_utc,
                execute=execute,
                environ=os.environ,
            )
        elif args.command == "bind-execution":
            result = bind_phase_execution(
                storage=store,
                contract_identity=_identity_from_args(args, "contract").as_dict(),
                task_index=args.task_index,
                phase=args.phase,
                execution_metadata=_read_external_file(
                    Path(args.execution_metadata_file),
                    label="execution metadata",
                ),
                parked_job=_read_external_file(Path(args.job_file), label="job"),
                executions=_read_external_file(
                    Path(args.executions_file), label="executions"
                ),
                schedulers=_read_external_file(
                    Path(args.schedulers_file), label="schedulers"
                ),
                all_regions_complete=args.all_regions_complete,
                created_at_utc=args.created_at_utc,
                execute=execute,
                environ=os.environ,
            )
        elif args.command == "recover-name":
            result = recover_phase_execution_name(
                storage=store,
                contract_identity=_identity_from_args(args, "contract").as_dict(),
                task_index=args.task_index,
                phase=args.phase,
                executions=_read_external_file(
                    Path(args.executions_file), label="executions"
                ),
                execute=execute,
                environ=os.environ,
            )
        elif args.command == "execute-task":
            result = execute_producer_task(
                storage=store,
                contract_identity=_identity_from_args(args, "contract").as_dict(),
                task_index=args.task_index,
                repository_root=args.repository_root,
                execute=execute,
                environ=os.environ,
            )
        elif args.command == "verify-task":
            result = execute_verifier_task(
                storage=store,
                contract_identity=_identity_from_args(args, "contract").as_dict(),
                task_index=args.task_index,
                repository_root=args.repository_root,
                execute=execute,
                environ=os.environ,
            )
        elif args.command == "close-producer":
            result = close_producer_task(
                storage=store,
                contract_identity=_identity_from_args(args, "contract").as_dict(),
                task_index=args.task_index,
                terminal_execution_metadata=_read_external_file(
                    Path(args.execution_metadata_file),
                    label="terminal execution",
                ),
                parked_job=_read_external_file(Path(args.job_file), label="job"),
                executions=_read_external_file(
                    Path(args.executions_file), label="executions"
                ),
                schedulers=_read_external_file(
                    Path(args.schedulers_file), label="schedulers"
                ),
                all_regions_complete=args.all_regions_complete,
                created_at_utc=args.created_at_utc,
                execute=execute,
                environ=os.environ,
            )
        elif args.command == "accept-task":
            result = accept_verified_task(
                storage=store,
                contract_identity=_identity_from_args(args, "contract").as_dict(),
                task_index=args.task_index,
                terminal_execution_metadata=_read_external_file(
                    Path(args.execution_metadata_file),
                    label="terminal execution",
                ),
                parked_job=_read_external_file(Path(args.job_file), label="job"),
                executions=_read_external_file(
                    Path(args.executions_file), label="executions"
                ),
                schedulers=_read_external_file(
                    Path(args.schedulers_file), label="schedulers"
                ),
                all_regions_complete=args.all_regions_complete,
                created_at_utc=args.created_at_utc,
                execute=execute,
                environ=os.environ,
            )
        elif args.command == "finish-batch":
            result = finish_batch(
                storage=store,
                contract_identity=_identity_from_args(args, "contract").as_dict(),
                created_at_utc=args.created_at_utc,
                execute=execute,
                environ=os.environ,
            )
        else:  # pragma: no cover - argparse makes this unreachable.
            raise CorpusParametricTransportError("unknown command")
        _print_json(result)
        return 0
    except (CorpusParametricTransportError, OSError, ValueError) as exc:
        parser.exit(2, f"corpus parametric transport refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
