"""Authenticated bootstrap for Fantasy Points projected ownership.

The ownership product is served from ``www.fantasypoints.com`` rather than
the Data Suite host.  The two hosts currently require distinct web sessions,
even though they use the same Fantasy Points account.  This module deliberately
stops at normal-site authentication and a non-sensitive surface inventory,
plus the ``collect`` command frozen on 2026-09-13 once the real 2026 grid was
visible: it reads the site's own table API payload (never the rendered DOM),
fails closed on anonymous sessions, offseason state, soft-gate-locked values
or a season/week mismatch, archives the exact rows create-once in GCS and
appends them to ``nfl_raw.fantasy_points_projected_ownership``.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from .fantasy_points_downloads import default_profile_dir


OWNERSHIP_URL = "https://www.fantasypoints.com/nfl/projections/dfs/ownership"
PROXY_URL = "https://www.fantasypoints.com/api/proxy"
SURFACE_VERSION = "fantasy-points-ownership-auth-bootstrap-v1"
COLLECTOR_VERSION = "fantasy-points-ownership-collector-v1"
TABLE_ROUTE = "/tables/nfl/projections/dfs/ownership"
ARCHIVE_PREFIX = "licensed/fantasy-points/ownership"
BQ_TABLE = "fantasy_points_projected_ownership"
OPERATORS = ("DraftKings", "FanDuel")
ROW_FIELDS = (
    "season", "week", "operator", "name", "position", "team", "salary",
    "projected_ownership_pct", "last_updated",
)
MIN_UNLOCKED_ROWS = 50
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


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(round(float(value)))


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def normalize_ownership_payload(
    payload: dict[str, Any], *, expected_season: int, expected_week: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate one authenticated, unlocked table payload; return rows + receipt.

    Fails closed when the API session is anonymous (the soft gate then masks
    every metric with ``CtaLockValue`` and serves a three-row preview), when
    the table is in offseason state, when the values are locked, or when the
    rows disagree with the expected season/week.  Never touches the DOM.
    """
    session = payload.get("session") if isinstance(payload, dict) else None
    if not isinstance(session, dict) or not session.get("uid"):
        raise RuntimeError("Fantasy Points ownership API returned no session")
    roles = [r for r in (session.get("roles") or []) if isinstance(r, str)]
    if not roles or all(r == "role_anonymous" for r in roles):
        raise RuntimeError(
            "Fantasy Points ownership API session is anonymous (roles="
            f"{roles!r}); run `fantasy-points-ownership login "
            "--terminal-credentials` and retry"
        )
    table = (payload.get("content") or {}).get("table")
    if not isinstance(table, dict):
        raise RuntimeError("ownership payload carries no table")
    if table.get("isOffseason"):
        raise RuntimeError("Fantasy Points ownership table reports offseason")
    values = table.get("values")
    if not isinstance(values, list) or not values:
        raise RuntimeError("ownership table has no values")
    rows: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict) or not value.get("name"):
            raise RuntimeError("ownership value row without a player name")
        rows.append({
            "season": int(value["season"]),
            "week": int(value["week"]),
            "operator": value.get("operator"),
            "name": " ".join(str(value["name"]).split()),
            "position": value.get("fantasyPosition"),
            "team": value.get("team"),
            "salary": _int_or_none(value.get("operatorSalary")),
            "projected_ownership_pct": _float_or_none(
                value.get("projectedOwnershipPercentage")
            ),
            "last_updated": value.get("lastUpdated"),
        })
    seasons = {r["season"] for r in rows}
    weeks = {r["week"] for r in rows}
    if seasons != {int(expected_season)} or weeks != {int(expected_week)}:
        raise RuntimeError(
            f"ownership rows are for season/week {sorted(seasons)}/{sorted(weeks)}, "
            f"expected {expected_season}/{expected_week}"
        )
    locked = sum(1 for r in rows if r["projected_ownership_pct"] is None)
    unlocked = len(rows) - locked
    if unlocked < MIN_UNLOCKED_ROWS:
        raise RuntimeError(
            f"ownership values are locked or truncated: {unlocked} unlocked of "
            f"{len(rows)} rows (soft gate / entitlement); nothing collected"
        )
    operators = sorted({r["operator"] for r in rows if r["operator"]})
    receipt = {
        "title": table.get("title"),
        "rows": len(rows),
        "locked_rows": locked,
        "operators": operators,
        "positions": sorted({r["position"] for r in rows if r["position"]}),
        "teams": len({r["team"] for r in rows if r["team"]}),
        "last_updated_max": max((r["last_updated"] or "") for r in rows),
        "session_roles": roles,
    }
    return rows, receipt


def _redacted(payload: dict[str, Any]) -> dict[str, Any]:
    """The raw payload with the session identity removed (roles retained)."""
    out = dict(payload)
    session = payload.get("session") if isinstance(payload, dict) else None
    if isinstance(session, dict):
        out["session"] = {
            "uid_present": bool(session.get("uid")),
            "roles": [r for r in (session.get("roles") or []) if isinstance(r, str)],
        }
    return out


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _archive_create_once(path: Path, digest: str, season: int, week: int) -> str:
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    from ..config import settings

    name = (
        f"{ARCHIVE_PREFIX}/season={season}/week={week:02d}/sha256={digest}/{path.name}"
    )
    blob = storage.Client().bucket(settings.gcs_bucket).blob(name)
    content_type = "text/csv" if path.suffix == ".csv" else "application/json"
    try:
        blob.upload_from_filename(str(path), content_type=content_type, if_generation_match=0)
    except PreconditionFailed:
        if hashlib.sha256(blob.download_as_bytes()).hexdigest() != digest:
            raise RuntimeError("hash-addressed ownership archive is non-identical")
    return f"gs://{settings.gcs_bucket}/{name}"


def collect_ownership(
    profile_dir: Path,
    timeout_seconds: float,
    *,
    expected_season: int,
    expected_week: int,
    output_root: Path,
    archive: bool = True,
    load: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Capture the Week's projected-ownership rows for every operator the
    site serves, archive them create-once and append them to BigQuery."""
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
    retrieved_at = (now or datetime.now(UTC)).astimezone(UTC)
    timeout_ms = int(timeout_seconds * 1000)
    payloads: list[dict[str, Any]] = []

    def capture(response: Any) -> None:
        if response.url != PROXY_URL:
            return
        try:
            post = response.request.post_data or ""
            body = response.json()
        except Exception:
            return
        if TABLE_ROUTE in post and isinstance(body, dict):
            payloads.append(body)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile_dir), headless=True,
            viewport={"width": 1800, "height": 1200},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.on("response", capture)
            page.goto(OWNERSHIP_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 30_000))
            except Exception:
                pass
            page.wait_for_timeout(2_000)
            # The operator control filters client-side; switching it may also
            # refetch.  Visit every operator so no served row is missed.
            operator_select = page.locator("select").filter(has_text="FanDuel")
            if operator_select.count():
                for operator in OPERATORS:
                    try:
                        operator_select.first.select_option(operator)
                        page.wait_for_timeout(2_500)
                    except Exception:
                        pass
            page.remove_listener("response", capture)
            headings = _visible_texts(page.get_by_role("heading"), limit=50)
            sign_in = _visible(_sign_in_button(page)) is not None
        finally:
            context.close()
    if not payloads:
        raise RuntimeError("no ownership table payload was observed")
    validate_surface_state(
        url=OWNERSHIP_URL, headings=headings, sign_in_visible=sign_in,
        session_uid_present=any(
            isinstance(p.get("session"), dict) and p["session"].get("uid") for p in payloads
        ),
        expected_season=expected_season,
    )
    # Union of every served row across payloads, keyed by operator/player/team.
    merged: dict[tuple, dict[str, Any]] = {}
    receipts = []
    for payload in payloads:
        rows, receipt = normalize_ownership_payload(
            payload, expected_season=expected_season, expected_week=expected_week
        )
        receipts.append(receipt)
        for row in rows:
            merged[(row["operator"], row["name"], row["team"], row["position"])] = row
    rows = sorted(
        merged.values(),
        key=lambda r: (r["operator"] or "", -(r["projected_ownership_pct"] or 0.0), r["name"]),
    )
    stamp = retrieved_at.strftime("%Y%m%dT%H%M%SZ")
    out_dir = output_root / f"season={expected_season}" / f"week={expected_week:02d}" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "ownership-raw.json"
    raw_path.write_text(
        json.dumps([_redacted(p) for p in payloads], indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    csv_path = out_dir / "ownership.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ROW_FIELDS))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in ROW_FIELDS})
    csv_digest = _sha256_file(csv_path)
    manifest: dict[str, Any] = {
        "version": COLLECTOR_VERSION,
        "source_url": OWNERSHIP_URL,
        "table_route": TABLE_ROUTE,
        "season": int(expected_season),
        "week": int(expected_week),
        "retrieved_at_utc": retrieved_at.isoformat(),
        "payloads_observed": len(payloads),
        "rows": len(rows),
        "rows_by_operator": {
            op: sum(1 for r in rows if r["operator"] == op) for op in sorted({r["operator"] for r in rows})
        },
        "receipts": receipts,
        "files": {
            "ownership.csv": {"sha256": csv_digest, "bytes": csv_path.stat().st_size},
            "ownership-raw.json": {"sha256": _sha256_file(raw_path), "bytes": raw_path.stat().st_size},
        },
        "archive": {},
        "bigquery": None,
    }
    if archive:
        manifest["archive"]["ownership.csv"] = _archive_create_once(csv_path, csv_digest, expected_season, expected_week)
        manifest["archive"]["ownership-raw.json"] = _archive_create_once(raw_path, csv_digest, expected_season, expected_week)
    if load:
        import pandas as pd

        from ..bq import load_dataframe
        from ..config import settings

        frame = pd.DataFrame(rows, columns=list(ROW_FIELDS))
        frame["last_updated"] = pd.to_datetime(frame["last_updated"], utc=True, errors="coerce")
        frame["salary"] = frame["salary"].astype("Int64")
        frame["retrieved_at"] = retrieved_at
        frame["source_sha256"] = csv_digest
        frame["source_url"] = OWNERSHIP_URL
        frame["collector_version"] = COLLECTOR_VERSION
        table_ref = f"{settings.raw}.{BQ_TABLE}"
        load_dataframe(frame, table_ref, write_disposition="WRITE_APPEND")
        manifest["bigquery"] = {"table": table_ref, "rows": int(len(frame))}
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if archive:
        _archive_create_once(manifest_path, csv_digest, expected_season, expected_week)
    print(json.dumps({k: v for k, v in manifest.items() if k != "receipts"}, indent=2, sort_keys=True))
    return manifest


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
    collect = commands.add_parser("collect", help="capture the week's projected-ownership rows (all operators), archive create-once, append to BigQuery")
    collect.add_argument("--week", type=int, required=True)
    collect.add_argument("--output-root", type=Path, default=default_profile_dir().parent / "fantasy-points-ownership")
    collect.add_argument("--no-archive", action="store_true")
    collect.add_argument("--no-load", action="store_true")
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
        elif args.command == "collect":
            collect_ownership(
                args.profile_dir, args.timeout, expected_season=args.season,
                expected_week=args.week, output_root=args.output_root,
                archive=not args.no_archive, load=not args.no_load,
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
    "COLLECTOR_VERSION",
    "OWNERSHIP_URL",
    "SURFACE_VERSION",
    "collect_ownership",
    "normalize_ownership_payload",
    "inspect_surface",
    "interactive_login",
    "main",
    "validate_surface_state",
    "verify_login",
]
