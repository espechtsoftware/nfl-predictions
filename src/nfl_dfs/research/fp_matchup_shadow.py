"""Point-in-time shadow join for the staged Fantasy Points live matchups.

Shadow-only by construction: this module reads the three ``nfl_raw`` staging
tables written by ``ingest.fantasy_points_matchups_weekly`` and writes three
``nfl_features.fp_matchup_shadow_*`` tables.  Nothing in ``sql/features/``,
``models/featureset.py`` or the projection path reads them; activation is a
separate reviewed change.

Point-in-time law
-----------------
For a target (season, week) every staged row was captured for that week, so
the only leakage surface is time: a row is admissible only when its capture
time is strictly before the target week's first kickoff.  When several
captures of the same target week exist (Tuesday and Thursday, say) the latest
admissible one per identity wins and its lag to kickoff is recorded.  A row
captured at or after kickoff is never dropped silently; the build fails.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from ..ingest.fantasy_points_matchups_weekly import (
    KEY_COLUMNS,
    REPORTS,
    SEASON,
    TABLES,
    metric_columns,
)
from ..ops.fantasy_points_matchups import advance_ledger


SHADOW_TABLES = {
    "qb-coverage-matchup": "fp_matchup_shadow_qb_coverage_week",
    "wr-coverage-matchup": "fp_matchup_shadow_wr_coverage_week",
    "line-matchups": "fp_matchup_shadow_line_week",
}
IDENTITY_COLUMNS = ("report", "identity", "team", "opponent")
SHADOW_KEY = ("season", "week", "report", "identity", "team", "opponent", "source_sha256")


class MatchupLeakageError(RuntimeError):
    """A staged matchup row would be visible at or after its target kickoff."""


def assert_capture_strict_prior(rows: pd.DataFrame) -> None:
    """Every row's capture time precedes its own target week's first kickoff."""
    needed = {"source_retrieved_at", "first_kickoff_utc", "target_week", "season"}
    if missing := needed - set(rows.columns):
        raise MatchupLeakageError(f"matchup rows missing {sorted(missing)}")
    if rows.empty:
        return
    retrieved = pd.to_datetime(rows.source_retrieved_at, utc=True)
    kickoff = pd.to_datetime(rows.first_kickoff_utc, utc=True)
    if retrieved.isna().any() or kickoff.isna().any():
        raise MatchupLeakageError("matchup rows carry an unreadable capture or kickoff time")
    late = retrieved >= kickoff
    if late.any():
        sample = rows.loc[late, ["report", "identity", "source_retrieved_at", "first_kickoff_utc"]].head(10)
        raise MatchupLeakageError(
            "Fantasy Points matchup rows captured at/after their target kickoff:\n"
            f"{sample.to_string(index=False)}"
        )
    if (rows.source_season.astype(int) > rows.season.astype(int)).any():
        raise MatchupLeakageError("matchup rows carry a source season after the target season")


def select_point_in_time(
    rows: pd.DataFrame,
    *,
    season: int,
    week: int,
    kickoff: pd.Timestamp,
    generated_at: datetime,
) -> pd.DataFrame:
    """Keep the latest capture per identity strictly before ``kickoff``."""
    if rows.empty:
        raise ValueError("no staged matchup rows for the target week")
    if not rows.season.eq(int(season)).all() or not rows.target_week.eq(int(week)).all():
        raise ValueError("staged rows are not all for the requested target week")
    stored_kickoff = pd.to_datetime(rows.first_kickoff_utc, utc=True)
    if not stored_kickoff.eq(pd.Timestamp(kickoff).tz_convert("UTC")).all():
        raise ValueError("staged rows disagree with the target week's first kickoff")
    assert_capture_strict_prior(rows)
    frame = rows.copy()
    frame["source_retrieved_at"] = pd.to_datetime(frame.source_retrieved_at, utc=True)
    keys = list(IDENTITY_COLUMNS)
    frame = frame.sort_values(
        keys + ["source_retrieved_at", "source_sha256"], kind="stable",
    )
    latest = frame.drop_duplicates(keys, keep="last").copy()
    latest["captures_available"] = (
        frame.groupby(keys, sort=False).source_sha256.nunique().reindex(
            pd.MultiIndex.from_frame(latest[keys])
        ).to_numpy()
    )
    latest["week"] = int(week)
    latest["pit_lag_hours"] = (
        (pd.Timestamp(kickoff).tz_convert("UTC") - latest.source_retrieved_at)
        .dt.total_seconds() / 3600.0
    )
    latest["shadow_generated_at"] = generated_at
    return latest.reset_index(drop=True)


def _kickoff(season: int, week: int) -> pd.Timestamp:
    from ..ops.fantasy_points_matchups import _schedule, first_kickoff_utc

    return first_kickoff_utc(_schedule(season, week))


def _staged_rows(table_ref: str, week: int) -> pd.DataFrame:
    from ..bq import query_df

    return query_df(f"""
        SELECT * FROM `{table_ref}`
        WHERE season = @season AND target_week = @week
        """, params={"season": SEASON, "week": int(week)})


def _existing_shadow(table_ref: str, week: int) -> pd.DataFrame:
    from google.api_core.exceptions import NotFound

    from ..bq import query_df

    try:
        return query_df(f"""
            SELECT season, week, report, identity, team, opponent, source_sha256
            FROM `{table_ref}`
            WHERE season = @season AND week = @week
            """, params={"season": SEASON, "week": int(week)})
    except NotFound:
        return pd.DataFrame(columns=list(SHADOW_KEY))


def build(
    *,
    week: int,
    kickoff: pd.Timestamp,
    staged: dict[str, pd.DataFrame],
    generated_at: datetime,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Point-in-time frames per report plus an audit; pure, no warehouse."""
    frames: dict[str, pd.DataFrame] = {}
    audit: dict[str, Any] = {"season": SEASON, "week": int(week), "reports": {}}
    for key in REPORTS:
        rows = staged.get(key)
        if rows is None or rows.empty:
            raise ValueError(f"{key}: nothing staged for Week {week}; stage the capture first")
        selected = select_point_in_time(
            rows, season=SEASON, week=week, kickoff=kickoff, generated_at=generated_at,
        )
        columns = (
            ["season", "week", "report", "identity", "team", "opponent", "gsis_id",
             "resolution_status", "vendor_name", "pos", "games", "source_season",
             "source_regime"]
            + metric_columns(key)
            + ["source_sha256", "source_run_id", "source_retrieved_at",
               "first_kickoff_utc", "pit_lag_hours", "captures_available",
               "archive_uri", "shadow_generated_at"]
        )
        frames[key] = selected[columns].reset_index(drop=True)
        audit["reports"][key] = {
            "staged_rows": int(len(rows)),
            "distinct_captures": int(rows.source_sha256.nunique()),
            "shadow_rows": int(len(selected)),
            "resolved_rows": int(selected.gsis_id.notna().sum()),
            "teams": int(selected.team.nunique()),
            "min_pit_lag_hours": float(selected.pit_lag_hours.min()),
            "max_pit_lag_hours": float(selected.pit_lag_hours.max()),
            "source_sha256": sorted(selected.source_sha256.unique().tolist()),
        }
    return frames, audit


def run(
    *,
    week: int,
    write: bool = False,
    run_dir: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the shadow tables for one target week; append-once on write."""
    from ..bq import load_dataframe
    from ..config import settings

    if not 1 <= int(week) <= 18:
        raise ValueError("shadow target week must be between 1 and 18")
    generated_at = now or datetime.now(UTC)
    kickoff = _kickoff(SEASON, week)
    staged = {
        key: _staged_rows(f"{settings.raw}.{TABLES[key]}", week) for key in REPORTS
    }
    frames, audit = build(week=week, kickoff=kickoff, staged=staged, generated_at=generated_at)
    audit.update({
        "write_requested": bool(write),
        "featureset_activated": False,
        "shadow_tables": {key: f"{settings.features}.{SHADOW_TABLES[key]}" for key in REPORTS},
    })
    for key in REPORTS:
        table_ref = f"{settings.features}.{SHADOW_TABLES[key]}"
        frame = frames[key]
        existing = _existing_shadow(table_ref, week)
        keys = list(SHADOW_KEY)
        if not existing.empty:
            joined = frame.merge(existing[keys], on=keys, how="left", indicator=True)
            frame = joined.loc[joined._merge.eq("left_only")].drop(columns="_merge")
        report_audit = audit["reports"][key]
        report_audit["existing_rows"] = int(len(existing))
        report_audit["append_rows"] = int(len(frame))
        if write:
            if frame.empty:
                report_audit["write_disposition"] = "already-identical"
            else:
                load_dataframe(frame.reset_index(drop=True), table_ref, write_disposition="WRITE_APPEND")
                report_audit["write_disposition"] = "appended"
            if run_dir is not None:
                advance_ledger(
                    run_dir, key, "consumed", now=generated_at,
                    sha256=report_audit["source_sha256"][0]
                    if len(report_audit["source_sha256"]) == 1 else None,
                    table=table_ref, rows=int(len(frame)),
                )
                report_audit["ledger"] = "consumed"
    print("FP_MATCHUP_SHADOW_JSON=" + json.dumps(audit, sort_keys=True, default=str))
    return audit


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fp-matchup-shadow",
        description="Build the shadow-only point-in-time Fantasy Points matchup tables",
    )
    parser.add_argument("--week", required=True, type=int)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--run-dir", type=Path, default=None,
                        help="capture run directory whose status ledger records 'consumed'")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run(week=args.week, write=args.write, run_dir=args.run_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
