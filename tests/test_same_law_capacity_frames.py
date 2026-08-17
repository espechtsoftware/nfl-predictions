from __future__ import annotations

import json

import pandas as pd
import pytest

from nfl_dfs.research.exact_p_generator_census import BASE_FAMILIES
from nfl_dfs.research.same_law_capacity_curve import BOOK_ORDER
from nfl_dfs.research.same_law_capacity_frames import (
    EXISTING_PANELS,
    NEW_PANELS,
    prepare_capacity_frames,
)
from nfl_dfs.research.same_law_capacity_sources import (
    EXACT_P_GENERATION,
    EXACT_P_SHA256,
    EXACT_P_URI,
    PRELOCK_ROW_HASH,
    PROTOCOL_SHA256,
    SEED_LEDGER_SHA256,
)


def _source_binding(new_rows: int) -> dict:
    return {
        "version": "same-law-capacity-source-binding-v1",
        "run_id": "20260817-same-law-capacity-curve-v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "seed_ledger_sha256": SEED_LEDGER_SHA256,
        "generation_validation_sha256": "a" * 64,
        "prelock_row_hash": PRELOCK_ROW_HASH,
        "prelock_candidate_rows": 68493,
        "prelock_slates": 54,
        "new_books": 45,
        "new_book_slate_cells": 2430,
        "new_candidate_rows": new_rows,
        "exact_p_uri": EXACT_P_URI,
        "exact_p_generation": EXACT_P_GENERATION,
        "exact_p_sha256": EXACT_P_SHA256,
        "exact_p_slates": 54,
        "uses_realized_outcome_values": False,
        "uses_outcome_derived_exact_p_identity": True,
        "candidate_scores_inspected": False,
        "capacity_statistics_computed": False,
        "production_change_licensed": False,
        "disposition": "valid-immutable-capacity-sources",
    }


@pytest.fixture(scope="module")
def capacity_frames():
    slate_grid = [
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]
    players = pd.DataFrame([
        {
            "season": season,
            "week": week,
            "id": f"p{slot}",
            "pos": "WR",
            "team": "A",
            "opp": "B",
            "game_id": f"{season}-{week}-A-B",
            "salary": 5000,
        }
        for season, week in slate_grid
        for slot in range(9)
    ])
    exact_p = pd.DataFrame([
        {
            "season": season,
            "week": week,
            "players": ",".join(f"p{slot}" for slot in range(9)),
        }
        for season, week in slate_grid
    ])
    all_families = json.dumps(list(BASE_FAMILIES))
    candidate_rows = []
    old_cells = [
        (panel, season, week)
        for panel in EXISTING_PANELS
        for season, week in slate_grid
    ]
    base, extra = divmod(68493, len(old_cells))
    for cell_index, (panel, season, week) in enumerate(old_cells):
        count = base + int(cell_index < extra)
        for cand_ix in range(count):
            candidate_rows.append({
                "panel_run_id": panel,
                "season": season,
                "week": week,
                "cand_ix": cand_ix,
                "players": ",".join(f"p{slot}" for slot in range(9)),
                "tag": "lev",
                "all_tags": all_families if cand_ix == 0 else '["lev"]',
            })
    mechanics = []
    for panel, replicate in NEW_PANELS.items():
        for season, week in slate_grid:
            candidate_rows.append({
                "panel_run_id": panel,
                "season": season,
                "week": week,
                "cand_ix": 0,
                "players": ",".join(f"p{slot}" for slot in range(9)),
                "tag": "lev",
                "all_tags": all_families,
            })
            mechanics.append({
                "replicate": replicate,
                "season": season,
                "week": week,
                "panel_run_id": panel,
                "candidate_rows": 1,
                "minimum_cand_ix": 0,
                "maximum_cand_ix": 0,
                "distinct_cand_ix": 1,
                "families_present": list(BASE_FAMILIES),
                "all_rosters_nine_unique": True,
                "all_rosters_legal": True,
            })
    candidates = pd.DataFrame(candidate_rows)
    completion = {"candidate_mechanics": mechanics}
    return players, candidates, exact_p, completion


def test_capacity_frames_bind_complete_identity_only_population(capacity_frames):
    players, candidates, exact_p, completion = capacity_frames

    prepared = prepare_capacity_frames(
        players,
        candidates,
        exact_p,
        _source_binding(2430),
        completion,
    )

    prepared_players, prepared_candidates, prepared_exact_p, receipt = prepared
    assert len(prepared_players) == 54 * 9
    assert len(prepared_candidates) == 68493 + 2430
    assert len(prepared_exact_p) == 54
    assert set(prepared_candidates["replicate"]) == set(BOOK_ORDER)
    assert receipt["book_slate_cells"] == 2700
    assert receipt["disposition"] == "valid-identity-only-capacity-frames"
    assert receipt["uses_realized_outcome_values"] is False


def test_capacity_frames_reject_score_column_or_mechanics_drift(capacity_frames):
    players, candidates, exact_p, completion = capacity_frames
    changed = candidates.copy()
    changed["actual_score"] = 0.0
    with pytest.raises(ValueError, match="candidate columns differ"):
        prepare_capacity_frames(
            players, changed, exact_p, _source_binding(2430), completion,
        )

    changed_completion = {"candidate_mechanics": [
        dict(row) for row in completion["candidate_mechanics"]
    ]}
    changed_completion["candidate_mechanics"][0]["candidate_rows"] = 2
    changed_completion["candidate_mechanics"][0]["maximum_cand_ix"] = 1
    changed_completion["candidate_mechanics"][0]["distinct_cand_ix"] = 2
    with pytest.raises(ValueError, match="row count differs"):
        prepare_capacity_frames(
            players,
            candidates,
            exact_p,
            _source_binding(2430),
            changed_completion,
        )
