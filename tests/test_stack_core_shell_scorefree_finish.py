from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = str(REPO / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import finish_stack_core_shell_scorefree as finish  # noqa: E402
import manage_stack_core_shell_scorefree_attempts as attempts  # noqa: E402


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    sources = (
        "run_stack_core_shell_scorefree.py",
        "aggregate_stack_core_shell_scorefree.py",
        "stack_core_shell_sources.py",
        "cloud_wait_stack_core_shell_scorefree_canary.sh",
        "validate_stack_core_shell_scorefree_canary.py",
    )
    for name in sources:
        (scripts / name).write_bytes((REPO / "scripts" / name).read_bytes())
    support = tmp_path / "reports/stack-core-shell-support-runs" / \
        "20260816-stack-core-shell-control-support-census-v1"
    support.mkdir(parents=True)
    (support / "report.json").write_text("report\n", encoding="utf-8")
    (support / "completion.txt").write_text("completion\n", encoding="utf-8")
    (support / "accepted-executions.txt").write_text("ledger\n", encoding="utf-8")
    manifest = {
        "run_id": finish.RUN_ID, "output_prefix": finish.PREFIX,
        "execution_protocol_sha256": attempts.EXECUTION_PROTOCOL_SHA256,
        "cpu": "4", "memory": "16Gi", "timeout_seconds": "14400",
        "max_retries": "0", "uses_realized_outcomes": "false",
        "effect_fields_inspected": "false", "treatment_constructed": "true",
        "production_change_licensed": "false",
        "historical_scoring_licensed": "false", "code_sha": "a" * 40,
        "image": "image@sha256:" + "b" * 64,
        "support_report_sha256": _sha(support / "report.json"),
        "support_completion_sha256": _sha(support / "completion.txt"),
        "support_accepted_execution_ledger_sha256": _sha(
            support / "accepted-executions.txt"
        ),
        "finisher_sha256": _sha(Path(finish.__file__)),
        "attempt_manager_sha256": _sha(Path(attempts.__file__)),
        "runner_sha256": _sha(scripts / sources[0]),
        "aggregator_sha256": _sha(scripts / sources[1]),
        "source_loader_sha256": _sha(scripts / sources[2]),
        "canary_sha256": _sha(scripts / sources[3]),
        "canary_validator_sha256": _sha(scripts / sources[4]),
    }
    return support, manifest


def test_scorefree_finisher_binds_local_sources_and_support(
    tmp_path: Path, monkeypatch,
) -> None:
    support, manifest = _fixture(tmp_path)
    monkeypatch.setattr(finish, "ROOT", tmp_path)
    finish._validate_manifest(tmp_path, manifest)
    (support / "report.json").write_text("changed\n", encoding="utf-8")
    try:
        finish._validate_manifest(tmp_path, manifest)
    except RuntimeError as exc:
        assert "support binding differs" in str(exc)
    else:
        raise AssertionError("changed support report was accepted")
