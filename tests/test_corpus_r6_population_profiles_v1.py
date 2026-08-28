from __future__ import annotations

from copy import deepcopy

import pulp
import pytest

from nfl_dfs.optimizer.lineup import StackRules
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles
from nfl_dfs.research import residual_world_columns as rw


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows = (
        ("dst-g", "DST", "G", "H", "g4"),
        ("dst-i", "DST", "I", "J", "g5"),
        ("q-a", "QB", "A", "B", "g1"),
        ("q-c", "QB", "C", "D", "g2"),
        ("rb-b", "RB", "B", "A", "g1"),
        ("rb-c", "RB", "C", "D", "g2"),
        ("rb-e", "RB", "E", "F", "g3"),
        ("rb-g", "RB", "G", "H", "g4"),
        ("rb-j", "RB", "J", "I", "g5"),
        ("te-a", "TE", "A", "B", "g1"),
        ("te-b", "TE", "B", "A", "g1"),
        ("te-c", "TE", "C", "D", "g2"),
        ("te-g", "TE", "G", "H", "g4"),
        ("wr-a", "WR", "A", "B", "g1"),
        ("wr-b", "WR", "B", "A", "g1"),
        ("wr-c", "WR", "C", "D", "g2"),
        ("wr-d", "WR", "D", "C", "g2"),
        ("wr-e", "WR", "E", "F", "g3"),
        ("wr-f", "WR", "F", "E", "g3"),
        ("wr-g", "WR", "G", "H", "g4"),
        ("wr-h", "WR", "H", "G", "g4"),
    )
    return tuple(sorted((
        rw.PlayerSpec(player_id, position, team, opponent, game_id, 5_500)
        for player_id, position, team, opponent, game_id in rows
    ), key=lambda player: player.player_id))


F7_OPEN_ROSTER = tuple(sorted((
    "q-a", "rb-c", "rb-e", "wr-c", "wr-d", "wr-e", "wr-f", "te-c",
    "dst-i",
)))
F8_CAP3_ROSTER = tuple(sorted((
    "q-a", "rb-c", "rb-e", "wr-c", "wr-d", "wr-e", "wr-f", "te-g",
    "dst-i",
)))
F9_SINGLE_ROSTER = tuple(sorted((
    "q-a", "rb-b", "rb-c", "wr-a", "wr-c", "wr-d", "wr-e", "te-b",
    "dst-i",
)))


def _accepts(
    players: tuple[rw.PlayerSpec, ...], roster: tuple[str, ...], profile_id: str
) -> bool:
    try:
        profiles.audit_profile_roster_v1(players, roster, profile_id)
    except profiles.CorpusR6PopulationProfileError:
        return False
    return True


def _solve_target(
    players: tuple[rw.PlayerSpec, ...],
    target: tuple[str, ...],
    profile_id: str,
) -> tuple[str, ...]:
    objective = tuple(
        1_000_000 if player.player_id in target else 0 for player in players
    )
    model = profiles.build_profile_model_v1(
        players,
        profile_id,
        objective,
        construction_serial=0,
        model_name=f"fixture_{profile_id}",
    )
    status = model.problem.solve(pulp.PULP_CBC_CMD(msg=False))
    assert status == pulp.LpStatusOptimal
    return tuple(sorted(
        player_id for player_id, variable in model.decision.items()
        if variable.value() is not None and variable.value() > 0.5
    ))


def _identity(uri: str, generation: int, marker: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": marker * 64,
        "bytes": 123,
    }


def _solver() -> dict[str, object]:
    return {
        "name": "cbc",
        "version": "2.10.3",
        "binary_sha256": "c" * 64,
        "options_sha256": "d" * 64,
        "exact_mode": True,
    }


def test_registry_has_three_explicit_nonproduction_profiles():
    registry = profiles.population_profile_registry_v1()
    rows = profiles.population_profiles_v1()
    assert tuple(row.profile_id for row in rows) == profiles.PROFILE_ORDER
    assert tuple(row.ordinal for row in rows) == (7, 8, 9)
    assert tuple(row.fingerprint for row in rows) == (
        "37fb69bc54b381ae81531b6b8e21d4adaade9ec8d224463cba315dca067c7dbf",
        "eb3bb475e6d515ea93e61039069d1c703c233ff87ce9bf27c28ff93ca12dc7ee",
        "3e297629fc5826437a39352152c1680c949770c05c60c30b48edf54ed9ea8861",
    )
    assert registry["registry_sha256"] == (
        "1faecb2a8b7704743b39978e87ffbe3b3e59734b1f70cd38560a781a653ce5cc"
    )
    assert registry["profiles"] == [row.payload() for row in rows]
    assert registry["production_default_change_licensed"] is False
    opposing_wr_audit = next(
        row for row in registry["legacy_constraint_audit"]
        if row["rule"] == "opposing WR mandate"
    )
    assert opposing_wr_audit["global_hard_rule_found"] is False
    assert "thesis locks must be absent" in opposing_wr_audit["disposition"]

    f7, f8, f9 = rows
    assert (f7.qb_partner_min, f7.bring_back_min, f7.max_from_game) == (
        0, 0, None,
    )
    # F8 is deliberately F7 + one cap.  Keeping incumbent QB+2 and one
    # bring-back would require four players from the QB game and be infeasible.
    assert (
        f8.qb_partner_min,
        f8.bring_back_min,
        f8.max_from_game,
        f8.comparison_base_profile_id,
    ) == (0, 0, 3, f7.profile_id)
    assert (
        f9.qb_partner_min,
        f9.qb_partner_max,
        f9.bring_back_min,
        f9.max_from_game,
    ) == (1, 1, 1, None)


def test_profiles_compile_to_complete_direct_model_doses_without_env_or_locks():
    for row in profiles.population_profiles_v1():
        effective = row.as_effective_policy()
        assert effective.parameter_set_id == row.profile_id
        assert effective.parameter_set_sha256 == row.fingerprint
        assert effective.constraints.budget == 50_000
        assert effective.constraints.min_salary == 49_000
        assert effective.constraints.locks == ()
        assert effective.constraints.bans == ()
        assert effective.constraints.game_lock is None
        assert effective.constraints.env == ()
        assert effective.stack.require_rb_vs_dst is False
        assert effective.stack.require_two_rb_same_team is False
    assert [
        row.as_effective_policy().constraints.max_per_game
        for row in profiles.population_profiles_v1()
    ] == [0, 3, 0]


def test_synthetic_vacuity_matrix_proves_all_three_feasible_sets_differ():
    players = _players()
    rosters = (F7_OPEN_ROSTER, F8_CAP3_ROSTER, F9_SINGLE_ROSTER)
    signatures = {
        profile_id: tuple(_accepts(players, roster, profile_id) for roster in rosters)
        for profile_id in profiles.PROFILE_ORDER
    }
    assert signatures == {
        "F7-qb-and-bringback-relaxed": (True, True, True),
        "F8-game-cap-3": (False, True, False),
        "F9-single-partner": (False, False, True),
    }
    assert len(set(signatures.values())) == 3


@pytest.mark.parametrize(
    ("profile_id", "target"),
    tuple(zip(
        profiles.PROFILE_ORDER,
        (F7_OPEN_ROSTER, F8_CAP3_ROSTER, F9_SINGLE_ROSTER),
        strict=True,
    )),
)
def test_each_profile_is_executable_and_selects_its_target(
    profile_id: str, target: tuple[str, ...]
):
    players = _players()
    selected = _solve_target(players, target, profile_id)
    assert selected == target
    profiles.audit_profile_roster_v1(players, selected, profile_id)


def test_f7_really_allows_naked_qb_without_bringback_and_f8_caps_game():
    players = _players()
    f7_shape = profiles.audit_profile_roster_v1(
        players, F7_OPEN_ROSTER, profiles.PROFILE_ORDER[0]
    )
    assert f7_shape["qb_partner_count"] == 0
    assert f7_shape["bring_back_count"] == 0
    assert f7_shape["max_from_game"] == 4
    f8_shape = profiles.audit_profile_roster_v1(
        players, F8_CAP3_ROSTER, profiles.PROFILE_ORDER[1]
    )
    assert f8_shape["qb_partner_count"] == 0
    assert f8_shape["bring_back_count"] == 0
    assert f8_shape["max_from_game"] == 3


def test_f9_requires_exactly_one_partner_not_an_opposing_wr():
    shape = profiles.audit_profile_roster_v1(
        _players(), F9_SINGLE_ROSTER, profiles.PROFILE_ORDER[2]
    )
    assert shape["qb_partner_count"] == 1
    assert shape["bring_back_count"] == 2
    assert shape["opposing_wr_count"] == 0


def test_inherited_hardcoded_structure_is_reported_per_profile_and_rejected():
    surface = profiles.inherited_constraint_surface_v1(
        stack=StackRules(qb_stack_min=2, bring_back_min=1),
        max_per_game=4,
        game_lock=("g1", 5),
        environment={"SINGLE_STACK_BOOM_SOLVES": "8"},
        opposing_wr_min=1,
        forced_qb_wr_pair_count=1,
        forced_qb_wr_opposing_wr_triplet_count=1,
    )
    conflicts = profiles.inherited_constraint_conflicts_v1(surface)
    assert {row["profile_id"] for row in conflicts} == set(profiles.PROFILE_ORDER)
    assert {
        row["rule"] for row in conflicts
    } >= {
        "qb_partner_min",
        "bring_back_min",
        "opposing_wr_min",
        "max_from_game",
        "min_from_game",
        "forced_qb_wr_pair_count",
        "forced_qb_wr_opposing_wr_triplet_count",
        "environment:SINGLE_STACK_BOOM_SOLVES",
    }
    with pytest.raises(profiles.InheritedConstraintConflict) as error:
        profiles.require_neutral_inherited_constraints_v1(surface)
    assert error.value.conflicts == conflicts


@pytest.mark.parametrize(
    "key",
    sorted(profiles.STRUCTURE_ENV_KEYS),
)
def test_every_known_ambient_structure_override_fails_closed(key: str):
    surface = profiles.inherited_constraint_surface_v1(environment={key: "0"})
    with pytest.raises(profiles.InheritedConstraintConflict) as error:
        profiles.require_neutral_inherited_constraints_v1(surface)
    assert {row["rule"] for row in error.value.conflicts} == {
        f"environment:{key}"
    }


def test_neutral_surface_is_accepted_and_does_not_mutate_stack_defaults():
    before = StackRules()
    surface = profiles.inherited_constraint_surface_v1(
        stack=StackRules(qb_stack_min=0, bring_back_min=0),
        environment={"UNRELATED_SETTING": "retained"},
    )
    assert surface.neutral
    profiles.require_neutral_inherited_constraints_v1(surface)
    assert StackRules() == before


def test_shared_plan_binds_equal_work_provenance_and_is_order_deterministic():
    sources = {
        "2024-w02": _identity("gs://fixture/2024-w02.json", 2, "b"),
        "2023-w01": _identity("gs://fixture/2023-w01.json", 1, "a"),
    }
    schedules = {"2024-w02": "2" * 64, "2023-w01": "1" * 64}
    work = profiles.SharedSolverWork(solve_attempts_per_block=2)
    kwargs = {
        "run_id": "fixture-f7-f9-shared-bank-v1",
        "source_identities_by_slate": sources,
        "world_schedule_sha256_by_slate": schedules,
        "source_commit_sha": "e" * 40,
        "module_sha256": "f" * 64,
        "solver_identity": _solver(),
        "inherited_surface": profiles.InheritedConstraintSurface(),
        "work": work,
    }
    plan = profiles.build_shared_historical_bank_plan_v1(**kwargs)
    reversed_plan = profiles.build_shared_historical_bank_plan_v1(
        **{
            **kwargs,
            "source_identities_by_slate": dict(reversed(list(sources.items()))),
            "world_schedule_sha256_by_slate": dict(
                reversed(list(schedules.items()))
            ),
        }
    )
    assert plan == reversed_plan
    assert [row["slate_id"] for row in plan["sources"]] == [
        "2023-w01", "2024-w02",
    ]
    assert len(set(plan["work_sha256_by_profile"].values())) == 1
    assert plan["total_solve_attempts"] == 2 * 3 * 5 * 2
    assert plan["code_identity"] == {
        "source_commit_sha": "e" * 40,
        "module_path": profiles.MODULE_PATH,
        "module_sha256": "f" * 64,
    }
    assert plan["production_default_changes"] == []
    assert plan["production_change_licensed"] is False
    assert profiles.validate_shared_historical_bank_plan_v1(plan) == plan


def test_equal_work_iterator_has_identical_ordered_lattice_per_profile():
    work = profiles.SharedSolverWork(solve_attempts_per_block=3)
    cells = tuple(profiles.iter_equal_work_cells_v1(work))
    by_profile = {
        profile_id: tuple(
            (block, visit) for candidate_id, block, visit in cells
            if candidate_id == profile_id
        )
        for profile_id in profiles.PROFILE_ORDER
    }
    assert len(set(by_profile.values())) == 1
    assert len(next(iter(by_profile.values()))) == 15


def test_shared_plan_rejects_rehashed_unequal_profile_work():
    plan = profiles.build_shared_historical_bank_plan_v1(
        run_id="fixture-f7-f9-shared-bank-v1",
        source_identities_by_slate={
            "2023-w01": _identity("gs://fixture/2023-w01.json", 1, "a")
        },
        world_schedule_sha256_by_slate={"2023-w01": "1" * 64},
        source_commit_sha="e" * 40,
        module_sha256="f" * 64,
        solver_identity=_solver(),
        inherited_surface=profiles.InheritedConstraintSurface(),
        work=profiles.SharedSolverWork(solve_attempts_per_block=1),
    )
    poisoned = deepcopy(plan)
    poisoned["work_sha256_by_profile"][profiles.PROFILE_ORDER[2]] = "0" * 64
    poisoned["plan_sha256"] = profiles.canonical_sha256_v1({
        key: value for key, value in poisoned.items() if key != "plan_sha256"
    })
    with pytest.raises(
        profiles.CorpusR6PopulationProfileError,
        match="per-profile solver work differs",
    ):
        profiles.validate_shared_historical_bank_plan_v1(poisoned)


def test_bank_plan_rejects_inherited_incumbent_stack_before_any_solve():
    with pytest.raises(profiles.InheritedConstraintConflict):
        profiles.build_shared_historical_bank_plan_v1(
            run_id="fixture-f7-f9-shared-bank-v1",
            source_identities_by_slate={
                "2023-w01": _identity("gs://fixture/2023-w01.json", 1, "a")
            },
            world_schedule_sha256_by_slate={"2023-w01": "1" * 64},
            source_commit_sha="e" * 40,
            module_sha256="f" * 64,
            solver_identity=_solver(),
            inherited_surface=profiles.inherited_constraint_surface_v1(
                stack=StackRules(qb_stack_min=2, bring_back_min=1)
            ),
            work=profiles.SharedSolverWork(solve_attempts_per_block=1),
        )
