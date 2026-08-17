#!/usr/bin/env python3
"""Resolve and validate bounded support-census Cloud Run attempts."""

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
RUN_ID = "20260816-stack-core-shell-control-support-census-v1"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-support-runs/"
    f"{RUN_ID}"
)
JOB_PATTERN = "stack-shell-support-s{season}-w{week}-v1"
RUNNER = "scripts/run_stack_core_shell_support_census.py"
TIMEOUT = "7200"
EXECUTION_PROTOCOL_SHA256 = (
    "d2e902611e070ef67c191dffd35d86fd0c81365126eb86dcae7b9640aede1cc3"
)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports/stack-core-shell-support-runs" / RUN_ID
GRID = tuple(
    (season, week)
    for season in (2023, 2024, 2025)
    for week in range(1, 19)
)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _read_manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def _read_ledger(path: Path, fields: int) -> list[list[str]]:
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines()]
    if any(len(row) != fields for row in rows):
        raise RuntimeError(f"stack-core/shell attempt ledger differs: {path.name}")
    return rows


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command), check=False, capture_output=True, text=True,
    )


def _gcloud_json(*args: str) -> dict:
    result = _run(("gcloud", *args, "--format=json"))
    if result.returncode != 0:
        raise RuntimeError(
            "gcloud query failed: " + (result.stderr.strip() or result.stdout.strip())
        )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("gcloud JSON response differs")
    return value


def _execution_metadata(execution: str) -> dict:
    return _gcloud_json(
        "run", "jobs", "executions", "describe", execution,
        "--project", PROJECT, "--region", REGION,
    )


def _job_executions(job: str) -> list[str]:
    result = _run((
        "gcloud", "run", "jobs", "executions", "list", "--job", job,
        "--project", PROJECT, "--region", REGION,
        "--format=value(metadata.name)",
    ))
    if result.returncode != 0:
        raise RuntimeError("stack-core/shell job execution query failed")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _object_metadata(uri: str) -> dict | None:
    result = _run((
        "gcloud", "storage", "objects", "describe", uri,
        "--project", PROJECT, "--format=json",
    ))
    if result.returncode == 0:
        value = json.loads(result.stdout)
        if not isinstance(value, dict) or \
                not str(value.get("generation", "")).isdigit() or \
                int(value.get("size", 0)) <= 0:
            raise RuntimeError("stack-core/shell object metadata differs")
        return value
    message = f"{result.stdout}\n{result.stderr}".lower()
    if "not found" in message and "404" in message:
        return None
    raise RuntimeError("stack-core/shell object query is ambiguous")


def _completed(metadata: Mapping) -> Mapping:
    rows = [
        row for row in metadata.get("status", {}).get("conditions", [])
        if row.get("type") == "Completed"
    ]
    if len(rows) != 1 or rows[0].get("status") not in {"True", "False"} or \
            not metadata.get("status", {}).get("completionTime"):
        raise RuntimeError("STACK_CORE_SHELL_SUPPORT_ATTEMPT_NOT_TERMINAL")
    return rows[0]


def _validate_contract(
    metadata: Mapping,
    manifest: Mapping[str, str],
    row: Sequence[str],
) -> None:
    season, week, job, execution, uri = row
    if metadata.get("metadata", {}).get("name") != execution:
        raise RuntimeError("stack-core/shell execution identity differs")
    expected_job = JOB_PATTERN.format(season=season, week=week)
    expected_uri = f"{PREFIX}/slate-{season}-{week}.json"
    if job != expected_job or not execution.startswith(job + "-") or uri != expected_uri:
        raise RuntimeError("stack-core/shell attempt ledger identity differs")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError("stack-core/shell execution shape differs")
    container = containers[0]
    expected_args = [
        RUNNER, "--season", season, "--week", week, "--output-uri", uri,
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
            str(task.get("timeoutSeconds")) != TIMEOUT or \
            task.get("serviceAccountName") != \
            "817589974517-compute@developer.gserviceaccount.com":
        raise RuntimeError("stack-core/shell execution contract differs")


def _validate_launch_receipts(out: Path) -> tuple[dict[str, str], list[list[str]]]:
    manifest_path = out / "manifest.txt"
    primary_path = out / "executions.txt"
    canary_path = out / "canary-completion.txt"
    release_path = out / "grid-release.txt"
    if not all(path.is_file() for path in (
        manifest_path, primary_path, canary_path, release_path,
    )):
        raise RuntimeError("stack-core/shell launch receipt is incomplete")
    manifest = _read_manifest(manifest_path)
    fixed = {
        "run_id": RUN_ID,
        "output_prefix": PREFIX,
        "execution_protocol_sha256": EXECUTION_PROTOCOL_SHA256,
        "cpu": "4",
        "memory": "16Gi",
        "timeout_seconds": TIMEOUT,
        "max_retries": "0",
        "uses_realized_outcomes": "false",
        "effect_fields_inspected": "false",
        "treatment_constructed": "false",
        "production_change_licensed": "false",
        "historical_scoring_licensed": "false",
    }
    if any(manifest.get(key) != value for key, value in fixed.items()) or \
            not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
            not re.fullmatch(
                r".+@sha256:[0-9a-f]{64}", manifest.get("image", ""),
            ):
        raise RuntimeError("stack-core/shell attempt manifest differs")
    primary = _read_ledger(primary_path, 5)
    if len(primary) != 54 or \
            {(int(row[0]), int(row[1])) for row in primary} != set(GRID) or \
            len({row[3] for row in primary}) != 54:
        raise RuntimeError("stack-core/shell primary population differs")
    canary = _read_manifest(canary_path)
    release = _read_manifest(release_path)
    if canary.get("status") != "True" or \
            canary.get("disposition") != "real-path-canary-passes" or \
            canary.get("cell") != "2023-1" or \
            canary.get("remaining_cells_released") != "false" or \
            canary.get("object_content_inspected") != "false" or \
            canary.get("effect_fields_inspected") != "false" or \
            canary.get("treatment_constructed") != "false" or \
            release.get("primary_executions") != "54" or \
            release.get("released_after_canary") != "53" or \
            release.get("canary_completion_sha256") != _sha(canary_path):
        raise RuntimeError("stack-core/shell canary/grid receipt differs")
    return manifest, primary


def _classification_paths(out: Path) -> dict[str, Path]:
    return {
        "classification": out / "primary-attempt-classification.json",
        "metadata": out / "primary-execution-metadata",
        "objects": out / "primary-object-status.json",
        "retries": out / "retry-executions.txt",
        "pending_retries": out / "retry-executions.pending.txt",
        "accepted": out / "accepted-executions.txt",
        "resolution": out / "attempt-resolution.json",
    }


def _classify(out: Path, manifest: Mapping[str, str], primary: list[list[str]]) -> dict:
    paths = _classification_paths(out)
    if paths["classification"].exists():
        return json.loads(paths["classification"].read_text(encoding="utf-8"))
    if paths["metadata"].exists() or paths["objects"].exists():
        raise RuntimeError("partial stack-core/shell classification exists")
    pending = out / ".primary-execution-metadata.pending"
    pending.mkdir()
    cells = []
    object_status = []
    eligible = []
    ineligible = []
    for row in primary:
        season, week, job, execution, uri = row
        metadata = _execution_metadata(execution)
        _validate_contract(metadata, manifest, row)
        condition = _completed(metadata)
        object_value = _object_metadata(uri)
        object_present = object_value is not None
        _write_json(pending / f"season-{season}-week-{week}.json", metadata)
        object_status.append({
            "season": int(season), "week": int(week), "uri": uri,
            "present": object_present,
            "metadata_sha256": (
                sha256(json.dumps(
                    object_value, sort_keys=True, separators=(",", ":"),
                ).encode()).hexdigest() if object_value is not None else None
            ),
        })
        status = metadata["status"]
        message = str(condition.get("message", ""))
        disposition = "primary-success"
        if condition["status"] == "True":
            if int(status.get("succeededCount") or 0) != 1 or \
                    int(status.get("failedCount") or 0) != 0 or not object_present:
                disposition = "ineligible-success-contract-or-object"
                ineligible.append((int(season), int(week)))
        else:
            literal_platform = bool(re.fullmatch(
                r"Internal error running task\.?", message.strip(), re.IGNORECASE,
            ))
            blocked_text = any(token in message.lower() for token in (
                "configured memory limit", "timeout", "signal", "sigkill",
                "solver", "cbc", "nonzero exit", "cancel",
            ))
            if literal_platform and not blocked_text and \
                    int(status.get("succeededCount") or 0) == 0 and \
                    int(status.get("failedCount") or 0) == 1 and \
                    int(status.get("cancelledCount") or 0) == 0 and \
                    not object_present:
                disposition = "eligible-platform-replacement"
                eligible.append((int(season), int(week)))
            else:
                disposition = "ineligible-primary-failure"
                ineligible.append((int(season), int(week)))
        cells.append({
            "season": int(season), "week": int(week), "job": job,
            "primary_execution": execution, "uri": uri,
            "status": condition["status"],
            "reason": str(condition.get("reason", "")),
            "message": message,
            "completion_time": status["completionTime"],
            "object_present": object_present,
            "eligibility": disposition,
        })
    disposition = (
        "terminal-invalid-primary" if ineligible else
        "replacement-required" if eligible else "all-primary-success"
    )
    payload = {
        "version": "stack-core-shell-primary-attempt-classification-v1",
        "run_id": RUN_ID,
        "execution_protocol_sha256": EXECUTION_PROTOCOL_SHA256,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "treatment_constructed": False,
        "task_max_retries": 0,
        "max_replacement_executions_per_cell": 1,
        "primary_executions": 54,
        "eligible_replacements": len(eligible),
        "ineligible_failures": len(ineligible),
        "disposition": disposition,
        "primary_execution_ledger_sha256": _sha(out / "executions.txt"),
        "canary_completion_sha256": _sha(out / "canary-completion.txt"),
        "grid_release_sha256": _sha(out / "grid-release.txt"),
        "cells": cells,
    }
    pending.rename(paths["metadata"])
    _write_json(paths["objects"], object_status)
    _write_json(paths["classification"], payload)
    return payload


def _write_resolution(
    out: Path,
    classification: Mapping,
    disposition: str,
    primary: Sequence[Sequence[str]],
    retries: Sequence[Sequence[str]],
    accepted: Sequence[Sequence[str]],
) -> dict:
    paths = _classification_paths(out)
    retry_text = "".join(" ".join(row) + "\n" for row in retries)
    accepted_text = "".join(" ".join(row) + "\n" for row in accepted)
    paths["retries"].write_text(retry_text, encoding="utf-8")
    if accepted:
        paths["accepted"].write_text(accepted_text, encoding="utf-8")
    payload = {
        "version": "stack-core-shell-attempt-resolution-v1",
        "run_id": RUN_ID,
        "disposition": disposition,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "treatment_constructed": False,
        "task_max_retries": 0,
        "max_replacement_executions_per_cell": 1,
        "primary_executions": len(primary),
        "retry_executions": len(retries),
        "accepted_executions": len(accepted),
        "classification_sha256": _sha(paths["classification"]),
        "primary_execution_ledger_sha256": _sha(out / "executions.txt"),
        "retry_execution_ledger_sha256": _sha(paths["retries"]),
        "accepted_execution_ledger_sha256": (
            _sha(paths["accepted"]) if accepted else None
        ),
    }
    _write_json(paths["resolution"], payload)
    return payload


def prepare(out: Path) -> dict:
    manifest, primary = _validate_launch_receipts(out)
    paths = _classification_paths(out)
    if paths["resolution"].exists():
        return validate(out)
    classification = _classify(out, manifest, primary)
    if classification["disposition"] == "terminal-invalid-primary":
        result = _write_resolution(
            out, classification, "terminal-invalid-primary", primary, [], [],
        )
        raise RuntimeError(
            "STACK_CORE_SHELL_SUPPORT_PRIMARY_TERMINALLY_INVALID "
            + json.dumps(result, sort_keys=True)
        )
    if classification["disposition"] == "all-primary-success":
        return _write_resolution(
            out, classification, "accepted-primary-population",
            primary, [], primary,
        )
    if classification["disposition"] != "replacement-required":
        raise RuntimeError("stack-core/shell primary disposition differs")

    eligible = {
        (str(row["season"]), str(row["week"])): row
        for row in classification["cells"]
        if row["eligibility"] == "eligible-platform-replacement"
    }
    pending_path = paths["pending_retries"]
    if paths["retries"].exists():
        retries = _read_ledger(paths["retries"], 6)
    else:
        if not pending_path.exists():
            pending_path.touch()
        retries = _read_ledger(pending_path, 6)
        retry_by_cell = {(row[0], row[1]): row for row in retries}
        for row in primary:
            season, week, job, primary_execution, uri = row
            cell = (season, week)
            if cell not in eligible:
                continue
            existing = retry_by_cell.get(cell)
            if existing is not None:
                if existing[:4] != [season, week, job, primary_execution] or \
                        existing[5] != uri or _job_executions(job) != sorted([
                            primary_execution, existing[4],
                        ]):
                    raise RuntimeError("stack-core/shell pending retry differs")
                continue
            if _job_executions(job) != [primary_execution] or \
                    _object_metadata(uri) is not None:
                raise RuntimeError("stack-core/shell replacement precondition differs")
            result = _run((
                "gcloud", "run", "jobs", "execute", job,
                "--project", PROJECT, "--region", REGION, "--async",
                "--format=value(metadata.name)",
            ))
            replacement = result.stdout.strip()
            if result.returncode != 0 or not replacement.startswith(job + "-") or \
                    replacement == primary_execution:
                raise RuntimeError("stack-core/shell replacement launch failed")
            retry_row = [
                season, week, job, primary_execution, replacement, uri,
            ]
            with pending_path.open("a", encoding="utf-8") as handle:
                handle.write(" ".join(retry_row) + "\n")
                handle.flush()
            retries.append(retry_row)
            print(
                "STACK_CORE_SHELL_PLATFORM_REPLACEMENT_LAUNCHED",
                season, week, replacement, flush=True,
            )
        if len(retries) != len(eligible):
            raise RuntimeError("stack-core/shell replacement population differs")
        pending_path.rename(paths["retries"])

    while True:
        running = []
        terminal = {}
        for season, week, job, primary_execution, replacement, uri in retries:
            metadata = _execution_metadata(replacement)
            _validate_contract(
                metadata, manifest, [season, week, job, replacement, uri],
            )
            try:
                condition = _completed(metadata)
            except RuntimeError as exc:
                if str(exc) != "STACK_CORE_SHELL_SUPPORT_ATTEMPT_NOT_TERMINAL":
                    raise
                running.append(replacement)
                continue
            terminal[replacement] = (metadata, condition)
        print(
            "STACK_CORE_SHELL_REPLACEMENT_STATUS",
            f"running={len(running)}", flush=True,
        )
        if not running:
            break
        time.sleep(60)

    for season, week, job, primary_execution, replacement, uri in retries:
        metadata, condition = terminal[replacement]
        status = metadata["status"]
        if condition["status"] != "True" or \
                int(status.get("succeededCount") or 0) != 1 or \
                int(status.get("failedCount") or 0) != 0 or \
                _object_metadata(uri) is None or \
                _job_executions(job) != sorted([primary_execution, replacement]):
            return _write_resolution(
                out, classification, "terminal-invalid-replacement",
                primary, retries, [],
            )
    retry_by_cell = {(row[0], row[1]): row for row in retries}
    accepted = []
    for row in primary:
        replacement = retry_by_cell.get((row[0], row[1]))
        accepted.append(
            [row[0], row[1], row[2], replacement[4], row[4]]
            if replacement else list(row)
        )
    return _write_resolution(
        out, classification, "accepted-population-with-platform-replacements",
        primary, retries, accepted,
    )


def validate(out: Path) -> dict:
    manifest, primary = _validate_launch_receipts(out)
    del manifest
    paths = _classification_paths(out)
    if not all(paths[name].is_file() for name in (
        "classification", "objects", "retries", "resolution",
    )) or not paths["metadata"].is_dir():
        raise RuntimeError("stack-core/shell attempt receipt is incomplete")
    classification = json.loads(paths["classification"].read_text(encoding="utf-8"))
    resolution = json.loads(paths["resolution"].read_text(encoding="utf-8"))
    retries = _read_ledger(paths["retries"], 6)
    accepted = (
        _read_ledger(paths["accepted"], 5) if paths["accepted"].is_file() else []
    )
    common = {
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "treatment_constructed": False,
        "task_max_retries": 0,
        "max_replacement_executions_per_cell": 1,
    }
    if classification.get("version") != \
            "stack-core-shell-primary-attempt-classification-v1" or any(
                classification.get(key) != value for key, value in common.items()
            ) or classification.get("execution_protocol_sha256") != \
            EXECUTION_PROTOCOL_SHA256 or \
            classification.get("primary_executions") != 54 or \
            classification.get("primary_execution_ledger_sha256") != \
            _sha(out / "executions.txt") or \
            classification.get("canary_completion_sha256") != \
            _sha(out / "canary-completion.txt") or \
            classification.get("grid_release_sha256") != \
            _sha(out / "grid-release.txt"):
        raise RuntimeError("stack-core/shell classification receipt differs")
    if resolution.get("version") != "stack-core-shell-attempt-resolution-v1" or \
            any(resolution.get(key) != value for key, value in common.items()) or \
            resolution.get("classification_sha256") != _sha(paths["classification"]) or \
            resolution.get("primary_execution_ledger_sha256") != \
            _sha(out / "executions.txt") or \
            resolution.get("retry_execution_ledger_sha256") != \
            _sha(paths["retries"]):
        raise RuntimeError("stack-core/shell resolution receipt differs")
    allowed = {
        "accepted-primary-population",
        "accepted-population-with-platform-replacements",
        "terminal-invalid-primary",
        "terminal-invalid-replacement",
    }
    disposition = resolution.get("disposition")
    if disposition not in allowed or resolution.get("primary_executions") != 54 or \
            resolution.get("retry_executions") != len(retries) or \
            resolution.get("accepted_executions") != len(accepted):
        raise RuntimeError("stack-core/shell resolution population differs")
    if disposition.startswith("accepted-"):
        if len(accepted) != 54 or \
                {(int(row[0]), int(row[1])) for row in accepted} != set(GRID) or \
                resolution.get("accepted_execution_ledger_sha256") != \
                _sha(paths["accepted"]):
            raise RuntimeError("stack-core/shell accepted population differs")
        primary_by_cell = {(row[0], row[1]): row for row in primary}
        retry_by_cell = {(row[0], row[1]): row for row in retries}
        for row in accepted:
            original = primary_by_cell[(row[0], row[1])]
            retry = retry_by_cell.get((row[0], row[1]))
            expected = [
                original[0], original[1], original[2],
                retry[4] if retry else original[3], original[4],
            ]
            if row != expected:
                raise RuntimeError("stack-core/shell accepted binding differs")
    cells = classification.get("cells")
    if not isinstance(cells, list) or len(cells) != 54 or \
            {(int(row["season"]), int(row["week"])) for row in cells} != set(GRID):
        raise RuntimeError("stack-core/shell classification cell grid differs")
    eligible = {
        (str(row["season"]), str(row["week"]))
        for row in cells
        if row.get("eligibility") == "eligible-platform-replacement"
    }
    ineligible = [
        row for row in cells
        if row.get("eligibility") not in {
            "primary-success", "eligible-platform-replacement",
        }
    ]
    retry_cells = {(row[0], row[1]) for row in retries}
    if len(retry_cells) != len(retries) or retry_cells != eligible or \
            classification.get("eligible_replacements") != len(eligible) or \
            classification.get("ineligible_failures") != len(ineligible):
        raise RuntimeError("stack-core/shell retry eligibility binding differs")
    expected_classification = (
        "terminal-invalid-primary" if ineligible else
        "replacement-required" if eligible else "all-primary-success"
    )
    if classification.get("disposition") != expected_classification:
        raise RuntimeError("stack-core/shell classification disposition differs")
    expected_resolution = (
        "terminal-invalid-primary" if ineligible else
        (
            "accepted-population-with-platform-replacements"
            if retries and disposition.startswith("accepted-") else
            "terminal-invalid-replacement"
            if retries else "accepted-primary-population"
        )
    )
    if disposition != expected_resolution:
        raise RuntimeError("stack-core/shell attempt resolution differs")
    object_status = json.loads(paths["objects"].read_text(encoding="utf-8"))
    if not isinstance(object_status, list) or len(object_status) != 54 or \
            {(int(row["season"]), int(row["week"])) for row in object_status} != \
            set(GRID):
        raise RuntimeError("stack-core/shell primary object-status grid differs")
    metadata = sorted(paths["metadata"].glob("season-*-week-*.json"))
    if len(metadata) != 54:
        raise RuntimeError("stack-core/shell primary metadata grid differs")
    print("STACK_CORE_SHELL_ATTEMPTS_VALIDATED", disposition)
    return resolution


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "validate"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    result = prepare(args.output_dir) if args.action == "prepare" else \
        validate(args.output_dir)
    print("STACK_CORE_SHELL_ATTEMPT_RESULT", result["disposition"])


if __name__ == "__main__":
    main()
