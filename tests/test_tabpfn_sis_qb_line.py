import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import tabpfn_sis_qb_line_final_served as final_served
from nfl_dfs.backtest import replay
from nfl_dfs.research.tabpfn_sis_qb_line import (
    SIS_QB_FEATURES,
    active_qb_coverage,
    attach_sis_qb_line,
    build_strict_prior_sis_qb_line,
    feature_contract,
)


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_tabpfn_sis_qb_line",
    ROOT / "scripts/validate_tabpfn_sis_qb_line.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _source() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "season": 2025, "week": week, "team": team,
            "source_run_id": "sis-team-context-tranche-1-v1",
            "pass_block_blown_blocks": week,
            "pass_block_snaps": 40,
            "block_points_earned_per_play": week / 10,
        }
        for team in ("ARI", "ATL") for week in range(1, 6)
    ])


def test_contract_changes_only_frozen_two_columns():
    assert feature_contract(["z", "a"], "control") == ["a", "z"]
    assert feature_contract(["z", "a"], "treatment") == [
        "a", "z", *SIS_QB_FEATURES]
    with pytest.raises(ValueError, match="already contains"):
        feature_contract([SIS_QB_FEATURES[0]], "control")


def test_strict_prior_features_exclude_and_ignore_target_week():
    source = _source()
    before = build_strict_prior_sis_qb_line(source)
    source.loc[(source.team == "ARI") & (source.week == 3),
               "pass_block_blown_blocks"] = 999
    after = build_strict_prior_sis_qb_line(source)
    key = lambda frame: frame[(frame.team == "ARI") & (frame.week == 3)].iloc[0]
    assert key(before).sis_qb_source_week_end == 2
    assert key(before).sis_qb_prior_games == 2
    assert key(before).sis_qb_pass_bb_l4 == pytest.approx((1 / 40 + 2 / 40) / 2)
    assert key(before).sis_qb_pass_bb_l4 == key(after).sis_qb_pass_bb_l4


def test_attach_exposes_features_only_to_qbs_and_preserves_rows():
    features = build_strict_prior_sis_qb_line(_source())
    panel = pd.DataFrame({
        "season": [2025] * 4, "week": [3] * 4,
        "team": ["ARI"] * 4, "position": ["QB", "RB", "WR", "TE"],
        "was_active": [True] * 4,
    })
    got = attach_sis_qb_line(panel, features)
    assert len(got) == len(panel)
    assert got.loc[0, list(SIS_QB_FEATURES)].notna().all()
    assert got.loc[1:, list(SIS_QB_FEATURES)].isna().all().all()
    assert active_qb_coverage(got) == [{
        "season": 2025, "rows": 1, "supported_rows": 1,
        "support_rate": 1.0,
    }]


def test_source_run_and_duplicate_keys_fail_closed():
    wrong = _source()
    wrong["source_run_id"] = "another-run"
    with pytest.raises(ValueError, match="source-run"):
        build_strict_prior_sis_qb_line(wrong)
    duplicate = pd.concat([_source(), _source().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="repeats team-week"):
        build_strict_prior_sis_qb_line(duplicate)


def _report(arm: str, features: list[str]) -> dict:
    return {
        "arm": arm,
        "label_law": "active_only",
        "feature_law": "base",
        "active_context_only": True,
        "code_sha": "abcdef1",
        "output_table": f"p.nfl_features.{validator.TABLES[arm]}",
        "training_source": {"content_checksum": 1},
        "sis_source": {
            "content_checksum": 2,
            "source_run_ids": ["sis-team-context-tranche-1-v1"],
        },
        "feature_columns": features,
        "feature_contract_sha256": f"hash-{arm}",
        "target_seasons": validator.TARGET_SEASONS,
        "quantiles": [0.1],
        "context_max": 28000,
        "random_seed": 7,
        "n_estimators": 4,
        "device": "cuda",
        "output_rows": validator.EXPECTED_ROWS,
        "unique_keys": validator.EXPECTED_ROWS,
        "active_qb_coverage": [
            {"season": season, "support_rate": 0.9}
            for season in validator.TARGET_SEASONS
        ],
        "folds": {
            str(season): {
                "target_rows": 100,
                "sampled_context_rows": 1000,
                "sampled_inactive_rows": 0,
            }
            for season in validator.TARGET_SEASONS
        },
    }


def test_report_gate_requires_active_qb_coverage_and_exact_bundle():
    baseline = ["z", "a"]
    control = _report("control", feature_contract(baseline, "control"))
    treatment = _report(
        "treatment", feature_contract(baseline, "treatment"))
    assert validator.validate_reports(
        control, treatment, "abcdef1", baseline)["passes"]
    treatment["active_qb_coverage"][2]["support_rate"] = 0.79
    result = validator.validate_reports(
        control, treatment, "abcdef1", baseline)
    assert not result["passes"]
    assert not result["checks"]["same_coverage_audits"]


def test_cache_tables_are_research_licensed_and_context_restores(monkeypatch):
    monkeypatch.setenv("TABPFN_MARGINAL_TABLE", "outside")
    for table in final_served.TABLES.values():
        assert replay._tabpfn_marginal_table(
            {"TABPFN_MARGINAL_TABLE": table}) == table
        with final_served._cache_environment(table):
            assert final_served.os.environ["TABPFN_MARGINAL_TABLE"] == table
        assert final_served.os.environ["TABPFN_MARGINAL_TABLE"] == "outside"


def test_cloud_path_is_write_once_and_gates_before_scoring():
    cli = (ROOT / "src/nfl_dfs/cli.py").read_text(encoding="utf-8")
    launch = (ROOT / "scripts/cloud_tabpfn_sis_qb_line.sh").read_text(
        encoding="utf-8")
    finish = (ROOT / "scripts/cloud_finish_tabpfn_sis_qb_line.sh").read_text(
        encoding="utf-8")
    gate = (
        ROOT / "scripts/cloud_tabpfn_sis_qb_line_final_served.sh"
    ).read_text(encoding="utf-8")
    assert "tabpfn-sis-qb-line-final-served" in cli
    assert "WRITE_EMPTY" in (
        ROOT / "scripts/tabpfn_sis_qb_line/gen.py"
    ).read_text(encoding="utf-8")
    assert "selected_active_label.txt" in launch
    assert "sched_selected" in launch and "team_qb_selected" in launch
    assert "TABPFN_SIS_QB_LINE_JSON=" in finish
    assert "tabpfn-sis-qb-line-caches-valid" in gate
    assert "selected_usage.txt" in gate
    assert "primary_gate=aggregate-active-qb-30-point-brier" in gate
