from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from nfl_dfs.research import (
    corpus_r6_matchup_capture_plan_from_seven_pack_v1 as bridge,
)
from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_v1 as capture
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from tests import test_corpus_r6_matchup_seven_pack_capture_v1 as fixture


def _identity(label: str) -> dict[str, object]:
    raw = label.encode()
    return {
        "uri": f"gs://fixture/{label}.json",
        "generation": str(int(sha256(raw).hexdigest()[:12], 16) + 1),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def test_load_release_reopens_complete_seven_pack_before_deriving_rows() -> None:
    store = fixture._MemoryStore()
    inputs = fixture._inputs(store)
    published = capture.publish_seven_pack_capture_v1(
        run_id="sevenpack-plan-bridge-test",
        fixed_source_root_identity=inputs["fixed"],
        artifact_manifest_identities=inputs["manifests"],
        implementation_authority=fixture._implementation(),
        query_warehouse=lambda spec: fixture._query_result(dict(spec)),
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    release, reopened, rows = bridge._load_release_and_rows(
        release_identity=published["terminal_release_identity"],
        read_exact=store.read,
    )
    assert reopened["complete"] is True
    assert reopened["all_seven_rows_exact_reopened"] is True
    assert [row["pack_id"] for row in rows] == list(source.PACK_IDS)
    assert release["fixed_source_root_identity"] == inputs["fixed"]


def test_capture_plan_uses_candidate_from_release_and_commit_a_adapter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    events: list[str] = []
    release_identity = _identity("seven-pack")
    candidate_identity = _identity("candidate-v2")
    release = {
        "fixed_source_root_identity": candidate_identity,
        "upstream_release_sha256": "a" * 64,
    }
    rows = [{"pack_id": pack_id} for pack_id in source.PACK_IDS]
    reopened = {
        "reopen_receipt_sha256": "b" * 64,
        "release_identity": release_identity,
    }
    monkeypatch.setattr(
        bridge,
        "_load_release_and_rows",
        lambda **_: events.append("seven-pack-reopen") or (release, reopened, rows),
    )
    captured: dict[str, object] = {}

    def build(**kwargs: object) -> dict[str, object]:
        events.append("build-plan")
        captured.update(kwargs)
        return {"schema_version": "fixture-plan", "capture_plan_sha256": "c" * 64}

    monkeypatch.setattr(bridge.capture_v3, "build_capture_plan_lock_v3", build)
    monkeypatch.setattr(
        bridge.capture_v3,
        "validate_capture_plan_against_prerequisites_v3",
        lambda plan, **_: events.append("rebuild-plan") or dict(plan),
    )
    result = bridge.build_capture_plan_from_seven_pack_v1(
        release_identity=release_identity,
        repository_root=tmp_path.resolve(),
        read_exact=lambda _: b"unused",
        git_head=lambda _: events.append("git-head") or "d" * 40,
        git_blob=lambda _root, _commit, _path: b"adapter-lock\n",
        git_status=lambda _root, _paths: b"",
    )
    assert events == [
        "seven-pack-reopen", "git-head", "build-plan", "rebuild-plan"
    ]
    assert captured["candidate_authority_root_identity"] == candidate_identity
    assert captured["upstream_source_release_identity"] == release_identity
    assert captured["upstream_pack_row_objects"] == rows
    assert captured["producer_namespace"] == bridge.PRODUCER_NAMESPACE
    assert result["capture_plan_built_after_complete_seven_pack_reopen"] is True
    assert result["capture_plan_requires_distinct_tracking_commit_b"] is True
    assert result["capture_plan_publication_count"] == 0
    expected_raw = source.canonical_json_bytes(result["capture_plan"]) + b"\n"
    assert result["capture_plan_sha256"] == sha256(expected_raw).hexdigest()
    assert result["capture_plan_bytes"] == len(expected_raw)


def test_failed_seven_pack_reopen_prevents_git_and_plan_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        bridge.seven_pack,
        "reopen_seven_pack_capture_v1",
        lambda **_: (_ for _ in ()).throw(
            capture.CorpusR6MatchupSevenPackCaptureV1Error("bad release")
        ),
    )
    with pytest.raises(
        bridge.CorpusR6MatchupCapturePlanFromSevenPackV1Error,
        match="independent reopen failed",
    ):
        bridge.build_capture_plan_from_seven_pack_v1(
            release_identity=_identity("bad-seven-pack"),
            repository_root=tmp_path.resolve(),
            read_exact=lambda _: b"unused",
            git_head=lambda _: calls.append("git") or "d" * 40,
            git_blob=lambda *_: calls.append("blob") or b"bad",
            git_status=lambda *_: b"",
        )
    assert calls == []
