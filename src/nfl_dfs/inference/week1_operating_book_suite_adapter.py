"""Bind the validated generation-shadow suite to the Week-1 money book.

The generation-shadow authority contains several scientific arms and a
separate cap-4 retrieval crossing.  The entered Week-1 book is narrower: it
uses only the three frozen base coverage-194 membership orders consumed by
``week1_operating_book``.  This adapter is the score-blind, local boundary
between those two contracts.

No artifact access, outcome access, ranking, or production mutation occurs
here.  Tier 3 is deliberately unsupported until its separate amendment is
available.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Final

from .generation_exposure import canonical_sha256
from . import prospective_generation_shadow_evaluation as shadow_evaluation
from .week1_operating_book import (
    BASE_SOURCE_ORDER,
    CORE_SOURCE_ID,
    Week1OperatingBookError,
    compose_week1_operating_book,
)


SCHEMA_VERSION: Final = "week1-operating-book-suite-adapter-envelope/v1"
ADAPTER_ID: Final = "2026-week1-suite-base-membership-adapter-v1"
BASE_RETRIEVAL_ID: Final = "incumbent-cbwu-coverage-194-k80"
BASE_SELECTION_ID: Final = "coverage-194"
SOURCE_AUTHORITY_FIELD: Final = "membership_lineup_ids_by_arm"
SUPPORTED_K: Final = (80, 100)
SOURCE_BOOK_SIZE: Final = 80

_LINEUP_ID = re.compile(r"lineup-v1-[0-9a-f]{64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class Week1OperatingBookSuiteAdapterError(ValueError):
    """The suite-to-operating-book authority boundary differs."""


def _fail(message: str) -> None:
    raise Week1OperatingBookSuiteAdapterError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be a mapping")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered sequence")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _validated_k(value: object) -> int:
    if type(value) is not int or value not in SUPPORTED_K:
        _fail(f"K must be one of {SUPPORTED_K}")
    return value


def _lineup_ids(value: object, *, source_id: str) -> tuple[str, ...]:
    raw = _sequence(value, label=f"{source_id} membership book")
    lineup_ids: list[str] = []
    for lineup_id in raw:
        if type(lineup_id) is not str or _LINEUP_ID.fullmatch(lineup_id) is None:
            _fail(f"{source_id} membership book has a noncanonical lineup ID")
        lineup_ids.append(lineup_id)
    if len(lineup_ids) != SOURCE_BOOK_SIZE:
        _fail(f"{source_id} membership book is not exact-{SOURCE_BOOK_SIZE}")
    if len(set(lineup_ids)) != len(lineup_ids):
        _fail(f"{source_id} membership book repeats a lineup")
    return tuple(lineup_ids)


def _source_bindings(
    sources: Mapping[str, Sequence[str]],
) -> list[dict[str, object]]:
    bindings: list[dict[str, object]] = []
    for source_id in BASE_SOURCE_ORDER:
        if source_id not in sources:
            _fail(f"source book {source_id} is absent")
        lineup_ids = list(sources[source_id])
        bindings.append({
            "source_id": source_id,
            "lineup_count": len(lineup_ids),
            "ordered_lineup_ids_sha256": canonical_sha256(lineup_ids),
        })
    return bindings


def _validated_authority_sources(
    authority: Mapping[str, object],
) -> dict[str, tuple[str, ...]]:
    if (
        authority.get("schema_version")
        != shadow_evaluation.SUITE_AUTHORITY_SCHEMA
        or authority.get("complete") is not True
    ):
        _fail("suite authority completion/schema differs")
    _digest(
        authority.get("suite_authority_sha256"),
        label="suite authority SHA-256",
    )

    for document_name in ("manifest", "terminal"):
        document = _mapping(
            authority.get(document_name), label=f"suite {document_name}"
        )
        if (
            document.get("uses_realized_outcomes") is not False
            or document.get("post_lock_data_read") is not False
        ):
            _fail(f"suite {document_name} is not score-blind and pre-lock")

    memberships = _mapping(
        authority.get(SOURCE_AUTHORITY_FIELD),
        label="suite base membership books",
    )
    if set(memberships) != set(shadow_evaluation.ARM_ORDER):
        _fail("suite membership source registry differs")
    sources = {
        source_id: _lineup_ids(memberships[source_id], source_id=source_id)
        for source_id in BASE_SOURCE_ORDER
    }

    # The suite carries cap-4 only as a separate scientific crossing.  Bind
    # the boom-first membership order to the crossing's named base retrieval
    # without reading or admitting the cap-4 book.
    retrievals = _mapping(
        authority.get("retrieval_lineup_ids_by_population"),
        label="suite retrieval population books",
    )
    for source_id in BASE_SOURCE_ORDER:
        raw_retrievals = retrievals.get(source_id)
        if raw_retrievals is None:
            if source_id == CORE_SOURCE_ID:
                _fail("boom-first base-retrieval authority is absent")
            continue
        source_retrievals = _mapping(
            raw_retrievals,
            label=f"suite {source_id} retrieval books",
        )
        base_book = _lineup_ids(
            source_retrievals.get(BASE_RETRIEVAL_ID), source_id=source_id
        )
        if base_book != sources[source_id]:
            _fail(
                f"{source_id} base-retrieval and membership source orders "
                "differ"
            )
    return sources


def _receipt_sources(receipt: Mapping[str, object]) -> dict[str, tuple[str, ...]]:
    memberships = _sequence(
        receipt.get("source_memberships"),
        label="compositor source memberships",
    )
    gathered: dict[str, list[str]] = {
        source_id: [] for source_id in BASE_SOURCE_ORDER
    }
    next_rank = {source_id: 1 for source_id in BASE_SOURCE_ORDER}
    for raw_row in memberships:
        row = _mapping(raw_row, label="compositor source membership")
        source_id = row.get("source_id")
        if source_id not in gathered:
            _fail("compositor receipt contains an unexpected source")
        expected_rank = next_rank[source_id]
        if row.get("source_rank") != expected_rank:
            _fail(f"{source_id} compositor source order differs")
        lineup_id = row.get("lineup_id")
        if type(lineup_id) is not str or _LINEUP_ID.fullmatch(lineup_id) is None:
            _fail("compositor receipt contains a noncanonical lineup ID")
        gathered[source_id].append(lineup_id)
        next_rank[source_id] += 1
    return {
        source_id: _lineup_ids(gathered[source_id], source_id=source_id)
        for source_id in BASE_SOURCE_ORDER
    }


def validate_week1_operating_book_suite_envelope_v1(
    value: object,
) -> dict[str, object]:
    """Reopen and fully recompute a suite-adapter envelope."""

    envelope = dict(_mapping(value, label="Week-1 suite adapter envelope"))
    fields = {
        "schema_version",
        "adapter_id",
        "complete",
        "suite_authority_schema_version",
        "suite_authority_sha256",
        "k",
        "source_authority_field",
        "source_arm_order",
        "source_arm_order_sha256",
        "source_book_bindings",
        "source_book_bindings_sha256",
        "base_retrieval_id",
        "base_selection_id",
        "cap4_used",
        "tier3_used",
        "uses_realized_outcomes",
        "outcome_fields",
        "compositor_receipt",
        "compositor_receipt_sha256",
        "envelope_sha256",
    }
    if set(envelope) != fields:
        _fail("Week-1 suite adapter envelope fields differ")
    retained_envelope_hash = _digest(
        envelope.get("envelope_sha256"), label="adapter envelope SHA-256"
    )
    unhashed = dict(envelope)
    unhashed.pop("envelope_sha256")
    if retained_envelope_hash != canonical_sha256(unhashed):
        _fail("Week-1 suite adapter envelope hash differs")

    k = _validated_k(envelope.get("k"))
    if (
        envelope.get("schema_version") != SCHEMA_VERSION
        or envelope.get("adapter_id") != ADAPTER_ID
        or envelope.get("complete") is not True
        or envelope.get("suite_authority_schema_version")
        != shadow_evaluation.SUITE_AUTHORITY_SCHEMA
        or envelope.get("source_authority_field") != SOURCE_AUTHORITY_FIELD
        or envelope.get("source_arm_order") != list(BASE_SOURCE_ORDER)
        or envelope.get("base_retrieval_id") != BASE_RETRIEVAL_ID
        or envelope.get("base_selection_id") != BASE_SELECTION_ID
        or envelope.get("cap4_used") is not False
        or envelope.get("tier3_used") is not False
        or envelope.get("uses_realized_outcomes") is not False
        or envelope.get("outcome_fields") != []
    ):
        _fail("Week-1 suite adapter fixed base-retrieval law differs")
    _digest(
        envelope.get("suite_authority_sha256"),
        label="bound suite authority SHA-256",
    )
    if envelope.get("source_arm_order_sha256") != canonical_sha256(
        list(BASE_SOURCE_ORDER)
    ):
        _fail("source arm order hash differs")

    receipt = dict(_mapping(
        envelope.get("compositor_receipt"), label="compositor receipt"
    ))
    retained_receipt_hash = _digest(
        envelope.get("compositor_receipt_sha256"),
        label="bound compositor receipt SHA-256",
    )
    if (
        receipt.get("receipt_sha256") != retained_receipt_hash
        or receipt.get("k") != k
        or receipt.get("cap4_used") is not False
        or receipt.get("uses_realized_outcomes") is not False
        or receipt.get("tier3_amendment") is not None
    ):
        _fail("bound compositor receipt fixed law differs")
    sources = _receipt_sources(receipt)
    try:
        rebuilt_receipt = compose_week1_operating_book(sources, k=k)
    except (ValueError, TypeError, KeyError) as exc:
        raise Week1OperatingBookSuiteAdapterError(
            "bound compositor receipt cannot be recomputed"
        ) from exc
    if rebuilt_receipt != receipt:
        _fail("bound compositor receipt differs from exact recomputation")

    expected_bindings = _source_bindings(sources)
    raw_bindings = envelope.get("source_book_bindings")
    if raw_bindings != expected_bindings:
        _fail("source order bindings differ")
    if envelope.get("source_book_bindings_sha256") != canonical_sha256(
        expected_bindings
    ):
        _fail("source order binding hash differs")
    return envelope


def build_week1_operating_book_from_suite_authority_v1(
    suite_authority: object,
    *,
    k: int,
    retrieval_id: str = BASE_RETRIEVAL_ID,
) -> dict[str, object]:
    """Compose K80/K100 from three validated base membership books only."""

    retained_k = _validated_k(k)
    if retrieval_id != BASE_RETRIEVAL_ID:
        _fail("only the no-cap4 base coverage-194 retrieval is permitted")
    try:
        authority = shadow_evaluation.validate_suite_authority_v1(
            suite_authority
        )
    except Exception as exc:
        raise Week1OperatingBookSuiteAdapterError(
            "suite authority validation failed"
        ) from exc
    authority = _mapping(authority, label="validated suite authority")
    sources = _validated_authority_sources(authority)
    source_bindings = _source_bindings(sources)
    source_projection_before = canonical_sha256(source_bindings)

    # Tuples prevent the compositor from mutating an authority-derived order.
    compositor_input = {
        source_id: tuple(sources[source_id]) for source_id in BASE_SOURCE_ORDER
    }
    try:
        receipt = compose_week1_operating_book(
            compositor_input, k=retained_k
        )
    except Week1OperatingBookError as exc:
        raise Week1OperatingBookSuiteAdapterError(
            "Week-1 compositor rejected the validated source books"
        ) from exc
    if canonical_sha256(_source_bindings(sources)) != source_projection_before:
        _fail("suite source membership orders mutated during composition")

    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "adapter_id": ADAPTER_ID,
        "complete": True,
        "suite_authority_schema_version": authority["schema_version"],
        "suite_authority_sha256": authority["suite_authority_sha256"],
        "k": retained_k,
        "source_authority_field": SOURCE_AUTHORITY_FIELD,
        "source_arm_order": list(BASE_SOURCE_ORDER),
        "source_arm_order_sha256": canonical_sha256(list(BASE_SOURCE_ORDER)),
        "source_book_bindings": source_bindings,
        "source_book_bindings_sha256": source_projection_before,
        "base_retrieval_id": BASE_RETRIEVAL_ID,
        "base_selection_id": BASE_SELECTION_ID,
        "cap4_used": False,
        "tier3_used": False,
        "uses_realized_outcomes": False,
        "outcome_fields": [],
        "compositor_receipt": receipt,
        "compositor_receipt_sha256": receipt["receipt_sha256"],
    }
    body["envelope_sha256"] = canonical_sha256(body)
    return validate_week1_operating_book_suite_envelope_v1(body)


__all__ = [
    "ADAPTER_ID",
    "BASE_RETRIEVAL_ID",
    "BASE_SELECTION_ID",
    "SCHEMA_VERSION",
    "SOURCE_AUTHORITY_FIELD",
    "SUPPORTED_K",
    "Week1OperatingBookSuiteAdapterError",
    "build_week1_operating_book_from_suite_authority_v1",
    "validate_week1_operating_book_suite_envelope_v1",
]
