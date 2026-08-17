from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from manage_stack_core_shell_scorefree_attempts import (  # noqa: E402
    EXECUTION_PROTOCOL_SHA256,
    GRID,
    PREFIX,
    RUN_ID,
    validate,
)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _population(tmp_path: Path) -> None:
    canary = tmp_path / "canary-completion.txt"
    canary.write_text("\n".join([
        "status=True", "disposition=real-path-canary-passes", "cell=2023-1",
        "remaining_cells_released=false", "object_content_inspected=false",
        "effect_fields_inspected=false", "treatment_constructed=true",
    ]) + "\n", encoding="utf-8")
    (tmp_path / "grid-release.txt").write_text("\n".join([
        "primary_executions=54", "released_after_canary=53",
        f"canary_completion_sha256={_sha(canary)}",
    ]) + "\n", encoding="utf-8")
    (tmp_path / "manifest.txt").write_text("\n".join([
        f"run_id={RUN_ID}", f"output_prefix={PREFIX}",
        f"execution_protocol_sha256={EXECUTION_PROTOCOL_SHA256}",
        "cpu=4", "memory=16Gi", "timeout_seconds=14400", "max_retries=0",
        "uses_realized_outcomes=false", "effect_fields_inspected=false",
        "treatment_constructed=true", "production_change_licensed=false",
        "historical_scoring_licensed=false", f"code_sha={'a' * 40}",
        f"image=image@sha256:{'b' * 64}",
        f"support_report_sha256={'c' * 64}",
        f"support_completion_sha256={'d' * 64}",
    ]) + "\n", encoding="utf-8")
    primary_rows = []
    cells = []
    objects = []
    metadata_dir = tmp_path / "primary-execution-metadata"
    metadata_dir.mkdir()
    for season, week in GRID:
        job = f"stack-shell-scorefree-s{season}-w{week}-v1"
        execution = job + "-abc12"
        uri = f"{PREFIX}/slate-{season}-{week}.json"
        primary_rows.append([str(season), str(week), job, execution, uri])
        cells.append({
            "season": season, "week": week, "job": job,
            "primary_execution": execution, "uri": uri, "status": "True",
            "reason": "", "message": "", "completion_time": "now",
            "object_present": True, "eligibility": "primary-success",
        })
        objects.append({
            "season": season, "week": week, "uri": uri, "present": True,
            "metadata_sha256": "e" * 64,
        })
        (metadata_dir / f"season-{season}-week-{week}.json").write_text(
            "{}\n", encoding="utf-8",
        )
    primary = tmp_path / "executions.txt"
    primary.write_text(
        "".join(" ".join(row) + "\n" for row in primary_rows),
        encoding="utf-8",
    )
    accepted = tmp_path / "accepted-executions.txt"
    accepted.write_bytes(primary.read_bytes())
    retries = tmp_path / "retry-executions.txt"
    retries.write_text("", encoding="utf-8")
    classification = {
        "version": "stack-core-shell-scorefree-primary-attempt-classification-v1",
        "run_id": RUN_ID, "execution_protocol_sha256": EXECUTION_PROTOCOL_SHA256,
        "uses_realized_outcomes": False, "effect_fields_inspected": False,
        "treatment_constructed": True, "task_max_retries": 0,
        "max_replacement_executions_per_cell": 1, "primary_executions": 54,
        "eligible_replacements": 0, "ineligible_failures": 0,
        "disposition": "all-primary-success",
        "primary_execution_ledger_sha256": _sha(primary),
        "canary_completion_sha256": _sha(canary),
        "grid_release_sha256": _sha(tmp_path / "grid-release.txt"),
        "cells": cells,
    }
    classification_path = tmp_path / "primary-attempt-classification.json"
    classification_path.write_text(
        json.dumps(classification, sort_keys=True) + "\n", encoding="utf-8",
    )
    (tmp_path / "primary-object-status.json").write_text(
        json.dumps(objects, sort_keys=True) + "\n", encoding="utf-8",
    )
    resolution = {
        "version": "stack-core-shell-scorefree-attempt-resolution-v1",
        "run_id": RUN_ID, "disposition": "accepted-primary-population",
        "uses_realized_outcomes": False, "effect_fields_inspected": False,
        "treatment_constructed": True, "task_max_retries": 0,
        "max_replacement_executions_per_cell": 1, "primary_executions": 54,
        "retry_executions": 0, "accepted_executions": 54,
        "classification_sha256": _sha(classification_path),
        "primary_execution_ledger_sha256": _sha(primary),
        "retry_execution_ledger_sha256": _sha(retries),
        "accepted_execution_ledger_sha256": _sha(accepted),
    }
    (tmp_path / "attempt-resolution.json").write_text(
        json.dumps(resolution, sort_keys=True) + "\n", encoding="utf-8",
    )


def test_scorefree_attempt_receipt_accepts_exact_primary_population(
    tmp_path: Path,
) -> None:
    _population(tmp_path)
    result = validate(tmp_path)
    assert result["disposition"] == "accepted-primary-population"
    assert result["treatment_constructed"] is True


def test_scorefree_attempt_receipt_rejects_support_style_flag(
    tmp_path: Path,
) -> None:
    _population(tmp_path)
    path = tmp_path / "attempt-resolution.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["treatment_constructed"] = False
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    try:
        validate(tmp_path)
    except RuntimeError as exc:
        assert "resolution differs" in str(exc)
    else:
        raise AssertionError("support-style treatment flag was accepted")
