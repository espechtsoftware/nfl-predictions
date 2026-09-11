from __future__ import annotations

from pathlib import Path
import re
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
    assert 'trap "rm -rf -- \'$work\'" EXIT' in text
    assert "cleanup_container()" not in text
    assert "submit_output=$(gcloud builds submit" in text
    assert "grep -Eo '[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}'" in text
    assert '[[ "${#build_ids[@]}" -eq 1 ]]' in text
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


def test_container_cleanup_survives_local_scope_exit(tmp_path: Path) -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r'^  (trap "rm -rf -- \'\$work\'" EXIT)$', text, re.MULTILINE)
    assert match is not None
    work = tmp_path / "payload-work"
    shell = f"""
set -euo pipefail
container_scope() {{
  local work={work!s}
  mkdir -p "$work"
  : >"$work/payload.json"
  {match.group(1)}
}}
container_scope
[[ -f {work!s}/payload.json ]]
"""
    result = subprocess.run(
        ["bash", "-c", shell], text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not work.exists()


def test_execute_passes_parallelism_explicitly():
    """An execution must not inherit the job's parallelism.

    `verify_execution` requires parallelism == taskCount. task0 runs one task,
    so omitting --parallelism submits it at the job's configured 54 and it can
    never verify -- which makes the 54-task phase unreachable, since that phase
    verifies task0 as its predecessor before launching. The variable existed
    and was computed correctly; it simply was never passed.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    execute = text.split("gcloud run jobs execute", 1)[1].split("\n\n", 1)[0]
    assert "--parallelism" in execute, (
        "jobs execute must pass --parallelism; without it the execution "
        "inherits the job value and verify_execution refuses it"
    )
    assert '--parallelism "$parallelism"' in execute
    # Both branches must set it, or one mode silently reverts to the default.
    assert "tasks=54 parallelism=54" in text
    assert "tasks=1 parallelism=1" in text
