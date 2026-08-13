"""Auditable Playwright acquisition from SIS DataHub Pro.

Authentication is retained only in a dedicated browser profile outside the
repository. Raw vendor downloads belong below the root-gitignored ``sis/``
directory. The initial command surface deliberately implements and verifies
authentication before bulk export logic is enabled.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence


BASE_URL = "https://pro.sisdatahub.com"
NFL_LEADERS_URL = f"{BASE_URL}/NFL/Leaders/Players"
AUTH_HOST = "auth.sportsinfosolutions.com"
MIN_API_REQUESTS_PER_EXPORT = 4


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    main_tab: str
    subtab: str | None
    metric_group: int
    subtype: float | int
    priority: int
    rationale: str


def _family(
    stem: str,
    main_tab: str,
    metric_group: int,
    priority: int,
    rationale: str,
) -> tuple[ReportDefinition, ...]:
    names = (("totals", 1, "Total"), ("rates", 2, "Rates"), ("value", 3, "Value"))
    prefixes = {
        "passing": ("passTotalTabNFL", "passRatesTabNFL", "passValuesTabNFL"),
        "rushing": ("rushingTotalTabNFL", "rushRatesTabNFL", "rushValuesTabNFL"),
        "receiving": ("recTotalTabNFL", "recRatesTabNFL", "recValuesTabNFL"),
        "pass-defense": (
            "passdefTotalTabNFL", "passdefRatesTabNFL", "passdefValuesTabNFL"),
        "pass-rush": (
            "passrushTotalTabNFL", "passrushRatesTabNFL", "passrushValuesTabNFL"),
        "run-defense": (
            "rundefTotalTabNFL", "rundefRatesTabNFL", "rundefValuesTabNFL"),
        "blocking": ("blockTotalTab", "blockRatesTab", "blockValuesTabNFL"),
    }
    tabs = prefixes[stem]
    return tuple(
        ReportDefinition(
            f"{stem}-{name}", main_tab, tabs[index - 1], metric_group,
            metric_group + index / 10, priority if name == "value" else priority + 1,
            f"{rationale} ({label.lower()} view).",
        )
        for name, index, label in names
    )


REPORTS: dict[str, ReportDefinition] = {
    report.key: report
    for report in (
        *_family("passing", "passTab", 1, 1, "QB/team efficiency and tail quality"),
        *_family("rushing", "rushTab", 3, 2, "RB/team efficiency and contact quality"),
        *_family("receiving", "receiveTab", 5, 1, "Routes, target quality and receiver value"),
        *_family("pass-defense", "passdefTab", 9, 1, "Coverage volume, quality and value"),
        *_family("pass-rush", "passrushTab", 10, 1, "Pressure creation and defensive value"),
        *_family("run-defense", "rundefTab", 11, 2, "Run-front quality and defensive value"),
        *_family("blocking", "blocktab", 14, 1, "Pass/run blocking quality and value"),
        ReportDefinition(
            "returning-totals", "returnTab", None, 12, 12, 3,
            "Lower-priority special-teams return volume"),
        ReportDefinition(
            "punting-totals", "puntTab", None, 13, 13, 3,
            "Lower-priority field-position and DST context"),
        ReportDefinition(
            "kicking-totals", "kickTab", None, 8, 8, 3,
            "Lower-priority kicker and scoring-opportunity context"),
        ReportDefinition(
            "runs-to-gap-totals", "runtogapTab", "runsToGapTotalTab",
            15, 15.1, 2,
            "Designed gap, bounce behavior and yards-before-contact volume"),
        ReportDefinition(
            "runs-to-gap-rates", "runtogapTab", "runsToGapRatesTab",
            15, 15.2, 3,
            "Designed gap, bounce behavior and yards-before-contact rates"),
        ReportDefinition(
            "runs-to-gap-value", "runtogapTab", "runsToGapValuesTab",
            15, 15.3, 2,
            "Designed gap and blocking-result value"),
        ReportDefinition(
            "adjusted-blown-blocks", "adjBlownBlockTab", None, 17, 17, 2,
            "Pass/run blown blocks adjusted for blocking opportunity"),
    )
}


@dataclass(frozen=True)
class ExportSpec:
    entity: str
    report: str
    season: int
    start_week: int
    end_week: int
    split_by_game: bool = True
    team_id: int | None = None

    @property
    def definition(self) -> ReportDefinition:
        return REPORTS[self.report]


class RowCapError(RuntimeError):
    """The normal UI returned exactly the paid-account row limit."""


@dataclass
class APIRequestBudget:
    ceiling: int
    used: int = 0
    state_path: Path | None = None
    plan_sha256: str | None = None

    def persist(self) -> None:
        if self.state_path is None:
            return
        payload = {
            "schema_version": 1,
            "plan_sha256": self.plan_sha256,
            "ceiling": self.ceiling,
            "used": self.used,
            "updated_at_utc": datetime.now(UTC).isoformat(),
        }
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".partial")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)

    def route(self, route: Any) -> None:
        if self.used >= self.ceiling:
            route.abort("blockedbyclient")
            return
        self.used += 1
        self.persist()
        route.continue_()


def validate_spec(spec: ExportSpec) -> None:
    if spec.entity not in {"players", "teams"}:
        raise ValueError("entity must be players or teams")
    if spec.report not in REPORTS:
        raise ValueError(f"unknown SIS report: {spec.report!r}")
    if not 2015 <= spec.season <= 2100:
        raise ValueError("SIS season must be at least 2015")
    if not 1 <= spec.start_week <= spec.end_week <= 22:
        raise ValueError("SIS week range must be within 1..22")
    if spec.team_id is not None and spec.team_id < 1:
        raise ValueError("SIS team_id must be positive")


def artifact_name(spec: ExportSpec) -> str:
    validate_spec(spec)
    team = f"__team-{spec.team_id}" if spec.team_id is not None else "__all-teams"
    grain = "game" if spec.split_by_game else "aggregate"
    return (
        f"{spec.entity}__{spec.report}__season-{spec.season}"
        f"__weeks-{spec.start_week:02d}-{spec.end_week:02d}{team}__{grain}.csv"
    )


def load_plan(path: Path) -> list[ExportSpec]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("SIS plan schema_version must be 1")
    exports = payload.get("exports")
    if not isinstance(exports, list) or not exports:
        raise ValueError("SIS plan exports must be a non-empty list")
    specs: list[ExportSpec] = []
    names: set[str] = set()
    for item in exports:
        if not isinstance(item, dict):
            raise ValueError("SIS plan exports must contain objects")
        entity = item["entity"]
        seasons = item.get("seasons")
        if seasons is None:
            seasons = [item["season"]]
        windows = item.get("week_windows")
        if windows is None:
            windows = [[item["start_week"], item["end_week"]]]
        if not isinstance(seasons, list) or not seasons:
            raise ValueError("SIS plan seasons must be a non-empty list")
        if not isinstance(windows, list) or not windows:
            raise ValueError("SIS plan week_windows must be a non-empty list")
        reports = item.get("reports")
        if not isinstance(reports, list) or not reports:
            raise ValueError("SIS plan export reports must be non-empty")
        team_ids = item.get("team_ids", [None])
        if not isinstance(team_ids, list) or not team_ids:
            raise ValueError("SIS plan team_ids must be a non-empty list")
        for season in seasons:
            for window in windows:
                if not isinstance(window, list) or len(window) != 2:
                    raise ValueError("SIS plan week windows must be [start, end]")
                for report in reports:
                    for team_id in team_ids:
                        spec = ExportSpec(
                            entity=entity, report=report, season=int(season),
                            start_week=int(window[0]), end_week=int(window[1]),
                            split_by_game=bool(item.get("split_by_game", True)),
                            team_id=team_id,
                        )
                        name = artifact_name(spec)
                        if name in names:
                            raise ValueError(
                                f"duplicate SIS planned artifact: {name}")
                        names.add(name)
                        specs.append(spec)
    budget = int(payload.get("max_exports", payload.get("max_queries", len(specs))))
    if len(specs) > budget:
        raise ValueError(
            f"SIS plan expands to {len(specs)} exports, above max_exports={budget}"
        )
    return specs


def plan_request_ceiling(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    ceiling = int(payload.get("max_api_requests", 0))
    if ceiling < 1 or ceiling > 1_000:
        raise ValueError("SIS plan max_api_requests must be within 1..1000")
    return ceiling


def default_profile_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "nfl-dfs" / "sis-playwright"


def default_storage_state_path(profile_dir: Path) -> Path:
    """Sensitive Playwright state, colocated with the external browser profile."""
    return profile_dir.parent / "sis-playwright-storage-state.json"


def _authenticated_url(url: str) -> bool:
    return url.startswith(BASE_URL) and AUTH_HOST not in url


def _assert_authenticated(page: object, timeout_ms: int) -> None:
    try:
        page.wait_for_url(
            re.compile(r"^https://pro\.sisdatahub\.com/(?:NFL(?:/.*)?|$)"),
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )
    except Exception as exc:
        raise RuntimeError(
            f"SIS login did not reach the authenticated NFL site (url={page.url})"
        ) from exc
    if not _authenticated_url(page.url):
        raise RuntimeError(f"SIS session is not authenticated (url={page.url})")


def _login_with_terminal_credentials(page: object, timeout_ms: int) -> None:
    print("Credentials are used only to fill the open browser and are not logged or saved.")
    email = input("SIS email: ").strip()
    password = getpass.getpass("SIS password (input hidden): ")
    if not email or not password:
        raise RuntimeError("email and password are required")

    email_input = page.locator("#Email, input[name='Email'], input[type='email']")
    password_input = page.locator(
        "#Password, input[name='Password'], input[type='password']"
    )
    try:
        email_input.first.wait_for(state="visible", timeout=timeout_ms)
        password_input.first.wait_for(state="visible", timeout=timeout_ms)
    except Exception as exc:
        raise RuntimeError(
            "SIS login form did not become ready "
            f"(url={page.url}, email_fields={email_input.count()}, "
            f"password_fields={password_input.count()})"
        ) from exc
    email_input.first.fill(email)
    password_input.first.fill(password)
    del password

    remember = page.locator("#RememberLogin, input[name='RememberLogin'][type='checkbox']")
    if remember.count() and remember.first.is_visible() and not remember.first.is_checked():
        remember.first.check()
    submit = page.locator("#login, input[name='submit'][type='submit']")
    if not submit.count() or not submit.first.is_visible():
        raise RuntimeError("SIS login submit control is missing")
    submit.first.click()
    _assert_authenticated(page, timeout_ms)


def interactive_login(
    profile_dir: Path,
    timeout_seconds: float,
    *,
    terminal_credentials: bool = False,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('install browser support with `pip install -e ".[browser]"`') from exc

    timeout_ms = int(timeout_seconds * 1000)
    state_path = default_storage_state_path(profile_dir)
    with sync_playwright() as playwright:
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            accept_downloads=True,
            viewport={"width": 1800, "height": 1200},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(NFL_LEADERS_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            if _authenticated_url(page.url):
                print("The saved SIS browser profile is already authenticated.")
            elif terminal_credentials:
                _login_with_terminal_credentials(page, timeout_ms)
            else:
                print("Sign in to SIS in the opened browser.")
                input(
                    "After the NFL Player Leaderboards page is visible, "
                    "press Enter here to verify and save the session: "
                )
                _assert_authenticated(page, timeout_ms)
            # Reload the protected URL to prove the persistent cookie/session,
            # rather than accepting a transient login callback page.
            page.goto(NFL_LEADERS_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            _assert_authenticated(page, timeout_ms)
            # SIS's identity cookie is session-scoped even with Remember Login.
            # Chromium removes it on a clean persistent-context shutdown, so
            # preserve Playwright storage state explicitly outside the repo.
            # This captures the already-authenticated session, never the
            # plaintext credentials.
            context.storage_state(path=str(state_path))
            print("SIS login completed and the persistent session was verified.")
        finally:
            context.close()


def verify_login(profile_dir: Path, timeout_seconds: float) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('install browser support with `pip install -e ".[browser]"`') from exc
    timeout_ms = int(timeout_seconds * 1000)
    state_path = default_storage_state_path(profile_dir)
    if not state_path.is_file():
        raise RuntimeError(
            "SIS saved storage state is missing; run "
            "`sis-download login --terminal-credentials`"
        )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(state_path), viewport={"width": 1800, "height": 1200}
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(NFL_LEADERS_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            _assert_authenticated(page, timeout_ms)
            heading = page.get_by_text("Player Leaderboards", exact=True)
            heading.first.wait_for(state="visible", timeout=timeout_ms)
            print(f"SIS session verified: {page.url}")
        except Exception as exc:
            raise RuntimeError(
                "SIS saved session is missing, expired, or cannot load Player Leaderboards; "
                "run `sis-download login`"
            ) from exc
        finally:
            context.close()
            browser.close()


def _set_select(page: Any, selector: str, value: str) -> None:
    """Set a styled native SIS select, including controls hidden by CSS."""
    retained = page.locator(selector).evaluate(
        """(element, value) => {
          const option = [...element.options].find(item => item.value === value);
          if (!option) return false;
          element.value = value;
          element.dispatchEvent(new Event('change', {bubbles: true}));
          return element.value === value;
        }""",
        value,
    )
    if not retained:
        raise RuntimeError(f"SIS filter {selector} has no value {value!r}")


def _set_checkbox(page: Any, selector: str, checked: bool) -> None:
    retained = page.locator(selector).evaluate(
        """(element, checked) => {
          element.checked = checked;
          element.dispatchEvent(new Event('change', {bubbles: true}));
          return element.checked === checked;
        }""",
        checked,
    )
    if not retained:
        raise RuntimeError(f"SIS filter {selector} did not retain {checked}")


def _click_ui_control(page: Any, selector: str) -> None:
    """Activate a SIS control, including submenu links hidden until hover."""
    control = page.locator(selector)
    control.wait_for(state="attached")
    if control.is_visible():
        control.click()
    else:
        # SIS implements hover menus as ordinary anchors with click handlers.
        # Dispatch that same DOM click; all request/response and rendered-table
        # checks below continue to apply.
        control.evaluate("element => element.click()")


def _request_scope(request: Any) -> dict[str, list[str]]:
    from urllib.parse import parse_qs

    return parse_qs(request.post_data or "", keep_blank_values=True)


def _api_rows(response: Any, stage: str) -> list[dict[str, Any]]:
    if response.status != 200:
        raise RuntimeError(f"SIS {stage} query returned HTTP {response.status}")
    try:
        payload = response.json()
    except Exception as exc:
        content_type = response.header_value("content-type") or "unknown"
        raise RuntimeError(
            f"SIS {stage} query returned non-JSON content ({content_type})"
        ) from exc
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError(f"SIS {stage} query response has invalid data rows")
    return rows


def _response_matches_spec(response: Any, spec: ExportSpec) -> bool:
    if f"/api/v1/nfl/{spec.entity}/query" not in response.url:
        return False
    scope = _request_scope(response.request)
    expected = {
        "MetricGroup": [str(spec.definition.metric_group)],
        "TimeFilters.SeasonFrom": [str(spec.season)],
        "TimeFilters.SeasonTo": [str(spec.season)],
        "TimeFilters.StartWeek": [str(spec.start_week)],
        "TimeFilters.EndWeek": [str(spec.end_week)],
    }
    if any(scope.get(key) != value for key, value in expected.items()):
        return False
    if spec.split_by_game and scope.get("TimeFilters.ByGame") != ["1"]:
        return False
    if not spec.split_by_game and "TimeFilters.ByGame" in scope:
        return False
    if spec.team_id is not None and scope.get("GameFilters.Team") != [
        str(spec.team_id)
    ]:
        return False
    return True


def _assert_api_scope(response: Any, spec: ExportSpec, row_cap: int) -> int:
    rows = _api_rows(response, "submitted")
    if len(rows) == row_cap:
        raise RowCapError(
            f"SIS query returned exactly the paid row cap ({row_cap}); "
            "split into narrower team or week queries"
        )
    for row in rows:
        if int(row.get("season", -1)) != spec.season:
            raise RuntimeError("SIS API returned an unexpected season")
        week = int(row.get("week", -1))
        if spec.split_by_game and not spec.start_week <= week <= spec.end_week:
            raise RuntimeError("SIS API returned a row outside the requested weeks")
        if spec.split_by_game and int(row.get("games", -1)) != 1:
            raise RuntimeError("SIS split-by-game API row does not have Games=1")
        if spec.team_id is not None and int(row.get("teamId", -1)) != spec.team_id:
            raise RuntimeError("SIS API returned an unexpected team")
    return len(rows)


def _identity_rows(response: Any) -> list[dict[str, Any]]:
    """Retain stable SIS IDs and human-readable join keys omitted by CSV."""
    rows = _api_rows(response, "submitted identity")
    descriptive = {
        "season", "week", "games", "player", "team", "opp", "opponent",
        "pos", "position", "name",
    }
    identities: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("SIS query response contains a non-object row")
        identities.append({
            key: row[key]
            for key in sorted(row)
            if key in descriptive or key.lower().endswith("id")
        })
    return identities


def _wait_for_table(page: Any, expected_rows: int, timeout_ms: int) -> None:
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        try:
            current = int(page.evaluate(
                "typeof dataTbl === 'undefined' ? -1 : dataTbl.data().count()"
            ))
        except Exception:
            current = -1
        if current == expected_rows:
            return
        page.wait_for_timeout(200)
    raise RuntimeError(
        f"SIS rendered table has not reached the API row count {expected_rows}"
    )


def _read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2 or len(rows[0]) < 2:
        raise RuntimeError(f"SIS download is not a populated CSV: {path}")
    return rows


def _validate_csv_scope(path: Path, spec: ExportSpec, expected_rows: int) -> None:
    rows = _read_csv(path)
    header = rows[0]
    if len(rows) - 1 != expected_rows:
        raise RuntimeError(
            f"SIS CSV has {len(rows) - 1} rows; API returned {expected_rows}"
        )
    season_column = next(
        (column for column in ("Season", "Year") if column in header), None)
    required: set[str] = set()
    if season_column is None:
        required.add("Season or Year")
    if spec.split_by_game:
        # Rates/value views deliberately omit Games from their visible CSV,
        # although the API row still carries Games=1. Week + opponent prove
        # the CSV's game grain; validate Games too whenever it is exported.
        required.update({"Week", "Opp."})
    missing = required - set(header)
    if missing:
        raise RuntimeError(
            f"SIS CSV lacks scope columns: {sorted(missing)}; "
            f"exported columns={header}"
        )
    season_index = header.index(season_column)
    if {int(row[season_index]) for row in rows[1:]} != {spec.season}:
        raise RuntimeError("SIS CSV contains an unexpected season")
    if spec.split_by_game:
        week_index = header.index("Week")
        weeks = {int(row[week_index]) for row in rows[1:]}
        if min(weeks) < spec.start_week or max(weeks) > spec.end_week:
            raise RuntimeError("SIS CSV contains an unexpected week")
        if "Games" in header:
            games_index = header.index("Games")
            if {int(row[games_index]) for row in rows[1:]} != {1}:
                raise RuntimeError("SIS split-by-game CSV contains Games != 1")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_one(
    profile_dir: Path,
    timeout_seconds: float,
    output_dir: Path,
    spec: ExportSpec,
    *,
    row_cap: int = 200,
    request_budget: APIRequestBudget | None = None,
) -> dict[str, Any]:
    """Run one normal-UI SIS export and fail closed on ambiguous scope."""
    validate_spec(spec)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('install browser support with `pip install -e ".[browser]"`') from exc
    timeout_ms = int(timeout_seconds * 1000)
    state_path = default_storage_state_path(profile_dir)
    if not state_path.is_file():
        raise RuntimeError("SIS saved storage state is missing; run `sis-download login`")
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / artifact_name(spec)
    partial = destination.with_suffix(destination.suffix + ".partial")
    if destination.exists():
        raise RuntimeError(f"refusing to overwrite SIS artifact: {destination}")
    if partial.exists():
        raise RuntimeError(f"remove stale incomplete SIS artifact first: {partial}")
    url = f"{BASE_URL}/NFL/Leaders/{spec.entity.title()}"
    with sync_playwright() as playwright:
        requests_before = request_budget.used if request_budget is not None else 0
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(state_path), accept_downloads=True,
            viewport={"width": 1800, "height": 1200},
        )
        if request_budget is not None:
            context.route("**/api/v1/nfl/**/query", request_budget.route)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            _assert_authenticated(page, timeout_ms)
            page.locator("#querybuilder").wait_for(state="attached")
            # Clicking the family starts a request with its old scope. Wait
            # for that request so the later Submit response cannot be confused
            # with it, then apply every hidden/native filter deliberately.
            with page.expect_response(
                lambda response: (
                    f"/api/v1/nfl/{spec.entity}/query" in response.url
                    and _request_scope(response.request).get("MetricGroup")
                    == [str(spec.definition.metric_group)]
                ), timeout=timeout_ms,
            ):
                _click_ui_control(page, f"#{spec.definition.main_tab}")
            if spec.definition.subtab:
                # SIS's tab request is immediate but the UI replaces the
                # DataTable asynchronously. Wait for its own API response and
                # rendered row count before mutating filters for Submit.
                with page.expect_response(
                    lambda response: (
                        f"/api/v1/nfl/{spec.entity}/query" in response.url
                        and _request_scope(response.request).get("MetricGroup")
                        == [str(spec.definition.metric_group)]
                    ), timeout=timeout_ms,
                ) as subtab_response:
                    _click_ui_control(page, f"#{spec.definition.subtab}")
                subtab_rows = _api_rows(subtab_response.value, "report-view")
                _wait_for_table(page, len(subtab_rows), timeout_ms)
                active = page.locator(
                    f"#{spec.definition.subtab}"
                ).get_attribute("value")
                if active is not None and float(active) != float(spec.definition.subtype):
                    raise RuntimeError("SIS report view did not retain its declared subtype")
            _set_select(page, "#TimeFilters_SeasonFrom", str(spec.season))
            _set_select(page, "#TimeFilters_SeasonTo", str(spec.season))
            _set_select(page, "#TimeFilters_StartWeek", str(spec.start_week))
            _set_select(page, "#TimeFilters_EndWeek", str(spec.end_week))
            _set_select(
                page, "#Teams", str(spec.team_id) if spec.team_id is not None else "-1")
            _set_checkbox(page, "#chkIncludePlayoffs", False)
            _set_checkbox(page, "#chkByGame", spec.split_by_game)
            with page.expect_response(
                lambda response: _response_matches_spec(response, spec),
                timeout=timeout_ms,
            ) as response_info:
                page.locator("#submit").click()
            response = response_info.value
            expected_rows = _assert_api_scope(response, spec, row_cap)
            identities = _identity_rows(response)
            if expected_rows == 0:
                raise RuntimeError("SIS query returned no rows")
            _wait_for_table(page, expected_rows, timeout_ms)
            button = page.locator("a.dt-button.buttons-csv:visible")
            if button.count() != 1:
                raise RuntimeError("SIS page has an ambiguous Download control")
            with page.expect_download(timeout=timeout_ms) as download_info:
                button.click()
            download_info.value.save_as(str(partial))
        finally:
            context.close()
            browser.close()
    try:
        _validate_csv_scope(partial, spec, expected_rows)
    except Exception:
        # This file was created by this invocation and failed its declared
        # scope contract. Never leave it looking like an accepted raw input.
        partial.unlink(missing_ok=True)
        raise
    partial.replace(destination)
    return {
        "spec": asdict(spec),
        "definition": asdict(spec.definition),
        "artifact": destination.name,
        "rows": expected_rows,
        "bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "row_cap": row_cap,
        "identities": identities,
        "api_requests_used_total": (
            request_budget.used if request_budget is not None else None),
        "api_requests_for_artifact": (
            request_budget.used - requests_before
            if request_budget is not None else None),
    }


def _manifest_path(output_dir: Path, artifact: str) -> Path:
    return output_dir / (Path(artifact).stem + ".manifest.json")


def _verified_existing(output_dir: Path, spec: ExportSpec) -> bool:
    artifact = output_dir / artifact_name(spec)
    manifest = _manifest_path(output_dir, artifact.name)
    if not artifact.exists() and not manifest.exists():
        return False
    if not artifact.is_file() or not manifest.is_file():
        raise RuntimeError(f"incomplete existing SIS artifact pair: {artifact.name}")
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"invalid SIS manifest: {manifest}") from exc
    if payload.get("spec") != asdict(spec):
        raise RuntimeError(f"existing SIS manifest scope differs: {manifest}")
    if payload.get("sha256") != _sha256(artifact):
        raise RuntimeError(f"existing SIS artifact hash differs: {artifact}")
    _validate_csv_scope(artifact, spec, int(payload.get("rows", -1)))
    return True


def run_plan(
    profile_dir: Path,
    timeout_seconds: float,
    output_dir: Path,
    plan_path: Path,
    *,
    row_cap: int = 200,
) -> dict[str, int]:
    specs = load_plan(plan_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    ceiling = plan_request_ceiling(plan_path)
    plan_hash = _sha256(plan_path)
    state_path = output_dir / f".{plan_path.stem}.run-state.json"
    used = 0
    has_existing_artifacts = any(
        (output_dir / artifact_name(spec)).exists()
        or _manifest_path(output_dir, artifact_name(spec)).exists()
        for spec in specs
    )
    if has_existing_artifacts and not state_path.exists():
        raise RuntimeError(
            "SIS artifacts exist but their durable API-request state is missing; "
            "do not reset the weekly request counter implicitly"
        )
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"invalid SIS plan run state: {state_path}") from exc
        if state.get("plan_sha256") != plan_hash or int(
            state.get("ceiling", -1)
        ) != ceiling:
            raise RuntimeError(
                "SIS plan or request ceiling changed after execution began; "
                f"preserve and review {state_path} before starting a new tranche"
            )
        used = int(state.get("used", -1))
        if not 0 <= used <= ceiling:
            raise RuntimeError(f"invalid SIS API count in {state_path}: {used}")
    budget = APIRequestBudget(
        ceiling=ceiling, used=used, state_path=state_path, plan_sha256=plan_hash)
    budget.persist()
    completed = skipped = 0
    for index, spec in enumerate(specs, start=1):
        if _verified_existing(output_dir, spec):
            skipped += 1
            print(f"SIS plan {index}/{len(specs)} verified existing: {artifact_name(spec)}")
            continue
        if budget.ceiling - budget.used < MIN_API_REQUESTS_PER_EXPORT:
            raise RuntimeError(
                "SIS API-request ceiling has insufficient reserve for one guarded "
                f"export ({budget.used}/{budget.ceiling} used; "
                f"{MIN_API_REQUESTS_PER_EXPORT} required)"
            )
        result = export_one(
            profile_dir, timeout_seconds, output_dir, spec,
            row_cap=row_cap, request_budget=budget,
        )
        manifest = _manifest_path(output_dir, result["artifact"])
        if manifest.exists():
            raise RuntimeError(f"refusing to overwrite SIS manifest: {manifest}")
        manifest.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        completed += 1
        print(
            f"SIS plan {index}/{len(specs)} complete: {result['artifact']} "
            f"({result['rows']} rows; API requests {budget.used}/{budget.ceiling})"
        )
    return {
        "planned": len(specs), "completed": completed, "skipped": skipped,
        "api_requests": budget.used, "api_request_ceiling": budget.ceiling,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sis-download",
        description="Auditable Playwright acquisition from SIS DataHub Pro",
    )
    parser.add_argument("--profile-dir", type=Path, default=default_profile_dir())
    parser.add_argument("--timeout", type=float, default=120.0)
    subparsers = parser.add_subparsers(dest="command", required=True)
    login = subparsers.add_parser("login", help="open a persistent browser for one-time login")
    login.add_argument(
        "--terminal-credentials",
        action="store_true",
        help="prompt securely in the terminal and fill the browser automatically",
    )
    subparsers.add_parser("verify-login", help="headlessly verify the saved SIS session")
    subparsers.add_parser(
        "catalog", help="list inventoried SIS NFL report views and priorities")
    export = subparsers.add_parser(
        "export", help="download one guarded SIS NFL report through the normal UI")
    export.add_argument("--entity", choices=("players", "teams"), required=True)
    export.add_argument("--report", choices=sorted(REPORTS), required=True)
    export.add_argument("--season", type=int, required=True)
    export.add_argument("--start-week", type=int, required=True)
    export.add_argument("--end-week", type=int, required=True)
    export.add_argument("--team-id", type=int)
    export.add_argument(
        "--aggregate", action="store_true",
        help="aggregate the requested window instead of one row per game",
    )
    export.add_argument("--row-cap", type=int, default=200)
    export.add_argument("--output-dir", type=Path, default=Path("sis/downloads"))
    plan = subparsers.add_parser(
        "plan", help="validate and summarize a declarative SIS query plan")
    plan.add_argument("--file", type=Path, required=True)
    run = subparsers.add_parser(
        "run-plan", help="resumably execute a guarded SIS query plan")
    run.add_argument("--file", type=Path, required=True)
    run.add_argument("--row-cap", type=int, default=200)
    run.add_argument("--output-dir", type=Path, default=Path("sis/downloads"))
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
        elif args.command == "verify-login":
            verify_login(args.profile_dir, args.timeout)
        elif args.command == "catalog":
            for definition in sorted(
                REPORTS.values(), key=lambda item: (item.priority, item.key)):
                print(
                    f"P{definition.priority} {definition.key}: "
                    f"{definition.rationale}"
                )
        elif args.command == "plan":
            specs = load_plan(args.file)
            ceiling = plan_request_ceiling(args.file)
            print(
                f"SIS plan valid: {len(specs)} guarded exports; "
                f"hard API-request ceiling {ceiling}"
            )
            for spec in specs:
                print(artifact_name(spec))
        elif args.command == "run-plan":
            summary = run_plan(
                args.profile_dir, args.timeout, args.output_dir, args.file,
                row_cap=args.row_cap,
            )
            print("SIS plan complete: " + json.dumps(summary, sort_keys=True))
        else:
            spec = ExportSpec(
                entity=args.entity,
                report=args.report,
                season=args.season,
                start_week=args.start_week,
                end_week=args.end_week,
                split_by_game=not args.aggregate,
                team_id=args.team_id,
            )
            result = export_one(
                args.profile_dir, args.timeout, args.output_dir, spec,
                row_cap=args.row_cap,
            )
            manifest = args.output_dir / (
                Path(result["artifact"]).stem + ".manifest.json")
            if manifest.exists():
                raise RuntimeError(f"refusing to overwrite SIS manifest: {manifest}")
            manifest.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(
                f"SIS export complete: {result['artifact']} "
                f"({result['rows']} rows; manifest {manifest.name})"
            )
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
