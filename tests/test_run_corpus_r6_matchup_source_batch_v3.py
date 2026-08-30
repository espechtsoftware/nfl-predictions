from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_corpus_r6_matchup_source_batch_v3 as runner


def test_validate_and_task0_are_distinct_default_off_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner.batch,
        "validate_matchup_source_batch_outer_candidate_authority_v3",
        lambda: {"mode": "validate", "cloud_write_performed": False},
    )
    monkeypatch.setattr(
        runner.batch,
        "validate_matchup_source_batch_task0_readiness_v3",
        lambda: {"mode": "task0", "write_capability_enabled": False},
    )
    assert runner.run(["--action", "validate"])["mode"] == "validate"
    assert runner.run(["--action", "task0"])["mode"] == "task0"


def test_publish_requires_both_confirmation_and_enable_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        runner.batch,
        "publish_matchup_source_batch_outer_candidate_authority_v3",
        lambda *, run_id: called.append(run_id) or {"complete": True},
    )
    monkeypatch.delenv(runner.batch.PUBLISH_ENABLE_ENV, raising=False)
    with pytest.raises(ValueError, match="publish requires"):
        runner.run([
            "--action", "publish", "--run-id", "fixture-source-v3",
            "--confirm-publish",
        ])
    monkeypatch.setenv(runner.batch.PUBLISH_ENABLE_ENV, "1")
    with pytest.raises(ValueError, match="publish requires"):
        runner.run([
            "--action", "publish", "--run-id", "fixture-source-v3",
        ])
    assert runner.run([
        "--action", "publish", "--run-id", "fixture-source-v3",
        "--confirm-publish",
    ]) == {"complete": True}
    assert called == ["fixture-source-v3"]


def test_reopen_accepts_only_one_absolute_regular_identity_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = {
        "uri": "gs://bucket/path/root.json",
        "generation": "1",
        "sha256": "a" * 64,
        "bytes": 1,
    }
    path = tmp_path / "root-identity.json"
    path.write_text(json.dumps(identity), encoding="utf-8")
    monkeypatch.setattr(
        runner.batch,
        "reopen_matchup_source_batch_outer_candidate_authority_v3",
        lambda *, batch_release_identity: {
            "identity": batch_release_identity,
            "write_capability_enabled": False,
        },
    )
    result = runner.run([
        "--action", "reopen", "--batch-root-identity", str(path.resolve()),
    ])
    assert result["identity"] == identity
    assert result["write_capability_enabled"] is False
    with pytest.raises(ValueError, match="absolute"):
        runner.run([
            "--action", "reopen", "--batch-root-identity", path.name,
        ])
