"""Pre-lock prospective capture for Fantasy Points no-history matchup tools.

Retention contract (manifest ``schema_version`` 2)
--------------------------------------------------
Every browser export is kept on disk, including the ones a gate rejects.  Each
attempt at a report is one entry in ``manifest["reports"]`` and carries exactly
one status:

``downloaded``  bytes were saved but the attempt ended before its gates ran
                (only visible in a manifest whose run failed mid-attempt)
``rejected``    the saved bytes failed the schedule gate or the source-regime
                check; the file stays for diagnosis and is never staged
``validated``   the saved bytes passed every capture-time gate before kickoff
``archived``    validated bytes also exist at the hash-addressed GCS object

The stages that follow (``ingest.fantasy_points_matchups_weekly`` -> ``staged``
and ``research.fp_matchup_shadow`` -> ``consumed``) never rewrite this manifest.
They advance the sibling ``status-ledger.json`` through :func:`advance_ledger`,
which refuses to skip a status, so a report can only be consumed after it was
staged, staged after it was validated, and validated after it was downloaded.

Why attempts exist (Week 1, 2026-09-09): the vendor answered the same Week-1
request with two different schedules minutes apart (Arizona at Carolina in one
response, Arizona at the Chargers in the next).  The schedule gate correctly
rejected the stale response each time, and a single-shot capture could never
line up all three reports.  A bounded re-apply per report, with every rejected
export preserved, is the repair; the gate itself is unchanged.

Why the control state is recorded (Week 3, 2026-09-21): the Schedule Week
control accepted ``3`` and then reverted after Apply because the vendor had
not opened Week 3 yet.  The old manifest could not distinguish that from a
missing option or a changed label, so each attempt now records what the
control showed before and after Apply and the run carries a typed
``failure_class``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

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
MANIFEST_SCHEMA_VERSION = 2
DEFAULT_MAX_ATTEMPTS = 3
LEDGER_NAME = "status-ledger.json"

# Vendor team spellings seen in matchup exports, on top of the Route Share map
# (which stays untouched; it belongs to the frozen historical import).
MATCHUP_TEAM_ALIASES: dict[str, str] = {
    **TEAM_MAP,
    "JAC": "JAX",
    "WSH": "WAS",
    "LAR": "LA",
}

REPORT_STATUSES = ("downloaded", "rejected", "validated", "archived")
LEDGER_ORDER = ("downloaded", "validated", "staged", "consumed")

FAILURE_CLASSES = (
    "control-missing",           # the Schedule Week label/control is absent
    "vendor-week-unavailable",   # the target week is not a listbox option
    "vendor-week-not-retained",  # the control showed another week after Apply
    "history-scope-not-default",  # the Week(s) popover is not the vendor All
    "values-contract",           # the Apply response is not the schedule tool
    "no-rows",                   # the table rendered no rows
    "schedule-gate",             # pairs mismatched on every attempt
    "source-regime",             # the export's source season is not allowed
    "after-kickoff",             # capture finished after the first kickoff
    "browser",                   # any other browser/export failure
)


class MatchupCaptureError(RuntimeError):
    """A capture failure with a typed ``failure_class`` for the manifest."""

    def __init__(self, failure_class: str, message: str, **detail: Any) -> None:
        if failure_class not in FAILURE_CLASSES:
            raise ValueError(f"unknown failure class {failure_class!r}")
        super().__init__(message)
        self.failure_class = failure_class
        self.detail = detail


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
    return MATCHUP_TEAM_ALIASES.get(raw, raw)


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


def reconcile_team(
    team: str, opponent: str, expected: set[tuple[str, str]],
) -> str | None:
    """Resolve a vendor team cell to the one scheduled team, or ``None``.

    A single team is returned as is when it forms an expected pair.  In the
    early-season prior-year regime Fantasy Points can retain a comma-separated
    list of teams for a player who changed clubs during the source season;
    the OPP field is still the selected current schedule week.  Such a cell is
    resolved only when exactly one listed team forms an expected pair.
    """
    if (team, opponent) in expected:
        return team
    raw_parts = team.split(",")
    parts = tuple(dict.fromkeys(_team(part) for part in raw_parts if part.strip()))
    matches = sorted(
        candidate for candidate in parts if (candidate, opponent) in expected
    )
    if len(raw_parts) >= 2 and len(parts) >= 2 and len(matches) == 1:
        return matches[0]
    return None


def validate_matchup_pairs(
    observed: set[tuple[str, str]],
    expected: set[tuple[str, str]],
    *,
    report: str,
) -> dict[str, Any]:
    """Fail on stale/wrong opponents or missing scheduled teams."""
    normalized: set[tuple[str, str]] = set()
    reconciled: list[dict[str, list[str]]] = []
    for team, opponent in sorted(observed):
        resolved = reconcile_team(team, opponent, expected)
        if resolved is None:
            normalized.add((team, opponent))
            continue
        normalized.add((resolved, opponent))
        if resolved != team:
            reconciled.append({
                "observed": [team, opponent],
                "normalized": [resolved, opponent],
            })

    unexpected = sorted(normalized - expected)
    missing = sorted(expected - normalized)
    passed = not unexpected and not missing
    return {
        "report": report,
        "passes": passed,
        "observed_pairs": len(observed),
        "normalized_observed_pairs": len(normalized),
        "expected_pairs": len(expected),
        "reconciled_multi_team_pairs": reconciled,
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


# Status ledger ---------------------------------------------------------------


def ledger_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / LEDGER_NAME


def read_ledger(run_dir: str | Path) -> dict[str, Any]:
    path = ledger_path(run_dir)
    if not path.is_file():
        raise FileNotFoundError(f"status ledger is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("reports"), dict):
        raise ValueError(f"status ledger is malformed: {path}")
    return payload


def _write_ledger(run_dir: Path, payload: dict[str, Any]) -> None:
    ledger_path(run_dir).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def new_ledger(run_dir: Path, run_id: str, keys: Sequence[str]) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "reports": {
            key: {status: None for status in LEDGER_ORDER} for key in keys
        },
    }
    _write_ledger(run_dir, payload)
    return payload


def advance_ledger(
    run_dir: str | Path,
    key: str,
    status: str,
    *,
    now: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Record ``status`` for ``key``; every earlier status must already exist.

    ``downloaded`` accumulates one entry per attempt (every export is kept).
    The later statuses bind to exactly one artifact: re-recording them is
    allowed only when the recorded ``sha256`` matches; anything else is a
    conflict, never a silent overwrite.
    """
    run_dir = Path(run_dir)
    if status not in LEDGER_ORDER:
        raise ValueError(f"unknown ledger status {status!r}")
    payload = read_ledger(run_dir)
    if key not in payload["reports"]:
        raise KeyError(f"status ledger has no report {key!r}")
    entry = payload["reports"][key]
    position = LEDGER_ORDER.index(status)
    for earlier in LEDGER_ORDER[:position]:
        if entry.get(earlier) is None:
            raise RuntimeError(
                f"{key}: cannot record {status!r} before {earlier!r}"
            )
    record = {
        "at_utc": (now or datetime.now(UTC)).isoformat(),
        **{name: value for name, value in fields.items()},
    }
    current = entry.get(status)
    if status == "downloaded":
        attempts = list(current["attempts"]) if current else []
        if not any(item.get("sha256") == record.get("sha256") for item in attempts):
            attempts.append(record)
        entry[status] = {"at_utc": attempts[0]["at_utc"], "attempts": attempts}
        _write_ledger(run_dir, payload)
        return payload
    if current is not None:
        if current.get("sha256") != record.get("sha256"):
            raise RuntimeError(
                f"{key}: {status!r} already recorded for a different artifact"
            )
        return payload
    entry[status] = record
    _write_ledger(run_dir, payload)
    return payload


# Browser driver --------------------------------------------------------------


class PlaywrightMatchupDriver:
    """The real browser surface behind :func:`run`; tests inject a fake."""

    def __init__(self, page: Any, timeout_seconds: float) -> None:
        self.page = page
        self.timeout_seconds = float(timeout_seconds)
        self.timeout_ms = int(timeout_seconds * 1000)
        page.set_default_timeout(self.timeout_ms)

    @property
    def url(self) -> str:
        return str(self.page.url)

    def navigate(self, definition: MatchupDefinition) -> None:
        page = self.page
        page.goto(f"{BASE_URL}{definition.path}", wait_until="domcontentloaded")
        page.get_by_text(definition.title, exact=True).first.wait_for(
            state="visible", timeout=self.timeout_ms
        )
        # The route heading is server-rendered before the client-side filter
        # controls.  A fast authenticated load can therefore expose the
        # heading while _filter_container still has nothing to select.  Bind
        # the capture to the actual Schedule Week control, not the shell.
        page.get_by_text("Schedule Week", exact=True).wait_for(
            state="visible", timeout=self.timeout_ms
        )

    def week_control(self) -> dict[str, Any]:
        """What the Schedule Week and Week(s) controls currently display."""
        page = self.page
        state: dict[str, Any] = {
            "present": False, "selected": None, "history_scope": [],
        }
        try:
            container = _filter_container(page, "Schedule Week")
        except RuntimeError as exc:
            state["error"] = str(exc)
            return state
        button = _visible(container.locator("button.fpts-listbox-button"))
        if button is None:
            state["error"] = "Schedule Week listbox button is not visible"
            return state
        state["present"] = True
        lines = [line.strip() for line in button.inner_text().splitlines()]
        state["selected"] = next((line for line in lines if line), None)
        try:
            history = _filter_container(page, "Week(s)")
        except RuntimeError as exc:
            state["history_error"] = str(exc)
            return state
        history_button = _visible(history.locator("button.fpts-popover-button"))
        if history_button is not None:
            state["history_scope"] = sorted({
                line.strip()
                for line in history_button.inner_text().splitlines()
                if line.strip()
            })
        return state

    def visible_options(self) -> list[str]:
        options = self.page.get_by_role("option")
        found: list[str] = []
        for index in range(options.count()):
            candidate = options.nth(index)
            try:
                if not candidate.is_visible():
                    continue
                text = " ".join(
                    line.strip() for line in candidate.inner_text().splitlines()
                    if line.strip()
                )
            except Exception:  # pragma: no cover - defensive against detached nodes
                continue
            if text:
                found.append(text)
        return found

    def select_week(self, week: int) -> None:
        try:
            _select_single_filter(self.page, "Schedule Week", str(week))
        except RuntimeError as exc:
            message = str(exc)
            if "has no option" in message:
                raise MatchupCaptureError(
                    "vendor-week-unavailable",
                    f"Schedule Week has no option {week}",
                    options_visible=self.visible_options(),
                ) from exc
            if "filter label is missing" in message or "filter control is missing" in message:
                raise MatchupCaptureError("control-missing", message) from exc
            raise MatchupCaptureError("browser", message) from exc

    def apply(self, definition: MatchupDefinition) -> Any:
        values_path = f"{definition.path}/values"
        with self.page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and response.url.split("?", 1)[0].endswith(values_path)
            ),
            timeout=self.timeout_ms,
        ) as response_info:
            _click_visible(
                self.page.get_by_role("button", name="Apply", exact=True),
                "Apply button",
            )
        return response_info.value

    def rendered_rows(self) -> int:
        deadline = time.monotonic() + self.timeout_seconds
        while (
            self.page.locator("[role='row']").count() < 2
            and time.monotonic() < deadline
        ):
            self.page.wait_for_timeout(250)
        return int(self.page.locator("[role='row']").count())

    def export(self, destination: Path) -> str:
        page = self.page
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
            raise MatchupCaptureError("browser", "Download as CSV button is missing")
        with page.expect_download(timeout=self.timeout_ms) as event:
            action.click()
        download = event.value
        download.save_as(destination)
        return download.suggested_filename


@contextmanager
def _playwright_driver(
    profile_dir: Path, headless: bool, timeout_seconds: float,
) -> Iterator[PlaywrightMatchupDriver]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('install browser support with `pip install -e ".[browser]"`') from exc
    with sync_playwright() as playwright:
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir), headless=headless, accept_downloads=True,
            viewport={"width": 1800, "height": 1200},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            yield PlaywrightMatchupDriver(page, timeout_seconds)
        finally:
            context.close()


DriverFactory = Callable[[Path, bool, float], Any]


def _assert_values_response(response: Any, definition: MatchupDefinition) -> dict[str, Any]:
    if response.status != 200:
        raise MatchupCaptureError(
            "values-contract", f"Apply values request returned HTTP {response.status}"
        )
    try:
        request = json.loads(response.request.post_data or "{}")
    except json.JSONDecodeError as exc:
        raise MatchupCaptureError(
            "values-contract", "Apply values request has no JSON contract"
        ) from exc
    context = request.get("context", {})
    if not isinstance(context, dict):
        raise MatchupCaptureError(
            "values-contract", "Apply values request context is not an object"
        )
    if (
        context.get("tableProperty") != definition.property
        or context.get("requiresSchedule") is not True
    ):
        raise MatchupCaptureError(
            "values-contract", "Apply values request is not the requested schedule tool"
        )
    payload = response.json()
    if payload.get("errors") or not isinstance(payload.get("content"), dict):
        raise MatchupCaptureError("values-contract", "Apply values response is invalid")
    return {
        "table_property": context.get("tableProperty"),
        "context_keys": sorted(str(key) for key in context),
    }


def _verify_week_control(
    state: dict[str, Any], week: int, *, control: dict[str, Any],
) -> None:
    if not state.get("present"):
        raise MatchupCaptureError(
            "control-missing",
            state.get("error") or "Schedule Week control is missing after Apply",
            schedule_week_control=control,
        )
    if state.get("selected") != str(week):
        raise MatchupCaptureError(
            "vendor-week-not-retained",
            f"Schedule Week control shows {state.get('selected')!r} after Apply, "
            f"not {week}; the vendor has not opened that week",
            schedule_week_control=control,
        )
    if "All" not in state.get("history_scope", []):
        raise MatchupCaptureError(
            "history-scope-not-default",
            "matchup input Week(s) is not the vendor All/default scope",
            schedule_week_control=control,
        )


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


def _status_counts(reports: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in REPORT_STATUSES}
    for report in reports:
        counts[report["status"]] = counts.get(report["status"], 0) + 1
    return counts


def _capture_attempt(
    driver: Any,
    definition: MatchupDefinition,
    *,
    attempt: int,
    season: int,
    week: int,
    run_dir: Path,
    expected: set[tuple[str, str]],
) -> dict[str, Any]:
    """One navigate/select/apply/export cycle; returns the attempt record.

    The record's ``status`` is ``validated`` or ``rejected``; a failure that
    yields no export raises :class:`MatchupCaptureError` and leaves no record
    beyond the manifest's ``failure_class``.
    """
    report: dict[str, Any] = {
        **asdict(definition),
        "attempt": attempt,
        "status": "downloaded",
        "schedule_week": week,
    }
    driver.navigate(definition)
    on_load = driver.week_control()
    driver.select_week(week)
    after_select = driver.week_control()
    response = driver.apply(definition)
    report["values_request"] = _assert_values_response(response, definition)
    after_apply = driver.week_control()
    control = {
        "on_load": on_load, "after_select": after_select, "after_apply": after_apply,
    }
    report["vendor_schedule_week_control"] = control
    _verify_week_control(after_apply, week, control=control)
    if driver.rendered_rows() < 2:
        raise MatchupCaptureError("no-rows", f"{definition.title} rendered no rows")
    destination = run_dir / f"{definition.key}.attempt-{attempt:02d}.csv"
    suggested = driver.export(destination)
    report.update({
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "source_url": driver.url,
        "vendor_suggested_filename": suggested,
        "path": destination.name,
        "bytes": destination.stat().st_size,
    })
    rows, columns = _csv_shape(destination)
    report["csv_rows_including_headers"] = rows
    report["max_csv_columns"] = columns
    report["sha256"] = _sha256(destination)
    try:
        pairs, source_seasons, source_rows = read_matchup_pairs(
            destination, definition.key
        )
    except ValueError as exc:
        report["status"] = "rejected"
        report["rejection"] = {"failure_class": "schedule-gate", "detail": str(exc)}
        return report
    report["source_rows"] = source_rows
    report["source_seasons"] = sorted(source_seasons)
    pair_gate = validate_matchup_pairs(pairs, expected, report=definition.key)
    report["schedule_gate"] = pair_gate
    if not pair_gate["passes"]:
        report["status"] = "rejected"
        report["rejection"] = {
            "failure_class": "schedule-gate",
            "detail": (
                f"unexpected {pair_gate['unexpected_pairs']} "
                f"missing {pair_gate['missing_pairs']}"
            ),
        }
        return report
    try:
        report["source_regime"] = source_regime(source_seasons, season, week)
    except ValueError as exc:
        report["status"] = "rejected"
        report["rejection"] = {"failure_class": "source-regime", "detail": str(exc)}
        return report
    report["status"] = "validated"
    return report


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
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    driver_factory: DriverFactory | None = None,
) -> Path:
    if season != 2026 or not 1 <= week <= 18:
        raise ValueError("live matchup contract is frozen to 2026 Weeks 1-18")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    factory = driver_factory or _playwright_driver

    now = now or datetime.now(UTC)
    schedule = _schedule(season, week)
    expected = expected_schedule_pairs(schedule)
    deadline = first_kickoff_utc(schedule)
    retrieved = pd.Timestamp(now).tz_convert("UTC")
    if retrieved >= deadline:
        raise MatchupCaptureError(
            "after-kickoff",
            f"target Week {week} capture is after first kickoff {deadline.isoformat()}",
        )
    run_id = f"{_utc_stamp(now)}__{CAPTURE_ID}__week-{week:02d}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "capture_id": CAPTURE_ID,
        "run_id": run_id,
        "target_season": season,
        "target_week": week,
        "started_at_utc": now.isoformat(),
        "first_kickoff_utc": deadline.isoformat(),
        "expected_schedule_pairs": [list(pair) for pair in sorted(expected)],
        "max_attempts": int(max_attempts),
        "reports": [],
        "validated_reports": {},
        "status_counts": _status_counts([]),
        "schedule_gate_failures": [],
        "archive_requested": archive,
        "status": "running",
    }
    manifest_path = run_dir / "manifest.json"
    new_ledger(run_dir, run_id, [definition.key for definition in MATCHUPS])

    def persist() -> None:
        manifest["status_counts"] = _status_counts(manifest["reports"])
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    persist()
    try:
        with factory(profile_dir, headless, timeout_seconds) as driver:
            for definition in MATCHUPS:
                accepted: dict[str, Any] | None = None
                for attempt in range(1, max_attempts + 1):
                    report = _capture_attempt(
                        driver, definition, attempt=attempt, season=season,
                        week=week, run_dir=run_dir, expected=expected,
                    )
                    manifest["reports"].append(report)
                    persist()
                    advance_ledger(
                        run_dir, definition.key, "downloaded",
                        path=report["path"], sha256=report["sha256"],
                        attempt=attempt,
                    )
                    if report["status"] == "validated":
                        accepted = report
                        break
                    if report["rejection"]["failure_class"] != "schedule-gate":
                        break
                if accepted is None:
                    manifest["schedule_gate_failures"].append(definition.key)
                    persist()
                    continue
                if pd.Timestamp.now(tz="UTC") >= deadline:
                    raise MatchupCaptureError(
                        "after-kickoff",
                        f"{definition.title} capture completed after first kickoff",
                    )
                if archive:
                    accepted["archive_uri"] = _archive(
                        run_dir / accepted["path"], accepted["sha256"], season, week
                    )
                    accepted["status"] = "archived"
                manifest["validated_reports"][definition.key] = {
                    "path": accepted["path"],
                    "sha256": accepted["sha256"],
                    "attempt": accepted["attempt"],
                    "status": accepted["status"],
                    "archive_uri": accepted.get("archive_uri"),
                }
                persist()
                advance_ledger(
                    run_dir, definition.key, "validated",
                    path=accepted["path"], sha256=accepted["sha256"],
                    attempt=accepted["attempt"],
                    archive_uri=accepted.get("archive_uri"),
                )
        if manifest["schedule_gate_failures"]:
            failed = ", ".join(manifest["schedule_gate_failures"])
            raise MatchupCaptureError(
                "schedule-gate",
                f"matchup schedule gate failed after {max_attempts} attempts for: {failed}",
            )
        finished = datetime.now(UTC)
        if pd.Timestamp(finished) >= deadline:
            raise MatchupCaptureError(
                "after-kickoff", "capture finished after target week's first kickoff",
            )
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["failure_class"] = (
            exc.failure_class if isinstance(exc, MatchupCaptureError) else "browser"
        )
        if isinstance(exc, MatchupCaptureError) and exc.detail:
            manifest["failure_detail"] = exc.detail
        manifest["finished_at_utc"] = datetime.now(UTC).isoformat()
        persist()
        raise
    manifest["status"] = "complete"
    manifest["finished_at_utc"] = finished.isoformat()
    persist()
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
    parser.add_argument(
        "--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS,
        help="re-apply a report this many times while the vendor answers with a stale schedule",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manifest = run(
        season=args.season, week=args.week, output_root=args.output_root,
        profile_dir=args.profile_dir, headless=not args.headed,
        timeout_seconds=args.timeout, archive=args.archive,
        max_attempts=args.max_attempts,
    )
    print(f"Completed: {manifest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
