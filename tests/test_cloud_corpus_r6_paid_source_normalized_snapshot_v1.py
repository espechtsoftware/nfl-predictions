from __future__ import annotations

from pathlib import Path
import re
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh"
RUNNER = ROOT / "scripts/run_corpus_r6_paid_source_normalized_snapshot_v1.py"
DOCKERFILE = ROOT / "Dockerfile.corpus-r6-paid-source-normalized-snapshot"
DOCKERIGNORE = ROOT / "Dockerfile.corpus-r6-paid-source-normalized-snapshot.dockerignore"
BUILD = ROOT / "cloudbuild.corpus-r6-paid-source-normalized-snapshot.yaml"


def test_container_dispatch_is_narrow_exact_and_cleanup_safe() -> None:
    text = LAUNCH.read_text(encoding="utf-8")
    assert str(RUNNER.relative_to(ROOT)) in text
    assert "container modes: task0 publish reopen" in text
    for mode in ("task0", "publish", "reopen"):
        assert re.search(rf"\b{mode}\b", text)
    assert "--task0-receipt" in text
    assert "--terminal-identity" in text
    assert "--repository-root" in text
    assert "--execute" in text
    assert "mktemp -d /tmp/paid-source-normalized-snapshot.XXXXXX" in text
    assert "trap cleanup_normalized_snapshot_payload EXIT" in text
    assert 'rm -rf "$work"' in text
    assert "exec /usr/local/bin/python" not in text
    assert "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_PAYLOAD_SHA256" in text
    assert "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_TASK0_RECEIPT_SHA256" in text
    assert "sha256sum" in text
    assert "MAX_PAYLOAD_BYTES=16777216" in text


def test_host_release_is_existing_job_only_exact_and_default_off() -> None:
    lowered = LAUNCH.read_text(encoding="utf-8").lower()
    for forbidden in (
        "gcloud run jobs create",
        "gcloud run jobs delete",
        "gcloud run jobs list",
        "gcloud storage",
        "add-iam-policy-binding",
    ):
        assert forbidden not in lowered
    assert "gcloud builds submit" in lowered
    assert "gcloud run jobs update" in lowered
    assert "gcloud run jobs execute" in lowered
    assert "expected_job_uid=1f4bcf0a-2300-4afa-9fc1-9981844c8275" in lowered
    assert "latest execution is not terminal-success" in lowered
    assert "disabled_install_only" in lowered
    assert "exact successful task0 execution" in lowered
    assert "task0 launch gate differs" in lowered
    assert "exact_execution_stdout_only:true" in lowered
    assert "paid-source-normalized-snapshot-build.xxxxxx" in lowered
    assert "paid-source-normalized-snapshot-launch.xxxxxx" in lowered
    assert "trap cleanup_build exit" in lowered
    assert "trap cleanup_host exit" in lowered
    assert "automatic-policy" not in lowered
    assert "promote" not in lowered


def test_clean_build_is_direct_git_narrow_and_outcome_blind() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    dockerignore = DOCKERIGNORE.read_text(encoding="utf-8")
    build_text = BUILD.read_text(encoding="utf-8")
    parsed = yaml.safe_load(build_text)
    assert parsed["timeout"] == "3600s"
    assert "_MODULE_SHA" in build_text
    assert "SOURCE_COMMIT_SHA=${_CODE_SHA}" in build_text
    assert "SNAPSHOT_MODULE_SHA256=${_MODULE_SHA}" in build_text
    assert "test ! -e release/.git" in build_text
    assert "test ! -e release/reports" in build_text
    assert "test ! -e release/sql" in build_text
    assert "test ! -e release/HANDOFF.md" in build_text
    assert "--network none" in build_text
    assert "IMAGE_SOURCE_COMMIT_SHA" in dockerfile
    assert "R6_PAID_SOURCE_NORMALIZED_SNAPSHOT_MODULE_SHA256" in dockerfile
    assert "google-cloud-bigquery==3.43.0" in dockerfile
    assert "google-cloud-storage==3.13.1" in dockerfile
    assert "COPY src /app/src" in dockerfile
    assert "!src/**" in dockerignore
    for forbidden in ("reports", "HANDOFF.md", "CLAUDE.md", ".git"):
        assert f"COPY {forbidden}" not in dockerfile


def test_shell_parses_and_help_is_side_effect_free() -> None:
    syntax = subprocess.run(
        ["bash", "-n", str(LAUNCH)], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert syntax.returncode == 0, syntax.stderr
    result = subprocess.run(
        ["bash", str(LAUNCH), "container-help"], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "container modes: task0 publish reopen"

    disabled = subprocess.run(
        ["bash", str(LAUNCH)], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert disabled.returncode == 2
    assert "usage:" in disabled.stderr
