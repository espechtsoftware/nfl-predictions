from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_generation_additions as additions
from nfl_dfs.research.corpus_legal_feasibility import canonical_sha256


WIDTH = 4
HELDOUT = "R4"
TRAINING_BLOCKS = ("R0", "R1", "R2", "R3")
ORIGIN = "R1"
SOLVER_IMPLEMENTATION_SHA256 = "7" * 64
MATRIX_DERIVATION_IMPLEMENTATION_SHA256 = "8" * 64


def _identity(
    name: str, generation: int = 1, *, content_sha256: str | None = None
) -> dict[str, object]:
    return {
        "uri": f"gs://fixture/{name}",
        "generation": str(generation),
        "sha256": (
            canonical_sha256({"name": name, "generation": generation})
            if content_sha256 is None
            else content_sha256
        ),
        "bytes": 100 + generation,
    }


def _proof(
    *,
    proof_id: str,
    proof_kind: str,
    implementation_sha256: str,
    input_body: object,
    output_body: object,
) -> dict[str, object]:
    content_hash = canonical_sha256(
        {
            "proof_id": proof_id,
            "proof_kind": proof_kind,
            "input": input_body,
            "output": output_body,
        }
    )
    return {
        "proof_id": proof_id,
        "proof_kind": proof_kind,
        "implementation_sha256": implementation_sha256,
        "input_sha256": canonical_sha256(input_body),
        "output_sha256": canonical_sha256(output_body),
        "proof_object_identity": _identity(
            f"proofs/{proof_id}.json", 31, content_sha256=content_hash
        ),
    }


def _players() -> list[dict[str, object]]:
    rows = [
        {
            "id": player_id,
            "pos": position,
            "team": team,
            "opp": opponent,
            "game_id": game_id,
            "salary": 5500,
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
    a_receiver = ("a-wr2", "a-wr3")[(seed // 1) % 2]
    b_receiver = ("b-wr1", "b-wr2")[(seed // 2) % 2]
    c_receiver = ("c-wr1", "c-wr2")[(seed // 4) % 2]
    return sorted(
        [
            "a-qb",
            "a-rb",
            "a-wr1",
            a_receiver,
            "b-rb",
            b_receiver,
            "c-dst",
            "c-te",
            c_receiver,
        ]
    )


def _source_member() -> dict[str, object]:
    member_sha = canonical_sha256({"member": "fixture-slate"})
    return {
        "member_id": "panel-member-fixture",
        "slate_id": "2022-W01-main",
        "member_sha256": member_sha,
        "object_identity": _identity(
            "panel/member.json", 2, content_sha256=member_sha
        ),
    }


def _score_matrix(
    block_ids: tuple[str, ...], *, width: int = WIDTH, all_zero: bool = False
) -> np.ndarray:
    players = _players()
    matrix = np.zeros((len(players), len(block_ids) * width), dtype="<i8")
    if all_zero:
        return matrix
    for block_ordinal, _ in enumerate(block_ids):
        for world_index in range(width):
            column = block_ordinal * width + world_index
            profile = world_index % 3
            for player_ordinal, player in enumerate(players):
                if profile == 0:
                    value = 20_000 if player["game_id"] == "g1" else 5_000
                elif profile == 1:
                    value = 10_000 if player["game_id"] == "g1" else 15_000
                else:
                    value = 8_000 if player["game_id"] == "g1" else 16_000
                matrix[player_ordinal, column] = value
    # All legal fixture rosters have a literal inclusive-230 hit here.
    matrix[:, 0] = 30_000
    return matrix


def _block_identities(
    block_ids: tuple[str, ...], *, width: int, source_member_sha256: str
) -> list[dict[str, object]]:
    return [
        {
            "block_id": block_id,
            "world_count": width,
            "source_member_sha256": source_member_sha256,
            "object_identity": _identity(
                f"scores/{block_id.lower()}.npy", ordinal + 10
            ),
        }
        for ordinal, block_id in enumerate(block_ids)
    ]


def _matrix_source(
    block_ids: tuple[str, ...], *, width: int = WIDTH, all_zero: bool = False
) -> dict[str, object]:
    source = _source_member()
    players = _players()
    blocks = _block_identities(
        block_ids,
        width=width,
        source_member_sha256=str(source["member_sha256"]),
    )
    matrix = _score_matrix(block_ids, width=width, all_zero=all_zero)
    matrix_hash = additions.canonical_score_matrix_sha256_v1(matrix)
    artifact = _identity("scores/player-score-matrix.npy", 25)
    matrix_id = f"fixture-{'-'.join(block_ids).lower()}-matrix"
    derivation_input = {
        "matrix_id": matrix_id,
        "score_unit": "milli-DraftKings-points",
        "matrix_shape": [len(players), len(block_ids) * width],
        "artifact_identity": artifact,
        "source_member_sha256": source["member_sha256"],
        "score_block_identities_sha256": canonical_sha256(blocks),
        "player_registry_sha256": canonical_sha256(players),
    }
    identity = {
        "matrix_id": matrix_id,
        "score_unit": "milli-DraftKings-points",
        "matrix_shape": [len(players), len(block_ids) * width],
        "canonical_score_matrix_sha256": matrix_hash,
        "artifact_identity": artifact,
        "source_member_sha256": source["member_sha256"],
        "score_block_identities_sha256": canonical_sha256(blocks),
        "player_registry_sha256": canonical_sha256(players),
        "derivation_proof_identity": _proof(
            proof_id=f"derive-{matrix_id}",
            proof_kind="score-matrix-derivation-v1",
            implementation_sha256=MATRIX_DERIVATION_IMPLEMENTATION_SHA256,
            input_body=derivation_input,
            output_body={"canonical_score_matrix_sha256": matrix_hash},
        ),
    }
    return {
        "source_member_identity": source,
        "score_block_identities": blocks,
        "player_registry": players,
        "score_matrix": matrix,
        "score_matrix_identity": identity,
    }


def _lineage(source: dict[str, object]) -> dict[str, object]:
    identity = source["score_matrix_identity"]
    return {
        "source_member_sha256": source["source_member_identity"]["member_sha256"],
        "score_block_ids": [
            row["block_id"] for row in source["score_block_identities"]
        ],
        "score_block_identities_sha256": canonical_sha256(
            source["score_block_identities"]
        ),
        "player_registry_sha256": canonical_sha256(source["player_registry"]),
        "score_matrix_sha256": identity["canonical_score_matrix_sha256"],
        "matrix_derivation_proof_identity_sha256": canonical_sha256(
            identity["derivation_proof_identity"]
        ),
    }


def _legality_proof(
    roster: list[str],
    source: dict[str, object],
    *,
    passed: bool = True,
    suffix: str = "",
) -> dict[str, object]:
    input_body = {
        "legality_audit_law_id": additions.LEGALITY_AUDIT_LAW_ID,
        "roster_player_ids": roster,
        "player_registry_sha256": canonical_sha256(source["player_registry"]),
    }
    return _proof(
        proof_id=f"legality-{canonical_sha256(roster)[:12]}{suffix}",
        proof_kind="independent-classic-legality-audit-v1",
        implementation_sha256=additions.LEGALITY_AUDIT_IMPLEMENTATION_SHA256,
        input_body=input_body,
        output_body={"legality_passed": passed},
    )


def _hard_occurrences(
    source: dict[str, object],
    order: list[int],
    roster_seeds: list[int],
    *,
    origin: str = ORIGIN,
    statuses: list[str] | None = None,
) -> list[dict[str, object]]:
    stream_id = f"hard230-{origin.lower()}-stream-v1"
    configuration_sha = "a" * 64
    lineage = _lineage(source)
    rows: list[dict[str, object]] = []
    for position, roster_seed in enumerate(roster_seeds):
        status = "optimal" if statuses is None else statuses[position]
        roster = _roster(roster_seed) if status == "optimal" else None
        solver_input = {
            "strategy_id": additions.HARD230_STRATEGY_ID,
            "generator_law_id": additions.HARD230_GENERATOR_LAW_ID,
            "stream_id": stream_id,
            "generator_configuration_sha256": configuration_sha,
            "candidate_origin_id": origin,
            "stream_position": position,
            "source_world_index": order[position],
            **lineage,
        }
        rows.append(
            {
                "stream_position": position,
                "source_world_index": order[position],
                "solver_call_ordinal": position,
                "solver_status": status,
                "solver_proof_identity": _proof(
                    proof_id=f"hard-solve-{position}",
                    proof_kind="incumbent-world-optimum-solver-result-v1",
                    implementation_sha256=SOLVER_IMPLEMENTATION_SHA256,
                    input_body=solver_input,
                    output_body={
                        "solver_status": status,
                        "roster_player_ids": roster,
                    },
                ),
                "roster_player_ids": roster,
                "legality_proof_identity": (
                    _legality_proof(roster, source, suffix=f"-{position}")
                    if roster is not None
                    else None
                ),
                "uses_realized_outcomes": False,
                "uses_atlas_world_ranking": False,
            }
        )
    return rows


def _hard_inputs(
    *,
    width: int = WIDTH,
    target: int = 2,
    roster_seeds: list[int] | None = None,
    all_zero: bool = False,
    origin: str = ORIGIN,
    heldout: str | None = HELDOUT,
) -> dict[str, object]:
    training = additions.WORLD_BLOCKS if heldout is None else tuple(
        block for block in additions.WORLD_BLOCKS if block != heldout
    )
    block_ids = (
        (*training, origin) if origin not in additions.WORLD_BLOCKS else training
    )
    source = _matrix_source(tuple(block_ids), width=width, all_zero=all_zero)
    order = list(reversed(range(width)))
    seeds = [0, 0, 1] if roster_seeds is None else roster_seeds
    occurrences = _hard_occurrences(source, order, seeds, origin=origin)
    lineage = _lineage(source)
    stream = {
        "stream_id": f"hard230-{origin.lower()}-stream-v1",
        "candidate_origin_id": origin,
        "generator_law_id": additions.HARD230_GENERATOR_LAW_ID,
        "generator_configuration_sha256": "a" * 64,
        "solver_implementation_sha256": SOLVER_IMPLEMENTATION_SHA256,
        "source_member_sha256": lineage["source_member_sha256"],
        "score_block_identities_sha256": lineage["score_block_identities_sha256"],
        "player_registry_sha256": lineage["player_registry_sha256"],
        "score_matrix_sha256": lineage["score_matrix_sha256"],
        "ordered_world_indices_sha256": canonical_sha256(order),
        "ordered_occurrence_inputs_sha256": additions._ordered_records_sha256(
            occurrences, label="generator occurrence inputs"
        ),
        "occurrence_count": len(occurrences),
        "stream_manifest_identity": _identity("hard/stream-manifest.json", 30),
    }
    fit_scope_id = "all-block-final-fit" if heldout is None else f"holdout-{heldout}"
    control_receipt_sha = canonical_sha256({"control": "hard", "target": target})
    control = {
        "control_population_id": "P0-incumbent-native",
        "candidate_origin_id": origin,
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout,
        "training_blocks": list(training),
        "source_member_sha256": lineage["source_member_sha256"],
        "score_block_ids": list(block_ids),
        "score_block_identities_sha256": lineage["score_block_identities_sha256"],
        "player_registry_sha256": lineage["player_registry_sha256"],
        "score_matrix_sha256": lineage["score_matrix_sha256"],
        "retained_count": target,
        "retained_roster_ids_sha256": "b" * 64,
        "control_receipt_sha256": control_receipt_sha,
        "receipt_identity": _identity(
            "hard/control.json", 21, content_sha256=control_receipt_sha
        ),
    }
    return {
        "candidate_origin_id": origin,
        "heldout_block": heldout,
        "worlds_per_block": width,
        **source,
        "generator_stream_identity": stream,
        "ordered_generator_world_indices": order,
        "paired_control": control,
        "occurrences": occurrences,
        "require_production_width": False,
    }


def _rehash_top(value: dict[str, object], field: str) -> None:
    value[field] = canonical_sha256(
        {key: item for key, item in value.items() if key != field}
    )


def test_literal_contracts_freeze_exact_public_ids_and_false_authority() -> None:
    hard = additions.frozen_hard230_generation_replenishment_contract_v1()
    discovery = additions.frozen_game_regime_tail_discovery_contract_v1()
    assert additions.HARD230_STRATEGY_ID == "hard-230-generate-replenish-v1"
    assert additions.DISCOVERY_STRATEGY_ID == (
        "game-regime-stratified-tail-discovery-v1"
    )
    assert hard["hard230_contract_sha256"] == (
        additions.EXPECTED_HARD230_CONTRACT_BODY_SHA256
    )
    assert discovery["discovery_contract_sha256"] == (
        additions.EXPECTED_DISCOVERY_CONTRACT_BODY_SHA256
    )
    assert hard["strategy_sha256"] == additions.EXPECTED_HARD230_STRATEGY_SHA256
    assert discovery["implementation_sha256"] == (
        additions.EXPECTED_DISCOVERY_IMPLEMENTATION_SHA256
    )
    assert hard["publication_authority"] is False
    assert discovery["solver_proof_authority"] is False


@pytest.mark.parametrize("body_name", ["hard-strategy", "discovery-implementation"])
def test_literal_hashes_reject_coherent_body_drift(
    monkeypatch: pytest.MonkeyPatch, body_name: str
) -> None:
    if body_name == "hard-strategy":
        original = additions._hard230_strategy_body

        def changed() -> dict[str, object]:
            body = original()
            body["retention_threshold_milli_dk"] = 229_000
            return body

        monkeypatch.setattr(additions, "_hard230_strategy_body", changed)
    else:
        original = additions._discovery_implementation_body

        def changed() -> dict[str, object]:
            body = original()
            body["world_aggregate_chunk_size"] = 512
            return body

        monkeypatch.setattr(additions, "_discovery_implementation_body", changed)
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="literal generation-addition",
    ):
        additions.frozen_hard230_generation_replenishment_contract_v1()


def test_hard230_replays_source_scores_legality_and_exact_stream() -> None:
    inputs = _hard_inputs()
    receipt = additions.build_hard230_generation_replenishment_v1(**inputs)
    assert receipt["status"] == (
        "mechanically-complete-pending-outer-solver-replay"
    )
    assert receipt["fit_scope_id"] == "holdout-R4"
    assert receipt["training_blocks"] == list(TRAINING_BLOCKS)
    assert receipt["attempted_visit_count"] == 3
    assert receipt["retained_count_pending_outer_solver_replay"] == 2
    assert receipt["cell_acceptance"] is False
    assert receipt["eligible_for_outer_acceptance_replay"] is True
    assert receipt["publication_authority"] is False
    assert [row["decision"] for row in receipt["occurrences"]] == [
        "retained-pending-outer-solver-replay",
        "rejected",
        "retained-pending-outer-solver-replay",
    ]
    assert receipt["occurrences"][1]["rejection_reason"] == (
        "duplicate-generated-roster"
    )
    assert all(
        row["score_scan"]["score_derivation_replayed_locally"] is True
        for row in (receipt["occurrences"][0], receipt["occurrences"][2])
    )
    assert all(
        row["solver_optimality_proven_locally"] is False
        for row in receipt["occurrences"]
    )


def test_hard230_final_and_discovery_origin_score_block_arithmetic() -> None:
    final_inputs = _hard_inputs(heldout=None)
    final_receipt = additions.build_hard230_generation_replenishment_v1(
        **final_inputs
    )
    assert final_receipt["scope_kind"] == "final-fit"
    assert final_receipt["source_lineage"]["score_block_ids"] == list(
        additions.WORLD_BLOCKS
    )

    discovery_inputs = _hard_inputs(origin="R5")
    discovery_receipt = additions.build_hard230_generation_replenishment_v1(
        **discovery_inputs
    )
    assert discovery_receipt["candidate_origin_is_discovery_only"] is True
    assert discovery_receipt["source_lineage"]["score_block_ids"] == [
        *TRAINING_BLOCKS,
        "R5",
    ]
    assert HELDOUT not in discovery_receipt["source_lineage"]["score_block_ids"]


@pytest.mark.parametrize(
    "field",
    [
        "candidate_origin_id",
        "fit_scope_id",
        "heldout_block",
        "training_blocks",
        "source_member_sha256",
        "score_block_ids",
        "score_block_identities_sha256",
        "player_registry_sha256",
        "score_matrix_sha256",
    ],
)
def test_hard230_paired_control_exact_binds_origin_scope_and_source(
    field: str,
) -> None:
    inputs = _hard_inputs()
    control = deepcopy(inputs["paired_control"])
    if field == "candidate_origin_id":
        control[field] = "R2"
    elif field == "fit_scope_id":
        control[field] = "holdout-R3"
    elif field == "heldout_block":
        control[field] = "R3"
    elif field == "training_blocks":
        control[field] = ["R0", "R1", "R2", "R4"]
    elif field == "score_block_ids":
        control[field] = ["R0", "R1", "R2", "R4"]
    else:
        control[field] = "f" * 64
    inputs["paired_control"] = control
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="paired control differs",
    ):
        additions.build_hard230_generation_replenishment_v1(**inputs)


def test_hard230_shortfall_exhausts_without_lowering_or_heldout_borrow() -> None:
    inputs = _hard_inputs(
        all_zero=True, roster_seeds=[0, 1, 2, 3], target=2
    )
    receipt = additions.build_hard230_generation_replenishment_v1(**inputs)
    assert receipt["status"] == "failed-exhausted-with-retained-shortfall"
    assert receipt["retained_shortfall"] == 2
    assert receipt["effective_ceiling_exhausted"] is True
    assert receipt["retention_threshold_milli_dk"] == 230_000
    assert receipt["threshold_was_not_lowered"] is True
    assert receipt["heldout_candidates_were_not_borrowed"] is True
    assert receipt["cell_acceptance"] is False


def test_hard230_rejects_early_stop_threshold_and_heldout_origin() -> None:
    early = _hard_inputs(all_zero=True, roster_seeds=[0, 1], target=2)
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="stopped before target",
    ):
        additions.build_hard230_generation_replenishment_v1(**early)
    heldout = _hard_inputs(origin=HELDOUT)
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="heldout candidate origin",
    ):
        additions.build_hard230_generation_replenishment_v1(**heldout)


@pytest.mark.parametrize(
    "attack", ["order", "raw-occurrence", "proof-input", "solver-implementation"]
)
def test_hard230_stream_and_generation_pinned_proofs_fail_closed(
    attack: str,
) -> None:
    inputs = _hard_inputs()
    if attack == "order":
        inputs["ordered_generator_world_indices"] = [3, 2, 2, 0]
    elif attack == "raw-occurrence":
        inputs["occurrences"][0]["source_world_index"] = 0
    elif attack == "proof-input":
        inputs["occurrences"][0]["solver_proof_identity"]["input_sha256"] = "0" * 64
        inputs["generator_stream_identity"]["ordered_occurrence_inputs_sha256"] = (
            additions._ordered_records_sha256(
                inputs["occurrences"], label="generator occurrence inputs"
            )
        )
    else:
        inputs["occurrences"][0]["solver_proof_identity"][
            "implementation_sha256"
        ] = "1" * 64
        inputs["generator_stream_identity"]["ordered_occurrence_inputs_sha256"] = (
            additions._ordered_records_sha256(
                inputs["occurrences"], label="generator occurrence inputs"
            )
        )
    with pytest.raises(additions.CorpusExtremeTailGenerationAdditionsError):
        additions.build_hard230_generation_replenishment_v1(**inputs)


def test_hard230_rejects_matrix_content_and_legality_lineage_splices() -> None:
    inputs = _hard_inputs()
    inputs["score_matrix"][0, 0] += 1
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="score matrix identity differs",
    ):
        additions.build_hard230_generation_replenishment_v1(**inputs)

    inputs = _hard_inputs()
    inputs["occurrences"][0]["legality_proof_identity"]["output_sha256"] = (
        canonical_sha256({"legality_passed": False})
    )
    inputs["generator_stream_identity"]["ordered_occurrence_inputs_sha256"] = (
        additions._ordered_records_sha256(
            inputs["occurrences"], label="generator occurrence inputs"
        )
    )
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="legality proof.*lineage differs",
    ):
        additions.build_hard230_generation_replenishment_v1(**inputs)


@pytest.mark.parametrize("attack", ["threshold", "scope", "authority", "occurrence"])
def test_hard230_replay_rejects_coherent_receipt_rehashes(attack: str) -> None:
    inputs = _hard_inputs()
    retained = deepcopy(
        additions.build_hard230_generation_replenishment_v1(**inputs)
    )
    if attack == "threshold":
        retained["retention_threshold_milli_dk"] = 229_000
    elif attack == "scope":
        retained["fit_scope_id"] = "holdout-R3"
    elif attack == "authority":
        retained["publication_authority"] = True
    else:
        retained["occurrences"][0]["decision"] = "rejected"
        _rehash_top(retained["occurrences"][0], "occurrence_sha256")
        retained["occurrences_sha256"] = additions._ordered_records_sha256(
            retained["occurrences"], label="hard-230 normalized occurrences"
        )
    _rehash_top(retained, "hard230_generation_receipt_sha256")
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="canonical replay differs",
    ):
        additions.validate_hard230_generation_replenishment_v1(
            retained, **inputs
        )


def _discovery_inputs(
    *,
    width: int = WIDTH,
    visits: int = 6,
    all_zero: bool = False,
) -> dict[str, object]:
    source = _matrix_source(
        additions.WORLD_BLOCKS, width=width, all_zero=all_zero
    )
    lineage = _lineage(source)
    receipt_sha = canonical_sha256(
        {"control": "discovery", "visits": visits}
    )
    control = {
        "control_id": "incumbent-equal-visit-control-v1",
        "fit_scope_id": f"holdout-{HELDOUT}",
        "heldout_block": HELDOUT,
        "training_blocks": list(TRAINING_BLOCKS),
        "source_member_sha256": lineage["source_member_sha256"],
        "ordinary_r_block_identities_sha256": lineage[
            "score_block_identities_sha256"
        ],
        "player_registry_sha256": lineage["player_registry_sha256"],
        "score_matrix_sha256": lineage["score_matrix_sha256"],
        "visit_count": visits,
        "solve_count": visits,
        "solver_implementation_sha256": SOLVER_IMPLEMENTATION_SHA256,
        "control_receipt_sha256": receipt_sha,
        "receipt_identity": _identity(
            "discovery/control.json", 27, content_sha256=receipt_sha
        ),
        "uses_realized_outcomes": False,
        "uses_atlas_world_ranking": False,
    }
    return {
        "heldout_block": HELDOUT,
        "worlds_per_block": width,
        "source_member_identity": source["source_member_identity"],
        "ordinary_r_block_identities": source["score_block_identities"],
        "player_registry": source["player_registry"],
        "ordinary_r_score_matrix": source["score_matrix"],
        "ordinary_r_score_matrix_identity": source["score_matrix_identity"],
        "control_budget_identity": control,
        "require_production_width": False,
    }


def _discovery_source_for_lineage(inputs: dict[str, object]) -> dict[str, object]:
    return {
        "source_member_identity": inputs["source_member_identity"],
        "score_block_identities": inputs["ordinary_r_block_identities"],
        "player_registry": inputs["player_registry"],
        "score_matrix": inputs["ordinary_r_score_matrix"],
        "score_matrix_identity": inputs["ordinary_r_score_matrix_identity"],
    }


def _solve_results(
    inputs: dict[str, object],
    schedule: dict[str, object],
    *,
    duplicate_second: bool = False,
) -> list[dict[str, object]]:
    source = _discovery_source_for_lineage(inputs)
    lineage = _lineage(source)
    players = source["player_registry"]
    player_index = {
        str(player["id"]): ordinal for ordinal, player in enumerate(players)
    }
    matrix = source["score_matrix"]
    width = int(inputs["worlds_per_block"])
    rows: list[dict[str, object]] = []
    for position, schedule_item in enumerate(schedule["schedule"]):
        seed = 0 if duplicate_second and position == 1 else position % 8
        roster = _roster(seed)
        block_ordinal = additions.WORLD_BLOCKS.index(schedule_item["block_id"])
        column = block_ordinal * width + int(schedule_item["world_index"])
        objective = sum(
            int(matrix[player_index[player_id], column]) for player_id in roster
        )
        solver_input = {
            "strategy_id": additions.DISCOVERY_STRATEGY_ID,
            "discovery_schedule_sha256": schedule["discovery_schedule_sha256"],
            "schedule_item_sha256": schedule_item["schedule_item_sha256"],
            "scheduled_world": {
                "block_id": schedule_item["block_id"],
                "world_index": schedule_item["world_index"],
            },
            "incumbent_legality_law_id": additions.LEGALITY_AUDIT_LAW_ID,
            **lineage,
        }
        rows.append(
            {
                "schedule_position": position,
                "schedule_item_sha256": schedule_item["schedule_item_sha256"],
                "solver_call_ordinal": position,
                "solver_status": "optimal",
                "solver_proof_identity": _proof(
                    proof_id=f"discovery-solve-{position}",
                    proof_kind="incumbent-world-optimum-solver-result-v1",
                    implementation_sha256=SOLVER_IMPLEMENTATION_SHA256,
                    input_body=solver_input,
                    output_body={
                        "solver_status": "optimal",
                        "roster_player_ids": roster,
                        "objective_score_milli_dk": objective,
                    },
                ),
                "roster_player_ids": roster,
                "legality_proof_identity": _legality_proof(
                    roster, source, suffix=f"-discovery-{position}"
                ),
                "objective_score_milli_dk": objective,
                "uses_realized_outcomes": False,
                "uses_atlas_world_ranking": False,
            }
        )
    return rows


def _discovery_bundle(
    *, all_zero: bool = False, visits: int = 6
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    inputs = _discovery_inputs(all_zero=all_zero, visits=visits)
    schedule = additions.build_game_regime_tail_discovery_schedule_v1(**inputs)
    return inputs, schedule, _solve_results(inputs, schedule)


def test_discovery_derives_deterministic_equal_budget_schedule_from_matrix() -> None:
    inputs = _discovery_inputs()
    first = additions.build_game_regime_tail_discovery_schedule_v1(**inputs)
    second = additions.build_game_regime_tail_discovery_schedule_v1(**inputs)
    assert second == first
    assert first["fit_scope_id"] == "holdout-R4"
    assert first["training_blocks"] == list(TRAINING_BLOCKS)
    assert first["control_visit_count"] == 6
    assert first["control_solve_count"] == 6
    assert first["scheduled_visit_count"] == 6
    assert first["arbitrary_caller_game_aggregates_accepted"] is False
    assert first["heldout_score_cells_used_for_schedule_features"] is False
    assert first["atlas_world_ranking_was_not_used"] is True
    assert all(row["block_id"] != HELDOUT for row in first["schedule"])
    assert len(
        {(row["block_id"], row["world_index"]) for row in first["schedule"]}
    ) == 6
    assert first["maximum_aggregate_buffer_shape"] == [2, WIDTH]
    assert first["aggregate_chunk_size"] == 256


def test_all_zero_game_totals_are_distributed_not_single_game_spike() -> None:
    inputs = _discovery_inputs(all_zero=True, visits=8)
    schedule = additions.build_game_regime_tail_discovery_schedule_v1(**inputs)
    assert {row["regime_id"] for row in schedule["schedule"]} == {
        "distributed-games"
    }
    assert all(
        row["anchor_game_points_milli_dk"] == 0 for row in schedule["schedule"]
    )
    assert all(row["anchor_game_id"] == "g1" for row in schedule["schedule"])


def test_discovery_dimension_checks_precede_aggregate_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _discovery_inputs()
    inputs["ordinary_r_score_matrix"] = inputs["ordinary_r_score_matrix"][:, :-1]

    def forbidden_zeros(*args: object, **kwargs: object) -> object:
        raise AssertionError("aggregate allocation happened before dimension check")

    monkeypatch.setattr(additions.np, "zeros", forbidden_zeros)
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="dimensions differ",
    ):
        additions.build_game_regime_tail_discovery_schedule_v1(**inputs)


@pytest.mark.parametrize(
    "attack",
    [
        "heldout",
        "training",
        "member",
        "blocks",
        "matrix",
        "budget",
        "atlas",
        "realized",
    ],
)
def test_discovery_control_exact_scope_source_budget_and_forbidden_inputs(
    attack: str,
) -> None:
    inputs = _discovery_inputs()
    control = deepcopy(inputs["control_budget_identity"])
    if attack == "heldout":
        control["heldout_block"] = "R3"
    elif attack == "training":
        control["training_blocks"] = ["R0", "R1", "R2", "R4"]
    elif attack == "member":
        control["source_member_sha256"] = "1" * 64
    elif attack == "blocks":
        control["ordinary_r_block_identities_sha256"] = "2" * 64
    elif attack == "matrix":
        control["score_matrix_sha256"] = "3" * 64
    elif attack == "budget":
        control["solve_count"] = int(control["visit_count"]) - 1
    elif attack == "atlas":
        control["uses_atlas_world_ranking"] = True
    else:
        control["uses_realized_outcomes"] = True
    inputs["control_budget_identity"] = control
    with pytest.raises(additions.CorpusExtremeTailGenerationAdditionsError):
        additions.build_game_regime_tail_discovery_schedule_v1(**inputs)


def test_discovery_rejects_player_game_membership_and_matrix_content_splices() -> None:
    inputs = _discovery_inputs()
    players = deepcopy(inputs["player_registry"])
    players[0]["game_id"] = "g9"
    inputs["player_registry"] = players
    with pytest.raises(additions.CorpusExtremeTailGenerationAdditionsError):
        additions.build_game_regime_tail_discovery_schedule_v1(**inputs)

    inputs = _discovery_inputs()
    inputs["ordinary_r_score_matrix"][0, 0] += 1
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="score matrix identity differs",
    ):
        additions.build_game_regime_tail_discovery_schedule_v1(**inputs)


def test_discovery_accounting_rebuilds_schedule_and_local_proofs() -> None:
    inputs, schedule, results = _discovery_bundle()
    accounting = additions.build_game_regime_tail_discovery_accounting_v1(
        **inputs, solve_results=results
    )
    assert accounting["discovery_schedule_sha256"] == schedule[
        "discovery_schedule_sha256"
    ]
    assert accounting["solver_call_count"] == 6
    assert accounting["reported_optimal_solve_count"] == 6
    assert accounting["locally_legal_candidate_occurrence_count"] == 6
    assert accounting["mechanically_complete"] is True
    assert accounting["cell_acceptance"] is False
    assert accounting["publication_authority"] is False
    assert all(
        row["objective_replayed_from_bound_matrix"] is True
        for row in accounting["occurrences"]
    )
    assert additions.validate_game_regime_tail_discovery_accounting_v1(
        accounting, **inputs, solve_results=results
    ) == accounting


@pytest.mark.parametrize(
    "attack",
    [
        "world-pointer",
        "objective",
        "proof-generation",
        "proof-implementation",
        "atlas",
        "realized",
    ],
)
def test_discovery_solve_world_matrix_proof_and_forbidden_splices_fail_closed(
    attack: str,
) -> None:
    inputs, _, results = _discovery_bundle()
    if attack == "world-pointer":
        results[0]["schedule_item_sha256"] = results[1]["schedule_item_sha256"]
    elif attack == "objective":
        results[0]["objective_score_milli_dk"] += 1
    elif attack == "proof-generation":
        results[0]["solver_proof_identity"]["proof_object_identity"][
            "generation"
        ] = "999"
    elif attack == "proof-implementation":
        results[0]["solver_proof_identity"]["implementation_sha256"] = "4" * 64
    elif attack == "atlas":
        results[0]["uses_atlas_world_ranking"] = True
    else:
        results[0]["uses_realized_outcomes"] = True
    if attack == "proof-generation":
        # A different generation is a different exact input; the retained
        # accounting validator must reject it against the original result set.
        changed = additions.build_game_regime_tail_discovery_accounting_v1(
            **inputs, solve_results=results
        )
        original_inputs, _, original_results = _discovery_bundle()
        with pytest.raises(
            additions.CorpusExtremeTailGenerationAdditionsError,
            match="canonical replay differs",
        ):
            additions.validate_game_regime_tail_discovery_accounting_v1(
                changed, **original_inputs, solve_results=original_results
            )
    else:
        with pytest.raises(additions.CorpusExtremeTailGenerationAdditionsError):
            additions.build_game_regime_tail_discovery_accounting_v1(
                **inputs, solve_results=results
            )


@pytest.mark.parametrize("attack", ["scope", "budget", "summary", "item", "source"])
def test_accounting_only_coherent_nested_splices_cannot_self_author(
    attack: str,
) -> None:
    inputs, _, results = _discovery_bundle()
    retained = deepcopy(
        additions.build_game_regime_tail_discovery_accounting_v1(
            **inputs, solve_results=results
        )
    )
    if attack == "scope":
        retained["fit_scope_id"] = "holdout-R3"
    elif attack == "budget":
        retained["control_visit_count"] = 5
    elif attack == "summary":
        retained["unique_candidate_roster_count"] = 1
    elif attack == "source":
        retained["source_lineage"]["score_matrix_sha256"] = "5" * 64
    else:
        retained["occurrences"][0]["scheduled_world"]["world_index"] += 1
        _rehash_top(
            retained["occurrences"][0], "discovery_occurrence_sha256"
        )
        retained["occurrences_sha256"] = additions._ordered_records_sha256(
            retained["occurrences"],
            label="tail-discovery normalized occurrences",
        )
    _rehash_top(retained, "discovery_accounting_sha256")
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="canonical replay differs",
    ):
        additions.validate_game_regime_tail_discovery_accounting_v1(
            retained, **inputs, solve_results=results
        )


def test_schedule_replay_rejects_coherent_scope_item_and_summary_splice() -> None:
    inputs = _discovery_inputs()
    retained = deepcopy(
        additions.build_game_regime_tail_discovery_schedule_v1(**inputs)
    )
    retained["heldout_block"] = "R3"
    retained["schedule"][0]["world_index"] += 1
    _rehash_top(retained["schedule"][0], "schedule_item_sha256")
    retained["schedule_items_sha256"] = additions._ordered_records_sha256(
        retained["schedule"], label="tail-discovery schedule items"
    )
    retained["scheduled_visit_count"] -= 1
    _rehash_top(retained, "discovery_schedule_sha256")
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="canonical replay differs",
    ):
        additions.validate_game_regime_tail_discovery_schedule_v1(
            retained, **inputs
        )


def test_heldout_evaluation_is_exactly_bound_and_reads_only_heldout_slice() -> None:
    inputs, _, results = _discovery_bundle()
    evaluation = (
        additions.build_game_regime_tail_discovery_heldout_evaluation_v1(
            **inputs, solve_results=results
        )
    )
    assert evaluation["heldout_block"] == HELDOUT
    assert evaluation["training_blocks"] == list(TRAINING_BLOCKS)
    assert evaluation["heldout_matrix_column_range"] == {
        "start_inclusive": 4 * WIDTH,
        "stop_exclusive": 5 * WIDTH,
    }
    assert evaluation["evaluation_score_derivation_used_only_heldout_columns"] is True
    assert evaluation["fit_score_columns_used_for_evaluation"] is False
    assert evaluation["realized_outcomes_used_for_evaluation"] is False
    assert evaluation["evaluation_authority"] is False
    assert evaluation["publication_authority"] is False
    assert additions.validate_game_regime_tail_discovery_heldout_evaluation_v1(
        evaluation, **inputs, solve_results=results
    ) == evaluation


@pytest.mark.parametrize(
    "attack", ["heldout", "selected-roster", "matrix", "authority"]
)
def test_heldout_evaluation_coherent_splices_fail_outer_replay(attack: str) -> None:
    inputs, _, results = _discovery_bundle()
    retained = deepcopy(
        additions.build_game_regime_tail_discovery_heldout_evaluation_v1(
            **inputs, solve_results=results
        )
    )
    if attack == "heldout":
        retained["heldout_block"] = "R3"
    elif attack == "selected-roster":
        retained["selected_roster_sha256s"][0] = "6" * 64
        retained["selected_roster_sha256s_sha256"] = canonical_sha256(
            retained["selected_roster_sha256s"]
        )
    elif attack == "matrix":
        retained["source_lineage"]["score_matrix_sha256"] = "6" * 64
    else:
        retained["evaluation_authority"] = True
    _rehash_top(retained, "heldout_evaluation_sha256")
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="canonical replay differs",
    ):
        additions.validate_game_regime_tail_discovery_heldout_evaluation_v1(
            retained, **inputs, solve_results=results
        )


def test_heldout_evaluation_refuses_incomplete_solver_accounting() -> None:
    inputs, schedule, results = _discovery_bundle()
    result = results[2]
    solver_input = {
        "strategy_id": additions.DISCOVERY_STRATEGY_ID,
        "discovery_schedule_sha256": schedule["discovery_schedule_sha256"],
        "schedule_item_sha256": schedule["schedule"][2]["schedule_item_sha256"],
        "scheduled_world": {
            "block_id": schedule["schedule"][2]["block_id"],
            "world_index": schedule["schedule"][2]["world_index"],
        },
        "incumbent_legality_law_id": additions.LEGALITY_AUDIT_LAW_ID,
        **_lineage(_discovery_source_for_lineage(inputs)),
    }
    result.update(
        {
            "solver_status": "infeasible",
            "solver_proof_identity": _proof(
                proof_id="discovery-infeasible-2",
                proof_kind="incumbent-world-optimum-solver-result-v1",
                implementation_sha256=SOLVER_IMPLEMENTATION_SHA256,
                input_body=solver_input,
                output_body={
                    "solver_status": "infeasible",
                    "roster_player_ids": None,
                    "objective_score_milli_dk": None,
                },
            ),
            "roster_player_ids": None,
            "legality_proof_identity": None,
            "objective_score_milli_dk": None,
        }
    )
    accounting = additions.build_game_regime_tail_discovery_accounting_v1(
        **inputs, solve_results=results
    )
    assert accounting["mechanically_complete"] is False
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="requires mechanically complete",
    ):
        additions.build_game_regime_tail_discovery_heldout_evaluation_v1(
            **inputs, solve_results=results
        )


def test_exact_schemas_reject_accidental_atlas_realized_or_aggregate_fields() -> None:
    inputs = _discovery_inputs()
    players = deepcopy(inputs["player_registry"])
    players[0]["realized_actual_points"] = 99
    inputs["player_registry"] = players
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="fields differ",
    ):
        additions.build_game_regime_tail_discovery_schedule_v1(**inputs)

    inputs = _discovery_inputs()
    inputs["control_budget_identity"]["world_game_aggregates"] = []
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="fields differ",
    ):
        additions.build_game_regime_tail_discovery_schedule_v1(**inputs)


def test_small_fixture_width_is_never_confused_with_production() -> None:
    inputs = _discovery_inputs()
    inputs["require_production_width"] = True
    with pytest.raises(
        additions.CorpusExtremeTailGenerationAdditionsError,
        match="exactly 10,000 worlds",
    ):
        additions.build_game_regime_tail_discovery_schedule_v1(**inputs)
