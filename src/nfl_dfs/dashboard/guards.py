"""Clock guards shared by the publisher and the deploy script.

The money path builds and late-swaps a week's books on the laptop until the
Sunday afternoon window closes. Nothing the dashboard ships may read the live
week directories (or replace the app) before then.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")
WINDOW_CLOSE_LOCAL = time(15, 30)


def week1_sunday(season: int) -> date:
    """The NFL's Week-1 Sunday: the Sunday after Labor Day (the first
    Monday of September). 2026 -> 2026-09-13; 2025 -> 2025-09-07."""
    d = date(season, 9, 1)
    labor_day = d + timedelta(days=(0 - d.weekday()) % 7)
    return labor_day + timedelta(days=6)


def week_sunday(season: int, week: int) -> date:
    if week < 1:
        raise ValueError(f"week must be >= 1, got {week}")
    return week1_sunday(season) + timedelta(days=7 * (week - 1))


def live_window_close(season: int, week: int) -> datetime:
    """When the week's Sunday build/swap window closes (15:30 Central), UTC."""
    local = datetime.combine(week_sunday(season, week), WINDOW_CLOSE_LOCAL,
                             tzinfo=CENTRAL)
    return local.astimezone(timezone.utc)


def week_is_live(season: int, week: int, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return now < live_window_close(season, week)
