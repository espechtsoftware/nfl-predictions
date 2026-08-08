"""System status: per-feed freshness from BigQuery table metadata.

Born from the odds_snapshots incident (see the README deficiency log,
2026-07-31): the hourly odds job failed on every run for weeks and nothing
noticed, because no downstream reader existed and job failures alert no
one. Two consumers share this module:

- ``nfl-dfs check-freshness`` (Cloud Run job, daily): raises if any
  alerting feed is stale, which fails the job and trips the Cloud
  Monitoring failed-execution alert -> email.
- ``GET /api/system-status`` (web app): the System status popup.

Freshness reads ``bigquery.get_table`` metadata (last modified + row
count) — no query cost, one metadata call per feed. Season-awareness is
date-based: NFL feeds idle outside September–January, CFB outside
mid-August–January; feeds marked "always" (nflverse refresh, feature
builds) must stay fresh year-round because their jobs run year-round.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from .config import settings


@dataclass(frozen=True)
class Feed:
    key: str
    label: str
    dataset: str          # settings attr: 'raw' | 'features' | 'predictions'
    table: str
    max_age_h: float      # freshness bar while the feed is active
    season: str = "always"  # 'always' | 'nfl' | 'cfb'
    alert: bool = True    # False: show in the popup, never fail check-freshness
    note: str = ""


# Thresholds follow the LIVE scheduler cadences (verified 2026-07-31), not
# README §11's aspirational ones: s-nflverse/s-features/s-train/s-project-tu
# all run weekly on Tuesdays, so their bar is 8 days (one missed Tuesday ->
# stale). s-odds runs 9:00/15:00 CT Wed-Sun (worst gap ~66h -> 78h bar).
#
# The Tuesday chain feeds are 'nfl'-seasonal, not 'always': their schedulers
# are PAUSED in the off-season (2026-07-31 — re-ingesting a finished season
# weekly is pure waste). Resume before week 1 (see the week-1 checklist);
# if forgotten, these feeds go active Sep 1 and check-freshness emails.
FEEDS: tuple[Feed, ...] = (
    Feed("pbp", "Play-by-play (nflverse)", "raw", "pbp", 8 * 24, "nfl"),
    Feed("weekly_stats", "Weekly stats (nflverse)", "raw", "weekly_stats",
         8 * 24, "nfl"),
    Feed("schedules", "Schedules + closing lines", "raw", "schedules",
         8 * 24, "nfl"),
    Feed("dk_salaries", "DK slates/salaries", "raw", "dk_salaries", 36, "nfl"),
    Feed("odds_snapshots", "Game lines (The Odds API)", "raw", "odds_snapshots",
         78),
    Feed("prop_lines", "Player props (The Odds API)", "raw", "prop_lines",
         8 * 24, "nfl"),
    # Adopted-model dependencies (2026-08-04): the sim's default
    # marginals and the component cache — stale means a logged fallback
    # to weaker distributions, which must page, not hide.
    Feed("tabpfn_projections", "TabPFN marginal cache (GPU job)",
         "features", "tabpfn_projections", 9 * 24, "nfl"),
    Feed("tabpfn_components", "TabPFN component cache (GPU job)",
         "features", "tabpfn_components", 9 * 24, "nfl"),
    Feed("weather", "Weather (Open-Meteo)", "raw", "weather", 72, "nfl"),
    Feed("player_week_training", "Feature build (training)", "features",
         "player_week_training", 8 * 24, "nfl"),
    # 'nfl', not 'always': inference rows are synthetic upcoming-week rows,
    # which need next-season rosters -- legitimately empty in the off-season
    # even though the build that produces them runs year-round.
    Feed("player_week_inference", "Feature build (inference)", "features",
         "player_week_inference", 8 * 24, "nfl"),
    Feed("player_projections", "Projections", "predictions",
         "player_projections", 8 * 24, "nfl"),
    Feed("cfb_dk_salaries", "CFB slates/salaries", "raw", "cfb_dk_salaries",
         36, "cfb", note="collection-only scaffold; empty until DK posts CFB slates"),
    Feed("dk_contest_fills", "Contest fills (overlay scaffold)", "raw",
         "dk_contest_fills", 48, "nfl", alert=False,
         note="opt-in scaffold, not scheduled — informational only"),
)


def _active(season: str, today: date) -> bool:
    if season == "always":
        return True
    if season == "nfl":
        return today.month in (9, 10, 11, 12, 1)
    if season == "cfb":
        return (today.month == 8 and today.day >= 15) or today.month in (9, 10, 11, 12, 1)
    raise ValueError(season)


def _table_info(dataset: str, table: str) -> tuple[datetime, int] | None:
    """(last modified UTC, row count), or None if the table doesn't exist.
    Seam for tests — the only line that touches GCP."""
    from google.api_core.exceptions import NotFound

    from .bq import client

    try:
        t = client().get_table(f"{getattr(settings, dataset)}.{table}")
    except NotFound:
        return None
    return t.modified, t.num_rows or 0


def system_status(now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    out = []
    for feed in FEEDS:
        active = _active(feed.season, now.date())
        info = _table_info(feed.dataset, feed.table)
        if info is None:
            state, modified, rows, age_h = "missing", None, 0, None
        else:
            modified, rows = info
            age_h = (now - modified).total_seconds() / 3600
            if rows == 0:
                state = "empty" if active else "idle"
            elif age_h <= feed.max_age_h:
                state = "ok"
            else:
                state = "stale" if active else "idle"
        out.append({
            "key": feed.key,
            "label": feed.label,
            "table": f"{feed.dataset}.{feed.table}",
            "state": state,
            "active": active,
            "alerting": feed.alert,
            "last_modified": modified.isoformat() if modified else None,
            "age_hours": round(age_h, 1) if age_h is not None else None,
            "rows": rows,
            "max_age_hours": feed.max_age_h,
            "note": feed.note,
        })
    return out


def check_freshness(now: datetime | None = None) -> None:
    """Raise RuntimeError if any alerting feed is stale/empty/missing while
    active. Run as a scheduled job: a raise fails the Cloud Run execution,
    which trips the failed-execution Cloud Monitoring alert."""
    bad = [
        f"{c['label']} ({c['table']}): {c['state']}"
        + (f", last modified {c['age_hours']}h ago (max {c['max_age_hours']}h)"
           if c["age_hours"] is not None else "")
        for c in system_status(now)
        if c["alerting"] and c["active"] and c["state"] in ("stale", "empty", "missing")
    ]
    # Effective-config health: the config manifest proves CODE defaults;
    # it cannot see a deployment override. Surface the resolved generation
    # budget and fail when a research arm departs from the adopted baseline.
    try:
        from .backtest.engine import effective_generation_config

        cfg = effective_generation_config()
        state = ("adopted" if cfg["matches_adopted_default"]
                 else "OVERRIDDEN")
        print(f"generation config: {state} "
              f"(CE {cfg['n_ce']} / EPI {cfg['n_epistemic']} / "
              f"Gumbel {cfg['n_gumbel']} / boom {cfg['n_boom']}, "
              f"total {cfg['total']})"
              + (f" overrides={cfg['overrides']}" if cfg["overrides"] else ""))
        if not cfg["matches_adopted_default"]:
            bad.append(
                "generation config departs from the adopted 0/40 baseline: "
                f"CE {cfg['n_ce']} / EPI {cfg['n_epistemic']} / "
                f"Gumbel {cfg['n_gumbel']} / boom {cfg['n_boom']} "
                f"overrides={cfg['overrides']}")
    except Exception:
        log.exception("effective-config health check failed")

    if bad:
        raise RuntimeError("Stale feeds:\n" + "\n".join(bad))
    print("All feeds fresh")
