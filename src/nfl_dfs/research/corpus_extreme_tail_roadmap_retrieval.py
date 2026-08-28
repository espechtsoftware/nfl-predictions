"""Two pure matrix-only retrieval laws required before 2026 Week 1.

The laws in this module are deliberately isolated from the frozen Foundry
engine and its 18-row core manifest:

* ``tail-lcb-ge-230-v1`` chooses one whole rank 80 from a finite, frozen
  two-rank catalog using an untouched deterministic calibration R block and
  a Bonferroni-adjusted exact binomial lower confidence bound; and
* ``correlation-aware-expected-max-ge-230-v1`` subtracts an explicitly
  DK-point-denominated inclusive-230 event-overlap penalty from ordinary
  greedy expected-maximum gain.

Both laws consume canonical candidate IDs and fit-world simulated scores.  The
LCB meta-selector additionally consumes one outcome-blind, generation-pinned
candidate-origin lineage artifact.  Its highest-ordinal fit block is
calibration-only;
its candidate-origin occurrences are stripped by replaying a generation-
pinned origin-lineage artifact, each candidate rank is built without that
block, then the frozen whole ranks are evaluated on calibration.  Four-block
folds still contain no outer held-out columns, and the five-block final fit is
a separate scope.  External source/matrix and occurrence-lineage identities
are retained only as lineage and require outer exact replay before
publication.  Every artifact in this module therefore carries false outcome,
publication, promotion, and production authority.

Score scans are row-chunked and inclusive-230 signatures are bit-packed.  No
dense candidate-by-world Boolean matrix or full score-matrix copy is created.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np
import scipy
from scipy.special import betaincinv

from nfl_dfs.research import corpus_extreme_tail_preweek_selectors as preweek
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    canonical_json_bytes,
    canonical_sha256,
)


RECEIPT_SCHEMA: Final = "extreme-tail-roadmap-retrieval/v1"
INPUT_BINDING_SCHEMA: Final = "extreme-tail-roadmap-retrieval-input/v1"
IMPLEMENTATION_SCHEMA: Final = "extreme-tail-roadmap-retrieval-implementation/v1"
STRATEGY_SCHEMA: Final = "extreme-tail-roadmap-retrieval-strategy/v1"
SELECTOR_SCHEMA: Final = "extreme-tail-roadmap-retrieval-selector/v1"
BOOK_SCHEMA: Final = "extreme-tail-roadmap-retrieval-book/v1"
CALIBRATION_ORIGIN_LINEAGE_SCHEMA: Final = (
    "extreme-tail-calibration-origin-lineage/v1"
)
CALIBRATION_ORIGIN_BINDING_SCHEMA: Final = (
    "extreme-tail-calibration-origin-binding/v1"
)
IMPLEMENTATION_ID: Final = (
    "packed-independent-calibration-cp-overlap-selectors-v1"
)
RECEIPT_LAW_ID: Final = "frozen-preweek-roadmap-retrieval-catalog/v1"

TAIL_LCB_STRATEGY_ID: Final = "tail-lcb-ge-230-v1"
CORRELATION_AWARE_STRATEGY_ID: Final = (
    "correlation-aware-expected-max-ge-230-v1"
)
ENTRY_BUDGETS: Final = (4, 14, 80)
RANKING_DEPTH: Final = 80
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
PRODUCTION_WORLDS_PER_BLOCK: Final = 10_000
CANDIDATE_CHUNK_ROWS: Final = 64
PACKED_BITORDER: Final = "little"
TAIL_THRESHOLD_DK: Final = 230.0
TAIL_OPERATOR: Final = ">="

# A fixed total one-sided error probability.  The exact two-member rank
# catalog receives alpha/2.  Because both whole ranks are frozen without the
# deterministic calibration block, Bonferroni makes the selected rank-80
# calibration lower bound valid despite choosing the larger catalog bound.
LCB_TOTAL_ALPHA_NUMERATOR: Final = 1
LCB_TOTAL_ALPHA_DENOMINATOR: Final = 20
LCB_TOTAL_ALPHA: Final = 0.05
LCB_CONFIDENCE_LEVEL: Final = 0.95
LCB_BOUND_NAME: Final = "one-sided-exact-clopper-pearson"
LCB_MULTIPLICITY_LAW: Final = "bonferroni-alpha-divided-by-exact-rank-catalog"
LCB_CALIBRATION_BLOCK_LAW: Final = "highest-ordinal-fit-r-block"
LCB_CALIBRATION_ORIGIN_LAW: Final = (
    "strip-calibration-origin-occurrences-retain-candidate-iff-other-origin-remains"
)
LCB_CALIBRATION_ORIGIN_INPUT_LAW: Final = (
    "generation-pinned-exact-origin-count-lineage-artifact"
)
LCB_CATALOG_IDS: Final = (
    "cp-transformed-training-utility-rank-v1",
    "correlation-aware-expected-max-training-rank-v1",
)
CP_TRAINING_TRANSFORM_ALPHA: Final = 0.05

# The expected-max base gain is measured in DK points per fit world.  An
# overlap rate is dimensionless.  Multiplying it by the literal target score
# gives the penalty the same DK-point unit without a tuneable coefficient.
REDUNDANCY_PENALTY_DK_PER_UNIT_OVERLAP: Final = 230.0
REDUNDANCY_SIGNATURE_LAW: Final = (
    "candidate-inclusive-230-events-intersection-current-book-event-union"
)

NUMPY_VERSION: Final = "2.5.1"
SCIPY_VERSION: Final = "1.18.0"
_PREWEEK_IMPLEMENTATION_ID: Final = "packed-chunked-preweek-selectors-v1"
_PREWEEK_IMPLEMENTATION_SHA256: Final = (
    "bc54abd13c4a5ecd5966dcc5e1b78afb06028850865517bde754507ccc40e94f"
)
_EXPECTED_MAX_REFERENCE_SHA256: Final = (
    "ad94b80a0ea61d1c58f64f825f00f0d0fea47f36158a239c29382836ff2cb780"
)

# These are literal release guards, replaced once after the bodies below are
# frozen.  Runtime construction never authors a new expected hash.
EXPECTED_IMPLEMENTATION_SHA256: Final = (
    "59f75200be251763126b5a556d8e324d787c7d22890fefadb9fce08dc0dcfdb4"
)
EXPECTED_STRATEGY_SHA256S: Final = {
    TAIL_LCB_STRATEGY_ID: (
        "36ddf8187e726f665d47936fe89750157720591dc005af73b0bd8d243cf86af1"
    ),
    CORRELATION_AWARE_STRATEGY_ID: (
        "e2e7245e784b5d047b7f89fc77c3647b0d1c51747bf31625ccdab14caa70dc31"
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
    "outcome_authority",
)
_OBJECT_IDENTITY_KEYS: Final = frozenset({
    "uri",
    "generation",
    "sha256",
    "bytes",
})
_CALIBRATION_ORIGIN_ROW_KEYS: Final = frozenset({
    "candidate_ordinal",
    "lineup_id",
    "origin_blocks",
    "occurrence_counts_by_block",
    "occurrence_count",
})
_CALIBRATION_ORIGIN_LINEAGE_KEYS: Final = frozenset({
    "schema_version",
    "lineage_law",
    "fit_scope_id",
    "fit_scope_binding_sha256",
    "training_blocks",
    "calibration_block",
    "source_manifest_identity_sha256",
    "source_member_identity_sha256",
    "source_manifest_member_binding_sha256",
    "score_matrix_binding_sha256",
    "candidate_mask_sha256",
    "occurrence_lineage_sha256",
    "ordered_lineup_count",
    "ordered_lineup_ids_sha256",
    "candidate_origin_rows",
    "candidate_origin_rows_sha256",
    "occurrence_count",
    "uses_realized_outcomes",
    "heldout_score_columns_present",
    "outer_exact_source_replay_required",
    "lineage_artifact_sha256",
})
_CALIBRATION_ORIGIN_BINDING_KEYS: Final = frozenset({
    "schema_version",
    "lineage_law",
    "calibration_block",
    "lineage_artifact_sha256",
    "lineage_object_identity",
    "lineage_object_identity_sha256",
    "candidate_origin_rows_sha256",
    "full_occurrence_lineage_sha256",
    "eligible_count",
    "excluded_count",
    "derived_eligible_mask_sha256",
    "caller_supplied_eligibility_mask",
    "generation_pinned",
    "outer_exact_source_replay_required",
    "calibration_origin_binding_sha256",
})
_POPCOUNT: Final = np.asarray(
    [value.bit_count() for value in range(256)], dtype=np.uint8
)


class CorpusExtremeTailRoadmapRetrievalError(ValueError):
    """A roadmap retrieval artifact violates its frozen pure contract."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailRoadmapRetrievalError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return canonical_json_bytes(value)
    except (TypeError, ValueError) as exc:
        raise CorpusExtremeTailRoadmapRetrievalError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _sha(value: object, *, label: str) -> str:
    try:
        return canonical_sha256(value)
    except (TypeError, ValueError) as exc:
        raise CorpusExtremeTailRoadmapRetrievalError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _implementation_body() -> dict[str, object]:
    return {
        "schema_version": IMPLEMENTATION_SCHEMA,
        "implementation_id": IMPLEMENTATION_ID,
        "candidate_chunk_rows": CANDIDATE_CHUNK_ROWS,
        "canonical_candidate_order": "ascending-lineup-id",
        "canonical_score_hash": "float64-le-row-chunked-in-canonical-order",
        "fit_scope_binding": (
            "exact-r0-r4-membership-candidate-mask-occurrence-matrix-source"
        ),
        "event_encoding": "numpy-packbits-uint8-little-per-fit-block",
        "popcount_law": "exact-frozen-uint8-lookup-v1",
        "tail_event": {
            "score_unit": "draftkings-points",
            "threshold": TAIL_THRESHOLD_DK,
            "operator": TAIL_OPERATOR,
        },
        "tail_lcb_law": {
            "bound": LCB_BOUND_NAME,
            "total_alpha_numerator": LCB_TOTAL_ALPHA_NUMERATOR,
            "total_alpha_denominator": LCB_TOTAL_ALPHA_DENOMINATOR,
            "total_alpha": LCB_TOTAL_ALPHA,
            "confidence_level": LCB_CONFIDENCE_LEVEL,
            "calibration_block_law": LCB_CALIBRATION_BLOCK_LAW,
            "calibration_origin_law": LCB_CALIBRATION_ORIGIN_LAW,
            "calibration_origin_input_law": (
                LCB_CALIBRATION_ORIGIN_INPUT_LAW
            ),
            "calibration_origin_derivation": (
                "exact-per-candidate-r0-r4-occurrence-counts;eligible-iff-"
                "positive-count-outside-calibration-block"
            ),
            "calibration_origin_artifact_binding": (
                "exact-uri-generation-content-sha256-bytes-plus-fit-source-"
                "matrix-candidate-and-full-occurrence-lineage"
            ),
            "rank_training_scope": "fit-blocks-minus-calibration-block",
            "rank_catalog_ids": list(LCB_CATALOG_IDS),
            "catalog_size": len(LCB_CATALOG_IDS),
            "catalog_ranks_frozen_before_calibration": True,
            "calibration_alpha": "total-alpha-divided-by-exact-rank-catalog",
            "count_zero_lower": 0.0,
            "positive_count_formula": (
                "scipy.special.betaincinv(k,n-k+1,total-alpha/catalog-size)"
            ),
            "multiplicity_law": LCB_MULTIPLICITY_LAW,
            "book_event_law": (
                "exact-rank80-book-inclusive-230-union-on-calibration-block"
            ),
            "catalog_choice": "largest-calibration-cp-lower-then-frozen-ties",
            "prefix_law": "choose-whole-rank80-then-take-4-14-80-prefixes",
            "bound_scope": "selected-exact-rank80-book-only",
            "prefix_confidence_claim": False,
            "statistical_unit": (
                "simulated-world-book-hit-event-in-independent-calibration-block"
            ),
            "selection_calibration_independence_required": True,
            "calibration_origin_exclusion_required": True,
            "caller_supplied_eligibility_mask_allowed": False,
            "coverage_scope": (
                "simultaneous-95-percent-one-sided-lower-bounds-for-the-exact-"
                "two-frozen-rank80-book-event-probabilities-under-iid-bernoulli-"
                "worlds-from-the-calibration-generator"
            ),
            "coverage_assumption": (
                "calibration-world-book-hit-events-are-iid-bernoulli-and-the-"
                "calibration-block-was-not-used-for-candidate-origin-or-ranking"
            ),
            "nfl_slate_inference_claim": False,
            "confidence_parameter_sweep": False,
        },
        "cp_transformed_training_catalog_law": {
            "catalog_id": LCB_CATALOG_IDS[0],
            "transform": "clopper-pearson-lower-quantile-by-block-count",
            "shape_alpha": CP_TRAINING_TRANSFORM_ALPHA,
            "shape_alpha_per_training_block": "shape-alpha/B-training",
            "adaptive_candidate_and_rank_search": True,
            "frequentist_confidence_claim": False,
            "coverage_claim": False,
            "selection_adjustment": "none-not-a-bound",
            "role": "heuristic-rank-candidate-inside-independent-calibration-meta-law",
        },
        "correlation_aware_expected_max_law": {
            "base_unit": "mean-draftkings-points-per-fit-world",
            "empty_book_first_gain": "candidate-fit-world-mean",
            "later_gain": "mean(max(candidate-current-book-max,0))",
            "signature_law": REDUNDANCY_SIGNATURE_LAW,
            "overlap_rate_denominator": "all-fit-worlds",
            "penalty_dk_per_unit_overlap": (
                REDUNDANCY_PENALTY_DK_PER_UNIT_OVERLAP
            ),
            "penalty_formula": (
                "230-dk-times-redundant-ge230-event-count/all-fit-world-count"
            ),
            "objective": "base-expected-max-gain-dk-minus-overlap-penalty-dk",
            "coefficient_sweep": False,
            "pearson_independence_claim": False,
        },
        "rank_law": "one-prefix-stable-rank-80-with-exact-prefixes-4-14-80",
        "full_per_rank_trace": True,
        "zero_or_negative_gain_law": "continue-by-the-frozen-exact-tie-order",
        "numerical_law": {
            "event_and_union_counts": "signed-int64-exact",
            "bounds_gains_means_and_penalties": "native-float64",
            "reduction_order": "numpy-c-order-axis-reductions",
            "comparison": "raw-float64-lexicographic-no-rounding-no-isclose",
            "nonfinite_values": "forbidden-before-selection",
            "clopper_pearson_lookup_identity": (
                "float64-le-table-hash-retained-in-input-binding"
            ),
        },
        "numpy_version": NUMPY_VERSION,
        "scipy_version": SCIPY_VERSION,
        "upstream_fit_scope_implementation_id": _PREWEEK_IMPLEMENTATION_ID,
        "upstream_fit_scope_implementation_sha256": (
            _PREWEEK_IMPLEMENTATION_SHA256
        ),
        "expected_max_reference_strategy_sha256": (
            _EXPECTED_MAX_REFERENCE_SHA256
        ),
        "dense_candidate_by_world_boolean_matrix": False,
        "full_score_matrix_copy": False,
        "standalone_evidence_role": "diagnostic-nonpublication-only",
        "outer_exact_source_replay_required": True,
    }


def _strategy_body(*, ordinal: int, strategy_id: str) -> dict[str, object]:
    if strategy_id == TAIL_LCB_STRATEGY_ID:
        method = "finite-rank-catalog-independent-calibration-cp-lower-v1"
        parameters = {
            "threshold": TAIL_THRESHOLD_DK,
            "operator": TAIL_OPERATOR,
            "bound": LCB_BOUND_NAME,
            "total_alpha_numerator": LCB_TOTAL_ALPHA_NUMERATOR,
            "total_alpha_denominator": LCB_TOTAL_ALPHA_DENOMINATOR,
            "confidence_level": LCB_CONFIDENCE_LEVEL,
            "multiplicity_law": LCB_MULTIPLICITY_LAW,
            "calibration_block_law": LCB_CALIBRATION_BLOCK_LAW,
            "calibration_origin_law": LCB_CALIBRATION_ORIGIN_LAW,
            "calibration_origin_input_law": (
                LCB_CALIBRATION_ORIGIN_INPUT_LAW
            ),
            "rank_catalog_ids": list(LCB_CATALOG_IDS),
            "catalog_size": len(LCB_CATALOG_IDS),
            "rank_training_scope": "fit-blocks-minus-calibration-block",
            "bound_scope": "selected-exact-rank80-book-only",
            "prefix_confidence_claim": False,
            "confidence_parameter_sweep": False,
        }
        tie_law = [
            "largest-bonferroni-adjusted-calibration-cp-lower",
            "largest-calibration-inclusive-230-book-hit-count",
            "ascending-frozen-rank-catalog-ordinal",
        ]
        role = "fixed-independent-calibration-tail-lower-confidence-meta-selector"
    elif strategy_id == CORRELATION_AWARE_STRATEGY_ID:
        method = "greedy-expected-max-minus-inclusive-230-overlap-penalty-v1"
        parameters = {
            "threshold": TAIL_THRESHOLD_DK,
            "operator": TAIL_OPERATOR,
            "signature_law": REDUNDANCY_SIGNATURE_LAW,
            "overlap_rate_denominator": "all-fit-worlds",
            "penalty_dk_per_unit_overlap": (
                REDUNDANCY_PENALTY_DK_PER_UNIT_OVERLAP
            ),
            "penalty_unit": "draftkings-points-per-fit-world",
            "coefficient_sweep": False,
        }
        tie_law = [
            "largest-penalized-marginal-expected-max-gain-dk",
            "largest-unpenalized-marginal-expected-max-gain-dk",
            "smallest-redundant-inclusive-230-event-count",
            "largest-individual-inclusive-230-world-count",
            "largest-fit-world-mean-score",
            "ascending-lineup-id",
        ]
        role = "fixed-event-redundancy-aware-expected-max-selector"
    else:
        _fail("unknown roadmap retrieval strategy ID")
    return {
        "schema_version": STRATEGY_SCHEMA,
        "ordinal": ordinal,
        "strategy_id": strategy_id,
        "method": method,
        "parameters": parameters,
        "tie_law": tie_law,
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "implementation_id": IMPLEMENTATION_ID,
        "implementation_sha256": EXPECTED_IMPLEMENTATION_SHA256,
        "selection_inputs": (
            "fit-scope-simulated-scores-plus-outcome-blind-generation-pinned-"
            "candidate-origin-lineage"
            if strategy_id == TAIL_LCB_STRATEGY_ID
            else "fit-scope-simulated-scores-only"
        ),
        "heldout_score_columns_allowed": False,
        "realized_outcomes_allowed": False,
        "role": role,
    }


def _guard_upstream_contracts() -> dict[str, object]:
    if (
        tuple(rw.WORLD_BLOCKS) != WORLD_BLOCKS
        or retrieval.WORLDS_PER_BLOCK != PRODUCTION_WORLDS_PER_BLOCK
        or tuple(preweek.ENTRY_BUDGETS) != ENTRY_BUDGETS
        or preweek.RANKING_DEPTH != RANKING_DEPTH
        or preweek.FIT_SCOPE_BINDING_SCHEMA
        != "extreme-tail-preweek-fit-scope-binding/v1"
    ):
        _fail("imported world, budget, or fit-scope constants drifted")
    upstream = _mapping(
        preweek.frozen_preweek_selector_implementation_v1(),
        label="upstream preweek implementation",
    )
    retained = upstream.get("implementation_sha256")
    remainder = {
        key: value
        for key, value in upstream.items()
        if key != "implementation_sha256"
    }
    if (
        upstream.get("implementation_id") != _PREWEEK_IMPLEMENTATION_ID
        or retained != _PREWEEK_IMPLEMENTATION_SHA256
        or _sha(remainder, label="upstream preweek implementation") != retained
    ):
        _fail("upstream preweek implementation identity drifted")
    expected_max_hash: str | None = None
    for raw in retrieval.frozen_retrieval_strategies_v2(RANKING_DEPTH):
        strategy = _mapping(raw, label="neighbor retrieval strategy")
        if strategy.get("strategy_id") != "expected-max-v1":
            continue
        retained_strategy = strategy.get("strategy_sha256")
        strategy_remainder = {
            key: value
            for key, value in strategy.items()
            if key != "strategy_sha256"
        }
        if (
            type(retained_strategy) is not str
            or _sha(strategy_remainder, label="neighbor expected-max strategy")
            != retained_strategy
        ):
            _fail("neighbor expected-max self-identity drifted")
        expected_max_hash = retained_strategy
    if expected_max_hash != _EXPECTED_MAX_REFERENCE_SHA256:
        _fail("neighbor expected-max strategy identity drifted")
    if tuple(preweek._FALSE_AUTHORITY_FIELDS) + ("outcome_authority",) != (  # noqa: SLF001
        _FALSE_AUTHORITY_FIELDS
    ):
        _fail("false-authority registry drifted")
    return {
        "fit_scope_implementation_id": _PREWEEK_IMPLEMENTATION_ID,
        "fit_scope_implementation_sha256": _PREWEEK_IMPLEMENTATION_SHA256,
        "expected_max_reference_strategy_sha256": expected_max_hash,
    }


def _guard_local_contracts() -> None:
    if (
        LCB_TOTAL_ALPHA_NUMERATOR,
        LCB_TOTAL_ALPHA_DENOMINATOR,
        LCB_TOTAL_ALPHA,
        LCB_CONFIDENCE_LEVEL,
        CP_TRAINING_TRANSFORM_ALPHA,
        TAIL_THRESHOLD_DK,
        REDUNDANCY_PENALTY_DK_PER_UNIT_OVERLAP,
        CANDIDATE_CHUNK_ROWS,
    ) != (1, 20, 0.05, 0.95, 0.05, 230.0, 230.0, 64) or (
        LCB_CALIBRATION_BLOCK_LAW != "highest-ordinal-fit-r-block"
        or LCB_CATALOG_IDS
        != (
            "cp-transformed-training-utility-rank-v1",
            "correlation-aware-expected-max-training-rank-v1",
        )
        or LCB_CALIBRATION_ORIGIN_LAW
        != (
            "strip-calibration-origin-occurrences-retain-candidate-iff-other-"
            "origin-remains"
        )
        or LCB_CALIBRATION_ORIGIN_INPUT_LAW
        != "generation-pinned-exact-origin-count-lineage-artifact"
    ):
        _fail("literal roadmap retrieval constants drifted")
    if np.__version__ != NUMPY_VERSION or scipy.__version__ != SCIPY_VERSION:
        _fail("roadmap retrieval numerical runtime differs")
    implementation_hash = _sha(
        _implementation_body(), label="roadmap retrieval implementation"
    )
    if implementation_hash != EXPECTED_IMPLEMENTATION_SHA256:
        _fail("literal roadmap retrieval implementation hash differs")
    observed: dict[str, str] = {}
    for ordinal, strategy_id in enumerate(
        (TAIL_LCB_STRATEGY_ID, CORRELATION_AWARE_STRATEGY_ID)
    ):
        body = _strategy_body(ordinal=ordinal, strategy_id=strategy_id)
        observed[strategy_id] = _sha(body, label=f"{strategy_id} strategy")
    if observed != EXPECTED_STRATEGY_SHA256S:
        _fail("literal roadmap retrieval strategy hashes differ")
    _guard_upstream_contracts()


def frozen_roadmap_retrieval_implementation_v1() -> dict[str, object]:
    """Return the literal-hash-pinned implementation contract."""
    _guard_local_contracts()
    body = _implementation_body()
    body["implementation_sha256"] = EXPECTED_IMPLEMENTATION_SHA256
    return body


def frozen_roadmap_retrieval_registry_v1() -> list[dict[str, object]]:
    """Return the exact two-law registry in canonical order."""
    _guard_local_contracts()
    rows: list[dict[str, object]] = []
    for ordinal, strategy_id in enumerate(
        (TAIL_LCB_STRATEGY_ID, CORRELATION_AWARE_STRATEGY_ID)
    ):
        body = _strategy_body(ordinal=ordinal, strategy_id=strategy_id)
        body["strategy_sha256"] = EXPECTED_STRATEGY_SHA256S[strategy_id]
        rows.append(body)
    return rows


def _candidate_chunks(row_count: int):
    for start in range(0, row_count, CANDIDATE_CHUNK_ROWS):
        yield start, min(start + CANDIDATE_CHUNK_ROWS, row_count)


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
        values = scores[rows]
    else:
        values = scores[rows, column_start:column_stop]
    return np.ascontiguousarray(values, dtype=np.float64)


def _row_means(
    scores: np.ndarray, canonical_source_rows: np.ndarray
) -> np.ndarray:
    result = np.empty(len(canonical_source_rows), dtype=np.float64)
    for start, stop in _candidate_chunks(len(canonical_source_rows)):
        result[start:stop] = _score_rows(
            scores, canonical_source_rows, start, stop
        ).mean(axis=1, dtype=np.float64)
    return result


def _pack_ge230_by_block(
    *,
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    block_count: int,
    worlds_per_block: int,
) -> list[np.ndarray]:
    packed_width = (worlds_per_block + 7) // 8
    packed_by_block = [
        np.empty((len(canonical_source_rows), packed_width), dtype=np.uint8)
        for _ in range(block_count)
    ]
    for block_ordinal, packed in enumerate(packed_by_block):
        column_start = block_ordinal * worlds_per_block
        column_stop = column_start + worlds_per_block
        for start, stop in _candidate_chunks(len(canonical_source_rows)):
            event = (
                _score_rows(
                    scores,
                    canonical_source_rows,
                    start,
                    stop,
                    column_start=column_start,
                    column_stop=column_stop,
                )
                >= TAIL_THRESHOLD_DK
            )
            packed[start:stop] = np.packbits(
                event, axis=1, bitorder=PACKED_BITORDER
            )
    return packed_by_block


def _packed_row_counts(packed: np.ndarray) -> np.ndarray:
    return _POPCOUNT[packed].sum(axis=1, dtype=np.int64)


def _fresh_counts(packed: np.ndarray, covered: np.ndarray) -> np.ndarray:
    return _POPCOUNT[np.bitwise_and(packed, np.bitwise_not(covered))].sum(
        axis=1, dtype=np.int64
    )


def _overlap_counts(packed: np.ndarray, covered: np.ndarray) -> np.ndarray:
    return _POPCOUNT[np.bitwise_and(packed, covered)].sum(
        axis=1, dtype=np.int64
    )


def _signature_sha256(
    values_by_block: Sequence[np.ndarray],
    *,
    training_blocks: Sequence[str],
    worlds_per_block: int,
) -> str:
    digest = sha256()
    digest.update(
        canonical_json_bytes(
            {
                "encoding": "packbits-uint8-little-per-block",
                "training_blocks": list(training_blocks),
                "worlds_per_block": worlds_per_block,
                "shapes": [list(np.asarray(value).shape) for value in values_by_block],
            }
        )
    )
    digest.update(b"\0")
    for block, raw in zip(training_blocks, values_by_block, strict=True):
        value = np.ascontiguousarray(raw, dtype=np.uint8)
        digest.update(block.encode("utf-8"))
        digest.update(b"\0")
        digest.update(memoryview(value).cast("B"))
        digest.update(b"\0")
    return digest.hexdigest()


def _clopper_pearson_lower_table(
    *, worlds_per_block: int, tail_probability: float
) -> np.ndarray:
    if (
        type(worlds_per_block) is not int
        or worlds_per_block < 1
        or type(tail_probability) is not float
        or not 0.0 < tail_probability < 1.0
    ):
        _fail("Clopper-Pearson table scope differs")
    counts = np.arange(1, worlds_per_block + 1, dtype=np.float64)
    table = np.zeros(worlds_per_block + 1, dtype=np.float64)
    table[1:] = betaincinv(
        counts,
        float(worlds_per_block) - counts + 1.0,
        tail_probability,
    )
    if (
        not np.isfinite(table).all()
        or table[0] != 0.0
        or np.any(table < 0.0)
        or np.any(table > 1.0)
        or np.any(np.diff(table) < 0.0)
    ):
        _fail("Clopper-Pearson lower lookup is invalid")
    return table


def _float64_array_sha256(value: np.ndarray, *, label: str) -> str:
    array = np.ascontiguousarray(value, dtype="<f8")
    digest = sha256()
    digest.update(
        canonical_json_bytes(
            {"label": label, "dtype": "float64-le", "shape": list(array.shape)}
        )
    )
    digest.update(b"\0")
    digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def _require_sha256(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _calibration_origin_eligibility(
    *,
    lineage_artifact: Mapping[str, object],
    lineage_artifact_identity: Mapping[str, object],
    canonical_ids: Sequence[str],
    training_blocks: Sequence[str],
    calibration_block: str,
    fit_scope: Mapping[str, object],
) -> tuple[np.ndarray, dict[str, object]]:
    """Derive calibration-origin eligibility from one pinned lineage artifact."""
    item = dict(_mapping(lineage_artifact, label="calibration-origin lineage"))
    if set(item) != _CALIBRATION_ORIGIN_LINEAGE_KEYS:
        _fail("calibration-origin lineage artifact fields differ")
    raw_rows = _sequence(
        item.get("candidate_origin_rows"),
        label="calibration-origin candidate rows",
    )
    if len(raw_rows) != len(canonical_ids):
        _fail("calibration-origin lineage candidate count differs")
    fit_blocks = list(training_blocks)
    fit_block_set = set(fit_blocks)
    normalized_rows: list[dict[str, object]] = []
    canonical_mask = np.zeros(len(canonical_ids), dtype=np.bool_)
    total_occurrences = 0
    for ordinal, (lineup_id, raw_row) in enumerate(
        zip(canonical_ids, raw_rows, strict=True)
    ):
        row = _mapping(raw_row, label=f"calibration-origin row[{ordinal}]")
        if set(row) != _CALIBRATION_ORIGIN_ROW_KEYS:
            _fail(f"calibration-origin row[{ordinal}] fields differ")
        raw_counts = _mapping(
            row.get("occurrence_counts_by_block"),
            label=f"calibration-origin row[{ordinal}] block counts",
        )
        if set(raw_counts) != set(WORLD_BLOCKS):
            _fail(f"calibration-origin row[{ordinal}] block count fields differ")
        counts: dict[str, int] = {}
        for block in WORLD_BLOCKS:
            value = raw_counts.get(block)
            if type(value) is not int or value < 0:
                _fail(f"calibration-origin row[{ordinal}] block count differs")
            if block not in fit_block_set and value != 0:
                _fail("calibration-origin lineage includes a non-fit origin block")
            counts[block] = value
        occurrence_count = sum(counts.values())
        origin_blocks = [block for block in WORLD_BLOCKS if counts[block] > 0]
        if (
            row.get("candidate_ordinal") != ordinal
            or row.get("lineup_id") != lineup_id
            or row.get("origin_blocks") != origin_blocks
            or type(row.get("occurrence_count")) is not int
            or row.get("occurrence_count") != occurrence_count
            or occurrence_count < 1
        ):
            _fail(f"calibration-origin row[{ordinal}] values differ")
        canonical_mask[ordinal] = any(
            counts[block] > 0 for block in fit_blocks if block != calibration_block
        )
        total_occurrences += occurrence_count
        normalized_rows.append({
            "candidate_ordinal": ordinal,
            "lineup_id": lineup_id,
            "origin_blocks": origin_blocks,
            "occurrence_counts_by_block": counts,
            "occurrence_count": occurrence_count,
        })
    fit_scope_mapping = _mapping(fit_scope, label="fit scope binding")
    score_matrix_binding = _mapping(
        fit_scope_mapping.get("score_matrix_binding"),
        label="fit-scope score matrix binding",
    )
    expected_body: dict[str, object] = {
        "schema_version": CALIBRATION_ORIGIN_LINEAGE_SCHEMA,
        "lineage_law": LCB_CALIBRATION_ORIGIN_INPUT_LAW,
        "fit_scope_id": fit_scope_mapping.get("fit_scope_id"),
        "fit_scope_binding_sha256": fit_scope_mapping.get(
            "fit_scope_binding_sha256"
        ),
        "training_blocks": fit_blocks,
        "calibration_block": calibration_block,
        "source_manifest_identity_sha256": _sha(
            fit_scope_mapping.get("source_manifest_identity"),
            label="calibration-origin source manifest identity",
        ),
        "source_member_identity_sha256": _sha(
            fit_scope_mapping.get("source_member_identity"),
            label="calibration-origin source member identity",
        ),
        "source_manifest_member_binding_sha256": fit_scope_mapping.get(
            "source_manifest_member_binding_sha256"
        ),
        "score_matrix_binding_sha256": _sha(
            score_matrix_binding,
            label="calibration-origin score matrix binding",
        ),
        "candidate_mask_sha256": fit_scope_mapping.get(
            "candidate_mask_sha256"
        ),
        "occurrence_lineage_sha256": fit_scope_mapping.get(
            "occurrence_lineage_sha256"
        ),
        "ordered_lineup_count": len(canonical_ids),
        "ordered_lineup_ids_sha256": _sha(
            list(canonical_ids),
            label="calibration-origin ordered lineup IDs",
        ),
        "candidate_origin_rows": normalized_rows,
        "candidate_origin_rows_sha256": _sha(
            normalized_rows,
            label="calibration-origin candidate rows",
        ),
        "occurrence_count": total_occurrences,
        "uses_realized_outcomes": False,
        "heldout_score_columns_present": False,
        "outer_exact_source_replay_required": True,
    }
    expected = dict(expected_body)
    expected["lineage_artifact_sha256"] = _sha(
        expected, label="calibration-origin lineage artifact"
    )
    if _canonical(item, label="calibration-origin lineage artifact") != _canonical(
        expected, label="expected calibration-origin lineage artifact"
    ):
        _fail("calibration-origin lineage artifact differs from exact scope replay")

    payload = _canonical(expected, label="calibration-origin lineage artifact")
    raw_identity = dict(
        _mapping(
            lineage_artifact_identity,
            label="calibration-origin lineage object identity",
        )
    )
    if set(raw_identity) != _OBJECT_IDENTITY_KEYS:
        _fail("calibration-origin lineage object identity fields differ")
    uri = raw_identity.get("uri")
    generation = raw_identity.get("generation")
    content_hash = raw_identity.get("sha256")
    byte_count = raw_identity.get("bytes")
    if (
        type(uri) is not str
        or not uri.startswith("gs://")
        or type(generation) is not str
        or not generation.isdigit()
        or _require_sha256(
            content_hash,
            label="calibration-origin lineage content hash",
        )
        != sha256(payload).hexdigest()
        or type(byte_count) is not int
        or byte_count != len(payload)
    ):
        _fail("calibration-origin lineage object identity differs from content")
    identity = {
        "uri": uri,
        "generation": generation,
        "sha256": content_hash,
        "bytes": byte_count,
    }
    eligible = np.flatnonzero(canonical_mask).astype(np.int64, copy=False)
    if len(eligible) < RANKING_DEPTH:
        _fail("fewer than 80 candidates remain after calibration-origin stripping")
    digest = sha256()
    digest.update(
        canonical_json_bytes(
            {
                "law": LCB_CALIBRATION_ORIGIN_LAW,
                "calibration_block": calibration_block,
                "ordered_lineup_ids_sha256": _sha(
                    list(canonical_ids),
                    label="calibration-origin eligibility lineup IDs",
                ),
                "candidate_count": len(canonical_ids),
                "eligible_count": len(eligible),
                "dtype": "bool-u8",
                "row_order": "ascending-lineup-id",
                "lineage_artifact_sha256": expected[
                    "lineage_artifact_sha256"
                ],
            }
        )
    )
    digest.update(b"\0")
    digest.update(memoryview(canonical_mask.view(np.uint8)).cast("B"))
    binding: dict[str, object] = {
        "schema_version": CALIBRATION_ORIGIN_BINDING_SCHEMA,
        "lineage_law": LCB_CALIBRATION_ORIGIN_INPUT_LAW,
        "calibration_block": calibration_block,
        "lineage_artifact_sha256": expected["lineage_artifact_sha256"],
        "lineage_object_identity": identity,
        "lineage_object_identity_sha256": _sha(
            identity,
            label="calibration-origin lineage object identity",
        ),
        "candidate_origin_rows_sha256": expected[
            "candidate_origin_rows_sha256"
        ],
        "full_occurrence_lineage_sha256": expected[
            "occurrence_lineage_sha256"
        ],
        "eligible_count": len(eligible),
        "excluded_count": len(canonical_ids) - len(eligible),
        "derived_eligible_mask_sha256": digest.hexdigest(),
        "caller_supplied_eligibility_mask": False,
        "generation_pinned": True,
        "outer_exact_source_replay_required": True,
    }
    binding["calibration_origin_binding_sha256"] = _sha(
        binding, label="calibration-origin binding"
    )
    return eligible, binding


def _canonical_score_slice_sha256(
    *,
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    column_start: int,
    column_stop: int,
    label: str,
) -> str:
    if not 0 <= column_start < column_stop <= scores.shape[1]:
        _fail("canonical score-slice bounds differ")
    digest = sha256()
    digest.update(
        canonical_json_bytes(
            {
                "label": label,
                "dtype": "float64-le",
                "shape": [
                    len(canonical_source_rows),
                    column_stop - column_start,
                ],
                "row_order": "ascending-lineup-id",
            }
        )
    )
    digest.update(b"\0")
    for start, stop in _candidate_chunks(len(canonical_source_rows)):
        chunk = np.ascontiguousarray(
            scores[
                canonical_source_rows[start:stop],
                column_start:column_stop,
            ],
            dtype="<f8",
        )
        digest.update(memoryview(chunk).cast("B"))
    return digest.hexdigest()


def _validated_scope(
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
    require_production_width: bool,
) -> tuple[
    list[str],
    np.ndarray,
    np.ndarray,
    tuple[str, ...],
    dict[str, object],
]:
    _guard_local_contracts()
    try:
        fit_scope = preweek.build_extreme_tail_preweek_fit_scope_binding_v1(
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
    except preweek.CorpusExtremeTailPreweekSelectorsError as exc:
        raise CorpusExtremeTailRoadmapRetrievalError(str(exc)) from exc
    raw_ids = list(_sequence(lineup_ids, label="lineup IDs"))
    scores = np.asarray(fit_scores)
    canonical_source_rows = np.asarray(
        sorted(range(len(raw_ids)), key=raw_ids.__getitem__), dtype=np.int64
    )
    canonical_ids = [raw_ids[int(index)] for index in canonical_source_rows]
    blocks = tuple(str(value) for value in fit_scope["training_blocks"])
    if (
        canonical_ids != fit_scope["ordered_lineup_ids"]
        or scores.shape
        != tuple(fit_scope["score_matrix_binding"]["canonical_fit_score_shape"])
    ):
        _fail("fit-scope canonical matrix replay differs")
    return canonical_ids, scores, canonical_source_rows, blocks, fit_scope


def _select_cp_transformed_training_utility(
    *,
    packed_by_block: Sequence[np.ndarray],
    training_blocks: Sequence[str],
    worlds_per_block: int,
    lineup_ids: Sequence[str],
    means: np.ndarray,
    transform_table: np.ndarray,
) -> tuple[list[int], list[dict[str, object]]]:
    block_count = len(training_blocks)
    individual_by_block = np.column_stack(
        [_packed_row_counts(packed) for packed in packed_by_block]
    )
    individual_totals = individual_by_block.sum(axis=1, dtype=np.int64)
    covered_by_block = [
        np.zeros(packed.shape[1], dtype=np.uint8) for packed in packed_by_block
    ]
    covered_counts = np.zeros(block_count, dtype=np.int64)
    selected: list[int] = []
    remaining = np.ones(len(lineup_ids), dtype=bool)
    trace: list[dict[str, object]] = []

    while len(selected) < RANKING_DEPTH:
        pre_transforms = transform_table[covered_counts]
        pre_objective = float(pre_transforms.mean(dtype=np.float64))
        best: int | None = None
        best_key: tuple[object, ...] | None = None
        best_post_counts: np.ndarray | None = None
        best_post_lowers: np.ndarray | None = None
        best_fresh_total = -1

        for start, stop in _candidate_chunks(len(lineup_ids)):
            fresh_by_block = np.column_stack(
                [
                    _fresh_counts(packed[start:stop], covered)
                    for packed, covered in zip(
                        packed_by_block, covered_by_block, strict=True
                    )
                ]
            )
            post_counts = fresh_by_block + covered_counts[None, :]
            post_transforms = transform_table[post_counts]
            post_objectives = post_transforms.mean(axis=1, dtype=np.float64)
            post_minima = post_transforms.min(axis=1)
            fresh_totals = fresh_by_block.sum(axis=1, dtype=np.int64)
            if not np.isfinite(post_objectives).all():
                _fail("CP-transformed training objective is non-finite")
            for offset in range(stop - start):
                index = start + offset
                if not remaining[index]:
                    continue
                key = (
                    -float(post_objectives[offset]),
                    -float(post_minima[offset]),
                    -int(fresh_totals[offset]),
                    -int(individual_totals[index]),
                    -float(means[index]),
                    lineup_ids[index],
                )
                if best_key is None or key < best_key:
                    best = index
                    best_key = key
                    best_post_counts = post_counts[offset].copy()
                    best_post_lowers = post_transforms[offset].copy()
                    best_fresh_total = int(fresh_totals[offset])

        if best is None or best_post_counts is None or best_post_lowers is None:
            _fail("CP-transformed training rank ended before 80")
        candidate_signatures = [packed[best] for packed in packed_by_block]
        post_covered = [
            np.bitwise_or(covered, signature)
            for covered, signature in zip(
                covered_by_block, candidate_signatures, strict=True
            )
        ]
        post_objective = float(best_post_lowers.mean(dtype=np.float64))
        trace.append(
            {
                "selection_rank": len(selected),
                "canonical_lineup_index": best,
                "lineup_id": lineup_ids[best],
                "pre_block_union_hit_counts": [
                    int(value) for value in covered_counts
                ],
                "candidate_individual_block_hit_counts": [
                    int(value) for value in individual_by_block[best]
                ],
                "post_block_union_hit_counts": [
                    int(value) for value in best_post_counts
                ],
                "pre_block_cp_training_transforms": [
                    float(value) for value in pre_transforms
                ],
                "post_block_cp_training_transforms": [
                    float(value) for value in best_post_lowers
                ],
                "pre_mean_block_cp_training_utility": pre_objective,
                "post_mean_block_cp_training_utility": post_objective,
                "marginal_mean_block_cp_training_utility": (
                    post_objective - pre_objective
                ),
                "post_minimum_block_cp_training_transform": float(
                    best_post_lowers.min()
                ),
                "frequentist_confidence_claim": False,
                "coverage_claim": False,
                "marginal_new_inclusive_230_world_count": best_fresh_total,
                "individual_inclusive_230_world_count": int(
                    individual_totals[best]
                ),
                "fit_world_mean_score_dk": float(means[best]),
                "candidate_ge230_signature_sha256": _signature_sha256(
                    candidate_signatures,
                    training_blocks=training_blocks,
                    worlds_per_block=worlds_per_block,
                ),
                "book_ge230_union_signature_sha256_after": _signature_sha256(
                    post_covered,
                    training_blocks=training_blocks,
                    worlds_per_block=worlds_per_block,
                ),
            }
        )
        selected.append(best)
        remaining[best] = False
        covered_by_block = post_covered
        covered_counts = best_post_counts
    return selected, trace


def _select_correlation_aware_expected_max(
    *,
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    packed_by_block: Sequence[np.ndarray],
    training_blocks: Sequence[str],
    worlds_per_block: int,
    lineup_ids: Sequence[str],
    means: np.ndarray,
    ranking_depth: int = RANKING_DEPTH,
) -> tuple[list[int], list[dict[str, object]]]:
    if (
        type(ranking_depth) is not int
        or ranking_depth < 1
        or ranking_depth > len(lineup_ids)
    ):
        _fail("correlation-aware expected-max ranking depth is infeasible")
    world_count = len(training_blocks) * worlds_per_block
    individual_totals = sum(
        (_packed_row_counts(packed) for packed in packed_by_block),
        start=np.zeros(len(lineup_ids), dtype=np.int64),
    )
    covered_by_block = [
        np.zeros(packed.shape[1], dtype=np.uint8) for packed in packed_by_block
    ]
    current_max: np.ndarray | None = None
    remaining = np.ones(len(lineup_ids), dtype=bool)
    selected: list[int] = []
    trace: list[dict[str, object]] = []

    while len(selected) < ranking_depth:
        expected_before = (
            0.0
            if current_max is None
            else float(current_max.mean(dtype=np.float64))
        )
        union_count_before = sum(
            int(_POPCOUNT[covered].sum(dtype=np.int64))
            for covered in covered_by_block
        )
        best: int | None = None
        best_key: tuple[object, ...] | None = None
        best_base_gain = 0.0
        best_overlap = 0
        best_penalty = 0.0
        best_adjusted = 0.0

        for start, stop in _candidate_chunks(len(lineup_ids)):
            values = _score_rows(scores, canonical_source_rows, start, stop)
            if current_max is None:
                base_gains = values.mean(axis=1, dtype=np.float64)
            else:
                np.subtract(values, current_max, out=values)
                np.maximum(values, 0.0, out=values)
                base_gains = values.mean(axis=1, dtype=np.float64)
            overlaps = sum(
                (
                    _overlap_counts(packed[start:stop], covered)
                    for packed, covered in zip(
                        packed_by_block, covered_by_block, strict=True
                    )
                ),
                start=np.zeros(stop - start, dtype=np.int64),
            )
            penalties = (
                REDUNDANCY_PENALTY_DK_PER_UNIT_OVERLAP
                * overlaps.astype(np.float64)
                / float(world_count)
            )
            adjusted = base_gains - penalties
            if not np.isfinite(adjusted).all():
                _fail("correlation-aware expected-max objective is non-finite")
            for offset in range(stop - start):
                index = start + offset
                if not remaining[index]:
                    continue
                key = (
                    -float(adjusted[offset]),
                    -float(base_gains[offset]),
                    int(overlaps[offset]),
                    -int(individual_totals[index]),
                    -float(means[index]),
                    lineup_ids[index],
                )
                if best_key is None or key < best_key:
                    best = index
                    best_key = key
                    best_base_gain = float(base_gains[offset])
                    best_overlap = int(overlaps[offset])
                    best_penalty = float(penalties[offset])
                    best_adjusted = float(adjusted[offset])

        if best is None:
            _fail(
                "correlation-aware expected-max rank ended before requested depth"
            )
        selected_scores = _score_rows(
            scores, canonical_source_rows, best, best + 1
        )[0]
        current_max = (
            selected_scores.copy()
            if current_max is None
            else np.maximum(current_max, selected_scores)
        )
        expected_after = float(current_max.mean(dtype=np.float64))
        candidate_signatures = [packed[best] for packed in packed_by_block]
        covered_after = [
            np.bitwise_or(covered, signature)
            for covered, signature in zip(
                covered_by_block, candidate_signatures, strict=True
            )
        ]
        union_count_after = sum(
            int(_POPCOUNT[covered].sum(dtype=np.int64))
            for covered in covered_after
        )
        trace.append(
            {
                "selection_rank": len(selected),
                "canonical_lineup_index": best,
                "lineup_id": lineup_ids[best],
                "book_expected_max_before_dk": expected_before,
                "base_marginal_expected_max_gain_dk": best_base_gain,
                "candidate_inclusive_230_world_count": int(
                    individual_totals[best]
                ),
                "book_inclusive_230_union_count_before": union_count_before,
                "redundant_inclusive_230_event_count": best_overlap,
                "redundant_inclusive_230_event_rate": (
                    float(best_overlap) / float(world_count)
                ),
                "redundancy_penalty_dk_per_unit_overlap": (
                    REDUNDANCY_PENALTY_DK_PER_UNIT_OVERLAP
                ),
                "redundancy_penalty_dk": best_penalty,
                "penalized_marginal_expected_max_gain_dk": best_adjusted,
                "book_expected_max_after_dk": expected_after,
                "book_inclusive_230_union_count_after": union_count_after,
                "fit_world_mean_score_dk": float(means[best]),
                "candidate_ge230_signature_sha256": _signature_sha256(
                    candidate_signatures,
                    training_blocks=training_blocks,
                    worlds_per_block=worlds_per_block,
                ),
                "book_ge230_union_signature_sha256_after": _signature_sha256(
                    covered_after,
                    training_blocks=training_blocks,
                    worlds_per_block=worlds_per_block,
                ),
            }
        )
        selected.append(best)
        remaining[best] = False
        covered_by_block = covered_after
    return selected, trace


def _calibration_book_event(
    *,
    selected: Sequence[int],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    calibration_column_start: int,
    worlds_per_block: int,
) -> tuple[np.ndarray, int]:
    if len(selected) != RANKING_DEPTH:
        _fail("calibration requires one exact frozen rank 80")
    current_max: np.ndarray | None = None
    column_stop = calibration_column_start + worlds_per_block
    for index in selected:
        row = _score_rows(
            scores,
            canonical_source_rows,
            index,
            index + 1,
            column_start=calibration_column_start,
            column_stop=column_stop,
        )[0]
        current_max = (
            row.copy() if current_max is None else np.maximum(current_max, row)
        )
    if current_max is None:
        _fail("calibration book event requires a nonempty rank")
    event = np.asarray(current_max >= TAIL_THRESHOLD_DK, dtype=bool)
    return event, int(np.count_nonzero(event))


def _select_independent_calibration_meta_rank(
    *,
    catalog: Sequence[
        tuple[str, Sequence[int], Sequence[Mapping[str, object]]]
    ],
    lineup_ids: Sequence[str],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    rank_training_blocks: Sequence[str],
    calibration_block: str,
    worlds_per_block: int,
    rank_training_matrix_sha256: str,
    calibration_matrix_sha256: str,
    eligible_canonical_indices: Sequence[int],
    calibration_origin_binding: Mapping[str, object],
) -> tuple[
    list[int],
    list[dict[str, object]],
    dict[str, object],
]:
    all_fit_blocks = tuple(rank_training_blocks) + (calibration_block,)
    canonical_fit_blocks = tuple(
        block for block in WORLD_BLOCKS if block in set(all_fit_blocks)
    )
    if (
        tuple(row[0] for row in catalog) != LCB_CATALOG_IDS
        or calibration_block in rank_training_blocks
        or len(all_fit_blocks) not in {4, 5}
        or all_fit_blocks != canonical_fit_blocks
    ):
        _fail("independent calibration rank catalog scope differs")
    calibration_column_start = len(rank_training_blocks) * worlds_per_block
    eligible_set = {int(value) for value in eligible_canonical_indices}
    if (
        len(eligible_set) != len(eligible_canonical_indices)
        or len(eligible_set) < RANKING_DEPTH
        or min(eligible_set) < 0
        or max(eligible_set) >= len(lineup_ids)
    ):
        _fail("calibration-origin eligible candidate scope differs")
    origin_binding = dict(
        _mapping(calibration_origin_binding, label="calibration-origin binding")
    )
    if set(origin_binding) != _CALIBRATION_ORIGIN_BINDING_KEYS:
        _fail("calibration-origin binding fields differ")
    retained_origin_binding_hash = origin_binding.get(
        "calibration_origin_binding_sha256"
    )
    origin_binding_body = {
        key: value
        for key, value in origin_binding.items()
        if key != "calibration_origin_binding_sha256"
    }
    if (
        origin_binding.get("schema_version")
        != CALIBRATION_ORIGIN_BINDING_SCHEMA
        or origin_binding.get("lineage_law")
        != LCB_CALIBRATION_ORIGIN_INPUT_LAW
        or origin_binding.get("calibration_block") != calibration_block
        or origin_binding.get("eligible_count") != len(eligible_set)
        or origin_binding.get("excluded_count")
        != len(lineup_ids) - len(eligible_set)
        or origin_binding.get("caller_supplied_eligibility_mask") is not False
        or origin_binding.get("generation_pinned") is not True
        or origin_binding.get("outer_exact_source_replay_required") is not True
        or _sha(
            origin_binding_body,
            label="calibration-origin binding",
        )
        != retained_origin_binding_hash
    ):
        _fail("calibration-origin binding differs")
    alpha_per_catalog_member = LCB_TOTAL_ALPHA / float(len(catalog))
    calibration_lower_table = _clopper_pearson_lower_table(
        worlds_per_block=worlds_per_block,
        tail_probability=alpha_per_catalog_member,
    )
    rows: list[dict[str, object]] = []
    for ordinal, (catalog_id, selected_raw, trace_raw) in enumerate(catalog):
        selected = list(selected_raw)
        trace = list(trace_raw)
        if (
            len(selected) != RANKING_DEPTH
            or len(trace) != RANKING_DEPTH
            or len(set(selected)) != RANKING_DEPTH
            or any(index not in eligible_set for index in selected)
        ):
            _fail("independent calibration candidate rank differs")
        selected_ids = [lineup_ids[index] for index in selected]
        event, event_count = _calibration_book_event(
            selected=selected,
            scores=scores,
            canonical_source_rows=canonical_source_rows,
            calibration_column_start=calibration_column_start,
            worlds_per_block=worlds_per_block,
        )
        packed_event = np.packbits(event, bitorder=PACKED_BITORDER)
        rows.append(
            {
                "catalog_ordinal": ordinal,
                "catalog_id": catalog_id,
                "rank_training_blocks": list(rank_training_blocks),
                "calibration_block": calibration_block,
                "rank_training_uses_calibration_block": False,
                "candidate_origin_uses_calibration_block": False,
                "rank_frozen_before_calibration": True,
                "calibration_origin_binding_sha256": (
                    retained_origin_binding_hash
                ),
                "ordered_lineup_ids": selected_ids,
                "ordered_lineup_ids_sha256": _sha(
                    selected_ids,
                    label="independent calibration catalog rank lineup IDs",
                ),
                "rank_training_trace_sha256": _sha(
                    trace,
                    label="independent calibration catalog training trace",
                ),
                "calibration_inclusive_230_book_hit_count": event_count,
                "calibration_world_count": worlds_per_block,
                "calibration_inclusive_230_book_hit_rate": (
                    float(event_count) / float(worlds_per_block)
                ),
                "calibration_cp_lower": float(
                    calibration_lower_table[event_count]
                ),
                "calibration_event_vector_sha256": sha256(
                    memoryview(
                        np.ascontiguousarray(packed_event, dtype=np.uint8)
                    ).cast("B")
                ).hexdigest(),
            }
        )
    chosen = min(
        rows,
        key=lambda row: (
            -float(row["calibration_cp_lower"]),
            -int(row["calibration_inclusive_230_book_hit_count"]),
            int(row["catalog_ordinal"]),
        ),
    )
    chosen_ordinal = int(chosen["catalog_ordinal"])
    chosen_id, chosen_selected_raw, chosen_trace_raw = catalog[chosen_ordinal]
    chosen_selected = list(chosen_selected_raw)
    chosen_trace = [
        {
            **dict(row),
            "meta_catalog_source_id": chosen_id,
            "meta_rank_trained_without_calibration": True,
        }
        for row in chosen_trace_raw
    ]
    calibration_body = {
        "schema_version": "independent-calibration-tail-lcb-meta-selection/v1",
        "calibration_block_law": LCB_CALIBRATION_BLOCK_LAW,
        "rank_training_blocks": list(rank_training_blocks),
        "calibration_block": calibration_block,
        "rank_training_matrix_sha256": rank_training_matrix_sha256,
        "calibration_matrix_sha256": calibration_matrix_sha256,
        "calibration_origin_law": LCB_CALIBRATION_ORIGIN_LAW,
        "calibration_origin_eligible_count": len(eligible_set),
        "calibration_origin_binding": origin_binding,
        "calibration_origin_binding_sha256": retained_origin_binding_hash,
        "catalog_ids": list(LCB_CATALOG_IDS),
        "catalog_size": len(LCB_CATALOG_IDS),
        "total_alpha": LCB_TOTAL_ALPHA,
        "alpha_per_catalog_member": alpha_per_catalog_member,
        "confidence_level": LCB_CONFIDENCE_LEVEL,
        "multiplicity_law": LCB_MULTIPLICITY_LAW,
        "catalog_ranks_frozen_before_calibration": True,
        "calibration_excluded_from_every_rank_search": True,
        "calibration_origin_excluded_from_every_rank_search": True,
        "catalog": rows,
        "catalog_sha256": _sha(rows, label="independent calibration catalog"),
        "chosen_catalog_ordinal": chosen_ordinal,
        "chosen_catalog_id": chosen_id,
        "chosen_exact_rank80_calibration_cp_lower": chosen[
            "calibration_cp_lower"
        ],
        "bound_scope": "chosen-exact-rank80-book-only",
        "prefix_confidence_claim": False,
        "selection_calibration_independence_required": True,
        "outer_exact_source_replay_required": True,
        "evidence_role": "standalone-diagnostic-nonpublication-only",
        **_false_authorities(),
    }
    calibration_body["calibration_receipt_sha256"] = _sha(
        calibration_body, label="independent calibration receipt"
    )
    return chosen_selected, chosen_trace, calibration_body


def _book_metrics(
    *,
    selected: Sequence[int],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    packed_by_block: Sequence[np.ndarray],
    world_count: int,
) -> dict[str, object]:
    current_max: np.ndarray | None = None
    covered = [
        np.zeros(packed.shape[1], dtype=np.uint8) for packed in packed_by_block
    ]
    for index in selected:
        row = _score_rows(scores, canonical_source_rows, index, index + 1)[0]
        current_max = (
            row.copy() if current_max is None else np.maximum(current_max, row)
        )
        for block_ordinal, packed in enumerate(packed_by_block):
            np.bitwise_or(
                covered[block_ordinal],
                packed[index],
                out=covered[block_ordinal],
            )
    if current_max is None:
        _fail("book metrics require a nonempty selected prefix")
    event_count = sum(
        int(_POPCOUNT[value].sum(dtype=np.int64)) for value in covered
    )
    return {
        "fit_book_expected_max_dk": float(current_max.mean(dtype=np.float64)),
        "fit_book_inclusive_230_union_count": event_count,
        "fit_book_inclusive_230_union_rate": (
            float(event_count) / float(world_count)
        ),
    }


def _book(
    *,
    strategy: Mapping[str, object],
    budget: int,
    selected: Sequence[int],
    trace: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    packed_by_block: Sequence[np.ndarray],
    fit_scope_id: str,
    input_binding_sha256: str,
) -> dict[str, object]:
    prefix = list(selected[:budget])
    prefix_ids = [lineup_ids[index] for index in prefix]
    trace_prefix = list(trace[:budget])
    metrics = _book_metrics(
        selected=prefix,
        scores=scores,
        canonical_source_rows=canonical_source_rows,
        packed_by_block=packed_by_block,
        world_count=scores.shape[1],
    )
    body = {
        "schema_version": BOOK_SCHEMA,
        "strategy_id": strategy["strategy_id"],
        "strategy_sha256": strategy["strategy_sha256"],
        "fit_scope_id": fit_scope_id,
        "input_binding_sha256": input_binding_sha256,
        "entry_budget": budget,
        "selected_count": len(prefix),
        "ordered_canonical_lineup_indices": prefix,
        "ordered_lineup_ids": prefix_ids,
        "ordered_lineup_ids_sha256": _sha(
            prefix_ids, label="roadmap retrieval book lineup IDs"
        ),
        "ranking_prefix_sha256": _sha(
            {"indices": prefix, "lineup_ids": prefix_ids},
            label="roadmap retrieval ranking prefix",
        ),
        "trace_prefix_sha256": _sha(
            trace_prefix, label="roadmap retrieval trace prefix"
        ),
        "prefix_replay_exact": True,
        **metrics,
        "evidence_role": "standalone-diagnostic-nonpublication-only",
        **_false_authorities(),
    }
    body["book_sha256"] = _sha(body, label="roadmap retrieval book")
    return body


def _selector_receipt(
    *,
    strategy: Mapping[str, object],
    selected: Sequence[int],
    trace: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
    scores: np.ndarray,
    canonical_source_rows: np.ndarray,
    packed_by_block: Sequence[np.ndarray],
    fit_scope_id: str,
    fit_scope_binding_sha256: str,
    input_binding_sha256: str,
    independent_calibration_receipt: Mapping[str, object] | None,
) -> dict[str, object]:
    if len(selected) != RANKING_DEPTH or len(trace) != RANKING_DEPTH:
        _fail("roadmap selector must materialize one exact rank 80")
    selected_ids = [lineup_ids[index] for index in selected]
    books = [
        _book(
            strategy=strategy,
            budget=budget,
            selected=selected,
            trace=trace,
            lineup_ids=lineup_ids,
            scores=scores,
            canonical_source_rows=canonical_source_rows,
            packed_by_block=packed_by_block,
            fit_scope_id=fit_scope_id,
            input_binding_sha256=input_binding_sha256,
        )
        for budget in ENTRY_BUDGETS
    ]
    body = {
        "schema_version": SELECTOR_SCHEMA,
        "strategy": dict(strategy),
        "strategy_id": strategy["strategy_id"],
        "strategy_sha256": strategy["strategy_sha256"],
        "implementation_id": IMPLEMENTATION_ID,
        "implementation_sha256": EXPECTED_IMPLEMENTATION_SHA256,
        "fit_scope_id": fit_scope_id,
        "fit_scope_binding_sha256": fit_scope_binding_sha256,
        "input_binding_sha256": input_binding_sha256,
        "ranking_depth": RANKING_DEPTH,
        "selected_count": len(selected),
        "ordered_canonical_lineup_indices": list(selected),
        "ordered_lineup_ids": selected_ids,
        "ordered_lineup_ids_sha256": _sha(
            selected_ids, label="roadmap selector lineup IDs"
        ),
        "ranking_sha256": _sha(
            {"indices": list(selected), "lineup_ids": selected_ids},
            label="roadmap selector ranking",
        ),
        "trace_count": len(trace),
        "trace": list(trace),
        "trace_sha256": _sha(list(trace), label="roadmap selector trace"),
        "independent_calibration_receipt": (
            None
            if independent_calibration_receipt is None
            else dict(independent_calibration_receipt)
        ),
        "independent_calibration_receipt_sha256": (
            None
            if independent_calibration_receipt is None
            else independent_calibration_receipt["calibration_receipt_sha256"]
        ),
        "entry_budgets": list(ENTRY_BUDGETS),
        "books": books,
        "book_sha256s": [book["book_sha256"] for book in books],
        "book_sha256s_sha256": _sha(
            [book["book_sha256"] for book in books],
            label="roadmap selector book hashes",
        ),
        "prefix_stability_exact": True,
        "fit_columns_only": True,
        "heldout_scores_present": False,
        "realized_outcomes_present": False,
        "evidence_role": "standalone-diagnostic-nonpublication-only",
        **_false_authorities(),
    }
    body["selector_receipt_sha256"] = _sha(
        body, label="roadmap selector receipt"
    )
    return body


def run_extreme_tail_roadmap_retrieval_v1(
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    candidate_mask_sha256: str,
    occurrence_lineage_sha256: str,
    calibration_origin_lineage_artifact: Mapping[str, object],
    calibration_origin_lineage_artifact_identity: Mapping[str, object],
    source_manifest_identity: Mapping[str, object],
    source_member_identity: Mapping[str, object],
    source_score_matrix_identity: Mapping[str, object],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Run both frozen laws over one exact fit scope.

    No held-out score array or realized-outcome argument exists.  A four-block
    fold matrix must have exactly those four fit blocks; an all-block final fit
    must have exactly all five R blocks.
    """
    (
        canonical_ids,
        scores,
        canonical_source_rows,
        blocks,
        fit_scope,
    ) = _validated_scope(
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
    implementation = frozen_roadmap_retrieval_implementation_v1()
    registry = frozen_roadmap_retrieval_registry_v1()
    upstream = _guard_upstream_contracts()
    calibration_block = blocks[-1]
    rank_training_blocks = blocks[:-1]
    (
        rank_eligible_indices,
        calibration_origin_binding,
    ) = _calibration_origin_eligibility(
        lineage_artifact=calibration_origin_lineage_artifact,
        lineage_artifact_identity=(
            calibration_origin_lineage_artifact_identity
        ),
        canonical_ids=canonical_ids,
        training_blocks=blocks,
        calibration_block=calibration_block,
        fit_scope=fit_scope,
    )
    rank_eligible_ids = [
        canonical_ids[int(index)] for index in rank_eligible_indices
    ]
    rank_eligible_source_rows = canonical_source_rows[rank_eligible_indices]
    rank_training_column_stop = len(rank_training_blocks) * worlds_per_block
    rank_training_scores = scores[:, :rank_training_column_stop]
    cp_training_transform_table = _clopper_pearson_lower_table(
        worlds_per_block=worlds_per_block,
        tail_probability=(
            CP_TRAINING_TRANSFORM_ALPHA / float(len(rank_training_blocks))
        ),
    )
    calibration_cp_lower_table = _clopper_pearson_lower_table(
        worlds_per_block=worlds_per_block,
        tail_probability=(LCB_TOTAL_ALPHA / float(len(LCB_CATALOG_IDS))),
    )
    cp_training_transform_table_hash = _float64_array_sha256(
        cp_training_transform_table,
        label="cp-transformed-training-utility-lookup",
    )
    calibration_cp_lower_table_hash = _float64_array_sha256(
        calibration_cp_lower_table,
        label="independent-calibration-clopper-pearson-lower-lookup",
    )
    rank_training_matrix_hash = _canonical_score_slice_sha256(
        scores=scores,
        canonical_source_rows=rank_eligible_source_rows,
        column_start=0,
        column_stop=rank_training_column_stop,
        label="meta-rank-training-score-matrix",
    )
    calibration_matrix_hash = _canonical_score_slice_sha256(
        scores=scores,
        canonical_source_rows=rank_eligible_source_rows,
        column_start=rank_training_column_stop,
        column_stop=rank_training_column_stop + worlds_per_block,
        label="meta-independent-calibration-score-matrix",
    )
    input_body = {
        "schema_version": INPUT_BINDING_SCHEMA,
        "fit_scope_id": fit_scope["fit_scope_id"],
        "fit_scope_binding": fit_scope,
        "fit_scope_binding_sha256": fit_scope["fit_scope_binding_sha256"],
        "candidate_mask_sha256": fit_scope["candidate_mask_sha256"],
        "occurrence_lineage_sha256": fit_scope["occurrence_lineage_sha256"],
        "score_matrix_binding": fit_scope["score_matrix_binding"],
        "source_manifest_identity": fit_scope["source_manifest_identity"],
        "source_member_identity": fit_scope["source_member_identity"],
        "training_blocks": list(blocks),
        "heldout_block_identifier_only": heldout_block,
        "worlds_per_block": worlds_per_block,
        "fit_world_count": scores.shape[1],
        "tail_threshold_dk": TAIL_THRESHOLD_DK,
        "tail_operator": TAIL_OPERATOR,
        "lcb_total_alpha": LCB_TOTAL_ALPHA,
        "lcb_confidence_level": LCB_CONFIDENCE_LEVEL,
        "lcb_calibration_block_law": LCB_CALIBRATION_BLOCK_LAW,
        "lcb_rank_training_blocks": list(rank_training_blocks),
        "lcb_calibration_block": calibration_block,
        "lcb_calibration_origin_law": LCB_CALIBRATION_ORIGIN_LAW,
        "lcb_calibration_origin_eligible_count": len(rank_eligible_indices),
        "lcb_calibration_origin_excluded_count": (
            len(canonical_ids) - len(rank_eligible_indices)
        ),
        "lcb_calibration_origin_binding": calibration_origin_binding,
        "lcb_calibration_origin_binding_sha256": calibration_origin_binding[
            "calibration_origin_binding_sha256"
        ],
        "lcb_catalog_ids": list(LCB_CATALOG_IDS),
        "lcb_catalog_size": len(LCB_CATALOG_IDS),
        "lcb_alpha_per_catalog_member": (
            LCB_TOTAL_ALPHA / float(len(LCB_CATALOG_IDS))
        ),
        "lcb_calibration_lower_lookup_sha256": (
            calibration_cp_lower_table_hash
        ),
        "lcb_rank_training_matrix_sha256": rank_training_matrix_hash,
        "lcb_calibration_matrix_sha256": calibration_matrix_hash,
        "cp_training_transform_shape_alpha": CP_TRAINING_TRANSFORM_ALPHA,
        "cp_training_transform_probability_per_block": (
            CP_TRAINING_TRANSFORM_ALPHA / float(len(rank_training_blocks))
        ),
        "cp_training_transform_lookup_sha256": (
            cp_training_transform_table_hash
        ),
        "cp_training_transform_confidence_claim": False,
        "cp_training_transform_coverage_claim": False,
        "redundancy_penalty_dk_per_unit_overlap": (
            REDUNDANCY_PENALTY_DK_PER_UNIT_OVERLAP
        ),
        "implementation_id": IMPLEMENTATION_ID,
        "implementation_sha256": EXPECTED_IMPLEMENTATION_SHA256,
        "strategy_registry_sha256": _sha(
            registry, label="roadmap retrieval registry"
        ),
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "numerical_runtime": {
            "numpy_version": NUMPY_VERSION,
            "scipy_version": SCIPY_VERSION,
        },
        "upstream_contracts": upstream,
        "fit_score_columns_only": True,
        "heldout_score_columns_present": False,
        "realized_outcomes_present": False,
        "require_production_width": require_production_width,
        "evidence_role": "standalone-diagnostic-nonpublication-only",
        "outer_exact_source_replay_required": True,
        **_false_authorities(),
    }
    input_binding = dict(input_body)
    input_binding["input_binding_sha256"] = _sha(
        input_binding, label="roadmap retrieval input binding"
    )
    input_hash = str(input_binding["input_binding_sha256"])

    packed_by_block = _pack_ge230_by_block(
        scores=scores,
        canonical_source_rows=canonical_source_rows,
        block_count=len(blocks),
        worlds_per_block=worlds_per_block,
    )
    event_matrix_hash = _signature_sha256(
        packed_by_block,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
    )
    rank_training_means = _row_means(
        rank_training_scores, rank_eligible_source_rows
    )
    rank_training_packed = [
        np.ascontiguousarray(packed[rank_eligible_indices], dtype=np.uint8)
        for packed in packed_by_block[:-1]
    ]
    cp_training_selected, cp_training_trace = (
        _select_cp_transformed_training_utility(
            packed_by_block=rank_training_packed,
            training_blocks=rank_training_blocks,
            worlds_per_block=worlds_per_block,
            lineup_ids=rank_eligible_ids,
            means=rank_training_means,
            transform_table=cp_training_transform_table,
        )
    )
    catalog_correlation_selected, catalog_correlation_trace = (
        _select_correlation_aware_expected_max(
            scores=rank_training_scores,
            canonical_source_rows=rank_eligible_source_rows,
            packed_by_block=rank_training_packed,
            training_blocks=rank_training_blocks,
            worlds_per_block=worlds_per_block,
            lineup_ids=rank_eligible_ids,
            means=rank_training_means,
        )
    )
    cp_training_selected = [
        int(rank_eligible_indices[index]) for index in cp_training_selected
    ]
    cp_training_trace = [
        {
            **row,
            "canonical_lineup_index": int(
                rank_eligible_indices[int(row["canonical_lineup_index"])]
            ),
        }
        for row in cp_training_trace
    ]
    catalog_correlation_selected = [
        int(rank_eligible_indices[index])
        for index in catalog_correlation_selected
    ]
    catalog_correlation_trace = [
        {
            **row,
            "canonical_lineup_index": int(
                rank_eligible_indices[int(row["canonical_lineup_index"])]
            ),
        }
        for row in catalog_correlation_trace
    ]
    lcb_selected, lcb_trace, independent_calibration = (
        _select_independent_calibration_meta_rank(
            catalog=(
                (
                    LCB_CATALOG_IDS[0],
                    cp_training_selected,
                    cp_training_trace,
                ),
                (
                    LCB_CATALOG_IDS[1],
                    catalog_correlation_selected,
                    catalog_correlation_trace,
                ),
            ),
            lineup_ids=canonical_ids,
            scores=scores,
            canonical_source_rows=canonical_source_rows,
            rank_training_blocks=rank_training_blocks,
            calibration_block=calibration_block,
            worlds_per_block=worlds_per_block,
            rank_training_matrix_sha256=rank_training_matrix_hash,
            calibration_matrix_sha256=calibration_matrix_hash,
            eligible_canonical_indices=rank_eligible_indices,
            calibration_origin_binding=calibration_origin_binding,
        )
    )
    means = _row_means(scores, canonical_source_rows)
    correlation_selected, correlation_trace = (
        _select_correlation_aware_expected_max(
            scores=scores,
            canonical_source_rows=canonical_source_rows,
            packed_by_block=packed_by_block,
            training_blocks=blocks,
            worlds_per_block=worlds_per_block,
            lineup_ids=canonical_ids,
            means=means,
        )
    )
    selectors = [
        _selector_receipt(
            strategy=registry[0],
            selected=lcb_selected,
            trace=lcb_trace,
            lineup_ids=canonical_ids,
            scores=scores,
            canonical_source_rows=canonical_source_rows,
            packed_by_block=packed_by_block,
            fit_scope_id=str(fit_scope["fit_scope_id"]),
            fit_scope_binding_sha256=str(fit_scope["fit_scope_binding_sha256"]),
            input_binding_sha256=input_hash,
            independent_calibration_receipt=independent_calibration,
        ),
        _selector_receipt(
            strategy=registry[1],
            selected=correlation_selected,
            trace=correlation_trace,
            lineup_ids=canonical_ids,
            scores=scores,
            canonical_source_rows=canonical_source_rows,
            packed_by_block=packed_by_block,
            fit_scope_id=str(fit_scope["fit_scope_id"]),
            fit_scope_binding_sha256=str(fit_scope["fit_scope_binding_sha256"]),
            input_binding_sha256=input_hash,
            independent_calibration_receipt=None,
        ),
    ]
    body = {
        "schema_version": RECEIPT_SCHEMA,
        "receipt_law_id": RECEIPT_LAW_ID,
        "fit_scope_id": fit_scope["fit_scope_id"],
        "fit_scope_binding_sha256": fit_scope["fit_scope_binding_sha256"],
        "input_binding": input_binding,
        "input_binding_sha256": input_hash,
        "implementation": implementation,
        "implementation_sha256": EXPECTED_IMPLEMENTATION_SHA256,
        "strategy_registry": registry,
        "strategy_registry_sha256": _sha(
            registry, label="roadmap retrieval registry"
        ),
        "inclusive_230_event_matrix_sha256": event_matrix_hash,
        "selector_count": len(selectors),
        "selectors": selectors,
        "selector_receipt_sha256s": [
            selector["selector_receipt_sha256"] for selector in selectors
        ],
        "selector_receipt_sha256s_sha256": _sha(
            [selector["selector_receipt_sha256"] for selector in selectors],
            label="roadmap selector receipt hashes",
        ),
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "fit_score_columns_only": True,
        "heldout_score_columns_present": False,
        "realized_outcomes_present": False,
        "evidence_role": "standalone-diagnostic-nonpublication-only",
        "standalone_source_authority": False,
        "outer_exact_source_replay_required": True,
        **_false_authorities(),
    }
    body["receipt_sha256"] = _sha(body, label="roadmap retrieval receipt")
    return body


def validate_extreme_tail_roadmap_retrieval_v1(
    receipt: object,
    *,
    lineup_ids: Sequence[str],
    fit_scores: np.ndarray,
    training_blocks: Sequence[str],
    heldout_block: str | None,
    worlds_per_block: int,
    candidate_mask_sha256: str,
    occurrence_lineage_sha256: str,
    calibration_origin_lineage_artifact: Mapping[str, object],
    calibration_origin_lineage_artifact_identity: Mapping[str, object],
    source_manifest_identity: Mapping[str, object],
    source_member_identity: Mapping[str, object],
    source_score_matrix_identity: Mapping[str, object],
    require_production_width: bool = True,
) -> dict[str, object]:
    """Replay a retained receipt against its exact fit matrix and lineage."""
    item = _mapping(receipt, label="roadmap retrieval receipt")
    if item.get("schema_version") != RECEIPT_SCHEMA:
        _fail("roadmap retrieval receipt schema differs")
    retained_hash = item.get("receipt_sha256")
    if type(retained_hash) is not str:
        _fail("roadmap retrieval receipt hash is absent")
    remainder = {
        key: value for key, value in item.items() if key != "receipt_sha256"
    }
    if _sha(remainder, label="roadmap retrieval receipt") != retained_hash:
        _fail("roadmap retrieval receipt self-hash differs")
    expected = run_extreme_tail_roadmap_retrieval_v1(
        lineup_ids=lineup_ids,
        fit_scores=fit_scores,
        training_blocks=training_blocks,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        candidate_mask_sha256=candidate_mask_sha256,
        occurrence_lineage_sha256=occurrence_lineage_sha256,
        calibration_origin_lineage_artifact=(
            calibration_origin_lineage_artifact
        ),
        calibration_origin_lineage_artifact_identity=(
            calibration_origin_lineage_artifact_identity
        ),
        source_manifest_identity=source_manifest_identity,
        source_member_identity=source_member_identity,
        source_score_matrix_identity=source_score_matrix_identity,
        require_production_width=require_production_width,
    )
    if _canonical(item, label="retained roadmap receipt") != _canonical(
        expected, label="replayed roadmap receipt"
    ):
        _fail("roadmap retrieval receipt differs from canonical replay")
    return expected


__all__ = [
    "CORRELATION_AWARE_STRATEGY_ID",
    "CorpusExtremeTailRoadmapRetrievalError",
    "ENTRY_BUDGETS",
    "EXPECTED_IMPLEMENTATION_SHA256",
    "EXPECTED_STRATEGY_SHA256S",
    "RANKING_DEPTH",
    "TAIL_LCB_STRATEGY_ID",
    "frozen_roadmap_retrieval_implementation_v1",
    "frozen_roadmap_retrieval_registry_v1",
    "run_extreme_tail_roadmap_retrieval_v1",
    "validate_extreme_tail_roadmap_retrieval_v1",
]
