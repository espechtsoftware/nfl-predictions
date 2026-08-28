from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.corpus_r6_belief_calibration_v1 import (
    BeliefCalibrationError,
)
from nfl_dfs.research.corpus_r6_l2_base_rate_v1 import (
    apply_l2_base_rate_calibration_v1,
    build_l2_base_rate_calibration_release_v1,
    l2_base_rate_residual_samples_by_group_v1,
    validate_l2_base_rate_calibration_release_v1,
)
from nfl_dfs.research.corpus_r6_l2_base_rate_runtime_v1 import (
    build_l2_base_rate_historical_bank_v1,
    build_l2_base_rate_prospective_bank_v1,
)
from nfl_dfs.research.latent_role_state import INPUT_FEATURES, STATES


def _identity(name: str, digit: str) -> dict[str, object]:
    return {
        "uri": f"gs://bucket/{name}.parquet",
        "generation": "42",
        "sha256": digit * 64,
        "bytes": 1234,
    }


def _features(position: str, previous_state: str) -> dict[str, object]:
    state_index = STATES.index(previous_state) if previous_state in STATES else 2
    level = 0.05 + state_index * 0.15
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
        "position": position,
        "previous_state": previous_state,
        "injury_status": "Healthy",
    }
    assert set(values) == set(INPUT_FEATURES)
    return values


def _history() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    for season in range(2018, 2023):
        for position in ("RB", "WR", "TE"):
            for previous_index, previous_state in enumerate(STATES):
                outcomes = [previous_state] * 20
                if previous_index + 1 < len(STATES):
                    outcomes += [STATES[previous_index + 1]] * 8
                for repeat, realized_state in enumerate(outcomes):
                    identity = (
                        f"{season}-{position}-{previous_state}-{repeat:02d}"
                    )
                    rows.append({
                        "gsis_id": identity,
                        "season": season,
                        "week": repeat % 18 + 1,
                        "team": f"T-{identity}",
                        "target_share": 0.1,
                        "carry_share": 0.1,
                        "snap_share": 0.5,
                        "realized_state": realized_state,
                        **_features(position, previous_state),
                    })
            for repeat in range(20):
                identity = f"{season}-{position}-unknown-{repeat:02d}"
                rows.append({
                    "gsis_id": identity,
                    "season": season,
                    "week": repeat % 18 + 1,
                    "team": f"T-{identity}",
                    "target_share": 0.1,
                    "carry_share": 0.1,
                    "snap_share": 0.5,
                    "realized_state": "rotation",
                    **_features(position, "unknown"),
                })
    roles = pd.DataFrame(rows)
    residual_rows: list[dict[str, object]] = []
    for row in roles[roles["season"].isin((2019, 2021, 2022))].itertuples():
        previous = str(row.previous_state)
        jumped = previous in STATES and STATES.index(str(row.realized_state)) > (
            STATES.index(previous)
        )
        residual_rows.append({
            "gsis_id": row.gsis_id,
            "season": row.season,
            "week": row.week,
            "ordinary_mean": 10.0,
            "player_actual_points": 24.0 if jumped else 10.0,
        })
    return roles, pd.DataFrame(residual_rows)


@pytest.fixture(scope="module")
def release() -> dict[str, object]:
    roles, residuals = _history()
    return build_l2_base_rate_calibration_release_v1(
        role_history=roles,
        residual_history=residuals,
        source_identities={
            "role": _identity("role", "a"),
            "residual": _identity("residual", "b"),
        },
        code_sha="c" * 40,
    )


def test_base_rate_release_passes_prespecified_forward_and_holdout_gates(release):
    assert release["hyperparameter_search_performed"] is False
    assert release["candidate_preexisting_as_exact_l2_baseline"] is True
    assert release["post_failure_fallback_evaluation_disclosed"] is True
    for fold in ("WF21", "HOLD22"):
        metrics = release["folds"][fold]
        assert metrics["candidate_log_loss"] < metrics["comparator_log_loss"]
        assert metrics["candidate_multiclass_brier"] < metrics[
            "comparator_multiclass_brier"
        ]
        assert metrics["candidate_competing_jump_scores"]["log_loss"] < (
            metrics["comparator_competing_jump_scores"]["log_loss"]
        )
        assert metrics["candidate_competing_jump_scores"]["brier"] < (
            metrics["comparator_competing_jump_scores"]["brier"]
        )
    assert release["gate"]["passes"] is True
    assert release["prospective_challenger_bank_generation_licensed"] is True
    assert release["historical_lineup_scoring_licensed"] is False
    assert release["production_change_licensed"] is False
    assert validate_l2_base_rate_calibration_release_v1(release) == release


def test_base_rate_release_is_order_invariant_and_has_positive_residuals(release):
    roles, residuals = _history()
    shuffled = build_l2_base_rate_calibration_release_v1(
        role_history=roles.sample(frac=1.0, random_state=7),
        residual_history=residuals.sample(frac=1.0, random_state=9),
        source_identities={
            "role": _identity("role", "a"),
            "residual": _identity("residual", "b"),
        },
        code_sha="c" * 40,
    )
    assert shuffled == release
    samples = l2_base_rate_residual_samples_by_group_v1(release)
    assert set(samples) == {"RB", "WR", "TE"}
    assert all(len(values) >= 20 for values in samples.values())
    assert all(float(values.mean()) > 0.0 for values in samples.values())


def test_hold22_application_is_unchanged_by_hold22_labels_and_residuals(release):
    roles, residuals = _history()
    target_rows = roles.index[
        roles["season"].eq(2022)
        & roles["previous_state"].eq("inactive")
        & roles["realized_state"].eq("inactive")
    ]
    roles.loc[target_rows[0], "realized_state"] = "dormant"
    residual_rows = residuals.index[
        residuals["season"].eq(2022)
        & residuals["gsis_id"].eq(roles.loc[target_rows[0], "gsis_id"])
    ]
    residuals.loc[residual_rows[0], "player_actual_points"] = 99.0
    changed = build_l2_base_rate_calibration_release_v1(
        role_history=roles,
        residual_history=residuals,
        source_identities={
            "role": _identity("role", "a"),
            "residual": _identity("residual", "b"),
        },
        code_sha="c" * 40,
    )
    original_application = release["historical_application_registry"][
        "HOLD22"
    ]
    changed_application = changed["historical_application_registry"][
        "HOLD22"
    ]
    assert changed_application == original_application
    assert original_application["role_train_last_season"] == 2021
    assert original_application["residual_source_fold_ids"] == [
        "CAL19", "WF21"
    ]
    assert original_application["residual_source_seasons"] == [2019, 2021]
    assert original_application["uses_target_role_labels_for_fit"] is False
    assert original_application[
        "uses_target_player_outcomes_for_fit"
    ] is False


def test_base_rate_application_is_team_exclusive_and_zeroes_out_players(release):
    target = pd.DataFrame([
        {
            "gsis_id": "wr-a",
            "team": "A",
            "position": "WR",
            "previous_state": "rotation",
            "injury_status": "Healthy",
        },
        {
            "gsis_id": "te-a",
            "team": "A",
            "position": "TE",
            "previous_state": "dormant",
            "injury_status": "Out",
        },
        {
            "gsis_id": "rb-b",
            "team": "B",
            "position": "RB",
            "previous_state": "secondary",
            "injury_status": "Healthy",
        },
    ])
    application = apply_l2_base_rate_calibration_v1(release, target)
    values = application.role_jump_probabilities
    assert values.shape == (3,)
    assert values[1] == 0.0
    assert values[:2].sum() <= 1.0
    assert values[2:].sum() <= 1.0
    assert application.receipt["uses_lineup_outcomes"] is False


def test_base_rate_release_rejects_outcomes_and_tampering(release):
    roles, residuals = _history()
    roles["lineup_score"] = 200.0
    with pytest.raises(BeliefCalibrationError, match="forbidden outcomes"):
        build_l2_base_rate_calibration_release_v1(
            role_history=roles,
            residual_history=residuals,
            source_identities={"role": _identity("role", "a")},
            code_sha="d" * 40,
        )
    tampered = deepcopy(release)
    tampered["transition_table"][0]["probabilities"]["primary"] += 0.1
    with pytest.raises(BeliefCalibrationError, match="probabilities differ"):
        validate_l2_base_rate_calibration_release_v1(tampered)


def test_base_rate_application_requires_a_passing_release(release):
    failed = deepcopy(release)
    failed["gate"]["hold22_multiclass_improves"] = False
    failed["gate"]["passes"] = False
    failed["prospective_challenger_bank_generation_licensed"] = False
    failed.pop("release_sha256")
    from nfl_dfs.research.belief_world_v1 import canonical_sha256

    failed["release_sha256"] = canonical_sha256(failed)
    target = pd.DataFrame([{
        "gsis_id": "wr-a",
        "team": "A",
        "position": "WR",
        "previous_state": "rotation",
        "injury_status": "Healthy",
    }])
    with pytest.raises(BeliefCalibrationError, match="did not pass HOLD22"):
        apply_l2_base_rate_calibration_v1(failed, target)


def _historical_target(season: int) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "gsis_id": "wr-a",
            "season": season,
            "team": "A",
            "position": "WR",
            "previous_state": "rotation",
            "injury_status": "Healthy",
        },
        {
            "gsis_id": "te-a",
            "season": season,
            "team": "A",
            "position": "TE",
            "previous_state": "dormant",
            "injury_status": "Healthy",
        },
        {
            "gsis_id": "rb-b",
            "season": season,
            "team": "B",
            "position": "RB",
            "previous_state": "secondary",
            "injury_status": "Healthy",
        },
        {
            "gsis_id": "wr-b",
            "season": season,
            "team": "B",
            "position": "WR",
            "previous_state": "dormant",
            "injury_status": "Healthy",
        },
        {
            "gsis_id": "te-c",
            "season": season,
            "team": "C",
            "position": "TE",
            "previous_state": "secondary",
            "injury_status": "Healthy",
        },
        {
            "gsis_id": "rb-c",
            "season": season,
            "team": "C",
            "position": "RB",
            "previous_state": "rotation",
            "injury_status": "Healthy",
        },
    ])


def _historical_bank(
    release: dict[str, object], fold_id: str, season: int,
):
    target = _historical_target(season)
    worlds = tuple(f"w{index}" for index in range(256))
    ordinary = np.arange(len(target) * len(worlds), dtype=float).reshape(
        len(target), len(worlds)
    )
    return build_l2_base_rate_historical_bank_v1(
        release=release,
        fold_id=fold_id,
        target_players=target,
        ordinary_draws=ordinary,
        player_ids=tuple(target["gsis_id"]),
        world_ids=worlds,
        calibration_source_identity=_identity("calibration", "d"),
        source_identities={"ordinary": _identity("ordinary", "e")},
        component_seed=719,
        mixture_seed=727,
    )


def _prospective_bank(release: dict[str, object], season: int):
    target = _historical_target(season)
    worlds = tuple(f"w{index}" for index in range(256))
    ordinary = np.arange(len(target) * len(worlds), dtype=float).reshape(
        len(target), len(worlds)
    )
    return build_l2_base_rate_prospective_bank_v1(
        release=release,
        target_players=target,
        ordinary_draws=ordinary,
        player_ids=tuple(target["gsis_id"]),
        world_ids=worlds,
        calibration_source_identity=_identity("calibration", "d"),
        source_identities={"ordinary": _identity("ordinary", "e")},
        component_seed=719,
        mixture_seed=727,
    )


def test_cal19_historical_runtime_fails_without_pre_target_residual_support(
    release,
):
    with pytest.raises(
        BeliefCalibrationError, match="CAL19 lacks pre-target residual support"
    ):
        _historical_bank(release, "CAL19", 2019)


@pytest.mark.parametrize(("fold_id", "season"), [
    ("WF21", 2021),
    ("HOLD22", 2022),
])
def test_historical_worlds_ignore_target_year_labels_and_residuals(
    release, fold_id, season,
):
    roles, residuals = _history()
    role_index = roles.index[roles["season"].eq(season)][0]
    player_id = roles.loc[role_index, "gsis_id"]
    roles.loc[role_index, "realized_state"] = "primary"
    residual_index = residuals.index[
        residuals["season"].eq(season)
        & residuals["gsis_id"].eq(player_id)
    ][0]
    residuals.loc[residual_index, "player_actual_points"] = 99.0
    perturbed = build_l2_base_rate_calibration_release_v1(
        role_history=roles,
        residual_history=residuals,
        source_identities={
            "role": _identity("role-perturbed", "f"),
            "residual": _identity("residual-perturbed", "0"),
        },
        code_sha="c" * 40,
    )
    assert (
        perturbed["historical_application_registry"][fold_id]
        == release["historical_application_registry"][fold_id]
    )

    original_bank = _historical_bank(release, fold_id, season)
    perturbed_bank = _historical_bank(perturbed, fold_id, season)
    assert np.array_equal(
        original_bank.application.role_jump_probabilities,
        perturbed_bank.application.role_jump_probabilities,
    )
    assert np.array_equal(
        original_bank.components.role_jump_draws,
        perturbed_bank.components.role_jump_draws,
    )
    assert np.array_equal(original_bank.bank.draws, perturbed_bank.bank.draws)
    assert np.array_equal(
        original_bank.bank.latent_states, perturbed_bank.bank.latent_states
    )
    assert (
        original_bank.bank.belief_world_artifact
        == perturbed_bank.bank.belief_world_artifact
    )


def test_prospective_runtime_holds_the_2018_2022_fit_fixed_across_panel(release):
    bank_2023 = _prospective_bank(release, 2023)
    bank_2025 = _prospective_bank(release, 2025)
    assert bank_2023.application.receipt["calibration_id"] == release[
        "calibration_id"
    ]
    assert np.array_equal(bank_2023.bank.draws, bank_2025.bank.draws)
    assert (
        bank_2023.bank.belief_world_artifact
        == bank_2025.bank.belief_world_artifact
    )
    with pytest.raises(
        BeliefCalibrationError, match="prospective target season differs"
    ):
        _prospective_bank(release, 2022)
    exposed = _historical_target(2023).assign(realized_state="primary")
    with pytest.raises(BeliefCalibrationError, match="target players expose"):
        build_l2_base_rate_prospective_bank_v1(
            release=release,
            target_players=exposed,
            ordinary_draws=np.zeros((len(exposed), 32)),
            player_ids=tuple(exposed["gsis_id"]),
            world_ids=tuple(f"w{index}" for index in range(32)),
            calibration_source_identity=_identity("calibration", "d"),
            source_identities={"ordinary": _identity("ordinary", "e")},
            component_seed=719,
            mixture_seed=727,
        )
