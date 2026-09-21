import pandas as pd
from nfl_dfs.ingest.sis_team_context_weekly import KEY, coverage, plan_append


def _frame():
    return pd.DataFrame({
        "season": [2026] * 4, "week": [1, 1, 2, 2], "team": ["DET", "NO", "BUF", "DET"], "opp": ["NO", "DET", "DET", "BUF"],
        "game_key": ["2026-01-DET-NO", "2026-01-DET-NO", "2026-02-BUF-DET", "2026-02-BUF-DET"], "x": [1.0, 2.0, 3.0, 4.0],
    })


def test_plan_append_skips_existing_team_weeks_and_names_them():
    to_append, skipped = plan_append(_frame(), {(2026, 1, "DET"), (2026, 1, "NO")})
    assert to_append.week.tolist() == [2, 2] and skipped == [(2026, 1, "DET"), (2026, 1, "NO")]
    to_append, skipped = plan_append(_frame(), set())
    assert len(to_append) == 4 and skipped == []


def test_coverage_reports_partial_weeks():
    f = _frame().iloc[:3]                      # Week 2 has only one side of BUF-DET (SIS charting still posting)
    c = coverage(f)
    assert c["2026-01"] == {"rows": 2, "games": 1, "games_with_both_sides": 1, "games_one_side": 0}
    assert c["2026-02"] == {"rows": 1, "games": 1, "games_with_both_sides": 0, "games_one_side": 1}
    assert KEY == ("season", "week", "team")
