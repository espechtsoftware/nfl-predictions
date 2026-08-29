"""Terminal and generic-grader seam for hard-230 selector confirmation.

The score-free science lives in
``corpus_r6_hard230_selector_confirmation_v1``.  This module validates its
persisted surface, binds it to the already sealed hard-230 selector bridge,
and builds one create-last 54-slate terminal.  It performs no I/O and has no
outcome reader.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as bridge
from nfl_dfs.research import (
    corpus_r6_hard230_selector_confirmation_v1 as confirmation,
)
from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as grader
from nfl_dfs.research import (
    corpus_r6_selector_diversity_challengers_v1 as diversity,
)


TERMINAL_SCHEMA: Final = "corpus-r6-hard230-selector-confirmation-terminal/v1"
TERMINAL_ADAPTER_ID: Final = confirmation.ADAPTER_ID
OUTPUT_SUFFIX: Final = "selector-confirmation-v1/"

_RESULT_FIELDS: Final = frozenset(
    {
        "schema_version",
        "adapter_id",
        "source_ordinal",
        "slate_id",
        "bridge_slate_sha256",
        "generator_origin_block",
        "selector_fit_blocks",
        "selector_fit_law",
        "population_count",
        "selector_count_per_population",
        "entry_budgets",
        "book_count",
        "diversity_bindings",
        "diversity_bindings_sha256",
        "books",
        "books_sha256",
        "corpus_regeneration_performed",
        "uses_realized_outcomes",
        "heldout_scores_used",
        "confirmation_sha256",
    }
)
_BOOK_FIELDS: Final = frozenset(
    {
        "coordinate",
        "coordinate_sha256",
        "selected_lineup_ids",
        "selected_lineup_ids_sha256",
        "book_sha256",
    }
)
_COORDINATE_FIELDS: Final = frozenset(
    {
        "adapter_id",
        "metric_kind",
        "population_role",
        "population_id",
        "selector_family",
        "selector_id",
        "entry_budget",
    }
)
_DIVERSITY_BINDING_FIELDS: Final = frozenset(
    {
        "population_role",
        "population_id",
        "diversity_contract_sha256",
        "diversity_selector_results_sha256",
        "training_score_matrix_sha256",
    }
)
_TERMINAL_FIELDS: Final = frozenset(
    {
        "schema_version",
        "adapter_id",
        "bridge_terminal_identity",
        "bridge_terminal_sha256",
        "task0_smoke_receipt_identity",
        "task0_smoke_receipt_sha256",
        "terminal_build_receipt_identity",
        "terminal_build_receipt_sha256",
        "source_commit_sha",
        "immutable_image_digest",
        "later_source_identity",
        "output_prefix",
        "terminal_uri",
        "source_slate_count",
        "slate_results",
        "slate_result_descriptors",
        "slate_result_descriptors_sha256",
        "all_confirmation_slates_exact_replayed_before_terminal",
        "generic_normalized_terminal_validated",
        "complete",
        "outcome_columns_read",
        "corpus_regeneration_performed",
        "uses_realized_outcomes",
        "heldout_scores_used",
        "terminal_sha256",
    }
)


class CorpusR6Hard230SelectorConfirmationExecutionV1Error(ValueError):
    """The hard-230 confirmation execution surface differs."""


def _fail(message: str) -> None:
    raise CorpusR6Hard230SelectorConfirmationExecutionV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return grader.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6Hard230SelectorConfirmationExecutionV1Error(
            "value is not finite canonical JSON"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(value)
    if field in result:
        _fail(f"{field} already exists")
    result[field] = _hash(result)
    return result


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return grader._identity(value, label=label)
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6Hard230SelectorConfirmationExecutionV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def confirmation_output_prefix_v1(bridge_terminal: Mapping[str, object]) -> str:
    source_prefix = bridge_terminal.get("output_prefix")
    if (
        type(source_prefix) is not str
        or not source_prefix.startswith("gs://")
        or not source_prefix.endswith("/selector-bridge/")
        or "//" in source_prefix[5:]
    ):
        _fail("hard230 bridge output prefix differs")
    return f"{source_prefix}{OUTPUT_SUFFIX}"


def _expected_selector_coordinates() -> list[tuple[str, str, int]]:
    selectors = [
        ("native-grouped-rank150", rank_id)
        for _grouped_id, rank_id in bridge.NATIVE_SELECTORS
    ] + [
        ("effective-independent-shots-dpp", bridge.DPP_SELECTOR_ID),
    ] + [
        ("tail-ladder-diversity-challengers", selector_id)
        for selector_id in confirmation.DIVERSITY_IDS
    ]
    return [
        (family, selector_id, budget)
        for family, selector_id in selectors
        for budget in confirmation.ENTRY_BUDGETS
    ]


def validate_confirmation_slate_structure_v1(
    value: object,
    *,
    bridge_slate: object,
) -> dict[str, object]:
    """Validate one replay-produced confirmation without opening outcomes."""
    result = _mapping(value, label="hard230 confirmation slate")
    source = _mapping(bridge_slate, label="hard230 bridge slate")
    if (
        set(result) != _RESULT_FIELDS
        or result.get("confirmation_sha256")
        != _hash(
            {
                key: item
                for key, item in result.items()
                if key != "confirmation_sha256"
            }
        )
        or result.get("schema_version") != confirmation.SCHEMA_VERSION
        or result.get("adapter_id") != confirmation.ADAPTER_ID
        or result.get("source_ordinal") != source.get("source_ordinal")
        or result.get("slate_id") != source.get("slate_id")
        or result.get("bridge_slate_sha256") != source.get("slate_result_sha256")
        or result.get("generator_origin_block") != bridge.GENERATOR_ORIGIN_BLOCK
        or result.get("selector_fit_blocks") != list(bridge.SELECTOR_BLOCKS)
        or result.get("selector_fit_law")
        != "fixed-r1-through-r4-out-of-r0-origin-simulated-bank"
        or result.get("population_count") != confirmation.POPULATION_COUNT
        or result.get("selector_count_per_population")
        != confirmation.SELECTOR_COUNT
        or result.get("entry_budgets") != list(confirmation.ENTRY_BUDGETS)
        or result.get("book_count") != confirmation.BOOK_COUNT
        or result.get("corpus_regeneration_performed") is not False
        or result.get("uses_realized_outcomes") is not False
        or result.get("heldout_scores_used") is not False
    ):
        _fail("hard230 confirmation fixed slate law differs")

    source_populations = {
        str(row["population_role"]): _mapping(
            row, label="hard230 bridge population"
        )
        for row in _sequence(
            source.get("population_results"), label="hard230 bridge populations"
        )
    }
    expected_roles = [spec[0] for spec in bridge.POPULATION_SPECS]
    if list(source_populations) != expected_roles:
        _fail("hard230 confirmation source population order differs")

    bindings = [
        _mapping(row, label="hard230 confirmation diversity binding")
        for row in _sequence(
            result.get("diversity_bindings"),
            label="hard230 confirmation diversity bindings",
        )
    ]
    diversity_contract_sha = diversity.diversity_challenger_contract_v1()[
        "contract_sha256"
    ]
    if (
        result.get("diversity_bindings_sha256") != _hash(bindings)
        or len(bindings) != confirmation.POPULATION_COUNT
    ):
        _fail("hard230 confirmation diversity binding collection differs")
    population_ids_by_role = {spec[0]: spec[1] for spec in bridge.POPULATION_SPECS}
    for binding, role in zip(bindings, expected_roles, strict=True):
        source_population = source_populations[role]
        if (
            set(binding) != _DIVERSITY_BINDING_FIELDS
            or binding.get("population_role") != role
            or binding.get("population_id") != population_ids_by_role[role]
            or binding.get("diversity_contract_sha256")
            != diversity_contract_sha
            or binding.get("training_score_matrix_sha256")
            != source_population.get("selector_fit_score_matrix_sha256")
        ):
            _fail("hard230 confirmation diversity binding differs")
        _digest(
            binding.get("diversity_selector_results_sha256"),
            label="hard230 confirmation diversity selector result",
        )

    books = [
        _mapping(row, label="hard230 confirmation book")
        for row in _sequence(result.get("books"), label="hard230 confirmation books")
    ]
    if result.get("books_sha256") != _hash(books) or len(books) != confirmation.BOOK_COUNT:
        _fail("hard230 confirmation book collection differs")
    expected_selectors = _expected_selector_coordinates()
    expected_coordinates = [
        (role, population_ids_by_role[role], family, selector_id, budget)
        for role in expected_roles
        for family, selector_id, budget in expected_selectors
    ]
    retained_coordinates: list[tuple[str, str, str, str, int]] = []
    for book in books:
        coordinate = _mapping(
            book.get("coordinate"), label="hard230 confirmation coordinate"
        )
        selected = [
            str(lineup_id)
            for lineup_id in _sequence(
                book.get("selected_lineup_ids"),
                label="hard230 confirmation selected lineup IDs",
            )
        ]
        role = str(coordinate.get("population_role"))
        population_id = str(coordinate.get("population_id"))
        budget = coordinate.get("entry_budget")
        source_population = source_populations.get(role)
        sampled = (
            set(str(value) for value in source_population["sampled_lineup_ids"])
            if source_population is not None
            else set()
        )
        retained_coordinates.append(
            (
                role,
                population_id,
                str(coordinate.get("selector_family")),
                str(coordinate.get("selector_id")),
                int(budget) if type(budget) is int else -1,
            )
        )
        if (
            set(book) != _BOOK_FIELDS
            or set(coordinate) != _COORDINATE_FIELDS
            or coordinate.get("adapter_id") != confirmation.ADAPTER_ID
            or coordinate.get("metric_kind") != "selected-book"
            or population_id != population_ids_by_role.get(role)
            or type(budget) is not int
            or len(selected) != budget
            or len(set(selected)) != budget
            or not set(selected) <= sampled
            or book.get("coordinate_sha256") != _hash(coordinate)
            or book.get("selected_lineup_ids_sha256") != _hash(selected)
            or book.get("book_sha256")
            != _hash(
                {key: item for key, item in book.items() if key != "book_sha256"}
            )
        ):
            _fail("hard230 confirmation selected book differs")
    if retained_coordinates != expected_coordinates:
        _fail("hard230 confirmation exact 42-book lattice differs")
    return result


def normalized_confirmation_slate_v1(
    value: object,
    *,
    bridge_slate: object,
) -> dict[str, object]:
    """Project one validated confirmation onto the public grader boundary."""
    result = validate_confirmation_slate_structure_v1(
        value, bridge_slate=bridge_slate
    )
    source = bridge.normalized_slate_for_grader_v1(bridge_slate)
    books = [
        {
            "coordinate": row["coordinate"],
            "coordinate_sha256": row["coordinate_sha256"],
            "population_id": row["coordinate"]["population_id"],
            "selected_lineup_ids": row["selected_lineup_ids"],
        }
        for row in result["books"]
    ]
    return {
        "source_ordinal": source["source_ordinal"],
        "slate_id": source["slate_id"],
        "populations": source["populations"],
        "books": books,
        "later_source_identity": source["later_source_identity"],
    }


def validate_terminal_envelope_v1(value: object) -> dict[str, object]:
    """Validate the terminal itself before following its source identity."""
    terminal = _mapping(value, label="hard230 confirmation terminal")
    if (
        set(terminal) != _TERMINAL_FIELDS
        or terminal.get("terminal_sha256")
        != _hash(
            {
                key: item
                for key, item in terminal.items()
                if key != "terminal_sha256"
            }
        )
        or terminal.get("schema_version") != TERMINAL_SCHEMA
        or terminal.get("adapter_id") != TERMINAL_ADAPTER_ID
        or terminal.get("source_slate_count") != grader.SOURCE_SLATE_COUNT
        or terminal.get("complete") is not True
        or terminal.get("all_confirmation_slates_exact_replayed_before_terminal")
        is not True
        or terminal.get("generic_normalized_terminal_validated") is not True
        or terminal.get("outcome_columns_read") != []
        or terminal.get("corpus_regeneration_performed") is not False
        or terminal.get("uses_realized_outcomes") is not False
        or terminal.get("heldout_scores_used") is not False
    ):
        _fail("hard230 confirmation terminal fixed law differs")
    _identity(
        terminal.get("bridge_terminal_identity"),
        label="hard230 confirmation bridge terminal",
    )
    _identity(
        terminal.get("later_source_identity"),
        label="hard230 confirmation later source",
    )
    _identity(
        terminal.get("task0_smoke_receipt_identity"),
        label="hard230 confirmation task0 smoke receipt",
    )
    _identity(
        terminal.get("terminal_build_receipt_identity"),
        label="hard230 confirmation terminal build receipt",
    )
    _digest(
        terminal.get("bridge_terminal_sha256"),
        label="hard230 confirmation bridge terminal",
    )
    _digest(
        terminal.get("task0_smoke_receipt_sha256"),
        label="hard230 confirmation task0 smoke receipt",
    )
    _digest(
        terminal.get("terminal_build_receipt_sha256"),
        label="hard230 confirmation terminal build receipt",
    )
    source_commit = terminal.get("source_commit_sha")
    image_digest = terminal.get("immutable_image_digest")
    if (
        type(source_commit) is not str
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
        or type(image_digest) is not str
        or not image_digest.startswith("sha256:")
        or len(image_digest) != 71
        or any(character not in "0123456789abcdef" for character in image_digest[7:])
    ):
        _fail("hard230 confirmation code/image authority differs")
    output_prefix = terminal.get("output_prefix")
    if (
        type(output_prefix) is not str
        or not output_prefix.startswith("gs://")
        or not output_prefix.endswith(f"/{OUTPUT_SUFFIX}")
        or "//" in output_prefix[5:]
        or terminal.get("terminal_uri") != f"{output_prefix}full-54/terminal.json"
    ):
        _fail("hard230 confirmation terminal topology differs")
    results = _sequence(
        terminal.get("slate_results"), label="hard230 confirmation terminal slates"
    )
    descriptors = _sequence(
        terminal.get("slate_result_descriptors"),
        label="hard230 confirmation terminal descriptors",
    )
    if (
        len(results) != grader.SOURCE_SLATE_COUNT
        or len(descriptors) != grader.SOURCE_SLATE_COUNT
        or terminal.get("slate_result_descriptors_sha256") != _hash(descriptors)
        or [row.get("source_ordinal") for row in results]
        != list(range(grader.SOURCE_SLATE_COUNT))
        or len({str(row.get("slate_id")) for row in results})
        != grader.SOURCE_SLATE_COUNT
    ):
        _fail("hard230 confirmation terminal 54-slate coverage differs")
    for ordinal, (raw_result, raw_descriptor) in enumerate(
        zip(results, descriptors, strict=True)
    ):
        result = _mapping(raw_result, label=f"hard230 confirmation result[{ordinal}]")
        descriptor = _mapping(
            raw_descriptor, label=f"hard230 confirmation descriptor[{ordinal}]"
        )
        if descriptor != {
            "source_ordinal": ordinal,
            "slate_id": result.get("slate_id"),
            "bridge_slate_sha256": result.get("bridge_slate_sha256"),
            "confirmation_sha256": result.get("confirmation_sha256"),
        }:
            _fail("hard230 confirmation terminal descriptor differs")
    return terminal


def build_confirmation_terminal_v1(
    *,
    bridge_terminal: object,
    bridge_terminal_identity: object,
    task0_smoke_receipt_identity: object,
    task0_smoke_receipt_sha256: str,
    terminal_build_receipt_identity: object,
    terminal_build_receipt_sha256: str,
    source_commit_sha: str,
    immutable_image_digest: str,
    output_prefix: str,
    slate_results: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build one create-last terminal after all 54 score-free replays."""
    if (
        type(source_commit_sha) is not str
        or len(source_commit_sha) != 40
        or any(
            character not in "0123456789abcdef" for character in source_commit_sha
        )
        or type(immutable_image_digest) is not str
        or not immutable_image_digest.startswith("sha256:")
        or len(immutable_image_digest) != 71
        or any(
            character not in "0123456789abcdef"
            for character in immutable_image_digest[7:]
        )
    ):
        _fail("hard230 confirmation code/image authority differs")
    source = bridge.validate_hard230_selector_terminal_v1(bridge_terminal)
    source_identity = _identity(
        bridge_terminal_identity, label="hard230 confirmation bridge terminal"
    )
    smoke_identity = _identity(
        task0_smoke_receipt_identity,
        label="hard230 confirmation task0 smoke receipt",
    )
    build_identity = _identity(
        terminal_build_receipt_identity,
        label="hard230 confirmation terminal build receipt",
    )
    _digest(
        task0_smoke_receipt_sha256,
        label="hard230 confirmation task0 smoke receipt",
    )
    _digest(
        terminal_build_receipt_sha256,
        label="hard230 confirmation terminal build receipt",
    )
    if (
        source_identity["uri"] != source["terminal_uri"]
        or output_prefix != confirmation_output_prefix_v1(source)
    ):
        _fail("hard230 confirmation source identity or output prefix differs")
    raw_results = list(slate_results)
    if len(raw_results) != grader.SOURCE_SLATE_COUNT:
        _fail("hard230 confirmation terminal requires exactly 54 slates")
    results = [
        validate_confirmation_slate_structure_v1(
            row, bridge_slate=source["slate_results"][ordinal]
        )
        for ordinal, row in enumerate(raw_results)
    ]
    normalized = tuple(
        normalized_confirmation_slate_v1(
            row, bridge_slate=source["slate_results"][ordinal]
        )
        for ordinal, row in enumerate(results)
    )
    try:
        grader.validate_external_normalized_terminal_v1(
            adapter_id=TERMINAL_ADAPTER_ID, slates=normalized
        )
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6Hard230SelectorConfirmationExecutionV1Error(str(exc)) from exc
    descriptors = [
        {
            "source_ordinal": ordinal,
            "slate_id": row["slate_id"],
            "bridge_slate_sha256": row["bridge_slate_sha256"],
            "confirmation_sha256": row["confirmation_sha256"],
        }
        for ordinal, row in enumerate(results)
    ]
    body = {
        "schema_version": TERMINAL_SCHEMA,
        "adapter_id": TERMINAL_ADAPTER_ID,
        "bridge_terminal_identity": source_identity,
        "bridge_terminal_sha256": source["terminal_sha256"],
        "task0_smoke_receipt_identity": smoke_identity,
        "task0_smoke_receipt_sha256": task0_smoke_receipt_sha256,
        "terminal_build_receipt_identity": build_identity,
        "terminal_build_receipt_sha256": terminal_build_receipt_sha256,
        "source_commit_sha": source_commit_sha,
        "immutable_image_digest": immutable_image_digest,
        "later_source_identity": source["later_source_identity"],
        "output_prefix": output_prefix,
        "terminal_uri": f"{output_prefix}full-54/terminal.json",
        "source_slate_count": grader.SOURCE_SLATE_COUNT,
        "slate_results": results,
        "slate_result_descriptors": descriptors,
        "slate_result_descriptors_sha256": _hash(descriptors),
        "all_confirmation_slates_exact_replayed_before_terminal": True,
        "generic_normalized_terminal_validated": True,
        "complete": True,
        "outcome_columns_read": [],
        "corpus_regeneration_performed": False,
        "uses_realized_outcomes": False,
        "heldout_scores_used": False,
    }
    return _with_hash(body, field="terminal_sha256")


def validate_confirmation_terminal_v1(
    value: object,
    *,
    bridge_terminal: object,
) -> dict[str, object]:
    terminal = validate_terminal_envelope_v1(value)
    expected = build_confirmation_terminal_v1(
        bridge_terminal=bridge_terminal,
        bridge_terminal_identity=terminal["bridge_terminal_identity"],
        task0_smoke_receipt_identity=terminal["task0_smoke_receipt_identity"],
        task0_smoke_receipt_sha256=str(terminal["task0_smoke_receipt_sha256"]),
        terminal_build_receipt_identity=terminal["terminal_build_receipt_identity"],
        terminal_build_receipt_sha256=str(
            terminal["terminal_build_receipt_sha256"]
        ),
        source_commit_sha=str(terminal["source_commit_sha"]),
        immutable_image_digest=str(terminal["immutable_image_digest"]),
        output_prefix=str(terminal["output_prefix"]),
        slate_results=terminal["slate_results"],
    )
    if _canonical(terminal) != _canonical(expected):
        _fail("hard230 confirmation terminal differs from exact reconstruction")
    return expected


def normalized_confirmation_terminal_v1(
    value: object,
    *,
    bridge_terminal: object,
) -> tuple[dict[str, object], ...]:
    terminal = validate_confirmation_terminal_v1(
        value, bridge_terminal=bridge_terminal
    )
    source = bridge.validate_hard230_selector_terminal_v1(bridge_terminal)
    slates = tuple(
        normalized_confirmation_slate_v1(
            row, bridge_slate=source["slate_results"][ordinal]
        )
        for ordinal, row in enumerate(terminal["slate_results"])
    )
    try:
        return grader.validate_external_normalized_terminal_v1(
            adapter_id=TERMINAL_ADAPTER_ID, slates=slates
        )
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6Hard230SelectorConfirmationExecutionV1Error(str(exc)) from exc


__all__ = [
    "TERMINAL_ADAPTER_ID",
    "TERMINAL_SCHEMA",
    "build_confirmation_terminal_v1",
    "confirmation_output_prefix_v1",
    "normalized_confirmation_slate_v1",
    "normalized_confirmation_terminal_v1",
    "validate_confirmation_slate_structure_v1",
    "validate_confirmation_terminal_v1",
    "validate_terminal_envelope_v1",
]
