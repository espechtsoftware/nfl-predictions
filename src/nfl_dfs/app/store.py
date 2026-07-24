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
    def defense_points_against(self, season: int | None = None) -> pd.DataFrame: ...


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


    def defense_points_against(self, season: int | None = None) -> pd.DataFrame:
        from ..bq import query_df

        where = f"WHERE season = {int(season)}" if season else ""
        return query_df(
            f"""
            SELECT * FROM `{settings.features}.defense_points_against`
            {where}
            ORDER BY season, week, position, team
            """
        )


class InMemoryStore:
    """For tests and local demos."""

    def __init__(self, frame: pd.DataFrame, defense: pd.DataFrame | None = None):
        self.frame = frame
        self.defense = defense if defense is not None else pd.DataFrame(
            columns=["team", "season", "week", "position", "fp_allowed",
                     "fp_allowed_l3", "fp_allowed_l6", "fp_allowed_season", "trend"]
        )

    def defense_points_against(self, season: int | None = None) -> pd.DataFrame:
        df = self.defense
        return df[df.season == season] if season else df

    def slates(self) -> pd.DataFrame:
        return (
            self.frame.groupby(["season", "week"])
            .size()
            .reset_index(name="players")
        )

    def projections(self, season: int, week: int) -> pd.DataFrame:
        df = self.frame
        return df[(df.season == season) & (df.week == week)].reset_index(drop=True)
