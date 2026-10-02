"""fantasy_points_articles: the week filter and the article record (no browser, no network)."""
import pytest

from nfl_dfs.ops import fantasy_points_articles as fpa

LISTING = [
    {"title": "Ryan Heath's 2026 Week 4 Fantasy Football Advanced Matchups", "slug": "ryan-heath-s-2026-week-4-fantasy-football-advanced-matchups",
     "path": "/nfl/articles/2026/ryan-heath-s-2026-week-4-fantasy-football-advanced-matchups", "season": 2026},
    {"title": "2026 Week 4 DraftKings/FanDuel DFS Main Slate Early Look", "slug": "week-4-draftkings-fanduel-dfs-main-slate-early-look",
     "path": "/nfl/articles/2026/week-4-draftkings-fanduel-dfs-main-slate-early-look", "season": 2026},
    {"title": "2026 Week 3 Monday Showdown", "slug": "week-3-monday-draftkings-showdown-analysis-phi-chi", "path": "/a/w3", "season": 2026},
    {"title": "Week 14 rankings", "slug": "week-14-rankings", "path": "/a/w14", "season": 2026},
    {"title": "2026 Fantasy Football Injury Tracker", "slug": "fantasy-football-injury-tracker", "path": "/a/inj", "season": 2026},
    {"title": "2025 Week 4 recap", "slug": "week-4-recap", "path": "/a/old", "season": 2025},
    {"title": "dup", "slug": "week-4-staff-picks", "path": "/nfl/articles/2026/week-4-draftkings-fanduel-dfs-main-slate-early-look", "season": 2026},
]


def test_select_takes_the_week_and_the_injury_tracker_only():
    got = [a["path"] for a in fpa.select_articles(LISTING, season=2026, week=4)]
    assert got == ["/nfl/articles/2026/ryan-heath-s-2026-week-4-fantasy-football-advanced-matchups",
                   "/nfl/articles/2026/week-4-draftkings-fanduel-dfs-main-slate-early-look", "/a/inj"]   # not week 3/14, not 2025, no dup


def test_record_keeps_the_author_name_only_and_refuses_previews():
    art = {"articleId": 7, "slug": "s", "path": "/p", "title": "T", "author": {"name": "Ryan Heath", "email": "x@y.com"},
           "categories": ["DFS"], "publishedDate": "2026-10-02T12:43:00Z", "topic": "dfs"}
    rec = fpa.article_record(art, "x" * 500, season=2026, week=4)
    assert rec["author"] == "Ryan Heath" and "email" not in str(rec) and rec["text_chars"] == 500
    with pytest.raises(RuntimeError, match="paywall preview"):
        fpa.article_record(art, "short teaser", season=2026, week=4)
    with pytest.raises(RuntimeError, match="locked"):
        fpa.article_record({**art, "access": {"locked": True}}, "x" * 500, season=2026, week=4)


def test_author_list_gives_the_names():
    art = {"articleId": 1, "slug": "s", "author": [{"name": "Tom Brolley", "authorId": "x", "title": "Owner"}, {"name": "Scott Barrett"}]}
    assert fpa.article_record(art, "x" * 400, season=2026, week=4)["author"] == "Tom Brolley, Scott Barrett"
