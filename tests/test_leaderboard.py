import json

import pandas as pd

from nfl_dfs.analysis.leaderboard import (
    forced_player_counterfactual,
    leaderboard_tables,
    missed_player_rows,
    top_entries,
)
from nfl_dfs.analysis.archetype_research import (
    matched_archetype_pairs,
    summarize_archetype_pairs,
)


def _entries():
    names = [
        "Patrick Mahomes II", "James Cook III", "A Player", "A.J. Brown",
        "B Player", "C Player", "Travis Kelce", "D Player", "Chiefs",
    ]
    slots = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    lineup = " ".join(f"{s} {n}" for s, n in zip(slots, names))
    parsed = [{"slot": s, "player": n} for s, n in zip(slots, names)]
    return pd.DataFrame([
        {"rank": 2, "entry_id": "e2", "points": 210.0, "lineup": lineup,
         "lineup_slots_json": json.dumps(parsed), "players_key": "same"},
        {"rank": 1, "entry_id": "e1", "points": 220.0, "lineup": lineup,
         "lineup_slots_json": json.dumps(parsed), "players_key": "same"},
        {"rank": 21, "entry_id": "e21", "points": 180.0, "lineup": lineup,
         "lineup_slots_json": json.dumps(parsed), "players_key": "other"},
    ])


def test_top_entries_and_leverage_tables():
    entries = _entries()
    assert top_entries(entries, 2).entry_id.tolist() == ["e1", "e2"]
    ownership = pd.DataFrame({
        "display_name": ["Patrick Mahomes", "James Cook", "A.J. Brown"],
        "pct_drafted": [20.0, 10.0, 4.0],
        "fpts": [30.0, 25.0, 28.0],
    })
    entry, players = leaderboard_tables(entries, ownership, n=2)
    assert len(entry) == 2 and entry.duplicate_count.eq(2).all()
    assert entry.ownership_sum.tolist() == [34.0, 34.0]
    assert entry.low_owned_players.eq(1).all()
    cook = players[players.display_name == "James Cook III"].iloc[0]
    assert cook.pct_drafted == 10.0 and cook.top20_appearances == 2


def test_forced_player_counterfactual_separates_generation_and_selection():
    candidates = pd.DataFrame([
        {"players": "A,B,C", "actual_score": 190.0, "selected": True},
        {"players": "A,X,C", "actual_score": 205.0, "selected": False},
        {"players": "D,E,F", "actual_score": 215.0, "selected": False},
    ])
    out = forced_player_counterfactual(candidates, "X")
    assert out["generated"] and not out["selected"]
    assert out["n_candidates_with_player"] == 1
    assert out["best_with_player_score"] == 205.0
    assert out["selection_opportunity"] == 15.0
    assert out["pool_oracle_score"] == 215.0


def test_missed_player_rows_attributes_failure_stage():
    candidates = pd.DataFrame([
        {"season": 2025, "week": 1, "players": "A,B,C",
         "actual_score": 190.0, "selected": True},
        {"season": 2025, "week": 1, "players": "A,X,C",
         "actual_score": 205.0, "selected": False},
    ])
    features = pd.DataFrame([
        {"season": 2025, "week": 1, "id": "A", "name": "Selected",
         "pos": "WR", "team": "A", "salary": 5000, "proj": 15,
         "own_est": .1, "actual": 22},
        {"season": 2025, "week": 1, "id": "X", "name": "Missed",
         "pos": "WR", "team": "B", "salary": 4500, "proj": 10,
         "own_est": .03, "actual": 27, "snap_share_last": .82,
         "spread": 3.5, "implied_team_total": 20.5},
        {"season": 2025, "week": 1, "id": "Z", "name": "Not generated",
         "pos": "TE", "team": "C", "salary": 3000, "proj": 7,
         "own_est": .01, "actual": 25},
    ])
    out = missed_player_rows(candidates, features)
    assert dict(zip(out.player_id, out.failure_stage)) == {
        "X": "selection", "Z": "generation"}
    assert out.set_index("player_id").loc[
        "X", "breakout_archetype"] == "secure_role_bad_environment"


def test_archetype_panel_matching_uses_ordinary_same_slate_control():
    common = {
        "season": 2025, "week": 1, "slate_run_id": "s1", "pos": "WR",
        "salary": 4500, "implied_team_total": 23, "spread": -1,
        "snap_share_l4": .70, "target_share_l4": .18, "carry_share_l4": 0,
        "dk_points_l4": 10, "carry_share_last": 0,
        "carry_share_jump": 0, "snap_share_jump": 0,
        "is_cold_start": False, "depth_rank_delta": 0,
        "team_vacated_target_share": 0,
        "team_vacated_carry_share": 0,
    }
    features = pd.DataFrame([
        {**common, "id": "T", "gsis_id": "T", "name": "Treatment",
         "actual": 28, "target_share_last": .28,
         "target_share_jump": .10, "snap_share_last": .82},
        {**common, "id": "C", "gsis_id": "C", "name": "Control",
         "actual": 11, "target_share_last": .18,
         "target_share_jump": 0, "snap_share_last": .70},
    ])
    pairs = matched_archetype_pairs(features)
    assert len(pairs) == 1
    assert pairs.iloc[0].breakout_archetype == "fast_role_rise"
    assert pairs.iloc[0].treated_gsis_id == "T"
    assert pairs.iloc[0].control_gsis_id == "C"
    summary = summarize_archetype_pairs(pairs)
    assert summary.iloc[0].mean_delta == 17
    assert summary.iloc[0].tail_lift == 1
