from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import manage_stack_core_shell_support_attempts as attempts  # noqa: E402


IMAGE = "example/image@sha256:" + "b" * 64
CODE = "a" * 40


def _metadata(
    season: int,
    week: int,
    *,
    status: str = "True",
    message: str = "",
) -> dict:
    job = attempts.JOB_PATTERN.format(season=season, week=week)
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
                    "resources": {"limits": {"cpu": "4", "memory": "16Gi"}},
                }],
                "maxRetries": 0,
                "timeoutSeconds": 7200,
                "serviceAccountName": (
                    "817589974517-compute@developer.gserviceaccount.com"
                ),
            }},
        },
        "status": {
            "conditions": [{
                "type": "Completed", "status": status,
                "message": message, "reason": "",
            }],
            "succeededCount": 1 if status == "True" else 0,
            "failedCount": 0 if status == "True" else 1,
            "cancelledCount": 0,
            "completionTime": "2026-08-17T00:00:00Z",
        },
    }


def _launch_receipts(tmp_path: Path) -> tuple[Path, dict[str, dict]]:
    manifest = {
        "run_id": attempts.RUN_ID,
        "output_prefix": attempts.PREFIX,
        "execution_protocol_sha256": attempts.EXECUTION_PROTOCOL_SHA256,
        "cpu": "4", "memory": "16Gi", "timeout_seconds": "7200",
        "max_retries": "0", "uses_realized_outcomes": "false",
        "effect_fields_inspected": "false", "treatment_constructed": "false",
        "production_change_licensed": "false",
        "historical_scoring_licensed": "false",
        "code_sha": CODE, "image": IMAGE,
    }
    (tmp_path / "manifest.txt").write_text(
        "".join(f"{key}={value}\n" for key, value in manifest.items()),
        encoding="utf-8",
    )
    rows = []
    metadata = {}
    for season, week in attempts.GRID:
        job = attempts.JOB_PATTERN.format(season=season, week=week)
        execution = f"{job}-primary"
        uri = f"{attempts.PREFIX}/slate-{season}-{week}.json"
        rows.append(f"{season} {week} {job} {execution} {uri}\n")
        metadata[execution] = _metadata(season, week)
    (tmp_path / "executions.txt").write_text("".join(rows), encoding="utf-8")
    canary = (
        "status=True\n"
        "disposition=real-path-canary-passes\n"
        "cell=2023-1\n"
        "remaining_cells_released=false\n"
        "object_content_inspected=false\n"
        "effect_fields_inspected=false\n"
        "treatment_constructed=false\n"
    )
    (tmp_path / "canary-completion.txt").write_text(canary, encoding="utf-8")
    canary_sha = sha256(canary.encode()).hexdigest()
    (tmp_path / "grid-release.txt").write_text(
        "primary_executions=54\n"
        "released_after_canary=53\n"
        f"canary_completion_sha256={canary_sha}\n",
        encoding="utf-8",
    )
    return tmp_path, metadata


def test_all_primary_success_is_accepted_and_revalidates(
    tmp_path: Path, monkeypatch,
) -> None:
    out, metadata = _launch_receipts(tmp_path)
    monkeypatch.setattr(attempts, "_execution_metadata", metadata.__getitem__)
    monkeypatch.setattr(
        attempts, "_object_metadata",
        lambda _uri: {"generation": "1", "size": "100"},
    )
    result = attempts.prepare(out)
    assert result["disposition"] == "accepted-primary-population"
    assert result["retry_executions"] == 0
    assert result["accepted_executions"] == 54
    assert len((out / "accepted-executions.txt").read_text().splitlines()) == 54
    assert attempts.validate(out)["disposition"] == \
        "accepted-primary-population"


def test_literal_zero_object_platform_failure_is_only_eligible_class(
    tmp_path: Path, monkeypatch,
) -> None:
    out, metadata = _launch_receipts(tmp_path)
    failed = next(iter(metadata))
    metadata[failed]["status"]["conditions"][0].update({
        "status": "False", "message": "Internal error running task",
    })
    metadata[failed]["status"].update({"succeededCount": 0, "failedCount": 1})
    failed_uri = metadata[failed]["spec"]["template"]["spec"]["containers"][0][
        "args"
    ][-1]
    monkeypatch.setattr(attempts, "_execution_metadata", metadata.__getitem__)
    monkeypatch.setattr(
        attempts, "_object_metadata",
        lambda uri: None if uri == failed_uri else {"generation": "1", "size": 100},
    )
    manifest, primary = attempts._validate_launch_receipts(out)
    result = attempts._classify(out, manifest, primary)
    assert result["disposition"] == "replacement-required"
    assert result["eligible_replacements"] == 1
    assert result["ineligible_failures"] == 0


def test_memory_failure_is_terminal_and_never_replacement_eligible(
    tmp_path: Path, monkeypatch,
) -> None:
    out, metadata = _launch_receipts(tmp_path)
    failed = next(iter(metadata))
    metadata[failed]["status"]["conditions"][0].update({
        "status": "False",
        "message": "The container exceeded the configured memory limit.",
    })
    metadata[failed]["status"].update({"succeededCount": 0, "failedCount": 1})
    failed_uri = metadata[failed]["spec"]["template"]["spec"]["containers"][0][
        "args"
    ][-1]
    monkeypatch.setattr(attempts, "_execution_metadata", metadata.__getitem__)
    monkeypatch.setattr(
        attempts, "_object_metadata",
        lambda uri: None if uri == failed_uri else {"generation": "1", "size": 100},
    )
    manifest, primary = attempts._validate_launch_receipts(out)
    result = attempts._classify(out, manifest, primary)
    assert result["disposition"] == "terminal-invalid-primary"
    assert result["eligible_replacements"] == 0
    assert result["ineligible_failures"] == 1
