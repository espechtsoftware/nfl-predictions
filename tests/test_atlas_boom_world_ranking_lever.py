"""ATLAS_BOOM_WORLD_RANKING lever: default parity, treatment order, and
self-identification (protocol 20260818-atlas-minimal-world-selection-c-v1).

The C test's validity rests on three properties tested here offline:
the default path is byte-identical to the incumbent argsort ranking, the
treatment path equals rank_worlds(roster_slot_upper_bound(...)) with the
deterministic world-id tiebreak, and the lever key is in the immutable
recorded lever set so a treatment arm is self-identifying in BQ (the
EXTRA_FEATURES omission lesson, 2026-08-06).
"""

import inspect

import numpy as np

from nfl_dfs.analysis.atlas_world_ranking import (
    rank_worlds,
    roster_slot_upper_bound,
)
from nfl_dfs.backtest import engine


def _synthetic_rd(seed: int = 7, rows: int = 24, worlds: int = 50):
    rng = np.random.default_rng(seed)
    rd = rng.gamma(2.0, 6.0, size=(rows, worlds))
    positions = (
        ["QB"] * 3 + ["RB"] * 6 + ["WR"] * 9 + ["TE"] * 4 + ["DST"] * 2
    )
    assert len(positions) == rows
    return rd, positions


def test_default_is_incumbent_argsort_order():
    rd, positions = _synthetic_rd()
    order = engine._boom_world_order(rd, positions, {})
    expected = np.argsort(rd.sum(axis=0))[::-1]
    np.testing.assert_array_equal(order, expected)


def test_empty_lever_value_is_control():
    rd, positions = _synthetic_rd()
    order = engine._boom_world_order(
        rd, positions, {"ATLAS_BOOM_WORLD_RANKING": ""})
    expected = np.argsort(rd.sum(axis=0))[::-1]
    np.testing.assert_array_equal(order, expected)


def test_treatment_is_roster_bound_rank_worlds():
    rd, positions = _synthetic_rd()
    order = engine._boom_world_order(
        rd, positions, {"ATLAS_BOOM_WORLD_RANKING": "1"})
    expected = rank_worlds(
        roster_slot_upper_bound(rd, positions), rd.shape[1])
    np.testing.assert_array_equal(order, expected)
    # Complete permutation of the world book, not a truncation.
    assert sorted(order.tolist()) == list(range(rd.shape[1]))


def test_treatment_differs_from_control_on_generic_draws():
    rd, positions = _synthetic_rd()
    control = engine._boom_world_order(rd, positions, {})
    treatment = engine._boom_world_order(
        rd, positions, {"ATLAS_BOOM_WORLD_RANKING": "1"})
    assert not np.array_equal(control, treatment)


def test_treatment_tiebreak_is_world_id():
    # Constant draws make every world tie; the treatment order must fall
    # back to ascending world id, deterministically.
    rd = np.full((24, 10), 5.0)
    _, positions = _synthetic_rd()
    order = engine._boom_world_order(
        rd, positions, {"ATLAS_BOOM_WORLD_RANKING": "1"})
    np.testing.assert_array_equal(order, np.arange(10))


def test_lever_key_is_recorded_in_immutable_lever_set():
    source = inspect.getsource(engine)
    lever_block = source.split("_lever_keys = {", 1)[1].split("}", 1)[0]
    assert '"ATLAS_BOOM_WORLD_RANKING"' in lever_block


def test_production_policy_does_not_set_the_lever():
    from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
    env = ADOPTED_CLASSIC_POLICY.public_identity()[
        "engine_environment_receipt"]["values"]
    assert "ATLAS_BOOM_WORLD_RANKING" not in env
