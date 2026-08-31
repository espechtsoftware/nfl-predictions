from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import subprocess

import yaml

from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from scripts import run_corpus_r6_matchup_seven_pack_capture_v1 as runner


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "scripts/cloud_corpus_r6_matchup_seven_pack_capture_v1.sh"
RUNNER = ROOT / "scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py"
DOCKERFILE = ROOT / "Dockerfile.corpus-r6-matchup-seven-pack-capture"
DOCKERIGNORE = ROOT / "Dockerfile.corpus-r6-matchup-seven-pack-capture.dockerignore"
BUILD = ROOT / "cloudbuild.corpus-r6-matchup-seven-pack-capture.yaml"


def test_container_is_three_mode_default_off_and_cleanup_safe() -> None:
    text = SHELL.read_text(encoding="utf-8")
    assert "container modes: task0 publish reopen" in text
    assert "CORPUS_R6_MATCHUP_SEVEN_PACK_TASK0" in text
    assert "CORPUS_R6_MATCHUP_SEVEN_PACK_PUBLISH" in text
    assert "CORPUS_R6_MATCHUP_SEVEN_PACK_REOPEN" in text
    assert "R6_MATCHUP_SEVEN_PACK_OUTCOMES_ALLOWED" in text
    assert "--implementation-authority" in text
    assert "mktemp -d /tmp/matchup-seven-pack.XXXXXX" in text
    assert 'rm -rf "$work"' in text
    assert "CLOUD_RUN_TASK_COUNT" in text
    assert "CLOUD_RUN_TASK_ATTEMPT" in text


def test_host_reuses_one_exact_job_and_requires_terminal_task0() -> None:
    lowered = SHELL.read_text(encoding="utf-8").lower()
    assert "expected_job_uid=1f4bcf0a-2300-4afa-9fc1-9981844c8275" in lowered
    assert "gcloud run jobs update" in lowered
    assert "gcloud run jobs execute" in lowered
    assert "gcloud run jobs executions describe" in lowered
    assert "gcloud logging read" in lowered
    assert "publish requires one exact successful task0 execution" in lowered
    assert "task0 launch gate differs" in lowered
    assert "latest execution is not terminal success" in lowered
    assert "gcloud run jobs create" not in lowered
    assert "gcloud run jobs delete" not in lowered
    assert "gcloud run jobs list" not in lowered
    assert "gcloud storage" not in lowered
    assert "add-iam-policy-binding" not in lowered


def test_build_is_git_source_bound_outcome_blind_and_git_free_at_runtime() -> None:
    build_text = BUILD.read_text(encoding="utf-8")
    parsed = yaml.safe_load(build_text)
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    dockerignore = DOCKERIGNORE.read_text(encoding="utf-8")
    assert parsed["timeout"] == "3600s"
    assert "_IMPLEMENTATION_AUTHORITY_SHA" in build_text
    assert "build-implementation-authority" in build_text
    assert "test ! -e release/.git" in build_text
    assert "test ! -e release/reports" in build_text
    assert "test ! -e release/sql" in build_text
    assert "--network none" in build_text
    assert "SEVEN_PACK_IMPLEMENTATION_AUTHORITY.json" in dockerfile
    assert "google-cloud-bigquery==3.43.0" in dockerfile
    assert "google-cloud-storage==3.13.1" in dockerfile
    assert "COPY .git" not in dockerfile
    assert "COPY reports" not in dockerfile
    assert "!src/**" in dockerignore


def test_shell_parses_and_help_has_no_external_action() -> None:
    syntax = subprocess.run(
        ["bash", "-n", str(SHELL)], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert syntax.returncode == 0, syntax.stderr
    result = subprocess.run(
        ["bash", str(SHELL), "container-help"], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "container modes: task0 publish reopen"


def test_runner_exposes_local_authority_and_post_reopen_plan_freezer() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert "build-implementation-authority" in text
    assert "freeze-capture-plan" in text
    assert "_write_capture_plan_create_once" in text
    assert "CORPUS_R6_MATCHUP_CAPTURE_PLAN_V3_FREEZE" not in text
    # The variable is referenced through the bridge constant, avoiding a
    # second string authority in the CLI.
    assert "plan_bridge.FREEZE_ENABLE_ENV" in text


def test_capture_plan_freezer_writes_exact_canonical_newline_bytes(
    tmp_path: Path,
) -> None:
    plan = {"schema_version": "fixture-plan", "value": 7}
    raw = source.canonical_json_bytes(plan) + b"\n"
    result = {
        "capture_plan_relative_path": "config/fixture-plan.json",
        "capture_plan": plan,
        "capture_plan_sha256": sha256(raw).hexdigest(),
        "capture_plan_bytes": len(raw),
    }
    path = runner._write_capture_plan_create_once(
        repository_root=tmp_path.resolve(), result=result
    )
    assert path.read_bytes() == raw
    assert not path.read_bytes().endswith(b"\n\n")
