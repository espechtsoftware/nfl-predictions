"""Frozen local contract for composing the 2026 Week-1 operating book.

This module does not generate or rank lineups.  It accepts already ordered,
canonical lineup IDs from the adopted source books and deterministically
composes an exact-K entered book.  Realized outcomes are not an input.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Final

from .generation_exposure import canonical_sha256


SCHEMA_VERSION: Final = "week1-operating-book-receipt/v1"
CONTRACT_SCHEMA: Final = "week1-operating-book-contract/v1"
AMENDMENT_SCHEMA: Final = "week1-tier3-amendment/v1"
CONTRACT_ID: Final = "2026-week1-owner-adoption-20260830-v1"

DECISION_DATE: Final = "2026-08-30"
WEEK1_DEADLINE_UTC: Final = "2026-09-13T17:00:00Z"
INTERNAL_FREEZE_UTC: Final = "2026-09-11T17:00:00Z"
TIER3_EARLIEST_UTC: Final = "2026-08-31T00:00:00Z"

CORE_SOURCE_ID: Final = "boom-first-40-160"
ALL_BOOM_SOURCE_ID: Final = "ceiling-all-boom-0-200"
BX60_SOURCE_ID: Final = "cross-law-40-100-60"
BASE_SOURCE_ORDER: Final = (
    CORE_SOURCE_ID,
    ALL_BOOM_SOURCE_ID,
    BX60_SOURCE_ID,
)

SUPPORTED_K: Final = (20, 40, 80, 100)
OPERATING_K: Final = (80, 100)
TIER3_READ_ID: Final = "PREREG-026/054"
MAX_TIER3_BASIS_POINTS: Final = 500

# Repeating this schedule preserves 80/15/5 at every registered prefix:
# K20=16/3/1, K40=32/6/2, K80=64/12/4, K100=80/15/5.
BALANCED_SOURCE_SCHEDULE_20: Final = (
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
    ALL_BOOM_SOURCE_ID,
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
    BX60_SOURCE_ID,
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
    ALL_BOOM_SOURCE_ID,
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
    ALL_BOOM_SOURCE_ID,
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
    CORE_SOURCE_ID,
)

_LINEUP_ID = re.compile(r"^lineup-v1-[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class Week1OperatingBookError(ValueError):
    """The requested book violates the frozen Week-1 owner contract."""


def _fail(message: str) -> None:
    raise Week1OperatingBookError(message)


def _utc(value: str, *, label: str) -> datetime:
    if type(value) is not str or _UTC_TIMESTAMP.fullmatch(value) is None:
        _fail(f"{label} must be a second-precision UTC timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _identifier(value: object, *, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        _fail(f"{label} is not a canonical identifier")
    return value


def _is_cap4(value: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", value.lower())
    return "cap4" in compact


def _base_schedule(k: int) -> tuple[str, ...]:
    if type(k) is not int or k not in SUPPORTED_K:
        _fail(f"K must be one of {SUPPORTED_K}")
    repeats = max(SUPPORTED_K) // len(BALANCED_SOURCE_SCHEDULE_20)
    schedule = BALANCED_SOURCE_SCHEDULE_20 * repeats
    return schedule[:k]


def _base_quota(k: int) -> dict[str, int]:
    counts = Counter(_base_schedule(k))
    return {source_id: counts[source_id] for source_id in BASE_SOURCE_ORDER}


def operating_book_contract() -> dict[str, object]:
    """Return the immutable score-blind owner contract and its content hash."""

    body: dict[str, object] = {
        "schema_version": CONTRACT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "decision_date": DECISION_DATE,
        "week1_main_slate_deadline_utc": WEEK1_DEADLINE_UTC,
        "internal_book_freeze_utc": INTERNAL_FREEZE_UTC,
        "supported_prefix_k": list(SUPPORTED_K),
        "operating_k": list(OPERATING_K),
        "core": {
            "source_id": CORE_SOURCE_ID,
            "generation_id": "boom-first",
            "leverage_solves_per_block": 40,
            "boom_solves_per_block": 160,
            "optimizer_k": 1,
            "centering": "corrected-mean-centering",
            "market_blend": "props-first-with-dk-ppg-fallback",
            "selection_id": "coverage-194",
        },
        "tier2": [
            {
                "source_id": ALL_BOOM_SOURCE_ID,
                "share_basis_points": 1500,
                "generation_id": "all-boom",
                "world_order": "legal-roster-ceiling",
                "selection_id": "coverage-194",
                "frozen_on": DECISION_DATE,
            },
            {
                "source_id": BX60_SOURCE_ID,
                "share_basis_points": 500,
                "generation_id": "cross-law-bx60",
                "selection_id": "coverage-194",
                "frozen_on": DECISION_DATE,
            },
        ],
        "prefix_quotas_before_tier3": {
            str(k): _base_quota(k) for k in SUPPORTED_K
        },
        "balanced_source_schedule_20": list(BALANCED_SOURCE_SCHEDULE_20),
        "cap4": {
            "allowed_in_entered_book": False,
            "forbidden_selection_ids": [
                "cap-4-prefix",
                "cap-4-prefix-then-fill",
                "cap4-prefix-then-fill",
            ],
        },
        "tier3": {
            "status": "pending-prereg-026-054-amendment",
            "default_entered_slots": 0,
            "required_read_id": TIER3_READ_ID,
            "requires_explicit_amendment_object": True,
            "must_be_positive_and_orthogonal": True,
            "max_core_replacement_basis_points": MAX_TIER3_BASIS_POINTS,
            "changes_tier2_counts": False,
            "changes_total_k": False,
        },
        "composition": {
            "input": "ordered-canonical-lineup-ids-by-source",
            "global_lineup_deduplication": True,
            "source_dedupe_precedence": list(BASE_SOURCE_ORDER),
            "prefix_stability_authority": "allocate-k100-then-truncate",
            "duplicate_handling": "advance-within-requested-source",
            "quota_shortfall": "fail-closed",
            "uses_realized_outcomes": False,
        },
    }
    body["contract_sha256"] = canonical_sha256(body)
    return body


@dataclass(frozen=True)
class Tier3Amendment:
    """Explicit post-054 authority for a bounded Tier-3 core replacement."""

    amendment_id: str
    issued_at_utc: str
    source_id: str
    selection_id: str
    slots_by_k: tuple[tuple[int, int], ...]
    evidence_receipt_sha256: str
    read_id: str = TIER3_READ_ID
    positive: bool = True
    orthogonal_to_core: bool = True


def _validated_amendment(
    amendment: Tier3Amendment,
) -> tuple[dict[int, int], dict[str, object]]:
    if type(amendment) is not Tier3Amendment:
        _fail("Tier 3 requires an explicit Tier3Amendment object")
    amendment_id = _identifier(amendment.amendment_id, label="amendment ID")
    source_id = _identifier(amendment.source_id, label="Tier-3 source ID")
    selection_id = _identifier(
        amendment.selection_id, label="Tier-3 selection ID"
    )
    if source_id in BASE_SOURCE_ORDER:
        _fail("Tier-3 source ID collides with a frozen base source")
    if _is_cap4(source_id) or _is_cap4(selection_id):
        _fail("cap-4 is forbidden from the Week-1 entered book")
    if amendment.read_id != TIER3_READ_ID:
        _fail(f"Tier-3 amendment must bind {TIER3_READ_ID}")
    if amendment.positive is not True or amendment.orthogonal_to_core is not True:
        _fail("Tier-3 amendment must state positive and orthogonal evidence")
    if _SHA256.fullmatch(amendment.evidence_receipt_sha256) is None:
        _fail("Tier-3 evidence receipt SHA-256 is invalid")

    issued = _utc(amendment.issued_at_utc, label="Tier-3 issued_at_utc")
    earliest = _utc(TIER3_EARLIEST_UTC, label="Tier-3 earliest timestamp")
    freeze = _utc(INTERNAL_FREEZE_UTC, label="internal freeze timestamp")
    if issued < earliest or issued > freeze:
        _fail("Tier-3 amendment is outside its allowed decision window")

    try:
        slot_pairs = tuple(amendment.slots_by_k)
    except TypeError as exc:
        raise Week1OperatingBookError(
            "Tier-3 slots_by_k must be an ordered tuple"
        ) from exc
    if slot_pairs != amendment.slots_by_k:
        _fail("Tier-3 slots_by_k must be an immutable ordered tuple")
    if tuple(k for k, _count in slot_pairs) != SUPPORTED_K:
        _fail(f"Tier-3 slots_by_k must cover {SUPPORTED_K} in order")

    slots: dict[int, int] = {}
    prior = 0
    for k, count in slot_pairs:
        if type(k) is not int or type(count) is not int:
            _fail("Tier-3 slot keys and values must be integers")
        maximum = k * MAX_TIER3_BASIS_POINTS // 10_000
        if count < prior or count < 0 or count > maximum:
            _fail(f"Tier-3 slots at K{k} exceed the monotone 5% core reserve")
        slots[k] = count
        prior = count
    if not any(slots.values()):
        _fail("Tier-3 amendment does not allocate an entered slot")

    receipt: dict[str, object] = {
        "schema_version": AMENDMENT_SCHEMA,
        "amendment_id": amendment_id,
        "issued_at_utc": amendment.issued_at_utc,
        "read_id": amendment.read_id,
        "source_id": source_id,
        "selection_id": selection_id,
        "positive": amendment.positive,
        "orthogonal_to_core": amendment.orthogonal_to_core,
        "slots_by_k": {str(k): slots[k] for k in SUPPORTED_K},
        "evidence_receipt_sha256": amendment.evidence_receipt_sha256,
        "replaces_source_id": CORE_SOURCE_ID,
        "changes_tier2_counts": False,
        "changes_total_k": False,
    }
    receipt["amendment_sha256"] = canonical_sha256(receipt)
    return slots, receipt


def _schedule_with_amendment(
    amendment: Tier3Amendment | None,
) -> tuple[tuple[str, ...], dict[str, object] | None]:
    schedule = list(_base_schedule(max(SUPPORTED_K)))
    if amendment is None:
        return tuple(schedule), None
    slots, receipt = _validated_amendment(amendment)
    source_id = amendment.source_id
    previous_k = 0
    previous_slots = 0
    for k in SUPPORTED_K:
        additional = slots[k] - previous_slots
        core_positions = [
            index
            for index in range(previous_k, k)
            if schedule[index] == CORE_SOURCE_ID
        ]
        if additional > len(core_positions):
            _fail(f"Tier-3 amendment cannot replace enough core slots by K{k}")
        for index in core_positions[-additional:] if additional else ():
            schedule[index] = source_id
        previous_k = k
        previous_slots = slots[k]
    return tuple(schedule), receipt


def _source_role(source_id: str, amendment_source: str | None) -> str:
    if source_id == CORE_SOURCE_ID:
        return "tier1-core"
    if source_id in (ALL_BOOM_SOURCE_ID, BX60_SOURCE_ID):
        return "tier2-sleeve"
    if source_id == amendment_source:
        return "tier3-amended-sleeve"
    _fail(f"unknown source {source_id!r}")


def _validated_sources(
    source_lineup_ids: Mapping[str, Sequence[str]],
    *,
    amendment_source: str | None,
) -> dict[str, tuple[str, ...]]:
    if not isinstance(source_lineup_ids, Mapping):
        _fail("source lineup IDs must be a mapping")
    expected = set(BASE_SOURCE_ORDER)
    if amendment_source is not None:
        expected.add(amendment_source)
    if set(source_lineup_ids) != expected:
        _fail(
            "source lineup IDs differ from the frozen source set: "
            f"expected {sorted(expected)!r}"
        )

    validated: dict[str, tuple[str, ...]] = {}
    order = (*BASE_SOURCE_ORDER, *((amendment_source,) if amendment_source else ()))
    for source_id in order:
        raw_ids = source_lineup_ids[source_id]
        if isinstance(raw_ids, (str, bytes)) or not isinstance(raw_ids, Sequence):
            _fail(f"{source_id} lineup IDs must be an ordered sequence")
        lineup_ids = tuple(raw_ids)
        for lineup_id in lineup_ids:
            if type(lineup_id) is not str or _LINEUP_ID.fullmatch(lineup_id) is None:
                _fail(f"{source_id} contains a noncanonical lineup ID")
        validated[source_id] = lineup_ids
    return validated


def compose_week1_operating_book(
    source_lineup_ids: Mapping[str, Sequence[str]],
    *,
    k: int,
    tier3_amendment: Tier3Amendment | None = None,
) -> dict[str, object]:
    """Compose one exact-K book from frozen, ordered source memberships.

    A duplicate is claimed in frozen evidence precedence (core, all-boom,
    BX60, then an amended Tier 3).  Later sources advance through their own
    ordered book until they find a globally new lineup.  Allocation occurs at
    K100 before the requested scheduled prefix is exposed, so K20/K40/K80 are
    literal prefixes of K100 even when the source books overlap.  A source
    that cannot meet its frozen quota fails the whole composition; another
    source never fills its slots.
    """

    _base_schedule(k)  # validate K before amendment/source handling
    full_schedule, amendment_receipt = _schedule_with_amendment(tier3_amendment)
    schedule = full_schedule[:k]
    amendment_source = (
        tier3_amendment.source_id if tier3_amendment is not None else None
    )
    sources = _validated_sources(
        source_lineup_ids, amendment_source=amendment_source
    )

    quotas = Counter(schedule)
    # Allocate the largest registered book once, then expose its scheduled
    # prefix.  Without this step, a lineup shared by (for example) core rank
    # 70 and all-boom rank 1 could be assigned to all-boom at K80 but to core
    # at K100, making the nominal K80 book differ from the first 80 entries of
    # K100.  The Week-1 contract requires one stable operating book, not four
    # independently deduplicated books.
    allocation_quotas = Counter(full_schedule[:max(SUPPORTED_K)])
    source_order = list(BASE_SOURCE_ORDER)
    if amendment_source is not None:
        source_order.append(amendment_source)
    cursors = {source_id: 0 for source_id in sources}
    selected_ids: set[str] = set()
    selected_by_source: dict[str, list[tuple[int, str]]] = {}
    # Establish membership in evidence order before interleaving final entry
    # ranks.  Core therefore retains its exact prefix; each later sleeve must
    # contribute genuinely distinct rosters rather than claiming a lineup
    # that the core would already contain.
    for source_id in source_order:
        required = allocation_quotas[source_id]
        lineup_ids = sources[source_id]
        retained: list[tuple[int, str]] = []
        while len(retained) < required and cursors[source_id] < len(lineup_ids):
            source_rank = cursors[source_id] + 1
            lineup_id = lineup_ids[cursors[source_id]]
            cursors[source_id] += 1
            if lineup_id in selected_ids:
                continue
            selected_ids.add(lineup_id)
            retained.append((source_rank, lineup_id))
        if len(retained) != required:
            _fail(
                f"{source_id} cannot fill its exact quota "
                f"({len(retained)}/{required}) after global deduplication"
            )
        selected_by_source[source_id] = retained

    selected_occurrences: dict[tuple[str, int], int] = {}
    reserved_occurrences = {
        (source_id, source_rank)
        for source_id, rows in selected_by_source.items()
        for source_rank, _lineup_id in rows
    }
    entered: list[dict[str, object]] = []
    scheduled_cursors = {source_id: 0 for source_id in sources}
    for entry_rank, source_id in enumerate(schedule, start=1):
        source_rank, lineup_id = selected_by_source[source_id][
            scheduled_cursors[source_id]
        ]
        scheduled_cursors[source_id] += 1
        selected_occurrences[(source_id, source_rank)] = entry_rank
        entered.append({
            "entry_rank": entry_rank,
            "lineup_id": lineup_id,
            "source_id": source_id,
            "source_rank": source_rank,
            "source_role": _source_role(source_id, amendment_source),
            "entered": True,
        })

    entered_ids = {str(row["lineup_id"]) for row in entered}
    if len(entered) != k or len(entered_ids) != k:
        _fail(f"composition did not produce exact-{k} unique lineups")

    memberships: list[dict[str, object]] = []
    for source_id in source_order:
        seen_in_source: set[str] = set()
        for source_rank, lineup_id in enumerate(sources[source_id], start=1):
            key = (source_id, source_rank)
            entry_rank = selected_occurrences.get(key)
            duplicate_occurrence = lineup_id in seen_in_source
            seen_in_source.add(lineup_id)
            if entry_rank is not None:
                status = "entered"
            elif key in reserved_occurrences:
                status = "reserved-for-larger-prefix"
            elif lineup_id in entered_ids:
                status = "duplicate-of-entered-lineup"
            elif lineup_id in selected_ids:
                status = "duplicate-of-larger-prefix-lineup"
            elif duplicate_occurrence:
                status = "unentered-duplicate-occurrence"
            else:
                status = "unentered-source-remainder"
            memberships.append({
                "source_id": source_id,
                "source_role": _source_role(source_id, amendment_source),
                "source_rank": source_rank,
                "lineup_id": lineup_id,
                "entered": entry_rank is not None,
                "entry_rank": entry_rank,
                "status": status,
            })

    source_receipts = []
    for source_id in source_order:
        source_memberships = [
            row for row in memberships if row["source_id"] == source_id
        ]
        source_entered = [
            row for row in entered if row["source_id"] == source_id
        ]
        current_selected = selected_by_source[source_id][:quotas[source_id]]
        consumed_membership_count = (
            current_selected[-1][0] if current_selected else 0
        )
        source_receipts.append({
            "source_id": source_id,
            "source_role": _source_role(source_id, amendment_source),
            "requested_quota": quotas[source_id],
            "input_membership_count": len(source_memberships),
            "distinct_input_lineup_count": len({
                row["lineup_id"] for row in source_memberships
            }),
            "consumed_membership_count": consumed_membership_count,
            "dedupe_backfill_count": (
                consumed_membership_count - len(source_entered)
            ),
            "entered_count": len(source_entered),
            "allocation_quota_at_max_prefix": allocation_quotas[source_id],
            "reserved_for_larger_prefix_count": (
                allocation_quotas[source_id] - quotas[source_id]
            ),
            "entered_lineup_ids_sha256": canonical_sha256([
                row["lineup_id"] for row in source_entered
            ]),
        })

    contract = operating_book_contract()
    receipt: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "contract_sha256": contract["contract_sha256"],
        "decision_date": DECISION_DATE,
        "week1_main_slate_deadline_utc": WEEK1_DEADLINE_UTC,
        "internal_book_freeze_utc": INTERNAL_FREEZE_UTC,
        "k": k,
        "source_schedule": list(schedule),
        "source_quotas": {
            source_id: quotas[source_id] for source_id in source_order
        },
        "tier3_amendment": amendment_receipt,
        "cap4_used": False,
        "uses_realized_outcomes": False,
        "entered_lineups": entered,
        "unentered_lineups": [
            row for row in memberships if row["entered"] is False
        ],
        "source_memberships": memberships,
        "source_receipts": source_receipts,
        "entered_lineup_ids_sha256": canonical_sha256([
            row["lineup_id"] for row in entered
        ]),
        "source_memberships_sha256": canonical_sha256(memberships),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


__all__ = [
    "ALL_BOOM_SOURCE_ID",
    "AMENDMENT_SCHEMA",
    "BALANCED_SOURCE_SCHEDULE_20",
    "BX60_SOURCE_ID",
    "CONTRACT_ID",
    "CORE_SOURCE_ID",
    "DECISION_DATE",
    "INTERNAL_FREEZE_UTC",
    "OPERATING_K",
    "SCHEMA_VERSION",
    "SUPPORTED_K",
    "TIER3_READ_ID",
    "Tier3Amendment",
    "WEEK1_DEADLINE_UTC",
    "Week1OperatingBookError",
    "compose_week1_operating_book",
    "operating_book_contract",
]
