from __future__ import annotations

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile.corpus-r6-construction-allocation-snapshot"
BUILD = ROOT / "cloudbuild.corpus-r6-construction-allocation-snapshot.yaml"
LAUNCH = ROOT / "scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh"
RUNNER = ROOT / "scripts/run_corpus_r6_construction_allocation_snapshot_shard_v1.py"
GRADE_RUNNER = ROOT / "scripts/run_corpus_r6_construction_allocation_grade_v1.py"
GRADE_OPERATOR = (
    ROOT / "src/nfl_dfs/research/corpus_r6_construction_allocation_grade_operator_v1.py"
)


def test_release_surface_contains_real_selection_and_grade_paths() -> None:
    assert RUNNER.is_file(), "selection runner must exist before release"
    assert GRADE_RUNNER.is_file(), "dedicated grade runner must exist before release"
    assert GRADE_OPERATOR.is_file(), "dedicated grade operator must exist before release"
    docker = DOCKERFILE.read_text()
    build = BUILD.read_text()
    assert RUNNER.relative_to(ROOT).as_posix() in docker
    assert GRADE_RUNNER.relative_to(ROOT).as_posix() in docker
    assert "COPY src /app/src" in docker
    assert GRADE_RUNNER.relative_to(ROOT).as_posix() in build
    assert GRADE_OPERATOR.relative_to(ROOT).as_posix() in build
    assert "prepare_grade_manifest_v1" in build
    assert "publish_grade_v1" in build
    assert "reopen_grade_terminal_v1" in build
    assert "reopen_terminal_bundle_v1" in build
    assert "google-cloud-cli" in docker
    assert "SOURCE_COMMIT_SHA" in docker
    assert "COPY SOURCE_COMMIT /app/SOURCE_COMMIT" in docker
    assert "test ! -e reports" in build
    assert "test ! -e HANDOFF.md" in build


def test_launch_surface_is_existing_job_only_and_install_is_dormant() -> None:
    text = LAUNCH.read_text()
    lowered = "\n".join(
        path.read_text() for path in (LAUNCH, BUILD, DOCKERFILE)
    ).lower()
    assert "atlas-cbc-32g-full-2023-w8-v1" in text
    assert "1f4bcf0a-2300-4afa-9fc1-9981844c8275" in text
    assert text.count('gcloud run jobs update "$JOB"') == 1
    assert 'gcloud run jobs describe "$JOB"' in text
    assert 'gcloud run jobs execute "$JOB"' in text
    assert "disabled_install_only" in lowered
    assert "install_only:true" in lowered
    forbidden = (
        "run jobs create", "run jobs deploy", "run jobs delete",
        "run jobs list", "run jobs executions list", "scheduler",
        "gcloud iam", "add-iam-policy-binding",
    )
    for token in forbidden:
        assert token not in lowered
    assert re.search(
        r"gcloud\s+run\s+jobs\s+(?:create|deploy|delete|list)\b", lowered,
    ) is None
    assert re.search(
        r"gcloud\s+run\s+jobs\s+executions\s+list\b", lowered,
    ) is None


def test_every_required_phase_has_explicit_execution_args() -> None:
    text = LAUNCH.read_text()
    runner = RUNNER.read_text()
    for phase in (
        "prepare", "task0", "task", "collect", "reopen",
        "grade-prepare", "grade", "grade-reopen",
    ):
        assert re.search(rf"\b{phase}\b", text)
    assert "container-request,prepare" in text
    assert "container-request,task0" in text
    assert "container-request,collect" in text
    assert "container-request,reopen" in text
    assert "container-task" in text
    assert "container-grade,grade-prepare" in text
    assert "container-grade,grade" in text
    assert "container-grade,grade-reopen" in text
    assert 'tasks=54' in text
    assert 'tasks=1' in text
    assert "CLOUD_RUN_TASK_INDEX=0 CLOUD_RUN_TASK_COUNT=54" in text
    assert "NO_OUTCOME_SMOKE" in text
    assert "TARGET_OUTCOMES_ALLOWED" in text
    smoke_body = runner.split("def task0_smoke_v1(", 1)[1].split(
        "\ndef collect_v1(", 1,
    )[0]
    assert "publish=False" in smoke_body


def test_build_uses_exact_direct_git_with_narrow_outcome_blind_context() -> None:
    text = LAUNCH.read_text()
    build = BUILD.read_text()
    assert 'if [[ "${1:-}" == "build" ]]' in text
    assert "status --porcelain --untracked-files=all" in text
    assert "refs/remotes/origin/main" in text
    assert "https://github.com/espechtsoftware/nfl-predictions.git" in text
    assert 'gcloud builds submit "$source_repository"' in text
    assert '--git-source-revision "$build_code_sha"' in text
    assert ".source.gitSource == {url:$repository,revision:$sha}" in text
    assert (
        ".sourceProvenance.resolvedGitSource == "
        "{url:$repository,revision:$sha}"
    ) in text
    assert "prepare-outcome-blind-release-context" in build
    assert "dir: release" in build
    assert "printf '%s\\n' '${_CODE_SHA}' >release/SOURCE_COMMIT" in build
    assert "test ! -e release/reports" in build
    assert "test ! -e release/HANDOFF.md" in build
    assert "provider_git_source_is_full_repository:true" in text
    assert "outcome_artifacts_read_by_build_steps:false" in text
    assert "outcome_artifacts_in_runtime_image_context:false" in text
    archive_block = text.split("archive_paths=(", 1)[1].split("  )", 1)[0]
    assert "reports" not in archive_block
    assert "HANDOFF.md" not in archive_block


def test_provider_and_execution_receipts_bind_all_release_authorities() -> None:
    text = LAUNCH.read_text()
    for token in (
        "Cloud Build authority differs", "provider_resolved_image",
        "cloud_build_id", "code_sha", "image_digest", "job_generation",
        "execution_uid", "task_count", "manifest_identity",
        "runtime_build_attestation_identity",
        "runtime_execution_attestation_identity",
        "request_sha256", "no_outcome_smoke_mode",
    ):
        assert token in text
    assert ".metadata.uid == $uid" in text
    assert ".substitutions._CODE_SHA == $sha" in text
    assert ".substitutions._BUILD_IMAGE == $tag" in text
    assert ".digest == $digest" in text
    assert "runtime_build_attestation_v1" in text
    assert "validate_runtime_build_attestation_v1" in text
    assert "GCloudBuildProviderV1" in text
    assert "publish_create_once(attestation_uri, raw)" in text
    assert "status --porcelain --untracked-files=all" in text
    assert "refs/remotes/origin/main" in text


def test_collect_publishes_exact_terminal_task_execution_authority() -> None:
    text = LAUNCH.read_text()
    assert "R6_CONSTRUCTION_ALLOCATION_TASK_EXECUTION_NAME" in text
    assert 'gcloud run jobs executions describe "$task_execution_name"' in text
    assert "runtime_execution_attestation_v1" in text
    assert "validate_runtime_execution_attestation_v1" in text
    assert "provider_observed_at=completion_time" in text
    assert "succeeded_count != 54" in text
    assert 'spec.get("taskCount") != 54' in text
    assert "failed_count != 0" in text
    assert "cancelled_count != 0" in text
    assert "running_count != 0" in text
    assert "publish_create_once(attestation_uri, raw)" in text
    assert "runtime_execution_attestation_identity:$execution" in text
    assert '"uses_target_slate_outcomes"' in text


def test_grade_dispatch_delegates_to_dedicated_runner_without_inline_grader() -> None:
    text = LAUNCH.read_text()
    assert str(GRADE_RUNNER.relative_to(ROOT)) in text
    assert 'exec /usr/local/bin/python3.11 -I "$GRADE_RUNNER" "$command"' in text
    assert "R6_CONSTRUCTION_ALLOCATION_GRADE_ENABLED" in text
    assert "R6_CONSTRUCTION_ALLOCATION_GRADE_CODE_SHA" in text
    assert "R6_CONSTRUCTION_ALLOCATION_GRADE_RUNTIME_IMAGE" in text
    for duplicated_inline_token in (
        "grade_published_cross_v1", "validate_published_grade_v1",
        "_verified_lease_blob", "selection_reopened_before_outcome_join",
        "active_lease_revalidated_after_outcome_join",
    ):
        assert duplicated_inline_token not in text


def test_shell_contract_parses_and_container_help_is_side_effect_free() -> None:
    text = LAUNCH.read_text()
    heredoc_start = "<<'PY'\n"
    assert text.count(heredoc_start) == 2
    remaining = text
    embedded_blocks: list[str] = []
    for _ in range(2):
        remaining = remaining.split(heredoc_start, 1)[1]
        embedded, remaining = remaining.split("\nPY\n", 1)
        embedded_blocks.append(embedded)
    compile(embedded_blocks[0], "embedded-runtime-build-attestation.py", "exec")
    compile(embedded_blocks[1], "embedded-runtime-execution-attestation.py", "exec")
    syntax = subprocess.run(
        ["bash", "-n", str(LAUNCH)], cwd=ROOT, text=True, capture_output=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    help_result = subprocess.run(
        ["bash", str(LAUNCH), "container-help"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert help_result.stdout.strip() == (
        "container phases: prepare task0 task collect reopen "
        "grade-prepare grade grade-reopen"
    )
