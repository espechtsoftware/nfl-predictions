#!/usr/bin/env python3
"""Prepare, execute, or finalize the fixed 54-task R6 L2b panel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_r6_l2b_panel_cloud_v1 as panel
from nfl_dfs.research import corpus_r6_l2b_panel_operator_v1 as operator


class RunCorpusR6L2BPanelCloudV1Error(RuntimeError):
    """The fixed L2b cloud command failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6L2BPanelCloudV1Error(message)


def _canonical(value: object) -> bytes:
    return legal.canonical_json_bytes(value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(
            f"{label} is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=label)
    if _canonical(item) != raw:
        _fail(f"{label} is not canonical JSON")
    return item


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return panel._identity(value, label=label)
    except panel.CorpusR6L2BPanelCloudV1Error as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(str(exc)) from exc


class GCSExactTransportV1:
    """Fixed-project exact reads plus create-once equal-byte recovery."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise RuntimeError("google-cloud-storage is required") from exc
        self._client = storage.Client(
            project=panel.FIXED_GCP_PROJECT,
            client_options=ClientOptions(
                api_endpoint=panel.FIXED_STORAGE_ENDPOINT
            ),
        )
        self._cache: dict[tuple[str, str, str, int], bytes] = {}

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            _fail("GCS URI must use gs://")
        bucket, separator, name = uri[5:].partition("/")
        if not separator or not bucket or not name:
            _fail("GCS URI is malformed")
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="GCS exact read")
        key = (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        if key in self._cache:
            return self._cache[key]
        bucket_name, object_name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = blob.download_as_bytes(
            if_generation_match=generation, retry=None
        )
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-exact GCS bytes differ")
        self._cache[key] = raw
        return raw

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("create-once publication bytes differ")
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        content_type = (
            "application/octet-stream" if uri.endswith(".npz")
            else "application/json"
        )
        try:
            blob.upload_from_string(
                raw,
                content_type=content_type,
                if_generation_match=0,
                retry=None,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            current = self._client.bucket(bucket_name).blob(object_name)
            current.reload(retry=None)
            if current.generation is None:
                _fail("create-once collision lacks an existing generation")
            identity = {
                "uri": uri,
                "generation": str(current.generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
            if self.read_exact(identity) != raw:
                _fail("create-once collision bytes differ")
            return identity
        if blob.generation is None:
            _fail("create-once publication lacks a generation")
        identity = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if self.read_exact(identity) != raw:
            _fail("create-once publication exact reopen differs")
        return identity

    def open_known(
        self, uri: str, maximum_bytes: int,
    ) -> tuple[bytes, Mapping[str, object]]:
        if type(maximum_bytes) is not int or maximum_bytes < 1:
            _fail("known-object byte ceiling differs")
        bucket_name, object_name = self._parts(uri)
        metadata = self._client.bucket(bucket_name).blob(object_name)
        metadata.reload(retry=None)
        if metadata.generation is None or metadata.size is None:
            _fail("known object lacks generation or size")
        generation = int(metadata.generation)
        size = int(metadata.size)
        if size < 1 or size > maximum_bytes:
            _fail("known object exceeds its byte ceiling")
        pinned = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        raw = pinned.download_as_bytes(
            if_generation_match=generation, retry=None
        )
        identity = _identity({
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, label="known object")
        if len(raw) != size:
            _fail("known object generation-exact size differs")
        self._cache[(
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )] = raw
        return raw, identity


class SubprocessRunnerV1:
    """Bounded argv-only gcloud runner with no shell invocation."""

    def __call__(self, argv: Sequence[str]) -> Mapping[str, object]:
        with tempfile.TemporaryFile(mode="w+b") as stdout_file, tempfile.TemporaryFile(
            mode="w+b"
        ) as stderr_file:
            completed = subprocess.run(
                list(argv),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                check=False,
                timeout=300,
            )
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read(operator.MAXIMUM_PROVIDER_JSON_BYTES + 1)
            stderr = stderr_file.read(operator.MAXIMUM_PROVIDER_STDERR_BYTES + 1)
        return {
            "returncode": int(completed.returncode),
            "stdout": bytes(stdout),
            "stderr": bytes(stderr),
        }


def _run_checked(
    runner: SubprocessRunnerV1, argv: Sequence[str], *, label: str,
    stdout_ceiling: int,
) -> bytes:
    result = runner(argv)
    if set(result) != {"returncode", "stdout", "stderr"}:
        _fail(f"{label} subprocess result fields differ")
    if (
        type(result["returncode"]) is not int
        or type(result["stdout"]) is not bytes
        or type(result["stderr"]) is not bytes
        or len(result["stdout"]) > stdout_ceiling
        or len(result["stderr"]) > operator.MAXIMUM_PROVIDER_STDERR_BYTES
        or result["returncode"] != 0
    ):
        _fail(f"{label} subprocess failed or exceeded its framing")
    return result["stdout"]


def _provider_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(
            f"{label} is not provider JSON"
        ) from exc
    return _mapping(value, label=label)


def _run_json(
    runner: SubprocessRunnerV1, argv: Sequence[str], *, label: str,
) -> dict[str, object]:
    return _provider_json(
        _run_checked(
            runner, argv, label=label,
            stdout_ceiling=operator.MAXIMUM_PROVIDER_JSON_BYTES,
        ),
        label=f"{label} JSON",
    )


def _identity_environment(value: str, *, label: str) -> dict[str, object]:
    if not value or len(value.encode("utf-8")) > 2_048:
        _fail(f"{label} is absent or oversized")
    return _identity(
        _strict_json(value.encode("utf-8"), label=label), label=label
    )


def _prepare(request_file: Path, store: GCSExactTransportV1) -> dict[str, object]:
    request = _strict_json(request_file.read_bytes(), label="preparation request")
    expected = {
        "later_source_freeze_identity", "calibration_release_identity",
        "pit_target_panel_identity", "terminal_build_receipt_identity",
        "output_prefix", "source_commit_sha", "immutable_image_digest",
        "reused_job_name", "reused_job_uid",
    }
    if set(request) != expected:
        _fail("preparation request fields differ")
    return panel.prepare_54_task_manifest_v1(
        later_source_freeze_identity=request["later_source_freeze_identity"],
        calibration_release_identity=request["calibration_release_identity"],
        pit_target_panel_identity=request["pit_target_panel_identity"],
        terminal_build_receipt_identity=request[
            "terminal_build_receipt_identity"
        ],
        output_prefix=str(request["output_prefix"]),
        source_commit_sha=str(request["source_commit_sha"]),
        immutable_image_digest=str(request["immutable_image_digest"]),
        reused_job_name=str(request["reused_job_name"]),
        reused_job_uid=str(request["reused_job_uid"]),
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )


def _execute_task(store: GCSExactTransportV1) -> dict[str, object]:
    if os.environ.get(panel.ENABLE_ENV) != "1":
        _fail("L2b panel execution is not explicitly enabled")
    manifest_identity = _identity_environment(
        os.environ.get(panel.MANIFEST_IDENTITY_ENV, ""),
        label="L2b manifest identity environment",
    )
    try:
        task_index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", ""))
        task_count = int(os.environ.get("CLOUD_RUN_TASK_COUNT", ""))
        task_attempt = int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", ""))
    except ValueError as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(
            "Cloud Run task environment is not exact integer text"
        ) from exc
    scope = os.environ.get(panel.EXECUTION_SCOPE_ENV)
    if scope == panel.TASK0_SCOPE:
        expected_task_count = 1
        if task_index != 0:
            _fail("L2b task0 smoke may execute only task index zero")
    elif scope == panel.FULL54_SCOPE:
        expected_task_count = panel.TASK_COUNT
    else:
        _fail("L2b execution scope must be task0 or full54")
    if task_count != expected_task_count or task_attempt != 0:
        _fail("Cloud Run task count/attempt differs from the no-retry law")
    manifest, _ = panel._open_manifest(
        manifest_identity=manifest_identity, read_exact=store.read_exact
    )
    if (
        os.environ.get("CODE_SHA") != manifest["source_commit_sha"]
        or os.environ.get("R6_RUNTIME_IMAGE_DIGEST")
        != manifest["immutable_image_digest"]
        or os.environ.get(panel.REUSED_JOB_UID_ENV)
        != manifest["reused_job_uid"]
    ):
        _fail("Cloud Run code/image/job environment differs from the manifest")
    result = panel.execute_manifest_task_v1(
        manifest_identity=manifest_identity,
        task_index=task_index,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    return {
        "schema_version": "corpus-r6-l2b-cloud-task-completion/v1",
        "task_index": task_index,
        "slate_id": result.task_result["slate_id"],
        "task_result_identity": result.task_result_identity,
        "task_result_sha256": result.task_result["task_result_sha256"],
        "complete": True,
    }


def _finalize(request_file: Path, store: GCSExactTransportV1) -> dict[str, object]:
    request = _strict_json(request_file.read_bytes(), label="finalization request")
    if set(request) != {"manifest_identity", "task_result_identities"}:
        _fail("finalization request fields differ")
    identities = request["task_result_identities"]
    if isinstance(identities, (str, bytes)) or not isinstance(identities, list):
        _fail("finalization task identities must be one ordered array")
    return panel.finalize_panel_root_v1(
        manifest_identity=request["manifest_identity"],
        task_result_identities=identities,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )


def _read_local(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file():
        _fail(f"{label} must be an existing absolute file")
    try:
        return _strict_json(path.read_bytes(), label=label)
    except OSError as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(f"{label} read failed") from exc


def _scope_from_execution(value: Mapping[str, object]) -> str:
    spec = value.get("spec")
    count = spec.get("taskCount") if isinstance(spec, Mapping) else None
    if count == 1:
        return operator.TASK0_SCOPE
    if count == panel.TASK_COUNT:
        return operator.FULL54_SCOPE
    _fail("latest L2b execution task count is not task0 or full54")


def _status(
    launch: Mapping[str, object], *, runner: SubprocessRunnerV1,
) -> dict[str, object]:
    retained = operator.validate_launch_result_v1(launch)
    raw = _run_json(
        runner,
        operator.execution_describe_argv_v1(str(retained["execution_name"])),
        label="L2b execution describe",
    )
    return operator.build_execution_status_v1(
        raw,
        execution_name=str(retained["execution_name"]),
        scope=str(retained["scope"]),
    )


def _assert_latest_not_active(
    job_description: Mapping[str, object], *, runner: SubprocessRunnerV1,
) -> dict[str, object] | None:
    job = operator.validate_job_identity_v1(job_description)
    latest = job["latest_execution_name"]
    if latest is None:
        return None
    raw = _run_json(
        runner,
        operator.execution_describe_argv_v1(str(latest)),
        label="latest L2b execution describe",
    )
    status = operator.build_execution_status_v1(
        raw,
        execution_name=str(latest),
        scope=_scope_from_execution(raw),
    )
    if status["terminal_state"] == "ACTIVE":
        _fail("reused L2b job has an active execution")
    return status


def configure_operator_v1(
    *, preparation: object, scope: str, store: GCSExactTransportV1,
    runner: SubprocessRunnerV1,
) -> dict[str, object]:
    retained = operator.validate_preparation_v1(preparation)
    configuration = operator.build_job_configuration_v1(
        preparation=retained, scope=scope, read_exact=store.read_exact
    )
    before_raw = _run_json(
        runner, operator.job_describe_argv_v1(),
        label="preconfigure L2b job describe",
    )
    before = operator.validate_job_identity_v1(before_raw)
    latest = _assert_latest_not_active(before_raw, runner=runner)
    with tempfile.TemporaryDirectory(prefix="r6-l2b-flags-", dir="/tmp") as directory:
        flags_path = Path(directory) / "configure-flags.json"
        flags_path.write_bytes(_canonical(configuration["gcloud_update_flags"]))
        os.chmod(flags_path, 0o600)
        updated_raw = _run_json(
            runner,
            operator.configure_argv_v1(flags_path=str(flags_path)),
            label="L2b job update",
        )
    after = operator.validate_exact_job_configuration_v1(
        updated_raw, configuration=configuration
    )
    if before["job_uid"] != after["job_uid"]:
        _fail("reused L2b job UID changed during update")
    body = {
        "schema_version": "corpus-r6-l2b-operator-configure/v1",
        "scope": scope,
        "job_configuration_sha256": configuration[
            "job_configuration_sha256"
        ],
        "job_identity_before": before,
        "latest_execution_before": latest,
        "job_identity_after": after,
        "job_created": False,
        "outcomes_read": False,
    }
    return {**body, "configure_result_sha256": operator.canonical_sha256_v1(body)}


def launch_operator_v1(
    *, preparation: object, scope: str, store: GCSExactTransportV1,
    runner: SubprocessRunnerV1,
) -> dict[str, object]:
    retained = operator.validate_preparation_v1(preparation)
    configuration = operator.build_job_configuration_v1(
        preparation=retained, scope=scope, read_exact=store.read_exact
    )
    job_raw = _run_json(
        runner, operator.job_describe_argv_v1(), label="prelaunch L2b job describe"
    )
    operator.validate_exact_job_configuration_v1(
        job_raw, configuration=configuration
    )
    _assert_latest_not_active(job_raw, runner=runner)
    raw_name = _run_checked(
        runner,
        operator.execute_argv_v1(),
        label="L2b asynchronous launch",
        stdout_ceiling=4_096,
    )
    try:
        execution_name = raw_name.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(
            "L2b launch result is not UTF-8"
        ) from exc
    return operator.build_launch_result_v1(
        execution_name=execution_name, scope=scope
    )


def collect_operator_v1(
    *, preparation: object, launch: object, store: GCSExactTransportV1,
    runner: SubprocessRunnerV1,
) -> dict[str, object]:
    status = _status(_mapping(launch, label="L2b launch"), runner=runner)
    return operator.collect_task_results_v1(
        preparation=preparation,
        launch_result=launch,
        execution_status=status,
        read_exact=store.read_exact,
        open_known=store.open_known,
    )


def _write_create_once(path: Path, value: Mapping[str, object]) -> None:
    raw = _canonical(value)
    if not path.is_absolute() or not path.parent.is_dir():
        _fail("local output must be a new file in an existing directory")
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(
            "local output already exists; create-once write refused"
        ) from exc
    except OSError as exc:
        raise RunCorpusR6L2BPanelCloudV1Error(
            "create-once local output write failed"
        ) from exc
    sys.stdout.buffer.write(raw + b"\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--request-file", type=Path, required=True)
    prepare.add_argument("--output-file", type=Path, required=True)
    sub.add_parser("execute-task")
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--request-file", type=Path, required=True)
    finalize.add_argument("--output-file", type=Path, required=True)
    for command in ("configure", "launch"):
        child = sub.add_parser(command)
        child.add_argument("--preparation-file", type=Path, required=True)
        child.add_argument("--scope", choices=operator.SCOPES, required=True)
        child.add_argument("--output-file", type=Path, required=True)
    status = sub.add_parser("status")
    status.add_argument("--launch-file", type=Path, required=True)
    status.add_argument("--output-file", type=Path, required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--preparation-file", type=Path, required=True)
    collect.add_argument("--launch-file", type=Path, required=True)
    collect.add_argument("--output-file", type=Path, required=True)
    collect.add_argument("--finalization-request-file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare":
        store = GCSExactTransportV1()
        _write_create_once(args.output_file, _prepare(args.request_file, store))
        return 0
    if args.command == "execute-task":
        store = GCSExactTransportV1()
        sys.stdout.buffer.write(_canonical(_execute_task(store)) + b"\n")
        return 0
    if args.command == "finalize":
        store = GCSExactTransportV1()
        _write_create_once(args.output_file, _finalize(args.request_file, store))
        return 0
    runner = SubprocessRunnerV1()
    if args.command == "status":
        launch = _read_local(args.launch_file, label="L2b launch result")
        _write_create_once(args.output_file, _status(launch, runner=runner))
        return 0
    preparation = _read_local(args.preparation_file, label="L2b preparation")
    store = GCSExactTransportV1()
    if args.command == "configure":
        result = configure_operator_v1(
            preparation=preparation, scope=args.scope, store=store, runner=runner
        )
    elif args.command == "launch":
        result = launch_operator_v1(
            preparation=preparation, scope=args.scope, store=store, runner=runner
        )
    elif args.command == "collect":
        launch = _read_local(args.launch_file, label="L2b launch result")
        result = collect_operator_v1(
            preparation=preparation, launch=launch, store=store, runner=runner
        )
        if args.finalization_request_file is not None:
            if result["panel_finalization_ready"] is not True:
                _fail("task0 collection cannot create a panel finalization request")
            _write_create_once(args.finalization_request_file, {
                "manifest_identity": result["task_manifest_identity"],
                "task_result_identities": result["task_result_identities"],
            })
    else:  # pragma: no cover - argparse owns the command registry
        _fail("unknown command")
    _write_create_once(args.output_file, result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        RunCorpusR6L2BPanelCloudV1Error,
        panel.CorpusR6L2BPanelCloudV1Error,
        operator.CorpusR6L2BPanelOperatorV1Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
