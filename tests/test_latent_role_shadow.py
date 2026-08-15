import types

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.inference import latent_role_shadow as shadow
from nfl_dfs.research.latent_role_state import (
    INPUT_FEATURES,
    STATES,
    JointRoleStateWorld,
    LatentRoleStateError,
)


def _feature_rows():
    positions = ["RB", "WR", "TE", "WR", "RB", "WR", "TE", "WR"]
    rows = []
    for index, position in enumerate(positions):
        row = {
            "gsis_id": f"p{index}",
            "position": position,
            "team": f"T{index}",
            "status": "None",
            "season": 2026,
            "week": 1,
            "game_id": f"G{index // 2}",
            "game_total": 45.0,
            "salary": 5_000,
            "is_rookie": False,
        }
        for name in INPUT_FEATURES:
            if name in {"position", "previous_state", "injury_status"}:
                continue
            row[name] = 0.1
        row["injury_status"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def _slate():
    features = _feature_rows()
    rows = []
    for index, item in enumerate(features.itertuples(index=False)):
        rows.append({
            "id": index,
            "gsis_id": item.gsis_id,
            "pos": item.position,
            "team": item.team,
            "salary": 5_000,
            "season": 2026,
            "week": 1,
            "proj": 12.0,
            "proj_tourney": 11.8,
            "market_points": 11.0,
        })
    rows.append({
        "id": 99,
        "gsis_id": "",
        "pos": "DST",
        "team": "DST",
        "salary": 3_000,
        "season": 2026,
        "week": 1,
        "proj": 6.0,
        "proj_tourney": 5.9,
        "market_points": np.nan,
    })
    return pd.DataFrame(rows)


def test_live_transition_rows_use_within_season_previous_state_and_pit_injury():
    features = _feature_rows()
    history = pd.DataFrame({
        "gsis_id": ["p0", "p1"],
        "season": [2025, 2025],
        "week": [18, 18],
        "realized_state": ["primary", "rotation"],
    })
    injury = pd.DataFrame({
        "gsis_id": ["p1"],
        "injury_status": ["Questionable"],
        "practice_level": [1.0],
    })
    live = shadow.build_live_transition_rows(
        _slate(), features, history, injury,
    )
    assert live.gsis_id.tolist() == [f"p{i}" for i in range(8)]
    assert live.loc[live.gsis_id.eq("p0"), "previous_state"].item() == "unknown"
    assert live.loc[live.gsis_id.eq("p1"), "previous_state"].item() == "unknown"
    assert live.loc[live.gsis_id.eq("p1"), "injury_status"].item() == "Questionable"
    assert pd.isna(live.loc[live.gsis_id.eq("p2"), "injury_status"].item())

    week3_slate = _slate().assign(week=3)
    week3_features = features.assign(week=3)
    current_history = pd.concat([
        history,
        pd.DataFrame({
            "gsis_id": ["p0"], "season": [2026], "week": [2],
            "realized_state": ["secondary"],
        }),
    ], ignore_index=True)
    week3 = shadow.build_live_transition_rows(
        week3_slate, week3_features, current_history, injury,
    )
    assert week3.loc[
        week3.gsis_id.eq("p0"), "previous_state"
    ].item() == "secondary"

    with pytest.raises(LatentRoleStateError, match="target/future"):
        shadow.build_live_transition_rows(
            _slate(), features, current_history, injury,
        )

    with pytest.raises(LatentRoleStateError, match="contains outcomes"):
        shadow.build_live_transition_rows(
            _slate().assign(actual=20.0), features, history, injury,
        )


def _world(kind, sequence, *, accepted=True):
    states = tuple((f"p{index}", "rotation") for index in range(8))
    kwargs = {}
    if kind == "promotion":
        kwargs = {
            "promoted_player_id": f"p{sequence - 1}",
            "modal_state": "rotation",
            "promoted_state": "primary",
            "entropy": 1.0,
        }
    return JointRoleStateWorld(
        kind=kind,
        sequence=sequence,
        states=states,
        cap_accepted=accepted,
        rejection_reason=(None if accepted else "team-share cap"),
        **kwargs,
    )


def test_factory_emits_exact_four_plus_eight_with_score_free_receipts(monkeypatch):
    probabilities = pd.DataFrame(
        np.tile([0.05, 0.10, 0.45, 0.20, 0.20], (8, 1)),
        columns=STATES,
    )
    promotions = tuple(_world("promotion", index) for index in range(1, 5))
    attempts = tuple(
        _world("sampled", index, accepted=index not in {2, 7})
        for index in range(1, 11)
    )
    monkeypatch.setattr(
        shadow,
        "predict_role_transition_artifact",
        lambda artifact, rows: probabilities.set_axis(rows.index),
    )
    monkeypatch.setattr(
        shadow,
        "build_joint_role_state_worlds",
        lambda artifact, rows, probs: (promotions, attempts),
    )
    factory = shadow.LiveLatentRoleScenarioFactory(
        season=2026,
        week=1,
        as_of="2026-08-15T12:00:00Z",
        code_sha="a" * 40,
        artifact={"artifact_version": "test"},
        artifact_receipt={"sha256": "b" * 64, "create_only": True},
        history=pd.DataFrame(columns=["gsis_id", "season", "week", "realized_state"]),
        features=_feature_rows(),
        injury=pd.DataFrame(),
        conditional_model=None,
        conditional_model_version="pooled/components__tail_k1_role/2026-W33",
        expected_n_sims=4,
    )

    def fake_projection(self, world, live_rows, slate, **kwargs):
        draws = np.add.outer(
            np.arange(len(slate), dtype=float),
            np.arange(kwargs["n_sims"], dtype=float),
        ) + world.sequence
        objective = draws.mean(axis=1)
        return objective, draws

    factory._conditional_projection = types.MethodType(fake_projection, factory)
    env = {
        "EPISTEMIC_FAMILY": "latent_role_states",
        "PROSPECTIVE_LATENT_ROLE_VERSION": "prospective-latent-role-state-v1",
        "MULTISEED_PORTFOLIO": "CBWU_LATENT_ROLE_SHADOW",
    }
    scenarios, receipt = factory(
        season=2026,
        week=1,
        source_label="R0",
        projection_seed=0,
        role_seed=7331,
        n_sims=4,
        slate=_slate(),
        conditional_model_variant="tail_k1_role",
        policy_env=env,
    )
    assert len(scenarios) == 12
    assert [name.split(":", 1)[0] for name, _ in scenarios[:4]] == [
        "latent_promotion"
    ] * 4
    sampled_attempts = [int(name.split(":")[1]) for name, _ in scenarios[4:]]
    assert sampled_attempts == [1, 3, 4, 5, 6, 8, 9, 10]
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["uses_fantasy_or_lineup_outcomes"] is False
    assert receipt["promotion_scenarios"] == 4
    assert receipt["sampled_cap_valid_scenarios"] == 8
    assert [row["attempt"] for row in receipt["sampled_cap_rejections"]] == [2, 7]
    assert len(receipt["role_probability_sha256"]) == 64

    bad = dict(env, N_ROUTE_TAIL="12")
    with pytest.raises(LatentRoleStateError, match="bundles another arm"):
        factory(
            season=2026,
            week=1,
            source_label="R0",
            projection_seed=0,
            role_seed=7331,
            n_sims=4,
            slate=_slate(),
            conditional_model_variant="tail_k1_role",
            policy_env=bad,
        )
