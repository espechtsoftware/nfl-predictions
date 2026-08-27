from __future__ import annotations

from copy import deepcopy
import math

import numpy as np
import pytest

from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.research.belief_world_v1 import (
    DIRECT_SAMPLING_PROPOSAL_ID,
    LINEUP_DEVELOPMENT_SEASONS,
    SAMPLING_DESIGN_SCHEMA,
    SERVED_BASELINE_LAW_ENV_KEYS,
    SERVED_BASELINE_LAW_ID,
    BeliefWorldError,
    add_discrete_log_probability,
    build_belief_world_artifact,
    build_support_census,
    calibration_fold_registry,
    canonical_sha256,
    direct_sampling_design,
    mixture_log_density,
    normalize_log_importance_weights,
    served_baseline_environment,
    served_baseline_identity,
    support_census_contract,
    validate_belief_world_artifact,
    validate_sampling_design,
)


def _importance_design(**updates) -> dict[str, object]:
    design: dict[str, object] = {
        "schema": SAMPLING_DESIGN_SCHEMA,
        "adaptation_bank_id": "adaptation-bank-1",
        "evaluation_bank_id": "evaluation-bank-1",
        "proposal_frozen_before_evaluation": True,
        "evaluation_worlds_are_fresh": True,
        "evaluation_worlds_are_adaptation_elites": False,
        "proposal_density_evaluation": "full-mixture",
        "density_proposal_id": "rare-breakout-proposal-v1",
        "proposal_supports_target": True,
    }
    design.update(updates)
    return design


def _player_support_record(
    fold_id: str, season: int, week: int = 1,
) -> dict[str, object]:
    return {
        "fold_id": fold_id,
        "season": season,
        "table": "player",
        "dimensions": {"week": week, "position": "WR"},
        "counts": {
            "player_rows": 20,
            "active_rows": 16,
            "salary_rows": 19,
            "component_rows": 20,
            "game_id_rows": 20,
            "team_id_rows": 20,
            "market_rows": 8,
            "tabpfn_rows": 12,
            "empirical_fallback_rows": 8,
        },
    }


def test_served_baseline_adapter_is_exact_and_separates_candidate_policy() -> None:
    expected = ADOPTED_CLASSIC_POLICY.engine_environment()
    assert served_baseline_environment() == expected
    identity = served_baseline_identity()
    assert identity["law_id"] == SERVED_BASELINE_LAW_ID
    assert identity["direct_sampling_proposal_id"] == \
        DIRECT_SAMPLING_PROPOSAL_ID
    assert identity["full_policy_environment"] == expected
    assert set(identity["law_environment"]) == set(
        SERVED_BASELINE_LAW_ENV_KEYS
    )
    assert "N_CE" in identity["full_policy_environment"]
    assert "N_CE" not in identity["law_environment"]
    assert identity["candidate_generation_is_not_part_of_law"] is True
    unhashed = dict(identity)
    digest = unhashed.pop("identity_sha256")
    assert canonical_sha256(unhashed) == digest


def test_direct_world_artifact_binds_ordered_players_worlds_and_draws() -> None:
    draws = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    artifact = build_belief_world_artifact(
        draws=draws,
        player_ids=("p1", "p2"),
        world_ids=("w1", "w2", "w3"),
        law_id=SERVED_BASELINE_LAW_ID,
        proposal_id=DIRECT_SAMPLING_PROPOSAL_ID,
        calibration_id="CAL19",
        sampling_design=direct_sampling_design("evaluation-direct-1"),
    )
    assert artifact["player_world_shape"] == [2, 3]
    assert artifact["normalized_weight"] == pytest.approx([1 / 3] * 3)
    assert artifact["weight_diagnostics"]["effective_sample_size"] == \
        pytest.approx(3.0)
    assert validate_belief_world_artifact(artifact, draws=draws) == artifact

    reordered = build_belief_world_artifact(
        draws=draws[::-1],
        player_ids=("p2", "p1"),
        world_ids=("w1", "w2", "w3"),
        law_id=SERVED_BASELINE_LAW_ID,
        proposal_id=DIRECT_SAMPLING_PROPOSAL_ID,
        calibration_id="CAL19",
        sampling_design=direct_sampling_design("evaluation-direct-1"),
    )
    assert reordered["player_world_binding_sha256"] != artifact[
        "player_world_binding_sha256"
    ]
    with pytest.raises(BeliefWorldError, match="duplicate"):
        build_belief_world_artifact(
            draws=draws,
            player_ids=("p1", "p1"),
            world_ids=("w1", "w2", "w3"),
            law_id=SERVED_BASELINE_LAW_ID,
            proposal_id=DIRECT_SAMPLING_PROPOSAL_ID,
            calibration_id="CAL19",
            sampling_design=direct_sampling_design("evaluation-direct-1"),
        )


def test_importance_normalization_is_stable_and_reports_concentration() -> None:
    result = normalize_log_importance_weights(
        [10_000.0, 9_000.0, 8_000.0],
        [0.0, 0.0, 0.0],
        proposal_supports_target=True,
    )
    assert np.isfinite(result.normalized_weight).all()
    assert result.normalized_weight.sum() == pytest.approx(1.0)
    assert result.normalized_weight[0] > 0.999
    assert 1.0 <= result.effective_sample_size < 1.01
    assert result.max_normalized_weight == pytest.approx(
        result.normalized_weight[0]
    )
    with pytest.raises(BeliefWorldError, match="support"):
        normalize_log_importance_weights(
            [0.0], [0.0], proposal_supports_target=False
        )
    with pytest.raises(BeliefWorldError, match="finite"):
        normalize_log_importance_weights(
            [0.0], [-np.inf], proposal_supports_target=True
        )


def test_full_mixture_denominator_and_discrete_probability_are_exact() -> None:
    components = np.log(np.array([
        [0.90, 0.20, 0.50],
        [0.10, 0.80, 0.25],
    ]))
    mixed = mixture_log_density(components, [0.25, 0.75])
    expected = np.log(
        0.25 * np.exp(components[0]) + 0.75 * np.exp(components[1])
    )
    assert mixed == pytest.approx(expected)
    # The denominator is not the density of whichever component happened to
    # generate the world.
    assert not np.allclose(mixed, components[0])

    conditional = np.log(np.array([0.5, 0.25, 0.125]))
    joint = add_discrete_log_probability(conditional, [0.2, 0.4, 0.8])
    assert joint == pytest.approx(
        np.log(np.array([0.5, 0.25, 0.125]) * np.array([0.2, 0.4, 0.8]))
    )
    with pytest.raises(BeliefWorldError, match=r"\(0, 1\]"):
        add_discrete_log_probability([0.0], [0.0])


def test_artifact_retains_full_mixture_weights_and_component_probabilities() -> None:
    components = np.log(np.array([
        [0.8, 0.3, 0.6],
        [0.2, 0.7, 0.4],
    ]))
    log_q = mixture_log_density(components, [0.7, 0.3])
    log_p = np.log(np.array([0.5, 0.5, 0.5]))
    artifact = build_belief_world_artifact(
        draws=np.arange(6, dtype=float).reshape(2, 3),
        player_ids=("p1", "p2"),
        world_ids=("w1", "w2", "w3"),
        law_id="correlated-ceiling-v1",
        proposal_id="rare-breakout-proposal-v1",
        calibration_id="WF21",
        sampling_design=_importance_design(),
        log_target_density=log_p,
        log_proposal_density=log_q,
        proposal_component_ids=("base", "tail", "base"),
        proposal_component_probabilities=(0.7, 0.3, 0.7),
    )
    expected = np.exp(log_p - log_q)
    expected /= expected.sum()
    assert artifact["normalized_weight"] == pytest.approx(expected)
    assert artifact["proposal_component_probabilities"] == [0.7, 0.3, 0.7]


def test_direct_artifact_rejects_nonidentity_density_or_component() -> None:
    common = {
        "draws": np.array([[1.0, 2.0]]),
        "player_ids": ("p1",),
        "world_ids": ("w1", "w2"),
        "law_id": SERVED_BASELINE_LAW_ID,
        "proposal_id": DIRECT_SAMPLING_PROPOSAL_ID,
        "calibration_id": "CAL19",
        "sampling_design": direct_sampling_design("direct-density-bank"),
    }
    with pytest.raises(BeliefWorldError, match="identical target/proposal"):
        build_belief_world_artifact(
            **common,
            log_target_density=[0.0, 0.0],
            log_proposal_density=[0.0, -1.0],
        )
    with pytest.raises(BeliefWorldError, match="unit-probability proposal"):
        build_belief_world_artifact(
            **common,
            proposal_component_ids=("other", "other"),
            proposal_component_probabilities=(1.0, 1.0),
        )


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"evaluation_worlds_are_adaptation_elites": True}, "adaptation elites"),
        (
            {"evaluation_bank_id": "adaptation-bank-1"},
            "must be independent",
        ),
        (
            {"proposal_frozen_before_evaluation": False},
            "not frozen",
        ),
        ({"evaluation_worlds_are_fresh": False}, "not a fresh"),
        (
            {"proposal_density_evaluation": "selected-component"},
            "full mixture",
        ),
        (
            {"proposal_density_evaluation": "direct-target"},
            "cannot have an adaptation bank",
        ),
    ],
)
def test_sampling_design_rejects_adaptation_elites_and_invalid_densities(
    updates, message,
) -> None:
    with pytest.raises(BeliefWorldError, match=message):
        validate_sampling_design(
            _importance_design(**updates),
            proposal_id="rare-breakout-proposal-v1",
        )


def test_artifact_validation_rejects_weight_or_matrix_drift() -> None:
    draws = np.array([[1.0, 2.0], [3.0, 4.0]])
    artifact = build_belief_world_artifact(
        draws=draws,
        player_ids=("p1", "p2"),
        world_ids=("w1", "w2"),
        law_id=SERVED_BASELINE_LAW_ID,
        proposal_id=DIRECT_SAMPLING_PROPOSAL_ID,
        calibration_id="CAL19",
        sampling_design=direct_sampling_design("direct-bank"),
    )
    changed = deepcopy(artifact)
    changed["normalized_weight"][0] = 0.75
    with pytest.raises(BeliefWorldError, match="importance-weight values"):
        validate_belief_world_artifact(changed)
    with pytest.raises(BeliefWorldError, match="matrix differs"):
        validate_belief_world_artifact(artifact, draws=draws + 0.5)


def test_fold_registry_is_expanding_and_disjoint_from_lineup_panel() -> None:
    registry = calibration_fold_registry()
    folds = registry["folds"]
    assert [fold["fold_id"] for fold in folds] == ["CAL19", "WF21", "HOLD22"]
    assert [fold["season"] for fold in folds] == [2019, 2021, 2022]
    assert folds[0]["prior_label_folds"] == []
    assert folds[1]["prior_label_folds"] == ["CAL19"]
    assert folds[2]["prior_label_folds"] == ["CAL19", "WF21"]
    assert all(
        fold["component_train_last_season"] < fold["season"] for fold in folds
    )
    assert set(fold["season"] for fold in folds).isdisjoint(
        LINEUP_DEVELOPMENT_SEASONS
    )
    assert registry["primary_excluded_seasons"] == [2020]
    assert registry["labels_read"] is False


def test_support_census_is_canonical_and_rejects_outcome_fields() -> None:
    records = [
        _player_support_record("WF21", 2021),
        _player_support_record("CAL19", 2019),
    ]
    first = build_support_census(records)
    second = build_support_census(list(reversed(records)))
    assert first == second
    assert first["record_count"] == 2
    assert [row["fold_id"] for row in first["records"]] == ["CAL19", "WF21"]
    assert first["fantasy_or_lineup_labels_read"] is False
    assert first["uses_realized_outcomes"] is False
    assert support_census_contract()["uses_realized_outcomes"] is False

    forbidden = deepcopy(records[0])
    forbidden["dimensions"]["actual_points"] = 20.0
    with pytest.raises(BeliefWorldError, match="forbidden outcome field"):
        build_support_census([forbidden])


def test_support_census_rejects_duplicate_cells_and_wrong_fold_season() -> None:
    record = _player_support_record("HOLD22", 2022)
    with pytest.raises(BeliefWorldError, match="cell repeats"):
        build_support_census([record, deepcopy(record)])
    wrong = deepcopy(record)
    wrong["season"] = 2021
    with pytest.raises(BeliefWorldError, match="season/fold"):
        build_support_census([wrong])
    with pytest.raises(BeliefWorldError, match="cannot be empty"):
        build_support_census([])


def test_direct_sampling_weights_have_exact_uniform_diagnostics() -> None:
    result = normalize_log_importance_weights(
        [0.0] * 10, [0.0] * 10, proposal_supports_target=True
    )
    assert result.normalized_weight == pytest.approx([0.1] * 10)
    assert result.effective_sample_size == pytest.approx(10.0)
    assert result.effective_sample_fraction == pytest.approx(1.0)
    assert result.max_normalized_weight == pytest.approx(0.1)
    assert result.entropy == pytest.approx(math.log(10.0))
