"""fantasy_points_projections: the pure normalizers on synthetic payloads (no browser, no network)."""
import json

import pytest

from nfl_dfs.ops import fantasy_points_projections as fpp

SESSION = {"uid": "u1", "roles": ["role_authenticated", "role_abc"]}


def _dfs(week=4, lock=False, players=True):
    p = {"playerId": "A1", "fantasyPosition": "WR", "operatorSlatePlayerId": 44, "name": "Some Receiver", "operatorPosition": "WR",
         "team": "SEA", "operatorSalary": 9100, "fantasyPoints": 21.1, "fantasyPointsPerDollar": 2.3,
         "projectedOwnershipPercentage": "CtaLockValue" if lock else 14.0, "operatorRosterSlots": ["WR", "FLEX"], "opponent": "LAC"}
    slate = {"operator": "DraftKings", "operatorName": "Main", "operatorSlateId": 154078, "operatorGameType": "Classic",
             "operatorStartTime": "2026-10-04T12:00:00", "numberOfGames": 12, "season": 2026, "week": week,
             "lastUpdated": "2026-10-02T14:59:39Z", "dfsSlatePlayers": [p] if players else []}
    return {"session": SESSION, "content": {"table": {"isOffseason": False, "values": [slate]}}}


def test_dfs_rows_carry_the_slate_and_the_player():
    rows = fpp.normalize_dfs(_dfs(), season=2026, week=4)
    assert rows == [{**rows[0]}] and rows[0]["slate_id"] == "154078" and rows[0]["projected_ownership_pct"] == 14.0
    assert rows[0]["roster_slots"] == "WR,FLEX" and rows[0]["salary"] == 9100 and rows[0]["slate_player_id"] == "44"


@pytest.mark.parametrize("payload,match", [
    (lambda: {**_dfs(), "session": {"uid": "u", "roles": ["role_anonymous"]}}, "anonymous"),
    (lambda: _dfs(lock=True), "locked"),
    (lambda: _dfs(week=3), "expected 2026/4"),
    (lambda: _dfs(players=False), "no slate players"),
    (lambda: {"session": SESSION, "content": {"table": {"isOffseason": True, "values": [1]}}}, "offseason"),
])
def test_dfs_fails_closed(payload, match):
    with pytest.raises(RuntimeError, match=match):
        fpp.normalize_dfs(payload(), season=2026, week=4)


def test_whole_rows_keep_every_field_and_check_the_week():
    v = {"playerId": "B2", "season": 2026, "week": 4, "name": "Some Back", "fantasyPosition": "RB", "team": "DET",
         "opponent": "CAR", "fantasyPointsDraftKings": 27.0, "rushingYards": 88.5, "lastUpdated": "2026-10-02T14:58:26Z"}
    body = {"session": SESSION, "content": {"table": {"values": [v]}}}
    rows, ev = fpp.normalize_whole(body, "weekly", season=2026, week=4)
    assert ev == {"rows_without_week": 0} and rows[0]["fantasy_points_draftkings"] == 27.0 and json.loads(rows[0]["row_json"])["rushingYards"] == 88.5
    with pytest.raises(RuntimeError, match="week 3"):
        fpp.normalize_whole({"session": SESSION, "content": {"table": {"values": [{**v, "week": 3}]}}}, "weekly", season=2026, week=4)


def test_whole_refuses_without_week_evidence():
    v = {"playerId": "B2", "name": "Some Back", "fantasyPointsDraftKings": 27.0}                 # no season / week
    with pytest.raises(RuntimeError, match="cannot be verified"):
        fpp.normalize_whole({"session": SESSION, "content": {"table": {"values": [v] * 10}}}, "weekly", season=2026, week=4)
    ok = [{**v, "season": 2026, "week": 4}] * 99 + [v]                                         # 99% carry it: passes, counted
    rows, ev = fpp.normalize_whole({"session": SESSION, "content": {"table": {"values": ok}}}, "weekly", season=2026, week=4)
    assert len(rows) == 100 and ev == {"rows_without_week": 1}


def test_redacted_archive_carries_no_email_or_token():
    from nfl_dfs.ops.fantasy_points_ownership import _redacted
    body = {**_dfs(), "session": {"uid": "u1", "email": "someone@example.com", "token": "eyJabcdefghij.klmnopqrstu.vwxyzABCDEF",
                                  "roles": ["role_authenticated"]}}
    fpp.assert_no_secrets(json.dumps(_redacted(body)))                                            # the session is reduced to roles
    with pytest.raises(RuntimeError, match="email-like or token-like"):
        fpp.assert_no_secrets(json.dumps({"x": "someone@example.com"}))
    with pytest.raises(RuntimeError, match="email-like or token-like"):
        fpp.assert_no_secrets(json.dumps({"x": "eyJabcdefghij.klmnopqrstu.vwxyzABCDEF"}))


def test_coerced_nulls_counts_values_lost_on_parsing():
    import pandas as pd
    rows = [{"salary": 9100, "fantasy_points": "21.1"}, {"salary": "n/a", "fantasy_points": None}]
    frame = pd.DataFrame({"salary": pd.to_numeric(pd.Series([9100, "n/a"]), errors="coerce"),
                          "fantasy_points": pd.to_numeric(pd.Series(["21.1", None]), errors="coerce")})
    assert fpp.coerced_nulls(rows, frame) == {"salary": 1, "fantasy_points": 0}                 # None was never present


def test_rest_of_season_rankings_need_no_week_but_a_wrong_week_still_refuses():
    v = {"playerId": "C3", "name": "Some Ranked Player", "rank": 12, "season": 2026}
    body = {"session": SESSION, "content": {"table": {"values": [v] * 5}}}
    rows, ev = fpp.normalize_whole(body, "rankings-ros", season=2026, week=4, require_week=False)
    assert len(rows) == 5 and ev == {"rows_without_week": 5}
    with pytest.raises(RuntimeError, match="stale season"):                                   # no season evidence: refuse
        fpp.normalize_whole({"session": SESSION, "content": {"table": {"values": [{"name": "x"}] * 5}}}, "rankings-ros",
                            season=2026, week=4, require_week=False)
    rows0, _ = fpp.normalize_whole({"session": SESSION, "content": {"table": {"values": [{**v, "season": 2026, "week": 0}]}}},
                                   "rankings-ros", season=2026, week=4, require_week=False)          # season-long = week 0
    assert len(rows0) == 1
    with pytest.raises(RuntimeError, match="week 3"):
        fpp.normalize_whole({"session": SESSION, "content": {"table": {"values": [{**v, "week": 3}]}}}, "rankings-ros",
                            season=2026, week=4, require_week=False)
    assert "rankings-ros" in fpp.NO_WEEK_TABLES and "rankings-weekly" not in fpp.NO_WEEK_TABLES
