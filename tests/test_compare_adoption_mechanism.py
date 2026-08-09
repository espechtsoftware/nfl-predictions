import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd


spec = importlib.util.spec_from_file_location(
    "compare_adoption_panel",
    Path(__file__).parents[1] / "scripts" / "compare_adoption_panel.py")
compare = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(compare)


def _features(model_only: bool) -> pd.DataFrame:
    return pd.DataFrame([
        {"season": 2025, "week": 1, "id": "qb", "pos": "QB",
         "proj": 10.0, "model_points_pre": 12.0, "market_points": 8.0,
         "mean_projection": 12.0 if model_only else 9.8},
        {"season": 2025, "week": 1, "id": "wr", "pos": "WR",
         "proj": 7.0, "model_points_pre": 7.0, "market_points": None,
         "mean_projection": 7.0},
        {"season": 2025, "week": 1, "id": "DST_X", "pos": "DST",
         "proj": 6.0, "model_points_pre": None, "market_points": None,
         "mean_projection": 6.0},
    ])


def _audit() -> dict:
    return {
        "candidate_rows": 1,
        "duplicate_feature_keys": 0,
        "missing_roster_players": 0,
        "max_abs_error": 1e-5,
    }


def _reproduction() -> dict:
    return {
        "slates": 1,
        "source_rows": 1,
        "treatment_rows": 1,
        "missing_rows": 0,
        "roster_mismatch": 0,
        "selected_mismatch": 0,
        "actual_max_delta": 0.0,
        "sim_mean_max_delta": 0.0,
        "p_line_max_delta": 0.0,
    }


def _ensemble_features(size: int) -> pd.DataFrame:
    specs = compare.ensemble_member_specs({"MODEL_ENSEMBLE": str(size)})
    spec_json = json.dumps(specs, separators=(",", ":"), sort_keys=True)
    if size == 3:
        member_rows = [(10.0, 11.0, 12.0), (7.0, 8.0, 9.0)]
        model_means = [11.0, 8.0]
    else:
        member_rows = [(9.5, None, None), (7.5, None, None)]
        model_means = [9.5, 7.5]
    rows = []
    for player_id, position, salary, actual, market, members, model_mean in (
            ("qb", "QB", 7000, 20.0, 10.0, member_rows[0], model_means[0]),
            ("wr", "WR", 6000, 15.0, None, member_rows[1], model_means[1])):
        rows.append({
            "season": 2025, "week": 1, "id": player_id,
            "pos": position, "salary": salary, "actual": actual,
            "proj": model_mean, "market_points": market,
            "model_points_pre": model_mean,
            "mean_projection": (
                0.45 * model_mean + 0.55 * market
                if market is not None else model_mean),
            "model_ensemble_size": size,
            "model_member_spec": spec_json,
            "ensemble_point_0": members[0],
            "ensemble_point_1": members[1],
            "ensemble_point_2": members[2],
        })
    return pd.DataFrame(rows)


def _ensemble_seeds(size: int, other: str = "CE_SEED=1701") -> str:
    specs = compare.ensemble_member_specs({"MODEL_ENSEMBLE": str(size)})
    spec_json = json.dumps(specs, separators=(",", ":"), sort_keys=True)
    return f"{other};MODEL_ENSEMBLE_SIZE={size};MODEL_MEMBER_SPEC={spec_json}"


def _salary_candidates(deleted: bool) -> pd.DataFrame:
    salaries = [49_000, 49_400] if not deleted else [48_700, 49_400]
    return pd.DataFrame([
        {"season": 2025, "week": 1, "cand_ix": i,
         "players": f"p{i}", "selected": True, "actual_score": 180 + i,
         "sim_mean": 170 + i, "salary": salary,
         "lever_env": ("GAME_SIM_MODE=possession,MIN_LINEUP_SALARY=0"
                       if deleted else "GAME_SIM_MODE=possession")}
        for i, salary in enumerate(salaries)
    ])


def _member_world_candidates(active: bool) -> pd.DataFrame:
    return pd.DataFrame([{
        "lever_env": ("GAME_SIM_MODE=possession,"
                      "ENSEMBLE_WORLD_MODE=member_sample"
                      if active else "GAME_SIM_MODE=possession"),
        "seeds": (_ensemble_seeds(3) + ";ENSEMBLE_WORLD_SEED=8161"
                  if active else _ensemble_seeds(3)),
    }])


def _member_world_pair_report() -> dict:
    return {
        "source_rows": 10,
        "treatment_rows": 10,
        "missing_rows": 0,
        "roster_mismatch": 4,
        "support_mismatch": 8,
        "p_line_mismatch": 8,
        "sim_mean_mismatch": 0,
        "same_roster_actual_mismatch": 0,
        "selected_shared": 7,
        "selected_source_only": 3,
        "selected_treatment_only": 3,
    }


def _candidate_budget_candidates(multiple: int) -> pd.DataFrame:
    lever = "GAME_SIM_MODE=possession,N_BOOM=40,N_CE=0"
    if multiple != 2:
        lever = f"CAND_MULT={multiple}," + lever
    return pd.DataFrame([{
        "lever_env": lever,
        "seeds": _ensemble_seeds(3),
    }])


def _candidate_budget_pair_report() -> dict:
    return {
        "source_rows": 10,
        "treatment_rows": 15,
        "common_rows": 10,
        "source_only_rows": 0,
        "treatment_only_rows": 5,
        "treatment_only_lev_rows": 5,
        "treatment_only_nonlev_rows": 0,
        "common_actual_mismatch": 0,
        "common_p_line_mismatch": 0,
        "common_sim_mean_mismatch": 0,
        "common_support_mismatch": 0,
        "selected_shared": 7,
        "selected_source_only": 3,
        "selected_treatment_only": 3,
        "slates_with_more_candidates": 107,
        "min_extra_candidates_per_slate": 3,
        "max_extra_candidates_per_slate": 7,
    }


def test_blend_mechanism_proves_only_weight_changed():
    report, failures = compare._blend_mechanism(
        _features(False), _features(True), _audit(), _audit(),
        _reproduction())
    assert failures == []
    assert report["covered_player_weeks"] == 1
    assert report["market_input_mismatch_rows"] == 0
    assert report["post_shaping_model_max_abs_delta"] == 0.0
    assert abs(report["covered_mean_abs_ablation_delta"] - 2.2) < 1e-9


def test_blend_mechanism_rejects_changed_market_input():
    treatment = _features(True)
    treatment.loc[treatment.id.eq("qb"), "market_points"] = 8.5
    _, failures = compare._blend_mechanism(
        _features(False), treatment, _audit(), _audit(), _reproduction())
    assert "source/treatment market inputs differ" in failures


def test_blend_mechanism_rejects_no_market_control_drift():
    reproduction = _reproduction()
    reproduction["roster_mismatch"] = 1
    _, failures = compare._blend_mechanism(
        _features(False), _features(True), _audit(), _audit(), reproduction)
    assert "no-market slates do not reproduce the control exactly" in failures


def test_ensemble_mechanism_proves_member_ablation_fired():
    report, failures = compare._ensemble_mechanism(
        _ensemble_features(3), _ensemble_features(1), _audit(), _audit(),
        _ensemble_seeds(3), _ensemble_seeds(1))
    assert failures == []
    assert report["source_ensemble_size"] == 3
    assert report["treatment_ensemble_size"] == 1
    assert report["source_rows_with_member_disagreement"] == 2
    assert report["non_ensemble_seeds_match"] is True
    assert report["unchanged_input_mismatch_rows"] == {
        "pos": 0, "salary": 0, "actual": 0, "market_points": 0}


def test_ensemble_mechanism_allows_shaped_mean_invariance():
    """TabPFN marginals fix each player distribution while K changes copula."""
    source = _ensemble_features(3)
    treatment = _ensemble_features(1)
    treatment["model_points_pre"] = source.model_points_pre
    treatment["mean_projection"] = np.where(
        treatment.market_points.notna(),
        0.45 * treatment.model_points_pre + 0.55 * treatment.market_points,
        treatment.model_points_pre)
    report, failures = compare._ensemble_mechanism(
        source, treatment, _audit(), _audit(),
        _ensemble_seeds(3), _ensemble_seeds(1))
    assert failures == []
    assert report["k1_vs_k3_mean_abs_delta"] > 0
    assert report["post_shaping_model_mean_abs_delta"] == 0.0
    assert report["post_shaping_model_mean_changed_rows"] == 0


def test_ensemble_mechanism_rejects_missing_member_prediction():
    source = _ensemble_features(3)
    source.loc[source.id.eq("qb"), "ensemble_point_2"] = None
    _, failures = compare._ensemble_mechanism(
        source, _ensemble_features(1), _audit(), _audit(),
        _ensemble_seeds(3), _ensemble_seeds(1))
    assert "source offense is missing one or more K=3 predictions" in failures


def test_ensemble_mechanism_rejects_wrong_member_identity():
    treatment = _ensemble_features(1)
    treatment["model_ensemble_size"] = 2
    _, failures = compare._ensemble_mechanism(
        _ensemble_features(3), treatment, _audit(), _audit(),
        _ensemble_seeds(3), _ensemble_seeds(1))
    assert "treatment feature snapshot does not uniformly record K=1" in failures


def test_ensemble_mechanism_rejects_unrelated_seed_drift():
    _, failures = compare._ensemble_mechanism(
        _ensemble_features(3), _ensemble_features(1), _audit(), _audit(),
        _ensemble_seeds(3), _ensemble_seeds(1, other="CE_SEED=1702"))
    assert "source and treatment non-ensemble seeds differ" in failures


def test_member_world_mechanism_proves_joint_only_change():
    report, failures = compare._member_world_mechanism(
        _member_world_candidates(False), _member_world_candidates(True),
        _ensemble_features(3), _ensemble_features(3),
        _audit(), _audit(), _member_world_pair_report())
    assert failures == []
    assert report["source_mode"] == ""
    assert report["treatment_mode"] == "member_sample"
    assert report["treatment_member_world_seed"] == "8161"
    assert report["non_member_world_seeds_match"] is True
    assert not any(report["invariant_feature_mismatch_rows"].values())


def test_member_world_mechanism_rejects_marginal_or_seed_drift():
    treatment_features = _ensemble_features(3)
    treatment_features.loc[0, "mean_projection"] += 0.1
    treatment_candidates = _member_world_candidates(True)
    treatment_candidates.loc[0, "seeds"] = (
        _ensemble_seeds(3, other="CE_SEED=1702")
        + ";ENSEMBLE_WORLD_SEED=8161")
    _, failures = compare._member_world_mechanism(
        _member_world_candidates(False), treatment_candidates,
        _ensemble_features(3), treatment_features,
        _audit(), _audit(), _member_world_pair_report())
    assert "source/treatment non-member-world seeds differ" in failures
    assert "source/treatment mean_projection feature rows differ" in failures


def test_candidate_budget_mechanism_proves_strict_superset():
    report, failures = compare._candidate_budget_mechanism(
        _candidate_budget_candidates(2), _candidate_budget_candidates(4),
        _ensemble_features(3), _ensemble_features(3),
        _audit(), _audit(), _candidate_budget_pair_report())
    assert failures == []
    assert report["source_candidate_multiple"] == 2
    assert report["treatment_candidate_multiple"] == 4
    assert report["other_levers_match"] is True
    assert report["candidate_superset"]["treatment_only_rows"] == 5


def test_candidate_budget_mechanism_rejects_drift_or_inert_pool():
    treatment = _candidate_budget_candidates(4)
    treatment.loc[0, "lever_env"] += ",N_BOOM=41"
    pair = _candidate_budget_pair_report()
    pair["source_only_rows"] = 1
    pair["selected_treatment_only"] = 0
    _, failures = compare._candidate_budget_mechanism(
        _candidate_budget_candidates(2), treatment,
        _ensemble_features(3), _ensemble_features(3),
        _audit(), _audit(), pair)
    assert "candidate-budget arm changes other replay levers" in failures
    assert "larger candidate request is not a source superset" in failures
    assert "CAND_MULT=4 did not add any selected rosters" in failures


def test_primary_high_tail_disposition_precedes_legacy_gate():
    assert compare._disposition(
        [], {"passes": True}, {"passes": False}, {"passes": False}
    ) == "high-tail-improves"
    assert compare._disposition(
        ["bad mechanism"], {"passes": True}, {"passes": True},
        {"passes": True}) == "invalid"


def test_tail_first_disposition_is_separate_from_frozen_disposition():
    assert compare._tail_first_disposition(
        [], {"passes": True}) == "tail-first-improves"
    assert compare._tail_first_disposition(
        [], {"passes": False}) == "tail-first-not-supported"
    assert compare._tail_first_disposition(
        ["bad mechanism"], {"passes": True}) == "invalid"


def test_salary_floor_mechanism_proves_deletion_fired():
    report, failures = compare._salary_floor_mechanism(
        _salary_candidates(False), _salary_candidates(True),
        _features(False), _features(False))
    assert failures == []
    assert report["source_floor"] == 49_000
    assert report["treatment_floor"] == 0
    assert report["source_salary"]["below_49000_rows"] == 0
    assert report["treatment_salary"]["below_49000_rows"] == 1


def test_salary_floor_mechanism_rejects_inert_deletion():
    treatment = _salary_candidates(True)
    treatment["salary"] = [49_000, 49_400]
    _, failures = compare._salary_floor_mechanism(
        _salary_candidates(False), treatment,
        _features(False), _features(False))
    assert "salary-floor deletion generated no sub-$49k candidates" in failures


def test_salary_floor_mechanism_rejects_feature_drift():
    treatment_features = _features(False)
    treatment_features.loc[treatment_features.id.eq("qb"), "proj"] += 0.1
    _, failures = compare._salary_floor_mechanism(
        _salary_candidates(False), _salary_candidates(True),
        _features(False), treatment_features)
    assert "source/treatment proj features differ" in failures


def test_panel_validation_accepts_explicit_entry_count():
    rows = []
    for week in range(1, 108):
        for ix in range(80):
            rows.append({
                "season": 2025, "week": week, "selected": True,
                "actual_score": 150.0 + ix, "code_sha": "a",
                "config_hash": "b", "lever_env": "c", "seeds": "d",
            })
    panel = pd.DataFrame(rows)
    assert compare._validate_panel("panel", panel, 80) == []
    assert any("exactly 40" in failure
               for failure in compare._validate_panel("panel", panel, 40))
