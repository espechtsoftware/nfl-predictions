from nfl_dfs.ingest.discoverylab_import import pick_main_classic_slate, slate_rows


def _slate(gtype, n_games, players):
    return {"Operator": "DraftKings", "OperatorGameType": gtype,
            "NumberOfGames": n_games, "DfsSlatePlayers": players}


def _players(n, salary=5000, start=0):
    return [{"SlatePlayerID": start + i, "OperatorPlayerName": f"P{i}",
             "OperatorPosition": "WR", "Team": "kc", "OperatorSalary": salary}
            for i in range(n)]


def test_rejects_zero_salary_pseudo_slate():
    pseudo = _slate("Classic", 16, _players(2000, salary=0))
    real = _slate("Classic", 16, _players(800, start=5000))
    small = _slate("Classic", 3, _players(150, start=9000))
    showdown = _slate("Showdown Captain Mode", 1, _players(100, start=99000))
    got = pick_main_classic_slate([pseudo, small, real, showdown])
    assert got is real
    assert pick_main_classic_slate([pseudo, showdown]) is None


def test_slate_rows_dst_points_merge():
    players = _players(2) + [{
        "SlatePlayerID": 77, "OperatorPlayerName": "Chiefs",
        "OperatorPosition": "DST", "Team": "KC", "OperatorSalary": 3200}]
    dst = {"KC": (11.0, "DEN")}
    df = slate_rows(_slate("Classic", 16, players), 2025, 15, dst)
    assert len(df) == 3
    d = df[df.position == "Def"].iloc[0]
    assert d.dk_points == 11.0 and d.opponent == "DEN" and d.team_abbr == "KC"
    skill = df[df.position == "WR"]
    assert skill.dk_points.isna().all()
    assert (df.season == 2025).all() and (df.week == 15).all()
