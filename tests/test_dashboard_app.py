"""Dashboard v2 routes with empty and synthetic warehouses (FastAPI
TestClient, fake query routed by the SQL template marker). Synthetic names."""
from __future__ import annotations

import json
import sys

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nfl_dfs.dashboard import data as D
from nfl_dfs.dashboard.app import create_app

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from test_dashboard_milly import OWN, SLATE, top_rows  # noqa: E402

ROUTES = ["/", "/games", "/players", "/offense", "/defense", "/accuracy", "/arms",
          "/milly", "/insights"]
Q = "?season=2026&week=5"


def schedule():
    return pd.DataFrame([
        {"season": 2026, "week": w, "game_id": f"2026_{w:02d}_{a}_{h}", "gameday": d, "gametime": "13:00",
         "weekday": "Sunday", "home_team": h, "away_team": a, "home_score": hs, "away_score": as_,
         "total_line": 45.0, "spread_line": 3.0}
        for w, d, h, a, hs, as_ in ((4, "2026-10-04", "BUF", "MIA", 27, 20), (4, "2026-10-04", "KC", "LV", 30, 10),
                                    (5, "2026-10-11", "BUF", "MIA", None, None),
                                    (5, "2026-10-11", "KC", "LV", None, None))])


def fixtures() -> dict[str, pd.DataFrame]:
    proj = pd.DataFrame([
        {"generated_at": "2026-10-10T15:00Z", "slate_id": 1, "gsis_id": "g-qa", "dk_player_id": 1,
         "display_name": "qa", "position": "QB", "team": "BUF", "opponent": "MIA", "salary": 7000,
         "proj_points": 22.0, "proj_p10": 10.0, "proj_p50": 21.0, "proj_p90": 35.0},
        {"generated_at": "2026-10-10T15:00Z", "slate_id": 1, "gsis_id": "g-wa1", "dk_player_id": 2,
         "display_name": "wa1", "position": "WR", "team": "BUF", "opponent": "MIA", "salary": 8000,
         "proj_points": 18.0, "proj_p10": 6.0, "proj_p50": 17.0, "proj_p90": 31.0}])
    off = pd.DataFrame([{"season": 2026, "week": w, "team": t, "points": p, "dk_points": dk, "yards": 350,
                         "plays": 62} for w in (3, 4) for t, p, dk in
                        (("BUF", 27, 110.0), ("MIA", 20, 80.0), ("KC", 30, 120.0), ("LV", 10, 50.0))])
    dpa = pd.DataFrame([{"team": t, "season": 2026, "week": w, "position": pos, "fp_allowed": v}
                        for w in (3, 4) for t, v in (("BUF", 15.0), ("MIA", 22.0), ("KC", 18.0), ("LV", 30.0))
                        for pos in ("QB", "RB", "WR", "TE")])
    arms = pd.DataFrame([{"season": 2026, "week": 5, "arm": a, "kind": k, "contest_id": None, "n_lineups": n,
                          "mean_points": 150.0, "best_points": b, "best_rank": r, "cash_rate": None,
                          "source_file": "week/x", "source_sha256": "0" * 64,
                          "published_utc": "2026-10-12T09:00Z"}
                         for a, k, n, b, r in (("played", "played", 30, 210.0, 40), ("pool", "pool", 6000, 249.0, 2),
                                               ("book", "book", 110, 215.0, 33),
                                               ("composite", "shadow", 30, 220.0, 25))])
    lines = pd.DataFrame([{"season": 2026, "week": 5, "contest_id": "c1", "contest_name": "Synthetic Milly",
                           "n_entries": 300, "winning_score": 250.0, "top_01pct_line": 250.0,
                           "top_1pct_line": 240.0, "cash_line": None, "median_score": 120.0}])
    ours = pd.DataFrame([{"week": 4, "gsis_id": "g-qa", "display_name": "qa", "position": "QB", "team": "BUF",
                          "salary": 7000, "proj_points": 22.0, "dk_points": 30.0}])
    fp_season = pd.DataFrame([{"week": 4, "name": "qa", "position": "QB", "team": "BUF", "fantasy_points": 17.0}])
    fp_own_season = pd.DataFrame([{"week": 5, "name": n, "position": "QB", "team": "BUF",
                                   "projected_ownership_pct": v} for n, v in (("qa", 25.0), ("wa1", 12.0))])
    return {
        "schedules_season": schedule(),
        "milly_contests": pd.DataFrame([{"season": 2026, "week": 5, "contest_id": "c1",
                                         "contest_name": "Synthetic Milly", "draft_group_id": 1,
                                         "start_time": "2026-10-11T17:00Z", "field_size": 300, "n_entries": 300}]),
        "slate_teams": pd.DataFrame({"team_abbr": ["BUF", "MIA", "KC", "LV"]}),
        "odds_week": pd.DataFrame([
            ("2026-10-10T12:00Z", "e1", "Miami Dolphins @ Buffalo Bills", "2026-10-11T17:00:00Z", "Total", "Over", 47.5, -110),
            ("2026-10-10T12:00Z", "e1", "Miami Dolphins @ Buffalo Bills", "2026-10-11T17:00:00Z", "Spread", "Buffalo Bills", -6.5, -110)],
            columns=["pulled_at", "event_id", "event_name", "start_time", "market_type", "selection", "line",
                     "odds_american"]),
        "team_context_week": pd.DataFrame([{"team": "KC", "opponent": "LV", "is_home": 1,
                                            "implied_team_total": 26.0, "spread": -5.0, "game_total": 47.0}]),
        "projections_week": proj,
        "fp_projections_week": pd.DataFrame([{"slate_id": "1", "slate_name": "Main", "n_games": 2, "name": "qa",
                                              "position": "QB", "team": "BUF", "salary": 7000,
                                              "slate_player_id": "9", "fantasy_points": 20.5,
                                              "retrieved_at": "2026-10-10T12:00Z"}]),
        "fp_ownership_week": pd.DataFrame([{"name": "qa", "position": "QB", "team": "BUF", "salary": 7000,
                                            "projected_ownership_pct": 25.0, "retrieved_at": "2026-10-10T12:00Z"}]),
        "pool_exposure": pd.DataFrame([{"season": 2026, "week": 5, "run_id": "run-synthetic",
                                        "built_utc": "2026-10-10T15:35Z", "player": "qa", "dk_player_id": 1,
                                        "position": "QB", "team": "BUF", "pool_share": 0.4, "book_share": 0.6,
                                        "n_pool": 40, "n_book": 18, "book_source": "played-synthetic",
                                        "published_utc": "2026-10-12T09:00Z"}]),
        "offense_weekly": off, "defense_weekly": dpa, "arms_weekly": arms, "milly_lines": lines,
        "milly_top_lineups": top_rows(), "milly_slate": SLATE, "milly_field_ownership": OWN,
        "accuracy_ours": ours, "fp_projections_season": fp_season, "fp_ownership_season": fp_own_season,
        "freshness": pd.DataFrame({"source": ["odds_snapshots"], "newest": ["2026-10-10 12:00"]}),
        "insight_winners_vs_field": pd.DataFrame([{"week": 5, "grp": "top 1%", "n": 3, "own_sum": 120.0,
                                                   "proj_sum": 140.0, "unmatched": 0.1}]),
        "insight_book_fp": pd.DataFrame([{"week": 5, "grp": "our book", "n": None, "own_sum": 110.0,
                                          "proj_sum": 138.0, "unmatched": 0.0}]),
        "insight_leverage_paid": pd.DataFrame([{"week": 5, "player": "wa2", "fp_own": 15.0, "realized": 6.0,
                                                "top1_rate": 30.0, "fpts": 28.0,
                                                "category": "leverage that paid"}]),
        "insight_stacks": pd.DataFrame([{"week": 5, "qb": "qa", "catcher": "wa1", "team": "BUF", "lineups": 2,
                                         "share_top1": 66.7, "pair_fp_own": 37.0}]),
        "insight_repeat_finishers": pd.DataFrame([
            {"username": "user_a", "entries": 150, "weeks": 4, "top1_lineups": 9, "top1_weeks": 3,
             "top01_lineups": 2, "best_rank": 4, "top1_rate": 6.0, "top_qb": "qa", "top_qb_lineups": 5},
            {"username": "user_b", "entries": 20, "weeks": 2, "top1_lineups": 1, "top1_weeks": 1,
             "top01_lineups": 0, "best_rank": 77, "top1_rate": 5.0, "top_qb": "qb_b", "top_qb_lineups": 1}]),
        "insight_book_vs_top": pd.DataFrame([{"week": 5, "player": "qa", "position": "QB", "book_pct": 60.0,
                                              "top01_pct": 100.0, "field_pct": 30.0, "fp_own": 25.0,
                                              "divergence": -40.0}]),
    }


class Warehouse:
    def __init__(self, frames=None, fail: dict | None = None):
        self.frames = frames or {}
        self.fail = fail or {}
        self.calls: list[str] = []

    def __call__(self, sql: str) -> pd.DataFrame:
        name = D.sql_name(sql)
        self.calls.append(name)
        if name in self.fail:
            raise self.fail[name]
        return self.frames.get(name, pd.DataFrame()).copy()


CONTESTS = json.dumps([{"name": "milly", "dk_name": "Synthetic Milly", "contest_id": "c1", "entries": 3,
                        "keep": 3, "fee": 20.0},
                       {"name": "sat", "dk_name": "Synthetic Satellite", "contest_id": "c2", "entries": 4,
                        "keep": 2, "fee": 0.25}])


def client(wh, env=None, stakes=None):
    return TestClient(create_app(query=wh, env=env or {"DASHBOARD_SEASON": "2026"},
                                 stake_reader=stakes or (lambda s, w: None)))


@pytest.mark.parametrize("route", ROUTES)
def test_every_page_renders_with_an_empty_warehouse(route):
    r = client(Warehouse()).get(route + Q)
    assert r.status_code == 200
    assert "note err" not in r.text


@pytest.mark.parametrize("route", ROUTES)
def test_every_page_renders_when_tables_are_missing(route):
    missing = {n: Exception("404 Not found: Dataset nfl_dashboard was not found")
               for n in ("pool_exposure", "arms_weekly", "insight_book_fp", "insight_book_vs_top")}
    r = client(Warehouse(fixtures(), fail=missing)).get(route + Q)
    assert r.status_code == 200 and "note err" not in r.text


def test_a_failing_source_is_contained_to_its_section():
    wh = Warehouse(fixtures(), fail={"offense_weekly": RuntimeError("quota exceeded")})
    r = client(wh).get("/offense" + Q)
    assert r.status_code == 200 and "unavailable: RuntimeError: quota exceeded" in r.text
    assert "Offense" in r.text


def test_pages_show_synthetic_content():
    c = client(Warehouse(fixtures()), stakes=lambda s, w: CONTESTS)
    games = c.get("/games" + Q).text
    assert "MIA @ BUF" in games and "27.00" in games and "20.50" in games   # 47.5/2 -/+ -6.5/2
    assert "nflverse" in games                                               # KC-LV fallback
    players = c.get("/players" + Q).text
    assert "qa" in players and "20.5" in players and "25.0%" in players and "60.0%" in players
    assert "played-synthetic" in players
    assert "<svg" in c.get("/offense" + Q).text and "<svg" in c.get("/defense?season=2026&pos=WR").text
    arms = c.get("/arms" + Q).text
    assert "composite" in arms and "W5 best" in arms
    assert "Synthetic Satellite" in arms and "$61.00" in arms                # 3x20 + 4x0.25
    milly = c.get("/milly" + Q).text
    assert "Winning lineup" in milly and "QB+2+2" in milly and "Top construction" in milly
    assert "210.00" in milly and ">played<" in milly and "215.00" in milly  # played, book beside it
    assert "3 lineups = 1.00% of 300" in milly and "3 fully resolved, 0 excluded" in milly
    ins = c.get("/insights" + Q).text
    assert "leverage that paid" in ins and "our book" in ins and "wa1" in ins
    assert "Repeat top finishers by user name" in ins and "permission policy" not in ins
    assert "user_a" in ins and "user_b" in ins and "Most-used QB in top 1%" in ins and "6.0%" in ins
    acc = c.get("/accuracy" + Q).text
    assert "MAE ours" in acc and "Active share" in acc


def test_results_are_cached_between_requests():
    wh = Warehouse(fixtures())
    c = client(wh)
    c.get("/offense" + Q)
    n = wh.calls.count("offense_weekly")
    c.get("/offense" + Q)
    assert wh.calls.count("offense_weekly") == n == 1


def test_the_graph_is_not_part_of_the_ui():
    """Operator 2026-10-04: the Milly Neo4j graph is local only, not a page."""
    c = client(Warehouse(fixtures()))
    assert c.get("/milly/graph").status_code == 404
    for route in ROUTES:
        text = c.get(route + Q).text
        assert "/milly/graph" not in text and "Neo4j" not in text, route
    import nfl_dfs.dashboard.app as A
    assert "milly_graph" not in A.__dict__ and "G" not in A.__dict__


def test_repeat_finishers_is_season_wide_and_escaped():
    f = fixtures()
    f["insight_repeat_finishers"] = f["insight_repeat_finishers"].assign(
        username=["user_a", "<b>user_x</b>"])
    ins = client(Warehouse(f)).get("/insights?season=2026&week=1").text   # not a week filter
    assert "user_a" in ins and "&lt;b&gt;user_x&lt;/b&gt;" in ins and "<b>user_x" not in ins
    assert "No Millionaire standings with user names" in client(Warehouse()).get("/insights" + Q).text


def test_user_names_survive_into_the_insight_payload():
    wh = Warehouse(fixtures())
    df = D.fetch_insight(wh, "repeat_finishers", 2026)
    assert wh.calls == ["insight_repeat_finishers"]
    assert df.username.tolist() == ["user_a", "user_b"]


def test_fixtures_use_only_synthetic_user_names():
    """Real DraftKings user names never appear in tracked tests (operator
    2026-10-03): every user-name value in the dashboard fixtures is user_<x>,
    and no dashboard test file spells a user name outside that form."""
    import re
    from pathlib import Path

    from test_dashboard_milly import SYNTHETIC_USER
    names = list(top_rows().username) + list(fixtures()["insight_repeat_finishers"].username)
    assert names and all(re.fullmatch(SYNTHETIC_USER, n) for n in names), names
    here = Path(__file__).resolve().parent
    seen = 0
    for path in sorted(here.glob("test_dashboard_*.py")):
        text = path.read_text()
        for m in re.finditer(r"""["'](?:username|user)["']\s*[:=]\s*["']([^"']*)["']""", text):
            assert re.fullmatch(SYNTHETIC_USER, m.group(1)), (path.name, m.group(1))
            seen += 1
        for m in re.finditer(r"""(?:username|user)=["']([^"']*)["']""", text):
            assert re.fullmatch(SYNTHETIC_USER, m.group(1)) or "<" in m.group(1), (path.name, m.group(1))
            seen += 1
    assert seen >= 3                                   # the scan is not vacuous


def test_health():
    r = client(Warehouse(), env={"CODE_SHA": "abc"}).get("/health")
    assert r.json() == {"ok": True, "app": "dashboard-v2", "code_sha": "abc"}


def test_stake_rows():
    from nfl_dfs.dashboard.stakes import object_name, stake_rows
    plan = stake_rows(CONTESTS)
    assert plan.stake.tolist() == [60.0, 1.0] and plan.keep.tolist() == [3, 2]
    assert stake_rows(None).empty
    assert object_name(2026, 5) == "week-inputs/2026/w05/contests.json"


def test_milly_week_without_a_slate_says_so():
    f = fixtures()
    f["milly_slate"] = f["milly_slate"].iloc[0:0]
    milly = client(Warehouse(f)).get("/milly" + Q).text
    assert "stack unknown (0 of 9" in milly and "No lineup resolved fully" in milly
    assert "QB+0" not in milly


def test_contest_mismatch_and_published_cash_line_are_shown():
    f = fixtures()
    f["milly_contests"] = f["milly_contests"].assign(lobby_contest_id="c9", standings_contest_id="c1")
    f["contest_lines"] = pd.DataFrame([{"season": 2026, "week": 5, "contest_id": "c1", "cash_line": 155.5,
                                        "published_utc": "2026-10-12T09:00Z"}])
    c = client(Warehouse(f))
    assert "lobby&#x27;s Millionaire is c9" in c.get("/" + Q).text
    assert "155.50" in c.get("/milly" + Q).text
