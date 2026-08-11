"""Pre-lock prospective capture for Fantasy Points no-history matchup tools."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from ..config import settings
from ..ingest.fantasy_points_advanced import _grouped_rows
from ..ingest.fantasy_points_coverage import TEAM_NAMES
from ..ingest.fantasy_points_route import TEAM_MAP
from .fantasy_points_downloads import (
    _click_visible,
    _filter_container,
    _open_export_panel,
    _select_single_filter,
    _set_checkbox,
    _sha256,
    _utc_stamp,
    _visible,
    default_profile_dir,
)


BASE_URL = "https://data.fantasypoints.com"
CAPTURE_ID = "2026-live-matchups-v1"


@dataclass(frozen=True)
class MatchupDefinition:
    key: str
    title: str
    property: str
    path: str


MATCHUPS = (
    MatchupDefinition(
        "qb-coverage-matchup", "QB Coverage Matchup", "qbCoverageMatchup",
        "/nfl/tools/player/qb-coverage-matchup",
    ),
    MatchupDefinition(
        "wr-coverage-matchup", "WR Coverage Matchup", "wrCoverageMatchup",
        "/nfl/tools/player/wr-coverage-matchup",
    ),
    MatchupDefinition(
        "line-matchups", "OL/DL Matchups", "lineMatchups",
        "/nfl/tools/team/line-matchups",
    ),
)


def _team(value: object) -> str:
    raw = str(value or "").strip().upper()
    return TEAM_MAP.get(raw, raw)


def _csv_shape(path: Path) -> tuple[int, int]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    return len(rows), max((len(row) for row in rows), default=0)


def read_matchup_pairs(
    path: str | Path,
    report: str,
) -> tuple[set[tuple[str, str]], set[int], int]:
    """Return unique team/opponent pairs, input seasons and source rows."""
    path = Path(path)
    columns, rows = _grouped_rows(path)
    if report in {"qb-coverage-matchup", "wr-coverage-matchup"}:
        required = {
            "Player Details::Team", "Player Details::OPP",
            "Player Details::Season",
        }
        if missing := required - set(columns):
            raise ValueError(f"{path.name} missing {sorted(missing)}")
        team_col = "Player Details::Team"
        opponent_col = "Player Details::OPP"
        season_col = "Player Details::Season"
        parsed = [
            (_team(row[team_col]), _team(row[opponent_col]), int(row[season_col]))
            for row in rows
        ]
    elif report == "line-matchups":
        required = {
            "Offense Stats::Team", "Defense Stats::Name",
            "Team Details::Season",
        }
        if missing := required - set(columns):
            raise ValueError(f"{path.name} missing {sorted(missing)}")
        parsed = []
        for row in rows:
            opponent_name = row["Defense Stats::Name"].strip()
            if opponent_name not in TEAM_NAMES:
                raise ValueError(
                    f"{path.name} has unknown defense team {opponent_name!r}"
                )
            parsed.append((
                _team(row["Offense Stats::Team"]),
                TEAM_NAMES[opponent_name],
                int(row["Team Details::Season"]),
            ))
    else:
        raise ValueError(f"unsupported matchup report {report!r}")
    if not parsed:
        raise ValueError(f"{path.name} has no matchup rows")
    if any(not team or not opponent or team == opponent for team, opponent, _ in parsed):
        raise ValueError(f"{path.name} has invalid matchup identity")
    pairs = {(team, opponent) for team, opponent, _ in parsed}
    seasons = {season for _, _, season in parsed}
    return pairs, seasons, len(parsed)


def expected_schedule_pairs(schedule: pd.DataFrame) -> set[tuple[str, str]]:
    needed = {"home_team", "away_team"}
    if missing := needed - set(schedule.columns):
        raise ValueError(f"schedule missing {sorted(missing)}")
    pairs: set[tuple[str, str]] = set()
    for row in schedule.itertuples(index=False):
        home, away = _team(row.home_team), _team(row.away_team)
        if not home or not away or home == away:
            raise ValueError("target schedule has an invalid game")
        pairs.add((home, away))
        pairs.add((away, home))
    if not pairs:
        raise ValueError("target schedule has no games")
    if len({team for team, _ in pairs}) != len(pairs):
        raise ValueError("target schedule has duplicate team games")
    return pairs


def validate_matchup_pairs(
    observed: set[tuple[str, str]],
    expected: set[tuple[str, str]],
    *,
    report: str,
) -> dict[str, Any]:
    """Fail on stale/wrong opponents or missing scheduled teams."""
    unexpected = sorted(observed - expected)
    missing = sorted(expected - observed)
    passed = not unexpected and not missing
    return {
        "report": report,
        "passes": passed,
        "observed_pairs": len(observed),
        "expected_pairs": len(expected),
        "unexpected_pairs": [list(pair) for pair in unexpected],
        "missing_pairs": [list(pair) for pair in missing],
    }


def first_kickoff_utc(schedule: pd.DataFrame) -> pd.Timestamp:
    needed = {"gameday", "gametime"}
    if missing := needed - set(schedule.columns):
        raise ValueError(f"schedule missing {sorted(missing)}")
    local = pd.to_datetime(
        schedule.gameday.astype(str) + " " + schedule.gametime.astype(str),
        errors="coerce",
    ).dt.tz_localize(
        "America/New_York", ambiguous="NaT", nonexistent="shift_forward",
    ).dt.tz_convert("UTC")
    if local.isna().any() or local.empty:
        raise ValueError("target schedule has an invalid kickoff")
    return local.min()


def source_regime(source_seasons: set[int], target_season: int, week: int) -> str:
    if not source_seasons:
        raise ValueError("matchup export has no source season")
    if len(source_seasons) != 1:
        raise ValueError(
            f"matchup export mixes source seasons {sorted(source_seasons)}"
        )
    if week <= 3:
        allowed = {target_season - 1, target_season}
        if not source_seasons <= allowed:
            raise ValueError(
                f"early matchup source seasons {sorted(source_seasons)} "
                f"outside {sorted(allowed)}"
            )
        return (
            "vendor-prior-season-early"
            if source_seasons == {target_season - 1}
            else "vendor-active-season-early"
        )
    if source_seasons != {target_season}:
        raise ValueError(
            f"Week {week} matchup source is {sorted(source_seasons)}, "
            f"expected active season {target_season}"
        )
    return "vendor-active-season-mature"


def _schedule(season: int, week: int) -> pd.DataFrame:
    from ..bq import query_df

    return query_df(f"""
        SELECT home_team, away_team, gameday, gametime
        FROM `{settings.raw}.schedules`
        WHERE CAST(season AS INT64) = @season
          AND CAST(week AS INT64) = @week
          AND game_type = 'REG'
        ORDER BY gameday, gametime, game_id
        """, params={"season": int(season), "week": int(week)})


def _navigate(page: Any, definition: MatchupDefinition, timeout_ms: int) -> None:
    page.goto(f"{BASE_URL}{definition.path}", wait_until="domcontentloaded")
    page.get_by_text(definition.title, exact=True).first.wait_for(
        state="visible", timeout=timeout_ms
    )


def _verify_schedule_week(page: Any, week: int) -> None:
    container = _filter_container(page, "Schedule Week")
    button = _visible(container.locator("button.fpts-listbox-button"))
    if button is None or str(week) not in {
        line.strip() for line in button.inner_text().splitlines()
    }:
        raise RuntimeError(f"Schedule Week control does not show {week}")
    history = _filter_container(page, "Week(s)")
    history_button = _visible(history.locator("button.fpts-popover-button"))
    history_scope = (
        {line.strip() for line in history_button.inner_text().splitlines()}
        if history_button is not None else set()
    )
    if "All" not in history_scope:
        raise RuntimeError("matchup input Week(s) is not the vendor All/default scope")


def _assert_values_response(response: Any, definition: MatchupDefinition) -> None:
    if response.status != 200:
        raise RuntimeError(f"Apply values request returned HTTP {response.status}")
    try:
        request = json.loads(response.request.post_data or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Apply values request has no JSON contract") from exc
    context = request.get("context", {})
    if (
        context.get("tableProperty") != definition.property
        or context.get("requiresSchedule") is not True
    ):
        raise RuntimeError("Apply values request is not the requested schedule tool")
    payload = response.json()
    if payload.get("errors") or not isinstance(payload.get("content"), dict):
        raise RuntimeError("Apply values response is invalid")


def _export_csv(page: Any, destination: Path, timeout_ms: int) -> str:
    _open_export_panel(page)
    _set_checkbox(page, "Include Group Headers", True)
    _set_checkbox(page, "Include Column Headers", True)
    _set_checkbox(page, "Only Export Selected Rows", False)
    _set_checkbox(page, "Only Export Selected Range", False)
    export_heading = _visible(page.get_by_text("Export Options", exact=True))
    panel = export_heading
    for _ in range(3):
        if panel is not None:
            panel = panel.locator("xpath=..")
    icon = (
        _visible(panel.locator("svg[data-icon='material-symbols:download-sharp']"))
        if panel is not None else None
    )
    action = icon.locator("xpath=..") if icon is not None else None
    if action is None:
        raise RuntimeError("Download as CSV button is missing")
    with page.expect_download(timeout=timeout_ms) as event:
        action.click()
    download = event.value
    download.save_as(destination)
    return download.suggested_filename


def _archive(path: Path, digest: str, season: int, week: int) -> str:
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    name = (
        "licensed/fantasy-points/live-matchups/"
        f"season={season}/week={week:02d}/sha256={digest}/{path.name}"
    )
    blob = storage.Client().bucket(settings.gcs_bucket).blob(name)
    try:
        blob.upload_from_filename(
            str(path), content_type="text/csv", if_generation_match=0
        )
    except PreconditionFailed:
        if hashlib.sha256(blob.download_as_bytes()).hexdigest() != digest:
            raise RuntimeError("hash-addressed matchup archive is non-identical")
    return f"gs://{settings.gcs_bucket}/{name}"


def run(
    *,
    season: int,
    week: int,
    output_root: Path,
    profile_dir: Path,
    headless: bool,
    timeout_seconds: float,
    archive: bool,
    now: datetime | None = None,
) -> Path:
    if season != 2026 or not 1 <= week <= 18:
        raise ValueError("live matchup contract is frozen to 2026 Weeks 1-18")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('install browser support with `pip install -e ".[browser]"`') from exc

    now = now or datetime.now(UTC)
    schedule = _schedule(season, week)
    expected = expected_schedule_pairs(schedule)
    deadline = first_kickoff_utc(schedule)
    retrieved = pd.Timestamp(now).tz_convert("UTC")
    if retrieved >= deadline:
        raise RuntimeError(
            f"target Week {week} capture is after first kickoff {deadline.isoformat()}"
        )
    run_id = f"{_utc_stamp()}__{CAPTURE_ID}__week-{week:02d}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "capture_id": CAPTURE_ID,
        "run_id": run_id,
        "target_season": season,
        "target_week": week,
        "started_at_utc": now.isoformat(),
        "first_kickoff_utc": deadline.isoformat(),
        "expected_schedule_pairs": [list(pair) for pair in sorted(expected)],
        "reports": [],
        "archive_requested": archive,
    }
    manifest_path = run_dir / "manifest.json"
    timeout_ms = int(timeout_seconds * 1000)
    try:
        with sync_playwright() as playwright:
            profile_dir.mkdir(parents=True, exist_ok=True)
            context = playwright.chromium.launch_persistent_context(
                str(profile_dir), headless=headless, accept_downloads=True,
                viewport={"width": 1800, "height": 1200},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(timeout_ms)
            try:
                for definition in MATCHUPS:
                    _navigate(page, definition, timeout_ms)
                    _select_single_filter(page, "Schedule Week", str(week))
                    values_path = f"{definition.path}/values"
                    with page.expect_response(
                        lambda response: (
                            response.request.method == "POST"
                            and response.url.split("?", 1)[0].endswith(values_path)
                        ),
                        timeout=timeout_ms,
                    ) as response_info:
                        _click_visible(
                            page.get_by_role("button", name="Apply", exact=True),
                            "Apply button",
                        )
                    _assert_values_response(response_info.value, definition)
                    _verify_schedule_week(page, week)
                    deadline_wait = time.monotonic() + timeout_seconds
                    while (
                        page.locator("[role='row']").count() < 2
                        and time.monotonic() < deadline_wait
                    ):
                        page.wait_for_timeout(250)
                    if page.locator("[role='row']").count() < 2:
                        raise RuntimeError(f"{definition.title} rendered no rows")
                    destination = run_dir / f"{definition.key}.csv"
                    suggested = _export_csv(page, destination, timeout_ms)
                    pairs, source_seasons, source_rows = read_matchup_pairs(
                        destination, definition.key
                    )
                    pair_gate = validate_matchup_pairs(
                        pairs, expected, report=definition.key
                    )
                    regime = source_regime(source_seasons, season, week)
                    rows, columns = _csv_shape(destination)
                    digest = _sha256(destination)
                    report = {
                        **asdict(definition),
                        "status": "captured",
                        "schedule_week": week,
                        "retrieved_at_utc": datetime.now(UTC).isoformat(),
                        "source_url": page.url,
                        "vendor_suggested_filename": suggested,
                        "path": destination.name,
                        "bytes": destination.stat().st_size,
                        "csv_rows_including_headers": rows,
                        "max_csv_columns": columns,
                        "source_rows": source_rows,
                        "source_seasons": sorted(source_seasons),
                        "source_regime": regime,
                        "sha256": digest,
                        "schedule_gate": pair_gate,
                    }
                    manifest["reports"].append(report)
                    manifest_path.write_text(
                        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                    )
                    if not pair_gate["passes"]:
                        raise RuntimeError(
                            f"{definition.title} schedule pairs do not match 2026 Week {week}"
                        )
                    if pd.Timestamp.now(tz="UTC") >= deadline:
                        raise RuntimeError(
                            f"{definition.title} capture completed after first kickoff"
                        )
                    if archive:
                        report["archive_uri"] = _archive(
                            destination, digest, season, week
                        )
                    manifest_path.write_text(
                        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
                    )
            finally:
                context.close()
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["finished_at_utc"] = datetime.now(UTC).isoformat()
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        raise
    manifest["status"] = "complete"
    manifest["finished_at_utc"] = datetime.now(UTC).isoformat()
    if pd.Timestamp(manifest["finished_at_utc"]) >= deadline:
        manifest["status"] = "failed"
        manifest["error"] = "capture finished after target week's first kickoff"
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        raise RuntimeError(manifest["error"])
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fantasy-points-matchups",
        description="Capture the three frozen pre-lock live matchup tools",
    )
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path.cwd() / "fantasy-points" / "automated",
    )
    parser.add_argument("--profile-dir", type=Path, default=default_profile_dir())
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--archive", action="store_true")
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manifest = run(
        season=args.season, week=args.week, output_root=args.output_root,
        profile_dir=args.profile_dir, headless=not args.headed,
        timeout_seconds=args.timeout, archive=args.archive,
    )
    print(f"Completed: {manifest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
