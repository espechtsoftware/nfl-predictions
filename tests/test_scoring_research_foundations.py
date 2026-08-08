import numpy as np
import pandas as pd

from nfl_dfs.research.breakout_state import classify_breakout_state, conformal_labels
from nfl_dfs.research.decision_loss import realized_decision_regret, spo_plus_loss_and_gradient
from nfl_dfs.research.evidence_effect import LabeledEvent, fit_effect_model
from nfl_dfs.research.evidence_scenarios import apply_evidence_scenarios
from nfl_dfs.research.evidence_schema import ActiveAdjustment
from nfl_dfs.research.matched_controls import matched_report, nearest_matched_controls
from nfl_dfs.research.dst_tail import tail_metrics, walk_forward_probabilities
from nfl_dfs.models.featureset import active_training_rows


def test_breakout_state_and_conformal_group_are_point_in_time():
    row = {"position": "WR", "salary": 4300, "target_share_jump": 0.08,
           "snap_share_last": 0.75, "spread": 5, "implied_team_total": 20}
    state = classify_breakout_state(row)
    assert state == "fast_role_rise"
    labels = conformal_labels("WR", state)
    assert labels["position_archetype"] == "WR:fast_role_rise"


def test_matched_controls_compare_signal_to_same_slate_non_signal():
    frame = pd.DataFrame([
        {"season": 2025, "week": 1, "position": "WR", "signal": True,
         "salary": 4500, "implied_team_total": 21, "spread": 4,
         "snap_share_l4": .7, "target_share_l4": .2, "carry_share_l4": 0,
         "dk_points_l4": 10, "y_dk_points": 26},
        {"season": 2025, "week": 1, "position": "WR", "signal": False,
         "salary": 4600, "implied_team_total": 21, "spread": 3,
         "snap_share_l4": .69, "target_share_l4": .19, "carry_share_l4": 0,
         "dk_points_l4": 11, "y_dk_points": 12},
        {"season": 2025, "week": 1, "position": "WR", "signal": False,
         "salary": 8000, "implied_team_total": 28, "spread": -7,
         "snap_share_l4": .9, "target_share_l4": .35, "carry_share_l4": 0,
         "dk_points_l4": 23, "y_dk_points": 30},
    ])
    pairs = nearest_matched_controls(frame, "signal")
    assert len(pairs) == 1 and pairs.iloc[0].control_outcome == 12
    report = matched_report(pairs)
    assert report["mean_delta"] == 14 and report["tail_lift"] == 1


def test_evidence_scenarios_change_only_affected_component():
    model = fit_effect_model([
        LabeledEvent("promotion", "WR", "targets", 0.20),
        LabeledEvent("promotion", "WR", "targets", 0.25),
    ])
    adj = ActiveAdjustment(
        gsis_id="p1", component="targets", direction="opportunity_up",
        event_ids=("e1",), confidence=1.0, conflict=False,
        variance_inflation=1.0, event_types=("promotion",),
    )
    base = {"targets": np.full((2, 2000), 10.0),
            "carries": np.full((2, 2000), 5.0)}
    out, audit = apply_evidence_scenarios(
        base, ["p1", "p2"], {"p1": "WR", "p2": "RB"}, [adj], model, seed=3)
    assert out["targets"][0].mean() > 11
    np.testing.assert_array_equal(out["targets"][1], base["targets"][1])
    np.testing.assert_array_equal(out["carries"], base["carries"])
    assert len(audit) == 1


def test_spo_plus_exposes_lineup_decision_gradient():
    # Legal decisions: choose exactly one of three players.
    def optimize(values):
        out = np.zeros(3)
        out[int(np.argmax(values))] = 1
        return out

    actual = np.array([1.0, 10.0, 2.0])
    predicted = np.array([9.0, 1.0, 2.0])
    assert realized_decision_regret(predicted, actual, optimize) == 9.0
    loss, grad = spo_plus_loss_and_gradient(predicted, actual, optimize)
    assert loss > 0
    assert grad.shape == predicted.shape and not np.allclose(grad, 0)


def test_dst_tail_model_is_walk_forward():
    rng = np.random.default_rng(8)
    rows = []
    for season in (2021, 2022, 2023, 2024):
        for week in range(1, 15):
            implied = rng.uniform(16, 30)
            points = max(0, 25 - implied + rng.normal(0, 5))
            rows.append({
                "season": season, "week": week, "dst_dk_points": points,
                "implied_opponent_total": implied, "team_spread": implied - 23,
                "dst_points_l4": rng.uniform(3, 10), "dst_points_l16": 6,
                "sacks_l4": rng.uniform(1, 5), "takeaways_l4": rng.uniform(0, 3),
                "return_tds_l16": rng.uniform(0, .3),
                "opp_sack_rate_l4": rng.uniform(.02, .15),
                "opp_giveaway_rate_l4": rng.uniform(.01, .08),
            })
    scored = walk_forward_probabilities(pd.DataFrame(rows), threshold=8)
    assert set(scored.season.unique()) == {2023, 2024}
    assert scored.tail_probability.between(0, 1).all()
    assert tail_metrics(scored)["rows"] == len(scored)


def test_salary_inactive_rows_are_replayable_but_not_training_examples():
    frame = pd.DataFrame({"was_active": [True, False, None], "value": [1, 2, 3]})
    kept = active_training_rows(frame)
    assert kept.value.tolist() == [1]


def test_research_archetypes_and_matching_tolerate_nullable_metadata():
    nullable = {
        "position": "WR", "salary": 4000, "is_cold_start": pd.NA,
        "depth_rank_delta": pd.NA, "team_vacated_target_share": pd.NA,
        "team_vacated_carry_share": pd.NA, "target_share_jump": pd.NA,
        "carry_share_jump": pd.NA, "snap_share_jump": pd.NA,
        "snap_share_last": 0.75, "spread": 3.0,
        "implied_team_total": 20.0,
    }
    assert classify_breakout_state(nullable) == "secure_role_bad_environment"

    frame = pd.DataFrame([
        {"season": 2025, "week": 1, "position": "WR", "signal": pd.NA,
         "salary": 4000, "implied_team_total": 20, "spread": 3,
         "snap_share_l4": .7, "target_share_l4": .1, "carry_share_l4": 0,
         "dk_points_l4": 8, "y_dk_points": 5},
        {"season": 2025, "week": 1, "position": "WR", "signal": True,
         "salary": 4200, "implied_team_total": 20, "spread": 3,
         "snap_share_l4": .72, "target_share_l4": .15, "carry_share_l4": 0,
         "dk_points_l4": 9, "y_dk_points": 25},
    ])
    assert len(nearest_matched_controls(frame, "signal")) == 1
