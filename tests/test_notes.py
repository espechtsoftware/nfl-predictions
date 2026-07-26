"""Manual usage notes: decay curve, opportunity application, chat dispatch.
All offline — BigQuery reads are monkeypatched."""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs import notes


def test_decay_curve():
    assert notes.decay(1) == 1.0
    assert 0 < notes.decay(3) < 1
    assert notes.decay(notes.DECAY_FULL_WEEK) == 0.0
    assert notes.decay(18) == 0.0


def _fake_notes():
    return pd.DataFrame([
        {"note_id": "a", "gsis_id": "P1", "display_name": "Player One",
         "season": 2026, "mult": 1.2, "note": "slot role", "source": ""},
    ])


def test_apply_notes_scales_opportunity(monkeypatch):
    monkeypatch.setattr(notes, "list_notes", lambda s: _fake_notes())
    comps = pd.DataFrame({"targets": [5.0, 5.0], "carries": [1.0, 1.0],
                          "ypr": [10.0, 10.0]})
    feats = pd.DataFrame({"gsis_id": ["P1", "P2"]})
    out = notes.apply_notes(comps, feats, season=2026, week=1)
    assert out.targets.iloc[0] == pytest.approx(6.0)   # 1.2x at full effect
    assert out.targets.iloc[1] == pytest.approx(5.0)   # untouched player
    assert out.ypr.iloc[0] == pytest.approx(10.0)      # rates never scaled

    late = notes.apply_notes(comps, feats, season=2026, week=10)
    assert np.allclose(late.targets, comps.targets)    # decayed to nothing

    mid = notes.apply_notes(comps, feats, season=2026, week=3)
    assert 5.0 < mid.targets.iloc[0] < 6.0             # partial decay


def test_apply_notes_survives_bq_failure(monkeypatch):
    def boom(_):
        raise RuntimeError("bq down")
    monkeypatch.setattr(notes, "list_notes", boom)
    comps = pd.DataFrame({"targets": [5.0]})
    feats = pd.DataFrame({"gsis_id": ["P1"]})
    out = notes.apply_notes(comps, feats, season=2026, week=1)
    assert out.targets.iloc[0] == 5.0


def test_add_note_clamps_mult(monkeypatch):
    captured = {}

    def fake_load(df, table, **kw):
        captured["mult"] = df.mult.iloc[0]
    monkeypatch.setattr(notes, "load_dataframe", fake_load)
    notes.add_note("P1", "Player One", 2026, mult=9.0, note="hype")
    assert captured["mult"] == 1.4


def test_chat_tool_dispatch(monkeypatch):
    from nfl_dfs.app import chat

    monkeypatch.setattr(notes, "list_notes", lambda s: _fake_notes())
    out = chat.execute_tool("list_usage_notes", {"season": 2026})
    assert "Player One" in out

    monkeypatch.setattr(notes, "add_note", lambda **kw: "abc123")
    out = chat.execute_tool("add_usage_note", {
        "gsis_id": "P1", "display_name": "Player One", "mult": 1.15,
        "note": "coach: slot role"})
    assert "abc123" in out

    monkeypatch.setattr(notes, "delete_note", lambda nid: 1)
    assert "deleted 1" in chat.execute_tool("delete_usage_note",
                                            {"note_id": "abc123"})
    assert "unknown tool" in chat.execute_tool("nope", {})


def test_dst_projection_rows_assembly():
    from nfl_dfs.inference.dst_projections import (FALLBACK_PROJ, P90_OFF,
                                                   build_rows)

    slate = pd.DataFrame({
        "dk_player_id": [901, 902], "display_name": ["Bears", "Lions"],
        "team_abbr": ["CHI", "DET"], "salary": [3200, 2600],
        "draft_group_id": [7, 7]})
    trailing = pd.DataFrame({"team": ["CHI"], "dst_l4": [8.0]})
    opponents = pd.DataFrame({"team": ["CHI", "DET"],
                              "opponent": ["DET", "CHI"]})
    qb = pd.DataFrame({"team": ["DET", "CHI"], "career_starts": [2, 120]})

    rows = build_rows(slate, trailing, opponents, qb, 2026, 1, "vtest")
    chi = rows[rows.team == "CHI"].iloc[0]
    det = rows[rows.team == "DET"].iloc[0]
    # CHI: 8.0 trailing + rookie-opponent bonus 2.2
    assert chi.proj_points == pytest.approx(10.2)
    assert chi.proj_p90 == pytest.approx(10.2 + P90_OFF)
    # DET: no trailing history -> fallback, veteran opponent -0.7
    assert det.proj_points == pytest.approx(FALLBACK_PROJ - 0.7)
    assert (rows.position == "DST").all()
    assert rows.value.gt(0).all()
