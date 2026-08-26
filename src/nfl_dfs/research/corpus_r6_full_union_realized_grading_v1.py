"""Pure score-once realized grading for the frozen R6 full-union panel.

The structural freeze owns selection.  This module starts only from the exact
54/54 freeze root and the separately validated realized-outcome snapshot.  It
scores each distinct ``all-block-final-fit`` roster once per slate, creates a
``(source_ordinal, lineup_id)`` score map, and projects every frozen book from
that map.  Book projection never sums a roster again.

The logical output is intentionally sharded: one self-hashed grade holds the
large rank-80 score rows for each slate, while one smaller aggregate holds 54
hash descriptors and the exact 6 scope x 8 strategy x 3 prefix = 144
historical cells.  Prefix grades bind the first 4/14/80 rank rows by hashes and
metrics; they do not repeat rank-80 score rows.  A separate root-last function
publishes all 54 shards through a caller-owned create-once callback and only
then publishes a terminal root containing their generation-pinned content
identities.  Only that identity-bound root has durable replay authority.

This module owns no warehouse, object-store, graph, selector, or publication
client.  The caller supplies an exact-read callback used by the existing
freeze and outcome-snapshot validators.  Contest rank and ROI remain
unavailable without a separately specified and validated full-field standings,
duplicate/tie-settlement, and payout-ladder contract.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_fast_lane_v1 as lane
from nfl_dfs.research import corpus_r6_full_union_outcome_snapshot_v1 as outcomes
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as freeze
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_batch_evidence_contract import MICRO_DK_PER_POINT
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


LOGICAL_ROOT_SCHEMA: Final = "corpus-r6-full-union-realized-logical-root/v1"
PERSISTED_ROOT_SCHEMA: Final = "corpus-r6-full-union-realized-grade-root/v1"
SLATE_GRADE_SCHEMA: Final = "corpus-r6-full-union-realized-slate-grade/v1"
BOOK_GRADE_SCHEMA: Final = "corpus-r6-full-union-realized-book-grade/v1"
PREFIX_GRADE_SCHEMA: Final = "corpus-r6-full-union-realized-prefix-grade/v1"
AGGREGATE_CELL_SCHEMA: Final = (
    "corpus-r6-full-union-realized-aggregate-cell/v1"
)

THRESHOLDS_DK: Final = (187, 194, 200, 210, 220, 230, 240)
PREFIX_SIZES: Final = tuple(lane.PREFIX_SIZES)
SOURCE_SLATE_COUNT: Final = freeze.AUTHORITATIVE_SLATE_COUNT
SCOPES_PER_SLATE: Final = lane.SCOPE_COUNT
STRATEGIES_PER_SCOPE: Final = lane.STRATEGY_COUNT
BOOKS_PER_SLATE: Final = lane.BOOKS_PER_SLATE
PREFIXES_PER_BOOK: Final = len(PREFIX_SIZES)
PANEL_BOOK_COUNT: Final = SOURCE_SLATE_COUNT * BOOKS_PER_SLATE
PANEL_PREFIX_COUNT: Final = PANEL_BOOK_COUNT * PREFIXES_PER_BOOK
AGGREGATE_CELL_COUNT: Final = (
    SCOPES_PER_SLATE * STRATEGIES_PER_SCOPE * PREFIXES_PER_BOOK
)
AGGREGATE_SLATE_ROW_COUNT: Final = AGGREGATE_CELL_COUNT * SOURCE_SLATE_COUNT

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")

_UNION_SCORE_ROW_FIELDS: Final = frozenset({
    "source_ordinal", "union_index", "lineup_id", "roster_identity_sha256",
    "realized_score_micro",
})
_RANK_SCORE_ROW_FIELDS: Final = frozenset({
    "selection_rank", "lineup_id", "realized_score_micro",
})
_THRESHOLD_FIELDS: Final = frozenset({
    "threshold_dk", "threshold_micro", "operator", "lineup_count",
    "at_or_above_count", "at_or_above_fraction",
    "produced_at_least_one_hit",
})
_TAIL_FIELDS: Final = frozenset({
    "tail_id", "threshold_dk", "threshold_micro", "operator", "lineup_count",
    "union_indices", "lineup_ids", "lineup_ids_sha256",
    "lineup_score_rows_sha256",
})
_BASIC_METRICS_FIELDS: Final = frozenset({
    "lineup_count", "score_sum_micro", "score_mean",
    "score_median", "maximum_score_micro", "maximum_lineup_ids",
    "maximum_lineup_ids_sha256", "thresholds", "score_multiset_sha256",
})
_UNION_METRICS_FIELDS: Final = frozenset({
    *_BASIC_METRICS_FIELDS, "tail_identity_subsets",
})
_PREFIX_FIELDS: Final = frozenset({
    "schema_version", "source_ordinal", "scope_ordinal", "fit_scope_id",
    "strategy_ordinal", "strategy_id", "book_id", "book_coordinate_sha256",
    "entry_count", "prefix_of_rank_80", "rank_80_payload_sha256",
    "prefix_descriptor_sha256", "prefix_payload_sha256",
    "selected_lineup_ids_sha256", "selected_rosters_sha256",
    "rank_80_score_prefix_sha256", "metrics",
    "projected_from_union_score_lookup", "roster_sum_operation_count",
    "prefix_grade_sha256",
})
_BOOK_FIELDS: Final = frozenset({
    "schema_version", "source_ordinal", "scope_ordinal", "fit_scope_id",
    "heldout_block", "strategy_ordinal", "strategy_id", "strategy_sha256",
    "book_id", "book_sha256", "book_coordinate_sha256",
    "rank_80_entry_count", "rank_80_score_rows",
    "rank_80_score_rows_sha256", "prefix_count", "prefixes",
    "projected_from_union_score_lookup", "roster_sum_operation_count",
    "book_grade_sha256",
})
_SLATE_FIELDS: Final = frozenset({
    "schema_version", "source_ordinal", "slate_id", "panel_freeze_identity",
    "panel_freeze_sha256", "slate_freeze_identity", "slate_freeze_sha256",
    "task_result_identity", "task_result_sha256", "outcome_snapshot_identity",
    "outcome_snapshot_sha256", "population_descriptor_sha256",
    "union_lineup_count", "union_score_rows", "union_score_rows_sha256",
    "union_metrics", "roster_sum_operation_ceiling",
    "roster_sum_operation_count", "book_grade_count",
    "book_coordinate_set_sha256", "book_grades", "complete",
    "every_unique_final_union_roster_scored_once",
    "every_book_projected_from_union_score_lookup",
    "rank_80_score_rows_stored_once", "prefixes_store_hashes_and_metrics_only",
    "uses_realized_outcomes", "historical_retune_licensed",
    "historical_retry_licensed", "graph_mutation_licensed",
    "production_change_licensed", "decision_authority", "slate_grade_sha256",
})
_AGGREGATE_SLATE_ROW_FIELDS: Final = frozenset({
    "source_ordinal", "slate_id", "book_id", "book_coordinate_sha256",
    "prefix_grade_sha256", "maximum_score_micro",
    "maximum_lineup_ids_sha256", "lineup_score_sum_micro",
    "at_or_above_counts", "produced_hit_flags",
})
_AGGREGATE_THRESHOLD_FIELDS: Final = frozenset({
    "threshold_dk", "threshold_micro", "operator",
    "slates_with_at_least_one_hit", "slate_hit_fraction",
    "lineups_at_or_above_count", "lineup_hit_fraction",
})
_AGGREGATE_CELL_FIELDS: Final = frozenset({
    "schema_version", "scope_ordinal", "fit_scope_id", "strategy_ordinal",
    "strategy_id", "strategy_sha256", "entry_count", "source_slate_count",
    "slate_rows", "slate_rows_sha256", "lineup_occurrence_count",
    "lineup_score_sum_micro", "lineup_score_mean", "slate_maximum_mean",
    "slate_maximum_median", "minimum_slate_maximum_micro",
    "maximum_slate_maximum_micro", "thresholds", "complete",
    "aggregate_cell_sha256",
})
_SLATE_DESCRIPTOR_FIELDS: Final = frozenset({
    "source_ordinal", "slate_id", "slate_grade_sha256", "union_lineup_count",
    "roster_sum_operation_count", "book_grade_count",
    "book_coordinate_set_sha256",
})
_COVERAGE_FIELDS: Final = frozenset({
    "source_slate_count", "scopes_per_slate", "strategies_per_scope",
    "rank_80_books_per_slate", "rank_80_book_count", "prefixes_per_book",
    "prefix_grade_count", "aggregate_cell_count", "aggregate_slate_row_count",
    "unique_final_union_roster_count", "roster_sum_operation_ceiling",
    "roster_sum_operation_count", "actual_player_outcome_row_count",
    "every_unique_final_union_roster_scored_once",
    "roster_sum_operation_ceiling_equals_final_union_count",
    "every_book_projected_from_union_score_lookup",
    "all_4_14_80_prefixes_projected_from_rank_80",
    "actual_player_outcome_keys_exact", "complete",
})
_ROOT_FIELDS: Final = frozenset({
    "schema_version", "panel_freeze_identity", "panel_freeze_sha256",
    "execution_manifest_sha256", "panel_index_identity", "panel_index_sha256",
    "outcome_key_projection_identity", "outcome_key_projection_sha256",
    "later_source_freeze_identity", "later_source_freeze_sha256",
    "realized_source_identity", "realized_source_sha256",
    "outcome_snapshot_identity", "outcome_snapshot_sha256", "score_unit",
    "micro_dk_per_point", "threshold_registry", "fit_scope_ids",
    "strategy_registry", "strategy_registry_sha256", "prefix_sizes",
    "coverage", "slate_grade_descriptors", "slate_grade_descriptors_sha256",
    "aggregate_cell_count", "aggregate_cells", "aggregate_cells_sha256",
    "contest_metrics", "complete", "outcome_blind_freeze_mutated",
    "uses_realized_outcomes",
    "historical_retune_licensed", "historical_retry_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "realized_grade_sha256",
})
_PERSISTED_SHARD_FIELDS: Final = frozenset({
    "source_ordinal", "slate_id", "target_uri", "slate_grade_identity",
    "slate_grade_sha256", "slate_grade_object_sha256",
})
_PERSISTED_ROOT_FIELDS: Final = frozenset({
    "schema_version", "publication_mode", "target_uri",
    "logical_grade_root", "logical_grade_root_sha256", "source_slate_count",
    "slate_grade_objects", "slate_grade_objects_sha256", "complete",
    "all_shard_identities_resolved_before_root_build",
    "root_create_once_requested_last",
    "uses_realized_outcomes", "historical_retune_licensed",
    "historical_retry_licensed", "graph_mutation_licensed",
    "production_change_licensed", "decision_authority",
    "persisted_grade_root_sha256",
})

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], object]


class CorpusR6FullUnionRealizedGradingV1Error(ValueError):
    """The post-freeze score-once grade failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6FullUnionRealizedGradingV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionRealizedGradingV1Error(str(exc)) from exc


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


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _integer(value: object, *, label: str, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        suffix = "" if minimum is None else f" >= {minimum}"
        _fail(f"{label} must be an exact integer{suffix}")
    return value


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be a canonical nonempty string")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionRealizedGradingV1Error(str(exc)) from exc


def _exact_read_json(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-read content identity differs")
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionRealizedGradingV1Error(str(exc)) from exc
    return _mapping(value, label=label), identity


def _publication_prefix(value: object) -> str:
    prefix = _string(value, label="realized-grade output prefix")
    if (
        not prefix.startswith("gs://")
        or prefix == "gs://"
        or "//" in prefix[5:]
        or prefix.endswith(".json")
    ):
        _fail("realized-grade output prefix must be one canonical GCS prefix")
    return prefix.rstrip("/")


def _published_identity(
    value: object,
    *,
    target_uri: str,
    raw: bytes,
    label: str,
) -> dict[str, object]:
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        value = as_dict()
    identity = _identity(value, label=label)
    if (
        identity["uri"] != target_uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} differs from the create-once bytes/target")
    return identity


def _verify_published_json(
    value: object,
    *,
    target_uri: str,
    raw: bytes,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Exact-open one create-once result and require the intended bytes."""
    identity = _published_identity(
        value, target_uri=target_uri, raw=raw, label=f"{label} identity"
    )
    retained_raw = read_exact(identity)
    if type(retained_raw) is not bytes or retained_raw != raw:
        _fail(f"{label} exact-read bytes differ from intended publication")
    try:
        retained = batch.parse_canonical_json_bytes(retained_raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionRealizedGradingV1Error(str(exc)) from exc
    return _mapping(retained, label=label), identity


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _rational(numerator: int, denominator: int, *, unit: str) -> dict[str, object]:
    if type(numerator) is not int or type(denominator) is not int or denominator < 1:
        raise AssertionError("internal exact rational received invalid values")
    return {"numerator": numerator, "denominator": denominator, "unit": unit}


def _mean(values: Sequence[int], *, unit: str = "micro_dk") -> dict[str, object]:
    if not values:
        _fail("an exact mean requires at least one value")
    return _rational(sum(values), len(values), unit=unit)


def _median(values: Sequence[int], *, unit: str = "micro_dk") -> dict[str, object]:
    if not values:
        _fail("an exact median requires at least one value")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return _rational(ordered[middle], 1, unit=unit)
    return _rational(ordered[middle - 1] + ordered[middle], 2, unit=unit)


def _threshold_registry() -> list[dict[str, object]]:
    return [
        {
            "threshold_dk": threshold,
            "threshold_micro": threshold * MICRO_DK_PER_POINT,
            "operator": ">=",
        }
        for threshold in THRESHOLDS_DK
    ]


def _threshold_rows(scores: Sequence[int]) -> list[dict[str, object]]:
    if not scores:
        _fail("threshold metrics require a nonempty lineup population")
    rows: list[dict[str, object]] = []
    for threshold in THRESHOLDS_DK:
        threshold_micro = threshold * MICRO_DK_PER_POINT
        count = sum(score >= threshold_micro for score in scores)
        rows.append({
            "threshold_dk": threshold,
            "threshold_micro": threshold_micro,
            "operator": ">=",
            "lineup_count": len(scores),
            "at_or_above_count": count,
            "at_or_above_fraction": _rational(
                count, len(scores), unit="lineups"
            ),
            "produced_at_least_one_hit": count > 0,
        })
    return rows


def _basic_metrics(score_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if not score_rows:
        _fail("score metrics require a nonempty score-row population")
    scores = [_integer(row.get("realized_score_micro"), label="realized score")
              for row in score_rows]
    maximum = max(scores)
    maximum_ids = [
        _string(row.get("lineup_id"), label="maximum lineup ID")
        for row in score_rows
        if row.get("realized_score_micro") == maximum
    ]
    return {
        "lineup_count": len(scores),
        "score_sum_micro": sum(scores),
        "score_mean": _mean(scores),
        "score_median": _median(scores),
        "maximum_score_micro": maximum,
        "maximum_lineup_ids": maximum_ids,
        "maximum_lineup_ids_sha256": canonical_sha256(maximum_ids),
        "thresholds": _threshold_rows(scores),
        "score_multiset_sha256": canonical_sha256(sorted(scores, reverse=True)),
    }


def _tail_subset(
    score_rows: Sequence[Mapping[str, object]], *, threshold_dk: int, operator: str,
) -> dict[str, object]:
    threshold_micro = threshold_dk * MICRO_DK_PER_POINT
    if operator == ">=":
        retained = [row for row in score_rows
                    if int(row["realized_score_micro"]) >= threshold_micro]
        tail_id = f"ge-{threshold_dk}"
    elif operator == ">":
        retained = [row for row in score_rows
                    if int(row["realized_score_micro"]) > threshold_micro]
        tail_id = f"gt-{threshold_dk}"
    else:
        raise AssertionError("internal tail operator is not registered")
    indices = [int(row["union_index"]) for row in retained]
    lineup_ids = [str(row["lineup_id"]) for row in retained]
    compact_rows = [{
        "union_index": row["union_index"],
        "lineup_id": row["lineup_id"],
        "realized_score_micro": row["realized_score_micro"],
    } for row in retained]
    return {
        "tail_id": tail_id,
        "threshold_dk": threshold_dk,
        "threshold_micro": threshold_micro,
        "operator": operator,
        "lineup_count": len(retained),
        "union_indices": indices,
        "lineup_ids": lineup_ids,
        "lineup_ids_sha256": canonical_sha256(lineup_ids),
        "lineup_score_rows_sha256": canonical_sha256(compact_rows),
    }


def _union_metrics(
    score_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        **_basic_metrics(score_rows),
        "tail_identity_subsets": [
            _tail_subset(score_rows, threshold_dk=200, operator=">="),
            _tail_subset(score_rows, threshold_dk=200, operator=">"),
            _tail_subset(score_rows, threshold_dk=230, operator=">"),
        ],
    }


@dataclass(frozen=True, slots=True)
class _PreparedBook:
    source_ordinal: int
    scope_ordinal: int
    fit_scope_id: str
    heldout_block: str | None
    strategy_ordinal: int
    strategy_id: str
    strategy_sha256: str
    book_id: str
    book_sha256: str
    selected_lineup_ids: tuple[str, ...]
    selected_rosters: tuple[tuple[str, ...], ...]
    descriptor: Mapping[str, object]

    @property
    def coordinate(self) -> tuple[int, int, int, str]:
        return (
            self.source_ordinal,
            self.scope_ordinal,
            self.strategy_ordinal,
            self.book_id,
        )


@dataclass(frozen=True, slots=True)
class _PreparedSlate:
    source_ordinal: int
    slate_id: str
    leaf: Mapping[str, object]
    leaf_identity: Mapping[str, object]
    result: Mapping[str, object]
    population: tuple[tuple[str, tuple[str, ...]], ...]
    books: tuple[_PreparedBook, ...]


class _RosterSumCounter:
    """Make the one-roster/one-sum ceiling explicit and fail closed."""

    def __init__(self, *, ceiling: int) -> None:
        self.ceiling = ceiling
        self.count = 0

    def score(
        self,
        *,
        source_ordinal: int,
        roster: Sequence[str],
        player_scores: Mapping[tuple[int, str], int],
    ) -> int:
        if self.count >= self.ceiling:
            _fail("final-union roster-sum operation ceiling exceeded")
        self.count += 1
        values: list[int] = []
        for player_id in roster:
            key = (source_ordinal, player_id)
            if key not in player_scores:
                _fail("one final-union roster lacks an exact outcome key")
            value = player_scores[key]
            if type(value) is not int:
                _fail("one realized player outcome is not exact integer micro-DK")
            values.append(value)
        return sum(values)


def _population_from_result(
    *,
    source_ordinal: int,
    result: Mapping[str, object],
    leaf: Mapping[str, object],
) -> tuple[
    tuple[tuple[str, tuple[str, ...]], ...],
    dict[str, tuple[str, ...]],
    Mapping[str, object],
    Sequence[object],
    Sequence[object],
]:
    surface = _mapping(result.get("full_union_surface"), label="full-union surface")
    scopes = _sequence(surface.get("scopes"), label="full-union scopes")
    strategies = _sequence(
        surface.get("strategy_registry"), label="full-union strategies"
    )
    if (
        surface.get("scope_count") != SCOPES_PER_SLATE
        or surface.get("books_per_scope") != STRATEGIES_PER_SCOPE
        or surface.get("book_count") != BOOKS_PER_SLATE
        or surface.get("prefix_sizes") != list(PREFIX_SIZES)
        or len(scopes) != SCOPES_PER_SLATE
        or len(strategies) != STRATEGIES_PER_SCOPE
    ):
        _fail(f"slate[{source_ordinal}] full-union 6x8 lattice differs")
    final_scope = _mapping(scopes[-1], label="all-block final-fit scope")
    if (
        final_scope.get("fit_scope_id") != freeze.FIT_SCOPE_IDS[-1]
        or final_scope.get("heldout_block") is not None
    ):
        _fail(f"slate[{source_ordinal}] final-union fit scope differs")
    view = _mapping(final_scope.get("candidate_view"), label="final candidate view")
    admission = _mapping(final_scope.get("admission"), label="final admission")
    raw_rows = _sequence(
        view.get("eligible_candidates"), label="final-union candidates"
    )
    admitted = _sequence(
        admission.get("admitted_lineup_ids"), label="final-union admitted IDs"
    )
    slate = _mapping(surface.get("slate"), label="full-union slate")
    population: list[tuple[str, tuple[str, ...]]] = []
    roster_by_lineup: dict[str, tuple[str, ...]] = {}
    for union_index, raw_row in enumerate(raw_rows):
        row = _mapping(raw_row, label=f"final-union candidate[{union_index}]")
        lineup_id = _string(row.get("lineup_id"), label="final-union lineup ID")
        roster = tuple(
            _string(player_id, label="final-union player ID")
            for player_id in _sequence(
                row.get("roster_player_ids"), label="final-union roster"
            )
        )
        if (
            lineup_id in roster_by_lineup
            or len(roster) != rw.ROSTER_SIZE
            or tuple(sorted(roster)) != roster
            or len(set(roster)) != rw.ROSTER_SIZE
            or canonical_lineup_id(slate, roster) != lineup_id
        ):
            _fail(f"slate[{source_ordinal}] final-union roster identity differs")
        population.append((lineup_id, roster))
        roster_by_lineup[lineup_id] = roster
    descriptor = _mapping(
        leaf.get("all_block_union"), label="all-block union descriptor"
    )
    population_payload = [
        {"lineup_id": lineup_id, "roster_player_ids": list(roster)}
        for lineup_id, roster in population
    ]
    lineup_ids = [lineup_id for lineup_id, _ in population]
    rosters = [list(roster) for _, roster in population]
    if (
        len(population) < lane.ENTRY_BUDGET
        or lineup_ids != sorted(set(lineup_ids))
        or admitted != lineup_ids
        or admission.get("admitted_count") != len(population)
        or view.get("eligible_count") != len(population)
        or view.get("excluded_count") != 0
        or descriptor.get("lineup_count") != len(population)
        or descriptor.get("ordered_lineup_ids_sha256")
        != canonical_sha256(lineup_ids)
        or descriptor.get("ordered_rosters_sha256") != canonical_sha256(rosters)
        or descriptor.get("ordered_population_sha256")
        != canonical_sha256(population_payload)
        or descriptor.get("eligible_equals_admitted") is not True
        or descriptor.get("excluded_count") != 0
    ):
        _fail(f"slate[{source_ordinal}] final-union population binding differs")
    return tuple(population), roster_by_lineup, surface, scopes, strategies


def _validate_prefix_descriptors(
    *,
    source_ordinal: int,
    book: Mapping[str, object],
    descriptor: Mapping[str, object],
) -> None:
    selected_ids = _sequence(book.get("selected_lineup_ids"), label="rank-80 IDs")
    selected_rosters = _sequence(
        book.get("selected_rosters"), label="rank-80 rosters"
    )
    prefixes = _sequence(descriptor.get("prefixes"), label="prefix descriptors")
    rank_payload = {
        "selected_lineup_ids": selected_ids,
        "selected_rosters": selected_rosters,
    }
    rank_sha = canonical_sha256(rank_payload)
    if (
        descriptor.get("rank_80_payload_sha256") != rank_sha
        or descriptor.get("selected_lineup_ids_sha256")
        != canonical_sha256(selected_ids)
        or descriptor.get("selected_rosters_sha256")
        != canonical_sha256(selected_rosters)
        or descriptor.get("prefix_count") != PREFIXES_PER_BOOK
        or len(prefixes) != PREFIXES_PER_BOOK
    ):
        _fail(f"slate[{source_ordinal}] rank-80 descriptor binding differs")
    for expected_size, raw_prefix in zip(PREFIX_SIZES, prefixes, strict=True):
        prefix = _mapping(raw_prefix, label="prefix descriptor")
        _validate_self_hash(
            prefix,
            field="prefix_descriptor_sha256",
            label="prefix descriptor",
        )
        ids = selected_ids[:expected_size]
        rosters = selected_rosters[:expected_size]
        if (
            prefix.get("schema_version") != freeze.PREFIX_DESCRIPTOR_SCHEMA
            or prefix.get("entry_count") != expected_size
            or prefix.get("prefix_of_rank_80") is not True
            or prefix.get("rank_80_payload_sha256") != rank_sha
            or prefix.get("prefix_payload_sha256")
            != canonical_sha256({
                "selected_lineup_ids": ids,
                "selected_rosters": rosters,
            })
            or prefix.get("selected_lineup_ids_sha256") != canonical_sha256(ids)
            or prefix.get("selected_rosters_sha256") != canonical_sha256(rosters)
        ):
            _fail(f"slate[{source_ordinal}] first-{expected_size} prefix differs")


def _books_from_result(
    *,
    source_ordinal: int,
    scopes: Sequence[object],
    strategies: Sequence[object],
    leaf: Mapping[str, object],
    roster_by_lineup: Mapping[str, tuple[str, ...]],
) -> tuple[_PreparedBook, ...]:
    raw_descriptors = _sequence(
        leaf.get("book_descriptors"), label="leaf book descriptors"
    )
    if (
        leaf.get("book_count") != BOOKS_PER_SLATE
        or leaf.get("prefix_count") != BOOKS_PER_SLATE * PREFIXES_PER_BOOK
        or len(raw_descriptors) != BOOKS_PER_SLATE
    ):
        _fail(f"slate[{source_ordinal}] does not contain complete 48-book coverage")
    books: list[_PreparedBook] = []
    coordinates: set[tuple[int, int, int, str]] = set()
    global_book_ordinal = 0
    for scope_ordinal, raw_scope in enumerate(scopes):
        scope = _mapping(raw_scope, label=f"scope[{scope_ordinal}]")
        fit_scope_id = _string(scope.get("fit_scope_id"), label="fit scope ID")
        expected_scope_id = freeze.FIT_SCOPE_IDS[scope_ordinal]
        raw_books = _sequence(scope.get("books"), label="scope books")
        if (
            fit_scope_id != expected_scope_id
            or scope.get("heldout_block")
            != (
                rw.WORLD_BLOCKS[scope_ordinal]
                if scope_ordinal < len(rw.WORLD_BLOCKS)
                else None
            )
            or scope.get("book_count") != STRATEGIES_PER_SCOPE
            or len(raw_books) != STRATEGIES_PER_SCOPE
        ):
            _fail(f"slate[{source_ordinal}] scope[{scope_ordinal}] lattice differs")
        for strategy_ordinal, (raw_book, raw_strategy) in enumerate(
            zip(raw_books, strategies, strict=True)
        ):
            book = _mapping(raw_book, label="full-union book")
            strategy = _mapping(raw_strategy, label="strategy")
            descriptor = _mapping(
                raw_descriptors[global_book_ordinal], label="book descriptor"
            )
            book_id = _string(book.get("book_id"), label="book ID")
            strategy_id = _string(strategy.get("strategy_id"), label="strategy ID")
            strategy_sha = _digest(
                strategy.get("strategy_sha256"), label="strategy SHA"
            )
            selected_ids = tuple(
                _string(value, label="selected lineup ID")
                for value in _sequence(
                    book.get("selected_lineup_ids"), label="selected lineup IDs"
                )
            )
            selected_rosters = tuple(
                tuple(
                    _string(value, label="selected player ID")
                    for value in _sequence(raw_roster, label="selected roster")
                )
                for raw_roster in _sequence(
                    book.get("selected_rosters"), label="selected rosters"
                )
            )
            if (
                strategy.get("ordinal") != strategy_ordinal
                or book.get("strategy_id") != strategy_id
                or book.get("strategy_sha256") != strategy_sha
                or book.get("fit_scope_id") != fit_scope_id
                or book.get("entry_count") != lane.ENTRY_BUDGET
                or len(selected_ids) != lane.ENTRY_BUDGET
                or len(set(selected_ids)) != lane.ENTRY_BUDGET
                or len(selected_rosters) != lane.ENTRY_BUDGET
                or any(
                    lineup_id not in roster_by_lineup
                    or roster != roster_by_lineup[lineup_id]
                    for lineup_id, roster in zip(
                        selected_ids, selected_rosters, strict=True
                    )
                )
                or descriptor.get("global_book_ordinal") != global_book_ordinal
                or descriptor.get("scope_ordinal") != scope_ordinal
                or descriptor.get("scope_book_ordinal") != strategy_ordinal
                or descriptor.get("fit_scope_id") != fit_scope_id
                or descriptor.get("book_id") != book_id
                or descriptor.get("book_sha256") != book.get("book_sha256")
                or descriptor.get("strategy_ordinal") != strategy_ordinal
                or descriptor.get("strategy_id") != strategy_id
                or descriptor.get("strategy_sha256") != strategy_sha
                or descriptor.get("entry_count") != lane.ENTRY_BUDGET
            ):
                _fail(
                    f"slate[{source_ordinal}] book[{scope_ordinal},"
                    f"{strategy_ordinal}] roster/coordinate binding differs"
                )
            _validate_prefix_descriptors(
                source_ordinal=source_ordinal, book=book, descriptor=descriptor
            )
            coordinate = (
                source_ordinal, scope_ordinal, strategy_ordinal, book_id
            )
            if coordinate in coordinates:
                _fail("source/scope/strategy/book coordinate collision")
            coordinates.add(coordinate)
            books.append(_PreparedBook(
                source_ordinal=source_ordinal,
                scope_ordinal=scope_ordinal,
                fit_scope_id=fit_scope_id,
                heldout_block=scope.get("heldout_block"),
                strategy_ordinal=strategy_ordinal,
                strategy_id=strategy_id,
                strategy_sha256=strategy_sha,
                book_id=book_id,
                book_sha256=_digest(book.get("book_sha256"), label="book SHA"),
                selected_lineup_ids=selected_ids,
                selected_rosters=selected_rosters,
                descriptor=descriptor,
            ))
            global_book_ordinal += 1
    if len(books) != BOOKS_PER_SLATE or len(coordinates) != BOOKS_PER_SLATE:
        _fail(f"slate[{source_ordinal}] complete 6x8 book coordinates differ")
    return tuple(books)


def _prepare_slates(
    *,
    root: Mapping[str, object],
    root_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> tuple[_PreparedSlate, ...]:
    root_rows = _sequence(root.get("slate_freezes"), label="panel slate freezes")
    root_strategies = _sequence(
        root.get("strategy_registry"), label="panel strategy registry"
    )
    if (
        root.get("source_slate_count") != SOURCE_SLATE_COUNT
        or root.get("fit_scope_ids") != list(freeze.FIT_SCOPE_IDS)
        or root.get("prefix_sizes") != list(PREFIX_SIZES)
        or root.get("rank_80_book_count") != PANEL_BOOK_COUNT
        or root.get("prefix_count") != PANEL_PREFIX_COUNT
        or root.get("complete") is not True
        or root.get("outcome_key_projection_inputs_frozen") is not True
        or len(root_rows) != SOURCE_SLATE_COUNT
    ):
        _fail("complete 54x48 structural-freeze root is required")
    prepared: list[_PreparedSlate] = []
    all_coordinates: set[tuple[int, int, int, str]] = set()
    union_count = 0
    for source_ordinal, raw_root_row in enumerate(root_rows):
        root_row = _mapping(
            raw_root_row, label=f"panel slate descriptor[{source_ordinal}]"
        )
        leaf_identity = _identity(
            root_row.get("slate_freeze_identity"),
            label=f"slate[{source_ordinal}] freeze identity",
        )
        try:
            leaf, _, _, _, result, retained_leaf_identity = (
                freeze.reopen_slate_freeze_v1(
                    leaf_identity, read_exact=read_exact
                )
            )
        except freeze.CorpusR6FullUnionPanelFreezeV1Error as exc:
            raise CorpusR6FullUnionRealizedGradingV1Error(
                f"slate[{source_ordinal}] freeze exact replay differs"
            ) from exc
        if (
            retained_leaf_identity != leaf_identity
            or root_row.get("source_ordinal") != source_ordinal
            or leaf.get("source_ordinal") != source_ordinal
            or root_row.get("slate_id") != leaf.get("slate_id")
            or root_row.get("slate_freeze_sha256")
            != leaf.get("slate_freeze_sha256")
            or root_row.get("task_result_identity")
            != leaf.get("task_result_identity")
            or root_row.get("task_result_sha256")
            != result.get("task_result_sha256")
            or root_row.get("scope_count") != SCOPES_PER_SLATE
            or root_row.get("book_count") != BOOKS_PER_SLATE
            or root_row.get("prefix_count")
            != BOOKS_PER_SLATE * PREFIXES_PER_BOOK
            or leaf.get("manifest_identity") != root.get("manifest_identity")
        ):
            _fail(f"slate[{source_ordinal}] root/leaf/result binding differs")
        population, roster_by_lineup, _, scopes, strategies = (
            _population_from_result(
                source_ordinal=source_ordinal, result=result, leaf=leaf
            )
        )
        if (
            canonical_json_bytes(strategies) != canonical_json_bytes(root_strategies)
            or root.get("strategy_registry_sha256")
            != canonical_sha256(root_strategies)
        ):
            _fail(f"slate[{source_ordinal}] root/result strategy splice differs")
        books = _books_from_result(
            source_ordinal=source_ordinal,
            scopes=scopes,
            strategies=strategies,
            leaf=leaf,
            roster_by_lineup=roster_by_lineup,
        )
        for book in books:
            if book.coordinate in all_coordinates:
                _fail("source/scope/strategy/book coordinate repeats across panel")
            all_coordinates.add(book.coordinate)
        union_count += len(population)
        prepared.append(_PreparedSlate(
            source_ordinal=source_ordinal,
            slate_id=_string(leaf.get("slate_id"), label="slate ID"),
            leaf=leaf,
            leaf_identity=leaf_identity,
            result=result,
            population=population,
            books=books,
        ))
    if (
        len(prepared) != SOURCE_SLATE_COUNT
        or len(all_coordinates) != PANEL_BOOK_COUNT
        or union_count != root.get("union_lineup_count")
    ):
        _fail("complete 54x48 panel census differs")
    return tuple(prepared)


def _book_coordinate_sha(book: _PreparedBook) -> str:
    return canonical_sha256({
        "source_ordinal": book.source_ordinal,
        "scope_ordinal": book.scope_ordinal,
        "strategy_ordinal": book.strategy_ordinal,
        "book_id": book.book_id,
    })


def _prefix_grade(
    *,
    book: _PreparedBook,
    descriptor: Mapping[str, object],
    rank_score_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    entry_count = _integer(
        descriptor.get("entry_count"), label="prefix entry count", minimum=1
    )
    score_rows = list(rank_score_rows[:entry_count])
    body = {
        "schema_version": PREFIX_GRADE_SCHEMA,
        "source_ordinal": book.source_ordinal,
        "scope_ordinal": book.scope_ordinal,
        "fit_scope_id": book.fit_scope_id,
        "strategy_ordinal": book.strategy_ordinal,
        "strategy_id": book.strategy_id,
        "book_id": book.book_id,
        "book_coordinate_sha256": _book_coordinate_sha(book),
        "entry_count": entry_count,
        "prefix_of_rank_80": True,
        "rank_80_payload_sha256": descriptor["rank_80_payload_sha256"],
        "prefix_descriptor_sha256": descriptor["prefix_descriptor_sha256"],
        "prefix_payload_sha256": descriptor["prefix_payload_sha256"],
        "selected_lineup_ids_sha256": descriptor[
            "selected_lineup_ids_sha256"
        ],
        "selected_rosters_sha256": descriptor["selected_rosters_sha256"],
        "rank_80_score_prefix_sha256": canonical_sha256(score_rows),
        "metrics": _basic_metrics(score_rows),
        "projected_from_union_score_lookup": True,
        "roster_sum_operation_count": 0,
    }
    return _with_hash(body, field="prefix_grade_sha256")


def _book_grade(
    *, book: _PreparedBook, score_by_lineup: Mapping[tuple[int, str], int],
) -> dict[str, object]:
    rank_rows: list[dict[str, object]] = []
    for selection_rank, lineup_id in enumerate(book.selected_lineup_ids):
        key = (book.source_ordinal, lineup_id)
        if key not in score_by_lineup:
            _fail("a frozen book contains a lineup outside its final union")
        rank_rows.append({
            "selection_rank": selection_rank,
            "lineup_id": lineup_id,
            "realized_score_micro": score_by_lineup[key],
        })
    raw_prefixes = _sequence(
        book.descriptor.get("prefixes"), label="book prefix descriptors"
    )
    prefixes = [
        _prefix_grade(
            book=book,
            descriptor=_mapping(raw, label="prefix descriptor"),
            rank_score_rows=rank_rows,
        )
        for raw in raw_prefixes
    ]
    body = {
        "schema_version": BOOK_GRADE_SCHEMA,
        "source_ordinal": book.source_ordinal,
        "scope_ordinal": book.scope_ordinal,
        "fit_scope_id": book.fit_scope_id,
        "heldout_block": book.heldout_block,
        "strategy_ordinal": book.strategy_ordinal,
        "strategy_id": book.strategy_id,
        "strategy_sha256": book.strategy_sha256,
        "book_id": book.book_id,
        "book_sha256": book.book_sha256,
        "book_coordinate_sha256": _book_coordinate_sha(book),
        "rank_80_entry_count": lane.ENTRY_BUDGET,
        "rank_80_score_rows": rank_rows,
        "rank_80_score_rows_sha256": canonical_sha256(rank_rows),
        "prefix_count": len(prefixes),
        "prefixes": prefixes,
        "projected_from_union_score_lookup": True,
        "roster_sum_operation_count": 0,
    }
    return _with_hash(body, field="book_grade_sha256")


def _slate_grade(
    *,
    prepared: _PreparedSlate,
    root: Mapping[str, object],
    root_identity: Mapping[str, object],
    snapshot: Mapping[str, object],
    snapshot_identity: Mapping[str, object],
    player_scores: Mapping[tuple[int, str], int],
) -> dict[str, object]:
    counter = _RosterSumCounter(ceiling=len(prepared.population))
    score_rows: list[dict[str, object]] = []
    score_by_lineup: dict[tuple[int, str], int] = {}
    for union_index, (lineup_id, roster) in enumerate(prepared.population):
        score = counter.score(
            source_ordinal=prepared.source_ordinal,
            roster=roster,
            player_scores=player_scores,
        )
        key = (prepared.source_ordinal, lineup_id)
        if key in score_by_lineup:
            raise AssertionError("validated final-union lineup repeated")
        score_by_lineup[key] = score
        score_rows.append({
            "source_ordinal": prepared.source_ordinal,
            "union_index": union_index,
            "lineup_id": lineup_id,
            "roster_identity_sha256": canonical_sha256(list(roster)),
            "realized_score_micro": score,
        })
    if counter.count != counter.ceiling or len(score_by_lineup) != counter.ceiling:
        _fail("final-union roster-sum operation count differs from its ceiling")
    book_grades = [
        _book_grade(book=book, score_by_lineup=score_by_lineup)
        for book in prepared.books
    ]
    coordinate_payload = [{
        "source_ordinal": row["source_ordinal"],
        "scope_ordinal": row["scope_ordinal"],
        "strategy_ordinal": row["strategy_ordinal"],
        "book_id": row["book_id"],
    } for row in book_grades]
    body = {
        "schema_version": SLATE_GRADE_SCHEMA,
        "source_ordinal": prepared.source_ordinal,
        "slate_id": prepared.slate_id,
        "panel_freeze_identity": dict(root_identity),
        "panel_freeze_sha256": root["panel_freeze_sha256"],
        "slate_freeze_identity": dict(prepared.leaf_identity),
        "slate_freeze_sha256": prepared.leaf["slate_freeze_sha256"],
        "task_result_identity": prepared.leaf["task_result_identity"],
        "task_result_sha256": prepared.result["task_result_sha256"],
        "outcome_snapshot_identity": dict(snapshot_identity),
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "population_descriptor_sha256": _mapping(
            prepared.leaf["all_block_union"], label="union descriptor"
        )["population_descriptor_sha256"],
        "union_lineup_count": len(score_rows),
        "union_score_rows": score_rows,
        "union_score_rows_sha256": canonical_sha256(score_rows),
        "union_metrics": _union_metrics(score_rows),
        "roster_sum_operation_ceiling": counter.ceiling,
        "roster_sum_operation_count": counter.count,
        "book_grade_count": len(book_grades),
        "book_coordinate_set_sha256": canonical_sha256(coordinate_payload),
        "book_grades": book_grades,
        "complete": True,
        "every_unique_final_union_roster_scored_once": True,
        "every_book_projected_from_union_score_lookup": True,
        "rank_80_score_rows_stored_once": True,
        "prefixes_store_hashes_and_metrics_only": True,
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    return _with_hash(body, field="slate_grade_sha256")


def _aggregate_slate_row(
    *, shard: Mapping[str, object], book: Mapping[str, object], prefix: Mapping[str, object],
) -> dict[str, object]:
    metrics = _mapping(prefix.get("metrics"), label="prefix metrics")
    thresholds = _sequence(metrics.get("thresholds"), label="prefix thresholds")
    return {
        "source_ordinal": shard["source_ordinal"],
        "slate_id": shard["slate_id"],
        "book_id": book["book_id"],
        "book_coordinate_sha256": book["book_coordinate_sha256"],
        "prefix_grade_sha256": prefix["prefix_grade_sha256"],
        "maximum_score_micro": metrics["maximum_score_micro"],
        "maximum_lineup_ids_sha256": metrics["maximum_lineup_ids_sha256"],
        "lineup_score_sum_micro": metrics["score_sum_micro"],
        "at_or_above_counts": {
            str(row["threshold_dk"]): row["at_or_above_count"]
            for row in thresholds
        },
        "produced_hit_flags": {
            str(row["threshold_dk"]): row["produced_at_least_one_hit"]
            for row in thresholds
        },
    }


def _aggregate_cells(
    shards: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    lookup: dict[
        tuple[int, int, int],
        list[
            tuple[
                Mapping[str, object],
                Mapping[str, object],
                Mapping[str, object],
            ]
        ],
    ] = {}
    prefix_order = {value: ordinal for ordinal, value in enumerate(PREFIX_SIZES)}
    for raw_shard in shards:
        shard = _mapping(raw_shard, label="slate grade")
        for raw_book in _sequence(shard.get("book_grades"), label="book grades"):
            book = _mapping(raw_book, label="book grade")
            for raw_prefix in _sequence(book.get("prefixes"), label="prefix grades"):
                prefix = _mapping(raw_prefix, label="prefix grade")
                entry_count = int(prefix["entry_count"])
                if entry_count not in prefix_order:
                    _fail("aggregate saw an unregistered prefix size")
                key = (
                    int(book["scope_ordinal"]),
                    int(book["strategy_ordinal"]),
                    entry_count,
                )
                lookup.setdefault(key, []).append((shard, book, prefix))
    expected_keys = {
        (scope, strategy, prefix)
        for scope in range(SCOPES_PER_SLATE)
        for strategy in range(STRATEGIES_PER_SCOPE)
        for prefix in PREFIX_SIZES
    }
    if set(lookup) != expected_keys:
        _fail("aggregate 6x8x3 cell lattice differs")
    result: list[dict[str, object]] = []
    for key in sorted(lookup, key=lambda value: (
        value[0], value[1], prefix_order[value[2]]
    )):
        scope_ordinal, strategy_ordinal, entry_count = key
        triples = sorted(lookup[key], key=lambda value: int(value[0]["source_ordinal"]))
        if (
            len(triples) != SOURCE_SLATE_COUNT
            or [int(value[0]["source_ordinal"]) for value in triples]
            != list(range(SOURCE_SLATE_COUNT))
        ):
            _fail("aggregate cell does not contain exactly 54 slate rows")
        first_book = triples[0][1]
        fit_scope_id = str(first_book["fit_scope_id"])
        strategy_id = str(first_book["strategy_id"])
        strategy_sha = str(first_book["strategy_sha256"])
        if any(
            int(book["scope_ordinal"]) != scope_ordinal
            or str(book["fit_scope_id"]) != fit_scope_id
            or int(book["strategy_ordinal"]) != strategy_ordinal
            or str(book["strategy_id"]) != strategy_id
            or str(book["strategy_sha256"]) != strategy_sha
            or int(prefix["entry_count"]) != entry_count
            for _, book, prefix in triples
        ):
            _fail("aggregate cell scope/strategy/prefix identity differs")
        rows = [
            _aggregate_slate_row(shard=shard, book=book, prefix=prefix)
            for shard, book, prefix in triples
        ]
        maximums = [int(row["maximum_score_micro"]) for row in rows]
        lineup_score_sum = sum(int(row["lineup_score_sum_micro"]) for row in rows)
        threshold_summaries: list[dict[str, object]] = []
        for threshold in THRESHOLDS_DK:
            key_text = str(threshold)
            slate_hits = sum(bool(row["produced_hit_flags"][key_text]) for row in rows)
            lineup_hits = sum(int(row["at_or_above_counts"][key_text]) for row in rows)
            threshold_summaries.append({
                "threshold_dk": threshold,
                "threshold_micro": threshold * MICRO_DK_PER_POINT,
                "operator": ">=",
                "slates_with_at_least_one_hit": slate_hits,
                "slate_hit_fraction": _rational(
                    slate_hits, SOURCE_SLATE_COUNT, unit="slates"
                ),
                "lineups_at_or_above_count": lineup_hits,
                "lineup_hit_fraction": _rational(
                    lineup_hits,
                    SOURCE_SLATE_COUNT * entry_count,
                    unit="lineup_occurrences",
                ),
            })
        body = {
            "schema_version": AGGREGATE_CELL_SCHEMA,
            "scope_ordinal": scope_ordinal,
            "fit_scope_id": fit_scope_id,
            "strategy_ordinal": strategy_ordinal,
            "strategy_id": strategy_id,
            "strategy_sha256": strategy_sha,
            "entry_count": entry_count,
            "source_slate_count": SOURCE_SLATE_COUNT,
            "slate_rows": rows,
            "slate_rows_sha256": canonical_sha256(rows),
            "lineup_occurrence_count": SOURCE_SLATE_COUNT * entry_count,
            "lineup_score_sum_micro": lineup_score_sum,
            "lineup_score_mean": _rational(
                lineup_score_sum,
                SOURCE_SLATE_COUNT * entry_count,
                unit="micro_dk",
            ),
            "slate_maximum_mean": _mean(maximums),
            "slate_maximum_median": _median(maximums),
            "minimum_slate_maximum_micro": min(maximums),
            "maximum_slate_maximum_micro": max(maximums),
            "thresholds": threshold_summaries,
            "complete": True,
        }
        result.append(_with_hash(body, field="aggregate_cell_sha256"))
    if len(result) != AGGREGATE_CELL_COUNT:
        raise AssertionError("registered aggregate cell count differs")
    return result


def _slate_descriptors(
    shards: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    return [{
        "source_ordinal": shard["source_ordinal"],
        "slate_id": shard["slate_id"],
        "slate_grade_sha256": shard["slate_grade_sha256"],
        "union_lineup_count": shard["union_lineup_count"],
        "roster_sum_operation_count": shard["roster_sum_operation_count"],
        "book_grade_count": shard["book_grade_count"],
        "book_coordinate_set_sha256": shard["book_coordinate_set_sha256"],
    } for shard in shards]


def _coverage(
    *, shards: Sequence[Mapping[str, object]], snapshot: Mapping[str, object],
) -> dict[str, object]:
    union_count = sum(int(shard["union_lineup_count"]) for shard in shards)
    operation_count = sum(
        int(shard["roster_sum_operation_count"]) for shard in shards
    )
    operation_ceiling = sum(
        int(shard["roster_sum_operation_ceiling"]) for shard in shards
    )
    return {
        "source_slate_count": len(shards),
        "scopes_per_slate": SCOPES_PER_SLATE,
        "strategies_per_scope": STRATEGIES_PER_SCOPE,
        "rank_80_books_per_slate": BOOKS_PER_SLATE,
        "rank_80_book_count": sum(int(shard["book_grade_count"]) for shard in shards),
        "prefixes_per_book": PREFIXES_PER_BOOK,
        "prefix_grade_count": PANEL_PREFIX_COUNT,
        "aggregate_cell_count": AGGREGATE_CELL_COUNT,
        "aggregate_slate_row_count": AGGREGATE_SLATE_ROW_COUNT,
        "unique_final_union_roster_count": union_count,
        "roster_sum_operation_ceiling": operation_ceiling,
        "roster_sum_operation_count": operation_count,
        "actual_player_outcome_row_count": snapshot["row_count"],
        "every_unique_final_union_roster_scored_once": operation_count == union_count,
        "roster_sum_operation_ceiling_equals_final_union_count": (
            operation_ceiling == union_count
        ),
        "every_book_projected_from_union_score_lookup": True,
        "all_4_14_80_prefixes_projected_from_rank_80": True,
        "actual_player_outcome_keys_exact": True,
        "complete": True,
    }


def _root(
    *,
    freeze_root: Mapping[str, object],
    freeze_root_identity: Mapping[str, object],
    projection: Mapping[str, object],
    snapshot: Mapping[str, object],
    snapshot_identity: Mapping[str, object],
    shards: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    descriptors = _slate_descriptors(shards)
    for descriptor in descriptors:
        _exact_keys(
            descriptor, _SLATE_DESCRIPTOR_FIELDS, label="slate-grade descriptor"
        )
    cells = _aggregate_cells(shards)
    coverage = _coverage(shards=shards, snapshot=snapshot)
    body = {
        "schema_version": LOGICAL_ROOT_SCHEMA,
        "panel_freeze_identity": dict(freeze_root_identity),
        "panel_freeze_sha256": freeze_root["panel_freeze_sha256"],
        "execution_manifest_sha256": freeze_root["execution_manifest_sha256"],
        "panel_index_identity": freeze_root["panel_index_identity"],
        "panel_index_sha256": freeze_root["panel_index_sha256"],
        "outcome_key_projection_identity": snapshot[
            "outcome_key_projection_identity"
        ],
        "outcome_key_projection_sha256": projection[
            "outcome_key_projection_sha256"
        ],
        "later_source_freeze_identity": snapshot[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_sha256": snapshot[
            "later_source_freeze_sha256"
        ],
        "realized_source_identity": snapshot["realized_source_identity"],
        "realized_source_sha256": snapshot["realized_source_sha256"],
        "outcome_snapshot_identity": dict(snapshot_identity),
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "score_unit": "micro_dk",
        "micro_dk_per_point": MICRO_DK_PER_POINT,
        "threshold_registry": _threshold_registry(),
        "fit_scope_ids": list(freeze.FIT_SCOPE_IDS),
        "strategy_registry": freeze_root["strategy_registry"],
        "strategy_registry_sha256": freeze_root["strategy_registry_sha256"],
        "prefix_sizes": list(PREFIX_SIZES),
        "coverage": coverage,
        "slate_grade_descriptors": descriptors,
        "slate_grade_descriptors_sha256": canonical_sha256(descriptors),
        "aggregate_cell_count": len(cells),
        "aggregate_cells": cells,
        "aggregate_cells_sha256": canonical_sha256(cells),
        "contest_metrics": {
            "availability": "unavailable",
            "reason": (
                "full_field_standings_duplicate_tie_settlement_and_"
                "payout_ladder_not_supplied"
            ),
            "rank": None,
            "roi_micro_usd": None,
        },
        "complete": True,
        "outcome_blind_freeze_mutated": False,
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    return _with_hash(body, field="realized_grade_sha256")


def _validate_thresholds(
    value: object, *, scores: Sequence[int], label: str,
) -> list[dict[str, object]]:
    rows = [
        _mapping(raw, label=f"{label}[{ordinal}]")
        for ordinal, raw in enumerate(_sequence(value, label=label))
    ]
    for row in rows:
        _exact_keys(row, _THRESHOLD_FIELDS, label="threshold metric")
    if canonical_json_bytes(rows) != canonical_json_bytes(_threshold_rows(scores)):
        _fail(f"{label} canonical replay differs")
    return rows


def _validate_basic_metrics(
    value: object,
    *,
    score_rows: Sequence[Mapping[str, object]],
    label: str,
) -> dict[str, object]:
    metrics = _mapping(value, label=label)
    _exact_keys(metrics, _BASIC_METRICS_FIELDS, label=label)
    scores = [int(row["realized_score_micro"]) for row in score_rows]
    _validate_thresholds(metrics.get("thresholds"), scores=scores, label="thresholds")
    expected = _basic_metrics(score_rows)
    if canonical_json_bytes(metrics) != canonical_json_bytes(expected):
        _fail(f"{label} canonical replay differs")
    return metrics


def _validate_slate_grade(value: object, *, source_ordinal: int) -> dict[str, object]:
    shard = _mapping(value, label=f"slate grade[{source_ordinal}]")
    _exact_keys(shard, _SLATE_FIELDS, label="slate grade")
    _validate_self_hash(shard, field="slate_grade_sha256", label="slate grade")
    score_rows = [
        _mapping(raw, label="union score row")
        for raw in _sequence(shard.get("union_score_rows"), label="union score rows")
    ]
    for union_index, row in enumerate(score_rows):
        _exact_keys(row, _UNION_SCORE_ROW_FIELDS, label="union score row")
        if (
            row.get("source_ordinal") != source_ordinal
            or row.get("union_index") != union_index
            or type(row.get("realized_score_micro")) is not int
        ):
            _fail("union score row coordinate/value differs")
    union_score_by_id = {
        str(row["lineup_id"]): int(row["realized_score_micro"])
        for row in score_rows
    }
    if len(union_score_by_id) != len(score_rows):
        _fail("union score rows repeat a lineup identity")
    union_metrics = _mapping(shard.get("union_metrics"), label="union metrics")
    _exact_keys(union_metrics, _UNION_METRICS_FIELDS, label="union metrics")
    expected_union_metrics = _union_metrics(score_rows)
    if canonical_json_bytes(union_metrics) != canonical_json_bytes(expected_union_metrics):
        _fail("union score metrics/tail identities differ")
    for raw_tail in _sequence(
        union_metrics.get("tail_identity_subsets"), label="tail subsets"
    ):
        _exact_keys(_mapping(raw_tail, label="tail subset"), _TAIL_FIELDS, label="tail subset")
    books = [
        _mapping(raw, label="book grade")
        for raw in _sequence(shard.get("book_grades"), label="book grades")
    ]
    coordinates: list[dict[str, object]] = []
    observed_cells: set[tuple[int, int]] = set()
    for book_ordinal, book in enumerate(books):
        _exact_keys(book, _BOOK_FIELDS, label="book grade")
        _validate_self_hash(book, field="book_grade_sha256", label="book grade")
        scope_ordinal = _integer(
            book.get("scope_ordinal"), label="book scope ordinal", minimum=0
        )
        strategy_ordinal = _integer(
            book.get("strategy_ordinal"), label="book strategy ordinal", minimum=0
        )
        coordinate = {
            "source_ordinal": source_ordinal,
            "scope_ordinal": scope_ordinal,
            "strategy_ordinal": strategy_ordinal,
            "book_id": book["book_id"],
        }
        expected_scope_ordinal = book_ordinal // STRATEGIES_PER_SCOPE
        expected_strategy_ordinal = book_ordinal % STRATEGIES_PER_SCOPE
        expected_heldout = (
            rw.WORLD_BLOCKS[scope_ordinal]
            if scope_ordinal < len(rw.WORLD_BLOCKS)
            else None
        )
        _string(book.get("book_id"), label="book ID")
        _digest(book.get("book_sha256"), label="book SHA")
        _string(book.get("strategy_id"), label="book strategy ID")
        _digest(book.get("strategy_sha256"), label="book strategy SHA")
        if (
            book.get("source_ordinal") != source_ordinal
            or not 0 <= scope_ordinal < SCOPES_PER_SLATE
            or not 0 <= strategy_ordinal < STRATEGIES_PER_SCOPE
            or scope_ordinal != expected_scope_ordinal
            or strategy_ordinal != expected_strategy_ordinal
            or book.get("fit_scope_id") != freeze.FIT_SCOPE_IDS[scope_ordinal]
            or book.get("heldout_block") != expected_heldout
            or book.get("book_coordinate_sha256") != canonical_sha256(coordinate)
            or (scope_ordinal, strategy_ordinal) in observed_cells
            or book.get("rank_80_entry_count") != lane.ENTRY_BUDGET
            or book.get("prefix_count") != PREFIXES_PER_BOOK
            or book.get("projected_from_union_score_lookup") is not True
            or book.get("roster_sum_operation_count") != 0
        ):
            _fail("book source/scope/strategy/book coordinate law differs")
        observed_cells.add((scope_ordinal, strategy_ordinal))
        coordinates.append(coordinate)
        rank_rows = [
            _mapping(raw, label="rank-80 score row")
            for raw in _sequence(
                book.get("rank_80_score_rows"), label="rank-80 score rows"
            )
        ]
        if (
            len(rank_rows) != lane.ENTRY_BUDGET
            or len({str(row.get("lineup_id")) for row in rank_rows})
            != lane.ENTRY_BUDGET
            or book.get("rank_80_score_rows_sha256") != canonical_sha256(rank_rows)
        ):
            _fail("rank-80 score row census/hash differs")
        for selection_rank, row in enumerate(rank_rows):
            _exact_keys(row, _RANK_SCORE_ROW_FIELDS, label="rank-80 score row")
            lineup_id = str(row.get("lineup_id"))
            if (
                row.get("selection_rank") != selection_rank
                or lineup_id not in union_score_by_id
                or row.get("realized_score_micro") != union_score_by_id[lineup_id]
            ):
                _fail("rank-80 book was not projected from the union score lookup")
        prefixes = [
            _mapping(raw, label="prefix grade")
            for raw in _sequence(book.get("prefixes"), label="prefix grades")
        ]
        if (
            len(prefixes) != PREFIXES_PER_BOOK
            or [row.get("entry_count") for row in prefixes] != list(PREFIX_SIZES)
        ):
            _fail("book prefix order is not exact first 4/14/80")
        for prefix, entry_count in zip(prefixes, PREFIX_SIZES, strict=True):
            _exact_keys(prefix, _PREFIX_FIELDS, label="prefix grade")
            _validate_self_hash(prefix, field="prefix_grade_sha256", label="prefix grade")
            for field in (
                "rank_80_payload_sha256", "prefix_descriptor_sha256",
                "prefix_payload_sha256", "selected_lineup_ids_sha256",
                "selected_rosters_sha256", "rank_80_score_prefix_sha256",
            ):
                _digest(prefix.get(field), label=f"prefix {field}")
            expected_score_rows = rank_rows[:entry_count]
            if (
                prefix.get("source_ordinal") != source_ordinal
                or prefix.get("scope_ordinal") != scope_ordinal
                or prefix.get("fit_scope_id") != book.get("fit_scope_id")
                or prefix.get("strategy_ordinal") != strategy_ordinal
                or prefix.get("strategy_id") != book.get("strategy_id")
                or prefix.get("book_id") != book.get("book_id")
                or prefix.get("book_coordinate_sha256")
                != book.get("book_coordinate_sha256")
                or prefix.get("prefix_of_rank_80") is not True
                or prefix.get("rank_80_score_prefix_sha256")
                != canonical_sha256(expected_score_rows)
                or prefix.get("projected_from_union_score_lookup") is not True
                or prefix.get("roster_sum_operation_count") != 0
            ):
                _fail("prefix grade is not an exact first-N rank projection")
            _validate_basic_metrics(
                prefix.get("metrics"),
                score_rows=expected_score_rows,
                label="prefix metrics",
            )
    if (
        shard.get("source_ordinal") != source_ordinal
        or shard.get("union_lineup_count") != len(score_rows)
        or shard.get("union_score_rows_sha256") != canonical_sha256(score_rows)
        or shard.get("roster_sum_operation_ceiling") != len(score_rows)
        or shard.get("roster_sum_operation_count") != len(score_rows)
        or shard.get("book_grade_count") != BOOKS_PER_SLATE
        or len(books) != BOOKS_PER_SLATE
        or len(observed_cells) != BOOKS_PER_SLATE
        or shard.get("book_coordinate_set_sha256") != canonical_sha256(coordinates)
        or shard.get("complete") is not True
        or shard.get("every_unique_final_union_roster_scored_once") is not True
        or shard.get("every_book_projected_from_union_score_lookup") is not True
        or shard.get("rank_80_score_rows_stored_once") is not True
        or shard.get("prefixes_store_hashes_and_metrics_only") is not True
        or shard.get("uses_realized_outcomes") is not True
        or any(shard.get(field) is not False for field in (
            "historical_retune_licensed", "historical_retry_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("slate grade coverage/authority law differs")
    _string(shard.get("slate_id"), label="slate-grade slate ID")
    for field in (
        "panel_freeze_identity", "slate_freeze_identity",
        "task_result_identity", "outcome_snapshot_identity",
    ):
        _identity(shard.get(field), label=f"slate-grade {field}")
    for field in (
        "panel_freeze_sha256", "slate_freeze_sha256", "task_result_sha256",
        "outcome_snapshot_sha256", "population_descriptor_sha256",
        "union_score_rows_sha256", "book_coordinate_set_sha256",
    ):
        _digest(shard.get(field), label=f"slate-grade {field}")
    return shard


def _validate_logical_grade_structure_v1(
    value: object, *, slate_grades: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Internal coherence check; this is deliberately not durable authority."""
    root = _mapping(value, label="realized grade root")
    _exact_keys(root, _ROOT_FIELDS, label="realized grade root")
    _validate_self_hash(
        root, field="realized_grade_sha256", label="realized grade root"
    )
    raw_shards = _sequence(slate_grades, label="slate grades")
    if len(raw_shards) != SOURCE_SLATE_COUNT:
        _fail("realized grade requires exactly 54 slate shards")
    shards = [
        _validate_slate_grade(raw, source_ordinal=source_ordinal)
        for source_ordinal, raw in enumerate(raw_shards)
    ]
    descriptors = _slate_descriptors(shards)
    cells = _aggregate_cells(shards)
    for descriptor in descriptors:
        _exact_keys(
            descriptor, _SLATE_DESCRIPTOR_FIELDS, label="slate-grade descriptor"
        )
    coverage = _mapping(root.get("coverage"), label="grade coverage")
    _exact_keys(coverage, _COVERAGE_FIELDS, label="grade coverage")
    actual_outcome_count = _integer(
        coverage.get("actual_player_outcome_row_count"),
        label="actual player outcome row count",
        minimum=1,
    )
    expected_union_count = sum(int(row["union_lineup_count"]) for row in shards)
    expected_operations = sum(
        int(row["roster_sum_operation_count"]) for row in shards
    )
    expected_coverage = {
        **_coverage(shards=shards, snapshot={"row_count": actual_outcome_count}),
    }
    panel_identity = _identity(
        root.get("panel_freeze_identity"), label="root panel-freeze identity"
    )
    snapshot_identity = _identity(
        root.get("outcome_snapshot_identity"), label="root snapshot identity"
    )
    strategy_registry = [
        _mapping(raw, label=f"root strategy[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(root.get("strategy_registry"), label="root strategies")
        )
    ]
    strategy_ids: list[str] = []
    strategy_shas: list[str] = []
    for ordinal, strategy in enumerate(strategy_registry):
        if strategy.get("ordinal") != ordinal:
            _fail("root strategy ordinals differ")
        strategy_ids.append(
            _string(strategy.get("strategy_id"), label="root strategy ID")
        )
        strategy_shas.append(
            _digest(strategy.get("strategy_sha256"), label="root strategy SHA")
        )
    if (
        len(strategy_registry) != STRATEGIES_PER_SCOPE
        or len(set(strategy_ids)) != STRATEGIES_PER_SCOPE
        or len(set(strategy_shas)) != STRATEGIES_PER_SCOPE
        or root.get("strategy_registry_sha256")
        != canonical_sha256(strategy_registry)
    ):
        _fail("root strategy registry differs")
    for field in (
        "panel_freeze_sha256", "execution_manifest_sha256",
        "panel_index_sha256", "outcome_key_projection_sha256",
        "later_source_freeze_sha256", "realized_source_sha256",
        "outcome_snapshot_sha256",
    ):
        _digest(root.get(field), label=f"root {field}")
    for field in (
        "panel_index_identity", "outcome_key_projection_identity",
        "later_source_freeze_identity", "realized_source_identity",
    ):
        _identity(root.get(field), label=f"root {field}")
    for source_ordinal, shard in enumerate(shards):
        for raw_book in _sequence(
            shard.get("book_grades"), label="root-bound book grades"
        ):
            book = _mapping(raw_book, label="root-bound book grade")
            strategy_ordinal = int(book["strategy_ordinal"])
            strategy = strategy_registry[strategy_ordinal]
            if (
                book.get("strategy_id") != strategy.get("strategy_id")
                or book.get("strategy_sha256") != strategy.get("strategy_sha256")
            ):
                _fail("root strategy/book binding differs")
        if (
            shard.get("panel_freeze_identity") != panel_identity
            or shard.get("panel_freeze_sha256") != root.get("panel_freeze_sha256")
            or shard.get("outcome_snapshot_identity") != snapshot_identity
            or shard.get("outcome_snapshot_sha256")
            != root.get("outcome_snapshot_sha256")
            or descriptors[source_ordinal].get("slate_grade_sha256")
            != shard.get("slate_grade_sha256")
        ):
            _fail("root/slate-grade authority binding differs")
    if (
        root.get("schema_version") != LOGICAL_ROOT_SCHEMA
        or root.get("score_unit") != "micro_dk"
        or root.get("micro_dk_per_point") != MICRO_DK_PER_POINT
        or root.get("threshold_registry") != _threshold_registry()
        or root.get("fit_scope_ids") != list(freeze.FIT_SCOPE_IDS)
        or root.get("prefix_sizes") != list(PREFIX_SIZES)
        or root.get("slate_grade_descriptors") != descriptors
        or root.get("slate_grade_descriptors_sha256") != canonical_sha256(descriptors)
        or root.get("aggregate_cell_count") != AGGREGATE_CELL_COUNT
        or root.get("aggregate_cells") != cells
        or root.get("aggregate_cells_sha256") != canonical_sha256(cells)
        or coverage != expected_coverage
        or coverage.get("unique_final_union_roster_count") != expected_union_count
        or coverage.get("roster_sum_operation_count") != expected_operations
        or root.get("contest_metrics") != {
            "availability": "unavailable",
            "reason": (
                "full_field_standings_duplicate_tie_settlement_and_"
                "payout_ladder_not_supplied"
            ),
            "rank": None,
            "roi_micro_usd": None,
        }
        or root.get("complete") is not True
        or root.get("outcome_blind_freeze_mutated") is not False
        or root.get("uses_realized_outcomes") is not True
        or any(root.get(field) is not False for field in (
            "historical_retune_licensed", "historical_retry_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("realized grade root coverage/aggregate law differs")
    for cell in cells:
        _exact_keys(cell, _AGGREGATE_CELL_FIELDS, label="aggregate cell")
        _validate_self_hash(
            cell, field="aggregate_cell_sha256", label="aggregate cell"
        )
        rows = _sequence(cell.get("slate_rows"), label="aggregate slate rows")
        for row in rows:
            _exact_keys(
                _mapping(row, label="aggregate slate row"),
                _AGGREGATE_SLATE_ROW_FIELDS,
                label="aggregate slate row",
            )
        for row in _sequence(cell.get("thresholds"), label="aggregate thresholds"):
            _exact_keys(
                _mapping(row, label="aggregate threshold"),
                _AGGREGATE_THRESHOLD_FIELDS,
                label="aggregate threshold",
            )
    return root, shards


def _persisted_shard_rows(
    *,
    logical_root: Mapping[str, object],
    shards: Sequence[Mapping[str, object]],
    shard_identities: Sequence[Mapping[str, object]],
    output_prefix: str,
) -> list[dict[str, object]]:
    if (
        len(shards) != SOURCE_SLATE_COUNT
        or len(shard_identities) != SOURCE_SLATE_COUNT
    ):
        _fail("persisted grade requires exactly 54 shard identities")
    descriptors = _sequence(
        logical_root.get("slate_grade_descriptors"),
        label="logical slate-grade descriptors",
    )
    rows: list[dict[str, object]] = []
    seen_identities: set[tuple[str, str, str, int]] = set()
    for source_ordinal, (raw_shard, raw_identity, raw_descriptor) in enumerate(
        zip(shards, shard_identities, descriptors, strict=True)
    ):
        shard = _mapping(raw_shard, label=f"slate grade[{source_ordinal}]")
        identity = _identity(
            raw_identity, label=f"slate grade[{source_ordinal}] identity"
        )
        descriptor = _mapping(
            raw_descriptor, label=f"slate descriptor[{source_ordinal}]"
        )
        target_uri = (
            f"{output_prefix}/slate-grades/"
            f"{source_ordinal:02d}-{shard['slate_id']}.json"
        )
        identity_key = (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        if (
            identity["uri"] != target_uri
            or identity["sha256"] != sha256(canonical_json_bytes(shard)).hexdigest()
            or identity["bytes"] != len(canonical_json_bytes(shard))
            or shard.get("source_ordinal") != source_ordinal
            or descriptor.get("source_ordinal") != source_ordinal
            or descriptor.get("slate_id") != shard.get("slate_id")
            or descriptor.get("slate_grade_sha256")
            != shard.get("slate_grade_sha256")
            or identity_key in seen_identities
        ):
            _fail("persisted slate-grade content identity/binding differs")
        seen_identities.add(identity_key)
        rows.append(_with_hash({
            "source_ordinal": source_ordinal,
            "slate_id": shard["slate_id"],
            "target_uri": target_uri,
            "slate_grade_identity": identity,
            "slate_grade_sha256": shard["slate_grade_sha256"],
        }, field="slate_grade_object_sha256"))
    return rows


def _build_persisted_root(
    *,
    logical_root: Mapping[str, object],
    shards: Sequence[Mapping[str, object]],
    shard_identities: Sequence[Mapping[str, object]],
    output_prefix: str,
) -> dict[str, object]:
    retained_logical, retained_shards = _validate_logical_grade_structure_v1(
        logical_root, slate_grades=shards
    )
    rows = _persisted_shard_rows(
        logical_root=retained_logical,
        shards=retained_shards,
        shard_identities=shard_identities,
        output_prefix=output_prefix,
    )
    body = {
        "schema_version": PERSISTED_ROOT_SCHEMA,
        "publication_mode": "create_once_root_last",
        "target_uri": f"{output_prefix}/realized-grade-root.json",
        "logical_grade_root": retained_logical,
        "logical_grade_root_sha256": retained_logical["realized_grade_sha256"],
        "source_slate_count": SOURCE_SLATE_COUNT,
        "slate_grade_objects": rows,
        "slate_grade_objects_sha256": canonical_sha256(rows),
        "complete": True,
        "all_shard_identities_resolved_before_root_build": True,
        "root_create_once_requested_last": True,
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    return _with_hash(body, field="persisted_grade_root_sha256")


def _validate_persisted_root_structure_v1(
    value: object,
    *,
    identity: object,
    read_exact: ReadExact,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    list[dict[str, object]], list[dict[str, object]], str,
]:
    supplied = _mapping(value, label="persisted realized-grade root")
    root, retained_identity = _exact_read_json(
        identity,
        read_exact=read_exact,
        label="persisted realized-grade root",
    )
    if canonical_json_bytes(supplied) != canonical_json_bytes(root):
        _fail("supplied persisted root differs from its exact-reopened object")
    _exact_keys(root, _PERSISTED_ROOT_FIELDS, label="persisted realized-grade root")
    _validate_self_hash(
        root,
        field="persisted_grade_root_sha256",
        label="persisted realized-grade root",
    )
    target_uri = _string(root.get("target_uri"), label="persisted root target URI")
    suffix = "/realized-grade-root.json"
    if not target_uri.endswith(suffix):
        _fail("persisted realized-grade root target differs")
    output_prefix = target_uri[:-len(suffix)]
    if (
        retained_identity["uri"] != target_uri
        or root.get("schema_version") != PERSISTED_ROOT_SCHEMA
        or root.get("publication_mode") != "create_once_root_last"
        or root.get("source_slate_count") != SOURCE_SLATE_COUNT
        or root.get("complete") is not True
        or root.get("all_shard_identities_resolved_before_root_build") is not True
        or root.get("root_create_once_requested_last") is not True
        or root.get("uses_realized_outcomes") is not True
        or any(root.get(field) is not False for field in (
            "historical_retune_licensed", "historical_retry_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("persisted realized-grade root authority law differs")
    rows = [
        _mapping(raw, label=f"persisted shard row[{source_ordinal}]")
        for source_ordinal, raw in enumerate(
            _sequence(root.get("slate_grade_objects"), label="persisted shards")
        )
    ]
    if (
        len(rows) != SOURCE_SLATE_COUNT
        or root.get("slate_grade_objects_sha256") != canonical_sha256(rows)
    ):
        _fail("persisted realized-grade shard census/hash differs")
    shards: list[dict[str, object]] = []
    shard_identities: list[dict[str, object]] = []
    for source_ordinal, row in enumerate(rows):
        _exact_keys(row, _PERSISTED_SHARD_FIELDS, label="persisted shard row")
        _validate_self_hash(
            row,
            field="slate_grade_object_sha256",
            label="persisted shard row",
        )
        identity_value = _identity(
            row.get("slate_grade_identity"),
            label=f"persisted shard[{source_ordinal}] identity",
        )
        expected_uri = (
            f"{output_prefix}/slate-grades/"
            f"{source_ordinal:02d}-{row.get('slate_id')}.json"
        )
        if (
            row.get("source_ordinal") != source_ordinal
            or row.get("target_uri") != expected_uri
            or identity_value["uri"] != expected_uri
        ):
            _fail("persisted shard source/target coordinate differs")
        shard, reopened_identity = _exact_read_json(
            identity_value,
            read_exact=read_exact,
            label=f"persisted slate grade[{source_ordinal}]",
        )
        if (
            reopened_identity != identity_value
            or shard.get("source_ordinal") != source_ordinal
            or shard.get("slate_id") != row.get("slate_id")
            or shard.get("slate_grade_sha256") != row.get("slate_grade_sha256")
        ):
            _fail("persisted shard row/body binding differs")
        shards.append(shard)
        shard_identities.append(identity_value)
    logical = _mapping(root.get("logical_grade_root"), label="logical grade root")
    if (
        root.get("logical_grade_root_sha256")
        != logical.get("realized_grade_sha256")
    ):
        _fail("persisted root/logical root binding differs")
    logical, shards = _validate_logical_grade_structure_v1(
        logical, slate_grades=shards
    )
    return (
        root, retained_identity, logical, shards, shard_identities, output_prefix
    )


def grade_r6_full_union_realized_v1(
    *,
    panel_freeze_identity: object,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    realized_source: object,
    realized_source_identity: object,
    outcome_snapshot: object,
    outcome_snapshot_identity: object,
    read_exact: ReadExact,
    contest_field: object | None = None,
    payout_contract: object | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Exact-open, score once, and return ``(aggregate_root, 54 shards)``."""
    if contest_field is not None or payout_contract is not None:
        _fail(
            "contest rank/ROI is unavailable until a separately validated "
            "full-field standings, duplicate/tie-settlement, and payout-ladder "
            "contract is implemented"
        )
    try:
        root, root_identity = freeze.reopen_panel_freeze_v1(
            panel_freeze_identity, read_exact=read_exact
        )
    except freeze.CorpusR6FullUnionPanelFreezeV1Error as exc:
        raise CorpusR6FullUnionRealizedGradingV1Error(
            "complete structural-freeze root exact replay differs"
        ) from exc
    projection = _mapping(
        outcome_key_projection, label="outcome-key projection"
    )
    try:
        snapshot, snapshot_identity, player_scores = (
            outcomes.validate_outcome_snapshot_v1(
                outcome_snapshot,
                identity=outcome_snapshot_identity,
                outcome_key_projection=outcome_key_projection,
                outcome_key_projection_identity=outcome_key_projection_identity,
                realized_source=realized_source,
                realized_source_identity=realized_source_identity,
                read_exact=read_exact,
            )
        )
    except outcomes.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise CorpusR6FullUnionRealizedGradingV1Error(
            "root-bound outcome snapshot exact replay differs"
        ) from exc
    if (
        snapshot.get("panel_freeze_identity") != root_identity
        or snapshot.get("panel_freeze_sha256") != root.get("panel_freeze_sha256")
        or projection.get("panel_freeze_identity") != root_identity
        or projection.get("panel_freeze_sha256") != root.get("panel_freeze_sha256")
        or projection.get("source_slate_count") != SOURCE_SLATE_COUNT
        or snapshot.get("score_unit") != "micro_dk"
        or snapshot.get("micro_dk_per_point") != MICRO_DK_PER_POINT
        or snapshot.get("exact_union_coverage") is not True
        or snapshot.get("lineup_scoring_performed") is not False
        or snapshot.get("full_field_standings_included") is not False
        or snapshot.get("payout_ladder_included") is not False
    ):
        _fail("outcome snapshot/root authority binding differs")
    prepared = _prepare_slates(
        root=root, root_identity=root_identity, read_exact=read_exact
    )
    required_outcome_keys = {
        (slate.source_ordinal, player_id)
        for slate in prepared
        for _, roster in slate.population
        for player_id in roster
    }
    if (
        set(player_scores) != required_outcome_keys
        or snapshot.get("row_count") != len(required_outcome_keys)
        or projection.get("required_player_count") != len(required_outcome_keys)
        or projection.get("outcome_key_count") != len(required_outcome_keys)
        or projection.get("all_block_union_lineup_count")
        != sum(len(slate.population) for slate in prepared)
    ):
        _fail("outcome-key snapshot does not exactly equal the final-union player set")
    shards = [
        _slate_grade(
            prepared=slate,
            root=root,
            root_identity=root_identity,
            snapshot=snapshot,
            snapshot_identity=snapshot_identity,
            player_scores=player_scores,
        )
        for slate in prepared
    ]
    grade_root = _root(
        freeze_root=root,
        freeze_root_identity=root_identity,
        projection=projection,
        snapshot=snapshot,
        snapshot_identity=snapshot_identity,
        shards=shards,
    )
    return _validate_logical_grade_structure_v1(
        grade_root, slate_grades=shards
    )


def grade_and_publish_r6_full_union_realized_v1(
    *,
    panel_freeze_identity: object,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    realized_source: object,
    realized_source_identity: object,
    outcome_snapshot: object,
    outcome_snapshot_identity: object,
    output_prefix: object,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    contest_field: object | None = None,
    payout_contract: object | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Publish 54 immutable shards first and their identity-bound root last."""
    prefix = _publication_prefix(output_prefix)
    logical_root, shards = grade_r6_full_union_realized_v1(
        panel_freeze_identity=panel_freeze_identity,
        outcome_key_projection=outcome_key_projection,
        outcome_key_projection_identity=outcome_key_projection_identity,
        realized_source=realized_source,
        realized_source_identity=realized_source_identity,
        outcome_snapshot=outcome_snapshot,
        outcome_snapshot_identity=outcome_snapshot_identity,
        read_exact=read_exact,
        contest_field=contest_field,
        payout_contract=payout_contract,
    )
    shard_identities: list[dict[str, object]] = []
    for source_ordinal, shard in enumerate(shards):
        target_uri = (
            f"{prefix}/slate-grades/"
            f"{source_ordinal:02d}-{shard['slate_id']}.json"
        )
        raw = canonical_json_bytes(shard)
        retained = publish_create_once(target_uri, raw)
        retained_shard, retained_identity = _verify_published_json(
            retained,
            target_uri=target_uri,
            raw=raw,
            read_exact=read_exact,
            label=f"published slate grade[{source_ordinal}]",
        )
        if canonical_json_bytes(retained_shard) != raw:
            _fail(
                f"published slate grade[{source_ordinal}] canonical replay differs"
            )
        shard_identities.append(retained_identity)
    persisted_root = _build_persisted_root(
        logical_root=logical_root,
        shards=shards,
        shard_identities=shard_identities,
        output_prefix=prefix,
    )
    root_target = str(persisted_root["target_uri"])
    root_raw = canonical_json_bytes(persisted_root)
    published_root = publish_create_once(root_target, root_raw)
    retained_root, root_identity = _verify_published_json(
        published_root,
        target_uri=root_target,
        raw=root_raw,
        read_exact=read_exact,
        label="published realized-grade root",
    )
    if canonical_json_bytes(retained_root) != root_raw:
        _fail("published realized-grade root canonical replay differs")
    return retained_root, root_identity


def validate_persisted_realized_grade_v1(
    value: object,
    *,
    identity: object,
    panel_freeze_identity: object,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    realized_source: object,
    realized_source_identity: object,
    outcome_snapshot: object,
    outcome_snapshot_identity: object,
    read_exact: ReadExact,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    list[dict[str, object]],
]:
    """Exact-reopen all shards and canonically rederive them from upstream."""
    (
        persisted_root,
        persisted_identity,
        logical_root,
        shards,
        shard_identities,
        output_prefix,
    ) = _validate_persisted_root_structure_v1(
        value, identity=identity, read_exact=read_exact
    )
    expected_logical, expected_shards = grade_r6_full_union_realized_v1(
        panel_freeze_identity=panel_freeze_identity,
        outcome_key_projection=outcome_key_projection,
        outcome_key_projection_identity=outcome_key_projection_identity,
        realized_source=realized_source,
        realized_source_identity=realized_source_identity,
        outcome_snapshot=outcome_snapshot,
        outcome_snapshot_identity=outcome_snapshot_identity,
        read_exact=read_exact,
    )
    if canonical_json_bytes(logical_root) != canonical_json_bytes(expected_logical):
        _fail("persisted logical grade does not canonically rederive from upstream")
    for source_ordinal, (observed, expected) in enumerate(
        zip(shards, expected_shards, strict=True)
    ):
        if canonical_json_bytes(observed) != canonical_json_bytes(expected):
            _fail(
                f"persisted slate grade[{source_ordinal}] does not canonically "
                "rederive from upstream"
            )
    expected_root = _build_persisted_root(
        logical_root=expected_logical,
        shards=expected_shards,
        shard_identities=shard_identities,
        output_prefix=output_prefix,
    )
    if canonical_json_bytes(persisted_root) != canonical_json_bytes(expected_root):
        _fail("persisted realized-grade root canonical replay differs")
    return persisted_root, persisted_identity, logical_root, shards


__all__ = [
    "AGGREGATE_CELL_COUNT",
    "AGGREGATE_CELL_SCHEMA",
    "BOOK_GRADE_SCHEMA",
    "CorpusR6FullUnionRealizedGradingV1Error",
    "LOGICAL_ROOT_SCHEMA",
    "PERSISTED_ROOT_SCHEMA",
    "PREFIX_GRADE_SCHEMA",
    "PREFIX_SIZES",
    "SLATE_GRADE_SCHEMA",
    "SOURCE_SLATE_COUNT",
    "THRESHOLDS_DK",
    "canonical_json_bytes",
    "canonical_sha256",
    "grade_and_publish_r6_full_union_realized_v1",
    "grade_r6_full_union_realized_v1",
    "validate_persisted_realized_grade_v1",
]
