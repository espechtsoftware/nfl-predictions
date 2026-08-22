"""Retrieval surface over accepted parametric batch tasks (the R6 vehicle).

Reconstructs each accepted task's per-arm score matrices deterministically
from the pinned Atlas world artifacts plus retained rosters, VERIFIES the
reconstruction against every retained `candidate_score_sha256` and
`selected_score_sha256` (review F9's verified-reconstruction law), builds
the cross-arm first-occurrence union, and applies the frozen v2 retrieval
laws under two admission modes:

  * `full-union`: every union lineup is admissible (the pure retrieval
    axis);
  * `matchup-top-200`: only the 200 union lineups with the highest frozen
    matchup lineup edge are admissible (the R6 admission axis; frozen
    constant, deterministic ties by first-occurrence order).

Selection uses DISCOVERY blocks R0-R3 only; R4 world coverage is reported
as descriptive held-out evidence and never ranks anything. Realized
outcomes are never read here. Receipts are exploratory-tier with zero
adoption authority; the preregistered batch comparison spec governs any
later read.

REALITY GATE: first production use requires one accepted batch task
reconstructed and verified end-to-end; synthetic tests alone do not
license it (frozen-chain lesson 1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    _score_matrix_sha256,
    cross_score_full_union,
    first_occurrence_unique,
)
from nfl_dfs.research.corpus_retrieval_engine import (
    DISCOVERY_BLOCKS,
    WORLDS_PER_BLOCK,
    _run_strategy,
    frozen_retrieval_strategies_v2,
)
from nfl_dfs.research.lr8_later_period_source import prepare_later_slate
from nfl_dfs.research.winner_registry import canonical_sha256

RUNNER_SCHEMA: Final = "corpus-batch-retrieval-surface/v1"
ADMISSION_M: Final = 200
ADMISSION_MODES: Final = ("full-union", "matchup-top-200")
THRESHOLDS: Final = (194.0, 200.0, 210.0, 220.0)


class CorpusBatchRetrievalError(ValueError):
    pass


def _fail(message: str) -> None:
    raise CorpusBatchRetrievalError(message)


def reconstruct_and_verify(
    variant_results: Sequence[Mapping[str, object]],
    *,
    source_freeze: Mapping[str, object],
    artifact_bodies: Mapping[str, bytes],
) -> dict[str, object]:
    """Rebuild per-arm scores from pinned draws; verify retained hashes."""
    if not variant_results:
        _fail("no variant results supplied")
    slate = variant_results[0]["slate"]
    season = int(slate["season"])
    week = int(slate["week"])
    freeze_sha = str(
        variant_results[0]["later_source_freeze_manifest_sha256"]
    )
    expected_blocks = dict(variant_results[0]["artifact_sha256_by_block"])
    if set(expected_blocks) != set(artifact_bodies):
        _fail("artifact bodies differ from the retained block set")
    for block, raw in artifact_bodies.items():
        if sha256(raw).hexdigest() != expected_blocks[block]:
            _fail(f"artifact body for block {block!r} differs")
    prepared = prepare_later_slate(
        source_freeze,
        expected_source_freeze_sha256=freeze_sha,
        season=season,
        week=week,
        artifact_bodies=artifact_bodies,
    )
    arm_receipts = []
    all_rosters: list[tuple[str, ...]] = []
    incumbent_books: dict[str, list[tuple[str, ...]]] = {}
    for body in variant_results:
        if (
            body["slate"] != slate
            or body["later_source_freeze_manifest_sha256"] != freeze_sha
            or dict(body["artifact_sha256_by_block"]) != expected_blocks
        ):
            _fail("variant results disagree on slate/source identity")
        unique = tuple(
            tuple(str(player) for player in roster)
            for roster in body["unique_rosters"]
        )
        scores = cross_score_full_union(
            prepared.players, prepared.player_draws, unique
        )
        if _score_matrix_sha256(scores) != body["candidate_score_sha256"]:
            _fail(
                "reconstructed candidate scores differ for arm "
                f"{body['profile']['parameter_set_id']!r}"
            )
        selected_indices = [
            int(value) for value in body["selector"]["selected_indices"]
        ]
        selected = np.ascontiguousarray(
            scores[np.asarray(selected_indices, dtype=np.int64)],
            dtype=np.float64,
        )
        selected.flags.writeable = False
        if _score_matrix_sha256(selected) != body["selected_score_sha256"]:
            _fail(
                "reconstructed selected scores differ for arm "
                f"{body['profile']['parameter_set_id']!r}"
            )
        parameter_set_id = str(body["profile"]["parameter_set_id"])
        incumbent_books[parameter_set_id] = [
            unique[index] for index in selected_indices
        ]
        all_rosters.extend(unique)
        arm_receipts.append({
            "parameter_set_id": parameter_set_id,
            "unique_count": len(unique),
            "candidate_score_sha256": body["candidate_score_sha256"],
            "selected_score_sha256": body["selected_score_sha256"],
            "verified": True,
        })
    union, _ = first_occurrence_unique(all_rosters)
    union_scores = cross_score_full_union(
        prepared.players, prepared.player_draws, union
    )
    return {
        "season": season,
        "week": week,
        "prepared": prepared,
        "arm_receipts": arm_receipts,
        "union_rosters": union,
        "union_scores": union_scores,
        "incumbent_books": incumbent_books,
    }


def matchup_lineup_scores(
    rosters: Sequence[Sequence[str]],
    matchup_rows: Sequence[Mapping[str, object]],
) -> np.ndarray:
    """Frozen lineup matchup score: mean edge over annotated skill players.

    QB rows apply the codified starter gate (qb_depth1 false rows are
    ignored). Lineups with no annotated player score 0.0 and therefore
    never enter the matchup-admitted pool ahead of supported lineups.
    """
    edge_by_id: dict[str, float] = {}
    for row in matchup_rows:
        edge = row.get("matchup_edge_score")
        if edge is None:
            continue
        if row.get("family") == "qb" and row.get("qb_depth1") is False:
            continue
        edge_by_id[str(row["gsis_id"])] = float(edge)
    scores = np.zeros(len(rosters), dtype=np.float64)
    for index, roster in enumerate(rosters):
        values = [
            edge_by_id[player] for player in roster if player in edge_by_id
        ]
        if values:
            scores[index] = float(np.mean(values))
    return scores


def run_retrieval_surface(
    *,
    union_rosters: Sequence[tuple[str, ...]],
    union_scores: np.ndarray,
    incumbent_books: Mapping[str, Sequence[tuple[str, ...]]],
    lineup_matchup: np.ndarray,
) -> dict[str, object]:
    """Apply the frozen v2 laws under both admission modes; report coverage."""
    count = len(union_rosters)
    if union_scores.shape[0] != count or len(lineup_matchup) != count:
        _fail("union surface inputs are misaligned")
    discovery_stop = len(DISCOVERY_BLOCKS) * WORLDS_PER_BLOCK
    if union_scores.shape[1] <= discovery_stop:
        _fail("union scores lack a held-out block")
    lineup_ids = [
        f"lineup:{sha256(','.join(roster).encode()).hexdigest()}"
        for roster in union_rosters
    ]
    index_by_roster = {
        roster: index for index, roster in enumerate(union_rosters)
    }

    def coverage(indices: Sequence[int]) -> dict[str, object]:
        block = union_scores[np.asarray(indices, dtype=np.int64)]
        discovery = block[:, :discovery_stop]
        heldout = block[:, discovery_stop:]
        best_discovery = discovery.max(axis=0)
        best_heldout = heldout.max(axis=0)
        result: dict[str, object] = {
            "discovery_expected_max": round(
                float(best_discovery.astype(np.float64).mean()), 4
            ),
            "heldout_expected_max_descriptive": round(
                float(best_heldout.astype(np.float64).mean()), 4
            ),
        }
        for threshold in THRESHOLDS:
            result[f"discovery_worlds_ge_{int(threshold)}"] = int(
                (best_discovery >= threshold).sum()
            )
            result[f"heldout_worlds_ge_{int(threshold)}_descriptive"] = int(
                (best_heldout >= threshold).sum()
            )
        return result

    books: dict[str, object] = {}
    for name, rosters in incumbent_books.items():
        indices = [index_by_roster[tuple(roster)] for roster in rosters]
        books[f"incumbent:{name}"] = {
            "book_size": len(indices),
            "admission": "fixed-line194-arm-book",
            **coverage(indices),
        }

    admitted_order = np.lexsort((
        np.arange(count), -lineup_matchup,
    ))
    admitted = np.zeros(count, dtype=bool)
    admitted[admitted_order[: min(ADMISSION_M, count)]] = True
    for mode in ADMISSION_MODES:
        mask = (
            np.ones(count, dtype=bool) if mode == "full-union" else admitted
        )
        pool_indices = np.flatnonzero(mask)
        pool_scores = union_scores[pool_indices, :discovery_stop]
        pool_ids = [lineup_ids[index] for index in pool_indices]
        if len(pool_indices) < 80:
            continue
        for strategy in frozen_retrieval_strategies_v2(80)[4:]:
            local_selected, _ = _run_strategy(
                strategy,
                discovery_scores=pool_scores,
                lineup_ids=pool_ids,
            )
            indices = [int(pool_indices[value]) for value in local_selected]
            books[f"{mode}:{strategy['strategy_id']}"] = {
                "book_size": len(indices),
                "admission": mode,
                "strategy_sha256": strategy["strategy_sha256"],
                **coverage(indices),
            }
    body = {
        "schema_version": RUNNER_SCHEMA,
        "union_count": count,
        "admission_m": ADMISSION_M,
        "matchup_admitted_count": int(admitted.sum()),
        "books": books,
        "heldout_semantics": (
            "R4 coverage is descriptive only and never ranked or selected"
        ),
        "uses_realized_outcomes": False,
        "evidence_tier": "exploratory-pre-comparison",
        "adoption_authority": False,
    }
    body["retrieval_surface_sha256"] = canonical_sha256(body)
    return body


__all__ = [
    "ADMISSION_M",
    "ADMISSION_MODES",
    "CorpusBatchRetrievalError",
    "RUNNER_SCHEMA",
    "matchup_lineup_scores",
    "reconstruct_and_verify",
    "run_retrieval_surface",
]
