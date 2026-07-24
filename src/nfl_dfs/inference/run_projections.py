"""Weekly/hourly inference: project the upcoming slate and write
nfl_predictions.player_projections.

Schedule: Tuesday after retrain, then hourly Sat-Sun for late swap — the
player pool changes as inactives are announced, and stale projections on
Sunday morning are how you enter lineups you didn't mean to enter.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from ..bq import load_dataframe, query_df
from ..config import current_season, settings
from ..models import coldstart, components, simulate
from ..models.blend import blend, market_projection_frame

log = logging.getLogger(__name__)

BLEND_WEIGHT = 0.45  # refit on validation each retrain; see models/blend.py


def upcoming_slate_features(season: int, week: int) -> pd.DataFrame:
    """Feature rows for the players in the current classic slate, with the
    same point-in-time features the model trained on. Unmatched slate
    players fail loudly — a dropped player is a lineup you can't build."""
    df = query_df(
        f"""
        WITH latest_pull AS (
          SELECT MAX(pulled_at) AS ts FROM `{settings.raw}.dk_salaries`
          WHERE slate_type = 'classic'
        ),
        slate AS (
          SELECT DISTINCT s.dk_player_id, s.display_name, s.salary,
                 s.position AS dk_position, s.team_abbr, s.status, s.dk_ppg,
                 s.draft_group_id
          FROM `{settings.raw}.dk_salaries` s, latest_pull
          WHERE s.pulled_at = latest_pull.ts AND s.slate_type = 'classic'
        )
        SELECT sl.*, m.gsis_id, t.*
        FROM slate sl
        LEFT JOIN `{settings.features}.player_id_map` m USING (dk_player_id)
        LEFT JOIN `{settings.features}.player_week_training` t
          ON t.gsis_id = m.gsis_id AND t.season = {season} AND t.week = {week}
        """
    )
    unmatched = df[df.gsis_id.isna() & (df.dk_position != "DST")]
    if not unmatched.empty:
        raise RuntimeError(
            f"{len(unmatched)} slate players have no GSIS mapping — add them "
            f"to nfl_features.player_id_overrides before projecting:\n"
            + unmatched[["dk_player_id", "display_name", "team_abbr"]]
            .head(20).to_string(index=False)
        )
    return df


def project(
    feats: pd.DataFrame,
    model: components.ComponentModels,
    model_version: str,
    season: int,
    week: int,
    n_sims: int = 10_000,
) -> pd.DataFrame:
    feats = coldstart.fill_cold_start_features(feats)
    comps = model.predict_components(feats)
    sim = simulate.simulate(comps, n_sims=n_sims)
    preds = sim.summary
    preds = coldstart.widen_cold_start_quantiles(
        preds, feats.get("is_cold_start", pd.Series(False, index=feats.index))
    )

    market = market_projection_frame(feats)
    preds["proj_points"] = blend(
        preds["proj_points"].to_numpy(), market.to_numpy(), BLEND_WEIGHT
    )

    out = pd.DataFrame(
        {
            "generated_at": datetime.now(timezone.utc),
            "model_version": model_version,
            "season": season,
            "week": week,
            "slate_id": feats.get("draft_group_id"),
            "gsis_id": feats.get("gsis_id"),
            "dk_player_id": feats.get("dk_player_id"),
            "display_name": feats.get("display_name"),
            "position": feats.get("position", feats.get("dk_position")),
            "team": feats.get("team", feats.get("team_abbr")),
            "opponent": feats.get("opponent"),
            "salary": feats.get("salary"),
            "proj_points": preds["proj_points"],
            "proj_p10": preds["proj_p10"],
            "proj_p50": preds["proj_p50"],
            "proj_p90": preds["proj_p90"],
            "proj_std": preds["proj_std"],
            "p_20_plus": preds["p_20_plus"],
            "value": preds["proj_points"] / (feats["salary"] / 1000.0),
            "proj_ownership": pd.NA,
        }
    )
    return out


def run() -> None:
    from ..models.train_job import load_latest_component_models

    season = current_season()
    week = query_df(
        f"""SELECT MIN(week) AS week FROM `{settings.raw}.schedules`
            WHERE season = {season} AND gameday >= CAST(CURRENT_DATE() AS STRING)"""
    ).week.iloc[0]
    week = int(week)

    model, version = load_latest_component_models()
    feats = upcoming_slate_features(season, week)
    skill = feats[feats.dk_position.isin(["QB", "RB", "WR", "TE"])].reset_index(drop=True)
    out = project(skill, model, version, season, week)
    load_dataframe(out, f"{settings.predictions}.player_projections",
                   write_disposition="WRITE_APPEND", partition_field="generated_at")
    log.info("Wrote %d projections for season %s week %s (model %s)",
             len(out), season, week, version)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
