from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from scripts import run_corpus_r6_construction_allocation_cross_v1 as runner


def test_runner_is_default_off_and_registry_is_read_only():
    with pytest.raises(SystemExit):
        runner.run([])
    registry = runner.run(["--action", "registry"])
    assert registry["slate_count"] == 54
    assert registry["uses_target_slate_outcomes"] is False
    with pytest.raises(ValueError, match="generate requires"):
        runner.run([
            "--action", "generate",
            "--input-bundle", "/tmp/input.json",
            "--output-selection", "/tmp/output.json",
            "--confirm-generate",
        ])


def test_explicit_generation_is_local_create_once(tmp_path, monkeypatch):
    input_path = tmp_path / "input.json"
    input_path.write_text("{}", encoding="utf-8")
    output_path = tmp_path / "selection.json"
    monkeypatch.setenv(runner.GENERATE_ENABLE_ENV, "1")
    monkeypatch.setattr(runner, "_inputs", lambda bundle: (["inputs"], "authority"))
    selection = {
        "receipt_sha256": "a" * 64,
        "slate_count": 54,
        "cell_order": ["a", "b", "c", "d"],
    }
    monkeypatch.setattr(
        runner.adapter,
        "build_score_blind_cross_from_pit_inputs",
        lambda *args, **kwargs: selection,
    )
    result = runner.run([
        "--action", "generate",
        "--input-bundle", str(input_path.resolve()),
        "--output-selection", str(output_path.resolve()),
        "--confirm-generate",
    ])
    raw = output_path.read_bytes()
    assert json.loads(raw) == selection
    assert result["selection_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["cloud_mutation_performed"] is False
    with pytest.raises(ValueError, match="already exists"):
        runner.run([
            "--action", "generate",
            "--input-bundle", str(input_path.resolve()),
            "--output-selection", str(output_path.resolve()),
            "--confirm-generate",
        ])


def test_parquet_member_is_parsed_from_the_exact_verified_inode(tmp_path):
    path = tmp_path / "source.parquet"
    expected = pd.DataFrame({"player_id": ["p1", "p2"], "mean": [1.25, 2.5]})
    expected.to_parquet(path, index=False)
    raw = path.read_bytes()
    receipt = {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "format": "parquet",
    }
    actual = runner._parquet_member(receipt, label="test source")
    pd.testing.assert_frame_equal(actual, expected)

    forged = dict(receipt)
    forged["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="byte identity differs"):
        runner._parquet_member(forged, label="test source")
