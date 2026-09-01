"""Fail-closed boundary for paid DraftKings NFL Classic books.

The historical exporters in :mod:`nfl_dfs.optimizer.export` deliberately
remain unchanged because frozen receipts and preview tools still reproduce
their bytes.  Money-ready callers use this versioned successor instead.  It
requires an exact, unique book and reopens every roster against the current
slate salary catalog before producing upload bytes.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from .export import ENTRY_META_HEADER, fill_entries_csv
from .lineup import MAX_FROM_TEAM, ROSTER_SIZE, SALARY_CAP, Lineup

PAID_CLASSIC_BOUNDARY_ID = "paid-classic-book-boundary-v2"
INACTIVE_STATUSES = frozenset({"O", "OUT", "IR"})
# ``ingest-dk`` is an hourly live snapshot.  Two hours permits one missed
# hourly pull while refusing a catalog old enough to miss multiple status or
# draftable-ID updates at a paid decision boundary.
PAID_CLASSIC_CATALOG_MAX_AGE = timedelta(hours=2)
_CLASSIC_HEADER = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
_ALLOWED_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "DST"})
_CELL_ID = re.compile(r"^.+ \(([0-9]+)\)$")


@dataclass(frozen=True)
class PaidClassicCatalog:
    """Immutable normalized view of one current DraftKings salary slate."""

    draft_group_id: int
    by_player_id: Mapping[int, Mapping[str, Any]]
    by_draftable_id: Mapping[int, Mapping[str, Any]]
    sha256: str
    rows: int
    pulled_at: str
    validated_at: str
    age_seconds: float
    max_age_seconds: int


@dataclass(frozen=True)
class PaidClassicExport:
    """Validated CSV bytes plus deterministic boundary evidence."""

    csv_text: str
    receipt: Mapping[str, Any]


def _fail(message: str) -> None:
    raise ValueError(f"{PAID_CLASSIC_BOUNDARY_ID}: {message}")


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _integer(value: Any, *, label: str, positive: bool = True) -> int:
    if isinstance(value, bool):
        _fail(f"{label} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        _fail(f"{label} must be an integer")
    try:
        if float(value) != float(parsed):
            _fail(f"{label} must be an integer")
    except (TypeError, ValueError, OverflowError):
        _fail(f"{label} must be an integer")
    if positive and parsed <= 0:
        _fail(f"{label} must be positive")
    return parsed


def _text(value: Any, *, label: str) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        _fail(f"{label} is missing")
    parsed = str(value).strip()
    if not parsed:
        _fail(f"{label} is missing")
    return parsed


def _status(value: Any) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    parsed = str(value).strip().upper()
    return "" if parsed in {"NONE", "NAN", "NULL"} else parsed


def _utc_timestamp(value: Any, *, label: str) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError):
        _fail(f"{label} must be a timezone-aware timestamp")
    if pd.isna(parsed) or parsed.tzinfo is None:
        _fail(f"{label} must be a timezone-aware timestamp")
    return parsed.tz_convert("UTC")


def build_paid_classic_catalog_v2(
    salary_rows: pd.DataFrame,
    *,
    draft_group_id: int,
    validated_at: datetime | pd.Timestamp | None = None,
) -> PaidClassicCatalog:
    """Normalize one slate-local salary snapshot and fail on ambiguity.

    The input must be the latest salary pull for exactly one draft group.
    Stable player IDs and slate-specific draftable IDs are independently
    unique.  No deduplication is performed at this money boundary.
    """

    gid = _integer(draft_group_id, label="draft_group_id")
    if not isinstance(salary_rows, pd.DataFrame) or salary_rows.empty:
        _fail(f"draft group {gid} has no salary catalog")
    required = {
        "draft_group_id",
        "pulled_at",
        "dk_player_id",
        "dk_draftable_id",
        "display_name",
        "team_abbr",
        "position",
        "salary",
        "status",
    }
    missing = required - set(salary_rows.columns)
    if missing:
        _fail("salary catalog is missing " + ", ".join(sorted(missing)))

    validation_stamp = _utc_timestamp(
        validated_at if validated_at is not None else datetime.now(timezone.utc),
        label="paid catalog validation time",
    )
    pull_stamps = [
        _utc_timestamp(value, label=f"salary row {ordinal} pulled_at")
        for ordinal, value in enumerate(salary_rows["pulled_at"], start=1)
    ]
    pull_values = {stamp.value for stamp in pull_stamps}
    if len(pull_values) != 1:
        _fail("salary catalog mixes multiple pulled_at snapshots")
    pull_stamp = pull_stamps[0]
    age = validation_stamp - pull_stamp
    if age < pd.Timedelta(0):
        _fail("salary catalog pulled_at is in the future")
    max_age = pd.Timedelta(PAID_CLASSIC_CATALOG_MAX_AGE)
    if age > max_age:
        _fail(
            "salary catalog is stale: "
            f"age {age.total_seconds():.0f}s exceeds "
            f"{max_age.total_seconds():.0f}s"
        )

    normalized: list[dict[str, Any]] = []
    for ordinal, row in enumerate(salary_rows.to_dict("records"), start=1):
        row_gid = _integer(
            row.get("draft_group_id"), label=f"salary row {ordinal} draft_group_id"
        )
        if row_gid != gid:
            _fail(f"salary row {ordinal} belongs to draft group {row_gid}, not {gid}")
        position = _text(
            row.get("position"), label=f"salary row {ordinal} position"
        ).upper()
        if position not in _ALLOWED_POSITIONS:
            _fail(f"salary row {ordinal} has unsupported position {position!r}")
        normalized.append(
            {
                "player_id": _integer(
                    row.get("dk_player_id"),
                    label=f"salary row {ordinal} dk_player_id",
                ),
                "draftable_id": _integer(
                    row.get("dk_draftable_id"),
                    label=f"salary row {ordinal} dk_draftable_id",
                ),
                "name": _text(
                    row.get("display_name"),
                    label=f"salary row {ordinal} display_name",
                ),
                "team": _text(
                    row.get("team_abbr"), label=f"salary row {ordinal} team_abbr"
                ).upper(),
                "pos": position,
                "salary": _integer(
                    row.get("salary"), label=f"salary row {ordinal} salary"
                ),
                "status": _status(row.get("status")),
            }
        )

    player_ids = [row["player_id"] for row in normalized]
    draftable_ids = [row["draftable_id"] for row in normalized]
    if len(set(player_ids)) != len(player_ids):
        _fail("salary catalog has duplicate stable player IDs")
    if len(set(draftable_ids)) != len(draftable_ids):
        _fail("salary catalog has duplicate draftable IDs")
    normalized.sort(key=lambda row: row["player_id"])
    by_player = {int(row["player_id"]): row for row in normalized}
    by_draftable = {int(row["draftable_id"]): row for row in normalized}
    pulled_at_iso = pull_stamp.isoformat()
    validated_at_iso = validation_stamp.isoformat()
    catalog_identity = {
        "draft_group_id": gid,
        "pulled_at": pulled_at_iso,
        "players": normalized,
    }
    return PaidClassicCatalog(
        draft_group_id=gid,
        by_player_id=by_player,
        by_draftable_id=by_draftable,
        sha256=_canonical_sha256(catalog_identity),
        rows=len(normalized),
        pulled_at=pulled_at_iso,
        validated_at=validated_at_iso,
        age_seconds=float(age.total_seconds()),
        max_age_seconds=int(max_age.total_seconds()),
    )


def assert_paid_candidate_supply_v2(
    *, available_candidates: int, requested_entries: int
) -> None:
    """Preselection half of the paid exact-K contract."""

    available = _integer(
        available_candidates, label="available candidate count", positive=False
    )
    if available < 0:
        _fail("available candidate count must be non-negative")
    requested = _integer(requested_entries, label="requested entry count")
    if available < requested:
        _fail(
            f"candidate supply is short: requested {requested}, available {available}"
        )


def assert_exact_unique_classic_book_v2(
    lineups: Sequence[Lineup], *, expected_entries: int
) -> None:
    """Terminal selection check that is safe before catalog availability."""

    expected = _integer(expected_entries, label="requested entry count")
    if len(lineups) != expected:
        _fail(f"book is short: requested {expected}, selected {len(lineups)}")
    identities: list[tuple[int, ...]] = []
    for lineup_ordinal, lineup in enumerate(lineups, start=1):
        if not isinstance(lineup, Lineup):
            _fail(f"lineup {lineup_ordinal} is not a Lineup")
        raw_ids = [
            _integer(
                player.get("id"),
                label=f"lineup {lineup_ordinal} player ID",
            )
            for player in lineup.players
        ]
        if len(raw_ids) != ROSTER_SIZE or len(set(raw_ids)) != ROSTER_SIZE:
            _fail(f"lineup {lineup_ordinal} is not nine distinct players")
        identities.append(tuple(sorted(raw_ids)))
    if len(set(identities)) != expected:
        _fail("book contains duplicate canonical rosters")


def _validate_roster(
    lineup: Lineup,
    *,
    catalog: PaidClassicCatalog,
    lineup_ordinal: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    raw_ids: list[int] = []
    draftable_ids: list[int] = []
    authoritative: list[Mapping[str, Any]] = []
    for player_ordinal, player in enumerate(lineup.players, start=1):
        if not isinstance(player, Mapping):
            _fail(f"lineup {lineup_ordinal} player {player_ordinal} is not a mapping")
        player_id = _integer(
            player.get("id"),
            label=f"lineup {lineup_ordinal} player {player_ordinal} ID",
        )
        source = catalog.by_player_id.get(player_id)
        if source is None:
            _fail(f"lineup {lineup_ordinal} player {player_id} is outside the slate")
        draftable_id = _integer(
            player.get("dk_id"),
            label=f"lineup {lineup_ordinal} player {player_id} draftable ID",
        )
        if draftable_id != source["draftable_id"]:
            _fail(f"lineup {lineup_ordinal} player {player_id} has a stale draftable ID")
        observed_position = _text(
            player.get("pos"), label=f"lineup {lineup_ordinal} player {player_id} position"
        ).upper()
        observed_team = _text(
            player.get("team"), label=f"lineup {lineup_ordinal} player {player_id} team"
        ).upper()
        observed_salary = _integer(
            player.get("salary"),
            label=f"lineup {lineup_ordinal} player {player_id} salary",
        )
        if (
            observed_position != source["pos"]
            or observed_team != source["team"]
            or observed_salary != source["salary"]
        ):
            _fail(
                f"lineup {lineup_ordinal} player {player_id} differs from the "
                "current salary catalog"
            )
        if source["status"] in INACTIVE_STATUSES:
            _fail(
                f"lineup {lineup_ordinal} contains inactive player {player_id} "
                f"({source['status']})"
            )
        _text(
            player.get("name"), label=f"lineup {lineup_ordinal} player {player_id} name"
        )
        raw_ids.append(player_id)
        draftable_ids.append(draftable_id)
        authoritative.append(source)

    if len(raw_ids) != ROSTER_SIZE or len(set(raw_ids)) != ROSTER_SIZE:
        _fail(f"lineup {lineup_ordinal} is not nine distinct players")
    if len(set(draftable_ids)) != ROSTER_SIZE:
        _fail(f"lineup {lineup_ordinal} has duplicate draftable IDs")

    positions = Counter(str(row["pos"]) for row in authoritative)
    if not (
        positions["QB"] == 1
        and positions["DST"] == 1
        and 2 <= positions["RB"] <= 3
        and 3 <= positions["WR"] <= 4
        and 1 <= positions["TE"] <= 2
        and sum(positions.values()) == ROSTER_SIZE
    ):
        _fail(f"lineup {lineup_ordinal} violates DraftKings Classic positions")
    salary = sum(int(row["salary"]) for row in authoritative)
    if salary > SALARY_CAP:
        _fail(f"lineup {lineup_ordinal} exceeds the DraftKings salary cap")
    teams = Counter(str(row["team"]) for row in authoritative)
    if len(teams) < 2 or max(teams.values()) > MAX_FROM_TEAM:
        _fail(f"lineup {lineup_ordinal} violates the DraftKings team limit")

    ordered = lineup.slot_order()
    ordered_ids = [
        _integer(
            player.get("id"), label=f"lineup {lineup_ordinal} slot-order player ID"
        )
        for player in ordered
    ]
    if len(ordered_ids) != ROSTER_SIZE or set(ordered_ids) != set(raw_ids):
        _fail(f"lineup {lineup_ordinal} cannot be represented in Classic slots")
    return tuple(sorted(raw_ids)), tuple(sorted(draftable_ids))


def validate_paid_classic_book_v2(
    lineups: Sequence[Lineup],
    *,
    expected_entries: int,
    catalog: PaidClassicCatalog,
) -> dict[str, Any]:
    """Validate exact K, unique rosters, legality, IDs, and active status."""

    assert_exact_unique_classic_book_v2(lineups, expected_entries=expected_entries)
    identities: list[tuple[int, ...]] = []
    draftable_identities: list[tuple[int, ...]] = []
    for ordinal, lineup in enumerate(lineups, start=1):
        stable, draftable = _validate_roster(
            lineup, catalog=catalog, lineup_ordinal=ordinal
        )
        identities.append(stable)
        draftable_identities.append(draftable)
    if len(set(draftable_identities)) != len(lineups):
        _fail("book contains duplicate draftable-ID rosters")
    body: dict[str, Any] = {
        "boundary_id": PAID_CLASSIC_BOUNDARY_ID,
        "draft_group_id": catalog.draft_group_id,
        "expected_entries": len(lineups),
        "actual_entries": len(lineups),
        "unique_rosters": len(set(identities)),
        "roster_order_sha256": _canonical_sha256(identities),
        "draftable_roster_order_sha256": _canonical_sha256(draftable_identities),
        "salary_catalog_sha256": catalog.sha256,
        "salary_catalog_rows": catalog.rows,
        "salary_catalog_pulled_at": catalog.pulled_at,
        "salary_catalog_validated_at": catalog.validated_at,
        "salary_catalog_age_seconds": catalog.age_seconds,
        "salary_catalog_max_age_seconds": catalog.max_age_seconds,
        "salary_catalog_fresh": True,
        "inactive_statuses": sorted(INACTIVE_STATUSES),
        "exact_k": True,
        "unique": True,
        "draftkings_legal": True,
        "active_eligible": True,
    }
    body["receipt_sha256"] = _canonical_sha256(body)
    return body


def _cell(player: Mapping[str, Any]) -> str:
    return f"{str(player['name']).strip()} ({int(player['dk_id'])})"


def to_paid_dk_csv_v2(
    lineups: Sequence[Lineup],
    *,
    expected_entries: int,
    catalog: PaidClassicCatalog,
) -> PaidClassicExport:
    """Validate and serialize an exact paid Classic upload book."""

    receipt = validate_paid_classic_book_v2(
        lineups, expected_entries=expected_entries, catalog=catalog
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CLASSIC_HEADER)
    expected_rows: list[list[int]] = []
    for lineup in lineups:
        ordered = lineup.slot_order()
        writer.writerow([_cell(player) for player in ordered])
        expected_rows.append([int(player["dk_id"]) for player in ordered])
    csv_text = buf.getvalue()

    reopened = list(csv.reader(io.StringIO(csv_text)))
    if tuple(reopened[0]) != _CLASSIC_HEADER or len(reopened) != len(lineups) + 1:
        _fail("serialized upload has the wrong header or row count")
    for ordinal, (row, expected_ids) in enumerate(
        zip(reopened[1:], expected_rows, strict=True), start=1
    ):
        ids = []
        for cell in row:
            matched = _CELL_ID.fullmatch(cell)
            if matched is None:
                _fail(f"serialized upload row {ordinal} has a malformed cell")
            ids.append(int(matched.group(1)))
        if ids != expected_ids or len(set(ids)) != ROSTER_SIZE:
            _fail(f"serialized upload row {ordinal} changed the validated roster")
    export_receipt = dict(receipt)
    payload = csv_text.encode("utf-8")
    export_receipt.update(
        {
            "export_kind": "draftkings-classic-lineup-upload",
            "csv_sha256": hashlib.sha256(payload).hexdigest(),
            "csv_bytes": len(payload),
        }
    )
    export_receipt["export_receipt_sha256"] = _canonical_sha256(export_receipt)
    return PaidClassicExport(csv_text=csv_text, receipt=export_receipt)


def _paid_contest_id(contest_id: str | None) -> str:
    if contest_id is None or not str(contest_id).strip():
        _fail("paid DKEntries fill requires an explicit contest_id")
    return str(contest_id).strip()


def _entries_rows(
    entries_csv: str, *, contest_id: str | None
) -> tuple[list[list[str]], int, int, list[list[str]]]:
    cid = _paid_contest_id(contest_id)
    rows = list(csv.reader(io.StringIO(entries_csv)))
    header_index = -1
    for index, row in enumerate(rows):
        cells = [cell.strip().lstrip("\ufeff") for cell in row]
        if cells[: len(ENTRY_META_HEADER)] == ENTRY_META_HEADER:
            header_index = index
            break
    if header_index < 0:
        _fail("input is not a DKEntries.csv")
    header = [cell.strip() for cell in rows[header_index]]
    first_slot = len(ENTRY_META_HEADER)
    if tuple(header[first_slot : first_slot + ROSTER_SIZE]) != _CLASSIC_HEADER:
        _fail("DKEntries.csv does not contain the Classic slot header")

    candidates: list[list[str]] = []
    for row in rows[header_index + 1 :]:
        metadata = (row[: len(ENTRY_META_HEADER)] + [""] * len(ENTRY_META_HEADER))[
            : len(ENTRY_META_HEADER)
        ]
        if not any(str(cell).strip() for cell in metadata):
            continue
        if not str(metadata[2]).strip():
            _fail("DKEntries target selection is ambiguous: an entry row has no contest ID")
        candidates.append(row)
    selected = [row for row in candidates if row[2].strip() == cid]
    if not selected:
        _fail(f"DKEntries.csv contains no entry rows for contest_id {cid}")

    entry_ids = [row[0].strip() if row else "" for row in selected]
    if any(not entry_id for entry_id in entry_ids):
        _fail("targeted DKEntries rows require nonblank Entry IDs")
    if len(set(entry_ids)) != len(entry_ids):
        _fail("targeted DKEntries rows contain duplicate Entry IDs")
    targeted_ids = set(entry_ids)
    if any(
        row[2].strip() != cid and row[0].strip() in targeted_ids
        for row in candidates
    ):
        _fail("DKEntries target selection is ambiguous across contests")
    return rows, header_index, first_slot, selected


def paid_entry_count_v2(entries_csv: str, *, contest_id: str | None) -> int:
    """Validate an unambiguous paid target and return its exact row count."""

    return len(_entries_rows(entries_csv, contest_id=contest_id)[3])


def fill_paid_entries_csv_v2(
    entries_csv: str,
    lineups: Sequence[Lineup],
    *,
    catalog: PaidClassicCatalog,
    contest_id: str | None,
) -> PaidClassicExport:
    """Fill paid entries without cycling, locked-row fallback, or drift."""

    cid = _paid_contest_id(contest_id)
    _, _, first_slot, before_rows = _entries_rows(
        entries_csv, contest_id=contest_id
    )
    expected_entries = len(before_rows)
    before_entry_ids = [row[0].strip() for row in before_rows]
    if any(
        "LOCKED" in cell.upper()
        for row in before_rows
        for cell in row[first_slot : first_slot + ROSTER_SIZE]
    ):
        _fail("ordinary paid fill refuses locked rows; use validated late swap")
    receipt = validate_paid_classic_book_v2(
        lineups, expected_entries=expected_entries, catalog=catalog
    )
    # The legacy filler provides the reviewed min-churn one-to-one assignment.
    # Exact K above makes its historical modulo fallback unreachable as a
    # shortfall mechanism; the reopened output audit below proves that every
    # validated roster appears exactly once.
    filled = fill_entries_csv(
        entries_csv, list(lineups), contest_id=cid
    )
    _, _, output_first_slot, output_rows = _entries_rows(
        filled, contest_id=contest_id
    )
    if len(output_rows) != expected_entries:
        _fail("filled DKEntries.csv changed the targeted entry count")
    output_entry_ids = [row[0].strip() for row in output_rows]
    if output_entry_ids != before_entry_ids:
        _fail("filled DKEntries.csv changed the targeted Entry ID order")

    output_rosters: list[tuple[int, ...]] = []
    for ordinal, row in enumerate(output_rows, start=1):
        cells = (
            row[output_first_slot : output_first_slot + ROSTER_SIZE]
            + [""] * ROSTER_SIZE
        )[:ROSTER_SIZE]
        draftable_ids: list[int] = []
        for cell in cells:
            matched = _CELL_ID.fullmatch(cell)
            if matched is None:
                _fail(f"filled entry row {ordinal} has a malformed or empty slot")
            draftable_id = int(matched.group(1))
            if draftable_id not in catalog.by_draftable_id:
                _fail(f"filled entry row {ordinal} has an out-of-slate draftable ID")
            draftable_ids.append(draftable_id)
        if len(set(draftable_ids)) != ROSTER_SIZE:
            _fail(f"filled entry row {ordinal} contains duplicate players")
        output_rosters.append(tuple(sorted(draftable_ids)))

    expected_rosters = {
        tuple(sorted(int(player["dk_id"]) for player in lineup.players))
        for lineup in lineups
    }
    if len(set(output_rosters)) != expected_entries:
        _fail("filled DKEntries.csv contains duplicate rosters")
    if set(output_rosters) != expected_rosters:
        _fail("filled DKEntries.csv does not contain the exact validated book")

    export_receipt = dict(receipt)
    payload = filled.encode("utf-8")
    export_receipt.update(
        {
            "export_kind": "draftkings-classic-edit-entries",
            "csv_sha256": hashlib.sha256(payload).hexdigest(),
            "csv_bytes": len(payload),
            "targeted_entries": expected_entries,
            "contest_id": cid,
            "entry_id_order_sha256": _canonical_sha256(before_entry_ids),
        }
    )
    export_receipt["export_receipt_sha256"] = _canonical_sha256(export_receipt)
    return PaidClassicExport(csv_text=filled, receipt=export_receipt)


__all__ = [
    "INACTIVE_STATUSES",
    "PAID_CLASSIC_CATALOG_MAX_AGE",
    "PAID_CLASSIC_BOUNDARY_ID",
    "PaidClassicCatalog",
    "PaidClassicExport",
    "assert_exact_unique_classic_book_v2",
    "assert_paid_candidate_supply_v2",
    "build_paid_classic_catalog_v2",
    "fill_paid_entries_csv_v2",
    "paid_entry_count_v2",
    "to_paid_dk_csv_v2",
    "validate_paid_classic_book_v2",
]
