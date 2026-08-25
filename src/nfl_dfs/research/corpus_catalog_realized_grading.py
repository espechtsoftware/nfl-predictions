"""Pure score-once realized grading over an immutable Core v1 catalog.

The scorer has no warehouse, object-store, selector, graph, or process API.
It consumes an exact Core v1 catalog and a separately materialized player
outcome snapshot, sums each unique roster exactly once per slate, and projects
all 4/14/80 books from that shared score map.  Contest rank and ROI remain
unavailable because a player-score snapshot is not a full contest field or a
payout settlement record.

All authoritative arithmetic uses signed integer micro-DK points.  Means,
medians, fractions, and sensitivity summaries are retained as exact rational
numerator/denominator pairs; no floating-point summary is authoritative.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_core_v1_catalog as catalog_contract
from nfl_dfs.research import corpus_core_v1_outcome_snapshot as outcome_contract
from nfl_dfs.research.corpus_batch_evidence_contract import MICRO_DK_PER_POINT


OUTCOME_SNAPSHOT_SCHEMA: Final = outcome_contract.OUTCOME_SNAPSHOT_SCHEMA
RESULT_SCHEMA: Final = "corpus-core-v1-realized-catalog-grade/v1"
SLATE_GRADE_SCHEMA: Final = "corpus-core-v1-realized-slate-grade/v1"
BOOK_GRADE_SCHEMA: Final = "corpus-core-v1-realized-book-grade/v1"
CONTRAST_ROW_SCHEMA: Final = "corpus-core-v1-realized-contrast-row/v1"
CONTRAST_SUMMARY_SCHEMA: Final = "corpus-core-v1-realized-contrast-summary/v1"

_SHA256: Final = re.compile(r"[0-9a-f]{64}")


class CorpusCatalogRealizedGradingError(ValueError):
    """The generic Core v1 realized grade failed closed."""


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCatalogRealizedGradingError(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _fail(message: str) -> None:
    raise CorpusCatalogRealizedGradingError(message)


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


def _exact_int(
    value: object, *, label: str, minimum: int | None = None,
) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        suffix = "" if minimum is None else f" >= {minimum}"
        _fail(f"{label} must be an exact integer{suffix}")
    return value


def _canonical_string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be a nonempty canonical string")
    return value


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCatalogRealizedGradingError(str(exc)) from exc


def _json_identity(
    value: object, identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCatalogRealizedGradingError(str(exc)) from exc


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _self_hash(value: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = canonical_sha256(result)
    return result


def _rational(numerator: int, denominator: int, *, unit: str) -> dict[str, object]:
    if type(numerator) is not int or type(denominator) is not int or denominator < 1:
        raise AssertionError("internal rational arithmetic received invalid values")
    return {"numerator": numerator, "denominator": denominator, "unit": unit}


def _mean(values: Sequence[int]) -> dict[str, object]:
    if not values:
        _fail("an exact mean requires at least one value")
    return _rational(sum(values), len(values), unit="micro_dk")


def _median(values: Sequence[int]) -> dict[str, object]:
    if not values:
        _fail("an exact median requires at least one value")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return _rational(ordered[middle], 1, unit="micro_dk")
    return _rational(
        ordered[middle - 1] + ordered[middle], 2, unit="micro_dk"
    )


def _threshold_rows(scores: Sequence[int]) -> list[dict[str, object]]:
    count = len(scores)
    if not count:
        _fail("threshold metrics require one nonempty score population")
    rows: list[dict[str, object]] = []
    for threshold_dk in catalog_contract.THRESHOLDS_DK:
        threshold_micro = threshold_dk * MICRO_DK_PER_POINT
        hits = sum(score >= threshold_micro for score in scores)
        rows.append({
            "threshold_dk": threshold_dk,
            "threshold_micro": threshold_micro,
            "at_or_above_count": hits,
            "at_or_above_fraction": _rational(hits, count, unit="lineups"),
            "produced_at_least_one_hit": hits > 0,
        })
    return rows


def _union_score_rows(
    *,
    source_ordinal: int,
    lineup_ids: Sequence[str],
    rosters: Sequence[tuple[str, ...]],
    player_scores: Mapping[tuple[int, str], int],
) -> tuple[list[dict[str, object]], dict[str, int]]:
    rows: list[dict[str, object]] = []
    score_by_lineup: dict[str, int] = {}
    for union_index, (lineup_id, roster) in enumerate(
        zip(lineup_ids, rosters, strict=True)
    ):
        try:
            score = sum(player_scores[(source_ordinal, player)] for player in roster)
        except KeyError as exc:
            _fail("a union roster lacks an exact slate-keyed player outcome")
        row = {
            "union_index": union_index,
            "lineup_id": lineup_id,
            "roster_identity_sha256": canonical_sha256(list(roster)),
            "realized_score_micro": score,
        }
        rows.append(row)
        score_by_lineup[lineup_id] = score
    if len(score_by_lineup) != len(lineup_ids):
        raise AssertionError("catalog union lineup identities repeated after validation")
    return rows, score_by_lineup


def _union_metrics(
    *, score_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    scores = [int(row["realized_score_micro"]) for row in score_rows]
    ordered = sorted(scores, reverse=True)
    threshold_rows = _threshold_rows(scores)
    subset_rows: dict[str, object] = {}
    for threshold_dk in (200, 230):
        threshold_micro = threshold_dk * MICRO_DK_PER_POINT
        indices = [
            int(row["union_index"])
            for row in score_rows
            if int(row["realized_score_micro"]) >= threshold_micro
        ]
        lineup_ids = [str(score_rows[index]["lineup_id"]) for index in indices]
        subset_rows[f"ge_{threshold_dk}"] = {
            "threshold_micro": threshold_micro,
            "union_indices": indices,
            "lineup_ids": lineup_ids,
            "lineup_ids_sha256": canonical_sha256(lineup_ids),
        }
    return {
        "unique_union_roster_count": len(scores),
        "complete_score_coverage": True,
        "maximum_micro": ordered[0],
        "top_3_scores_micro": ordered[:3],
        "top_5_scores_micro": ordered[:5],
        "top_10_scores_micro": ordered[:10],
        "thresholds": threshold_rows,
        "tail_subsets": subset_rows,
        "score_multiset_sha256": canonical_sha256(ordered),
    }


def _book_metric(
    *,
    source_ordinal: int,
    book: Mapping[str, object],
    rank: Mapping[str, object],
    union_score_rows: Sequence[Mapping[str, object]],
    score_by_lineup: Mapping[str, int],
    corpus_ceiling: int,
) -> dict[str, object]:
    budget = int(book["entry_budget"])
    indices = [int(value) for value in book["selected_union_indices"]]
    expected_indices = [int(value) for value in rank["rank_union_indices"][:budget]]
    if indices != expected_indices:
        _fail("book projection differs from its immutable rank prefix")
    rows = [
        {
            "selection_rank": selection_rank,
            **dict(union_score_rows[union_index]),
        }
        for selection_rank, union_index in enumerate(indices)
    ]
    # Independent projection replay uses the book's lineup identities and the
    # already-built score map.  It never sums a roster a second time.
    replayed_scores = [
        score_by_lineup[str(lineup_id)] for lineup_id in book["selected_lineup_ids"]
    ]
    scores = [int(row["realized_score_micro"]) for row in rows]
    if (
        replayed_scores != scores
        or [row["lineup_id"] for row in rows] != list(book["selected_lineup_ids"])
    ):
        _fail("book score-map projection does not independently replay")
    maximum = max(scores)
    gap = corpus_ceiling - maximum
    if gap < 0:
        raise AssertionError("book maximum exceeds its shared union ceiling")
    body = {
        "schema_version": BOOK_GRADE_SCHEMA,
        "source_ordinal": source_ordinal,
        "book_id": book["book_id"],
        "book_sha256": book["book_sha256"],
        "strategy_id": book["strategy_id"],
        "implementation_sha256": book["implementation_sha256"],
        "entry_budget": budget,
        "entry_count": len(scores),
        "maximum_micro": maximum,
        "mean": _mean(scores),
        "median": _median(scores),
        "top_three_mean": _mean(sorted(scores, reverse=True)[:3]),
        "thresholds": _threshold_rows(scores),
        "gap_to_shared_corpus_ceiling_micro": gap,
        "roster_score_rows_rank_order": rows,
        "rank_order_score_rows_sha256": canonical_sha256(rows),
        "score_multiset_sha256": canonical_sha256(sorted(scores)),
        "exact_prefix_consistency_verified": True,
        "independent_score_map_projection_replayed": True,
    }
    return _self_hash(body, "book_grade_sha256")


def _build_slate_grade(
    *,
    catalog_slate: Mapping[str, object],
    player_scores: Mapping[tuple[int, str], int],
) -> tuple[dict[str, object], int]:
    source_ordinal = int(catalog_slate["source_ordinal"])
    union = _mapping(catalog_slate["union_population"], label="union population")
    lineup_ids = [str(value) for value in union["lineup_ids"]]
    rosters = [
        tuple(str(player) for player in roster) for roster in union["rosters"]
    ]
    score_rows, score_by_lineup = _union_score_rows(
        source_ordinal=source_ordinal,
        lineup_ids=lineup_ids,
        rosters=rosters,
        player_scores=player_scores,
    )
    union_metrics = _union_metrics(score_rows=score_rows)
    ceiling = int(union_metrics["maximum_micro"])
    ranks = {
        str(rank["strategy_id"]): rank for rank in catalog_slate["ranks"]
    }
    book_metrics = [
        _book_metric(
            source_ordinal=source_ordinal,
            book=book,
            rank=ranks[str(book["strategy_id"])],
            union_score_rows=score_rows,
            score_by_lineup=score_by_lineup,
            corpus_ceiling=ceiling,
        )
        for book in catalog_slate["books"]
    ]
    body = {
        "schema_version": SLATE_GRADE_SCHEMA,
        "source_ordinal": source_ordinal,
        "slate": dict(catalog_slate["slate"]),
        "slate_catalog_sha256": catalog_slate["slate_catalog_sha256"],
        "union_population_sha256": union["population_sha256"],
        "union_roster_sum_operation_count": len(score_rows),
        "union_score_rows": score_rows,
        "union_score_map_sha256": canonical_sha256(score_rows),
        "union_metrics": union_metrics,
        "book_grade_count": len(book_metrics),
        "book_grades": book_metrics,
        "every_unique_union_roster_scored_once": True,
        "every_book_projected_without_roster_rescore": True,
        "every_book_projection_independently_replayed": True,
    }
    return _self_hash(body, "slate_grade_sha256"), len(score_rows)


def _threshold_metric_map(
    value: Sequence[Mapping[str, object]],
) -> dict[int, Mapping[str, object]]:
    return {int(row["threshold_micro"]): row for row in value}


def _contrast_row(
    *,
    contrast: Mapping[str, object],
    budget: int,
    slate_grade: Mapping[str, object],
    book_lookup: Mapping[tuple[str, int], Mapping[str, object]],
) -> dict[str, object]:
    challenger = book_lookup[(str(contrast["challenger_strategy_id"]), budget)]
    comparator = book_lookup[(str(contrast["comparator_strategy_id"]), budget)]
    challenger_thresholds = _threshold_metric_map(challenger["thresholds"])
    comparator_thresholds = _threshold_metric_map(comparator["thresholds"])
    threshold_deltas = []
    for threshold_dk in catalog_contract.THRESHOLDS_DK:
        threshold_micro = threshold_dk * MICRO_DK_PER_POINT
        left = challenger_thresholds[threshold_micro]
        right = comparator_thresholds[threshold_micro]
        threshold_deltas.append({
            "threshold_dk": threshold_dk,
            "threshold_micro": threshold_micro,
            "at_or_above_count_delta": (
                int(left["at_or_above_count"]) - int(right["at_or_above_count"])
            ),
            "at_least_one_hit_conversion_delta": (
                int(bool(left["produced_at_least_one_hit"]))
                - int(bool(right["produced_at_least_one_hit"]))
            ),
        })
    max_delta = int(challenger["maximum_micro"]) - int(comparator["maximum_micro"])
    mean_delta = (
        int(challenger["mean"]["numerator"])
        - int(comparator["mean"]["numerator"])
    )
    slate = slate_grade["slate"]
    body = {
        "schema_version": CONTRAST_ROW_SCHEMA,
        "contrast_id": contrast["contrast_id"],
        "contrast_sha256": contrast["contrast_sha256"],
        "family": contrast["family"],
        "source_ordinal": slate_grade["source_ordinal"],
        "season": slate["season"],
        "week": slate["week"],
        "slate_id": slate["slate_id"],
        "entry_budget": budget,
        "challenger_strategy_id": contrast["challenger_strategy_id"],
        "comparator_strategy_id": contrast["comparator_strategy_id"],
        "challenger_book_grade_sha256": challenger["book_grade_sha256"],
        "comparator_book_grade_sha256": comparator["book_grade_sha256"],
        "challenger_maximum_micro": challenger["maximum_micro"],
        "comparator_maximum_micro": comparator["maximum_micro"],
        "weekly_maximum_delta_micro": max_delta,
        "weekly_mean_delta": _rational(mean_delta, budget, unit="micro_dk"),
        "corpus_ceiling_gap_improvement_micro": max_delta,
        "threshold_deltas": threshold_deltas,
        "direction": "challenger-minus-comparator",
        "evidence_class": catalog_contract.EVIDENCE_CLASS,
    }
    return _self_hash(body, "contrast_row_sha256")


def _delta_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    if not rows:
        _fail("contrast sensitivity summary cannot be empty")
    deltas = [int(row["weekly_maximum_delta_micro"]) for row in rows]
    threshold_sums = {
        threshold_dk: {"count_delta_sum": 0, "hit_conversion_delta_sum": 0}
        for threshold_dk in catalog_contract.THRESHOLDS_DK
    }
    for row in rows:
        for threshold in row["threshold_deltas"]:
            retained = threshold_sums[int(threshold["threshold_dk"])]
            retained["count_delta_sum"] += int(threshold["at_or_above_count_delta"])
            retained["hit_conversion_delta_sum"] += int(
                threshold["at_least_one_hit_conversion_delta"]
            )
    return {
        "slate_count": len(rows),
        "weekly_maximum_delta_mean": _mean(deltas),
        "weekly_maximum_delta_sum_micro": sum(deltas),
        "challenger_better_slate_count": sum(value > 0 for value in deltas),
        "exact_tie_slate_count": sum(value == 0 for value in deltas),
        "challenger_worse_slate_count": sum(value < 0 for value in deltas),
        "threshold_delta_sums": [
            {"threshold_dk": threshold_dk, **threshold_sums[threshold_dk]}
            for threshold_dk in catalog_contract.THRESHOLDS_DK
        ],
    }


def _contrast_summary(
    *,
    contrast: Mapping[str, object],
    budget: int,
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    seasons = sorted({int(row["season"]) for row in rows})
    by_season = [
        {"season": season, **_delta_summary([
            row for row in rows if row["season"] == season
        ])}
        for season in seasons
    ]
    leave_one_slate = [
        {
            "omitted_source_ordinal": row["source_ordinal"],
            **_delta_summary([
                candidate
                for candidate in rows
                if candidate["source_ordinal"] != row["source_ordinal"]
            ]),
        }
        for row in rows
    ]
    leave_one_season = [
        {
            "omitted_season": season,
            **_delta_summary([row for row in rows if row["season"] != season]),
        }
        for season in seasons
    ]
    multiplicity = {
        "primary-headline": "five-prespecified-t230-method-family",
        "mandatory-secondary-fill-arm": "mandatory-secondary-source-arm-family",
        "support-switch-mechanism": "four-prespecified-raw-law-family",
        "source-arm-diagnostic": "six-prespecified-source-arm-family",
    }[str(contrast["family"])]
    body = {
        "schema_version": CONTRAST_SUMMARY_SCHEMA,
        "contrast_id": contrast["contrast_id"],
        "contrast_sha256": contrast["contrast_sha256"],
        "family": contrast["family"],
        "entry_budget": budget,
        "challenger_strategy_id": contrast["challenger_strategy_id"],
        "comparator_strategy_id": contrast["comparator_strategy_id"],
        "weekly_contrast_row_count": len(rows),
        "weekly_contrast_rows_sha256": canonical_sha256([
            row["contrast_row_sha256"] for row in rows
        ]),
        "overall": _delta_summary(rows),
        "season_summaries": by_season,
        "leave_one_slate_sensitivity": leave_one_slate,
        "leave_one_season_sensitivity": leave_one_season,
        "multiplicity_label": multiplicity,
        "evidence_class": catalog_contract.EVIDENCE_CLASS,
        "report_regardless_of_sign": True,
    }
    return _self_hash(body, "contrast_summary_sha256")


def grade_core_v1_catalog(
    *,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    outcome_snapshot: Mapping[str, object],
    outcome_snapshot_identity: Mapping[str, object],
    player_source: Mapping[str, object],
    player_source_identity: Mapping[str, object],
    outcome_keys: Sequence[outcome_contract.CoreOutcomeKey],
    contest_outcomes: object | None = None,
) -> dict[str, object]:
    """Score every shared-union roster once and project all frozen books."""
    if contest_outcomes is not None:
        _fail(
            "contest rank/ROI requires a separately validated full-field, "
            "tie-settlement, duplicate-entry and payout-ladder contract"
        )
    try:
        retained_catalog = catalog_contract.validate_core_v1_catalog(catalog)
    except catalog_contract.CorpusCoreV1CatalogError as exc:
        raise CorpusCatalogRealizedGradingError(str(exc)) from exc
    retained_catalog_identity = _json_identity(
        retained_catalog, catalog_identity, label="Core v1 catalog identity"
    )
    try:
        snapshot, retained_snapshot_identity, player_scores = (
            outcome_contract.validate_core_outcome_snapshot(
                outcome_snapshot,
                identity=outcome_snapshot_identity,
                catalog=retained_catalog,
                catalog_identity=catalog_identity,
                player_source=player_source,
                player_source_identity=player_source_identity,
                outcome_keys=outcome_keys,
            )
        )
    except outcome_contract.CorpusCoreV1OutcomeSnapshotError as exc:
        raise CorpusCatalogRealizedGradingError(str(exc)) from exc
    required_player_keys = {
        (int(slate["source_ordinal"]), str(player))
        for slate in retained_catalog["slates"]
        for roster in slate["union_population"]["rosters"]
        for player in roster
    }
    if set(player_scores) != required_player_keys:
        _fail(
            "outcome snapshot keys do not exactly equal the complete Core v1 "
            "slate/player union"
        )
    slate_grades: list[dict[str, object]] = []
    score_operation_count = 0
    for catalog_slate in retained_catalog["slates"]:
        slate_grade, operation_count = _build_slate_grade(
            catalog_slate=catalog_slate, player_scores=player_scores
        )
        slate_grades.append(slate_grade)
        score_operation_count += operation_count

    book_lookup_by_slate: dict[
        int, dict[tuple[str, int], Mapping[str, object]]
    ] = {}
    for slate_grade in slate_grades:
        lookup = {
            (str(row["strategy_id"]), int(row["entry_budget"])): row
            for row in slate_grade["book_grades"]
        }
        if len(lookup) != catalog_contract.EXPECTED_STRATEGY_COUNT * 3:
            raise AssertionError("book-grade lookup lost a validated cell")
        book_lookup_by_slate[int(slate_grade["source_ordinal"])] = lookup
    weekly_contrasts: list[dict[str, object]] = []
    contrast_summaries: list[dict[str, object]] = []
    for contrast in retained_catalog["contrast_registry"]:
        for budget in catalog_contract.EXPECTED_BOOK_BUDGETS:
            rows = [
                _contrast_row(
                    contrast=contrast,
                    budget=budget,
                    slate_grade=slate_grade,
                    book_lookup=book_lookup_by_slate[
                        int(slate_grade["source_ordinal"])
                    ],
                )
                for slate_grade in slate_grades
            ]
            weekly_contrasts.extend(rows)
            contrast_summaries.append(_contrast_summary(
                contrast=contrast, budget=budget, rows=rows
            ))
    expected_union_count = sum(
        int(slate["union_population"]["lineup_count"])
        for slate in retained_catalog["slates"]
    )
    coverage = {
        "source_slate_count": len(slate_grades),
        "strategy_count": retained_catalog["strategy_count"],
        "entry_budget_count": len(catalog_contract.EXPECTED_BOOK_BUDGETS),
        "book_cell_count": sum(
            int(slate["book_grade_count"]) for slate in slate_grades
        ),
        "contrast_definition_count": retained_catalog["contrast_count"],
        "weekly_contrast_cell_count": len(weekly_contrasts),
        "contrast_summary_count": len(contrast_summaries),
        "unique_union_roster_membership_count": expected_union_count,
        "union_roster_sum_operation_count": score_operation_count,
        "actual_player_outcome_row_count": len(player_scores),
        "every_unique_union_roster_scored_exactly_once_per_slate": (
            score_operation_count == expected_union_count
        ),
        "every_book_projected_from_shared_score_map": True,
        "every_book_projection_independently_replayed": True,
        "all_registered_contrasts_reported_regardless_of_sign": True,
        "actual_player_outcome_keys_exact": True,
        "complete": True,
    }
    body = {
        "schema_version": RESULT_SCHEMA,
        "phase": "post-catalog-realized-historical",
        "evidence_class": catalog_contract.EVIDENCE_CLASS,
        "catalog_authority": {
            "catalog_identity": retained_catalog_identity,
            "catalog_sha256": retained_catalog["catalog_sha256"],
            "source_panel_identity": retained_catalog["source_panel_identity"],
            "t230_panel_release_identity": retained_catalog[
                "t230_panel_release_identity"
            ],
            "strategy_registry_sha256": retained_catalog[
                "strategy_registry_sha256"
            ],
            "contrast_registry_sha256": retained_catalog[
                "contrast_registry_sha256"
            ],
        },
        "actual_player_outcome_authority": {
            "outcome_snapshot_identity": retained_snapshot_identity,
            "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
            "source_identity": snapshot["source_identity"],
            "row_count": snapshot["row_count"],
            "row_keys_sha256": snapshot["row_keys_sha256"],
            "rows_sha256": snapshot["rows_sha256"],
        },
        "score_unit": "micro_dk",
        "micro_dk_per_point": MICRO_DK_PER_POINT,
        "thresholds_micro": [
            value * MICRO_DK_PER_POINT for value in catalog_contract.THRESHOLDS_DK
        ],
        "coverage": coverage,
        "slate_grades": slate_grades,
        "weekly_contrasts": weekly_contrasts,
        "contrast_summaries": contrast_summaries,
        "contest_metrics": {
            "availability": "unavailable",
            "reason": "full_field_standings_and_payout_ladder_not_supplied",
            "full_field_standings_identity": None,
            "payout_ladder_identity": None,
            "rank": None,
            "roi_micro_usd": None,
        },
        "outcome_blind_catalog_mutated": False,
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    return validate_core_v1_realized_grade(_self_hash(body, "realized_grade_sha256"))


def validate_core_v1_realized_grade(value: object) -> dict[str, object]:
    """Validate the grade's score-once and complete-census evidence."""
    item = dict(_mapping(value, label="Core v1 realized grade"))
    _validate_self_hash(
        item, field="realized_grade_sha256", label="Core v1 realized grade"
    )
    coverage = _mapping(item.get("coverage"), label="grade coverage")
    slates = list(_sequence(item.get("slate_grades"), label="slate grades"))
    weekly = list(
        _sequence(item.get("weekly_contrasts"), label="weekly contrasts")
    )
    summaries = list(
        _sequence(item.get("contrast_summaries"), label="contrast summaries")
    )
    expected_weekly = (
        catalog_contract.EXPECTED_SOURCE_SLATE_COUNT * 45
        * len(catalog_contract.EXPECTED_BOOK_BUDGETS)
    )
    expected_summaries = 45 * len(catalog_contract.EXPECTED_BOOK_BUDGETS)
    if (
        item.get("schema_version") != RESULT_SCHEMA
        or item.get("phase") != "post-catalog-realized-historical"
        or item.get("evidence_class") != catalog_contract.EVIDENCE_CLASS
        or item.get("score_unit") != "micro_dk"
        or item.get("micro_dk_per_point") != MICRO_DK_PER_POINT
        or item.get("thresholds_micro")
        != [value * MICRO_DK_PER_POINT for value in catalog_contract.THRESHOLDS_DK]
        or len(slates) != catalog_contract.EXPECTED_SOURCE_SLATE_COUNT
        or len(weekly) != expected_weekly
        or len(summaries) != expected_summaries
        or coverage.get("book_cell_count")
        != catalog_contract.EXPECTED_BOOK_CELL_COUNT
        or coverage.get("weekly_contrast_cell_count") != expected_weekly
        or coverage.get("contrast_summary_count") != expected_summaries
        or coverage.get("union_roster_sum_operation_count")
        != coverage.get("unique_union_roster_membership_count")
        or coverage.get("every_unique_union_roster_scored_exactly_once_per_slate")
        is not True
        or coverage.get("every_book_projected_from_shared_score_map") is not True
        or coverage.get("every_book_projection_independently_replayed") is not True
        or coverage.get("all_registered_contrasts_reported_regardless_of_sign")
        is not True
        or coverage.get("actual_player_outcome_keys_exact") is not True
        or coverage.get("complete") is not True
        or item.get("contest_metrics") != {
            "availability": "unavailable",
            "reason": "full_field_standings_and_payout_ladder_not_supplied",
            "full_field_standings_identity": None,
            "payout_ladder_identity": None,
            "rank": None,
            "roi_micro_usd": None,
        }
        or item.get("outcome_blind_catalog_mutated") is not False
        or item.get("uses_realized_outcomes") is not True
        or any(item.get(field) is not False for field in (
            "historical_retune_licensed",
            "historical_retry_licensed",
            "graph_mutation_licensed",
            "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("Core v1 realized grade root law differs")
    observed_operations = 0
    observed_books = 0
    for source_ordinal, slate_raw in enumerate(slates):
        slate = _mapping(slate_raw, label=f"slate grade[{source_ordinal}]")
        _validate_self_hash(slate, field="slate_grade_sha256", label="slate grade")
        books = list(_sequence(slate.get("book_grades"), label="book grades"))
        score_rows = list(
            _sequence(slate.get("union_score_rows"), label="union score rows")
        )
        if (
            slate.get("schema_version") != SLATE_GRADE_SCHEMA
            or slate.get("source_ordinal") != source_ordinal
            or slate.get("union_roster_sum_operation_count") != len(score_rows)
            or slate.get("union_score_map_sha256") != canonical_sha256(score_rows)
            or slate.get("book_grade_count")
            != catalog_contract.EXPECTED_STRATEGY_COUNT * 3
            or len(books) != catalog_contract.EXPECTED_STRATEGY_COUNT * 3
            or slate.get("every_unique_union_roster_scored_once") is not True
            or slate.get("every_book_projected_without_roster_rescore") is not True
            or slate.get("every_book_projection_independently_replayed") is not True
        ):
            _fail("Core v1 realized slate grade law differs")
        observed_operations += len(score_rows)
        observed_books += len(books)
        for book in books:
            _validate_self_hash(book, field="book_grade_sha256", label="book grade")
            rows = list(
                _sequence(
                    book.get("roster_score_rows_rank_order"),
                    label="book score rows",
                )
            )
            if (
                book.get("schema_version") != BOOK_GRADE_SCHEMA
                or book.get("entry_count") != book.get("entry_budget")
                or len(rows) != book.get("entry_budget")
                or book.get("rank_order_score_rows_sha256")
                != canonical_sha256(rows)
                or book.get("exact_prefix_consistency_verified") is not True
                or book.get("independent_score_map_projection_replayed") is not True
            ):
                _fail("Core v1 realized book grade law differs")
    if (
        observed_operations != coverage["union_roster_sum_operation_count"]
        or observed_books != coverage["book_cell_count"]
    ):
        _fail("Core v1 realized grade coverage totals differ")
    for row in weekly:
        _validate_self_hash(row, field="contrast_row_sha256", label="contrast row")
        if (
            row.get("schema_version") != CONTRAST_ROW_SCHEMA
            or row.get("direction") != "challenger-minus-comparator"
            or row.get("evidence_class") != catalog_contract.EVIDENCE_CLASS
        ):
            _fail("Core v1 weekly contrast row differs")
    for summary in summaries:
        _validate_self_hash(
            summary,
            field="contrast_summary_sha256",
            label="contrast summary",
        )
        if (
            summary.get("schema_version") != CONTRAST_SUMMARY_SCHEMA
            or summary.get("weekly_contrast_row_count")
            != catalog_contract.EXPECTED_SOURCE_SLATE_COUNT
            or summary.get("evidence_class") != catalog_contract.EVIDENCE_CLASS
            or summary.get("report_regardless_of_sign") is not True
        ):
            _fail("Core v1 contrast summary differs")
    return item


__all__ = [
    "BOOK_GRADE_SCHEMA",
    "CONTRAST_ROW_SCHEMA",
    "CONTRAST_SUMMARY_SCHEMA",
    "CorpusCatalogRealizedGradingError",
    "OUTCOME_SNAPSHOT_SCHEMA",
    "RESULT_SCHEMA",
    "SLATE_GRADE_SCHEMA",
    "canonical_json_bytes",
    "canonical_sha256",
    "grade_core_v1_catalog",
    "validate_core_v1_realized_grade",
]
