from nfl_dfs.optimizer import lineup


def test_min_lowown_uses_passed_policy_not_process_environment(monkeypatch):
    players = [
        {"id": "qb", "name": "QB", "pos": "QB", "team": "A", "opp": "B",
         "game_id": "g1", "salary": 5000, "proj": 20, "low_own": False},
        {"id": "rb1", "name": "RB1", "pos": "RB", "team": "C", "opp": "D",
         "game_id": "g2", "salary": 5000, "proj": 20, "low_own": False},
        {"id": "rb2", "name": "RB2", "pos": "RB", "team": "E", "opp": "F",
         "game_id": "g3", "salary": 5000, "proj": 20, "low_own": False},
        {"id": "wr1", "name": "WR1", "pos": "WR", "team": "A", "opp": "B",
         "game_id": "g1", "salary": 5000, "proj": 20, "low_own": False},
        {"id": "wr2", "name": "WR2", "pos": "WR", "team": "A", "opp": "B",
         "game_id": "g1", "salary": 5000, "proj": 20, "low_own": False},
        {"id": "wr3", "name": "WR3", "pos": "WR", "team": "B", "opp": "A",
         "game_id": "g1", "salary": 5000, "proj": 20, "low_own": False},
        {"id": "te", "name": "TE", "pos": "TE", "team": "G", "opp": "H",
         "game_id": "g4", "salary": 5000, "proj": 20, "low_own": False},
        {"id": "flex", "name": "FLEX", "pos": "WR", "team": "I", "opp": "J",
         "game_id": "g5", "salary": 5000, "proj": 20, "low_own": False},
        {"id": "dst", "name": "DST", "pos": "DST", "team": "K", "opp": "L",
         "game_id": "g6", "salary": 5000, "proj": 20, "low_own": False},
    ]
    monkeypatch.setenv("MIN_LOWOWN", "2")
    result = lineup.optimize(
        players,
        stack=lineup.StackRules(qb_stack_min=2, bring_back_min=1),
        env={"MIN_LINEUP_SALARY": "0", "MIN_LOWOWN": "0"},
    )
    assert result is not None
