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
SIS_LOGOUT_URL = f"{BASE_URL}/Home/SignoutOidc"
AUTH_HOST = "auth.sportsinfosolutions.com"
MIN_API_REQUESTS_PER_EXPORT = 4

# View identity cannot be inferred from row count or season/week scope. SIS's
# submenu anchors do not consistently write MetricGroupSubType themselves, and
# a stale DataTables export can therefore look complete while carrying another
# view's columns. These small schema signatures fail closed on that condition.
CSV_REQUIRED_COLUMNS: dict[str, frozenset[str]] = {
    "passing-totals": frozenset(("Games", "Dropbacks", "Gross Yds")),
    "passing-value": frozenset(("Points Earned", "PE Per Play", "Boom%", "Bust%")),
    "rushing-totals": frozenset(("Games", "YAContact", "Hit at Line")),
    "rushing-value": frozenset(("Points Earned", "PE Per Play", "Boom%", "Bust%")),
    "receiving-totals": frozenset(("Games", "Routes", "Tgts")),
    "pass-defense-totals": frozenset(("Games", "Catchable", "Pass Def.")),
    "pass-defense-value": frozenset(("Points Saved", "PS Per Play", "Boom%", "Bust%")),
    "pass-rush-totals": frozenset(("Games", "Pressures", "Passes Batted")),
    "pass-rush-value": frozenset(("Points Saved", "PS Per Play", "PAR", "WAR")),
    "run-defense-totals": frozenset(("Games", "Tackle Broken", "TFL")),
    "run-defense-value": frozenset(("Points Saved", "PS Per Play", "Boom%", "Bust%")),
    "blocking-totals": frozenset(("Games", "PassSnap", "RushSnap")),
    "blocking-value": frozenset(("Points Earned", "PE Per Play", "PAR", "WAR")),
}

ALIGNMENT_SAMPLE_SLICES = (
    ("receiving", "ReceivingFilters.RecAlignment", ("1",), "left"),
    ("receiving", "ReceivingFilters.RecAlignment", ("2", "5"), "slot"),
    ("receiving", "ReceivingFilters.RecAlignment", ("6",), "right"),
    ("pass-defense", "PassDefenseFilters.DefenderLinedUp", ("1",), "lcb"),
    ("pass-defense", "PassDefenseFilters.DefenderLinedUp", ("2",), "rcb"),
    ("pass-defense", "PassDefenseFilters.DefenderLinedUp", ("3",), "scb"),
)

TEAM_PASS_DEFENSE_PROFILE_SLICES = (
    ("wide-man", ("2",), ("0", "1", "5")),
    ("wide-zone", ("2",), ("2", "3", "4", "6")),
    ("slot-man", ("3",), ("0", "1", "5")),
    ("slot-zone", ("3",), ("2", "3", "4", "6")),
)
TEAM_PASS_DEFENSE_PROFILE_REPORTS = (
    "pass-defense-totals",
    "pass-defense-value",
)
ASOE_SEASONS = (2022, 2023, 2024, 2025)
ASOE_WINDOWS = ((1, 6), (7, 12), (13, 17))
ASOE_ALIGNMENTS = (("wide", ("2",)), ("slot", ("3",)))
# Retain the normal UI's DOM serialization order. The values are the complete
# frozen set; request-scope checks deliberately compare the actual form order.
ASOE_ALL_SCHEMES = ("0", "1", "2", "5", "3", "4", "6")
ASOE_API_REQUEST_CEILING = 28
PASS_TAIL_WEEKLY_VERSION = "prospective-sis-pass-tail-weekly-acquisition-v1"
PASS_TAIL_WEEKLY_API_REQUEST_CEILING = 7
PLAYER_PASS_DEFENSE_GRAIN_VERSION = (
    "20260815-sis-player-pass-defense-grain-feasibility-v1"
)
PLAYER_PASS_DEFENSE_GRAIN_FILTERS = {
    "PassDefenseFilters.DefenderPos": ["12"],
    "PassDefenseFilters.ReceiverPos": ["4"],
    "PassDefenseFilters.TargetLinedUp": ["2"],
    "PassDefenseFilters.MinTargets": ["0"],
    "PassDefenseFilters.MinAttempts": ["0"],
}
PLAYER_PASS_DEFENSE_GRAIN_API_REQUEST_CEILING = 3


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


@dataclass
class SubmitOnlyAPIRequestBudget:
    """Block incidental UI refreshes and meter only an explicitly armed Submit."""

    budget: APIRequestBudget
    armed: bool = False

    def route(self, route: Any) -> None:
        if not self.armed:
            route.abort("blockedbyclient")
            return
        self.budget.route(route)


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
    force_fresh: bool = False,
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
            if force_fresh:
                if _authenticated_url(page.url):
                    page.goto(
                        SIS_LOGOUT_URL,
                        wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )
                context.clear_cookies()
                state_path.unlink(missing_ok=True)
                page.goto(
                    NFL_LEADERS_URL,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                if _authenticated_url(page.url):
                    raise RuntimeError("SIS forced logout did not end the saved session")
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


def _set_checkbox_values(page: Any, name: str, values: Sequence[str]) -> None:
    """Select an exact subset of one SIS checkbox group."""
    retained = page.locator(f'input[name="{name}"]').evaluate_all(
        """(elements, values) => {
          const wanted = new Set(values);
          for (const element of elements) {
            const checked = wanted.has(element.value);
            if (element.checked !== checked) {
              element.checked = checked;
              element.dispatchEvent(new Event('change', {bubbles: true}));
            }
          }
          return elements.filter(element => element.checked)
            .map(element => element.value).sort();
        }""",
        list(values),
    )
    if retained != sorted(values):
        raise RuntimeError(
            f"SIS checkbox group {name} retained {retained}, expected {sorted(values)}"
        )


def _set_input_value(page: Any, name: str, value: str) -> None:
    retained = page.locator(f'input[name="{name}"]').evaluate(
        """(element, value) => {
          element.value = value;
          element.dispatchEvent(new Event('change', {bubbles: true}));
          return element.value;
        }""",
        value,
    )
    if retained != value:
        raise RuntimeError(
            f"SIS input {name} retained {retained!r}, expected {value!r}"
        )


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


def _select_report_subtype(page: Any, definition: ReportDefinition) -> None:
    """Bind the hidden subtype to the visible submenu choice before clicking.

    Several SIS submenu anchors advertise their subtype in ``value`` but omit
    the corresponding ``setMetricGroupSubType`` call from ``onclick``. Setting
    the page's own hidden form control from that visible value is equivalent to
    retaining the user's menu selection and keeps the subsequent Submit on the
    ordinary UI path.
    """
    if not definition.subtab:
        return
    control = page.locator(f"#{definition.subtab}")
    control.wait_for(state="attached")
    advertised = control.get_attribute("value")
    if advertised is None or float(advertised) != float(definition.subtype):
        raise RuntimeError("SIS report submenu does not advertise its subtype")
    retained = page.locator("#MetricGroupSubType").evaluate(
        """(element, value) => {
          element.value = value;
          element.dispatchEvent(new Event('change', {bubbles: true}));
          return element.value === value;
        }""",
        str(definition.subtype),
    )
    if not retained:
        raise RuntimeError("SIS report subtype did not retain the menu value")


def _select_report_without_refresh(page: Any, definition: ReportDefinition) -> None:
    """Set the exact visible menu identities for the next normal UI Submit.

    This is the query-budget recovery path: the report menu controls advertise
    the same group/subtype values that their click handlers write, but clicking
    each one spends an intermediate query whose rows are not used.
    """
    main = page.locator(f"#{definition.main_tab}")
    main.wait_for(state="attached")
    advertised_group = main.get_attribute("value")
    if advertised_group is not None and float(advertised_group) != float(
        definition.metric_group
    ):
        raise RuntimeError("SIS report menu does not advertise its metric group")
    retained = page.locator("#MetricGroup").evaluate(
        """(element, value) => {
          element.value = value;
          element.dispatchEvent(new Event('change', {bubbles: true}));
          return element.value === value;
        }""",
        str(definition.metric_group),
    )
    if not retained:
        raise RuntimeError("SIS report group did not retain the menu value")
    _select_report_subtype(page, definition)


def _activate_report_view_without_refresh(
    page: Any, definition: ReportDefinition,
) -> None:
    """Activate SIS's visible subtype tab while API refreshes stay blocked.

    The normal Submit serializer derives ``MetricGroupSubType`` from the active
    ``li`` in the report-family tab list, not only from the hidden input. SIS's
    subtype click handler also attempts an incidental API refresh; callers must
    keep a ``SubmitOnlyAPIRequestBudget`` route disarmed while using this helper.
    """
    _select_report_without_refresh(page, definition)
    if not definition.subtab:
        return
    control = page.locator(f"#{definition.subtab}")
    control.wait_for(state="attached")
    control.evaluate("element => element.click()")
    parent_class = control.evaluate("element => element.parentElement.className")
    if "active" not in str(parent_class).split():
        raise RuntimeError("SIS report subtype tab did not become active")
    retained = page.locator("#MetricGroupSubType").input_value()
    if float(retained) != float(definition.subtype):
        raise RuntimeError("SIS active report subtype differs from hidden scope")


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
        "MetricGroupSubType": [str(spec.definition.subtype)],
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


def _response_matches_filters(
    response: Any, spec: ExportSpec, filters: dict[str, list[str]],
) -> bool:
    if not _response_matches_spec(response, spec):
        return False
    scope = _request_scope(response.request)
    return all(scope.get(name) == values for name, values in filters.items())


def _assert_submitted_scope(
    response: Any, spec: ExportSpec, filters: dict[str, list[str]],
) -> None:
    """Fail immediately with the exact request-scope difference."""
    scope = _request_scope(response.request)
    expected = {
        "MetricGroup": [str(spec.definition.metric_group)],
        "MetricGroupSubType": [str(spec.definition.subtype)],
        "TimeFilters.SeasonFrom": [str(spec.season)],
        "TimeFilters.SeasonTo": [str(spec.season)],
        "TimeFilters.StartWeek": [str(spec.start_week)],
        "TimeFilters.EndWeek": [str(spec.end_week)],
        **filters,
    }
    if spec.split_by_game:
        expected["TimeFilters.ByGame"] = ["1"]
    if spec.team_id is not None:
        expected["GameFilters.Team"] = [str(spec.team_id)]
    differences = {
        name: {"expected": values, "actual": scope.get(name)}
        for name, values in expected.items()
        if scope.get(name) != values
    }
    if differences:
        raise RuntimeError(
            "SIS submitted scope differs: "
            + json.dumps(differences, sort_keys=True)
        )


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


def _wait_for_table(
    page: Any,
    expected_rows: int,
    timeout_ms: int,
    expected_columns: frozenset[str] = frozenset(),
) -> None:
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        try:
            state = page.evaluate(
                "typeof dataTbl === 'undefined' ? -1 : dataTbl.data().count()"
            )
            current = int(state)
            headers = set(page.evaluate(
                """typeof dataTbl === 'undefined' ? [] :
                [...dataTbl.table().header().querySelectorAll('th')]
                  .map(element => element.innerText.trim())"""
            ))
        except Exception:
            current = -1
            headers = set()
        if current == expected_rows and expected_columns <= headers:
            return
        page.wait_for_timeout(200)
    raise RuntimeError(
        "SIS rendered table has not reached the submitted response state: "
        f"rows={expected_rows}, required columns={sorted(expected_columns)}"
    )


def _read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2 or len(rows[0]) < 2:
        raise RuntimeError(f"SIS download is not a populated CSV: {path}")
    return rows


def _csv_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle), [])
    if len(header) < 2:
        raise RuntimeError(f"SIS download has no usable CSV header: {path}")
    return header


def _validate_csv_scope(path: Path, spec: ExportSpec, expected_rows: int) -> None:
    rows = _read_csv(path)
    header = rows[0]
    required_view = CSV_REQUIRED_COLUMNS.get(spec.report, frozenset())
    if missing_view := required_view - set(header):
        raise RuntimeError(
            f"SIS CSV view differs from {spec.report}: missing "
            f"{sorted(missing_view)}; exported columns={header}"
        )
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


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


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
                _select_report_subtype(page, spec.definition)
                with page.expect_response(
                    lambda response: (
                        f"/api/v1/nfl/{spec.entity}/query" in response.url
                        and _request_scope(response.request).get(
                            "MetricGroup") == [str(spec.definition.metric_group)]
                        and _request_scope(response.request).get(
                            "MetricGroupSubType") == [str(spec.definition.subtype)]
                    ), timeout=timeout_ms,
                ) as subtab_response:
                    _click_ui_control(page, f"#{spec.definition.subtab}")
                subtab_rows = _api_rows(subtab_response.value, "report-view")
                _wait_for_table(
                    page, len(subtab_rows), timeout_ms,
                    CSV_REQUIRED_COLUMNS.get(spec.report, frozenset()))
                active = page.locator("#MetricGroupSubType").input_value()
                if float(active) != float(spec.definition.subtype):
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
            _wait_for_table(
                page, expected_rows, timeout_ms,
                CSV_REQUIRED_COLUMNS.get(spec.report, frozenset()))
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


def _alignment_sample_artifact(slice_name: str) -> str:
    return f"2025-week01-ari-no__{slice_name}.csv"


def _prepare_sample_report(
    page: Any, spec: ExportSpec, timeout_ms: int,
) -> None:
    """Select one report and its frozen game/team scope on an existing page."""
    with page.expect_response(
        lambda response: (
            f"/api/v1/nfl/{spec.entity}/query" in response.url
            and _request_scope(response.request).get("MetricGroup")
            == [str(spec.definition.metric_group)]
        ), timeout=timeout_ms,
    ):
        _click_ui_control(page, f"#{spec.definition.main_tab}")
    _select_report_subtype(page, spec.definition)
    if spec.definition.subtab:
        with page.expect_response(
            lambda response: (
                f"/api/v1/nfl/{spec.entity}/query" in response.url
                and _request_scope(response.request).get("MetricGroup")
                == [str(spec.definition.metric_group)]
                and _request_scope(response.request).get("MetricGroupSubType")
                == [str(spec.definition.subtype)]
            ), timeout=timeout_ms,
        ) as response_info:
            _click_ui_control(page, f"#{spec.definition.subtab}")
        rows = _api_rows(response_info.value, "alignment report-view")
        _wait_for_table(
            page, len(rows), timeout_ms,
            CSV_REQUIRED_COLUMNS.get(spec.report, frozenset()),
        )
    _set_select(page, "#TimeFilters_SeasonFrom", str(spec.season))
    _set_select(page, "#TimeFilters_SeasonTo", str(spec.season))
    _set_select(page, "#TimeFilters_StartWeek", str(spec.start_week))
    _set_select(page, "#TimeFilters_EndWeek", str(spec.end_week))
    _set_select(page, "#Teams", str(spec.team_id))
    _set_checkbox(page, "#chkIncludePlayoffs", False)
    _set_checkbox(page, "#chkByGame", True)


def run_alignment_feasibility_sample(
    profile_dir: Path,
    timeout_seconds: float,
    output_dir: Path,
) -> dict[str, Any]:
    """Acquire the frozen seven-slice ARI/NO alignment sample in one session."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('install browser support with `pip install -e ".[browser]"`') from exc
    protocol = Path("reports/2026-08-13-sis-alignment-feasibility-protocol.md")
    if not protocol.is_file():
        raise RuntimeError("frozen SIS alignment protocol is missing")
    state_path = default_storage_state_path(profile_dir)
    if not state_path.is_file():
        raise RuntimeError("SIS saved storage state is missing; run `sis-download login`")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_state = output_dir / ".alignment-feasibility.run-state.json"
    manifest_path = output_dir / "alignment-feasibility.manifest.json"
    result_path = output_dir / "alignment-feasibility.result.json"
    if manifest_path.exists() or result_path.exists():
        raise RuntimeError("refusing to overwrite SIS alignment sample result")
    if any((output_dir / _alignment_sample_artifact(row[3])).exists()
           for row in ALIGNMENT_SAMPLE_SLICES):
        raise RuntimeError("partial SIS alignment sample already exists")
    protocol_hash = _sha256(protocol)
    used = 0
    if run_state.exists():
        state = json.loads(run_state.read_text(encoding="utf-8"))
        if (state.get("plan_sha256") != protocol_hash
                or int(state.get("ceiling", -1)) != 12):
            raise RuntimeError("SIS alignment request state identity differs")
        used = int(state.get("used", -1))
        if not 0 <= used <= 12:
            raise RuntimeError("SIS alignment request state count is invalid")
    budget = APIRequestBudget(
        ceiling=12, used=used, state_path=run_state,
        plan_sha256=protocol_hash)
    budget.persist()
    submit_budget = SubmitOnlyAPIRequestBudget(budget)
    timeout_ms = int(timeout_seconds * 1000)
    artifacts: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(state_path), accept_downloads=True,
            viewport={"width": 1800, "height": 1200},
        )
        context.route("**/api/v1/nfl/**/query", submit_budget.route)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(NFL_LEADERS_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            _assert_authenticated(page, timeout_ms)
            page.locator("#querybuilder").wait_for(state="attached")
            current_family = None
            for family, filter_name, filter_values, slice_name in ALIGNMENT_SAMPLE_SLICES:
                if family != current_family:
                    spec = ExportSpec(
                        entity="players",
                        report=("receiving-totals" if family == "receiving"
                                else "pass-defense-totals"),
                        season=2025, start_week=1, end_week=1,
                        team_id=1 if family == "receiving" else 20,
                    )
                    # Use the report menu's declared group/subtype values and
                    # let the next visible Submit perform the only needed
                    # refresh. This avoids spending two intermediate queries
                    # per family and permits a fail-closed retry without
                    # resetting the durable 12-query counter.
                    _select_report_without_refresh(page, spec.definition)
                    _set_select(page, "#TimeFilters_SeasonFrom", "2025")
                    _set_select(page, "#TimeFilters_SeasonTo", "2025")
                    _set_select(page, "#TimeFilters_StartWeek", "1")
                    _set_select(page, "#TimeFilters_EndWeek", "1")
                    _set_select(page, "#Teams", str(spec.team_id))
                    _set_checkbox(page, "#chkIncludePlayoffs", False)
                    _set_checkbox(page, "#chkByGame", True)
                    if family == "receiving":
                        _set_checkbox_values(
                            page, "ReceivingFilters.TargetPos", ["4"])
                    else:
                        _set_checkbox_values(
                            page, "PassDefenseFilters.DefenderPos", ["12"])
                        _set_checkbox_values(
                            page, "PassDefenseFilters.ReceiverPos", ["4"])
                    current_family = family
                _set_checkbox_values(page, filter_name, filter_values)
                expected_filters = {filter_name: list(filter_values)}
                if family == "receiving":
                    expected_filters["ReceivingFilters.TargetPos"] = ["4"]
                else:
                    expected_filters.update({
                        "PassDefenseFilters.DefenderPos": ["12"],
                        "PassDefenseFilters.ReceiverPos": ["4"],
                    })
                submit_budget.armed = True
                try:
                    with page.expect_response(
                        lambda response, expected=expected_filters, current=spec:
                        _response_matches_filters(response, current, expected),
                        timeout=timeout_ms,
                    ) as response_info:
                        page.locator("#submit").click()
                finally:
                    submit_budget.armed = False
                response = response_info.value
                expected_rows = _assert_api_scope(response, spec, row_cap=200)
                if expected_rows == 0:
                    raise RuntimeError(f"SIS alignment slice {slice_name} is empty")
                _wait_for_table(
                    page, expected_rows, timeout_ms,
                    CSV_REQUIRED_COLUMNS[spec.report],
                )
                button = page.locator("a.dt-button.buttons-csv:visible")
                if button.count() != 1:
                    raise RuntimeError("SIS page has an ambiguous Download control")
                destination = output_dir / _alignment_sample_artifact(slice_name)
                partial = destination.with_suffix(destination.suffix + ".partial")
                with page.expect_download(timeout=timeout_ms) as download_info:
                    button.click()
                download_info.value.save_as(str(partial))
                try:
                    _validate_csv_scope(partial, spec, expected_rows)
                except Exception:
                    partial.unlink(missing_ok=True)
                    raise
                partial.replace(destination)
                artifacts.append({
                    "family": family, "filter_name": filter_name,
                    "filter_values": list(filter_values), "slice": slice_name,
                    "spec": asdict(spec), "artifact": destination.name,
                    "rows": expected_rows, "bytes": destination.stat().st_size,
                    "sha256": _sha256(destination),
                    "identities": _identity_rows(response),
                    "submitted_scope": _request_scope(response.request),
                })
        finally:
            context.close()
            browser.close()
    manifest = {
        "schema_version": 1,
        "protocol_sha256": _sha256(protocol),
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "api_requests_used": budget.used,
        "api_request_ceiling": budget.ceiling,
        "artifacts": artifacts,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = analyze_alignment_feasibility_sample(output_dir, manifest)
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def analyze_alignment_feasibility_sample(
    output_dir: Path, manifest: dict[str, Any],
) -> dict[str, Any]:
    """Apply the frozen volume-only concentration calculation."""
    if len(manifest.get("artifacts", [])) != len(ALIGNMENT_SAMPLE_SLICES):
        raise RuntimeError("SIS alignment manifest is not the frozen seven slices")
    receiver: dict[tuple[int, str], dict[str, float]] = {}
    defenders: dict[tuple[int, str], dict[str, float]] = {}
    receiver_bucket = {"left": "left", "right": "right", "slot": "slot"}

    def number(value: str) -> float:
        return float(value.replace(",", "").strip() or 0)

    for artifact in manifest["artifacts"]:
        path = output_dir / artifact["artifact"]
        if _sha256(path) != artifact["sha256"]:
            raise RuntimeError("SIS alignment artifact hash differs")
        id_by_name = {
            str(row.get("player")): int(row["playerId"])
            for row in artifact["identities"] if row.get("playerId") is not None
        }
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            name = row["Player"]
            if name not in id_by_name:
                raise RuntimeError("SIS alignment CSV row lacks stable player identity")
            key = (id_by_name[name], name)
            if artifact["family"] == "receiving":
                if row.get("Pos.") != "WR":
                    raise RuntimeError("SIS receiver sample contains a non-WR")
                bucket = receiver_bucket[artifact["slice"]]
                player = receiver.setdefault(
                    key, {"left": 0.0, "right": 0.0, "slot": 0.0})
                player[bucket] += number(row["Routes"])
            else:
                if row.get("Pos.") != "CB":
                    raise RuntimeError("SIS defender sample contains a non-CB")
                player = defenders.setdefault(
                    key, {"lcb": 0.0, "rcb": 0.0, "scb": 0.0})
                player[artifact["slice"]] += number(row["Cov. Snaps"])
    eligible_wr = [(key, values, sum(values.values()))
                   for key, values in receiver.items() if sum(values.values()) >= 5]
    eligible_cb = [(key, values, sum(values.values()))
                   for key, values in defenders.items() if sum(values.values()) >= 5]
    if not eligible_wr or len(eligible_cb) < 2:
        raise RuntimeError("SIS alignment sample lacks frozen minimum volume support")
    wr_key, wr_values, wr_total = sorted(
        eligible_wr, key=lambda row: (-row[2], row[0][0]))[0]
    top_cbs = sorted(eligible_cb, key=lambda row: (-row[2], row[0][0]))[:2]
    wr_share = {name: value / wr_total for name, value in wr_values.items()}
    cb_results = []
    for key, values, total in top_cbs:
        share = {name: value / total for name, value in values.items()}
        overlap = (
            wr_share["right"] * share["lcb"]
            + wr_share["left"] * share["rcb"]
            + wr_share["slot"] * share["scb"]
        )
        cb_results.append({
            "player_id": key[0], "player": key[1], "coverage_snaps": total,
            "shares": share, "largest_share": max(share.values()),
            "alignment_overlap": overlap,
        })
    wr_largest = max(wr_share.values())
    best_cb_largest = max(row["largest_share"] for row in cb_results)
    best_overlap = max(row["alignment_overlap"] for row in cb_results)
    passes = wr_largest >= 0.55 and best_cb_largest >= 0.55 and best_overlap >= 0.50
    return {
        "disposition": (
            "sis-alignment-feasibility-passes" if passes
            else "sis-alignment-feasibility-fails"),
        "passes": passes,
        "receiver": {
            "player_id": wr_key[0], "player": wr_key[1], "routes": wr_total,
            "shares": wr_share, "largest_share": wr_largest,
        },
        "defenders": cb_results,
        "best_defender_largest_share": best_cb_largest,
        "best_alignment_overlap": best_overlap,
        "thresholds": {
            "receiver_largest_share": 0.55,
            "defender_largest_share": 0.55,
            "alignment_overlap": 0.50,
        },
        "outcome_columns_read": [],
        "api_requests_used": manifest["api_requests_used"],
    }


def _player_pass_defense_grain_artifact() -> str:
    return "2025-weeks01-18-ari-wide-wr-cb-pass-defense-totals.csv"


def analyze_player_pass_defense_grain_sample(
    output_dir: Path, manifest: dict[str, Any],
) -> dict[str, Any]:
    """Apply the frozen schema/identity-only player-grain feasibility gate."""
    artifacts = manifest.get("artifacts", [])
    if len(artifacts) != 1:
        raise RuntimeError("SIS player-grain manifest must contain one artifact")
    item = artifacts[0]
    path = output_dir / item.get("artifact", "")
    if not path.is_file() or _sha256(path) != item.get("sha256"):
        raise RuntimeError("SIS player-grain artifact is missing or changed")
    spec = ExportSpec(**item.get("spec", {}))
    expected_spec = ExportSpec(
        entity="players", report="pass-defense-totals", season=2025,
        start_week=1, end_week=18, split_by_game=True, team_id=1,
    )
    if spec != expected_spec:
        raise RuntimeError("SIS player-grain artifact scope differs")
    if item.get("submitted_scope") is None:
        raise RuntimeError("SIS player-grain submitted scope is missing")
    differences = {
        name: {"expected": values, "actual": item["submitted_scope"].get(name)}
        for name, values in PLAYER_PASS_DEFENSE_GRAIN_FILTERS.items()
        if item["submitted_scope"].get(name) != values
    }
    if differences:
        raise RuntimeError(
            "SIS player-grain filter scope differs: "
            + json.dumps(differences, sort_keys=True)
        )
    rows = int(item.get("rows", -1))
    if not 1 <= rows < 200:
        raise RuntimeError("SIS player-grain row count is empty or capped")
    _validate_csv_scope(path, expected_spec, rows)
    header = _csv_header(path)
    failures: list[str] = []
    if "Player" not in header:
        failures.append("missing-player")
    if not ({"Cov. Snaps", "Coverage Snaps"} & set(header)):
        failures.append("missing-coverage-snaps")
    if not ({"Tgts", "Targets"} & set(header)):
        failures.append("missing-targets")

    with path.open(encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    identities = item.get("identities", [])
    if len(identities) != rows:
        failures.append("identity-row-count")
    identity_keys: list[tuple[int, int]] = []
    identity_name_weeks: set[tuple[str, int]] = set()
    for identity in identities:
        player_id = identity.get("playerId")
        player = identity.get("player") or identity.get("name")
        week = identity.get("week")
        if player_id is None or not player or week is None:
            failures.append("unstable-identity")
            continue
        identity_keys.append((int(player_id), int(week)))
        identity_name_weeks.add((str(player), int(week)))
    if len(identity_keys) != len(set(identity_keys)):
        failures.append("duplicate-player-week-identity")
    csv_name_weeks = {
        (str(row.get("Player", "")), int(row.get("Week", -1)))
        for row in csv_rows
    }
    if csv_name_weeks != identity_name_weeks:
        failures.append("csv-api-player-week-mismatch")
    used = int(manifest.get("api_requests_used", -1))
    ceiling = int(manifest.get("api_request_ceiling", -1))
    if ceiling != PLAYER_PASS_DEFENSE_GRAIN_API_REQUEST_CEILING:
        failures.append("request-ceiling")
    if not 1 <= used <= ceiling:
        failures.append("request-count")
    passes = not failures
    return {
        "schema_version": 1,
        "protocol": PLAYER_PASS_DEFENSE_GRAIN_VERSION,
        "disposition": (
            "sis-player-pass-defense-grain-feasibility-passes"
            if passes else "sis-player-pass-defense-grain-feasibility-fails"
        ),
        "passes": passes,
        "failures": failures,
        "rows": rows,
        "distinct_player_ids": len({key[0] for key in identity_keys}),
        "weeks": sorted({key[1] for key in identity_keys}),
        "headers": header,
        "api_requests_used": used,
        "api_request_ceiling": ceiling,
        "performance_values_read": [],
        "fantasy_or_lineup_outcomes_read": [],
    }


def run_player_pass_defense_grain_sample(
    profile_dir: Path,
    timeout_seconds: float,
    output_dir: Path,
) -> dict[str, Any]:
    """Acquire the frozen one-query player pass-defense grain sample."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            'install browser support with `pip install -e ".[browser]"`'
        ) from exc
    protocol = Path(
        "reports/2026-08-15-sis-player-pass-defense-grain-feasibility-protocol.md"
    )
    if not protocol.is_file():
        raise RuntimeError("frozen SIS player-grain protocol is missing")
    storage_state = default_storage_state_path(profile_dir)
    if not storage_state.is_file():
        raise RuntimeError("SIS saved storage state is missing; run `sis-download login`")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_state = output_dir / ".player-pass-defense-grain.run-state.json"
    manifest_path = output_dir / "player-pass-defense-grain.manifest.json"
    result_path = output_dir / "player-pass-defense-grain.result.json"
    artifact_path = output_dir / _player_pass_defense_grain_artifact()
    if manifest_path.exists() or result_path.exists() or artifact_path.exists():
        raise RuntimeError("refusing to overwrite SIS player-grain sample")
    protocol_hash = _sha256(protocol)
    used = 0
    if run_state.exists():
        state = json.loads(run_state.read_text(encoding="utf-8"))
        if state.get("plan_sha256") != protocol_hash or int(
            state.get("ceiling", -1)
        ) != PLAYER_PASS_DEFENSE_GRAIN_API_REQUEST_CEILING:
            raise RuntimeError("SIS player-grain request state identity differs")
        used = int(state.get("used", -1))
        if not 0 <= used <= PLAYER_PASS_DEFENSE_GRAIN_API_REQUEST_CEILING:
            raise RuntimeError("SIS player-grain request count is invalid")
    budget = APIRequestBudget(
        ceiling=PLAYER_PASS_DEFENSE_GRAIN_API_REQUEST_CEILING,
        used=used,
        state_path=run_state,
        plan_sha256=protocol_hash,
    )
    budget.persist()
    submit_budget = SubmitOnlyAPIRequestBudget(budget)
    timeout_ms = int(timeout_seconds * 1000)
    spec = ExportSpec(
        entity="players", report="pass-defense-totals", season=2025,
        start_week=1, end_week=18, split_by_game=True, team_id=1,
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(storage_state), accept_downloads=True,
            viewport={"width": 1800, "height": 1200},
        )
        context.route("**/api/v1/nfl/**/query", submit_budget.route)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(NFL_LEADERS_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            _assert_authenticated(page, timeout_ms)
            page.locator("#querybuilder").wait_for(state="attached")
            _activate_report_view_without_refresh(page, spec.definition)
            _set_select(page, "#TimeFilters_SeasonFrom", "2025")
            _set_select(page, "#TimeFilters_SeasonTo", "2025")
            _set_select(page, "#TimeFilters_StartWeek", "1")
            _set_select(page, "#TimeFilters_EndWeek", "18")
            _set_select(page, "#Teams", "1")
            _set_checkbox(page, "#chkIncludePlayoffs", False)
            _set_checkbox(page, "#chkByGame", True)
            _set_checkbox_values(page, "PassDefenseFilters.DefenderPos", ["12"])
            _set_checkbox_values(page, "PassDefenseFilters.ReceiverPos", ["4"])
            _set_checkbox_values(page, "PassDefenseFilters.TargetLinedUp", ["2"])
            _set_input_value(page, "PassDefenseFilters.MinTargets", "0")
            _set_input_value(page, "PassDefenseFilters.MinAttempts", "0")
            submit_budget.armed = True
            try:
                with page.expect_response(
                    lambda response: _response_matches_filters(
                        response, spec, PLAYER_PASS_DEFENSE_GRAIN_FILTERS
                    ),
                    timeout=timeout_ms,
                ) as response_info:
                    page.locator("#submit").click()
            finally:
                submit_budget.armed = False
            response = response_info.value
            _assert_submitted_scope(
                response, spec, PLAYER_PASS_DEFENSE_GRAIN_FILTERS
            )
            expected_rows = _assert_api_scope(response, spec, row_cap=200)
            if expected_rows == 0:
                raise RuntimeError("SIS player-grain sample returned no rows")
            _wait_for_table(
                page, expected_rows, timeout_ms,
                CSV_REQUIRED_COLUMNS["pass-defense-totals"],
            )
            button = page.locator("a.dt-button.buttons-csv:visible")
            if button.count() != 1:
                raise RuntimeError("SIS page has an ambiguous Download control")
            partial = artifact_path.with_suffix(artifact_path.suffix + ".partial")
            with page.expect_download(timeout=timeout_ms) as download_info:
                button.click()
            download_info.value.save_as(str(partial))
            try:
                _validate_csv_scope(partial, spec, expected_rows)
            except Exception:
                partial.unlink(missing_ok=True)
                raise
            partial.replace(artifact_path)
            artifact = {
                "artifact": artifact_path.name,
                "sha256": _sha256(artifact_path),
                "bytes": artifact_path.stat().st_size,
                "rows": expected_rows,
                "headers": _csv_header(artifact_path),
                "spec": asdict(spec),
                "submitted_scope": _request_scope(response.request),
                "identities": _identity_rows(response),
            }
        finally:
            context.close()
            browser.close()
    manifest = {
        "schema_version": 1,
        "protocol": PLAYER_PASS_DEFENSE_GRAIN_VERSION,
        "protocol_sha256": protocol_hash,
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "api_requests_used": budget.used,
        "api_request_ceiling": budget.ceiling,
        "artifacts": [artifact],
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result = analyze_player_pass_defense_grain_sample(output_dir, manifest)
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def _team_pass_defense_artifact(report: str, slice_name: str) -> str:
    if report not in TEAM_PASS_DEFENSE_PROFILE_REPORTS:
        raise ValueError(f"unsupported SIS defense-profile report {report!r}")
    if slice_name not in {row[0] for row in TEAM_PASS_DEFENSE_PROFILE_SLICES}:
        raise ValueError(f"unsupported SIS defense-profile slice {slice_name!r}")
    return f"2025-week01-team-pass-defense__{slice_name}__{report}.csv"


def _asoe_artifact(
    season: int, start_week: int, end_week: int, alignment: str,
) -> str:
    if season not in ASOE_SEASONS:
        raise ValueError(f"unsupported ASOE season {season}")
    if (start_week, end_week) not in ASOE_WINDOWS:
        raise ValueError(f"unsupported ASOE window {(start_week, end_week)}")
    if alignment not in dict(ASOE_ALIGNMENTS):
        raise ValueError(f"unsupported ASOE alignment {alignment!r}")
    return (
        f"{season}-weeks{start_week:02d}-{end_week:02d}"
        f"-team-pass-defense__{alignment}__pass-defense-totals.csv"
    )


def analyze_team_pass_defense_asoe_acquisition(
    output_dir: Path, manifest: dict[str, Any],
) -> dict[str, Any]:
    """Validate the frozen ASOE opportunity-only acquisition."""
    artifacts = manifest.get("artifacts", [])
    expected = {
        (season, start, end, alignment)
        for season in ASOE_SEASONS
        for start, end in ASOE_WINDOWS
        for alignment, _values in ASOE_ALIGNMENTS
    }
    observed = {
        (
            int(item.get("season", -1)), int(item.get("start_week", -1)),
            int(item.get("end_week", -1)), str(item.get("alignment")),
        )
        for item in artifacts
    }
    if len(artifacts) != len(expected) or observed != expected:
        raise RuntimeError("SIS ASOE manifest is not the frozen 24-artifact grid")

    failures: list[str] = []
    all_teams: set[int] = set()
    total_rows = 0
    total_attempts = 0
    for item in artifacts:
        season = int(item["season"])
        start = int(item["start_week"])
        end = int(item["end_week"])
        alignment = str(item["alignment"])
        path = output_dir / str(item["artifact"])
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise RuntimeError("SIS ASOE artifact is missing or changed")
        rows = int(item.get("rows", -1))
        total_rows += rows
        if rows >= 200:
            failures.append(f"{season}:{start}-{end}:{alignment}:row-cap")
        headers = set(item.get("headers", []))
        if not {"Season", "Team", "Week", "Opp.", "Att"} <= headers:
            failures.append(f"{season}:{start}-{end}:{alignment}:schema")
        expected_scope = {
            "PassDefenseFilters.TargetLinedUp": list(
                dict(ASOE_ALIGNMENTS)[alignment]),
            "PassDefenseFilters.Schemes": list(ASOE_ALL_SCHEMES),
            "PassDefenseFilters.ReceiverPos": ["4"],
            "PassDefenseFilters.MinTargets": ["0"],
            "PassDefenseFilters.MinAttempts": ["1"],
        }
        submitted = item.get("submitted_scope", {})
        for name, values in expected_scope.items():
            if submitted.get(name) != values:
                failures.append(
                    f"{season}:{start}-{end}:{alignment}:scope:{name}")
        identities = item.get("identities", [])
        if len(identities) != rows:
            failures.append(
                f"{season}:{start}-{end}:{alignment}:identity-row-count")
        keys: set[tuple[int, int]] = set()
        for identity in identities:
            required = {"season", "week", "games", "teamId", "team", "opp"}
            if missing := required - set(identity):
                raise RuntimeError(
                    f"SIS ASOE identity lacks {sorted(missing)}")
            team_id = int(identity["teamId"])
            key = (team_id, int(identity["week"]))
            if key in keys:
                failures.append(
                    f"{season}:{start}-{end}:{alignment}:duplicate-team-week")
            keys.add(key)
            all_teams.add(team_id)
            if (
                int(identity["season"]) != season
                or not start <= int(identity["week"]) <= end
                or int(identity["games"]) != 1
            ):
                failures.append(
                    f"{season}:{start}-{end}:{alignment}:identity-scope")

        with path.open(encoding="utf-8-sig", newline="") as handle:
            csv_rows = list(csv.DictReader(handle))
        if len(csv_rows) != rows:
            failures.append(f"{season}:{start}-{end}:{alignment}:csv-row-count")
        for row in csv_rows:
            raw = str(row.get("Att", "")).replace(",", "").strip()
            try:
                attempts = float(raw)
            except ValueError:
                failures.append(
                    f"{season}:{start}-{end}:{alignment}:invalid-attempt")
                continue
            if attempts < 0 or not attempts.is_integer():
                failures.append(
                    f"{season}:{start}-{end}:{alignment}:invalid-attempt")
            else:
                total_attempts += int(attempts)
    if len(all_teams) != 32:
        failures.append(f"union-team-count:{len(all_teams)}")
    used = int(manifest.get("api_requests_used", -1))
    ceiling = int(manifest.get("api_request_ceiling", -1))
    if ceiling != ASOE_API_REQUEST_CEILING or not 24 <= used <= ceiling:
        failures.append(f"request-budget:{used}/{ceiling}")
    passes = not failures
    return {
        "schema_version": 1,
        "disposition": (
            "sis-asoe-acquisition-passes" if passes
            else "sis-asoe-acquisition-fails"
        ),
        "passes": passes,
        "failures": failures,
        "artifact_count": len(artifacts),
        "rows": total_rows,
        "attempts": total_attempts,
        "union_team_count": len(all_teams),
        "api_requests_used": used,
        "api_request_ceiling": ceiling,
        "opportunity_columns_read": ["Att"],
        "performance_values_read": [],
    }


def run_team_pass_defense_asoe_acquisition(
    profile_dir: Path,
    timeout_seconds: float,
    output_dir: Path,
) -> dict[str, Any]:
    """Acquire the frozen 24-artifact SIS team/game ASOE history."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('install browser support with `pip install -e "[browser]"`') from exc
    protocol = Path("reports/2026-08-13-sis-asoe-acquisition-protocol.md")
    if not protocol.is_file():
        raise RuntimeError("frozen SIS ASOE acquisition protocol is missing")
    storage_state = default_storage_state_path(profile_dir)
    if not storage_state.is_file():
        raise RuntimeError("SIS saved storage state is missing; run `sis-download login`")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_state = output_dir / ".team-pass-defense-asoe.run-state.json"
    partial_manifest_path = output_dir / ".team-pass-defense-asoe.partial-manifest.json"
    manifest_path = output_dir / "team-pass-defense-asoe.manifest.json"
    result_path = output_dir / "team-pass-defense-asoe.result.json"
    if manifest_path.exists() or result_path.exists():
        raise RuntimeError("refusing to overwrite SIS ASOE acquisition result")
    protocol_hash = _sha256(protocol)
    used = 0
    if run_state.exists():
        state = json.loads(run_state.read_text(encoding="utf-8"))
        if state.get("plan_sha256") != protocol_hash or int(
            state.get("ceiling", -1)
        ) != ASOE_API_REQUEST_CEILING:
            raise RuntimeError("SIS ASOE request-state identity differs")
        used = int(state.get("used", -1))
        if not 0 <= used <= ASOE_API_REQUEST_CEILING:
            raise RuntimeError("SIS ASOE request count is invalid")
    budget = APIRequestBudget(
        ceiling=ASOE_API_REQUEST_CEILING, used=used, state_path=run_state,
        plan_sha256=protocol_hash,
    )
    budget.persist()
    submit_budget = SubmitOnlyAPIRequestBudget(budget)
    timeout_ms = int(timeout_seconds * 1000)
    artifacts: list[dict[str, Any]] = []
    if partial_manifest_path.exists():
        partial = json.loads(partial_manifest_path.read_text(encoding="utf-8"))
        if partial.get("protocol_sha256") != protocol_hash:
            raise RuntimeError("SIS ASOE partial-manifest identity differs")
        artifacts = partial.get("artifacts", [])
        keys = [
            (
                item.get("season"), item.get("start_week"),
                item.get("end_week"), item.get("alignment"),
            )
            for item in artifacts
        ]
        if len(keys) != len(set(keys)):
            raise RuntimeError("SIS ASOE partial manifest has duplicate artifacts")
        for item in artifacts:
            path = output_dir / item["artifact"]
            if not path.is_file() or _sha256(path) != item.get("sha256"):
                raise RuntimeError("SIS ASOE partial artifact is missing or changed")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(storage_state), accept_downloads=True,
            viewport={"width": 1800, "height": 1200},
        )
        context.route("**/api/v1/nfl/**/query", submit_budget.route)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(
                f"{BASE_URL}/NFL/Leaders/Teams",
                wait_until="domcontentloaded", timeout=timeout_ms,
            )
            _assert_authenticated(page, timeout_ms)
            page.locator("#querybuilder").wait_for(state="attached")
            spec_definition = REPORTS["pass-defense-totals"]
            _activate_report_view_without_refresh(page, spec_definition)
            _set_select(page, "#Teams", "-1")
            _set_checkbox(page, "#chkIncludePlayoffs", False)
            _set_checkbox(page, "#chkByGame", True)
            _set_checkbox_values(page, "PassDefenseFilters.ReceiverPos", ["4"])
            _set_checkbox_values(
                page, "PassDefenseFilters.Schemes", ASOE_ALL_SCHEMES)
            _set_input_value(page, "PassDefenseFilters.MinTargets", "0")
            _set_input_value(page, "PassDefenseFilters.MinAttempts", "1")
            for season in ASOE_SEASONS:
                _set_select(page, "#TimeFilters_SeasonFrom", str(season))
                _set_select(page, "#TimeFilters_SeasonTo", str(season))
                for start, end in ASOE_WINDOWS:
                    _set_select(page, "#TimeFilters_StartWeek", str(start))
                    _set_select(page, "#TimeFilters_EndWeek", str(end))
                    for alignment, alignment_values in ASOE_ALIGNMENTS:
                        prior = next((
                            item for item in artifacts
                            if int(item["season"]) == season
                            and int(item["start_week"]) == start
                            and int(item["end_week"]) == end
                            and item["alignment"] == alignment
                        ), None)
                        if prior is not None:
                            print(
                                "SIS ASOE verified existing: "
                                f"{season}/{start}-{end}/{alignment}",
                                flush=True,
                            )
                            continue
                        destination = output_dir / _asoe_artifact(
                            season, start, end, alignment)
                        if destination.exists():
                            raise RuntimeError(
                                f"unmanifested SIS ASOE artifact: {destination}")
                        _set_checkbox_values(
                            page, "PassDefenseFilters.TargetLinedUp",
                            alignment_values,
                        )
                        filters = {
                            "PassDefenseFilters.TargetLinedUp": list(
                                alignment_values),
                            "PassDefenseFilters.Schemes": list(
                                ASOE_ALL_SCHEMES),
                            "PassDefenseFilters.ReceiverPos": ["4"],
                            "PassDefenseFilters.MinTargets": ["0"],
                            "PassDefenseFilters.MinAttempts": ["1"],
                        }
                        spec = ExportSpec(
                            entity="teams", report="pass-defense-totals",
                            season=season, start_week=start, end_week=end,
                            split_by_game=True,
                        )
                        submit_budget.armed = True
                        try:
                            with page.expect_response(
                                lambda response, current=spec: (
                                    f"/api/v1/nfl/{current.entity}/query"
                                    in response.url
                                ),
                                timeout=timeout_ms,
                            ) as response_info:
                                page.locator("#submit").click()
                        finally:
                            submit_budget.armed = False
                        response = response_info.value
                        _assert_submitted_scope(response, spec, filters)
                        expected_rows = _assert_api_scope(
                            response, spec, row_cap=200)
                        if expected_rows == 0:
                            raise RuntimeError(
                                f"SIS ASOE slice is empty: "
                                f"{season}/{start}-{end}/{alignment}")
                        _wait_for_table(
                            page, expected_rows, timeout_ms,
                            CSV_REQUIRED_COLUMNS["pass-defense-totals"],
                        )
                        button = page.locator(
                            "a.dt-button.buttons-csv:visible")
                        if button.count() != 1:
                            raise RuntimeError(
                                "SIS page has an ambiguous Download control")
                        temporary = destination.with_suffix(
                            destination.suffix + ".partial")
                        with page.expect_download(
                            timeout=timeout_ms) as download_info:
                            button.click()
                        download_info.value.save_as(str(temporary))
                        try:
                            _validate_csv_scope(
                                temporary, spec, expected_rows)
                        except Exception:
                            temporary.unlink(missing_ok=True)
                            raise
                        temporary.replace(destination)
                        artifacts.append({
                            "season": season,
                            "start_week": start,
                            "end_week": end,
                            "alignment": alignment,
                            "artifact": destination.name,
                            "sha256": _sha256(destination),
                            "bytes": destination.stat().st_size,
                            "rows": expected_rows,
                            "headers": _csv_header(destination),
                            "spec": asdict(spec),
                            "filters": filters,
                            "submitted_scope": _request_scope(response.request),
                            "identities": _identity_rows(response),
                        })
                        _write_json_atomic(partial_manifest_path, {
                            "schema_version": 1,
                            "protocol_sha256": protocol_hash,
                            "api_requests_used": budget.used,
                            "api_request_ceiling": budget.ceiling,
                            "artifacts": artifacts,
                        })
                        print(
                            "SIS ASOE acquired: "
                            f"{season}/{start}-{end}/{alignment} "
                            f"({expected_rows} rows; {budget.used}/"
                            f"{ASOE_API_REQUEST_CEILING} requests)",
                            flush=True,
                        )
        finally:
            context.close()
            browser.close()
    manifest = {
        "schema_version": 1,
        "protocol_sha256": protocol_hash,
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "api_requests_used": budget.used,
        "api_request_ceiling": budget.ceiling,
        "artifacts": artifacts,
    }
    _write_json_atomic(manifest_path, manifest)
    result = analyze_team_pass_defense_asoe_acquisition(output_dir, manifest)
    _write_json_atomic(result_path, result)
    partial_manifest_path.unlink(missing_ok=True)
    return result


def _pass_tail_weekly_artifact(
    target_week: int, start_week: int, end_week: int,
    report: str, slice_name: str,
) -> str:
    if not 5 <= int(target_week) <= 18:
        raise ValueError("SIS pass-tail target week must be within 5..18")
    allowed = {
        ("pass-defense-totals", "all"),
        ("pass-defense-value", "all"),
        ("pass-rush-totals", "all"),
        ("pass-defense-totals", "wide"),
        ("pass-defense-totals", "slot"),
    }
    if (report, slice_name) not in allowed:
        raise ValueError("unsupported SIS pass-tail weekly view")
    return (
        f"2026-target-week-{int(target_week):02d}"
        f"__source-weeks-{int(start_week):02d}-{int(end_week):02d}"
        f"__{report}__{slice_name}.csv"
    )


def _analyze_pass_tail_weekly_manifest(
    output_dir: Path, manifest: dict[str, Any],
) -> dict[str, Any]:
    target_week = int(manifest.get("target_week", -1))
    source_start = int(manifest.get("source_week_start", -1))
    source_end = int(manifest.get("source_week_end", -1))
    expected_start = 1 if target_week == 5 else target_week - 1
    if not 5 <= target_week <= 18 or (source_start, source_end) != (
        expected_start, target_week - 1,
    ):
        raise RuntimeError("SIS pass-tail weekly source window differs")
    expected = {
        ("pass-defense-totals", "all"),
        ("pass-defense-value", "all"),
        ("pass-rush-totals", "all"),
        ("pass-defense-totals", "wide"),
        ("pass-defense-totals", "slot"),
    }
    artifacts = manifest.get("artifacts", [])
    observed = {
        (str(item.get("report")), str(item.get("slice")))
        for item in artifacts
    }
    if len(artifacts) != len(expected) or observed != expected:
        raise RuntimeError("SIS pass-tail weekly manifest is not five views")
    failures: list[str] = []
    for item in artifacts:
        report, slice_name = str(item["report"]), str(item["slice"])
        path = output_dir / str(item["artifact"])
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise RuntimeError("SIS pass-tail weekly artifact is missing or changed")
        spec = ExportSpec(**item["spec"])
        if (
            spec.entity != "teams" or spec.season != 2026
            or spec.start_week != source_start or spec.end_week != source_end
            or not spec.split_by_game or spec.report != report
        ):
            failures.append(f"{report}:{slice_name}:spec")
        rows = int(item.get("rows", -1))
        if not 0 < rows < 200:
            failures.append(f"{report}:{slice_name}:rows:{rows}")
        if len(item.get("identities", [])) != rows:
            failures.append(f"{report}:{slice_name}:identity-row-count")
        if slice_name in {"wide", "slot"}:
            wanted = list(dict(ASOE_ALIGNMENTS)[slice_name])
            submitted = item.get("submitted_scope", {})
            if submitted.get("PassDefenseFilters.TargetLinedUp") != wanted:
                failures.append(f"{report}:{slice_name}:alignment")
            if submitted.get("PassDefenseFilters.Schemes") != list(
                ASOE_ALL_SCHEMES
            ):
                failures.append(f"{report}:{slice_name}:schemes")
        _validate_csv_scope(path, spec, rows)
    used = int(manifest.get("api_requests_used", -1))
    ceiling = int(manifest.get("api_request_ceiling", -1))
    if ceiling != PASS_TAIL_WEEKLY_API_REQUEST_CEILING or not 5 <= used <= ceiling:
        failures.append(f"request-budget:{used}/{ceiling}")
    return {
        "schema_version": 1,
        "version": PASS_TAIL_WEEKLY_VERSION,
        "passes": not failures,
        "disposition": (
            "sis-pass-tail-weekly-acquisition-passes"
            if not failures else "sis-pass-tail-weekly-acquisition-fails"
        ),
        "failures": failures,
        "target_week": target_week,
        "source_week_start": source_start,
        "source_week_end": source_end,
        "artifacts": len(artifacts),
        "api_requests_used": used,
        "api_request_ceiling": ceiling,
    }


def run_pass_tail_weekly_acquisition(
    profile_dir: Path,
    timeout_seconds: float,
    output_dir: Path,
    *,
    target_week: int,
) -> dict[str, Any]:
    """Acquire the five frozen SIS views for one 2026 target week."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            'install browser support with `pip install -e "[browser]"`'
        ) from exc
    target_week = int(target_week)
    if not 5 <= target_week <= 18:
        raise ValueError("SIS pass-tail target week must be within 5..18")
    source_start = 1 if target_week == 5 else target_week - 1
    source_end = target_week - 1
    protocol = Path(
        "reports/2026-08-15-prospective-sis-pass-tail-finite-k-protocol.md"
    )
    if not protocol.is_file():
        raise RuntimeError("frozen SIS pass-tail protocol is missing")
    storage_state = default_storage_state_path(profile_dir)
    if not storage_state.is_file():
        raise RuntimeError("SIS saved storage state is missing; run `sis-download login`")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_state = output_dir / ".pass-tail-weekly.run-state.json"
    partial_manifest_path = output_dir / ".pass-tail-weekly.partial-manifest.json"
    manifest_path = output_dir / "pass-tail-weekly.manifest.json"
    result_path = output_dir / "pass-tail-weekly.result.json"
    if manifest_path.exists() or result_path.exists():
        raise RuntimeError("refusing to overwrite SIS pass-tail weekly result")
    identity = hashlib.sha256(
        (
            _sha256(protocol) + f"|{PASS_TAIL_WEEKLY_VERSION}|2026|"
            f"{target_week}|{source_start}|{source_end}"
        ).encode()
    ).hexdigest()
    used = 0
    if run_state.exists():
        state = json.loads(run_state.read_text(encoding="utf-8"))
        if (
            state.get("plan_sha256") != identity
            or int(state.get("ceiling", -1))
            != PASS_TAIL_WEEKLY_API_REQUEST_CEILING
        ):
            raise RuntimeError("SIS pass-tail weekly request-state identity differs")
        used = int(state.get("used", -1))
        if not 0 <= used <= PASS_TAIL_WEEKLY_API_REQUEST_CEILING:
            raise RuntimeError("SIS pass-tail weekly request count is invalid")
    budget = APIRequestBudget(
        ceiling=PASS_TAIL_WEEKLY_API_REQUEST_CEILING,
        used=used,
        state_path=run_state,
        plan_sha256=identity,
    )
    budget.persist()
    submit_budget = SubmitOnlyAPIRequestBudget(budget)
    artifacts: list[dict[str, Any]] = []
    if partial_manifest_path.exists():
        partial = json.loads(partial_manifest_path.read_text(encoding="utf-8"))
        if partial.get("acquisition_identity") != identity:
            raise RuntimeError("SIS pass-tail partial-manifest identity differs")
        artifacts = list(partial.get("artifacts", []))
        keys = [(item.get("report"), item.get("slice")) for item in artifacts]
        if len(keys) != len(set(keys)):
            raise RuntimeError("SIS pass-tail partial manifest has duplicate views")
        for item in artifacts:
            path = output_dir / str(item["artifact"])
            if not path.is_file() or _sha256(path) != item.get("sha256"):
                raise RuntimeError("SIS pass-tail partial artifact changed")

    views = (
        ("pass-defense-totals", "all", None),
        ("pass-defense-value", "all", None),
        ("pass-rush-totals", "all", None),
        ("pass-defense-totals", "wide", dict(ASOE_ALIGNMENTS)["wide"]),
        ("pass-defense-totals", "slot", dict(ASOE_ALIGNMENTS)["slot"]),
    )
    timeout_ms = int(timeout_seconds * 1000)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(storage_state), accept_downloads=True,
            viewport={"width": 1800, "height": 1200},
        )
        context.route("**/api/v1/nfl/**/query", submit_budget.route)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(
                f"{BASE_URL}/NFL/Leaders/Teams",
                wait_until="domcontentloaded", timeout=timeout_ms,
            )
            _assert_authenticated(page, timeout_ms)
            page.locator("#querybuilder").wait_for(state="attached")
            for report, slice_name, alignment_values in views:
                prior = next((
                    item for item in artifacts
                    if item.get("report") == report
                    and item.get("slice") == slice_name
                ), None)
                if prior is not None:
                    print(
                        f"SIS pass-tail verified existing: {report}/{slice_name}",
                        flush=True,
                    )
                    continue
                spec = ExportSpec(
                    entity="teams", report=report, season=2026,
                    start_week=source_start, end_week=source_end,
                    split_by_game=True,
                )
                definition = spec.definition
                _activate_report_view_without_refresh(page, definition)
                _set_select(page, "#TimeFilters_SeasonFrom", "2026")
                _set_select(page, "#TimeFilters_SeasonTo", "2026")
                _set_select(page, "#TimeFilters_StartWeek", str(source_start))
                _set_select(page, "#TimeFilters_EndWeek", str(source_end))
                _set_select(page, "#Teams", "-1")
                _set_checkbox(page, "#chkIncludePlayoffs", False)
                _set_checkbox(page, "#chkByGame", True)
                filters: dict[str, list[str]] = {}
                if alignment_values is not None:
                    _set_checkbox_values(
                        page, "PassDefenseFilters.TargetLinedUp",
                        alignment_values,
                    )
                    _set_checkbox_values(
                        page, "PassDefenseFilters.Schemes", ASOE_ALL_SCHEMES,
                    )
                    _set_checkbox_values(
                        page, "PassDefenseFilters.ReceiverPos", ["4"],
                    )
                    _set_input_value(page, "PassDefenseFilters.MinTargets", "0")
                    _set_input_value(page, "PassDefenseFilters.MinAttempts", "1")
                    filters = {
                        "PassDefenseFilters.TargetLinedUp": list(alignment_values),
                        "PassDefenseFilters.Schemes": list(ASOE_ALL_SCHEMES),
                        "PassDefenseFilters.ReceiverPos": ["4"],
                        "PassDefenseFilters.MinTargets": ["0"],
                        "PassDefenseFilters.MinAttempts": ["1"],
                    }
                submit_budget.armed = True
                try:
                    with page.expect_response(
                        lambda response, current=spec, wanted=filters: (
                            _response_matches_filters(response, current, wanted)
                            if wanted else _response_matches_spec(response, current)
                        ),
                        timeout=timeout_ms,
                    ) as response_info:
                        page.locator("#submit").click()
                finally:
                    submit_budget.armed = False
                response = response_info.value
                if filters:
                    _assert_submitted_scope(response, spec, filters)
                expected_rows = _assert_api_scope(response, spec, row_cap=200)
                if expected_rows == 0:
                    raise RuntimeError(
                        f"SIS pass-tail view is empty: {report}/{slice_name}")
                _wait_for_table(
                    page, expected_rows, timeout_ms,
                    CSV_REQUIRED_COLUMNS[report],
                )
                destination = output_dir / _pass_tail_weekly_artifact(
                    target_week, source_start, source_end, report, slice_name)
                if destination.exists():
                    raise RuntimeError(
                        f"unmanifested SIS pass-tail artifact: {destination}")
                temporary = destination.with_suffix(destination.suffix + ".partial")
                button = page.locator("a.dt-button.buttons-csv:visible")
                if button.count() != 1:
                    raise RuntimeError("SIS page has an ambiguous Download control")
                with page.expect_download(timeout=timeout_ms) as download_info:
                    button.click()
                download_info.value.save_as(str(temporary))
                try:
                    _validate_csv_scope(temporary, spec, expected_rows)
                except Exception:
                    temporary.unlink(missing_ok=True)
                    raise
                temporary.replace(destination)
                item = {
                    "report": report,
                    "slice": slice_name,
                    "artifact": destination.name,
                    "sha256": _sha256(destination),
                    "bytes": destination.stat().st_size,
                    "rows": expected_rows,
                    "headers": _csv_header(destination),
                    "spec": asdict(spec),
                    "filters": filters,
                    "submitted_scope": _request_scope(response.request),
                    "identities": _identity_rows(response),
                }
                _write_json_atomic(
                    destination.with_suffix(".manifest.json"), item)
                artifacts.append(item)
                _write_json_atomic(partial_manifest_path, {
                    "schema_version": 1,
                    "version": PASS_TAIL_WEEKLY_VERSION,
                    "acquisition_identity": identity,
                    "target_week": target_week,
                    "source_week_start": source_start,
                    "source_week_end": source_end,
                    "api_requests_used": budget.used,
                    "api_request_ceiling": budget.ceiling,
                    "artifacts": artifacts,
                })
                print(
                    f"SIS pass-tail acquired: {report}/{slice_name} "
                    f"({expected_rows} rows; {budget.used}/"
                    f"{budget.ceiling} requests)",
                    flush=True,
                )
        finally:
            context.close()
            browser.close()
    manifest = {
        "schema_version": 1,
        "version": PASS_TAIL_WEEKLY_VERSION,
        "acquisition_identity": identity,
        "protocol_sha256": _sha256(protocol),
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "season": 2026,
        "target_week": target_week,
        "source_week_start": source_start,
        "source_week_end": source_end,
        "api_requests_used": budget.used,
        "api_request_ceiling": budget.ceiling,
        "artifacts": artifacts,
    }
    _write_json_atomic(manifest_path, manifest)
    result = _analyze_pass_tail_weekly_manifest(output_dir, manifest)
    if not result["passes"]:
        raise RuntimeError(f"SIS pass-tail acquisition failed: {result['failures']}")
    _write_json_atomic(result_path, result)
    partial_manifest_path.unlink(missing_ok=True)
    return result


def analyze_team_pass_defense_schema_sample(
    output_dir: Path, manifest: dict[str, Any],
) -> dict[str, Any]:
    """Apply the frozen schema/identity/cap gate without reading values."""
    artifacts = manifest.get("artifacts", [])
    expected = {
        (report, slice_name)
        for report in TEAM_PASS_DEFENSE_PROFILE_REPORTS
        for slice_name, _alignment, _schemes in TEAM_PASS_DEFENSE_PROFILE_SLICES
    }
    observed = {
        (str(item.get("report")), str(item.get("slice"))) for item in artifacts
    }
    if len(artifacts) != 8 or observed != expected:
        raise RuntimeError("SIS defense-profile manifest is not the frozen eight views")

    by_key = {(item["report"], item["slice"]): item for item in artifacts}
    all_teams: set[int] = set()
    totals_headers: set[str] = set()
    value_headers: set[str] = set()
    slice_team_counts: dict[str, int] = {}
    slice_report_team_ids: dict[str, dict[str, list[int]]] = {}
    failures: list[str] = []
    used = int(manifest.get("api_requests_used", -1))
    ceiling = int(manifest.get("api_request_ceiling", -1))
    if ceiling != 10 or not 8 <= used <= 10:
        failures.append(f"request-budget:{used}/{ceiling}")
    expected_filters = {
        slice_name: (list(alignment), list(schemes))
        for slice_name, alignment, schemes in TEAM_PASS_DEFENSE_PROFILE_SLICES
    }
    for report, slice_name in sorted(expected):
        item = by_key[(report, slice_name)]
        path = output_dir / item["artifact"]
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise RuntimeError("SIS defense-profile artifact hash differs")
        if int(item.get("rows", -1)) >= 200:
            failures.append(f"{report}:{slice_name}:row-cap")
        headers = {str(value) for value in item.get("headers", [])}
        if report == "pass-defense-totals":
            totals_headers |= headers
            if not ({"Cov. Snaps", "Coverage Snaps"} & headers):
                failures.append(f"{report}:{slice_name}:missing-coverage-snaps")
            if not ({"Tgts", "Targets"} & headers):
                failures.append(f"{report}:{slice_name}:missing-targets")
        else:
            value_headers |= headers
            if not {"Points Saved", "PS Per Play"} <= headers:
                failures.append(f"{report}:{slice_name}:missing-value-fields")
        alignment, schemes = expected_filters[slice_name]
        expected_scope = {
            "PassDefenseFilters.TargetLinedUp": alignment,
            "PassDefenseFilters.Schemes": schemes,
            "PassDefenseFilters.ReceiverPos": ["4"],
            "PassDefenseFilters.MinTargets": ["0"],
            "PassDefenseFilters.MinAttempts": ["0"],
        }
        submitted = item.get("submitted_scope", {})
        for name, values in expected_scope.items():
            if submitted.get(name) != values:
                failures.append(f"{report}:{slice_name}:scope:{name}")
        team_ids: list[int] = []
        for identity in item.get("identities", []):
            required = {"season", "week", "games", "teamId", "team", "opp"}
            if missing := required - set(identity):
                raise RuntimeError(
                    f"SIS defense-profile identity lacks {sorted(missing)}"
                )
            if (
                int(identity["season"]) != 2025
                or int(identity["week"]) != 1
                or int(identity["games"]) != 1
            ):
                raise RuntimeError("SIS defense-profile identity scope differs")
            team_ids.append(int(identity["teamId"]))
        if len(team_ids) != int(item.get("rows", -1)):
            failures.append(f"{report}:{slice_name}:identity-row-count")
        if len(set(team_ids)) != len(team_ids):
            failures.append(f"{report}:{slice_name}:duplicate-team")
        if len(team_ids) > 32:
            failures.append(f"{report}:{slice_name}:more-than-32-teams")
        all_teams.update(team_ids)
        slice_report_team_ids.setdefault(slice_name, {})[report] = sorted(team_ids)

    for slice_name, reports in sorted(slice_report_team_ids.items()):
        totals = reports.get("pass-defense-totals", [])
        value = reports.get("pass-defense-value", [])
        if totals != value:
            failures.append(f"{slice_name}:totals-value-team-mismatch")
        slice_team_counts[slice_name] = len(set(totals))
    if len(all_teams) != 32:
        failures.append(f"union-team-count:{len(all_teams)}")
    passes = not failures
    return {
        "schema_version": 1,
        "disposition": (
            "sis-team-pass-defense-schema-passes"
            if passes else "sis-team-pass-defense-schema-fails"
        ),
        "passes": passes,
        "failures": failures,
        "artifact_count": len(artifacts),
        "union_team_count": len(all_teams),
        "slice_team_counts": slice_team_counts,
        "totals_headers": sorted(totals_headers),
        "value_headers": sorted(value_headers),
        "api_requests_used": manifest.get("api_requests_used"),
        "api_request_ceiling": manifest.get("api_request_ceiling"),
        "outcome_values_read": [],
    }


def run_team_pass_defense_schema_sample(
    profile_dir: Path,
    timeout_seconds: float,
    output_dir: Path,
) -> dict[str, Any]:
    """Acquire the frozen eight-view team defense-profile feasibility sample."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('install browser support with `pip install -e ".[browser]"`') from exc
    protocol = Path("reports/2026-08-13-sis-team-pass-defense-schema-protocol.md")
    if not protocol.is_file():
        raise RuntimeError("frozen SIS team pass-defense protocol is missing")
    storage_state = default_storage_state_path(profile_dir)
    if not storage_state.is_file():
        raise RuntimeError("SIS saved storage state is missing; run `sis-download login`")
    output_dir.mkdir(parents=True, exist_ok=True)
    run_state = output_dir / ".team-pass-defense-schema.run-state.json"
    partial_manifest_path = (
        output_dir / ".team-pass-defense-schema.partial-manifest.json"
    )
    manifest_path = output_dir / "team-pass-defense-schema.manifest.json"
    result_path = output_dir / "team-pass-defense-schema.result.json"
    if manifest_path.exists() or result_path.exists():
        raise RuntimeError("refusing to overwrite SIS defense-profile result")
    protocol_hash = _sha256(protocol)
    used = 0
    if run_state.exists():
        state = json.loads(run_state.read_text(encoding="utf-8"))
        if state.get("plan_sha256") != protocol_hash or int(
            state.get("ceiling", -1)
        ) != 10:
            raise RuntimeError("SIS defense-profile request state identity differs")
        used = int(state.get("used", -1))
        if not 0 <= used <= 10:
            raise RuntimeError("SIS defense-profile request state count is invalid")
    budget = APIRequestBudget(
        ceiling=10, used=used, state_path=run_state, plan_sha256=protocol_hash
    )
    budget.persist()
    submit_budget = SubmitOnlyAPIRequestBudget(budget)
    timeout_ms = int(timeout_seconds * 1000)
    artifacts: list[dict[str, Any]] = []
    if partial_manifest_path.exists():
        partial_manifest = json.loads(
            partial_manifest_path.read_text(encoding="utf-8")
        )
        if partial_manifest.get("protocol_sha256") != protocol_hash:
            raise RuntimeError("SIS defense-profile partial manifest identity differs")
        artifacts = partial_manifest.get("artifacts", [])
        keys = [(item.get("report"), item.get("slice")) for item in artifacts]
        if len(keys) != len(set(keys)):
            raise RuntimeError("SIS defense-profile partial manifest has duplicates")
        expected_keys = {
            (report, slice_name)
            for report in TEAM_PASS_DEFENSE_PROFILE_REPORTS
            for slice_name, _alignment, _schemes in TEAM_PASS_DEFENSE_PROFILE_SLICES
        }
        if not set(keys) <= expected_keys:
            raise RuntimeError("SIS defense-profile partial manifest scope differs")
        for item in artifacts:
            artifact_path = output_dir / item["artifact"]
            if not artifact_path.is_file() or _sha256(artifact_path) != item.get(
                "sha256"
            ):
                raise RuntimeError(
                    "SIS defense-profile partial artifact is missing or changed"
                )
            _validate_csv_scope(
                artifact_path,
                ExportSpec(**item["spec"]),
                int(item["rows"]),
            )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(storage_state), accept_downloads=True,
            viewport={"width": 1800, "height": 1200},
        )
        context.route("**/api/v1/nfl/**/query", submit_budget.route)
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(
                f"{BASE_URL}/NFL/Leaders/Teams",
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            _assert_authenticated(page, timeout_ms)
            page.locator("#querybuilder").wait_for(state="attached")
            for report in TEAM_PASS_DEFENSE_PROFILE_REPORTS:
                spec = ExportSpec(
                    entity="teams", report=report, season=2025,
                    start_week=1, end_week=1, split_by_game=True,
                )
                _activate_report_view_without_refresh(page, spec.definition)
                _set_select(page, "#TimeFilters_SeasonFrom", "2025")
                _set_select(page, "#TimeFilters_SeasonTo", "2025")
                _set_select(page, "#TimeFilters_StartWeek", "1")
                _set_select(page, "#TimeFilters_EndWeek", "1")
                _set_select(page, "#Teams", "-1")
                _set_checkbox(page, "#chkIncludePlayoffs", False)
                _set_checkbox(page, "#chkByGame", True)
                _set_checkbox_values(page, "PassDefenseFilters.ReceiverPos", ["4"])
                _set_input_value(page, "PassDefenseFilters.MinTargets", "0")
                _set_input_value(page, "PassDefenseFilters.MinAttempts", "0")
                for slice_name, alignment, schemes in TEAM_PASS_DEFENSE_PROFILE_SLICES:
                    destination = output_dir / _team_pass_defense_artifact(
                        report, slice_name
                    )
                    prior = next(
                        (
                            item for item in artifacts
                            if item["report"] == report and item["slice"] == slice_name
                        ),
                        None,
                    )
                    if prior is not None:
                        print(
                            "SIS defense-profile verified existing: "
                            f"{report}/{slice_name}"
                        )
                        continue
                    if destination.exists():
                        raise RuntimeError(
                            f"unmanifested SIS defense-profile artifact: {destination}"
                        )
                    _set_checkbox_values(
                        page, "PassDefenseFilters.TargetLinedUp", alignment
                    )
                    _set_checkbox_values(
                        page, "PassDefenseFilters.Schemes", schemes
                    )
                    filters = {
                        "PassDefenseFilters.TargetLinedUp": list(alignment),
                        "PassDefenseFilters.Schemes": list(schemes),
                        "PassDefenseFilters.ReceiverPos": ["4"],
                        "PassDefenseFilters.MinTargets": ["0"],
                        "PassDefenseFilters.MinAttempts": ["0"],
                    }
                    submit_budget.armed = True
                    try:
                        with page.expect_response(
                            lambda response, expected=filters, current=spec:
                            _response_matches_filters(response, current, expected),
                            timeout=timeout_ms,
                        ) as response_info:
                            page.locator("#submit").click()
                    finally:
                        submit_budget.armed = False
                    response = response_info.value
                    expected_rows = _assert_api_scope(response, spec, row_cap=200)
                    if expected_rows == 0:
                        raise RuntimeError(
                            f"SIS defense-profile slice {report}/{slice_name} is empty"
                        )
                    _wait_for_table(
                        page, expected_rows, timeout_ms,
                        CSV_REQUIRED_COLUMNS[report],
                    )
                    button = page.locator("a.dt-button.buttons-csv:visible")
                    if button.count() != 1:
                        raise RuntimeError("SIS page has an ambiguous Download control")
                    partial = destination.with_suffix(destination.suffix + ".partial")
                    with page.expect_download(timeout=timeout_ms) as download_info:
                        button.click()
                    download_info.value.save_as(str(partial))
                    try:
                        _validate_csv_scope(partial, spec, expected_rows)
                    except Exception:
                        partial.unlink(missing_ok=True)
                        raise
                    partial.replace(destination)
                    artifacts.append({
                        "report": report,
                        "slice": slice_name,
                        "artifact": destination.name,
                        "sha256": _sha256(destination),
                        "bytes": destination.stat().st_size,
                        "rows": expected_rows,
                        "headers": _csv_header(destination),
                        "spec": asdict(spec),
                        "filters": filters,
                        "submitted_scope": _request_scope(response.request),
                        "identities": _identity_rows(response),
                    })
                    _write_json_atomic(partial_manifest_path, {
                        "schema_version": 1,
                        "protocol_sha256": protocol_hash,
                        "api_requests_used": budget.used,
                        "api_request_ceiling": budget.ceiling,
                        "artifacts": artifacts,
                    })
        finally:
            context.close()
            browser.close()
    manifest = {
        "schema_version": 1,
        "protocol_sha256": protocol_hash,
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "api_requests_used": budget.used,
        "api_request_ceiling": budget.ceiling,
        "artifacts": artifacts,
    }
    _write_json_atomic(manifest_path, manifest)
    result = analyze_team_pass_defense_schema_sample(output_dir, manifest)
    _write_json_atomic(result_path, result)
    partial_manifest_path.unlink(missing_ok=True)
    return result


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
    login.add_argument(
        "--fresh",
        action="store_true",
        help="force logout and replace the saved SIS session before login",
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
    alignment = subparsers.add_parser(
        "alignment-sample",
        help="run the frozen outcome-blind ARI/NO alignment feasibility sample",
    )
    alignment.add_argument(
        "--output-dir", type=Path, default=Path("sis/alignment-feasibility-v1"))
    defense_profile = subparsers.add_parser(
        "team-pass-defense-schema-sample",
        help="run the frozen outcome-blind team defense-profile schema/cap sample",
    )
    defense_profile.add_argument(
        "--output-dir",
        type=Path,
        default=Path("sis/team-pass-defense-schema-v1"),
    )
    player_defense_grain = subparsers.add_parser(
        "player-pass-defense-grain-sample",
        help="run the frozen outcome-blind player pass-defense grain sample",
    )
    player_defense_grain.add_argument(
        "--output-dir",
        type=Path,
        default=Path("sis/player-pass-defense-grain-feasibility-v1"),
    )
    asoe = subparsers.add_parser(
        "team-pass-defense-asoe",
        help="run the frozen historical team/game alignment-attempt acquisition",
    )
    asoe.add_argument(
        "--output-dir",
        type=Path,
        default=Path("sis/team-pass-defense-asoe-v1"),
    )
    pass_tail = subparsers.add_parser(
        "pass-tail-weekly",
        help="run the frozen 2026 pass-tail target-week acquisition",
    )
    pass_tail.add_argument("--target-week", type=int, required=True)
    pass_tail.add_argument(
        "--output-dir", type=Path, default=Path("sis/pass-tail-weekly")
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
                force_fresh=args.fresh,
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
        elif args.command == "alignment-sample":
            result = run_alignment_feasibility_sample(
                args.profile_dir, args.timeout, args.output_dir)
            print("SIS alignment sample complete: " + json.dumps(
                result, sort_keys=True))
        elif args.command == "team-pass-defense-schema-sample":
            result = run_team_pass_defense_schema_sample(
                args.profile_dir, args.timeout, args.output_dir
            )
            print(
                "SIS team pass-defense schema sample complete: "
                + json.dumps(result, sort_keys=True)
            )
        elif args.command == "player-pass-defense-grain-sample":
            result = run_player_pass_defense_grain_sample(
                args.profile_dir, args.timeout, args.output_dir
            )
            print(
                "SIS player pass-defense grain sample complete: "
                + json.dumps(result, sort_keys=True)
            )
        elif args.command == "team-pass-defense-asoe":
            result = run_team_pass_defense_asoe_acquisition(
                args.profile_dir, args.timeout, args.output_dir
            )
            print(
                "SIS ASOE acquisition complete: "
                + json.dumps(result, sort_keys=True)
            )
        elif args.command == "pass-tail-weekly":
            result = run_pass_tail_weekly_acquisition(
                args.profile_dir,
                args.timeout,
                args.output_dir,
                target_week=args.target_week,
            )
            print(
                "SIS pass-tail weekly acquisition complete: "
                + json.dumps(result, sort_keys=True)
            )
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
