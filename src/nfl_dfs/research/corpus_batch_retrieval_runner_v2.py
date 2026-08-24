"""Fold-safe, all-seven retrieval surface for accepted Foundry v12 corpora.

This is the additive successor to the frozen legacy R6 runner.  It consumes a
canonical, outcome-blind v12 reconstruction, rotates every R block through a
held-out fold, strips held-out candidate provenance before admission or ties,
runs the one registered seven-law selector catalog, and creates a distinct
all-block final fit before any realized score read.

The scientific bodies are pure and deterministic.  Runtime, memory, cloud
execution, publication, and terminal-panel authority belong in separate
execution/acceptance receipts; no function here imports an outcome source.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from hashlib import sha256
import json
import math
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_parametric_snapshot as parametric_snapshot
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    VISITS_PER_BLOCK,
    _score_matrix_sha256,
    canonical_json_bytes,
    canonical_sha256,
)
from nfl_dfs.research.corpus_parametric_batch import PARAMETER_SET_ORDER
from nfl_dfs.research.corpus_v12_import import (
    MATRIX_BINDING_SCHEMA,
    PROVENANCE_SCHEMA,
    RECONSTRUCTION_SCHEMA,
    canonical_lineup_id,
)


RUNNER_SCHEMA: Final = "corpus-batch-retrieval-surface/v2"
SCOPE_SCHEMA: Final = "corpus-batch-retrieval-fit-scope/v2"
ADMISSION_SCHEMA: Final = "corpus-batch-retrieval-admission/v2"
BOOK_SCHEMA: Final = "corpus-batch-retrieval-book/v2"
MATCHUP_SUMMARY_SCHEMA: Final = "corpus-matchup-lineup-summary/v2"
MATCHUP_SOURCE_SCHEMA: Final = "corpus-r6-matchup-source-snapshot/v1"
NEUTRAL_LAW_ID: Final = "score-blind-size-composition-matched-v1"
FULL_UNION_ADMISSION_ID: Final = "fold-eligible-union-v1"
MATCHUP_ADMISSION_ID: Final = "matchup-top-200-supported-v2"
DEFAULT_ADMISSION_M: Final = 200
DEFAULT_NEUTRAL_REPLICATES: Final = 32
ENTRY_BUDGET: Final = 80
PRIMARY_STRATEGY_ID: Final = "coverage-194-v1"
AUTHORITATIVE_DOSE: Final = "authoritative-production-dose"
FIXTURE_DOSE: Final = "non-authoritative-fixture-dose"
FIXTURE_ID_PREFIX: Final = "fixture-only-"
CORRELATION_PAIR_SAMPLE_CAP: Final = 32
THRESHOLDS: Final = (
    ("ge_194", 194.0, ">="),
    ("gt_200", 200.0, ">"),
    ("gt_210", 210.0, ">"),
    ("gt_220", 220.0, ">"),
)
ELIGIBLE_MATCHUP_FAMILIES: Final = ("qb", "rb", "receiver")


class CorpusBatchRetrievalV2Error(ValueError):
    """The R6-v2 surface cannot be produced without violating its law."""


def _fail(message: str) -> None:
    raise CorpusBatchRetrievalV2Error(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = canonical_sha256(result)
    return result


def _is_lower_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_self_hash(body: Mapping[str, object], field: str, *, label: str) -> None:
    retained = body.get(field)
    if not _is_lower_sha256(retained):
        _fail(f"{label} lacks a canonical self-hash")
    remainder = {key: value for key, value in body.items() if key != field}
    if canonical_sha256(remainder) != retained:
        _fail(f"{label} self-hash differs")


def _operator_mask(scores: np.ndarray, threshold: float, operator: str) -> np.ndarray:
    if operator == ">=":
        return scores >= threshold
    if operator == ">":
        return scores > threshold
    _fail(f"unsupported threshold operator {operator!r}")


def _block_columns(
    blocks: Sequence[str], *, worlds_per_block: int
) -> np.ndarray:
    if type(worlds_per_block) is not int or worlds_per_block <= 0:
        _fail("worlds_per_block must be a positive exact integer")
    values: list[int] = []
    for block in blocks:
        if block not in rw.WORLD_BLOCKS:
            _fail(f"unknown world block {block!r}")
        ordinal = rw.WORLD_BLOCKS.index(block)
        values.extend(range(
            ordinal * worlds_per_block, (ordinal + 1) * worlds_per_block
        ))
    return np.asarray(values, dtype=np.int64)


def _dose_authority(
    *,
    provenance: Mapping[str, object],
    admission_m: int,
    worlds_per_block: int,
    require_authoritative: bool,
) -> str:
    """Fail closed unless a production run uses every registered dose."""
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    if type(admission_m) is not int or admission_m < ENTRY_BUDGET:
        _fail("admission_m must be an exact integer at least 80")
    if type(worlds_per_block) is not int or worlds_per_block < 1:
        _fail("worlds_per_block must be a positive exact integer")
    if require_authoritative:
        if (
            admission_m != DEFAULT_ADMISSION_M
            or worlds_per_block != rw.WORLDS_PER_BLOCK
            or retrieval.WORLDS_PER_BLOCK != rw.WORLDS_PER_BLOCK
            or provenance.get("visits_per_block") != VISITS_PER_BLOCK
        ):
            _fail(
                "authoritative R6-v2 requires top-200 admission, canonical "
                "10k-world blocks, and the authoritative v12 visit dose"
            )
        return AUTHORITATIVE_DOSE
    return FIXTURE_DOSE


def _validate_strategy_registry() -> list[dict[str, object]]:
    """Resolve the one canonical catalog and reject order/identity drift."""
    raw_strategies = retrieval.frozen_retrieval_strategies_v2(ENTRY_BUDGET)
    if len(raw_strategies) != 7:
        _fail("seven-law retrieval registry differs")
    strategies: list[dict[str, object]] = []
    for ordinal, raw_strategy in enumerate(raw_strategies):
        strategy = dict(_mapping(raw_strategy, label=f"strategy[{ordinal}]"))
        if strategy.get("ordinal") != ordinal:
            _fail("seven-law retrieval registry order/ordinal differs")
        try:
            validated = retrieval.validate_retrieval_strategy_v2(
                strategy,
                expected_ordinal=ordinal,
                entry_budget=ENTRY_BUDGET,
            )
        except retrieval.CorpusRetrievalError as exc:
            raise CorpusBatchRetrievalV2Error(
                f"seven-law retrieval registry differs: {exc}"
            ) from exc
        _validate_self_hash(
            validated,
            "strategy_sha256",
            label=f"strategy[{ordinal}]",
        )
        strategies.append(dict(validated))
    strategy_ids = [str(strategy["strategy_id"]) for strategy in strategies]
    strategy_hashes = [str(strategy["strategy_sha256"]) for strategy in strategies]
    if (
        len(set(strategy_ids)) != len(strategies)
        or len(set(strategy_hashes)) != len(strategies)
        or strategy_ids.count(PRIMARY_STRATEGY_ID) != 1
    ):
        _fail("seven-law retrieval registry identities are not unique/canonical")
    return strategies


def _validate_provenance(value: Mapping[str, object]) -> list[dict[str, object]]:
    body = _mapping(value, label="candidate provenance")
    if set(body) != {
        "schema_version",
        "slate",
        "visit_schedule_sha256",
        "visits_per_block",
        "arm_count",
        "visit_occurrence_count",
        "candidate_count",
        "lineup_order_law",
        "candidates",
        "uses_realized_outcomes",
        "candidate_provenance_sha256",
    }:
        _fail("candidate provenance fields differ")
    if (
        body.get("schema_version") != PROVENANCE_SCHEMA
        or not _is_lower_sha256(body.get("visit_schedule_sha256"))
        or type(body.get("visits_per_block")) is not int
        or int(body["visits_per_block"]) < 1
        or body.get("arm_count") != len(PARAMETER_SET_ORDER)
        or type(body.get("arm_count")) is not int
        or type(body.get("visit_occurrence_count")) is not int
        or int(body["visit_occurrence_count"]) < 1
        or type(body.get("candidate_count")) is not int
        or int(body["candidate_count"]) < 1
        or body.get("lineup_order_law")
        != "ascending-stable-per-slate-lineup-id"
    ):
        _fail("candidate provenance schema differs")
    _validate_self_hash(
        body, "candidate_provenance_sha256", label="candidate provenance"
    )
    if body.get("uses_realized_outcomes") is not False:
        _fail("candidate provenance is not outcome-blind")
    slate = _mapping(body.get("slate"), label="candidate provenance slate")
    raw_candidates = _sequence(body.get("candidates"), label="provenance candidates")
    candidates: list[dict[str, object]] = []
    prior_id = ""
    occurrence_keys: set[tuple[int, int]] = set()
    occurrence_total = 0
    for offset, raw_candidate in enumerate(raw_candidates):
        row = dict(_mapping(raw_candidate, label=f"provenance candidate[{offset}]"))
        if set(row) != {
            "lineup_id",
            "roster_player_ids",
            "origin_blocks",
            "source_arms",
            "occurrence_counts_by_block",
            "source_arms_by_block",
            "occurrence_count",
            "occurrences",
        }:
            _fail(f"provenance candidate[{offset}] fields differ")
        lineup_id = row.get("lineup_id")
        roster = _sequence(
            row.get("roster_player_ids"), label=f"candidate[{offset}] roster"
        )
        if (
            type(lineup_id) is not str
            or lineup_id <= prior_id
            or len(roster) != rw.ROSTER_SIZE
            or any(type(player_id) is not str for player_id in roster)
            or lineup_id != canonical_lineup_id(slate, roster)
        ):
            _fail("provenance lineup order/identity differs")
        prior_id = lineup_id
        occurrences = _sequence(
            row.get("occurrences"), label=f"candidate[{offset}] occurrences"
        )
        if not occurrences:
            _fail("provenance candidate has no occurrence")
        normalized_occurrences: list[dict[str, object]] = []
        for raw_occurrence in occurrences:
            occurrence = _mapping(raw_occurrence, label="candidate occurrence")
            if set(occurrence) != {
                "arm_ordinal",
                "parameter_set_id",
                "visit_ordinal",
                "block_id",
                "objective_world_index",
            }:
                _fail("candidate occurrence fields differ")
            arm_ordinal = occurrence["arm_ordinal"]
            visit_ordinal = occurrence["visit_ordinal"]
            world_index = occurrence["objective_world_index"]
            if (
                type(arm_ordinal) is not int
                or not 0 <= arm_ordinal < len(PARAMETER_SET_ORDER)
                or occurrence["parameter_set_id"]
                != PARAMETER_SET_ORDER[arm_ordinal]
                or type(visit_ordinal) is not int
                or visit_ordinal < 0
                or occurrence.get("block_id") not in rw.WORLD_BLOCKS
                or type(world_index) is not int
                or not 0 <= world_index < rw.WORLDS_PER_BLOCK
            ):
                _fail("candidate occurrence values differ")
            occurrence_key = (arm_ordinal, visit_ordinal)
            if occurrence_key in occurrence_keys:
                _fail("candidate provenance repeats an arm/visit occurrence")
            occurrence_keys.add(occurrence_key)
            normalized_occurrences.append(dict(occurrence))
        occurrence_total += len(normalized_occurrences)
        block_counts = Counter(
            str(occurrence["block_id"])
            for occurrence in normalized_occurrences
        )
        source_arms = sorted({
            str(occurrence["parameter_set_id"])
            for occurrence in normalized_occurrences
        })
        source_arms_by_block = {
            block: sorted({
                str(occurrence["parameter_set_id"])
                for occurrence in normalized_occurrences
                if occurrence["block_id"] == block
            })
            for block in rw.WORLD_BLOCKS
        }
        if (
            row.get("origin_blocks")
            != [block for block in rw.WORLD_BLOCKS if block_counts[block]]
            or row.get("source_arms") != source_arms
            or row.get("occurrence_counts_by_block")
            != {block: int(block_counts[block]) for block in rw.WORLD_BLOCKS}
            or row.get("source_arms_by_block") != source_arms_by_block
            or type(row.get("occurrence_count")) is not int
            or row.get("occurrence_count") != len(normalized_occurrences)
        ):
            _fail("candidate provenance summary differs from occurrences")
        candidates.append(row)
    if (
        len(candidates) != body.get("candidate_count")
        or body.get("arm_count") != len(PARAMETER_SET_ORDER)
        or body.get("visit_occurrence_count") != occurrence_total
    ):
        _fail("candidate provenance count differs")
    return candidates


def _validate_reconstruction_input(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
) -> str:
    receipt = _mapping(reconstruction_receipt, label="v12 reconstruction receipt")
    if set(receipt) != {
        "schema_version",
        "compatibility_import_sha256",
        "candidate_provenance_sha256",
        "matrix_binding",
        "verified_arm_score_hashes",
        "uses_realized_outcomes",
        "promotion_authority",
        "reconstruction_sha256",
    }:
        _fail("v12 reconstruction receipt fields differ")
    if (
        receipt.get("schema_version") != RECONSTRUCTION_SCHEMA
        or receipt.get("uses_realized_outcomes") is not False
        or receipt.get("promotion_authority") is not False
    ):
        _fail("v12 reconstruction receipt policy differs")
    _validate_self_hash(receipt, "reconstruction_sha256", label="reconstruction")
    candidates = _validate_provenance(provenance)
    if receipt.get("candidate_provenance_sha256") != provenance.get(
        "candidate_provenance_sha256"
    ):
        _fail("reconstruction receipt differs from candidate provenance")
    matrix = _mapping(receipt.get("matrix_binding"), label="matrix binding")
    if set(matrix) != {
        "schema_version",
        "slate",
        "candidate_provenance_sha256",
        "lineup_ids_sha256",
        "world_ids_sha256",
        "shape",
        "score_matrix_sha256",
        "uses_realized_outcomes",
        "matrix_binding_sha256",
    }:
        _fail("matrix binding fields differ")
    if (
        matrix.get("schema_version") != MATRIX_BINDING_SCHEMA
        or matrix.get("uses_realized_outcomes") is not False
        or matrix.get("slate") != provenance.get("slate")
        or matrix.get("candidate_provenance_sha256")
        != provenance.get("candidate_provenance_sha256")
    ):
        _fail("matrix binding policy/provenance differs")
    _validate_self_hash(matrix, "matrix_binding_sha256", label="matrix binding")
    scores = np.asarray(union_scores)
    lineup_ids = [str(row["lineup_id"]) for row in candidates]
    shape = matrix.get("shape")
    if (
        not isinstance(shape, list)
        or any(type(value) is not int or value < 1 for value in shape)
        or shape != list(scores.shape)
        or matrix.get("lineup_ids_sha256") != canonical_sha256(lineup_ids)
        or not _is_lower_sha256(matrix.get("world_ids_sha256"))
        or matrix.get("score_matrix_sha256") != _score_matrix_sha256(scores)
    ):
        _fail("matrix binding differs from the supplied canonical scores")
    compatibility_sha = receipt.get("compatibility_import_sha256")
    raw_arms = _sequence(
        receipt.get("verified_arm_score_hashes"),
        label="verified arm score hashes",
    )
    if not _is_lower_sha256(compatibility_sha) or len(raw_arms) != len(
        PARAMETER_SET_ORDER
    ):
        _fail("reconstruction compatibility/arm evidence differs")
    for ordinal, raw_arm in enumerate(raw_arms):
        arm = _mapping(raw_arm, label=f"verified arm score hash[{ordinal}]")
        if set(arm) != {
            "ordinal",
            "parameter_set_id",
            "candidate_score_sha256",
            "selected_score_sha256",
            "unique_count",
            "selected_count",
            "verified",
        }:
            _fail(f"verified arm score hash[{ordinal}] fields differ")
        if (
            arm["ordinal"] != ordinal
            or type(arm["ordinal"]) is not int
            or arm["parameter_set_id"] != PARAMETER_SET_ORDER[ordinal]
            or not _is_lower_sha256(arm["candidate_score_sha256"])
            or not _is_lower_sha256(arm["selected_score_sha256"])
            or type(arm["unique_count"]) is not int
            or arm["unique_count"] < ENTRY_BUDGET
            or type(arm["selected_count"]) is not int
            or arm["selected_count"] != ENTRY_BUDGET
            or arm["verified"] is not True
        ):
            _fail(f"verified arm score hash[{ordinal}] values differ")
    return str(receipt["reconstruction_sha256"])


def build_fit_candidate_view(
    provenance: Mapping[str, object],
    *,
    heldout_block: str | None,
    dose_authority: str = AUTHORITATIVE_DOSE,
) -> dict[str, object]:
    """Strip held-out occurrences before deriving any selection provenance."""
    candidates = _validate_provenance(provenance)
    if dose_authority not in {AUTHORITATIVE_DOSE, FIXTURE_DOSE}:
        _fail("candidate-view dose authority differs")
    if heldout_block is not None and heldout_block not in rw.WORLD_BLOCKS:
        _fail("heldout block differs")
    training_blocks = [
        block for block in rw.WORLD_BLOCKS if block != heldout_block
    ]
    eligible: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    for row in candidates:
        occurrences = [
            dict(value)
            for value in row["occurrences"]
            if value["block_id"] in training_blocks
        ]
        heldout_present = bool(
            heldout_block is not None
            and any(value["block_id"] == heldout_block for value in row["occurrences"])
        )
        if not occurrences:
            excluded.append({
                "lineup_id": row["lineup_id"],
                "reason_code": "heldout-only-origin",
                "heldout_origin_present": heldout_present,
            })
            continue
        block_counts = Counter(str(value["block_id"]) for value in occurrences)
        arms_by_block = {
            block: sorted({
                str(value["parameter_set_id"])
                for value in occurrences
                if value["block_id"] == block
            })
            for block in training_blocks
        }
        selection_projection = {
            "lineup_id": row["lineup_id"],
            "roster_player_ids": list(row["roster_player_ids"]),
            "training_origin_blocks": [
                block for block in training_blocks if block_counts[block]
            ],
            "training_source_arms": sorted({
                str(value["parameter_set_id"]) for value in occurrences
            }),
            "training_occurrence_counts_by_block": {
                block: int(block_counts[block]) for block in training_blocks
            },
            "training_source_arms_by_block": arms_by_block,
            "training_occurrence_count": len(occurrences),
        }
        eligible.append(selection_projection)
    body: dict[str, object] = {
        "schema_version": "corpus-fold-candidate-view/v2",
        "slate": provenance["slate"],
        "fit_scope_id": (
            "all-block-final-fit" if heldout_block is None else f"holdout-{heldout_block}"
        ),
        "training_blocks": training_blocks,
        "heldout_block": heldout_block,
        "eligible_candidates": eligible,
        "excluded_candidates_audit": excluded,
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "dose_authority": dose_authority,
        "selection_inputs_exclude_heldout_occurrences": True,
        "uses_realized_outcomes": False,
    }
    body["fit_candidate_view_sha256"] = canonical_sha256(body)
    selection_only = {
        "schema_version": "corpus-fold-selection-provenance/v2",
        "slate": body["slate"],
        "fit_scope_id": body["fit_scope_id"],
        "training_blocks": training_blocks,
        "eligible_candidates": eligible,
        "dose_authority": dose_authority,
        "uses_realized_outcomes": False,
    }
    body["selection_provenance_sha256"] = canonical_sha256(selection_only)
    body["fit_candidate_view_sha256"] = canonical_sha256({
        key: value
        for key, value in body.items()
        if key != "fit_candidate_view_sha256"
    })
    return body


def _utc_timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    if type(value) is not str or not value.endswith("Z"):
        _fail(f"{label} must be a UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CorpusBatchRetrievalV2Error(
            f"{label} is not a valid timestamp"
        ) from exc
    if parsed.tzinfo is None:
        _fail(f"{label} lacks a timezone")
    return value, parsed


def build_matchup_source_snapshot(
    *,
    slate: Mapping[str, object],
    lock_time_utc: str,
    maximum_source_time_utc: str,
    eligible_players: Sequence[Mapping[str, object]],
    annotation_rows: Sequence[Mapping[str, object]],
    player_catalog_identity: Mapping[str, object],
    annotation_query_receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    """Freeze the complete skill-player denominator and 017r projection.

    The source export is score/outcome-free.  Missing annotation rows are
    materialized as ``matchup_edge_score=None`` against the complete pre-lock
    eligible-player catalog, so completeness can never be inflated by source
    absence.
    """
    normalized_slate = dict(_mapping(slate, label="matchup source slate"))
    lock, lock_instant = _utc_timestamp(lock_time_utc, label="matchup lock time")
    maximum, maximum_instant = _utc_timestamp(
        maximum_source_time_utc, label="matchup maximum source time"
    )
    if maximum_instant > lock_instant:
        _fail("matchup source is not point-in-time at slate lock")
    catalog_identity = parametric_snapshot.normalize_object_identity(
        player_catalog_identity, label="matchup player catalog"
    )
    query_identity = parametric_snapshot.normalize_object_identity(
        annotation_query_receipt_identity,
        label="matchup annotation query receipt",
    )
    players: list[dict[str, object]] = []
    player_by_id: dict[str, dict[str, object]] = {}
    for offset, raw_player in enumerate(eligible_players):
        player = _mapping(raw_player, label=f"eligible player[{offset}]")
        if set(player) != {"gsis_id", "family", "position", "qb_depth1"}:
            _fail(f"eligible player[{offset}] fields differ")
        player_id = player["gsis_id"]
        family = player["family"]
        position = player["position"]
        depth = player["qb_depth1"]
        if (
            type(player_id) is not str
            or not player_id
            or player_id in player_by_id
            or family not in ELIGIBLE_MATCHUP_FAMILIES
            or position not in {"QB", "RB", "WR", "TE"}
            or (family == "qb") != (position == "QB")
            or (family == "rb") != (position == "RB")
            or (family == "receiver") != (position in {"WR", "TE"})
            or (
                family == "qb"
                and depth is not None
                and type(depth) is not bool
            )
            or (family != "qb" and depth is not None)
        ):
            _fail(f"eligible player[{offset}] values differ")
        normalized = {
            "gsis_id": player_id,
            "family": family,
            "position": position,
            "qb_depth1": depth,
        }
        player_by_id[player_id] = normalized
        players.append(normalized)
    players.sort(key=lambda row: str(row["gsis_id"]))
    if not players:
        _fail("matchup source has no eligible skill players")

    edge_by_id: dict[str, float | None] = {}
    for offset, raw_row in enumerate(annotation_rows):
        row = _mapping(raw_row, label=f"matchup annotation row[{offset}]")
        if set(row) != {"gsis_id", "family", "matchup_edge_score"}:
            _fail(f"matchup annotation row[{offset}] fields differ")
        player_id = row["gsis_id"]
        family = row["family"]
        edge = row["matchup_edge_score"]
        if (
            type(player_id) is not str
            or player_id not in player_by_id
            or player_id in edge_by_id
            or family != player_by_id[player_id]["family"]
            or (
                edge is not None
                and (
                    isinstance(edge, bool)
                    or not isinstance(edge, (int, float))
                    or not math.isfinite(float(edge))
                )
            )
        ):
            _fail(f"matchup annotation row[{offset}] values differ")
        edge_by_id[player_id] = None if edge is None else float(edge)
    rows = [{
        **player,
        "matchup_edge_score": edge_by_id.get(str(player["gsis_id"])),
        "annotation_row_present": str(player["gsis_id"]) in edge_by_id,
    } for player in players]
    body = {
        "schema_version": MATCHUP_SOURCE_SCHEMA,
        "slate": normalized_slate,
        "source_relation": "player_matchup_week_pit-017r",
        "source_projection": [
            "gsis_id",
            "family",
            "matchup_edge_score",
            "qb_depth1",
        ],
        "lock_time_utc": lock,
        "maximum_source_time_utc": maximum,
        "point_in_time_at_lock": True,
        "player_catalog_identity": catalog_identity,
        "annotation_query_receipt_identity": query_identity,
        "eligible_player_count": len(players),
        "eligible_players_sha256": canonical_sha256(players),
        "rows": rows,
        "rows_sha256": canonical_sha256(rows),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, "matchup_source_snapshot_sha256")


def validate_matchup_source_snapshot(value: Mapping[str, object]) -> dict[str, object]:
    body = _mapping(value, label="matchup source snapshot")
    if set(body) != {
        "schema_version",
        "slate",
        "source_relation",
        "source_projection",
        "lock_time_utc",
        "maximum_source_time_utc",
        "point_in_time_at_lock",
        "player_catalog_identity",
        "annotation_query_receipt_identity",
        "eligible_player_count",
        "eligible_players_sha256",
        "rows",
        "rows_sha256",
        "outcome_columns_read",
        "uses_realized_outcomes",
        "matchup_source_snapshot_sha256",
    }:
        _fail("matchup source snapshot fields differ")
    if (
        body.get("schema_version") != MATCHUP_SOURCE_SCHEMA
        or body.get("source_relation") != "player_matchup_week_pit-017r"
        or body.get("source_projection") != [
            "gsis_id",
            "family",
            "matchup_edge_score",
            "qb_depth1",
        ]
        or body.get("point_in_time_at_lock") is not True
        or body.get("outcome_columns_read") != []
        or body.get("uses_realized_outcomes") is not False
    ):
        _fail("matchup source snapshot policy differs")
    _validate_self_hash(
        body,
        "matchup_source_snapshot_sha256",
        label="matchup source snapshot",
    )
    raw_rows = _sequence(body.get("rows"), label="matchup source rows")
    rows: list[Mapping[str, object]] = []
    for offset, raw_row in enumerate(raw_rows):
        row = _mapping(raw_row, label=f"matchup source row[{offset}]")
        if set(row) != {
            "gsis_id",
            "family",
            "position",
            "qb_depth1",
            "matchup_edge_score",
            "annotation_row_present",
        } or type(row["annotation_row_present"]) is not bool:
            _fail(f"matchup source row[{offset}] fields differ")
        rows.append(row)
    eligible = [{
        key: row[key] for key in ("gsis_id", "family", "position", "qb_depth1")
    } for row in rows]
    annotations = [{
        key: row[key] for key in ("gsis_id", "family", "matchup_edge_score")
    } for row in rows if row["annotation_row_present"] is True]
    rebuilt = build_matchup_source_snapshot(
        slate=_mapping(body["slate"], label="matchup source slate"),
        lock_time_utc=str(body["lock_time_utc"]),
        maximum_source_time_utc=str(body["maximum_source_time_utc"]),
        eligible_players=eligible,
        annotation_rows=annotations,
        player_catalog_identity=_mapping(
            body["player_catalog_identity"], label="matchup player catalog"
        ),
        annotation_query_receipt_identity=_mapping(
            body["annotation_query_receipt_identity"],
            label="matchup query receipt",
        ),
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(body):
        _fail("matchup source snapshot canonical replay differs")
    return rebuilt


def build_matchup_lineup_summaries(
    *,
    provenance: Mapping[str, object],
    matchup_source: Mapping[str, object],
    minimum_supported_players: int = 2,
    minimum_completeness: float = 0.5,
) -> dict[str, object]:
    """Create null-preserving matchup summaries with an explicit QB gate."""
    candidates = _validate_provenance(provenance)
    source = validate_matchup_source_snapshot(matchup_source)
    if source["slate"] != provenance["slate"]:
        _fail("matchup source slate differs from candidate provenance")
    if type(minimum_supported_players) is not int or minimum_supported_players < 1:
        _fail("minimum_supported_players must be positive")
    if (
        isinstance(minimum_completeness, bool)
        or not isinstance(minimum_completeness, (int, float))
        or not 0.0 <= float(minimum_completeness) <= 1.0
    ):
        _fail("minimum_completeness must be within [0,1]")
    by_player = {
        str(row["gsis_id"]): dict(row)
        for row in source["rows"]
        if not (row["family"] == "qb" and row["qb_depth1"] is False)
    }
    catalog_by_player = {
        str(row["gsis_id"]): dict(row) for row in source["rows"]
    }

    summaries: list[dict[str, object]] = []
    for candidate in candidates:
        catalog_members = [
            catalog_by_player[player]
            for player in candidate["roster_player_ids"]
            if player in catalog_by_player
        ]
        if (
            len(catalog_members) != rw.ROSTER_SIZE - 1
            or sum(row["family"] == "qb" for row in catalog_members) != 1
        ):
            _fail(
                "matchup player catalog does not cover exactly eight skill "
                "players including one QB for every lineup"
            )
        annotations = [
            by_player[player]
            for player in candidate["roster_player_ids"]
            if player in by_player
        ]
        supported = [
            row for row in annotations if row["matchup_edge_score"] is not None
        ]
        eligible_count = len(annotations)
        supported_count = len(supported)
        completeness = (
            supported_count / eligible_count if eligible_count else 0.0
        )
        edge = (
            float(np.mean([
                float(row["matchup_edge_score"]) for row in supported
            ], dtype=np.float64))
            if supported
            else None
        )
        qualifies = (
            supported_count >= minimum_supported_players
            and completeness >= float(minimum_completeness)
        )
        summaries.append({
            "lineup_id": candidate["lineup_id"],
            "matchup_edge_mean": edge,
            "eligible_player_count": eligible_count,
            "supported_player_count": supported_count,
            "supported_families": sorted({
                str(row["family"]) for row in supported
            }),
            "annotation_completeness": completeness,
            "qualifies_for_matchup_admission": qualifies,
            "missing_semantics": "missing-not-zero",
        })
    body: dict[str, object] = {
        "schema_version": MATCHUP_SUMMARY_SCHEMA,
        "slate": provenance["slate"],
        "matchup_source_snapshot_sha256": source[
            "matchup_source_snapshot_sha256"
        ],
        "player_catalog_identity": source["player_catalog_identity"],
        "annotation_query_receipt_identity": source[
            "annotation_query_receipt_identity"
        ],
        "eligible_families": list(ELIGIBLE_MATCHUP_FAMILIES),
        "qb_gate": "exclude-only-when-qb_depth1-is-literal-false",
        "minimum_supported_players": minimum_supported_players,
        "minimum_completeness": float(minimum_completeness),
        "lineups": summaries,
        "uses_realized_outcomes": False,
    }
    body["matchup_summary_sha256"] = canonical_sha256(body)
    return body


def validate_matchup_lineup_summaries(
    value: Mapping[str, object],
    *,
    provenance: Mapping[str, object],
    matchup_source: Mapping[str, object],
) -> dict[str, object]:
    """Replay a lineup summary from its exact PIT source and candidate union."""
    body = _mapping(value, label="matchup summary")
    if set(body) != {
        "schema_version",
        "slate",
        "matchup_source_snapshot_sha256",
        "player_catalog_identity",
        "annotation_query_receipt_identity",
        "eligible_families",
        "qb_gate",
        "minimum_supported_players",
        "minimum_completeness",
        "lineups",
        "uses_realized_outcomes",
        "matchup_summary_sha256",
    }:
        _fail("matchup summary fields differ")
    if (
        body.get("schema_version") != MATCHUP_SUMMARY_SCHEMA
        or body.get("uses_realized_outcomes") is not False
    ):
        _fail("matchup summary contract differs")
    _validate_self_hash(body, "matchup_summary_sha256", label="matchup summary")
    source = validate_matchup_source_snapshot(matchup_source)
    if body.get("matchup_source_snapshot_sha256") != source.get(
        "matchup_source_snapshot_sha256"
    ):
        _fail("matchup summary source binding differs")
    rebuilt = build_matchup_lineup_summaries(
        provenance=provenance,
        matchup_source=source,
        minimum_supported_players=body["minimum_supported_players"],
        minimum_completeness=body["minimum_completeness"],
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(body):
        _fail("matchup summary canonical replay differs")
    return rebuilt


def _summary_by_id(matchup_summary: Mapping[str, object]) -> dict[str, dict[str, object]]:
    body = _mapping(matchup_summary, label="matchup summary")
    if (
        body.get("schema_version") != MATCHUP_SUMMARY_SCHEMA
        or body.get("uses_realized_outcomes") is not False
    ):
        _fail("matchup summary contract differs")
    _validate_self_hash(body, "matchup_summary_sha256", label="matchup summary")
    result: dict[str, dict[str, object]] = {}
    for raw_row in _sequence(body.get("lineups"), label="matchup summary lineups"):
        row = dict(_mapping(raw_row, label="matchup lineup summary"))
        lineup_id = row.get("lineup_id")
        if type(lineup_id) is not str or lineup_id in result:
            _fail("matchup summary lineup identity differs")
        result[lineup_id] = row
    return result


def _full_union_admission(candidate_view: Mapping[str, object]) -> dict[str, object]:
    admitted = [
        str(row["lineup_id"]) for row in candidate_view["eligible_candidates"]
    ]
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": (
            FULL_UNION_ADMISSION_ID
            if candidate_view["dose_authority"] == AUTHORITATIVE_DOSE
            else f"{FIXTURE_ID_PREFIX}{FULL_UNION_ADMISSION_ID}"
        ),
        "fit_scope_id": candidate_view["fit_scope_id"],
        "selection_provenance_sha256": candidate_view[
            "selection_provenance_sha256"
        ],
        "admitted_lineup_ids": admitted,
        "admitted_count": len(admitted),
        "excluded_eligible_candidates": [],
        "dose_authority": candidate_view["dose_authority"],
        "admission_inputs": "fold-local-provenance-and-stable-lineup-id-only",
        "uses_simulated_scores": False,
        "uses_matchup_values": False,
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, "admission_sha256")


def _matchup_admission(
    candidate_view: Mapping[str, object],
    *,
    matchup_by_id: Mapping[str, Mapping[str, object]],
    matchup_summary_sha256: str,
    cap: int,
    entry_budget: int,
) -> dict[str, object]:
    if type(cap) is not int or cap < entry_budget:
        _fail("matchup admission cap cannot satisfy the entry budget")
    eligible_ids = [
        str(row["lineup_id"]) for row in candidate_view["eligible_candidates"]
    ]
    missing = [lineup_id for lineup_id in eligible_ids if lineup_id not in matchup_by_id]
    if missing:
        _fail("matchup summary does not cover the fold-eligible union")
    qualifying = [
        lineup_id
        for lineup_id in eligible_ids
        if matchup_by_id[lineup_id]["qualifies_for_matchup_admission"] is True
    ]
    ranked = sorted(
        qualifying,
        key=lambda lineup_id: (
            -float(matchup_by_id[lineup_id]["matchup_edge_mean"]), lineup_id
        ),
    )
    admitted_ranked = ranked[: min(cap, len(ranked))]
    if len(admitted_ranked) < entry_budget:
        _fail(
            "matchup admission has fewer qualifying candidates than the exact budget"
        )
    admitted_set = set(admitted_ranked)
    excluded = []
    for lineup_id in eligible_ids:
        row = matchup_by_id[lineup_id]
        if lineup_id in admitted_set:
            continue
        if row["qualifies_for_matchup_admission"] is not True:
            reason = "matchup-insufficient-or-missing-support"
        else:
            reason = "matchup-below-cap-cutoff"
        excluded.append({"lineup_id": lineup_id, "reason_code": reason})
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": (
            MATCHUP_ADMISSION_ID
            if candidate_view["dose_authority"] == AUTHORITATIVE_DOSE
            else f"{FIXTURE_ID_PREFIX}matchup-top-{cap}-supported-v2"
        ),
        "fit_scope_id": candidate_view["fit_scope_id"],
        "selection_provenance_sha256": candidate_view[
            "selection_provenance_sha256"
        ],
        "matchup_summary_sha256": matchup_summary_sha256,
        "admission_cap": cap,
        "fallback_policy": (
            "admit-all-qualifying-if-at-least-budget-otherwise-fail"
        ),
        "admitted_lineup_ids": sorted(admitted_set),
        "matchup_ranked_lineup_ids": admitted_ranked,
        "admitted_count": len(admitted_set),
        "excluded_eligible_candidates": excluded,
        "dose_authority": candidate_view["dose_authority"],
        "admission_inputs": "matchup-edge-plus-completeness-and-stable-lineup-id",
        "uses_simulated_scores": False,
        "uses_matchup_values": True,
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, "admission_sha256")


def _recurrence_bin(count: int) -> str:
    if count <= 1:
        return "1"
    if count <= 4:
        return "2-4"
    return "5-plus"


def _count_bin(count: int) -> str:
    if count == 0:
        return "0"
    if count == 1:
        return "1"
    if count <= 3:
        return "2-3"
    return "4-plus"


def _completeness_bin(value: float) -> str:
    if value <= 0.0:
        return "0"
    if value < 0.5:
        return "lt-0.5"
    if value < 1.0:
        return "0.5-to-lt-1"
    return "1"


def build_neutral_strata(
    candidate_view: Mapping[str, object],
    *,
    matchup_by_id: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Project score/value-free composition cells for neutral admissions."""
    result: dict[str, dict[str, object]] = {}
    for candidate in candidate_view["eligible_candidates"]:
        lineup_id = str(candidate["lineup_id"])
        if lineup_id not in matchup_by_id:
            _fail("neutral strata lack matchup availability metadata")
        matchup = matchup_by_id[lineup_id]
        # Deliberately excludes matchup_edge_mean and every simulated score.
        result[lineup_id] = {
            "training_source_arms": list(candidate["training_source_arms"]),
            "training_block_support_count": len(
                candidate["training_origin_blocks"]
            ),
            "training_recurrence_bin": _recurrence_bin(
                int(candidate["training_occurrence_count"])
            ),
            "eligible_player_count_bin": _count_bin(
                int(matchup["eligible_player_count"])
            ),
            "supported_player_count_bin": _count_bin(
                int(matchup["supported_player_count"])
            ),
            "annotation_completeness_bin": _completeness_bin(
                float(matchup["annotation_completeness"])
            ),
            "supported_families": list(matchup["supported_families"]),
        }
    return result


def build_score_blind_neutral_admission(
    *,
    candidate_ids: Sequence[str],
    target_ids: Sequence[str],
    strata_by_id: Mapping[str, Mapping[str, object]],
    slate: Mapping[str, object],
    fit_scope_id: str,
    seed_root: str,
    replicate_index: int,
    selection_provenance_sha256: str,
    target_admission_sha256: str,
    dose_authority: str,
) -> dict[str, object]:
    """Match target size/strata using only hashes, IDs, and score-free cells."""
    candidate_values = [str(value) for value in candidate_ids]
    target_values = [str(value) for value in target_ids]
    if (
        len(set(candidate_values)) != len(candidate_values)
        or len(set(target_values)) != len(target_values)
        or not set(target_values).issubset(candidate_values)
        or set(strata_by_id) != set(candidate_values)
    ):
        _fail("neutral admission candidates/targets/strata differ")
    candidates = sorted(candidate_values)
    targets = sorted(target_values)
    if type(seed_root) is not str or not seed_root:
        _fail("neutral seed_root must be nonempty")
    if type(replicate_index) is not int or replicate_index < 0:
        _fail("neutral replicate index must be nonnegative")
    if dose_authority not in {AUTHORITATIVE_DOSE, FIXTURE_DOSE}:
        _fail("neutral dose authority differs")
    for label, value in (
        ("selection provenance", selection_provenance_sha256),
        ("target admission", target_admission_sha256),
    ):
        if not _is_lower_sha256(value):
            _fail(f"neutral {label} SHA must be lowercase 64-hex")
    key_by_id = {
        lineup_id: canonical_json_bytes(strata_by_id[lineup_id]).decode("utf-8")
        for lineup_id in candidates
    }
    target_counts = Counter(key_by_id[lineup_id] for lineup_id in targets)
    candidates_by_key: dict[str, list[str]] = defaultdict(list)
    for lineup_id in candidates:
        candidates_by_key[key_by_id[lineup_id]].append(lineup_id)
    selected: list[str] = []
    for stratum_key in sorted(target_counts):
        needed = target_counts[stratum_key]
        available = candidates_by_key[stratum_key]
        ranked = sorted(
            available,
            key=lambda lineup_id: (
                sha256(canonical_json_bytes({
                    "neutral_law_id": NEUTRAL_LAW_ID,
                    "seed_root": seed_root,
                    "slate": dict(slate),
                    "fit_scope_id": fit_scope_id,
                    "replicate_index": replicate_index,
                    "stratum": json_loads_canonical(stratum_key),
                    "lineup_id": lineup_id,
                })).hexdigest(),
                lineup_id,
            ),
        )
        if len(ranked) < needed:
            _fail("neutral stratum cannot reproduce the target composition")
        selected.extend(ranked[:needed])
    admitted = sorted(selected)
    if (
        len(admitted) != len(targets)
        or len(set(admitted)) != len(admitted)
        or Counter(key_by_id[lineup_id] for lineup_id in admitted) != target_counts
    ):
        _fail("neutral admission did not exactly match target composition")
    selected_set = set(admitted)
    excluded = [
        {"lineup_id": lineup_id, "reason_code": "neutral-not-sampled"}
        for lineup_id in candidates
        if lineup_id not in selected_set
    ]
    neutral_prefix = "" if dose_authority == AUTHORITATIVE_DOSE else FIXTURE_ID_PREFIX
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": (
            f"{neutral_prefix}neutral-{replicate_index:02d}-{NEUTRAL_LAW_ID}"
        ),
        "neutral_law_id": NEUTRAL_LAW_ID,
        "fit_scope_id": fit_scope_id,
        "selection_provenance_sha256": selection_provenance_sha256,
        "target_admission_sha256": target_admission_sha256,
        "target_lineup_ids_sha256": canonical_sha256(targets),
        "candidate_strata_sha256": canonical_sha256({
            lineup_id: strata_by_id[lineup_id] for lineup_id in candidates
        }),
        "seed_root": seed_root,
        "replicate_index": replicate_index,
        "target_admission_size": len(targets),
        "target_stratum_counts": [
            {"stratum": json_loads_canonical(key), "count": target_counts[key]}
            for key in sorted(target_counts)
        ],
        "admitted_lineup_ids": admitted,
        "admitted_count": len(admitted),
        "excluded_eligible_candidates": excluded,
        "excluded_eligible_candidate_count": len(excluded),
        "excluded_eligible_lineup_ids_sha256": canonical_sha256([
            row["lineup_id"] for row in excluded
        ]),
        "excluded_set_replay_law": (
            "sorted-fold-eligible-lineup-ids-minus-admitted-lineup-ids;"
            "reason=neutral-not-sampled"
        ),
        "admission_inputs": (
            "stable-lineup-id-plus-fold-local-provenance-and-annotation-"
            "availability-strata-only"
        ),
        "dose_authority": dose_authority,
        "uses_simulated_scores": False,
        "uses_matchup_values": False,
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, "admission_sha256")


def _validate_admission_partition(
    admission: Mapping[str, object], *, eligible_ids: Sequence[str]
) -> None:
    """Replay one admission's exact admitted/excluded partition."""
    body = _mapping(admission, label="admission partition")
    _validate_self_hash(body, "admission_sha256", label="admission partition")
    candidates = [str(value) for value in eligible_ids]
    admitted = [
        str(value)
        for value in _sequence(
            body.get("admitted_lineup_ids"), label="admitted lineup ids"
        )
    ]
    raw_excluded = _sequence(
        body.get("excluded_eligible_candidates"),
        label="excluded eligible candidates",
    )
    excluded: list[dict[str, str]] = []
    for offset, raw_row in enumerate(raw_excluded):
        row = _mapping(raw_row, label=f"excluded eligible candidate[{offset}]")
        if set(row) != {"lineup_id", "reason_code"} or any(
            type(row[key]) is not str or not row[key]
            for key in ("lineup_id", "reason_code")
        ):
            _fail("excluded eligible candidate fields/values differ")
        excluded.append({
            "lineup_id": str(row["lineup_id"]),
            "reason_code": str(row["reason_code"]),
        })
    excluded_ids = [row["lineup_id"] for row in excluded]
    if (
        candidates != sorted(set(candidates))
        or admitted != sorted(set(admitted))
        or excluded_ids != sorted(set(excluded_ids))
        or set(admitted) & set(excluded_ids)
        or set(admitted) | set(excluded_ids) != set(candidates)
        or body.get("admitted_count") != len(admitted)
    ):
        _fail("admission admitted/excluded partition does not replay")
    admission_id = str(body.get("admission_id"))
    normalized_id = (
        admission_id[len(FIXTURE_ID_PREFIX):]
        if admission_id.startswith(FIXTURE_ID_PREFIX)
        else admission_id
    )
    allowed_reasons: set[str]
    if normalized_id == FULL_UNION_ADMISSION_ID:
        allowed_reasons = set()
    elif normalized_id.startswith("matchup-top-"):
        allowed_reasons = {
            "matchup-insufficient-or-missing-support",
            "matchup-below-cap-cutoff",
        }
    elif normalized_id.startswith("neutral-"):
        allowed_reasons = {"neutral-not-sampled"}
    else:
        _fail("admission partition has an unregistered admission id")
    if any(row["reason_code"] not in allowed_reasons for row in excluded):
        _fail("admission exclusion reason differs from its registered law")
    if "excluded_eligible_candidate_count" in body and body.get(
        "excluded_eligible_candidate_count"
    ) != len(excluded):
        _fail("admission excluded count differs")
    if "excluded_eligible_lineup_ids_sha256" in body and body.get(
        "excluded_eligible_lineup_ids_sha256"
    ) != canonical_sha256(excluded_ids):
        _fail("admission excluded identity hash differs")


def json_loads_canonical(value: str) -> object:
    """Decode one internally generated canonical JSON stratum key."""
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:  # pragma: no cover - internal invariant
        raise CorpusBatchRetrievalV2Error("neutral stratum key is invalid") from exc


def _neutral_diagnostics(
    neutrals: Sequence[Mapping[str, object]], *, target_ids: Sequence[str]
) -> dict[str, object]:
    memberships = [
        tuple(str(value) for value in neutral["admitted_lineup_ids"])
        for neutral in neutrals
    ]
    membership_hashes = [canonical_sha256(list(values)) for values in memberships]
    target = set(str(value) for value in target_ids)
    target_overlaps = [len(target & set(values)) for values in memberships]
    pair_overlaps = [
        len(set(memberships[left]) & set(memberships[right]))
        for left in range(len(memberships))
        for right in range(left + 1, len(memberships))
    ]
    duplicate_groups = [
        {
            "membership_sha256": digest,
            "replicate_indices": [
                index for index, value in enumerate(membership_hashes)
                if value == digest
            ],
        }
        for digest in sorted(set(membership_hashes))
        if membership_hashes.count(digest) > 1
    ]
    body = {
        "schema_version": "corpus-neutral-control-diagnostics/v1",
        "replicate_count": len(memberships),
        "unique_membership_count": len(set(membership_hashes)),
        "membership_sha256_by_replicate": membership_hashes,
        "target_overlap_count_by_replicate": target_overlaps,
        "pairwise_overlap": {
            "pair_count": len(pair_overlaps),
            "minimum": min(pair_overlaps) if pair_overlaps else None,
            "maximum": max(pair_overlaps) if pair_overlaps else None,
            "mean": (
                float(np.mean(pair_overlaps, dtype=np.float64))
                if pair_overlaps else None
            ),
        },
        "duplicate_membership_groups": duplicate_groups,
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, "neutral_diagnostics_sha256")


def _score_summary(scores: np.ndarray) -> dict[str, object]:
    matrix = np.asarray(scores)
    if matrix.ndim != 2 or not matrix.shape[0] or not matrix.shape[1]:
        _fail("score summary requires one nonempty selected book")
    best = matrix.max(axis=0)
    body: dict[str, object] = {
        "lineup_count": int(matrix.shape[0]),
        "world_count": int(matrix.shape[1]),
        "expected_book_max": float(best.mean(dtype=np.float64)),
        "maximum_book_score": float(best.max()),
    }
    for label, threshold, operator in THRESHOLDS:
        body[f"worlds_{label}"] = int(
            np.count_nonzero(_operator_mask(best, threshold, operator))
        )
    return body


def _metric_vector(
    scores: np.ndarray, *, blocks: Sequence[str], worlds_per_block: int
) -> dict[str, object]:
    if scores.shape[1] != len(blocks) * worlds_per_block:
        _fail("metric score columns differ from the named block scope")
    return {
        "aggregate": _score_summary(scores),
        "by_block": [
            {
                "block_id": block,
                **_score_summary(scores[:, ordinal * worlds_per_block:(ordinal + 1) * worlds_per_block]),
            }
            for ordinal, block in enumerate(blocks)
        ],
    }


def _bounded_pairwise_score_correlation(
    scores: np.ndarray,
    *,
    lineup_ids: Sequence[str],
) -> dict[str, object]:
    """Materialize a stable bounded correlation sample without matrix copies."""
    matrix = np.asarray(scores)
    ids = [str(value) for value in lineup_ids]
    if (
        matrix.ndim != 2
        or matrix.shape[0] != len(ids)
        or len(set(ids)) != len(ids)
        or any(not value for value in ids)
    ):
        _fail("pairwise correlation inputs differ")
    pair_population = [
        (min(ids[left], ids[right]), max(ids[left], ids[right]), left, right)
        for left in range(len(ids))
        for right in range(left + 1, len(ids))
    ]
    ranked_pairs = sorted(
        pair_population,
        key=lambda value: (
            sha256(canonical_json_bytes({
                "law": "stable-lineup-id-hash-pair-sample-v1",
                "left_lineup_id": value[0],
                "right_lineup_id": value[1],
            })).hexdigest(),
            value[0],
            value[1],
        ),
    )[:CORRELATION_PAIR_SAMPLE_CAP]
    world_count = matrix.shape[1]
    sums = matrix.sum(axis=1, dtype=np.float64)
    sum_squares = np.einsum(
        "ij,ij->i", matrix, matrix, dtype=np.float64, optimize=False
    )
    variance_terms = np.maximum(
        world_count * sum_squares - sums * sums,
        0.0,
    )
    rows: list[dict[str, object]] = []
    defined_values: list[float] = []
    for left_id, right_id, left, right in ranked_pairs:
        denominator = math.sqrt(
            float(variance_terms[left]) * float(variance_terms[right])
        )
        correlation: float | None = None
        if denominator > 0.0:
            numerator = (
                world_count
                * float(np.dot(matrix[left], matrix[right]))
                - float(sums[left]) * float(sums[right])
            )
            correlation = float(round(
                max(-1.0, min(1.0, numerator / denominator)),
                12,
            ))
            defined_values.append(correlation)
        rows.append({
            "left_lineup_id": left_id,
            "right_lineup_id": right_id,
            "pearson_correlation": correlation,
            "defined": correlation is not None,
        })
    body = {
        "schema_version": "corpus-bounded-pairwise-score-correlation/v1",
        "representation": "deterministic-stable-lineup-id-pair-sample",
        "selection_law": (
            "ascending-sha256(law,left-lineup-id,right-lineup-id),then-ids"
        ),
        "pair_population_count": len(pair_population),
        "pair_sample_cap": CORRELATION_PAIR_SAMPLE_CAP,
        "sampled_pair_count": len(rows),
        "defined_pair_count": len(defined_values),
        "constant-series-pair-count": len(rows) - len(defined_values),
        "minimum": min(defined_values) if defined_values else None,
        "maximum": max(defined_values) if defined_values else None,
        "mean": (
            float(np.mean(defined_values, dtype=np.float64))
            if defined_values else None
        ),
        "rows": rows,
        "full_pairwise_materialized": (
            len(pair_population) <= CORRELATION_PAIR_SAMPLE_CAP
        ),
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, "pairwise_correlation_sha256")


def _book_redundancy_diagnostics(
    scores: np.ndarray,
    *,
    rosters: Sequence[Sequence[str]],
    lineup_ids: Sequence[str],
) -> dict[str, object]:
    """Compact exact diagnostics replayable from the bound selected matrix."""
    matrix = np.asarray(scores)
    if (
        matrix.ndim != 2
        or matrix.shape[0] != len(rosters)
        or matrix.shape[0] != len(lineup_ids)
        or not len(rosters)
    ):
        _fail("book redundancy inputs differ")
    normalized_rosters = [tuple(str(value) for value in roster) for roster in rosters]
    if any(
        len(roster) != rw.ROSTER_SIZE or len(set(roster)) != rw.ROSTER_SIZE
        for roster in normalized_rosters
    ):
        _fail("book redundancy roster differs")
    exposures = Counter(
        player_id for roster in normalized_rosters for player_id in roster
    )
    overlap_histogram = Counter(
        len(set(normalized_rosters[left]) & set(normalized_rosters[right]))
        for left in range(len(normalized_rosters))
        for right in range(left + 1, len(normalized_rosters))
    )
    pair_count = len(normalized_rosters) * (len(normalized_rosters) - 1) // 2
    event_redundancy = []
    for label, threshold, operator in THRESHOLDS:
        mask = _operator_mask(matrix, threshold, operator)
        individual_events = mask.sum(axis=1, dtype=np.int64)
        individual_total = int(individual_events.sum(dtype=np.int64))
        covered_worlds = int(np.count_nonzero(mask.any(axis=0)))
        redundant_events = individual_total - covered_worlds
        event_redundancy.append({
            "label": label,
            "threshold": threshold,
            "operator": operator,
            "book_covered_world_count": covered_worlds,
            "selected_lineup_event_count_sum": individual_total,
            "redundant_event_count_beyond_first_book_cover": redundant_events,
            "redundant_event_fraction": (
                float(redundant_events / individual_total)
                if individual_total else None
            ),
            "selected_lineup_event_count_minimum": int(individual_events.min()),
            "selected_lineup_event_count_maximum": int(individual_events.max()),
            "selected_lineup_event_count_mean": float(
                individual_events.mean(dtype=np.float64)
            ),
        })
    body = {
        "schema_version": "corpus-book-redundancy-diagnostics/v1",
        "selected_score_matrix_sha256": _score_matrix_sha256(matrix),
        "selected_rosters_sha256": canonical_sha256([
            list(roster) for roster in normalized_rosters
        ]),
        "distinct_player_count": len(exposures),
        "maximum_player_exposure_count": max(exposures.values()),
        "player_exposure_count_histogram": [
            {"lineup_count": count, "player_count": frequency}
            for count, frequency in sorted(Counter(exposures.values()).items())
        ],
        "lineup_pair_count": pair_count,
        "shared_player_count_histogram": [
            {"shared_player_count": overlap, "lineup_pair_count": frequency}
            for overlap, frequency in sorted(overlap_histogram.items())
        ],
        "simulated_outcome_event_redundancy": event_redundancy,
        "pairwise_score_correlation": _bounded_pairwise_score_correlation(
            matrix,
            lineup_ids=lineup_ids,
        ),
        "correlation_replay_source": "bound-selected-score-matrix",
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, "redundancy_diagnostics_sha256")


def _select_expected_max_without_matrix_copy(
    scores: np.ndarray,
    *,
    budget: int,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    """Byte-semantic parity with v1 expected-max without a float64 copy."""
    values = np.asarray(scores, dtype=np.float64)
    means = values.mean(axis=1)
    primary_counts = (scores > 200.0).sum(axis=1, dtype=np.int64)
    current: np.ndarray | None = None
    remaining = set(range(scores.shape[0]))
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < budget and remaining:
        order = sorted(remaining)
        rows = np.asarray(order, dtype=np.int64)
        if current is None:
            gains = means[rows]
        else:
            gains = np.maximum(values[rows] - current, 0.0).mean(axis=1)
        gain_by_index = {
            index: float(gain) for index, gain in zip(order, gains, strict=True)
        }
        best = sorted(
            order,
            key=lambda index: (
                -gain_by_index[index],
                -int(primary_counts[index]),
                -float(means[index]),
                lineup_ids[index],
            ),
        )[0]
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": gain_by_index[best],
            "discovery_primary_event_count": int(primary_counts[best]),
            "discovery_mean_score": float(means[best]),
        })
        current = (
            values[best].copy()
            if current is None
            else np.maximum(current, values[best])
        )
        remaining.remove(best)
    return selected, trace


def _run_strategy_v2(
    strategy: Mapping[str, object],
    *,
    training_scores: np.ndarray,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    if strategy["method"] == "greedy-expected-max-v1":
        return _select_expected_max_without_matrix_copy(
            training_scores,
            budget=int(strategy["entry_budget"]),
            lineup_ids=lineup_ids,
        )
    return retrieval._run_strategy(
        strategy,
        discovery_scores=training_scores,
        lineup_ids=lineup_ids,
    )


def _trace_evidence(
    *,
    strategy: Mapping[str, object],
    scores: np.ndarray,
    lineup_ids: Sequence[str],
    selected: Sequence[int],
    base_trace: Sequence[Mapping[str, object]],
    blocks: Sequence[str],
    worlds_per_block: int,
) -> list[dict[str, object]]:
    """Replay selected rows into complete objective/contribution evidence."""
    method = str(strategy["method"])
    parameters = _mapping(strategy["parameters"], label="strategy parameters")
    if len(selected) != len(base_trace):
        _fail("selector trace length differs from selected book")
    block_count = len(blocks)
    if scores.shape[1] != block_count * worlds_per_block:
        _fail("selector trace block scope differs")
    cumulative_total: int | float = 0
    current_max: np.ndarray | None = None
    covered_single: np.ndarray | None = None
    rung_masks: list[np.ndarray] = []
    rung_covered: list[np.ndarray] = []
    rungs: list[Mapping[str, object]] = []
    block_state = np.zeros(block_count, dtype=np.int64)
    mean_block_state = np.zeros(block_count, dtype=np.float64)
    if method == "greedy-threshold-coverage-v1":
        covered_single = np.zeros(scores.shape[1], dtype=bool)
    elif method in {
        "greedy-tail-ladder-v1",
        "greedy-block-supported-ladder-v1",
        "greedy-blockmin-ladder-v1",
    }:
        rungs = [
            _mapping(value, label="strategy rung")
            for value in _sequence(parameters["rungs"], label="strategy rungs")
        ]
        rung_masks = [
            _operator_mask(scores, float(rung["threshold"]), str(rung["operator"]))
            for rung in rungs
        ]
        rung_covered = [np.zeros(scores.shape[1], dtype=bool) for _ in rungs]

    evidence: list[dict[str, object]] = []
    for rank, (selected_index, raw_trace) in enumerate(
        zip(selected, base_trace, strict=True)
    ):
        trace = _mapping(raw_trace, label=f"selector trace[{rank}]")
        if (
            trace.get("selection_rank") != rank
            or trace.get("lineup_index") != selected_index
            or trace.get("lineup_id") != lineup_ids[selected_index]
        ):
            _fail("selector trace identity differs")
        threshold_contributions: list[dict[str, object]] = []
        block_contributions: list[dict[str, object]] = []
        before_blocks: list[int | float] = []
        gain_blocks: list[int | float] = []
        after_blocks: list[int | float] = []

        if method == "greedy-threshold-coverage-v1":
            assert covered_single is not None
            mask = _operator_mask(
                scores[selected_index],
                float(parameters["threshold"]),
                str(parameters["operator"]),
            )
            fresh = mask & ~covered_single
            before_total = int(np.count_nonzero(covered_single))
            gain_total = int(np.count_nonzero(fresh))
            after_total = before_total + gain_total
            for block_ordinal, block in enumerate(blocks):
                start = block_ordinal * worlds_per_block
                stop = start + worlds_per_block
                before = int(np.count_nonzero(covered_single[start:stop]))
                gain = int(np.count_nonzero(fresh[start:stop]))
                before_blocks.append(before)
                gain_blocks.append(gain)
                after_blocks.append(before + gain)
            threshold_contributions.append({
                "threshold": float(parameters["threshold"]),
                "operator": str(parameters["operator"]),
                "weight": 1,
                "new_world_count": gain_total,
                "weighted_utility": gain_total,
            })
            covered_single |= mask
            cumulative_total = after_total
        elif method in {
            "greedy-tail-ladder-v1",
            "greedy-block-supported-ladder-v1",
            "greedy-blockmin-ladder-v1",
        }:
            weighted_by_block = np.zeros(block_count, dtype=np.int64)
            for rung, mask, covered in zip(rungs, rung_masks, rung_covered, strict=True):
                fresh = mask[selected_index] & ~covered
                weight = int(rung["weight"])
                support = 1
                if method == "greedy-block-supported-ladder-v1":
                    support = int(
                        mask[selected_index]
                        .reshape(block_count, worlds_per_block)
                        .any(axis=1)
                        .sum()
                    )
                new_count = int(np.count_nonzero(fresh))
                weighted = weight * support * new_count
                threshold_contributions.append({
                    "threshold": float(rung["threshold"]),
                    "operator": str(rung["operator"]),
                    "weight": weight,
                    "support_factor": support,
                    "new_world_count": new_count,
                    "weighted_utility": weighted,
                })
                weighted_by_block += (
                    weight
                    * support
                    * fresh.reshape(block_count, worlds_per_block).sum(
                        axis=1, dtype=np.int64
                    )
                )
            gain_total = int(weighted_by_block.sum())
            before_vector = block_state.copy()
            after_vector = before_vector + weighted_by_block
            before_total = int(before_vector.sum())
            after_total = int(after_vector.sum())
            before_blocks = [int(value) for value in before_vector]
            gain_blocks = [int(value) for value in weighted_by_block]
            after_blocks = [int(value) for value in after_vector]
            block_state = after_vector
            cumulative_total = after_total
            for mask, covered in zip(rung_masks, rung_covered, strict=True):
                covered |= mask[selected_index]
        elif method == "rank-mean-score-v1":
            row = scores[selected_index]
            gain_total = float(row.mean(dtype=np.float64))
            before_total = float(cumulative_total)
            after_total = before_total + gain_total
            gain_blocks = [
                float(row[offset * worlds_per_block:(offset + 1) * worlds_per_block].mean(dtype=np.float64))
                for offset in range(block_count)
            ]
            before_blocks = [float(value) for value in mean_block_state]
            mean_block_state = mean_block_state + np.asarray(
                gain_blocks, dtype=np.float64
            )
            after_blocks = [float(value) for value in mean_block_state]
            cumulative_total = after_total
        elif method == "greedy-expected-max-v1":
            row = scores[selected_index].astype(np.float64, copy=False)
            if current_max is None:
                before_vector = np.zeros_like(row)
                after_vector = row.copy()
            else:
                before_vector = current_max
                after_vector = np.maximum(before_vector, row)
            improvement = after_vector - before_vector
            before_total = float(before_vector.mean(dtype=np.float64))
            gain_total = float(improvement.mean(dtype=np.float64))
            after_total = float(after_vector.mean(dtype=np.float64))
            before_blocks = [
                float(before_vector[offset * worlds_per_block:(offset + 1) * worlds_per_block].mean(dtype=np.float64))
                for offset in range(block_count)
            ]
            gain_blocks = [
                float(improvement[offset * worlds_per_block:(offset + 1) * worlds_per_block].mean(dtype=np.float64))
                for offset in range(block_count)
            ]
            after_blocks = [
                float(after_vector[offset * worlds_per_block:(offset + 1) * worlds_per_block].mean(dtype=np.float64))
                for offset in range(block_count)
            ]
            current_max = after_vector
        else:  # pragma: no cover - registry/dispatcher parity is separately tested
            _fail(f"unregistered trace method {method!r}")

        if not threshold_contributions:
            if method == "greedy-expected-max-v1":
                for label, threshold, operator in THRESHOLDS:
                    before_event = _operator_mask(
                        before_vector, threshold, operator
                    )
                    after_event = _operator_mask(
                        after_vector, threshold, operator
                    )
                    threshold_contributions.append({
                        "label": label,
                        "threshold": threshold,
                        "operator": operator,
                        "new_book_world_count": int(
                            np.count_nonzero(after_event & ~before_event)
                        ),
                    })
            else:
                for label, threshold, operator in THRESHOLDS:
                    threshold_contributions.append({
                        "label": label,
                        "threshold": threshold,
                        "operator": operator,
                        "selected_lineup_event_count": int(np.count_nonzero(
                            _operator_mask(scores[selected_index], threshold, operator)
                        )),
                        "objective_contribution": None,
                    })

        retained_gain = trace.get("marginal_utility")
        if isinstance(gain_total, float):
            if not math.isclose(float(retained_gain), gain_total, rel_tol=0.0, abs_tol=1e-12):
                _fail("selector marginal utility does not replay")
        elif retained_gain != gain_total:
            _fail("selector marginal utility does not replay")
        objective_before: object = before_total
        objective_gain: object = gain_total
        objective_after: object = after_total
        objective_law = {
            "greedy-threshold-coverage-v1": "distinct-world-threshold-coverage",
            "greedy-tail-ladder-v1": "weighted-distinct-world-tail-ladder",
            "rank-mean-score-v1": "ranked-individual-mean-score",
            "greedy-expected-max-v1": "mean-per-world-book-maximum",
            "greedy-block-supported-ladder-v1": (
                "block-support-scaled-weighted-tail-ladder"
            ),
            "greedy-blockmin-ladder-v1": (
                "leximin-ascending-per-block-weighted-coverage"
            ),
        }[method]
        if method == "greedy-blockmin-ladder-v1":
            retained_before = trace.get("block_utilities_before")
            retained_added = trace.get("block_utilities_added")
            retained_after = trace.get("block_utilities_after")
            retained_leximin = trace.get("leximin_profile_after")
            expected_leximin = sorted(after_blocks)
            if (
                retained_before != before_blocks
                or retained_added != gain_blocks
                or retained_after != after_blocks
                or retained_leximin != expected_leximin
            ):
                _fail("block-min selector objective vector does not replay")
            objective_before = {
                "block_utilities": before_blocks,
                "leximin_profile": sorted(before_blocks),
            }
            objective_gain = {
                "block_utility_delta": gain_blocks,
                "marginal_utility_sum": gain_total,
            }
            objective_after = {
                "block_utilities": after_blocks,
                "leximin_profile": expected_leximin,
            }
        block_contributions = [
            {
                "block_id": block,
                "objective_before": before_blocks[offset],
                "objective_gain": gain_blocks[offset],
                "objective_after": after_blocks[offset],
            }
            for offset, block in enumerate(blocks)
        ]
        selector_event_definition = (
            {
                "threshold": float(parameters["threshold"]),
                "operator": str(parameters["operator"]),
            }
            if method == "greedy-threshold-coverage-v1"
            else {"threshold": 200.0, "operator": ">"}
        )
        evidence.append({
            "selection_rank": rank,
            "lineup_index": selected_index,
            "lineup_id": lineup_ids[selected_index],
            "objective_law": objective_law,
            "objective_before": objective_before,
            "objective_gain": objective_gain,
            "objective_after": objective_after,
            "threshold_contributions": threshold_contributions,
            "block_contributions": block_contributions,
            "tie_break_values": {
                "individual_selector_event_count": int(
                    trace["discovery_primary_event_count"]
                ),
                "selector_event_definition": selector_event_definition,
                "training_mean_score": float(trace["discovery_mean_score"]),
                "stable_lineup_id": lineup_ids[selected_index],
            },
            "base_trace": dict(trace),
        })
    return evidence


def _run_book(
    *,
    strategy: Mapping[str, object],
    admission: Mapping[str, object],
    admitted_ids: Sequence[str],
    admitted_global: np.ndarray,
    training_scores: np.ndarray,
    training_score_matrix_sha256: str,
    roster_by_id: Mapping[str, Sequence[str]],
    global_index_by_id: Mapping[str, int],
    scores: np.ndarray,
    heldout_columns: np.ndarray | None,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    fit_scope_id: str,
    reconstruction_sha256: str,
    dose_authority: str,
) -> dict[str, object]:
    admitted_ids = [str(value) for value in admitted_ids]
    if (
        admitted_ids != admission["admitted_lineup_ids"]
        or admitted_ids != sorted(set(admitted_ids))
        or len(admitted_ids) < ENTRY_BUDGET
        or admitted_global.shape != (len(admitted_ids),)
        or training_scores.shape[0] != len(admitted_ids)
    ):
        _fail("admission cannot satisfy exact-80 selection")
    selected_local, base_trace = _run_strategy_v2(
        strategy,
        training_scores=training_scores,
        lineup_ids=admitted_ids,
    )
    if len(selected_local) != ENTRY_BUDGET or len(set(selected_local)) != ENTRY_BUDGET:
        _fail("registered selector did not produce exact-80 unique entries")
    selected_ids = [admitted_ids[index] for index in selected_local]
    selected_global = [int(admitted_global[index]) for index in selected_local]
    selected_rosters = [
        list(roster_by_id[lineup_id]) for lineup_id in selected_ids
    ]
    trace = _trace_evidence(
        strategy=strategy,
        scores=training_scores,
        lineup_ids=admitted_ids,
        selected=selected_local,
        base_trace=base_trace,
        blocks=training_blocks,
        worlds_per_block=worlds_per_block,
    )
    for row in trace:
        local_index = int(row.pop("lineup_index"))
        row["admitted_lineup_index"] = local_index
        row["global_lineup_index"] = int(
            global_index_by_id[str(row["lineup_id"])]
        )
    selected_training = training_scores[
        np.asarray(selected_local, dtype=np.int64)
    ]
    heldout_metrics = None
    if heldout_columns is not None:
        heldout_scores = np.ascontiguousarray(
            scores[np.ix_(np.asarray(selected_global, dtype=np.int64), heldout_columns)],
            dtype=np.float64,
        )
        heldout_metrics = _metric_vector(
            heldout_scores, blocks=[str(heldout_block)], worlds_per_block=worlds_per_block
        )
    body = {
        "schema_version": BOOK_SCHEMA,
        "book_id": (
            f"{fit_scope_id}:{admission['admission_id']}:"
            f"{strategy['strategy_id']}"
        ),
        "fit_scope_id": fit_scope_id,
        "reconstruction_sha256": reconstruction_sha256,
        "training_blocks": list(training_blocks),
        "heldout_block": heldout_block,
        "admission_id": admission["admission_id"],
        "admission_sha256": admission["admission_sha256"],
        "strategy_id": strategy["strategy_id"],
        "strategy_sha256": strategy["strategy_sha256"],
        "strategy_application_scope": (
            "explicit-rotated-training-blocks"
            if heldout_block is not None
            else "explicit-all-five-block-final-fit"
        ),
        "input_lineup_ids_sha256": canonical_sha256(admitted_ids),
        "training_score_matrix_sha256": training_score_matrix_sha256,
        "training_score_shape": list(training_scores.shape),
        "worlds_per_block": worlds_per_block,
        "dose_authority": dose_authority,
        "selected_local_indices": [int(value) for value in selected_local],
        "selected_global_indices": selected_global,
        "selected_lineup_ids": selected_ids,
        "selected_rosters": selected_rosters,
        "entry_count": len(selected_ids),
        "marginal_trace": trace,
        "training_metrics": _metric_vector(
            selected_training,
            blocks=training_blocks,
            worlds_per_block=worlds_per_block,
        ),
        "redundancy_diagnostics": _book_redundancy_diagnostics(
            selected_training,
            rosters=selected_rosters,
            lineup_ids=selected_ids,
        ),
        "heldout_metrics_descriptive": heldout_metrics,
        "threshold_semantics": [
            {"label": label, "threshold": threshold, "operator": operator}
            for label, threshold, operator in THRESHOLDS
        ],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    return _self_hash(body, "book_sha256")


def _run_fit_scope_impl(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    matchup_summary: Mapping[str, object],
    matchup_source: Mapping[str, object],
    heldout_block: str | None,
    admission_m: int = DEFAULT_ADMISSION_M,
    neutral_replicates: int = DEFAULT_NEUTRAL_REPLICATES,
    neutral_seed_root: str = "r6-v2-neutral-v1",
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
    validated_reconstruction_sha256: str | None = None,
    validated_matchup_summary_sha256: str | None = None,
) -> dict[str, object]:
    """Run 7×2 primary cells plus primary-selector neutral controls."""
    if worlds_per_block is None:
        worlds_per_block = retrieval.WORLDS_PER_BLOCK
    if type(neutral_replicates) is not int or neutral_replicates < 1:
        _fail("neutral_replicates must be positive")
    candidates = _validate_provenance(provenance)
    dose_authority = _dose_authority(
        provenance=provenance,
        admission_m=admission_m,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )
    scores = np.asarray(union_scores)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or scores.shape != (len(candidates), len(rw.WORLD_BLOCKS) * worlds_per_block)
        or not np.isfinite(scores).all()
    ):
        _fail("canonical union score matrix shape/dtype/content differs")
    reconstruction_sha256 = (
        _validate_reconstruction_input(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=reconstruction_receipt,
        )
        if validated_reconstruction_sha256 is None
        else validated_reconstruction_sha256
    )
    validated_matchup_summary = (
        validate_matchup_lineup_summaries(
            matchup_summary,
            provenance=provenance,
            matchup_source=matchup_source,
        )
        if validated_matchup_summary_sha256 is None
        else dict(_mapping(matchup_summary, label="matchup summary"))
    )
    if validated_matchup_summary.get(
        "matchup_summary_sha256"
    ) != (
        validated_matchup_summary_sha256
        if validated_matchup_summary_sha256 is not None
        else validated_matchup_summary.get("matchup_summary_sha256")
    ):
        _fail("validated matchup summary identity differs")
    candidate_ids = [str(row["lineup_id"]) for row in candidates]
    roster_by_id = {
        str(row["lineup_id"]): tuple(str(value) for value in row["roster_player_ids"])
        for row in candidates
    }
    global_index_by_id = {
        lineup_id: index for index, lineup_id in enumerate(candidate_ids)
    }
    view = build_fit_candidate_view(
        provenance,
        heldout_block=heldout_block,
        dose_authority=dose_authority,
    )
    eligible_ids = [
        str(row["lineup_id"]) for row in view["eligible_candidates"]
    ]
    if eligible_ids != sorted(eligible_ids) or len(eligible_ids) < ENTRY_BUDGET:
        _fail("fold-eligible union cannot satisfy exact-80")
    matchup_by_id = _summary_by_id(validated_matchup_summary)
    if set(matchup_by_id) != set(candidate_ids):
        _fail("matchup summary differs from canonical candidate union")
    full = _full_union_admission(view)
    matchup = _matchup_admission(
        view,
        matchup_by_id=matchup_by_id,
        matchup_summary_sha256=str(
            validated_matchup_summary["matchup_summary_sha256"]
        ),
        cap=admission_m,
        entry_budget=ENTRY_BUDGET,
    )
    strata = build_neutral_strata(view, matchup_by_id=matchup_by_id)
    neutrals = [
        build_score_blind_neutral_admission(
            candidate_ids=eligible_ids,
            target_ids=matchup["admitted_lineup_ids"],
            strata_by_id=strata,
            slate=provenance["slate"],
            fit_scope_id=str(view["fit_scope_id"]),
            seed_root=neutral_seed_root,
            replicate_index=replicate,
            selection_provenance_sha256=str(view["selection_provenance_sha256"]),
            target_admission_sha256=str(matchup["admission_sha256"]),
            dose_authority=dose_authority,
        )
        for replicate in range(neutral_replicates)
    ]
    for admission in [full, matchup, *neutrals]:
        _validate_admission_partition(admission, eligible_ids=eligible_ids)
    strategies = _validate_strategy_registry()
    training_blocks = [
        block for block in rw.WORLD_BLOCKS if block != heldout_block
    ]
    training_columns = _block_columns(
        training_blocks, worlds_per_block=worlds_per_block
    )
    heldout_columns = (
        None
        if heldout_block is None
        else _block_columns([heldout_block], worlds_per_block=worlds_per_block)
    )
    books: list[dict[str, object]] = []

    def append_admission_books(
        admission: Mapping[str, object],
        admission_strategies: Sequence[Mapping[str, object]],
    ) -> None:
        """Materialize one admission matrix, run its laws, then release it."""
        admitted_ids = [
            str(value) for value in admission["admitted_lineup_ids"]
        ]
        try:
            admitted_global = np.asarray(
                [global_index_by_id[lineup_id] for lineup_id in admitted_ids],
                dtype=np.int64,
            )
        except KeyError as exc:
            raise CorpusBatchRetrievalV2Error(
                "admission contains a lineup outside the canonical reconstruction"
            ) from exc
        training_scores = np.ascontiguousarray(
            scores[np.ix_(admitted_global, training_columns)],
            dtype=np.float64,
        )
        training_score_matrix_sha256 = _score_matrix_sha256(training_scores)
        for strategy in admission_strategies:
            books.append(_run_book(
                strategy=strategy,
                admission=admission,
                admitted_ids=admitted_ids,
                admitted_global=admitted_global,
                training_scores=training_scores,
                training_score_matrix_sha256=training_score_matrix_sha256,
                roster_by_id=roster_by_id,
                global_index_by_id=global_index_by_id,
                scores=scores,
                heldout_columns=heldout_columns,
                training_blocks=training_blocks,
                heldout_block=heldout_block,
                worlds_per_block=worlds_per_block,
                fit_scope_id=str(view["fit_scope_id"]),
                reconstruction_sha256=reconstruction_sha256,
                dose_authority=dose_authority,
            ))

    append_admission_books(full, strategies)
    append_admission_books(matchup, strategies)
    primary = next(
        strategy for strategy in strategies
        if strategy["strategy_id"] == PRIMARY_STRATEGY_ID
    )
    for neutral in neutrals:
        append_admission_books(neutral, [primary])
    expected_books = 14 + neutral_replicates
    if len(books) != expected_books or len({row["book_id"] for row in books}) != len(books):
        _fail("fit-scope book lattice differs")
    body = {
        "schema_version": SCOPE_SCHEMA,
        "fit_scope_id": view["fit_scope_id"],
        "reconstruction_sha256": reconstruction_sha256,
        "training_blocks": training_blocks,
        "heldout_block": heldout_block,
        "worlds_per_block": worlds_per_block,
        "admission_cap": admission_m,
        "dose_authority": dose_authority,
        "require_authoritative": require_authoritative,
        "candidate_view": view,
        "matchup_summary_sha256": validated_matchup_summary[
            "matchup_summary_sha256"
        ],
        "matchup_source_snapshot_sha256": validated_matchup_summary[
            "matchup_source_snapshot_sha256"
        ],
        "admissions": [full, matchup, *neutrals],
        "neutral_control_diagnostics": _neutral_diagnostics(
            neutrals, target_ids=matchup["admitted_lineup_ids"]
        ),
        "strategy_registry": strategies,
        "neutral_controls_apply_to_strategy_id": PRIMARY_STRATEGY_ID,
        "book_count": len(books),
        "books": books,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    return _self_hash(body, "fit_scope_sha256")


def run_fit_scope(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    matchup_summary: Mapping[str, object],
    matchup_source: Mapping[str, object],
    heldout_block: str | None,
    admission_m: int = DEFAULT_ADMISSION_M,
    neutral_replicates: int = DEFAULT_NEUTRAL_REPLICATES,
    neutral_seed_root: str = "r6-v2-neutral-v1",
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Validate one v12 reconstruction and run one fold/final-fit scope."""
    return _run_fit_scope_impl(
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
        matchup_summary=matchup_summary,
        matchup_source=matchup_source,
        heldout_block=heldout_block,
        admission_m=admission_m,
        neutral_replicates=neutral_replicates,
        neutral_seed_root=neutral_seed_root,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )


def run_retrieval_surface_v2(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    matchup_summary: Mapping[str, object],
    matchup_source: Mapping[str, object],
    admission_m: int = DEFAULT_ADMISSION_M,
    neutral_replicates: int = DEFAULT_NEUTRAL_REPLICATES,
    neutral_seed_root: str = "r6-v2-neutral-v1",
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Build five cross-fit scopes and the separate all-block final fit."""
    reconstruction_sha256 = _validate_reconstruction_input(
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
    )
    validated_matchup_summary = validate_matchup_lineup_summaries(
        matchup_summary,
        provenance=provenance,
        matchup_source=matchup_source,
    )
    validated_matchup_summary_sha256 = str(
        validated_matchup_summary["matchup_summary_sha256"]
    )
    folds = [
        _run_fit_scope_impl(
            provenance=provenance,
            union_scores=union_scores,
            reconstruction_receipt=reconstruction_receipt,
            matchup_summary=validated_matchup_summary,
            matchup_source=matchup_source,
            heldout_block=heldout,
            admission_m=admission_m,
            neutral_replicates=neutral_replicates,
            neutral_seed_root=neutral_seed_root,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
            validated_reconstruction_sha256=reconstruction_sha256,
            validated_matchup_summary_sha256=(
                validated_matchup_summary_sha256
            ),
        )
        for heldout in rw.WORLD_BLOCKS
    ]
    final_fit = _run_fit_scope_impl(
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
        matchup_summary=validated_matchup_summary,
        matchup_source=matchup_source,
        heldout_block=None,
        admission_m=admission_m,
        neutral_replicates=neutral_replicates,
        neutral_seed_root=neutral_seed_root,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
        validated_reconstruction_sha256=reconstruction_sha256,
        validated_matchup_summary_sha256=validated_matchup_summary_sha256,
    )
    body = {
        "schema_version": RUNNER_SCHEMA,
        "slate": provenance["slate"],
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "reconstruction_sha256": reconstruction_sha256,
        "matchup_summary_sha256": validated_matchup_summary_sha256,
        "matchup_source_snapshot_sha256": validated_matchup_summary[
            "matchup_source_snapshot_sha256"
        ],
        "folds": folds,
        "final_fit": final_fit,
        "fold_count": len(folds),
        "books_per_scope": 14 + neutral_replicates,
        "cross_fit_book_count": len(folds) * (14 + neutral_replicates),
        "final_fit_book_count": 14 + neutral_replicates,
        "neutral_replicate_count": neutral_replicates,
        "worlds_per_block": final_fit["worlds_per_block"],
        "admission_cap": admission_m,
        "dose_authority": final_fit["dose_authority"],
        "require_authoritative": require_authoritative,
        "neutral_replicate_freeze_requires_outcome_blind_runtime_benchmark": True,
        "final_fit_is_distinct_all-block-refit": True,
        "uses_realized_outcomes": False,
        "evidence_tier": "outcome-blind-simulated-analysis",
        "promotion_authority": False,
    }
    return _self_hash(body, "retrieval_surface_sha256")


def validate_fit_scope(
    value: Mapping[str, object],
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    matchup_summary: Mapping[str, object],
    matchup_source: Mapping[str, object],
    heldout_block: str | None,
    admission_m: int = DEFAULT_ADMISSION_M,
    neutral_replicates: int = DEFAULT_NEUTRAL_REPLICATES,
    neutral_seed_root: str = "r6-v2-neutral-v1",
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Independently replay one retained scope, including every exact trace."""
    retained = _mapping(value, label="retained retrieval fit scope")
    expected = run_fit_scope(
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
        matchup_summary=matchup_summary,
        matchup_source=matchup_source,
        heldout_block=heldout_block,
        admission_m=admission_m,
        neutral_replicates=neutral_replicates,
        neutral_seed_root=neutral_seed_root,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )
    if canonical_json_bytes(retained) != canonical_json_bytes(expected):
        _fail("retained retrieval fit scope canonical replay differs")
    return expected


def validate_retrieval_surface_v2(
    value: Mapping[str, object],
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    matchup_summary: Mapping[str, object],
    matchup_source: Mapping[str, object],
    admission_m: int = DEFAULT_ADMISSION_M,
    neutral_replicates: int = DEFAULT_NEUTRAL_REPLICATES,
    neutral_seed_root: str = "r6-v2-neutral-v1",
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Independently replay all five folds and the distinct final fit."""
    retained = _mapping(value, label="retained retrieval surface")
    expected = run_retrieval_surface_v2(
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
        matchup_summary=matchup_summary,
        matchup_source=matchup_source,
        admission_m=admission_m,
        neutral_replicates=neutral_replicates,
        neutral_seed_root=neutral_seed_root,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )
    if canonical_json_bytes(retained) != canonical_json_bytes(expected):
        _fail("retained retrieval surface canonical replay differs")
    return expected


__all__ = [
    "ADMISSION_SCHEMA",
    "AUTHORITATIVE_DOSE",
    "BOOK_SCHEMA",
    "CORRELATION_PAIR_SAMPLE_CAP",
    "CorpusBatchRetrievalV2Error",
    "DEFAULT_ADMISSION_M",
    "DEFAULT_NEUTRAL_REPLICATES",
    "ENTRY_BUDGET",
    "FULL_UNION_ADMISSION_ID",
    "FIXTURE_DOSE",
    "FIXTURE_ID_PREFIX",
    "MATCHUP_ADMISSION_ID",
    "MATCHUP_SOURCE_SCHEMA",
    "MATCHUP_SUMMARY_SCHEMA",
    "NEUTRAL_LAW_ID",
    "PRIMARY_STRATEGY_ID",
    "RUNNER_SCHEMA",
    "SCOPE_SCHEMA",
    "build_fit_candidate_view",
    "build_matchup_lineup_summaries",
    "build_matchup_source_snapshot",
    "build_neutral_strata",
    "build_score_blind_neutral_admission",
    "run_fit_scope",
    "run_retrieval_surface_v2",
    "validate_fit_scope",
    "validate_matchup_lineup_summaries",
    "validate_matchup_source_snapshot",
    "validate_retrieval_surface_v2",
]
