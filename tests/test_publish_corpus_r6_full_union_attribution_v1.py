"""Hermetic contract tests for the guarded R6 attribution release CLI.

These tests exercise argument/authority validation and the publish/reopen
dispatch boundary only.  The release functions are replaced at the CLI seam;
no frozen artifact, realized-outcome artifact, GCS object, or score reader is
opened.
"""

from __future__ import annotations

from hashlib import sha256
import importlib.util
import inspect
import json
from pathlib import Path
import sys
from typing import Mapping

import pytest

from nfl_dfs.research import corpus_r6_full_union_attribution_release_v1 as release
from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as grade_release


ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    path = ROOT / "scripts/publish_corpus_r6_full_union_attribution_v1.py"
    spec = importlib.util.spec_from_file_location(
        "publish_corpus_r6_full_union_attribution_v1_test", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


def _config() -> grade_release.FullUnionGradeReleaseConfigV1:
    return grade_release.FullUnionGradeReleaseConfigV1(
        run_id="r6-grade-attribution-fixture",
        job="r6-grade-job",
        execution="r6-grade-job-abc12",
        code_sha="a" * 40,
        image=f"grade@sha256:{'b' * 64}",
        expected_supply_run_id="r6-supply-attribution-fixture",
        expected_supply_job="r6-supply-job",
        expected_supply_code_sha="c" * 40,
        expected_supply_image=f"supply@sha256:{'d' * 64}",
        snapshot_module_sha256="1" * 64,
        snapshot_cli_sha256="2" * 64,
        snapshot_test_sha256="3" * 64,
        snapshot_cli_test_sha256="4" * 64,
        enabled=True,
    )


def _identity(uri: str, label: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "17",
        "sha256": sha256(label.encode("utf-8")).hexdigest(),
        "bytes": 1234,
    }


def _grade_arguments() -> list[str]:
    config = _config()
    identity = _identity(config.completion_uri, "grade completion")
    return [
        "--grade-completion-uri", str(identity["uri"]),
        "--grade-completion-generation", str(identity["generation"]),
        "--grade-completion-sha256", str(identity["sha256"]),
        "--grade-completion-bytes", str(identity["bytes"]),
        "--expected-grade-run-id", config.run_id,
        "--expected-grade-job", config.job,
        "--expected-grade-execution", config.execution,
        "--expected-grade-code-sha", config.code_sha,
        "--expected-grade-image", config.image,
        "--expected-supply-run-id", config.expected_supply_run_id,
        "--expected-supply-job", config.expected_supply_job,
        "--expected-supply-code-sha", config.expected_supply_code_sha,
        "--expected-supply-image", config.expected_supply_image,
        "--snapshot-module-sha256", config.snapshot_module_sha256,
        "--snapshot-cli-sha256", config.snapshot_cli_sha256,
        "--snapshot-test-sha256", config.snapshot_test_sha256,
        "--snapshot-cli-test-sha256", config.snapshot_cli_test_sha256,
    ]


def _publish_argv(*, execute: bool = True, run_id: str = "attr-release-fixture") -> list[str]:
    argv = ["--project", cli.PROJECT]
    if execute:
        argv.insert(0, "--execute")
    return [*argv, "publish", *_grade_arguments(), "--output-run-id", run_id]


def _root_identity(*, uri: str | None = None) -> dict[str, object]:
    retained_uri = uri or (
        f"gs://{release.OUTPUT_BUCKET}/{release.OUTPUT_NAMESPACE}/"
        "attr-release-fixture/attribution-release.json"
    )
    return _identity(retained_uri, "attribution root")


def _reopen_argv(*, execute: bool = True, root_uri: str | None = None) -> list[str]:
    root_identity = _root_identity(uri=root_uri)
    argv = ["--project", cli.PROJECT]
    if execute:
        argv.insert(0, "--execute")
    return [
        *argv,
        "reopen",
        *_grade_arguments(),
        "--attribution-root-uri", str(root_identity["uri"]),
        "--attribution-root-generation", str(root_identity["generation"]),
        "--attribution-root-sha256", str(root_identity["sha256"]),
        "--attribution-root-bytes", str(root_identity["bytes"]),
    ]


def _root() -> dict[str, object]:
    return {
        "run_id": "attr-release-fixture",
        "source_slate_count": 54,
        "lineup_count": 207_999,
        "scope_membership_count": 1_247_994,
        "book_count": 2_592,
        "selection_count": 207_360,
        "attribution_release_sha256": "e" * 64,
        "reads_freeze_and_grade_artifacts_only": True,
        "outcome_source_read": False,
        "outcome_snapshot_read": False,
        "lineup_rescore_performed": False,
        "complete": True,
    }


class _NeverStorage:
    def bucket(self, _name: str) -> object:
        raise AssertionError("CLI gate must fail before storage access")


class _FakeTransport:
    instances: list["_FakeTransport"] = []

    def __init__(self, client: object, *, cache_bytes: int) -> None:
        self.client = client
        self.cache_bytes = cache_bytes
        self.__class__.instances.append(self)

    def read_exact(self, _identity_value: Mapping[str, object]) -> bytes:
        raise AssertionError("fake release must not read an artifact")

    def publish_create_once(self, _uri: str, _raw: bytes) -> object:
        raise AssertionError("fake release must not publish an artifact")


@pytest.fixture(autouse=True)
def _reset_transport() -> None:
    _FakeTransport.instances.clear()


def _assert_summary(
    output: str,
    *,
    command: str,
    root_identity: Mapping[str, object],
) -> None:
    observed = json.loads(output)
    assert observed == {
        "schema_version": "corpus-r6-full-union-attribution-cli-summary/v1",
        "command": command,
        "root_identity": dict(root_identity),
        "run_id": "attr-release-fixture",
        "source_slate_count": 54,
        "lineup_count": 207_999,
        "scope_membership_count": 1_247_994,
        "book_count": 2_592,
        "selection_count": 207_360,
        "attribution_release_sha256": "e" * 64,
        "reads_freeze_and_grade_artifacts_only": True,
        "outcome_source_read": False,
        "outcome_snapshot_read": False,
        "lineup_rescore_performed": False,
        "complete": True,
    }


@pytest.mark.parametrize("command", ["publish", "reopen"])
def test_cli_is_default_off_before_storage_or_release(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli.release,
        "publish_r6_full_union_attribution_release_v1",
        lambda **_kwargs: pytest.fail("publish release must not run"),
    )
    monkeypatch.setattr(
        cli.release,
        "reopen_r6_full_union_attribution_release_v1",
        lambda *_args, **_kwargs: pytest.fail("reopen release must not run"),
    )
    argv = _publish_argv(execute=False) if command == "publish" else _reopen_argv(execute=False)
    with pytest.raises(
        cli.PublishCorpusR6FullUnionAttributionV1Error, match="--execute"
    ):
        cli.main(argv, environ={}, storage_client=_NeverStorage())


def test_cli_requires_literal_enable_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cli.release,
        "publish_r6_full_union_attribution_release_v1",
        lambda **_kwargs: pytest.fail("release must not run"),
    )
    with pytest.raises(
        cli.PublishCorpusR6FullUnionAttributionV1Error,
        match=cli.ENABLED_ENV,
    ):
        cli.main(
            _publish_argv(), environ={cli.ENABLED_ENV: "true"},
            storage_client=_NeverStorage(),
        )


def test_cli_rejects_project_drift_before_storage_or_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv = _publish_argv()
    argv[argv.index("--project") + 1] = "different-project"
    monkeypatch.setattr(
        cli.release,
        "publish_r6_full_union_attribution_release_v1",
        lambda **_kwargs: pytest.fail("release must not run"),
    )
    with pytest.raises(
        cli.PublishCorpusR6FullUnionAttributionV1Error, match="project differs"
    ):
        cli.main(
            argv, environ={cli.ENABLED_ENV: "1"},
            storage_client=_NeverStorage(),
        )


def test_publish_rejects_output_prefix_escape_before_storage_read() -> None:
    with pytest.raises(
        cli.PublishCorpusR6FullUnionAttributionV1Error,
        match="outside the isolated namespace",
    ):
        cli.main(
            _publish_argv(run_id="../other-prefix"),
            environ={cli.ENABLED_ENV: "1"},
            storage_client=_NeverStorage(),
        )


def test_reopen_rejects_root_outside_output_prefix_before_storage_read() -> None:
    with pytest.raises(
        cli.PublishCorpusR6FullUnionAttributionV1Error,
        match="outside the isolated namespace",
    ):
        cli.main(
            _reopen_argv(
                root_uri="gs://foreign-bucket/elsewhere/attribution-release.json"
            ),
            environ={cli.ENABLED_ENV: "1"},
            storage_client=_NeverStorage(),
        )


def test_publish_constructs_exact_config_and_emits_bounded_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    storage_client = object()
    root = _root()
    root_identity = _root_identity()
    captured: dict[str, object] = {}

    def fake_publish(**kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        captured.update(kwargs)
        return root, root_identity

    monkeypatch.setattr(cli, "GenerationPinnedGCSV1", _FakeTransport)
    monkeypatch.setattr(
        cli.release, "publish_r6_full_union_attribution_release_v1", fake_publish
    )
    assert cli.main(
        _publish_argv(),
        environ={cli.ENABLED_ENV: "1"},
        storage_client=storage_client,
    ) == 0
    assert len(_FakeTransport.instances) == 1
    transport = _FakeTransport.instances[0]
    assert transport.client is storage_client
    assert transport.cache_bytes == cli.DEFAULT_CACHE_BYTES
    assert captured == {
        "grade_completion_identity": _identity(
            _config().completion_uri, "grade completion"
        ),
        "grade_release_config": _config(),
        "output_prefix": (
            f"gs://{release.OUTPUT_BUCKET}/{release.OUTPUT_NAMESPACE}/"
            "attr-release-fixture"
        ),
        "read_exact": transport.read_exact,
        "publish_create_once": transport.publish_create_once,
    }
    _assert_summary(
        capsys.readouterr().out,
        command="publish",
        root_identity=root_identity,
    )


def test_reopen_constructs_exact_config_and_emits_bounded_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    storage_client = object()
    root = _root()
    root_identity = _root_identity()
    captured: dict[str, object] = {}

    def fake_reopen(
        supplied_root_identity: object, **kwargs: object,
    ) -> tuple[dict[str, object], dict[str, object]]:
        captured["root_identity"] = supplied_root_identity
        captured.update(kwargs)
        return root, root_identity

    monkeypatch.setattr(cli, "GenerationPinnedGCSV1", _FakeTransport)
    monkeypatch.setattr(
        cli.release, "reopen_r6_full_union_attribution_release_v1", fake_reopen
    )
    assert cli.main(
        _reopen_argv(),
        environ={cli.ENABLED_ENV: "1"},
        storage_client=storage_client,
    ) == 0
    assert len(_FakeTransport.instances) == 1
    transport = _FakeTransport.instances[0]
    assert captured == {
        "root_identity": root_identity,
        "grade_completion_identity": _identity(
            _config().completion_uri, "grade completion"
        ),
        "grade_release_config": _config(),
        "read_exact": transport.read_exact,
    }
    _assert_summary(
        capsys.readouterr().out,
        command="reopen",
        root_identity=root_identity,
    )


def _all_parser_options() -> set[str]:
    parser = cli._parser()
    options: set[str] = set()
    pending = [parser]
    while pending:
        retained = pending.pop()
        for action in retained._actions:  # noqa: SLF001 - parser contract audit
            options.update(action.option_strings)
            choices = getattr(action, "choices", None)
            if isinstance(choices, Mapping):
                pending.extend(choices.values())
    return options


def test_cli_exposes_no_outcome_source_or_rescore_boundary() -> None:
    options = _all_parser_options()
    forbidden = {
        "--outcome-snapshot-uri",
        "--outcome-snapshot-generation",
        "--outcome-snapshot-sha256",
        "--outcome-snapshot-bytes",
        "--realized-source-uri",
        "--realized-source-generation",
        "--realized-source-sha256",
        "--realized-source-bytes",
        "--historical-outcome-lease-uri",
        "--score",
        "--rescore",
    }
    assert options.isdisjoint(forbidden)
    signature = inspect.signature(cli.main)
    assert "storage_client" in signature.parameters
    assert set(inspect.signature(
        release.publish_r6_full_union_attribution_release_v1
    ).parameters) == {
        "grade_completion_identity",
        "grade_release_config",
        "output_prefix",
        "read_exact",
        "publish_create_once",
    }
    assert set(inspect.signature(
        release.reopen_r6_full_union_attribution_release_v1
    ).parameters) == {
        "root_identity",
        "grade_completion_identity",
        "grade_release_config",
        "read_exact",
    }
