"""Read-only, fail-closed scorecard over completed R6 realized grades.

The scorecard deliberately has no storage or outcome-source client.  It reads
only local JSON artifacts that have already been downloaded.  New score-sprint
grades share the aggregate-cell contract from the novel-roster grader; the two
older comparison surfaces are accepted only at their exact frozen file hashes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from hashlib import sha256
import json
from pathlib import Path
from typing import Final


SCORECARD_SCHEMA: Final = "corpus-r6-score-sprint-scorecard/v1"
NOVEL_GRADE_SCHEMA: Final = "corpus-r6-novel-roster-realized-grade/v1"
L2B_PROVISIONAL_GRADE_SCHEMA: Final = (
    "corpus-r6-l2b-selector-provider-realized-grade-provisional/v1"
)
HARD230_GRADE_SCHEMA: Final = (
    "corpus-r6-hard230-selector-bridge-realized-grade/v1"
)
AGGREGATE_CELL_SCHEMA: Final = (
    "corpus-r6-novel-roster-realized-aggregate-cell/v1"
)
FULL_UNION_REPORT_SCHEMA: Final = "corpus-r6-full-union-score-report/v1"

SOURCE_SLATE_COUNT: Final = 54
MICRO_DK_PER_POINT: Final = 1_000_000
REQUESTED_THRESHOLDS_DK: Final = (194, 200, 220, 230)
STORED_NOVEL_THRESHOLDS_DK: Final = (200, 210, 220, 230)
EXPECTED_SLATE_IDS: Final = tuple(
    f"{season}-w{week:02d}"
    for season in (2023, 2024, 2025)
    for week in range(1, 19)
)
LOGICAL_SCOPE_ID: Final = "r6-sunday-main-2023-2025-w01-w18-54"

FROZEN_FULL_UNION_FILE_SHA256: Final = (
    "b0ccc59416b61c46b586a4b477639d95664870db1d2c466c390b88c1af62395d"
)
FROZEN_A7_FILE_SHA256: Final = (
    "e29c31df96f8d207361504d5db5615e3120ede77d783a0725a4721621bf74b15"
)
FROZEN_A7_VERSION: Final = "a7-select-ladder-phase-s-incumbent-v2"

WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
POPULATION_PROFILES: Final = (
    "F7-qb-and-bringback-relaxed", "F8-game-cap-3", "F9-single-partner",
)
L2B_FRACTIONS: Final = ("l2b-quarter-world-mixture", "l2b-native")
HARD_POPULATIONS: Final = (
    ("score-blind-control", "P0-sized-shared-stream-score-blind-prefix-v1"),
    ("hard230-challenger", "G-hard230-generate-replenish-successor-v1"),
)
HARD_SELECTORS: Final = (
    ("native-grouped-rank150", "native-convex-excess-expected-max-rank150-v1"),
    ("native-grouped-rank150", "native-correlation-aware-expected-max-rank150-v1"),
    ("native-grouped-rank150", "native-support-switched-scenario-ticket-rank150-v1"),
    ("effective-independent-shots-dpp", "effective-independent-tail-shots-dpp-ge-230-v1"),
)
_UPSTREAM_PRESET_SELECTOR_IDS: Final = (
    "convex-excess-expected-max-ge-200-v1",
    "correlation-aware-expected-max-ge-230-v1",
    "support-switched-event-component-tickets-ge-230-v1",
)
GENERIC_SELECTOR_IDS: Final = {
    "grouped-native-rank80": (
        *_UPSTREAM_PRESET_SELECTOR_IDS,
    ),
    "exact-rank150-continuation": (
        *_UPSTREAM_PRESET_SELECTOR_IDS,
    ),
    "effective-independent-tail-shots": (
        "effective-independent-tail-shots-dpp-ge-230-v1",
    ),
    "tail-ladder-diversity-challengers": (
        "tail-ladder-roster-overlap-cap-4-v1",
        "tail-ladder-roster-overlap-cap-5-v1",
        "tail-ladder-evil-twin-strict-200-v1",
    ),
}
# The exact L2b result preserves ordinals from the complete challenger
# registry.  Cap-3 remains the unregistered ordinal-0 follow-up, so the three
# active books retain source ordinals 1/2/3 rather than being renumbered.
GENERIC_SELECTOR_ORDINALS: Final = {
    family: tuple(range(len(selector_ids)))
    for family, selector_ids in GENERIC_SELECTOR_IDS.items()
    if family != "tail-ladder-diversity-challengers"
} | {"tail-ladder-diversity-challengers": (1, 2, 3)}
_NOVEL_ROOT_FIELDS: Final = frozenset({
    "schema_version", "adapter_id", "terminal_root_identity",
    "terminal_root_sha256", "task_manifest_identity", "task_manifest_sha256",
    "outcome_snapshot_identity", "outcome_snapshot_sha256",
    "later_source_freeze_identity", "score_unit", "micro_dk_per_point",
    "threshold_registry", "source_slate_count", "slate_grade_count",
    "slate_grades", "slate_grades_sha256", "aggregate_cell_count",
    "aggregate_cells", "aggregate_cells_sha256", "roster_sum_operation_count",
    "every_distinct_roster_scored_once_per_slate",
    "terminal_before_first_outcome_read", "uses_realized_outcomes",
    "historical_retune_licensed", "historical_retry_licensed",
    "decision_authority", "complete", "realized_grade_sha256",
})
_PROVISIONAL_AUTHORITY_FIELDS: Final = frozenset({
    "authority_tier", "provider_task_results_structurally_validated",
    "central_exact_selector_replay_completed",
    "asynchronous_exact_replay_required",
    "coherent_substitution_excluded_by_hashes_alone",
    "confirmatory_authority", "promotion_authority",
    "production_change_licensed",
})
_HARD_ROOT_FIELDS: Final = frozenset({
    "schema_version", "adapter_id", "terminal_identity", "terminal_sha256",
    "outcome_snapshot_identity", "outcome_snapshot_sha256",
    "later_source_identity", "source_slate_count", "slate_grades",
    "slate_grades_sha256", "aggregate_cells", "aggregate_cells_sha256",
    "all_score_free_predecessors_replayed_before_outcome_open",
    "outcome_source_and_slate_identity_bound", "complete", "grade_sha256",
})

_CELL_FIELDS: Final = frozenset({
    "schema_version",
    "coordinate",
    "coordinate_sha256",
    "source_slate_count",
    "slate_rows",
    "slate_rows_sha256",
    "mean_weekly_maximum_micro",
    "mean_population_ceiling_micro",
    "thresholds",
    "selection_conversion_available",
    "population_ceiling_conversion_count",
    "population_ceiling_conversion_fraction",
    "mean_population_ceiling_regret_micro",
    "complete",
    "aggregate_cell_sha256",
})
_SLATE_ROW_FIELDS: Final = frozenset({
    "source_ordinal",
    "slate_id",
    "entry_budget",
    "population_lineup_count",
    "selected_lineup_count",
    "population_ceiling_micro",
    "selected_weekly_maximum_micro",
    "weekly_maximum_micro",
    "population_ceiling_converted",
    "population_ceiling_regret_micro",
})
_CELL_THRESHOLD_FIELDS: Final = frozenset({
    "threshold_dk",
    "threshold_micro",
    "operator",
    "population_lineup_hit_count",
    "population_slates_with_at_least_one_hit",
    "selected_lineup_hit_count",
    "selected_slates_with_at_least_one_hit",
})


class CorpusR6ScoreSprintScorecardV1Error(ValueError):
    """A local score input was incomplete, incompatible, or inconsistent."""


@dataclass(frozen=True, slots=True)
class ScorecardInputV1:
    """One user label and one already-downloaded local JSON path."""

    label: str
    path: Path


@dataclass(frozen=True, slots=True)
class _LoadedInput:
    label: str
    path: str
    raw: bytes
    file_sha256: str
    value: dict[str, object]


def _fail(message: str) -> None:
    raise CorpusR6ScoreSprintScorecardV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusR6ScoreSprintScorecardV1Error(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def _pairs_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"JSON repeats object key {key!r}")
        result[key] = value
    return result


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _integer(value: object, *, label: str, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        suffix = "" if minimum is None else f" >= {minimum}"
        _fail(f"{label} must be an exact integer{suffix}")
    return value


def _digest(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    identity = _mapping(value, label=label)
    if set(identity) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} fields differ")
    if (
        type(identity["uri"]) is not str
        or not identity["uri"]
        or type(identity["generation"]) is not str
        or not identity["generation"].isdigit()
    ):
        _fail(f"{label} URI or generation differs")
    _digest(identity["sha256"], label=f"{label} SHA-256")
    _integer(identity["bytes"], label=f"{label} bytes", minimum=1)
    return identity


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    retained = _digest(value.get(field), label=f"{label} {field}")
    body = {key: item for key, item in value.items() if key != field}
    if retained != canonical_sha256_v1(body):
        _fail(f"{label} self-hash differs")


def _load_input(spec: ScorecardInputV1) -> _LoadedInput:
    if type(spec.label) is not str or not spec.label.strip():
        _fail("input label must be a nonempty string")
    path = Path(spec.path)
    if not path.is_file():
        _fail(f"{spec.label}: input is not an existing local file")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusR6ScoreSprintScorecardV1Error(
            f"{spec.label}: local input read failed"
        ) from exc
    if not raw:
        _fail(f"{spec.label}: local input is empty")
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs_without_duplicates
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6ScoreSprintScorecardV1Error(
            f"{spec.label}: local input is not UTF-8 JSON"
        ) from exc
    item = _mapping(value, label=f"{spec.label} input")
    return _LoadedInput(
        label=spec.label.strip(),
        path=str(path.resolve()),
        raw=raw,
        file_sha256=sha256(raw).hexdigest(),
        value=item,
    )


def _rational(
    *, numerator: int, denominator: int, unit: str = "micro_dk"
) -> dict[str, object]:
    _integer(numerator, label="rational numerator")
    _integer(denominator, label="rational denominator", minimum=1)
    return {"numerator": numerator, "denominator": denominator, "unit": unit}


def _validate_rational(
    value: object,
    *,
    expected_numerator: int,
    expected_denominator: int,
    unit: str,
    label: str,
) -> dict[str, object]:
    row = _mapping(value, label=label)
    expected = _rational(
        numerator=expected_numerator,
        denominator=expected_denominator,
        unit=unit,
    )
    if row != expected:
        _fail(f"{label} differs from exact rows")
    return expected


def _rate(count: int) -> dict[str, object]:
    return _rational(numerator=count, denominator=SOURCE_SLATE_COUNT, unit="slates")


def _threshold_rows_from_scores(scores: Sequence[int]) -> list[dict[str, object]]:
    if len(scores) != SOURCE_SLATE_COUNT:
        _fail("threshold score vector does not contain exactly 54 slates")
    return [
        {
            "threshold_dk": threshold,
            "slates_with_at_least_one_hit": sum(
                score >= threshold * MICRO_DK_PER_POINT for score in scores
            ),
            "slate_hit_rate": _rate(sum(
                score >= threshold * MICRO_DK_PER_POINT for score in scores
            )),
        }
        for threshold in REQUESTED_THRESHOLDS_DK
    ]


def _population_coordinate(
    *, adapter_id: str, coordinate: Mapping[str, object]
) -> dict[str, object]:
    if adapter_id == "population-crossed-v1":
        required = ("heldout_block", "profile_id")
    elif adapter_id == "l2b-current-union-selectors-v1":
        # Both L2b fractions select from the same held-out-block population.
        # ``fraction_id`` describes how that population is selected and is
        # therefore part of the selector coordinate below, never population
        # identity.  Keeping it here would double-count five physical corpus
        # ceilings as ten fraction-specific populations.
        required = ("heldout_block",)
    elif adapter_id in {"hard230-v1", "hard230-selected-book-bridge-v1"}:
        required = tuple(
            key for key in ("population_role", "population_id") if key in coordinate
        )
        if "population_id" not in required:
            _fail("hard230 coordinate lacks population_id")
    else:
        _fail(f"unknown score-sprint adapter {adapter_id!r}")
    if any(key not in coordinate for key in required):
        _fail("score coordinate lacks its population dimensions")
    return {
        "adapter_id": adapter_id,
        **{key: coordinate[key] for key in required},
    }


def _selector_coordinate(coordinate: Mapping[str, object]) -> dict[str, object]:
    required = ("selector_family", "selector_id")
    if any(key not in coordinate for key in required):
        _fail("selected-book coordinate lacks selector family or ID")
    retained = {key: coordinate[key] for key in required}
    if "selector_ordinal" in coordinate:
        retained["selector_ordinal"] = coordinate["selector_ordinal"]
    if "fraction_id" in coordinate:
        retained["fraction_id"] = coordinate["fraction_id"]
    return retained


def _coordinate_key(coordinate: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(sorted(coordinate.items()))


def _validate_complete_lattice(
    *, adapter_id: str, cells: Sequence[object], label: str
) -> None:
    """Prove the complete frozen adapter lattice, not merely cell validity."""
    coordinates = [
        _mapping(_mapping(cell, label="aggregate cell").get("coordinate"),
                 label="aggregate coordinate")
        for cell in cells
    ]
    if len({_coordinate_key(row) for row in coordinates}) != len(coordinates):
        _fail(f"{label}: aggregate coordinate repeats")
    if any(row.get("metric_kind") != "selected-book" for row in coordinates):
        _fail(f"{label}: score sprint adapters require selected-book cells")

    expected: set[tuple[object, ...]] = set()
    if adapter_id == "hard230-selected-book-bridge-v1":
        for role, population_id in HARD_POPULATIONS:
            for family, selector_id in HARD_SELECTORS:
                for budget in (80, 100, 150):
                    expected.add(_coordinate_key({
                        "adapter_id": adapter_id, "metric_kind": "selected-book",
                        "population_role": role, "population_id": population_id,
                        "selector_family": family, "selector_id": selector_id,
                        "entry_budget": budget,
                    }))
    else:
        outer_name = "profile_id" if adapter_id == "population-crossed-v1" else "fraction_id"
        outer_values = POPULATION_PROFILES if outer_name == "profile_id" else L2B_FRACTIONS
        families = (
            (("grouped-native-rank80", 3, (4, 14, 80)),
             ("exact-rank150-continuation", 3, (80, 100, 150)),
             ("effective-independent-tail-shots", 1, (80, 100, 150)))
            if adapter_id == "population-crossed-v1" else
            (("grouped-native-rank80", 3, (4, 14, 80)),
             ("exact-rank150-continuation", 3, (80, 100, 150)),
             ("effective-independent-tail-shots", 1, (80, 100, 150)),
             ("tail-ladder-diversity-challengers", 3, (80, 100, 150)))
        )
        # Selector IDs are frozen predecessor identities.  Their values are
        # validated as one stable ID per family/ordinal across every outer/fold
        # coordinate, then the complete Cartesian product is required.
        selector_ids: dict[tuple[str, int], object] = {}
        for row in coordinates:
            key = (str(row.get("selector_family")), int(row.get("selector_ordinal", -1)))
            prior = selector_ids.setdefault(key, row.get("selector_id"))
            if prior != row.get("selector_id"):
                _fail(f"{label}: selector identity changes across folds")
        expected_selector_ids = {
            (family, ordinal): GENERIC_SELECTOR_IDS[family][position]
            for family, _count, _budgets in families
            for position, ordinal in enumerate(GENERIC_SELECTOR_ORDINALS[family])
        }
        expected_selector_keys = set(expected_selector_ids)
        if set(selector_ids) != expected_selector_keys or any(
            type(value) is not str or not value for value in selector_ids.values()
        ):
            _fail(f"{label}: selector family/ordinal census differs")
        if any(
            selector_ids[key] != expected_selector_ids[key]
            for key in expected_selector_keys
        ):
            _fail(f"{label}: selector IDs differ from frozen adapter registry")
        for outer in outer_values:
            for block in WORLD_BLOCKS:
                for family, count, budgets in families:
                    ordinals = GENERIC_SELECTOR_ORDINALS[family]
                    if len(ordinals) != count:
                        _fail(f"{label}: selector ordinal registry differs")
                    for ordinal in ordinals:
                        for budget in budgets:
                            expected.add(_coordinate_key({
                                "adapter_id": adapter_id,
                                "metric_kind": "selected-book",
                                outer_name: outer, "heldout_block": block,
                                "selector_family": family,
                                "selector_ordinal": ordinal,
                                "selector_id": selector_ids[(family, ordinal)],
                                "entry_budget": budget,
                            }))
    if {_coordinate_key(row) for row in coordinates} != expected:
        _fail(f"{label}: incomplete or foreign aggregate-cell lattice")


def _validate_cell(
    raw_cell: object, *, adapter_id: str
) -> tuple[dict[str, object] | None, dict[str, object]]:
    cell = _mapping(raw_cell, label="aggregate cell")
    if set(cell) != _CELL_FIELDS:
        _fail("aggregate cell fields differ")
    _self_hash(cell, field="aggregate_cell_sha256", label="aggregate cell")
    coordinate = _mapping(cell["coordinate"], label="aggregate coordinate")
    if (
        cell.get("schema_version") != AGGREGATE_CELL_SCHEMA
        or coordinate.get("adapter_id") != adapter_id
        or coordinate.get("metric_kind") not in {"selected-book", "population-only"}
        or cell.get("coordinate_sha256") != canonical_sha256_v1(coordinate)
        or cell.get("source_slate_count") != SOURCE_SLATE_COUNT
        or cell.get("complete") is not True
    ):
        _fail("aggregate cell fixed law differs")
    selected_available = cell.get("selection_conversion_available") is True
    if cell.get("selection_conversion_available") not in {True, False}:
        _fail("aggregate selection availability differs")
    if (coordinate.get("metric_kind") == "population-only") is not (
        not selected_available
    ):
        _fail("metric kind and selection-conversion availability are not iff")

    slate_rows = [
        _mapping(row, label=f"aggregate slate row[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(cell["slate_rows"], label="aggregate slate rows")
        )
    ]
    if (
        len(slate_rows) != SOURCE_SLATE_COUNT
        or cell.get("slate_rows_sha256") != canonical_sha256_v1(slate_rows)
    ):
        _fail("aggregate cell does not bind exactly 54 slate rows")

    maxima: list[int] = []
    ceilings: list[int] = []
    regrets: list[int] = []
    conversions = 0
    entry_budget = _integer(
        coordinate.get("entry_budget"), label="coordinate entry budget", minimum=1
    )
    for ordinal, (row, expected_slate_id) in enumerate(
        zip(slate_rows, EXPECTED_SLATE_IDS, strict=True)
    ):
        if set(row) != _SLATE_ROW_FIELDS:
            _fail("aggregate slate-row fields differ")
        if row.get("source_ordinal") != ordinal or row.get("slate_id") != expected_slate_id:
            _fail("aggregate slate scope/order differs from the frozen 54-slate panel")
        if row.get("entry_budget") != entry_budget:
            _fail("aggregate slate entry budget differs from coordinate")
        population_count = _integer(
            row.get("population_lineup_count"),
            label="population lineup count",
            minimum=1,
        )
        ceiling = _integer(row.get("population_ceiling_micro"), label="ceiling")
        weekly = _integer(row.get("weekly_maximum_micro"), label="weekly maximum")
        ceilings.append(ceiling)
        maxima.append(weekly)
        if selected_available:
            selected_count = _integer(
                row.get("selected_lineup_count"),
                label="selected lineup count",
                minimum=1,
            )
            selected = _integer(
                row.get("selected_weekly_maximum_micro"),
                label="selected weekly maximum",
            )
            regret = _integer(
                row.get("population_ceiling_regret_micro"),
                label="population ceiling regret",
                minimum=0,
            )
            converted = row.get("population_ceiling_converted")
            if (
                type(converted) is not bool
                or selected_count != entry_budget
                or selected_count > population_count
                or weekly != selected
                or ceiling < selected
                or regret != ceiling - selected
                or converted != (ceiling == selected)
            ):
                _fail("aggregate selected-book slate metric differs")
            regrets.append(regret)
            conversions += int(converted)
        elif any(
            row.get(field) is not None
            for field in (
                "selected_lineup_count",
                "selected_weekly_maximum_micro",
                "population_ceiling_converted",
                "population_ceiling_regret_micro",
            )
        ) or weekly != ceiling:
            _fail("population-only aggregate cell contains selected-book claims")

    _validate_rational(
        cell["mean_weekly_maximum_micro"],
        expected_numerator=sum(maxima),
        expected_denominator=SOURCE_SLATE_COUNT,
        unit="micro_dk",
        label="mean weekly maximum",
    )
    _validate_rational(
        cell["mean_population_ceiling_micro"],
        expected_numerator=sum(ceilings),
        expected_denominator=SOURCE_SLATE_COUNT,
        unit="micro_dk",
        label="mean population ceiling",
    )

    stored_thresholds = [
        _mapping(row, label="aggregate stored threshold")
        for row in _sequence(cell["thresholds"], label="aggregate thresholds")
    ]
    if [row.get("threshold_dk") for row in stored_thresholds] != list(
        STORED_NOVEL_THRESHOLDS_DK
    ):
        _fail("aggregate stored threshold registry differs")
    selected_derived = {
        row["threshold_dk"]: row["slates_with_at_least_one_hit"]
        for row in _threshold_rows_from_scores(maxima)
    }
    ceiling_derived = {
        row["threshold_dk"]: row["slates_with_at_least_one_hit"]
        for row in _threshold_rows_from_scores(ceilings)
    }
    for row in stored_thresholds:
        if set(row) != _CELL_THRESHOLD_FIELDS:
            _fail("aggregate threshold fields differ")
        threshold = _integer(row["threshold_dk"], label="stored threshold")
        population_count = _integer(
            row["population_slates_with_at_least_one_hit"],
            label="stored population slate hits",
            minimum=0,
        )
        if (
            row.get("threshold_micro") != threshold * MICRO_DK_PER_POINT
            or row.get("operator") != ">="
            or population_count != sum(
                value >= threshold * MICRO_DK_PER_POINT for value in ceilings
            )
        ):
            _fail("aggregate population threshold summary differs from slate rows")
        _integer(
            row["population_lineup_hit_count"],
            label="population lineup threshold hits",
            minimum=0,
        )
        if selected_available:
            selected_count = _integer(
                row["selected_slates_with_at_least_one_hit"],
                label="stored selected slate hits",
                minimum=0,
            )
            _integer(
                row["selected_lineup_hit_count"],
                label="selected lineup threshold hits",
                minimum=0,
            )
            if selected_count != sum(
                value >= threshold * MICRO_DK_PER_POINT for value in maxima
            ):
                _fail("aggregate selected threshold summary differs from slate rows")
        elif (
            row.get("selected_slates_with_at_least_one_hit") is not None
            or row.get("selected_lineup_hit_count") is not None
        ):
            _fail("population-only threshold contains selected hits")

    if selected_available:
        if (
            cell.get("population_ceiling_conversion_count") != conversions
            or cell.get("population_ceiling_conversion_fraction")
            != _rational(
                numerator=conversions,
                denominator=SOURCE_SLATE_COUNT,
                unit="slates",
            )
        ):
            _fail("aggregate ceiling-conversion summary differs")
        _validate_rational(
            cell["mean_population_ceiling_regret_micro"],
            expected_numerator=sum(regrets),
            expected_denominator=SOURCE_SLATE_COUNT,
            unit="micro_dk",
            label="mean population ceiling regret",
        )
    elif any(
        cell.get(field) is not None
        for field in (
            "population_ceiling_conversion_count",
            "population_ceiling_conversion_fraction",
            "mean_population_ceiling_regret_micro",
        )
    ):
        _fail("population-only aggregate contains selection summary")

    population_coordinate = _population_coordinate(
        adapter_id=adapter_id, coordinate=coordinate
    )
    ceiling_row = {
        "availability": "available",
        "population_coordinate": population_coordinate,
        "mean_population_ceiling_micro": _rational(
            numerator=sum(ceilings), denominator=SOURCE_SLATE_COUNT
        ),
        "thresholds": _threshold_rows_from_scores(ceilings),
        "_ceiling_vector": ceilings,
    }
    if not selected_available:
        return None, ceiling_row
    if coordinate.get("metric_kind") != "selected-book":
        _fail("selection-available cell is not a selected-book coordinate")
    performance = {
        "estimand_class": (
            "rotated-heldout-exact-k80"
            if adapter_id in {"population-crossed-v1", "l2b-current-union-selectors-v1"}
            and entry_budget == 80 else
            "rotated-heldout-expanded-k"
            if adapter_id in {"population-crossed-v1", "l2b-current-union-selectors-v1"}
            else "fixed-r1-r4-fit-exact-k80"
            if entry_budget == 80 else "fixed-r1-r4-fit-expanded-k"
        ),
        "population_coordinate": population_coordinate,
        "selector_coordinate": _selector_coordinate(coordinate),
        "selection_coordinate": coordinate,
        "entry_budget": entry_budget,
        "mean_weekly_maximum_micro": _rational(
            numerator=sum(maxima), denominator=SOURCE_SLATE_COUNT
        ),
        "thresholds": _threshold_rows_from_scores(maxima),
        "mean_population_ceiling_regret_micro": _rational(
            numerator=sum(regrets), denominator=SOURCE_SLATE_COUNT
        ),
        "population_ceiling_conversion_count": conversions,
    }
    # Explicit references silence any temptation to use lineup-hit counts as
    # weekly best-of-book counts.
    if any(
        selected_derived[threshold]
        != next(
            row["selected_slates_with_at_least_one_hit"]
            for row in stored_thresholds
            if row["threshold_dk"] == threshold
        )
        for threshold in (200, 220, 230)
    ) or any(
        ceiling_derived[threshold]
        != next(
            row["population_slates_with_at_least_one_hit"]
            for row in stored_thresholds
            if row["threshold_dk"] == threshold
        )
        for threshold in (200, 220, 230)
    ):
        _fail("requested threshold projection differs from stored grade")
    return performance, ceiling_row


def _extract_new_grade(source: _LoadedInput) -> dict[str, object]:
    grade = source.value
    schema = grade.get("schema_version")
    novel_like = schema in {NOVEL_GRADE_SCHEMA, L2B_PROVISIONAL_GRADE_SCHEMA}
    if novel_like:
        hash_field = "realized_grade_sha256"
        expected_fields = (
            _NOVEL_ROOT_FIELDS | _PROVISIONAL_AUTHORITY_FIELDS
            if schema == L2B_PROVISIONAL_GRADE_SCHEMA
            else _NOVEL_ROOT_FIELDS
        )
        if set(grade) != expected_fields:
            _fail(f"{source.label}: generic realized-grade root fields differ")
        if (
            grade.get("adapter_id") not in {
                "population-crossed-v1", "l2b-current-union-selectors-v1"
            }
            or
            grade.get("score_unit") != "micro_dk"
            or grade.get("micro_dk_per_point") != MICRO_DK_PER_POINT
            or grade.get("uses_realized_outcomes") is not True
            or grade.get("terminal_before_first_outcome_read") is not True
            or grade.get("every_distinct_roster_scored_once_per_slate") is not True
            or grade.get("historical_retune_licensed") is not False
            or grade.get("historical_retry_licensed") is not False
            or grade.get("decision_authority") is not False
            or grade.get("aggregate_cell_count")
            != len(_sequence(grade.get("aggregate_cells"), label="aggregate cells"))
        ):
            _fail(f"{source.label}: generic realized-grade law differs")
        if schema == L2B_PROVISIONAL_GRADE_SCHEMA and (
            grade.get("adapter_id") != "l2b-current-union-selectors-v1"
            or grade.get("authority_tier")
            != "descriptive-provisional-provider-results"
            or grade.get("provider_task_results_structurally_validated") is not True
            or grade.get("central_exact_selector_replay_completed") is not False
            or grade.get("asynchronous_exact_replay_required") is not True
            or grade.get("coherent_substitution_excluded_by_hashes_alone") is not False
            or grade.get("confirmatory_authority") is not False
            or grade.get("promotion_authority") is not False
            or grade.get("production_change_licensed") is not False
        ):
            _fail(f"{source.label}: provisional realized-grade authority differs")
    elif schema == HARD230_GRADE_SCHEMA:
        hash_field = "grade_sha256"
        if set(grade) != _HARD_ROOT_FIELDS:
            _fail(f"{source.label}: hard230 realized-grade root fields differ")
        if (
            grade.get("adapter_id") != "hard230-selected-book-bridge-v1"
            or
            grade.get("all_score_free_predecessors_replayed_before_outcome_open")
            is not True
            or grade.get("outcome_source_and_slate_identity_bound") is not True
        ):
            _fail(f"{source.label}: hard230 realized-grade law differs")
    else:
        _fail(f"{source.label}: unsupported new-grade schema")
    _self_hash(grade, field=hash_field, label=f"{source.label} realized grade")
    if grade.get("source_slate_count") != SOURCE_SLATE_COUNT or grade.get(
        "complete"
    ) is not True:
        _fail(f"{source.label}: realized grade is not a complete 54-slate result")
    adapter_id = str(grade["adapter_id"])
    identity_fields = (
        ("terminal_root_identity", "task_manifest_identity",
         "later_source_freeze_identity")
        if novel_like else
        ("terminal_identity", "later_source_identity")
    )
    for field in identity_fields:
        _identity(grade.get(field), label=f"{source.label} {field}")
    digest_fields = (
        ("terminal_root_sha256", "task_manifest_sha256")
        if novel_like else ("terminal_sha256",)
    )
    for field in digest_fields:
        _digest(grade.get(field), label=f"{source.label} {field}")
    outcome_identity = _identity(
        grade.get("outcome_snapshot_identity"),
        label=f"{source.label} outcome snapshot",
    )
    # Object content identity hashes the complete snapshot, whereas the
    # snapshot's internal self-hash excludes its own hash field.  They are two
    # distinct, intentional digests and must never be equated.
    _digest(
        grade.get("outcome_snapshot_sha256"),
        label=f"{source.label} outcome snapshot internal SHA-256",
    )
    cells = _sequence(grade.get("aggregate_cells"), label="aggregate cells")
    if grade.get("aggregate_cells_sha256") != canonical_sha256_v1(cells):
        _fail(f"{source.label}: aggregate-cell hash differs")
    slate_grades = _sequence(grade.get("slate_grades"), label="slate grades")
    if (
        len(slate_grades) != SOURCE_SLATE_COUNT
        or grade.get("slate_grades_sha256") != canonical_sha256_v1(slate_grades)
        or (novel_like
            and grade.get("slate_grade_count") != SOURCE_SLATE_COUNT)
    ):
        _fail(f"{source.label}: slate-grade census/hash differs")
    if novel_like:
        expected_thresholds = [{
            "threshold_dk": threshold,
            "threshold_micro": threshold * MICRO_DK_PER_POINT,
            "operator": ">=",
        } for threshold in STORED_NOVEL_THRESHOLDS_DK]
        if grade.get("threshold_registry") != expected_thresholds:
            _fail(f"{source.label}: threshold registry differs")
        _integer(grade.get("roster_sum_operation_count"),
                 label=f"{source.label} roster sum operations", minimum=1)
    _validate_complete_lattice(adapter_id=adapter_id, cells=cells,
                               label=source.label)

    performance_rows: list[dict[str, object]] = []
    ceilings: dict[bytes, dict[str, object]] = {}
    for raw_cell in cells:
        performance, ceiling = _validate_cell(raw_cell, adapter_id=adapter_id)
        key = canonical_json_bytes_v1(ceiling["population_coordinate"])
        prior = ceilings.get(key)
        if prior is None:
            ceilings[key] = ceiling
        elif prior["_ceiling_vector"] != ceiling["_ceiling_vector"]:
            _fail(f"{source.label}: one population has multiple corpus ceilings")
        if performance is not None:
            performance_rows.append(performance)
    if not performance_rows and not ceilings:
        _fail(f"{source.label}: realized grade has no comparable cells")
    for row in ceilings.values():
        row.pop("_ceiling_vector")
    return {
        "schema_version": schema,
        "outcome_authority": {
            "kind": "exact-realized-outcome-snapshot",
            "identity": outcome_identity,
            "internal_sha256": grade["outcome_snapshot_sha256"],
        },
        "performance_rows": performance_rows,
        "ceiling_rows": list(ceilings.values()),
    }


def _validate_report_thresholds(
    value: object, *, expected_denominator: int, label: str
) -> list[dict[str, object]]:
    rows = [
        _mapping(row, label=f"{label} threshold")
        for row in _sequence(value, label=f"{label} thresholds")
    ]
    by_threshold: dict[int, dict[str, object]] = {}
    for row in rows:
        threshold = _integer(row.get("threshold_dk"), label=f"{label} threshold")
        slate_fraction = _mapping(
            row.get("slate_hit_fraction"), label=f"{label} slate-hit fraction"
        )
        count = _integer(
            row.get("slates_with_at_least_one_hit"),
            label=f"{label} slate hits",
            minimum=0,
        )
        if (
            threshold in by_threshold
            or row.get("threshold_micro") != threshold * MICRO_DK_PER_POINT
            or row.get("operator") != ">="
            or slate_fraction
            != _rational(
                numerator=count,
                denominator=expected_denominator,
                unit="slates",
            )
        ):
            _fail(f"{label} threshold denominator or registry differs")
        by_threshold[threshold] = row
    if any(threshold not in by_threshold for threshold in REQUESTED_THRESHOLDS_DK):
        _fail(f"{label} omits a requested threshold")
    return [
        {
            "threshold_dk": threshold,
            "slates_with_at_least_one_hit": by_threshold[threshold][
                "slates_with_at_least_one_hit"
            ],
            "slate_hit_rate": _rate(
                int(by_threshold[threshold]["slates_with_at_least_one_hit"])
            ),
        }
        for threshold in REQUESTED_THRESHOLDS_DK
    ]


def _extract_full_union_benchmark(source: _LoadedInput) -> dict[str, object]:
    report = source.value
    if source.file_sha256 != FROZEN_FULL_UNION_FILE_SHA256:
        _fail(f"{source.label}: current-R6 benchmark file hash is not frozen")
    _self_hash(report, field="score_report_sha256", label="current-R6 report")
    if (
        report.get("schema_version") != FULL_UNION_REPORT_SCHEMA
        or report.get("source_slate_count") != SOURCE_SLATE_COUNT
        or report.get("slate_grade_object_count") != SOURCE_SLATE_COUNT
        or report.get("reads_grade_artifacts_only") is not True
        or report.get("outcome_source_read") is not False
        or report.get("historical_outcome_lease_read") is not False
        or report.get("bigquery_client_constructed") is not False
        or report.get("complete") is not True
    ):
        _fail(f"{source.label}: current-R6 benchmark law differs")
    summaries = _sequence(
        report.get("strategy_summaries"), label="current-R6 strategy summaries"
    )
    if report.get("strategy_count") != len(summaries) or len(summaries) != 8:
        _fail(f"{source.label}: current-R6 strategy census differs")
    performance: list[dict[str, object]] = []
    for ordinal, raw_summary in enumerate(summaries):
        summary = _mapping(raw_summary, label="current-R6 strategy summary")
        if summary.get("strategy_ordinal") != ordinal:
            _fail("current-R6 strategy order differs")
        strategy_id = summary.get("strategy_id")
        if type(strategy_id) is not str or not strategy_id:
            _fail("current-R6 strategy ID differs")
        final_cells = [
            _mapping(cell, label="current-R6 final cell")
            for cell in _sequence(summary.get("cells"), label="current-R6 cells")
            if isinstance(cell, Mapping)
            and cell.get("fit_scope_id") == "all-block-final-fit"
            and cell.get("entry_count") == 80
        ]
        if len(final_cells) != 1:
            _fail("current-R6 benchmark lacks one final-fit exact-80 cell")
        cell = final_cells[0]
        mean = _mapping(cell.get("slate_maximum_mean"), label="current-R6 mean")
        numerator = _integer(mean.get("numerator"), label="current-R6 mean numerator")
        if mean != _rational(
            numerator=numerator,
            denominator=SOURCE_SLATE_COUNT,
            unit="micro_dk",
        ):
            _fail("current-R6 mean denominator differs")
        performance.append({
            "estimand_class": "all-block-final-fit-exact-k80",
            "population_coordinate": {
                "adapter_id": "frozen-current-r6-benchmark",
                "population_id": "r6-full-union",
                "fit_scope_id": "all-block-final-fit",
            },
            "selector_coordinate": {"selector_id": strategy_id},
            "selection_coordinate": {
                "adapter_id": "frozen-current-r6-benchmark",
                "population_id": "r6-full-union",
                "fit_scope_id": "all-block-final-fit",
                "selector_id": strategy_id,
                "entry_budget": 80,
            },
            "entry_budget": 80,
            "mean_weekly_maximum_micro": mean,
            "thresholds": _validate_report_thresholds(
                cell.get("thresholds"),
                expected_denominator=SOURCE_SLATE_COUNT,
                label=f"current-R6 {strategy_id}",
            ),
            "mean_population_ceiling_regret_micro": None,
            "population_ceiling_conversion_count": None,
        })
    return {
        "schema_version": FULL_UNION_REPORT_SCHEMA,
        "outcome_authority": {
            "kind": "frozen-grade-report",
            "file_sha256": source.file_sha256,
            "bound_to_new_grade_snapshot": False,
        },
        "performance_rows": performance,
        "ceiling_rows": [{
            "availability": "unavailable",
            "population_coordinate": {
                "adapter_id": "frozen-current-r6-benchmark",
                "population_id": "r6-full-union",
                "fit_scope_id": "all-block-final-fit",
            },
            "reason": "aggregate-only frozen report omits corpus ceiling",
            "mean_population_ceiling_micro": None,
            "thresholds": None,
        }],
    }


def _score_to_micro(value: object, *, label: str) -> int:
    if type(value) not in {int, float}:
        _fail(f"{label} must be a JSON number")
    try:
        raw_micro = Decimal(str(value)) * MICRO_DK_PER_POINT
    except InvalidOperation as exc:
        raise CorpusR6ScoreSprintScorecardV1Error(
            f"{label} is not a finite score"
        ) from exc
    rounded = raw_micro.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    if not raw_micro.is_finite() or abs(raw_micro - rounded) > Decimal("0.001"):
        _fail(f"{label} cannot be represented exactly in micro-DK")
    return int(rounded)


def _extract_a7_benchmark(source: _LoadedInput) -> dict[str, object]:
    report = source.value
    if source.file_sha256 != FROZEN_A7_FILE_SHA256:
        _fail(f"{source.label}: legacy A7 benchmark file hash is not frozen")
    outcome = _mapping(report.get("outcome"), label="legacy A7 outcome")
    if (
        report.get("version") != FROZEN_A7_VERSION
        or report.get("run_id") != "20260820-a7-select-ladder-phase-s-incumbent-v2"
        or report.get("uses_realized_outcomes") is not True
        or outcome.get("uses_realized_outcomes") is not True
        or report.get("production_change_licensed") is not False
    ):
        _fail(f"{source.label}: legacy A7 benchmark law differs")
    slates = _sequence(report.get("slates"), label="legacy A7 slates")
    expected_pairs = [
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]
    observed_pairs = [
        (
            _mapping(row, label="legacy A7 slate").get("season"),
            _mapping(row, label="legacy A7 slate").get("week"),
        )
        for row in slates
    ]
    if observed_pairs != expected_pairs:
        _fail("legacy A7 slate scope/order differs")
    conversion = _mapping(
        outcome.get("pool_to_book_conversion"),
        label="legacy A7 pool-to-book conversion",
    )
    weekly = [
        _mapping(row, label="legacy A7 weekly conversion")
        for row in _sequence(conversion.get("weekly"), label="legacy A7 weekly rows")
    ]
    if len(weekly) != SOURCE_SLATE_COUNT or [
        (row.get("season"), row.get("week")) for row in weekly
    ] != expected_pairs:
        _fail("legacy A7 weekly denominator or scope differs")
    vectors = {
        "control": [
            _score_to_micro(row.get("control_s80"), label="legacy control score")
            for row in weekly
        ],
        "treatment": [
            _score_to_micro(
                row.get("treatment_s80"), label="legacy treatment score"
            )
            for row in weekly
        ],
        "ceiling": [
            _score_to_micro(row.get("pool_c"), label="legacy corpus ceiling")
            for row in weekly
        ],
    }
    cut80 = _mapping(
        _mapping(outcome.get("cuts"), label="legacy A7 cuts").get("80"),
        label="legacy A7 exact-80 cut",
    )
    performance: list[dict[str, object]] = []
    for arm, selector_id in (
        ("control", "coverage-194-control"),
        ("treatment", "a7-select-ladder-treatment"),
    ):
        scores = vectors[arm]
        derived_thresholds = _threshold_rows_from_scores(scores)
        retained_counts = _mapping(
            cut80.get(f"{arm}_threshold_counts"),
            label=f"legacy A7 {arm} threshold counts",
        )
        if any(
            retained_counts.get(str(row["threshold_dk"]))
            != row["slates_with_at_least_one_hit"]
            for row in derived_thresholds
        ):
            _fail(f"legacy A7 {arm} threshold counts differ from weekly rows")
        performance.append({
            "estimand_class": "frozen-legacy-exact-k80-reference",
            "population_coordinate": {
                "adapter_id": "frozen-legacy-a7-benchmark",
                "population_id": "a7-fixed-incumbent-pool",
            },
            "selector_coordinate": {"selector_id": selector_id},
            "selection_coordinate": {
                "adapter_id": "frozen-legacy-a7-benchmark",
                "population_id": "a7-fixed-incumbent-pool",
                "selector_id": selector_id,
                "entry_budget": 80,
            },
            "entry_budget": 80,
            "mean_weekly_maximum_micro": _rational(
                numerator=sum(scores), denominator=SOURCE_SLATE_COUNT
            ),
            "thresholds": derived_thresholds,
            "mean_population_ceiling_regret_micro": _rational(
                numerator=sum(
                    ceiling - selected
                    for ceiling, selected in zip(
                        vectors["ceiling"], scores, strict=True
                    )
                ),
                denominator=SOURCE_SLATE_COUNT,
            ),
            "population_ceiling_conversion_count": sum(
                ceiling == selected
                for ceiling, selected in zip(vectors["ceiling"], scores, strict=True)
            ),
        })
    ceiling_thresholds = _threshold_rows_from_scores(vectors["ceiling"])
    published_ceiling_counts = _mapping(
        conversion.get("pool_c_threshold_counts"),
        label="legacy A7 corpus threshold counts",
    )
    if any(
        published_ceiling_counts.get(str(row["threshold_dk"]))
        != row["slates_with_at_least_one_hit"]
        for row in ceiling_thresholds
    ):
        _fail("legacy A7 corpus threshold counts differ")
    return {
        "schema_version": FROZEN_A7_VERSION,
        "outcome_authority": {
            "kind": "frozen-file-reference",
            "file_sha256": source.file_sha256,
            "bound_to_new_grade_snapshot": False,
        },
        "performance_rows": performance,
        "ceiling_rows": [{
            "availability": "available",
            "population_coordinate": {
                "adapter_id": "frozen-legacy-a7-benchmark",
                "population_id": "a7-fixed-incumbent-pool",
            },
            "mean_population_ceiling_micro": _rational(
                numerator=sum(vectors["ceiling"]), denominator=SOURCE_SLATE_COUNT
            ),
            "thresholds": ceiling_thresholds,
        }],
    }


def _extract(source: _LoadedInput) -> dict[str, object]:
    schema = source.value.get("schema_version")
    if schema in {
        NOVEL_GRADE_SCHEMA,
        L2B_PROVISIONAL_GRADE_SCHEMA,
        HARD230_GRADE_SCHEMA,
    }:
        return _extract_new_grade(source)
    if schema == FULL_UNION_REPORT_SCHEMA:
        return _extract_full_union_benchmark(source)
    if source.value.get("version") == FROZEN_A7_VERSION:
        return _extract_a7_benchmark(source)
    _fail(f"{source.label}: unsupported local score artifact schema")


def _merge_global_ceiling(
    retained: dict[bytes, dict[str, object]], candidate: dict[str, object]
) -> None:
    row = {key: value for key, value in candidate.items()
           if key not in {"source_ordinal", "source_label"}}
    key = canonical_json_bytes_v1(row["population_coordinate"])
    prior = retained.get(key)
    if prior is None:
        retained[key] = candidate
    elif {key: value for key, value in prior.items()
          if key not in {"source_ordinal", "source_label"}} != row:
        _fail("cross-input duplicate population ceilings diverge")


def build_scorecard_v1(inputs: Sequence[ScorecardInputV1]) -> dict[str, object]:
    """Build one exact-scope comparison without any external reads or writes."""
    if not inputs:
        _fail("at least one local score input is required")
    loaded = [_load_input(spec) for spec in inputs]
    labels = [source.label for source in loaded]
    if len(labels) != len(set(labels)):
        _fail("scorecard input labels must be unique")
    extracted = [_extract(source) for source in loaded]
    outcome_authorities = [
        item["outcome_authority"]
        for item in extracted
        if item["outcome_authority"]["kind"] == "exact-realized-outcome-snapshot"
    ]
    if outcome_authorities and any(
        authority != outcome_authorities[0]
        for authority in outcome_authorities[1:]
    ):
        _fail("new grades use incompatible realized-outcome authority tuples")

    performance: list[dict[str, object]] = []
    ceilings_by_key: dict[bytes, dict[str, object]] = {}
    sources: list[dict[str, object]] = []
    for source_ordinal, (source, item) in enumerate(zip(loaded, extracted, strict=True)):
        sources.append({
            "source_ordinal": source_ordinal,
            "label": source.label,
            "path": source.path,
            "file_sha256": source.file_sha256,
            "input_schema_version": item["schema_version"],
            "outcome_authority": item["outcome_authority"],
        })
        for row in item["performance_rows"]:
            performance.append({
                "source_ordinal": source_ordinal,
                "source_label": source.label,
                **row,
            })
        for row in item["ceiling_rows"]:
            candidate = {
                "source_ordinal": source_ordinal,
                "source_label": source.label,
                **row,
            }
            # Population identity, not source label, owns a ceiling.  Identical
            # duplicate populations collapse globally; divergent duplicates
            # are an integrity failure.
            _merge_global_ceiling(ceilings_by_key, candidate)
    if not performance:
        _fail("scorecard has no selected-book performance rows")
    body = {
        "schema_version": SCORECARD_SCHEMA,
        "scope": {
            "logical_scope_id": LOGICAL_SCOPE_ID,
            "source_slate_count": SOURCE_SLATE_COUNT,
            "slate_ids": list(EXPECTED_SLATE_IDS),
        },
        "new_grade_outcome_authority": (
            None if not outcome_authorities else {
                "kind": "common-exact-realized-outcome-snapshot",
                "identity": outcome_authorities[0]["identity"],
                "internal_sha256": outcome_authorities[0]["internal_sha256"],
            }
        ),
        "threshold_registry": [{
            "threshold_dk": threshold,
            "threshold_micro": threshold * MICRO_DK_PER_POINT,
            "operator": ">=",
        } for threshold in REQUESTED_THRESHOLDS_DK],
        "sources": sources,
        "decision_bearing_all_block_final_fit_rows": [
            row for row in performance
            if row["estimand_class"] == "all-block-final-fit-exact-k80"
        ],
        "frozen_benchmark_reference_rows": [
            row for row in performance
            if row["estimand_class"] == "frozen-legacy-exact-k80-reference"
        ],
        "diagnostic_groups": [{
            "estimand_class": estimand,
            "entry_budget": budget,
            "rows": [row for row in performance
                     if row["estimand_class"] == estimand
                     and row["entry_budget"] == budget],
        } for estimand, budget in sorted({
            (str(row["estimand_class"]), int(row["entry_budget"]))
            for row in performance
            if row["estimand_class"] not in {
                "all-block-final-fit-exact-k80",
                "frozen-legacy-exact-k80-reference",
            }
        })],
        "estimands_never_ranked_across_groups": True,
        "corpus_ceiling_rows": list(ceilings_by_key.values()),
        "corpus_ceiling_reported_separately": True,
        "external_reads_performed": False,
        "outcome_source_read": False,
        "cloud_mutation_performed": False,
        "complete": True,
    }
    return {**body, "scorecard_sha256": canonical_sha256_v1(body)}


def _mean_display(value: object) -> str:
    rational = _mapping(value, label="display mean")
    numerator = Decimal(_integer(rational.get("numerator"), label="mean numerator"))
    denominator = Decimal(
        _integer(rational.get("denominator"), label="mean denominator", minimum=1)
    )
    if rational.get("unit") != "micro_dk":
        _fail("display mean unit differs")
    return f"{numerator / denominator / MICRO_DK_PER_POINT:.3f}"


def _threshold_display(rows: object, threshold: int) -> str:
    for raw in _sequence(rows, label="display thresholds"):
        row = _mapping(raw, label="display threshold")
        if row.get("threshold_dk") == threshold:
            count = _integer(
                row.get("slates_with_at_least_one_hit"),
                label="display threshold count",
                minimum=0,
            )
            return f"{count}/54 ({Decimal(count) * 100 / 54:.1f}%)"
    _fail(f"display threshold {threshold} is absent")


def _compact_coordinate(value: object) -> str:
    return canonical_json_bytes_v1(value).decode("utf-8")


def _append_performance_table(
    lines: list[str], rows: object, *, label: str
) -> None:
    """Render every selected-book metric row within one estimand section."""
    lines.extend((
        "| Source | Population coordinate | Selector coordinate | K | Mean weekly max | >=194 | >=200 | >=220 | >=230 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ))
    for raw in _sequence(rows, label=label):
        row = _mapping(raw, label="performance row")
        lines.append(
            "| "
            + " | ".join((
                str(row["source_label"]),
                f"`{_compact_coordinate(row['population_coordinate'])}`",
                f"`{_compact_coordinate(row['selector_coordinate'])}`",
                str(row["entry_budget"]),
                _mean_display(row["mean_weekly_maximum_micro"]),
                *(
                    _threshold_display(row["thresholds"], threshold)
                    for threshold in REQUESTED_THRESHOLDS_DK
                ),
            ))
            + " |"
        )


def render_markdown_v1(scorecard: Mapping[str, object]) -> str:
    """Render a compact human comparison while preserving exact JSON output."""
    if scorecard.get("schema_version") != SCORECARD_SCHEMA:
        _fail("cannot render an unknown scorecard schema")
    lines = [
        "# R6 score sprint scorecard",
        "",
        f"Scope: `{LOGICAL_SCOPE_ID}` ({SOURCE_SLATE_COUNT} slates).",
        "",
        "## Decision-bearing all-block final-fit (exact K80)",
        "",
    ]
    rendered_rows = _sequence(
        scorecard.get("decision_bearing_all_block_final_fit_rows"),
        label="decision rows",
    )
    _append_performance_table(lines, rendered_rows, label="decision rows")
    lines.extend(("", "## Frozen legacy references", ""))
    _append_performance_table(
        lines,
        scorecard.get("frozen_benchmark_reference_rows"),
        label="benchmark rows",
    )
    lines.extend(("", "## Rotated/fixed-fit diagnostics (not ranked with final-fit)", ""))
    for raw_group in _sequence(scorecard.get("diagnostic_groups"),
                               label="diagnostic groups"):
        group = _mapping(raw_group, label="diagnostic group")
        lines.extend((
            f"### `{group['estimand_class']}` — K={group['entry_budget']}",
            "",
        ))
        _append_performance_table(
            lines, group.get("rows"), label="diagnostic rows"
        )
        lines.append("")
    lines.extend((
        "",
        "## Corpus ceilings (not selector scores)",
        "",
        "| Source | Population coordinate | Mean ceiling | >=194 | >=200 | >=220 | >=230 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ))
    for raw in _sequence(
        scorecard.get("corpus_ceiling_rows"), label="corpus ceiling rows"
    ):
        row = _mapping(raw, label="corpus ceiling row")
        if row.get("availability") == "available":
            values = (
                _mean_display(row["mean_population_ceiling_micro"]),
                *(
                    _threshold_display(row["thresholds"], threshold)
                    for threshold in REQUESTED_THRESHOLDS_DK
                ),
            )
        elif row.get("availability") == "unavailable":
            reason = str(row.get("reason", "unavailable"))
            values = (f"N/A ({reason})", "N/A", "N/A", "N/A", "N/A")
        else:
            _fail("corpus ceiling availability differs")
        lines.append(
            "| "
            + " | ".join((
                str(row["source_label"]),
                f"`{_compact_coordinate(row['population_coordinate'])}`",
                *values,
            ))
            + " |"
        )
    lines.extend((
        "",
        "The >=194 values for novel-roster grades are derived exactly from their 54 immutable weekly maxima; stored >=200/220/230 counts are independently cross-checked.",
        "",
    ))
    return "\n".join(lines)


__all__ = [
    "CorpusR6ScoreSprintScorecardV1Error",
    "ScorecardInputV1",
    "build_scorecard_v1",
    "canonical_json_bytes_v1",
    "canonical_sha256_v1",
    "render_markdown_v1",
]
