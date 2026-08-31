from __future__ import annotations

import base64
import gzip
from hashlib import sha256
from pathlib import Path
import re
import subprocess

import yaml

from nfl_dfs.research import paid_source_ablation_execution_v1 as execution
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry


ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh"
RUNNER = ROOT / "scripts/run_corpus_r6_paid_source_fp_sis_v1.py"
DOCKERFILE = ROOT / "Dockerfile.corpus-r6-paid-source-fp-sis"
DOCKERIGNORE = ROOT / "Dockerfile.corpus-r6-paid-source-fp-sis.dockerignore"
BUILD = ROOT / "cloudbuild.corpus-r6-paid-source-fp-sis.yaml"


def test_container_dispatch_is_narrow_default_off_and_cleanup_safe() -> None:
    text = LAUNCH.read_text(encoding="utf-8")
    assert str(RUNNER.relative_to(ROOT)) in text
    assert (
        "container modes: validate task0 task collect reopen grade grade-reopen"
        in text
    )
    for mode in (
        "validate", "task0", "task", "collect", "reopen", "grade",
        "grade-reopen",
    ):
        assert re.search(rf"\b{re.escape(mode)}\b", text)
    assert "--task0-receipt" in text
    assert "--execute" in text
    assert "mktemp -d /tmp/paid-source-fp-sis.XXXXXX" in text
    assert 'trap cleanup_paid_source_request EXIT' in text
    assert 'rm -rf "$work"' in text
    assert "exec /usr/local/bin/python" not in text
    assert "R6_PAID_SOURCE_FP_SIS_REQUEST_SHA256" in text
    assert "R6_PAID_SOURCE_FP_SIS_TASK0_RECEIPT_SHA256" in text
    assert "R6_PAID_SOURCE_FP_SIS_TASK0_PROVIDER_GATE_SHA256" in text
    assert "R6_PAID_SOURCE_FP_SIS_TASK0_PROVIDER_GATE_B64" in text
    assert "--task0-provider-gate" in text
    assert "R6_PAID_SOURCE_FP_SIS_SLATE_PUBLICATIONS_SHA256" in text
    assert "R6_PAID_SOURCE_FP_SIS_SLATE_PUBLICATIONS_GZIP_B64" in text
    assert "gzip -n -9" in text
    assert "sha256sum" in text
    assert "MAX_REQUEST_BYTES=16777216" in text
    assert "MAX_ENV_B64_BYTES=30000" in text


def test_host_release_reuses_one_exact_job_and_binds_the_full_chain() -> None:
    text = LAUNCH.read_text(encoding="utf-8")
    lowered = text.lower()
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
    assert "disabled_install_only" in lowered
    assert "publication manifest differs from exact 54-task execution" in lowered
    assert "task0 provider gate differs from exact execution" in lowered
    assert "validate-task0-cloud-gate" in lowered
    assert "54-task execution request/task0 provider binding differs" in lowered
    assert "runtime_build_attestation_identity" in text
    assert "runtime-build-attestation.json" in text
    assert "attestation_create_once_exact_reopened" in text
    assert "build-request" in text
    assert '"$action" == "prepare"' in text
    assert "serviceAccountName" in text
    assert "provider_execution_spec" in text
    assert "provider_execution_spec_sha256" in text
    assert "paid-source-fp-sis-build.xxxxxx" in lowered
    assert "paid-source-fp-sis-host.xxxxxx" in lowered
    assert "trap cleanup_host_build exit" in lowered
    assert "trap cleanup_host_release exit" in lowered
    launch_call = text.index('gcloud run jobs execute "$JOB"')
    assert text.index("validate-task0-cloud-gate") < launch_call
    assert text.index("publication manifest differs from exact 54-task execution") < launch_call
    assert "automatic-policy" not in lowered
    assert "promote" not in lowered


def test_host_full54_has_no_manual_or_private_task0_receipt_artifact() -> None:
    text = LAUNCH.read_text(encoding="utf-8")
    help_block = text[text.index("host-help") : text.index("PROJECT=")]
    assert "prepare IMAGE@sha256:DIGEST" in help_block
    assert "task REQUEST TASK0_EXECUTION" in help_block
    assert "collect REQUEST TASK0_EXECUTION" in help_block
    assert "task0-receipt.json TASK0_EXECUTION" not in help_block
    assert 'task0_path="$work/task0-receipt.json"' in text
    assert "--task0-receipt \"$task0_path\"" not in text


def test_clean_build_is_exact_git_and_runtime_contains_reopen_history() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    dockerignore = DOCKERIGNORE.read_text(encoding="utf-8")
    build_text = BUILD.read_text(encoding="utf-8")
    parsed = yaml.safe_load(build_text)
    assert parsed["timeout"] == "3600s"
    assert "git clone '${_SOURCE_REPOSITORY}' release" in build_text
    assert "git -C release checkout --detach '${_CODE_SHA}'" in build_text
    assert "SOURCE_COMMIT_SHA=${_CODE_SHA}" in build_text
    assert "--network none" in build_text
    assert "COPY . /app" in dockerfile
    assert 'git -C /app rev-parse HEAD' in dockerfile
    assert "numpy==2.5.1" in dockerfile
    assert "scipy==1.18.0" in dockerfile
    assert ".git" not in dockerignore.splitlines()


def test_exact_54_publication_manifest_fits_compressed_env_ceiling() -> None:
    rows: list[dict[str, object]] = []
    for ordinal in range(54):
        digest = sha256(f"slate-{ordinal}".encode()).hexdigest()
        body: dict[str, object] = {
            "schema_version": execution.TASK_PUBLICATION_SCHEMA,
            "source_task_ordinal": ordinal,
            "slate": f"20{22 + ordinal // 18}-w{ordinal % 18 + 1:02d}",
            "slate_result_identity": {
                "uri": (
                    "gs://nfl-predictions-503414-corpus-retrieval/research/"
                    f"corpus-r6-paid-source-fp-sis/run/tasks/{ordinal:04d}.json"
                ),
                "generation": str(10_000_000_000 + ordinal),
                "sha256": digest,
                "bytes": 10_000_000 + ordinal,
                "create_once": True,
            },
            "slate_result_sha256": sha256(
                f"result-{ordinal}".encode()
            ).hexdigest(),
            "task0_provider_gate_sha256": "a" * 64,
            "one_slate_only": True,
            "matrix_body_read_count": 1,
            "complete": True,
            **execution._policy(uses_realized_outcomes=False),
        }
        body["slate_publication_sha256"] = registry.canonical_sha256(body)
        rows.append(body)
    manifest = {
        "schema_version": (
            "corpus-r6-paid-source-fp-sis-slate-publication-manifest/v1"
        ),
        "slate_publications": rows,
        "slate_publication_manifest_sha256": registry.canonical_sha256(rows),
    }
    raw = registry.canonical_json_bytes(manifest)
    encoded = base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0))
    assert len(raw) > 30_000
    assert len(encoded) <= 30_000


def test_shell_parses_and_help_is_side_effect_free() -> None:
    syntax = subprocess.run(
        ["bash", "-n", str(LAUNCH)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr
    result = subprocess.run(
        ["bash", str(LAUNCH), "container-help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "container modes: validate task0 task collect reopen grade grade-reopen"
    )
    host = subprocess.run(
        ["bash", str(LAUNCH), "host-help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert host.returncode == 0, host.stderr
    for phase in (
        "prepare IMAGE@sha256:DIGEST", "task0 REQUEST", "task REQUEST",
        "task-manifest", "collect REQUEST",
        "reopen REOPEN_REQUEST", "grade GRADE_REQUEST",
        "grade-reopen GRADE_REOPEN_REQUEST",
    ):
        assert phase in host.stdout
