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


def test_public_cli_excludes_direct_full_publication(
    tmp_path: Path,
) -> None:
    gate_receipt = tmp_path / "task0-verifier-receipt.json"
    gate_receipt.write_text('{"gate":"fixture"}', encoding="utf-8")
    with pytest.raises(SystemExit):
        runner.run([
            "--action", "publish", "--run-id", "fixture-source-v3",
            "--task0-verifier-receipt", str(gate_receipt.resolve()),
            "--confirm-publish",
        ])
    parser = runner._parser()
    action = next(row for row in parser._actions if row.dest == "action")
    assert tuple(action.choices) == ("validate", "task0", "reopen")


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
