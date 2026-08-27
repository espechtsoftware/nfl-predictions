"""Exact candidate-artifact to scored-union row-order proof.

This module is deliberately independent of any terminal matchup-source root
schema.  A successor source consumer can call it only after that source
module has exact-reopened a fixed-G0 candidate-authority root and returned the
selected accepted-candidate artifact.  The comparator proves that the exact
ordered candidate IDs and exact ordered nine-player rosters in that artifact
are the same rows represented by the reconstructed provenance and score
matrix.

It reads no cloud object, Git state, outcome, contest score, or realized data
and grants no scoring, selection, promotion, graph, or production authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


BINDING_SCHEMA: Final = (
    "corpus-r6-candidate-population-scored-union-binding/v1"
)
_FALSE_AUTHORITY_FIELDS: Final = (
    "analytical_authority",
    "decision_authority",
    "graph_authority",
    "historical_scoring_authority",
    "outcome_authority",
    "production_authority",
    "promotion_authority",
    "retrieval_authority",
    "scoring_authority",
)


class CorpusR6CandidatePopulationScoredUnionV1Error(ValueError):
    """The root-authorized candidate order differs from the scored union."""


def _fail(message: str) -> None:
    raise CorpusR6CandidatePopulationScoredUnionV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def bind_authorized_candidate_artifact_to_scored_union_v1(
    *,
    candidate_artifact: Mapping[str, object],
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Validate both inputs, then compare every candidate and roster in order."""
    try:
        artifact = source.validate_accepted_candidate_artifact_v1(
            candidate_artifact
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6CandidatePopulationScoredUnionV1Error(str(exc)) from exc
    try:
        reconstruction_sha = runner._validate_reconstruction_input(
            provenance=provenance,
            union_scores=union_scores,
            reconstruction_receipt=reconstruction_receipt,
        )
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6CandidatePopulationScoredUnionV1Error(str(exc)) from exc

    normalized_provenance = _mapping(
        provenance, label="reconstructed candidate provenance"
    )
    rows = [
        _mapping(value, label=f"authorized candidate row[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(artifact.get("rows"), label="authorized candidate rows")
        )
    ]
    candidates = [
        _mapping(value, label=f"reconstructed candidate[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(
                normalized_provenance.get("candidates"),
                label="reconstructed candidate universe",
            )
        )
    ]
    scores = np.asarray(union_scores)
    candidate_count = len(rows)
    if (
        candidate_count < 1
        or artifact.get("candidate_count") != candidate_count
        or normalized_provenance.get("candidate_count") != candidate_count
        or len(candidates) != candidate_count
        or normalized_provenance.get("lineup_order_law")
        != "ascending-stable-per-slate-lineup-id"
        or artifact.get("slate") != normalized_provenance.get("slate")
        or scores.ndim != 2
        or scores.shape[0] != candidate_count
    ):
        _fail("authorized candidate count/order differs from scored universe")

    candidate_ids: list[str] = []
    roster_projection: list[dict[str, object]] = []
    for ordinal, (authorized, reconstructed) in enumerate(
        zip(rows, candidates, strict=True)
    ):
        candidate_id = authorized.get("candidate_id")
        player_ids = authorized.get("player_ids")
        roster = reconstructed.get("roster_player_ids")
        if (
            type(candidate_id) is not str
            or candidate_id != reconstructed.get("lineup_id")
            or isinstance(player_ids, (str, bytes))
            or not isinstance(player_ids, Sequence)
            or isinstance(roster, (str, bytes))
            or not isinstance(roster, Sequence)
            or list(player_ids) != list(roster)
            or authorized.get("roster_sha256")
            != batch.canonical_sha256(list(player_ids))
        ):
            _fail(
                f"authorized candidate row[{ordinal}] differs from scored universe"
            )
        candidate_ids.append(candidate_id)
        roster_projection.append({
            "candidate_id": candidate_id,
            "player_ids": list(player_ids),
        })

    ordered_sha = batch.canonical_sha256(candidate_ids)
    matrix_binding = _mapping(
        _mapping(
            reconstruction_receipt,
            label="reconstruction receipt",
        ).get("matrix_binding"),
        label="reconstruction matrix binding",
    )
    if (
        artifact.get("ordered_candidate_ids_sha256") != ordered_sha
        or matrix_binding.get("lineup_ids_sha256") != ordered_sha
        or matrix_binding.get("shape") != list(scores.shape)
    ):
        _fail("authorized candidate order differs from score-matrix binding")

    body: dict[str, object] = {
        "schema_version": BINDING_SCHEMA,
        "source_task_ordinal": artifact["source_task_ordinal"],
        "slate": artifact["slate"],
        "candidate_artifact_sha256": artifact["candidate_artifact_sha256"],
        "candidate_provenance_sha256": normalized_provenance[
            "candidate_provenance_sha256"
        ],
        "reconstruction_sha256": reconstruction_sha,
        "candidate_count": candidate_count,
        "ordered_candidate_ids_sha256": ordered_sha,
        "ordered_candidate_rosters_sha256": batch.canonical_sha256(
            roster_projection
        ),
        "candidate_ids_exact_order_verified": True,
        "candidate_rosters_exact_order_verified": True,
        "score_matrix_row_order_verified": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["candidate_population_scored_union_binding_sha256"] = (
        batch.canonical_sha256(body)
    )
    return body


__all__ = [
    "BINDING_SCHEMA",
    "CorpusR6CandidatePopulationScoredUnionV1Error",
    "bind_authorized_candidate_artifact_to_scored_union_v1",
]
