from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = str(REPO / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import finish_stack_core_shell_production_locks as finish  # noqa: E402
import manage_stack_core_shell_lock_attempts as attempts  # noqa: E402


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> dict[str, str]:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    sources = (
        "run_stack_core_shell_production_lock.py",
        "aggregate_stack_core_shell_production_locks.py",
        "stack_core_shell_sources.py",
        "cloud_wait_stack_core_shell_lock_canary.sh",
        "validate_stack_core_shell_lock_canary.py",
    )
    for name in sources:
        (scripts / name).write_bytes((REPO / "scripts" / name).read_bytes())
    scorefree = tmp_path / "reports/stack-core-shell-runs" / \
        "20260816-stack-core-shell-scorefree-v1"
    scorefree.mkdir(parents=True)
    report = scorefree / "report.json"
    report.write_text("report\n", encoding="utf-8")
    ledger = scorefree / "accepted-executions.txt"
    ledger.write_text("ledger\n", encoding="utf-8")
    completion = scorefree / "completion.txt"
    completion.write_text("\n".join([
        "disposition=stack-core-shell-shadow-licensed",
        "historical_scoring_licensed=true",
        f"report_sha256={_sha(report)}",
        f"accepted_execution_ledger_sha256={_sha(ledger)}",
    ]) + "\n", encoding="utf-8")
    return {
        "run_id": finish.RUN_ID, "output_prefix": finish.PREFIX,
        "historical_protocol_sha256": finish.HISTORICAL_PROTOCOL_SHA256,
        "execution_protocol_sha256": attempts.EXECUTION_PROTOCOL_SHA256,
        "cpu": "4", "memory": "16Gi", "timeout_seconds": "7200",
        "max_retries": "0", "uses_realized_outcomes": "false",
        "effect_fields_inspected": "false", "actual_scores_queried": "false",
        "treatment_constructed": "true", "production_change_licensed": "false",
        "historical_scoring_licensed": "true", "code_sha": "a" * 40,
        "image": "image@sha256:" + "b" * 64,
        "scorefree_report_sha256": _sha(report),
        "scorefree_completion_sha256": _sha(completion),
        "scorefree_accepted_execution_ledger_sha256": _sha(ledger),
        "finisher_sha256": _sha(Path(finish.__file__)),
        "attempt_manager_sha256": _sha(Path(attempts.__file__)),
        "runner_sha256": _sha(scripts / sources[0]),
        "aggregator_sha256": _sha(scripts / sources[1]),
        "source_loader_sha256": _sha(scripts / sources[2]),
        "canary_sha256": _sha(scripts / sources[3]),
        "canary_validator_sha256": _sha(scripts / sources[4]),
    }


def test_lock_finisher_binds_local_sources_and_positive_scorefree_license(
    tmp_path: Path, monkeypatch,
) -> None:
    manifest = _fixture(tmp_path)
    monkeypatch.setattr(finish, "ROOT", tmp_path)
    finish._validate_manifest(tmp_path, manifest)
    scorefree = tmp_path / "reports/stack-core-shell-runs" / \
        "20260816-stack-core-shell-scorefree-v1"
    (scorefree / "report.json").write_text("changed\n", encoding="utf-8")
    try:
        finish._validate_manifest(tmp_path, manifest)
    except RuntimeError as exc:
        assert "score-free binding differs" in str(exc)
    else:
        raise AssertionError("changed score-free report was accepted")


def test_lock_transport_preserves_real_canary_and_outcome_boundary() -> None:
    launcher = (REPO / "scripts/cloud_stack_core_shell_production_locks.sh").read_text(
        encoding="utf-8",
    )
    watcher = (
        REPO / "scripts/watch_stack_core_shell_production_lock_queue.sh"
    ).read_text(encoding="utf-8")
    assert "launch_cell 2023 1\nbash \"$CANARY\"" in launcher
    assert "released_after_canary=53" in launcher
    assert "actual_scores_queried=false" in launcher
    assert "--max-retries 0 --task-timeout 2h" in launcher
    assert "manage_stack_core_shell_lock_attempts.py" in watcher
    assert "finish_stack_core_shell_production_locks.py" in watcher
