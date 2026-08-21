from __future__ import annotations

from dataclasses import fields, replace
from itertools import combinations, product
import json
import os
from pathlib import Path

import numpy as np
import pulp
import pytest

from nfl_dfs.research import corpus_legal_feasibility as core
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_parametric_batch import (
    PARAMETER_ORDER,
    PARAMETER_SET_ORDER,
    frozen_parameter_sets,
)
from nfl_dfs.research.effective_policy_rule_inventory import (
    generate_effective_policy_rule_inventory,
)
from nfl_dfs.research.lr8_later_period_source import PreparedLaterSlate


ROOT = Path(__file__).resolve().parents[1]


def _players(*, salary: int = 5_500) -> tuple[rw.PlayerSpec, ...]:
    rows = (
        ("q-a", "QB", "A", "B", "g1"),
        ("q-c", "QB", "C", "D", "g2"),
        ("rb-a1", "RB", "A", "B", "g1"),
        ("rb-a2", "RB", "A", "B", "g1"),
        ("rb-b", "RB", "B", "A", "g1"),
        ("rb-c", "RB", "C", "D", "g2"),
        ("rb-d", "RB", "D", "C", "g2"),
        ("rb-e", "RB", "E", "F", "g3"),
        ("wr-a1", "WR", "A", "B", "g1"),
        ("wr-a2", "WR", "A", "B", "g1"),
        ("wr-b", "WR", "B", "A", "g1"),
        ("wr-c1", "WR", "C", "D", "g2"),
        ("wr-c2", "WR", "C", "D", "g2"),
        ("wr-d", "WR", "D", "C", "g2"),
        ("wr-e", "WR", "E", "F", "g3"),
        ("wr-f", "WR", "F", "E", "g3"),
        ("te-a", "TE", "A", "B", "g1"),
        ("te-b", "TE", "B", "A", "g1"),
        ("te-c", "TE", "C", "D", "g2"),
        ("te-d", "TE", "D", "C", "g2"),
        ("te-e", "TE", "E", "F", "g3"),
        ("dst-b", "DST", "B", "A", "g1"),
        ("dst-c", "DST", "C", "D", "g2"),
        ("dst-e", "DST", "E", "F", "g3"),
    )
    return tuple(sorted((
        rw.PlayerSpec(player_id, position, team, opponent, game_id, salary)
        for player_id, position, team, opponent, game_id in rows
    ), key=lambda player: player.player_id))


def _hard_legal_rosters(
    players: tuple[rw.PlayerSpec, ...], *, count: int, house_clean: bool,
) -> tuple[tuple[str, ...], ...]:
    by_position = {
        position: [
            player.player_id for player in players
            if player.position == position
        ]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    result: list[tuple[str, ...]] = []
    for qb, rbs, wrs, te, dst in product(
        by_position["QB"],
        combinations(by_position["RB"], 2),
        combinations(by_position["WR"], 4),
        by_position["TE"],
        by_position["DST"],
    ):
        roster = tuple(sorted((qb, *rbs, *wrs, te, dst)))
        try:
            core.audit_dk_classic(players, roster)
            violations = core.house_rule_violations(players, roster)
        except core.CorpusLegalFeasibilityError:
            continue
        if house_clean and violations:
            continue
        result.append(roster)
        if len(result) == count:
            return tuple(result)
    raise AssertionError(f"test catalog produced only {len(result)} rosters")


@pytest.fixture(scope="module")
def players() -> tuple[rw.PlayerSpec, ...]:
    return _players()


@pytest.fixture(scope="module")
def clean_rosters(players) -> tuple[tuple[str, ...], ...]:
    return _hard_legal_rosters(players, count=100, house_clean=True)


@pytest.fixture(scope="module")
def inventory() -> dict[str, object]:
    return generate_effective_policy_rule_inventory(ROOT)


@pytest.fixture(scope="module")
def prepared(players, clean_rosters) -> PreparedLaterSlate:
    world_ids = tuple(
        rw.WorldId(block, index)
        for block in rw.WORLD_BLOCKS
        for index in range(rw.WORLDS_PER_BLOCK)
    )
    row = np.arange(len(players), dtype=np.float32)[:, None]
    column = (
        np.arange(core.EXPECTED_WORLD_COUNT, dtype=np.float32)[None, :] % 17
    ) / np.float32(100.0)
    draws = np.ascontiguousarray(np.float32(8.0) + row / 10 + column)
    draws.flags.writeable = False
    return PreparedLaterSlate(
        season=2023,
        week=1,
        slate_id="2023-w01",
        players=players,
        world_ids=world_ids,
        player_draws=draws,
        incumbent_candidates=clean_rosters[:88],
        source_freeze_sha256="a" * 64,
        artifact_sha256_by_block={
            block: f"{index + 1:064x}"
            for index, block in enumerate(rw.WORLD_BLOCKS)
        },
    )


def _capture_solver(roster, sink):
    def solve(request: core.SolveRequest) -> core.SolveOutcome:
        sink.append({
            "request": request,
            "problem": request.model.problem,
            "problem_text": str(request.model.problem),
            "player_ids": tuple(
                player.player_id for player in request.model.players
            ),
            "objective": request.objective_micro,
        })
        return core._make_mock_optimal_outcome(request, roster)

    return solve


def test_exact_profile_mapping_covers_five_fields_and_seven_sets():
    profiles = core.frozen_policy_profiles()
    parameter_sets = frozen_parameter_sets()
    assert tuple(profile.parameter_set_id for profile in profiles) == (
        PARAMETER_SET_ORDER
    )
    assert len(profiles) == 7
    for profile, parameter_set in zip(profiles, parameter_sets, strict=True):
        values = parameter_set["values"]
        assert dict(profile.parameter_values) == values
        assert profile.constraints.min_salary == values["min_lineup_salary"]
        assert profile.constraints.budget == 50_000
        assert profile.constraints.locks == ()
        assert profile.constraints.bans == ()
        assert profile.constraints.banned_lineups == ()
        assert profile.constraints.punt_max_salary is None
        assert profile.constraints.punt_min == 0
        assert profile.constraints.game_lock is None
        assert profile.constraints.max_per_game == 0
        assert profile.constraints.env == ()
        assert profile.stack.as_payload() == {
            "qb_stack_min": values["qb_stack_min"],
            "bring_back_min": values["bring_back_min"],
            "forbid_rb_vs_dst": values["forbid_rb_vs_dst"],
            "forbid_two_rb_same_team": values["forbid_two_rb_same_team"],
            "qb_stack_max": None,
            "bring_back_max": None,
            "require_rb_vs_dst": False,
            "require_two_rb_same_team": False,
        }
    assert profiles[-1].parameter_set_id == (
        "remove-all-five-shared-constraints"
    )


def test_runtime_policy_binds_every_inventory_and_experimental_rule(
    inventory,
):
    profiles = core.frozen_policy_profiles()
    bindings = [
        core.build_runtime_effective_policy(
            inventory,
            profile,
            visits_per_block=1,
            visit_schedule_sha256="f" * 64,
            ambient_process_keys_present=(),
        )
        for profile in profiles
    ]
    for profile, binding in zip(profiles, bindings, strict=True):
        payload = json.loads(binding.canonical_payload)
        assert binding.rule_count == inventory["rule_count"]
        assert len(payload["rules"]) == inventory["rule_count"]
        assert [row["id"] for row in payload["rules"]] == [
            row["id"] for row in inventory["rules"]
        ]
        assert payload["experimental_rule_set_sha256"] == (
            binding.experimental_rule_set_sha256
        )
        assert [row["id"] for row in payload["experimental_rules"]] == [
            "experimental:matched-fixed-world-schedule",
            "experimental:one-world-optimum-per-visit",
            "experimental:no-production-generation-recipes",
            "experimental:first-occurrence-unique-union",
            "experimental:common-full-world-cross-score",
            "experimental:direct-exact80-line194-selector",
        ]
        core.validate_runtime_effective_policy(
            binding,
            inventory,
            profile,
            visits_per_block=1,
            visit_schedule_sha256="f" * 64,
            ambient_process_keys_present=(),
        )
    assert bindings[0].dk_classic_feasibility_only is False
    assert bindings[-1].dk_classic_feasibility_only is True
    final_rows = json.loads(bindings[-1].canonical_payload)["rules"]
    active_nonparam_house = [
        row for row in final_rows
        if row["classification"] == "house_soft"
        and row["parametric_field"] is None
        and row["baseline_state"] == "active"
    ]
    assert active_nonparam_house
    assert all(
        row["application"] == "not_applicable"
        and row["effective_state"] == "inactive"
        and row["effective_dose"] is None
        for row in active_nonparam_house
    )
    poisoned = replace(
        bindings[0],
        canonical_payload=bindings[0].canonical_payload + b" ",
    )
    with pytest.raises(
        core.CorpusLegalFeasibilityError, match="not canonical"
    ):
        core.validate_runtime_effective_policy(
            poisoned,
            inventory,
            profiles[0],
            visits_per_block=1,
            visit_schedule_sha256="f" * 64,
            ambient_process_keys_present=(),
        )


def test_exact_seven_by_full_schedule_and_fresh_model(
    prepared, clean_rosters, inventory,
):
    calls: list[dict[str, object]] = []
    matrix = core._execute_generation_matrix_for_test(
        prepared,
        inventory,
        solver=_capture_solver(clean_rosters[0], calls),
        semantic_environment={},
        visits_per_block=1,
    )
    assert len(matrix.visit_schedule) == 5
    assert len(calls) == 7 * 5 == len(matrix.attempts)
    assert [attempt.construction_serial for attempt in matrix.attempts] == (
        list(range(35))
    )
    assert len({id(row["problem"]) for row in calls}) == 35
    assert all(attempt.status is core.SolverStatus.OPTIMAL for attempt in matrix.attempts)
    for ordinal in range(7):
        block = calls[ordinal * 5:(ordinal + 1) * 5]
        assert tuple(row["request"].world for row in block) == (
            matrix.visit_schedule
        )
    for visit in range(5):
        objectives = {
            calls[ordinal * 5 + visit]["objective"] for ordinal in range(7)
        }
        assert len(objectives) == 1


def test_variant_result_v2_separates_task_ledger_from_arm_attempt_rows(
    prepared, clean_rosters, inventory,
):
    matrix = core._execute_generation_matrix_for_test(
        prepared,
        inventory,
        solver=_capture_solver(clean_rosters[0], []),
        semantic_environment={},
        visits_per_block=1,
    )
    variant = matrix.variants[0]
    roster = clean_rosters[0]
    selector = core.SelectorReceipt(
        candidate_count=1,
        world_count=core.EXPECTED_WORLD_COUNT,
        entry_count=1,
        tail_line_dk=core.TAIL_LINE_DK,
        selected_indices=(0,),
        tie_law_applied="test-only",
    )
    census = core.ViolationCensus(
        unique_candidate_counts=tuple((name, 0) for name in PARAMETER_ORDER),
        visit_counts=tuple((name, 0) for name in PARAMETER_ORDER),
        selected_counts=tuple((name, 0) for name in PARAMETER_ORDER),
    )
    payload, _ = core._build_variant_result_payload(
        matrix=matrix,
        variant=variant,
        unique=(roster,),
        first_indices=(0,),
        candidate_score_sha256="1" * 64,
        selector=selector,
        selected_rosters=(roster,),
        selected_score_sha256="2" * 64,
        census=census,
    )
    parsed = json.loads(payload)
    attempt_rows = [
        core._attempt_payload(attempt) for attempt in variant.attempts
    ]
    assert parsed["schema"] == (
        "corpus-legal-feasibility-variant-result/v2"
    )
    assert parsed["attempt_ledger_sha256"] == matrix.attempt_ledger_sha256
    assert parsed["variant_attempt_rows_sha256"] == core.canonical_sha256(
        attempt_rows
    )
    assert "variant_attempt_ledger_sha256" not in parsed


def test_hostile_environment_and_player_order_do_not_change_models(
    prepared, clean_rosters, inventory, monkeypatch,
):
    clean_calls: list[dict[str, object]] = []
    core._execute_generation_matrix_for_test(
        prepared,
        inventory,
        solver=_capture_solver(clean_rosters[0], clean_calls),
        semantic_environment={},
        visits_per_block=1,
    )
    reverse = np.arange(len(prepared.players) - 1, -1, -1)
    reversed_draws = np.ascontiguousarray(prepared.player_draws[reverse])
    reversed_draws.flags.writeable = False
    reversed_prepared = replace(
        prepared,
        players=tuple(prepared.players[int(index)] for index in reverse),
        player_draws=reversed_draws,
    )
    hostile = {
        "MIN_LINEUP_SALARY": "50001",
        "MAX_PER_GAME": "1",
        "VALUE2_MIN": "9",
        "MIN_LOWOWN": "9",
        "OWN_BARBELL": "1",
        "PUNT_STRICT": "1",
    }
    for key, value in hostile.items():
        monkeypatch.setenv(key, value)
    hostile_calls: list[dict[str, object]] = []
    core._execute_generation_matrix_for_test(
        reversed_prepared,
        inventory,
        solver=_capture_solver(clean_rosters[0], hostile_calls),
        semantic_environment={},
        visits_per_block=1,
    )
    assert os.environ["MIN_LINEUP_SALARY"] == "50001"
    assert [row["player_ids"] for row in hostile_calls] == [
        row["player_ids"] for row in clean_calls
    ]
    assert [row["objective"] for row in hostile_calls] == [
        row["objective"] for row in clean_calls
    ]
    assert [row["problem_text"] for row in hostile_calls] == [
        row["problem_text"] for row in clean_calls
    ]


def test_authoritative_loader_passes_source_binding_and_path(
    prepared, monkeypatch,
):
    source_binding = core.TaskSourceBinding(
        canonical_payload=b"{}",
        binding_sha256="1" * 64,
        batch_manifest_sha256="2" * 64,
        task_index=0,
        task_sha256="3" * 64,
        artifact_source_authority_completion_object_sha256="4" * 64,
        artifact_source_authority_completion_sha256="5" * 64,
        artifact_source_authority_task_sha256="6" * 64,
        later_source_freeze_manifest_sha256="7" * 64,
        world_artifact_receipt_set_sha256="8" * 64,
    )
    source = core._AuthoritativeSource(
        prepared=prepared, binding=source_binding
    )
    law = core.RegisteredLawBinding(
        canonical_payload=b"{}",
        binding_sha256="9" * 64,
        common_law_sha256="a" * 64,
        code_source_object_sha256="b" * 64,
        code_source_body_sha256="c" * 64,
        immutable_image_sha256="d" * 64,
        runtime_image_terminal_verification_required=True,
        artifact_source_authority_completion_object_sha256="4" * 64,
        artifact_source_authority_completion_sha256="5" * 64,
        artifact_source_authority_task_sha256="6" * 64,
        world_schedule_object_sha256="e" * 64,
        visit_schedule_sha256="f" * 64,
        solver_authority_sha256="0" * 64,
    )
    request = {"task_index": 0, "task_request_sha256": "a" * 64}
    manifest = {"common_law": {}, "batch_manifest_sha256": "2" * 64}
    inventory_value = {
        "classified_input_projection": {
            "ambient_process_keys_requiring_absence": []
        }
    }
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        core,
        "bind_task_request_to_manifest",
        lambda task_request, raw: (request, manifest),
    )

    def load_inventory(*, raw, common_law, repository_root):
        observed["inventory_root"] = repository_root
        return inventory_value

    monkeypatch.setattr(core, "_load_authoritative_inventory", load_inventory)
    monkeypatch.setattr(
        core, "_load_authoritative_source", lambda **kwargs: source
    )
    monkeypatch.setattr(core, "_cbc_runtime_authority", lambda: {})

    def load_law(**kwargs):
        observed["law_root"] = kwargs["repository_root"]
        observed["task_source_binding"] = kwargs["task_source_binding"]
        return law

    monkeypatch.setattr(core, "_load_registered_common_law", load_law)
    loaded = core._load_authoritative_inputs(
        task_request={},
        batch_manifest_bytes=b"{}",
        effective_policy_inventory_bytes=b"{}",
        artifact_source_authority_completion_bytes=b"{}",
        later_source_freeze_bytes=b"{}",
        world_artifact_bodies={},
        common_law_bodies={},
        repository_root=ROOT,
    )
    assert loaded.source is source
    assert loaded.law is law
    assert observed == {
        "inventory_root": ROOT,
        "law_root": ROOT,
        "task_source_binding": source_binding,
    }


def test_first_occurrence_dedup_is_exact_and_stable(clean_rosters):
    a, b, c = clean_rosters[:3]
    unique, first = core.first_occurrence_unique((a, b, a, c, b))
    assert unique == (a, b, c)
    assert first == (0, 1, 3)
    with pytest.raises(core.CorpusLegalFeasibilityError, match="canonical"):
        core.first_occurrence_unique((tuple(reversed(a)),))


def test_selector_uses_first_occurrence_ties_and_fails_short():
    scores = np.zeros((80, 4), dtype=np.float64)
    scores[0, 0] = 200.0
    scores[1, 0] = 200.0
    receipt = core.select_exact80(scores)
    assert receipt.selected_indices == tuple(range(80))
    assert receipt.tie_law_applied.endswith("first_occurrence")
    with pytest.raises(core.InsufficientCandidateSupport, match="at least exact-80"):
        core.select_exact80(scores[:79])
    poisoned = scores.copy()
    poisoned[0, 0] = np.nan
    with pytest.raises(core.InsufficientCandidateSupport, match="finite"):
        core.select_exact80(poisoned)


def test_cross_score_is_full_world_read_only_and_rejects_duplicates(
    prepared, clean_rosters,
):
    rosters = clean_rosters[:2]
    totals = core.cross_score_full_union(
        prepared.players,
        prepared.player_draws,
        rosters,
        expected_worlds=core.EXPECTED_WORLD_COUNT,
    )
    assert totals.shape == (2, 50_000)
    assert totals.flags.writeable is False
    index = {
        player.player_id: row for row, player in enumerate(prepared.players)
    }
    expected = prepared.player_draws[
        [index[player_id] for player_id in rosters[0]]
    ].sum(axis=0, dtype=np.float64)
    np.testing.assert_array_equal(totals[0], expected)
    with pytest.raises(core.CorpusLegalFeasibilityError, match="duplicated"):
        core.cross_score_full_union(
            prepared.players,
            prepared.player_draws,
            (rosters[0], rosters[0]),
        )


@pytest.mark.parametrize(
    ("status", "solution_status", "expected"),
    (
        (pulp.LpStatusOptimal, pulp.LpSolutionOptimal, core.SolverStatus.OPTIMAL),
        (
            pulp.LpStatusInfeasible,
            pulp.LpSolutionInfeasible,
            core.SolverStatus.INFEASIBLE,
        ),
        (
            pulp.LpStatusOptimal,
            pulp.LpSolutionIntegerFeasible,
            core.SolverStatus.TIMEOUT,
        ),
        (
            pulp.LpStatusNotSolved,
            pulp.LpSolutionNoSolutionFound,
            core.SolverStatus.TIMEOUT,
        ),
        (pulp.LpStatusUnbounded, pulp.LpSolutionUnbounded, core.SolverStatus.ERROR),
    ),
)
def test_solver_status_classification(status, solution_status, expected):
    problem = pulp.LpProblem("status_only", pulp.LpMaximize)
    problem.status = status
    problem.sol_status = solution_status
    assert core.classify_pulp_status(problem) is expected


def test_bundled_cbc_proves_clean_two_stage_unique_optimum(players):
    # Binary weights make every roster's primary sum unique, so the second
    # stage must prove infeasibility after excluding the first witness.
    objective = tuple(1 << index for index in range(len(players)))
    profile = core.frozen_policy_profiles()[0]
    model = core.build_fresh_legal_model(
        players,
        profile,
        objective,
        construction_serial=0,
        model_name="real_cbc_two_stage_regression",
    )
    outcome = core.default_cbc_solver(core.SolveRequest(
        variant_ordinal=0,
        parameter_set_id=profile.parameter_set_id,
        visit_ordinal=0,
        world=rw.WorldId("R0", 0),
        objective_micro=objective,
        timeout_seconds=core.SOLVER_TIMEOUT_SECONDS,
        model=model,
    ))

    assert outcome.status is core.SolverStatus.OPTIMAL
    assert outcome.detail == "unique lexicographic combined optimum"
    assert outcome.roster is not None and len(outcome.roster) == rw.ROSTER_SIZE
    assert outcome.solver_proof is not None
    stages = outcome.solver_proof.stages
    assert tuple(stage.status for stage in stages) == (
        core.SolverStatus.OPTIMAL,
        core.SolverStatus.INFEASIBLE,
    )
    assert stages[0].exact_terminal_record == "Result - Optimal solution found"
    assert stages[1].exact_terminal_record is not None
    assert core._CBC_INFEASIBLE_TERMINAL.fullmatch(
        stages[1].exact_terminal_record
    ) is not None
    assert stages[0].objective_sha256 == stages[1].objective_sha256
    for stage in stages:
        command_lines = [
            line for line in stage.raw_cbc_log.splitlines()
            if line.startswith("command line - ")
        ]
        assert len(command_lines) == 1
        assert command_lines[0].endswith(" (default strategy 1)")
        assert stage.raw_command_sha256 == core.sha256(
            command_lines[0].encode("utf-8")
        ).hexdigest()
        assert stage.model_pre_exec_sha256 == stage.model_post_exit_sha256
        assert stage.warning_or_forbidden_marker_detected is False


def _write_renamed_mps(problem, path):
    variables, variable_names, constraint_names, objective_name = (
        problem.writeMPS(str(path), rename=1)
    )
    return (
        path.read_bytes(),
        variables,
        variable_names,
        constraint_names,
        objective_name,
    )


def test_exact_integer_mps_semantics_replays_and_rejects_writer_rounding(
    tmp_path,
):
    exact = pulp.LpProblem("exact_integer_mps", pulp.LpMaximize)
    exact_x = pulp.LpVariable("exact_x", cat="Binary")
    exact_y = pulp.LpVariable("exact_y", cat="Binary")
    exact += 17 * exact_x + 3 * exact_y
    exact += 2 * exact_x + exact_y <= 2, "integer_limit"
    raw, variables, variable_names, constraint_names, objective_name = (
        _write_renamed_mps(exact, tmp_path / "exact.mps")
    )
    first = core._validate_exact_integer_mps_semantics(
        raw,
        exact,
        variables=variables,
        variable_names=variable_names,
        constraint_names=constraint_names,
        objective_name=objective_name,
    )
    second = core._validate_exact_integer_mps_semantics(
        raw,
        exact,
        variables=variables,
        variable_names=variable_names,
        constraint_names=constraint_names,
        objective_name=objective_name,
    )
    assert first == second == core.canonical_sha256(
        core._parse_exact_integer_mps(raw)
    )

    rounded = pulp.LpProblem("rounded_integer_mps", pulp.LpMaximize)
    rounded_x = pulp.LpVariable("rounded_x", cat="Binary")
    rounded += 10_000_000_000_001 * rounded_x
    rounded += rounded_x <= 1, "binary_limit"
    raw, variables, variable_names, constraint_names, objective_name = (
        _write_renamed_mps(rounded, tmp_path / "rounded.mps")
    )
    with pytest.raises(
        core.CorpusLegalFeasibilityError,
        match="serialized CBC MPS integer semantics",
    ):
        core._validate_exact_integer_mps_semantics(
            raw,
            rounded,
            variables=variables,
            variable_names=variable_names,
            constraint_names=constraint_names,
            objective_name=objective_name,
        )


def test_binary_roster_decode_uses_pinned_integer_tolerance(
    players, clean_rosters,
):
    profile = core.frozen_policy_profiles()[0]
    model = core.build_fresh_legal_model(
        players,
        profile,
        (0,) * len(players),
        construction_serial=0,
        model_name="integer_tolerance",
    )
    roster = clean_rosters[0]
    for player_id, variable in model.decision.items():
        variable.varValue = float(player_id in roster)
    poisoned_id = roster[0]
    model.decision[poisoned_id].varValue = (
        1.0 - 2 * core.CBC_INTEGER_TOLERANCE_VALUE
    )
    with pytest.raises(
        core.CorpusLegalFeasibilityError, match="nonintegral"
    ):
        core._decode_binary_roster(model)
    model.decision[poisoned_id].varValue = (
        1.0 - core.CBC_INTEGER_TOLERANCE_VALUE / 2
    )
    assert core._decode_binary_roster(model) == roster


def test_nonoptimal_cell_still_attempts_entire_matrix(
    prepared, clean_rosters, inventory,
):
    calls = 0

    def solver(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return core.SolveOutcome(
                core.SolverStatus.AMBIGUOUS,
                detail="test ambiguity",
            )
        return core._make_mock_optimal_outcome(request, clean_rosters[0])

    with pytest.raises(core.BatchExecutionError) as captured:
        core._execute_generation_matrix_for_test(
            prepared,
            inventory,
            solver=solver,
            semantic_environment={},
            visits_per_block=1,
        )
    assert calls == 35
    assert len(captured.value.attempts) == 35
    assert captured.value.attempts[0].status is core.SolverStatus.AMBIGUOUS
    assert all(
        attempt.status is core.SolverStatus.OPTIMAL
        for attempt in captured.value.attempts[1:]
    )


def test_strict_input_corruption_outcome_columns_and_immutability(
    prepared, clean_rosters, inventory,
):
    original = prepared.player_draws.tobytes()
    calls: list[dict[str, object]] = []
    core._execute_generation_matrix_for_test(
        prepared,
        inventory,
        solver=_capture_solver(clean_rosters[0], calls),
        semantic_environment={},
        visits_per_block=1,
    )
    assert prepared.player_draws.tobytes() == original
    assert prepared.player_draws.flags.writeable is False

    writeable = prepared.player_draws.copy()
    with pytest.raises(core.CorpusLegalFeasibilityError, match="read-only"):
        core._execute_generation_matrix_for_test(
            replace(prepared, player_draws=writeable),
            inventory,
            solver=_capture_solver(clean_rosters[0], []),
            semantic_environment={},
            visits_per_block=1,
        )
    nonfinite = prepared.player_draws.copy()
    nonfinite[0, 0] = np.nan
    nonfinite.flags.writeable = False
    with pytest.raises(core.CorpusLegalFeasibilityError, match="finite"):
        core._execute_generation_matrix_for_test(
            replace(prepared, player_draws=nonfinite),
            inventory,
            solver=_capture_solver(clean_rosters[0], []),
            semantic_environment={},
            visits_per_block=1,
        )
    duplicate_players = (*prepared.players[:-1], prepared.players[0])
    with pytest.raises(core.CorpusLegalFeasibilityError, match="player ids repeat"):
        core._execute_generation_matrix_for_test(
            replace(prepared, players=duplicate_players),
            inventory,
            solver=_capture_solver(clean_rosters[0], []),
            semantic_environment={},
            visits_per_block=1,
        )
    duplicate_worlds = (
        prepared.world_ids[0], prepared.world_ids[0], *prepared.world_ids[2:]
    )
    with pytest.raises(core.CorpusLegalFeasibilityError, match="canonical R0"):
        core._execute_generation_matrix_for_test(
            replace(prepared, world_ids=duplicate_worlds),
            inventory,
            solver=_capture_solver(clean_rosters[0], []),
            semantic_environment={},
            visits_per_block=1,
        )
    with pytest.raises(core.CorpusLegalFeasibilityError, match="outcome fields"):
        core._execute_generation_matrix_for_test(
            prepared,
            inventory,
            solver=_capture_solver(clean_rosters[0], []),
            semantic_environment={},
            visits_per_block=1,
            source_columns=(*core.SOURCE_COLUMN_ORDER, "actual_score"),
        )
    with pytest.raises(core.CorpusLegalFeasibilityError, match="repeat"):
        core.validate_outcome_blind_column_names(("id", "id"))


def test_independent_house_rule_census_observes_all_five_fields(players):
    legal = _hard_legal_rosters(players, count=2_000, house_clean=False)
    observed = {
        field
        for roster in legal
        for field in core.house_rule_violations(players, roster)
    }
    low_salary_players = _players(salary=5_000)
    low_salary_roster = _hard_legal_rosters(
        low_salary_players, count=1, house_clean=False
    )[0]
    observed.update(core.house_rule_violations(
        low_salary_players, low_salary_roster
    ))
    assert observed == set(PARAMETER_ORDER)


def test_authoritative_evidence_directory_is_exact_empty_real_and_create_once(
    tmp_path,
):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    with core._sealed_empty_evidence_directory(evidence) as (
        sealed,
        directory_fd,
    ):
        receipt = core._write_create_once_evidence_file(
            b"bounded-evidence",
            evidence_directory=sealed,
            directory_fd=directory_fd,
            basename="shard-000.zlib",
            maximum_bytes=1024,
        )
        assert receipt[0] == evidence / "shard-000.zlib"
        assert receipt[1] == core.sha256(b"bounded-evidence").hexdigest()
        assert receipt[2] == len(b"bounded-evidence")
        with pytest.raises(
            core.CorpusLegalFeasibilityError, match="exactly once"
        ):
            core._write_create_once_evidence_file(
                b"replacement",
                evidence_directory=sealed,
                directory_fd=directory_fd,
                basename="shard-000.zlib",
                maximum_bytes=1024,
            )

    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "foreign").write_bytes(b"x")
    with pytest.raises(core.CorpusLegalFeasibilityError, match="exactly empty"):
        with core._sealed_empty_evidence_directory(nonempty):
            pass

    real_target = tmp_path / "real-target"
    real_target.mkdir()
    linked = tmp_path / "linked-evidence"
    linked.symlink_to(real_target, target_is_directory=True)
    with pytest.raises(core.CorpusLegalFeasibilityError, match="nonsymlink"):
        with core._sealed_empty_evidence_directory(linked):
            pass


def _synthetic_attempts_for_shard(
    variant_ordinal: int,
    variant_shard_ordinal: int,
) -> tuple[core.AttemptRecord, ...]:
    start = variant_shard_ordinal * core.EVIDENCE_SHARD_VISITS
    rows = []
    for visit in range(start, start + core.EVIDENCE_SHARD_VISITS):
        block_ordinal, world_index = divmod(visit, core.VISITS_PER_BLOCK)
        rows.append(core.AttemptRecord(
            variant_ordinal=variant_ordinal,
            parameter_set_id=PARAMETER_SET_ORDER[variant_ordinal],
            visit_ordinal=visit,
            world=rw.WorldId(rw.WORLD_BLOCKS[block_ordinal], world_index),
            construction_serial=(
                variant_ordinal * core.MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
                + visit
            ),
            status=core.SolverStatus.ERROR,
            roster=None,
            primary_optimum_micro=None,
            secondary_rank_sum=None,
            lexicographic_radix=None,
            combined_optimum=None,
            solver_proof=None,
            detail="bounded publication-seam fixture",
        ))
    return tuple(rows)


@pytest.fixture(scope="module")
def authoritative_publication_fixture(tmp_path_factory):
    evidence = tmp_path_factory.mktemp("corpus-authority-evidence")
    shards = []
    with core._sealed_empty_evidence_directory(evidence) as (
        sealed,
        directory_fd,
    ):
        for variant in range(len(PARAMETER_SET_ORDER)):
            for variant_shard in range(core.EVIDENCE_SHARDS_PER_VARIANT):
                shards.append(core._build_solver_evidence_shard(
                    _synthetic_attempts_for_shard(variant, variant_shard),
                    variant_ordinal=variant,
                    variant_shard_ordinal=variant_shard,
                    evidence_directory=sealed,
                    evidence_directory_fd=directory_fd,
                ))
    shard_tuple = tuple(shards)
    root_payload, root_sha, _ = core._build_solver_evidence_task_root(
        shard_tuple
    )
    draft_body = {
        "schema": core.DRAFT_AUTHORITY_BUNDLE_SCHEMA,
        "fixture_scope": "publication-boundary-only",
        "artifact_source_authority_completion_object_sha256": "6" * 64,
        "artifact_source_authority_completion_sha256": "7" * 64,
        "artifact_source_authority_task_sha256": "8" * 64,
        "solver_evidence_task_root_sha256": root_sha,
        "evidence_output_prefix": "gs://test-bucket/corpus/task-000/",
    }
    draft_sha = core.canonical_sha256(draft_body)
    draft = core.DraftAuthorityBundle(
        schema=core.DRAFT_AUTHORITY_BUNDLE_SCHEMA,
        source_binding_payload=b"{}",
        source_binding_sha256="1" * 64,
        artifact_source_authority_completion_object_sha256="6" * 64,
        artifact_source_authority_completion_sha256="7" * 64,
        artifact_source_authority_task_sha256="8" * 64,
        registered_law_payload=b"{}",
        registered_law_sha256="2" * 64,
        runtime_policy_payloads=(),
        attempt_ledger_payload=b"{}",
        attempt_ledger_sha256="3" * 64,
        matrix_authority_payload=b"{}",
        matrix_authority_sha256="4" * 64,
        solver_evidence_shards=shard_tuple,
        solver_evidence_task_root_payload=root_payload,
        solver_evidence_task_root_sha256=root_sha,
        variant_result_payloads=(),
        batch_result_payload=b"{}",
        batch_result_sha256="5" * 64,
        evidence_output_prefix="gs://test-bucket/corpus/task-000/",
        canonical_draft_payload=core.canonical_json_bytes({
            **draft_body, "draft_sha256": draft_sha,
        }),
        draft_sha256=draft_sha,
        generation_matrix=None,
        result=None,
    )
    identities = tuple({
        "global_shard_ordinal": shard.global_shard_ordinal,
        "compressed_object_identity": {
            "uri": (
                "gs://test-bucket/corpus/task-000/solver-evidence/"
                f"shard-{shard.global_shard_ordinal:03d}.zlib"
            ),
            "generation": str(shard.global_shard_ordinal + 1),
            "sha256": shard.compressed_sha256,
            "bytes": shard.compressed_bytes,
        },
        "index_object_identity": {
            "uri": (
                "gs://test-bucket/corpus/task-000/solver-evidence/"
                f"shard-{shard.global_shard_ordinal:03d}.index.json"
            ),
            "generation": str(shard.global_shard_ordinal + 101),
            "sha256": shard.index_object_sha256,
            "bytes": shard.index_bytes,
        },
    } for shard in shard_tuple)
    return draft, identities, evidence


def test_authoritative_draft_is_descriptor_only_and_exact_70_by_140(
    authoritative_publication_fixture,
):
    draft, identities, evidence = authoritative_publication_fixture
    assert len(draft.solver_evidence_shards) == 70
    assert len(identities) == 70
    assert sum(
        int("compressed_object_identity" in row)
        + int("index_object_identity" in row)
        for row in identities
    ) == 140
    assert len(tuple(evidence.iterdir())) == 140
    shard_field_names = {
        field.name for field in fields(core.SolverEvidenceShard)
    }
    assert "compressed_payload" not in shard_field_names
    assert "index_payload" not in shard_field_names
    assert all(
        not isinstance(getattr(shard, field.name), bytes)
        for shard in draft.solver_evidence_shards
        for field in fields(core.SolverEvidenceShard)
    )


def test_authoritative_finalizer_rejects_fabricated_component_graph(
    authoritative_publication_fixture,
):
    draft, identities, _ = authoritative_publication_fixture
    with pytest.raises(
        core.CorpusLegalFeasibilityError, match="generation matrix"
    ):
        core.finalize_authoritative_corpus_bundle(
            draft, solver_evidence_object_identities=identities
        )


def test_publication_identity_seam_reopens_exact_local_bytes(
    authoritative_publication_fixture,
):
    draft, identities, _ = authoritative_publication_fixture
    shard = draft.solver_evidence_shards[0]
    compressed_identity = identities[0]["compressed_object_identity"]
    normalized = core._validate_local_evidence_object_identity(
        shard.compressed_path,
        compressed_identity,
        expected_sha256=shard.compressed_sha256,
        expected_size=shard.compressed_bytes,
        expected_device=shard.compressed_device,
        expected_inode=shard.compressed_inode,
        maximum_bytes=core.MAX_SHARD_SOLVER_EVIDENCE_COMPRESSED_BYTES,
        label="test compressed evidence",
    )
    assert normalized == compressed_identity
    poisoned = dict(compressed_identity)
    poisoned["sha256"] = "f" * 64
    with pytest.raises(
        core.CorpusLegalFeasibilityError, match="retained identity"
    ):
        core._validate_local_evidence_object_identity(
            shard.compressed_path,
            poisoned,
            expected_sha256=shard.compressed_sha256,
            expected_size=shard.compressed_bytes,
            expected_device=shard.compressed_device,
            expected_inode=shard.compressed_inode,
            maximum_bytes=core.MAX_SHARD_SOLVER_EVIDENCE_COMPRESSED_BYTES,
            label="test compressed evidence",
        )


def test_authoritative_and_private_matrix_types_are_not_interchangeable(
    prepared, clean_rosters, inventory,
):
    matrix = core._execute_generation_matrix_for_test(
        prepared,
        inventory,
        solver=_capture_solver(clean_rosters[0], []),
        semantic_environment={},
        visits_per_block=1,
    )
    with pytest.raises(
        core.CorpusLegalFeasibilityError, match="authoritative finalizer"
    ):
        core._finalize_authoritative_generation_matrix(matrix)
    authoritative = core.AuthoritativeGenerationMatrix(**{
        field.name: getattr(matrix, field.name)
        for field in fields(core.GenerationMatrix)
    })
    with pytest.raises(
        core.CorpusLegalFeasibilityError, match="private finalizer"
    ):
        core._finalize_test_generation_matrix(authoritative)


def _deadline_stage(
    name: str,
    status: core.SolverStatus,
    *,
    remaining_before: int,
    requested: int,
    watchdog: int,
    elapsed: int,
    remaining_after: int,
) -> core.SolverStageReceipt:
    log = f"command line - cbc model.mps -sec {requested / 1_000_000:.6f}\n"
    solution = b"synthetic exact terminal solution\n"
    model_sha = "a" * 64
    return core.SolverStageReceipt(
        stage=name,
        status=status,
        pulp_status=1 if status is core.SolverStatus.OPTIMAL else -1,
        pulp_solution_status=1 if status is core.SolverStatus.OPTIMAL else -1,
        remaining_before_microseconds=remaining_before,
        cbc_requested_microseconds=requested,
        host_watchdog_microseconds=watchdog,
        elapsed_microseconds=elapsed,
        remaining_after_microseconds=remaining_after,
        objective_sha256="b" * 64,
        witness_sha256=None,
        log_sha256=core.sha256(log.encode()).hexdigest(),
        log_bytes=len(log.encode()),
        raw_cbc_log=log,
        solution_sha256=core.sha256(solution).hexdigest(),
        solution_bytes=len(solution),
        raw_cbc_solution=solution,
        model_sha256=model_sha,
        model_bytes=100,
        model_pre_exec_sha256=model_sha,
        model_post_exit_sha256=model_sha,
        model_regular_exclusive_inode=True,
        model_path_command_bound=True,
        raw_command_sha256="c" * 64,
        exact_terminal_record=(
            "Optimal objective" if status is core.SolverStatus.OPTIMAL
            else "Infeasible"
        ),
        warning_or_forbidden_marker_detected=False,
        solver_binary_sha256="d" * 64,
        solver_options_sha256="e" * 64,
    )


def test_solver_proof_reconciles_absolute_deadline_and_stage_budgets():
    solver = {
        "binary_sha256": "d" * 64,
        "options_sha256": "e" * 64,
    }
    stages = (
        _deadline_stage(
            "lexicographic_combined_optimum",
            core.SolverStatus.OPTIMAL,
            remaining_before=120_000_000,
            requested=119_999_990,
            watchdog=119_999_980,
            elapsed=10,
            remaining_after=119_999_970,
        ),
        _deadline_stage(
            "combined_optimum_collision",
            core.SolverStatus.INFEASIBLE,
            remaining_before=119_999_960,
            requested=119_999_950,
            watchdog=119_999_940,
            elapsed=10,
            remaining_after=119_999_930,
        ),
    )
    proof = core._build_solver_proof(
        solver, stages, total_elapsed_microseconds=80
    )
    core._validate_authoritative_solver_proof(
        core.SolveOutcome(
            core.SolverStatus.OPTIMAL, solver_proof=proof
        ),
        solver_authority_sha256=core.canonical_sha256(solver),
    )

    underreported = core._build_solver_proof(
        solver, stages, total_elapsed_microseconds=0
    )
    with pytest.raises(
        core.CorpusLegalFeasibilityError, match="total monotonic"
    ):
        core._validate_authoritative_solver_proof(
            core.SolveOutcome(
                core.SolverStatus.OPTIMAL, solver_proof=underreported
            ),
            solver_authority_sha256=core.canonical_sha256(solver),
        )

    exhausted = core._build_solver_proof(
        solver, stages, total_elapsed_microseconds=120_000_000
    )
    with pytest.raises(
        core.CorpusLegalFeasibilityError, match="identity/deadline"
    ):
        core._validate_authoritative_solver_proof(
            core.SolveOutcome(
                core.SolverStatus.OPTIMAL, solver_proof=exhausted
            ),
            solver_authority_sha256=core.canonical_sha256(solver),
        )
