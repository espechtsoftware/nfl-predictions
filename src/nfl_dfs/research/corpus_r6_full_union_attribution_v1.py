"""Deterministic lineup-level attribution for the sealed R6 full-union grade.

This module performs no scoring and owns no object-store or outcome reader.  A
higher-level release boundary exact-reopens one frozen task result and its
already-published realized grade, then calls :func:`build_slate_attribution_v1`.
The join proves that every frozen final-union roster is the roster scored by
the grade and that every ranked book row is the lineup selected by the frozen
selector trace.

The resulting rows support descriptive fill-arm/block attribution and exact
selector attribution.  They do not claim causal fill effects, contain
per-player realized points, or attach point-in-time player traits.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as freeze
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


SLATE_ATTRIBUTION_SCHEMA: Final = (
    "corpus-r6-full-union-slate-attribution/v1"
)
CANDIDATE_PROVENANCE_RESOLUTION: Final = "arm-block-count-summary-only"
CONTEST_UNAVAILABLE_REASON: Final = (
    "full_field_standings_duplicate_tie_settlement_and_payout_ladder_not_supplied"
)
REALIZED_UNION_RANK_LAW: Final = (
    "zero-based-score-desc-lineup-id-ascending-tiebreak-not-contest-rank"
)
SELECTOR_REGRET_LAW: Final = (
    "realized-eligible-maximum-minus-selected-maximum-descriptive-only"
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")

_FALSE_AUTHORITY_FIELDS: Final = (
    "outcome_source_read",
    "additional_historical_outcome_read",
    "bigquery_client_constructed",
    "outcome_query_executed",
    "historical_scoring_licensed",
    "historical_retry_licensed",
    "historical_retune_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "promotion_authority",
    "decision_authority",
    "live_money_policy_authority",
    "causal_claims_licensed",
)

_LINEUP_FIELDS: Final = frozenset({
    "source_ordinal", "slate_id", "union_index", "lineup_id",
    "roster_player_ids", "roster_identity_sha256", "realized_score_micro",
    "realized_union_rank", "realized_score_tie_count",
    "union_maximum_score_micro", "regret_to_union_maximum_micro",
    "at_or_above_thresholds_dk", "training_origin_blocks",
    "training_source_arms", "training_occurrence_counts_by_block",
    "training_source_arms_by_block", "training_occurrence_count",
    "source_arm_count", "origin_block_count", "multi_arm_origin",
    "multi_block_origin", "selected_book_count", "selected_scope_count",
    "selected_strategy_count", "selected_any", "missed_by_every_book",
})
_SCOPE_FIELDS: Final = frozenset({
    "source_ordinal", "slate_id", "scope_ordinal", "fit_scope_id",
    "heldout_block", "training_blocks", "lineup_id", "union_index",
    "eligible", "admitted", "eligible_index", "admitted_index",
    "exclusion_reason_code", "training_origin_blocks",
    "training_source_arms", "training_occurrence_counts_by_block",
    "training_source_arms_by_block", "training_occurrence_count",
})
_BOOK_FIELDS: Final = frozenset({
    "source_ordinal", "slate_id", "scope_ordinal", "fit_scope_id",
    "heldout_block", "strategy_ordinal", "strategy_id", "strategy_sha256",
    "book_id", "book_sha256", "book_coordinate_sha256",
    "eligible_lineup_count", "selected_lineup_count",
    "selected_lineup_ids_sha256", "marginal_trace_sha256",
    "eligible_maximum_score_micro", "eligible_maximum_lineup_ids",
    "selected_maximum_score_micro", "selected_maximum_lineup_ids",
    "selector_regret_micro", "threshold_capture",
})
_SELECTION_FIELDS: Final = frozenset({
    "source_ordinal", "slate_id", "scope_ordinal", "fit_scope_id",
    "strategy_ordinal", "strategy_id", "book_id", "selection_rank",
    "lineup_id", "union_index", "realized_score_micro",
    "realized_union_rank", "at_or_above_thresholds_dk",
    "prefix_entry_counts", "selected_local_index", "selected_global_index",
    "marginal_trace", "marginal_trace_sha256",
})
_THRESHOLD_CAPTURE_FIELDS: Final = frozenset({
    "threshold_dk", "threshold_micro", "eligible_lineup_count",
    "selected_lineup_count", "selected_hit", "eligible_hit",
})

_TOP_LEVEL_FIELDS: Final = frozenset({
    "schema_version", "source_ordinal", "slate_id",
    "panel_freeze_identity", "slate_freeze_identity",
    "task_result_identity", "task_result_sha256", "slate_grade_identity",
    "slate_grade_sha256", "candidate_provenance_sha256",
    "candidate_provenance_resolution",
    "exact_generation_occurrence_rows_available",
    "player_realized_contributions_available",
    "point_in_time_player_traits_attached", "thresholds_dk",
    "realized_union_rank_law", "selector_regret_law",
    "lineup_count", "lineup_rows", "lineup_rows_sha256",
    "scope_membership_count", "scope_membership_rows",
    "scope_membership_rows_sha256", "book_count", "book_rows",
    "book_rows_sha256", "selection_count", "selection_rows",
    "selection_rows_sha256", "contest_metrics", "fill_effect_interpretation",
    "uses_realized_outcomes", "no_rescore",
    "projected_from_persisted_union_score_lookup", "complete",
    *_FALSE_AUTHORITY_FIELDS, "slate_attribution_sha256",
})


class CorpusR6FullUnionAttributionV1Error(ValueError):
    """The frozen-task/grade attribution join failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6FullUnionAttributionV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionAttributionV1Error(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionAttributionV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        _fail(f"{label} fields differ")


def _candidate_summary(
    value: object,
    *,
    slate: Mapping[str, object],
    training_blocks: Sequence[str],
    label: str,
) -> dict[str, object]:
    row = _mapping(value, label=label)
    lineup_id = row.get("lineup_id")
    roster = _sequence(row.get("roster_player_ids"), label=f"{label} roster")
    origin_blocks = _sequence(
        row.get("training_origin_blocks"), label=f"{label} origin blocks"
    )
    source_arms = _sequence(
        row.get("training_source_arms"), label=f"{label} source arms"
    )
    counts = _mapping(
        row.get("training_occurrence_counts_by_block"),
        label=f"{label} occurrence counts",
    )
    arms_by_block = _mapping(
        row.get("training_source_arms_by_block"),
        label=f"{label} arms by block",
    )
    if (
        type(lineup_id) is not str
        or not lineup_id
        or len(roster) != rw.ROSTER_SIZE
        or roster != sorted(roster)
        or len(set(roster)) != rw.ROSTER_SIZE
        or any(type(player_id) is not str or not player_id for player_id in roster)
        or canonical_lineup_id(slate, roster) != lineup_id
        or source_arms != sorted(set(source_arms))
        or any(arm not in batch.PARAMETER_SET_ORDER for arm in source_arms)
        or set(counts) != set(training_blocks)
        or set(arms_by_block) != set(training_blocks)
        or any(type(count) is not int or count < 0 for count in counts.values())
        or origin_blocks
        != [block for block in training_blocks if int(counts[block]) > 0]
        or row.get("training_occurrence_count")
        != sum(int(count) for count in counts.values())
    ):
        _fail(f"{label} candidate lineage/roster differs")
    for block in training_blocks:
        block_arms = _sequence(
            arms_by_block[block], label=f"{label} source arms for {block}"
        )
        if (
            block_arms != sorted(set(block_arms))
            or any(arm not in batch.PARAMETER_SET_ORDER for arm in block_arms)
            or (int(counts[block]) == 0) != (block_arms == [])
        ):
            _fail(f"{label} block source-arm evidence differs")
    if source_arms != sorted({
        str(arm)
        for block in training_blocks
        for arm in _sequence(arms_by_block[block], label=f"{label} block arms")
    }):
        _fail(f"{label} aggregate source-arm evidence differs")
    return {
        "lineup_id": lineup_id,
        "roster_player_ids": [str(player_id) for player_id in roster],
        "training_origin_blocks": [str(block) for block in origin_blocks],
        "training_source_arms": [str(arm) for arm in source_arms],
        "training_occurrence_counts_by_block": {
            str(block): int(counts[block]) for block in training_blocks
        },
        "training_source_arms_by_block": {
            str(block): [str(arm) for arm in _sequence(
                arms_by_block[block], label=f"{label} block arms"
            )]
            for block in training_blocks
        },
        "training_occurrence_count": int(row["training_occurrence_count"]),
    }


def _threshold_hits(score_micro: int) -> list[int]:
    return [
        int(threshold)
        for threshold in grading.THRESHOLDS_DK
        if score_micro >= int(threshold) * grading.MICRO_DK_PER_POINT
    ]


def _maximum_ids(
    lineup_ids: Sequence[str], score_by_id: Mapping[str, int],
) -> tuple[int, list[str]]:
    if not lineup_ids:
        _fail("an attribution comparison population is empty")
    maximum = max(score_by_id[lineup_id] for lineup_id in lineup_ids)
    return maximum, sorted(
        lineup_id for lineup_id in lineup_ids
        if score_by_id[lineup_id] == maximum
    )


def build_slate_attribution_v1(
    *,
    source_ordinal: int,
    slate_id: str,
    task_result: Mapping[str, object],
    realized_slate_grade: Mapping[str, object],
    panel_freeze_identity: Mapping[str, object],
    slate_freeze_identity: Mapping[str, object],
    task_result_identity: Mapping[str, object],
    slate_grade_identity: Mapping[str, object],
    candidate_provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Join one exact frozen task result to one already-published grade shard."""
    ordinal = _integer(source_ordinal, label="source ordinal")
    if ordinal >= grading.SOURCE_SLATE_COUNT:
        _fail("source ordinal is outside the 54-slate panel")
    if type(slate_id) is not str or not slate_id:
        _fail("slate ID must be nonempty")
    panel_identity = _identity(panel_freeze_identity, label="panel freeze identity")
    leaf_identity = _identity(slate_freeze_identity, label="slate freeze identity")
    result_identity = _identity(task_result_identity, label="task-result identity")
    grade_identity = _identity(slate_grade_identity, label="slate-grade identity")
    task = _mapping(task_result, label="task result")
    grade = _mapping(realized_slate_grade, label="realized slate grade")

    surface = _mapping(task.get("full_union_surface"), label="full-union surface")
    slate = _mapping(surface.get("slate"), label="surface slate")
    scopes = [_mapping(value, label="fit scope") for value in _sequence(
        surface.get("scopes"), label="fit scopes"
    )]
    strategies = [_mapping(value, label="strategy") for value in _sequence(
        surface.get("strategy_registry"), label="strategy registry"
    )]
    if (
        task.get("slate_id") != slate_id
        or slate.get("slate_id") != slate_id
        or grade.get("source_ordinal") != ordinal
        or grade.get("slate_id") != slate_id
        or grade.get("panel_freeze_identity") != panel_identity
        or grade.get("slate_freeze_identity") != leaf_identity
        or grade.get("task_result_identity") != result_identity
        or grade.get("task_result_sha256") != task.get("task_result_sha256")
        or len(scopes) != grading.SCOPES_PER_SLATE
        or len(strategies) != grading.STRATEGIES_PER_SCOPE
    ):
        _fail("task/grade panel, slate, or identity binding differs")
    _digest(task.get("task_result_sha256"), label="task-result SHA")
    _digest(grade.get("slate_grade_sha256"), label="slate-grade SHA")

    final_scope = scopes[-1]
    final_view = _mapping(
        final_scope.get("candidate_view"), label="final candidate view"
    )
    final_blocks = [str(block) for block in _sequence(
        final_scope.get("training_blocks"), label="final training blocks"
    )]
    final_candidates = [
        _candidate_summary(
            value,
            slate=slate,
            training_blocks=final_blocks,
            label=f"final candidate[{index}]",
        )
        for index, value in enumerate(_sequence(
            final_view.get("eligible_candidates"), label="final candidates"
        ))
    ]
    final_ids = [str(row["lineup_id"]) for row in final_candidates]
    if (
        final_ids != sorted(set(final_ids))
        or len(final_ids) < 80
        or final_view.get("excluded_count") != 0
    ):
        _fail("final-union candidate population repeats, omits, or excludes a lineup")
    final_by_id = {str(row["lineup_id"]): row for row in final_candidates}
    union_index_by_id = {
        lineup_id: union_index for union_index, lineup_id in enumerate(final_ids)
    }

    score_rows = [_mapping(value, label="union score row") for value in _sequence(
        grade.get("union_score_rows"), label="union score rows"
    )]
    if len(score_rows) != len(final_candidates):
        _fail("grade/frozen final-union lineup count differs")
    score_by_id: dict[str, int] = {}
    for union_index, (candidate, score_row) in enumerate(
        zip(final_candidates, score_rows, strict=True)
    ):
        lineup_id = str(candidate["lineup_id"])
        roster = list(candidate["roster_player_ids"])
        score = score_row.get("realized_score_micro")
        if (
            score_row.get("source_ordinal") != ordinal
            or score_row.get("union_index") != union_index
            or score_row.get("lineup_id") != lineup_id
            or score_row.get("roster_identity_sha256")
            != canonical_sha256(roster)
            or type(score) is not int
            or lineup_id in score_by_id
        ):
            _fail("grade/frozen final-union lineup or roster join differs")
        score_by_id[lineup_id] = int(score)
    realized_order = sorted(final_ids, key=lambda item: (-score_by_id[item], item))
    realized_rank_by_id = {
        lineup_id: rank for rank, lineup_id in enumerate(realized_order)
    }
    score_tie_count = Counter(score_by_id.values())
    union_maximum, _union_max_ids = _maximum_ids(final_ids, score_by_id)

    scope_rows: list[dict[str, object]] = []
    eligible_ids_by_scope: dict[int, list[str]] = {}
    admitted_index_by_scope: dict[int, dict[str, int]] = {}
    for scope_ordinal, scope in enumerate(scopes):
        fit_scope_id = str(scope.get("fit_scope_id"))
        heldout = scope.get("heldout_block")
        training_blocks = [str(block) for block in _sequence(
            scope.get("training_blocks"), label="scope training blocks"
        )]
        expected_heldout = (
            rw.WORLD_BLOCKS[scope_ordinal]
            if scope_ordinal < len(rw.WORLD_BLOCKS)
            else None
        )
        if (
            fit_scope_id != freeze.FIT_SCOPE_IDS[scope_ordinal]
            or heldout != expected_heldout
        ):
            _fail("fit-scope order or heldout block differs")
        view = _mapping(scope.get("candidate_view"), label="scope candidate view")
        admission = _mapping(scope.get("admission"), label="scope admission")
        eligible = [
            _candidate_summary(
                value,
                slate=slate,
                training_blocks=training_blocks,
                label=f"scope[{scope_ordinal}] candidate[{index}]",
            )
            for index, value in enumerate(_sequence(
                view.get("eligible_candidates"), label="scope eligible candidates"
            ))
        ]
        eligible_ids = [str(row["lineup_id"]) for row in eligible]
        eligible_by_id = {str(row["lineup_id"]): row for row in eligible}
        excluded_values = [_mapping(value, label="scope excluded candidate") for value in _sequence(
            view.get("excluded_candidates_audit"), label="scope excluded candidates"
        )]
        excluded_by_id = {
            str(row.get("lineup_id")): row for row in excluded_values
        }
        admitted_ids = [str(value) for value in _sequence(
            admission.get("admitted_lineup_ids"), label="scope admitted IDs"
        )]
        if (
            eligible_ids != sorted(set(eligible_ids))
            or len(excluded_by_id) != len(excluded_values)
            or set(eligible_ids).intersection(excluded_by_id)
            or set(eligible_ids).union(excluded_by_id) != set(final_ids)
            or admitted_ids != eligible_ids
            or any(
                list(eligible_by_id[lineup_id]["roster_player_ids"])
                != list(final_by_id[lineup_id]["roster_player_ids"])
                for lineup_id in eligible_ids
            )
        ):
            _fail("scope candidate/admission partition differs from final union")
        eligible_ids_by_scope[scope_ordinal] = eligible_ids
        admitted_index_by_scope[scope_ordinal] = {
            lineup_id: index for index, lineup_id in enumerate(admitted_ids)
        }
        for lineup_id in final_ids:
            union_index = union_index_by_id[lineup_id]
            if lineup_id in eligible_by_id:
                candidate = eligible_by_id[lineup_id]
                eligible_index = admitted_index_by_scope[scope_ordinal][lineup_id]
                scope_rows.append({
                    "source_ordinal": ordinal,
                    "slate_id": slate_id,
                    "scope_ordinal": scope_ordinal,
                    "fit_scope_id": fit_scope_id,
                    "heldout_block": heldout,
                    "training_blocks": training_blocks,
                    "lineup_id": lineup_id,
                    "union_index": union_index,
                    "eligible": True,
                    "admitted": True,
                    "eligible_index": eligible_index,
                    "admitted_index": eligible_index,
                    "exclusion_reason_code": None,
                    "training_origin_blocks": candidate["training_origin_blocks"],
                    "training_source_arms": candidate["training_source_arms"],
                    "training_occurrence_counts_by_block": candidate[
                        "training_occurrence_counts_by_block"
                    ],
                    "training_source_arms_by_block": candidate[
                        "training_source_arms_by_block"
                    ],
                    "training_occurrence_count": candidate[
                        "training_occurrence_count"
                    ],
                })
            else:
                excluded = excluded_by_id[lineup_id]
                if (
                    excluded.get("reason_code") != "heldout-only-origin"
                    or excluded.get("heldout_origin_present") is not True
                    or heldout is None
                ):
                    _fail("scope excluded-candidate evidence differs")
                scope_rows.append({
                    "source_ordinal": ordinal,
                    "slate_id": slate_id,
                    "scope_ordinal": scope_ordinal,
                    "fit_scope_id": fit_scope_id,
                    "heldout_block": heldout,
                    "training_blocks": training_blocks,
                    "lineup_id": lineup_id,
                    "union_index": union_index,
                    "eligible": False,
                    "admitted": False,
                    "eligible_index": None,
                    "admitted_index": None,
                    "exclusion_reason_code": "heldout-only-origin",
                    "training_origin_blocks": [],
                    "training_source_arms": [],
                    "training_occurrence_counts_by_block": {
                        block: 0 for block in training_blocks
                    },
                    "training_source_arms_by_block": {
                        block: [] for block in training_blocks
                    },
                    "training_occurrence_count": 0,
                })

    grade_books = [_mapping(value, label="grade book") for value in _sequence(
        grade.get("book_grades"), label="grade books"
    )]
    if len(grade_books) != grading.BOOKS_PER_SLATE:
        _fail("grade book census differs")
    selection_rows: list[dict[str, object]] = []
    book_rows: list[dict[str, object]] = []
    selected_coordinates_by_id: dict[str, list[tuple[int, int]]] = defaultdict(list)
    grade_book_ordinal = 0
    for scope_ordinal, scope in enumerate(scopes):
        books = [_mapping(value, label="frozen book") for value in _sequence(
            scope.get("books"), label="frozen books"
        )]
        if len(books) != grading.STRATEGIES_PER_SCOPE:
            _fail("frozen scope book census differs")
        eligible_ids = eligible_ids_by_scope[scope_ordinal]
        eligible_maximum, eligible_max_ids = _maximum_ids(eligible_ids, score_by_id)
        for strategy_ordinal, (strategy, book) in enumerate(
            zip(strategies, books, strict=True)
        ):
            grade_book = grade_books[grade_book_ordinal]
            grade_book_ordinal += 1
            strategy_id = str(strategy.get("strategy_id"))
            selected_ids = [str(value) for value in _sequence(
                book.get("selected_lineup_ids"), label="selected lineup IDs"
            )]
            selected_rosters = _sequence(
                book.get("selected_rosters"), label="selected rosters"
            )
            selected_local = _sequence(
                book.get("selected_local_indices"), label="selected local indices"
            )
            selected_global = _sequence(
                book.get("selected_global_indices"), label="selected global indices"
            )
            traces = _sequence(book.get("marginal_trace"), label="marginal traces")
            rank_rows = [_mapping(value, label="rank score row") for value in _sequence(
                grade_book.get("rank_80_score_rows"), label="rank score rows"
            )]
            coordinate = {
                "source_ordinal": ordinal,
                "scope_ordinal": scope_ordinal,
                "strategy_ordinal": strategy_ordinal,
                "book_id": book.get("book_id"),
            }
            if (
                strategy.get("ordinal") != strategy_ordinal
                or book.get("strategy_id") != strategy_id
                or book.get("strategy_sha256") != strategy.get("strategy_sha256")
                or grade_book.get("source_ordinal") != ordinal
                or grade_book.get("scope_ordinal") != scope_ordinal
                or grade_book.get("strategy_ordinal") != strategy_ordinal
                or grade_book.get("fit_scope_id") != scope.get("fit_scope_id")
                or grade_book.get("book_id") != book.get("book_id")
                or grade_book.get("book_sha256") != book.get("book_sha256")
                or grade_book.get("strategy_id") != strategy_id
                or grade_book.get("strategy_sha256") != strategy.get("strategy_sha256")
                or grade_book.get("book_coordinate_sha256")
                != canonical_sha256(coordinate)
                or len(selected_ids) != 80
                or len(set(selected_ids)) != 80
                or len(selected_rosters) != 80
                or len(selected_local) != 80
                or len(selected_global) != 80
                or len(traces) != 80
                or len(rank_rows) != 80
            ):
                _fail("frozen/grade book coordinate or rank census differs")
            for rank, lineup_id in enumerate(selected_ids):
                roster = _sequence(
                    selected_rosters[rank], label=f"selected roster[{rank}]"
                )
                trace = _mapping(traces[rank], label=f"marginal trace[{rank}]")
                score_row = rank_rows[rank]
                local_index = selected_local[rank]
                global_index = selected_global[rank]
                if (
                    lineup_id not in admitted_index_by_scope[scope_ordinal]
                    or lineup_id not in final_by_id
                    or roster != list(final_by_id[lineup_id]["roster_player_ids"])
                    or local_index
                    != admitted_index_by_scope[scope_ordinal][lineup_id]
                    or global_index != union_index_by_id[lineup_id]
                    or trace.get("selection_rank") != rank
                    or trace.get("lineup_id") != lineup_id
                    or trace.get("admitted_lineup_index") != local_index
                    or trace.get("global_lineup_index") != global_index
                    or score_row.get("selection_rank") != rank
                    or score_row.get("lineup_id") != lineup_id
                    or score_row.get("realized_score_micro") != score_by_id[lineup_id]
                ):
                    _fail("frozen trace/grade rank/selection lineup join differs")
                selected_coordinates_by_id[lineup_id].append(
                    (scope_ordinal, strategy_ordinal)
                )
                selection_rows.append({
                    "source_ordinal": ordinal,
                    "slate_id": slate_id,
                    "scope_ordinal": scope_ordinal,
                    "fit_scope_id": scope["fit_scope_id"],
                    "strategy_ordinal": strategy_ordinal,
                    "strategy_id": strategy_id,
                    "book_id": book["book_id"],
                    "selection_rank": rank,
                    "lineup_id": lineup_id,
                    "union_index": union_index_by_id[lineup_id],
                    "realized_score_micro": score_by_id[lineup_id],
                    "realized_union_rank": realized_rank_by_id[lineup_id],
                    "at_or_above_thresholds_dk": _threshold_hits(
                        score_by_id[lineup_id]
                    ),
                    "prefix_entry_counts": [
                        int(size) for size in grading.PREFIX_SIZES if rank < int(size)
                    ],
                    "selected_local_index": int(local_index),
                    "selected_global_index": int(global_index),
                    "marginal_trace": deepcopy(trace),
                    "marginal_trace_sha256": canonical_sha256(trace),
                })
            selected_maximum, selected_max_ids = _maximum_ids(
                selected_ids, score_by_id
            )
            threshold_capture = []
            for threshold in grading.THRESHOLDS_DK:
                threshold_micro = int(threshold) * grading.MICRO_DK_PER_POINT
                eligible_count = sum(
                    score_by_id[lineup_id] >= threshold_micro
                    for lineup_id in eligible_ids
                )
                selected_count = sum(
                    score_by_id[lineup_id] >= threshold_micro
                    for lineup_id in selected_ids
                )
                threshold_capture.append({
                    "threshold_dk": int(threshold),
                    "threshold_micro": threshold_micro,
                    "eligible_lineup_count": eligible_count,
                    "selected_lineup_count": selected_count,
                    "selected_hit": selected_count > 0,
                    "eligible_hit": eligible_count > 0,
                })
            book_rows.append({
                "source_ordinal": ordinal,
                "slate_id": slate_id,
                "scope_ordinal": scope_ordinal,
                "fit_scope_id": scope["fit_scope_id"],
                "heldout_block": scope["heldout_block"],
                "strategy_ordinal": strategy_ordinal,
                "strategy_id": strategy_id,
                "strategy_sha256": strategy["strategy_sha256"],
                "book_id": book["book_id"],
                "book_sha256": book["book_sha256"],
                "book_coordinate_sha256": canonical_sha256(coordinate),
                "eligible_lineup_count": len(eligible_ids),
                "selected_lineup_count": len(selected_ids),
                "selected_lineup_ids_sha256": canonical_sha256(selected_ids),
                "marginal_trace_sha256": canonical_sha256(traces),
                "eligible_maximum_score_micro": eligible_maximum,
                "eligible_maximum_lineup_ids": eligible_max_ids,
                "selected_maximum_score_micro": selected_maximum,
                "selected_maximum_lineup_ids": selected_max_ids,
                "selector_regret_micro": eligible_maximum - selected_maximum,
                "threshold_capture": threshold_capture,
            })
    if grade_book_ordinal != grading.BOOKS_PER_SLATE:
        _fail("frozen/grade book traversal census differs")

    lineup_rows: list[dict[str, object]] = []
    for union_index, candidate in enumerate(final_candidates):
        lineup_id = str(candidate["lineup_id"])
        score = score_by_id[lineup_id]
        coordinates = selected_coordinates_by_id.get(lineup_id, [])
        source_arms = list(candidate["training_source_arms"])
        origin_blocks = list(candidate["training_origin_blocks"])
        lineup_rows.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "union_index": union_index,
            "lineup_id": lineup_id,
            "roster_player_ids": candidate["roster_player_ids"],
            "roster_identity_sha256": canonical_sha256(
                candidate["roster_player_ids"]
            ),
            "realized_score_micro": score,
            "realized_union_rank": realized_rank_by_id[lineup_id],
            "realized_score_tie_count": score_tie_count[score],
            "union_maximum_score_micro": union_maximum,
            "regret_to_union_maximum_micro": union_maximum - score,
            "at_or_above_thresholds_dk": _threshold_hits(score),
            "training_origin_blocks": origin_blocks,
            "training_source_arms": source_arms,
            "training_occurrence_counts_by_block": candidate[
                "training_occurrence_counts_by_block"
            ],
            "training_source_arms_by_block": candidate[
                "training_source_arms_by_block"
            ],
            "training_occurrence_count": candidate["training_occurrence_count"],
            "source_arm_count": len(source_arms),
            "origin_block_count": len(origin_blocks),
            "multi_arm_origin": len(source_arms) > 1,
            "multi_block_origin": len(origin_blocks) > 1,
            "selected_book_count": len(coordinates),
            "selected_scope_count": len({scope for scope, _ in coordinates}),
            "selected_strategy_count": len({strategy for _, strategy in coordinates}),
            "selected_any": bool(coordinates),
            "missed_by_every_book": not coordinates,
        })

    if candidate_provenance is not None:
        _fail(
            "exact candidate occurrence provenance requires a separately "
            "versioned generation-pinned sidecar"
        )
    body: dict[str, object] = {
        "schema_version": SLATE_ATTRIBUTION_SCHEMA,
        "source_ordinal": ordinal,
        "slate_id": slate_id,
        "panel_freeze_identity": panel_identity,
        "slate_freeze_identity": leaf_identity,
        "task_result_identity": result_identity,
        "task_result_sha256": task["task_result_sha256"],
        "slate_grade_identity": grade_identity,
        "slate_grade_sha256": grade["slate_grade_sha256"],
        "candidate_provenance_sha256": task["candidate_provenance_sha256"],
        "candidate_provenance_resolution": CANDIDATE_PROVENANCE_RESOLUTION,
        "exact_generation_occurrence_rows_available": False,
        "player_realized_contributions_available": False,
        "point_in_time_player_traits_attached": False,
        "thresholds_dk": [int(value) for value in grading.THRESHOLDS_DK],
        "realized_union_rank_law": REALIZED_UNION_RANK_LAW,
        "selector_regret_law": SELECTOR_REGRET_LAW,
        "lineup_count": len(lineup_rows),
        "lineup_rows": lineup_rows,
        "lineup_rows_sha256": canonical_sha256(lineup_rows),
        "scope_membership_count": len(scope_rows),
        "scope_membership_rows": scope_rows,
        "scope_membership_rows_sha256": canonical_sha256(scope_rows),
        "book_count": len(book_rows),
        "book_rows": book_rows,
        "book_rows_sha256": canonical_sha256(book_rows),
        "selection_count": len(selection_rows),
        "selection_rows": selection_rows,
        "selection_rows_sha256": canonical_sha256(selection_rows),
        "contest_metrics": {
            "availability": "unavailable",
            "reason": CONTEST_UNAVAILABLE_REASON,
            "rank": None,
            "roi_micro_usd": None,
        },
        "fill_effect_interpretation": "descriptive-only-pooled-multi-arm",
        "uses_realized_outcomes": True,
        "no_rescore": True,
        "projected_from_persisted_union_score_lookup": True,
        "complete": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["slate_attribution_sha256"] = canonical_sha256(body)
    return validate_slate_attribution_structure_v1(body)


def validate_slate_attribution_structure_v1(value: object) -> dict[str, object]:
    """Validate one attribution shard without reopening its predecessors."""
    item = _mapping(value, label="slate attribution")
    _exact_keys(item, _TOP_LEVEL_FIELDS, label="slate attribution")
    retained_hash = _digest(
        item.get("slate_attribution_sha256"), label="slate attribution SHA"
    )
    if canonical_sha256({
        key: nested for key, nested in item.items()
        if key != "slate_attribution_sha256"
    }) != retained_hash:
        _fail("slate attribution self-hash differs")
    ordinal = _integer(item.get("source_ordinal"), label="source ordinal")
    if ordinal >= grading.SOURCE_SLATE_COUNT:
        _fail("source ordinal is outside the 54-slate panel")
    if type(item.get("slate_id")) is not str or not item["slate_id"]:
        _fail("slate ID differs")
    for field in (
        "panel_freeze_identity", "slate_freeze_identity",
        "task_result_identity", "slate_grade_identity",
    ):
        _identity(item.get(field), label=field)
    for field in (
        "task_result_sha256", "slate_grade_sha256",
        "candidate_provenance_sha256", "lineup_rows_sha256",
        "scope_membership_rows_sha256", "book_rows_sha256",
        "selection_rows_sha256",
    ):
        _digest(item.get(field), label=field)
    if (
        item.get("schema_version") != SLATE_ATTRIBUTION_SCHEMA
        or item.get("candidate_provenance_resolution")
        != CANDIDATE_PROVENANCE_RESOLUTION
        or item.get("exact_generation_occurrence_rows_available") is not False
        or item.get("player_realized_contributions_available") is not False
        or item.get("point_in_time_player_traits_attached") is not False
        or item.get("thresholds_dk")
        != [int(value) for value in grading.THRESHOLDS_DK]
        or item.get("realized_union_rank_law") != REALIZED_UNION_RANK_LAW
        or item.get("selector_regret_law") != SELECTOR_REGRET_LAW
        or item.get("contest_metrics") != {
            "availability": "unavailable",
            "reason": CONTEST_UNAVAILABLE_REASON,
            "rank": None,
            "roi_micro_usd": None,
        }
        or item.get("fill_effect_interpretation")
        != "descriptive-only-pooled-multi-arm"
        or item.get("uses_realized_outcomes") is not True
        or item.get("no_rescore") is not True
        or item.get("projected_from_persisted_union_score_lookup") is not True
        or item.get("complete") is not True
        or any(item.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("slate attribution authority or availability law differs")

    lineup_rows = [_mapping(value, label="lineup row") for value in _sequence(
        item.get("lineup_rows"), label="lineup rows"
    )]
    if (
        item.get("lineup_count") != len(lineup_rows)
        or len(lineup_rows) < 80
        or item.get("lineup_rows_sha256") != canonical_sha256(lineup_rows)
    ):
        _fail("lineup-row census/hash differs")
    lineup_by_id: dict[str, dict[str, object]] = {}
    for union_index, row in enumerate(lineup_rows):
        _exact_keys(row, _LINEUP_FIELDS, label="lineup row")
        lineup_id = row.get("lineup_id")
        roster = _sequence(row.get("roster_player_ids"), label="lineup roster")
        score = row.get("realized_score_micro")
        if (
            row.get("source_ordinal") != ordinal
            or row.get("slate_id") != item.get("slate_id")
            or row.get("union_index") != union_index
            or type(lineup_id) is not str
            or not lineup_id
            or lineup_id in lineup_by_id
            or len(roster) != rw.ROSTER_SIZE
            or roster != sorted(roster)
            or len(set(roster)) != rw.ROSTER_SIZE
            or row.get("roster_identity_sha256") != canonical_sha256(roster)
            or type(score) is not int
            or row.get("at_or_above_thresholds_dk") != _threshold_hits(int(score))
            or row.get("source_arm_count") != len(row.get("training_source_arms", []))
            or row.get("origin_block_count") != len(row.get("training_origin_blocks", []))
            or row.get("multi_arm_origin") is not (row["source_arm_count"] > 1)
            or row.get("multi_block_origin") is not (row["origin_block_count"] > 1)
            or row.get("selected_any") is not (row.get("selected_book_count", 0) > 0)
            or row.get("missed_by_every_book") is not (not row["selected_any"])
        ):
            _fail("lineup row coordinate, roster, score, or selection summary differs")
        lineup_by_id[str(lineup_id)] = row
    scores = {lineup_id: int(row["realized_score_micro"]) for lineup_id, row in lineup_by_id.items()}
    realized_order = sorted(scores, key=lambda lineup_id: (-scores[lineup_id], lineup_id))
    union_maximum = max(scores.values())
    score_tie_count = Counter(scores.values())
    for rank, lineup_id in enumerate(realized_order):
        row = lineup_by_id[lineup_id]
        if (
            row.get("realized_union_rank") != rank
            or row.get("union_maximum_score_micro") != union_maximum
            or row.get("regret_to_union_maximum_micro")
            != union_maximum - scores[lineup_id]
            or row.get("realized_score_tie_count")
            != score_tie_count[scores[lineup_id]]
        ):
            _fail("lineup realized rank/regret differs")

    scope_rows = [_mapping(value, label="scope membership row") for value in _sequence(
        item.get("scope_membership_rows"), label="scope membership rows"
    )]
    expected_scope_count = grading.SCOPES_PER_SLATE * len(lineup_rows)
    if (
        item.get("scope_membership_count") != len(scope_rows)
        or len(scope_rows) != expected_scope_count
        or item.get("scope_membership_rows_sha256") != canonical_sha256(scope_rows)
    ):
        _fail("scope-membership census/hash differs")
    for index, row in enumerate(scope_rows):
        _exact_keys(row, _SCOPE_FIELDS, label="scope membership row")
        scope_ordinal = index // len(lineup_rows)
        union_index = index % len(lineup_rows)
        expected_lineup = lineup_rows[union_index]
        if (
            row.get("source_ordinal") != ordinal
            or row.get("slate_id") != item.get("slate_id")
            or row.get("scope_ordinal") != scope_ordinal
            or row.get("fit_scope_id") != freeze.FIT_SCOPE_IDS[scope_ordinal]
            or row.get("lineup_id") != expected_lineup["lineup_id"]
            or row.get("union_index") != union_index
            or type(row.get("eligible")) is not bool
            or row.get("admitted") is not row.get("eligible")
            or (row.get("eligible_index") is None) is row.get("eligible")
            or (row.get("admitted_index") is None) is row.get("admitted")
        ):
            _fail("scope membership coordinate/admission differs")

    book_rows = [_mapping(value, label="book row") for value in _sequence(
        item.get("book_rows"), label="book rows"
    )]
    selection_rows = [_mapping(value, label="selection row") for value in _sequence(
        item.get("selection_rows"), label="selection rows"
    )]
    if (
        item.get("book_count") != grading.BOOKS_PER_SLATE
        or len(book_rows) != grading.BOOKS_PER_SLATE
        or item.get("book_rows_sha256") != canonical_sha256(book_rows)
        or item.get("selection_count")
        != grading.BOOKS_PER_SLATE * 80
        or len(selection_rows) != grading.BOOKS_PER_SLATE * 80
        or item.get("selection_rows_sha256") != canonical_sha256(selection_rows)
    ):
        _fail("book/selection census or hash differs")
    selected_counts: dict[str, int] = defaultdict(int)
    selected_scopes: dict[str, set[int]] = defaultdict(set)
    selected_strategies: dict[str, set[int]] = defaultdict(set)
    for book_ordinal, book in enumerate(book_rows):
        _exact_keys(book, _BOOK_FIELDS, label="book row")
        scope_ordinal = book_ordinal // grading.STRATEGIES_PER_SCOPE
        strategy_ordinal = book_ordinal % grading.STRATEGIES_PER_SCOPE
        selected_slice = selection_rows[book_ordinal * 80:(book_ordinal + 1) * 80]
        selected_ids = [str(row.get("lineup_id")) for row in selected_slice]
        if (
            book.get("source_ordinal") != ordinal
            or book.get("scope_ordinal") != scope_ordinal
            or book.get("strategy_ordinal") != strategy_ordinal
            or book.get("selected_lineup_count") != 80
            or book.get("selected_lineup_ids_sha256") != canonical_sha256(selected_ids)
            or book.get("selector_regret_micro")
            != int(book["eligible_maximum_score_micro"])
            - int(book["selected_maximum_score_micro"])
        ):
            _fail("book row coordinate, selection, or regret differs")
        captures = [_mapping(value, label="threshold capture") for value in _sequence(
            book.get("threshold_capture"), label="threshold captures"
        )]
        if len(captures) != len(grading.THRESHOLDS_DK):
            _fail("book threshold-capture census differs")
        for threshold, capture in zip(grading.THRESHOLDS_DK, captures, strict=True):
            _exact_keys(capture, _THRESHOLD_CAPTURE_FIELDS, label="threshold capture")
            if (
                capture.get("threshold_dk") != int(threshold)
                or capture.get("threshold_micro")
                != int(threshold) * grading.MICRO_DK_PER_POINT
                or capture.get("selected_hit")
                is not (int(capture["selected_lineup_count"]) > 0)
                or capture.get("eligible_hit")
                is not (int(capture["eligible_lineup_count"]) > 0)
            ):
                _fail("book threshold-capture row differs")
        for rank, row in enumerate(selected_slice):
            _exact_keys(row, _SELECTION_FIELDS, label="selection row")
            lineup_id = row.get("lineup_id")
            if (
                row.get("source_ordinal") != ordinal
                or row.get("slate_id") != item.get("slate_id")
                or row.get("scope_ordinal") != scope_ordinal
                or row.get("strategy_ordinal") != strategy_ordinal
                or row.get("book_id") != book.get("book_id")
                or row.get("selection_rank") != rank
                or lineup_id not in lineup_by_id
                or row.get("union_index") != lineup_by_id[str(lineup_id)]["union_index"]
                or row.get("realized_score_micro") != scores[str(lineup_id)]
                or row.get("realized_union_rank")
                != lineup_by_id[str(lineup_id)]["realized_union_rank"]
                or row.get("at_or_above_thresholds_dk")
                != _threshold_hits(scores[str(lineup_id)])
                or row.get("prefix_entry_counts")
                != [int(size) for size in grading.PREFIX_SIZES if rank < int(size)]
                or row.get("marginal_trace_sha256")
                != canonical_sha256(row.get("marginal_trace"))
            ):
                _fail("selection row coordinate, rank, or score differs")
            selected_counts[str(lineup_id)] += 1
            selected_scopes[str(lineup_id)].add(scope_ordinal)
            selected_strategies[str(lineup_id)].add(strategy_ordinal)
    for lineup_id, row in lineup_by_id.items():
        if (
            row.get("selected_book_count") != selected_counts[lineup_id]
            or row.get("selected_scope_count") != len(selected_scopes[lineup_id])
            or row.get("selected_strategy_count")
            != len(selected_strategies[lineup_id])
        ):
            _fail("lineup selection-membership summary differs")
    return item


def validate_slate_attribution_v1(
    value: object,
    *,
    source_ordinal: int,
    slate_id: str,
    task_result: Mapping[str, object],
    realized_slate_grade: Mapping[str, object],
    panel_freeze_identity: Mapping[str, object],
    slate_freeze_identity: Mapping[str, object],
    task_result_identity: Mapping[str, object],
    slate_grade_identity: Mapping[str, object],
    candidate_provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate structure and byte-identically replay the predecessor join."""
    observed = validate_slate_attribution_structure_v1(value)
    expected = build_slate_attribution_v1(
        source_ordinal=source_ordinal,
        slate_id=slate_id,
        task_result=task_result,
        realized_slate_grade=realized_slate_grade,
        panel_freeze_identity=panel_freeze_identity,
        slate_freeze_identity=slate_freeze_identity,
        task_result_identity=task_result_identity,
        slate_grade_identity=slate_grade_identity,
        candidate_provenance=candidate_provenance,
    )
    if canonical_json_bytes(observed) != canonical_json_bytes(expected):
        _fail("slate attribution canonical predecessor replay differs")
    return expected


__all__ = [
    "CANDIDATE_PROVENANCE_RESOLUTION",
    "CorpusR6FullUnionAttributionV1Error",
    "REALIZED_UNION_RANK_LAW",
    "SELECTOR_REGRET_LAW",
    "SLATE_ATTRIBUTION_SCHEMA",
    "build_slate_attribution_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "validate_slate_attribution_structure_v1",
    "validate_slate_attribution_v1",
]
