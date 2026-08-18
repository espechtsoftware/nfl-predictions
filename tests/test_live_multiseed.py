import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference import live_lineups
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.optimizer.lineup import Lineup, select_from_support


def _frame(seed):
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "DST",
                 "WR", "RB", "TE", "WR", "RB"]
    rows = []
    for player_id, pos in enumerate(positions):
        rows.append({
            "id": player_id,
            "name": f"P{player_id}",
            "pos": pos,
            "team": f"T{player_id % 4}",
            "opp": f"T{(player_id + 1) % 4}",
            "game_id": f"G{player_id % 2}",
            "salary": 5_000,
            "proj": 20.0,
            "proj_tourney": 20.0,
            "draw_idx": player_id,
            "season": 2026,
            "week": 1,
            "test_seed": int(seed),
        })
    frame = pd.DataFrame(rows)
    frame.attrs["model_version"] = "test/model"
    return frame


def test_role_belief_uses_registered_independent_seed(monkeypatch):
    calls = []

    def fake_slate(season, week, n_sims=None, seed=42,
                   log_ownership_shadow=True, **kwargs):
        calls.append((int(seed), bool(log_ownership_shadow)))
        frame = _frame(seed)
        return frame, np.full((len(frame), n_sims or 4), 20.0,
                              dtype=np.float32)

    def fake_tail(slate, pool, draws, **kwargs):
        return [Lineup(pool[:9])]

    monkeypatch.setattr(live_lineups, "build_slate_with_draws", fake_slate)
    monkeypatch.setattr(
        "nfl_dfs.backtest.engine.tail_select_lineups", fake_tail)
    env = {
        "N_EPISTEMIC": "1",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_SEED": "991",
    }
    result = live_lineups.build_sim_lineups(
        2026, 1, n_entries=1, stack=None, tail_line=194,
        n_sims=4, seed=17, apply_notes=False,
        model_variant="base", belief_model_variant="role",
        policy_env=env,
    )
    assert len(result) == 1
    assert calls == [(17, True), (991, False)]


@pytest.mark.parametrize(
    ("portfolio", "expected_portfolio"),
    [("control", "CBWU"), ("shadow", "CBWU_ARCHETYPE_SHADOW")],
)
def test_live_cbwu_runs_all_registered_pairs_and_combines_before_selection(
    monkeypatch, portfolio, expected_portfolio,
):
    slate_calls = []
    final_batches = []

    def fake_slate(season, week, n_sims=None, seed=42,
                   log_ownership_shadow=True, **kwargs):
        slate_calls.append((int(seed), bool(log_ownership_shadow)))
        frame = _frame(seed)
        draws = np.stack([
            np.full(n_sims, 10 + player_id + (int(seed) % 7),
                    dtype=np.float32)
            for player_id in range(len(frame))
        ])
        return frame, draws

    def fake_tail(slate, pool, draws, n_entries, candidate_capture=None,
                  candidate_transform=None, **kwargs):
        seed = int(slate.test_seed.iloc[0])
        rotation = seed % 5
        rosters = []
        for offset in (0, 1):
            ids = [0] + [
                int(1 + (rotation + offset + i) % (len(pool) - 1))
                for i in range(8)
            ]
            rosters.append(Lineup([pool[player_id] for player_id in ids], tag="lev"))
        row_draws = np.asarray(draws, dtype=np.float32)
        totals = np.stack([
            row_draws[list(lineup.ids)].sum(axis=0) for lineup in rosters
        ]).astype(np.float32)
        batch = CandidateBatch(
            candidates=tuple(rosters),
            candidate_totals=totals,
            player_ids=tuple(slate.id.tolist()),
            player_rows=tuple(slate.to_dict("records")),
            row_draws=row_draws,
            all_tags={lineup.ids: ("lev",) for lineup in rosters},
        )
        if candidate_capture is not None:
            candidate_capture(batch)
        if candidate_transform is not None:
            batch = candidate_transform(batch)
            final_batches.append(batch)
        clears = batch.candidate_totals >= 194
        picked = select_from_support(
            clears, clears.mean(axis=1),
            batch.candidate_totals.mean(axis=1), n_entries)
        return [batch.candidates[index] for index in picked]

    monkeypatch.setattr(live_lineups, "build_slate_with_draws", fake_slate)
    monkeypatch.setattr(
        "nfl_dfs.backtest.engine.tail_select_lineups", fake_tail)
    policy = ADOPTED_CLASSIC_POLICY
    env = (
        policy.engine_environment()
        if portfolio == "control"
        else policy.archetype_shadow_environment()
    )
    env["MULTISEED_WORLDS_PER_BLOCK"] = "3"
    outer_capture = []
    control_capture = []
    result = live_lineups.build_sim_lineups(
        2026, 1, n_entries=1, stack=None, tail_line=194,
        n_sims=3, apply_notes=False, model_variant=policy.model_variant,
        belief_model_variant=policy.role_model_variant,
        expected_model_k=policy.model_ensemble, policy_env=env,
        _candidate_capture=outer_capture.append,
        _control_candidate_capture=(
            control_capture.append if portfolio == "shadow" else None
        ),
    )
    assert len(result) == 1
    expected_calls = []
    pairs = policy.multiseed_seed_pairs
    for projection_seed, role_seed in (*pairs[1:], pairs[0]):
        expected_calls.extend([
            (projection_seed, projection_seed == pairs[0][0]),
            (role_seed, False),
        ])
    assert slate_calls == expected_calls
    assert len(final_batches) == 1
    final = final_batches[0]
    assert outer_capture == [final]
    if portfolio == "shadow":
        assert len(control_capture) == 1
        assert control_capture[0].metadata["portfolio"] == "CBWU"
        assert np.array_equal(
            control_capture[0].row_draws, final.row_draws
        )
    else:
        assert control_capture == []
    assert final.metadata["portfolio"] == expected_portfolio
    assert final.metadata["worlds_per_block"] == [3] * 5
    assert final.candidate_totals.shape[1] == 15
    if portfolio == "shadow":
        assert final.metadata["production_enabled"] is False
        assert final.metadata["allocation_receipt"][
            "uses_realized_outcomes"
        ] is False


def test_live_cbwu_rejects_more_than_licensed_80_entries():
    env = ADOPTED_CLASSIC_POLICY.engine_environment()
    with pytest.raises(ValueError, match="at most its licensed 80-entry"):
        live_lineups.build_sim_lineups(
            2026, 1, n_entries=81, stack=None, tail_line=194,
            apply_notes=False, policy_env=env)


def test_live_control_rejects_paired_control_capture():
    # Paired capture is licensed only for the named paired shadow
    # portfolios (archetype, CBWU-OI); the plain money portfolio must
    # still fail closed (message updated with CBWU_OI_SHADOW, 2026-08-18).
    env = ADOPTED_CLASSIC_POLICY.engine_environment()
    with pytest.raises(
        ValueError, match="requires a paired shadow portfolio"
    ):
        live_lineups.build_sim_lineups(
            2026, 1, n_entries=1, stack=None, tail_line=194,
            apply_notes=False, policy_env=env,
            _control_candidate_capture=lambda batch: None,
        )


def test_live_archetype_shadow_rejects_version_or_tail_drift():
    env = ADOPTED_CLASSIC_POLICY.archetype_shadow_environment()
    env["ARCHETYPE_ALLOCATION_VERSION"] = "wrong"
    with pytest.raises(ValueError, match="version differs"):
        live_lineups.build_sim_lineups(
            2026, 1, n_entries=1, stack=None, tail_line=194,
            apply_notes=False, policy_env=env,
        )
    env = ADOPTED_CLASSIC_POLICY.archetype_shadow_environment()
    with pytest.raises(ValueError, match="tail line differs"):
        live_lineups.build_sim_lineups(
            2026, 1, n_entries=1, stack=None, tail_line=200,
            apply_notes=False, policy_env=env,
        )


def test_live_latent_role_factory_is_score_free_and_seed_specific(monkeypatch):
    factory_calls = []
    tail_calls = []

    def fake_slate(season, week, n_sims=None, seed=42,
                   log_ownership_shadow=True, **kwargs):
        frame = _frame(seed)
        return frame, np.full((len(frame), n_sims or 4), 20.0,
                              dtype=np.float32)

    def factory(**kwargs):
        factory_calls.append(kwargs)
        scenarios = tuple(
            (f"scenario-{index}", np.full(len(kwargs["slate"]), index + 1.0))
            for index in range(12)
        )
        return scenarios, {
            "uses_realized_outcomes": False,
            "conditional_model_version": "role/test-v1",
            "source_label": kwargs["source_label"],
        }

    def fake_tail(slate, pool, draws, **kwargs):
        tail_calls.append(kwargs)
        assert kwargs["latent_optimization_receipt"] == []
        kwargs["latent_optimization_receipt"].append({"accepted": True})
        return [Lineup(pool[:9])]

    monkeypatch.setattr(live_lineups, "build_slate_with_draws", fake_slate)
    monkeypatch.setattr(
        "nfl_dfs.backtest.engine.tail_select_lineups", fake_tail)
    env = ADOPTED_CLASSIC_POLICY.latent_role_shadow_environment()
    env["MULTISEED_PORTFOLIO"] = ""
    result = live_lineups.build_sim_lineups(
        2026, 1, n_entries=1, stack=None, tail_line=194,
        n_sims=4, seed=17, apply_notes=False,
        model_variant="base", belief_model_variant="tail_k1_role",
        policy_env=env, _latent_scenario_factory=factory,
    )
    assert len(result) == 1
    assert result[0].role_model_version == "role/test-v1"
    assert len(factory_calls) == 1
    assert factory_calls[0]["projection_seed"] == 17
    assert factory_calls[0]["role_seed"] == 7331
    assert factory_calls[0]["source_label"] == "single"
    assert len(tail_calls[0]["explicit_epistemic_scenarios"]) == 12
    assert tail_calls[0]["latent_scenario_receipt"] == {
        "uses_realized_outcomes": False,
        "conditional_model_version": "role/test-v1",
        "source_label": "single",
    }


def test_live_latent_cbwu_builds_five_treatment_books(monkeypatch):
    slate_calls = []
    factory_calls = []
    final_batches = []

    def fake_slate(season, week, n_sims=None, seed=42,
                   log_ownership_shadow=True, **kwargs):
        slate_calls.append((int(seed), bool(log_ownership_shadow)))
        frame = _frame(seed)
        draws = np.stack([
            np.full(n_sims, 10 + player_id + (int(seed) % 7),
                    dtype=np.float32)
            for player_id in range(len(frame))
        ])
        return frame, draws

    def factory(**kwargs):
        factory_calls.append((
            kwargs["source_label"], kwargs["projection_seed"],
            kwargs["role_seed"], kwargs["n_sims"],
        ))
        scenarios = tuple(
            (f"scenario-{index}", np.full(len(kwargs["slate"]), index + 1.0))
            for index in range(12)
        )
        return scenarios, {
            "uses_realized_outcomes": False,
            "conditional_model_version": "role/test-v1",
            "source_label": kwargs["source_label"],
        }

    def fake_tail(slate, pool, draws, n_entries, candidate_capture=None,
                  candidate_transform=None, **kwargs):
        seed = int(slate.test_seed.iloc[0])
        assert kwargs["latent_optimization_receipt"] == []
        assert len(kwargs["explicit_epistemic_scenarios"]) == 12
        rotation = seed % 5
        rosters = []
        for offset in (0, 1):
            ids = [0] + [
                int(1 + (rotation + offset + i) % (len(pool) - 1))
                for i in range(8)
            ]
            rosters.append(Lineup(
                [pool[player_id] for player_id in ids], tag="epi"))
        row_draws = np.asarray(draws, dtype=np.float32)
        totals = np.stack([
            row_draws[list(lineup.ids)].sum(axis=0) for lineup in rosters
        ]).astype(np.float32)
        batch = CandidateBatch(
            candidates=tuple(rosters), candidate_totals=totals,
            player_ids=tuple(slate.id.tolist()),
            player_rows=tuple(slate.to_dict("records")),
            row_draws=row_draws,
            all_tags={lineup.ids: ("epi",) for lineup in rosters},
            metadata={
                "latent_scenario_receipt": kwargs["latent_scenario_receipt"],
            },
        )
        if candidate_capture is not None:
            candidate_capture(batch)
        if candidate_transform is not None:
            batch = candidate_transform(batch)
            final_batches.append(batch)
        return [batch.candidates[0]]

    monkeypatch.setattr(live_lineups, "build_slate_with_draws", fake_slate)
    monkeypatch.setattr(
        "nfl_dfs.backtest.engine.tail_select_lineups", fake_tail)
    policy = ADOPTED_CLASSIC_POLICY
    env = policy.latent_role_shadow_environment()
    env["MULTISEED_WORLDS_PER_BLOCK"] = "3"
    captured = []
    result = live_lineups.build_sim_lineups(
        2026, 1, n_entries=1, stack=None, tail_line=194,
        n_sims=3, apply_notes=False, model_variant=policy.model_variant,
        belief_model_variant=policy.role_model_variant,
        expected_model_k=policy.model_ensemble, policy_env=env,
        _candidate_capture=captured.append,
        _latent_scenario_factory=factory,
    )
    assert len(result) == 1
    expected = [
        (f"R{index}", projection_seed, role_seed, 3)
        for index, (projection_seed, role_seed) in enumerate(
            policy.multiseed_seed_pairs)
    ]
    assert factory_calls == [*expected[1:], expected[0]]
    assert slate_calls == [
        (projection_seed, projection_seed == policy.multiseed_seed_pairs[0][0])
        for projection_seed, _ in (
            *policy.multiseed_seed_pairs[1:], policy.multiseed_seed_pairs[0]
        )
    ]
    assert len(final_batches) == 1
    assert captured == [final_batches[0]]
    final = final_batches[0]
    assert final.metadata["portfolio"] == "CBWU_LATENT_ROLE_SHADOW"
    assert final.metadata["production_enabled"] is False
    assert final.metadata["uses_realized_outcomes"] is False
    assert set(final.metadata["latent_seed_receipts"]) == {
        "R0", "R1", "R2", "R3", "R4",
    }
    assert final.candidate_totals.shape[1] == 15


def test_live_latent_cbwu_requires_factory():
    env = ADOPTED_CLASSIC_POLICY.latent_role_shadow_environment()
    with pytest.raises(ValueError, match="requires a scenario factory"):
        live_lineups.build_sim_lineups(
            2026, 1, n_entries=1, stack=None, tail_line=194,
            apply_notes=False, policy_env=env,
        )
