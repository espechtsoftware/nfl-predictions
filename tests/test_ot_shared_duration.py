"""OT shared-duration mixture (S2 v2): exact marginal preservation,
determinism, co-movement increase, constant-row and cross-game
invariance, and fail-closed validation."""
import numpy as np
import pytest

from nfl_dfs.research.ot_shared_duration import (
    OtMixtureError,
    apply_ot_duration_mixture,
    assert_marginals_preserved,
    same_game_comovement,
)


def _slate(n_worlds=4000, seed=5):
    rng = np.random.default_rng(seed)
    # Two games of four players each plus one constant (DST-like) row per
    # game and one row with no game key.
    draws = rng.gamma(2.0, 5.0, size=(11, n_worlds))
    draws[4] = 7.0                      # constant row, game A
    draws[9] = 6.0                      # constant row, game B
    game_ids = ["A"] * 5 + ["B"] * 5 + [None]
    return draws, game_ids


def test_marginals_preserved_exactly():
    draws, game_ids = _slate()
    mixed, flags = apply_ot_duration_mixture(draws, game_ids)
    assert assert_marginals_preserved(draws, mixed) == 0.0
    assert set(flags) == {"A", "B"}
    assert 0 < flags["A"].sum() < len(flags["A"])


def test_constant_and_keyless_rows_are_byte_identical():
    draws, game_ids = _slate()
    mixed, _ = apply_ot_duration_mixture(draws, game_ids)
    np.testing.assert_array_equal(mixed[4], draws[4])
    np.testing.assert_array_equal(mixed[9], draws[9])
    np.testing.assert_array_equal(mixed[10], draws[10])


def test_zero_probability_is_identity():
    draws, game_ids = _slate()
    mixed, flags = apply_ot_duration_mixture(draws, game_ids, p_ot=0.0)
    np.testing.assert_array_equal(mixed, draws)
    assert not flags["A"].any() and not flags["B"].any()


def test_deterministic_across_calls():
    draws, game_ids = _slate()
    first, f1 = apply_ot_duration_mixture(draws, game_ids)
    second, f2 = apply_ot_duration_mixture(draws, game_ids)
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(f1["A"], f2["A"])


def test_same_game_comovement_rises():
    draws, game_ids = _slate()
    mixed, _ = apply_ot_duration_mixture(draws, game_ids, p_ot=0.08)
    before = same_game_comovement(draws, game_ids)
    after = same_game_comovement(mixed, game_ids)
    assert after > before + 0.01, (before, after)


def test_flagged_worlds_land_in_the_upper_tail_together():
    draws, game_ids = _slate()
    mixed, flags = apply_ot_duration_mixture(draws, game_ids)
    flagged = flags["A"]
    # Game-A variance players' summed score in flagged worlds must sit
    # well above their unflagged mean — the co-boom the law was missing.
    team = mixed[[0, 1, 2, 3]].sum(axis=0)
    assert team[flagged].mean() > team[~flagged].mean() + team.std()


def test_fail_closed_validation():
    draws, game_ids = _slate()
    with pytest.raises(OtMixtureError):
        apply_ot_duration_mixture(draws, game_ids[:-1])
    with pytest.raises(OtMixtureError):
        apply_ot_duration_mixture(draws, game_ids, p_ot=1.0)
    with pytest.raises(OtMixtureError):
        apply_ot_duration_mixture(draws, game_ids, kappa=0.0)
    bad = draws.copy()
    bad[0, 0] = np.nan
    with pytest.raises(OtMixtureError):
        apply_ot_duration_mixture(bad, game_ids)
    with pytest.raises(OtMixtureError):
        assert_marginals_preserved(draws, draws + 0.5)
