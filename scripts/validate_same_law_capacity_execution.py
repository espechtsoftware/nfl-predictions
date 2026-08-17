#!/usr/bin/env python3
"""Validate one immutable same-law capacity generation execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pandas as pd

from nfl_dfs.research.same_law_capacity_generation import (
    GenerationCell,
    SERVICE_ACCOUNT,
    generation_schedule,
)


SEED_LEDGER = Path(
    "reports/2026-08-17-same-law-capacity-curve-seeds.csv"
)


def _completed_status(execution: Mapping[str, Any]) -> str:
    for condition in execution.get("status", {}).get("conditions", []):
        if condition.get("type") == "Completed":
            return str(condition.get("status", ""))
    return ""


def _environment(container: Mapping[str, Any]) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    failures: list[str] = []
    for item in container.get("env", []):
        name = str(item.get("name", ""))
        if not name:
            failures.append("execution has an unnamed environment variable")
        elif name in values:
            failures.append(f"execution repeats environment variable {name}")
        elif "value" not in item:
            failures.append(f"execution environment variable {name} has no value")
        else:
            values[name] = str(item["value"])
    return values, failures


def execution_failures(
    execution: Mapping[str, Any],
    *,
    cell: GenerationCell,
    execution_name: str,
    require_success: bool = True,
) -> list[str]:
    """Return every execution-contract mismatch for one frozen cell."""
    failures: list[str] = []
    metadata = execution.get("metadata", {})
    if metadata.get("name") != execution_name:
        failures.append("execution name differs from ledger")
    if metadata.get("labels", {}).get("run.googleapis.com/job") != cell.job:
        failures.append("execution-owned job differs from schedule")

    spec = execution.get("spec", {})
    if int(spec.get("taskCount", -1)) != 1 or int(
        spec.get("parallelism", -1)
    ) != 1:
        failures.append("execution task count or parallelism differs")
    try:
        template = spec["template"]["spec"]
        containers = template["containers"]
        container = containers[0]
    except (KeyError, IndexError, TypeError):
        return failures + ["execution container specification is missing"]
    if len(containers) != 1:
        failures.append("execution does not contain exactly one container")
    if container.get("image") != cell.image:
        failures.append("execution image differs from frozen source image")
    if container.get("command") != list(cell.command):
        failures.append("execution command differs")
    if container.get("args") != list(cell.args):
        failures.append("execution arguments differ")
    limits = container.get("resources", {}).get("limits", {})
    if str(limits.get("cpu", "")) != str(cell.cpu) or \
            limits.get("memory") != cell.memory:
        failures.append("execution resource shape differs")
    if int(template.get("maxRetries", -1)) != cell.max_retries:
        failures.append("execution maxRetries differs")
    if str(template.get("timeoutSeconds", "")) != str(cell.timeout_seconds):
        failures.append("execution timeout differs")
    if template.get("serviceAccountName") != SERVICE_ACCOUNT:
        failures.append("execution service account differs")

    environment, env_failures = _environment(container)
    failures.extend(env_failures)
    if environment != dict(cell.environment):
        failures.append("execution environment differs from frozen cell")

    if require_success:
        status = execution.get("status", {})
        if _completed_status(execution) != "True":
            failures.append("execution is not a clean terminal success")
        if int(status.get("succeededCount", 0) or 0) != 1:
            failures.append("execution succeededCount differs from one")
        if int(status.get("failedCount", 0) or 0) != 0:
            failures.append("execution failedCount differs from zero")
        if int(status.get("retriedCount", 0) or 0) != 0:
            failures.append("execution task retry count differs from zero")
    return failures


def scheduled_cell(replicate: str, season: int) -> GenerationCell:
    ledger = pd.read_csv(SEED_LEDGER)
    matches = [
        cell for cell in generation_schedule(ledger)
        if cell.replicate == replicate and cell.season == season
    ]
    if len(matches) != 1:
        raise RuntimeError("capacity generation cell is not unique")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replicate", required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--allow-nonterminal", action="store_true")
    args = parser.parse_args()
    execution = json.load(sys.stdin)
    try:
        cell = scheduled_cell(args.replicate, args.season)
    except (RuntimeError, ValueError) as exc:
        print(f"CAPACITY_EXECUTION_FAILURE {exc}", file=sys.stderr)
        return 2
    failures = execution_failures(
        execution,
        cell=cell,
        execution_name=args.execution,
        require_success=not args.allow_nonterminal,
    )
    if failures:
        for failure in failures:
            print(f"CAPACITY_EXECUTION_FAILURE {failure}", file=sys.stderr)
        return 2
    print(
        "CAPACITY_EXECUTION_VERIFIED",
        cell.replicate,
        cell.season,
        args.execution,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
