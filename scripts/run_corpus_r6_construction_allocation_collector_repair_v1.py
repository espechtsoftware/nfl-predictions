#!/usr/bin/env python3
"""Execute and seal the one-use d594 construction collector repair.

``container-collect`` is the only Cloud Run mutation phase.  It uses the new
collector runtime to exact-read the old d594 manifest and 54 already-published
shards, then delegates to the unchanged v1 collector publication.  ``seal``
runs after both collect and independent reopen executions have succeeded; it
provider-reopens those executions and publishes one create-once repair
sidecar.  Neither mode exposes outcomes or a shard builder.
"""

from __future__ import annotations

from collections.abc import Mapping
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from nfl_dfs.research import (  # noqa: E402
    corpus_r6_construction_allocation_collector_repair_v1 as repair,
)
from nfl_dfs.research import (  # noqa: E402
    corpus_r6_construction_allocation_cross_operator_v1 as selection_operator,
)
import run_corpus_r6_construction_allocation_snapshot_shard_v1 as source_runner  # noqa: E402


MAX_REQUEST_BYTES: Final = 256_000
MAX_LOG_ROWS: Final = 100
SOURCE_ENABLE_ENV: Final = source_runner.ENABLE_ENV
SOURCE_ENABLE_VALUE: Final = source_runner.ENABLE_VALUE
SOURCE_MANIFEST_ENV: Final = source_runner.MANIFEST_IDENTITY_ENV
SOURCE_CODE_ENV: Final = source_runner.CODE_SHA_ENV
SOURCE_IMAGE_DIGEST_ENV: Final = source_runner.IMAGE_DIGEST_ENV
SOURCE_FULL_IMAGE_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_FULL_IMAGE"
OUTCOMES_ALLOWED_ENV: Final = (
    "R6_CONSTRUCTION_ALLOCATION_TARGET_OUTCOMES_ALLOWED"
)
REPAIR_PHASE_ENV: Final = "R6_CONSTRUCTION_ALLOCATION_COLLECTOR_REPAIR_PHASE"


class CollectorRepairRunnerV1Error(RuntimeError):
    """The recovery execution or provider closure differs."""


def _fail(message: str) -> None:
    raise CollectorRepairRunnerV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} differs")
    return dict(value)


def _parse(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CollectorRepairRunnerV1Error(f"{label} JSON differs") from exc
    item = _mapping(value, label=label)
    if raw not in {
        repair.canonical_bytes(item),
        repair.canonical_bytes(item, newline=True),
    }:
        _fail(f"{label} is not canonical JSON")
    return item


def _request_from_environment() -> dict[str, object]:
    encoded = os.environ.get(repair.REQUEST_B64_ENV, "")
    retained_sha = os.environ.get(repair.REQUEST_SHA_ENV, "")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise CollectorRepairRunnerV1Error("repair request base64 differs") from exc
    if (
        not raw
        or len(raw) > MAX_REQUEST_BYTES
        or sha256(raw).hexdigest() != retained_sha
    ):
        _fail("repair request transport differs")
    return repair.validate_request_v1(_parse(raw, label="repair request"))


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    normalized = {
        "uri": item.get("uri"),
        "generation": str(item.get("generation", "")),
        "sha256": item.get("sha256"),
        "bytes": item.get("bytes"),
    }
    if (
        type(normalized["uri"]) is not str
        or not str(normalized["uri"]).startswith("gs://")
        or not normalized["generation"]
        or type(normalized["sha256"]) is not str
        or len(str(normalized["sha256"])) != 64
        or type(normalized["bytes"]) is not int
        or int(normalized["bytes"]) <= 0
    ):
        _fail(f"{label} differs")
    if item.get("create_once") is True:
        normalized["create_once"] = True
    return normalized


def _validate_collector_runtime(
    request: Mapping[str, object], *, store: source_runner.GCSExactKnownNameStoreV1,
    provider: source_runner.GCloudBuildProviderV1,
) -> tuple[str, str, str]:
    if (
        os.environ.get(repair.ENABLE_ENV) != repair.ENABLE_VALUE
        or os.environ.get(OUTCOMES_ALLOWED_ENV) != "false"
        or os.environ.get(SOURCE_ENABLE_ENV) != SOURCE_ENABLE_VALUE
    ):
        _fail("collector repair is not explicitly outcome-blind armed")
    phase = str(request["phase"])
    if os.environ.get(REPAIR_PHASE_ENV) != phase:
        _fail("collector repair phase environment differs")
    code_sha = os.environ.get(repair.COLLECTOR_CODE_SHA_ENV, "")
    image = os.environ.get(repair.COLLECTOR_IMAGE_ENV, "")
    build_id = os.environ.get(repair.COLLECTOR_BUILD_ID_ENV, "")
    source_commit = os.environ.get("IMAGE_SOURCE_COMMIT_SHA", "")
    raw_build_identity = os.environ.get(
        repair.COLLECTOR_BUILD_ATTESTATION_ENV, ""
    )
    try:
        environment_build_identity = _identity(
            json.loads(raw_build_identity),
            label="collector build-attestation environment",
        )
    except json.JSONDecodeError as exc:
        raise CollectorRepairRunnerV1Error(
            "collector build-attestation environment differs"
        ) from exc
    if (
        code_sha != source_commit
        or code_sha == repair.SOURCE_CODE_SHA
        or image == repair.SOURCE_IMAGE
        or not image.endswith("@" + os.environ.get(SOURCE_IMAGE_DIGEST_ENV, ""))
        or os.environ.get(SOURCE_CODE_ENV) != code_sha
        or os.environ.get("BUILD_ID") != build_id
        or os.environ.get(SOURCE_FULL_IMAGE_ENV) != image
    ):
        _fail("collector repair runtime differs from its immutable image")
    identity = _identity(
        request["collector_runtime_build_attestation_identity"],
        label="collector build attestation",
    )
    if (
        environment_build_identity != identity
        or raw_build_identity.encode("ascii")
        != repair.canonical_bytes(identity)
    ):
        _fail("collector build-attestation runtime binding differs")
    raw = store.read_exact(identity)
    if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
        _fail("collector build attestation exact bytes differ")
    attestation = selection_operator.validate_runtime_build_attestation_v1(
        _parse(raw, label="collector build attestation"),
        expected_code_sha=code_sha,
        expected_image_digest=image.rsplit("@", 1)[-1],
    )
    try:
        observed = provider.observe_runtime_build(attestation)
    except Exception as exc:
        raise CollectorRepairRunnerV1Error(
            "collector build provider observation failed"
        ) from exc
    if observed != attestation or attestation.get("build_id") != build_id:
        _fail("collector build provider authority differs")
    return code_sha, image, build_id


def _assert_known_output_state(
    *, phase: str, store: source_runner.GCSExactKnownNameStoreV1,
) -> None:
    from google.api_core.exceptions import NotFound

    for uri in (repair.SELECTION_URI, repair.TERMINAL_URI):
        bucket_name, object_name = store._parts(uri)
        blob = store._client.bucket(bucket_name).blob(object_name)
        try:
            blob.reload(timeout=source_runner.GCS_TIMEOUT_SECONDS)
        except NotFound:
            if phase == "reopen":
                _fail(f"repair reopen predecessor is absent: {uri}")
            continue
        if phase == "collect":
            _fail(f"repair collect output name is not absent: {uri}")
        if blob.generation is None or blob.size is None or int(blob.size) <= 0:
            _fail(f"repair reopen predecessor metadata differs: {uri}")
    bucket_name, object_name = store._parts(repair.REPAIR_RECEIPT_URI)
    receipt_blob = store._client.bucket(bucket_name).blob(object_name)
    try:
        receipt_blob.reload(timeout=source_runner.GCS_TIMEOUT_SECONDS)
    except NotFound:
        return
    _fail("collector repair sidecar already exists before seal")


def container_collect_v1() -> dict[str, object]:
    request = _request_from_environment()
    store = source_runner.GCSExactKnownNameStoreV1()
    provider = source_runner.GCloudBuildProviderV1(project=repair.PROJECT)
    code_sha, image, build_id = _validate_collector_runtime(
        request, store=store, provider=provider
    )
    _assert_known_output_state(phase=str(request["phase"]), store=store)

    # The legacy collector gate continues to see the exact d594 source
    # runtime.  The actual repair runtime remains separately present in the
    # Cloud Run execution spec and in the repair-specific environment above.
    source_environment = dict(os.environ)
    source_environment[SOURCE_CODE_ENV] = repair.SOURCE_CODE_SHA
    source_environment[SOURCE_IMAGE_DIGEST_ENV] = repair.SOURCE_IMAGE_DIGEST
    source_environment[SOURCE_MANIFEST_ENV] = repair.canonical_bytes(
        repair.SOURCE_MANIFEST_IDENTITY
    ).decode("ascii")
    source_collect = source_runner.collect_v1(
        manifest_identity=repair.SOURCE_MANIFEST_IDENTITY,
        runtime_execution_attestation_identity=(
            repair.SOURCE_EXECUTION_ATTESTATION_IDENTITY
        ),
        environment=source_environment,
        store=store,
        provider=provider,
    )
    return repair.collect_result_v1(
        request=request,
        collector_code_sha=code_sha,
        collector_image=image,
        collector_build_id=build_id,
        source_collect_result=source_collect,
    )


def _run_json(argv: list[str], *, label: str) -> dict[str, object]:
    completed = subprocess.run(argv, check=False, capture_output=True)
    if completed.returncode != 0:
        _fail(f"{label} command failed")
    return _mapping(json.loads(completed.stdout), label=label)


def _describe_execution(name: str) -> dict[str, object]:
    return _run_json(
        [
            "gcloud", "run", "jobs", "executions", "describe", name,
            "--project", repair.PROJECT, "--region", repair.REGION,
            "--format=json",
        ],
        label=f"execution {name}",
    )


def _condition(status: Mapping[str, object], *, name: str) -> dict[str, object]:
    values = [
        row for row in status.get("conditions", [])
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if len(values) != 1:
        _fail(f"{name} Completed condition differs")
    return dict(values[0])


def _env(container: Mapping[str, object], name: str) -> str:
    values = [
        row.get("value")
        for row in container.get("env", [])
        if isinstance(row, Mapping) and row.get("name") == name
    ]
    if len(values) != 1 or type(values[0]) is not str:
        _fail(f"execution environment {name} differs")
    return values[0]


def _validate_failed_execution() -> None:
    execution = _describe_execution(str(repair.FAILED_COLLECT_EXECUTION["name"]))
    metadata = _mapping(execution.get("metadata"), label="failed metadata")
    labels = _mapping(metadata.get("labels"), label="failed labels")
    status = _mapping(execution.get("status"), label="failed status")
    spec = _mapping(execution.get("spec"), label="failed spec")
    template = _mapping(spec.get("template"), label="failed template")
    task = _mapping(template.get("spec"), label="failed task")
    containers = task.get("containers")
    if not isinstance(containers, list) or len(containers) != 1:
        _fail("failed collect container count differs")
    container = _mapping(containers[0], label="failed container")
    completed = _condition(status, name="failed collect")
    expected = repair.FAILED_COLLECT_EXECUTION
    if (
        metadata.get("name") != expected["name"]
        or metadata.get("uid") != expected["uid"]
        or labels.get("run.googleapis.com/job") != expected["job_name"]
        or labels.get("run.googleapis.com/jobUid") != expected["job_uid"]
        or str(labels.get("run.googleapis.com/jobGeneration"))
        != expected["job_generation"]
        or spec.get("taskCount") != 1
        or status.get("failedCount") != 1
        or status.get("completionTime") != expected["completion_time"]
        or completed.get("status") != expected["completed_condition_status"]
        or completed.get("reason") != expected["completed_condition_reason"]
        or container.get("image") != expected["source_image"]
        or _env(container, "CODE_SHA") != expected["source_code_sha"]
    ):
        _fail("known failed collect execution differs")


def _read_stdout_result(name: str) -> dict[str, object]:
    log_filter = (
        'resource.type="cloud_run_job" AND '
        f'labels."run.googleapis.com/execution_name"="{name}" AND '
        f'logName="projects/{repair.PROJECT}/logs/run.googleapis.com%2Fstdout" '
        "AND textPayload:*"
    )
    completed = subprocess.run(
        [
            "gcloud", "logging", "read", log_filter,
            "--project", repair.PROJECT, f"--limit={MAX_LOG_ROWS}",
            "--order=asc", "--format=json",
        ],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        _fail("repair stdout log read failed")
    rows = json.loads(completed.stdout)
    payloads = [
        row.get("textPayload") for row in rows
        if isinstance(row, Mapping) and type(row.get("textPayload")) is str
    ]
    if len(payloads) != 1:
        _fail("repair stdout document count differs")
    return repair.validate_collect_result_v1(
        _parse(payloads[0].encode("utf-8"), label="repair stdout")
    )


def _validate_success_execution(
    *, name: str, result: Mapping[str, object], expected_phase: str,
) -> dict[str, object]:
    execution = _describe_execution(name)
    metadata = _mapping(execution.get("metadata"), label="repair metadata")
    labels = _mapping(metadata.get("labels"), label="repair labels")
    status = _mapping(execution.get("status"), label="repair status")
    spec = _mapping(execution.get("spec"), label="repair spec")
    template = _mapping(spec.get("template"), label="repair template")
    task = _mapping(template.get("spec"), label="repair task")
    containers = task.get("containers")
    if not isinstance(containers, list) or len(containers) != 1:
        _fail("repair execution container count differs")
    container = _mapping(containers[0], label="repair container")
    completed = _condition(status, name=f"repair {expected_phase}")
    code_sha = str(result["collector_code_sha"])
    image = str(result["collector_image"])
    build_id = str(result["collector_build_id"])
    if (
        result.get("phase") != expected_phase
        or metadata.get("name") != name
        or labels.get("run.googleapis.com/job") != repair.JOB_NAME
        or labels.get("run.googleapis.com/jobUid") != repair.JOB_UID
        or spec.get("taskCount") != 1
        or task.get("maxRetries") != 0
        or task.get("serviceAccountName") != repair.SERVICE_ACCOUNT
        or container.get("image") != image
        or container.get("command") != ["/usr/local/bin/python3.11"]
        or container.get("args") != [
            "/app/scripts/run_corpus_r6_construction_allocation_collector_repair_v1.py",
            "container-collect", "--execute",
        ]
        or _env(container, repair.COLLECTOR_CODE_SHA_ENV) != code_sha
        or _env(container, repair.COLLECTOR_IMAGE_ENV) != image
        or _env(container, repair.COLLECTOR_BUILD_ID_ENV) != build_id
        or _env(container, REPAIR_PHASE_ENV) != expected_phase
        or _env(container, repair.REQUEST_SHA_ENV)
        != result.get("request_transport_sha256")
        or _env(container, OUTCOMES_ALLOWED_ENV) != "false"
        or status.get("succeededCount") != 1
        or status.get("failedCount", 0) not in {None, 0}
        or status.get("cancelledCount", 0) not in {None, 0}
        or status.get("runningCount", 0) not in {None, 0}
        or completed.get("status") != "True"
        or type(status.get("completionTime")) is not str
    ):
        _fail(f"repair {expected_phase} provider execution differs")
    return repair.repair_execution_v1(
        phase=expected_phase,
        code_sha=code_sha,
        image=image,
        build_id=build_id,
        job_generation=str(labels.get("run.googleapis.com/jobGeneration", "")),
        execution_name=name,
        execution_uid=str(metadata.get("uid", "")),
        completion_time=str(status["completionTime"]),
    )


def _validate_seal_checkout(*, expected_code_sha: str) -> None:
    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            _fail("repair seal git authority is unavailable")
        return completed.stdout.strip()

    if (
        git("rev-parse", "HEAD") != expected_code_sha
        or git("rev-parse", "--verify", "refs/remotes/origin/main^{commit}")
        != expected_code_sha
        or git("status", "--porcelain", "--untracked-files=all")
    ):
        _fail("repair seal must run from the exact clean durable collector commit")


def seal_v1(*, collect_execution_name: str, reopen_execution_name: str) -> dict[str, object]:
    _validate_failed_execution()
    collected = _read_stdout_result(collect_execution_name)
    reopened = _read_stdout_result(reopen_execution_name)
    _validate_seal_checkout(expected_code_sha=str(collected["collector_code_sha"]))
    collect_runtime = _validate_success_execution(
        name=collect_execution_name, result=collected, expected_phase="collect"
    )
    reopen_runtime = _validate_success_execution(
        name=reopen_execution_name, result=reopened, expected_phase="reopen"
    )
    store = source_runner.GCSExactKnownNameStoreV1()
    closure = selection_operator.reopen_terminal_bundle_v1(
        collected["terminal_envelope"], read_exact=store.read_exact
    )
    receipt = repair.receipt_v1(
        collect_result=collected,
        reopen_result=reopened,
        collect_execution=collect_runtime,
        reopen_execution=reopen_runtime,
        selection_reopen_receipt=closure,
    )
    raw = repair.canonical_bytes(receipt, newline=True)
    identity = _identity(
        store.publish_create_once(repair.REPAIR_RECEIPT_URI, raw),
        label="collector repair receipt publication",
    )
    identity["create_once"] = True
    if store.read_exact(identity) != raw:
        _fail("collector repair receipt exact reopen differs")
    repair.validate_receipt_v1(_parse(raw, label="collector repair receipt"))
    body = {
        "schema_version": repair.SEAL_RESULT_SCHEMA,
        "collector_repair_receipt_identity": identity,
        "collector_repair_sha256": receipt["collector_repair_sha256"],
        "selection_terminal_envelope": collected["terminal_envelope"],
        "collect_execution": collect_runtime,
        "reopen_execution": reopen_runtime,
        "source_and_collector_runtime_are_distinct": True,
        "shard_recomputation_performed": False,
        "target_slate_outcomes_read": False,
        "complete": True,
    }
    return {**body, "seal_sha256": repair.digest(body)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    container = commands.add_parser("container-collect")
    container.add_argument("--execute", action="store_true")
    seal = commands.add_parser("seal")
    seal.add_argument("--collect-execution", required=True)
    seal.add_argument("--reopen-execution", required=True)
    seal.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.execute:
        _fail("collector repair action requires --execute")
    if args.command == "container-collect":
        result = container_collect_v1()
    else:
        result = seal_v1(
            collect_execution_name=args.collect_execution,
            reopen_execution_name=args.reopen_execution,
        )
    sys.stdout.buffer.write(repair.canonical_bytes(result, newline=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CollectorRepairRunnerV1Error,
        repair.CollectorRepairV1Error,
        selection_operator.ConstructionAllocationCrossOperatorError,
        source_runner.SnapshotShardRunnerError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
