import importlib.util
import base64
import json
from pathlib import Path
import zlib

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import tabpfn_sis_pass_tail_final_served as final_served
from nfl_dfs.backtest import replay
from nfl_dfs.research.tabpfn_sis_pass_tail import (
    SIS_PASS_TAIL_FEATURES,
    active_pass_tail_coverage,
    attach_sis_pass_tail,
    build_strict_prior_sis_pass_tail,
    feature_contract,
)


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_tabpfn_sis_pass_tail",
    ROOT / "scripts/validate_tabpfn_sis_pass_tail.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _source() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "season": 2025, "week": week, "team": team,
            "source_run_id": "sis-team-context-tranche-1-v1",
            "pdef_attempts": 20 + week,
            "pdef_value_attempts": 10 * week,
            "pdef_boom_rate": 0.1 * week,
            "pdef_bust_rate": 0.05 * week,
            "prush_combined_sacks": week,
            "prush_pressures": 2 * week,
        }
        for team in ("ARI", "ATL") for week in range(1, 5)
    ])


def test_contract_changes_only_frozen_three_columns():
    assert feature_contract(["z", "a"], "control") == ["a", "z"]
    assert feature_contract(["z", "a"], "treatment") == [
        "a", "z", *SIS_PASS_TAIL_FEATURES]
    with pytest.raises(ValueError, match="already contains"):
        feature_contract([SIS_PASS_TAIL_FEATURES[0]], "control")


def test_strict_prior_is_weighted_and_target_week_blind():
    source = _source()
    before = build_strict_prior_sis_pass_tail(source)
    source.loc[(source.team == "ARI") & source.week.eq(3),
               "pdef_boom_rate"] = 0.99
    after = build_strict_prior_sis_pass_tail(source)
    key = lambda frame: frame[(frame.team == "ARI") & frame.week.eq(3)].iloc[0]
    assert key(before).sis_pass_tail_source_week_end == 2
    assert key(before).sis_pass_tail_prior_games == 2
    assert key(before)[SIS_PASS_TAIL_FEATURES[0]] == pytest.approx(1 / 6)
    assert key(before)[SIS_PASS_TAIL_FEATURES[1]] == pytest.approx(1 / 12)
    assert key(before)[SIS_PASS_TAIL_FEATURES[2]] == pytest.approx(6 / 46)
    assert key(before)[SIS_PASS_TAIL_FEATURES[0]] == key(after)[
        SIS_PASS_TAIL_FEATURES[0]]


def test_attach_uses_opponent_and_exposes_only_qb_wr_te():
    features = build_strict_prior_sis_pass_tail(_source())
    panel = pd.DataFrame({
        "season": [2025] * 4, "week": [3] * 4,
        "opponent": ["ARI"] * 4,
        "position": ["QB", "RB", "WR", "TE"],
        "was_active": [True] * 4,
    })
    got = attach_sis_pass_tail(panel, features)
    assert len(got) == len(panel)
    assert got.loc[[0, 2, 3], list(SIS_PASS_TAIL_FEATURES)].notna().all().all()
    assert got.loc[1, list(SIS_PASS_TAIL_FEATURES)].isna().all()
    coverage = active_pass_tail_coverage(got)
    assert coverage[0]["rows"] == 3
    assert coverage[0]["support_rate"] == 1.0
    assert set(coverage[0]["by_position"]) == {"QB", "WR", "TE"}


def test_source_identity_duplicates_and_invalid_rates_fail_closed():
    wrong = _source()
    wrong["source_run_id"] = "another-run"
    with pytest.raises(ValueError, match="source-run"):
        build_strict_prior_sis_pass_tail(wrong)
    duplicate = pd.concat([_source(), _source().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="repeats team-week"):
        build_strict_prior_sis_pass_tail(duplicate)
    invalid = _source()
    invalid.loc[0, "pdef_boom_rate"] = 1.1
    with pytest.raises(ValueError, match="outside"):
        build_strict_prior_sis_pass_tail(invalid)


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
        "active_pass_tail_coverage": [
            {
                "season": season,
                "support_rate": 0.9,
                "by_position": {"QB": {}, "WR": {}, "TE": {}},
            }
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


def test_report_gate_requires_coverage_and_exact_bundle():
    baseline = ["z", "a"]
    control = _report("control", feature_contract(baseline, "control"))
    treatment = _report("treatment", feature_contract(baseline, "treatment"))
    assert validator.validate_reports(
        control, treatment, "abcdef1", baseline)["passes"]
    treatment["active_pass_tail_coverage"][2]["support_rate"] = 0.79
    result = validator.validate_reports(
        control, treatment, "abcdef1", baseline)
    assert not result["passes"]
    assert not result["checks"]["same_coverage_audits"]


def _served_folds() -> dict[int, tuple[pd.DataFrame, np.ndarray]]:
    folds = {}
    quantiles = np.linspace(-8.0, 8.0, 10_000)
    for season in (2022, 2023, 2024, 2025):
        rows = []
        draws = []
        for pos_index, position in enumerate(("QB", "RB", "WR", "TE")):
            for row_index in range(2):
                center = 12.0 + 4 * pos_index + row_index
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


def test_final_served_gate_reports_all_frozen_diagnostics(monkeypatch):
    monkeypatch.setattr(final_served, "EXPECTED_PASS_ROWS", {
        2023: 6, 2024: 6, 2025: 6,
    })
    control = _served_folds()
    treatment = {
        season: (frame.copy(), draws.copy())
        for season, (frame, draws) in control.items()
    }
    report = final_served.evaluate_pass_tail_arms(control, treatment)
    assert not report["gate"]["passes"]
    assert report["proper_score_ratios"][
        "equal_position_equal_quantile_mean_ratio"] == pytest.approx(1.0)
    assert set(report["control"]["positions"]) == {"QB", "WR", "TE"}
    assert "brier_25" in report["control"]["aggregate"]
    assert "reliability_gap_25" in report["control"]["aggregate"]
    assert "pinball_q99" in report["paired_loss_uncertainty"]


def test_cache_tables_are_research_licensed_and_context_restores(monkeypatch):
    monkeypatch.setenv("TABPFN_MARGINAL_TABLE", "outside")
    for table in final_served.TABLES.values():
        assert replay._tabpfn_marginal_table(
            {"TABPFN_MARGINAL_TABLE": table}) == table
        with final_served._cache_environment(table):
            assert replay._tabpfn_marginal_table() == table
        assert final_served.os.environ["TABPFN_MARGINAL_TABLE"] == "outside"


def test_large_report_is_chunked_and_round_trips_below_log_limit(monkeypatch):
    monkeypatch.setattr(final_served, "OUTPUT_CHUNK_SIZE", 100)
    report = {"rows": [{"value": index, "detail": f"row-{index:06d}"}
                       for index in range(200)]}
    lines = final_served.encoded_report_lines(report)
    assert len(lines) > 1
    assert max(map(len, lines)) < 100_000
    prefix = final_served.OUTPUT_CHUNK_PREFIX
    chunks = {}
    for line in lines:
        header, chunk = line.removeprefix(prefix).split(":", 1)
        index, total = map(int, header.split("/"))
        chunks[index] = chunk
    encoded = "".join(chunks[index] for index in range(1, total + 1))
    assert json.loads(zlib.decompress(base64.b64decode(encoded))) == report


def test_cloud_path_is_write_once_and_score_gate_is_separate():
    launch = (ROOT / "scripts/cloud_tabpfn_sis_pass_tail.sh").read_text()
    finish = (ROOT / "scripts/cloud_finish_tabpfn_sis_pass_tail.sh").read_text()
    served_launch = (
        ROOT / "scripts/cloud_tabpfn_sis_pass_tail_final_served.sh"
    ).read_text()
    served_retry = (
        ROOT / "scripts/cloud_retry_tabpfn_sis_pass_tail_final_served.sh"
    ).read_text()
    harvest_retry = (
        ROOT / "scripts/cloud_retry_tabpfn_sis_pass_tail_harvest.sh"
    ).read_text()
    served_finish = (
        ROOT / "scripts/cloud_finish_tabpfn_sis_pass_tail_final_served.sh"
    ).read_text()
    generator = (ROOT / "scripts/tabpfn_sis_qb_line/gen.py").read_text()
    assert "WRITE_EMPTY" in generator
    assert "TABPFN_SIS_PASS_TAIL_ARM" in generator
    assert "tabpfn-sis-pass-tail-caches-valid" in served_launch
    assert "equal-position-equal-q95-q99" in served_launch
    assert "executions.txt" in launch
    assert "TABPFN_SIS_PASS_TAIL_JSON=" in finish
    assert "execution_retry.txt" in served_retry
    assert "research_table_allowlist_omission" in served_retry
    assert "execution_retry.txt" in served_finish
    assert "execution_harvest_retry.txt" in served_finish
    assert "TABPFN_SIS_PASS_TAIL_FINAL_SERVED_CHUNK=" in served_finish
    assert "cloud_logging_text_entry_truncation" in harvest_retry
