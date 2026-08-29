from __future__ import annotations

from copy import deepcopy

import pytest

from nfl_dfs.research.corpus_r6_l2b_grade_summary_v1 import (
    CorpusR6L2BGradeSummaryV1Error,
    render_compact_markdown_v1,
    summarize_validated_l2b_v1,
)
from nfl_dfs.research.corpus_r6_score_sprint_scorecard_v1 import (
    GENERIC_SELECTOR_IDS,
    GENERIC_SELECTOR_ORDINALS,
)


def _surface() -> tuple[dict[str, object], dict[str, object]]:
    families = (
        ("grouped-native-rank80", (4, 14, 80)),
        ("exact-rank150-continuation", (80, 100, 150)),
        ("effective-independent-tail-shots", (80, 100, 150)),
        ("tail-ladder-diversity-challengers", (80, 100, 150)),
    )
    rows = []
    cells = []
    for fraction_ordinal, fraction in enumerate(
        ("l2b-quarter-world-mixture", "l2b-native")
    ):
        for block_ordinal, block in enumerate(("R0", "R1", "R2", "R3", "R4")):
            for family, budgets in families:
                for selector_ordinal, selector_id in zip(
                    GENERIC_SELECTOR_ORDINALS[family],
                    GENERIC_SELECTOR_IDS[family],
                    strict=True,
                ):
                    for budget in budgets:
                        coordinate = {
                            "adapter_id": "l2b-current-union-selectors-v1",
                            "metric_kind": "selected-book",
                            "fraction_id": fraction,
                            "heldout_block": block,
                            "selector_family": family,
                            "selector_ordinal": selector_ordinal,
                            "selector_id": selector_id,
                            "entry_budget": budget,
                        }
                        # Native is exactly 1 DK higher slate-by-slate.  The
                        # final R4/last selector is the deterministic top cell.
                        base = (
                            170 + fraction_ordinal + block_ordinal
                            + selector_ordinal + budget // 10
                        ) * 1_000_000
                        vector = [base + ordinal * 1_000_000 for ordinal in range(54)]
                        counts = {
                            threshold: sum(v >= threshold * 1_000_000 for v in vector)
                            for threshold in (194, 200, 220, 230)
                        }
                        rows.append({
                            "estimand_class": (
                                "rotated-heldout-exact-k80" if budget == 80
                                else "rotated-heldout-expanded-k"
                            ),
                            "selection_coordinate": coordinate,
                            "entry_budget": budget,
                            "mean_weekly_maximum_micro": {
                                "numerator": sum(vector), "denominator": 54,
                                "unit": "micro_dk",
                            },
                            "thresholds": [{
                                "threshold_dk": threshold,
                                "slates_with_at_least_one_hit": counts[threshold],
                            } for threshold in (194, 200, 220, 230)],
                        })
                        cells.append({
                            "coordinate": coordinate,
                            "slate_rows": [
                                {"weekly_maximum_micro": value} for value in vector
                            ],
                        })
    return ({
        "complete": True,
        "scorecard_sha256": "a" * 64,
        "diagnostic_groups": [{"rows": rows}],
    }, {"aggregate_cells": cells})


def test_summary_reports_complete_surface_and_scientific_boundaries() -> None:
    scorecard, grade = _surface()
    summary = summarize_validated_l2b_v1(scorecard, grade)

    assert summary["complete"] is True
    assert summary["cell_count"] == 300
    assert summary["entry_budget_census"] == {
        "4": 30, "14": 30, "80": 100, "100": 70, "150": 70,
    }
    assert len(summary["all_cells"]) == 300
    assert [row["entry_budget"] for row in summary["descriptive_post_outcome_top_cells"]] == [80, 100, 150]
    assert all(row["winner_selected_after_outcomes"] is True for row in summary["descriptive_post_outcome_top_cells"])
    assert all(row["scientifically_paired_to_current_benchmark"] is False for row in summary["descriptive_post_outcome_top_cells"])
    assert len(summary["matched_fraction_contrasts"]) == 150
    assert all(row["mean_delta_dk"] == "-1.000" for row in summary["matched_fraction_contrasts"])
    assert all(row["weekly_delta_sign_counts"] == {"positive": 0, "tied": 0, "negative": 54} for row in summary["matched_fraction_contrasts"])
    assert summary["inference_guardrails"]["current_benchmark_pair_available"] is False
    markdown = render_compact_markdown_v1(summary)
    assert "all 300 predeclared cells" in markdown
    assert "post-outcome descriptive winner" in markdown
    assert "| current reference | 80 | 178.435 |" in markdown


def test_summary_rejects_incomplete_cell_surface() -> None:
    scorecard, grade = _surface()
    broken_scorecard = deepcopy(scorecard)
    broken_scorecard["diagnostic_groups"][0]["rows"].pop()
    with pytest.raises(CorpusR6L2BGradeSummaryV1Error, match="exactly 300"):
        summarize_validated_l2b_v1(broken_scorecard, grade)


def test_summary_rejects_missing_fraction_mate() -> None:
    scorecard, grade = _surface()
    broken_grade = deepcopy(grade)
    broken_grade["aggregate_cells"][0]["coordinate"]["fraction_id"] = "l2b-native"
    with pytest.raises(CorpusR6L2BGradeSummaryV1Error, match="coordinates differ"):
        summarize_validated_l2b_v1(scorecard, broken_grade)
