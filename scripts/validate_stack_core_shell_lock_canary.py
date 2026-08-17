#!/usr/bin/env python3
"""Pure validator for the first real production-lock grid execution."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re


RUN_ID = "20260816-stack-core-shell-production-lock-v1"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-lock-runs/"
    f"{RUN_ID}"
)
RUNNER = "scripts/run_stack_core_shell_production_lock.py"
EXECUTION_PROTOCOL_SHA256 = (
    "71063a42c21a1f6bff4d881af6e60bb10b1860d87d72c62332beb2ec83b27e7f"
)
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"


def _manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def validate(
    manifest_path: Path,
    ledger_path: Path,
    metadata_path: Path,
    object_path: Path | None,
    validator_path: Path,
    completion_path: Path,
) -> bool:
    manifest = _manifest(manifest_path)
    row = ledger_path.read_text(encoding="utf-8").split()
    if len(row) != 5:
        raise ValueError("stack-core/shell lock canary ledger differs")
    season, week, job, execution, uri = row
    if season != "2023" or week != "1" or \
            job != "stack-shell-lock-s2023-w1-v1" or \
            uri != f"{PREFIX}/slate-2023-1.json" or \
            manifest.get("run_id") != RUN_ID or \
            manifest.get("output_prefix") != PREFIX or \
            manifest.get("execution_protocol_sha256") != \
            EXECUTION_PROTOCOL_SHA256 or \
            manifest.get("canary_validator_sha256") != sha256(
                validator_path.read_bytes()
            ).hexdigest() or \
            not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
            not re.fullmatch(
                r".+@sha256:[0-9a-f]{64}", manifest.get("image", ""),
            ) or not re.fullmatch(
                r"[0-9a-f]{64}", manifest.get("scorefree_report_sha256", ""),
            ) or not re.fullmatch(
                r"[0-9a-f]{64}", manifest.get("scorefree_completion_sha256", ""),
            ):
        raise ValueError("stack-core/shell lock canary manifest differs")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("metadata", {}).get("name") != execution:
        raise ValueError("stack-core/shell lock canary execution differs")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise ValueError("stack-core/shell lock canary shape differs")
    container = containers[0]
    expected_args = [
        RUNNER, "--season", season, "--week", week, "--output-uri", uri,
        "--scorefree-report-sha256", manifest["scorefree_report_sha256"],
        "--scorefree-completion-sha256", manifest["scorefree_completion_sha256"],
    ]
    env = {
        value.get("name"): str(value.get("value", ""))
        for value in container.get("env", [])
    }
    if container.get("image") != manifest["image"] or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or env != {
                "CODE_SHA": manifest["code_sha"],
                "ANALYSIS_IMAGE": manifest["image"],
            } or container.get("resources", {}).get("limits") != {
                "cpu": "4", "memory": "16Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "7200" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise ValueError("stack-core/shell lock canary contract differs")
    status = metadata.get("status", {})
    completed = [
        value for value in status.get("conditions", [])
        if value.get("type") == "Completed"
    ]
    object_present = object_path is not None and object_path.is_file()
    success = bool(
        len(completed) == 1
        and completed[0].get("status") == "True"
        and int(status.get("succeededCount") or 0) == 1
        and int(status.get("failedCount") or 0) == 0
        and status.get("completionTime")
        and object_present
    )
    object_hash = "absent"
    if object_present:
        value = json.loads(object_path.read_text(encoding="utf-8"))
        if not str(value.get("generation", "")).isdigit() or \
                int(value.get("size", 0)) <= 0:
            success = False
        object_hash = sha256(object_path.read_bytes()).hexdigest()
    completion_path.write_text("\n".join([
        f"validated_at={status.get('completionTime', '')}",
        f"status={'True' if success else 'False'}",
        f"disposition={'real-path-canary-passes' if success else 'real-path-canary-fails'}",
        f"execution={execution}", "cell=2023-1",
        "remaining_cells_released=false", "object_content_inspected=false",
        "actual_scores_queried=false", "treatment_constructed=true",
        "uses_realized_outcomes=false",
        f"execution_metadata_sha256={sha256(metadata_path.read_bytes()).hexdigest()}",
        f"object_metadata_sha256={object_hash}",
    ]) + "\n", encoding="utf-8")
    return success


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--object", type=Path)
    parser.add_argument("--validator", type=Path, required=True)
    parser.add_argument("--completion", type=Path, required=True)
    args = parser.parse_args()
    if not validate(
        args.manifest, args.ledger, args.metadata, args.object,
        args.validator, args.completion,
    ):
        raise SystemExit("STACK_CORE_SHELL_LOCK_REAL_PATH_CANARY_FAILED")


if __name__ == "__main__":
    main()
