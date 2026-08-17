from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import validate_coherent_market_state_attempts as attempts  # noqa: E402


IMAGE = "example/image@sha256:" + "b" * 64
CODE = "a" * 40


def _metadata(season: int, week: int) -> dict:
    job = f"coherent-state-s{season}-w{week}-v1"
    execution = f"{job}-primary"
    uri = f"{attempts.PREFIX}/slate-{season}-{week}.json"
    return {
        "metadata": {"name": execution},
        "spec": {
            "parallelism": 1,
            "taskCount": 1,
            "template": {"spec": {
                "containers": [{
                    "image": IMAGE,
                    "command": ["python"],
                    "args": [
                        attempts.RUNNER, "--season", str(season),
                        "--week", str(week), "--output-uri", uri,
                    ],
                    "env": [
                        {"name": "CODE_SHA", "value": CODE},
                        {"name": "ANALYSIS_IMAGE", "value": IMAGE},
                    ],
                    "resources": {"limits": {
                        "cpu": "4", "memory": "16Gi",
                    }},
                }],
                "maxRetries": 0,
                "timeoutSeconds": 14400,
                "serviceAccountName": (
                    "817589974517-compute@developer.gserviceaccount.com"
                ),
            }},
        },
        "status": {
            "conditions": [{
                "type": "Completed", "status": "True",
                "message": "", "reason": "",
            }],
            "succeededCount": 1,
            "failedCount": 0,
            "completionTime": "2026-08-17T00:00:00Z",
        },
    }


def _receipts(tmp_path: Path) -> tuple[Path, Path]:
    resolver = ROOT / "scripts/cloud_prepare_coherent_market_state_attempts.sh"
    validator = ROOT / "scripts/validate_coherent_market_state_attempts.py"
    manifest = tmp_path / "manifest.txt"
    manifest.write_text(
        "\n".join((
            f"execution_protocol_sha256={attempts.PROTOCOL_SHA256}",
            f"attempt_resolver_sha256={sha256(resolver.read_bytes()).hexdigest()}",
            f"attempt_validator_sha256={sha256(validator.read_bytes()).hexdigest()}",
            f"image={IMAGE}",
            f"code_sha={CODE}",
        )) + "\n",
        encoding="utf-8",
    )
    primary_rows = []
    cells = []
    inventory = []
    metadata_dir = tmp_path / "primary-execution-metadata"
    metadata_dir.mkdir()
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            job = f"coherent-state-s{season}-w{week}-v1"
            execution = f"{job}-primary"
            uri = f"{attempts.PREFIX}/slate-{season}-{week}.json"
            primary_rows.append(
                f"{season} {week} {job} {execution} {uri}\n"
            )
            inventory.append(uri + "\n")
            metadata = _metadata(season, week)
            metadata_path = (
                metadata_dir / f"season-{season}-week-{week}.json"
            )
            metadata_path.write_text(
                json.dumps(metadata), encoding="utf-8",
            )
            cells.append({
                "season": season,
                "week": week,
                "job": job,
                "primary_execution": execution,
                "uri": uri,
                "status": "True",
                "reason": "",
                "message": "",
                "completion_time": "2026-08-17T00:00:00Z",
                "object_present": True,
                "eligibility": "primary-success",
            })
    primary = tmp_path / "executions.txt"
    primary.write_text("".join(primary_rows), encoding="utf-8")
    retries = tmp_path / "retry-executions.txt"
    retries.write_text("", encoding="utf-8")
    accepted = tmp_path / "accepted-executions.txt"
    accepted.write_text("".join(primary_rows), encoding="utf-8")
    inventory_path = tmp_path / "primary-object-inventory.txt"
    inventory_path.write_text("".join(inventory), encoding="utf-8")
    canary = tmp_path / "canary-completion.txt"
    canary.write_text("status=True\n", encoding="utf-8")
    release = tmp_path / "grid-release.txt"
    release.write_text("primary_executions=54\n", encoding="utf-8")
    classification = tmp_path / "primary-attempt-classification.json"
    classification.write_text(json.dumps({
        "version": "coherent-market-state-primary-attempt-classification-v1",
        "run_id": attempts.RUN_ID,
        "execution_protocol_sha256": attempts.PROTOCOL_SHA256,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "task_max_retries": 0,
        "max_replacement_executions_per_cell": 1,
        "primary_executions": 54,
        "eligible_replacements": 0,
        "ineligible_failures": 0,
        "disposition": "all-primary-success",
        "primary_execution_ledger_sha256": sha256(
            primary.read_bytes()
        ).hexdigest(),
        "primary_object_inventory_sha256": sha256(
            inventory_path.read_bytes()
        ).hexdigest(),
        "canary_completion_sha256": sha256(canary.read_bytes()).hexdigest(),
        "grid_release_sha256": sha256(release.read_bytes()).hexdigest(),
        "cells": cells,
    }), encoding="utf-8")
    resolution = tmp_path / "attempt-resolution.json"
    resolution.write_text(json.dumps({
        "version": "coherent-market-state-attempt-resolution-v1",
        "run_id": attempts.RUN_ID,
        "disposition": "accepted-primary-population",
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "task_max_retries": 0,
        "max_replacement_executions_per_cell": 1,
        "primary_executions": 54,
        "retry_executions": 0,
        "accepted_executions": 54,
        "classification_sha256": sha256(classification.read_bytes()).hexdigest(),
        "primary_execution_ledger_sha256": sha256(
            primary.read_bytes()
        ).hexdigest(),
        "retry_execution_ledger_sha256": sha256(
            retries.read_bytes()
        ).hexdigest(),
        "accepted_execution_ledger_sha256": sha256(
            accepted.read_bytes()
        ).hexdigest(),
    }), encoding="utf-8")
    (tmp_path / "primary-execution-metadata.sha256").write_text(
        "".join(
            f"{sha256(path.read_bytes()).hexdigest()}  {path}\n"
            for path in sorted(metadata_dir.glob("*.json"))
        ),
        encoding="utf-8",
    )
    return manifest, classification


def test_attempt_validator_accepts_exact_primary_population(tmp_path: Path) -> None:
    manifest, _classification = _receipts(tmp_path)
    result = attempts.validate(tmp_path, manifest)
    assert result["disposition"] == "accepted-primary-population"


def test_attempt_validator_rejects_terminal_evidence_drift(tmp_path: Path) -> None:
    manifest, classification = _receipts(tmp_path)
    value = json.loads(classification.read_text(encoding="utf-8"))
    value["cells"][0]["completion_time"] = "2026-08-17T00:01:00Z"
    classification.write_text(json.dumps(value), encoding="utf-8")
    resolution = tmp_path / "attempt-resolution.json"
    receipt = json.loads(resolution.read_text(encoding="utf-8"))
    receipt["classification_sha256"] = sha256(
        classification.read_bytes()
    ).hexdigest()
    resolution.write_text(json.dumps(receipt), encoding="utf-8")
    try:
        attempts.validate(tmp_path, manifest)
    except ValueError as exc:
        assert "terminal evidence differs" in str(exc)
    else:
        raise AssertionError("coherent-state terminal evidence drift was accepted")


def test_cloud_transport_enforces_real_path_canary_and_full_harvest() -> None:
    launcher = (
        ROOT / "scripts/cloud_coherent_market_state_scorefree.sh"
    ).read_text(encoding="utf-8")
    canary = (
        ROOT / "scripts/cloud_wait_coherent_market_state_canary.sh"
    ).read_text(encoding="utf-8")
    resolver = (
        ROOT / "scripts/cloud_prepare_coherent_market_state_attempts.sh"
    ).read_text(encoding="utf-8")
    finisher = (
        ROOT / "scripts/cloud_finish_coherent_market_state_scorefree.sh"
    ).read_text(encoding="utf-8")
    watcher = (
        ROOT / "scripts/watch_coherent_market_state_queue.sh"
    ).read_text(encoding="utf-8")
    assert launcher.index("deploy_cell 2023 1") < launcher.index(
        'bash "$CANARY_VALIDATOR"'
    ) < launcher.index("for SEASON in 2023 2024 2025")
    assert "scripts/cloud_coherent_market_state_scorefree.sh" in launcher
    assert "scripts/watch_coherent_market_state_queue.sh" in launcher
    assert "launcher_sha256=" in launcher
    assert "watcher_sha256=" in launcher
    assert "gcloud storage cp" not in canary
    assert 'row.get("type") == "Completed"' in canary
    assert "internal error running task" in resolver
    for forbidden in (
        "configured memory limit", "timeout", "signal", "sigkill",
        "solver", "cbc", "nonzero exit",
    ):
        assert forbidden in resolver
    download_boundary = finisher.index(
        "# Only after all 54 accepted executions and objects"
    )
    assert "gcloud storage cp" not in finisher[:download_boundary]
    assert 'TMP=$(mktemp -d "$OUT/.harvest.XXXXXX")' in finisher
    assert "trap 'rm -rf -- \"$TMP\"' EXIT" in finisher
    assert 'wc -l < "$ACCEPTED")" = 54' in finisher
    assert watcher.index("cloud_coherent_market_state_scorefree.sh") < \
        watcher.index("cloud_prepare_coherent_market_state_attempts.sh") < \
        watcher.index("cloud_finish_coherent_market_state_scorefree.sh")
    assert "COHERENT_MARKET_STATE_ACCEPTED_STATUS" in watcher
    assert 'row.get("type") == "Completed"' in watcher
    for script in (
        "cloud_wait_coherent_market_state_canary.sh",
        "cloud_prepare_coherent_market_state_attempts.sh",
        "cloud_coherent_market_state_scorefree.sh",
        "cloud_finish_coherent_market_state_scorefree.sh",
        "watch_coherent_market_state_queue.sh",
    ):
        subprocess.run(
            ["bash", "-n", str(ROOT / "scripts" / script)], check=True,
        )
