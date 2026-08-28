from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as grader


def _load_cli():
    path = Path("scripts/run_corpus_r6_novel_roster_realized_grader_v1.py")
    spec = importlib.util.spec_from_file_location("novel_roster_grader_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(label: str, ordinal: int = 0) -> dict[str, object]:
    raw = grader.canonical_json_bytes_v1({"label": label, "ordinal": ordinal})
    return {
        "uri": f"gs://fixture/{label}-{ordinal}.json",
        "generation": str(ordinal + 1),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _Store:
    def read_exact(self, _identity):
        raise AssertionError("patched core should own reads")

    def publish_create_once(self, _uri, _raw):
        raise AssertionError("patched core should own publication")


def test_create_terminal_root_request_delegates_exact_54_and_output_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_cli()
    manifest_identity = _identity("manifest")
    result_identities = [_identity("result", ordinal) for ordinal in range(54)]
    published_identity = _identity("terminal-root", 99)
    calls = []

    def publish(**kwargs):
        calls.append(kwargs)
        return ({
            "adapter_id": grader.HARD230_ADAPTER,
            "terminal_experiment_root_sha256": "a" * 64,
            "source_slate_count": 54,
        }, published_identity)

    monkeypatch.setattr(grader, "publish_terminal_experiment_root_v1", publish)
    store = _Store()
    result = cli.create_terminal_root_from_request_v1({
        "adapter_id": grader.HARD230_ADAPTER,
        "task_manifest_identity": manifest_identity,
        "task_result_identities": result_identities,
        "output_uri": "gs://fixture/grading/hard230-terminal-root.json",
    }, store=store)
    assert len(calls) == 1
    assert calls[0]["task_result_identities"] == result_identities
    assert calls[0]["target_uri"].endswith("hard230-terminal-root.json")
    assert calls[0]["read_exact"] == store.read_exact
    assert calls[0]["publish_create_once"] == store.publish_create_once
    assert result["terminal_root_identity"] == published_identity
    assert result["source_slate_count"] == 54


def test_create_terminal_root_rejects_non54_before_core_or_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_cli()
    calls = 0

    def publish(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("core must not be reached")

    monkeypatch.setattr(grader, "publish_terminal_experiment_root_v1", publish)
    with pytest.raises(
        cli.RunCorpusR6NovelRosterRealizedGraderV1Error,
        match="exactly 54",
    ):
        cli.create_terminal_root_from_request_v1({
            "adapter_id": grader.POPULATION_CROSSED_ADAPTER,
            "task_manifest_identity": _identity("manifest"),
            "task_result_identities": [_identity("result")],
            "output_uri": "gs://fixture/grading/terminal-root.json",
        }, store=_Store())
    assert calls == 0


def test_grade_request_uses_fixed_identities_and_publishes_one_scorecard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_cli()
    terminal_identity = _identity("terminal-root")
    outcome_identity = _identity("outcome-snapshot")
    scorecard_identity = _identity("scorecard")
    calls = []

    def grade_and_publish(**kwargs):
        calls.append(kwargs)
        return ({
            "adapter_id": grader.POPULATION_CROSSED_ADAPTER,
            "terminal_root_identity": terminal_identity,
            "outcome_snapshot_identity": outcome_identity,
            "realized_grade_sha256": "b" * 64,
            "source_slate_count": 54,
            "aggregate_cell_count": 315,
            "terminal_before_first_outcome_read": True,
        }, scorecard_identity)

    monkeypatch.setattr(
        grader,
        "grade_and_publish_novel_roster_experiment_realized_v1",
        grade_and_publish,
    )
    store = _Store()
    result = cli.grade_from_request_v1({
        "terminal_root_identity": terminal_identity,
        "outcome_snapshot_identity": outcome_identity,
        "output_uri": "gs://fixture/grading/scorecard.json",
    }, store=store)
    assert len(calls) == 1
    assert calls[0]["terminal_root_identity"] == terminal_identity
    assert calls[0]["outcome_snapshot_identity"] == outcome_identity
    assert calls[0]["target_uri"].endswith("scorecard.json")
    assert calls[0]["read_terminal_exact"] == store.read_exact
    assert calls[0]["read_outcome_exact"] == store.read_exact
    assert calls[0]["publish_create_once"] == store.publish_create_once
    assert result["realized_scorecard_identity"] == scorecard_identity
    assert result["terminal_before_first_outcome_read"] is True


def test_request_files_are_canonical_and_local_results_are_create_once(
    tmp_path: Path,
) -> None:
    cli = _load_cli()
    request = {"adapter_id": grader.HARD230_ADAPTER}
    request_path = tmp_path / "request.json"
    request_path.write_bytes(grader.canonical_json_bytes_v1(request))
    assert cli._request_file(request_path, label="fixture request") == request

    noncanonical = tmp_path / "noncanonical.json"
    noncanonical.write_text('{"adapter_id": "hard230-v1"}\n')
    with pytest.raises(
        cli.RunCorpusR6NovelRosterRealizedGraderV1Error,
        match="not canonical",
    ):
        cli._request_file(noncanonical, label="fixture request")

    output = tmp_path / "result.json"
    cli._write_create_once(output, {"complete": True})
    with pytest.raises(
        cli.RunCorpusR6NovelRosterRealizedGraderV1Error,
        match="already exists",
    ):
        cli._write_create_once(output, {"complete": True})
