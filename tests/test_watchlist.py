"""Player watch notes: module + endpoints (BQ seams monkeypatched)."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nfl_dfs import watchlist
from nfl_dfs.app import main as app_main


def _fake_df(rows):
    cols = ["note_id", "gsis_id", "display_name", "note", "status",
            "created_at", "converted_at", "converted_note_id", "converted_mult"]
    return pd.DataFrame(rows, columns=cols)


def test_annotate_players_matches_by_name(monkeypatch):
    monkeypatch.setattr(watchlist, "list_watch", lambda include_converted=True: _fake_df([
        ["n1", "", "Rookie Guy", "explosive in camp", "active",
         "2026-08-01", None, "", np.nan],
    ]))
    players = [{"name": "Rookie Guy", "pos": "WR"},
               {"name": "Someone Else", "pos": "RB"}]
    watchlist.annotate_players(players)
    assert players[0]["watch_note"] == "explosive in camp"
    assert "watch_note" not in players[1]


def test_annotate_failsafe(monkeypatch):
    def boom(include_converted=True):
        raise RuntimeError("bq down")
    monkeypatch.setattr(watchlist, "list_watch", boom)
    players = [{"name": "A"}]
    watchlist.annotate_players(players)  # must not raise
    assert "watch_note" not in players[0]


def test_convert_guards(monkeypatch):
    monkeypatch.setattr(watchlist, "list_watch", lambda include_converted=True: _fake_df([
        ["n1", "g1", "P One", "note", "converted", "2026-08-01",
         "2026-08-02", "m1", 1.1],
    ]))
    with pytest.raises(ValueError, match="already converted"):
        watchlist.convert_watch("n1", 1.2, 2026)
    with pytest.raises(ValueError, match="no watch note"):
        watchlist.convert_watch("missing", 1.2, 2026)


def test_watchlist_page_and_api(monkeypatch):
    monkeypatch.setattr(watchlist, "list_watch", lambda include_converted=True: _fake_df([
        ["n1", "", "P One", "note text", "active", "2026-08-01",
         None, "", np.nan],
    ]))
    client = TestClient(app_main.app)
    assert "Watchlist" in client.get("/watchlist").text
    j = client.get("/api/watchlist").json()
    assert j[0]["display_name"] == "P One" and j[0]["status"] == "active"


def test_build_lineups_annotation_hook(monkeypatch):
    """_with_watch_notes decorates player dicts in lineup responses."""
    monkeypatch.setattr(watchlist, "list_watch", lambda include_converted=True: _fake_df([
        ["n1", "", "Note Target", "watch him", "active", "2026-08-01",
         None, "", np.nan],
    ]))
    players = [{"name": "Note Target"}, {"name": "Nobody"}]
    out = app_main._with_watch_notes(players)
    assert out[0]["watch_note"] == "watch him"
