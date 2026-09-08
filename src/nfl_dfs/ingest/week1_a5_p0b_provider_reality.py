"""Local, outcome-blind Week-1 DraftKings acceptance-download rehearsal.

The default command is inert.  The separately confirmed ``audit`` command
performs one authenticated GET through a private Playwright storage-state
file, validates every redirect before the next contact, and writes only
redacted structural evidence to local create-once files.

This is not a deployment-certification, activation, publication, contest-entry
or outcome-reading path.  It has no cloud or gcloud surface and does not fill
any live pin.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import stat
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path
from types import MappingProxyType
from typing import Final, Protocol
from urllib.parse import urljoin, urlsplit

from nfl_dfs.ingest import week1_a5_capture_contracts as capture
from nfl_dfs.ingest import week1_a5_dk_acquisition as acquisition
from nfl_dfs.ingest import week1_a5_dk_acquisition_pins as live_pins
from nfl_dfs.ingest import week1_a5_governed_capture_v3 as capture_v3

PLAN_SCHEMA: Final = "week1-a5-capture-v3-p0b-local-rehearsal-plan/v1"
INTENT_SCHEMA: Final = "week1-a5-capture-v3-p0b-local-rehearsal-intent/v1"
EVIDENCE_SCHEMA: Final = "week1-a5-capture-v3-p0b-local-rehearsal-evidence/v1"
RECEIPT_SCHEMA: Final = "week1-a5-capture-v3-p0b-local-rehearsal-receipt/v1"
CONFIRMATION_PHRASE: Final = "rehearse-week1-a5-acceptance-download-v1"

SESSION_PROFILE: Final = acquisition.COLLECTOR_SESSION_PROFILE
MAX_PRIVATE_FILE_BYTES: Final = 4 * 1024 * 1024
MAX_RESPONSE_BYTES: Final = 8 * 1024 * 1024
_REDIRECT_STATUSES: Final = frozenset({301, 302, 303, 307, 308})
_FORBIDDEN_PATH_SEGMENTS: Final = frozenset(
    {
        "auth",
        "create",
        "draft",
        "edit",
        "enter",
        "entry",
        "import",
        "join",
        "leaderboard",
        "login",
        "logout",
        "purchase",
        "register",
        "results",
        "save",
        "scores",
        "signin",
        "sso",
        "standings",
        "submit",
        "swap",
        "upload",
    }
)
_FORBIDDEN_PATH_MARKERS: Final = frozenset(
    {
        "auth",
        "create",
        "draft",
        "edit",
        "enter",
        "entry",
        "import",
        "join",
        "leaderboard",
        "login",
        "logout",
        "purchase",
        "register",
        "results",
        "save",
        "scores",
        "signin",
        "sso",
        "standings",
        "submit",
        "swap",
        "upload",
    }
)

# These are code-owned endpoint families, not caller-provided suffix matches.
# A new provider/CDN family requires a reviewed source change; an observed
# redirect is never used as authority for its own subsequent contact.
FIXED_DRAFTKINGS_HTTPS_FAMILIES: Final = (
    acquisition.LocatorFamily("https", "www.draftkings.com", "/lineup/", 443),
    acquisition.LocatorFamily("https", "www.draftkings.com", "/mycontests/", 443),
)
FIXED_FAMILY_ROWS: Final = tuple(
    MappingProxyType(family.as_dict()) for family in FIXED_DRAFTKINGS_HTTPS_FAMILIES
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")


class Week1A5P0BProviderRealityError(RuntimeError):
    """The local provider-reality rehearsal failed closed."""


def _fail(message: str) -> None:
    raise Week1A5P0BProviderRealityError(message)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _seal(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        _fail(f"{field} is already present")
    sealed = dict(value)
    sealed[field] = _canonical_sha(sealed)
    return sealed


def _module_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact(value: Mapping[str, object], fields: set[str], *, label: str) -> None:
    if set(value) != fields:
        _fail(
            f"{label} fields differ: missing={sorted(fields - set(value))} "
            f"unexpected={sorted(set(value) - fields)}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{label} must be a canonical nonempty string")
    if "\r" in value or "\n" in value or "\x00" in value:
        _fail(f"{label} contains a forbidden control character")
    return value


def _timestamp(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise Week1A5P0BProviderRealityError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(f"{label} must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _family_rows() -> list[dict[str, object]]:
    return [dict(row) for row in FIXED_FAMILY_ROWS]


def _assert_all_pins_absent() -> None:
    pins = {
        name: value
        for name, value in vars(live_pins).items()
        if name.startswith("PINNED_")
    }
    pins["PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR"] = (
        capture.PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR
    )
    if not pins or any(value is not None for value in pins.values()):
        _fail("local rehearsal requires every activation/live pin to remain absent")


def validate_intent_v1(value: object) -> dict[str, object]:
    """Validate one canonical, independently reviewed pre-contact intent."""

    row = _mapping(value, label="local rehearsal intent")
    _exact(
        row,
        {
            "schema_version",
            "created_at_utc",
            "rehearsal_module_sha256",
            "collector_module_sha256",
            "contest_role",
            "http_method",
            "session_profile",
            "fixed_locator_families",
            "maximum_redirects",
            "capture_v3_schema",
            "provider_contact_authorized",
            "cloud_contact_authorized",
            "cloud_mutation_authorized",
            "gcs_publication_authorized",
            "pin_change_authorized",
            "contest_entry_authorized",
            "outcome_or_standings_access_authorized",
            "legacy_v2_live_fallback_authorized",
            "intent_sha256",
        },
        label="local rehearsal intent",
    )
    if row["schema_version"] != INTENT_SCHEMA:
        _fail("local rehearsal intent schema differs")
    claimed = row.pop("intent_sha256")
    if type(claimed) is not str or claimed != _canonical_sha(row):
        _fail("local rehearsal intent hash differs")
    normalized_created_at = _timestamp(
        row["created_at_utc"], label="intent creation time"
    )
    if normalized_created_at != row["created_at_utc"]:
        _fail("local rehearsal intent creation time is not canonical UTC")
    row["created_at_utc"] = normalized_created_at
    for field in ("rehearsal_module_sha256", "collector_module_sha256"):
        digest = _string(row[field], label=field)
        if _SHA.fullmatch(digest) is None:
            _fail(f"{field} is not an exact SHA-256")
    role = _string(row["contest_role"], label="contest role")
    if role not in capture.A5_ROLE_TABLE:
        _fail("contest role is outside exact Week-1 A5")
    if row["http_method"] != "GET":
        _fail("local rehearsal intent must bind GET only")
    if row["session_profile"] != SESSION_PROFILE:
        _fail("local rehearsal session profile differs")
    if row["fixed_locator_families"] != _family_rows():
        _fail("local rehearsal locator families differ from code-owned authority")
    if row["maximum_redirects"] != acquisition.MAX_REDIRECTS:
        _fail("local rehearsal redirect bound differs")
    if row["capture_v3_schema"] != capture_v3.ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA:
        _fail("local rehearsal does not bind the accepted capture-v3 schema")
    expected_authorizations = {
        "provider_contact_authorized": True,
        "cloud_contact_authorized": False,
        "cloud_mutation_authorized": False,
        "gcs_publication_authorized": False,
        "pin_change_authorized": False,
        "contest_entry_authorized": False,
        "outcome_or_standings_access_authorized": False,
        "legacy_v2_live_fallback_authorized": False,
    }
    if any(
        row[field] is not expected
        for field, expected in expected_authorizations.items()
    ):
        _fail("local rehearsal intent grants a forbidden operation")
    row["intent_sha256"] = claimed
    return row


def plan_v1() -> dict[str, object]:
    """Return the inert local-rehearsal contract."""

    body: dict[str, object] = {
        "schema_version": PLAN_SCHEMA,
        "mode": "no-contact-plan",
        "confirmation_phrase": CONFIRMATION_PHRASE,
        "accepted_collector_module_sha256": acquisition._module_sha256(),
        "rehearsal_module_sha256": _module_sha256(),
        "session_profile": SESSION_PROFILE,
        "capture_v3_schema": capture_v3.ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA,
        "http_method": "GET",
        "maximum_redirects": acquisition.MAX_REDIRECTS,
        "fixed_locator_families": _family_rows(),
        "private_inputs": {
            "playwright_storage_state_file": "owner-only regular mode-0600",
            "acceptance_locator_file": "owner-only regular mode-0600",
            "persisted_or_printed": False,
        },
        "provider_contacted": False,
        "cloud_contacted": False,
        "cloud_mutation_authorized": False,
        "gcs_publication_authorized": False,
        "pin_change_authorized": False,
        "contest_entry_authorized": False,
        "outcome_or_standings_access_authorized": False,
        "legacy_v2_live_fallback_authorized": False,
    }
    return _seal(body, field="plan_sha256")


def build_intent_v1(*, created_at_utc: object, contest_role: object) -> dict[str, object]:
    """Build a canonical review artifact without reading a credential or network."""

    body: dict[str, object] = {
        "schema_version": INTENT_SCHEMA,
        "created_at_utc": _timestamp(created_at_utc, label="intent creation time"),
        "rehearsal_module_sha256": _module_sha256(),
        "collector_module_sha256": acquisition._module_sha256(),
        "contest_role": _string(contest_role, label="contest role"),
        "http_method": "GET",
        "session_profile": SESSION_PROFILE,
        "fixed_locator_families": _family_rows(),
        "maximum_redirects": acquisition.MAX_REDIRECTS,
        "capture_v3_schema": capture_v3.ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA,
        "provider_contact_authorized": True,
        "cloud_contact_authorized": False,
        "cloud_mutation_authorized": False,
        "gcs_publication_authorized": False,
        "pin_change_authorized": False,
        "contest_entry_authorized": False,
        "outcome_or_standings_access_authorized": False,
        "legacy_v2_live_fallback_authorized": False,
    }
    return validate_intent_v1(_seal(body, field="intent_sha256"))


def _read_private_regular(path: Path, *, label: str) -> bytes:
    """Read an owner-only file without following its terminal path component."""

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise Week1A5P0BProviderRealityError(
            f"private {label} is unavailable"
        ) from None
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.geteuid()
            or metadata.st_nlink != 1
            or metadata.st_size < 1
            or metadata.st_size > MAX_PRIVATE_FILE_BYTES
        ):
            _fail(f"private {label} must be one owner-only mode-0600 regular file")
        chunks: list[bytes] = []
        remaining = MAX_PRIVATE_FILE_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if not raw or len(raw) != metadata.st_size or len(raw) > MAX_PRIVATE_FILE_BYTES:
            _fail(f"private {label} changed during its exact read")
        return raw
    finally:
        os.close(descriptor)


def _playwright_cookies(raw: bytes) -> tuple[dict[str, object], ...]:
    """Validate storage-state bytes and retain only in-memory DK cookies."""

    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Week1A5P0BProviderRealityError(
            "private Playwright storage state is invalid JSON"
        ) from None
    state = _mapping(value, label="Playwright storage state")
    cookies: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw_cookie in _sequence(state.get("cookies"), label="Playwright cookies"):
        cookie = _mapping(raw_cookie, label="Playwright cookie")
        name = _string(cookie.get("name"), label="Playwright cookie name")
        secret_value = _string(cookie.get("value"), label="Playwright cookie value")
        domain = _string(cookie.get("domain"), label="Playwright cookie domain")
        normalized_domain = domain.lstrip(".").lower()
        path = _string(cookie.get("path", "/"), label="Playwright cookie path")
        if normalized_domain != "draftkings.com" and not normalized_domain.endswith(
            ".draftkings.com"
        ):
            continue
        if not path.startswith("/"):
            _fail("Playwright DraftKings cookie path is invalid")
        key = (name, domain.lower(), path)
        if key in seen:
            _fail("Playwright storage state repeats a DraftKings cookie")
        seen.add(key)
        secure = cookie.get("secure", True)
        if type(secure) is not bool:
            _fail("Playwright DraftKings cookie secure flag is invalid")
        cookies.append(
            {
                "name": name,
                "value": secret_value,
                "domain": domain,
                "path": path,
                "secure": secure,
            }
        )
    if not cookies:
        _fail("private Playwright storage state contains no DraftKings cookie")
    return tuple(cookies)


def _acceptance_locator(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Week1A5P0BProviderRealityError(
            "private acceptance locator is not UTF-8"
        ) from None
    text = text.removesuffix("\n")
    if not text or text != text.strip() or "\r" in text or "\n" in text:
        _fail("private acceptance locator must be one canonical line")
    canonical = acquisition._canonical_url(text, label="private acceptance locator")
    if canonical != text:
        _fail("private acceptance locator is not in canonical URL form")
    return _admit_locator(canonical, label="private acceptance locator")


def _is_forbidden_surface(locator: str) -> bool:
    segments = {
        re.sub(r"[^a-z0-9]+", "", segment.casefold())
        for segment in urlsplit(locator).path.split("/")
        if segment
    }
    return bool(
        segments & _FORBIDDEN_PATH_SEGMENTS
        or any(
            marker in segment
            for segment in segments
            for marker in _FORBIDDEN_PATH_MARKERS
        )
    )


def _admit_locator(locator: object, *, label: str) -> str:
    if type(locator) is not str:
        _fail(f"{label} is not a canonical locator")
    raw_path = urlsplit(locator).path
    if (
        any(
            ord(character) <= 32 or ord(character) == 127 or ord(character) > 127
            for character in locator
        )
        or "\\" in raw_path
        or "%" in raw_path
        or any(segment in {".", ".."} for segment in raw_path.split("/"))
    ):
        _fail(f"{label} contains an ambiguous path encoding")
    retained = acquisition._canonical_url(locator, label=label)
    if not any(family.accepts(retained) for family in FIXED_DRAFTKINGS_HTTPS_FAMILIES):
        _fail(f"{label} is outside the fixed DraftKings HTTPS families")
    if _is_forbidden_surface(retained):
        _fail(f"{label} resolves to a rejected auth, action, or outcome surface")
    return retained


class _Response(Protocol):
    url: str
    status_code: int
    headers: Mapping[str, str]
    history: Sequence[object]

    def iter_content(
        self, *, chunk_size: int, decode_unicode: bool
    ) -> Iterable[bytes]: ...


class _CookieJar(Protocol):
    def set(self, name: str, value: str, **kwargs: object) -> object: ...


class _Session(Protocol):
    cookies: _CookieJar

    def get(self, locator: str, **kwargs: object) -> _Response: ...


@dataclass
class _LocalAcceptanceTransport:
    cookies: tuple[dict[str, object], ...]
    session_factory: Callable[[], _Session]

    def _new_session(self) -> _Session:
        return self.session_factory()

    def perform(self, *, method: str, locator: str) -> acquisition.TransportEvent:
        if method != "GET":
            _fail("local acceptance rehearsal permits GET only")
        current = _admit_locator(locator, label="initial acceptance locator")
        try:
            session = self._new_session()
        except Week1A5P0BProviderRealityError:
            raise
        except Exception:  # noqa: BLE001 - redact arbitrary session-factory detail
            raise Week1A5P0BProviderRealityError(
                "local HTTP session construction failed; exception detail was not retained"
            ) from None
        close = getattr(session, "close", None)
        try:
            try:
                session.trust_env = False  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001 - redact arbitrary adapter detail
                raise Week1A5P0BProviderRealityError(
                    "local HTTP session cannot disable environment credentials"
                ) from None
            for cookie in self.cookies:
                session.cookies.set(
                    str(cookie["name"]),
                    str(cookie["value"]),
                    domain=str(cookie["domain"]),
                    path=str(cookie["path"]),
                    secure=bool(cookie["secure"]),
                )
            headers = {
                "Accept": "text/csv,*/*;q=0.1",
                "Accept-Encoding": "identity",
                "User-Agent": "nfl-dfs-week1-local-acceptance-rehearsal/1",
            }
            seen: set[str] = set()
            hops: list[acquisition.TransportHop] = []
            terminal: _Response | None = None
            for redirect_count in range(acquisition.MAX_REDIRECTS + 1):
                if current in seen:
                    _fail("DraftKings redirect loop was rejected before re-contact")
                seen.add(current)
                try:
                    response = session.get(
                        current,
                        allow_redirects=False,
                        timeout=(10, 120),
                        headers=headers,
                        stream=True,
                        verify=True,
                    )
                except Exception:  # noqa: BLE001 - redact arbitrary network detail
                    raise Week1A5P0BProviderRealityError(
                        "DraftKings request failed; exception detail was not retained"
                    ) from None
                if getattr(response, "history", ()):
                    _fail("HTTP adapter followed an unreviewed redirect internally")
                response_locator = _admit_locator(
                    getattr(response, "url", None),
                    label="provider response locator",
                )
                if response_locator != current:
                    _fail("provider response locator differs from requested hop")
                status_code = getattr(response, "status_code", None)
                if type(status_code) is not int or not 100 <= status_code <= 599:
                    _fail("provider response status is invalid")
                response_headers = getattr(response, "headers", None)
                if not isinstance(response_headers, Mapping):
                    _fail("provider response headers are unavailable")
                location = response_headers.get("Location")
                if status_code in _REDIRECT_STATUSES:
                    if type(location) is not str or not location:
                        _fail("DraftKings redirect omits its Location target")
                    # Admission occurs here, before another session.get call.
                    next_locator = _admit_locator(
                        urljoin(current, location), label="redirect target"
                    )
                    hops.append(
                        acquisition.TransportHop(current, status_code, location)
                    )
                    if redirect_count == acquisition.MAX_REDIRECTS:
                        _fail("DraftKings redirect count exceeds the exact bound")
                    if next_locator in seen:
                        _fail("DraftKings redirect loop was rejected before re-contact")
                    current = next_locator
                    continue
                if 300 <= status_code <= 399:
                    _fail("DraftKings returned an unsupported redirect status")
                if location is not None:
                    _fail("nonredirect DraftKings response contains Location")
                if status_code != 200:
                    _fail("DraftKings terminal response is not exact HTTP 200")
                content_encoding = response_headers.get("Content-Encoding")
                if content_encoding not in (None, "", "identity"):
                    _fail("DraftKings response uses an unreviewed content encoding")
                content_length = response_headers.get("Content-Length")
                if content_length is not None and (
                    not str(content_length).isdigit()
                    or int(str(content_length)) > MAX_RESPONSE_BYTES
                ):
                    _fail("DraftKings response Content-Length is invalid or oversized")
                _content_type(response_headers.get("Content-Type"))
                _content_disposition(response_headers.get("Content-Disposition"))
                hops.append(acquisition.TransportHop(current, status_code, None))
                terminal = response
                break
            if terminal is None:
                _fail("DraftKings response chain has no terminal response")
            iter_content = getattr(terminal, "iter_content", None)
            if not callable(iter_content):
                _fail("DraftKings terminal response has no bounded body stream")
            chunks: list[bytes] = []
            body_bytes = 0
            try:
                for chunk in iter_content(chunk_size=65_536, decode_unicode=False):
                    if not isinstance(chunk, bytes):
                        _fail("DraftKings terminal response body stream is malformed")
                    if not chunk:
                        continue
                    body_bytes += len(chunk)
                    if body_bytes > MAX_RESPONSE_BYTES:
                        _fail("DraftKings terminal response body is oversized")
                    chunks.append(chunk)
            except Week1A5P0BProviderRealityError:
                raise
            except Exception:  # noqa: BLE001 - redact arbitrary stream detail
                raise Week1A5P0BProviderRealityError(
                    "DraftKings response-body read failed; exception detail was not retained"
                ) from None
            body = b"".join(chunks)
            if not body:
                _fail("DraftKings terminal response body is empty or malformed")
            content_length = terminal.headers.get("Content-Length")
            if content_length is not None and int(str(content_length)) != len(body):
                _fail("DraftKings response Content-Length differs from body bytes")
            return acquisition.TransportEvent(
                body=body,
                observed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                hops=tuple(hops),
                response_content_type=str(terminal.headers.get("Content-Type", "")),
                response_content_disposition=(
                    str(terminal.headers["Content-Disposition"])
                    if "Content-Disposition" in terminal.headers
                    else None
                ),
                session_profile=SESSION_PROFILE,
            )
        except Week1A5P0BProviderRealityError:
            raise
        except Exception:  # noqa: BLE001 - redact arbitrary adapter detail
            raise Week1A5P0BProviderRealityError(
                "local HTTP session failed; exception detail was not retained"
            ) from None
        finally:
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001 - redact arbitrary close detail
                    raise Week1A5P0BProviderRealityError(
                        "local HTTP session close failed; exception detail was not retained"
                    ) from None


def _redacted_locator(locator: str) -> dict[str, object]:
    retained = _admit_locator(locator, label="locator projection")
    parsed = urlsplit(retained)
    family = next(
        family for family in FIXED_DRAFTKINGS_HTTPS_FAMILIES if family.accepts(retained)
    )
    return {
        "scheme": "https",
        "host": parsed.hostname,
        "port": parsed.port or 443,
        "reviewed_path_prefix": family.path_prefix,
        "path_suffix_present": parsed.path != family.path_prefix,
        "query_present": bool(parsed.query),
        "path_suffix_retained": False,
        "query_names_or_values_retained": False,
    }


def _content_disposition(value: object) -> dict[str, object]:
    text = _string(value, label="response content disposition")
    message = Message()
    message["Content-Disposition"] = text
    if message.get_content_disposition() != "attachment":
        _fail("DraftKings response is not an attachment")
    parameters = message.get_params(header="content-disposition", unquote=True) or []
    if len(parameters) != 2 or str(parameters[1][0]).casefold() != "filename":
        _fail("DraftKings attachment disposition parameters differ")
    filename = message.get_filename()
    if (
        type(filename) is not str
        or len(filename) > 128
        or re.fullmatch(r"[A-Za-z0-9 ._()\[\]-]+\.csv", filename, re.IGNORECASE) is None
    ):
        _fail("DraftKings attachment does not name a CSV")
    return {
        "disposition": "attachment",
        "filename_present": True,
        "filename_extension": ".csv",
        "raw_header_retained": False,
    }


def _content_type(value: object) -> dict[str, object]:
    text = _string(value, label="response content type")
    message = Message()
    message["Content-Type"] = text
    media_type = message.get_content_type().casefold()
    charset = message.get_content_charset()
    parameters = message.get_params(header="content-type") or []
    if (
        media_type != "text/csv"
        or charset not in {None, "utf-8", "utf8"}
        or any(str(key).casefold() != "charset" for key, _ in parameters[1:])
        or len({str(key).casefold() for key, _ in parameters[1:]})
        != len(parameters[1:])
    ):
        _fail("DraftKings response media type is not text/csv")
    return {
        "media_type": "text/csv",
        "charset": charset,
        "raw_content_type_retained": False,
    }


def _normalize_transport_event(
    event: object, *, request_locator: str
) -> dict[str, object]:
    if not isinstance(event, acquisition.TransportEvent):
        _fail("local transport returned another event type")
    if event.session_profile != SESSION_PROFILE:
        _fail("local transport session profile differs")
    if not isinstance(event.body, bytes) or not event.body:
        _fail("local transport response body is empty")
    if not event.hops:
        _fail("local transport response chain is empty")
    raw_locators: list[str] = []
    hops: list[dict[str, object]] = []
    for ordinal, hop in enumerate(event.hops):
        if not isinstance(hop, acquisition.TransportHop):
            _fail("local transport chain contains another hop type")
        locator = _admit_locator(hop.locator, label=f"transport hop {ordinal}")
        target = (
            _admit_locator(
                urljoin(locator, hop.redirect_target),
                label=f"transport hop {ordinal} redirect",
            )
            if hop.redirect_target is not None
            else None
        )
        if ordinal < len(event.hops) - 1:
            if hop.status not in _REDIRECT_STATUSES or target is None:
                _fail("nonterminal response is not an admitted redirect")
        elif type(hop.status) is not int or hop.status != 200 or target:
            _fail("terminal response is not a nonredirect exact HTTP 200")
        raw_locators.append(locator)
        hops.append(
            {
                "ordinal": ordinal,
                "status": hop.status,
                "locator": _redacted_locator(locator),
                "redirect_target": (
                    _redacted_locator(target) if target is not None else None
                ),
            }
        )
    if raw_locators[0] != request_locator:
        _fail("transport chain does not start at the reviewed locator")
    for ordinal, hop in enumerate(event.hops[:-1]):
        expected_next = _admit_locator(
            urljoin(raw_locators[ordinal], str(hop.redirect_target)),
            label="redirect continuity target",
        )
        if expected_next != raw_locators[ordinal + 1]:
            _fail("transport redirect chain is discontinuous")
    content_type = _content_type(event.response_content_type)
    disposition = _content_disposition(event.response_content_disposition)
    return {
        "request_method": "GET",
        "requested_locator": _redacted_locator(request_locator),
        "effective_locator": _redacted_locator(raw_locators[-1]),
        "redirect_chain": hops,
        "http_response_count": len(hops),
        "redirect_count": len(hops) - 1,
        "terminal_status": event.hops[-1].status,
        **content_type,
        "content_disposition": disposition,
        "observed_at_utc": _timestamp(event.observed_at, label="transport observation"),
        "body_bytes": len(event.body),
        "body_sha256": hashlib.sha256(event.body).hexdigest(),
        "query_values_retained": False,
        "cookie_values_retained": False,
        "response_body_retained": False,
    }


def _response_shape(raw: bytes, *, contest_role: str) -> dict[str, object]:
    """Validate provider bytes while retaining no row or roster value."""

    inspection = capture.inspect_acceptance_provider_bytes_v1(
        raw, contest_role=contest_role
    )
    try:
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    except UnicodeDecodeError as exc:  # guarded by the accepted parser too
        raise Week1A5P0BProviderRealityError(
            "DraftKings attachment is not UTF-8 CSV"
        ) from exc
    expected_header = [
        "Entry ID",
        "Contest Name",
        "Contest ID",
        "Entry Fee",
        *capture.CLASSIC_SLOTS,
    ]
    header_index = next(
        (
            ordinal
            for ordinal, row in enumerate(rows)
            if [cell.strip().lstrip("\ufeff") for cell in row] == expected_header
        ),
        None,
    )
    if header_index != 0:
        _fail("DraftKings attachment does not begin with the exact DKEntries header")
    widths = {
        len(row) for row in rows[header_index:] if any(cell.strip() for cell in row)
    }
    if widths != {len(expected_header)}:
        _fail("DraftKings attachment row widths differ from the exact header")
    pin = capture.A5_ROLE_TABLE[contest_role]
    return {
        "shape_schema": inspection["schema_version"],
        "source_profile": inspection["source_profile"],
        "contest_role": pin.role,
        "expected_role_entry_count": pin.planned_entries,
        "observed_role_entry_count": inspection["entry_count"],
        "unique_role_entry_count": inspection["unique_entry_count"],
        "exact_header": expected_header,
        "header_ordinal": header_index,
        "all_nonempty_rows_exact_width": True,
        "all_role_rows_match_exact_contest_name_id_and_fee": True,
        "all_role_rosters_have_nine_unique_draftables": inspection[
            "all_rosters_have_nine_unique_draftables"
        ],
        "row_values_retained": False,
        "roster_values_retained": False,
        "entry_projection_retained": False,
    }


def _rehearse_acceptance_download_v1(
    *,
    intent: object,
    storage_state: bytes,
    acceptance_locator: str,
    session_factory: Callable[[], _Session],
) -> dict[str, dict[str, object]]:
    """Run one local provider rehearsal without any cloud or publication path."""

    retained = validate_intent_v1(intent)
    _assert_all_pins_absent()
    if retained["rehearsal_module_sha256"] != _module_sha256():
        _fail("running rehearsal module differs from the reviewed intent")
    if retained["collector_module_sha256"] != acquisition._module_sha256():
        _fail("accepted collector module differs from the reviewed intent")
    cookies = _playwright_cookies(storage_state)
    locator = _admit_locator(acceptance_locator, label="acceptance locator")
    event = _LocalAcceptanceTransport(
        cookies=cookies, session_factory=session_factory
    ).perform(method="GET", locator=locator)
    transport = _normalize_transport_event(event, request_locator=locator)
    shape = _response_shape(event.body, contest_role=str(retained["contest_role"]))
    evidence = _seal(
        {
            "schema_version": EVIDENCE_SCHEMA,
            "intent_sha256": retained["intent_sha256"],
            "rehearsal_module_sha256": retained["rehearsal_module_sha256"],
            "collector_module_sha256": retained["collector_module_sha256"],
            "capture_v3_schema": retained["capture_v3_schema"],
            "private_storage_state_validated": True,
            "private_acceptance_locator_validated": True,
            "transport": transport,
            "response_shape": shape,
            "provider_bytes_published": False,
            "cloud_contacted": False,
            "cloud_mutation_performed": False,
            "gcs_object_published": False,
            "activation_pin_changed": False,
            "contest_entry_performed": False,
            "outcome_or_standings_accessed": False,
            "legacy_v2_live_fallback_used": False,
        },
        field="evidence_sha256",
    )
    receipt = _seal(
        {
            "schema_version": RECEIPT_SCHEMA,
            "observed_at_utc": transport["observed_at_utc"],
            "intent_sha256": retained["intent_sha256"],
            "evidence_sha256": evidence["evidence_sha256"],
            "provider_rehearsal_complete": True,
            "provider_bytes_published": False,
            "cloud_contacted": False,
            "cloud_mutation_performed": False,
            "gcs_object_published": False,
            "activation_pin_changed": False,
            "contest_entry_performed": False,
            "outcome_or_standings_accessed": False,
            "legacy_v2_live_fallback_used": False,
            "release_gate": "HOLD_FOR_INDEPENDENT_REVIEW_AND_PIN_ONLY_SUCCESSOR",
        },
        field="receipt_sha256",
    )
    return {"evidence": evidence, "receipt": receipt}


def _read_canonical_intent(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Week1A5P0BProviderRealityError(
            "local rehearsal intent is unavailable or invalid JSON"
        ) from exc
    if raw != _canonical_bytes(value):
        _fail("local rehearsal intent is not canonical JSON")
    return validate_intent_v1(value)


def _reserve_private_create_once(path: Path, *, label: str) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise Week1A5P0BProviderRealityError(f"refusing to overwrite {label}") from exc
    except OSError as exc:
        raise Week1A5P0BProviderRealityError(f"cannot create {label}") from exc
    try:
        os.fchmod(descriptor, 0o600)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.geteuid()
            or metadata.st_nlink != 1
            or metadata.st_size != 0
        ):
            _fail(f"reserved {label} is not one private empty regular file")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _write_reserved(descriptor: int, value: object, *, label: str) -> None:
    metadata = os.fstat(descriptor)
    if metadata.st_size != 0 or os.lseek(descriptor, 0, os.SEEK_CUR) != 0:
        _fail(f"reserved {label} changed before its write")
    view = memoryview(_canonical_bytes(value))
    while view:
        written = os.write(descriptor, view)
        if written < 1:
            _fail(f"create-once {label} write did not progress")
        view = view[written:]
    os.fsync(descriptor)


def _write_private_create_once(path: Path, value: object, *, label: str) -> None:
    descriptor = _reserve_private_create_once(path, label=label)
    try:
        _write_reserved(descriptor, value, label=label)
    finally:
        os.close(descriptor)


def _path_exists_no_follow(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise Week1A5P0BProviderRealityError(
            "local output path cannot be inspected"
        ) from exc
    return True


def _reserve_evidence_directory(path: Path) -> None:
    try:
        path.mkdir(mode=0o700, parents=False, exist_ok=False)
        os.chmod(path, 0o700)
        metadata = path.lstat()
    except OSError as exc:
        raise Week1A5P0BProviderRealityError(
            "local evidence directory cannot be reserved"
        ) from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
    ):
        _fail("local evidence directory is not one private mode-0700 directory")


def _assert_private_output_parent(evidence_directory: Path, receipt: Path) -> None:
    evidence_parent = evidence_directory.parent
    receipt_parent = receipt.parent
    if evidence_parent != receipt_parent:
        _fail("local evidence and receipt must share one private parent directory")
    try:
        metadata = evidence_parent.lstat()
    except OSError:
        raise Week1A5P0BProviderRealityError(
            "local output parent directory is unavailable"
        ) from None
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
    ):
        _fail("local output parent must be one owner-only mode-0700 directory")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("plan", help="render the inert local rehearsal plan")
    intent = subparsers.add_parser(
        "intent", help="render one offline canonical pre-contact intent"
    )
    intent.add_argument("--created-at-utc", required=True)
    intent.add_argument("--contest-role", required=True)
    audit = subparsers.add_parser(
        "audit", help="perform one explicitly confirmed local provider rehearsal"
    )
    audit.add_argument("--confirm", required=True)
    audit.add_argument("--intent", required=True, type=Path)
    audit.add_argument("--storage-state-file", required=True, type=Path)
    audit.add_argument("--acceptance-locator-file", required=True, type=Path)
    audit.add_argument("--evidence-directory", required=True, type=Path)
    audit.add_argument("--receipt", required=True, type=Path)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory: Callable[[], _Session] | None = None,
) -> int:
    args = _parser().parse_args(argv)
    if args.command in {None, "plan"}:
        sys.stdout.buffer.write(_canonical_bytes(plan_v1()))
        return 0
    if args.command == "intent":
        try:
            intent = build_intent_v1(
                created_at_utc=args.created_at_utc,
                contest_role=args.contest_role,
            )
        except Week1A5P0BProviderRealityError as exc:
            print(f"local Week-1 intent HOLD: {exc}", file=sys.stderr)
            return 2
        sys.stdout.buffer.write(_canonical_bytes(intent))
        return 0
    try:
        if args.confirm != CONFIRMATION_PHRASE:
            _fail("local rehearsal confirmation phrase differs")
        # All caller-controlled intent, path, mode, ownership and collision
        # checks occur before a requests Session can be constructed.
        intent = _read_canonical_intent(args.intent)
        _assert_all_pins_absent()
        if intent["rehearsal_module_sha256"] != _module_sha256():
            _fail("running rehearsal module differs from the reviewed intent")
        if intent["collector_module_sha256"] != acquisition._module_sha256():
            _fail("accepted collector module differs from the reviewed intent")
        _assert_private_output_parent(args.evidence_directory, args.receipt)
        evidence_path = args.evidence_directory / "rehearsal-evidence.json"
        intent_copy_path = args.evidence_directory / "intent.json"
        if _path_exists_no_follow(
            args.evidence_directory
        ) or _path_exists_no_follow(args.receipt):
            _fail("local evidence directory and receipt must both be absent")
        _reserve_evidence_directory(args.evidence_directory)
        _write_private_create_once(intent_copy_path, intent, label="intent evidence")
        evidence_descriptor = _reserve_private_create_once(
            evidence_path, label="rehearsal evidence"
        )
        try:
            receipt_descriptor = _reserve_private_create_once(
                args.receipt, label="rehearsal receipt"
            )
        except Exception:
            os.close(evidence_descriptor)
            raise
        try:
            # Locator validation precedes even the secret storage-state read.
            locator_raw = _read_private_regular(
                args.acceptance_locator_file, label="acceptance locator file"
            )
            locator = _acceptance_locator(locator_raw)
            storage_state = _read_private_regular(
                args.storage_state_file, label="Playwright storage-state file"
            )
            # Parse secret material in memory before a Session can be constructed.
            _playwright_cookies(storage_state)
            retained_session_factory = session_factory
            if retained_session_factory is None:
                try:
                    import requests
                except ImportError as exc:  # pragma: no cover - base dependency
                    raise Week1A5P0BProviderRealityError(
                        "requests is unavailable"
                    ) from exc
                retained_session_factory = requests.Session
            bundle = _rehearse_acceptance_download_v1(
                intent=intent,
                storage_state=storage_state,
                acceptance_locator=locator,
                session_factory=retained_session_factory,
            )
            _write_reserved(
                evidence_descriptor,
                bundle["evidence"],
                label="rehearsal evidence",
            )
            _write_reserved(
                receipt_descriptor,
                bundle["receipt"],
                label="rehearsal receipt",
            )
        finally:
            os.close(evidence_descriptor)
            os.close(receipt_descriptor)
        sys.stdout.buffer.write(_canonical_bytes(bundle["receipt"]))
        return 0
    except (
        Week1A5P0BProviderRealityError,
        acquisition.Week1A5DraftKingsAcquisitionError,
        capture.Week1A5CaptureContractError,
    ) as exc:
        print(f"local Week-1 provider rehearsal HOLD: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "CONFIRMATION_PHRASE",
    "EVIDENCE_SCHEMA",
    "FIXED_DRAFTKINGS_HTTPS_FAMILIES",
    "INTENT_SCHEMA",
    "PLAN_SCHEMA",
    "RECEIPT_SCHEMA",
    "Week1A5P0BProviderRealityError",
    "build_intent_v1",
    "main",
    "plan_v1",
    "validate_intent_v1",
]
