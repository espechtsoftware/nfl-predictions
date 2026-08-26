import json
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog
from nfl_dfs.research import (
    corpus_r6_player_catalog_fixed_g0_terminal_recovery_v1 as recovery,
)


def _rehash(value, field):
    value.pop(field, None)
    value[field] = recovery.canonical_sha256(value)


def _repo_and_head():
    repository = adapter.SubprocessGitRepositoryV1()
    return repository, repository.require_current_clean_head()


def _clean_focused_output(*, duration=b"0.20"):
    first = 72
    second = 72
    final = recovery.EXPECTED_FOCUSED_CASE_COUNT - first - second
    assert final > 0
    return (
        b"." * first + b" [ 48%]\n"
        + b"." * second + b" [ 97%]\n"
        + b"." * final + b" [100%]\n"
        + str(recovery.EXPECTED_FOCUSED_CASE_COUNT).encode("ascii")
        + b" passed in " + duration + b"s\n"
    )


def test_exact_tracked_publication_receipt_regression_and_terminal_evidence():
    repository, head = _repo_and_head()
    evidence = recovery.validate_fixed_terminal_evidence_v1(
        repository=repository, head=head
    )
    assert evidence["official_publication_receipt_file"] == {
        "relative_path": recovery.OFFICIAL_RECEIPT_PATH,
        "sha256": recovery.OFFICIAL_RECEIPT_SHA256,
        "bytes": recovery.OFFICIAL_RECEIPT_BYTES,
    }
    assert evidence["official_publication_receipt_internal_sha256"] == (
        recovery.OFFICIAL_RECEIPT_INTERNAL_SHA256
    )
    assert evidence["v1_attempt_internal_sha256"] == (
        recovery.V1_ATTEMPT_INTERNAL_SHA256
    )
    assert evidence["v2_attempt_internal_sha256"] == (
        recovery.V2_ATTEMPT_INTERNAL_SHA256
    )
    assert evidence["prior_real_artifact_smoke_internal_sha256"] == (
        recovery.PRIOR_SMOKE_INTERNAL_SHA256
    )


def test_wrong_publication_schema_literal_is_absent_from_corrected_adapter():
    source = (
        Path(recovery.REPOSITORY_ROOT) / adapter.FIXED_ADAPTER_MODULE_PATH
    ).read_text()
    tests = (
        Path(recovery.REPOSITORY_ROOT) / adapter.FIXED_ADAPTER_TEST_PATH
    ).read_text()
    wrong = "foundry-v12-panel-publication-receipt/v1"
    correct = "foundry-v12-panel-index-publication/v1"
    assert wrong not in source
    assert wrong not in tests
    assert source.count(correct) == 1
    assert tests.count(correct) >= 1


def test_current_execution_measurements_cover_the_complete_private_runtime():
    assert recovery.IMPLEMENTATION_PATHS == (
        *adapter.FIXED_ADAPTER_IMPLEMENTATION_PATHS,
        recovery.MODULE_PATH,
        recovery.TEST_PATH,
    )
    assert recovery.FOCUSED_TEST_COMMAND == (
        "/home/erich/projects/nfl-predictions/.venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
        "--color=no",
        adapter.FIXED_ADAPTER_TEST_PATH,
        recovery.TEST_PATH,
    )


@pytest.mark.parametrize(
    "drift_path",
    (adapter.FIXED_CATALOG_MODULE_PATH, adapter.FIXED_BATCH_MODULE_PATH),
)
def test_review_resolver_rejects_current_private_runtime_dependency_drift(
    monkeypatch, drift_path,
):
    implementation_commit = "a" * 40
    head = "b" * 40
    reviewed = {
        path: f"reviewed:{path}\n".encode("ascii")
        for path in recovery.IMPLEMENTATION_PATHS
    }
    measurements = [
        recovery._binding(path, reviewed[path])
        for path in recovery.IMPLEMENTATION_PATHS
    ]
    focused_raw = _clean_focused_output(duration=b"0.01")
    lock = recovery._build_review_lock(
        implementation_commit_sha=implementation_commit,
        implementation_measurements=measurements,
        evidence={},
        focused_output_file=recovery._binding(
            recovery.FOCUSED_OUTPUT_PATH, focused_raw
        ),
        focused_pass_count=recovery.EXPECTED_FOCUSED_CASE_COUNT,
        independent_static_review_passed=True,
    )
    lock_raw = recovery.canonical_bytes(lock) + b"\n"
    current = dict(reviewed)
    current[drift_path] = b"clean-commit runtime drift\n"

    class Repository:
        def read_tracked(self, commit, path):
            if commit == head and path == recovery.REVIEW_LOCK_PATH:
                return lock_raw
            if commit == head and path == recovery.FOCUSED_OUTPUT_PATH:
                return focused_raw
            if commit == implementation_commit:
                return reviewed[path]
            if commit == head:
                return current[path]
            raise AssertionError((commit, path))

    monkeypatch.setattr(
        recovery,
        "validate_fixed_terminal_evidence_v1",
        lambda **_kwargs: {},
    )
    with pytest.raises(recovery.CorpusR6FixedG0TerminalRecoveryV1Error):
        recovery._resolve_review_lock(repository=Repository(), head=head)


def test_success_receipt_absence_requires_one_successful_exact_tree_query():
    head = "a" * 40
    path = adapter.FIXED_TASK0_SMOKE_RECEIPT_PATH

    class Repository:
        def __init__(self, *, response=b"", error=None):
            self.response = response
            self.error = error
            self.calls = []

        def _run(self, args, *, label):
            self.calls.append((args, label))
            if self.error is not None:
                raise self.error
            return self.response

    absent = Repository()
    recovery._require_tracked_absence(
        absent,
        commit=head,
        path=path,
        label="adapter smoke success receipt",
    )
    assert absent.calls == [(
        [
            "ls-tree",
            "--full-tree",
            "-z",
            "--name-only",
            head,
            "--",
            path,
        ],
        "adapter smoke success receipt absence proof",
    )]

    present = Repository(response=path.encode("utf-8") + b"\0")
    with pytest.raises(recovery.CorpusR6FixedG0TerminalRecoveryV1Error):
        recovery._require_tracked_absence(
            present,
            commit=head,
            path=path,
            label="adapter smoke success receipt",
        )

    broken = Repository(error=RuntimeError("injected Git failure"))
    with pytest.raises(
        recovery.CorpusR6FixedG0TerminalRecoveryV1Error,
        match="absence proof failed",
    ):
        recovery._require_tracked_absence(
            broken,
            commit=head,
            path=path,
            label="adapter smoke success receipt",
        )


def test_review_and_final_locks_truthfully_close_both_attempts():
    repository, head = _repo_and_head()
    evidence = recovery.validate_fixed_terminal_evidence_v1(
        repository=repository, head=head
    )
    measurements = [
        {"relative_path": path, "sha256": "a" * 64, "bytes": 1}
        for path in recovery.IMPLEMENTATION_PATHS
    ]
    focused = {
        "relative_path": recovery.FOCUSED_OUTPUT_PATH,
        "sha256": "b" * 64,
        "bytes": 100,
    }
    review = recovery._build_review_lock(
        implementation_commit_sha="c" * 40,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file=focused,
        focused_pass_count=recovery.EXPECTED_FOCUSED_CASE_COUNT,
        independent_static_review_passed=True,
    )
    recovery.validate_review_lock_v1(
        review,
        implementation_commit_sha="c" * 40,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file=focused,
        focused_pass_count=recovery.EXPECTED_FOCUSED_CASE_COUNT,
    )
    assert review["adapter_attempt_count"] == 2
    assert review["adapter_v1_smoke_passed"] is False
    assert review["adapter_v2_smoke_passed"] is False
    assert review["adapter_success_receipt_absent"] is True
    assert review["prior_real_artifact_smoke_passed"] is True
    assert review["third_adapter_smoke_allowed"] is False
    assert review["projection_publication_licensed"] is False
    assert review["focused_test_command"] == list(recovery.FOCUSED_TEST_COMMAND)
    assert review["focused_test_cwd"] == recovery.FOCUSED_TEST_CWD
    assert review["focused_test_pythonpath"] == recovery.FOCUSED_TEST_PYTHONPATH
    assert all(review[field] is False for field in catalog.FALSE_AUTHORITY_FIELDS)
    assert all(review[field] is False for field in recovery._FALSE_AUTHORITY_FIELDS)
    for field, replacement in (
        ("focused_test_cwd", "/tmp/unreviewed-worktree"),
        ("focused_test_pythonpath", "/tmp/unreviewed-worktree/src"),
    ):
        mutated_review = dict(review)
        mutated_review[field] = replacement
        _rehash(mutated_review, "terminal_recovery_review_lock_sha256")
        with pytest.raises(recovery.CorpusR6FixedG0TerminalRecoveryV1Error):
            recovery.validate_review_lock_v1(
                mutated_review,
                implementation_commit_sha="c" * 40,
                implementation_measurements=measurements,
                evidence=evidence,
                focused_output_file=focused,
                focused_pass_count=recovery.EXPECTED_FOCUSED_CASE_COUNT,
            )
    review_file = {
        "relative_path": recovery.REVIEW_LOCK_PATH,
        "sha256": "d" * 64,
        "bytes": 1000,
    }
    final = recovery._build_final_lock(
        review_lock_file=review_file, review_lock=review
    )
    recovery.validate_final_lock_v2(
        final, review_lock_file=review_file, review_lock=review
    )
    assert final["schema_version"] == recovery.FINAL_LOCK_SCHEMA
    assert final["projection_only_publication_licensed"] is True
    assert final["required_source_task_count"] == 54
    assert final["required_task_acceptance_body_reopen_count"] == 54
    assert final["required_carrier_body_reopen_count"] == 54
    assert final["all_inputs_derived_before_first_output"] is True
    assert final["historical_scoring_licensed"] is False
    assert final["uses_realized_outcomes"] is False
    assert final["focused_test_command"] == list(recovery.FOCUSED_TEST_COMMAND)
    assert final["focused_test_cwd"] == recovery.FOCUSED_TEST_CWD
    assert final["focused_test_pythonpath"] == recovery.FOCUSED_TEST_PYTHONPATH
    assert all(final[field] is False for field in catalog.FALSE_AUTHORITY_FIELDS)
    assert all(final[field] is False for field in recovery._FALSE_AUTHORITY_FIELDS)


@pytest.mark.parametrize(
    "field,value",
    (
        ("adapter_v2_smoke_passed", True),
        ("third_adapter_smoke_allowed", True),
        ("prior_real_artifact_smoke_passed", False),
        ("projection_publication_licensed", True),
        ("historical_scoring_licensed", True),
        ("publication_authority", True),
        ("uses_realized_outcomes", True),
        ("focused_test_command", ["python", "-m", "pytest"]),
    ),
)
def test_review_lock_rejects_coherently_rehashed_semantic_drift(field, value):
    repository, head = _repo_and_head()
    evidence = recovery.validate_fixed_terminal_evidence_v1(
        repository=repository, head=head
    )
    measurements = [
        {"relative_path": path, "sha256": "a" * 64, "bytes": 1}
        for path in recovery.IMPLEMENTATION_PATHS
    ]
    focused = {
        "relative_path": recovery.FOCUSED_OUTPUT_PATH,
        "sha256": "b" * 64,
        "bytes": 100,
    }
    value_under_test = recovery._build_review_lock(
        implementation_commit_sha="c" * 40,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file=focused,
        focused_pass_count=recovery.EXPECTED_FOCUSED_CASE_COUNT,
        independent_static_review_passed=True,
    )
    value_under_test[field] = value
    _rehash(value_under_test, "terminal_recovery_review_lock_sha256")
    with pytest.raises(recovery.CorpusR6FixedG0TerminalRecoveryV1Error):
        recovery.validate_review_lock_v1(
            value_under_test,
            implementation_commit_sha="c" * 40,
            implementation_measurements=measurements,
            evidence=evidence,
            focused_output_file=focused,
            focused_pass_count=recovery.EXPECTED_FOCUSED_CASE_COUNT,
        )


def test_final_lock_rejects_wrong_commands_and_required_count():
    repository, head = _repo_and_head()
    evidence = recovery.validate_fixed_terminal_evidence_v1(
        repository=repository, head=head
    )
    measurements = [
        {"relative_path": path, "sha256": "a" * 64, "bytes": 1}
        for path in recovery.IMPLEMENTATION_PATHS
    ]
    focused = {
        "relative_path": recovery.FOCUSED_OUTPUT_PATH,
        "sha256": "b" * 64,
        "bytes": 100,
    }
    review = recovery._build_review_lock(
        implementation_commit_sha="c" * 40,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file=focused,
        focused_pass_count=recovery.EXPECTED_FOCUSED_CASE_COUNT,
        independent_static_review_passed=True,
    )
    review_file = {
        "relative_path": recovery.REVIEW_LOCK_PATH,
        "sha256": "d" * 64,
        "bytes": 1000,
    }
    for mutation in (
        "projection_command",
        "focused_command",
        "focused_cwd",
        "focused_pythonpath",
        "count",
    ):
        final = recovery._build_final_lock(
            review_lock_file=review_file, review_lock=review
        )
        if mutation == "projection_command":
            final["projection_release_command"][-1] = "--preflight"
        elif mutation == "focused_command":
            final["focused_test_command"][-1] = "tests/test_unreviewed.py"
        elif mutation == "focused_cwd":
            final["focused_test_cwd"] = "/tmp/unreviewed-worktree"
        elif mutation == "focused_pythonpath":
            final["focused_test_pythonpath"] = "/tmp/unreviewed-worktree/src"
        else:
            final["required_source_task_count"] = 1
        _rehash(final, "final_release_lock_sha256")
        with pytest.raises(recovery.CorpusR6FixedG0TerminalRecoveryV1Error):
            recovery.validate_final_lock_v2(
                final, review_lock_file=review_file, review_lock=review
            )


def test_focused_output_rejects_incomplete_or_unclean_output():
    exact = _clean_focused_output()
    adversarial_outputs = (
        b". [100%]\n1 passed in 0.20s\n",
        exact.replace(b".... [100%]", b"...F [100%]", 1),
        exact.replace(b" [ 48%]", b" [ 49%]", 1),
        exact.replace(b" [ 97%]", b" [ 48%]", 1),
        exact.replace(b"148 passed in 0.20s", b"148 passed in 0.1.2s"),
        exact + b"extra\n",
        exact.replace(b"148 passed in 0.20s", b"147 passed, 1 skipped in 0.20s"),
        exact.replace(b"148 passed in 0.20s", b"148 passed, 1 warning in 0.20s"),
        exact[:-1],
    )
    for raw in adversarial_outputs:
        with pytest.raises(recovery.CorpusR6FixedG0TerminalRecoveryV1Error):
            recovery._focused_output(raw)


def test_focused_output_accepts_one_clean_summary():
    raw = _clean_focused_output()
    assert recovery._focused_output(raw) == {
        "passed_test_count": recovery.EXPECTED_FOCUSED_CASE_COUNT,
        "exit_code": 0,
    }


def test_local_lock_write_is_create_once_and_canonical(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "REPOSITORY_ROOT", tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir()
    output = recovery._safe_output_path("reports/lock.json", label="test lock")
    real_write = recovery.os.write
    write_calls = 0

    def partial_write(fd, raw):
        nonlocal write_calls
        write_calls += 1
        return real_write(fd, raw[:max(1, len(raw) // 2)])

    monkeypatch.setattr(recovery.os, "write", partial_write)
    recovery._write_once(output, {"b": 2, "a": 1}, label="test lock")
    assert write_calls > 1
    assert output.read_bytes() == b'{"a":1,"b":2}\n'
    assert (output.stat().st_mode & 0o777) == 0o600
    with pytest.raises(recovery.CorpusR6FixedG0TerminalRecoveryV1Error):
        recovery._safe_output_path("reports/lock.json", label="test lock")


def test_production_projection_is_parked_before_client(monkeypatch):
    monkeypatch.delenv(recovery.PRODUCTION_ENABLE_ENV, raising=False)
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        lambda: pytest.fail("client must remain unopened"),
    )
    with pytest.raises(recovery.CorpusR6FixedG0TerminalRecoveryV1Error):
        recovery.publish_projection_production_v1()


def test_production_projection_resolves_final_before_client_and_forwards_fixed_call(
    monkeypatch,
):
    events = []
    base_review = object()
    transport = object()
    expected = {"projection": "published"}

    class Repository:
        def read_tracked(self, *_args):
            raise AssertionError("the patched publisher must not read directly")

    class Backend:
        def transport(self):
            events.append("transport")
            return transport

    expected_repository = Repository()

    def resolve_final(*, repository: object):
        assert repository is expected_repository
        events.append("final")
        return "a" * 40, base_review, {"validated": True}

    def build_client():
        assert events == ["final"]
        events.append("client")
        return Backend()

    def publish(**kwargs):
        events.append("publish")
        assert kwargs["pins"] is adapter.FIXED_PINS
        assert kwargs["adapter_review"] is base_review
        assert kwargs["read_tracked"].__self__ is expected_repository
        assert kwargs["transport"] is transport
        assert kwargs["request_authoritative_publication"] is False
        return expected

    monkeypatch.setenv(recovery.PRODUCTION_ENABLE_ENV, "1")
    monkeypatch.setattr(
        adapter, "SubprocessGitRepositoryV1", lambda: expected_repository
    )
    monkeypatch.setattr(recovery, "_resolve_final_lock", resolve_final)
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        build_client,
    )
    monkeypatch.setattr(adapter, "_publish_pinned_projection_release_v1", publish)

    assert recovery.publish_projection_production_v1() is expected
    assert events == ["final", "client", "transport", "publish"]


@pytest.mark.parametrize("forbidden", ("smoke", "preflight-task0", "outcomes"))
def test_cli_exposes_no_smoke_or_outcome_command(capsys, forbidden):
    assert recovery.main(["status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["adapter_attempt_count"] == 2
    assert status["third_adapter_smoke_allowed"] is False
    assert status["uses_realized_outcomes"] is False
    assert "smoke" not in {"build-review-lock", "build-final-lock", "publish-projection"}
    with pytest.raises(SystemExit):
        recovery.main([forbidden])
    assert "invalid choice" in capsys.readouterr().err
