#!/usr/bin/env python3
"""Dispatch exactly one immutable R6 current-bank task from a Cloud Run index."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import json
import os
import re
import resource
import signal
import subprocess
import sys
from threading import Lock, Thread
from time import monotonic
from typing import Final

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_task_manifest_v1 as task_manifest,
)


ENABLE_ENV: Final = "R6_CURRENT_BANK_TASK_DISPATCH_ENABLED"
FIXED_BUCKET: Final = "nfl-predictions-503414-corpus-retrieval"
MAXIMUM_STDOUT_EVIDENCE_BYTES: Final = (
    8_192
)
MAXIMUM_FAILURE_DIAGNOSTIC_BYTES: Final = 4_096
MAXIMUM_FAILURE_DIAGNOSTIC_EXCERPT_BYTES: Final = 768
MAXIMUM_KERNEL_CMDLINE_BYTES: Final = 8_192
MAXIMUM_EXACT_READS: Final = 256
MAXIMUM_EXACT_READ_BYTES: Final = task_manifest.MAXIMUM_MANIFEST_BYTES
MAXIMUM_EXACT_IDENTITY_PROOFS: Final = (
    task_manifest.MAXIMUM_DISPATCHER_EXACT_IDENTITY_PROOFS
)
MAXIMUM_EXACT_PROOF_BYTES: Final = (
    task_manifest.MAXIMUM_DISPATCHER_EXACT_PROOF_BYTES
)
MAXIMUM_DISPATCHER_WALL_SECONDS: Final = (
    task_manifest.MAXIMUM_DISPATCHER_WALL_SECONDS
)
MAXIMUM_CHILD_PIPE_CLEANUP_SECONDS: Final = 10
DISPATCH_TERMINAL_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-crossed-screen-dispatch-terminal-result/v1"
)
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}\Z")
_SHA_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_RUNTIME_NAME_RE: Final = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}\Z"
)
_SENSITIVE_DIAGNOSTIC_VALUE_RE: Final = re.compile(
    r"(?i)\b(authorization|bearer|token|password|passwd|secret|"
    r"api[-_ ]?key|credential)\b(?:\s*[:=]\s*|\s+)[^\s,;]+"
)
_REDIRECT_ENV_KEYS: Final = (
    "STORAGE_EMULATOR_HOST",
    "CLOUDSDK_API_ENDPOINT_OVERRIDES_STORAGE",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "PYTHONHOME",
    "PYTHONPATH",
    "LD_AUDIT",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "R6_GCS_ENDPOINT",
    "R6_PROJECT_OVERRIDE",
    "R6_PROJECTION_COMMAND",
    "R6_SELECTION_COMMAND",
    "R6_EVALUATOR_COMMAND",
    "R6_AGGREGATE_COMMAND",
    "R6_TASK_COMMAND",
    "R6_TASK_REQUEST",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH",
    "GOOGLE_API_USE_MTLS_ENDPOINT",
    "GOOGLE_API_USE_CLIENT_CERTIFICATE",
    "GCE_METADATA_HOST",
    "GCE_METADATA_ROOT",
    "GCE_METADATA_IP",
    "CLOUDSDK_CONFIG",
)
_CHILD_ENV_PASSTHROUGH: Final = frozenset({
    "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "CLOUD_RUN_JOB",
    "CLOUD_RUN_EXECUTION", "CLOUD_RUN_TASK_INDEX", "CLOUD_RUN_TASK_COUNT",
    "CLOUD_RUN_TASK_ATTEMPT", "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT",
    "GCP_PROJECT", "CODE_SHA", "R6_RUNTIME_IMAGE_DIGEST", "K_SERVICE",
    "K_REVISION", "K_CONFIGURATION",
})


class RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error(RuntimeError):
    """The immutable task dispatcher failed closed."""


def _fail(message: str) -> None:
    raise RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error(message)


class EndToEndWallDeadlineV1:
    """One monotonic budget shared by transport, child, and publication."""

    def __init__(
        self, maximum_seconds: float,
        *, clock: Callable[[], float] = monotonic,
    ) -> None:
        if (
            type(maximum_seconds) not in {int, float}
            or type(maximum_seconds) is bool
            or not 0 < float(maximum_seconds) <= 24 * 60 * 60
        ):
            _fail("dispatcher wall deadline differs")
        self._clock = clock
        self._deadline = clock() + float(maximum_seconds)

    def remaining_seconds(self) -> float:
        remaining = self._deadline - self._clock()
        if remaining <= 0:
            _fail("dispatcher end-to-end wall deadline is exhausted")
        return remaining


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error(
            "dispatcher value is not canonical JSON"
        ) from exc


def _redacted_bounded_text_v1(value: str) -> str | None:
    retained = " ".join(value.split())
    if not retained:
        return None
    retained = _SENSITIVE_DIAGNOSTIC_VALUE_RE.sub(
        lambda match: f"{match.group(1)}=<redacted>", retained
    )
    raw = retained.encode("utf-8")
    return raw[:MAXIMUM_FAILURE_DIAGNOSTIC_EXCERPT_BYTES].decode(
        "utf-8", errors="ignore"
    )


def _failure_diagnostic_v1(
    result: Mapping[str, object], *, terminalization_error: Exception | None,
) -> str:
    """Build a bounded diagnostic log line, never a scientific authority."""
    if terminalization_error is not None:
        classification = "child-terminal-contract-rejected"
    elif result.get("timed_out") is True:
        classification = "child-timeout"
    elif result.get("stdout_overflow") is True:
        classification = "child-stdout-overflow"
    elif result.get("stderr_overflow") is True:
        classification = "child-stderr-overflow"
    elif result.get("exit_code") != 0:
        classification = "child-nonzero-exit"
    else:
        classification = "child-not-accepted"
    stderr = result.get("stderr")
    stderr_bytes = stderr if type(stderr) is bytes else b""
    stderr_excerpt = _redacted_bounded_text_v1(
        stderr_bytes[-4_096:].decode("utf-8", errors="replace")
    )
    body = {
        "schema_version": (
            "corpus-r6-current-bank-crossed-screen-failure-diagnostic/v1"
        ),
        "channel": "non-authoritative-dispatcher-stderr",
        "classification": classification,
        "child_exit_code": result.get("exit_code"),
        "timed_out": result.get("timed_out"),
        "stdout_overflow": result.get("stdout_overflow"),
        "stderr_overflow": result.get("stderr_overflow"),
        "child_stderr_bytes": len(stderr_bytes),
        "child_stderr_sha256": sha256(stderr_bytes).hexdigest(),
        "sanitized_stderr_excerpt": stderr_excerpt,
        "terminalization_error_type": (
            type(terminalization_error).__name__
            if terminalization_error is not None else None
        ),
        "terminalization_error": (
            _redacted_bounded_text_v1(str(terminalization_error))
            if terminalization_error is not None else None
        ),
        "raw_child_streams_embedded_in_science_authority": False,
    }
    raw = _canonical_bytes(body)
    if len(raw) > MAXIMUM_FAILURE_DIAGNOSTIC_BYTES:
        _fail("dispatcher failure diagnostic exceeds its byte ceiling")
    return raw.decode("utf-8")


def _emit_failure_diagnostic_v1(value: str) -> None:
    try:
        sys.stderr.write(value + "\n")
        sys.stderr.flush()
    except (OSError, UnicodeError):
        # Diagnostic logging must never prevent terminal-evidence publication.
        return


def canonical_dispatcher_command_v1() -> list[str]:
    spec = task_manifest.canonical_dispatcher_process_spec_v1()
    return [str(token) for token in spec["command"]]


def kernel_observed_dispatcher_command_v1(
    raw_cmdline: bytes | None = None,
) -> list[str]:
    """Read one bounded kernel argv snapshot; wrappers and extra args fail."""
    if raw_cmdline is None:
        try:
            with open("/proc/self/cmdline", "rb") as stream:
                raw_cmdline = stream.read(MAXIMUM_KERNEL_CMDLINE_BYTES + 1)
        except OSError as exc:
            raise RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error(
                "dispatcher kernel command cannot be observed"
            ) from exc
    if (
        type(raw_cmdline) is not bytes
        or not raw_cmdline
        or len(raw_cmdline) > MAXIMUM_KERNEL_CMDLINE_BYTES
        or not raw_cmdline.endswith(b"\0")
    ):
        _fail("dispatcher kernel command bytes differ")
    try:
        tokens = [
            value.decode("utf-8") for value in raw_cmdline[:-1].split(b"\0")
        ]
    except UnicodeDecodeError as exc:
        raise RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error(
            "dispatcher kernel command is not UTF-8"
        ) from exc
    if (
        len(tokens) != len(canonical_dispatcher_command_v1())
        or any(not token for token in tokens)
    ):
        _fail("dispatcher kernel command token count differs")
    observed = tokens
    if observed != canonical_dispatcher_command_v1():
        _fail("dispatcher kernel command differs from canonical entrypoint")
    return observed


def _safe_runtime_name(value: object, *, label: str) -> str:
    if type(value) is not str or _SAFE_RUNTIME_NAME_RE.fullmatch(value) is None:
        _fail(f"{label} differs")
    return value


def _manifest_identity_from_environment(raw_value: str) -> dict[str, object]:
    if (
        not raw_value
        or len(raw_value.encode("utf-8"))
        > task_manifest.MAXIMUM_IDENTITY_ENV_BYTES
    ):
        _fail("dispatcher manifest identity environment value differs")
    identity = task_manifest.strict_json_v1(
        raw_value.encode("utf-8"), label="dispatcher manifest identity"
    )
    if set(identity) != {"uri", "generation", "sha256", "bytes"}:
        _fail("dispatcher manifest identity fields differ")
    uri = identity.get("uri")
    generation = identity.get("generation")
    digest = identity.get("sha256")
    byte_count = identity.get("bytes")
    if (
        type(uri) is not str
        or not uri.startswith(
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-current-bank-crossed-screens/"
        )
        or "/authorities/task-manifests/" not in uri
        or type(generation) is not str
        or not generation.isdecimal()
        or generation.startswith("0")
        or type(digest) is not str
        or _SHA_RE.fullmatch(digest) is None
        or type(byte_count) is not int
        or not 0 < byte_count <= task_manifest.MAXIMUM_MANIFEST_BYTES
    ):
        _fail("dispatcher manifest identity is not a bounded exact authority")
    return dict(identity)


def _bounded_identity_v1(
    value: object, *, label: str, maximum_bytes: int,
) -> dict[str, object]:
    identity = dict(value) if isinstance(value, Mapping) else {}
    if set(identity) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} fields differ")
    uri = identity.get("uri")
    generation = identity.get("generation")
    digest = identity.get("sha256")
    byte_count = identity.get("bytes")
    if (
        type(uri) is not str
        or not uri.startswith(f"gs://{FIXED_BUCKET}/")
        or type(generation) is not str
        or not generation.isdecimal()
        or generation.startswith("0")
        or type(digest) is not str
        or _SHA_RE.fullmatch(digest) is None
        or type(byte_count) is not int
        or not 0 < byte_count <= maximum_bytes
    ):
        _fail(f"{label} is not a bounded exact identity")
    return identity


def validate_preclient_invocation_v1(
    *, observed_command: object, environ: Mapping[str, str], raw_stdin: bytes,
) -> dict[str, object]:
    """Reject every invocation/redirect/authority error before cloud clients."""
    command = [str(row) for row in observed_command] if isinstance(
        observed_command, list
    ) else []
    if command != canonical_dispatcher_command_v1():
        _fail("dispatcher kernel command differs from canonical entrypoint")
    if type(raw_stdin) is not bytes or raw_stdin:
        _fail("dispatcher stdin must be immediate EOF")
    environment = dict(environ)
    if environment.get(ENABLE_ENV) != "1":
        _fail(f"dispatcher requires exact {ENABLE_ENV}=1")
    redirected = [key for key in _REDIRECT_ENV_KEYS if environment.get(key)]
    if redirected:
        _fail("dispatcher endpoint/loader/request/command redirect is forbidden")
    injected_child_keys = [
        key for key, value in environment.items()
        if key.startswith("R6_TASK_") and value
    ]
    if injected_child_keys:
        _fail("caller-supplied child task binding environment is forbidden")
    allowed_controller_keys = {
        ENABLE_ENV, task_manifest.DISPATCH_MANIFEST_IDENTITY_ENV,
        task_manifest.DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV,
    }
    extra_controller_keys = [
        key for key, value in environment.items()
        if key.startswith("R6_CURRENT_BANK_TASK_")
        and value and key not in allowed_controller_keys
    ]
    if extra_controller_keys:
        _fail("alternate dispatcher manifest/request environment is forbidden")
    project_values = {
        environment[key]
        for key in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "GCP_PROJECT")
        if environment.get(key)
    }
    if (
        project_values != {task_manifest.FIXED_GCP_PROJECT}
        or environment.get("GOOGLE_CLOUD_PROJECT")
        != task_manifest.FIXED_GCP_PROJECT
    ):
        _fail("dispatcher observed project differs from fixed project")
    commit = environment.get("CODE_SHA", "")
    image = environment.get("R6_RUNTIME_IMAGE_DIGEST", "")
    if (
        _COMMIT_RE.fullmatch(commit) is None
        or not image.startswith("sha256:")
        or _SHA_RE.fullmatch(image[7:]) is None
    ):
        _fail("dispatcher observed code/image differs")
    job = _safe_runtime_name(environment.get("CLOUD_RUN_JOB"), label="Cloud Run job")
    execution = _safe_runtime_name(
        environment.get("CLOUD_RUN_EXECUTION"), label="Cloud Run execution"
    )
    index_text = environment.get("CLOUD_RUN_TASK_INDEX", "")
    count_text = environment.get("CLOUD_RUN_TASK_COUNT", "")
    attempt_text = environment.get("CLOUD_RUN_TASK_ATTEMPT", "")
    if (
        not index_text.isdecimal()
        or len(index_text) > 6
        or not count_text.isdecimal()
        or len(count_text) > 6
        or attempt_text != "0"
    ):
        _fail("dispatcher Cloud Run task index/count/attempt differs")
    task_index = int(index_text)
    task_count = int(count_text)
    if task_count < 1 or task_index >= task_count:
        _fail("dispatcher Cloud Run task index is outside its task count")
    identity = _manifest_identity_from_environment(
        environment.get(task_manifest.DISPATCH_MANIFEST_IDENTITY_ENV, "")
    )
    if (
        environment.get(task_manifest.DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV)
        != task_manifest.ABSENT_RESUME_AUTHORITY_ENV_VALUE
    ):
        _fail("layer recovery is absent-only in the pre-output release")
    selected_environment = {
        ENABLE_ENV: environment[ENABLE_ENV],
        task_manifest.DISPATCH_MANIFEST_IDENTITY_ENV: environment[
            task_manifest.DISPATCH_MANIFEST_IDENTITY_ENV
        ],
        task_manifest.DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV: environment[
            task_manifest.DISPATCH_RESUME_AUTHORITY_IDENTITY_ENV
        ],
        "GOOGLE_CLOUD_PROJECT": environment["GOOGLE_CLOUD_PROJECT"],
        "CODE_SHA": commit,
        "R6_RUNTIME_IMAGE_DIGEST": image,
        "CLOUD_RUN_JOB": job,
        "CLOUD_RUN_EXECUTION": execution,
        "CLOUD_RUN_TASK_INDEX": index_text,
        "CLOUD_RUN_TASK_COUNT": count_text,
        "CLOUD_RUN_TASK_ATTEMPT": attempt_text,
    }
    return {
        "manifest_identity": identity,
        "recovery_allowed": False,
        "resume_authority_identity": None,
        "project_id": task_manifest.FIXED_GCP_PROJECT,
        "code_commit": commit,
        "image_digest": image,
        "job_name": job,
        "execution_name": execution,
        "task_index": task_index,
        "task_count": task_count,
        "task_attempt": 0,
        "storage_endpoint": task_manifest.FIXED_STORAGE_ENDPOINT,
        "observed_dispatcher_command": command,
        "dispatcher_selected_environment": selected_environment,
        "redirect_environment_present": False,
    }


class GCSExactReadTransportV1:
    """Bounded exact GET/create-once only; no list/current/metadata resolution."""

    def __init__(
        self, *, validated_runtime: Mapping[str, object],
        wall_deadline: EndToEndWallDeadlineV1,
    ) -> None:
        if (
            validated_runtime.get("project_id") != task_manifest.FIXED_GCP_PROJECT
            or validated_runtime.get("storage_endpoint")
            != task_manifest.FIXED_STORAGE_ENDPOINT
            or validated_runtime.get("redirect_environment_present") is not False
        ):
            _fail("exact-read transport requires validated fixed runtime")
        try:
            from google.cloud import storage
            from google.cloud.storage.retry import DEFAULT_RETRY
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error(
                "google-cloud-storage is required for task dispatch"
            ) from exc
        self._client = storage.Client(
            project=task_manifest.FIXED_GCP_PROJECT,
            client_options={"api_endpoint": task_manifest.FIXED_STORAGE_ENDPOINT},
        )
        self._wall_deadline = wall_deadline
        self._base_retry = DEFAULT_RETRY
        self._read_count = 0
        self._proof_count = 0
        self._write_count = 0

    def _operation_options(self) -> dict[str, object]:
        remaining = self._wall_deadline.remaining_seconds()
        retry = (
            None
            if self._base_retry is None
            else self._base_retry.with_deadline(remaining)
        )
        return {"timeout": remaining, "retry": retry}

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            _fail("exact-read object URI must use gs://")
        bucket, marker, name = uri[5:].partition("/")
        if (
            not marker or not bucket or not name or name.endswith("/")
            or "//" in name
            or any(part in {"", ".", ".."} for part in name.split("/"))
        ):
            _fail("exact-read object URI differs")
        return bucket, name

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        self._read_count += 1
        if self._read_count > MAXIMUM_EXACT_READS:
            _fail("dispatcher exact-read budget is exhausted")
        identity = _bounded_identity_v1(
            identity_value,
            label="dispatcher exact-read identity",
            maximum_bytes=MAXIMUM_EXACT_READ_BYTES,
        )
        bucket, name = self._parts(str(identity["uri"]))
        generation = str(identity["generation"])
        if not generation.isdecimal() or generation.startswith("0"):
            _fail("exact-read generation differs")
        blob = self._client.bucket(bucket).blob(name, generation=int(generation))
        operation = self._operation_options()
        try:
            # GCS range ends are inclusive. Request one byte beyond the exact
            # identity so a larger object fails without ever materializing an
            # unbounded response body.
            raw = blob.download_as_bytes(
                start=0,
                end=int(identity["bytes"]),
                if_generation_match=int(generation),
                **operation,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            raise RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error(
                "generation-pinned task authority GET failed"
            ) from exc
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-pinned task authority body differs")
        return raw

    def prove_exact_identity(
        self, identity_value: Mapping[str, object]
    ) -> dict[str, object]:
        """Stream one opaque generation to a digest without retaining its body."""
        self._proof_count += 1
        if self._proof_count > MAXIMUM_EXACT_IDENTITY_PROOFS:
            _fail("dispatcher exact-identity proof budget is exhausted")
        identity = _bounded_identity_v1(
            identity_value,
            label="dispatcher exact-identity proof",
            maximum_bytes=MAXIMUM_EXACT_PROOF_BYTES,
        )
        bucket, name = self._parts(str(identity["uri"]))
        generation = str(identity["generation"])
        if not generation.isdecimal() or generation.startswith("0"):
            _fail("exact-identity proof generation differs")

        class DigestSink:
            def __init__(self, maximum_bytes: int) -> None:
                self.maximum_bytes = maximum_bytes
                self.bytes_written = 0
                self.digest = sha256()

            def write(self, chunk: bytes) -> int:
                if not isinstance(chunk, bytes):
                    _fail("exact-identity proof stream emitted non-bytes")
                next_count = self.bytes_written + len(chunk)
                if next_count > self.maximum_bytes:
                    _fail("exact-identity proof stream exceeded its range ceiling")
                self.digest.update(chunk)
                self.bytes_written = next_count
                return len(chunk)

        # GCS range ends are inclusive. The extra requested byte proves that a
        # body larger than its claimed identity cannot be silently accepted.
        sink = DigestSink(int(identity["bytes"]) + 1)
        blob = self._client.bucket(bucket).blob(name, generation=int(generation))
        operation = self._operation_options()
        try:
            blob.download_to_file(
                sink,
                start=0,
                end=int(identity["bytes"]),
                raw_download=True,
                if_generation_match=int(generation),
                checksum=None,
                single_shot_download=False,
                **operation,
            )
        except RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error:
            raise
        except Exception as exc:  # pragma: no cover - cloud dependent
            raise RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error(
                "generation-pinned exact-identity proof failed"
            ) from exc
        if (
            sink.bytes_written != identity["bytes"]
            or sink.digest.hexdigest() != identity["sha256"]
        ):
            _fail("generation-pinned exact-identity proof differs")
        return identity

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if self._write_count != 0:
            _fail("dispatcher create-once write budget is exhausted")
        if (
            type(raw) is not bytes
            or not raw
            or len(raw) > task_manifest.MAXIMUM_TASK_TERMINAL_EVIDENCE_BYTES
        ):
            _fail("dispatcher create-once bytes exceed terminal evidence ceiling")
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        self._write_count += 1
        operation = self._operation_options()
        try:
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0,
                **operation,
            )
        except Exception as exc:  # pragma: no cover - cloud dependent
            if exc.__class__.__name__ in {"PreconditionFailed", "Conflict"}:
                raise RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error(
                    "terminal evidence collision lacks a manifest exact prior"
                ) from exc
            raise RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error(
                "terminal evidence create-once publication failed"
            ) from exc
        generation = str(blob.generation or "")
        if not generation.isdecimal() or generation.startswith("0"):
            _fail("terminal evidence created generation is unavailable")
        return {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }


def validate_runtime_against_manifest_v1(
    runtime_value: Mapping[str, object], authority_value: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    runtime = dict(runtime_value)
    authority = dict(authority_value)
    manifest = dict(authority.get("manifest", {}))
    manifest_identity = dict(authority.get("manifest_identity", {}))
    authorization = dict(
        authority.get("pre_design_run_authorization", {})
    )
    image_rows = [
        dict(row) for row in authorization.get("image_entrypoint_authority", [])
        if isinstance(row, Mapping)
        and row.get("process_role") == "dispatcher"
        and row.get("component_role") == "dispatcher"
    ]
    layer_rows = [
        dict(row) for row in authorization.get("layer_registry", [])
        if isinstance(row, Mapping)
        and row.get("layer_id") == manifest.get("layer_id")
    ]
    index = int(runtime["task_index"])
    if (
        runtime.get("manifest_identity") != manifest_identity
        or runtime.get("recovery_allowed") is not False
        or runtime.get("resume_authority_identity") is not None
        or runtime.get("code_commit") != manifest.get("code_commit")
        or runtime.get("image_digest") != manifest.get("image_digest")
        or runtime.get("job_name") != manifest.get("reused_job_name")
        or runtime.get("task_count") != manifest.get("task_count")
        or index >= int(manifest.get("task_count", 0))
        or runtime.get("observed_dispatcher_command")
        != manifest.get("dispatcher_process_spec", {}).get("command")
        or manifest.get("dispatcher_process_spec")
        != task_manifest.canonical_dispatcher_process_spec_v1()
        or len(image_rows) != 1
        or len(layer_rows) != 1
        or layer_rows[0].get("recovery_allowed") is not False
        or layer_rows[0].get("resume_authority_uris") != []
        or image_rows[0].get("image_canonical_path")
        != "/app/scripts/run_corpus_r6_current_bank_crossed_screen_task_dispatcher_v1.py"
        or image_rows[0].get("image_canonical_command_authority") is not True
        or image_rows[0].get("ambient_host_path_is_image_authority") is not False
    ):
        _fail("observed dispatcher runtime differs from immutable manifest")
    task = dict(manifest["task_bindings"][index])
    if task.get("task_index") != index or task.get("task_ordinal") != index:
        _fail("Cloud Run task index does not select exactly one manifest request")
    return manifest, task


def sanitized_child_environment_v1(
    *, environ: Mapping[str, str], manifest: Mapping[str, object],
    manifest_identity: Mapping[str, object], task: Mapping[str, object],
) -> dict[str, str]:
    retained = {
        key: str(value) for key, value in environ.items()
        if key in _CHILD_ENV_PASSTHROUGH and value
    }
    for key in list(retained):
        if key in _REDIRECT_ENV_KEYS or key.startswith("R6_TASK_"):
            retained.pop(key, None)
    layer = str(manifest["layer_id"])
    if layer == "projection":
        retained["R6_CURRENT_BANK_PROJECTION_PUBLICATION_ENABLED"] = "1"
    elif str(manifest["process_role"]).endswith("slate-assembler"):
        retained["R6_SELECTOR_PROCESS_ORDINAL"] = str(task["process_ordinal"])
    elif str(manifest["process_role"]).endswith("evaluator"):
        retained["R6_CURRENT_BANK_EVALUATION_PUBLICATION_ENABLED"] = "1"
        retained["R6_EVALUATOR_PROCESS_ORDINAL"] = str(task["process_ordinal"])
    else:
        retained["R6_CURRENT_BANK_AGGREGATE_PUBLICATION_ENABLED"] = "1"
        retained["R6_AGGREGATE_PROCESS_ORDINAL"] = str(task["process_ordinal"])
    retained.update(task_manifest.child_task_binding_environment_v1(
        manifest,
        manifest_identity=manifest_identity,
        task_index=int(task["task_index"]),
    ))
    return retained


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            process.kill()
        except ProcessLookupError:
            pass


def _dispatcher_peak_rss_bytes_v1() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value * 1024 if sys.platform.startswith("linux") else value


def _run_child_bounded_v1(
    *, command: list[str], input_bytes: bytes, environment: Mapping[str, str],
    stdout_ceiling: int, stderr_ceiling: int, timeout_seconds: float,
) -> dict[str, object]:
    """Run one fixed child with concurrent hard-capped pipe drains and kill."""
    if (
        not command
        or type(input_bytes) is not bytes
        or not 0 < stdout_ceiling <= 1_000_000_000
        or not 0 < stderr_ceiling <= 10_000_000
        or not 0 < timeout_seconds <= 24 * 60 * 60
    ):
        _fail("bounded child resource envelope differs")
    started = monotonic()
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(environment),
        start_new_session=True,
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    ceilings = {"stdout": stdout_ceiling, "stderr": stderr_ceiling}
    overflow = {"stdout": False, "stderr": False}
    stdin_state = {"bytes_written": 0, "closed": False}
    lock = Lock()

    def drain(name: str, stream: object) -> None:
        while True:
            chunk = stream.read(65_536)
            if not chunk:
                return
            with lock:
                remaining = ceilings[name] - len(buffers[name])
                if len(chunk) > remaining:
                    if remaining > 0:
                        buffers[name].extend(chunk[:remaining])
                    overflow[name] = True
                    _kill_process_group(process)
                    return
                buffers[name].extend(chunk)

    def write_stdin() -> None:
        assert process.stdin is not None
        view = memoryview(input_bytes)
        try:
            while view:
                written = process.stdin.write(view[:65_536])
                if written is None or written <= 0:
                    return
                stdin_state["bytes_written"] += written
                view = view[written:]
        except (BrokenPipeError, OSError):
            return
        finally:
            try:
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            stdin_state["closed"] = True

    assert process.stdout is not None and process.stderr is not None
    readers = [
        Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    writer = Thread(target=write_stdin, daemon=True)
    for reader in readers:
        reader.start()
    writer.start()
    timed_out = False
    try:
        remaining = timeout_seconds - (monotonic() - started)
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout_seconds)
        process.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_group(process)
        cleanup_deadline = monotonic() + MAXIMUM_CHILD_PIPE_CLEANUP_SECONDS
        try:
            process.wait(timeout=max(0.0, cleanup_deadline - monotonic()))
        except subprocess.TimeoutExpired:
            _fail("bounded child did not terminate after process-group kill")
    else:
        cleanup_deadline = monotonic() + MAXIMUM_CHILD_PIPE_CLEANUP_SECONDS
    writer.join(timeout=max(0.0, cleanup_deadline - monotonic()))
    for reader in readers:
        reader.join(timeout=max(0.0, cleanup_deadline - monotonic()))
    if writer.is_alive() or any(reader.is_alive() for reader in readers):
        _kill_process_group(process)
        _fail("bounded child pipe worker did not terminate")
    if (
        not timed_out
        and not any(overflow.values())
        and process.returncode == 0
        and (
            stdin_state["bytes_written"] != len(input_bytes)
            or stdin_state["closed"] is not True
        )
    ):
        _fail("bounded child did not consume its complete request stream")
    return_code = process.returncode if process.returncode is not None else 255
    if return_code < 0 or return_code > 255:
        return_code = 255
    return {
        "exit_code": return_code,
        "stdout": bytes(buffers["stdout"]),
        "stderr": bytes(buffers["stderr"]),
        "timed_out": timed_out,
        "stdout_overflow": overflow["stdout"],
        "stderr_overflow": overflow["stderr"],
        "elapsed_milliseconds": int((monotonic() - started) * 1_000),
    }


ChildRunner = Callable[..., Mapping[str, object]]


def _compact_terminal_result_v1(
    *, manifest: Mapping[str, object], manifest_identity: Mapping[str, object],
    task: Mapping[str, object], evidence: Mapping[str, object],
    evidence_identity: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "schema_version": DISPATCH_TERMINAL_RESULT_SCHEMA,
        "manifest_identity": dict(manifest_identity),
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "layer_id": manifest["layer_id"],
        "task_index": task["task_index"],
        "task_binding_sha256": task["task_binding_sha256"],
        "task_science_binding_sha256": task.get(
            "task_science_binding_sha256",
            evidence["task_science_binding_sha256"],
        ),
        "task_terminal_evidence_identity": dict(evidence_identity),
        "task_terminal_evidence_manifest_identity": dict(
            evidence["manifest_identity"]
        ),
        "task_terminal_evidence_sha256": evidence[
            "task_terminal_evidence_sha256"
        ],
        "task_completed": evidence["task_completed"],
        "recovery_allowed": False,
        "resumed_exact_prior": False,
        "terminal_evidence_generation_exact_reopen_proved": True,
        "terminal_evidence_body_embedded": False,
    }
    body["dispatch_terminal_result_sha256"] = sha256(
        _canonical_bytes(body)
    ).hexdigest()
    if len(_canonical_bytes(body)) + 1 > MAXIMUM_STDOUT_EVIDENCE_BYTES:
        _fail("dispatcher compact terminal result exceeds stdout ceiling")
    return body


def dispatch_once_v1(
    *, runtime: Mapping[str, object], environ: Mapping[str, str],
    wall_deadline: EndToEndWallDeadlineV1,
    read_exact: Callable[[Mapping[str, object]], bytes],
    prove_exact_identity: Callable[
        [Mapping[str, object]], Mapping[str, object]
    ],
    publish_create_once: Callable[[str, bytes], Mapping[str, object]],
    child_runner: ChildRunner = _run_child_bounded_v1,
) -> tuple[dict[str, object], int]:
    authority = task_manifest.reopen_task_manifest_authority_v1(
        runtime["manifest_identity"], read_exact=read_exact
    )
    manifest, task = validate_runtime_against_manifest_v1(runtime, authority)
    command = task_manifest.render_child_command_v1(
        str(manifest["layer_id"]), task["request"]
    )
    if command != task["child_command"]:
        _fail("derived child command differs from selected task binding")
    request_raw = _canonical_bytes(task["request"])
    if (
        len(request_raw) != task["request_bytes"]
        or sha256(request_raw).hexdigest() != task["request_sha256"]
    ):
        _fail("selected task canonical request bytes differ")
    child_environment = sanitized_child_environment_v1(
        environ=environ,
        manifest=manifest,
        manifest_identity=authority["manifest_identity"],
        task=task,
    )
    remaining = wall_deadline.remaining_seconds()
    child_timeout = min(
        float(task["maximum_wall_seconds"]),
        remaining - MAXIMUM_CHILD_PIPE_CLEANUP_SECONDS - 1.0,
    )
    if child_timeout <= 0:
        _fail("dispatcher wall deadline cannot admit the selected child")
    result = dict(child_runner(
        command=command,
        input_bytes=request_raw,
        environment=child_environment,
        stdout_ceiling=int(task["child_stdout_byte_ceiling"]),
        stderr_ceiling=int(task["child_stderr_byte_ceiling"]),
        timeout_seconds=child_timeout,
    ))
    required_result_fields = {
        "exit_code", "stdout", "stderr", "timed_out", "stdout_overflow",
        "stderr_overflow", "elapsed_milliseconds",
    }
    if set(result) != required_result_fields:
        _fail("bounded child runner result fields differ")
    if (
        type(result["exit_code"]) is not int
        or not 0 <= result["exit_code"] <= 255
        or type(result["stdout"]) is not bytes
        or type(result["stderr"]) is not bytes
        or type(result["elapsed_milliseconds"]) is not int
        or result["elapsed_milliseconds"] < 0
        or any(type(result[field]) is not bool for field in (
            "timed_out", "stdout_overflow", "stderr_overflow"
        ))
        or _dispatcher_peak_rss_bytes_v1() > 512 * 1024 * 1024
    ):
        _fail("bounded child runner result types/resource evidence differ")
    accepted = True
    terminalization_error: Exception | None = None
    try:
        evidence = task_manifest.build_task_terminal_evidence_v1(
            manifest=manifest,
            manifest_identity=authority["manifest_identity"],
            task_index=int(task["task_index"]),
            cloud_execution_name=str(runtime["execution_name"]),
            child_exit_code=int(result["exit_code"]),
            child_stdout=result["stdout"],
            child_stderr=result["stderr"],
            elapsed_milliseconds=int(result["elapsed_milliseconds"]),
            read_exact=read_exact,
            prove_exact_identity=prove_exact_identity,
            dispatcher_kernel_observed_command=runtime[
                "observed_dispatcher_command"
            ],
            dispatcher_selected_environment=runtime[
                "dispatcher_selected_environment"
            ],
            timed_out=result["timed_out"],
            stdout_overflow=result["stdout_overflow"],
            stderr_overflow=result["stderr_overflow"],
        )
    except Exception as exc:
        accepted = False
        terminalization_error = exc
        _emit_failure_diagnostic_v1(_failure_diagnostic_v1(
            result, terminalization_error=terminalization_error
        ))
        evidence = task_manifest.build_task_terminal_evidence_v1(
            manifest=manifest,
            manifest_identity=authority["manifest_identity"],
            task_index=int(task["task_index"]),
            cloud_execution_name=str(runtime["execution_name"]),
            child_exit_code=255,
            child_stdout=result["stdout"],
            child_stderr=result["stderr"],
            elapsed_milliseconds=int(result["elapsed_milliseconds"]),
            read_exact=read_exact,
            prove_exact_identity=prove_exact_identity,
            dispatcher_kernel_observed_command=runtime[
                "observed_dispatcher_command"
            ],
            dispatcher_selected_environment=runtime[
                "dispatcher_selected_environment"
            ],
            timed_out=bool(result["timed_out"]),
            stdout_overflow=bool(result["stdout_overflow"]),
            stderr_overflow=bool(result["stderr_overflow"]),
        )
    evidence_identity = task_manifest.publish_task_terminal_evidence_v1(
        evidence,
        manifest=manifest,
        prior_identity=None,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
    )
    compact = _compact_terminal_result_v1(
        manifest=manifest,
        manifest_identity=authority["manifest_identity"],
        task=task,
        evidence=evidence,
        evidence_identity=evidence_identity,
    )
    success = accepted and evidence["task_completed"] is True
    if not success and terminalization_error is None:
        _emit_failure_diagnostic_v1(_failure_diagnostic_v1(
            result, terminalization_error=None
        ))
    wall_deadline.remaining_seconds()
    return compact, 0 if success else 1


def _read_empty_stdin_v1() -> bytes:
    raw = sys.stdin.buffer.read(1)
    return raw


def main() -> int:
    wall_deadline = EndToEndWallDeadlineV1(MAXIMUM_DISPATCHER_WALL_SECONDS)
    raw_stdin = _read_empty_stdin_v1()
    observed_command = kernel_observed_dispatcher_command_v1()
    runtime = validate_preclient_invocation_v1(
        observed_command=observed_command, environ=os.environ,
        raw_stdin=raw_stdin,
    )
    transport = GCSExactReadTransportV1(
        validated_runtime=runtime, wall_deadline=wall_deadline
    )
    evidence, exit_code = dispatch_once_v1(
        runtime=runtime,
        environ=os.environ,
        wall_deadline=wall_deadline,
        read_exact=transport.read_exact,
        prove_exact_identity=transport.prove_exact_identity,
        publish_create_once=transport.publish_create_once,
    )
    output = _canonical_bytes(evidence) + b"\n"
    if len(output) > MAXIMUM_STDOUT_EVIDENCE_BYTES:
        _fail("dispatcher terminal evidence exceeds stdout ceiling")
    wall_deadline.remaining_seconds()
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()
    wall_deadline.remaining_seconds()
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error as exc:
        sys.stderr.write(f"task dispatcher failed closed: {exc}\n")
        raise SystemExit(1) from exc


__all__ = [
    "ENABLE_ENV",
    "GCSExactReadTransportV1",
    "MAXIMUM_KERNEL_CMDLINE_BYTES",
    "MAXIMUM_STDOUT_EVIDENCE_BYTES",
    "RunCorpusR6CurrentBankCrossedScreenTaskDispatcherV1Error",
    "canonical_dispatcher_command_v1",
    "dispatch_once_v1",
    "kernel_observed_dispatcher_command_v1",
    "main",
    "sanitized_child_environment_v1",
    "validate_preclient_invocation_v1",
    "validate_runtime_against_manifest_v1",
]
