import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.latent_role_state import (
    MODEL_FEATURES,
    STATES,
    TRANSITION_SOURCE_SQL,
    LatentRoleStateError,
    add_previous_state,
    classify_realized_states,
    empirical_transition_probabilities,
    expanding_role_audit,
    fit_role_transition,
    multiclass_scores,
    prepare_transition_frame,
)


def test_frozen_role_state_boundaries_and_unavailable_snap():
    rows = pd.DataFrame({
        "position": ["WR", "WR", "TE", "RB", "RB", "WR", "RB"],
        "was_active": [False, True, True, True, True, True, True],
        "snap_share": [np.nan, 0.20, 0.70, 0.70, 0.70, np.nan, 0.50],
        "target_share": [np.nan, 0.07, 0.14, 0.10, 0.10, 0.30, np.nan],
        "carry_share": [np.nan, 0.00, 0.00, 0.20, 0.30, 0.00, np.nan],
    })
    out = classify_realized_states(rows)
    assert out.iloc[:5].tolist() == [
        "inactive", "dormant", "rotation", "secondary", "primary",
    ]
    assert pd.isna(out.iloc[5])
    assert pd.isna(out.iloc[6])


def test_role_state_rejects_unregistered_positions():
    rows = pd.DataFrame({
        "position": ["QB"], "was_active": [True], "snap_share": [1.0],
        "target_share": [0.0], "carry_share": [0.0],
    })
    with pytest.raises(LatentRoleStateError, match="unsupported"):
        classify_realized_states(rows)


def test_previous_state_is_strict_prior_within_player_season():
    rows = pd.DataFrame({
        "gsis_id": ["a", "a", "a", "a"],
        "season": [2026, 2025, 2025, 2025],
        "week": [1, 3, 1, 2],
        "realized_state": ["primary", "secondary", "dormant", "rotation"],
    })
    out = add_previous_state(rows).sort_values(["season", "week"])
    assert out.previous_state.tolist() == [
        "unknown", "dormant", "rotation", "unknown",
    ]


def _transition_rows(n_per_state: int = 8) -> pd.DataFrame:
    rows = []
    for state_index, state in enumerate(STATES):
        for repeat in range(n_per_state):
            level = state_index / (len(STATES) - 1)
            rows.append({
                "position": ("RB", "WR", "TE")[repeat % 3],
                "previous_state": STATES[(state_index + repeat) % len(STATES)],
                "injury_status": None if repeat == 0 else "Questionable",
                "target_share_last": level * 0.30,
                "target_share_l4": level * 0.25,
                "carry_share_last": level * 0.35,
                "carry_share_l4": level * 0.30,
                "snap_share_last": 0.05 + level * 0.90,
                "snap_share_l4": 0.05 + level * 0.80,
                "target_share_jump": level * 0.10,
                "carry_share_jump": level * 0.10,
                "snap_share_jump": level * 0.15,
                "games_played_prior": repeat + 1,
                "practice_level": None if repeat == 0 else float(repeat % 3),
                "team_vacated_target_share": (
                    None if repeat == 0 else level * 0.20
                ),
                "team_vacated_carry_share": (
                    None if repeat == 0 else level * 0.25
                ),
                "realized_state": state,
            })
    return pd.DataFrame(rows)


def test_transition_input_denies_outcomes_and_builds_missing_flags():
    rows = _transition_rows()
    prepared = prepare_transition_frame(rows)
    assert list(prepared.columns) == [*MODEL_FEATURES, "realized_state"]
    assert prepared.injury_status_missing.sum() == len(STATES)
    assert prepared.practice_level_missing.sum() == len(STATES)
    assert prepared.vacated_target_missing.sum() == len(STATES)
    assert prepared.vacated_carry_missing.sum() == len(STATES)

    unsafe = rows.assign(dk_points=100.0)
    with pytest.raises(LatentRoleStateError, match="forbidden outcomes"):
        prepare_transition_frame(unsafe)

    with pytest.raises(LatentRoleStateError, match="unsupported transition"):
        prepare_transition_frame(rows.assign(position="QB"))


def test_frozen_transition_fit_is_deterministic_and_predicts_canonical_states():
    rows = _transition_rows()
    first = fit_role_transition(rows)
    second = fit_role_transition(rows)
    assert first.n_rows == len(rows)
    assert set(first.classes) == set(STATES)

    live = rows.drop(columns="realized_state").iloc[:7]
    p1 = first.predict_proba(live)
    p2 = second.predict_proba(live)
    assert list(p1.columns) == list(STATES)
    assert np.allclose(p1, p2)
    assert np.allclose(p1.sum(axis=1), 1.0)

    baseline = empirical_transition_probabilities(rows, rows.iloc[:7])
    assert list(baseline.columns) == list(STATES)
    assert np.allclose(baseline.sum(axis=1), 1.0)


def test_source_query_is_score_denying_and_expanding_audit_is_walk_forward():
    lower = TRANSITION_SOURCE_SQL.lower()
    for forbidden in (
        "fantasy_points", "dk_points", "lineup_score", "winner_score",
        "winnings", "payout",
    ):
        assert forbidden not in lower
    assert "t.season between 2018 and 2025" in lower
    assert "t.position in ('rb', 'wr', 'te')" in lower

    frames = []
    for season in (2021, 2022, 2023):
        frame = _transition_rows().copy()
        frame["season"] = season
        frames.append(frame)
    audit = expanding_role_audit(
        pd.concat(frames, ignore_index=True), evaluation_seasons=(2023,),
    )
    assert audit.season.tolist() == [2023]
    assert audit.n_train.tolist() == [80]
    assert audit.n_test.tolist() == [40]
    for column in (
        "model_log_loss", "model_multiclass_brier",
        "baseline_log_loss", "baseline_multiclass_brier",
    ):
        assert np.isfinite(audit[column]).all()


def test_role_calibration_metrics_use_only_state_labels():
    truth = pd.Series(list(STATES), index=range(len(STATES)), dtype="string")
    values = np.full((len(STATES), len(STATES)), 0.025)
    np.fill_diagonal(values, 0.90)
    probabilities = pd.DataFrame(values, columns=STATES, index=truth.index)
    scores = multiclass_scores(truth, probabilities)
    assert 0 < scores["log_loss"] < 0.2
    assert 0 < scores["multiclass_brier"] < 0.02

    with pytest.raises(LatentRoleStateError, match="canonical"):
        multiclass_scores(truth, probabilities[list(reversed(STATES))])
