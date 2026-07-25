import pandas as pd

from nfl_dfs.ingest.sportsdataio_import import pick_main_dk_slate, slate_rows


def _slate(operator, n_players, gtype="Classic", start_id=0):
    return {
        "Operator": operator, "OperatorGameType": gtype,
        "DfsSlatePlayers": [
            {"SlatePlayerID": start_id + i, "OperatorPlayerName": f"Player {i}",
             "OperatorSalary": 3000 + 100 * i, "OperatorPosition": "WR",
             "Team": "kc"} for i in range(n_players)
        ],
    }


def test_picks_largest_dk_slate():
    slates = [_slate("FanDuel", 300), _slate("DraftKings", 40, "Showdown"),
              _slate("DraftKings", 250)]
    assert len(pick_main_dk_slate(slates)["DfsSlatePlayers"]) == 250
    assert pick_main_dk_slate([_slate("FanDuel", 10)]) is None


def test_slate_rows_normalization():
    slate = _slate("DraftKings", 2)
    slate["DfsSlatePlayers"].append(
        {"SlatePlayerID": 99, "OperatorPlayerName": "KC ",
         "OperatorSalary": 3200, "OperatorPosition": "DST", "Team": "kc"})
    slate["DfsSlatePlayers"].append(  # missing salary -> dropped
        {"SlatePlayerID": 100, "OperatorPlayerName": "No Salary",
         "OperatorSalary": None, "OperatorPosition": "WR", "Team": "kc"})
    df = slate_rows(slate, 2023, 5)
    assert len(df) == 3
    assert set(df.columns) >= {"season", "week", "display_name", "position",
                               "team_abbr", "salary", "rotoguru_gid"}
    dst = df[df.rotoguru_gid == "sdio-99"].iloc[0]
    assert dst.position == "Def" and dst.team_abbr == "KC"
    assert (df.season == 2023).all() and (df.week == 5).all()
