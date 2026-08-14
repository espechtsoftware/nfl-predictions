import numpy as np
import pytest
from pathlib import Path

from nfl_dfs.optimizer.lineup import select_from_support
from nfl_dfs.research.selector_resampling import (
    analyze_selector_resampling,
    summarize_selector_resampling,
)


def _fixture(candidates=12, worlds=240, entries=5):
    rng = np.random.default_rng(91)
    totals = rng.normal(
        np.linspace(185, 205, candidates)[:, None],
        18,
        size=(candidates, worlds),
    ).astype(np.float32)
    clears = totals >= 194
    picked = select_from_support(
        clears, clears.mean(axis=1), totals.mean(axis=1), entries
    )
    return totals, picked


def test_selector_resampling_is_deterministic_and_score_free():
    totals, picked = _fixture()
    left = analyze_selector_resampling(
        totals, picked, season=2025, week=4, entry_count=5,
        bootstrap_resamples=8, expected_world_count=240,
    )
    right = analyze_selector_resampling(
        totals, picked, season=2025, week=4, entry_count=5,
        bootstrap_resamples=8, expected_world_count=240,
    )
    assert left == right
    assert left["full_book_reproduced"]
    assert left["bootstrap"]["pairwise_overlap"]["pair_count"] == 28
    assert sum(
        left["bootstrap"]["frequency_counts"].values()
    ) == totals.shape[0]
    assert len(left["candidate_frequencies"]) == totals.shape[0]


def test_selector_resampling_rejects_wrong_full_book_or_world_count():
    totals, picked = _fixture()
    wrong = picked.copy()
    wrong[0], wrong[1] = wrong[1], wrong[0]
    with pytest.raises(ValueError, match="does not reproduce"):
        analyze_selector_resampling(
            totals, wrong, season=2025, week=4, entry_count=5,
            bootstrap_resamples=8, expected_world_count=240,
        )
    with pytest.raises(ValueError, match="world count differs"):
        analyze_selector_resampling(
            totals, picked, season=2025, week=4, entry_count=5,
            bootstrap_resamples=8, expected_world_count=241,
        )


def test_selector_resampling_summary_has_fixed_bands_and_seasons():
    totals, picked = _fixture()
    rows = [
        analyze_selector_resampling(
            totals, picked, season=season, week=4, entry_count=5,
            bootstrap_resamples=8, expected_world_count=240,
        )
        for season in (2024, 2025)
    ]
    out = summarize_selector_resampling(rows)
    assert out["overall"]["slates"] == 2
    assert set(out["by_season"]) == {"2024", "2025"}
    # The production bands are expressed in exact-80 overlap units. A tiny
    # fixture therefore falls into the low label by construction.
    assert out["overall"]["stability_band"] == "low"
    assert all(
        "candidate_frequencies" not in slate for slate in out["slates"]
    )


def test_cloud_analyzer_query_is_score_free_and_launcher_is_frozen():
    root = Path(__file__).resolve().parents[1]
    analyzer = (root / "scripts/analyze_selector_resampling.py").read_text()
    query = analyzer.split("return query_df", 1)[1].split(")\n\n", 1)[0]
    assert "actual_score" not in query
    assert "players" not in query
    assert "score_artifact_uri" in query
    assert "if_generation_match=0" in analyzer

    launcher = (root / "scripts/cloud_selector_resampling.sh").read_text()
    assert "20260813-sis-asoe-treatment-r0-v1" in launcher
    assert "bootstrap_resamples=32" in launcher
    assert "reads_realized_outcomes=0" in launcher
