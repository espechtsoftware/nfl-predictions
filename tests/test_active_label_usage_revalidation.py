from pathlib import Path

import pandas as pd

from nfl_dfs.research import active_label_usage_revalidation as arm


def _lever_env(season: int, *, fitted: bool) -> str:
    common = {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": arm.CACHE_TABLE,
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": (
            "target_share_last,carry_share_last,snap_share_last,"
            "target_share_jump,carry_share_jump,snap_share_jump"),
        "ROLE_BELIEF_SEED": "7331",
        "REPLACEMENT_SLOTS": "12",
        "SERVED_POSITION_SCALES": arm.POSITION_SPECS[season],
    }
    if fitted:
        common.update({"GAME_SIM_USAGE": "dirichlet", "DIRICHLET_K": arm.FITTED_K})
    return ",".join(f"{key}={value}" for key, value in sorted(common.items()))


def test_mechanism_accepts_only_registered_usage_difference():
    control = pd.DataFrame({
        "season": list(arm.POSITION_SPECS),
        "code_sha": ["a12ab31"] * 3,
        "seeds": ["same"] * 3,
        "lever_env": [_lever_env(season, fitted=False) for season in arm.POSITION_SPECS],
    })
    treatment = control.copy()
    treatment["lever_env"] = [
        _lever_env(season, fitted=True) for season in arm.POSITION_SPECS]
    feature = {
        "left_rows": 10, "right_rows": 10, "left_only_rows": 0,
        "right_only_rows": 0, "mismatch_rows": 0,
        "max_numeric_abs_delta": 0.0,
        "ignored_numeric_fields": list(arm.DISTRIBUTION_DERIVED_FEATURES),
    }
    candidates = {
        "paired_slates": 54, "common_rows": 10,
        "left_only_rows": 1, "right_only_rows": 1,
        "common_actual_mismatch": 0, "common_sim_mean_mismatch": 0,
    }
    assert arm.mechanism_failures(
        control, treatment, feature, candidates,
        expected_code_sha="a12ab31") == []


def test_mechanism_rejects_extra_treatment_lever():
    control = pd.DataFrame({
        "season": list(arm.POSITION_SPECS), "code_sha": ["a12ab31"] * 3,
        "seeds": ["same"] * 3,
        "lever_env": [_lever_env(season, fitted=False) for season in arm.POSITION_SPECS],
    })
    treatment = control.copy()
    treatment["lever_env"] = [
        _lever_env(season, fitted=True) + ",UNREGISTERED=1"
        for season in arm.POSITION_SPECS]
    feature = {
        "left_rows": 10, "right_rows": 10, "left_only_rows": 0,
        "right_only_rows": 0, "mismatch_rows": 0,
        "max_numeric_abs_delta": 0.0,
        "ignored_numeric_fields": list(arm.DISTRIBUTION_DERIVED_FEATURES),
    }
    candidates = {
        "paired_slates": 54, "common_rows": 10,
        "left_only_rows": 1, "right_only_rows": 1,
        "common_actual_mismatch": 0, "common_sim_mean_mismatch": 0,
    }
    failures = arm.mechanism_failures(
        control, treatment, feature, candidates,
        expected_code_sha="a12ab31")
    assert any("beyond fitted usage" in failure for failure in failures)


def _score_rows(seasons, score=180.0):
    return pd.DataFrame([
        {
            "season": season, "week": week, "selected": True,
            "actual_score": score,
        }
        for season in seasons
        for week in range(1, 18 if season == 2019 else 19)
    ])


def test_cost_disclosure_groups_same_week_threshold_crossings():
    historical = _score_rows((2019, 2021, 2022, 2023, 2024, 2025))
    control = _score_rows((2023, 2024, 2025))
    treatment = control.copy()
    treatment.loc[
        treatment.season.eq(2023) & treatment.week.eq(3), "actual_score"
    ] = 245.0
    report = arm.comparison_report(historical, control, treatment)
    crossing = report["decision_cost_disclosure"]["threshold_crossings"][0]
    assert crossing["gained_thresholds"] == [240, 230, 220, 210, 200, 194, 187]
    assert report["decision"]["treatment_selected"]
    assert not report["decision"]["incumbent_retained_on_exact_tie"]


def test_exact_tie_retains_finite_k_incumbent():
    historical = _score_rows((2019, 2021, 2022, 2023, 2024, 2025))
    control = _score_rows((2023, 2024, 2025))
    report = arm.comparison_report(historical, control, control.copy())
    assert report["decision"]["comparison"] == 0
    assert report["decision"]["treatment_selected"]
    assert report["decision"]["incumbent_retained_on_exact_tie"]


def test_main_image_contains_registered_comparator():
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text(
        encoding="utf-8")
    assert "COPY scripts/compare_active_label_usage_revalidation.py " \
        "./scripts/compare_active_label_usage_revalidation.py" in dockerfile


def test_comparator_allows_only_within_season_config_identity():
    """The registered position schedule changes between evaluation seasons."""
    source = (Path(__file__).parents[1]
              / "scripts/compare_active_label_usage_revalidation.py").read_text(
                  encoding="utf-8")
    assert source.count("allow_season_config=True") == 2


def test_repaired_finisher_uses_new_v3_execution_identity():
    source = (Path(__file__).parents[1]
              / "scripts/cloud_finish_active_label_usage_revalidation.sh").read_text(
                  encoding="utf-8")
    assert "JOB=compare-active-label-usage-revalidation-v3" in source
    assert "comparison_execution_v3.txt" in source
    assert "comparison_execution_v2.txt" not in source
