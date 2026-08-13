import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.analysis import tabpfn_sis_rb_rdef_final_served as final_served
from nfl_dfs.backtest import replay
from nfl_dfs.research.tabpfn_sis_rb_rdef import (
    SIS_RB_FEATURE,
    SOURCE_HASH_COLUMNS,
    active_rb_coverage,
    attach_sis_rb_rdef,
    build_strict_prior_sis_rb_rdef,
    feature_contract,
)


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_tabpfn_sis_rb_rdef",
    ROOT / "scripts/validate_tabpfn_sis_rb_rdef.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _source():
    rows = []
    for team in ("ARI", "ATL"):
        for week in range(1, 6):
            row = {
                "season": 2025, "week": week, "team": team,
                "source_run_id": "sis-team-run-context-tranche-2-v1",
                "rdef_points_saved": week, "rdef_attempts": 20,
            }
            row.update({column: f"hash-{column}" for column in SOURCE_HASH_COLUMNS})
            rows.append(row)
    return pd.DataFrame(rows)


def test_contract_changes_only_frozen_rb_column():
    assert feature_contract(["z", "a"], "control") == ["a", "z"]
    assert feature_contract(["z", "a"], "treatment") == [
        "a", "z", SIS_RB_FEATURE]


def test_strict_prior_excludes_target_and_uses_volume_ratio():
    source = _source()
    before = build_strict_prior_sis_rb_rdef(source)
    source.loc[(source.team == "ARI") & (source.week == 3),
               "rdef_points_saved"] = 999
    after = build_strict_prior_sis_rb_rdef(source)
    key = lambda frame: frame[(frame.team == "ARI") & (frame.week == 3)].iloc[0]
    assert key(before).sis_rb_rdef_source_week_end == 2
    assert key(before)[SIS_RB_FEATURE] == pytest.approx(3 / 40)
    assert key(before)[SIS_RB_FEATURE] == key(after)[SIS_RB_FEATURE]


def test_attach_uses_opponent_only_on_rb_and_preserves_rows():
    features = build_strict_prior_sis_rb_rdef(_source())
    panel = pd.DataFrame({
        "season": [2025] * 4, "week": [3] * 4, "opp": ["ATL"] * 4,
        "position": ["QB", "RB", "WR", "TE"], "was_active": [True] * 4,
    })
    got = attach_sis_rb_rdef(panel, features)
    assert len(got) == len(panel)
    assert pd.isna(got.loc[0, SIS_RB_FEATURE])
    assert got.loc[1, SIS_RB_FEATURE] == pytest.approx(3 / 40)
    assert got.loc[[0, 2, 3], SIS_RB_FEATURE].isna().all()
    assert active_rb_coverage(got) == [{
        "season": 2025, "rows": 1, "supported_rows": 1,
        "support_rate": 1.0,
    }]


def test_source_identity_and_duplicate_keys_fail_closed():
    wrong = _source()
    wrong["source_run_id"] = "wrong"
    with pytest.raises(ValueError, match="source-run"):
        build_strict_prior_sis_rb_rdef(wrong)
    changed = _source()
    changed.loc[0, SOURCE_HASH_COLUMNS[0]] = "another"
    with pytest.raises(ValueError, match="identity"):
        build_strict_prior_sis_rb_rdef(changed)
    duplicate = pd.concat([_source(), _source().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="repeats team-week"):
        build_strict_prior_sis_rb_rdef(duplicate)


def test_cache_tables_are_research_licensed_and_context_restores(monkeypatch):
    monkeypatch.setenv("TABPFN_MARGINAL_TABLE", "outside")
    for table in final_served.TABLES.values():
        assert replay._tabpfn_marginal_table(
            {"TABPFN_MARGINAL_TABLE": table}) == table
        with final_served._cache_environment(table):
            assert replay.os.environ["TABPFN_MARGINAL_TABLE"] == table
        assert replay.os.environ["TABPFN_MARGINAL_TABLE"] == "outside"


def test_report_validator_requires_hashes_and_active_rb_coverage():
    baseline = ["z", "a"]
    def report(arm):
        return {
            "arm": arm, "label_law": "active_only", "feature_law": "base",
            "active_context_only": True, "code_sha": "abcdef1",
            "output_table": f"p.nfl_features.{validator.TABLES[arm]}",
            "training_source": {"content_checksum": 1},
            "sis_source": {
                "content_checksum": 2,
                "source_run_ids": ["sis-team-run-context-tranche-2-v1"],
                "expected_source_run": "sis-team-run-context-tranche-2-v1",
                "source_hash_identities": {
                    column: [f"hash-{column}"] for column in SOURCE_HASH_COLUMNS},
            },
            "feature_columns": feature_contract(baseline, arm),
            "feature_contract_sha256": f"hash-{arm}",
            "target_seasons": validator.TARGET_SEASONS, "quantiles": [0.1],
            "context_max": 28000, "random_seed": 7, "n_estimators": 4,
            "device": "cuda", "output_rows": validator.EXPECTED_ROWS,
            "unique_keys": validator.EXPECTED_ROWS,
            "active_rb_coverage": [{"season": season, "support_rate": 0.9}
                                   for season in validator.TARGET_SEASONS],
            "folds": {str(season): {"target_rows": 100,
                                     "sampled_context_rows": 1000,
                                     "sampled_inactive_rows": 0}
                      for season in validator.TARGET_SEASONS},
        }
    control, treatment = report("control"), report("treatment")
    assert validator.validate_reports(
        control, treatment, "abcdef1", baseline)["passes"]
    treatment["active_rb_coverage"][2]["support_rate"] = 0.79
    assert not validator.validate_reports(
        control, treatment, "abcdef1", baseline)["passes"]


def test_cloud_path_is_write_once_and_gate_bound():
    cli = (ROOT / "src/nfl_dfs/cli.py").read_text(encoding="utf-8")
    launch = (ROOT / "scripts/cloud_tabpfn_sis_rb_rdef.sh").read_text(
        encoding="utf-8")
    finish = (ROOT / "scripts/cloud_finish_tabpfn_sis_rb_rdef.sh").read_text(
        encoding="utf-8")
    gate = (ROOT / "scripts/cloud_tabpfn_sis_rb_rdef_final_served.sh").read_text(
        encoding="utf-8")
    assert "tabpfn-sis-rb-rdef-final-served" in cli
    assert "WRITE_EMPTY" in (
        ROOT / "scripts/tabpfn_sis_qb_line/gen.py").read_text(encoding="utf-8")
    assert "selected_active_label.txt" in launch
    assert "TABPFN_SIS_RB_RDEF_JSON=" in finish
    assert "tabpfn-sis-rb-rdef-caches-valid" in gate
    assert "aggregate-active-rb-30-point-brier" in gate
