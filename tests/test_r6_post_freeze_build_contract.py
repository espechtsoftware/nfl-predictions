"""Offline contract for the dedicated immutable R6 post-freeze image."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile.r6-post-freeze"
BUILD_CONFIG = ROOT / "cloudbuild.r6-post-freeze.yaml"
BUILD_IGNORE = ROOT / "deploy" / "r6_post_freeze_build.gcloudignore"

MODULES = (
    "lr8_label_fit_adapter",
    "lr8_label_score_map",
    "lr8_later_period_evaluation",
    "corpus_realized_outcome_transport",
    "corpus_r6_full_union_panel_freeze_v1",
    "corpus_r6_full_union_panel_freeze_release_v1",
    "corpus_r6_full_union_outcome_snapshot_v1",
    "corpus_r6_full_union_outcome_supply_v1",
    "corpus_r6_full_union_realized_grading_v1",
    "corpus_r6_full_union_grade_release_v1",
    "corpus_r6_full_union_score_report_v1",
)
RUNNERS = (
    "scripts/compile_corpus_r6_full_union_query_v1.py",
    "scripts/run_corpus_r6_full_union_panel_freeze_v1.py",
    "scripts/run_corpus_r6_full_union_outcome_snapshot_v1.py",
    "scripts/run_corpus_r6_full_union_outcome_supply_v1.py",
    "scripts/run_corpus_r6_full_union_realized_grade_v1.py",
    "scripts/validate_r6_full_union_lane_terminal_v1.py",
    "scripts/report_corpus_r6_full_union_scores_v1.py",
    "scripts/historical_outcome_lease.py",
)
ORCHESTRATOR = "scripts/cloud_r6_full_union_score_chain_v1.sh"
FREEZE_LAUNCHER = "scripts/run_r6_full_union_freeze_cloud_v1.sh"
SHELL_SCRIPTS = (FREEZE_LAUNCHER, ORCHESTRATOR)
FOCUSED_TESTS = (
    "tests/test_compile_corpus_r6_full_union_query_v1.py",
    "tests/test_lr8_label_fit_adapter.py",
    "tests/test_lr8_label_score_map.py",
    "tests/test_lr8_later_period_evaluation.py",
    "tests/test_corpus_realized_outcome_transport.py",
    "tests/test_corpus_r6_full_union_panel_freeze_v1.py",
    "tests/test_corpus_r6_full_union_outcome_snapshot_v1.py",
    "tests/test_run_corpus_r6_full_union_outcome_snapshot_v1.py",
    "tests/test_corpus_r6_full_union_outcome_supply_v1.py",
    "tests/test_run_corpus_r6_full_union_outcome_supply_v1.py",
    "tests/test_corpus_r6_full_union_realized_grading_v1.py",
    "tests/test_corpus_r6_full_union_grade_release_v1.py",
    "tests/test_run_corpus_r6_full_union_realized_grade_v1.py",
    "tests/test_corpus_r6_full_union_score_report_v1.py",
    "tests/test_validate_r6_full_union_lane_terminal_v1.py",
    "tests/test_run_r6_full_union_freeze_terminal_contract.py",
    "tests/test_historical_outcome_lease.py",
    "tests/test_cloud_r6_full_union_score_chain_v1.py",
    "tests/test_r6_post_freeze_build_contract.py",
)
FOCUSED_BUILD_TOOLS = (
    "awk", "bash", "cat", "chmod", "cmp", "date", "dirname", "env", "git",
    "jq", "ln", "mkdir", "mktemp", "pip", "python", "python3", "rm",
    "sha256sum", "sleep", "tr", "wc",
)
IMAGE_SMOKE_TOOLS = ("bash", "git", "jq", "python", "sha256sum")
METADATA_SOURCES = (
    "Dockerfile.r6-post-freeze",
    "cloudbuild.r6-post-freeze.yaml",
    "deploy/r6_post_freeze_build.gcloudignore",
    *(f"src/nfl_dfs/research/{module}.py" for module in MODULES),
    *RUNNERS,
    *SHELL_SCRIPTS,
    "tests/test_r6_post_freeze_build_contract.py",
)


def test_required_post_freeze_sources_are_present() -> None:
    required = tuple(
        ROOT / "src" / "nfl_dfs" / "research" / f"{module}.py"
        for module in MODULES
    ) + tuple(ROOT / runner for runner in RUNNERS) + tuple(
        ROOT / script for script in SHELL_SCRIPTS
    )
    assert all(path.is_file() for path in required)


def test_dockerfile_proves_commit_and_smoke_imports_complete_boundary() -> None:
    source = DOCKERFILE.read_text(encoding="utf-8")
    assert "ARG SOURCE_COMMIT" in source
    assert source.count('git rev-parse --verify HEAD)" = "${SOURCE_COMMIT}') == 3
    assert source.count("git status --porcelain=v1 --untracked-files=all") == 3
    assert source.count("git clean -ffdX") == 2
    assert 'apt-get install -y --no-install-recommends bash ca-certificates git jq libgomp1' in source
    assert 'pip install --no-cache-dir ".[gcp]"' in source
    expected_tools = " ".join(IMAGE_SMOKE_TOOLS)
    assert (
        f'for tool in {expected_tools}; do command -v "${{tool}}" >/dev/null; done'
        in source
    )
    for module in MODULES:
        assert module in source
    for runner in RUNNERS:
        assert f"python {runner} --help >/dev/null" in source
    for script in SHELL_SCRIPTS:
        assert f"bash -n {script}" in source
    assert f"bash {ORCHESTRATOR} help >/dev/null" in source
    assert "explicit command required" in source


def test_build_fetches_exact_pushed_commit_and_tests_before_push() -> None:
    source = BUILD_CONFIG.read_text(encoding="utf-8")
    assert "[[ '${_SOURCE_COMMIT}' =~ ^[0-9a-f]{40}$ ]]" in source
    assert "git fetch --depth=1 origin '${_SOURCE_COMMIT}'" in source
    assert "git checkout --detach FETCH_HEAD" in source
    assert source.count("git rev-parse --verify HEAD") >= 3
    assert "git status --porcelain=v1 --untracked-files=all" in source
    for test in FOCUSED_TESTS:
        assert source.count(test) >= 2  # execution list and build metadata
    assert source.index("focused-post-freeze-contract-tests") < source.index(
        "docker push"
    )
    assert source.index("git clean -ffdX") < source.index("docker build")
    assert "pytest" in source
    assert "tests/" in source
    assert "pytest tests" not in source


def test_focused_test_container_proves_required_os_tools() -> None:
    config = yaml.safe_load(BUILD_CONFIG.read_text(encoding="utf-8"))
    focused_test_shell = config["steps"][1]["args"][-1].replace("$$", "$")
    assert "apt-get install -y --no-install-recommends git jq libgomp1" in (
        focused_test_shell
    )
    expected = (
        "required_tools=(\n"
        "  awk bash cat chmod cmp date dirname env git jq ln mkdir mktemp pip\n"
        "  python python3 rm sha256sum sleep tr wc\n"
        ")"
    )
    assert expected in focused_test_shell
    assert 'for tool in "${required_tools[@]}"; do' in focused_test_shell
    assert 'command -v "${tool}" >/dev/null' in focused_test_shell
    declared = tuple(
        focused_test_shell.split("required_tools=(", 1)[1]
        .split(")", 1)[0]
        .split()
    )
    assert declared == FOCUSED_BUILD_TOOLS


def test_build_pushes_tag_then_uses_only_resolved_digest_for_smoke() -> None:
    source = BUILD_CONFIG.read_text(encoding="utf-8")
    assert ":r6-post-freeze-${_SOURCE_COMMIT}-${BUILD_ID}" in source
    # The sole occurrence is the metadata writer's explicit rejection guard,
    # never a tag declaration or runtime reference.
    assert source.count(":latest") == 1
    assert '":latest" in image_tag' in source
    assert source.index("docker push") < source.index("RepoDigests")
    assert source.index("RepoDigests") < source.index(
        "smoke-import-immutable-digest"
    )
    smoke = source.split("id: smoke-import-immutable-digest", 1)[1].split(
        "id: write-machine-readable-build-metadata", 1
    )[0]
    assert "docker pull \"$${digest_ref}\"" in smoke
    assert "\"$${digest_ref}\" bash -ceu" in smoke
    assert "r6-post-freeze-${_SOURCE_COMMIT}-${BUILD_ID}" not in smoke
    for module in MODULES:
        assert module in smoke
    for runner in RUNNERS:
        assert f"python {runner} --help >/dev/null" in smoke
    for script in SHELL_SCRIPTS:
        assert f"bash -n {script}" in smoke
    assert f"bash {ORCHESTRATOR} help >/dev/null" in smoke


def test_build_emits_canonical_audit_metadata_without_mutation_authority() -> None:
    source = BUILD_CONFIG.read_text(encoding="utf-8")
    assert '"schema_version": "r6-full-union-post-freeze-build/v1"' in source
    assert '"source_commit": source_commit' in source
    assert '"immutable_image": immutable_image' in source
    assert '"image_digest": match.group(1)' in source
    assert "identity_paths = tuple(dict.fromkeys((*sources, *tests)))" in source
    assert "if not path.is_file() or path.is_symlink():" in source
    assert "for name in identity_paths" in source
    for path in METADATA_SOURCES:
        assert path in source
    assert 'json.dumps(payload, sort_keys=True, separators=(",", ":"))' in source
    assert "r6-post-freeze-build-metadata.json" in source
    assert "artifacts:" in source
    for flag in (
        "uses_realized_outcomes",
        "historical_outcome_lease_acquired",
        "query_executed",
        "scoring_executed",
        "job_mutation_licensed",
        "iam_mutation_licensed",
        "graph_mutation_licensed",
        "production_change_licensed",
        "decision_authority",
    ):
        assert f'"{flag}": False' in source
    forbidden = (
        "gcloud run jobs",
        "gcloud projects",
        "add-iam-policy-binding",
        "neo4j",
        "deploy/deploy_jobs.sh",
    )
    assert not any(token in source.lower() for token in forbidden)


def test_submission_context_is_scoped_to_the_build_config() -> None:
    assert BUILD_IGNORE.read_text(encoding="utf-8") == (
        "**\n!cloudbuild.r6-post-freeze.yaml\n"
    )


def test_cloud_build_schema_and_inline_metadata_writer_parse_offline() -> None:
    config = yaml.safe_load(BUILD_CONFIG.read_text(encoding="utf-8"))
    assert [step["id"] for step in config["steps"]] == [
        "exact-pushed-detached-checkout",
        "focused-post-freeze-contract-tests",
        "build-exact-commit-tag",
        "push-tag-and-resolve-immutable-digest",
        "smoke-import-immutable-digest",
        "write-machine-readable-build-metadata",
    ]
    metadata_shell = config["steps"][-1]["args"][-1]
    focused_test_shell = config["steps"][1]["args"][-1]
    assert tuple(re.findall(r"tests/[a-zA-Z0-9_]+\.py", focused_test_shell)) == (
        FOCUSED_TESTS
    )
    marker = "python - <<'PY'\n"
    assert metadata_shell.count(marker) == 1
    python_source = metadata_shell.split(marker, 1)[1].rsplit("\nPY\n", 1)[0]
    compile(python_source, "cloudbuild-metadata-writer", "exec")
    assert config["artifacts"]["objects"]["paths"] == [
        "/workspace/r6-post-freeze-build-metadata.json"
    ]
    assert config["artifacts"]["objects"]["location"] == (
        "${_BUILD_METADATA_PREFIX}/${BUILD_ID}/"
    )
    metadata_prefix = config["substitutions"]["_BUILD_METADATA_PREFIX"]
    expected_uri = (
        f"{metadata_prefix}/${{BUILD_ID}}/r6-post-freeze-build-metadata.json"
    )
    assert (
        'f"{metadata_prefix}/{build_id}/"\n'
        '                "r6-post-freeze-build-metadata.json"'
    ) in BUILD_CONFIG.read_text(encoding="utf-8")
    assert expected_uri == (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "r6-full-union-post-freeze-builds/${BUILD_ID}/"
        "r6-post-freeze-build-metadata.json"
    )


def test_all_cloud_build_shell_steps_parse_after_substitution_unescape() -> None:
    config = yaml.safe_load(BUILD_CONFIG.read_text(encoding="utf-8"))
    for step in config["steps"]:
        assert step["entrypoint"] == "bash"
        script = step["args"][-1].replace("$$", "$")
        completed = subprocess.run(
            ["bash", "-n"],
            input=script,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, (
            step["id"], completed.stdout, completed.stderr
        )
