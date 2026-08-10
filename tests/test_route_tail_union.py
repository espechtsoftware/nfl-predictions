import json

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research import route_tail_union as route_union
from nfl_dfs.research.candidate_union import select_candidate_union


def _bits(indices: set[int], n: int = 8) -> str:
    mask = np.array([i in indices for i in range(n)], dtype=bool)
    return np.packbits(mask, bitorder="big").tobytes().hex()


def _row(season: int, week: int, ix: int, players: str, *,
         selected: bool, tag: str = "lev", actual: float = 180.0) -> dict:
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
    monkeypatch.setattr(route_union, "EXPECTED_SLATES", 2)
    monkeypatch.setattr(route_union, "EXPECTED_ENTRIES", 2)
    slates = [(2023, 1), (2024, 1)]
    source_rows = []
    for season, week in slates:
        source_rows.extend([
            _row(season, week, ix, f"source-{season}-{ix}",
                 selected=ix < 2, actual=180.0 + ix)
            for ix in range(3)
        ])
    source = pd.DataFrame(source_rows)
    treatment = source.copy()
    novel = [
        _row(2024, 1, 3 + ix, f"route-{ix}", selected=False,
             tag="route_tail", actual=190.0 + ix)
        for ix in range(12)
    ]
    treatment = pd.concat([treatment, pd.DataFrame(novel)], ignore_index=True)
    union, _ = select_candidate_union(source, treatment, entry_count=2)
    selected = set(union.loc[union.selected, ["season", "week", "players"]]
                   .itertuples(index=False, name=None))
    treatment["selected"] = [
        (int(r.season), int(r.week), str(r.players)) in selected
        for r in treatment.itertuples()
    ]
    signals = pd.DataFrame([
        {
            "season": 2024,
            "week": 1,
            "id": "p1",
            "pos": "WR",
            "fp_route_source_season": 2023,
            "fp_route_source_week": 18,
            "route_control_p30": 0.10,
            "route_treatment_p30": 0.12,
            "route_delta_30": 0.02,
        },
    ])
    return source, treatment, signals


def test_route_union_requires_exact_added_budget_and_reproduces_selection(
        monkeypatch):
    source, treatment, signals = _panels(monkeypatch)
    report = route_union.evaluate_union(source, treatment, signals)
    assert report["mechanical_checks"]["strict_prior_route_signal"]
    assert report["candidate_audit"]["novel_route_candidates"] == 12
    assert report["candidate_audit"]["source_candidates"] == 6


def test_route_union_rejects_same_week_signal(monkeypatch):
    source, treatment, signals = _panels(monkeypatch)
    signals.loc[0, "fp_route_source_season"] = 2024
    signals.loc[0, "fp_route_source_week"] = 1
    with pytest.raises(ValueError, match="same/future week"):
        route_union.evaluate_union(source, treatment, signals)
