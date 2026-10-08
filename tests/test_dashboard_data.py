"""Dashboard v2 data layer: team mapping, implied totals, newest batch,
weekly ranks, accuracy, ownership calibration, leverage, SQL rendering and
the clock guards. Synthetic rows only."""
from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.dashboard import data as D
from nfl_dfs.dashboard import guards
from nfl_dfs.dashboard.teams import (TEAM_NAMES, canon_team, display_team, norm_name,
                                     parse_event_name)


# ------------------------------------------------------------------ teams --

def test_team_names_match_the_ingest_map():
    from nfl_dfs.ingest.fantasy_points_coverage import TEAM_NAMES as INGEST
    assert TEAM_NAMES == INGEST


@pytest.mark.parametrize("raw, code", [
    ("LAR", "LA"), ("LA", "LA"), ("Los Angeles Rams", "LA"), ("Rams", "LA"),
    ("JAC", "JAX"), ("WSH", "WAS"), ("OAK", "LV"), ("sd", "LAC"), ("Vikings", "MIN"),
    ("KC", "KC"), ("", None), (None, None), ("nan", None), ("XYZ", None),
])
def test_canon_team(raw, code):
    assert canon_team(raw) == code


def test_display_team_shows_draftkings_spelling():
    assert display_team("LA") == "LAR"
    assert display_team("Los Angeles Rams") == "LAR"
    assert display_team("BUF") == "BUF"


def test_parse_event_name_and_norm_name():
    assert parse_event_name("Los Angeles Rams @ Philadelphia Eagles") == ("LA", "PHI")
    assert parse_event_name("no separator") == (None, None)
    assert norm_name("Sample Runner III") == norm_name("Sample Runner")
    assert norm_name("Ta'Sample Catcher") == "TASAMPLECATCHER"
    assert norm_name("A.B. Sample Jr.") == "ABSAMPLE"


def test_player_key_dst_is_its_team():
    assert D.player_key("Rams", "DST", "LAR") == D.player_key("Los Angeles Rams", "D", "LA") == "DST:LA"
    assert D.player_key("Player One Jr.", "WR", "LAR") == "PLAYERONE:LA"


# --------------------------------------------------------- implied totals --

def test_implied_math():
    away, home = D.implied(48.0, -3.0)          # home favored by 3
    assert home == pytest.approx(25.5) and away == pytest.approx(22.5)
    assert away + home == pytest.approx(48.0)


def _odds(rows):
    return pd.DataFrame(rows, columns=["pulled_at", "event_id", "event_name", "start_time",
                                       "market_type", "selection", "line", "odds_american"])


def _game_rows(ev, name, start, pulled, total, home_sel, home_line, away_sel=None, away_line=None):
    out = [(pulled, ev, name, start, "Total", "Over", total, -110),
           (pulled, ev, name, start, "Total", "Under", total, -110)]
    if home_sel:
        out.append((pulled, ev, name, start, "Spread", home_sel, home_line, -110))
    if away_sel:
        out.append((pulled, ev, name, start, "Spread", away_sel, away_line, -110))
    return out


def test_odds_game_lines_newest_prekick_and_movement():
    start = "2026-10-04T17:00:00Z"
    name = "Los Angeles Rams @ Philadelphia Eagles"
    rows = (_game_rows("e1", name, start, "2026-09-20T12:00:00Z", 40.0, "Philadelphia Eagles", 9.0)  # too early
            + _game_rows("e1", name, start, "2026-09-30T12:00:00Z", 42.0, "Philadelphia Eagles", 1.5)
            + _game_rows("e1", name, start, "2026-10-03T12:00:00Z", 42.5, "Philadelphia Eagles", 3.5)
            + _game_rows("e1", name, start, "2026-10-04T18:00:00Z", 60.0, "Philadelphia Eagles", -9.0))  # live
    lines = D.odds_game_lines(_odds(rows))
    r = lines.iloc[0]
    assert (r.away, r.home) == ("LA", "PHI")
    assert r.total == 42.5 and r.home_spread == 3.5
    assert r.total_open == 42.0 and r.home_spread_open == 1.5
    assert r.n_pulls == 2


def test_odds_game_lines_uses_minus_away_line_when_home_row_missing():
    rows = _game_rows("e2", "Buffalo Bills @ Miami Dolphins", "2026-10-04T17:00:00Z",
                      "2026-10-03T12:00:00Z", 50.0, None, None, "Buffalo Bills", -6.5)
    r = D.odds_game_lines(_odds(rows)).iloc[0]
    assert r.home_spread == 6.5


def _games():
    return pd.DataFrame([
        {"season": 2026, "week": 4, "game_id": "g1", "gameday": "2026-10-04", "gametime": "13:00",
         "weekday": "Sunday", "home_team": "PHI", "away_team": "LA"},
        {"season": 2026, "week": 4, "game_id": "g2", "gameday": "2026-10-04", "gametime": "20:20",
         "weekday": "Sunday", "home_team": "CAR", "away_team": "DET"},
        {"season": 2026, "week": 4, "game_id": "g3", "gameday": "2026-10-01", "gametime": "20:15",
         "weekday": "Thursday", "home_team": "CLE", "away_team": "PIT"},
    ])


def test_implied_totals_odds_fallback_and_main_slate():
    rows = _game_rows("e1", "Los Angeles Rams @ Philadelphia Eagles", "2026-10-04T17:00:00Z",
                      "2026-10-03T12:00:00Z", 42.5, "Philadelphia Eagles", 3.5)
    ctx = pd.DataFrame([{"team": "CAR", "opponent": "DET", "is_home": 1, "implied_team_total": 23.5,
                         "spread": 3.5, "game_total": 50.5}])
    t = D.implied_totals(_games(), _odds(rows), ctx, main_teams={"LA", "PHI"}).set_index("game_id")
    assert t.loc["g1", "source"] == "odds"
    assert t.loc["g1", "home_implied"] == pytest.approx(19.5)
    assert t.loc["g1", "away_implied"] == pytest.approx(23.0)
    assert t.loc["g2", "source"] == "nflverse"
    assert t.loc["g2", "home_implied"] == pytest.approx(23.5)
    assert t.loc["g3", "source"] == "none" and np.isnan(t.loc["g3", "home_implied"])
    assert t.loc["g1", "main_slate"] == True and t.loc["g2", "main_slate"] == False  # noqa: E712
    unknown = D.implied_totals(_games(), _odds(rows), ctx, main_teams=set())
    assert unknown.main_slate.isna().all()


def test_main_slate_fallback_is_the_sunday_afternoon_window():
    assert D.main_slate_fallback(_games()) == {"LA", "PHI"}


# ------------------------------------------------------------ newest batch --

def test_newest_rows_overall_and_by_group():
    df = pd.DataFrame({"slate": [1, 1, 2, 2], "x": [1, 2, 3, 4],
                       "ts": ["2026-10-01T10:00Z", "2026-10-02T10:00Z",
                              "2026-10-01T10:00Z", "2026-10-01T09:00Z"]})
    assert D.newest_rows(df, "ts").x.tolist() == [2]
    assert sorted(D.newest_rows(df, "ts", by=["slate"]).x) == [2, 3]
    assert D.newest_rows(df.iloc[0:0], "ts").empty


def test_fp_main_slate_prefers_the_draft_group_then_main():
    fp = pd.DataFrame({"slate_id": ["1", "2", "2"], "slate_name": ["Thu-Mon", "Main", "Main"],
                       "name": ["a", "b", "b"], "retrieved_at": ["2026-10-01", "2026-10-01", "2026-10-02"]})
    assert D.fp_main_slate(fp, 1).name.tolist() == ["a"]
    out = D.fp_main_slate(fp, None)
    assert out.name.tolist() == ["b"] and str(out.retrieved_at.iloc[0]) == "2026-10-02"


def test_player_board_joins_fp_and_exposure():
    proj = pd.DataFrame([
        {"dk_player_id": 1, "display_name": "Alpha Player", "position": "QB", "team": "LA",
         "opponent": "PHI", "salary": 6000, "proj_points": 20.0, "proj_p90": 35.0},
        {"dk_player_id": 2, "display_name": "Rams", "position": "DST", "team": "LAR",
         "opponent": "PHI", "salary": 3000, "proj_points": 7.0, "proj_p90": 15.0}])
    fp = pd.DataFrame([{"name": "Alpha Player", "position": "QB", "team": "LAR", "fantasy_points": 18.0},
                       {"name": "Rams", "position": "DST", "team": "LAR", "fantasy_points": 8.0}])
    own = pd.DataFrame([{"name": "Alpha Player", "position": "QB", "team": "LAR",
                         "projected_ownership_pct": 12.0, "retrieved_at": "2026-10-02"}])
    exp = pd.DataFrame([{"dk_player_id": 1, "pool_share": 0.5, "book_share": 0.25}])
    b = D.player_board(proj, fp, own, exp).set_index("display_name")
    assert b.loc["Alpha Player", "fp_proj"] == 18.0
    assert b.loc["Alpha Player", "proj_minus_fp"] == pytest.approx(2.0)
    assert b.loc["Alpha Player", "book_minus_fp_own"] == pytest.approx(13.0)
    assert b.loc["Rams", "fp_proj"] == 8.0 and np.isnan(b.loc["Rams", "book_share"])


# ------------------------------------------------------------- weekly ranks --

def test_weekly_ranks_rank_summary_and_trend():
    rows = []
    for wk, vals in enumerate([(30, 20, 10), (10, 20, 30), (20, 30, 10), (25, 15, 5)], start=1):
        rows += [{"team": t, "week": wk, "v": v} for t, v in zip("ABC", vals)]
    long, summ = D.weekly_ranks(pd.DataFrame(rows), "v")
    r = long.set_index(["team", "week"])["rank"]
    assert r[("A", 1)] == 1 and r[("C", 2)] == 1 and r[("B", 3)] == 1
    s = summ.set_index("team")
    assert s.loc["A", "season"] == pytest.approx(21.25)
    assert s.loc["A", "l3"] == pytest.approx((10 + 20 + 25) / 3)
    assert s.loc["A", "trend"] == pytest.approx(s.loc["A", "l3"] - 21.25)
    assert s.loc["A", "latest_rank"] == 1 and s.loc["A", "season_rank"] == 1
    _, low = D.weekly_ranks(pd.DataFrame(rows), "v", higher_is_better=False)
    assert low.iloc[0].team == "C"


def test_weekly_ranks_leave_out_an_in_progress_week():
    rows = [{"team": t, "week": 1, "v": i} for i, t in enumerate("ABCD")]
    rows += [{"team": "A", "week": 2, "v": 99}]          # only Thursday played
    long, summ = D.weekly_ranks(pd.DataFrame(rows), "v")
    assert set(long.week) == {1}
    assert summ.set_index("team").loc["A", "games"] == 1


def test_defense_totals_all_and_one_position():
    dpa = pd.DataFrame([{"team": "A", "week": 1, "position": p, "fp_allowed": v}
                        for p, v in (("QB", 20), ("RB", 25), ("WR", 40), ("TE", 10))])
    assert D.defense_totals(dpa).fp_allowed.tolist() == [95]
    assert D.defense_totals(dpa, "WR").fp_allowed.tolist() == [40]


# --------------------------------------------------------------- accuracy --

def _ours():
    return pd.DataFrame([
        {"week": 1, "gsis_id": "g1", "display_name": "Player A", "position": "WR", "team": "BUF",
         "salary": 7000, "proj_points": 15.0, "dk_points": 20.0},
        {"week": 1, "gsis_id": "g2", "display_name": "Player B", "position": "RB", "team": "MIA",
         "salary": 6000, "proj_points": 12.0, "dk_points": 4.0},
        {"week": 1, "gsis_id": "g3", "display_name": "Player C", "position": "TE", "team": "MIA",
         "salary": 3000, "proj_points": 2.0, "dk_points": 0.0},        # below min_proj
    ])


def _fp():
    return pd.DataFrame([{"week": 1, "name": "Player A", "position": "WR", "team": "BUF", "fantasy_points": 19.0},
                         {"week": 1, "name": "Player B", "position": "RB", "team": "MIA", "fantasy_points": 5.0}])


def test_accuracy_by_week():
    acc = D.accuracy_by_week(_ours(), _fp()).set_index(["week", "position"])
    allp = acc.loc[(1, "ALL")]
    assert allp.n == 2
    assert allp.mae_ours == pytest.approx((5 + 8) / 2)
    assert allp.bias_ours == pytest.approx((-5 + 8) / 2)
    assert allp.n_common == 2 and allp.mae_fp_common == pytest.approx((1 + 1) / 2)
    assert acc.loc[(1, "WR")].mae_ours == pytest.approx(5)
    assert D.accuracy_by_week(pd.DataFrame(), _fp()).empty


def test_projection_disagreements_who_was_right():
    summ, players = D.projection_disagreements(_ours(), _fp(), threshold=4.0)
    s = summ.set_index("position").loc["ALL"]
    assert s.n == 2 and s.fp_closer == 2 and s.ours_closer == 0
    assert set(players.closer) == {"FP"}
    none, _ = D.projection_disagreements(_ours(), _fp(), threshold=50)
    assert none.empty


def test_ownership_calibration_population_and_bins():
    pred = pd.DataFrame({"week": 1, "name": ["P1", "P2", "P3", "P4"], "own": [1.0, 12.0, 25.0, 8.0]})
    real = pd.DataFrame({"week": 1, "display_name": ["P1", "P2", "P3"], "own": [2.0, 10.0, 30.0]})
    cal, weeks = D.ownership_calibration(pred, real)
    w = weeks.iloc[0]
    assert w.n == 3 and w.undrafted == 1
    assert w.spearman == pytest.approx(1.0)
    assert w.mae == pytest.approx((1 + 2 + 5) / 3)
    assert cal.n.sum() == 3


def test_book_leverage_active_share():
    exp = pd.DataFrame({"player": ["A", "B"], "position": ["QB", "WR"], "book_share": [1.0, 0.5]})
    own = pd.DataFrame({"display_name": ["A", "C"], "own": [40.0, 20.0], "fpts": [20.0, 5.0]})
    lev, s = D.book_leverage(exp, own)
    t = lev.set_index("player")
    assert t.loc["A", "leverage"] == pytest.approx(60.0)
    assert t.loc["B", "field_pct"] == 0.0 and t.loc["C", "book_pct"] == 0.0
    assert s["active_share"] == pytest.approx(0.5 * (60 + 50 + 20) / 100 / 9)


# ------------------------------------------------------------ SQL & clocks --

def test_render_substitutes_includes_and_marks():
    sql = D.render("milly_lines", season=2026)
    assert D.sql_name(sql) == "milly_lines"
    assert "${" not in sql and "dk_contest_fills_nfl" in sql      # resolver inlined
    ins = D.render("insight_leverage_paid", season=2026)
    assert "CREATE TEMP FUNCTION norm" in ins and "fpo AS" in ins and "${" not in ins
    with pytest.raises(ValueError):
        D.render("milly_lines")                                   # season missing


def test_lock_and_current_week():
    sch = _games()
    assert D.lock_utc(sch, 4) == datetime(2026, 10, 4, 17, 0, tzinfo=timezone.utc)
    assert D.current_week(sch, today=date(2026, 10, 2)) == 4
    assert D.current_week(sch, today=date(2027, 1, 1)) == 4
    assert D.current_week(sch.iloc[0:0]) is None


def test_guards_week_window():
    assert guards.week1_sunday(2026) == date(2026, 9, 13)
    assert guards.week1_sunday(2025) == date(2025, 9, 7)
    assert guards.week_sunday(2026, 4) == date(2026, 10, 4)
    close = guards.live_window_close(2026, 4)
    assert close == datetime(2026, 10, 4, 20, 30, tzinfo=timezone.utc)
    assert guards.week_is_live(2026, 4, datetime(2026, 10, 4, 20, 29, tzinfo=timezone.utc))
    assert not guards.week_is_live(2026, 4, datetime(2026, 10, 4, 20, 30, tzinfo=timezone.utc))
    assert not guards.week_is_live(2026, 1, datetime(2026, 10, 3, tzinfo=timezone.utc))


def test_ownership_calibration_joins_on_name_and_team():
    """Two players share a name on different teams: with teams on both sides
    each is scored against his own realized ownership, never merged."""
    pred = pd.DataFrame({"week": 1, "name": ["Twin", "Twin", "Solo"], "team": ["BUF", "LAR", "KC"],
                         "own": [20.0, 2.0, 10.0]})
    real = pd.DataFrame({"week": 1, "display_name": ["Twin", "Twin", "Solo"], "team": ["BUF", "LA", None],
                         "own": [18.0, 3.0, 9.0]})
    cal, weeks = D.ownership_calibration(pred, real)
    w = weeks.iloc[0]
    assert w.n == 2 and w.mae == pytest.approx((2 + 1) / 2)    # Solo: unresolved team, left out


def test_book_leverage_joins_on_dk_id_when_resolved():
    exp = pd.DataFrame({"player": ["Twin", "Twin"], "dk_player_id": [11, 12], "position": ["WR", "WR"],
                        "book_share": [0.5, 0.0]})
    own = pd.DataFrame({"display_name": ["Twin", "Twin"], "dk_player_id": [11, 12], "own": [5.0, 30.0],
                        "fpts": [20.0, 2.0]})
    lev, _ = D.book_leverage(exp, own)
    assert sorted(lev.leverage.round(1)) == [-30.0, 45.0]


# --------------------------------------------- SQL contracts (reviewer fixes) --
# BigQuery cannot run offline; these pin the rendered text of each fix (every
# template was also dry-run against BigQuery when it was written).

def _sql(name, **kw):
    return " ".join(D.render(name, **{"season": 2026, **kw}).split())


def test_unplayed_weeks_are_not_scored_as_zeros():
    for name in ("accuracy_ours", "defense_weekly"):
        sql = _sql(name)
        assert "HAVING LOGICAL_OR(has_stat_line)" in sql, name
    assert "JOIN played t ON t.season = a.season AND t.week = a.week AND t.team = a.team" in _sql("accuracy_ours")
    assert "JOIN faced f ON f.season = d.season AND f.week = d.week AND f.defense = d.team" in _sql("defense_weekly")


def test_cuts_use_rank_so_ties_are_inside():
    assert "RANK() OVER (PARTITION BY contest_id ORDER BY points DESC) AS pos" in _sql("milly_lines")
    assert "RANK() OVER (PARTITION BY contest_id ORDER BY points DESC) AS pos" in _sql(
        "insight_leverage_paid")                                       # via field_ranked
    top = _sql("milly_top_lineups", top_n=10, top_share=0.01, cash_rows=0)
    assert "WHERE rk <= LEAST(10," in top


def test_book_vs_top_only_weeks_with_standings():
    assert "COALESCE(own.week, pe.week) IN (SELECT DISTINCT week FROM r)" in _sql("insight_book_vs_top")


def test_week_points_come_from_the_millionaire_only():
    sql = _sql("week_player_points", week=5)
    assert "JOIN m ON m.season = o.season AND m.week = o.week AND m.contest_id = o.contest_id" in sql


def test_publications_are_chosen_scored_first_and_by_published_utc():
    arms = _sql("arms_weekly")
    assert "LOGICAL_OR(mean_points IS NOT NULL)" in arms and "ORDER BY scored DESC, published_utc DESC" in arms
    for name in ("pool_exposure", "insight_book_fp", "insight_book_vs_top"):
        assert "QUALIFY published_utc = MAX(published_utc) OVER (PARTITION BY week)" in _sql(name), name
        assert "built_utc = MAX" not in _sql(name)
    ddl = _sql("ddl")
    assert "published_utc TIMESTAMP ) CLUSTER BY" in ddl and "contest_lines" in ddl


def test_millionaire_prefers_the_contest_with_standings():
    sql = _sql("milly_contests")
    assert "CASE WHEN nf.n_entries IS NOT NULL THEN f.contest_id ELSE COALESCE(e.contest_id, f.contest_id) END" in sql
    assert "f.contest_id AS lobby_contest_id" in sql and "e.contest_id AS standings_contest_id" in sql


def test_name_joins_resolve_through_the_slate_and_drop_collisions():
    for name in ("insight_winners_vs_field", "insight_leverage_paid", "insight_stacks", "insight_book_vs_top",
                 "milly_field_ownership"):
        sql = _sql(name)
        assert "HAVING COUNT(DISTINCT s.dk_player_id) = 1" in sql, name
    assert "pe.dk_player_id = own.dk_player_id" in _sql("insight_book_vs_top")
    fp = _sql("insight_winners_vs_field")
    assert "fpo.k = s.k AND fpo.team = s.team" in fp and "GROUP BY 1, 2, 3 HAVING COUNT(*) = 1" in fp


def test_user_name_is_the_entry_name_without_its_counter():
    """Operator 2026-10-03: DraftKings user names are kept in the Milly
    derivations (the entry name minus its "(k/n)" counter)."""
    rx = r"REGEXP_REPLACE(TRIM(x.entry_name), r'\s*\(\d+/\d+\)$', '') AS username"
    assert rx in _sql("milly_top_lineups", top_n=10, top_share=0.01, cash_rows=0)
    import re
    pattern = r"\s*\(\d+/\d+\)$"                    # the same rule, applied in Python
    assert re.sub(pattern, "", "user_a (3/150)") == "user_a"
    assert re.sub(pattern, "", "user_b") == "user_b"


def test_repeat_finishers_sql_contract():
    sql = _sql("insight_repeat_finishers")
    assert D.sql_name(D.render("insight_repeat_finishers", season=2026)) == "insight_repeat_finishers"
    assert "${" not in sql and "dk_contest_fills_nfl" in sql                 # one Millionaire per week
    assert "REGEXP_REPLACE(TRIM(x.entry_name), r'\\s*\\(\\d+/\\d+\\)$', '') AS username" in sql
    assert ("QUALIFY ROW_NUMBER() OVER (PARTITION BY x.contest_id, x.entry_id "
            "ORDER BY x.imported_at DESC) = 1") in sql                        # newest import wins
    assert "RANK() OVER (PARTITION BY contest_id ORDER BY points DESC) AS pos" in sql
    # names are filtered AFTER ranking: blank-name entries still count toward the field
    assert sql.index("RANK() OVER") < sql.index("WHERE username IS NOT NULL AND username != ''")
    assert "pos <= GREATEST(1, CAST(CEIL(0.01 * n) AS INT64)) AS top1" in sql
    assert "pos <= GREATEST(1, CAST(CEIL(0.001 * n) AS INT64)) AS top01" in sql
    assert "WHERE x.season = 2026 QUALIFY" in sql and not __import__("re").search(r"\.week = \d", sql)  # season-wide
    assert sql.rstrip().endswith("LIMIT 50")
    for col in ("entries", "weeks", "top1_lineups", "top1_weeks", "top01_lineups", "best_rank",
                "top1_rate", "top_qb", "top_qb_lineups"):
        assert f" AS {col}" in sql or f"u.{col}" in sql, col



@pytest.mark.parametrize("fetch", [D.fetch_exposure, D.fetch_milly_slate, D.fetch_field_ownership, D.fetch_milly_top])
def test_every_week_filter_alias_is_declared_in_its_sql(fetch):
    """2026-10-05: /players and /accuracy failed live ("Unrecognized name: pool_exposure"): the week filter named an
    alias the SQL never declared. The app tests stub every query, so capture each fetch's SQL for one week and require
    every `<alias>.week = 4` filter to use an alias the SQL declares (`... AS alias`, `` `table` alias`` or a CTE)."""
    import re
    seen = []
    fetch(lambda sql: seen.append(sql) or pd.DataFrame(), 2026, 4)
    sql = seen[0]
    aliases = set(re.findall(r"\b(\w+)\.week = 4\b", sql))
    assert aliases, "no week filter rendered"
    for a in aliases:
        declared = rf"(\bAS\s+{a}\b(?!\s*\()|`\s+{a}\b|\b(?:WITH|,)\s*{a}\s+AS\s*\()"   # table alias or a CTE named a
        assert re.search(declared, sql), f"{fetch.__name__}: filters on {a}.week but never declares {a}"


def test_user_lineups_refuse_unsafe_names_and_render_top_columns():
    """--users-file (operator 10-06): names are inlined as a literal, so anything outside [A-Za-z0-9_.-] is refused;
    the SQL returns milly_top_lineups' columns, filters every lineup of the listed users, and declares its week alias."""
    import re
    for bad in ("a'b", "x; DROP TABLE t", "", "a b"):
        with pytest.raises(ValueError):
            D.fetch_milly_user_lineups(lambda sql: pd.DataFrame(), 2026, 4, [bad])
    seen = []
    D.fetch_milly_user_lineups(lambda sql: seen.append(sql) or pd.DataFrame(), 2026, 4, ["user_b", "user_a", "user_a"])
    sql = seen[0]
    assert "username IN UNNEST(['user_a', 'user_b'])" in sql
    for col in ("lineup_key", "rank", "points", "lineup_slots_json", "dupes", "n_entries", "username", "at_cash_line"):
        assert re.search(rf"\b{col}\b", sql), col
    for a in set(re.findall(r"\b(\w+)\.week = 4\b", sql)):
        assert re.search(rf"`\s+{a}\b|\bAS\s+{a}\b", sql), a


def test_every_dashboard_template_renders():
    """EVERY sql/dashboard/*.sql renders through D.render, which raises on any unresolved placeholder (2026-10-08: moved
    here from test_dk_client's pipeline render test, whose renderer cannot fill the dashboard's own ${season} / ${inc:}
    templates). Placeholders render fills itself are left to it; the rest get season=2026 or a dummy value."""
    import re as _re
    files = sorted(D.SQL_DIR.glob("*.sql"))
    assert len(files) >= 30, files
    self_filled = {"raw", "features", "predictions", "dashboard", "week_filter", "week_filter_m", "milly_contests"}
    names = set()
    for f in files:
        names |= set(_re.findall(r"\$\{(\w+)\}", f.read_text()))      # ${inc:NAME} has a colon: not matched, render inlines it
    subs = {n: "1" for n in names - self_filled}
    subs["season"] = 2026
    for f in files:
        sql = D.render(f.stem, **subs)
        assert "${" not in sql, f.name
