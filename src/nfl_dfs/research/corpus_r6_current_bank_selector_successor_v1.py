"""Pure grouped native-selector successor for the frozen R6 current bank.

This module is deliberately not connected to a cloud dispatcher.  It accepts
one already-sampled, four-block score matrix and corresponding projection-
shaped candidate rows, performs common preprocessing once, and runs three
predeclared outcome-blind selector laws over that same matrix:

* convex excess expected maximum above 200;
* correlation-aware expected maximum at inclusive 230;
* support-switched event-component scenario tickets.

All three adapters reuse the frozen numerical kernels from their source
modules.  The independent-calibration tail-LCB law is deliberately deferred:
an already-sampled current-bank view cannot prove that its membership and
equal-count sample were formed without the internal calibration block.

No realized outcome, held-out score column, object-store reader, graph client,
or production mutation capability is accepted by any public function here.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_extreme_tail_preweek_additions as convex_source,
)
from nfl_dfs.research import (
    corpus_extreme_tail_roadmap_retrieval as roadmap_source,
)
from nfl_dfs.research import (
    corpus_extreme_tail_scenario_ticket as scenario_source,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as current_contract,
)


RESULT_SCHEMA: Final = "corpus-r6-current-bank-selector-successor-result/v1"
IMPLEMENTATION_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-implementation/v1"
)
PRESET_SCHEMA: Final = "corpus-r6-current-bank-selector-successor-preset/v1"
IMPLEMENTATION_ID: Final = "grouped-three-native-current-bank-selectors-v1"
EXPECTED_IMPLEMENTATION_SHA256: Final = (
    "f32c07afd2a75d56a119b23135e5e8f3300575158bf3be0d731bd4ea7ed0fef4"
)
EXPECTED_PRESET_REGISTRY_SHA256: Final = (
    "c73065043d5381967957526074adfc046bf19f9208441f1552f6f9d2aaaf66b4"
)
ENTRY_BUDGET: Final = 80
PREFIX_SIZES: Final = (4, 14, 80)
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
FIT_BLOCK_COUNT: Final = 4
MAX_CANDIDATES: Final = 250
ROSTER_SIZE: Final = 9
PACKED_BITORDER: Final = "little"
CANDIDATE_CHUNK_ROWS: Final = 64
INCLUSIVE_TAIL_THRESHOLDS: Final = (210.0, 220.0, 230.0, 240.0, 250.0)
SCENARIO_FALLBACK_WEIGHTS: Final = (1, 2, 4, 8, 16)

_CANDIDATE_FIELDS: Final = frozenset({
    "lineup_id",
    "roster_player_ids",
    "training_origin_blocks",
    "training_source_arms",
    "training_occurrence_counts_by_block",
    "training_source_arms_by_block",
    "training_occurrence_count",
})
_IDENTIFIER_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_POPCOUNT: Final = np.asarray(
    [value.bit_count() for value in range(256)], dtype=np.uint8
)
_FALSE_POLICY: Final = {
    "uses_realized_outcomes": False,
    "historical_scoring_performed": False,
    "historical_scoring_licensed": False,
    "heldout_score_columns_present": False,
    "heldout_artifact_identity_present": False,
    "corpus_regeneration_performed": False,
    "graph_mutation_performed": False,
    "production_change_performed": False,
    "promotion_authority": False,
    "decision_authority": False,
    "publication_authority": False,
}


class CorpusR6CurrentBankSelectorSuccessorV1Error(ValueError):
    """The grouped current-bank selector successor cannot execute exactly."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectorSuccessorV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return current_contract.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorV1Error(
            "value is not canonical finite JSON"
        ) from exc


def _sha(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(body)
    if field in result:
        _fail(f"{field} cannot already be present")
    result[field] = _sha(result)
    return result


def _array_sha(
    value: np.ndarray, *, label: str, dtype: str | np.dtype[object]
) -> str:
    array = np.ascontiguousarray(value, dtype=dtype)
    digest = sha256()
    digest.update(_canonical({
        "label": label,
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "row_order": "ascending-lineup-id",
    }))
    digest.update(b"\0")
    digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def _matrix_sha(value: np.ndarray) -> str:
    # Input validation requires C-contiguous native float64, so this view does
    # not materialize a second score matrix.
    digest = sha256()
    digest.update(_canonical({
        "label": "sampled-four-block-score-matrix",
        "dtype": "float64-le",
        "shape": list(value.shape),
        "row_order": "ascending-lineup-id",
        "column_order": "training-block-registry-then-world-ordinal",
    }))
    digest.update(b"\0")
    little = value.dtype.byteorder in {"<", "="} and np.little_endian
    if not little:
        _fail("score matrix must use native little-endian float64")
    digest.update(memoryview(value).cast("B"))
    return digest.hexdigest()


def _require_identifier(value: object, *, label: str, maximum: int = 96) -> str:
    if (
        type(value) is not str
        or not value
        or len(value.encode("utf-8")) > maximum
        or _IDENTIFIER_RE.fullmatch(value) is None
    ):
        _fail(f"{label} must be one bounded canonical identifier")
    return value


def _require_string_array(
    value: object, *, label: str, maximum: int = 96
) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    rows = [
        _require_identifier(item, label=f"{label} item", maximum=maximum)
        for item in value
    ]
    return rows


def _upstream_snapshot_v1() -> dict[str, object]:
    """Reopen every frozen upstream semantic contract and fail on drift."""
    try:
        convex_implementation = (
            convex_source.frozen_preweek_additions_implementation_v1()
        )
        convex_registry = convex_source.frozen_preweek_additions_registry_v1()
        roadmap_implementation = (
            roadmap_source.frozen_roadmap_retrieval_implementation_v1()
        )
        roadmap_registry = roadmap_source.frozen_roadmap_retrieval_registry_v1()
        scenario_contract = scenario_source.frozen_scenario_ticket_contract_v1()
    except (
        convex_source.CorpusExtremeTailPreweekAdditionsError,
        roadmap_source.CorpusExtremeTailRoadmapRetrievalError,
        scenario_source.CorpusExtremeTailScenarioTicketError,
    ) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorV1Error(
            f"frozen upstream selector contract drifted: {exc}"
        ) from exc
    if (
        len(convex_registry) != 3
        or convex_registry[0].get("strategy_id")
        != "convex-excess-expected-max-ge-200-v1"
        or len(roadmap_registry) != 2
        or roadmap_registry[0].get("strategy_id") != "tail-lcb-ge-230-v1"
        or roadmap_registry[1].get("strategy_id")
        != "correlation-aware-expected-max-ge-230-v1"
        or scenario_contract.get("strategy_id")
        != "support-switched-event-component-tickets-ge-230-v1"
        or scenario_contract.get("entry_budgets") != list(PREFIX_SIZES)
        or scenario_contract.get("ranking_depth") != ENTRY_BUDGET
        or tuple(scenario_source.FALLBACK_RUNGS)
        != tuple(
            zip(
                INCLUSIVE_TAIL_THRESHOLDS,
                (">=",) * len(INCLUSIVE_TAIL_THRESHOLDS),
                SCENARIO_FALLBACK_WEIGHTS,
                strict=True,
            )
        )
    ):
        _fail("upstream native selector identities differ")
    return {
        "convex_implementation": convex_implementation,
        "convex_strategy": convex_registry[0],
        "roadmap_implementation": roadmap_implementation,
        "correlation_strategy": roadmap_registry[1],
        "scenario_contract": scenario_contract,
    }


def frozen_successor_implementation_v1() -> dict[str, object]:
    """Return the semantic implementation contract, independent of file hash."""
    upstream = _upstream_snapshot_v1()
    body: dict[str, object] = {
        "schema_version": IMPLEMENTATION_SCHEMA,
        "implementation_id": IMPLEMENTATION_ID,
        "input_law": {
            "candidate_count": [ENTRY_BUDGET, MAX_CANDIDATES],
            "candidate_order": "ascending-canonical-lineup-id",
            "score_dtype": "native-little-endian-float64",
            "score_shape": "candidate-count-by-four-times-worlds-per-block",
            "training_block_law": "canonical-r0-r4-order-minus-one-heldout",
            "candidate_provenance": (
                "caller-supplied-projection-shaped-row-local-consistency-only"
            ),
            "production_authority_validated": False,
            "production_authority_wrapper_required": True,
        },
        "shared_preprocessing_law": {
            "no_persistent_full_float64_matrix_clone": True,
            "full_fit_mean_passes": 1,
            "strict_gt_200_count_passes": 1,
            "inclusive_tail_thresholds": list(INCLUSIVE_TAIL_THRESHOLDS),
            "inclusive_mask_builds_per_threshold": 1,
            "block_partition_builds": 1,
            "event_encoding": "numpy-packbits-uint8-little-per-block",
            "dense_candidate_by_world_boolean_retained": False,
        },
        "adapter_order": [
            "native-convex-excess-expected-max-v1",
            "native-correlation-aware-expected-max-v1",
            "native-support-switched-scenario-ticket-v1",
        ],
        "deferred_adapters": [{
            "source_strategy_id": "tail-lcb-ge-230-v1",
            "reason": (
                "rank-only-view-and-equal-count-sample-authority-required-"
                "before-independent-calibration"
            ),
        }],
        "prefix_sizes": list(PREFIX_SIZES),
        "entry_budget": ENTRY_BUDGET,
        "upstream_semantic_bindings": {
            "convex_implementation_sha256": upstream[
                "convex_implementation"
            ]["implementation_sha256"],
            "convex_strategy_sha256": upstream["convex_strategy"][
                "strategy_sha256"
            ],
            "roadmap_implementation_sha256": upstream[
                "roadmap_implementation"
            ]["implementation_sha256"],
            "correlation_strategy_sha256": upstream[
                "correlation_strategy"
            ]["strategy_sha256"],
            "scenario_contract_sha256": upstream["scenario_contract"][
                "contract_sha256"
            ],
        },
        "policy": dict(_FALSE_POLICY),
    }
    result = _with_hash(body, field="implementation_sha256")
    if result["implementation_sha256"] != EXPECTED_IMPLEMENTATION_SHA256:
        _fail("successor semantic implementation contract drifted")
    return result


def _preset(
    *,
    ordinal: int,
    preset_id: str,
    adapter_id: str,
    source_strategy_id: str,
    source_semantics_sha256: str,
    source_implementation_id: str,
    source_implementation_sha256: str,
    parameters: Mapping[str, object],
    old_receipt_parity_claimed: bool,
    successor_implementation_sha256: str,
) -> dict[str, object]:
    parameter_body = deepcopy(dict(parameters))
    body: dict[str, object] = {
        "schema_version": PRESET_SCHEMA,
        "ordinal": ordinal,
        "preset_id": preset_id,
        "adapter_id": adapter_id,
        "source_strategy_id": source_strategy_id,
        "source_semantics_sha256": source_semantics_sha256,
        "source_implementation_id": source_implementation_id,
        "source_implementation_sha256": source_implementation_sha256,
        "entry_budget": ENTRY_BUDGET,
        "prefix_sizes": list(PREFIX_SIZES),
        "parameters": parameter_body,
        "parameters_sha256": _sha(parameter_body),
        "selection_inputs": (
            "caller-supplied-sampled-four-fit-block-simulated-scores-and-"
            "projection-shaped-candidate-rows"
        ),
        "old_receipt_parity_claimed": old_receipt_parity_claimed,
        "successor_implementation_sha256": successor_implementation_sha256,
    }
    body["executable_fingerprint_sha256"] = _sha({
        "adapter_id": adapter_id,
        "entry_budget": ENTRY_BUDGET,
        "parameters": parameter_body,
        "source_semantics_sha256": source_semantics_sha256,
        "source_implementation_sha256": source_implementation_sha256,
        "successor_implementation_sha256": successor_implementation_sha256,
    })
    return _with_hash(body, field="preset_sha256")


def frozen_native_preset_registry_v1() -> list[dict[str, object]]:
    """Return the exact three-challenger registry accepted by this successor."""
    upstream = _upstream_snapshot_v1()
    implementation = frozen_successor_implementation_v1()
    successor_hash = str(implementation["implementation_sha256"])
    convex_strategy = upstream["convex_strategy"]
    roadmap_implementation = upstream["roadmap_implementation"]
    correlation_strategy = upstream["correlation_strategy"]
    scenario_contract = upstream["scenario_contract"]
    registry = [
        _preset(
            ordinal=0,
            preset_id=str(convex_strategy["strategy_id"]),
            adapter_id="native-convex-excess-expected-max-v1",
            source_strategy_id=str(convex_strategy["strategy_id"]),
            source_semantics_sha256=str(convex_strategy["strategy_sha256"]),
            source_implementation_id=str(
                upstream["convex_implementation"]["implementation_id"]
            ),
            source_implementation_sha256=str(
                upstream["convex_implementation"]["implementation_sha256"]
            ),
            parameters=convex_strategy["parameters"],
            old_receipt_parity_claimed=False,
            successor_implementation_sha256=successor_hash,
        ),
        _preset(
            ordinal=1,
            preset_id=str(correlation_strategy["strategy_id"]),
            adapter_id="native-correlation-aware-expected-max-v1",
            source_strategy_id=str(correlation_strategy["strategy_id"]),
            source_semantics_sha256=str(correlation_strategy["strategy_sha256"]),
            source_implementation_id=str(
                roadmap_implementation["implementation_id"]
            ),
            source_implementation_sha256=str(
                roadmap_implementation["implementation_sha256"]
            ),
            parameters=correlation_strategy["parameters"],
            old_receipt_parity_claimed=False,
            successor_implementation_sha256=successor_hash,
        ),
        _preset(
            ordinal=2,
            preset_id=str(scenario_contract["strategy_id"]),
            adapter_id="native-support-switched-scenario-ticket-v1",
            source_strategy_id=str(scenario_contract["strategy_id"]),
            source_semantics_sha256=str(scenario_contract["contract_sha256"]),
            source_implementation_id=str(scenario_contract["implementation_id"]),
            source_implementation_sha256=str(scenario_contract["contract_sha256"]),
            parameters={
                "event_law": scenario_contract["event_law"],
                "component_law": scenario_contract["component_law"],
                "allocation_law": scenario_contract["allocation_law"],
                "support_gate": scenario_contract["support_gate"],
                "fallback": scenario_contract["fallback"],
            },
            old_receipt_parity_claimed=False,
            successor_implementation_sha256=successor_hash,
        ),
    ]
    if _sha(registry) != EXPECTED_PRESET_REGISTRY_SHA256:
        _fail("successor three-native preset registry drifted")
    return registry


def validate_frozen_native_preset_registry_v1(
    value: object,
) -> list[dict[str, object]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("preset registry must be an array")
    expected = frozen_native_preset_registry_v1()
    if _canonical(list(value)) != _canonical(expected):
        _fail("preset registry differs from the frozen three-native registry")
    return expected


def _validated_training_blocks(value: object) -> tuple[tuple[str, ...], str]:
    blocks = _require_string_array(value, label="training blocks")
    if (
        len(blocks) != FIT_BLOCK_COUNT
        or len(set(blocks)) != FIT_BLOCK_COUNT
        or any(block not in WORLD_BLOCKS for block in blocks)
        or blocks != [block for block in WORLD_BLOCKS if block in set(blocks)]
    ):
        _fail("training blocks must be four canonical ordered R blocks")
    heldout = [block for block in WORLD_BLOCKS if block not in blocks]
    if len(heldout) != 1:
        _fail("training blocks do not imply one exact heldout label")
    return tuple(blocks), heldout[0]


def _validated_candidates(
    value: object,
    *,
    sampled_lineup_ids: Sequence[str],
    training_blocks: Sequence[str],
    source_arm_registry: object | None = None,
) -> list[dict[str, object]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("candidate rows must be an array")
    rows = list(value)
    if len(rows) != len(sampled_lineup_ids):
        _fail("candidate row count differs from sampled lineup IDs")
    if source_arm_registry is None:
        known_arms = {
            str(row[1]) for row in current_contract.PROFILE_IDENTITIES
        }
    else:
        declared_arms = _require_string_array(
            source_arm_registry, label="source arm registry"
        )
        if not declared_arms or declared_arms != sorted(set(declared_arms)):
            _fail("source arm registry must be sorted, unique, and nonempty")
        known_arms = set(declared_arms)
    normalized: list[dict[str, object]] = []
    for ordinal, (expected_id, raw) in enumerate(
        zip(sampled_lineup_ids, rows, strict=True)
    ):
        if not isinstance(raw, Mapping) or set(raw) != _CANDIDATE_FIELDS:
            _fail(f"candidate[{ordinal}] fields differ")
        lineup_id = _require_identifier(
            raw["lineup_id"],
            label=f"candidate[{ordinal}] lineup ID",
            maximum=current_contract.MAX_LINEUP_ID_UTF8_BYTES,
        )
        roster = _require_string_array(
            raw["roster_player_ids"],
            label=f"candidate[{ordinal}] roster",
            maximum=current_contract.MAX_PLAYER_ID_UTF8_BYTES,
        )
        origin_blocks = _require_string_array(
            raw["training_origin_blocks"],
            label=f"candidate[{ordinal}] origin blocks",
        )
        source_arms = _require_string_array(
            raw["training_source_arms"],
            label=f"candidate[{ordinal}] source arms",
        )
        counts_raw = raw["training_occurrence_counts_by_block"]
        arms_by_block_raw = raw["training_source_arms_by_block"]
        if (
            not isinstance(counts_raw, Mapping)
            or set(counts_raw) != set(training_blocks)
            or not isinstance(arms_by_block_raw, Mapping)
            or set(arms_by_block_raw) != set(training_blocks)
        ):
            _fail(f"candidate[{ordinal}] block provenance fields differ")
        counts: dict[str, int] = {}
        arms_by_block: dict[str, list[str]] = {}
        for block in training_blocks:
            count = counts_raw[block]
            if type(count) is not int or not 0 <= count <= 2_147_483_647:
                _fail(f"candidate[{ordinal}] occurrence count differs")
            arms = _require_string_array(
                arms_by_block_raw[block],
                label=f"candidate[{ordinal}] {block} source arms",
            )
            if (
                arms != sorted(set(arms))
                or not set(arms) <= known_arms
                or (count == 0) != (arms == [])
            ):
                _fail(f"candidate[{ordinal}] block source arms differ")
            counts[block] = count
            arms_by_block[block] = arms
        occurrence_count = raw["training_occurrence_count"]
        if (
            lineup_id != expected_id
            or len(roster) != ROSTER_SIZE
            or roster != sorted(set(roster))
            or origin_blocks
            != [block for block in training_blocks if counts[block] > 0]
            or source_arms != sorted(set(source_arms))
            or not source_arms
            or not set(source_arms) <= known_arms
            or source_arms
            != sorted({arm for arms in arms_by_block.values() for arm in arms})
            or type(occurrence_count) is not int
            or occurrence_count != sum(counts.values())
            or occurrence_count < 1
        ):
            _fail(f"candidate[{ordinal}] identity/provenance differs")
        normalized.append({
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "training_origin_blocks": origin_blocks,
            "training_source_arms": source_arms,
            "training_occurrence_counts_by_block": counts,
            "training_source_arms_by_block": arms_by_block,
            "training_occurrence_count": occurrence_count,
        })
    if source_arm_registry is not None and {
        arm
        for candidate in normalized
        for arm in candidate["training_source_arms"]
    } != known_arms:
        _fail("candidate source arms do not exactly cover the declared registry")
    return normalized


def _validated_inputs(
    *,
    sampled_lineup_ids: object,
    training_score_matrix: object,
    candidate_rows: object,
    training_blocks: object,
    worlds_per_block: object,
    source_arm_registry: object | None = None,
) -> tuple[
    list[str], np.ndarray, list[dict[str, object]], tuple[str, ...], str, int
]:
    ids = _require_string_array(
        sampled_lineup_ids,
        label="sampled lineup IDs",
        maximum=current_contract.MAX_LINEUP_ID_UTF8_BYTES,
    )
    if (
        not ENTRY_BUDGET <= len(ids) <= MAX_CANDIDATES
        or ids != sorted(set(ids))
    ):
        _fail("sampled lineup IDs must be 80..250 sorted unique IDs")
    blocks, heldout = _validated_training_blocks(training_blocks)
    if (
        type(worlds_per_block) is not int
        or worlds_per_block < 8
        or worlds_per_block % 8 != 0
    ):
        _fail("worlds_per_block must be a positive multiple of eight")
    if not isinstance(training_score_matrix, np.ndarray):
        _fail("training score matrix must be one numpy array")
    scores = np.asarray(training_score_matrix)
    if (
        scores is not training_score_matrix
        or scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or not scores.flags.c_contiguous
        or scores.shape != (len(ids), FIT_BLOCK_COUNT * worlds_per_block)
    ):
        _fail("training score matrix must be exact C-contiguous float64 shape")
    for start in range(0, len(ids), CANDIDATE_CHUNK_ROWS):
        if not np.isfinite(scores[start:start + CANDIDATE_CHUNK_ROWS]).all():
            _fail("training score matrix contains a non-finite value")
    candidates = _validated_candidates(
        candidate_rows,
        sampled_lineup_ids=ids,
        training_blocks=blocks,
        source_arm_registry=source_arm_registry,
    )
    return ids, scores, candidates, blocks, heldout, worlds_per_block


@dataclass(frozen=True, slots=True)
class _SharedPreprocessingV1:
    means: np.ndarray
    strict_gt_200_counts: np.ndarray
    packed_by_threshold: Mapping[float, tuple[np.ndarray, ...]]
    packed_full_230: np.ndarray
    inclusive_ge_230_counts: np.ndarray
    diagnostics: Mapping[str, object]


def _build_shared_preprocessing_v1(
    *,
    scores: np.ndarray,
    training_blocks: Sequence[str],
    worlds_per_block: int,
) -> _SharedPreprocessingV1:
    """Build all common summaries once without copying the score matrix."""
    candidate_count = scores.shape[0]
    packed_width = worlds_per_block // 8
    means = np.empty(candidate_count, dtype=np.float64)
    strict_counts = np.empty(candidate_count, dtype=np.int64)
    packed_mutable: dict[float, list[np.ndarray]] = {
        threshold: [
            np.empty((candidate_count, packed_width), dtype=np.uint8)
            for _ in training_blocks
        ]
        for threshold in INCLUSIVE_TAIL_THRESHOLDS
    }
    for start in range(0, candidate_count, CANDIDATE_CHUNK_ROWS):
        stop = min(start + CANDIDATE_CHUNK_ROWS, candidate_count)
        chunk = scores[start:stop]
        means[start:stop] = chunk.mean(axis=1, dtype=np.float64)
        strict_counts[start:stop] = np.count_nonzero(chunk > 200.0, axis=1)
        for block_ordinal, _block in enumerate(training_blocks):
            column_start = block_ordinal * worlds_per_block
            column_stop = column_start + worlds_per_block
            block_scores = chunk[:, column_start:column_stop]
            for threshold in INCLUSIVE_TAIL_THRESHOLDS:
                packed_mutable[threshold][block_ordinal][start:stop] = (
                    np.packbits(
                        block_scores >= np.float32(threshold),
                        axis=1,
                        bitorder=PACKED_BITORDER,
                    )
                )
    packed = {
        threshold: tuple(by_block)
        for threshold, by_block in packed_mutable.items()
    }
    packed_230 = packed[230.0]
    packed_full_230 = np.ascontiguousarray(
        np.concatenate(packed_230, axis=1), dtype=np.uint8
    )
    inclusive_counts = sum(
        (_POPCOUNT[value].sum(axis=1, dtype=np.int64) for value in packed_230),
        start=np.zeros(candidate_count, dtype=np.int64),
    )
    threshold_hashes = {
        str(int(threshold)): _sha({
            "threshold": threshold,
            "operator": ">=",
            "training_blocks": list(training_blocks),
            "worlds_per_block": worlds_per_block,
            "block_sha256s": [
                _array_sha(
                    value,
                    label=f"inclusive-ge-{int(threshold)}-{block}",
                    dtype=np.uint8,
                )
                for block, value in zip(training_blocks, by_block, strict=True)
            ],
        })
        for threshold, by_block in packed.items()
    }
    diagnostics = {
        "no_persistent_full_float64_matrix_clone": True,
        "shared_preprocessing_build_count": 1,
        "full_fit_mean_pass_count": 1,
        "strict_gt_200_count_pass_count": 1,
        "inclusive_mask_build_count_by_threshold": {
            str(int(threshold)): 1 for threshold in INCLUSIVE_TAIL_THRESHOLDS
        },
        "block_partition_build_count": 1,
        "candidate_chunk_count": (
            candidate_count + CANDIDATE_CHUNK_ROWS - 1
        ) // CANDIDATE_CHUNK_ROWS,
        "block_slices": [
            {
                "block_id": block,
                "column_start": ordinal * worlds_per_block,
                "column_stop": (ordinal + 1) * worlds_per_block,
            }
            for ordinal, block in enumerate(training_blocks)
        ],
        "mean_vector_sha256": _array_sha(
            means, label="full-fit-row-means", dtype="<f8"
        ),
        "strict_gt_200_count_vector_sha256": _array_sha(
            strict_counts, label="strict-gt-200-counts", dtype="<i8"
        ),
        "inclusive_tail_mask_sha256s": threshold_hashes,
        "inclusive_ge_230_count_vector_sha256": _array_sha(
            inclusive_counts, label="inclusive-ge-230-counts", dtype="<i8"
        ),
        "dense_candidate_by_world_boolean_retained": False,
    }
    return _SharedPreprocessingV1(
        means=means,
        strict_gt_200_counts=strict_counts,
        packed_by_threshold=packed,
        packed_full_230=packed_full_230,
        inclusive_ge_230_counts=inclusive_counts,
        diagnostics=diagnostics,
    )


def _fresh_counts_chunk(
    packed: np.ndarray, *, start: int, stop: int, covered: np.ndarray
) -> np.ndarray:
    fresh = np.bitwise_and(packed[start:stop], np.bitwise_not(covered))
    return _POPCOUNT[fresh].sum(axis=1, dtype=np.int64)


def _block_robust_rank_from_shared_v1(
    *,
    shared: _SharedPreprocessingV1,
    lineup_ids: Sequence[str],
    training_blocks: Sequence[str],
    depth: int,
) -> tuple[list[int], list[dict[str, object]]]:
    rung_masks = [
        shared.packed_by_threshold[threshold]
        for threshold in INCLUSIVE_TAIL_THRESHOLDS
    ]
    covered = [
        [np.zeros(mask.shape[1], dtype=np.uint8) for mask in by_block]
        for by_block in rung_masks
    ]
    block_utilities = np.zeros(len(training_blocks), dtype=np.int64)
    remaining = np.ones(len(lineup_ids), dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < depth and np.any(remaining):
        best: int | None = None
        best_added: np.ndarray | None = None
        best_key: tuple[object, ...] | None = None
        for start in range(0, len(lineup_ids), CANDIDATE_CHUNK_ROWS):
            stop = min(start + CANDIDATE_CHUNK_ROWS, len(lineup_ids))
            added = np.zeros((stop - start, len(training_blocks)), dtype=np.int64)
            for weight, by_block, seen_by_block in zip(
                SCENARIO_FALLBACK_WEIGHTS, rung_masks, covered, strict=True
            ):
                for block_ordinal, (mask, seen) in enumerate(
                    zip(by_block, seen_by_block, strict=True)
                ):
                    added[:, block_ordinal] += weight * _fresh_counts_chunk(
                        mask, start=start, stop=stop, covered=seen
                    )
            for offset in range(stop - start):
                candidate = start + offset
                if not remaining[candidate]:
                    continue
                after = block_utilities + added[offset]
                key = (
                    tuple(-int(value) for value in np.sort(after)),
                    -int(shared.strict_gt_200_counts[candidate]),
                    -float(shared.means[candidate]),
                    lineup_ids[candidate],
                )
                if best_key is None or key < best_key:
                    best = candidate
                    best_added = added[offset].copy()
                    best_key = key
        if best is None or best_added is None:
            break
        if not np.any(best_added):
            fill = sorted(
                np.flatnonzero(remaining).tolist(),
                key=lambda candidate: (
                    -int(shared.strict_gt_200_counts[candidate]),
                    -float(shared.means[candidate]),
                    lineup_ids[candidate],
                ),
            )[: depth - len(selected)]
            for candidate in fill:
                selected.append(candidate)
                trace.append({
                    "source_rank": len(selected) - 1,
                    "lineup_id": lineup_ids[candidate],
                    "canonical_lineup_index": candidate,
                    "marginal_utility": 0,
                    "individual_strict_gt_200_count": int(
                        shared.strict_gt_200_counts[candidate]
                    ),
                    "fit_world_mean_score": float(shared.means[candidate]),
                    "leximin_profile_after": [
                        int(value) for value in np.sort(block_utilities)
                    ],
                })
            break
        after = block_utilities + best_added
        selected.append(best)
        trace.append({
            "source_rank": len(selected) - 1,
            "lineup_id": lineup_ids[best],
            "canonical_lineup_index": best,
            "marginal_utility": int(best_added.sum()),
            "individual_strict_gt_200_count": int(
                shared.strict_gt_200_counts[best]
            ),
            "fit_world_mean_score": float(shared.means[best]),
            "leximin_profile_after": [int(value) for value in np.sort(after)],
        })
        block_utilities = after
        for by_block, seen_by_block in zip(rung_masks, covered, strict=True):
            for mask, seen in zip(by_block, seen_by_block, strict=True):
                seen |= mask[best]
        remaining[best] = False
    if len(selected) != depth or len(set(selected)) != depth:
        _fail("shared block-robust fallback did not produce exact rank 80")
    return selected, trace


def _run_convex_v1(
    *, scores: np.ndarray, lineup_ids: Sequence[str], shared: _SharedPreprocessingV1
) -> tuple[list[int], dict[str, object]]:
    source_rows = np.arange(len(lineup_ids), dtype=np.int64)
    try:
        selected, trace = convex_source._select_convex_expected_max(
            scores=scores,
            canonical_source_rows=source_rows,
            lineup_ids=lineup_ids,
            means=shared.means,
            primary_counts=shared.strict_gt_200_counts,
        )
    except convex_source.CorpusExtremeTailPreweekAdditionsError as exc:
        raise CorpusR6CurrentBankSelectorSuccessorV1Error(str(exc)) from exc
    diagnostics = {
        "selection_trace_sha256": _sha(trace),
        "first_marginal_convex_gain": float(
            trace[0]["marginal_mean_convex_excess_expected_max_gain"]
        ),
        "last_marginal_convex_gain": float(
            trace[-1]["marginal_mean_convex_excess_expected_max_gain"]
        ),
    }
    return selected, diagnostics


def _run_correlation_v1(
    *,
    scores: np.ndarray,
    lineup_ids: Sequence[str],
    training_blocks: Sequence[str],
    worlds_per_block: int,
    shared: _SharedPreprocessingV1,
) -> tuple[list[int], dict[str, object]]:
    source_rows = np.arange(len(lineup_ids), dtype=np.int64)
    try:
        selected, trace = roadmap_source._select_correlation_aware_expected_max(
            scores=scores,
            canonical_source_rows=source_rows,
            packed_by_block=shared.packed_by_threshold[230.0],
            training_blocks=training_blocks,
            worlds_per_block=worlds_per_block,
            lineup_ids=lineup_ids,
            means=shared.means,
        )
    except roadmap_source.CorpusExtremeTailRoadmapRetrievalError as exc:
        raise CorpusR6CurrentBankSelectorSuccessorV1Error(str(exc)) from exc
    diagnostics = {
        "selection_trace_sha256": _sha(trace),
        "book_expected_max_after_dk": float(
            trace[-1]["book_expected_max_after_dk"]
        ),
        "book_inclusive_230_union_count_after": int(
            trace[-1]["book_inclusive_230_union_count_after"]
        ),
        "total_redundancy_penalty_dk": float(
            sum(float(row["redundancy_penalty_dk"]) for row in trace)
        ),
    }
    return selected, diagnostics


def _run_scenario_v1(
    *,
    scores: np.ndarray,
    lineup_ids: Sequence[str],
    training_blocks: Sequence[str],
    worlds_per_block: int,
    shared: _SharedPreprocessingV1,
) -> tuple[list[int], dict[str, object]]:
    try:
        scenario_source._assert_frozen_dependency_contract()
        components, owner = scenario_source._event_graph(
            packed=shared.packed_full_230,
            event_counts=shared.inclusive_ge_230_counts,
            lineup_ids=lineup_ids,
            block_count=len(training_blocks),
            worlds_per_block=worlds_per_block,
        )
        gate = scenario_source._support_gate(
            owner=owner,
            blocks=training_blocks,
            worlds_per_block=worlds_per_block,
            scope_kind="cross-fit",
        )
        selected: list[int] = []
        trace: list[dict[str, object]] = []
        if gate["passed"]:
            selected, trace = scenario_source._scenario_rank(
                components=components,
                packed=shared.packed_full_230,
                event_counts=shared.inclusive_ge_230_counts,
                means=shared.means,
                lineup_ids=lineup_ids,
            )
        fallback_start: int | None = None
        fallback_trace: list[dict[str, object]] = []
        if not gate["passed"] or len(selected) < ENTRY_BUDGET:
            fallback_start = len(selected)
            fallback_rank, fallback_trace = _block_robust_rank_from_shared_v1(
                shared=shared,
                lineup_ids=lineup_ids,
                training_blocks=training_blocks,
                depth=ENTRY_BUDGET,
            )
            selected_set = set(selected)
            for source_rank, candidate in enumerate(fallback_rank):
                if candidate in selected_set:
                    continue
                selected.append(candidate)
                selected_set.add(candidate)
                source = fallback_trace[source_rank]
                trace.append({
                    "selection_rank": len(selected) - 1,
                    "lineup_id": lineup_ids[candidate],
                    "canonical_lineup_index": candidate,
                    "selection_source": "block-robust-fallback",
                    "source_fallback_rank": source_rank,
                    "source_marginal_utility": source["marginal_utility"],
                    "source_leximin_profile_after": source[
                        "leximin_profile_after"
                    ],
                })
                if len(selected) == ENTRY_BUDGET:
                    break
        if len(selected) != ENTRY_BUDGET or len(set(selected)) != ENTRY_BUDGET:
            _fail("scenario adapter did not produce exact rank 80")
    except scenario_source.CorpusExtremeTailScenarioTicketError as exc:
        raise CorpusR6CurrentBankSelectorSuccessorV1Error(str(exc)) from exc
    opportunity_counts = [component.q for component in components]
    breadth = Counter(component.breadth for component in components)
    diagnostics = {
        "selection_trace_sha256": _sha(trace),
        "support_gate": gate,
        "selection_mode": (
            "block-robust-fallback-support-failure"
            if not gate["passed"]
            else (
                "scenario-tickets-with-block-robust-exhaustion-suffix"
                if fallback_start is not None
                else "scenario-tickets"
            )
        ),
        "fallback_rank_start": fallback_start,
        "fallback_trace_sha256": _sha(fallback_trace),
        "component_count": len(components),
        "opportunity_world_count": int(sum(opportunity_counts)),
        "largest_component_opportunity_world_count": int(
            max(opportunity_counts, default=0)
        ),
        "component_block_breadth_distribution": [
            {"distinct_fit_block_count": key, "component_count": value}
            for key, value in sorted(breadth.items())
        ],
    }
    return selected, diagnostics


def _common_selected_diagnostics(
    *,
    selected: Sequence[int],
    scores: np.ndarray,
    shared: _SharedPreprocessingV1,
) -> dict[str, object]:
    current_max: np.ndarray | None = None
    covered = np.zeros(shared.packed_full_230.shape[1], dtype=np.uint8)
    for candidate in selected:
        current_max = (
            scores[candidate].copy()
            if current_max is None
            else np.maximum(current_max, scores[candidate])
        )
        covered |= shared.packed_full_230[candidate]
    if current_max is None:
        _fail("selected book cannot be empty")
    return {
        "fit_book_expected_max_dk": float(current_max.mean(dtype=np.float64)),
        "fit_book_inclusive_ge_230_union_count": int(
            _POPCOUNT[covered].sum(dtype=np.int64)
        ),
        "selected_individual_inclusive_ge_230_count_sum": int(
            shared.inclusive_ge_230_counts[
                np.asarray(selected, dtype=np.int64)
            ].sum(dtype=np.int64)
        ),
        "selected_fit_mean_score_mean_dk": float(
            shared.means[np.asarray(selected, dtype=np.int64)].mean(
                dtype=np.float64
            )
        ),
    }


def _prefixes(
    *,
    selected_ids: Sequence[str],
    candidate_by_id: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for size in PREFIX_SIZES:
        ids = list(selected_ids[:size])
        rosters = [
            list(candidate_by_id[lineup_id]["roster_player_ids"])
            for lineup_id in ids
        ]
        rows.append(_with_hash({
            "prefix_size": size,
            "selected_lineup_ids": ids,
            "selected_lineup_ids_sha256": _sha(ids),
            "selected_rosters_sha256": _sha(rosters),
        }, field="prefix_sha256"))
    return rows


def run_grouped_native_selectors_v1(
    *,
    sampled_lineup_ids: object,
    training_score_matrix: object,
    candidate_rows: object,
    training_blocks: object,
    worlds_per_block: object,
    preset_registry: object,
    source_arm_registry: object | None = None,
) -> dict[str, object]:
    """Run four native challengers from one sampled four-block matrix.

    The function is pure with respect to external state.  It does not mutate
    the input matrix or candidate rows and performs no I/O.
    """
    presets = validate_frozen_native_preset_registry_v1(preset_registry)
    (
        lineup_ids,
        scores,
        candidates,
        blocks,
        heldout_block,
        retained_worlds_per_block,
    ) = _validated_inputs(
        sampled_lineup_ids=sampled_lineup_ids,
        training_score_matrix=training_score_matrix,
        candidate_rows=candidate_rows,
        training_blocks=training_blocks,
        worlds_per_block=worlds_per_block,
        source_arm_registry=source_arm_registry,
    )
    matrix_hash = _matrix_sha(scores)
    shared = _build_shared_preprocessing_v1(
        scores=scores,
        training_blocks=blocks,
        worlds_per_block=retained_worlds_per_block,
    )
    candidate_by_id = {
        str(candidate["lineup_id"]): candidate for candidate in candidates
    }
    dispatch = {
        "native-convex-excess-expected-max-v1": lambda: _run_convex_v1(
            scores=scores, lineup_ids=lineup_ids, shared=shared
        ),
        "native-correlation-aware-expected-max-v1": lambda: _run_correlation_v1(
            scores=scores,
            lineup_ids=lineup_ids,
            training_blocks=blocks,
            worlds_per_block=retained_worlds_per_block,
            shared=shared,
        ),
        "native-support-switched-scenario-ticket-v1": lambda: _run_scenario_v1(
            scores=scores,
            lineup_ids=lineup_ids,
            training_blocks=blocks,
            worlds_per_block=retained_worlds_per_block,
            shared=shared,
        ),
    }
    selectors: list[dict[str, object]] = []
    for preset in presets:
        adapter_id = str(preset["adapter_id"])
        if adapter_id not in dispatch:
            _fail("frozen preset adapter is absent from the successor dispatcher")
        selected, adapter_diagnostics = dispatch[adapter_id]()
        if (
            len(selected) != ENTRY_BUDGET
            or len(set(selected)) != ENTRY_BUDGET
            or any(index < 0 or index >= len(lineup_ids) for index in selected)
        ):
            _fail(f"{preset['preset_id']} did not return exact-80 unique rows")
        selected_ids = [lineup_ids[index] for index in selected]
        diagnostics = {
            **adapter_diagnostics,
            **_common_selected_diagnostics(
                selected=selected, scores=scores, shared=shared
            ),
        }
        selectors.append(_with_hash({
            "ordinal": preset["ordinal"],
            "preset_id": preset["preset_id"],
            "preset_sha256": preset["preset_sha256"],
            "adapter_id": adapter_id,
            "parameters_sha256": preset["parameters_sha256"],
            "executable_fingerprint_sha256": preset[
                "executable_fingerprint_sha256"
            ],
            "selected_canonical_indices": [int(index) for index in selected],
            "selected_lineup_ids": selected_ids,
            "selected_lineup_ids_sha256": _sha(selected_ids),
            "selected_rosters_sha256": _sha([
                candidate_by_id[lineup_id]["roster_player_ids"]
                for lineup_id in selected_ids
            ]),
            "prefixes": _prefixes(
                selected_ids=selected_ids, candidate_by_id=candidate_by_id
            ),
            "compact_diagnostics": diagnostics,
            "compact_diagnostics_sha256": _sha(diagnostics),
        }, field="selector_result_sha256"))
    implementation = frozen_successor_implementation_v1()
    input_binding = _with_hash({
        "ordered_sampled_lineup_ids_sha256": _sha(lineup_ids),
        "sampled_candidate_rows_sha256": _sha(candidates),
        "candidate_count": len(lineup_ids),
        "training_blocks": list(blocks),
        "heldout_block_label_only": heldout_block,
        "worlds_per_block": retained_worlds_per_block,
        "training_score_shape": list(scores.shape),
        "training_score_matrix_sha256": matrix_hash,
        "input_score_matrix_object_reused": True,
        "no_persistent_full_float64_matrix_clone": True,
        "score_matrix_mutated": False,
        "heldout_score_columns_present": False,
        "uses_realized_outcomes": False,
        "caller_supplied_inputs_only": True,
        "production_authority_validated": False,
    }, field="input_binding_sha256")
    body: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "implementation": implementation,
        "implementation_sha256": implementation["implementation_sha256"],
        "preset_registry": presets,
        "preset_registry_sha256": _sha(presets),
        "input_binding": input_binding,
        "input_binding_sha256": input_binding["input_binding_sha256"],
        "shared_preprocessing": dict(shared.diagnostics),
        "shared_preprocessing_sha256": _sha(shared.diagnostics),
        "selector_count": len(selectors),
        "selectors": selectors,
        "selector_result_sha256s": [
            selector["selector_result_sha256"] for selector in selectors
        ],
        "entry_budget": ENTRY_BUDGET,
        "prefix_sizes": list(PREFIX_SIZES),
        "policy": dict(_FALSE_POLICY),
    }
    return _with_hash(body, field="result_sha256")


def validate_grouped_native_selector_result_v1(
    value: object,
    *,
    sampled_lineup_ids: object,
    training_score_matrix: object,
    candidate_rows: object,
    training_blocks: object,
    worlds_per_block: object,
    preset_registry: object,
    source_arm_registry: object | None = None,
) -> dict[str, object]:
    """Replay the pure computation and require byte-exact canonical equality."""
    if not isinstance(value, Mapping):
        _fail("successor result must be one mapping")
    try:
        retained = dict(value)
        _canonical(retained)
    except (TypeError, ValueError) as exc:
        raise CorpusR6CurrentBankSelectorSuccessorV1Error(
            "successor result is not canonical finite JSON"
        ) from exc
    expected = run_grouped_native_selectors_v1(
        sampled_lineup_ids=sampled_lineup_ids,
        training_score_matrix=training_score_matrix,
        candidate_rows=candidate_rows,
        training_blocks=training_blocks,
        worlds_per_block=worlds_per_block,
        preset_registry=preset_registry,
        source_arm_registry=source_arm_registry,
    )
    if _canonical(retained) != _canonical(expected):
        _fail("successor result differs from exact pure replay")
    return expected


__all__ = [
    "CorpusR6CurrentBankSelectorSuccessorV1Error",
    "ENTRY_BUDGET",
    "EXPECTED_IMPLEMENTATION_SHA256",
    "EXPECTED_PRESET_REGISTRY_SHA256",
    "IMPLEMENTATION_ID",
    "PREFIX_SIZES",
    "RESULT_SCHEMA",
    "frozen_native_preset_registry_v1",
    "frozen_successor_implementation_v1",
    "run_grouped_native_selectors_v1",
    "validate_frozen_native_preset_registry_v1",
    "validate_grouped_native_selector_result_v1",
]
