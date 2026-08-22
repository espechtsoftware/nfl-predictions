"""One-shot Cloud Run and lease governance for realized corpus grading.

The realized grader deliberately owns only the single BigQuery read and its
deterministic replay.  This module owns the surrounding control plane:

* one immutable accepted 54x7 batch and one immutable expansion image;
* one externally reused, attachment-free Cloud Run job kept parked;
* a create-once launch claim and intent before any execution request;
* two durable proofs that the deterministic BigQuery job id was unused;
* generation-pinned delivery of the historical-outcome lease receipt;
* census-only recovery and binding of exactly one Cloud Run execution;
* strict terminal acceptance followed by a generation-matched lease release;
* or a create-once, archived, fail-closed abandonment with no retry license.

There is no import-time cloud client and no operation grants retry, graph
mutation, corpus filling, production change, or decision authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Final, Protocol

from nfl_dfs.research import corpus_expansion_build as expansion_build
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_realized_outcome_transport as outcomes
from nfl_dfs.research import lr8_label_fit_adapter as lease_adapter
from nfl_dfs.research import lr8_label_score_map as lease_validation


PROJECT: Final = outcomes.PROJECT
REGION: Final = "us-central1"
LOCATION: Final = outcomes.LOCATION
ENABLE_ENV: Final = "CORPUS_REALIZED_TRANSPORT_ENABLED"
WORKER_ENABLE_ENV: Final = "CORPUS_REALIZED_OUTCOMES_ENABLED"
IMAGE_ENV: Final = "CORPUS_REALIZED_IMAGE"
BUILD_ENV: Final = "CORPUS_REALIZED_BUILD_ID"
CODE_ENV: Final = "CODE_SHA"

PARKED_COMMAND: Final = ["python"]
PARKED_ARGS: Final = [
    "scripts/run_corpus_realized_cloud_transport.py", "parked",
]
EXPECTED_TASK_COUNT: Final = 1
EXPECTED_PARALLELISM: Final = 1
EXPECTED_MAX_RETRIES: Final = 0
EXPECTED_TIMEOUT_SECONDS: Final = "86400"
EXPECTED_RESOURCES: Final = {"cpu": "4", "memory": "16Gi"}

LEASE_RECEIPT_SCHEMA: Final = "corpus-realized-lease-receipt/v1"
LAUNCH_CLAIM_SCHEMA: Final = "corpus-realized-launch-claim/v1"
LAUNCH_INTENT_SCHEMA: Final = "corpus-realized-launch-intent/v1"
QUERY_UNUSED_SCHEMA: Final = "corpus-realized-query-job-unused/v1"
QUERY_CONFIRMATION_SCHEMA: Final = (
    "corpus-realized-pre-execution-query-confirmation/v1"
)
EXECUTION_BINDING_SCHEMA: Final = "corpus-realized-execution-binding/v1"
TERMINAL_SCHEMA: Final = "corpus-realized-terminal-acceptance/v1"
LEASE_DISPOSITION_INTENT_SCHEMA: Final = (
    "corpus-realized-lease-disposition-intent/v1"
)
LEASE_RELEASE_SCHEMA: Final = "corpus-realized-lease-release/v1"
LEASE_ABANDON_SCHEMA: Final = "corpus-realized-lease-abandonment/v1"

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}")
_BUILD: Final = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_GENERATION: Final = re.compile(r"[1-9][0-9]*")
_SERVICE_ACCOUNT: Final = re.compile(
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]@"
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com"
)
_EXECUTION: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}-[a-z0-9]{5}")
_REASON: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,60}")


class CorpusRealizedCloudTransportError(RuntimeError):
    """The realized-outcome cloud control plane failed closed."""


def canonical_json_bytes(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusRealizedCloudTransportError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if type(value) is not list:
        raise CorpusRealizedCloudTransportError(f"{label} must be an array")
    return value


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusRealizedCloudTransportError(
            f"{label} must be a canonical string"
        )
    return value


def _blob_generation(value: object, *, label: str) -> str:
    """Normalize one loaded google-cloud-storage generation for receipts."""
    if type(value) is not int or value < 1:
        raise CorpusRealizedCloudTransportError(
            f"{label} must be a positive SDK integer"
        )
    return str(value)


def _timestamp(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorpusRealizedCloudTransportError(
            f"{label} must be an ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CorpusRealizedCloudTransportError(
            f"{label} must be timezone-aware"
        )
    return parsed.astimezone(timezone.utc).isoformat()


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> dict[str, object]:
    item = dict(value)
    digest = item.get(field)
    if type(digest) is not str or _SHA256.fullmatch(digest) is None:
        raise CorpusRealizedCloudTransportError(f"{label} hash differs")
    body = {key: retained for key, retained in item.items() if key != field}
    if canonical_sha256(body) != digest:
        raise CorpusRealizedCloudTransportError(f"{label} self-hash differs")
    return item


def _with_self_hash(
    value: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    body = dict(value)
    if field in body:
        raise CorpusRealizedCloudTransportError("self-hash field was prefilled")
    return {**body, field: canonical_sha256(body)}


def _gcs_uri(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if not text.startswith("gs://"):
        raise CorpusRealizedCloudTransportError(f"{label} must use gs://")
    bucket_name, separator, name = text.removeprefix("gs://").partition("/")
    if (
        not bucket_name or not separator or not name
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        raise CorpusRealizedCloudTransportError(
            f"{label} must name one exact object"
        )
    return text


@dataclass(frozen=True, slots=True)
class ObjectIdentity:
    uri: str
    generation: str
    sha256: str
    bytes: int

    @classmethod
    def from_value(cls, value: object, *, label: str) -> ObjectIdentity:
        item = _mapping(value, label=label)
        retained = {
            key: item[key] for key in ("uri", "generation", "sha256", "bytes")
            if key in item
        }
        if set(retained) != {"uri", "generation", "sha256", "bytes"}:
            raise CorpusRealizedCloudTransportError(f"{label} fields differ")
        uri = _gcs_uri(retained["uri"], label=f"{label}.uri")
        generation = _string(
            retained["generation"], label=f"{label}.generation"
        )
        digest = _string(retained["sha256"], label=f"{label}.sha256")
        size = retained["bytes"]
        if (
            _GENERATION.fullmatch(generation) is None
            or _SHA256.fullmatch(digest) is None
            or type(size) is not int or size <= 0
        ):
            raise CorpusRealizedCloudTransportError(f"{label} identity differs")
        return cls(uri=uri, generation=generation, sha256=digest, bytes=size)

    def as_dict(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "generation": self.generation,
            "sha256": self.sha256,
            "bytes": self.bytes,
        }


class ObjectStore(Protocol):
    def read(self, identity: Mapping[str, object]) -> bytes: ...

    def resolve(self, uri: str) -> tuple[dict[str, object], bytes] | None: ...

    def publish_or_reopen(self, uri: str, raw: bytes) -> dict[str, object]: ...

    def delete_exact(self, identity: Mapping[str, object]) -> None: ...


@dataclass(frozen=True, slots=True)
class RunConfig:
    run_id: str
    build_id: str
    code_sha: str
    image: str
    job_name: str
    job_uid: str
    service_account: str
    batch_acceptance: ObjectIdentity

    @property
    def output_root(self) -> str:
        return (
            f"gs://{outcomes.OUTPUT_BUCKET}/{outcomes.OUTPUT_NAMESPACE}/"
            f"{self.run_id}"
        )

    @property
    def governance_root(self) -> str:
        return f"{self.output_root}/governance"

    @property
    def query_job_id(self) -> str:
        supplier = outcomes.SupplierConfig(
            run_id=self.run_id,
            job=self.job_name,
            code_sha=self.code_sha,
            image=self.image,
            expected_batch_acceptance_object_sha256=(
                self.batch_acceptance.sha256
            ),
            enabled=True,
        )
        return outcomes.deterministic_query_job_id(supplier)

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "build_id": self.build_id,
            "code_sha": self.code_sha,
            "image": self.image,
            "job_name": self.job_name,
            "job_uid": self.job_uid,
            "service_account": self.service_account,
            "batch_acceptance": self.batch_acceptance.as_dict(),
            "query_job_id": self.query_job_id,
        }


def validate_run_config(value: RunConfig) -> RunConfig:
    if not isinstance(value, RunConfig) or (
        _RUN_ID.fullmatch(value.run_id) is None
        or len(value.run_id) > 81
        or _BUILD.fullmatch(value.build_id) is None
        or _CODE_SHA.fullmatch(value.code_sha) is None
        or _IMAGE.fullmatch(value.image) is None
        or _JOB.fullmatch(value.job_name) is None
        or not value.job_uid
        or _SERVICE_ACCOUNT.fullmatch(value.service_account) is None
        or not isinstance(value.batch_acceptance, ObjectIdentity)
    ):
        raise CorpusRealizedCloudTransportError(
            "realized cloud runtime identity differs"
        )
    if len(value.query_job_id) > 1024:
        raise CorpusRealizedCloudTransportError(
            "deterministic BigQuery job id differs"
        )
    return value


def validate_build_metadata(
    value: object, *, config: RunConfig,
) -> dict[str, str]:
    config = validate_run_config(config)
    try:
        retained = expansion_build.validate_build_metadata(
            value,
            build_id=config.build_id,
            code_sha=config.code_sha,
            image=config.image,
        )
    except expansion_build.CorpusExpansionBuildError as exc:
        raise CorpusRealizedCloudTransportError(str(exc)) from exc
    return dict(retained)


def require_execute_gate(
    *, execute: bool, environ: Mapping[str, str],
) -> None:
    if execute is not True or environ.get(ENABLE_ENV) != "1":
        raise CorpusRealizedCloudTransportError(
            f"literal --execute and {ENABLE_ENV}=1 are required"
        )


def _read_exact_json(
    storage: ObjectStore, identity: object, *, label: str,
) -> tuple[ObjectIdentity, dict[str, object]]:
    retained = ObjectIdentity.from_value(identity, label=f"{label} identity")
    try:
        raw = storage.read(retained.as_dict())
    except Exception as exc:
        raise CorpusRealizedCloudTransportError(
            f"{label} generation-pinned read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != retained.bytes
        or sha256(raw).hexdigest() != retained.sha256
    ):
        raise CorpusRealizedCloudTransportError(f"{label} identity differs")
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusRealizedCloudTransportError(str(exc)) from exc
    return retained, dict(_mapping(value, label=label))


def _publish(
    storage: ObjectStore, *, uri: str, value: Mapping[str, object], label: str,
) -> ObjectIdentity:
    return _publish_raw(
        storage, uri=uri, raw=canonical_json_bytes(value), label=label
    )


def _publish_raw(
    storage: ObjectStore, *, uri: str, raw: bytes, label: str,
) -> ObjectIdentity:
    try:
        identity = ObjectIdentity.from_value(
            storage.publish_or_reopen(uri, raw), label=f"{label} publication"
        )
        reopened = storage.read(identity.as_dict())
    except Exception as exc:
        if isinstance(exc, CorpusRealizedCloudTransportError):
            raise
        raise CorpusRealizedCloudTransportError(
            f"{label} create-once publication failed"
        ) from exc
    if (
        identity.uri != uri
        or identity.sha256 != sha256(raw).hexdigest()
        or identity.bytes != len(raw)
        or reopened != raw
    ):
        raise CorpusRealizedCloudTransportError(
            f"{label} create-once reopen differs"
        )
    return identity


def _fixed_uri(config: RunConfig, name: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.json", name):
        raise CorpusRealizedCloudTransportError("governance object name differs")
    return f"{config.governance_root}/{name}"


def _lease_supplier_config(config: RunConfig) -> lease_validation.SupplierConfig:
    return lease_validation.SupplierConfig(
        run_id=config.run_id,
        job=config.job_name,
        code_sha=config.code_sha,
        image=config.image,
        expected_source_manifest_sha256=config.batch_acceptance.sha256,
        enabled=True,
    )


def _validate_lease_contract(
    value: object, *, config: RunConfig,
) -> dict[str, object]:
    item = _mapping(value, label="historical lease receipt object")
    if set(item) != {"schema_version", "lease", "object"} or (
        item.get("schema_version") != LEASE_RECEIPT_SCHEMA
    ):
        raise CorpusRealizedCloudTransportError(
            "historical lease receipt wrapper differs"
        )
    normalized = {
        "body": item["lease"],
        "object_receipt": item["object"],
    }
    try:
        validated = lease_validation._validate_lease(  # noqa: SLF001
            normalized, config=_lease_supplier_config(config)
        )
    except lease_validation.LR8ScoreMapError as exc:
        raise CorpusRealizedCloudTransportError(str(exc)) from exc
    return {
        "schema_version": LEASE_RECEIPT_SCHEMA,
        "lease": validated["body"],
        "object": validated["object_receipt"],
    }


def lease_receipt_identity(storage: ObjectStore, *, config: RunConfig) -> ObjectIdentity:
    config = validate_run_config(config)
    uri = _fixed_uri(config, "historical-lease-receipt.json")
    resolved = storage.resolve(uri)
    if resolved is None:
        raise CorpusRealizedCloudTransportError(
            "historical lease receipt is absent"
        )
    identity = ObjectIdentity.from_value(resolved[0], label="lease receipt")
    retained, value = _read_exact_json(
        storage, identity.as_dict(), label="historical lease receipt"
    )
    if retained.uri != uri:
        raise CorpusRealizedCloudTransportError("lease receipt URI differs")
    _validate_lease_contract(value, config=config)
    return retained


def acquire_historical_lease(
    *, storage: ObjectStore, config: RunConfig, acquired_at_utc: str,
) -> dict[str, object]:
    """Acquire or exactly recover this run's active lease and receipt."""
    config = validate_run_config(config)
    acquired_at = _timestamp(acquired_at_utc, label="lease acquisition")
    body = {
        "version": lease_adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": config.run_id,
        "job": config.job_name,
        "code_sha": config.code_sha,
        "image": config.image,
        "acquired_at": acquired_at,
    }
    active_identity = _publish_raw(
        storage,
        uri=lease_adapter.HISTORICAL_OUTCOME_LEASE_URI,
        raw=lease_validation.canonical_json(body),
        label="active historical lease",
    )
    wrapped = {
        "schema_version": LEASE_RECEIPT_SCHEMA,
        "lease": body,
        "object": {**active_identity.as_dict(), "create_only": True},
    }
    wrapped = _validate_lease_contract(wrapped, config=config)
    receipt_identity = _publish(
        storage,
        uri=_fixed_uri(config, "historical-lease-receipt.json"),
        value=wrapped,
        label="historical lease receipt",
    )
    return {
        "schema_version": "corpus-realized-lease-acquired/v1",
        "run_id": config.run_id,
        "active_lease": active_identity.as_dict(),
        "lease_receipt": receipt_identity.as_dict(),
        "release_or_abandon_required": True,
        "automatic_retry_licensed": False,
    }


def load_lease_contract(
    storage: ObjectStore, *, config: RunConfig,
) -> tuple[ObjectIdentity, dict[str, object]]:
    identity = lease_receipt_identity(storage, config=config)
    _, wrapped = _read_exact_json(
        storage, identity.as_dict(), label="historical lease receipt"
    )
    retained = _validate_lease_contract(wrapped, config=config)
    return identity, {
        "body": retained["lease"],
        "object_receipt": retained["object"],
    }


def _outer_spec(job: Mapping[str, object]) -> Mapping[str, object]:
    spec = _mapping(job.get("spec"), label="job.spec")
    template = _mapping(spec.get("template"), label="job.spec.template")
    return _mapping(template.get("spec"), label="job outer spec")


def _task_spec(job: Mapping[str, object]) -> Mapping[str, object]:
    outer = _outer_spec(job)
    template = _mapping(outer.get("template"), label="job task template")
    return _mapping(template.get("spec"), label="job task spec")


def _container(task: Mapping[str, object], *, label: str) -> Mapping[str, object]:
    containers = task.get("containers")
    if type(containers) is not list or len(containers) != 1:
        raise CorpusRealizedCloudTransportError(f"{label} container differs")
    return _mapping(containers[0], label=f"{label} container")


def _environment(container: Mapping[str, object], *, label: str) -> dict[str, str]:
    rows = container.get("env", [])
    if type(rows) is not list:
        raise CorpusRealizedCloudTransportError(f"{label} environment differs")
    retained: dict[str, str] = {}
    for raw in rows:
        row = _mapping(raw, label=f"{label} environment row")
        if set(row) != {"name", "value"}:
            raise CorpusRealizedCloudTransportError(
                f"{label} environment may not use secrets/valueFrom"
            )
        name = _string(row["name"], label=f"{label} environment name")
        value = _string(row["value"], label=f"{label} environment value")
        if name in retained:
            raise CorpusRealizedCloudTransportError(
                f"{label} environment repeats"
            )
        retained[name] = value
    return retained


def _job_identity(value: object, *, label: str) -> dict[str, str]:
    item = _mapping(value, label=label)
    metadata = _mapping(item.get("metadata"), label=f"{label}.metadata")
    status = _mapping(item.get("status"), label=f"{label}.status")
    name = _string(metadata.get("name"), label=f"{label}.name")
    uid = _string(metadata.get("uid"), label=f"{label}.uid")
    generation = str(metadata.get("generation", ""))
    observed = str(status.get("observedGeneration", ""))
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
        raise CorpusRealizedCloudTransportError(
            f"{label} is not reconciled Ready"
        )
    return {
        "name": name,
        "uid": uid,
        "generation": generation,
        "observed_generation": observed,
        "spec_sha256": canonical_sha256(item["spec"]),
    }


def _reject_attachments(
    job: Mapping[str, object], *, require_plain_env: bool,
) -> None:
    rendered = canonical_json_bytes(job).decode("utf-8").lower()
    forbidden_markers = (
        "cloudsqlinstances", "secretkeyref", "valuefrom", "vpcaccess",
        "vpcconnector", "networkinterfaces", "volumemounts",
    )
    if any(marker in rendered for marker in forbidden_markers):
        raise CorpusRealizedCloudTransportError(
            "reused job retains network, volume, Cloud SQL, or secret attachment"
        )
    task = _task_spec(job)
    container = _container(task, label="job")
    allowed_task = {
        "containers", "maxRetries", "serviceAccountName", "timeoutSeconds",
        "volumes",
    }
    allowed_container = {
        "args", "command", "env", "image", "resources", "volumeMounts",
    }
    if set(task) - allowed_task or set(container) - allowed_container:
        raise CorpusRealizedCloudTransportError(
            "reused job retains an unbound task/container attachment"
        )
    if task.get("volumes", []) != [] or container.get("volumeMounts", []) != []:
        raise CorpusRealizedCloudTransportError("reused job retains a volume")
    if require_plain_env:
        _environment(container, label="job")


def _completion_state(value: Mapping[str, object]) -> str:
    status = _mapping(value.get("status", {}), label="execution.status")
    conditions = status.get("conditions", [])
    if type(conditions) is not list:
        raise CorpusRealizedCloudTransportError(
            "execution conditions differ"
        )
    rows = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if not rows:
        return "Unknown"
    if len(rows) != 1 or rows[0].get("status") not in {"Unknown", "True", "False"}:
        raise CorpusRealizedCloudTransportError(
            "execution Completed condition differs"
        )
    return str(rows[0]["status"])


def execution_names(value: object) -> list[str]:
    rows = _sequence(value, label="execution census")
    names: list[str] = []
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"execution census[{ordinal}]")
        metadata = _mapping(row.get("metadata"), label="execution metadata")
        name = _string(metadata.get("name"), label="execution name").rsplit(
            "/", 1
        )[-1]
        if _EXECUTION.fullmatch(name) is None:
            raise CorpusRealizedCloudTransportError(
                "execution census name differs"
            )
        names.append(name)
    if len(names) != len(set(names)):
        raise CorpusRealizedCloudTransportError(
            "execution census repeats a name"
        )
    return sorted(names)


def require_no_active_executions(value: object) -> None:
    for raw in _sequence(value, label="execution census"):
        if _completion_state(_mapping(raw, label="execution census row")) == "Unknown":
            raise CorpusRealizedCloudTransportError(
                "active execution forbids realized-outcome launch"
            )


def validate_scheduler_census(
    value: object, *, job_name: str, all_regions_complete: bool,
) -> None:
    if all_regions_complete is not True:
        raise CorpusRealizedCloudTransportError(
            "all-region scheduler census is required"
        )
    needle = f"/jobs/{job_name}:run"
    for raw in _sequence(value, label="scheduler census"):
        row = _mapping(raw, label="scheduler census row")
        target = row.get("httpTarget", {})
        if isinstance(target, Mapping) and needle in str(target.get("uri", "")):
            raise CorpusRealizedCloudTransportError(
                "scheduler targets the reused realized-outcome job"
            )


def validate_reuse_preflight(
    *, job: object, executions: object, schedulers: object,
    job_name: str, job_uid: str, all_regions_complete: bool,
) -> dict[str, object]:
    item = _mapping(job, label="reused job")
    identity = _job_identity(item, label="reused job")
    if identity["name"] != job_name or identity["uid"] != job_uid:
        raise CorpusRealizedCloudTransportError("reused job identity differs")
    _reject_attachments(item, require_plain_env=False)
    task = _task_spec(item)
    if task.get("maxRetries") != 0:
        raise CorpusRealizedCloudTransportError(
            "reused job must already have max-retries 0"
        )
    require_no_active_executions(executions)
    validate_scheduler_census(
        schedulers,
        job_name=job_name,
        all_regions_complete=all_regions_complete,
    )
    return {
        "schema_version": "corpus-realized-reuse-preflight/v1",
        "job": identity,
        "execution_names": execution_names(executions),
        "no_active_executions": True,
        "no_scheduler_targets_job": True,
        "attachment_free": True,
        "max_retries": 0,
    }


def _parked_environment(config: RunConfig) -> dict[str, str]:
    return {
        ENABLE_ENV: "1",
        WORKER_ENABLE_ENV: "1",
        IMAGE_ENV: config.image,
        BUILD_ENV: config.build_id,
        CODE_ENV: config.code_sha,
    }


def validate_parked_job(value: object, *, config: RunConfig) -> dict[str, str]:
    config = validate_run_config(config)
    item = _mapping(value, label="parked job")
    identity = _job_identity(item, label="parked job")
    _reject_attachments(item, require_plain_env=True)
    outer = _outer_spec(item)
    task = _task_spec(item)
    container = _container(task, label="parked job")
    resources = _mapping(
        container.get("resources"), label="parked resources"
    )
    if (
        identity["name"] != config.job_name
        or identity["uid"] != config.job_uid
        or set(outer) != {"taskCount", "parallelism", "template"}
        or set(resources) != {"limits"}
        or outer.get("taskCount") != EXPECTED_TASK_COUNT
        or outer.get("parallelism") != EXPECTED_PARALLELISM
        or task.get("maxRetries") != EXPECTED_MAX_RETRIES
        or str(task.get("timeoutSeconds")) != EXPECTED_TIMEOUT_SECONDS
        or task.get("serviceAccountName") != config.service_account
        or container.get("image") != config.image
        or container.get("command") != PARKED_COMMAND
        or container.get("args") != PARKED_ARGS
        or _environment(container, label="parked job")
        != _parked_environment(config)
        or resources.get("limits") != EXPECTED_RESOURCES
    ):
        raise CorpusRealizedCloudTransportError(
            "job is not the exact default-off realized-outcome parked contract"
        )
    return identity


def query_unused_proof(
    *, config: RunConfig, observed_at_utc: str,
) -> dict[str, object]:
    config = validate_run_config(config)
    body = {
        "schema_version": QUERY_UNUSED_SCHEMA,
        "project": PROJECT,
        "location": LOCATION,
        "job_id": config.query_job_id,
        "observed_at_utc": _timestamp(
            observed_at_utc, label="query unused observation"
        ),
        "lookup": "bigquery.jobs.get",
        "job_absent": True,
        "query_has_not_run": True,
    }
    return _with_self_hash(body, field="query_unused_sha256")


def _validate_query_unused(
    value: object, *, config: RunConfig,
) -> dict[str, object]:
    item = _self_hash(
        _mapping(value, label="query unused proof"),
        field="query_unused_sha256",
        label="query unused proof",
    )
    if (
        item.get("schema_version") != QUERY_UNUSED_SCHEMA
        or item.get("project") != PROJECT
        or item.get("location") != LOCATION
        or item.get("job_id") != config.query_job_id
        or item.get("lookup") != "bigquery.jobs.get"
        or item.get("job_absent") is not True
        or item.get("query_has_not_run") is not True
    ):
        raise CorpusRealizedCloudTransportError(
            "deterministic BigQuery job-id unused proof differs"
        )
    _timestamp(item.get("observed_at_utc"), label="query unused observation")
    return item


BatchReopener = Callable[[ObjectStore, RunConfig], outcomes.AcceptedBatchGraph]


def reopen_accepted_batch(
    storage: ObjectStore, config: RunConfig,
) -> outcomes.AcceptedBatchGraph:
    config = validate_run_config(config)
    try:
        graph = outcomes.reopen_accepted_batch(
            read_exact=storage.read,
            batch_acceptance_identity=config.batch_acceptance.as_dict(),
        )
    except outcomes.CorpusRealizedOutcomeError as exc:
        raise CorpusRealizedCloudTransportError(str(exc)) from exc
    if graph.acceptance_identity != config.batch_acceptance.as_dict():
        raise CorpusRealizedCloudTransportError(
            "accepted batch identity changed"
        )
    return graph


def worker_args(
    *, config: RunConfig, lease_receipt: ObjectIdentity,
) -> list[str]:
    config = validate_run_config(config)
    return [
        "scripts/run_corpus_realized_outcomes.py",
        "--execute",
        "--project", PROJECT,
        "--run-id", config.run_id,
        "--job", config.job_name,
        "--code-sha", config.code_sha,
        "--image", config.image,
        "--batch-acceptance-uri", config.batch_acceptance.uri,
        "--batch-acceptance-generation", config.batch_acceptance.generation,
        "--batch-acceptance-sha256", config.batch_acceptance.sha256,
        "--batch-acceptance-bytes", str(config.batch_acceptance.bytes),
        "--historical-lease-receipt-uri", lease_receipt.uri,
        "--historical-lease-receipt-generation", lease_receipt.generation,
        "--historical-lease-receipt-sha256", lease_receipt.sha256,
        "--historical-lease-receipt-bytes", str(lease_receipt.bytes),
    ]


def prepare_launch(
    *,
    storage: ObjectStore,
    config: RunConfig,
    build_metadata: object,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    unused_proof: object,
    created_at_utc: str,
    batch_reopener: BatchReopener = reopen_accepted_batch,
) -> dict[str, object]:
    """Consume one launch namespace after every outcome-blind preflight."""
    config = validate_run_config(config)
    build = validate_build_metadata(build_metadata, config=config)
    graph = batch_reopener(storage, config)
    if graph.acceptance_identity != config.batch_acceptance.as_dict():
        raise CorpusRealizedCloudTransportError(
            "launch batch acceptance differs"
        )
    lease_identity, lease_contract = load_lease_contract(storage, config=config)
    del lease_contract
    job = validate_parked_job(parked_job, config=config)
    require_no_active_executions(executions)
    validate_scheduler_census(
        schedulers,
        job_name=config.job_name,
        all_regions_complete=all_regions_complete,
    )
    names = execution_names(executions)
    unused = _validate_query_unused(unused_proof, config=config)
    created_at = _timestamp(created_at_utc, label="launch creation")
    claim_body = {
        "schema_version": LAUNCH_CLAIM_SCHEMA,
        "created_at_utc": created_at,
        "run": config.as_dict(),
        "accepted_batch": graph.acceptance_identity,
        "accepted_batch_manifest": graph.manifest_identity,
        "accepted_batch_manifest_sha256": graph.manifest[
            "batch_manifest_sha256"
        ],
        "build": build,
        "parked_job": job,
        "historical_lease_receipt": lease_identity.as_dict(),
        "query_job_id": config.query_job_id,
        "query_job_unused_proof": unused,
        "execution_names_before": names,
        "execution_names_before_sha256": canonical_sha256(names),
        "scheduler_census_sha256": canonical_sha256(schedulers),
        "one_execution_licensed": True,
        "one_historical_query_licensed": True,
        "automatic_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    claim = _with_self_hash(claim_body, field="launch_claim_sha256")
    claim_identity = _publish(
        storage,
        uri=_fixed_uri(config, "launch-claim.json"),
        value=claim,
        label="launch claim",
    )
    intent_body = {
        "schema_version": LAUNCH_INTENT_SCHEMA,
        "created_at_utc": created_at,
        "run": config.as_dict(),
        "launch_claim": claim_identity.as_dict(),
        "parked_job": job,
        "historical_lease_receipt": lease_identity.as_dict(),
        "query_job_id": config.query_job_id,
        "worker_command": PARKED_COMMAND,
        "worker_args": worker_args(
            config=config, lease_receipt=lease_identity
        ),
        "worker_environment": _parked_environment(config),
        "execution_names_before": names,
        "max_retries": 0,
        "task_count": 1,
        "parallelism": 1,
        "launch_request_count": 1,
        "ambiguous_response_policy": "census-only-never-relaunch",
        "automatic_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    intent = _with_self_hash(intent_body, field="launch_intent_sha256")
    intent_identity = _publish(
        storage,
        uri=_fixed_uri(config, "launch-intent.json"),
        value=intent,
        label="launch intent",
    )
    return {
        "schema_version": "corpus-realized-launch-consumed/v1",
        "run_id": config.run_id,
        "query_job_id": config.query_job_id,
        "launch_claim": claim_identity.as_dict(),
        "launch_intent": intent_identity.as_dict(),
        "historical_lease_receipt": lease_identity.as_dict(),
        "launch_request_count_remaining": 1,
        "automatic_retry_licensed": False,
    }


def _load_launch(
    storage: ObjectStore, *, config: RunConfig,
) -> tuple[ObjectIdentity, dict[str, object]]:
    uri = _fixed_uri(config, "launch-intent.json")
    resolved = storage.resolve(uri)
    if resolved is None:
        raise CorpusRealizedCloudTransportError("launch intent is absent")
    identity, intent = _read_exact_json(
        storage, resolved[0], label="launch intent"
    )
    item = _self_hash(
        intent, field="launch_intent_sha256", label="launch intent"
    )
    if (
        identity.uri != uri
        or item.get("schema_version") != LAUNCH_INTENT_SCHEMA
        or item.get("run") != config.as_dict()
        or item.get("query_job_id") != config.query_job_id
        or item.get("max_retries") != 0
        or item.get("task_count") != 1
        or item.get("parallelism") != 1
        or item.get("launch_request_count") != 1
        or item.get("automatic_retry_licensed") is not False
        or item.get("worker_command") != PARKED_COMMAND
    ):
        raise CorpusRealizedCloudTransportError("launch intent differs")
    lease_identity = ObjectIdentity.from_value(
        item.get("historical_lease_receipt"), label="launch lease receipt"
    )
    if item.get("worker_args") != worker_args(
        config=config, lease_receipt=lease_identity
    ) or item.get("worker_environment") != _parked_environment(config):
        raise CorpusRealizedCloudTransportError(
            "launch worker boundary differs"
        )
    return identity, item


def confirm_query_unused(
    *, storage: ObjectStore, config: RunConfig, unused_proof: object,
    created_at_utc: str,
) -> dict[str, object]:
    config = validate_run_config(config)
    intent_identity, intent = _load_launch(storage, config=config)
    unused = _validate_query_unused(unused_proof, config=config)
    body = {
        "schema_version": QUERY_CONFIRMATION_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="pre-execution confirmation"
        ),
        "run": config.as_dict(),
        "launch_intent": intent_identity.as_dict(),
        "query_job_id": config.query_job_id,
        "query_job_unused_proof": unused,
        "launch_request_count": intent["launch_request_count"],
        "confirmed_immediately_before_execution_request": True,
        "automatic_retry_licensed": False,
    }
    confirmation = _with_self_hash(
        body, field="query_confirmation_sha256"
    )
    identity = _publish(
        storage,
        uri=_fixed_uri(config, "pre-execution-query-confirmation.json"),
        value=confirmation,
        label="pre-execution query confirmation",
    )
    return {
        "schema_version": "corpus-realized-query-confirmed/v1",
        "query_job_id": config.query_job_id,
        "confirmation": identity.as_dict(),
        "execute_exactly_once_now": True,
        "automatic_retry_licensed": False,
    }


def _load_confirmation(
    storage: ObjectStore, *, config: RunConfig, intent: ObjectIdentity,
) -> tuple[ObjectIdentity, dict[str, object]]:
    uri = _fixed_uri(config, "pre-execution-query-confirmation.json")
    resolved = storage.resolve(uri)
    if resolved is None:
        raise CorpusRealizedCloudTransportError(
            "pre-execution query confirmation is absent"
        )
    identity, value = _read_exact_json(
        storage, resolved[0], label="query confirmation"
    )
    item = _self_hash(
        value,
        field="query_confirmation_sha256",
        label="query confirmation",
    )
    if (
        identity.uri != uri
        or item.get("schema_version") != QUERY_CONFIRMATION_SCHEMA
        or item.get("run") != config.as_dict()
        or item.get("launch_intent") != intent.as_dict()
        or item.get("query_job_id") != config.query_job_id
        or item.get("confirmed_immediately_before_execution_request") is not True
        or item.get("automatic_retry_licensed") is not False
    ):
        raise CorpusRealizedCloudTransportError(
            "pre-execution query confirmation differs"
        )
    _validate_query_unused(item.get("query_job_unused_proof"), config=config)
    return identity, item


def _execution_runtime(
    value: object,
    *,
    config: RunConfig,
    intent: Mapping[str, object],
    require_terminal: bool,
) -> dict[str, object]:
    item = _mapping(value, label="execution")
    metadata = _mapping(item.get("metadata"), label="execution.metadata")
    full_name = _string(metadata.get("name"), label="execution name")
    execution_id = full_name.rsplit("/", 1)[-1]
    labels = _mapping(metadata.get("labels"), label="execution labels")
    spec = _mapping(item.get("spec"), label="execution spec")
    template = _mapping(spec.get("template"), label="execution template")
    task = _mapping(template.get("spec"), label="execution task")
    container = _container(task, label="execution")
    _reject_attachments(
        {
            "spec": {"template": {"spec": {
                "taskCount": spec.get("taskCount"),
                "parallelism": spec.get("parallelism"),
                "template": {"spec": task},
            }}},
            "metadata": {},
            "status": {},
        },
        require_plain_env=True,
    )
    if (
        _EXECUTION.fullmatch(execution_id) is None
        or labels.get("run.googleapis.com/job") != config.job_name
        or labels.get("run.googleapis.com/jobUid") != config.job_uid
        or set(spec) != {"taskCount", "parallelism", "template"}
        or set(template) != {"spec"}
        or str(labels.get("run.googleapis.com/jobGeneration"))
        != str(_mapping(intent["parked_job"], label="intent job")["generation"])
        or spec.get("taskCount") != 1
        or spec.get("parallelism") != 1
        or task.get("maxRetries") != 0
        or str(task.get("timeoutSeconds")) != EXPECTED_TIMEOUT_SECONDS
        or task.get("serviceAccountName") != config.service_account
        or container.get("image") != config.image
        or container.get("command") != PARKED_COMMAND
        or container.get("args") != intent["worker_args"]
        or _environment(container, label="execution")
        != intent["worker_environment"]
        or _mapping(container.get("resources"), label="execution resources").get(
            "limits"
        ) != EXPECTED_RESOURCES
    ):
        raise CorpusRealizedCloudTransportError(
            "Cloud Run execution override differs from launch intent"
        )
    state = _completion_state(item)
    status = _mapping(item.get("status", {}), label="execution status")
    counters = {
        "succeeded": status.get("succeededCount", 0),
        "failed": status.get("failedCount", 0),
        "cancelled": status.get("cancelledCount", 0),
        "retried": status.get("retriedCount", 0),
    }
    if any(type(count) is not int or count < 0 for count in counters.values()):
        raise CorpusRealizedCloudTransportError("execution counters differ")
    if require_terminal and (
        state != "True"
        or counters != {
            "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
        }
        or not status.get("completionTime")
    ):
        raise CorpusRealizedCloudTransportError(
            "execution is not strict terminal success attempt zero"
        )
    return {
        "execution_id": execution_id,
        "execution_name": full_name,
        "execution_uid": _string(metadata.get("uid"), label="execution UID"),
        "state": state,
        "counters": counters,
        "execution_metadata_sha256": canonical_sha256(item),
    }


def bind_execution(
    *,
    storage: ObjectStore,
    config: RunConfig,
    execution: object,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    created_at_utc: str,
) -> dict[str, object]:
    """Bind the sole post-intent execution; this never launches or retries."""
    config = validate_run_config(config)
    intent_identity, intent = _load_launch(storage, config=config)
    confirmation_identity, _ = _load_confirmation(
        storage, config=config, intent=intent_identity
    )
    parked = validate_parked_job(parked_job, config=config)
    if parked != intent["parked_job"]:
        raise CorpusRealizedCloudTransportError("parked job changed after intent")
    validate_scheduler_census(
        schedulers,
        job_name=config.job_name,
        all_regions_complete=all_regions_complete,
    )
    before = set(_sequence(
        intent.get("execution_names_before"), label="prelaunch execution names"
    ))
    after_names = execution_names(executions)
    after = set(after_names)
    new = after - before
    if before - after or len(new) != 1:
        raise CorpusRealizedCloudTransportError(
            "launch response is ambiguous; census only and never relaunch"
        )
    runtime = _execution_runtime(
        execution, config=config, intent=intent, require_terminal=False
    )
    if runtime["execution_id"] != next(iter(new)):
        raise CorpusRealizedCloudTransportError(
            "recovered execution differs from the sole census delta"
        )
    body = {
        "schema_version": EXECUTION_BINDING_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="execution binding"
        ),
        "run": config.as_dict(),
        "launch_intent": intent_identity.as_dict(),
        "query_confirmation": confirmation_identity.as_dict(),
        "execution": runtime,
        "execution_names_after": after_names,
        "exactly_one_new_execution": True,
        "task_attempt": 0,
        "max_retries": 0,
        "automatic_retry_licensed": False,
    }
    binding = _with_self_hash(body, field="execution_binding_sha256")
    identity = _publish(
        storage,
        uri=_fixed_uri(config, "execution-binding.json"),
        value=binding,
        label="execution binding",
    )
    return {
        "schema_version": "corpus-realized-execution-bound/v1",
        "execution_id": runtime["execution_id"],
        "execution_uid": runtime["execution_uid"],
        "execution_binding": identity.as_dict(),
        "automatic_retry_licensed": False,
    }


def _load_binding(
    storage: ObjectStore, *, config: RunConfig, intent: ObjectIdentity,
) -> tuple[ObjectIdentity, dict[str, object]]:
    uri = _fixed_uri(config, "execution-binding.json")
    resolved = storage.resolve(uri)
    if resolved is None:
        raise CorpusRealizedCloudTransportError("execution binding is absent")
    identity, value = _read_exact_json(
        storage, resolved[0], label="execution binding"
    )
    item = _self_hash(
        value, field="execution_binding_sha256", label="execution binding"
    )
    if (
        identity.uri != uri
        or item.get("schema_version") != EXECUTION_BINDING_SCHEMA
        or item.get("run") != config.as_dict()
        or item.get("launch_intent") != intent.as_dict()
        or item.get("exactly_one_new_execution") is not True
        or item.get("task_attempt") != 0
        or item.get("max_retries") != 0
        or item.get("automatic_retry_licensed") is not False
    ):
        raise CorpusRealizedCloudTransportError("execution binding differs")
    return identity, item


CompletionValidator = Callable[
    [ObjectStore, RunConfig], tuple[ObjectIdentity, dict[str, object]]
]


def validate_worker_completion(
    storage: ObjectStore, config: RunConfig,
) -> tuple[ObjectIdentity, dict[str, object]]:
    """Independently replay the worker's four create-once publications."""
    config = validate_run_config(config)
    graph = reopen_accepted_batch(storage, config)
    lease_identity, lease_contract = load_lease_contract(storage, config=config)
    del lease_identity

    def resolved(name: str, label: str) -> tuple[ObjectIdentity, dict[str, object]]:
        uri = f"{config.output_root}/{name}"
        current = storage.resolve(uri)
        if current is None:
            raise CorpusRealizedCloudTransportError(f"{label} is absent")
        identity, value = _read_exact_json(storage, current[0], label=label)
        if identity.uri != uri:
            raise CorpusRealizedCloudTransportError(f"{label} URI differs")
        return identity, value

    attempt_identity, attempt = resolved("read-attempt.json", "read attempt")
    source_identity, source = resolved(
        "player-score-source.json", "player score source"
    )
    outcome_identity, outcome_bundle = resolved(
        "actual-player-outcomes.json", "actual outcome bundle"
    )
    completion_identity, completion = resolved(
        "realized-completion.json", "realized completion"
    )
    query = _mapping(attempt.get("query_spec"), label="attempt query spec")
    snapshot = _string(
        query.get("source_snapshot_at"), label="attempt source snapshot"
    )
    supplier_config = outcomes.SupplierConfig(
        run_id=config.run_id,
        job=config.job_name,
        code_sha=config.code_sha,
        image=config.image,
        expected_batch_acceptance_object_sha256=config.batch_acceptance.sha256,
        enabled=True,
    )
    spec = outcomes.build_query_spec(
        config=supplier_config,
        outcome_keys=graph.outcome_keys,
        source_snapshot_at=snapshot,
    )
    try:
        outcomes._validate_attempt(  # noqa: SLF001
            attempt,
            config=supplier_config,
            graph=graph,
            lease=lease_contract,
            spec=spec,
        )
        source_rows = outcomes._validate_source(  # noqa: SLF001
            source,
            graph=graph,
            attempt=attempt,
            attempt_receipt={**attempt_identity.as_dict(), "create_only": True},
            spec=spec,
        )
        rebuilt_outcome = outcomes._build_outcome_bundle(  # noqa: SLF001
            graph,
            source_identity=source_identity.as_dict(),
            rows=outcomes._actual_rows(source_rows),  # noqa: SLF001
        )
        if rebuilt_outcome != outcome_bundle:
            raise CorpusRealizedCloudTransportError(
                "actual outcome bundle replay differs"
            )
        grade = outcomes._grade(  # noqa: SLF001
            graph,
            outcome_bundle=outcome_bundle,
            outcome_identity=outcome_identity.as_dict(),
        )
        outcomes._validate_completion(  # noqa: SLF001
            completion,
            config=supplier_config,
            graph=graph,
            attempt=attempt,
            attempt_receipt={**attempt_identity.as_dict(), "create_only": True},
            source_receipt={**source_identity.as_dict(), "create_only": True},
            outcome_receipt={**outcome_identity.as_dict(), "create_only": True},
            grade=grade,
        )
    except outcomes.CorpusRealizedOutcomeError as exc:
        raise CorpusRealizedCloudTransportError(
            "realized completion independent replay failed"
        ) from exc
    if query.get("job_id") != config.query_job_id:
        raise CorpusRealizedCloudTransportError(
            "worker used a different BigQuery job id"
        )
    return completion_identity, completion


def finish_execution(
    *,
    storage: ObjectStore,
    config: RunConfig,
    execution: object,
    parked_job: object,
    executions: object,
    schedulers: object,
    all_regions_complete: bool,
    created_at_utc: str,
    completion_validator: CompletionValidator = validate_worker_completion,
) -> dict[str, object]:
    """Accept one strict success; lease disposition remains mandatory."""
    config = validate_run_config(config)
    intent_identity, intent = _load_launch(storage, config=config)
    binding_identity, binding = _load_binding(
        storage, config=config, intent=intent_identity
    )
    parked = validate_parked_job(parked_job, config=config)
    if parked != intent["parked_job"]:
        raise CorpusRealizedCloudTransportError("terminal parked job changed")
    validate_scheduler_census(
        schedulers,
        job_name=config.job_name,
        all_regions_complete=all_regions_complete,
    )
    require_no_active_executions(executions)
    expected_names = set(_sequence(
        intent["execution_names_before"], label="prelaunch execution names"
    )) | {str(_mapping(binding["execution"], label="bound execution")["execution_id"])}
    if set(execution_names(executions)) != expected_names:
        raise CorpusRealizedCloudTransportError(
            "terminal execution census does not prove one governed launch"
        )
    runtime = _execution_runtime(
        execution, config=config, intent=intent, require_terminal=True
    )
    bound = _mapping(binding["execution"], label="bound execution")
    if (
        runtime["execution_id"] != bound.get("execution_id")
        or runtime["execution_uid"] != bound.get("execution_uid")
    ):
        raise CorpusRealizedCloudTransportError(
            "terminal execution differs from bound execution"
        )
    completion_identity, completion = completion_validator(storage, config)
    if (
        completion.get("run_id") != config.run_id
        or completion.get("batch_acceptance")
        != config.batch_acceptance.as_dict()
        or completion.get("one_historical_outcome_read") is not True
        or completion.get("independent_replay_complete") is not True
        or completion.get("historical_outcome_lease_release_required") is not True
        or completion.get("historical_retry_licensed") is not False
        or completion.get("decision_authority") is not False
    ):
        raise CorpusRealizedCloudTransportError(
            "worker realized completion differs"
        )
    body = {
        "schema_version": TERMINAL_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="terminal acceptance"
        ),
        "run": config.as_dict(),
        "launch_intent": intent_identity.as_dict(),
        "execution_binding": binding_identity.as_dict(),
        "execution": runtime,
        "realized_completion": completion_identity.as_dict(),
        "realized_grade_sha256": completion["realized_grade_sha256"],
        "query_job_id": config.query_job_id,
        "strict_terminal_success": True,
        "one_execution": True,
        "task_attempt": 0,
        "retry_count": 0,
        "job_remains_parked": True,
        "no_active_executions": True,
        "no_scheduler_targets_job": True,
        "historical_lease_release_required": True,
        "automatic_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    terminal = _with_self_hash(body, field="terminal_acceptance_sha256")
    identity = _publish(
        storage,
        uri=_fixed_uri(config, "terminal-acceptance.json"),
        value=terminal,
        label="terminal acceptance",
    )
    return {
        "schema_version": "corpus-realized-terminal-accepted/v1",
        "run_id": config.run_id,
        "execution_id": runtime["execution_id"],
        "terminal_acceptance": identity.as_dict(),
        "historical_lease_release_required": True,
        "automatic_retry_licensed": False,
    }


def _load_terminal(
    storage: ObjectStore, *, config: RunConfig,
) -> tuple[ObjectIdentity, dict[str, object]]:
    uri = _fixed_uri(config, "terminal-acceptance.json")
    resolved = storage.resolve(uri)
    if resolved is None:
        raise CorpusRealizedCloudTransportError("terminal acceptance is absent")
    identity, value = _read_exact_json(
        storage, resolved[0], label="terminal acceptance"
    )
    item = _self_hash(
        value,
        field="terminal_acceptance_sha256",
        label="terminal acceptance",
    )
    if (
        identity.uri != uri
        or item.get("schema_version") != TERMINAL_SCHEMA
        or item.get("run") != config.as_dict()
        or item.get("strict_terminal_success") is not True
        or item.get("historical_lease_release_required") is not True
        or item.get("automatic_retry_licensed") is not False
    ):
        raise CorpusRealizedCloudTransportError("terminal acceptance differs")
    return identity, item


def _active_lease(
    storage: ObjectStore, *, config: RunConfig,
) -> tuple[ObjectIdentity, bytes]:
    _, contract = load_lease_contract(storage, config=config)
    expected = ObjectIdentity.from_value(
        contract["object_receipt"], label="active lease"
    )
    resolved = storage.resolve(lease_adapter.HISTORICAL_OUTCOME_LEASE_URI)
    if resolved is None:
        raise CorpusRealizedCloudTransportError("active lease is absent")
    current = ObjectIdentity.from_value(resolved[0], label="live active lease")
    if current != expected or resolved[1] != lease_validation.canonical_json(
        contract["body"]
    ):
        raise CorpusRealizedCloudTransportError(
            "active historical lease changed"
        )
    return current, resolved[1]


def _disposition_intent(
    *,
    storage: ObjectStore,
    config: RunConfig,
    disposition: str,
    created_at_utc: str,
    reason: str | None,
    terminal_identity: ObjectIdentity | None,
) -> tuple[ObjectIdentity, dict[str, object], ObjectIdentity]:
    if disposition not in {"release", "abandon"}:
        raise CorpusRealizedCloudTransportError("lease disposition differs")
    if disposition == "release" and terminal_identity is None:
        raise CorpusRealizedCloudTransportError(
            "lease release requires terminal acceptance"
        )
    if disposition == "abandon" and (
        reason is None or _REASON.fullmatch(reason) is None
    ):
        raise CorpusRealizedCloudTransportError(
            "lease abandonment reason differs"
        )
    _, contract = load_lease_contract(storage, config=config)
    expected_active = ObjectIdentity.from_value(
        contract["object_receipt"], label="expected active lease"
    )
    uri = _fixed_uri(config, f"lease-{disposition}-intent.json")
    existing = storage.resolve(uri)
    if existing is not None:
        identity, value = _read_exact_json(
            storage, existing[0], label=f"lease {disposition} intent"
        )
        item = _self_hash(
            value,
            field="lease_disposition_intent_sha256",
            label=f"lease {disposition} intent",
        )
        if (
            item.get("schema_version") != LEASE_DISPOSITION_INTENT_SCHEMA
            or item.get("run") != config.as_dict()
            or item.get("disposition") != disposition
            or item.get("active_lease") != expected_active.as_dict()
            or item.get("terminal_acceptance")
            != (terminal_identity.as_dict() if terminal_identity else None)
            or item.get("reason") != reason
        ):
            raise CorpusRealizedCloudTransportError(
                f"lease {disposition} recovery intent differs"
            )
        return identity, item, expected_active
    body = {
        "schema_version": LEASE_DISPOSITION_INTENT_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label=f"lease {disposition} intent"
        ),
        "run": config.as_dict(),
        "disposition": disposition,
        "reason": reason,
        "active_lease": expected_active.as_dict(),
        "terminal_acceptance": (
            terminal_identity.as_dict() if terminal_identity else None
        ),
        "generation_matched_delete_required": True,
        "automatic_retry_licensed": False,
    }
    intent = _with_self_hash(
        body, field="lease_disposition_intent_sha256"
    )
    identity = _publish(
        storage, uri=uri, value=intent, label=f"lease {disposition} intent"
    )
    return identity, intent, expected_active


def _delete_or_recover_absent(
    storage: ObjectStore, *, expected: ObjectIdentity,
) -> None:
    current = storage.resolve(expected.uri)
    if current is not None:
        identity = ObjectIdentity.from_value(current[0], label="live lease")
        if identity != expected:
            raise CorpusRealizedCloudTransportError(
                "live lease generation changed; deletion refused"
            )
        try:
            storage.delete_exact(expected.as_dict())
        except Exception as exc:
            raise CorpusRealizedCloudTransportError(
                "generation-matched lease deletion failed"
            ) from exc
    if storage.resolve(expected.uri) is not None:
        raise CorpusRealizedCloudTransportError(
            "historical lease remains live after disposition"
        )


def release_historical_lease(
    *, storage: ObjectStore, config: RunConfig, created_at_utc: str,
) -> dict[str, object]:
    """Release only after terminal acceptance; recover safely after deletion."""
    config = validate_run_config(config)
    terminal_identity, terminal = _load_terminal(storage, config=config)
    del terminal
    if storage.resolve(_fixed_uri(config, "lease-abandonment.json")) is not None:
        raise CorpusRealizedCloudTransportError(
            "abandoned lease cannot also be released"
        )
    intent_identity, _, active = _disposition_intent(
        storage=storage,
        config=config,
        disposition="release",
        created_at_utc=created_at_utc,
        reason=None,
        terminal_identity=terminal_identity,
    )
    _delete_or_recover_absent(storage, expected=active)
    body = {
        "schema_version": LEASE_RELEASE_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="lease release"
        ),
        "run": config.as_dict(),
        "lease_release_intent": intent_identity.as_dict(),
        "terminal_acceptance": terminal_identity.as_dict(),
        "released_active_lease": active.as_dict(),
        "generation_matched_delete": True,
        "active_lease_absent_after_delete": True,
        "historical_outcome_read_closed": True,
        "automatic_retry_licensed": False,
        "decision_authority": False,
    }
    release = _with_self_hash(body, field="lease_release_sha256")
    identity = _publish(
        storage,
        uri=_fixed_uri(config, "lease-release.json"),
        value=release,
        label="lease release receipt",
    )
    return {
        "schema_version": "corpus-realized-run-closed/v1",
        "run_id": config.run_id,
        "disposition": "terminal-success-lease-released",
        "lease_release": identity.as_dict(),
        "active_lease_absent": True,
        "automatic_retry_licensed": False,
    }


def abandon_historical_lease(
    *,
    storage: ObjectStore,
    config: RunConfig,
    reason: str,
    created_at_utc: str,
) -> dict[str, object]:
    """Archive and delete this run's lease; the consumed run cannot retry."""
    config = validate_run_config(config)
    if storage.resolve(_fixed_uri(config, "terminal-acceptance.json")) is not None:
        raise CorpusRealizedCloudTransportError(
            "terminal-success lease must be released, not abandoned"
        )
    if storage.resolve(_fixed_uri(config, "lease-release.json")) is not None:
        raise CorpusRealizedCloudTransportError(
            "released lease cannot also be abandoned"
        )
    intent_identity, _, active = _disposition_intent(
        storage=storage,
        config=config,
        disposition="abandon",
        created_at_utc=created_at_utc,
        reason=reason,
        terminal_identity=None,
    )
    archive_uri = _fixed_uri(config, "abandoned-historical-lease.json")
    archive_current = storage.resolve(archive_uri)
    live_current = storage.resolve(active.uri)
    if live_current is not None:
        live_identity = ObjectIdentity.from_value(
            live_current[0], label="live lease before abandonment"
        )
        if live_identity != active:
            raise CorpusRealizedCloudTransportError(
                "live lease changed before abandonment"
            )
        active_raw = live_current[1]
    elif archive_current is not None:
        active_raw = archive_current[1]
    else:
        raise CorpusRealizedCloudTransportError(
            "neither active nor archived lease is available for recovery"
        )
    archive_identity = _publish_raw(
        storage,
        uri=archive_uri,
        raw=active_raw,
        label="abandoned historical lease archive",
    )
    if archive_identity.sha256 != active.sha256 or archive_identity.bytes != active.bytes:
        raise CorpusRealizedCloudTransportError(
            "abandoned lease archive bytes differ"
        )
    _delete_or_recover_absent(storage, expected=active)
    body = {
        "schema_version": LEASE_ABANDON_SCHEMA,
        "created_at_utc": _timestamp(
            created_at_utc, label="lease abandonment"
        ),
        "run": config.as_dict(),
        "lease_abandon_intent": intent_identity.as_dict(),
        "reason": reason,
        "abandoned_active_lease": active.as_dict(),
        "archived_lease": archive_identity.as_dict(),
        "generation_matched_delete": True,
        "active_lease_absent_after_delete": True,
        "run_namespace_permanently_consumed": True,
        "historical_outcome_read_closed": True,
        "automatic_retry_licensed": False,
        "historical_retune_licensed": False,
        "decision_authority": False,
    }
    abandoned = _with_self_hash(body, field="lease_abandonment_sha256")
    identity = _publish(
        storage,
        uri=_fixed_uri(config, "lease-abandonment.json"),
        value=abandoned,
        label="lease abandonment receipt",
    )
    return {
        "schema_version": "corpus-realized-run-abandoned/v1",
        "run_id": config.run_id,
        "disposition": "failed-closed-lease-abandoned",
        "reason": reason,
        "lease_abandonment": identity.as_dict(),
        "active_lease_absent": True,
        "automatic_retry_licensed": False,
    }


class GoogleCloudObjectStore:
    """Generation-pinned GCS store used only after the explicit execute gate."""

    def __init__(
        self, *, execute: bool, environ: Mapping[str, str], project: str = PROJECT,
    ) -> None:
        require_execute_gate(execute=execute, environ=environ)
        from google.cloud import storage

        self._client = storage.Client(project=project)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        retained = _gcs_uri(uri, label="GCS object")
        bucket, name = retained.removeprefix("gs://").split("/", 1)
        return bucket, name

    def read(self, identity: Mapping[str, object]) -> bytes:
        retained = ObjectIdentity.from_value(identity, label="GCS read")
        bucket, name = self._parts(retained.uri)
        try:
            blob = self._client.bucket(bucket).blob(
                name, generation=int(retained.generation)
            )
            raw = blob.download_as_bytes(
                if_generation_match=int(retained.generation)
            )
        except Exception as exc:
            raise CorpusRealizedCloudTransportError(
                "GCS generation-pinned read failed"
            ) from exc
        if len(raw) != retained.bytes or sha256(raw).hexdigest() != retained.sha256:
            raise CorpusRealizedCloudTransportError("GCS read identity differs")
        return raw

    def resolve(self, uri: str) -> tuple[dict[str, object], bytes] | None:
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.reload()
        except Exception as exc:
            if type(exc).__name__ == "NotFound":
                return None
            raise CorpusRealizedCloudTransportError(
                "GCS object resolution failed"
            ) from exc
        generation = _blob_generation(
            blob.generation, label="resolved GCS generation"
        )
        pinned = self._client.bucket(bucket).blob(
            name, generation=int(generation)
        )
        raw = pinned.download_as_bytes(if_generation_match=int(generation))
        return ({
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, raw)

    def publish_or_reopen(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            raise CorpusRealizedCloudTransportError(
                "create-once payload differs"
            )
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
        except Exception as exc:
            if type(exc).__name__ != "PreconditionFailed":
                raise CorpusRealizedCloudTransportError(
                    "GCS create-once publication failed"
                ) from exc
            current = self.resolve(uri)
            if current is None or current[1] != raw:
                raise CorpusRealizedCloudTransportError(
                    "GCS create-once collision differs"
                ) from exc
            return current[0]
        generation = _blob_generation(
            blob.generation, label="published GCS generation"
        )
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read(identity) != raw:
            raise CorpusRealizedCloudTransportError(
                "GCS created object reopen differs"
            )
        return identity

    def delete_exact(self, identity: Mapping[str, object]) -> None:
        retained = ObjectIdentity.from_value(identity, label="GCS deletion")
        bucket, name = self._parts(retained.uri)
        try:
            self._client.bucket(bucket).blob(
                name, generation=int(retained.generation)
            ).delete(if_generation_match=int(retained.generation))
        except Exception as exc:
            raise CorpusRealizedCloudTransportError(
                "GCS generation-matched delete failed"
            ) from exc


class GoogleBigQueryJobInspector:
    """Read-only negative lookup for the deterministic one-query job id."""

    def __init__(self, *, project: str = PROJECT) -> None:
        from google.cloud import bigquery

        self._client = bigquery.Client(project=project)

    def prove_unused(
        self, *, config: RunConfig, observed_at_utc: str,
    ) -> dict[str, object]:
        config = validate_run_config(config)
        try:
            self._client.get_job(
                config.query_job_id, project=PROJECT, location=LOCATION
            )
        except Exception as exc:
            if type(exc).__name__ != "NotFound":
                raise CorpusRealizedCloudTransportError(
                    "BigQuery deterministic job-id lookup failed"
                ) from exc
        else:
            raise CorpusRealizedCloudTransportError(
                "deterministic BigQuery job id is already used; never launch"
            )
        return query_unused_proof(
            config=config, observed_at_utc=observed_at_utc
        )


__all__ = [
    "BUILD_ENV",
    "CODE_ENV",
    "CorpusRealizedCloudTransportError",
    "ENABLE_ENV",
    "EXPECTED_MAX_RETRIES",
    "EXPECTED_PARALLELISM",
    "EXPECTED_RESOURCES",
    "EXPECTED_TASK_COUNT",
    "EXPECTED_TIMEOUT_SECONDS",
    "GoogleBigQueryJobInspector",
    "GoogleCloudObjectStore",
    "IMAGE_ENV",
    "ObjectIdentity",
    "PARKED_ARGS",
    "PARKED_COMMAND",
    "PROJECT",
    "REGION",
    "RunConfig",
    "WORKER_ENABLE_ENV",
    "abandon_historical_lease",
    "acquire_historical_lease",
    "bind_execution",
    "canonical_json_bytes",
    "canonical_sha256",
    "confirm_query_unused",
    "execution_names",
    "finish_execution",
    "lease_receipt_identity",
    "load_lease_contract",
    "prepare_launch",
    "query_unused_proof",
    "release_historical_lease",
    "require_execute_gate",
    "validate_build_metadata",
    "validate_parked_job",
    "validate_reuse_preflight",
    "validate_run_config",
    "validate_scheduler_census",
    "validate_worker_completion",
    "worker_args",
]
