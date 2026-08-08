import importlib.util
import json
from pathlib import Path

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
