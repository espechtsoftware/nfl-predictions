import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research import sis_asoe_final_served as final
from nfl_dfs.models import simulate


def test_rank_transport_preserves_each_control_multiset_and_treatment_order():
    control = np.array([[4.0, 1.0, 3.0, 2.0], [9.0, 7.0, 8.0, 6.0]])
    treatment = np.array([[0.2, 0.4, 0.1, 0.3], [3.0, 1.0, 4.0, 2.0]])
    out = final.rank_transport(control, treatment)
    np.testing.assert_array_equal(np.sort(out, axis=1), np.sort(control, axis=1))
    np.testing.assert_array_equal(
        np.argsort(out, axis=1, kind="stable"),
        np.argsort(treatment, axis=1, kind="stable"),
    )


def test_asoe_multiplier_uses_supported_game_team_and_falls_back_elsewhere():
    rows = pd.DataFrame({
        "season": [2023, 2023, 2023, 2023],
        "week": [5, 5, 4, 4],
        "game_id": ["g5", "g5", "g4", "g4"],
        "team": ["A", "A", "A", "A"],
        "opponent": ["B", "B", "C", "C"],
        "gsis_id": ["p1", "p2", "p1", "p2"],
    })
    comps = pd.DataFrame({"targets": [8.0, 2.0, 7.0, 3.0]})
    player = pd.DataFrame({
        "season": [2023, 2023], "target_week": [5, 5],
        "team": ["A", "A"], "gsis_id": ["p1", "p2"],
        "alignment_supported": [True, True],
        "player_wide_share": [0.9, 0.1],
    })
    offense = pd.DataFrame({
        "season": [2023], "target_week": [5], "team": ["A"],
        "offense_alignment_supported": [True], "offense_wide_share": [0.5],
    })
    defense = pd.DataFrame({
        "season": [2023], "target_week": [5], "defense": ["B"],
        "asoe_supported": [True], "defense_asoe": [0.2],
    })
    multipliers, audit = final.build_target_allocation_multipliers(
        rows, comps, player, offense, defense, beta=1.0
    )
    assert multipliers[0] > 1.0
    assert multipliers[1] < 1.0
    np.testing.assert_array_equal(multipliers[2:], [1.0, 1.0])
    p = np.array([0.8, 0.2])
    assert np.dot(p, multipliers[:2]) == pytest.approx(1.0)
    assert audit["eligible_units"] == 1
    assert audit["supported_units"] == audit["changed_units"] == 1


def test_treatment_env_binds_exact_frozen_beta():
    assert not final.treatment_enabled({})
    assert final.treatment_enabled({final.ENV_FLAG: "1"})
    with pytest.raises(ValueError, match="frozen beta"):
        final.treatment_enabled({final.ENV_FLAG: "1", final.ENV_BETA: "0.1"})


def test_target_receiving_delta_does_not_import_unrelated_treatment_rng():
    comps = pd.DataFrame({
        "targets": [8.0, 2.0], "catch_rate": [0.65, 0.65],
        "ypr": [11.0, 11.0], "rec_tds": [0.3, 0.3],
        "carries": [3.0, 3.0], "ypc": [4.0, 4.0],
        "rush_tds": [0.2, 0.2], "pass_attempts": [0.0, 0.0],
        "ypa": [0.0, 0.0], "pass_tds": [0.0, 0.0],
        "interceptions": [0.0, 0.0],
    })
    ids = {
        "game_ids": pd.Series(["g", "g"]),
        "team_ids": pd.Series(["A", "A"]),
    }
    control = simulate.simulate(
        comps, n_sims=500, seed=4, keep_draws=True,
        keep_target_receiving=True, **ids,
    )
    same = simulate.simulate(
        comps, n_sims=500, seed=4, keep_target_receiving=True,
        target_allocation_multipliers=np.ones(2), **ids,
    )
    np.testing.assert_array_equal(
        control.target_receiving_draws, same.target_receiving_draws
    )
    composed = (
        control.draws - control.target_receiving_draws
        + same.target_receiving_draws
    )
    np.testing.assert_allclose(composed, control.draws, rtol=0, atol=2e-15)


def test_fallback_rows_can_remain_bit_exact_without_arithmetic_round_trip():
    control = np.array([[1.0, 1.0, 2.0], [3.0, 4.0, 5.0]])
    control_receiving = np.array([[0.1, 0.1, 0.2], [0.3, 0.4, 0.5]])
    treatment_receiving = control_receiving.copy()
    changed = np.array([False, True])
    composed = control.copy()
    composed[changed] = (
        control[changed] - control_receiving[changed]
        + treatment_receiving[changed]
    )
    np.testing.assert_array_equal(composed[~changed], control[~changed])


def test_live_multiplier_explicitly_admits_2026(monkeypatch):
    rows = pd.DataFrame({
        "season": [2026, 2026], "week": [5, 5],
        "game_id": ["g", "g"], "team": ["A", "A"],
        "opponent": ["B", "B"], "gsis_id": ["p1", "p2"],
    })
    comps = pd.DataFrame({"targets": [8.0, 2.0]})
    player = pd.DataFrame({
        "season": [2026, 2026], "target_week": [5, 5],
        "team": ["A", "A"], "gsis_id": ["p1", "p2"],
        "alignment_supported": [True, True],
        "player_wide_share": [0.9, 0.1],
    })
    offense = pd.DataFrame({
        "season": [2026], "target_week": [5], "team": ["A"],
        "offense_alignment_supported": [True],
        "offense_wide_share": [0.5],
    })
    defense = pd.DataFrame({
        "season": [2026], "target_week": [5], "defense": ["B"],
        "asoe_supported": [True], "defense_asoe": [0.2],
    })
    monkeypatch.setattr(
        final, "load_live_sources",
        lambda season, week: (
            player, offense, defense, {"season": season, "target_week": week},
        ),
    )
    multipliers, audit = final.live_target_allocation_multipliers(rows, comps)
    assert multipliers[0] > 1
    assert multipliers[1] < 1
    assert audit["prospective"] is True
