import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest
import numpy as np
import pandas as pd

from nfl_dfs.backtest import engine
from nfl_dfs.inference import live_lineups
from nfl_dfs.app.main import LineupRequest, _request_construction_preset
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.optimizer.construction_presets import (
    BASE_CONSTRUCTION_RECEIPT_SCOPE,
    INCUMBENT_GPP_PRESET_ID,
    LEGALITY_ONLY_PRESET_ID,
    UNRECEIPTED_CONSTRUCTION_SCOPE,
    construction_receipt_scope,
    preset_from_receipt,
    resolve_construction_preset,
    resolve_construction_preset_from_environment,
    verify_construction_execution,
)
from nfl_dfs.optimizer.lineup import (
    StackRules, optimize, optimize_many, select_tail_entries,
)


def _one_game_low_salary_pool():
    rows = [
        ("qb", "QB", "A", "B"),
        ("rb1", "RB", "B", "A"),
        ("rb2", "RB", "B", "A"),
        ("wr1", "WR", "B", "A"),
        ("wr2", "WR", "B", "A"),
        ("wr3", "WR", "B", "A"),
        ("wr4", "WR", "B", "A"),
        ("te", "TE", "B", "A"),
        ("dst", "DST", "A", "B"),
    ]
    return [
        {
            "id": pid, "name": pid, "pos": pos, "team": team,
            "opp": opp, "game_id": "only-game", "salary": 4_000,
            "proj": float(20 - index),
        }
        for index, (pid, pos, team, opp) in enumerate(rows)
    ]


def test_bare_optimizer_is_legality_only_despite_ambient_strategy(monkeypatch):
    monkeypatch.setenv("MIN_LINEUP_SALARY", "49000")
    monkeypatch.setenv("MIN_GAMES", "2")
    monkeypatch.setenv("MAX_PER_GAME", "1")
    monkeypatch.setenv("FORBID_RB_DST", "1")
    lineup = optimize(_one_game_low_salary_pool(), stack=StackRules())
    assert lineup is not None
    assert lineup.salary == 36_000
    assert {p["game_id"] for p in lineup.players} == {"only-game"}
    assert StackRules() == StackRules(
        qb_stack_min=0,
        bring_back_min=0,
        forbid_rb_vs_dst=False,
        forbid_two_rb_same_team=False,
    )


def test_incumbent_preset_reproduces_pre_seam_construction():
    preset = resolve_construction_preset(INCUMBENT_GPP_PRESET_ID)
    assert preset.stack == StackRules(
        qb_stack_min=2,
        bring_back_min=1,
        forbid_rb_vs_dst=True,
        forbid_two_rb_same_team=True,
    )
    assert preset.min_salary == 49_000
    assert preset.min_games == 2
    assert preset.punt_min == 0
    assert preset.punt_max_salary == 4_000
    assert preset.value2_min == 0
    assert preset.own_barbell is False
    assert preset.max_per_game == 0
    assert preset.min_lowown == 0
    assert preset.max_overlap == 7
    with pytest.raises(FrozenInstanceError):
        preset.stack.qb_stack_min = 0
    assert resolve_construction_preset(
        INCUMBENT_GPP_PRESET_ID,
    ).stack.qb_stack_min == 2


def test_nullable_punt_ceiling_distinguishes_omission_from_disable():
    inherited = resolve_construction_preset(INCUMBENT_GPP_PRESET_ID)
    disabled = resolve_construction_preset(
        INCUMBENT_GPP_PRESET_ID, punt_max_salary=None,
    )
    assert inherited.punt_max_salary == 4_000
    assert disabled.punt_max_salary is None


def test_all_stack_rule_fields_are_explicitly_resolvable_and_receipted():
    preset = resolve_construction_preset(
        LEGALITY_ONLY_PRESET_ID,
        qb_stack_min=1,
        qb_stack_max=2,
        bring_back_min=0,
        bring_back_max=1,
        forbid_rb_vs_dst=False,
        forbid_two_rb_same_team=False,
        require_rb_vs_dst=True,
        require_two_rb_same_team=True,
    )
    assert preset.stack == StackRules(
        qb_stack_min=1,
        qb_stack_max=2,
        bring_back_min=0,
        bring_back_max=1,
        require_rb_vs_dst=True,
        require_two_rb_same_team=True,
    )
    assert preset_from_receipt(preset.receipt()) == preset


def test_environment_stack_bypass_neutralizes_all_eight_stack_fields(
    monkeypatch,
):
    from nfl_dfs.optimizer import construction_presets

    nonneutral = resolve_construction_preset(
        LEGALITY_ONLY_PRESET_ID,
        qb_stack_min=1,
        qb_stack_max=2,
        bring_back_min=1,
        bring_back_max=2,
        forbid_rb_vs_dst=True,
        forbid_two_rb_same_team=True,
        require_rb_vs_dst=True,
        require_two_rb_same_team=True,
    )
    monkeypatch.setitem(
        construction_presets._PRESETS,
        "test-all-eight-stack-fields",
        nonneutral,
    )
    resolved = resolve_construction_preset_from_environment(
        "test-all-eight-stack-fields", {}, use_stack=False,
    )
    assert resolved.stack == StackRules()


def test_construction_receipt_must_match_executed_stack_and_environment():
    preset = resolve_construction_preset(INCUMBENT_GPP_PRESET_ID)
    receipt = preset.receipt()
    env = preset.optimizer_environment()
    assert verify_construction_execution(
        receipt, stack=preset.stack, env=env,
    ) == preset

    with pytest.raises(ValueError, match="StackRules differ"):
        verify_construction_execution(
            receipt, stack=StackRules(), env=env,
        )
    with pytest.raises(ValueError, match="environment differs"):
        verify_construction_execution(
            receipt,
            stack=preset.stack,
            env={**env, "MIN_LINEUP_SALARY": "0"},
        )
    forged = {**receipt, "punt_strict": "false"}
    with pytest.raises(ValueError, match="boolean field type"):
        preset_from_receipt(forged)
    forged = {**receipt, "min_games": 1}
    with pytest.raises(ValueError, match="content hash or values differ"):
        preset_from_receipt(forged)


def test_zero_overrides_are_effective_not_treated_as_omissions():
    preset = resolve_construction_preset(
        INCUMBENT_GPP_PRESET_ID,
        qb_stack_min=0,
        bring_back_min=0,
        forbid_rb_vs_dst=False,
        forbid_two_rb_same_team=False,
        min_salary=0,
        min_games=1,
        punt_min=0,
        punt_max_salary=0,
        value2_min=0,
        own_barbell=False,
        max_per_game=0,
        min_lowown=0,
    )
    assert preset.stack == StackRules()
    assert preset.min_salary == 0
    assert preset.min_games == 1
    assert preset.punt_max_salary == 0
    assert preset.optimizer_environment()["MIN_LINEUP_SALARY"] == "0"


def test_legality_and_replay_resolution_are_named_and_receipted():
    legal = resolve_construction_preset(LEGALITY_ONLY_PRESET_ID)
    assert legal.stack == StackRules()
    assert legal.min_salary == 0
    assert legal.min_games == 1

    replay = resolve_construction_preset_from_environment(
        INCUMBENT_GPP_PRESET_ID,
        {"STACK_QB_MIN": "0", "MIN_LINEUP_SALARY": "0"},
    )
    assert replay.stack.qb_stack_min == 0
    assert replay.stack.bring_back_min == 1
    assert replay.min_salary == 0
    receipt = replay.receipt()
    payload = {
        key: value for key, value in receipt.items()
        if key not in {"effective_id", "sha256"}
    }
    assert receipt["sha256"] == hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def test_production_identity_records_named_incumbent_preset():
    identity = ADOPTED_CLASSIC_POLICY.public_identity()
    receipt = identity["construction_preset"]
    assert identity["construction_receipt_scope"] == (
        BASE_CONSTRUCTION_RECEIPT_SCOPE
    )
    assert receipt["base_preset_id"] == INCUMBENT_GPP_PRESET_ID
    assert receipt["effective_id"].startswith(
        f"{INCUMBENT_GPP_PRESET_ID}@sha256:"
    )
    assert receipt["min_salary"] == 49_000
    assert receipt["min_games"] == 2
    assert identity["engine_environment_receipt"]["values"]["MIN_GAMES"] == "2"
    env = identity["engine_environment_receipt"]["values"]
    assert env["MIN_LINEUP_SALARY"] == str(receipt["min_salary"])
    assert env["MAX_PER_GAME"] == str(receipt["max_per_game"])


def test_request_omission_inherits_named_preset_and_legality_is_selectable():
    incumbent = _request_construction_preset(LineupRequest(season=2026, week=1))
    assert incumbent.preset_id == INCUMBENT_GPP_PRESET_ID
    assert incumbent.stack.qb_stack_min == 2
    assert incumbent.stack.bring_back_min == 1
    assert incumbent.stack.forbid_rb_vs_dst is True
    assert incumbent.stack.forbid_two_rb_same_team is True
    assert incumbent.min_salary == 49_000
    assert incumbent.min_games == 2

    legal = _request_construction_preset(LineupRequest(
        season=2026, week=1,
        construction_preset_id=LEGALITY_ONLY_PRESET_ID,
    ))
    assert legal.stack == StackRules()
    assert legal.min_salary == 0
    assert legal.min_games == 1
    assert legal.max_per_game == 0
    assert legal.max_overlap == 8


def test_bare_and_incumbent_multi_lineup_overlap_are_distinct():
    assert resolve_construction_preset(
        LEGALITY_ONLY_PRESET_ID,
    ).optimizer_environment()["MAX_OVERLAP"] == "8"
    assert resolve_construction_preset(
        INCUMBENT_GPP_PRESET_ID,
    ).optimizer_environment()["MAX_OVERLAP"] == "7"
    assert optimize_many.__defaults__[1] is None


def test_bare_selector_ignores_ambient_strategy(monkeypatch):
    monkeypatch.setenv("SELECT_LSE", "0.2")
    monkeypatch.setenv("SELECT_LADDER", "200:1")
    totals = np.array([[100.0, 0.0], [0.0, 100.0]])
    assert select_tail_entries(totals, 1, 50.0) in ([0], [1])


def test_bare_tail_engine_passes_neutral_runtime_environment(monkeypatch):
    monkeypatch.setenv("N_BOOM", "999")
    monkeypatch.setenv("CAND_MULT", "999")
    monkeypatch.setenv("SELECT_LADDER", "200:1")
    seen = {}

    def stop_after_resolution(n_boom_solves, env):
        seen.update(env)
        raise RuntimeError("stop after environment capture")

    monkeypatch.setattr(engine, "resolve_generation_budget", stop_after_resolution)
    slate = pd.DataFrame([{
        "id": "p", "name": "p", "pos": "QB", "team": "A",
        "opp": "B", "game_id": "g", "salary": 4_000, "proj": 1.0,
        "actual": 1.0, "draw_idx": 0,
    }])
    with pytest.raises(RuntimeError, match="environment capture"):
        engine.tail_select_lineups(
            slate, slate.to_dict("records"), np.ones((1, 2)), 1.0, 1,
            None, "proj", policy_env=None,
        )
    assert seen == {}


def test_tail_engine_refuses_a_receipt_that_does_not_match_execution(
    monkeypatch,
):
    preset = resolve_construction_preset(INCUMBENT_GPP_PRESET_ID)
    monkeypatch.setattr(
        engine,
        "_row_draws",
        lambda *args, **kwargs: pytest.fail("draws opened before law check"),
    )
    slate = pd.DataFrame([{
        "id": "p", "name": "p", "pos": "QB", "team": "A",
        "opp": "B", "game_id": "g", "salary": 4_000, "proj": 1.0,
        "actual": 1.0, "draw_idx": 0,
    }])
    with pytest.raises(ValueError, match="StackRules differ"):
        engine.tail_select_lineups(
            slate,
            slate.to_dict("records"),
            np.ones((1, 2)),
            1.0,
            1,
            StackRules(),
            "proj",
            policy_env=preset.optimizer_environment(),
            construction_preset_receipt=preset.receipt(),
        )


def test_live_builder_refuses_mismatch_before_slate_or_draw_construction(
    monkeypatch,
):
    preset = resolve_construction_preset(INCUMBENT_GPP_PRESET_ID)
    monkeypatch.setattr(
        live_lineups,
        "build_slate_with_draws",
        lambda *args, **kwargs: pytest.fail(
            "live slate/draw construction opened before law check"
        ),
    )
    with pytest.raises(ValueError, match="StackRules differ"):
        live_lineups.build_sim_lineups(
            2026,
            1,
            n_entries=1,
            stack=StackRules(),
            tail_line=194.0,
            policy_env=preset.optimizer_environment(),
            construction_preset_receipt=preset.receipt(),
        )


def test_non_tail_week_refuses_mismatch_before_optimizer(monkeypatch):
    preset = resolve_construction_preset(INCUMBENT_GPP_PRESET_ID)
    monkeypatch.setattr(
        engine,
        "optimize_many",
        lambda *args, **kwargs: pytest.fail(
            "optimizer opened before construction-law check"
        ),
    )
    slate = pd.DataFrame([{
        "id": "p", "name": "p", "pos": "QB", "team": "A",
        "opp": "B", "game_id": "g", "salary": 4_000, "proj": 1.0,
        "actual": 2.0,
    }])
    with pytest.raises(ValueError, match="StackRules differ"):
        engine.run_week(
            slate,
            object(),
            n_entries=1,
            stack=StackRules(),
            policy_env=preset.optimizer_environment(),
            construction_preset_receipt=preset.receipt(),
        )


def test_construction_receipt_scope_labels_are_explicit():
    assert BASE_CONSTRUCTION_RECEIPT_SCOPE == "base-policy-only-v1"
    assert UNRECEIPTED_CONSTRUCTION_SCOPE == "unreceipted"
    assert construction_receipt_scope(None) == UNRECEIPTED_CONSTRUCTION_SCOPE
    assert construction_receipt_scope({}) == BASE_CONSTRUCTION_RECEIPT_SCOPE


def test_explicit_min_games_fails_closed_when_slate_has_one_game():
    preset = resolve_construction_preset(
        LEGALITY_ONLY_PRESET_ID, min_games=2,
    )
    assert optimize(
        _one_game_low_salary_pool(), stack=preset.stack,
        env=preset.optimizer_environment(),
    ) is None
