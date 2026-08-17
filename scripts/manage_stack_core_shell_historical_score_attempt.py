#!/usr/bin/env python3
"""Resolve the one-cell historical scorer under the narrow retry law."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Mapping, Sequence


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
RUN_ID = "20260816-stack-core-shell-historical-score-v1"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-historical-runs/"
    f"{RUN_ID}"
)
OUTPUT_URI = f"{PREFIX}/report.json"
JOB = "stack-shell-historical-score-v1"
RUNNER = "scripts/run_stack_core_shell_historical_score.py"
EXECUTION_PROTOCOL_SHA256 = (
    "ad3fe7e1045b61d4f64e21fee72c9f5d829fb7b2b4fb3854586e11641b458597"
)
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports/stack-core-shell-historical-runs" / RUN_ID


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(command), check=False, capture_output=True, text=True)


def _execution(execution: str) -> dict:
    result = _run((
        "gcloud", "run", "jobs", "executions", "describe", execution,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ))
    if result.returncode != 0:
        raise RuntimeError("historical-score execution query failed")
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("historical-score execution metadata differs")
    return value


def _job_executions() -> list[str]:
    result = _run((
        "gcloud", "run", "jobs", "executions", "list", "--job", JOB,
        "--project", PROJECT, "--region", REGION,
        "--format=value(metadata.name)",
    ))
    if result.returncode != 0:
        raise RuntimeError("historical-score execution list failed")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _object() -> dict | None:
    result = _run((
        "gcloud", "storage", "objects", "describe", OUTPUT_URI,
        "--project", PROJECT, "--format=json",
    ))
    if result.returncode == 0:
        value = json.loads(result.stdout)
        if not isinstance(value, dict) or \
                not str(value.get("generation", "")).isdigit() or \
                int(value.get("size", 0)) <= 0:
            raise RuntimeError("historical-score object metadata differs")
        return value
    message = f"{result.stdout}\n{result.stderr}".lower()
    if "404" in message and "not found" in message:
        return None
    raise RuntimeError("historical-score object query is ambiguous")


def _completed(metadata: Mapping) -> Mapping:
    rows = [
        row for row in metadata.get("status", {}).get("conditions", [])
        if row.get("type") == "Completed"
    ]
    if len(rows) != 1 or rows[0].get("status") not in {"True", "False"} or \
            not metadata.get("status", {}).get("completionTime"):
        raise RuntimeError("STACK_CORE_SHELL_HISTORICAL_ATTEMPT_NOT_TERMINAL")
    return rows[0]


def _validate_contract(metadata: Mapping, manifest: Mapping[str, str], execution: str) -> None:
    if metadata.get("metadata", {}).get("name") != execution or \
            not execution.startswith(JOB + "-"):
        raise RuntimeError("historical-score execution identity differs")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError("historical-score execution shape differs")
    container = containers[0]
    expected_args = [
        RUNNER, "--output-uri", OUTPUT_URI,
        "--lock-report-sha256", manifest.get("lock_report_sha256"),
        "--lock-completion-sha256", manifest.get("lock_completion_sha256"),
    ]
    env = {
        value.get("name"): str(value.get("value", ""))
        for value in container.get("env", [])
    }
    if container.get("image") != manifest.get("image") or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or env != {
                "CODE_SHA": manifest.get("code_sha"),
                "ANALYSIS_IMAGE": manifest.get("image"),
            } or container.get("resources", {}).get("limits") != {
                "cpu": "4", "memory": "16Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "7200" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError("historical-score execution contract differs")


def _validate_launch(out: Path) -> tuple[dict[str, str], str]:
    manifest = _manifest(out / "manifest.txt")
    row = (out / "executions.txt").read_text(encoding="utf-8").split()
    fixed = {
        "run_id": RUN_ID, "output_prefix": PREFIX, "output_uri": OUTPUT_URI,
        "execution_protocol_sha256": EXECUTION_PROTOCOL_SHA256,
        "tasks": "1", "parallelism": "1", "cpu": "4", "memory": "16Gi",
        "timeout_seconds": "7200", "max_retries": "0",
        "uses_realized_outcomes": "true", "actual_scores_queried": "true",
        "production_change_licensed": "false",
    }
    if len(row) != 3 or row[0] != JOB or row[2] != OUTPUT_URI or \
            any(manifest.get(key) != value for key, value in fixed.items()) or \
            not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", manifest.get("image", "")) or \
            not re.fullmatch(r"[0-9a-f]{64}", manifest.get("lock_report_sha256", "")) or \
            not re.fullmatch(
                r"[0-9a-f]{64}", manifest.get("lock_completion_sha256", ""),
            ):
        raise RuntimeError("historical-score launch receipt differs")
    return manifest, row[1]


def _resolution(
    out: Path, disposition: str, primary: str, replacement: str | None,
    accepted: str | None,
) -> dict:
    retry = "" if replacement is None else f"{JOB} {primary} {replacement} {OUTPUT_URI}\n"
    accepted_text = "" if accepted is None else f"{JOB} {accepted} {OUTPUT_URI}\n"
    (out / "retry-executions.txt").write_text(retry, encoding="utf-8")
    (out / "accepted-executions.txt").write_text(accepted_text, encoding="utf-8")
    payload = {
        "version": "stack-core-shell-historical-attempt-resolution-v1",
        "run_id": RUN_ID, "disposition": disposition,
        "primary_execution": primary, "replacement_execution": replacement,
        "accepted_execution": accepted, "task_max_retries": 0,
        "max_replacement_executions": 1,
        "uses_realized_outcomes": True, "actual_scores_queried": True,
        "report_content_inspected": False,
        "primary_execution_ledger_sha256": _sha(out / "executions.txt"),
        "retry_execution_ledger_sha256": _sha(out / "retry-executions.txt"),
        "accepted_execution_ledger_sha256": _sha(out / "accepted-executions.txt"),
    }
    _json(out / "attempt-resolution.json", payload)
    return payload


def prepare(out: Path = DEFAULT_OUT) -> dict:
    manifest, primary = _validate_launch(out)
    if (out / "attempt-resolution.json").exists():
        return validate(out)
    metadata = _execution(primary)
    _validate_contract(metadata, manifest, primary)
    condition = _completed(metadata)
    object_value = _object()
    _json(out / "primary-execution-metadata.json", metadata)
    _json(out / "primary-object-status.json", {
        "uri": OUTPUT_URI, "present": object_value is not None,
        "metadata_sha256": sha256(json.dumps(
            object_value, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest() if object_value is not None else None,
    })
    status = metadata["status"]
    if condition.get("status") == "True":
        if int(status.get("succeededCount") or 0) == 1 and \
                int(status.get("failedCount") or 0) == 0 and object_value is not None:
            return _resolution(out, "accepted-primary", primary, None, primary)
        return _resolution(out, "terminal-invalid-primary", primary, None, None)
    message = str(condition.get("message", "")).strip()
    literal_platform = bool(re.fullmatch(
        r"Internal error running task\.?", message, re.IGNORECASE,
    ))
    blocked = any(token in message.lower() for token in (
        "memory", "timeout", "signal", "sigkill", "solver", "cbc",
        "nonzero", "cancel",
    ))
    eligible = literal_platform and not blocked and object_value is None and \
        int(status.get("succeededCount") or 0) == 0 and \
        int(status.get("failedCount") or 0) == 1 and \
        int(status.get("cancelledCount") or 0) == 0
    if not eligible or _job_executions() != [primary]:
        return _resolution(out, "terminal-invalid-primary", primary, None, None)
    result = _run((
        "gcloud", "run", "jobs", "execute", JOB,
        "--project", PROJECT, "--region", REGION, "--async",
        "--format=value(metadata.name)",
    ))
    replacement = result.stdout.strip()
    if result.returncode != 0 or not replacement.startswith(JOB + "-") or \
            replacement == primary:
        raise RuntimeError("historical-score platform replacement failed")
    while True:
        retry_metadata = _execution(replacement)
        _validate_contract(retry_metadata, manifest, replacement)
        try:
            retry_condition = _completed(retry_metadata)
            break
        except RuntimeError as exc:
            if str(exc) != "STACK_CORE_SHELL_HISTORICAL_ATTEMPT_NOT_TERMINAL":
                raise
        print("STACK_CORE_SHELL_HISTORICAL_REPLACEMENT_RUNNING", replacement, flush=True)
        time.sleep(60)
    _json(out / "replacement-execution-metadata.json", retry_metadata)
    retry_status = retry_metadata["status"]
    success = retry_condition.get("status") == "True" and \
        int(retry_status.get("succeededCount") or 0) == 1 and \
        int(retry_status.get("failedCount") or 0) == 0 and \
        _object() is not None and _job_executions() == sorted([primary, replacement])
    return _resolution(
        out,
        "accepted-platform-replacement" if success else "terminal-invalid-replacement",
        primary, replacement, replacement if success else None,
    )


def validate(out: Path = DEFAULT_OUT) -> dict:
    _manifest_value, primary = _validate_launch(out)
    del _manifest_value
    required = [
        out / "primary-execution-metadata.json", out / "primary-object-status.json",
        out / "retry-executions.txt", out / "accepted-executions.txt",
        out / "attempt-resolution.json",
    ]
    if not all(path.is_file() for path in required):
        raise RuntimeError("historical-score attempt receipt is incomplete")
    value = json.loads((out / "attempt-resolution.json").read_text(encoding="utf-8"))
    allowed = {
        "accepted-primary", "accepted-platform-replacement",
        "terminal-invalid-primary", "terminal-invalid-replacement",
    }
    retry = (out / "retry-executions.txt").read_text(encoding="utf-8").split()
    accepted = (out / "accepted-executions.txt").read_text(encoding="utf-8").split()
    replacement = value.get("replacement_execution")
    accepted_execution = value.get("accepted_execution")
    if value.get("version") != "stack-core-shell-historical-attempt-resolution-v1" or \
            value.get("run_id") != RUN_ID or value.get("disposition") not in allowed or \
            value.get("primary_execution") != primary or \
            value.get("task_max_retries") != 0 or \
            value.get("max_replacement_executions") != 1 or \
            value.get("uses_realized_outcomes") is not True or \
            value.get("actual_scores_queried") is not True or \
            value.get("report_content_inspected") is not False or \
            value.get("primary_execution_ledger_sha256") != _sha(out / "executions.txt") or \
            value.get("retry_execution_ledger_sha256") != \
            _sha(out / "retry-executions.txt") or \
            value.get("accepted_execution_ledger_sha256") != \
            _sha(out / "accepted-executions.txt"):
        raise RuntimeError("historical-score attempt resolution differs")
    if replacement is None:
        if retry or value["disposition"] not in {"accepted-primary", "terminal-invalid-primary"}:
            raise RuntimeError("historical-score primary disposition differs")
    elif retry != [JOB, primary, replacement, OUTPUT_URI] or \
            not (out / "replacement-execution-metadata.json").is_file() or \
            value["disposition"] not in {
                "accepted-platform-replacement", "terminal-invalid-replacement",
            }:
        raise RuntimeError("historical-score replacement receipt differs")
    if value["disposition"].startswith("accepted-"):
        if accepted != [JOB, accepted_execution, OUTPUT_URI] or \
                accepted_execution not in {primary, replacement}:
            raise RuntimeError("historical-score accepted execution differs")
    elif accepted or accepted_execution is not None:
        raise RuntimeError("historical-score invalid attempt was accepted")
    print("STACK_CORE_SHELL_HISTORICAL_ATTEMPT_VALIDATED", value["disposition"])
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "validate"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    value = prepare(args.output_dir) if args.action == "prepare" else validate(args.output_dir)
    print("STACK_CORE_SHELL_HISTORICAL_ATTEMPT_RESULT", value["disposition"])


if __name__ == "__main__":
    main()
