from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_generation_additions as source_contract
from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_population_process_v1 as process,
)
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_population_successor_v1 as successor,
)


SLATE = "2023-w01"
HELDOUT = "R4"
ORIGIN = "R1"
TRAINING = ("R0", "R1", "R2", "R3")


def _identity(
    name: str,
    generation: int = 1,
    *,
    payload: bytes | None = None,
    digest: str | None = None,
    size: int = 100,
) -> dict[str, object]:
    if payload is not None:
        digest = hashlib.sha256(payload).hexdigest()
        size = len(payload)
    return {
        "uri": f"gs://hard230-successor-fixture/{name}",
        "generation": str(generation),
        "sha256": digest or legal.canonical_sha256({"name": name}),
        "bytes": size,
    }


def _body_identity(name: str, body: object, generation: int = 1) -> dict[str, object]:
    return _identity(
        name, generation, payload=legal.canonical_json_bytes(body)
    )


def _players() -> list[dict[str, object]]:
    rows = [
        {
            "id": player_id,
            "pos": position,
            "team": team,
            "opp": opponent,
            "game_id": game_id,
            "salary": 5_500,
        }
        for player_id, position, team, opponent, game_id in (
            ("a-qb", "QB", "A", "B", "g1"),
            ("a-rb", "RB", "A", "B", "g1"),
            ("a-wr1", "WR", "A", "B", "g1"),
            ("a-wr2", "WR", "A", "B", "g1"),
            ("a-wr3", "WR", "A", "B", "g1"),
            ("b-rb", "RB", "B", "A", "g1"),
            ("b-wr1", "WR", "B", "A", "g1"),
            ("b-wr2", "WR", "B", "A", "g1"),
            ("c-dst", "DST", "C", "D", "g2"),
            ("c-te", "TE", "C", "D", "g2"),
            ("c-wr1", "WR", "C", "D", "g2"),
            ("c-wr2", "WR", "C", "D", "g2"),
        )
    ]
    return sorted(rows, key=lambda row: str(row["id"]))


def _roster(seed: int) -> list[str]:
    return sorted(
        [
            "a-qb",
            "a-rb",
            "a-wr1",
            ("a-wr2", "a-wr3")[seed % 2],
            "b-rb",
            ("b-wr1", "b-wr2")[(seed // 2) % 2],
            "c-dst",
            "c-te",
            ("c-wr1", "c-wr2")[(seed // 4) % 2],
        ]
    )


def _proof(
    *,
    proof_id: str,
    input_body: object,
    output_body: object,
) -> dict[str, object]:
    return {
        "proof_id": proof_id,
        "proof_kind": "score-matrix-derivation-v1",
        "implementation_sha256": "8" * 64,
        "input_sha256": legal.canonical_sha256(input_body),
        "output_sha256": legal.canonical_sha256(output_body),
        "proof_object_identity": _identity(f"proofs/{proof_id}.json", 7),
    }


def _source(
    *,
    width: int,
    high_roster: list[str] | None,
    all_players_high: bool = False,
    players: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    registry = _players() if players is None else players
    source_sha = legal.canonical_sha256({"slate": SLATE, "players": len(registry)})
    source_member = {
        "member_id": "fixture-member",
        "slate_id": SLATE,
        "member_sha256": source_sha,
        "object_identity": _identity(
            "source-member.json", 2, digest=source_sha
        ),
    }
    blocks = [
        {
            "block_id": block,
            "world_count": width,
            "source_member_sha256": source_sha,
            "object_identity": _identity(f"blocks/{block}.npy", ordinal + 3),
        }
        for ordinal, block in enumerate(TRAINING)
    ]
    matrix = np.zeros((len(registry), len(TRAINING) * width), dtype="<i8")
    player_index = {str(row["id"]): index for index, row in enumerate(registry)}
    if all_players_high:
        matrix[:, :] = 30_000
    elif high_roster is not None:
        for player_id in high_roster:
            matrix[player_index[player_id], :] = 30_000
    matrix_sha = source_contract.canonical_score_matrix_sha256_v1(matrix)
    artifact = _identity("matrix.npy", 20)
    derivation_input = {
        "matrix_id": "fixture-fit-matrix",
        "score_unit": "milli-DraftKings-points",
        "matrix_shape": list(matrix.shape),
        "artifact_identity": artifact,
        "source_member_sha256": source_sha,
        "score_block_identities_sha256": legal.canonical_sha256(blocks),
        "player_registry_sha256": legal.canonical_sha256(registry),
    }
    matrix_identity = {
        **derivation_input,
        "canonical_score_matrix_sha256": matrix_sha,
        "derivation_proof_identity": _proof(
            proof_id="matrix-derivation",
            input_body=derivation_input,
            output_body={"canonical_score_matrix_sha256": matrix_sha},
        ),
    }
    lineage = {
        "source_member_sha256": source_sha,
        "score_block_ids": list(TRAINING),
        "score_block_identities_sha256": legal.canonical_sha256(blocks),
        "player_registry_sha256": legal.canonical_sha256(registry),
        "score_matrix_sha256": matrix_sha,
        "matrix_derivation_proof_identity_sha256": legal.canonical_sha256(
            matrix_identity["derivation_proof_identity"]
        ),
    }
    return {
        "source_member_identity": source_member,
        "score_block_identities": blocks,
        "player_registry": registry,
        "score_matrix": matrix,
        "score_matrix_identity": matrix_identity,
        "lineage": lineage,
    }


class _MemoryRecorder:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, bytes]] = []

    def __call__(self, *, role: str, deterministic_key: str, payload: bytes) -> None:
        self.rows.append((role, deterministic_key, payload))


class _MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, object]]] = {}

    def publish(self, uri: str, payload: bytes) -> dict[str, object]:
        if uri in self.objects:
            prior, identity = self.objects[uri]
            if prior != payload:
                raise RuntimeError("create-once collision differs")
            return dict(identity)
        identity = {
            "uri": uri,
            "generation": str(len(self.objects) + 10),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        self.objects[uri] = (payload, identity)
        return dict(identity)

    def read(self, identity: dict[str, object]) -> bytes:
        raw, retained = self.objects[str(identity["uri"])]
        if retained != identity:
            raise RuntimeError("generation-pinned read differs")
        return raw


def _authorities(
    source: dict[str, object], *, width: int, target: int
) -> dict[str, object]:
    p0 = successor.build_p0_target_authority_v1(
        slate_id=SLATE,
        candidate_origin_id=ORIGIN,
        heldout_block=HELDOUT,
        source_lineage=source["lineage"],
        retained_lineup_ids=[f"p0-lineup-{index}" for index in range(target)],
        population_receipt_identity=_identity("p0-receipt.json", 30),
    )
    p0_identity = _body_identity("p0-target.json", p0, 31)
    permutation = successor.build_world_permutation_authority_v1(
        slate_id=SLATE,
        candidate_origin_id=ORIGIN,
        heldout_block=HELDOUT,
        worlds_per_block=width,
        ordered_world_indices=list(range(width)),
        source_lineage=source["lineage"],
        derivation_identity=_identity("world-permutation-derivation.json", 32),
    )
    permutation_identity = _body_identity("world-permutation.json", permutation, 33)
    budget = process.build_process_budget_v1(
        slate_id=SLATE,
        candidate_origin_id=ORIGIN,
        heldout_block=HELDOUT,
        p0_target_authority=p0,
        p0_target_authority_identity=p0_identity,
        world_permutation_authority=permutation,
        world_permutation_authority_identity=permutation_identity,
        output_prefix="gs://hard230-successor-fixture/output/cell-000",
        execution_mode=successor.FIXTURE_EXECUTION_MODE,
    )
    budget_identity = _body_identity("process-budget.json", budget, 34)
    contract_sha = hashlib.sha256(Path(successor.__file__).read_bytes()).hexdigest()
    process_sha = hashlib.sha256(Path(process.__file__).read_bytes()).hexdigest()
    solver_sha = hashlib.sha256(Path(legal.__file__).read_bytes()).hexdigest()
    runtime = successor.build_runtime_authority_v1(
        slate_id=SLATE,
        candidate_origin_id=ORIGIN,
        heldout_block=HELDOUT,
        source_commit_sha="1" * 40,
        immutable_image_digest="sha256:" + "2" * 64,
        contract_source_sha256=contract_sha,
        process_source_sha256=process_sha,
        solver_implementation_sha256=solver_sha,
        solver_authority_sha256="4" * 64,
        optimizer_source_identity=_identity("optimizer-source.tar", 35),
        terminal_build_receipt_identity=_identity("build-receipt.json", 36),
        task_manifest_identity=_identity("task-manifest.json", 37),
        launch_intent_identity=_identity("launch-intent.json", 38),
        process_budget_identity=budget_identity,
        p0_target_authority_identity=p0_identity,
        world_permutation_authority_identity=permutation_identity,
    )
    runtime_identity = _body_identity("runtime-authority.json", runtime, 39)
    request = process.build_process_request_v1(
        task_index=0,
        process_budget=budget,
        process_budget_identity=budget_identity,
        source_member_identity=source["source_member_identity"],
        score_block_identities=source["score_block_identities"],
        player_registry_sha256=source["lineage"]["player_registry_sha256"],
        score_matrix_identity=source["score_matrix_identity"],
        p0_target_authority_identity=p0_identity,
        world_permutation_authority_identity=permutation_identity,
        runtime_authority_identity=runtime_identity,
        require_production_width=False,
    )
    return {
        "p0": p0,
        "p0_identity": p0_identity,
        "permutation": permutation,
        "permutation_identity": permutation_identity,
        "budget": budget,
        "budget_identity": budget_identity,
        "runtime": runtime,
        "runtime_identity": runtime_identity,
        "request": request,
        "request_identity": _body_identity("process-request.json", request, 40),
    }


def _solver(rosters: list[list[str]]):
    def solve(request: legal.SolveRequest) -> legal.SolveOutcome:
        roster = rosters[min(request.visit_ordinal, len(rosters) - 1)]
        return legal._make_mock_optimal_outcome(request, roster)

    return solve


def _run(
    *,
    width: int = 4,
    target: int = 1,
    high_roster: list[str] | None = None,
    all_players_high: bool = False,
    rosters: list[list[str]] | None = None,
    players: list[dict[str, object]] | None = None,
) -> tuple[successor.Hard230PopulationSuccessorResult, dict[str, object]]:
    high = _roster(7) if high_roster is None else high_roster
    source = _source(
        width=width,
        high_roster=high,
        all_players_high=all_players_high,
        players=players,
    )
    authorities = _authorities(source, width=width, target=target)
    result = successor.run_hard230_population_successor_v1(
        slate_id=SLATE,
        candidate_origin_id=ORIGIN,
        heldout_block=HELDOUT,
        worlds_per_block=width,
        source_member_identity=source["source_member_identity"],
        score_block_identities=source["score_block_identities"],
        player_registry=source["player_registry"],
        score_matrix=source["score_matrix"],
        score_matrix_identity=source["score_matrix_identity"],
        p0_target_authority=authorities["p0"],
        p0_target_authority_identity=authorities["p0_identity"],
        world_permutation_authority=authorities["permutation"],
        world_permutation_authority_identity=authorities["permutation_identity"],
        runtime_authority=authorities["runtime"],
        runtime_authority_identity=authorities["runtime_identity"],
        evidence_recorder=_MemoryRecorder(),
        execution_mode=successor.FIXTURE_EXECUTION_MODE,
        require_production_width=False,
        solver_callback=_solver(rosters or [high]),
    )
    return result, {"source": source, **authorities}


def test_native_successor_replenishes_after_rejection_on_one_shared_stream() -> None:
    low = _roster(0)
    high = _roster(7)
    result, _ = _run(rosters=[low, low, high])
    receipt = result.receipt
    assert receipt["does_not_use_frozen_stop_at_control_target_companion_law"] is True
    assert receipt["actual_shared_solver_call_count"] == 3
    assert receipt["control_observed_solver_call_count"] == 3
    assert receipt["challenger_observed_solver_call_count"] == 3
    assert receipt["solver_occurrences_shared_not_reexecuted"] is True
    assert receipt["score_blind_control_population"]["population_rosters"][0][
        "roster_player_ids"
    ] == low
    assert receipt["hard230_challenger_population"]["population_rosters"][0][
        "roster_player_ids"
    ] == high
    assert receipt["rejection_counts"] == {
        "non-optimal-solver-result": 0,
        "duplicate-generated-roster": 1,
        "no-inclusive-230-permitted-fit-world-hit": 1,
    }


def test_unique_lineup_identity_and_200_220_230_diagnostics_are_exact() -> None:
    result, _ = _run()
    population = result.receipt["hard230_challenger_population"]
    row = population["population_rosters"][0]
    assert row["lineup_id"] == f"lineup-v1-{row['roster_sha256']}"
    assert row["roster_sha256"] == legal.canonical_sha256(
        row["roster_player_ids"]
    )
    assert [
        item["threshold_milli_dk"] for item in population["threshold_diagnostics"]
    ] == [200_000, 220_000, 230_000]
    assert all(
        item["available_lineup_count"] == 1
        and item["oracle_world_hit_count"] == population["fit_world_count"]
        for item in population["threshold_diagnostics"]
    )
    assert population["oracle_maximum_score_milli_dk"] == 270_000


def test_exact_p0_permutation_and_runtime_identities_fail_before_solver() -> None:
    source = _source(width=2, high_roster=_roster(7))
    authorities = _authorities(source, width=2, target=1)
    bad_runtime = deepcopy(authorities["runtime"])
    bad_runtime["world_permutation_authority_identity"] = _identity(
        "wrong-permutation.json", 99
    )
    body = {
        key: value
        for key, value in bad_runtime.items()
        if key != "runtime_authority_sha256"
    }
    bad_runtime["runtime_authority_sha256"] = legal.canonical_sha256(body)
    bad_runtime_identity = _body_identity("bad-runtime.json", bad_runtime, 100)
    calls = 0

    def solver(request: legal.SolveRequest) -> legal.SolveOutcome:
        nonlocal calls
        calls += 1
        return legal._make_mock_optimal_outcome(request, _roster(7))

    with pytest.raises(
        successor.Hard230PopulationSuccessorV1Error,
        match="does not bind the exact permutation identity",
    ):
        successor.run_hard230_population_successor_v1(
            slate_id=SLATE,
            candidate_origin_id=ORIGIN,
            heldout_block=HELDOUT,
            worlds_per_block=2,
            source_member_identity=source["source_member_identity"],
            score_block_identities=source["score_block_identities"],
            player_registry=source["player_registry"],
            score_matrix=source["score_matrix"],
            score_matrix_identity=source["score_matrix_identity"],
            p0_target_authority=authorities["p0"],
            p0_target_authority_identity=authorities["p0_identity"],
            world_permutation_authority=authorities["permutation"],
            world_permutation_authority_identity=authorities[
                "permutation_identity"
            ],
            runtime_authority=bad_runtime,
            runtime_authority_identity=bad_runtime_identity,
            evidence_recorder=_MemoryRecorder(),
            execution_mode=successor.FIXTURE_EXECUTION_MODE,
            require_production_width=False,
            solver_callback=solver,
        )
    assert calls == 0


def test_successor_accepts_exact_1024_player_envelope_and_rejects_1025() -> None:
    players = _players()
    template = dict(players[-1])
    for index in range(successor.MAX_PLAYER_COUNT - len(players)):
        row = dict(template)
        row["id"] = f"zz-extra-{index:04d}"
        players.append(row)
    players.sort(key=lambda row: str(row["id"]))
    result, _ = _run(width=1, players=players)
    assert result.receipt["player_count"] == 1_024
    oversized = [*players, {**template, "id": "zzz-over-bound"}]
    with pytest.raises(
        successor.Hard230PopulationSuccessorV1Error,
        match="9..1,024 bound",
    ):
        _run(width=1, players=oversized)


def test_release_validates_one_real_local_cbc_proof() -> None:
    width = 1
    source = _source(width=width, high_roster=_roster(7))
    authorities = _authorities(source, width=width, target=1)
    runtime = deepcopy(authorities["runtime"])
    runtime["solver_authority_sha256"] = legal.canonical_sha256(
        legal._cbc_runtime_authority()
    )
    body = {
        key: value for key, value in runtime.items() if key != "runtime_authority_sha256"
    }
    runtime["runtime_authority_sha256"] = legal.canonical_sha256(body)
    runtime_identity = _body_identity("release-runtime.json", runtime, 55)
    result = successor.run_hard230_population_successor_v1(
        slate_id=SLATE,
        candidate_origin_id=ORIGIN,
        heldout_block=HELDOUT,
        worlds_per_block=width,
        source_member_identity=source["source_member_identity"],
        score_block_identities=source["score_block_identities"],
        player_registry=source["player_registry"],
        score_matrix=source["score_matrix"],
        score_matrix_identity=source["score_matrix_identity"],
        p0_target_authority=authorities["p0"],
        p0_target_authority_identity=authorities["p0_identity"],
        world_permutation_authority=authorities["permutation"],
        world_permutation_authority_identity=authorities["permutation_identity"],
        runtime_authority=runtime,
        runtime_authority_identity=runtime_identity,
        evidence_recorder=_MemoryRecorder(),
        execution_mode=successor.RELEASE_EXECUTION_MODE,
        require_production_width=False,
    )
    assert result.receipt["authoritative_solver_proofs_validated"] is True


def test_process_publishes_bounded_shards_index_and_root_create_once() -> None:
    width = 20
    target = 9
    source = _source(width=width, high_roster=None, all_players_high=True)
    authorities = _authorities(source, width=width, target=target)
    store = _MemoryStore()
    kwargs = {
        "process_request": authorities["request"],
        "process_request_identity": authorities["request_identity"],
        "process_budget": authorities["budget"],
        "process_budget_identity": authorities["budget_identity"],
        "player_registry": source["player_registry"],
        "score_matrix": source["score_matrix"],
        "p0_target_authority": authorities["p0"],
        "world_permutation_authority": authorities["permutation"],
        "runtime_authority": authorities["runtime"],
        "publisher": store.publish,
        "reader": store.read,
        "solver_callback": _solver([_roster(index) for index in range(8)]),
    }
    first = process.execute_and_publish_process_v1(**kwargs)
    second = process.execute_and_publish_process_v1(**kwargs)
    assert first.process_receipt_identity == second.process_receipt_identity
    assert first.evidence_index["evidence_shard_count"] == 2
    assert first.scientific_result.receipt["hard230_shortfall"] == 1
    assert first.process_receipt["publication_order_completed"] == (
        "evidence-shards-then-index-then-root"
    )
    assert list(store.objects)[-1].endswith("/process-receipt.json")
    assert process.validate_process_receipt_v1(first.process_receipt) == (
        first.process_receipt
    )


def test_consolidated_manifest_requires_exactly_54_unique_slate_tasks() -> None:
    rows = [
        {
            "task_index": index,
            "slate_id": f"slate-{index:02d}",
            "process_budget_identity": _identity(f"budget-{index:02d}.json", index + 1),
            "request_uri": (
                f"gs://hard230-successor-fixture/requests/request-{index:02d}.json"
            ),
            "output_prefix": (
                f"gs://hard230-successor-fixture/results/slate-{index:02d}"
            ),
        }
        for index in range(54)
    ]
    manifest = process.build_consolidated_54_task_manifest_v1(
        immutable_image_digest="sha256:" + "a" * 64,
        task_rows=rows,
        launch_intent_identity=_identity("launch.json", 200),
    )
    assert manifest["task_count"] == 54
    assert manifest["one_consolidated_image"] is True
    assert process.validate_consolidated_54_task_manifest_v1(manifest) == manifest
    with pytest.raises(
        process.Hard230PopulationProcessV1Error,
        match="exactly 54",
    ):
        process.build_consolidated_54_task_manifest_v1(
            immutable_image_digest="sha256:" + "a" * 64,
            task_rows=rows[:-1],
            launch_intent_identity=_identity("launch.json", 200),
        )


def test_outcome_blind_production_width_shape_smoke() -> None:
    result, _ = _run(width=10_000)
    receipt = result.receipt
    assert receipt["effective_solver_call_ceiling"] == 200
    assert receipt["actual_shared_solver_call_count"] == 1
    assert receipt["outcome_columns_read"] == []
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["uses_heldout_scores"] is False
    assert receipt["diagnostics_are_fit_world_only_not_heldout_effects"] is True


def test_receipts_fail_closed_on_coherent_equal_work_tamper() -> None:
    result, _ = _run()
    assert successor.validate_successor_receipt_v1(result.receipt) == result.receipt
    tampered = deepcopy(result.receipt)
    tampered["control_solver_call_budget"] += 1
    body = {
        key: value for key, value in tampered.items() if key != "successor_receipt_sha256"
    }
    tampered["successor_receipt_sha256"] = legal.canonical_sha256(body)
    with pytest.raises(
        successor.Hard230PopulationSuccessorV1Error,
        match="does not bind the replenishing shared law",
    ):
        successor.validate_successor_receipt_v1(tampered)
