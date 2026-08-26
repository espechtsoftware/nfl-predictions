import ast
import json
from copy import deepcopy
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog
from nfl_dfs.research import (
    corpus_r6_player_catalog_fixed_g0_projection_successor_v1 as successor,
)


def _rehash(value, field):
    value.pop(field, None)
    value[field] = successor.canonical_sha256(value)


def _repo_and_head():
    repository = adapter.SubprocessGitRepositoryV1()
    return repository, repository.require_current_clean_head()


def _focused_output(*, duration=b"0.20"):
    first = 74
    second = 74
    final = successor.EXPECTED_FOCUSED_CASE_COUNT - first - second
    assert final == 2
    return (
        b"." * first + b" [ 49%]\n"
        + b"." * second + b" [ 98%]\n"
        + b"." * final + b" [100%]\n"
        + str(successor.EXPECTED_FOCUSED_CASE_COUNT).encode("ascii")
        + b" passed in " + duration + b"s\n"
    )


def _measurements():
    return [
        {"relative_path": path, "sha256": "a" * 64, "bytes": 1}
        for path in successor.IMPLEMENTATION_PATHS
    ]


def _review_parts():
    repository, head = _repo_and_head()
    evidence = successor.validate_successor_evidence_v1(
        repository=repository, head=head
    )
    measurements = _measurements()
    focused = {
        "relative_path": successor.FOCUSED_OUTPUT_PATH,
        "sha256": "b" * 64,
        "bytes": 100,
    }
    review = successor._build_review_lock(
        implementation_commit_sha="c" * 40,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file=focused,
        focused_pass_count=successor.EXPECTED_FOCUSED_CASE_COUNT,
        independent_static_review_passed=True,
    )
    review_file = {
        "relative_path": successor.REVIEW_LOCK_PATH,
        "sha256": "d" * 64,
        "bytes": 1000,
    }
    return evidence, measurements, focused, review, review_file


def _static_pytest_case_count(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    total = 0
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        multiplier = 1
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or len(decorator.args) < 2:
                continue
            func = decorator.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "parametrize"
            ):
                continue
            values = decorator.args[1]
            if isinstance(values, (ast.List, ast.Tuple, ast.Set)):
                multiplier *= len(values.elts)
            else:
                multiplier *= len(ast.literal_eval(values))
        total += multiplier
    return total


def test_exact_old_final_and_projection_failure_evidence_reopen():
    repository, head = _repo_and_head()
    evidence = successor.validate_successor_evidence_v1(
        repository=repository, head=head
    )
    assert evidence["old_final_lock_commit_sha"] == successor.OLD_FINAL_LOCK_COMMIT
    assert evidence["old_final_lock_file"] == {
        "relative_path": successor.OLD_FINAL_LOCK_PATH,
        "sha256": successor.OLD_FINAL_LOCK_SHA256,
        "bytes": successor.OLD_FINAL_LOCK_BYTES,
    }
    assert evidence["old_final_lock_internal_sha256"] == (
        successor.OLD_FINAL_LOCK_INTERNAL_SHA256
    )
    assert evidence["projection_failure_report_file"] == {
        "relative_path": successor.FAILURE_REPORT_PATH,
        "sha256": successor.FAILURE_REPORT_SHA256,
        "bytes": successor.FAILURE_REPORT_BYTES,
    }
    assert evidence["first_projection_output_create_count"] == 0
    assert evidence["first_projection_failed_before_output_create_phase"] is True


def test_old_final_outer_binding_rejects_one_byte_drift():
    repository, head = _repo_and_head()
    old = repository.read_tracked(
        successor.OLD_FINAL_LOCK_COMMIT, successor.OLD_FINAL_LOCK_PATH
    )
    report = repository.read_tracked(head, successor.FAILURE_REPORT_PATH)

    class Repository:
        def read_tracked(self, commit, path):
            if path == successor.OLD_FINAL_LOCK_PATH:
                return old + (b" " if commit == successor.OLD_FINAL_LOCK_COMMIT else b"")
            if commit == head and path == successor.FAILURE_REPORT_PATH:
                return report
            raise AssertionError((commit, path))

    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor.validate_successor_evidence_v1(
            repository=Repository(), head=head
        )


def test_old_final_semantic_mutation_fails_when_coherently_rehashed():
    repository, _ = _repo_and_head()
    raw = repository.read_tracked(
        successor.OLD_FINAL_LOCK_COMMIT, successor.OLD_FINAL_LOCK_PATH
    )
    value = successor._parse_json(raw, label="fixture old final lock")
    value["third_adapter_smoke_allowed"] = True
    _rehash(value, "final_release_lock_sha256")
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor._validate_old_final_lock(value)


def test_old_final_base_adapter_review_exact_reopens_without_cloud():
    repository, _ = _repo_and_head()
    raw = repository.read_tracked(
        successor.OLD_FINAL_LOCK_COMMIT, successor.OLD_FINAL_LOCK_PATH
    )
    old = successor._validate_old_final_lock(
        successor._parse_json(raw, label="fixture old final lock")
    )
    review = successor._adapter_review_from_old_final(old)
    reopened = adapter._reopen_adapter_review_binding_v1(
        review=review, read_tracked=repository.read_tracked
    )
    assert reopened["review_lock_internal_sha256"] == (
        old["base_adapter_review_binding"]["review_lock_internal_sha256"]
    )


def test_runtime_measurements_cover_only_adapter_catalog_batch_and_successor():
    assert successor.IMPLEMENTATION_PATHS == (
        *adapter.FIXED_ADAPTER_IMPLEMENTATION_PATHS,
        successor.MODULE_PATH,
        successor.TEST_PATH,
    )
    assert len(successor.IMPLEMENTATION_PATHS) == 6
    assert len(set(successor.IMPLEMENTATION_PATHS)) == 6


def test_static_case_counts_preserve_adapter_count_and_pin_successor_count():
    root = Path(successor.REPOSITORY_ROOT)
    assert _static_pytest_case_count(
        root / adapter.FIXED_ADAPTER_TEST_PATH
    ) == successor.EXPECTED_ADAPTER_CASE_COUNT
    assert _static_pytest_case_count(
        root / successor.TEST_PATH
    ) == successor.EXPECTED_SUCCESSOR_CASE_COUNT
    assert successor.EXPECTED_FOCUSED_CASE_COUNT == 150


def test_focused_argv_has_one_effective_quiet_flag_and_exact_environment():
    assert successor.FOCUSED_TEST_COMMAND == (
        "/home/erich/projects/nfl-predictions/.venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
        "--color=no",
        adapter.FIXED_ADAPTER_TEST_PATH,
        successor.TEST_PATH,
    )
    assert successor.FOCUSED_TEST_COMMAND.count("-q") == 1
    assert successor.FOCUSED_TEST_CWD == (
        "/tmp/nfl-r6-catalog-projection-successor-v1"
    )
    assert successor.FOCUSED_TEST_PYTHONPATH == (
        "/tmp/nfl-r6-catalog-projection-successor-v1/src"
    )


def test_adapter_source_and_fixture_pin_false_top_level_claim():
    root = Path(successor.REPOSITORY_ROOT)
    source = (root / adapter.FIXED_ADAPTER_MODULE_PATH).read_text(encoding="utf-8")
    tests = (root / adapter.FIXED_ADAPTER_TEST_PATH).read_text(encoding="utf-8")
    field = '"complete_dk_salary_coverage_claimed"'
    assert field in source
    assert f"item[{field}] is not False" in source
    assert f"{field}: False" in tests
    assert 'top_level_claim["complete_dk_salary_coverage_claimed"] = True' in tests


def test_focused_output_accepts_exact_wrapped_progress_and_summary():
    assert successor._focused_output(_focused_output()) == {
        "passed_test_count": 150,
        "exit_code": 0,
    }


def test_focused_output_rejects_failure_marker():
    raw = _focused_output().replace(b".. [100%]", b".F [100%]", 1)
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor._focused_output(raw)


def test_focused_output_rejects_incomplete_case_count():
    raw = _focused_output().replace(b".. [100%]", b". [100%]", 1)
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor._focused_output(raw)


def test_focused_output_rejects_warning_skip_or_extra_line():
    exact = _focused_output()
    variants = (
        exact.replace(b"150 passed in", b"150 passed, 1 warning in"),
        exact.replace(b"150 passed in", b"149 passed, 1 skipped in"),
        exact + b"extra\n",
        exact[:-1],
    )
    for raw in variants:
        with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
            successor._focused_output(raw)


def test_review_lock_round_trip_preserves_consumed_attempt_accounting():
    evidence, measurements, focused, review, _ = _review_parts()
    successor.validate_review_lock_v1(
        review,
        implementation_commit_sha="c" * 40,
        implementation_measurements=measurements,
        evidence=evidence,
        focused_output_file=focused,
        focused_pass_count=150,
    )
    assert review["adapter_attempt_count"] == 2
    assert review["projection_attempt_count"] == 1
    assert review["first_projection_passed"] is False
    assert review["corrected_projection_rerun_licensed"] is False
    assert review["third_projection_attempt_licensed"] is False
    assert review["projection_publication_licensed"] is False
    assert all(review[field] is False for field in successor._FALSE_AUTHORITY_FIELDS)


def test_review_lock_rejects_coherent_early_projection_license():
    evidence, measurements, focused, review, _ = _review_parts()
    review["corrected_projection_rerun_licensed"] = True
    _rehash(review, "projection_successor_review_lock_sha256")
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor.validate_review_lock_v1(
            review,
            implementation_commit_sha="c" * 40,
            implementation_measurements=measurements,
            evidence=evidence,
            focused_output_file=focused,
            focused_pass_count=150,
        )


def test_review_lock_rejects_coherent_prior_failure_erasure():
    evidence, measurements, focused, review, _ = _review_parts()
    review["first_projection_output_create_count"] = 1
    _rehash(review, "projection_successor_review_lock_sha256")
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor.validate_review_lock_v1(
            review,
            implementation_commit_sha="c" * 40,
            implementation_measurements=measurements,
            evidence=evidence,
            focused_output_file=focused,
            focused_pass_count=150,
        )


def test_final_lock_round_trip_licenses_only_one_corrected_projection():
    _, _, _, review, review_file = _review_parts()
    final = successor._build_final_lock(
        review_lock_file=review_file, review_lock=review
    )
    successor.validate_final_lock_v1(
        final, review_lock_file=review_file, review_lock=review
    )
    assert final["projection_attempt_count_before_successor"] == 1
    assert final["maximum_projection_attempt_count"] == 2
    assert final["corrected_projection_rerun_licensed"] is True
    assert final["third_projection_attempt_licensed"] is False
    assert final["projection_attempt_marker_schema"] == (
        successor.PROJECTION_ATTEMPT_SCHEMA
    )
    assert final["projection_attempt_marker_relative_path"] == (
        successor.PROJECTION_ATTEMPT_PATH
    )
    assert final["projection_attempt_marker_create_once_before_client"] is True
    assert final["projection_only_publication_licensed"] is True
    assert final["all_inputs_derived_before_first_output"] is True
    assert final["generation_pinned_input_reads_required"] is True
    assert final["gcs_create_once_required"] is True
    assert final["gcs_exact_reopen_required"] is True
    assert final["gcs_overwrite_licensed"] is False


def test_final_lock_rejects_coherent_third_projection_license():
    _, _, _, review, review_file = _review_parts()
    final = successor._build_final_lock(
        review_lock_file=review_file, review_lock=review
    )
    final["third_projection_attempt_licensed"] = True
    _rehash(final, "projection_successor_final_lock_sha256")
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor.validate_final_lock_v1(
            final, review_lock_file=review_file, review_lock=review
        )


def test_final_lock_rejects_coherent_authority_or_command_drift():
    _, _, _, review, review_file = _review_parts()
    mutations = (
        ("historical_scoring_licensed", True),
        ("publication_authority", True),
        ("uses_realized_outcomes", True),
        ("projection_release_command", ["python", "unreviewed.py"]),
        ("projection_attempt_marker_create_once_before_client", False),
        ("required_source_task_count", 1),
        ("gcs_exact_reopen_required", False),
    )
    for field, value in mutations:
        final = successor._build_final_lock(
            review_lock_file=review_file, review_lock=review
        )
        final[field] = value
        _rehash(final, "projection_successor_final_lock_sha256")
        with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
            successor.validate_final_lock_v1(
                final, review_lock_file=review_file, review_lock=review
            )


def test_local_lock_write_is_partial_write_safe_create_once_and_canonical(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(successor, "REPOSITORY_ROOT", tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir()
    output = successor._safe_output_path("reports/lock.json", label="test lock")
    real_write = successor.os.write
    calls = 0

    def partial_write(fd, raw):
        nonlocal calls
        calls += 1
        return real_write(fd, raw[:max(1, len(raw) // 2)])

    monkeypatch.setattr(successor.os, "write", partial_write)
    successor._write_once(output, {"b": 2, "a": 1}, label="test lock")
    assert calls > 1
    assert output.read_bytes() == b'{"a":1,"b":2}\n'
    assert (output.stat().st_mode & 0o777) == 0o600
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor._safe_output_path("reports/lock.json", label="test lock")


def test_local_lock_path_rejects_symlink_parent(tmp_path, monkeypatch):
    monkeypatch.setattr(successor, "REPOSITORY_ROOT", tmp_path)
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "reports").symlink_to(real, target_is_directory=True)
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor._safe_output_path("reports/lock.json", label="test lock")


def test_review_resolver_rejects_current_runtime_drift(monkeypatch):
    implementation_commit = "a" * 40
    head = "b" * 40
    reviewed = {
        path: f"reviewed:{path}\n".encode("ascii")
        for path in successor.IMPLEMENTATION_PATHS
    }
    measurements = [
        successor._binding(path, reviewed[path])
        for path in successor.IMPLEMENTATION_PATHS
    ]
    focused_raw = _focused_output(duration=b"0.01")
    lock = successor._build_review_lock(
        implementation_commit_sha=implementation_commit,
        implementation_measurements=measurements,
        evidence={},
        focused_output_file=successor._binding(
            successor.FOCUSED_OUTPUT_PATH, focused_raw
        ),
        focused_pass_count=150,
        independent_static_review_passed=True,
    )
    lock_raw = successor.canonical_bytes(lock) + b"\n"
    current = dict(reviewed)
    current[adapter.FIXED_CATALOG_MODULE_PATH] = b"runtime drift\n"

    class Repository:
        def read_tracked(self, commit, path):
            if commit == head and path == successor.REVIEW_LOCK_PATH:
                return lock_raw
            if commit == head and path == successor.FOCUSED_OUTPUT_PATH:
                return focused_raw
            if commit == implementation_commit:
                return reviewed[path]
            if commit == head:
                return current[path]
            raise AssertionError((commit, path))

    monkeypatch.setattr(
        successor, "validate_successor_evidence_v1", lambda **_kwargs: {}
    )
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor._resolve_review_lock(repository=Repository(), head=head)


def test_production_projection_is_parked_before_repository_or_client(monkeypatch):
    monkeypatch.delenv(successor.PRODUCTION_ENABLE_ENV, raising=False)
    monkeypatch.setattr(
        adapter,
        "SubprocessGitRepositoryV1",
        lambda: pytest.fail("repository must remain unopened"),
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1,
        "from_default_client",
        lambda: pytest.fail("client must remain unopened"),
    )
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor.publish_projection_production_v1()

    class Repository:
        pass

    expected_repository = Repository()
    monkeypatch.setenv(successor.PRODUCTION_ENABLE_ENV, "1")
    monkeypatch.setattr(
        adapter, "SubprocessGitRepositoryV1", lambda: expected_repository
    )
    monkeypatch.setattr(
        successor,
        "_resolve_final_lock",
        lambda **_kwargs: (_ for _ in ()).throw(
            successor.CorpusR6FixedG0ProjectionSuccessorV1Error("injected")
        ),
    )
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor.publish_projection_production_v1()


def test_production_resolves_successor_final_before_client_and_forwards_adapter(
    monkeypatch,
):
    events = []
    base_review = object()
    final_lock = object()
    final_file = object()
    transport = object()
    expected = {"projection": "published"}

    class Repository:
        def read_tracked(self, *_args):
            raise AssertionError("patched publisher must not read directly")

    class Backend:
        def transport(self):
            events.append("transport")
            return transport

    expected_repository = Repository()

    def resolve_final(*, repository):
        assert repository is expected_repository
        events.append("final")
        return "a" * 40, base_review, final_lock, final_file

    def reserve_attempt(**kwargs):
        assert events == ["final"]
        assert kwargs == {
            "current_clean_commit_sha": "a" * 40,
            "final_lock_file": final_file,
            "final_lock": final_lock,
        }
        events.append("attempt")
        return {"attempt": "reserved"}

    def client():
        assert events == ["final", "attempt"]
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

    monkeypatch.setenv(successor.PRODUCTION_ENABLE_ENV, "1")
    monkeypatch.setattr(
        adapter, "SubprocessGitRepositoryV1", lambda: expected_repository
    )
    monkeypatch.setattr(successor, "_resolve_final_lock", resolve_final)
    monkeypatch.setattr(
        successor, "_reserve_projection_attempt_v1", reserve_attempt
    )
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1, "from_default_client", client
    )
    monkeypatch.setattr(adapter, "_publish_pinned_projection_release_v1", publish)
    assert successor.publish_projection_production_v1() is expected
    assert events == ["final", "attempt", "client", "transport", "publish"]


def test_attempt_marker_binds_final_lock_command_and_current_source_identity():
    _, _, _, review, review_file = _review_parts()
    final = successor._build_final_lock(
        review_lock_file=review_file, review_lock=review
    )
    final_file = {
        "relative_path": successor.FINAL_LOCK_PATH,
        "sha256": "e" * 64,
        "bytes": 2000,
    }
    current_commit = "f" * 40
    attempt = successor._build_projection_attempt_v1(
        current_clean_commit_sha=current_commit,
        final_lock_file=final_file,
        final_lock=final,
    )
    successor.validate_projection_attempt_v1(
        attempt,
        current_clean_commit_sha=current_commit,
        final_lock_file=final_file,
        final_lock=final,
    )
    assert attempt["projection_attempt_ordinal"] == 2
    assert attempt["maximum_projection_attempt_count"] == 2
    assert attempt["command"] == list(successor.PROJECTION_COMMAND)
    assert attempt["projection_successor_final_lock_file"] == final_file
    assert attempt["projection_successor_final_lock_internal_sha256"] == final[
        "projection_successor_final_lock_sha256"
    ]
    assert attempt["current_clean_commit_sha"] == current_commit
    assert attempt["current_source_identity"] == {
        "commit_sha": current_commit,
        "successor_module_file": next(
            row
            for row in final["implementation_measurements"]
            if row["relative_path"] == successor.MODULE_PATH
        ),
    }
    assert attempt["corrected_projection_rerun_license_consumed"] is True
    assert attempt["corrected_projection_rerun_licensed"] is False
    assert attempt["third_projection_attempt_licensed"] is False
    assert all(
        attempt[field] is False for field in successor._FALSE_AUTHORITY_FIELDS
    )
    changed = deepcopy(attempt)
    changed["projection_attempt_ordinal"] = 3
    _rehash(changed, "projection_successor_attempt_sha256")
    with pytest.raises(successor.CorpusR6FixedG0ProjectionSuccessorV1Error):
        successor.validate_projection_attempt_v1(
            changed,
            current_clean_commit_sha=current_commit,
            final_lock_file=final_file,
            final_lock=final,
        )


def test_failed_reserved_attempt_cannot_retry_or_recontact_cloud(
    tmp_path, monkeypatch,
):
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(successor, "REPOSITORY_ROOT", tmp_path)
    _, _, _, review, review_file = _review_parts()
    final = successor._build_final_lock(
        review_lock_file=review_file, review_lock=review
    )
    final_file = {
        "relative_path": successor.FINAL_LOCK_PATH,
        "sha256": "1" * 64,
        "bytes": 2001,
    }
    current_commit = "2" * 40
    repository = object()
    client_calls = 0

    class InjectedClientFailure(RuntimeError):
        pass

    def client():
        nonlocal client_calls
        client_calls += 1
        raise InjectedClientFailure("injected after durable reservation")

    def resolve_final(*, repository):
        return current_commit, object(), final, final_file

    monkeypatch.setenv(successor.PRODUCTION_ENABLE_ENV, "1")
    monkeypatch.setattr(adapter, "SubprocessGitRepositoryV1", lambda: repository)
    monkeypatch.setattr(successor, "_resolve_final_lock", resolve_final)
    monkeypatch.setattr(
        adapter.GCSGenerationBackendV1, "from_default_client", client
    )
    monkeypatch.setattr(
        adapter,
        "_publish_pinned_projection_release_v1",
        lambda **_kwargs: pytest.fail("adapter must remain unopened"),
    )

    with pytest.raises(InjectedClientFailure):
        successor.publish_projection_production_v1()
    raw = (tmp_path / successor.PROJECTION_ATTEMPT_PATH).read_bytes()
    assert raw.endswith(b"\n")
    attempt = successor.validate_projection_attempt_v1(
        json.loads(raw),
        current_clean_commit_sha=current_commit,
        final_lock_file=final_file,
        final_lock=final,
    )
    assert attempt["reserved_before_cloud_client_construction"] is True
    assert client_calls == 1

    with pytest.raises(
        successor.CorpusR6FixedG0ProjectionSuccessorV1Error,
        match="already exists",
    ):
        successor.publish_projection_production_v1()
    assert client_calls == 1


def test_cli_status_exposes_no_smoke_outcome_or_third_attempt(capsys):
    assert successor.main(["status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["projection_attempt_count"] == 1
    assert status["first_projection_passed"] is False
    assert status["corrected_projection_rerun_licensed"] is False
    assert status["projection_attempt_marker_path"] == (
        successor.PROJECTION_ATTEMPT_PATH
    )
    assert status["third_adapter_smoke_allowed"] is False
    assert status["third_projection_attempt_licensed"] is False
    assert status["uses_realized_outcomes"] is False
    for forbidden in ("smoke", "outcomes", "third-projection"):
        with pytest.raises(SystemExit):
            successor.main([forbidden])
        assert "invalid choice" in capsys.readouterr().err
