from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_a2a_production_law_dependence_remeasurement.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("a2a_remeasurement_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_static_frozen_references_validate() -> None:
    runner = _load_runner()
    sources = runner._validate_static_sources()
    control = runner._validate_control_reference()

    assert sources[
        "reports/2026-08-20-a2a-production-law-dependence-remeasurement-protocol.md"
    ] == runner.PROTOCOL_SHA256
    assert control["sha256"] == runner.CONTROL_REPORT_SHA256


def test_locked_catalog_reproduces_reporting_only_coverage() -> None:
    runner = _load_runner()
    lock = json.loads((
        ROOT / "reports/production-law-dependence-runs/"
        "20260817-production-law-dependence-source-lock-v1/source-lock.json"
    ).read_text())
    coverage = runner.decision.support_accounting(lock["catalog"])

    for key, value in runner.EXPECTED_ACCOUNTING.items():
        assert coverage[key] == value
    assert coverage["covered_group_fraction"] == 1_041 / 1_194
    assert coverage["direct_row_transform_fraction"] == 7_171 / 9_469


def test_historical_path_is_default_off_before_any_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a disabled runner constructed a cloud client")

    monkeypatch.setattr(runner.storage, "Client", forbidden)
    monkeypatch.setattr(runner.bigquery, "Client", forbidden)
    monkeypatch.delenv("A2A_REMEASUREMENT_ENABLED", raising=False)
    with pytest.raises(RuntimeError, match="default-off"):
        runner.run_historical(
            execute_frozen=False,
            protocol_sha256=runner.PROTOCOL_SHA256,
            output_uri=runner.OUTPUT_URI,
        )

    with pytest.raises(RuntimeError, match="default-off"):
        runner.run_historical(
            execute_frozen=True,
            protocol_sha256=runner.PROTOCOL_SHA256,
            output_uri=runner.OUTPUT_URI,
        )


def test_outcome_query_is_narrow_and_lineup_free() -> None:
    runner = _load_runner()
    compact = " ".join(runner.OUTCOME_SQL.lower().split())
    assert "select season, week, id as player_id, actual" in compact
    for forbidden in (
        "actual_score", "candidate", "lineup", "winner", "ownership",
        "payout", "standing", "selected",
    ):
        assert forbidden not in compact


def test_historical_identity_mismatch_precedes_any_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()
    monkeypatch.setenv("A2A_REMEASUREMENT_ENABLED", "1")
    monkeypatch.setenv("CODE_SHA", "a" * 40)
    monkeypatch.setenv("ANALYSIS_IMAGE", "example/image@sha256:" + "b" * 64)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("identity mismatch constructed a cloud client")

    monkeypatch.setattr(runner.storage, "Client", forbidden)
    with pytest.raises(RuntimeError, match="frozen identity differs"):
        runner.run_historical(
            execute_frozen=True,
            protocol_sha256="0" * 64,
            output_uri=runner.OUTPUT_URI,
        )


def test_result_serialization_rejects_nonfinite_values() -> None:
    runner = _load_runner()
    with pytest.raises(RuntimeError, match="nonfinite"):
        runner._canonical_json({"bad": float("nan")})
