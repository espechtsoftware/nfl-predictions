from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_corpus_r6_matchup_source_task0_v3 as runner


def test_worker_exposes_only_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runner.task0,
        "publish_task0_worker_v3",
        lambda *, run_id: {"run_id": run_id, "complete": True},
    )
    assert runner.run([
        "--action", "worker", "--run-id", "fixture-task0-run",
    ])["run_id"] == "fixture-task0-run"
    with pytest.raises(ValueError, match="only --run-id"):
        runner.run([
            "--action", "worker", "--run-id", "fixture-task0-run",
            "--worker-result-identity", "/tmp/identity.json",
        ])


def test_verify_accepts_one_absolute_identity_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = {"uri": "gs://bucket/root.json", "generation": "1",
                "sha256": "a" * 64, "bytes": 1}
    path = tmp_path / "worker.json"
    path.write_text(json.dumps(identity), encoding="utf-8")
    monkeypatch.setattr(
        runner.task0,
        "verify_task0_worker_v3",
        lambda *, worker_result_identity: {
            "identity": worker_result_identity, "complete": True,
        },
    )
    assert runner.run([
        "--action", "verify", "--worker-result-identity", str(path.resolve()),
    ])["identity"] == identity


def test_validate_receipt_is_read_only_local_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = {"schema_version": "fixture"}
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(
        runner.task0,
        "validate_task0_provider_receipt_v3",
        lambda value: {"validated": value},
    )
    assert runner.run([
        "--action", "validate-receipt", "--verifier-receipt", str(path.resolve()),
    ])["validated"] == receipt


def test_public_cli_excludes_provider_receipt_construction(tmp_path: Path) -> None:
    spec = tmp_path / "provider-spec.json"
    output = tmp_path / "operator-output.json"
    spec.write_text("{}", encoding="utf-8")
    output.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        runner.run([
            "--action", "bind-provider-receipt",
            "--provider-spec", str(spec.resolve()),
            "--operator-output", str(output.resolve()),
        ])
    parser = runner._parser()
    action = next(row for row in parser._actions if row.dest == "action")
    assert "bind-provider-receipt" not in action.choices
