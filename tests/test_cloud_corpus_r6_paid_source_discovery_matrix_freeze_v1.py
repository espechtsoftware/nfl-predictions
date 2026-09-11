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


def test_execution_parallelism_is_verified_against_the_job_not_the_task_count():
    """An execution always carries the JOB's parallelism, never its own.

    Cloud Run has no per-execution parallelism override -- `jobs execute`
    accepts --tasks only. So verify_execution must compare parallelism to the
    job's deployed value, not to taskCount. Comparing it to taskCount made
    task0 (one task under a job deployed at 54) impossible to verify, and since
    the 54-task phase verifies task0 as its predecessor, the entire
    materialization was unreachable. The 54-task case passed only by
    coincidence, because there taskCount happens to equal the job value.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    assert "JOB_PARALLELISM=54" in text
    assert '--argjson expected_parallelism "$JOB_PARALLELISM"' in text
    assert '--argjson expected_parallelism "$tasks"' not in text

    # --parallelism is not a valid `jobs execute` flag; passing it aborts the
    # submit outright, so it must not reappear.
    execute = text.split("gcloud run jobs execute", 1)[1].split("\n\n", 1)[0]
    assert "--parallelism" not in execute

    # task0 must still be a single task, and the cohort still 54.
    assert "mode=task0 tasks=1" in text
    assert "mode=$ACTION tasks=54" in text
