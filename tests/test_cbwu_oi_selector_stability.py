from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.optimizer.lineup import select_tail_entries
from nfl_dfs.research.cbwu_oi_selector_stability import (
    analyze_paired_selector_stability,
    stratified_world_samples,
    summarize_paired_selector_stability,
)


def _fixture(candidates=12, blocks=3, worlds=60, entries=5):
    rng = np.random.default_rng(144)
    canonical = rng.normal(
        np.linspace(180, 207, candidates)[:, None], 17,
        size=(candidates, blocks * worlds),
    ).astype(np.float32)
    treatment = canonical.copy()
    treatment[[1, 5, 9]] += rng.normal(
        2, 3, size=(3, blocks * worlds),
    ).astype(np.float32)
    canonical_ids = [[f"p{index}-{slot}" for slot in range(9)]
                     for index in range(candidates)]
    treatment_ids = canonical_ids[:6] + [
        [f"q{index}-{slot}" for slot in range(9)]
        for index in range(6, candidates)
    ]
    control_pick = select_tail_entries(
        canonical, entries, 194.0, env={"SELECT_LSE": "0"}
    )
    treatment_pick = select_tail_entries(
        treatment, entries, 194.0, env={"SELECT_LSE": "0"}
    )
    return (
        canonical, canonical_ids, [canonical_ids[index] for index in control_pick],
        treatment, treatment_ids,
        [treatment_ids[index] for index in treatment_pick],
    )


def test_stratified_samples_are_deterministic_disjoint_and_balanced():
    left, right, boots = stratified_world_samples(
        season=2025, week=7, block_count=3, worlds_per_block=60,
        bootstrap_resamples=8, bootstrap_per_block=12,
    )
    again = stratified_world_samples(
        season=2025, week=7, block_count=3, worlds_per_block=60,
        bootstrap_resamples=8, bootstrap_per_block=12,
    )
    assert np.array_equal(left, again[0])
    assert np.array_equal(right, again[1])
    assert all(np.array_equal(a, b) for a, b in zip(boots, again[2], strict=True))
    assert len(left) == len(right) == 90
    assert set(left).isdisjoint(set(right))
    assert set(left) | set(right) == set(range(180))
    assert all(len(sample) == 36 for sample in boots)
    for sample in boots:
        assert [int(np.sum((sample // 60) == block)) for block in range(3)] == [
            12, 12, 12,
        ]


def test_paired_selector_stability_is_deterministic_and_score_free():
    fixture = _fixture()
    kwargs = dict(
        season=2025, week=7, entry_count=5, block_count=3,
        worlds_per_block=60, bootstrap_resamples=8, bootstrap_per_block=12,
    )
    left = analyze_paired_selector_stability(*fixture, **kwargs)
    right = analyze_paired_selector_stability(*fixture, **kwargs)
    assert left == right
    assert left["uses_realized_outcomes"] is False
    assert left["samples_identical_across_pools"] is True
    assert left["canonical"]["full_book_reproduced"] is True
    assert left["cbwu_oi"]["full_book_reproduced"] is True
    assert left["canonical"]["bootstrap"]["pairwise_overlap"]["pair_count"] == 28
    assert len(left["candidate_frequencies"]["canonical"]) == 12
    assert 0 <= left["cross_pool_identity_overlap"]["full"] <= 5


def test_paired_selector_stability_rejects_bad_receipt_and_budget():
    fixture = list(_fixture())
    kwargs = dict(
        season=2025, week=7, entry_count=5, block_count=3,
        worlds_per_block=60, bootstrap_resamples=8, bootstrap_per_block=12,
    )
    wrong = list(fixture[2])
    wrong[0], wrong[1] = wrong[1], wrong[0]
    fixture[2] = wrong
    with pytest.raises(ValueError, match="does not reproduce"):
        analyze_paired_selector_stability(*fixture, **kwargs)

    fixture = list(_fixture())
    fixture[3] = fixture[3][:-1]
    fixture[4] = fixture[4][:-1]
    with pytest.raises(ValueError, match="candidate budgets differ"):
        analyze_paired_selector_stability(*fixture, **kwargs)


def test_paired_summary_has_seasons_deltas_and_no_frequencies():
    fixture = _fixture()
    rows = [
        analyze_paired_selector_stability(
            *fixture, season=season, week=7, entry_count=5, block_count=3,
            worlds_per_block=60, bootstrap_resamples=8,
            bootstrap_per_block=12,
        )
        for season in (2024, 2025)
    ]
    result = summarize_paired_selector_stability(rows)
    assert result["overall"]["slates"] == 2
    assert set(result["by_season"]) == {"2024", "2025"}
    assert "mean_pairwise_overlap" in result["overall"][
        "cbwu_oi_minus_canonical"
    ]
    assert all("candidate_frequencies" not in row for row in result["slates"])


def test_protocol_and_runner_are_outcome_free():
    root = Path(__file__).resolve().parents[1]
    protocol = (root / "reports/2026-08-15-cbwu-oi-selector-stability-protocol.md").read_text()
    assert "81c8d0ff7750c7781e9c9181699b3bdf397d6161c8bf6e7a91025d233236cb01" not in protocol
    assert "32 resamples" in protocol
    assert "cannot score C or S" in protocol
    runner = (root / "scripts/run_cbwu_oi_selector_stability.py").read_text()
    query = runner.split("sources = _query", 1)[1].split(")\n    players", 1)[0]
    assert "actual_score" not in query
    assert "actual_ownership" not in query
    assert "if_generation_match=0" in runner
    launcher = (root / "scripts/cloud_cbwu_oi_selector_stability.sh").read_text()
    assert "bootstrap_resamples=32" in launcher
    assert "uses_realized_outcomes=false" in launcher
