from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.research.exact_p_identity_source import (
    derive_corrected_p_identities,
    preflight_receipt,
)
from nfl_dfs.research.final_forensic import TAILS


def _fixture() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rows = [
        ("qb_a", "QB", "A", "B", "A@B", 7000, 30),
        ("rb_c", "RB", "C", "D", "C@D", 6000, 22),
        ("rb_d", "RB", "D", "C", "C@D", 5500, 18),
        ("wr_a", "WR", "A", "B", "A@B", 6500, 30),
        ("wr_b", "WR", "B", "A", "A@B", 6000, 20),
        ("wr_c", "WR", "C", "D", "C@D", 5500, 25),
        ("wr_d", "WR", "D", "C", "C@D", 5000, 18),
        ("te_a", "TE", "A", "B", "A@B", 4500, 15),
        ("dst_a", "DST", "A", "B", "A@B", 3000, 10),
    ]
    players = pd.DataFrame(
        rows,
        columns=["id", "pos", "team", "opp", "game_id", "salary", "actual"],
    )
    players["season"] = 2025
    players["week"] = 1
    roster = sorted(players.id.tolist())
    candidates = pd.DataFrame([{
        "season": 2025,
        "week": 1,
        "players": ",".join(roster),
    }])
    score = float(players.actual.sum())
    source = {
        "records": [{"season": 2025, "week": 1, "exact_p": score}],
        "tail_counts": {
            "exact_p": {
                str(tail): int(score >= tail) for tail in TAILS
            },
        },
    }
    return players, candidates, source


def test_corrected_identity_source_reproduces_but_persists_no_outcome():
    result = derive_corrected_p_identities(*_fixture(), expected_slates=1)

    assert result["slates"] == 1
    assert result["roster_slots"] == 9
    assert result["all_rosters_independently_legal"]
    assert result["exact_stack_scores_reproduced"]
    assert not result["persisted_outcome_values"]
    assert not result["scientific_result_licensed"]
    assert set(result["records"][0]) == {"season", "week", "players"}
    encoded = json.dumps(result)
    assert "actual_score" not in encoded
    assert "selected_rank" not in encoded


def test_corrected_identity_source_rejects_score_or_candidate_leakage():
    players, candidates, source = _fixture()
    source["records"][0]["exact_p"] += 1.0
    with pytest.raises(ValueError, match="score does not reproduce"):
        derive_corrected_p_identities(
            players, candidates, source, expected_slates=1,
        )

    players, candidates, source = _fixture()
    candidates["selected"] = False
    with pytest.raises(ValueError, match="not identity-only"):
        derive_corrected_p_identities(
            players, candidates, source, expected_slates=1,
        )


def test_preflight_receipt_strips_identities():
    result = {
        "slates": 18,
        "roster_slots": 162,
        "records": [
            {"season": 2023, "week": week, "players": [f"p{i}" for i in range(9)]}
            for week in range(1, 19)
        ],
        "scientific_result_licensed": False,
    }

    receipt = preflight_receipt(result)

    assert "records" not in receipt
    assert receipt["identities_persisted"] is False
    assert receipt["preflight_season"] == 2023


def test_corrected_identity_cloud_contract_is_create_only_and_staged():
    runner = Path(
        "scripts/run_exact_p_corrected_identity_source.py"
    ).read_text(encoding="utf-8")
    launcher = Path(
        "scripts/cloud_exact_p_corrected_identity_source.sh"
    ).read_text(encoding="utf-8")
    finisher = Path(
        "scripts/cloud_finish_exact_p_corrected_identity_source.sh"
    ).read_text(encoding="utf-8")

    candidate_query = runner.split(
        "candidates = _query", 1,
    )[1].split("if mode ==", 1)[0]
    assert "actual_score" not in candidate_query
    assert "selected" not in candidate_query
    assert "tag" not in candidate_query
    assert "if_generation_match=0" in runner
    assert "strict 2023 corrected-identity preflight is absent" in launcher
    assert "[ ! -e \"$OUT/report.json\" ]" in finisher
    assert '"records" in r' in finisher

