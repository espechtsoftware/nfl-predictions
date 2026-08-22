"""Governed transport for the dedicated corpus-research Neo4j projection.

The scientific receipts and large numerical bodies remain authoritative in
generation-pinned GCS objects.  This module adds the operational boundary that
the storage-neutral graph planner intentionally omits:

* exact-generation object GETs without bucket LIST;
* a dedicated deployment/database/TLS/principal binding;
* complete accepted retrieval and 54-task parametric evidence traversal;
* mandatory compact retrieval analytics;
* idempotent per-task graph-load receipts and read-only recovery; and
* a terminal graph census before cross-slate queries are considered complete.

No function in this module changes production policy, reads realized outcomes,
or stores world matrices in Neo4j.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import os
import re
from typing import Any, Final, Protocol
from urllib.parse import urlparse

from nfl_dfs.research import corpus_expansion_build as expansion_build
from nfl_dfs.research.corpus_neo4j_extensions import (
    PARAMETRIC_NAMESPACE,
    POPULATION_NAMESPACE,
    RETRIEVAL_NAMESPACE,
    append_parametric_batch,
    append_retrieval_analytics,
)
from nfl_dfs.research.corpus_retrieval_neo4j import (
    CorpusRetrievalNeo4jError,
    Neo4jLoadPlan,
    SCHEMA_STATEMENTS,
    apply_load_plan,
    build_load_plan,
    build_load_result_receipt,
    canonical_json_bytes,
    canonical_sha256,
    parse_canonical_json_bytes,
)


DEPLOYMENT_SCHEMA: Final = "corpus-neo4j-dedicated-deployment/v2"
POPULATION_DEPLOYMENT_SCHEMA: Final = "corpus-neo4j-dedicated-deployment/v3"
LOAD_MANIFEST_SCHEMA: Final = "corpus-neo4j-governed-load-manifest/v2"
BOOTSTRAP_RECEIPT_SCHEMA: Final = "corpus-neo4j-schema-bootstrap/v1"
LOAD_RECEIPT_SCHEMA: Final = "corpus-neo4j-governed-load-result/v2"
SUITE_RECEIPT_SCHEMA: Final = "corpus-neo4j-suite-terminal/v2"
QUERY_SMOKE_SCHEMA: Final = "corpus-neo4j-query-smoke/v2"
LAUNCH_INTENT_SCHEMA: Final = "corpus-neo4j-launch-intent/v1"
EXECUTION_BINDING_SCHEMA: Final = "corpus-neo4j-execution-binding/v1"
EXECUTION_TERMINAL_SCHEMA: Final = "corpus-neo4j-execution-terminal/v1"

TRANSPORT_ENABLE_ENV: Final = "CORPUS_NEO4J_TRANSPORT_ENABLED"
MANIFEST_PUBLICATION_ENABLE_ENV: Final = (
    "CORPUS_NEO4J_MANIFEST_PUBLICATION_ENABLED"
)
URI_ENV: Final = "CORPUS_RETRIEVAL_NEO4J_URI"
DATABASE_ENV: Final = "CORPUS_RETRIEVAL_NEO4J_DATABASE"
USERNAME_ENV: Final = "CORPUS_RETRIEVAL_NEO4J_USERNAME"
PASSWORD_ENV: Final = "CORPUS_RETRIEVAL_NEO4J_PASSWORD"
PROVIDER_RESOURCE_ENV: Final = "CORPUS_RETRIEVAL_NEO4J_PROVIDER_RESOURCE_ID"
USERNAME_SECRET_VERSION_ENV: Final = (
    "CORPUS_RETRIEVAL_NEO4J_USERNAME_SECRET_VERSION"
)
PASSWORD_SECRET_VERSION_ENV: Final = (
    "CORPUS_RETRIEVAL_NEO4J_PASSWORD_SECRET_VERSION"
)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_GENERATION = re.compile(r"^[1-9][0-9]*$")
_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SECRET_VERSION = re.compile(
    r"^projects/[a-z][a-z0-9-]{4,62}/secrets/"
    r"[A-Za-z0-9_-]{1,255}/versions/[1-9][0-9]*$"
)

_PRINCIPAL_ROLES: Final = ("bootstrap", "writer", "reader")
_TLS_SCHEMES: Final = ("neo4j+s", "bolt+s")
STRATEGY_REGISTRY_NAMESPACE: Final = "corpus-strategy-registry"
REALIZED_OUTCOME_NAMESPACE: Final = "corpus-realized-outcomes"
_MANDATORY_ANALYTIC_ROLES: Final = (
    "enrichment-discovery",
    "enrichment-all-worlds",
    "redundancy-topk",
)
_TASK_ACCEPTANCE_SCHEMA: Final = "corpus-parametric-task-acceptance/v1"
_BATCH_ACCEPTANCE_SCHEMA: Final = "corpus-parametric-batch-acceptance/v1"
_BUILD = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_JOB = re.compile(r"^[a-z][a-z0-9-]{0,61}[a-z0-9]$")
_EXECUTION = re.compile(r"^[a-z][a-z0-9-]{0,61}[a-z0-9]$")
EXPECTED_CODE_REPOSITORY: Final = expansion_build.EXPECTED_CODE_REPOSITORY
EXPECTED_BUILD_STEPS: Final = {
    step_id: (builder, entrypoint)
    for step_id, builder, entrypoint in expansion_build.EXPECTED_STEP_SPECS
}
REQUIRED_BUILD_COMMANDS: Final = (
    *expansion_build.FOCUSED_TEST_COMMANDS,
    *expansion_build.SOURCE_SMOKE_COMMANDS,
    *expansion_build.PARAMETRIC_SMOKE_COMMANDS,
    *expansion_build.NEO4J_SMOKE_COMMANDS,
)

_ROLE_BY_OPERATION: Final = {
    "bootstrap-schema": "bootstrap",
    "load-task0": "writer",
    "load-parametric-task": "writer",
    "load-suite": "writer",
    "load-strategy-registry": "writer",
    "recover-task0-receipt": "reader",
    "recover-parametric-receipt": "reader",
    "recover-strategy-registry-receipt": "reader",
    "finish-suite": "reader",
    "query-smoke": "reader",
    "query-strategy-registry": "reader",
}


class CorpusNeo4jTransportError(RuntimeError):
    """The governed graph transport failed closed."""


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


class ExactObjectStore(Protocol):
    """Exact-name storage API.  It deliberately has no LIST operation."""

    def read_exact(self, identity: ObjectIdentity) -> bytes: ...

    def resolve_optional(self, uri: str) -> tuple[ObjectIdentity, bytes] | None: ...

    def publish_create_once(self, uri: str, raw: bytes) -> ObjectIdentity: ...


class GraphBackend(Protocol):
    """Small injected graph boundary used by live code and offline fakes."""

    database: str

    def component(self) -> Mapping[str, object]: ...

    def census(self) -> Mapping[str, object]: ...

    def bootstrap_schema(self, statements: Sequence[str]) -> None: ...

    def apply(self, plan: Neo4jLoadPlan) -> Mapping[str, object]: ...

    def verify(self, plan: Neo4jLoadPlan) -> Mapping[str, object]: ...

    def suite_census(
        self, *, batch_id: str, registry_id: str,
    ) -> Mapping[str, object]: ...

    def query_smoke(self, *, run_id: str, task_id: str) -> Mapping[str, object]: ...

    def run_read_only_query(
        self, database: str, cypher: str, parameters: Mapping[str, object],
    ) -> Sequence[Mapping[str, object]]: ...


@dataclass(frozen=True, slots=True)
class ValidatedLoadBundle:
    manifest: dict[str, object]
    manifest_identity: ObjectIdentity | None
    deployment: dict[str, object]
    deployment_identity: ObjectIdentity
    retrieval_plan: Neo4jLoadPlan
    parametric_plans: tuple[Neo4jLoadPlan, ...]
    strategy_registry_bundle: Any


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusNeo4jTransportError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise CorpusNeo4jTransportError(f"{label} must be an array")
    return value


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CorpusNeo4jTransportError(f"{label} must be a nonempty string")
    return value


def _cloud_run_generation(value: object, *, label: str) -> str:
    if type(value) is not int or value < 1:
        raise CorpusNeo4jTransportError(
            f"{label} must be a positive JSON integer"
        )
    return str(value)


def _blob_generation(value: object, *, label: str) -> str:
    """Normalize one loaded google-cloud-storage generation for receipts."""
    if type(value) is not int or value < 1:
        raise CorpusNeo4jTransportError(
            f"{label} must be a positive SDK integer"
        )
    return str(value)


def object_identity(value: object, *, label: str) -> ObjectIdentity:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        raise CorpusNeo4jTransportError(f"{label} schema differs")
    uri = _string(item["uri"], label=f"{label}.uri")
    generation = _string(item["generation"], label=f"{label}.generation")
    digest = _string(item["sha256"], label=f"{label}.sha256")
    size = item["bytes"]
    if (
        not uri.startswith("gs://")
        or uri.endswith("/")
        or ".." in uri.split("/")
        or _GENERATION.fullmatch(generation) is None
        or _SHA.fullmatch(digest) is None
        or type(size) is not int
        or size < 1
    ):
        raise CorpusNeo4jTransportError(f"{label} differs")
    return ObjectIdentity(uri, generation, digest, size)


def _bind_raw(raw: bytes, identity: ObjectIdentity, *, label: str) -> bytes:
    if type(raw) is not bytes:
        raise CorpusNeo4jTransportError(f"{label} must be bytes")
    if len(raw) != identity.bytes or sha256(raw).hexdigest() != identity.sha256:
        raise CorpusNeo4jTransportError(f"{label} content identity differs")
    return raw


def _read_exact(
    storage: ExactObjectStore, value: object, *, label: str,
) -> tuple[ObjectIdentity, bytes]:
    identity = object_identity(value, label=f"{label} identity")
    raw = storage.read_exact(identity)
    return identity, _bind_raw(raw, identity, label=label)


def _json(raw: bytes, *, label: str) -> dict[str, object]:
    value = parse_canonical_json_bytes(raw, label=label)
    return dict(_mapping(value, label=label))


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> str:
    digest = value.get(field)
    if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
        raise CorpusNeo4jTransportError(f"{label}.{field} differs")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256(body) != digest:
        raise CorpusNeo4jTransportError(f"{label} self-hash differs")
    return digest


def _with_self_hash(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = canonical_sha256(result)
    return result


def _timestamp(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _UTC.fullmatch(text) is None:
        raise CorpusNeo4jTransportError(f"{label} must be second-precision UTC")
    return text


def _gcs_prefix(value: object, *, label: str) -> str:
    prefix = _string(value, label=label)
    if (
        not prefix.startswith("gs://")
        or not prefix.endswith("/")
        or ".." in prefix.split("/")
    ):
        raise CorpusNeo4jTransportError(f"{label} must be a GCS prefix")
    return prefix


def require_execute_gate(
    *, execute: bool, environ: Mapping[str, str], publication_only: bool = False,
) -> None:
    env_name = (
        MANIFEST_PUBLICATION_ENABLE_ENV if publication_only
        else TRANSPORT_ENABLE_ENV
    )
    if execute is not True or environ.get(env_name) != "1":
        raise CorpusNeo4jTransportError(
            f"live execution requires literal --execute and {env_name}=1"
        )


def validate_build_metadata(
    value: object, *, build_id: str, code_sha: str, image: str,
) -> dict[str, str]:
    """Require direct-Git provenance and the committed graph smoke surface."""
    try:
        retained = expansion_build.validate_build_metadata(
            value, build_id=build_id, code_sha=code_sha, image=image
        )
    except expansion_build.CorpusExpansionBuildError as exc:
        raise CorpusNeo4jTransportError(str(exc)) from exc
    return {
        key: retained[key]
        for key in ("build_id", "code_repository", "code_sha", "image")
    }


def _task_spec(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        task = value["spec"]["template"]["spec"]["template"]["spec"]  # type: ignore[index]
    except (KeyError, TypeError):
        try:
            task = value["spec"]["template"]["spec"]  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise CorpusNeo4jTransportError("Cloud Run task spec differs") from exc
    return _mapping(task, label="Cloud Run task spec")


def _outer_spec(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        return _mapping(
            value["spec"]["template"]["spec"],  # type: ignore[index]
            label="Cloud Run outer spec",
        )
    except (KeyError, TypeError) as exc:
        raise CorpusNeo4jTransportError("Cloud Run outer spec differs") from exc


def _job_identity(
    value: object, *, expected_name: str, expected_uid: str,
) -> dict[str, str]:
    item = _mapping(value, label="reused job")
    metadata = _mapping(item.get("metadata"), label="reused job metadata")
    status = _mapping(item.get("status"), label="reused job status")
    name = _string(metadata.get("name"), label="reused job name").rsplit("/", 1)[-1]
    uid = _string(metadata.get("uid"), label="reused job UID")
    generation = _cloud_run_generation(
        metadata.get("generation"), label="reused job generation"
    )
    observed = _cloud_run_generation(
        status.get("observedGeneration"), label="reused job observed generation"
    )
    conditions = status.get("conditions")
    if (
        _JOB.fullmatch(expected_name) is None
        or name != expected_name
        or uid != expected_uid
        or observed != generation
        or type(conditions) is not list
        or not any(
            isinstance(row, Mapping)
            and row.get("type") == "Ready"
            and row.get("status") == "True"
            for row in conditions
        )
    ):
        raise CorpusNeo4jTransportError(
            "reused job does not match the externally frozen Ready name/UID"
        )
    return {
        "name": name,
        "uid": uid,
        "generation": generation,
        "observed_generation": observed,
        "resource_version": _string(
            metadata.get("resourceVersion"), label="reused job resource version"
        ),
        "spec_sha256": canonical_sha256(
            _mapping(item.get("spec"), label="reused job spec")
        ),
    }


def _validate_template_metadata(
    job: Mapping[str, object], *, require_governed_rest: bool = False,
) -> None:
    try:
        template = _mapping(
            job["spec"]["template"],  # type: ignore[index]
            label="job template",
        )
    except (KeyError, TypeError) as exc:
        raise CorpusNeo4jTransportError("job template differs") from exc
    metadata = _mapping(template.get("metadata"), label="job template metadata")
    if set(metadata) != {"annotations", "labels"}:
        raise CorpusNeo4jTransportError("job template metadata fields differ")
    annotations = _mapping(
        metadata["annotations"], label="job template annotations"
    )
    allowed_annotations = {
        "run.googleapis.com/client-name",
        "run.googleapis.com/client-version",
        "run.googleapis.com/execution-environment",
    }
    expected_client = (
        "corpus-neo4j-governed-rest" if require_governed_rest else None
    )
    client_name = annotations.get("run.googleapis.com/client-name")
    if (
        set(annotations) != allowed_annotations
        or (
            client_name != expected_client
            if expected_client is not None
            else client_name not in {"gcloud", "corpus-neo4j-governed-rest"}
        )
        or annotations.get("run.googleapis.com/execution-environment") != "gen2"
        or re.fullmatch(
            r"[0-9]+(?:\.[0-9]+){2}",
            str(annotations.get("run.googleapis.com/client-version", "")),
        ) is None
    ):
        raise CorpusNeo4jTransportError(
            "unexpected job template annotations or execution environment"
        )
    labels = _mapping(metadata["labels"], label="job template labels")
    if set(labels) != {"client.knative.dev/nonce"} or not labels.get(
        "client.knative.dev/nonce"
    ):
        raise CorpusNeo4jTransportError("unexpected job template labels")


def _reject_inherited_attachments(job: Mapping[str, object]) -> None:
    _validate_template_metadata(job)
    outer = _outer_spec(job)
    task = _task_spec(job)
    containers = _sequence(task.get("containers"), label="job containers")
    if len(containers) != 1:
        raise CorpusNeo4jTransportError("reused job must have exactly one container")
    container = _mapping(containers[0], label="job container")
    forbidden_outer = {
        "vpcAccess", "networkInterfaces", "cloudSqlInstances", "volumes",
        "nodeSelector", "encryptionKey", "sessionAffinity",
    }
    forbidden_task = {
        "vpcAccess", "networkInterfaces", "cloudSqlInstances", "volumes",
        "nodeSelector", "encryptionKey",
    }
    forbidden_container = {
        "volumeMounts", "startupProbe", "livenessProbe", "ports",
        "dependsOn", "baseImageUri",
    }
    if set(outer).intersection(forbidden_outer) or set(task).intersection(forbidden_task):
        raise CorpusNeo4jTransportError("reused job has inherited task attachments")
    if set(container).intersection(forbidden_container):
        raise CorpusNeo4jTransportError("reused job has inherited container attachments")
    if container.get("workingDir") not in {None, ""}:
        raise CorpusNeo4jTransportError("reused job has an inherited working directory")
    annotations = _mapping(
        _mapping(
            _mapping(job["spec"], label="job spec")["template"],
            label="job template",
        )["metadata"],
        label="job template metadata",
    )["annotations"]
    if any(
        fragment in str(annotations).lower()
        for fragment in ("vpc", "network", "cloudsql", "sql-instances", "network-tags")
    ):
        raise CorpusNeo4jTransportError("reused job annotation attachment differs")


def _completion_state(value: Mapping[str, object]) -> str:
    status = _mapping(value.get("status", {}), label="execution status")
    conditions = status.get("conditions", [])
    if type(conditions) is not list:
        raise CorpusNeo4jTransportError("execution conditions differ")
    completed = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if not completed:
        return "Unknown"
    if len(completed) != 1 or completed[0].get("status") not in {
        "Unknown", "True", "False",
    }:
        raise CorpusNeo4jTransportError("execution Completed state differs")
    return str(completed[0]["status"])


def _execution_names(value: object, *, require_terminal: bool) -> list[str]:
    names: list[str] = []
    for ordinal, raw in enumerate(_sequence(value, label="execution census")):
        row = _mapping(raw, label=f"execution census[{ordinal}]")
        metadata = _mapping(row.get("metadata"), label="execution metadata")
        name = _string(metadata.get("name"), label="execution name").rsplit("/", 1)[-1]
        if _EXECUTION.fullmatch(name) is None:
            raise CorpusNeo4jTransportError("execution name differs")
        if require_terminal and _completion_state(row) == "Unknown":
            raise CorpusNeo4jTransportError("reused job has an active execution")
        names.append(name)
    if len(names) != len(set(names)):
        raise CorpusNeo4jTransportError("execution census repeats a name")
    return sorted(names)


def _validate_schedulers(
    value: object, *, job_name: str, all_regions_complete: bool,
) -> None:
    if all_regions_complete is not True:
        raise CorpusNeo4jTransportError("all-region scheduler census is required")
    needle = f"/jobs/{job_name}:run"
    for ordinal, raw in enumerate(_sequence(value, label="scheduler census")):
        row = _mapping(raw, label=f"scheduler census[{ordinal}]")
        target = row.get("httpTarget", {})
        if isinstance(target, Mapping) and needle in str(target.get("uri", "")):
            raise CorpusNeo4jTransportError("a scheduler targets the reused job")


def validate_reuse_preflight(
    *,
    job: object,
    executions: object,
    schedulers: object,
    expected_job_name: str,
    expected_job_uid: str,
    all_regions_complete: bool,
) -> dict[str, object]:
    retained_job = _mapping(job, label="reused job")
    identity = _job_identity(
        retained_job,
        expected_name=expected_job_name,
        expected_uid=expected_job_uid,
    )
    _reject_inherited_attachments(retained_job)
    names = _execution_names(executions, require_terminal=True)
    _validate_schedulers(
        schedulers,
        job_name=expected_job_name,
        all_regions_complete=all_regions_complete,
    )
    return {
        "job": identity,
        "execution_names": names,
        "execution_census_sha256": canonical_sha256(executions),
        "scheduler_census_sha256": canonical_sha256(schedulers),
        "all_regions_complete": True,
        "idle": True,
        "unscheduled": True,
        "inherited_attachment_surface_empty": True,
    }


def _secret_ref_matches(value: object, *, version_identity: str) -> bool:
    row = _mapping(value, label="secret environment row")
    source = _mapping(row.get("valueSource"), label="secret value source")
    ref = _mapping(source.get("secretKeyRef"), label="secret key reference")
    match = _SECRET_VERSION.fullmatch(version_identity)
    if match is None:
        return False
    prefix, _, version = version_identity.rpartition("/versions/")
    secret_name = prefix.rsplit("/secrets/", 1)[-1]
    retained_name = str(ref.get("name", ""))
    return (
        str(ref.get("key", "")) == version
        and retained_name in {secret_name, prefix}
        and set(row) == {"name", "valueSource"}
        and set(source) == {"secretKeyRef"}
        and set(ref) == {"key", "name"}
    )


def validate_parked_job(
    *,
    job: object,
    expected_job_name: str,
    expected_job_uid: str,
    image: str,
    code_sha: str,
    build_id: str,
    service_account: str,
    role: str,
    uri: str,
    database: str,
    provider_resource_id: str,
    username_secret_version: str,
    password_secret_version: str,
) -> dict[str, object]:
    retained = _mapping(job, label="parked job")
    identity = _job_identity(
        retained,
        expected_name=expected_job_name,
        expected_uid=expected_job_uid,
    )
    _validate_template_metadata(retained, require_governed_rest=True)
    if role not in _PRINCIPAL_ROLES:
        raise CorpusNeo4jTransportError("configured graph role differs")
    outer = _outer_spec(retained)
    if set(outer) != {"taskCount", "parallelism", "template"}:
        raise CorpusNeo4jTransportError("parked job outer spec has inherited fields")
    if outer["taskCount"] != 1 or outer["parallelism"] != 1:
        raise CorpusNeo4jTransportError("parked job task concurrency differs")
    task = _task_spec(retained)
    if set(task) != {
        "containers", "maxRetries", "serviceAccountName", "timeoutSeconds",
    }:
        raise CorpusNeo4jTransportError("parked task attachment surface differs")
    if (
        task["maxRetries"] != 0
        or str(task["timeoutSeconds"]) != "86400s"
        or task["serviceAccountName"] != service_account
    ):
        raise CorpusNeo4jTransportError("parked task execution contract differs")
    containers = _sequence(task["containers"], label="parked containers")
    if len(containers) != 1:
        raise CorpusNeo4jTransportError("parked job container count differs")
    container = _mapping(containers[0], label="parked container")
    if set(container) != {"image", "command", "args", "env", "resources"}:
        raise CorpusNeo4jTransportError("parked container attachment surface differs")
    resources = _mapping(container["resources"], label="parked resources")
    if (
        container["image"] != image
        or container["command"] != ["python"]
        or container["args"] != ["scripts/run_corpus_neo4j_transport.py", "parked"]
        or resources != {"limits": {"cpu": "2000m", "memory": "4Gi"}}
    ):
        raise CorpusNeo4jTransportError("parked image/command/resources differ")
    env_rows = _sequence(container["env"], label="parked environment")
    by_name: dict[str, Mapping[str, object]] = {}
    for raw in env_rows:
        row = _mapping(raw, label="parked environment row")
        name = _string(row.get("name"), label="environment name")
        if name in by_name:
            raise CorpusNeo4jTransportError("parked environment repeats")
        by_name[name] = row
    literals = {
        TRANSPORT_ENABLE_ENV: "1",
        "CORPUS_NEO4J_CONFIGURED_ROLE": role,
        URI_ENV: uri,
        DATABASE_ENV: database,
        PROVIDER_RESOURCE_ENV: provider_resource_id,
        USERNAME_SECRET_VERSION_ENV: username_secret_version,
        PASSWORD_SECRET_VERSION_ENV: password_secret_version,
        "CORPUS_NEO4J_IMAGE": image,
        "CORPUS_NEO4J_BUILD_ID": build_id,
        "CODE_SHA": code_sha,
    }
    if set(by_name) != {*literals, USERNAME_ENV, PASSWORD_ENV}:
        raise CorpusNeo4jTransportError("parked environment surface differs")
    for name, expected in literals.items():
        if by_name[name] != {"name": name, "value": expected}:
            raise CorpusNeo4jTransportError(f"parked environment {name} differs")
    if (
        not _secret_ref_matches(
            by_name[USERNAME_ENV], version_identity=username_secret_version
        )
        or not _secret_ref_matches(
            by_name[PASSWORD_ENV], version_identity=password_secret_version
        )
    ):
        raise CorpusNeo4jTransportError("parked Secret Manager version binding differs")
    return {"job": identity, "role": role, "exact_parked_spec": True}


def build_deployment_manifest(
    *,
    deployment_id: str,
    provider: str,
    provider_resource_id: str,
    endpoint_host: str,
    database: str,
    server_version: str,
    server_edition: str,
    principal_secret_versions: Mapping[str, Mapping[str, str]],
    created_at_utc: str,
) -> dict[str, object]:
    """Build a secret-free binding for one initially empty dedicated graph."""
    host = endpoint_host.strip().lower().rstrip(".")
    if not host or "://" in host or "/" in host or "@" in host:
        raise CorpusNeo4jTransportError("endpoint_host must be a bare DNS host")
    principals: dict[str, dict[str, str]] = {}
    if set(principal_secret_versions) != set(_PRINCIPAL_ROLES):
        raise CorpusNeo4jTransportError("all three dedicated principal roles are required")
    seen_secret_versions: set[str] = set()
    for role in _PRINCIPAL_ROLES:
        row = _mapping(principal_secret_versions[role], label=f"{role} principal")
        if set(row) != {"username", "password"}:
            raise CorpusNeo4jTransportError(f"{role} principal schema differs")
        username = _string(row["username"], label=f"{role} username secret version")
        password = _string(row["password"], label=f"{role} password secret version")
        if (
            _SECRET_VERSION.fullmatch(username) is None
            or _SECRET_VERSION.fullmatch(password) is None
            or username == password
        ):
            raise CorpusNeo4jTransportError(f"{role} secret versions must be numeric")
        if username in seen_secret_versions or password in seen_secret_versions:
            raise CorpusNeo4jTransportError("principal secret versions must be distinct")
        seen_secret_versions.update((username, password))
        principals[role] = {"username": username, "password": password}

    body: dict[str, object] = {
        "schema_version": DEPLOYMENT_SCHEMA,
        "publication_mode": "create_once",
        "deployment_id": _string(deployment_id, label="deployment id"),
        "provider": _string(provider, label="provider"),
        "provider_resource_id": _string(
            provider_resource_id, label="provider resource id"
        ),
        "endpoint_host_sha256": sha256(host.encode("utf-8")).hexdigest(),
        "database": _string(database, label="database"),
        "tls": {
            "required": True,
            "accepted_uri_schemes": list(_TLS_SCHEMES),
        },
        "server": {
            "version": _string(server_version, label="server version"),
            "edition": _string(server_edition, label="server edition"),
        },
        "principal_secret_versions": principals,
        "allowed_schema": {
            "node_labels": ["CorpusRetrievalEntity"],
            "relationship_types": ["CORPUS_RELATION"],
            "workstream_namespaces": [
                PARAMETRIC_NAMESPACE,
                RETRIEVAL_NAMESPACE,
                STRATEGY_REGISTRY_NAMESPACE,
            ],
            "reserved_empty_namespaces": [
                POPULATION_NAMESPACE,
                REALIZED_OUTCOME_NAMESPACE,
            ],
        },
        "initial_empty_census": {
            "node_count": 0,
            "relationship_count": 0,
            "node_labels": [],
            "relationship_types": [],
            "workstream_namespaces": [],
        },
        "dedicated_physical_instance_required": True,
        "shared_application_database_forbidden": True,
        "world_matrices_stored_in_graph": False,
        "raw_outcomes_stored_in_graph": False,
        "created_at_utc": _timestamp(created_at_utc, label="created timestamp"),
    }
    return _with_self_hash(body, field="deployment_manifest_sha256")


def build_population_authorized_deployment_manifest(
    *,
    base_deployment_manifest: Mapping[str, object],
    base_deployment_identity: object,
    authorization_id: str,
    created_at_utc: str,
) -> dict[str, object]:
    """Authorize only the bounded population projection on the same graph.

    The v2 manifest deliberately reserves both population and realized
    namespaces.  This create-once v3 successor copies every physical,
    principal, TLS, and empty-origin binding from that exact v2 authority,
    moves only ``corpus-population-research`` into the allowed set, and keeps
    the realized namespace reserved empty.  It is not a replacement for the
    original load manifest and grants no outcome or policy authority.
    """

    base = validate_deployment_manifest(base_deployment_manifest)
    if base["schema_version"] != DEPLOYMENT_SCHEMA:
        raise CorpusNeo4jTransportError(
            "population authorization must directly succeed deployment v2"
        )
    base_identity = object_identity(
        base_deployment_identity, label="base deployment manifest identity"
    )
    body = {
        key: value
        for key, value in base.items()
        if key not in {"schema_version", "deployment_manifest_sha256"}
    }
    body.update({
        "schema_version": POPULATION_DEPLOYMENT_SCHEMA,
        "supersedes_deployment_manifest": base_identity.as_dict(),
        "authorization_id": _string(
            authorization_id, label="population authorization id"
        ),
        "authorized_added_namespaces": [POPULATION_NAMESPACE],
        "population_projection_only": True,
        "realized_outcome_namespace_reserved_empty": True,
        "created_at_utc": _timestamp(
            created_at_utc, label="population authorization timestamp"
        ),
    })
    body["allowed_schema"] = {
        "node_labels": ["CorpusRetrievalEntity"],
        "relationship_types": ["CORPUS_RELATION"],
        "workstream_namespaces": [
            PARAMETRIC_NAMESPACE,
            POPULATION_NAMESPACE,
            RETRIEVAL_NAMESPACE,
            STRATEGY_REGISTRY_NAMESPACE,
        ],
        "reserved_empty_namespaces": [REALIZED_OUTCOME_NAMESPACE],
    }
    return _with_self_hash(body, field="deployment_manifest_sha256")


def validate_deployment_manifest(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="deployment manifest"))
    v2_keys = {
        "schema_version", "publication_mode", "deployment_id", "provider",
        "provider_resource_id", "endpoint_host_sha256", "database", "tls",
        "server", "principal_secret_versions", "allowed_schema",
        "initial_empty_census", "dedicated_physical_instance_required",
        "shared_application_database_forbidden", "world_matrices_stored_in_graph",
        "raw_outcomes_stored_in_graph", "created_at_utc",
        "deployment_manifest_sha256",
    }
    v3_extra_keys = {
        "supersedes_deployment_manifest", "authorization_id",
        "authorized_added_namespaces", "population_projection_only",
        "realized_outcome_namespace_reserved_empty",
    }
    schema_version = item.get("schema_version")
    expected_keys = (
        v2_keys if schema_version == DEPLOYMENT_SCHEMA
        else v2_keys | v3_extra_keys
        if schema_version == POPULATION_DEPLOYMENT_SCHEMA
        else set()
    )
    if not expected_keys or set(item) != expected_keys:
        raise CorpusNeo4jTransportError("deployment manifest schema differs")
    if (
        item["publication_mode"] != "create_once"
        or item["dedicated_physical_instance_required"] is not True
        or item["shared_application_database_forbidden"] is not True
        or item["world_matrices_stored_in_graph"] is not False
        or item["raw_outcomes_stored_in_graph"] is not False
    ):
        raise CorpusNeo4jTransportError("deployment authority differs")
    _self_hash(item, field="deployment_manifest_sha256", label="deployment manifest")
    _string(item["deployment_id"], label="deployment id")
    _string(item["provider"], label="provider")
    _string(item["provider_resource_id"], label="provider resource id")
    endpoint_hash = _string(item["endpoint_host_sha256"], label="endpoint host SHA")
    if _SHA.fullmatch(endpoint_hash) is None:
        raise CorpusNeo4jTransportError("endpoint host SHA differs")
    _string(item["database"], label="database")
    tls = _mapping(item["tls"], label="TLS policy")
    if tls != {"required": True, "accepted_uri_schemes": list(_TLS_SCHEMES)}:
        raise CorpusNeo4jTransportError("TLS policy differs")
    server = _mapping(item["server"], label="server binding")
    if set(server) != {"version", "edition"}:
        raise CorpusNeo4jTransportError("server binding differs")
    _string(server["version"], label="server version")
    _string(server["edition"], label="server edition")
    principals = _mapping(
        item["principal_secret_versions"], label="principal secret versions"
    )
    if set(principals) != set(_PRINCIPAL_ROLES):
        raise CorpusNeo4jTransportError("principal role coverage differs")
    seen: set[str] = set()
    for role in _PRINCIPAL_ROLES:
        row = _mapping(principals[role], label=f"{role} principal")
        if set(row) != {"username", "password"}:
            raise CorpusNeo4jTransportError(f"{role} principal schema differs")
        for field in ("username", "password"):
            version = _string(row[field], label=f"{role} {field} secret version")
            if _SECRET_VERSION.fullmatch(version) is None or version in seen:
                raise CorpusNeo4jTransportError("secret version binding differs")
            seen.add(version)
    schema = _mapping(item["allowed_schema"], label="allowed schema")
    expected_schema_v2 = {
        "node_labels": ["CorpusRetrievalEntity"],
        "relationship_types": ["CORPUS_RELATION"],
        "workstream_namespaces": [
            PARAMETRIC_NAMESPACE,
            RETRIEVAL_NAMESPACE,
            STRATEGY_REGISTRY_NAMESPACE,
        ],
        "reserved_empty_namespaces": [
            POPULATION_NAMESPACE,
            REALIZED_OUTCOME_NAMESPACE,
        ],
    }
    expected_schema_v3 = {
        "node_labels": ["CorpusRetrievalEntity"],
        "relationship_types": ["CORPUS_RELATION"],
        "workstream_namespaces": [
            PARAMETRIC_NAMESPACE,
            POPULATION_NAMESPACE,
            RETRIEVAL_NAMESPACE,
            STRATEGY_REGISTRY_NAMESPACE,
        ],
        "reserved_empty_namespaces": [REALIZED_OUTCOME_NAMESPACE],
    }
    expected_schema = (
        expected_schema_v2
        if schema_version == DEPLOYMENT_SCHEMA
        else expected_schema_v3
    )
    if schema != expected_schema:
        raise CorpusNeo4jTransportError("dedicated allowed schema differs")
    census = _mapping(item["initial_empty_census"], label="initial empty census")
    if census != {
        "node_count": 0,
        "relationship_count": 0,
        "node_labels": [],
        "relationship_types": [],
        "workstream_namespaces": [],
    }:
        raise CorpusNeo4jTransportError("initial graph census is not empty")
    if schema_version == POPULATION_DEPLOYMENT_SCHEMA:
        object_identity(
            item["supersedes_deployment_manifest"],
            label="superseded deployment manifest",
        )
        _string(item["authorization_id"], label="population authorization id")
        if (
            item["authorized_added_namespaces"] != [POPULATION_NAMESPACE]
            or item["population_projection_only"] is not True
            or item["realized_outcome_namespace_reserved_empty"] is not True
        ):
            raise CorpusNeo4jTransportError(
                "population deployment authorization differs"
            )
    _timestamp(item["created_at_utc"], label="deployment created timestamp")
    return item


def validate_connection_binding(
    deployment: Mapping[str, object], *, role: str, environ: Mapping[str, str],
) -> dict[str, str]:
    """Bind runtime connection values without retaining secret values."""
    validate_deployment_manifest(deployment)
    if role not in _PRINCIPAL_ROLES:
        raise CorpusNeo4jTransportError("Neo4j principal role differs")
    values = {
        "uri": environ.get(URI_ENV, ""),
        "database": environ.get(DATABASE_ENV, ""),
        "username": environ.get(USERNAME_ENV, ""),
        "password": environ.get(PASSWORD_ENV, ""),
        "provider_resource_id": environ.get(PROVIDER_RESOURCE_ENV, ""),
        "username_secret_version": environ.get(USERNAME_SECRET_VERSION_ENV, ""),
        "password_secret_version": environ.get(PASSWORD_SECRET_VERSION_ENV, ""),
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise CorpusNeo4jTransportError(
            "Neo4j connection binding is incomplete: " + ", ".join(missing)
        )
    parsed = urlparse(values["uri"])
    if (
        parsed.scheme not in _TLS_SCHEMES
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise CorpusNeo4jTransportError("Neo4j URI must be credential-free TLS")
    host_hash = sha256(parsed.hostname.lower().rstrip(".").encode("utf-8")).hexdigest()
    principal = _mapping(
        _mapping(
            deployment["principal_secret_versions"],
            label="principal secret versions",
        )[role],
        label=f"{role} principal",
    )
    if (
        host_hash != deployment["endpoint_host_sha256"]
        or values["database"] != deployment["database"]
        or values["provider_resource_id"] != deployment["provider_resource_id"]
        or values["username_secret_version"] != principal["username"]
        or values["password_secret_version"] != principal["password"]
    ):
        raise CorpusNeo4jTransportError("runtime dedicated deployment binding differs")
    return values


def _validate_component(
    deployment: Mapping[str, object], component: Mapping[str, object],
) -> dict[str, object]:
    item = dict(_mapping(component, label="Neo4j component"))
    if set(item) != {"version", "edition"}:
        raise CorpusNeo4jTransportError("Neo4j component schema differs")
    expected = _mapping(deployment["server"], label="deployment server")
    if item != expected:
        raise CorpusNeo4jTransportError("Neo4j server version/edition differs")
    return item


def _normalize_census(value: object, *, label: str) -> dict[str, object]:
    item = dict(_mapping(value, label=label))
    expected = {
        "node_count", "relationship_count", "node_labels",
        "relationship_types", "workstream_namespaces",
    }
    if set(item) != expected:
        raise CorpusNeo4jTransportError(f"{label} schema differs")
    if any(type(item[key]) is not int or item[key] < 0 for key in (
        "node_count", "relationship_count",
    )):
        raise CorpusNeo4jTransportError(f"{label} counts differ")
    for key in ("node_labels", "relationship_types", "workstream_namespaces"):
        values = _sequence(item[key], label=f"{label}.{key}")
        if any(not isinstance(row, str) or not row for row in values):
            raise CorpusNeo4jTransportError(f"{label}.{key} differs")
        if list(values) != sorted(set(values)):
            raise CorpusNeo4jTransportError(f"{label}.{key} is not unique/sorted")
    return item


def _require_allowed_census(
    deployment: Mapping[str, object], census: object, *, initially_empty: bool,
) -> dict[str, object]:
    item = _normalize_census(census, label="graph census")
    if initially_empty and item != deployment["initial_empty_census"]:
        raise CorpusNeo4jTransportError("dedicated graph is not initially empty")
    schema = _mapping(deployment["allowed_schema"], label="allowed schema")
    if (
        not set(item["node_labels"]).issubset(set(schema["node_labels"]))
        or not set(item["relationship_types"]).issubset(
            set(schema["relationship_types"])
        )
        or not set(item["workstream_namespaces"]).issubset(
            set(schema["workstream_namespaces"])
        )
        or set(item["workstream_namespaces"]).intersection(
            set(schema["reserved_empty_namespaces"])
        )
    ):
        raise CorpusNeo4jTransportError("foreign or reserved graph schema is present")
    return item


def _mandatory_analytics(
    *, storage: ExactObjectStore, task_result: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[tuple[str, str], bytes]]:
    strategy_rows = _sequence(task_result.get("strategy_results"), label="strategies")
    strategy_ids = []
    for ordinal, raw in enumerate(strategy_rows):
        row = _mapping(raw, label=f"strategy[{ordinal}]")
        strategy_ids.append(_string(row.get("strategy_id"), label="strategy id"))
    if len(strategy_ids) != 4 or len(set(strategy_ids)) != 4:
        raise CorpusNeo4jTransportError("retrieval strategy identity coverage differs")
    expected_keys = {
        *((role, "") for role in _MANDATORY_ANALYTIC_ROLES),
        *(("strategy-selection", strategy_id) for strategy_id in strategy_ids),
    }
    receipts: dict[tuple[str, str], Mapping[str, object]] = {}
    for ordinal, raw in enumerate(_sequence(task_result.get("sidecars"), label="sidecars")):
        row = _mapping(raw, label=f"sidecar[{ordinal}]")
        key = (str(row.get("role", "")), str(row.get("strategy_id", "")))
        if key in receipts:
            raise CorpusNeo4jTransportError("retrieval sidecar keys repeat")
        receipts[key] = row
    missing = sorted(expected_keys - set(receipts))
    if missing:
        raise CorpusNeo4jTransportError(
            f"mandatory retrieval analytics are absent: {missing}"
        )
    identities: list[dict[str, object]] = []
    bodies: dict[tuple[str, str], bytes] = {}
    for key in sorted(expected_keys):
        receipt = receipts[key]
        identity, raw = _read_exact(
            storage, receipt.get("object_identity"),
            label=f"retrieval analytic {key}",
        )
        identities.append({
            "role": key[0],
            "strategy_id": key[1],
            "object_identity": identity.as_dict(),
        })
        bodies[key] = raw
    return identities, bodies


def _accepted_task0(
    storage: ExactObjectStore, terminal_identity_value: object,
) -> tuple[dict[str, object], Neo4jLoadPlan]:
    terminal_identity, terminal_raw = _read_exact(
        storage, terminal_identity_value, label="retrieval terminal"
    )
    terminal = _json(terminal_raw, label="retrieval terminal")
    completion_identity, completion_raw = _read_exact(
        storage, terminal.get("batch_completion"), label="retrieval completion"
    )
    result_identity, result_raw = _read_exact(
        storage, terminal.get("result_object"), label="retrieval task result"
    )
    result = _json(result_raw, label="retrieval task result")
    graph_identity, graph_raw = _read_exact(
        storage, result.get("graph_projection_object"),
        label="retrieval graph projection",
    )
    analytic_identities, analytic_bodies = _mandatory_analytics(
        storage=storage, task_result=result
    )
    try:
        plan = build_load_plan(
            terminal_receipt_raw=terminal_raw,
            terminal_receipt_identity=terminal_identity.as_dict(),
            batch_completion_raw=completion_raw,
            task_result_raw=result_raw,
            graph_projection_raw=graph_raw,
        )
        plan = append_retrieval_analytics(
            plan,
            task_result_raw=result_raw,
            json_sidecar_bodies=analytic_bodies,
        )
    except CorpusRetrievalNeo4jError as exc:
        raise CorpusNeo4jTransportError(
            f"accepted retrieval task-0 graph differs: {exc}"
        ) from exc
    return {
        "terminal": terminal_identity.as_dict(),
        "completion": completion_identity.as_dict(),
        "task_result": result_identity.as_dict(),
        "graph_projection": graph_identity.as_dict(),
        "mandatory_analytics": analytic_identities,
        "run_id": plan.run_id,
        "task_id": plan.task_id,
        "plan_sha256": plan.plan_sha256,
        "node_count": len(plan.nodes),
        "relationship_count": len(plan.relationships),
    }, plan


def _validate_task_acceptance(
    raw: bytes, *, identity: ObjectIdentity, expected_index: int,
) -> dict[str, object]:
    item = _json(_bind_raw(raw, identity, label="task acceptance"), label="task acceptance")
    _self_hash(item, field="task_acceptance_sha256", label="task acceptance")
    false_flags = (
        "automatic_retry_licensed", "uses_realized_outcomes",
        "historical_scoring_licensed", "corpus_fill_licensed",
        "graph_mutation_licensed", "production_change_licensed",
        "decision_authority",
    )
    if (
        item.get("schema_version") != _TASK_ACCEPTANCE_SCHEMA
        or item.get("task_index") != expected_index
        or item.get("evidence_object_count") != 140
        or item.get("complete_evidence_receipt") is not True
        or item.get("independent_verification_complete") is not True
        or item.get("strict_verifier_terminal_success") is not True
        or item.get("accepted") is not True
        or item.get("partial_result") is not False
        or any(item.get(key) is not False for key in false_flags)
    ):
        raise CorpusNeo4jTransportError("parametric task acceptance is not final")
    for field in ("science_terminal", "task_result", "independent_verification"):
        object_identity(item.get(field), label=f"task acceptance {field}")
    return item


def _accepted_parametric_suite(
    *,
    storage: ExactObjectStore,
    batch_acceptance_identity_value: object,
    retrieval_plan: Neo4jLoadPlan,
) -> tuple[dict[str, object], tuple[Neo4jLoadPlan, ...]]:
    acceptance_identity, acceptance_raw = _read_exact(
        storage, batch_acceptance_identity_value,
        label="parametric batch acceptance",
    )
    acceptance = _json(acceptance_raw, label="parametric batch acceptance")
    _self_hash(
        acceptance,
        field="batch_acceptance_sha256",
        label="parametric batch acceptance",
    )
    false_flags = (
        "automatic_retry_licensed", "uses_realized_outcomes",
        "historical_scoring_licensed", "corpus_fill_licensed",
        "graph_mutation_licensed", "production_change_licensed",
        "decision_authority",
    )
    if (
        acceptance.get("schema_version") != _BATCH_ACCEPTANCE_SCHEMA
        or acceptance.get("batch_mode") != "complete-54-task"
        or acceptance.get("task_count") != 54
        or acceptance.get("parameter_set_count") != 7
        or acceptance.get("matrix_cell_count") != 378
        or acceptance.get("complete") is not True
        or acceptance.get("accepted") is not True
        or acceptance.get("partial_result") is not False
        or acceptance.get("independent_verification_complete_for_every_task")
        is not True
        or any(acceptance.get(key) is not False for key in false_flags)
    ):
        raise CorpusNeo4jTransportError("parametric batch acceptance is not final")
    completion_identity, completion_raw = _read_exact(
        storage, acceptance.get("batch_completion"),
        label="parametric batch completion",
    )
    task_acceptance_values = _sequence(
        acceptance.get("task_acceptances"), label="task acceptances"
    )
    if len(task_acceptance_values) != 54:
        raise CorpusNeo4jTransportError("parametric task acceptance coverage differs")

    task_rows: list[dict[str, object]] = []
    plans: list[Neo4jLoadPlan] = []
    seen_identities: set[tuple[object, ...]] = set()
    for task_index, value in enumerate(task_acceptance_values):
        task_acceptance_identity, task_acceptance_raw = _read_exact(
            storage, value, label=f"task[{task_index}] acceptance"
        )
        task_acceptance = _validate_task_acceptance(
            task_acceptance_raw,
            identity=task_acceptance_identity,
            expected_index=task_index,
        )
        result_identity, result_raw = _read_exact(
            storage, task_acceptance["task_result"],
            label=f"task[{task_index}] result",
        )
        terminal_identity, terminal_raw = _read_exact(
            storage, task_acceptance["science_terminal"],
            label=f"task[{task_index}] science terminal",
        )
        verification_identity, verification_raw = _read_exact(
            storage, task_acceptance["independent_verification"],
            label=f"task[{task_index}] independent verification",
        )
        result_body = _json(result_raw, label=f"task[{task_index}] result")
        verification_body = _json(
            verification_raw,
            label=f"task[{task_index}] independent verification",
        )
        if (
            task_acceptance.get("task_sha256") != result_body.get("task_sha256")
            or task_acceptance.get("independent_verification_sha256")
            != verification_body.get("verification_sha256")
        ):
            raise CorpusNeo4jTransportError(
                "parametric task acceptance evidence binding differs"
            )
        identities = (
            task_acceptance_identity, result_identity,
            terminal_identity, verification_identity,
        )
        for identity in identities:
            key = (identity.uri, identity.generation, identity.sha256, identity.bytes)
            if key in seen_identities:
                raise CorpusNeo4jTransportError(
                    "parametric accepted object aliases across tasks"
                )
            seen_identities.add(key)
        try:
            plan = append_parametric_batch(
                retrieval_plan,
                batch_completion_raw=completion_raw,
                batch_completion_identity=completion_identity.as_dict(),
                task_result_raw=result_raw,
                task_result_identity=result_identity.as_dict(),
                terminal_receipt_raw=terminal_raw,
                terminal_receipt_identity=terminal_identity.as_dict(),
                independent_verification_raw=verification_raw,
                independent_verification_identity=verification_identity.as_dict(),
            )
        except CorpusRetrievalNeo4jError as exc:
            raise CorpusNeo4jTransportError(
                f"accepted parametric task[{task_index}] graph differs: {exc}"
            ) from exc
        slate_rows = [
            row for row in plan.nodes
            if row.get("kind") == "CorpusParametricTask"
            and row.get("task_index") == task_index
        ]
        if len(slate_rows) != 1:
            raise CorpusNeo4jTransportError("parametric task graph grain differs")
        slate_id = str(slate_rows[0]["slate_id"])
        task_rows.append({
            "task_index": task_index,
            "slate_id": slate_id,
            "task_acceptance": task_acceptance_identity.as_dict(),
            "task_result": result_identity.as_dict(),
            "science_terminal": terminal_identity.as_dict(),
            "independent_verification": verification_identity.as_dict(),
            "plan_sha256": plan.plan_sha256,
            "node_count": len(plan.nodes),
            "relationship_count": len(plan.relationships),
        })
        plans.append(plan)
    batch_ids = {
        str(row["run_id"]) for plan in plans for row in plan.nodes
        if row.get("kind") == "CorpusParametricWorkstream"
    }
    if len(batch_ids) != 1:
        raise CorpusNeo4jTransportError("parametric batch ID differs")
    return {
        "batch_acceptance": acceptance_identity.as_dict(),
        "batch_completion": completion_identity.as_dict(),
        "batch_id": next(iter(batch_ids)),
        "task_count": 54,
        "parameter_set_count": 7,
        "matrix_cell_count": 378,
        "tasks": task_rows,
    }, tuple(plans)


def _accepted_strategy_registry(
    *,
    storage: ExactObjectStore,
    release_identity_value: object,
    retrieval_plan: Neo4jLoadPlan,
) -> tuple[dict[str, object], Any]:
    # Imported lazily because the registry reuses this transport's exact-object
    # protocol and error type.
    from nfl_dfs.research import corpus_strategy_registry as registry

    try:
        bundle = registry.prepare_strategy_registry_plan(
            parent_plan=retrieval_plan,
            storage=storage,
            release_identity=release_identity_value,
        )
        catalog = registry.query_catalog()
    except registry.CorpusStrategyRegistryError as exc:
        raise CorpusNeo4jTransportError(
            f"strategy registry evidence differs: {exc}"
        ) from exc
    registry_nodes = [
        row for row in bundle.plan.nodes
        if row.get("workstream_namespace") == STRATEGY_REGISTRY_NAMESPACE
    ]
    registry_node_ids = {str(row["id"]) for row in registry_nodes}
    registry_edges = [
        row for row in bundle.plan.relationships
        if str(row["from_id"]) in registry_node_ids
        or str(row["to_id"]) in registry_node_ids
    ]
    if bundle.winner_imported or bundle.winner_count != 0 or not registry_nodes:
        raise CorpusNeo4jTransportError(
            "strategy registry violates the outcome-blind v2 boundary"
        )
    return {
        "registry_release": bundle.release_identity.as_dict(),
        "registry_id": bundle.release["registry_id"],
        "plan_sha256": bundle.plan.plan_sha256,
        "registry_node_count": len(registry_nodes),
        "registry_relationship_count": len(registry_edges),
        "kind_counts": {
            kind: sum(row["kind"] == kind for row in registry_nodes)
            for kind in sorted({str(row["kind"]) for row in registry_nodes})
        },
        "winner_imported": False,
        "winner_count": 0,
        "query_catalog": catalog,
        "query_catalog_sha256": canonical_sha256(catalog),
        "uses_realized_outcomes": False,
        "raw_outcomes_stored_in_graph": False,
    }, bundle


def prepare_load_manifest(
    *,
    storage: ExactObjectStore,
    deployment_manifest_identity: object,
    retrieval_terminal_identity: object,
    parametric_batch_acceptance_identity: object | None,
    strategy_registry_release_identity: object,
    output_prefix: str,
    code_commit: str,
    image: str,
    created_at_utc: str,
) -> tuple[dict[str, object], ValidatedLoadBundle]:
    deployment_identity, deployment_raw = _read_exact(
        storage, deployment_manifest_identity, label="deployment manifest"
    )
    deployment = validate_deployment_manifest(
        _json(deployment_raw, label="deployment manifest")
    )
    retrieval, retrieval_plan = _accepted_task0(
        storage, retrieval_terminal_identity
    )
    parametric: dict[str, object] | None = None
    parametric_plans: tuple[Neo4jLoadPlan, ...] = ()
    if parametric_batch_acceptance_identity is not None:
        parametric, parametric_plans = _accepted_parametric_suite(
            storage=storage,
            batch_acceptance_identity_value=parametric_batch_acceptance_identity,
            retrieval_plan=retrieval_plan,
        )
    strategy_registry, strategy_registry_bundle = _accepted_strategy_registry(
        storage=storage,
        release_identity_value=strategy_registry_release_identity,
        retrieval_plan=retrieval_plan,
    )
    if _COMMIT.fullmatch(code_commit) is None:
        raise CorpusNeo4jTransportError("code commit must be an exact Git SHA")
    if _IMAGE.fullmatch(image) is None:
        raise CorpusNeo4jTransportError("image must be an immutable digest URI")
    prefix = _gcs_prefix(output_prefix, label="graph output prefix")
    body: dict[str, object] = {
        "schema_version": LOAD_MANIFEST_SCHEMA,
        "publication_mode": "create_once",
        "deployment_manifest": deployment_identity.as_dict(),
        "deployment_id": deployment["deployment_id"],
        "retrieval": retrieval,
        "parametric": parametric,
        "strategy_registry": strategy_registry,
        "release": {"code_commit": code_commit, "image": image},
        "output_prefix": prefix,
        "receipt_uris": {
            "bootstrap": f"{prefix}governance/schema-bootstrap.json",
            "retrieval": f"{prefix}task0/load-result.json",
            "parametric_prefix": f"{prefix}parametric/",
            "strategy_registry_load": (
                f"{prefix}strategy-registry/load-result.json"
            ),
            "strategy_registry_projection": (
                f"{prefix}strategy-registry/projection-receipt.json"
            ),
            "strategy_registry_query": (
                f"{prefix}strategy-registry/query-receipt.json"
            ),
            "suite_terminal": f"{prefix}governance/suite-terminal.json",
            "query_smoke_task0": f"{prefix}governance/query-smoke-task0.json",
            "query_smoke_complete": f"{prefix}governance/query-smoke-complete.json",
            "launch_prefix": f"{prefix}governance/launches/",
        },
        "worker_object_access_mode": "generation-pinned-exact-get-no-list",
        "graph_is_rebuildable_projection": True,
        "gcs_remains_authoritative": True,
        "world_matrices_stored_in_graph": False,
        "raw_outcomes_stored_in_graph": False,
        "automatic_policy_feedback": False,
        "corpus_population_mutation_authority": False,
        "production_policy_authority": False,
        "created_at_utc": _timestamp(created_at_utc, label="manifest created timestamp"),
    }
    manifest = _with_self_hash(body, field="load_manifest_sha256")
    return manifest, ValidatedLoadBundle(
        manifest=manifest,
        manifest_identity=None,
        deployment=deployment,
        deployment_identity=deployment_identity,
        retrieval_plan=retrieval_plan,
        parametric_plans=parametric_plans,
        strategy_registry_bundle=strategy_registry_bundle,
    )


def _validate_manifest_shape(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="load manifest"))
    expected_keys = {
        "schema_version", "publication_mode", "deployment_manifest",
        "deployment_id", "retrieval", "parametric", "strategy_registry",
        "release",
        "output_prefix", "receipt_uris", "worker_object_access_mode",
        "graph_is_rebuildable_projection", "gcs_remains_authoritative",
        "world_matrices_stored_in_graph", "raw_outcomes_stored_in_graph",
        "automatic_policy_feedback", "corpus_population_mutation_authority",
        "production_policy_authority", "created_at_utc",
        "load_manifest_sha256",
    }
    if set(item) != expected_keys:
        raise CorpusNeo4jTransportError("load manifest schema differs")
    if (
        item["schema_version"] != LOAD_MANIFEST_SCHEMA
        or item["publication_mode"] != "create_once"
        or item["worker_object_access_mode"]
        != "generation-pinned-exact-get-no-list"
        or item["graph_is_rebuildable_projection"] is not True
        or item["gcs_remains_authoritative"] is not True
        or item["world_matrices_stored_in_graph"] is not False
        or item["raw_outcomes_stored_in_graph"] is not False
        or item["automatic_policy_feedback"] is not False
        or item["corpus_population_mutation_authority"] is not False
        or item["production_policy_authority"] is not False
    ):
        raise CorpusNeo4jTransportError("load manifest authority differs")
    _self_hash(item, field="load_manifest_sha256", label="load manifest")
    prefix = _gcs_prefix(item["output_prefix"], label="graph output prefix")
    receipt_uris = _mapping(item["receipt_uris"], label="receipt URIs")
    if receipt_uris != {
        "bootstrap": f"{prefix}governance/schema-bootstrap.json",
        "retrieval": f"{prefix}task0/load-result.json",
        "parametric_prefix": f"{prefix}parametric/",
        "strategy_registry_load": f"{prefix}strategy-registry/load-result.json",
        "strategy_registry_projection": (
            f"{prefix}strategy-registry/projection-receipt.json"
        ),
        "strategy_registry_query": f"{prefix}strategy-registry/query-receipt.json",
        "suite_terminal": f"{prefix}governance/suite-terminal.json",
        "query_smoke_task0": f"{prefix}governance/query-smoke-task0.json",
        "query_smoke_complete": f"{prefix}governance/query-smoke-complete.json",
        "launch_prefix": f"{prefix}governance/launches/",
    }:
        raise CorpusNeo4jTransportError("load manifest receipt URIs differ")
    release = _mapping(item["release"], label="release")
    if (
        set(release) != {"code_commit", "image"}
        or _COMMIT.fullmatch(str(release.get("code_commit", ""))) is None
        or _IMAGE.fullmatch(str(release.get("image", ""))) is None
    ):
        raise CorpusNeo4jTransportError("load manifest release differs")
    strategy_registry = _mapping(
        item["strategy_registry"], label="strategy registry manifest"
    )
    expected_registry_keys = {
        "registry_release", "registry_id", "plan_sha256",
        "registry_node_count", "registry_relationship_count", "kind_counts",
        "winner_imported", "winner_count", "query_catalog",
        "query_catalog_sha256", "uses_realized_outcomes",
        "raw_outcomes_stored_in_graph",
    }
    if (
        set(strategy_registry) != expected_registry_keys
        or not isinstance(strategy_registry.get("registry_id"), str)
        or not strategy_registry["registry_id"]
        or _SHA.fullmatch(str(strategy_registry.get("plan_sha256", ""))) is None
        or type(strategy_registry.get("registry_node_count")) is not int
        or strategy_registry["registry_node_count"] < 1
        or type(strategy_registry.get("registry_relationship_count")) is not int
        or strategy_registry["registry_relationship_count"] < 1
        or not isinstance(strategy_registry.get("kind_counts"), Mapping)
        or strategy_registry.get("winner_imported") is not False
        or strategy_registry.get("winner_count") != 0
        or strategy_registry.get("uses_realized_outcomes") is not False
        or strategy_registry.get("raw_outcomes_stored_in_graph") is not False
    ):
        raise CorpusNeo4jTransportError("strategy registry manifest differs")
    kind_counts = _mapping(
        strategy_registry["kind_counts"], label="strategy registry kind counts"
    )
    if (
        not kind_counts
        or any(
            not isinstance(kind, str)
            or not kind
            or type(count) is not int
            or count < 1
            for kind, count in kind_counts.items()
        )
        or sum(int(count) for count in kind_counts.values())
        != strategy_registry["registry_node_count"]
    ):
        raise CorpusNeo4jTransportError("strategy registry kind census differs")
    object_identity(
        strategy_registry["registry_release"],
        label="strategy registry release",
    )
    catalog = _sequence(
        strategy_registry["query_catalog"], label="strategy query catalog"
    )
    if (
        canonical_sha256(catalog) != strategy_registry["query_catalog_sha256"]
        or _SHA.fullmatch(str(strategy_registry["query_catalog_sha256"])) is None
    ):
        raise CorpusNeo4jTransportError("strategy registry query catalog differs")
    _timestamp(item["created_at_utc"], label="manifest created timestamp")
    return item


def validate_load_manifest(
    *, storage: ExactObjectStore, manifest_identity: object,
) -> ValidatedLoadBundle:
    retained_identity, raw = _read_exact(
        storage, manifest_identity, label="load manifest"
    )
    item = _validate_manifest_shape(_json(raw, label="load manifest"))
    deployment_value = item["deployment_manifest"]
    retrieval_value = _mapping(item["retrieval"], label="manifest retrieval")
    parametric_value = item["parametric"]
    registry_value = _mapping(
        item["strategy_registry"], label="manifest strategy registry"
    )
    rebuilt, bundle = prepare_load_manifest(
        storage=storage,
        deployment_manifest_identity=deployment_value,
        retrieval_terminal_identity=retrieval_value.get("terminal"),
        parametric_batch_acceptance_identity=(
            None if parametric_value is None
            else _mapping(parametric_value, label="manifest parametric").get(
                "batch_acceptance"
            )
        ),
        strategy_registry_release_identity=registry_value.get("registry_release"),
        output_prefix=str(item["output_prefix"]),
        code_commit=str(_mapping(item["release"], label="release")["code_commit"]),
        image=str(_mapping(item["release"], label="release")["image"]),
        created_at_utc=str(item["created_at_utc"]),
    )
    if canonical_json_bytes(rebuilt) != raw:
        raise CorpusNeo4jTransportError("load manifest does not rebuild exactly")
    return ValidatedLoadBundle(
        manifest=item,
        manifest_identity=retained_identity,
        deployment=bundle.deployment,
        deployment_identity=bundle.deployment_identity,
        retrieval_plan=bundle.retrieval_plan,
        parametric_plans=bundle.parametric_plans,
        strategy_registry_bundle=bundle.strategy_registry_bundle,
    )


def publish_manifest(
    *, storage: ExactObjectStore, uri: str, manifest: Mapping[str, object],
) -> ObjectIdentity:
    _validate_manifest_shape(manifest)
    return storage.publish_create_once(uri, canonical_json_bytes(manifest))


def _operation_key(
    operation: str, *, task_index: int | None, require_complete_suite: bool,
) -> str:
    if operation not in _ROLE_BY_OPERATION:
        raise CorpusNeo4jTransportError("graph operation differs")
    if operation in {"load-parametric-task", "recover-parametric-receipt"}:
        if type(task_index) is not int or not 0 <= task_index < 54:
            raise CorpusNeo4jTransportError("parametric task index must be in 0..53")
        key = f"{operation}-task-{task_index:04d}"
    else:
        if task_index is not None:
            raise CorpusNeo4jTransportError("task index is not valid for this operation")
        key = operation
    if operation == "query-smoke":
        key += "-complete" if require_complete_suite else "-task0"
    elif require_complete_suite:
        raise CorpusNeo4jTransportError(
            "complete-suite query flag is not valid for this operation"
        )
    return key


def _launch_uri(
    bundle: ValidatedLoadBundle,
    *,
    operation: str,
    task_index: int | None,
    require_complete_suite: bool,
    leaf: str,
) -> str:
    prefix = str(
        _mapping(bundle.manifest["receipt_uris"], label="receipt URIs")[
            "launch_prefix"
        ]
    )
    key = _operation_key(
        operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
    )
    if leaf not in {"intent.json", "execution-binding.json", "terminal.json"}:
        raise CorpusNeo4jTransportError("launch receipt leaf differs")
    return f"{prefix}{key}/{leaf}"


def _worker_args(
    *,
    bundle: ValidatedLoadBundle,
    project: str,
    operation: str,
    task_index: int | None,
    require_complete_suite: bool,
) -> list[str]:
    if bundle.manifest_identity is None:
        raise CorpusNeo4jTransportError("published load manifest identity is required")
    identity = bundle.manifest_identity
    args = [
        "scripts/run_corpus_neo4j_transport.py",
        operation,
        "--manifest-uri", identity.uri,
        "--manifest-generation", identity.generation,
        "--manifest-sha256", identity.sha256,
        "--manifest-bytes", str(identity.bytes),
        "--project", _string(project, label="GCP project"),
        "--execute",
    ]
    if task_index is not None:
        args.extend(("--task-index", str(task_index)))
    if require_complete_suite:
        args.append("--require-complete-suite")
    return args


def _validate_launch_intent(
    raw: bytes, *, bundle: ValidatedLoadBundle, operation: str,
    task_index: int | None, require_complete_suite: bool,
) -> dict[str, object]:
    item = _json(raw, label="graph launch intent")
    _self_hash(item, field="launch_intent_sha256", label="graph launch intent")
    if (
        item.get("schema_version") != LAUNCH_INTENT_SCHEMA
        or bundle.manifest_identity is None
        or item.get("load_manifest") != bundle.manifest_identity.as_dict()
        or item.get("deployment_manifest") != bundle.deployment_identity.as_dict()
        or item.get("operation") != operation
        or item.get("task_index") != (-1 if task_index is None else task_index)
        or item.get("require_complete_suite") is not require_complete_suite
        or item.get("role") != _ROLE_BY_OPERATION[operation]
        or item.get("one_execution_only") is not True
        or item.get("automatic_retry_licensed") is not False
    ):
        raise CorpusNeo4jTransportError("graph launch intent binding differs")
    return item


def consume_launch_intent(
    *,
    storage: ExactObjectStore,
    bundle: ValidatedLoadBundle,
    operation: str,
    task_index: int | None,
    require_complete_suite: bool,
    project: str,
    job: object,
    executions: object,
    schedulers: object,
    expected_job_name: str,
    expected_job_uid: str,
    all_regions_complete: bool,
    parked_job_contract: Mapping[str, str],
    created_at_utc: str,
) -> dict[str, object]:
    """Consume one durable operation-specific launch authority before execute."""
    key = _operation_key(
        operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
    )
    role = _ROLE_BY_OPERATION[operation]
    if parked_job_contract.get("role") != role:
        raise CorpusNeo4jTransportError("configured role does not match graph operation")
    parked = validate_parked_job(
        job=job,
        expected_job_name=expected_job_name,
        expected_job_uid=expected_job_uid,
        image=parked_job_contract["image"],
        code_sha=parked_job_contract["code_sha"],
        build_id=parked_job_contract["build_id"],
        service_account=parked_job_contract["service_account"],
        role=role,
        uri=parked_job_contract["uri"],
        database=parked_job_contract["database"],
        provider_resource_id=parked_job_contract["provider_resource_id"],
        username_secret_version=parked_job_contract["username_secret_version"],
        password_secret_version=parked_job_contract["password_secret_version"],
    )
    preflight = validate_reuse_preflight(
        job=job,
        executions=executions,
        schedulers=schedulers,
        expected_job_name=expected_job_name,
        expected_job_uid=expected_job_uid,
        all_regions_complete=all_regions_complete,
    )
    intent_uri = _launch_uri(
        bundle,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
        leaf="intent.json",
    )
    existing = storage.resolve_optional(intent_uri)
    if existing is not None:
        identity, raw = existing
        item = _validate_launch_intent(
            raw,
            bundle=bundle,
            operation=operation,
            task_index=task_index,
            require_complete_suite=require_complete_suite,
        )
        return {
            "schema_version": "corpus-neo4j-launch-consumption/v1",
            "operation_key": key,
            "launch_intent": identity.as_dict(),
            "worker_args": item["worker_args"],
            "launch_permitted": False,
            "automatic_retry_licensed": False,
        }
    worker_args = _worker_args(
        bundle=bundle,
        project=project,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
    )
    body = {
        "schema_version": LAUNCH_INTENT_SCHEMA,
        "publication_mode": "create_once",
        "deployment_manifest": bundle.deployment_identity.as_dict(),
        "load_manifest": bundle.manifest_identity.as_dict(),
        "operation_key": key,
        "operation": operation,
        "task_index": -1 if task_index is None else task_index,
        "require_complete_suite": require_complete_suite,
        "role": role,
        "job": parked["job"],
        "job_spec_sha256": preflight["job"]["spec_sha256"],
        "before_execution_names": preflight["execution_names"],
        "before_execution_census_sha256": preflight["execution_census_sha256"],
        "scheduler_census_sha256": preflight["scheduler_census_sha256"],
        "all_regions_complete": True,
        "worker_args": worker_args,
        "one_execution_only": True,
        "automatic_retry_licensed": False,
        "created_at_utc": _timestamp(created_at_utc, label="launch intent timestamp"),
    }
    intent = _with_self_hash(body, field="launch_intent_sha256")
    identity = storage.publish_create_once(intent_uri, canonical_json_bytes(intent))
    return {
        "schema_version": "corpus-neo4j-launch-consumption/v1",
        "operation_key": key,
        "launch_intent": identity.as_dict(),
        "worker_args": worker_args,
        "launch_permitted": True,
        "automatic_retry_licensed": False,
    }


def bind_launch_execution(
    *,
    storage: ExactObjectStore,
    bundle: ValidatedLoadBundle,
    operation: str,
    task_index: int | None,
    require_complete_suite: bool,
    job: object,
    executions: object,
    schedulers: object,
    expected_job_name: str,
    expected_job_uid: str,
    all_regions_complete: bool,
    created_at_utc: str,
) -> dict[str, object]:
    intent_uri = _launch_uri(
        bundle,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
        leaf="intent.json",
    )
    resolved_intent = storage.resolve_optional(intent_uri)
    if resolved_intent is None:
        raise CorpusNeo4jTransportError("launch intent is absent")
    intent_identity, intent_raw = resolved_intent
    intent = _validate_launch_intent(
        intent_raw,
        bundle=bundle,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
    )
    binding_uri = _launch_uri(
        bundle,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
        leaf="execution-binding.json",
    )
    existing = storage.resolve_optional(binding_uri)
    if existing is not None:
        identity, raw = existing
        item = _validate_execution_binding(
            raw,
            bundle=bundle,
            intent_identity=intent_identity,
            operation=operation,
            task_index=task_index,
            require_complete_suite=require_complete_suite,
        )
        return {**item, "execution_binding_identity": identity.as_dict()}
    retained_job = _job_identity(
        job,
        expected_name=expected_job_name,
        expected_uid=expected_job_uid,
    )
    if (
        retained_job["spec_sha256"] != intent["job_spec_sha256"]
        or retained_job["uid"] != _mapping(intent["job"], label="intent job")["uid"]
    ):
        raise CorpusNeo4jTransportError("job changed after launch authority consumption")
    _validate_schedulers(
        schedulers,
        job_name=expected_job_name,
        all_regions_complete=all_regions_complete,
    )
    after_names = _execution_names(executions, require_terminal=False)
    before_names = list(_sequence(
        intent["before_execution_names"], label="before execution names"
    ))
    if not set(before_names).issubset(after_names):
        raise CorpusNeo4jTransportError("after execution census lost prior names")
    new_names = sorted(set(after_names) - set(before_names))
    if len(new_names) != 1 or not new_names[0].startswith(f"{expected_job_name}-"):
        raise CorpusNeo4jTransportError(
            "launch does not have exactly one attributable execution"
        )
    body = {
        "schema_version": EXECUTION_BINDING_SCHEMA,
        "publication_mode": "create_once",
        "deployment_manifest": bundle.deployment_identity.as_dict(),
        "load_manifest": bundle.manifest_identity.as_dict(),
        "launch_intent": intent_identity.as_dict(),
        "operation": operation,
        "task_index": -1 if task_index is None else task_index,
        "require_complete_suite": require_complete_suite,
        "job": retained_job,
        "execution_name": new_names[0],
        "before_execution_names": before_names,
        "after_execution_names": after_names,
        "after_execution_census_sha256": canonical_sha256(executions),
        "scheduler_census_sha256": canonical_sha256(schedulers),
        "sole_new_execution": True,
        "automatic_retry_licensed": False,
        "created_at_utc": _timestamp(created_at_utc, label="binding timestamp"),
    }
    binding = _with_self_hash(body, field="execution_binding_sha256")
    identity = storage.publish_create_once(binding_uri, canonical_json_bytes(binding))
    return {**binding, "execution_binding_identity": identity.as_dict()}


def _receipt_uri(bundle: ValidatedLoadBundle, *, task_index: int | None) -> str:
    receipts = _mapping(bundle.manifest["receipt_uris"], label="receipt URIs")
    if task_index is None:
        return str(receipts["retrieval"])
    return f"{receipts['parametric_prefix']}task-{task_index:04d}/load-result.json"


def _strategy_registry_load_uri(bundle: ValidatedLoadBundle) -> str:
    return str(
        _mapping(bundle.manifest["receipt_uris"], label="receipt URIs")[
            "strategy_registry_load"
        ]
    )


def _strategy_registry_plan(bundle: ValidatedLoadBundle) -> Neo4jLoadPlan:
    plan = getattr(bundle.strategy_registry_bundle, "plan", None)
    if not isinstance(plan, Neo4jLoadPlan):
        raise CorpusNeo4jTransportError("strategy registry graph plan is absent")
    expected = _mapping(
        bundle.manifest["strategy_registry"], label="strategy registry manifest"
    )
    if plan.plan_sha256 != expected["plan_sha256"]:
        raise CorpusNeo4jTransportError("strategy registry graph plan differs")
    return plan


def _strategy_registry_load_receipt(
    *,
    bundle: ValidatedLoadBundle,
    core_result: Mapping[str, object],
    verification: Mapping[str, object],
) -> dict[str, object]:
    if bundle.manifest_identity is None:
        raise CorpusNeo4jTransportError("published load manifest identity is required")
    registry_manifest = _mapping(
        bundle.manifest["strategy_registry"], label="strategy registry manifest"
    )
    body = {
        "schema_version": LOAD_RECEIPT_SCHEMA,
        "publication_mode": "create_once",
        "deployment_manifest": bundle.deployment_identity.as_dict(),
        "load_manifest": bundle.manifest_identity.as_dict(),
        "deployment_id": bundle.deployment["deployment_id"],
        "task_kind": "strategy-registry",
        "task_index": -1,
        "slate_id": "",
        "registry_release": registry_manifest["registry_release"],
        "registry_id": registry_manifest["registry_id"],
        "plan_sha256": registry_manifest["plan_sha256"],
        "registry_node_count": registry_manifest["registry_node_count"],
        "registry_relationship_count": registry_manifest[
            "registry_relationship_count"
        ],
        "kind_counts": registry_manifest["kind_counts"],
        "core_load_result": dict(core_result),
        "post_load_verification": dict(verification),
        "idempotent": True,
        "gcs_remains_authoritative": True,
        "world_matrices_stored_in_graph": False,
        "raw_outcomes_stored_in_graph": False,
        "uses_realized_outcomes": False,
        "automatic_policy_feedback": False,
        "corpus_population_mutation_authority": False,
        "production_policy_authority": False,
    }
    return _with_self_hash(body, field="governed_load_result_sha256")


def _validate_existing_strategy_registry_load_receipt(
    raw: bytes, *, bundle: ValidatedLoadBundle,
) -> dict[str, object]:
    item = _json(raw, label="strategy registry graph load receipt")
    _self_hash(
        item,
        field="governed_load_result_sha256",
        label="strategy registry graph load receipt",
    )
    plan = _strategy_registry_plan(bundle)
    registry_manifest = _mapping(
        bundle.manifest["strategy_registry"], label="strategy registry manifest"
    )
    expected_core = build_load_result_receipt(
        plan,
        database=str(bundle.deployment["database"]),
        node_count=len(plan.nodes),
        relationship_count=len(plan.relationships),
    )
    if (
        item.get("schema_version") != LOAD_RECEIPT_SCHEMA
        or item.get("publication_mode") != "create_once"
        or item.get("deployment_manifest") != bundle.deployment_identity.as_dict()
        or bundle.manifest_identity is None
        or item.get("load_manifest") != bundle.manifest_identity.as_dict()
        or item.get("deployment_id") != bundle.deployment["deployment_id"]
        or item.get("task_kind") != "strategy-registry"
        or item.get("task_index") != -1
        or item.get("slate_id") != ""
        or item.get("registry_release") != registry_manifest["registry_release"]
        or item.get("registry_id") != registry_manifest["registry_id"]
        or item.get("plan_sha256") != registry_manifest["plan_sha256"]
        or item.get("registry_node_count")
        != registry_manifest["registry_node_count"]
        or item.get("registry_relationship_count")
        != registry_manifest["registry_relationship_count"]
        or item.get("kind_counts") != registry_manifest["kind_counts"]
        or item.get("core_load_result") != expected_core
        or item.get("idempotent") is not True
        or item.get("gcs_remains_authoritative") is not True
        or item.get("world_matrices_stored_in_graph") is not False
        or item.get("raw_outcomes_stored_in_graph") is not False
        or item.get("uses_realized_outcomes") is not False
        or item.get("automatic_policy_feedback") is not False
        or item.get("corpus_population_mutation_authority") is not False
        or item.get("production_policy_authority") is not False
    ):
        raise CorpusNeo4jTransportError(
            "strategy registry graph load receipt binding differs"
        )
    _validate_plan_verification(item.get("post_load_verification"), plan=plan)
    return item


def _load_receipt(
    *,
    bundle: ValidatedLoadBundle,
    plan: Neo4jLoadPlan,
    core_result: Mapping[str, object],
    verification: Mapping[str, object],
    task_index: int | None,
) -> dict[str, object]:
    if bundle.manifest_identity is None:
        raise CorpusNeo4jTransportError("published load manifest identity is required")
    task_kind = "retrieval-task0" if task_index is None else "parametric-task"
    body = {
        "schema_version": LOAD_RECEIPT_SCHEMA,
        "publication_mode": "create_once",
        "deployment_manifest": bundle.deployment_identity.as_dict(),
        "load_manifest": bundle.manifest_identity.as_dict(),
        "deployment_id": bundle.deployment["deployment_id"],
        "task_kind": task_kind,
        "task_index": -1 if task_index is None else task_index,
        "slate_id": plan.task_id if task_index is None else _parametric_slate(
            bundle, task_index
        ),
        "plan_sha256": plan.plan_sha256,
        "core_load_result": dict(core_result),
        "post_load_verification": dict(verification),
        "idempotent": True,
        "gcs_remains_authoritative": True,
        "world_matrices_stored_in_graph": False,
        "raw_outcomes_stored_in_graph": False,
        "automatic_policy_feedback": False,
        "corpus_population_mutation_authority": False,
        "production_policy_authority": False,
    }
    return _with_self_hash(body, field="governed_load_result_sha256")


def _parametric_slate(bundle: ValidatedLoadBundle, task_index: int) -> str:
    parametric = _mapping(bundle.manifest.get("parametric"), label="parametric manifest")
    tasks = _sequence(parametric["tasks"], label="parametric tasks")
    if not 0 <= task_index < len(tasks):
        raise CorpusNeo4jTransportError("parametric task index differs")
    row = _mapping(tasks[task_index], label=f"parametric task[{task_index}]")
    if row.get("task_index") != task_index:
        raise CorpusNeo4jTransportError("parametric task order differs")
    return str(row["slate_id"])


def _plan_for_task(
    bundle: ValidatedLoadBundle, *, task_index: int | None,
) -> Neo4jLoadPlan:
    if task_index is None:
        return bundle.retrieval_plan
    if (
        type(task_index) is not int
        or not 0 <= task_index < 54
        or len(bundle.parametric_plans) != 54
    ):
        raise CorpusNeo4jTransportError(
            "complete 54-task graph manifest and index 0..53 are required"
        )
    return bundle.parametric_plans[task_index]


def _validate_plan_verification(
    value: object, *, plan: Neo4jLoadPlan,
) -> dict[str, object]:
    item = dict(_mapping(value, label="graph plan verification"))
    expected = {
        "plan_sha256": plan.plan_sha256,
        "verified_node_count": len(plan.nodes),
        "verified_relationship_count": len(plan.relationships),
        "exact": True,
    }
    if item != expected:
        raise CorpusNeo4jTransportError("graph plan verification differs")
    return item


def _validate_existing_load_receipt(
    raw: bytes, *, bundle: ValidatedLoadBundle, plan: Neo4jLoadPlan,
    task_index: int | None,
) -> dict[str, object]:
    item = _json(raw, label="graph load receipt")
    _self_hash(item, field="governed_load_result_sha256", label="graph load receipt")
    expected_core = build_load_result_receipt(
        plan,
        database=str(bundle.deployment["database"]),
        node_count=len(plan.nodes),
        relationship_count=len(plan.relationships),
    )
    if (
        item.get("schema_version") != LOAD_RECEIPT_SCHEMA
        or item.get("deployment_manifest") != bundle.deployment_identity.as_dict()
        or bundle.manifest_identity is None
        or item.get("load_manifest") != bundle.manifest_identity.as_dict()
        or item.get("deployment_id") != bundle.deployment["deployment_id"]
        or item.get("task_kind")
        != ("retrieval-task0" if task_index is None else "parametric-task")
        or item.get("task_index") != (-1 if task_index is None else task_index)
        or item.get("slate_id")
        != (
            plan.task_id if task_index is None
            else _parametric_slate(bundle, task_index)
        )
        or item.get("plan_sha256") != plan.plan_sha256
        or item.get("core_load_result") != expected_core
        or item.get("idempotent") is not True
        or item.get("gcs_remains_authoritative") is not True
        or item.get("world_matrices_stored_in_graph") is not False
        or item.get("raw_outcomes_stored_in_graph") is not False
        or item.get("automatic_policy_feedback") is not False
        or item.get("corpus_population_mutation_authority") is not False
        or item.get("production_policy_authority") is not False
    ):
        raise CorpusNeo4jTransportError("graph load receipt binding differs")
    _validate_plan_verification(item.get("post_load_verification"), plan=plan)
    return item


def _validate_bootstrap_receipt(
    raw: bytes, *, bundle: ValidatedLoadBundle,
) -> dict[str, object]:
    item = _json(raw, label="schema bootstrap receipt")
    _self_hash(item, field="schema_bootstrap_sha256", label="schema bootstrap receipt")
    expected_hashes = [
        sha256(statement.encode("utf-8")).hexdigest()
        for statement in SCHEMA_STATEMENTS
    ]
    if (
        item.get("schema_version") != BOOTSTRAP_RECEIPT_SCHEMA
        or item.get("publication_mode") != "create_once"
        or item.get("deployment_manifest") != bundle.deployment_identity.as_dict()
        or bundle.manifest_identity is None
        or item.get("load_manifest") != bundle.manifest_identity.as_dict()
        or item.get("deployment_id") != bundle.deployment["deployment_id"]
        or item.get("database") != bundle.deployment["database"]
        or item.get("component") != bundle.deployment["server"]
        or item.get("initial_empty_census")
        != bundle.deployment["initial_empty_census"]
        or item.get("post_schema_census")
        != bundle.deployment["initial_empty_census"]
        or item.get("schema_statement_sha256s") != expected_hashes
        or item.get("separate_bootstrap_principal_required") is not True
        or item.get("routine_writer_schema_mutation_forbidden") is not True
    ):
        raise CorpusNeo4jTransportError("schema bootstrap receipt differs")
    return item


def bootstrap_schema(
    *, storage: ExactObjectStore, graph: GraphBackend,
    bundle: ValidatedLoadBundle,
) -> dict[str, object]:
    if bundle.manifest_identity is None:
        raise CorpusNeo4jTransportError("published load manifest identity is required")
    uri = str(_mapping(bundle.manifest["receipt_uris"], label="receipt URIs")["bootstrap"])
    existing = storage.resolve_optional(uri)
    if existing is not None:
        _, raw = existing
        return _validate_bootstrap_receipt(raw, bundle=bundle)
    component = _validate_component(bundle.deployment, graph.component())
    before = _require_allowed_census(
        bundle.deployment, graph.census(), initially_empty=True
    )
    graph.bootstrap_schema(SCHEMA_STATEMENTS)
    after = _require_allowed_census(
        bundle.deployment, graph.census(), initially_empty=False
    )
    if after["node_count"] != 0 or after["relationship_count"] != 0:
        raise CorpusNeo4jTransportError("schema bootstrap created graph data")
    body = {
        "schema_version": BOOTSTRAP_RECEIPT_SCHEMA,
        "publication_mode": "create_once",
        "deployment_manifest": bundle.deployment_identity.as_dict(),
        "load_manifest": bundle.manifest_identity.as_dict(),
        "deployment_id": bundle.deployment["deployment_id"],
        "database": graph.database,
        "component": component,
        "initial_empty_census": before,
        "post_schema_census": after,
        "schema_statement_sha256s": [
            sha256(statement.encode("utf-8")).hexdigest()
            for statement in SCHEMA_STATEMENTS
        ],
        "separate_bootstrap_principal_required": True,
        "routine_writer_schema_mutation_forbidden": True,
    }
    receipt = _with_self_hash(body, field="schema_bootstrap_sha256")
    storage.publish_create_once(uri, canonical_json_bytes(receipt))
    return receipt


def _require_bootstrap(storage: ExactObjectStore, bundle: ValidatedLoadBundle) -> None:
    uri = str(_mapping(bundle.manifest["receipt_uris"], label="receipt URIs")["bootstrap"])
    existing = storage.resolve_optional(uri)
    if existing is None:
        raise CorpusNeo4jTransportError("schema bootstrap receipt is absent")
    _, raw = existing
    _validate_bootstrap_receipt(raw, bundle=bundle)


def load_plan(
    *, storage: ExactObjectStore, graph: GraphBackend,
    bundle: ValidatedLoadBundle, task_index: int | None,
) -> dict[str, object]:
    plan = _plan_for_task(bundle, task_index=task_index)
    _require_bootstrap(storage, bundle)
    uri = _receipt_uri(bundle, task_index=task_index)
    existing = storage.resolve_optional(uri)
    if existing is not None:
        _, raw = existing
        return _validate_existing_load_receipt(
            raw, bundle=bundle, plan=plan, task_index=task_index
        )
    _validate_component(bundle.deployment, graph.component())
    _require_allowed_census(bundle.deployment, graph.census(), initially_empty=False)
    core = dict(graph.apply(plan))
    expected_core = build_load_result_receipt(
        plan,
        database=str(bundle.deployment["database"]),
        node_count=len(plan.nodes),
        relationship_count=len(plan.relationships),
    )
    if core != expected_core:
        raise CorpusNeo4jTransportError("core graph load result differs")
    verification = _validate_plan_verification(graph.verify(plan), plan=plan)
    _require_allowed_census(bundle.deployment, graph.census(), initially_empty=False)
    receipt = _load_receipt(
        bundle=bundle, plan=plan, core_result=core,
        verification=verification, task_index=task_index,
    )
    storage.publish_create_once(uri, canonical_json_bytes(receipt))
    return receipt


def recover_plan_receipt(
    *, storage: ExactObjectStore, graph: GraphBackend,
    bundle: ValidatedLoadBundle, task_index: int | None,
) -> dict[str, object]:
    """Publish a missing receipt only after exact read-only graph replay."""
    plan = _plan_for_task(bundle, task_index=task_index)
    _require_bootstrap(storage, bundle)
    uri = _receipt_uri(bundle, task_index=task_index)
    existing = storage.resolve_optional(uri)
    if existing is not None:
        _, raw = existing
        return _validate_existing_load_receipt(
            raw, bundle=bundle, plan=plan, task_index=task_index
        )
    _validate_component(bundle.deployment, graph.component())
    _require_allowed_census(bundle.deployment, graph.census(), initially_empty=False)
    verification = _validate_plan_verification(graph.verify(plan), plan=plan)
    core = build_load_result_receipt(
        plan,
        database=graph.database,
        node_count=len(plan.nodes),
        relationship_count=len(plan.relationships),
    )
    receipt = _load_receipt(
        bundle=bundle, plan=plan, core_result=core,
        verification=verification, task_index=task_index,
    )
    storage.publish_create_once(uri, canonical_json_bytes(receipt))
    return receipt


def _publish_strategy_projection_receipt(
    *, storage: ExactObjectStore, bundle: ValidatedLoadBundle,
) -> tuple[ObjectIdentity, dict[str, object]]:
    from nfl_dfs.research import corpus_strategy_registry as registry

    if bundle.manifest_identity is None:
        raise CorpusNeo4jTransportError("published load manifest identity is required")
    resolved_load = storage.resolve_optional(_strategy_registry_load_uri(bundle))
    if resolved_load is None:
        raise CorpusNeo4jTransportError("strategy registry load receipt is absent")
    load_identity, load_raw = resolved_load
    _validate_existing_strategy_registry_load_receipt(load_raw, bundle=bundle)
    try:
        expected = registry.build_projection_receipt(
            bundle.strategy_registry_bundle,
            governed_load_manifest=bundle.manifest_identity.as_dict(),
            governed_registry_load_receipt=load_identity.as_dict(),
        )
    except registry.CorpusStrategyRegistryError as exc:
        raise CorpusNeo4jTransportError(
            f"strategy registry projection receipt differs: {exc}"
        ) from exc
    uri = str(_mapping(bundle.manifest["receipt_uris"], label="receipt URIs")[
        "strategy_registry_projection"
    ])
    existing = storage.resolve_optional(uri)
    if existing is not None:
        identity, raw = existing
        if _json(raw, label="strategy registry projection receipt") != expected:
            raise CorpusNeo4jTransportError(
                "strategy registry projection receipt binding differs"
            )
        return identity, expected
    identity = storage.publish_create_once(uri, canonical_json_bytes(expected))
    return identity, expected


def load_strategy_registry(
    *, storage: ExactObjectStore, graph: GraphBackend,
    bundle: ValidatedLoadBundle,
) -> dict[str, object]:
    """Idempotently load the outcome-blind v2 registry after retrieval task 0."""
    _require_bootstrap(storage, bundle)
    retrieval = storage.resolve_optional(_receipt_uri(bundle, task_index=None))
    if retrieval is None:
        raise CorpusNeo4jTransportError(
            "accepted retrieval graph load is required before the strategy registry"
        )
    _validate_existing_load_receipt(
        retrieval[1],
        bundle=bundle,
        plan=bundle.retrieval_plan,
        task_index=None,
    )
    uri = _strategy_registry_load_uri(bundle)
    existing = storage.resolve_optional(uri)
    if existing is not None:
        receipt = _validate_existing_strategy_registry_load_receipt(
            existing[1], bundle=bundle
        )
        _publish_strategy_projection_receipt(storage=storage, bundle=bundle)
        return receipt
    plan = _strategy_registry_plan(bundle)
    _validate_component(bundle.deployment, graph.component())
    _require_allowed_census(bundle.deployment, graph.census(), initially_empty=False)
    core = dict(graph.apply(plan))
    expected_core = build_load_result_receipt(
        plan,
        database=str(bundle.deployment["database"]),
        node_count=len(plan.nodes),
        relationship_count=len(plan.relationships),
    )
    if core != expected_core:
        raise CorpusNeo4jTransportError("strategy registry core load result differs")
    verification = _validate_plan_verification(graph.verify(plan), plan=plan)
    _require_allowed_census(bundle.deployment, graph.census(), initially_empty=False)
    receipt = _strategy_registry_load_receipt(
        bundle=bundle, core_result=core, verification=verification
    )
    storage.publish_create_once(uri, canonical_json_bytes(receipt))
    _publish_strategy_projection_receipt(storage=storage, bundle=bundle)
    return receipt


def recover_strategy_registry_receipt(
    *, storage: ExactObjectStore, graph: GraphBackend,
    bundle: ValidatedLoadBundle,
) -> dict[str, object]:
    """Recover only after an exact read-only replay of the full registry plan."""
    _require_bootstrap(storage, bundle)
    retrieval = storage.resolve_optional(_receipt_uri(bundle, task_index=None))
    if retrieval is None:
        raise CorpusNeo4jTransportError(
            "accepted retrieval graph load is required before registry recovery"
        )
    _validate_existing_load_receipt(
        retrieval[1],
        bundle=bundle,
        plan=bundle.retrieval_plan,
        task_index=None,
    )
    uri = _strategy_registry_load_uri(bundle)
    existing = storage.resolve_optional(uri)
    if existing is not None:
        receipt = _validate_existing_strategy_registry_load_receipt(
            existing[1], bundle=bundle
        )
        _publish_strategy_projection_receipt(storage=storage, bundle=bundle)
        return receipt
    plan = _strategy_registry_plan(bundle)
    _validate_component(bundle.deployment, graph.component())
    _require_allowed_census(bundle.deployment, graph.census(), initially_empty=False)
    verification = _validate_plan_verification(graph.verify(plan), plan=plan)
    core = build_load_result_receipt(
        plan,
        database=graph.database,
        node_count=len(plan.nodes),
        relationship_count=len(plan.relationships),
    )
    receipt = _strategy_registry_load_receipt(
        bundle=bundle, core_result=core, verification=verification
    )
    storage.publish_create_once(uri, canonical_json_bytes(receipt))
    _publish_strategy_projection_receipt(storage=storage, bundle=bundle)
    return receipt


def query_strategy_registry(
    *, storage: ExactObjectStore, graph: GraphBackend,
    bundle: ValidatedLoadBundle,
) -> dict[str, object]:
    """Run the bounded registry catalog through the dedicated reader role."""
    from nfl_dfs.research import corpus_strategy_registry as registry

    if bundle.manifest_identity is None:
        raise CorpusNeo4jTransportError("published load manifest identity is required")
    load_resolved = storage.resolve_optional(_strategy_registry_load_uri(bundle))
    if load_resolved is None:
        raise CorpusNeo4jTransportError("strategy registry load receipt is absent")
    load_identity, load_raw = load_resolved
    _validate_existing_strategy_registry_load_receipt(load_raw, bundle=bundle)
    projection_identity, _ = _publish_strategy_projection_receipt(
        storage=storage, bundle=bundle
    )
    uri = str(_mapping(bundle.manifest["receipt_uris"], label="receipt URIs")[
        "strategy_registry_query"
    ])
    existing = storage.resolve_optional(uri)
    if existing is not None:
        item = _json(existing[1], label="strategy registry query receipt")
        try:
            registry.validate_registry_receipt(
                bundle=bundle.strategy_registry_bundle, receipt=item
            )
        except registry.CorpusStrategyRegistryError as exc:
            raise CorpusNeo4jTransportError(
                f"strategy registry query receipt binding differs: {exc}"
            ) from exc
        if (
            item["governed_load_manifest"] != bundle.manifest_identity.as_dict()
            or item["governed_registry_load_receipt"] != load_identity.as_dict()
            or item["registry_projection_receipt"] != projection_identity.as_dict()
            or item["query_catalog_sha256"]
            != _mapping(bundle.manifest["strategy_registry"], label="registry")[
                "query_catalog_sha256"
            ]
        ):
            raise CorpusNeo4jTransportError(
                "strategy registry query receipt binding differs"
            )
        return item
    try:
        receipt = registry.run_read_only_traversal_receipt(
            bundle=bundle.strategy_registry_bundle,
            database=graph.database,
            query_runner=graph.run_read_only_query,
            governed_load_manifest=bundle.manifest_identity.as_dict(),
            governed_registry_load_receipt=load_identity.as_dict(),
            registry_projection_receipt=projection_identity.as_dict(),
        )
    except registry.CorpusStrategyRegistryError as exc:
        raise CorpusNeo4jTransportError(
            f"strategy registry read-only query differs: {exc}"
        ) from exc
    registry_manifest = _mapping(
        bundle.manifest["strategy_registry"], label="strategy registry manifest"
    )
    if (
        receipt.get("query_catalog_sha256")
        != registry_manifest["query_catalog_sha256"]
        or receipt.get("plan_sha256") != registry_manifest["plan_sha256"]
    ):
        raise CorpusNeo4jTransportError("strategy registry query catalog differs")
    try:
        registry.validate_registry_receipt(
            bundle=bundle.strategy_registry_bundle, receipt=receipt
        )
    except registry.CorpusStrategyRegistryError as exc:
        raise CorpusNeo4jTransportError(
            f"strategy registry query receipt differs: {exc}"
        ) from exc
    storage.publish_create_once(uri, canonical_json_bytes(receipt))
    return receipt


def load_parametric_suite(
    *, storage: ExactObjectStore, graph: GraphBackend,
    bundle: ValidatedLoadBundle,
) -> dict[str, object]:
    if len(bundle.parametric_plans) != 54:
        raise CorpusNeo4jTransportError("complete 54-task graph manifest is required")
    retrieval_uri = _receipt_uri(bundle, task_index=None)
    if storage.resolve_optional(retrieval_uri) is None:
        raise CorpusNeo4jTransportError("accepted retrieval graph load is required first")
    rows = [
        load_plan(
            storage=storage, graph=graph, bundle=bundle, task_index=task_index
        )
        for task_index in range(54)
    ]
    return {
        "schema_version": "corpus-neo4j-parametric-load-pass/v1",
        "task_count": len(rows),
        "task_indexes": list(range(54)),
        "all_task_receipts_present": True,
        "automatic_science_retry": False,
    }


def _validate_suite_census(
    value: object, *, bundle: ValidatedLoadBundle,
) -> dict[str, object]:
    item = dict(_mapping(value, label="parametric suite census"))
    expected_keys = {
        "batch_id", "task_count", "arm_count", "task_indexes", "slate_ids",
        "registry_id", "registry_node_count", "registry_relationship_count",
        "registry_kind_counts", "workstream_namespaces",
        "reserved_population_node_count", "reserved_realized_outcome_node_count",
    }
    if set(item) != expected_keys:
        raise CorpusNeo4jTransportError("parametric suite census schema differs")
    parametric = _mapping(bundle.manifest.get("parametric"), label="parametric manifest")
    expected_slates = [
        str(_mapping(row, label="parametric task")["slate_id"])
        for row in _sequence(parametric["tasks"], label="parametric tasks")
    ]
    registry = _mapping(
        bundle.manifest["strategy_registry"], label="strategy registry manifest"
    )
    if (
        item["batch_id"] != parametric["batch_id"]
        or item["task_count"] != 54
        or item["arm_count"] != 378
        or item["task_indexes"] != list(range(54))
        or item["slate_ids"] != expected_slates
        or item["workstream_namespaces"]
        != [
            PARAMETRIC_NAMESPACE,
            RETRIEVAL_NAMESPACE,
            STRATEGY_REGISTRY_NAMESPACE,
        ]
        or item["registry_id"] != registry["registry_id"]
        or item["registry_node_count"] != registry["registry_node_count"]
        or item["registry_relationship_count"]
        != registry["registry_relationship_count"]
        or item["registry_kind_counts"] != registry["kind_counts"]
        or item["reserved_population_node_count"] != 0
        or item["reserved_realized_outcome_node_count"] != 0
    ):
        raise CorpusNeo4jTransportError("parametric suite census is incomplete")
    return item


def _validate_suite_terminal(
    raw: bytes, *, bundle: ValidatedLoadBundle,
) -> dict[str, object]:
    item = _json(raw, label="graph suite terminal")
    _self_hash(item, field="suite_terminal_sha256", label="graph suite terminal")
    retrieval_identity = object_identity(
        item.get("retrieval_load_receipt"),
        label="suite retrieval load receipt",
    )
    task_identities = _sequence(
        item.get("parametric_task_load_receipts"),
        label="suite parametric load receipts",
    )
    if len(task_identities) != 54:
        raise CorpusNeo4jTransportError("graph suite terminal receipt coverage differs")
    for ordinal, value in enumerate(task_identities):
        object_identity(value, label=f"suite parametric receipt[{ordinal}]")
    registry_load_identity = object_identity(
        item.get("strategy_registry_load_receipt"),
        label="suite strategy registry load receipt",
    )
    registry_projection_identity = object_identity(
        item.get("strategy_registry_projection_receipt"),
        label="suite strategy registry projection receipt",
    )
    registry_query_identity = object_identity(
        item.get("strategy_registry_query_receipt"),
        label="suite strategy registry query receipt",
    )
    census = _validate_suite_census(item.get("suite_census"), bundle=bundle)
    if (
        item.get("schema_version") != SUITE_RECEIPT_SCHEMA
        or item.get("publication_mode") != "create_once"
        or item.get("deployment_manifest") != bundle.deployment_identity.as_dict()
        or bundle.manifest_identity is None
        or item.get("load_manifest") != bundle.manifest_identity.as_dict()
        or item.get("deployment_id") != bundle.deployment["deployment_id"]
        or item.get("database") != bundle.deployment["database"]
        or item.get("component") != bundle.deployment["server"]
        or retrieval_identity.uri != _receipt_uri(bundle, task_index=None)
        or registry_load_identity.uri != _strategy_registry_load_uri(bundle)
        or registry_projection_identity.uri
        != _mapping(bundle.manifest["receipt_uris"], label="receipt URIs")[
            "strategy_registry_projection"
        ]
        or registry_query_identity.uri
        != _mapping(bundle.manifest["receipt_uris"], label="receipt URIs")[
            "strategy_registry_query"
        ]
        or item.get("suite_census") != census
        or item.get("task_count") != 54
        or item.get("parameter_set_count") != 7
        or item.get("matrix_cell_count") != 378
        or item.get("complete") is not True
        or item.get("gcs_remains_authoritative") is not True
        or item.get("world_matrices_stored_in_graph") is not False
        or item.get("raw_outcomes_stored_in_graph") is not False
        or item.get("uses_realized_outcomes") is not False
        or item.get("automatic_policy_feedback") is not False
        or item.get("corpus_population_mutation_authority") is not False
        or item.get("production_policy_authority") is not False
    ):
        raise CorpusNeo4jTransportError("graph suite terminal differs")
    return item


def finish_suite(
    *, storage: ExactObjectStore, graph: GraphBackend,
    bundle: ValidatedLoadBundle,
) -> dict[str, object]:
    if len(bundle.parametric_plans) != 54:
        raise CorpusNeo4jTransportError("complete 54-task graph manifest is required")
    if bundle.manifest_identity is None:
        raise CorpusNeo4jTransportError("published load manifest identity is required")
    receipts = _mapping(bundle.manifest["receipt_uris"], label="receipt URIs")
    terminal_uri = str(receipts["suite_terminal"])
    existing_terminal = storage.resolve_optional(terminal_uri)
    if existing_terminal is not None:
        _, raw = existing_terminal
        return _validate_suite_terminal(raw, bundle=bundle)
    retrieval_identity, retrieval_raw = storage.resolve_optional(
        _receipt_uri(bundle, task_index=None)
    ) or (None, None)
    if retrieval_identity is None or retrieval_raw is None:
        raise CorpusNeo4jTransportError("retrieval load receipt is absent")
    _validate_existing_load_receipt(
        retrieval_raw, bundle=bundle, plan=bundle.retrieval_plan, task_index=None
    )
    task_receipt_identities: list[dict[str, object]] = []
    for task_index, plan in enumerate(bundle.parametric_plans):
        resolved = storage.resolve_optional(_receipt_uri(bundle, task_index=task_index))
        if resolved is None:
            raise CorpusNeo4jTransportError(
                f"parametric graph load receipt {task_index} is absent"
            )
        identity, raw = resolved
        _validate_existing_load_receipt(
            raw, bundle=bundle, plan=plan, task_index=task_index
        )
        task_receipt_identities.append(identity.as_dict())
    registry_load_resolved = storage.resolve_optional(
        _strategy_registry_load_uri(bundle)
    )
    if registry_load_resolved is None:
        raise CorpusNeo4jTransportError("strategy registry load receipt is absent")
    registry_load_identity, registry_load_raw = registry_load_resolved
    _validate_existing_strategy_registry_load_receipt(
        registry_load_raw, bundle=bundle
    )
    receipts_map = _mapping(bundle.manifest["receipt_uris"], label="receipt URIs")
    registry_projection_resolved = storage.resolve_optional(
        str(receipts_map["strategy_registry_projection"])
    )
    registry_query_resolved = storage.resolve_optional(
        str(receipts_map["strategy_registry_query"])
    )
    if registry_projection_resolved is None or registry_query_resolved is None:
        raise CorpusNeo4jTransportError(
            "strategy registry projection/query receipt chain is incomplete"
        )
    _publish_strategy_projection_receipt(storage=storage, bundle=bundle)
    query_body = _json(
        registry_query_resolved[1], label="strategy registry query receipt"
    )
    from nfl_dfs.research import corpus_strategy_registry as registry
    try:
        registry.validate_registry_receipt(
            bundle=bundle.strategy_registry_bundle, receipt=query_body
        )
    except registry.CorpusStrategyRegistryError as exc:
        raise CorpusNeo4jTransportError(
            f"strategy registry query receipt differs: {exc}"
        ) from exc
    if (
        query_body.get("governed_registry_load_receipt")
        != registry_load_identity.as_dict()
        or query_body.get("registry_projection_receipt")
        != registry_projection_resolved[0].as_dict()
        or query_body.get("uses_realized_outcomes") is not False
        or query_body.get("graph_mutation") is not False
    ):
        raise CorpusNeo4jTransportError(
            "strategy registry query receipt chain differs"
        )
    component = _validate_component(bundle.deployment, graph.component())
    census = _validate_suite_census(
        graph.suite_census(
            batch_id=str(_mapping(bundle.manifest["parametric"], label="parametric")["batch_id"]),
            registry_id=str(_mapping(
                bundle.manifest["strategy_registry"], label="strategy registry"
            )["registry_id"]),
        ),
        bundle=bundle,
    )
    _require_allowed_census(bundle.deployment, graph.census(), initially_empty=False)
    body = {
        "schema_version": SUITE_RECEIPT_SCHEMA,
        "publication_mode": "create_once",
        "deployment_manifest": bundle.deployment_identity.as_dict(),
        "load_manifest": bundle.manifest_identity.as_dict(),
        "deployment_id": bundle.deployment["deployment_id"],
        "database": graph.database,
        "component": component,
        "retrieval_load_receipt": retrieval_identity.as_dict(),
        "parametric_task_load_receipts": task_receipt_identities,
        "strategy_registry_load_receipt": registry_load_identity.as_dict(),
        "strategy_registry_projection_receipt": (
            registry_projection_resolved[0].as_dict()
        ),
        "strategy_registry_query_receipt": registry_query_resolved[0].as_dict(),
        "suite_census": census,
        "task_count": 54,
        "parameter_set_count": 7,
        "matrix_cell_count": 378,
        "complete": True,
        "gcs_remains_authoritative": True,
        "world_matrices_stored_in_graph": False,
        "raw_outcomes_stored_in_graph": False,
        "uses_realized_outcomes": False,
        "automatic_policy_feedback": False,
        "corpus_population_mutation_authority": False,
        "production_policy_authority": False,
    }
    receipt = _with_self_hash(body, field="suite_terminal_sha256")
    storage.publish_create_once(terminal_uri, canonical_json_bytes(receipt))
    return receipt


def query_smoke(
    *, storage: ExactObjectStore, graph: GraphBackend,
    bundle: ValidatedLoadBundle, require_complete_suite: bool,
) -> dict[str, object]:
    if bundle.manifest_identity is None:
        raise CorpusNeo4jTransportError("published load manifest identity is required")
    receipts = _mapping(bundle.manifest["receipt_uris"], label="receipt URIs")
    if require_complete_suite:
        terminal = storage.resolve_optional(str(receipts["suite_terminal"]))
        if terminal is None:
            raise CorpusNeo4jTransportError("complete graph suite terminal is absent")
        _, terminal_raw = terminal
        _validate_suite_terminal(terminal_raw, bundle=bundle)
    result = dict(graph.query_smoke(
        run_id=bundle.retrieval_plan.run_id,
        task_id=bundle.retrieval_plan.task_id,
    ))
    expected_counts = {
        kind: sum(row["kind"] == kind for row in bundle.retrieval_plan.nodes)
        for kind in (
            "LineupCandidate", "CorpusAssociationMeasurement",
            "CorpusCorrelationMeasurement", "CorpusStrategySplitMeasurement",
            "CorpusArtifactPointer",
        )
    }
    expected_result = {
        "retrieval_kind_counts": expected_counts,
        "reserved_population_node_count": 0,
        "reserved_realized_outcome_node_count": 0,
        "read_only": True,
    }
    if result != expected_result:
        raise CorpusNeo4jTransportError("read-only graph query smoke differs")
    body = {
        "schema_version": QUERY_SMOKE_SCHEMA,
        "publication_mode": "create_once",
        "deployment_manifest": bundle.deployment_identity.as_dict(),
        "load_manifest": bundle.manifest_identity.as_dict(),
        "require_complete_suite": require_complete_suite,
        "query_catalog_sha256": sha256(
            ("high-tail|enrichment|correlation|strategy|population-firewall")
            .encode("utf-8")
        ).hexdigest(),
        "result": result,
        "gcs_remains_authoritative": True,
        "graph_mutation": False,
        "uses_realized_outcomes": False,
        "outcome_namespace_read": False,
        "production_policy_authority": False,
    }
    receipt = _with_self_hash(body, field="query_smoke_sha256")
    receipt_key = (
        "query_smoke_complete" if require_complete_suite else "query_smoke_task0"
    )
    storage.publish_create_once(
        str(receipts[receipt_key]), canonical_json_bytes(receipt)
    )
    return receipt


def _validate_query_smoke_receipt(
    raw: bytes, *, bundle: ValidatedLoadBundle, require_complete_suite: bool,
) -> dict[str, object]:
    item = _json(raw, label="graph query smoke receipt")
    _self_hash(item, field="query_smoke_sha256", label="graph query smoke receipt")
    if (
        item.get("schema_version") != QUERY_SMOKE_SCHEMA
        or item.get("publication_mode") != "create_once"
        or item.get("deployment_manifest") != bundle.deployment_identity.as_dict()
        or bundle.manifest_identity is None
        or item.get("load_manifest") != bundle.manifest_identity.as_dict()
        or item.get("require_complete_suite") is not require_complete_suite
        or item.get("gcs_remains_authoritative") is not True
        or item.get("graph_mutation") is not False
        or item.get("uses_realized_outcomes") is not False
        or item.get("outcome_namespace_read") is not False
        or item.get("production_policy_authority") is not False
    ):
        raise CorpusNeo4jTransportError("graph query smoke receipt differs")
    return item


def _resolve_operation_receipts(
    *,
    storage: ExactObjectStore,
    bundle: ValidatedLoadBundle,
    operation: str,
    task_index: int | None,
    require_complete_suite: bool,
) -> list[dict[str, object]]:
    receipts = _mapping(bundle.manifest["receipt_uris"], label="receipt URIs")

    def resolve(uri: str, *, label: str) -> tuple[ObjectIdentity, bytes]:
        result = storage.resolve_optional(uri)
        if result is None:
            raise CorpusNeo4jTransportError(f"{label} is absent after terminal execution")
        return result

    retained: list[ObjectIdentity] = []
    if operation == "bootstrap-schema":
        identity, raw = resolve(str(receipts["bootstrap"]), label="bootstrap receipt")
        _validate_bootstrap_receipt(raw, bundle=bundle)
        retained.append(identity)
    elif operation in {"load-task0", "recover-task0-receipt"}:
        identity, raw = resolve(
            _receipt_uri(bundle, task_index=None), label="task0 load receipt"
        )
        _validate_existing_load_receipt(
            raw,
            bundle=bundle,
            plan=bundle.retrieval_plan,
            task_index=None,
        )
        retained.append(identity)
    elif operation in {"load-parametric-task", "recover-parametric-receipt"}:
        plan = _plan_for_task(bundle, task_index=task_index)
        identity, raw = resolve(
            _receipt_uri(bundle, task_index=task_index),
            label=f"parametric task {task_index} load receipt",
        )
        _validate_existing_load_receipt(
            raw,
            bundle=bundle,
            plan=plan,
            task_index=task_index,
        )
        retained.append(identity)
    elif operation in {
        "load-strategy-registry", "recover-strategy-registry-receipt",
    }:
        identity, raw = resolve(
            _strategy_registry_load_uri(bundle),
            label="strategy registry load receipt",
        )
        _validate_existing_strategy_registry_load_receipt(raw, bundle=bundle)
        retained.append(identity)
        projection_uri = str(receipts["strategy_registry_projection"])
        projection_identity, projection_raw = resolve(
            projection_uri, label="strategy registry projection receipt"
        )
        expected_projection_identity, expected_projection = (
            _publish_strategy_projection_receipt(storage=storage, bundle=bundle)
        )
        if (
            projection_identity != expected_projection_identity
            or _json(projection_raw, label="strategy registry projection receipt")
            != expected_projection
        ):
            raise CorpusNeo4jTransportError(
                "strategy registry projection receipt differs"
            )
        retained.append(projection_identity)
    elif operation == "load-suite":
        if len(bundle.parametric_plans) != 54:
            raise CorpusNeo4jTransportError("complete suite graph manifest is required")
        for index, plan in enumerate(bundle.parametric_plans):
            identity, raw = resolve(
                _receipt_uri(bundle, task_index=index),
                label=f"parametric task {index} load receipt",
            )
            _validate_existing_load_receipt(
                raw, bundle=bundle, plan=plan, task_index=index
            )
            retained.append(identity)
    elif operation == "finish-suite":
        identity, raw = resolve(
            str(receipts["suite_terminal"]), label="suite terminal"
        )
        _validate_suite_terminal(raw, bundle=bundle)
        retained.append(identity)
    elif operation == "query-smoke":
        key = (
            "query_smoke_complete"
            if require_complete_suite else "query_smoke_task0"
        )
        identity, raw = resolve(str(receipts[key]), label="query smoke receipt")
        _validate_query_smoke_receipt(
            raw,
            bundle=bundle,
            require_complete_suite=require_complete_suite,
        )
        retained.append(identity)
    elif operation == "query-strategy-registry":
        load_identity, load_raw = resolve(
            _strategy_registry_load_uri(bundle),
            label="strategy registry load receipt",
        )
        _validate_existing_strategy_registry_load_receipt(
            load_raw, bundle=bundle
        )
        projection_identity, projection_raw = resolve(
            str(receipts["strategy_registry_projection"]),
            label="strategy registry projection receipt",
        )
        query_identity, query_raw = resolve(
            str(receipts["strategy_registry_query"]),
            label="strategy registry query receipt",
        )
        query_body = _json(query_raw, label="strategy registry query receipt")
        from nfl_dfs.research import corpus_strategy_registry as registry
        try:
            registry.validate_registry_receipt(
                bundle=bundle.strategy_registry_bundle, receipt=query_body
            )
        except registry.CorpusStrategyRegistryError as exc:
            raise CorpusNeo4jTransportError(
                f"strategy registry query receipt differs: {exc}"
            ) from exc
        if (
            query_body.get("governed_registry_load_receipt")
            != load_identity.as_dict()
            or query_body.get("registry_projection_receipt")
            != projection_identity.as_dict()
            or query_body.get("graph_mutation") is not False
            or query_body.get("uses_realized_outcomes") is not False
        ):
            raise CorpusNeo4jTransportError(
                "strategy registry query receipt differs"
            )
        _json(projection_raw, label="strategy registry projection receipt")
        retained.extend((load_identity, projection_identity, query_identity))
    else:  # pragma: no cover - operation domain is checked before dispatch
        raise CorpusNeo4jTransportError("graph operation differs")
    return [identity.as_dict() for identity in retained]


def _validate_execution_binding(
    raw: bytes,
    *,
    bundle: ValidatedLoadBundle,
    intent_identity: ObjectIdentity,
    operation: str,
    task_index: int | None,
    require_complete_suite: bool,
) -> dict[str, object]:
    item = _json(raw, label="graph execution binding")
    _self_hash(item, field="execution_binding_sha256", label="graph execution binding")
    if (
        item.get("schema_version") != EXECUTION_BINDING_SCHEMA
        or item.get("publication_mode") != "create_once"
        or item.get("deployment_manifest") != bundle.deployment_identity.as_dict()
        or bundle.manifest_identity is None
        or item.get("load_manifest") != bundle.manifest_identity.as_dict()
        or item.get("launch_intent") != intent_identity.as_dict()
        or item.get("operation") != operation
        or item.get("task_index") != (-1 if task_index is None else task_index)
        or item.get("require_complete_suite") is not require_complete_suite
        or item.get("sole_new_execution") is not True
        or item.get("automatic_retry_licensed") is not False
    ):
        raise CorpusNeo4jTransportError("graph execution binding differs")
    return item


def finish_launch_execution(
    *,
    storage: ExactObjectStore,
    bundle: ValidatedLoadBundle,
    operation: str,
    task_index: int | None,
    require_complete_suite: bool,
    execution: object,
    created_at_utc: str,
) -> dict[str, object]:
    """Accept one terminal execution only after its exact GCS receipt exists."""
    intent_uri = _launch_uri(
        bundle,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
        leaf="intent.json",
    )
    binding_uri = _launch_uri(
        bundle,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
        leaf="execution-binding.json",
    )
    terminal_uri = _launch_uri(
        bundle,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
        leaf="terminal.json",
    )
    resolved_intent = storage.resolve_optional(intent_uri)
    resolved_binding = storage.resolve_optional(binding_uri)
    if resolved_intent is None or resolved_binding is None:
        raise CorpusNeo4jTransportError("launch intent/execution binding is absent")
    intent_identity, intent_raw = resolved_intent
    binding_identity, binding_raw = resolved_binding
    _validate_launch_intent(
        intent_raw,
        bundle=bundle,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
    )
    binding = _validate_execution_binding(
        binding_raw,
        bundle=bundle,
        intent_identity=intent_identity,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
    )
    existing = storage.resolve_optional(terminal_uri)
    if existing is not None:
        identity, raw = existing
        item = _json(raw, label="graph execution terminal")
        _self_hash(item, field="execution_terminal_sha256", label="graph execution terminal")
        if item.get("execution_binding") != binding_identity.as_dict():
            raise CorpusNeo4jTransportError("graph execution terminal differs")
        return {**item, "execution_terminal_identity": identity.as_dict()}
    retained_execution = _mapping(execution, label="terminal execution")
    metadata = _mapping(
        retained_execution.get("metadata"), label="terminal execution metadata"
    )
    execution_name = _string(
        metadata.get("name"), label="terminal execution name"
    ).rsplit("/", 1)[-1]
    if execution_name != binding.get("execution_name"):
        raise CorpusNeo4jTransportError("terminal execution name differs")
    state = _completion_state(retained_execution)
    status = _mapping(retained_execution.get("status"), label="terminal status")
    if (
        state != "True"
        or status.get("succeededCount") != 1
        or int(status.get("failedCount", 0) or 0) != 0
        or int(status.get("cancelledCount", 0) or 0) != 0
        or int(status.get("retriedCount", 0) or 0) != 0
    ):
        raise CorpusNeo4jTransportError("graph execution is not strict terminal success")
    receipt_identities = _resolve_operation_receipts(
        storage=storage,
        bundle=bundle,
        operation=operation,
        task_index=task_index,
        require_complete_suite=require_complete_suite,
    )
    body = {
        "schema_version": EXECUTION_TERMINAL_SCHEMA,
        "publication_mode": "create_once",
        "deployment_manifest": bundle.deployment_identity.as_dict(),
        "load_manifest": bundle.manifest_identity.as_dict(),
        "launch_intent": intent_identity.as_dict(),
        "execution_binding": binding_identity.as_dict(),
        "operation": operation,
        "task_index": -1 if task_index is None else task_index,
        "require_complete_suite": require_complete_suite,
        "execution_name": execution_name,
        "execution_metadata_sha256": canonical_sha256(retained_execution),
        "operation_receipts": receipt_identities,
        "strict_terminal_success": True,
        "one_execution": True,
        "automatic_retry_licensed": False,
        "gcs_remains_authoritative": True,
        "created_at_utc": _timestamp(created_at_utc, label="execution terminal timestamp"),
    }
    terminal = _with_self_hash(body, field="execution_terminal_sha256")
    identity = storage.publish_create_once(terminal_uri, canonical_json_bytes(terminal))
    return {**terminal, "execution_terminal_identity": identity.as_dict()}


class GoogleCloudObjectStore:
    """Google Cloud Storage adapter restricted to exact object operations."""

    def __init__(self, *, project: str | None = None) -> None:
        try:
            from google.cloud import storage
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise CorpusNeo4jTransportError(
                "google-cloud-storage is required for live graph transport"
            ) from exc
        self._client = storage.Client(project=project)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            raise CorpusNeo4jTransportError("object URI must use gs://")
        bucket, marker, name = uri[5:].partition("/")
        if not marker or not bucket or not name or name.endswith("/"):
            raise CorpusNeo4jTransportError("object URI differs")
        return bucket, name

    def read_exact(self, identity: ObjectIdentity) -> bytes:
        bucket_name, object_name = self._parts(identity.uri)
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=int(identity.generation)
        )
        try:
            raw = blob.download_as_bytes(if_generation_match=int(identity.generation))
        except Exception as exc:  # pragma: no cover - cloud dependent
            raise CorpusNeo4jTransportError(
                f"generation-pinned GET failed for {identity.uri}"
            ) from exc
        return _bind_raw(raw, identity, label=identity.uri)

    def resolve_optional(self, uri: str) -> tuple[ObjectIdentity, bytes] | None:
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.reload()
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ == "NotFound":
                return None
            raise CorpusNeo4jTransportError(
                f"exact-name object metadata GET failed for {uri}"
            ) from exc
        generation = _blob_generation(
            blob.generation, label="resolved object generation"
        )
        pinned = self._client.bucket(bucket_name).blob(
            object_name, generation=int(generation)
        )
        try:
            raw = pinned.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:  # pragma: no cover - cloud dependent
            raise CorpusNeo4jTransportError(
                f"exact-name object GET failed for {uri}"
            ) from exc
        identity = ObjectIdentity(
            uri=uri,
            generation=generation,
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        return identity, raw

    def publish_create_once(self, uri: str, raw: bytes) -> ObjectIdentity:
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"PreconditionFailed", "Conflict"}:
                raise CorpusNeo4jTransportError(
                    f"create-once publication failed for {uri}"
                ) from exc
            existing = self.resolve_optional(uri)
            if existing is None or existing[1] != raw:
                raise CorpusNeo4jTransportError(
                    f"create-once object conflicts at {uri}"
                ) from exc
            return existing[0]
        blob.reload()
        identity = ObjectIdentity(
            uri=uri,
            generation=_blob_generation(
                blob.generation, label="published object generation"
            ),
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        reopened = self.read_exact(identity)
        if reopened != raw:
            raise CorpusNeo4jTransportError("published object reopen differs")
        return identity


class Neo4jDriverBackend:
    """Live Neo4j adapter.  Construction is intentionally explicit and late."""

    def __init__(self, *, values: Mapping[str, str]) -> None:
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise CorpusNeo4jTransportError(
                "neo4j driver is required for live graph transport"
            ) from exc
        self.database = values["database"]
        self._driver = GraphDatabase.driver(
            values["uri"], auth=(values["username"], values["password"])
        )
        self._driver.verify_connectivity()

    def close(self) -> None:
        self._driver.close()

    def component(self) -> Mapping[str, object]:
        with self._driver.session(database=self.database) as session:
            row = session.run(
                "CALL dbms.components() YIELD versions, edition "
                "RETURN versions[0] AS version, edition"
            ).single(strict=True)
            return {"version": row["version"], "edition": row["edition"]}

    def census(self) -> Mapping[str, object]:
        with self._driver.session(database=self.database) as session:
            node_count = session.run("MATCH (n) RETURN count(n) AS value").single(
                strict=True
            )["value"]
            rel_count = session.run(
                "MATCH ()-[r]->() RETURN count(r) AS value"
            ).single(strict=True)["value"]
            labels = session.run(
                "MATCH (n) UNWIND labels(n) AS label RETURN DISTINCT label ORDER BY label"
            ).value("label")
            rel_types = session.run(
                "MATCH ()-[r]->() RETURN DISTINCT type(r) AS value ORDER BY value"
            ).value("value")
            namespaces = session.run(
                "MATCH (n:CorpusRetrievalEntity) "
                "WHERE n.workstream_namespace IS NOT NULL "
                "RETURN DISTINCT n.workstream_namespace AS value ORDER BY value"
            ).value("value")
        return {
            "node_count": int(node_count),
            "relationship_count": int(rel_count),
            "node_labels": list(labels),
            "relationship_types": list(rel_types),
            "workstream_namespaces": list(namespaces),
        }

    def bootstrap_schema(self, statements: Sequence[str]) -> None:
        with self._driver.session(database=self.database) as session:
            for statement in statements:
                session.run(statement).consume()

    def apply(self, plan: Neo4jLoadPlan) -> Mapping[str, object]:
        with self._driver.session(database=self.database) as session:
            def write(transaction: Any) -> dict[str, object]:
                def runner(query: str, parameters: Mapping[str, object]) -> Mapping[str, object]:
                    records = list(transaction.run(query, dict(parameters)))
                    if len(records) != 1:
                        raise CorpusNeo4jTransportError(
                            "Neo4j load returned an unexpected record count"
                        )
                    return dict(records[0])

                return apply_load_plan(
                    plan, run_statement=runner, database=self.database
                )

            return session.execute_write(write)

    @staticmethod
    def _chunks(values: Sequence[object], size: int = 500) -> Sequence[Sequence[object]]:
        return [values[index:index + size] for index in range(0, len(values), size)]

    def verify(self, plan: Neo4jLoadPlan) -> Mapping[str, object]:
        expected_nodes = {str(row["id"]): dict(row) for row in plan.nodes}
        expected_relationships = {
            str(row["edge_key"]): dict(row) for row in plan.relationships
        }
        actual_nodes: dict[str, dict[str, object]] = {}
        actual_relationships: dict[str, dict[str, object]] = {}
        with self._driver.session(database=self.database) as session:
            for chunk in self._chunks(list(expected_nodes)):
                rows = session.run(
                    "MATCH (n:CorpusRetrievalEntity) WHERE n.id IN $ids "
                    "RETURN n.id AS id, properties(n) AS properties",
                    ids=list(chunk),
                )
                for row in rows:
                    actual_nodes[str(row["id"])] = dict(row["properties"])
            for chunk in self._chunks(list(expected_relationships)):
                rows = session.run(
                    "MATCH (source)-[r:CORPUS_RELATION]->(target) "
                    "WHERE r.edge_key IN $keys "
                    "RETURN r.edge_key AS edge_key, source.id AS from_id, "
                    "target.id AS to_id, properties(r) AS properties",
                    keys=list(chunk),
                )
                for row in rows:
                    props = dict(row["properties"])
                    props["from_id"] = row["from_id"]
                    props["to_id"] = row["to_id"]
                    actual_relationships[str(row["edge_key"])] = props
        node_fields = {
            key for key in next(iter(expected_nodes.values())) if key != "id"
        }
        for node_id, expected in expected_nodes.items():
            actual = actual_nodes.get(node_id)
            if actual is None or actual != {
                key: expected[key] for key in node_fields
            } | {"id": node_id}:
                # Neo4j properties(n) includes id because id is a stored property.
                raise CorpusNeo4jTransportError("exact graph node replay differs")
        relationship_fields = {
            key for key in next(iter(expected_relationships.values()))
            if key not in {"from_id", "to_id"}
        }
        for edge_key, expected in expected_relationships.items():
            actual = actual_relationships.get(edge_key)
            if actual is None or actual != {
                **{key: expected[key] for key in relationship_fields},
                "from_id": expected["from_id"],
                "to_id": expected["to_id"],
            }:
                raise CorpusNeo4jTransportError(
                    "exact graph relationship replay differs"
                )
        return {
            "plan_sha256": plan.plan_sha256,
            "verified_node_count": len(expected_nodes),
            "verified_relationship_count": len(expected_relationships),
            "exact": True,
        }

    def suite_census(
        self, *, batch_id: str, registry_id: str,
    ) -> Mapping[str, object]:
        with self._driver.session(database=self.database) as session:
            tasks = list(session.run(
                "MATCH (n:CorpusRetrievalEntity) "
                "WHERE n.workstream_namespace = $namespace "
                "AND n.run_id = $batch_id AND n.kind = 'CorpusParametricTask' "
                "RETURN n.task_index AS task_index, n.slate_id AS slate_id "
                "ORDER BY task_index",
                namespace=PARAMETRIC_NAMESPACE,
                batch_id=batch_id,
            ))
            arm_count = session.run(
                "MATCH (n:CorpusRetrievalEntity) "
                "WHERE n.workstream_namespace = $namespace "
                "AND n.run_id = $batch_id AND n.kind = 'CorpusParametricArm' "
                "RETURN count(n) AS value",
                namespace=PARAMETRIC_NAMESPACE,
                batch_id=batch_id,
            ).single(strict=True)["value"]
            namespaces = session.run(
                "MATCH (n:CorpusRetrievalEntity) "
                "RETURN DISTINCT n.workstream_namespace AS value ORDER BY value"
            ).value("value")
            population_count = session.run(
                "MATCH (n:CorpusRetrievalEntity) "
                "WHERE n.workstream_namespace = $namespace RETURN count(n) AS value",
                namespace=POPULATION_NAMESPACE,
            ).single(strict=True)["value"]
            realized_count = session.run(
                "MATCH (n:CorpusRetrievalEntity) "
                "WHERE n.workstream_namespace = $namespace RETURN count(n) AS value",
                namespace=REALIZED_OUTCOME_NAMESPACE,
            ).single(strict=True)["value"]
            registry_kind_rows = list(session.run(
                "MATCH (n:CorpusRetrievalEntity) "
                "WHERE n.workstream_namespace = $namespace "
                "AND n.run_id = $registry_id "
                "RETURN n.kind AS kind, count(n) AS value ORDER BY kind",
                namespace=STRATEGY_REGISTRY_NAMESPACE,
                registry_id=registry_id,
            ))
            registry_relationship_count = session.run(
                "MATCH (source:CorpusRetrievalEntity)-[r:CORPUS_RELATION]->"
                "(target:CorpusRetrievalEntity) "
                "WHERE (source.workstream_namespace = $namespace "
                "AND source.run_id = $registry_id) OR "
                "(target.workstream_namespace = $namespace "
                "AND target.run_id = $registry_id) "
                "RETURN count(r) AS value",
                namespace=STRATEGY_REGISTRY_NAMESPACE,
                registry_id=registry_id,
            ).single(strict=True)["value"]
        registry_kind_counts = {
            str(row["kind"]): int(row["value"]) for row in registry_kind_rows
        }
        return {
            "batch_id": batch_id,
            "task_count": len(tasks),
            "arm_count": int(arm_count),
            "task_indexes": [int(row["task_index"]) for row in tasks],
            "slate_ids": [str(row["slate_id"]) for row in tasks],
            "registry_id": registry_id,
            "registry_node_count": sum(registry_kind_counts.values()),
            "registry_relationship_count": int(registry_relationship_count),
            "registry_kind_counts": registry_kind_counts,
            "workstream_namespaces": list(namespaces),
            "reserved_population_node_count": int(population_count),
            "reserved_realized_outcome_node_count": int(realized_count),
        }

    def run_read_only_query(
        self, database: str, cypher: str, parameters: Mapping[str, object],
    ) -> Sequence[Mapping[str, object]]:
        if database != self.database:
            raise CorpusNeo4jTransportError(
                "strategy registry query database differs"
            )
        with self._driver.session(database=self.database) as session:
            rows = [dict(row) for row in session.run(cypher, dict(parameters))]
        if len(rows) > 100_000:
            raise CorpusNeo4jTransportError(
                "strategy registry query exceeds the bounded transport limit"
            )
        return rows

    def query_smoke(self, *, run_id: str, task_id: str) -> Mapping[str, object]:
        kinds = (
            "LineupCandidate", "CorpusAssociationMeasurement",
            "CorpusCorrelationMeasurement", "CorpusStrategySplitMeasurement",
            "CorpusArtifactPointer",
        )
        with self._driver.session(database=self.database) as session:
            rows = session.run(
                "MATCH (n:CorpusRetrievalEntity) "
                "WHERE n.workstream_namespace = $namespace "
                "AND n.run_id = $run_id AND n.task_id = $task_id "
                "AND n.kind IN $kinds "
                "RETURN n.kind AS kind, count(n) AS value ORDER BY kind",
                namespace=RETRIEVAL_NAMESPACE,
                run_id=run_id,
                task_id=task_id,
                kinds=list(kinds),
            )
            counts = {kind: 0 for kind in kinds}
            for row in rows:
                counts[str(row["kind"])] = int(row["value"])
            population_count = session.run(
                "MATCH (n:CorpusRetrievalEntity) "
                "WHERE n.workstream_namespace = $namespace RETURN count(n) AS value",
                namespace=POPULATION_NAMESPACE,
            ).single(strict=True)["value"]
            realized_count = session.run(
                "MATCH (n:CorpusRetrievalEntity) "
                "WHERE n.workstream_namespace = $namespace RETURN count(n) AS value",
                namespace=REALIZED_OUTCOME_NAMESPACE,
            ).single(strict=True)["value"]
        return {
            "retrieval_kind_counts": counts,
            "reserved_population_node_count": int(population_count),
            "reserved_realized_outcome_node_count": int(realized_count),
            "read_only": True,
        }


def open_bound_backend(
    *, deployment: Mapping[str, object], role: str,
    environ: Mapping[str, str] | None = None,
) -> Neo4jDriverBackend:
    values = validate_connection_binding(
        deployment, role=role, environ=os.environ if environ is None else environ
    )
    return Neo4jDriverBackend(values=values)


__all__ = [
    "BOOTSTRAP_RECEIPT_SCHEMA",
    "CorpusNeo4jTransportError",
    "DEPLOYMENT_SCHEMA",
    "ExactObjectStore",
    "EXECUTION_BINDING_SCHEMA",
    "EXECUTION_TERMINAL_SCHEMA",
    "EXPECTED_BUILD_STEPS",
    "EXPECTED_CODE_REPOSITORY",
    "GoogleCloudObjectStore",
    "GraphBackend",
    "LOAD_MANIFEST_SCHEMA",
    "LOAD_RECEIPT_SCHEMA",
    "LAUNCH_INTENT_SCHEMA",
    "MANIFEST_PUBLICATION_ENABLE_ENV",
    "Neo4jDriverBackend",
    "ObjectIdentity",
    "REALIZED_OUTCOME_NAMESPACE",
    "QUERY_SMOKE_SCHEMA",
    "REQUIRED_BUILD_COMMANDS",
    "SUITE_RECEIPT_SCHEMA",
    "STRATEGY_REGISTRY_NAMESPACE",
    "TRANSPORT_ENABLE_ENV",
    "ValidatedLoadBundle",
    "bootstrap_schema",
    "bind_launch_execution",
    "build_deployment_manifest",
    "consume_launch_intent",
    "finish_launch_execution",
    "finish_suite",
    "load_parametric_suite",
    "load_plan",
    "load_strategy_registry",
    "object_identity",
    "open_bound_backend",
    "prepare_load_manifest",
    "publish_manifest",
    "query_smoke",
    "query_strategy_registry",
    "recover_plan_receipt",
    "recover_strategy_registry_receipt",
    "require_execute_gate",
    "validate_connection_binding",
    "validate_build_metadata",
    "validate_deployment_manifest",
    "validate_load_manifest",
    "validate_parked_job",
    "validate_reuse_preflight",
]
