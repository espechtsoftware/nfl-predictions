#!/usr/bin/env python3
"""Run the frozen-snapshot construction x allocation cross as 54 shards.

This operator is deliberately narrower than a deployment controller.  It can
prepare immutable inputs, run one explicitly armed ordinal, perform an
outcome-blind task-0 smoke, and collect already-published deterministic shard
URIs.  It cannot create/update a Cloud Run job, launch an execution, list an
object prefix, read outcomes, grade results, or relaunch work automatically.

The expensive worker reuses the exact score-blind snapshots published by the
2026-08-29 boom-first replay.  Each task opens one snapshot, its R0--R4 world
artifacts, and one typed *non-evaluation* audit placeholder.  The collector
resolves every known shard name to an immutable generation without listing,
then delegates selection-first / terminal-root-last publication and complete
upstream replay to the hardened construction-allocation operator.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Final, Protocol


ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from nfl_dfs.research import (  # noqa: E402
    boom_first_historical_construction_snapshot_adapter_v1 as snapshot_adapter,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_construction_allocation_cross_operator_v1 as operator,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_construction_allocation_cross_v1 as cross,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_construction_allocation_shard_v1 as shard_science,
)


INPUT_MANIFEST_SCHEMA: Final = (
    "corpus-r6-construction-allocation-snapshot-shard-manifest/v1"
)
PREPARE_RESULT_SCHEMA: Final = (
    "corpus-r6-construction-allocation-snapshot-shard-prepare/v1"
)
TASK_RESULT_SCHEMA: Final = (
    "corpus-r6-construction-allocation-snapshot-shard-task/v1"
)
SMOKE_RESULT_SCHEMA: Final = (
    "corpus-r6-construction-allocation-snapshot-shard-task0-smoke/v1"
)
COLLECT_RESULT_SCHEMA: Final = (
    "corpus-r6-construction-allocation-snapshot-shard-collect/v1"
)
LEGACY_MANIFEST_SCHEMA: Final = "corpus-r6-boom-first-allocation-manifest/v2"

ENABLE_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_ENABLE"
ENABLE_VALUE: Final = "I_UNDERSTAND_SCORE_BLIND_CONSTRUCTION_CROSS_V1"
MANIFEST_IDENTITY_ENV: Final = (
    "R6_CONSTRUCTION_ALLOCATION_SNAPSHOT_SHARD_MANIFEST_IDENTITY"
)
CODE_SHA_ENV: Final = "CODE_SHA"
IMAGE_DIGEST_ENV: Final = "IMAGE_DIGEST"
TASK_INDEX_ENV: Final = "CLOUD_RUN_TASK_INDEX"
TASK_COUNT_ENV: Final = "CLOUD_RUN_TASK_COUNT"
TASK_ATTEMPT_ENV: Final = "CLOUD_RUN_TASK_ATTEMPT"
CLOUD_RUN_JOB_ENV: Final = "CLOUD_RUN_JOB"
CLOUD_RUN_EXECUTION_ENV: Final = "CLOUD_RUN_EXECUTION"

FROZEN_BOOM_FIRST_MANIFEST_IDENTITY: dict[str, object] = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-boom-first-allocation/"
        "20260829-boom-first-68873f42-git-v1/manifest.json"
    ),
    "generation": "1788039789304897",
    "sha256": "8db332783ee3da9f3175f3f867f0e007a5f776958b8d4749c9756e3ae3f51e80",
    "bytes": 41_769,
}

OUTPUT_ROOT: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-construction-allocation-snapshot-shards/"
)
MAX_REQUEST_BYTES: Final = 2_000_000
MAX_INPUT_MANIFEST_BYTES: Final = 2_000_000
MAX_LEGACY_MANIFEST_BYTES: Final = 2_000_000
MAX_GENERATION_SNAPSHOT_BYTES: Final = 8_000_000
MAX_ATTESTATION_BYTES: Final = 256_000
MAX_PLACEHOLDER_BYTES: Final = 64_000
MAX_SHARD_BYTES: Final = 2_000_000_000
GCS_TIMEOUT_SECONDS: Final = 300

_SHA = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE = re.compile(r"^sha256:[0-9a-f]{64}$")
_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")


class SnapshotShardRunnerError(RuntimeError):
    """A frozen input, runtime authority, shard, or publication differed."""


class ExactStore(Protocol):
    def read_exact(self, identity: Mapping[str, object]) -> bytes: ...

    def publish_create_once(
        self, uri: str, raw: bytes,
    ) -> Mapping[str, object]: ...

    def resolve_known(
        self, uri: str, maximum_bytes: int,
    ) -> Mapping[str, object]: ...


class BuildProvider(Protocol):
    def observe_runtime_build(
        self, expected_attestation: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def observe_runtime_execution(
        self, expected_attestation: Mapping[str, object],
    ) -> Mapping[str, object]: ...


def _fail(message: str) -> None:
    raise SnapshotShardRunnerError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _canonical(value: object) -> bytes:
    try:
        return cross.canonical_json_bytes(value)
    except cross.ConstructionAllocationCrossError as exc:
        raise SnapshotShardRunnerError(str(exc)) from exc


def _document(value: Mapping[str, object]) -> bytes:
    return _canonical(dict(value)) + b"\n"


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(
    value: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    return {**body, field: _hash(body)}


def _identity(
    value: object, *, label: str, expected_uri: str | None = None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not one exact content identity")
    uri = value.get("uri")
    generation = value.get("generation")
    digest = value.get("sha256")
    size = value.get("bytes")
    if (
        type(uri) is not str
        or not uri.startswith("gs://")
        or type(generation) not in {str, int}
        or not str(generation)
        or type(digest) is not str
        or _SHA.fullmatch(digest) is None
        or type(size) is not int
        or size <= 0
        or (expected_uri is not None and uri != expected_uri)
    ):
        _fail(f"{label} content identity differs")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": digest,
        "bytes": size,
    }


def _published_identity(
    value: object, *, label: str, uri: str, raw: bytes,
) -> dict[str, object]:
    identity = _identity(value, label=label, expected_uri=uri)
    if (
        not isinstance(value, Mapping)
        or value.get("create_once") is not True
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} create-once identity differs")
    return {**identity, "create_once": True}


def _read_exact(
    identity_value: object, *, store: ExactStore, label: str,
    maximum_bytes: int,
) -> tuple[bytes, dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds its exact byte ceiling")
    try:
        raw = store.read_exact(identity)
    except Exception as exc:
        raise SnapshotShardRunnerError(
            f"{label} generation-exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-exact bytes differ")
    return raw, identity


def _parse_document(
    raw: bytes, *, label: str, newline: bool | None,
) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} bytes differ")
    if newline is True and not raw.endswith(b"\n"):
        _fail(f"{label} is not newline-terminated")
    if newline is False and raw.endswith(b"\n"):
        _fail(f"{label} unexpectedly carries a newline")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotShardRunnerError(f"{label} JSON differs") from exc
    body = _mapping(value, label=label)
    allowed = {_canonical(body), _document(body)} if newline is None else {
        _document(body) if newline else _canonical(body)
    }
    if raw not in allowed:
        _fail(f"{label} canonical JSON replay differs")
    return body


def _output_prefix(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith(OUTPUT_ROOT)
        or not value.endswith("/")
        or "//" in value[5:]
        or any(part in {"", ".", ".."} for part in value[5:].split("/")[:-1])
    ):
        _fail("snapshot-shard output prefix differs")
    return value


def _run_prefix(output_prefix: str, run_id: str) -> str:
    prefix = _output_prefix(output_prefix)
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("snapshot-shard run ID differs")
    return f"{prefix}{run_id}/"


def _utc_timestamp(value: object, *, label: str) -> str:
    if type(value) is not str or not value.endswith("Z"):
        _fail(f"{label} must be one explicit UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise SnapshotShardRunnerError(f"{label} differs") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _fail(f"{label} is not UTC")
    return value


def _manifest_uri(output_prefix: str, run_id: str) -> str:
    return f"{_run_prefix(output_prefix, run_id)}input-manifest.json"


def _placeholder_uri(output_prefix: str, run_id: str, ordinal: int, slate_id: str) -> str:
    return (
        f"{_run_prefix(output_prefix, run_id)}authorities/"
        f"audit-placeholders/{ordinal:02d}-{slate_id}.json"
    )


def _shard_uri(output_prefix: str, run_id: str, ordinal: int, slate_id: str) -> str:
    return f"{_run_prefix(output_prefix, run_id)}shards/{ordinal:02d}-{slate_id}.json"


def _selection_uri(output_prefix: str, run_id: str) -> str:
    return f"{_run_prefix(output_prefix, run_id)}selection.json"


def _terminal_uri(output_prefix: str, run_id: str) -> str:
    return f"{_run_prefix(output_prefix, run_id)}terminal.json"


def validate_frozen_boom_first_manifest_v1(
    value: object, *, exact_raw: bytes, exact_identity: object,
) -> dict[str, object]:
    """Validate the exact prior manifest without importing its giant runner."""

    identity = _identity(exact_identity, label="frozen boom-first manifest")
    expected = _identity(
        FROZEN_BOOM_FIRST_MANIFEST_IDENTITY,
        label="expected frozen boom-first manifest",
    )
    if identity != expected:
        _fail("frozen boom-first manifest is not the adopted exact object")
    if (
        len(exact_raw) != identity["bytes"]
        or sha256(exact_raw).hexdigest() != identity["sha256"]
    ):
        _fail("frozen boom-first manifest exact body differs")
    manifest = _mapping(value, label="frozen boom-first manifest")
    if _canonical(manifest) != exact_raw:
        _fail("frozen boom-first manifest canonical body differs")
    body = dict(manifest)
    retained_hash = body.pop("manifest_sha256", None)
    bindings = _sequence(
        manifest.get("task_bindings"), label="frozen task bindings"
    )
    if (
        manifest.get("schema_version") != LEGACY_MANIFEST_SCHEMA
        or retained_hash != _hash(body)
        or manifest.get("manifest_uri") != identity["uri"]
        or manifest.get("task_count") != len(cross.EXPECTED_SLATE_IDS)
        or len(bindings) != len(cross.EXPECTED_SLATE_IDS)
        or manifest.get("task_bindings_sha256") != _hash(bindings)
        or manifest.get("uses_realized_outcomes") is not False
        or manifest.get("target_slate_outcome_columns") != []
    ):
        _fail("frozen boom-first manifest authority differs")
    prefix = manifest.get("output_prefix")
    if type(prefix) is not str or not prefix.startswith("gs://") or not prefix.endswith("/"):
        _fail("frozen boom-first output prefix differs")
    normalized: list[dict[str, object]] = []
    for ordinal, raw_binding in enumerate(bindings):
        binding = _mapping(raw_binding, label=f"frozen task[{ordinal}]")
        slate_id = cross.EXPECTED_SLATE_IDS[ordinal]
        snapshot_identity = _identity(
            binding.get("snapshot_identity"),
            label=f"frozen task[{ordinal}] snapshot",
            expected_uri=f"{prefix}inputs/{ordinal:02d}-{slate_id}.json",
        )
        snapshot_hash = binding.get("generation_snapshot_sha256")
        if (
            set(binding) != {
                "source_ordinal", "slate_id", "snapshot_identity",
                "generation_snapshot_sha256", "result_uri",
            }
            or binding.get("source_ordinal") != ordinal
            or binding.get("slate_id") != slate_id
            or type(snapshot_hash) is not str
            or _SHA.fullmatch(snapshot_hash) is None
            or binding.get("result_uri")
            != f"{prefix}slates/{ordinal:02d}-{slate_id}.json"
        ):
            _fail(f"frozen boom-first task[{ordinal}] binding differs")
        normalized.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "snapshot_identity": snapshot_identity,
            "generation_snapshot_sha256": snapshot_hash,
        })
    return {**manifest, "_normalized_snapshot_bindings": normalized}


def _validate_attestation_bytes(
    raw: bytes, identity_value: object, *, code_sha: str, image_digest: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label="runtime build attestation")
    if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
        _fail("runtime build attestation exact bytes differ")
    body = _parse_document(raw, label="runtime build attestation", newline=None)
    try:
        attestation = operator.validate_runtime_build_attestation_v1(
            body,
            expected_code_sha=code_sha,
            expected_image_digest=image_digest,
        )
    except operator.ConstructionAllocationCrossOperatorError as exc:
        raise SnapshotShardRunnerError(str(exc)) from exc
    return attestation, identity


def prepare_audit_placeholder_documents_v1(
    *, output_prefix: str, run_id: str,
) -> list[dict[str, object]]:
    """Return the 54 deterministic typed placeholder documents, without I/O."""

    rows: list[dict[str, object]] = []
    for ordinal, slate_id in enumerate(cross.EXPECTED_SLATE_IDS):
        placeholder = operator.audit_bank_placeholder_v1(
            slate_id=slate_id,
            placeholder_id=f"construction-cross-{ordinal:02d}-{slate_id}",
        )
        rows.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "uri": _placeholder_uri(output_prefix, run_id, ordinal, slate_id),
            "document": placeholder,
            "raw": _canonical(placeholder),
        })
    return rows


def build_input_manifest_v1(
    *, frozen_manifest_raw: bytes, frozen_manifest_identity: object,
    audit_placeholder_identities: Sequence[Mapping[str, object]],
    runtime_build_attestation_raw: bytes,
    runtime_build_attestation_identity: object,
    panel_identity: object,
    code_sha: str, image_digest: str,
    output_prefix: str, run_id: str, frozen_at: str,
) -> dict[str, object]:
    """Build the self-hashed, fully deterministic 54-task input manifest."""

    if (
        type(code_sha) is not str
        or type(image_digest) is not str
        or _COMMIT.fullmatch(code_sha) is None
        or _IMAGE.fullmatch(image_digest) is None
    ):
        _fail("snapshot-shard code or immutable image differs")
    _run_prefix(output_prefix, run_id)
    retained_run_id = run_id
    retained_frozen_at = _utc_timestamp(frozen_at, label="frozen_at")
    retained_panel = _identity(panel_identity, label="fixed G0 panel")
    if retained_panel != cross.FOUNDRY_G0_PANEL_IDENTITY:
        _fail("snapshot-shard panel is not the full fixed G0 authority")
    frozen_value = _parse_document(
        frozen_manifest_raw, label="frozen boom-first manifest", newline=False
    )
    frozen = validate_frozen_boom_first_manifest_v1(
        frozen_value,
        exact_raw=frozen_manifest_raw,
        exact_identity=frozen_manifest_identity,
    )
    _attestation, attestation_identity = _validate_attestation_bytes(
        runtime_build_attestation_raw,
        runtime_build_attestation_identity,
        code_sha=code_sha,
        image_digest=image_digest,
    )
    placeholders = list(audit_placeholder_identities)
    if len(placeholders) != len(cross.EXPECTED_SLATE_IDS):
        _fail("snapshot-shard placeholder lattice is not exact 54-slate membership")
    task_bindings: list[dict[str, object]] = []
    frozen_bindings = frozen["_normalized_snapshot_bindings"]
    for ordinal, (slate_id, frozen_binding, placeholder_value) in enumerate(zip(
        cross.EXPECTED_SLATE_IDS, frozen_bindings, placeholders, strict=True
    )):
        placeholder = _identity(
            placeholder_value,
            label=f"{slate_id} audit placeholder",
            expected_uri=_placeholder_uri(
                output_prefix, retained_run_id, ordinal, slate_id
            ),
        )
        task_bindings.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "snapshot_identity": frozen_binding["snapshot_identity"],
            "generation_snapshot_sha256": frozen_binding[
                "generation_snapshot_sha256"
            ],
            "audit_placeholder_identity": placeholder,
            "required_world_artifact_blocks": list(cross.SEED_LABELS),
            "shard_uri": _shard_uri(
                output_prefix, retained_run_id, ordinal, slate_id
            ),
        })
    body: dict[str, object] = {
        "schema_version": INPUT_MANIFEST_SCHEMA,
        "version": shard_science.SHARD_VERSION,
        "run_id": retained_run_id,
        "frozen_at": retained_frozen_at,
        "frozen_boom_first_manifest_identity": _identity(
            frozen_manifest_identity, label="frozen boom-first manifest"
        ),
        "frozen_boom_first_manifest_sha256": frozen["manifest_sha256"],
        "frozen_boom_first_task_bindings_sha256": frozen[
            "task_bindings_sha256"
        ],
        "foundry_g0_panel_id": cross.FOUNDRY_G0_PANEL_ID,
        "foundry_g0_panel_identity": retained_panel,
        "expected_slate_ids": list(cross.EXPECTED_SLATE_IDS),
        "code_sha": code_sha,
        "image_digest": image_digest,
        "runtime_build_attestation_identity": attestation_identity,
        "output_prefix": _output_prefix(output_prefix),
        "manifest_uri": _manifest_uri(output_prefix, retained_run_id),
        "selection_uri": _selection_uri(output_prefix, retained_run_id),
        "terminal_uri": _terminal_uri(output_prefix, retained_run_id),
        "task_count": len(cross.EXPECTED_SLATE_IDS),
        "task_bindings": task_bindings,
        "task_bindings_sha256": _hash(task_bindings),
        "execution_contract": {
            "task_selection": "exact-cloud-run-ordinal-only",
            "explicit_enable_environment": ENABLE_ENV,
            "explicit_enable_value_sha256": sha256(
                ENABLE_VALUE.encode("ascii")
            ).hexdigest(),
            "manifest_identity_environment": MANIFEST_IDENTITY_ENV,
            "code_sha_environment": CODE_SHA_ENV,
            "image_digest_environment": IMAGE_DIGEST_ENV,
            "task_index_environment": TASK_INDEX_ENV,
            "task_count_environment": TASK_COUNT_ENV,
            "one_snapshot_per_task": True,
            "required_world_artifact_blocks": list(cross.SEED_LABELS),
            "one_typed_audit_placeholder_per_task": True,
            "audit_placeholder_is_evaluation_authority": False,
            "deterministic_known_name_resolution_without_listing": True,
            "create_once_shards": True,
            "selection_first_terminal_root_last": True,
            "automatic_launch_or_relaunch": False,
            "deployment_mutation": False,
        },
        "target_slate_outcome_columns": [],
        "uses_target_slate_outcomes": False,
        "grading_available": False,
        "automatic_policy_promotion": False,
        "production_policy_authority": False,
    }
    return validate_input_manifest_v1(_with_hash(body, field="manifest_sha256"))


def validate_input_manifest_v1(value: object) -> dict[str, object]:
    manifest = _mapping(value, label="snapshot-shard input manifest")
    body = dict(manifest)
    retained = body.pop("manifest_sha256", None)
    expected_keys = {
        "schema_version", "version", "run_id", "frozen_at",
        "frozen_boom_first_manifest_identity",
        "frozen_boom_first_manifest_sha256",
        "frozen_boom_first_task_bindings_sha256", "foundry_g0_panel_id",
        "foundry_g0_panel_identity", "expected_slate_ids", "code_sha",
        "image_digest", "runtime_build_attestation_identity", "output_prefix",
        "manifest_uri", "selection_uri", "terminal_uri", "task_count",
        "task_bindings", "task_bindings_sha256", "execution_contract",
        "target_slate_outcome_columns", "uses_target_slate_outcomes",
        "grading_available", "automatic_policy_promotion",
        "production_policy_authority", "manifest_sha256",
    }
    if (
        set(manifest) != expected_keys
        or type(retained) is not str
        or _SHA.fullmatch(retained) is None
        or retained != _hash(body)
        or manifest.get("schema_version") != INPUT_MANIFEST_SCHEMA
        or manifest.get("version") != shard_science.SHARD_VERSION
        or type(manifest.get("run_id")) is not str
        or _RUN_ID.fullmatch(manifest.get("run_id", "")) is None
        or _utc_timestamp(manifest.get("frozen_at"), label="frozen_at")
        != manifest.get("frozen_at")
        or type(manifest.get("code_sha")) is not str
        or _COMMIT.fullmatch(manifest.get("code_sha", "")) is None
        or type(manifest.get("image_digest")) is not str
        or _IMAGE.fullmatch(manifest.get("image_digest", "")) is None
        or manifest.get("foundry_g0_panel_id") != cross.FOUNDRY_G0_PANEL_ID
        or _identity(manifest.get("foundry_g0_panel_identity"), label="G0 panel")
        != cross.FOUNDRY_G0_PANEL_IDENTITY
        or _identity(
            manifest.get("frozen_boom_first_manifest_identity"),
            label="frozen boom-first manifest",
        ) != _identity(
            FROZEN_BOOM_FIRST_MANIFEST_IDENTITY,
            label="expected frozen boom-first manifest",
        )
        or _SHA.fullmatch(
            str(manifest.get("frozen_boom_first_manifest_sha256", ""))
        ) is None
        or _SHA.fullmatch(
            str(manifest.get("frozen_boom_first_task_bindings_sha256", ""))
        ) is None
        or manifest.get("expected_slate_ids") != list(cross.EXPECTED_SLATE_IDS)
        or manifest.get("task_count") != len(cross.EXPECTED_SLATE_IDS)
        or manifest.get("target_slate_outcome_columns") != []
        or manifest.get("uses_target_slate_outcomes") is not False
        or manifest.get("grading_available") is not False
        or manifest.get("automatic_policy_promotion") is not False
        or manifest.get("production_policy_authority") is not False
    ):
        _fail("snapshot-shard input manifest authority differs")
    output_prefix = _output_prefix(manifest.get("output_prefix"))
    run_id = str(manifest["run_id"])
    if (
        manifest.get("manifest_uri") != _manifest_uri(output_prefix, run_id)
        or manifest.get("selection_uri") != _selection_uri(output_prefix, run_id)
        or manifest.get("terminal_uri") != _terminal_uri(output_prefix, run_id)
    ):
        _fail("snapshot-shard deterministic root URIs differ")
    _identity(
        manifest.get("runtime_build_attestation_identity"),
        label="runtime build attestation",
    )
    expected_contract = {
        "task_selection": "exact-cloud-run-ordinal-only",
        "explicit_enable_environment": ENABLE_ENV,
        "explicit_enable_value_sha256": sha256(ENABLE_VALUE.encode("ascii")).hexdigest(),
        "manifest_identity_environment": MANIFEST_IDENTITY_ENV,
        "code_sha_environment": CODE_SHA_ENV,
        "image_digest_environment": IMAGE_DIGEST_ENV,
        "task_index_environment": TASK_INDEX_ENV,
        "task_count_environment": TASK_COUNT_ENV,
        "one_snapshot_per_task": True,
        "required_world_artifact_blocks": list(cross.SEED_LABELS),
        "one_typed_audit_placeholder_per_task": True,
        "audit_placeholder_is_evaluation_authority": False,
        "deterministic_known_name_resolution_without_listing": True,
        "create_once_shards": True,
        "selection_first_terminal_root_last": True,
        "automatic_launch_or_relaunch": False,
        "deployment_mutation": False,
    }
    bindings = _sequence(manifest.get("task_bindings"), label="task bindings")
    if (
        manifest.get("execution_contract") != expected_contract
        or len(bindings) != len(cross.EXPECTED_SLATE_IDS)
        or manifest.get("task_bindings_sha256") != _hash(bindings)
    ):
        _fail("snapshot-shard task contract differs")
    for ordinal, (slate_id, raw_binding) in enumerate(zip(
        cross.EXPECTED_SLATE_IDS, bindings, strict=True
    )):
        binding = _mapping(raw_binding, label=f"task binding[{ordinal}]")
        if (
            set(binding) != {
                "source_ordinal", "slate_id", "snapshot_identity",
                "generation_snapshot_sha256", "audit_placeholder_identity",
                "required_world_artifact_blocks", "shard_uri",
            }
            or binding.get("source_ordinal") != ordinal
            or binding.get("slate_id") != slate_id
            or _SHA.fullmatch(
                str(binding.get("generation_snapshot_sha256", ""))
            ) is None
            or binding.get("required_world_artifact_blocks")
            != list(cross.SEED_LABELS)
            or binding.get("shard_uri")
            != _shard_uri(output_prefix, run_id, ordinal, slate_id)
        ):
            _fail(f"snapshot-shard task binding[{ordinal}] differs")
        _identity(binding.get("snapshot_identity"), label=f"{slate_id} snapshot")
        _identity(
            binding.get("audit_placeholder_identity"),
            label=f"{slate_id} audit placeholder",
            expected_uri=_placeholder_uri(output_prefix, run_id, ordinal, slate_id),
        )
    return manifest


def open_input_manifest_v1(
    manifest_identity: object, *, store: ExactStore,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    raw, identity = _read_exact(
        manifest_identity,
        store=store,
        label="snapshot-shard input manifest",
        maximum_bytes=MAX_INPUT_MANIFEST_BYTES,
    )
    manifest = validate_input_manifest_v1(
        _parse_document(raw, label="snapshot-shard input manifest", newline=True)
    )
    if identity["uri"] != manifest["manifest_uri"]:
        _fail("snapshot-shard input manifest URI differs")
    frozen_raw, frozen_identity = _read_exact(
        manifest["frozen_boom_first_manifest_identity"],
        store=store,
        label="frozen boom-first manifest",
        maximum_bytes=MAX_LEGACY_MANIFEST_BYTES,
    )
    frozen = validate_frozen_boom_first_manifest_v1(
        _parse_document(
            frozen_raw, label="frozen boom-first manifest", newline=False
        ),
        exact_raw=frozen_raw,
        exact_identity=frozen_identity,
    )
    if (
        manifest["frozen_boom_first_manifest_sha256"] != frozen["manifest_sha256"]
        or manifest["frozen_boom_first_task_bindings_sha256"]
        != frozen["task_bindings_sha256"]
    ):
        _fail("snapshot-shard frozen-manifest binding differs")
    for current, prior in zip(
        manifest["task_bindings"],
        frozen["_normalized_snapshot_bindings"],
        strict=True,
    ):
        if (
            current["source_ordinal"] != prior["source_ordinal"]
            or current["slate_id"] != prior["slate_id"]
            or current["snapshot_identity"] != prior["snapshot_identity"]
            or current["generation_snapshot_sha256"]
            != prior["generation_snapshot_sha256"]
        ):
            _fail("snapshot-shard exact frozen task projection differs")
    attestation_raw, attestation_identity = _read_exact(
        manifest["runtime_build_attestation_identity"],
        store=store,
        label="runtime build attestation",
        maximum_bytes=MAX_ATTESTATION_BYTES,
    )
    _validate_attestation_bytes(
        attestation_raw,
        attestation_identity,
        code_sha=str(manifest["code_sha"]),
        image_digest=str(manifest["image_digest"]),
    )
    return manifest, identity, frozen


def _publish(
    *, uri: str, value: Mapping[str, object], store: ExactStore,
    maximum_bytes: int,
) -> dict[str, object]:
    raw = _document(value)
    if len(raw) > maximum_bytes:
        _fail("snapshot-shard publication exceeds its exact byte ceiling")
    try:
        published = store.publish_create_once(uri, raw)
    except Exception as exc:
        raise SnapshotShardRunnerError(
            f"create-once publication failed for {uri}"
        ) from exc
    identity = _published_identity(
        published, label="snapshot-shard publication", uri=uri, raw=raw
    )
    reopened, _ = _read_exact(
        identity,
        store=store,
        label="published snapshot-shard object",
        maximum_bytes=maximum_bytes,
    )
    if reopened != raw:
        _fail("snapshot-shard create-once exact reopen differs")
    return identity


def _verify_provider_attestation(
    manifest: Mapping[str, object], *, store: ExactStore,
    provider: BuildProvider,
) -> dict[str, object]:
    raw, identity = _read_exact(
        manifest["runtime_build_attestation_identity"],
        store=store,
        label="runtime build attestation",
        maximum_bytes=MAX_ATTESTATION_BYTES,
    )
    attestation, retained_identity = _validate_attestation_bytes(
        raw,
        identity,
        code_sha=str(manifest["code_sha"]),
        image_digest=str(manifest["image_digest"]),
    )
    observer = getattr(provider, "observe_runtime_build", None)
    if not callable(observer):
        _fail("provider build observer is unavailable")
    try:
        observed = _mapping(
            observer(attestation), label="provider-observed build attestation"
        )
    except Exception as exc:
        raise SnapshotShardRunnerError(
            "provider build attestation observation failed"
        ) from exc
    if observed != attestation:
        _fail("provider build attestation differs from the frozen authority")
    return {
        "identity": retained_identity,
        "build_id": attestation["build_id"],
        "code_sha": attestation["resolved_source_commit"],
        "image_digest": attestation["image_digest"],
        "provider_observed": True,
    }


def _verify_provider_execution_attestation(
    identity_value: object, *, manifest: Mapping[str, object],
    store: ExactStore, provider: BuildProvider,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, identity = _read_exact(
        identity_value,
        store=store,
        label="runtime execution attestation",
        maximum_bytes=MAX_ATTESTATION_BYTES,
    )
    document = _parse_document(
        raw, label="runtime execution attestation", newline=None
    )
    try:
        attestation = operator.validate_runtime_execution_attestation_v1(
            document,
            expected_code_sha=str(manifest["code_sha"]),
            expected_image_digest=str(manifest["image_digest"]),
            expected_task_count=int(manifest["task_count"]),
        )
    except operator.ConstructionAllocationCrossOperatorError as exc:
        raise SnapshotShardRunnerError(str(exc)) from exc
    observer = getattr(provider, "observe_runtime_execution", None)
    if not callable(observer):
        _fail("provider execution observer is unavailable")
    try:
        observed = _mapping(
            observer(attestation),
            label="provider-observed runtime execution attestation",
        )
    except Exception as exc:
        raise SnapshotShardRunnerError(
            "provider runtime execution observation failed"
        ) from exc
    if observed != attestation:
        _fail("provider runtime execution differs from the frozen authority")
    receipt = {
        "identity": identity,
        "job_name": attestation["job_name"],
        "job_generation": attestation["job_generation"],
        "execution_name": attestation["execution_name"],
        "execution_uid": attestation["execution_uid"],
        "task_count": attestation["task_count"],
        "succeeded_count": attestation["succeeded_count"],
        "image_digest": attestation["image_digest"],
        "code_sha": attestation["code_sha"],
        "provider_observed": True,
    }
    return attestation, receipt


def prepare_from_request_v1(
    request: object, *, store: ExactStore, provider: BuildProvider,
) -> dict[str, object]:
    item = _mapping(request, label="snapshot-shard prepare request")
    if set(item) != {
        "frozen_boom_first_manifest_identity",
        "runtime_build_attestation_identity", "panel_identity", "code_sha",
        "image_digest", "output_prefix", "run_id", "frozen_at",
    }:
        _fail("snapshot-shard prepare request fields differ")
    if any(
        type(item.get(field)) is not str
        for field in (
            "code_sha", "image_digest", "output_prefix", "run_id", "frozen_at"
        )
    ):
        _fail("snapshot-shard prepare request scalar types differ")
    frozen_raw, frozen_identity = _read_exact(
        item["frozen_boom_first_manifest_identity"],
        store=store,
        label="frozen boom-first manifest",
        maximum_bytes=MAX_LEGACY_MANIFEST_BYTES,
    )
    attestation_raw, attestation_identity = _read_exact(
        item["runtime_build_attestation_identity"],
        store=store,
        label="runtime build attestation",
        maximum_bytes=MAX_ATTESTATION_BYTES,
    )
    # Validate every non-publication authority before the first write.
    placeholder_documents = prepare_audit_placeholder_documents_v1(
        output_prefix=item["output_prefix"], run_id=item["run_id"]
    )
    provisional = build_input_manifest_v1(
        frozen_manifest_raw=frozen_raw,
        frozen_manifest_identity=frozen_identity,
        audit_placeholder_identities=[{
            "uri": row["uri"], "generation": "provisional",
            "sha256": sha256(row["raw"]).hexdigest(), "bytes": len(row["raw"]),
        } for row in placeholder_documents],
        runtime_build_attestation_raw=attestation_raw,
        runtime_build_attestation_identity=attestation_identity,
        panel_identity=item["panel_identity"], code_sha=item["code_sha"],
        image_digest=item["image_digest"],
        output_prefix=item["output_prefix"], run_id=item["run_id"],
        frozen_at=item["frozen_at"],
    )
    _verify_provider_attestation(provisional, store=store, provider=provider)

    placeholder_identities = [
        _publish(
            uri=str(row["uri"]), value=row["document"], store=store,
            maximum_bytes=MAX_PLACEHOLDER_BYTES,
        )
        for row in placeholder_documents
    ]
    manifest = build_input_manifest_v1(
        frozen_manifest_raw=frozen_raw,
        frozen_manifest_identity=frozen_identity,
        audit_placeholder_identities=placeholder_identities,
        runtime_build_attestation_raw=attestation_raw,
        runtime_build_attestation_identity=attestation_identity,
        panel_identity=item["panel_identity"], code_sha=item["code_sha"],
        image_digest=item["image_digest"],
        output_prefix=item["output_prefix"], run_id=item["run_id"],
        frozen_at=item["frozen_at"],
    )
    manifest_identity = _publish(
        uri=str(manifest["manifest_uri"]), value=manifest, store=store,
        maximum_bytes=MAX_INPUT_MANIFEST_BYTES,
    )
    opened, opened_identity, _ = open_input_manifest_v1(
        manifest_identity, store=store
    )
    if opened != manifest or opened_identity != {
        key: manifest_identity[key] for key in ("uri", "generation", "sha256", "bytes")
    }:
        _fail("snapshot-shard prepared manifest exact reopen differs")
    body = {
        "schema_version": PREPARE_RESULT_SCHEMA,
        "manifest_identity": {
            key: manifest_identity[key]
            for key in ("uri", "generation", "sha256", "bytes")
        },
        "manifest_sha256": manifest["manifest_sha256"],
        "placeholder_count": len(placeholder_identities),
        "task_count": len(manifest["task_bindings"]),
        "provider_build_attestation_verified": True,
        "deployment_mutation_performed": False,
        "execution_launched": False,
        "uses_target_slate_outcomes": False,
        "complete": True,
    }
    return _with_hash(body, field="prepare_sha256")


def _runtime_manifest_identity(
    environment: Mapping[str, str], manifest_identity: object,
) -> dict[str, object]:
    expected = _identity(manifest_identity, label="runtime input manifest")
    raw = environment.get(MANIFEST_IDENTITY_ENV, "")
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SnapshotShardRunnerError(
            "runtime input-manifest identity environment differs"
        ) from exc
    observed = _identity(parsed, label="runtime input manifest environment")
    if observed != expected or raw.encode("ascii") != _canonical(observed):
        _fail("runtime input-manifest identity environment differs")
    return observed


def _runtime_gate(
    manifest: Mapping[str, object], *, environment: Mapping[str, str],
    require_task_ordinal: bool,
) -> int | None:
    if environment.get(ENABLE_ENV) != ENABLE_VALUE:
        _fail(f"snapshot-shard action requires {ENABLE_ENV}={ENABLE_VALUE}")
    if (
        environment.get(CODE_SHA_ENV) != manifest["code_sha"]
        or environment.get(IMAGE_DIGEST_ENV) != manifest["image_digest"]
    ):
        _fail("runtime code/image differs from the frozen snapshot-shard manifest")
    if not require_task_ordinal:
        return None
    try:
        ordinal = int(environment.get(TASK_INDEX_ENV, ""))
        count = int(environment.get(TASK_COUNT_ENV, ""))
    except ValueError as exc:
        raise SnapshotShardRunnerError("runtime task coordinate differs") from exc
    if (
        str(ordinal) != environment.get(TASK_INDEX_ENV)
        or str(count) != environment.get(TASK_COUNT_ENV)
        or count != len(cross.EXPECTED_SLATE_IDS)
        or not 0 <= ordinal < count
    ):
        _fail("runtime task coordinate differs")
    return ordinal


def _runtime_execution_coordinate(
    environment: Mapping[str, str], *, ordinal: int,
) -> dict[str, object]:
    job_name = environment.get(CLOUD_RUN_JOB_ENV, "").strip()
    execution_name = environment.get(CLOUD_RUN_EXECUTION_ENV, "").strip()
    try:
        attempt = int(environment.get(TASK_ATTEMPT_ENV, ""))
        count = int(environment.get(TASK_COUNT_ENV, ""))
    except ValueError as exc:
        raise SnapshotShardRunnerError(
            "runtime Cloud Run execution coordinate differs"
        ) from exc
    if (
        not job_name
        or not execution_name
        or environment.get(TASK_ATTEMPT_ENV) != str(attempt)
        or attempt < 0
        or count != len(cross.EXPECTED_SLATE_IDS)
        or environment.get(TASK_INDEX_ENV) != str(ordinal)
    ):
        _fail("runtime Cloud Run execution coordinate differs")
    return {
        "job_name": job_name,
        "execution_name": execution_name,
        "task_index": ordinal,
        "task_count": count,
        "task_attempt": attempt,
    }


def _early_action_gate(
    environment: Mapping[str, str], *, require_task_ordinal: bool,
) -> None:
    """Reject unarmed/mis-shaped actions before the first object read."""

    if environment.get(ENABLE_ENV) != ENABLE_VALUE:
        _fail(f"snapshot-shard action requires {ENABLE_ENV}={ENABLE_VALUE}")
    if not require_task_ordinal:
        return
    try:
        ordinal = int(environment.get(TASK_INDEX_ENV, ""))
        count = int(environment.get(TASK_COUNT_ENV, ""))
    except ValueError as exc:
        raise SnapshotShardRunnerError("runtime task coordinate differs") from exc
    if (
        environment.get(TASK_INDEX_ENV) != str(ordinal)
        or environment.get(TASK_COUNT_ENV) != str(count)
        or count != len(cross.EXPECTED_SLATE_IDS)
        or not 0 <= ordinal < count
    ):
        _fail("runtime task coordinate differs")


def _validate_placeholder(
    identity_value: object, *, slate_id: str, store: ExactStore,
) -> dict[str, object]:
    raw, identity = _read_exact(
        identity_value,
        store=store,
        label=f"{slate_id} audit placeholder",
        maximum_bytes=MAX_PLACEHOLDER_BYTES,
    )
    document = _parse_document(
        raw, label=f"{slate_id} audit placeholder", newline=None
    )
    placeholder_id = document.get("placeholder_id")
    if type(placeholder_id) is not str:
        _fail(f"{slate_id} audit placeholder ID differs")
    try:
        expected = operator.audit_bank_placeholder_v1(
            slate_id=slate_id, placeholder_id=placeholder_id
        )
    except operator.ConstructionAllocationCrossOperatorError as exc:
        raise SnapshotShardRunnerError(str(exc)) from exc
    if (
        document != expected
        or document.get("evaluation_authority") is not False
        or document.get("independent_bank_available") is not False
        or document.get("opened_during_selection") is not False
    ):
        _fail(f"{slate_id} placeholder cannot be evaluation authority")
    return identity


def _build_one_shard(
    *, manifest: Mapping[str, object], ordinal: int, environment: Mapping[str, str],
    store: ExactStore,
) -> dict[str, object]:
    binding = manifest["task_bindings"][ordinal]
    slate_id = str(binding["slate_id"])
    snapshot_raw, snapshot_identity = _read_exact(
        binding["snapshot_identity"],
        store=store,
        label=f"{slate_id} frozen generation snapshot",
        maximum_bytes=MAX_GENERATION_SNAPSHOT_BYTES,
    )
    try:
        snapshot = snapshot_adapter.frozen_allocation.validate_generation_snapshot_v1(
            _parse_document(
                snapshot_raw,
                label=f"{slate_id} frozen generation snapshot",
                newline=None,
            )
        )
    except Exception as exc:
        raise SnapshotShardRunnerError(
            f"{slate_id} frozen generation snapshot differs"
        ) from exc
    if (
        snapshot.get("generation_snapshot_sha256")
        != binding["generation_snapshot_sha256"]
        or snapshot.get("slate_id") != slate_id
        or snapshot.get("source_ordinal") != ordinal
    ):
        _fail(f"{slate_id} frozen generation snapshot binding differs")

    def _cached_snapshot_read(identity_value: Mapping[str, object]) -> bytes:
        retained = _identity(identity_value, label="snapshot adapter exact read")
        if retained == snapshot_identity:
            return snapshot_raw
        return store.read_exact(retained)

    _validate_placeholder(
        binding["audit_placeholder_identity"], slate_id=slate_id, store=store
    )
    builder = snapshot_adapter.FrozenSnapshotConstructionNativeBookBuilder(
        [snapshot_adapter.FrozenSnapshotBinding(
            snapshot_identity=binding["snapshot_identity"],
            audit_bank_identity=binding["audit_placeholder_identity"],
        )],
        read_exact=_cached_snapshot_read,
        require_exact_panel=False,
    )
    slates = builder.cross_slates()
    if (
        len(slates) != 1
        or slates[0].slate_id != slate_id
        or slates[0].season != int(slate_id[:4])
        or slates[0].week != int(slate_id[-2:])
    ):
        _fail("snapshot adapter returned the wrong task coordinate")
    authority = cross.CrossPanelAuthority(
        panel_id=cross.FOUNDRY_G0_PANEL_ID,
        expected_slate_ids=tuple(cross.EXPECTED_SLATE_IDS),
        identity=dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
    )
    try:
        root = shard_science.build_score_blind_cross_shard_v1(
            slates[0], builder,
            expected_slate_ordinal=ordinal,
            panel_id=str(manifest["run_id"]),
            code_sha=str(manifest["code_sha"]),
            image_digest=str(manifest["image_digest"]),
            panel_authority=authority,
            runtime_execution_coordinate=_runtime_execution_coordinate(
                environment, ordinal=ordinal
            ),
        )
        retained = shard_science.validate_score_blind_cross_shard_v1(root)
    except (
        shard_science.ConstructionAllocationShardError,
        snapshot_adapter.ConstructionSnapshotAdapterError,
    ) as exc:
        raise SnapshotShardRunnerError(str(exc)) from exc
    coordinate = retained.get("expected_slate_coordinate")
    if (
        not isinstance(coordinate, Mapping)
        or coordinate.get("ordinal") != ordinal
        or coordinate.get("slate_id") != slate_id
        or retained.get("code_sha") != manifest["code_sha"]
        or retained.get("image_digest") != manifest["image_digest"]
        or retained.get("uses_target_slate_outcomes") is not False
    ):
        _fail("snapshot-shard worker result authority differs")
    return retained


def execute_task_v1(
    *, manifest_identity: object, environment: Mapping[str, str],
    store: ExactStore, publish: bool = True,
) -> dict[str, object]:
    """Execute exactly the environment-selected ordinal; never launch work."""

    _early_action_gate(environment, require_task_ordinal=True)
    _runtime_manifest_identity(environment, manifest_identity)
    manifest, retained_manifest_identity, _ = open_input_manifest_v1(
        manifest_identity, store=store
    )
    ordinal = _runtime_gate(
        manifest, environment=environment, require_task_ordinal=True
    )
    assert ordinal is not None
    root = _build_one_shard(
        manifest=manifest, ordinal=ordinal, environment=environment, store=store
    )
    binding = manifest["task_bindings"][ordinal]
    if publish:
        root_identity = _publish(
            uri=str(binding["shard_uri"]), value=root, store=store,
            maximum_bytes=MAX_SHARD_BYTES,
        )
    else:
        root_identity = None
    body = {
        "schema_version": TASK_RESULT_SCHEMA if publish else SMOKE_RESULT_SCHEMA,
        "manifest_identity": retained_manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "source_ordinal": ordinal,
        "slate_id": binding["slate_id"],
        "shard_uri": binding["shard_uri"],
        "shard_identity": root_identity,
        "shard_sha256": root["shard_sha256"],
        "scientific_sha256": root["scientific_sha256"],
        "publication_performed": publish,
        "snapshot_and_r0_r4_generation_exact_reads_required": True,
        "audit_placeholder_evaluation_authority": False,
        "deployment_mutation_performed": False,
        "execution_launched": False,
        "uses_target_slate_outcomes": False,
        "complete": True,
    }
    return _with_hash(
        body, field="task_result_sha256" if publish else "smoke_sha256"
    )


def task0_smoke_v1(
    *, manifest_identity: object, environment: Mapping[str, str], store: ExactStore,
) -> dict[str, object]:
    if environment.get(TASK_INDEX_ENV) != "0":
        _fail("snapshot-shard smoke is task-0 only")
    return execute_task_v1(
        manifest_identity=manifest_identity,
        environment=environment,
        store=store,
        publish=False,
    )


def collect_v1(
    *, manifest_identity: object, environment: Mapping[str, str],
    runtime_execution_attestation_identity: object,
    store: ExactStore, provider: BuildProvider,
) -> dict[str, object]:
    """Resolve 54 fixed names, collect, and publish terminal-root-last."""

    _early_action_gate(environment, require_task_ordinal=False)
    _runtime_manifest_identity(environment, manifest_identity)
    manifest, retained_manifest_identity, _ = open_input_manifest_v1(
        manifest_identity, store=store
    )
    _runtime_gate(manifest, environment=environment, require_task_ordinal=False)
    provider_receipt = _verify_provider_attestation(
        manifest, store=store, provider=provider
    )
    _, execution_provider_receipt = _verify_provider_execution_attestation(
        runtime_execution_attestation_identity,
        manifest=manifest,
        store=store,
        provider=provider,
    )
    resolver = getattr(store, "resolve_known", None)
    if not callable(resolver):
        _fail("known-name generation resolver is unavailable")
    roots: list[dict[str, object]] = []
    shard_identities: list[dict[str, object]] = []
    for ordinal, binding in enumerate(manifest["task_bindings"]):
        uri = str(binding["shard_uri"])
        try:
            resolved = resolver(uri, MAX_SHARD_BYTES)
        except Exception as exc:
            raise SnapshotShardRunnerError(
                f"deterministic shard[{ordinal}] is missing or mutable"
            ) from exc
        identity = _identity(
            resolved, label=f"shard[{ordinal}]", expected_uri=uri
        )
        raw, identity = _read_exact(
            identity, store=store, label=f"shard[{ordinal}]",
            maximum_bytes=MAX_SHARD_BYTES,
        )
        root = shard_science.validate_score_blind_cross_shard_v1(
            _parse_document(raw, label=f"shard[{ordinal}]", newline=True)
        )
        coordinate = root["expected_slate_coordinate"]
        if (
            coordinate["ordinal"] != ordinal
            or coordinate["slate_id"] != binding["slate_id"]
            or root["panel_id"] != manifest["run_id"]
            or root["code_sha"] != manifest["code_sha"]
            or root["image_digest"] != manifest["image_digest"]
        ):
            _fail(f"deterministic shard[{ordinal}] authority differs")
        roots.append(root)
        shard_identities.append(identity)
    try:
        selection = shard_science.collect_score_blind_cross_shards_v1(roots)
    except shard_science.ConstructionAllocationShardError as exc:
        raise SnapshotShardRunnerError(str(exc)) from exc
    if (
        selection.get("panel_id") != manifest["run_id"]
        or selection.get("code_sha") != manifest["code_sha"]
        or selection.get("image_digest") != manifest["image_digest"]
    ):
        _fail("collected selection authority differs")
    try:
        ready = operator.prepare_create_once_bundle_v1(
            selection,
            run_id=str(manifest["run_id"]),
            output_prefix=str(manifest["output_prefix"]).rstrip("/"),
            frozen_at=str(manifest["frozen_at"]),
            runtime_build_attestation_identity=manifest[
                "runtime_build_attestation_identity"
            ],
            execution_authority=operator.selection_execution_authority_v1(
                input_manifest_identity=retained_manifest_identity,
                input_manifest_sha256=str(manifest["manifest_sha256"]),
                ordered_shard_identities=shard_identities,
                runtime_execution_attestation_identity=(
                    execution_provider_receipt["identity"]
                ),
            ),
        )
        if (
            ready["selection_uri"] != manifest["selection_uri"]
            or ready["terminal_uri"] != manifest["terminal_uri"]
        ):
            _fail("hardened operator root URIs differ from input manifest")
        envelope = operator.publish_create_once_bundle_v1(
            ready,
            publish_create_once=store.publish_create_once,
            read_exact=store.read_exact,
        )
        reopened = operator.reopen_terminal_bundle_v1(
            envelope, read_exact=store.read_exact
        )
    except operator.ConstructionAllocationCrossOperatorError as exc:
        raise SnapshotShardRunnerError(str(exc)) from exc
    upstream = reopened.get("upstream_reopen_receipt")
    execution_reopen = reopened.get("execution_reopen_receipt")
    if (
        reopened.get("complete") is not True
        or not isinstance(upstream, Mapping)
        or not isinstance(execution_reopen, Mapping)
        or upstream.get("fixed_g0_panel_generation_exact_reopened") is not True
        or upstream.get(
            "runtime_code_image_provider_attestation_exact_reopened"
        ) is not True
        or upstream.get("all_sources_generation_exact_reopened") is not True
        or upstream.get("all_locks_generation_exact_reopened") is not True
        or upstream.get(
            "all_audit_authority_documents_generation_exact_reopened"
        ) is not True
        or upstream.get("unconsumed_audit_placeholder_count")
        != len(cross.EXPECTED_SLATE_IDS)
        or upstream.get("independent_audit_evaluation_authority_available")
        is not False
        or upstream.get("audit_placeholders_have_evaluation_authority")
        is not False
        or upstream.get("outcome_data_accessed") is not False
        or execution_reopen.get(
            "all_shards_generation_exact_reopened"
        ) is not True
        or execution_reopen.get(
            "selection_replayed_from_declared_shards"
        ) is not True
        or execution_reopen.get(
            "all_shards_match_runtime_execution"
        ) is not True
        or execution_reopen.get(
            "runtime_execution_provider_attestation_exact_reopened"
        ) is not True
        or execution_reopen.get("uses_target_slate_outcomes") is not False
    ):
        _fail("hardened terminal did not prove every upstream exact reopen")
    body = {
        "schema_version": COLLECT_RESULT_SCHEMA,
        "manifest_identity": retained_manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "provider_build_receipt": provider_receipt,
        "provider_execution_receipt": execution_provider_receipt,
        "shard_count": len(shard_identities),
        "shard_identities_sha256": _hash(shard_identities),
        "selection_receipt_sha256": selection["receipt_sha256"],
        "terminal_envelope": envelope,
        "terminal_reopen_complete": True,
        "all_shards_resolved_by_deterministic_name_without_listing": True,
        "all_shards_generation_exact_reopened": True,
        "selection_published_before_terminal_root": True,
        "selection_upstream_authorities_generation_exact_reopened": True,
        "input_manifest_and_ordered_shards_generation_exact_reopened": True,
        "runtime_execution_provider_attestation_exact_reopened": True,
        "audit_placeholders_have_evaluation_authority": False,
        "outcome_data_accessed": False,
        "grading_performed": False,
        "deployment_mutation_performed": False,
        "execution_launched": False,
        "automatic_relaunch": False,
        "complete": True,
    }
    return _with_hash(body, field="collect_sha256")


class GCSExactKnownNameStoreV1:
    """GCS transport exposing exact reads, create-once, and known names only."""

    def __init__(self, client: object | None = None) -> None:
        if client is None:
            from google.cloud import storage

            client = storage.Client()
        self._client = client
        self._exact_cache: dict[tuple[str, str, str, int], bytes] = {}

    @staticmethod
    def _cache_key(identity: Mapping[str, object]) -> tuple[str, str, str, int]:
        return (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if type(uri) is not str or not uri.startswith("gs://"):
            _fail("GCS URI differs")
        retained = uri[5:]
        bucket, separator, name = retained.partition("/")
        if not separator or not bucket or not name or "//" in name:
            _fail("GCS URI differs")
        return bucket, name

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        retained = _identity(identity, label="GCS exact read")
        cache_key = self._cache_key(retained)
        # Resolution-to-read reuse is deliberately single-shot.  A collector
        # must not retain all 54 potentially large shard bodies in memory.
        cached = self._exact_cache.pop(cache_key, None)
        if cached is not None:
            return cached
        bucket, name = self._parts(str(retained["uri"]))
        blob = self._client.bucket(bucket).blob(name)
        raw = blob.download_as_bytes(
            if_generation_match=int(str(retained["generation"])),
            timeout=GCS_TIMEOUT_SECONDS,
        )
        if (
            len(raw) != retained["bytes"]
            or sha256(raw).hexdigest() != retained["sha256"]
        ):
            _fail("GCS generation-exact bytes differ")
        self._exact_cache[cache_key] = raw
        return raw

    def resolve_known(self, uri: str, maximum_bytes: int) -> Mapping[str, object]:
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        # This is a metadata lookup for one deterministic name, never a list.
        blob.reload(timeout=GCS_TIMEOUT_SECONDS)
        if blob.generation is None or blob.size is None:
            _fail("known GCS object lacks generation or size")
        generation = int(blob.generation)
        size = int(blob.size)
        if size <= 0 or size > maximum_bytes:
            _fail("known GCS object exceeds its byte ceiling")
        raw = blob.download_as_bytes(
            if_generation_match=generation, timeout=GCS_TIMEOUT_SECONDS
        )
        if len(raw) != size:
            _fail("known GCS object changed during generation resolution")
        identity = {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": size,
        }
        self._exact_cache[self._cache_key(identity)] = raw
        return identity

    def publish_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("GCS create-once bytes differ")
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
                timeout=GCS_TIMEOUT_SECONDS,
            )
            if blob.generation is None:
                _fail("GCS create-once object lacks generation")
            identity = {
                "uri": uri,
                "generation": str(blob.generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
                "create_once": True,
            }
            self._exact_cache[self._cache_key(identity)] = raw
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            prior = _identity(
                self.resolve_known(uri, len(raw)), label="prior create-once object"
            )
            if self.read_exact(prior) != raw:
                raise SnapshotShardRunnerError(
                    "create-once URI already contains different bytes"
                ) from exc
            identity = {**prior, "create_once": True}
        if self.read_exact(identity) != raw:
            _fail("GCS create-once exact reopen differs")
        return identity


class GCloudBuildProviderV1:
    """Read-only Cloud Build and Cloud Run execution observer."""

    def __init__(self, *, project: str = "nfl-predictions-503414") -> None:
        self._project = project

    def observe_runtime_build(
        self, expected_attestation: Mapping[str, object],
    ) -> Mapping[str, object]:
        expected = _mapping(expected_attestation, label="expected build attestation")
        command = [
            "gcloud", "builds", "describe", str(expected["build_id"]),
            "--project", self._project, "--format=json",
        ]
        completed = subprocess.run(
            command, check=True, capture_output=True, text=True
        )
        raw = _mapping(json.loads(completed.stdout), label="Cloud Build observation")
        source = _mapping(raw.get("source"), label="Cloud Build source")
        git_source = _mapping(
            source.get("gitSource"), label="Cloud Build Git source"
        )
        provenance = _mapping(
            raw.get("sourceProvenance"),
            label="Cloud Build source provenance",
        )
        resolved_git_source = _mapping(
            provenance.get("resolvedGitSource"),
            label="Cloud Build resolved Git source",
        )
        substitutions = _mapping(
            raw.get("substitutions"), label="Cloud Build substitutions"
        )
        images = raw.get("results", {}).get("images", []) if isinstance(
            raw.get("results"), Mapping
        ) else []
        expected_digest = str(expected["image_digest"])
        expected_source = {
            "url": expected["source_repository"],
            "revision": expected["resolved_source_commit"],
        }
        matching_images = [
            row for row in images
            if isinstance(row, Mapping)
            and row.get("name") == expected["image_tag"]
            and str(row.get("digest")) in {
                expected_digest,
                expected_digest.removeprefix("sha256:"),
            }
        ]
        if (
            str(raw.get("id")) != expected["build_id"]
            or str(raw.get("status")) != "SUCCESS"
            or git_source != expected_source
            or resolved_git_source != expected_source
            or substitutions.get("_CODE_SHA")
            != expected["resolved_source_commit"]
            or substitutions.get("_BUILD_IMAGE") != expected["image_tag"]
            or len(matching_images) != 1
        ):
            _fail("Cloud Build provider observation differs from attestation")
        return expected

    def observe_runtime_execution(
        self, expected_attestation: Mapping[str, object],
    ) -> Mapping[str, object]:
        expected = _mapping(
            expected_attestation, label="expected runtime execution attestation"
        )
        if expected.get("project_id") != self._project:
            _fail("runtime execution project differs")
        region = str(expected["region"])
        job_name = str(expected["job_name"])
        execution_name = str(expected["execution_name"])
        job_completed = subprocess.run(
            [
                "gcloud", "run", "jobs", "describe", job_name,
                "--project", self._project, "--region", region,
                "--format=json",
            ],
            check=True, capture_output=True, text=True,
        )
        execution_completed = subprocess.run(
            [
                "gcloud", "run", "jobs", "executions", "describe",
                execution_name, "--project", self._project,
                "--region", region, "--format=json",
            ],
            check=True, capture_output=True, text=True,
        )
        job = _mapping(
            json.loads(job_completed.stdout), label="Cloud Run job observation"
        )
        execution = _mapping(
            json.loads(execution_completed.stdout),
            label="Cloud Run execution observation",
        )
        job_metadata = _mapping(
            job.get("metadata"), label="Cloud Run job metadata"
        )
        execution_metadata = _mapping(
            execution.get("metadata"), label="Cloud Run execution metadata"
        )
        labels = _mapping(
            execution_metadata.get("labels"),
            label="Cloud Run execution labels",
        )
        status = _mapping(
            execution.get("status"), label="Cloud Run execution status"
        )
        execution_spec = _mapping(
            execution.get("spec"), label="Cloud Run execution spec"
        )
        task_template = _mapping(
            execution_spec.get("template"),
            label="Cloud Run execution task template",
        )
        task_spec = _mapping(
            task_template.get("spec"), label="Cloud Run execution task spec"
        )
        containers = task_spec.get("containers")
        if not isinstance(containers, list) or len(containers) != 1:
            _fail("Cloud Run execution container count differs")
        container = _mapping(
            containers[0], label="Cloud Run execution container"
        )

        def _count(name: str) -> int:
            value = status.get(name, 0)
            if value in {None, ""}:
                return 0
            if type(value) is not int or value < 0:
                _fail(f"Cloud Run execution {name} differs")
            return value

        def _environment(name: str) -> str:
            environment = container.get("env")
            if not isinstance(environment, list):
                _fail("Cloud Run execution environment differs")
            values = [
                row.get("value")
                for row in environment
                if isinstance(row, Mapping) and row.get("name") == name
            ]
            if len(values) != 1 or type(values[0]) is not str:
                _fail(f"Cloud Run execution environment {name} differs")
            return values[0]

        conditions = status.get("conditions")
        completed_true = isinstance(conditions, list) and any(
            isinstance(condition, Mapping)
            and condition.get("type") == "Completed"
            and str(condition.get("status")).lower() == "true"
            for condition in conditions
        )
        image = container.get("image")
        expected_digest = str(expected["image_digest"])
        # A Cloud Run Job is mutable while each Execution permanently records
        # the Job generation that created it.  The provider observation is an
        # exact reopen of the frozen Execution, so its generation authority is
        # the immutable execution label, not the Job's current generation.
        # The current Job describe remains useful only to prove that the
        # immutable Job identity/UID referenced by the Execution still exists.
        job_uid = job_metadata.get("uid")
        if (
            job_metadata.get("name") != job_name
            or type(job_uid) is not str
            or not job_uid
            or labels.get("run.googleapis.com/job") != job_name
            or labels.get("run.googleapis.com/jobUid") != job_uid
            or str(labels.get("run.googleapis.com/jobGeneration"))
            != str(expected["job_generation"])
            or execution_metadata.get("name") != execution_name
            or str(execution_metadata.get("uid")) != expected["execution_uid"]
            or execution_spec.get("taskCount") != expected["task_count"]
            or _count("succeededCount") != expected["succeeded_count"]
            or _count("failedCount") != expected["failed_count"]
            or _count("cancelledCount") != expected["cancelled_count"]
            or _count("runningCount") != expected["running_count"]
            or type(image) is not str
            or not image.endswith("@" + expected_digest)
            or _environment("CODE_SHA") != expected["code_sha"]
            or status.get("completionTime") != expected["provider_observed_at"]
            or not completed_true
        ):
            _fail("Cloud Run provider observation differs from attestation")
        return expected


def _load_request(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file():
        _fail(f"{label} must be one existing absolute file")
    raw = path.read_bytes()
    if len(raw) > MAX_REQUEST_BYTES:
        _fail(f"{label} exceeds its byte ceiling")
    return _parse_document(raw, label=label, newline=None)


def _manifest_identity_from_environment() -> dict[str, object]:
    raw = os.environ.get(MANIFEST_IDENTITY_ENV, "")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SnapshotShardRunnerError(
            "runtime manifest identity is not JSON"
        ) from exc
    identity = _identity(value, label="runtime manifest")
    if raw.encode("ascii") != _canonical(identity):
        _fail("runtime manifest identity is not canonical JSON")
    return identity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "smoke", "collect", "validate"):
        child = commands.add_parser(name)
        child.add_argument("--request", type=Path, required=True)
        child.add_argument("--execute", action="store_true")
    task = commands.add_parser("task")
    task.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute:
        _fail("snapshot-shard action requires --execute")
    if os.environ.get(ENABLE_ENV) != ENABLE_VALUE:
        _fail(f"snapshot-shard action requires {ENABLE_ENV}={ENABLE_VALUE}")
    store = GCSExactKnownNameStoreV1()
    provider = GCloudBuildProviderV1()
    if args.command == "task":
        result = execute_task_v1(
            manifest_identity=_manifest_identity_from_environment(),
            environment=os.environ,
            store=store,
        )
    else:
        request = _load_request(args.request, label=f"{args.command} request")
        expected_fields = (
            {"manifest_identity", "runtime_execution_attestation_identity"}
            if args.command == "collect"
            else {"manifest_identity"}
        )
        if set(request) != expected_fields and args.command != "prepare":
            _fail(f"{args.command} request fields differ")
        if args.command == "prepare":
            result = prepare_from_request_v1(request, store=store, provider=provider)
        elif args.command == "smoke":
            result = task0_smoke_v1(
                manifest_identity=request["manifest_identity"],
                environment=os.environ,
                store=store,
            )
        elif args.command == "collect":
            result = collect_v1(
                manifest_identity=request["manifest_identity"],
                runtime_execution_attestation_identity=request[
                    "runtime_execution_attestation_identity"
                ],
                environment=os.environ,
                store=store,
                provider=provider,
            )
        elif args.command == "validate":
            manifest, identity, _ = open_input_manifest_v1(
                request["manifest_identity"], store=store
            )
            result = {
                "schema_version": "snapshot-shard-input-validation/v1",
                "manifest_identity": identity,
                "manifest_sha256": manifest["manifest_sha256"],
                "valid": True,
                "uses_target_slate_outcomes": False,
            }
        else:  # pragma: no cover
            _fail("unknown snapshot-shard action")
    sys.stdout.buffer.write(_document(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        SnapshotShardRunnerError,
        cross.ConstructionAllocationCrossError,
        operator.ConstructionAllocationCrossOperatorError,
        shard_science.ConstructionAllocationShardError,
        snapshot_adapter.ConstructionSnapshotAdapterError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


__all__ = [
    "BuildProvider",
    "COLLECT_RESULT_SCHEMA",
    "ENABLE_ENV",
    "ENABLE_VALUE",
    "FROZEN_BOOM_FIRST_MANIFEST_IDENTITY",
    "GCSExactKnownNameStoreV1",
    "GCloudBuildProviderV1",
    "IMAGE_DIGEST_ENV",
    "INPUT_MANIFEST_SCHEMA",
    "MANIFEST_IDENTITY_ENV",
    "OUTPUT_ROOT",
    "PREPARE_RESULT_SCHEMA",
    "SMOKE_RESULT_SCHEMA",
    "SnapshotShardRunnerError",
    "TASK_COUNT_ENV",
    "TASK_INDEX_ENV",
    "TASK_RESULT_SCHEMA",
    "build_input_manifest_v1",
    "collect_v1",
    "execute_task_v1",
    "open_input_manifest_v1",
    "prepare_audit_placeholder_documents_v1",
    "prepare_from_request_v1",
    "task0_smoke_v1",
    "validate_frozen_boom_first_manifest_v1",
    "validate_input_manifest_v1",
]
