"""Outcome-blind extreme-tail support census for accepted Foundry v12 corpora.

This pure sidecar answers whether an arm or fold-safe cross-arm corpus contains
ordinary-R simulated opportunities at 220/230/240/250 before any new selector
is credited for retrieving them. It deliberately does not modify R6-v2's
seven-law registry or its older strict/non-strict threshold semantics.

Every fold derives membership and lineage only from training-block provenance.
Held-out ordinary-R scores are descriptive evaluation. The implementation
streams bounded candidate chunks and never materializes a full Boolean event
matrix. Nothing here reads realized outcomes, publishes, mutates a graph, or
grants analytical/promotion authority.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    VISITS_PER_BLOCK,
    canonical_json_bytes,
    canonical_sha256,
)
from nfl_dfs.research.corpus_parametric_batch import PARAMETER_SET_ORDER


CENSUS_SCHEMA: Final = "corpus-extreme-tail-support-census/v1"
UNIVERSE_SCHEMA: Final = "corpus-extreme-tail-support-universe/v1"
METRIC_SCHEMA: Final = "corpus-extreme-tail-opportunity-metrics/v1"
CENSUS_LAW_ID: Final = "ordinary-r-ge-220-230-240-250-support/v1"
THRESHOLDS: Final = (
    ("ge_220", 220.0, ">="),
    ("ge_230", 230.0, ">="),
    ("ge_240", 240.0, ">="),
    ("ge_250", 250.0, ">="),
)
SOURCE_ARM_ORDER: Final = (
    "incumbent",
    "remove-salary-floor",
    "remove-qb-stack",
    "remove-bring-back",
    "allow-rb-vs-dst",
    "allow-two-rb",
    "remove-all-five-shared-constraints",
)
SOURCE_ARM_ORDER_SHA256: Final = (
    "91d04d9fdc58b8ac02262aead9eb21df14a21ff3f8ea03a0e8f7bea9d93ee0fe"
)
LITERAL_230_MIN_TRAINING_OPPORTUNITY_WORLDS: Final = 100
_CANDIDATE_CHUNK_ROWS: Final = 256


class CorpusExtremeTailCensusError(ValueError):
    """The support census cannot be produced without weakening its bindings."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailCensusError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    retained = dict(body)
    retained[field] = canonical_sha256(retained)
    return retained


def _fraction(numerator: int, denominator: int) -> dict[str, int] | None:
    if denominator < 0 or numerator < 0:
        _fail("support fraction counts cannot be negative")
    if denominator == 0:
        return None
    return {"numerator": numerator, "denominator": denominator}


def _validate_source_arm_order() -> None:
    if (
        tuple(PARAMETER_SET_ORDER) != SOURCE_ARM_ORDER
        or canonical_sha256(list(SOURCE_ARM_ORDER)) != SOURCE_ARM_ORDER_SHA256
    ):
        _fail("frozen v12 source-arm order differs")


def _validate_world_ids(
    value: Sequence[Mapping[str, object]],
    *,
    reconstruction_receipt: Mapping[str, object],
    worlds_per_block: int,
) -> list[dict[str, object]]:
    raw_rows = _sequence(value, label="ordered world IDs")
    rows: list[dict[str, object]] = []
    expected_count = len(rw.WORLD_BLOCKS) * worlds_per_block
    if len(raw_rows) != expected_count:
        _fail("ordered world ID count differs from five complete R blocks")
    for flat_index, raw_row in enumerate(raw_rows):
        row = _mapping(raw_row, label=f"world ID[{flat_index}]")
        expected_block = rw.WORLD_BLOCKS[flat_index // worlds_per_block]
        expected_index = flat_index % worlds_per_block
        if (
            set(row) != {"block", "index"}
            or row.get("block") != expected_block
            or type(row.get("index")) is not int
            or row.get("index") != expected_index
        ):
            _fail("ordered world IDs do not match canonical block-major R order")
        rows.append({"block": expected_block, "index": expected_index})
    receipt = _mapping(reconstruction_receipt, label="reconstruction receipt")
    binding = _mapping(receipt.get("matrix_binding"), label="matrix binding")
    if canonical_sha256(rows) != binding.get("world_ids_sha256"):
        _fail("ordered world IDs differ from the reconstruction binding")
    return rows


def _training_lineage_row(
    candidate: Mapping[str, object], *, training_blocks: Sequence[str]
) -> dict[str, object]:
    occurrences = []
    for value in _sequence(candidate["occurrences"], label="candidate occurrences"):
        occurrence = dict(_mapping(value, label="candidate occurrence"))
        if occurrence.get("block_id") in training_blocks:
            occurrences.append(occurrence)
    if not occurrences:
        _fail("fold-eligible lineage row has no training occurrence")
    block_counts = Counter(str(value["block_id"]) for value in occurrences)
    return {
        "lineup_id": candidate["lineup_id"],
        "training_origin_blocks": [
            block for block in training_blocks if block_counts[block]
        ],
        "training_source_arms": [
            arm for arm in PARAMETER_SET_ORDER
            if any(value["parameter_set_id"] == arm for value in occurrences)
        ],
        "training_occurrence_counts_by_block": {
            block: int(block_counts[block]) for block in training_blocks
        },
        "training_occurrence_count": len(occurrences),
        "training_occurrences": occurrences,
    }


def _validate_arm_membership_and_authoritative_dose(
    *,
    candidates: Sequence[Mapping[str, object]],
    provenance: Mapping[str, object],
    reconstruction_receipt: Mapping[str, object],
    require_authoritative: bool,
) -> dict[str, int]:
    _validate_source_arm_order()
    receipt = _mapping(reconstruction_receipt, label="reconstruction receipt")
    raw_arm_receipts = _sequence(
        receipt["verified_arm_score_hashes"],
        label="verified arm score hashes",
    )
    unique_count_by_arm: dict[str, int] = {}
    all_occurrences = [
        _mapping(occurrence, label="candidate occurrence")
        for candidate in candidates
        for occurrence in _sequence(
            candidate["occurrences"], label="candidate occurrences"
        )
    ]
    for ordinal, arm in enumerate(PARAMETER_SET_ORDER):
        arm_receipt = _mapping(
            raw_arm_receipts[ordinal], label=f"arm receipt[{ordinal}]"
        )
        unique_count = int(arm_receipt["unique_count"])
        membership_count = sum(
            any(
                occurrence["parameter_set_id"] == arm
                for occurrence in candidate["occurrences"]
            )
            for candidate in candidates
        )
        if membership_count != unique_count:
            _fail(
                f"source arm {arm!r} universe count differs from its "
                "verified unique-candidate count"
            )
        unique_count_by_arm[arm] = unique_count
    if not require_authoritative:
        return unique_count_by_arm

    visits_per_arm = len(rw.WORLD_BLOCKS) * VISITS_PER_BLOCK
    expected_total = len(PARAMETER_SET_ORDER) * visits_per_arm
    if (
        provenance.get("visits_per_block") != VISITS_PER_BLOCK
        or provenance.get("visit_occurrence_count") != expected_total
        or len(all_occurrences) != expected_total
    ):
        _fail("authoritative provenance does not contain the exact 7x5x200 dose")
    reference_schedule: list[tuple[str, int]] | None = None
    for ordinal, arm in enumerate(PARAMETER_SET_ORDER):
        arm_occurrences = [
            occurrence for occurrence in all_occurrences
            if occurrence["parameter_set_id"] == arm
        ]
        if (
            len(arm_occurrences) != visits_per_arm
            or any(
                occurrence["arm_ordinal"] != ordinal
                for occurrence in arm_occurrences
            )
        ):
            _fail(f"authoritative arm {arm!r} visit dose/ordinal differs")
        by_visit = {
            int(occurrence["visit_ordinal"]): occurrence
            for occurrence in arm_occurrences
        }
        if sorted(by_visit) != list(range(visits_per_arm)):
            _fail(f"authoritative arm {arm!r} visit ordinals differ")
        schedule = [
            (str(by_visit[visit]["block_id"]), int(
                by_visit[visit]["objective_world_index"]
            ))
            for visit in range(visits_per_arm)
        ]
        expected_blocks = [
            block for block in rw.WORLD_BLOCKS
            for _ in range(VISITS_PER_BLOCK)
        ]
        if (
            [block for block, _ in schedule] != expected_blocks
            or len(set(schedule)) != visits_per_arm
        ):
            _fail(f"authoritative arm {arm!r} block/world schedule differs")
        if reference_schedule is None:
            reference_schedule = schedule
        elif schedule != reference_schedule:
            _fail("authoritative visit ordinal-to-world mapping differs across arms")
    retained_schedule = [
        {"block": block, "index": index}
        for block, index in (reference_schedule or [])
    ]
    if canonical_sha256(retained_schedule) != provenance.get(
        "visit_schedule_sha256"
    ):
        _fail("authoritative visit schedule hash differs from provenance")
    return unique_count_by_arm


def _source_support(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    candidate_count_by_block = {
        block: sum(block in row["training_origin_blocks"] for row in rows)
        for block in rw.WORLD_BLOCKS
    }
    occurrence_count_by_block = {
        block: sum(
            int(_mapping(
                row["training_occurrence_counts_by_block"],
                label="training occurrence counts",
            ).get(block, 0))
            for row in rows
        )
        for block in rw.WORLD_BLOCKS
    }
    candidate_count_by_arm = {
        arm: sum(arm in row["training_source_arms"] for row in rows)
        for arm in PARAMETER_SET_ORDER
    }
    occurrence_count_by_arm = {
        arm: sum(
            occurrence["parameter_set_id"] == arm
            for row in rows
            for occurrence in row["training_occurrences"]
        )
        for arm in PARAMETER_SET_ORDER
    }
    occurrence_counts = [int(row["training_occurrence_count"]) for row in rows]
    distinct_arm_visits = {
        (str(occurrence["parameter_set_id"]), int(occurrence["visit_ordinal"]))
        for row in rows for occurrence in row["training_occurrences"]
    }
    body = {
        "candidate_counts_are_nonexclusive_across_arms_and_blocks": True,
        "occurrence_counts_partition_occurrences_by_arm_and_block": True,
        "candidate_count": len(rows),
        "candidate_count_by_training_origin_block": candidate_count_by_block,
        "training_occurrence_count_by_block": occurrence_count_by_block,
        "candidate_count_by_training_source_arm": candidate_count_by_arm,
        "training_occurrence_count_by_source_arm": occurrence_count_by_arm,
        "training_origin_block_breadth_histogram": [
            {"block_count": count, "lineup_count": frequency}
            for count, frequency in sorted(Counter(
                len(row["training_origin_blocks"]) for row in rows
            ).items())
        ],
        "training_source_arm_breadth_histogram": [
            {"arm_count": count, "lineup_count": frequency}
            for count, frequency in sorted(Counter(
                len(row["training_source_arms"]) for row in rows
            ).items())
        ],
        "training_visit_occurrence_count_total": sum(occurrence_counts),
        "distinct_training_arm_visit_count": len(distinct_arm_visits),
        "training_visit_occurrence_count_minimum": min(occurrence_counts),
        "training_visit_occurrence_count_maximum": max(occurrence_counts),
        "training_visit_occurrence_count_mean_fraction": _fraction(
            sum(occurrence_counts), len(occurrence_counts)
        ),
    }
    return body


def _event_lineage(
    rows: Sequence[Mapping[str, object]], event_positive: np.ndarray
) -> dict[str, object]:
    retained = [
        row for row, positive in zip(rows, event_positive, strict=True)
        if bool(positive)
    ]
    distinct_arm_visits = {
        (str(occurrence["parameter_set_id"]), int(occurrence["visit_ordinal"]))
        for row in retained for occurrence in row["training_occurrences"]
    }
    return {
        "event_lineup_counts_are_nonexclusive_across_arms_and_blocks": True,
        "event_occurrence_counts_partition_occurrences_by_arm_and_block": True,
        "event_lineup_count_by_training_source_arm": {
            arm: sum(arm in row["training_source_arms"] for row in retained)
            for arm in PARAMETER_SET_ORDER
        },
        "event_training_occurrence_count_by_source_arm": {
            arm: sum(
                occurrence["parameter_set_id"] == arm
                for row in retained
                for occurrence in row["training_occurrences"]
            )
            for arm in PARAMETER_SET_ORDER
        },
        "event_lineup_count_by_training_origin_block": {
            block: sum(block in row["training_origin_blocks"] for row in retained)
            for block in rw.WORLD_BLOCKS
        },
        "event_training_occurrence_count_by_origin_block": {
            block: sum(
                occurrence["block_id"] == block
                for row in retained
                for occurrence in row["training_occurrences"]
            )
            for block in rw.WORLD_BLOCKS
        },
        "event_distinct_training_arm_visit_count": len(distinct_arm_visits),
    }


def _count_row(
    *,
    label: str,
    threshold: float,
    operator: str,
    candidate_ids: Sequence[str],
    source_rows: Sequence[Mapping[str, object]],
    individual_counts: np.ndarray,
    event_score_block_counts: np.ndarray,
    opportunity_world_ids: Sequence[Mapping[str, object]],
    world_count: int,
    include_lineage: bool,
) -> dict[str, object]:
    event_positive = individual_counts > 0
    event_lineup_ids = [
        lineup_id for lineup_id, positive
        in zip(candidate_ids, event_positive, strict=True)
        if bool(positive)
    ]
    event_total = int(individual_counts.sum(dtype=np.int64))
    opportunity_count = len(opportunity_world_ids)
    candidate_count = len(candidate_ids)
    body: dict[str, object] = {
        "label": label,
        "threshold": threshold,
        "operator": operator,
        "event_lineup_count": len(event_lineup_ids),
        "event_lineup_ids_sha256": canonical_sha256(event_lineup_ids),
        "lineup_world_event_count": event_total,
        "opportunity_world_count": opportunity_count,
        "opportunity_world_ids_sha256": canonical_sha256(
            list(opportunity_world_ids)
        ),
        "non_opportunity_world_count": world_count - opportunity_count,
        "opportunity_rate_fraction": _fraction(opportunity_count, world_count),
        "summed_individual_event_rate_fraction": _fraction(
            event_total, world_count
        ),
        "mean_individual_event_rate_fraction": _fraction(
            event_total, candidate_count * world_count
        ),
        "event_union_efficiency_fraction": _fraction(
            opportunity_count, event_total
        ),
    }
    if include_lineage:
        body.update({
            "event_score_block_breadth_histogram": [
                {"block_count": count, "lineup_count": frequency}
                for count, frequency in sorted(Counter(
                    int(value) for value in event_score_block_counts
                ).items())
            ],
            "event_positive_lineup_generation_origin_block_breadth_histogram": [
                {"block_count": count, "lineup_count": frequency}
                for count, frequency in sorted(Counter(
                    len(row["training_origin_blocks"])
                    for row, positive in zip(
                        source_rows, event_positive, strict=True
                    )
                    if bool(positive)
                ).items())
            ],
            "event_source_lineage": _event_lineage(source_rows, event_positive),
        })
    return body


def _opportunity_metrics(
    scores: np.ndarray,
    *,
    candidate_indices: np.ndarray,
    candidate_ids: Sequence[str],
    source_rows: Sequence[Mapping[str, object]],
    blocks: Sequence[str],
    world_ids: Sequence[Mapping[str, object]],
    worlds_per_block: int,
) -> dict[str, object]:
    matrix = np.asarray(scores)
    ids = [str(value) for value in candidate_ids]
    indices = np.asarray(candidate_indices, dtype=np.int64)
    if (
        matrix.dtype != np.dtype(np.float64)
        or matrix.ndim != 2
        or len(indices) != len(ids)
        or len(source_rows) != len(ids)
        or not len(ids)
        or len(set(ids)) != len(ids)
        or ids != sorted(ids)
        or np.any(indices < 0)
        or np.any(indices >= matrix.shape[0])
    ):
        _fail("tail opportunity matrix/candidate binding differs")
    block_ordinals = [rw.WORLD_BLOCKS.index(block) for block in blocks]
    state = [
        {
            "individual_counts": np.zeros(len(ids), dtype=np.int64),
            "event_score_block_counts": np.zeros(len(ids), dtype=np.uint8),
            "opportunity_world_ids": [],
            "by_block": [],
        }
        for _ in THRESHOLDS
    ]
    for block, block_ordinal in zip(blocks, block_ordinals, strict=True):
        column_start = block_ordinal * worlds_per_block
        column_stop = column_start + worlds_per_block
        block_world_ids = world_ids[column_start:column_stop]
        block_counts = [
            np.zeros(len(ids), dtype=np.int64) for _ in THRESHOLDS
        ]
        opportunity = [
            np.zeros(worlds_per_block, dtype=bool) for _ in THRESHOLDS
        ]
        for row_start in range(0, len(indices), _CANDIDATE_CHUNK_ROWS):
            row_stop = min(row_start + _CANDIDATE_CHUNK_ROWS, len(indices))
            values = np.ascontiguousarray(
                matrix[
                    indices[row_start:row_stop],
                    column_start:column_stop,
                ],
                dtype=np.float64,
            )
            for threshold_ordinal, (_, threshold, operator) in enumerate(
                THRESHOLDS
            ):
                if operator != ">=":
                    _fail("extreme-tail census thresholds must use >= semantics")
                event = values >= threshold
                block_counts[threshold_ordinal][row_start:row_stop] = (
                    event.sum(axis=1, dtype=np.int64)
                )
                opportunity[threshold_ordinal] |= event.any(axis=0)
        for threshold_ordinal, (label, threshold, operator) in enumerate(
            THRESHOLDS
        ):
            counts = block_counts[threshold_ordinal]
            state[threshold_ordinal]["individual_counts"] += counts
            state[threshold_ordinal]["event_score_block_counts"] += (
                counts > 0
            ).astype(np.uint8)
            opportunity_ids = [
                world_id for world_id, positive in zip(
                    block_world_ids,
                    opportunity[threshold_ordinal],
                    strict=True,
                )
                if bool(positive)
            ]
            state[threshold_ordinal]["opportunity_world_ids"].extend(
                opportunity_ids
            )
            state[threshold_ordinal]["by_block"].append({
                "block_id": block,
                "world_count": worlds_per_block,
                "world_ids_sha256": canonical_sha256(list(block_world_ids)),
                **_count_row(
                    label=label,
                    threshold=threshold,
                    operator=operator,
                    candidate_ids=ids,
                    source_rows=source_rows,
                    individual_counts=counts,
                    event_score_block_counts=(counts > 0).astype(np.uint8),
                    opportunity_world_ids=opportunity_ids,
                    world_count=worlds_per_block,
                    include_lineage=False,
                ),
            })
    world_scope = [
        world_ids[ordinal * worlds_per_block + index]
        for ordinal in block_ordinals for index in range(worlds_per_block)
    ]
    thresholds = []
    for (label, threshold, operator), retained in zip(
        THRESHOLDS, state, strict=True
    ):
        thresholds.append({
            **_count_row(
                label=label,
                threshold=threshold,
                operator=operator,
                candidate_ids=ids,
                source_rows=source_rows,
                individual_counts=retained["individual_counts"],
                event_score_block_counts=retained[
                    "event_score_block_counts"
                ],
                opportunity_world_ids=retained["opportunity_world_ids"],
                world_count=len(world_scope),
                include_lineage=True,
            ),
            "by_block": retained["by_block"],
        })
    body = {
        "schema_version": METRIC_SCHEMA,
        "blocks": list(blocks),
        "worlds_per_block": worlds_per_block,
        "world_count": len(world_scope),
        "world_ids_sha256": canonical_sha256(world_scope),
        "lineup_count": len(ids),
        "lineup_ids_sha256": canonical_sha256(ids),
        "thresholds": thresholds,
        "ordinary_unweighted_r_worlds": True,
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, "opportunity_metrics_sha256")


def _universe(
    *,
    universe_id: str,
    universe_kind: str,
    parameter_set_id: str | None,
    heldout_block: str | None,
    membership_law: str,
    rows: Sequence[Mapping[str, object]],
    global_index_by_id: Mapping[str, int],
    scores: np.ndarray,
    training_blocks: Sequence[str],
    world_ids: Sequence[Mapping[str, object]],
    worlds_per_block: int,
    fit_candidate_view_sha256: str | None = None,
    selection_provenance_sha256: str | None = None,
    excluded_count: int = 0,
) -> dict[str, object]:
    candidate_ids = [str(row["lineup_id"]) for row in rows]
    indices = np.asarray(
        [global_index_by_id[lineup_id] for lineup_id in candidate_ids],
        dtype=np.int64,
    )
    training_metrics = _opportunity_metrics(
        scores,
        candidate_indices=indices,
        candidate_ids=candidate_ids,
        source_rows=rows,
        blocks=training_blocks,
        world_ids=world_ids,
        worlds_per_block=worlds_per_block,
    )
    body = {
        "schema_version": UNIVERSE_SCHEMA,
        "universe_id": universe_id,
        "universe_kind": universe_kind,
        "parameter_set_id": parameter_set_id,
        "heldout_block": heldout_block,
        "training_blocks": list(training_blocks),
        "membership_law": membership_law,
        "lineup_count": len(candidate_ids),
        "lineup_ids_sha256": canonical_sha256(candidate_ids),
        "heldout_only_excluded_lineup_count": excluded_count,
        "fit_candidate_view_sha256": fit_candidate_view_sha256,
        "selection_provenance_sha256": selection_provenance_sha256,
        "source_support": _source_support(rows),
        "training_metrics": training_metrics,
        "heldout_metrics_descriptive": (
            None if heldout_block is None else _opportunity_metrics(
                scores,
                candidate_indices=indices,
                candidate_ids=candidate_ids,
                source_rows=rows,
                blocks=[heldout_block],
                world_ids=world_ids,
                worlds_per_block=worlds_per_block,
            )
        ),
        "uses_realized_outcomes": False,
        "analytical_authority": False,
        "promotion_authority": False,
    }
    return _self_hash(body, "universe_sha256")


def _threshold(metrics: Mapping[str, object], label: str) -> Mapping[str, object]:
    matches = [
        _mapping(value, label="threshold metric")
        for value in _sequence(metrics["thresholds"], label="threshold metrics")
        if _mapping(value, label="threshold metric").get("label") == label
    ]
    if len(matches) != 1:
        _fail(f"threshold metric {label!r} differs")
    return matches[0]


def build_extreme_tail_support_census(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    world_ids: Sequence[Mapping[str, object]],
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Build seven all-block arms, five fold-safe unions, and one full union."""
    _validate_source_arm_order()
    if worlds_per_block is None:
        worlds_per_block = rw.WORLDS_PER_BLOCK
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    scores = np.asarray(union_scores)
    try:
        candidates = runner._validate_provenance(provenance)
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusExtremeTailCensusError(str(exc)) from exc
    expected_shape = (
        len(candidates), len(rw.WORLD_BLOCKS) * worlds_per_block
    )
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or scores.shape != expected_shape
        or not scores.flags.c_contiguous
    ):
        _fail(
            "canonical union scores must be exact-shape native float64 and "
            "C-contiguous before reconstruction replay"
        )
    try:
        reconstruction_sha256 = runner._validate_reconstruction_input(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=reconstruction_receipt,
        )
        dose_authority = runner._dose_authority(
            provenance=provenance,
            admission_m=runner.DEFAULT_ADMISSION_M,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusExtremeTailCensusError(str(exc)) from exc
    for row_start in range(0, scores.shape[0], _CANDIDATE_CHUNK_ROWS):
        row_stop = min(row_start + _CANDIDATE_CHUNK_ROWS, scores.shape[0])
        if not np.isfinite(scores[row_start:row_stop]).all():
            _fail("canonical union score matrix contains a non-finite value")
    normalized_world_ids = _validate_world_ids(
        world_ids,
        reconstruction_receipt=reconstruction_receipt,
        worlds_per_block=worlds_per_block,
    )
    candidate_by_id = {str(row["lineup_id"]): row for row in candidates}
    global_index_by_id = {
        str(row["lineup_id"]): index for index, row in enumerate(candidates)
    }
    all_block_rows = [
        _training_lineage_row(row, training_blocks=rw.WORLD_BLOCKS)
        for row in candidates
    ]
    verified_unique_count_by_arm = _validate_arm_membership_and_authoritative_dose(
        candidates=candidates,
        provenance=provenance,
        reconstruction_receipt=reconstruction_receipt,
        require_authoritative=require_authoritative,
    )
    universes: list[dict[str, object]] = []
    for arm in PARAMETER_SET_ORDER:
        arm_rows = [
            row for row in all_block_rows if arm in row["training_source_arms"]
        ]
        if len(arm_rows) != verified_unique_count_by_arm[arm]:
            _fail(f"source arm {arm!r} verified membership replay differs")
        universes.append(_universe(
            universe_id=f"source-arm-all-block:{arm}",
            universe_kind="source-arm-all-block",
            parameter_set_id=arm,
            heldout_block=None,
            membership_law="any-all-block-provenance-occurrence-from-source-arm",
            rows=arm_rows,
            global_index_by_id=global_index_by_id,
            scores=scores,
            training_blocks=rw.WORLD_BLOCKS,
            world_ids=normalized_world_ids,
            worlds_per_block=worlds_per_block,
        ))
    fold_universes: list[dict[str, object]] = []
    for heldout in rw.WORLD_BLOCKS:
        try:
            view = runner.build_fit_candidate_view(
                provenance,
                heldout_block=heldout,
                dose_authority=dose_authority,
            )
        except runner.CorpusBatchRetrievalV2Error as exc:
            raise CorpusExtremeTailCensusError(str(exc)) from exc
        view_rows = [
            _mapping(value, label="fold-eligible candidate")
            for value in _sequence(
                view["eligible_candidates"], label="fold-eligible candidates"
            )
        ]
        fold_rows = [
            _training_lineage_row(
                candidate_by_id[str(row["lineup_id"])],
                training_blocks=view["training_blocks"],
            )
            for row in view_rows
        ]
        fold = _universe(
            universe_id=f"cross-arm-fold-eligible:holdout-{heldout}",
            universe_kind="cross-arm-fold-eligible",
            parameter_set_id=None,
            heldout_block=heldout,
            membership_law=(
                "cross-arm-union-with-heldout-only-origins-and-heldout-"
                "occurrences-removed-before-selection"
            ),
            rows=fold_rows,
            global_index_by_id=global_index_by_id,
            scores=scores,
            training_blocks=view["training_blocks"],
            world_ids=normalized_world_ids,
            worlds_per_block=worlds_per_block,
            fit_candidate_view_sha256=str(view["fit_candidate_view_sha256"]),
            selection_provenance_sha256=str(view["selection_provenance_sha256"]),
            excluded_count=int(view["excluded_count"]),
        )
        universes.append(fold)
        fold_universes.append(fold)
    universes.append(_universe(
        universe_id="cross-arm-all-block-union",
        universe_kind="cross-arm-all-block-union",
        parameter_set_id=None,
        heldout_block=None,
        membership_law="canonical-deduplicated-cross-arm-all-block-union",
        rows=all_block_rows,
        global_index_by_id=global_index_by_id,
        scores=scores,
        training_blocks=rw.WORLD_BLOCKS,
        world_ids=normalized_world_ids,
        worlds_per_block=worlds_per_block,
    ))
    expected_universe_contract = [
        (
            f"source-arm-all-block:{arm}",
            "source-arm-all-block",
            arm,
            None,
        )
        for arm in PARAMETER_SET_ORDER
    ] + [
        (
            f"cross-arm-fold-eligible:holdout-{block}",
            "cross-arm-fold-eligible",
            None,
            block,
        )
        for block in rw.WORLD_BLOCKS
    ] + [
        (
            "cross-arm-all-block-union",
            "cross-arm-all-block-union",
            None,
            None,
        )
    ]
    actual_universe_contract = [
        (
            universe.get("universe_id"),
            universe.get("universe_kind"),
            universe.get("parameter_set_id"),
            universe.get("heldout_block"),
        )
        for universe in universes
    ]
    if (
        actual_universe_contract != expected_universe_contract
        or len({row[0] for row in actual_universe_contract}) != 13
    ):
        _fail("exact thirteen-universe identity/kind/order law differs")
    gate_observations = []
    for fold in fold_universes:
        ge_230 = _threshold(fold["training_metrics"], "ge_230")
        by_block = [
            _mapping(value, label="ge-230 block metric")
            for value in _sequence(ge_230["by_block"], label="ge-230 blocks")
        ]
        every_block_nonzero = all(
            int(row["opportunity_world_count"]) > 0 for row in by_block
        )
        opportunity_count = int(ge_230["opportunity_world_count"])
        gate_observations.append({
            "heldout_block": fold["heldout_block"],
            "training_blocks": fold["training_blocks"],
            "every_training_block_nonzero": every_block_nonzero,
            "training_opportunity_world_count": opportunity_count,
            "nomination_support_passed": (
                every_block_nonzero
                and opportunity_count
                >= LITERAL_230_MIN_TRAINING_OPPORTUNITY_WORLDS
            ),
        })
    receipt = _mapping(reconstruction_receipt, label="reconstruction receipt")
    binding = _mapping(receipt["matrix_binding"], label="matrix binding")
    body = {
        "schema_version": CENSUS_SCHEMA,
        "census_law_id": CENSUS_LAW_ID,
        "slate": provenance["slate"],
        "input_binding": {
            "reconstruction_sha256": reconstruction_sha256,
            "candidate_provenance_sha256": provenance[
                "candidate_provenance_sha256"
            ],
            "matrix_binding_sha256": binding["matrix_binding_sha256"],
            "score_matrix_sha256": binding["score_matrix_sha256"],
            "lineup_ids_sha256": binding["lineup_ids_sha256"],
            "world_ids_sha256": binding["world_ids_sha256"],
            "score_shape": binding["shape"],
        },
        "world_basis": {
            "blocks": list(rw.WORLD_BLOCKS),
            "worlds_per_block": worlds_per_block,
            "world_count": len(normalized_world_ids),
            "ordinary_unweighted_r_worlds": True,
        },
        "threshold_registry": [
            {"threshold_id": label, "score": threshold, "operator": operator}
            for label, threshold, operator in THRESHOLDS
        ],
        "source_arm_order": list(SOURCE_ARM_ORDER),
        "source_arm_order_sha256": SOURCE_ARM_ORDER_SHA256,
        "universe_order_law": (
            "seven-source-arms-parameter-order-then-five-heldout-blocks-"
            "then-cross-arm-all-block-union"
        ),
        "universe_count": len(universes),
        "universes": universes,
        "coverage_ge_230_support_gate": {
            "role": "support-observation-not-selector-or-promotion-authority",
            "requires_every_training_block_nonzero": True,
            "minimum_training_opportunity_world_count": (
                LITERAL_230_MIN_TRAINING_OPPORTUNITY_WORLDS
            ),
            "failure_role": (
                "literal-230-remains-diagnostic-use-bounded-tail-fallback"
            ),
            "fold_observations": gate_observations,
        },
        "dose_authority": dose_authority,
        "require_authoritative": require_authoritative,
        "evidence_class": "outcome-blind-simulated-instrument",
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "automatic_retry_licensed": False,
        "live_policy_access_licensed": False,
        "r6_freeze_authority": False,
        "analytical_authority": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    return _self_hash(body, "support_census_sha256")


def validate_extreme_tail_support_census(
    value: Mapping[str, object],
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    world_ids: Sequence[Mapping[str, object]],
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Independently replay the complete census and require byte identity."""
    retained = _mapping(value, label="retained extreme-tail support census")
    expected = build_extreme_tail_support_census(
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
        world_ids=world_ids,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )
    if canonical_json_bytes(retained) != canonical_json_bytes(expected):
        _fail("retained extreme-tail support census canonical replay differs")
    return expected


__all__ = [
    "CENSUS_LAW_ID",
    "CENSUS_SCHEMA",
    "CorpusExtremeTailCensusError",
    "LITERAL_230_MIN_TRAINING_OPPORTUNITY_WORLDS",
    "SOURCE_ARM_ORDER",
    "SOURCE_ARM_ORDER_SHA256",
    "THRESHOLDS",
    "build_extreme_tail_support_census",
    "validate_extreme_tail_support_census",
]
