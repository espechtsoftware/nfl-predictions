"""Focused offline tests for the bounded R6 realized-score reporter."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
import sys
from typing import Callable, Mapping

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as release
from nfl_dfs.research import corpus_r6_full_union_score_report_v1 as report
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import lr8_label_score_map as shared
from tests import test_corpus_r6_full_union_realized_grading_v1 as fixture


ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    path = ROOT / "scripts/report_corpus_r6_full_union_scores_v1.py"
    spec = importlib.util.spec_from_file_location(
        "report_corpus_r6_full_union_scores_v1_test", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


def _opaque_identity(uri: str, marker: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": marker * 64,
        "bytes": 100,
    }


def _config() -> release.FullUnionGradeReleaseConfigV1:
    return release.FullUnionGradeReleaseConfigV1(
        run_id="r6-grade-report-fixture",
        job="r6-grade-job",
        execution="r6-grade-job-abc12",
        code_sha="a" * 40,
        image=f"grade@sha256:{'b' * 64}",
        expected_supply_run_id="r6-supply-fixture",
        expected_supply_job="r6-supply-job",
        expected_supply_code_sha="c" * 40,
        expected_supply_image=f"supply@sha256:{'d' * 64}",
        snapshot_module_sha256="1" * 64,
        snapshot_cli_sha256="2" * 64,
        snapshot_test_sha256="3" * 64,
        snapshot_cli_test_sha256="4" * 64,
        enabled=True,
    )


class _Reader:
    def __init__(
        self,
        store: fixture._MemoryStore,
        *,
        overrides: Mapping[tuple[str, str, str, int], bytes] | None = None,
        forbid: Callable[[str], bool] | None = None,
    ) -> None:
        self.store = store
        self.overrides = dict(overrides or {})
        self.forbid = forbid or (lambda _uri: False)
        self.calls: list[str] = []

    def __call__(self, identity: Mapping[str, object]) -> bytes:
        uri = str(identity["uri"])
        if self.forbid(uri):
            raise AssertionError(f"forbidden read: {uri}")
        self.calls.append(uri)
        key = fixture._MemoryStore._key(identity)
        if key in self.overrides:
            return self.overrides[key]
        return self.store.read_exact(identity)


def _seeded_identity(
    value: object, *, uri: str, generation: str,
) -> tuple[dict[str, object], bytes]:
    raw = batch.canonical_json_bytes(value)
    return (
        {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        raw,
    )


def _rehash(value: dict[str, object], field: str) -> None:
    value[field] = grading.canonical_sha256({
        key: item for key, item in value.items() if key != field
    })


@pytest.fixture(scope="module")
def published() -> dict[str, object]:
    monkeypatch = pytest.MonkeyPatch()
    config = _config()
    supply_root = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-full-union-realized/r6-supply-fixture"
    )
    panel = fixture._synthetic_panel()
    panel.projection_identity = _opaque_identity(
        f"{supply_root}/outcome-key-projection.json", "2"
    )
    panel.source_identity = _opaque_identity(
        f"{supply_root}/realized-source.json", "3"
    )
    panel.snapshot_identity = _opaque_identity(
        f"{supply_root}/outcome-snapshot.json", "4"
    )
    panel.source["outcome_key_projection_identity"] = panel.projection_identity
    panel.snapshot["outcome_key_projection_identity"] = panel.projection_identity
    panel.snapshot["realized_source_identity"] = panel.source_identity
    panel.projection["later_source_freeze_identity"] = panel.snapshot[
        "later_source_freeze_identity"
    ]
    panel.projection["later_source_freeze_sha256"] = panel.snapshot[
        "later_source_freeze_sha256"
    ]
    panel.source["panel_freeze_identity"] = panel.root_identity
    panel.source["outcome_key_projection_identity"] = panel.projection_identity
    fixture._install_validators(monkeypatch, panel)
    store = fixture._MemoryStore()
    persisted_root, persisted_root_identity = (
        grading.grade_and_publish_r6_full_union_realized_v1(
            panel_freeze_identity=panel.root_identity,
            outcome_key_projection=panel.projection,
            outcome_key_projection_identity=panel.projection_identity,
            realized_source=panel.source,
            realized_source_identity=panel.source_identity,
            outcome_snapshot=panel.snapshot,
            outcome_snapshot_identity=panel.snapshot_identity,
            output_prefix=config.output_root,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    )
    expected_registry = deepcopy(
        persisted_root["logical_grade_root"]["strategy_registry"]
    )
    monkeypatch.setattr(
        report.lane,
        "frozen_full_union_strategies_v1",
        lambda: deepcopy(expected_registry),
    )
    monkeypatch.setattr(
        report.lane, "STRICT_230_STRATEGY_ID", "strategy-7"
    )

    supply_identity = _opaque_identity(f"{supply_root}/completion.json", "5")
    smoke_identity = _opaque_identity(
        f"{supply_root}/actual-root-smoke-receipt.json", "6"
    )
    supply_completion = {
        "run_id": config.expected_supply_run_id,
        "object_uri": supply_identity["uri"],
        "completion_sha256": "c" * 64,
        "query_job_id": "r6_full_union_realized_fixture",
        "panel_freeze_identity": panel.root_identity,
        "outcome_key_projection_identity": panel.projection_identity,
        "realized_source_identity": panel.source_identity,
        "outcome_snapshot_identity": panel.snapshot_identity,
        "actual_root_smoke_receipt_identity": smoke_identity,
    }
    smoke_receipt = {
        "panel_freeze_identity": panel.root_identity,
        "outcome_key_projection_identity": panel.projection_identity,
        "reviewed_source_commit_sha": config.expected_supply_code_sha,
        "runtime_immutable_image": config.expected_supply_image,
        "snapshot_module_sha256": config.snapshot_module_sha256,
        "snapshot_cli_sha256": config.snapshot_cli_sha256,
        "snapshot_test_sha256": config.snapshot_test_sha256,
        "snapshot_cli_test_sha256": config.snapshot_cli_test_sha256,
        "actual_root_smoke_receipt_sha256": "6" * 64,
    }
    lease_body = {
        "version": "historical-outcome-active-v1",
        "run_id": config.expected_supply_run_id,
        "job": config.expected_supply_job,
        "code_sha": config.expected_supply_code_sha,
        "image": config.expected_supply_image,
        "acquired_at": "2026-08-26T00:00:00+00:00",
    }
    lease_raw = shared.canonical_json(lease_body)
    lease_identity = {
        "uri": shared.adapter.HISTORICAL_OUTCOME_LEASE_URI,
        "generation": "1",
        "sha256": sha256(lease_raw).hexdigest(),
        "bytes": len(lease_raw),
    }
    historical_lease = {
        "body": lease_body,
        "object_receipt": {**lease_identity, "create_only": True},
    }
    completion = release.build_grade_completion_v1(
        config=config,
        panel_freeze_identity=panel.root_identity,
        outcome_supply_completion=supply_completion,
        outcome_supply_completion_identity=supply_identity,
        actual_root_smoke_receipt=smoke_receipt,
        actual_root_smoke_receipt_identity=smoke_identity,
        historical_outcome_lease=historical_lease,
        outcome_key_projection=panel.projection,
        outcome_key_projection_identity=panel.projection_identity,
        realized_source=panel.source,
        realized_source_identity=panel.source_identity,
        outcome_snapshot=panel.snapshot,
        outcome_snapshot_identity=panel.snapshot_identity,
        persisted_grade_root=persisted_root,
        persisted_grade_root_identity=persisted_root_identity,
    )
    completion_identity = store.seed(
        config.completion_uri, batch.canonical_json_bytes(completion)
    )
    yield {
        "config": config,
        "store": store,
        "completion": completion,
        "completion_identity": completion_identity,
        "persisted_root": persisted_root,
        "persisted_root_identity": persisted_root_identity,
    }
    monkeypatch.undo()


def _build(
    case: Mapping[str, object],
    *,
    identity: object | None = None,
    read_exact: Callable[[Mapping[str, object]], bytes] | None = None,
) -> dict[str, object]:
    return report.build_persisted_score_report_v1(
        grade_completion_identity=(
            case["completion_identity"] if identity is None else identity
        ),
        grade_release_config=case["config"],  # type: ignore[arg-type]
        read_exact=(
            case["store"].read_exact if read_exact is None else read_exact  # type: ignore[union-attr]
        ),
    )


def _completion_variant(
    case: Mapping[str, object],
    mutate: Callable[[dict[str, object]], None],
    *,
    generation: str,
) -> tuple[dict[str, object], dict[tuple[str, str, str, int], bytes]]:
    completion = deepcopy(case["completion"])
    mutate(completion)
    _rehash(completion, "grade_completion_sha256")
    identity, raw = _seeded_identity(
        completion,
        uri=str(case["completion_identity"]["uri"]),  # type: ignore[index]
        generation=generation,
    )
    return identity, {fixture._MemoryStore._key(identity): raw}


def test_report_is_deterministic_and_reads_only_selected_grade_prefix(
    published: dict[str, object],
) -> None:
    prefix = published["config"].output_root  # type: ignore[union-attr]
    first_reader = _Reader(published["store"])  # type: ignore[arg-type]
    first = _build(published, read_exact=first_reader)
    second = _build(published)

    assert report.canonical_json_bytes(first) == report.canonical_json_bytes(second)
    assert first["strategy_count"] == 8
    assert len(first["strategy_summaries"]) == 8
    assert first["strategy_summaries"][-1]["strict_230_strategy"] is True
    assert all(len(row["cells"]) == 18 for row in first["strategy_summaries"])
    assert first["outcome_source_read"] is False
    assert first["historical_outcome_lease_read"] is False
    assert first_reader.calls
    assert all(uri.startswith(f"{prefix}/") for uri in first_reader.calls)
    assert not any("outcome-snapshot" in uri for uri in first_reader.calls)
    rendered = report.canonical_json_bytes(first)
    assert b'"union_score_rows"' not in rendered
    assert b'"rank_80_score_rows"' not in rendered
    assert b'"selected_lineup_ids"' not in rendered
    assert b'"selected_rosters"' not in rendered


def test_completion_identity_drift_fails_closed(
    published: dict[str, object],
) -> None:
    wrong = {**published["completion_identity"], "sha256": "f" * 64}
    with pytest.raises(report.CorpusR6FullUnionScoreReportV1Error, match="read failed"):
        _build(published, identity=wrong)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("decision_authority", True, "forbidden authority flag"),
        ("snapshot_module_sha256", "e" * 64, "runtime or supply pins"),
        ("source_slate_count", 53, "terminal census"),
    ],
)
def test_self_hashed_flag_pin_and_count_drift_fail_before_root_read(
    published: dict[str, object],
    field: str,
    replacement: object,
    message: str,
) -> None:
    identity, overrides = _completion_variant(
        published,
        lambda completion: completion.__setitem__(field, replacement),
        generation={
            "decision_authority": "201",
            "snapshot_module_sha256": "202",
            "source_slate_count": "203",
        }[field],
    )
    completion_uri = str(identity["uri"])
    reader = _Reader(
        published["store"],  # type: ignore[arg-type]
        overrides=overrides,
        forbid=lambda uri: uri != completion_uri,
    )
    with pytest.raises(report.CorpusR6FullUnionScoreReportV1Error, match=message):
        _build(published, identity=identity, read_exact=reader)
    assert reader.calls == [completion_uri]


def test_self_hashed_cross_run_root_uri_fails_before_forbidden_read(
    published: dict[str, object],
) -> None:
    def mutate(completion: dict[str, object]) -> None:
        retained = dict(completion["persisted_grade_root_identity"])
        retained["uri"] = (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-full-union-realized-grades/other-run/"
            "realized-grade-root.json"
        )
        completion["persisted_grade_root_identity"] = retained

    identity, overrides = _completion_variant(
        published, mutate, generation="204"
    )
    completion_uri = str(identity["uri"])
    reader = _Reader(
        published["store"],  # type: ignore[arg-type]
        overrides=overrides,
        forbid=lambda uri: uri != completion_uri,
    )
    with pytest.raises(
        report.CorpusR6FullUnionScoreReportV1Error,
        match="upstream or grade artifact URI",
    ):
        _build(published, identity=identity, read_exact=reader)
    assert reader.calls == [completion_uri]


def test_scoped_reader_rejects_cross_run_identity_before_delegate() -> None:
    delegated = False

    def forbidden(_identity: Mapping[str, object]) -> bytes:
        nonlocal delegated
        delegated = True
        raise AssertionError("must not delegate")

    scoped = report._scoped_reader(  # noqa: SLF001
        read_exact=forbidden,
        grade_run_prefix=(
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-full-union-realized-grades/selected-run"
        ),
    )
    with pytest.raises(
        report.CorpusR6FullUnionScoreReportV1Error, match="escapes"
    ):
        scoped(_opaque_identity(
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-full-union-realized-grades/other-run/shard.json",
            "f",
        ))
    assert delegated is False


def test_self_hashed_t230_sha_drift_fails_before_any_shard_read(
    published: dict[str, object],
) -> None:
    root = deepcopy(published["persisted_root"])
    logical = root["logical_grade_root"]
    logical["strategy_registry"][-1]["strategy_sha256"] = "f" * 64
    logical["strategy_registry_sha256"] = grading.canonical_sha256(
        logical["strategy_registry"]
    )
    _rehash(logical, "realized_grade_sha256")
    root["logical_grade_root_sha256"] = logical["realized_grade_sha256"]
    _rehash(root, "persisted_grade_root_sha256")
    root_identity, root_raw = _seeded_identity(
        root,
        uri=str(published["persisted_root_identity"]["uri"]),  # type: ignore[index]
        generation="301",
    )

    def mutate_completion(completion: dict[str, object]) -> None:
        completion["persisted_grade_root_identity"] = root_identity
        completion["persisted_grade_root_sha256"] = root[
            "persisted_grade_root_sha256"
        ]
        completion["logical_grade_root_sha256"] = logical[
            "realized_grade_sha256"
        ]
        completion["strategy_registry_sha256"] = logical[
            "strategy_registry_sha256"
        ]
        completion["score_once_identity_sha256"] = release._score_once_identity(  # noqa: SLF001
            persisted_grade_root=root,
            logical_root=logical,
            coverage=logical["coverage"],
        )

    completion_identity, overrides = _completion_variant(
        published, mutate_completion, generation="302"
    )
    overrides[fixture._MemoryStore._key(root_identity)] = root_raw
    reader = _Reader(
        published["store"],  # type: ignore[arg-type]
        overrides=overrides,
        forbid=lambda uri: "/slate-grades/" in uri,
    )
    with pytest.raises(
        report.CorpusR6FullUnionScoreReportV1Error,
        match="eight-strategy registry or T230",
    ):
        _build(published, identity=completion_identity, read_exact=reader)
    assert reader.calls == [
        completion_identity["uri"],
        root_identity["uri"],
    ]


def test_missing_shard_fails_closed(published: dict[str, object]) -> None:
    root = published["persisted_root"]
    missing_uri = root["slate_grade_objects"][17]["slate_grade_identity"]["uri"]
    reader = _Reader(
        published["store"],  # type: ignore[arg-type]
        forbid=lambda uri: uri == missing_uri,
    )
    with pytest.raises(report.CorpusR6FullUnionScoreReportV1Error):
        _build(published, read_exact=reader)


def _argv(case: Mapping[str, object]) -> list[str]:
    identity = case["completion_identity"]
    config = case["config"]
    return [
        "--execute",
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


def test_cli_passes_independent_runtime_and_supply_pins(
    published: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_build(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli.report, "build_persisted_score_report_v1", fake_build)
    assert cli.main(
        _argv(published),
        environ={cli.ENABLED_ENV: "1"},
        storage_client=object(),
    ) == 0
    assert captured["grade_release_config"] == published["config"]
    assert capsys.readouterr().out == '{"ok":true}'


def test_cli_rejects_malformed_pin_before_storage_access(
    published: dict[str, object],
) -> None:
    argv = _argv(published)
    index = argv.index("--snapshot-module-sha256") + 1
    argv[index] = "not-a-sha"

    class NeverStorage:
        def bucket(self, _name: str) -> object:
            raise AssertionError("storage must remain untouched")

    with pytest.raises(cli.ScoreReportCliV1Error, match="runtime identity"):
        cli.main(
            argv,
            environ={cli.ENABLED_ENV: "1"},
            storage_client=NeverStorage(),
        )


def test_cli_rejects_cross_run_completion_uri_before_storage_access(
    published: dict[str, object],
) -> None:
    argv = _argv(published)
    index = argv.index("--grade-completion-uri") + 1
    argv[index] = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-full-union-realized-grades/other-run/grade-completion.json"
    )

    class NeverStorage:
        def bucket(self, _name: str) -> object:
            raise AssertionError("storage must remain untouched")

    with pytest.raises(cli.ScoreReportCliV1Error, match="URI/runtime coordinate"):
        cli.main(
            argv,
            environ={cli.ENABLED_ENV: "1"},
            storage_client=NeverStorage(),
        )


def test_cli_is_default_off(published: dict[str, object]) -> None:
    with pytest.raises(cli.ScoreReportCliV1Error, match="--execute"):
        cli.main(_argv(published), environ={}, storage_client=object())
