import pandas as pd

from nfl_dfs.ingest import dk_client


def payload():
    return {
        "competitions": [
            {"competitionId": 111, "startTime": "2025-09-07T17:00:00Z"},
        ],
        "draftables": [
            {
                "draftableId": 9001,
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
                "draftableId": 9002,
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
                "draftableId": 9003,
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


def test_draftables_frame_keeps_draftable_ids():
    """DK's lineup upload matches on draftable IDs (the DKSalaries 'ID'
    column), so the frame must carry them. Classic repeats share a player,
    and any of the player's draftable IDs resolves on upload — keep the
    first."""
    df = dk_client.draftables_frame(123, "classic", payload())
    jj = df[df.dk_player_id == 1].iloc[0]
    assert jj.dk_draftable_id == 9001
    assert pd.isna(jj.dk_cpt_draftable_id)  # classic has no CPT slot
    assert df.dk_draftable_id.dtype == "Int64"


def test_showdown_dedup_keeps_flex_salary():
    """Showdown draftables repeat each player as CPT (1.5x salary) and FLEX;
    the frame must keep the FLEX price regardless of payload order — and
    both draftable IDs, because the upload's CPT cell only accepts the
    CPT-specific ID."""
    pl = payload()
    pl["draftables"][0]["salary"] = 13_350  # CPT row first: 1.5x the 8900 FLEX
    df = dk_client.draftables_frame(123, "showdown", pl)
    jj = df[df.dk_player_id == 1].iloc[0]
    assert jj.salary == 8900
    assert jj.dk_draftable_id == 9002       # the FLEX row
    assert jj.dk_cpt_draftable_id == 9001   # the CPT row


def test_showdown_dedup_flex_row_first():
    pl = payload()
    pl["draftables"][1]["salary"] = 13_350  # FLEX first, CPT repeat after
    df = dk_client.draftables_frame(123, "showdown", pl)
    jj = df[df.dk_player_id == 1].iloc[0]
    assert jj.salary == 8900
    assert jj.dk_draftable_id == 9001
    assert jj.dk_cpt_draftable_id == 9002


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


def test_every_shipped_sql_file_renders():
    """Placeholder coverage for the real pipeline SQL: build-features runs
    every file under sql/, and an unresolved ${...} should fail here, not
    in the morning build."""
    from nfl_dfs.bq import SQL_DIR, render_sql

    files = sorted(SQL_DIR.rglob("*.sql"))
    assert files, f"no SQL found under {SQL_DIR}"
    for path in files:
        sql = render_sql(path, prior_k=4)
        assert "${" not in sql, path
