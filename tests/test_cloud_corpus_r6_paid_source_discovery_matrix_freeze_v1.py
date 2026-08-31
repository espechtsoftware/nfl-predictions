from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.sh"


def test_cloud_shell_is_syntax_valid_and_default_off() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    result = subprocess.run(
        ["bash", str(SCRIPT), "container-help"],
        check=True, capture_output=True, text=True,
    )
    assert result.stdout.strip() == "container modes: task0 task reopen-task"
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--max-retries 0" in text
    assert "--tasks 54 --parallelism 54" in text
    assert "jobs executions list" not in text
    assert "storage ls" not in text
    assert "task0)" in text
    assert "task0-gate" in text
    assert "extract_task0_receipt" in text
    assert "gcloud logging read" in text
    assert "TASK0_GATE_B64" in text
    assert 'structured = row.get("jsonPayload")' in text
    assert '.spec.template.spec.timeoutSeconds == "21600"' in text
    assert "reopen-task)" in text
    assert "reopen-collect)" in text
    assert "rm -rf \"$tmp\"" in text
    assert "IMAGE_SOURCE_COMMIT_SHA=$CODE_SHA" not in text
    assert "cat /app/SOURCE_COMMIT" in text


def test_container_fails_before_payload_without_enable_gate() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "container-run", "task"],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 2
    assert "matrix freezer disabled" in result.stderr
