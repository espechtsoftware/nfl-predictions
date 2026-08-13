"""Auditable Playwright acquisition from SIS DataHub Pro.

Authentication is retained only in a dedicated browser profile outside the
repository. Raw vendor downloads belong below the root-gitignored ``sis/``
directory. The initial command surface deliberately implements and verifies
authentication before bulk export logic is enabled.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from pathlib import Path
from typing import Sequence


BASE_URL = "https://pro.sisdatahub.com"
NFL_LEADERS_URL = f"{BASE_URL}/NFL/Leaders/Players"
AUTH_HOST = "auth.sportsinfosolutions.com"


def default_profile_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "nfl-dfs" / "sis-playwright"


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
                return
            if terminal_credentials:
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
            print("SIS login completed and the persistent session was verified.")
        finally:
            context.close()


def verify_login(profile_dir: Path, timeout_seconds: float) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('install browser support with `pip install -e ".[browser]"`') from exc
    timeout_ms = int(timeout_seconds * 1000)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir), headless=True, viewport={"width": 1800, "height": 1200}
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
        else:
            verify_login(args.profile_dir, args.timeout)
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
