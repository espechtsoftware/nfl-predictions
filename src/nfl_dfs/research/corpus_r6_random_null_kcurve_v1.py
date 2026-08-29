"""Deterministic realized-score diagnostics for frozen R6 books.

This module consumes only three already-materialized JSON artifacts:

* the current-R6 persisted score report;
* the hard-230 score-free selector terminal; and
* the realized grade of that terminal.

It never queries outcomes, regenerates a population, or reruns a selector.
For every hard-230 frozen 150-lineup ranking it derives nested prefixes at
K=4/14/80/100/150, verifies the persisted 80/100/150 books, attaches the
already-materialized realized scores, and computes the exact uniform random
book probability

    1 - C(N-M, K) / C(N, K)

for each slate and threshold.  The aggregate ``capture_equivalent_shots`` is
an explicitly outcome-driven inversion of independent-with-replacement
capture probabilities.  It is *not* the simulated tail-event correlation
participation ratio / entropy effective rank; the persisted terminal retains
matrix hashes rather than the 54 matrix bodies needed for that calculation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from hashlib import sha256
import json
import math
from typing import Final

from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as bridge


SCHEMA_VERSION: Final = "corpus-r6-random-null-kcurve-diagnostic/v1"
CURRENT_REPORT_SCHEMA: Final = "corpus-r6-full-union-score-report/v1"
HARD_GRADE_SCHEMA: Final = "corpus-r6-hard230-selector-bridge-realized-grade/v1"
CURRENT_STRATEGY_ID: Final = "tail-ladder-200-210-220-v1"
CURRENT_FIT_SCOPE_ID: Final = "all-block-final-fit"
ENTRY_COUNTS: Final = (4, 14, 80, 100, 150)
PERSISTED_HARD_ENTRY_COUNTS: Final = (80, 100, 150)
THRESHOLDS_DK: Final = (194, 200, 220, 230)
MICRO_DK_PER_POINT: Final = 1_000_000


class CorpusR6RandomNullKCurveV1Error(ValueError):
    """A frozen artifact or derived diagnostic was incomplete or divergent."""


def _fail(message: str) -> None:
    raise CorpusR6RandomNullKCurveV1Error(message)


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


def _text(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusR6RandomNullKCurveV1Error(
            "diagnostic value is not canonical finite JSON"
        ) from exc


def _sha(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    retained = value.get(field)
    if type(retained) is not str or len(retained) != 64:
        _fail(f"{label} {field} must be one SHA-256")
    body = {key: item for key, item in value.items() if key != field}
    if retained != _sha(body):
        _fail(f"{label} self-hash differs")


def _fraction(value: object, *, label: str) -> tuple[int, int]:
    row = _mapping(value, label=label)
    numerator = _integer(row.get("numerator"), label=f"{label} numerator")
    denominator = _integer(
        row.get("denominator"), label=f"{label} denominator", minimum=1
    )
    return numerator, denominator


@lru_cache(maxsize=None)
def _combination(n: int, k: int) -> int:
    return math.comb(n, k)


def uniform_random_book_null_v1(*, population_count: int, hit_count: int, k: int) -> dict[str, object]:
    """Return the exact hypergeometric probability of at least one hit."""
    _integer(population_count, label="population count", minimum=1)
    _integer(hit_count, label="hit count", minimum=0)
    _integer(k, label="entry count", minimum=1)
    if hit_count > population_count:
        _fail("hit count exceeds population count")
    if k > population_count:
        _fail("entry count exceeds population count")
    denominator = _combination(population_count, k)
    no_hit_numerator = (
        _combination(population_count - hit_count, k)
        if k <= population_count - hit_count
        else 0
    )
    hit_numerator = denominator - no_hit_numerator
    return {
        "population_lineup_count": population_count,
        "population_hit_count": hit_count,
        "entry_count": k,
        "random_hit_numerator": hit_numerator,
        "random_no_hit_numerator": no_hit_numerator,
        "random_denominator": denominator,
        "random_hit_probability": hit_numerator / denominator,
    }


def capture_equivalent_independent_shots_v1(
    *, prevalence: Sequence[float], observed_hits: int
) -> dict[str, object]:
    """Invert independent-with-replacement capture over opportunity slates.

    The returned count answers: how many independent random shots with each
    slate's observed population prevalence would have the same expected
    number of captured opportunity slates as the frozen book actually did?
    It measures realized retrieval enrichment.  It does not measure simulated
    score-vector correlation or portfolio diversification.
    """
    probabilities = [float(value) for value in prevalence]
    if any(not math.isfinite(value) or value <= 0.0 or value > 1.0 for value in probabilities):
        _fail("opportunity prevalence must be finite in (0, 1]")
    _integer(observed_hits, label="observed hits", minimum=0)
    opportunities = len(probabilities)
    if observed_hits > opportunities:
        _fail("observed hits exceed opportunity count")
    if opportunities == 0:
        return {"shots": None, "right_censored": False, "opportunity_count": 0}
    if observed_hits == 0:
        return {"shots": 0.0, "right_censored": False, "opportunity_count": opportunities}
    if observed_hits == opportunities:
        return {"shots": None, "right_censored": True, "opportunity_count": opportunities}

    def expected(shots: float) -> float:
        if shots == 0.0:
            return 0.0
        total = 0.0
        for probability in probabilities:
            if probability == 1.0:
                total += 1.0
            else:
                total += -math.expm1(shots * math.log1p(-probability))
        return total

    low = 0.0
    high = 1.0
    while expected(high) < observed_hits:
        high *= 2.0
        if high > 1.0e12:
            _fail("capture-equivalent shot inversion did not converge")
    for _ in range(96):
        midpoint = (low + high) / 2.0
        if expected(midpoint) < observed_hits:
            low = midpoint
        else:
            high = midpoint
    shots = (low + high) / 2.0
    return {"shots": shots, "right_censored": False, "opportunity_count": opportunities}


def _threshold_summary(weekly_rows: Sequence[Mapping[str, object]], *, k: int, threshold: int) -> dict[str, object]:
    opportunities = [row for row in weekly_rows if int(row["population_hit_count"]) > 0]
    observed_hits = sum(bool(row["selected_hit"]) for row in opportunities)
    expected_random_hits = sum(float(row["random_hit_probability"]) for row in opportunities)
    selected_lineup_hits = sum(int(row["selected_lineup_hit_count"]) for row in opportunities)
    prevalence = [
        int(row["population_hit_count"]) / int(row["population_lineup_count"])
        for row in opportunities
    ]
    equivalent = capture_equivalent_independent_shots_v1(
        prevalence=prevalence, observed_hits=observed_hits
    )
    return {
        "threshold_dk": threshold,
        "entry_count": k,
        "opportunity_slate_count": len(opportunities),
        "selected_hit_slate_count": observed_hits,
        "selected_lineup_hit_count": selected_lineup_hits,
        "selected_conditional_capture": (
            observed_hits / len(opportunities) if opportunities else None
        ),
        "uniform_random_expected_hit_slates": expected_random_hits,
        "uniform_random_conditional_capture": (
            expected_random_hits / len(opportunities) if opportunities else None
        ),
        "additive_capture_lift": (
            (observed_hits - expected_random_hits) / len(opportunities)
            if opportunities
            else None
        ),
        "capture_equivalent_independent_shots": equivalent,
        "effective_shot_kind": "realized-opportunity-capture-inversion",
        "simulated_tail_correlation_effective_rank_available": False,
    }


def _aggregate_weekly_rows(weekly_rows: Sequence[Mapping[str, object]], *, k: int) -> dict[str, object]:
    if not weekly_rows:
        _fail("cannot aggregate an empty weekly curve")
    maxima = [int(row["weekly_maximum_micro"]) for row in weekly_rows]
    return {
        "entry_count": k,
        "slate_count": len(weekly_rows),
        "mean_weekly_maximum_micro": {
            "numerator": sum(maxima),
            "denominator": len(maxima),
            "unit": "micro_dk",
        },
        "mean_weekly_maximum_dk": sum(maxima) / len(maxima) / MICRO_DK_PER_POINT,
        "thresholds": [
            _threshold_summary(
                [row["thresholds"][str(threshold)] for row in weekly_rows],
                k=k,
                threshold=threshold,
            )
            for threshold in THRESHOLDS_DK
        ],
    }


def _current_curve(current_report: Mapping[str, object], *, expected_slate_count: int) -> dict[str, object]:
    report = _mapping(current_report, label="current-R6 score report")
    if report.get("schema_version") != CURRENT_REPORT_SCHEMA or report.get("complete") is not True:
        _fail("current-R6 score report schema or completion differs")
    _self_hash(report, field="score_report_sha256", label="current-R6 score report")
    if _integer(report.get("source_slate_count"), label="current-R6 slate count") != expected_slate_count:
        _fail("current-R6 slate count differs")
    strategies = [
        _mapping(item, label="current-R6 strategy")
        for item in _sequence(report.get("strategy_summaries"), label="current-R6 strategies")
    ]
    retained = [row for row in strategies if row.get("strategy_id") == CURRENT_STRATEGY_ID]
    if len(retained) != 1:
        _fail("current-R6 tail-ladder strategy is not unique")
    all_cells = [
        _mapping(item, label="current-R6 strategy cell")
        for item in _sequence(
            retained[0].get("cells"), label="current-R6 strategy cells"
        )
    ]
    cells = [
        item for item in all_cells if item.get("fit_scope_id") == CURRENT_FIT_SCOPE_ID
    ]
    by_k: dict[int, dict[str, object]] = {}
    for cell in cells:
        k = _integer(cell.get("entry_count"), label="current-R6 entry count", minimum=1)
        if k in by_k:
            _fail("current-R6 all-block entry count repeats")
        numerator, denominator = _fraction(
            cell.get("slate_maximum_mean"), label="current-R6 weekly maximum mean"
        )
        threshold_rows = {
            _integer(item.get("threshold_dk"), label="current threshold"): _mapping(
                item, label="current threshold row"
            )
            for item in (
                _mapping(raw, label="current threshold row")
                for raw in _sequence(cell.get("thresholds"), label="current thresholds")
            )
        }
        by_k[k] = {
            "entry_count": k,
            "mean_weekly_maximum_micro": {
                "numerator": numerator,
                "denominator": denominator,
                "unit": "micro_dk",
            },
            "mean_weekly_maximum_dk": numerator / denominator / MICRO_DK_PER_POINT,
            "threshold_hit_slates": {
                str(threshold): _integer(
                    threshold_rows[threshold].get("slates_with_at_least_one_hit"),
                    label=f"current {threshold} hit slates",
                    minimum=0,
                )
                for threshold in THRESHOLDS_DK
            },
        }
    if set(by_k) != {4, 14, 80}:
        _fail("current-R6 frozen entry-count lattice differs")
    return {
        "strategy_id": CURRENT_STRATEGY_ID,
        "fit_scope_id": CURRENT_FIT_SCOPE_ID,
        "available_entry_counts": sorted(by_k),
        "unavailable_entry_counts": [100, 150],
        "weekly_rows_available": False,
        "random_null_available": False,
        "curve": [by_k[k] for k in sorted(by_k)],
    }


def _grade_score_lookup(grade_slate: Mapping[str, object]) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for raw in _sequence(grade_slate.get("lineup_score_rows"), label="grade lineup scores"):
        row = _mapping(raw, label="grade lineup score")
        lineup_id = _text(row.get("lineup_id"), label="grade lineup ID")
        score = _integer(row.get("realized_score_micro"), label="realized score")
        if lineup_id in lookup:
            _fail("grade lineup score repeats")
        lookup[lineup_id] = score
    return lookup


def _metric_lookup(grade_slate: Mapping[str, object]) -> dict[tuple[str, str, int], dict[str, object]]:
    lookup: dict[tuple[str, str, int], dict[str, object]] = {}
    for raw in _sequence(grade_slate.get("metrics"), label="grade metrics"):
        metric = _mapping(raw, label="grade metric")
        coordinate = _mapping(metric.get("coordinate"), label="grade coordinate")
        key = (
            _text(coordinate.get("population_id"), label="metric population ID"),
            _text(coordinate.get("selector_id"), label="metric selector ID"),
            _integer(coordinate.get("entry_budget"), label="metric entry budget", minimum=1),
        )
        if key in lookup:
            _fail("grade metric coordinate repeats")
        lookup[key] = metric
    return lookup


def _book_lookup(population: Mapping[str, object]) -> dict[tuple[str, int], list[str]]:
    lookup: dict[tuple[str, int], list[str]] = {}
    for raw in _sequence(population.get("books"), label="hard-230 books"):
        book = _mapping(raw, label="hard-230 book")
        coordinate = _mapping(book.get("coordinate"), label="hard-230 book coordinate")
        key = (
            _text(coordinate.get("selector_id"), label="book selector ID"),
            _integer(coordinate.get("entry_budget"), label="book entry budget", minimum=1),
        )
        ids = [
            _text(item, label="selected lineup ID")
            for item in _sequence(book.get("selected_lineup_ids"), label="selected lineup IDs")
        ]
        if key in lookup or len(ids) != len(set(ids)) or len(ids) != key[1]:
            _fail("hard-230 persisted book differs")
        lookup[key] = ids
    return lookup


def _ranking_weekly_rows(
    *,
    slate_id: str,
    source_ordinal: int,
    population: Mapping[str, object],
    ranking: Mapping[str, object],
    score_lookup: Mapping[str, int],
    metric_lookup: Mapping[tuple[str, str, int], Mapping[str, object]],
) -> list[dict[str, object]]:
    population_id = _text(population.get("population_id"), label="population ID")
    population_role = _text(population.get("population_role"), label="population role")
    population_lineups = [
        _mapping(item, label="full population lineup")
        for item in _sequence(population.get("full_population_lineups"), label="full population")
    ]
    population_ids = [
        _text(item.get("lineup_id"), label="population lineup ID")
        for item in population_lineups
    ]
    if len(population_ids) != len(set(population_ids)):
        _fail("full population repeats a lineup")
    declared_count = _integer(
        population.get("full_population_lineup_count"), label="full population count", minimum=1
    )
    if len(population_ids) != declared_count or any(item not in score_lookup for item in population_ids):
        _fail("full population score coverage differs")

    rank_selector_id = _text(ranking.get("rank150_selector_id"), label="rank-150 selector ID")
    grouped_selector = ranking.get("grouped_selector_id")
    if grouped_selector is not None:
        grouped_selector = _text(grouped_selector, label="grouped selector ID")
    ranked_ids = [
        _text(item, label="ranked lineup ID")
        for item in _sequence(ranking.get("ranked_lineup_ids"), label="ranked lineup IDs")
    ]
    if len(ranked_ids) != 150 or len(set(ranked_ids)) != 150 or not set(ranked_ids).issubset(population_ids):
        _fail("frozen rank-150 lineup IDs differ")
    books = _book_lookup(population)

    weekly: list[dict[str, object]] = []
    population_scores = [score_lookup[lineup_id] for lineup_id in population_ids]
    for k in ENTRY_COUNTS:
        selected_ids = ranked_ids[:k]
        selected_scores = [score_lookup[lineup_id] for lineup_id in selected_ids]
        # The bridge deliberately normalizes all three persisted budgets onto
        # the rank-150 selector coordinate.  For native selectors the source
        # summary separately proves grouped-rank80/prefix parity.
        persisted_selector_id = rank_selector_id
        if k in PERSISTED_HARD_ENTRY_COUNTS:
            if books.get((persisted_selector_id, k)) != selected_ids:
                _fail(
                    "persisted hard-230 book is not the frozen ranking prefix: "
                    f"slate={slate_id} population={population_id} "
                    f"selector={persisted_selector_id} K={k}"
                )
            metric = metric_lookup.get((population_id, persisted_selector_id, k))
            if metric is None:
                _fail("persisted hard-230 grade metric is missing")
            if (
                _integer(metric.get("weekly_maximum_micro"), label="grade weekly maximum")
                != max(selected_scores)
                or _integer(metric.get("population_lineup_count"), label="metric population count")
                != declared_count
                or _integer(metric.get("selected_lineup_count"), label="metric selected count") != k
            ):
                _fail("persisted hard-230 grade metric differs from ranking replay")
            metric_thresholds = {
                _integer(item.get("threshold_dk"), label="metric threshold"): _mapping(
                    item, label="metric threshold row"
                )
                for item in (
                    _mapping(raw, label="metric threshold row")
                    for raw in _sequence(metric.get("thresholds"), label="metric thresholds")
                )
            }
        else:
            metric_thresholds = {}

        threshold_rows: dict[str, object] = {}
        for threshold in THRESHOLDS_DK:
            threshold_micro = threshold * MICRO_DK_PER_POINT
            population_hits = sum(score >= threshold_micro for score in population_scores)
            selected_hits = sum(score >= threshold_micro for score in selected_scores)
            if k in PERSISTED_HARD_ENTRY_COUNTS and threshold != 194:
                metric_row = metric_thresholds.get(threshold)
                if metric_row is None or (
                    _integer(metric_row.get("population_lineup_hit_count"), label="metric population hits")
                    != population_hits
                    or _integer(metric_row.get("selected_lineup_hit_count"), label="metric selected hits")
                    != selected_hits
                ):
                    _fail("persisted hard-230 threshold metric differs")
            null = uniform_random_book_null_v1(
                population_count=declared_count, hit_count=population_hits, k=k
            )
            threshold_rows[str(threshold)] = {
                "slate_id": slate_id,
                "source_ordinal": source_ordinal,
                "population_lineup_count": declared_count,
                "population_hit_count": population_hits,
                "selected_lineup_hit_count": selected_hits,
                "selected_hit": selected_hits > 0,
                **null,
            }
        weekly.append(
            {
                "slate_id": slate_id,
                "source_ordinal": source_ordinal,
                "population_id": population_id,
                "population_role": population_role,
                "selector_id": rank_selector_id,
                "entry_count": k,
                "weekly_maximum_micro": max(selected_scores),
                "thresholds": threshold_rows,
                "persisted_book": k in PERSISTED_HARD_ENTRY_COUNTS,
                "derived_nested_prefix": k not in PERSISTED_HARD_ENTRY_COUNTS,
            }
        )
    return weekly


def _paired_summaries(rankings: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], dict[str, Mapping[str, object]]] = {}
    for raw in rankings:
        row = _mapping(raw, label="ranking aggregate")
        key = (_text(row.get("selector_id"), label="ranking selector ID"), _integer(row.get("entry_count"), label="ranking K"))
        role = _text(row.get("population_role"), label="ranking population role")
        if role in grouped.setdefault(key, {}):
            _fail("paired ranking role repeats")
        grouped[key][role] = row
    pairs: list[dict[str, object]] = []
    for (selector_id, k), roles in sorted(grouped.items()):
        if set(roles) != {"score-blind-control", "hard230-challenger"}:
            _fail("matched hard-230 populations are incomplete")
        control = roles["score-blind-control"]
        challenger = roles["hard230-challenger"]
        control_weekly = {
            str(item["slate_id"]): int(item["weekly_maximum_micro"])
            for item in _sequence(control.get("weekly_rows"), label="control weekly rows")
        }
        challenger_weekly = {
            str(item["slate_id"]): int(item["weekly_maximum_micro"])
            for item in _sequence(challenger.get("weekly_rows"), label="challenger weekly rows")
        }
        if set(control_weekly) != set(challenger_weekly):
            _fail("paired weekly slate IDs differ")
        deltas = [challenger_weekly[slate] - control_weekly[slate] for slate in sorted(control_weekly)]
        control_thresholds = {
            int(item["threshold_dk"]): item
            for item in _sequence(control.get("thresholds"), label="control thresholds")
        }
        challenger_thresholds = {
            int(item["threshold_dk"]): item
            for item in _sequence(challenger.get("thresholds"), label="challenger thresholds")
        }
        pairs.append(
            {
                "selector_id": selector_id,
                "entry_count": k,
                "paired_mean_weekly_maximum_delta_micro": {
                    "numerator": sum(deltas),
                    "denominator": len(deltas),
                    "unit": "micro_dk",
                },
                "paired_mean_weekly_maximum_delta_dk": sum(deltas) / len(deltas) / MICRO_DK_PER_POINT,
                "challenger_win_slate_count": sum(delta > 0 for delta in deltas),
                "tie_slate_count": sum(delta == 0 for delta in deltas),
                "challenger_loss_slate_count": sum(delta < 0 for delta in deltas),
                "threshold_hit_slate_deltas": {
                    str(threshold): int(challenger_thresholds[threshold]["selected_hit_slate_count"])
                    - int(control_thresholds[threshold]["selected_hit_slate_count"])
                    for threshold in THRESHOLDS_DK
                },
            }
        )
    return pairs


def analyze_random_null_kcurve_v1(
    *,
    current_report: object,
    hard_terminal: object,
    hard_grade: object,
    expected_slate_count: int = 54,
    terminal_validator: Callable[[object], Mapping[str, object]] = bridge.validate_hard230_selector_terminal_v1,
) -> dict[str, object]:
    """Build the local-only frozen-book diagnostic."""
    _integer(expected_slate_count, label="expected slate count", minimum=1)
    current = _mapping(current_report, label="current-R6 report")
    terminal = _mapping(terminal_validator(hard_terminal), label="validated hard-230 terminal")
    grade = _mapping(hard_grade, label="hard-230 grade")
    if grade.get("schema_version") != HARD_GRADE_SCHEMA or grade.get("complete") is not True:
        _fail("hard-230 grade schema or completion differs")
    _self_hash(grade, field="grade_sha256", label="hard-230 grade")
    if grade.get("terminal_sha256") != terminal.get("terminal_sha256"):
        _fail("hard-230 terminal/grade binding differs")
    if (
        _integer(terminal.get("source_slate_count"), label="terminal slate count")
        != expected_slate_count
        or _integer(grade.get("source_slate_count"), label="grade slate count")
        != expected_slate_count
    ):
        _fail("hard-230 slate count differs")

    terminal_slates = [
        _mapping(item, label="terminal slate")
        for item in _sequence(terminal.get("slate_results"), label="terminal slates")
    ]
    if len(terminal_slates) != expected_slate_count:
        _fail("hard-230 terminal slate coverage differs")
    grade_slates = {
        (
            _integer(item.get("source_ordinal"), label="grade source ordinal", minimum=0),
            _text(item.get("slate_id"), label="grade slate ID"),
        ): item
        for item in (
            _mapping(raw, label="grade slate")
            for raw in _sequence(grade.get("slate_grades"), label="grade slates")
        )
    }
    if len(grade_slates) != expected_slate_count:
        _fail("hard-230 grade slate coverage differs")

    all_weekly: dict[tuple[str, str, int], list[dict[str, object]]] = {}
    for terminal_slate in terminal_slates:
        ordinal = _integer(terminal_slate.get("source_ordinal"), label="terminal source ordinal", minimum=0)
        slate_id = _text(terminal_slate.get("slate_id"), label="terminal slate ID")
        grade_slate = grade_slates.get((ordinal, slate_id))
        if grade_slate is None:
            _fail("terminal slate is absent from hard-230 grade")
        score_lookup = _grade_score_lookup(grade_slate)
        metrics = _metric_lookup(grade_slate)
        populations = [
            _mapping(item, label="terminal population")
            for item in _sequence(terminal_slate.get("population_results"), label="terminal populations")
        ]
        if len(populations) != 2:
            _fail("hard-230 matched population count differs")
        for population in populations:
            role = _text(population.get("population_role"), label="population role")
            rankings = [
                _mapping(item, label="selector ranking")
                for item in _sequence(population.get("selector_summaries"), label="selector rankings")
            ]
            if len(rankings) != 4:
                _fail("hard-230 selector ranking count differs")
            for ranking in rankings:
                selector_id = _text(ranking.get("rank150_selector_id"), label="rank-150 selector ID")
                for weekly in _ranking_weekly_rows(
                    slate_id=slate_id,
                    source_ordinal=ordinal,
                    population=population,
                    ranking=ranking,
                    score_lookup=score_lookup,
                    metric_lookup=metrics,
                ):
                    key = (role, selector_id, int(weekly["entry_count"]))
                    all_weekly.setdefault(key, []).append(weekly)

    rankings: list[dict[str, object]] = []
    for (role, selector_id, k), weekly in sorted(all_weekly.items()):
        if len(weekly) != expected_slate_count:
            _fail("hard-230 ranking weekly coverage differs")
        weekly.sort(key=lambda row: (int(row["source_ordinal"]), str(row["slate_id"])))
        aggregate = _aggregate_weekly_rows(weekly, k=k)
        rankings.append(
            {
                "population_role": role,
                "selector_id": selector_id,
                **aggregate,
                "weekly_rows": weekly,
            }
        )

    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "complete": True,
        "source_slate_count": expected_slate_count,
        "thresholds_dk": list(THRESHOLDS_DK),
        "entry_counts": list(ENTRY_COUNTS),
        "current_r6": _current_curve(current, expected_slate_count=expected_slate_count),
        "hard230_rankings": rankings,
        "hard230_paired_population_comparisons": _paired_summaries(rankings),
        "random_book_null_law": "1-C(N-M,K)/C(N,K)-without-replacement",
        "capture_equivalent_shot_law": (
            "solve-sum_s(1-(1-M_s/N_s)^n_eff)=observed-opportunity-hit-slates"
        ),
        "simulated_tail_correlation_effective_rank_available": False,
        "simulated_tail_correlation_effective_rank_reason": (
            "realized-grade-and-terminal-retain-score-matrix-identities-and-hashes-"
            "not-all-54-score-matrix-bodies"
        ),
        "no_new_outcome_query": True,
        "no_population_regeneration": True,
        "no_selector_rerun": True,
    }
    result["diagnostic_sha256"] = _sha(result)
    return result


__all__ = [
    "CorpusR6RandomNullKCurveV1Error",
    "analyze_random_null_kcurve_v1",
    "capture_equivalent_independent_shots_v1",
    "uniform_random_book_null_v1",
]
