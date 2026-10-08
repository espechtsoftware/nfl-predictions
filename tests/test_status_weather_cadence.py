"""The weather feed's freshness bar matches its schedule (2026-10-08): s-weather loads Fri-Sun 08:00 CT and
s-freshness checks daily at 08:30 CT, so a healthy week never fails the check and a missed Friday load still does."""
from nfl_dfs import status


def _weather():
    (feed,) = [f for f in status.FEEDS if f.table == "weather"]
    return feed


def test_a_healthy_week_never_fails_and_a_missed_friday_load_does():
    healthy_worst = 4 * 24 + 0.5         # Sunday 08:00 load -> Thursday 08:30 check
    missed_friday = 5 * 24 + 0.5         # Sunday 08:00 load -> Friday 08:30 check, Friday's load missing
    assert healthy_worst < _weather().max_age_h < missed_friday
    assert _weather().alert
