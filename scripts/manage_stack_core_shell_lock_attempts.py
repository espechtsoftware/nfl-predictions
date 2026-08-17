#!/usr/bin/env python3
"""Apply the narrow platform-replacement ledger to production-lock jobs."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import re
from typing import Iterator, Mapping, Sequence

import manage_stack_core_shell_scorefree_attempts as engine


RUN_ID = "20260816-stack-core-shell-production-lock-v1"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-lock-runs/"
    f"{RUN_ID}"
)
JOB_PATTERN = "stack-shell-lock-s{season}-w{week}-v1"
RUNNER = "scripts/run_stack_core_shell_production_lock.py"
TIMEOUT = "7200"
EXECUTION_PROTOCOL_SHA256 = (
    "71063a42c21a1f6bff4d881af6e60bb10b1860d87d72c62332beb2ec83b27e7f"
)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "reports/stack-core-shell-lock-runs" / RUN_ID
GRID = engine.GRID


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _manifest(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def _ledger(path: Path) -> list[list[str]]:
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines()]
    if any(len(row) != 5 for row in rows):
        raise RuntimeError("stack-core/shell lock primary ledger differs")
    return rows


def _validate_contract(
    metadata: Mapping,
    manifest: Mapping[str, str],
    row: Sequence[str],
) -> None:
    season, week, job, execution, uri = row
    expected_job = JOB_PATTERN.format(season=season, week=week)
    if metadata.get("metadata", {}).get("name") != execution or \
            job != expected_job or not execution.startswith(job + "-") or \
            uri != f"{PREFIX}/slate-{season}-{week}.json":
        raise RuntimeError("stack-core/shell lock execution identity differs")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError("stack-core/shell lock execution shape differs")
    container = containers[0]
    expected_args = [
        RUNNER, "--season", season, "--week", week, "--output-uri", uri,
        "--scorefree-report-sha256", manifest.get("scorefree_report_sha256"),
        "--scorefree-completion-sha256",
        manifest.get("scorefree_completion_sha256"),
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
        raise RuntimeError("stack-core/shell lock execution contract differs")


def _validate_launch_receipts(
    out: Path,
) -> tuple[dict[str, str], list[list[str]]]:
    manifest_path = out / "manifest.txt"
    primary_path = out / "executions.txt"
    canary_path = out / "canary-completion.txt"
    release_path = out / "grid-release.txt"
    if not all(path.is_file() for path in (
        manifest_path, primary_path, canary_path, release_path,
    )):
        raise RuntimeError("stack-core/shell lock launch receipt incomplete")
    manifest = _manifest(manifest_path)
    fixed = {
        "run_id": RUN_ID, "output_prefix": PREFIX,
        "execution_protocol_sha256": EXECUTION_PROTOCOL_SHA256,
        "cpu": "4", "memory": "16Gi", "timeout_seconds": TIMEOUT,
        "max_retries": "0", "uses_realized_outcomes": "false",
        "effect_fields_inspected": "false", "treatment_constructed": "true",
        "production_change_licensed": "false",
        "historical_scoring_licensed": "true",
        "actual_scores_queried": "false",
    }
    if any(manifest.get(key) != value for key, value in fixed.items()) or \
            not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
            not re.fullmatch(
                r".+@sha256:[0-9a-f]{64}", manifest.get("image", ""),
            ) or not re.fullmatch(
                r"[0-9a-f]{64}", manifest.get("scorefree_report_sha256", ""),
            ) or not re.fullmatch(
                r"[0-9a-f]{64}", manifest.get("scorefree_completion_sha256", ""),
            ):
        raise RuntimeError("stack-core/shell lock attempt manifest differs")
    primary = _ledger(primary_path)
    if len(primary) != 54 or \
            {(int(row[0]), int(row[1])) for row in primary} != set(GRID) or \
            len({row[3] for row in primary}) != 54:
        raise RuntimeError("stack-core/shell lock primary grid differs")
    canary = _manifest(canary_path)
    release = _manifest(release_path)
    if canary.get("status") != "True" or \
            canary.get("disposition") != "real-path-canary-passes" or \
            canary.get("cell") != "2023-1" or \
            canary.get("remaining_cells_released") != "false" or \
            canary.get("object_content_inspected") != "false" or \
            canary.get("actual_scores_queried") != "false" or \
            canary.get("treatment_constructed") != "true" or \
            release.get("primary_executions") != "54" or \
            release.get("released_after_canary") != "53" or \
            release.get("canary_completion_sha256") != _sha(canary_path):
        raise RuntimeError("stack-core/shell lock canary/grid receipt differs")
    return manifest, primary


_ENGINE_FIELDS = (
    "RUN_ID", "PREFIX", "JOB_PATTERN", "RUNNER", "TIMEOUT",
    "EXECUTION_PROTOCOL_SHA256", "DEFAULT_OUT", "_validate_contract",
    "_validate_launch_receipts",
)
_BASE_FIELDS = _ENGINE_FIELDS + ("_classify", "_write_resolution", "validate")


@contextmanager
def _configured() -> Iterator[None]:
    """Temporarily specialize the already-tested score-free ledger engine."""

    engine_before = {name: getattr(engine, name) for name in _ENGINE_FIELDS}
    base_before = {name: getattr(engine.base, name) for name in _BASE_FIELDS}
    try:
        engine.RUN_ID = RUN_ID
        engine.PREFIX = PREFIX
        engine.JOB_PATTERN = JOB_PATTERN
        engine.RUNNER = RUNNER
        engine.TIMEOUT = TIMEOUT
        engine.EXECUTION_PROTOCOL_SHA256 = EXECUTION_PROTOCOL_SHA256
        engine.DEFAULT_OUT = DEFAULT_OUT
        engine._validate_contract = _validate_contract
        engine._validate_launch_receipts = _validate_launch_receipts
        engine._configure_base()
        yield
    finally:
        for name, value in engine_before.items():
            setattr(engine, name, value)
        for name, value in base_before.items():
            setattr(engine.base, name, value)


def prepare(out: Path) -> dict:
    with _configured():
        return engine.base.prepare(out)


def validate(out: Path) -> dict:
    with _configured():
        return engine.validate(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "validate"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    result = prepare(args.output_dir) if args.action == "prepare" else \
        validate(args.output_dir)
    print("STACK_CORE_SHELL_LOCK_ATTEMPT_RESULT", result["disposition"])


if __name__ == "__main__":
    main()
