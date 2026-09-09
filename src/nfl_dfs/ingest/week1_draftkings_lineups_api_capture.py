"""Seal the authenticated Week-1 DraftKings lineups API capture without PII.

The browser/CDP collector writes the provider body to an owner-only local file
only after observing one exact HTTP-200 response from the reviewed lineups API
family.  This module is deliberately offline: it validates those bytes and
emits a redacted receipt.  It never reads cookies, contacts DraftKings, or
retains user, entry, lineup, player, or query values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from urllib.parse import parse_qsl, urlsplit

from nfl_dfs.ingest import week1_a5_capture_contracts as capture

SCHEMA: Final = "week1-draftkings-lineups-api-capture/v1"
CAPTURE_PROFILE: Final = "authenticated-edge-cdp-lineups-api-http200/v1"
COLLECTOR_SHA256: Final = (
    "05f3d044c8bf0db165f0ed44964665e16e7562a1c9abcc72adb4ebbd070be315"
)
QUERY_NAMES: Final = (
    "embed",
    "format",
    "includeBestBall",
    "includeNFT",
    "includeSnakeDraft",
)
TOP_FIELDS: Final = frozenset(
    {"bestBallStartingGameTypes", "errorStatus", "gameTypes", "lineups", "responseStatus"}
)
LINEUP_FIELDS: Final = frozenset(
    {
        "CreateDate",
        "contestEntries",
        "contestStartDate",
        "contestTypeId",
        "draftGroupId",
        "draftedPlayers",
        "entries",
        "gameTypeId",
        "lineupComparisonValue",
        "lineupKey",
        "salaryCap",
        "salaryRemaining",
        "sport",
        "status",
    }
)
ENTRY_FIELDS: Final = frozenset(
    {"contestEntryKey", "contestKey", "entryName", "lineupKey"}
)
PLAYER_FIELDS: Final = frozenset(
    {
        "DefaultPMR",
        "ExternalRequirements",
        "FPPG",
        "competitionIds",
        "displayName",
        "draftableId",
        "firstName",
        "gameKey",
        "injury",
        "lastName",
        "playerDkId",
        "playerId",
        "positionId",
        "positionName",
        "rosterPositionName",
        "rosterSlotId",
        "salary",
        "shortName",
        "teamId",
    }
)
GAME_TYPE_FIELDS: Final = frozenset(
    {"description", "draftType", "gameStyle", "gameTypeId", "name", "sportId", "tag"}
)
GAME_STYLE_FIELDS: Final = frozenset(
    {"abbreviation", "description", "gameStyleId", "isEnabled", "name", "sortOrder", "sportId"}
)
_DIGITS = re.compile(r"[1-9][0-9]*\Z")
_GUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)


class DraftKingsLineupsCaptureError(ValueError):
    """The private provider response or its redacted receipt is inadmissible."""


def _fail(message: str) -> None:
    raise DraftKingsLineupsCaptureError(message)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _constant(value: str) -> object:
    _fail(f"non-finite JSON token {value!r}")


def parse_strict(raw: bytes) -> dict[str, object]:
    if not raw or len(raw) > 2_000_000:
        _fail("lineups response size is outside the closed bound")
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DraftKingsLineupsCaptureError("lineups response is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        _fail("lineups response root is not an object")
    return value


def _exact(value: object, fields: frozenset[str], *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} is not a string-keyed object")
    retained = dict(value)
    if set(retained) != set(fields):
        _fail(f"{label} fields differ")
    return retained


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} is not an array")
    return list(value)


def _string(value: object, *, label: str, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value):
        _fail(f"{label} is not a canonical string")
    return value


def _positive(value: object, *, label: str, zero: bool = False) -> int:
    if type(value) is not int or value < (0 if zero else 1):
        _fail(f"{label} is not a {'nonnegative' if zero else 'positive'} integer")
    return value


def _numeric_key(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if _DIGITS.fullmatch(retained) is None:
        _fail(f"{label} is not a positive numeric key")
    return retained


def _captured_at(value: object) -> str:
    retained = _string(value, label="captured_at_utc")
    try:
        parsed = datetime.fromisoformat(retained.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DraftKingsLineupsCaptureError("captured_at_utc is not ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("captured_at_utc lacks an offset")
    parsed = parsed.astimezone(UTC)
    lock = datetime.fromisoformat(capture.EXPECTED_LOCK_UTC.replace("Z", "+00:00"))
    if parsed >= lock:
        _fail("lineups capture is not pre-lock")
    return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")


def admit_locator(locator: object) -> dict[str, object]:
    value = _string(locator, label="lineups locator")
    parsed = urlsplit(value)
    segments = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.draftkings.com"
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or len(segments) != 5
        or segments[:3] != ["lineups", "v1", "users"]
        or segments[4] != "lineups"
        or _GUID.fullmatch(segments[3]) is None
    ):
        _fail("lineups locator is outside the reviewed exact family")
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    names = tuple(sorted({name for name, _ in pairs}))
    if names != QUERY_NAMES or len(pairs) != len(QUERY_NAMES):
        _fail("lineups locator query names differ")
    return {
        "scheme": "https",
        "host": "api.draftkings.com",
        "path_template": "/lineups/v1/users/<redacted>/lineups",
        "query_parameter_names": list(QUERY_NAMES),
        "locator_sha256": hashlib.sha256(value.encode()).hexdigest(),
        "user_or_query_values_retained": False,
    }


def _lineups_locator(resource_raw: bytes) -> tuple[str, dict[str, object]]:
    rows = parse_strict_resource_list(resource_raw)
    matches: list[tuple[str, dict[str, object]]] = []
    for row in rows:
        name = row.get("name")
        if type(name) is not str:
            continue
        try:
            projection = admit_locator(name)
        except DraftKingsLineupsCaptureError:
            continue
        matches.append((name, projection))
    if len(matches) != 1:
        _fail("private resource census does not contain exactly one lineups locator")
    return matches[0]


def parse_strict_resource_list(raw: bytes) -> list[dict[str, object]]:
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DraftKingsLineupsCaptureError("resource census is not strict UTF-8 JSON") from exc
    rows = _sequence(value, label="resource census")
    if not rows or len(rows) > 2_000:
        _fail("resource census count is outside the closed bound")
    return [dict(_exact(row, frozenset({"name", "initiatorType", "transferSize", "encodedBodySize"}), label="resource row")) for row in rows]


def inspect_lineups(raw: bytes) -> dict[str, object]:
    root = _exact(parse_strict(raw), TOP_FIELDS, label="response")
    if root["responseStatus"] != {} or root["errorStatus"] != {}:
        _fail("provider response carries a nonempty status or error object")
    if _sequence(root["bestBallStartingGameTypes"], label="best-ball types"):
        _fail("provider response unexpectedly carries best-ball types")

    game_types = _sequence(root["gameTypes"], label="game types")
    if len(game_types) != 1:
        _fail("provider response must carry one game type")
    game_type = _exact(game_types[0], GAME_TYPE_FIELDS, label="game type")
    style = _exact(game_type["gameStyle"], GAME_STYLE_FIELDS, label="game style")
    if (
        game_type["gameTypeId"] != 1
        or game_type["sportId"] != 1
        or game_type["name"] != "Classic"
        or game_type["draftType"] != "SalaryCap"
        or style["gameStyleId"] != 1
        or style["sportId"] != 1
        or style["name"] != "Classic"
        or style["abbreviation"] != "CLA"
        or style["isEnabled"] is not True
    ):
        _fail("game type is not enabled NFL Classic salary-cap")

    lineups = _sequence(root["lineups"], label="lineups")
    if len(lineups) != 1:
        _fail("provider response must carry exactly one Week-1 lineup")
    lineup = _exact(lineups[0], LINEUP_FIELDS, label="lineup")
    lineup_key = _numeric_key(lineup["lineupKey"], label="lineup key")
    if (
        lineup["draftGroupId"] != int(capture.EXPECTED_DRAFT_GROUP_ID)
        or lineup["contestStartDate"]
        not in (capture.EXPECTED_LOCK_UTC, "2026-09-13T17:00:00.0000000Z")
        or lineup["gameTypeId"] != 1
        or lineup["contestTypeId"] != 21
        or lineup["sport"] != "NFL"
        or lineup["status"] != "Upcoming"
        or lineup["salaryCap"] != capture.SALARY_CAP
    ):
        _fail("lineup identity, state, lock, or game law differs")
    salary_remaining = _positive(
        lineup["salaryRemaining"], label="salary remaining", zero=True
    )

    entries = _sequence(lineup["entries"], label="entries")
    if lineup["contestEntries"] != capture.EXPECTED_PLANNED_ENTRIES or len(entries) != capture.EXPECTED_PLANNED_ENTRIES:
        _fail("provider entry count differs from the 90-entry Week-1 plan")
    entry_keys: set[str] = set()
    contest_counts: Counter[str] = Counter()
    for ordinal, raw_entry in enumerate(entries):
        entry = _exact(raw_entry, ENTRY_FIELDS, label=f"entry {ordinal}")
        entry_key = _numeric_key(entry["contestEntryKey"], label=f"entry {ordinal} key")
        contest_key = _numeric_key(entry["contestKey"], label=f"entry {ordinal} contest")
        if entry_key in entry_keys:
            _fail("provider response repeats an entry key")
        entry_keys.add(entry_key)
        contest_counts[contest_key] += 1
        if _numeric_key(entry["lineupKey"], label=f"entry {ordinal} lineup") != lineup_key:
            _fail("provider entry names another lineup")
        _string(entry["entryName"], label=f"entry {ordinal} name", allow_empty=True)

    expected_counts = {
        pin.contest_id: pin.planned_entries for pin in capture.A5_ROLE_TABLE.values()
    }
    if dict(contest_counts) != expected_counts:
        _fail("provider contest-entry allocation differs from the exact A5 plan")

    players = _sequence(lineup["draftedPlayers"], label="drafted players")
    if len(players) != len(capture.CLASSIC_SLOTS):
        _fail("provider lineup does not carry nine drafted players")
    draftable_ids: set[int] = set()
    salary_spent = 0
    slots: list[str] = []
    for ordinal, raw_player in enumerate(players):
        player = _exact(raw_player, PLAYER_FIELDS, label=f"drafted player {ordinal}")
        draftable = _positive(player["draftableId"], label="draftable id")
        if draftable in draftable_ids:
            _fail("provider lineup repeats a draftable")
        draftable_ids.add(draftable)
        for key in ("playerDkId", "playerId", "positionId", "rosterSlotId", "teamId"):
            _positive(player[key], label=f"drafted player {ordinal} {key}")
        for key in (
            "displayName",
            "firstName",
            "gameKey",
            "positionName",
            "rosterPositionName",
            "shortName",
        ):
            _string(player[key], label=f"drafted player {ordinal} {key}")
        last_name = _string(
            player["lastName"],
            label=f"drafted player {ordinal} lastName",
            allow_empty=True,
        )
        if not last_name and player["positionName"] != "DST":
            _fail("only a DST may carry an empty provider last name")
        _string(player["injury"], label=f"drafted player {ordinal} injury", allow_empty=True)
        if player["ExternalRequirements"] != {}:
            _fail("drafted player carries external requirements")
        competitions = _sequence(player["competitionIds"], label="competition ids")
        if len(competitions) != 1 or type(competitions[0]) is not str or not competitions[0]:
            _fail("drafted player competition identity differs")
        fppg = player["FPPG"]
        if type(fppg) not in (int, float) or not math.isfinite(fppg) or fppg < 0:
            _fail("drafted player FPPG is not finite and nonnegative")
        _positive(player["DefaultPMR"], label="drafted player PMR", zero=True)
        salary_spent += _positive(player["salary"], label="drafted player salary")
        slots.append(str(player["rosterPositionName"]))
    if tuple(slots) != capture.CLASSIC_SLOTS:
        _fail("provider lineup slot order differs from NFL Classic")
    if salary_spent + salary_remaining != capture.SALARY_CAP:
        _fail("provider lineup salary does not reconcile")

    role_counts = {
        role: contest_counts[pin.contest_id]
        for role, pin in capture.A5_ROLE_TABLE.items()
    }
    return {
        "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
        "lock_utc": capture.EXPECTED_LOCK_UTC,
        "lineup_count": 1,
        "entry_count": len(entries),
        "unique_entry_count": len(entry_keys),
        "contest_count": len(contest_counts),
        "role_entry_counts": role_counts,
        "drafted_player_count": len(players),
        "classic_slots": list(capture.CLASSIC_SLOTS),
        "unique_draftable_count": len(draftable_ids),
        "salary_cap": capture.SALARY_CAP,
        "salary_spent": salary_spent,
        "salary_remaining": salary_remaining,
        "lineup_status": "Upcoming",
        "entry_lineup_player_values_retained": False,
    }


def build_receipt(
    raw: bytes,
    *,
    captured_at_utc: object,
    locator: object,
    collector_sha256: object = COLLECTOR_SHA256,
) -> dict[str, object]:
    if collector_sha256 != COLLECTOR_SHA256:
        _fail("capture collector differs from the reviewed one-shot source")
    captured = _captured_at(captured_at_utc)
    receipt: dict[str, object] = {
        "schema_version": SCHEMA,
        "capture_profile": CAPTURE_PROFILE,
        "season": 2026,
        "week": 1,
        "captured_at_utc": captured,
        "captured_at_basis": "owner-host private response-file close time",
        "prelock": True,
        "collector_sha256": COLLECTOR_SHA256,
        "request": admit_locator(locator),
        "response": {
            "http_status": 200,
            "status_basis": "collector writes only after exact response status 200",
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "facts": inspect_lineups(raw),
        "private_raw_body_published": False,
        "credentials_or_cookie_values_retained": False,
        "entry_lineup_player_values_retained": False,
        "standings_or_outcome_opened": False,
        "receipt_sha256": "",
    }
    receipt["receipt_sha256"] = hashlib.sha256(canonical({k: v for k, v in receipt.items() if k != "receipt_sha256"})).hexdigest()
    return receipt


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def _read_private(path: Path, *, label: str, maximum: int) -> bytes:
    if path.is_symlink():
        _fail(f"{label} is a symlink")
    metadata = path.stat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_uid != os.geteuid()
        or metadata.st_nlink != 1
        or not 0 < metadata.st_size <= maximum
    ):
        _fail(f"{label} is not one bounded owner-only mode-0600 file")
    return path.read_bytes()


def _write_create_once(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-private", required=True, type=Path)
    parser.add_argument("--resource-census-private", required=True, type=Path)
    parser.add_argument("--collector", required=True, type=Path)
    parser.add_argument("--captured-at-utc", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args(argv)
    raw = _read_private(args.raw_private, label="lineups response", maximum=2_000_000)
    resource_raw = _read_private(
        args.resource_census_private, label="resource census", maximum=2_000_000
    )
    collector = args.collector.read_bytes()
    if hashlib.sha256(collector).hexdigest() != COLLECTOR_SHA256:
        _fail("capture collector bytes differ")
    locator, _ = _lineups_locator(resource_raw)
    receipt = build_receipt(
        raw,
        captured_at_utc=args.captured_at_utc,
        locator=locator,
        collector_sha256=hashlib.sha256(collector).hexdigest(),
    )
    _write_create_once(args.receipt, canonical(receipt))
    print(
        f"DraftKings Week-1 lineups API capture PASS: "
        f"{receipt['facts']['entry_count']} entries; receipt={receipt['receipt_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
