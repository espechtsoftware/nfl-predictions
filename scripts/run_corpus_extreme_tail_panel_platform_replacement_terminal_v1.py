#!/usr/bin/env python3
"""Outcome-blind terminal closer for the exhausted T230 ordinal-6 worker.

There is intentionally no Cloud Run submit method in this controller.  Its
only cloud mutation is create-once publication of the reviewed negative
terminal and, later, the negative Lane-A root.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Final

from nfl_dfs.research import (
    corpus_extreme_tail_panel_platform_replacement_terminal_v1 as closure,
)
from nfl_dfs.research import corpus_extreme_tail_panel_platform_replacement_v1 as replacement
from nfl_dfs.research import corpus_extreme_tail_panel_transport as transport
from nfl_dfs.research import corpus_parametric_batch as batch

import run_corpus_extreme_tail_panel_platform_replacement_v1 as launch_controller
import run_corpus_extreme_tail_panel_transport_v1 as transport_cli


ENABLE_ENV: Final = "FOUNDRY_T230_TERMINAL_CLOSURE_ENABLED"
EXECUTION_DESCRIBE_ARGV: Final = closure.EXECUTION_DESCRIBE_ARGV
TASK_DESCRIBE_ARGV: Final = closure.TASK_DESCRIBE_ARGV


class T230TerminalClosureControllerError(RuntimeError):
    """The no-execution terminal closer failed closed."""


def _fail(message: str) -> None:
    raise T230TerminalClosureControllerError(message)


def _canonical(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def _one_mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _parse_json(raw: bytes, *, label: str) -> object:
    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                _fail(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda value: _fail(
                f"{label} contains non-finite value {value}"
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise T230TerminalClosureControllerError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc


def _conditions(value: object, *, label: str) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        _fail(f"{label} must be one ordered list")
    return [
        _one_mapping(row, label=f"{label}[{ordinal}]")
        for ordinal, row in enumerate(value)
    ]


class TerminalCloudObserver:
    """Two fixed gcloud describes and no write/submit/log operation."""

    @staticmethod
    def _describe(argv: Sequence[str], *, label: str) -> tuple[object, bytes]:
        completed = subprocess.run(
            list(argv),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0 or not completed.stdout:
            _fail(f"{label} exact describe failed")
        return _parse_json(completed.stdout, label=label), completed.stdout

    def observe(
        self, *, ownership: Mapping[str, object]
    ) -> Mapping[str, object]:
        execution_value, execution_raw = self._describe(
            EXECUTION_DESCRIBE_ARGV, label="replacement execution"
        )
        task_value, task_raw = self._describe(
            TASK_DESCRIBE_ARGV, label="replacement task"
        )
        execution_body = _one_mapping(
            execution_value, label="replacement execution"
        )
        if (
            not isinstance(task_value, Sequence)
            or isinstance(task_value, (str, bytes))
            or len(task_value) != 1
        ):
            _fail("replacement execution-scoped task query differs")
        task_body = _one_mapping(task_value[0], label="replacement task")
        status = _one_mapping(
            execution_body.get("status"), label="replacement execution status"
        )
        execution_conditions = _conditions(
            status.get("conditions"), label="replacement execution conditions"
        )
        expected_status_keys = {
            "completionTime",
            "conditions",
            "failedCount",
            "logUri",
            "observedGeneration",
            "startTime",
        }
        if (
            set(status) != expected_status_keys
            or execution_conditions != closure.EXECUTION_CONDITIONS
        ):
            _fail("replacement execution terminal conditions differ")
        if "succeededCount" in status or "cancelledCount" in status:
            _fail("replacement absent success/cancel count surface differs")
        metadata = _one_mapping(
            task_body.get("metadata"), label="replacement task metadata"
        )
        annotations = _one_mapping(
            metadata.get("annotations"), label="replacement task annotations"
        )
        labels = _one_mapping(
            metadata.get("labels"), label="replacement task labels"
        )
        task_status = _one_mapping(
            task_body.get("status"), label="replacement task status"
        )
        task_conditions = _conditions(
            task_status.get("conditions"), label="replacement task conditions"
        )
        last = _one_mapping(
            task_status.get("lastAttemptResult"), label="replacement last attempt"
        )
        if (
            set(task_body) != {"apiVersion", "kind", "metadata", "spec", "status"}
            or set(metadata)
            != {
                "annotations",
                "creationTimestamp",
                "generation",
                "labels",
                "name",
                "namespace",
                "resourceVersion",
                "selfLink",
            }
            or annotations
            != {"run.googleapis.com/scheduled-time": closure.REPLACEMENT_STARTED_TIME}
            or labels
            != {
                "cloud.googleapis.com/location": transport.REGION,
                "run.googleapis.com/execution": closure.REPLACEMENT_EXECUTION,
                "run.googleapis.com/job": replacement.REUSE_JOB,
                "run.googleapis.com/runningState": "Failed",
            }
            or metadata.get("generation") != 1
            or metadata.get("name") != closure.REPLACEMENT_TASK
            or task_body.get("spec") != {}
            or task_conditions
            != [
                {
                    "message": closure.TASK_MESSAGE,
                    "reason": closure.TASK_REASON,
                    "status": "False",
                    "type": "Completed",
                },
                {"status": "True", "type": "Started"},
            ]
            or last
            != {
                "exitCode": 1,
                "status": {"code": 10, "message": closure.TASK_MESSAGE},
            }
            or set(task_status)
            != {
                "completionTime",
                "conditions",
                "lastAttemptResult",
                "observedGeneration",
                "startTime",
            }
        ):
            _fail("replacement task exact shape differs")
        envelope = launch_controller._cloud_run_v1_envelope(
            execution_body,
            expected_name=closure.REPLACEMENT_EXECUTION,
            expected_job=replacement.REUSE_JOB,
            job_resource=False,
        )
        submitted = ownership.get("submitted_execution_projection")
        if not isinstance(submitted, Mapping):
            _fail("replacement ownership submitted projection differs")
        semantic_submitted = {
            key: value
            for key, value in submitted.items()
            if key
            not in {
                "schema_version",
                "execution_name",
                "full_execution_envelope_exactly_validated",
                "worker_launch_plan_sha256",
                "execution_flags_sha256",
                "describe_argv",
                "describe_stdout_sha256",
                "describe_stdout_bytes",
            }
        }
        if envelope != semantic_submitted:
            _fail("replacement terminal envelope differs from launch ownership")
        log_uri = status.get("logUri")
        if not isinstance(log_uri, str) or not log_uri:
            _fail("replacement execution log URI surface differs")
        projection = {
            "schema_version": closure.TERMINAL_PROJECTION_SCHEMA,
            "execution_name": closure.REPLACEMENT_EXECUTION,
            "task_name": metadata.get("name"),
            "job": replacement.REUSE_JOB,
            "completed_status": "False",
            "completed_reason": closure.TASK_REASON,
            "completed_message": closure.EXECUTION_COMPLETED_MESSAGE,
            "execution_status_keys": sorted(expected_status_keys),
            "execution_conditions": execution_conditions,
            "start_time": status.get("startTime"),
            "completion_time": status.get("completionTime"),
            "failed_count": status.get("failedCount"),
            "succeeded_count_present": False,
            "succeeded_count": 0,
            "cancelled_count_present": False,
            "cancelled_count": 0,
            "execution_observed_generation": status.get("observedGeneration"),
            "log_uri": log_uri,
            "log_content_read": False,
            "task_api_version": task_body.get("apiVersion"),
            "task_kind": task_body.get("kind"),
            "task_namespace": metadata.get("namespace"),
            "task_resource_version": metadata.get("resourceVersion"),
            "task_self_link": metadata.get("selfLink"),
            "task_creation_time": metadata.get("creationTimestamp"),
            "task_scheduled_time": annotations.get(
                "run.googleapis.com/scheduled-time"
            ),
            "task_start_time": task_status.get("startTime"),
            "task_completion_time": task_status.get("completionTime"),
            "task_running_state": labels.get("run.googleapis.com/runningState"),
            "task_spec": task_body.get("spec"),
            "task_completed_condition": task_conditions[0],
            "task_started_condition": task_conditions[1],
            "task_last_attempt_result": last,
            "task_observed_generation": task_status.get("observedGeneration"),
            "execution_envelope": {
                "execution_name": closure.REPLACEMENT_EXECUTION,
                **envelope,
            },
            "execution_describe_argv": list(EXECUTION_DESCRIBE_ARGV),
            "execution_describe_stdout_sha256": sha256(execution_raw).hexdigest(),
            "execution_describe_stdout_bytes": len(execution_raw),
            "task_describe_argv": list(TASK_DESCRIBE_ARGV),
            "task_describe_stdout_sha256": sha256(task_raw).hexdigest(),
            "task_describe_stdout_bytes": len(task_raw),
            "terminal_exactly_validated": True,
            "result_or_effect_content_inspected": False,
            "realized_outcomes_read": False,
        }
        return closure.validate_replacement_failure_projection_v1(projection)


class GCSClosureBackend(transport_cli.GCSJournalBackend):
    """Generation-pinned mechanics backend plus metadata-only probes."""

    def probe_known_uri_metadata(self, uri: str) -> Mapping[str, object] | None:
        bucket, name = self._parts(uri)
        blob = self._client.bucket(bucket).blob(name)
        try:
            blob.reload()
        except Exception as exc:
            try:
                from google.api_core.exceptions import NotFound
            except ImportError:  # pragma: no cover
                NotFound = ()  # type: ignore[assignment,misc]
            if NotFound and isinstance(exc, NotFound):
                return None
            raise
        if (
            blob.generation is None
            or blob.size is None
            or blob.crc32c is None
            or blob.etag is None
        ):
            _fail("known-name metadata projection is incomplete")
        return {
            "uri": uri,
            "generation": str(blob.generation),
            "size": int(blob.size),
            "crc32c": str(blob.crc32c),
            "etag": str(blob.etag),
            "content_type": "" if blob.content_type is None else str(blob.content_type),
            "content_inspected": False,
        }


def _surface_rows_for_uris(
    backend: closure.TerminalClosureBackend, uris: Sequence[str]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for uri in uris:
        retained = backend.probe_known_uri_metadata(uri)
        if retained is None:
            rows.append(
                {
                    "uri": uri,
                    "present": False,
                    "generation": None,
                    "size": None,
                    "crc32c": None,
                    "etag": None,
                    "content_type": None,
                    "content_inspected": False,
                }
            )
            continue
        row = dict(retained)
        if row.pop("uri", None) != uri or row.pop("content_inspected", None) is not False:
            _fail("known-name metadata probe differs")
        rows.append(
            {
                "uri": uri,
                "present": True,
                "generation": row.get("generation"),
                "size": row.get("size"),
                "crc32c": row.get("crc32c"),
                "etag": row.get("etag"),
                "content_type": row.get("content_type"),
                "content_inspected": False,
            }
        )
    return rows


def _surface_rows(backend: closure.TerminalClosureBackend) -> list[dict[str, object]]:
    return _surface_rows_for_uris(backend, closure.terminal_surface_uris_v1())


def build_real_artifact_preflight_v1(
    *,
    backend: closure.TerminalClosureBackend,
    observer: TerminalCloudObserver,
    preflight_attempt_marker_measurement: Mapping[str, object],
    preflight_attempt_marker: Mapping[str, object],
) -> dict[str, object]:
    lineage = closure.reopen_replacement_launch_lineage_v1(backend=backend)
    _, ownership, _ = closure._exact_read_json(
        backend,
        closure.REPLACEMENT_OWNERSHIP_IDENTITY,
        label="preflight replacement ownership",
    )
    terminal = observer.observe(ownership=ownership)
    first = closure.build_surface_census_v1(
        rows=_surface_rows(backend), pass_ordinal=1
    )
    second = closure.build_surface_census_v1(
        rows=_surface_rows(backend), pass_ordinal=2
    )
    return closure.build_terminal_closure_preflight_v1(
        launch_lineage=lineage,
        terminal_projection=terminal,
        first_census=first,
        second_census=second,
        reviewed_implementation_measurements=(
            closure.terminal_closure_implementation_measurements_v1()
        ),
        preflight_attempt_marker_measurement=(
            preflight_attempt_marker_measurement
        ),
        preflight_attempt_marker=preflight_attempt_marker,
    )


def _create_once_or_equal(
    backend: closure.TerminalClosureBackend,
    *,
    uri: str,
    value: Mapping[str, object],
) -> tuple[dict[str, object], bool]:
    raw = _canonical(value)
    try:
        identity = batch.normalize_object_identity(
            backend.create(uri, raw), label="closure create"
        )
        created = True
    except transport.JournalObjectExists:
        identity_value, retained_raw = backend.read_known_uri(uri)
        identity = batch.normalize_object_identity(
            identity_value, label="closure equal-existing"
        )
        if retained_raw != raw:
            _fail("closure create-once collision differs")
        created = False
    if (
        identity["uri"] != uri
        or identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
        or backend.read(identity) != raw
    ):
        _fail("closure create-once reopen differs")
    return identity, created


def _fixed_local_path(relative_path: str, *, must_be_absent: bool) -> Path:
    root = Path(transport.REPOSITORY_ROOT)
    relative = Path(relative_path)
    if (
        not root.is_absolute()
        or root.is_symlink()
        or not root.is_dir()
        or relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        _fail("fixed tracked path differs")
    parent = root
    for component in relative.parts[:-1]:
        parent = parent / component
        if parent.is_symlink() or not parent.is_dir():
            _fail("fixed tracked parent is unsafe")
    target = parent / relative.parts[-1]
    if target.is_symlink() or (must_be_absent and target.exists()):
        _fail("fixed tracked target is unsafe or already exists")
    return target


def _write_local_once(path: Path, value: Mapping[str, object]) -> None:
    raw = _canonical(value) + b"\n"
    directory_fd: int | None = None
    file_fd: int | None = None
    try:
        directory_fd = os.open(
            path.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        file_fd = os.open(
            path.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC,
            0o644,
            dir_fd=directory_fd,
        )
        offset = 0
        while offset < len(raw):
            written = os.write(file_fd, raw[offset:])
            if written < 1:
                _fail("tracked receipt write made no progress")
            offset += written
        os.fsync(file_fd)
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            _fail("tracked receipt file type/link count differs")
        os.fsync(directory_fd)
    except FileExistsError as exc:
        raise T230TerminalClosureControllerError(
            "tracked receipt create-once collision"
        ) from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _load_local_canonical(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        _fail(f"{label} path differs")
    raw = path.read_bytes()
    value = _parse_json(raw[:-1] if raw.endswith(b"\n") else raw, label=label)
    body = _one_mapping(value, label=label)
    if raw not in {_canonical(body), _canonical(body) + b"\n"}:
        _fail(f"{label} canonical bytes differ")
    return body


def _focused_test_pass_count(path: Path) -> int:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise T230TerminalClosureControllerError(
            "closure focused output cannot be read"
        ) from exc
    try:
        return closure.focused_test_pass_count_v1(raw)
    except closure.T230PlatformReplacementTerminalError as exc:
        raise T230TerminalClosureControllerError(str(exc)) from exc


def build_review_lock_v1() -> dict[str, object]:
    implementations = closure.terminal_closure_implementation_measurements_v1()
    marker_path = _fixed_local_path(
        closure.PREFLIGHT_ATTEMPT_RELATIVE_PATH, must_be_absent=False
    )
    marker = closure.validate_preflight_attempt_marker_v1(
        _load_local_canonical(marker_path, label="preflight-attempt marker")
    )
    marker_measurement = closure._regular_file_measurement(
        Path(transport.REPOSITORY_ROOT),
        closure.PREFLIGHT_ATTEMPT_RELATIVE_PATH,
        label="preflight-attempt marker",
    )
    preflight_path = _fixed_local_path(
        closure.PREFLIGHT_RELATIVE_PATH, must_be_absent=False
    )
    preflight = closure.validate_terminal_closure_preflight_v1(
        _load_local_canonical(preflight_path, label="closure preflight"),
        expected_implementation_measurements=implementations,
    )
    preflight_measurement = closure._regular_file_measurement(
        Path(transport.REPOSITORY_ROOT),
        closure.PREFLIGHT_RELATIVE_PATH,
        label="closure preflight",
    )
    output_path = _fixed_local_path(
        closure.FOCUSED_TEST_OUTPUT_RELATIVE_PATH, must_be_absent=False
    )
    output_measurement = closure._regular_file_measurement(
        Path(transport.REPOSITORY_ROOT),
        closure.FOCUSED_TEST_OUTPUT_RELATIVE_PATH,
        label="closure focused output",
    )
    if not output_path.is_file():
        _fail("closure focused output is absent")
    focused_test_collected = _focused_test_pass_count(output_path)
    closure.verify_terminal_closure_implementation_commit_v1(
        implementation_source_commit_sha=str(
            marker["implementation_source_commit_sha"]
        ),
        expected_implementation_measurements=implementations,
    )
    return closure.build_terminal_closure_review_lock_v1(
        implementation_source_commit_sha=str(
            marker["implementation_source_commit_sha"]
        ),
        reviewed_implementation_measurements=implementations,
        preflight_attempt_marker_measurement=marker_measurement,
        preflight_attempt_marker=marker,
        real_artifact_preflight_measurement=preflight_measurement,
        real_artifact_preflight=preflight,
        focused_test_output_measurement=output_measurement,
        focused_test_collected=focused_test_collected,
    )


def publish_replacement_terminal_v1(
    *, backend: closure.TerminalClosureBackend
) -> dict[str, object]:
    lock_measurement, lock = closure.reopen_terminal_closure_review_lock_v1()
    preflight_path = _fixed_local_path(
        closure.PREFLIGHT_RELATIVE_PATH, must_be_absent=False
    )
    preflight = closure.validate_terminal_closure_preflight_v1(
        _load_local_canonical(preflight_path, label="closure preflight")
    )
    preflight_measurement = closure._regular_file_measurement(
        Path(transport.REPOSITORY_ROOT),
        closure.PREFLIGHT_RELATIVE_PATH,
        label="closure preflight",
    )
    terminal = closure.build_replacement_execution_terminal_v1(
        preflight_measurement=preflight_measurement,
        preflight=preflight,
        review_lock_measurement=lock_measurement,
        review_lock_sha256=str(lock["terminal_closure_review_lock_sha256"]),
    )
    existing = backend.probe_known_uri_metadata(
        replacement.REPLACEMENT_EXECUTION_TERMINAL_URI
    )
    if existing is not None:
        identity, retained, raw = _read_known_json(
            backend,
            uri=replacement.REPLACEMENT_EXECUTION_TERMINAL_URI,
            label="existing replacement execution terminal",
        )
        if raw != _canonical(terminal) or retained != terminal:
            _fail("existing replacement execution terminal differs")
        other_uris = [
            uri
            for uri in closure.terminal_surface_uris_v1()
            if uri != replacement.REPLACEMENT_EXECUTION_TERMINAL_URI
        ]
        _require_absent_metadata(backend, other_uris)
        _require_absent_metadata(backend, other_uris)
        return {
            "schema_version": closure.OPERATOR_RESULT_SCHEMA,
            "disposition": "replacement-terminal-existing-equal-resolve-only",
            "replacement_execution_terminal_identity": identity,
            "replacement_execution_terminal_sha256": terminal[
                "replacement_execution_terminal_sha256"
            ],
            "cloud_run_submission_count": 0,
            "result_body_read": False,
            "acceptance_body_read": False,
            "realized_outcomes_read": False,
            "replacement_exhausted": True,
            "second_replacement_allowed": False,
            "bridge_verifier_allowed": False,
        }
    # Two new exact-name passes close the preflight-to-publication gap.  They
    # are required to remain byte-equal to the preflight absence projection.
    for pass_ordinal in (1, 2):
        current = closure.build_surface_census_v1(
            rows=_surface_rows(backend), pass_ordinal=pass_ordinal
        )
        if _canonical(current) != _canonical(
            preflight[f"{'first' if pass_ordinal == 1 else 'second'}_surface_census"]
        ):
            _fail("publication-time surface census differs from preflight")
    identity, created = _create_once_or_equal(
        backend,
        uri=replacement.REPLACEMENT_EXECUTION_TERMINAL_URI,
        value=terminal,
    )
    return {
        "schema_version": closure.OPERATOR_RESULT_SCHEMA,
        "disposition": (
            "replacement-terminal-created-once"
            if created
            else "replacement-terminal-existing-equal-resolve-only"
        ),
        "replacement_execution_terminal_identity": identity,
        "replacement_execution_terminal_sha256": terminal[
            "replacement_execution_terminal_sha256"
        ],
        "cloud_run_submission_count": 0,
        "result_body_read": False,
        "acceptance_body_read": False,
        "realized_outcomes_read": False,
        "replacement_exhausted": True,
        "second_replacement_allowed": False,
        "bridge_verifier_allowed": False,
    }


def _read_known_json(
    backend: closure.TerminalClosureBackend, *, uri: str, label: str
) -> tuple[dict[str, object], dict[str, object], bytes]:
    try:
        identity_value, raw = backend.read_known_uri(uri)
    except FileNotFoundError as exc:
        raise T230TerminalClosureControllerError(f"{label} is absent") from exc
    identity = batch.normalize_object_identity(identity_value, label=label)
    if (
        identity["uri"] != uri
        or backend.read(identity) != raw
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} generation-pinned bytes differ")
    body = _one_mapping(_parse_json(raw, label=label), label=label)
    if _canonical(body) != raw:
        _fail(f"{label} is not canonical JSON")
    return identity, body, raw


def _require_absent_metadata(
    backend: closure.TerminalClosureBackend, uris: Sequence[str]
) -> None:
    for uri in uris:
        retained = backend.probe_known_uri_metadata(uri)
        if retained is not None:
            _fail(f"Lane-A terminal surface exists: {uri}")


def publish_lane_a_terminal_root_v1(
    *, backend: closure.TerminalClosureBackend
) -> dict[str, object]:
    closure.reopen_terminal_closure_review_lock_v1()
    terminal_identity, terminal_body, _ = _read_known_json(
        backend,
        uri=replacement.REPLACEMENT_EXECUTION_TERMINAL_URI,
        label="replacement execution terminal",
    )
    terminal = closure.validate_replacement_execution_terminal_v1(terminal_body)
    contract_identity = replacement.frozen_platform_replacement_contract_v1()[
        "transport_contract_identity"
    ]
    _, contract_body, _ = closure._exact_read_json(
        backend, contract_identity, label="transport contract"
    )
    contract = transport.validate_transport_contract_v1(contract_body)
    contract_hash = str(contract["transport_contract_sha256"])
    worker_identities: list[dict[str, object]] = []
    verifier_identities: list[dict[str, object]] = []
    acceptance_identities: list[dict[str, object]] = []
    for ordinal in range(6):
        worker_uri = (
            transport.TRANSPORT_PREFIX + f"stages/run-slate/{ordinal:02d}.json"
        )
        verifier_uri = (
            transport.TRANSPORT_PREFIX
            + f"stages/verify-slate/{ordinal:02d}.json"
        )
        worker_identity, worker_body, _ = _read_known_json(
            backend, uri=worker_uri, label=f"Lane-A worker stage[{ordinal}]"
        )
        verifier_identity, verifier_body, _ = _read_known_json(
            backend, uri=verifier_uri, label=f"Lane-A verifier stage[{ordinal}]"
        )
        worker = transport.validate_stage_receipt_v1(
            worker_body,
            transport_contract_sha256=contract_hash,
            operation="run-slate",
            source_ordinal=ordinal,
        )
        verifier = transport.validate_stage_receipt_v1(
            verifier_body,
            transport_contract_sha256=contract_hash,
            operation="verify-slate",
            source_ordinal=ordinal,
        )
        exposed = verifier.get("exposed_identities")
        if not isinstance(exposed, Mapping):
            _fail("Lane-A verifier exposed identities differ")
        acceptance = batch.normalize_object_identity(
            exposed.get("acceptance_identity"),
            label=f"Lane-A acceptance[{ordinal}]",
        )
        metadata = backend.probe_known_uri_metadata(str(acceptance["uri"]))
        if (
            not isinstance(metadata, Mapping)
            or metadata.get("uri") != acceptance["uri"]
            or metadata.get("generation") != acceptance["generation"]
            or metadata.get("size") != acceptance["bytes"]
            or not isinstance(metadata.get("crc32c"), str)
            or not str(metadata["crc32c"])
            or not isinstance(metadata.get("etag"), str)
            or not str(metadata["etag"])
            or metadata.get("content_inspected") is not False
        ):
            _fail("Lane-A acceptance metadata differs from verifier stage")
        worker_identities.append(worker_identity)
        verifier_identities.append(verifier_identity)
        acceptance_identities.append(acceptance)
        if (
            worker.get("source_ordinal") != ordinal
            or verifier.get("source_ordinal") != ordinal
        ):
            _fail("Lane-A stage ordinal differs")
    existing_root = backend.probe_known_uri_metadata(
        replacement.SUPPLEMENTAL_LANE_ROOT_URI
    )
    if existing_root is not None:
        identity, retained_body, _ = _read_known_json(
            backend,
            uri=replacement.SUPPLEMENTAL_LANE_ROOT_URI,
            label="existing Lane-A terminal-invalid root",
        )
        retained = closure.validate_lane_a_terminal_invalid_root_v1(
            retained_body
        )
        if (
            retained["replacement_recovery_terminal_identity"]
            != terminal_identity
            or retained["replacement_recovery_terminal"] != terminal
            or retained["completed_worker_stage_identities"]
            != worker_identities
            or retained["completed_verifier_stage_identities"]
            != verifier_identities
            or retained["completed_acceptance_identities"]
            != acceptance_identities
        ):
            _fail("existing Lane-A terminal-invalid root lineage differs")
        other_uris = [
            uri
            for uri in closure.lane_a_terminal_surface_uris_v1()
            if uri != replacement.SUPPLEMENTAL_LANE_ROOT_URI
        ]
        _require_absent_metadata(backend, other_uris)
        _require_absent_metadata(backend, other_uris)
        return {
            "schema_version": closure.OPERATOR_RESULT_SCHEMA,
            "disposition": (
                "lane-a-terminal-invalid-root-existing-equal-resolve-only"
            ),
            "lane_a_terminal_invalid_root_identity": identity,
            "lane_a_terminal_invalid_root_sha256": retained[
                "lane_a_terminal_invalid_root_sha256"
            ],
            "accepted_count": 6,
            "required_count": 28,
            "first_incomplete_ordinal": 6,
            "cloud_run_submission_count": 0,
            "result_body_read": False,
            "acceptance_body_read": False,
            "realized_outcomes_read": False,
            "lane_terminal_invalid": True,
            "panel_terminal_invalid": True,
        }
    first_lane_a_census = closure.build_lane_a_surface_census_v1(
        rows=_surface_rows_for_uris(
            backend, closure.lane_a_terminal_surface_uris_v1()
        ),
        pass_ordinal=1,
    )
    second_lane_a_census = closure.build_lane_a_surface_census_v1(
        rows=_surface_rows_for_uris(
            backend, closure.lane_a_terminal_surface_uris_v1()
        ),
        pass_ordinal=2,
    )
    root = closure.build_lane_a_terminal_invalid_root_v1(
        recovery_terminal_identity=terminal_identity,
        recovery_terminal=terminal,
        completed_worker_stage_identities=worker_identities,
        completed_verifier_stage_identities=verifier_identities,
        completed_acceptance_identities=acceptance_identities,
        first_lane_a_surface_census=first_lane_a_census,
        second_lane_a_surface_census=second_lane_a_census,
    )
    identity, created = _create_once_or_equal(
        backend,
        uri=replacement.SUPPLEMENTAL_LANE_ROOT_URI,
        value=root,
    )
    return {
        "schema_version": closure.OPERATOR_RESULT_SCHEMA,
        "disposition": (
            "lane-a-terminal-invalid-root-created-once"
            if created
            else "lane-a-terminal-invalid-root-existing-equal-resolve-only"
        ),
        "lane_a_terminal_invalid_root_identity": identity,
        "lane_a_terminal_invalid_root_sha256": root[
            "lane_a_terminal_invalid_root_sha256"
        ],
        "accepted_count": 6,
        "required_count": 28,
        "first_incomplete_ordinal": 6,
        "cloud_run_submission_count": 0,
        "result_body_read": False,
        "acceptance_body_read": False,
        "realized_outcomes_read": False,
        "lane_terminal_invalid": True,
        "panel_terminal_invalid": True,
    }


def _backend() -> GCSClosureBackend:
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover
        raise T230TerminalClosureControllerError(
            "google-cloud-storage is required for terminal closure"
        ) from exc
    return GCSClosureBackend(storage.Client(project=transport.PROJECT))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed T230 ordinal-6 terminal closer"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--preflight", action="store_true", required=True)
    publish = commands.add_parser("publish-terminal")
    publish.add_argument("--execute", action="store_true", required=True)
    lane = commands.add_parser("publish-lane-a-closure")
    lane.add_argument("--execute", action="store_true", required=True)
    commands.add_parser("parked")
    lock = commands.add_parser("build-review-lock")
    lock.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "parked":
        print('{"cloud_run_submission_count":0,"state":"parked"}')
        return 0
    if os.environ.get(ENABLE_ENV) != "1":
        _fail(f"{ENABLE_ENV}=1 is required")
    if args.command == "build-review-lock":
        path = _fixed_local_path(
            closure.REVIEW_LOCK_RELATIVE_PATH, must_be_absent=True
        )
        result = build_review_lock_v1()
        _write_local_once(path, result)
        print(_canonical(result).decode("utf-8"))
        return 0
    if args.command == "preflight":
        path = _fixed_local_path(
            closure.PREFLIGHT_RELATIVE_PATH, must_be_absent=True
        )
        marker_path = _fixed_local_path(
            closure.PREFLIGHT_ATTEMPT_RELATIVE_PATH, must_be_absent=True
        )
        implementation_commit = os.environ.get(
            closure.IMPLEMENTATION_COMMIT_ENV, ""
        )
        implementations = closure.terminal_closure_implementation_measurements_v1()
        closure.verify_terminal_closure_implementation_commit_v1(
            implementation_source_commit_sha=implementation_commit,
            expected_implementation_measurements=implementations,
        )
        marker = closure.build_preflight_attempt_marker_v1(
            implementation_source_commit_sha=implementation_commit,
            reviewed_implementation_measurements=implementations,
        )
        _write_local_once(marker_path, marker)
        marker_measurement = closure._regular_file_measurement(
            Path(transport.REPOSITORY_ROOT),
            closure.PREFLIGHT_ATTEMPT_RELATIVE_PATH,
            label="preflight-attempt marker",
        )
        backend = _backend()
        result = build_real_artifact_preflight_v1(
            backend=backend,
            observer=TerminalCloudObserver(),
            preflight_attempt_marker_measurement=marker_measurement,
            preflight_attempt_marker=marker,
        )
        _write_local_once(path, result)
    else:
        backend = _backend()
    if args.command == "publish-terminal":
        result = publish_replacement_terminal_v1(backend=backend)
    elif args.command == "publish-lane-a-closure":
        result = publish_lane_a_terminal_root_v1(backend=backend)
    print(_canonical(result).decode("utf-8"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
