import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import served_position_calibration as position_calibration
from nfl_dfs.backtest.replay import (
    _stable_ordinal_ranks,
    _widen_draws,
    apply_served_position_scales,
)
from nfl_dfs.inference import live_lineups
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY


FROZEN_SPEC = "QB:0.970,RB:1.005,TE:0.940,WR:1.070"


def test_runtime_position_scales_are_mean_invariant_and_position_specific():
    draws = np.array([
        [0.0, 2.0, 4.0, 10.0],
        [1.0, 3.0, 7.0, 9.0],
        [2.0, 5.0, 6.0, 11.0],
        [0.0, 1.0, 8.0, 12.0],
        [4.0, 5.0, 6.0, 7.0],
    ])
    positions = pd.Series(["QB", "RB", "TE", "WR", "DST"])
    out = apply_served_position_scales(
        draws, positions, env={"SERVED_POSITION_SCALES": FROZEN_SPEC})
    assert out.mean(axis=1) == pytest.approx(draws.mean(axis=1), abs=1e-12)
    for row, factor in enumerate((0.970, 1.005, 0.940, 1.070)):
        assert np.ptp(out[row]) == pytest.approx(factor * np.ptp(draws[row]))
    assert out[4].tolist() == draws[4].tolist()


@pytest.mark.parametrize("identity", ["", "0", "off", "false", "identity", "none"])
def test_runtime_position_scale_identity(identity):
    draws = np.arange(12, dtype=float).reshape(3, 4)
    assert apply_served_position_scales(
        draws, pd.Series(["QB", "RB", "WR"]),
        env={"SERVED_POSITION_SCALES": identity},
    ) is draws


@pytest.mark.parametrize("spec, message", [
    ("QB:1,RB:1,TE:1", "exactly once"),
    ("QB:1,RB:1,TE:1,WR:1,QB:1", "expected"),
    ("QB:1,RB:1,TE:1,WR:1.51", r"\[0.75, 1.50\]"),
    ("QB:1,RB:nope,TE:1,WR:1", "expected"),
])
def test_runtime_position_scale_contract(spec, message):
    with pytest.raises(ValueError, match=message):
        apply_served_position_scales(
            np.arange(16, dtype=float).reshape(4, 4),
            pd.Series(["QB", "RB", "TE", "WR"]),
            env={"SERVED_POSITION_SCALES": spec},
        )


def test_live_path_applies_position_scale_after_market_and_global_scale():
    import inspect

    source = inspect.getsource(live_lineups.build_slate_with_draws)
    shift = source.index("draws = shift_draws_to_means")
    global_scale = source.index("draws = apply_served_tail_scale")
    position_scale = source.index("draws = apply_served_position_scales")
    assert shift < global_scale < position_scale


def test_production_policy_pins_position_scale_identity():
    env = ADOPTED_CLASSIC_POLICY.engine_environment({
        "SERVED_POSITION_SCALES": FROZEN_SPEC,
    })
    assert env["SERVED_POSITION_SCALES"] == ""


def test_position_scales_are_mean_invariant_and_support_narrowing():
    draws = np.array([
        [0.0, 2.0, 4.0, 10.0],
        [1.0, 3.0, 7.0, 9.0],
        [2.0, 5.0, 6.0, 11.0],
        [0.0, 1.0, 8.0, 12.0],
    ])
    positions = pd.Series(["QB", "RB", "WR", "TE"])
    factors = {"QB": 1.0, "RB": 1.1, "WR": 1.2, "TE": 0.8}
    out = position_calibration.apply_position_scales(draws, positions, factors)
    assert out.mean(axis=1) == pytest.approx(draws.mean(axis=1), abs=1e-12)
    assert np.ptp(out[0]) == pytest.approx(np.ptp(draws[0]))
    assert np.ptp(out[2]) == pytest.approx(1.2 * np.ptp(draws[2]))
    assert np.ptp(out[3]) == pytest.approx(0.8 * np.ptp(draws[3]))


def test_position_scales_require_exact_contract_and_bounds():
    draws = np.arange(24, dtype=float).reshape(4, 6)
    positions = pd.Series(["QB", "RB", "WR", "TE"])
    with pytest.raises(ValueError, match="exactly"):
        position_calibration.apply_position_scales(
            draws, positions, {"QB": 1, "RB": 1, "WR": 1})
    with pytest.raises(ValueError, match=r"\[0.75, 1.50\]"):
        position_calibration.apply_position_scales(
            draws, positions, {"QB": 1, "RB": 1, "WR": 1.51, "TE": 1})


def test_upstream_positive_widening_preserves_tabpfn_rank_input():
    draws = np.array([
        [1.0, 4.0, 2.0, 9.0, 3.0],
        [7.0, 2.0, 5.0, 1.0, 8.0],
    ])
    positions = pd.Series(["WR", "TE"])
    widened = _widen_draws(draws, positions, "WR:1.4,TE:0.8")
    for source, treatment in zip(draws, widened):
        assert _stable_ordinal_ranks(source).tolist() == \
            _stable_ordinal_ranks(treatment).tolist()


def _fold(season: int) -> tuple[pd.DataFrame, np.ndarray]:
    rows = []
    draws = []
    offsets = np.linspace(-4.0, 4.0, 1000)
    for position_index, position in enumerate(position_calibration.POSITIONS):
        for index in range(60):
            mean = 10.0 + position_index + index / 20
            rows.append({
                "season": season,
                "week": index // 6 + 1,
                "gsis_id": f"{season}-{position}-{index}",
                "position": position,
                "market_covered": True,
                "tabpfn_covered": True,
                "actual": mean + (6.0 if index >= 54 else 0.0),
            })
            draws.append(mean + offsets)
    return pd.DataFrame(rows), np.asarray(draws)


def test_fit_position_scales_uses_frozen_grid_and_all_seasons():
    folds = {season: _fold(season) for season in (2019, 2021, 2022)}
    fit = position_calibration.fit_position_scales(folds)
    assert set(fit["factors"]) == set(position_calibration.POSITIONS)
    assert all(
        factor in position_calibration.POSITION_SCALE_GRID
        for factor in fit["factors"].values()
    )
    assert all(
        len(fit["positions"][position]["curve"]) == 151
        for position in position_calibration.POSITIONS
    )
    with pytest.raises(ValueError, match="all calibration seasons"):
        position_calibration.fit_position_scales({2019: folds[2019]})


def test_position_calibration_gate_matches_frozen_requirements():
    def summary(gap: float, wr99: float, te99: float) -> dict:
        positions = {}
        for position in position_calibration.POSITIONS:
            positions[position] = {
                "q90_calibration_gap": gap,
                "q95_calibration_gap": gap,
                "q99_calibration_gap": (
                    wr99 if position == "WR" else te99 if position == "TE" else gap
                ),
            }
        return {
            "positions": positions,
            "crps": 2.0,
            "brier_20": 0.05,
            "brier_30": 0.02,
        }

    source = summary(0.02, 0.009, -0.003)
    treatment = summary(0.015, 0.006, -0.002)
    ratios = {
        "mean_ratio": 1.0,
        "position_mean_ratios": {
            position: 1.0 for position in position_calibration.POSITIONS
        },
    }
    gate = position_calibration.position_calibration_gate(
        {"QB": 1.0, "RB": 1.0, "WR": 1.1, "TE": 0.9},
        source, treatment, ratios, 1e-10,
    )
    assert gate["passes"]
    treatment["positions"]["TE"]["q99_calibration_gap"] = -0.004
    assert not position_calibration.position_calibration_gate(
        {"QB": 1.0, "RB": 1.0, "WR": 1.1, "TE": 0.9},
        source, treatment, ratios, 1e-10,
    )["passes"]
