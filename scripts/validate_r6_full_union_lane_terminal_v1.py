#!/usr/bin/env python3
"""Offline terminal-envelope receipt tool for the already-running R6 lanes."""

from __future__ import annotations

import argparse
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Mapping, Sequence


SCHEMA = "r6-full-union-lane-terminal-receipt/v1"


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _fail(message: str) -> None:
    raise ValueError(message)


def build_receipt(
    envelope: Mapping[str, object], *, lane: str, execution: str, job: str,
    image: str, code_sha: str, service_account: str, task_count: int, parallelism: int,
    expected_args: Sequence[str],
) -> dict[str, object]:
    spec = envelope.get("spec")
    status = envelope.get("status")
    metadata = envelope.get("metadata")
    if not all(isinstance(row, Mapping) for row in (spec, status, metadata)):
        _fail("terminal envelope shape differs")
    task = spec.get("template", {}).get("spec", {})  # type: ignore[union-attr]
    containers = task.get("containers", [])
    expected_env = [
        {"name": "R6_FULL_UNION_PANEL_FREEZE_PRODUCTION_ENABLED", "value": "1"},
        {"name": "R6_FULL_UNION_PANEL_FREEZE_RUNTIME_IMAGE", "value": image},
    ]
    conditions = [
        row.get("status") for row in status.get("conditions", [])  # type: ignore[union-attr]
        if row.get("type") == "Completed"
    ]
    observed_name = str(metadata.get("name", "")).split("/")[-1]  # type: ignore[union-attr]
    observed_job = metadata.get("labels", {}).get("run.googleapis.com/job")  # type: ignore[union-attr]
    if (
        observed_name != execution or observed_job != job
        or not execution.startswith(job + "-")
        or spec.get("taskCount") != task_count  # type: ignore[union-attr]
        or spec.get("parallelism") != parallelism  # type: ignore[union-attr]
        or task.get("maxRetries") != 0
        or set(task) != {"containers", "maxRetries", "serviceAccountName", "timeoutSeconds"}
        or len(containers) != 1
        or set(containers[0]) != {"args", "command", "env", "image", "resources"}
        or containers[0].get("image") != image
        or containers[0].get("command") != ["python"]
        or containers[0].get("args") != list(expected_args)
        or "workingDir" in containers[0]
        or not list(expected_args) or str(expected_args[0]).startswith("/")
        or task.get("serviceAccountName") != service_account
        or len(conditions) != 1 or conditions[0] not in {"True", "False"}
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", str(status.get("completionTime", ""))) is None  # type: ignore[union-attr]
        or status.get("runningCount", 0) != 0  # type: ignore[union-attr]
        or status.get("succeededCount", 0) + status.get("failedCount", 0) != task_count  # type: ignore[union-attr]
        or str(task.get("timeoutSeconds")) != "7200"
        or containers[0].get("resources", {}).get("limits") != {"cpu": "4", "memory": "16Gi"}
        or sorted(containers[0].get("env", []), key=lambda row: row.get("name")) != expected_env
        or containers[0].get("volumeMounts", []) != []
        or task.get("volumes", []) != [] or task.get("vpcAccess", {}) != {}
    ):
        _fail("terminal execution contract differs")
    success = (
        conditions[0] == "True"
        and status.get("succeededCount", 0) == task_count  # type: ignore[union-attr]
        and status.get("failedCount", 0) == 0  # type: ignore[union-attr]
    )
    body: dict[str, object] = {
        "schema_version": SCHEMA, "lane": lane, "execution": execution,
        "job": job, "image": image, "code_sha": code_sha,
        "service_account": service_account,
        "task_count": task_count, "parallelism": parallelism,
        "max_retries": 0, "command": ["python"], "args": list(expected_args),
        "working_dir": "/app (immutable image default)",
        "completion_time": status["completionTime"],  # type: ignore[index]
        "completed_condition": conditions[0],
        "succeeded_count": status.get("succeededCount", 0),  # type: ignore[union-attr]
        "failed_count": status.get("failedCount", 0),  # type: ignore[union-attr]
        "running_count": status.get("runningCount", 0),  # type: ignore[union-attr]
        "terminal_success": success,
    }
    body["terminal_receipt_sha256"] = sha256(_canonical(body)).hexdigest()
    return body


def _write_equal(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    read_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    def equal_existing() -> bool:
        descriptor = os.open(path.name, read_flags, dir_fd=directory_fd)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                return False
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
            current = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
            return (
                before.st_dev == after.st_dev == current.st_dev
                and before.st_ino == after.st_ino == current.st_ino
                and b"".join(chunks) == raw
            )
        finally:
            os.close(descriptor)
    temporary_name: str | None = None
    try:
        try:
            if equal_existing():
                os.fsync(directory_fd)
                return
            _fail("terminal receipt collision differs")
        except FileNotFoundError:
            pass
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                _fail("terminal receipt collision differs")
            raise
        temporary_fd, temporary_name = tempfile.mkstemp(
            prefix=".r6-terminal.", dir=path.parent
        )
        os.fchmod(temporary_fd, 0o600)
        try:
            view = memoryview(raw)
            while view:
                written = os.write(temporary_fd, view)
                if written <= 0:
                    _fail("terminal receipt write did not progress")
                view = view[written:]
            os.fsync(temporary_fd)
        finally:
            os.close(temporary_fd)
        try:
            os.link(temporary_name, path.name, dst_dir_fd=directory_fd,
                    follow_symlinks=False)
        except FileExistsError:
            if not equal_existing():
                _fail("terminal receipt collision differs")
        os.fsync(directory_fd)
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            os.fsync(directory_fd)
        os.close(directory_fd)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--envelope", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--task-count", type=int, required=True)
    parser.add_argument("--parallelism", type=int, required=True)
    parser.add_argument("--expected-args-json", required=True)
    parser.add_argument("--require-success", action="store_true")
    args = parser.parse_args(argv)
    if (re.fullmatch(r".+@sha256:[0-9a-f]{64}", args.image) is None
            or re.fullmatch(r"[0-9a-f]{40}", args.code_sha) is None
            or re.fullmatch(r"lane-[ab]|repair-(?:[0-9]|[1-4][0-9]|5[0-3])", args.lane) is None):
        _fail("immutable image differs")
    envelope = json.loads(args.envelope.read_bytes())
    expected_args = json.loads(args.expected_args_json)
    if not isinstance(expected_args, list) or not all(
        isinstance(value, str) for value in expected_args
    ):
        _fail("expected args differ")
    receipt = build_receipt(
        envelope, lane=args.lane, execution=args.execution, job=args.job,
        image=args.image, code_sha=args.code_sha, service_account=args.service_account,
        task_count=args.task_count, parallelism=args.parallelism,
        expected_args=expected_args,
    )
    if args.require_success and receipt["terminal_success"] is not True:
        _fail("successful terminal lane is required for finish")
    _write_equal(args.receipt, _canonical(receipt))
    print(_canonical(receipt).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
