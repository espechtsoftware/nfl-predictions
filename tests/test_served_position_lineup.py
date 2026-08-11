from pathlib import Path

import pandas as pd

from nfl_dfs.research import served_position_lineup as lineup


def _provenance(scale: str | None, code: str) -> pd.DataFrame:
    values = {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": lineup.ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331",
        "REPLACEMENT_SLOTS": "12",
    }
    if scale is not None:
        values["SERVED_POSITION_SCALES"] = scale
    return pd.DataFrame([{
        "code_sha": code,
        "config_hash": f"config-{code}-{scale}",
        "seeds": "same-seeds",
        "lever_env": ",".join(
            f"{key}={value}" for key, value in sorted(values.items())),
    }])


def _clean_features() -> dict:
    return {
        "left_rows": 100,
        "right_rows": 100,
        "left_only_rows": 0,
        "right_only_rows": 0,
        "mismatch_rows": 0,
        "max_numeric_abs_delta": 0.0,
    }


def _clean_candidates() -> dict:
    return {
        "paired_slates": 54,
        "common_rows": 100,
        "left_only_rows": 0,
        "right_only_rows": 0,
        "common_actual_mismatch": 0,
        "common_sim_mean_mismatch": 0,
    }


def test_mechanism_accepts_exact_factors_as_only_treatment_change():
    source = _provenance(None, lineup.SOURCE_CODE_SHA)
    control = _provenance("identity", "new")
    treatment = _provenance(lineup.POSITION_SPEC, "new")
    assert lineup.mechanism_failures(
        source, control, treatment,
        _clean_features(), _clean_features(),
        _clean_candidates(), _clean_candidates(),
        {"paired_slates": 54, "weekly_max_mismatches": 0},
        experiment_code_sha="new",
    ) == []


def test_comparator_is_packaged_in_cloud_run_image():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "COPY scripts/compare_served_position_lineup.py " \
        "./scripts/compare_served_position_lineup.py" in dockerfile


def test_mechanism_allows_treatment_candidate_pool_to_change():
    source = _provenance(None, lineup.SOURCE_CODE_SHA)
    control = _provenance("identity", "new")
    treatment = _provenance(lineup.POSITION_SPEC, "new")
    treatment_candidates = _clean_candidates()
    treatment_candidates.update({"left_only_rows": 20, "right_only_rows": 30})
    assert lineup.mechanism_failures(
        source, control, treatment,
        _clean_features(), _clean_features(),
        _clean_candidates(), treatment_candidates,
        {"paired_slates": 54, "weekly_max_mismatches": 0},
        experiment_code_sha="new",
    ) == []


def test_mechanism_rejects_wrong_factor_or_failed_control_reproduction():
    source = _provenance(None, lineup.SOURCE_CODE_SHA)
    control = _provenance("identity", "new")
    treatment = _provenance(
        "QB:0.970,RB:1.005,TE:0.940,WR:1.065", "new")
    failures = lineup.mechanism_failures(
        source, control, treatment,
        _clean_features(), _clean_features(),
        _clean_candidates(), _clean_candidates(),
        {"paired_slates": 54, "weekly_max_mismatches": 1},
        experiment_code_sha="new",
    )
    assert "treatment served-position factors differ from frozen fit" in failures
    assert "same-image control does not reproduce source weekly maxima" in failures


def test_tail_first_decision_uses_200_after_higher_threshold_ties():
    control = {
        "clear_240": 2, "clear_230": 3, "clear_220": 5,
        "clear_210": 7, "clear_200": 11,
    }
    treatment = dict(control, clear_200=12)
    decision = lineup.tail_first_decision(control, treatment)
    assert decision["passes"]
    assert decision["first_difference"] == 200
    losing = dict(treatment, clear_230=2, clear_200=20)
    decision = lineup.tail_first_decision(control, losing)
    assert decision["fails"]
    assert decision["first_difference"] == 230


def test_comparison_keeps_historical_books_unchanged():
    source_rows = []
    for season, week in sorted(lineup.expected_slate_pairs(
            lineup.SOURCE_SEASONS)):
        source_rows.append({
            "season": season, "week": week, "selected": True,
            "actual_score": 180.0,
        })
    control_rows = []
    treatment_rows = []
    for season, week in sorted(lineup.expected_slate_pairs(
            lineup.EVALUATION_SEASONS)):
        base = {
            "season": season, "week": week, "selected": True,
            "actual_score": 180.0,
        }
        control_rows.append(base)
        treatment_rows.append({
            **base,
            "actual_score": 205.0 if (season, week) == (2025, 18) else 180.0,
        })
    report = lineup.comparison_report(
        pd.DataFrame(source_rows),
        pd.DataFrame(control_rows),
        pd.DataFrame(treatment_rows),
    )
    assert report["tail_first_decision"]["passes"]
    assert report["tail_first_decision"]["first_difference"] == 200
    for row in report["season_metrics"]:
        if row["season"] in lineup.HISTORICAL_SEASONS:
            assert row["control_mean_best"] == row["treatment_mean_best"]
