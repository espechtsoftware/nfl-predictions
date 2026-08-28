from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.corpus_r6_belief_calibration_v1 import (
    BeliefCalibrationError,
    L1_METRICS,
    apply_l2_role_jump_calibration_v1,
    build_l1_shootout_calibration_release_v1,
    build_l2_role_jump_calibration_release_v1,
    l1_probability_by_game_v1,
    l2_residual_samples_by_group_v1,
    validate_l1_shootout_calibration_release_v1,
    validate_l2_role_jump_calibration_release_v1,
)
from nfl_dfs.research.corpus_r6_belief_law_challengers_v1 import (
    sample_l2_team_role_jump_bank_v1,
)
from nfl_dfs.research.corpus_r6_l2_role_jump_components_v1 import (
    build_l2_role_jump_components_v1,
)
from nfl_dfs.research.latent_role_state import INPUT_FEATURES, STATES


def _identity(name: str, digit: str = "a") -> dict[str, object]:
    return {
        "uri": f"gs://bucket/{name}.json",
        "generation": "42",
        "sha256": digit * 64,
        "bytes": 1234,
    }


def _l1_events() -> pd.DataFrame:
    rows = []
    # q = .05 + p*(.85-.05); 18/40 positives fixes p at exactly .5.
    for season in (2019, 2021, 2022):
        for sample in range(40):
            for metric_index, metric in enumerate(L1_METRICS):
                rows.append({
                    "season": season,
                    "sample_id": f"{season}-team-game-{sample:03d}",
                    "metric": metric,
                    "observed_event": int((sample + metric_index) % 40 < 18),
                    "ordinary_probability": 0.05,
                    "shootout_probability": 0.85,
                })
    return pd.DataFrame(rows)


def _l1_moments() -> pd.DataFrame:
    rows = []
    for season in (2019, 2021, 2022):
        for component, correlation in (
            ("ordinary", 0.0),
            ("shootout", 0.8),
            ("observed", 0.4),
        ):
            rows.append({
                "season": season,
                "component": component,
                "count": 1000,
                "sum_x": 0.0,
                "sum_y": 0.0,
                "sum_x2": 1000.0,
                "sum_y2": 1000.0,
                "sum_xy": correlation * 1000.0,
            })
    return pd.DataFrame(rows)


def test_l1_walk_forward_release_freezes_probability_and_coexceedence():
    first = build_l1_shootout_calibration_release_v1(
        event_rows=_l1_events(),
        opposing_wr1_moment_rows=_l1_moments(),
        source_identities={"events": _identity("events")},
    )
    second = build_l1_shootout_calibration_release_v1(
        event_rows=_l1_events().sample(frac=1.0, random_state=7),
        opposing_wr1_moment_rows=_l1_moments().sample(
            frac=1.0, random_state=9
        ),
        source_identities={"events": _identity("events")},
    )
    assert first == second
    assert first["final_shootout_probability"] == pytest.approx(0.5)
    assert first["folds"]["WF21"]["fit_seasons"] == [2019]
    assert first["folds"]["HOLD22"]["fit_seasons"] == [2019, 2021]
    assert first["folds"]["HOLD22"]["mixture_brier"] < first["folds"][
        "HOLD22"
    ]["ordinary_brier"]
    assert first["folds"]["HOLD22"]["opposing_wr1_correlation"][
        "mixture"
    ] == pytest.approx(0.4)
    assert first["gate"]["passes"] is True
    assert validate_l1_shootout_calibration_release_v1(first) == first
    assert l1_probability_by_game_v1(first, ("g0", "g0", "g1")) == {
        "g0": pytest.approx(0.5),
        "g1": pytest.approx(0.5),
    }


def test_l1_rejects_incomplete_evidence_and_tampered_release():
    incomplete = _l1_events()
    incomplete = incomplete[~(
        incomplete["season"].eq(2022)
        & incomplete["sample_id"].eq("2022-team-game-000")
        & incomplete["metric"].eq(L1_METRICS[0])
    )]
    with pytest.raises(BeliefCalibrationError, match="complete metric"):
        build_l1_shootout_calibration_release_v1(
            event_rows=incomplete,
            opposing_wr1_moment_rows=_l1_moments(),
            source_identities={"events": _identity("events")},
        )
    release = build_l1_shootout_calibration_release_v1(
        event_rows=_l1_events(),
        opposing_wr1_moment_rows=_l1_moments(),
        source_identities={"events": _identity("events")},
    )
    tampered = deepcopy(release)
    tampered["final_shootout_probability"] = 0.9
    with pytest.raises(BeliefCalibrationError, match="content hash"):
        validate_l1_shootout_calibration_release_v1(tampered)


def _state_features(state_index: int) -> dict[str, object]:
    level = 0.05 + 0.18 * state_index
    values: dict[str, object] = {
        "target_share_last": level,
        "target_share_l4": level,
        "carry_share_last": level,
        "carry_share_l4": level,
        "snap_share_last": level,
        "snap_share_l4": level,
        "target_share_jump": 0.0,
        "carry_share_jump": 0.0,
        "snap_share_jump": 0.0,
        "games_played_prior": 8.0,
        "practice_level": 1.0,
        "team_vacated_target_share": 0.0,
        "team_vacated_carry_share": 0.0,
        "position": "WR",
        "previous_state": "rotation",
        "injury_status": "Healthy",
    }
    assert set(values) == set(INPUT_FEATURES)
    return values


def _role_and_residual_history() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for season in range(2018, 2023):
        for position in ("RB", "WR", "TE"):
            # Clear state clusters let the mature transition model beat the
            # previous-state-only empirical baseline.
            for state_index, state in enumerate(STATES):
                for repeat in range(30):
                    features = _state_features(state_index)
                    features["position"] = position
                    rows.append({
                        "gsis_id": (
                            f"{season}-{position}-{state}-base-{repeat:02d}"
                        ),
                        "season": season,
                        "week": repeat % 18 + 1,
                        "team": (
                            f"T-{season}-{position}-{state}-base-{repeat:02d}"
                        ),
                        "target_share": 0.05 + 0.18 * state_index,
                        "carry_share": 0.05 + 0.18 * state_index,
                        "snap_share": 0.05 + 0.18 * state_index,
                        "realized_state": state,
                        **features,
                    })
            # Twenty-five intentionally surprising primary states share the
            # rotation predictor cluster (30 ordinary rotation rows), so the
            # modal forecast remains rotation while residual support is real.
            for repeat in range(25):
                features = _state_features(STATES.index("rotation"))
                features["position"] = position
                rows.append({
                    "gsis_id": f"{season}-{position}-surprise-{repeat:02d}",
                    "season": season,
                    "week": repeat % 18 + 1,
                    "team": f"T-{season}-{position}-surprise-{repeat:02d}",
                    "target_share": 0.75,
                    "carry_share": 0.75,
                    "snap_share": 0.75,
                    "realized_state": "primary",
                    **features,
                })
    role = pd.DataFrame(rows)
    residual_rows = []
    for row in role[role["season"].isin((2019, 2021, 2022))].itertuples():
        surprise = "-surprise-" in row.gsis_id
        residual_rows.append({
            "gsis_id": row.gsis_id,
            "season": row.season,
            "week": row.week,
            "ordinary_mean": 10.0,
            "player_actual_points": 25.0 if surprise else 10.0,
        })
    return role, pd.DataFrame(residual_rows)


@pytest.fixture(scope="module")
def l2_release() -> dict[str, object]:
    role, residual = _role_and_residual_history()
    return build_l2_role_jump_calibration_release_v1(
        role_history=role,
        residual_history=residual,
        source_identities={
            "role": _identity("role", "b"),
            "residual": _identity("residual", "c"),
        },
        code_sha="d" * 40,
        minimum_group_support=20,
    )


def test_l2_reuses_latent_transition_and_freezes_positive_residuals(l2_release):
    assert l2_release["effective_role_source_first_season"] == 2018
    assert l2_release["registered_component_first_season"] == 2015
    assert l2_release["source_boundary_intersection_disclosed"] is True
    assert l2_release["folds"]["CAL19"][
        "effective_role_train_first_season"
    ] == 2018
    assert l2_release["gate"]["passes"] is True
    assert l2_release["uses_lineup_outcomes"] is False
    assert validate_l2_role_jump_calibration_release_v1(
        l2_release
    ) == l2_release
    samples = l2_residual_samples_by_group_v1(l2_release)
    assert set(samples) == {"RB", "WR", "TE"}
    assert all(len(values) >= 20 for values in samples.values())
    assert all(float(values.mean()) > 0 for values in samples.values())


def _target_players() -> pd.DataFrame:
    rows = []
    for index, (position, team, state_index) in enumerate((
        ("WR", "A", 2),
        ("TE", "A", 1),
        ("RB", "B", 3),
        ("WR", "B", 2),
    )):
        features = _state_features(state_index)
        features["position"] = position
        if index == 1:
            features["injury_status"] = "Out"
        rows.append({
            "gsis_id": f"target-{index}",
            "team": team,
            **features,
        })
    return pd.DataFrame(rows)


def test_l2_application_feeds_existing_component_and_team_exclusive_bank(
    l2_release,
):
    application = apply_l2_role_jump_calibration_v1(
        l2_release, _target_players()
    )
    probability = application.role_jump_probabilities
    assert probability.shape == (4,)
    assert probability[1] == 0.0  # Out is fixed away from the jump mode.
    assert probability[:2].sum() <= 1.0
    assert probability[2:].sum() <= 1.0
    ordinary = np.zeros((4, 128), dtype=float)
    calibration_identity = _identity("l2-release", "e")
    components = build_l2_role_jump_components_v1(
        ordinary_draws=ordinary,
        player_ids=tuple(_target_players()["gsis_id"]),
        empirical_group_by_player=application.empirical_group_by_player,
        residual_samples_by_group=l2_residual_samples_by_group_v1(l2_release),
        calibration_source_identity=calibration_identity,
        base_seed=71,
        minimum_group_support=20,
    )
    bank = sample_l2_team_role_jump_bank_v1(
        ordinary_draws=ordinary,
        role_jump_draws=components.role_jump_draws,
        player_ids=tuple(_target_players()["gsis_id"]),
        world_ids=tuple(f"w{index}" for index in range(128)),
        team_ids=tuple(_target_players()["team"]),
        role_jump_probabilities=probability,
        seed=72,
        calibration_id=l2_release["calibration_id"],
        source_identities={"calibration": calibration_identity},
    )
    assert np.all((bank.draws[:2] != 0.0).sum(axis=0) <= 1)
    assert np.all((bank.draws[2:] != 0.0).sum(axis=0) <= 1)


def test_l2_rejects_lineup_outcomes_and_tampered_release(l2_release):
    role, residual = _role_and_residual_history()
    role["lineup_score"] = 200.0
    with pytest.raises(BeliefCalibrationError, match="forbidden outcomes"):
        build_l2_role_jump_calibration_release_v1(
            role_history=role,
            residual_history=residual,
            source_identities={"role": _identity("role")},
            code_sha="f" * 40,
        )
    tampered = deepcopy(l2_release)
    tampered["residual_samples_by_group"]["WR"][0] += 1.0
    with pytest.raises(BeliefCalibrationError, match="content differs"):
        validate_l2_role_jump_calibration_release_v1(tampered)
