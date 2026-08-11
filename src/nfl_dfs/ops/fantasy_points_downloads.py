"""Auditable Playwright downloads from the licensed Fantasy Points Data Suite.

Authentication lives only in a persistent browser profile outside the
repository.  Export plans are tracked, while downloaded licensed CSVs and
their run manifests live below the ignored ``fantasy-points/`` directory.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import requests


BASE_URL = "https://data.fantasypoints.com"
TOOLS_URL = f"{BASE_URL}/nfl/tools"
MENU_URL = f"{BASE_URL}/v2/ds/menus"


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    category: str
    title: str
    property: str
    path: str
    group_headers: bool = True


REPORTS: dict[str, ReportDefinition] = {
    report.key: report
    for report in (
        ReportDefinition(
            "advanced-receiving",
            "Receiving",
            "Advanced Receiving",
            "receivingAdvanced",
            "/nfl/tools/player/receiving-advanced",
        ),
        ReportDefinition(
            "advanced-rushing",
            "Rushing",
            "Advanced Rushing",
            "rushingAdvanced",
            "/nfl/tools/player/rushing-advanced",
        ),
        ReportDefinition(
            "advanced-passing",
            "Passing",
            "Advanced Passing",
            "passingAdvanced",
            "/nfl/tools/player/passing-advanced",
        ),
        ReportDefinition(
            "passing-depth",
            "Passing",
            "Passing Depth of Target",
            "passingDepth",
            "/nfl/tools/player/passing-depth",
        ),
        ReportDefinition(
            "route-share",
            "Weekly Reports",
            "Weekly Route Share Report",
            "receivingRouteShareReport",
            "/nfl/tools/player/receiving-route-share-report",
            False,
        ),
        ReportDefinition(
            "target-share",
            "Weekly Reports",
            "Weekly Target Share Report",
            "receivingTargetShareReport",
            "/nfl/tools/player/receiving-target-share-report",
            False,
        ),
        ReportDefinition(
            "snap-share",
            "Weekly Reports",
            "Weekly Snap Share Report",
            "offenseSnapShareReport",
            "/nfl/tools/player/offense-snap-share-report",
            False,
        ),
        ReportDefinition(
            "fantasy-points-scored",
            "Weekly Reports",
            "Weekly Fantasy Points Scored Report",
            "fptsScoredReport",
            "/nfl/tools/player/fpts-scored-report",
            False,
        ),
        ReportDefinition(
            "offense-proe",
            "Weekly Reports",
            "Weekly Pass Rate Over Expectation Report",
            "proeReport",
            "/nfl/tools/team/offense/proe-report",
            False,
        ),
        ReportDefinition(
            "receiving-man-vs-zone",
            "Receiving",
            "Receiving Man vs. Zone",
            "receivingManVsZone",
            "/nfl/tools/player/receiving-man-vs-zone",
        ),
        ReportDefinition(
            "receiving-separation-by-alignment",
            "Receiving",
            "Receiving Separation by Alignment",
            "receivingSeparationByAlignment",
            "/nfl/tools/player/receiving-separation-by-alignment",
        ),
        ReportDefinition(
            "receiving-separation-by-coverage",
            "Receiving",
            "Receiving Separation by Coverage",
            "receivingSeparationByCoverage",
            "/nfl/tools/player/receiving-separation-by-coverage",
        ),
        ReportDefinition(
            "rb-wr-efficiency",
            "Offense",
            "RB + WR Efficiency Report",
            "efficiency",
            "/nfl/tools/player/efficiency",
        ),
        ReportDefinition(
            "offense-snaps",
            "Offense",
            "Snaps Report",
            "offenseSnaps",
            "/nfl/tools/player/offense-snaps",
        ),
        ReportDefinition(
            "run-pass",
            "Offense",
            "Run/Pass Report",
            "runPassReport",
            "/nfl/tools/team/run-pass-report",
        ),
        ReportDefinition(
            "coverage-matrix",
            "Team",
            "Coverage Matrix",
            "coverageMatrix",
            "/nfl/tools/team/defense/coverage-matrix",
        ),
    )
}


@dataclass(frozen=True)
class ExportSpec:
    report: str
    season: int
    weeks: tuple[int, ...]
    include_group_headers: bool
    context: str | None = None
    target_week: int | None = None

    @property
    def definition(self) -> ReportDefinition:
        return REPORTS[self.report]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_profile_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "nfl-dfs" / "fantasy-points-playwright"


def parse_weeks(value: Any) -> tuple[int, ...]:
    """Parse ``1-4``, ``[1,2,3]`` or ``1,3-5`` into ordered unique weeks."""
    if isinstance(value, int):
        values: Iterable[Any] = [value]
    elif isinstance(value, list):
        values = value
    elif isinstance(value, str):
        values = [part.strip() for part in value.split(",") if part.strip()]
    else:
        raise ValueError(f"weeks must be an integer, list, or range string; got {value!r}")

    weeks: list[int] = []
    for part in values:
        if isinstance(part, int):
            candidates = [part]
        elif isinstance(part, str) and re.fullmatch(r"\d+", part):
            candidates = [int(part)]
        elif isinstance(part, str) and re.fullmatch(r"\d+\s*-\s*\d+", part):
            start, end = (int(piece.strip()) for piece in part.split("-", 1))
            if end < start:
                raise ValueError(f"week range ends before it starts: {part!r}")
            candidates = list(range(start, end + 1))
        else:
            raise ValueError(f"invalid week selection component: {part!r}")
        weeks.extend(candidates)

    unique = tuple(sorted(set(weeks)))
    if not unique or unique[0] < 1 or unique[-1] > 22:
        raise ValueError(f"weeks must be between 1 and 22; got {unique!r}")
    return unique


def compact_weeks(weeks: Sequence[int]) -> str:
    if not weeks:
        raise ValueError("at least one week is required")
    runs: list[str] = []
    start = previous = int(weeks[0])
    for value in (int(item) for item in weeks[1:]):
        if value == previous + 1:
            previous = value
            continue
        runs.append(f"{start:02d}" if start == previous else f"{start:02d}-{previous:02d}")
        start = previous = value
    runs.append(f"{start:02d}" if start == previous else f"{start:02d}-{previous:02d}")
    return "_".join(runs)


def expand_plan(payload: dict[str, Any]) -> list[ExportSpec]:
    if payload.get("schema_version") != 1:
        raise ValueError("plan schema_version must be 1")
    reports = payload.get("reports")
    if not isinstance(reports, list) or not reports:
        raise ValueError("plan reports must be a non-empty list")

    expanded: list[ExportSpec] = []
    seen: set[tuple[Any, ...]] = set()
    for item in reports:
        if not isinstance(item, dict):
            raise ValueError("each reports entry must be an object")
        report_key = item.get("report")
        if report_key not in REPORTS:
            raise ValueError(
                f"unknown report {report_key!r}; choose one of {', '.join(sorted(REPORTS))}"
            )
        seasons = item.get("seasons")
        windows = item.get("week_windows")
        target_weeks_raw = item.get("target_weeks")
        source_window = item.get("source_window")
        if not isinstance(seasons, list) or not seasons:
            raise ValueError(f"{report_key}: seasons must be a non-empty list")
        explicit = isinstance(windows, list) and bool(windows)
        generated = target_weeks_raw is not None or source_window is not None
        if explicit == generated:
            raise ValueError(
                f"{report_key}: use either week_windows or "
                "target_weeks plus source_window"
            )
        definition = REPORTS[report_key]
        group_headers = bool(item.get("include_group_headers", definition.group_headers))
        context = item.get("context")
        if context not in (None, "Player", "Offense", "Defense"):
            raise ValueError(f"{report_key}: unsupported context {context!r}")
        generated_windows: list[tuple[tuple[int, ...], int | None]]
        if explicit:
            generated_windows = [(parse_weeks(window), None) for window in windows]
        else:
            target_weeks = parse_weeks(target_weeks_raw)
            if source_window not in ("cumulative-prior", "last-four-prior"):
                raise ValueError(
                    f"{report_key}: source_window must be cumulative-prior "
                    "or last-four-prior"
                )
            generated_windows = []
            for target_week in target_weeks:
                if target_week < 2:
                    raise ValueError(f"{report_key}: target week must be at least 2")
                first = 1 if source_window == "cumulative-prior" else max(1, target_week - 4)
                generated_windows.append((tuple(range(first, target_week)), target_week))
        for season_raw in seasons:
            season = int(season_raw)
            if season < 2010 or season > 2100:
                raise ValueError(f"invalid season: {season}")
            for weeks, target_week in generated_windows:
                if target_week is not None and max(weeks) >= target_week:
                    raise ValueError(
                        f"{report_key}: source weeks must be strictly before target week"
                    )
                identity = (
                    report_key,
                    season,
                    weeks,
                    group_headers,
                    context,
                    target_week,
                )
                if identity in seen:
                    raise ValueError(f"duplicate export in plan: {identity!r}")
                seen.add(identity)
                expanded.append(
                    ExportSpec(
                        report=report_key,
                        season=season,
                        weeks=weeks,
                        include_group_headers=group_headers,
                        context=context,
                        target_week=target_week,
                    )
                )
    return expanded


def load_plan(path: Path) -> tuple[dict[str, Any], list[ExportSpec]]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("plan root must be an object")
    return payload, expand_plan(payload)


def artifact_name(spec: ExportSpec) -> str:
    context = f"__context-{spec.context.lower()}" if spec.context else ""
    target = f"__target-week-{spec.target_week:02d}" if spec.target_week else ""
    return (
        f"{spec.report}__season-{spec.season}"
        f"__weeks-{compact_weeks(spec.weeks)}{target}{context}.csv"
    )


def validate_catalog(timeout: float = 30.0) -> dict[str, Any]:
    response = requests.post(MENU_URL, json={"useCache": True}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    root = payload.get("content", {}).get("appMenu", {})
    actual: dict[str, tuple[str, str]] = {}
    for category in root.get("children", []):
        for report in category.get("children", []):
            prop = report.get("property")
            if prop:
                actual[prop] = (category.get("name", ""), report.get("name", ""))
    drift = []
    for definition in REPORTS.values():
        found = actual.get(definition.property)
        expected = (definition.category, definition.title)
        if found != expected:
            drift.append(
                {"property": definition.property, "expected": expected, "actual": found}
            )
    if drift:
        raise RuntimeError(f"Fantasy Points menu schema drifted: {json.dumps(drift)}")
    return {"validated_reports": len(REPORTS), "roles": payload.get("session", {}).get("roles", [])}


def _utc_stamp(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _csv_shape(path: Path) -> tuple[int, int]:
    rows = 0
    max_columns = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            rows += 1
            max_columns = max(max_columns, len(row))
    if rows < 2 or max_columns < 2:
        raise RuntimeError(f"download is not a populated CSV: {path}")
    return rows, max_columns


def _visible(locator: Any) -> Any | None:
    for index in range(locator.count()):
        candidate = locator.nth(index)
        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    return None


def _click_visible(locator: Any, description: str) -> None:
    candidate = _visible(locator)
    if candidate is None:
        raise RuntimeError(f"could not find visible {description}")
    candidate.click()


def _navigate_to_report(page: Any, definition: ReportDefinition, timeout_ms: int) -> None:
    # Direct report routes are materially more reliable than the animated
    # dashboard menus and are still the vendor's normal authenticated UI.
    # The SPA occasionally returns an empty shell on first load, so make a
    # small bounded retry before failing closed.
    attempt_timeout = max(5_000, min(timeout_ms, 45_000))
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            page.goto(
                f"{BASE_URL}{definition.path}",
                wait_until="domcontentloaded",
                timeout=attempt_timeout,
            )
            if "/login" in page.url:
                raise RuntimeError(
                    "Fantasy Points session is not authenticated; run "
                    "`fantasy-points-download login`"
                )
            report_heading = page.get_by_text(
                re.compile(rf"^{re.escape(definition.title)}(?:\s+-\s+.+)?$")
            )
            report_heading.first.wait_for(
                state="visible", timeout=attempt_timeout
            )
            page.get_by_text("Season", exact=True).first.wait_for(
                state="visible", timeout=attempt_timeout
            )
            return
        except RuntimeError:
            raise
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                page.wait_for_timeout(500 * (attempt + 1))
    raise RuntimeError(
        f"report did not load after three attempts: {definition.title} ({page.url})"
    ) from last_error


def _filter_container(page: Any, label_text: str) -> Any:
    label = _visible(page.get_by_text(label_text, exact=True))
    if label is None:
        raise RuntimeError(f"filter label is missing: {label_text}")
    current = label
    control_selector = (
        "select, [role='combobox'], input, "
        "button.fpts-listbox-button, button.fpts-popover-button"
    )
    for _ in range(8):
        current = current.locator("xpath=..")
        if _visible(current.locator(control_selector)) is not None:
            return current
    raise RuntimeError(f"filter control is missing: {label_text}")


def _select_single_filter(page: Any, label_text: str, value: str) -> None:
    container = _filter_container(page, label_text)
    native = _visible(container.locator("select"))
    if native is not None:
        try:
            native.select_option(label=value)
        except Exception:
            native.select_option(value=value)
        return
    control = _visible(
        container.locator(
            "[role='combobox'], input, button.fpts-listbox-button"
        )
    )
    if control is None:
        control = _visible(container.locator("button"))
    if control is None:
        raise RuntimeError(f"cannot operate filter: {label_text}")
    if value in {line.strip() for line in control.inner_text().splitlines()}:
        return
    control.click()
    option = None
    options = page.get_by_role("option")
    for index in range(options.count()):
        candidate = options.nth(index)
        if not candidate.is_visible():
            continue
        lines = {line.strip() for line in candidate.inner_text().splitlines()}
        if value in lines:
            option = candidate
            break
    if option is None and control.evaluate("el => el.matches('input')"):
        control.fill(value)
        control.press("Enter")
        return
    if option is None:
        raise RuntimeError(f"filter {label_text!r} has no option {value!r}")
    option.click()
    if value not in {line.strip() for line in control.inner_text().splitlines()}:
        raise RuntimeError(f"filter {label_text!r} did not retain {value!r}")


def _select_week_filter(page: Any, weeks: Sequence[int]) -> None:
    container = _filter_container(page, "Week(s)")
    control = _visible(container.locator("button.fpts-popover-button"))
    if control is None:
        raise RuntimeError("cannot operate Week(s) filter")
    control.click()
    page.wait_for_timeout(250)
    panel_id = control.get_attribute("aria-controls")
    if not panel_id:
        raise RuntimeError("Week(s) popover has no controlled panel")
    panel = page.locator(f"#{panel_id}")
    panel.wait_for(state="visible")
    none_button = _visible(panel.get_by_role("button", name="None", exact=True))
    if none_button is None:
        raise RuntimeError("Week(s) popover is missing its None preset")
    none_button.click()

    wanted = {int(value) for value in weeks}
    for week in sorted(wanted):
        option = panel.locator(f"[data-option='REG:{week}']")
        if option.count() != 1 or not option.is_visible():
            raise RuntimeError(f"Week(s) filter has no selectable regular week {week}")
        option.click()

    selected = {
        int(value.split(":", 1)[1])
        for value in panel.locator("[data-option^='REG:'].selected").evaluate_all(
            "els => els.map(el => el.dataset.option)"
        )
    }
    if selected != wanted:
        raise RuntimeError(
            f"Week(s) filter retained {sorted(selected)}, expected {sorted(wanted)}"
        )
    control.click()
    if control.get_attribute("aria-expanded") != "false":
        raise RuntimeError("Week(s) popover did not close after selection")


def _verify_applied_filters(page: Any, spec: ExportSpec) -> None:
    season_container = _filter_container(page, "Season")
    season_control = _visible(season_container.locator("button.fpts-listbox-button"))
    if season_control is None or str(spec.season) not in {
        line.strip() for line in season_control.inner_text().splitlines()
    }:
        raise RuntimeError(f"applied Season does not show {spec.season}")

    week_container = _filter_container(page, "Week(s)")
    week_control = _visible(week_container.locator("button.fpts-popover-button"))
    if week_control is None:
        raise RuntimeError("applied Week(s) control is missing")
    week_control.click()
    panel_id = week_control.get_attribute("aria-controls")
    panel = page.locator(f"#{panel_id}") if panel_id else None
    if panel is None:
        raise RuntimeError("applied Week(s) popover has no controlled panel")
    selected = {
        int(value.split(":", 1)[1])
        for value in panel.locator("[data-option^='REG:'].selected").evaluate_all(
            "els => els.map(el => el.dataset.option)"
        )
    }
    week_control.click()
    expected = {int(value) for value in spec.weeks}
    if selected != expected:
        raise RuntimeError(
            f"applied Week(s) shows {sorted(selected)}, expected {sorted(expected)}"
        )


def _assert_values_response_scope(response: Any, spec: ExportSpec) -> None:
    if response.status != 200:
        raise RuntimeError(f"Apply values request returned HTTP {response.status}")
    try:
        request = json.loads(response.request.post_data or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Apply values request has no JSON filter contract") from exc
    context = request.get("context", {})
    actual_weeks = context.get("weeks", {}).get("REG")
    actual_season = (
        context.get("filterMatch", {}).get("game.season", {}).get("eq")
    )
    if actual_weeks != list(spec.weeks) or actual_season != spec.season:
        raise RuntimeError(
            "Apply values request scope differs from the export: "
            f"season={actual_season}, weeks={actual_weeks}"
        )
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError("Apply values response is not JSON") from exc
    if payload.get("errors"):
        raise RuntimeError(f"Apply values response has errors: {payload['errors']}")
    if not isinstance(payload.get("content"), dict):
        raise RuntimeError("Apply values response has no content")


def _rendered_game_counts(page: Any) -> list[int]:
    games: list[int] = []
    rows = page.locator("[role='row']")
    for index in range(rows.count()):
        row = rows.nth(index)
        if not row.is_visible():
            continue
        lines = [line.strip() for line in row.inner_text().splitlines()]
        if not lines or not lines[0].isdigit():
            continue
        # Player reports freeze Rank/Name/Team/POS/G at the left edge.
        if (
            len(lines) >= 5
            and lines[3].upper() in {"QB", "RB", "FB", "WR", "TE"}
        ):
            if lines[4].isdigit():
                games.append(int(lines[4]))
            continue
        # Team reports freeze Rank/Name/G/Season/Location/Team/DB.
        if (
            len(lines) >= 4
            and lines[2].isdigit()
            and re.fullmatch(r"20\d{2}", lines[3])
        ):
            games.append(int(lines[2]))
    return games


def _wait_for_rendered_scope(page: Any, spec: ExportSpec, timeout_ms: int) -> None:
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while time.monotonic() < deadline:
        games = _rendered_game_counts(page)
        if games and min(games) >= 1 and max(games) <= len(spec.weeks):
            return
        page.wait_for_timeout(250)
    raise RuntimeError(
        f"rendered table did not reach {spec.season} Weeks {list(spec.weeks)}"
    )


def _validate_download_scope(path: Path, spec: ExportSpec) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    header_index = next(
        (
            index
            for index, row in enumerate(rows[:2])
            if "Season" in row and "G" in row
        ),
        None,
    )
    if header_index is None:
        raise RuntimeError(f"{path.name} has no Season/G scope columns")
    header = rows[header_index]
    season_index = header.index("Season")
    games_index = header.index("G")
    seasons: set[int] = set()
    games: list[int] = []
    for row in rows[header_index + 1:]:
        if len(row) <= max(season_index, games_index):
            raise RuntimeError(f"{path.name} has a malformed scope row")
        if not row[season_index].strip() and not row[games_index].strip():
            continue
        try:
            seasons.add(int(row[season_index]))
            games.append(int(float(row[games_index])))
        except ValueError as exc:
            raise RuntimeError(f"{path.name} has nonnumeric Season/G") from exc
    if seasons != {spec.season}:
        raise RuntimeError(
            f"{path.name} contains seasons {sorted(seasons)}, expected {spec.season}"
        )
    if not games or min(games) < 1 or max(games) > len(spec.weeks):
        raise RuntimeError(
            f"{path.name} G range is outside a {len(spec.weeks)}-week window"
        )


def _select_context(page: Any, context: str) -> None:
    expected_segment = {
        "Player": "/player/",
        "Offense": "/team/offense/",
        "Defense": "/team/defense/",
    }[context]
    if expected_segment in page.url:
        return
    current_path = page.url.split(BASE_URL, 1)[-1].split("?", 1)[0]
    if "/player/" in current_path:
        target_path = current_path.replace("/player/", expected_segment, 1)
    elif "/team/offense/" in current_path:
        target_path = current_path.replace("/team/offense/", expected_segment, 1)
    elif "/team/defense/" in current_path:
        target_path = current_path.replace("/team/defense/", expected_segment, 1)
    else:
        raise RuntimeError(f"cannot derive context route from {page.url}")
    target = _visible(page.locator(f"a[href='{target_path}']"))
    if target is None:
        raise RuntimeError(
            f"context {context} route is unavailable: {target_path}"
        )
    target.click()
    page.wait_for_url(re.compile(rf"{re.escape(target_path)}(?:\?|$)"))
    page.get_by_text("Season", exact=True).first.wait_for(state="visible")
    if expected_segment not in page.url:
        raise RuntimeError(f"context {context} did not load ({page.url})")


def _set_checkbox(page: Any, label_text: str, checked: bool) -> None:
    label = _visible(page.get_by_text(label_text, exact=True))
    if label is None:
        raise RuntimeError(f"export option is missing: {label_text}")
    current = label
    checkbox = None
    for _ in range(4):
        current = current.locator("xpath=..")
        checkbox = _visible(
            current.locator(
                "input[type='checkbox'], [role='checkbox'], [role='switch']"
            )
        )
        if checkbox is not None:
            break
    if checkbox is None:
        raise RuntimeError(f"checkbox control is missing: {label_text}")
    state = checkbox.is_checked() if checkbox.evaluate("el => el.matches('input')") else checkbox.get_attribute("aria-checked") == "true"
    if state != checked:
        checkbox.click()


def _open_export_panel(page: Any) -> None:
    if _visible(page.get_by_text("Export Options", exact=True)) is not None:
        return
    candidates = (
        page.locator("[title='Toggle Export Options']"),
        page.get_by_role("button", name=re.compile("export", re.IGNORECASE)),
        page.locator("[aria-label*='Export' i], [title*='Export' i]"),
        page.locator("button").filter(has=page.locator("svg")),
    )
    for locator in candidates:
        button = _visible(locator)
        if button is None:
            continue
        button.click()
        if _visible(page.get_by_text("Export Options", exact=True)) is not None:
            return
    raise RuntimeError("could not open Export Options")


def _download_one(page: Any, spec: ExportSpec, destination: Path, timeout_ms: int) -> dict[str, Any]:
    started = datetime.now(UTC)
    _navigate_to_report(page, spec.definition, timeout_ms)
    if spec.context:
        _select_context(page, spec.context)
    _select_single_filter(page, "Season", str(spec.season))
    _select_week_filter(page, spec.weeks)
    values_path = f"{spec.definition.path}/values"
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
    _assert_values_response_scope(response_info.value, spec)
    _verify_applied_filters(page, spec)
    _wait_for_rendered_scope(page, spec, timeout_ms)

    _open_export_panel(page)
    _set_checkbox(page, "Include Group Headers", spec.include_group_headers)
    _set_checkbox(page, "Include Column Headers", True)
    _set_checkbox(page, "Only Export Selected Rows", False)
    _set_checkbox(page, "Only Export Selected Range", False)

    # The vendor renders the primary CSV action as a clickable ``div`` next
    # to a real dropdown button, so accessible button lookup cannot see it.
    export_heading = _visible(page.get_by_text("Export Options", exact=True))
    export_panel = export_heading
    for _ in range(3):
        if export_panel is not None:
            export_panel = export_panel.locator("xpath=..")
    download_icon = (
        _visible(
            export_panel.locator(
                "svg[data-icon='material-symbols:download-sharp']"
            )
        )
        if export_panel is not None
        else None
    )
    download_action = download_icon.locator("xpath=..") if download_icon is not None else None
    if download_action is None:
        raise RuntimeError("Download as CSV button is missing")
    with page.expect_download(timeout=timeout_ms) as event:
        download_action.click()
    download = event.value
    download.save_as(destination)
    _validate_download_scope(destination, spec)
    rows, columns = _csv_shape(destination)
    return {
        "status": "downloaded",
        "report": spec.report,
        "vendor_property": spec.definition.property,
        "season": spec.season,
        "weeks": list(spec.weeks),
        "include_group_headers": spec.include_group_headers,
        "context": spec.context,
        "target_week": spec.target_week,
        "retrieved_at_utc": started.isoformat(),
        "source_url": page.url,
        "vendor_suggested_filename": download.suggested_filename,
        "path": destination.name,
        "bytes": destination.stat().st_size,
        "csv_rows_including_headers": rows,
        "max_csv_columns": columns,
        "sha256": _sha256(destination),
    }


def run_downloads(
    plan_path: Path,
    output_root: Path,
    profile_dir: Path,
    *,
    headless: bool,
    timeout_seconds: float,
    reuse_from: Path | None = None,
) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised without browser extra
        raise RuntimeError('install browser support with `pip install -e ".[browser]"`') from exc

    payload, specs = load_plan(plan_path)
    catalog = validate_catalog(timeout_seconds)
    run_id = f"{_utc_stamp()}__{re.sub(r'[^a-z0-9-]+', '-', payload.get('name', 'exports').lower()).strip('-')}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "plan": str(plan_path.resolve()),
        "plan_sha256": _sha256(plan_path),
        "started_at_utc": datetime.now(UTC).isoformat(),
        "point_in_time_contract": "Every target week may use only completed source weeks strictly less than it.",
        "catalog": catalog,
        "exports": [],
    }
    manifest_path = run_dir / "manifest.json"
    timeout_ms = int(timeout_seconds * 1000)

    if reuse_from is not None:
        reused, prior_run_id = _reuse_download_prefix(
            reuse_from,
            run_dir,
            specs,
            plan_sha256=manifest["plan_sha256"],
        )
        manifest["exports"].extend(reused)
        manifest["reused_from_run_id"] = prior_run_id
        manifest["reused_exports"] = len(reused)
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with sync_playwright() as playwright:
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=headless,
            accept_downloads=True,
            viewport={"width": 1800, "height": 1200},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            for index, spec in enumerate(specs, start=1):
                destination = run_dir / artifact_name(spec)
                if index <= len(manifest["exports"]):
                    print(
                        f"[{index}/{len(specs)} reused] {destination.name}",
                        flush=True,
                    )
                    continue
                print(f"[{index}/{len(specs)}] {destination.name}", flush=True)
                try:
                    result = _download_one(page, spec, destination, timeout_ms)
                except Exception as exc:
                    screenshot = run_dir / f"failure-{index:03d}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    result = {
                        "status": "failed",
                        "report": spec.report,
                        "season": spec.season,
                        "weeks": list(spec.weeks),
                        "error": f"{type(exc).__name__}: {exc}",
                        "source_url": page.url,
                        "screenshot": screenshot.name,
                    }
                    manifest["exports"].append(result)
                    manifest["finished_at_utc"] = datetime.now(UTC).isoformat()
                    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                    raise
                manifest["exports"].append(result)
                manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                time.sleep(float(payload.get("delay_between_downloads_seconds", 2.0)))
        finally:
            context.close()

    manifest["finished_at_utc"] = datetime.now(UTC).isoformat()
    manifest["status"] = "complete"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _reuse_download_prefix(
    prior_run_dir: Path,
    destination_dir: Path,
    specs: Sequence[ExportSpec],
    *,
    plan_sha256: str,
) -> tuple[list[dict], str]:
    """Copy a verified successful prefix into a new immutable run."""
    prior_run_dir = prior_run_dir.resolve()
    manifest_path = prior_run_dir / "manifest.json"
    prior = json.loads(manifest_path.read_text())
    if prior.get("schema_version") != 1:
        raise ValueError("reuse manifest schema must be 1")
    if prior.get("plan_sha256") != plan_sha256:
        raise ValueError("reuse manifest was produced from another plan")
    prior_run_id = str(prior.get("run_id", ""))
    if not prior_run_id:
        raise ValueError("reuse manifest has no run id")
    exports = prior.get("exports")
    if not isinstance(exports, list):
        raise ValueError("reuse manifest exports must be a list")
    prefix: list[dict] = []
    stopped = False
    for index, item in enumerate(exports):
        if item.get("status") != "downloaded":
            stopped = True
            continue
        if stopped:
            raise ValueError("reuse manifest has downloads after a failure")
        if index >= len(specs):
            raise ValueError("reuse manifest has more exports than the plan")
        spec = specs[index]
        expected = {
            "report": spec.report,
            "season": spec.season,
            "weeks": list(spec.weeks),
            "include_group_headers": spec.include_group_headers,
            "context": spec.context,
            "target_week": spec.target_week,
        }
        if any(item.get(key) != value for key, value in expected.items()):
            raise ValueError(f"reuse export {index + 1} differs from the plan")
        relative = Path(str(item.get("path", "")))
        if not relative.name or relative != Path(relative.name):
            raise ValueError(f"reuse export {index + 1} has an unsafe path")
        source = prior_run_dir / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        if _sha256(source) != item.get("sha256"):
            raise ValueError(f"reuse export {index + 1} hash differs")
        if source.stat().st_size != int(item.get("bytes", -1)):
            raise ValueError(f"reuse export {index + 1} byte count differs")
        rows, columns = _csv_shape(source)
        if rows != int(item.get("csv_rows_including_headers", -1)):
            raise ValueError(f"reuse export {index + 1} row count differs")
        if columns != int(item.get("max_csv_columns", -1)):
            raise ValueError(f"reuse export {index + 1} width differs")
        _validate_download_scope(source, spec)
        destination = destination_dir / artifact_name(spec)
        shutil.copy2(source, destination)
        copied = dict(item)
        copied["path"] = destination.name
        copied["reused_from_run_id"] = prior_run_id
        prefix.append(copied)
    return prefix, prior_run_id


def interactive_login(
    profile_dir: Path, timeout_seconds: float, *, terminal_credentials: bool = False
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('install browser support with `pip install -e ".[browser]"`') from exc

    with sync_playwright() as playwright:
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            viewport={"width": 1800, "height": 1200},
        )
        page = context.pages[0] if context.pages else context.new_page()
        timeout_ms = int(timeout_seconds * 1000)
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        if terminal_credentials:
            print("Credentials are used only to fill the open browser and are not logged or saved.")
            email = input("Fantasy Points email: ").strip()
            password = getpass.getpass("Fantasy Points password (input hidden): ")
            if not email or not password:
                raise RuntimeError("email and password are required")
            page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
            if "/login" not in page.url:
                del password
                print("The saved browser profile is already authenticated.")
                context.close()
                return
            # The vendor currently omits type=email even though the field has
            # email autocomplete semantics.  Prefer stable ids/autocomplete
            # and retain the type selector for compatible revisions.
            email_input = page.locator(
                "#login-form-email, input[autocomplete='email'], input[type='email']"
            )
            password_input = page.locator(
                "#login-form-password, input[autocomplete='current-password'], input[type='password']"
            )
            try:
                email_input.first.wait_for(state="visible", timeout=timeout_ms)
                password_input.first.wait_for(state="visible", timeout=timeout_ms)
            except Exception as exc:
                raise RuntimeError(
                    "Fantasy Points login form did not become ready "
                    f"(url={page.url}, email_fields={email_input.count()}, "
                    f"password_fields={password_input.count()})"
                ) from exc
            email_input = email_input.first
            password_input = password_input.first
            email_input.fill(email)
            password_input.fill(password)
            del password
            _click_visible(
                page.get_by_role("button", name=re.compile(r"sign\s*in", re.IGNORECASE)),
                "Sign In button",
            )
            try:
                page.wait_for_url(
                    re.compile(r"/nfl/tools(?:/|$)"),
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception as exc:
                form = page.locator("form[name='login']")
                form_text = form.inner_text().strip() if form.count() else ""
                harmless = {"email", "password", "sign in", "forgot password"}
                detail = [
                    line.strip()
                    for line in form_text.splitlines()
                    if line.strip() and line.strip().lower() not in harmless
                ]
                suffix = f" Site message: {' '.join(detail)}" if detail else ""
                raise RuntimeError(
                    f"Fantasy Points sign-in remained at {page.url}.{suffix}"
                ) from exc
            print("Login completed; the authenticated browser profile is saved locally.")
        else:
            print("Sign in to Fantasy Points in the opened browser.")
            input(
                "After the Data Suite dashboard is visible, press Enter here to save the session: "
            )
        context.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fantasy-points-download",
        description="Auditable Playwright exports from Fantasy Points Data Suite",
    )
    parser.add_argument("--profile-dir", type=Path, default=default_profile_dir())
    parser.add_argument("--timeout", type=float, default=120.0, help="browser timeout in seconds")
    subparsers = parser.add_subparsers(dest="command", required=True)
    login = subparsers.add_parser("login", help="open a persistent browser for one-time login")
    login.add_argument(
        "--terminal-credentials",
        action="store_true",
        help="prompt securely in the terminal and fill the browser automatically",
    )
    check = subparsers.add_parser("check", help="validate a plan and the live report catalog")
    check.add_argument("--plan", type=Path, required=True)
    run = subparsers.add_parser("run", help="run every export in a plan")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument(
        "--output-root", type=Path, default=_repo_root() / "fantasy-points" / "automated"
    )
    run.add_argument("--headed", action="store_true", help="show the browser while exporting")
    run.add_argument(
        "--reuse-from",
        type=Path,
        help=(
            "start a new run by verifying and copying the successful prefix "
            "of an interrupted run directory"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "login":
            interactive_login(
                args.profile_dir,
                args.timeout,
                terminal_credentials=args.terminal_credentials,
            )
            return 0
        payload, specs = load_plan(args.plan)
        catalog = validate_catalog(args.timeout)
        if args.command == "check":
            print(
                json.dumps(
                    {
                        "plan": payload.get("name"),
                        "exports": len(specs),
                        "catalog": catalog,
                        "artifacts": [artifact_name(spec) for spec in specs],
                    },
                    indent=2,
                )
            )
            return 0
        manifest = run_downloads(
            args.plan,
            args.output_root,
            args.profile_dir,
            headless=not args.headed,
            timeout_seconds=args.timeout,
            reuse_from=args.reuse_from,
        )
        print(f"Completed: {manifest}")
        return 0
    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
