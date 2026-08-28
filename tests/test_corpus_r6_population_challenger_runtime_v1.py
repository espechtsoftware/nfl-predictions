from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_runtime_v1 as runtime,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles
from nfl_dfs.research import lr8_later_period_source as later
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


F7_ROSTER = tuple(sorted((
    "q-a", "rb-c", "rb-e", "wr-c", "wr-d", "wr-e", "wr-f", "te-c",
    "dst-i",
)))
F8_ROSTER = tuple(sorted((
    "q-a", "rb-c", "rb-e", "wr-c", "wr-d", "wr-e", "wr-f", "te-g",
    "dst-i",
)))
F9_ROSTER = tuple(sorted((
    "q-a", "rb-b", "rb-c", "wr-a", "wr-c", "wr-d", "wr-e", "te-b",
    "dst-i",
)))


def _prepared() -> later.PreparedLaterSlate:
    players = _players()
    # Different block/index totals make the canonical one-visit schedule
    # deterministic while retaining the full production 50,000-world shape.
    draws = np.zeros((len(players), 50_000), dtype=np.float32)
    for block_ordinal in range(5):
        draws[:, block_ordinal * 10_000 + block_ordinal] = block_ordinal + 1
    draws.flags.writeable = False
    worlds = tuple(
        rw.WorldId(block, index)
        for block in rw.WORLD_BLOCKS
        for index in range(rw.WORLDS_PER_BLOCK)
    )
    return later.PreparedLaterSlate(
        season=2023,
        week=1,
        slate_id="2023-w01",
        players=players,
        world_ids=worlds,
        player_draws=draws,
        incumbent_candidates=(),
        source_freeze_sha256="a" * 64,
        artifact_sha256_by_block={block: block[-1] * 64 for block in rw.WORLD_BLOCKS},
    )


def _source() -> dict[str, object]:
    body = {
        "schema": runtime.SOURCE_AUTHORITY_SCHEMA,
        "source_ordinal": 0,
        "slate_id": "2023-w01",
        "projection_bundle_identity": {
            "uri": "gs://fixture/projection.json",
            "generation": "1",
            "sha256": "b" * 64,
            "bytes": 1,
        },
        "projection_bundle_sha256": "c" * 64,
        "later_source_identity": {
            "uri": "gs://fixture/source.json",
            "generation": "2",
            "sha256": "d" * 64,
            "bytes": 1,
        },
        "world_artifact_identities": {},
        "world_artifact_identities_sha256": authority.canonical_sha256_v1({}),
        "source_bank_task_result_identity": {
            "uri": "gs://fixture/task-result.json",
            "generation": "3",
            "sha256": "e" * 64,
            "bytes": 1,
        },
        "fold_projection_sha256s": [str(index) * 64 for index in range(1, 6)],
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
    }
    return {
        **body,
        "source_authority_sha256": authority.canonical_sha256_v1(body),
    }


def _solver(request: legal.SolveRequest) -> legal.SolveOutcome:
    target = {
        profiles.PROFILE_ORDER[0]: F7_ROSTER,
        profiles.PROFILE_ORDER[1]: F8_ROSTER,
        profiles.PROFILE_ORDER[2]: F9_ROSTER,
    }[request.parameter_set_id]
    return legal._make_mock_optimal_outcome(request, target)


@pytest.mark.parametrize(
    ("profile_id", "target"),
    tuple(zip(
        profiles.PROFILE_ORDER,
        (F7_ROSTER, F8_ROSTER, F9_ROSTER),
        strict=True,
    )),
)
def test_exact_production_cbc_path_accepts_each_named_profile_and_proof(
    profile_id: str, target: tuple[str, ...]
):
    players = _players()
    objective = tuple(
        1_000_000 if player.player_id in target else 0 for player in players
    )
    profile = profiles.population_profile_v1(profile_id)
    model = profiles.build_profile_model_v1(
        players,
        profile_id,
        objective,
        construction_serial=profile.ordinal,
        model_name=f"production_path_f{profile.ordinal}",
    )
    request = legal.SolveRequest(
        variant_ordinal=profile.ordinal,
        parameter_set_id=profile_id,
        visit_ordinal=0,
        world=rw.WorldId("R0", 0),
        objective_micro=objective,
        timeout_seconds=profiles.SharedSolverWork().solver_timeout_seconds,
        model=model,
    )
    solver_authority = legal._cbc_runtime_authority()
    outcome = runtime._normalize_profile_outcome_v1(
        legal.default_cbc_solver(request),
        request=request,
        profile_id=profile_id,
    )
    legal._validate_authoritative_solver_proof(
        outcome,
        solver_authority_sha256=legal.canonical_sha256(solver_authority),
    )
    assert outcome.status is legal.SolverStatus.OPTIMAL
    assert outcome.roster == target
    profiles.audit_profile_roster_v1(players, outcome.roster, profile_id)


def test_bounded_runtime_uses_one_equal_world_lattice_and_exact_lineup_identities():
    work = profiles.SharedSolverWork(solve_attempts_per_block=1)
    results = runtime.execute_equal_work_for_test_v1(
        prepared=_prepared(), work=work, solver=_solver, source_authority=_source()
    )
    assert tuple(results) == profiles.PROFILE_ORDER
    assert {row["attempt_count"] for row in results.values()} == {5}
    assert {row["work_sha256"] for row in results.values()} == {
        authority.canonical_sha256_v1(work.payload())
    }
    assert len({row["world_schedule_sha256"] for row in results.values()}) == 1
    assert len({row["source_authority_sha256"] for row in results.values()}) == 1
    assert all(row["test_only"] is True for row in results.values())
    assert all(
        row["authoritative_solver_proofs_complete"] is False
        for row in results.values()
    )
    assert all(row["unique_lineup_count"] == 1 for row in results.values())
    expected = dict(zip(
        profiles.PROFILE_ORDER, (F7_ROSTER, F8_ROSTER, F9_ROSTER), strict=True
    ))
    profile_lineup_hashes = set()
    for profile_id, row in results.items():
        assert tuple(row["unique_lineups"][0]["lineup_identity"]["roster"]) == (
            expected[profile_id]
        )
        assert row["unique_lineups"][0]["occurrence_count"] == 5
        profile_lineup_hashes.add(
            row["unique_lineups"][0]["lineup_identity"]["lineup_sha256"]
        )
        assert runtime.validate_profile_lineups_v1(
            deepcopy(row), players=_players()
        ) == row
    # Identical slate membership in different named profiles cannot collide.
    assert len(profile_lineup_hashes) == 3


def test_construction_serials_are_complete_profile_major_equal_work():
    results = runtime.execute_equal_work_for_test_v1(
        prepared=_prepared(),
        work=profiles.SharedSolverWork(solve_attempts_per_block=1),
        solver=_solver,
        source_authority=_source(),
    )
    assert {
        profile_id: [row["construction_serial"] for row in body["visit_results"]]
        for profile_id, body in results.items()
    } == {
        profiles.PROFILE_ORDER[0]: list(range(0, 5)),
        profiles.PROFILE_ORDER[1]: list(range(5, 10)),
        profiles.PROFILE_ORDER[2]: list(range(10, 15)),
    }


def test_runtime_rejects_callback_roster_that_violates_named_profile():
    def poisoned(request: legal.SolveRequest) -> legal.SolveOutcome:
        return legal._make_mock_optimal_outcome(request, F7_ROSTER)

    with pytest.raises(
        runtime.CorpusR6PopulationChallengerRuntimeV1Error,
        match="F8-game-cap-3 visit 0",
    ):
        runtime.execute_equal_work_for_test_v1(
            prepared=_prepared(),
            work=profiles.SharedSolverWork(solve_attempts_per_block=1),
            solver=poisoned,
            source_authority=_source(),
        )


def test_rehashed_profile_tamper_cannot_change_lineup_membership():
    results = runtime.execute_equal_work_for_test_v1(
        prepared=_prepared(),
        work=profiles.SharedSolverWork(solve_attempts_per_block=1),
        solver=_solver,
        source_authority=_source(),
    )
    poisoned = deepcopy(results[profiles.PROFILE_ORDER[0]])
    poisoned["visit_results"][0]["lineup_identity"]["roster"][0] = "not-a-player"
    with pytest.raises(
        runtime.CorpusR6PopulationChallengerRuntimeV1Error,
        match="self-hash differs",
    ):
        runtime.validate_profile_lineups_v1(poisoned, players=_players())


def _load_dispatcher_module():
    path = Path("scripts/run_corpus_r6_population_challenger_v1.py")
    spec = importlib.util.spec_from_file_location("population_dispatcher_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dispatcher_rejects_ambient_legacy_structure_before_store_access():
    dispatcher = _load_dispatcher_module()
    class NeverStore:
        def read_exact(self, identity):  # pragma: no cover - must not run
            raise AssertionError("store must not be accessed")

    with pytest.raises(
        dispatcher.RunCorpusR6PopulationChallengerV1Error,
        match="ambient inherited structure keys are forbidden",
    ):
        dispatcher.execute_environment_task_v1(
            {
                authority.ENABLE_ENV: "1",
                "STACK_QB_MIN": "2",
            },
            store=NeverStore(),
            observed_command=list(authority.DISPATCHER_COMMAND),
        )


def test_dispatcher_kernel_command_shape_is_exact():
    dispatcher = _load_dispatcher_module()
    raw = b"/usr/local/bin/python3.11\0-I\0/app/scripts/run_corpus_r6_population_challenger_v1.py\0task\0"
    assert dispatcher.observed_dispatcher_command_v1(raw) == list(
        authority.DISPATCHER_COMMAND
    )


def test_terminal_completion_retains_exact_task_and_profile_object_identities():
    profile_rows = []
    for ordinal, profile_id in enumerate(profiles.PROFILE_ORDER, start=1):
        profile_rows.append({
            "profile_id": profile_id,
            "profile_sha256": profiles.population_profile_v1(
                profile_id
            ).fingerprint,
            "lineups_sha256": str(ordinal) * 64,
            "lineups_identity": {
                "uri": f"gs://fixture/{profile_id}/lineups.json",
                "generation": str(ordinal),
                "sha256": str(ordinal) * 64,
                "bytes": ordinal,
            },
            "attempt_count": authority.SOLVES_PER_PROFILE_PER_SLATE,
            "unique_lineup_count": ordinal,
            "world_schedule_sha256": "a" * 64,
            "work_sha256": "b" * 64,
        })
    body = {
        "schema": authority.TASK_RESULT_SCHEMA,
        "task_index": 0,
        "source_ordinal": 0,
        "request_sha256": "c" * 64,
        "source_authority": _source(),
        "source_authority_sha256": _source()["source_authority_sha256"],
        "profile_results": profile_rows,
        "profile_results_sha256": authority.canonical_sha256_v1(profile_rows),
        "profile_count": 3,
        "solves_per_profile": authority.SOLVES_PER_PROFILE_PER_SLATE,
        "total_solves": authority.SOLVES_PER_TASK,
        "all_profiles_complete": True,
        "equal_solver_work_confirmed": True,
        "equal_world_schedule_confirmed": True,
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_performed": False,
        "production_default_change_licensed": False,
        "promotion_authority": False,
    }
    result = {
        **body,
        "task_result_sha256": authority.canonical_sha256_v1(body),
    }
    raw = authority.canonical_bytes_v1(result)
    result_identity = {
        "uri": "gs://fixture/task-result.json",
        "generation": "9",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    completion = runtime.build_task_completion_v1(
        task_result=result, task_result_identity=result_identity
    )
    assert runtime.validate_task_completion_v1(deepcopy(completion)) == completion
    assert completion["task_result_identity"] == result_identity
    assert tuple(completion["profile_lineup_identities"]) == profiles.PROFILE_ORDER
    assert completion["task_result_sha256"] == result["task_result_sha256"]
