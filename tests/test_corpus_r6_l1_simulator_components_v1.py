from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.models.components import COMPONENT_NAMES
from nfl_dfs.research.corpus_r6_belief_law_challengers_v1 import (
    sample_l1_shootout_regime_bank_v1,
)
from nfl_dfs.research.corpus_r6_l1_simulator_components_v1 import (
    L1ComponentError,
    SHOOTOUT_ENVIRONMENT,
    build_l1_simulator_components_v1,
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
