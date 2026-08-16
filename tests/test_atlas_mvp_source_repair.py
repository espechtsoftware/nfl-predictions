import copy
import json

import pytest

from nfl_dfs.research.atlas_mvp_source_repair import (
    EXPECTED_ARGS,
    EXPECTED_RESOURCES,
    EXPECTED_SERVICE_ACCOUNT,
    EXPECTED_TIMEOUT_SECONDS,
    ORIGINAL_ENVIRONMENT_SHA256,
    ORIGINAL_IMAGE,
    ORIGINAL_LINEUPS_TABLE,
    ORIGINAL_PANEL,
    REPAIR_LINEUPS_TABLE,
    REPAIR_PANEL,
    environment_differences,
    environment_sha256,
    repair_environment,
    validate_repair_execution,
)


def _source_receipt():
    path = (
        "reports/atlas-money-world-runs/"
        "20260815-atlas-current-money-worlds-v1/environment-receipts/"
        "r3-2025.json"
    )
    return json.load(open(path, encoding="utf-8"))


def _execution(env, name="repair-execution"):
    return {
        "metadata": {"name": name},
        "spec": {
            "parallelism": 1,
            "taskCount": 1,
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": EXPECTED_TIMEOUT_SECONDS,
                "serviceAccountName": EXPECTED_SERVICE_ACCOUNT,
                "containers": [{
                    "image": ORIGINAL_IMAGE,
                    "command": ["nfl-dfs"],
                    "args": list(EXPECTED_ARGS),
                    "env": [
                        {"name": key, "value": value}
                        for key, value in env.items()
                    ],
                    "resources": {"limits": EXPECTED_RESOURCES},
                }],
            }},
        },
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
            "failedCount": 0,
            "completionTime": "2026-08-16T12:00:00Z",
        },
    }


def test_repair_changes_only_two_destinations():
    receipt = _source_receipt()
    assert environment_sha256(receipt["values"]) == \
        ORIGINAL_ENVIRONMENT_SHA256 == receipt["sha256"]
    repaired = repair_environment(receipt["values"])
    assert environment_differences(receipt["values"], repaired) == {
        "PANEL_RUN_ID": (ORIGINAL_PANEL, REPAIR_PANEL),
        "REPLAY_LINEUPS_TABLE": (
            ORIGINAL_LINEUPS_TABLE, REPAIR_LINEUPS_TABLE,
        ),
    }


def test_repair_rejects_any_source_environment_drift():
    source = _source_receipt()["values"]
    drift = dict(source)
    drift["N_BOOM"] = "41"
    with pytest.raises(ValueError, match="environment differs"):
        repair_environment(drift)


def test_execution_receipt_is_strict():
    repaired = repair_environment(_source_receipt()["values"])
    receipt = _execution(repaired)
    result = validate_repair_execution(
        receipt, execution_name="repair-execution",
        expected_environment=repaired, terminal=True,
    )
    assert result["execution"] == "repair-execution"
    bad = copy.deepcopy(receipt)
    bad["spec"]["template"]["spec"]["containers"][0]["env"][0]["value"] += "x"
    with pytest.raises(ValueError, match="environment differs"):
        validate_repair_execution(
            bad, execution_name="repair-execution",
            expected_environment=repaired, terminal=True,
        )
