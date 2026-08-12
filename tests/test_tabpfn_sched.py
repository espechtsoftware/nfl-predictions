import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.analysis import tabpfn_sched_final_served as final_served
from nfl_dfs.backtest import replay
from nfl_dfs.research import tabpfn_sched_lineup_v1 as sched_lineup


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_tabpfn_sched", ROOT / "scripts/validate_tabpfn_sched.py")
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _report(arm: str, features: list[str], *, label_law: str = "active_only"):
    active_only = label_law == "active_only"
    folds = {
        str(season): {
            "target_rows": 100,
            "sampled_context_rows": 1000,
            "sampled_inactive_rows": 0 if active_only else 10,
        }
        for season in validator.TARGET_SEASONS
    }
    return {
        "arm": arm,
        "label_law": label_law,
        "active_context_only": active_only,
        "code_sha": "abcdef1",
        "output_table": (
            "p.nfl_features.tabpfn_sched_control_v1"
            if arm == "control"
            else "p.nfl_features.tabpfn_sched_treatment_v1"
        ),
        "training_source": {"content_checksum": 123},
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
        "folds": folds,
        "inherited_rng_warmup": (
            {} if active_only else {
                "2019": {"eligible_context_rows": 1, "sampled_context_rows": 1},
                "2021": {"eligible_context_rows": 2, "sampled_context_rows": 2},
            }
        ),
    }


def test_sched_report_gate_accepts_only_appended_pair_and_common_label_law():
    control, treatment = validator.expected_features(
        ROOT / "scripts/tabpfn_sched/features_control.txt")
    result = validator.validate_reports(
        _report("control", control), _report("treatment", treatment),
        "abcdef1", "active_only", control, treatment)
    assert result["passes"]
    broken = _report("treatment", [*control, "body_clock_hour"])
    result = validator.validate_reports(
        _report("control", control), broken, "abcdef1", "active_only",
        control, treatment)
    assert not result["passes"]
    assert not result["checks"]["exact_feature_contracts"]


def test_sched_table_gate_requires_changed_predictions(monkeypatch):
    monkeypatch.setattr(validator, "EXPECTED_ROWS", 4)
    common = {
        "season": [2022, 2023, 2024, 2025], "week": [1, 1, 1, 1],
        "gsis_id": ["a", "b", "c", "d"],
        "label_law": ["current"] * 4,
        "active_context_only": [False] * 4,
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
    result = validator.validate_tables(left, right)
    assert result["passes"]
    reproduction = validator.validate_control_reproduction(left, left.copy())
    assert reproduction["passes"]
    inherited = left.copy()
    inherited.loc[0, "q90"] += 0.01
    reproduction = validator.validate_control_reproduction(left, inherited)
    assert not reproduction["passes"]


def test_sched_launch_is_terminal_active_label_dependent_and_write_once():
    launch = (ROOT / "scripts/cloud_tabpfn_sched.sh").read_text(
        encoding="utf-8")
    finish = (ROOT / "scripts/cloud_finish_tabpfn_sched.sh").read_text(
        encoding="utf-8")
    generator = (ROOT / "scripts/tabpfn_sched/gen.py").read_text(
        encoding="utf-8")
    old = (ROOT / "scripts/tabpfn_gen/features.txt").read_text(
        encoding="utf-8").split()
    control = (ROOT / "scripts/tabpfn_sched/features_control.txt").read_text(
        encoding="utf-8").split()
    assert old == control
    assert "selected_active_label.txt" in launch
    assert "inherited_cache_table" in launch
    assert "active-only)" in launch and "LABEL_LAW=active_only" in launch
    assert "WRITE_EMPTY" in generator
    assert "_advance_inherited_rng(panel, rng)" in generator
    assert "CANONICAL_WARMUP_SEASONS = (2019, 2021)" in generator
    assert 'SCHED_FEATURES = ("net_rest_diff", "body_clock_hour")' in generator
    assert "TABPFN_SCHED_JSON=" in finish
    assert "validate_tabpfn_sched.py" in finish
    assert "--inherited-table" in finish


def test_sched_final_served_requires_terminal_usage_and_licensed_caches(
    monkeypatch,
):
    monkeypatch.setenv("TABPFN_ACCEPTED_USAGE_LAW", "multinomial")
    monkeypatch.delenv("TABPFN_ACCEPTED_DIRICHLET_K", raising=False)
    monkeypatch.delenv("GAME_SIM_USAGE", raising=False)
    monkeypatch.delenv("DIRICHLET_K", raising=False)
    assert final_served.accepted_usage_law()["mode"] == \
        "production-multinomial"
    monkeypatch.setenv("TABPFN_ACCEPTED_USAGE_LAW", "dirichlet")
    monkeypatch.setenv("TABPFN_ACCEPTED_DIRICHLET_K", "31.25")
    monkeypatch.setenv("GAME_SIM_USAGE", "dirichlet")
    monkeypatch.setenv("DIRICHLET_K", "31.25")
    assert final_served.accepted_usage_law()["k"] == "31.25"
    monkeypatch.setenv("DIRICHLET_K", "31.26")
    with pytest.raises(ValueError, match="differs from accepted fitted K"):
        final_served.accepted_usage_law()
    for table in final_served.TABLES.values():
        assert replay._tabpfn_marginal_table(
            {"TABPFN_MARGINAL_TABLE": table}) == table


def test_sched_final_served_cloud_path_is_async_and_harvested():
    cli = (ROOT / "src/nfl_dfs/cli.py").read_text(encoding="utf-8")
    launch = (ROOT / "scripts/cloud_tabpfn_sched_final_served.sh").read_text(
        encoding="utf-8")
    finish = (
        ROOT / "scripts/cloud_finish_tabpfn_sched_final_served.sh"
    ).read_text(encoding="utf-8")
    assert "tabpfn-sched-final-served" in cli
    assert "selected_tier1.txt" in launch
    assert "selected_usage.txt" in launch
    assert "selected_active_label.txt" in launch
    assert "tabpfn-sched-caches-valid" in launch
    assert "TABPFN_SCHED_FINAL_SERVED_JSON=" in finish
    assert "TABPFN_SCHED_FINAL_SERVED_COMPLETE" in finish


def _sched_rows(table: str, schedules: dict[int, str]) -> pd.DataFrame:
    rows = []
    for season in (2023, 2024, 2025):
        values = {
            "GAME_SIM_MODE": "possession", "MODEL_ENSEMBLE": "1",
            "N_CE": "0", "N_EPISTEMIC": "12", "N_GUMBEL": "0",
            "N_BOOM": "40", "EPISTEMIC_FAMILY": "role_draws",
            "ROLE_BELIEF_FEATURES": (
                "target_share_last,carry_share_last,snap_share_last,"
                "target_share_jump,carry_share_jump,snap_share_jump"
            ),
            "ROLE_BELIEF_SEED": "7331", "REPLACEMENT_SLOTS": "12",
            "TABPFN_MARGINAL_TABLE": table,
            "SERVED_POSITION_SCALES": schedules[season],
        }
        rows.append({
            "season": season, "code_sha": "abcdef1", "seeds": "fixed",
            "lever_env": ",".join(f"{key}={value}" for key, value in values.items()),
        })
    return pd.DataFrame(rows)


def test_sched_exact80_mechanism_allows_only_cache_and_schedule_pair():
    control_schedules = {
        season: "QB:0.99,RB:1.0,TE:0.95,WR:1.05"
        for season in (2023, 2024, 2025)
    }
    treatment_schedules = {
        season: "QB:0.98,RB:1.01,TE:0.96,WR:1.04"
        for season in (2023, 2024, 2025)
    }
    features = {
        "left_rows": 10, "right_rows": 10, "left_only_rows": 0,
        "right_only_rows": 0, "mismatch_rows": 0,
        "max_numeric_abs_delta": 0.0,
        "ignored_numeric_fields": list(sched_lineup.DISTRIBUTION_DERIVED_FEATURES),
    }
    candidates = {
        "paired_slates": 54, "common_rows": 10, "left_only_rows": 1,
        "right_only_rows": 1, "common_actual_mismatch": 0,
        "common_sim_mean_mismatch": 0,
    }
    failures = sched_lineup.mechanism_failures(
        _sched_rows(sched_lineup.CONTROL_TABLE, control_schedules),
        _sched_rows(sched_lineup.TREATMENT_TABLE, treatment_schedules),
        features, candidates, expected_code_sha="abcdef1",
        role_selected=True, allocation="multinomial", selected_k="infinity",
        control_schedules=control_schedules,
        treatment_schedules=treatment_schedules,
    )
    assert failures == []


def test_sched_exact80_has_frozen_launch_finish_and_fallback_paths():
    protocol = (
        ROOT / "reports/2026-08-12-pit-clean-tabpfn-sched-exact80.md"
    ).read_text(encoding="utf-8")
    launch = (
        ROOT / "scripts/prop_lock_tabpfn_sched_exact80_v1.sh"
    ).read_text(encoding="utf-8")
    finish = (
        ROOT / "scripts/cloud_finish_tabpfn_sched_exact80_v1.sh"
    ).read_text(encoding="utf-8")
    fallback = (
        ROOT / "scripts/resolve_tabpfn_sched_fallback_v1.sh"
    ).read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "240,230,220,210,200,194,187" in protocol
    assert "20260812-sched-generation-v1/image.txt" in launch
    assert "control_reproduction" in launch
    assert "code_sha='a12ab31'" in launch
    assert "TABPFN_SCHED_STAGE_B_V1_JSON=" in finish
    assert "selected_sched.txt" in finish
    assert "final-served-gate-failed" in fallback
    assert "COPY scripts/compare_tabpfn_sched_lineup_v1.py " \
        "./scripts/compare_tabpfn_sched_lineup_v1.py" in dockerfile
