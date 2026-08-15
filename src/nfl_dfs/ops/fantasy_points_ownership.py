"""Authenticated bootstrap for Fantasy Points projected ownership.

The ownership product is served from ``www.fantasypoints.com`` rather than
the Data Suite host.  The two hosts currently require distinct web sessions,
even though they use the same Fantasy Points account.  This module deliberately
stops at normal-site authentication and a non-sensitive surface inventory.
The row/export collector is not allowed to guess at an offseason or signed-out
DOM; it will be frozen only after the real 2026 licensed grid is visible.
"""

from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

from .fantasy_points_downloads import default_profile_dir


OWNERSHIP_URL = "https://www.fantasypoints.com/nfl/projections/dfs/ownership"
PROXY_URL = "https://www.fantasypoints.com/api/proxy"
SURFACE_VERSION = "fantasy-points-ownership-auth-bootstrap-v1"
_HEADING = re.compile(r"^(20\d{2}) NFL DFS OWNERSHIP PROJECTIONS$", re.I)
_RELEVANT_TEXT = re.compile(
    r"draftkings|\bdk\b|nfl|classic|main|slate|week|apply|export|download|csv",
    re.I,
)


def validate_surface_state(
    *,
    url: str,
    headings: Sequence[str],
    sign_in_visible: bool,
    session_uid_present: bool,
    expected_season: int,
) -> dict[str, Any]:
    """Fail closed unless this is an authenticated NFL ownership surface."""
    if not url.startswith(OWNERSHIP_URL):
        raise RuntimeError(f"ownership surface redirected to unexpected URL: {url}")
    if sign_in_visible:
        raise RuntimeError(
            "Fantasy Points ownership session is not authenticated; run "
            "`fantasy-points-ownership login --terminal-credentials`"
        )
    if not session_uid_present:
        raise RuntimeError(
            "Fantasy Points ownership API returned no authenticated session; "
            "run `fantasy-points-ownership login --terminal-credentials`"
        )
    normalized = [" ".join(str(text).split()) for text in headings]
    seasons = {
        int(match.group(1))
        for text in normalized
        if (match := _HEADING.fullmatch(text))
    }
    if seasons != {int(expected_season)}:
        raise RuntimeError(
            "Fantasy Points ownership heading does not identify the expected "
            f"season {expected_season}: {normalized!r}"
        )
    return {
        "version": SURFACE_VERSION,
        "authenticated": True,
        "season": int(expected_season),
        "source_url": url,
    }


def _visible_texts(locator: Any, *, limit: int = 200) -> list[str]:
    values: list[str] = []
    for index in range(min(locator.count(), limit)):
        candidate = locator.nth(index)
        try:
            if not candidate.is_visible():
                continue
            text = " ".join(candidate.inner_text().split())
        except Exception:
            continue
        if text and text not in values:
            values.append(text)
    return values


def _sign_in_button(page: Any) -> Any:
    return page.get_by_role(
        "button", name=re.compile(r"sign in(?: to your account)?", re.I)
    )


def _visible(locator: Any) -> Any | None:
    for index in range(locator.count()):
        candidate = locator.nth(index)
        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    return None


def _open_surface(page: Any, *, timeout_ms: int) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []

    def capture(response: Any) -> None:
        if response.url != PROXY_URL:
            return
        try:
            payload = response.json()
        except Exception:
            return
        if not isinstance(payload, dict) or not isinstance(
            payload.get("session"), dict
        ):
            return
        session = payload["session"]
        table = payload.get("content", {}).get("table", {})
        evidence.append({
            # Never retain or print the UID itself. Presence is the positive
            # authenticated signal missing from the public/signed-out reply.
            "session_uid_present": bool(session.get("uid")),
            "is_offseason": (
                bool(table.get("isOffseason"))
                if isinstance(table, dict) and "isOffseason" in table
                else None
            ),
            "table_title_present": bool(
                isinstance(table, dict) and table.get("title")
            ),
        })

    page.on("response", capture)
    page.goto(OWNERSHIP_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 30_000))
    except Exception:
        # Advertising/analytics can remain active after the application is
        # ready.  All acceptance below is based on rendered first-party state.
        pass
    finally:
        page.remove_listener("response", capture)
    if not evidence:
        raise RuntimeError(
            "Fantasy Points ownership API session response was not observed"
        )
    return evidence[-1]


def _surface_state(
    page: Any, api_evidence: dict[str, Any], *, expected_season: int
) -> dict[str, Any]:
    headings = _visible_texts(page.get_by_role("heading"), limit=50)
    sign_in = _visible(_sign_in_button(page)) is not None
    state = validate_surface_state(
        url=page.url,
        headings=headings,
        sign_in_visible=sign_in,
        session_uid_present=bool(api_evidence.get("session_uid_present")),
        expected_season=expected_season,
    )
    state.update({
        "is_offseason": api_evidence.get("is_offseason"),
        "table_title_present": bool(api_evidence.get("table_title_present")),
    })
    return state


def interactive_login(
    profile_dir: Path,
    timeout_seconds: float,
    *,
    terminal_credentials: bool = False,
    expected_season: int = 2026,
) -> None:
    """Authenticate through the ordinary Fantasy Points account dialog."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            'install browser support with `pip install -e ".[browser]"`'
        ) from exc

    timeout_ms = int(timeout_seconds * 1000)
    with sync_playwright() as playwright:
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            viewport={"width": 1800, "height": 1200},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            api_evidence = _open_surface(page, timeout_ms=timeout_ms)
            if _visible(_sign_in_button(page)) is None:
                _surface_state(
                    page, api_evidence, expected_season=expected_season
                )
                print("Fantasy Points ownership session is already authenticated.")
                return
            _visible(_sign_in_button(page)).click()
            dialog = page.get_by_role("dialog")
            dialog.first.wait_for(state="visible", timeout=timeout_ms)
            if terminal_credentials:
                print(
                    "Credentials fill only the open Fantasy Points dialog; "
                    "they are not logged or saved by this project."
                )
                email = input("Fantasy Points email: ").strip()
                password = getpass.getpass(
                    "Fantasy Points password (input hidden): "
                )
                if not email or not password:
                    raise RuntimeError("email and password are required")
                email_input = dialog.locator(
                    "input[name='email'], input[autocomplete='email'], "
                    "input[type='email']"
                )
                password_input = dialog.locator(
                    "input[name='password'], input[type='password']"
                )
                email_input.first.wait_for(state="visible", timeout=timeout_ms)
                password_input.first.wait_for(state="visible", timeout=timeout_ms)
                email_input.first.fill(email)
                password_input.first.fill(password)
                del password
                submit = dialog.get_by_role(
                    "button", name=re.compile(r"^sign\s*in$", re.I)
                )
                visible_submit = _visible(submit)
                if visible_submit is None:
                    raise RuntimeError("ownership sign-in submit button is missing")
                visible_submit.click()
                try:
                    dialog.first.wait_for(state="hidden", timeout=timeout_ms)
                except Exception as exc:
                    raise RuntimeError(
                        "Fantasy Points ownership sign-in did not complete; "
                        "verify the credentials and any site challenge"
                    ) from exc
            else:
                print("Sign in to Fantasy Points in the opened browser.")
                input(
                    "After the ownership page is visible, press Enter here "
                    "to verify and save the session: "
                )
            api_evidence = _open_surface(page, timeout_ms=timeout_ms)
            _surface_state(
                page, api_evidence, expected_season=expected_season
            )
            print(
                "Ownership login completed; the authenticated browser profile "
                "is saved locally."
            )
        finally:
            context.close()


def verify_login(
    profile_dir: Path,
    timeout_seconds: float,
    *,
    expected_season: int = 2026,
) -> dict[str, Any]:
    """Headlessly prove the normal ownership page is authenticated."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            'install browser support with `pip install -e ".[browser]"`'
        ) from exc
    if not profile_dir.is_dir():
        raise RuntimeError(
            "Fantasy Points browser profile is missing; run "
            "`fantasy-points-ownership login --terminal-credentials`"
        )
    timeout_ms = int(timeout_seconds * 1000)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=True,
            viewport={"width": 1800, "height": 1200},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            api_evidence = _open_surface(page, timeout_ms=timeout_ms)
            state = _surface_state(
                page, api_evidence, expected_season=expected_season
            )
        finally:
            context.close()
    print("Fantasy Points ownership session verified: " + OWNERSHIP_URL)
    return state


def inspect_surface(
    profile_dir: Path,
    timeout_seconds: float,
    *,
    expected_season: int = 2026,
) -> dict[str, Any]:
    """Return only non-sensitive control/header metadata for DOM freezing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            'install browser support with `pip install -e ".[browser]"`'
        ) from exc
    timeout_ms = int(timeout_seconds * 1000)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir), headless=True,
            viewport={"width": 1800, "height": 1200},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            api_evidence = _open_surface(page, timeout_ms=timeout_ms)
            result = _surface_state(
                page, api_evidence, expected_season=expected_season
            )
            buttons = _visible_texts(page.get_by_role("button"))
            comboboxes = _visible_texts(page.get_by_role("combobox"))
            headers = _visible_texts(
                page.locator("th, [role='columnheader']"), limit=300
            )
            result.update({
                "relevant_buttons": [
                    text for text in buttons if _RELEVANT_TEXT.search(text)
                ],
                "relevant_comboboxes": [
                    text for text in comboboxes if _RELEVANT_TEXT.search(text)
                ],
                "column_headers": headers,
                "visible_tables": sum(
                    1 for index in range(page.locator("table").count())
                    if page.locator("table").nth(index).is_visible()
                ),
                "visible_grids": sum(
                    1 for index in range(page.locator("[role='grid']").count())
                    if page.locator("[role='grid']").nth(index).is_visible()
                ),
                "collector_status": "dom-inventory-only-no-row-capture",
            })
        finally:
            context.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fantasy-points-ownership",
        description=(
            "Authenticate and inspect the normal Fantasy Points NFL ownership "
            "surface before freezing its 2026 collector"
        ),
    )
    parser.add_argument("--profile-dir", type=Path, default=default_profile_dir())
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--season", type=int, default=2026)
    commands = parser.add_subparsers(dest="command", required=True)
    login = commands.add_parser("login")
    login.add_argument("--terminal-credentials", action="store_true")
    commands.add_parser("verify-login")
    commands.add_parser("inspect")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "login":
            interactive_login(
                args.profile_dir,
                args.timeout,
                terminal_credentials=args.terminal_credentials,
                expected_season=args.season,
            )
        elif args.command == "verify-login":
            verify_login(
                args.profile_dir, args.timeout, expected_season=args.season
            )
        else:
            inspect_surface(
                args.profile_dir, args.timeout, expected_season=args.season
            )
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "OWNERSHIP_URL",
    "SURFACE_VERSION",
    "inspect_surface",
    "interactive_login",
    "main",
    "validate_surface_state",
    "verify_login",
]
