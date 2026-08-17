from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys

import pytest

from nfl_dfs.research.atlas_repair6 import EXPECTED_CELLS, PROTOCOL_SHA256, REPAIR6_RUN_ID
from nfl_dfs.research.atlas_repair6_hybrid import (
    PROOF_PREFIX,
    REPAIR5_CODE_SHA,
    REPAIR5_IMAGE,
    REPAIR5_PREFIX,
    REPAIR6_PREFIX,
    SERVICE_ACCOUNT,
    validate_hybrid_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from finish_atlas_repair6_dual_canary import _validate_execution  # noqa: E402


R6_CODE = "a" * 40
R6_IMAGE = "registry/image@sha256:" + "b" * 64


def _execution(row, *, image, code, command):
    season, week, _source, _job, execution, uri = row
    return {
        "metadata": {"name": execution},
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1, "failedCount": 0, "cancelledCount": 0,
            "completionTime": "2026-08-17T12:00:00Z",
        },
        "spec": {"parallelism": 1, "taskCount": 1, "template": {"spec": {
            "containers": [{
                "image": image, "command": ["python"],
                "args": [
                    "-c", command, "--season", season, "--week", week,
                    "--output-uri", uri,
                ],
                "env": [
                    {"name": "CODE_SHA", "value": code},
                    {"name": "ANALYSIS_IMAGE", "value": image},
                ],
                "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
            }],
            "maxRetries": 0, "timeoutSeconds": "43200",
            "serviceAccountName": SERVICE_ACCOUNT,
        }}},
    }


def _object(uri):
    return {
        "uri": uri, "generation": "1", "bytes": 10,
        "sha256": "c" * 64, "md5_hash": "m", "crc32c": "c",
        "updated": "time",
    }


def _receipt():
    eligible = {(2023, 7)}
    primary = []
    accepted = []
    executions = {}
    objects = {}
    jobs = {}
    r5_inventory = []
    r6_inventory = []
    for season, week in EXPECTED_CELLS:
        r5_job = f"atlas-md-s{season}-w{week}-r5"
        r5_execution = f"{r5_job}-primary"
        r5_uri = f"{REPAIR5_PREFIX}/slate-{season}-{week}.json"
        primary.append([str(season), str(week), r5_job, r5_execution, r5_uri])
        jobs[r5_job] = [r5_execution]
        r6_job = f"atlas-md-s{season}-w{week}-r6"
        if (season, week) in eligible:
            source, job, execution = "repair6", r6_job, f"{r6_job}-one"
            uri = f"{REPAIR6_PREFIX}/slate-{season}-{week}.json"
            jobs[r6_job] = [execution]
            r6_inventory.append(uri)
            image, code, command = R6_IMAGE, R6_CODE, "r6-command"
        else:
            source, job, execution, uri = "repair5", r5_job, r5_execution, r5_uri
            jobs[r6_job] = []
            r5_inventory.append(uri)
            image, code, command = REPAIR5_IMAGE, REPAIR5_CODE_SHA, "r5-command"
        row = [str(season), str(week), source, job, execution, uri]
        accepted.append(row)
        key = f"{season}-{week}"
        executions[key] = _execution(row, image=image, code=code, command=command)
        objects[key] = _object(uri)
    proof_execution = "atlas-md-s2023-w1-r6-proof-one"
    jobs["atlas-md-s2023-w1-r6-proof"] = [proof_execution]
    return {
        "version": "atlas-repair6-hybrid-population-receipt-v1",
        "run_id": REPAIR6_RUN_ID, "repair5_run_id": "20260816-atlas-matched-diversity-mvp-v1-repair5",
        "repair5_prefix": REPAIR5_PREFIX, "repair6_prefix": REPAIR6_PREFIX,
        "proof_prefix": PROOF_PREFIX, "protocol_sha256": PROTOCOL_SHA256,
        "repair5_code_sha": REPAIR5_CODE_SHA, "repair5_image": REPAIR5_IMAGE,
        "repair6_code_sha": R6_CODE, "repair6_image": R6_IMAGE,
        "repair5_terminal_census_sha256": "d" * 64,
        "eligibility_classification_sha256": "e" * 64,
        "code_diff_proof_sha256": "f" * 64,
        "dual_canary_completion_sha256": "1" * 64,
        "repair6_grid_release_sha256": "2" * 64,
        "accepted_execution_ledger_sha256": "3" * 64,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "effect_fields_inspected": False,
        "production_change_licensed": False,
        "disposition": "valid-complete-repair6-hybrid-population", "cells": 54,
        "eligible_cells": [[2023, 7]], "repair5_primary_rows": primary,
        "accepted_rows": accepted, "execution_metadata": executions,
        "objects": objects, "job_execution_names": jobs,
        "prefix_inventories": {
            "repair5": r5_inventory, "repair6": r6_inventory,
            "proof": [f"{PROOF_PREFIX}/slate-2023-1.json"],
        },
        "proof_execution": proof_execution,
    }


def test_repair6_hybrid_accepts_exact_partial_function_extension():
    value = validate_hybrid_receipt(
        _receipt(), repair5_grid_command="r5-command",
        repair6_grid_command="r6-command",
    )
    assert value["eligible_cells"] == [(2023, 7)]
    assert len(value["accepted_rows"]) == 54


def test_repair6_hybrid_rejects_recomputing_success_cell():
    receipt = _receipt()
    target = next(row for row in receipt["accepted_rows"] if row[:2] == ["2023", "8"])
    target[2] = "repair6"
    with pytest.raises(ValueError, match="accepted-cell"):
        validate_hybrid_receipt(
            receipt, repair5_grid_command="r5-command",
            repair6_grid_command="r6-command",
        )


def test_repair6_hybrid_rejects_extra_execution():
    receipt = _receipt()
    receipt["job_execution_names"]["atlas-md-s2024-w2-r6"] = ["unreceipted"]
    with pytest.raises(ValueError, match="execution population"):
        validate_hybrid_receipt(
            receipt, repair5_grid_command="r5-command",
            repair6_grid_command="r6-command",
        )


def test_dual_canary_execution_validator_requires_terminal_success():
    row = [
        "defect", "2023", "7", "atlas-md-s2023-w7-r6",
        "atlas-md-s2023-w7-r6-one", f"{REPAIR6_PREFIX}/slate-2023-7.json",
    ]
    hybrid_row = [row[1], row[2], "repair6", row[3], row[4], row[5]]
    value = _execution(hybrid_row, image=R6_IMAGE, code=R6_CODE, command="r6-command")
    manifest = {"image": R6_IMAGE, "code_sha": R6_CODE}
    _validate_execution(value, row, manifest, "r6-command")
    value["status"]["conditions"][0]["status"] = "False"
    with pytest.raises(RuntimeError, match="did not succeed"):
        _validate_execution(value, row, manifest, "r6-command")


def test_repair6_transport_is_packaged_and_protocol_bound():
    protocol = ROOT / "reports/2026-08-17-atlas-repair6-identity-tiebreak-extension-protocol.md"
    assert sha256(protocol.read_bytes()).hexdigest() == PROTOCOL_SHA256
    launcher = (ROOT / "scripts/cloud_atlas_repair6_dual_canary.sh").read_text()
    grid = (ROOT / "scripts/cloud_atlas_repair6_grid.sh").read_text()
    finisher = (ROOT / "scripts/finish_atlas_repair6_hybrid_population.py").read_text()
    assert "IFS=$'\\t'" in launcher
    assert "atlas-md-s2023-w1-r6-proof" in launcher
    assert "repair6-dual-canary-passes" in grid
    assert "valid-complete-repair6-hybrid-population" in finisher
