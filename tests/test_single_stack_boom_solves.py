"""Default-off exact-single-stack boom carve and shared carve hardening."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import engine
from nfl_dfs.optimizer.lineup import StackRules


def _slate(n_worlds: int = 24):
    partner = {"T0": "T1", "T1": "T0", "T2": "T3", "T3": "T2"}
    game_of = {"T0": "g0", "T1": "g0", "T2": "g1", "T3": "g1"}
    pool, index = [], 0
    for pos, count in (("QB", 4), ("RB", 8), ("WR", 12),
                       ("TE", 6), ("DST", 4)):
        for offset in range(count):
            team = f"T{index % 4}"
            salary = 4000 if pos == "DST" else 5650 + (offset % 3) * 25
            pool.append({
                "id": f"{pos}{offset}", "name": f"{pos}{offset}",
                "pos": pos, "team": team, "opp": partner[team],
                "game_id": game_of[team], "salary": salary,
                "proj": 8.0 + (offset % 6), "actual": 9.0 + (offset % 7),
                "season": 2025, "week": 3,
            })
            index += 1
    slate = pd.DataFrame(pool)
    slate["draw_idx"] = range(len(slate))
    rng = np.random.default_rng(71)
    draws = np.abs(rng.normal(9, 3.0, size=(len(pool), n_worlds)))
    qb_team = {row["id"]: row["team"] for row in pool if row["pos"] == "QB"}
    for world in range(n_worlds):
        hot_qb = f"QB{world % 4}"
        hot_team = qb_team[hot_qb]
        for row_index, row in enumerate(pool):
            if row["id"] == hot_qb:
                draws[row_index, world] += 25.0
            elif row["team"] == hot_team and row["pos"] in ("WR", "TE"):
                draws[row_index, world] = 0.5
    return slate, pool, draws


def _candidates(extra_env):
    slate, pool, draws = _slate()
    captured = {}
    policy_env = {
        "N_QB_VARIANTS": "0", "N_GAMESTACK": "0", "N_DARKGAME": "0",
        **extra_env,
    }
    engine.tail_select_lineups(
        slate, pool, draws, tail_line=95.0, n_entries=4,
        stack=StackRules(qb_stack_min=2, bring_back_min=1),
        objective_col="proj", n_boom_solves=6, policy_env=policy_env,
        candidate_capture=lambda batch: captured.__setitem__("batch", batch),
    )
    return captured["batch"], pool


def _structure(roster, pool):
    by_id = {row["id"]: row for row in pool}
    players = [by_id[player_id] for player_id in roster]
    qb = next(player for player in players if player["pos"] == "QB")
    stack = sum(
        player["team"] == qb["team"] and player["pos"] in ("WR", "TE")
        for player in players
    )
    bring_back = sum(
        player["team"] == qb["opp"] and player["pos"] in ("RB", "WR", "TE")
        for player in players
    )
    return stack, bring_back, players


def test_single_stack_off_is_identical_to_absent():
    plain, _ = _candidates({})
    zero, _ = _candidates({"SINGLE_STACK_BOOM_SOLVES": "0"})
    assert [lineup.ids for lineup in plain.candidates] == [
        lineup.ids for lineup in zero.candidates
    ]
    assert plain.all_tags == zero.all_tags
    assert np.array_equal(plain.candidate_totals, zero.candidate_totals)


def test_single_stack_carve_is_exact_and_keeps_incumbent_rules():
    plain, _ = _candidates({})
    carved, pool = _candidates({"SINGLE_STACK_BOOM_SOLVES": "1"})
    rosters = [
        roster for roster, tags in carved.all_tags.items()
        if "single_stack" in tags
    ]
    assert len(rosters) == 1
    stack, bring_back, players = _structure(rosters[0], pool)
    assert stack == 1
    assert bring_back >= 1
    assert 49_000 <= sum(player["salary"] for player in players) <= 50_000
    rbs = [player for player in players if player["pos"] == "RB"]
    dst = next(player for player in players if player["pos"] == "DST")
    assert len({player["team"] for player in rbs}) == len(rbs)
    assert all(player["team"] != dst["opp"] for player in rbs)
    assert len({player["game_id"] for player in players}) >= 2
    assert sum(lineup.tag == "boom" for lineup in carved.candidates) == sum(
        lineup.tag == "boom" for lineup in plain.candidates)


@pytest.mark.parametrize(
    "key", ["OPEN_BOOM_SOLVES", "SINGLE_STACK_BOOM_SOLVES"])
@pytest.mark.parametrize("value", ["-1", "01", "1.0", " 1", "+1", None, 1])
def test_boom_structure_carves_reject_noncanonical_counts(key, value):
    with pytest.raises(ValueError, match="canonical nonnegative integer"):
        engine._boom_structure_carve_counts({key: value}, 6)


def test_boom_structure_carves_are_bounded_and_mutually_exclusive():
    with pytest.raises(ValueError, match="exceeds the 6 boom-solve budget"):
        engine._boom_structure_carve_counts(
            {"SINGLE_STACK_BOOM_SOLVES": "7"}, 6)
    with pytest.raises(ValueError, match="mutually exclusive"):
        engine._boom_structure_carve_counts({
            "OPEN_BOOM_SOLVES": "1", "SINGLE_STACK_BOOM_SOLVES": "1",
        }, 6)


def test_single_stack_duplicate_rosters_fail_closed(monkeypatch):
    real_optimize = engine.optimize
    first_single = []

    def repeated_single(*args, **kwargs):
        stack = kwargs.get("stack")
        if stack is not None and (
                stack.qb_stack_min, stack.qb_stack_max) == (1, 1):
            if first_single:
                return first_single[0]
            lineup = real_optimize(*args, **kwargs)
            first_single.append(lineup)
            return lineup
        return real_optimize(*args, **kwargs)

    monkeypatch.setattr(engine, "optimize", repeated_single)
    with pytest.raises(RuntimeError, match="SINGLE_STACK_BOOM_SOLVES shortfall"):
        _candidates({"SINGLE_STACK_BOOM_SOLVES": "2"})


def test_single_stack_duplicate_of_incumbent_candidate_fails_closed(monkeypatch):
    real_optimize = engine.optimize
    first_carve_seen = []
    incumbent_between_carves = []

    def repeat_incumbent(*args, **kwargs):
        stack = kwargs.get("stack")
        if stack is not None and (
                stack.qb_stack_min, stack.qb_stack_max) == (1, 1):
            if incumbent_between_carves:
                return incumbent_between_carves[0]
            lineup = real_optimize(*args, **kwargs)
            first_carve_seen.append(True)
            return lineup
        lineup = real_optimize(*args, **kwargs)
        if lineup is not None and first_carve_seen and not incumbent_between_carves:
            incumbent_between_carves.append(lineup)
        return lineup

    monkeypatch.setattr(engine, "optimize", repeat_incumbent)
    with pytest.raises(RuntimeError, match="SINGLE_STACK_BOOM_SOLVES shortfall"):
        _candidates({"SINGLE_STACK_BOOM_SOLVES": "2"})
