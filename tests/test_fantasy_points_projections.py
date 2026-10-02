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
    rows = fpp.normalize_whole(body, "weekly", season=2026, week=4)
    assert rows[0]["fantasy_points_draftkings"] == 27.0 and json.loads(rows[0]["row_json"])["rushingYards"] == 88.5
    with pytest.raises(RuntimeError, match="week 3"):
        fpp.normalize_whole({"session": SESSION, "content": {"table": {"values": [{**v, "week": 3}]}}}, "weekly", season=2026, week=4)
