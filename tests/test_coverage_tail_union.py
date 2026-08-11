import json

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research import coverage_tail_union as coverage_union
from nfl_dfs.research.candidate_union import select_candidate_union


def _bits(indices: set[int], n: int = 8) -> str:
    mask = np.array([i in indices for i in range(n)], dtype=bool)
    return np.packbits(mask, bitorder="big").tobytes().hex()


def _row(
    season: int,
    week: int,
    ix: int,
    players: str,
    *,
    selected: bool,
    tag: str = "lev",
    actual: float = 180.0,
) -> dict:
    support = _bits({ix % 8})
    return {
        "season": season,
        "week": week,
        "cand_ix": ix,
        "players": players,
        "tag": tag,
        "all_tags": json.dumps([tag]),
        "selected": selected,
        "selected_rank": ix if selected else -1,
        "actual_score": actual,
        "p_line": 0.125,
        "sim_mean": 175.0 + ix,
        "n_worlds": 8,
        "clear_bits_187": support,
        "clear_bits_194": support,
        "clear_bits_200": support,
        "clear_bits_210": support,
        "clear_bits_220": support,
        "score_artifact_uri": f"gs://bucket/{season}_{week}.npz",
        "score_artifact_sha256": "a" * 64,
    }


def _panels(monkeypatch):
    monkeypatch.setattr(coverage_union, "EXPECTED_SLATES", 2)
    monkeypatch.setattr(coverage_union, "EXPECTED_ENTRIES", 2)
    source_rows = []
    for season, week in ((2023, 1), (2024, 1)):
        source_rows.extend([
            _row(
                season, week, ix, f"source-{season}-{ix}",
                selected=ix < 2, actual=180.0 + ix,
            )
            for ix in range(3)
        ])
    source = pd.DataFrame(source_rows)
    treatment = pd.concat([
        source.copy(),
        pd.DataFrame([
            _row(
                2024, 1, 3 + ix, f"coverage-{ix}", selected=False,
                tag="coverage_tail", actual=190.0 + ix,
            )
            for ix in range(12)
        ]),
    ], ignore_index=True)
    union, _ = select_candidate_union(source, treatment, entry_count=2)
    selected = set(union.loc[
        union.selected, ["season", "week", "players"]
    ].itertuples(index=False, name=None))
    treatment["selected"] = [
        (int(row.season), int(row.week), str(row.players)) in selected
        for row in treatment.itertuples()
    ]
    signals = pd.DataFrame([{
        "season": 2024,
        "week": 1,
        "id": "p1",
        "pos": "WR",
        "fp_cov_receiver_source_season": 2023,
        "fp_cov_defense_source_season": 2023,
        "coverage_control_p30": 0.10,
        "coverage_treatment_p30": 0.12,
        "coverage_delta_30": 0.02,
    }])
    return source, treatment, signals


def test_coverage_union_requires_exact_novel_budget_and_reproduces_selection(
        monkeypatch):
    source, treatment, signals = _panels(monkeypatch)
    report = coverage_union.evaluate_union(source, treatment, signals)
    assert report["mechanical_checks"][
        "strict_prior_receiver_and_defense_signal"]
    assert report["candidate_audit"]["novel_coverage_candidates"] == 12
    assert report["candidate_audit"]["source_candidates"] == 6


@pytest.mark.parametrize(
    "column", [
        "fp_cov_receiver_source_season",
        "fp_cov_defense_source_season",
    ],
)
def test_coverage_union_rejects_non_prior_source(monkeypatch, column):
    source, treatment, signals = _panels(monkeypatch)
    signals.loc[0, column] = 2024
    with pytest.raises(ValueError, match="non-prior season"):
        coverage_union.evaluate_union(source, treatment, signals)
