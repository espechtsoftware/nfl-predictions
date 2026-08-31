#!/usr/bin/env python3
"""Explicit CLI for validate/task0/publish/reopen of the R6 seven-pack.

No mode is implicit.  Every external mode has a separate environment guard.
The adapters use one fixed BigQuery project/location and a generation-pinned,
inventory-bounded GCS transport.  They never list, overwrite, delete, deploy,
inspect IAM, read outcomes, score lineups, or mutate graph/policy state.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from threading import Lock
from typing import Final

from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_operator_v1 as operator
from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_v1 as capture
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import (
    corpus_r6_matchup_capture_plan_from_seven_pack_v1 as plan_bridge,
)


FORBIDDEN_GCS_ENVIRONMENT: Final = (
    "STORAGE_EMULATOR_HOST",
    "CLOUD_STORAGE_EMULATOR_HOST",
    "GOOGLE_CLOUD_STORAGE_EMULATOR_HOST",
)
FORBIDDEN_BIGQUERY_ENVIRONMENT: Final = (
    "BIGQUERY_EMULATOR_HOST",
    "GOOGLE_CLOUD_BIGQUERY_EMULATOR_HOST",
)
GCS_API_ENDPOINT: Final = "https://storage.googleapis.com"
GCS_UNIVERSE_DOMAIN: Final = "googleapis.com"
GIT_EXECUTABLE: Final = Path("/usr/bin/git")
CREATE_ONCE_ATTEMPTS: Final = 2
MAX_CREATE_ONCE_BYTES: Final = 32 * 1024 * 1024 * 1024


class SevenPackCaptureCliError(RuntimeError):
    """The guarded CLI could not establish its fixed runtime boundary."""


def _fail(message: str) -> None:
    raise SevenPackCaptureCliError(message)


def _read_canonical_json(path: Path, *, label: str) -> dict[str, object]:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise SevenPackCaptureCliError(f"{label} file is absent") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        _fail(f"{label} must be one non-symlink regular file")
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SevenPackCaptureCliError(f"{label} is not canonical JSON") from exc
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a JSON object")
    item = dict(value)
    canonical = source.canonical_json_bytes(item)
    if raw not in (canonical, canonical + b"\n"):
        _fail(f"{label} bytes differ from canonical JSON")
    return item


def _trusted_repository_root(value: str) -> Path:
    path = Path(value)
    try:
        resolved = path.resolve(strict=True)
        info = os.lstat(path)
    except OSError as exc:
        raise SevenPackCaptureCliError("repository root is absent") from exc
    if (
        not path.is_absolute()
        or resolved != path
        or stat.S_ISLNK(info.st_mode)
        or not stat.S_ISDIR(info.st_mode)
    ):
        _fail("repository root must be one canonical absolute directory")
    return path


def _clean_git_environment() -> dict[str, str]:
    return {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
    }


def _run_git(repository_root: Path, arguments: Sequence[str]) -> bytes:
    try:
        info = os.lstat(GIT_EXECUTABLE)
    except OSError as exc:
        raise SevenPackCaptureCliError("fixed Git executable is absent") from exc
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or not os.access(GIT_EXECUTABLE, os.X_OK)
    ):
        _fail("fixed Git executable differs")
    try:
        completed = subprocess.run(
            [
                str(GIT_EXECUTABLE), "--no-replace-objects",
                "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                "-C", str(repository_root), *arguments,
            ],
            cwd=repository_root,
            env=_clean_git_environment(),
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SevenPackCaptureCliError("trusted Git command failed") from exc
    return completed.stdout


def _git_head(repository_root: Path) -> str:
    raw = _run_git(repository_root, ["rev-parse", "--verify", "HEAD^{commit}"])
    try:
        value = raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise SevenPackCaptureCliError("Git HEAD is not ASCII") from exc
    if raw != f"{value}\n".encode("ascii"):
        _fail("Git HEAD bytes differ")
    top_raw = _run_git(repository_root, ["rev-parse", "--show-toplevel"])
    if top_raw != f"{repository_root}\n".encode("utf-8"):
        _fail("Git top-level directory differs")
    return value


def _git_blob(repository_root: Path, commit: str, relative_path: str) -> bytes:
    if relative_path.startswith("/") or ".." in relative_path.split("/"):
        _fail("Git blob path differs")
    raw = _run_git(
        repository_root,
        ["show", "--no-ext-diff", f"{commit}:{relative_path}"],
    )
    if not raw:
        _fail("Git blob is empty")
    return raw


def _git_status(repository_root: Path, relative_paths: Sequence[str]) -> bytes:
    if not relative_paths or len(relative_paths) != len(set(relative_paths)):
        _fail("Git status path inventory differs")
    return _run_git(
        repository_root,
        ["status", "--porcelain=v1", "--untracked-files=all", "--", *relative_paths],
    )


def _gcs_parts(uri: object) -> tuple[str, str]:
    if type(uri) is not str or not uri.startswith("gs://"):
        _fail("GCS URI must be canonical")
    remainder = uri[5:]
    if (
        "/" not in remainder
        or "?" in remainder
        or "#" in remainder
        or "//" in remainder
    ):
        _fail("GCS URI must contain one bucket and object")
    bucket, object_name = remainder.split("/", 1)
    if not bucket or not object_name or object_name.startswith("/"):
        _fail("GCS URI must contain one bucket and object")
    return bucket, object_name


def _gcs_not_found(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    return (
        code == 404
        or callable(code) and code() == 404
        or type(exc).__name__ == "NotFound"
    )


class FixedGCSCaptureTransportV1:
    """Bounded pinned reader and exact-inventory create-once writer."""

    def __init__(
        self, client: object, *, expected_write_uris: Sequence[str],
    ) -> None:
        if (
            getattr(client, "project", None) != capture.PRODUCTION_PROJECT
            or str(getattr(client, "api_endpoint", "")).rstrip("/")
            != GCS_API_ENDPOINT
            or getattr(client, "universe_domain", None) != GCS_UNIVERSE_DOMAIN
            or getattr(client, "_is_emulator_set", None) is not False
        ):
            _fail("GCS client differs from the fixed genuine endpoint")
        uris = list(expected_write_uris)
        if (
            any(type(value) is not str for value in uris)
            or uris != sorted(uris)
            or len(uris) != len(set(uris))
        ):
            _fail("GCS write inventory must be unique and sorted")
        for uri in uris:
            _gcs_parts(uri)
        self._client = client
        self._expected_write_uris = tuple(uris)
        self._completed_write_uris: set[str] = set()
        self._read_operations = 0
        self._read_bytes = 0
        self._write_operations = 0
        self._write_bytes = 0
        self._read_charges: list[dict[str, object]] = []
        self._write_charges: list[dict[str, object]] = []
        self._read_lock = Lock()
        self._write_lock = Lock()

    def _charge_read(
        self, *, uri: str, generation: str | None, byte_count: int,
        purpose: str,
    ) -> None:
        if (
            type(byte_count) is not int
            or not 1 <= byte_count <= capture.MAX_EXACT_OBJECT_BYTES
        ):
            _fail("GCS exact read exceeds the per-object bound")
        with self._read_lock:
            next_operations = self._read_operations + 1
            next_bytes = self._read_bytes + byte_count
            if (
                next_operations > capture.MAX_EXACT_READS
                or next_bytes > capture.MAX_EXACT_READ_BYTES
            ):
                _fail("GCS exact-read invocation budget exhausted")
            body: dict[str, object] = {
                "ordinal": self._read_operations,
                "uri": uri,
                "generation": generation,
                "bytes": byte_count,
                "purpose": purpose,
                "charged_before_payload_access": True,
                "failed_reads_remain_charged": True,
            }
            body["read_charge_sha256"] = source.canonical_sha256(body)
            self._read_operations = next_operations
            self._read_bytes = next_bytes
            self._read_charges.append(body)

    def _charge_write(self, *, uri: str, byte_count: int, attempt: int) -> None:
        if (
            uri not in self._expected_write_uris
            or type(byte_count) is not int
            or not 1 <= byte_count <= capture.MAX_EXACT_OBJECT_BYTES
            or type(attempt) is not int
            or not 1 <= attempt <= CREATE_ONCE_ATTEMPTS
        ):
            _fail("GCS create-once charge escapes the fixed inventory")
        with self._write_lock:
            next_operations = self._write_operations + 1
            next_bytes = self._write_bytes + byte_count
            if (
                next_operations
                > len(self._expected_write_uris) * CREATE_ONCE_ATTEMPTS
                or next_bytes > MAX_CREATE_ONCE_BYTES
            ):
                _fail("GCS create-once invocation budget exhausted")
            body: dict[str, object] = {
                "ordinal": self._write_operations,
                "uri": uri,
                "attempt": attempt,
                "bytes": byte_count,
                "charged_before_backend_call": True,
                "failed_attempts_remain_charged": True,
            }
            body["write_charge_sha256"] = source.canonical_sha256(body)
            self._write_operations = next_operations
            self._write_bytes = next_bytes
            self._write_charges.append(body)

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        try:
            identity = source.normalize_object_identity_v2(
                identity_value, label="generation-pinned GCS object"
            )
        except source.CorpusR6MatchupSourceV2Error as exc:
            raise SevenPackCaptureCliError(str(exc)) from exc
        bucket, object_name = _gcs_parts(identity["uri"])
        generation = int(str(identity["generation"]))
        self._charge_read(
            uri=str(identity["uri"]),
            generation=str(identity["generation"]),
            byte_count=int(identity["bytes"]),
            purpose="generation-pinned-exact-read",
        )
        try:
            blob = self._client.bucket(bucket).blob(
                object_name, generation=generation
            )
            blob.reload(if_generation_match=generation)
        except Exception as exc:
            raise SevenPackCaptureCliError(
                "generation-pinned GCS metadata read failed"
            ) from exc
        if (
            str(getattr(blob, "generation", "")) != identity["generation"]
            or type(getattr(blob, "size", None)) is not int
            or blob.size != identity["bytes"]
        ):
            _fail("generation-pinned GCS metadata differs from reservation")
        try:
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise SevenPackCaptureCliError(
                "generation-pinned GCS payload read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-pinned GCS content identity differs")
        return raw

    def _resolve_current(
        self, uri: str, *, precharged_bytes: int,
    ) -> tuple[dict[str, object], bytes] | None:
        bucket, object_name = _gcs_parts(uri)
        try:
            current = self._client.bucket(bucket).blob(object_name)
            current.reload()
        except Exception as exc:
            if _gcs_not_found(exc):
                return None
            raise SevenPackCaptureCliError(
                "current GCS object resolution failed"
            ) from exc
        generation = str(getattr(current, "generation", ""))
        current_size = getattr(current, "size", None)
        if (
            not generation.isdigit()
            or generation.startswith("0")
            or type(current_size) is not int
            or not 1 <= current_size <= precharged_bytes
        ):
            _fail("current GCS object exceeds its precharged reopen bound")
        try:
            pinned = self._client.bucket(bucket).blob(
                object_name, generation=int(generation)
            )
            pinned.reload(if_generation_match=int(generation))
            raw = pinned.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise SevenPackCaptureCliError(
                "current GCS generation-exact reopen failed"
            ) from exc
        if (
            type(raw) is not bytes
            or not raw
            or str(getattr(pinned, "generation", "")) != generation
            or getattr(pinned, "size", None) != current_size
            or len(raw) != current_size
        ):
            _fail("current GCS generation differs")
        return (
            {
                "uri": uri,
                "generation": generation,
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            raw,
        )

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if (
            type(uri) is not str
            or type(raw) is not bytes
            or not raw
            or len(raw) > capture.MAX_EXACT_OBJECT_BYTES
            or uri not in self._expected_write_uris
        ):
            _fail("GCS publication escapes the exact write inventory")
        with self._write_lock:
            if uri in self._completed_write_uris:
                _fail("GCS write URI was repeated in one invocation")
        bucket, object_name = _gcs_parts(uri)
        for attempt in range(1, CREATE_ONCE_ATTEMPTS + 1):
            self._charge_read(
                uri=uri,
                generation=None,
                byte_count=len(raw),
                purpose="create-once-exact-equal-resume",
            )
            self._charge_write(uri=uri, byte_count=len(raw), attempt=attempt)
            try:
                blob = self._client.bucket(bucket).blob(object_name)
                blob.upload_from_string(
                    raw,
                    content_type="application/json",
                    if_generation_match=0,
                )
            except Exception:
                pass
            reopened = self._resolve_current(uri, precharged_bytes=len(raw))
            if reopened is None:
                continue
            identity, existing = reopened
            if existing != raw:
                _fail("different bytes occupy a create-once GCS target")
            with self._write_lock:
                self._completed_write_uris.add(uri)
            return identity
        _fail("create-once GCS target remains absent after bounded attempts")

    def read_budget_receipt(self) -> dict[str, object]:
        with self._read_lock:
            body: dict[str, object] = {
                "max_operations": capture.MAX_EXACT_READS,
                "max_bytes": capture.MAX_EXACT_READ_BYTES,
                "max_object_bytes": capture.MAX_EXACT_OBJECT_BYTES,
                "operations": self._read_operations,
                "bytes_reserved": self._read_bytes,
                "charges": [dict(value) for value in self._read_charges],
                "charges_sha256": source.canonical_sha256(self._read_charges),
                "all_reads_charged_before_access": True,
            }
        body["read_budget_sha256"] = source.canonical_sha256(body)
        return body

    def write_budget_receipt(self) -> dict[str, object]:
        with self._write_lock:
            completed = sorted(self._completed_write_uris)
            pending = sorted(set(self._expected_write_uris) - set(completed))
            body: dict[str, object] = {
                "expected_write_uris": list(self._expected_write_uris),
                "expected_write_uri_manifest_sha256": source.canonical_sha256(
                    list(self._expected_write_uris)
                ),
                "max_operations": (
                    len(self._expected_write_uris) * CREATE_ONCE_ATTEMPTS
                ),
                "max_bytes": MAX_CREATE_ONCE_BYTES,
                "operations": self._write_operations,
                "bytes_reserved": self._write_bytes,
                "charges": [dict(value) for value in self._write_charges],
                "charges_sha256": source.canonical_sha256(self._write_charges),
                "completed_write_uris": completed,
                "pending_write_uris": pending,
                "all_backend_writes_charged_before_call": True,
            }
        body["write_budget_sha256"] = source.canonical_sha256(body)
        return body


def _trusted_gcs_transport(
    *, expected_write_uris: Sequence[str],
) -> FixedGCSCaptureTransportV1:
    if any(os.environ.get(name) for name in FORBIDDEN_GCS_ENVIRONMENT):
        _fail("GCS emulator environment is forbidden")
    try:
        from google.cloud import storage

        client = storage.Client(
            project=capture.PRODUCTION_PROJECT,
            client_options={"api_endpoint": GCS_API_ENDPOINT},
        )
    except Exception as exc:
        raise SevenPackCaptureCliError("GCS client construction failed") from exc
    return FixedGCSCaptureTransportV1(
        client, expected_write_uris=tuple(sorted(expected_write_uris))
    )


def _not_found(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    return (
        code == 404
        or callable(code) and code() == 404
        or type(exc).__name__ == "NotFound"
    )


def _utc_seconds(value: object, *, label: str) -> str:
    if not isinstance(value, datetime):
        _fail(f"{label} timestamp is absent")
    if value.tzinfo is None:
        _fail(f"{label} timestamp lacks timezone")
    retained = value.astimezone(timezone.utc).replace(microsecond=0)
    return retained.strftime("%Y-%m-%dT%H:%M:%SZ")


class FixedBigQueryRunnerV1:
    """Five-name query-only adapter; existing deterministic jobs are reused."""

    def __init__(self) -> None:
        if any(os.environ.get(name) for name in FORBIDDEN_BIGQUERY_ENVIRONMENT):
            _fail("BigQuery emulator environment is forbidden")
        try:
            from google.cloud import bigquery

            self._bigquery = bigquery
            self._client = bigquery.Client(
                project=capture.PRODUCTION_PROJECT,
                location=capture.WAREHOUSE_LOCATION,
            )
        except Exception as exc:
            raise SevenPackCaptureCliError(
                "BigQuery client construction failed"
            ) from exc
        if getattr(self._client, "project", None) != capture.PRODUCTION_PROJECT:
            _fail("BigQuery client project differs")
        self.invocations = 0

    def __call__(self, spec_value: Mapping[str, object]) -> Mapping[str, object]:
        spec = dict(spec_value)
        if self.invocations >= capture.WAREHOUSE_QUERY_COUNT:
            _fail("BigQuery invocation budget exhausted")
        self.invocations += 1
        job_id = str(spec["job_id"])
        try:
            job = self._client.get_job(
                job_id, project=capture.PRODUCTION_PROJECT,
                location=capture.WAREHOUSE_LOCATION,
            )
        except Exception as exc:
            if not _not_found(exc):
                raise SevenPackCaptureCliError(
                    "BigQuery deterministic job lookup failed"
                ) from exc
            config = self._bigquery.QueryJobConfig(
                use_legacy_sql=False,
                use_query_cache=False,
                maximum_bytes_billed=int(spec["maximum_bytes_billed"]),
            )
            try:
                job = self._client.query(
                    str(spec["canonical_query"]),
                    job_config=config,
                    job_id=job_id,
                    location=capture.WAREHOUSE_LOCATION,
                    project=capture.PRODUCTION_PROJECT,
                )
            except Exception as query_exc:
                raise SevenPackCaptureCliError(
                    "BigQuery deterministic job creation failed"
                ) from query_exc
        if (
            getattr(job, "job_id", None) != job_id
            or getattr(job, "project", None) != capture.PRODUCTION_PROJECT
            or getattr(job, "location", None) != capture.WAREHOUSE_LOCATION
            or getattr(job, "query", None) != spec["canonical_query"]
            or getattr(job, "use_legacy_sql", None) is not False
            or getattr(job, "use_query_cache", None) is not False
            or getattr(job, "maximum_bytes_billed", None)
            != spec["maximum_bytes_billed"]
        ):
            _fail("BigQuery job differs from the fixed query request")
        try:
            result = job.result()
            rows = [
                {
                    "record_kind": row["record_kind"],
                    "slice_kind": row["slice_kind"],
                    "row_json": row["row_json"],
                }
                for row in result
            ]
            job.reload()
        except Exception as exc:
            raise SevenPackCaptureCliError("BigQuery job result failed") from exc
        return {
            "job_metadata": {
                "project_id": job.project,
                "location": job.location,
                "job_id": job.job_id,
                "query_sha256": spec["query_sha256"],
                "state": job.state,
                "error_result": job.error_result,
                "cache_hit": job.cache_hit,
                "total_bytes_processed": int(job.total_bytes_processed or 0),
                "created_utc": _utc_seconds(job.created, label="BigQuery created"),
                "started_utc": _utc_seconds(job.started, label="BigQuery started"),
                "ended_utc": _utc_seconds(job.ended, label="BigQuery ended"),
            },
            "result_rows": rows,
        }


def _emit(value: Mapping[str, object]) -> None:
    sys.stdout.buffer.write(source.canonical_json_bytes(value) + b"\n")


def _write_capture_plan_create_once(
    *, repository_root: Path, result: Mapping[str, object],
) -> Path:
    relative = result.get("capture_plan_relative_path")
    if (
        type(relative) is not str
        or relative.startswith("/")
        or "." in Path(relative).parts
        or ".." in Path(relative).parts
    ):
        _fail("capture-plan output path differs")
    path = repository_root / relative
    if path != path.resolve() or repository_root not in path.parents:
        _fail("capture-plan output escapes the repository")
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent = path.parent.resolve(strict=True)
    except OSError as exc:
        raise SevenPackCaptureCliError(
            "capture-plan output parent creation failed"
        ) from exc
    if parent != path.parent or path.exists() or path.is_symlink():
        _fail("capture-plan output must be one absent canonical path")
    plan = result.get("capture_plan")
    if not isinstance(plan, Mapping):
        _fail("capture-plan body is absent")
    raw = source.canonical_json_bytes(dict(plan)) + b"\n"
    if (
        sha256(raw).hexdigest() != result.get("capture_plan_sha256")
        or len(raw) != result.get("capture_plan_bytes")
    ):
        _fail("capture-plan result byte binding differs")
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise SevenPackCaptureCliError(
            "capture-plan create-once write failed"
        ) from exc
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guarded R6 matchup seven-pack capture"
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for name in ("validate", "task0", "publish"):
        command = subparsers.add_parser(name)
        command.add_argument("--request", type=Path, required=True)
        if name == "publish":
            command.add_argument("--repository-root", required=True)
            command.add_argument("--implementation-authority", type=Path)
    build_authority = subparsers.add_parser("build-implementation-authority")
    build_authority.add_argument("--repository-root", required=True)
    build_authority.add_argument("--source-commit-sha", required=True)
    reopen = subparsers.add_parser("reopen")
    reopen.add_argument("--release-identity", type=Path, required=True)
    reopen.add_argument("--expected-fixed-source-root", type=Path)
    freeze_plan = subparsers.add_parser("freeze-capture-plan")
    freeze_plan.add_argument("--release-identity", type=Path, required=True)
    freeze_plan.add_argument("--repository-root", required=True)
    freeze_plan.add_argument("--confirm-freeze", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "build-implementation-authority":
            repository_root = _trusted_repository_root(args.repository_root)
            _emit(operator.build_provider_source_implementation_authority_v1(
                repository_root=repository_root,
                source_commit_sha=args.source_commit_sha,
            ))
            return 0
        if args.mode == "validate":
            request = _read_canonical_json(args.request, label="capture request")
            _emit(operator.validate_request_only_v1(request))
            return 0
        if args.mode in ("task0", "publish"):
            request_raw = _read_canonical_json(args.request, label="capture request")
            request = operator.validate_capture_request_v1(request_raw)
            operator.require_mode_enabled_v1(args.mode)
            expected_writes = (
                request["output_uri_inventory"] if args.mode == "publish" else []
            )
            store = _trusted_gcs_transport(expected_write_uris=expected_writes)
            if args.mode == "task0":
                receipt = operator.run_task0_v1(
                    request_value=request,
                    read_exact=store.read_exact,
                )
            else:
                repository_root = _trusted_repository_root(args.repository_root)
                if args.implementation_authority is None:
                    implementation = (
                        operator.build_clean_implementation_authority_v1(
                            repository_root=repository_root,
                            git_head=_git_head,
                            git_blob=_git_blob,
                            git_status=_git_status,
                        )
                    )
                else:
                    implementation = (
                        operator.reopen_runtime_implementation_authority_v1(
                            repository_root=repository_root,
                            implementation_authority=_read_canonical_json(
                                args.implementation_authority,
                                label="implementation authority",
                            ),
                        )
                    )
                warehouse = FixedBigQueryRunnerV1()
                receipt = operator.run_publish_v1(
                    request_value=request,
                    implementation_authority=implementation,
                    query_warehouse=warehouse,
                    read_exact=store.read_exact,
                    publish_create_once=store.publish_create_once,
                )
            _emit({
                "operator_receipt": receipt,
                "gcs_read_budget": store.read_budget_receipt(),
                "gcs_write_budget": store.write_budget_receipt(),
            })
            return 0
        if args.mode == "reopen":
            operator.require_mode_enabled_v1("reopen")
            release_identity = _read_canonical_json(
                args.release_identity, label="release identity"
            )
            expected_root = (
                _read_canonical_json(
                    args.expected_fixed_source_root,
                    label="expected fixed source root identity",
                )
                if args.expected_fixed_source_root is not None else None
            )
            store = _trusted_gcs_transport(expected_write_uris=[])
            receipt = operator.run_reopen_v1(
                release_identity=release_identity,
                expected_fixed_source_root_identity=expected_root,
                read_exact=store.read_exact,
            )
            _emit({
                "operator_receipt": receipt,
                "gcs_read_budget": store.read_budget_receipt(),
                "gcs_write_budget": store.write_budget_receipt(),
            })
            return 0
        if args.mode == "freeze-capture-plan":
            if (
                args.confirm_freeze is not True
                or os.environ.get(plan_bridge.FREEZE_ENABLE_ENV)
                != plan_bridge.ENABLE_VALUE
            ):
                _fail(
                    "capture-plan freeze is disabled; require --confirm-freeze "
                    f"and {plan_bridge.FREEZE_ENABLE_ENV}=1"
                )
            repository_root = _trusted_repository_root(args.repository_root)
            release_identity = _read_canonical_json(
                args.release_identity, label="seven-pack release identity"
            )
            store = _trusted_gcs_transport(expected_write_uris=[])
            result = plan_bridge.build_capture_plan_from_seven_pack_v1(
                release_identity=release_identity,
                repository_root=repository_root,
                read_exact=store.read_exact,
                git_head=_git_head,
                git_blob=_git_blob,
                git_status=_git_status,
            )
            output = _write_capture_plan_create_once(
                repository_root=repository_root, result=result
            )
            receipt = dict(result)
            del receipt["capture_plan"]
            _emit({
                "bridge_receipt": receipt,
                "capture_plan_output_path": str(output),
                "gcs_read_budget": store.read_budget_receipt(),
                "gcs_write_budget": store.write_budget_receipt(),
            })
            return 0
        _fail("unregistered CLI mode")
    except (
        SevenPackCaptureCliError,
        operator.CorpusR6MatchupSevenPackCaptureOperatorV1Error,
        capture.CorpusR6MatchupSevenPackCaptureV1Error,
        plan_bridge.CorpusR6MatchupCapturePlanFromSevenPackV1Error,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
