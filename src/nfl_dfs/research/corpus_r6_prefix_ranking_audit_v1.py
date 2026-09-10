"""Retrospective audit of final-book ordering and breakout capture.

The audit consumes already-persisted R6 attribution shards.  It never queries
outcomes, mutates Neo4j, or grants policy authority.  Its purpose is to split a
miss at any bankroll prefix into candidate-supply, full-book selection, and
within-book ordering losses.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from statistics import mean
from typing import Final, Mapping, Sequence


SCHEMA_VERSION: Final = "corpus-r6-prefix-ranking-audit/v1"
FIT_SCOPE_ID: Final = "all-block-final-fit"
PREFIX_SIZES: Final = (1, 3, 5, 10, 20, 40, 57, 80)
THRESHOLDS_DK: Final = (187, 194, 200, 210, 220, 230, 240)
METRIC_NAMES: Final = (
    "selection_priority",
    "training_mean_score",
    "selector_event_count",
    "objective_gain",
    "discovery_mean_score",
    "discovery_event_count",
)


class CorpusR6PrefixRankingAuditV1Error(ValueError):
    """Raised when a shard grid or derived audit invariant differs."""


def _fail(message: str) -> None:
    raise CorpusR6PrefixRankingAuditV1Error(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        _fail(f"{label} must be an array")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or int(value) < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return int(value)


def _numeric(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    retained = float(value)
    return retained if math.isfinite(retained) else None


def _rankdata(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        stop = cursor + 1
        while stop < len(order) and values[order[stop]] == values[order[cursor]]:
            stop += 1
        average_rank = (cursor + 1 + stop) / 2.0
        for index in order[cursor:stop]:
            ranks[index] = average_rank
        cursor = stop
    return ranks


def _spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        _fail("Spearman inputs must have the same nontrivial length")
    ranked_left = _rankdata(left)
    ranked_right = _rankdata(right)
    left_mean = mean(ranked_left)
    right_mean = mean(ranked_right)
    left_ss = sum((value - left_mean) ** 2 for value in ranked_left)
    right_ss = sum((value - right_mean) ** 2 for value in ranked_right)
    if left_ss == 0.0 or right_ss == 0.0:
        return None
    covariance = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(ranked_left, ranked_right, strict=True)
    )
    return covariance / math.sqrt(left_ss * right_ss)


def _fraction(numerator: int, denominator: int, *, unit: str) -> dict[str, object]:
    return {"numerator": numerator, "denominator": denominator, "unit": unit}


def _mean_micro(values: Sequence[int]) -> dict[str, object]:
    return {
        "numerator": sum(values),
        "denominator": len(values),
        "unit": "micro_dk",
    }


def _median_rank(values: Sequence[int]) -> dict[str, int]:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return {"numerator": ordered[midpoint], "denominator": 1}
    return {
        "numerator": ordered[midpoint - 1] + ordered[midpoint],
        "denominator": 2,
    }


def _metric_values(row: Mapping[str, object]) -> dict[str, float | None]:
    trace = _mapping(row.get("marginal_trace"), label="marginal trace")
    tie_break = _mapping(trace.get("tie_break_values"), label="tie-break values")
    base = _mapping(trace.get("base_trace"), label="base trace")
    rank = _integer(row.get("selection_rank"), label="selection rank")
    return {
        "selection_priority": float(-rank),
        "training_mean_score": _numeric(tie_break.get("training_mean_score")),
        "selector_event_count": _numeric(
            tie_break.get("individual_selector_event_count")
        ),
        "objective_gain": _numeric(trace.get("objective_gain")),
        "discovery_mean_score": _numeric(base.get("discovery_mean_score")),
        "discovery_event_count": _numeric(
            base.get("discovery_primary_event_count")
        ),
    }


def build_prefix_ranking_audit_v1(
    shards: Sequence[Mapping[str, object]],
    *,
    source_binding: Mapping[str, object],
    expected_slate_count: int = 54,
    expected_strategy_count: int = 8,
    entry_count: int = 80,
) -> dict[str, object]:
    """Build a row-free ordering audit from a complete attribution shard grid."""

    if len(shards) != expected_slate_count:
        _fail("attribution shard census differs")
    if entry_count != PREFIX_SIZES[-1]:
        _fail("entry count differs from the frozen K80 book")
    ordered_shards = sorted(
        shards,
        key=lambda shard: _integer(shard.get("source_ordinal"), label="source ordinal"),
    )
    if [shard.get("source_ordinal") for shard in ordered_shards] != list(
        range(expected_slate_count)
    ):
        _fail("source ordinal grid differs")

    strategy_ids: list[str] | None = None
    strategy_state: dict[str, dict[str, object]] = {}
    observed_slate_ids: set[str] = set()
    for shard in ordered_shards:
        if shard.get("complete") is not True or shard.get("uses_realized_outcomes") is not True:
            _fail("attribution shard authority differs")
        slate_id = shard.get("slate_id")
        if type(slate_id) is not str or not slate_id or slate_id in observed_slate_ids:
            _fail("slate identity grid differs")
        observed_slate_ids.add(slate_id)
        books = [
            _mapping(row, label="book row")
            for row in _sequence(shard.get("book_rows"), label="book rows")
            if _mapping(row, label="book row").get("fit_scope_id") == FIT_SCOPE_ID
        ]
        books.sort(key=lambda row: _integer(row.get("strategy_ordinal"), label="strategy ordinal"))
        current_strategy_ids = [str(row.get("strategy_id")) for row in books]
        if (
            len(books) != expected_strategy_count
            or len(set(current_strategy_ids)) != expected_strategy_count
        ):
            _fail("final-fit strategy census differs")
        if strategy_ids is None:
            strategy_ids = current_strategy_ids
        elif current_strategy_ids != strategy_ids:
            _fail("final-fit strategy order differs")

        selections_by_strategy: dict[str, list[Mapping[str, object]]] = defaultdict(list)
        for raw_row in _sequence(shard.get("selection_rows"), label="selection rows"):
            row = _mapping(raw_row, label="selection row")
            if row.get("fit_scope_id") == FIT_SCOPE_ID:
                selections_by_strategy[str(row.get("strategy_id"))].append(row)

        for book in books:
            strategy_id = str(book.get("strategy_id"))
            rows = sorted(
                selections_by_strategy[strategy_id],
                key=lambda row: _integer(row.get("selection_rank"), label="selection rank"),
            )
            if (
                len(rows) != entry_count
                or [row.get("selection_rank") for row in rows] != list(range(entry_count))
                or book.get("selected_lineup_count") != entry_count
            ):
                _fail("final-fit ordered book differs")
            scores = [
                _integer(row.get("realized_score_micro"), label="realized score")
                for row in rows
            ]
            eligible_maximum = _integer(
                book.get("eligible_maximum_score_micro"), label="eligible maximum"
            )
            selected_maximum = max(scores)
            if (
                book.get("selected_maximum_score_micro") != selected_maximum
                or book.get("selector_regret_micro")
                != eligible_maximum - selected_maximum
            ):
                _fail("book maximum/regret differs")

            state = strategy_state.setdefault(
                strategy_id,
                {
                    "eligible": [],
                    "selected": [],
                    "regret": [],
                    "best_rank": [],
                    "prefix_maxima": {size: [] for size in PREFIX_SIZES},
                    "thresholds": {
                        threshold: {
                            "supply": 0,
                            "selected": 0,
                            "first_hit_rank_sum": 0,
                            "prefix": {size: 0 for size in PREFIX_SIZES},
                        }
                        for threshold in THRESHOLDS_DK
                    },
                    "correlations": {name: [] for name in METRIC_NAMES},
                },
            )
            state["eligible"].append(eligible_maximum)  # type: ignore[union-attr]
            state["selected"].append(selected_maximum)  # type: ignore[union-attr]
            state["regret"].append(eligible_maximum - selected_maximum)  # type: ignore[union-attr]
            best_rank = next(
                rank for rank, score in enumerate(scores, start=1) if score == selected_maximum
            )
            state["best_rank"].append(best_rank)  # type: ignore[union-attr]
            for size in PREFIX_SIZES:
                state["prefix_maxima"][size].append(max(scores[:size]))  # type: ignore[index,union-attr]
            for threshold in THRESHOLDS_DK:
                threshold_micro = threshold * 1_000_000
                threshold_state = state["thresholds"][threshold]  # type: ignore[index]
                threshold_state["supply"] += eligible_maximum >= threshold_micro
                threshold_state["selected"] += selected_maximum >= threshold_micro
                hit_ranks = [
                    rank
                    for rank, score in enumerate(scores, start=1)
                    if score >= threshold_micro
                ]
                if hit_ranks:
                    threshold_state["first_hit_rank_sum"] += hit_ranks[0]
                for size in PREFIX_SIZES:
                    threshold_state["prefix"][size] += (  # type: ignore[index]
                        max(scores[:size]) >= threshold_micro
                    )

            metric_rows = [_metric_values(row) for row in rows]
            for metric_name in METRIC_NAMES:
                metric = [row[metric_name] for row in metric_rows]
                if any(value is None for value in metric):
                    continue
                correlation = _spearman(
                    [float(value) for value in metric if value is not None], scores
                )
                if correlation is not None:
                    state["correlations"][metric_name].append(correlation)  # type: ignore[index,union-attr]

    if strategy_ids is None or set(strategy_state) != set(strategy_ids):
        _fail("strategy audit grid differs")

    strategy_summaries: list[dict[str, object]] = []
    for strategy_id in strategy_ids:
        state = strategy_state[strategy_id]
        selected_values = state["selected"]
        prefix_rows = []
        for size in PREFIX_SIZES:
            prefix_maxima = state["prefix_maxima"][size]  # type: ignore[index]
            prefix_rows.append(
                {
                    "entry_count": size,
                    "prefix_maximum_mean": _mean_micro(prefix_maxima),
                    "full_book_best_retained_slate_count": sum(
                        prefix == selected
                        for prefix, selected in zip(
                            prefix_maxima, selected_values, strict=True
                        )
                    ),
                }
            )
        threshold_rows = []
        for threshold in THRESHOLDS_DK:
            threshold_state = state["thresholds"][threshold]  # type: ignore[index]
            supply = int(threshold_state["supply"])
            selected = int(threshold_state["selected"])
            prefixes = []
            for size in PREFIX_SIZES:
                captured = int(threshold_state["prefix"][size])  # type: ignore[index]
                partition = {
                    "no_eligible_supply_slate_count": expected_slate_count - supply,
                    "eligible_but_full_book_miss_slate_count": supply - selected,
                    "full_book_hit_but_below_prefix_slate_count": selected - captured,
                    "prefix_capture_slate_count": captured,
                }
                if sum(partition.values()) != expected_slate_count or min(partition.values()) < 0:
                    _fail("prefix loss partition differs")
                prefixes.append({"entry_count": size, **partition})
            threshold_rows.append(
                {
                    "threshold_dk": threshold,
                    "eligible_supply_slate_count": supply,
                    "full_book_capture_slate_count": selected,
                    "first_hit_rank_1_based_mean": _fraction(
                        int(threshold_state["first_hit_rank_sum"]),
                        selected,
                        unit="selected_capture_slates",
                    ),
                    "prefixes": prefixes,
                }
            )
        correlation_rows = []
        for metric_name in METRIC_NAMES:
            values = state["correlations"][metric_name]  # type: ignore[index]
            correlation_rows.append(
                {
                    "metric": metric_name,
                    "observed_slate_count": len(values),
                    "mean_within_slate_spearman": (
                        round(mean(values), 12) if values else None
                    ),
                    "positive_slate_count": sum(value > 0 for value in values),
                    "zero_slate_count": sum(value == 0 for value in values),
                    "negative_slate_count": sum(value < 0 for value in values),
                }
            )
        strategy_summaries.append(
            {
                "strategy_id": strategy_id,
                "slate_count": expected_slate_count,
                "entry_count": entry_count,
                "eligible_maximum_mean": _mean_micro(state["eligible"]),  # type: ignore[arg-type]
                "selected_maximum_mean": _mean_micro(selected_values),  # type: ignore[arg-type]
                "selector_regret_mean": _mean_micro(state["regret"]),  # type: ignore[arg-type]
                "best_selected_lineup_rank_1_based_median": _median_rank(
                    state["best_rank"]  # type: ignore[arg-type]
                ),
                "prefix_rows": prefix_rows,
                "threshold_rows": threshold_rows,
                "metric_correlations": correlation_rows,
            }
        )

    audit: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": "retrospective-development-diagnostic",
        "source_binding": dict(source_binding),
        "source_slate_count": expected_slate_count,
        "strategy_count": expected_strategy_count,
        "fit_scope_id": FIT_SCOPE_ID,
        "entry_count": entry_count,
        "prefix_sizes": list(PREFIX_SIZES),
        "thresholds_dk": list(THRESHOLDS_DK),
        "uses_realized_outcomes": True,
        "raw_outcome_query_performed": False,
        "neo4j_mutation_performed": False,
        "individual_rows_included": False,
        "promotion_authority": False,
        "decision_authority": False,
        "production_policy_authority": False,
        "strategy_summaries": strategy_summaries,
        "complete": True,
    }
    encoded = json.dumps(audit, sort_keys=True, separators=(",", ":")).encode()
    audit["audit_sha256"] = hashlib.sha256(encoded).hexdigest()
    return audit


__all__ = [
    "CorpusR6PrefixRankingAuditV1Error",
    "FIT_SCOPE_ID",
    "METRIC_NAMES",
    "PREFIX_SIZES",
    "SCHEMA_VERSION",
    "THRESHOLDS_DK",
    "build_prefix_ranking_audit_v1",
]
