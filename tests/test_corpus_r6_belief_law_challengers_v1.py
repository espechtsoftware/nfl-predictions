from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research.belief_world_v1 import validate_belief_world_artifact
from nfl_dfs.research.corpus_r6_belief_law_challengers_v1 import (
    BeliefLawChallengerError,
    L1_LAW_ID,
    L2_LAW_ID,
    sample_l1_shootout_regime_bank_v1,
    sample_l2_team_role_jump_bank_v1,
    validate_challenger_receipt,
)


def _identity(name: str) -> dict[str, object]:
    return {
        "uri": f"gs://bucket/{name}.json",
        "generation": "123",
        "sha256": "a" * 64,
        "bytes": 456,
    }


def _axes(world_count: int = 32):
    players = ("p0", "p1", "p2", "p3")
    worlds = tuple(f"w{i}" for i in range(world_count))
    games = ("g0", "g0", "g1", "g1")
    teams = ("A", "B", "C", "D")
    return players, worlds, games, teams


def test_l1_switches_whole_games_and_emits_direct_law_artifact():
    players, worlds, games, teams = _axes()
    ordinary = np.arange(4 * len(worlds), dtype=float).reshape(4, -1)
    shootout = ordinary + 1000.0
    bank = sample_l1_shootout_regime_bank_v1(
        ordinary_draws=ordinary,
        shootout_draws=shootout,
        player_ids=players,
        world_ids=worlds,
        game_ids=games,
        team_ids=teams,
        shootout_probability_by_game={"g0": 1.0, "g1": 0.0},
        seed=7,
        calibration_id="cal19-wf21-hold22-v1",
        source_identities={"ordinary": _identity("ordinary")},
    )
    assert bank.receipt["law_id"] == L1_LAW_ID
    assert np.array_equal(bank.draws[:2], shootout[:2])
    assert np.array_equal(bank.draws[2:], ordinary[2:])
    assert np.all(bank.latent_states[0])
    assert not np.any(bank.latent_states[1])
    assert bank.receipt["mechanism"]["both_teams_share_state"] is True
    assert validate_challenger_receipt(bank.receipt) == bank.receipt
    assert (
        validate_belief_world_artifact(
            bank.belief_world_artifact, draws=bank.draws
        )
        == bank.belief_world_artifact
    )
    weights = np.asarray(bank.belief_world_artifact["normalized_weight"])
    assert np.allclose(weights, 1.0 / len(worlds), rtol=0.0, atol=1e-15)


def test_l1_is_seed_replayable_and_zero_probability_is_exact_control():
    players, worlds, games, teams = _axes(100)
    ordinary = np.zeros((4, 100))
    shootout = np.ones((4, 100))
    kwargs = dict(
        ordinary_draws=ordinary,
        shootout_draws=shootout,
        player_ids=players,
        world_ids=worlds,
        game_ids=games,
        team_ids=teams,
        shootout_probability_by_game={"g0": 0.35, "g1": 0.65},
        seed=91,
        calibration_id="calibration-v1",
        source_identities={"components": _identity("components")},
    )
    first = sample_l1_shootout_regime_bank_v1(**kwargs)
    second = sample_l1_shootout_regime_bank_v1(**kwargs)
    assert np.array_equal(first.draws, second.draws)
    assert first.receipt == second.receipt
    zero = sample_l1_shootout_regime_bank_v1(
        **{**kwargs, "shootout_probability_by_game": {"g0": 0.0, "g1": 0.0}}
    )
    assert np.array_equal(zero.draws, ordinary)


def test_l1_rejects_incomplete_probability_or_non_game_surface():
    players, worlds, games, teams = _axes()
    draws = np.zeros((4, len(worlds)))
    common = dict(
        ordinary_draws=draws,
        shootout_draws=draws,
        player_ids=players,
        world_ids=worlds,
        game_ids=games,
        team_ids=teams,
        seed=1,
        calibration_id="calibration-v1",
        source_identities={"components": _identity("components")},
    )
    with pytest.raises(BeliefLawChallengerError, match="every and only"):
        sample_l1_shootout_regime_bank_v1(
            **common, shootout_probability_by_game={"g0": 0.5}
        )
    with pytest.raises(BeliefLawChallengerError, match="exactly two"):
        sample_l1_shootout_regime_bank_v1(
            **{**common, "team_ids": ("A", "A", "C", "D")},
            shootout_probability_by_game={"g0": 0.5, "g1": 0.5},
        )


def test_l2_allows_at_most_one_role_jump_per_team_world():
    players = ("p0", "p1", "p2", "p3")
    worlds = tuple(f"w{i}" for i in range(200))
    teams = ("A", "A", "B", "B")
    ordinary = np.zeros((4, len(worlds)))
    jump = np.vstack([
        np.full(len(worlds), 10.0),
        np.full(len(worlds), 20.0),
        np.full(len(worlds), 30.0),
        np.full(len(worlds), 40.0),
    ])
    bank = sample_l2_team_role_jump_bank_v1(
        ordinary_draws=ordinary,
        role_jump_draws=jump,
        player_ids=players,
        world_ids=worlds,
        team_ids=teams,
        role_jump_probabilities=(0.25, 0.35, 0.40, 0.60),
        seed=17,
        calibration_id="cal19-wf21-hold22-v1",
        source_identities={"jump": _identity("jump")},
    )
    assert bank.receipt["law_id"] == L2_LAW_ID
    assert bank.latent_states.shape == (2, len(worlds))
    assert np.all(np.sum(bank.draws[:2] != 0.0, axis=0) <= 1)
    assert np.all(np.sum(bank.draws[2:] != 0.0, axis=0) == 1)
    for team_index in range(2):
        for world_index, selected in enumerate(bank.latent_states[team_index]):
            if selected >= 0:
                assert bank.draws[selected, world_index] == jump[selected, world_index]
    assert validate_challenger_receipt(bank.receipt) == bank.receipt


def test_l2_is_replayable_and_zero_probability_is_exact_control():
    players, worlds, _, _ = _axes(64)
    ordinary = np.arange(4 * 64, dtype=float).reshape(4, 64)
    jump = ordinary + 500.0
    kwargs = dict(
        ordinary_draws=ordinary,
        role_jump_draws=jump,
        player_ids=players,
        world_ids=worlds,
        team_ids=("A", "A", "B", "B"),
        role_jump_probabilities=(0.1, 0.2, 0.3, 0.4),
        seed=22,
        calibration_id="calibration-v1",
        source_identities={"components": _identity("components")},
    )
    first = sample_l2_team_role_jump_bank_v1(**kwargs)
    second = sample_l2_team_role_jump_bank_v1(**kwargs)
    assert np.array_equal(first.draws, second.draws)
    assert np.array_equal(first.latent_states, second.latent_states)
    assert first.receipt == second.receipt
    zero = sample_l2_team_role_jump_bank_v1(
        **{**kwargs, "role_jump_probabilities": (0.0, 0.0, 0.0, 0.0)}
    )
    assert np.array_equal(zero.draws, ordinary)
    assert np.all(zero.latent_states == -1)


def test_l2_rejects_impossible_team_probability_and_receipt_tampering():
    players, worlds, _, _ = _axes()
    draws = np.zeros((4, len(worlds)))
    with pytest.raises(BeliefLawChallengerError, match="exceed one"):
        sample_l2_team_role_jump_bank_v1(
            ordinary_draws=draws,
            role_jump_draws=draws,
            player_ids=players,
            world_ids=worlds,
            team_ids=("A", "A", "B", "B"),
            role_jump_probabilities=(0.7, 0.4, 0.0, 0.0),
            seed=1,
            calibration_id="calibration-v1",
            source_identities={"components": _identity("components")},
        )
    valid = sample_l2_team_role_jump_bank_v1(
        ordinary_draws=draws,
        role_jump_draws=draws + 1.0,
        player_ids=players,
        world_ids=worlds,
        team_ids=("A", "A", "B", "B"),
        role_jump_probabilities=(0.1, 0.1, 0.1, 0.1),
        seed=1,
        calibration_id="calibration-v1",
        source_identities={"components": _identity("components")},
    )
    tampered = deepcopy(valid.receipt)
    tampered["seed"] = 2
    with pytest.raises(BeliefLawChallengerError, match="content hash"):
        validate_challenger_receipt(tampered)
