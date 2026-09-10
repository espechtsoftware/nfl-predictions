"""Fail-closed Week-1 A5 capture evidence contracts.

This module is an evidence adapter only.  It does not score, generate, select,
upload, or settle entries.  Every fact used by a contract is parsed from bytes
reopened at one exact object generation.  Provider observations additionally
require recognition by a separate authenticated-acquisition authority; a raw
object-store identity alone has no source authority.  A semantic artifact hash
and the hash of its serialized object are intentionally different identities.

The live allocation pins remain deliberately unset until the four final books,
player bridge, and allocation object have been published create-once and
independently reopened.  ``live_capture_pins`` therefore fails closed today.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Final, Protocol

from nfl_dfs.inference.generation_exposure import (
    canonical_json_bytes,
    canonical_sha256,
)

PRELOCK_SCHEMA: Final = "dk-contest-manifest/v3"
ALLOCATION_SCHEMA: Final = "week1-a5-allocation-authority/v2"
BOOK_SCHEMA: Final = "week1-a5-book-materialization/v2"
SALARY_CATALOG_SCHEMA: Final = "week1-a5-paid-salary-catalog/v1"
PLAYER_BRIDGE_SCHEMA: Final = "week1-a5-player-bridge/v1"
PROVIDER_ACQUISITION_SCHEMA: Final = "dk-authenticated-provider-acquisition/v1"
PROVIDER_TRANSPORT_TRACE_SCHEMA: Final = "dk-authenticated-transport-trace/v1"
PROVIDER_ACQUISITION_AUTHORITY_PROFILE: Final = (
    "repository-governed-dk-acquisition/v1"
)
PROVIDER_AUTHENTICATED_SURFACE: Final = (
    "draftkings-authenticated-account-session/v1"
)
ACCEPTANCE_ACQUISITION_PROFILE: Final = "active-entry-export-download/v1"
CONTEST_DETAIL_ACQUISITION_PROFILE: Final = "contest-detail-api-get/v1"
STANDINGS_ACQUISITION_PROFILE: Final = "full-standings-export-download/v1"
ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA: Final = (
    "dk-accepted-entry-provider-capture/v2"
)
ACCEPTED_EVIDENCE_SCHEMA: Final = "dk-accepted-entry-evidence/v2"
ACCEPTANCE_SCHEMA: Final = "week1-a5-entry-acceptance/v2"
ACCEPTANCE_ROOT_SCHEMA: Final = "week1-a5-entry-acceptance-root/v2"
# Retained only so old callers receive an explicit retirement error.  The v1
# shape put caller-authored contest state and field size next to a source URL;
# those values were not parsed from the provider response.
FINAL_FIELD_SOURCE_SCHEMA: Final = "dk-final-field-provider-source/v1"
FINAL_FIELD_PROVIDER_CAPTURE_SCHEMA: Final = (
    "dk-final-field-provider-capture/v2"
)
FINAL_FIELD_EVIDENCE_SCHEMA: Final = "dk-final-field-evidence/v2"
NORMALIZED_STANDINGS_SCHEMA: Final = "dk-normalized-complete-field/v2"
SETTLEMENT_SCHEMA: Final = "dk-contest-settlement/v2"

ACCEPTANCE_CAPTURE_METHOD: Final = "authenticated-active-entry-export-csv"
FINAL_FIELD_CAPTURE_METHOD: Final = (
    "contest-detail-api-and-full-standings-export"
)
ACCEPTANCE_SOURCE_LOCATOR: Final = "https://www.draftkings.com/mycontests"
# No exact active-entry download URL/HAR profile has been observed yet.  The
# account page above is a human-facing surface, not an acquisition locator.
# Live acquisition therefore fails closed until a redacted real-shape smoke
# establishes and an independent review pins the exact response/download
# locator.  Tests replace only this explicit absent pin with a fixture URL.
PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR: Final[str | None] = None
FINAL_FIELD_SOURCE_LOCATOR_PREFIX: Final = (
    "https://api.draftkings.com/contests/v1/contests/"
)
FINAL_STANDINGS_SOURCE_LOCATOR_PREFIX: Final = (
    "https://www.draftkings.com/contest/exportfullstandingscsv/"
)
_SETTLED_CONTEST_STATES: Final = frozenset(
    {"Complete", "Completed", "Final", "Settled"}
)

EXPECTED_ROLE_ENTRIES: Final = MappingProxyType(
    {
        "milly-5": 57,
        "large-20max-3": 20,
        "championship-qualifier-18": 3,
        "championship-qualifier-5": 10,
    }
)
EXPECTED_POLICIES: Final = ("P_MIX", "P_CTRL", "D400_DEMAX", "D800_WEMAX")
SHADOW_POLICIES: Final = ("P_CTRL", "D400_DEMAX", "D800_WEMAX")
EXPECTED_SLATE_ID: Final = "dk-151307"
EXPECTED_DRAFT_GROUP_ID: Final = "151307"
EXPECTED_LOCK_UTC: Final = "2026-09-13T17:00:00Z"
EXPECTED_ALLOCATION_ID: Final = "2026-w01-a5-57-20-3-10-v1"
EXPECTED_PLANNED_ENTRIES: Final = 90
EXPECTED_PLANNED_SPEND_MICRO: Final = 449_000_000
EXPECTED_BOOK_SIZE: Final = 80
SALARY_CAP: Final = 50_000
MAX_FROM_TEAM: Final = 4
CLASSIC_SLOTS: Final = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
QUALIFIER_TICKET_NAMES: Final = (
    "NFL 2026 $12.5M FFWC Contest Ticket",
    "NFL 2026 $1.5M FFWC Afternoon Only Contest Ticket",
)
TEMPLATE_PROJECTION_SEMANTIC_SHA256: Final = (
    "dc449a918f15e9bee25171c4867039b4097fac4bc11008e437845b684936f7a0"
)
TEMPLATE_AUTHORITY: Final = (
    "reports/2026-09-04-week1-a5-live-contest-capture.md#public-lobby-projection"
)


@dataclass(frozen=True)
class ContestPin:
    role: str
    contest_id: str
    name: str
    entry_fee_micro: int
    advertised_field_capacity: int
    entry_limit: int
    template_id: str
    is_qualifier: bool
    advertised_prize_pool_micro: int
    planned_entries: int


_ROLE_ROWS = (
    ContestPin(
        "milly-5",
        "193028206",
        "NFL $3.5M Fantasy Football Millionaire [$1M to 1st]",
        5_000_000,
        832_342,
        150,
        "963916",
        False,
        3_500_000_000_000,
        57,
    ),
    ContestPin(
        "large-20max-3",
        "193028208",
        "NFL $400K Play-Action [20 Entry Max]",
        3_000_000,
        158_541,
        20,
        "388597",
        False,
        400_000_000_000,
        20,
    ),
    ContestPin(
        "championship-qualifier-18",
        "194478066",
        "$14M 2026 Fantasy Football World Championship Qualifier #6",
        18_000_000,
        5_000,
        150,
        "970817",
        True,
        76_500_000_000,
        3,
    ),
    ContestPin(
        "championship-qualifier-5",
        "194478065",
        "$14M 2026 Fantasy Football World Championship Qualifier #5",
        5_000_000,
        17_835,
        150,
        "970816",
        True,
        75_000_000_000,
        10,
    ),
)
A5_ROLE_TABLE: Final = MappingProxyType({row.role: row for row in _ROLE_ROWS})

PINNED_SOURCE_MANIFEST_IDENTITY: Final = MappingProxyType(
    {
        "uri": "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/"
        "contests/a5/20260904T105535Z/manifest.json",
        "generation": "1788519340044066",
        "sha256": "28408ab4e57d8f994d29d8afe16b86d9d2fc14cf02f0a89ccd2af76929d17dd4",
        "bytes": 2664,
    }
)
PINNED_CONTEST_SOURCE_IDENTITIES: Final = MappingProxyType(
    {
        "193028206": MappingProxyType(
            {
                "uri": "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/"
                "contests/a5/20260904T105535Z/contest-193028206.json",
                "generation": "1788519338008617",
                "sha256": "fc90746752ca351b5aaace7f8355327d3d425c09ef1235fbe649fc3c47087bfa",
                "bytes": 9220,
            }
        ),
        "193028208": MappingProxyType(
            {
                "uri": "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/"
                "contests/a5/20260904T105535Z/contest-193028208.json",
                "generation": "1788519338593279",
                "sha256": "5349b02fde739fbefb0e0eee0000072d8780e5202692eddf6de8cd71822f6602",
                "bytes": 7784,
            }
        ),
        "194478065": MappingProxyType(
            {
                "uri": "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/"
                "contests/a5/20260904T105535Z/contest-194478065.json",
                "generation": "1788519339081128",
                "sha256": "5126b875ea4ba8dcc323498cd4c644d6eb499315428802197c49f6505349b5ac",
                "bytes": 5137,
            }
        ),
        "194478066": MappingProxyType(
            {
                "uri": "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/"
                "contests/a5/20260904T105535Z/contest-194478066.json",
                "generation": "1788519339562982",
                "sha256": "ef081a6b0941eedbe539c232d8683babcbe43e5a560aea7861cba5db9738e1ab",
                "bytes": 4901,
            }
        ),
    }
)
PINNED_TEMPLATE_PROJECTION_IDENTITY: Final = MappingProxyType(
    {
        "uri": "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/"
        "contests/a5/20260904T104754Z/lobby-template-projection.json",
        "generation": "1789039703362881",
        "sha256": "5a98a3ebeb03e0f95afe8845e1f66cf7a21882054f45dd23ef9e85cde60611ee",
        "bytes": 2104,
    }
)

# Deliberately absent until a real final allocation is published/reopened.
PINNED_ALLOCATION_IDENTITY: Final[Mapping[str, object] | None] = None
PINNED_ALLOCATION_SEMANTIC_SHA256: Final[str | None] = None

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LINEUP = re.compile(r"lineup-v1-([0-9a-f]{64})\Z")
_PLAYER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_FILLED_CELL = re.compile(r"^.+ \(([0-9]+)\)$")
_IDENTITY_FIELDS = frozenset({"uri", "generation", "sha256", "bytes"})
_CENT_MICRO = 10_000
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_AUTHORITY_EVENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}\Z")


class Week1A5CaptureContractError(ValueError):
    """An immutable Week-1 A5 evidence contract failed closed."""


class ImmutableObjectStore(Protocol):
    """One create-once/exact-generation object boundary."""

    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> Mapping[str, object]: ...

    def read_exact(
        self, *, identity: Mapping[str, object]
    ) -> Mapping[str, object]: ...


class AuthenticatedProviderAcquisitionAuthority(Protocol):
    """Independent trust root for one governed authenticated acquisition.

    The generic object store proves byte immutability only.  This separate
    boundary must refuse any receipt that was not emitted by the governed
    authenticated collector.  Implementations may back this with a signed
    collector ledger, an independently retained browser/download event log,
    or an equivalent reviewed authority.  Callers cannot promote a raw GCS
    object merely by placing it in a provider-looking namespace.
    """

    def read_authenticated_acquisition(
        self, *, identity: Mapping[str, object]
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class A5SourcePins:
    manifest_identity: Mapping[str, object]
    contest_identities: Mapping[str, Mapping[str, object]]
    template_projection_identity: Mapping[str, object] | None = None
    template_projection_semantic_sha256: str = TEMPLATE_PROJECTION_SEMANTIC_SHA256


@dataclass(frozen=True)
class A5CapturePins:
    source: A5SourcePins
    allocation_identity: Mapping[str, object]
    allocation_semantic_sha256: str


@dataclass(frozen=True)
class ReopenedObject:
    identity: dict[str, object]
    created_at: str
    created: datetime
    raw: bytes


@dataclass(frozen=True)
class ReopenedAcquisition:
    receipt: dict[str, object]
    receipt_object: ReopenedObject
    raw_object: ReopenedObject


def _fail(message: str) -> None:
    raise Week1A5CaptureContractError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact(value: Mapping[str, object], fields: set[str] | frozenset[str], *, label: str) -> None:
    if set(value) != set(fields):
        _fail(
            f"{label} fields differ: missing={sorted(set(fields) - set(value))} "
            f"unexpected={sorted(set(value) - set(fields))}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{label} must be a canonical nonempty string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _signed_integer(value: object, *, label: str) -> int:
    if type(value) is not int:
        _fail(f"{label} must be an integer")
    return value


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    text = _string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Week1A5CaptureContractError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(f"{label} must include a UTC offset")
    parsed = parsed.astimezone(UTC)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _publish_by(
    value: object,
    *,
    label: str,
    phase: str,
) -> tuple[str, datetime]:
    """Validate an executable prospective create-once publication cutoff.

    ``frozen_at`` and ``accepted_at`` fields in this module are deadlines by
    which the artifact itself must exist at its immutable provider generation;
    they are not claims that a GCS object was created before it was uploaded.
    Source observation times are represented separately and must precede the
    provider creation time of their archived raw bytes.
    """

    text, cutoff = _timestamp(value, label=label)
    _, lock = _timestamp(EXPECTED_LOCK_UTC, label="A5 lock")
    if phase == "prelock":
        if cutoff >= lock:
            _fail(f"{label} must be strictly before lock")
    elif phase == "postlock":
        if cutoff <= lock:
            _fail(f"{label} must be strictly after lock")
    else:  # Defensive because phase is an internal control, not caller data.
        raise AssertionError(f"unsupported publication phase {phase!r}")
    return text, cutoff


def _identity(value: object, *, label: str) -> dict[str, object]:
    row = _mapping(value, label=label)
    _exact(row, _IDENTITY_FIELDS, label=label)
    uri = _string(row.get("uri"), label=f"{label}.uri")
    if not uri.startswith("gs://") or uri.endswith("/") or "/" not in uri[5:]:
        _fail(f"{label}.uri must name one generation-free gs:// object")
    generation = row.get("generation")
    if type(generation) not in {str, int} or not str(generation).isdigit():
        _fail(f"{label}.generation must identify one immutable generation")
    if int(str(generation)) < 1:
        _fail(f"{label}.generation must be positive")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": _sha(row.get("sha256"), label=f"{label}.sha256"),
        "bytes": _integer(row.get("bytes"), label=f"{label}.bytes", minimum=1),
    }


def _identity_equal(left: object, right: object, *, label: str) -> dict[str, object]:
    retained = _identity(left, label=label)
    if retained != _identity(right, label=f"expected {label}"):
        _fail(f"{label} differs from its exact pinned identity")
    return retained


def _reopen_exact(
    store: ImmutableObjectStore,
    identity: object,
    *,
    label: str,
    not_after: datetime | None = None,
    not_before: datetime | None = None,
) -> ReopenedObject:
    expected = _identity(identity, label=f"{label} identity")
    try:
        receipt = _mapping(
            store.read_exact(identity=expected), label=f"{label} exact-read receipt"
        )
    except Exception as exc:
        if isinstance(exc, Week1A5CaptureContractError):
            raise
        raise Week1A5CaptureContractError(f"{label} exact reopen failed") from exc
    _exact(receipt, {"identity", "created_at", "raw"}, label=f"{label} exact-read receipt")
    _identity_equal(receipt.get("identity"), expected, label=f"{label} reopened identity")
    raw = receipt.get("raw")
    if not isinstance(raw, bytes) or not raw:
        _fail(f"{label} exact reopen must return nonempty bytes")
    if len(raw) != expected["bytes"] or hashlib.sha256(raw).hexdigest() != expected["sha256"]:
        _fail(f"{label} exact reopened bytes/hash differ")
    created_at, created = _timestamp(receipt.get("created_at"), label=f"{label}.created_at")
    if not_after is not None and created > not_after:
        _fail(f"{label} provider creation time is after its evidence boundary")
    if not_before is not None and created < not_before:
        _fail(f"{label} provider creation time precedes its evidence boundary")
    return ReopenedObject(expected, created_at, created, raw)


def _parse_json(raw: bytes, *, label: str, canonical: bool = False) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Week1A5CaptureContractError(f"{label} is not valid JSON") from exc
    row = _mapping(value, label=label)
    if canonical and canonical_json_bytes(row) != raw:
        _fail(f"{label} bytes are not canonical JSON")
    return row


def seal_semantic_artifact(value: Mapping[str, object]) -> dict[str, object]:
    """Return a semantic artifact whose hash excludes only its hash field."""

    body = dict(value)
    if "semantic_sha256" in body:
        _fail("semantic_sha256 already exists")
    body["semantic_sha256"] = canonical_sha256(body)
    return body


def validate_semantic_artifact(value: object, *, label: str) -> dict[str, object]:
    row = _mapping(value, label=label)
    retained = _sha(row.pop("semantic_sha256", None), label=f"{label}.semantic_sha256")
    if canonical_sha256(row) != retained:
        _fail(f"{label}.semantic_sha256 differs from its semantic body")
    row["semantic_sha256"] = retained
    return row


def _reopen_semantic(
    store: ImmutableObjectStore,
    identity: object,
    *,
    label: str,
    expected_semantic_sha256: object | None = None,
    not_after: datetime | None = None,
    not_before: datetime | None = None,
) -> tuple[dict[str, object], ReopenedObject]:
    reopened = _reopen_exact(
        store,
        identity,
        label=label,
        not_after=not_after,
        not_before=not_before,
    )
    value = validate_semantic_artifact(
        _parse_json(reopened.raw, label=label, canonical=True), label=label
    )
    if expected_semantic_sha256 is not None:
        expected = _sha(expected_semantic_sha256, label=f"{label} pinned semantic hash")
        if value["semantic_sha256"] != expected:
            _fail(f"{label} differs from its pinned semantic root")
    return value, reopened


def publish_semantic_artifact(
    store: ImmutableObjectStore,
    *,
    uri: str,
    artifact: object,
    not_after: object | None = None,
    not_before: object | None = None,
) -> dict[str, object]:
    """Publish canonical bytes create-once, then independently reopen them."""

    value = validate_semantic_artifact(artifact, label="artifact")
    raw = canonical_json_bytes(value)
    try:
        receipt = _mapping(
            store.publish_create_once(uri=uri, raw=raw, content_type="application/json"),
            label="publication receipt",
        )
    except Exception as exc:
        if isinstance(exc, Week1A5CaptureContractError):
            raise
        raise Week1A5CaptureContractError("create-once publication failed") from exc
    _exact(receipt, {"identity", "created_at"}, label="publication receipt")
    identity = _identity(receipt.get("identity"), label="published identity")
    if identity["uri"] != uri:
        _fail("publisher returned another object URI")
    if identity["bytes"] != len(raw) or identity["sha256"] != hashlib.sha256(raw).hexdigest():
        _fail("publisher returned a false raw content identity")
    boundary_after = (
        _timestamp(not_after, label="publication not_after")[1]
        if not_after is not None
        else None
    )
    boundary_before = (
        _timestamp(not_before, label="publication not_before")[1]
        if not_before is not None
        else None
    )
    if (
        boundary_after is not None
        and boundary_before is not None
        and boundary_before > boundary_after
    ):
        _fail("publication time window is inverted")
    reopened_value, reopened = _reopen_semantic(
        store,
        identity,
        label="published artifact",
        expected_semantic_sha256=value["semantic_sha256"],
        not_after=boundary_after,
        not_before=boundary_before,
    )
    if reopened.raw != raw or reopened_value != value:
        _fail("independent exact reopen differs from published artifact")
    return {
        "artifact_identity": identity,
        "semantic_sha256": value["semantic_sha256"],
        "created_at": reopened.created_at,
    }


def pinned_source_pins() -> A5SourcePins:
    return A5SourcePins(
        manifest_identity=dict(PINNED_SOURCE_MANIFEST_IDENTITY),
        contest_identities={
            contest_id: dict(identity)
            for contest_id, identity in PINNED_CONTEST_SOURCE_IDENTITIES.items()
        },
        template_projection_identity=dict(PINNED_TEMPLATE_PROJECTION_IDENTITY),
        template_projection_semantic_sha256=TEMPLATE_PROJECTION_SEMANTIC_SHA256,
    )


def _require_exact_source_pins(source_pins: A5SourcePins) -> None:
    """Reject any source root other than the code-pinned A5 capture."""

    _identity_equal(
        source_pins.manifest_identity,
        PINNED_SOURCE_MANIFEST_IDENTITY,
        label="terminal contest-source manifest identity",
    )
    if set(source_pins.contest_identities) != set(PINNED_CONTEST_SOURCE_IDENTITIES):
        _fail("contest-source pin set differs from the exact four A5 children")
    for contest_id, expected in PINNED_CONTEST_SOURCE_IDENTITIES.items():
        _identity_equal(
            source_pins.contest_identities[contest_id],
            expected,
            label=f"contest {contest_id} source identity",
        )
    _identity_equal(
        source_pins.template_projection_identity,
        PINNED_TEMPLATE_PROJECTION_IDENTITY,
        label="lobby/template projection identity",
    )
    if (
        _sha(
            source_pins.template_projection_semantic_sha256,
            label="template projection semantic hash",
        )
        != TEMPLATE_PROJECTION_SEMANTIC_SHA256
    ):
        _fail("template projection differs from the exact September 4 semantic root")


def live_capture_pins() -> A5CapturePins:
    if PINNED_ALLOCATION_IDENTITY is None or PINNED_ALLOCATION_SEMANTIC_SHA256 is None:
        _fail(
            "live A5 allocation raw/semantic identity is not published and pinned; "
            "capture remains HOLD"
        )
    return A5CapturePins(
        source=pinned_source_pins(),
        allocation_identity=dict(PINNED_ALLOCATION_IDENTITY),
        allocation_semantic_sha256=PINNED_ALLOCATION_SEMANTIC_SHA256,
    )


def _boolish(value: object) -> bool:
    if type(value) is bool:
        return value
    if type(value) is str and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    _fail("boolean source field has an unsupported representation")


def _money_micro(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        _fail(f"{label} must be a decimal money value")
    try:
        retained = Decimal(str(value)) * Decimal(1_000_000)
    except InvalidOperation as exc:
        raise Week1A5CaptureContractError(f"{label} is invalid money") from exc
    if retained != retained.to_integral_value() or retained < 0:
        _fail(f"{label} must be exact nonnegative micro-units")
    return int(retained)


def _source_payouts(value: object, *, pin: ContestPin) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    last = 0
    for ordinal, raw in enumerate(_sequence(value, label="payoutSummary")):
        tier = _mapping(raw, label=f"payoutSummary[{ordinal}]")
        start = _integer(tier.get("minPosition"), label="payout minPosition", minimum=1)
        end = _integer(tier.get("maxPosition"), label="payout maxPosition", minimum=start)
        if start != last + 1 or end > pin.advertised_field_capacity:
            _fail("source payout ranks are not contiguous and capacity-bounded")
        descriptions = _sequence(tier.get("payoutDescriptions"), label="payoutDescriptions")
        if len(descriptions) != 1:
            _fail("source payout tier must contain one exact award description")
        description = _mapping(descriptions[0], label="payout description")
        _exact(
            description,
            {
                "order",
                "payoutDescription",
                "payoutDescriptionType",
                "quantity",
                "value",
            },
            label="payout description",
        )
        if description["order"] != 1 or description["payoutDescriptionType"] != "Text":
            _fail("source payout description encoding differs")
        quantity = _integer(description.get("quantity"), label="award quantity", minimum=1)
        amount = _money_micro(description.get("value"), label="award value")
        tier_labels = _mapping(tier.get("tierPayoutDescriptions"), label="tier award labels")
        if set(tier_labels) == {"Cash"}:
            cash_label = _string(tier_labels["Cash"], label="cash award label")
            if description["payoutDescription"] != cash_label:
                _fail("source cash award description/label differ")
            normalized_cash = cash_label.replace("$", "").replace(",", "")
            if _money_micro(normalized_cash, label="cash award label") != amount:
                _fail("source cash award label/value differ")
            award = {
                "kind": "cash",
                "cash_micro": amount,
                "ticket_destinations": [],
                "quantity": quantity,
            }
        elif set(tier_labels) == {"Ticket"}:
            exact_label = _string(tier_labels.get("Ticket"), label="ticket label")
            if description["payoutDescription"] != exact_label:
                _fail("source ticket award description/label differ")
            destinations = exact_label.split(",")
            if not pin.is_qualifier or tuple(destinations) != QUALIFIER_TICKET_NAMES:
                _fail("source qualifier ticket destinations differ from the A5 pin")
            award = {
                "kind": "ticket",
                "cash_micro": 0,
                "ticket_value_micro": amount,
                "ticket_destinations": destinations,
                "quantity": quantity,
            }
        else:
            _fail("source payout tier has an unsupported award authority")
        rows.append({"rank_start": start, "rank_end": end, **award})
        last = end
    if not rows:
        _fail("source payout ladder is empty")
    derived_total = sum(
        (int(item["rank_end"]) - int(item["rank_start"]) + 1)
        * int(
            item["cash_micro"]
            if item["kind"] == "cash"
            else item["ticket_value_micro"]
        )
        * int(item["quantity"])
        for item in rows
    )
    if derived_total != pin.advertised_prize_pool_micro:
        _fail(
            f"source payout ladder total for {pin.role} differs from exact A5 "
            f"prize pool: derived={derived_total} "
            f"expected={pin.advertised_prize_pool_micro}"
        )
    return rows


def _parse_contest_source(raw: bytes, *, pin: ContestPin) -> dict[str, object]:
    wrapper = _parse_json(raw, label=f"contest source {pin.contest_id}")
    _exact(
        wrapper,
        {
            "schema_version",
            "captured_at",
            "contest_id",
            "endpoint",
            "outcome_fields_read",
            "source",
        },
        label=f"contest source {pin.contest_id}",
    )
    if wrapper["schema_version"] != "dk-contest-detail-prelock-source/v1":
        _fail("contest source schema differs")
    if wrapper["contest_id"] != pin.contest_id or wrapper["outcome_fields_read"] != []:
        _fail("contest source identity/outcome boundary differs")
    endpoint = _string(wrapper["endpoint"], label="contest endpoint")
    if endpoint != f"https://api.draftkings.com/contests/v1/contests/{pin.contest_id}":
        _fail("contest source endpoint differs")
    captured_at, captured = _timestamp(wrapper["captured_at"], label="contest captured_at")
    lock_text, lock = _timestamp(EXPECTED_LOCK_UTC, label="A5 lock")
    if captured >= lock:
        _fail("contest source was captured after lock")
    source = _mapping(wrapper["source"], label="contest source body")
    _exact(source, {"contestDetail", "errorStatus"}, label="contest source body")
    if source["errorStatus"] != {}:
        _fail("contest source contains a provider error")
    detail = _mapping(source["contestDetail"], label="contestDetail")
    fact_pairs = {
        "contestKey": pin.contest_id,
        "name": pin.name,
        "draftGroupId": int(EXPECTED_DRAFT_GROUP_ID),
        "entryFee": pin.entry_fee_micro // 1_000_000,
        "maximumEntries": pin.advertised_field_capacity,
        "maximumEntriesPerUser": pin.entry_limit,
        "contestState": "Upcoming",
        "contestStateDetail": "Upcoming",
        "isGuaranteed": True,
        "wasResized": False,
        "totalPayouts": pin.advertised_prize_pool_micro // 1_000_000,
    }
    for field, expected in fact_pairs.items():
        if detail.get(field) != expected:
            _fail(f"contest {pin.role} source {field} differs from its exact A5 pin")
    detail_lock, _ = _timestamp(detail.get("contestStartTime"), label="contestStartTime")
    if detail_lock != lock_text:
        _fail(f"contest {pin.role} source lock differs")
    attributes = _mapping(detail.get("attributes"), label="contest attributes")
    qualifier = _boolish(attributes.get("IsQualifier", False))
    if qualifier is not pin.is_qualifier:
        _fail(f"contest {pin.role} qualifier classification differs")
    entries = _integer(detail.get("entries"), label="source entries")
    if entries > pin.advertised_field_capacity:
        _fail("source entries exceed advertised capacity")
    payouts = _source_payouts(detail.get("payoutSummary"), pin=pin)
    if pin.is_qualifier:
        first = payouts[0]
        if (
            first["rank_start"] != 1
            or first["rank_end"] != 1
            or first["kind"] != "ticket"
            or first["quantity"] != 1
            or first["ticket_destinations"] != list(QUALIFIER_TICKET_NAMES)
        ):
            _fail("qualifier first-place ticket terms differ from exact source")
    elif any(item["kind"] == "ticket" for item in payouts):
        _fail("cash contest source unexpectedly contains a ticket tier")
    return {
        "contest_role": pin.role,
        "contest_id": pin.contest_id,
        "contest_name": pin.name,
        "draft_group_id": EXPECTED_DRAFT_GROUP_ID,
        "slate_id": EXPECTED_SLATE_ID,
        "lock_utc": lock_text,
        "entry_fee_micro": pin.entry_fee_micro,
        "advertised_field_capacity": pin.advertised_field_capacity,
        "entry_limit": pin.entry_limit,
        "advertised_prize_pool_micro": pin.advertised_prize_pool_micro,
        "entries_observed_at_freeze": entries,
        "entries_observed_at": captured_at,
        "is_qualifier": pin.is_qualifier,
        "is_guaranteed": True,
        "underfill_authority": "guaranteed-source-ladder",
        "qualifier_ticket_destinations": (
            list(QUALIFIER_TICKET_NAMES) if pin.is_qualifier else []
        ),
        "payout_ladder": payouts,
    }


def load_pinned_contest_sources(
    store: ImmutableObjectStore,
    source_pins: A5SourcePins,
    *,
    not_after: object | None = None,
) -> dict[str, dict[str, object]]:
    """Exact-reopen the terminal source manifest and all four children."""

    _require_exact_source_pins(source_pins)
    _, lock = _timestamp(EXPECTED_LOCK_UTC, label="A5 lock")
    boundary = (
        _timestamp(not_after, label="source not_after")[1]
        if not_after is not None
        else lock
    )
    manifest_obj = _reopen_exact(
        store,
        source_pins.manifest_identity,
        label="terminal contest-source manifest",
        not_after=boundary,
    )
    manifest = _parse_json(manifest_obj.raw, label="terminal contest-source manifest")
    if manifest_obj.created >= lock:
        _fail("terminal contest-source manifest provider time is not pre-lock")
    required = {
        "schema_version",
        "capture_id",
        "complete",
        "season",
        "week",
        "draft_group_id",
        "lock_utc",
        "captured_at",
        "contest_sources",
        "all_sources_create_once_and_exact_reopened",
        "all_sources_upcoming",
        "qualifier_ticket_terms_complete",
        "paid_entries_created",
        "outcome_fields_read",
    }
    _exact(manifest, required, label="terminal contest-source manifest")
    expected_header = {
        "schema_version": "week1-a5-contest-source-manifest/v1",
        "capture_id": "20260904T105535Z",
        "complete": True,
        "season": 2026,
        "week": 1,
        "draft_group_id": int(EXPECTED_DRAFT_GROUP_ID),
        "lock_utc": "2026-09-13T17:00:00+00:00",
        "all_sources_create_once_and_exact_reopened": True,
        "all_sources_upcoming": True,
        "qualifier_ticket_terms_complete": True,
        "paid_entries_created": 0,
        "outcome_fields_read": [],
    }
    for field, expected in expected_header.items():
        if manifest.get(field) != expected:
            _fail(f"terminal contest-source manifest {field} differs")
    _, manifest_captured = _timestamp(
        manifest.get("captured_at"), label="terminal manifest captured_at"
    )
    if manifest_captured >= lock or manifest_captured > boundary:
        _fail("terminal manifest declared capture is outside its pre-lock boundary")
    if manifest_captured > manifest_obj.created:
        _fail("terminal manifest provider creation precedes its declared capture")
    rows = _sequence(manifest.get("contest_sources"), label="contest_sources")
    if len(rows) != len(A5_ROLE_TABLE):
        _fail("terminal manifest must name all four A5 sources")
    source_by_id: dict[str, dict[str, object]] = {}
    for ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"contest_sources[{ordinal}]")
        _exact(
            row,
            {"checks", "contest_id", "identity", "qualifier_ticket_names"},
            label=f"contest_sources[{ordinal}]",
        )
        contest_id = _string(row.get("contest_id"), label="source contest_id")
        if contest_id in source_by_id:
            _fail("terminal manifest repeats a contest source")
        try:
            expected_identity = source_pins.contest_identities[contest_id]
        except KeyError as exc:
            raise Week1A5CaptureContractError("terminal manifest has another contest") from exc
        identity = _identity_equal(
            row.get("identity"), expected_identity, label=f"contest {contest_id} source identity"
        )
        checks = _mapping(row.get("checks"), label="source checks")
        if not checks or set(checks.values()) != {True}:
            _fail("terminal manifest source checks are incomplete")
        pin = next(item for item in _ROLE_ROWS if item.contest_id == contest_id)
        expected_ticket = ",".join(QUALIFIER_TICKET_NAMES) if pin.is_qualifier else None
        if row.get("qualifier_ticket_names") != expected_ticket:
            _fail("terminal manifest qualifier ticket terms differ")
        child = _reopen_exact(
            store,
            identity,
            label=f"contest {contest_id} source",
            not_after=boundary,
        )
        if child.created >= lock:
            _fail("contest source provider time is not strictly pre-lock")
        projection = _parse_contest_source(child.raw, pin=pin)
        child_captured = _timestamp(
            projection["entries_observed_at"], label="contest source captured_at"
        )[1]
        if child_captured > boundary:
            _fail("contest source declared capture is after its evidence boundary")
        if child_captured > child.created:
            _fail("contest source provider creation precedes its declared capture")
        projection["source_identity"] = identity
        projection["source_provider_created_at"] = child.created_at
        source_by_id[contest_id] = projection
    if set(source_by_id) != {pin.contest_id for pin in _ROLE_ROWS}:
        _fail("terminal manifest contest set differs from exact A5")
    for projection in source_by_id.values():
        projection["terminal_source_manifest_identity"] = manifest_obj.identity
        projection["terminal_source_manifest_provider_created_at"] = manifest_obj.created_at
    return {projection["contest_role"]: projection for projection in source_by_id.values()}


def _semantic_ref(value: object, *, label: str) -> dict[str, object]:
    row = _mapping(value, label=label)
    _exact(row, {"artifact_identity", "semantic_sha256"}, label=label)
    return {
        "artifact_identity": _identity(
            row.get("artifact_identity"), label=f"{label}.artifact_identity"
        ),
        "semantic_sha256": _sha(
            row.get("semantic_sha256"), label=f"{label}.semantic_sha256"
        ),
    }


def _ref(identity: object, semantic_sha256: object) -> dict[str, object]:
    return {
        "artifact_identity": _identity(identity, label="artifact identity"),
        "semantic_sha256": _sha(semantic_sha256, label="semantic sha256"),
    }


def _collector_commit(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _COMMIT.fullmatch(text) is None:
        _fail(f"{label} must be one exact lowercase Git commit")
    return text


def _collector_image(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _IMAGE_DIGEST.fullmatch(text) is None:
        _fail(f"{label} must be one immutable sha256 image digest")
    return text


def _authority_event(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _AUTHORITY_EVENT.fullmatch(text) is None:
        _fail(f"{label} must be one canonical acquisition event ID")
    return text


def _expected_acquisition_locator(profile: str, pin: ContestPin) -> str:
    if profile == ACCEPTANCE_ACQUISITION_PROFILE:
        if PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR is None:
            _fail("live acceptance acquisition locator is not pinned")
        return PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR
    if profile == CONTEST_DETAIL_ACQUISITION_PROFILE:
        return f"{FINAL_FIELD_SOURCE_LOCATOR_PREFIX}{pin.contest_id}"
    if profile == STANDINGS_ACQUISITION_PROFILE:
        return f"{FINAL_STANDINGS_SOURCE_LOCATOR_PREFIX}{pin.contest_id}"
    raise AssertionError(f"unsupported acquisition profile {profile!r}")


def _validate_acquisition_receipt_body(
    value: object,
    *,
    expected_profile: str,
    pin: ContestPin,
) -> dict[str, object]:
    """Validate one authority-issued request/download receipt body.

    Source authority is deliberately not inferred here.  The separate
    ``AuthenticatedProviderAcquisitionAuthority`` must first attest the exact
    serialized receipt generation.  This parser then enforces the closed
    request, response, collector, contest, and raw-object contract.
    """

    row = validate_semantic_artifact(value, label="provider acquisition receipt")
    _exact(
        row,
        {
            "schema_version",
            "authority_profile",
            "authority_event_id",
            "acquisition_profile",
            "source_system",
            "authenticated_surface",
            "request_method",
            "canonical_locator",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "observed_at",
            "response_status",
            "response_content_type",
            "response_content_disposition",
            "collector_source_commit",
            "collector_code_sha256",
            "collector_image_digest",
            "transport_trace_identity",
            "raw_object_identity",
            "raw_provider_created_at",
            "semantic_sha256",
        },
        label="provider acquisition receipt",
    )
    if row["schema_version"] != PROVIDER_ACQUISITION_SCHEMA:
        _fail("provider acquisition receipt schema differs")
    if row["authority_profile"] != PROVIDER_ACQUISITION_AUTHORITY_PROFILE:
        _fail("provider acquisition authority profile differs")
    row["authority_event_id"] = _authority_event(
        row["authority_event_id"], label="provider authority event ID"
    )
    if row["acquisition_profile"] != expected_profile:
        _fail("provider acquisition profile differs")
    if row["source_system"] != "draftkings":
        _fail("provider acquisition source system differs")
    if row["authenticated_surface"] != PROVIDER_AUTHENTICATED_SURFACE:
        _fail("provider acquisition did not use the authenticated surface")
    if row["request_method"] != "GET":
        _fail("provider acquisition request method differs")
    expected_locator = _expected_acquisition_locator(expected_profile, pin)
    if row["canonical_locator"] != expected_locator:
        _fail("provider acquisition locator differs from its exact profile")
    if (
        row["contest_role"] != pin.role
        or row["contest_id"] != pin.contest_id
        or row["draft_group_id"] != EXPECTED_DRAFT_GROUP_ID
    ):
        _fail("provider acquisition receipt is cross-wired")
    row["observed_at"] = _timestamp(
        row["observed_at"], label="provider acquisition observed_at"
    )[0]
    row["response_status"] = _integer(
        row["response_status"], label="provider acquisition response status"
    )
    if row["response_status"] != 200:
        _fail("provider acquisition response status is not 200")
    content_type = _string(
        row["response_content_type"], label="provider acquisition content type"
    ).lower()
    media_type = content_type.split(";", 1)[0].strip()
    expected_media = (
        "application/json"
        if expected_profile == CONTEST_DETAIL_ACQUISITION_PROFILE
        else "text/csv"
    )
    if media_type != expected_media:
        _fail("provider acquisition response content type differs")
    disposition = row["response_content_disposition"]
    if expected_profile == CONTEST_DETAIL_ACQUISITION_PROFILE:
        if disposition is not None:
            _fail("contest-detail acquisition unexpectedly claims a download")
    else:
        disposition_text = _string(
            disposition, label="provider acquisition content disposition"
        ).lower()
        if "attachment" not in disposition_text or ".csv" not in disposition_text:
            _fail("provider download lacks an attachment CSV disposition")
    row["collector_source_commit"] = _collector_commit(
        row["collector_source_commit"], label="provider collector source commit"
    )
    row["collector_code_sha256"] = _sha(
        row["collector_code_sha256"], label="provider collector code SHA"
    )
    row["collector_image_digest"] = _collector_image(
        row["collector_image_digest"], label="provider collector image"
    )
    row["transport_trace_identity"] = _identity(
        row["transport_trace_identity"], label="provider transport trace identity"
    )
    row["raw_object_identity"] = _identity(
        row["raw_object_identity"], label="provider raw-object identity"
    )
    row["raw_provider_created_at"] = _timestamp(
        row["raw_provider_created_at"], label="provider raw-object creation time"
    )[0]
    return row


def _reopen_authenticated_acquisition(
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    receipt: object,
    expected_profile: str,
    pin: ContestPin,
    not_after: datetime,
    not_before: datetime | None = None,
) -> ReopenedAcquisition:
    """Reopen and authenticate one governed request/download acquisition.

    The ordinary object store and the acquisition authority are intentionally
    two different dependencies.  Byte-identical objects in the ordinary store
    are not provider observations unless the independent authority recognizes
    that exact receipt generation and authority event.
    """

    reference = _semantic_ref(receipt, label="provider acquisition receipt")
    receipt_value, receipt_obj = _reopen_semantic(
        store,
        reference["artifact_identity"],
        label="provider acquisition receipt",
        expected_semantic_sha256=reference["semantic_sha256"],
        not_after=not_after,
        not_before=not_before,
    )
    try:
        authority_read = _mapping(
            acquisition_authority.read_authenticated_acquisition(
                identity=receipt_obj.identity
            ),
            label="authenticated acquisition authority read",
        )
    except Exception as exc:
        if isinstance(exc, Week1A5CaptureContractError):
            raise
        raise Week1A5CaptureContractError(
            "provider acquisition receipt is not recognized by the authority"
        ) from exc
    _exact(
        authority_read,
        {"identity", "created_at", "raw", "authority_event_id"},
        label="authenticated acquisition authority read",
    )
    _identity_equal(
        authority_read["identity"],
        receipt_obj.identity,
        label="authority-issued acquisition receipt identity",
    )
    authority_created_at, _ = _timestamp(
        authority_read["created_at"], label="authority acquisition created_at"
    )
    if authority_created_at != receipt_obj.created_at:
        _fail("acquisition authority creation time differs from object provider")
    authority_raw = authority_read["raw"]
    if not isinstance(authority_raw, bytes) or authority_raw != receipt_obj.raw:
        _fail("acquisition authority bytes differ from exact receipt generation")
    receipt_value = _validate_acquisition_receipt_body(
        receipt_value,
        expected_profile=expected_profile,
        pin=pin,
    )
    if _authority_event(
        authority_read["authority_event_id"],
        label="authority-recognized acquisition event ID",
    ) != receipt_value["authority_event_id"]:
        _fail("acquisition authority event differs from receipt")
    raw_obj = _reopen_exact(
        store,
        receipt_value["raw_object_identity"],
        label="authority-bound provider raw object",
        not_after=receipt_obj.created,
        not_before=not_before,
    )
    trace_obj = _reopen_exact(
        store,
        receipt_value["transport_trace_identity"],
        label="authority-bound provider transport trace",
        not_after=receipt_obj.created,
        not_before=not_before,
    )
    trace = _parse_json(
        trace_obj.raw,
        label="authority-bound provider transport trace",
        canonical=True,
    )
    _exact(
        trace,
        {
            "schema_version",
            "authority_event_id",
            "request_method",
            "canonical_locator",
            "authenticated_surface",
            "observed_at",
            "response_status",
            "response_content_type",
            "response_content_disposition",
            "collector_source_commit",
            "collector_code_sha256",
            "collector_image_digest",
            "raw_object_identity",
        },
        label="authority-bound provider transport trace",
    )
    if trace.pop("schema_version") != PROVIDER_TRANSPORT_TRACE_SCHEMA:
        _fail("provider transport trace schema differs")
    trace_projection = {
        key: receipt_value[key]
        for key in (
            "authority_event_id",
            "request_method",
            "canonical_locator",
            "authenticated_surface",
            "observed_at",
            "response_status",
            "response_content_type",
            "response_content_disposition",
            "collector_source_commit",
            "collector_code_sha256",
            "collector_image_digest",
            "raw_object_identity",
        )
    }
    if trace != trace_projection:
        _fail("provider acquisition receipt differs from its exact transport trace")
    observed = _timestamp(
        receipt_value["observed_at"], label="provider acquisition observed_at"
    )[1]
    if observed > raw_obj.created or observed > trace_obj.created:
        _fail("provider acquisition archives predate the authenticated observation")
    if receipt_value["raw_provider_created_at"] != raw_obj.created_at:
        _fail("provider acquisition raw creation time differs from exact reopen")
    return ReopenedAcquisition(receipt_value, receipt_obj, raw_obj)


def _load_ref(
    store: ImmutableObjectStore,
    value: object,
    *,
    label: str,
    not_after: datetime | None = None,
    not_before: datetime | None = None,
) -> tuple[dict[str, object], ReopenedObject, dict[str, object]]:
    reference = _semantic_ref(value, label=f"{label} reference")
    artifact, reopened = _reopen_semantic(
        store,
        reference["artifact_identity"],
        label=label,
        expected_semantic_sha256=reference["semantic_sha256"],
        not_after=not_after,
        not_before=not_before,
    )
    return artifact, reopened, reference


def _canonical_player_id(value: object, *, label: str) -> str:
    if type(value) is not str or _PLAYER.fullmatch(value) is None:
        _fail(f"{label} must be a canonical internal player ID")
    return value


def _paid_player_id(value: object, *, label: str) -> int:
    return _integer(value, label=label, minimum=1)


def _draftable_id(value: object, *, label: str) -> int:
    return _integer(value, label=label, minimum=1)


def _entry_id(value: object, *, label: str) -> str:
    if type(value) not in {str, int}:
        _fail(f"{label} must be a positive numeric external ID")
    retained = str(value)
    if not retained.isdigit() or int(retained) < 1:
        _fail(f"{label} must be a positive numeric external ID")
    return retained


def _validate_salary_catalog(value: object) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="paid salary catalog")
    _exact(
        row,
        {
            "schema_version",
            "slate_id",
            "draft_group_id",
            "pulled_at",
            "players",
            "paid_catalog_sha256",
            "semantic_sha256",
        },
        label="paid salary catalog",
    )
    if row["schema_version"] != SALARY_CATALOG_SCHEMA:
        _fail("paid salary catalog schema differs")
    if (
        row["slate_id"] != EXPECTED_SLATE_ID
        or row["draft_group_id"] != EXPECTED_DRAFT_GROUP_ID
    ):
        _fail("paid salary catalog slate/draft group differs")
    _, pulled = _timestamp(row["pulled_at"], label="salary catalog pulled_at")
    pulled_at = pulled.isoformat()
    if row["pulled_at"] != pulled_at:
        _fail("salary catalog pulled_at must use production ISO normalization")
    _, lock = _timestamp(EXPECTED_LOCK_UTC, label="A5 lock")
    if pulled >= lock:
        _fail("paid salary catalog was pulled after lock")
    players: list[dict[str, object]] = []
    player_ids: set[int] = set()
    draftable_ids: set[int] = set()
    display_names: set[str] = set()
    for ordinal, raw in enumerate(_sequence(row["players"], label="salary players")):
        player = _mapping(raw, label=f"salary players[{ordinal}]")
        _exact(
            player,
            {"player_id", "draftable_id", "name", "team", "pos", "salary", "status"},
            label=f"salary players[{ordinal}]",
        )
        player_id = _paid_player_id(player["player_id"], label="salary DK player ID")
        draftable_id = _draftable_id(
            player["draftable_id"], label="salary DK draftable ID"
        )
        name = _string(player["name"], label="salary display name")
        team = _string(player["team"], label="salary team")
        position = _string(player["pos"], label="salary position")
        if position not in {"QB", "RB", "WR", "TE", "DST"}:
            _fail("salary catalog contains an unsupported position")
        salary = _integer(player["salary"], label="salary", minimum=1)
        if salary > SALARY_CAP:
            _fail("salary catalog contains an impossible salary")
        status = player["status"]
        if type(status) is not str or status != status.strip().upper():
            _fail("salary catalog status is not normalized")
        if status in {"O", "OUT", "IR"}:
            _fail("salary catalog contains an inactive player")
        if (
            player_id in player_ids
            or draftable_id in draftable_ids
            or name in display_names
        ):
            _fail("salary catalog player identity is not one-to-one")
        player_ids.add(player_id)
        draftable_ids.add(draftable_id)
        display_names.add(name)
        players.append(
            {
                "player_id": player_id,
                "draftable_id": draftable_id,
                "name": name,
                "team": team,
                "pos": position,
                "salary": salary,
                "status": status,
            }
        )
    if not players or [item["player_id"] for item in players] != sorted(player_ids):
        _fail("salary catalog players must be nonempty and DK-player ordered")
    paid_hash = canonical_sha256(
        {
            "draft_group_id": int(EXPECTED_DRAFT_GROUP_ID),
            "pulled_at": pulled_at,
            "players": players,
        }
    )
    if row["paid_catalog_sha256"] != paid_hash:
        _fail("paid salary catalog hash differs from production normalization")
    retained = dict(row)
    retained["pulled_at"] = pulled_at
    retained["players"] = players
    retained["paid_catalog_sha256"] = paid_hash
    return retained


def _validate_player_bridge(
    value: object,
    *,
    catalog: Mapping[str, object],
    expected_catalog_ref: Mapping[str, object],
) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="player bridge")
    _exact(
        row,
        {
            "schema_version",
            "slate_id",
            "draft_group_id",
            "salary_cap",
            "salary_catalog",
            "paid_catalog_sha256",
            "players",
            "semantic_sha256",
        },
        label="player bridge",
    )
    if row["schema_version"] != PLAYER_BRIDGE_SCHEMA:
        _fail("player bridge schema differs")
    if (
        row["slate_id"] != EXPECTED_SLATE_ID
        or row["draft_group_id"] != EXPECTED_DRAFT_GROUP_ID
    ):
        _fail("player bridge slate/draft group differs")
    if row["salary_cap"] != SALARY_CAP:
        _fail("player bridge salary cap differs")
    catalog_ref = _semantic_ref(row["salary_catalog"], label="bridge salary catalog")
    if (
        catalog_ref
        != _semantic_ref(expected_catalog_ref, label="exact salary catalog")
        or catalog_ref["semantic_sha256"] != catalog["semantic_sha256"]
        or row["paid_catalog_sha256"] != catalog["paid_catalog_sha256"]
    ):
        _fail("player bridge names another exact paid salary catalog")
    catalog_by_player = {item["player_id"]: item for item in catalog["players"]}
    players: list[dict[str, object]] = []
    internal_seen: set[str] = set()
    paid_seen: set[int] = set()
    for ordinal, raw in enumerate(_sequence(row["players"], label="player bridge players")):
        player = _mapping(raw, label=f"player bridge players[{ordinal}]")
        _exact(
            player,
            {
                "internal_player_id",
                "dk_player_id",
                "dk_draftable_id",
                "display_name",
                "team",
                "position",
                "salary",
                "status",
            },
            label=f"player bridge players[{ordinal}]",
        )
        internal_id = _canonical_player_id(
            player["internal_player_id"], label="internal player ID"
        )
        paid_player_id = _paid_player_id(
            player["dk_player_id"], label="DK player ID"
        )
        try:
            catalog_player = catalog_by_player[paid_player_id]
        except KeyError as exc:
            raise Week1A5CaptureContractError(
                "player bridge DK player is absent from exact salary catalog"
            ) from exc
        expected = {
            "dk_draftable_id": catalog_player["draftable_id"],
            "display_name": catalog_player["name"],
            "team": catalog_player["team"],
            "position": catalog_player["pos"],
            "salary": catalog_player["salary"],
            "status": catalog_player["status"],
        }
        if any(player[key] != expected_value for key, expected_value in expected.items()):
            _fail("player bridge row differs from exact salary catalog")
        if internal_id in internal_seen or paid_player_id in paid_seen:
            _fail("player bridge is not one-to-one")
        internal_seen.add(internal_id)
        paid_seen.add(paid_player_id)
        players.append(
            {
                "internal_player_id": internal_id,
                "dk_player_id": paid_player_id,
                **expected,
            }
        )
    if set(paid_seen) != set(catalog_by_player):
        _fail("player bridge does not completely cover the exact salary catalog")
    if [item["internal_player_id"] for item in players] != sorted(internal_seen):
        _fail("player bridge rows must be internal-ID ordered")
    retained = dict(row)
    retained["salary_catalog"] = catalog_ref
    retained["players"] = players
    return retained


def _slot_eligible(slot: str, positions: Sequence[str]) -> bool:
    if slot == "FLEX":
        return bool(set(positions) & {"RB", "WR", "TE"})
    return slot in positions


def _validate_book(value: object, *, bridge: Mapping[str, object]) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="book materialization")
    _exact(
        row,
        {
            "schema_version",
            "policy",
            "purpose",
            "slate_id",
            "draft_group_id",
            "player_bridge",
            "entries",
            "semantic_sha256",
        },
        label="book materialization",
    )
    if row["schema_version"] != BOOK_SCHEMA:
        _fail("book materialization schema differs")
    policy = _string(row["policy"], label="book policy")
    if policy not in EXPECTED_POLICIES:
        _fail("book policy is not in the A5 decision")
    purpose = "paid" if policy == "P_MIX" else "shadow"
    if row["purpose"] != purpose:
        _fail("book purpose differs from its policy")
    if row["slate_id"] != EXPECTED_SLATE_ID or row["draft_group_id"] != EXPECTED_DRAFT_GROUP_ID:
        _fail("book slate/draft group differs")
    bridge_ref = _semantic_ref(row["player_bridge"], label="book player bridge")
    if bridge_ref["semantic_sha256"] != bridge["semantic_sha256"]:
        _fail("book names another player bridge semantic root")
    by_internal = {item["internal_player_id"]: item for item in bridge["players"]}
    by_draftable = {item["dk_draftable_id"]: item for item in bridge["players"]}
    entries: list[dict[str, object]] = []
    lineup_seen: set[str] = set()
    for ordinal, raw in enumerate(_sequence(row["entries"], label="book entries")):
        entry = _mapping(raw, label=f"book entries[{ordinal}]")
        _exact(
            entry,
            {
                "lineup_rank",
                "lineup_id",
                "roster_sha256",
                "internal_player_ids",
                "slot_dk_draftable_ids",
                "salary",
            },
            label=f"book entries[{ordinal}]",
        )
        rank = _integer(entry["lineup_rank"], label="lineup rank", minimum=1)
        if rank != ordinal + 1:
            _fail("book ranks must be complete, unique, and ordered from one")
        internal_ids = [
            _canonical_player_id(item, label="book internal player ID")
            for item in _sequence(entry["internal_player_ids"], label="book internal IDs")
        ]
        draftable_ids = [
            _draftable_id(item, label="book DK draftable ID")
            for item in _sequence(
                entry["slot_dk_draftable_ids"], label="book slot draftable IDs"
            )
        ]
        if len(internal_ids) != 9 or len(set(internal_ids)) != 9:
            _fail("book roster must contain nine unique internal players")
        if len(draftable_ids) != 9 or len(set(draftable_ids)) != 9:
            _fail("book roster must contain nine unique DK draftables")
        if set(internal_ids) - set(by_internal) or set(draftable_ids) - set(by_draftable):
            _fail("book roster contains a player absent from its exact bridge")
        mapped_internal = [by_draftable[item]["internal_player_id"] for item in draftable_ids]
        if set(mapped_internal) != set(internal_ids):
            _fail("book internal/DK roster mapping differs from its exact bridge")
        for slot, draftable_id in zip(CLASSIC_SLOTS, draftable_ids, strict=True):
            if not _slot_eligible(
                slot, (str(by_draftable[draftable_id]["position"]),)
            ):
                _fail("book roster violates a classic slot position")
        salary = sum(int(by_draftable[item]["salary"]) for item in draftable_ids)
        if salary > SALARY_CAP or entry["salary"] != salary:
            _fail("book salary differs from bridge replay or exceeds the cap")
        team_counts = Counter(str(by_draftable[item]["team"]) for item in draftable_ids)
        if len(team_counts) < 2 or max(team_counts.values()) > MAX_FROM_TEAM:
            _fail("book roster violates the exact NFL Classic team constraint")
        roster_hash = canonical_sha256(sorted(internal_ids))
        if entry["roster_sha256"] != roster_hash:
            _fail("book roster_sha256 differs from canonical internal membership")
        lineup_id = _string(entry["lineup_id"], label="lineup ID")
        match = _LINEUP.fullmatch(lineup_id)
        if match is None or match.group(1) != roster_hash:
            _fail("lineup_id does not bind canonical internal roster membership")
        if lineup_id in lineup_seen:
            _fail("book repeats a lineup identity")
        lineup_seen.add(lineup_id)
        entries.append(
            {
                "lineup_rank": rank,
                "lineup_id": lineup_id,
                "roster_sha256": roster_hash,
                "internal_player_ids": internal_ids,
                "slot_dk_draftable_ids": draftable_ids,
                "salary": salary,
            }
        )
    if len(entries) != EXPECTED_BOOK_SIZE:
        _fail("book must contain the exact frozen K80 order")
    retained = dict(row)
    retained["player_bridge"] = bridge_ref
    retained["entries"] = entries
    return retained


def _load_player_bridge(
    store: ImmutableObjectStore,
    *,
    bridge_ref: object,
    not_after: datetime,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    bridge_raw, _, retained_bridge_ref = _load_ref(
        store, bridge_ref, label="A5 player bridge", not_after=not_after
    )
    bridge_candidate = validate_semantic_artifact(
        bridge_raw, label="A5 player bridge"
    )
    salary_ref = _semantic_ref(
        bridge_candidate.get("salary_catalog"), label="bridge salary catalog"
    )
    catalog_raw, catalog_obj, retained_catalog_ref = _load_ref(
        store, salary_ref, label="A5 paid salary catalog", not_after=not_after
    )
    catalog = _validate_salary_catalog(catalog_raw)
    if _timestamp(catalog["pulled_at"], label="salary catalog pulled_at")[1] > catalog_obj.created:
        _fail("salary catalog provider creation precedes its declared pull")
    bridge = _validate_player_bridge(
        bridge_raw,
        catalog=catalog,
        expected_catalog_ref=retained_catalog_ref,
    )
    return bridge, retained_bridge_ref, catalog


def _load_bridge_and_books(
    store: ImmutableObjectStore,
    *,
    bridge_ref: object,
    book_refs: object,
    not_after: datetime,
) -> tuple[
    dict[str, object],
    dict[str, dict[str, object]],
    dict[str, object],
    dict[str, dict[str, object]],
]:
    bridge, retained_bridge_ref, _ = _load_player_bridge(
        store, bridge_ref=bridge_ref, not_after=not_after
    )
    raw_refs = _mapping(book_refs, label="A5 book references")
    if set(raw_refs) != set(EXPECTED_POLICIES):
        _fail("allocation must reference all exact paid/shadow policies")
    books: dict[str, dict[str, object]] = {}
    retained_refs: dict[str, dict[str, object]] = {}
    for policy in EXPECTED_POLICIES:
        raw_book, _, book_ref = _load_ref(
            store, raw_refs[policy], label=f"{policy} book", not_after=not_after
        )
        book = _validate_book(raw_book, bridge=bridge)
        if book["policy"] != policy:
            _fail("book reference is cross-wired to another policy")
        if book["player_bridge"] != retained_bridge_ref:
            _fail("book reference names another exact player bridge")
        books[policy] = book
        retained_refs[policy] = book_ref
    return bridge, books, retained_bridge_ref, retained_refs


def _parse_template_projection(
    raw: bytes,
    *,
    expected_semantic_sha256: str,
) -> dict[str, str]:
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Week1A5CaptureContractError("template projection is not JSON") from exc
    if canonical_sha256(parsed) != _sha(
        expected_semantic_sha256, label="template projection semantic hash"
    ):
        _fail("template projection differs from its source-qualified semantic hash")
    rows = _sequence(parsed, label="template projection")
    templates: dict[str, str] = {}
    for ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"template projection[{ordinal}]")
        contest_id = str(row.get("contest_id", ""))
        if contest_id not in {pin.contest_id for pin in _ROLE_ROWS}:
            continue
        template_id = str(row.get("contest_template_id", ""))
        pin = next(item for item in _ROLE_ROWS if item.contest_id == contest_id)
        if template_id != pin.template_id:
            _fail("template projection contest/template pairing differs")
        if contest_id in templates:
            _fail("template projection repeats an A5 contest")
        templates[contest_id] = template_id
    if templates != {pin.contest_id: pin.template_id for pin in _ROLE_ROWS}:
        _fail("template projection does not contain all exact A5 contests")
    return templates


def _load_template_projection(
    store: ImmutableObjectStore,
    source_pins: A5SourcePins,
    *,
    not_after: datetime,
) -> tuple[dict[str, str], dict[str, object]]:
    _require_exact_source_pins(source_pins)
    if source_pins.template_projection_identity is None:
        _fail(
            "generation-pinned lobby/template projection identity is unavailable; "
            "live allocation publication remains HOLD"
        )
    reopened = _reopen_exact(
        store,
        source_pins.template_projection_identity,
        label="A5 template projection",
        not_after=not_after,
    )
    templates = _parse_template_projection(
        reopened.raw,
        expected_semantic_sha256=source_pins.template_projection_semantic_sha256,
    )
    return templates, reopened.identity


def _expected_edges(
    books: Mapping[str, Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    paid: list[dict[str, object]] = []
    shadows: list[dict[str, object]] = []
    for pin in _ROLE_ROWS:
        for rank in range(1, pin.planned_entries + 1):
            paid_book = books["P_MIX"]["entries"][rank - 1]
            paid.append(
                {
                    "contest_role": pin.role,
                    "contest_id": pin.contest_id,
                    "entry_index": rank,
                    "lineup_rank": rank,
                    "lineup_id": paid_book["lineup_id"],
                    "roster_sha256": paid_book["roster_sha256"],
                }
            )
            for policy in SHADOW_POLICIES:
                shadow_book = books[policy]["entries"][rank - 1]
                shadows.append(
                    {
                        "policy": policy,
                        "contest_role": pin.role,
                        "contest_id": pin.contest_id,
                        "entry_index": rank,
                        "lineup_rank": rank,
                        "lineup_id": shadow_book["lineup_id"],
                        "roster_sha256": shadow_book["roster_sha256"],
                    }
                )
    return paid, shadows


def build_week1_allocation_authority_v2(
    *,
    store: ImmutableObjectStore,
    source_pins: A5SourcePins,
    player_bridge: object,
    books: object,
    frozen_at: object,
) -> dict[str, object]:
    """Build an allocation only from exact source, bridge, and book bytes."""

    frozen_text, frozen = _publish_by(
        frozen_at,
        label="allocation frozen_at",
        phase="prelock",
    )
    source = load_pinned_contest_sources(store, source_pins, not_after=frozen_text)
    templates, template_identity = _load_template_projection(
        store, source_pins, not_after=frozen
    )
    bridge, loaded_books, bridge_ref, book_refs = _load_bridge_and_books(
        store,
        bridge_ref=player_bridge,
        book_refs=books,
        not_after=frozen,
    )
    del bridge
    paid_edges, shadow_edges = _expected_edges(loaded_books)
    contests = []
    for pin in _ROLE_ROWS:
        fact = source[pin.role]
        if templates[pin.contest_id] != pin.template_id:
            _fail("source-qualified template projection differs")
        contests.append(
            {
                key: fact[key]
                for key in (
                    "contest_role",
                    "contest_id",
                    "contest_name",
                    "draft_group_id",
                    "slate_id",
                    "lock_utc",
                    "entry_fee_micro",
                    "advertised_field_capacity",
                    "entry_limit",
                    "advertised_prize_pool_micro",
                    "is_qualifier",
                    "is_guaranteed",
                    "underfill_authority",
                    "qualifier_ticket_destinations",
                )
            }
            | {
                "template_id": templates[pin.contest_id],
                "template_authority": TEMPLATE_AUTHORITY,
                "template_projection_semantic_sha256": _sha(
                    source_pins.template_projection_semantic_sha256,
                    label="template projection semantic hash",
                ),
                "planned_entries": pin.planned_entries,
                "contest_source_identity": fact["source_identity"],
            }
        )
    return seal_semantic_artifact(
        {
            "schema_version": ALLOCATION_SCHEMA,
            "allocation_id": EXPECTED_ALLOCATION_ID,
            "complete": True,
            "season": 2026,
            "week": 1,
            "draft_group_id": EXPECTED_DRAFT_GROUP_ID,
            "slate_id": EXPECTED_SLATE_ID,
            "lock_utc": EXPECTED_LOCK_UTC,
            "frozen_at": frozen_text,
            "source_manifest_identity": _identity(
                source_pins.manifest_identity, label="source manifest identity"
            ),
            "template_projection": {
                "artifact_identity": template_identity,
                "semantic_sha256": _sha(
                    source_pins.template_projection_semantic_sha256,
                    label="template projection semantic hash",
                ),
                "authority": TEMPLATE_AUTHORITY,
            },
            "player_bridge": bridge_ref,
            "books": book_refs,
            "paid_policy": "P_MIX",
            "shadow_policies": list(SHADOW_POLICIES),
            "contests": contests,
            "paid_entry_edges": paid_edges,
            "shadow_entry_edges": shadow_edges,
            "planned_entry_count": EXPECTED_PLANNED_ENTRIES,
            "planned_spend_micro": EXPECTED_PLANNED_SPEND_MICRO,
            "accepted_entry_receipts_pending": True,
            "outcome_fields_read": [],
        }
    )


def validate_week1_allocation_authority_v2(
    value: object,
    *,
    store: ImmutableObjectStore,
    source_pins: A5SourcePins,
) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="A5 allocation")
    rebuilt = build_week1_allocation_authority_v2(
        store=store,
        source_pins=source_pins,
        player_bridge=row.get("player_bridge"),
        books=row.get("books"),
        frozen_at=row.get("frozen_at"),
    )
    if row != rebuilt:
        _fail("A5 allocation differs from exact source/book-derived authority")
    return row


def _load_allocation(
    store: ImmutableObjectStore,
    pins: A5CapturePins,
    *,
    not_after: datetime,
) -> tuple[dict[str, object], ReopenedObject]:
    allocation, reopened = _reopen_semantic(
        store,
        pins.allocation_identity,
        label="pinned A5 allocation",
        expected_semantic_sha256=pins.allocation_semantic_sha256,
        not_after=not_after,
    )
    validated = validate_week1_allocation_authority_v2(
        allocation, store=store, source_pins=pins.source
    )
    declared_freeze = _timestamp(
        validated["frozen_at"], label="allocation frozen_at"
    )[1]
    if declared_freeze > not_after:
        _fail("allocation declared freeze is after its consumer boundary")
    if reopened.created > declared_freeze:
        _fail("allocation provider creation time is after its declared freeze")
    return validated, reopened


def build_week1_prelock_manifest_v3(
    *,
    store: ImmutableObjectStore,
    pins: A5CapturePins,
    contest_role: str,
    manifest_frozen_at: object,
) -> dict[str, object]:
    """Build one contest manifest entirely from exact reopened authorities."""

    if contest_role not in A5_ROLE_TABLE:
        _fail("manifest contest role is not in exact A5")
    frozen_text, frozen = _publish_by(
        manifest_frozen_at,
        label="manifest frozen_at",
        phase="prelock",
    )
    allocation, _ = _load_allocation(store, pins, not_after=frozen)
    sources = load_pinned_contest_sources(store, pins.source, not_after=frozen_text)
    contest = sources[contest_role]
    allocation_contest = next(
        item for item in allocation["contests"] if item["contest_role"] == contest_role
    )
    source_fields = {
        key: contest[key]
        for key in (
            "contest_role",
            "contest_id",
            "contest_name",
            "draft_group_id",
            "slate_id",
            "lock_utc",
            "entry_fee_micro",
            "advertised_field_capacity",
            "entry_limit",
            "advertised_prize_pool_micro",
            "is_qualifier",
            "is_guaranteed",
            "underfill_authority",
            "qualifier_ticket_destinations",
        )
    }
    for key, expected in source_fields.items():
        if allocation_contest[key] != expected:
            _fail("allocation contest facts differ from exact reopened source")
    contest_projection = source_fields | {
        "template_id": allocation_contest["template_id"],
        "template_authority": allocation_contest["template_authority"],
        "template_projection_semantic_sha256": allocation_contest[
            "template_projection_semantic_sha256"
        ],
        "entries_observed_at_freeze": contest["entries_observed_at_freeze"],
        "entries_observed_at": contest["entries_observed_at"],
        "planned_entries": allocation_contest["planned_entries"],
    }
    return seal_semantic_artifact(
        {
            "schema_version": PRELOCK_SCHEMA,
            "manifest_frozen_at": frozen_text,
            "contest": contest_projection,
            "payout_ladder": contest["payout_ladder"],
            "source_manifest_identity": contest["terminal_source_manifest_identity"],
            "contest_source_identity": contest["source_identity"],
            "allocation": _ref(
                pins.allocation_identity, pins.allocation_semantic_sha256
            ),
            "player_bridge": allocation["player_bridge"],
            "books": allocation["books"],
            "correction_lineage": {
                "revision": 0,
                "predecessor": None,
                "reason": "initial",
            },
            "outcome_fields_read": [],
        }
    )


def validate_week1_prelock_manifest_v3(
    value: object,
    *,
    store: ImmutableObjectStore,
    pins: A5CapturePins,
) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="prelock manifest")
    _exact(
        row,
        {
            "schema_version",
            "manifest_frozen_at",
            "contest",
            "payout_ladder",
            "source_manifest_identity",
            "contest_source_identity",
            "allocation",
            "player_bridge",
            "books",
            "correction_lineage",
            "outcome_fields_read",
            "semantic_sha256",
        },
        label="prelock manifest",
    )
    contest = _mapping(row["contest"], label="manifest contest")
    role = _string(contest.get("contest_role"), label="manifest contest role")
    rebuilt = build_week1_prelock_manifest_v3(
        store=store,
        pins=pins,
        contest_role=role,
        manifest_frozen_at=row["manifest_frozen_at"],
    )
    if row != rebuilt:
        _fail("prelock manifest differs from exact reopened evidence")
    return row


def _load_manifest(
    store: ImmutableObjectStore,
    pins: A5CapturePins,
    identity: object,
    *,
    expected_semantic_sha256: object,
    not_after: datetime,
) -> tuple[dict[str, object], ReopenedObject]:
    manifest, reopened = _reopen_semantic(
        store,
        identity,
        label="prelock manifest",
        expected_semantic_sha256=expected_semantic_sha256,
        not_after=not_after,
    )
    validated = validate_week1_prelock_manifest_v3(
        manifest, store=store, pins=pins
    )
    declared_freeze = _timestamp(
        validated["manifest_frozen_at"], label="manifest frozen_at"
    )[1]
    if declared_freeze > not_after:
        _fail("manifest declared freeze is after its consumer boundary")
    if reopened.created > declared_freeze:
        _fail("manifest provider creation time is after its declared freeze")
    return validated, reopened


def _parse_prepared_capture(
    raw: bytes,
    *,
    contest: Mapping[str, object],
    paid_book: Mapping[str, object],
    bridge: Mapping[str, object],
) -> dict[str, object]:
    value = _parse_json(raw, label="prepared paid-entry capture", canonical=True)
    _exact(
        value,
        {
            "schema_version",
            "contest_id",
            "draft_group_id",
            "salary_catalog_sha256",
            "csv_sha256",
            "csv_bytes",
            "paid_export_receipt_sha256",
            "entries",
            "uses_realized_outcomes",
            "post_lock_data_read",
        },
        label="prepared paid-entry capture",
    )
    if value["schema_version"] != "paid-entry-capture/v1":
        _fail("prepared capture schema differs")
    if (
        value["contest_id"] != contest["contest_id"]
        or value["draft_group_id"] != EXPECTED_DRAFT_GROUP_ID
    ):
        _fail("prepared capture is cross-wired to another contest/draft group")
    if value["uses_realized_outcomes"] is not False or value["post_lock_data_read"] is not False:
        _fail("prepared capture crossed the pre-lock outcome boundary")
    salary_catalog_sha = _sha(
        value["salary_catalog_sha256"], label="salary catalog SHA"
    )
    if salary_catalog_sha != bridge["paid_catalog_sha256"]:
        _fail("prepared capture names another exact paid salary catalog")
    _sha(value["csv_sha256"], label="filled CSV SHA")
    _integer(value["csv_bytes"], label="filled CSV bytes", minimum=1)
    _sha(value["paid_export_receipt_sha256"], label="paid export receipt SHA")
    k = int(contest["planned_entries"])
    entries = _sequence(value["entries"], label="prepared entries")
    if len(entries) != k:
        _fail("prepared capture entry count differs from exact A5 K")
    retained: list[dict[str, object]] = []
    export_ordinals: set[int] = set()
    book_ordinals: set[int] = set()
    entry_ids: set[str] = set()
    bridge_by_draftable = {
        item["dk_draftable_id"]: item for item in bridge["players"]
    }
    for ordinal, raw_entry in enumerate(entries):
        entry = _mapping(raw_entry, label=f"prepared entries[{ordinal}]")
        _exact(
            entry,
            {
                "export_ordinal",
                "entry_id",
                "internal_player_ids",
                "dk_draftable_ids",
                "paid_input_book_ordinal",
                "slot_dk_draftable_ids",
            },
            label=f"prepared entries[{ordinal}]",
        )
        export_ordinal = _integer(entry["export_ordinal"], label="export ordinal")
        book_ordinal = _integer(
            entry["paid_input_book_ordinal"], label="paid input book ordinal"
        )
        if export_ordinal >= k or book_ordinal >= k:
            _fail("prepared ordinal falls outside exact A5 K")
        entry_id = _entry_id(entry["entry_id"], label="prepared Entry ID")
        internal_ids = [
            _paid_player_id(item, label="prepared DK player ID")
            for item in _sequence(entry["internal_player_ids"], label="prepared internal IDs")
        ]
        draftable_ids = [
            _draftable_id(item, label="prepared DK draftable ID")
            for item in _sequence(entry["dk_draftable_ids"], label="prepared draftable IDs")
        ]
        slot_ids = [
            _draftable_id(item, label="prepared slot draftable ID")
            for item in _sequence(
                entry["slot_dk_draftable_ids"], label="prepared slot draftable IDs"
            )
        ]
        expected_book = paid_book["entries"][book_ordinal]
        expected_paid_ids = sorted(
            int(bridge_by_draftable[item]["dk_player_id"])
            for item in expected_book["slot_dk_draftable_ids"]
        )
        if internal_ids != expected_paid_ids:
            _fail("prepared DK-player roster differs from exact paid book/bridge")
        if draftable_ids != sorted(expected_book["slot_dk_draftable_ids"]):
            _fail("prepared unordered DK roster differs from exact paid book")
        if slot_ids != expected_book["slot_dk_draftable_ids"]:
            _fail("prepared slot roster differs from exact paid book")
        export_ordinals.add(export_ordinal)
        book_ordinals.add(book_ordinal)
        if entry_id in entry_ids:
            _fail("prepared capture repeats an Entry ID")
        entry_ids.add(entry_id)
        retained.append(
            {
                "export_ordinal": export_ordinal,
                "entry_id": entry_id,
                "internal_player_ids": internal_ids,
                "dk_draftable_ids": draftable_ids,
                "paid_input_book_ordinal": book_ordinal,
                "slot_dk_draftable_ids": slot_ids,
            }
        )
    if export_ordinals != set(range(k)):
        _fail("prepared export ordinals are missing or duplicated")
    if book_ordinals != set(range(k)):
        _fail("prepared lineup ranks are missing or duplicated")
    retained.sort(key=lambda item: int(item["export_ordinal"]))
    value["entries"] = retained
    return value


def _parse_filled_upload(
    raw: bytes,
    *,
    contest_id: str,
    contest_name: str,
    entry_fee_micro: int,
    expected_entries: int,
) -> list[dict[str, object]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Week1A5CaptureContractError("filled upload is not UTF-8 CSV") from exc
    rows = list(csv.reader(io.StringIO(text)))
    metadata_header = ["Entry ID", "Contest Name", "Contest ID", "Entry Fee"]
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if [cell.strip().lstrip("\ufeff") for cell in row[:4]]
            == metadata_header
        ),
        None,
    )
    if header_index is None:
        _fail("filled upload is not a DKEntries CSV")
    header = [cell.strip() for cell in rows[header_index]]
    if tuple(header[4:13]) != CLASSIC_SLOTS:
        _fail("filled upload lacks the exact NFL Classic slot header")
    candidates: list[list[str]] = []
    for row in rows[header_index + 1 :]:
        normalized_row = (row + [""] * 13)[: max(13, len(row))]
        metadata = normalized_row[:4]
        if not any(cell.strip() for cell in metadata):
            continue
        if not metadata[2].strip():
            _fail("filled upload entry row has no contest ID")
        candidates.append(normalized_row)
    selected = [row for row in candidates if row[2].strip() == contest_id]
    if len(selected) != expected_entries:
        _fail("filled upload targeted row count differs from exact A5 K")
    projection: list[dict[str, object]] = []
    entry_ids: set[str] = set()
    for ordinal, row in enumerate(selected):
        if row[1].strip() != contest_name:
            _fail("filled upload contest name differs from exact A5")
        fee_text = row[3].strip().replace("$", "").replace(",", "")
        if _money_micro(fee_text, label="filled upload entry fee") != entry_fee_micro:
            _fail("filled upload entry fee differs from exact A5")
        cells = (row[4:13] + [""] * 9)[:9]
        slot_ids: list[int] = []
        for cell in cells:
            match = _FILLED_CELL.fullmatch(cell.strip())
            if match is None:
                _fail("filled upload contains a malformed or empty roster slot")
            slot_ids.append(int(match.group(1)))
        if len(set(slot_ids)) != 9:
            _fail("filled upload roster repeats a DK draftable ID")
        entry_id = _entry_id(row[0].strip(), label="filled upload Entry ID")
        if entry_id in entry_ids:
            _fail("filled upload repeats a targeted Entry ID")
        entry_ids.add(entry_id)
        projection.append(
            {
                "export_ordinal": ordinal,
                "entry_id": entry_id,
                "slot_dk_draftable_ids": slot_ids,
            }
        )
    targeted_ids = set(entry_ids)
    if any(
        row[2].strip() != contest_id and row[0].strip() in targeted_ids
        for row in candidates
    ):
        _fail("filled upload reuses a targeted Entry ID in another contest")
    return projection


def _pin_for_role(value: object) -> ContestPin:
    role = _string(value, label="A5 contest role")
    try:
        return A5_ROLE_TABLE[role]
    except KeyError as exc:
        raise Week1A5CaptureContractError(
            "contest role is outside the exact A5 allocation"
        ) from exc


def _parse_active_entry_export(
    raw: bytes,
    *,
    pin: ContestPin,
) -> list[dict[str, object]]:
    """Derive accepted rows from one raw DK active-entry export.

    The provider export itself is the observation.  No status, row, roster,
    or completeness value supplied by a caller enters this projection.
    Draft-group identity comes from the exact contest manifest because the DK
    edit-entries CSV does not expose it.
    """

    rows = _parse_filled_upload(
        raw,
        contest_id=pin.contest_id,
        contest_name=pin.name,
        entry_fee_micro=pin.entry_fee_micro,
        expected_entries=pin.planned_entries,
    )
    entries = [
        {
            "entry_id": item["entry_id"],
            "status": "accepted",
            "slot_dk_draftable_ids": item["slot_dk_draftable_ids"],
        }
        for item in rows
    ]
    entries.sort(key=lambda item: str(item["entry_id"]))
    return entries


def inspect_acceptance_provider_bytes_v1(
    raw: bytes,
    *,
    contest_role: object,
) -> dict[str, object]:
    """Return a redacted, write-free real-shape smoke projection."""

    pin = _pin_for_role(contest_role)
    entries = _parse_active_entry_export(raw, pin=pin)
    return {
        "schema_version": "week1-a5-acceptance-shape-smoke/v1",
        "source_profile": ACCEPTANCE_CAPTURE_METHOD,
        "contest_role": pin.role,
        "contest_id": pin.contest_id,
        "entry_count": len(entries),
        "unique_entry_count": len({item["entry_id"] for item in entries}),
        "all_rosters_have_nine_unique_draftables": all(
            len(item["slot_dk_draftable_ids"]) == 9
            and len(set(item["slot_dk_draftable_ids"])) == 9
            for item in entries
        ),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw),
        "entry_projection_sha256": canonical_sha256(entries),
        "writes_performed": False,
    }


def build_acceptance_provider_capture_v2(
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    contest_role: object,
    acquisition_receipt: object,
    publish_by: object,
) -> dict[str, object]:
    """Bind one authority-issued DK active-entry acquisition."""

    pin = _pin_for_role(contest_role)
    publish_text, cutoff = _publish_by(
        publish_by,
        label="acceptance provider capture publish_by",
        phase="prelock",
    )
    acquisition = _reopen_authenticated_acquisition(
        store=store,
        acquisition_authority=acquisition_authority,
        receipt=acquisition_receipt,
        expected_profile=ACCEPTANCE_ACQUISITION_PROFILE,
        pin=pin,
        not_after=cutoff,
    )
    observed_text, observed = _timestamp(
        acquisition.receipt["observed_at"],
        label="acceptance provider observed_at",
    )
    if observed > cutoff:
        _fail("acceptance provider observation is after its publish-by cutoff")
    entries = _parse_active_entry_export(acquisition.raw_object.raw, pin=pin)
    acquisition_ref = _semantic_ref(
        acquisition_receipt, label="acceptance provider acquisition receipt"
    )
    return seal_semantic_artifact(
        {
            "schema_version": ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA,
            "source_system": "draftkings",
            "capture_method": ACCEPTANCE_CAPTURE_METHOD,
            "source_locator": acquisition.receipt["canonical_locator"],
            "contest_role": pin.role,
            "contest_id": pin.contest_id,
            "draft_group_id": EXPECTED_DRAFT_GROUP_ID,
            "observed_at": observed_text,
            "publish_by": publish_text,
            "acquisition_receipt": acquisition_ref,
            "acquisition_authority_event_id": acquisition.receipt[
                "authority_event_id"
            ],
            "raw_observation_identity": acquisition.raw_object.identity,
            "observed_entry_count": len(entries),
            "entry_projection_sha256": canonical_sha256(entries),
        }
    )


def validate_acceptance_provider_capture_v2(
    value: object,
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="acceptance provider capture")
    _exact(
        row,
        {
            "schema_version",
            "source_system",
            "capture_method",
            "source_locator",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "observed_at",
            "publish_by",
            "acquisition_receipt",
            "acquisition_authority_event_id",
            "raw_observation_identity",
            "observed_entry_count",
            "entry_projection_sha256",
            "semantic_sha256",
        },
        label="acceptance provider capture",
    )
    if row["schema_version"] != ACCEPTANCE_PROVIDER_CAPTURE_SCHEMA:
        _fail("acceptance provider capture schema differs")
    rebuilt = build_acceptance_provider_capture_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        contest_role=row["contest_role"],
        acquisition_receipt=row["acquisition_receipt"],
        publish_by=row["publish_by"],
    )
    if row != rebuilt:
        _fail("acceptance provider capture differs from exact raw observation")
    return row


def build_acceptance_provider_capture_v1(**_: object) -> dict[str, object]:
    _fail(
        "acceptance provider capture/v1 is retired; "
        "use authority-bound capture/v2"
    )


def validate_acceptance_provider_capture_v1(
    *_: object, **__: object
) -> dict[str, object]:
    _fail(
        "acceptance provider capture/v1 is retired; "
        "use authority-bound capture/v2"
    )


def build_accepted_entry_evidence_v2(
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    provider_capture: object,
    frozen_at: object,
) -> dict[str, object]:
    """Project accepted Entry IDs/rosters only from raw provider bytes."""

    frozen_text, frozen = _publish_by(
        frozen_at,
        label="accepted-entry evidence frozen_at",
        phase="prelock",
    )
    capture_ref = _semantic_ref(provider_capture, label="acceptance provider capture")
    capture_raw, capture_obj = _reopen_semantic(
        store,
        capture_ref["artifact_identity"],
        label="acceptance provider capture",
        expected_semantic_sha256=capture_ref["semantic_sha256"],
        not_after=frozen,
    )
    provider = validate_acceptance_provider_capture_v2(
        capture_raw,
        store=store,
        acquisition_authority=acquisition_authority,
    )
    provider_cutoff = _publish_by(
        provider["publish_by"],
        label="acceptance provider capture publish_by",
        phase="prelock",
    )[1]
    if capture_obj.created > provider_cutoff:
        _fail("acceptance provider capture was published after its cutoff")
    if provider_cutoff > frozen:
        _fail("acceptance provider capture cutoff is after evidence cutoff")
    raw_obj = _reopen_exact(
        store,
        provider["raw_observation_identity"],
        label="raw accepted-entry provider observation",
        not_after=provider_cutoff,
    )
    if capture_obj.created < raw_obj.created:
        _fail("acceptance provider capture predates its raw observation archive")
    pin = _pin_for_role(provider["contest_role"])
    entries = _parse_active_entry_export(raw_obj.raw, pin=pin)
    return seal_semantic_artifact(
        {
            "schema_version": ACCEPTED_EVIDENCE_SCHEMA,
            "complete": True,
            "observed_at": provider["observed_at"],
            "frozen_at": frozen_text,
            "contest_role": pin.role,
            "contest_id": pin.contest_id,
            "draft_group_id": EXPECTED_DRAFT_GROUP_ID,
            "provider_capture": capture_ref,
            "raw_observation_identity": raw_obj.identity,
            "entries": entries,
        }
    )


def _parse_accepted_evidence(value: object) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="accepted-entry evidence")
    _exact(
        row,
        {
            "schema_version",
            "complete",
            "observed_at",
            "frozen_at",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "provider_capture",
            "raw_observation_identity",
            "entries",
            "semantic_sha256",
        },
        label="accepted-entry evidence",
    )
    if row["schema_version"] != ACCEPTED_EVIDENCE_SCHEMA or row["complete"] is not True:
        _fail("accepted-entry evidence is not a complete supported capture")
    pin = _pin_for_role(row["contest_role"])
    if (
        row["contest_id"] != pin.contest_id
        or row["draft_group_id"] != EXPECTED_DRAFT_GROUP_ID
    ):
        _fail("accepted-entry evidence is cross-wired")
    observed_text, observed = _timestamp(
        row["observed_at"], label="accepted evidence observed_at"
    )
    frozen_text, frozen = _publish_by(
        row["frozen_at"],
        label="accepted evidence frozen_at",
        phase="prelock",
    )
    if observed > frozen:
        _fail("accepted-entry observation is after its evidence cutoff")
    entries: list[dict[str, object]] = []
    ids: set[str] = set()
    for ordinal, raw in enumerate(
        _sequence(row["entries"], label="accepted evidence entries")
    ):
        entry = _mapping(raw, label=f"accepted evidence entries[{ordinal}]")
        _exact(
            entry,
            {"entry_id", "status", "slot_dk_draftable_ids"},
            label=f"accepted evidence entries[{ordinal}]",
        )
        entry_id = _entry_id(entry["entry_id"], label="accepted Entry ID")
        if entry_id in ids:
            _fail("accepted-entry evidence repeats an Entry ID")
        ids.add(entry_id)
        if entry["status"] != "accepted":
            _fail("accepted-entry evidence contains a non-accepted row")
        slot_ids = [
            _draftable_id(item, label="accepted slot draftable ID")
            for item in _sequence(
                entry["slot_dk_draftable_ids"], label="accepted slot draftable IDs"
            )
        ]
        if len(slot_ids) != 9 or len(set(slot_ids)) != 9:
            _fail("accepted evidence roster must contain nine unique DK draftables")
        entries.append(
            {
                "entry_id": entry_id,
                "status": "accepted",
                "slot_dk_draftable_ids": slot_ids,
            }
        )
    entries.sort(key=lambda item: str(item["entry_id"]))
    if len(entries) != pin.planned_entries:
        _fail("accepted-entry evidence count differs from exact A5 K")
    row["observed_at"] = observed_text
    row["frozen_at"] = frozen_text
    row["provider_capture"] = _semantic_ref(
        row["provider_capture"], label="acceptance provider capture"
    )
    row["raw_observation_identity"] = _identity(
        row["raw_observation_identity"], label="raw acceptance observation identity"
    )
    row["entries"] = entries
    return row


def validate_accepted_entry_evidence_v2(
    value: object,
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
) -> dict[str, object]:
    row = _parse_accepted_evidence(value)
    rebuilt = build_accepted_entry_evidence_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        provider_capture=row["provider_capture"],
        frozen_at=row["frozen_at"],
    )
    if row != rebuilt:
        _fail("accepted-entry evidence differs from exact provider observation")
    return row


def build_week1_entry_acceptance_v2(
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    pins: A5CapturePins,
    manifest: object,
    prepared_capture_identity: object,
    filled_upload_identity: object,
    acceptance_evidence: object,
    accepted_at: object,
) -> dict[str, object]:
    """Project one receipt by a prospective pre-lock publication cutoff."""

    accepted_text, accepted = _publish_by(
        accepted_at,
        label="accepted_at publication cutoff",
        phase="prelock",
    )
    manifest_ref = _semantic_ref(manifest, label="manifest")
    manifest_value, _ = _load_manifest(
        store,
        pins,
        manifest_ref["artifact_identity"],
        expected_semantic_sha256=manifest_ref["semantic_sha256"],
        not_after=accepted,
    )
    contest = manifest_value["contest"]
    allocation, _ = _load_allocation(store, pins, not_after=accepted)
    bridge, books, _, _ = _load_bridge_and_books(
        store,
        bridge_ref=allocation["player_bridge"],
        book_refs=allocation["books"],
        not_after=accepted,
    )
    prepared_obj = _reopen_exact(
        store,
        prepared_capture_identity,
        label="prepared paid-entry capture",
        not_after=accepted,
    )
    prepared = _parse_prepared_capture(
        prepared_obj.raw,
        contest=contest,
        paid_book=books["P_MIX"],
        bridge=bridge,
    )
    filled_obj = _reopen_exact(
        store, filled_upload_identity, label="filled DK upload CSV", not_after=accepted
    )
    if (
        filled_obj.identity["sha256"] != prepared["csv_sha256"]
        or filled_obj.identity["bytes"] != prepared["csv_bytes"]
    ):
        _fail("filled upload raw bytes/hash differ from prepared capture")
    filled_projection = _parse_filled_upload(
        filled_obj.raw,
        contest_id=str(contest["contest_id"]),
        contest_name=str(contest["contest_name"]),
        entry_fee_micro=int(contest["entry_fee_micro"]),
        expected_entries=int(contest["planned_entries"]),
    )
    prepared_filled_projection = [
        {
            "export_ordinal": entry["export_ordinal"],
            "entry_id": entry["entry_id"],
            "slot_dk_draftable_ids": entry["slot_dk_draftable_ids"],
        }
        for entry in prepared["entries"]
    ]
    if filled_projection != prepared_filled_projection:
        _fail("prepared capture differs from deterministic filled-upload projection")
    evidence_ref = _semantic_ref(acceptance_evidence, label="acceptance evidence")
    evidence_raw, evidence_obj = _reopen_semantic(
        store,
        evidence_ref["artifact_identity"],
        label="accepted-entry evidence",
        expected_semantic_sha256=evidence_ref["semantic_sha256"],
        not_after=accepted,
    )
    evidence = validate_accepted_entry_evidence_v2(
        evidence_raw,
        store=store,
        acquisition_authority=acquisition_authority,
    )
    if evidence_obj.created > accepted:
        _fail("accepted-entry evidence provider time is after accepted_at")
    evidence_cutoff = _publish_by(
        evidence["frozen_at"],
        label="accepted-entry evidence frozen_at",
        phase="prelock",
    )[1]
    if evidence_obj.created > evidence_cutoff:
        _fail("accepted-entry evidence was published after its prospective cutoff")
    if evidence_cutoff > accepted:
        _fail("accepted-entry evidence cutoff is after accepted_at")
    evidence_observed = _timestamp(
        evidence["observed_at"], label="evidence observed_at"
    )[1]
    if evidence_observed > accepted:
        _fail("accepted-entry observation is after accepted_at")
    if prepared_obj.created > evidence_observed or filled_obj.created > evidence_observed:
        _fail(
            "prepared/filled upload artifacts must predate the provider "
            "acceptance observation"
        )
    if (
        evidence["contest_role"] != contest["contest_role"]
        or evidence["contest_id"] != contest["contest_id"]
        or evidence["draft_group_id"] != EXPECTED_DRAFT_GROUP_ID
    ):
        _fail("accepted-entry evidence is cross-wired to another A5 contest")
    if evidence["raw_observation_identity"] == filled_obj.identity:
        _fail("provider acceptance observation must be archived separately from upload")
    by_id = {item["entry_id"]: item for item in evidence["entries"]}
    if set(by_id) != {item["entry_id"] for item in prepared["entries"]}:
        _fail("accepted-entry raw projection Entry IDs differ from prepared capture")
    k = int(contest["planned_entries"])
    allocation_edges = [
        item
        for item in allocation["paid_entry_edges"]
        if item["contest_role"] == contest["contest_role"]
    ]
    if {item["entry_index"] for item in allocation_edges} != set(range(1, k + 1)):
        _fail("allocation entry-index domain differs from exact A5 K")
    if {item["lineup_rank"] for item in allocation_edges} != set(range(1, k + 1)):
        _fail("allocation lineup-rank domain differs from exact A5 K")
    realized: list[dict[str, object]] = []
    for prepared_entry in prepared["entries"]:
        export_ordinal = int(prepared_entry["export_ordinal"])
        book_ordinal = int(prepared_entry["paid_input_book_ordinal"])
        evidence_entry = by_id[prepared_entry["entry_id"]]
        if evidence_entry["slot_dk_draftable_ids"] != prepared_entry["slot_dk_draftable_ids"]:
            _fail("accepted-entry raw roster differs from prepared capture")
        book_entry = books["P_MIX"]["entries"][book_ordinal]
        realized.append(
            {
                "entry_index": export_ordinal + 1,
                "lineup_rank": book_ordinal + 1,
                "entry_id": prepared_entry["entry_id"],
                "lineup_id": book_entry["lineup_id"],
                "roster_sha256": book_entry["roster_sha256"],
                "internal_player_ids": sorted(book_entry["internal_player_ids"]),
                "dk_player_ids": prepared_entry["internal_player_ids"],
                "slot_dk_draftable_ids": prepared_entry["slot_dk_draftable_ids"],
            }
        )
    realized.sort(key=lambda item: int(item["entry_index"]))
    if {item["entry_index"] for item in realized} != set(range(1, k + 1)):
        _fail("realized acceptance entry indices are not a complete bijection")
    if {item["lineup_rank"] for item in realized} != set(range(1, k + 1)):
        _fail("realized acceptance lineup ranks are not a complete bijection")
    evidence_projection = evidence["entries"]
    return seal_semantic_artifact(
        {
            "schema_version": ACCEPTANCE_SCHEMA,
            "contest_role": contest["contest_role"],
            "contest_id": contest["contest_id"],
            "draft_group_id": EXPECTED_DRAFT_GROUP_ID,
            "lock_utc": EXPECTED_LOCK_UTC,
            "accepted_at": accepted_text,
            "manifest": manifest_ref,
            "allocation": _ref(
                pins.allocation_identity, pins.allocation_semantic_sha256
            ),
            "prepared_capture_identity": prepared_obj.identity,
            "filled_upload_identity": filled_obj.identity,
            "acceptance_evidence": evidence_ref,
            "acceptance_evidence_projection_sha256": canonical_sha256(
                evidence_projection
            ),
            "salary_catalog_sha256": prepared["salary_catalog_sha256"],
            "paid_export_receipt_sha256": prepared["paid_export_receipt_sha256"],
            "entry_count": k,
            "realized_entry_lineup_bijection": realized,
        }
    )


def validate_week1_entry_acceptance_v2(
    value: object,
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    pins: A5CapturePins,
) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="entry acceptance")
    _exact(
        row,
        {
            "schema_version",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "lock_utc",
            "accepted_at",
            "manifest",
            "allocation",
            "prepared_capture_identity",
            "filled_upload_identity",
            "acceptance_evidence",
            "acceptance_evidence_projection_sha256",
            "salary_catalog_sha256",
            "paid_export_receipt_sha256",
            "entry_count",
            "realized_entry_lineup_bijection",
            "semantic_sha256",
        },
        label="entry acceptance",
    )
    if row["schema_version"] != ACCEPTANCE_SCHEMA:
        _fail("entry acceptance schema differs")
    rebuilt = build_week1_entry_acceptance_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        pins=pins,
        manifest=row["manifest"],
        prepared_capture_identity=row["prepared_capture_identity"],
        filled_upload_identity=row["filled_upload_identity"],
        acceptance_evidence=row["acceptance_evidence"],
        accepted_at=row["accepted_at"],
    )
    if row != rebuilt:
        _fail("entry acceptance differs from its exact raw evidence projection")
    return row


def build_week1_acceptance_root_v2(
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    pins: A5CapturePins,
    manifests: object,
    acceptances: object,
    frozen_at: object,
) -> dict[str, object]:
    frozen_text, frozen = _publish_by(
        frozen_at,
        label="acceptance root frozen_at",
        phase="prelock",
    )
    _load_allocation(store, pins, not_after=frozen)
    manifest_refs = _mapping(manifests, label="manifest references")
    acceptance_refs = _mapping(acceptances, label="acceptance references")
    if set(manifest_refs) != set(A5_ROLE_TABLE) or set(acceptance_refs) != set(A5_ROLE_TABLE):
        _fail("acceptance root requires all exact A5 roles")
    retained_manifests: dict[str, dict[str, object]] = {}
    retained_acceptances: dict[str, dict[str, object]] = {}
    all_entry_ids: set[str] = set()
    contest_rows: list[dict[str, object]] = []
    for pin in _ROLE_ROWS:
        manifest_ref = _semantic_ref(
            manifest_refs[pin.role], label=f"{pin.role} manifest"
        )
        manifest, _ = _load_manifest(
            store,
            pins,
            manifest_ref["artifact_identity"],
            expected_semantic_sha256=manifest_ref["semantic_sha256"],
            not_after=frozen,
        )
        acceptance_ref = _semantic_ref(
            acceptance_refs[pin.role], label=f"{pin.role} acceptance"
        )
        acceptance_raw, acceptance_obj = _reopen_semantic(
            store,
            acceptance_ref["artifact_identity"],
            label=f"{pin.role} acceptance",
            expected_semantic_sha256=acceptance_ref["semantic_sha256"],
            not_after=frozen,
        )
        acceptance = validate_week1_entry_acceptance_v2(
            acceptance_raw,
            store=store,
            acquisition_authority=acquisition_authority,
            pins=pins,
        )
        declared_acceptance = _timestamp(
            acceptance["accepted_at"], label="accepted_at"
        )[1]
        if declared_acceptance > frozen:
            _fail("acceptance declared time is after root freeze")
        if acceptance_obj.created > declared_acceptance:
            _fail("acceptance provider creation is after accepted_at")
        if manifest["contest"]["contest_role"] != pin.role:
            _fail("acceptance root manifest is cross-wired")
        if acceptance["contest_role"] != pin.role or acceptance["manifest"] != manifest_ref:
            _fail("acceptance root receipt is cross-wired")
        ids = {item["entry_id"] for item in acceptance["realized_entry_lineup_bijection"]}
        if len(ids) != pin.planned_entries or all_entry_ids & ids:
            _fail("acceptance root Entry IDs are incomplete or globally duplicated")
        all_entry_ids.update(ids)
        retained_manifests[pin.role] = manifest_ref
        retained_acceptances[pin.role] = acceptance_ref
        contest_rows.append(
            {
                "contest_role": pin.role,
                "contest_id": pin.contest_id,
                "planned_entries": pin.planned_entries,
                "accepted_entries": len(ids),
            }
        )
    if len(all_entry_ids) != EXPECTED_PLANNED_ENTRIES:
        _fail("acceptance root does not contain exactly 90 unique entries")
    return seal_semantic_artifact(
        {
            "schema_version": ACCEPTANCE_ROOT_SCHEMA,
            "allocation": _ref(
                pins.allocation_identity, pins.allocation_semantic_sha256
            ),
            "frozen_at": frozen_text,
            "manifests": retained_manifests,
            "acceptances": retained_acceptances,
            "required_contests": contest_rows,
            "accepted_entry_count": EXPECTED_PLANNED_ENTRIES,
            "planned_spend_micro": EXPECTED_PLANNED_SPEND_MICRO,
        }
    )


def validate_week1_acceptance_root_v2(
    value: object,
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    pins: A5CapturePins,
) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="acceptance root")
    _exact(
        row,
        {
            "schema_version",
            "allocation",
            "frozen_at",
            "manifests",
            "acceptances",
            "required_contests",
            "accepted_entry_count",
            "planned_spend_micro",
            "semantic_sha256",
        },
        label="acceptance root",
    )
    if row["schema_version"] != ACCEPTANCE_ROOT_SCHEMA:
        _fail("acceptance root schema differs")
    rebuilt = build_week1_acceptance_root_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        pins=pins,
        manifests=row["manifests"],
        acceptances=row["acceptances"],
        frozen_at=row["frozen_at"],
    )
    if row != rebuilt:
        _fail("acceptance root differs from exact manifest/receipt reopens")
    return row


_SLOT_RE = re.compile(r"(?:^|\s)(QB|RB|WR|TE|FLEX|DST)\s+")


def _parse_lineup_names(value: object) -> list[tuple[str, str]]:
    text = _string(value, label="standings lineup")
    matches = list(_SLOT_RE.finditer(text))
    slots: list[tuple[str, str]] = []
    for ordinal, match in enumerate(matches):
        end = matches[ordinal + 1].start() if ordinal + 1 < len(matches) else len(text)
        name = text[match.end() : end].strip()
        if not name:
            _fail("standings lineup contains an empty player")
        slots.append((match.group(1), name))
    if tuple(slot for slot, _ in slots) != CLASSIC_SLOTS:
        _fail("standings lineup is not an ordered NFL Classic roster")
    if len({name for _, name in slots}) != 9:
        _fail("standings lineup repeats a player")
    return slots


def _decimal_micro(value: object, *, label: str, signed: bool) -> int:
    text = str(value).strip().replace(",", "")
    if not text:
        _fail(f"{label} is empty")
    try:
        retained = Decimal(text) * Decimal(1_000_000)
    except InvalidOperation as exc:
        raise Week1A5CaptureContractError(f"{label} is not numeric") from exc
    if retained != retained.to_integral_value():
        _fail(f"{label} has precision finer than micro-units")
    result = int(retained)
    if not signed and result < 0:
        _fail(f"{label} must be nonnegative")
    return result


def _cash_micro(value: object) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = f"-{text[1:-1]}"
    text = text.replace("$", "").replace(",", "")
    return _decimal_micro(text, label="standings cash payout", signed=False)


def _settled_time(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"0", "0.0", "00:00", "00:00:00"}:
        return "0"
    try:
        if Decimal(text) == 0:
            return "0"
    except InvalidOperation:
        pass
    _fail("standings row is not demonstrably settled")


def _parse_ticket(value: object, *, allowed: Sequence[str]) -> list[str]:
    text = str(value or "").strip()
    if not text or text.startswith("$"):
        return []
    if text in allowed:
        return [text]
    if text == ",".join(allowed):
        return list(allowed)
    _fail("standings ticket destination differs from source-backed terms")


def _parse_raw_standings(
    raw: bytes,
    *,
    bridge: Mapping[str, object],
    qualifier_ticket_destinations: Sequence[str],
) -> list[dict[str, object]]:
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
    except UnicodeDecodeError as exc:
        raise Week1A5CaptureContractError("raw standings are not UTF-8 CSV") from exc
    fields = set(reader.fieldnames or ())
    required = {"Rank", "EntryId", "Points", "TimeRemaining", "Lineup"}
    if not required <= fields or not ({"Winnings", "Prize"} & fields):
        _fail("raw standings are missing complete-field settlement columns")
    by_name = {item["display_name"]: item for item in bridge["players"]}
    rows: list[dict[str, object]] = []
    for raw_row in reader:
        if not str(raw_row.get("Rank") or "").strip() or not str(
            raw_row.get("Lineup") or ""
        ).strip():
            continue
        try:
            rank = int(str(raw_row["Rank"]).replace(",", "").strip())
        except (TypeError, ValueError) as exc:
            raise Week1A5CaptureContractError("standings rank is not an integer") from exc
        if rank < 1:
            _fail("standings rank must be positive")
        entry_id = _entry_id(raw_row["EntryId"], label="standings Entry ID")
        points = _decimal_micro(
            raw_row["Points"], label="standings fantasy points", signed=True
        )
        time_remaining = _settled_time(raw_row["TimeRemaining"])
        lineup = _parse_lineup_names(raw_row["Lineup"])
        try:
            players = [by_name[name] for _, name in lineup]
        except KeyError as exc:
            raise Week1A5CaptureContractError(
                "standings roster player is absent from the exact player bridge"
            ) from exc
        for (slot, _), player in zip(lineup, players, strict=True):
            if not _slot_eligible(slot, (str(player["position"]),)):
                _fail("standings roster violates the exact player bridge positions")
        internal_ids = sorted(str(player["internal_player_id"]) for player in players)
        draftable_ids = [int(player["dk_draftable_id"]) for player in players]
        roster_sha = canonical_sha256(internal_ids)
        ticket_source = raw_row.get("Prize", "")
        tickets = _parse_ticket(
            ticket_source, allowed=qualifier_ticket_destinations
        )
        rows.append(
            {
                "entry_id": entry_id,
                "rank": rank,
                "points_micropoints": points,
                "cash_payout_micro": _cash_micro(raw_row.get("Winnings", "")),
                "ticket_destinations": tickets,
                "time_remaining": time_remaining,
                "lineup_id": f"lineup-v1-{roster_sha}",
                "roster_sha256": roster_sha,
                "internal_player_ids": internal_ids,
                "slot_dk_draftable_ids": draftable_ids,
            }
        )
    if not rows:
        _fail("raw standings contain no entry rows")
    ids = [item["entry_id"] for item in rows]
    if len(ids) != len(set(ids)):
        _fail("raw standings repeat an Entry ID")
    scores = Counter(int(item["points_micropoints"]) for item in rows)
    better = 0
    expected_rank: dict[int, int] = {}
    for score in sorted(scores, reverse=True):
        expected_rank[score] = better + 1
        better += scores[score]
    if any(
        item["rank"] != expected_rank[int(item["points_micropoints"])]
        for item in rows
    ):
        _fail("raw standings ranks do not reproduce full-field competition rank")
    rows.sort(key=lambda item: (int(item["rank"]), str(item["entry_id"])))
    return rows


def _source_integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is str and value.isdigit():
        value = int(value)
    return _integer(value, label=label, minimum=minimum)


def _parse_final_field_provider_body(raw: bytes) -> dict[str, object]:
    """Parse the exact DK contest-detail HTTP response body, not a wrapper."""

    body = _parse_json(raw, label="raw final-field provider response")
    if body.get("schema_version") == FINAL_FIELD_SOURCE_SCHEMA or "source" in body:
        _fail("caller-authored final-field source wrappers are retired")
    error_status = body.get("errorStatus", {})
    if error_status not in ({}, None, False):
        _fail("final-field provider response contains an error status")
    detail = _mapping(body.get("contestDetail"), label="provider contestDetail")
    contest_id = _entry_id(
        detail.get("contestKey"), label="provider final-field contest ID"
    )
    draft_group_id = str(
        _source_integer(
            detail.get("draftGroupId"),
            label="provider final-field draft group",
            minimum=1,
        )
    )
    state = _string(detail.get("contestState"), label="provider contestState")
    state_detail_value = detail.get("contestStateDetail")
    state_detail = (
        _string(state_detail_value, label="provider contestStateDetail")
        if state_detail_value not in (None, "")
        else state
    )
    if state not in _SETTLED_CONTEST_STATES:
        _fail("raw final-field provider response does not show settled state")
    final_size = _source_integer(
        detail.get("entries"),
        label="provider final submitted entry count",
        minimum=1,
    )
    return {
        "contest_id": contest_id,
        "draft_group_id": draft_group_id,
        "provider_contest_state": state,
        "provider_contest_state_detail": state_detail,
        "settled": True,
        "displayed_final_field_size": final_size,
    }


def _count_raw_standings_entries(raw: bytes) -> int:
    """Stream-count exact provider rows without interpreting score columns."""

    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    except UnicodeDecodeError as exc:
        raise Week1A5CaptureContractError(
            "raw standings are not UTF-8 CSV"
        ) from exc
    fields = set(reader.fieldnames or ())
    required = {"Rank", "EntryId", "Lineup"}
    if not required <= fields:
        _fail("raw standings are missing entry-count authority columns")
    seen: set[str] = set()
    count = 0
    for row in reader:
        has_rank = bool(str(row.get("Rank") or "").strip())
        has_lineup = bool(str(row.get("Lineup") or "").strip())
        if not has_rank and not has_lineup:
            continue
        if not has_rank or not has_lineup:
            _fail("raw standings contain a partial entry row")
        entry_id = _entry_id(row.get("EntryId"), label="standings Entry ID")
        if entry_id in seen:
            _fail("raw standings repeat an Entry ID")
        seen.add(entry_id)
        count += 1
    if count < 1:
        _fail("raw standings contain no entry rows")
    return count


def inspect_final_field_provider_bytes_v1(
    provider_raw: bytes,
    standings_raw: bytes,
    *,
    contest_role: object,
) -> dict[str, object]:
    """Return a redacted, write-free final-field real-shape projection."""

    pin = _pin_for_role(contest_role)
    projection = _parse_final_field_provider_body(provider_raw)
    if (
        projection["contest_id"] != pin.contest_id
        or projection["draft_group_id"] != EXPECTED_DRAFT_GROUP_ID
    ):
        _fail("raw final-field provider response is cross-wired")
    if projection["displayed_final_field_size"] > pin.advertised_field_capacity:
        _fail("provider final submitted count exceeds advertised A5 capacity")
    parsed_count = _count_raw_standings_entries(standings_raw)
    if parsed_count != projection["displayed_final_field_size"]:
        _fail("raw standings count differs from provider final submitted count")
    return {
        "schema_version": "week1-a5-final-field-shape-smoke/v1",
        "source_profile": FINAL_FIELD_CAPTURE_METHOD,
        "contest_role": pin.role,
        "contest_id": pin.contest_id,
        "provider_contest_state": projection["provider_contest_state"],
        "provider_contest_state_detail": projection[
            "provider_contest_state_detail"
        ],
        "provider_final_entry_count": projection["displayed_final_field_size"],
        "parsed_standings_entry_count": parsed_count,
        "provider_raw_sha256": hashlib.sha256(provider_raw).hexdigest(),
        "provider_raw_bytes": len(provider_raw),
        "standings_raw_sha256": hashlib.sha256(standings_raw).hexdigest(),
        "standings_raw_bytes": len(standings_raw),
        "writes_performed": False,
    }


def build_final_field_provider_capture_v2(
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    contest_role: object,
    provider_acquisition_receipt: object,
    standings_acquisition_receipt: object,
    publish_by: object,
) -> dict[str, object]:
    """Bind authority-issued contest-detail and standings acquisitions."""

    pin = _pin_for_role(contest_role)
    publish_text, cutoff = _publish_by(
        publish_by,
        label="final-field provider capture publish_by",
        phase="postlock",
    )
    _, lock = _timestamp(EXPECTED_LOCK_UTC, label="A5 lock")
    provider_acquisition = _reopen_authenticated_acquisition(
        store=store,
        acquisition_authority=acquisition_authority,
        receipt=provider_acquisition_receipt,
        expected_profile=CONTEST_DETAIL_ACQUISITION_PROFILE,
        pin=pin,
        not_after=cutoff,
        not_before=lock,
    )
    standings_acquisition = _reopen_authenticated_acquisition(
        store=store,
        acquisition_authority=acquisition_authority,
        receipt=standings_acquisition_receipt,
        expected_profile=STANDINGS_ACQUISITION_PROFILE,
        pin=pin,
        not_after=cutoff,
        not_before=lock,
    )
    provider_observed_text, provider_observed = _timestamp(
        provider_acquisition.receipt["observed_at"],
        label="final-field provider observed_at",
    )
    standings_observed_text, standings_observed = _timestamp(
        standings_acquisition.receipt["observed_at"],
        label="standings observed_at",
    )
    if (
        provider_acquisition.receipt["authority_event_id"]
        == standings_acquisition.receipt["authority_event_id"]
    ):
        _fail("final-field sources do not have separate authority events")
    if provider_observed <= lock or standings_observed <= lock:
        _fail("final-field sources must be observed strictly after lock")
    if provider_observed > cutoff or standings_observed > cutoff:
        _fail("final-field source observation is after its publish-by cutoff")
    provider_obj = provider_acquisition.raw_object
    standings_obj = standings_acquisition.raw_object
    if provider_obj.created <= lock or standings_obj.created <= lock:
        _fail("final-field source archive creation is not strictly post-lock")
    projection = _parse_final_field_provider_body(provider_obj.raw)
    if (
        projection["contest_id"] != pin.contest_id
        or projection["draft_group_id"] != EXPECTED_DRAFT_GROUP_ID
    ):
        _fail("raw final-field provider response is cross-wired")
    if projection["displayed_final_field_size"] > pin.advertised_field_capacity:
        _fail("provider final submitted count exceeds advertised A5 capacity")
    parsed_count = _count_raw_standings_entries(standings_obj.raw)
    if parsed_count != projection["displayed_final_field_size"]:
        _fail("raw standings count differs from provider final submitted count")
    return seal_semantic_artifact(
        {
            "schema_version": FINAL_FIELD_PROVIDER_CAPTURE_SCHEMA,
            "source_system": "draftkings",
            "capture_method": FINAL_FIELD_CAPTURE_METHOD,
            "source_locator": f"{FINAL_FIELD_SOURCE_LOCATOR_PREFIX}{pin.contest_id}",
            "contest_role": pin.role,
            "contest_id": pin.contest_id,
            "draft_group_id": EXPECTED_DRAFT_GROUP_ID,
            "provider_observed_at": provider_observed_text,
            "standings_observed_at": standings_observed_text,
            "publish_by": publish_text,
            "provider_acquisition_receipt": _semantic_ref(
                provider_acquisition_receipt,
                label="contest-detail acquisition receipt",
            ),
            "standings_acquisition_receipt": _semantic_ref(
                standings_acquisition_receipt,
                label="standings acquisition receipt",
            ),
            "provider_authority_event_id": provider_acquisition.receipt[
                "authority_event_id"
            ],
            "standings_authority_event_id": standings_acquisition.receipt[
                "authority_event_id"
            ],
            "raw_provider_body_identity": provider_obj.identity,
            "raw_standings_identity": standings_obj.identity,
            "provider_contest_state": projection["provider_contest_state"],
            "provider_contest_state_detail": projection[
                "provider_contest_state_detail"
            ],
            "provider_final_entry_count": projection[
                "displayed_final_field_size"
            ],
            "parsed_standings_entry_count": parsed_count,
        }
    )


def validate_final_field_provider_capture_v2(
    value: object,
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="final-field provider capture")
    _exact(
        row,
        {
            "schema_version",
            "source_system",
            "capture_method",
            "source_locator",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "provider_observed_at",
            "standings_observed_at",
            "publish_by",
            "provider_acquisition_receipt",
            "standings_acquisition_receipt",
            "provider_authority_event_id",
            "standings_authority_event_id",
            "raw_provider_body_identity",
            "raw_standings_identity",
            "provider_contest_state",
            "provider_contest_state_detail",
            "provider_final_entry_count",
            "parsed_standings_entry_count",
            "semantic_sha256",
        },
        label="final-field provider capture",
    )
    if row["schema_version"] != FINAL_FIELD_PROVIDER_CAPTURE_SCHEMA:
        _fail("final-field provider capture schema differs")
    rebuilt = build_final_field_provider_capture_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        contest_role=row["contest_role"],
        provider_acquisition_receipt=row["provider_acquisition_receipt"],
        standings_acquisition_receipt=row["standings_acquisition_receipt"],
        publish_by=row["publish_by"],
    )
    if row != rebuilt:
        _fail("final-field provider capture differs from exact source bytes")
    return row


def build_final_field_provider_capture_v1(**_: object) -> dict[str, object]:
    _fail(
        "final-field provider capture/v1 is retired; "
        "use authority-bound capture/v2"
    )


def validate_final_field_provider_capture_v1(
    *_: object, **__: object
) -> dict[str, object]:
    _fail(
        "final-field provider capture/v1 is retired; "
        "use authority-bound capture/v2"
    )


def build_final_field_evidence_v2(
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    provider_capture: object,
    frozen_at: object,
) -> dict[str, object]:
    """Project final size/state only from a validated raw-source receipt."""

    frozen_text, frozen = _publish_by(
        frozen_at,
        label="final-field evidence frozen_at",
        phase="postlock",
    )
    _, lock = _timestamp(EXPECTED_LOCK_UTC, label="A5 lock")
    capture_ref = _semantic_ref(provider_capture, label="final-field provider capture")
    capture_raw, capture_obj = _reopen_semantic(
        store,
        capture_ref["artifact_identity"],
        label="final-field provider capture",
        expected_semantic_sha256=capture_ref["semantic_sha256"],
        not_after=frozen,
        not_before=lock,
    )
    capture = validate_final_field_provider_capture_v2(
        capture_raw,
        store=store,
        acquisition_authority=acquisition_authority,
    )
    capture_cutoff = _publish_by(
        capture["publish_by"],
        label="final-field provider capture publish_by",
        phase="postlock",
    )[1]
    if capture_obj.created > capture_cutoff:
        _fail("final-field provider capture was published after its cutoff")
    if capture_cutoff > frozen:
        _fail("final-field provider capture cutoff is after evidence cutoff")
    provider_obj = _reopen_exact(
        store,
        capture["raw_provider_body_identity"],
        label="raw final-field provider response",
        not_after=capture_cutoff,
        not_before=lock,
    )
    standings_obj = _reopen_exact(
        store,
        capture["raw_standings_identity"],
        label="raw complete standings",
        not_after=capture_cutoff,
        not_before=lock,
    )
    if capture_obj.created < max(provider_obj.created, standings_obj.created):
        _fail("final-field provider capture predates one of its raw archives")
    return seal_semantic_artifact(
        {
            "schema_version": FINAL_FIELD_EVIDENCE_SCHEMA,
            "contest_id": capture["contest_id"],
            "draft_group_id": capture["draft_group_id"],
            "settled": True,
            "provider_contest_state": capture["provider_contest_state"],
            "provider_contest_state_detail": capture[
                "provider_contest_state_detail"
            ],
            "displayed_final_field_size": capture[
                "provider_final_entry_count"
            ],
            "captured_at": capture["provider_observed_at"],
            "standings_captured_at": capture["standings_observed_at"],
            "frozen_at": frozen_text,
            "provider_capture": capture_ref,
            "provider_source_identity": provider_obj.identity,
            "raw_standings_identity": standings_obj.identity,
        }
    )


def _parse_final_field_evidence(value: object) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="final-field evidence")
    _exact(
        row,
        {
            "schema_version",
            "contest_id",
            "draft_group_id",
            "settled",
            "provider_contest_state",
            "provider_contest_state_detail",
            "displayed_final_field_size",
            "captured_at",
            "standings_captured_at",
            "frozen_at",
            "provider_capture",
            "provider_source_identity",
            "raw_standings_identity",
            "semantic_sha256",
        },
        label="final-field evidence",
    )
    if row["schema_version"] != FINAL_FIELD_EVIDENCE_SCHEMA:
        _fail("final-field evidence schema differs")
    if row["settled"] is not True:
        _fail("final-field evidence does not prove settled state")
    _string(row["provider_contest_state"], label="provider contest state")
    _string(
        row["provider_contest_state_detail"],
        label="provider contest state detail",
    )
    _string(row["contest_id"], label="final-field contest ID")
    if row["draft_group_id"] != EXPECTED_DRAFT_GROUP_ID:
        _fail("final-field evidence draft group differs")
    _integer(
        row["displayed_final_field_size"],
        label="displayed final field size",
        minimum=1,
    )
    captured_text, captured = _timestamp(
        row["captured_at"], label="final-field captured_at"
    )
    _, lock = _timestamp(EXPECTED_LOCK_UTC, label="A5 lock")
    if captured <= lock:
        _fail("final-field evidence must be captured after lock")
    standings_captured_text, standings_captured = _timestamp(
        row["standings_captured_at"], label="standings captured_at"
    )
    if standings_captured <= lock:
        _fail("standings evidence must be captured after lock")
    row["captured_at"] = captured_text
    row["standings_captured_at"] = standings_captured_text
    row["frozen_at"] = _publish_by(
        row["frozen_at"],
        label="final-field evidence frozen_at",
        phase="postlock",
    )[0]
    row["provider_capture"] = _semantic_ref(
        row["provider_capture"], label="final-field provider capture"
    )
    row["provider_source_identity"] = _identity(
        row["provider_source_identity"], label="final-field provider source identity"
    )
    row["raw_standings_identity"] = _identity(
        row["raw_standings_identity"], label="raw standings identity"
    )
    return row


def validate_final_field_evidence_v2(
    value: object,
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
) -> dict[str, object]:
    row = _parse_final_field_evidence(value)
    rebuilt = build_final_field_evidence_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        provider_capture=row["provider_capture"],
        frozen_at=row["frozen_at"],
    )
    if row != rebuilt:
        _fail("final-field evidence differs from exact raw-source projection")
    return row


def build_final_field_evidence_v1(**_: object) -> dict[str, object]:
    _fail("final-field evidence/v1 is retired; use raw-source evidence/v2")


def validate_final_field_evidence_v1(**_: object) -> dict[str, object]:
    _fail("final-field evidence/v1 is retired; use raw-source evidence/v2")


def build_normalized_standings_v2(
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    final_field_evidence: object,
    player_bridge: object,
    frozen_at: object,
) -> dict[str, object]:
    """Normalize a complete field only from exact raw/evidence/bridge bytes."""

    frozen_text, frozen = _publish_by(
        frozen_at,
        label="normalized field frozen_at",
        phase="postlock",
    )
    _, lock = _timestamp(EXPECTED_LOCK_UTC, label="A5 lock")
    evidence_ref = _semantic_ref(final_field_evidence, label="final-field evidence")
    evidence_raw, evidence_obj = _reopen_semantic(
        store,
        evidence_ref["artifact_identity"],
        label="final-field evidence",
        expected_semantic_sha256=evidence_ref["semantic_sha256"],
        not_after=frozen,
        not_before=lock,
    )
    evidence = validate_final_field_evidence_v2(
        evidence_raw,
        store=store,
        acquisition_authority=acquisition_authority,
    )
    if evidence_obj.created <= lock:
        _fail("final-field evidence provider time is not post-lock")
    if evidence_obj.created > _timestamp(
        evidence["frozen_at"], label="final-field evidence frozen_at"
    )[1]:
        _fail("final-field evidence provider creation is after its declared freeze")
    if _timestamp(evidence["frozen_at"], label="final-field evidence frozen_at")[1] > frozen:
        _fail("final-field evidence freeze is after normalized-field freeze")
    if _timestamp(evidence["captured_at"], label="evidence captured_at")[1] > frozen:
        _fail("final-field captured_at is after normalized freeze")
    if (
        _timestamp(
            evidence["standings_captured_at"], label="standings captured_at"
        )[1]
        > frozen
    ):
        _fail("standings captured_at is after normalized freeze")
    bridge, bridge_ref, _ = _load_player_bridge(
        store,
        bridge_ref=player_bridge,
        not_after=lock,
    )
    raw_obj = _reopen_exact(
        store,
        evidence["raw_standings_identity"],
        label="raw complete standings",
        not_after=frozen,
        not_before=lock,
    )
    if raw_obj.created <= lock:
        _fail("raw standings provider time is not post-lock")
    pin = next(
        (item for item in _ROLE_ROWS if item.contest_id == evidence["contest_id"]),
        None,
    )
    if pin is None:
        _fail("final-field evidence names a contest outside exact A5")
    rows = _parse_raw_standings(
        raw_obj.raw,
        bridge=bridge,
        qualifier_ticket_destinations=(
            QUALIFIER_TICKET_NAMES if pin.is_qualifier else ()
        ),
    )
    displayed = int(evidence["displayed_final_field_size"])
    if len(rows) != displayed:
        _fail("raw standings row count differs from source-backed displayed final size")
    if displayed > pin.advertised_field_capacity:
        _fail("final field exceeds advertised source capacity")
    return seal_semantic_artifact(
        {
            "schema_version": NORMALIZED_STANDINGS_SCHEMA,
            "contest_id": pin.contest_id,
            "draft_group_id": EXPECTED_DRAFT_GROUP_ID,
            "captured_at": evidence["captured_at"],
            "frozen_at": frozen_text,
            "settled": True,
            "displayed_final_field_size": displayed,
            "parsed_final_field_size": len(rows),
            "raw_standings_identity": raw_obj.identity,
            "final_field_evidence": evidence_ref,
            "player_bridge": bridge_ref,
            "rows": rows,
        }
    )


def validate_normalized_standings_v2(
    value: object,
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="normalized standings")
    _exact(
        row,
        {
            "schema_version",
            "contest_id",
            "draft_group_id",
            "captured_at",
            "frozen_at",
            "settled",
            "displayed_final_field_size",
            "parsed_final_field_size",
            "raw_standings_identity",
            "final_field_evidence",
            "player_bridge",
            "rows",
            "semantic_sha256",
        },
        label="normalized standings",
    )
    if row["schema_version"] != NORMALIZED_STANDINGS_SCHEMA:
        _fail("normalized standings schema differs")
    rebuilt = build_normalized_standings_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        final_field_evidence=row["final_field_evidence"],
        player_bridge=row["player_bridge"],
        frozen_at=row["frozen_at"],
    )
    if row != rebuilt:
        _fail("normalized standings differ from exact raw/evidence projection")
    return row


def build_normalized_standings_v1(**_: object) -> dict[str, object]:
    _fail("normalized complete-field/v1 is retired; use v2")


def validate_normalized_standings_v1(**_: object) -> dict[str, object]:
    _fail("normalized complete-field/v1 is retired; use v2")


def _tier_for_rank(
    payout_ladder: Sequence[Mapping[str, object]], rank: int
) -> Mapping[str, object] | None:
    for tier in payout_ladder:
        if int(tier["rank_start"]) <= rank <= int(tier["rank_end"]):
            return tier
    return None


def _reconcile_source_payouts(
    rows: Sequence[Mapping[str, object]],
    payout_ladder: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    grouped: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["points_micropoints"])].append(row)
    expected_cash_total = 0
    observed_cash_total = 0
    expected_ticket_quantity = 0
    observed_ticket_quantity = 0
    tie_remainder_cents = 0
    for score in sorted(grouped, reverse=True):
        group = grouped[score]
        rank = int(group[0]["rank"])
        if any(int(item["rank"]) != rank for item in group):
            _fail("equal scores have unequal competition ranks")
        cash_pool = 0
        tickets: list[Mapping[str, object]] = []
        for position in range(rank, rank + len(group)):
            tier = _tier_for_rank(payout_ladder, position)
            if tier is None:
                continue
            if tier["kind"] == "cash":
                cash_pool += int(tier["cash_micro"]) * int(tier["quantity"])
            else:
                tickets.extend([tier] * int(tier["quantity"]))
        if cash_pool % _CENT_MICRO:
            _fail("source cash pool is not cent-exact")
        cents, remainder = divmod(cash_pool // _CENT_MICRO, len(group))
        expected_group_cash = sorted(
            [
                (cents + (1 if index < remainder else 0)) * _CENT_MICRO
                for index in range(len(group))
            ]
        )
        observed_group_cash = sorted(int(item["cash_payout_micro"]) for item in group)
        if observed_group_cash != expected_group_cash:
            _fail("observed cash payouts differ from exact source/tie-cent law")
        expected_destinations = [
            tuple(str(item) for item in tier["ticket_destinations"]) for tier in tickets
        ]
        observed_destinations = [
            tuple(str(item) for item in item["ticket_destinations"])
            for item in group
            if item["ticket_destinations"]
        ]
        if len(observed_destinations) != len(expected_destinations):
            _fail("observed qualifier ticket quantity differs from source ladder")
        for observed in observed_destinations:
            if not any(
                observed == expected
                or (len(observed) == 1 and observed[0] in expected)
                for expected in expected_destinations
            ):
                _fail("observed qualifier ticket destination differs")
        expected_cash_total += cash_pool
        observed_cash_total += sum(observed_group_cash)
        expected_ticket_quantity += len(expected_destinations)
        observed_ticket_quantity += len(observed_destinations)
        tie_remainder_cents += remainder
    if expected_cash_total != observed_cash_total:
        _fail("complete-field cash total does not reconcile exactly")
    if expected_ticket_quantity != observed_ticket_quantity:
        _fail("complete-field ticket total does not reconcile exactly")
    return {
        "expected_cash_pool_micro": expected_cash_total,
        "observed_cash_pool_micro": observed_cash_total,
        "expected_ticket_quantity": expected_ticket_quantity,
        "observed_ticket_quantity": observed_ticket_quantity,
        "tie_remainder_cents": tie_remainder_cents,
        "reconciled": True,
    }


def build_week1_settlement_v2(
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    pins: A5CapturePins,
    acceptance_root: object,
    normalized_standings: object,
    settlement_frozen_at: object,
) -> dict[str, object]:
    """Build a source-backed settlement from one exact complete field."""

    frozen_text, frozen = _publish_by(
        settlement_frozen_at,
        label="settlement frozen_at",
        phase="postlock",
    )
    _, lock = _timestamp(EXPECTED_LOCK_UTC, label="A5 lock")
    root_ref = _semantic_ref(acceptance_root, label="acceptance root")
    root_raw, root_obj = _reopen_semantic(
        store,
        root_ref["artifact_identity"],
        label="acceptance root",
        expected_semantic_sha256=root_ref["semantic_sha256"],
        not_after=lock,
    )
    root = validate_week1_acceptance_root_v2(
        root_raw,
        store=store,
        acquisition_authority=acquisition_authority,
        pins=pins,
    )
    if root_obj.created > _timestamp(root["frozen_at"], label="root frozen_at")[1]:
        _fail("acceptance-root provider creation is after its declared freeze")
    normalized_ref = _semantic_ref(normalized_standings, label="normalized standings")
    normalized_raw, normalized_obj = _reopen_semantic(
        store,
        normalized_ref["artifact_identity"],
        label="normalized standings",
        expected_semantic_sha256=normalized_ref["semantic_sha256"],
        not_after=frozen,
        not_before=lock,
    )
    if normalized_obj.created <= lock:
        _fail("normalized standings provider time is not post-lock")
    normalized = validate_normalized_standings_v2(
        normalized_raw,
        store=store,
        acquisition_authority=acquisition_authority,
    )
    if normalized_obj.created > _timestamp(
        normalized["frozen_at"], label="normalized frozen_at"
    )[1]:
        _fail("normalized provider creation is after its declared freeze")
    if _timestamp(normalized["frozen_at"], label="normalized frozen_at")[1] > frozen:
        _fail("normalized-field freeze is after settlement freeze")
    contest_id = normalized["contest_id"]
    pin = next((item for item in _ROLE_ROWS if item.contest_id == contest_id), None)
    if pin is None:
        _fail("normalized standings name a contest outside exact A5")
    manifest_ref = root["manifests"][pin.role]
    manifest, _ = _load_manifest(
        store,
        pins,
        manifest_ref["artifact_identity"],
        expected_semantic_sha256=manifest_ref["semantic_sha256"],
        not_after=lock,
    )
    acceptance_ref = root["acceptances"][pin.role]
    acceptance_raw, _ = _reopen_semantic(
        store,
        acceptance_ref["artifact_identity"],
        label=f"{pin.role} acceptance",
        expected_semantic_sha256=acceptance_ref["semantic_sha256"],
        not_after=lock,
    )
    acceptance = validate_week1_entry_acceptance_v2(
        acceptance_raw,
        store=store,
        acquisition_authority=acquisition_authority,
        pins=pins,
    )
    if normalized["player_bridge"] != manifest["player_bridge"]:
        _fail("normalized standings name another exact player bridge")
    rows_by_id = {item["entry_id"]: item for item in normalized["rows"]}
    paid_results: list[dict[str, object]] = []
    for accepted in acceptance["realized_entry_lineup_bijection"]:
        try:
            final = rows_by_id[accepted["entry_id"]]
        except KeyError as exc:
            raise Week1A5CaptureContractError(
                "complete field omits an accepted Entry ID"
            ) from exc
        if (
            final["lineup_id"] != accepted["lineup_id"]
            or final["roster_sha256"] != accepted["roster_sha256"]
            or final["internal_player_ids"] != accepted["internal_player_ids"]
            or final["slot_dk_draftable_ids"] != accepted["slot_dk_draftable_ids"]
        ):
            _fail("accepted-to-final roster drift lacks a frozen late-swap transition")
        paid_results.append(
            {
                "entry_index": accepted["entry_index"],
                "lineup_rank": accepted["lineup_rank"],
                "entry_id": accepted["entry_id"],
                "lineup_id": final["lineup_id"],
                "roster_sha256": final["roster_sha256"],
                "rank": final["rank"],
                "points_micropoints": _signed_integer(
                    final["points_micropoints"], label="final fantasy points"
                ),
                "cash_payout_micro": final["cash_payout_micro"],
                "ticket_destinations": final["ticket_destinations"],
            }
        )
    payout_reconciliation = _reconcile_source_payouts(
        normalized["rows"], manifest["payout_ladder"]
    )
    final_size = int(normalized["parsed_final_field_size"])
    capacity = int(manifest["contest"]["advertised_field_capacity"])
    if (
        final_size < capacity
        and manifest["contest"]["underfill_authority"]
        != "guaranteed-source-ladder"
    ):
        _fail("underfill lacks exact guarantee/rule authority")
    return seal_semantic_artifact(
        {
            "schema_version": SETTLEMENT_SCHEMA,
            "contest_role": pin.role,
            "contest_id": pin.contest_id,
            "draft_group_id": EXPECTED_DRAFT_GROUP_ID,
            "settlement_frozen_at": frozen_text,
            "allocation": _ref(
                pins.allocation_identity, pins.allocation_semantic_sha256
            ),
            "acceptance_root": root_ref,
            "manifest": manifest_ref,
            "acceptance": acceptance_ref,
            "normalized_standings": normalized_ref,
            "raw_standings_identity": normalized["raw_standings_identity"],
            "final_field_evidence": normalized["final_field_evidence"],
            "player_bridge": normalized["player_bridge"],
            "advertised_field_capacity": capacity,
            "observed_final_field_size": final_size,
            "underfilled_vs_advertised": final_size < capacity,
            "payout_reconciliation": payout_reconciliation,
            "paid_results": paid_results,
            "correction_lineage": {
                "revision": 0,
                "predecessor": None,
                "reason": "initial",
            },
        }
    )


def validate_week1_settlement_v2(
    value: object,
    *,
    store: ImmutableObjectStore,
    acquisition_authority: AuthenticatedProviderAcquisitionAuthority,
    pins: A5CapturePins,
) -> dict[str, object]:
    row = validate_semantic_artifact(value, label="settlement")
    _exact(
        row,
        {
            "schema_version",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "settlement_frozen_at",
            "allocation",
            "acceptance_root",
            "manifest",
            "acceptance",
            "normalized_standings",
            "raw_standings_identity",
            "final_field_evidence",
            "player_bridge",
            "advertised_field_capacity",
            "observed_final_field_size",
            "underfilled_vs_advertised",
            "payout_reconciliation",
            "paid_results",
            "correction_lineage",
            "semantic_sha256",
        },
        label="settlement",
    )
    if row["schema_version"] != SETTLEMENT_SCHEMA:
        _fail("settlement schema differs")
    rebuilt = build_week1_settlement_v2(
        store=store,
        acquisition_authority=acquisition_authority,
        pins=pins,
        acceptance_root=row["acceptance_root"],
        normalized_standings=row["normalized_standings"],
        settlement_frozen_at=row["settlement_frozen_at"],
    )
    if row != rebuilt:
        _fail("settlement differs from exact complete-field evidence")
    return row


# Old v1 builders accepted independent in-memory rows and caller truth booleans.
# Keep explicit failures instead of silently retaining that unsafe API.
def build_week1_entry_acceptance_v1(**_: object) -> dict[str, object]:
    _fail("acceptance/v1 is retired; use exact-reopen acceptance/v2")


def validate_week1_entry_acceptance_v1(*_: object, **__: object) -> dict[str, object]:
    _fail("acceptance/v1 is retired; use exact-reopen acceptance/v2")


def build_week1_acceptance_root_v1(**_: object) -> dict[str, object]:
    _fail("acceptance-root/v1 is retired; use exact-reopen acceptance-root/v2")


def validate_week1_acceptance_root_v1(*_: object, **__: object) -> dict[str, object]:
    _fail("acceptance-root/v1 is retired; use exact-reopen acceptance-root/v2")


def build_week1_settlement_v1(**_: object) -> dict[str, object]:
    _fail("settlement/v1 is retired; use exact-reopen settlement/v2")


def validate_week1_settlement_v1(*_: object, **__: object) -> dict[str, object]:
    _fail("settlement/v1 is retired; use exact-reopen settlement/v2")
