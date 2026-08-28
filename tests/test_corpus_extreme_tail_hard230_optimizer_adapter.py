from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_generation_additions as hard
from nfl_dfs.research import corpus_extreme_tail_hard230_optimizer_adapter as adapter
from nfl_dfs.research import corpus_legal_feasibility as legal


HELDOUT = "R4"
ORIGIN = "R1"
TRAINING = ("R0", "R1", "R2", "R3")


def _identity(
    name: str, generation: int = 1, *, content_sha256: str | None = None, size: int = 100
) -> dict[str, object]:
    return {
        "uri": f"gs://hard230-fixture/{name}",
        "generation": str(generation),
        "sha256": content_sha256 or legal.canonical_sha256(
            {"name": name, "generation": generation}
        ),
        "bytes": size,
    }


class _MemoryPublisher:
    def __init__(self, *, corrupt: bool = False) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.corrupt = corrupt

    def __call__(
        self, *, role: str, deterministic_key: str, payload: bytes
    ) -> dict[str, object]:
        key = (role, deterministic_key)
        prior = self.objects.setdefault(key, payload)
        if prior != payload:
            raise AssertionError("create-once fixture collision differs")
        digest = hashlib.sha256(payload).hexdigest()
        return {
            "uri": f"gs://hard230-fixture/evidence/{role}/{deterministic_key}.json",
            "generation": "11",
            "sha256": "0" * 64 if self.corrupt else digest,
            "bytes": len(payload),
        }


def _players() -> list[dict[str, object]]:
    rows = [
        {"id": player_id, "pos": position, "team": team, "opp": opponent,
         "game_id": game_id, "salary": 5500}
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
    proof_kind: str,
    implementation_sha256: str,
    input_body: object,
    output_body: object,
) -> dict[str, object]:
    return {
        "proof_id": proof_id,
        "proof_kind": proof_kind,
        "implementation_sha256": implementation_sha256,
        "input_sha256": legal.canonical_sha256(input_body),
        "output_sha256": legal.canonical_sha256(output_body),
        "proof_object_identity": _identity(f"proofs/{proof_id}.json", 7),
    }


def _source(*, width: int, high_roster: list[str] | None) -> dict[str, object]:
    players = _players()
    source_sha = legal.canonical_sha256({"slate": "fixture"})
    source_member = {
        "member_id": "fixture-member",
        "slate_id": "2023-w01",
        "member_sha256": source_sha,
        "object_identity": _identity(
            "source-member.json", 2, content_sha256=source_sha
        ),
    }
    block_identities = [
        {
            "block_id": block,
            "world_count": width,
            "source_member_sha256": source_sha,
            "object_identity": _identity(f"blocks/{block}.npy", ordinal + 3),
        }
        for ordinal, block in enumerate(TRAINING)
    ]
    matrix = np.zeros((len(players), len(TRAINING) * width), dtype="<i8")
    if high_roster is not None:
        player_index = {str(row["id"]): index for index, row in enumerate(players)}
        for player_id in high_roster:
            matrix[player_index[player_id], :] = 30_000
    matrix_sha = hard.canonical_score_matrix_sha256_v1(matrix)
    artifact = _identity("player-score-matrix.npy", 20)
    derivation_input = {
        "matrix_id": "fixture-fit-matrix",
        "score_unit": "milli-DraftKings-points",
        "matrix_shape": list(matrix.shape),
        "artifact_identity": artifact,
        "source_member_sha256": source_sha,
        "score_block_identities_sha256": legal.canonical_sha256(block_identities),
        "player_registry_sha256": legal.canonical_sha256(players),
    }
    matrix_identity = {
        "matrix_id": "fixture-fit-matrix",
        "score_unit": "milli-DraftKings-points",
        "matrix_shape": list(matrix.shape),
        "canonical_score_matrix_sha256": matrix_sha,
        "artifact_identity": artifact,
        "source_member_sha256": source_sha,
        "score_block_identities_sha256": legal.canonical_sha256(block_identities),
        "player_registry_sha256": legal.canonical_sha256(players),
        "derivation_proof_identity": _proof(
            proof_id="matrix-derivation",
            proof_kind="score-matrix-derivation-v1",
            implementation_sha256="8" * 64,
            input_body=derivation_input,
            output_body={"canonical_score_matrix_sha256": matrix_sha},
        ),
    }
    return {
        "source_member_identity": source_member,
        "score_block_identities": block_identities,
        "player_registry": players,
        "score_matrix": matrix,
        "score_matrix_identity": matrix_identity,
    }


def _paired_control(source: dict[str, object], *, target: int) -> dict[str, object]:
    receipt_sha = legal.canonical_sha256({"control": "P0", "target": target})
    return {
        "control_population_id": "P0-incumbent-native",
        "candidate_origin_id": ORIGIN,
        "fit_scope_id": "holdout-R4",
        "heldout_block": HELDOUT,
        "training_blocks": list(TRAINING),
        "source_member_sha256": source["source_member_identity"]["member_sha256"],
        "score_block_ids": list(TRAINING),
        "score_block_identities_sha256": legal.canonical_sha256(
            source["score_block_identities"]
        ),
        "player_registry_sha256": legal.canonical_sha256(source["player_registry"]),
        "score_matrix_sha256": source["score_matrix_identity"][
            "canonical_score_matrix_sha256"
        ],
        "retained_count": target,
        "retained_roster_ids_sha256": "b" * 64,
        "control_receipt_sha256": receipt_sha,
        "receipt_identity": _identity(
            "paired-control.json", 9, content_sha256=receipt_sha
        ),
    }


def _authority() -> dict[str, object]:
    source_path = Path(adapter.__file__)
    return {
        "schema_version": adapter.OUTER_AUTHORITY_SCHEMA,
        "source_commit_sha": "1" * 40,
        "immutable_image_digest": "sha256:" + "2" * 64,
        "outer_adapter_source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "solver_implementation_sha256": "3" * 64,
        "solver_authority_sha256": "4" * 64,
        "incumbent_profile_sha256": legal.frozen_policy_profiles()[0].parameter_set_sha256,
        "optimizer_source_identity": _identity("source.tar", 12),
        "terminal_runtime_receipt_identity": _identity("runtime.json", 13),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }


def _solver(rosters: list[list[str]]):
    def solve(request: legal.SolveRequest) -> legal.SolveOutcome:
        roster = rosters[min(request.visit_ordinal, len(rosters) - 1)]
        return legal._make_mock_optimal_outcome(request, roster)

    return solve


def _run(
    *,
    width: int = 4,
    high_roster: list[str] | None = None,
    solver_rosters: list[list[str]] | None = None,
    target: int = 1,
    publisher: _MemoryPublisher | None = None,
    execution_mode: str = adapter.FIXTURE_EXECUTION_MODE,
    require_production_width: bool = False,
) -> adapter.Hard230OuterOptimizerResult:
    high = _roster(7) if high_roster is None else high_roster
    source = _source(width=width, high_roster=high)
    rosters = solver_rosters or [high]
    return adapter.run_hard230_outer_optimizer_v1(
        slate_id="2023-w01",
        candidate_origin_id=ORIGIN,
        heldout_block=HELDOUT,
        worlds_per_block=width,
        **source,
        ordered_generator_world_indices=list(range(width)),
        paired_control=_paired_control(source, target=target),
        optimizer_authority=_authority(),
        evidence_publisher=publisher or _MemoryPublisher(),
        execution_mode=execution_mode,
        require_production_width=require_production_width,
        solver_callback=_solver(rosters),
    )


def test_hard230_is_new_population_generation_and_replenishes_rejections() -> None:
    low = _roster(0)
    high = _roster(7)
    result = _run(
        high_roster=high,
        solver_rosters=[low, low, high],
    )
    outer = result.outer_receipt
    generation = result.hard230_generation_receipt
    assert outer["mechanism_class"] == (
        "population-generation-with-deterministic-replenishment"
    )
    assert outer["is_selector"] is False
    assert outer["is_strict230_admission_filter"] is False
    assert outer["is_legacy_t230_panel"] is False
    assert outer["actual_shared_solver_call_count"] == 3
    assert outer["equal_solver_call_budget"] is True
    assert outer["solver_occurrences_shared_not_reexecuted"] is True
    assert generation["retained_count_pending_outer_solver_replay"] == 1
    assert generation["rejection_counts"]["duplicate-generated-roster"] == 1
    assert generation["rejection_counts"]["no-inclusive-230-permitted-world-hit"] == 1
    assert outer["score_blind_comparator_population"]["population_rosters"][0][
        "roster_player_ids"
    ] == low
    assert outer["hard230_population"]["population_rosters"][0][
        "roster_player_ids"
    ] == high


def test_shortfall_is_exact_ceiling_exhaustion_without_threshold_lowering() -> None:
    low = _roster(0)
    source = _source(width=2, high_roster=None)
    result = adapter.run_hard230_outer_optimizer_v1(
        slate_id="2023-w01",
        candidate_origin_id=ORIGIN,
        heldout_block=HELDOUT,
        worlds_per_block=2,
        **source,
        ordered_generator_world_indices=[1, 0],
        paired_control=_paired_control(source, target=1),
        optimizer_authority=_authority(),
        evidence_publisher=_MemoryPublisher(),
        execution_mode=adapter.FIXTURE_EXECUTION_MODE,
        require_production_width=False,
        solver_callback=_solver([low, low]),
    )
    outer = result.outer_receipt
    generation = result.hard230_generation_receipt
    assert outer["termination_reason"] == (
        "frozen-effective-ceiling-exhausted-with-shortfall"
    )
    assert outer["hard230_shortfall"] == 1
    assert outer["actual_shared_solver_call_count"] == 2
    assert generation["status"] == "failed-exhausted-with-retained-shortfall"
    assert generation["threshold_was_not_lowered"] is True
    assert generation["effective_ceiling_exhausted"] is True


def test_population_diagnostics_bind_200_220_230_availability_density_and_oracle() -> None:
    result = _run()
    diagnostics = result.outer_receipt["hard230_population"]
    assert [
        row["threshold_milli_dk"] for row in diagnostics["threshold_diagnostics"]
    ] == [200_000, 220_000, 230_000]
    assert all(
        row["available_lineup_count"] == 1
        and row["lineup_world_hit_count"] == diagnostics["fit_world_count"]
        and row["oracle_world_hit_count"] == diagnostics["fit_world_count"]
        for row in diagnostics["threshold_diagnostics"]
    )
    assert diagnostics["oracle_maximum_score_milli_dk"] == 270_000
    assert diagnostics["diagnostic_scope"] == "simulated-permitted-fit-worlds-only"
    assert diagnostics["uses_realized_outcomes"] is False


def test_lineup_ids_are_canonical_roster_hash_identities() -> None:
    result = _run()
    row = result.outer_receipt["hard230_population"]["population_rosters"][0]
    assert row["lineup_id"] == f"hard230-roster-{row['roster_sha256']}"
    assert row["roster_sha256"] == legal.canonical_sha256(row["roster_player_ids"])


def test_release_refuses_fixture_solver_without_exact_cbc_proof() -> None:
    with pytest.raises(
        adapter.Hard230OuterOptimizerAdapterError,
        match=r"solver proof\[0\] is not authoritative",
    ):
        _run(execution_mode=adapter.RELEASE_EXECUTION_MODE)


def test_release_mode_executes_and_validates_real_local_cbc_proof() -> None:
    source = _source(width=1, high_roster=_roster(7))
    authority = _authority()
    authority["solver_authority_sha256"] = legal.canonical_sha256(
        legal._cbc_runtime_authority()
    )
    result = adapter.run_hard230_outer_optimizer_v1(
        slate_id="2023-w01",
        candidate_origin_id=ORIGIN,
        heldout_block=HELDOUT,
        worlds_per_block=1,
        **source,
        ordered_generator_world_indices=[0],
        paired_control=_paired_control(source, target=1),
        optimizer_authority=authority,
        evidence_publisher=_MemoryPublisher(),
        execution_mode=adapter.RELEASE_EXECUTION_MODE,
        require_production_width=False,
    )
    assert result.outer_receipt["authoritative_solver_proofs_validated"] is True
    assert result.outer_receipt["fixture_solver_proof_bypass"] is False
    assert result.outer_receipt["hard230_exact_target_reached"] is True


def test_publisher_must_return_identity_for_exact_published_bytes() -> None:
    with pytest.raises(
        adapter.Hard230OuterOptimizerAdapterError,
        match="differs from the exact bytes",
    ):
        _run(publisher=_MemoryPublisher(corrupt=True))


def test_missing_or_mismatched_optimizer_authority_fails_before_solver() -> None:
    source = _source(width=2, high_roster=_roster(7))
    authority = _authority()
    authority["outcome_columns_read"] = ["fantasy_points"]
    calls = 0

    def solver(request: legal.SolveRequest) -> legal.SolveOutcome:
        nonlocal calls
        calls += 1
        return legal._make_mock_optimal_outcome(request, _roster(7))

    with pytest.raises(
        adapter.Hard230OuterOptimizerAdapterError,
        match="may not expose outcome columns",
    ):
        adapter.run_hard230_outer_optimizer_v1(
            slate_id="2023-w01",
            candidate_origin_id=ORIGIN,
            heldout_block=HELDOUT,
            worlds_per_block=2,
            **source,
            ordered_generator_world_indices=[0, 1],
            paired_control=_paired_control(source, target=1),
            optimizer_authority=authority,
            evidence_publisher=_MemoryPublisher(),
            execution_mode=adapter.FIXTURE_EXECUTION_MODE,
            require_production_width=False,
            solver_callback=solver,
        )
    assert calls == 0


def test_unbound_discovery_origin_and_frozen_player_cap_fail_precisely() -> None:
    source = _source(width=2, high_roster=_roster(7))
    with pytest.raises(
        adapter.Hard230OuterOptimizerAdapterError,
        match="R5..R19 lack a bound optimizer WorldId authority",
    ):
        adapter.run_hard230_outer_optimizer_v1(
            slate_id="2023-w01",
            candidate_origin_id="R5",
            heldout_block=HELDOUT,
            worlds_per_block=2,
            **source,
            ordered_generator_world_indices=[0, 1],
            paired_control=_paired_control(source, target=1),
            optimizer_authority=_authority(),
            evidence_publisher=_MemoryPublisher(),
            execution_mode=adapter.FIXTURE_EXECUTION_MODE,
            require_production_width=False,
            solver_callback=_solver([_roster(7)]),
        )

    oversized = deepcopy(source)
    template = dict(oversized["player_registry"][-1])
    extra = []
    for index in range(501):
        row = dict(template)
        row["id"] = f"zz-extra-{index:03d}"
        extra.append(row)
    oversized["player_registry"] = [*oversized["player_registry"], *extra]
    oversized["score_matrix"] = np.zeros((513, 8), dtype="<i8")
    with pytest.raises(
        adapter.Hard230OuterOptimizerAdapterError,
        match="9..512-player bound",
    ):
        adapter.run_hard230_outer_optimizer_v1(
            slate_id="2023-w01",
            candidate_origin_id=ORIGIN,
            heldout_block=HELDOUT,
            worlds_per_block=2,
            **oversized,
            ordered_generator_world_indices=[0, 1],
            paired_control=_paired_control(source, target=1),
            optimizer_authority=_authority(),
            evidence_publisher=_MemoryPublisher(),
            execution_mode=adapter.FIXTURE_EXECUTION_MODE,
            require_production_width=False,
            solver_callback=_solver([_roster(7)]),
        )


def test_outer_receipt_self_hash_and_equal_work_fail_closed_on_tamper() -> None:
    result = _run()
    validated = adapter.validate_hard230_outer_receipt_v1(result.outer_receipt)
    assert validated == result.outer_receipt
    tampered = deepcopy(result.outer_receipt)
    tampered["control_solver_call_budget"] += 1
    with pytest.raises(
        adapter.Hard230OuterOptimizerAdapterError,
        match="self-hash differs",
    ):
        adapter.validate_hard230_outer_receipt_v1(tampered)
    coherent = deepcopy(result.outer_receipt)
    coherent["control_solver_call_budget"] += 1
    body = {
        key: value for key, value in coherent.items() if key != "outer_receipt_sha256"
    }
    coherent["outer_receipt_sha256"] = legal.canonical_sha256(body)
    with pytest.raises(
        adapter.Hard230OuterOptimizerAdapterError,
        match="does not bind equal shared solver work",
    ):
        adapter.validate_hard230_outer_receipt_v1(coherent)


def test_outcome_blind_production_world_shape_smoke() -> None:
    width = hard.PRODUCTION_WORLDS_PER_BLOCK
    publisher = _MemoryPublisher()
    result = _run(
        width=width,
        publisher=publisher,
        require_production_width=True,
    )
    outer = result.outer_receipt
    assert outer["actual_shared_solver_call_count"] == 1
    assert outer["effective_solver_call_ceiling"] == 200
    assert outer["outcome_columns_read"] == []
    assert outer["uses_realized_outcomes"] is False
    assert outer["diagnostics_are_fit_world_only_not_heldout_effects"] is True
    assert len(publisher.objects) == 3  # solver, legality, stream manifest
