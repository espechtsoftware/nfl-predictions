from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research.corpus_r6_belief_law_challengers_v1 import (
    sample_l2_team_role_jump_bank_v1,
)
from nfl_dfs.research.corpus_r6_l2_role_jump_components_v1 import (
    L2ComponentError,
    build_l2_role_jump_components_v1,
    validate_l2_role_jump_component_receipt,
)


def _identity() -> dict[str, object]:
    return {
        "uri": "gs://bucket/calibration.json",
        "generation": "42",
        "sha256": "c" * 64,
        "bytes": 1200,
    }


def _kwargs() -> dict[str, object]:
    return {
        "ordinary_draws": np.arange(4 * 128, dtype=float).reshape(4, 128),
        "player_ids": ("p0", "p1", "p2", "p3"),
        "empirical_group_by_player": ("WR:rise", "WR:rise", "RB:rise", "RB:rise"),
        "residual_samples_by_group": {
            "WR:rise": np.linspace(-2.0, 18.0, 40),
            "RB:rise": np.linspace(-4.0, 24.0, 40),
        },
        "calibration_source_identity": _identity(),
        "base_seed": 99,
        "minimum_group_support": 30,
    }


def test_l2_empirical_component_is_deterministic_and_group_conditional():
    first = build_l2_role_jump_components_v1(**_kwargs())
    second = build_l2_role_jump_components_v1(**_kwargs())
    assert first.role_jump_draws.shape == (4, 128)
    assert np.array_equal(first.role_jump_draws, second.role_jump_draws)
    assert np.array_equal(first.sampled_residuals, second.sampled_residuals)
    assert first.receipt == second.receipt
    assert np.array_equal(
        first.role_jump_draws,
        _kwargs()["ordinary_draws"] + first.sampled_residuals,
    )
    wr_support = set(_kwargs()["residual_samples_by_group"]["WR:rise"])
    rb_support = set(_kwargs()["residual_samples_by_group"]["RB:rise"])
    assert set(first.sampled_residuals[0]) <= wr_support
    assert set(first.sampled_residuals[2]) <= rb_support
    assert first.receipt["derived_historical_player_residuals_consumed"] is True
    assert first.receipt["calibration_artifact_content_validated_here"] is False
    assert validate_l2_role_jump_component_receipt(first.receipt) == first.receipt


def test_l2_empirical_component_feeds_team_exclusive_mixture():
    components = build_l2_role_jump_components_v1(**_kwargs())
    ordinary = _kwargs()["ordinary_draws"]
    bank = sample_l2_team_role_jump_bank_v1(
        ordinary_draws=ordinary,
        role_jump_draws=components.role_jump_draws,
        player_ids=("p0", "p1", "p2", "p3"),
        world_ids=tuple(f"w{i}" for i in range(128)),
        team_ids=("A", "A", "B", "B"),
        role_jump_probabilities=(0.10, 0.15, 0.20, 0.25),
        seed=100,
        calibration_id="cal19-wf21-hold22-v1",
        source_identities={"calibration": _identity()},
    )
    changed = bank.draws != ordinary
    assert np.all(changed[:2].sum(axis=0) <= 1)
    assert np.all(changed[2:].sum(axis=0) <= 1)
    assert bank.receipt["mechanism"]["maximum_role_jumps_per_team_world"] == 1
    assert bank.receipt["uses_lineup_outcomes"] is False


def test_l2_component_rejects_missing_support_nonjump_and_tampering():
    kwargs = _kwargs()
    with pytest.raises(L2ComponentError, match="every and only"):
        build_l2_role_jump_components_v1(
            **{
                **kwargs,
                "residual_samples_by_group": {
                    "WR:rise": kwargs["residual_samples_by_group"]["WR:rise"]
                },
            }
        )
    with pytest.raises(L2ComponentError, match="positive jump"):
        build_l2_role_jump_components_v1(
            **{
                **kwargs,
                "residual_samples_by_group": {
                    **kwargs["residual_samples_by_group"],
                    "WR:rise": np.linspace(-20.0, -1.0, 40),
                },
            }
        )
    valid = build_l2_role_jump_components_v1(**kwargs)
    tampered = deepcopy(valid.receipt)
    tampered["base_seed"] = 100
    with pytest.raises(L2ComponentError, match="content hash"):
        validate_l2_role_jump_component_receipt(tampered)
