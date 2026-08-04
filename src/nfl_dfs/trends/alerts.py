"""Salary-lag alerts (guide §8.5): DK reprices roles with a one-to-two-week
lag, so a detected changepoint with a flat salary is the highest-value
signal this system produces. The Tuesday report should name 5-10 players
whose role just changed; you should recognize most of them.
"""

from __future__ import annotations

import logging

import pandas as pd

from ..bq import SQL_DIR, load_dataframe, query_df, run_sql_file
from ..config import settings
from . import changepoint

log = logging.getLogger(__name__)

SALARY_LAG_MAX_DELTA = 500      # salary hasn't caught up yet
CHANGEPOINT_THRESHOLD = 0.5
RECENT_WEEKS = 2


def build_changepoints_table(season: int) -> pd.DataFrame:
    """Run detection over the season's usage panel and write
    nfl_features.changepoints. Uses target share for pass catchers and
    carry share for backs, taking the max signal of the two."""
    usage = query_df(
        f"""
        SELECT r.gsis_id, r.season, r.week,
               r.target_share, ru.carry_share
        FROM `{settings.features}.rz_receiving` r
        FULL OUTER JOIN `{settings.features}.rz_rushing` ru
          USING (game_id, season, week, team, gsis_id)
        WHERE COALESCE(r.season, ru.season) = {season}
        """
    )
    tgt = changepoint.detect_panel(usage.dropna(subset=["target_share"]),
                                   "target_share")
    car = changepoint.detect_panel(usage.dropna(subset=["carry_share"]),
                                   "carry_share")
    merged = (
        pd.concat([tgt.assign(signal="targets"), car.assign(signal="carries")])
        .sort_values("changepoint_prob", ascending=False)
        .drop_duplicates(["gsis_id", "season", "week"])
    )
    load_dataframe(merged, f"{settings.features}.changepoints")
    return merged


def is_salary_lagged(changepoint_prob: float, weeks_since_change: int,
                     salary_delta_wow: float | None) -> bool:
    """Pure mirror of the watchlist SQL predicate (external review
    2026-08-04: the threshold had no test). A Gadsden-type promotion —
    fresh usage changepoint, salary not yet repriced — must flag."""
    return (changepoint_prob > CHANGEPOINT_THRESHOLD
            and weeks_since_change <= RECENT_WEEKS
            and (salary_delta_wow is None
                 or salary_delta_wow < SALARY_LAG_MAX_DELTA))


def salary_lag_watchlist() -> pd.DataFrame:
    """The alert query: fresh changepoint + flat salary."""
    return query_df(
        f"""
        SELECT p.display_name, p.team_abbr AS team, c.signal,
               c.changepoint_prob, c.weeks_since_change,
               dk.salary, dk.salary_delta_wow,
               u.target_share_l4, u.target_share_std
        FROM `{settings.features}.changepoints` c
        JOIN `{settings.features}.dk_salary_week` dk USING (gsis_id, season, week)
        JOIN `{settings.features}.player_week_usage` u USING (gsis_id, season, week)
        JOIN `{settings.features}.player_id_map` p USING (gsis_id)
        WHERE c.changepoint_prob > {CHANGEPOINT_THRESHOLD}
          AND c.weeks_since_change <= {RECENT_WEEKS}
          AND (dk.salary_delta_wow IS NULL OR dk.salary_delta_wow < {SALARY_LAG_MAX_DELTA})
        ORDER BY c.changepoint_prob DESC
        """
    )


def run(season: int) -> None:
    build_changepoints_table(season)
    watch = salary_lag_watchlist()
    if watch.empty:
        log.info("No salary-lag candidates this week")
        return
    log.info("Salary-lag watchlist (%d players):\n%s",
             len(watch), watch.head(15).to_string(index=False))


if __name__ == "__main__":
    import sys

    from ..config import current_season

    logging.basicConfig(level=logging.INFO)
    run(int(sys.argv[1]) if len(sys.argv) > 1 else current_season())
