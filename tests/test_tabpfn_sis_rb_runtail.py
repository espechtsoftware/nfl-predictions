from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import zlib

import pandas as pd
import pytest
import numpy as np

from nfl_dfs.analysis import tabpfn_sis_rb_runtail_final_served as final_served
from nfl_dfs.backtest import replay
from nfl_dfs.research.tabpfn_sis_rb_runtail import (
    SIS_RB_RUNTAIL_FEATURES,
    SOURCE_HASH_COLUMNS,
    active_rb_coverage,
    attach_sis_rb_runtail,
    build_strict_prior_sis_rb_runtail,
    feature_contract,
)


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_tabpfn_sis_rb_runtail",
    ROOT / "scripts/validate_tabpfn_sis_rb_runtail.py",
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _source() -> pd.DataFrame:
    rows = []
    for team in ("ARI", "ATL"):
        for week in range(1, 7):
            attempts = 10.0 * week
            row = {
                "season": 2025,
                "week": week,
                "team": team,
                "source_run_id": "sis-team-run-context-tranche-2-v1",
                "rdef_attempts": attempts,
                "rdef_boom_rate": 0.10 * week,
                "rdef_bust_rate": 0.05 * week,
            }
            row.update({column: f"hash-{column}" for column in SOURCE_HASH_COLUMNS})
            rows.append(row)
    return pd.DataFrame(rows)


def test_contract_adds_only_two_frozen_tail_fields():
    assert feature_contract(["z", "a"], "control") == ["a", "z"]
    assert feature_contract(["z", "a"], "treatment") == [
        "a", "z", *SIS_RB_RUNTAIL_FEATURES,
    ]
    with pytest.raises(ValueError, match="already contains"):
        feature_contract([SIS_RB_RUNTAIL_FEATURES[0]], "control")


def test_strict_prior_is_volume_weighted_and_target_mutation_invariant():
    source = _source()
    before = build_strict_prior_sis_rb_runtail(source)
    source.loc[(source.team.eq("ARI")) & source.week.eq(3), [
        "rdef_boom_rate", "rdef_bust_rate",
    ]] = [0.99, 0.99]
    after = build_strict_prior_sis_rb_runtail(source)
    key = lambda frame: frame[(frame.team.eq("ARI")) & frame.week.eq(3)].iloc[0]
    expected_boom = (0.1 * 10 + 0.2 * 20) / 30
    expected_bust = (0.05 * 10 + 0.10 * 20) / 30
    assert key(before).sis_rb_runtail_source_week_end == 2
    assert key(before)[SIS_RB_RUNTAIL_FEATURES[0]] == pytest.approx(expected_boom)
    assert key(before)[SIS_RB_RUNTAIL_FEATURES[1]] == pytest.approx(expected_bust)
    assert key(before)[list(SIS_RB_RUNTAIL_FEATURES)].tolist() == pytest.approx(
        key(after)[list(SIS_RB_RUNTAIL_FEATURES)].tolist()
    )


def test_attach_uses_opponent_only_for_rb_and_preserves_rows():
    strict = build_strict_prior_sis_rb_runtail(_source())
    panel = pd.DataFrame({
        "season": [2025] * 4,
        "week": [3] * 4,
        "opponent": ["ATL"] * 4,
        "position": ["QB", "RB", "WR", "TE"],
        "was_active": [True] * 4,
    })
    result = attach_sis_rb_runtail(panel, strict)
    assert len(result) == len(panel)
    assert result.loc[1, list(SIS_RB_RUNTAIL_FEATURES)].notna().all()
    assert result.loc[[0, 2, 3], list(SIS_RB_RUNTAIL_FEATURES)].isna().all().all()
    assert active_rb_coverage(result) == [{
        "season": 2025, "rows": 1, "supported_rows": 1, "support_rate": 1.0,
    }]


def test_source_identity_range_and_duplicate_keys_fail_closed():
    wrong = _source()
    wrong["source_run_id"] = "wrong"
    with pytest.raises(ValueError, match="source-run"):
        build_strict_prior_sis_rb_runtail(wrong)
    invalid = _source()
    invalid.loc[0, "rdef_boom_rate"] = 1.01
    with pytest.raises(ValueError, match=r"outside \[0,1\]"):
        build_strict_prior_sis_rb_runtail(invalid)
    missing = _source()
    missing.loc[0, "rdef_bust_rate"] = np.nan
    with pytest.raises(ValueError, match=r"outside \[0,1\]"):
        build_strict_prior_sis_rb_runtail(missing)
    negative = _source()
    negative.loc[0, "rdef_attempts"] = -1
    with pytest.raises(ValueError, match="attempts are invalid"):
        build_strict_prior_sis_rb_runtail(negative)
    changed = _source()
    changed.loc[0, SOURCE_HASH_COLUMNS[0]] = "another"
    with pytest.raises(ValueError, match="identity"):
        build_strict_prior_sis_rb_runtail(changed)
    duplicate = pd.concat([_source(), _source().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="repeats team-week"):
        build_strict_prior_sis_rb_runtail(duplicate)


def test_generic_gpu_generator_has_exclusive_run_tail_branch():
    text = open("scripts/tabpfn_sis_qb_line/gen.py", encoding="utf-8").read()
    assert "TABPFN_SIS_RB_RUNTAIL_ARM" in text
    assert "tabpfn_sis_rb_runtail_control_v1" in text
    assert "sis_rb_runtail" in text


def _cache_report(arm: str, features: list[str]) -> dict:
    return {
        "arm": arm,
        "label_law": "active_only",
        "feature_law": "base",
        "active_context_only": True,
        "code_sha": "a" * 40,
        "output_table": f"p.nfl_features.{validator.TABLES[arm]}",
        "training_source": {"content_checksum": 1},
        "sis_source": {
            "content_checksum": 2,
            "source_run_ids": ["sis-team-run-context-tranche-2-v1"],
            "expected_source_run": "sis-team-run-context-tranche-2-v1",
            "source_hash_identities": {
                column: [f"hash-{column}"] for column in SOURCE_HASH_COLUMNS
            },
        },
        "feature_columns": features,
        "feature_contract_sha256": f"hash-{arm}",
        "target_seasons": validator.SHARED.TARGET_SEASONS,
        "quantiles": [0.1],
        "context_max": 28_000,
        "random_seed": 7,
        "n_estimators": 4,
        "device": "cuda",
        "output_rows": validator.SHARED.EXPECTED_ROWS,
        "unique_keys": validator.SHARED.EXPECTED_ROWS,
        "active_rb_coverage": [
            {"season": season, "support_rate": 0.9}
            for season in validator.SHARED.TARGET_SEASONS
        ],
        "folds": {
            str(season): {
                "target_rows": 100,
                "sampled_context_rows": 1_000,
                "sampled_inactive_rows": 0,
            }
            for season in validator.SHARED.TARGET_SEASONS
        },
    }


def test_cache_report_gate_requires_exact_source_bundle_and_coverage():
    baseline = ["z", "a"]
    control = _cache_report(
        "control", feature_contract(baseline, "control")
    )
    treatment = _cache_report(
        "treatment", feature_contract(baseline, "treatment")
    )
    assert validator.validate_reports(
        control, treatment, "a" * 40, baseline
    )["passes"]
    treatment["active_rb_coverage"][2]["support_rate"] = 0.79
    failed = validator.validate_reports(
        control, treatment, "a" * 40, baseline
    )
    assert not failed["passes"]
    assert not failed["checks"]["same_coverage"]


def test_cache_table_rows_must_match_log_and_requested_code_identity():
    baseline = ["z", "a"]
    reports = {
        arm: _cache_report(arm, feature_contract(baseline, arm))
        for arm in validator.TABLES
    }
    frames = {
        arm: pd.DataFrame({
            "arm": [arm],
            "label_law": ["active_only"],
            "feature_law": ["base"],
            "active_context_only": [True],
            "code_sha": ["a" * 40],
            "feature_contract_sha256": [f"hash-{arm}"],
        })
        for arm in validator.TABLES
    }
    assert validator.validate_table_report_identity(
        frames, reports, "a" * 40
    )["passes"]
    frames["treatment"].loc[0, "code_sha"] = "b" * 40
    failed = validator.validate_table_report_identity(
        frames, reports, "a" * 40
    )
    assert not failed["passes"]
    assert not failed["checks"]["treatment_row_identity"]


def _served_folds() -> dict[int, tuple[pd.DataFrame, np.ndarray]]:
    folds = {}
    quantiles = np.linspace(-8.0, 8.0, 10_000)
    for season in (2022, 2023, 2024, 2025):
        rows = []
        draws = []
        for position in ("QB", "RB", "WR", "TE"):
            for row_index in range(2):
                center = 16.0 + row_index
                rows.append({
                    "season": season,
                    "week": row_index + 1,
                    "gsis_id": f"{season}-{position}-{row_index}",
                    "position": position,
                    "actual": center + (3 if row_index else -2),
                    "market_covered": True,
                    "tabpfn_covered": True,
                })
                draws.append(center + quantiles)
        folds[season] = (pd.DataFrame(rows), np.asarray(draws))
    return folds


def test_final_served_gate_is_rb_q95_q99_only(monkeypatch):
    monkeypatch.setattr(final_served, "EXPECTED_RB_ROWS", {
        2023: 2, 2024: 2, 2025: 2,
    })
    control = _served_folds()
    treatment = {
        season: (frame.copy(), draws.copy())
        for season, (frame, draws) in control.items()
    }
    report = final_served.evaluate_runtail_arms(control, treatment)
    assert not report["gate"]["passes"]
    assert report["proper_score_ratio"]["equal_q95_q99_mean_ratio"] \
        == pytest.approx(1.0)
    assert "brier_30" in report["control"]["aggregate"]
    assert "pinball_q99" in report["paired_loss_uncertainty"]


def test_cache_tables_are_allowlisted_and_environment_restores(monkeypatch):
    monkeypatch.setenv("TABPFN_MARGINAL_TABLE", "outside")
    for table in final_served.TABLES.values():
        assert replay._tabpfn_marginal_table(
            {"TABPFN_MARGINAL_TABLE": table}
        ) == table
        with final_served._cache_environment(table):
            assert replay._tabpfn_marginal_table() == table
        assert final_served.os.environ["TABPFN_MARGINAL_TABLE"] == "outside"


def test_final_served_transport_round_trips_with_pinned_metadata(monkeypatch):
    monkeypatch.setattr(final_served, "OUTPUT_CHUNK_SIZE", 100)
    report = {
        "gate": {"passes": False},
        "rows": [{"index": index, "text": f"row-{index:05d}"}
                 for index in range(300)],
    }
    lines = final_served.encoded_report_lines(report)
    meta = json.loads(lines[0].removeprefix(final_served.OUTPUT_META_PREFIX))
    chunks = {}
    for line in lines[1:]:
        header, chunk = line.removeprefix(
            final_served.OUTPUT_CHUNK_PREFIX
        ).split(":", 1)
        index, total = map(int, header.split("/"))
        chunks[index] = chunk
    assert set(chunks) == set(range(total))
    compressed = base64.b64decode(
        "".join(chunks[index] for index in range(total)), validate=True
    )
    content = zlib.decompress(compressed)
    assert len(compressed) == meta["zlib_bytes"]
    assert hashlib.sha256(compressed).hexdigest() == meta["zlib_sha256"]
    assert len(content) == meta["json_bytes"]
    assert hashlib.sha256(content).hexdigest() == meta["json_sha256"]
    assert json.loads(content) == report


def test_cloud_path_is_write_once_adaptive_and_gate_bound():
    launch = (
        ROOT / "scripts/cloud_tabpfn_sis_rb_runtail.sh"
    ).read_text(encoding="utf-8")
    finish = (
        ROOT / "scripts/cloud_finish_tabpfn_sis_rb_runtail.sh"
    ).read_text(encoding="utf-8")
    gate = (
        ROOT / "scripts/cloud_tabpfn_sis_rb_runtail_final_served.sh"
    ).read_text(encoding="utf-8")
    harvest = (
        ROOT / "scripts/cloud_finish_tabpfn_sis_rb_runtail_final_served.sh"
    ).read_text(encoding="utf-8")
    generator = (
        ROOT / "scripts/tabpfn_sis_qb_line/gen.py"
    ).read_text(encoding="utf-8")
    assert "WRITE_EMPTY" in generator
    assert "TABPFN_SIS_RB_RUNTAIL_ARM" in generator
    assert "executions.txt" in launch
    assert "TABPFN_SIS_RB_RUNTAIL_JSON=" in finish
    assert "tabpfn-sis-rb-runtail-caches-valid" in gate
    assert "adaptive_retrospective=true" in gate
    assert "equal-q95-q99-normalized-pinball" in gate
    assert "TABPFN_SIS_RB_RUNTAIL_FINAL_SERVED_META=" in harvest
    assert "json_sha256" in harvest
