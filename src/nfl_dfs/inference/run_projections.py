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
from ..models import calibration, coldstart, components, simulate
from ..models.blend import blend, market_projection_frame
from . import cascade_adjust

log = logging.getLogger(__name__)

BLEND_WEIGHT = 0.45  # refit on validation each retrain; see models/blend.py


def upcoming_slate_features(season: int, week: int) -> pd.DataFrame:
    """Feature rows for the players in the current classic slate, with the
    same point-in-time features the model trained on. Unmatched slate
    players fail loudly — a dropped player is a lineup you can't build.

    Features come from player_week_inference (023): as-of-now rollups built
    on the upcoming week's synthetic rows. The training table can't serve
    live slates — its rows require played games and actuals.

    The pool is the UNION of every upcoming classic draft group (latest pull
    per group), deduped per player, so any slate — Sunday main, full
    Thu-Mon, afternoon-only — can be built from these projections. A single
    MAX(pulled_at) would pick just one arbitrary group: each group gets its
    own timestamp within an ingest run."""
    df = query_df(
        f"""
        WITH pulls AS (
          SELECT draft_group_id, MAX(pulled_at) AS ts
          FROM `{settings.raw}.dk_salaries`
          WHERE slate_type = 'classic'
          GROUP BY draft_group_id
          HAVING MAX(game_start) >= CURRENT_TIMESTAMP()
        ),
        latest AS (
          SELECT DISTINCT s.dk_player_id, s.display_name, s.salary,
                 s.position AS dk_position, s.team_abbr, s.status, s.dk_ppg,
                 s.draft_group_id
          FROM `{settings.raw}.dk_salaries` s
          JOIN pulls p
            ON s.draft_group_id = p.draft_group_id AND s.pulled_at = p.ts
          WHERE s.slate_type = 'classic'
        ),
        sizes AS (
          SELECT draft_group_id, COUNT(DISTINCT dk_player_id) AS n_players
          FROM latest GROUP BY draft_group_id
        ),
        slate AS (
          -- One row per player; ties broken toward the biggest group so
          -- slate_id mostly names the fullest slate.
          SELECT * EXCEPT (rn) FROM (
            SELECT l.*, ROW_NUMBER() OVER (
              PARTITION BY l.dk_player_id
              ORDER BY z.n_players DESC, l.draft_group_id) AS rn
            FROM latest l JOIN sizes z USING (draft_group_id)
          ) WHERE rn = 1
        )
        SELECT sl.*, m.gsis_id, t.*
        FROM slate sl
        LEFT JOIN `{settings.features}.player_id_map` m USING (dk_player_id)
        LEFT JOIN `{settings.features}.player_week_inference` t
          ON t.gsis_id = m.gsis_id AND t.season = {season} AND t.week = {week}
        """
    )
    if df.empty:
        raise RuntimeError(
            "no upcoming classic slates in dk_salaries — run ingest-dk "
            "(or DK hasn't posted next week's draft groups yet)"
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
    adjust=None,
) -> pd.DataFrame:
    """adjust: optional callable (feats) -> (feats, out_gsis_ids), applied
    after the cold-start fill so cascade bumps land on top of role priors —
    see inference.cascade_adjust."""
    feats = coldstart.fill_cold_start_features(feats)
    out_ids: list[str] = []
    if adjust is not None:
        feats, out_ids = adjust(feats)
    comps = model.predict_components(feats)
    # Manual usage notes (coach statements etc.): inference-only prior
    # adjustment, decaying to zero by week 6 — see notes.py.
    from .. import notes as manual_notes

    comps = manual_notes.apply_notes(comps, feats, season, week)
    sim = simulate.simulate(comps, n_sims=n_sims,
                        game_ids=feats.get("game_id"))
    preds = calibration.apply_widen(
        sim.summary, feats.get("position", feats.get("dk_position"))
    )
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
    return cascade_adjust.zero_out_projections(out, out_ids)


def _cascade_adjuster(season: int):
    """Build the late-inactive adjuster from warehouse history (current and
    prior season give the with/without splits enough absences to work with).
    Inference must survive this failing — projections without the cascade
    beat no projections on a Sunday morning."""
    try:
        span = f"({season - 1}, {season})"
        usage_rec = query_df(
            f"""SELECT gsis_id, season, week, total_targets, rz20_targets,
                       target_share
                FROM `{settings.features}.rz_receiving` WHERE season IN {span}"""
        )
        usage_rush = query_df(
            f"""SELECT gsis_id, season, week, total_carries, gl3_carries,
                       carry_share
                FROM `{settings.features}.rz_rushing` WHERE season IN {span}"""
        )
        injuries = query_df(
            f"""SELECT gsis_id, season, week, injury_status AS game_status
                FROM `{settings.features}.player_week_injury`
                WHERE season IN {span}"""
        )
    except Exception:
        log.exception("cascade inputs unavailable; projecting without "
                      "late-inactive redistribution")
        return None
    return lambda f: cascade_adjust.adjust_for_inactives(
        f, usage_rec, usage_rush, injuries)


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
    out = project(skill, model, version, season, week,
                  adjust=_cascade_adjuster(season))
    # DST rows (issue #7): trailing team-defense form + opposing-QB
    # experience. Failure-safe — skill projections without DSTs still
    # beat nothing, though lineup building needs the DST rows.
    try:
        from .dst_projections import project_dst

        dst = project_dst(season, week, model_version=version)
        if not dst.empty:
            out = pd.concat([out, dst], ignore_index=True)
    except Exception:
        log.exception("DST projections failed; writing skill rows only")
    load_dataframe(out, f"{settings.predictions}.player_projections",
                   write_disposition="WRITE_APPEND", partition_field="generated_at")
    log.info("Wrote %d projections for season %s week %s (model %s)",
             len(out), season, week, version)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
