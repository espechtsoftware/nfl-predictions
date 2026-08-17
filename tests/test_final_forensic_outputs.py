from __future__ import annotations

import pandas as pd

from nfl_dfs.research.final_forensic_outputs import (
    candidate_scorecard,
    player_capture_slate,
    portfolio_slate,
    warehouse_slate_frames,
)


def _players():
    rows = []
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
    for index in range(89):
        position = positions[index % len(positions)]
        rows.append({
            "id": f"p{index}", "pos": position, "team": "A" if index < 7 else "B",
            "opp": "B" if index < 7 else "A", "game_id": "A@B",
            "kickoff_time": "13:00",
            "salary": 5500, "actual": 10.0 + index,
            "mean_projection": 9.0 + index, "proj_p90": 15.0 + index,
        })
    return pd.DataFrame(rows)


def _candidates():
    return pd.DataFrame([
        {
            "players": ",".join(f"p{i}" for i in range(rank, rank + 9)),
            "actual_score": 126.0 + rank,
            "selected": True, "selected_rank": rank,
            "cand_ix": rank,
            "p_line": rank / 100, "sim_mean": 120 + rank,
            "sim_q99": 180 + rank, "tag": "fixture",
        }
        for rank in range(80)
    ])


def _hpcs():
    ids = [f"p{i}" for i in range(9)]
    return {
        layer: {"players": ids, "actual_score": score}
        for layer, score in (
            ("H_no_salary_floor", 225), ("H", 220), ("P", 210),
            ("C", 205), ("S", 205),
        )
    } | {"gaps": {"player_support": 10, "construction": 5, "selection": 0}}


def test_portfolio_and_capture_outputs_preserve_exact80_semantics():
    portfolio = portfolio_slate(_players(), _candidates(), _hpcs(), known_winner_score=230)
    assert portfolio["entries"] == 80
    assert portfolio["outcome_blind_selected_prefixes"]["80"]["best"] == 205
    assert portfolio["known_first_place"]["selected_beats"] is False

    capture = player_capture_slate(_players(), _candidates(), _hpcs())
    assert capture["threshold_funnel"]["20"]["salary_listed"] == 79
    assert capture["calibration"]["WR"]["rows"] > 0

    additive = _hpcs() | {
        "H_DK_legal": {"players": [f"p{i}" for i in range(9)], "actual_score": 230},
        "H_strategy": {"players": [f"p{i}" for i in range(9)], "actual_score": 220},
    }
    additive_capture = player_capture_slate(
        _players(), _candidates(), additive,
    )
    funnel = additive_capture["threshold_funnel"]["20"]
    assert "oracle_H_DK_legal" in funnel
    assert "oracle_H_strategy" in funnel
    # Legacy fields remain present for existing consumers.
    assert "oracle_H" in funnel
    assert "oracle_P" in funnel


def test_candidate_scorecard_reports_rank_skill_and_tag_yield():
    report = candidate_scorecard(_candidates())
    assert report["selected_count"] == 80
    assert report["rank_skill"]["p_line"]["spearman"] == 1.0
    assert report["generator_yield"][0]["tag"] == "fixture"


def test_warehouse_frames_retain_full_corpus_exact80_and_hpcs_rosters():
    players = _players()
    chosen = ["p0", "p1", "p10", "p3", "p4", "p5", "p6", "p7", "p8"]
    layout = {
        "p0": ("A", "B", "A@B"),
        "p1": ("A", "B", "A@B"),
        "p10": ("C", "D", "C@D"),
        "p3": ("A", "B", "A@B"),
        "p4": ("A", "B", "A@B"),
        "p5": ("A", "B", "A@B"),
        "p6": ("A", "B", "A@B"),
        "p7": ("B", "A", "A@B"),
        "p8": ("C", "D", "C@D"),
    }
    for player_id, (team, opponent, game_id) in layout.items():
        mask = players.id.eq(player_id)
        players.loc[mask, ["team", "opp", "game_id"]] = [team, opponent, game_id]
    score = float(players.set_index("id").loc[chosen, "actual"].sum())
    hpcs = {
        layer: {
            "players": chosen,
            "actual_score": score,
            **({"solver_status": "Optimal"} if layer in {
                "H_DK_legal", "H_strategy", "H", "P",
            } else {}),
        }
        for layer in (
            "H_DK_legal", "H_no_salary_floor", "H_strategy",
            "H", "P", "C", "S",
        )
    } | {
        "gaps": {
            "player_support": 0.0,
            "construction": 0.0,
            "selection": 0.0,
        },
        "strategy_gaps": {
            "non_salary_strategy_constraints": 0.0,
            "salary_floor": 0.0,
            "combined_strategy_constraints": 0.0,
        },
        "construction_policy": {
            "qb_stack_min": 2,
            "bring_back_min": 1,
            "forbid_two_rb_same_team": True,
            "forbid_rb_vs_dst": True,
            "minimum_salary": 49_000,
            "maximum_salary": 50_000,
        },
    }

    frames = warehouse_slate_frames(
        players,
        _candidates(),
        hpcs,
        scope="fixture",
        season=2025,
        week=1,
        manifest_sha256="a" * 64,
        analysis_code_sha="b" * 40,
        analysis_image="repo/image@sha256:" + "c" * 64,
    )

    assert len(frames["player_corpus"]) == 89
    assert not frames["player_corpus"].feature_missing_any.any()
    assert frames["player_corpus"].player_name.iloc[0] == "p0"
    assert frames["player_corpus"].source_features_json.str.startswith("{").all()
    assert len(frames["candidate_corpus"]) == 80
    assert frames["candidate_corpus"].source_candidate_json.str.startswith("{").all()
    assert frames["actual_selections"].selected_rank.tolist() == list(range(80))
    assert frames["oracle_rosters"].layer.tolist() == [
        "H_DK_legal", "H_no_salary_floor", "H_strategy", "H", "P", "C", "S",
    ]
    assert frames["oracle_rosters"].legality_verified.all()
