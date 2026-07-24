"""Projection storage behind a small interface so the API is testable
without a warehouse and swappable later."""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from ..config import settings

PROJ_COLUMNS = [
    "season", "week", "slate_id", "gsis_id", "dk_player_id", "display_name",
    "position", "team", "opponent", "salary",
    "proj_points", "proj_p10", "proj_p50", "proj_p90", "proj_std",
    "p_20_plus", "value", "model_version", "generated_at",
]


class ProjectionStore(Protocol):
    def slates(self) -> pd.DataFrame: ...
    def projections(self, season: int, week: int) -> pd.DataFrame: ...


class BigQueryStore:
    def slates(self) -> pd.DataFrame:
        from ..bq import query_df

        return query_df(
            f"""
            SELECT season, week, slate_id, COUNT(*) AS players,
                   MAX(generated_at) AS last_generated
            FROM `{settings.predictions}.player_projections`
            GROUP BY 1, 2, 3
            ORDER BY season DESC, week DESC
            """
        )

    def projections(self, season: int, week: int) -> pd.DataFrame:
        from ..bq import query_df

        return query_df(
            f"""
            SELECT * EXCEPT (rn) FROM (
              SELECT *, ROW_NUMBER() OVER (
                PARTITION BY dk_player_id ORDER BY generated_at DESC) AS rn
              FROM `{settings.predictions}.player_projections`
              WHERE season = @season AND week = @week
            ) WHERE rn = 1
            ORDER BY proj_points DESC
            """,
            params={"season": season, "week": week},
        )


class InMemoryStore:
    """For tests and local demos."""

    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    def slates(self) -> pd.DataFrame:
        return (
            self.frame.groupby(["season", "week"])
            .size()
            .reset_index(name="players")
        )

    def projections(self, season: int, week: int) -> pd.DataFrame:
        df = self.frame
        return df[(df.season == season) & (df.week == week)].reset_index(drop=True)
