"""Pure create-once publication for a sharded Core v1 realized grade.

The established :mod:`corpus_catalog_realized_grading` module remains the
only scoring implementation.  This module adds a narrow persistence boundary:
it validates that logical grade, splits its large score surface into 54 slate
shards, retains every weekly contrast at its original logical index, stores
all contrast summaries in one separate object, and publishes a small root
last.  Exact reopen reconstructs and validates the original logical grade.

No warehouse, outcome-query, selector, graph, or process API exists here.
Callers supply an already persisted player outcome snapshot to the existing
grader and provide only exact-read and create-once object-store callbacks.

V1 still materializes the logical grade in memory because the score-once
grader and its self-hash are authoritative.  A caller-provided byte ceiling
fails before the first publication; output sharding removes the unsafe giant
single-object publication without claiming a streaming scoring implementation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_catalog_realized_grading as grading
from nfl_dfs.research import corpus_core_v1_catalog as catalog_contract
from nfl_dfs.research import corpus_core_v1_outcome_snapshot as outcome_contract
from nfl_dfs.research import corpus_parametric_batch as batch


SHARDED_GRADE_ROOT_SCHEMA: Final = (
    "corpus-core-v1-sharded-realized-grade-root/v1"
)
SLATE_GRADE_SHARD_SCHEMA: Final = (
    "corpus-core-v1-realized-grade-slate-shard/v1"
)
CONTRAST_SUMMARY_SHARD_SCHEMA: Final = (
    "corpus-core-v1-realized-grade-contrast-summary-shard/v1"
)
PUBLICATION_MODE: Final = "create_once"
ROOT_FILENAME: Final = "realized-grade-root.json"
SUMMARY_FILENAME: Final = "contrast-summaries.json"
EXPECTED_CONTRAST_COUNT: Final = 45
EXPECTED_WEEKLY_ROWS_PER_SLATE: Final = (
    EXPECTED_CONTRAST_COUNT * len(catalog_contract.EXPECTED_BOOK_BUDGETS)
)
EXPECTED_WEEKLY_ROW_COUNT: Final = (
    catalog_contract.EXPECTED_SOURCE_SLATE_COUNT
    * EXPECTED_WEEKLY_ROWS_PER_SLATE
)
EXPECTED_CONTRAST_SUMMARY_COUNT: Final = EXPECTED_WEEKLY_ROWS_PER_SLATE

_FALSE_AUTHORITY_FIELDS: Final = (
    "historical_retune_licensed",
    "historical_retry_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
)
_GRADE_ARRAY_FIELDS: Final = frozenset({
    "slate_grades",
    "weekly_contrasts",
    "contrast_summaries",
    "realized_grade_sha256",
})
_GRADE_HEADER_KEYS: Final = frozenset({
    "schema_version",
    "phase",
    "evidence_class",
    "catalog_authority",
    "actual_player_outcome_authority",
    "score_unit",
    "micro_dk_per_point",
    "thresholds_micro",
    "coverage",
    "contest_metrics",
    "outcome_blind_catalog_mutated",
    "uses_realized_outcomes",
    *_FALSE_AUTHORITY_FIELDS,
})
_SLATE_SHARD_KEYS: Final = frozenset({
    "schema_version",
    "source_ordinal",
    "slate",
    "catalog_sha256",
    "outcome_snapshot_sha256",
    "realized_grade_sha256",
    "slate_grade",
    "slate_grade_sha256",
    "weekly_contrast_count",
    "weekly_contrast_indices",
    "weekly_contrast_indices_sha256",
    "weekly_contrasts",
    "weekly_contrast_rows_sha256",
    "weekly_contrast_row_hashes_sha256",
    "complete",
    "uses_realized_outcomes",
    *_FALSE_AUTHORITY_FIELDS,
    "slate_grade_shard_sha256",
})
_SLATE_DESCRIPTOR_KEYS: Final = frozenset({
    "source_ordinal",
    "slate",
    "slate_grade_sha256",
    "weekly_contrast_count",
    "weekly_contrast_indices_sha256",
    "weekly_contrast_rows_sha256",
    "slate_grade_shard_sha256",
    "shard_identity",
    "descriptor_sha256",
})
_SUMMARY_SHARD_KEYS: Final = frozenset({
    "schema_version",
    "catalog_sha256",
    "outcome_snapshot_sha256",
    "realized_grade_sha256",
    "contrast_summary_count",
    "contrast_summaries",
    "contrast_summary_hashes_sha256",
    "complete",
    "uses_realized_outcomes",
    *_FALSE_AUTHORITY_FIELDS,
    "contrast_summary_shard_sha256",
})
_SUMMARY_DESCRIPTOR_KEYS: Final = frozenset({
    "contrast_summary_count",
    "contrast_summary_hashes_sha256",
    "contrast_summary_shard_sha256",
    "summary_identity",
    "descriptor_sha256",
})
_MATERIALIZATION_METRIC_KEYS: Final = frozenset({
    "logical_grade_canonical_bytes",
    "logical_grade_payload_ceiling_bytes",
    "slate_shard_count",
    "weekly_contrast_row_count",
    "contrast_summary_count",
    "slate_shard_payload_bytes",
    "summary_shard_payload_bytes",
    "largest_component_payload_bytes",
    "logical_grade_assembled_in_memory",
    "payload_ceiling_passed",
})
_ROOT_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "create_once",
    "realized_grade_sha256",
    "catalog_sha256",
    "catalog_identity",
    "outcome_snapshot_sha256",
    "outcome_snapshot_identity",
    "player_source_identity",
    "grade_header",
    "grade_header_sha256",
    "slate_shard_uri_law",
    "slate_shard_count",
    "slate_shard_descriptors",
    "slate_shard_descriptors_sha256",
    "summary_uri_law",
    "summary_descriptor",
    "materialization_metrics",
    "complete",
    "uses_realized_outcomes",
    *_FALSE_AUTHORITY_FIELDS,
    "sharded_grade_root_sha256",
})
_SLATE_KEYS: Final = frozenset({"season", "week", "slate_id"})


class CorpusCoreV1GradePublisherError(ValueError):
    """The sharded Core v1 realized-grade publication failed closed."""


@dataclass(frozen=True, slots=True)
class CreateOncePublication:
    """Caller-owned create-once result, reopened before it is trusted."""

    identity: Mapping[str, object]
    created: bool


@dataclass(frozen=True, slots=True)
class PublishedShardedCoreV1Grade:
    """Durable identities and recovery counts for one complete grade."""

    root: Mapping[str, object]
    root_identity: Mapping[str, object]
    slate_shard_identities: tuple[Mapping[str, object], ...]
    summary_identity: Mapping[str, object]
    created_slate_shard_count: int
    recovered_slate_shard_count: int
    summary_created: bool
    root_created: bool


ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], CreateOncePublication]


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1GradePublisherError(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _fail(message: str) -> None:
    raise CorpusCoreV1GradePublisherError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1GradePublisherError(str(exc)) from exc


def _parse_json(raw: bytes, *, label: str) -> object:
    try:
        return batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1GradePublisherError(str(exc)) from exc


def _self_hash(value: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    retained = value.get(field)
    body = {key: item for key, item in value.items() if key != field}
    if (
        type(retained) is not str
        or len(retained) != 64
        or any(character not in "0123456789abcdef" for character in retained)
        or canonical_sha256(body) != retained
    ):
        _fail(f"{label} self-hash differs")


def _output_prefix(value: object) -> str:
    try:
        return batch._gcs_uri(  # noqa: SLF001
            value, label="Core v1 realized-grade output prefix", prefix=True
        )
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1GradePublisherError(str(exc)) from exc


def slate_shard_uri(output_prefix: str, source_ordinal: int) -> str:
    prefix = _output_prefix(output_prefix)
    ordinal = _exact_int(
        source_ordinal, label="Core v1 grade-shard source ordinal"
    )
    if ordinal >= catalog_contract.EXPECTED_SOURCE_SLATE_COUNT:
        _fail("Core v1 grade-shard source ordinal is outside 0..53")
    return f"{prefix}slate-grades/{ordinal:02d}.json"


def summary_uri(output_prefix: str) -> str:
    return _output_prefix(output_prefix) + SUMMARY_FILENAME


def root_uri(output_prefix: str) -> str:
    return _output_prefix(output_prefix) + ROOT_FILENAME


def _read_json_exact(
    identity: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object], bytes]:
    retained_identity = _identity(identity, label=f"{label} identity")
    try:
        raw = read_exact(retained_identity)
    except Exception as exc:
        raise CorpusCoreV1GradePublisherError(
            f"{label} exact read failed"
        ) from exc
    if type(raw) is not bytes:
        _fail(f"{label} exact reader did not return bytes")
    if (
        len(raw) != retained_identity["bytes"]
        or sha256(raw).hexdigest() != retained_identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ from their identity")
    value = dict(_mapping(_parse_json(raw, label=label), label=label))
    return retained_identity, value, raw


def _publish_exact(
    *,
    uri: str,
    value: Mapping[str, object],
    raw: bytes,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    label: str,
) -> tuple[dict[str, object], bool]:
    if canonical_json_bytes(value) != raw:
        raise AssertionError("precomputed publication bytes differ")
    try:
        publication = publish_create_once(uri, raw)
    except Exception as exc:
        raise CorpusCoreV1GradePublisherError(
            f"{label} create-once publication failed"
        ) from exc
    if (
        not isinstance(publication, CreateOncePublication)
        or type(publication.created) is not bool
    ):
        _fail(f"{label} create-once publication result differs")
    identity = _identity(publication.identity, label=f"{label} identity")
    if (
        identity["uri"] != uri
        or identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
    ):
        _fail(f"{label} create-once identity differs")
    _, reopened, reopened_raw = _read_json_exact(
        identity, read_exact=read_exact, label=f"reopened {label}"
    )
    if reopened_raw != raw or reopened != value:
        _fail(f"{label} create-once reopen differs")
    return identity, publication.created


def _grade_authority_hashes(
    grade_header: Mapping[str, object],
) -> tuple[str, str]:
    catalog_authority = _mapping(
        grade_header.get("catalog_authority"), label="grade catalog authority"
    )
    outcome_authority = _mapping(
        grade_header.get("actual_player_outcome_authority"),
        label="grade outcome authority",
    )
    catalog_sha = catalog_authority.get("catalog_sha256")
    outcome_sha = outcome_authority.get("outcome_snapshot_sha256")
    return (
        _sha(catalog_sha, label="grade catalog SHA"),
        _sha(outcome_sha, label="grade outcome snapshot SHA"),
    )


def _grade_authority_identities(
    grade_header: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    catalog_authority = _mapping(
        grade_header.get("catalog_authority"), label="grade catalog authority"
    )
    outcome_authority = _mapping(
        grade_header.get("actual_player_outcome_authority"),
        label="grade outcome authority",
    )
    return (
        _identity(
            catalog_authority.get("catalog_identity"),
            label="grade catalog identity",
        ),
        _identity(
            outcome_authority.get("outcome_snapshot_identity"),
            label="grade outcome snapshot identity",
        ),
        _identity(
            outcome_authority.get("source_identity"),
            label="grade player-source identity",
        ),
    )


def _complete_grade_census(value: Mapping[str, object]) -> None:
    """Reject duplicate or incomplete cells the base grade validator misses."""
    slates = [
        _mapping(row, label="census slate grade")
        for row in _sequence(value.get("slate_grades"), label="census slates")
    ]
    summaries = [
        _mapping(row, label="census contrast summary")
        for row in _sequence(
            value.get("contrast_summaries"), label="census summaries"
        )
    ]
    weekly = [
        _mapping(row, label="census weekly contrast")
        for row in _sequence(
            value.get("weekly_contrasts"), label="census weekly rows"
        )
    ]
    expected_book_keys = {
        (strategy_id, budget)
        for strategy_id in catalog_contract.STRATEGY_IDS
        for budget in catalog_contract.EXPECTED_BOOK_BUDGETS
    }
    for source_ordinal, slate in enumerate(slates):
        score_rows = [
            _mapping(row, label="census union score row")
            for row in _sequence(
                slate.get("union_score_rows"), label="census union score rows"
            )
        ]
        indices = [row.get("union_index") for row in score_rows]
        lineup_ids = [row.get("lineup_id") for row in score_rows]
        if (
            indices != list(range(len(score_rows)))
            or any(
                type(lineup_id) is not str or not lineup_id
                for lineup_id in lineup_ids
            )
            or len(lineup_ids) != len(set(lineup_ids))
        ):
            _fail("Core v1 union score-row census differs")
        score_by_index = {
            int(row["union_index"]): (
                row["lineup_id"], row.get("realized_score_micro")
            )
            for row in score_rows
        }
        books = [
            _mapping(row, label="census book grade")
            for row in _sequence(slate.get("book_grades"), label="census books")
        ]
        book_keys = [
            (row.get("strategy_id"), row.get("entry_budget")) for row in books
        ]
        if (
            slate.get("source_ordinal") != source_ordinal
            or set(book_keys) != expected_book_keys
            or len(book_keys) != len(expected_book_keys)
        ):
            _fail("Core v1 realized book-grade key census differs")
        for book in books:
            rows = [
                _mapping(row, label="census book score row")
                for row in _sequence(
                    book.get("roster_score_rows_rank_order"),
                    label="census book score rows",
                )
            ]
            budget = book.get("entry_budget")
            selected_indices = [row.get("union_index") for row in rows]
            if (
                type(budget) is not int
                or book.get("source_ordinal") != source_ordinal
                or [row.get("selection_rank") for row in rows]
                != list(range(budget))
                or any(type(index) is not int for index in selected_indices)
                or len(selected_indices) != len(set(selected_indices))
                or any(index not in score_by_index for index in selected_indices)
                or any(
                    (row.get("lineup_id"), row.get("realized_score_micro"))
                    != score_by_index[int(row["union_index"])]
                    for row in rows
                )
            ):
                _fail("Core v1 realized book score-row census differs")

    summary_by_key: dict[tuple[str, int], Mapping[str, object]] = {}
    for summary in summaries:
        contrast_id = summary.get("contrast_id")
        budget = summary.get("entry_budget")
        if (
            type(contrast_id) is not str
            or not contrast_id
            or budget not in catalog_contract.EXPECTED_BOOK_BUDGETS
            or (contrast_id, int(budget)) in summary_by_key
        ):
            _fail("Core v1 contrast-summary key census differs")
        summary_by_key[(contrast_id, int(budget))] = summary
    contrast_ids = {key[0] for key in summary_by_key}
    if (
        len(contrast_ids) != EXPECTED_CONTRAST_COUNT
        or set(summary_by_key)
        != {
            (contrast_id, budget)
            for contrast_id in contrast_ids
            for budget in catalog_contract.EXPECTED_BOOK_BUDGETS
        }
    ):
        _fail("Core v1 45-by-3 contrast-summary census differs")

    weekly_by_key: dict[tuple[str, int, int], Mapping[str, object]] = {}
    for row in weekly:
        contrast_id = row.get("contrast_id")
        budget = row.get("entry_budget")
        source_ordinal = row.get("source_ordinal")
        if (
            type(contrast_id) is not str
            or budget not in catalog_contract.EXPECTED_BOOK_BUDGETS
            or type(source_ordinal) is not int
            or source_ordinal < 0
            or source_ordinal >= catalog_contract.EXPECTED_SOURCE_SLATE_COUNT
        ):
            _fail("Core v1 weekly contrast key differs")
        key = (contrast_id, int(budget), source_ordinal)
        if key in weekly_by_key:
            _fail("Core v1 weekly contrast key repeats")
        weekly_by_key[key] = row
    expected_weekly_keys = {
        (contrast_id, budget, source_ordinal)
        for contrast_id, budget in summary_by_key
        for source_ordinal in range(catalog_contract.EXPECTED_SOURCE_SLATE_COUNT)
    }
    if set(weekly_by_key) != expected_weekly_keys:
        _fail("Core v1 45-by-3-by-54 weekly contrast census differs")
    for (contrast_id, budget), summary in summary_by_key.items():
        rows = [
            weekly_by_key[(contrast_id, budget, source_ordinal)]
            for source_ordinal in range(catalog_contract.EXPECTED_SOURCE_SLATE_COUNT)
        ]
        if (
            summary.get("weekly_contrast_rows_sha256")
            != canonical_sha256([row.get("contrast_row_sha256") for row in rows])
            or any(
                row.get(field) != summary.get(field)
                for row in rows
                for field in (
                    "contrast_sha256",
                    "family",
                    "challenger_strategy_id",
                    "comparator_strategy_id",
                )
            )
        ):
            _fail("Core v1 weekly/summary contrast binding differs")


def _validate_authoritative_grade_inputs(
    *,
    grade: Mapping[str, object],
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    outcome_snapshot: Mapping[str, object],
    outcome_snapshot_identity: Mapping[str, object],
    player_source: Mapping[str, object],
    player_source_identity: Mapping[str, object],
) -> None:
    """Bind every scored cell back to the exact upstream bodies."""
    try:
        retained_catalog = catalog_contract.validate_core_v1_catalog(catalog)
        retained_catalog_identity = batch.validate_json_identity(
            retained_catalog,
            catalog_identity,
            label="authoritative grade catalog identity",
        )
        retained_snapshot_identity = batch.validate_json_identity(
            outcome_snapshot,
            outcome_snapshot_identity,
            label="authoritative grade outcome snapshot identity",
        )
        retained_source_identity = batch.validate_json_identity(
            player_source,
            player_source_identity,
            label="authoritative grade player source identity",
        )
    except (
        catalog_contract.CorpusCoreV1CatalogError,
        batch.CorpusParametricBatchError,
    ) as exc:
        raise CorpusCoreV1GradePublisherError(str(exc)) from exc
    header = {
        key: item for key, item in grade.items() if key not in _GRADE_ARRAY_FIELDS
    }
    catalog_authority = _mapping(
        header.get("catalog_authority"), label="authoritative catalog binding"
    )
    outcome_authority = _mapping(
        header.get("actual_player_outcome_authority"),
        label="authoritative outcome binding",
    )
    if (
        catalog_authority.get("catalog_identity") != retained_catalog_identity
        or catalog_authority.get("catalog_sha256")
        != retained_catalog["catalog_sha256"]
        or outcome_authority.get("outcome_snapshot_identity")
        != retained_snapshot_identity
        or outcome_authority.get("source_identity") != retained_source_identity
        or outcome_authority.get("outcome_snapshot_sha256")
        != outcome_snapshot.get("outcome_snapshot_sha256")
    ):
        _fail("Core v1 realized grade upstream authority differs")

    for source_ordinal, (catalog_slate_raw, grade_slate_raw) in enumerate(zip(
        retained_catalog["slates"], grade["slate_grades"], strict=True
    )):
        catalog_slate = _mapping(catalog_slate_raw, label="authority catalog slate")
        grade_slate = _mapping(grade_slate_raw, label="authority grade slate")
        union = _mapping(
            catalog_slate.get("union_population"), label="authority union"
        )
        score_rows = [
            _mapping(row, label="authority score row")
            for row in _sequence(
                grade_slate.get("union_score_rows"), label="authority score rows"
            )
        ]
        expected_lineups = list(union["lineup_ids"])
        expected_roster_hashes = [
            canonical_sha256(list(roster)) for roster in union["rosters"]
        ]
        if (
            grade_slate.get("slate_catalog_sha256")
            != catalog_slate.get("slate_catalog_sha256")
            or [row.get("lineup_id") for row in score_rows] != expected_lineups
            or [row.get("roster_identity_sha256") for row in score_rows]
            != expected_roster_hashes
        ):
            _fail("Core v1 realized union scores differ from the catalog")
        catalog_books = {
            (row["strategy_id"], row["entry_budget"]): row
            for row in catalog_slate["books"]
        }
        for grade_book_raw in grade_slate["book_grades"]:
            grade_book = _mapping(grade_book_raw, label="authority book grade")
            key = (grade_book.get("strategy_id"), grade_book.get("entry_budget"))
            catalog_book = catalog_books.get(key)
            rows = list(grade_book["roster_score_rows_rank_order"])
            if (
                catalog_book is None
                or grade_book.get("book_sha256") != catalog_book.get("book_sha256")
                or [row["union_index"] for row in rows]
                != list(catalog_book["selected_union_indices"])
                or [row["lineup_id"] for row in rows]
                != list(catalog_book["selected_lineup_ids"])
            ):
                _fail("Core v1 realized book differs from its catalog book")

    contrast_registry = {
        row["contrast_id"]: row for row in retained_catalog["contrast_registry"]
    }
    for row_raw in [*grade["weekly_contrasts"], *grade["contrast_summaries"]]:
        row = _mapping(row_raw, label="authority contrast row")
        retained = contrast_registry.get(row.get("contrast_id"))
        if retained is None or any(
            row.get(field) != retained.get(field)
            for field in (
                "contrast_sha256",
                "family",
                "challenger_strategy_id",
                "comparator_strategy_id",
            )
        ):
            _fail("Core v1 realized contrast differs from its catalog registry")


def _common_authority_body() -> dict[str, object]:
    return {
        "uses_realized_outcomes": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


def _build_slate_shard(
    *,
    realized_grade: Mapping[str, object],
    source_ordinal: int,
    weekly_indices: Sequence[int],
) -> dict[str, object]:
    grade_header = {
        key: value
        for key, value in realized_grade.items()
        if key not in _GRADE_ARRAY_FIELDS
    }
    catalog_sha, outcome_sha = _grade_authority_hashes(grade_header)
    slate_grade = dict(_mapping(
        realized_grade["slate_grades"][source_ordinal],
        label=f"logical slate grade[{source_ordinal}]",
    ))
    weekly = list(_sequence(
        realized_grade["weekly_contrasts"], label="logical weekly contrasts"
    ))
    rows = [dict(_mapping(weekly[index], label="logical weekly contrast"))
            for index in weekly_indices]
    body = {
        "schema_version": SLATE_GRADE_SHARD_SCHEMA,
        "source_ordinal": source_ordinal,
        "slate": dict(_mapping(slate_grade["slate"], label="slate grade key")),
        "catalog_sha256": catalog_sha,
        "outcome_snapshot_sha256": outcome_sha,
        "realized_grade_sha256": realized_grade["realized_grade_sha256"],
        "slate_grade": slate_grade,
        "slate_grade_sha256": slate_grade["slate_grade_sha256"],
        "weekly_contrast_count": len(rows),
        "weekly_contrast_indices": list(weekly_indices),
        "weekly_contrast_indices_sha256": canonical_sha256(list(weekly_indices)),
        "weekly_contrasts": rows,
        "weekly_contrast_rows_sha256": canonical_sha256(rows),
        "weekly_contrast_row_hashes_sha256": canonical_sha256([
            row["contrast_row_sha256"] for row in rows
        ]),
        "complete": True,
        **_common_authority_body(),
    }
    return _self_hash(body, "slate_grade_shard_sha256")


def _build_summary_shard(
    *, realized_grade: Mapping[str, object],
) -> dict[str, object]:
    grade_header = {
        key: value
        for key, value in realized_grade.items()
        if key not in _GRADE_ARRAY_FIELDS
    }
    catalog_sha, outcome_sha = _grade_authority_hashes(grade_header)
    summaries = [dict(_mapping(row, label="logical contrast summary"))
                 for row in _sequence(
                     realized_grade["contrast_summaries"],
                     label="logical contrast summaries",
                 )]
    body = {
        "schema_version": CONTRAST_SUMMARY_SHARD_SCHEMA,
        "catalog_sha256": catalog_sha,
        "outcome_snapshot_sha256": outcome_sha,
        "realized_grade_sha256": realized_grade["realized_grade_sha256"],
        "contrast_summary_count": len(summaries),
        "contrast_summaries": summaries,
        "contrast_summary_hashes_sha256": canonical_sha256([
            row["contrast_summary_sha256"] for row in summaries
        ]),
        "complete": True,
        **_common_authority_body(),
    }
    return _self_hash(body, "contrast_summary_shard_sha256")


def _slate_descriptor(
    *, shard: Mapping[str, object], shard_identity: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "source_ordinal": shard["source_ordinal"],
        "slate": dict(_mapping(shard["slate"], label="grade shard slate")),
        "slate_grade_sha256": shard["slate_grade_sha256"],
        "weekly_contrast_count": shard["weekly_contrast_count"],
        "weekly_contrast_indices_sha256": shard[
            "weekly_contrast_indices_sha256"
        ],
        "weekly_contrast_rows_sha256": shard[
            "weekly_contrast_rows_sha256"
        ],
        "slate_grade_shard_sha256": shard["slate_grade_shard_sha256"],
        "shard_identity": dict(shard_identity),
    }
    return _self_hash(body, "descriptor_sha256")


def _summary_descriptor(
    *, summary: Mapping[str, object], summary_identity: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "contrast_summary_count": summary["contrast_summary_count"],
        "contrast_summary_hashes_sha256": summary[
            "contrast_summary_hashes_sha256"
        ],
        "contrast_summary_shard_sha256": summary[
            "contrast_summary_shard_sha256"
        ],
        "summary_identity": dict(summary_identity),
    }
    return _self_hash(body, "descriptor_sha256")


def _validate_slate_shard(
    value: object,
    *,
    source_ordinal: int,
    realized_grade_sha256: str,
    catalog_sha256: str,
    outcome_snapshot_sha256: str,
) -> dict[str, object]:
    shard = dict(_mapping(value, label=f"realized grade shard[{source_ordinal}]"))
    _exact_keys(shard, _SLATE_SHARD_KEYS, label="realized grade slate shard")
    _validate_self_hash(
        shard,
        field="slate_grade_shard_sha256",
        label="realized grade slate shard",
    )
    slate = _mapping(shard.get("slate"), label="realized grade shard slate")
    _exact_keys(slate, _SLATE_KEYS, label="realized grade shard slate")
    slate_grade = _mapping(
        shard.get("slate_grade"), label="realized grade shard slate grade"
    )
    rows = [
        _mapping(row, label="shard weekly contrast row")
        for row in _sequence(
            shard.get("weekly_contrasts"), label="shard weekly contrasts"
        )
    ]
    indices = list(_sequence(
        shard.get("weekly_contrast_indices"),
        label="shard weekly contrast indices",
    ))
    if any(type(index) is not int for index in indices):
        _fail("shard weekly contrast indices must be exact integers")
    if (
        shard.get("schema_version") != SLATE_GRADE_SHARD_SCHEMA
        or shard.get("source_ordinal") != source_ordinal
        or shard.get("catalog_sha256") != catalog_sha256
        or shard.get("outcome_snapshot_sha256") != outcome_snapshot_sha256
        or shard.get("realized_grade_sha256") != realized_grade_sha256
        or shard.get("slate_grade_sha256")
        != slate_grade.get("slate_grade_sha256")
        or slate_grade.get("source_ordinal") != source_ordinal
        or slate_grade.get("slate") != slate
        or shard.get("weekly_contrast_count")
        != EXPECTED_WEEKLY_ROWS_PER_SLATE
        or len(rows) != EXPECTED_WEEKLY_ROWS_PER_SLATE
        or len(indices) != EXPECTED_WEEKLY_ROWS_PER_SLATE
        or indices != sorted(indices)
        or len(indices) != len(set(indices))
        or any(index < 0 or index >= EXPECTED_WEEKLY_ROW_COUNT for index in indices)
        or shard.get("weekly_contrast_indices_sha256")
        != canonical_sha256(indices)
        or shard.get("weekly_contrast_rows_sha256") != canonical_sha256(rows)
        or shard.get("weekly_contrast_row_hashes_sha256")
        != canonical_sha256([row["contrast_row_sha256"] for row in rows])
        or any(row.get("source_ordinal") != source_ordinal for row in rows)
        or shard.get("complete") is not True
        or shard.get("uses_realized_outcomes") is not True
        or any(shard.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("Core v1 realized grade slate-shard law differs")
    _validate_self_hash(
        slate_grade,
        field="slate_grade_sha256",
        label="sharded logical slate grade",
    )
    for row in rows:
        _validate_self_hash(
            _mapping(row, label="shard weekly contrast row"),
            field="contrast_row_sha256",
            label="shard weekly contrast row",
        )
    return shard


def _validate_summary_shard(
    value: object,
    *,
    realized_grade_sha256: str,
    catalog_sha256: str,
    outcome_snapshot_sha256: str,
) -> dict[str, object]:
    summary = dict(_mapping(value, label="realized grade contrast-summary shard"))
    _exact_keys(
        summary,
        _SUMMARY_SHARD_KEYS,
        label="realized grade contrast-summary shard",
    )
    _validate_self_hash(
        summary,
        field="contrast_summary_shard_sha256",
        label="realized grade contrast-summary shard",
    )
    rows = [
        _mapping(row, label="sharded contrast summary")
        for row in _sequence(
            summary.get("contrast_summaries"),
            label="sharded contrast summaries",
        )
    ]
    if (
        summary.get("schema_version") != CONTRAST_SUMMARY_SHARD_SCHEMA
        or summary.get("catalog_sha256") != catalog_sha256
        or summary.get("outcome_snapshot_sha256") != outcome_snapshot_sha256
        or summary.get("realized_grade_sha256") != realized_grade_sha256
        or summary.get("contrast_summary_count")
        != EXPECTED_CONTRAST_SUMMARY_COUNT
        or len(rows) != EXPECTED_CONTRAST_SUMMARY_COUNT
        or summary.get("contrast_summary_hashes_sha256")
        != canonical_sha256([row["contrast_summary_sha256"] for row in rows])
        or summary.get("complete") is not True
        or summary.get("uses_realized_outcomes") is not True
        or any(summary.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("Core v1 realized grade contrast-summary shard law differs")
    for row in rows:
        _validate_self_hash(
            _mapping(row, label="sharded contrast summary"),
            field="contrast_summary_sha256",
            label="sharded contrast summary",
        )
    return summary


def validate_sharded_core_v1_realized_grade_root(
    value: object,
) -> dict[str, object]:
    """Validate the compact root census without reading any component."""
    root = dict(_mapping(value, label="sharded Core v1 realized-grade root"))
    _exact_keys(root, _ROOT_KEYS, label="sharded Core v1 realized-grade root")
    _validate_self_hash(
        root,
        field="sharded_grade_root_sha256",
        label="sharded Core v1 realized-grade root",
    )
    realized_grade_sha = _sha(
        root.get("realized_grade_sha256"), label="logical realized-grade SHA"
    )
    header = dict(_mapping(root.get("grade_header"), label="grade header"))
    _exact_keys(header, _GRADE_HEADER_KEYS, label="grade header")
    catalog_sha, outcome_sha = _grade_authority_hashes(header)
    (
        catalog_identity,
        outcome_snapshot_identity,
        player_source_identity,
    ) = _grade_authority_identities(header)
    descriptors = list(_sequence(
        root.get("slate_shard_descriptors"), label="grade shard descriptors"
    ))
    summary_descriptor = _mapping(
        root.get("summary_descriptor"), label="grade summary descriptor"
    )
    _exact_keys(
        summary_descriptor,
        _SUMMARY_DESCRIPTOR_KEYS,
        label="grade summary descriptor",
    )
    _validate_self_hash(
        summary_descriptor,
        field="descriptor_sha256",
        label="grade summary descriptor",
    )
    summary_identity = _identity(
        summary_descriptor.get("summary_identity"),
        label="grade summary identity",
    )
    _sha(
        summary_descriptor.get("contrast_summary_hashes_sha256"),
        label="descriptor contrast-summary hashes SHA",
    )
    _sha(
        summary_descriptor.get("contrast_summary_shard_sha256"),
        label="descriptor contrast-summary shard SHA",
    )
    metrics = _mapping(
        root.get("materialization_metrics"), label="grade materialization metrics"
    )
    _exact_keys(
        metrics,
        _MATERIALIZATION_METRIC_KEYS,
        label="grade materialization metrics",
    )
    coverage = _mapping(header.get("coverage"), label="grade header coverage")
    logical_bytes = _exact_int(
        metrics.get("logical_grade_canonical_bytes"),
        label="logical realized-grade bytes",
        minimum=1,
    )
    ceiling = _exact_int(
        metrics.get("logical_grade_payload_ceiling_bytes"),
        label="logical realized-grade byte ceiling",
        minimum=1,
    )
    slate_payload_bytes = _exact_int(
        metrics.get("slate_shard_payload_bytes"),
        label="slate shard payload bytes",
        minimum=1,
    )
    summary_payload_bytes = _exact_int(
        metrics.get("summary_shard_payload_bytes"),
        label="summary shard payload bytes",
        minimum=1,
    )
    largest_payload = _exact_int(
        metrics.get("largest_component_payload_bytes"),
        label="largest grade component bytes",
        minimum=1,
    )
    if (
        root.get("schema_version") != SHARDED_GRADE_ROOT_SCHEMA
        or root.get("publication_mode") != PUBLICATION_MODE
        or root.get("create_once") is not True
        or root.get("realized_grade_sha256") != realized_grade_sha
        or root.get("catalog_sha256") != catalog_sha
        or root.get("catalog_identity") != catalog_identity
        or root.get("outcome_snapshot_sha256") != outcome_sha
        or root.get("outcome_snapshot_identity") != outcome_snapshot_identity
        or root.get("player_source_identity") != player_source_identity
        or root.get("grade_header_sha256") != canonical_sha256(header)
        or root.get("slate_shard_uri_law")
        != "{output_prefix}slate-grades/{source_ordinal:02d}.json"
        or root.get("slate_shard_count")
        != catalog_contract.EXPECTED_SOURCE_SLATE_COUNT
        or len(descriptors) != catalog_contract.EXPECTED_SOURCE_SLATE_COUNT
        or root.get("slate_shard_descriptors_sha256")
        != canonical_sha256(descriptors)
        or root.get("summary_uri_law")
        != "{output_prefix}contrast-summaries.json"
        or summary_descriptor.get("contrast_summary_count")
        != EXPECTED_CONTRAST_SUMMARY_COUNT
        or metrics.get("slate_shard_count")
        != catalog_contract.EXPECTED_SOURCE_SLATE_COUNT
        or metrics.get("weekly_contrast_row_count")
        != EXPECTED_WEEKLY_ROW_COUNT
        or metrics.get("contrast_summary_count")
        != EXPECTED_CONTRAST_SUMMARY_COUNT
        or slate_payload_bytes
        != sum(
            _identity(
                _mapping(row, label="grade shard descriptor").get(
                    "shard_identity"
                ),
                label="grade shard identity",
            )["bytes"]
            for row in descriptors
        )
        or summary_payload_bytes != summary_identity["bytes"]
        or largest_payload
        != max(
            summary_payload_bytes,
            *(
                _identity(
                    _mapping(row, label="grade shard descriptor").get(
                        "shard_identity"
                    ),
                    label="grade shard identity",
                )["bytes"]
                for row in descriptors
            ),
        )
        or logical_bytes > ceiling
        or metrics.get("logical_grade_assembled_in_memory") is not True
        or metrics.get("payload_ceiling_passed") is not True
        or coverage.get("source_slate_count")
        != catalog_contract.EXPECTED_SOURCE_SLATE_COUNT
        or coverage.get("weekly_contrast_cell_count")
        != EXPECTED_WEEKLY_ROW_COUNT
        or coverage.get("contrast_summary_count")
        != EXPECTED_CONTRAST_SUMMARY_COUNT
        or root.get("complete") is not True
        or root.get("uses_realized_outcomes") is not True
        or any(root.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
        or header.get("uses_realized_outcomes") is not True
        or any(header.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("sharded Core v1 realized-grade root law differs")

    observed_uris: set[str] = {str(summary_identity["uri"])}
    observed_slates: set[tuple[object, object, object]] = set()
    observed_weekly = 0
    for source_ordinal, raw in enumerate(descriptors):
        descriptor = _mapping(
            raw, label=f"grade shard descriptor[{source_ordinal}]"
        )
        _exact_keys(
            descriptor,
            _SLATE_DESCRIPTOR_KEYS,
            label="grade slate-shard descriptor",
        )
        _validate_self_hash(
            descriptor,
            field="descriptor_sha256",
            label="grade slate-shard descriptor",
        )
        slate = _mapping(descriptor.get("slate"), label="grade descriptor slate")
        _exact_keys(slate, _SLATE_KEYS, label="grade descriptor slate")
        identity = _identity(
            descriptor.get("shard_identity"), label="grade shard identity"
        )
        _sha(
            descriptor.get("slate_grade_sha256"),
            label="descriptor slate-grade SHA",
        )
        _sha(
            descriptor.get("weekly_contrast_indices_sha256"),
            label="descriptor weekly-index SHA",
        )
        _sha(
            descriptor.get("weekly_contrast_rows_sha256"),
            label="descriptor weekly-row SHA",
        )
        _sha(
            descriptor.get("slate_grade_shard_sha256"),
            label="descriptor grade-shard SHA",
        )
        slate_key = (slate.get("season"), slate.get("week"), slate.get("slate_id"))
        if (
            descriptor.get("source_ordinal") != source_ordinal
            or descriptor.get("weekly_contrast_count")
            != EXPECTED_WEEKLY_ROWS_PER_SLATE
            or identity["uri"] in observed_uris
            or slate_key in observed_slates
        ):
            _fail("sharded Core v1 grade descriptor census differs")
        observed_uris.add(str(identity["uri"]))
        observed_slates.add(slate_key)
        observed_weekly += int(descriptor["weekly_contrast_count"])
    if observed_weekly != EXPECTED_WEEKLY_ROW_COUNT:
        _fail("sharded Core v1 grade weekly contrast census differs")
    return root


def _publish_validated_sharded_core_v1_realized_grade(
    *,
    realized_grade: Mapping[str, object],
    output_prefix: str,
    max_logical_grade_bytes: int,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> PublishedShardedCoreV1Grade:
    """Mechanically shard a grade already bound to exact upstream inputs.

    This private helper is intentionally not an authority boundary.  The only
    public grade-and-publish path below first runs the established grader from
    exact upstream bodies and identities, then independently replays those
    bindings before this create-once splitter can write anything.
    """
    prefix = _output_prefix(output_prefix)
    ceiling = _exact_int(
        max_logical_grade_bytes,
        label="Core v1 logical realized-grade byte ceiling",
        minimum=1,
    )
    try:
        retained_grade = grading.validate_core_v1_realized_grade(realized_grade)
    except grading.CorpusCatalogRealizedGradingError as exc:
        raise CorpusCoreV1GradePublisherError(str(exc)) from exc
    _complete_grade_census(retained_grade)
    logical_raw = canonical_json_bytes(retained_grade)
    if len(logical_raw) > ceiling:
        _fail(
            "logical Core v1 realized grade exceeds its configured payload "
            f"ceiling ({len(logical_raw)} > {ceiling})"
        )
    grade_header = {
        key: value
        for key, value in retained_grade.items()
        if key not in _GRADE_ARRAY_FIELDS
    }
    _exact_keys(grade_header, _GRADE_HEADER_KEYS, label="logical grade header")
    catalog_sha, outcome_sha = _grade_authority_hashes(grade_header)
    (
        catalog_identity,
        outcome_snapshot_identity,
        player_source_identity,
    ) = _grade_authority_identities(grade_header)

    weekly_indices_by_slate: list[list[int]] = [
        [] for _ in range(catalog_contract.EXPECTED_SOURCE_SLATE_COUNT)
    ]
    for index, raw in enumerate(retained_grade["weekly_contrasts"]):
        row = _mapping(raw, label=f"logical weekly contrast[{index}]")
        source_ordinal = _exact_int(
            row.get("source_ordinal"), label="weekly contrast source ordinal"
        )
        if source_ordinal >= catalog_contract.EXPECTED_SOURCE_SLATE_COUNT:
            _fail("weekly contrast source ordinal is outside 0..53")
        weekly_indices_by_slate[source_ordinal].append(index)
    if any(
        len(indices) != EXPECTED_WEEKLY_ROWS_PER_SLATE
        for indices in weekly_indices_by_slate
    ):
        _fail("logical grade weekly contrast slate partition differs")

    # Construct and canonicalize every component before the first write.  This
    # makes schema/size failures pre-publication and bounds the V1 peak openly.
    slate_components: list[tuple[dict[str, object], bytes]] = []
    for source_ordinal, indices in enumerate(weekly_indices_by_slate):
        shard = _build_slate_shard(
            realized_grade=retained_grade,
            source_ordinal=source_ordinal,
            weekly_indices=indices,
        )
        _validate_slate_shard(
            shard,
            source_ordinal=source_ordinal,
            realized_grade_sha256=str(retained_grade["realized_grade_sha256"]),
            catalog_sha256=catalog_sha,
            outcome_snapshot_sha256=outcome_sha,
        )
        slate_components.append((shard, canonical_json_bytes(shard)))
    summary = _build_summary_shard(realized_grade=retained_grade)
    _validate_summary_shard(
        summary,
        realized_grade_sha256=str(retained_grade["realized_grade_sha256"]),
        catalog_sha256=catalog_sha,
        outcome_snapshot_sha256=outcome_sha,
    )
    summary_raw = canonical_json_bytes(summary)

    descriptors: list[dict[str, object]] = []
    shard_identities: list[dict[str, object]] = []
    created_shards = 0
    for source_ordinal, (shard, raw) in enumerate(slate_components):
        identity, created = _publish_exact(
            uri=slate_shard_uri(prefix, source_ordinal),
            value=shard,
            raw=raw,
            read_exact=read_exact,
            publish_create_once=publish_create_once,
            label=f"Core v1 realized grade shard[{source_ordinal}]",
        )
        created_shards += int(created)
        shard_identities.append(identity)
        descriptors.append(_slate_descriptor(
            shard=shard, shard_identity=identity
        ))
    retained_summary_identity, summary_created = _publish_exact(
        uri=summary_uri(prefix),
        value=summary,
        raw=summary_raw,
        read_exact=read_exact,
        publish_create_once=publish_create_once,
        label="Core v1 realized grade contrast-summary shard",
    )
    retained_summary_descriptor = _summary_descriptor(
        summary=summary, summary_identity=retained_summary_identity
    )
    component_sizes = [
        int(identity["bytes"]) for identity in shard_identities
    ] + [int(retained_summary_identity["bytes"])]
    root_body = {
        "schema_version": SHARDED_GRADE_ROOT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "create_once": True,
        "realized_grade_sha256": retained_grade["realized_grade_sha256"],
        "catalog_sha256": catalog_sha,
        "catalog_identity": catalog_identity,
        "outcome_snapshot_sha256": outcome_sha,
        "outcome_snapshot_identity": outcome_snapshot_identity,
        "player_source_identity": player_source_identity,
        "grade_header": grade_header,
        "grade_header_sha256": canonical_sha256(grade_header),
        "slate_shard_uri_law": (
            "{output_prefix}slate-grades/{source_ordinal:02d}.json"
        ),
        "slate_shard_count": len(descriptors),
        "slate_shard_descriptors": descriptors,
        "slate_shard_descriptors_sha256": canonical_sha256(descriptors),
        "summary_uri_law": "{output_prefix}contrast-summaries.json",
        "summary_descriptor": retained_summary_descriptor,
        "materialization_metrics": {
            "logical_grade_canonical_bytes": len(logical_raw),
            "logical_grade_payload_ceiling_bytes": ceiling,
            "slate_shard_count": len(descriptors),
            "weekly_contrast_row_count": len(
                retained_grade["weekly_contrasts"]
            ),
            "contrast_summary_count": len(
                retained_grade["contrast_summaries"]
            ),
            "slate_shard_payload_bytes": sum(
                int(identity["bytes"]) for identity in shard_identities
            ),
            "summary_shard_payload_bytes": retained_summary_identity["bytes"],
            "largest_component_payload_bytes": max(component_sizes),
            "logical_grade_assembled_in_memory": True,
            "payload_ceiling_passed": True,
        },
        "complete": True,
        **_common_authority_body(),
    }
    root = validate_sharded_core_v1_realized_grade_root(
        _self_hash(root_body, "sharded_grade_root_sha256")
    )
    root_raw = canonical_json_bytes(root)
    retained_root_identity, root_created = _publish_exact(
        uri=root_uri(prefix),
        value=root,
        raw=root_raw,
        read_exact=read_exact,
        publish_create_once=publish_create_once,
        label="sharded Core v1 realized-grade root",
    )
    reopened_grade = reopen_sharded_core_v1_realized_grade(
        root_identity=retained_root_identity,
        read_exact=read_exact,
    )
    if canonical_json_bytes(reopened_grade) != logical_raw:
        _fail("published sharded Core v1 realized grade differs after exact reopen")
    return PublishedShardedCoreV1Grade(
        root=root,
        root_identity=retained_root_identity,
        slate_shard_identities=tuple(shard_identities),
        summary_identity=retained_summary_identity,
        created_slate_shard_count=created_shards,
        recovered_slate_shard_count=len(shard_identities) - created_shards,
        summary_created=summary_created,
        root_created=root_created,
    )


def reopen_sharded_core_v1_realized_grade(
    *, root_identity: Mapping[str, object], read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-reopen all components and reconstruct the authoritative grade."""
    retained_root_identity, root_raw_value, root_raw = _read_json_exact(
        root_identity,
        read_exact=read_exact,
        label="sharded Core v1 realized-grade root",
    )
    root = validate_sharded_core_v1_realized_grade_root(root_raw_value)
    if len(root_raw) != retained_root_identity["bytes"]:
        raise AssertionError("exact root read lost its byte census")
    retained_root_uri = str(retained_root_identity["uri"])
    if not retained_root_uri.endswith(ROOT_FILENAME):
        _fail("sharded Core v1 realized-grade root URI differs")
    prefix = retained_root_uri[:-len(ROOT_FILENAME)]

    summary_descriptor = _mapping(
        root["summary_descriptor"], label="grade summary descriptor"
    )
    summary_identity = _identity(
        summary_descriptor["summary_identity"], label="grade summary identity"
    )
    if summary_identity["uri"] != summary_uri(prefix):
        _fail("Core v1 realized-grade summary URI differs from its law")
    reopened_summary_identity, summary_raw_value, _ = _read_json_exact(
        summary_identity,
        read_exact=read_exact,
        label="Core v1 realized-grade contrast-summary shard",
    )
    summary = _validate_summary_shard(
        summary_raw_value,
        realized_grade_sha256=str(root["realized_grade_sha256"]),
        catalog_sha256=str(root["catalog_sha256"]),
        outcome_snapshot_sha256=str(root["outcome_snapshot_sha256"]),
    )
    if summary_descriptor != _summary_descriptor(
        summary=summary, summary_identity=reopened_summary_identity
    ):
        _fail("reopened contrast-summary shard differs from its descriptor")

    slate_grades: list[dict[str, object]] = []
    weekly: list[dict[str, object] | None] = [None] * EXPECTED_WEEKLY_ROW_COUNT
    for source_ordinal, raw_descriptor in enumerate(
        root["slate_shard_descriptors"]
    ):
        descriptor = _mapping(
            raw_descriptor, label=f"grade shard descriptor[{source_ordinal}]"
        )
        identity = _identity(
            descriptor["shard_identity"], label="grade shard identity"
        )
        if identity["uri"] != slate_shard_uri(prefix, source_ordinal):
            _fail("Core v1 realized-grade shard URI differs from its law")
        reopened_identity, shard_raw_value, _ = _read_json_exact(
            identity,
            read_exact=read_exact,
            label=f"Core v1 realized-grade shard[{source_ordinal}]",
        )
        shard = _validate_slate_shard(
            shard_raw_value,
            source_ordinal=source_ordinal,
            realized_grade_sha256=str(root["realized_grade_sha256"]),
            catalog_sha256=str(root["catalog_sha256"]),
            outcome_snapshot_sha256=str(root["outcome_snapshot_sha256"]),
        )
        if descriptor != _slate_descriptor(
            shard=shard, shard_identity=reopened_identity
        ):
            _fail("reopened realized-grade shard differs from its descriptor")
        slate_grades.append(dict(shard["slate_grade"]))
        for index, row in zip(
            shard["weekly_contrast_indices"],
            shard["weekly_contrasts"],
            strict=True,
        ):
            if weekly[index] is not None:
                _fail("sharded weekly contrast index repeats")
            weekly[index] = dict(row)
    if any(row is None for row in weekly):
        _fail("sharded weekly contrast index census is incomplete")

    logical = {
        **dict(root["grade_header"]),
        "slate_grades": slate_grades,
        "weekly_contrasts": [row for row in weekly if row is not None],
        "contrast_summaries": [
            dict(row) for row in summary["contrast_summaries"]
        ],
        "realized_grade_sha256": root["realized_grade_sha256"],
    }
    try:
        retained_grade = grading.validate_core_v1_realized_grade(logical)
    except grading.CorpusCatalogRealizedGradingError as exc:
        raise CorpusCoreV1GradePublisherError(str(exc)) from exc
    _complete_grade_census(retained_grade)
    metrics = _mapping(
        root["materialization_metrics"], label="grade materialization metrics"
    )
    if (
        len(canonical_json_bytes(retained_grade))
        != metrics["logical_grade_canonical_bytes"]
        or retained_grade["realized_grade_sha256"]
        != root["realized_grade_sha256"]
    ):
        _fail("reopened logical Core v1 realized-grade metrics differ")
    return retained_grade


def grade_and_publish_sharded_core_v1(
    *,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    outcome_snapshot: Mapping[str, object],
    outcome_snapshot_identity: Mapping[str, object],
    player_source: Mapping[str, object],
    player_source_identity: Mapping[str, object],
    outcome_keys: Sequence[outcome_contract.CoreOutcomeKey],
    output_prefix: str,
    max_logical_grade_bytes: int,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    contest_outcomes: object | None = None,
) -> PublishedShardedCoreV1Grade:
    """Run the one established score-once grader and shard its exact result."""
    try:
        realized_grade = grading.grade_core_v1_catalog(
            catalog=catalog,
            catalog_identity=catalog_identity,
            outcome_snapshot=outcome_snapshot,
            outcome_snapshot_identity=outcome_snapshot_identity,
            player_source=player_source,
            player_source_identity=player_source_identity,
            outcome_keys=outcome_keys,
            contest_outcomes=contest_outcomes,
        )
    except grading.CorpusCatalogRealizedGradingError as exc:
        raise CorpusCoreV1GradePublisherError(str(exc)) from exc
    _validate_authoritative_grade_inputs(
        grade=realized_grade,
        catalog=catalog,
        catalog_identity=catalog_identity,
        outcome_snapshot=outcome_snapshot,
        outcome_snapshot_identity=outcome_snapshot_identity,
        player_source=player_source,
        player_source_identity=player_source_identity,
    )
    return _publish_validated_sharded_core_v1_realized_grade(
        realized_grade=realized_grade,
        output_prefix=output_prefix,
        max_logical_grade_bytes=max_logical_grade_bytes,
        read_exact=read_exact,
        publish_create_once=publish_create_once,
    )


__all__ = [
    "CONTRAST_SUMMARY_SHARD_SCHEMA",
    "CorpusCoreV1GradePublisherError",
    "CreateOncePublication",
    "PublishedShardedCoreV1Grade",
    "SHARDED_GRADE_ROOT_SCHEMA",
    "SLATE_GRADE_SHARD_SCHEMA",
    "grade_and_publish_sharded_core_v1",
    "reopen_sharded_core_v1_realized_grade",
    "root_uri",
    "slate_shard_uri",
    "summary_uri",
    "validate_sharded_core_v1_realized_grade_root",
]
