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


SHOWDOWN_COLUMNS = [
    "draft_group_id", "dk_player_id", "dk_draftable_id",
    "dk_cpt_draftable_id", "display_name", "team_abbr",
    "position", "salary", "game_start", "status", "dk_ppg",
]


CLASSIC_COLUMNS = [
    "draft_group_id", "dk_player_id", "dk_draftable_id", "display_name",
    "team_abbr", "position", "salary", "game_start", "status",
]


class ProjectionStore(Protocol):
    def slates(self) -> pd.DataFrame: ...
    def projections(self, season: int, week: int) -> pd.DataFrame: ...
    def defense_points_against(self, season: int | None = None) -> pd.DataFrame: ...
    def showdown_salaries(self) -> pd.DataFrame: ...
    def classic_slates(self) -> pd.DataFrame: ...
    def classic_salaries(self, draft_group_id: int) -> pd.DataFrame: ...
    def classic_draftable_ids(self) -> pd.DataFrame: ...


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


    def trailing_kdst(self, season: int, week: int) -> pd.DataFrame:
        """Trailing-mean DK points for K and DST, strictly-prior weeks of
        `season` (min 2 games) — the live showdown pool's fallback for the
        positions the model doesn't cover, replacing raw dk_ppg (issue
        #10's last item). K scoring is computed from distance-bucketed
        kicking stats (DK: 3/4/5-pt FGs + PAT); DST from pbp + schedules
        (sacks/takeaways/TDs + points-allowed brackets).

        Columns: kind ('K'|'DST'), key (UPPER player name for K, team
        abbr for DST), trailing_pts."""
        from ..bq import query_df

        return query_df(
            f"""
            WITH k AS (
              SELECT 'K' AS kind, UPPER(player_display_name) AS key,
                     AVG(3*(fg_made_0_19+fg_made_20_29+fg_made_30_39)
                         + 4*fg_made_40_49
                         + 5*(fg_made_50_59+fg_made_60_)
                         + pat_made) AS trailing_pts,
                     COUNT(*) AS games
              FROM `{settings.raw}.weekly_stats`
              WHERE position = 'K' AND season = @season AND week < @week
              GROUP BY key
            ),
            def_game AS (
              SELECT p.game_id, p.defteam AS team, ANY_VALUE(p.week) AS week,
                     SUM(CAST(p.sack AS INT64)) AS sacks,
                     SUM(CAST(p.interception AS INT64))
                       + SUM(IF(p.fumble_lost = 1, 1, 0)) AS takeaways,
                     SUM(IF(p.touchdown = 1 AND p.td_team = p.defteam, 1, 0)) AS tds
              FROM `{settings.raw}.pbp` p
              WHERE p.season = @season AND p.week < @week AND p.defteam IS NOT NULL
              GROUP BY p.game_id, p.defteam
            ),
            pts AS (
              SELECT game_id, home_team AS team, away_score AS pa
              FROM `{settings.raw}.schedules` WHERE season = @season
              UNION ALL
              SELECT game_id, away_team, home_score
              FROM `{settings.raw}.schedules` WHERE season = @season
            ),
            d AS (
              SELECT 'DST' AS kind, dg.team AS key,
                     AVG(dg.sacks + 2*dg.takeaways + 6*dg.tds +
                         CASE WHEN p.pa = 0 THEN 10 WHEN p.pa <= 6 THEN 7
                              WHEN p.pa <= 13 THEN 4 WHEN p.pa <= 20 THEN 1
                              WHEN p.pa <= 27 THEN 0 WHEN p.pa <= 34 THEN -1
                              ELSE -4 END) AS trailing_pts,
                     COUNT(*) AS games
              FROM def_game dg JOIN pts p USING (game_id, team)
              GROUP BY key
            )
            SELECT kind, key, trailing_pts FROM k WHERE games >= 2
            UNION ALL
            SELECT kind, key, trailing_pts FROM d WHERE games >= 2
            """,
            params={"season": season, "week": week},
        )

    def showdown_salaries(self) -> pd.DataFrame:
        """Latest pull per upcoming showdown draft group (one game each).
        Salaries are FLEX-slot; the optimizer derives the 1.5x CPT cost."""
        from ..bq import query_df

        return query_df(
            f"""
            WITH pulls AS (
              SELECT draft_group_id, MAX(pulled_at) AS ts
              FROM `{settings.raw}.dk_salaries`
              WHERE slate_type = 'showdown'
                AND game_start >= CURRENT_TIMESTAMP()
              GROUP BY draft_group_id
            )
            SELECT s.draft_group_id, s.dk_player_id, s.dk_draftable_id,
                   s.dk_cpt_draftable_id, s.display_name,
                   s.team_abbr, s.position, s.salary, s.game_start,
                   s.status, s.dk_ppg
            FROM `{settings.raw}.dk_salaries` s
            JOIN pulls p
              ON s.draft_group_id = p.draft_group_id AND s.pulled_at = p.ts
            WHERE s.slate_type = 'showdown'
            ORDER BY s.game_start, s.salary DESC
            """
        )

    def classic_slates(self) -> pd.DataFrame:
        """One row per (upcoming classic draft group, kickoff time): team and
        player counts from the latest pull per group. A group stays listed
        until its last game kicks off, so late swap keeps working after the
        early games lock."""
        from ..bq import query_df

        return query_df(
            f"""
            WITH pulls AS (
              SELECT draft_group_id, MAX(pulled_at) AS ts
              FROM `{settings.raw}.dk_salaries`
              WHERE slate_type = 'classic'
              GROUP BY draft_group_id
              HAVING MAX(game_start) >= CURRENT_TIMESTAMP()
            )
            SELECT s.draft_group_id, s.game_start,
                   COUNT(DISTINCT s.team_abbr) AS teams,
                   COUNT(DISTINCT s.dk_player_id) AS players
            FROM `{settings.raw}.dk_salaries` s
            JOIN pulls p
              ON s.draft_group_id = p.draft_group_id AND s.pulled_at = p.ts
            WHERE s.slate_type = 'classic'
            GROUP BY 1, 2
            ORDER BY s.draft_group_id, s.game_start
            """
        )

    def classic_salaries(self, draft_group_id: int) -> pd.DataFrame:
        """Latest pull for one classic draft group: the slate's player pool
        with its own salaries and draftable IDs (both are slate-specific)."""
        from ..bq import query_df

        return query_df(
            f"""
            WITH pull AS (
              SELECT MAX(pulled_at) AS ts
              FROM `{settings.raw}.dk_salaries`
              WHERE slate_type = 'classic' AND draft_group_id = @gid
            )
            SELECT DISTINCT s.draft_group_id, s.dk_player_id,
                   s.dk_draftable_id, s.display_name, s.team_abbr,
                   s.position, s.salary, s.game_start, s.status
            FROM `{settings.raw}.dk_salaries` s, pull
            WHERE s.pulled_at = pull.ts AND s.slate_type = 'classic'
              AND s.draft_group_id = @gid
            """,
            params={"gid": int(draft_group_id)},
        )

    def classic_draftable_ids(self) -> pd.DataFrame:
        """dk_player_id -> draftable ID from the latest classic pull. The
        upload CSV needs draftable IDs (the DKSalaries 'ID' column), which
        change every slate — so this is always the freshest snapshot."""
        from ..bq import query_df

        return query_df(
            f"""
            WITH latest_pull AS (
              SELECT MAX(pulled_at) AS ts FROM `{settings.raw}.dk_salaries`
              WHERE slate_type = 'classic'
            )
            SELECT DISTINCT s.dk_player_id, s.dk_draftable_id
            FROM `{settings.raw}.dk_salaries` s, latest_pull
            WHERE s.pulled_at = latest_pull.ts AND s.slate_type = 'classic'
              AND s.dk_draftable_id IS NOT NULL
            """
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

    def __init__(self, frame: pd.DataFrame, defense: pd.DataFrame | None = None,
                 showdown: pd.DataFrame | None = None,
                 draftables: pd.DataFrame | None = None,
                 classic: pd.DataFrame | None = None):
        self.frame = frame
        self.defense = defense if defense is not None else pd.DataFrame(
            columns=["team", "season", "week", "position", "fp_allowed",
                     "fp_allowed_l3", "fp_allowed_l6", "fp_allowed_season", "trend"]
        )
        self.showdown = showdown if showdown is not None else pd.DataFrame(
            columns=SHOWDOWN_COLUMNS
        )
        self.draftables = draftables if draftables is not None else pd.DataFrame(
            columns=["dk_player_id", "dk_draftable_id"]
        )
        self.classic = classic if classic is not None else pd.DataFrame(
            columns=CLASSIC_COLUMNS
        )

    def showdown_salaries(self) -> pd.DataFrame:
        return self.showdown

    def classic_slates(self) -> pd.DataFrame:
        if self.classic.empty:
            return pd.DataFrame(
                columns=["draft_group_id", "game_start", "teams", "players"]
            )
        return (
            self.classic.groupby(["draft_group_id", "game_start"])
            .agg(teams=("team_abbr", "nunique"),
                 players=("dk_player_id", "nunique"))
            .reset_index()
        )

    def classic_salaries(self, draft_group_id: int) -> pd.DataFrame:
        c = self.classic
        return c[c.draft_group_id == draft_group_id].reset_index(drop=True)

    def classic_draftable_ids(self) -> pd.DataFrame:
        return self.draftables

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
