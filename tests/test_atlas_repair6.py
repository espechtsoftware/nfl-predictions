from copy import deepcopy

import pytest

from nfl_dfs.research.atlas_repair6 import (
    EXPECTED_CELLS,
    REPAIR5_RUN_ID,
    classify_repair5_for_repair6,
)


PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    f"{REPAIR5_RUN_ID}"
)


def _fixture():
    terminal = []
    cells = []
    inventory = []
    failed_execution = "atlas-md-s2023-w7-r5-abcde"
    for season, week in EXPECTED_CELLS:
        failed = (season, week) == (2023, 7)
        job = f"atlas-md-s{season}-w{week}-r5"
        execution = failed_execution if failed else f"{job}-ok"
        uri = f"{PREFIX}/slate-{season}-{week}.json"
        terminal.append({
            "season": season, "week": week, "job": job,
            "execution": execution, "status": "False" if failed else "True",
            "reason": "NonZeroExitCode" if failed else "",
            "message": (
                "Task failed with exit code: 1 and message: container error"
                if failed else ""
            ),
            "completion_time": "2026-08-17T14:00:00Z",
        })
        cells.append({
            "season": season, "week": week, "job": job,
            "primary_execution": execution, "uri": uri,
            "status": "False" if failed else "True", "reason": "",
            "message": "", "completion_time": "2026-08-17T14:00:00Z",
            "object_present": not failed,
            "eligibility": (
                "ineligible-primary-failure" if failed else "primary-success"
            ),
        })
        if not failed:
            inventory.append(uri)
    census = {
        "version": "atlas-matched-diversity-repair5-terminal-census-v1",
        "protocol_sha256": (
            "94a792d80c4a908aed56034add9635478c738a29522554670c09360458561d0f"
        ),
        "run_id": REPAIR5_RUN_ID,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "scientific_result_valid": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "executions": 54, "terminal_succeeded": 53, "terminal_failed": 1,
        "output_objects_present": 53, "terminal": terminal,
    }
    classification = {
        "version": "atlas-repair5-primary-attempt-classification-v1",
        "run_id": REPAIR5_RUN_ID, "disposition": "terminal-invalid-primary",
        "uses_realized_outcomes": False, "effect_fields_inspected": False,
        "primary_executions": 54, "ineligible_failures": 1, "cells": cells,
    }
    resolution = {
        "version": "atlas-repair5-attempt-resolution-v1",
        "run_id": REPAIR5_RUN_ID, "disposition": "terminal-invalid-primary",
        "uses_realized_outcomes": False, "effect_fields_inspected": False,
        "primary_executions": 54, "retry_executions": 0,
        "accepted_executions": 0,
    }
    logs = {failed_execution: (
        "Traceback (most recent call last):\n"
        "  File \"runner.py\", line 1, in run\n"
        "RuntimeError: ATLAS world 2605 identity tiebreak is infeasible\n"
    )}
    return census, classification, resolution, inventory, logs


def _classify(values):
    census, classification, resolution, inventory, logs = values
    return classify_repair5_for_repair6(
        census=census, primary_classification=classification,
        attempt_resolution=resolution, object_inventory=inventory,
        error_logs=logs,
    )


def test_exact_tiebreak_failure_licenses_dual_canary_without_scores():
    result = _classify(_fixture())
    assert result["disposition"] == "repair6-dual-canary-licensed"
    assert result["repair6_launch_licensed"] is True
    assert result["repair5_successes"] == 53
    assert result["eligible_tiebreak_failures"] == [{
        **result["eligible_tiebreak_failures"][0],
        "season": 2023, "week": 7, "world": 2605,
    }]
    assert result["uses_realized_outcomes"] is False
    assert result["candidate_or_lineup_scores_read"] is False


def test_memory_or_other_failure_closes_repair6():
    values = list(_fixture())
    census = deepcopy(values[0])
    census["terminal"][6]["message"] += " configured memory limit"
    values[0] = census
    logs = dict(values[4])
    logs[next(iter(logs))] += "configured memory limit\n"
    values[4] = logs
    result = _classify(values)
    assert result["disposition"] == "repair6-closed-by-non-tiebreak-failure"
    assert result["repair6_launch_licensed"] is False
    assert len(result["ineligible_failures"]) == 1


def test_inventory_and_log_populations_fail_closed():
    values = list(_fixture())
    values[3] = [*values[3], "gs://unexpected/object"]
    with pytest.raises(ValueError, match="inventory"):
        _classify(values)

    values = list(_fixture())
    values[4] = {**values[4], "extra-execution": "error"}
    with pytest.raises(ValueError, match="log population"):
        _classify(values)
