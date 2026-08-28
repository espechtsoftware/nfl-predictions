from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.backtest.replay import (
    apply_draw_shape,
    apply_served_position_scales,
    apply_served_tail_scale,
)
from nfl_dfs.models.blend import (
    blend,
    effective_model_weight,
    shift_draws_to_means,
)
from nfl_dfs.models.components import COMPONENT_NAMES
from nfl_dfs.research.corpus_r6_belief_law_challengers_v1 import (
    sample_l1_shootout_regime_bank_v1,
)
from nfl_dfs.research.corpus_r6_l1_simulator_components_v1 import (
    L1ComponentError,
    SHOOTOUT_ENVIRONMENT,
    build_l1_simulator_components_v1,
    build_l1_served_components_v1,
    validate_l1_served_component_receipt,
    validate_l1_simulator_component_receipt,
)


def _components() -> pd.DataFrame:
    rows = []
    for team in ("A", "B"):
        rows.append({
            "targets": 0.0,
            "catch_rate": 0.0,
            "ypr": 0.0,
            "rec_tds": 0.0,
            "carries": 4.0,
            "ypc": 4.5,
            "rush_tds": 0.15,
            "pass_attempts": 34.0,
            "ypa": 7.3,
            "pass_tds": 1.8,
            "interceptions": 0.7,
        })
        for targets in (9.0, 6.0):
            rows.append({
                "targets": targets,
                "catch_rate": 0.66,
                "ypr": 11.5,
                "rec_tds": 0.45,
                "carries": 0.0,
                "ypc": 0.0,
                "rush_tds": 0.0,
                "pass_attempts": 0.0,
                "ypa": 0.0,
                "pass_tds": 0.0,
                "interceptions": 0.0,
            })
    return pd.DataFrame(rows, columns=COMPONENT_NAMES)


def _identity() -> dict[str, object]:
    return {
        "uri": "gs://bucket/components.json",
        "generation": "12",
        "sha256": "b" * 64,
        "bytes": 999,
    }


def _kwargs() -> dict[str, object]:
    components = _components()
    return {
        "components": components,
        "game_ids": ["g0"] * len(components),
        "team_ids": ["A"] * 3 + ["B"] * 3,
        "game_totals": [48.0] * len(components),
        "n_sims": 500,
        "base_seed": 41,
        "ordinary_environment": ADOPTED_CLASSIC_POLICY.engine_environment(),
        "source_identities": {"components": _identity()},
        "usage_dirichlet_k": 8.0,
        "td_allocation_k": 12.0,
    }


def test_l1_component_adapter_is_deterministic_and_mechanism_distinct():
    first = build_l1_simulator_components_v1(**_kwargs())
    second = build_l1_simulator_components_v1(**_kwargs())
    assert first.ordinary_draws.shape == (6, 500)
    assert first.shootout_draws.shape == (6, 500)
    assert np.array_equal(first.ordinary_draws, second.ordinary_draws)
    assert np.array_equal(first.shootout_draws, second.shootout_draws)
    assert not np.array_equal(first.ordinary_draws, first.shootout_draws)
    assert first.receipt == second.receipt
    for key, value in SHOOTOUT_ENVIRONMENT.items():
        assert first.receipt["shootout_environment"][key] == value
    assert first.receipt["ordinary_environment"]["GAME_SIM_TEAM_FACTORS"] == "1"
    assert validate_l1_simulator_component_receipt(first.receipt) == first.receipt


def test_l1_components_feed_the_game_wide_mixture_without_outcomes():
    components = build_l1_simulator_components_v1(**_kwargs())
    player_ids = tuple(f"p{i}" for i in range(6))
    world_ids = tuple(f"w{i}" for i in range(500))
    bank = sample_l1_shootout_regime_bank_v1(
        ordinary_draws=components.ordinary_draws,
        shootout_draws=components.shootout_draws,
        player_ids=player_ids,
        world_ids=world_ids,
        game_ids=("g0",) * 6,
        team_ids=("A",) * 3 + ("B",) * 3,
        shootout_probability_by_game={"g0": 0.25},
        seed=70,
        calibration_id="unfitted-smoke-v1",
        source_identities={"components": _identity()},
    )
    assert bank.draws.shape == (6, 500)
    assert 0 < int(bank.latent_states.sum()) < 500
    assert bank.receipt["calibrated_model_claimed"] is False
    assert bank.receipt["uses_lineup_outcomes"] is False


def test_l1_component_adapter_rejects_wrong_surface_and_receipt_tampering():
    kwargs = _kwargs()
    with pytest.raises(L1ComponentError, match="columns or order"):
        build_l1_simulator_components_v1(
            **{**kwargs, "components": kwargs["components"].iloc[:, ::-1]}
        )
    with pytest.raises(L1ComponentError, match="exactly two"):
        build_l1_simulator_components_v1(
            **{**kwargs, "team_ids": ["A"] * 6}
        )
    valid = build_l1_simulator_components_v1(**kwargs)
    changed = deepcopy(valid.receipt)
    changed["usage_dirichlet_k"] = 9.0
    with pytest.raises(L1ComponentError, match="content hash"):
        validate_l1_simulator_component_receipt(changed)


def _served_environment() -> dict[str, str]:
    environment = ADOPTED_CLASSIC_POLICY.engine_environment()
    environment.update({
        "SERVED_TAIL_SCALE": "1.10",
        "SERVED_POSITION_SCALES": "QB:0.97,RB:1.01,TE:0.94,WR:1.07",
    })
    return environment


def _served_fixture(*, two_games: bool = False) -> dict[str, object]:
    components = _components()
    game_ids = ["g0"] * len(components)
    team_ids = ["A"] * 3 + ["B"] * 3
    if two_games:
        components = pd.concat([components, _components()], ignore_index=True)
        game_ids += ["g1"] * 6
        team_ids += ["C"] * 3 + ["D"] * 3
    environment = _served_environment()
    projection_seed = 314
    component_banks = build_l1_simulator_components_v1(
        components=components,
        game_ids=game_ids,
        team_ids=team_ids,
        game_totals=[48.0] * len(components),
        n_sims=500,
        base_seed=projection_seed,
        ordinary_environment=environment,
        source_identities={"components": _identity()},
        usage_dirichlet_k=8.0,
        td_allocation_k=12.0,
        paired_projection_seed=projection_seed,
    )
    positions = tuple(
        value for _ in range(2 if two_games else 1)
        for value in ("QB", "WR", "WR", "QB", "WR", "WR")
    )
    keys = pd.DataFrame({
        "season": [2019] * len(components),
        "week": [1] * len(components),
        "gsis_id": [f"p{index}" for index in range(len(components))],
        "is_rookie": [False] * len(components),
    })
    tabpfn_cache = keys[["season", "week", "gsis_id"]].copy()
    for quantile, value in (
        ("q01", 0.0), ("q10", 2.0), ("q50", 10.0),
        ("q90", 25.0), ("q99", 40.0),
    ):
        tabpfn_cache[quantile] = [
            value + 0.1 * index for index in range(len(components))
        ]
    market = np.asarray([
        np.nan if index % 3 == 0 else 11.0 + index
        for index in range(len(components))
    ])
    shaped = apply_draw_shape(
        component_banks.ordinary_draws,
        pd.Series(positions),
        projection_seed,
        keys=keys,
        env=environment,
        tabpfn_cache_rows=tabpfn_cache,
    ).astype(np.float32)
    target = blend(
        shaped.mean(axis=1, dtype=np.float64),
        market,
        effective_model_weight(environment),
    )
    authority = shift_draws_to_means(shaped, target)
    authority = apply_served_tail_scale(
        authority, pd.Series(positions), env=environment
    )
    authority = apply_served_position_scales(
        authority, pd.Series(positions), env=environment
    ).astype(np.float32)
    return {
        "component_banks": component_banks,
        "ordinary_served_authority": authority,
        "positions": positions,
        "player_keys": keys,
        "market_points": market,
        "projection_seed": projection_seed,
        "served_environment": environment,
        "tabpfn_cache_rows": tabpfn_cache,
        "source_identities": {
            "components": _identity(),
            "ordinary_worlds": {
                "uri": "gs://bucket/ordinary.npz",
                "generation": "23",
                "sha256": "c" * 64,
                "bytes": 20_000,
            },
        },
        "game_ids": tuple(game_ids),
        "team_ids": tuple(team_ids),
    }


def test_l1_served_adapter_has_exact_zero_weight_parity_and_selective_change():
    fixture = _served_fixture(two_games=True)
    game_ids = fixture.pop("game_ids")
    team_ids = fixture.pop("team_ids")
    served = build_l1_served_components_v1(**fixture)
    authority = fixture["ordinary_served_authority"]
    assert served.ordinary_draws.dtype == np.float32
    assert served.ordinary_draws.tobytes() == authority.tobytes()
    assert not np.array_equal(served.shootout_draws, served.ordinary_draws)
    assert validate_l1_served_component_receipt(served.receipt) == served.receipt

    player_ids = tuple(f"p{index}" for index in range(len(game_ids)))
    world_ids = tuple(f"w{index}" for index in range(500))
    zero = sample_l1_shootout_regime_bank_v1(
        ordinary_draws=served.ordinary_draws,
        shootout_draws=served.shootout_draws,
        player_ids=player_ids,
        world_ids=world_ids,
        game_ids=game_ids,
        team_ids=team_ids,
        shootout_probability_by_game={"g0": 0.0, "g1": 0.0},
        seed=99,
        calibration_id="zero-parity",
        source_identities={"served": _identity()},
    )
    assert np.array_equal(zero.draws, authority)

    selective = sample_l1_shootout_regime_bank_v1(
        ordinary_draws=served.ordinary_draws,
        shootout_draws=served.shootout_draws,
        player_ids=player_ids,
        world_ids=world_ids,
        game_ids=game_ids,
        team_ids=team_ids,
        shootout_probability_by_game={"g0": 1.0, "g1": 0.0},
        seed=99,
        calibration_id="selective-change",
        source_identities={"served": _identity()},
    )
    assert np.array_equal(selective.draws[:6], served.shootout_draws[:6])
    assert np.array_equal(selective.draws[6:], authority[6:])


def test_l1_served_adapter_rejects_raw_or_partially_served_authority():
    fixture = _served_fixture()
    fixture.pop("game_ids")
    fixture.pop("team_ids")
    raw_proxy = fixture["component_banks"].ordinary_draws.astype(np.float32)
    with pytest.raises(L1ComponentError, match="final-served reconstruction"):
        build_l1_served_components_v1(
            **{**fixture, "ordinary_served_authority": raw_proxy}
        )

    shifted_only = apply_draw_shape(
        fixture["component_banks"].ordinary_draws,
        pd.Series(fixture["positions"]),
        fixture["projection_seed"],
        keys=fixture["player_keys"],
        env=fixture["served_environment"],
        tabpfn_cache_rows=fixture["tabpfn_cache_rows"],
    ).astype(np.float32)
    with pytest.raises(L1ComponentError, match="final-served reconstruction"):
        build_l1_served_components_v1(
            **{**fixture, "ordinary_served_authority": shifted_only}
        )


def test_l1_served_adapter_rejects_unpaired_seed_and_implicit_tabpfn_read():
    fixture = _served_fixture()
    fixture.pop("game_ids")
    fixture.pop("team_ids")
    unpaired = build_l1_simulator_components_v1(**_kwargs())
    with pytest.raises(L1ComponentError, match="exact projection seed"):
        build_l1_served_components_v1(
            **{**fixture, "component_banks": unpaired}
        )

    with pytest.raises(L1ComponentError, match="explicit frozen cache"):
        build_l1_served_components_v1(
            **{
                **fixture,
                "tabpfn_cache_rows": None,
            }
        )
