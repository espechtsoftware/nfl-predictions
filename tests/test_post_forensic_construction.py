from __future__ import annotations

import pandas as pd

from nfl_dfs.research.final_forensic import _solve_oracle
from nfl_dfs.research.post_forensic_construction import (
    PROTOCOL_ID,
    analyze_exact_stack_construction,
)


def _players() -> pd.DataFrame:
    rows = [
        ("qb_a", "QB", "A", "B", "A@B", 7000, 30),
        ("qb_c", "QB", "C", "D", "C@D", 6500, 20),
        ("rb_a", "RB", "A", "B", "A@B", 6500, 25),
        ("rb_b", "RB", "B", "A", "A@B", 6000, 20),
        ("rb_c", "RB", "C", "D", "C@D", 6000, 22),
        ("rb_d", "RB", "D", "C", "C@D", 5500, 18),
        ("wr_a", "WR", "A", "B", "A@B", 6500, 30),
        ("wr_b", "WR", "B", "A", "A@B", 6000, 20),
        ("wr_c", "WR", "C", "D", "C@D", 5500, 25),
        ("wr_d", "WR", "D", "C", "C@D", 5000, 18),
        ("wr_e", "WR", "E", "F", "E@F", 4500, 40),
        ("te_a", "TE", "A", "B", "A@B", 4500, 15),
        ("te_c", "TE", "C", "D", "C@D", 4000, 12),
        ("dst_a", "DST", "A", "B", "A@B", 3000, 10),
        ("dst_c", "DST", "C", "D", "C@D", 2500, 8),
    ]
    frame = pd.DataFrame(
        rows,
        columns=["id", "pos", "team", "opp", "game_id", "salary", "actual"],
    )
    frame["season"] = 2025
    frame["week"] = 1
    frame["actual_ownership"] = 10.0
    return frame


def test_exact_stack_addendum_reproduces_old_p_and_restricts_use():
    players = _players()
    roster = [
        "qb_a", "rb_c", "rb_d", "wr_a", "wr_b", "wr_c", "wr_d",
        "te_a", "dst_a",
    ]
    actuals = players.set_index("id").actual.to_dict()
    score = sum(actuals[player] for player in roster)
    candidates = pd.DataFrame([{
        "season": 2025,
        "week": 1,
        "candidate_index": 0,
        "players": ",".join(roster),
        "actual_score": score,
        "selected": True,
        "selected_rank": 0,
    }])
    support = set(roster)
    loose = _solve_oracle(
        players, support, min_salary=49_000,
        qb_stack_min=1, bring_back_min=0,
    )
    published = pd.DataFrame([
        {
            "season": 2025,
            "week": 1,
            "layer": layer,
            "players": ",".join(loose["players"]),
            "actual_score": loose["actual_score"],
        }
        for layer in ("H_no_salary_floor", "H", "P", "C", "S")
    ])

    result = analyze_exact_stack_construction(
        players,
        candidates,
        published,
        expected_slates=1,
        expected_entries=1,
    )

    assert result["protocol_id"] == PROTOCOL_ID
    assert result["production_stack_contract"] == {
        "qb_stack_min": 2,
        "bring_back_min": 1,
    }
    assert result["expected_entries"] == 1
    assert result["slates"] == 1
    assert result["swap_distance"]["minimum_player_swaps_to_exact_p"]["mean"] == 0
    assert result["records"][0]["exact_p"] == score
    assert result["uses_realized_outcomes"] is True
    assert "not a historical arm" in result["use_restriction"]
