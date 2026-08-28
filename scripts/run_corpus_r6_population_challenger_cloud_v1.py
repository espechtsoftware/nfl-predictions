#!/usr/bin/env python3
"""Prepare, launch, observe, and collect the F7/F8/F9 population batch.

This operator reuses one UID-pinned Cloud Run job.  It never creates a job,
lists Cloud Storage, reads logs, or reads outcomes.  ``configure`` and
``launch`` refuse to act while the reused job's latest execution is active.
"""

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

from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_cloud_v1 as cloud,
)


MAXIMUM_LOCAL_JSON_BYTES = 32_000_000


class RunCorpusR6PopulationChallengerCloudV1Error(RuntimeError):
    """The population challenger cloud executable failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6PopulationChallengerCloudV1Error(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return authority.object_identity_v1(value, label=label)
    except authority.CorpusR6PopulationChallengerAuthorityV1Error as exc:
        raise RunCorpusR6PopulationChallengerCloudV1Error(str(exc)) from exc


def _provider_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                _fail(f"{label} repeats JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: _fail(
                f"{label} contains non-finite constant {token}"
            ),
        )
    except RunCorpusR6PopulationChallengerCloudV1Error:
        raise
    except Exception as exc:
        raise RunCorpusR6PopulationChallengerCloudV1Error(
            f"{label} is not strict provider JSON"
        ) from exc
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _read_local(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size > MAXIMUM_LOCAL_JSON_BYTES:
        _fail(f"{label} is absent or oversized")
    try:
        return cloud.strict_json_bytes_v1(path.read_bytes(), label=label)
    except cloud.CorpusR6PopulationChallengerCloudV1Error as exc:
        raise RunCorpusR6PopulationChallengerCloudV1Error(str(exc)) from exc


def _write_local_create_once(path: Path, value: Mapping[str, object]) -> None:
    raw = cloud.canonical_bytes_v1(value)
    if len(raw) > MAXIMUM_LOCAL_JSON_BYTES:
        _fail("local operator result exceeds byte ceiling")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if path.read_bytes() != raw:
            _fail("local create-once output collision differs")


class GCSOperatorStoreV1:
    """Generation-exact known-name GCS transport; no listing method exists."""

    def __init__(self) -> None:
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - cloud dependency
            raise RuntimeError("google-cloud-storage is required") from exc
        self._client = storage.Client(
            project=cloud.PROJECT,
            client_options=ClientOptions(
                api_endpoint=authority.FIXED_STORAGE_ENDPOINT
            ),
        )
        self._cache: dict[tuple[str, str, str, int], bytes] = {}

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            _fail("operator object URI is not gs://")
        bucket, separator, name = uri[5:].partition("/")
        if (
            not separator
            or not bucket
            or not name
            or name.endswith("/")
            or "//" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))
        ):
            _fail("operator object URI differs")
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="operator exact read")
        key = (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        if key in self._cache:
            return self._cache[key]
        bucket, name = self._parts(str(identity["uri"]))
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket).blob(name, generation=generation)
        raw = blob.download_as_bytes(
            if_generation_match=generation, retry=None, timeout=300
        )
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("operator generation-exact read content differs")
        self._cache[key] = raw
        return raw

    def open_known(
        self, uri: str, maximum_bytes: int,
    ) -> tuple[bytes, Mapping[str, object]]:
        if type(maximum_bytes) is not int or maximum_bytes < 1:
            _fail("known-object byte ceiling differs")
        bucket, name = self._parts(uri)
        metadata = self._client.bucket(bucket).blob(name)
        metadata.reload(retry=None, timeout=120)
        if metadata.generation is None or metadata.size is None:
            _fail("known-object metadata lacks generation/size")
        generation = int(metadata.generation)
        size = int(metadata.size)
        if size < 1 or size > maximum_bytes:
            _fail("known-object metadata exceeds byte ceiling")
        pinned = self._client.bucket(bucket).blob(name, generation=generation)
        raw = pinned.download_as_bytes(
            if_generation_match=generation, retry=None, timeout=300
        )
        if type(raw) is not bytes or len(raw) != size:
            _fail("known-object generation-exact bytes differ")
        identity = _identity({
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": size,
        }, label="known-object result")
        self._cache[(
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )] = raw
        return raw, identity

    def publish_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw:
            _fail("operator create-once bytes differ")
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
                retry=None,
                timeout=300,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ not in {"Conflict", "PreconditionFailed"}:
                raise
            existing = self._client.bucket(bucket).blob(name)
            existing.reload(retry=None, timeout=120)
            if existing.generation is None:
                _fail("create-once collision lacks a generation")
            identity = _identity({
                "uri": uri,
                "generation": str(existing.generation),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }, label="create-once collision")
            if self.read_exact(identity) != raw:
                _fail("create-once collision bytes differ")
            return identity
        if blob.generation is None:
            _fail("create-once publication lacks a generation")
        identity = _identity({
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, label="create-once publication")
        if self.read_exact(identity) != raw:
            _fail("create-once publication exact reopen differs")
        return identity


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
            stdout = stdout_file.read(cloud.MAXIMUM_PROVIDER_JSON_BYTES + 1)
            stderr = stderr_file.read(cloud.MAXIMUM_PROVIDER_STDERR_BYTES + 1)
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
    returncode = result["returncode"]
    stdout = result["stdout"]
    stderr = result["stderr"]
    if (
        type(returncode) is not int
        or type(stdout) is not bytes
        or type(stderr) is not bytes
        or len(stdout) > stdout_ceiling
        or len(stderr) > cloud.MAXIMUM_PROVIDER_STDERR_BYTES
    ):
        _fail(f"{label} subprocess framing differs")
    if returncode != 0:
        _fail(f"{label} subprocess failed")
    return stdout


def _run_json(
    runner: SubprocessRunnerV1, argv: Sequence[str], *, label: str,
) -> dict[str, object]:
    return _provider_json(
        _run_checked(
            runner, argv, label=label,
            stdout_ceiling=cloud.MAXIMUM_PROVIDER_JSON_BYTES,
        ),
        label=f"{label} JSON",
    )


def _scope_from_execution(value: Mapping[str, object]) -> str:
    spec = value.get("spec")
    count = spec.get("taskCount") if isinstance(spec, Mapping) else None
    if count == 1:
        return cloud.TASK0_SCOPE
    if count == authority.TASK_COUNT:
        return cloud.FULL54_SCOPE
    _fail("latest execution task count is not a population operator scope")


def _assert_latest_not_active(
    job_description: Mapping[str, object], *, runner: SubprocessRunnerV1,
) -> dict[str, object] | None:
    job = cloud.validate_job_identity_v1(job_description)
    latest = job["latest_execution_name"]
    if latest is None:
        return None
    execution = _run_json(
        runner,
        cloud.execution_describe_argv_v1(str(latest)),
        label="latest execution describe",
    )
    status = cloud.build_execution_status_v1(
        execution,
        execution_name=str(latest),
        scope=_scope_from_execution(execution),
    )
    if status["terminal_state"] == "ACTIVE":
        _fail("reused job has an active execution; configuration/launch refused")
    return status


def _prepare_mode(args: argparse.Namespace) -> dict[str, object]:
    request = _read_local(args.request_file, label="population prepare request")
    store = GCSOperatorStoreV1()
    try:
        return cloud.prepare_population_manifest_v1(
            request=request,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    except cloud.CorpusR6PopulationChallengerCloudV1Error as exc:
        raise RunCorpusR6PopulationChallengerCloudV1Error(str(exc)) from exc


def _configure_mode(args: argparse.Namespace) -> dict[str, object]:
    preparation = cloud.validate_preparation_v1(
        _read_local(args.preparation_file, label="population preparation")
    )
    configuration = cloud.job_configuration_v1(preparation, scope=args.scope)
    runner = SubprocessRunnerV1()
    before_raw = _run_json(
        runner, cloud.job_describe_argv_v1(), label="preconfigure job describe"
    )
    before = cloud.validate_job_identity_v1(before_raw)
    latest = _assert_latest_not_active(before_raw, runner=runner)
    with tempfile.TemporaryDirectory(
        prefix="r6-population-challenger-flags-", dir="/tmp"
    ) as directory:
        flags_path = Path(directory) / "configure-flags.json"
        flags_path.write_bytes(
            cloud.canonical_bytes_v1(configuration["gcloud_update_flags"])
        )
        os.chmod(flags_path, 0o600)
        updated_raw = _run_json(
            runner,
            cloud.configure_argv_v1(flags_path=str(flags_path)),
            label="population job update",
        )
    after = cloud.validate_exact_job_configuration_v1(
        updated_raw, preparation=preparation, scope=args.scope
    )
    if before["job_uid"] != after["job_uid"]:
        _fail("reused job UID changed during update")
    body = {
        "schema_version": "corpus-r6-population-challenger-cloud-configure/v1",
        "scope": args.scope,
        "job_configuration_sha256": configuration[
            "job_configuration_sha256"
        ],
        "job_identity_before": before,
        "latest_execution_before": latest,
        "job_identity_after": after,
        "job_created": False,
        "outcomes_read": False,
    }
    return {
        **body,
        "configure_result_sha256": cloud.canonical_sha256_v1(body),
    }


def _launch_mode(args: argparse.Namespace) -> dict[str, object]:
    preparation = cloud.validate_preparation_v1(
        _read_local(args.preparation_file, label="population preparation")
    )
    runner = SubprocessRunnerV1()
    job_raw = _run_json(
        runner, cloud.job_describe_argv_v1(), label="prelaunch job describe"
    )
    cloud.validate_exact_job_configuration_v1(
        job_raw, preparation=preparation, scope=args.scope
    )
    _assert_latest_not_active(job_raw, runner=runner)
    raw_name = _run_checked(
        runner,
        cloud.execute_argv_v1(),
        label="population asynchronous launch",
        stdout_ceiling=4_096,
    )
    try:
        execution_name = raw_name.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise RunCorpusR6PopulationChallengerCloudV1Error(
            "population launch result is not UTF-8"
        ) from exc
    return cloud.build_launch_result_v1(
        execution_name=execution_name,
        scope=args.scope,
    )


def _status(
    launch: Mapping[str, object], *, runner: SubprocessRunnerV1,
) -> dict[str, object]:
    retained = cloud.validate_launch_result_v1(launch)
    execution = _run_json(
        runner,
        cloud.execution_describe_argv_v1(str(retained["execution_name"])),
        label="population execution describe",
    )
    return cloud.build_execution_status_v1(
        execution,
        execution_name=str(retained["execution_name"]),
        scope=str(retained["scope"]),
    )


def _status_mode(args: argparse.Namespace) -> dict[str, object]:
    launch = _read_local(args.launch_file, label="population launch result")
    return _status(launch, runner=SubprocessRunnerV1())


def _collect_mode(args: argparse.Namespace) -> dict[str, object]:
    preparation = cloud.validate_preparation_v1(
        _read_local(args.preparation_file, label="population preparation")
    )
    launch = cloud.validate_launch_result_v1(
        _read_local(args.launch_file, label="population launch result")
    )
    status = _status(launch, runner=SubprocessRunnerV1())
    store = GCSOperatorStoreV1()
    collection = cloud.collect_task_results_v1(
        preparation=preparation,
        launch_result=launch,
        execution_status=status,
        read_exact=store.read_exact,
        open_known=store.open_known,
    )
    if args.crossed_request_file is not None:
        if args.crossed_output_prefix is None:
            _fail("--crossed-request-file requires --crossed-output-prefix")
        crossed_request = cloud.build_crossed_prepare_request_v1(
            preparation=preparation,
            collection=collection,
            output_prefix=args.crossed_output_prefix,
        )
        _write_local_create_once(args.crossed_request_file, crossed_request)
    elif args.crossed_output_prefix is not None:
        _fail("--crossed-output-prefix requires --crossed-request-file")
    return collection


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Operate the frozen-source 54-task F7/F8/F9 population batch"
        )
    )
    parser.add_argument(
        "mode", choices=("prepare", "configure", "launch", "status", "collect")
    )
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--preparation-file", type=Path)
    parser.add_argument("--launch-file", type=Path)
    parser.add_argument("--scope", choices=cloud.SCOPES)
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--crossed-output-prefix")
    parser.add_argument("--crossed-request-file", type=Path)
    return parser


def _validate_cli(args: argparse.Namespace) -> None:
    required = {
        "prepare": ("request_file",),
        "configure": ("preparation_file", "scope"),
        "launch": ("preparation_file", "scope"),
        "status": ("launch_file",),
        "collect": ("preparation_file", "launch_file"),
    }[args.mode]
    missing = [field for field in required if getattr(args, field) is None]
    if missing:
        _fail(f"{args.mode} is missing required options: {missing}")
    if args.output_file.exists():
        _fail("operator output file already exists")
    if args.crossed_request_file is not None and args.crossed_request_file.exists():
        _fail("crossed prepare request file already exists")
    if args.mode != "collect" and (
        args.crossed_output_prefix is not None
        or args.crossed_request_file is not None
    ):
        _fail("crossed prepare options are collect-only")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _validate_cli(args)
    if args.mode == "prepare":
        result = _prepare_mode(args)
    elif args.mode == "configure":
        result = _configure_mode(args)
    elif args.mode == "launch":
        result = _launch_mode(args)
    elif args.mode == "status":
        result = _status_mode(args)
    else:
        result = _collect_mode(args)
    _write_local_create_once(args.output_file, result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except (
        RunCorpusR6PopulationChallengerCloudV1Error,
        cloud.CorpusR6PopulationChallengerCloudV1Error,
    ) as exc:
        print(f"population challenger cloud operator failed closed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
