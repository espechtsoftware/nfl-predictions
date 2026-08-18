"""Parity contract for the shared DraftKings Classic constraint builder.

The frozen roster snapshots below were captured from
``lineup.py`` SHA-256
``81544e5f80769012fccef66b38c6bea54a830ac15dbed447952a593aa40b3bee``
before the inline constraints were extracted.  They protect ordinary
``optimize`` behavior while research models reuse the exact same domain.
"""

from __future__ import annotations

import inspect
import hashlib
from pathlib import Path
import subprocess
import sys
import types

import numpy as np
import pulp
import pytest

import nfl_dfs.optimizer.lineup as lineup_module
from nfl_dfs.optimizer.lineup import (
    StackRules,
    add_classic_lineup_constraints,
    optimize,
)


_PRE_REFACTOR_COMMIT = "7c74f2a54191fc853e7d3ab122bf344819c3f033"
_PRE_REFACTOR_SOURCE_SHA256 = (
    "81544e5f80769012fccef66b38c6bea54a830ac15dbed447952a593aa40b3bee"
)


def _pool(seed: int = 31, n_teams: int = 6) -> list[dict]:
    rng = np.random.default_rng(seed)
    players = []
    player_id = 0
    opponents = {
        f"T{team_index}": f"T{team_index + 1 if team_index % 2 == 0 else team_index - 1}"
        for team_index in range(n_teams)
    }
    for team_index, (team, opponent) in enumerate(opponents.items()):
        game = f"G{team_index // 2}"
        for pos, count in (
            ("QB", 1), ("RB", 3), ("WR", 4), ("TE", 2), ("DST", 1),
        ):
            for position_index in range(count):
                base = {"QB": 20, "RB": 14, "WR": 12, "TE": 8, "DST": 7}[pos]
                projection = max(
                    1.0,
                    base - 3 * position_index + rng.normal(0, 1.5),
                )
                players.append({
                    "id": player_id,
                    "name": f"{pos}{position_index}_{team}",
                    "pos": pos,
                    "team": team,
                    "opp": opponent,
                    "game_id": game,
                    "salary": int(np.clip(
                        2_800 + projection * 320 + rng.normal(0, 300),
                        2_500,
                        9_500,
                    )),
                    "proj": projection,
                    "own_est": (0.01, 0.10, 0.30)[player_id % 3],
                    "low_own": player_id % 7 == 0,
                    "punt_elig": player_id % 11 == 0,
                })
                player_id += 1
    return players


def _case_kwargs(case: str) -> dict:
    if case == "plain":
        return {}
    if case == "stack":
        return {"stack": StackRules(qb_stack_min=2, bring_back_min=1)}
    if case == "locks_bans":
        return {
            "locks": {65},
            "bans": {0},
            "stack": StackRules(qb_stack_min=2, bring_back_min=1),
        }
    if case == "explicit_money":
        return {
            "stack": StackRules(qb_stack_min=2, bring_back_min=1),
            "min_salary": 49_000,
            "max_per_game": 0,
            "punt_min": 0,
            "punt_max_salary": None,
            "env": {},
        }
    if case == "levers":
        return {
            "stack": StackRules(qb_stack_min=2, bring_back_min=1),
            "punt_min": 1,
            "punt_max_salary": 4_000,
            "min_salary": 0,
            "env": {
                "VALUE2_MIN": "2",
                "VALUE2_MAX": "5300",
                "OWN_BARBELL": "1",
                "OWN_BARBELL_NLOW": "2",
                "OWN_BARBELL_NHIGH": "2",
                "MAX_PER_GAME": "4",
                "MIN_LOWOWN": "1",
                "PUNT_STRICT": "1",
            },
        }
    if case == "infeasible_no_qb":
        return {"env": {}}
    raise AssertionError(f"unknown test case {case}")


_PRE_REFACTOR_ROSTERS = {
    "plain": (4, 7, 11, 12, 19, 32, 36, 49, 52),
    "stack": (1, 7, 12, 32, 40, 44, 49, 52, 58),
    "locks_bans": (4, 12, 19, 36, 44, 49, 52, 62, 65),
    "explicit_money": (1, 7, 12, 32, 40, 44, 49, 52, 58),
    "levers": (4, 12, 19, 21, 36, 44, 49, 52, 62),
    "infeasible_no_qb": None,
}


@pytest.mark.parametrize("case", tuple(_PRE_REFACTOR_ROSTERS))
def test_optimize_status_and_roster_match_pre_refactor_snapshot(case):
    players = _pool()
    if case == "infeasible_no_qb":
        players = [player for player in players if player["pos"] != "QB"]
    lineup = optimize(players, **_case_kwargs(case))
    roster = None if lineup is None else tuple(sorted(lineup.ids))
    assert roster == _PRE_REFACTOR_ROSTERS[case]


def _direct_shared_solve(players, **kwargs):
    problem = pulp.LpProblem("dfs", pulp.LpMaximize)
    variables = {
        player["id"]: pulp.LpVariable(f"x_{player['id']}", cat="Binary")
        for player in players
    }
    problem += pulp.lpSum(
        variables[player["id"]] * float(player["proj"])
        for player in players
    )
    add_classic_lineup_constraints(problem, variables, players, **kwargs)
    problem.solve(pulp.PULP_CBC_CMD(msg=0))
    roster = None
    if pulp.LpStatus[problem.status] == "Optimal":
        roster = frozenset(
            player_id for player_id, variable in variables.items()
            if variable.value() == 1
        )
    return problem, roster


def test_direct_shared_builder_matches_production_model_and_order(monkeypatch):
    players = _pool()
    kwargs = {
        "budget": 50_000,
        "locks": {65},
        "bans": {0},
        "banned_lineups": [frozenset(_PRE_REFACTOR_ROSTERS["plain"])],
        "stack": StackRules(qb_stack_min=2, bring_back_min=1),
        "max_overlap": 8,
        "punt_max_salary": 4_000,
        "punt_min": 1,
        "game_lock": ("G1", 2),
        "min_salary": 45_000,
        "max_salary": 49_950,
        "max_per_game": 4,
        "env": {
            "VALUE2_MIN": "2",
            "VALUE2_MAX": "5300",
            "OWN_BARBELL": "1",
            "OWN_BARBELL_NLOW": "2",
            "OWN_BARBELL_NHIGH": "2",
            "MIN_LOWOWN": "1",
            "PUNT_STRICT": "1",
        },
    }
    captured = {}
    original_solve = pulp.LpProblem.solve

    def capture(problem, solver=None, **solve_kwargs):
        captured["problem"] = problem
        captured["solver"] = solver
        return original_solve(problem, solver=solver, **solve_kwargs)

    monkeypatch.setattr(pulp.LpProblem, "solve", capture)
    production = optimize(players, **kwargs)
    monkeypatch.setattr(pulp.LpProblem, "solve", original_solve)

    direct_problem, direct_roster = _direct_shared_solve(players, **kwargs)
    production_problem = captured["problem"]
    assert production_problem.toDict()["constraints"] == (
        direct_problem.toDict()["constraints"]
    )
    assert str(production_problem.objective) == str(direct_problem.objective)
    assert isinstance(captured["solver"], pulp.PULP_CBC_CMD)
    assert production is not None
    assert production.ids == direct_roster


def test_research_money_domain_and_normalized_no_good_are_shared():
    players = _pool()
    money_domain = {
        "budget": 50_000,
        "min_salary": 49_000,
        "max_per_game": 0,
        "punt_max_salary": None,
        "punt_min": 0,
        "locks": None,
        "bans": None,
        "env": {},
        "stack": StackRules(
            qb_stack_min=2,
            bring_back_min=1,
            forbid_rb_vs_dst=True,
            forbid_two_rb_same_team=True,
        ),
    }
    first_problem, first = _direct_shared_solve(players, **money_domain)
    assert pulp.LpStatus[first_problem.status] == "Optimal"
    assert first is not None

    production = optimize(players, **money_domain)
    assert production is not None and production.ids == first
    assert 49_000 <= production.salary <= 50_000

    second_problem, second = _direct_shared_solve(
        players,
        **money_domain,
        banned_lineups=[frozenset(sorted(first))],
        max_overlap=8,
    )
    assert pulp.LpStatus[second_problem.status] == "Optimal"
    assert second is not None and second != first
    assert len(second & first) <= 8


def test_production_cbc_invocation_remains_literal_default():
    source = inspect.getsource(optimize)
    assert source.count("prob.solve(pulp.PULP_CBC_CMD(msg=0))") == 1


# ---------------------------------------------------------------------------
# Full persisted pre-refactor model/status/identity corpus


def _exact_pool(
    flex_position: str = "WR",
    *,
    total_salary: int = 49_500,
    team_mode: str = "unique",
    game_mode: str = "two",
) -> list[dict]:
    skill = {
        "RB": ("RB", "RB", "RB", "WR", "WR", "WR", "TE"),
        "WR": ("RB", "RB", "WR", "WR", "WR", "WR", "TE"),
        "TE": ("RB", "RB", "WR", "WR", "WR", "TE", "TE"),
    }[flex_position]
    positions = ("QB", *skill, "DST")
    salaries = [5_500] * 9
    salaries[0] += total_salary - sum(salaries)
    rows = []
    for index, (position, salary) in enumerate(zip(positions, salaries)):
        if team_mode == "nine":
            team = "A"
        elif team_mode == "eight":
            team = "A" if index < 8 else "B"
        else:
            team = f"T{index}"
        if game_mode == "one":
            game_id = "G0"
        elif game_mode == "empty":
            game_id = ""
        elif game_mode == "none":
            game_id = None
        else:
            game_id = f"G{index % 2}"
        rows.append({
            "id": 100 + index,
            "name": f"{position}-{index}",
            "pos": position,
            "team": team,
            "opp": "Z",
            "game_id": game_id,
            "salary": salary,
            "proj": float(30 - index),
            "floor_metric": float(20 - index / 10),
            "own_est": 0.10,
            "low_own": False,
            "punt_elig": False,
        })
    return rows


def _matrix_pool(case: str) -> list[dict]:
    if case == "flex_rb":
        return _exact_pool("RB")
    if case == "flex_wr":
        return _exact_pool("WR")
    if case == "flex_te":
        return _exact_pool("TE")
    if case == "salary_49000":
        return _exact_pool(total_salary=49_000)
    if case == "salary_50000":
        return _exact_pool(total_salary=50_000)
    if case == "salary_48999_infeasible":
        return _exact_pool(total_salary=48_999)
    if case == "salary_50001_infeasible":
        return _exact_pool(total_salary=50_001)
    if case == "team_eight":
        return _exact_pool(team_mode="eight")
    if case == "team_nine_infeasible":
        return _exact_pool(team_mode="nine")
    if case == "one_game_legacy":
        return _exact_pool(game_mode="one")
    if case == "empty_game_legacy":
        return _exact_pool(game_mode="empty")
    if case == "none_game_legacy":
        return _exact_pool(game_mode="none")
    if case == "two_game_enforced":
        players = _exact_pool(game_mode="one")
        alternative = dict(players[4])
        alternative.update({
            "id": 999,
            "name": "WR-low-other-game",
            "team": "ALT",
            "game_id": "G1",
            "proj": -100.0,
        })
        return [*players, alternative]

    players = _pool()
    for player in players:
        player["floor_metric"] = float(player["proj"] * 0.9)
    if case in {"punt_unavailable_inert", "punt_strict_zero_eligible"}:
        for player in players:
            player["punt_elig"] = False
            if case == "punt_unavailable_inert":
                player["salary"] = max(4_100, player["salary"])
    elif case == "value2_insufficient_inert":
        for player in players:
            if player["pos"] != "DST":
                player["salary"] = 5_400
            else:
                player["salary"] = 3_000
    elif case == "own_missing_inert":
        for player in players:
            player.pop("own_est")
    elif case == "own_insufficient_bands_inert":
        for player in players:
            player["own_est"] = 0.10
    elif case == "maxpg_none_uncapped":
        uncapped = frozenset(_PRE_REFACTOR_ROSTERS["plain"])
        for player in players:
            if player["id"] in uncapped:
                player["game_id"] = None
    elif case == "lowown_missing_inert":
        for player in players:
            player["low_own"] = False
    elif case == "lowown_requested_above_available_clamps":
        for player in players:
            player["low_own"] = player["id"] == 4
    elif case == "infeasible_no_qb":
        players = [player for player in players if player["pos"] != "QB"]
    elif case in {"tie_input", "tie_reversed"}:
        for player in players:
            player["proj"] = 10.0
        if case == "tie_reversed":
            players.reverse()
    return players


def _matrix_kwargs(case: str, stack_type) -> dict:
    kwargs = {"env": {}}
    if case == "stack_default":
        kwargs["stack"] = stack_type()
    elif case == "stack_money":
        kwargs["stack"] = stack_type(qb_stack_min=2, bring_back_min=1)
    elif case == "stack_qb_max":
        kwargs["stack"] = stack_type(qb_stack_min=1, qb_stack_max=1)
    elif case == "stack_bring_max":
        kwargs["stack"] = stack_type(bring_back_min=1, bring_back_max=1)
    elif case == "stack_allow_rb_dst":
        kwargs["stack"] = stack_type(forbid_rb_vs_dst=False)
    elif case == "stack_require_rb_dst":
        kwargs["stack"] = stack_type(
            forbid_rb_vs_dst=False,
            require_rb_vs_dst=True,
        )
    elif case == "stack_allow_two_rb":
        kwargs["stack"] = stack_type(forbid_two_rb_same_team=False)
    elif case == "stack_require_two_rb":
        kwargs["stack"] = stack_type(
            forbid_two_rb_same_team=False,
            require_two_rb_same_team=True,
        )
    elif case == "stack_conflict_rb_dst":
        kwargs["stack"] = stack_type(require_rb_vs_dst=True)
    elif case == "stack_conflict_two_rb":
        kwargs["stack"] = stack_type(require_two_rb_same_team=True)
    elif case == "stack_invalid_min":
        kwargs["stack"] = stack_type(qb_stack_min=-1)
    elif case == "stack_invalid_max":
        kwargs["stack"] = stack_type(qb_stack_min=2, qb_stack_max=1)
    elif case == "stack_invalid_bring_min":
        kwargs["stack"] = stack_type(bring_back_min=-1)
    elif case == "stack_invalid_bring_max":
        kwargs["stack"] = stack_type(
            bring_back_min=2,
            bring_back_max=1,
        )
    elif case == "lock":
        kwargs["locks"] = {65}
    elif case == "ban":
        kwargs["bans"] = {0}
    elif case == "no_good":
        kwargs["banned_lineups"] = [
            frozenset(_PRE_REFACTOR_ROSTERS["plain"]),
        ]
    elif case == "no_good_unknown":
        kwargs["banned_lineups"] = [
            frozenset((*_PRE_REFACTOR_ROSTERS["plain"], 9_999)),
        ]
    elif case == "lock_unknown":
        kwargs["locks"] = {9_999}
    elif case == "ban_unknown":
        kwargs["bans"] = {9_999}
    elif case == "punt_salary":
        kwargs.update({"punt_min": 1, "punt_max_salary": 4_000})
    elif case == "punt_strict":
        kwargs.update({
            "punt_min": 1,
            "punt_max_salary": 4_000,
            "env": {"PUNT_STRICT": "1"},
        })
    elif case == "punt_strict_zero_eligible":
        kwargs.update({
            "punt_min": 1,
            "punt_max_salary": 4_000,
            "env": {"PUNT_STRICT": "1"},
        })
    elif case == "punt_unavailable_inert":
        kwargs.update({
            "punt_min": 1,
            "punt_max_salary": 4_000,
            "min_salary": 0,
        })
    elif case == "value2":
        kwargs["env"] = {"VALUE2_MIN": "2", "VALUE2_MAX": "5300"}
    elif case == "value2_insufficient_inert":
        kwargs.update({
            "min_salary": 0,
            "env": {"VALUE2_MIN": "2", "VALUE2_MAX": "5300"},
        })
    elif case == "own_on":
        kwargs["env"] = {
            "OWN_BARBELL": "1",
            "OWN_BARBELL_NLOW": "2",
            "OWN_BARBELL_NHIGH": "2",
        }
    elif case == "own_string_zero":
        kwargs["env"] = {
            "OWN_BARBELL": "0",
            "OWN_BARBELL_NLOW": "2",
            "OWN_BARBELL_NHIGH": "2",
        }
    elif case == "own_missing_inert":
        kwargs["env"] = {"OWN_BARBELL": "1"}
    elif case == "own_insufficient_bands_inert":
        kwargs["env"] = {
            "OWN_BARBELL": "1",
            "OWN_BARBELL_NLOW": "3",
            "OWN_BARBELL_NHIGH": "2",
        }
    elif case == "maxpg_env":
        kwargs["env"] = {"MAX_PER_GAME": "3"}
    elif case == "maxpg_explicit_zero":
        kwargs.update({"max_per_game": 0, "env": {"MAX_PER_GAME": "3"}})
    elif case == "maxpg_none_uncapped":
        kwargs["max_per_game"] = 1
    elif case == "lowown":
        kwargs["env"] = {"MIN_LOWOWN": "2"}
    elif case == "lowown_missing_inert":
        kwargs["env"] = {"MIN_LOWOWN": "2"}
    elif case == "lowown_requested_above_available_clamps":
        kwargs["env"] = {"MIN_LOWOWN": "5"}
    elif case == "game_lock":
        kwargs["game_lock"] = ("G0", 5)
    elif case == "game_lock_insufficient_inert":
        kwargs["game_lock"] = ("G0", 99)
    elif case == "objective_floor":
        kwargs.update({
            "objective_floor_col": "floor_metric",
            "objective_floor": 70.0,
        })
    elif case == "objective_floor_pair_missing":
        kwargs["objective_floor_col"] = "floor_metric"
    elif case == "objective_floor_nan":
        kwargs.update({
            "objective_floor_col": "floor_metric",
            "objective_floor": float("nan"),
        })
    elif case == "interaction_objective":
        kwargs["interaction_objective"] = {(7, 8): 1.0}
    elif case == "interaction_floor":
        kwargs.update({
            "interaction_floor_weights": {(7, 8): 1.0},
            "interaction_floor": 1.0 - 1e-9,
        })
    elif case == "interaction_floor_pair_missing":
        kwargs["interaction_floor_weights"] = {(7, 8): 1.0}
    elif case == "max_salary_fire":
        kwargs["max_salary"] = 49_950
    elif case == "max_salary_budget_inert":
        kwargs["max_salary"] = 50_000
    return kwargs


_PARITY_MATRIX = (
    "flex_rb", "flex_wr", "flex_te",
    "salary_49000", "salary_50000",
    "salary_48999_infeasible", "salary_50001_infeasible",
    "max_salary_fire", "max_salary_budget_inert",
    "team_eight", "team_nine_infeasible",
    "one_game_legacy", "empty_game_legacy", "none_game_legacy",
    "two_game_enforced",
    "stack_none", "stack_default", "stack_money",
    "stack_qb_max", "stack_bring_max",
    "stack_allow_rb_dst", "stack_require_rb_dst",
    "stack_allow_two_rb", "stack_require_two_rb",
    "stack_conflict_rb_dst", "stack_conflict_two_rb",
    "stack_invalid_min", "stack_invalid_max",
    "stack_invalid_bring_min", "stack_invalid_bring_max",
    "lock", "ban", "no_good", "no_good_unknown",
    "lock_unknown", "ban_unknown",
    "punt_salary", "punt_strict", "punt_unavailable_inert",
    "punt_strict_zero_eligible",
    "value2", "value2_insufficient_inert",
    "own_on", "own_string_zero", "own_missing_inert",
    "own_insufficient_bands_inert",
    "maxpg_env", "maxpg_explicit_zero", "maxpg_none_uncapped",
    "lowown", "lowown_missing_inert",
    "lowown_requested_above_available_clamps",
    "game_lock", "game_lock_insufficient_inert",
    "objective_floor", "objective_floor_pair_missing",
    "objective_floor_nan", "interaction_objective",
    "interaction_floor", "interaction_floor_pair_missing",
    "infeasible_no_qb", "tie_input", "tie_reversed",
)


def _run_optimizer_with_model_receipt(
    module,
    case: str,
) -> tuple[str, str, tuple[object, ...] | None]:
    """Capture a deterministic receipt without depending on the new helper."""
    constructed = []
    original_init = pulp.LpProblem.__init__

    def capture_init(problem, *args, **kwargs):
        original_init(problem, *args, **kwargs)
        constructed.append(problem)

    pulp.LpProblem.__init__ = capture_init
    try:
        lineup = None
        error = None
        try:
            lineup = module.optimize(
                _matrix_pool(case),
                **_matrix_kwargs(case, module.StackRules),
            )
        except Exception as exc:  # exact historical exception is the contract
            error = f"{type(exc).__name__}: {exc}"
    finally:
        pulp.LpProblem.__init__ = original_init

    assert len(constructed) == 1
    problem = constructed[0]
    return (
        hashlib.sha256(str(problem).encode("utf-8")).hexdigest(),
        error or pulp.LpStatus[problem.status],
        None if lineup is None else tuple(
            player["id"] for player in lineup.players
        ),
    )


# Generated once from the exact pre-refactor blob identified at the top of
# this file.  Runtime tests intentionally do not require Git metadata, so this
# remains valid in the repository's clean-archive/Cloud Build test path.
_PRE_REFACTOR_MATRIX = {
    "flex_rb": ("02e9bd2df312b43a447e6f17c5c2d452d5ad2cb2def981096cfb4afa1611a648", "Optimal", (100, 101, 102, 103, 104, 105, 106, 107, 108)),
    "flex_wr": ("58648f2851efedd03b490da91538b58c4f03a03c7ea409a6e4a8926219ba99c3", "Optimal", (100, 101, 102, 103, 104, 105, 106, 107, 108)),
    "flex_te": ("ccfed603f250e4bcdc1323b57dc432bc1cd43cd84f501ecb8a96121ef704c2d2", "Optimal", (100, 101, 102, 103, 104, 105, 106, 107, 108)),
    "salary_49000": ("d3ce7f6d604517a2966d675f5ad352e3ceb95eecd5f045af1cdc1859c770e80d", "Optimal", (100, 101, 102, 103, 104, 105, 106, 107, 108)),
    "salary_50000": ("7151eda2a88835680d643af615ad1e595fb1867d1b99ca2ce8178cedbb0efa81", "Optimal", (100, 101, 102, 103, 104, 105, 106, 107, 108)),
    "salary_48999_infeasible": ("b6cd468dbe5383054f621f0cf03213a8fb23aa20f0cbea5d7ffcc490c871c5f8", "Infeasible", None),
    "salary_50001_infeasible": ("b82d6d91eecd124276881ab4c19b62920cea6f55761b435bcc57d085dbf14848", "Infeasible", None),
    "max_salary_fire": ("fc7dcc366b93b3ad2915f53cbec6418d0635551f2de4f651184fe756693edcbd", "Optimal", (7, 12, 19, 32, 44, 45, 49, 58, 62)),
    "max_salary_budget_inert": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "team_eight": ("2da141403f5d7c5578b3ca5f37c67a95701247875a7e88c0e8dc5d7eada3b179", "Optimal", (100, 101, 102, 103, 104, 105, 106, 107, 108)),
    "team_nine_infeasible": ("d8c443eb81fe047309cc9e1e6131c9ae23596229c0a76e75e125bbbf0534b9d7", "Infeasible", None),
    "one_game_legacy": ("5e2d198b24cd6ca800f4a46907bccbb4103ae68ca9310d1b2a4c249516f7be99", "Optimal", (100, 101, 102, 103, 104, 105, 106, 107, 108)),
    "empty_game_legacy": ("5e2d198b24cd6ca800f4a46907bccbb4103ae68ca9310d1b2a4c249516f7be99", "Optimal", (100, 101, 102, 103, 104, 105, 106, 107, 108)),
    "none_game_legacy": ("5e2d198b24cd6ca800f4a46907bccbb4103ae68ca9310d1b2a4c249516f7be99", "Optimal", (100, 101, 102, 103, 104, 105, 106, 107, 108)),
    "two_game_enforced": ("c0adda858e566f2590ed7d0843890984e57a365e2a95a16b1b24da93602a89ab", "Optimal", (100, 101, 102, 103, 104, 105, 107, 108, 999)),
    "stack_none": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "stack_default": ("c48dbe85f165fdcc21716f4fd9b1ebe2f5af0d05a799593cb44c526706146266", "Optimal", (7, 12, 19, 32, 44, 45, 49, 58, 62)),
    "stack_money": ("c71b4545b2cc60ea1975bbd46ce4208840f59351cab4b10af1cc563687e96333", "Optimal", (1, 7, 12, 32, 40, 44, 49, 52, 58)),
    "stack_qb_max": ("10402fcb943cb4daa11c1265e8e997bc32dec9329768ab28b7fa7c32e7968687", "Optimal", (7, 12, 19, 32, 44, 45, 49, 58, 62)),
    "stack_bring_max": ("e35e82b39884da3bc61ea579c4bbf99063b83d6b4d0d32e06b9488d2af281879", "Optimal", (7, 12, 15, 19, 32, 40, 44, 49, 58)),
    "stack_allow_rb_dst": ("d542448aced725dcf61bd422fe864c8387c6b1cf3c0e61790055b9677da269c4", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "stack_require_rb_dst": ("1a49f05bec9f1378591601e7eef1ecd5e908c0938311289c7b628cf7f0d0743a", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "stack_allow_two_rb": ("d5d6d13ef90f73da89b4e54ccbd24669670b51100016026682d9863a7f2077e4", "Optimal", (7, 12, 19, 32, 44, 45, 49, 58, 62)),
    "stack_require_two_rb": ("1e8b0ef7e9ce955522d6b83ae40208fd8358ed5dfe4e46bf8020850a8670a21f", "Optimal", (4, 7, 11, 19, 32, 52, 56, 58, 62)),
    "stack_conflict_rb_dst": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "ValueError: RB-versus-DST cannot be both forbidden and required", None),
    "stack_conflict_two_rb": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "ValueError: same-team RBs cannot be both forbidden and required", None),
    "stack_invalid_min": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "ValueError: qb_stack_min must be one nonnegative integer", None),
    "stack_invalid_max": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "ValueError: qb_stack_max must be an integer at least its minimum", None),
    "stack_invalid_bring_min": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "ValueError: bring_back_min must be one nonnegative integer", None),
    "stack_invalid_bring_max": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "ValueError: bring_back_max must be an integer at least its minimum", None),
    "lock": ("a0601d0b3a9d5d7c1a5d99a3b25c598f90600e7e0314fe402c94303d571f5879", "Optimal", (7, 12, 19, 23, 44, 49, 58, 62, 65)),
    "ban": ("f890eeb98b1bdf83f1b721aeef1fb343cdeaa932601825d3065f8751d86c574c", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "no_good": ("19e897f116376f8a55f022a2b02dfbc4bdbd9b3fb3cdf2c5fbcdb1d971880473", "Optimal", (7, 12, 19, 32, 44, 45, 49, 58, 62)),
    "no_good_unknown": ("19e897f116376f8a55f022a2b02dfbc4bdbd9b3fb3cdf2c5fbcdb1d971880473", "Optimal", (7, 12, 19, 32, 44, 45, 49, 58, 62)),
    "lock_unknown": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "KeyError: 9999", None),
    "ban_unknown": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "KeyError: 9999", None),
    "punt_salary": ("5f853c95a7a0fa41822ef41a8cad7557840445d178c7908cce5cb5551c3aa13d", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "punt_strict": ("001034d21552a225803d15c9954acc65aab9effda417d3c5bd0221712cab8f01", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "punt_unavailable_inert": ("86b807def088df896ea73718aaa4574b7eae2b18a0862cad0696b3dd5d9a3979", "Optimal", (4, 19, 32, 36, 39, 44, 49, 52, 58)),
    "punt_strict_zero_eligible": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "value2": ("b8410381ab60c8786667d87c2fbc293cb6cebc9ec91ca4a5dcddc4dedaac94e2", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "value2_insufficient_inert": ("b4dd2d7185aa412ad65d9c6030a07c0e7641597026b8da2a9cb188f7e7c17f3d", "Optimal", (1, 4, 33, 35, 48, 54, 56, 59, 63)),
    "own_on": ("f48c4dd02ef4ec5001862046fd79525cb10692ab94e31d3136c59d5366ea20da", "Optimal", (7, 12, 19, 32, 44, 45, 49, 58, 62)),
    "own_string_zero": ("f48c4dd02ef4ec5001862046fd79525cb10692ab94e31d3136c59d5366ea20da", "Optimal", (7, 12, 19, 32, 44, 45, 49, 58, 62)),
    "own_missing_inert": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "own_insufficient_bands_inert": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "maxpg_env": ("87f33a4c40e312d5a3987e3e08d39a768cf2a28d78e943c5140ba08c0331e156", "Optimal", (7, 12, 19, 22, 23, 32, 49, 58, 62)),
    "maxpg_explicit_zero": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "maxpg_none_uncapped": ("da1392c8ccb6a5b0bda3fc6671db46e16102f5b16f31f9f2b5673c52db0fcfb5", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "lowown": ("e25a34a93ff1f0451d37bfab39f5ff07a6b7732ce2d0e46df1e350fec85df8e9", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "lowown_missing_inert": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "lowown_requested_above_available_clamps": ("0c9bc1caba0c524e8926c54f81f17289e7a7e3371501a8f90b0e2f2475cbb136", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "game_lock": ("6f7b73328f7e4e0e9ff4f477935ba16249cb8af10ac8f79d333da3703b880c40", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "game_lock_insufficient_inert": ("bba0897fe89e2700523413c5394e376f9e45d24b1f042ddfea9be075e472394f", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "objective_floor": ("1e786744c46ba7951b48e2917284246963541725f9cb472c631137a99262d658", "Optimal", (4, 7, 11, 12, 19, 32, 36, 49, 52)),
    "objective_floor_pair_missing": ("a55b7d71d9558b8f59a900a987309f1a7829564fc97b6db5cd6accc4ed2f6551", "ValueError: objective floor column and value must be provided together", None),
    "objective_floor_nan": ("a55b7d71d9558b8f59a900a987309f1a7829564fc97b6db5cd6accc4ed2f6551", "ValueError: objective floor must be finite", None),
    "interaction_objective": ("fefcacd2997a3563180ab27532d8a67078f5188193424e45f5f94de84ebb3279", "Optimal", (7, 8, 20, 27, 39, 44, 46, 54, 57)),
    "interaction_floor": ("173f95cf618ce827bc67fd2d5716eed57d2bf34298ba848d05ca262b78b63e47", "Optimal", (4, 7, 8, 11, 19, 32, 36, 49, 58)),
    "interaction_floor_pair_missing": ("1b3803b965382f3313f2221ef5f00170eedf4d3ea7706429b568afe560ce6ae7", "ValueError: interaction floor weights and value must be provided together", None),
    "infeasible_no_qb": ("919cce6f7c6bf12fd245e17d0c311d191a3aab58bf6aa3ef71653401b044762b", "Infeasible", None),
    "tie_input": ("f5e254be8416d38bbfe65214ec879cfa070ee8209de43af7c9d78ef86b47df9a", "Optimal", (11, 16, 18, 20, 24, 46, 52, 61, 65)),
    "tie_reversed": ("f5e254be8416d38bbfe65214ec879cfa070ee8209de43af7c9d78ef86b47df9a", "Optimal", (65, 61, 52, 46, 24, 20, 18, 16, 11)),
}


@pytest.mark.parametrize("case", _PARITY_MATRIX)
def test_full_pre_refactor_lp_status_and_ordered_roster_corpus(case):
    assert _run_optimizer_with_model_receipt(lineup_module, case) == (
        _PRE_REFACTOR_MATRIX[case]
    )


def test_persisted_corpus_reproduces_from_independent_git_blob():
    """Regenerate the corpus when Git history is available.

    Clean source archives deliberately omit ``.git``; their ordinary parity
    tests use the persisted receipts above.  A developer checkout additionally
    proves those receipts came from the immutable pre-extraction source rather
    than from the new helper under test.
    """
    repository = Path(__file__).resolve().parents[1]
    try:
        source = subprocess.check_output(
            [
                "git", "show",
                f"{_PRE_REFACTOR_COMMIT}:src/nfl_dfs/optimizer/lineup.py",
            ],
            cwd=repository,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("pre-refactor Git blob is unavailable in this source archive")
    assert hashlib.sha256(source).hexdigest() == _PRE_REFACTOR_SOURCE_SHA256

    module_name = "_pre_refactor_lineup_parity_reference"
    legacy = types.ModuleType(module_name)
    legacy.__file__ = "pre_refactor_lineup.py"
    sys.modules[module_name] = legacy
    try:
        exec(compile(source, legacy.__file__, "exec"), legacy.__dict__)
        regenerated = {
            case: _run_optimizer_with_model_receipt(legacy, case)
            for case in _PARITY_MATRIX
        }
    finally:
        sys.modules.pop(module_name, None)
    assert regenerated == _PRE_REFACTOR_MATRIX


def test_production_constructs_exactly_one_default_cbc_solver(monkeypatch):
    calls = []
    real_constructor = pulp.PULP_CBC_CMD

    def capture_constructor(*args, **kwargs):
        calls.append((args, kwargs))
        return real_constructor(*args, **kwargs)

    monkeypatch.setattr(lineup_module.pulp, "PULP_CBC_CMD", capture_constructor)
    assert optimize(_pool(), env={}) is not None
    assert calls == [((), {"msg": 0})]


def test_explicit_research_domain_is_immune_to_process_environment(monkeypatch):
    players = _pool()
    frozen = {
        "budget": 50_000,
        "min_salary": 49_000,
        "max_per_game": 0,
        "punt_max_salary": None,
        "punt_min": 0,
        "locks": None,
        "bans": None,
        "banned_lineups": [],
        "env": {},
        "stack": StackRules(
            qb_stack_min=2,
            bring_back_min=1,
            forbid_rb_vs_dst=True,
            forbid_two_rb_same_team=True,
        ),
    }
    clean_problem, clean_roster = _direct_shared_solve(players, **frozen)
    for key, value in {
        "MIN_LINEUP_SALARY": "50000",
        "PUNT_STRICT": "1",
        "VALUE2_MIN": "9",
        "VALUE2_MAX": "9000",
        "OWN_BARBELL": "1",
        "MAX_PER_GAME": "1",
        "MIN_LOWOWN": "9",
    }.items():
        monkeypatch.setenv(key, value)
    hostile_problem, hostile_roster = _direct_shared_solve(players, **frozen)
    assert clean_problem.toDict()["constraints"] == (
        hostile_problem.toDict()["constraints"]
    )
    assert clean_roster == hostile_roster
