#!/usr/bin/env python3
"""Read-only, exact-chain reporting for one completed Core v1 grade.

The cloud command is deliberately default-off.  It starts from the one known
grade-completion name, delegates its metadata-GET plus generation-pinned
predecessor/root/shard replay to :mod:`run_core_v1_grade_cloud`, and emits a
descriptive JSON or Markdown report to stdout.  It has no object-list,
publication, BigQuery, IAM, selector, graph, or process-mutation interface.

Authoritative arithmetic remains signed integer micro-DK or exact rational
numerator/denominator pairs.  Decimal strings are display aids only.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from decimal import Decimal, ROUND_HALF_UP, localcontext
from hashlib import sha256
import json
from math import gcd
import os
from pathlib import Path
import re
import sys
from typing import Final


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from nfl_dfs.research import corpus_catalog_realized_grading as grading  # noqa: E402
from nfl_dfs.research import corpus_core_v1_catalog as catalog  # noqa: E402
from nfl_dfs.research import corpus_core_v1_grade_publisher as publisher  # noqa: E402
from nfl_dfs.research import corpus_parametric_batch as batch  # noqa: E402
import run_core_v1_grade_cloud as grade_cloud  # noqa: E402


PROJECT: Final = grade_cloud.PROJECT
ENABLED_ENV: Final = "CORE_V1_GRADE_REPORT_ENABLED"
REPORT_SCHEMA: Final = "core-v1-human-readable-grade-report/v1"
REPORT_STATUS: Final = "CORE_V1_HISTORICAL_SCORE_REPORT_READY"
BASELINE_STRATEGY_ID: Final = "r194:incumbent"
T230_STRATEGY_IDS: Final = tuple(catalog.T230_STRATEGY_IDS)
SOURCE_STRATEGY_IDS: Final = tuple(catalog.SOURCE_STRATEGY_IDS)
ABSOLUTE_STRATEGY_IDS: Final = tuple(catalog.STRATEGY_IDS)
HEADLINE_STRATEGY_IDS: Final = (BASELINE_STRATEGY_ID, *T230_STRATEGY_IDS)
_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_FALSE_LICENSE_FIELDS: Final = (
    "historical_retune_licensed",
    "historical_retry_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
)


class CoreV1GradeReportError(RuntimeError):
    """The read-only Core v1 score report failed closed."""


def _fail(message: str) -> None:
    raise CoreV1GradeReportError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_int(
    value: object, *, label: str, minimum: int | None = None,
) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        suffix = "" if minimum is None else f" >= {minimum}"
        _fail(f"{label} must be an exact integer{suffix}")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CoreV1GradeReportError(str(exc)) from exc


def _rational(
    numerator: int, denominator: int, *, unit: str,
) -> dict[str, object]:
    if type(numerator) is not int or type(denominator) is not int or denominator < 1:
        raise AssertionError("internal report rational differs")
    common = gcd(abs(numerator), denominator)
    return {
        "numerator": numerator // common,
        "denominator": denominator // common,
        "unit": unit,
    }


def _rational_value(value: object, *, label: str) -> tuple[int, int, str]:
    row = _mapping(value, label=label)
    numerator = _exact_int(row.get("numerator"), label=f"{label}.numerator")
    denominator = _exact_int(
        row.get("denominator"), label=f"{label}.denominator", minimum=1
    )
    unit = row.get("unit")
    if type(unit) is not str or not unit:
        _fail(f"{label}.unit differs")
    return numerator, denominator, unit


def _same_rational(
    value: object, *, numerator: int, denominator: int, unit: str, label: str,
) -> None:
    retained_num, retained_den, retained_unit = _rational_value(value, label=label)
    if (
        retained_unit != unit
        or retained_num * denominator != numerator * retained_den
    ):
        _fail(f"{label} exact rational differs")


def _median(values: Sequence[int], *, unit: str) -> dict[str, object]:
    if not values:
        _fail("report median requires one nonempty population")
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return _rational(ordered[midpoint], 1, unit=unit)
    return _rational(
        ordered[midpoint - 1] + ordered[midpoint], 2, unit=unit
    )


def _decimal_display(numerator: int, denominator: int) -> str:
    with localcontext() as context:
        context.prec = 40
        value = Decimal(numerator) / Decimal(denominator) / Decimal(1_000_000)
        rounded = value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return f"{rounded:.3f}"


def _with_dk_display(value: Mapping[str, object]) -> dict[str, object]:
    numerator, denominator, unit = _rational_value(value, label="report rational")
    if unit != "micro_dk":
        _fail("DK display received a non-micro-DK rational")
    return {
        **dict(value),
        "dk_points_display": _decimal_display(numerator, denominator),
    }


def _micro_with_display(value: int) -> dict[str, object]:
    retained = _exact_int(value, label="report micro-DK value")
    return {
        "micro_dk": retained,
        "dk_points_display": _decimal_display(retained, 1),
    }


def _threshold_map(
    value: object, *, entry_count: int, scores: Sequence[int], label: str,
) -> dict[int, dict[str, object]]:
    rows = [
        _mapping(row, label=f"{label} threshold")
        for row in _sequence(value, label=f"{label} thresholds")
    ]
    expected = list(catalog.THRESHOLDS_DK)
    if [row.get("threshold_dk") for row in rows] != expected:
        _fail(f"{label} threshold lattice differs")
    result: dict[int, dict[str, object]] = {}
    for row in rows:
        threshold_dk = _exact_int(
            row.get("threshold_dk"), label=f"{label}.threshold_dk"
        )
        threshold_micro = threshold_dk * grading.MICRO_DK_PER_POINT
        hits = sum(score >= threshold_micro for score in scores)
        retained_hits = _exact_int(
            row.get("at_or_above_count"),
            label=f"{label}.at_or_above_count",
            minimum=0,
        )
        if (
            row.get("threshold_micro") != threshold_micro
            or retained_hits != hits
            or row.get("produced_at_least_one_hit") is not (hits > 0)
        ):
            _fail(f"{label} threshold metric differs")
        _same_rational(
            row.get("at_or_above_fraction"),
            numerator=hits,
            denominator=entry_count,
            unit="lineups",
            label=f"{label}.at_or_above_fraction",
        )
        result[threshold_dk] = dict(row)
    return result


def _book_week_row(
    *,
    slate_grade: Mapping[str, object],
    book: Mapping[str, object],
    shared_union_maximum_micro: int,
) -> tuple[dict[str, object], list[int], dict[int, dict[str, object]]]:
    source_ordinal = _exact_int(
        slate_grade.get("source_ordinal"), label="report source ordinal"
    )
    slate = _mapping(slate_grade.get("slate"), label="report slate")
    strategy_id = book.get("strategy_id")
    budget = _exact_int(book.get("entry_budget"), label="report entry budget")
    if (
        strategy_id not in ABSOLUTE_STRATEGY_IDS
        or budget not in catalog.EXPECTED_BOOK_BUDGETS
    ):
        _fail("report book key differs")
    score_rows = [
        _mapping(row, label="report roster score row")
        for row in _sequence(
            book.get("roster_score_rows_rank_order"), label="report score rows"
        )
    ]
    scores = [
        _exact_int(
            row.get("realized_score_micro"), label="report realized score"
        )
        for row in score_rows
    ]
    if len(scores) != budget or not scores:
        _fail("report book score-row census differs")
    maximum = max(scores)
    if book.get("maximum_micro") != maximum:
        _fail("report book maximum differs from its retained scores")
    _same_rational(
        book.get("mean"),
        numerator=sum(scores),
        denominator=budget,
        unit="micro_dk",
        label="report book mean",
    )
    expected_median = _median(scores, unit="micro_dk")
    _same_rational(
        book.get("median"),
        numerator=int(expected_median["numerator"]),
        denominator=int(expected_median["denominator"]),
        unit="micro_dk",
        label="report book median",
    )
    top_three = sorted(scores, reverse=True)[:3]
    _same_rational(
        book.get("top_three_mean"),
        numerator=sum(top_three),
        denominator=len(top_three),
        unit="micro_dk",
        label="report book top-three mean",
    )
    thresholds = _threshold_map(
        book.get("thresholds"),
        entry_count=budget,
        scores=scores,
        label="report book",
    )
    gap = _exact_int(
        book.get("gap_to_shared_corpus_ceiling_micro"),
        label="report corpus-ceiling gap",
        minimum=0,
    )
    if gap != shared_union_maximum_micro - maximum:
        _fail("report corpus-ceiling gap differs from union maximum minus book maximum")
    return ({
        "source_ordinal": source_ordinal,
        "season": slate.get("season"),
        "week": slate.get("week"),
        "slate_id": slate.get("slate_id"),
        "strategy_id": strategy_id,
        "entry_budget": budget,
        "maximum": _micro_with_display(maximum),
        "mean": _with_dk_display(_mapping(book["mean"], label="book mean")),
        "median": _with_dk_display(
            _mapping(book["median"], label="book median")
        ),
        "top_three_mean": _with_dk_display(
            _mapping(book["top_three_mean"], label="book top-three mean")
        ),
        "gap_to_shared_corpus_ceiling": _micro_with_display(gap),
        "thresholds": [
            {
                "threshold_dk": threshold_dk,
                "selected_lineup_hit_count": thresholds[threshold_dk][
                    "at_or_above_count"
                ],
                "produced_at_least_one_hit": thresholds[threshold_dk][
                    "produced_at_least_one_hit"
                ],
            }
            for threshold_dk in catalog.THRESHOLDS_DK
        ],
    }, scores, thresholds)


def _absolute_summary(
    *, strategy_id: str, budget: int,
    retained: Sequence[tuple[Mapping[str, object], Sequence[int], Mapping[int, Mapping[str, object]]]],
) -> dict[str, object]:
    if len(retained) != catalog.EXPECTED_SOURCE_SLATE_COUNT:
        _fail("report absolute strategy/slate census differs")
    weekly = [row[0] for row in retained]
    all_scores = [score for _, scores, _ in retained for score in scores]
    maxima = [int(row["maximum"]["micro_dk"]) for row in weekly]
    gaps = [
        int(row["gap_to_shared_corpus_ceiling"]["micro_dk"])
        for row in weekly
    ]
    weekly_mean = _rational(
        sum(maxima), len(maxima), unit="micro_dk"
    )
    selected_mean = _rational(
        sum(all_scores), len(all_scores), unit="micro_dk"
    )
    gap_mean = _rational(sum(gaps), len(gaps), unit="micro_dk")
    thresholds = []
    for threshold_dk in catalog.THRESHOLDS_DK:
        hits = sum(
            int(threshold_map[threshold_dk]["at_or_above_count"])
            for _, _, threshold_map in retained
        )
        slate_hits = sum(
            bool(threshold_map[threshold_dk]["produced_at_least_one_hit"])
            for _, _, threshold_map in retained
        )
        thresholds.append({
            "threshold_dk": threshold_dk,
            "selected_lineup_hit_count": hits,
            "selected_lineup_hit_fraction": _rational(
                hits, len(all_scores), unit="lineups"
            ),
            "slates_with_at_least_one_hit": slate_hits,
            "slate_hit_fraction": _rational(
                slate_hits, len(retained), unit="slates"
            ),
        })
    return {
        "strategy_id": strategy_id,
        "entry_budget": budget,
        "slate_count": len(retained),
        "selected_lineup_membership_count": len(all_scores),
        "overall_best_score": _micro_with_display(max(maxima)),
        "weekly_maximum_mean": _with_dk_display(weekly_mean),
        "weekly_maximum_median": _with_dk_display(
            _median(maxima, unit="micro_dk")
        ),
        "selected_lineup_score_mean": _with_dk_display(selected_mean),
        "weekly_union_ceiling_gap_mean": _with_dk_display(gap_mean),
        "thresholds": thresholds,
    }


def _replay_delta_summary(
    rows: Sequence[Mapping[str, object]], *, label: str,
) -> dict[str, object]:
    if not rows:
        _fail(f"{label} cannot be empty")
    deltas = [
        _exact_int(
            row.get("weekly_maximum_delta_micro"),
            label=f"{label} weekly maximum delta",
        )
        for row in rows
    ]
    threshold_sums = {
        threshold_dk: {"count_delta_sum": 0, "hit_conversion_delta_sum": 0}
        for threshold_dk in catalog.THRESHOLDS_DK
    }
    for row in rows:
        threshold_rows = [
            _mapping(item, label=f"{label} weekly threshold delta")
            for item in _sequence(
                row.get("threshold_deltas"),
                label=f"{label} weekly threshold deltas",
            )
        ]
        if [item.get("threshold_dk") for item in threshold_rows] != list(
            catalog.THRESHOLDS_DK
        ):
            _fail(f"{label} weekly threshold lattice differs")
        for item in threshold_rows:
            threshold_dk = int(item["threshold_dk"])
            threshold_sums[threshold_dk]["count_delta_sum"] += _exact_int(
                item.get("at_or_above_count_delta"),
                label=f"{label} threshold count delta",
            )
            threshold_sums[threshold_dk][
                "hit_conversion_delta_sum"
            ] += _exact_int(
                item.get("at_least_one_hit_conversion_delta"),
                label=f"{label} hit-conversion delta",
            )
    return {
        "slate_count": len(rows),
        "weekly_maximum_delta_mean": _rational(
            sum(deltas), len(deltas), unit="micro_dk"
        ),
        "weekly_maximum_delta_sum_micro": sum(deltas),
        "challenger_better_slate_count": sum(value > 0 for value in deltas),
        "exact_tie_slate_count": sum(value == 0 for value in deltas),
        "challenger_worse_slate_count": sum(value < 0 for value in deltas),
        "threshold_delta_sums": [
            {"threshold_dk": threshold_dk, **threshold_sums[threshold_dk]}
            for threshold_dk in catalog.THRESHOLDS_DK
        ],
    }


def _require_delta_summary(
    value: object,
    *,
    rows: Sequence[Mapping[str, object]],
    label: str,
) -> Mapping[str, object]:
    row = _mapping(value, label=label)
    replayed = _replay_delta_summary(rows, label=label)
    for field in (
        "slate_count",
        "weekly_maximum_delta_sum_micro",
        "challenger_better_slate_count",
        "exact_tie_slate_count",
        "challenger_worse_slate_count",
        "threshold_delta_sums",
    ):
        if row.get(field) != replayed[field]:
            _fail(f"{label}.{field} differs from its weekly replay")
    expected_mean = _mapping(
        replayed["weekly_maximum_delta_mean"],
        label=f"{label} expected weekly max mean",
    )
    _same_rational(
        row.get("weekly_maximum_delta_mean"),
        numerator=int(expected_mean["numerator"]),
        denominator=int(expected_mean["denominator"]),
        unit="micro_dk",
        label=f"{label} weekly maximum delta mean",
    )
    return row


def _delta_summary_projection(value: object, *, label: str) -> dict[str, object]:
    row = _mapping(value, label=label)
    mean = _mapping(
        row.get("weekly_maximum_delta_mean"), label=f"{label} weekly max mean"
    )
    return {
        "slate_count": row.get("slate_count"),
        "weekly_maximum_delta_mean": _with_dk_display(mean),
        "weekly_maximum_delta_sum": _micro_with_display(
            _exact_int(
                row.get("weekly_maximum_delta_sum_micro"),
                label=f"{label} weekly maximum delta sum",
            )
        ),
        "challenger_better_slate_count": row.get(
            "challenger_better_slate_count"
        ),
        "exact_tie_slate_count": row.get("exact_tie_slate_count"),
        "challenger_worse_slate_count": row.get(
            "challenger_worse_slate_count"
        ),
        "threshold_delta_sums": [
            dict(_mapping(item, label=f"{label} threshold delta"))
            for item in _sequence(
                row.get("threshold_delta_sums"),
                label=f"{label} threshold delta sums",
            )
        ],
    }


def _primary_paired_rows(
    *, grade: Mapping[str, object],
    books_by_key: Mapping[tuple[int, str, int], tuple[Mapping[str, object], Sequence[int], Mapping[int, Mapping[str, object]]]],
    absolute_by_key: Mapping[tuple[str, int], Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    weekly_source = [
        _mapping(row, label="report weekly contrast")
        for row in _sequence(
            grade.get("weekly_contrasts"), label="report weekly contrasts"
        )
        if _mapping(row, label="report weekly contrast").get("family")
        == "primary-headline"
    ]
    weekly_by_key: dict[tuple[str, int, int], Mapping[str, object]] = {}
    weekly_output: list[dict[str, object]] = []
    for row in weekly_source:
        challenger = row.get("challenger_strategy_id")
        comparator = row.get("comparator_strategy_id")
        budget = _exact_int(row.get("entry_budget"), label="paired budget")
        source_ordinal = _exact_int(
            row.get("source_ordinal"), label="paired source ordinal"
        )
        if challenger not in T230_STRATEGY_IDS or comparator != BASELINE_STRATEGY_ID:
            _fail("primary paired strategy law differs")
        key = (str(challenger), budget, source_ordinal)
        if key in weekly_by_key:
            _fail("primary paired weekly key repeats")
        challenger_book = books_by_key[(source_ordinal, str(challenger), budget)]
        baseline_book = books_by_key[
            (source_ordinal, BASELINE_STRATEGY_ID, budget)
        ]
        challenger_week, challenger_scores, challenger_thresholds = challenger_book
        baseline_week, baseline_scores, baseline_thresholds = baseline_book
        if any(
            row.get(field) != challenger_week.get(field)
            or row.get(field) != baseline_week.get(field)
            for field in ("season", "week", "slate_id")
        ):
            _fail("primary paired weekly slate label differs from its books")
        challenger_max = int(challenger_week["maximum"]["micro_dk"])
        baseline_max = int(baseline_week["maximum"]["micro_dk"])
        delta = challenger_max - baseline_max
        if (
            row.get("challenger_maximum_micro") != challenger_max
            or row.get("comparator_maximum_micro") != baseline_max
            or row.get("weekly_maximum_delta_micro") != delta
            or row.get("corpus_ceiling_gap_improvement_micro") != delta
        ):
            _fail("primary paired weekly maximum differs")
        _same_rational(
            row.get("weekly_mean_delta"),
            numerator=sum(challenger_scores) - sum(baseline_scores),
            denominator=budget,
            unit="micro_dk",
            label="primary paired weekly mean delta",
        )
        threshold_deltas = [
            _mapping(item, label="paired weekly threshold delta")
            for item in _sequence(
                row.get("threshold_deltas"), label="paired threshold deltas"
            )
        ]
        if [item.get("threshold_dk") for item in threshold_deltas] != list(
            catalog.THRESHOLDS_DK
        ):
            _fail("primary paired threshold lattice differs")
        for item in threshold_deltas:
            threshold_dk = int(item["threshold_dk"])
            left = challenger_thresholds[threshold_dk]
            right = baseline_thresholds[threshold_dk]
            expected_count = int(left["at_or_above_count"]) - int(
                right["at_or_above_count"]
            )
            expected_conversion = int(bool(left["produced_at_least_one_hit"])) - int(
                bool(right["produced_at_least_one_hit"])
            )
            if (
                item.get("at_or_above_count_delta") != expected_count
                or item.get("at_least_one_hit_conversion_delta")
                != expected_conversion
            ):
                _fail("primary paired weekly threshold delta differs")
        weekly_by_key[key] = row
        weekly_output.append({
            "source_ordinal": source_ordinal,
            "season": row.get("season"),
            "week": row.get("week"),
            "slate_id": row.get("slate_id"),
            "challenger_strategy_id": challenger,
            "comparator_strategy_id": comparator,
            "entry_budget": budget,
            "challenger_maximum": _micro_with_display(challenger_max),
            "comparator_maximum": _micro_with_display(baseline_max),
            "weekly_maximum_delta": _micro_with_display(delta),
            "weekly_mean_delta": _with_dk_display(
                _mapping(row["weekly_mean_delta"], label="weekly mean delta")
            ),
            "threshold_deltas": [dict(item) for item in threshold_deltas],
        })

    expected_weekly_keys = {
        (strategy_id, budget, source_ordinal)
        for strategy_id in T230_STRATEGY_IDS
        for budget in catalog.EXPECTED_BOOK_BUDGETS
        for source_ordinal in range(catalog.EXPECTED_SOURCE_SLATE_COUNT)
    }
    if set(weekly_by_key) != expected_weekly_keys:
        _fail("primary paired 5-by-3-by-54 weekly census differs")

    summaries = [
        _mapping(row, label="report contrast summary")
        for row in _sequence(
            grade.get("contrast_summaries"), label="report contrast summaries"
        )
        if _mapping(row, label="report contrast summary").get("family")
        == "primary-headline"
    ]
    summary_output: list[dict[str, object]] = []
    observed: set[tuple[str, int]] = set()
    for summary in summaries:
        challenger = summary.get("challenger_strategy_id")
        comparator = summary.get("comparator_strategy_id")
        budget = _exact_int(summary.get("entry_budget"), label="summary budget")
        key = (str(challenger), budget)
        if (
            challenger not in T230_STRATEGY_IDS
            or comparator != BASELINE_STRATEGY_ID
            or key in observed
        ):
            _fail("primary paired summary key differs")
        rows = [
            weekly_by_key[(str(challenger), budget, source_ordinal)]
            for source_ordinal in range(catalog.EXPECTED_SOURCE_SLATE_COUNT)
        ]
        overall = _require_delta_summary(
            summary.get("overall"), rows=rows, label="paired overall"
        )
        expected_thresholds = []
        challenger_absolute = absolute_by_key[(str(challenger), budget)]
        baseline_absolute = absolute_by_key[(BASELINE_STRATEGY_ID, budget)]
        challenger_abs_thresholds = {
            int(row["threshold_dk"]): row
            for row in challenger_absolute["thresholds"]
        }
        baseline_abs_thresholds = {
            int(row["threshold_dk"]): row
            for row in baseline_absolute["thresholds"]
        }
        for threshold_dk in catalog.THRESHOLDS_DK:
            left = challenger_abs_thresholds[threshold_dk]
            right = baseline_abs_thresholds[threshold_dk]
            expected_thresholds.append({
                "threshold_dk": threshold_dk,
                "count_delta_sum": int(left["selected_lineup_hit_count"])
                - int(right["selected_lineup_hit_count"]),
                "hit_conversion_delta_sum": int(
                    left["slates_with_at_least_one_hit"]
                ) - int(right["slates_with_at_least_one_hit"]),
            })
        if overall.get("threshold_delta_sums") != expected_thresholds:
            _fail("primary paired overall summary differs from absolute books")

        seasons = sorted({int(row["season"]) for row in rows})
        season_rows = [
            _mapping(raw, label="paired season summary")
            for raw in _sequence(
                summary.get("season_summaries"),
                label="paired season summaries",
            )
        ]
        if [row.get("season") for row in season_rows] != seasons:
            _fail("paired season-summary census differs")
        validated_seasons = [
            _require_delta_summary(
                row,
                rows=[candidate for candidate in rows if candidate["season"] == season],
                label=f"paired season {season}",
            )
            for season, row in zip(seasons, season_rows, strict=True)
        ]

        leave_one_slate = [
            _mapping(raw, label="leave-one-slate row")
            for raw in _sequence(
                summary.get("leave_one_slate_sensitivity"),
                label="leave-one-slate sensitivity",
            )
        ]
        if [row.get("omitted_source_ordinal") for row in leave_one_slate] != list(
            range(catalog.EXPECTED_SOURCE_SLATE_COUNT)
        ):
            _fail("leave-one-slate sensitivity census differs")
        validated_leave_one_slate = [
            _require_delta_summary(
                row,
                rows=[
                    candidate
                    for candidate in rows
                    if candidate["source_ordinal"] != source_ordinal
                ],
                label=f"leave-one-slate {source_ordinal}",
            )
            for source_ordinal, row in enumerate(leave_one_slate)
        ]

        leave_one_season = [
            _mapping(raw, label="leave-one-season row")
            for raw in _sequence(
                summary.get("leave_one_season_sensitivity"),
                label="leave-one-season sensitivity",
            )
        ]
        if [row.get("omitted_season") for row in leave_one_season] != seasons:
            _fail("leave-one-season sensitivity census differs")
        validated_leave_one_season = [
            _require_delta_summary(
                row,
                rows=[candidate for candidate in rows if candidate["season"] != season],
                label=f"leave-one-season {season}",
            )
            for season, row in zip(seasons, leave_one_season, strict=True)
        ]
        observed.add(key)
        summary_output.append({
            "contrast_id": summary.get("contrast_id"),
            "challenger_strategy_id": challenger,
            "comparator_strategy_id": comparator,
            "entry_budget": budget,
            "overall": _delta_summary_projection(
                overall, label="paired overall"
            ),
            "season_summaries": [
                {
                    "season": row.get("season"),
                    **_delta_summary_projection(row, label="paired season"),
                }
                for row in validated_seasons
            ],
            "leave_one_slate_sensitivity": [
                {
                    "omitted_source_ordinal": row.get(
                        "omitted_source_ordinal"
                    ),
                    **_delta_summary_projection(row, label="leave-one-slate"),
                }
                for row in validated_leave_one_slate
            ],
            "leave_one_season_sensitivity": [
                {
                    "omitted_season": row.get("omitted_season"),
                    **_delta_summary_projection(row, label="leave-one-season"),
                }
                for row in validated_leave_one_season
            ],
            "multiplicity_label": summary.get("multiplicity_label"),
            "evidence_class": summary.get("evidence_class"),
            "report_regardless_of_sign": summary.get(
                "report_regardless_of_sign"
            ),
        })
    expected_summary_keys = {
        (strategy_id, budget)
        for strategy_id in T230_STRATEGY_IDS
        for budget in catalog.EXPECTED_BOOK_BUDGETS
    }
    if observed != expected_summary_keys:
        _fail("primary paired 5-by-3 summary census differs")
    weekly_output.sort(
        key=lambda row: (
            int(row["source_ordinal"]),
            str(row["challenger_strategy_id"]),
            int(row["entry_budget"]),
        )
    )
    summary_output.sort(
        key=lambda row: (
            int(row["entry_budget"]), str(row["challenger_strategy_id"])
        )
    )
    return weekly_output, summary_output


def _completion_binding(
    *, grade_run_id: str, completion: Mapping[str, object],
    completion_identity: Mapping[str, object], grade: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    retained_identity = _identity(
        completion_identity, label="report grade-completion identity"
    )
    expected_prefix = grade_cloud.grade_output_prefix(grade_run_id)
    if retained_identity["uri"] != expected_prefix + grade_cloud.GRADE_COMPLETION_FILENAME:
        _fail("report grade-completion URI differs from its known-name law")
    retained_hash = completion.get("grade_completion_sha256")
    body = {
        key: item
        for key, item in completion.items()
        if key != "grade_completion_sha256"
    }
    if retained_hash != publisher.canonical_sha256(body):
        _fail("report grade completion self-hash differs")
    root_identity = _identity(
        completion.get("grade_root_identity"), label="report grade-root identity"
    )
    if (
        completion.get("grade_run_id") != grade_run_id
        or root_identity["uri"] != expected_prefix + publisher.ROOT_FILENAME
        or completion.get("realized_grade_sha256")
        != grade.get("realized_grade_sha256")
        or completion.get("catalog_sha256")
        != _mapping(
            grade.get("catalog_authority"), label="report catalog authority"
        ).get("catalog_sha256")
        or completion.get("outcome_snapshot_sha256")
        != _mapping(
            grade.get("actual_player_outcome_authority"),
            label="report outcome authority",
        ).get("outcome_snapshot_sha256")
        or completion.get("slate_grade_shard_count")
        != catalog.EXPECTED_SOURCE_SLATE_COUNT
        or completion.get("one_historical_outcome_read") is not True
        or completion.get("uses_realized_outcomes") is not True
        or any(completion.get(field) is not False for field in _FALSE_LICENSE_FIELDS)
    ):
        _fail("report grade completion binding differs")
    return retained_identity, root_identity


def build_core_v1_grade_report(
    *, grade_run_id: str, completion: Mapping[str, object],
    completion_identity: Mapping[str, object], realized_grade: Mapping[str, object],
) -> dict[str, object]:
    """Build one descriptive report from a fully exact-reopened grade chain."""
    if type(grade_run_id) is not str or _RUN_ID.fullmatch(grade_run_id) is None:
        _fail("report grade run ID differs")
    try:
        grade = grading.validate_core_v1_realized_grade(realized_grade)
    except grading.CorpusCatalogRealizedGradingError as exc:
        raise CoreV1GradeReportError(str(exc)) from exc
    retained_completion = dict(_mapping(completion, label="report completion"))
    retained_completion_identity, root_identity = _completion_binding(
        grade_run_id=grade_run_id,
        completion=retained_completion,
        completion_identity=completion_identity,
        grade=grade,
    )
    contest_metrics = dict(
        _mapping(grade.get("contest_metrics"), label="report contest metrics")
    )
    if contest_metrics != {
        "availability": "unavailable",
        "reason": "full_field_standings_and_payout_ladder_not_supplied",
        "full_field_standings_identity": None,
        "payout_ladder_identity": None,
        "rank": None,
        "roi_micro_usd": None,
    }:
        _fail("report contest rank/ROI availability differs")

    weekly_rows: list[dict[str, object]] = []
    books_by_key: dict[
        tuple[int, str, int],
        tuple[Mapping[str, object], Sequence[int], Mapping[int, Mapping[str, object]]],
    ] = {}
    union_ceiling_rows: list[dict[str, object]] = []
    slate_grades = [
        _mapping(row, label="report slate grade")
        for row in _sequence(grade.get("slate_grades"), label="report slates")
    ]
    if len(slate_grades) != catalog.EXPECTED_SOURCE_SLATE_COUNT:
        _fail("report source-slate census differs")
    for expected_ordinal, slate_grade in enumerate(slate_grades):
        if slate_grade.get("source_ordinal") != expected_ordinal:
            _fail("report source-slate ordinal differs")
        union = _mapping(
            slate_grade.get("union_metrics"), label="report union metrics"
        )
        union_count = _exact_int(
            union.get("unique_union_roster_count"),
            label="report union roster count",
            minimum=1,
        )
        union_scores = []
        for raw_union_row in _sequence(
            slate_grade.get("union_score_rows"), label="report union rows"
        ):
            union_row = _mapping(raw_union_row, label="report union row")
            union_scores.append(_exact_int(
                union_row.get("realized_score_micro"),
                label="report union score",
            ))
        if len(union_scores) != union_count:
            _fail("report union score census differs")
        union_thresholds = _threshold_map(
            union.get("thresholds"),
            entry_count=union_count,
            scores=union_scores,
            label="report union",
        )
        union_maximum = max(union_scores)
        if union.get("maximum_micro") != union_maximum:
            _fail("report union maximum differs")
        slate = _mapping(slate_grade.get("slate"), label="report union slate")
        union_ceiling_rows.append({
            "source_ordinal": expected_ordinal,
            "season": slate.get("season"),
            "week": slate.get("week"),
            "slate_id": slate.get("slate_id"),
            "shared_union_roster_count": union_count,
            "shared_union_maximum": _micro_with_display(union_maximum),
            "thresholds": [
                {
                    "threshold_dk": threshold_dk,
                    "shared_union_lineup_hit_count": union_thresholds[
                        threshold_dk
                    ]["at_or_above_count"],
                }
                for threshold_dk in catalog.THRESHOLDS_DK
            ],
        })

        books = [
            _mapping(book, label="report book")
            for book in _sequence(
                slate_grade.get("book_grades"), label="report books"
            )
        ]
        if len(books) != len(ABSOLUTE_STRATEGY_IDS) * len(
            catalog.EXPECTED_BOOK_BUDGETS
        ):
            _fail("report complete 12-strategy book census differs")
        for book in books:
            key = (
                expected_ordinal,
                str(book["strategy_id"]),
                int(book["entry_budget"]),
            )
            if key in books_by_key:
                _fail("report book key repeats")
            retained = _book_week_row(
                slate_grade=slate_grade,
                book=book,
                shared_union_maximum_micro=union_maximum,
            )
            books_by_key[key] = retained
            weekly_rows.append(dict(retained[0]))

    expected_book_keys = {
        (source_ordinal, strategy_id, budget)
        for source_ordinal in range(catalog.EXPECTED_SOURCE_SLATE_COUNT)
        for strategy_id in ABSOLUTE_STRATEGY_IDS
        for budget in catalog.EXPECTED_BOOK_BUDGETS
    }
    if set(books_by_key) != expected_book_keys:
        _fail("report 54-by-12-by-3 book census differs")
    absolute_summaries: list[dict[str, object]] = []
    absolute_by_key: dict[tuple[str, int], Mapping[str, object]] = {}
    for budget in catalog.EXPECTED_BOOK_BUDGETS:
        for strategy_id in ABSOLUTE_STRATEGY_IDS:
            retained = [
                books_by_key[(source_ordinal, strategy_id, budget)]
                for source_ordinal in range(catalog.EXPECTED_SOURCE_SLATE_COUNT)
            ]
            summary = _absolute_summary(
                strategy_id=strategy_id, budget=budget, retained=retained
            )
            absolute_summaries.append(summary)
            absolute_by_key[(strategy_id, budget)] = summary

    weekly_paired, paired_summaries = _primary_paired_rows(
        grade=grade,
        books_by_key=books_by_key,
        absolute_by_key=absolute_by_key,
    )
    coverage = dict(_mapping(grade.get("coverage"), label="report coverage"))
    body = {
        "schema_version": REPORT_SCHEMA,
        "status": REPORT_STATUS,
        "grade_run_id": grade_run_id,
        "grade_completion_identity": retained_completion_identity,
        "grade_root_identity": root_identity,
        "realized_grade_sha256": grade["realized_grade_sha256"],
        "catalog_sha256": _mapping(
            grade["catalog_authority"], label="catalog authority"
        )["catalog_sha256"],
        "outcome_snapshot_sha256": _mapping(
            grade["actual_player_outcome_authority"], label="outcome authority"
        )["outcome_snapshot_sha256"],
        "score_unit": "micro_dk",
        "micro_dk_per_point": grading.MICRO_DK_PER_POINT,
        "baseline_strategy_id": BASELINE_STRATEGY_ID,
        "absolute_strategy_ids": list(ABSOLUTE_STRATEGY_IDS),
        "source_fill_strategy_ids": list(SOURCE_STRATEGY_IDS),
        "t230_strategy_ids": list(T230_STRATEGY_IDS),
        "entry_budgets": list(catalog.EXPECTED_BOOK_BUDGETS),
        "thresholds_dk": list(catalog.THRESHOLDS_DK),
        "coverage": coverage,
        "absolute_strategy_budget_summaries": absolute_summaries,
        "weekly_strategy_budget_rows": weekly_rows,
        "primary_paired_summaries": paired_summaries,
        "weekly_primary_contrasts": weekly_paired,
        "shared_union_ceiling_rows": union_ceiling_rows,
        "contest_metrics": contest_metrics,
        "limitations": [
            "contest_rank_unavailable_without_full_field_standings",
            "contest_roi_unavailable_without_payout_ladder_and_tie_settlement",
            "final_fit_books_only_cross_fit_books_excluded",
            "descriptive_historical_report_not_production_or_retune_authority",
            "threshold_187_not_prespecified_in_core_v1",
        ],
        "full_predecessor_root_and_shard_chain_exactly_reopened": True,
        "known_name_then_generation_pinned_reads_only": True,
        "object_listing_used": False,
        "one_historical_outcome_read_reused": True,
        "uses_realized_outcomes": True,
        **{field: False for field in _FALSE_LICENSE_FIELDS},
    }
    report = dict(body)
    report["report_sha256"] = sha256(
        publisher.canonical_json_bytes(body)
    ).hexdigest()
    return report


def _threshold(summary: Mapping[str, object], threshold_dk: int) -> Mapping[str, object]:
    for row in summary["thresholds"]:
        retained = _mapping(row, label="Markdown threshold")
        if retained.get("threshold_dk") == threshold_dk:
            return retained
    raise AssertionError("validated report lost one threshold")


def render_markdown(report: Mapping[str, object]) -> str:
    """Render a compact operator view; JSON retains the full weekly surface."""
    absolute = [
        _mapping(row, label="Markdown absolute summary")
        for row in report["absolute_strategy_budget_summaries"]
    ]
    paired = [
        _mapping(row, label="Markdown paired summary")
        for row in report["primary_paired_summaries"]
    ]
    lines = [
        "# Core v1 historical score report",
        "",
        f"Grade run: `{report['grade_run_id']}`",
        "",
        (
            "Contest rank and ROI are **unavailable**: Core v1 has no full-field "
            "standings, payout ladder, duplicate-entry, or tie-settlement contract."
        ),
        "",
        "All scores below are realized DraftKings points over 54 historical slates. "
        "Decimal displays are non-authoritative; exact micro-DK values remain in JSON.",
    ]
    for budget in catalog.EXPECTED_BOOK_BUDGETS:
        lines.extend([
            "",
            f"## Absolute results — {budget} entries",
            "",
            "| Strategy | Mean weekly max | Median weekly max | Best | >=194 hits/weeks | >=200 hits/weeks | >=210 hits/weeks | Mean gap to union ceiling |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in absolute:
            if (
                row["entry_budget"] != budget
                or row["strategy_id"] not in HEADLINE_STRATEGY_IDS
            ):
                continue
            threshold_cells = []
            for threshold_dk in (194, 200, 210):
                threshold = _threshold(row, threshold_dk)
                threshold_cells.append(
                    f"{threshold['selected_lineup_hit_count']}/"
                    f"{threshold['slates_with_at_least_one_hit']}"
                )
            lines.append(
                f"| `{row['strategy_id']}` | "
                f"{row['weekly_maximum_mean']['dk_points_display']} | "
                f"{row['weekly_maximum_median']['dk_points_display']} | "
                f"{row['overall_best_score']['dk_points_display']} | "
                f"{threshold_cells[0]} | {threshold_cells[1]} | "
                f"{threshold_cells[2]} | "
                f"{row['weekly_union_ceiling_gap_mean']['dk_points_display']} |"
            )
    lines.extend([
        "",
        "## T230 paired against `r194:incumbent`",
        "",
        "| Budget | T230 strategy | Mean weekly-max delta | Better / tie / worse slates | >=194 count/week delta | >=200 count/week delta | >=210 count/week delta |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ])
    for row in paired:
        overall = _mapping(row["overall"], label="Markdown paired overall")
        threshold_rows = {
            item["threshold_dk"]: item for item in overall["threshold_delta_sums"]
        }
        cells = [
            f"{threshold_rows[value]['count_delta_sum']:+d}/"
            f"{threshold_rows[value]['hit_conversion_delta_sum']:+d}"
            for value in (194, 200, 210)
        ]
        lines.append(
            f"| {row['entry_budget']} | `{row['challenger_strategy_id']}` | "
            f"{overall['weekly_maximum_delta_mean']['dk_points_display']} | "
            f"{overall['challenger_better_slate_count']} / "
            f"{overall['exact_tie_slate_count']} / "
            f"{overall['challenger_worse_slate_count']} | "
            f"{cells[0]} | {cells[1]} | {cells[2]} |"
        )
    lines.extend([
        "",
        "The JSON form also contains all 1,944 absolute weekly book rows across "
        "all 12 scenarios, all 810 "
        "primary paired weekly contrasts, season summaries, and leave-one-out "
        "sensitivity rows.",
        "",
    ])
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--grade-run-id", required=True)
    parser.add_argument("--grade-completion-uri", required=True)
    parser.add_argument("--grade-root-uri", required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser


def _require_gate(
    args: argparse.Namespace, *, environ: Mapping[str, str],
) -> None:
    if args.execute is not True or environ.get(ENABLED_ENV) != "1":
        _fail(f"--execute and {ENABLED_ENV}=1 are required explicitly")
    if args.project != PROJECT:
        _fail("Core v1 grade-report project differs")
    if type(args.grade_run_id) is not str or _RUN_ID.fullmatch(args.grade_run_id) is None:
        _fail("Core v1 grade-report run ID differs")
    prefix = grade_cloud.grade_output_prefix(args.grade_run_id)
    if args.grade_completion_uri != prefix + grade_cloud.GRADE_COMPLETION_FILENAME:
        _fail("Core v1 grade-report completion URI differs")
    if args.grade_root_uri != prefix + publisher.ROOT_FILENAME:
        _fail("Core v1 grade-report root URI differs")


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    storage_client: object | None = None,
) -> int:
    args = _parser().parse_args(argv)
    retained_environ = os.environ if environ is None else environ
    _require_gate(args, environ=retained_environ)
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client(project=PROJECT)
    store = grade_cloud.ReadOnlyGenerationPinnedGCS(storage_client)
    reopened = grade_cloud.reopen_completed_core_v1_grade(
        grade_run_id=args.grade_run_id, store=store
    )
    report = build_core_v1_grade_report(
        grade_run_id=args.grade_run_id,
        completion=reopened.completion,
        completion_identity=reopened.completion_identity,
        realized_grade=reopened.realized_grade,
    )
    if report["grade_root_identity"]["uri"] != args.grade_root_uri:
        _fail("exact-reopened grade root differs from the requested root URI")
    if args.format == "markdown":
        print(render_markdown(report), end="")
    else:
        print(publisher.canonical_json_bytes(report).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        CoreV1GradeReportError,
        grade_cloud.CoreV1GradeCloudError,
        grading.CorpusCatalogRealizedGradingError,
        publisher.CorpusCoreV1GradePublisherError,
        batch.CorpusParametricBatchError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


__all__ = [
    "ABSOLUTE_STRATEGY_IDS",
    "BASELINE_STRATEGY_ID",
    "CoreV1GradeReportError",
    "ENABLED_ENV",
    "REPORT_SCHEMA",
    "T230_STRATEGY_IDS",
    "build_core_v1_grade_report",
    "main",
    "render_markdown",
]
