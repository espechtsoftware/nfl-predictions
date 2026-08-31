"""One-use provenance contract for the final d594 collector validation repair.

The 54 source shards remain bound to their original d594 runtime.  A later
collector runtime may only exact-reopen those shards, remove the one invalid
panel-id/panel-self-hash equality assertion, and publish the otherwise
unchanged v1 selection/terminal graph.  This module makes that source/runtime
split explicit and supplies the create-once sidecar contract used to seal the
two successful repair executions.

There is deliberately no outcome surface and no general recovery registry.
Every old authority and both known failed collect executions are pinned below.
The final repair also corrects the provider observer's use of mutable current
Job generation when reopening an immutable source Execution.  A different
failure requires a different reviewed release.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import re
from typing import Final

from . import corpus_r6_construction_allocation_cross_v1 as cross


VERSION: Final = "corpus-r6-construction-allocation-collector-repair-v2"
LEGACY_VERSION: Final = "corpus-r6-construction-allocation-collector-repair-v1"
LEGACY_REQUEST_SCHEMA: Final = f"{LEGACY_VERSION}/request"
REQUEST_SCHEMA: Final = f"{VERSION}/request"
COLLECT_RESULT_SCHEMA: Final = f"{VERSION}/collect-result"
RECEIPT_SCHEMA: Final = f"{VERSION}/receipt"
SEAL_RESULT_SCHEMA: Final = f"{VERSION}/seal-result"

PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
JOB_NAME: Final = "atlas-cbc-32g-full-2023-w8-v1"
JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
SERVICE_ACCOUNT: Final = "817589974517-compute@developer.gserviceaccount.com"

SOURCE_CODE_SHA: Final = "d5946133ebba0955586816c15905065c3ec71a0f"
SOURCE_BUILD_ID: Final = "aeb293f7-6e95-47c2-b6fe-3df7141c2fcd"
SOURCE_IMAGE_DIGEST: Final = (
    "sha256:e8959e94cf41f0a0f63bf97d4631e0c7c799af7594675a0f037ed7625a2280a7"
)
SOURCE_IMAGE: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    f"nfl-dfs@{SOURCE_IMAGE_DIGEST}"
)
SOURCE_MANIFEST_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-construction-allocation-snapshot-shards/"
        "20260830-construction-allocation-d5946133-v1/input-manifest.json"
    ),
    "generation": "1788111932751802",
    "sha256": "bbe47919f0dd753f8f7278f5f3d3e022bd70c2879c3f826dcd31e207ab1d4536",
    "bytes": 60_541,
}
SOURCE_EXECUTION_NAME: Final = "atlas-cbc-32g-full-2023-w8-v1-nsvkd"
SOURCE_EXECUTION_UID: Final = "cde282a2-2a02-464a-84f4-70b822e9aac0"
SOURCE_EXECUTION_ATTESTATION_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-construction-allocation-snapshot-shards/"
        "20260830-construction-allocation-d5946133-v1/authorities/"
        "runtime-execution-attestation-"
        "atlas-cbc-32g-full-2023-w8-v1-nsvkd.json"
    ),
    "generation": "1788142639340768",
    "sha256": "e08f26d39be40a7e2248adbe3c353bcce9a3331cbce600326f3e53de8cf9c7cc",
    "bytes": 836,
}

FAILED_COLLECT_EXECUTION: Final = {
    "name": "atlas-cbc-32g-full-2023-w8-v1-29lvz",
    "uid": "7cf1f35f-9c99-41ce-bd66-c78af15cc412",
    "job_name": JOB_NAME,
    "job_uid": JOB_UID,
    "job_generation": "42",
    "task_count": 1,
    "failed_count": 1,
    "completion_time": "2026-08-31T02:25:33.731980Z",
    "completed_condition_status": "False",
    "completed_condition_reason": "NonZeroExitCode",
    "source_code_sha": SOURCE_CODE_SHA,
    "source_image": SOURCE_IMAGE,
    "failure_class": "invalid-panel-id-to-panel-self-hash-equality",
}

FAILED_REPAIR_V1_BUILD_ATTESTATION_IDENTITY: Final = {
    "uri": (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-construction-allocation-builds/"
        "def26c98ee88b4e874f516494fd57a76f62326f0/"
        "281132a4-4e0e-4b6a-966b-91214fb27a93/"
        "runtime-build-attestation.json"
    ),
    "generation": "1788145929800066",
    "sha256": "965ea8d74ead8c896a0adadc2efd62d0108425db32f02f3b7e2a6c717b3c5ae0",
    "bytes": 855,
}
FAILED_REPAIR_V1_EXECUTION: Final = {
    "name": "atlas-cbc-32g-full-2023-w8-v1-lnxjq",
    "uid": "d32a017f-5248-4612-a965-7acc6ad2fd1e",
    "job_name": JOB_NAME,
    "job_uid": JOB_UID,
    "job_generation": "43",
    "task_count": 1,
    "failed_count": 1,
    "completion_time": "2026-08-31T03:16:48.795896Z",
    "completed_condition_status": "False",
    "completed_condition_reason": "NonZeroExitCode",
    "max_retries": 0,
    "service_account": SERVICE_ACCOUNT,
    "collector_code_sha": "def26c98ee88b4e874f516494fd57a76f62326f0",
    "collector_image": (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
        "nfl-dfs@sha256:96f4819299cb14127762db474b55fdeb2cd721cac1d4051d13ff83f47f76d4ee"
    ),
    "collector_build_id": "281132a4-4e0e-4b6a-966b-91214fb27a93",
    "collector_build_attestation_identity": dict(
        FAILED_REPAIR_V1_BUILD_ATTESTATION_IDENTITY
    ),
    "command": ["/usr/local/bin/python3.11"],
    "args": [
        "/app/scripts/run_corpus_r6_construction_allocation_collector_repair_v1.py",
        "container-collect",
        "--execute",
    ],
    "request_sha256": "f06e3c6792265f93aee31f092d083ee8e279504c9f7c259e30e1e54f456d727c",
    "request_transport_sha256": (
        "8e75be599d804542fb000613692e3c46bdcad6a4c90d56d1dac223a35d29fc74"
    ),
    "failure_class": "mutable-current-job-generation-used-for-execution-reopen",
}

RUN_PREFIX: Final = SOURCE_MANIFEST_IDENTITY["uri"].removesuffix(
    "/input-manifest.json"
)
SELECTION_URI: Final = f"{RUN_PREFIX}/selection.json"
TERMINAL_URI: Final = f"{RUN_PREFIX}/terminal.json"
LEGACY_REPAIR_RECEIPT_URI: Final = (
    f"{RUN_PREFIX}/collector-repair-receipt-v1.json"
)
REPAIR_RECEIPT_URI: Final = f"{RUN_PREFIX}/collector-repair-receipt-v2.json"

ENABLE_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_COLLECTOR_REPAIR_ENABLE"
ENABLE_VALUE: Final = "I_UNDERSTAND_D594_COLLECTOR_REPAIR_V2"
REQUEST_B64_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_COLLECTOR_REPAIR_REQUEST_B64"
REQUEST_SHA_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_COLLECTOR_REPAIR_REQUEST_SHA256"
COLLECTOR_CODE_SHA_ENV: Final = "R6_COLLECTOR_REPAIR_CODE_SHA"
COLLECTOR_IMAGE_ENV: Final = "R6_COLLECTOR_REPAIR_IMAGE"
COLLECTOR_BUILD_ID_ENV: Final = "R6_COLLECTOR_REPAIR_BUILD_ID"
COLLECTOR_BUILD_ATTESTATION_ENV: Final = (
    "R6_COLLECTOR_REPAIR_BUILD_ATTESTATION_IDENTITY"
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE = re.compile(r".+@sha256:[0-9a-f]{64}\Z")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)


class CollectorRepairV1Error(ValueError):
    """The one admitted collector-repair authority differs."""


def _fail(message: str) -> None:
    raise CollectorRepairV1Error(message)


def canonical_bytes(value: object, *, newline: bool = False) -> bytes:
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CollectorRepairV1Error("canonical JSON differs") from exc
    return raw + (b"\n" if newline else b"")


def digest(value: object) -> str:
    return sha256(canonical_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} differs")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    uri = item.get("uri")
    generation = item.get("generation")
    checksum = item.get("sha256")
    size = item.get("bytes")
    if (
        type(uri) is not str
        or not uri.startswith("gs://")
        or type(generation) not in {str, int}
        or not str(generation)
        or type(checksum) is not str
        or _SHA.fullmatch(checksum) is None
        or type(size) is not int
        or size <= 0
    ):
        _fail(f"{label} differs")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": checksum,
        "bytes": size,
    }


def _self_hash(value: object, *, field: str, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    body = dict(item)
    retained = body.pop(field, None)
    if (
        type(retained) is not str
        or _SHA.fullmatch(retained) is None
        or digest(body) != retained
    ):
        _fail(f"{label} self-hash differs")
    return item


def validate_failed_repair_v1_request(value: object) -> dict[str, object]:
    """Validate the exact request carried by the admitted lnxjq failure."""

    item = _self_hash(
        value, field="request_sha256", label="failed repair-v1 request"
    )
    expected_body: dict[str, object] = {
        "schema_version": LEGACY_REQUEST_SCHEMA,
        "version": LEGACY_VERSION,
        "phase": "collect",
        "source_manifest_identity": dict(SOURCE_MANIFEST_IDENTITY),
        "source_code_sha": SOURCE_CODE_SHA,
        "source_image": SOURCE_IMAGE,
        "source_build_id": SOURCE_BUILD_ID,
        "source_execution_name": SOURCE_EXECUTION_NAME,
        "source_execution_uid": SOURCE_EXECUTION_UID,
        "source_runtime_execution_attestation_identity": dict(
            SOURCE_EXECUTION_ATTESTATION_IDENTITY
        ),
        "failed_collect_execution": dict(FAILED_COLLECT_EXECUTION),
        "collector_runtime_build_attestation_identity": dict(
            FAILED_REPAIR_V1_BUILD_ATTESTATION_IDENTITY
        ),
        "prior_repair_execution": None,
        "selection_uri": SELECTION_URI,
        "terminal_uri": TERMINAL_URI,
        "repair_receipt_uri": LEGACY_REPAIR_RECEIPT_URI,
        "source_and_collector_runtime_are_distinct": True,
        "existing_54_shards_are_only_selection_authority": True,
        "shard_recomputation_licensed": False,
        "target_slate_outcomes_allowed": False,
        "automatic_relaunch_licensed": False,
    }
    expected = {**expected_body, "request_sha256": digest(expected_body)}
    if (
        item != expected
        or item["request_sha256"]
        != FAILED_REPAIR_V1_EXECUTION["request_sha256"]
    ):
        _fail("failed repair-v1 request differs")
    return item


def request_v1(
    *, phase: str, collector_runtime_build_attestation_identity: object,
    prior_repair_execution: object | None = None,
) -> dict[str, object]:
    if phase not in {"collect", "reopen"}:
        _fail("repair phase differs")
    build_identity = _identity(
        collector_runtime_build_attestation_identity,
        label="collector runtime build attestation",
    )
    if phase == "collect":
        if prior_repair_execution is not None:
            _fail("initial repair collect cannot name a prior repair execution")
        prior: dict[str, object] | None = None
    else:
        prior = _mapping(
            prior_repair_execution, label="prior repair collect execution"
        )
        if (
            set(prior) != {"phase", "execution_name", "execution_uid"}
            or prior.get("phase") != "collect"
            or type(prior.get("execution_name")) is not str
            or not str(prior["execution_name"]).startswith(JOB_NAME + "-")
            or type(prior.get("execution_uid")) is not str
            or not prior["execution_uid"]
        ):
            _fail("repair reopen predecessor is not collect")
    body: dict[str, object] = {
        "schema_version": REQUEST_SCHEMA,
        "version": VERSION,
        "phase": phase,
        "source_manifest_identity": dict(SOURCE_MANIFEST_IDENTITY),
        "source_code_sha": SOURCE_CODE_SHA,
        "source_image": SOURCE_IMAGE,
        "source_build_id": SOURCE_BUILD_ID,
        "source_execution_name": SOURCE_EXECUTION_NAME,
        "source_execution_uid": SOURCE_EXECUTION_UID,
        "source_runtime_execution_attestation_identity": dict(
            SOURCE_EXECUTION_ATTESTATION_IDENTITY
        ),
        "failed_collect_execution": dict(FAILED_COLLECT_EXECUTION),
        "failed_repair_v1_execution": dict(FAILED_REPAIR_V1_EXECUTION),
        "collector_runtime_build_attestation_identity": build_identity,
        "prior_repair_execution": prior,
        "selection_uri": SELECTION_URI,
        "terminal_uri": TERMINAL_URI,
        "repair_receipt_uri": REPAIR_RECEIPT_URI,
        "source_and_collector_runtime_are_distinct": True,
        "immutable_execution_label_is_generation_authority": True,
        "current_job_generation_is_not_execution_authority": True,
        "existing_54_shards_are_only_selection_authority": True,
        "shard_recomputation_licensed": False,
        "target_slate_outcomes_allowed": False,
        "automatic_relaunch_licensed": False,
    }
    return {**body, "request_sha256": digest(body)}


def validate_request_v1(value: object) -> dict[str, object]:
    item = _self_hash(value, field="request_sha256", label="repair request")
    expected_keys = {
        "schema_version", "version", "phase", "source_manifest_identity",
        "source_code_sha", "source_image", "source_build_id",
        "source_execution_name", "source_execution_uid",
        "source_runtime_execution_attestation_identity",
        "failed_collect_execution", "failed_repair_v1_execution",
        "collector_runtime_build_attestation_identity",
        "prior_repair_execution", "selection_uri", "terminal_uri",
        "repair_receipt_uri", "source_and_collector_runtime_are_distinct",
        "immutable_execution_label_is_generation_authority",
        "current_job_generation_is_not_execution_authority",
        "existing_54_shards_are_only_selection_authority",
        "shard_recomputation_licensed", "target_slate_outcomes_allowed",
        "automatic_relaunch_licensed", "request_sha256",
    }
    phase = item.get("phase")
    prior = item.get("prior_repair_execution")
    if (
        set(item) != expected_keys
        or item.get("schema_version") != REQUEST_SCHEMA
        or item.get("version") != VERSION
        or phase not in {"collect", "reopen"}
        or _identity(item.get("source_manifest_identity"), label="source manifest")
        != SOURCE_MANIFEST_IDENTITY
        or item.get("source_code_sha") != SOURCE_CODE_SHA
        or item.get("source_image") != SOURCE_IMAGE
        or item.get("source_build_id") != SOURCE_BUILD_ID
        or item.get("source_execution_name") != SOURCE_EXECUTION_NAME
        or item.get("source_execution_uid") != SOURCE_EXECUTION_UID
        or _identity(
            item.get("source_runtime_execution_attestation_identity"),
            label="source execution attestation",
        )
        != SOURCE_EXECUTION_ATTESTATION_IDENTITY
        or item.get("failed_collect_execution") != FAILED_COLLECT_EXECUTION
        or item.get("failed_repair_v1_execution") != FAILED_REPAIR_V1_EXECUTION
        or item.get("selection_uri") != SELECTION_URI
        or item.get("terminal_uri") != TERMINAL_URI
        or item.get("repair_receipt_uri") != REPAIR_RECEIPT_URI
        or item.get("source_and_collector_runtime_are_distinct") is not True
        or item.get("immutable_execution_label_is_generation_authority") is not True
        or item.get("current_job_generation_is_not_execution_authority") is not True
        or item.get("existing_54_shards_are_only_selection_authority") is not True
        or item.get("shard_recomputation_licensed") is not False
        or item.get("target_slate_outcomes_allowed") is not False
        or item.get("automatic_relaunch_licensed") is not False
    ):
        _fail("repair request authority differs")
    _identity(
        item.get("collector_runtime_build_attestation_identity"),
        label="collector runtime build attestation",
    )
    if phase == "collect" and prior is not None:
        _fail("initial repair collect predecessor differs")
    if phase == "reopen":
        retained_prior = _mapping(
            prior, label="prior repair collect execution"
        )
        if (
            set(retained_prior) != {"phase", "execution_name", "execution_uid"}
            or retained_prior.get("phase") != "collect"
            or type(retained_prior.get("execution_name")) is not str
            or not str(retained_prior["execution_name"]).startswith(JOB_NAME + "-")
            or type(retained_prior.get("execution_uid")) is not str
            or not retained_prior["execution_uid"]
        ):
            _fail("repair reopen predecessor differs")
    return item


def repair_execution_v1(
    *, phase: str, code_sha: str, image: str, build_id: str,
    job_generation: str, execution_name: str, execution_uid: str,
    completion_time: str,
) -> dict[str, object]:
    if (
        phase not in {"collect", "reopen"}
        or _COMMIT.fullmatch(code_sha) is None
        or code_sha in {
            SOURCE_CODE_SHA,
            FAILED_REPAIR_V1_EXECUTION["collector_code_sha"],
        }
        or _IMAGE.fullmatch(image) is None
        or image in {
            SOURCE_IMAGE,
            FAILED_REPAIR_V1_EXECUTION["collector_image"],
        }
        or _UUID.fullmatch(build_id) is None
        or build_id == FAILED_REPAIR_V1_EXECUTION["collector_build_id"]
        or not str(job_generation)
        or not execution_name.startswith(JOB_NAME + "-")
        or not execution_uid
        or type(completion_time) is not str
        or not completion_time.endswith("Z")
    ):
        _fail("repair execution facts differ")
    body = {
        "phase": phase,
        "project_id": PROJECT,
        "region": REGION,
        "job_name": JOB_NAME,
        "job_uid": JOB_UID,
        "job_generation": str(job_generation),
        "execution_name": execution_name,
        "execution_uid": execution_uid,
        "task_count": 1,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "running_count": 0,
        "completion_time": completion_time,
        "code_sha": code_sha,
        "image": image,
        "image_digest": image.rsplit("@", 1)[-1],
        "build_id": build_id,
        "service_account": SERVICE_ACCOUNT,
        "max_retries": 0,
        "cpu": "8",
        "memory": "32Gi",
        "target_slate_outcomes_allowed": False,
        "provider_observed": True,
    }
    return body


def validate_repair_execution_v1(
    value: object, *, label: str = "repair execution",
) -> dict[str, object]:
    item = _mapping(value, label=label)
    expected = repair_execution_v1(
        phase=str(item.get("phase", "")),
        code_sha=str(item.get("code_sha", "")),
        image=str(item.get("image", "")),
        build_id=str(item.get("build_id", "")),
        job_generation=str(item.get("job_generation", "")),
        execution_name=str(item.get("execution_name", "")),
        execution_uid=str(item.get("execution_uid", "")),
        completion_time=str(item.get("completion_time", "")),
    )
    if item != expected:
        _fail(f"{label} differs")
    return item


def collect_result_v1(
    *, request: object, collector_code_sha: str, collector_image: str,
    collector_build_id: str, source_collect_result: object,
) -> dict[str, object]:
    retained_request = validate_request_v1(request)
    source = _mapping(source_collect_result, label="source collect result")
    terminal = _mapping(source.get("terminal_envelope"), label="terminal envelope")
    if (
        _COMMIT.fullmatch(collector_code_sha) is None
        or collector_code_sha in {
            SOURCE_CODE_SHA,
            FAILED_REPAIR_V1_EXECUTION["collector_code_sha"],
        }
        or _IMAGE.fullmatch(collector_image) is None
        or collector_image in {
            SOURCE_IMAGE,
            FAILED_REPAIR_V1_EXECUTION["collector_image"],
        }
        or _UUID.fullmatch(collector_build_id) is None
        or collector_build_id == FAILED_REPAIR_V1_EXECUTION["collector_build_id"]
        or source.get("schema_version")
        != "corpus-r6-construction-allocation-snapshot-shard-collect/v1"
        or source.get("manifest_identity") != SOURCE_MANIFEST_IDENTITY
        or source.get("shard_count") != 54
        or source.get("all_shards_generation_exact_reopened") is not True
        or source.get("input_manifest_and_ordered_shards_generation_exact_reopened")
        is not True
        or source.get("runtime_execution_provider_attestation_exact_reopened")
        is not True
        or source.get("outcome_data_accessed") is not False
        or source.get("grading_performed") is not False
        or source.get("complete") is not True
        or terminal.get("terminal_identity", {}).get("uri") != TERMINAL_URI
    ):
        _fail("repaired source collect result differs")
    body: dict[str, object] = {
        "schema_version": COLLECT_RESULT_SCHEMA,
        "version": VERSION,
        "phase": retained_request["phase"],
        "request_sha256": retained_request["request_sha256"],
        "request_transport_sha256": sha256(
            canonical_bytes(retained_request, newline=True)
        ).hexdigest(),
        "collector_code_sha": collector_code_sha,
        "collector_image": collector_image,
        "collector_build_id": collector_build_id,
        "collector_runtime_build_attestation_identity": retained_request[
            "collector_runtime_build_attestation_identity"
        ],
        "source_code_sha": SOURCE_CODE_SHA,
        "source_image": SOURCE_IMAGE,
        "source_execution_name": SOURCE_EXECUTION_NAME,
        "source_execution_uid": SOURCE_EXECUTION_UID,
        "source_runtime_execution_attestation_identity": dict(
            SOURCE_EXECUTION_ATTESTATION_IDENTITY
        ),
        "source_collect_result": source,
        "terminal_envelope": terminal,
        "source_and_collector_runtime_are_distinct": True,
        "existing_54_shards_reused": True,
        "shard_recomputation_performed": False,
        "target_slate_outcomes_read": False,
        "complete": True,
    }
    return {**body, "repair_collect_sha256": digest(body)}


def validate_collect_result_v1(value: object) -> dict[str, object]:
    item = _self_hash(
        value, field="repair_collect_sha256", label="repair collect result"
    )
    expected_keys = {
        "schema_version", "version", "phase", "request_sha256",
        "request_transport_sha256",
        "collector_code_sha", "collector_image", "collector_build_id",
        "collector_runtime_build_attestation_identity", "source_code_sha",
        "source_image", "source_execution_name", "source_execution_uid",
        "source_runtime_execution_attestation_identity", "source_collect_result",
        "terminal_envelope", "source_and_collector_runtime_are_distinct",
        "existing_54_shards_reused", "shard_recomputation_performed",
        "target_slate_outcomes_read", "complete", "repair_collect_sha256",
    }
    if (
        set(item) != expected_keys
        or item.get("schema_version") != COLLECT_RESULT_SCHEMA
        or item.get("version") != VERSION
        or item.get("phase") not in {"collect", "reopen"}
        or type(item.get("request_transport_sha256")) is not str
        or _SHA.fullmatch(str(item.get("request_transport_sha256", ""))) is None
        or _COMMIT.fullmatch(str(item.get("collector_code_sha", ""))) is None
        or item.get("collector_code_sha") in {
            SOURCE_CODE_SHA,
            FAILED_REPAIR_V1_EXECUTION["collector_code_sha"],
        }
        or _IMAGE.fullmatch(str(item.get("collector_image", ""))) is None
        or item.get("collector_image") in {
            SOURCE_IMAGE,
            FAILED_REPAIR_V1_EXECUTION["collector_image"],
        }
        or _UUID.fullmatch(str(item.get("collector_build_id", ""))) is None
        or item.get("collector_build_id")
        == FAILED_REPAIR_V1_EXECUTION["collector_build_id"]
        or item.get("source_code_sha") != SOURCE_CODE_SHA
        or item.get("source_image") != SOURCE_IMAGE
        or item.get("source_execution_name") != SOURCE_EXECUTION_NAME
        or item.get("source_execution_uid") != SOURCE_EXECUTION_UID
        or _identity(
            item.get("source_runtime_execution_attestation_identity"),
            label="source execution attestation",
        )
        != SOURCE_EXECUTION_ATTESTATION_IDENTITY
        or item.get("source_and_collector_runtime_are_distinct") is not True
        or item.get("existing_54_shards_reused") is not True
        or item.get("shard_recomputation_performed") is not False
        or item.get("target_slate_outcomes_read") is not False
        or item.get("complete") is not True
    ):
        _fail("repair collect result differs")
    source = _mapping(item.get("source_collect_result"), label="source collect result")
    terminal = _mapping(item.get("terminal_envelope"), label="terminal envelope")
    if (
        source.get("schema_version")
        != "corpus-r6-construction-allocation-snapshot-shard-collect/v1"
        or source.get("manifest_identity") != SOURCE_MANIFEST_IDENTITY
        or source.get("shard_count") != 54
        or source.get("terminal_envelope") != terminal
        or source.get("all_shards_generation_exact_reopened") is not True
        or source.get("outcome_data_accessed") is not False
        or source.get("complete") is not True
    ):
        _fail("repair collect legacy result differs")
    return item


def receipt_v1(
    *, collect_result: object, reopen_result: object,
    collect_execution: object, reopen_execution: object,
    selection_reopen_receipt: object,
) -> dict[str, object]:
    collected = validate_collect_result_v1(collect_result)
    reopened = validate_collect_result_v1(reopen_result)
    collect_runtime = validate_repair_execution_v1(
        collect_execution, label="repair collect execution"
    )
    reopen_runtime = validate_repair_execution_v1(
        reopen_execution, label="repair reopen execution"
    )
    closure = _mapping(selection_reopen_receipt, label="selection reopen receipt")
    source = _mapping(collected["source_collect_result"], label="source collect")
    envelope = _mapping(collected["terminal_envelope"], label="terminal envelope")
    upstream = _mapping(
        closure.get("upstream_reopen_receipt"), label="upstream reopen receipt"
    )
    panel_reopen = _mapping(
        upstream.get("fixed_g0_panel_reopen"), label="fixed panel reopen"
    )
    execution_authority = _mapping(
        closure.get("execution_authority"), label="selection execution authority"
    )
    source_execution = _mapping(
        envelope.get("runtime_execution_attestation_identity"),
        label="terminal source execution attestation",
    )
    if (
        collected["phase"] != "collect"
        or reopened["phase"] != "reopen"
        or reopened["terminal_envelope"] != envelope
        or collect_runtime["phase"] != "collect"
        or reopen_runtime["phase"] != "reopen"
        or collect_runtime["code_sha"] != collected["collector_code_sha"]
        or reopen_runtime["code_sha"] != collected["collector_code_sha"]
        or collect_runtime["image"] != collected["collector_image"]
        or reopen_runtime["image"] != collected["collector_image"]
        or collect_runtime["build_id"] != collected["collector_build_id"]
        or reopen_runtime["build_id"] != collected["collector_build_id"]
        or reopened["collector_runtime_build_attestation_identity"]
        != collected["collector_runtime_build_attestation_identity"]
        or source_execution != SOURCE_EXECUTION_ATTESTATION_IDENTITY
        or closure.get("complete") is not True
        or closure.get("outcome_data_accessed") is not False
        or closure.get("post_lock_data_read") is not False
        or _mapping(closure.get("terminal_envelope"), label="reopened envelope")
        != envelope
        or panel_reopen.get("panel_id") != cross.FOUNDRY_G0_PANEL_ID
        or panel_reopen.get("panel_index_sha256")
        != "479b65bb40fcab6ba6721431718c8e2e95fc0a28a4354f1e7b3b1e205c69b094"
        or panel_reopen.get("accepted_slate_count") != 54
        or execution_authority.get("task_count") != 54
        or execution_authority.get("ordered_shard_identities_sha256")
        != source.get("shard_identities_sha256")
        or execution_authority.get("runtime_execution_attestation_identity")
        != SOURCE_EXECUTION_ATTESTATION_IDENTITY
    ):
        _fail("collector repair seal predecessor differs")
    terminal_identity = _identity(
        envelope.get("terminal_identity"), label="terminal identity"
    )
    selection_identity = _identity(
        envelope.get("selection_identity"), label="selection identity"
    )
    if (
        terminal_identity["uri"] != TERMINAL_URI
        or selection_identity["uri"] != SELECTION_URI
    ):
        _fail("collector repair terminal names differ")
    body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "version": VERSION,
        "source_manifest_identity": dict(SOURCE_MANIFEST_IDENTITY),
        "source_code_sha": SOURCE_CODE_SHA,
        "source_image": SOURCE_IMAGE,
        "source_build_id": SOURCE_BUILD_ID,
        "source_execution_name": SOURCE_EXECUTION_NAME,
        "source_execution_uid": SOURCE_EXECUTION_UID,
        "source_runtime_execution_attestation_identity": dict(
            SOURCE_EXECUTION_ATTESTATION_IDENTITY
        ),
        "source_ordered_shard_identities_sha256": source[
            "shard_identities_sha256"
        ],
        "source_selection_receipt_sha256": source["selection_receipt_sha256"],
        "failed_collect_execution": dict(FAILED_COLLECT_EXECUTION),
        "failed_repair_v1_execution": dict(FAILED_REPAIR_V1_EXECUTION),
        "corrected_invalid_predicates": [
            "panel_index_sha256-equals-panel_id-suffix",
            "current-job-generation-equals-frozen-execution-generation",
        ],
        "execution_generation_authority": (
            "immutable-run.googleapis.com/jobGeneration-execution-label"
        ),
        "job_identity_authority": (
            "current-job-name-and-uid-must-match-immutable-execution-labels"
        ),
        "fixed_panel_id": cross.FOUNDRY_G0_PANEL_ID,
        "fixed_panel_index_sha256": (
            "479b65bb40fcab6ba6721431718c8e2e95fc0a28a4354f1e7b3b1e205c69b094"
        ),
        "collector_code_sha": collected["collector_code_sha"],
        "collector_image": collected["collector_image"],
        "collector_build_id": collected["collector_build_id"],
        "collector_runtime_build_attestation_identity": collected[
            "collector_runtime_build_attestation_identity"
        ],
        "repair_collect_execution": collect_runtime,
        "repair_reopen_execution": reopen_runtime,
        "selection_identity": selection_identity,
        "terminal_identity": terminal_identity,
        "terminal_envelope_sha256": envelope["envelope_sha256"],
        "selection_terminal_v1_unchanged": True,
        "source_and_collector_runtime_are_distinct": True,
        "all_54_source_shards_generation_exact_reopened": True,
        "selection_replayed_from_declared_source_shards": True,
        "shard_recomputation_performed": False,
        "selection_replayed_from_existing_shards": True,
        "target_slate_outcomes_read": False,
        "repair_scope": "validation-only-no-scientific-change",
        "automatic_policy_promotion": False,
        "complete": True,
    }
    return {**body, "collector_repair_sha256": digest(body)}


def validate_receipt_v1(value: object) -> dict[str, object]:
    item = _self_hash(
        value, field="collector_repair_sha256", label="collector repair receipt"
    )
    expected_keys = {
        "schema_version", "version", "source_manifest_identity",
        "source_code_sha", "source_image", "source_build_id",
        "source_execution_name", "source_execution_uid",
        "source_runtime_execution_attestation_identity",
        "source_ordered_shard_identities_sha256",
        "source_selection_receipt_sha256", "failed_collect_execution",
        "failed_repair_v1_execution", "corrected_invalid_predicates",
        "execution_generation_authority", "job_identity_authority",
        "fixed_panel_id", "fixed_panel_index_sha256", "collector_code_sha",
        "collector_image", "collector_build_id",
        "collector_runtime_build_attestation_identity",
        "repair_collect_execution", "repair_reopen_execution",
        "selection_identity", "terminal_identity", "terminal_envelope_sha256",
        "selection_terminal_v1_unchanged",
        "source_and_collector_runtime_are_distinct",
        "all_54_source_shards_generation_exact_reopened",
        "selection_replayed_from_declared_source_shards",
        "shard_recomputation_performed", "selection_replayed_from_existing_shards",
        "target_slate_outcomes_read", "repair_scope", "automatic_policy_promotion",
        "complete", "collector_repair_sha256",
    }
    if (
        set(item) != expected_keys
        or item.get("schema_version") != RECEIPT_SCHEMA
        or item.get("version") != VERSION
        or item.get("source_manifest_identity") != SOURCE_MANIFEST_IDENTITY
        or item.get("source_code_sha") != SOURCE_CODE_SHA
        or item.get("source_image") != SOURCE_IMAGE
        or item.get("source_build_id") != SOURCE_BUILD_ID
        or item.get("source_execution_name") != SOURCE_EXECUTION_NAME
        or item.get("source_execution_uid") != SOURCE_EXECUTION_UID
        or item.get("source_runtime_execution_attestation_identity")
        != SOURCE_EXECUTION_ATTESTATION_IDENTITY
        or item.get("failed_collect_execution") != FAILED_COLLECT_EXECUTION
        or item.get("failed_repair_v1_execution") != FAILED_REPAIR_V1_EXECUTION
        or item.get("corrected_invalid_predicates") != [
            "panel_index_sha256-equals-panel_id-suffix",
            "current-job-generation-equals-frozen-execution-generation",
        ]
        or item.get("execution_generation_authority")
        != "immutable-run.googleapis.com/jobGeneration-execution-label"
        or item.get("job_identity_authority")
        != "current-job-name-and-uid-must-match-immutable-execution-labels"
        or item.get("fixed_panel_id") != cross.FOUNDRY_G0_PANEL_ID
        or item.get("fixed_panel_index_sha256")
        != "479b65bb40fcab6ba6721431718c8e2e95fc0a28a4354f1e7b3b1e205c69b094"
        or item.get("selection_terminal_v1_unchanged") is not True
        or item.get("source_and_collector_runtime_are_distinct") is not True
        or item.get("all_54_source_shards_generation_exact_reopened") is not True
        or item.get("selection_replayed_from_declared_source_shards") is not True
        or item.get("shard_recomputation_performed") is not False
        or item.get("selection_replayed_from_existing_shards") is not True
        or item.get("target_slate_outcomes_read") is not False
        or item.get("repair_scope") != "validation-only-no-scientific-change"
        or item.get("automatic_policy_promotion") is not False
        or item.get("complete") is not True
    ):
        _fail("collector repair receipt differs")
    _identity(item.get("collector_runtime_build_attestation_identity"), label="build")
    validate_repair_execution_v1(item.get("repair_collect_execution"))
    validate_repair_execution_v1(item.get("repair_reopen_execution"))
    selection = _identity(item.get("selection_identity"), label="selection")
    terminal = _identity(item.get("terminal_identity"), label="terminal")
    if selection["uri"] != SELECTION_URI or terminal["uri"] != TERMINAL_URI:
        _fail("collector repair output identities differ")
    return item


__all__ = [
    "COLLECT_RESULT_SCHEMA",
    "COLLECTOR_BUILD_ATTESTATION_ENV",
    "COLLECTOR_BUILD_ID_ENV",
    "COLLECTOR_CODE_SHA_ENV",
    "COLLECTOR_IMAGE_ENV",
    "CollectorRepairV1Error",
    "ENABLE_ENV",
    "ENABLE_VALUE",
    "FAILED_COLLECT_EXECUTION",
    "FAILED_REPAIR_V1_BUILD_ATTESTATION_IDENTITY",
    "FAILED_REPAIR_V1_EXECUTION",
    "JOB_NAME",
    "JOB_UID",
    "PROJECT",
    "RECEIPT_SCHEMA",
    "REGION",
    "LEGACY_REPAIR_RECEIPT_URI",
    "REPAIR_RECEIPT_URI",
    "REQUEST_B64_ENV",
    "REQUEST_SCHEMA",
    "REQUEST_SHA_ENV",
    "SEAL_RESULT_SCHEMA",
    "SELECTION_URI",
    "SERVICE_ACCOUNT",
    "SOURCE_BUILD_ID",
    "SOURCE_CODE_SHA",
    "SOURCE_EXECUTION_ATTESTATION_IDENTITY",
    "SOURCE_EXECUTION_NAME",
    "SOURCE_EXECUTION_UID",
    "SOURCE_IMAGE",
    "SOURCE_IMAGE_DIGEST",
    "SOURCE_MANIFEST_IDENTITY",
    "TERMINAL_URI",
    "VERSION",
    "canonical_bytes",
    "collect_result_v1",
    "digest",
    "receipt_v1",
    "repair_execution_v1",
    "request_v1",
    "validate_collect_result_v1",
    "validate_failed_repair_v1_request",
    "validate_receipt_v1",
    "validate_repair_execution_v1",
    "validate_request_v1",
]
