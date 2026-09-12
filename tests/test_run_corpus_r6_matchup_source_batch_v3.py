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


def test_secure_current_observation_matches_the_consumer_contract(tmp_path):
    """The producer must emit the exact shape the capture-plan reader requires.

    This shape previously existed only in the consumer and in hand-built test
    fixtures; the real producer returned raw bytes, so the tracked
    capture-plan-v3 reopen failed with "must be a string-keyed object" and the
    source-v3 image could never build its own validation step.
    """
    from nfl_dfs.research import (
        corpus_r6_matchup_capture_plan_v1 as capture_v1,
        corpus_r6_matchup_source_batch_outer_candidate_authority_v3 as batch,
    )

    root = tmp_path.resolve()
    (root / "reports").mkdir()
    target = root / "reports" / "probe.json"
    target.write_bytes(b'{"a":1}')

    observation = batch._secure_current_observation(root, "reports/probe.json")

    # Exactly the consumer's field set -- no more, no less.
    assert set(observation) == set(capture_v1._SECURE_CURRENT_OBSERVATION_FIELDS)
    assert observation["relative_path"] == "reports/probe.json"
    assert observation["raw"] == b'{"a":1}'
    assert observation["is_regular_file"] is True
    assert observation["is_symlink"] is False
    assert observation["opened_nofollow"] is True


def test_secure_current_observation_refuses_a_symlink(tmp_path):
    """The flags are entailed by the read, not asserted over it.

    A symlink must raise rather than return an observation claiming
    is_symlink False -- that is what makes the hardcoded flags truthful.
    """
    import pytest

    from nfl_dfs.research import (
        corpus_r6_matchup_source_batch_outer_candidate_authority_v3 as batch,
    )

    root = tmp_path.resolve()
    (root / "reports").mkdir()
    (root / "real.json").write_bytes(b'{"a":1}')
    (root / "reports" / "link.json").symlink_to(root / "real.json")

    with pytest.raises(Exception):
        batch._secure_current_observation(root, "reports/link.json")
