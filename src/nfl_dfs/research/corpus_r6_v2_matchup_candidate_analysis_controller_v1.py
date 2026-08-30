"""One-job Cloud Run controller for the canonical outcome-blind R6-v2 release.

The scientific release module owns every candidate/book/prefix assertion.  This
module owns only the provider boundary around it: one existing Cloud Run job is
snapshotted, used for six fixed phases, and restored exactly.  Provider
mutation is impossible through this API unless a fresh create-once claim was
published first.

The fixed phase order is::

    prepare -> task0-worker -> task0-verifier -> full-workers
            -> full-verifiers -> finish -> independent-reopen -> restore

The two fan-out phases always use all 54 Cloud Run task indices.  Task zero is
therefore replayed/recovered after the canary; the canonical release still
proves one distinct worker/verifier process pair for every accepted slate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Final, Protocol

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_analysis_release_v2 as release,
)
from nfl_dfs.research.corpus_neo4j_transport import ExactObjectStore, ObjectIdentity


CONTROLLER_MANIFEST_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-one-job-controller-manifest/v1"
)
JOB_SNAPSHOT_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-one-job-snapshot/v1"
)
MUTATION_CLAIM_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-one-job-mutation-claim/v1"
)
EXECUTION_BINDING_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-one-job-execution-binding/v1"
)
PHASE_STATUS_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-one-job-phase-status/v1"
)
PHASE_ACCEPTANCE_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-one-job-phase-acceptance/v1"
)
RESTORATION_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-one-job-restoration/v1"
)
REOPEN_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-one-job-independent-reopen/v1"
)

PHASES: Final = (
    "prepare",
    "task0-worker",
    "task0-verifier",
    "full-workers",
    "full-verifiers",
    "finish",
)
PHASE_TASK_COUNTS: Final = {
    "prepare": 1,
    "task0-worker": 1,
    "task0-verifier": 1,
    "full-workers": release.AUTHORITATIVE_SLATE_COUNT,
    "full-verifiers": release.AUTHORITATIVE_SLATE_COUNT,
    "finish": 1,
}
PHASE_ROLES: Final = {
    "prepare": "prepare",
    "task0-worker": "run-worker",
    "task0-verifier": "verify-worker",
    "full-workers": "run-worker",
    "full-verifiers": "verify-worker",
    "finish": "finish",
}
PUBLICATION_MODE: Final = "create_once"
MAX_RETRIES: Final = 0
DEFAULT_TIMEOUT_SECONDS: Final = 14_400
DEFAULT_CPU: Final = "4"
DEFAULT_MEMORY: Final = "16Gi"
DISPATCH_PYTHON: Final = "python"
DISPATCH_SCRIPT: Final = (
    "/app/scripts/"
    "run_corpus_r6_v2_matchup_candidate_analysis_controller_v1.py"
)
DISPATCH_ARGS: Final = (DISPATCH_SCRIPT, "dispatch", "--execute")
ON_IMAGE_RUNTIME_AUTHORITY_RELATIVE_PATH: Final = (
    "runtime/r6-v2-runtime-authority.json"
)
MANIFEST_IDENTITY_ENV: Final = "R6_V2_CONTROLLER_MANIFEST_IDENTITY_B64"
PHASE_ENV: Final = "R6_V2_CONTROLLER_PHASE"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_GENERATION = re.compile(r"[1-9][0-9]*")
_JOB = re.compile(r"[a-z][a-z0-9-]{0,61}[a-z0-9]")
_EXECUTION = re.compile(r"[a-z][a-z0-9-]{0,61}[a-z0-9]")
_UID = re.compile(r"[^\s]{1,256}")
_IMAGE = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}")
_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,79}")
_PROJECT = re.compile(r"[a-z][a-z0-9-]{4,62}")
_REGION = re.compile(r"[a-z]+-[a-z]+[0-9]")

_VOLATILE_ANNOTATIONS: Final = frozenset({
    "run.googleapis.com/client-name",
    "run.googleapis.com/client-version",
    "run.googleapis.com/lastModifier",
    "run.googleapis.com/operation-id",
})
_VOLATILE_LABELS: Final = frozenset({"run.googleapis.com/lastUpdatedTime"})
_FORBIDDEN_NORMALIZED_KEYS: Final = frozenset({
    "actualpoints", "actualscore", "contestfinish", "contestplace",
    "contestrank", "contestscore", "entryrank", "historicalgrader",
    "historicaloutcome", "historicalscoring", "lineupactual",
    "lineuppoints", "lineupscore", "outcomereader", "outcomes",
    "payout", "realized", "realizedoutcome", "realizedpoints",
    "realizedreader", "realizedscore", "scorereader", "winner",
    "winningscore",
})
_FALSE_AUTHORITY_FIELDS: Final = {
    "analytical_authority": False,
    "automatic_retry_licensed": False,
    "decision_authority": False,
    "graph_mutation_licensed": False,
    "historical_scoring_licensed": False,
    "outcome_authority": False,
    "production_change_licensed": False,
    "production_policy_authority": False,
    "promotion_authority": False,
    "uses_realized_outcomes": False,
}


class CorpusR6V2MatchupCandidateAnalysisControllerV1Error(RuntimeError):
    """The one-job controller cannot preserve its exact provider boundary."""


class FreshClaimStore(ExactObjectStore, Protocol):
    """Exact store with a non-idempotent operation for provider claims."""

    def claim_create_once(self, uri: str, raw: bytes) -> ObjectIdentity: ...


def _fail(message: str) -> None:
    raise CorpusR6V2MatchupCandidateAnalysisControllerV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or any(ch == "\x00" for ch in value):
        _fail(f"{label} must be one nonempty string")
    return value


def _integer(
    value: object, *, label: str, minimum: int = 0, maximum: int | None = None,
) -> int:
    if type(value) is not int or value < minimum or (
        maximum is not None and value > maximum
    ):
        _fail(f"{label} differs")
    return value


def _digest(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if _SHA256.fullmatch(retained) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return retained


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisControllerV1Error(str(exc)) from exc


def _object_identity(value: object, *, label: str) -> ObjectIdentity:
    item = _identity(value, label=label)
    return ObjectIdentity(
        uri=str(item["uri"]), generation=str(item["generation"]),
        sha256=str(item["sha256"]), bytes=int(item["bytes"]),
    )


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        _fail(f"{field} supplied before hashing")
    result = dict(value)
    result[field] = batch.canonical_sha256(result)
    return result


def _validate_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label} {field}")
    body = {key: child for key, child in value.items() if key != field}
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _normalized_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def reject_outcome_carriers_v1(value: object, *, label: str) -> None:
    """Reject outcome/scoring carrier keys and environment-variable names."""
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized = _normalized_key(key)
            policy_declaration = (
                (key in _FALSE_AUTHORITY_FIELDS and child is False)
                or (key == "outcome_columns_read" and child == [])
            )
            if not policy_declaration and (
                normalized in _FORBIDDEN_NORMALIZED_KEYS or any(
                token in normalized
                for token in ("realizedoutcome", "outcomereader", "scorereader")
                )
            ):
                _fail(f"{label} carries forbidden outcome field {key!r}")
            if key == "name" and type(child) is str:
                env_name = _normalized_key(child)
                if env_name in _FORBIDDEN_NORMALIZED_KEYS or any(
                    token in env_name for token in (
                        "realizedoutcome", "outcomereader", "scorereader",
                    )
                ):
                    _fail(f"{label} carries forbidden environment name")
            reject_outcome_carriers_v1(child, label=label)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            reject_outcome_carriers_v1(child, label=label)


def _read_raw(
    storage: ExactObjectStore, identity: object, *, label: str,
) -> tuple[dict[str, object], bytes]:
    retained = _identity(identity, label=f"{label} identity")
    try:
        raw = storage.read_exact(_object_identity(retained, label=label))
    except Exception as exc:
        raise CorpusR6V2MatchupCandidateAnalysisControllerV1Error(
            f"{label} generation-exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != retained["bytes"]
        or sha256(raw).hexdigest() != retained["sha256"]
    ):
        _fail(f"{label} content identity differs")
    return retained, raw


def _read_json(
    storage: ExactObjectStore, identity: object, *, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    retained, raw = _read_raw(storage, identity, label=label)
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6V2MatchupCandidateAnalysisControllerV1Error(str(exc)) from exc
    return retained, _mapping(value, label=label)


def publish_json_v1(
    *, storage: ExactObjectStore, uri: str, value: Mapping[str, object],
    label: str,
) -> dict[str, object]:
    raw = batch.canonical_json_bytes(value)
    try:
        identity = storage.publish_create_once(uri, raw)
        reopened = storage.read_exact(identity)
    except Exception as exc:
        raise CorpusR6V2MatchupCandidateAnalysisControllerV1Error(
            f"{label} create-once publication failed"
        ) from exc
    if identity.uri != uri or reopened != raw:
        _fail(f"{label} exact reopen differs")
    return identity.as_dict()


def publish_fresh_claim_v1(
    *, storage: FreshClaimStore, uri: str, value: Mapping[str, object],
    label: str,
) -> dict[str, object]:
    claim = getattr(storage, "claim_create_once", None)
    if not callable(claim):
        _fail("provider mutation requires a fresh-claim-capable store")
    raw = batch.canonical_json_bytes(value)
    try:
        identity = claim(uri, raw)
        reopened = storage.read_exact(identity)
    except Exception as exc:
        raise CorpusR6V2MatchupCandidateAnalysisControllerV1Error(
            f"{label} fresh create-once claim failed; automatic retry is forbidden"
        ) from exc
    if identity.uri != uri or reopened != raw:
        _fail(f"{label} fresh claim exact reopen differs")
    return identity.as_dict()


def output_prefix_v1(value: object) -> str:
    prefix = _string(value, label="controller output prefix")
    if (
        not prefix.startswith("gs://") or not prefix.endswith("/")
        or "//" in prefix[5:]
    ):
        _fail("controller output prefix must be a canonical non-root GCS prefix")
    bucket, marker, name = prefix[5:].partition("/")
    if not bucket or not marker or not name:
        _fail("controller output prefix differs")
    return prefix


def _short_name(value: object, *, label: str, pattern: re.Pattern[str]) -> str:
    retained = _string(value, label=label).rsplit("/", 1)[-1]
    if pattern.fullmatch(retained) is None:
        _fail(f"{label} differs")
    return retained


def _job_parts(
    value: object, *, expected_job: str | None = None,
    expected_uid: str | None = None,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    job = _mapping(value, label="provider job")
    metadata = _mapping(job.get("metadata"), label="provider job metadata")
    name = _short_name(metadata.get("name"), label="job name", pattern=_JOB)
    uid = _string(metadata.get("uid"), label="job UID")
    if _UID.fullmatch(uid) is None:
        _fail("job UID differs")
    if expected_job is not None and name != expected_job:
        _fail("provider job name differs")
    if expected_uid is not None and uid != expected_uid:
        _fail("provider job UID differs")
    spec = _mapping(job.get("spec"), label="provider job spec")
    outer = _mapping(
        _mapping(spec.get("template"), label="job template").get("spec"),
        label="job outer spec",
    )
    task = _mapping(
        _mapping(outer.get("template"), label="job task template").get("spec"),
        label="job task spec",
    )
    containers = _sequence(task.get("containers"), label="job containers")
    if len(containers) != 1:
        _fail("reused job must have exactly one container")
    return job, metadata, outer, _mapping(containers[0], label="job container")


def stable_job_v1(value: object) -> dict[str, object]:
    job, metadata, _, _ = _job_parts(value)
    annotations = _mapping(metadata.get("annotations", {}), label="job annotations")
    labels = _mapping(metadata.get("labels", {}), label="job labels")
    for key in _VOLATILE_ANNOTATIONS:
        annotations.pop(key, None)
    for key in _VOLATILE_LABELS:
        labels.pop(key, None)
    return {
        "name": _short_name(metadata["name"], label="job name", pattern=_JOB),
        "uid": metadata["uid"],
        "annotations": annotations,
        "labels": labels,
        "spec": job["spec"],
    }


def _environment(value: object, *, label: str) -> dict[str, str]:
    rows = _sequence(value, label=label)
    retained: dict[str, str] = {}
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"{label}[{ordinal}]")
        if set(row) != {"name", "value"}:
            _fail(f"{label} may not use secrets or valueFrom")
        name = _string(row["name"], label=f"{label}[{ordinal}] name")
        child = _string(row["value"], label=f"{label}[{ordinal}] value")
        if name in retained:
            _fail(f"{label} repeats a name")
        retained[name] = child
    reject_outcome_carriers_v1(
        [{"name": key, "value": child} for key, child in retained.items()],
        label=label,
    )
    return retained


def _has_attachment(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = _normalized_key(str(key))
            if any(token in normalized for token in (
                "cloudsql", "networkinterface", "secretkeyref",
                "valuefrom", "vpcaccess", "vpcconnector",
            )) and child not in (None, "", [], {}):
                return True
            if _has_attachment(child):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_has_attachment(child) for child in value)
    return False


def validate_reusable_job_v1(
    value: object, *, expected_job: str, expected_uid: str,
) -> dict[str, object]:
    job, metadata, outer, container = _job_parts(
        value, expected_job=expected_job, expected_uid=expected_uid,
    )
    task = _mapping(
        _mapping(outer.get("template"), label="job task template").get("spec"),
        label="job task spec",
    )
    status = _mapping(job.get("status", {}), label="job status")
    generation = str(metadata.get("generation", ""))
    observed = str(status.get("observedGeneration", ""))
    conditions = _sequence(status.get("conditions", []), label="job conditions")
    ready = any(
        isinstance(row, Mapping) and row.get("type") == "Ready" and (
            row.get("status") in {True, "True"}
            or row.get("state") == "CONDITION_SUCCEEDED"
        ) for row in conditions
    )
    environment = _environment(container.get("env", []), label="job environment")
    if (
        not generation.isdigit() or int(generation) < 1
        or observed != generation or not ready
        or task.get("maxRetries") != 0
        or task.get("volumes", []) != []
        or container.get("volumeMounts", []) != []
        or _has_attachment(job)
    ):
        _fail("reused job is not reconciled, retry-free, and attachment-free")
    reject_outcome_carriers_v1(job, label="reused job")
    return {
        "job_name": expected_job,
        "job_uid": expected_uid,
        "job_generation": generation,
        "service_account": _string(
            task.get("serviceAccountName"), label="job service account"
        ),
        "environment": environment,
        "stable_job": stable_job_v1(job),
        "stable_job_sha256": batch.canonical_sha256(stable_job_v1(job)),
        "provider_observed": True,
    }


def _execution_terminal_state(value: Mapping[str, object]) -> str:
    status = _mapping(value.get("status", {}), label="execution status")
    conditions = _sequence(status.get("conditions", []), label="execution conditions")
    completed = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if not completed:
        return "ACTIVE"
    if len(completed) != 1:
        _fail("execution has multiple Completed conditions")
    row = completed[0]
    if row.get("state") == "CONDITION_SUCCEEDED" or row.get("status") in {
        True, "True",
    }:
        return "SUCCEEDED"
    if row.get("state") in {"CONDITION_FAILED", "CONDITION_CANCELLED"} or (
        row.get("status") in {False, "False"}
    ):
        return "FAILED"
    return "ACTIVE"


def validate_no_active_executions_v1(value: object, *, job_name: str) -> list[str]:
    rows = _sequence(value, label="provider execution census")
    names: list[str] = []
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"provider execution census[{ordinal}]")
        metadata = _mapping(row.get("metadata"), label="execution metadata")
        name = _short_name(metadata.get("name"), label="execution name", pattern=_EXECUTION)
        labels = _mapping(metadata.get("labels", {}), label="execution labels")
        owner = labels.get("run.googleapis.com/job")
        if owner is not None and _short_name(owner, label="execution job", pattern=_JOB) != job_name:
            _fail("execution census carries another job")
        if _execution_terminal_state(row) == "ACTIVE":
            _fail("active execution forbids reused-job mutation")
        names.append(name)
    if len(names) != len(set(names)):
        _fail("provider execution census repeats an execution")
    return sorted(names)


def validate_scheduler_census_v1(
    value: object, *, job_name: str, all_regions_complete: bool,
) -> None:
    if all_regions_complete is not True:
        _fail("all-region scheduler census is required")
    needle = f"/jobs/{job_name}:run"
    for raw in _sequence(value, label="scheduler census"):
        row = _mapping(raw, label="scheduler census row")
        target = row.get("httpTarget", {})
        if isinstance(target, Mapping) and needle in str(target.get("uri", "")):
            _fail("a scheduler targets the reused job")


def build_job_snapshot_v1(
    *, job: object, exported_job: bytes, executions: object,
    schedulers: object, all_regions_complete: bool, job_name: str,
    job_uid: str,
) -> dict[str, object]:
    if type(exported_job) is not bytes or not exported_job:
        _fail("exported job bytes differ")
    reusable = validate_reusable_job_v1(
        job, expected_job=job_name, expected_uid=job_uid,
    )
    names = validate_no_active_executions_v1(executions, job_name=job_name)
    validate_scheduler_census_v1(
        schedulers, job_name=job_name,
        all_regions_complete=all_regions_complete,
    )
    return _with_hash({
        "schema_version": JOB_SNAPSHOT_SCHEMA,
        "job_name": job_name,
        "job_uid": job_uid,
        "job_generation": reusable["job_generation"],
        "service_account": reusable["service_account"],
        "stable_job": reusable["stable_job"],
        "stable_job_sha256": reusable["stable_job_sha256"],
        "provider_job_observation_sha256": batch.canonical_sha256(
            _mapping(job, label="provider job")
        ),
        "exported_job_sha256": sha256(exported_job).hexdigest(),
        "exported_job_bytes": len(exported_job),
        "execution_names_before": names,
        "no_active_executions": True,
        "all_region_scheduler_census_complete": True,
        "no_scheduler_targets_job": True,
        "maximum_task_retries": 0,
        "attachment_free": True,
        "provider_observed": True,
        **_FALSE_AUTHORITY_FIELDS,
    }, field="job_snapshot_sha256")


def validate_job_snapshot_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="controller job snapshot")
    _validate_hash(item, field="job_snapshot_sha256", label="job snapshot")
    if (
        item.get("schema_version") != JOB_SNAPSHOT_SCHEMA
        or _JOB.fullmatch(str(item.get("job_name", ""))) is None
        or _UID.fullmatch(str(item.get("job_uid", ""))) is None
        or type(item.get("exported_job_bytes")) is not int
        or int(item["exported_job_bytes"]) < 1
        or item.get("stable_job_sha256")
        != batch.canonical_sha256(item.get("stable_job"))
        or item.get("no_active_executions") is not True
        or item.get("all_region_scheduler_census_complete") is not True
        or item.get("no_scheduler_targets_job") is not True
        or item.get("maximum_task_retries") != 0
        or item.get("attachment_free") is not True
        or item.get("provider_observed") is not True
        or any(item.get(key) is not expected for key, expected in _FALSE_AUTHORITY_FIELDS.items())
    ):
        _fail("controller job snapshot differs")
    _digest(item.get("exported_job_sha256"), label="exported job SHA")
    reject_outcome_carriers_v1(item, label="job snapshot")
    return item


def phase_spec_v1(phase: str) -> dict[str, object]:
    if phase not in PHASES:
        _fail("controller phase differs")
    count = PHASE_TASK_COUNTS[phase]
    return {
        "phase": phase,
        "role": PHASE_ROLES[phase],
        "task_count": count,
        "parallelism": count,
        "maximum_task_retries": MAX_RETRIES,
        "expected_task_indices": list(range(count)),
    }


def build_controller_manifest_v1(
    *, run_id: str, controller_output_prefix: str,
    analysis_output_prefix: str, project_id: str, region: str,
    job_snapshot_identity: object, job_snapshot: object,
    job_export_identity: object, panel_index_identity: object,
    lane_terminal_identities: Sequence[object],
    matchup_source_release_identity: object,
    runtime_image_authority_identity: object,
    runtime_image_authority: object,
    embedded_runtime_authority_identity: object,
    embedded_runtime_authority: object,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    cpu: str = DEFAULT_CPU, memory: str = DEFAULT_MEMORY,
) -> dict[str, object]:
    if _RUN_ID.fullmatch(run_id) is None:
        _fail("controller run id differs")
    prefix = output_prefix_v1(controller_output_prefix)
    analysis_prefix = output_prefix_v1(analysis_output_prefix)
    if (
        prefix == analysis_prefix
        or prefix.startswith(analysis_prefix)
        or analysis_prefix.startswith(prefix)
    ):
        _fail("controller governance prefix must be disjoint from science output")
    snapshot = validate_job_snapshot_v1(job_snapshot)
    snapshot_identity = _identity(job_snapshot_identity, label="job snapshot")
    export_identity = _identity(job_export_identity, label="job export")
    if (
        export_identity["sha256"] != snapshot["exported_job_sha256"]
        or export_identity["bytes"] != snapshot["exported_job_bytes"]
    ):
        _fail("job export identity differs from snapshot")
    image_authority = release.validate_provider_runtime_image_authority_v1(
        runtime_image_authority
    )
    embedded = release.validate_embedded_runtime_authority_v1(
        embedded_runtime_authority
    )
    image_identity = _identity(
        runtime_image_authority_identity, label="runtime image authority"
    )
    embedded_identity = _identity(
        embedded_runtime_authority_identity, label="embedded runtime authority"
    )
    if (
        image_identity["uri"]
        != f"{prefix}runtime/provider-image-authority.json"
        or embedded_identity["uri"]
        != f"{prefix}runtime/embedded-runtime-authority.json"
        or image_identity["sha256"]
        != batch.canonical_sha256(image_authority)
        or embedded_identity["sha256"]
        != batch.canonical_sha256(embedded)
        or image_authority["embedded_runtime_authority_sha256"]
        != embedded["runtime_authority_sha256"]
        or image_authority["critical_runtime_paths_sha256"]
        != embedded["critical_runtime_paths_sha256"]
        or image_authority["critical_runtime_files_sha256"]
        != embedded["critical_runtime_files_sha256"]
    ):
        _fail("provider image and embedded runtime authorities differ")
    lane_identities = [
        _identity(value, label=f"lane terminal[{ordinal}]")
        for ordinal, value in enumerate(lane_terminal_identities)
    ]
    if len(lane_identities) != 2:
        _fail("controller requires exactly two lane terminals")
    _integer(timeout_seconds, label="task timeout", minimum=1, maximum=86_400)
    if cpu not in {"1", "2", "4", "8"} or not re.fullmatch(r"[1-9][0-9]*Gi", memory):
        _fail("controller resource envelope differs")
    body = {
        "schema_version": CONTROLLER_MANIFEST_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "run_id": run_id,
        "controller_output_prefix": prefix,
        "analysis_output_prefix": analysis_prefix,
        "project_id": _string(project_id, label="project id"),
        "region": _string(region, label="region"),
        "job_name": snapshot["job_name"],
        "job_uid": snapshot["job_uid"],
        "service_account": snapshot["service_account"],
        "job_snapshot_identity": snapshot_identity,
        "job_snapshot_sha256": snapshot["job_snapshot_sha256"],
        "job_export_identity": export_identity,
        "panel_index_identity": _identity(panel_index_identity, label="panel index"),
        "lane_terminal_identities": lane_identities,
        "matchup_source_release_identity": _identity(
            matchup_source_release_identity, label="matchup source release"
        ),
        "runtime_image_authority_identity": image_identity,
        "provider_runtime_image_authority_sha256": image_authority[
            "provider_runtime_image_authority_sha256"
        ],
        "embedded_runtime_authority_identity": embedded_identity,
        "embedded_runtime_authority_sha256": embedded[
            "runtime_authority_sha256"
        ],
        "source_commit_sha": image_authority["source_commit_sha"],
        "immutable_image": image_authority["immutable_image"],
        "image_digest": image_authority["image_digest"],
        "phases": [phase_spec_v1(phase) for phase in PHASES],
        "task_count_law": [1, 1, 1, 54, 54, 1],
        "source_ordinal_law": "CLOUD_RUN_TASK_INDEX-bijective-0-through-53",
        "worker_verifier_processes_must_be_distinct": True,
        "task_timeout_seconds": timeout_seconds,
        "cpu": cpu,
        "memory": memory,
        "working_directory": "",
        "volumes": [],
        "volume_mounts": [],
        "maximum_task_retries": 0,
        "new_job_creation_allowed": False,
        "restore_exact_snapshot_required": True,
        "independent_terminal_reopen_required": True,
        **_FALSE_AUTHORITY_FIELDS,
    }
    reject_outcome_carriers_v1(body, label="controller manifest")
    return _with_hash(body, field="controller_manifest_sha256")


def validate_controller_manifest_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="controller manifest")
    _validate_hash(
        item, field="controller_manifest_sha256", label="controller manifest"
    )
    phases = _sequence(item.get("phases"), label="controller phases")
    if (
        item.get("schema_version") != CONTROLLER_MANIFEST_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or phases != [phase_spec_v1(phase) for phase in PHASES]
        or item.get("task_count_law") != [1, 1, 1, 54, 54, 1]
        or item.get("maximum_task_retries") != 0
        or item.get("new_job_creation_allowed") is not False
        or item.get("restore_exact_snapshot_required") is not True
        or item.get("independent_terminal_reopen_required") is not True
        or item.get("worker_verifier_processes_must_be_distinct") is not True
        or item.get("working_directory") != ""
        or item.get("volumes") != []
        or item.get("volume_mounts") != []
        or any(item.get(key) is not expected for key, expected in _FALSE_AUTHORITY_FIELDS.items())
    ):
        _fail("controller manifest fixed laws differ")
    controller_prefix = output_prefix_v1(item.get("controller_output_prefix"))
    analysis_prefix = output_prefix_v1(item.get("analysis_output_prefix"))
    if (
        controller_prefix == analysis_prefix
        or controller_prefix.startswith(analysis_prefix)
        or analysis_prefix.startswith(controller_prefix)
    ):
        _fail("controller manifest output prefixes overlap")
    if _RUN_ID.fullmatch(str(item.get("run_id", ""))) is None:
        _fail("controller manifest run id differs")
    if _JOB.fullmatch(str(item.get("job_name", ""))) is None:
        _fail("controller manifest job differs")
    if _IMAGE.fullmatch(str(item.get("immutable_image", ""))) is None:
        _fail("controller manifest image differs")
    if (
        _PROJECT.fullmatch(str(item.get("project_id", ""))) is None
        or _REGION.fullmatch(str(item.get("region", ""))) is None
        or str(item.get("immutable_image", "")).rsplit("@", 1)[-1]
        != str(item.get("image_digest", ""))
    ):
        _fail("controller manifest provider coordinates differ")
    for field in (
        "job_snapshot_identity", "job_export_identity", "panel_index_identity",
        "matchup_source_release_identity", "runtime_image_authority_identity",
        "embedded_runtime_authority_identity",
    ):
        _identity(item.get(field), label=field)
    lanes = _sequence(item.get("lane_terminal_identities"), label="lane terminals")
    if len(lanes) != 2:
        _fail("controller manifest lane count differs")
    for ordinal, identity in enumerate(lanes):
        _identity(identity, label=f"lane terminal[{ordinal}]")
    reject_outcome_carriers_v1(item, label="controller manifest")
    return item


def reopen_controller_manifest_v1(
    *, storage: ExactObjectStore, manifest_identity: object,
) -> tuple[dict[str, object], dict[str, object]]:
    identity, manifest = _read_json(
        storage, manifest_identity, label="controller manifest"
    )
    retained = validate_controller_manifest_v1(manifest)
    expected_uri = f"{retained['controller_output_prefix']}controller-manifest.json"
    if identity["uri"] != expected_uri:
        _fail("controller manifest URI differs")
    snapshot_identity, snapshot = _read_json(
        storage, retained["job_snapshot_identity"], label="job snapshot"
    )
    snapshot = validate_job_snapshot_v1(snapshot)
    if (
        snapshot["job_snapshot_sha256"] != retained["job_snapshot_sha256"]
        or snapshot["job_name"] != retained["job_name"]
        or snapshot["job_uid"] != retained["job_uid"]
    ):
        _fail("controller manifest job snapshot binding differs")
    _, export = _read_raw(
        storage, retained["job_export_identity"], label="job export"
    )
    if (
        sha256(export).hexdigest() != snapshot["exported_job_sha256"]
        or len(export) != snapshot["exported_job_bytes"]
    ):
        _fail("controller manifest job export binding differs")
    image_identity, image = _read_json(
        storage, retained["runtime_image_authority_identity"],
        label="provider runtime image authority",
    )
    image = release.validate_provider_runtime_image_authority_v1(image)
    embedded_identity, embedded = _read_json(
        storage, retained["embedded_runtime_authority_identity"],
        label="embedded runtime authority",
    )
    embedded = release.validate_embedded_runtime_authority_v1(embedded)
    if (
        image_identity["sha256"]
        != batch.canonical_sha256(image)
        or embedded_identity["sha256"]
        != batch.canonical_sha256(embedded)
        or image["provider_runtime_image_authority_sha256"]
        != retained["provider_runtime_image_authority_sha256"]
        or embedded["runtime_authority_sha256"]
        != retained["embedded_runtime_authority_sha256"]
        or image["embedded_runtime_authority_sha256"]
        != embedded["runtime_authority_sha256"]
        or image["immutable_image"] != retained["immutable_image"]
        or image["source_commit_sha"] != retained["source_commit_sha"]
        or image["image_digest"] != retained["image_digest"]
        or image["critical_runtime_paths_sha256"]
        != embedded["critical_runtime_paths_sha256"]
        or image["critical_runtime_files_sha256"]
        != embedded["critical_runtime_files_sha256"]
    ):
        _fail("controller runtime authority replay differs")
    return identity, retained


def phase_job_projection_v1(
    *, manifest: Mapping[str, object], manifest_identity_b64: str, phase: str,
) -> dict[str, object]:
    retained = validate_controller_manifest_v1(manifest)
    spec = phase_spec_v1(phase)
    environment = {
        MANIFEST_IDENTITY_ENV: _string(
            manifest_identity_b64, label="encoded controller manifest identity"
        ),
        PHASE_ENV: phase,
        "GOOGLE_CLOUD_PROJECT": str(retained["project_id"]),
    }
    reject_outcome_carriers_v1(
        [{"name": key, "value": value} for key, value in environment.items()],
        label="phase environment",
    )
    return {
        "job_name": retained["job_name"],
        "job_uid": retained["job_uid"],
        "service_account": retained["service_account"],
        "project_id": retained["project_id"],
        "region": retained["region"],
        "immutable_image": retained["immutable_image"],
        "command": [DISPATCH_PYTHON],
        "args": list(DISPATCH_ARGS),
        "environment": environment,
        "task_count": spec["task_count"],
        "parallelism": spec["parallelism"],
        "maximum_task_retries": 0,
        "timeout_seconds": retained["task_timeout_seconds"],
        "cpu": retained["cpu"],
        "memory": retained["memory"],
        "working_directory": "",
        "volumes": [],
        "volume_mounts": [],
        "provider_observed_required": True,
    }


def build_mutation_claim_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    phase: str, operation: str, predecessor_acceptance_identity: object | None,
) -> dict[str, object]:
    retained = validate_controller_manifest_v1(manifest)
    if operation not in {"configure", "launch", "restore"}:
        _fail("controller mutation operation differs")
    if operation == "restore":
        phase = "restore"
    elif phase not in PHASES:
        _fail("controller mutation phase differs")
    predecessor = None if predecessor_acceptance_identity is None else _identity(
        predecessor_acceptance_identity, label="predecessor phase acceptance"
    )
    expected_predecessor = None
    if phase in PHASES and PHASES.index(phase) > 0:
        expected_predecessor = PHASES[PHASES.index(phase) - 1]
    if (expected_predecessor is None) != (predecessor is None) and operation != "restore":
        _fail("controller mutation predecessor presence differs")
    return _with_hash({
        "schema_version": MUTATION_CLAIM_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "run_id": retained["run_id"],
        "manifest_identity": _identity(manifest_identity, label="controller manifest"),
        "controller_manifest_sha256": retained["controller_manifest_sha256"],
        "phase": phase,
        "operation": operation,
        "predecessor_phase": expected_predecessor,
        "predecessor_acceptance_identity": predecessor,
        "job_name": retained["job_name"],
        "job_uid": retained["job_uid"],
        "immutable_image": retained["immutable_image"],
        "task_count": 0 if phase == "restore" else PHASE_TASK_COUNTS[phase],
        "maximum_task_retries": 0,
        "claim_created_before_provider_mutation": True,
        **_FALSE_AUTHORITY_FIELDS,
    }, field="mutation_claim_sha256")


def validate_mutation_claim_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object,
    phase: str, operation: str,
    predecessor_acceptance_identity: object | None,
) -> dict[str, object]:
    """Require a stored mutation claim to equal its deterministic law exactly."""
    item = _mapping(value, label=f"{phase} {operation} mutation claim")
    expected = build_mutation_claim_v1(
        manifest=manifest, manifest_identity=manifest_identity, phase=phase,
        operation=operation,
        predecessor_acceptance_identity=predecessor_acceptance_identity,
    )
    if item != expected:
        _fail(f"{phase} {operation} mutation claim replay differs")
    reject_outcome_carriers_v1(item, label="mutation claim")
    return item


def phase_uri_v1(manifest: Mapping[str, object], phase: str, name: str) -> str:
    retained = validate_controller_manifest_v1(manifest)
    if phase not in (*PHASES, "restore") or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]*\.json", name
    ):
        _fail("controller phase object name differs")
    return f"{retained['controller_output_prefix']}phases/{phase}/{name}"


def validate_phase_job_observation_v1(
    value: object, *, manifest: Mapping[str, object],
    manifest_identity_b64: str, phase: str,
) -> dict[str, object]:
    retained = validate_controller_manifest_v1(manifest)
    job, metadata, outer, container = _job_parts(
        value, expected_job=str(retained["job_name"]),
        expected_uid=str(retained["job_uid"]),
    )
    task = _mapping(
        _mapping(outer.get("template"), label="job task template").get("spec"),
        label="job task spec",
    )
    projection = phase_job_projection_v1(
        manifest=retained, manifest_identity_b64=manifest_identity_b64,
        phase=phase,
    )
    resources = _mapping(container.get("resources", {}), label="job resources")
    limits = _mapping(resources.get("limits", {}), label="job resource limits")
    timeout = str(task.get("timeoutSeconds", "")).removesuffix("s")
    environment = _environment(container.get("env", []), label="job environment")
    image = str(container.get("image", ""))
    generation = str(metadata.get("generation", ""))
    status = _mapping(job.get("status", {}), label="phase job status")
    observed_generation = str(status.get("observedGeneration", ""))
    conditions = _sequence(status.get("conditions", []), label="phase job conditions")
    ready = any(
        isinstance(row, Mapping) and row.get("type") == "Ready" and (
            row.get("status") in {True, "True"}
            or row.get("state") == "CONDITION_SUCCEEDED"
        )
        for row in conditions
    )
    if (
        image != projection["immutable_image"]
        or _IMAGE.fullmatch(image) is None
        or container.get("command", []) != projection["command"]
        or container.get("args", []) != projection["args"]
        or environment != projection["environment"]
        or outer.get("taskCount") != projection["task_count"]
        or outer.get("parallelism") != projection["parallelism"]
        or task.get("maxRetries") != 0
        or not timeout.isdigit()
        or int(timeout) != projection["timeout_seconds"]
        or limits != {"cpu": projection["cpu"], "memory": projection["memory"]}
        or task.get("serviceAccountName") != projection["service_account"]
        or container.get("workingDir", "") != ""
        or task.get("volumes", []) != []
        or container.get("volumeMounts", []) != []
        or _has_attachment(job)
        or not generation.isdigit()
        or int(generation) < 1
        or observed_generation != generation
        or not ready
    ):
        _fail("provider-observed phase job differs from exact projection")
    return {
        **projection,
        "job_generation": generation,
        "provider_observed": True,
        "provider_raw_job_sha256": batch.canonical_sha256(job),
        "job_projection_sha256": batch.canonical_sha256(projection),
    }


def _execution_parts(
    value: object, *, manifest: Mapping[str, object], phase: str,
) -> tuple[dict[str, object], str, str, dict[str, object], dict[str, object]]:
    execution = _mapping(value, label="provider execution")
    metadata = _mapping(execution.get("metadata"), label="execution metadata")
    name = _short_name(metadata.get("name"), label="execution name", pattern=_EXECUTION)
    uid = _string(metadata.get("uid"), label="execution UID")
    labels = _mapping(metadata.get("labels", {}), label="execution labels")
    job = _short_name(
        labels.get("run.googleapis.com/job"), label="execution job", pattern=_JOB
    )
    job_uid = _string(labels.get("run.googleapis.com/jobUid"), label="execution job UID")
    if job != manifest["job_name"] or job_uid != manifest["job_uid"]:
        _fail("provider execution job identity differs")
    spec = _mapping(execution.get("spec"), label="execution spec")
    template = _mapping(spec.get("template"), label="execution template")
    task = _mapping(template.get("spec"), label="execution task spec")
    containers = _sequence(task.get("containers"), label="execution containers")
    if len(containers) != 1:
        _fail("provider execution container count differs")
    return execution, name, uid, spec, _mapping(containers[0], label="execution container")


def validate_phase_execution_v1(
    value: object, *, manifest: Mapping[str, object],
    manifest_identity_b64: str, phase: str, expected_execution: str,
    expected_job_generation: str, require_terminal: bool,
) -> dict[str, object]:
    retained = validate_controller_manifest_v1(manifest)
    execution, name, uid, spec, container = _execution_parts(
        value, manifest=retained, phase=phase,
    )
    if name != expected_execution:
        _fail("provider execution name differs")
    labels = _mapping(
        _mapping(execution.get("metadata"), label="execution metadata").get(
            "labels", {}
        ),
        label="execution labels",
    )
    if (
        not expected_job_generation.isdigit()
        or int(expected_job_generation) < 1
        or str(labels.get("run.googleapis.com/jobGeneration"))
        != expected_job_generation
    ):
        _fail("provider execution job generation differs")
    task = _mapping(
        _mapping(spec.get("template"), label="execution template").get("spec"),
        label="execution task spec",
    )
    projection = phase_job_projection_v1(
        manifest=retained, manifest_identity_b64=manifest_identity_b64,
        phase=phase,
    )
    resources = _mapping(container.get("resources", {}), label="execution resources")
    limits = _mapping(resources.get("limits", {}), label="execution limits")
    environment = _environment(container.get("env", []), label="execution environment")
    timeout = str(task.get("timeoutSeconds", "")).removesuffix("s")
    if (
        spec.get("taskCount") != projection["task_count"]
        or spec.get("parallelism") != projection["parallelism"]
        or task.get("maxRetries") != 0
        or container.get("image") != projection["immutable_image"]
        or container.get("command", []) != projection["command"]
        or container.get("args", []) != projection["args"]
        or environment != projection["environment"]
        or task.get("serviceAccountName") != projection["service_account"]
        or not timeout.isdigit() or int(timeout) != projection["timeout_seconds"]
        or limits != {"cpu": projection["cpu"], "memory": projection["memory"]}
        or container.get("workingDir", "") != ""
        or task.get("volumes", []) != []
        or container.get("volumeMounts", []) != []
        or _has_attachment(execution)
    ):
        _fail("provider-observed execution template differs")
    state = _execution_terminal_state(execution)
    status = _mapping(execution.get("status", {}), label="execution status")
    counters: dict[str, int] = {}
    for key in ("succeededCount", "failedCount", "cancelledCount", "retriedCount"):
        value = status.get(key, 0)
        if type(value) is not int or value < 0:
            _fail("provider execution counters differ")
        counters[key] = value
    succeeded = counters["succeededCount"]
    failed = counters["failedCount"]
    cancelled = counters["cancelledCount"]
    retried = counters["retriedCount"]
    if require_terminal and (
        state != "SUCCEEDED" or succeeded != projection["task_count"]
        or failed != 0 or cancelled != 0 or retried != 0
        or type(status.get("completionTime")) is not str
        or not status["completionTime"]
    ):
        _fail("provider execution is not exact terminal success")
    return {
        "execution_name": name,
        "execution_uid": uid,
        "job_name": retained["job_name"],
        "job_uid": retained["job_uid"],
        "job_generation": expected_job_generation,
        "phase": phase,
        "task_count": projection["task_count"],
        "parallelism": projection["parallelism"],
        "maximum_task_retries": 0,
        "immutable_image": retained["immutable_image"],
        "terminal_state": state,
        "succeeded_count": succeeded,
        "failed_count": failed,
        "cancelled_count": cancelled,
        "retried_count": retried,
        "provider_observed": True,
        "provider_raw_execution_sha256": batch.canonical_sha256(execution),
    }


def validate_task_observation_v1(
    value: object, *, execution_name: str, task_index: int,
) -> dict[str, object]:
    task = _mapping(value, label=f"provider task[{task_index}]")
    metadata = _mapping(task.get("metadata"), label="task metadata")
    expected = f"{execution_name}-task{task_index}"
    name = _short_name(metadata.get("name"), label="task name", pattern=re.compile(
        rf"{re.escape(execution_name)}-task(?:0|[1-9][0-9]*)"
    ))
    labels = _mapping(metadata.get("labels", {}), label="task labels")
    status = _mapping(task.get("status", {}), label="task status")
    index = status.get("index", task_index)
    retried = status.get("retried", 0)
    state = _execution_terminal_state(task)
    attempt = _mapping(status.get("lastAttemptResult", {}), label="task result")
    exit_code = int(attempt.get("exitCode", 0 if state == "SUCCEEDED" else 255))
    if (
        name != expected
        or labels.get("run.googleapis.com/execution") != execution_name
        or index != task_index or retried != 0
        or state != "SUCCEEDED" or exit_code != 0
        or type(status.get("completionTime")) is not str
        or not status["completionTime"]
    ):
        _fail("provider task index/attempt/status differs")
    return {
        "task_index": task_index,
        "task_name": name,
        "attempt": 0,
        "exit_code": 0,
        "terminal_state": "SUCCEEDED",
        "provider_observed": True,
        "provider_raw_task_sha256": batch.canonical_sha256(task),
    }


def build_execution_binding_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    phase: str, configure_claim_identity: object,
    launch_claim_identity: object, configured_job: object, execution: object,
    manifest_identity_b64: str,
) -> dict[str, object]:
    retained = validate_controller_manifest_v1(manifest)
    job_raw = _mapping(configured_job, label="configured provider job")
    job_row = validate_phase_job_observation_v1(
        job_raw, manifest=retained,
        manifest_identity_b64=manifest_identity_b64, phase=phase,
    )
    execution_raw = _mapping(execution, label="provider execution")
    execution_row = validate_phase_execution_v1(
        execution_raw, manifest=retained,
        manifest_identity_b64=manifest_identity_b64, phase=phase,
        expected_execution=_short_name(
            execution_raw.get("metadata", {}).get("name"),
            label="execution name", pattern=_EXECUTION,
        ), expected_job_generation=str(job_row["job_generation"]),
        require_terminal=False,
    )
    body = {
        "schema_version": EXECUTION_BINDING_SCHEMA,
        "run_id": retained["run_id"],
        "manifest_identity": _identity(manifest_identity, label="controller manifest"),
        "controller_manifest_sha256": retained["controller_manifest_sha256"],
        "phase": phase,
        "configure_claim_identity": _identity(
            configure_claim_identity, label="configure claim"
        ),
        "launch_claim_identity": _identity(launch_claim_identity, label="launch claim"),
        "runtime_image_authority_identity": retained[
            "runtime_image_authority_identity"
        ],
        "provider_runtime_image_authority_sha256": retained[
            "provider_runtime_image_authority_sha256"
        ],
        "provider_job_observation": job_raw,
        "provider_raw_job_sha256": job_row["provider_raw_job_sha256"],
        "job_observation": job_row,
        "job_generation": job_row["job_generation"],
        "provider_execution_observation": execution_raw,
        "provider_raw_execution_sha256": execution_row[
            "provider_raw_execution_sha256"
        ],
        "execution": execution_row,
        "execution_name": execution_row["execution_name"],
        "execution_uid": execution_row["execution_uid"],
        "provider_observed_immutable_image": True,
        "maximum_task_retries": 0,
        "automatic_retry_licensed": False,
        **{key: value for key, value in _FALSE_AUTHORITY_FIELDS.items()
           if key != "automatic_retry_licensed"},
    }
    reject_outcome_carriers_v1(body, label="execution binding")
    return _with_hash(body, field="execution_binding_sha256")


def validate_execution_binding_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object,
    phase: str, manifest_identity_b64: str,
) -> dict[str, object]:
    """Replay a stored job/execution observation without contacting provider."""
    retained = validate_controller_manifest_v1(manifest)
    item = _mapping(value, label="execution binding")
    _validate_hash(
        item, field="execution_binding_sha256", label="execution binding"
    )
    job_raw = _mapping(
        item.get("provider_job_observation"), label="bound provider job"
    )
    job_row = validate_phase_job_observation_v1(
        job_raw, manifest=retained,
        manifest_identity_b64=manifest_identity_b64, phase=phase,
    )
    execution_raw = _mapping(
        item.get("provider_execution_observation"),
        label="bound provider execution",
    )
    execution_row = validate_phase_execution_v1(
        execution_raw, manifest=retained,
        manifest_identity_b64=manifest_identity_b64, phase=phase,
        expected_execution=str(item.get("execution_name")),
        expected_job_generation=str(job_row["job_generation"]),
        require_terminal=False,
    )
    if (
        item.get("schema_version") != EXECUTION_BINDING_SCHEMA
        or item.get("run_id") != retained["run_id"]
        or item.get("manifest_identity")
        != _identity(manifest_identity, label="controller manifest")
        or item.get("controller_manifest_sha256")
        != retained["controller_manifest_sha256"]
        or item.get("phase") != phase
        or item.get("runtime_image_authority_identity")
        != retained["runtime_image_authority_identity"]
        or item.get("provider_runtime_image_authority_sha256")
        != retained["provider_runtime_image_authority_sha256"]
        or item.get("provider_raw_job_sha256")
        != job_row["provider_raw_job_sha256"]
        or item.get("job_observation") != job_row
        or item.get("job_generation") != job_row["job_generation"]
        or item.get("provider_raw_execution_sha256")
        != execution_row["provider_raw_execution_sha256"]
        or item.get("execution") != execution_row
        or item.get("execution_name") != execution_row["execution_name"]
        or item.get("execution_uid") != execution_row["execution_uid"]
        or item.get("provider_observed_immutable_image") is not True
        or item.get("maximum_task_retries") != 0
        or any(
            item.get(key) is not expected
            for key, expected in _FALSE_AUTHORITY_FIELDS.items()
        )
    ):
        _fail("execution binding provider/manifest replay differs")
    _identity(item.get("configure_claim_identity"), label="configure claim")
    _identity(item.get("launch_claim_identity"), label="launch claim")
    reject_outcome_carriers_v1(item, label="execution binding")
    return item


def build_phase_status_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    phase: str, binding_identity: object, binding: Mapping[str, object],
    execution: object, task_observations: Sequence[object],
    manifest_identity_b64: str,
) -> dict[str, object]:
    retained = validate_controller_manifest_v1(manifest)
    retained_manifest_identity = _identity(
        manifest_identity, label="controller manifest"
    )
    binding_row = validate_execution_binding_v1(
        binding, manifest=retained, manifest_identity=retained_manifest_identity,
        phase=phase, manifest_identity_b64=manifest_identity_b64,
    )
    retained_binding_identity = _identity(
        binding_identity, label="execution binding"
    )
    binding_raw = batch.canonical_json_bytes(binding_row)
    if (
        retained_binding_identity["sha256"] != sha256(binding_raw).hexdigest()
        or retained_binding_identity["bytes"] != len(binding_raw)
        or retained_binding_identity["uri"]
        != phase_uri_v1(retained, phase, "execution-binding.json")
    ):
        _fail("execution binding content identity differs")
    execution_raw = _mapping(execution, label="terminal provider execution")
    execution_row = validate_phase_execution_v1(
        execution_raw, manifest=retained,
        manifest_identity_b64=manifest_identity_b64, phase=phase,
        expected_execution=str(binding_row["execution_name"]),
        expected_job_generation=str(binding_row["job_generation"]),
        require_terminal=True,
    )
    expected_count = PHASE_TASK_COUNTS[phase]
    tasks = _sequence(task_observations, label="provider task observations")
    if len(tasks) != expected_count:
        _fail("provider task observation count differs")
    raw_tasks = [
        _mapping(raw, label=f"provider task observation[{ordinal}]")
        for ordinal, raw in enumerate(tasks)
    ]
    validated_tasks = [
        validate_task_observation_v1(
            raw, execution_name=str(execution_row["execution_name"]),
            task_index=ordinal,
        ) for ordinal, raw in enumerate(raw_tasks)
    ]
    body = {
        "schema_version": PHASE_STATUS_SCHEMA,
        "run_id": retained["run_id"],
        "manifest_identity": retained_manifest_identity,
        "controller_manifest_sha256": retained["controller_manifest_sha256"],
        "phase": phase,
        "binding_identity": retained_binding_identity,
        "execution_binding_sha256": binding_row["execution_binding_sha256"],
        "provider_terminal_execution_observation": execution_raw,
        "provider_raw_terminal_execution_sha256": batch.canonical_sha256(
            execution_raw
        ),
        "execution": execution_row,
        "task_count": expected_count,
        "expected_task_indices": list(range(expected_count)),
        "tasks": validated_tasks,
        "tasks_sha256": batch.canonical_sha256(validated_tasks),
        "provider_task_observations": raw_tasks,
        "provider_task_observations_sha256": batch.canonical_sha256(raw_tasks),
        "strict_terminal_success": True,
        "provider_observed_immutable_image": True,
        "zero_retries_verified": True,
        **_FALSE_AUTHORITY_FIELDS,
    }
    return _with_hash(body, field="phase_status_sha256")


def validate_phase_status_v1(
    value: object, *, manifest: Mapping[str, object], manifest_identity: object,
    phase: str, binding: Mapping[str, object], binding_identity: object,
    manifest_identity_b64: str,
) -> dict[str, object]:
    """Independently replay one embedded terminal provider phase status."""
    retained = validate_controller_manifest_v1(manifest)
    item = _mapping(value, label="phase status")
    _validate_hash(item, field="phase_status_sha256", label="phase status")
    retained_manifest_identity = _identity(
        manifest_identity, label="controller manifest"
    )
    retained_binding = validate_execution_binding_v1(
        binding, manifest=retained, manifest_identity=retained_manifest_identity,
        phase=phase, manifest_identity_b64=manifest_identity_b64,
    )
    retained_binding_identity = _identity(
        binding_identity, label="execution binding"
    )
    binding_raw = batch.canonical_json_bytes(retained_binding)
    execution_raw = _mapping(
        item.get("provider_terminal_execution_observation"),
        label="terminal provider execution",
    )
    execution_row = validate_phase_execution_v1(
        execution_raw, manifest=retained,
        manifest_identity_b64=manifest_identity_b64, phase=phase,
        expected_execution=str(retained_binding["execution_name"]),
        expected_job_generation=str(retained_binding["job_generation"]),
        require_terminal=True,
    )
    raw_tasks = _sequence(
        item.get("provider_task_observations"),
        label="provider task observations",
    )
    expected_count = PHASE_TASK_COUNTS[phase]
    if len(raw_tasks) != expected_count:
        _fail("provider task observation count differs")
    validated_tasks = [
        validate_task_observation_v1(
            raw, execution_name=str(execution_row["execution_name"]),
            task_index=ordinal,
        )
        for ordinal, raw in enumerate(raw_tasks)
    ]
    if (
        item.get("schema_version") != PHASE_STATUS_SCHEMA
        or item.get("run_id") != retained["run_id"]
        or item.get("manifest_identity") != retained_manifest_identity
        or item.get("controller_manifest_sha256")
        != retained["controller_manifest_sha256"]
        or item.get("phase") != phase
        or retained_binding_identity["uri"]
        != phase_uri_v1(retained, phase, "execution-binding.json")
        or retained_binding_identity["sha256"] != sha256(binding_raw).hexdigest()
        or retained_binding_identity["bytes"] != len(binding_raw)
        or item.get("binding_identity") != retained_binding_identity
        or item.get("execution_binding_sha256")
        != retained_binding["execution_binding_sha256"]
        or item.get("provider_raw_terminal_execution_sha256")
        != batch.canonical_sha256(execution_raw)
        or item.get("execution") != execution_row
        or item.get("task_count") != expected_count
        or item.get("expected_task_indices") != list(range(expected_count))
        or item.get("tasks") != validated_tasks
        or item.get("tasks_sha256") != batch.canonical_sha256(validated_tasks)
        or item.get("provider_task_observations_sha256")
        != batch.canonical_sha256(raw_tasks)
        or item.get("strict_terminal_success") is not True
        or item.get("provider_observed_immutable_image") is not True
        or item.get("zero_retries_verified") is not True
        or any(
            item.get(key) is not expected
            for key, expected in _FALSE_AUTHORITY_FIELDS.items()
        )
    ):
        _fail("phase status independent replay differs")
    reject_outcome_carriers_v1(item, label="phase status")
    return item


def build_phase_acceptance_v1(
    *, manifest: Mapping[str, object], manifest_identity: object,
    phase_status: Mapping[str, object], predecessor_identity: object | None,
    science_gate: Mapping[str, object],
) -> dict[str, object]:
    retained = validate_controller_manifest_v1(manifest)
    status = _mapping(phase_status, label="phase status")
    _validate_hash(status, field="phase_status_sha256", label="phase status")
    phase = str(status.get("phase"))
    retained_manifest_identity = _identity(
        manifest_identity, label="controller manifest"
    )
    if (
        phase not in PHASES
        or status.get("strict_terminal_success") is not True
        or status.get("manifest_identity") != retained_manifest_identity
        or status.get("controller_manifest_sha256")
        != retained["controller_manifest_sha256"]
        or status.get("task_count") != PHASE_TASK_COUNTS.get(phase)
        or status.get("expected_task_indices")
        != list(range(PHASE_TASK_COUNTS.get(phase, 0)))
        or status.get("zero_retries_verified") is not True
        or status.get("provider_observed_immutable_image") is not True
        or any(
            status.get(key) is not expected
            for key, expected in _FALSE_AUTHORITY_FIELDS.items()
        )
    ):
        _fail("phase status cannot be accepted")
    predecessor = None if predecessor_identity is None else _identity(
        predecessor_identity, label="predecessor acceptance"
    )
    if (PHASES.index(phase) == 0) != (predecessor is None):
        _fail("phase acceptance predecessor differs")
    gate = _mapping(science_gate, label="phase science gate")
    reject_outcome_carriers_v1(gate, label="phase science gate")
    if gate.get("passed") is not True or gate.get("phase") != phase:
        _fail("phase science gate did not pass")
    return _with_hash({
        "schema_version": PHASE_ACCEPTANCE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "status": "accepted",
        "accepted": True,
        "run_id": retained["run_id"],
        "manifest_identity": retained_manifest_identity,
        "controller_manifest_sha256": retained["controller_manifest_sha256"],
        "phase": phase,
        "predecessor_acceptance_identity": predecessor,
        "phase_status": dict(status),
        "phase_status_sha256": status["phase_status_sha256"],
        "science_gate": gate,
        "science_gate_sha256": batch.canonical_sha256(gate),
        "provider_mutation_complete": True,
        "provider_observed_immutable_image": True,
        "zero_retries_verified": True,
        **_FALSE_AUTHORITY_FIELDS,
    }, field="phase_acceptance_sha256")


def validate_restored_job_v1(
    *, snapshot: Mapping[str, object], restored_job: object,
) -> dict[str, object]:
    retained = validate_job_snapshot_v1(snapshot)
    restored = stable_job_v1(restored_job)
    _, metadata, _, _ = _job_parts(
        restored_job, expected_job=str(retained["job_name"]),
        expected_uid=str(retained["job_uid"]),
    )
    if (
        restored != retained["stable_job"]
        or batch.canonical_sha256(restored) != retained["stable_job_sha256"]
    ):
        _fail("reused job restoration differs from exact snapshot")
    return {
        "job_name": retained["job_name"],
        "job_uid": metadata["uid"],
        "stable_job_sha256": retained["stable_job_sha256"],
        "exact_snapshot_restored": True,
        "provider_observed": True,
    }


__all__ = [
    "CONTROLLER_MANIFEST_SCHEMA", "DISPATCH_ARGS", "DISPATCH_PYTHON",
    "EXECUTION_BINDING_SCHEMA", "FreshClaimStore", "MANIFEST_IDENTITY_ENV",
    "ON_IMAGE_RUNTIME_AUTHORITY_RELATIVE_PATH",
    "PHASES", "PHASE_ACCEPTANCE_SCHEMA", "PHASE_ENV", "PHASE_TASK_COUNTS",
    "PUBLICATION_MODE",
    "REOPEN_SCHEMA", "RESTORATION_SCHEMA",
    "CorpusR6V2MatchupCandidateAnalysisControllerV1Error",
    "build_controller_manifest_v1", "build_execution_binding_v1",
    "build_job_snapshot_v1", "build_mutation_claim_v1",
    "build_phase_acceptance_v1", "build_phase_status_v1",
    "output_prefix_v1", "phase_job_projection_v1", "phase_spec_v1",
    "phase_uri_v1", "publish_fresh_claim_v1", "publish_json_v1",
    "reject_outcome_carriers_v1", "reopen_controller_manifest_v1",
    "stable_job_v1", "validate_controller_manifest_v1",
    "validate_execution_binding_v1",
    "validate_job_snapshot_v1", "validate_no_active_executions_v1",
    "validate_mutation_claim_v1",
    "validate_phase_execution_v1", "validate_phase_job_observation_v1",
    "validate_phase_status_v1",
    "validate_restored_job_v1", "validate_scheduler_census_v1",
    "validate_task_observation_v1",
]
