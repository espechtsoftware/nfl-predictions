from __future__ import annotations

import json

import pytest

from nfl_dfs.research import (
    corpus_r6_matchup_batch_candidate_authority_v1 as batch,
)
from scripts import run_corpus_r6_matchup_source_batch_v2 as operator


def test_cli_is_default_off_and_validate_has_no_cloud_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(SystemExit):
        operator.run([])
    expected = {"validated": True, "uses_realized_outcomes": False}
    monkeypatch.setattr(
        batch,
        "validate_matchup_source_batch_candidate_authority_v1",
        lambda: expected,
    )
    assert operator.run(["--action", "validate"]) == expected
    with pytest.raises(ValueError, match="validate accepts no"):
        operator.run(["--action", "validate", "--run-id", "forbidden-run"])


def test_publish_requires_dual_confirmation_and_exposes_only_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        batch,
        "publish_matchup_source_batch_candidate_authority_v1",
        lambda *, run_id: calls.append(run_id) or {"run_id": run_id},
    )
    with pytest.raises(ValueError, match="publish requires"):
        operator.run([
            "--action", "publish", "--run-id", "fixture-source-batch",
            "--confirm-publish",
        ])
    monkeypatch.setenv(batch.PUBLISH_ENABLE_ENV, "1")
    assert operator.run([
        "--action", "publish", "--run-id", "fixture-source-batch",
        "--confirm-publish",
    ]) == {"run_id": "fixture-source-batch"}
    assert calls == ["fixture-source-batch"]


def test_reopen_accepts_only_absolute_generation_pinned_identity_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = {
        "uri": "gs://fixture-bucket/fixed/matchup-source-batch-release.json",
        "generation": "17",
        "sha256": "a" * 64,
        "bytes": 123,
    }
    path = tmp_path / "root-identity.json"
    path.write_text(json.dumps(identity), encoding="utf-8")
    monkeypatch.setattr(
        batch,
        "reopen_matchup_source_batch_candidate_authority_v1",
        lambda *, batch_release_identity: {
            "identity": batch_release_identity,
            "uses_realized_outcomes": False,
        },
    )
    result = operator.run([
        "--action", "reopen", "--batch-root-identity", str(path.resolve()),
    ])
    assert result["identity"] == identity
    with pytest.raises(ValueError, match="requires only"):
        operator.run([
            "--action", "reopen", "--batch-root-identity", str(path.resolve()),
            "--run-id", "forbidden-run",
        ])
