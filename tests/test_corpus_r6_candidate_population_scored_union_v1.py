from __future__ import annotations

from hashlib import sha256

import numpy as np
import pytest

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_candidate_population_scored_union_v1 as binding
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import _score_matrix_sha256


SLATE = {"season": 2023, "week": 1, "slate_id": "2023-w01"}


def _fixture(
    *, player_prefix: str = "p",
) -> tuple[
    dict[str, object],
    dict[str, object],
    np.ndarray,
    dict[str, object],
]:
    candidates: list[dict[str, object]] = []
    for ordinal in range(2):
        roster = [f"{player_prefix}-{ordinal}-{slot}" for slot in range(9)]
        occurrence = {
            "arm_ordinal": ordinal,
            "parameter_set_id": batch.PARAMETER_SET_ORDER[ordinal],
            "visit_ordinal": 0,
            "block_id": rw.WORLD_BLOCKS[ordinal],
            "objective_world_index": ordinal,
        }
        candidates.append({
            "lineup_id": v12_import.canonical_lineup_id(SLATE, roster),
            "roster_player_ids": roster,
            "origin_blocks": [rw.WORLD_BLOCKS[ordinal]],
            "source_arms": [batch.PARAMETER_SET_ORDER[ordinal]],
            "occurrence_counts_by_block": {
                block: int(block == rw.WORLD_BLOCKS[ordinal])
                for block in rw.WORLD_BLOCKS
            },
            "source_arms_by_block": {
                block: (
                    [batch.PARAMETER_SET_ORDER[ordinal]]
                    if block == rw.WORLD_BLOCKS[ordinal]
                    else []
                )
                for block in rw.WORLD_BLOCKS
            },
            "occurrence_count": 1,
            "occurrences": [occurrence],
        })
    candidates.sort(key=lambda row: str(row["lineup_id"]))
    provenance: dict[str, object] = {
        "schema_version": v12_import.PROVENANCE_SCHEMA,
        "slate": dict(SLATE),
        "visit_schedule_sha256": sha256(b"schedule").hexdigest(),
        "visits_per_block": 1,
        "arm_count": len(batch.PARAMETER_SET_ORDER),
        "visit_occurrence_count": len(candidates),
        "candidate_count": len(candidates),
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": candidates,
        "uses_realized_outcomes": False,
    }
    provenance["candidate_provenance_sha256"] = batch.canonical_sha256(
        provenance
    )
    scores = np.ascontiguousarray(
        [[180.0, 181.0], [190.0, 191.0]], dtype=np.float64
    )
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    matrix: dict[str, object] = {
        "schema_version": v12_import.MATRIX_BINDING_SCHEMA,
        "slate": dict(SLATE),
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "lineup_ids_sha256": batch.canonical_sha256(lineup_ids),
        "world_ids_sha256": sha256(b"worlds").hexdigest(),
        "shape": list(scores.shape),
        "score_matrix_sha256": _score_matrix_sha256(scores),
        "uses_realized_outcomes": False,
    }
    matrix["matrix_binding_sha256"] = batch.canonical_sha256(matrix)
    receipt: dict[str, object] = {
        "schema_version": v12_import.RECONSTRUCTION_SCHEMA,
        "compatibility_import_sha256": sha256(b"compatibility").hexdigest(),
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "matrix_binding": matrix,
        "verified_arm_score_hashes": [
            {
                "ordinal": ordinal,
                "parameter_set_id": arm_id,
                "candidate_score_sha256": sha256(
                    f"candidate-{ordinal}".encode()
                ).hexdigest(),
                "selected_score_sha256": sha256(
                    f"selected-{ordinal}".encode()
                ).hexdigest(),
                "unique_count": runner.ENTRY_BUDGET,
                "selected_count": runner.ENTRY_BUDGET,
                "verified": True,
            }
            for ordinal, arm_id in enumerate(batch.PARAMETER_SET_ORDER)
        ],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    receipt["reconstruction_sha256"] = batch.canonical_sha256(receipt)
    artifact = source.build_accepted_candidate_artifact_v1(
        source_task_ordinal=0,
        rows=[{
            "candidate_id": row["lineup_id"],
            "player_ids": row["roster_player_ids"],
        } for row in candidates],
    )
    return artifact, provenance, scores, receipt


def test_exact_candidate_and_roster_order_binds_to_scored_matrix() -> None:
    artifact, provenance, scores, receipt = _fixture()
    result = binding.bind_authorized_candidate_artifact_to_scored_union_v1(
        candidate_artifact=artifact,
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=receipt,
    )
    assert result["schema_version"] == binding.BINDING_SCHEMA
    assert result["candidate_count"] == 2
    assert result["candidate_ids_exact_order_verified"] is True
    assert result["candidate_rosters_exact_order_verified"] is True
    assert result["score_matrix_row_order_verified"] is True
    assert result["uses_realized_outcomes"] is False


def test_coherent_alternate_authorized_artifact_order_is_rejected() -> None:
    artifact, provenance, scores, receipt = _fixture()
    reversed_artifact = source.build_accepted_candidate_artifact_v1(
        source_task_ordinal=0,
        rows=[{
            "candidate_id": row["candidate_id"],
            "player_ids": row["player_ids"],
        } for row in reversed(artifact["rows"])],
    )
    with pytest.raises(
        binding.CorpusR6CandidatePopulationScoredUnionV1Error,
        match=r"authorized candidate row\[0\] differs",
    ):
        binding.bind_authorized_candidate_artifact_to_scored_union_v1(
            candidate_artifact=reversed_artifact,
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=receipt,
        )


def test_coherent_alternate_reconstructed_union_is_rejected() -> None:
    authorized_artifact, _, _, _ = _fixture(player_prefix="authorized")
    _, alternate_provenance, alternate_scores, alternate_receipt = _fixture(
        player_prefix="alternate"
    )
    with pytest.raises(
        binding.CorpusR6CandidatePopulationScoredUnionV1Error,
        match=r"authorized candidate row\[0\] differs",
    ):
        binding.bind_authorized_candidate_artifact_to_scored_union_v1(
            candidate_artifact=authorized_artifact,
            provenance=alternate_provenance,
            union_scores=alternate_scores,
            reconstruction_receipt=alternate_receipt,
        )


def test_same_candidate_id_with_coherently_rehashed_roster_is_rejected() -> None:
    artifact, provenance, scores, receipt = _fixture()
    rows = [{
        "candidate_id": row["candidate_id"],
        "player_ids": list(row["player_ids"]),
    } for row in artifact["rows"]]
    rows[0]["player_ids"][0], rows[0]["player_ids"][1] = (
        rows[0]["player_ids"][1], rows[0]["player_ids"][0]
    )
    substituted = source.build_accepted_candidate_artifact_v1(
        source_task_ordinal=0,
        rows=rows,
    )
    with pytest.raises(
        binding.CorpusR6CandidatePopulationScoredUnionV1Error,
        match=r"authorized candidate row\[0\] differs",
    ):
        binding.bind_authorized_candidate_artifact_to_scored_union_v1(
            candidate_artifact=substituted,
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=receipt,
        )
