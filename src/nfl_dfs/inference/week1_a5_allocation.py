"""Frozen Week-1 A5 contest allocation over one ranked participation book.

This is a pre-lock mapping contract, not an entry client.  It binds the
operator's 57/20/3/10 allocation to exact DraftKings contest identities and
to nested prefixes of P_MIX, with P_CTRL, D400_DEMAX, and D800_WEMAX retained
as same-count shadows.  No contest result or realized score is accepted.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Final

from . import week1_participation_mixture as pmix
from . import week1_participation_mixture_operator as pmix_operator
from .generation_exposure import canonical_sha256
from .prospective_generation_shadow_operator import _prelock_uri

SCHEMA_VERSION: Final = "week1-a5-contest-allocation/v1"
ALLOCATION_ID: Final = "2026-w01-a5-57-20-3-10-v1"
_LINEUP_ID = re.compile(r"lineup-v1-[0-9a-f]{64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ROLES: Final = {
    "milly-5": {"entries": 57, "fee_micro": 5_000_000},
    "large-20max-3": {"entries": 20, "fee_micro": 3_000_000},
    "championship-qualifier-18": {"entries": 3, "fee_micro": 18_000_000},
    "championship-qualifier-5": {"entries": 10, "fee_micro": 5_000_000},
}
_SHADOW_BOOKS: Final = ("P_CTRL", "D400_DEMAX", "D800_WEMAX")
_IDENTITY_FIELDS: Final = frozenset({"uri", "generation", "sha256", "bytes"})
_CONTEST_FIELDS: Final = frozenset({
    "role",
    "contest_id",
    "contest_name",
    "draft_group_id",
    "field_cap",
    "entry_limit",
    "entry_fee_micro",
    "lock_utc",
    "metadata_identity",
    "payout_identity",
    "ticket_terms_identity",
})
_ALLOCATION_FIELDS: Final = frozenset({
    "schema_version",
    "allocation_id",
    "complete",
    "season",
    "week",
    "draft_group_id",
    "lock_utc",
    "participation_package_identity",
    "selection_receipt_sha256",
    "book_identities",
    "paid_policy",
    "fallback_policy",
    "shadow_policies",
    "contests",
    "paid_entry_edges",
    "shadow_entry_edges",
    "planned_entry_count",
    "planned_spend_micro",
    "accepted_entry_receipts_pending",
    "outcome_fields_read",
    "allocation_sha256",
})


class Week1A5AllocationError(ValueError):
    """A Week-1 contest or lineup mapping differs from the A5 decision."""


def _fail(message: str) -> None:
    raise Week1A5AllocationError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed mapping")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    identity = _mapping(value, label=label)
    if set(identity) != _IDENTITY_FIELDS:
        _fail(f"{label} fields differ")
    try:
        uri = _prelock_uri(identity.get("uri"), label=label)
    except Exception as exc:
        raise Week1A5AllocationError(f"{label} is not a pre-lock object") from exc
    generation = identity.get("generation")
    byte_count = identity.get("bytes")
    digest = identity.get("sha256")
    if (
        type(generation) not in {str, int}
        or not str(generation).isdigit()
        or int(generation) < 1
        or type(byte_count) is not int
        or byte_count < 1
        or type(digest) is not str
        or _SHA256.fullmatch(digest) is None
    ):
        _fail(f"{label} content identity differs")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": digest,
        "bytes": byte_count,
    }


def _lineup_ids(value: object, *, label: str) -> list[str]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered lineup sequence")
    ids = list(value)
    if any(type(item) is not str or _LINEUP_ID.fullmatch(item) is None for item in ids):
        _fail(f"{label} contains a noncanonical lineup ID")
    if len(ids) != pmix.EXACT_K or len(set(ids)) != pmix.EXACT_K:
        _fail(f"{label} must contain exactly 80 unique lineups")
    return ids


def _normalize_contests(value: object) -> list[dict[str, object]]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail("A5 contests must be an ordered sequence")
    by_role: dict[str, dict[str, object]] = {}
    contest_ids: set[str] = set()
    for ordinal, raw in enumerate(value):
        contest = _mapping(raw, label=f"contest[{ordinal}]")
        if set(contest) != _CONTEST_FIELDS:
            _fail(f"contest[{ordinal}] fields differ")
        role = contest.get("role")
        contest_id = contest.get("contest_id")
        name = contest.get("contest_name")
        if type(role) is not str or role not in _ROLES or role in by_role:
            _fail("A5 contest roles must appear exactly once")
        if (
            type(contest_id) is not str
            or not contest_id.isdigit()
            or contest_id in contest_ids
        ):
            _fail("A5 contest IDs must be unique numeric DraftKings IDs")
        if type(name) is not str or not name.strip() or name != name.strip():
            _fail("A5 contest name must be canonical and nonempty")
        expected = _ROLES[role]
        field_cap = contest.get("field_cap")
        entry_limit = contest.get("entry_limit")
        fee = contest.get("entry_fee_micro")
        if (
            type(field_cap) is not int
            or field_cap < expected["entries"]
            or type(entry_limit) is not int
            or entry_limit < expected["entries"]
            or fee != expected["fee_micro"]
        ):
            _fail(f"{role} fee, field cap, or entry-limit boundary differs")
        if role == "large-20max-3" and entry_limit != 20:
            _fail("the $3 large-field contest must be exactly 20-max")
        if (
            contest.get("draft_group_id") != pmix.DRAFT_GROUP_ID
            or contest.get("lock_utc") != pmix.LOCK_UTC
        ):
            _fail("A5 contests must bind the frozen Week-1 slate and lock")
        normalized = {
            "role": role,
            "contest_id": contest_id,
            "contest_name": name,
            "draft_group_id": pmix.DRAFT_GROUP_ID,
            "field_cap": field_cap,
            "entry_limit": entry_limit,
            "entry_fee_micro": fee,
            "lock_utc": pmix.LOCK_UTC,
            "planned_entries": expected["entries"],
            "metadata_identity": _identity(
                contest.get("metadata_identity"), label=f"{role} metadata"
            ),
            "payout_identity": _identity(
                contest.get("payout_identity"), label=f"{role} payout"
            ),
            "ticket_terms_identity": _identity(
                contest.get("ticket_terms_identity"), label=f"{role} ticket terms"
            ),
        }
        by_role[role] = normalized
        contest_ids.add(contest_id)
    if set(by_role) != set(_ROLES):
        _fail("A5 contest set is incomplete")
    return [by_role[role] for role in _ROLES]


def _entry_edges(
    *, contests: Sequence[Mapping[str, object]], books: Mapping[str, Sequence[str]]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    paid: list[dict[str, object]] = []
    shadows: list[dict[str, object]] = []
    for contest in contests:
        role = str(contest["role"])
        count = int(contest["planned_entries"])
        contest_id = str(contest["contest_id"])
        for index, lineup_id in enumerate(books["P_MIX"][:count], start=1):
            paid.append({
                "contest_role": role,
                "contest_id": contest_id,
                "entry_index": index,
                "lineup_rank": index,
                "lineup_id": lineup_id,
            })
        for book_id in _SHADOW_BOOKS:
            for index, lineup_id in enumerate(books[book_id][:count], start=1):
                shadows.append({
                    "book_id": book_id,
                    "contest_role": role,
                    "contest_id": contest_id,
                    "entry_index": index,
                    "lineup_rank": index,
                    "lineup_id": lineup_id,
                })
    return paid, shadows


def validate_week1_a5_allocation_v1(value: object) -> dict[str, object]:
    """Validate a sealed A5 allocation without reading future entry receipts."""

    allocation = _mapping(value, label="Week-1 A5 allocation")
    if set(allocation) != _ALLOCATION_FIELDS:
        _fail("Week-1 A5 allocation fields differ")
    retained_hash = allocation.pop("allocation_sha256", None)
    if type(retained_hash) is not str or _SHA256.fullmatch(retained_hash) is None:
        _fail("A5 allocation SHA-256 is invalid")
    if retained_hash != canonical_sha256(allocation):
        _fail("A5 allocation SHA-256 differs")
    if (
        allocation.get("schema_version") != SCHEMA_VERSION
        or allocation.get("allocation_id") != ALLOCATION_ID
        or allocation.get("complete") is not True
        or allocation.get("season") != pmix.SEASON
        or allocation.get("week") != pmix.WEEK
        or allocation.get("draft_group_id") != pmix.DRAFT_GROUP_ID
        or allocation.get("lock_utc") != pmix.LOCK_UTC
        or allocation.get("paid_policy") != "P_MIX"
        or allocation.get("fallback_policy") != "P_CTRL"
        or allocation.get("shadow_policies") != list(_SHADOW_BOOKS)
        or allocation.get("planned_entry_count") != 90
        or allocation.get("planned_spend_micro") != 449_000_000
        or allocation.get("accepted_entry_receipts_pending") is not True
        or allocation.get("outcome_fields_read") != []
    ):
        _fail("Week-1 A5 fixed decision boundary differs")
    _identity(
        allocation.get("participation_package_identity"),
        label="P_MIX terminal package",
    )
    selection_sha = allocation.get("selection_receipt_sha256")
    if type(selection_sha) is not str or _SHA256.fullmatch(selection_sha) is None:
        _fail("A5 selection receipt SHA-256 is invalid")

    contests = allocation.get("contests")
    if not isinstance(contests, list):
        _fail("A5 normalized contests must be a list")
    replay_contests = _normalize_contests([
        {key: row[key] for key in _CONTEST_FIELDS}
        for row in contests
        if isinstance(row, Mapping)
    ])
    if replay_contests != contests:
        _fail("A5 normalized contests do not replay exactly")
    books = _mapping(allocation.get("book_identities"), label="A5 book identities")
    if set(books) != {"P_MIX", "P_CTRL", "D400_DEMAX", "D800_WEMAX"}:
        _fail("A5 book identity set differs")
    for name in ("P_MIX", "P_CTRL"):
        row = _mapping(books[name], label=f"{name} identity")
        if (
            set(row) != {"selection_receipt_sha256", "ordered_lineup_ids_sha256"}
            or row.get("selection_receipt_sha256") != selection_sha
            or type(row.get("ordered_lineup_ids_sha256")) is not str
            or _SHA256.fullmatch(row["ordered_lineup_ids_sha256"]) is None
        ):
            _fail(f"{name} selection identity differs")
    for name in ("D400_DEMAX", "D800_WEMAX"):
        row = _mapping(books[name], label=f"{name} identity")
        if set(row) != {"artifact_identity", "ordered_lineup_ids_sha256"}:
            _fail(f"{name} identity fields differ")
        _identity(row["artifact_identity"], label=f"{name} artifact")
        digest = row.get("ordered_lineup_ids_sha256")
        if type(digest) is not str or _SHA256.fullmatch(digest) is None:
            _fail(f"{name} lineup order SHA-256 differs")

    paid_edges = allocation.get("paid_entry_edges")
    shadow_edges = allocation.get("shadow_entry_edges")
    if not isinstance(paid_edges, list) or not isinstance(shadow_edges, list):
        _fail("A5 entry edges must be lists")
    if len(paid_edges) != 90 or len(shadow_edges) != 270:
        _fail("A5 entry edge counts differ")
    for contest in contests:
        contest_id = contest["contest_id"]
        count = contest["planned_entries"]
        paid = [row for row in paid_edges if row.get("contest_id") == contest_id]
        if (
            len(paid) != count
            or [row.get("entry_index") for row in paid] != list(range(1, count + 1))
            or [row.get("lineup_rank") for row in paid] != list(range(1, count + 1))
            or len({row.get("lineup_id") for row in paid}) != count
            or any(
                row.get("contest_role") != contest["role"]
                or type(row.get("lineup_id")) is not str
                or _LINEUP_ID.fullmatch(row["lineup_id"]) is None
                for row in paid
            )
        ):
            _fail("A5 paid entry edges differ")
        for book_id in _SHADOW_BOOKS:
            shadow = [
                row
                for row in shadow_edges
                if row.get("contest_id") == contest_id
                and row.get("book_id") == book_id
            ]
            if (
                len(shadow) != count
                or [row.get("entry_index") for row in shadow]
                != list(range(1, count + 1))
                or [row.get("lineup_rank") for row in shadow]
                != list(range(1, count + 1))
                or len({row.get("lineup_id") for row in shadow}) != count
            ):
                _fail("A5 shadow entry edges differ")
    allocation["allocation_sha256"] = retained_hash
    return allocation


def build_week1_a5_allocation_v1(
    *,
    participation_package_identity: Mapping[str, object],
    participation_package: Mapping[str, object],
    participation_selection: Mapping[str, object],
    d400_lineup_ids: Sequence[str],
    d400_book_identity: Mapping[str, object],
    d800_wemax_lineup_ids: Sequence[str],
    d800_wemax_book_identity: Mapping[str, object],
    contests: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Bind the A5 decision to exact live contests and four ranked K80 books."""

    package = pmix_operator.validate_week1_participation_package_v1(
        participation_package
    )
    selection = pmix.validate_participation_selection_v1(
        participation_selection
    )
    package_identity = _identity(
        participation_package_identity, label="P_MIX terminal package"
    )
    if (
        selection["candidate_count"] != 800
        or package["selection_identity"]["sha256"]
        != canonical_sha256(selection)
        or package["candidate_ids_sha256"] != selection["candidate_ids_sha256"]
        or package["candidate_rosters_sha256"]
        != selection["candidate_rosters_sha256"]
        or package_identity["sha256"] != canonical_sha256(package)
    ):
        _fail("A5 selection does not bind the exact P_MIX D800 package")
    books = {
        "P_MIX": _lineup_ids(
            selection["P_MIX"]["ordered_lineup_ids"], label="P_MIX book"
        ),
        "P_CTRL": _lineup_ids(
            selection["P_CTRL"]["ordered_lineup_ids"], label="P_CTRL book"
        ),
        "D400_DEMAX": _lineup_ids(d400_lineup_ids, label="D400 shadow book"),
        "D800_WEMAX": _lineup_ids(
            d800_wemax_lineup_ids, label="D800_WEMAX shadow book"
        ),
    }
    normalized_contests = _normalize_contests(contests)
    paid_edges, shadow_edges = _entry_edges(
        contests=normalized_contests, books=books
    )
    if len(paid_edges) != 90 or len(shadow_edges) != 270:
        _fail("A5 edge count differs from the 57/20/3/10 decision")
    if any(
        len({row["lineup_id"] for row in paid_edges if row["contest_id"] == contest["contest_id"]})
        != contest["planned_entries"]
        for contest in normalized_contests
    ):
        _fail("A5 paid lineups must be unique within each contest")

    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "allocation_id": ALLOCATION_ID,
        "complete": True,
        "season": pmix.SEASON,
        "week": pmix.WEEK,
        "draft_group_id": pmix.DRAFT_GROUP_ID,
        "lock_utc": pmix.LOCK_UTC,
        "participation_package_identity": package_identity,
        "selection_receipt_sha256": selection["selection_receipt_sha256"],
        "book_identities": {
            "P_MIX": {
                "selection_receipt_sha256": selection["selection_receipt_sha256"],
                "ordered_lineup_ids_sha256": selection["P_MIX"][
                    "ordered_lineup_ids_sha256"
                ],
            },
            "P_CTRL": {
                "selection_receipt_sha256": selection["selection_receipt_sha256"],
                "ordered_lineup_ids_sha256": selection["P_CTRL"][
                    "ordered_lineup_ids_sha256"
                ],
            },
            "D400_DEMAX": {
                "artifact_identity": _identity(
                    d400_book_identity, label="D400 book"
                ),
                "ordered_lineup_ids_sha256": canonical_sha256(
                    books["D400_DEMAX"]
                ),
            },
            "D800_WEMAX": {
                "artifact_identity": _identity(
                    d800_wemax_book_identity, label="D800_WEMAX book"
                ),
                "ordered_lineup_ids_sha256": canonical_sha256(
                    books["D800_WEMAX"]
                ),
            },
        },
        "paid_policy": "P_MIX",
        "fallback_policy": "P_CTRL",
        "shadow_policies": list(_SHADOW_BOOKS),
        "contests": normalized_contests,
        "paid_entry_edges": paid_edges,
        "shadow_entry_edges": shadow_edges,
        "planned_entry_count": 90,
        "planned_spend_micro": 449_000_000,
        "accepted_entry_receipts_pending": True,
        "outcome_fields_read": [],
    }
    body["allocation_sha256"] = canonical_sha256(body)
    return validate_week1_a5_allocation_v1(body)


__all__ = [
    "ALLOCATION_ID",
    "SCHEMA_VERSION",
    "Week1A5AllocationError",
    "build_week1_a5_allocation_v1",
    "validate_week1_a5_allocation_v1",
]
