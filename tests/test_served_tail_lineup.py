import pandas as pd

from nfl_dfs.research import served_tail_lineup as lineup


def _provenance(scale: str | None = None, code: str = "new") -> pd.DataFrame:
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
        values["SERVED_TAIL_SCALE"] = scale
    lever = ",".join(f"{key}={value}" for key, value in sorted(values.items()))
    return pd.DataFrame([{
        "code_sha": code,
        "config_hash": f"cfg-{code}",
        "seeds": "ROLE_BELIEF_SEED=7331",
        "lever_env": lever,
    }])


def test_stage_b_mechanism_accepts_only_scale_change():
    source = _provenance(code=lineup.SOURCE_CODE_SHA)
    treatment = _provenance("1.025")
    features = {
        "source_rows": 100, "treatment_rows": 100,
        "source_only_rows": 0, "treatment_only_rows": 0,
        "mismatch_rows": 0, "max_numeric_abs_delta": 0.0,
    }
    candidates = {
        "paired_slates": 54, "common_rows": 50,
        "common_actual_mismatch": 0, "common_sim_mean_mismatch": 0,
    }
    assert lineup.mechanism_failures(
        source, treatment, features, candidates,
        treatment_code_sha="new") == []


def test_stage_b_mechanism_rejects_wrong_factor_and_unrelated_change():
    source = _provenance(code=lineup.SOURCE_CODE_SHA)
    treatment = _provenance("1.020")
    treatment.loc[0, "lever_env"] += ",Q99_WILD=1"
    failures = lineup.mechanism_failures(
        source, treatment,
        {"source_rows": 1, "treatment_rows": 1},
        {"paired_slates": 54, "common_rows": 1},
        treatment_code_sha="new")
    assert "treatment served-tail scale is not 1.025" in failures
    assert "treatment changes replay levers other than served-tail scale" in failures


def test_lineup_decision_requires_nonworse_high_thresholds():
    source = {
        "clear_240": 2, "clear_230": 3, "clear_220": 5, "clear_210": 7,
    }
    clean = {
        "clear_240": 2, "clear_230": 4, "clear_220": 5, "clear_210": 8,
    }
    assert lineup.lineup_decision(source, clean)["passes"]
    mixed = dict(clean, clear_220=4)
    result = lineup.lineup_decision(source, mixed)
    assert not result["passes"]
    assert result["operator_review_required"]


def test_expected_stage_b_slate_counts():
    assert len(lineup.expected_slate_pairs(lineup.EVALUATION_SEASONS)) == 54
    assert len(lineup.expected_slate_pairs(lineup.SOURCE_SEASONS)) == 107


def test_comparison_keeps_pre_evaluation_books_unchanged():
    source_rows = []
    for season, week in sorted(lineup.expected_slate_pairs(
            lineup.SOURCE_SEASONS)):
        source_rows.append({
            "season": season, "week": week, "selected": True,
            "actual_score": 180.0,
        })
    treatment_rows = []
    for season, week in sorted(lineup.expected_slate_pairs(
            lineup.EVALUATION_SEASONS)):
        treatment_rows.append({
            "season": season, "week": week, "selected": True,
            "actual_score": 245.0 if (season, week) == (2025, 18) else 180.0,
        })
    report = lineup.comparison_report(
        pd.DataFrame(source_rows), pd.DataFrame(treatment_rows))
    assert report["source_metrics"]["clear_240"] == 0
    assert report["combined_treatment_metrics"]["clear_240"] == 1
    assert report["tail_first_decision"]["passes"]
    for row in report["season_metrics"]:
        if row["season"] in lineup.HISTORICAL_SEASONS:
            assert row["source_mean_best"] == row["treatment_mean_best"]
