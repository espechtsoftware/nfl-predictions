"""Outcome-blind full-union R6 lane for the first historical score release.

This module separates the part of R6 that is already ready to test from the
still-richer matchup-admission source.  It exact-reconstructs an accepted
Foundry-v12 slate, admits the complete fold-eligible cross-arm union, and runs
the seven frozen R6-v2 retrieval laws plus one separately versioned strict-230
coverage law.  Five rotated simulated-world folds and one distinct all-block
final fit are retained; every book is an immutable exact-80 rank whose 4/14
prefixes can be projected later without rerunning selection.

The lane never reads a matchup source or a realized outcome.  It owns no
storage client, publisher, warehouse client, graph writer, live-policy seam,
or production authority.  A later panel release must still exact-bind all 54
accepted tasks before an outcome snapshot may be opened for score-once
grading.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as execution
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import _score_matrix_sha256


SURFACE_SCHEMA: Final = "corpus-r6-full-union-fast-lane-surface/v1"
SCOPE_SCHEMA: Final = "corpus-r6-full-union-fast-lane-scope/v1"
EXECUTION_SCHEMA: Final = "corpus-r6-full-union-fast-lane-execution/v1"
STRICT_230_STRATEGY_ID: Final = "strict-230-coverage-v1"
STRATEGY_COUNT: Final = 8
SCOPE_COUNT: Final = 6
BOOKS_PER_SCOPE: Final = STRATEGY_COUNT
BOOKS_PER_SLATE: Final = SCOPE_COUNT * BOOKS_PER_SCOPE
ENTRY_BUDGET: Final = runner.ENTRY_BUDGET
PREFIX_SIZES: Final = (4, 14, 80)
NEUTRAL_SEED_ROOT: Final = "not-used-full-union-fast-lane-v1"

_FALSE_EXECUTION_AUTHORITY_FIELDS: Final = (
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
)

ReadExact = Callable[[Mapping[str, object]], bytes]


class CorpusR6FullUnionFastLaneV1Error(ValueError):
    """The full-union lane cannot preserve its fixed inputs or book lattice."""


def _fail(message: str) -> None:
    raise CorpusR6FullUnionFastLaneV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    body[field] = batch.canonical_sha256(body)
    return body


def _validate_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = value.get(field)
    if (
        type(retained) is not str
        or len(retained) != 64
        or any(character not in "0123456789abcdef" for character in retained)
    ):
        _fail(f"{label} {field} must be lowercase SHA-256")
    body = {key: item for key, item in value.items() if key != field}
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _strict_230_strategy_v1() -> dict[str, object]:
    """Build the separately versioned T230 selector without changing R6-v2."""
    try:
        strategy = retrieval._strategy(
            ordinal=7,
            strategy_id=STRICT_230_STRATEGY_ID,
            method="greedy-threshold-coverage-v1",
            entry_budget=ENTRY_BUDGET,
            parameters={"threshold": 230.0, "operator": ">"},
            tie_law=[
                "largest-marginal-new-world-count",
                "largest-individual-threshold-count",
                "largest-discovery-mean-score",
                "ascending-lineup-id",
            ],
            description=(
                "Strict simulated-world coverage above 230 DK points; an "
                "outcome-blind T230 retrieval arm over the accepted full union."
            ),
        )
    except retrieval.CorpusRetrievalError as exc:
        raise CorpusR6FullUnionFastLaneV1Error(str(exc)) from exc
    if (
        strategy.get("ordinal") != 7
        or strategy.get("strategy_id") != STRICT_230_STRATEGY_ID
        or strategy.get("method") != "greedy-threshold-coverage-v1"
        or strategy.get("entry_budget") != ENTRY_BUDGET
        or strategy.get("parameters") != {"threshold": 230.0, "operator": ">"}
        or strategy.get("selection_inputs")
        != "discovery-block-simulated-scores-only"
    ):
        _fail("strict-230 retrieval law differs")
    return strategy


def frozen_full_union_strategies_v1() -> list[dict[str, object]]:
    """Return seven byte-identical v2 strategies plus the strict-230 arm."""
    try:
        inherited = runner._validate_strategy_registry()
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6FullUnionFastLaneV1Error(str(exc)) from exc
    strategies = [dict(value) for value in inherited] + [_strict_230_strategy_v1()]
    if (
        len(strategies) != STRATEGY_COUNT
        or [int(value["ordinal"]) for value in strategies]
        != list(range(STRATEGY_COUNT))
        or len({str(value["strategy_id"]) for value in strategies})
        != STRATEGY_COUNT
        or len({str(value["strategy_sha256"]) for value in strategies})
        != STRATEGY_COUNT
    ):
        _fail("full-union strategy registry differs")
    return strategies


def _run_scope_v1(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    heldout_block: str | None,
    worlds_per_block: int,
    require_authoritative: bool,
    validated_reconstruction_sha256: str | None = None,
) -> dict[str, object]:
    """Run one fold/final scope with complete-union admission only."""
    if heldout_block is not None and heldout_block not in rw.WORLD_BLOCKS:
        _fail("heldout block is not registered")
    try:
        candidates = runner._validate_provenance(provenance)
        dose_authority = runner._dose_authority(
            provenance=provenance,
            admission_m=runner.DEFAULT_ADMISSION_M,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
        scores = np.asarray(union_scores)
        if (
            scores.dtype != np.dtype(np.float64)
            or scores.ndim != 2
            or scores.shape
            != (len(candidates), len(rw.WORLD_BLOCKS) * worlds_per_block)
            or not np.isfinite(scores).all()
        ):
            _fail("canonical union score matrix shape/dtype/content differs")
        reconstruction_sha256 = (
            runner._validate_reconstruction_input(
                provenance=provenance,
                union_scores=scores,
                reconstruction_receipt=reconstruction_receipt,
            )
            if validated_reconstruction_sha256 is None
            else validated_reconstruction_sha256
        )
        view = runner.build_fit_candidate_view(
            provenance,
            heldout_block=heldout_block,
            dose_authority=dose_authority,
        )
        eligible_ids = [
            str(row["lineup_id"])
            for row in _sequence(
                view.get("eligible_candidates"), label="eligible candidates"
            )
            if isinstance(row, Mapping)
        ]
        if eligible_ids != sorted(set(eligible_ids)) or len(eligible_ids) < ENTRY_BUDGET:
            _fail("fold-eligible full union cannot satisfy exact-80")
        admission = runner._full_union_admission(view)
        runner._validate_admission_partition(admission, eligible_ids=eligible_ids)

        candidate_ids = [str(row["lineup_id"]) for row in candidates]
        roster_by_id = {
            str(row["lineup_id"]): tuple(
                str(player_id) for player_id in row["roster_player_ids"]
            )
            for row in candidates
        }
        global_index_by_id = {
            lineup_id: index for index, lineup_id in enumerate(candidate_ids)
        }
        admitted_ids = [str(value) for value in admission["admitted_lineup_ids"]]
        admitted_global = np.asarray(
            [global_index_by_id[lineup_id] for lineup_id in admitted_ids],
            dtype=np.int64,
        )
        training_blocks = [
            block for block in rw.WORLD_BLOCKS if block != heldout_block
        ]
        training_columns = runner._block_columns(
            training_blocks, worlds_per_block=worlds_per_block
        )
        heldout_columns = (
            None
            if heldout_block is None
            else runner._block_columns(
                [heldout_block], worlds_per_block=worlds_per_block
            )
        )
        training_scores = np.ascontiguousarray(
            scores[np.ix_(admitted_global, training_columns)], dtype=np.float64
        )
        training_sha256 = _score_matrix_sha256(training_scores)
        books = [
            runner._run_book(
                strategy=strategy,
                admission=admission,
                admitted_ids=admitted_ids,
                admitted_global=admitted_global,
                training_scores=training_scores,
                training_score_matrix_sha256=training_sha256,
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
            )
            for strategy in frozen_full_union_strategies_v1()
        ]
    except KeyError as exc:
        raise CorpusR6FullUnionFastLaneV1Error(
            "full-union input omitted a required canonical field"
        ) from exc
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6FullUnionFastLaneV1Error(str(exc)) from exc
    if (
        len(books) != BOOKS_PER_SCOPE
        or len({str(book["book_id"]) for book in books}) != BOOKS_PER_SCOPE
        or [str(book["strategy_id"]) for book in books]
        != [str(strategy["strategy_id"]) for strategy in frozen_full_union_strategies_v1()]
    ):
        _fail("full-union scope book lattice differs")
    body = {
        "schema_version": SCOPE_SCHEMA,
        "fit_scope_id": view["fit_scope_id"],
        "reconstruction_sha256": reconstruction_sha256,
        "training_blocks": training_blocks,
        "heldout_block": heldout_block,
        "worlds_per_block": worlds_per_block,
        "dose_authority": dose_authority,
        "require_authoritative": require_authoritative,
        "candidate_view": view,
        "admission": admission,
        "admission_mode": "complete-fold-eligible-cross-arm-union",
        "matchup_source_read": False,
        "matchup_admission_read": False,
        "neutral_control_read": False,
        "strategy_registry": frozen_full_union_strategies_v1(),
        "strategy_count": STRATEGY_COUNT,
        "book_count": len(books),
        "books": books,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    return _with_hash(body, field="fit_scope_sha256")


def run_full_union_surface_v1(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Run all five rotated folds and the distinct all-block final fit."""
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    effective_worlds = (
        rw.WORLDS_PER_BLOCK if worlds_per_block is None else worlds_per_block
    )
    if type(effective_worlds) is not int or effective_worlds < 1:
        _fail("worlds_per_block must be a positive exact integer")
    if (
        not require_authoritative
        and effective_worlds != retrieval.WORLDS_PER_BLOCK
    ):
        _fail(
            "non-authoritative fixture world width differs from the retrieval "
            "selector width"
        )
    try:
        reconstruction_sha256 = runner._validate_reconstruction_input(
            provenance=provenance,
            union_scores=np.asarray(union_scores),
            reconstruction_receipt=reconstruction_receipt,
        )
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6FullUnionFastLaneV1Error(str(exc)) from exc
    scopes = [
        _run_scope_v1(
            provenance=provenance,
            union_scores=union_scores,
            reconstruction_receipt=reconstruction_receipt,
            heldout_block=heldout,
            worlds_per_block=effective_worlds,
            require_authoritative=require_authoritative,
            validated_reconstruction_sha256=reconstruction_sha256,
        )
        for heldout in (*rw.WORLD_BLOCKS, None)
    ]
    if (
        len(scopes) != SCOPE_COUNT
        or sum(int(scope["book_count"]) for scope in scopes) != BOOKS_PER_SLATE
        or scopes[-1]["heldout_block"] is not None
        or scopes[-1]["training_blocks"] != list(rw.WORLD_BLOCKS)
    ):
        _fail("full-union surface scope lattice differs")
    body = {
        "schema_version": SURFACE_SCHEMA,
        "slate": dict(_mapping(provenance, label="candidate provenance")["slate"]),
        "candidate_provenance_sha256": provenance["candidate_provenance_sha256"],
        "reconstruction_sha256": reconstruction_sha256,
        "strategy_registry": frozen_full_union_strategies_v1(),
        "strategy_registry_sha256": batch.canonical_sha256(
            frozen_full_union_strategies_v1()
        ),
        "scope_count": SCOPE_COUNT,
        "books_per_scope": BOOKS_PER_SCOPE,
        "book_count": BOOKS_PER_SLATE,
        "prefix_sizes": list(PREFIX_SIZES),
        "scopes": scopes,
        "rotated_simulated_fold_count": len(rw.WORLD_BLOCKS),
        "final_fit_is_distinct_all_block_refit": True,
        "full_union_only": True,
        "matchup_source_read": False,
        "uses_realized_outcomes": False,
        "evidence_tier": "outcome-blind-simulated-analysis",
        "promotion_authority": False,
    }
    return _with_hash(body, field="full_union_surface_sha256")


def validate_full_union_surface_v1(
    value: object,
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Canonical replay validation of every selected book and marginal trace."""
    item = _mapping(value, label="full-union surface")
    _validate_hash(
        item, field="full_union_surface_sha256", label="full-union surface"
    )
    expected = run_full_union_surface_v1(
        provenance=provenance,
        union_scores=union_scores,
        reconstruction_receipt=reconstruction_receipt,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("full-union surface canonical replay differs")
    return expected


def execute_one_accepted_slate_full_union_v1(
    *,
    validated_panel_index: Mapping[str, object],
    panel_index_identity: Mapping[str, object],
    accepted_slate_membership: Mapping[str, object],
    task_acceptance_identity: Mapping[str, object],
    carrier_identity: Mapping[str, object],
    read_exact: ReadExact,
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Exact-reconstruct one accepted Foundry slate, then run the full lane."""
    try:
        accepted = execution.reconstruct_one_accepted_v12_slate(
            validated_panel_index=validated_panel_index,
            panel_index_identity=panel_index_identity,
            accepted_slate_membership=accepted_slate_membership,
            task_acceptance_identity=task_acceptance_identity,
            carrier_identity=carrier_identity,
            read_exact=read_exact,
            require_authoritative=require_authoritative,
        )
    except execution.CorpusR6V2OneSlateExecutionError as exc:
        raise CorpusR6FullUnionFastLaneV1Error(str(exc)) from exc
    reconstructed = accepted.reconstructed
    surface = run_full_union_surface_v1(
        provenance=reconstructed.provenance,
        union_scores=reconstructed.union_scores,
        reconstruction_receipt=reconstructed.reconstruction_receipt,
        worlds_per_block=worlds_per_block,
        require_authoritative=require_authoritative,
    )
    import_receipt = _mapping(
        accepted.imported.compatibility_receipt, label="compatibility import"
    )
    body = {
        "schema_version": EXECUTION_SCHEMA,
        "slate_id": accepted.slate_id,
        "panel_index_identity": dict(accepted.panel_index_identity),
        "panel_index_sha256": accepted.panel_index_sha256,
        "accepted_slate_membership": dict(accepted.accepted_slate_membership),
        "accepted_slate_membership_sha256": batch.canonical_sha256(
            accepted.accepted_slate_membership
        ),
        "task_acceptance_identity": dict(accepted.task_acceptance_identity),
        "carrier_identity": dict(accepted.carrier_identity),
        "later_source_freeze_identity": dict(
            accepted.later_source_freeze_identity
        ),
        "world_artifact_identities": {
            key: dict(value)
            for key, value in accepted.world_artifact_identities.items()
        },
        "world_artifact_identity_set_sha256": batch.canonical_sha256(
            accepted.world_artifact_identities
        ),
        "compatibility_import_sha256": import_receipt[
            "compatibility_import_sha256"
        ],
        "candidate_provenance_sha256": reconstructed.provenance[
            "candidate_provenance_sha256"
        ],
        "reconstruction_sha256": reconstructed.reconstruction_receipt[
            "reconstruction_sha256"
        ],
        "full_union_surface": surface,
        "full_union_surface_sha256": surface["full_union_surface_sha256"],
        "verification": {
            "panel_exact_reopen_verified": True,
            "accepted_membership_binding_verified": True,
            "task_acceptance_exact_reopen_verified": True,
            "carrier_exact_reopen_verified": True,
            "world_artifact_exact_reopen_verified": True,
            "all_seven_arm_score_hashes_verified": True,
            "complete_cross_arm_union_reconstructed": True,
            "all_48_books_materialized": True,
            "matchup_source_not_read": True,
            "realized_outcomes_not_read": True,
        },
        **{field: False for field in _FALSE_EXECUTION_AUTHORITY_FIELDS},
    }
    return _with_hash(body, field="task_result_sha256")


__all__ = [
    "BOOKS_PER_SCOPE",
    "BOOKS_PER_SLATE",
    "CorpusR6FullUnionFastLaneV1Error",
    "ENTRY_BUDGET",
    "EXECUTION_SCHEMA",
    "PREFIX_SIZES",
    "SCOPE_COUNT",
    "SCOPE_SCHEMA",
    "STRICT_230_STRATEGY_ID",
    "STRATEGY_COUNT",
    "SURFACE_SCHEMA",
    "execute_one_accepted_slate_full_union_v1",
    "frozen_full_union_strategies_v1",
    "run_full_union_surface_v1",
    "validate_full_union_surface_v1",
]
