from nfl_dfs.ingest import dk_client


def payload():
    return {
        "competitions": [
            {"competitionId": 111, "startTime": "2025-09-07T17:00:00Z"},
        ],
        "draftables": [
            {
                "playerId": 1,
                "displayName": "Justin Jefferson",
                "teamAbbreviation": "MIN",
                "position": "WR",
                "salary": 8900,
                "rosterSlotId": 511,
                "status": "None",
                "competition": {"competitionId": 111},
                "draftStatAttributes": [{"id": 90, "value": "21.3"}],
            },
            # Same player repeated in the FLEX slot — must be deduped
            {
                "playerId": 1,
                "displayName": "Justin Jefferson",
                "teamAbbreviation": "MIN",
                "position": "WR",
                "salary": 8900,
                "rosterSlotId": 512,
                "status": "None",
                "competition": {"competitionId": 111},
            },
            {
                "playerId": 2,
                "displayName": "Ja'Marr Chase",
                "teamAbbreviation": "CIN",
                "position": "WR",
                "salary": 9100,
                "rosterSlotId": 511,
                "status": "Q",
                "competition": {"competitionId": 999},  # unknown comp -> null game_start
                "draftStatAttributes": [{"id": 90, "value": "-"}],
            },
        ],
    }


def test_draftables_frame_dedupes_roster_slots():
    df = dk_client.draftables_frame(123, "classic", payload())
    assert len(df) == 2
    assert set(df.dk_player_id) == {1, 2}


def test_draftables_frame_fields():
    df = dk_client.draftables_frame(123, "classic", payload())
    jj = df[df.dk_player_id == 1].iloc[0]
    assert jj.salary == 8900
    assert jj.game_start == "2025-09-07T17:00:00Z"
    assert jj.dk_ppg == 21.3
    import pandas as pd

    chase = df[df.dk_player_id == 2].iloc[0]
    assert pd.isna(chase.game_start)
    assert pd.isna(chase.dk_ppg)  # non-numeric attr value handled


def test_classify_slate():
    assert dk_client.classify_slate({"gameTypeDescription": "Showdown Captain Mode"}) == "showdown"
    assert dk_client.classify_slate({"gameType": "NFL Captain"}) == "showdown"
    assert dk_client.classify_slate({"gameTypeDescription": "Classic"}) == "classic"


def test_render_sql_placeholders(tmp_path):
    from nfl_dfs.bq import render_sql

    p = tmp_path / "q.sql"
    p.write_text("SELECT * FROM `${raw}.pbp` WHERE season = ${season}")
    sql = render_sql(p, season=2024)
    assert "${" not in sql
    assert "nfl_raw.pbp" in sql
    assert "season = 2024" in sql


def test_render_sql_fails_on_unresolved(tmp_path):
    import pytest

    from nfl_dfs.bq import render_sql

    p = tmp_path / "q.sql"
    p.write_text("SELECT ${mystery}")
    with pytest.raises(ValueError):
        render_sql(p)
