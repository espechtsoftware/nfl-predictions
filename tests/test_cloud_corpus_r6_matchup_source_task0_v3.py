from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/cloud_corpus_r6_matchup_source_task0_v3.sh"
DOCKERFILE = ROOT / "Dockerfile.corpus-r6-matchup-source-v3"
CLOUDBUILD = ROOT / "cloudbuild.corpus-r6-matchup-source-v3.yaml"


def test_controller_is_syntax_valid_and_exposes_only_explicit_container_modes() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    result = subprocess.run(
        ["bash", str(SCRIPT), "container-help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "container modes: worker verify publish reopen"


def test_controller_requires_provider_bound_worker_verifier_and_publish_receipts() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "EXPECTED_JOB_UID=1f4bcf0a-2300-4afa-9fc1-9981844c8275" in text
    assert "--max-retries 0" in text
    assert "--async --format=json" in text
    assert "execution=$(jq -er '.metadata.name'" in text
    assert "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER" in text
    assert "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFY" in text
    assert "sourceProvenance.resolvedGitSource.revision == $code" in text
    assert "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFIER_EXECUTION" in text
    assert "--action bind-provider-receipt" not in text
    assert "--action validate-provider-receipt" in text
    assert "bind_controller_provider_receipt" in text
    assert "persist_controller_artifact" in text
    assert "_exact_reopen_provider_receipt_v3" in text
    assert ".provider_execution_spec.phase == \"worker\"" in text
    assert ".provider_execution_spec.phase == \"verify\"" in text
    assert ".operator_output.worker_result_identity" in text
    assert "cp \"$work/worker.json\" \"$payload\"" in text
    assert (
        'cp "$work/verifier.json.provider-receipt.identity.json" "$payload"'
        in text
    )
    assert "--action validate-receipt" not in text
    assert '"$action" =~ ^(worker|verify|publish|reopen|result)$' in text
    assert '"container-run","reopen"' in text
    assert "write_inventory_count == 0" in text
    assert "CORPUS_R6_MATCHUP_SOURCE_V3_PUBLISHER_EXECUTION" in text


def test_controller_deep_validates_provider_execution_and_exact_payload() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert '.metadata.labels["run.googleapis.com/jobUid"] == $expected_job_uid' in text
    assert '.metadata.labels["run.googleapis.com/jobGeneration"]' in text
    assert ".spec.taskCount == 1 and .spec.parallelism == 1" in text
    assert '(.spec.template.spec.timeoutSeconds | tostring) == "86400s"' in text
    assert '$container.command == ["/bin/bash"]' in text
    assert '"container-run",$phase' in text
    assert '$container.resources.limits == {"cpu":"8","memory":"32Gi"}' in text
    assert "$env.IMAGE_DIGEST == $digest" in text
    assert "$env.CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_REFERENCE == $image" in text
    assert "$env.CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_SOURCE_COMMIT == $code" in text
    assert "payload base64 is not canonical" in text
    assert "MAX_PAYLOAD_BYTES=262144" in text
    assert "MAX_PAYLOAD_BASE64_BYTES=30000" in text
    assert text.count('gzip -n -9 -c') == 2
    assert 'gzip -t "$compressed"' in text
    assert 'gzip -dc "$compressed" >"$target"' in text
    assert "payload gzip encoding is not exact deterministic gzip-n9" in text
    assert 'command -v gzip >/dev/null' in text
    assert "payload_sha256:$payload_sha" in text
    assert "payload_bytes:($payload_bytes | tonumber)" in text
    assert "bound_worker_execution:" in text
    assert "bound_verifier_execution:" in text
    assert "corpus-r6-matchup-source-task0-provider-execution-spec/v3" in text


def test_commit_b_build_preserves_exact_clean_git_runtime() -> None:
    docker = DOCKERFILE.read_text(encoding="utf-8")
    build = CLOUDBUILD.read_text(encoding="utf-8")
    assert "FROM python:3.11-slim" in docker
    assert "COPY . /app" in docker
    assert "git ca-certificates gzip jq libgomp1" in " ".join(docker.split())
    assert "git -C /app rev-parse HEAD" in docker
    assert "git -C /app rev-parse --is-shallow-repository" in docker
    assert "git -C /app status --porcelain --untracked-files=all" in docker
    assert 'pip install --no-cache-dir --editable ".[gcp]"' in docker
    assert "run_corpus_r6_matchup_source_task0_v3.py --help" in docker
    assert "run_corpus_r6_matchup_source_batch_v3.py --help" in docker
    assert "_trusted_dependency_closure_v3" in docker
    assert "_trusted_capture_plan_v3" in docker
    assert "git -C release fetch --no-tags origin '${_CODE_SHA}'" in build
    assert "--depth=1" not in build
    assert "git -C release checkout --detach '${_CODE_SHA}'" in build
    assert "git -C release rev-parse --is-shallow-repository" in build
    assert "pip install --no-cache-dir --editable '.[gcp]'" in build
    assert "_trusted_dependency_closure_v3" in build
    assert "_trusted_capture_plan_v3" in build
    assert "isolated-controller-smoke" in build
    assert build.count("docker run --rm --network none '${_BUILD_IMAGE}'") == 3
    assert "run_corpus_r6_matchup_source_task0_v3.py" in build
    assert "run_corpus_r6_matchup_source_batch_v3.py" in build
