"""Prospective K=1 Sunday-main lineup shadow.

The historical K=1 result is outcome-viewed, so the next honest evidence is
an immutable portfolio created before each 2026 slate.  This job deliberately
does not publish projections or alter the app: it loads the isolated K=1
registry, builds the frozen 80-entry/194-tail book, and synchronously stores
the complete candidate pool and support artifacts for later grading.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone

import pandas as pd

from ..config import current_season, settings
from ..models.components import effective_ensemble_size
from ..models.train_job import CANONICAL_VARIANT, registry_variant
from ..optimizer.lineup import StackRules

log = logging.getLogger(__name__)

K1_VARIANT = "tail_k1"
SHADOW_ENTRIES = 80
SHADOW_TAIL_LINE = 194.0


def upcoming_season_week() -> tuple[int, int, date]:
    """Current season, next regular week, and that week's Sunday date."""
    from ..bq import query_df

    season = current_season()
    frame = query_df(
        f"""SELECT week, gameday FROM `{settings.raw}.schedules`
            WHERE season = @season
              AND game_type = 'REG'
              AND gameday >= CAST(CURRENT_DATE() AS STRING)
            ORDER BY week, gameday""",
        params={"season": season},
    )
    if frame.empty or pd.isna(frame.week.iloc[0]):
        raise RuntimeError(f"no upcoming regular-season week for {season}")
    week = int(frame.week.min())
    dates = pd.to_datetime(
        frame.loc[frame.week == week, "gameday"], errors="coerce")
    sundays = dates[dates.dt.dayofweek == 6]
    if sundays.empty:
        raise RuntimeError(
            f"regular-season {season} week {week} has no Sunday games")
    return season, week, sundays.min().date()


def sunday_main_group(slates: pd.DataFrame, target_sunday: date) -> int:
    """Largest all-Sunday group on the target regular-season Sunday."""
    required = {"draft_group_id", "game_start", "teams", "players"}
    missing = required - set(slates.columns)
    if missing:
        raise ValueError(f"classic slate rows missing {sorted(missing)}")
    choices: list[tuple[int, int, int]] = []
    for gid, grp in slates.groupby("draft_group_id", sort=False):
        starts = pd.to_datetime(grp.game_start, utc=True)
        eastern = starts.dt.tz_convert("America/New_York")
        days = set(eastern.dt.day_name())
        if days != {"Sunday"}:
            continue
        slate_dates = set(eastern.dt.date)
        if slate_dates != {target_sunday}:
            continue
        games = int(pd.to_numeric(grp.teams, errors="coerce").fillna(0).sum()) // 2
        players = int(pd.to_numeric(
            grp.players, errors="coerce").fillna(0).sum())
        choices.append((games, players, int(gid)))
    if not choices:
        raise RuntimeError(
            f"no all-Sunday classic draft group is available for "
            f"{target_sunday}")
    return max(choices)[2]


def run(*, store=None, generated_at: datetime | None = None) -> dict:
    """Freeze one prospective K=1 candidate book and return its identity."""
    variant = registry_variant()
    if variant == CANONICAL_VARIANT:
        raise RuntimeError(
            "tail shadow refuses the canonical registry; set "
            f"MODEL_REGISTRY_VARIANT={K1_VARIANT}")
    if variant != K1_VARIANT:
        raise RuntimeError(
            f"tail shadow requires MODEL_REGISTRY_VARIANT={K1_VARIANT}, "
            f"got {variant}")
    size = effective_ensemble_size()
    if size != 1:
        raise RuntimeError(
            f"tail shadow requires MODEL_ENSEMBLE=1, got {size}")
    if not os.environ.get("CAND_ARTIFACT_BUCKET", "").strip():
        raise RuntimeError(
            "tail shadow requires CAND_ARTIFACT_BUCKET so the full "
            "candidate-by-world matrix is frozen")

    if store is None:
        from ..app.store import BigQueryStore

        store = BigQueryStore()
    season, week, target_sunday = upcoming_season_week()
    gid = sunday_main_group(store.classic_slates(), target_sunday)
    salary_frame = store.classic_salaries(gid)
    if salary_frame.empty:
        raise RuntimeError(f"Sunday-main draft group {gid} has no salaries")
    salary_frame = salary_frame.drop_duplicates("dk_player_id")
    allowed = {int(v) for v in salary_frame.dk_player_id.dropna()}
    salaries = {
        int(r.dk_player_id): int(r.salary)
        for r in salary_frame[["dk_player_id", "salary"]].dropna().itertuples()
    }

    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(timezone.utc)
    panel_run_id = (
        f"live-shadow-{K1_VARIANT}-{season}w{week:02d}-"
        f"{stamp.strftime('%Y%m%dT%H%M%SZ')}")

    from .live_lineups import build_sim_lineups

    lineups = build_sim_lineups(
        season, week, n_entries=SHADOW_ENTRIES,
        stack=StackRules(qb_stack_min=2, bring_back_min=1,
                         forbid_rb_vs_dst=True),
        tail_line=SHADOW_TAIL_LINE, seed=42, lev_scale=1.0,
        allowed_ids=allowed, salary_overrides=salaries,
        apply_notes=False, model_variant=variant,
        cand_log_table=f"{settings.predictions}.live_candidates_shadow",
        cand_log_async=False, cand_log_required=True,
        panel_run_id=panel_run_id,
        candidate_run_type="live_shadow",
    )
    if len(lineups) != SHADOW_ENTRIES:
        raise RuntimeError(
            f"K=1 shadow built {len(lineups)} lineups, expected "
            f"{SHADOW_ENTRIES}")
    log.info("froze K=1 shadow %s: draft_group=%s lineups=%d tail=%.1f",
             panel_run_id, gid, len(lineups), SHADOW_TAIL_LINE)
    return {
        "panel_run_id": panel_run_id,
        "season": season,
        "week": week,
        "draft_group_id": gid,
        "entries": len(lineups),
        "tail_line": SHADOW_TAIL_LINE,
        "model_variant": variant,
    }
