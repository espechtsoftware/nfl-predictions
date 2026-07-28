"""Production DST projections (issue #7).

proj = trailing 4-game DK average (from features.team_defense_week,
computed off play-by-play, validated 0.98 corr / 0.44 MAE vs exported
actuals) + opposing-QB experience adjustment (qb_experience.py).
Quantiles use fixed empirical offsets — DST scores are one fat-tailed
distribution and a component simulation buys nothing here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from ..config import settings
from .qb_experience import adjustment

log = logging.getLogger(__name__)

FALLBACK_PROJ = 6.0   # league-average DST DK points
# Global residual spread of weekly DST scores around trailing form
STD = 5.4
P10_OFF, P50_OFF, P90_OFF = -4.5, -0.5, 7.0

# Vegas-first model, fit 2026-07-26 on 6,126 DST-weeks (OOS fit<=2020,
# eval 2021+2025: R=0.293 vs 0.124 trailing-only). Opponent implied total
# is ~4x the signal of trailing form; QB experience survives Vegas at
# about half its raw size (the market prices the rest).
COEF_INTERCEPT = 14.33
COEF_OPP_IMPLIED = -0.385
COEF_L16 = 0.118
COEF_ROOKIE = 1.05   # opposing QB <= 3 career starts
COEF_EARLY = 0.91    # 4-10 career starts


def model_projection(opp_implied: pd.Series, trailing: pd.Series,
                     opp_qb_starts: pd.Series) -> pd.Series:
    """Vegas-first DST projection; rows without a line fall back to
    trailing form + the raw QB-experience adjustment."""
    opp_implied = pd.to_numeric(opp_implied, errors="coerce")
    trailing = pd.to_numeric(trailing, errors="coerce").fillna(FALLBACK_PROJ)
    starts = pd.to_numeric(opp_qb_starts, errors="coerce")
    rookie = (starts <= 3).fillna(False).astype(float)
    early = ((starts > 3) & (starts <= 10)).fillna(False).astype(float)
    vegas = (COEF_INTERCEPT + COEF_OPP_IMPLIED * opp_implied
             + COEF_L16 * trailing + COEF_ROOKIE * rookie
             + COEF_EARLY * early)
    fallback = trailing + adjustment(opp_qb_starts)
    return vegas.where(opp_implied.notna(), fallback)


def build_rows(
    slate: pd.DataFrame,      # dk_player_id, display_name, team_abbr, salary, draft_group_id
    trailing: pd.DataFrame,   # team, dst_l4
    opponents: pd.DataFrame,  # team, opponent  (for the target week)
    qb_starts: pd.DataFrame,  # team, career_starts (expected starter, as of now)
    season: int,
    week: int,
    model_version: str,
) -> pd.DataFrame:
    """Pure assembly — every input injectable for offline tests."""
    d = slate.merge(opponents, left_on="team_abbr", right_on="team", how="left")
    d = d.merge(trailing, left_on="team_abbr", right_on="team",
                how="left", suffixes=("", "_t"))
    d = d.merge(qb_starts.rename(columns={"team": "opp_team",
                                          "career_starts": "opp_qb_starts"}),
                left_on="opponent", right_on="opp_team", how="left")
    opp_implied = (d["opp_implied"] if "opp_implied" in d.columns
                   else pd.Series(pd.NA, index=d.index))
    proj = model_projection(opp_implied, d["dst_l4"], d["opp_qb_starts"])
    return pd.DataFrame({
        "generated_at": datetime.now(timezone.utc),
        "model_version": model_version,
        "season": season,
        "week": week,
        "slate_id": d.get("draft_group_id"),
        "gsis_id": None,
        "dk_player_id": d["dk_player_id"],
        "display_name": d["display_name"],
        "position": "DST",
        "team": d["team_abbr"],
        "opponent": d["opponent"],
        "salary": d["salary"],
        "proj_points": proj,
        "proj_p10": proj + P10_OFF,
        "proj_p50": proj + P50_OFF,
        "proj_p90": proj + P90_OFF,
        "proj_std": STD,
        "p_20_plus": 0.03,
        "value": proj / (d["salary"] / 1000.0),
        "proj_ownership": pd.NA,
    })


def project_dst(season: int, week: int, model_version: str) -> pd.DataFrame:
    """Assemble DST projection rows for the upcoming slate from live data."""
    from ..bq import query_df

    # Union of every upcoming classic group (latest pull each), one row per
    # DST, so full-week slates get Thu/Mon defenses too — mirrors
    # run_projections.upcoming_slate_features.
    slate = query_df(
        f"""
        WITH pulls AS (
          SELECT draft_group_id, MAX(pulled_at) AS ts
          FROM `{settings.raw}.dk_salaries`
          WHERE slate_type = 'classic'
          GROUP BY draft_group_id
          HAVING MAX(game_start) >= CURRENT_TIMESTAMP()
        )
        SELECT dk_player_id, display_name, team_abbr, salary, draft_group_id
        FROM (
          SELECT DISTINCT s.dk_player_id, s.display_name, s.team_abbr,
                 s.salary, s.draft_group_id, s.pulled_at
          FROM `{settings.raw}.dk_salaries` s
          JOIN pulls p
            ON s.draft_group_id = p.draft_group_id AND s.pulled_at = p.ts
          WHERE s.slate_type = 'classic' AND s.position = 'DST'
        )
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY dk_player_id
          ORDER BY pulled_at DESC, draft_group_id) = 1
        """
    )
    if slate.empty:
        log.warning("no DST rows in the latest classic pull")
        return slate
    trailing = query_df(
        f"""
        SELECT team, AVG(dst_dk_points) AS dst_l4 FROM (
          SELECT team, dst_dk_points, ROW_NUMBER() OVER (
            PARTITION BY team ORDER BY season DESC, week DESC) AS rn
          FROM `{settings.features}.team_defense_week`
        ) WHERE rn <= 4 GROUP BY team
        """
    )
    opponents = query_df(
        f"""
        SELECT home_team AS team, away_team AS opponent,
               (total_line - spread_line)/2 AS opp_implied
        FROM `{settings.raw}.schedules`
        WHERE season = {season} AND week = {week}
        UNION ALL
        SELECT away_team AS team, home_team AS opponent,
               (total_line + spread_line)/2 AS opp_implied
        FROM `{settings.raw}.schedules`
        WHERE season = {season} AND week = {week}
        """
    )
    # Expected starter = whoever started the opponent's most recent game;
    # their career starts as of now = prior_starts at that game + 1.
    # A late QB change is exactly what manual notes / late swap are for.
    qb = query_df(
        f"""
        WITH starters AS (
          SELECT season, week, team, player_id,
                 ROW_NUMBER() OVER (PARTITION BY season, week, team
                                    ORDER BY attempts DESC) AS rk
          FROM `{settings.raw}.weekly_stats`
          WHERE position = 'QB' AND attempts > 0
        ), s AS (
          SELECT *, COUNT(*) OVER (PARTITION BY player_id
                    ORDER BY season, week ROWS BETWEEN UNBOUNDED PRECEDING
                    AND 1 PRECEDING) AS prior_starts
          FROM starters WHERE rk = 1
        )
        SELECT team, prior_starts + 1 AS career_starts FROM (
          SELECT *, ROW_NUMBER() OVER (PARTITION BY team
                    ORDER BY season DESC, week DESC) AS rn FROM s
        ) WHERE rn = 1
        """
    )
    return build_rows(slate, trailing, opponents, qb, season, week,
                      model_version)
