"""Millionaire derivations on a synthetic contest (invented players/teams)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.dashboard import milly as M


def lineup(qb, rb1, rb2, wr1, wr2, wr3, te, flex, dst):
    slots = [("QB", qb), ("RB", rb1), ("RB", rb2), ("WR", wr1), ("WR", wr2), ("WR", wr3),
             ("TE", te), ("FLEX", flex), ("DST", dst)]
    return json.dumps([{"slot": s, "player": p} for s, p in slots])


# Synthetic slate: BUF (home) vs MIA, KC vs LV; all player names invented.
SLATE = pd.DataFrame([
    ("qa", "BUF", "QB", 7000), ("wa1", "BUF", "WR", 8000), ("wa2", "BUF", "WR", 6000),
    ("ta", "BUF", "TE", 5000), ("ra", "BUF", "RB", 7000),
    ("qb_b", "MIA", "QB", 6000), ("wb1", "MIA", "WR", 7000), ("rb_b", "MIA", "RB", 6500),
    ("wc1", "KC", "WR", 5000), ("rc", "KC", "RB", 5500), ("wd1", "LV", "WR", 4500),
    ("Dees", "LV", "DST", 3000),
], columns=["display_name", "team", "position", "salary"]).assign(season=2026, week=5, contest_id="c1")
SLATE["dk_player_id"] = range(1001, 1001 + len(SLATE))

GAMES = pd.DataFrame([
    {"season": 2026, "week": 5, "game_id": "g1", "home_team": "BUF", "away_team": "MIA"},
    {"season": 2026, "week": 5, "game_id": "g2", "home_team": "KC", "away_team": "LV"},
])


# DraftKings user names in fixtures are synthetic, always user_<letters>
# (operator 2026-10-03: real names never appear in tracked files or tests).
SYNTHETIC_USER = r"user_[a-z]+"


def top_rows():
    rows = [
        # winner: QB qa + wa1, wa2 (stack 2) + bring-back rb_b and wb1 (2)
        ("k1", 1, 250.0, lineup("qa", "rb_b", "rc", "wa1", "wa2", "wb1", "wc1", "wd1", "Dees"), 1, "user_a"),
        # QB qa + ra, wa1, ta (stack 3) + bring-back rb_b (1)
        ("k2", 2, 240.0, lineup("qa", "ra", "rc", "wc1", "wd1", "wa1", "ta", "rb_b", "Dees"), 3, "user_b"),
        # QB qb_b + wb1 (stack 1) + bring-back ra, wa1, ta (3)
        ("k3", 3, 230.0, lineup("qb_b", "rc", "ra", "wb1", "wa1", "wc1", "ta", "wd1", "Dees"), 1, "user_a"),
    ]
    return pd.DataFrame([{"season": 2026, "week": 5, "contest_id": "c1", "lineup_key": k, "rank": r,
                          "points": p, "lineup_slots_json": j, "dupes": d, "n_entries": 300,
                          "username": u, "at_cash_line": False} for k, r, p, j, d, u in rows])


OWN = pd.DataFrame({"season": 2026, "week": 5, "contest_id": "c1",
                    "display_name": SLATE.display_name, "own": np.linspace(30, 2, len(SLATE)),
                    "fpts": np.linspace(25, 3, len(SLATE))})


def test_explode_lineups():
    long = M.explode_lineups(top_rows())
    assert len(long) == 27 and set(long.slot) == {"QB", "RB", "WR", "TE", "FLEX", "DST"}
    bad = top_rows().assign(lineup_slots_json="not json")
    assert M.explode_lineups(bad).empty


def test_lineup_construction_stack_bring_back_salary_ownership():
    cons = M.lineup_construction(top_rows(), SLATE, GAMES, OWN).set_index("lineup_key")
    w = cons.loc["k1"]
    assert (w.qb, w.qb_team, w.stack, w.bring_back, w.stack_label) == ("qa", "BUF", 2, 2, "QB+2+2")
    assert w.salary == pytest.approx(7000 + 6500 + 5500 + 8000 + 6000 + 7000 + 5000 + 4500 + 3000)
    own = OWN.set_index("display_name").own
    assert w.own_sum == pytest.approx(own[["qa", "rb_b", "rc", "wa1", "wa2", "wb1", "wc1", "wd1", "Dees"]].sum())
    assert w.n_games == 2 and w.matched == 9 and w.dupes == 1
    assert cons.loc["k2"].stack_label == "QB+3+1"
    assert cons.loc["k3"].stack_label == "QB+1+3"


def test_construction_summary_and_winner():
    cons = M.lineup_construction(top_rows(), SLATE, GAMES, OWN)
    s = M.construction_summary(cons).iloc[0]
    assert s.n == 3 and s.n_excluded == 0
    assert s.share_qb_stack2 == pytest.approx(2 / 3)
    assert s.median_dupes == 1
    win = M.winners(cons)
    assert win.lineup_key.tolist() == ["k1"]
    assert M.lineup_players(top_rows(), "k1")[0] == ("QB", "qa")
    assert M.lineup_players(top_rows(), "k1")[-1] == ("DST", "Dees")


def test_unknown_qb_team_is_unknown_never_qb_plus_zero():
    """A week without a slate (the entries-fallback week has no draft group)."""
    cons = M.lineup_construction(top_rows(), SLATE.iloc[0:0], GAMES)
    assert cons["stack"].isna().all() and cons.bring_back.isna().all()
    assert cons.stack_label.isna().all() and cons.salary.isna().all() and (cons.matched == 0).all()
    s = M.construction_summary(cons).iloc[0]
    assert s.n == 0 and s.n_excluded == 3


def test_partially_resolved_lineups_are_excluded_from_the_summary():
    slate = SLATE[SLATE.display_name != "wc1"]          # k1, k2 and k3 all carry wc1 ...
    top = top_rows()
    top.loc[2, "lineup_slots_json"] = top.loc[2, "lineup_slots_json"].replace('"wc1"', '"wd1"')
    cons = M.lineup_construction(top, slate, GAMES, OWN)
    s = M.construction_summary(cons).iloc[0]
    assert (s.n, s.n_excluded) == (1, 2)                # ... except the edited k3


def test_most_owned_and_ours_vs_winner():
    mo = M.most_owned(OWN, 3)
    assert mo.display_name.tolist() == ["qa", "wa1", "wa2"]
    lines = pd.DataFrame([{"week": 5, "n_entries": 300, "winning_score": 250.0, "top_01pct_line": 250.0,
                           "top_1pct_line": 240.0, "cash_line": np.nan}])
    arms = pd.DataFrame([
        {"week": 5, "arm": "played", "kind": "played", "best_points": 200.0, "best_rank": 40},
        {"week": 5, "arm": "composite", "kind": "shadow", "best_points": 245.0, "best_rank": 2},
        {"week": 5, "arm": "book", "kind": "book", "best_points": 210.0, "best_rank": 30}])
    o = M.ours_vs_winner(lines, arms).iloc[0]
    assert (o.our_best, o.our_rank, o.our_source, o.gap) == (200.0, 40, "played", 50.0)
    assert (o.book_best, o.book_rank) == (210.0, 30)            # shown beside, never substituted
    fb = M.ours_vs_winner(lines, arms[arms.kind != "played"]).iloc[0]
    assert fb.our_best == 210.0 and fb.our_source == "book (no played arm published)"
    empty = M.ours_vs_winner(lines, pd.DataFrame()).iloc[0]
    assert np.isnan(empty.our_best) and empty.our_source is None


def test_same_named_players_on_two_teams_are_never_merged():
    """Two slate players normalise to one name (different teams): the name is
    a collision, reported, and resolves to neither player."""
    slate = pd.concat([SLATE, pd.DataFrame([
        {"display_name": "Twin Name", "team": "BUF", "position": "WR", "salary": 4000,
         "season": 2026, "week": 5, "contest_id": "c1", "dk_player_id": 2001},
        {"display_name": "Twin Name Jr.", "team": "KC", "position": "WR", "salary": 3900,
         "season": 2026, "week": 5, "contest_id": "c1", "dk_player_id": 2002}])], ignore_index=True)
    coll = M.slate_collisions(slate)
    assert sorted(coll.dk_player_id) == [2001, 2002] and coll.k.nunique() == 1
    res = M.resolve_slate(slate)
    assert "TWINNAME" not in set(res.k) and len(res) == len(SLATE)
    long = pd.DataFrame({"contest_id": ["c1", "c1"], "player": ["Twin Name", "qa"]})
    r = M.resolve_names(long, slate)
    assert pd.isna(r.dk_player_id.iloc[0]) and r.dk_player_id.iloc[1] == 1001
    top = top_rows()
    top.loc[0, "lineup_slots_json"] = lineup("qa", "rb_b", "rc", "wa1", "wa2", "Twin Name", "wc1", "wd1", "Dees")
    cons = M.lineup_construction(top, slate, GAMES, OWN).set_index("lineup_key")
    assert cons.loc["k1"].matched == 8                    # the twin slot stays unresolved


def test_one_player_listed_twice_is_not_a_collision():
    dup = pd.concat([SLATE, SLATE.iloc[[0]]], ignore_index=True)
    assert M.slate_collisions(dup).empty and len(M.resolve_slate(dup)) == len(SLATE)
