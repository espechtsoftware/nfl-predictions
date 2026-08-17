from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = str(REPO / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import finish_stack_core_shell_historical_score as finish  # noqa: E402
import manage_stack_core_shell_historical_score_attempt as attempts  # noqa: E402


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _launch_receipts(tmp_path: Path) -> tuple[dict[str, str], str]:
    execution = attempts.JOB + "-abc12"
    manifest = {
        "run_id": attempts.RUN_ID, "output_prefix": attempts.PREFIX,
        "output_uri": attempts.OUTPUT_URI,
        "execution_protocol_sha256": attempts.EXECUTION_PROTOCOL_SHA256,
        "tasks": "1", "parallelism": "1", "cpu": "4", "memory": "16Gi",
        "timeout_seconds": "7200", "max_retries": "0",
        "uses_realized_outcomes": "true", "actual_scores_queried": "true",
        "production_change_licensed": "false", "code_sha": "a" * 40,
        "image": "image@sha256:" + "b" * 64,
        "lock_report_sha256": "c" * 64,
        "lock_completion_sha256": "d" * 64,
    }
    (tmp_path / "manifest.txt").write_text(
        "\n".join(f"{key}={value}" for key, value in manifest.items()) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "executions.txt").write_text(
        f"{attempts.JOB} {execution} {attempts.OUTPUT_URI}\n", encoding="utf-8",
    )
    return manifest, execution


def _metadata(manifest: dict[str, str], execution: str) -> dict:
    return {
        "metadata": {"name": execution},
        "spec": {"parallelism": 1, "taskCount": 1, "template": {"spec": {
            "maxRetries": 0, "timeoutSeconds": "7200",
            "serviceAccountName": attempts.SERVICE_ACCOUNT,
            "containers": [{
                "image": manifest["image"], "command": ["python"],
                "args": [
                    attempts.RUNNER, "--output-uri", attempts.OUTPUT_URI,
                    "--lock-report-sha256", manifest["lock_report_sha256"],
                    "--lock-completion-sha256", manifest["lock_completion_sha256"],
                ],
                "env": [
                    {"name": "CODE_SHA", "value": manifest["code_sha"]},
                    {"name": "ANALYSIS_IMAGE", "value": manifest["image"]},
                ],
                "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
            }],
        }}},
        "status": {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1, "failedCount": 0,
            "completionTime": "2026-08-17T03:00:00Z",
        },
    }


def test_historical_attempt_contract_and_primary_receipt(tmp_path: Path) -> None:
    manifest, execution = _launch_receipts(tmp_path)
    metadata = _metadata(manifest, execution)
    attempts._validate_contract(metadata, manifest, execution)
    (tmp_path / "primary-execution-metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8",
    )
    (tmp_path / "primary-object-status.json").write_text(
        json.dumps({"uri": attempts.OUTPUT_URI, "present": True}),
        encoding="utf-8",
    )
    (tmp_path / "retry-executions.txt").write_text("", encoding="utf-8")
    accepted = tmp_path / "accepted-executions.txt"
    accepted.write_text(
        f"{attempts.JOB} {execution} {attempts.OUTPUT_URI}\n", encoding="utf-8",
    )
    resolution = {
        "version": "stack-core-shell-historical-attempt-resolution-v1",
        "run_id": attempts.RUN_ID, "disposition": "accepted-primary",
        "primary_execution": execution, "replacement_execution": None,
        "accepted_execution": execution, "task_max_retries": 0,
        "max_replacement_executions": 1, "uses_realized_outcomes": True,
        "actual_scores_queried": True, "report_content_inspected": False,
        "primary_execution_ledger_sha256": _sha(tmp_path / "executions.txt"),
        "retry_execution_ledger_sha256": _sha(tmp_path / "retry-executions.txt"),
        "accepted_execution_ledger_sha256": _sha(accepted),
    }
    (tmp_path / "attempt-resolution.json").write_text(
        json.dumps(resolution), encoding="utf-8",
    )
    assert attempts.validate(tmp_path)["disposition"] == "accepted-primary"


def test_historical_finisher_recomputes_report_and_binds_lock(monkeypatch) -> None:
    base = {
        "version": finish.REPORT_VERSION,
        "uses_realized_outcomes": True, "mechanical_valid": True,
        "population": {"seasons": [2023, 2024, 2025], "slates": 54},
        "gate": {
            "disposition": "historical-tail-first-positive",
            "production_change_licensed": False,
        },
        "production_change_licensed": False, "rows": [{}] * 54,
    }
    monkeypatch.setattr(finish, "aggregate_historical", lambda _rows: base)
    manifest = {
        "code_sha": "a" * 40, "image": "image@sha256:" + "b" * 64,
        "protocol_sha256": "f" * 64,
        "lock_report_uri": "gs://bucket/lock-report.json",
        "lock_report_sha256": "c" * 64,
        "lock_completion_uri": "gs://bucket/lock-completion.txt",
        "lock_completion_sha256": "d" * 64,
        "lock_accepted_execution_ledger_sha256": "e" * 64,
    }
    report = {
        **base, "run_id": finish.RUN_ID, "scorer_code_sha": manifest["code_sha"],
        "scorer_image": manifest["image"],
        "historical_protocol_sha256": manifest["protocol_sha256"],
        "native_actual_score_parity": {
            "registered_candidate_rows": 68_199, "slots_per_roster": 9,
            "malformed_rosters": 0, "missing_player_outcomes": 0,
            "compared_rows": 68_199, "maximum_absolute_error": 1e-12,
            "absolute_tolerance": 1e-9, "relative_tolerance": 0.0,
            "source_storage_type": "FLOAT",
        },
        "source_artifacts": {"count": 270, "sha256": "1" * 64},
        "lock_receipt": {
            "report": {"uri": manifest["lock_report_uri"], "sha256": "c" * 64},
            "completion": {
                "uri": manifest["lock_completion_uri"], "sha256": "d" * 64,
            },
            "accepted_execution_ledger_sha256": "e" * 64,
        },
    }
    finish._validate_report(report, manifest)
    report["native_actual_score_parity"]["compared_rows"] -= 1
    try:
        finish._validate_report(report, manifest)
    except RuntimeError as exc:
        assert "native parity differs" in str(exc)
    else:
        raise AssertionError("incomplete native score parity was accepted")


def test_historical_launcher_and_watcher_preserve_single_score_boundary() -> None:
    launcher = (REPO / "scripts/cloud_stack_core_shell_historical_score.sh").read_text(
        encoding="utf-8",
    )
    watcher = (
        REPO / "scripts/watch_stack_core_shell_historical_score_queue.sh"
    ).read_text(encoding="utf-8")
    assert "--max-retries 0 --task-timeout 2h" in launcher
    assert "actual_scores_queried=true" in launcher
    assert "STACK_CORE_SHELL_HISTORICAL_SCORE_LAUNCHED" in launcher
    assert "manage_stack_core_shell_historical_score_attempt.py" in watcher
    assert "finish_stack_core_shell_historical_score.py" in watcher
