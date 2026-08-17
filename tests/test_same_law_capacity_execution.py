from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pandas as pd

from nfl_dfs.research.same_law_capacity_generation import generation_schedule
from nfl_dfs.research.same_law_capacity_attempts import (
    OutputInventory,
    classify_primary_attempt,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_same_law_capacity_execution",
    ROOT / "scripts/validate_same_law_capacity_execution.py",
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)
CANARY_SPEC = importlib.util.spec_from_file_location(
    "validate_same_law_capacity_canary",
    ROOT / "scripts/validate_same_law_capacity_canary.py",
)
assert CANARY_SPEC and CANARY_SPEC.loader
canary = importlib.util.module_from_spec(CANARY_SPEC)
CANARY_SPEC.loader.exec_module(canary)


def _cell():
    ledger = pd.read_csv(
        ROOT / "reports/2026-08-17-same-law-capacity-curve-seeds.csv"
    )
    return generation_schedule(ledger)[0]


def _execution(*, terminal: bool = True):
    cell = _cell()
    status = {
        "conditions": [{
            "type": "Completed",
            "status": "True" if terminal else "Unknown",
        }],
    }
    if terminal:
        status["succeededCount"] = 1
    return cell, {
        "metadata": {
            "name": "capacity-r05-2023-v1-abcde",
            "labels": {"run.googleapis.com/job": cell.job},
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": cell.image,
                    "command": list(cell.command),
                    "args": list(cell.args),
                    "env": [
                        {"name": name, "value": value}
                        for name, value in cell.environment
                    ],
                    "resources": {"limits": {
                        "cpu": str(cell.cpu), "memory": cell.memory,
                    }},
                }],
                "maxRetries": cell.max_retries,
                "timeoutSeconds": str(cell.timeout_seconds),
                "serviceAccountName": validator.SERVICE_ACCOUNT,
            }},
        },
        "status": status,
    }


def test_capacity_execution_accepts_exact_terminal_cell():
    cell, execution = _execution()

    assert validator.execution_failures(
        execution,
        cell=cell,
        execution_name="capacity-r05-2023-v1-abcde",
    ) == []


def test_capacity_execution_accepts_exact_nonterminal_canary_spec():
    cell, execution = _execution(terminal=False)

    assert validator.execution_failures(
        execution,
        cell=cell,
        execution_name="capacity-r05-2023-v1-abcde",
        require_success=False,
    ) == []


def test_capacity_execution_rejects_environment_or_resource_drift():
    cell, execution = _execution()
    changed = deepcopy(execution)
    changed["spec"]["template"]["spec"]["containers"][0]["env"][0][
        "value"
    ] = "wrong-project"
    changed["spec"]["template"]["spec"]["containers"][0]["resources"][
        "limits"
    ]["memory"] = "16Gi"

    failures = validator.execution_failures(
        changed,
        cell=cell,
        execution_name="capacity-r05-2023-v1-abcde",
    )

    assert "execution environment differs from frozen cell" in failures
    assert "execution resource shape differs" in failures


def test_capacity_execution_rejects_task_retry_or_extra_environment():
    cell, execution = _execution()
    execution["status"]["retriedCount"] = 1
    execution["spec"]["template"]["spec"]["containers"][0]["env"].append(
        {"name": "UNFROZEN", "value": "1"}
    )

    failures = validator.execution_failures(
        execution,
        cell=cell,
        execution_name="capacity-r05-2023-v1-abcde",
    )

    assert "execution task retry count differs from zero" in failures
    assert "execution environment differs from frozen cell" in failures


def test_capacity_canary_metadata_requires_all_18_positive_weeks():
    rows = [
        {"season": 2023, "week": week, "row_count": 240 + week}
        for week in range(1, 19)
    ]

    assert canary.validate_week_counts(rows, label="candidate") == rows

    rows[-1]["row_count"] = 0
    try:
        canary.validate_week_counts(rows, label="candidate")
    except ValueError as exc:
        assert "population differs" in str(exc)
    else:
        raise AssertionError("zero-row canary week was accepted")


def test_capacity_canary_artifacts_are_metadata_only_complete_grid():
    panel = "20260817-same-law-capacity-r05-v1"
    rows = [{
        "name": f"cand_scores/{panel}/2023_w{week}_{week:012x}.npz",
        "generation": str(1000 + week),
        "size": 100_000 + week,
        "md5_hash": f"md5-{week}",
        "crc32c": f"crc-{week}",
    } for week in range(1, 19)]

    result = canary.validate_artifact_inventory(rows, panel_run_id=panel)

    assert [row["week"] for row in result] == list(range(1, 19))
    assert all("players" not in row and "score" not in row for row in result)


def _terminal_attempt(status: str, message: str = ""):
    result = {
        "status": {
            "conditions": [{
                "type": "Completed", "status": status, "message": message,
            }],
            "completionTime": "2026-08-17T00:00:00Z",
        },
    }
    if status == "True":
        result["status"]["succeededCount"] = 1
    else:
        result["status"]["failedCount"] = 1
    return result


def test_capacity_attempt_accepts_only_complete_success_population():
    complete = OutputInventory(4500, 1800, 12960, 18)
    incomplete = OutputInventory(4500, 1800, 12960, 17)

    accepted = classify_primary_attempt(
        _terminal_attempt("True"), complete, is_canary=False,
    )
    rejected = classify_primary_attempt(
        _terminal_attempt("True"), incomplete, is_canary=False,
    )

    assert accepted["eligibility"] == "primary-success"
    assert rejected["eligibility"] == "terminal-invalid-success-contract"
    assert not accepted["replacement_licensed"]


def test_capacity_attempt_retries_only_literal_zero_output_platform_error():
    empty = OutputInventory(0, 0, 0, 0)
    execution = _terminal_attempt("False", "Internal error running task")

    eligible = classify_primary_attempt(execution, empty, is_canary=False)
    canary = classify_primary_attempt(execution, empty, is_canary=True)

    assert eligible["eligibility"] == "eligible-platform-replacement"
    assert eligible["replacement_licensed"]
    assert canary["eligibility"] == "terminal-invalid-primary"
    assert not canary["replacement_licensed"]


def test_capacity_attempt_rejects_substantive_ambiguous_or_partial_failures():
    empty = OutputInventory(0, 0, 0, 0)
    partial = OutputInventory(1, 0, 0, 0)
    messages = (
        "Internal error running task after timeout",
        "The container exceeded the configured memory limit",
        "solver failed",
        "something went wrong",
    )

    for message in messages:
        result = classify_primary_attempt(
            _terminal_attempt("False", message), empty, is_canary=False,
        )
        assert result["eligibility"] == "terminal-invalid-primary"
        assert not result["replacement_licensed"]
    partial_result = classify_primary_attempt(
        _terminal_attempt("False", "Internal error running task"),
        partial,
        is_canary=False,
    )
    assert partial_result["eligibility"] == "terminal-invalid-primary"
