from __future__ import annotations

from copy import deepcopy

import pytest

from nfl_dfs.research import corpus_r6_random_null_kcurve_v1 as diagnostic


def _with_hash(value: dict[str, object], field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = diagnostic._sha(result)
    return result


def _current_report() -> dict[str, object]:
    cells = []
    for k, total in ((4, 300_000_000), (14, 320_000_000), (80, 360_000_000)):
        cells.append(
            {
                "entry_count": k,
                "fit_scope_id": diagnostic.CURRENT_FIT_SCOPE_ID,
                "slate_maximum_mean": {
                    "numerator": total,
                    "denominator": 2,
                    "unit": "micro_dk",
                },
                "thresholds": [
                    {
                        "threshold_dk": threshold,
                        "slates_with_at_least_one_hit": int(threshold <= 200),
                    }
                    for threshold in diagnostic.THRESHOLDS_DK
                ],
            }
        )
    return _with_hash(
        {
            "schema_version": diagnostic.CURRENT_REPORT_SCHEMA,
            "complete": True,
            "source_slate_count": 2,
            "strategy_summaries": [
                {
                    "strategy_id": diagnostic.CURRENT_STRATEGY_ID,
                    "cells": cells,
                }
            ],
        },
        "score_report_sha256",
    )


def _population(*, role: str, prefix: str) -> dict[str, object]:
    full_ids = [f"{prefix}-{index:03d}" for index in range(160)]
    selectors = []
    books = []
    for selector_index in range(4):
        ranked = full_ids[selector_index:] + full_ids[:selector_index]
        ranked = ranked[:150]
        grouped_id = None if selector_index == 3 else f"g-{selector_index}"
        rank_id = f"r-{selector_index}"
        selectors.append(
            {
                "grouped_selector_id": grouped_id,
                "rank150_selector_id": rank_id,
                "ranked_lineup_ids": ranked,
            }
        )
        for k in diagnostic.PERSISTED_HARD_ENTRY_COUNTS:
            books.append(
                {
                    "coordinate": {"selector_id": rank_id, "entry_budget": k},
                    "selected_lineup_ids": ranked[:k],
                }
            )
    return {
        "population_id": f"pop-{role}",
        "population_role": role,
        "full_population_lineup_count": len(full_ids),
        "full_population_lineups": [{"lineup_id": lineup_id} for lineup_id in full_ids],
        "selector_summaries": selectors,
        "books": books,
    }


def _score(lineup_id: str, slate_ordinal: int) -> int:
    index = int(lineup_id.rsplit("-", 1)[1])
    role_bonus = 20_000_000 if "hard230" in lineup_id else 0
    return 120_000_000 + role_bonus + index * 1_000_000 + slate_ordinal * 2_000_000


def _terminal_and_grade() -> tuple[dict[str, object], dict[str, object]]:
    terminal_slates = []
    grade_slates = []
    for ordinal in range(2):
        slate_id = f"202{ordinal + 3}-w01"
        populations = [
            _population(role="score-blind-control", prefix=f"control-{ordinal}"),
            _population(role="hard230-challenger", prefix=f"hard230-{ordinal}"),
        ]
        terminal_slates.append(
            {
                "source_ordinal": ordinal,
                "slate_id": slate_id,
                "population_results": populations,
            }
        )
        score_rows = []
        metrics = []
        for population in populations:
            population_ids = [row["lineup_id"] for row in population["full_population_lineups"]]
            for lineup_id in population_ids:
                score_rows.append(
                    {
                        "lineup_id": lineup_id,
                        "realized_score_micro": _score(lineup_id, ordinal),
                    }
                )
            population_scores = [_score(lineup_id, ordinal) for lineup_id in population_ids]
            for ranking in population["selector_summaries"]:
                rank_id = ranking["rank150_selector_id"]
                grouped_id = ranking["grouped_selector_id"]
                ranked = ranking["ranked_lineup_ids"]
                for k in diagnostic.PERSISTED_HARD_ENTRY_COUNTS:
                    selected_scores = [_score(lineup_id, ordinal) for lineup_id in ranked[:k]]
                    metrics.append(
                        {
                            "coordinate": {
                                "population_id": population["population_id"],
                                "selector_id": rank_id,
                                "entry_budget": k,
                            },
                            "weekly_maximum_micro": max(selected_scores),
                            "population_lineup_count": len(population_ids),
                            "selected_lineup_count": k,
                            "thresholds": [
                                {
                                    "threshold_dk": threshold,
                                    "population_lineup_hit_count": sum(
                                        score >= threshold * diagnostic.MICRO_DK_PER_POINT
                                        for score in population_scores
                                    ),
                                    "selected_lineup_hit_count": sum(
                                        score >= threshold * diagnostic.MICRO_DK_PER_POINT
                                        for score in selected_scores
                                    ),
                                }
                                for threshold in (200, 210, 220, 230)
                            ],
                        }
                    )
        grade_slates.append(
            {
                "source_ordinal": ordinal,
                "slate_id": slate_id,
                "lineup_score_rows": score_rows,
                "metrics": metrics,
            }
        )
    terminal = {
        "terminal_sha256": "a" * 64,
        "source_slate_count": 2,
        "slate_results": terminal_slates,
    }
    grade = _with_hash(
        {
            "schema_version": diagnostic.HARD_GRADE_SCHEMA,
            "complete": True,
            "terminal_sha256": terminal["terminal_sha256"],
            "source_slate_count": 2,
            "slate_grades": grade_slates,
        },
        "grade_sha256",
    )
    return terminal, grade


def test_uniform_random_book_null_is_exact_hypergeometric() -> None:
    result = diagnostic.uniform_random_book_null_v1(
        population_count=5, hit_count=2, k=2
    )
    assert result["random_hit_numerator"] == 7
    assert result["random_no_hit_numerator"] == 3
    assert result["random_denominator"] == 10
    assert result["random_hit_probability"] == pytest.approx(0.7)


def test_capture_equivalent_shots_inverts_expected_capture() -> None:
    result = diagnostic.capture_equivalent_independent_shots_v1(
        prevalence=[0.5, 0.5], observed_hits=1
    )
    assert result["shots"] == pytest.approx(1.0)
    assert result["right_censored"] is False


def test_analyzer_replays_nested_prefixes_and_matched_pairs() -> None:
    terminal, grade = _terminal_and_grade()
    result = diagnostic.analyze_random_null_kcurve_v1(
        current_report=_current_report(),
        hard_terminal=terminal,
        hard_grade=grade,
        expected_slate_count=2,
        terminal_validator=lambda value: value,
    )
    assert result["complete"] is True
    assert result["current_r6"]["available_entry_counts"] == [4, 14, 80]
    assert result["current_r6"]["unavailable_entry_counts"] == [100, 150]
    assert len(result["hard230_rankings"]) == 40
    assert len(result["hard230_paired_population_comparisons"]) == 20
    primary = next(
        row
        for row in result["hard230_rankings"]
        if row["population_role"] == "hard230-challenger"
        and row["selector_id"] == "r-3"
        and row["entry_count"] == 4
    )
    assert all(row["derived_nested_prefix"] for row in primary["weekly_rows"])
    assert primary["mean_weekly_maximum_dk"] == pytest.approx(147.0)
    paired = next(
        row
        for row in result["hard230_paired_population_comparisons"]
        if row["selector_id"] == "r-3" and row["entry_count"] == 4
    )
    assert paired["paired_mean_weekly_maximum_delta_dk"] == pytest.approx(20.0)
    assert result["simulated_tail_correlation_effective_rank_available"] is False


def test_analyzer_rejects_a_persisted_book_that_is_not_the_prefix() -> None:
    terminal, grade = _terminal_and_grade()
    forged = deepcopy(terminal)
    book = forged["slate_results"][0]["population_results"][0]["books"][0]
    book["selected_lineup_ids"][0], book["selected_lineup_ids"][1] = (
        book["selected_lineup_ids"][1],
        book["selected_lineup_ids"][0],
    )
    with pytest.raises(
        diagnostic.CorpusR6RandomNullKCurveV1Error,
        match="not the frozen ranking prefix",
    ):
        diagnostic.analyze_random_null_kcurve_v1(
            current_report=_current_report(),
            hard_terminal=forged,
            hard_grade=grade,
            expected_slate_count=2,
            terminal_validator=lambda value: value,
        )
