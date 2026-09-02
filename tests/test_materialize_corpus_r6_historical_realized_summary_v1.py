from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from scripts import materialize_corpus_r6_historical_realized_summary_v1 as runner

SUMMARY = {
    "schema_version": "fixture-summary/v1",
    "source_binding": {"source_object_count": 219},
    "summary_sha256": "a" * 64,
}


def test_build_derives_roots_from_receipt_and_delegates_exact_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    funnel_raw = b'{"funnel":"exact"}'
    (staging / "no-rescore-funnel-release.json").write_bytes(funnel_raw)
    candidate_identity = {"uri": "fixture://candidate"}
    funnel_identity = {"uri": "fixture://funnel"}
    receipt_raw = (
        runner.summary_v1.canonical_json_bytes(
            {
                "source_root_identities": {
                    "candidate_v2": candidate_identity,
                    "no_rescore_funnel": funnel_identity,
                }
            }
        )
        + b"\n"
    )
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_bytes(receipt_raw)
    exact_inputs = [object()]
    catalog_identity = {"uri": "fixture://catalog"}
    plan = object()
    calls: dict[str, object] = {}

    def inputs(**kwargs: object) -> tuple[object, object, object, object]:
        calls["inputs"] = kwargs
        return (
            exact_inputs,
            candidate_identity,
            catalog_identity,
            funnel_identity,
        )

    def build_plan(**kwargs: object) -> object:
        calls["plan"] = kwargs
        return plan

    def build_summary(**kwargs: object) -> dict[str, object]:
        calls["summary"] = kwargs
        return SUMMARY

    monkeypatch.setattr(runner.e0_runner, "_inputs", inputs)
    monkeypatch.setattr(
        runner.historical, "build_historical_corpus_graph_plan_v1", build_plan
    )
    monkeypatch.setattr(
        runner.summary_v1,
        "build_historical_realized_summary_v1",
        build_summary,
    )

    assert (
        runner._build_summary(
            staging_dir=staging,
            accepted_e0_receipt_path=receipt_path,
        )
        == SUMMARY
    )
    assert calls["inputs"] == {
        "staging_dir": staging,
        "candidate_identity": candidate_identity,
        "funnel_identity": funnel_identity,
    }
    assert calls["plan"] == {
        "exact_objects": exact_inputs,
        "candidate_root_identity": candidate_identity,
        "catalog_outer_identity": catalog_identity,
        "attribution_root_identity": funnel_identity,
    }
    assert calls["summary"] == {
        "accepted_e0_receipt_raw": receipt_raw,
        "no_rescore_funnel_raw": funnel_raw,
        "e0_plan": plan,
    }


def test_main_writes_one_canonical_create_once_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    receipt = tmp_path / "accepted.json"
    receipt.write_bytes(b"{}\n")
    output = tmp_path / "nested" / "summary.json"
    build_calls: list[tuple[Path, Path]] = []

    def build(
        *, staging_dir: Path, accepted_e0_receipt_path: Path
    ) -> dict[str, object]:
        build_calls.append((staging_dir, accepted_e0_receipt_path))
        return SUMMARY

    monkeypatch.setattr(runner, "_build_summary", build)
    monkeypatch.setattr(
        runner.summary_v1,
        "validate_historical_realized_summary_v1",
        lambda value: value,
    )
    assert (
        runner.main(
            [
                "--staging-dir",
                str(staging),
                "--accepted-e0-receipt",
                str(receipt),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    expected = runner.summary_v1.canonical_json_bytes(SUMMARY) + b"\n"
    assert output.read_bytes() == expected
    result = json.loads(capsys.readouterr().out)
    assert result["artifact_file_sha256"] == sha256(expected).hexdigest()
    assert result["summary_sha256"] == SUMMARY["summary_sha256"]
    assert result["source_object_count"] == 219
    assert result["neo4j_access_performed"] is False
    assert result["scoring_performed"] is False
    assert build_calls == [(staging.resolve(), receipt.resolve())]

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        runner.main(
            [
                "--staging-dir",
                str(staging),
                "--accepted-e0-receipt",
                str(receipt),
                "--output",
                str(output),
            ]
        )
    assert build_calls == [(staging.resolve(), receipt.resolve())]
    assert output.read_bytes() == expected


def test_build_fails_before_source_enumeration_without_bound_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(b"{}\n")
    enumerated = False

    def inputs(**_kwargs: object) -> object:
        nonlocal enumerated
        enumerated = True
        raise AssertionError("must not enumerate")

    monkeypatch.setattr(runner.e0_runner, "_inputs", inputs)
    with pytest.raises(SystemExit, match="source root identities"):
        runner._build_summary(
            staging_dir=tmp_path,
            accepted_e0_receipt_path=receipt,
        )
    assert enumerated is False
