"""Weekly/hourly inference: project the upcoming slate and write
nfl_predictions.player_projections.

Schedule: Tuesday after retrain, then hourly Sat-Sun for late swap — the
player pool changes as inactives are announced, and stale projections on
Sunday morning are how you enter lineups you didn't mean to enter.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..bq import load_dataframe, query_df
from ..config import current_season, settings
from ..models import calibration, coldstart, components, simulate
from ..models.blend import (BLEND_W as BLEND_WEIGHT, blend,
                            effective_model_weight, market_projection_frame)
from . import cascade_adjust

log = logging.getLogger(__name__)


def _props_first_market_with_dk_fallback(
    dk_ppg_market: pd.Series | np.ndarray,
    prop_market: pd.Series | np.ndarray,
    *,
    minimum_prop_coverage: float = 0.30,
) -> tuple[np.ndarray, np.ndarray]:
    """Prefer available props without discarding per-player DK fallbacks.

    The prop snapshot is used only when it covers the configured share of the
    slate.  Once that slate-level gate passes, rows without a prop retain the
    aligned DK-PPG value.  Below the gate the complete DK-PPG vector is kept.
    The returned mask identifies only rows truly sourced from props so audit
    logging cannot mislabel fallback rows as prop observations.
    """
    fallback = np.asarray(dk_ppg_market, dtype=float)
    props = np.asarray(prop_market, dtype=float)
    if fallback.ndim != 1 or props.shape != fallback.shape:
        raise ValueError("prop and DK-PPG market vectors must be aligned")
    if not 0.0 <= minimum_prop_coverage <= 1.0:
        raise ValueError("minimum prop coverage must be between 0 and 1")

    prop_mask = np.isfinite(props)
    if (
        len(fallback) == 0
        or int(prop_mask.sum()) < minimum_prop_coverage * len(fallback)
    ):
        return fallback.copy(), np.zeros(len(fallback), dtype=bool)

    market = fallback.copy()
    market[prop_mask] = props[prop_mask]
    return market, prop_mask

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
        WITH current_roster_receipt AS (
          SELECT MAX(nflverse_pulled_at) AS pulled_at
          FROM `{settings.raw}.rosters_weekly`
          WHERE CAST(season AS INT64) = @season
            AND CAST(week AS INT64) = @week
        ),
        current_roster_receipt_quality AS (
          SELECT
            COUNT(DISTINCT r.team) = 32
            AND COUNT(DISTINCT r.gsis_id) >= 1000
            AND MAX(r.nflverse_pulled_at) >=
                TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 72 HOUR)
              AS receipt_is_valid
          FROM `{settings.raw}.rosters_weekly` r
          JOIN current_roster_receipt x
            ON r.nflverse_pulled_at = x.pulled_at
          WHERE CAST(r.season AS INT64) = @season
            AND CAST(r.week AS INT64) = @week
        ),
        current_active_fantasy_roster AS (
          SELECT DISTINCT
            r.gsis_id,
            REGEXP_REPLACE(
              REGEXP_REPLACE(
                REGEXP_REPLACE(UPPER(TRIM(roster_name)),
                               r"\\s+(JR|SR|II|III|IV|V)\\.?$", ""),
                r"[^A-Z ]", ""),
              r" +", " ") AS clean_name,
            CASE UPPER(TRIM(r.team))
              WHEN 'ARZ' THEN 'ARI' WHEN 'BLT' THEN 'BAL'
              WHEN 'CLV' THEN 'CLE' WHEN 'HST' THEN 'HOU'
              WHEN 'GBP' THEN 'GB' WHEN 'GNB' THEN 'GB'
              WHEN 'JAC' THEN 'JAX'
              WHEN 'KCC' THEN 'KC' WHEN 'KAN' THEN 'KC'
              WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
              WHEN 'LAR' THEN 'LA' WHEN 'RAM' THEN 'LA'
              WHEN 'STL' THEN 'LA'
              WHEN 'NEP' THEN 'NE' WHEN 'NWE' THEN 'NE'
              WHEN 'NOS' THEN 'NO' WHEN 'NOR' THEN 'NO'
              WHEN 'SDC' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
              WHEN 'SD' THEN 'LAC' WHEN 'SFO' THEN 'SF'
              WHEN 'TBB' THEN 'TB' WHEN 'TAM' THEN 'TB'
              WHEN 'WSH' THEN 'WAS'
              ELSE UPPER(TRIM(r.team))
            END AS team_abbr,
            UPPER(TRIM(r.position)) AS roster_position
          FROM `{settings.raw}.rosters_weekly` r
          JOIN current_roster_receipt x
            ON r.nflverse_pulled_at = x.pulled_at,
               UNNEST([r.full_name,
                       CONCAT(r.football_name, ' ', r.last_name)])
                 AS roster_name
          WHERE CAST(r.season AS INT64) = @season
            AND CAST(r.week AS INT64) = @week
            AND r.status = 'ACT'
            AND UPPER(TRIM(r.position)) IN ('QB', 'RB', 'WR', 'TE', 'FB')
            AND roster_name IS NOT NULL
        ),
        unique_current_active_identity AS (
          SELECT clean_name, team_abbr, roster_position
          FROM current_active_fantasy_roster
          GROUP BY clean_name, team_abbr, roster_position
          HAVING COUNT(DISTINCT gsis_id) = 1
        ),
        target_gamedays AS (
          SELECT DISTINCT PARSE_DATE('%Y-%m-%d', gameday) AS gameday
          FROM `{settings.raw}.schedules`
          WHERE season = @season
            AND week = @week
            AND game_type = 'REG'
        ),
        eligible_salaries AS (
          SELECT s.*
          FROM `{settings.raw}.dk_salaries` s
          JOIN target_gamedays g
            ON DATE(s.game_start, 'America/New_York') = g.gameday
          WHERE s.slate_type = 'classic'
            AND CAST(s.season AS INT64) = @season
        ),
        pulls AS (
          SELECT draft_group_id, MAX(pulled_at) AS ts
          FROM eligible_salaries
          GROUP BY draft_group_id
          HAVING MAX(game_start) >= CURRENT_TIMESTAMP()
        ),
        latest AS (
          SELECT DISTINCT s.dk_player_id, s.display_name, s.salary,
                 s.position AS dk_position, s.team_abbr, s.status, s.dk_ppg,
                 s.draft_group_id, CAST(s.season AS INT64) AS season
          FROM eligible_salaries s
          JOIN pulls p
            ON s.draft_group_id = p.draft_group_id AND s.pulled_at = p.ts
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
        ),
        classified_slate AS (
          SELECT
            sl.*,
            q.receipt_is_valid AS roster_receipt_is_valid,
            m.gsis_id,
            a.gsis_id AS active_gsis_id,
            n.clean_name AS active_exact_name
          FROM slate sl
          CROSS JOIN current_roster_receipt_quality q
          LEFT JOIN `{settings.features}.player_id_map` m
            USING (dk_player_id)
          LEFT JOIN (
            SELECT DISTINCT gsis_id, team_abbr
            FROM current_active_fantasy_roster
          ) a
            ON a.gsis_id = m.gsis_id
           AND a.team_abbr = CASE UPPER(TRIM(sl.team_abbr))
             WHEN 'ARZ' THEN 'ARI' WHEN 'BLT' THEN 'BAL'
             WHEN 'CLV' THEN 'CLE' WHEN 'HST' THEN 'HOU'
             WHEN 'GBP' THEN 'GB' WHEN 'GNB' THEN 'GB'
             WHEN 'JAC' THEN 'JAX'
             WHEN 'KCC' THEN 'KC' WHEN 'KAN' THEN 'KC'
             WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
             WHEN 'LAR' THEN 'LA' WHEN 'RAM' THEN 'LA'
             WHEN 'STL' THEN 'LA'
             WHEN 'NEP' THEN 'NE' WHEN 'NWE' THEN 'NE'
             WHEN 'NOS' THEN 'NO' WHEN 'NOR' THEN 'NO'
             WHEN 'SDC' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
             WHEN 'SD' THEN 'LAC' WHEN 'SFO' THEN 'SF'
             WHEN 'TBB' THEN 'TB' WHEN 'TAM' THEN 'TB'
             WHEN 'WSH' THEN 'WAS'
             ELSE UPPER(TRIM(sl.team_abbr))
           END
          LEFT JOIN unique_current_active_identity n
            ON n.clean_name = REGEXP_REPLACE(
                 REGEXP_REPLACE(
                   REGEXP_REPLACE(UPPER(TRIM(sl.display_name)),
                                  r"\\s+(JR|SR|II|III|IV|V)\\.?$", ""),
                   r"[^A-Z ]", ""),
                 r" +", " ")
           AND n.team_abbr = CASE UPPER(TRIM(sl.team_abbr))
             WHEN 'ARZ' THEN 'ARI' WHEN 'BLT' THEN 'BAL'
             WHEN 'CLV' THEN 'CLE' WHEN 'HST' THEN 'HOU'
             WHEN 'GBP' THEN 'GB' WHEN 'GNB' THEN 'GB'
             WHEN 'JAC' THEN 'JAX'
             WHEN 'KCC' THEN 'KC' WHEN 'KAN' THEN 'KC'
             WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
             WHEN 'LAR' THEN 'LA' WHEN 'RAM' THEN 'LA'
             WHEN 'STL' THEN 'LA'
             WHEN 'NEP' THEN 'NE' WHEN 'NWE' THEN 'NE'
             WHEN 'NOS' THEN 'NO' WHEN 'NOR' THEN 'NO'
             WHEN 'SDC' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
             WHEN 'SD' THEN 'LAC' WHEN 'SFO' THEN 'SF'
             WHEN 'TBB' THEN 'TB' WHEN 'TAM' THEN 'TB'
             WHEN 'WSH' THEN 'WAS'
             ELSE UPPER(TRIM(sl.team_abbr))
           END
           AND n.roster_position = UPPER(TRIM(sl.dk_position))
        )
        SELECT sl.* EXCEPT (
          active_gsis_id, active_exact_name, season
        ), t.*
        FROM classified_slate sl
        LEFT JOIN `{settings.features}.player_week_inference` t
          ON t.gsis_id = sl.gsis_id
         AND t.season = @season
         AND t.week = @week
        WHERE sl.dk_position = 'DST'
           OR NOT sl.roster_receipt_is_valid
           OR sl.active_gsis_id IS NOT NULL
           OR sl.active_exact_name IS NOT NULL
        """,
        {"season": season, "week": week},
    )
    if df.empty:
        raise RuntimeError(
            "no upcoming classic slates in dk_salaries — run ingest-dk "
            "(or DK hasn't posted next week's draft groups yet)"
        )
    if (
        "roster_receipt_is_valid" not in df
        or not df["roster_receipt_is_valid"].fillna(False).all()
    ):
        raise RuntimeError(
            "target-week roster eligibility receipt is stale or incomplete; "
            "refusing to project a partially classified DK pool"
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
    policy_env: dict[str, str] | None = None,
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
                        game_ids=feats.get("game_id"),
                        team_ids=feats.get("team"),
                        game_totals=feats.get("game_total"),
                        env=policy_env)
    preds = calibration.apply_widen(
        sim.summary, feats.get("position", feats.get("dk_position"))
    )
    preds = coldstart.widen_cold_start_quantiles(
        preds, feats.get("is_cold_start", pd.Series(False, index=feats.index))
    )

    # Live blend parity fix (review #5 round 3): the REPLAY blend —
    # where BLEND_W=0.45 was validated — uses de-vigged PROP-market
    # points; the live path was blending DK's historical PPG
    # (market_projection_frame's documented stand-in). Prefer the real
    # prop feed, fall back to DK PPG when props are absent.
    market = np.asarray(market_projection_frame(feats), dtype=float)
    _mkt_src = "dk_ppg"
    _prop_market_mask = np.zeros(len(feats), dtype=bool)
    try:
        from ..models.prop_market import market_points as _prop_points
        _pm = _prop_points((season,))
        _pm = _pm[_pm.week == week]
        if len(_pm):
            _m = feats[["gsis_id"]].merge(
                _pm[["gsis_id", "market_points"]], on="gsis_id",
                how="left").market_points
            market, _prop_market_mask = (
                _props_first_market_with_dk_fallback(market, _m)
            )
            if _prop_market_mask.any():
                _mkt_src = "props"
            else:
                log.info(
                    "prop-market coverage below 30 percent (%d/%d); "
                    "using full DK-PPG fallback",
                    int(_m.notna().sum()), len(feats),
                )
    except Exception:
        log.exception("prop market unavailable; blending DK PPG stand-in")
    log.info("market blend source: %s (%d/%d rows)",
             _mkt_src, int(pd.notna(market).sum()), len(feats))
    _pre_blend = preds["proj_points"].to_numpy().copy()
    preds["proj_points"] = blend(
        _pre_blend, np.asarray(market, dtype=float),
        effective_model_weight(policy_env)
    )
    # DIV_TILT shadow log (2026-08-05, Addendum 82; source fixed round
    # 3): logs the PROP-market divergence only — rows are written only
    # when the market source is the real prop feed, so the grader
    # never mistakes DK-PPG disagreement for prop-market disagreement.
    try:
        if _mkt_src == "props":
            _mkt = np.asarray(market, dtype=float)
            _has = _prop_market_mask
            shadow = pd.DataFrame({
                "generated_at": datetime.now(timezone.utc),
                "season": season, "week": week,
                "gsis_id": feats.get("gsis_id"),
                "display_name": feats.get("display_name"),
                "position": feats.get("position", feats.get("dk_position")),
                "salary": feats.get("salary"),
                "our_points": _pre_blend,
                "market_points": _mkt,
                "blend_points": preds["proj_points"],
            })[_has]
            shadow["consensus_div"] = shadow.our_points - shadow.market_points
            load_dataframe(shadow, f"{settings.predictions}.div_shadow",
                           write_disposition="WRITE_APPEND")
            log.info("div-shadow: %d rows logged (median |div| %.2f)",
                     len(shadow), float(shadow.consensus_div.abs().median()))
        else:
            log.info("div-shadow: skipped (no prop feed this run)")
    except Exception:
        log.exception("div-shadow logging failed; projections unaffected")

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
    from ..models.train_job import (load_latest_component_models,
                                    registered_ensemble_size)
    from .production_policy import ADOPTED_CLASSIC_POLICY

    season = current_season()
    week = query_df(
        f"""SELECT MIN(week) AS week FROM `{settings.raw}.schedules`
            WHERE season = @season
              AND game_type = 'REG'
              AND gameday >= CAST(CURRENT_DATE() AS STRING)""",
        {"season": season},
    ).week.iloc[0]
    week = int(week)

    policy = ADOPTED_CLASSIC_POLICY
    policy_env = policy.engine_environment(os.environ)
    model, version = load_latest_component_models(policy.model_variant)
    loaded_k = registered_ensemble_size(model)
    if loaded_k != policy.model_ensemble:
        raise RuntimeError(
            f"production policy {policy.policy_id} requires K="
            f"{policy.model_ensemble}, but {version} contains K={loaded_k}")
    # LIVE_SIMS (adopted 2026-08-03): live paths sim 30k worlds (better
    # medians/ROI, one slate = pennies); panels/replays stay at 10k.
    n_sims = int(policy_env["LIVE_SIMS"])
    feats = upcoming_slate_features(season, week)
    skill = feats[feats.dk_position.isin(["QB", "RB", "WR", "TE"])].reset_index(drop=True)
    out = project(skill, model, version, season, week, n_sims=n_sims,
                  adjust=_cascade_adjuster(season), policy_env=policy_env)
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
    log.info("Wrote %d projections for season %s week %s (policy %s, model %s)",
             len(out), season, week, policy.policy_id, version)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
