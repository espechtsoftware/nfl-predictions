"""Proposed regression for finding 8; expected to fail before the source fix.

Explicitly run with pytest; not added to the production suite by this review.
Synthetic main-market quotes only, no alternate lines or real outcome data.
"""
import pandas as pd
from nfl_dfs.models.prop_market import latest_pre_main_lock


def test_moved_main_line_replaces_earlier_snapshot():
    rows = []
    for point, snapshot in (
        (49.5, "2026-09-20T09:00:00Z"),
        (59.5, "2026-09-20T16:00:00Z"),
        (69.5, "2026-09-20T18:00:00Z"),  # after common lock: excluded
    ):
        for side in ("Over", "Under"):
            rows.append(dict(season=2026, week=2, bookmaker="synthetic",
                             market="player_reception_yds", player="Synthetic Receiver",
                             outcome_name=side, price=-110, point=point,
                             snapshot_ts=snapshot))
    schedule = pd.DataFrame([dict(season=2026, week=2, gameday="2026-09-20",
                                 gametime="13:00", game_type="REG", weekday="Sunday")])
    quotes, _ = latest_pre_main_lock(pd.DataFrame(rows), schedule)
    assert set(quotes.point) == {59.5}, "Old main-line thresholds must not survive the latest snapshot"
    assert len(quotes) == 2
    assert set(quotes.outcome_name) == {"Over", "Under"}
    assert set(quotes.snapshot_ts) == {"2026-09-20T16:00:00Z"}
