#!/usr/bin/env python3
"""Governed reuse-only Cloud Run transport for the 54-slate source authority.

This operator-side transport publishes one exact execution plan outside the
nine-object science namespace, binds an already-existing parked Cloud Run job,
consumes one launch authority, recovers and binds the resulting execution, and
accepts the terminal source publication only after an exact semantic reopen.
The worker is ``prepare_corpus_artifact_source_authority.py cloud-worker`` and
never lists GCS.  Prefix inventories in this module are operator-only.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from typing import Final, Protocol


ROOT: Final = Path(__file__).resolve().parents[1]
SCRIPTS: Final = ROOT / "scripts"
SRC: Final = ROOT / "src"
for path in (SCRIPTS, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import prepare_corpus_artifact_source_authority as source  # noqa: E402
from nfl_dfs.research import corpus_expansion_build as expansion_build  # noqa: E402
from nfl_dfs.research import corpus_artifact_source_authority as authority  # noqa: E402
from nfl_dfs.research import lr8_later_period_source as later  # noqa: E402


PROJECT: Final = source.PROJECT
PROJECT_NUMBER: Final = "817589974517"
REGION: Final = "us-central1"
EXPECTED_CODE_REPOSITORY: Final = expansion_build.EXPECTED_CODE_REPOSITORY
ENABLE_ENV: Final = source.ENABLE_ENV
IMAGE_ENV: Final = source.IMAGE_ENV
BUILD_ENV: Final = "CORPUS_ARTIFACT_SOURCE_BUILD_ID"
CODE_ENV: Final = source.CODE_ENV
PARKED_COMMAND: Final = ["python"]
PARKED_ARGS: Final = [
    "scripts/prepare_corpus_artifact_source_authority.py",
    "parked",
]
EXPECTED_TASK_COUNT: Final = 1
EXPECTED_PARALLELISM: Final = 1
EXPECTED_MAX_RETRIES: Final = 0
# Cloud Run's retained v1 JSON uses protobuf seconds without the CLI suffix.
EXPECTED_TIMEOUT_SECONDS: Final = "86400"
EXPECTED_RESOURCES: Final = {"cpu": "8", "memory": "32Gi"}

TRANSPORT_CONTRACT_SCHEMA: Final = "corpus-artifact-source-transport-contract/v1"
RUNTIME_IAM_CAPTURE_SCHEMA: Final = (
    "corpus-artifact-source-runtime-iam-policy-capture/v1"
)
RUNTIME_IAM_SCHEMA: Final = "corpus-artifact-source-runtime-iam-evidence/v3"
PUBLIC_PRINCIPAL_SEARCH_SCHEMA: Final = (
    "corpus-artifact-source-public-principal-search-evidence/v1"
)
PUBLIC_PRINCIPAL_SEARCH_PAGE_SIZE: Final = 500
LAUNCH_LEDGER_SCHEMA: Final = "corpus-artifact-source-launch-ledger/v1"
EXECUTION_BINDING_SCHEMA: Final = "corpus-artifact-source-execution-binding/v1"
TERMINAL_ACCEPTANCE_SCHEMA: Final = "corpus-artifact-source-terminal-acceptance/v1"

QUERY_TABLES: Final = tuple(sorted({later.CANDIDATE_TABLE, later.CATALOG_TABLE}))
STORAGE_GET_PERMISSION: Final = "storage.objects.get"
STORAGE_CREATE_PERMISSION: Final = "storage.objects.create"
BIGQUERY_JOB_PERMISSION: Final = "bigquery.jobs.create"
BIGQUERY_DATA_PERMISSION: Final = "bigquery.tables.getData"
# The frozen matrices live in the project's pre-UBLA raw bucket.  IAM
# Conditions cannot be attached there without a potentially breaking
# bucket-wide migration.  Permit only the custom GET-only role on this named
# legacy bucket; the worker still has no LIST permission and its traced reads
# are restricted to the retained generation/hash identities.
LEGACY_GET_ONLY_BUCKETS: Final = frozenset({
    "nfl-predictions-503414-raw",
})
RUNTIME_READ_CONDITION_TITLE: Final = "corpus-artifact-source-read-v1"
RUNTIME_CREATE_CONDITION_TITLE: Final = "corpus-artifact-source-create-v1"

_CLOUD_ASSET_OPTIONS: Final = {
    "expandGroups": True,
    "expandResources": True,
    "expandRoles": True,
    "outputGroupEdges": True,
    "outputResourceEdges": True,
}

_SHA: Final = re.compile(r"[0-9a-f]{64}")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_GENERATION: Final = re.compile(r"[1-9][0-9]*")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_BUILD: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,159}")
_JOB: Final = re.compile(r"[a-z][a-z0-9-]{0,62}")
_EXECUTION: Final = re.compile(r"[a-z][a-z0-9-]{0,62}")
_SERVICE_ACCOUNT: Final = re.compile(
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,61}"
    r"[a-z0-9]\.iam\.gserviceaccount\.com"
)
_CUSTOM_ROLE: Final = re.compile(
    rf"projects/{re.escape(PROJECT)}/roles/[A-Za-z0-9_.]{{3,64}}"
)


class CorpusArtifactSourceTransportError(RuntimeError):
    """The governed source-authority transport failed closed."""


class ObjectStore(Protocol):
    def read(self, identity: Mapping[str, object]) -> bytes: ...

    def publish(self, uri: str, raw: bytes) -> Mapping[str, object]: ...

    def resolve_current(self, uri: str) -> tuple[Mapping[str, object], bytes]: ...

    def resolve_generation(
        self, uri: str, generation: str
    ) -> tuple[Mapping[str, object], bytes]: ...

    def inventory(self, prefix: str) -> list[dict[str, object]]: ...


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
        raise CorpusArtifactSourceTransportError(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def strict_json_bytes(raw: bytes, *, label: str) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CorpusArtifactSourceTransportError(
                    f"{label} repeats key {key!r}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise CorpusArtifactSourceTransportError(
            f"{label} contains non-finite value {value}"
        )

    if type(raw) is not bytes:
        raise CorpusArtifactSourceTransportError(f"{label} must be bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except CorpusArtifactSourceTransportError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusArtifactSourceTransportError(
            f"{label} is not UTF-8 JSON"
        ) from exc
    if canonical_json_bytes(value) != raw:
        raise CorpusArtifactSourceTransportError(
            f"{label} is not canonical JSON"
        )
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusArtifactSourceTransportError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if type(value) is not list:
        raise CorpusArtifactSourceTransportError(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise CorpusArtifactSourceTransportError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusArtifactSourceTransportError(
            f"{label} must be a nonempty canonical string"
        )
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CorpusArtifactSourceTransportError(
            f"{label} must be an integer >= {minimum}"
        )
    return value


def _generation(value: object, *, label: str) -> str:
    """Normalize one positive JSON integer generation for durable receipts."""
    return str(_integer(value, label=label, minimum=1))


def _sha(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if _SHA.fullmatch(retained) is None:
        raise CorpusArtifactSourceTransportError(f"{label} must be SHA-256")
    return retained


def _timestamp(value: object, *, label: str) -> str:
    try:
        return source._timestamp(value, label=label)[0]  # noqa: SLF001
    except source.CorpusArtifactSourcePreparationError as exc:
        raise CorpusArtifactSourceTransportError(str(exc)) from exc


def _self_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        raise CorpusArtifactSourceTransportError(f"{field} already exists")
    result = dict(value)
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> None:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if retained != canonical_sha256(body):
        raise CorpusArtifactSourceTransportError(f"{label} self-hash differs")


def object_identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity(value, label=label)
    except source.CorpusArtifactSourcePreparationError as exc:
        raise CorpusArtifactSourceTransportError(str(exc)) from exc


def identity_for_bytes(*, uri: str, generation: str, raw: bytes) -> dict[str, object]:
    return object_identity(
        {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        label="object identity",
    )


def _gcs_prefix(value: object, *, label: str) -> str:
    try:
        return source._gcs_prefix(value, label=label)  # noqa: SLF001
    except source.CorpusArtifactSourcePreparationError as exc:
        raise CorpusArtifactSourceTransportError(str(exc)) from exc


def require_execute_gate(*, execute: bool, environ: Mapping[str, str]) -> None:
    if execute is not True:
        raise CorpusArtifactSourceTransportError("literal --execute is required")
    if environ.get(ENABLE_ENV) != "1":
        raise CorpusArtifactSourceTransportError(f"{ENABLE_ENV}=1 is required")


def _identity_rows(values: Sequence[object]) -> list[dict[str, object]]:
    rows = []
    for ordinal, value in enumerate(values):
        identity = object_identity(value, label=f"inventory identity[{ordinal}]")
        rows.append({
            "uri": identity["uri"],
            "generation": identity["generation"],
            "bytes": identity["bytes"],
        })
    return sorted(rows, key=lambda row: (str(row["uri"]), str(row["generation"])))


def _normalized_inventory(value: object, *, label: str) -> list[dict[str, object]]:
    rows = []
    for ordinal, raw in enumerate(_sequence(value, label=label)):
        row = _mapping(raw, label=f"{label}[{ordinal}]")
        _exact_keys(
            row, frozenset({"uri", "generation", "bytes"}),
            label=f"{label}[{ordinal}]",
        )
        identity = object_identity(
            {
                "uri": row["uri"],
                "generation": row["generation"],
                "sha256": "0" * 64,
                "bytes": row["bytes"],
            },
            label=f"{label}[{ordinal}]",
        )
        rows.append({
            "uri": identity["uri"],
            "generation": identity["generation"],
            "bytes": identity["bytes"],
        })
    ordered = sorted(rows, key=lambda row: (str(row["uri"]), str(row["generation"])))
    if rows != ordered or len({(row["uri"], row["generation"]) for row in rows}) != len(rows):
        raise CorpusArtifactSourceTransportError(f"{label} order/uniqueness differs")
    return rows


def _require_exact_inventory(
    storage: ObjectStore,
    *,
    prefix: str,
    identities: Sequence[object],
    label: str,
) -> None:
    observed = _normalized_inventory(storage.inventory(prefix), label=label)
    if observed != _identity_rows(identities):
        raise CorpusArtifactSourceTransportError(f"{label} differs")


def _governance_uris(delivery_prefix: str) -> dict[str, str]:
    return {
        "plan": f"{delivery_prefix}input/publication-plan.json",
        "runtime_iam": f"{delivery_prefix}governance/runtime-iam.json",
        "contract": f"{delivery_prefix}governance/transport-contract.json",
        "launch_ledger": f"{delivery_prefix}governance/launch-ledger.json",
        "execution_binding": f"{delivery_prefix}governance/execution-binding.json",
        "terminal_acceptance": f"{delivery_prefix}governance/terminal-acceptance.json",
    }


def cloud_worker_base_args(plan_identity: object) -> list[str]:
    plan = object_identity(plan_identity, label="worker plan identity")
    return [
        "scripts/prepare_corpus_artifact_source_authority.py",
        "cloud-worker",
        "--plan-uri", str(plan["uri"]),
        "--plan-generation", str(plan["generation"]),
        "--plan-sha256", str(plan["sha256"]),
        "--plan-bytes", str(plan["bytes"]),
    ]


def cloud_worker_args(plan_identity: object, intent_identity: object) -> list[str]:
    intent = object_identity(intent_identity, label="worker intent identity")
    return [
        *cloud_worker_base_args(plan_identity),
        "--intent-uri", str(intent["uri"]),
        "--intent-generation", str(intent["generation"]),
        "--intent-sha256", str(intent["sha256"]),
        "--intent-bytes", str(intent["bytes"]),
        "--execute",
    ]


class GenerationPinnedStorage:
    """Operator GCS boundary; inventory is never reachable by the worker."""

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
        identity = object_identity(
            {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
            label="GCS URI",
        )
        return tuple(str(identity["uri"]).removeprefix("gs://").split("/", 1))  # type: ignore[return-value]

    def read(self, value: Mapping[str, object]) -> bytes:
        identity = object_identity(value, label="GCS read identity")
        bucket, name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket).blob(name, generation=generation)
        raw = blob.download_as_bytes(if_generation_match=generation)
        if (
            len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            raise CorpusArtifactSourceTransportError("GCS read identity differs")
        return raw

    def publish(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw:
            raise CorpusArtifactSourceTransportError("publication body differs")
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        blob.upload_from_string(
            raw, content_type="application/json", if_generation_match=0
        )
        identity = identity_for_bytes(
            uri=uri, generation=_string(blob.generation, label="generation"), raw=raw
        )
        if self.read(identity) != raw:
            raise CorpusArtifactSourceTransportError("publication reopen differs")
        return identity

    def resolve_current(self, uri: str) -> tuple[Mapping[str, object], bytes]:
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        blob.reload()
        generation = _string(blob.generation, label="current generation")
        return self.resolve_generation(uri, generation)

    def resolve_generation(
        self, uri: str, generation: str
    ) -> tuple[Mapping[str, object], bytes]:
        if _GENERATION.fullmatch(generation) is None:
            raise CorpusArtifactSourceTransportError("generation differs")
        bucket, name = self._parts(uri)
        raw = self._client.bucket(bucket).blob(
            name, generation=int(generation)
        ).download_as_bytes(if_generation_match=int(generation))
        return identity_for_bytes(uri=uri, generation=generation, raw=raw), raw

    def inventory(self, prefix: str) -> list[dict[str, object]]:
        retained = _gcs_prefix(prefix, label="inventory prefix")
        bucket, name = retained.removeprefix("gs://").split("/", 1)
        rows = []
        for blob in self._client.list_blobs(bucket, prefix=name, versions=True):
            generation = _string(blob.generation, label="inventory generation")
            if _GENERATION.fullmatch(generation) is None or blob.size is None:
                raise CorpusArtifactSourceTransportError("inventory row differs")
            rows.append({
                "uri": f"gs://{bucket}/{blob.name}",
                "generation": generation,
                "bytes": int(blob.size),
            })
        return sorted(rows, key=lambda row: (str(row["uri"]), str(row["generation"])))


class _VerifierTraceStore:
    """Restrict and retain every science-verifier generation GET."""

    def __init__(
        self,
        storage: ObjectStore,
        *,
        allowed: Sequence[Mapping[str, object]],
    ) -> None:
        self._storage = storage
        self._allowed: dict[tuple[str, str], dict[str, object] | None] = {}
        self._events: list[dict[str, object]] = []
        self.allow(allowed)

    def allow(self, values: Sequence[Mapping[str, object]]) -> None:
        for ordinal, raw in enumerate(values):
            row = _mapping(raw, label=f"verifier allowed read[{ordinal}]")
            uri = _string(row.get("uri"), label="verifier allowed URI")
            generation = _string(
                row.get("generation"), label="verifier allowed generation"
            )
            if _GENERATION.fullmatch(generation) is None:
                raise CorpusArtifactSourceTransportError(
                    "verifier allowed generation differs"
                )
            complete = (
                object_identity(row, label="verifier allowed identity")
                if set(row) >= {"uri", "generation", "sha256", "bytes"}
                else None
            )
            key = (uri, generation)
            if key in self._allowed and self._allowed[key] != complete:
                raise CorpusArtifactSourceTransportError(
                    "verifier read authority aliases one generation"
                )
            self._allowed[key] = complete

    def _check_and_record(
        self, identity: Mapping[str, object], raw: bytes
    ) -> dict[str, object]:
        normalized = object_identity(identity, label="verifier observed GET")
        key = (str(normalized["uri"]), str(normalized["generation"]))
        if key not in self._allowed:
            raise CorpusArtifactSourceTransportError(
                f"verifier GET is outside exact authority: {normalized['uri']}"
            )
        expected = self._allowed[key]
        if expected is not None and expected != normalized:
            raise CorpusArtifactSourceTransportError(
                "verifier GET identity differs from exact authority"
            )
        if (
            len(raw) != normalized["bytes"]
            or sha256(raw).hexdigest() != normalized["sha256"]
        ):
            raise CorpusArtifactSourceTransportError("verifier GET body differs")
        self._events.append({
            "ordinal": len(self._events),
            "identity": normalized,
        })
        return normalized

    def read(self, identity: Mapping[str, object]) -> bytes:
        normalized = object_identity(identity, label="verifier exact GET")
        key = (str(normalized["uri"]), str(normalized["generation"]))
        if key not in self._allowed:
            raise CorpusArtifactSourceTransportError(
                f"verifier GET is outside exact authority: {normalized['uri']}"
            )
        raw = self._storage.read(normalized)
        self._check_and_record(normalized, raw)
        return raw

    def resolve_generation(
        self, uri: str, generation: str
    ) -> tuple[Mapping[str, object], bytes]:
        if (uri, generation) not in self._allowed:
            raise CorpusArtifactSourceTransportError(
                f"verifier generation GET is outside exact authority: {uri}"
            )
        identity, raw = self._storage.resolve_generation(uri, generation)
        normalized = self._check_and_record(identity, raw)
        return normalized, raw

    def events(self) -> list[dict[str, object]]:
        return list(self._events)


def validate_build_metadata(
    value: object, *, build_id: str, code_sha: str, image: str
) -> dict[str, str]:
    try:
        retained = expansion_build.validate_build_metadata(
            value, build_id=build_id, code_sha=code_sha, image=image
        )
    except expansion_build.CorpusExpansionBuildError as exc:
        raise CorpusArtifactSourceTransportError(str(exc)) from exc
    return {
        key: retained[key]
        for key in (
            "build_id", "code_repository", "code_sha", "image",
            "image_tag", "build_config_sha256",
        )
    }


_PREFIX_CLAUSE: Final = re.compile(
    r"resource\.name\.startsWith\((?:\"([^\"]+)\"|'([^']+)')\)"
)
_EXACT_CLAUSE: Final = re.compile(
    r"resource\.name\s*==\s*(?:\"([^\"]+)\"|'([^']+)')"
)


def _condition_grants(
    expression: object, *, label: str
) -> tuple[frozenset[str], frozenset[str]]:
    text = _string(expression, label=label)
    prefixes: list[str] = []
    exact_objects: list[str] = []
    for ordinal, raw in enumerate(text.split("||")):
        clause = raw.strip()
        prefix_match = _PREFIX_CLAUSE.fullmatch(clause)
        exact_match = _EXACT_CLAUSE.fullmatch(clause)
        if prefix_match is None and exact_match is None:
            raise CorpusArtifactSourceTransportError(
                f"{label} clause[{ordinal}] differs"
            )
        match = prefix_match or exact_match
        assert match is not None
        target = match.group(1) or match.group(2)
        collection = prefixes if prefix_match is not None else exact_objects
        if target in collection:
            raise CorpusArtifactSourceTransportError(
                f"{label} repeats a read grant"
            )
        collection.append(target)
    if not prefixes and not exact_objects:
        raise CorpusArtifactSourceTransportError(f"{label} has no grant")
    return frozenset(prefixes), frozenset(exact_objects)


def _resource_prefix(prefix: str) -> str:
    bucket, name = prefix.removeprefix("gs://").split("/", 1)
    return f"projects/_/buckets/{bucket}/objects/{name}"


def _resource_name(uri: str) -> str:
    retained = object_identity(
        {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
        label="IAM exact object",
    )["uri"]
    bucket, name = str(retained).removeprefix("gs://").split("/", 1)
    return f"projects/_/buckets/{bucket}/objects/{name}"


def derive_minimal_read_authority(
    *, required_read_uris: Sequence[str], output_prefix: str
) -> tuple[list[str], list[str]]:
    """Derive immediate shared parents; singleton reads stay exact objects."""
    required = sorted({
        str(object_identity(
            {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
            label=f"derived read URI[{ordinal}]",
        )["uri"])
        for ordinal, uri in enumerate(required_read_uris)
    })
    if len(required) != len(required_read_uris):
        raise CorpusArtifactSourceTransportError("required read URI repeats")
    by_parent: dict[str, list[str]] = {}
    for uri in required:
        parent = uri.rsplit("/", 1)[0] + "/"
        by_parent.setdefault(parent, []).append(uri)
    prefixes = sorted(
        parent for parent, uris in by_parent.items() if len(uris) > 1
    )
    exact = sorted(
        uri
        for parent, uris in by_parent.items()
        if len(uris) == 1
        for uri in uris
    )
    output = _gcs_prefix(output_prefix, label="derived output prefix")
    exact.extend(sorted(source._publication_uris(output).values()))  # noqa: SLF001
    exact = sorted(exact)
    for uri in required:
        matches = [prefix for prefix in prefixes if uri.startswith(prefix)]
        exact_match = uri in exact
        if len(matches) + int(exact_match) != 1:
            raise CorpusArtifactSourceTransportError(
                "derived read URI authority is ambiguous"
            )
    if any(any(uri.startswith(prefix) for prefix in prefixes) for uri in exact):
        raise CorpusArtifactSourceTransportError(
            "derived prefix aliases an exact-object read"
        )
    return prefixes, exact


def _validate_custom_roles(value: object) -> dict[str, str]:
    expected_permissions = {
        STORAGE_GET_PERMISSION,
        STORAGE_CREATE_PERMISSION,
        BIGQUERY_JOB_PERMISSION,
        BIGQUERY_DATA_PERMISSION,
    }
    rows = _sequence(value, label="runtime custom role definitions")
    permission_to_role: dict[str, str] = {}
    normalized: list[dict[str, object]] = []
    for ordinal, raw in enumerate(rows):
        role = dict(_mapping(raw, label=f"runtime custom role[{ordinal}]"))
        name = _string(role.get("name"), label="runtime custom role name")
        permissions = role.get("includedPermissions")
        if (
            _CUSTOM_ROLE.fullmatch(name) is None
            or type(role.get("etag")) is not str
            or not role.get("etag")
            or role.get("stage") != "GA"
            or role.get("deleted", False) is not False
            or type(permissions) is not list
            or len(permissions) != 1
            or permissions[0] not in expected_permissions
            or permissions[0] in permission_to_role
        ):
            raise CorpusArtifactSourceTransportError(
                "runtime custom role is absent, repeated, disabled, or overbroad"
            )
        permission_to_role[str(permissions[0])] = name
        normalized.append(role)
    if (
        set(permission_to_role) != expected_permissions
        or normalized != sorted(normalized, key=lambda row: str(row["name"]))
    ):
        raise CorpusArtifactSourceTransportError(
            "runtime custom role permission census differs"
        )
    return permission_to_role


def _policy_bindings(value: object, *, label: str) -> Sequence[object]:
    policy = _mapping(value, label=label)
    if (
        type(policy.get("etag")) is not str
        or not policy.get("etag")
        or type(policy.get("version")) is not int
    ):
        raise CorpusArtifactSourceTransportError(
            f"{label} lacks retained etag/version"
        )
    bindings = policy.get("bindings", [])
    return _sequence(bindings, label=f"{label}.bindings")


def _reject_public_members(bindings: Sequence[object], *, label: str) -> None:
    for ordinal, raw in enumerate(bindings):
        row = _mapping(raw, label=f"{label}[{ordinal}]")
        members = _sequence(row.get("members", []), label=f"{label}.members")
        if any(member in {"allUsers", "allAuthenticatedUsers"} for member in members):
            raise CorpusArtifactSourceTransportError(
                f"{label} contains a public principal"
            )


_RUNTIME_IAM_CAPTURE_KEYS: Final = frozenset({
    "schema_version", "captured_at_utc", "project", "project_policy",
    "query_table_policies", "custom_role_definitions", "bucket_policies",
    "bucket_metadata", "effective_access_analyses", "capture_sha256",
})
_RUNTIME_IAM_KEYS: Final = frozenset({
    "schema_version", "captured_at_utc", "project", "service_account",
    "required_read_uris_sha256", "read_prefixes", "read_exact_uris",
    "read_authority_sha256", "output_prefix",
    "query_tables", "project_policy", "query_table_policies",
    "custom_role_definitions", "bucket_policies", "bucket_metadata",
    "effective_access_analyses",
    "iam_evidence_sha256",
})


def build_runtime_iam_evidence(
    *,
    policy_capture: object,
    plan_raw: bytes,
    base_source_lock_raw: bytes,
    delivery_prefix: str,
    service_account: str,
) -> dict[str, object]:
    """Derive the exact v3 IAM evidence from retained policy bodies.

    This is client-free.  It recomputes the 270-artifact read lattice from the
    frozen source lock and derives the plan/launch/output object authorities;
    callers cannot supply an ad-hoc read prefix list.
    """
    capture = dict(_mapping(policy_capture, label="runtime IAM policy capture"))
    _exact_keys(
        capture, _RUNTIME_IAM_CAPTURE_KEYS,
        label="runtime IAM policy capture",
    )
    _validate_self_hash(
        capture, field="capture_sha256", label="runtime IAM policy capture"
    )
    if (
        capture["schema_version"] != RUNTIME_IAM_CAPTURE_SCHEMA
        or capture["project"] != PROJECT
    ):
        raise CorpusArtifactSourceTransportError(
            "runtime IAM policy capture identity differs"
        )
    _timestamp(capture["captured_at_utc"], label="runtime IAM capture timestamp")
    plan = _parse_plan(plan_raw)
    delivery = _gcs_prefix(delivery_prefix, label="source delivery prefix")
    output = _gcs_prefix(plan["output_prefix"], label="source output prefix")
    if (
        not delivery.endswith(f"/{plan['run_id']}/")
        or delivery.startswith(output)
        or output.startswith(delivery)
    ):
        raise CorpusArtifactSourceTransportError(
            "delivery and source prefixes overlap or differ"
        )
    base_identity = object_identity(
        plan["base_source_lock_object"], label="plan base source lock"
    )
    try:
        _base, receipts = source.validate_base_source_lock_bytes(
            base_source_lock_raw, identity=base_identity
        )
    except source.CorpusArtifactSourcePreparationError as exc:
        raise CorpusArtifactSourceTransportError(
            "base source-lock replay differs"
        ) from exc
    manifest_sha = canonical_sha256([
        {
            "season": row["season"],
            "week": row["week"],
            "block": row["block"],
            "uri": row["uri"],
            "generation": row["generation"],
            "sha256": row["sha256"],
            "bytes": row["bytes"],
        }
        for row in receipts
    ])
    if manifest_sha != plan["base_source_lock_artifact_manifest_sha256"]:
        raise CorpusArtifactSourceTransportError(
            "base source-lock artifact manifest differs"
        )
    uris = _governance_uris(delivery)
    plan_identity = {
        "uri": uris["plan"],
        "generation": "1",
        "sha256": sha256(plan_raw).hexdigest(),
        "bytes": len(plan_raw),
    }
    required_read_uris = _required_read_uris(
        plan_identity=plan_identity, plan=plan, receipts=receipts
    ) + [uris["launch_ledger"]]
    read_prefixes, read_exact_uris = derive_minimal_read_authority(
        required_read_uris=required_read_uris,
        output_prefix=output,
    )
    body = {
        "schema_version": RUNTIME_IAM_SCHEMA,
        "captured_at_utc": capture["captured_at_utc"],
        "project": PROJECT,
        "service_account": service_account,
        "required_read_uris_sha256": canonical_sha256(
            sorted(required_read_uris)
        ),
        "read_prefixes": read_prefixes,
        "read_exact_uris": read_exact_uris,
        "read_authority_sha256": canonical_sha256({
            "read_prefixes": read_prefixes,
            "read_exact_uris": read_exact_uris,
        }),
        "output_prefix": output,
        "query_tables": list(QUERY_TABLES),
        "project_policy": capture["project_policy"],
        "query_table_policies": capture["query_table_policies"],
        "custom_role_definitions": capture["custom_role_definitions"],
        "bucket_policies": capture["bucket_policies"],
        "bucket_metadata": capture["bucket_metadata"],
        "effective_access_analyses": capture["effective_access_analyses"],
    }
    result = _self_hash(body, field="iam_evidence_sha256")
    return validate_runtime_iam_evidence(
        result,
        service_account=service_account,
        required_read_uris=required_read_uris,
        output_prefix=output,
    )


def _cloud_asset_results(value: object, *, identity: str) -> list[object]:
    response = _mapping(value, label=f"Cloud Asset analysis for {identity}")
    main = _mapping(
        response.get("mainAnalysis"), label=f"Cloud Asset main analysis for {identity}"
    )
    base_query = {
        "identitySelector": {"identity": identity},
        "scope": f"projects/{PROJECT}",
    }
    query = main.get("analysisQuery")
    accepted_queries = [{**base_query, "options": _CLOUD_ASSET_OPTIONS}]
    # Cloud Asset can exhaust the expanded graph for the two special public
    # principals even when their fully explored result is empty.  A minimal
    # fully explored special-principal query is equally conclusive here:
    # special principals cannot be group members, and with zero bindings
    # there is no role, resource, group, or edge to expand.  Runtime identity
    # evidence remains expansion-mandatory.
    if identity in {"allUsers", "allAuthenticatedUsers"}:
        accepted_queries.append(base_query)
    if (
        response.get("fullyExplored") is not True
        or main.get("fullyExplored") is not True
        or query not in accepted_queries
        or response.get("nonCriticalErrors", []) != []
        or main.get("nonCriticalErrors", []) != []
    ):
        raise CorpusArtifactSourceTransportError(
            f"Cloud Asset analysis for {identity} is incomplete or differs"
        )
    return list(
        _sequence(
            main.get("analysisResults", []),
            label=f"Cloud Asset results for {identity}",
        )
    )


_PUBLIC_PRINCIPAL_SEARCH_KEYS: Final = frozenset({
    "schema_version",
    "search_all_iam_policies_request",
    "search_all_iam_policies_response",
    "resource_manager_project",
})
_PUBLIC_PRINCIPAL_SEARCH_REQUEST_KEYS: Final = frozenset({
    "scope", "query", "pageSize",
})
_RESOURCE_MANAGER_PROJECT_KEYS: Final = frozenset({
    "name", "projectId", "state", "displayName", "createTime",
    "updateTime", "etag",
})


def _public_principal_results(value: object, *, identity: str) -> list[object]:
    """Replay either conclusive AnalyzeIamPolicy or its bounded fallback.

    SearchAllIamPolicies is only conclusive for a project when the retained
    response is a complete empty page and the project has no parent.  The
    latter closes the ancestor-policy gap inherent in a project-scoped
    search.  This bundle intentionally has no inner self-hash: the enclosing
    policy-capture/evidence self-hash remains the sole byte authority.
    """
    if identity not in {"allUsers", "allAuthenticatedUsers"}:
        raise CorpusArtifactSourceTransportError(
            "public-principal fallback identity differs"
        )
    if not (
        isinstance(value, Mapping)
        and value.get("schema_version") == PUBLIC_PRINCIPAL_SEARCH_SCHEMA
    ):
        return _cloud_asset_results(value, identity=identity)

    proof = _mapping(
        value, label=f"public-principal search proof for {identity}"
    )
    _exact_keys(
        proof,
        _PUBLIC_PRINCIPAL_SEARCH_KEYS,
        label=f"public-principal search proof for {identity}",
    )
    request = _mapping(
        proof["search_all_iam_policies_request"],
        label=f"SearchAllIamPolicies request for {identity}",
    )
    _exact_keys(
        request,
        _PUBLIC_PRINCIPAL_SEARCH_REQUEST_KEYS,
        label=f"SearchAllIamPolicies request for {identity}",
    )
    if request != {
        "scope": f"projects/{PROJECT}",
        "query": f"policy:{identity}",
        "pageSize": PUBLIC_PRINCIPAL_SEARCH_PAGE_SIZE,
    }:
        raise CorpusArtifactSourceTransportError(
            f"SearchAllIamPolicies request for {identity} differs"
        )

    response = _mapping(
        proof["search_all_iam_policies_response"],
        label=f"SearchAllIamPolicies response for {identity}",
    )
    # The retained direct REST searches returned exact empty objects.  Do not
    # widen that observed wire result to a synthesized ``results: []`` or to
    # any response carrying pagination, unreachable scopes, or API errors.
    if response != {}:
        raise CorpusArtifactSourceTransportError(
            f"SearchAllIamPolicies response for {identity} is not a complete "
            "zero-result page"
        )

    project = _mapping(
        proof["resource_manager_project"],
        label="Resource Manager project",
    )
    # The raw v3 Project resource omits parent for a parentless project.  Do
    # not treat an empty/null parent as equivalent: retaining the field means
    # the proof is not the exact observed parentless body.
    if "parent" in project:
        raise CorpusArtifactSourceTransportError(
            "Resource Manager project must be parentless"
        )
    _exact_keys(
        project,
        _RESOURCE_MANAGER_PROJECT_KEYS,
        label="Resource Manager project",
    )
    if (
        project["name"] != f"projects/{PROJECT_NUMBER}"
        or project["projectId"] != PROJECT
        or project["state"] != "ACTIVE"
    ):
        raise CorpusArtifactSourceTransportError(
            "Resource Manager project identity/state differs"
        )
    _string(project["displayName"], label="Resource Manager project displayName")
    _string(project["etag"], label="Resource Manager project etag")
    _timestamp(
        project["createTime"], label="Resource Manager project createTime"
    )
    _timestamp(
        project["updateTime"], label="Resource Manager project updateTime"
    )
    return []


def _cloud_asset_grant(
    value: object, *, member: str
) -> tuple[
    str, str, str | None, frozenset[str], frozenset[str], frozenset[str]
]:
    result = _mapping(value, label="Cloud Asset runtime result")
    binding = _mapping(result.get("iamBinding"), label="Cloud Asset IAM binding")
    members = list(
        _sequence(binding.get("members"), label="Cloud Asset binding members")
    )
    identities = _mapping(
        result.get("identityList"), label="Cloud Asset identity list"
    )
    identity_rows = _sequence(
        identities.get("identities"), label="Cloud Asset identities"
    )
    if identities.get("groupEdges", []) != []:
        raise CorpusArtifactSourceTransportError(
            "Cloud Asset runtime grant is inherited through a group"
        )
    names = [
        _string(
            _mapping(row, label="Cloud Asset identity").get("name"),
            label="Cloud Asset identity name",
        )
        for row in identity_rows
    ]
    role = _string(binding.get("role"), label="Cloud Asset role")
    attached = _string(
        result.get("attachedResourceFullName"),
        label="Cloud Asset attached resource",
    )
    condition = binding.get("condition")
    title: str | None = None
    prefixes: frozenset[str] = frozenset()
    exact_objects: frozenset[str] = frozenset()
    if condition is not None:
        retained_condition = _mapping(
            condition, label="Cloud Asset binding condition"
        )
        title = _string(
            retained_condition.get("title"), label="Cloud Asset condition title"
        )
        prefixes, exact_objects = _condition_grants(
            retained_condition.get("expression"),
            label="Cloud Asset condition expression",
        )
    access_lists = _sequence(
        result.get("accessControlLists"), label="Cloud Asset access lists"
    )
    observed_role = False
    permissions: set[str] = set()
    for raw_acl in access_lists:
        acl = _mapping(raw_acl, label="Cloud Asset access list")
        accesses = _sequence(acl.get("accesses"), label="Cloud Asset accesses")
        resources = _sequence(
            acl.get("resources"), label="Cloud Asset access resources"
        )
        resource_names = {
            _string(
                _mapping(resource, label="Cloud Asset resource").get(
                    "fullResourceName"
                ),
                label="Cloud Asset resource name",
            )
            for resource in resources
        }
        if not resource_names or resource_names != {attached}:
            raise CorpusArtifactSourceTransportError(
                "Cloud Asset effective resource differs"
            )
        for raw_access in accesses:
            access = _mapping(raw_access, label="Cloud Asset access")
            if set(access) == {"role"} and access["role"] == role:
                observed_role = True
            elif set(access) == {"permission"}:
                permissions.add(_string(
                    access["permission"], label="Cloud Asset expanded permission"
                ))
            else:
                raise CorpusArtifactSourceTransportError(
                    "Cloud Asset expanded capability differs"
                )
        evaluation = acl.get("conditionEvaluation")
        if condition is not None:
            if (
                not isinstance(evaluation, Mapping)
                or evaluation.get("evaluationValue") != "CONDITIONAL"
            ):
                raise CorpusArtifactSourceTransportError(
                    "Cloud Asset conditional grant evaluation differs"
                )
        elif evaluation not in (None, {}):
            raise CorpusArtifactSourceTransportError(
                "Cloud Asset unconditional grant evaluation differs"
            )
    if (
        result.get("fullyExplored") is not True
        or result.get("nonCriticalErrors", []) != []
        or members != [member]
        or names != [member]
        or not observed_role
        or not permissions
    ):
        raise CorpusArtifactSourceTransportError(
            "Cloud Asset runtime identity expansion differs"
        )
    return (
        role, attached, title, prefixes, exact_objects,
        frozenset(permissions),
    )


def _validate_effective_access(
    value: object,
    *,
    service_account: str,
    read_prefixes: Sequence[str],
    read_exact_uris: Sequence[str],
    output_prefix: str,
    custom_roles: Mapping[str, str],
) -> None:
    analyses = _mapping(value, label="effective-access analyses")
    _exact_keys(
        analyses,
        frozenset({"runtime_identity", "all_users", "all_authenticated_users"}),
        label="effective-access analyses",
    )
    member = f"serviceAccount:{service_account}"
    runtime_results = _cloud_asset_results(
        analyses["runtime_identity"], identity=member
    )
    observed = [
        _cloud_asset_grant(row, member=member) for row in runtime_results
    ]
    if len(observed) != len(set(observed)):
        raise CorpusArtifactSourceTransportError(
            "Cloud Asset effective grant repeats"
        )
    expected: set[tuple[
        str, str, str | None, frozenset[str], frozenset[str], frozenset[str]
    ]] = {
        (
            custom_roles[BIGQUERY_JOB_PERMISSION],
            f"//cloudresourcemanager.googleapis.com/projects/{PROJECT}",
            None,
            frozenset(),
            frozenset(),
            frozenset({BIGQUERY_JOB_PERMISSION}),
        ),
        *(
            (
            custom_roles[BIGQUERY_DATA_PERMISSION],
                "//bigquery.googleapis.com/projects/"
                + table.replace(".", "/datasets/", 1).replace(".", "/tables/", 1),
            None,
            frozenset(),
            frozenset(),
            frozenset({BIGQUERY_DATA_PERMISSION}),
            )
            for table in QUERY_TABLES
        ),
    }
    buckets = sorted({
        prefix.removeprefix("gs://").split("/", 1)[0]
        for prefix in read_prefixes
    } | {
        uri.removeprefix("gs://").split("/", 1)[0]
        for uri in read_exact_uris
    })
    output_bucket = output_prefix.removeprefix("gs://").split("/", 1)[0]
    for bucket in buckets:
        expected.add((
            custom_roles[STORAGE_GET_PERMISSION],
            f"//storage.googleapis.com/{bucket}",
            RUNTIME_READ_CONDITION_TITLE,
            frozenset(
                _resource_prefix(prefix)
                for prefix in read_prefixes
                if prefix.startswith(f"gs://{bucket}/")
            ),
            frozenset(
                _resource_name(uri)
                for uri in read_exact_uris
                if uri.startswith(f"gs://{bucket}/")
            ),
            frozenset({STORAGE_GET_PERMISSION}),
        ))
        if bucket == output_bucket:
            expected.add((
                custom_roles[STORAGE_CREATE_PERMISSION],
                f"//storage.googleapis.com/{bucket}",
                RUNTIME_CREATE_CONDITION_TITLE,
                frozenset({_resource_prefix(output_prefix)}),
                frozenset(),
                frozenset({STORAGE_CREATE_PERMISSION}),
            ))
    observed_set = set(observed)
    accepted_sets = [expected]
    legacy_expected = set(expected)
    for bucket in sorted(LEGACY_GET_ONLY_BUCKETS.intersection(buckets)):
        conditional = next(
            row for row in legacy_expected
            if row[0] == custom_roles[STORAGE_GET_PERMISSION]
            and row[1] == f"//storage.googleapis.com/{bucket}"
        )
        legacy_expected.remove(conditional)
        legacy_expected.add((
            custom_roles[STORAGE_GET_PERMISSION],
            f"//storage.googleapis.com/{bucket}",
            None,
            frozenset(),
            frozenset(),
            frozenset({STORAGE_GET_PERMISSION}),
        ))
    if legacy_expected != expected:
        accepted_sets.append(legacy_expected)
    if all(observed_set != candidate for candidate in accepted_sets):
        raise CorpusArtifactSourceTransportError(
            "Cloud Asset runtime effective capabilities are incomplete or overbroad"
        )
    for key, identity in (
        ("all_users", "allUsers"),
        ("all_authenticated_users", "allAuthenticatedUsers"),
    ):
        if _public_principal_results(analyses[key], identity=identity):
            raise CorpusArtifactSourceTransportError(
                f"Cloud Asset public access exists for {identity}"
            )


def validate_runtime_iam_evidence(
    value: object,
    *,
    service_account: str,
    required_read_uris: Sequence[str],
    output_prefix: str,
) -> dict[str, object]:
    """Replay retained raw IAM policies; no self-attested capability flags."""
    item = dict(_mapping(value, label="runtime IAM evidence"))
    _exact_keys(item, _RUNTIME_IAM_KEYS, label="runtime IAM evidence")
    _validate_self_hash(
        item, field="iam_evidence_sha256", label="runtime IAM evidence"
    )
    retained_output = _gcs_prefix(output_prefix, label="source output prefix")
    required = sorted(
        object_identity(
            {"uri": uri, "generation": "1", "sha256": "0" * 64, "bytes": 1},
            label=f"required read URI[{ordinal}]",
        )["uri"]
        for ordinal, uri in enumerate(required_read_uris)
    )
    if (
        item["schema_version"] != RUNTIME_IAM_SCHEMA
        or item["project"] != PROJECT
        or item["service_account"] != service_account
        or _SERVICE_ACCOUNT.fullmatch(service_account) is None
        or item["required_read_uris_sha256"] != canonical_sha256(required)
        or item["output_prefix"] != retained_output
        or item["query_tables"] != list(QUERY_TABLES)
    ):
        raise CorpusArtifactSourceTransportError(
            "runtime IAM principal/input/query binding differs"
        )
    _timestamp(item["captured_at_utc"], label="runtime IAM timestamp")
    read_prefixes = [
        _gcs_prefix(row, label=f"runtime read prefix[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(item["read_prefixes"], label="runtime read prefixes")
        )
    ]
    read_exact_uris = [
        str(object_identity(
            {"uri": row, "generation": "1", "sha256": "0" * 64, "bytes": 1},
            label=f"runtime exact read[{ordinal}]",
        )["uri"])
        for ordinal, row in enumerate(
            _sequence(item["read_exact_uris"], label="runtime exact reads")
        )
    ]
    expected_prefixes, expected_exact = derive_minimal_read_authority(
        required_read_uris=[str(uri) for uri in required],
        output_prefix=retained_output,
    )
    expected_authority_sha = canonical_sha256({
        "read_prefixes": expected_prefixes,
        "read_exact_uris": expected_exact,
    })
    if (
        read_prefixes != expected_prefixes
        or read_exact_uris != expected_exact
        or item["read_authority_sha256"] != expected_authority_sha
    ):
        raise CorpusArtifactSourceTransportError(
            "runtime IAM read authority is not the deterministic minimum"
        )
    custom_roles = _validate_custom_roles(item["custom_role_definitions"])

    member = f"serviceAccount:{service_account}"
    project_bindings = _policy_bindings(
        item["project_policy"], label="runtime project policy"
    )
    _reject_public_members(project_bindings, label="runtime project bindings")
    project_roles: list[str] = []
    for raw in project_bindings:
        binding = _mapping(raw, label="runtime project binding")
        members = _sequence(
            binding.get("members", []), label="runtime project binding members"
        )
        if member in members:
            if list(members) != [member] or "condition" in binding:
                raise CorpusArtifactSourceTransportError(
                    "runtime BigQuery job role condition differs"
                )
            project_roles.append(
                _string(binding.get("role"), label="runtime project role")
            )
    if project_roles != [custom_roles[BIGQUERY_JOB_PERMISSION]]:
        raise CorpusArtifactSourceTransportError(
            "runtime project role is absent, repeated, or overbroad"
        )

    table_rows = _sequence(
        item["query_table_policies"], label="query table policies"
    )
    observed_tables: set[str] = set()
    for ordinal, raw in enumerate(table_rows):
        row = _mapping(raw, label=f"query table policy[{ordinal}]")
        _exact_keys(
            row, frozenset({"table", "policy"}),
            label=f"query table policy[{ordinal}]",
        )
        table = _string(row["table"], label="query table")
        if table in observed_tables:
            raise CorpusArtifactSourceTransportError("query table policy repeats")
        observed_tables.add(table)
        bindings = _policy_bindings(row["policy"], label=f"table {table} policy")
        _reject_public_members(bindings, label=f"table {table} bindings")
        roles = []
        for raw_binding in bindings:
            binding = _mapping(raw_binding, label=f"table {table} binding")
            members = _sequence(
                binding.get("members", []), label=f"table {table} members"
            )
            if member in members:
                if list(members) != [member] or "condition" in binding:
                    raise CorpusArtifactSourceTransportError(
                        "query table role condition differs"
                    )
                roles.append(_string(binding.get("role"), label="query table role"))
        if roles != [custom_roles[BIGQUERY_DATA_PERMISSION]]:
            raise CorpusArtifactSourceTransportError(
                f"query table {table} permission is absent/repeated/overbroad"
            )
    if observed_tables != set(QUERY_TABLES):
        raise CorpusArtifactSourceTransportError(
            "query table policy census is incomplete"
        )

    relevant_buckets = {
        prefix.removeprefix("gs://").split("/", 1)[0]
        for prefix in read_prefixes
    } | {
        uri.removeprefix("gs://").split("/", 1)[0]
        for uri in read_exact_uris
    }
    output_bucket = retained_output.removeprefix("gs://").split("/", 1)[0]
    metadata_rows = _sequence(item["bucket_metadata"], label="bucket metadata")
    observed_metadata: set[str] = set()
    legacy_unconditioned_buckets: set[str] = set()
    for ordinal, raw in enumerate(metadata_rows):
        row = _mapping(raw, label=f"bucket metadata[{ordinal}]")
        _exact_keys(
            row, frozenset({"bucket", "metadata"}),
            label=f"bucket metadata[{ordinal}]",
        )
        bucket = _string(row["bucket"], label="metadata bucket")
        if bucket in observed_metadata:
            raise CorpusArtifactSourceTransportError("bucket metadata repeats")
        observed_metadata.add(bucket)
        metadata = _mapping(row["metadata"], label=f"bucket {bucket} metadata")
        iam = _mapping(
            metadata.get("iamConfiguration"), label=f"bucket {bucket} IAM config"
        )
        ubla = _mapping(
            iam.get("uniformBucketLevelAccess"), label=f"bucket {bucket} UBLA"
        )
        legacy_get_only = (
            bucket in LEGACY_GET_ONLY_BUCKETS and ubla.get("enabled") is False
        )
        if (
            metadata.get("name") not in {bucket, f"projects/_/buckets/{bucket}"}
            or type(metadata.get("etag")) is not str
            or not metadata.get("etag")
            or not str(metadata.get("metageneration", "")).isdigit()
            or int(str(metadata.get("metageneration", "0"))) < 1
            or (
                legacy_get_only
                and (
                    bucket == output_bucket
                    or ubla.get("enabled") is not False
                    or iam.get("publicAccessPrevention")
                    not in {"inherited", "enforced"}
                )
            )
            or (
                not legacy_get_only
                and (
                    ubla.get("enabled") is not True
                    or iam.get("publicAccessPrevention") != "enforced"
                )
            )
        ):
            raise CorpusArtifactSourceTransportError(
                f"bucket {bucket} UBLA/PAP storage boundary differs"
            )
        if legacy_get_only:
            legacy_unconditioned_buckets.add(bucket)
    if observed_metadata != relevant_buckets:
        raise CorpusArtifactSourceTransportError(
            "bucket metadata census is incomplete or overbroad"
        )

    policy_rows = _sequence(item["bucket_policies"], label="bucket policies")
    observed_policies: set[str] = set()
    for ordinal, raw in enumerate(policy_rows):
        row = _mapping(raw, label=f"bucket policy[{ordinal}]")
        _exact_keys(
            row, frozenset({"bucket", "policy"}),
            label=f"bucket policy[{ordinal}]",
        )
        bucket = _string(row["bucket"], label="policy bucket")
        if bucket in observed_policies:
            raise CorpusArtifactSourceTransportError("bucket policy repeats")
        observed_policies.add(bucket)
        policy = _mapping(row["policy"], label=f"bucket {bucket} policy")
        bindings = _policy_bindings(policy, label=f"bucket {bucket} policy")
        legacy_get_only = bucket in legacy_unconditioned_buckets
        if (
            (legacy_get_only and policy.get("version") not in {1, 3})
            or (not legacy_get_only and policy.get("version") != 3)
        ):
            raise CorpusArtifactSourceTransportError(
                f"bucket {bucket} conditional policy version differs"
            )
        _reject_public_members(bindings, label=f"bucket {bucket} bindings")
        account_roles: dict[
            str, tuple[frozenset[str], frozenset[str]]
        ] = {}
        for raw_binding in bindings:
            binding = _mapping(raw_binding, label=f"bucket {bucket} binding")
            members = _sequence(
                binding.get("members", []), label=f"bucket {bucket} members"
            )
            if member not in members:
                continue
            if list(members) != [member]:
                raise CorpusArtifactSourceTransportError(
                    "runtime bucket binding aliases another member"
                )
            role = _string(binding.get("role"), label="runtime bucket role")
            expected_title = {
                custom_roles[STORAGE_GET_PERMISSION]: RUNTIME_READ_CONDITION_TITLE,
                custom_roles[STORAGE_CREATE_PERMISSION]: RUNTIME_CREATE_CONDITION_TITLE,
            }.get(role)
            if expected_title is None or role in account_roles:
                raise CorpusArtifactSourceTransportError(
                    "runtime bucket role is repeated or overbroad"
                )
            if legacy_get_only:
                if (
                    role != custom_roles[STORAGE_GET_PERMISSION]
                    or "condition" in binding
                ):
                    raise CorpusArtifactSourceTransportError(
                        "legacy raw bucket must use one unconditional GET-only role"
                    )
                account_roles[role] = (frozenset(), frozenset())
            else:
                condition = _mapping(
                    binding.get("condition"), label="runtime bucket condition"
                )
                if (
                    set(condition) - {"title", "description", "expression"}
                    or condition.get("title") != expected_title
                ):
                    raise CorpusArtifactSourceTransportError(
                        "runtime bucket IAM condition differs"
                    )
                account_roles[role] = _condition_grants(
                    condition.get("expression"), label="runtime bucket condition"
                )
        expected_view = (
            (frozenset(), frozenset())
            if legacy_get_only
            else (
                frozenset(
                    _resource_prefix(prefix)
                    for prefix in read_prefixes
                    if prefix.startswith(f"gs://{bucket}/")
                ),
                frozenset(
                    _resource_name(uri)
                    for uri in read_exact_uris
                    if uri.startswith(f"gs://{bucket}/")
                ),
            )
        )
        expected_roles = {custom_roles[STORAGE_GET_PERMISSION]: expected_view}
        if bucket == output_bucket:
            expected_roles[custom_roles[STORAGE_CREATE_PERMISSION]] = (
                frozenset({_resource_prefix(retained_output)}), frozenset()
            )
        if account_roles != expected_roles:
            raise CorpusArtifactSourceTransportError(
                f"bucket {bucket} exact read/create conditions differ"
            )
    if observed_policies != relevant_buckets:
        raise CorpusArtifactSourceTransportError(
            "bucket policy census is incomplete or overbroad"
        )
    _validate_effective_access(
        item["effective_access_analyses"],
        service_account=service_account,
        read_prefixes=read_prefixes,
        read_exact_uris=read_exact_uris,
        output_prefix=retained_output,
        custom_roles=custom_roles,
    )
    return item


def _task_spec(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        task = value["spec"]["template"]["spec"]["template"]["spec"]  # type: ignore[index]
    except (KeyError, TypeError):
        try:
            task = value["spec"]["template"]["spec"]  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise CorpusArtifactSourceTransportError(
                "Cloud Run task spec differs"
            ) from exc
    return _mapping(task, label="Cloud Run task spec")


def _outer_spec(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        return _mapping(
            value["spec"]["template"]["spec"],  # type: ignore[index]
            label="Cloud Run outer spec",
        )
    except (KeyError, TypeError) as exc:
        raise CorpusArtifactSourceTransportError(
            "Cloud Run outer spec differs"
        ) from exc


def _validate_job_template_boundary(value: Mapping[str, object]) -> None:
    spec = _mapping(value.get("spec"), label="parked job spec")
    _exact_keys(spec, frozenset({"template"}), label="parked job spec")
    template = _mapping(spec.get("template"), label="parked job template")
    _exact_keys(
        template,
        frozenset({"metadata", "spec"}),
        label="parked job template",
    )
    metadata = _mapping(
        template.get("metadata"), label="parked job template metadata"
    )
    _exact_keys(
        metadata,
        frozenset({"annotations", "labels"}),
        label="parked job template metadata",
    )
    annotations = _mapping(
        metadata.get("annotations"), label="parked job template annotations"
    )
    expected_annotations = frozenset({
        "run.googleapis.com/client-name",
        "run.googleapis.com/client-version",
        "run.googleapis.com/execution-environment",
    })
    cloudsql_clear = "run.googleapis.com/cloudsql-instances"
    if not (
        frozenset(annotations) == expected_annotations | {cloudsql_clear}
        and annotations.get(cloudsql_clear) == ""
    ):
        _exact_keys(
            annotations,
            expected_annotations,
            label="parked job template annotations",
        )
    labels = _mapping(metadata.get("labels"), label="parked job template labels")
    _exact_keys(
        labels,
        frozenset({"client.knative.dev/nonce"}),
        label="parked job template labels",
    )
    client_version = annotations.get("run.googleapis.com/client-version")
    nonce = labels.get("client.knative.dev/nonce")
    if (
        annotations.get("run.googleapis.com/client-name") != "gcloud"
        or annotations.get("run.googleapis.com/execution-environment") != "gen2"
        or type(client_version) is not str
        or re.fullmatch(r"[0-9]+(?:\.[0-9]+){2}", client_version) is None
        or type(nonce) is not str
        or not nonce
    ):
        raise CorpusArtifactSourceTransportError(
            "parked job template annotations/labels differ"
        )


def _validate_task_attachment_boundary(
    task: Mapping[str, object], container: Mapping[str, object]
) -> None:
    _exact_keys(
        task,
        frozenset({
            "containers", "maxRetries", "serviceAccountName", "timeoutSeconds"
        }),
        label="Cloud Run task attachment boundary",
    )
    _exact_keys(
        container,
        frozenset({"args", "command", "env", "image", "resources"}),
        label="Cloud Run container attachment boundary",
    )
    resources = _mapping(
        container.get("resources"), label="Cloud Run container resources"
    )
    _exact_keys(
        resources,
        frozenset({"limits"}),
        label="Cloud Run container resources",
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
        raise CorpusArtifactSourceTransportError("job environment differs")
    result = {str(row["name"]): str(row["value"]) for row in rows}
    if len(result) != len(rows):
        raise CorpusArtifactSourceTransportError("job environment repeats")
    return result


def job_identity(value: object, *, label: str = "job") -> dict[str, str]:
    item = _mapping(value, label=label)
    metadata = _mapping(item.get("metadata"), label=f"{label}.metadata")
    status = _mapping(item.get("status"), label=f"{label}.status")
    name = _string(metadata.get("name"), label=f"{label}.name")
    generation = _generation(
        metadata.get("generation"), label=f"{label}.generation"
    )
    observed = _generation(
        status.get("observedGeneration"), label=f"{label}.observedGeneration"
    )
    conditions = status.get("conditions")
    if (
        _JOB.fullmatch(name) is None
        or _GENERATION.fullmatch(generation) is None
        or observed != generation
        or type(conditions) is not list
        or not any(
            isinstance(row, Mapping)
            and row.get("type") == "Ready"
            and row.get("status") == "True"
            for row in conditions
        )
    ):
        raise CorpusArtifactSourceTransportError(f"{label} is not reconciled Ready")
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
    status = _mapping(value.get("status", {}), label="execution status")
    conditions = status.get("conditions", [])
    if type(conditions) is not list:
        raise CorpusArtifactSourceTransportError("execution conditions differ")
    rows = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if not rows:
        return "Unknown"
    if len(rows) != 1 or rows[0].get("status") not in {"Unknown", "True", "False"}:
        raise CorpusArtifactSourceTransportError(
            "execution Completed state differs"
        )
    return str(rows[0]["status"])


def execution_census_names(value: object) -> list[str]:
    rows = _sequence(value, label="execution census")
    names: list[str] = []
    for ordinal, raw in enumerate(rows):
        item = _mapping(raw, label=f"execution census[{ordinal}]")
        metadata = _mapping(item.get("metadata"), label="execution metadata")
        name = _string(
            metadata.get("name"), label="execution census name"
        ).rsplit("/", 1)[-1]
        if _EXECUTION.fullmatch(name) is None:
            raise CorpusArtifactSourceTransportError(
                "execution census name differs"
            )
        names.append(name)
    if len(names) != len(set(names)):
        raise CorpusArtifactSourceTransportError(
            "execution census repeats a name"
        )
    return sorted(names)


def _require_all_terminal(value: object, *, label: str) -> None:
    for ordinal, raw in enumerate(_sequence(value, label=label)):
        item = _mapping(raw, label=f"{label}[{ordinal}]")
        if _completion_state(item) == "Unknown":
            raise CorpusArtifactSourceTransportError(
                f"{label} contains an active execution"
            )


def _canonical_execution_census(value: object) -> list[dict[str, object]]:
    rows = [
        dict(_mapping(raw, label=f"execution census[{ordinal}]"))
        for ordinal, raw in enumerate(
            _sequence(value, label="execution census")
        )
    ]
    return sorted(
        rows,
        key=lambda row: str(
            _mapping(row.get("metadata"), label="execution census metadata").get(
                "name", ""
            )
        ),
    )


def _canonical_scheduler_census(value: object) -> list[dict[str, object]]:
    rows = [
        dict(_mapping(raw, label=f"scheduler census[{ordinal}]"))
        for ordinal, raw in enumerate(
            _sequence(value, label="scheduler census")
        )
    ]
    return sorted(rows, key=canonical_sha256)


def validate_scheduler_census(
    schedulers: object, *, job_name: str, all_regions_complete: bool
) -> None:
    rows = _sequence(schedulers, label="scheduler census")
    if all_regions_complete is not True:
        raise CorpusArtifactSourceTransportError(
            "all-region scheduler census is required"
        )
    needle = f"/jobs/{job_name}:run"
    for raw in rows:
        item = _mapping(raw, label="scheduler census row")
        target = item.get("httpTarget", {})
        if isinstance(target, Mapping) and needle in str(target.get("uri", "")):
            raise CorpusArtifactSourceTransportError(
                "scheduler targets reused job"
            )


def validate_parked_job(
    value: object,
    *,
    expected_job: Mapping[str, object],
    build: Mapping[str, object],
    service_account: str,
) -> dict[str, str]:
    item = _mapping(value, label="parked job")
    identity = job_identity(item, label="parked job")
    expected = _mapping(expected_job, label="expected job")
    _validate_job_template_boundary(item)
    outer = _outer_spec(item)
    _exact_keys(
        outer,
        frozenset({"parallelism", "taskCount", "template"}),
        label="parked job outer spec",
    )
    _exact_keys(
        _mapping(outer.get("template"), label="parked task template"),
        frozenset({"spec"}),
        label="parked task template",
    )
    task = _task_spec(item)
    containers = task.get("containers")
    if type(containers) is not list or len(containers) != 1:
        raise CorpusArtifactSourceTransportError("parked container differs")
    container = _mapping(containers[0], label="parked container")
    _validate_task_attachment_boundary(task, container)
    expected_env = {
        ENABLE_ENV: "1",
        IMAGE_ENV: str(build["image"]),
        BUILD_ENV: str(build["build_id"]),
        CODE_ENV: str(build["code_sha"]),
    }
    if (
        identity != expected
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
        or _mapping(
            container.get("resources", {}), label="parked resources"
        ).get("limits") != EXPECTED_RESOURCES
    ):
        raise CorpusArtifactSourceTransportError(
            "job is not the exact default-off parked source contract"
        )
    return identity


def validate_execution(
    value: object,
    *,
    contract: Mapping[str, object],
    execution_intent_identity: object,
    require_terminal_success: bool,
) -> dict[str, object]:
    item = _mapping(value, label="execution metadata")
    metadata = _mapping(item.get("metadata"), label="execution identity")
    spec = _mapping(item.get("spec"), label="execution spec")
    _exact_keys(
        spec,
        frozenset({"parallelism", "taskCount", "template"}),
        label="execution spec",
    )
    execution_template = _mapping(
        spec.get("template"), label="execution template"
    )
    _exact_keys(
        execution_template,
        frozenset({"spec"}),
        label="execution template",
    )
    status = _mapping(item.get("status", {}), label="execution status")
    full_name = _string(metadata.get("name"), label="execution name")
    execution_id = full_name.rsplit("/", 1)[-1]
    if _EXECUTION.fullmatch(execution_id) is None:
        raise CorpusArtifactSourceTransportError("execution name differs")
    job = _mapping(contract["job"], label="contract job")
    labels = _mapping(metadata.get("labels"), label="execution labels")
    if (
        labels.get("run.googleapis.com/job") != job["name"]
        or labels.get("run.googleapis.com/jobUid") != job["uid"]
        or str(labels.get("run.googleapis.com/jobGeneration"))
        != str(job["generation"])
        or spec.get("taskCount") != EXPECTED_TASK_COUNT
        or spec.get("parallelism") != EXPECTED_PARALLELISM
    ):
        raise CorpusArtifactSourceTransportError(
            "execution job binding differs"
        )
    task = _mapping(
        _mapping(spec.get("template"), label="execution template").get("spec"),
        label="execution task spec",
    )
    containers = task.get("containers")
    if type(containers) is not list or len(containers) != 1:
        raise CorpusArtifactSourceTransportError(
            "execution container differs"
        )
    container = _mapping(containers[0], label="execution container")
    _validate_task_attachment_boundary(task, container)
    build = _mapping(contract["build"], label="contract build")
    expected_env = {
        ENABLE_ENV: "1",
        IMAGE_ENV: str(build["image"]),
        BUILD_ENV: str(build["build_id"]),
        CODE_ENV: str(build["code_sha"]),
    }
    if (
        task.get("maxRetries") != EXPECTED_MAX_RETRIES
        or task.get("timeoutSeconds") != EXPECTED_TIMEOUT_SECONDS
        or task.get("serviceAccountName") != contract["service_account"]
        or task.get("volumes", []) != []
        or container.get("image") != build["image"]
        or container.get("command") != PARKED_COMMAND
        or container.get("args") != cloud_worker_args(
            contract["plan_object"], execution_intent_identity
        )
        or container.get("volumeMounts", []) != []
        or _container_environment(container) != expected_env
        or _mapping(
            container.get("resources", {}), label="execution resources"
        ).get("limits") != EXPECTED_RESOURCES
    ):
        raise CorpusArtifactSourceTransportError(
            "execution worker override differs"
        )
    state = _completion_state(item)
    counters = {
        "succeeded": _integer(status.get("succeededCount", 0), label="succeeded"),
        "failed": _integer(status.get("failedCount", 0), label="failed"),
        "cancelled": _integer(status.get("cancelledCount", 0), label="cancelled"),
        "retried": _integer(status.get("retriedCount", 0), label="retried"),
    }
    if require_terminal_success and (
        state != "True"
        or counters
        != {"succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0}
    ):
        raise CorpusArtifactSourceTransportError(
            "execution is not strict terminal success"
        )
    return {
        "execution_id": execution_id,
        "execution_name": full_name,
        "execution_uid": _string(metadata.get("uid"), label="execution UID"),
        "state": state,
        "counters": counters,
        "spec_sha256": canonical_sha256(spec),
        "metadata_sha256": canonical_sha256(item),
    }


_CONTRACT_KEYS: Final = frozenset({
    "schema_version", "created_at_utc", "project", "region", "run_id",
    "delivery_prefix", "source_output_prefix", "plan_object", "plan_sha256",
    "runtime_iam_object", "runtime_iam_evidence_sha256", "build",
    "reuse_job_before", "job", "service_account", "execution_names_before",
    "source_publication_uris", "source_output_object_count", "governance_uris",
    "default_command", "default_args", "worker_args", "task_count",
    "parallelism", "max_retries", "timeout_seconds", "resources",
    "plan_outside_source_prefix", "create_once", "worker_object_list_used",
    "operator_inventory_required", "automatic_retry_licensed",
    "uses_realized_outcomes", "historical_scoring_licensed",
    "production_change_licensed", "transport_contract_sha256",
})


def validate_transport_contract(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="source transport contract"))
    _exact_keys(item, _CONTRACT_KEYS, label="source transport contract")
    _validate_self_hash(
        item, field="transport_contract_sha256", label="source transport contract"
    )
    run_id = _string(item["run_id"], label="contract run ID")
    delivery = _gcs_prefix(item["delivery_prefix"], label="delivery prefix")
    output = _gcs_prefix(item["source_output_prefix"], label="source output prefix")
    if (
        item["schema_version"] != TRANSPORT_CONTRACT_SCHEMA
        or item["project"] != PROJECT
        or item["region"] != REGION
        or not delivery.endswith(f"/{run_id}/")
        or not output.endswith(f"/{run_id}/")
        or delivery.startswith(output)
        or output.startswith(delivery)
        or item["governance_uris"] != _governance_uris(delivery)
        or item["source_publication_uris"] != source._publication_uris(output)  # noqa: SLF001
        or item["source_output_object_count"] != 9
        or item["default_command"] != PARKED_COMMAND
        or item["default_args"] != PARKED_ARGS
        or item["task_count"] != EXPECTED_TASK_COUNT
        or item["parallelism"] != EXPECTED_PARALLELISM
        or item["max_retries"] != EXPECTED_MAX_RETRIES
        or item["timeout_seconds"] != EXPECTED_TIMEOUT_SECONDS
        or item["resources"] != EXPECTED_RESOURCES
        or item["plan_outside_source_prefix"] is not True
        or item["create_once"] is not True
        or item["worker_object_list_used"] is not False
        or item["operator_inventory_required"] is not True
        or item["automatic_retry_licensed"] is not False
        or item["uses_realized_outcomes"] is not False
        or item["historical_scoring_licensed"] is not False
        or item["production_change_licensed"] is not False
    ):
        raise CorpusArtifactSourceTransportError(
            "source transport contract authority differs"
        )
    _timestamp(item["created_at_utc"], label="contract timestamp")
    _sha(item["plan_sha256"], label="contract plan SHA")
    _sha(
        item["runtime_iam_evidence_sha256"], label="contract IAM evidence SHA"
    )
    plan_identity = object_identity(item["plan_object"], label="contract plan")
    iam_identity = object_identity(
        item["runtime_iam_object"], label="contract runtime IAM"
    )
    uris = _governance_uris(delivery)
    if (
        plan_identity["uri"] != uris["plan"]
        or iam_identity["uri"] != uris["runtime_iam"]
        or str(plan_identity["uri"]).startswith(output)
        or str(iam_identity["uri"]).startswith(output)
    ):
        raise CorpusArtifactSourceTransportError(
            "contract delivery identity differs"
        )
    build = _mapping(item["build"], label="contract build")
    _exact_keys(
        build,
        frozenset({
            "build_id", "code_repository", "code_sha", "image", "image_tag",
            "build_config_sha256",
        }),
        label="contract build",
    )
    if (
        _BUILD.fullmatch(str(build["build_id"])) is None
        or build["code_repository"] != EXPECTED_CODE_REPOSITORY
        or _COMMIT.fullmatch(str(build["code_sha"])) is None
        or _IMAGE.fullmatch(str(build["image"])) is None
        or type(build["image_tag"]) is not str
        or str(build["image_tag"]).rsplit(":", 1)[0]
        != str(build["image"]).rsplit("@", 1)[0]
    ):
        raise CorpusArtifactSourceTransportError("contract build differs")
    service_account = _string(
        item["service_account"], label="contract service account"
    )
    _sha(build["build_config_sha256"], label="contract build config SHA")
    if _SERVICE_ACCOUNT.fullmatch(service_account) is None:
        raise CorpusArtifactSourceTransportError(
            "contract service account differs"
        )
    prior = _mapping(item["reuse_job_before"], label="contract prior job")
    parked = _mapping(item["job"], label="contract parked job")
    expected_job_keys = frozenset({
        "name", "uid", "generation", "observed_generation", "spec_sha256",
    })
    _exact_keys(prior, expected_job_keys, label="contract prior job")
    _exact_keys(parked, expected_job_keys, label="contract parked job")
    if (
        prior["name"] != parked["name"]
        or prior["uid"] != parked["uid"]
        or parked["generation"] != parked["observed_generation"]
        or prior["generation"] != prior["observed_generation"]
        or _GENERATION.fullmatch(str(prior["generation"])) is None
        or _GENERATION.fullmatch(str(parked["generation"])) is None
        or int(str(parked["generation"])) <= int(str(prior["generation"]))
        or _JOB.fullmatch(str(parked["name"])) is None
    ):
        raise CorpusArtifactSourceTransportError(
            "contract reused-job transition differs"
        )
    _sha(prior["spec_sha256"], label="prior job spec SHA")
    _sha(parked["spec_sha256"], label="parked job spec SHA")
    names = _sequence(
        item["execution_names_before"], label="contract execution names"
    )
    if (
        list(names) != sorted(names)
        or len(names) != len(set(names))
        or any(_EXECUTION.fullmatch(str(name)) is None for name in names)
    ):
        raise CorpusArtifactSourceTransportError(
            "contract execution baseline differs"
        )
    if item["worker_args"] != cloud_worker_base_args(plan_identity):
        raise CorpusArtifactSourceTransportError("contract worker args differ")
    item["plan_object"] = plan_identity
    item["runtime_iam_object"] = iam_identity
    item["build"] = dict(build)
    item["reuse_job_before"] = dict(prior)
    item["job"] = dict(parked)
    item["execution_names_before"] = list(names)
    return item


def _parse_plan(raw: bytes) -> dict[str, object]:
    try:
        return source.validate_execution_plan(
            source.parse_canonical_json_bytes(raw, label="delivered plan")
        )
    except source.CorpusArtifactSourcePreparationError as exc:
        raise CorpusArtifactSourceTransportError(
            "delivered source plan differs"
        ) from exc


def _base_source_receipts(
    storage: ObjectStore, plan: Mapping[str, object]
) -> tuple[dict[str, object], tuple[dict[str, object], ...], bytes]:
    identity = object_identity(
        plan["base_source_lock_object"], label="plan base source lock"
    )
    raw = storage.read(identity)
    try:
        base, receipts = source.validate_base_source_lock_bytes(
            raw, identity=identity
        )
    except source.CorpusArtifactSourcePreparationError as exc:
        raise CorpusArtifactSourceTransportError(
            "base source-lock replay differs"
        ) from exc
    manifest_sha = canonical_sha256([
        {
            "season": row["season"],
            "week": row["week"],
            "block": row["block"],
            "uri": row["uri"],
            "generation": row["generation"],
            "sha256": row["sha256"],
            "bytes": row["bytes"],
        }
        for row in receipts
    ])
    if manifest_sha != plan["base_source_lock_artifact_manifest_sha256"]:
        raise CorpusArtifactSourceTransportError(
            "base source-lock 270-object manifest differs"
        )
    return base, receipts, raw


def _required_read_uris(
    *, plan_identity: Mapping[str, object], plan: Mapping[str, object],
    receipts: Sequence[Mapping[str, object]],
) -> list[str]:
    return sorted({
        str(plan_identity["uri"]),
        str(_mapping(plan["base_source_lock_object"], label="base object")["uri"]),
        *(str(row["uri"]) for row in receipts),
    })


def _reopen_contract(
    storage: ObjectStore, contract_identity: object
) -> tuple[dict[str, object], dict[str, object], bytes]:
    retained_identity = object_identity(
        contract_identity, label="transport contract identity"
    )
    raw = storage.read(retained_identity)
    contract = validate_transport_contract(
        strict_json_bytes(raw, label="source transport contract")
    )
    if retained_identity["uri"] != contract["governance_uris"]["contract"]:
        raise CorpusArtifactSourceTransportError(
            "transport contract URI differs"
        )
    plan_raw = storage.read(contract["plan_object"])
    plan = _parse_plan(plan_raw)
    if (
        plan["plan_sha256"] != contract["plan_sha256"]
        or plan["run_id"] != contract["run_id"]
        or plan["output_prefix"] != contract["source_output_prefix"]
        or plan["publication_uris"] != contract["source_publication_uris"]
        or plan["runtime_identity"]["job"] != contract["job"]["name"]
        or plan["runtime_identity"]["code_sha"] != contract["build"]["code_sha"]
        or plan["runtime_identity"]["image"] != contract["build"]["image"]
    ):
        raise CorpusArtifactSourceTransportError(
            "contract/source-plan binding differs"
        )
    _base, receipts, _base_raw = _base_source_receipts(storage, plan)
    iam_raw = storage.read(contract["runtime_iam_object"])
    iam = strict_json_bytes(iam_raw, label="runtime IAM evidence")
    validated_iam = validate_runtime_iam_evidence(
        iam,
        service_account=str(contract["service_account"]),
        required_read_uris=_required_read_uris(
            plan_identity=contract["plan_object"], plan=plan, receipts=receipts
        ) + [str(contract["governance_uris"]["launch_ledger"])],
        output_prefix=str(contract["source_output_prefix"]),
    )
    if (
        validated_iam["iam_evidence_sha256"]
        != contract["runtime_iam_evidence_sha256"]
    ):
        raise CorpusArtifactSourceTransportError(
            "contract runtime IAM binding differs"
        )
    return contract, plan, raw


def configure_transport(
    *,
    plan_raw: bytes,
    runtime_iam: object,
    delivery_prefix: str,
    build_metadata: object,
    build_id: str,
    code_sha: str,
    image: str,
    service_account: str,
    job_before: object,
    job_after: object,
    executions_before: object,
    executions_after: object,
    schedulers_before: object,
    schedulers_after: object,
    all_regions_complete: bool,
    created_at_utc: str,
    storage: ObjectStore,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    require_execute_gate(execute=execute, environ=environ)
    plan = _parse_plan(plan_raw)
    run_id = str(plan["run_id"])
    delivery = _gcs_prefix(delivery_prefix, label="delivery prefix")
    output = _gcs_prefix(plan["output_prefix"], label="source output prefix")
    if (
        not delivery.endswith(f"/{run_id}/")
        or delivery.startswith(output)
        or output.startswith(delivery)
    ):
        raise CorpusArtifactSourceTransportError(
            "delivery and nine-object output prefixes must be disjoint"
        )
    if storage.inventory(delivery) != [] or storage.inventory(output) != []:
        raise CorpusArtifactSourceTransportError(
            "delivery/source namespace is not pristine"
        )
    build = validate_build_metadata(
        build_metadata, build_id=build_id, code_sha=code_sha, image=image
    )
    runtime = _mapping(plan["runtime_identity"], label="plan runtime")
    if (
        runtime["code_sha"] != code_sha
        or runtime["image"] != image
        or runtime["job"] is None
    ):
        raise CorpusArtifactSourceTransportError(
            "plan/build/runtime identity differs"
        )
    prior = job_identity(job_before, label="reused job before")
    parked = job_identity(job_after, label="parked job after")
    if (
        prior["name"] != runtime["job"]
        or parked["name"] != runtime["job"]
        or prior["uid"] != parked["uid"]
        or int(parked["generation"]) <= int(prior["generation"])
    ):
        raise CorpusArtifactSourceTransportError(
            "reused-job update identity differs"
        )
    validate_parked_job(
        job_after,
        expected_job=parked,
        build=build,
        service_account=service_account,
    )
    names_before = execution_census_names(executions_before)
    names_after = execution_census_names(executions_after)
    _require_all_terminal(executions_before, label="preconfigure executions")
    _require_all_terminal(executions_after, label="configured executions")
    if names_before != names_after:
        raise CorpusArtifactSourceTransportError(
            "configure changed the execution census"
        )
    validate_scheduler_census(
        schedulers_before,
        job_name=str(runtime["job"]),
        all_regions_complete=all_regions_complete,
    )
    validate_scheduler_census(
        schedulers_after,
        job_name=str(runtime["job"]),
        all_regions_complete=all_regions_complete,
    )
    _base, receipts, _base_raw = _base_source_receipts(storage, plan)
    uris = _governance_uris(delivery)
    plan_identity = object_identity(
        storage.publish(uris["plan"], plan_raw), label="published plan"
    )
    if storage.read(plan_identity) != plan_raw:
        raise CorpusArtifactSourceTransportError("published plan reopen differs")
    validated_iam = validate_runtime_iam_evidence(
        runtime_iam,
        service_account=service_account,
        required_read_uris=_required_read_uris(
            plan_identity=plan_identity, plan=plan, receipts=receipts
        ) + [str(uris["launch_ledger"])],
        output_prefix=output,
    )
    iam_raw = canonical_json_bytes(validated_iam)
    iam_identity = object_identity(
        storage.publish(uris["runtime_iam"], iam_raw),
        label="published runtime IAM evidence",
    )
    if storage.read(iam_identity) != iam_raw:
        raise CorpusArtifactSourceTransportError(
            "runtime IAM publication reopen differs"
        )
    _require_exact_inventory(
        storage,
        prefix=delivery,
        identities=[plan_identity, iam_identity],
        label="precontract delivery inventory",
    )
    contract = _self_hash({
        "schema_version": TRANSPORT_CONTRACT_SCHEMA,
        "created_at_utc": _timestamp(created_at_utc, label="configure timestamp"),
        "project": PROJECT,
        "region": REGION,
        "run_id": run_id,
        "delivery_prefix": delivery,
        "source_output_prefix": output,
        "plan_object": plan_identity,
        "plan_sha256": plan["plan_sha256"],
        "runtime_iam_object": iam_identity,
        "runtime_iam_evidence_sha256": validated_iam["iam_evidence_sha256"],
        "build": build,
        "reuse_job_before": prior,
        "job": parked,
        "service_account": service_account,
        "execution_names_before": names_after,
        "source_publication_uris": plan["publication_uris"],
        "source_output_object_count": 9,
        "governance_uris": uris,
        "default_command": PARKED_COMMAND,
        "default_args": PARKED_ARGS,
        "worker_args": cloud_worker_base_args(plan_identity),
        "task_count": EXPECTED_TASK_COUNT,
        "parallelism": EXPECTED_PARALLELISM,
        "max_retries": EXPECTED_MAX_RETRIES,
        "timeout_seconds": EXPECTED_TIMEOUT_SECONDS,
        "resources": EXPECTED_RESOURCES,
        "plan_outside_source_prefix": True,
        "create_once": True,
        "worker_object_list_used": False,
        "operator_inventory_required": True,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }, field="transport_contract_sha256")
    contract = validate_transport_contract(contract)
    contract_raw = canonical_json_bytes(contract)
    contract_identity = object_identity(
        storage.publish(uris["contract"], contract_raw),
        label="published transport contract",
    )
    if storage.read(contract_identity) != contract_raw:
        raise CorpusArtifactSourceTransportError(
            "transport contract publication reopen differs"
        )
    _require_exact_inventory(
        storage,
        prefix=delivery,
        identities=[plan_identity, iam_identity, contract_identity],
        label="configured delivery inventory",
    )
    if storage.inventory(output) != []:
        raise CorpusArtifactSourceTransportError(
            "source namespace changed during configure"
        )
    return {
        "schema_version": "corpus-artifact-source-configured/v1",
        "run_id": run_id,
        "plan_object": plan_identity,
        "runtime_iam_object": iam_identity,
        "transport_contract": contract_identity,
        "launch_permitted": False,
        "next_action": "consume-launch-once",
    }


_LAUNCH_LEDGER_KEYS: Final = frozenset({
    "schema_version", "created_at_utc", "transport_contract", "plan_object",
    "run_id", "job", "execution_names_before", "worker_args",
    "worker_args_sha256", "launch_authority_consumed", "one_execution",
    "max_retries", "automatic_retry_licensed", "uses_realized_outcomes",
    "production_change_licensed", "launch_ledger_sha256",
    "execution_intent", "intent_nonce",
})


def _validate_launch_ledger(
    value: object,
    *,
    contract: Mapping[str, object],
    contract_identity: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="source launch ledger"))
    _exact_keys(item, _LAUNCH_LEDGER_KEYS, label="source launch ledger")
    _validate_self_hash(item, field="launch_ledger_sha256", label="launch ledger")
    if (
        item["schema_version"] != LAUNCH_LEDGER_SCHEMA
        or item["transport_contract"] != contract_identity
        or item["plan_object"] != contract["plan_object"]
        or item["run_id"] != contract["run_id"]
        or item["job"] != contract["job"]
        or item["execution_names_before"] != contract["execution_names_before"]
        or item["worker_args"] != contract["worker_args"]
        or item["worker_args_sha256"] != canonical_sha256(contract["worker_args"])
        or item["launch_authority_consumed"] is not True
        or item["execution_intent"] is not True
        or item["intent_nonce"] != canonical_sha256({
            "transport_contract": contract_identity,
            "plan_object": contract["plan_object"],
            "job": contract["job"],
            "run_id": contract["run_id"],
        })
        or item["one_execution"] is not True
        or item["max_retries"] != 0
        or item["automatic_retry_licensed"] is not False
        or item["uses_realized_outcomes"] is not False
        or item["production_change_licensed"] is not False
    ):
        raise CorpusArtifactSourceTransportError("launch ledger binding differs")
    _timestamp(item["created_at_utc"], label="launch ledger timestamp")
    return item


def _resolve_json(
    storage: ObjectStore, uri: str, *, label: str
) -> tuple[dict[str, object], dict[str, object], bytes]:
    raw_identity, raw = storage.resolve_current(uri)
    identity = object_identity(raw_identity, label=f"{label} identity")
    value = dict(_mapping(strict_json_bytes(raw, label=label), label=label))
    return value, identity, raw


def _publish_consumption(
    storage: ObjectStore, *, uri: str, raw: bytes
) -> tuple[dict[str, object], bool]:
    try:
        return object_identity(
            storage.publish(uri, raw), label="consumption publication"
        ), True
    except Exception as publish_error:
        try:
            current_identity, current_raw = storage.resolve_current(uri)
            identity = object_identity(
                current_identity, label="existing consumption publication"
            )
        except Exception:
            raise CorpusArtifactSourceTransportError(
                "create-once consumption cannot be recovered"
            ) from publish_error
        if current_raw != raw:
            raise CorpusArtifactSourceTransportError(
                "existing create-once consumption differs"
            ) from publish_error
        return identity, False


def _delivery_inventory_with_optional(
    storage: ObjectStore,
    *,
    contract: Mapping[str, object],
    contract_identity: Mapping[str, object],
    required: Sequence[object],
    optional_uri: str | None,
    label: str,
) -> dict[str, object] | None:
    del contract_identity
    prefix = str(contract["delivery_prefix"])
    observed = _normalized_inventory(storage.inventory(prefix), label=label)
    expected = _identity_rows(required)
    extras = [row for row in observed if row not in expected]
    if not extras:
        if observed != expected:
            raise CorpusArtifactSourceTransportError(f"{label} differs")
        return None
    if (
        optional_uri is None
        or len(extras) != 1
        or extras[0]["uri"] != optional_uri
        or observed != sorted(
            [*expected, extras[0]],
            key=lambda row: (str(row["uri"]), str(row["generation"])),
        )
    ):
        raise CorpusArtifactSourceTransportError(f"{label} differs")
    identity, _raw = storage.resolve_generation(
        str(extras[0]["uri"]), str(extras[0]["generation"])
    )
    return object_identity(identity, label=f"{label} optional object")


def _source_inventory_state(
    storage: ObjectStore,
    *,
    contract: Mapping[str, object],
    mode: str,
) -> list[dict[str, object]]:
    observed = _normalized_inventory(
        storage.inventory(str(contract["source_output_prefix"])),
        label=f"source {mode} inventory",
    )
    allowed = set(_mapping(
        contract["source_publication_uris"], label="source publication URIs"
    ).values())
    if any(row["uri"] not in allowed for row in observed):
        raise CorpusArtifactSourceTransportError(
            f"source {mode} inventory contains a rogue object"
        )
    if len({str(row["uri"]) for row in observed}) != len(observed):
        raise CorpusArtifactSourceTransportError(
            f"source {mode} inventory contains multiple generations"
        )
    terminal_uri = contract["source_publication_uris"]["publication_completion"]
    if mode == "pristine" and observed:
        raise CorpusArtifactSourceTransportError(
            "source namespace is not pristine before launch"
        )
    if mode == "partial" and any(row["uri"] == terminal_uri for row in observed) and len(observed) != 9:
        raise CorpusArtifactSourceTransportError(
            "source terminal exists in a partial namespace"
        )
    if mode == "terminal" and (
        len(observed) != 9 or {row["uri"] for row in observed} != allowed
    ):
        raise CorpusArtifactSourceTransportError(
            "source terminal inventory is not the exact nine objects"
        )
    return observed


def consume_launch(
    *,
    storage: ObjectStore,
    contract_identity: object,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    created_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    require_execute_gate(execute=execute, environ=environ)
    retained_contract_identity = object_identity(
        contract_identity, label="transport contract identity"
    )
    contract, _plan, _raw = _reopen_contract(
        storage, retained_contract_identity
    )
    validate_parked_job(
        parked_job,
        expected_job=_mapping(contract["job"], label="contract job"),
        build=_mapping(contract["build"], label="contract build"),
        service_account=str(contract["service_account"]),
    )
    names = execution_census_names(executions)
    _require_all_terminal(executions, label="prelaunch executions")
    if names != contract["execution_names_before"]:
        raise CorpusArtifactSourceTransportError(
            "prelaunch execution census differs from configure"
        )
    validate_scheduler_census(
        schedulers,
        job_name=str(contract["job"]["name"]),
        all_regions_complete=all_regions_complete,
    )
    _source_inventory_state(storage, contract=contract, mode="pristine")
    base_delivery = [
        contract["plan_object"], contract["runtime_iam_object"],
        retained_contract_identity,
    ]
    existing = _delivery_inventory_with_optional(
        storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        required=base_delivery,
        optional_uri=str(contract["governance_uris"]["launch_ledger"]),
        label="prelaunch delivery inventory",
    )
    ledger = _self_hash({
        "schema_version": LAUNCH_LEDGER_SCHEMA,
        "created_at_utc": _timestamp(created_at_utc, label="launch timestamp"),
        "transport_contract": retained_contract_identity,
        "plan_object": contract["plan_object"],
        "run_id": contract["run_id"],
        "job": contract["job"],
        "execution_names_before": names,
        "worker_args": contract["worker_args"],
        "worker_args_sha256": canonical_sha256(contract["worker_args"]),
        "launch_authority_consumed": True,
        "execution_intent": True,
        "intent_nonce": canonical_sha256({
            "transport_contract": retained_contract_identity,
            "plan_object": contract["plan_object"],
            "job": contract["job"],
            "run_id": contract["run_id"],
        }),
        "one_execution": True,
        "max_retries": 0,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
    }, field="launch_ledger_sha256")
    ledger_raw = canonical_json_bytes(ledger)
    ledger_identity, created = _publish_consumption(
        storage,
        uri=str(contract["governance_uris"]["launch_ledger"]),
        raw=ledger_raw,
    )
    if existing is not None and existing != ledger_identity:
        raise CorpusArtifactSourceTransportError(
            "existing launch ledger identity differs"
        )
    _validate_launch_ledger(
        ledger,
        contract=contract,
        contract_identity=retained_contract_identity,
    )
    _require_exact_inventory(
        storage,
        prefix=str(contract["delivery_prefix"]),
        identities=[*base_delivery, ledger_identity],
        label="consumed-launch delivery inventory",
    )
    return {
        "schema_version": "corpus-artifact-source-launch-ready/v1",
        "launch_ledger": ledger_identity,
        "worker_args": (
            cloud_worker_args(contract["plan_object"], ledger_identity)
            if created else []
        ),
        "launch_permitted": created,
        "launch_authority_consumed": True,
        "automatic_retry_licensed": False,
        "recovery_action": (
            "invoke-exactly-once-now" if created else "recover-only-never-relaunch"
        ),
    }


def _load_launch_ledger(
    storage: ObjectStore,
    *,
    contract: Mapping[str, object],
    contract_identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    value, identity, _raw = _resolve_json(
        storage,
        str(contract["governance_uris"]["launch_ledger"]),
        label="source launch ledger",
    )
    ledger = _validate_launch_ledger(
        value, contract=contract, contract_identity=contract_identity
    )
    return ledger, identity


def _one_new_execution(
    *, contract: Mapping[str, object], executions: object
) -> tuple[str, list[str]]:
    names = execution_census_names(executions)
    baseline = set(str(row) for row in contract["execution_names_before"])
    current = set(names)
    if not baseline.issubset(current) or len(current - baseline) != 1:
        raise CorpusArtifactSourceTransportError(
            "execution census must contain exactly one new execution"
        )
    for raw in _sequence(executions, label="execution census"):
        item = _mapping(raw, label="execution census row")
        metadata = _mapping(item.get("metadata"), label="execution census metadata")
        name = str(metadata.get("name", "")).rsplit("/", 1)[-1]
        if name in baseline and _completion_state(item) == "Unknown":
            raise CorpusArtifactSourceTransportError(
                "a configured baseline execution became active"
            )
    return next(iter(current - baseline)), names


def recover_execution_name(
    *,
    storage: ObjectStore,
    contract_identity: object,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    require_execute_gate(execute=execute, environ=environ)
    retained_contract_identity = object_identity(
        contract_identity, label="transport contract identity"
    )
    contract, _plan, _raw = _reopen_contract(storage, retained_contract_identity)
    validate_parked_job(
        parked_job,
        expected_job=_mapping(contract["job"], label="contract job"),
        build=_mapping(contract["build"], label="contract build"),
        service_account=str(contract["service_account"]),
    )
    validate_scheduler_census(
        schedulers,
        job_name=str(contract["job"]["name"]),
        all_regions_complete=all_regions_complete,
    )
    _ledger, ledger_identity = _load_launch_ledger(
        storage,
        contract=contract,
        contract_identity=retained_contract_identity,
    )
    _require_exact_inventory(
        storage,
        prefix=str(contract["delivery_prefix"]),
        identities=[
            contract["plan_object"], contract["runtime_iam_object"],
            retained_contract_identity, ledger_identity,
        ],
        label="recovery delivery inventory",
    )
    _source_inventory_state(storage, contract=contract, mode="partial")
    execution_id, names = _one_new_execution(
        contract=contract, executions=executions
    )
    return {
        "schema_version": "corpus-artifact-source-recovery-candidate/v1",
        "execution_id": execution_id,
        "execution_names_after": names,
        "census_only": True,
        "launch_permitted": False,
        "automatic_retry_licensed": False,
    }


_EXECUTION_BINDING_KEYS: Final = frozenset({
    "schema_version", "created_at_utc", "transport_contract", "launch_ledger",
    "run_id", "job", "execution_id", "execution_name", "execution_uid",
    "execution_spec_sha256", "execution_names_after", "one_execution",
    "attempt_zero", "retry_count", "automatic_retry_licensed",
    "uses_realized_outcomes", "production_change_licensed",
    "execution_binding_sha256",
})


def _validate_execution_binding(
    value: object,
    *,
    contract: Mapping[str, object],
    contract_identity: Mapping[str, object],
    launch_identity: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="execution binding"))
    _exact_keys(item, _EXECUTION_BINDING_KEYS, label="execution binding")
    _validate_self_hash(
        item, field="execution_binding_sha256", label="execution binding"
    )
    baseline = set(str(row) for row in contract["execution_names_before"])
    after = _sequence(item["execution_names_after"], label="binding census")
    execution_id = _string(item["execution_id"], label="bound execution ID")
    execution_name = _string(
        item["execution_name"], label="bound execution name"
    )
    if (
        item["schema_version"] != EXECUTION_BINDING_SCHEMA
        or item["transport_contract"] != contract_identity
        or item["launch_ledger"] != launch_identity
        or item["run_id"] != contract["run_id"]
        or item["job"] != contract["job"]
        or execution_name.rsplit("/", 1)[-1] != execution_id
        or set(after) - baseline != {execution_id}
        or len(after) != len(baseline) + 1
        or item["one_execution"] is not True
        or item["attempt_zero"] is not True
        or item["retry_count"] != 0
        or item["automatic_retry_licensed"] is not False
        or item["uses_realized_outcomes"] is not False
        or item["production_change_licensed"] is not False
    ):
        raise CorpusArtifactSourceTransportError(
            "execution binding authority differs"
        )
    _timestamp(item["created_at_utc"], label="execution binding timestamp")
    _string(item["execution_uid"], label="execution binding UID")
    _sha(item["execution_spec_sha256"], label="execution binding spec SHA")
    return item


def bind_execution(
    *,
    storage: ObjectStore,
    contract_identity: object,
    execution_metadata: object,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    created_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    require_execute_gate(execute=execute, environ=environ)
    retained_contract_identity = object_identity(
        contract_identity, label="transport contract identity"
    )
    contract, _plan, _raw = _reopen_contract(storage, retained_contract_identity)
    _ledger, ledger_identity = _load_launch_ledger(
        storage,
        contract=contract,
        contract_identity=retained_contract_identity,
    )
    validate_parked_job(
        parked_job,
        expected_job=_mapping(contract["job"], label="contract job"),
        build=_mapping(contract["build"], label="contract build"),
        service_account=str(contract["service_account"]),
    )
    validate_scheduler_census(
        schedulers,
        job_name=str(contract["job"]["name"]),
        all_regions_complete=all_regions_complete,
    )
    execution_id, names = _one_new_execution(
        contract=contract, executions=executions
    )
    execution = validate_execution(
        execution_metadata,
        contract=contract,
        execution_intent_identity=ledger_identity,
        require_terminal_success=False,
    )
    if execution["execution_id"] != execution_id:
        raise CorpusArtifactSourceTransportError(
            "bound execution differs from full census"
        )
    _source_inventory_state(storage, contract=contract, mode="partial")
    base_delivery = [
        contract["plan_object"], contract["runtime_iam_object"],
        retained_contract_identity, ledger_identity,
    ]
    existing = _delivery_inventory_with_optional(
        storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        required=base_delivery,
        optional_uri=str(contract["governance_uris"]["execution_binding"]),
        label="prebinding delivery inventory",
    )
    binding = _self_hash({
        "schema_version": EXECUTION_BINDING_SCHEMA,
        "created_at_utc": _timestamp(created_at_utc, label="binding timestamp"),
        "transport_contract": retained_contract_identity,
        "launch_ledger": ledger_identity,
        "run_id": contract["run_id"],
        "job": contract["job"],
        "execution_id": execution["execution_id"],
        "execution_name": execution["execution_name"],
        "execution_uid": execution["execution_uid"],
        "execution_spec_sha256": execution["spec_sha256"],
        "execution_names_after": names,
        "one_execution": True,
        "attempt_zero": True,
        "retry_count": 0,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
    }, field="execution_binding_sha256")
    binding_raw = canonical_json_bytes(binding)
    binding_identity, created = _publish_consumption(
        storage,
        uri=str(contract["governance_uris"]["execution_binding"]),
        raw=binding_raw,
    )
    if existing is not None and existing != binding_identity:
        raise CorpusArtifactSourceTransportError(
            "existing execution binding identity differs"
        )
    _validate_execution_binding(
        binding,
        contract=contract,
        contract_identity=retained_contract_identity,
        launch_identity=ledger_identity,
    )
    _require_exact_inventory(
        storage,
        prefix=str(contract["delivery_prefix"]),
        identities=[*base_delivery, binding_identity],
        label="bound delivery inventory",
    )
    return {
        "schema_version": "corpus-artifact-source-execution-bound/v1",
        "execution_binding": binding_identity,
        "execution_id": execution_id,
        "created": created,
        "launch_permitted": False,
        "automatic_retry_licensed": False,
    }


def _source_terminal_publications(
    storage: ObjectStore,
    *,
    contract: Mapping[str, object],
    plan: Mapping[str, object],
    execution_intent_identity: Mapping[str, object],
) -> dict[str, object]:
    """Reopen and independently replay the complete nine-object publication."""
    inventory = _source_inventory_state(storage, contract=contract, mode="terminal")
    trace_store = _VerifierTraceStore(
        storage,
        allowed=[
            *inventory,
            object_identity(
                plan["base_source_lock_object"], label="verifier base source lock"
            ),
        ],
    )
    by_uri = {str(row["uri"]): row for row in inventory}
    identities: dict[str, dict[str, object]] = {}
    raws: dict[str, bytes] = {}
    publication_uris = _mapping(
        contract["source_publication_uris"], label="source publication URIs"
    )
    for role, raw_uri in publication_uris.items():
        uri = str(raw_uri)
        row = by_uri[uri]
        raw_identity, body = trace_store.resolve_generation(
            uri, str(row["generation"])
        )
        identity = object_identity(
            raw_identity, label=f"terminal {role} identity"
        )
        if identity["bytes"] != row["bytes"]:
            raise CorpusArtifactSourceTransportError(
                f"terminal {role} inventory/body size differs"
            )
        identities[role] = identity
        raws[role] = body

    expected_claim_raw = source.canonical_json_bytes(source.build_prefix_claim(plan))
    if raws["prefix_claim"] != expected_claim_raw:
        raise CorpusArtifactSourceTransportError(
            "terminal prefix claim differs from delivered plan"
        )
    expected_registration_raw = authority.canonical_json_bytes(
        plan["registration"]
    )
    if raws["registration"] != expected_registration_raw:
        raise CorpusArtifactSourceTransportError(
            "terminal registration differs from delivered plan"
        )
    try:
        registration = authority.validate_registration(plan["registration"])
    except authority.CorpusArtifactSourceAuthorityError as exc:
        raise CorpusArtifactSourceTransportError(
            "terminal registration semantic validation failed"
        ) from exc

    query_identities = source._query_identities(registration)  # noqa: SLF001
    captures: dict[str, dict[str, object]] = {}
    capture_identities: dict[str, dict[str, object]] = {}
    for role in source.QUERY_ROLES:
        try:
            parsed = source.parse_canonical_json_bytes(
                raws[role], label=f"terminal {role} capture"
            )
            capture = source.validate_query_capture(
                parsed,
                role=role,
                query_identity=query_identities[role],
                registered_at=str(registration["registered_at"]),
            )
        except source.CorpusArtifactSourcePreparationError as exc:
            raise CorpusArtifactSourceTransportError(
                f"terminal {role} capture semantic validation failed"
            ) from exc
        captures[role] = capture
        capture_identities[role] = identities[role]

    base_source, receipts, _base_raw = _base_source_receipts(trace_store, plan)
    trace_store.allow([
        {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")}
        for receipt in receipts
    ])
    try:
        rebuilt_source = later.build_source_freeze(
            base_source_lock=base_source,
            base_source_lock_object=plan["base_source_lock_object"],
            base_source_lock_sha256=str(plan["base_source_lock_object"]["sha256"]),
            r0_candidate_rows=captures["r0_candidates"]["rows"],
            full_catalog_rows=captures["artifact_catalog"]["rows"],
            query_provenance={
                "candidate_query": captures["r0_candidates"]["query_receipt"],
                "catalog_query": captures["artifact_catalog"]["query_receipt"],
                "candidate_table": later.CANDIDATE_TABLE,
                "catalog_table": later.CATALOG_TABLE,
                "source_snapshot_at": registration["source_snapshot_at"],
            },
            runtime_identity=plan["runtime_identity"],
        )
    except later.LR8LaterSourceError as exc:
        raise CorpusArtifactSourceTransportError(
            "terminal later-source replay failed"
        ) from exc
    expected_source_raw = later.canonical_json(rebuilt_source)
    if raws["later_source_freeze"] != expected_source_raw:
        raise CorpusArtifactSourceTransportError(
            "terminal later-source freeze differs from query replay"
        )
    try:
        salary_diagnostic = source.build_salary_diagnostic(
            registration=registration,
            salary_capture=captures["salary_player_ids"],
        )
    except source.CorpusArtifactSourcePreparationError as exc:
        raise CorpusArtifactSourceTransportError(
            "terminal salary diagnostic replay failed"
        ) from exc
    expected_salary_raw = authority.canonical_json_bytes(salary_diagnostic)
    if raws["salary_diagnostic"] != expected_salary_raw:
        raise CorpusArtifactSourceTransportError(
            "terminal salary diagnostic differs from query replay"
        )

    try:
        completion = authority.validate_completion_bytes(
            raws["source_authority_completion"]
        )
        replayed_completion_raw = authority.verify_artifact_supported_source_authority(
            later_source_freeze_bytes=expected_source_raw,
            later_source_freeze_object=identities["later_source_freeze"],
            registration_bytes=expected_registration_raw,
            registration_object=identities["registration"],
            salary_diagnostic_bytes=expected_salary_raw,
            salary_diagnostic_object=identities["salary_diagnostic"],
            artifact_bodies=source._artifact_body_stream(  # noqa: SLF001
                source_freeze=rebuilt_source,
                storage=trace_store,
            ),
        )
    except CorpusArtifactSourceTransportError:
        raise
    except Exception as exc:
        raise CorpusArtifactSourceTransportError(
            "terminal 270-artifact authority replay failed"
        ) from exc
    if replayed_completion_raw != raws["source_authority_completion"]:
        raise CorpusArtifactSourceTransportError(
            "terminal source-authority completion differs from independent replay"
        )
    if len(receipts) != authority.EXPECTED_ARTIFACT_COUNT:
        raise CorpusArtifactSourceTransportError(
            "terminal base receipt count differs"
        )

    before_roles = (
        "prefix_claim", "registration", *source.QUERY_ROLES,
        "later_source_freeze", "salary_diagnostic",
        "source_authority_completion",
    )
    expected_before = source._inventory_rows(  # noqa: SLF001
        [identities[role] for role in before_roles]
    )
    try:
        publication = source.validate_publication_completion_bytes(
            raws["publication_completion"]
        )
        source.validate_producer_get_trace(
            publication["producer_get_trace"],
            delivered_plan_identity=contract["plan_object"],
            delivered_intent_identity=execution_intent_identity,
            plan=plan,
            artifact_receipts=receipts,
            publication_identities=identities,
        )
        source.validate_producer_query_trace(
            publication["producer_query_trace"],
            registration=registration,
            captures=captures,
        )
        rebuilt_publication = source._build_publication_completion(  # noqa: SLF001
            plan=plan,
            claim_identity=identities["prefix_claim"],
            registration_identity=identities["registration"],
            capture_identities=capture_identities,
            captures=captures,
            source_identity=identities["later_source_freeze"],
            source_freeze=rebuilt_source,
            salary_identity=identities["salary_diagnostic"],
            salary_diagnostic=salary_diagnostic,
            completion_identity=identities["source_authority_completion"],
            completion=completion,
            inventory_before_publication=expected_before,
            producer_get_trace=publication["producer_get_trace"],
            producer_query_trace=publication["producer_query_trace"],
        )
    except source.CorpusArtifactSourcePreparationError as exc:
        raise CorpusArtifactSourceTransportError(
            "terminal transport completion semantic validation failed"
        ) from exc
    if (
        source.canonical_json_bytes(rebuilt_publication)
        != raws["publication_completion"]
        or publication["plan_sha256"] != plan["plan_sha256"]
    ):
        raise CorpusArtifactSourceTransportError(
            "terminal transport completion differs from full replay"
        )
    expected_verifier_identities = [
        *(identities[role] for role in publication_uris),
        object_identity(
            plan["base_source_lock_object"], label="expected verifier base lock"
        ),
        *(
            object_identity(
                {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")},
                label=f"expected verifier artifact[{ordinal}]",
            )
            for ordinal, receipt in enumerate(receipts)
        ),
    ]
    verifier_events = trace_store.events()
    if [event["identity"] for event in verifier_events] != expected_verifier_identities:
        raise CorpusArtifactSourceTransportError(
            "terminal verifier GET trace is incomplete, extra, or reordered"
        )
    verifier_trace = _self_hash({
        "schema_version": "corpus-artifact-source-verifier-get-trace/v1",
        "events": verifier_events,
        "event_count": len(verifier_events),
        "events_sha256": canonical_sha256(verifier_events),
        "complete": True,
        "object_list_used": False,
    }, field="trace_sha256")
    return {
        "identities": identities,
        "source_authority_completion_sha256": completion["completion_sha256"],
        "publication_completion_sha256": publication[
            "publication_completion_sha256"
        ],
        "task_count": completion["task_count"],
        "artifact_count": completion["artifact_count"],
        "inventory": inventory,
        "inventory_sha256": canonical_sha256(inventory),
        "producer_get_trace_sha256": publication["producer_get_trace"][
            "trace_sha256"
        ],
        "producer_query_trace_sha256": publication["producer_query_trace"][
            "trace_sha256"
        ],
        "verifier_get_trace": verifier_trace,
    }


_TERMINAL_ACCEPTANCE_KEYS: Final = frozenset({
    "schema_version", "accepted_at_utc", "transport_contract", "plan_object",
    "runtime_iam_object", "launch_ledger", "execution_binding", "run_id",
    "job", "execution", "execution_names_terminal", "execution_census_sha256",
    "scheduler_census_sha256", "all_regions_scheduler_census_complete",
    "source_publications", "source_inventory", "source_inventory_sha256",
    "source_authority_completion_sha256", "publication_completion_sha256",
    "producer_get_trace_sha256", "producer_query_trace_sha256",
    "verifier_get_trace",
    "task_count", "artifact_count", "exact_nine_objects_reopened",
    "artifact_replay_count", "independent_semantic_replay", "accepted",
    "partial_result", "one_execution", "attempt_zero", "retry_count",
    "automatic_retry_licensed", "uses_realized_outcomes",
    "historical_scoring_licensed", "production_change_licensed",
    "terminal_acceptance_sha256",
})


def _validate_terminal_acceptance(
    value: object,
    *,
    contract: Mapping[str, object],
    contract_identity: Mapping[str, object],
    launch_identity: Mapping[str, object],
    binding_identity: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(value, label="source terminal acceptance"))
    _exact_keys(item, _TERMINAL_ACCEPTANCE_KEYS, label="source terminal acceptance")
    _validate_self_hash(
        item, field="terminal_acceptance_sha256", label="terminal acceptance"
    )
    if (
        item["schema_version"] != TERMINAL_ACCEPTANCE_SCHEMA
        or item["transport_contract"] != contract_identity
        or item["plan_object"] != contract["plan_object"]
        or item["runtime_iam_object"] != contract["runtime_iam_object"]
        or item["launch_ledger"] != launch_identity
        or item["execution_binding"] != binding_identity
        or item["run_id"] != contract["run_id"]
        or item["job"] != contract["job"]
        or item["task_count"] != authority.EXPECTED_TASK_COUNT
        or item["artifact_count"] != authority.EXPECTED_ARTIFACT_COUNT
        or item["exact_nine_objects_reopened"] is not True
        or item["artifact_replay_count"] != authority.EXPECTED_ARTIFACT_COUNT
        or item["independent_semantic_replay"] is not True
        or item["accepted"] is not True
        or item["partial_result"] is not False
        or item["one_execution"] is not True
        or item["attempt_zero"] is not True
        or item["retry_count"] != 0
        or item["automatic_retry_licensed"] is not False
        or item["uses_realized_outcomes"] is not False
        or item["historical_scoring_licensed"] is not False
        or item["production_change_licensed"] is not False
        or item["all_regions_scheduler_census_complete"] is not True
    ):
        raise CorpusArtifactSourceTransportError(
            "terminal acceptance authority differs"
        )
    _timestamp(item["accepted_at_utc"], label="terminal acceptance timestamp")
    _sha(item["execution_census_sha256"], label="execution census SHA")
    _sha(item["scheduler_census_sha256"], label="scheduler census SHA")
    _sha(item["source_inventory_sha256"], label="source inventory SHA")
    _sha(
        item["source_authority_completion_sha256"],
        label="source completion SHA",
    )
    _sha(
        item["publication_completion_sha256"],
        label="publication completion SHA",
    )
    _sha(item["producer_get_trace_sha256"], label="producer GET trace SHA")
    _sha(item["producer_query_trace_sha256"], label="producer query trace SHA")
    verifier_trace = dict(_mapping(
        item["verifier_get_trace"], label="verifier GET trace"
    ))
    _exact_keys(
        verifier_trace,
        frozenset({
            "schema_version", "events", "event_count", "events_sha256",
            "complete", "object_list_used", "trace_sha256",
        }),
        label="verifier GET trace",
    )
    _validate_self_hash(
        verifier_trace, field="trace_sha256", label="verifier GET trace"
    )
    verifier_events = list(_sequence(
        verifier_trace["events"], label="verifier GET trace events"
    ))
    if (
        verifier_trace["schema_version"]
        != "corpus-artifact-source-verifier-get-trace/v1"
        or verifier_trace["event_count"]
        != authority.EXPECTED_ARTIFACT_COUNT + 10
        or len(verifier_events) != verifier_trace["event_count"]
        or verifier_trace["events_sha256"] != canonical_sha256(verifier_events)
        or verifier_trace["complete"] is not True
        or verifier_trace["object_list_used"] is not False
        or any(
            not isinstance(event, Mapping) or event.get("ordinal") != ordinal
            for ordinal, event in enumerate(verifier_events)
        )
    ):
        raise CorpusArtifactSourceTransportError("verifier GET trace differs")
    publications = _mapping(
        item["source_publications"], label="accepted source publications"
    )
    if set(publications) != set(source._publication_uris(  # noqa: SLF001
        str(contract["source_output_prefix"])
    )):
        raise CorpusArtifactSourceTransportError(
            "accepted source publication roles differ"
        )
    normalized_publications = {
        role: object_identity(identity, label=f"accepted {role}")
        for role, identity in publications.items()
    }
    inventory = _normalized_inventory(
        item["source_inventory"], label="accepted source inventory"
    )
    if (
        inventory != _identity_rows(list(normalized_publications.values()))
        or item["source_inventory_sha256"] != canonical_sha256(inventory)
    ):
        raise CorpusArtifactSourceTransportError(
            "accepted source inventory differs"
        )
    item["source_publications"] = normalized_publications
    item["source_inventory"] = inventory
    return item


def accept_terminal(
    *,
    storage: ObjectStore,
    contract_identity: object,
    terminal_execution_metadata: object,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    accepted_at_utc: str,
    execute: bool,
    environ: Mapping[str, str],
) -> dict[str, object]:
    require_execute_gate(execute=execute, environ=environ)
    retained_contract_identity = object_identity(
        contract_identity, label="transport contract identity"
    )
    contract, plan, _raw = _reopen_contract(storage, retained_contract_identity)
    _ledger, ledger_identity = _load_launch_ledger(
        storage,
        contract=contract,
        contract_identity=retained_contract_identity,
    )
    binding_value, binding_identity, _binding_raw = _resolve_json(
        storage,
        str(contract["governance_uris"]["execution_binding"]),
        label="execution binding",
    )
    binding = _validate_execution_binding(
        binding_value,
        contract=contract,
        contract_identity=retained_contract_identity,
        launch_identity=ledger_identity,
    )
    validate_parked_job(
        parked_job,
        expected_job=_mapping(contract["job"], label="contract job"),
        build=_mapping(contract["build"], label="contract build"),
        service_account=str(contract["service_account"]),
    )
    validate_scheduler_census(
        schedulers,
        job_name=str(contract["job"]["name"]),
        all_regions_complete=all_regions_complete,
    )
    execution_id, terminal_names = _one_new_execution(
        contract=contract, executions=executions
    )
    _require_all_terminal(executions, label="terminal execution census")
    execution = validate_execution(
        terminal_execution_metadata,
        contract=contract,
        execution_intent_identity=ledger_identity,
        require_terminal_success=True,
    )
    if (
        execution["execution_id"] != execution_id
        or execution["execution_id"] != binding["execution_id"]
        or execution["execution_name"] != binding["execution_name"]
        or execution["execution_uid"] != binding["execution_uid"]
        or execution["spec_sha256"] != binding["execution_spec_sha256"]
        or terminal_names != binding["execution_names_after"]
    ):
        raise CorpusArtifactSourceTransportError(
            "terminal execution differs from bound sole execution"
        )
    base_delivery = [
        contract["plan_object"], contract["runtime_iam_object"],
        retained_contract_identity, ledger_identity, binding_identity,
    ]
    existing = _delivery_inventory_with_optional(
        storage,
        contract=contract,
        contract_identity=retained_contract_identity,
        required=base_delivery,
        optional_uri=str(contract["governance_uris"]["terminal_acceptance"]),
        label="preacceptance delivery inventory",
    )
    source_terminal = _source_terminal_publications(
        storage,
        contract=contract,
        plan=plan,
        execution_intent_identity=ledger_identity,
    )
    canonical_executions = _canonical_execution_census(executions)
    canonical_schedulers = _canonical_scheduler_census(schedulers)
    acceptance = _self_hash({
        "schema_version": TERMINAL_ACCEPTANCE_SCHEMA,
        "accepted_at_utc": _timestamp(
            accepted_at_utc, label="terminal acceptance timestamp"
        ),
        "transport_contract": retained_contract_identity,
        "plan_object": contract["plan_object"],
        "runtime_iam_object": contract["runtime_iam_object"],
        "launch_ledger": ledger_identity,
        "execution_binding": binding_identity,
        "run_id": contract["run_id"],
        "job": contract["job"],
        "execution": execution,
        "execution_names_terminal": terminal_names,
        "execution_census_sha256": canonical_sha256(canonical_executions),
        "scheduler_census_sha256": canonical_sha256(canonical_schedulers),
        "all_regions_scheduler_census_complete": True,
        "source_publications": source_terminal["identities"],
        "source_inventory": source_terminal["inventory"],
        "source_inventory_sha256": source_terminal["inventory_sha256"],
        "source_authority_completion_sha256": source_terminal[
            "source_authority_completion_sha256"
        ],
        "publication_completion_sha256": source_terminal[
            "publication_completion_sha256"
        ],
        "producer_get_trace_sha256": source_terminal[
            "producer_get_trace_sha256"
        ],
        "producer_query_trace_sha256": source_terminal[
            "producer_query_trace_sha256"
        ],
        "verifier_get_trace": source_terminal["verifier_get_trace"],
        "task_count": source_terminal["task_count"],
        "artifact_count": source_terminal["artifact_count"],
        "exact_nine_objects_reopened": True,
        "artifact_replay_count": authority.EXPECTED_ARTIFACT_COUNT,
        "independent_semantic_replay": True,
        "accepted": True,
        "partial_result": False,
        "one_execution": True,
        "attempt_zero": True,
        "retry_count": 0,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }, field="terminal_acceptance_sha256")
    acceptance_raw = canonical_json_bytes(acceptance)
    acceptance_identity, created = _publish_consumption(
        storage,
        uri=str(contract["governance_uris"]["terminal_acceptance"]),
        raw=acceptance_raw,
    )
    if existing is not None and existing != acceptance_identity:
        raise CorpusArtifactSourceTransportError(
            "existing terminal acceptance identity differs"
        )
    _validate_terminal_acceptance(
        acceptance,
        contract=contract,
        contract_identity=retained_contract_identity,
        launch_identity=ledger_identity,
        binding_identity=binding_identity,
    )
    _require_exact_inventory(
        storage,
        prefix=str(contract["delivery_prefix"]),
        identities=[*base_delivery, acceptance_identity],
        label="terminal delivery inventory",
    )
    return {
        "schema_version": "corpus-artifact-source-accepted-result/v1",
        "terminal_acceptance": acceptance_identity,
        "accepted": True,
        "partial_result": False,
        "source_authority_completion": source_terminal["identities"][
            "source_authority_completion"
        ],
        "publication_completion": source_terminal["identities"][
            "publication_completion"
        ],
        "created": created,
    }


def _load_json_file(path: Path, *, label: str) -> object:
    if path.is_symlink() or not path.is_file():
        raise CorpusArtifactSourceTransportError(f"{label} file is unsafe")
    return strict_json_bytes(path.read_bytes(), label=label)


def _load_raw_file(path: Path, *, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise CorpusArtifactSourceTransportError(f"{label} file is unsafe")
    raw = path.read_bytes()
    strict_json_bytes(raw, label=label)
    return raw


def _load_bytes_file(path: Path, *, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise CorpusArtifactSourceTransportError(f"{label} file is unsafe")
    raw = path.read_bytes()
    if not raw:
        raise CorpusArtifactSourceTransportError(f"{label} file is empty")
    return raw


def _write_once(path: Path, raw: bytes) -> None:
    if path.is_symlink():
        raise CorpusArtifactSourceTransportError("output path is a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError as exc:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise CorpusArtifactSourceTransportError(
                f"immutable local output differs: {path}"
            ) from exc


def _add_contract_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--contract-uri", required=True)
    command.add_argument("--contract-generation", required=True)
    command.add_argument("--contract-sha256", required=True)
    command.add_argument("--contract-bytes", type=int, required=True)


def _contract_identity_from_args(args: argparse.Namespace) -> dict[str, object]:
    return object_identity({
        "uri": args.contract_uri,
        "generation": args.contract_generation,
        "sha256": args.contract_sha256,
        "bytes": args.contract_bytes,
    }, label="CLI contract identity")


def _add_census_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--job-file", type=Path, required=True)
    command.add_argument("--executions-file", type=Path, required=True)
    command.add_argument("--schedulers-file", type=Path, required=True)
    command.add_argument("--all-regions-complete", action="store_true")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("parked", help="client-free default-off command")
    validate = commands.add_parser("validate-only", help="client-free plan validation")
    validate.add_argument("--plan-file", type=Path, required=True)
    validate_build = commands.add_parser(
        "validate-build", help="client-free immutable build validation"
    )
    validate_build.add_argument("--build-metadata-file", type=Path, required=True)
    validate_build.add_argument("--build-id", required=True)
    validate_build.add_argument("--code-sha", required=True)
    validate_build.add_argument("--image", required=True)
    build_iam = commands.add_parser(
        "build-runtime-iam-evidence",
        help="derive v3 IAM evidence from retained policy bodies without clients",
    )
    build_iam.add_argument("--policy-capture-file", type=Path, required=True)
    build_iam.add_argument("--plan-file", type=Path, required=True)
    build_iam.add_argument("--base-source-lock-file", type=Path, required=True)
    build_iam.add_argument("--delivery-prefix", required=True)
    build_iam.add_argument("--service-account", required=True)
    build_iam.add_argument("--output", type=Path, required=True)
    validate_job = commands.add_parser(
        "validate-parked-job", help="client-free parked-job validation"
    )
    validate_job.add_argument("--job-file", type=Path, required=True)
    validate_job.add_argument("--build-metadata-file", type=Path, required=True)
    validate_job.add_argument("--build-id", required=True)
    validate_job.add_argument("--code-sha", required=True)
    validate_job.add_argument("--image", required=True)
    validate_job.add_argument("--service-account", required=True)

    configure = commands.add_parser(
        "configure", help="publish plan/IAM/contract after parked-job update"
    )
    configure.add_argument("--plan-file", type=Path, required=True)
    configure.add_argument("--runtime-iam-file", type=Path, required=True)
    configure.add_argument("--delivery-prefix", required=True)
    configure.add_argument("--build-metadata-file", type=Path, required=True)
    configure.add_argument("--build-id", required=True)
    configure.add_argument("--code-sha", required=True)
    configure.add_argument("--image", required=True)
    configure.add_argument("--service-account", required=True)
    configure.add_argument("--job-before-file", type=Path, required=True)
    configure.add_argument("--job-after-file", type=Path, required=True)
    configure.add_argument("--executions-before-file", type=Path, required=True)
    configure.add_argument("--executions-after-file", type=Path, required=True)
    configure.add_argument("--schedulers-before-file", type=Path, required=True)
    configure.add_argument("--schedulers-after-file", type=Path, required=True)
    configure.add_argument("--all-regions-complete", action="store_true")
    configure.add_argument("--created-at-utc", required=True)
    configure.add_argument("--execute", action="store_true")

    launch = commands.add_parser("consume-launch", help="consume one launch")
    _add_contract_arguments(launch)
    _add_census_arguments(launch)
    launch.add_argument("--created-at-utc", required=True)
    launch.add_argument("--execute", action="store_true")

    recover = commands.add_parser("recover-name", help="census-only recovery")
    _add_contract_arguments(recover)
    _add_census_arguments(recover)
    recover.add_argument("--execute", action="store_true")

    bind = commands.add_parser("bind-execution", help="bind sole new execution")
    _add_contract_arguments(bind)
    _add_census_arguments(bind)
    bind.add_argument("--execution-metadata-file", type=Path, required=True)
    bind.add_argument("--created-at-utc", required=True)
    bind.add_argument("--execute", action="store_true")

    accept = commands.add_parser(
        "accept-terminal", help="replay and accept exact terminal publication"
    )
    _add_contract_arguments(accept)
    _add_census_arguments(accept)
    accept.add_argument("--execution-metadata-file", type=Path, required=True)
    accept.add_argument("--accepted-at-utc", required=True)
    accept.add_argument("--execute", action="store_true")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "parked":
        print(
            "CORPUS_ARTIFACT_SOURCE_TRANSPORT_PARKED "
            "default_off=true client_constructed=false"
        )
        return 0
    if args.command == "validate-only":
        plan = _parse_plan(_load_raw_file(args.plan_file, label="source plan"))
        print(canonical_json_bytes({
            "schema_version": "corpus-artifact-source-plan-validation/v1",
            "plan_sha256": plan["plan_sha256"],
            "task_count": plan["task_count"],
            "artifact_count": plan["artifact_count"],
            "client_constructed": False,
        }).decode("utf-8"))
        return 0
    if args.command == "validate-build":
        build = validate_build_metadata(
            _load_json_file(args.build_metadata_file, label="build metadata"),
            build_id=args.build_id,
            code_sha=args.code_sha,
            image=args.image,
        )
        print(canonical_json_bytes({
            "schema_version": "corpus-artifact-source-build-validation/v1",
            "build": build,
            "client_constructed": False,
        }).decode("utf-8"))
        return 0
    if args.command == "build-runtime-iam-evidence":
        result = build_runtime_iam_evidence(
            policy_capture=_load_json_file(
                args.policy_capture_file, label="runtime IAM policy capture"
            ),
            plan_raw=_load_raw_file(args.plan_file, label="source plan"),
            base_source_lock_raw=_load_bytes_file(
                args.base_source_lock_file, label="base source lock"
            ),
            delivery_prefix=args.delivery_prefix,
            service_account=args.service_account,
        )
        raw = canonical_json_bytes(result)
        _write_once(args.output, raw)
        print(canonical_json_bytes({
            "schema_version": "corpus-artifact-source-runtime-iam-build/v1",
            "output": str(args.output),
            "iam_evidence_sha256": result["iam_evidence_sha256"],
            "client_constructed": False,
        }).decode("utf-8"))
        return 0
    if args.command == "validate-parked-job":
        build = validate_build_metadata(
            _load_json_file(args.build_metadata_file, label="build metadata"),
            build_id=args.build_id,
            code_sha=args.code_sha,
            image=args.image,
        )
        job = _load_json_file(args.job_file, label="parked job")
        identity = job_identity(job, label="parked job")
        validate_parked_job(
            job,
            expected_job=identity,
            build=build,
            service_account=args.service_account,
        )
        print(canonical_json_bytes({
            "schema_version": "corpus-artifact-source-parked-validation/v1",
            "job": identity,
            "client_constructed": False,
        }).decode("utf-8"))
        return 0

    # Every mutating branch gates before the GCS client is constructed.
    require_execute_gate(execute=args.execute, environ=os.environ)
    storage = GenerationPinnedStorage(
        execute=True, environ=os.environ, project=PROJECT
    )
    if args.command == "configure":
        result = configure_transport(
            plan_raw=_load_raw_file(args.plan_file, label="source plan"),
            runtime_iam=_load_json_file(
                args.runtime_iam_file, label="runtime IAM evidence"
            ),
            delivery_prefix=args.delivery_prefix,
            build_metadata=_load_json_file(
                args.build_metadata_file, label="build metadata"
            ),
            build_id=args.build_id,
            code_sha=args.code_sha,
            image=args.image,
            service_account=args.service_account,
            job_before=_load_json_file(args.job_before_file, label="job before"),
            job_after=_load_json_file(args.job_after_file, label="job after"),
            executions_before=_load_json_file(
                args.executions_before_file, label="executions before"
            ),
            executions_after=_load_json_file(
                args.executions_after_file, label="executions after"
            ),
            schedulers_before=_load_json_file(
                args.schedulers_before_file, label="schedulers before"
            ),
            schedulers_after=_load_json_file(
                args.schedulers_after_file, label="schedulers after"
            ),
            all_regions_complete=args.all_regions_complete,
            created_at_utc=args.created_at_utc,
            storage=storage,
            execute=True,
            environ=os.environ,
        )
    else:
        contract_identity = _contract_identity_from_args(args)
        if args.command == "recover-name":
            result = recover_execution_name(
                storage=storage,
                contract_identity=contract_identity,
                parked_job=_load_json_file(args.job_file, label="parked job"),
                executions=_load_json_file(
                    args.executions_file, label="execution census"
                ),
                schedulers=_load_json_file(
                    args.schedulers_file, label="scheduler census"
                ),
                all_regions_complete=args.all_regions_complete,
                execute=True,
                environ=os.environ,
            )
        else:
            parked_job = _load_json_file(args.job_file, label="parked job")
            executions = _load_json_file(
                args.executions_file, label="execution census"
            )
            schedulers = _load_json_file(
                args.schedulers_file, label="scheduler census"
            )
            if args.command == "consume-launch":
                result = consume_launch(
                    storage=storage,
                    contract_identity=contract_identity,
                    parked_job=parked_job,
                    executions=executions,
                    schedulers=schedulers,
                    all_regions_complete=args.all_regions_complete,
                    created_at_utc=args.created_at_utc,
                    execute=True,
                    environ=os.environ,
                )
            elif args.command == "bind-execution":
                result = bind_execution(
                    storage=storage,
                    contract_identity=contract_identity,
                    execution_metadata=_load_json_file(
                        args.execution_metadata_file,
                        label="execution metadata",
                    ),
                    parked_job=parked_job,
                    executions=executions,
                    schedulers=schedulers,
                    all_regions_complete=args.all_regions_complete,
                    created_at_utc=args.created_at_utc,
                    execute=True,
                    environ=os.environ,
                )
            elif args.command == "accept-terminal":
                result = accept_terminal(
                    storage=storage,
                    contract_identity=contract_identity,
                    terminal_execution_metadata=_load_json_file(
                        args.execution_metadata_file,
                        label="terminal execution metadata",
                    ),
                    parked_job=parked_job,
                    executions=executions,
                    schedulers=schedulers,
                    all_regions_complete=args.all_regions_complete,
                    accepted_at_utc=args.accepted_at_utc,
                    execute=True,
                    environ=os.environ,
                )
            else:
                raise CorpusArtifactSourceTransportError("command differs")
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


__all__ = [
    "CorpusArtifactSourceTransportError",
    "ENABLE_ENV",
    "accept_terminal",
    "bind_execution",
    "canonical_json_bytes",
    "configure_transport",
    "consume_launch",
    "recover_execution_name",
    "validate_build_metadata",
    "validate_runtime_iam_evidence",
    "validate_transport_contract",
]


if __name__ == "__main__":
    raise SystemExit(main())
