import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import tabpfn_team_qb_final_served
from nfl_dfs.backtest import replay
from nfl_dfs.research.tabpfn_team_qb import (
    broadcast_team_qb_quality,
    feature_contract,
    feature_coverage,
    qb_ngs_support,
)


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_tabpfn_team_qb", ROOT / "scripts/validate_tabpfn_team_qb.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def test_feature_contract_changes_only_the_frozen_broadcast_column():
    base = ["z", "a"]
    assert feature_contract(base, "base", "control") == ["a", "z"]
    assert feature_contract(base, "base", "treatment") == [
        "a", "z", "team_qb_cpoe_l6", "team_qb_cpoe_cross_season"]
    assert feature_contract(base, "sched", "control") == [
        "a", "z", "net_rest_diff", "body_clock_hour"]
    assert feature_contract(base, "sched", "treatment") == [
        "a", "z", "net_rest_diff", "body_clock_hour",
        "team_qb_cpoe_l6", "team_qb_cpoe_cross_season"]
    with pytest.raises(ValueError, match="already contains"):
        feature_contract(["team_qb_cpoe_l6"], "base", "control")


def test_team_qb_quality_is_normalized_and_broadcast_only_to_pass_catchers():
    panel = pd.DataFrame({
        "team": ["OAK", "LV", "SD", "STL"],
        "season": [2022] * 4,
        "week": [1] * 4,
        "position": ["QB", "RB", "WR", "TE"],
    })
    quality = pd.DataFrame({
        "team": ["LV", "LAC", "LA"],
        "season": [2022] * 3,
        "week": [1] * 3,
        "team_qb_cpoe_l6": [1.5, 2.5, 3.5],
        "team_qb_cpoe_cross_season": [1, 0, 1],
    })
    got = broadcast_team_qb_quality(panel, quality)
    assert np.isnan(got.iloc[0].team_qb_cpoe_l6)
    assert got.iloc[1].team_qb_cpoe_l6 == 1.5
    assert got.iloc[2].team_qb_cpoe_l6 == 2.5
    assert got.iloc[3].team_qb_cpoe_l6 == 3.5
    assert np.isnan(got.iloc[0].team_qb_cpoe_cross_season)
    assert got.iloc[1].team_qb_cpoe_cross_season == 1
    assert got.iloc[2].team_qb_cpoe_cross_season == 0
    assert got.iloc[3].team_qb_cpoe_cross_season == 1


def test_team_qb_quality_rejects_duplicate_team_week_keys():
    panel = pd.DataFrame({
        "team": ["LV"], "season": [2022], "week": [1], "position": ["RB"]})
    quality = pd.DataFrame({
        "team": ["LV", "LV"], "season": [2022, 2022], "week": [1, 1],
        "team_qb_cpoe_l6": [1.0, 2.0],
        "team_qb_cpoe_cross_season": [0, 0]})
    with pytest.raises(ValueError, match="not unique"):
        broadcast_team_qb_quality(panel, quality)


def test_team_qb_audits_report_coverage_and_qb_support():
    panel = pd.DataFrame({
        "team": ["LV", "LV", "LV", "LV"],
        "season": [2022] * 4,
        "week": [1] * 4,
        "position": ["QB", "RB", "WR", "TE"],
        "was_active": [True, True, False, True],
        "qb_cpoe_l6": [0.1, np.nan, np.nan, np.nan],
    })
    quality = pd.DataFrame({
        "team": ["LV"], "season": [2022], "week": [1],
        "team_qb_cpoe_l6": [1.0],
        "team_qb_cpoe_cross_season": [1]})
    joined = broadcast_team_qb_quality(panel, quality)
    coverage = feature_coverage(joined)
    assert {row["position"]: row["supported_rows"] for row in coverage} == {
        "QB": 0, "RB": 1, "TE": 1, "WR": 1}
    support = qb_ngs_support(joined)
    assert support == [{
        "season": 2022, "active": True, "rows": 1,
        "supported_rows": 1, "support_rate": 1.0}]


def _report(arm: str, features: list[str]) -> dict:
    folds = {
        str(season): {
            "target_rows": 100,
            "sampled_context_rows": 1000,
            "sampled_inactive_rows": 0,
        }
        for season in validator.TARGET_SEASONS
    }
    return {
        "arm": arm,
        "label_law": "active_only",
        "feature_law": "sched",
        "active_context_only": True,
        "code_sha": "abcdef1",
        "output_table": (
            "p.nfl_features.tabpfn_team_qb_control_v1"
            if arm == "control"
            else "p.nfl_features.tabpfn_team_qb_treatment_v1"),
        "training_source": {"content_checksum": 1},
        "team_qb_source": {"content_checksum": 2},
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
        "team_qb_coverage": [
            {"season": 2022, "position": "QB", "supported_rows": 0}],
        "existing_qb_cpoe_support": [
            {"season": 2022, "active": True, "supported_rows": 1}],
        "folds": folds,
        "inherited_rng_warmup": {},
    }


def test_team_qb_report_gate_requires_frozen_two_column_treatment():
    baseline = ["b", "a"]
    control = feature_contract(baseline, "sched", "control")
    treatment = feature_contract(baseline, "sched", "treatment")
    result = validator.validate_reports(
        _report("control", control), _report("treatment", treatment),
        "abcdef1", "active_only", "sched", baseline)
    assert result["passes"]
    broken = _report("treatment", control)
    result = validator.validate_reports(
        _report("control", control), broken,
        "abcdef1", "active_only", "sched", baseline)
    assert not result["passes"]
    assert not result["checks"]["exact_feature_contracts"]


def test_team_qb_table_gate_requires_changed_predictions(monkeypatch):
    monkeypatch.setattr(validator, "EXPECTED_ROWS", 4)
    common = {
        "season": [2022, 2023, 2024, 2025], "week": [1, 1, 1, 1],
        "gsis_id": ["a", "b", "c", "d"],
        "label_law": ["active_only"] * 4,
        "feature_law": ["sched"] * 4,
        "active_context_only": [True] * 4,
        "code_sha": ["abcdef1"] * 4,
    }
    quantiles = {
        name: [float(index + offset) for offset in range(4)]
        for index, name in enumerate(validator.QUANTILE_COLUMNS)
    }
    left = pd.DataFrame({
        **common, **quantiles, "mean": [1.0, 2.0, 3.0, 4.0],
        "arm": ["control"] * 4,
        "feature_contract_sha256": ["left"] * 4,
    })
    right = left.copy()
    right["arm"] = "treatment"
    right["feature_contract_sha256"] = "right"
    assert not validator.validate_tables(left, right)["passes"]
    right.loc[0, "mean"] = 1.1
    assert validator.validate_tables(left, right)["passes"]
    assert validator.validate_control_reproduction(left, left.copy())["passes"]


def test_team_qb_cloud_path_is_terminal_sched_dependent_and_write_once():
    cli = (ROOT / "src/nfl_dfs/cli.py").read_text(encoding="utf-8")
    launch_side = (ROOT / "scripts/cloud_team_qb_quality_side_table.sh").read_text(
        encoding="utf-8")
    finish_side = (
        ROOT / "scripts/cloud_finish_team_qb_quality_side_table.sh"
    ).read_text(encoding="utf-8")
    launch = (ROOT / "scripts/cloud_tabpfn_team_qb.sh").read_text(
        encoding="utf-8")
    finish = (ROOT / "scripts/cloud_finish_tabpfn_team_qb.sh").read_text(
        encoding="utf-8")
    generator = (ROOT / "scripts/tabpfn_team_qb/gen.py").read_text(
        encoding="utf-8")
    assert "build-team-qb-quality" in cli
    assert "017l_team_qb_quality.sql only" in launch_side
    assert "TEAM_QB_QUALITY_SIDE_TABLE_VALIDATED" in finish_side
    assert "selected_sched.txt" in launch
    assert "side-table-valid" in launch
    assert "tabpfn_sched_treatment_v1" in launch
    assert "WRITE_EMPTY" in generator
    assert "broadcast_team_qb_quality(panel, quality)" in generator
    assert "_advance_inherited_rng(panel, rng)" in generator
    assert "TABPFN_TEAM_QB_JSON=" in finish
    assert "validate_tabpfn_team_qb.py" in finish
    assert "--inherited-table" in finish


def test_team_qb_final_served_cache_scope_is_research_licensed(monkeypatch):
    monkeypatch.setenv("TABPFN_MARGINAL_TABLE", "outside")
    for table in tabpfn_team_qb_final_served.TABLES.values():
        assert replay._tabpfn_marginal_table(
            {"TABPFN_MARGINAL_TABLE": table}) == table
        with tabpfn_team_qb_final_served._cache_environment(table):
            assert tabpfn_team_qb_final_served.os.environ[
                "TABPFN_MARGINAL_TABLE"] == table
        assert tabpfn_team_qb_final_served.os.environ[
            "TABPFN_MARGINAL_TABLE"] == "outside"


def test_team_qb_final_served_cloud_path_uses_terminal_laws():
    cli = (ROOT / "src/nfl_dfs/cli.py").read_text(encoding="utf-8")
    launch = (
        ROOT / "scripts/cloud_tabpfn_team_qb_final_served.sh"
    ).read_text(encoding="utf-8")
    finish = (
        ROOT / "scripts/cloud_finish_tabpfn_team_qb_final_served.sh"
    ).read_text(encoding="utf-8")
    assert "tabpfn-team-qb-final-served" in cli
    assert "selected_usage.txt" in launch
    assert "selected_sched.txt" in launch
    assert "tabpfn-team-qb-caches-valid" in launch
    assert "TABPFN_TEAM_QB_LABEL_LAW" in launch
    assert "TABPFN_TEAM_QB_FEATURE_LAW" in launch
    assert "TABPFN_TEAM_QB_FINAL_SERVED_JSON=" in finish
