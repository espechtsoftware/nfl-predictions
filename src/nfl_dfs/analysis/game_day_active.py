"""O-32 correction protocol (reports/2026-10-05-o32-correction-protocol.md): the ONE shared repair for player-level
projection-vs-outcome analyses on replay panels.

Replay panels (`nfl_predictions.slate_player_features`) keep players who did not play with `actual` = 0 and carry no
`was_active` column. This helper keeps a target row only if `nfl_raw.rosters_weekly` gives that player game-day status
ACT (any REG row: a player traded that week can carry two rows); a row with no roster row is dropped too. Game-day
status is announced ~90 minutes before kickoff, so the filter is point-in-time for a T-70 build. It is the frozen
study 22a reader's eligibility logic (deviation note 1), shared here so the six corrected analyses apply it identically.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

KEYS = ["season", "week", "gsis_id"]


def load_active(seasons: Iterable[int]) -> pd.DataFrame:
    from ..bq import query_df
    from ..config import settings

    return query_df(f"""
        SELECT season, week, gsis_id, LOGICAL_OR(status = 'ACT') AS act
        FROM `{settings.raw}.rosters_weekly`
        WHERE season IN UNNEST(@seasons) AND game_type = 'REG' AND gsis_id IS NOT NULL
        GROUP BY season, week, gsis_id
        """, params={"seasons": sorted({int(s) for s in seasons})})


def filter_game_day_active(rows: pd.DataFrame, active: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Rows whose player was ACT on game day, in the original order and columns; and the audit counts."""
    missing = set(KEYS) - set(rows.columns)
    if missing:
        raise ValueError(f"game-day filter needs {sorted(missing)}")
    act = active.assign(season=active.season.astype(int), week=active.week.astype(int),
                        gsis_id=active.gsis_id.astype(str)).drop_duplicates(KEYS).set_index(KEYS).act
    key = pd.MultiIndex.from_arrays([rows.season.astype(int), rows.week.astype(int), rows.gsis_id.astype(str)])
    status = pd.Series(act.reindex(key).to_numpy(), index=rows.index)
    keep = status.eq(True)
    audit = {"rule": "O-32 game-day rosters_weekly status ACT", "rows_in": int(len(rows)),
             "rows_kept": int(keep.sum()), "dropped_not_act": int(status.eq(False).sum()),
             "dropped_no_roster_row": int(status.isna().sum())}
    return rows[keep].copy(), audit


def apply(rows: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Load the game-day statuses for the rows' seasons and filter (the call the six analyses make)."""
    if rows.empty:
        return rows, {"rule": "O-32 game-day rosters_weekly status ACT", "rows_in": 0, "rows_kept": 0,
                      "dropped_not_act": 0, "dropped_no_roster_row": 0}
    return filter_game_day_active(rows, load_active(rows.season.unique()))
