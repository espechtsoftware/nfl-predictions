"""Pure pre-Week-1 selector mechanisms over one frozen fit matrix.

This module adds the three inexpensive selector mechanisms frozen after the
population matrices were specified:

* complete-union inclusive-194 marginal coverage;
* individual training-world maximum rank; and
* inclusive-230 training-hit admission followed by the frozen T230 support
  switch on that exact admitted subset.

Inputs are normalized to ascending lineup ID before hashing or selection, so
an equivalent row permutation cannot change the receipt.  Event matrices are
bit-packed and score scans are chunked.  Every result is a false-authority,
canonical, self-hashed artifact that can be rebuilt byte-for-byte from the
same source identities and fit matrix.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as t230
from nfl_dfs.research import corpus_extreme_tail_support_switch as switch
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    canonical_json_bytes,
    canonical_sha256,
)


RECEIPT_SCHEMA: Final = "extreme-tail-preweek-selectors/v1"
INPUT_BINDING_SCHEMA: Final = "extreme-tail-preweek-selector-input/v1"
FIT_SCOPE_BINDING_SCHEMA: Final = "extreme-tail-preweek-fit-scope-binding/v1"
SELECTOR_SCHEMA: Final = "extreme-tail-preweek-selector/v1"
BOOK_SCHEMA: Final = "extreme-tail-preweek-book/v1"
ADMISSION_SCHEMA: Final = "extreme-tail-preweek-admission/v1"
RAW_RANKING_SCHEMA: Final = "extreme-tail-preweek-raw-subset-ranking/v1"
RAW_BOOK_SCHEMA: Final = "extreme-tail-preweek-raw-subset-book/v1"
SUPPORT_PROJECTION_SCHEMA: Final = "extreme-tail-preweek-support-projection/v1"
STRATEGY_SCHEMA: Final = "extreme-tail-preweek-strategy/v1"
IMPLEMENTATION_SCHEMA: Final = "extreme-tail-preweek-implementation/v1"
IMPLEMENTATION_ID: Final = "packed-chunked-preweek-selectors-v1"
RECEIPT_LAW_ID: Final = "frozen-preweek-historical-selector-catalog/v1"

ENTRY_BUDGETS: Final = (4, 14, 80)
RANKING_DEPTH: Final = 80
_CANDIDATE_CHUNK_ROWS: Final = 64
_PACKED_BITORDER: Final = "little"
_WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
_PRODUCTION_WORLDS_PER_BLOCK: Final = 10_000
_TAIL_RUNGS: Final = (
    (210.0, ">=", 1),
    (220.0, ">=", 2),
    (230.0, ">=", 4),
    (240.0, ">=", 8),
    (250.0, ">=", 16),
)
_FOLD_MINIMUM_OPPORTUNITY_WORLDS: Final = 100
_FINAL_MINIMUM_OPPORTUNITY_WORLDS: Final = 125
_LITERAL_COVERAGE_STRATEGY_ID: Final = "coverage-ge-230-v1"
_FALLBACK_STRATEGY_ID: Final = (
    "block-robust-bounded-tail-ge-210-250-v1"
)
_UPSTREAM_IMPLEMENTATION_ID: Final = (
    "packed-chunked-exact-t230-selectors-v1"
)
_UPSTREAM_IMPLEMENTATION_SHA256: Final = (
    "0ede95f034186bdf382af8a9c87c311b83799c5e9609ec11d2cffb3c2114ce4b"
)
_UPSTREAM_STRATEGY_HASHES: Final = {
    "coverage-ge-230-v1": (
        "c43598db8dc2b081158f0660f8edc1ccae4ce1c58ff6a468036c6dbc089fa965"
    ),
    "bounded-tail-ladder-ge-210-250-v1": (
        "e769cadb1a3189d736784225647d9a7342ab4ea25bd2b55f632dd0ec8de254fa"
    ),
    "block-robust-bounded-tail-ge-210-250-v1": (
        "b3c4bf6ea5e09446e0fff6b901412c7e9370a1b0e1ac0053d864eaef36f958d9"
    ),
    "individual-ge-230-rank-v1": (
        "d267f5401fd234ba962d6d350d4dac2716a8e3c9e789a2e7c8a91a79cd9a1aee"
    ),
}
_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
    "publication_authority",
    "panel_membership_authority",
    "source_replay_authority",
    "realized_grade_open_authority",
)
_POPCOUNT: Final = np.asarray(
    [value.bit_count() for value in range(256)], dtype=np.uint8
)


class CorpusExtremeTailPreweekSelectorsError(ValueError):
    """A pre-Week-1 selector receipt violates its frozen contract."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailPreweekSelectorsError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _sha(value: object, *, label: str) -> str:
    try:
        return canonical_sha256(value)
    except (TypeError, ValueError) as exc:
        raise CorpusExtremeTailPreweekSelectorsError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return canonical_json_bytes(value)
    except (TypeError, ValueError) as exc:
        raise CorpusExtremeTailPreweekSelectorsError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = _sha(result, label=field)
    return result


def _require_sha256(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: set[str], *, label: str
) -> None:
    if set(value) != expected:
        _fail(f"{label} fields differ")


def _nonempty_string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be one nonempty exact string")
    return value


def _object_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, {"uri", "generation", "sha256", "bytes"}, label=label)
    uri = _nonempty_string(item.get("uri"), label=f"{label} URI")
    generation = _nonempty_string(
        item.get("generation"), label=f"{label} generation"
    )
    byte_count = item.get("bytes")
    if (
        not uri.startswith("gs://")
        or not generation.isdigit()
        or type(byte_count) is not int
        or byte_count < 1
    ):
        _fail(f"{label} content identity differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _require_sha256(
            item.get("sha256"), label=f"{label} content hash"
        ),
        "bytes": byte_count,
    }


def _source_manifest_identity(value: object) -> dict[str, object]:
    item = _mapping(value, label="source manifest identity")
    _exact_keys(
        item,
        {"manifest_id", "manifest_sha256", "object_identity"},
        label="source manifest identity",
    )
    return {
        "manifest_id": _nonempty_string(
            item.get("manifest_id"), label="source manifest ID"
        ),
        "manifest_sha256": _require_sha256(
            item.get("manifest_sha256"), label="source manifest hash"
        ),
        "object_identity": _object_identity(
            item.get("object_identity"), label="source manifest object"
        ),
    }


def _source_member_identity(value: object) -> dict[str, object]:
    item = _mapping(value, label="source member identity")
    _exact_keys(
        item,
        {"member_id", "member_ordinal", "member_sha256", "slate_id"},
        label="source member identity",
    )
    ordinal = item.get("member_ordinal")
    if type(ordinal) is not int or ordinal < 0:
        _fail("source member ordinal must be a nonnegative exact integer")
    return {
        "member_id": _nonempty_string(
            item.get("member_id"), label="source member ID"
        ),
        "member_ordinal": ordinal,
        "member_sha256": _require_sha256(
            item.get("member_sha256"), label="source member hash"
        ),
        "slate_id": _nonempty_string(
            item.get("slate_id"), label="source member slate ID"
        ),
    }


def _source_score_matrix_identity(value: object) -> dict[str, object]:
    item = _mapping(value, label="source score-matrix identity")
    _exact_keys(
        item,
        {"matrix_id", "matrix_sha256", "object_identity"},
        label="source score-matrix identity",
    )
    return {
        "matrix_id": _nonempty_string(
            item.get("matrix_id"), label="source score-matrix ID"
        ),
        "matrix_sha256": _require_sha256(
            item.get("matrix_sha256"), label="source score-matrix hash"
        ),
        "object_identity": _object_identity(
            item.get("object_identity"), label="source score-matrix object"
        ),
    }


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _guard_frozen_upstream_contract() -> dict[str, str]:
    """Fail closed if imported T230 constants drift, even coherently."""
    if (
        tuple(rw.WORLD_BLOCKS) != _WORLD_BLOCKS
        or retrieval.WORLDS_PER_BLOCK != _PRODUCTION_WORLDS_PER_BLOCK
        or tuple(t230.ENTRY_BUDGETS) != ENTRY_BUDGETS
        or t230.RANKING_DEPTH != RANKING_DEPTH
        or tuple(t230.TAIL_RUNGS) != _TAIL_RUNGS
        or switch.FOLD_MINIMUM_OPPORTUNITY_WORLDS
        != _FOLD_MINIMUM_OPPORTUNITY_WORLDS
        or switch.FINAL_MINIMUM_OPPORTUNITY_WORLDS
        != _FINAL_MINIMUM_OPPORTUNITY_WORLDS
        or switch.LITERAL_COVERAGE_STRATEGY_ID
        != _LITERAL_COVERAGE_STRATEGY_ID
        or switch.FALLBACK_STRATEGY_ID != _FALLBACK_STRATEGY_ID
    ):
        _fail("imported frozen T230 constants differ from the local contract")
    implementation = _mapping(
        t230.frozen_selector_implementation_contract_v1(),
        label="upstream selector implementation",
    )
    retained_implementation_hash = _require_sha256(
        implementation.get("selector_implementation_sha256"),
        label="upstream selector implementation hash",
    )
    implementation_remainder = {
        key: value
        for key, value in implementation.items()
        if key != "selector_implementation_sha256"
    }
    if (
        implementation.get("implementation_id")
        != _UPSTREAM_IMPLEMENTATION_ID
        or retained_implementation_hash != _UPSTREAM_IMPLEMENTATION_SHA256
        or _sha(
            implementation_remainder,
            label="upstream selector implementation",
        )
        != _UPSTREAM_IMPLEMENTATION_SHA256
    ):
        _fail("imported frozen T230 implementation identity differs")
    registry = _sequence(
        t230.frozen_extreme_tail_strategies_v1(),
        label="upstream T230 strategy registry",
    )
    if len(registry) != 4:
        _fail("imported frozen T230 strategy registry cardinality differs")
    observed: dict[str, str] = {}
    for raw in registry:
        strategy = _mapping(raw, label="upstream T230 strategy")
        strategy_id = strategy.get("strategy_id")
        strategy_hash = _require_sha256(
            strategy.get("strategy_sha256"),
            label="upstream T230 strategy hash",
        )
        remainder = {
            key: value for key, value in strategy.items() if key != "strategy_sha256"
        }
        if (
            type(strategy_id) is not str
            or strategy_id in observed
            or _sha(remainder, label="upstream T230 strategy") != strategy_hash
        ):
            _fail("imported frozen T230 strategy self-identity differs")
        observed[strategy_id] = strategy_hash
    if observed != _UPSTREAM_STRATEGY_HASHES:
        _fail("imported frozen T230 strategy identities differ")
    return observed


def frozen_preweek_selector_implementation_v1() -> dict[str, object]:
    """Return the exact bounded-memory implementation contract."""
    body = {
        "schema_version": IMPLEMENTATION_SCHEMA,
        "implementation_id": IMPLEMENTATION_ID,
        "candidate_chunk_rows": _CANDIDATE_CHUNK_ROWS,
        "canonical_candidate_order": "ascending-lineup-id",
        "canonical_score_hash": "float64-le-row-chunked-in-canonical-order",
        "event_mask_encoding": "numpy-packbits-uint8",
        "event_mask_bitorder": _PACKED_BITORDER,
        "popcount_law": "exact-frozen-uint8-lookup-v1",
        "r194_zero_gain_law": (
            "continue-by-individual-inclusive-count-mean-and-lineup-id"
        ),
        "support_switch_execution": (
            "materialize-both-raw-subset-ranks-then-project-by-support"
        ),
        "fit_scope_binding_law": (
            "exact-block-membership-lineup-mask-lineage-matrix-manifest-member"
        ),
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "outer_exact_source_replay_required": True,
        "dense_candidate-by-world_boolean_matrix": False,
        "full_score_matrix_copy": False,
        "exact_prefix_law": "one-rank-80-yields-prefixes-4-14-80",
    }
    return _self_hash(body, "implementation_sha256")


def _strategy(
    *,
    ordinal: int,
    selector_id: str,
    method: str,
    parameters: Mapping[str, object],
    tie_law: Sequence[str],
    role: str,
) -> dict[str, object]:
    implementation = frozen_preweek_selector_implementation_v1()
    body = {
        "schema_version": STRATEGY_SCHEMA,
        "ordinal": ordinal,
        "selector_id": selector_id,
        "method": method,
        "parameters": dict(parameters),
        "tie_law": list(tie_law),
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "implementation_id": IMPLEMENTATION_ID,
        "implementation_sha256": implementation["implementation_sha256"],
        "selection_inputs": "fit-scope-simulated-scores-only",
        "role": role,
    }
    return _self_hash(body, "strategy_sha256")


def frozen_preweek_selector_registry_v1() -> list[dict[str, object]]:
    """Return the exact three-mechanism pre-Week-1 registry."""
    return [
        _strategy(
            ordinal=0,
            selector_id="complete-union-inclusive-r194-rank-v1",
            method="greedy-inclusive-threshold-coverage-v1",
            parameters={
                "threshold": 194.0,
                "operator": ">=",
                "candidate_scope": "complete-fit-eligible-union",
            },
            tie_law=[
                "largest-marginal-new-inclusive-194-world-count",
                "largest-individual-inclusive-194-world-count",
                "largest-fit-world-mean-score",
                "ascending-lineup-id",
            ],
            role="factorial-complete-union-r194",
        ),
        _strategy(
            ordinal=1,
            selector_id="individual-training-maximum-rank-v1",
            method="rank-individual-fit-maximum-v1",
            parameters={"candidate_scope": "complete-fit-eligible-union"},
            tie_law=[
                "largest-fit-world-maximum-score",
                "largest-fit-world-mean-score",
                "ascending-lineup-id",
            ],
            role="upper-end-anti-diversification-ablation-not-nominee",
        ),
        _strategy(
            ordinal=2,
            selector_id="training-hit-ge-230-admission-v1",
            method="inclusive-230-admission-then-frozen-support-switch-v1",
            parameters={
                "admission_threshold": 230.0,
                "admission_operator": ">=",
                "minimum_admitted_candidates": 80,
                "fold_minimum_opportunity_worlds": 100,
                "final_minimum_opportunity_worlds": 125,
                "passed_raw_strategy_id": _LITERAL_COVERAGE_STRATEGY_ID,
                "failed_raw_strategy_id": _FALLBACK_STRATEGY_ID,
                "tail_rungs": [
                    {
                        "threshold": threshold,
                        "operator": operator,
                        "weight": weight,
                    }
                    for threshold, operator, weight in _TAIL_RUNGS
                ],
            },
            tie_law=[
                "exact-selected-raw-t230-strategy-tie-law",
                "no-threshold-relaxation-or-borrowing",
            ],
            role="secondary-hard-230-admission-sensitivity",
        ),
    ]


def _validate_blocks(
    training_blocks: Sequence[str], *, worlds_per_block: int
) -> tuple[str, ...]:
    blocks = tuple(_sequence(training_blocks, label="training blocks"))
    if any(type(block) is not str for block in blocks):
        _fail("training block IDs must be exact strings")
    if len(blocks) not in {4, 5}:
        _fail("preweek selectors require exactly four or five training blocks")
    expected = tuple(block for block in _WORLD_BLOCKS if block in set(blocks))
    if blocks != expected or len(set(blocks)) != len(blocks):
        _fail("training blocks must be a canonical R0..R4 subset")
    if type(worlds_per_block) is not int or worlds_per_block < 1:
        _fail("worlds_per_block must be a positive exact integer")
    return blocks


def _scope_identity(
    training_blocks: Sequence[str], *, heldout_block: str | None
) -> tuple[str, str]:
    blocks = tuple(training_blocks)
    if heldout_block is not None and (
        type(heldout_block) is not str or heldout_block not in _WORLD_BLOCKS
    ):
        _fail("heldout block must be null or one literal R0..R4 ID")
    if len(blocks) == 5:
        if heldout_block is not None or blocks != _WORLD_BLOCKS:
            _fail("final fit must contain all five blocks and no heldout ID")
        return "final-fit", "all-block-final-fit"
    expected_heldout = [block for block in _WORLD_BLOCKS if block not in blocks]
    if (
        len(expected_heldout) != 1
        or heldout_block != expected_heldout[0]
        or blocks
        != tuple(block for block in _WORLD_BLOCKS if block != heldout_block)
    ):
        _fail("fold fit must equal the registry minus its exact heldout block")
    return "cross-fit", f"holdout-{heldout_block}"


def _validated_inputs(
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    require_production_width: bool,
) -> tuple[
    list[str],
    np.ndarray,
    np.ndarray,
    tuple[str, ...],
    str,
    str,
]:
    _guard_frozen_upstream_contract()
    if type(require_production_width) is not bool:
        _fail("require_production_width must be an exact boolean")
    if require_production_width and worlds_per_block != _PRODUCTION_WORLDS_PER_BLOCK:
        _fail("production preweek selector width must be exactly 10,000")
    blocks = _validate_blocks(
        training_blocks, worlds_per_block=worlds_per_block
    )
    scope_kind, fit_scope_id = _scope_identity(
        blocks, heldout_block=heldout_block
    )
    raw_ids = list(_sequence(lineup_ids, label="lineup IDs"))
    if (
        len(raw_ids) < RANKING_DEPTH
        or any(type(lineup_id) is not str or not lineup_id for lineup_id in raw_ids)
        or len(set(raw_ids)) != len(raw_ids)
    ):
        _fail("lineup IDs must contain at least 80 unique nonempty strings")
    scores = np.asarray(fit_scores)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or not scores.flags.c_contiguous
        or scores.shape != (len(raw_ids), len(blocks) * worlds_per_block)
    ):
        _fail(
            "fit scores must be exact-shape C-contiguous native float64"
        )
    for start, stop in _candidate_chunks(len(raw_ids)):
        if not np.isfinite(scores[start:stop]).all():
            _fail("fit score matrix contains a non-finite value")
    canonical_source_rows = np.asarray(
        sorted(range(len(raw_ids)), key=raw_ids.__getitem__), dtype=np.int64
    )
    canonical_ids = [raw_ids[int(index)] for index in canonical_source_rows]
    if canonical_ids != sorted(canonical_ids):
        _fail("canonical lineup ordering failed")
    return (
        canonical_ids,
        scores,
        canonical_source_rows,
        blocks,
        scope_kind,
        fit_scope_id,
    )


def _candidate_chunks(row_count: int):
    for start in range(0, row_count, _CANDIDATE_CHUNK_ROWS):
        yield start, min(start + _CANDIDATE_CHUNK_ROWS, row_count)


def _score_rows(
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    start: int,
    stop: int,
    *,
    column_start: int | None = None,
    column_stop: int | None = None,
) -> np.ndarray:
    rows = canonical_source_rows[start:stop]
    if column_start is None:
        result = scores[rows]
    else:
        result = scores[rows, column_start:column_stop]
    return np.ascontiguousarray(result, dtype=np.float64)


def _score_matrix_hash(
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
) -> str:
    header = canonical_json_bytes(
        {"dtype": "float64-le", "shape": [len(canonical_source_rows), scores.shape[1]]}
    )
    digest = sha256()
    digest.update(header)
    digest.update(b"\0")
    for start, stop in _candidate_chunks(len(canonical_source_rows)):
        chunk = np.ascontiguousarray(
            scores[canonical_source_rows[start:stop]], dtype="<f8"
        )
        digest.update(memoryview(chunk).cast("B"))
    return digest.hexdigest()


def _fit_scope_binding_from_validated(
    *,
    canonical_ids: Sequence[str],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    blocks: Sequence[str],
    scope_kind: str,
    fit_scope_id: str,
    heldout_block: str | None,
    worlds_per_block: int,
    candidate_mask_sha256: str,
    occurrence_lineage_sha256: str,
    source_manifest_identity: Mapping[str, object],
    source_member_identity: Mapping[str, object],
    source_score_matrix_identity: Mapping[str, object],
    require_production_width: bool,
) -> dict[str, object]:
    manifest = _source_manifest_identity(source_manifest_identity)
    member = _source_member_identity(source_member_identity)
    source_matrix = _source_score_matrix_identity(source_score_matrix_identity)
    body = {
        "schema_version": FIT_SCOPE_BINDING_SCHEMA,
        "world_block_registry": list(_WORLD_BLOCKS),
        "world_block_registry_sha256": _sha(
            list(_WORLD_BLOCKS), label="world-block registry"
        ),
        "scope_kind": scope_kind,
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout_block,
        "training_blocks": list(blocks),
        "training_blocks_sha256": _sha(
            list(blocks), label="fit-scope training blocks"
        ),
        "fold_block_law": (
            "registry-minus-exact-heldout"
            if scope_kind == "cross-fit"
            else "all-five-registry-blocks"
        ),
        "worlds_per_block": worlds_per_block,
        "ordered_lineup_count": len(canonical_ids),
        "ordered_lineup_ids": list(canonical_ids),
        "ordered_lineup_ids_sha256": _sha(
            list(canonical_ids), label="fit-scope ordered lineup IDs"
        ),
        "candidate_mask_sha256": _require_sha256(
            candidate_mask_sha256, label="candidate mask hash"
        ),
        "occurrence_lineage_sha256": _require_sha256(
            occurrence_lineage_sha256, label="occurrence lineage hash"
        ),
        "score_matrix_binding": {
            "source_score_matrix_identity": source_matrix,
            "canonical_fit_score_matrix_sha256": _score_matrix_hash(
                scores, canonical_source_rows
            ),
            "canonical_fit_score_shape": [
                len(canonical_ids),
                scores.shape[1],
            ],
            "canonical_fit_score_dtype": "float64-le",
            "row_order_law": "ascending-lineup-id",
            "column_order_law": "training-block-major-ordinary-r-world-index",
        },
        "source_manifest_identity": manifest,
        "source_member_identity": member,
        "source_manifest_member_binding_sha256": _sha(
            {"manifest": manifest, "member": member},
            label="source manifest/member binding",
        ),
        "require_production_width": require_production_width,
        "evidence_role": "standalone-diagnostic-nonpublication-only",
        "standalone_source_authority": False,
        "outer_exact_source_replay_required": True,
        "publication_status": "not-publishable-without-outer-source-replay",
        **_false_authorities(),
    }
    return _self_hash(body, "fit_scope_binding_sha256")


def build_extreme_tail_preweek_fit_scope_binding_v1(
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    candidate_mask_sha256: str,
    occurrence_lineage_sha256: str,
    source_manifest_identity: Mapping[str, object],
    source_member_identity: Mapping[str, object],
    source_score_matrix_identity: Mapping[str, object],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Build the exact externally replayed fit-scope binding."""
    (
        canonical_ids,
        scores,
        canonical_source_rows,
        blocks,
        scope_kind,
        fit_scope_id,
    ) = _validated_inputs(
        lineup_ids=lineup_ids,
        fit_scores=fit_scores,
        training_blocks=training_blocks,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        require_production_width=require_production_width,
    )
    return _fit_scope_binding_from_validated(
        canonical_ids=canonical_ids,
        scores=scores,
        canonical_source_rows=canonical_source_rows,
        blocks=blocks,
        scope_kind=scope_kind,
        fit_scope_id=fit_scope_id,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        candidate_mask_sha256=candidate_mask_sha256,
        occurrence_lineage_sha256=occurrence_lineage_sha256,
        source_manifest_identity=source_manifest_identity,
        source_member_identity=source_member_identity,
        source_score_matrix_identity=source_score_matrix_identity,
        require_production_width=require_production_width,
    )


def _row_means(
    scores: np.ndarray, canonical_source_rows: np.ndarray
) -> np.ndarray:
    result = np.empty(len(canonical_source_rows), dtype=np.float64)
    for start, stop in _candidate_chunks(len(canonical_source_rows)):
        result[start:stop] = _score_rows(
            scores, canonical_source_rows, start, stop
        ).mean(axis=1, dtype=np.float64)
    return result


def _row_maxima(
    scores: np.ndarray, canonical_source_rows: np.ndarray
) -> np.ndarray:
    result = np.empty(len(canonical_source_rows), dtype=np.float64)
    for start, stop in _candidate_chunks(len(canonical_source_rows)):
        result[start:stop] = _score_rows(
            scores, canonical_source_rows, start, stop
        ).max(axis=1)
    return result


def _pack_event_mask(
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    *,
    threshold: float,
    operator: str,
    column_start: int = 0,
    column_stop: int | None = None,
) -> np.ndarray:
    if column_stop is None:
        column_stop = scores.shape[1]
    width = column_stop - column_start
    if width < 1:
        _fail("event mask requires at least one score column")
    packed = np.empty(
        (len(canonical_source_rows), (width + 7) // 8), dtype=np.uint8
    )
    bound = np.float32(threshold)
    for start, stop in _candidate_chunks(len(canonical_source_rows)):
        chunk = _score_rows(
            scores,
            canonical_source_rows,
            start,
            stop,
            column_start=column_start,
            column_stop=column_stop,
        )
        if operator == ">=":
            event = chunk >= bound
        elif operator == ">":
            event = chunk > bound
        else:
            _fail(f"unsupported threshold operator {operator!r}")
        packed[start:stop] = np.packbits(
            event, axis=1, bitorder=_PACKED_BITORDER
        )
    return packed


def _packed_row_counts(packed: np.ndarray) -> np.ndarray:
    counts = np.empty(packed.shape[0], dtype=np.int64)
    for start, stop in _candidate_chunks(packed.shape[0]):
        counts[start:stop] = _POPCOUNT[packed[start:stop]].sum(
            axis=1, dtype=np.int64
        )
    return counts


def _fresh_counts(
    packed: np.ndarray,
    uncovered: np.ndarray,
    *,
    start: int,
    stop: int,
) -> np.ndarray:
    return _POPCOUNT[
        np.bitwise_and(packed[start:stop], uncovered)
    ].sum(axis=1, dtype=np.int64)


def _select_coverage(
    *,
    packed: np.ndarray,
    counts: np.ndarray,
    means: np.ndarray,
    lineup_ids: Sequence[str],
    trace_event_field: str,
) -> tuple[list[int], list[dict[str, object]]]:
    covered = np.zeros(packed.shape[1], dtype=np.uint8)
    remaining = np.ones(len(lineup_ids), dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < RANKING_DEPTH and np.any(remaining):
        uncovered = np.bitwise_not(covered)
        best: int | None = None
        best_gain = -1
        best_key: tuple[object, ...] | None = None
        for start, stop in _candidate_chunks(len(lineup_ids)):
            gains = _fresh_counts(packed, uncovered, start=start, stop=stop)
            for offset, raw_gain in enumerate(gains):
                index = start + offset
                if not remaining[index]:
                    continue
                gain = int(raw_gain)
                key = (
                    -gain,
                    -int(counts[index]),
                    -float(means[index]),
                    lineup_ids[index],
                )
                if best_key is None or key < best_key:
                    best = index
                    best_gain = gain
                    best_key = key
        if best is None or best_gain == 0:
            break
        selected.append(best)
        trace.append(
            {
                "selection_rank": len(selected) - 1,
                "canonical_lineup_index": best,
                "lineup_id": lineup_ids[best],
                "marginal_new_world_count": best_gain,
                trace_event_field: int(counts[best]),
                "fit_world_mean_score": float(means[best]),
            }
        )
        covered |= packed[best]
        remaining[best] = False
    fill = sorted(
        (index for index in range(len(lineup_ids)) if remaining[index]),
        key=lambda index: (
            -int(counts[index]),
            -float(means[index]),
            lineup_ids[index],
        ),
    )
    for best in fill[: RANKING_DEPTH - len(selected)]:
        selected.append(best)
        trace.append(
            {
                "selection_rank": len(selected) - 1,
                "canonical_lineup_index": best,
                "lineup_id": lineup_ids[best],
                "marginal_new_world_count": 0,
                trace_event_field: int(counts[best]),
                "fit_world_mean_score": float(means[best]),
            }
        )
    return selected, trace


def _select_training_maximum(
    *,
    maxima: np.ndarray,
    means: np.ndarray,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    selected = sorted(
        range(len(lineup_ids)),
        key=lambda index: (
            -float(maxima[index]),
            -float(means[index]),
            lineup_ids[index],
        ),
    )[:RANKING_DEPTH]
    return selected, [
        {
            "selection_rank": rank,
            "canonical_lineup_index": index,
            "lineup_id": lineup_ids[index],
            "fit_world_maximum_score": float(maxima[index]),
            "fit_world_mean_score": float(means[index]),
        }
        for rank, index in enumerate(selected)
    ]


def _select_block_robust_ladder(
    *,
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    lineup_ids: Sequence[str],
    means: np.ndarray,
    training_blocks: Sequence[str],
    worlds_per_block: int,
) -> tuple[list[int], list[dict[str, object]]]:
    rung_masks = [
        [
            _pack_event_mask(
                scores,
                canonical_source_rows,
                threshold=threshold,
                operator=operator,
                column_start=block_ordinal * worlds_per_block,
                column_stop=(block_ordinal + 1) * worlds_per_block,
            )
            for block_ordinal, _block in enumerate(training_blocks)
        ]
        for threshold, operator, _weight in _TAIL_RUNGS
    ]
    primary_counts = _packed_row_counts(
        _pack_event_mask(
            scores,
            canonical_source_rows,
            threshold=200.0,
            operator=">",
        )
    )
    covered = [
        [np.zeros(mask.shape[1], dtype=np.uint8) for mask in by_block]
        for by_block in rung_masks
    ]
    block_utilities = np.zeros(len(training_blocks), dtype=np.int64)
    remaining = np.ones(len(lineup_ids), dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    weights = [weight for _threshold, _operator, weight in _TAIL_RUNGS]
    while len(selected) < RANKING_DEPTH and np.any(remaining):
        uncovered = [
            [np.bitwise_not(mask) for mask in by_block]
            for by_block in covered
        ]
        best: int | None = None
        best_added: np.ndarray | None = None
        best_key: tuple[object, ...] | None = None
        for start, stop in _candidate_chunks(len(lineup_ids)):
            added = np.zeros(
                (stop - start, len(training_blocks)), dtype=np.int64
            )
            for weight, rung_by_block, uncovered_by_block in zip(
                weights, rung_masks, uncovered, strict=True
            ):
                for block_ordinal, (mask, available) in enumerate(
                    zip(rung_by_block, uncovered_by_block, strict=True)
                ):
                    added[:, block_ordinal] += weight * _fresh_counts(
                        mask, available, start=start, stop=stop
                    )
            for offset in range(stop - start):
                index = start + offset
                if not remaining[index]:
                    continue
                after = block_utilities + added[offset]
                key = (
                    tuple(-int(value) for value in np.sort(after)),
                    -int(primary_counts[index]),
                    -float(means[index]),
                    lineup_ids[index],
                )
                if best_key is None or key < best_key:
                    best = index
                    best_added = added[offset].copy()
                    best_key = key
        if best is None or best_added is None:
            break
        before = block_utilities.copy()
        after = before + best_added
        selected.append(best)
        trace.append(
            {
                "selection_rank": len(selected) - 1,
                "canonical_lineup_index": best,
                "lineup_id": lineup_ids[best],
                "marginal_weighted_utility": int(best_added.sum()),
                "individual_strict_gt_200_world_count": int(
                    primary_counts[best]
                ),
                "fit_world_mean_score": float(means[best]),
                "block_utilities_before": [int(value) for value in before],
                "block_utilities_added": [int(value) for value in best_added],
                "block_utilities_after": [int(value) for value in after],
                "leximin_profile_after": [
                    int(value) for value in np.sort(after)
                ],
            }
        )
        block_utilities = after
        for rung_by_block, seen_by_block in zip(
            rung_masks, covered, strict=True
        ):
            for mask, seen in zip(rung_by_block, seen_by_block, strict=True):
                seen |= mask[best]
        remaining[best] = False
    return selected, trace


def _admission_support_gate(
    *,
    scores: np.ndarray,
    admitted_source_rows: np.ndarray,
    training_blocks: Sequence[str],
    worlds_per_block: int,
) -> dict[str, object]:
    counts: list[dict[str, object]] = []
    for ordinal, block in enumerate(training_blocks):
        packed = _pack_event_mask(
            scores,
            admitted_source_rows,
            threshold=230.0,
            operator=">=",
            column_start=ordinal * worlds_per_block,
            column_stop=(ordinal + 1) * worlds_per_block,
        )
        union = np.bitwise_or.reduce(packed, axis=0)
        count = int(_POPCOUNT[union].sum(dtype=np.int64))
        if count > worlds_per_block:
            _fail("support opportunity count exceeds block width")
        counts.append({"block_id": block, "opportunity_world_count": count})
    minimum = (
        _FOLD_MINIMUM_OPPORTUNITY_WORLDS
        if len(training_blocks) == 4
        else _FINAL_MINIMUM_OPPORTUNITY_WORLDS
    )
    total = sum(int(row["opportunity_world_count"]) for row in counts)
    zero_blocks = [
        str(row["block_id"])
        for row in counts
        if row["opportunity_world_count"] == 0
    ]
    passed = not zero_blocks and total >= minimum
    reasons: list[str] = []
    if zero_blocks:
        reasons.append(
            "one-or-more-training-blocks-have-zero-ge-230-opportunity"
        )
    if total < minimum:
        reasons.append(
            "aggregate-training-ge-230-opportunity-below-frozen-minimum"
        )
    return {
        "threshold": 230.0,
        "operator": ">=",
        "training_blocks": list(training_blocks),
        "per_block_opportunity_world_counts": counts,
        "zero_opportunity_training_blocks": zero_blocks,
        "every_training_block_nonzero": not zero_blocks,
        "training_opportunity_world_count": total,
        "minimum_training_opportunity_world_count": minimum,
        "aggregate_comparison_operator": ">=",
        "passed": passed,
        "failure_reasons": reasons,
    }


def _normalize_admitted_rank(
    *,
    selected_local: Sequence[int],
    local_trace: Sequence[Mapping[str, object]],
    admitted_indices: Sequence[int],
    canonical_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    selected = [int(admitted_indices[index]) for index in selected_local]
    trace: list[dict[str, object]] = []
    for rank, (local_index, canonical_index, raw_trace) in enumerate(
        zip(selected_local, selected, local_trace, strict=True)
    ):
        row = dict(raw_trace)
        if (
            row.get("selection_rank") != rank
            or row.pop("canonical_lineup_index", None) != local_index
            or row.get("lineup_id") != canonical_ids[canonical_index]
        ):
            _fail("raw subset selector local/canonical trace differs")
        row["admitted_lineup_index"] = int(local_index)
        row["canonical_lineup_index"] = canonical_index
        trace.append(row)
    return selected, trace


def _raw_subset_book(
    *,
    raw_strategy_id: str,
    raw_strategy_sha256: str,
    fit_scope_id: str,
    input_binding_sha256: str,
    admission_sha256: str,
    selected: Sequence[int],
    trace: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    entry_budget: int,
) -> dict[str, object]:
    indices = [int(value) for value in selected[:entry_budget]]
    selected_ids = [lineup_ids[index] for index in indices]
    prefix_trace = [dict(row) for row in trace[:entry_budget]]
    if (
        entry_budget not in ENTRY_BUDGETS
        or len(indices) != entry_budget
        or len(set(indices)) != entry_budget
        or len(prefix_trace) != entry_budget
    ):
        _fail("raw subset ranking lacks one exact unique prefix")
    for rank, (index, lineup_id, row) in enumerate(
        zip(indices, selected_ids, prefix_trace, strict=True)
    ):
        if (
            row.get("selection_rank") != rank
            or row.get("canonical_lineup_index") != index
            or row.get("lineup_id") != lineup_id
        ):
            _fail("raw subset book trace identity differs")
    source_rows = canonical_source_rows[np.asarray(indices, dtype=np.int64)]
    body = {
        "schema_version": RAW_BOOK_SCHEMA,
        "raw_book_id": (
            f"{fit_scope_id}:training-hit-ge-230-admission-v1:"
            f"{raw_strategy_id}:exact-{entry_budget}"
        ),
        "fit_scope_id": fit_scope_id,
        "input_binding_sha256": input_binding_sha256,
        "admission_sha256": admission_sha256,
        "raw_strategy_id": raw_strategy_id,
        "raw_strategy_sha256": raw_strategy_sha256,
        "entry_budget": entry_budget,
        "entry_count": entry_budget,
        "ranking_depth": RANKING_DEPTH,
        "selected_canonical_indices": indices,
        "selected_lineup_ids": selected_ids,
        "selected_lineup_ids_sha256": _sha(
            selected_ids, label="raw subset book lineup IDs"
        ),
        "selected_fit_score_matrix_sha256": _score_matrix_hash(
            scores, source_rows
        ),
        "marginal_trace": prefix_trace,
        "marginal_trace_sha256": _sha(
            prefix_trace, label="raw subset book trace"
        ),
        **_false_authorities(),
    }
    return _self_hash(body, "raw_book_sha256")


def _raw_subset_ranking(
    *,
    raw_strategy_id: str,
    raw_strategy_sha256: str,
    fit_scope_id: str,
    input_binding_sha256: str,
    admission: Mapping[str, object],
    selected: Sequence[int],
    trace: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
) -> dict[str, object]:
    if (
        raw_strategy_id not in {
            _LITERAL_COVERAGE_STRATEGY_ID,
            _FALLBACK_STRATEGY_ID,
        }
        or _UPSTREAM_STRATEGY_HASHES[raw_strategy_id] != raw_strategy_sha256
        or len(selected) != RANKING_DEPTH
        or len(set(selected)) != RANKING_DEPTH
        or len(trace) != RANKING_DEPTH
    ):
        _fail("raw subset ranking identity or exact depth differs")
    rank_ids = [lineup_ids[int(index)] for index in selected]
    books = [
        _raw_subset_book(
            raw_strategy_id=raw_strategy_id,
            raw_strategy_sha256=raw_strategy_sha256,
            fit_scope_id=fit_scope_id,
            input_binding_sha256=input_binding_sha256,
            admission_sha256=str(admission["admission_sha256"]),
            selected=selected,
            trace=trace,
            lineup_ids=lineup_ids,
            scores=scores,
            canonical_source_rows=canonical_source_rows,
            entry_budget=budget,
        )
        for budget in ENTRY_BUDGETS
    ]
    body = {
        "schema_version": RAW_RANKING_SCHEMA,
        "raw_ranking_id": (
            f"{fit_scope_id}:training-hit-ge-230-admission-v1:"
            f"{raw_strategy_id}:rank-80"
        ),
        "fit_scope_id": fit_scope_id,
        "input_binding_sha256": input_binding_sha256,
        "admission_sha256": admission["admission_sha256"],
        "admitted_lineup_ids_sha256": admission[
            "admitted_lineup_ids_sha256"
        ],
        "raw_strategy_id": raw_strategy_id,
        "raw_strategy_sha256": raw_strategy_sha256,
        "upstream_selector_implementation_id": _UPSTREAM_IMPLEMENTATION_ID,
        "upstream_selector_implementation_sha256": (
            _UPSTREAM_IMPLEMENTATION_SHA256
        ),
        "ranking_depth": RANKING_DEPTH,
        "rank_80_canonical_indices": [int(value) for value in selected],
        "rank_80_lineup_ids": rank_ids,
        "rank_80_lineup_ids_sha256": _sha(
            rank_ids, label="raw subset rank IDs"
        ),
        "rank_trace": [dict(row) for row in trace],
        "rank_trace_sha256": _sha(trace, label="raw subset rank trace"),
        "entry_budgets": list(ENTRY_BUDGETS),
        "book_count": len(books),
        "books": books,
        "support_gate_was_not_used_to_materialize_this_rank": True,
        **_false_authorities(),
    }
    return _self_hash(body, "raw_ranking_sha256")


def _support_projection(
    *,
    support_gate: Mapping[str, object],
    raw_rankings: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    selected_strategy_id = (
        _LITERAL_COVERAGE_STRATEGY_ID
        if support_gate.get("passed") is True
        else _FALLBACK_STRATEGY_ID
    )
    by_id = {
        str(row["raw_strategy_id"]): row
        for row in raw_rankings
    }
    if set(by_id) != {
        _LITERAL_COVERAGE_STRATEGY_ID,
        _FALLBACK_STRATEGY_ID,
    }:
        _fail("support projection requires both raw subset rankings")
    selected = by_id[selected_strategy_id]
    book_pointers = [
        {
            "entry_budget": book["entry_budget"],
            "raw_book_id": book["raw_book_id"],
            "raw_book_sha256": book["raw_book_sha256"],
        }
        for book in selected["books"]
    ]
    body = {
        "schema_version": SUPPORT_PROJECTION_SCHEMA,
        "selection_law": (
            "support-gate-points-to-one-already-materialized-raw-rank"
        ),
        "support_gate": dict(support_gate),
        "raw_ranking_pointers": [
            {
                "raw_strategy_id": row["raw_strategy_id"],
                "raw_strategy_sha256": row["raw_strategy_sha256"],
                "raw_ranking_id": row["raw_ranking_id"],
                "raw_ranking_sha256": row["raw_ranking_sha256"],
            }
            for row in raw_rankings
        ],
        "selected_raw_strategy_id": selected_strategy_id,
        "selected_raw_strategy_sha256": selected["raw_strategy_sha256"],
        "selected_raw_ranking_id": selected["raw_ranking_id"],
        "selected_raw_ranking_sha256": selected["raw_ranking_sha256"],
        "selected_raw_book_pointers": book_pointers,
        "raw_selectors_recomputed_after_support_gate": False,
        **_false_authorities(),
    }
    return _self_hash(body, "support_projection_sha256")


def _book(
    *,
    selector_id: str,
    strategy_sha256: str,
    fit_scope_id: str,
    input_binding_sha256: str,
    selected: Sequence[int],
    trace: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    entry_budget: int,
    selected_raw_strategy_id: str | None = None,
    selected_raw_strategy_sha256: str | None = None,
    source_raw_book: Mapping[str, object] | None = None,
) -> dict[str, object]:
    indices = [int(value) for value in selected[:entry_budget]]
    if (
        entry_budget not in ENTRY_BUDGETS
        or len(indices) != entry_budget
        or len(set(indices)) != entry_budget
        or any(not 0 <= index < len(lineup_ids) for index in indices)
    ):
        _fail("preweek selector did not produce an exact unique prefix")
    selected_ids = [lineup_ids[index] for index in indices]
    prefix_trace = [dict(row) for row in trace[:entry_budget]]
    if len(prefix_trace) != entry_budget:
        _fail("preweek selector trace cannot replay the exact prefix")
    for rank, (index, lineup_id, row) in enumerate(
        zip(indices, selected_ids, prefix_trace, strict=True)
    ):
        if (
            row.get("selection_rank") != rank
            or row.get("canonical_lineup_index") != index
            or row.get("lineup_id") != lineup_id
        ):
            _fail("preweek selector trace identity differs")
    selected_source_rows = canonical_source_rows[
        np.asarray(indices, dtype=np.int64)
    ]
    source_raw_book_id = None
    source_raw_book_sha256 = None
    if source_raw_book is not None:
        raw_book = _mapping(source_raw_book, label="source raw subset book")
        if (
            raw_book.get("entry_budget") != entry_budget
            or raw_book.get("selected_lineup_ids") != selected_ids
            or raw_book.get("selected_canonical_indices") != indices
            or raw_book.get("raw_strategy_id") != selected_raw_strategy_id
            or raw_book.get("raw_strategy_sha256")
            != selected_raw_strategy_sha256
        ):
            _fail("support projection source raw book differs")
        source_raw_book_id = _nonempty_string(
            raw_book.get("raw_book_id"), label="source raw book ID"
        )
        source_raw_book_sha256 = _require_sha256(
            raw_book.get("raw_book_sha256"), label="source raw book hash"
        )
    body = {
        "schema_version": BOOK_SCHEMA,
        "book_id": f"{fit_scope_id}:{selector_id}:exact-{entry_budget}",
        "fit_scope_id": fit_scope_id,
        "selector_id": selector_id,
        "strategy_sha256": strategy_sha256,
        "selected_raw_strategy_id": selected_raw_strategy_id,
        "selected_raw_strategy_sha256": selected_raw_strategy_sha256,
        "source_raw_subset_book_id": source_raw_book_id,
        "source_raw_subset_book_sha256": source_raw_book_sha256,
        "input_binding_sha256": input_binding_sha256,
        "entry_budget": entry_budget,
        "entry_count": entry_budget,
        "ranking_depth": RANKING_DEPTH,
        "ranking_prefix_law": "exact-prefix-of-one-deterministic-rank-80",
        "selected_canonical_indices": indices,
        "selected_lineup_ids": selected_ids,
        "selected_lineup_ids_sha256": _sha(
            selected_ids, label="selected lineup IDs"
        ),
        "selected_fit_score_matrix_sha256": _score_matrix_hash(
            scores, selected_source_rows
        ),
        "marginal_trace": prefix_trace,
        "marginal_trace_sha256": _sha(prefix_trace, label="marginal trace"),
        **_false_authorities(),
    }
    return _self_hash(body, "book_sha256")


def _selector_receipt(
    *,
    strategy: Mapping[str, object],
    fit_scope_id: str,
    input_binding_sha256: str,
    selected: Sequence[int],
    trace: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    selected_raw_strategy_id: str | None = None,
    selected_raw_strategy_sha256: str | None = None,
    admission: Mapping[str, object] | None = None,
    raw_subset_rankings: Sequence[Mapping[str, object]] = (),
    support_projection: Mapping[str, object] | None = None,
) -> dict[str, object]:
    selector_id = str(strategy["selector_id"])
    strategy_hash = str(strategy["strategy_sha256"])
    if (
        len(selected) != RANKING_DEPTH
        or len(set(selected)) != RANKING_DEPTH
        or len(trace) != RANKING_DEPTH
    ):
        _fail("feasible preweek selector must produce one exact rank 80")
    rank_ids = [lineup_ids[int(index)] for index in selected]
    raw_rankings = [dict(row) for row in raw_subset_rankings]
    source_raw_books: dict[int, Mapping[str, object]] = {}
    if support_projection is not None:
        projection = _mapping(
            support_projection, label="support projection"
        )
        selected_rankings = [
            row
            for row in raw_rankings
            if row.get("raw_ranking_sha256")
            == projection.get("selected_raw_ranking_sha256")
        ]
        if len(selected_rankings) != 1:
            _fail("support projection does not point to one retained raw rank")
        source_raw_books = {
            int(book["entry_budget"]): book
            for book in selected_rankings[0]["books"]
        }
        if set(source_raw_books) != set(ENTRY_BUDGETS):
            _fail("selected raw rank lacks exact 4/14/80 books")
        expected_pointers = [
            {
                "entry_budget": budget,
                "raw_book_id": source_raw_books[budget]["raw_book_id"],
                "raw_book_sha256": source_raw_books[budget]["raw_book_sha256"],
            }
            for budget in ENTRY_BUDGETS
        ]
        if (
            projection.get("selected_raw_strategy_id")
            != selected_raw_strategy_id
            or projection.get("selected_raw_strategy_sha256")
            != selected_raw_strategy_sha256
            or projection.get("selected_raw_book_pointers")
            != expected_pointers
        ):
            _fail("support projection raw-rank/book pointers differ")
    books = [
        _book(
            selector_id=selector_id,
            strategy_sha256=strategy_hash,
            fit_scope_id=fit_scope_id,
            input_binding_sha256=input_binding_sha256,
            selected=selected,
            trace=trace,
            lineup_ids=lineup_ids,
            scores=scores,
            canonical_source_rows=canonical_source_rows,
            entry_budget=budget,
            selected_raw_strategy_id=selected_raw_strategy_id,
            selected_raw_strategy_sha256=selected_raw_strategy_sha256,
            source_raw_book=source_raw_books.get(budget),
        )
        for budget in ENTRY_BUDGETS
    ]
    body = {
        "schema_version": SELECTOR_SCHEMA,
        "fit_scope_id": fit_scope_id,
        "selector_id": selector_id,
        "strategy_sha256": strategy_hash,
        "input_binding_sha256": input_binding_sha256,
        "status": "feasible-exact-rank-80",
        "admission": admission,
        "raw_subset_ranking_count": len(raw_rankings),
        "raw_subset_rankings": raw_rankings,
        "raw_subset_rankings_sha256": _sha(
            [row.get("raw_ranking_sha256") for row in raw_rankings],
            label="raw subset ranking hashes",
        ),
        "support_projection": support_projection,
        "selected_raw_strategy_id": selected_raw_strategy_id,
        "selected_raw_strategy_sha256": selected_raw_strategy_sha256,
        "ranking_depth": RANKING_DEPTH,
        "rank_80_canonical_indices": [int(value) for value in selected],
        "rank_80_lineup_ids": rank_ids,
        "rank_80_lineup_ids_sha256": _sha(rank_ids, label="rank 80 IDs"),
        "rank_trace": [dict(row) for row in trace],
        "rank_trace_sha256": _sha(trace, label="rank trace"),
        "entry_budgets": list(ENTRY_BUDGETS),
        "book_count": len(books),
        "books": books,
        **_false_authorities(),
    }
    return _self_hash(body, "selector_receipt_sha256")


def _infeasible_admission_selector(
    *,
    strategy: Mapping[str, object],
    fit_scope_id: str,
    input_binding_sha256: str,
    admission: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "schema_version": SELECTOR_SCHEMA,
        "fit_scope_id": fit_scope_id,
        "selector_id": strategy["selector_id"],
        "strategy_sha256": strategy["strategy_sha256"],
        "input_binding_sha256": input_binding_sha256,
        "status": "mechanically-infeasible-below-exact-80",
        "admission": admission,
        "raw_subset_ranking_count": 0,
        "raw_subset_rankings": [],
        "raw_subset_rankings_sha256": _sha(
            [], label="empty raw subset ranking hashes"
        ),
        "support_projection": None,
        "selected_raw_strategy_id": None,
        "selected_raw_strategy_sha256": None,
        "ranking_depth": RANKING_DEPTH,
        "rank_80_canonical_indices": [],
        "rank_80_lineup_ids": [],
        "rank_80_lineup_ids_sha256": _sha([], label="empty rank IDs"),
        "rank_trace": [],
        "rank_trace_sha256": _sha([], label="empty rank trace"),
        "entry_budgets": list(ENTRY_BUDGETS),
        "book_count": 0,
        "books": [],
        **_false_authorities(),
    }
    return _self_hash(body, "selector_receipt_sha256")


def run_extreme_tail_preweek_selectors_v1(
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    candidate_mask_sha256: str,
    occurrence_lineage_sha256: str,
    source_manifest_identity: Mapping[str, object],
    source_member_identity: Mapping[str, object],
    source_score_matrix_identity: Mapping[str, object],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Build all three frozen selectors for one fold or final fit scope."""
    (
        canonical_ids,
        scores,
        canonical_source_rows,
        blocks,
        scope_kind,
        fit_scope_id,
    ) = _validated_inputs(
        lineup_ids=lineup_ids,
        fit_scores=fit_scores,
        training_blocks=training_blocks,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        require_production_width=require_production_width,
    )
    implementation = frozen_preweek_selector_implementation_v1()
    registry = frozen_preweek_selector_registry_v1()
    upstream_hashes = _guard_frozen_upstream_contract()
    fit_scope_binding = _fit_scope_binding_from_validated(
        canonical_ids=canonical_ids,
        scores=scores,
        canonical_source_rows=canonical_source_rows,
        blocks=blocks,
        scope_kind=scope_kind,
        fit_scope_id=fit_scope_id,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        candidate_mask_sha256=candidate_mask_sha256,
        occurrence_lineage_sha256=occurrence_lineage_sha256,
        source_manifest_identity=source_manifest_identity,
        source_member_identity=source_member_identity,
        source_score_matrix_identity=source_score_matrix_identity,
        require_production_width=require_production_width,
    )
    input_body = {
        "schema_version": INPUT_BINDING_SCHEMA,
        "fit_scope_id": fit_scope_id,
        "fit_scope_binding": fit_scope_binding,
        "fit_scope_binding_sha256": fit_scope_binding[
            "fit_scope_binding_sha256"
        ],
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "support_gate": {
            "threshold": 230.0,
            "operator": ">=",
            "fold_training_block_count": 4,
            "fold_minimum_opportunity_world_count": 100,
            "final_training_block_count": 5,
            "final_minimum_opportunity_world_count": 125,
            "requires_every_training_block_nonzero": True,
        },
        "tail_rungs": [
            {
                "threshold": threshold,
                "operator": operator,
                "weight": weight,
            }
            for threshold, operator, weight in _TAIL_RUNGS
        ],
        "upstream_t230_implementation_id": _UPSTREAM_IMPLEMENTATION_ID,
        "upstream_t230_implementation_sha256": (
            _UPSTREAM_IMPLEMENTATION_SHA256
        ),
        "upstream_t230_strategy_hashes": dict(upstream_hashes),
        "preweek_implementation_id": IMPLEMENTATION_ID,
        "preweek_implementation_sha256": implementation[
            "implementation_sha256"
        ],
        "strategy_registry_sha256": _sha(
            registry, label="preweek selector registry"
        ),
        "require_production_width": require_production_width,
        "evidence_role": "standalone-diagnostic-nonpublication-only",
        "outer_exact_source_replay_required": True,
        "standalone_source_authority": False,
        **_false_authorities(),
    }
    input_binding = _self_hash(input_body, "input_binding_sha256")
    input_hash = str(input_binding["input_binding_sha256"])
    means = _row_means(scores, canonical_source_rows)

    r194_packed = _pack_event_mask(
        scores,
        canonical_source_rows,
        threshold=194.0,
        operator=">=",
    )
    r194_counts = _packed_row_counts(r194_packed)
    r194_selected, r194_trace = _select_coverage(
        packed=r194_packed,
        counts=r194_counts,
        means=means,
        lineup_ids=canonical_ids,
        trace_event_field="individual_inclusive_194_world_count",
    )
    r194_receipt = _selector_receipt(
        strategy=registry[0],
        fit_scope_id=fit_scope_id,
        input_binding_sha256=input_hash,
        selected=r194_selected,
        trace=r194_trace,
        lineup_ids=canonical_ids,
        scores=scores,
        canonical_source_rows=canonical_source_rows,
    )

    maxima = _row_maxima(scores, canonical_source_rows)
    maximum_selected, maximum_trace = _select_training_maximum(
        maxima=maxima, means=means, lineup_ids=canonical_ids
    )
    maximum_receipt = _selector_receipt(
        strategy=registry[1],
        fit_scope_id=fit_scope_id,
        input_binding_sha256=input_hash,
        selected=maximum_selected,
        trace=maximum_trace,
        lineup_ids=canonical_ids,
        scores=scores,
        canonical_source_rows=canonical_source_rows,
    )

    ge230_packed = _pack_event_mask(
        scores,
        canonical_source_rows,
        threshold=230.0,
        operator=">=",
    )
    ge230_counts = _packed_row_counts(ge230_packed)
    admitted_indices = [
        index for index, count in enumerate(ge230_counts) if int(count) > 0
    ]
    admitted_ids = [canonical_ids[index] for index in admitted_indices]
    admitted_source_rows = canonical_source_rows[
        np.asarray(admitted_indices, dtype=np.int64)
    ]
    feasible = len(admitted_indices) >= RANKING_DEPTH
    admission_body: dict[str, object] = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": "training-hit-ge-230-admission-v1",
        "fit_scope_id": fit_scope_id,
        "input_binding_sha256": input_hash,
        "threshold": 230.0,
        "operator": ">=",
        "candidate_filter_law": (
            "retain-if-any-fit-world-score-is-inclusive-ge-230"
        ),
        "input_candidate_count": len(canonical_ids),
        "admitted_candidate_count": len(admitted_ids),
        "admitted_canonical_indices": admitted_indices,
        "admitted_lineup_ids": admitted_ids,
        "admitted_lineup_ids_sha256": _sha(
            admitted_ids, label="admitted lineup IDs"
        ),
        "minimum_admitted_candidate_count": RANKING_DEPTH,
        "exact_80_feasible": feasible,
        "infeasible_law": (
            "publish-no-book-never-lower-threshold-or-borrow-candidates"
        ),
        "support_gate_is_separate_from_admission": True,
        **_false_authorities(),
    }
    admission = _self_hash(admission_body, "admission_sha256")
    if not feasible:
        admission_receipt = _infeasible_admission_selector(
            strategy=registry[2],
            fit_scope_id=fit_scope_id,
            input_binding_sha256=input_hash,
            admission=admission,
        )
    else:
        admitted_means = _row_means(scores, admitted_source_rows)
        admitted_packed = _pack_event_mask(
            scores,
            admitted_source_rows,
            threshold=230.0,
            operator=">=",
        )
        admitted_counts = _packed_row_counts(admitted_packed)
        literal_local, literal_local_trace = _select_coverage(
            packed=admitted_packed,
            counts=admitted_counts,
            means=admitted_means,
            lineup_ids=admitted_ids,
            trace_event_field="individual_inclusive_230_world_count",
        )
        fallback_local, fallback_local_trace = _select_block_robust_ladder(
            scores=scores,
            canonical_source_rows=admitted_source_rows,
            lineup_ids=admitted_ids,
            means=admitted_means,
            training_blocks=blocks,
            worlds_per_block=worlds_per_block,
        )
        literal_selected, literal_trace = _normalize_admitted_rank(
            selected_local=literal_local,
            local_trace=literal_local_trace,
            admitted_indices=admitted_indices,
            canonical_ids=canonical_ids,
        )
        fallback_selected, fallback_trace = _normalize_admitted_rank(
            selected_local=fallback_local,
            local_trace=fallback_local_trace,
            admitted_indices=admitted_indices,
            canonical_ids=canonical_ids,
        )
        raw_rankings = [
            _raw_subset_ranking(
                raw_strategy_id=_LITERAL_COVERAGE_STRATEGY_ID,
                raw_strategy_sha256=upstream_hashes[
                    _LITERAL_COVERAGE_STRATEGY_ID
                ],
                fit_scope_id=fit_scope_id,
                input_binding_sha256=input_hash,
                admission=admission,
                selected=literal_selected,
                trace=literal_trace,
                lineup_ids=canonical_ids,
                scores=scores,
                canonical_source_rows=canonical_source_rows,
            ),
            _raw_subset_ranking(
                raw_strategy_id=_FALLBACK_STRATEGY_ID,
                raw_strategy_sha256=upstream_hashes[_FALLBACK_STRATEGY_ID],
                fit_scope_id=fit_scope_id,
                input_binding_sha256=input_hash,
                admission=admission,
                selected=fallback_selected,
                trace=fallback_trace,
                lineup_ids=canonical_ids,
                scores=scores,
                canonical_source_rows=canonical_source_rows,
            ),
        ]
        support_gate = _admission_support_gate(
            scores=scores,
            admitted_source_rows=admitted_source_rows,
            training_blocks=blocks,
            worlds_per_block=worlds_per_block,
        )
        projection = _support_projection(
            support_gate=support_gate, raw_rankings=raw_rankings
        )
        raw_strategy_id = str(projection["selected_raw_strategy_id"])
        raw_strategy_hash = str(projection["selected_raw_strategy_sha256"])
        selected_ranking = next(
            row
            for row in raw_rankings
            if row["raw_ranking_sha256"]
            == projection["selected_raw_ranking_sha256"]
        )
        admission_receipt = _selector_receipt(
            strategy=registry[2],
            fit_scope_id=fit_scope_id,
            input_binding_sha256=input_hash,
            selected=selected_ranking["rank_80_canonical_indices"],
            trace=selected_ranking["rank_trace"],
            lineup_ids=canonical_ids,
            scores=scores,
            canonical_source_rows=canonical_source_rows,
            selected_raw_strategy_id=raw_strategy_id,
            selected_raw_strategy_sha256=raw_strategy_hash,
            admission=admission,
            raw_subset_rankings=raw_rankings,
            support_projection=projection,
        )

    selectors = [r194_receipt, maximum_receipt, admission_receipt]
    body = {
        "schema_version": RECEIPT_SCHEMA,
        "receipt_law_id": RECEIPT_LAW_ID,
        "scope_kind": scope_kind,
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout_block,
        "training_blocks": list(blocks),
        "worlds_per_block": worlds_per_block,
        "fit_scope_binding_sha256": fit_scope_binding[
            "fit_scope_binding_sha256"
        ],
        "input_binding": input_binding,
        "strategy_registry": registry,
        "strategy_registry_sha256": _sha(
            registry, label="preweek selector registry"
        ),
        "implementation_contract": implementation,
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "selector_count": len(selectors),
        "selectors": selectors,
        "selector_receipts_sha256": _sha(
            [row["selector_receipt_sha256"] for row in selectors],
            label="selector receipt hashes",
        ),
        "all_books_are_false_authority": True,
        "ordinary_unweighted_r_fit_worlds": True,
        "evidence_role": "standalone-diagnostic-nonpublication-only",
        "publication_status": "not-publishable-without-outer-source-replay",
        "standalone_source_authority": False,
        "outer_exact_source_replay_required": True,
        **_false_authorities(),
    }
    return _self_hash(body, "preweek_selectors_sha256")


def validate_extreme_tail_preweek_selectors_v1(
    value: Mapping[str, object],
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    candidate_mask_sha256: str,
    occurrence_lineage_sha256: str,
    source_manifest_identity: Mapping[str, object],
    source_member_identity: Mapping[str, object],
    source_score_matrix_identity: Mapping[str, object],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Replay one retained receipt and require canonical byte identity."""
    retained = _mapping(value, label="retained preweek selector receipt")
    expected = run_extreme_tail_preweek_selectors_v1(
        lineup_ids=lineup_ids,
        fit_scores=fit_scores,
        training_blocks=training_blocks,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        candidate_mask_sha256=candidate_mask_sha256,
        occurrence_lineage_sha256=occurrence_lineage_sha256,
        source_manifest_identity=source_manifest_identity,
        source_member_identity=source_member_identity,
        source_score_matrix_identity=source_score_matrix_identity,
        require_production_width=require_production_width,
    )
    if _canonical(retained, label="retained preweek selector receipt") != _canonical(
        expected, label="replayed preweek selector receipt"
    ):
        _fail("retained preweek selector receipt canonical replay differs")
    return expected


__all__ = [
    "ADMISSION_SCHEMA",
    "BOOK_SCHEMA",
    "CorpusExtremeTailPreweekSelectorsError",
    "ENTRY_BUDGETS",
    "FIT_SCOPE_BINDING_SCHEMA",
    "IMPLEMENTATION_ID",
    "IMPLEMENTATION_SCHEMA",
    "INPUT_BINDING_SCHEMA",
    "RANKING_DEPTH",
    "RECEIPT_LAW_ID",
    "RECEIPT_SCHEMA",
    "RAW_BOOK_SCHEMA",
    "RAW_RANKING_SCHEMA",
    "SELECTOR_SCHEMA",
    "STRATEGY_SCHEMA",
    "SUPPORT_PROJECTION_SCHEMA",
    "build_extreme_tail_preweek_fit_scope_binding_v1",
    "frozen_preweek_selector_implementation_v1",
    "frozen_preweek_selector_registry_v1",
    "run_extreme_tail_preweek_selectors_v1",
    "validate_extreme_tail_preweek_selectors_v1",
]
