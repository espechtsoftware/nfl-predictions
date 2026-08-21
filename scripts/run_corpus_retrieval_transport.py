#!/usr/bin/env python3
"""Fail-closed local/cloud transport for the corpus retrieval engine.

The retrieval engine owns snapshot, strategy, task-result, and completion
semantics.  This module owns only transport: exact object reopening,
create-once publication, immutable build/job binding, one Cloud Run task at
attempt zero, terminal-first harvesting, and a permanently default-off parked
job after deployment.  The prior job export is rollback authority only until
the generic parked deployment is accepted; it is never restored after a
successful retrieval task.

No BigQuery, historical-outcome, corpus-fill, graph-mutation, or live-policy
client exists in this file.  Cloud access and score-matrix work are both
behind the literal ``--execute`` plus
``CORPUS_RETRIEVAL_RESEARCH_ENABLED=1`` gate.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Final


ROOT: Final = Path(__file__).resolve().parents[1]
SRC: Final = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
PARKED_JOB: Final = "atlas-minimal-c-s2023-w1-v1"
ENABLE_ENV: Final = "CORPUS_RETRIEVAL_RESEARCH_ENABLED"
IMAGE_ENV: Final = "CORPUS_RETRIEVAL_IMAGE"
BUILD_ENV: Final = "CORPUS_RETRIEVAL_BUILD_ID"
CODE_ENV: Final = "CODE_SHA"

TRANSPORT_PREFLIGHT_SCHEMA: Final = "corpus-retrieval-transport-preflight/v1"
EXECUTION_CONTRACT_SCHEMA: Final = (
    "corpus-retrieval-transport-execution-contract/v1"
)
PREFIX_CLAIM_SCHEMA: Final = "corpus-retrieval-transport-prefix-claim/v1"
LAUNCH_INTENT_SCHEMA: Final = "corpus-retrieval-transport-launch-intent/v1"
LAUNCH_LEDGER_SCHEMA: Final = "corpus-retrieval-transport-launch-ledger/v1"
EXECUTION_NAME_LEDGER_SCHEMA: Final = (
    "corpus-retrieval-transport-execution-name-ledger/v1"
)
TERMINAL_RECEIPT_SCHEMA: Final = "corpus-retrieval-transport-terminal/v1"
RUNTIME_IAM_EVIDENCE_SCHEMA: Final = (
    "corpus-retrieval-runtime-iam-evidence/v1"
)

CORE_MODULE: Final = "nfl_dfs.research.corpus_retrieval_engine"
SUITE_SCHEMA: Final = "corpus-retrieval-suite-manifest/v1"
TASK_RESULT_SCHEMA: Final = "corpus-retrieval-task-result/v1"
BATCH_COMPLETION_SCHEMA: Final = "corpus-retrieval-batch-completion/v1"

PARKED_COMMAND: Final = ["python"]
PARKED_ARGS: Final = [
    "scripts/run_corpus_retrieval_transport.py",
    "parked",
]
EXPECTED_RESOURCES: Final = {"cpu": "4", "memory": "16Gi"}
EXPECTED_TIMEOUT_SECONDS: Final = "21600"
EXPECTED_TASK_COUNT: Final = 1
EXPECTED_PARALLELISM: Final = 1
EXPECTED_MAX_RETRIES: Final = 0

REQUIRED_BUILD_FRAGMENTS: Final = (
    "python scripts/run_corpus_retrieval_transport.py --help",
    "import nfl_dfs.research.corpus_retrieval_engine",
)
EXPECTED_CODE_REPOSITORY: Final = (
    "https://github.com/espechtsoftware/nfl-predictions.git"
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_GENERATION: Final = re.compile(r"[1-9][0-9]*")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_BUILD: Final = re.compile(r"[0-9A-Za-z-]{8,80}")
_IMAGE: Final = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}"
)
_EXECUTION: Final = re.compile(r"[a-z][a-z0-9-]{1,62}")
_SERVICE_ACCOUNT: Final = re.compile(
    r"[a-z0-9][a-z0-9.-]{4,62}@[a-z0-9.-]+\.iam\.gserviceaccount\.com"
)

class CorpusRetrievalTransportError(RuntimeError):
    """A fail-closed transport or retained-evidence violation."""


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


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusRetrievalTransportError(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def strict_json_bytes(raw: bytes, *, label: str) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CorpusRetrievalTransportError(
                    f"{label} repeats key {key!r}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise CorpusRetrievalTransportError(
            f"{label} contains non-finite value {value}"
        )

    if type(raw) is not bytes:
        raise CorpusRetrievalTransportError(f"{label} must be bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except CorpusRetrievalTransportError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusRetrievalTransportError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    if canonical_json_bytes(value) != raw:
        raise CorpusRetrievalTransportError(f"{label} is not canonical JSON")
    return value


def external_json_bytes(raw: bytes, *, label: str) -> object:
    """Canonicalize an external CLI response while rejecting duplicate keys."""
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CorpusRetrievalTransportError(
                    f"{label} repeats key {key!r}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise CorpusRetrievalTransportError(
            f"{label} contains non-finite value {value}"
        )

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except CorpusRetrievalTransportError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusRetrievalTransportError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusRetrievalTransportError(f"{label} must be an object")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise CorpusRetrievalTransportError(
            f"{label} keys differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusRetrievalTransportError(
            f"{label} must be a nonempty canonical string"
        )
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CorpusRetrievalTransportError(
            f"{label} must be an exact integer >= {minimum}"
        )
    return value


def _sha(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _SHA256.fullmatch(text) is None:
        raise CorpusRetrievalTransportError(
            f"{label} must be a lowercase SHA-256"
        )
    return text


def _generation(value: object, *, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise CorpusRetrievalTransportError(
            f"{label} must be a positive decimal generation"
        )
    text = str(value)
    if _GENERATION.fullmatch(text) is None:
        raise CorpusRetrievalTransportError(
            f"{label} must be a positive decimal generation"
        )
    return text


def _timestamp(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorpusRetrievalTransportError(
            f"{label} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise CorpusRetrievalTransportError(f"{label} must be UTC")
    return text


def object_identity(value: object, *, label: str) -> ObjectIdentity:
    item = _mapping(value, label=label)
    _exact_keys(
        item,
        frozenset({"uri", "generation", "sha256", "bytes"}),
        label=label,
    )
    uri = _string(item["uri"], label=f"{label}.uri")
    tail = uri.removeprefix("gs://")
    bucket, separator, name = tail.partition("/")
    if (
        not uri.startswith("gs://")
        or not bucket
        or not separator
        or not name
        or uri.endswith("/")
        or "//" in name
        or ".." in name.split("/")
    ):
        raise CorpusRetrievalTransportError(
            f"{label}.uri must be a canonical GCS object URI"
        )
    return ObjectIdentity(
        uri=uri,
        generation=_generation(item["generation"], label=f"{label}.generation"),
        sha256=_sha(item["sha256"], label=f"{label}.sha256"),
        bytes=_exact_int(item["bytes"], label=f"{label}.bytes", minimum=1),
    )


def _load_json_file(path: Path, *, label: str) -> object:
    if path.is_symlink() or not path.is_file():
        raise CorpusRetrievalTransportError(f"{label} file is absent")
    return strict_json_bytes(path.read_bytes(), label=label)


def _write_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != raw:
            raise CorpusRetrievalTransportError(
                f"immutable local object differs: {path}"
            )


def _self_hash(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in body:
        raise CorpusRetrievalTransportError(f"{field} is already populated")
    result = dict(body)
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if retained != canonical_sha256(body):
        raise CorpusRetrievalTransportError(f"{label} self-hash differs")


def require_execute_gate(*, execute: bool, environ: Mapping[str, str]) -> None:
    """Run before importing the core or constructing any storage client."""
    if execute is not True:
        raise CorpusRetrievalTransportError("literal --execute is required")
    if environ.get(ENABLE_ENV) != "1":
        raise CorpusRetrievalTransportError(f"{ENABLE_ENV}=1 is required")


def _core_module():
    """Import only after the execute gate for any score-producing command."""
    return importlib.import_module(CORE_MODULE)


def _task_spec(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        task = value["spec"]["template"]["spec"]["template"]["spec"]  # type: ignore[index]
    except (KeyError, TypeError):
        try:
            task = value["spec"]["template"]["spec"]  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise CorpusRetrievalTransportError(
                "Cloud Run task spec differs"
            ) from exc
    if not isinstance(task, Mapping):
        raise CorpusRetrievalTransportError("Cloud Run task spec differs")
    return task


def _outer_spec(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        outer = value["spec"]["template"]["spec"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise CorpusRetrievalTransportError(
            "Cloud Run outer spec differs"
        ) from exc
    if not isinstance(outer, Mapping):
        raise CorpusRetrievalTransportError("Cloud Run outer spec differs")
    return outer


def job_identity(value: object, *, label: str = "job") -> dict[str, str]:
    item = _mapping(value, label=label)
    metadata = _mapping(item.get("metadata"), label=f"{label}.metadata")
    name = _string(metadata.get("name"), label=f"{label}.name")
    uid = _string(metadata.get("uid"), label=f"{label}.uid")
    generation = _generation(
        metadata.get("generation"), label=f"{label}.generation"
    )
    status = _mapping(item.get("status"), label=f"{label}.status")
    observed_generation = _generation(
        status.get("observedGeneration"),
        label=f"{label}.observedGeneration",
    )
    conditions = status.get("conditions")
    if type(conditions) is not list or not any(
        isinstance(row, Mapping)
        and row.get("type") == "Ready"
        and row.get("status") == "True"
        for row in conditions
    ):
        raise CorpusRetrievalTransportError(f"{label} is not Ready")
    if observed_generation != generation:
        raise CorpusRetrievalTransportError(
            f"{label} observedGeneration differs from generation"
        )
    spec = _mapping(item.get("spec"), label=f"{label}.spec")
    return {
        "name": name,
        "uid": uid,
        "generation": generation,
        "observed_generation": observed_generation,
        "spec_sha256": canonical_sha256(spec),
    }


def _completion_state(value: Mapping[str, object]) -> str:
    status = _mapping(value.get("status", {}), label="execution.status")
    conditions = status.get("conditions", [])
    if type(conditions) is not list:
        raise CorpusRetrievalTransportError("execution conditions differ")
    rows = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if not rows:
        return "Unknown"
    if len(rows) != 1 or rows[0].get("status") not in {
        "Unknown", "True", "False",
    }:
        raise CorpusRetrievalTransportError(
            "execution Completed condition differs"
        )
    return str(rows[0]["status"])


def validate_reuse_census(
    *, job: object, executions: object, schedulers: object,
) -> dict[str, str]:
    identity = job_identity(job)
    if identity["name"] != PARKED_JOB:
        raise CorpusRetrievalTransportError("reused job name differs")
    if type(executions) is not list:
        raise CorpusRetrievalTransportError("execution census differs")
    for row in executions:
        if not isinstance(row, Mapping) or _completion_state(row) == "Unknown":
            raise CorpusRetrievalTransportError(
                "reused job has an active/nonterminal execution"
            )
    validate_scheduler_census(schedulers)
    return identity


def validate_scheduler_census(schedulers: object) -> None:
    if type(schedulers) is not list:
        raise CorpusRetrievalTransportError("scheduler census differs")
    needle = f"/jobs/{PARKED_JOB}:run"
    for row in schedulers:
        if not isinstance(row, Mapping):
            raise CorpusRetrievalTransportError("scheduler census row differs")
        target = row.get("httpTarget", {})
        if isinstance(target, Mapping) and needle in str(target.get("uri", "")):
            raise CorpusRetrievalTransportError(
                "a scheduler targets the reused job"
            )


def execution_census_names(value: object) -> list[str]:
    if type(value) is not list:
        raise CorpusRetrievalTransportError("execution census differs")
    names: list[str] = []
    for index, row in enumerate(value):
        item = _mapping(row, label=f"execution census[{index}]")
        metadata = _mapping(
            item.get("metadata"), label=f"execution census[{index}].metadata"
        )
        name = _string(
            metadata.get("name"), label=f"execution census[{index}].name"
        ).rsplit("/", 1)[-1]
        if _EXECUTION.fullmatch(name) is None:
            raise CorpusRetrievalTransportError(
                "execution census contains a noncanonical name"
            )
        names.append(name)
    if len(names) != len(set(names)):
        raise CorpusRetrievalTransportError("execution census repeats a name")
    return sorted(names)


def validate_build_metadata(
    value: object, *, build_id: str, code_sha: str, image: str,
    code_repository: str,
) -> dict[str, str]:
    item = _mapping(value, label="build metadata")
    if (
        _BUILD.fullmatch(build_id) is None
        or _COMMIT.fullmatch(code_sha) is None
        or _IMAGE.fullmatch(image) is None
        or item.get("id") != build_id
        or item.get("status") != "SUCCESS"
    ):
        raise CorpusRetrievalTransportError("immutable build identity differs")
    try:
        requested = item["source"]["gitSource"]["revision"]  # type: ignore[index]
        requested_repository = item["source"]["gitSource"]["url"]  # type: ignore[index]
        resolved = item["sourceProvenance"]["resolvedGitSource"]["revision"]  # type: ignore[index]
        resolved_repository = item["sourceProvenance"]["resolvedGitSource"]["url"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise CorpusRetrievalTransportError(
            "direct-Git build provenance is absent"
        ) from exc
    if (
        requested != code_sha
        or resolved != code_sha
        or requested_repository != code_repository
        or resolved_repository != code_repository
        or code_repository != EXPECTED_CODE_REPOSITORY
    ):
        raise CorpusRetrievalTransportError("build source commit differs")
    digest = image.rsplit("@", 1)[1]
    results = item.get("results", {})
    images = results.get("images", []) if isinstance(results, Mapping) else []
    if type(images) is not list or not any(
        isinstance(row, Mapping) and row.get("digest") == digest
        for row in images
    ):
        raise CorpusRetrievalTransportError("build image digest differs")
    steps = item.get("steps")
    if type(steps) is not list or not steps or any(
        not isinstance(row, Mapping)
        or row.get("status") != "SUCCESS"
        or int(row.get("exitCode", 0) or 0) != 0
        for row in steps
    ):
        raise CorpusRetrievalTransportError("build steps are not all successful")
    rendered = "\n".join(
        str(part)
        for row in steps
        for part in (row.get("args", []) if isinstance(row, Mapping) else [])
    )
    missing = [part for part in REQUIRED_BUILD_FRAGMENTS if part not in rendered]
    if missing:
        raise CorpusRetrievalTransportError(
            f"retrieval transport build smokes are absent: {missing}"
        )
    return {
        "build_id": build_id,
        "code_repository": code_repository,
        "code_sha": code_sha,
        "image": image,
    }


def _gcs_prefix(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    tail = text.removeprefix("gs://")
    bucket, separator, name = tail.partition("/")
    if (
        not text.startswith("gs://")
        or not bucket
        or not separator
        or not name
        or not text.endswith("/")
        or "//" in name
        or ".." in name.split("/")
        or len([part for part in name.split("/") if part]) < 2
    ):
        raise CorpusRetrievalTransportError(
            f"{label} must be a narrow canonical GCS prefix"
        )
    return text


def _condition_targets(expression: object, *, label: str) -> frozenset[str]:
    text = _string(expression, label=label)
    pattern = re.compile(
        r"resource\.name\.startsWith\((?:\"([^\"]+)\"|'([^']+)')\)"
    )
    matches = list(pattern.finditer(text))
    residue = pattern.sub("", text)
    if not matches or re.sub(r"[\s()|]", "", residue):
        raise CorpusRetrievalTransportError(
            f"{label} is not an OR of exact resource-prefix clauses"
        )
    targets = [first or second for first, second in (
        match.groups() for match in matches
    )]
    if len(targets) != len(set(targets)):
        raise CorpusRetrievalTransportError(f"{label} repeats a prefix")
    return frozenset(targets)


def _resource_prefix(prefix: str) -> str:
    tail = prefix.removeprefix("gs://")
    bucket, name = tail.split("/", 1)
    return f"projects/_/buckets/{bucket}/objects/{name}"


def validate_runtime_iam_evidence(
    value: object,
    *,
    service_account: str,
    required_read_uris: Sequence[str],
    output_prefix: str,
) -> dict[str, object]:
    """Verify the runtime principal has only conditional object capabilities.

    This consumes retained project and bucket IAM policy bodies.  It rejects
    every project-level binding for the runtime principal and permits exactly
    conditional objectViewer plus objectCreator bucket bindings.  Provisioning
    and operator permissions are deliberately outside this transport.
    """
    item = dict(_mapping(value, label="runtime IAM evidence"))
    _exact_keys(item, frozenset({
        "schema_version", "captured_at_utc", "project", "service_account",
        "read_prefixes", "output_prefix", "project_policy",
        "bucket_policies", "bucket_metadata",
        "iam_evidence_sha256",
    }), label="runtime IAM evidence")
    _validate_self_hash(
        item, field="iam_evidence_sha256", label="runtime IAM evidence"
    )
    if (
        item["schema_version"] != RUNTIME_IAM_EVIDENCE_SCHEMA
        or item["project"] != PROJECT
        or item["service_account"] != service_account
        or _SERVICE_ACCOUNT.fullmatch(service_account) is None
    ):
        raise CorpusRetrievalTransportError(
            "runtime IAM evidence principal/project differs"
        )
    _timestamp(item["captured_at_utc"], label="runtime IAM capture timestamp")
    retained_output = _gcs_prefix(
        item["output_prefix"], label="IAM output prefix"
    )
    if retained_output != _gcs_prefix(output_prefix, label="output prefix"):
        raise CorpusRetrievalTransportError("runtime IAM output prefix differs")
    raw_prefixes = item["read_prefixes"]
    if type(raw_prefixes) is not list:
        raise CorpusRetrievalTransportError("IAM read prefixes must be an array")
    read_prefixes = [
        _gcs_prefix(row, label=f"IAM read prefix[{index}]")
        for index, row in enumerate(raw_prefixes)
    ]
    if (
        read_prefixes != sorted(read_prefixes)
        or len(read_prefixes) != len(set(read_prefixes))
        or len(read_prefixes) != 2
        or retained_output not in read_prefixes
    ):
        raise CorpusRetrievalTransportError(
            "IAM requires exact input/output read prefixes"
        )
    input_prefix = next(
        prefix for prefix in read_prefixes if prefix != retained_output
    )
    buckets = {
        prefix.removeprefix("gs://").split("/", 1)[0]
        for prefix in read_prefixes
    }
    if (
        len(buckets) != 1
        or input_prefix.startswith(retained_output)
        or retained_output.startswith(input_prefix)
    ):
        raise CorpusRetrievalTransportError(
            "IAM input/output prefixes must be non-overlapping in one dedicated bucket"
        )
    dedicated_bucket = next(iter(buckets))
    bucket_metadata = _mapping(
        item["bucket_metadata"], label="runtime bucket metadata"
    )
    iam_configuration = _mapping(
        bucket_metadata.get("iamConfiguration"),
        label="runtime bucket IAM configuration",
    )
    ubla = _mapping(
        iam_configuration.get("uniformBucketLevelAccess"),
        label="runtime bucket UBLA metadata",
    )
    if (
        bucket_metadata.get("name") not in {
            dedicated_bucket,
            f"projects/_/buckets/{dedicated_bucket}",
        }
        or ubla.get("enabled") is not True
        or iam_configuration.get("publicAccessPrevention") != "enforced"
    ):
        raise CorpusRetrievalTransportError(
            "dedicated runtime bucket does not prove UBLA/PAP enforcement"
        )
    for index, uri in enumerate(required_read_uris):
        exact_uri = object_identity(
            {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
            label=f"required read URI[{index}]",
        ).uri
        if sum(exact_uri.startswith(prefix) for prefix in read_prefixes) != 1:
            raise CorpusRetrievalTransportError(
                f"required read URI is not covered by exactly one prefix: {exact_uri}"
            )

    member = f"serviceAccount:{service_account}"
    project_policy = _mapping(
        item["project_policy"], label="runtime project policy"
    )
    project_bindings = project_policy.get("bindings", [])
    if type(project_bindings) is not list:
        raise CorpusRetrievalTransportError("runtime project bindings differ")
    for binding in project_bindings:
        row = _mapping(binding, label="runtime project binding")
        members = row.get("members", [])
        if type(members) is not list:
            raise CorpusRetrievalTransportError(
                "runtime project binding members differ"
            )
        if member in members:
            raise CorpusRetrievalTransportError(
                "runtime service account has a forbidden project-level role"
            )

    by_bucket: dict[str, dict[str, frozenset[str]]] = {}
    for prefix in read_prefixes:
        tail = prefix.removeprefix("gs://")
        bucket = tail.split("/", 1)[0]
        by_bucket.setdefault(bucket, {}).setdefault("read", frozenset())
    output_bucket = retained_output.removeprefix("gs://").split("/", 1)[0]
    by_bucket.setdefault(output_bucket, {}).setdefault("create", frozenset())
    rows = item["bucket_policies"]
    if type(rows) is not list:
        raise CorpusRetrievalTransportError("runtime bucket policies differ")
    observed_buckets: set[str] = set()
    observed_bindings: dict[str, dict[str, frozenset[str]]] = {}
    for index, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"runtime bucket policy[{index}]")
        _exact_keys(
            row, frozenset({"bucket", "policy"}),
            label=f"runtime bucket policy[{index}]",
        )
        bucket = _string(row["bucket"], label="runtime IAM bucket")
        if bucket in observed_buckets:
            raise CorpusRetrievalTransportError("runtime IAM repeats a bucket")
        observed_buckets.add(bucket)
        policy = _mapping(row["policy"], label=f"bucket {bucket} policy")
        bindings = policy.get("bindings", [])
        if type(bindings) is not list:
            raise CorpusRetrievalTransportError("runtime bucket bindings differ")
        account_bindings: dict[str, frozenset[str]] = {}
        for raw_binding in bindings:
            binding = _mapping(raw_binding, label=f"bucket {bucket} binding")
            members = binding.get("members", [])
            if type(members) is not list:
                raise CorpusRetrievalTransportError(
                    "runtime bucket binding members differ"
                )
            if member not in members:
                continue
            role = _string(binding.get("role"), label="runtime bucket role")
            expected_title = {
                "roles/storage.objectViewer": "corpus-retrieval-read-v1",
                "roles/storage.objectCreator": "corpus-retrieval-create-v1",
            }.get(role)
            if expected_title is None or role in account_bindings:
                raise CorpusRetrievalTransportError(
                    "runtime service account has a forbidden/repeated bucket role"
                )
            condition = _mapping(
                binding.get("condition"), label="runtime bucket condition"
            )
            if set(condition) - {"title", "description", "expression"} or (
                condition.get("title") != expected_title
            ):
                raise CorpusRetrievalTransportError(
                    "runtime bucket IAM condition differs"
                )
            account_bindings[role] = _condition_targets(
                condition.get("expression"), label="runtime bucket condition"
            )
        observed_bindings[bucket] = account_bindings
    if observed_buckets != set(by_bucket) or len(observed_buckets) != 1:
        raise CorpusRetrievalTransportError(
            "runtime IAM bucket-policy census is incomplete or overbroad"
        )
    for bucket in sorted(observed_buckets):
        expected_view = frozenset(
            _resource_prefix(prefix) for prefix in read_prefixes
            if prefix.startswith(f"gs://{bucket}/")
        )
        expected_create = (
            frozenset({_resource_prefix(retained_output)})
            if bucket == output_bucket else frozenset()
        )
        expected_roles = {"roles/storage.objectViewer": expected_view}
        if expected_create:
            expected_roles["roles/storage.objectCreator"] = expected_create
        if observed_bindings[bucket] != expected_roles:
            raise CorpusRetrievalTransportError(
                "runtime conditional object capabilities differ"
            )
    return item


def build_runtime_iam_evidence(
    *,
    captured_at_utc: str,
    service_account: str,
    read_prefixes: Sequence[str],
    output_prefix: str,
    project_policy: Mapping[str, object],
    bucket_policies: Sequence[Mapping[str, object]],
    required_read_uris: Sequence[str],
    bucket_metadata: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "schema_version": RUNTIME_IAM_EVIDENCE_SCHEMA,
        "captured_at_utc": _timestamp(
            captured_at_utc, label="runtime IAM capture timestamp"
        ),
        "project": PROJECT,
        "service_account": service_account,
        "read_prefixes": sorted(read_prefixes),
        "output_prefix": output_prefix,
        "project_policy": dict(project_policy),
        "bucket_policies": [dict(row) for row in sorted(
            bucket_policies, key=lambda row: str(row.get("bucket", ""))
        )],
        "bucket_metadata": dict(bucket_metadata),
    }
    result = _self_hash(body, field="iam_evidence_sha256")
    return validate_runtime_iam_evidence(
        result,
        service_account=service_account,
        required_read_uris=required_read_uris,
        output_prefix=output_prefix,
    )


def _container_environment(container: Mapping[str, object]) -> dict[str, str]:
    rows = container.get("env", [])
    if type(rows) is not list or any(
        not isinstance(row, Mapping)
        or frozenset(row) != frozenset({"name", "value"})
        or type(row["name"]) is not str
        or type(row["value"]) is not str
        for row in rows
    ):
        raise CorpusRetrievalTransportError("job environment differs")
    result = {str(row["name"]): str(row["value"]) for row in rows}
    if len(result) != len(rows):
        raise CorpusRetrievalTransportError("job environment repeats")
    return result


def validate_parked_job(
    value: object,
    *,
    expected_uid: str,
    expected_image: str,
    expected_code_sha: str,
    expected_build_id: str,
    expected_service_account: str,
) -> dict[str, str]:
    item = _mapping(value, label="updated job")
    identity = job_identity(item, label="updated job")
    if identity["name"] != PARKED_JOB or identity["uid"] != expected_uid:
        raise CorpusRetrievalTransportError("updated reused-job identity differs")
    outer = _outer_spec(item)
    task = _task_spec(item)
    containers = task.get("containers")
    if type(containers) is not list or len(containers) != 1 or not isinstance(
        containers[0], Mapping
    ):
        raise CorpusRetrievalTransportError("updated job container differs")
    container = containers[0]
    expected_env = {
        ENABLE_ENV: "1",
        IMAGE_ENV: expected_image,
        BUILD_ENV: expected_build_id,
        CODE_ENV: expected_code_sha,
    }
    if _SERVICE_ACCOUNT.fullmatch(expected_service_account) is None:
        raise CorpusRetrievalTransportError(
            "planned retrieval service account differs"
        )
    if (
        _exact_int(outer.get("taskCount"), label="job taskCount")
        != EXPECTED_TASK_COUNT
        or _exact_int(outer.get("parallelism"), label="job parallelism")
        != EXPECTED_PARALLELISM
        or _exact_int(task.get("maxRetries"), label="job maxRetries")
        != EXPECTED_MAX_RETRIES
        or task.get("timeoutSeconds") != EXPECTED_TIMEOUT_SECONDS
        or task.get("serviceAccountName") != expected_service_account
        or container.get("image") != expected_image
        or container.get("command") != PARKED_COMMAND
        or container.get("args") != PARKED_ARGS
        or _container_environment(container) != expected_env
        or container.get("resources", {}).get("limits") != EXPECTED_RESOURCES
        or container.get("volumeMounts", []) != []
        or task.get("volumes", []) != []
    ):
        raise CorpusRetrievalTransportError(
            "updated job is not the exact default-off parked contract"
        )
    return identity


def validate_preacceptance_rollback(
    *, before: object, rolled_back: object,
) -> dict[str, str]:
    prior = job_identity(before, label="job before")
    after = job_identity(rolled_back, label="rolled-back job")
    if (
        prior["name"] != PARKED_JOB
        or after["name"] != PARKED_JOB
        or prior["uid"] != after["uid"]
        or prior["spec_sha256"] != after["spec_sha256"]
        or int(after["generation"]) <= int(prior["generation"])
    ):
        raise CorpusRetrievalTransportError(
            "reused job was not rolled back to its exact prior spec"
        )
    return after


def validate_post_terminal_parked_job(
    *, deployed: object, post_terminal: object,
) -> dict[str, str]:
    """Prove a one-time execution did not mutate the accepted parked job."""
    accepted = job_identity(deployed, label="accepted parked job")
    retained = job_identity(post_terminal, label="post-terminal parked job")
    if accepted != retained or retained["name"] != PARKED_JOB:
        raise CorpusRetrievalTransportError(
            "accepted generic parked job changed during execution"
        )
    return retained


def _preflight_paths(binding: Mapping[str, object]) -> dict[str, str]:
    prefix = str(binding["output_prefix"])
    index = int(binding["task_index"])
    return {
        "prefix_claim_uri": f"{prefix}governance/transport-prefix-claim.json",
        "runtime_iam_evidence_uri": (
            f"{prefix}governance/runtime-iam-evidence.json"
        ),
        "execution_contract_uri": (
            f"{prefix}governance/task-{index:04d}-execution-contract.json"
        ),
        "launch_intent_uri": (
            f"{prefix}governance/task-{index:04d}-launch-intent.json"
        ),
        "launch_ledger_uri": (
            f"{prefix}governance/task-{index:04d}-launch-ledger.json"
        ),
        "execution_name_ledger_uri": (
            f"{prefix}governance/task-{index:04d}-execution-name.json"
        ),
        "terminal_receipt_uri": (
            f"{prefix}governance/task-{index:04d}-terminal.json"
        ),
        "completion_uri": f"{prefix}governance/completion.json",
    }


def _task_required_read_uris(
    *,
    suite_identity: ObjectIdentity,
    snapshot_identity: ObjectIdentity,
    snapshot: Mapping[str, object],
    task_index: int,
    candidate_rows_raw: bytes,
    player_catalog_raw: bytes,
) -> list[str]:
    tasks = snapshot.get("tasks")
    if type(tasks) is not list or task_index >= len(tasks):
        raise CorpusRetrievalTransportError("snapshot task index differs")
    task = _mapping(tasks[task_index], label="snapshot task")
    candidate_identity = object_identity(
        task.get("candidate_rows_object"), label="candidate_rows_object"
    )
    player_identity = object_identity(
        task.get("player_catalog_object"), label="player_catalog_object"
    )
    for identity, raw, label in (
        (candidate_identity, candidate_rows_raw, "candidate rows object"),
        (player_identity, player_catalog_raw, "player catalog object"),
    ):
        if (
            type(raw) is not bytes
            or len(raw) != identity.bytes
            or sha256(raw).hexdigest() != identity.sha256
        ):
            raise CorpusRetrievalTransportError(
                f"{label} bytes differ from snapshot identity"
            )
    core = _core_module()
    candidate_validator = getattr(core, "validate_candidate_rows_object", None)
    player_validator = getattr(core, "validate_player_catalog_object", None)
    if not callable(candidate_validator) or not callable(player_validator):
        raise CorpusRetrievalTransportError(
            "retrieval core lacks nested source validators"
        )
    candidate_body = _mapping(
        candidate_validator(strict_json_bytes(
            candidate_rows_raw, label="candidate rows object"
        )),
        label="validated candidate rows object",
    )
    player_body = _mapping(
        player_validator(strict_json_bytes(
            player_catalog_raw, label="player catalog object"
        )),
        label="validated player catalog object",
    )
    candidate_source = object_identity(
        candidate_body.get("source_authority"),
        label="candidate source authority",
    )
    player_source = object_identity(
        player_body.get("source_authority"),
        label="player source authority",
    )
    producer = _mapping(snapshot.get("producer"), label="snapshot producer")
    producer_authority = object_identity(
        producer.get("producer_authority"),
        label="snapshot producer authority",
    )
    if candidate_source != player_source:
        raise CorpusRetrievalTransportError(
            "candidate/player nested source authorities differ"
        )
    identities = [
        suite_identity,
        snapshot_identity,
        candidate_identity,
        player_identity,
        candidate_source,
        producer_authority,
    ]
    blocks = task.get("world_blocks")
    if type(blocks) is not list:
        raise CorpusRetrievalTransportError("snapshot world blocks differ")
    for ordinal, raw_block in enumerate(blocks):
        block = _mapping(raw_block, label=f"snapshot world block[{ordinal}]")
        identities.append(object_identity(
            block.get("artifact_object"),
            label=f"snapshot world block[{ordinal}] artifact",
        ))
    by_uri: dict[str, ObjectIdentity] = {}
    for identity in identities:
        prior = by_uri.setdefault(identity.uri, identity)
        if prior != identity:
            raise CorpusRetrievalTransportError(
                "retrieval task binds conflicting generations for one read URI"
            )
    return sorted(by_uri)


def build_transport_preflight(
    *,
    suite_raw: bytes,
    suite_identity: ObjectIdentity,
    snapshot_raw: bytes,
    snapshot_identity: ObjectIdentity,
    task_index: int,
    build_metadata: object,
    build_id: str,
    code_sha: str,
    image: str,
    service_account: str,
    runtime_iam_evidence_raw: bytes,
    candidate_rows_raw: bytes,
    player_catalog_raw: bytes,
    job_before: object,
    job_before_export_raw: bytes,
    executions: object,
    schedulers: object,
    output_inventory: object,
    created_at_utc: str,
) -> dict[str, object]:
    """Freeze every live identity before any reused-job update."""
    created = _timestamp(created_at_utc, label="preflight created_at_utc")
    if _SERVICE_ACCOUNT.fullmatch(service_account) is None:
        raise CorpusRetrievalTransportError(
            "planned retrieval service account differs"
        )
    job = validate_reuse_census(
        job=job_before, executions=executions, schedulers=schedulers,
    )
    if not job_before_export_raw:
        raise CorpusRetrievalTransportError("job restore export is empty")
    if len(suite_raw) != suite_identity.bytes or sha256(suite_raw).hexdigest() != (
        suite_identity.sha256
    ):
        raise CorpusRetrievalTransportError("preflight suite identity differs")
    if (
        len(snapshot_raw) != snapshot_identity.bytes
        or sha256(snapshot_raw).hexdigest() != snapshot_identity.sha256
    ):
        raise CorpusRetrievalTransportError("preflight snapshot identity differs")
    core = _core_module()
    suite = _validate_suite_with_core(core, suite_raw)
    snapshot = _validate_snapshot_with_core(core, snapshot_raw)
    _require_one_task_manifests(suite, snapshot, task_index)
    release = _engine_release(suite)
    build = validate_build_metadata(
        build_metadata,
        build_id=build_id,
        code_sha=code_sha,
        image=image,
        code_repository=release["code_repository"],
    )
    validate_suite_build_binding(suite, build)
    binding = _transport_binding(core, suite, task_index)
    if object_identity(
        binding["snapshot_manifest_identity"], label="bound snapshot identity"
    ) != snapshot_identity or suite.get("snapshot_id") != snapshot.get("snapshot_id"):
        raise CorpusRetrievalTransportError(
            "preflight suite/snapshot identity differs"
        )
    parsed_iam = strict_json_bytes(
        runtime_iam_evidence_raw, label="runtime IAM evidence"
    )
    validate_runtime_iam_evidence(
        parsed_iam,
        service_account=service_account,
        required_read_uris=_task_required_read_uris(
            suite_identity=suite_identity,
            snapshot_identity=snapshot_identity,
            snapshot=snapshot,
            task_index=task_index,
            candidate_rows_raw=candidate_rows_raw,
            player_catalog_raw=player_catalog_raw,
        ),
        output_prefix=str(binding["output_prefix"]),
    )
    if type(output_inventory) is not list:
        raise CorpusRetrievalTransportError("output-prefix inventory differs")
    normalized_inventory = []
    for index, raw_row in enumerate(output_inventory):
        row = _mapping(raw_row, label=f"output inventory[{index}]")
        _exact_keys(
            row,
            frozenset({"uri", "generation", "bytes"}),
            label=f"output inventory[{index}]",
        )
        normalized_inventory.append({
            "uri": _string(row["uri"], label="inventory URI"),
            "generation": _generation(
                row["generation"], label="inventory generation"
            ),
            "bytes": _exact_int(
                row["bytes"], label="inventory bytes", minimum=1
            ),
        })
    expected_inventory = [{
        "uri": suite_identity.uri,
        "generation": suite_identity.generation,
        "bytes": suite_identity.bytes,
    }]
    if normalized_inventory != expected_inventory:
        raise CorpusRetrievalTransportError(
            "output prefix is not pristine except for the exact suite manifest"
        )
    paths = _preflight_paths(binding)
    if suite_identity.uri != f"{binding['output_prefix']}governance/suite-manifest.json":
        raise CorpusRetrievalTransportError(
            "suite identity URI differs from its output prefix"
        )
    body = {
        "schema_version": TRANSPORT_PREFLIGHT_SCHEMA,
        "created_at_utc": created,
        "project": PROJECT,
        "region": REGION,
        "suite_manifest_identity": suite_identity.as_dict(),
        "snapshot_manifest_identity": snapshot_identity.as_dict(),
        "snapshot_id": snapshot["snapshot_id"],
        "task_index": task_index,
        "task_id": binding["task_id"],
        "output_prefix": binding["output_prefix"],
        "result_uri": binding["result_uri"],
        **paths,
        "build": build,
        "service_account": service_account,
        "runtime_iam_evidence_sha256": sha256(
            runtime_iam_evidence_raw
        ).hexdigest(),
        "runtime_iam_evidence_bytes": len(runtime_iam_evidence_raw),
        "job_before": job,
        "job_before_export_sha256": sha256(job_before_export_raw).hexdigest(),
        "job_before_export_bytes": len(job_before_export_raw),
        "execution_census_sha256": canonical_sha256(executions),
        "execution_names_before": execution_census_names(executions),
        "scheduler_census_sha256": canonical_sha256(schedulers),
        "output_inventory": normalized_inventory,
        "output_inventory_sha256": canonical_sha256(normalized_inventory),
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "cloud_run_task_attempt": 0,
        "create_once": True,
        "prior_spec_rollback_before_acceptance_only": True,
        "successful_deployment_remains_parked": True,
        "uses_realized_outcomes": False,
        "bigquery_access_licensed": False,
        "corpus_fill_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
    }
    return _self_hash(body, field="preflight_sha256")


_PREFLIGHT_KEYS: Final = frozenset({
    "schema_version", "created_at_utc", "project", "region",
    "suite_manifest_identity", "snapshot_manifest_identity", "snapshot_id",
    "task_index", "task_id", "output_prefix", "result_uri",
    "prefix_claim_uri", "execution_contract_uri", "launch_intent_uri",
    "launch_ledger_uri", "execution_name_ledger_uri",
    "terminal_receipt_uri", "completion_uri", "runtime_iam_evidence_uri", "build",
    "service_account", "runtime_iam_evidence_sha256",
    "runtime_iam_evidence_bytes", "job_before",
    "job_before_export_sha256", "job_before_export_bytes",
    "execution_census_sha256", "execution_names_before",
    "scheduler_census_sha256", "output_inventory",
    "output_inventory_sha256", "task_count", "parallelism", "max_retries",
    "cloud_run_task_attempt", "create_once",
    "prior_spec_rollback_before_acceptance_only",
    "successful_deployment_remains_parked",
    "uses_realized_outcomes", "bigquery_access_licensed",
    "corpus_fill_licensed", "live_policy_access_licensed",
    "production_change_licensed", "preflight_sha256",
})


def validate_transport_preflight(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="transport preflight"))
    _exact_keys(item, _PREFLIGHT_KEYS, label="transport preflight")
    _validate_self_hash(
        item, field="preflight_sha256", label="transport preflight"
    )
    if (
        item["schema_version"] != TRANSPORT_PREFLIGHT_SCHEMA
        or item["project"] != PROJECT
        or item["region"] != REGION
        or item["task_count"] != 1
        or item["parallelism"] != 1
        or item["max_retries"] != 0
        or item["cloud_run_task_attempt"] != 0
        or item["create_once"] is not True
        or item["prior_spec_rollback_before_acceptance_only"] is not True
        or item["successful_deployment_remains_parked"] is not True
        or any(item[key] is not False for key in (
            "uses_realized_outcomes", "bigquery_access_licensed",
            "corpus_fill_licensed", "live_policy_access_licensed",
            "production_change_licensed",
        ))
    ):
        raise CorpusRetrievalTransportError(
            "transport preflight authority/attempt law differs"
        )
    _timestamp(item["created_at_utc"], label="preflight created_at_utc")
    suite = object_identity(
        item["suite_manifest_identity"], label="preflight suite identity"
    )
    snapshot = object_identity(
        item["snapshot_manifest_identity"], label="preflight snapshot identity"
    )
    index = _exact_int(item["task_index"], label="preflight task index")
    binding = {
        "output_prefix": item["output_prefix"],
        "snapshot_manifest_identity": snapshot.as_dict(),
        "task_index": index,
        "task_id": item["task_id"],
        "result_uri": item["result_uri"],
    }
    paths = _preflight_paths(binding)
    if (
        suite.uri != f"{item['output_prefix']}governance/suite-manifest.json"
        or any(item[key] != value for key, value in paths.items())
        or item["result_uri"]
        != f"{item['output_prefix']}tasks/{index:04d}/result.json"
        or item["output_inventory"] != [{
            "uri": suite.uri,
            "generation": suite.generation,
            "bytes": suite.bytes,
        }]
        or item["output_inventory_sha256"]
        != canonical_sha256(item["output_inventory"])
    ):
        raise CorpusRetrievalTransportError(
            "transport preflight namespace/inventory differs"
        )
    build = _mapping(item["build"], label="preflight build")
    _exact_keys(
        build,
        frozenset({"build_id", "code_repository", "code_sha", "image"}),
        label="preflight build",
    )
    if (
        _BUILD.fullmatch(str(build["build_id"])) is None
        or build["code_repository"] != EXPECTED_CODE_REPOSITORY
        or _COMMIT.fullmatch(str(build["code_sha"])) is None
        or _IMAGE.fullmatch(str(build["image"])) is None
    ):
        raise CorpusRetrievalTransportError("preflight build identity differs")
    if _SERVICE_ACCOUNT.fullmatch(str(item["service_account"])) is None:
        raise CorpusRetrievalTransportError(
            "preflight retrieval service account differs"
        )
    _sha(
        item["runtime_iam_evidence_sha256"],
        label="preflight runtime IAM evidence SHA",
    )
    _exact_int(
        item["runtime_iam_evidence_bytes"],
        label="preflight runtime IAM evidence bytes",
        minimum=1,
    )
    job = _mapping(item["job_before"], label="preflight prior job")
    _exact_keys(
        job,
        frozenset({
            "name", "uid", "generation", "observed_generation",
            "spec_sha256",
        }),
        label="preflight prior job",
    )
    if job["name"] != PARKED_JOB:
        raise CorpusRetrievalTransportError("preflight reused job differs")
    _string(job["uid"], label="preflight job UID")
    _generation(job["generation"], label="preflight job generation")
    if _generation(
        job["observed_generation"], label="preflight observed generation"
    ) != str(job["generation"]):
        raise CorpusRetrievalTransportError(
            "preflight job is not reconciled"
        )
    for key in (
        "spec_sha256", "job_before_export_sha256", "execution_census_sha256",
        "scheduler_census_sha256", "output_inventory_sha256",
    ):
        _sha(item[key] if key != "spec_sha256" else job[key], label=key)
    _exact_int(
        item["job_before_export_bytes"],
        label="preflight job export bytes",
        minimum=1,
    )
    names = item["execution_names_before"]
    if (
        type(names) is not list
        or names != sorted(names)
        or len(names) != len(set(names))
        or any(_EXECUTION.fullmatch(str(name)) is None for name in names)
    ):
        raise CorpusRetrievalTransportError(
            "preflight execution-name census differs"
        )
    return item


def build_execution_contract(
    *, preflight: object, updated_job: object, created_at_utc: str,
) -> dict[str, object]:
    prior = validate_transport_preflight(preflight)
    build = _mapping(prior["build"], label="preflight build")
    updated = validate_parked_job(
        updated_job,
        expected_uid=str(prior["job_before"]["uid"]),  # type: ignore[index]
        expected_image=str(build["image"]),
        expected_code_sha=str(build["code_sha"]),
        expected_build_id=str(build["build_id"]),
        expected_service_account=str(prior["service_account"]),
    )
    if int(updated["generation"]) <= int(prior["job_before"]["generation"]):  # type: ignore[index]
        raise CorpusRetrievalTransportError(
            "updated job generation did not advance"
        )
    body = {
        "schema_version": EXECUTION_CONTRACT_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="execution contract created_at_utc"
        ),
        "project": PROJECT,
        "region": REGION,
        "preflight_sha256": prior["preflight_sha256"],
        "suite_manifest_identity": prior["suite_manifest_identity"],
        "snapshot_manifest_identity": prior["snapshot_manifest_identity"],
        "snapshot_id": prior["snapshot_id"],
        "task_index": prior["task_index"],
        "task_id": prior["task_id"],
        "output_prefix": prior["output_prefix"],
        "result_uri": prior["result_uri"],
        "prefix_claim_uri": prior["prefix_claim_uri"],
        "execution_contract_uri": prior["execution_contract_uri"],
        "launch_intent_uri": prior["launch_intent_uri"],
        "launch_ledger_uri": prior["launch_ledger_uri"],
        "execution_name_ledger_uri": prior["execution_name_ledger_uri"],
        "terminal_receipt_uri": prior["terminal_receipt_uri"],
        "completion_uri": prior["completion_uri"],
        "build": dict(build),
        "service_account": prior["service_account"],
        "runtime_iam_evidence_uri": prior["runtime_iam_evidence_uri"],
        "runtime_iam_evidence_sha256": prior[
            "runtime_iam_evidence_sha256"
        ],
        "runtime_iam_evidence_bytes": prior["runtime_iam_evidence_bytes"],
        "job_before": prior["job_before"],
        "execution_names_before": prior["execution_names_before"],
        "job_execution": updated,
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "cloud_run_task_attempt": 0,
        "default_command": PARKED_COMMAND,
        "default_args": PARKED_ARGS,
        "execute_override_required": True,
        "create_once": True,
        "uses_realized_outcomes": False,
        "bigquery_access_licensed": False,
        "corpus_fill_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
    }
    return _self_hash(body, field="execution_contract_sha256")


_EXECUTION_CONTRACT_KEYS: Final = frozenset({
    "schema_version", "created_at_utc", "project", "region",
    "preflight_sha256", "suite_manifest_identity", "snapshot_manifest_identity",
    "snapshot_id", "task_index", "task_id", "output_prefix", "result_uri",
    "prefix_claim_uri", "execution_contract_uri", "launch_intent_uri",
    "launch_ledger_uri", "execution_name_ledger_uri",
    "terminal_receipt_uri", "completion_uri", "build", "service_account",
    "runtime_iam_evidence_uri", "runtime_iam_evidence_sha256",
    "runtime_iam_evidence_bytes", "job_before", "execution_names_before",
    "job_execution",
    "task_count", "parallelism", "max_retries", "cloud_run_task_attempt",
    "default_command", "default_args", "execute_override_required",
    "create_once", "uses_realized_outcomes", "bigquery_access_licensed",
    "corpus_fill_licensed", "live_policy_access_licensed",
    "production_change_licensed", "execution_contract_sha256",
})


def validate_execution_contract(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="execution contract"))
    _exact_keys(item, _EXECUTION_CONTRACT_KEYS, label="execution contract")
    _validate_self_hash(
        item,
        field="execution_contract_sha256",
        label="execution contract",
    )
    if (
        item["schema_version"] != EXECUTION_CONTRACT_SCHEMA
        or item["project"] != PROJECT
        or item["region"] != REGION
        or item["task_count"] != 1
        or item["parallelism"] != 1
        or item["max_retries"] != 0
        or item["cloud_run_task_attempt"] != 0
        or item["default_command"] != PARKED_COMMAND
        or item["default_args"] != PARKED_ARGS
        or item["execute_override_required"] is not True
        or item["create_once"] is not True
        or any(item[key] is not False for key in (
            "uses_realized_outcomes", "bigquery_access_licensed",
            "corpus_fill_licensed", "live_policy_access_licensed",
            "production_change_licensed",
        ))
    ):
        raise CorpusRetrievalTransportError(
            "execution contract authority/attempt law differs"
        )
    _timestamp(item["created_at_utc"], label="execution contract timestamp")
    _sha(item["preflight_sha256"], label="execution preflight SHA")
    object_identity(item["suite_manifest_identity"], label="execution suite")
    object_identity(item["snapshot_manifest_identity"], label="execution snapshot")
    build = _mapping(item["build"], label="execution build")
    prior = _mapping(item["job_before"], label="execution prior job")
    active = _mapping(item["job_execution"], label="execution job")
    names = item["execution_names_before"]
    if (
        frozenset(build) != frozenset({
            "build_id", "code_repository", "code_sha", "image",
        })
        or prior.get("name") != PARKED_JOB
        or active.get("name") != PARKED_JOB
        or prior.get("uid") != active.get("uid")
        or str(prior.get("observed_generation"))
        != str(prior.get("generation"))
        or str(active.get("observed_generation"))
        != str(active.get("generation"))
        or int(str(active.get("generation", "0")))
        <= int(str(prior.get("generation", "0")))
        or type(names) is not list
        or names != sorted(names)
        or len(names) != len(set(names))
        or any(_EXECUTION.fullmatch(str(name)) is None for name in names)
    ):
        raise CorpusRetrievalTransportError(
            "execution build/reused-job identity differs"
        )
    _sha(active.get("spec_sha256"), label="execution job spec SHA")
    _sha(prior.get("spec_sha256"), label="execution prior spec SHA")
    _sha(
        item["runtime_iam_evidence_sha256"],
        label="execution runtime IAM evidence SHA",
    )
    _exact_int(
        item["runtime_iam_evidence_bytes"],
        label="execution runtime IAM evidence bytes",
        minimum=1,
    )
    if (
        _BUILD.fullmatch(str(build["build_id"])) is None
        or build["code_repository"] != EXPECTED_CODE_REPOSITORY
        or _COMMIT.fullmatch(str(build["code_sha"])) is None
        or _IMAGE.fullmatch(str(build["image"])) is None
        or _SERVICE_ACCOUNT.fullmatch(str(item["service_account"])) is None
    ):
        raise CorpusRetrievalTransportError("execution image/code differs")
    binding = {
        "output_prefix": item["output_prefix"],
        "snapshot_manifest_identity": item["snapshot_manifest_identity"],
        "task_index": item["task_index"],
        "task_id": item["task_id"],
        "result_uri": item["result_uri"],
    }
    if any(item[key] != value for key, value in _preflight_paths(binding).items()):
        raise CorpusRetrievalTransportError(
            "execution governance namespace differs"
        )
    return item


def _identity_argv(prefix: str, value: object) -> list[str]:
    identity = object_identity(value, label=f"{prefix} argument identity")
    option = prefix.replace("_", "-")
    return [
        f"--{option}-uri", identity.uri,
        f"--{option}-generation", identity.generation,
        f"--{option}-sha256", identity.sha256,
        f"--{option}-bytes", str(identity.bytes),
    ]


def cloud_worker_args(
    *, execution_contract: object,
    execution_contract_identity: object,
) -> list[str]:
    contract = validate_execution_contract(execution_contract)
    return [
        "scripts/run_corpus_retrieval_transport.py",
        "execute-task",
        *_identity_argv("suite", contract["suite_manifest_identity"]),
        *_identity_argv("snapshot", contract["snapshot_manifest_identity"]),
        *_identity_argv(
            "execution_contract", execution_contract_identity
        ),
        "--task-index", str(contract["task_index"]),
        "--execute",
    ]


def publish_transport_governance(
    *,
    preflight: object,
    execution_contract_raw: bytes,
    runtime_iam_evidence_raw: bytes,
    published_at_utc: str,
    storage: GenerationPinnedStorage,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Claim the pristine namespace, then bind the parked execution once."""
    require_execute_gate(execute=execute, environ=environ)
    prior = validate_transport_preflight(preflight)
    parsed_contract = strict_json_bytes(
        execution_contract_raw, label="execution contract"
    )
    contract = validate_execution_contract(parsed_contract)
    if contract["preflight_sha256"] != prior["preflight_sha256"]:
        raise CorpusRetrievalTransportError(
            "execution contract does not bind the exact preflight"
        )
    published_at = _timestamp(
        published_at_utc, label="governance publication timestamp"
    )
    suite = object_identity(
        prior["suite_manifest_identity"], label="governance suite identity"
    )
    suite_inventory = {
        "uri": suite.uri,
        "generation": suite.generation,
        "bytes": suite.bytes,
    }
    allowed_governance_uris = {
        suite.uri,
        str(prior["prefix_claim_uri"]),
        str(prior["runtime_iam_evidence_uri"]),
        str(prior["execution_contract_uri"]),
        str(prior["launch_intent_uri"]),
    }
    existing_inventory = storage.inventory(str(prior["output_prefix"]))
    if (
        suite_inventory not in existing_inventory
        or any(row["uri"] not in allowed_governance_uris for row in existing_inventory)
        or len({row["uri"] for row in existing_inventory})
        != len(existing_inventory)
    ):
        raise CorpusRetrievalTransportError(
            "retrieval governance recovery inventory is unsafe"
        )
    claim = _self_hash({
        "schema_version": PREFIX_CLAIM_SCHEMA,
        "published_at_utc": published_at,
        "preflight_sha256": prior["preflight_sha256"],
        "suite_manifest_identity": suite.as_dict(),
        "snapshot_manifest_identity": prior["snapshot_manifest_identity"],
        "task_index": prior["task_index"],
        "task_id": prior["task_id"],
        "output_prefix": prior["output_prefix"],
        "result_uri": prior["result_uri"],
        "job": PARKED_JOB,
        "job_uid": prior["job_before"]["uid"],  # type: ignore[index]
        "job_prior_generation": prior["job_before"]["generation"],  # type: ignore[index]
        "runtime_iam_evidence_uri": prior["runtime_iam_evidence_uri"],
        "runtime_iam_evidence_sha256": prior[
            "runtime_iam_evidence_sha256"
        ],
        "runtime_iam_evidence_bytes": prior["runtime_iam_evidence_bytes"],
        "create_once": True,
        "uses_realized_outcomes": False,
        "bigquery_access_licensed": False,
        "corpus_fill_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
    }, field="claim_sha256")
    claim_identity = storage.publish_or_reopen(
        str(prior["prefix_claim_uri"]),
        canonical_json_bytes(claim),
        "application/json",
    )
    if (
        len(runtime_iam_evidence_raw)
        != prior["runtime_iam_evidence_bytes"]
        or sha256(runtime_iam_evidence_raw).hexdigest()
        != prior["runtime_iam_evidence_sha256"]
    ):
        raise CorpusRetrievalTransportError(
            "runtime IAM evidence changed after preflight"
        )
    iam_identity = storage.publish_or_reopen(
        str(prior["runtime_iam_evidence_uri"]),
        runtime_iam_evidence_raw,
        "application/json",
    )
    contract_identity = storage.publish_or_reopen(
        str(prior["execution_contract_uri"]),
        execution_contract_raw,
        "application/json",
    )
    worker_args = cloud_worker_args(
        execution_contract=contract,
        execution_contract_identity=contract_identity,
    )
    intent = _self_hash({
        "schema_version": LAUNCH_INTENT_SCHEMA,
        "published_at_utc": published_at,
        "preflight_sha256": prior["preflight_sha256"],
        "execution_contract": contract_identity,
        "prefix_claim": claim_identity,
        "runtime_iam_evidence": iam_identity,
        "suite_manifest_identity": prior["suite_manifest_identity"],
        "snapshot_manifest_identity": prior["snapshot_manifest_identity"],
        "task_index": prior["task_index"],
        "task_id": prior["task_id"],
        "result_uri": prior["result_uri"],
        "job": PARKED_JOB,
        "job_uid": contract["job_execution"]["uid"],  # type: ignore[index]
        "job_generation": contract["job_execution"]["generation"],  # type: ignore[index]
        "job_spec_sha256": contract["job_execution"]["spec_sha256"],  # type: ignore[index]
        "worker_command": PARKED_COMMAND,
        "worker_args": worker_args,
        "worker_args_sha256": canonical_sha256(worker_args),
        "one_execution": True,
        "task_count": 1,
        "max_retries": 0,
        "cloud_run_task_attempt": 0,
        "execute_override_required": True,
        "create_once": True,
        "uses_realized_outcomes": False,
        "bigquery_access_licensed": False,
        "corpus_fill_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
    }, field="launch_intent_sha256")
    intent_identity = storage.publish_or_reopen(
        str(prior["launch_intent_uri"]),
        canonical_json_bytes(intent),
        "application/json",
    )
    expected_inventory = sorted([
        suite_inventory,
        *({
            "uri": row["uri"],
            "generation": row["generation"],
            "bytes": row["bytes"],
        } for row in (
            claim_identity, iam_identity, contract_identity, intent_identity,
        )),
    ], key=lambda row: (row["uri"], row["generation"]))
    if storage.inventory(str(prior["output_prefix"])) != expected_inventory:
        raise CorpusRetrievalTransportError(
            "retrieval governance create-once inventory differs"
        )
    return {
        "schema_version": "corpus-retrieval-transport-governance/v1",
        "preflight_sha256": prior["preflight_sha256"],
        "prefix_claim": claim_identity,
        "runtime_iam_evidence": iam_identity,
        "execution_contract": contract_identity,
        "launch_intent": intent_identity,
        "worker_args": worker_args,
        "worker_args_sha256": canonical_sha256(worker_args),
        "task_index": prior["task_index"],
        "result_uri": prior["result_uri"],
        "one_execution": True,
        "max_retries": 0,
        "cloud_run_task_attempt": 0,
        "uses_realized_outcomes": False,
    }


_PREFIX_CLAIM_KEYS: Final = frozenset({
    "schema_version", "published_at_utc", "preflight_sha256",
    "suite_manifest_identity", "snapshot_manifest_identity", "task_index",
    "task_id", "output_prefix", "result_uri", "job", "job_uid",
    "job_prior_generation", "runtime_iam_evidence_uri",
    "runtime_iam_evidence_sha256", "runtime_iam_evidence_bytes",
    "create_once", "uses_realized_outcomes", "bigquery_access_licensed",
    "corpus_fill_licensed", "live_policy_access_licensed",
    "production_change_licensed", "claim_sha256",
})


def validate_prefix_claim(
    value: object, *, execution_contract: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="transport prefix claim"))
    _exact_keys(item, _PREFIX_CLAIM_KEYS, label="transport prefix claim")
    _validate_self_hash(item, field="claim_sha256", label="transport prefix claim")
    prior = _mapping(execution_contract["job_before"], label="claim prior job")
    expected = {
        "schema_version": PREFIX_CLAIM_SCHEMA,
        "preflight_sha256": execution_contract["preflight_sha256"],
        "suite_manifest_identity": execution_contract["suite_manifest_identity"],
        "snapshot_manifest_identity": execution_contract[
            "snapshot_manifest_identity"
        ],
        "task_index": execution_contract["task_index"],
        "task_id": execution_contract["task_id"],
        "output_prefix": execution_contract["output_prefix"],
        "result_uri": execution_contract["result_uri"],
        "job": PARKED_JOB,
        "job_uid": prior["uid"],
        "job_prior_generation": prior["generation"],
        "runtime_iam_evidence_uri": execution_contract[
            "runtime_iam_evidence_uri"
        ],
        "runtime_iam_evidence_sha256": execution_contract[
            "runtime_iam_evidence_sha256"
        ],
        "runtime_iam_evidence_bytes": execution_contract[
            "runtime_iam_evidence_bytes"
        ],
    }
    if any(item.get(key) != expected_value for key, expected_value in expected.items()):
        raise CorpusRetrievalTransportError("transport prefix claim binding differs")
    _timestamp(item["published_at_utc"], label="prefix claim timestamp")
    if item["create_once"] is not True or any(item[key] is not False for key in (
        "uses_realized_outcomes", "bigquery_access_licensed",
        "corpus_fill_licensed", "live_policy_access_licensed",
        "production_change_licensed",
    )):
        raise CorpusRetrievalTransportError("transport prefix claim license differs")
    return item


_LAUNCH_INTENT_KEYS: Final = frozenset({
    "schema_version", "published_at_utc", "preflight_sha256",
    "execution_contract", "prefix_claim", "runtime_iam_evidence",
    "suite_manifest_identity", "snapshot_manifest_identity", "task_index",
    "task_id", "result_uri", "job", "job_uid", "job_generation",
    "job_spec_sha256", "worker_command", "worker_args",
    "worker_args_sha256", "one_execution", "task_count", "max_retries",
    "cloud_run_task_attempt", "execute_override_required", "create_once",
    "uses_realized_outcomes", "bigquery_access_licensed",
    "corpus_fill_licensed", "live_policy_access_licensed",
    "production_change_licensed", "launch_intent_sha256",
})


def validate_launch_intent(
    value: object,
    *,
    execution_contract: Mapping[str, object],
    execution_contract_identity: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="launch intent"))
    _exact_keys(item, _LAUNCH_INTENT_KEYS, label="launch intent")
    _validate_self_hash(item, field="launch_intent_sha256", label="launch intent")
    active = _mapping(execution_contract["job_execution"], label="intent job")
    expected_args = cloud_worker_args(
        execution_contract=execution_contract,
        execution_contract_identity=execution_contract_identity,
    )
    if (
        item["schema_version"] != LAUNCH_INTENT_SCHEMA
        or item["preflight_sha256"] != execution_contract["preflight_sha256"]
        or item["execution_contract"] != execution_contract_identity
        or item["suite_manifest_identity"]
        != execution_contract["suite_manifest_identity"]
        or item["snapshot_manifest_identity"]
        != execution_contract["snapshot_manifest_identity"]
        or item["task_index"] != execution_contract["task_index"]
        or item["task_id"] != execution_contract["task_id"]
        or item["result_uri"] != execution_contract["result_uri"]
        or item["job"] != PARKED_JOB
        or item["job_uid"] != active["uid"]
        or item["job_generation"] != active["generation"]
        or item["job_spec_sha256"] != active["spec_sha256"]
        or item["worker_command"] != PARKED_COMMAND
        or item["worker_args"] != expected_args
        or item["worker_args_sha256"] != canonical_sha256(expected_args)
        or item["one_execution"] is not True
        or item["task_count"] != 1
        or item["max_retries"] != 0
        or item["cloud_run_task_attempt"] != 0
        or item["execute_override_required"] is not True
        or item["create_once"] is not True
        or any(item[key] is not False for key in (
            "uses_realized_outcomes", "bigquery_access_licensed",
            "corpus_fill_licensed", "live_policy_access_licensed",
            "production_change_licensed",
        ))
    ):
        raise CorpusRetrievalTransportError("launch intent binding differs")
    _timestamp(item["published_at_utc"], label="launch intent timestamp")
    object_identity(item["prefix_claim"], label="intent prefix claim")
    object_identity(item["runtime_iam_evidence"], label="intent IAM evidence")
    return item


class GenerationPinnedStorage:
    """The only cloud object adapter; imported only after the execute gate."""

    def __init__(
        self,
        *,
        execute: bool,
        environ: Mapping[str, str],
        project: str = PROJECT,
    ):
        require_execute_gate(execute=execute, environ=environ)
        from google.cloud import storage

        self._client = storage.Client(project=project)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        identity = object_identity(
            {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
            label="object URI",
        )
        tail = identity.uri.removeprefix("gs://")
        return tuple(tail.split("/", 1))  # type: ignore[return-value]

    def read(self, value: Mapping[str, object]) -> bytes:
        identity = object_identity(value, label="read identity")
        bucket, name = self._parts(identity.uri)
        blob = self._client.bucket(bucket).blob(
            name, generation=int(identity.generation)
        )
        raw = blob.download_as_bytes(
            if_generation_match=int(identity.generation)
        )
        if len(raw) != identity.bytes or sha256(raw).hexdigest() != identity.sha256:
            raise CorpusRetrievalTransportError(
                "generation-pinned object content differs"
            )
        return raw

    def publish(
        self, uri: str, raw: bytes, media_type: str,
    ) -> dict[str, object]:
        candidate = object_identity(
            {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
            label="publish URI",
        )
        if type(raw) is not bytes or not raw:
            raise CorpusRetrievalTransportError("published body must be bytes")
        media = _string(media_type, label="published media type")
        bucket, name = self._parts(candidate.uri)
        blob = self._client.bucket(bucket).blob(name)
        blob.upload_from_string(
            raw,
            content_type=media,
            if_generation_match=0,
        )
        generation = _generation(blob.generation, label="published generation")
        result = ObjectIdentity(
            uri=uri,
            generation=generation,
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        reopened = self.read(result.as_dict())
        if reopened != raw:
            raise CorpusRetrievalTransportError(
                "create-once publication did not reopen byte-identically"
            )
        return result.as_dict()

    def inventory(self, prefix: str) -> list[dict[str, object]]:
        text = _string(prefix, label="inventory prefix")
        tail = text.removeprefix("gs://")
        bucket_name, separator, object_prefix = tail.partition("/")
        if (
            not text.startswith("gs://")
            or not bucket_name
            or not separator
            or not object_prefix
            or not text.endswith("/")
        ):
            raise CorpusRetrievalTransportError(
                "inventory prefix must be a canonical GCS prefix"
            )
        rows = []
        for blob in self._client.list_blobs(
            bucket_name, prefix=object_prefix, versions=True,
        ):
            generation = _generation(
                blob.generation, label="inventory object generation"
            )
            if blob.size is None or int(blob.size) < 1:
                raise CorpusRetrievalTransportError(
                    "inventory object size differs"
                )
            # Inventory is only a namespace/collision census. Content hashes
            # are required from canonical retained identities, never trusted
            # from mutable object metadata.
            rows.append({
                "uri": f"gs://{bucket_name}/{blob.name}",
                "generation": generation,
                "bytes": int(blob.size),
            })
        return sorted(rows, key=lambda row: (row["uri"], row["generation"]))

    def resolve_unique(self, uri: str) -> tuple[dict[str, object], bytes]:
        """Resolve one create-once object to an identity, then pin/reopen it."""
        candidate = object_identity(
            {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
            label="resolved object URI",
        )
        bucket, name = self._parts(candidate.uri)
        rows = list(self._client.list_blobs(
            bucket, prefix=name, versions=True,
        ))
        exact = [row for row in rows if row.name == name]
        if len(exact) != 1 or exact[0].size is None:
            raise CorpusRetrievalTransportError(
                "create-once object is absent or has multiple generations"
            )
        generation = _generation(
            exact[0].generation, label="resolved object generation"
        )
        raw = exact[0].download_as_bytes(
            if_generation_match=int(generation)
        )
        identity = ObjectIdentity(
            uri=uri,
            generation=generation,
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        if not raw:
            raise CorpusRetrievalTransportError("resolved object is empty")
        return identity.as_dict(), raw

    def resolve_current(self, uri: str) -> tuple[dict[str, object], bytes]:
        """Resolve an exact live object with GET only, then pin/reopen it.

        Unlike :meth:`resolve_unique`, this method deliberately performs no
        bucket listing.  It is the worker-safe resolver for a runtime identity
        whose conditional IAM grants ``storage.objects.get`` only under the
        two governed prefixes.  The operator proves sole-generation namespace
        purity with list-based censuses immediately before launch and again at
        terminal acceptance.
        """
        candidate = object_identity(
            {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
            label="current object URI",
        )
        bucket, name = self._parts(candidate.uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.reload()
            generation = _generation(
                blob.generation, label="current object generation"
            )
            if blob.size is None or int(blob.size) < 1:
                raise CorpusRetrievalTransportError(
                    "current object is empty"
                )
            pinned = self._client.bucket(bucket).blob(
                name, generation=int(generation)
            )
            raw = pinned.download_as_bytes(
                if_generation_match=int(generation)
            )
        except CorpusRetrievalTransportError:
            raise
        except Exception as exc:
            raise CorpusRetrievalTransportError(
                "exact current object is absent or unreadable"
            ) from exc
        if not raw or len(raw) != int(blob.size):
            raise CorpusRetrievalTransportError(
                "generation-pinned current object size differs"
            )
        identity = ObjectIdentity(
            uri=uri,
            generation=generation,
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        return identity.as_dict(), raw

    def publish_or_reopen(
        self, uri: str, raw: bytes, media_type: str,
    ) -> dict[str, object]:
        """Create once, or recover only the byte-identical sole generation."""
        try:
            return self.publish(uri, raw, media_type)
        except Exception as publish_error:
            try:
                identity, reopened = self.resolve_unique(uri)
            except Exception as resolve_error:
                raise CorpusRetrievalTransportError(
                    "create-once publication is absent or ambiguous after failure"
                ) from publish_error
            if reopened != raw:
                raise CorpusRetrievalTransportError(
                    "existing create-once object differs during recovery"
                ) from resolve_error
            return identity

    def publish_consumption_ledger(
        self, uri: str, raw: bytes, media_type: str,
    ) -> tuple[dict[str, object], bool]:
        """Create a one-shot authority ledger and expose launch ambiguity.

        ``created`` is true only when this call observed a complete successful
        create-and-reopen.  If upload may have succeeded but its response was
        lost, the byte-identical object is returned with ``created=false``;
        callers must recover by census and must never relaunch.
        """
        try:
            return self.publish(uri, raw, media_type), True
        except Exception as publish_error:
            try:
                identity, reopened = self.resolve_unique(uri)
            except Exception:
                raise CorpusRetrievalTransportError(
                    "launch-ledger creation failed without recoverable authority"
                ) from publish_error
            if reopened != raw:
                raise CorpusRetrievalTransportError(
                    "existing launch ledger differs during recovery"
                ) from publish_error
            return identity, False


def _inventory_row_for_identity(value: object) -> dict[str, object]:
    identity = object_identity(value, label="inventory identity")
    return {
        "uri": identity.uri,
        "generation": identity.generation,
        "bytes": identity.bytes,
    }


def _require_exact_inventory(
    storage: GenerationPinnedStorage,
    *,
    prefix: str,
    identities: Sequence[object],
    label: str,
) -> None:
    expected = sorted(
        [_inventory_row_for_identity(value) for value in identities],
        key=lambda row: (row["uri"], row["generation"]),
    )
    if (
        len({row["uri"] for row in expected}) != len(expected)
        or storage.inventory(prefix) != expected
    ):
        raise CorpusRetrievalTransportError(f"{label} inventory differs")


def _require_only_inventory_uris(
    storage: GenerationPinnedStorage,
    *,
    prefix: str,
    required_identities: Sequence[object],
    optional_uris: Sequence[str],
    label: str,
) -> list[dict[str, object]]:
    """Require every known identity exactly and permit named recovery tails."""
    rows = storage.inventory(prefix)
    if len({row["uri"] for row in rows}) != len(rows):
        raise CorpusRetrievalTransportError(f"{label} repeats an object URI")
    by_uri = {str(row["uri"]): row for row in rows}
    required = {
        str(row["uri"]): row
        for row in (
            _inventory_row_for_identity(value) for value in required_identities
        )
    }
    if len(required) != len(required_identities):
        raise CorpusRetrievalTransportError(
            f"{label} required identities repeat an object URI"
        )
    if any(by_uri.get(uri) != row for uri, row in required.items()):
        raise CorpusRetrievalTransportError(
            f"{label} required object identity differs"
        )
    allowed = set(required).union(optional_uris)
    if set(by_uri) - allowed:
        raise CorpusRetrievalTransportError(f"{label} has unknown objects")
    return rows


def _require_exact_governance_inventory(
    storage: GenerationPinnedStorage,
    *,
    prefix: str,
    identities: Sequence[object],
    label: str,
) -> None:
    expected = sorted(
        [_inventory_row_for_identity(value) for value in identities],
        key=lambda row: (row["uri"], row["generation"]),
    )
    rows = [
        row for row in storage.inventory(prefix)
        if "/governance/" in str(row["uri"])
    ]
    if (
        len({row["uri"] for row in expected}) != len(expected)
        or rows != expected
    ):
        raise CorpusRetrievalTransportError(f"{label} inventory differs")


def _load_execution_contract(
    storage: GenerationPinnedStorage, identity: ObjectIdentity,
) -> dict[str, object]:
    raw = storage.read(identity.as_dict())
    return validate_execution_contract(
        strict_json_bytes(raw, label="execution contract")
    )


def _reopen_governance(
    *,
    storage: GenerationPinnedStorage,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    exact_name_only: bool = False,
) -> dict[str, object]:
    resolve = (
        storage.resolve_current if exact_name_only else storage.resolve_unique
    )
    claim_identity_raw, claim_raw = resolve(
        str(contract["prefix_claim_uri"])
    )
    claim = validate_prefix_claim(
        strict_json_bytes(claim_raw, label="prefix claim"),
        execution_contract=contract,
    )
    iam_identity_raw, iam_raw = resolve(
        str(contract["runtime_iam_evidence_uri"])
    )
    if (
        len(iam_raw) != contract["runtime_iam_evidence_bytes"]
        or sha256(iam_raw).hexdigest()
        != contract["runtime_iam_evidence_sha256"]
    ):
        raise CorpusRetrievalTransportError(
            "generation-pinned runtime IAM evidence differs"
        )
    suite_identity = object_identity(
        contract["suite_manifest_identity"], label="governance suite identity"
    )
    snapshot_identity = object_identity(
        contract["snapshot_manifest_identity"],
        label="governance snapshot identity",
    )
    core = _core_module()
    suite = _validate_suite_with_core(core, storage.read(suite_identity.as_dict()))
    snapshot = _validate_snapshot_with_core(
        core, storage.read(snapshot_identity.as_dict())
    )
    _require_one_task_manifests(suite, snapshot, int(contract["task_index"]))
    build = _mapping(contract["build"], label="governance build")
    try:
        validate_suite_build_binding(suite, build)
    except CorpusRetrievalTransportError as exc:
        raise CorpusRetrievalTransportError(
            "reopened suite release differs from validated build"
        ) from exc
    validate_runtime_iam_evidence(
        strict_json_bytes(iam_raw, label="runtime IAM evidence"),
        service_account=str(contract["service_account"]),
        required_read_uris=_task_required_read_uris(
            suite_identity=suite_identity,
            snapshot_identity=snapshot_identity,
            snapshot=snapshot,
            task_index=int(contract["task_index"]),
            candidate_rows_raw=storage.read(
                snapshot["tasks"][int(contract["task_index"])][  # type: ignore[index]
                    "candidate_rows_object"
                ]
            ),
            player_catalog_raw=storage.read(
                snapshot["tasks"][int(contract["task_index"])][  # type: ignore[index]
                    "player_catalog_object"
                ]
            ),
        ),
        output_prefix=str(contract["output_prefix"]),
    )
    intent_identity_raw, intent_raw = resolve(
        str(contract["launch_intent_uri"])
    )
    intent = validate_launch_intent(
        strict_json_bytes(intent_raw, label="launch intent"),
        execution_contract=contract,
        execution_contract_identity=contract_identity.as_dict(),
    )
    if (
        intent["prefix_claim"] != claim_identity_raw
        or intent["runtime_iam_evidence"] != iam_identity_raw
    ):
        raise CorpusRetrievalTransportError(
            "launch intent governance identities differ"
        )
    return {
        "suite": suite,
        "snapshot": snapshot,
        "suite_identity": suite_identity.as_dict(),
        "snapshot_identity": snapshot_identity.as_dict(),
        "prefix_claim": claim,
        "prefix_claim_identity": claim_identity_raw,
        "runtime_iam_evidence_identity": iam_identity_raw,
        "launch_intent": intent,
        "launch_intent_identity": intent_identity_raw,
    }


def _validate_current_parked_job(
    value: object, *, contract: Mapping[str, object],
) -> dict[str, str]:
    build = _mapping(contract["build"], label="current parked build")
    identity = validate_parked_job(
        value,
        expected_uid=str(contract["job_execution"]["uid"]),  # type: ignore[index]
        expected_image=str(build["image"]),
        expected_code_sha=str(build["code_sha"]),
        expected_build_id=str(build["build_id"]),
        expected_service_account=str(contract["service_account"]),
    )
    if identity != contract["job_execution"]:
        raise CorpusRetrievalTransportError(
            "current parked job differs from accepted deployment"
        )
    return identity


def publish_launch_ledger(
    *,
    execution_contract_identity: ObjectIdentity,
    job: object,
    executions: object,
    schedulers: object,
    created_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
    storage: GenerationPinnedStorage | None = None,
) -> dict[str, object]:
    """Consume the sole launch authority before invoking Cloud Run."""
    require_execute_gate(execute=execute, environ=environ)
    store = GenerationPinnedStorage(
        execute=execute, environ=environ,
    ) if storage is None else storage
    contract = _load_execution_contract(store, execution_contract_identity)
    governance = _reopen_governance(
        storage=store,
        contract=contract,
        contract_identity=execution_contract_identity,
    )
    governance_identities = [
        contract["suite_manifest_identity"],
        governance["prefix_claim_identity"],
        governance["runtime_iam_evidence_identity"],
        execution_contract_identity.as_dict(),
        governance["launch_intent_identity"],
    ]
    inventory = store.inventory(str(contract["output_prefix"]))
    retained_launch_rows = [
        row for row in inventory
        if row["uri"] == contract["launch_ledger_uri"]
    ]
    if len(retained_launch_rows) > 1:
        raise CorpusRetrievalTransportError(
            "launch authority has multiple generations; never relaunch"
        )
    if retained_launch_rows:
        launch_identity_raw, launch_raw = store.resolve_unique(
            str(contract["launch_ledger_uri"])
        )
        validate_launch_ledger(
            strict_json_bytes(launch_raw, label="launch ledger"),
            contract=contract,
            contract_identity=execution_contract_identity,
            intent_identity=governance["launch_intent_identity"],
        )
        _require_exact_governance_inventory(
            store,
            prefix=str(contract["output_prefix"]),
            identities=[*governance_identities, launch_identity_raw],
            label="recovered launch governance",
        )
        return {
            "schema_version": "corpus-retrieval-transport-launch-ready/v1",
            "execution_contract": execution_contract_identity.as_dict(),
            "launch_ledger": launch_identity_raw,
            "worker_args": [],
            "launch_authority_consumed": True,
            "launch_permitted": False,
            "automatic_relaunch_licensed": False,
            "recovery_action": "census-only-never-relaunch",
        }

    current = _validate_current_parked_job(job, contract=contract)
    validate_reuse_census(job=job, executions=executions, schedulers=schedulers)
    names = execution_census_names(executions)
    if names != contract["execution_names_before"]:
        raise CorpusRetrievalTransportError(
            "launch census changed since preflight; no launch"
        )
    _require_exact_inventory(
        store,
        prefix=str(contract["output_prefix"]),
        identities=governance_identities,
        label="prelaunch governance",
    )
    body = _self_hash({
        "schema_version": LAUNCH_LEDGER_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="launch ledger timestamp"
        ),
        "execution_contract": execution_contract_identity.as_dict(),
        "launch_intent": governance["launch_intent_identity"],
        "job": current,
        "execution_names_before": names,
        "worker_args_sha256": governance["launch_intent"][
            "worker_args_sha256"
        ],
        "launch_authority_consumed": True,
        "one_execution": True,
        "automatic_relaunch_licensed": False,
        "ambiguous_response_requires_census_recovery": True,
        "uses_realized_outcomes": False,
    }, field="launch_ledger_sha256")
    identity, created = store.publish_consumption_ledger(
        str(contract["launch_ledger_uri"]),
        canonical_json_bytes(body),
        "application/json",
    )
    _require_exact_inventory(
        store,
        prefix=str(contract["output_prefix"]),
        identities=[*governance_identities, identity],
        label="launch-consumed governance",
    )
    return {
        "schema_version": "corpus-retrieval-transport-launch-ready/v1",
        "execution_contract": execution_contract_identity.as_dict(),
        "launch_ledger": identity,
        "worker_args": (
            governance["launch_intent"]["worker_args"] if created else []
        ),
        "launch_authority_consumed": True,
        "launch_permitted": created,
        "automatic_relaunch_licensed": False,
        "recovery_action": (
            "invoke-exactly-once-now" if created
            else "census-only-never-relaunch"
        ),
    }


_LAUNCH_LEDGER_KEYS: Final = frozenset({
    "schema_version", "created_at_utc", "execution_contract",
    "launch_intent", "job", "execution_names_before",
    "worker_args_sha256", "launch_authority_consumed", "one_execution",
    "automatic_relaunch_licensed", "ambiguous_response_requires_census_recovery",
    "uses_realized_outcomes", "launch_ledger_sha256",
})


def validate_launch_ledger(
    value: object,
    *,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    intent_identity: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="launch ledger"))
    _exact_keys(item, _LAUNCH_LEDGER_KEYS, label="launch ledger")
    _validate_self_hash(item, field="launch_ledger_sha256", label="launch ledger")
    if (
        item["schema_version"] != LAUNCH_LEDGER_SCHEMA
        or item["execution_contract"] != contract_identity.as_dict()
        or item["launch_intent"] != intent_identity
        or item["job"] != contract["job_execution"]
        or item["execution_names_before"] != contract["execution_names_before"]
        or item["worker_args_sha256"]
        != canonical_sha256(cloud_worker_args(
            execution_contract=contract,
            execution_contract_identity=contract_identity.as_dict(),
        ))
        or item["launch_authority_consumed"] is not True
        or item["one_execution"] is not True
        or item["automatic_relaunch_licensed"] is not False
        or item["ambiguous_response_requires_census_recovery"] is not True
        or item["uses_realized_outcomes"] is not False
    ):
        raise CorpusRetrievalTransportError("launch ledger binding differs")
    _timestamp(item["created_at_utc"], label="launch ledger timestamp")
    _sha(item["worker_args_sha256"], label="launch ledger argv SHA")
    return item


_EXECUTION_NAME_LEDGER_KEYS: Final = frozenset({
    "schema_version", "created_at_utc", "execution_contract",
    "launch_ledger", "execution_id", "execution_name", "execution_uid",
    "execution_metadata_sha256", "job_uid", "job_generation",
    "exactly_one_new_execution", "attempt", "max_retries",
    "automatic_relaunch_licensed", "uses_realized_outcomes",
    "execution_name_ledger_sha256",
})


def validate_execution_name_ledger(
    value: object,
    *,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    launch_identity: Mapping[str, object],
    execution_metadata: object | None = None,
) -> dict[str, object]:
    item = dict(_mapping(value, label="execution-name ledger"))
    _exact_keys(item, _EXECUTION_NAME_LEDGER_KEYS, label="execution-name ledger")
    _validate_self_hash(
        item,
        field="execution_name_ledger_sha256",
        label="execution-name ledger",
    )
    active = _mapping(contract["job_execution"], label="execution-name job")
    name = _string(item["execution_name"], label="bound execution name")
    execution_id = _string(item["execution_id"], label="bound execution ID")
    qualified_prefix = (
        f"projects/{PROJECT}/locations/{REGION}/jobs/{PARKED_JOB}/executions/"
    )
    if (
        item["schema_version"] != EXECUTION_NAME_LEDGER_SCHEMA
        or item["execution_contract"] != contract_identity.as_dict()
        or item["launch_ledger"] != launch_identity
        or execution_id != name.rsplit("/", 1)[-1]
        or _EXECUTION.fullmatch(execution_id) is None
        or (name != execution_id and not name.startswith(qualified_prefix))
        or not item["execution_uid"]
        or item["job_uid"] != active["uid"]
        or str(item["job_generation"]) != str(active["generation"])
        or item["exactly_one_new_execution"] is not True
        or item["attempt"] != 0
        or item["max_retries"] != 0
        or item["automatic_relaunch_licensed"] is not False
        or item["uses_realized_outcomes"] is not False
    ):
        raise CorpusRetrievalTransportError(
            "execution-name ledger binding differs"
        )
    _timestamp(item["created_at_utc"], label="execution-name ledger timestamp")
    _string(item["execution_uid"], label="bound execution UID")
    _sha(
        item["execution_metadata_sha256"],
        label="bound execution metadata SHA",
    )
    if (
        execution_metadata is not None
        and item["execution_metadata_sha256"]
        != canonical_sha256(execution_metadata)
    ):
        raise CorpusRetrievalTransportError(
            "execution-name ledger metadata binding differs"
        )
    return item


def bind_execution_name(
    *,
    execution_contract_identity: ObjectIdentity,
    execution_metadata: object,
    job: object,
    executions: object,
    schedulers: object,
    created_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
    storage: GenerationPinnedStorage | None = None,
) -> dict[str, object]:
    """Recover the sole execution name from census; this never launches."""
    require_execute_gate(execute=execute, environ=environ)
    store = GenerationPinnedStorage(
        execute=execute, environ=environ,
    ) if storage is None else storage
    contract = _load_execution_contract(store, execution_contract_identity)
    governance = _reopen_governance(
        storage=store,
        contract=contract,
        contract_identity=execution_contract_identity,
    )
    _validate_current_parked_job(job, contract=contract)
    validate_scheduler_census(schedulers)
    if type(executions) is not list:
        raise CorpusRetrievalTransportError("execution recovery census differs")
    before = set(contract["execution_names_before"])
    after = set(execution_census_names(executions))
    new_names = after.difference(before)
    if before.difference(after) or len(new_names) != 1:
        raise CorpusRetrievalTransportError(
            "launch outcome is ambiguous; never relaunch; repeat census recovery"
        )
    execution_id = next(iter(new_names))
    for row in executions:
        name = str(row.get("metadata", {}).get("name", "")).rsplit("/", 1)[-1]
        if name != execution_id and _completion_state(row) == "Unknown":
            raise CorpusRetrievalTransportError(
                "a pre-existing execution became nonterminal"
            )
    metadata = _mapping(execution_metadata, label="recovered execution metadata")
    retained_metadata = _mapping(
        metadata.get("metadata"), label="recovered execution metadata identity"
    )
    metadata_name = _string(
        retained_metadata.get("name"), label="recovered execution name"
    )
    if metadata_name.rsplit("/", 1)[-1] != execution_id:
        raise CorpusRetrievalTransportError(
            "recovered execution metadata/name differs"
        )
    labels = _mapping(
        retained_metadata.get("labels"), label="recovered execution labels"
    )
    active = _mapping(contract["job_execution"], label="recovered job")
    if (
        labels.get("run.googleapis.com/job") != PARKED_JOB
        or labels.get("run.googleapis.com/jobUid") != active["uid"]
        or str(labels.get("run.googleapis.com/jobGeneration"))
        != str(active["generation"])
    ):
        raise CorpusRetrievalTransportError(
            "recovered execution job binding differs"
        )
    launch_identity_raw, launch_raw = store.resolve_unique(
        str(contract["launch_ledger_uri"])
    )
    launch = validate_launch_ledger(
        strict_json_bytes(launch_raw, label="launch ledger"),
        contract=contract,
        contract_identity=execution_contract_identity,
        intent_identity=governance["launch_intent_identity"],
    )
    governance_identities = [
        contract["suite_manifest_identity"],
        governance["prefix_claim_identity"],
        governance["runtime_iam_evidence_identity"],
        execution_contract_identity.as_dict(),
        governance["launch_intent_identity"],
        launch_identity_raw,
    ]
    _require_exact_governance_inventory(
        store,
        prefix=str(contract["output_prefix"]),
        identities=governance_identities,
        label="pre-name-binding governance",
    )
    body = _self_hash({
        "schema_version": EXECUTION_NAME_LEDGER_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="execution-name ledger timestamp"
        ),
        "execution_contract": execution_contract_identity.as_dict(),
        "launch_ledger": launch_identity_raw,
        "execution_id": execution_id,
        "execution_name": metadata_name,
        "execution_uid": _string(
            retained_metadata.get("uid"), label="recovered execution UID"
        ),
        "execution_metadata_sha256": canonical_sha256(metadata),
        "job_uid": active["uid"],
        "job_generation": active["generation"],
        "exactly_one_new_execution": True,
        "attempt": 0,
        "max_retries": 0,
        "automatic_relaunch_licensed": False,
        "uses_realized_outcomes": False,
    }, field="execution_name_ledger_sha256")
    validate_execution_name_ledger(
        body,
        contract=contract,
        contract_identity=execution_contract_identity,
        launch_identity=launch_identity_raw,
        execution_metadata=metadata,
    )
    del launch
    identity = store.publish_or_reopen(
        str(contract["execution_name_ledger_uri"]),
        canonical_json_bytes(body),
        "application/json",
    )
    _require_exact_governance_inventory(
        store,
        prefix=str(contract["output_prefix"]),
        identities=[*governance_identities, identity],
        label="execution-name governance",
    )
    return {
        "schema_version": "corpus-retrieval-transport-execution-bound/v1",
        "execution_id": execution_id,
        "execution_name": metadata_name,
        "execution_uid": body["execution_uid"],
        "execution_name_ledger": identity,
        "automatic_relaunch_licensed": False,
    }


def _wait_for_execution_name_ledger(
    *,
    storage: GenerationPinnedStorage,
    contract: Mapping[str, object],
    contract_identity: ObjectIdentity,
    launch_identity: Mapping[str, object],
    runtime_execution: Mapping[str, object],
    timeout_seconds: int = 900,
) -> tuple[dict[str, object], dict[str, object]]:
    """Wait only on create-once GCS authority; never query the Run API."""
    timeout = _exact_int(
        timeout_seconds, label="execution-name bind timeout", minimum=1
    )
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while True:
        try:
            identity, raw = storage.resolve_current(
                str(contract["execution_name_ledger_uri"])
            )
        except CorpusRetrievalTransportError as exc:
            last_error = exc
        else:
            ledger = validate_execution_name_ledger(
                strict_json_bytes(raw, label="worker execution-name ledger"),
                contract=contract,
                contract_identity=contract_identity,
                launch_identity=launch_identity,
            )
            if (
                ledger["execution_id"] != runtime_execution["execution_id"]
                or ledger["execution_name"]
                != runtime_execution["execution_name"]
            ):
                raise CorpusRetrievalTransportError(
                    "worker execution differs from durable execution-name ledger"
                )
            return identity, ledger
        if time.monotonic() >= deadline:
            raise CorpusRetrievalTransportError(
                "durable execution-name ledger was not bound before score work"
            ) from last_error
        time.sleep(5)


class LocalIdentityReader:
    """Exact identity-to-file reader for outcome-blind real-artifact smokes."""

    def __init__(self, rows: Sequence[Mapping[str, object]]):
        self._paths: dict[tuple[str, str], tuple[ObjectIdentity, Path]] = {}
        for ordinal, raw_row in enumerate(rows):
            row = _mapping(raw_row, label=f"local object row[{ordinal}]")
            _exact_keys(
                row,
                frozenset({"identity", "path"}),
                label=f"local object row[{ordinal}]",
            )
            identity = object_identity(
                row["identity"], label=f"local object row[{ordinal}].identity"
            )
            path = Path(_string(row["path"], label="local object path")).resolve()
            key = (identity.uri, identity.generation)
            if key in self._paths:
                raise CorpusRetrievalTransportError(
                    "local object map repeats an identity"
                )
            self._paths[key] = (identity, path)

    def read(self, value: Mapping[str, object]) -> bytes:
        identity = object_identity(value, label="local read identity")
        retained = self._paths.get((identity.uri, identity.generation))
        if retained is None or retained[0] != identity:
            raise CorpusRetrievalTransportError(
                "local object map lacks the exact requested identity"
            )
        path = retained[1]
        if path.is_symlink() or not path.is_file():
            raise CorpusRetrievalTransportError("local object body is absent")
        raw = path.read_bytes()
        if len(raw) != identity.bytes or sha256(raw).hexdigest() != identity.sha256:
            raise CorpusRetrievalTransportError("local object body differs")
        return raw


class LocalCreateOncePublisher:
    """Map deterministic GCS output URIs into one empty local smoke root."""

    def __init__(self, root: Path, *, allowed_prefix: str):
        self.root = root.resolve()
        self.allowed_prefix = allowed_prefix
        if self.root.exists():
            raise CorpusRetrievalTransportError(
                "local create-once output root already exists"
            )
        self.root.mkdir(parents=True)
        self._published: dict[tuple[str, str], tuple[ObjectIdentity, Path]] = {}

    def publish(
        self, uri: str, raw: bytes, media_type: str,
    ) -> dict[str, object]:
        del media_type
        if not uri.startswith(self.allowed_prefix):
            raise CorpusRetrievalTransportError(
                "local publication escapes the suite output prefix"
            )
        relative = uri.removeprefix(self.allowed_prefix)
        if not relative or relative.startswith("/") or ".." in relative.split("/"):
            raise CorpusRetrievalTransportError(
                "local publication path is not canonical"
            )
        path = self.root / relative
        _write_once(path, raw)
        identity = ObjectIdentity(
            uri=uri,
            generation="1",
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        key = (identity.uri, identity.generation)
        if key in self._published:
            raise CorpusRetrievalTransportError(
                "local publisher repeated a supposedly create-once URI"
            )
        self._published[key] = (identity, path)
        return identity.as_dict()

    def read(self, value: Mapping[str, object]) -> bytes:
        identity = object_identity(value, label="local published identity")
        retained = self._published.get((identity.uri, identity.generation))
        if retained is None or retained[0] != identity:
            raise CorpusRetrievalTransportError(
                "local publisher lacks the exact requested identity"
            )
        raw = retained[1].read_bytes()
        if len(raw) != identity.bytes or sha256(raw).hexdigest() != identity.sha256:
            raise CorpusRetrievalTransportError(
                "local published body differs"
            )
        return raw


def _runtime_execution(environ: Mapping[str, str]) -> dict[str, object]:
    expected = {
        "CLOUD_RUN_JOB": PARKED_JOB,
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
    }
    wrong = {
        key: (environ.get(key), value)
        for key, value in expected.items()
        if environ.get(key) != value
    }
    execution_name = str(environ.get("CLOUD_RUN_EXECUTION", ""))
    execution_id = execution_name.rsplit("/", 1)[-1]
    qualified_prefix = (
        f"projects/{PROJECT}/locations/{REGION}/jobs/{PARKED_JOB}/executions/"
    )
    if (
        wrong
        or _EXECUTION.fullmatch(execution_id) is None
        or (
            execution_name != execution_id
            and not execution_name.startswith(qualified_prefix)
        )
    ):
        raise CorpusRetrievalTransportError(
            f"Cloud Run one-task/attempt-zero identity differs: {wrong}"
        )
    code_commit = _string(environ.get(CODE_ENV), label="runtime code commit")
    image_uri = _string(environ.get(IMAGE_ENV), label="runtime image URI")
    if _COMMIT.fullmatch(code_commit) is None or _IMAGE.fullmatch(image_uri) is None:
        raise CorpusRetrievalTransportError(
            "Cloud Run immutable code/image identity differs"
        )
    return {
        "execution_id": execution_id,
        "execution_name": execution_name,
        "task_index": 0,
        "attempt": 0,
        "retry_count": 0,
        "mode": "cloud-run-task",
        "code_commit": code_commit,
        "image_uri": image_uri,
        "image_digest": image_uri.rsplit("@", 1)[1],
    }


def _identity_from_args(args: argparse.Namespace, prefix: str) -> ObjectIdentity:
    return object_identity(
        {
            "uri": getattr(args, f"{prefix}_uri"),
            "generation": getattr(args, f"{prefix}_generation"),
            "sha256": getattr(args, f"{prefix}_sha256"),
            "bytes": getattr(args, f"{prefix}_bytes"),
        },
        label=f"{prefix} identity",
    )


def _add_identity_arguments(parser: argparse.ArgumentParser, prefix: str) -> None:
    option = prefix.replace("_", "-")
    parser.add_argument(f"--{option}-uri", required=True)
    parser.add_argument(f"--{option}-generation", required=True)
    parser.add_argument(f"--{option}-sha256", required=True)
    parser.add_argument(f"--{option}-bytes", required=True, type=int)


def _validate_suite_with_core(core: object, raw: bytes) -> Mapping[str, object]:
    parser = getattr(core, "parse_canonical_json_bytes", None)
    validator = getattr(core, "validate_retrieval_suite_manifest", None)
    if not callable(validator):
        validator = getattr(core, "validate_suite_manifest", None)
    if not callable(validator):
        raise CorpusRetrievalTransportError(
            "retrieval core lacks its frozen suite validator"
        )
    value = parser(raw, label="retrieval suite") if callable(parser) else (
        strict_json_bytes(raw, label="retrieval suite")
    )
    normalized = validator(value)
    result = _mapping(normalized, label="validated retrieval suite")
    if result.get("schema_version", result.get("schema")) != SUITE_SCHEMA:
        raise CorpusRetrievalTransportError("retrieval suite schema differs")
    return result


def _validate_snapshot_with_core(core: object, raw: bytes) -> Mapping[str, object]:
    parser = getattr(core, "parse_canonical_json_bytes", None)
    validator = getattr(core, "validate_snapshot_manifest", None)
    if not callable(validator):
        raise CorpusRetrievalTransportError(
            "retrieval core lacks its frozen snapshot validator"
        )
    value = parser(raw, label="retrieval snapshot") if callable(parser) else (
        strict_json_bytes(raw, label="retrieval snapshot")
    )
    normalized = validator(value)
    result = _mapping(normalized, label="validated retrieval snapshot")
    if result.get("schema_version") != (
        "corpus-retrieval-snapshot-manifest/v1"
    ):
        raise CorpusRetrievalTransportError("retrieval snapshot schema differs")
    return result


def _transport_binding(
    core: object, suite: Mapping[str, object], task_index: int,
) -> Mapping[str, object]:
    binder = getattr(core, "task_transport_binding", None)
    if not callable(binder):
        raise CorpusRetrievalTransportError(
            "retrieval core lacks its frozen task transport binding"
        )
    result = _mapping(
        binder(suite, task_index), label="retrieval task transport binding"
    )
    _exact_keys(
        result,
        frozenset({
            "output_prefix", "snapshot_manifest_identity", "task_index",
            "task_id", "result_uri",
        }),
        label="retrieval task transport binding",
    )
    if result["task_index"] != task_index:
        raise CorpusRetrievalTransportError(
            "retrieval transport binding task index differs"
        )
    object_identity(
        result["snapshot_manifest_identity"],
        label="transport snapshot manifest identity",
    )
    output_prefix = _string(
        result["output_prefix"], label="transport output prefix"
    )
    result_uri = _string(result["result_uri"], label="transport result URI")
    if (
        not output_prefix.startswith("gs://")
        or not output_prefix.endswith("/")
        or not result_uri.startswith(output_prefix)
        or result_uri != f"{output_prefix}tasks/{task_index:04d}/result.json"
    ):
        raise CorpusRetrievalTransportError(
            "retrieval task output namespace differs"
        )
    return result


def _require_one_task_manifests(
    suite: Mapping[str, object], snapshot: Mapping[str, object], task_index: int,
) -> None:
    if (
        task_index != 0
        or type(suite.get("tasks")) is not list
        or type(snapshot.get("tasks")) is not list
        or len(suite["tasks"]) != 1  # type: ignore[arg-type]
        or len(snapshot["tasks"]) != 1  # type: ignore[arg-type]
    ):
        raise CorpusRetrievalTransportError(
            "transport requires exactly manifest task index zero"
        )


def _engine_release(suite: Mapping[str, object]) -> dict[str, str]:
    value = _mapping(suite.get("engine_release"), label="suite engine release")
    _exact_keys(value, frozenset({
        "engine_version", "code_repository", "code_commit", "image_uri",
        "image_digest",
    }), label="suite engine release")
    result = {key: _string(value[key], label=f"engine release {key}") for key in value}
    if (
        result["code_repository"] != EXPECTED_CODE_REPOSITORY
        or _COMMIT.fullmatch(result["code_commit"]) is None
        or _IMAGE.fullmatch(result["image_uri"]) is None
        or not result["image_digest"].startswith("sha256:")
        or _SHA256.fullmatch(result["image_digest"].removeprefix("sha256:"))
        is None
        or result["image_uri"]
        != f"{result['image_uri'].split('@', 1)[0]}@{result['image_digest']}"
    ):
        raise CorpusRetrievalTransportError(
            "suite engine release is not immutable"
        )
    return result


def validate_suite_build_binding(
    suite: Mapping[str, object], build: Mapping[str, object],
) -> dict[str, str]:
    release = _engine_release(suite)
    if (
        release["code_repository"] != build.get("code_repository")
        or release["code_commit"] != build.get("code_sha")
        or release["image_uri"] != build.get("image")
        or release["image_digest"]
        != str(build.get("image", "")).rsplit("@", 1)[-1]
    ):
        raise CorpusRetrievalTransportError(
            "suite engine release differs from validated build"
        )
    return release


def _require_execution_release(
    execution: Mapping[str, object], suite: Mapping[str, object],
) -> None:
    release = _engine_release(suite)
    if (
        execution.get("code_commit") != release["code_commit"]
        or execution.get("image_uri") != release["image_uri"]
        or execution.get("image_digest") != release["image_digest"]
    ):
        raise CorpusRetrievalTransportError(
            "worker execution does not bind the suite engine release"
        )


def _run_and_replay_task(
    *,
    core: object,
    suite: Mapping[str, object],
    suite_identity: ObjectIdentity,
    snapshot: Mapping[str, object],
    snapshot_identity: ObjectIdentity,
    task_index: int,
    execution: Mapping[str, object],
    read_object: Callable[[Mapping[str, object]], bytes],
    publish_create_once: Callable[[str, bytes, str], Mapping[str, object]],
) -> dict[str, object]:
    runner = getattr(core, "run_retrieval_task", None)
    validator = getattr(core, "validate_retrieval_task_result", None)
    if not callable(runner) or not callable(validator):
        raise CorpusRetrievalTransportError(
            "retrieval core lacks its frozen run/replay APIs"
        )
    _require_execution_release(execution, suite)
    try:
        published = runner(
            suite_manifest=suite,
            suite_manifest_identity=suite_identity.as_dict(),
            snapshot_manifest=snapshot,
            snapshot_manifest_identity=snapshot_identity.as_dict(),
            task_index=task_index,
            execution=dict(execution),
            read_object=read_object,
            publish_create_once=publish_create_once,
        )
        authority = validator(
            published_result=published,
            suite_manifest=suite,
            suite_manifest_identity=suite_identity.as_dict(),
            snapshot_manifest=snapshot,
            snapshot_manifest_identity=snapshot_identity.as_dict(),
            read_object=read_object,
            replay=True,
        )
    except Exception as exc:
        raise CorpusRetrievalTransportError(
            "retrieval task run or generation-pinned replay failed"
        ) from exc
    envelope = _mapping(published, label="published task result")
    _exact_keys(
        envelope,
        frozenset({"authority", "object_identity"}),
        label="published task result",
    )
    result_identity = object_identity(
        envelope["object_identity"], label="published result identity"
    )
    authority_map = _mapping(authority, label="validated task authority")
    return {
        "schema_version": "corpus-retrieval-transport-task-receipt/v1",
        "task_index": task_index,
        "task_id": _transport_binding(core, suite, task_index)["task_id"],
        "result_object": result_identity.as_dict(),
        "authority_sha256": canonical_sha256(authority_map),
        "generation_pinned_replay": True,
        "uses_realized_outcomes": False,
    }


def run_local_task(
    *,
    suite_raw: bytes,
    suite_identity: ObjectIdentity,
    snapshot_raw: bytes,
    snapshot_identity: ObjectIdentity,
    object_rows: Sequence[Mapping[str, object]],
    task_index: int,
    output_dir: Path,
    execution_id: str,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    """Execute one real-artifact task through filesystem capability seams."""
    require_execute_gate(execute=execute, environ=environ)
    core = _core_module()
    suite = _validate_suite_with_core(core, suite_raw)
    snapshot = _validate_snapshot_with_core(core, snapshot_raw)
    _require_one_task_manifests(suite, snapshot, task_index)
    binding = _transport_binding(core, suite, task_index)
    if object_identity(
        binding["snapshot_manifest_identity"], label="local bound snapshot"
    ) != snapshot_identity:
        raise CorpusRetrievalTransportError("local suite/snapshot identity differs")
    if (
        len(suite_raw) != suite_identity.bytes
        or sha256(suite_raw).hexdigest() != suite_identity.sha256
        or len(snapshot_raw) != snapshot_identity.bytes
        or sha256(snapshot_raw).hexdigest() != snapshot_identity.sha256
    ):
        raise CorpusRetrievalTransportError("local manifest bytes differ")
    local_execution = _string(execution_id, label="local execution id")
    release = _engine_release(suite)
    execution = {
        "execution_id": local_execution,
        "execution_name": local_execution,
        "task_index": task_index,
        "attempt": 0,
        "retry_count": 0,
        "mode": "local-real-smoke",
        "code_commit": release["code_commit"],
        "image_uri": release["image_uri"],
        "image_digest": release["image_digest"],
    }
    source = LocalIdentityReader(object_rows)
    publisher = LocalCreateOncePublisher(
        output_dir, allowed_prefix=str(binding["output_prefix"])
    )

    def read_exact(identity: Mapping[str, object]) -> bytes:
        normalized = object_identity(identity, label="local chained read")
        if (normalized.uri, normalized.generation) in publisher._published:  # noqa: SLF001
            return publisher.read(normalized.as_dict())
        return source.read(normalized.as_dict())

    return _run_and_replay_task(
        core=core,
        suite=suite,
        suite_identity=suite_identity,
        snapshot=snapshot,
        snapshot_identity=snapshot_identity,
        task_index=task_index,
        execution=execution,
        read_object=read_exact,
        publish_create_once=publisher.publish,
    )


def execute_cloud_task(
    *,
    suite_identity: ObjectIdentity,
    snapshot_identity: ObjectIdentity,
    execution_contract_identity: ObjectIdentity,
    task_index: int,
    execute: bool,
    environ: Mapping[str, str],
    storage: GenerationPinnedStorage | None = None,
) -> dict[str, object]:
    """Cloud worker entry: one gated task, no Cloud Run control-plane client."""
    require_execute_gate(execute=execute, environ=environ)
    store = GenerationPinnedStorage(
        execute=execute, environ=environ,
    ) if storage is None else storage
    contract_raw = store.read(execution_contract_identity.as_dict())
    contract = validate_execution_contract(
        strict_json_bytes(contract_raw, label="execution contract")
    )
    if (
        contract["suite_manifest_identity"] != suite_identity.as_dict()
        or contract["snapshot_manifest_identity"] != snapshot_identity.as_dict()
        or contract["task_index"] != task_index
        or task_index != 0
    ):
        raise CorpusRetrievalTransportError(
            "Cloud worker manifest/task contract differs"
        )
    runtime = _runtime_execution(environ)
    if runtime["task_index"] != task_index:
        raise CorpusRetrievalTransportError("Cloud runtime task index differs")
    build = _mapping(contract["build"], label="Cloud execution build")
    if (
        build.get("code_sha") != runtime["code_commit"]
        or build.get("image") != runtime["image_uri"]
        or environ.get(BUILD_ENV) != build.get("build_id")
    ):
        raise CorpusRetrievalTransportError(
            "Cloud runtime build/code/image differs from execution contract"
        )
    governance = _reopen_governance(
        storage=store,
        contract=contract,
        contract_identity=execution_contract_identity,
        exact_name_only=True,
    )
    launch_identity, launch_raw = store.resolve_current(
        str(contract["launch_ledger_uri"])
    )
    validate_launch_ledger(
        strict_json_bytes(launch_raw, label="worker launch ledger"),
        contract=contract,
        contract_identity=execution_contract_identity,
        intent_identity=governance["launch_intent_identity"],
    )
    _wait_for_execution_name_ledger(
        storage=store,
        contract=contract,
        contract_identity=execution_contract_identity,
        launch_identity=launch_identity,
        runtime_execution=runtime,
    )
    # The runtime service account has exact-prefix object GET/CREATE authority,
    # not bucket-wide LIST.  Every known authority object is reopened and
    # content-bound above.  The operator performs the sole-generation and
    # no-extra-object censuses immediately before launch and at acceptance.
    core = _core_module()
    suite = _mapping(governance["suite"], label="Cloud suite")
    snapshot = _mapping(governance["snapshot"], label="Cloud snapshot")
    binding = _transport_binding(core, suite, task_index)
    if (
        object_identity(
            binding["snapshot_manifest_identity"],
            label="Cloud bound snapshot",
        ) != snapshot_identity
        or binding["result_uri"] != contract["result_uri"]
    ):
        raise CorpusRetrievalTransportError("Cloud task transport binding differs")
    return _run_and_replay_task(
        core=core,
        suite=suite,
        suite_identity=suite_identity,
        snapshot=snapshot,
        snapshot_identity=snapshot_identity,
        task_index=task_index,
        execution=runtime,
        read_object=store.read,
        publish_create_once=store.publish,
    )


def validate_terminal_execution(
    value: object,
    *,
    execution_name: str,
    execution_contract: object,
    execution_contract_identity: object,
) -> dict[str, object]:
    contract = validate_execution_contract(execution_contract)
    contract_identity = object_identity(
        execution_contract_identity, label="terminal execution contract"
    )
    item = _mapping(value, label="terminal execution metadata")
    metadata = _mapping(item.get("metadata"), label="execution metadata")
    spec = _mapping(item.get("spec"), label="execution spec")
    status = _mapping(item.get("status"), label="execution status")
    full_name = _string(metadata.get("name"), label="execution name")
    name = full_name.rsplit("/", 1)[-1]
    expected_name = _string(execution_name, label="expected execution name")
    if (
        full_name != expected_name
        or _EXECUTION.fullmatch(name) is None
    ):
        raise CorpusRetrievalTransportError("terminal execution name differs")
    uid = _string(metadata.get("uid"), label="terminal execution UID")
    labels = _mapping(metadata.get("labels"), label="execution labels")
    job = _mapping(contract["job_execution"], label="execution contract job")
    if (
        labels.get("run.googleapis.com/job") != PARKED_JOB
        or labels.get("run.googleapis.com/jobUid") != job["uid"]
        or str(labels.get("run.googleapis.com/jobGeneration"))
        != str(job["generation"])
    ):
        raise CorpusRetrievalTransportError(
            "terminal execution job UID/generation binding differs"
        )
    if (
        _exact_int(spec.get("taskCount"), label="execution task count") != 1
        or _exact_int(spec.get("parallelism"), label="execution parallelism")
        != 1
    ):
        raise CorpusRetrievalTransportError(
            "terminal execution is not one-task serial"
        )
    task = _mapping(spec.get("template", {}).get("spec", {}), label="execution task")
    containers = task.get("containers")
    if type(containers) is not list or len(containers) != 1 or not isinstance(
        containers[0], Mapping
    ):
        raise CorpusRetrievalTransportError("terminal execution container differs")
    container = containers[0]
    build = _mapping(contract["build"], label="terminal execution build")
    expected_env = {
        ENABLE_ENV: "1",
        IMAGE_ENV: str(build["image"]),
        BUILD_ENV: str(build["build_id"]),
        CODE_ENV: str(build["code_sha"]),
    }
    expected_args = cloud_worker_args(
        execution_contract=contract,
        execution_contract_identity=contract_identity.as_dict(),
    )
    if (
        _exact_int(task.get("maxRetries"), label="execution max retries") != 0
        or task.get("timeoutSeconds") != EXPECTED_TIMEOUT_SECONDS
        or task.get("serviceAccountName") != contract["service_account"]
        or task.get("volumes", []) != []
        or container.get("image") != build["image"]
        or container.get("command") != PARKED_COMMAND
        or container.get("args") != expected_args
        or _container_environment(container) != expected_env
        or container.get("resources", {}).get("limits") != EXPECTED_RESOURCES
        or container.get("volumeMounts", []) != []
    ):
        raise CorpusRetrievalTransportError(
            "terminal execution immutable command/spec binding differs"
        )
    if _completion_state(item) != "True":
        raise CorpusRetrievalTransportError(
            "execution is not strict terminal success"
        )
    counts = {
        short: _exact_int(status.get(key, 0), label=f"execution {short}")
        for key, short in (
            ("succeededCount", "succeeded"),
            ("failedCount", "failed"),
            ("cancelledCount", "cancelled"),
            ("retriedCount", "retried"),
        )
    }
    if counts != {
        "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
    }:
        raise CorpusRetrievalTransportError(
            "terminal execution counters differ"
        )
    return {
        "execution_id": name,
        "execution_name": full_name,
        "execution_uid": uid,
        "job": PARKED_JOB,
        "job_uid": job["uid"],
        "job_generation": job["generation"],
        "job_spec_sha256": job["spec_sha256"],
        "task_count": 1,
        "attempt": 0,
        "retry_count": 0,
        "state": "True",
        "counters": counts,
        "metadata_sha256": canonical_sha256(item),
    }


def validate_result_execution_binding(
    result_authority: object,
    *,
    terminal: Mapping[str, object],
) -> Mapping[str, object]:
    authority = _mapping(result_authority, label="task result authority")
    execution = _mapping(
        authority.get("execution"), label="task result execution"
    )
    if (
        execution.get("execution_id") != terminal["execution_id"]
        or execution.get("execution_name") != terminal["execution_name"]
        or execution.get("attempt") != 0
        or execution.get("retry_count") != 0
        or execution.get("mode") != "cloud-run-task"
    ):
        raise CorpusRetrievalTransportError(
            "task-result execution differs from exact terminal execution"
        )
    return execution


def _result_output_identities(
    result_authority: Mapping[str, object],
    result_identity: Mapping[str, object],
) -> list[object]:
    rows = result_authority.get("sidecars")
    if type(rows) is not list:
        raise CorpusRetrievalTransportError("task result sidecars differ")
    identities: list[object] = []
    for index, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"task result sidecar[{index}]")
        identities.append(object_identity(
            row.get("object_identity"),
            label=f"task result sidecar[{index}] identity",
        ).as_dict())
    identities.append(object_identity(
        result_identity, label="task result identity"
    ).as_dict())
    return identities


def finish_cloud_task(
    *,
    execution_contract_identity: ObjectIdentity,
    execution_name: str,
    terminal_metadata: object,
    deployed_job: object,
    post_terminal_job: object,
    executions_after: object,
    schedulers_after: object,
    finished_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
    storage: GenerationPinnedStorage | None = None,
) -> dict[str, object]:
    """Strict-terminal, generation-pinned harvest; never calls Cloud Run."""
    require_execute_gate(execute=execute, environ=environ)
    store = GenerationPinnedStorage(
        execute=execute, environ=environ,
    ) if storage is None else storage
    contract = _load_execution_contract(store, execution_contract_identity)
    governance = _reopen_governance(
        storage=store,
        contract=contract,
        contract_identity=execution_contract_identity,
    )
    launch_identity, launch_raw = store.resolve_unique(
        str(contract["launch_ledger_uri"])
    )
    validate_launch_ledger(
        strict_json_bytes(launch_raw, label="terminal launch ledger"),
        contract=contract,
        contract_identity=execution_contract_identity,
        intent_identity=governance["launch_intent_identity"],
    )
    name_identity, name_raw = store.resolve_unique(
        str(contract["execution_name_ledger_uri"])
    )
    name_ledger = validate_execution_name_ledger(
        strict_json_bytes(name_raw, label="terminal execution-name ledger"),
        contract=contract,
        contract_identity=execution_contract_identity,
        launch_identity=launch_identity,
    )
    if execution_name != name_ledger["execution_name"]:
        raise CorpusRetrievalTransportError(
            "requested finisher execution differs from durable name ledger"
        )
    terminal = validate_terminal_execution(
        terminal_metadata,
        execution_name=str(name_ledger["execution_name"]),
        execution_contract=contract,
        execution_contract_identity=execution_contract_identity.as_dict(),
    )
    if (
        terminal["execution_id"] != name_ledger["execution_id"]
        or terminal["execution_name"] != name_ledger["execution_name"]
        or terminal["execution_uid"] != name_ledger["execution_uid"]
    ):
        raise CorpusRetrievalTransportError(
            "terminal execution differs from durable name/UID binding"
        )
    _validate_current_parked_job(deployed_job, contract=contract)
    _validate_current_parked_job(post_terminal_job, contract=contract)
    validate_post_terminal_parked_job(
        deployed=deployed_job, post_terminal=post_terminal_job,
    )
    validate_reuse_census(
        job=post_terminal_job,
        executions=executions_after,
        schedulers=schedulers_after,
    )
    before_names = contract.get("execution_names_before")
    if before_names is None:
        # The preflight hash is authoritative; the explicit names are copied
        # into the execution contract below for terminal one-execution proof.
        raise CorpusRetrievalTransportError(
            "execution contract lacks its preflight execution-name census"
        )
    after_names = execution_census_names(executions_after)
    if set(after_names).difference(before_names) != {terminal["execution_id"]} or (
        set(before_names).difference(after_names)
    ):
        raise CorpusRetrievalTransportError(
            "exactly-one new execution law differs"
        )

    suite_identity = object_identity(
        governance["suite_identity"], label="terminal suite identity"
    )
    snapshot_identity = object_identity(
        governance["snapshot_identity"], label="terminal snapshot identity"
    )
    core = _core_module()
    suite = _mapping(governance["suite"], label="terminal suite")
    snapshot = _mapping(governance["snapshot"], label="terminal snapshot")
    result_identity_raw, result_raw = store.resolve_unique(str(contract["result_uri"]))
    result_authority = _mapping(
        strict_json_bytes(result_raw, label="terminal task result"),
        label="terminal task result",
    )
    validator = getattr(core, "validate_retrieval_task_result", None)
    if not callable(validator):
        raise CorpusRetrievalTransportError(
            "retrieval core lacks its frozen task-result validator"
        )
    try:
        replayed = validator(
            published_result={
                "authority": result_authority,
                "object_identity": result_identity_raw,
            },
            suite_manifest=suite,
            suite_manifest_identity=suite_identity.as_dict(),
            snapshot_manifest=snapshot,
            snapshot_manifest_identity=snapshot_identity.as_dict(),
            read_object=store.read,
            replay=True,
        )
    except Exception as exc:
        raise CorpusRetrievalTransportError(
            "terminal generation-pinned task-result replay failed"
        ) from exc
    replayed_authority = _mapping(replayed, label="terminal replay authority")
    if canonical_json_bytes(replayed_authority) != result_raw:
        raise CorpusRetrievalTransportError(
            "terminal task authority differs from retained result bytes"
        )
    validate_result_execution_binding(result_authority, terminal=terminal)
    published_result = {
        "authority": result_authority,
        "object_identity": result_identity_raw,
    }
    retained_identities: list[object] = [
        suite_identity.as_dict(),
        governance["prefix_claim_identity"],
        governance["runtime_iam_evidence_identity"],
        execution_contract_identity.as_dict(),
        governance["launch_intent_identity"],
        launch_identity,
        name_identity,
        *_result_output_identities(result_authority, result_identity_raw),
    ]
    _require_only_inventory_uris(
        store,
        prefix=str(contract["output_prefix"]),
        required_identities=retained_identities,
        optional_uris=[
            str(contract["completion_uri"]),
            str(contract["terminal_receipt_uri"]),
        ],
        label="terminal pre-completion",
    )
    completion_builder = getattr(
        core, "build_retrieval_batch_completion", None
    )
    completion_validator = getattr(
        core, "validate_retrieval_batch_completion", None
    )
    if not callable(completion_builder) or not callable(completion_validator):
        raise CorpusRetrievalTransportError(
            "retrieval core lacks its frozen completion APIs"
        )
    try:
        completion = completion_builder(
            suite_manifest=suite,
            suite_manifest_identity=suite_identity.as_dict(),
            snapshot_manifest=snapshot,
            snapshot_manifest_identity=snapshot_identity.as_dict(),
            published_results=[published_result],
            read_object=store.read,
        )
    except Exception as exc:
        raise CorpusRetrievalTransportError(
            "retrieval batch completion construction failed"
        ) from exc
    completion_raw = canonical_json_bytes(completion)
    completion_identity = store.publish_or_reopen(
        str(contract["completion_uri"]),
        completion_raw,
        "application/json",
    )
    if store.read(completion_identity) != completion_raw:
        raise CorpusRetrievalTransportError(
            "published retrieval completion did not reopen byte-identically"
        )
    try:
        replayed_completion = completion_validator(
            completion,
            suite_manifest=suite,
            suite_manifest_identity=suite_identity.as_dict(),
            snapshot_manifest=snapshot,
            snapshot_manifest_identity=snapshot_identity.as_dict(),
            published_results=[published_result],
            read_object=store.read,
        )
    except Exception as exc:
        raise CorpusRetrievalTransportError(
            "retrieval batch completion replay failed"
        ) from exc
    if canonical_json_bytes(replayed_completion) != completion_raw:
        raise CorpusRetrievalTransportError(
            "retrieval batch completion canonical replay differs"
        )
    before_terminal_identities = [*retained_identities, completion_identity]
    _require_only_inventory_uris(
        store,
        prefix=str(contract["output_prefix"]),
        required_identities=before_terminal_identities,
        optional_uris=[str(contract["terminal_receipt_uri"])],
        label="terminal pre-receipt",
    )
    expected_before_terminal_inventory = sorted(
        [
            _inventory_row_for_identity(value)
            for value in before_terminal_identities
        ],
        key=lambda row: (row["uri"], row["generation"]),
    )
    receipt = _self_hash({
        "schema_version": TERMINAL_RECEIPT_SCHEMA,
        "finished_at_utc": _timestamp(
            finished_at_utc, label="terminal finish timestamp"
        ),
        "execution_contract": execution_contract_identity.as_dict(),
        "prefix_claim": governance["prefix_claim_identity"],
        "runtime_iam_evidence": governance[
            "runtime_iam_evidence_identity"
        ],
        "launch_intent": governance["launch_intent_identity"],
        "launch_ledger": launch_identity,
        "execution_name_ledger": name_identity,
        "execution": terminal,
        "suite_manifest_identity": suite_identity.as_dict(),
        "snapshot_manifest_identity": snapshot_identity.as_dict(),
        "task_index": contract["task_index"],
        "task_id": contract["task_id"],
        "result_object": result_identity_raw,
        "task_result_sha256": result_authority["task_result_sha256"],
        "batch_completion": completion_identity,
        "batch_completion_sha256": completion["batch_completion_sha256"],
        "post_terminal_job": job_identity(post_terminal_job),
        "output_inventory_before_terminal": expected_before_terminal_inventory,
        "output_inventory_before_terminal_sha256": canonical_sha256(
            expected_before_terminal_inventory
        ),
        "one_execution": True,
        "attempt_zero": True,
        "retry_count": 0,
        "generation_pinned_replay": True,
        "successful_deployment_remains_parked": True,
        "uses_realized_outcomes": False,
        "bigquery_access_licensed": False,
        "corpus_fill_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
    }, field="terminal_receipt_sha256")
    terminal_raw = canonical_json_bytes(receipt)
    terminal_identity = store.publish_or_reopen(
        str(contract["terminal_receipt_uri"]),
        terminal_raw,
        "application/json",
    )
    if store.read(terminal_identity) != terminal_raw:
        raise CorpusRetrievalTransportError(
            "terminal receipt did not generation-pin reopen"
        )
    final_identities = [*before_terminal_identities, terminal_identity]
    _require_exact_inventory(
        store,
        prefix=str(contract["output_prefix"]),
        identities=final_identities,
        label="terminal final prefix",
    )
    final_inventory = sorted(
        [_inventory_row_for_identity(value) for value in final_identities],
        key=lambda row: (row["uri"], row["generation"]),
    )
    return {
        "schema_version": "corpus-retrieval-transport-finish/v1",
        "execution_id": terminal["execution_id"],
        "execution_uid": terminal["execution_uid"],
        "task_index": contract["task_index"],
        "result_object": result_identity_raw,
        "batch_completion": completion_identity,
        "terminal_receipt": terminal_identity,
        "task_result_sha256": result_authority["task_result_sha256"],
        "final_output_inventory_sha256": canonical_sha256(final_inventory),
        "final_output_object_count": len(final_inventory),
        "generation_pinned_replay": True,
        "successful_deployment_remains_parked": True,
        "uses_realized_outcomes": False,
    }


def validate_only(
    *, suite_raw: bytes, suite_identity: ObjectIdentity,
    snapshot_raw: bytes, snapshot_identity: ObjectIdentity,
    object_rows: Sequence[Mapping[str, object]], task_index: int,
) -> dict[str, object]:
    """Validate the same identities used by Cloud without running scoring."""
    if len(suite_raw) != suite_identity.bytes or sha256(suite_raw).hexdigest() != (
        suite_identity.sha256
    ):
        raise CorpusRetrievalTransportError("local suite identity differs")
    if (
        len(snapshot_raw) != snapshot_identity.bytes
        or sha256(snapshot_raw).hexdigest() != snapshot_identity.sha256
    ):
        raise CorpusRetrievalTransportError("local snapshot identity differs")
    core = _core_module()
    suite = _validate_suite_with_core(core, suite_raw)
    snapshot = _validate_snapshot_with_core(core, snapshot_raw)
    _require_one_task_manifests(suite, snapshot, task_index)
    _exact_int(task_index, label="task index")
    binding = _transport_binding(core, suite, task_index)
    bound_snapshot = object_identity(
        binding["snapshot_manifest_identity"],
        label="bound snapshot identity",
    )
    if bound_snapshot != snapshot_identity:
        raise CorpusRetrievalTransportError(
            "suite/snapshot transport identity differs"
        )
    if suite.get("snapshot_id") != snapshot.get("snapshot_id"):
        raise CorpusRetrievalTransportError("suite/snapshot ID differs")
    reader = LocalIdentityReader(object_rows)
    # Reopening all mapped bodies is outcome-blind and catches stale paths now,
    # before an immutable build.  The task run will request the exact subset.
    for identity, _path in reader._paths.values():  # noqa: SLF001
        reader.read(identity.as_dict())
    return {
        "schema": "corpus-retrieval-local-validation/v1",
        "suite_identity": suite_identity.as_dict(),
        "suite_manifest_sha256": suite.get(
            "suite_manifest_sha256", suite.get("manifest_sha256")
        ),
        "snapshot_identity": snapshot_identity.as_dict(),
        "snapshot_manifest_sha256": snapshot.get("snapshot_manifest_sha256"),
        "task_index": task_index,
        "task_id": binding["task_id"],
        "result_uri": binding["result_uri"],
        "mapped_object_count": len(reader._paths),  # noqa: SLF001
        "score_work_executed": False,
        "cloud_client_constructed": False,
        "uses_realized_outcomes": False,
    }


def _arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Default-off transport for one generic corpus retrieval task"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("parked", help="default-off job command; performs no work")

    canonicalize = sub.add_parser("canonicalize-external-json")
    canonicalize.add_argument("--raw", type=Path, required=True)
    canonicalize.add_argument("--output", type=Path, required=True)

    inventory = sub.add_parser("inventory")
    inventory.add_argument("--prefix", required=True)
    inventory.add_argument("--output", type=Path, required=True)
    inventory.add_argument("--execute", action="store_true")

    validate = sub.add_parser("validate-only")
    validate.add_argument("--suite", type=Path, required=True)
    _add_identity_arguments(validate, "suite")
    validate.add_argument("--snapshot", type=Path, required=True)
    _add_identity_arguments(validate, "snapshot")
    validate.add_argument("--object-map", type=Path, required=True)
    validate.add_argument("--task-index", type=int, required=True)
    validate.add_argument("--output", type=Path, required=True)

    local = sub.add_parser("run-local")
    local.add_argument("--suite", type=Path, required=True)
    _add_identity_arguments(local, "suite")
    local.add_argument("--snapshot", type=Path, required=True)
    _add_identity_arguments(local, "snapshot")
    local.add_argument("--object-map", type=Path, required=True)
    local.add_argument("--task-index", type=int, required=True)
    local.add_argument("--output-dir", type=Path, required=True)
    local.add_argument("--output", type=Path, required=True)
    local.add_argument("--execution-id", required=True)
    local.add_argument("--execute", action="store_true")

    cloud = sub.add_parser("execute-task")
    _add_identity_arguments(cloud, "suite")
    _add_identity_arguments(cloud, "snapshot")
    _add_identity_arguments(cloud, "execution_contract")
    cloud.add_argument("--task-index", type=int, required=True)
    cloud.add_argument("--execute", action="store_true")

    build = sub.add_parser("validate-build")
    build.add_argument("--metadata", type=Path, required=True)
    build.add_argument("--build-id", required=True)
    build.add_argument(
        "--code-repository", default=EXPECTED_CODE_REPOSITORY,
    )
    build.add_argument("--code-sha", required=True)
    build.add_argument("--image", required=True)
    build.add_argument("--output", type=Path, required=True)

    reuse = sub.add_parser("validate-reuse")
    reuse.add_argument("--job", type=Path, required=True)
    reuse.add_argument("--executions", type=Path, required=True)
    reuse.add_argument("--schedulers", type=Path, required=True)
    reuse.add_argument("--output", type=Path, required=True)

    parked = sub.add_parser("validate-parked-job")
    parked.add_argument("--job", type=Path, required=True)
    parked.add_argument("--uid", required=True)
    parked.add_argument("--image", required=True)
    parked.add_argument("--code-sha", required=True)
    parked.add_argument("--build-id", required=True)
    parked.add_argument("--service-account", required=True)
    parked.add_argument("--output", type=Path, required=True)

    rolled_back = sub.add_parser("validate-preacceptance-rollback")
    rolled_back.add_argument("--before", type=Path, required=True)
    rolled_back.add_argument("--rolled-back", type=Path, required=True)
    rolled_back.add_argument("--output", type=Path, required=True)

    retained = sub.add_parser("validate-post-terminal-parked-job")
    retained.add_argument("--deployed", type=Path, required=True)
    retained.add_argument("--post-terminal", type=Path, required=True)
    retained.add_argument("--output", type=Path, required=True)

    iam = sub.add_parser("build-runtime-iam-evidence")
    iam.add_argument("--suite", type=Path, required=True)
    _add_identity_arguments(iam, "suite")
    iam.add_argument("--snapshot", type=Path, required=True)
    _add_identity_arguments(iam, "snapshot")
    iam.add_argument("--candidate-rows", type=Path, required=True)
    iam.add_argument("--player-catalog", type=Path, required=True)
    iam.add_argument("--task-index", type=int, required=True)
    iam.add_argument("--service-account", required=True)
    iam.add_argument("--read-prefix", action="append", required=True)
    iam.add_argument("--project-policy", type=Path, required=True)
    iam.add_argument(
        "--bucket-policy", action="append", required=True,
        help="BUCKET=/path/to/canonical-policy.json",
    )
    iam.add_argument("--bucket-metadata", type=Path, required=True)
    iam.add_argument("--captured-at-utc", required=True)
    iam.add_argument("--output", type=Path, required=True)

    preflight = sub.add_parser("create-preflight")
    preflight.add_argument("--suite", type=Path, required=True)
    _add_identity_arguments(preflight, "suite")
    preflight.add_argument("--snapshot", type=Path, required=True)
    _add_identity_arguments(preflight, "snapshot")
    preflight.add_argument("--candidate-rows", type=Path, required=True)
    preflight.add_argument("--player-catalog", type=Path, required=True)
    preflight.add_argument("--task-index", type=int, required=True)
    preflight.add_argument("--build-metadata", type=Path, required=True)
    preflight.add_argument("--build-id", required=True)
    preflight.add_argument("--code-sha", required=True)
    preflight.add_argument("--image", required=True)
    preflight.add_argument("--service-account", required=True)
    preflight.add_argument("--runtime-iam-evidence", type=Path, required=True)
    preflight.add_argument("--job-before", type=Path, required=True)
    preflight.add_argument("--job-before-export", type=Path, required=True)
    preflight.add_argument("--executions", type=Path, required=True)
    preflight.add_argument("--schedulers", type=Path, required=True)
    preflight.add_argument("--inventory", type=Path, required=True)
    preflight.add_argument("--created-at-utc", required=True)
    preflight.add_argument("--output", type=Path, required=True)

    contract = sub.add_parser("create-execution-contract")
    contract.add_argument("--preflight", type=Path, required=True)
    contract.add_argument("--updated-job", type=Path, required=True)
    contract.add_argument("--created-at-utc", required=True)
    contract.add_argument("--output", type=Path, required=True)

    publish = sub.add_parser("publish-governance")
    publish.add_argument("--preflight", type=Path, required=True)
    publish.add_argument("--execution-contract", type=Path, required=True)
    publish.add_argument("--runtime-iam-evidence", type=Path, required=True)
    publish.add_argument("--published-at-utc", required=True)
    publish.add_argument("--output", type=Path, required=True)
    publish.add_argument("--execute", action="store_true")

    render = sub.add_parser("worker-args")
    render.add_argument("--execution-contract", type=Path, required=True)
    _add_identity_arguments(render, "execution_contract")
    render.add_argument("--format", choices=("json", "csv"), default="json")

    launch = sub.add_parser("consume-launch")
    _add_identity_arguments(launch, "execution_contract")
    launch.add_argument("--job", type=Path, required=True)
    launch.add_argument("--executions", type=Path, required=True)
    launch.add_argument("--schedulers", type=Path, required=True)
    launch.add_argument("--created-at-utc", required=True)
    launch.add_argument("--output", type=Path, required=True)
    launch.add_argument("--execute", action="store_true")

    bind = sub.add_parser("bind-execution-name")
    _add_identity_arguments(bind, "execution_contract")
    bind.add_argument("--execution-metadata", type=Path, required=True)
    bind.add_argument("--job", type=Path, required=True)
    bind.add_argument("--executions", type=Path, required=True)
    bind.add_argument("--schedulers", type=Path, required=True)
    bind.add_argument("--created-at-utc", required=True)
    bind.add_argument("--output", type=Path, required=True)
    bind.add_argument("--execute", action="store_true")

    finish = sub.add_parser("finish-task")
    _add_identity_arguments(finish, "execution_contract")
    finish.add_argument("--execution", required=True)
    finish.add_argument("--terminal-metadata", type=Path, required=True)
    finish.add_argument("--deployed-job", type=Path, required=True)
    finish.add_argument("--post-terminal-job", type=Path, required=True)
    finish.add_argument("--executions-after", type=Path, required=True)
    finish.add_argument("--schedulers-after", type=Path, required=True)
    finish.add_argument("--finished-at-utc", required=True)
    finish.add_argument("--output", type=Path, required=True)
    finish.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments().parse_args(argv)
    if args.command == "parked":
        print("CORPUS_RETRIEVAL_PARKED default_off=true client_constructed=false")
        return 0
    if args.command == "canonicalize-external-json":
        if args.raw.is_symlink() or not args.raw.is_file():
            raise CorpusRetrievalTransportError("external JSON input is absent")
        value = external_json_bytes(args.raw.read_bytes(), label="external JSON")
        _write_once(args.output, canonical_json_bytes(value))
        return 0
    if args.command == "validate-build":
        result = validate_build_metadata(
            _load_json_file(args.metadata, label="build metadata"),
            build_id=args.build_id,
            code_sha=args.code_sha,
            image=args.image,
            code_repository=args.code_repository,
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0
    if args.command == "validate-reuse":
        result = validate_reuse_census(
            job=_load_json_file(args.job, label="job metadata"),
            executions=_load_json_file(args.executions, label="execution census"),
            schedulers=_load_json_file(args.schedulers, label="scheduler census"),
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0
    if args.command == "validate-parked-job":
        result = validate_parked_job(
            _load_json_file(args.job, label="updated job"),
            expected_uid=args.uid,
            expected_image=args.image,
            expected_code_sha=args.code_sha,
            expected_build_id=args.build_id,
            expected_service_account=args.service_account,
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0
    if args.command == "validate-preacceptance-rollback":
        result = validate_preacceptance_rollback(
            before=_load_json_file(args.before, label="job before"),
            rolled_back=_load_json_file(
                args.rolled_back, label="rolled-back job"
            ),
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0
    if args.command == "validate-post-terminal-parked-job":
        result = validate_post_terminal_parked_job(
            deployed=_load_json_file(args.deployed, label="deployed job"),
            post_terminal=_load_json_file(
                args.post_terminal, label="post-terminal job"
            ),
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0
    if args.command == "inventory":
        storage = GenerationPinnedStorage(
            execute=args.execute, environ=os.environ,
        )
        _write_once(
            args.output, canonical_json_bytes(storage.inventory(args.prefix))
        )
        return 0

    if args.command == "worker-args":
        identity = _identity_from_args(args, "execution_contract")
        contract_value = _load_json_file(
            args.execution_contract, label="execution contract"
        )
        rendered = cloud_worker_args(
            execution_contract=contract_value,
            execution_contract_identity=identity.as_dict(),
        )
        if args.format == "csv":
            if any("," in part or "\n" in part for part in rendered):
                raise CorpusRetrievalTransportError(
                    "worker argument cannot be represented for gcloud"
                )
            print(",".join(rendered))
        else:
            print(canonical_json_bytes(rendered).decode("utf-8"))
        return 0

    if args.command == "create-execution-contract":
        result = build_execution_contract(
            preflight=_load_json_file(args.preflight, label="preflight"),
            updated_job=_load_json_file(args.updated_job, label="updated job"),
            created_at_utc=args.created_at_utc,
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0

    if args.command == "publish-governance":
        result = publish_transport_governance(
            preflight=_load_json_file(args.preflight, label="preflight"),
            execution_contract_raw=args.execution_contract.read_bytes(),
            runtime_iam_evidence_raw=args.runtime_iam_evidence.read_bytes(),
            published_at_utc=args.published_at_utc,
            storage=GenerationPinnedStorage(
                execute=args.execute, environ=os.environ,
            ),
            execute=args.execute,
            environ=os.environ,
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0

    if args.command == "consume-launch":
        result = publish_launch_ledger(
            execution_contract_identity=_identity_from_args(
                args, "execution_contract"
            ),
            job=_load_json_file(args.job, label="current parked job"),
            executions=_load_json_file(
                args.executions, label="prelaunch execution census"
            ),
            schedulers=_load_json_file(
                args.schedulers, label="prelaunch scheduler census"
            ),
            created_at_utc=args.created_at_utc,
            execute=args.execute,
            environ=os.environ,
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0

    if args.command == "bind-execution-name":
        result = bind_execution_name(
            execution_contract_identity=_identity_from_args(
                args, "execution_contract"
            ),
            execution_metadata=_load_json_file(
                args.execution_metadata, label="execution metadata"
            ),
            job=_load_json_file(args.job, label="current parked job"),
            executions=_load_json_file(
                args.executions, label="execution recovery census"
            ),
            schedulers=_load_json_file(
                args.schedulers, label="execution recovery scheduler census"
            ),
            created_at_utc=args.created_at_utc,
            execute=args.execute,
            environ=os.environ,
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0

    if args.command == "finish-task":
        result = finish_cloud_task(
            execution_contract_identity=_identity_from_args(
                args, "execution_contract"
            ),
            execution_name=args.execution,
            terminal_metadata=_load_json_file(
                args.terminal_metadata, label="terminal execution metadata"
            ),
            deployed_job=_load_json_file(
                args.deployed_job, label="deployed job"
            ),
            post_terminal_job=_load_json_file(
                args.post_terminal_job, label="post-terminal job"
            ),
            executions_after=_load_json_file(
                args.executions_after, label="post-terminal execution census"
            ),
            schedulers_after=_load_json_file(
                args.schedulers_after, label="post-terminal scheduler census"
            ),
            finished_at_utc=args.finished_at_utc,
            execute=args.execute,
            environ=os.environ,
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0

    suite_identity = _identity_from_args(args, "suite")
    if args.command == "execute-task":
        result = execute_cloud_task(
            suite_identity=suite_identity,
            snapshot_identity=_identity_from_args(args, "snapshot"),
            execution_contract_identity=_identity_from_args(
                args, "execution_contract"
            ),
            task_index=args.task_index,
            execute=args.execute,
            environ=os.environ,
        )
        print(canonical_json_bytes(result).decode("utf-8"))
        return 0
    suite_raw = args.suite.read_bytes()
    if args.command == "validate-only":
        snapshot_identity = _identity_from_args(args, "snapshot")
        rows = _load_json_file(args.object_map, label="local object map")
        if type(rows) is not list:
            raise CorpusRetrievalTransportError("local object map must be an array")
        result = validate_only(
            suite_raw=suite_raw,
            suite_identity=suite_identity,
            snapshot_raw=args.snapshot.read_bytes(),
            snapshot_identity=snapshot_identity,
            object_rows=rows,
            task_index=args.task_index,
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0

    if args.command == "build-runtime-iam-evidence":
        snapshot_identity = _identity_from_args(args, "snapshot")
        snapshot_raw = args.snapshot.read_bytes()
        core = _core_module()
        suite = _validate_suite_with_core(core, suite_raw)
        snapshot = _validate_snapshot_with_core(core, snapshot_raw)
        _require_one_task_manifests(suite, snapshot, args.task_index)
        rows = []
        for raw_binding in args.bucket_policy:
            bucket, marker, raw_path = raw_binding.partition("=")
            if not marker or not bucket or not raw_path:
                raise CorpusRetrievalTransportError(
                    "bucket policy must be BUCKET=/path/to/policy.json"
                )
            rows.append({
                "bucket": bucket,
                "policy": _load_json_file(
                    Path(raw_path), label=f"bucket {bucket} policy"
                ),
            })
        result = build_runtime_iam_evidence(
            captured_at_utc=args.captured_at_utc,
            service_account=args.service_account,
            read_prefixes=args.read_prefix,
            output_prefix=str(suite["output_prefix"]),
            project_policy=_mapping(
                _load_json_file(args.project_policy, label="project IAM policy"),
                label="project IAM policy",
            ),
            bucket_policies=rows,
            required_read_uris=_task_required_read_uris(
                suite_identity=suite_identity,
                snapshot_identity=snapshot_identity,
                snapshot=snapshot,
                task_index=args.task_index,
                candidate_rows_raw=args.candidate_rows.read_bytes(),
                player_catalog_raw=args.player_catalog.read_bytes(),
            ),
            bucket_metadata=_mapping(
                _load_json_file(
                    args.bucket_metadata, label="dedicated bucket metadata"
                ),
                label="dedicated bucket metadata",
            ),
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0

    if args.command == "create-preflight":
        result = build_transport_preflight(
            suite_raw=suite_raw,
            suite_identity=suite_identity,
            snapshot_raw=args.snapshot.read_bytes(),
            snapshot_identity=_identity_from_args(args, "snapshot"),
            task_index=args.task_index,
            build_metadata=_load_json_file(
                args.build_metadata, label="build metadata"
            ),
            build_id=args.build_id,
            code_sha=args.code_sha,
            image=args.image,
            service_account=args.service_account,
            runtime_iam_evidence_raw=args.runtime_iam_evidence.read_bytes(),
            candidate_rows_raw=args.candidate_rows.read_bytes(),
            player_catalog_raw=args.player_catalog.read_bytes(),
            job_before=_load_json_file(args.job_before, label="job before"),
            job_before_export_raw=args.job_before_export.read_bytes(),
            executions=_load_json_file(
                args.executions, label="execution census"
            ),
            schedulers=_load_json_file(
                args.schedulers, label="scheduler census"
            ),
            output_inventory=_load_json_file(
                args.inventory, label="output inventory"
            ),
            created_at_utc=args.created_at_utc,
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0

    if args.command == "run-local":
        rows = _load_json_file(args.object_map, label="local object map")
        if type(rows) is not list:
            raise CorpusRetrievalTransportError(
                "local object map must be an array"
            )
        result = run_local_task(
            suite_raw=suite_raw,
            suite_identity=suite_identity,
            snapshot_raw=args.snapshot.read_bytes(),
            snapshot_identity=_identity_from_args(args, "snapshot"),
            object_rows=rows,
            task_index=args.task_index,
            output_dir=args.output_dir,
            execution_id=args.execution_id,
            execute=args.execute,
            environ=os.environ,
        )
        _write_once(args.output, canonical_json_bytes(result))
        return 0

    raise CorpusRetrievalTransportError(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
