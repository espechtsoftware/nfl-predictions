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
time is strictly before the target week's first kickoff, which is read from
``nfl_raw.schedules`` here, never from the rows.  When several captures of
the same target week exist (Tuesday and Thursday, say) the latest admissible
one per vendor identity wins and its lag to kickoff is recorded.  A row
captured at or after kickoff is never dropped silently; the build fails.

Identity
--------
Rows are deduplicated on the vendor identity (report, team, opponent,
normalized name, vendor position), which is stable across captures.  Player
ids are resolved once here, from one roster snapshot, so the shadow never
carries the same player twice because a later capture resolved him.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from ..ingest.fantasy_points_matchups_weekly import (
    REPORTS,
    SEASON,
    TABLES,
    VENDOR_KEY,
    metric_columns,
)
from ..ingest.fantasy_points_route import _resolve_player, _snapshot_maps
from ..ops.fantasy_points_matchups import advance_ledger, ledger_path


SHADOW_TABLES = {
    "qb-coverage-matchup": "fp_matchup_shadow_qb_coverage_week",
    "wr-coverage-matchup": "fp_matchup_shadow_wr_coverage_week",
    "line-matchups": "fp_matchup_shadow_line_week",
}
SHADOW_KEY = ("season", "week", "report", "source_sha256", "source_row")
DDL_PATH = "research/fp_matchup_shadow_tables.sql"
INTEGER_COLUMNS = ("season", "week", "source_row", "games", "source_season", "captures_available")


class MatchupLeakageError(RuntimeError):
    """A staged matchup row would be visible at or after its target kickoff."""


def assert_capture_strict_prior(rows: pd.DataFrame, *, kickoff: pd.Timestamp) -> None:
    """Every row's capture time precedes the target week's first kickoff."""
    needed = {"source_retrieved_at", "first_kickoff_utc", "target_week", "season", "source_season"}
    if missing := needed - set(rows.columns):
        raise MatchupLeakageError(f"matchup rows missing {sorted(missing)}")
    if rows.empty:
        return
    retrieved = pd.to_datetime(rows.source_retrieved_at, utc=True)
    if retrieved.isna().any():
        raise MatchupLeakageError("matchup rows carry an unreadable capture time")
    kickoff = pd.Timestamp(kickoff).tz_convert("UTC")
    late = retrieved >= kickoff
    if late.any():
        sample = rows.loc[late, ["report", "vendor_name", "source_retrieved_at"]].head(10)
        raise MatchupLeakageError(
            "Fantasy Points matchup rows captured at/after their target kickoff "
            f"{kickoff.isoformat()}:\n{sample.to_string(index=False)}"
        )
    stored = pd.to_datetime(rows.first_kickoff_utc, utc=True)
    if stored.isna().any() or not stored.eq(kickoff).all():
        raise MatchupLeakageError("staged rows disagree with the schedule's first kickoff")
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
    """Keep the latest capture per vendor identity strictly before ``kickoff``."""
    if rows.empty:
        raise ValueError("no staged matchup rows for the target week")
    if not rows.season.eq(int(season)).all() or not rows.target_week.eq(int(week)).all():
        raise ValueError("staged rows are not all for the requested target week")
    assert_capture_strict_prior(rows, kickoff=kickoff)
    frame = rows.copy()
    frame["source_retrieved_at"] = pd.to_datetime(frame.source_retrieved_at, utc=True)
    keys = list(VENDOR_KEY)
    for column in ("normalized_name", "vendor_pos"):
        frame[column] = frame[column].fillna("").astype(str)
    frame = frame.sort_values(
        keys + ["source_retrieved_at", "source_sha256"], kind="stable",
    )
    latest = frame.drop_duplicates(keys, keep="last").copy()
    counts = frame.groupby(keys, sort=False).source_sha256.nunique()
    latest["captures_available"] = counts.reindex(
        pd.MultiIndex.from_frame(latest[keys])
    ).to_numpy()
    latest["week"] = int(week)
    latest["pit_lag_hours"] = (
        (pd.Timestamp(kickoff).tz_convert("UTC") - latest.source_retrieved_at)
        .dt.total_seconds() / 3600.0
    )
    latest["shadow_generated_at"] = generated_at
    return latest.reset_index(drop=True)


def resolve_identities(frame: pd.DataFrame, *, report: str, snapshots: pd.DataFrame | None) -> pd.DataFrame:
    """Resolve player ids from one roster snapshot at build time."""
    out = frame.copy()
    if report == "line-matchups":
        out["gsis_id"] = None
        out["resolution_status"] = "team"
        out["identity"] = out.team
        return out
    if snapshots is None:
        raise ValueError(f"{report}: player resolution needs roster snapshots")
    by_name, by_season_team = _snapshot_maps(snapshots)
    ids, statuses, identities = [], [], []
    for row in out.itertuples(index=False):
        teams = tuple(sorted(str(row.canonical_teams).split(","))) if row.canonical_teams else ()
        gsis_id, status = _resolve_player(
            SEASON, str(row.normalized_name), str(row.pos), teams, by_name, by_season_team,
        )
        ids.append(gsis_id)
        statuses.append(status)
        identities.append(gsis_id or f"UNRESOLVED:{row.normalized_name}:{row.pos}:{','.join(teams)}")
    out["gsis_id"] = ids
    out["resolution_status"] = statuses
    out["identity"] = identities
    return out


def ensure_tables() -> None:
    """Create the three typed shadow tables when absent (idempotent DDL)."""
    from ..bq import SQL_DIR, run_sql_file

    run_sql_file(SQL_DIR / DDL_PATH)


def _typed_payload(frame: pd.DataFrame) -> pd.DataFrame:
    payload = frame.copy()
    for column in INTEGER_COLUMNS:
        if column in payload.columns:
            payload[column] = payload[column].astype("Int64")
    return payload


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
            SELECT season, week, report, source_sha256, source_row
            FROM `{table_ref}`
            WHERE season = @season AND week = @week
            """, params={"season": SEASON, "week": int(week)})
    except NotFound:
        return pd.DataFrame(columns=list(SHADOW_KEY))


def _snapshots(week: int) -> pd.DataFrame:
    from ..bq import query_df
    from ..config import settings

    return query_df(f"""
        SELECT DISTINCT CAST(season AS INT64) AS season, gsis_id,
               full_name AS name, position AS pos, team
        FROM `{settings.raw}.rosters_weekly`
        WHERE CAST(season AS INT64) = @season
          AND CAST(week AS INT64) <= @week
          AND gsis_id IS NOT NULL AND full_name IS NOT NULL
        """, params={"season": SEASON, "week": int(week)})


def build(
    *,
    week: int,
    kickoff: pd.Timestamp,
    staged: dict[str, pd.DataFrame],
    snapshots: pd.DataFrame | None,
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
        selected = resolve_identities(selected, report=key, snapshots=snapshots)
        columns = (
            ["season", "week", "report", "source_sha256", "source_row", "identity",
             "team", "opponent", "gsis_id", "resolution_status", "vendor_name",
             "normalized_name", "vendor_pos", "pos", "games", "source_season",
             "source_regime"]
            + metric_columns(key)
            + ["source_run_id", "source_retrieved_at", "first_kickoff_utc",
               "pit_lag_hours", "captures_available", "archive_uri",
               "shadow_generated_at"]
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
            "selected_captures": {
                str(run_id): str(sha)
                for run_id, sha in selected[["source_run_id", "source_sha256"]]
                .drop_duplicates().itertuples(index=False)
            },
        }
    return frames, audit


def run(
    *,
    week: int,
    write: bool = False,
    output_root: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the shadow tables for one target week; append-once on write.

    ``output_root`` locates the capture run directories whose ledgers record
    ``consumed`` for the captures the join actually selected.  Without it the
    ledgers are left alone and the audit says so.
    """
    from ..bq import load_dataframe
    from ..config import settings

    if not 1 <= int(week) <= 18:
        raise ValueError("shadow target week must be between 1 and 18")
    generated_at = now or datetime.now(UTC)
    kickoff = _kickoff(SEASON, week)
    staged = {
        key: _staged_rows(f"{settings.raw}.{TABLES[key]}", week) for key in REPORTS
    }
    frames, audit = build(
        week=week, kickoff=kickoff, staged=staged, snapshots=_snapshots(week),
        generated_at=generated_at,
    )
    audit.update({
        "write_requested": bool(write),
        "featureset_activated": False,
        "schedule_authority": f"{settings.raw}.schedules",
        "shadow_tables": {key: f"{settings.features}.{SHADOW_TABLES[key]}" for key in REPORTS},
        "consumed_ledgers": {},
    })
    keys = list(SHADOW_KEY)
    pending: dict[str, pd.DataFrame] = {}
    for key in REPORTS:
        table_ref = f"{settings.features}.{SHADOW_TABLES[key]}"
        frame = frames[key]
        existing = _existing_shadow(table_ref, week)
        if not existing.empty:
            joined = frame.merge(existing[keys], on=keys, how="left", indicator=True)
            frame = joined.loc[joined._merge.eq("left_only")].drop(columns="_merge")
        pending[key] = frame.reset_index(drop=True)
        audit["reports"][key]["existing_rows"] = int(len(existing))
        audit["reports"][key]["append_rows"] = int(len(frame))
    if not write:
        print("FP_MATCHUP_SHADOW_JSON=" + json.dumps(audit, sort_keys=True, default=str))
        return audit
    ensure_tables()
    for key in REPORTS:
        table_ref = f"{settings.features}.{SHADOW_TABLES[key]}"
        frame = pending[key]
        if frame.empty:
            audit["reports"][key]["write_disposition"] = "already-identical"
        else:
            load_dataframe(_typed_payload(frame), table_ref, write_disposition="WRITE_APPEND")
            audit["reports"][key]["write_disposition"] = "appended"
    if output_root is None:
        audit["consumed_ledgers"] = "not-recorded (no output_root)"
    else:
        root = Path(output_root)
        for key in REPORTS:
            table_ref = f"{settings.features}.{SHADOW_TABLES[key]}"
            for run_id, sha in audit["reports"][key]["selected_captures"].items():
                run_dir = root / run_id
                if not ledger_path(run_dir).is_file():
                    audit["consumed_ledgers"].setdefault(run_id, {})[key] = "no-ledger"
                    continue
                advance_ledger(
                    run_dir, key, "consumed", now=generated_at, sha256=sha,
                    table=table_ref, rows=int(len(frames[key][frames[key].source_run_id == run_id])),
                )
                audit["consumed_ledgers"].setdefault(run_id, {})[key] = "consumed"
    print("FP_MATCHUP_SHADOW_JSON=" + json.dumps(audit, sort_keys=True, default=str))
    return audit


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fp-matchup-shadow",
        description="Build the shadow-only point-in-time Fantasy Points matchup tables",
    )
    parser.add_argument("--week", required=True, type=int)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output-root", type=Path, default=None,
                        help="fantasy-points/automated root; the selected captures' ledgers record 'consumed'")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run(week=args.week, write=args.write, output_root=args.output_root)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
