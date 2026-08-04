"""Salary-lag alert threshold contract (external review 4.3)."""
from nfl_dfs.trends.alerts import (CHANGEPOINT_THRESHOLD, is_salary_lagged)


def test_gadsden_type_promotion_flags():
    # fresh changepoint, salary flat -> must flag
    assert is_salary_lagged(0.9, 1, 0.0)
    assert is_salary_lagged(0.9, 1, None)      # DK row missing delta
    assert is_salary_lagged(0.9, 2, 400.0)     # under the 500 threshold


def test_repriced_or_stale_do_not_flag():
    assert not is_salary_lagged(0.9, 1, 800.0)   # salary already caught up
    assert not is_salary_lagged(0.9, 9, 0.0)     # old news
    assert not is_salary_lagged(CHANGEPOINT_THRESHOLD - 0.01, 1, 0.0)
