import pandas as pd
import requests

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


def draft_groups_payload():
    """Modeled on a live /draftgroups/v1/ response (verified 2026-07-31):
    entries carry sportId at the top level (1=NFL, 5=CFB per DK's own
    /sites/US-DK/sports/v1/sports) but no top-level "sport" string."""
    return {
        "draftGroups": [
            {"draftGroupId": 90001, "sportId": 1, "draftGroupState": "Upcoming"},
            {"draftGroupId": 90002, "sportId": 5, "draftGroupState": "Upcoming"},
            # Not upcoming -> excluded regardless of sport.
            {"draftGroupId": 90003, "sportId": 5, "draftGroupState": "Complete"},
            # A non-NFL, non-CFB sport (e.g. NBA) -> excluded from both.
            {"draftGroupId": 90004, "sportId": 4, "draftGroupState": "Upcoming"},
        ]
    }


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_cfb_draft_groups_filters_by_sport_id(monkeypatch):
    def fake_get(self, url, headers=None, timeout=None):
        assert url == dk_client.DK_GROUPS
        return _FakeResponse(draft_groups_payload())

    monkeypatch.setattr(requests.Session, "get", fake_get)
    groups = dk_client.cfb_draft_groups()
    assert [g["draftGroupId"] for g in groups] == [90002]


def test_nfl_contests_hits_nfl_endpoint(monkeypatch):
    calls = []

    def fake_get(self, url, headers=None, timeout=None):
        calls.append(url)
        return _FakeResponse({"Contests": [{"id": 1}]})

    monkeypatch.setattr(requests.Session, "get", fake_get)
    assert dk_client.nfl_contests() == [{"id": 1}]
    assert calls == [dk_client.DK_CONTESTS]


def test_cfb_contests_hits_cfb_endpoint(monkeypatch):
    calls = []

    def fake_get(self, url, headers=None, timeout=None):
        calls.append(url)
        return _FakeResponse({"Contests": [{"id": 2}]})

    monkeypatch.setattr(requests.Session, "get", fake_get)
    assert dk_client.cfb_contests() == [{"id": 2}]
    assert calls == [dk_client.DK_CFB_CONTESTS]


def contests_payload():
    return [
        {
            "id": 111,
            "dg": 555,
            "n": "$1M Fantasy Football Millionaire [$150K to 1st]",
            "gameType": "Classic",
            "a": 20,
            "m": 50_000,
            "nt": 12_000,
            "po": 1_000_000.0,
            "attr": {"IsGuaranteed": "true"},
            "sd": "/Date(1785513600000)/",
        },
        {
            # Non-guaranteed: never carries an overlay even when short-filled.
            "id": 112,
            "dg": 555,
            "n": "50/50 Double Up",
            "gameType": "Classic",
            "a": 5,
            "m": 1000,
            "nt": 10,
            "po": 4500.0,
            "attr": {},
            "sd": "/Date(1785513600000)/",
        },
        {
            # Different draft group (e.g. a Madden sim contest sharing the
            # sport=NFL tag) — excluded when filtering by draft_group_ids.
            "id": 113,
            "dg": 999,
            "n": "Madden Stream $6K Friday Special",
            "gameType": "Madden Classic",
            "a": 15,
            "m": 470,
            "nt": 222,
            "po": 6000.0,
            "attr": {"IsGuaranteed": "true"},
            "sd": "/Date(1785513600000)/",
        },
    ]


def test_contests_frame_filters_to_draft_group_ids():
    df = dk_client.contests_frame(contests_payload(), draft_group_ids={555})
    assert set(df.contest_id) == {111, 112}


def test_contests_frame_no_filter_keeps_everything():
    df = dk_client.contests_frame(contests_payload())
    assert set(df.contest_id) == {111, 112, 113}


def test_contests_frame_fill_rate():
    df = dk_client.contests_frame(contests_payload(), draft_group_ids={555})
    gpp = df[df.contest_id == 111].iloc[0]
    assert gpp.fill_rate == 12_000 / 50_000


def test_contests_frame_overlay_only_for_guaranteed():
    df = dk_client.contests_frame(contests_payload(), draft_group_ids={555})
    gpp = df[df.contest_id == 111].iloc[0]
    double_up = df[df.contest_id == 112].iloc[0]
    assert gpp.is_guaranteed
    assert gpp.overlay_dollars == 1_000_000.0 - 12_000 * 20
    assert not double_up.is_guaranteed
    # Short-filled (10 of 1000 entries) but not guaranteed -> no overlay.
    assert double_up.overlay_dollars == 0.0


def test_contests_frame_sport_defaults_nfl():
    df = dk_client.contests_frame(contests_payload(), draft_group_ids={555})
    assert set(df.sport) == {"NFL"}


def test_contests_frame_sport_stamps_cfb():
    """cfb_job.py passes sport="CFB" so dk_contest_fills can hold both
    sports' polls in one append-only table (issue #13 item 7)."""
    df = dk_client.contests_frame(contests_payload(), draft_group_ids={555}, sport="CFB")
    assert set(df.sport) == {"CFB"}


def test_contests_frame_empty_input():
    df = dk_client.contests_frame([])
    assert df.empty
    assert list(df.columns) == dk_client.CONTEST_COLUMNS


def test_contests_frame_handles_missing_fields():
    df = dk_client.contests_frame(
        [{"id": 1, "dg": 1, "n": "Weird contest", "attr": {"IsGuaranteed": "true"}}]
    )
    row = df.iloc[0]
    assert pd.isna(row.fill_rate)
    assert row.overlay_dollars == 0.0  # missing entries/fee/pool -> no overlay computed
    assert pd.isna(row.start_time)


def test_parse_dk_date():
    ts = dk_client._parse_dk_date("/Date(1785513600000)/")
    assert ts is not None
    assert ts.tz is not None
    assert ts.year == 2026

    assert dk_client._parse_dk_date("not a date") is None
    assert dk_client._parse_dk_date(None) is None


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
