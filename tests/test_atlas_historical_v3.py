from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys

import pytest

from nfl_dfs.research.atlas_historical_v3_sources import (
    CANARY_ATTEMPT0_RECEIPT_SHA256,
    CANARY_COMPLETION_SHA256,
    CANARY_EXECUTION,
    EXPECTED_CELLS,
    EXPECTED_SOURCE_HASHES,
    GRID_RELEASE_SHA256,
    HISTORICAL_PREFIX,
    HISTORICAL_RUN_ID,
    PRIMARY_LEDGER_SHA256,
    SERVICE_ACCOUNT,
    UPSTREAM_CODE_SHA,
    UPSTREAM_IMAGE,
    UPSTREAM_MANIFEST_SHA256,
    UPSTREAM_PREFIX,
    UPSTREAM_RUN_ID,
    validate_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


from run_atlas_historical_score_diagnostic_v3 import (  # noqa: E402
    OUTPUT_URI,
    PLAYER_SQL,
    SOURCE_SQL,
    UPSTREAM_RECEIPT_URI,
)


STRICT_KEYS = {
    "completion_sha256", "report_sha256", "season_reports_sha256",
    "shards_sha256", "execution_metadata_sha256",
    "primary_execution_metadata_sha256", "primary_object_inventory_sha256",
    "primary_attempt_classification_sha256", "retry_execution_ledger_sha256",
    "accepted_execution_ledger_sha256", "attempt_resolution_sha256",
    "attempt_artifacts_sha256", "canary_completion_sha256",
    "canary_execution_metadata_sha256", "canary_object_metadata_sha256",
    "canary_sha256", "grid_release_sha256", "validator_repair_sha256",
    "canary_attempt0_receipt_sha256", "canary_attempt0_metadata_sha256",
    "canary_attempt0_attempt_sha256",
}


def _execution(row, command="grid", *, success=True):
    season, week, _job, execution, uri = row
    return {
        "metadata": {"name": execution},
        "status": {
            "conditions": [{
                "type": "Completed", "status": "True" if success else "False",
            }],
            "succeededCount": 1 if success else 0,
            "failedCount": 0 if success else 1,
            "completionTime": "2026-08-17T12:00:00Z",
        },
        "spec": {
            "parallelism": 1, "taskCount": 1,
            "template": {"spec": {
                "containers": [{
                    "image": UPSTREAM_IMAGE, "command": ["python"],
                    "args": [
                        "-c", command, "--season", season, "--week", week,
                        "--output-uri", uri,
                    ],
                    "env": [
                        {"name": "CODE_SHA", "value": UPSTREAM_CODE_SHA},
                        {"name": "ANALYSIS_IMAGE", "value": UPSTREAM_IMAGE},
                    ],
                    "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
                }],
                "maxRetries": 0, "timeoutSeconds": "43200",
                "serviceAccountName": SERVICE_ACCOUNT,
            }},
        },
    }


def _object(uri):
    return {
        "uri": uri, "generation": "1", "bytes": 1, "sha256": "a" * 64,
        "md5_hash": "md5", "crc32c": "crc", "updated": "time",
    }


def _receipt(*, replacement=False):
    primary = []
    for season, week in EXPECTED_CELLS:
        job = f"atlas-md-s{season}-w{week}-r5"
        execution = CANARY_EXECUTION if (season, week) == (2023, 1) else (
            f"{job}-primary"
        )
        primary.append([
            str(season), str(week), job, execution,
            f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json",
        ])
    accepted = deepcopy(primary)
    retries = []
    if replacement:
        original = primary[-1]
        retry = [*original[:4], f"{original[2]}-replacement", original[4]]
        retries.append(retry)
        accepted[-1][3] = retry[4]
    strict = {key: "b" * 64 for key in STRICT_KEYS}
    strict.update({
        "canary_completion_sha256": CANARY_COMPLETION_SHA256,
        "grid_release_sha256": GRID_RELEASE_SHA256,
        "canary_attempt0_receipt_sha256": CANARY_ATTEMPT0_RECEIPT_SHA256,
        "retry_execution_ledger_sha256": "c" * 64,
        "accepted_execution_ledger_sha256": "d" * 64,
        "primary_object_inventory_sha256": "e" * 64,
        "primary_attempt_classification_sha256": "f" * 64,
    })
    primary_metadata = {}
    accepted_metadata = {}
    jobs = {}
    cells = []
    retry_by_cell = {(row[0], row[1]): row for row in retries}
    for primary_row, accepted_row in zip(primary, accepted, strict=True):
        key = f"{primary_row[0]}-{primary_row[1]}"
        retry = retry_by_cell.get((primary_row[0], primary_row[1]))
        primary_metadata[key] = _execution(primary_row, success=retry is None)
        accepted_metadata[key] = _execution(accepted_row)
        jobs[primary_row[2]] = [primary_row[3]] + ([] if retry is None else [retry[4]])
        cells.append({
            "season": int(primary_row[0]), "week": int(primary_row[1]),
            "job": primary_row[2], "primary_execution": primary_row[3],
            "uri": primary_row[4], "eligibility": (
                "primary-success" if retry is None else "eligible-platform-replacement"
            ),
            "object_present": retry is None,
        })
    resolution = {
        "version": "atlas-repair5-attempt-resolution-v1",
        "disposition": (
            "accepted-primary-population" if not retries
            else "accepted-population-with-platform-replacements"
        ),
        "uses_realized_outcomes": False, "effect_fields_inspected": False,
        "accepted_executions": 54, "retry_executions": len(retries),
        "classification_sha256": strict["primary_attempt_classification_sha256"],
        "primary_execution_ledger_sha256": PRIMARY_LEDGER_SHA256,
        "retry_execution_ledger_sha256": strict["retry_execution_ledger_sha256"],
        "accepted_execution_ledger_sha256": strict["accepted_execution_ledger_sha256"],
        "canary_completion_sha256": CANARY_COMPLETION_SHA256,
        "grid_release_sha256": GRID_RELEASE_SHA256,
    }
    classification = {
        "version": "atlas-repair5-primary-attempt-classification-v1",
        "uses_realized_outcomes": False, "effect_fields_inspected": False,
        "ineligible_failures": 0, "eligible_replacements": len(retries),
        "primary_execution_ledger_sha256": PRIMARY_LEDGER_SHA256,
        "primary_object_inventory_sha256": strict["primary_object_inventory_sha256"],
        "canary_completion_sha256": CANARY_COMPLETION_SHA256,
        "grid_release_sha256": GRID_RELEASE_SHA256, "cells": cells,
    }
    return {
        "version": "atlas-historical-upstream-receipt-v5",
        "historical_run_id": HISTORICAL_RUN_ID,
        "upstream_run_id": UPSTREAM_RUN_ID, "upstream_prefix": UPSTREAM_PREFIX,
        "upstream_code_sha": UPSTREAM_CODE_SHA, "upstream_image": UPSTREAM_IMAGE,
        "upstream_manifest_sha256": UPSTREAM_MANIFEST_SHA256,
        "primary_execution_ledger_sha256": PRIMARY_LEDGER_SHA256,
        "uses_realized_outcomes": False, "effect_fields_inspected": False,
        "canary_rerun": False, "source_hashes": EXPECTED_SOURCE_HASHES,
        "primary_execution_rows": primary, "retry_execution_rows": retries,
        "accepted_execution_rows": accepted,
        "primary_execution_metadata": primary_metadata,
        "accepted_execution_metadata": accepted_metadata,
        "canary_job_executions": [CANARY_EXECUTION],
        "job_execution_names": jobs, "strict_harvest": strict,
        "attempt": {"classification": classification, "resolution": resolution},
        "objects": {
            "report": _object(f"{UPSTREAM_PREFIX}/report.json"),
            **{
                f"season-{season}": _object(
                    f"{UPSTREAM_PREFIX}/season-{season}.json"
                ) for season in (2023, 2024, 2025)
            },
        },
        "shards": {
            f"{season}-{week}": _object(
                f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json"
            ) for season, week in EXPECTED_CELLS
        },
    }


@pytest.mark.parametrize("replacement", [False, True])
def test_v3_source_receipt_accepts_complete_primary_or_bounded_replacement(replacement):
    value = validate_receipt(_receipt(replacement=replacement), "grid")
    assert len(value["accepted_rows"]) == 54
    assert len(value["retry_rows"]) == int(replacement)


def test_v3_source_receipt_rejects_unreceipted_extra_execution():
    receipt = _receipt()
    receipt["job_execution_names"]["atlas-md-s2024-w7-r5"].append("extra")
    with pytest.raises(RuntimeError, match="unreceipted"):
        validate_receipt(receipt, "grid")


def test_v3_source_receipt_rejects_changed_upstream_resource():
    receipt = _receipt()
    receipt["accepted_execution_metadata"]["2024-7"]["spec"]["template"][
        "spec"
    ]["containers"][0]["resources"]["limits"]["memory"] = "16Gi"
    with pytest.raises(RuntimeError, match="contract"):
        validate_receipt(receipt, "grid")


def test_v3_frozen_sources_and_execution_protocol_are_present():
    for relative, digest in EXPECTED_SOURCE_HASHES.items():
        path = ROOT / relative
        assert path.is_file()
        assert sha256(path.read_bytes()).hexdigest() == digest
    assert sha256((
        ROOT / "reports/2026-08-17-atlas-historical-score-v3-execution-protocol.md"
    ).read_bytes()).hexdigest() == (
        "2a4b0ed6c6a2c4b15c052968248aefd0d8a1ff519c5ec2bce5c72bfb50020e7b"
    )


def test_v3_runner_queries_only_required_realized_fields_and_fixed_destinations():
    source = SOURCE_SQL.lower()
    player = PLAYER_SQL.lower()
    assert "actual_score" in source and " actual" in player
    for forbidden in ("ownership", "payout", "contest_rank", "actual_rank"):
        assert forbidden not in f"{source}\n{player}"
    assert UPSTREAM_RECEIPT_URI == f"{HISTORICAL_PREFIX}/upstream-receipt.json"
    assert OUTPUT_URI == f"{HISTORICAL_PREFIX}/report.json"


def test_v3_runner_is_packaged_smoked_and_lease_controlled():
    runner = "scripts/run_atlas_historical_score_diagnostic_v3.py"
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    cloudbuild = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    launcher = (
        ROOT / "scripts/cloud_atlas_historical_score_diagnostic_v3.sh"
    ).read_text(encoding="utf-8")
    watcher = (
        ROOT / "scripts/watch_atlas_historical_v3_queue.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/finish_atlas_historical_score_diagnostic_v3.py"
    ).read_text(encoding="utf-8")
    assert f"COPY {runner} ./{runner}" in dockerfile
    assert f"python {runner} --help" in cloudbuild
    for token in (
        "--upstream-receipt-generation", "--upstream-receipt-sha256",
        "--cpu 8", "--memory 32Gi", "--max-retries 0", "--task-timeout 8h",
    ):
        assert token in launcher
    assert "historical_outcome_lease.py\" acquire" in launcher
    assert "historical_outcome_lease.py\" release" in watcher
    assert "aggregate_diagnostic(rows)" in finisher
