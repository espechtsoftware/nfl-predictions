"""Create-once storage boundary for the Week-1 D800/D400 adopted pair.

The pair contract fixes the scientific recipe and artifact lineage.  This
module supplies the deliberately smaller operational boundary around it:

* one canonical, outcome-free DraftKings book payload for each arm;
* generation-pinned create-once GCS publication;
* an immutable adopted-pair manifest built only from returned object
  identities; and
* an independent exact reopen of the manifest, both books, and every
  additional source artifact exposed by the pair contract.

Only universal DraftKings Classic mechanics are checked here.  The book
validator does not inspect teams, opponents, stacks, bring-backs, salary
floors, ownership, or any other strategy law.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
import hashlib
import re
from typing import Final, Protocol

from .generation_exposure import canonical_sha256
from . import week1_adopted_pair as adopted_pair
from .prospective_generation_shadow_evaluation import canonical_json_bytes_v1
from .prospective_generation_shadow_operator import (
    GCSImmutableObjectStore as _GenerationShadowGCSStore,
    _assert_created_before,
    _prelock_uri,
    _publish_json,
    _read_json,
    _read_raw,
    _timestamp,
    _timestamp_text,
)


BOOK_SCHEMA_VERSION: Final = "week1-adopted-book/v1"
PUBLICATION_SCHEMA_VERSION: Final = "week1-adopted-pair-publication/v1"
DK_SLOT_ORDER: Final = (
    "QB",
    "RB",
    "RB",
    "WR",
    "WR",
    "WR",
    "TE",
    "FLEX",
    "DST",
)

_BOOK_FIELDS: Final = frozenset({
    "schema_version",
    "arm_id",
    "complete",
    "player_bridge_identity",
    "player_bridge",
    "slot_order",
    "roster_ids",
    "roster_ids_sha256",
    "lineups",
    "book_sha256",
})
_BRIDGE_IDENTITY_FIELDS: Final = frozenset({"id", "sha256"})
_BRIDGE_ROW_FIELDS: Final = frozenset({
    "player_id",
    "position",
    "team",
    "salary",
})
_LINEUP_FIELDS: Final = frozenset({
    "lineup_id",
    "player_ids",
    "slots",
    "salary",
})
_SLOT_FIELDS: Final = frozenset({"slot", "player_id"})
_PUBLICATION_FIELDS: Final = frozenset({
    "schema_version",
    "complete",
    "manifest_identity",
    "paid_book_identity",
    "shadow_book_identity",
    "manifest_storage_created_at",
    "paid_book_storage_created_at",
    "shadow_book_storage_created_at",
    "independent_exact_reopen",
    "publication_sha256",
})
_OBJECT_IDENTITY_FIELDS: Final = frozenset({
    "uri",
    "generation",
    "sha256",
    "bytes",
})
_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE", "DST"})
_FLEX_POSITIONS: Final = frozenset({"RB", "WR", "TE"})
_PLAYER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_TEAM_ID = re.compile(r"[A-Z0-9]{2,5}\Z")
_LINEUP_ID = re.compile(r"lineup-v1-[0-9a-f]{64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_OUTCOME_FIELD_FRAGMENTS: Final = (
    "actual",
    "outcome",
    "realized",
    "score",
    "payout",
    "winnings",
    "standing",
    "settlement",
    "placement",
    "finish_position",
)


class Week1AdoptedPairOperatorError(RuntimeError):
    """Publication or exact reopen of the adopted pair failed closed."""


def _fail(message: str) -> None:
    raise Week1AdoptedPairOperatorError(message)


class ImmutableObjectStore(Protocol):
    """Minimal create-once and generation-pinned store protocol."""

    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> Mapping[str, object]: ...

    def read_exact(
        self, *, identity: Mapping[str, object]
    ) -> Mapping[str, object]: ...


class GCSImmutableObjectStore(_GenerationShadowGCSStore):
    """The shared generation-pinned GCS implementation for this boundary."""


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed mapping")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
        value, Sequence
    ):
        _fail(f"{label} must be an ordered sequence")
    return list(value)


def _exact_fields(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    actual = set(value)
    if actual != expected:
        _fail(
            f"{label} fields differ: missing={sorted(expected - actual)} "
            f"unexpected={sorted(actual - expected)}"
        )


def _text(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be a nonempty canonical string")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _positive_integer(value: object, *, label: str) -> int:
    if type(value) is not int or value < 1:
        _fail(f"{label} must be a positive integer")
    return value


def _player_id(value: object, *, label: str) -> str:
    if type(value) is not str or _PLAYER_ID.fullmatch(value) is None:
        _fail(f"{label} must be a canonical player ID")
    return value


def _lineup_id(value: object, *, label: str) -> str:
    if type(value) is not str or _LINEUP_ID.fullmatch(value) is None:
        _fail(f"{label} must be a canonical lineup-v1 ID")
    return value


def _team_id(value: object, *, label: str) -> str:
    if type(value) is not str or _TEAM_ID.fullmatch(value) is None:
        _fail(f"{label} must be a canonical team abbreviation")
    return value


def _reject_outcome_fields(value: object, *, path: str = "book") -> None:
    """Reject outcome-bearing keys at any depth before schema normalization."""

    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            key = str(raw_key).lower().replace("-", "_")
            if any(fragment in key for fragment in _OUTCOME_FIELD_FRAGMENTS):
                _fail(f"{path}.{raw_key} is an outcome field")
            _reject_outcome_fields(nested, path=f"{path}.{raw_key}")
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for ordinal, nested in enumerate(value):
            _reject_outcome_fields(nested, path=f"{path}[{ordinal}]")


def _bridge_identity(value: object) -> dict[str, object]:
    identity = _mapping(value, label="player bridge identity")
    _exact_fields(
        identity, _BRIDGE_IDENTITY_FIELDS, label="player bridge identity"
    )
    retained = {
        "id": _text(identity.get("id"), label="player bridge identity id"),
        "sha256": _digest(
            identity.get("sha256"), label="player bridge identity SHA-256"
        ),
    }
    if retained["id"] != "player-bridge/v1":
        _fail("player bridge identity differs from the adopted pair")
    return retained


def _player_bridge(value: object) -> list[dict[str, object]]:
    rows = _sequence(value, label="player bridge")
    retained: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"player bridge[{ordinal}]")
        _exact_fields(
            row, _BRIDGE_ROW_FIELDS, label=f"player bridge[{ordinal}]"
        )
        position = _text(
            row.get("position"), label=f"player bridge[{ordinal}] position"
        )
        if position not in _POSITIONS:
            _fail(f"player bridge[{ordinal}] position is not DK eligible")
        retained.append({
            "player_id": _player_id(
                row.get("player_id"),
                label=f"player bridge[{ordinal}] player ID",
            ),
            "position": position,
            "team": _team_id(
                row.get("team"), label=f"player bridge[{ordinal}] team"
            ),
            "salary": _positive_integer(
                row.get("salary"), label=f"player bridge[{ordinal}] salary"
            ),
        })
    player_ids = [str(row["player_id"]) for row in retained]
    if not retained or len(set(player_ids)) != len(player_ids):
        _fail("player bridge is empty or repeats a player ID")
    if player_ids != sorted(player_ids):
        _fail("player bridge must be ordered by canonical player ID")
    return retained


def _lineups(
    value: object, *, bridge: Mapping[str, Mapping[str, object]]
) -> list[dict[str, object]]:
    rows = _sequence(value, label="adopted book lineups")
    retained: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"lineup[{ordinal}]")
        _exact_fields(row, _LINEUP_FIELDS, label=f"lineup[{ordinal}]")
        lineup_id = _lineup_id(
            row.get("lineup_id"), label=f"lineup[{ordinal}] ID"
        )
        player_ids = [
            _player_id(item, label=f"lineup[{ordinal}] player ID")
            for item in _sequence(
                row.get("player_ids"), label=f"lineup[{ordinal}] player IDs"
            )
        ]
        if (
            len(player_ids) != len(DK_SLOT_ORDER)
            or len(set(player_ids)) != len(DK_SLOT_ORDER)
            or player_ids != sorted(player_ids)
        ):
            _fail(
                f"lineup[{ordinal}] must bind nine unique sorted player IDs"
            )
        expected_lineup_id = f"lineup-v1-{canonical_sha256(player_ids)}"
        if lineup_id != expected_lineup_id:
            _fail(f"lineup[{ordinal}] ID does not bind its player IDs")

        raw_slots = _sequence(
            row.get("slots"), label=f"lineup[{ordinal}] slots"
        )
        if len(raw_slots) != len(DK_SLOT_ORDER):
            _fail(f"lineup[{ordinal}] must bind exact DK slot order")
        slots: list[dict[str, object]] = []
        for slot_ordinal, (raw_slot, expected_slot) in enumerate(
            zip(raw_slots, DK_SLOT_ORDER, strict=True)
        ):
            slot = _mapping(
                raw_slot, label=f"lineup[{ordinal}] slot[{slot_ordinal}]"
            )
            _exact_fields(
                slot,
                _SLOT_FIELDS,
                label=f"lineup[{ordinal}] slot[{slot_ordinal}]",
            )
            slot_name = _text(
                slot.get("slot"),
                label=f"lineup[{ordinal}] slot[{slot_ordinal}] name",
            )
            slot_player_id = _player_id(
                slot.get("player_id"),
                label=f"lineup[{ordinal}] slot[{slot_ordinal}] player ID",
            )
            if slot_name != expected_slot:
                _fail(f"lineup[{ordinal}] DK slot order differs")
            player = bridge.get(slot_player_id)
            if player is None:
                _fail(f"lineup[{ordinal}] player is absent from frozen bridge")
            position = str(player["position"])
            if (
                slot_name == "FLEX" and position not in _FLEX_POSITIONS
            ) or (
                slot_name != "FLEX" and position != slot_name
            ):
                _fail(f"lineup[{ordinal}] player is ineligible for {slot_name}")
            slots.append({"slot": slot_name, "player_id": slot_player_id})
        slot_player_ids = [str(slot["player_id"]) for slot in slots]
        if len(set(slot_player_ids)) != 9 or set(slot_player_ids) != set(player_ids):
            _fail(f"lineup[{ordinal}] slot membership differs from player IDs")

        salary = _positive_integer(
            row.get("salary"), label=f"lineup[{ordinal}] salary"
        )
        exact_salary = sum(int(bridge[player_id]["salary"]) for player_id in player_ids)
        if salary != exact_salary or salary > 50_000:
            _fail(f"lineup[{ordinal}] salary differs or exceeds the DK cap")
        teams = Counter(str(bridge[player_id]["team"]) for player_id in player_ids)
        if len(teams) < 2 or max(teams.values()) > 8:
            _fail(f"lineup[{ordinal}] violates the DK team limit")
        retained.append({
            "lineup_id": lineup_id,
            "player_ids": player_ids,
            "slots": slots,
            "salary": salary,
        })

    lineup_ids = [str(row["lineup_id"]) for row in retained]
    if len(lineup_ids) != adopted_pair.EXACT_ENTRIES:
        _fail(f"adopted book must contain exact-{adopted_pair.EXACT_ENTRIES}")
    if len(set(lineup_ids)) != adopted_pair.EXACT_ENTRIES:
        _fail("adopted book repeats a lineup ID")
    return retained


def _normalized_book(value: object) -> dict[str, object]:
    _reject_outcome_fields(value)
    book = _mapping(value, label="Week-1 adopted book")
    _exact_fields(book, _BOOK_FIELDS, label="Week-1 adopted book")
    arm_id = book.get("arm_id")
    if (
        book.get("schema_version") != BOOK_SCHEMA_VERSION
        or arm_id not in {adopted_pair.PAID_ARM_ID, adopted_pair.SHADOW_ARM_ID}
        or book.get("complete") is not True
        or book.get("slot_order") != list(DK_SLOT_ORDER)
    ):
        _fail("adopted book schema/arm/fixed DK slot order differs")
    bridge = _player_bridge(book.get("player_bridge"))
    bridge_identity = _bridge_identity(book.get("player_bridge_identity"))
    if bridge_identity["sha256"] != canonical_sha256(bridge):
        _fail("player bridge identity does not bind the frozen bridge")
    bridge_by_id = {str(row["player_id"]): row for row in bridge}
    lineups = _lineups(book.get("lineups"), bridge=bridge_by_id)
    roster_ids = [str(row["lineup_id"]) for row in lineups]
    if book.get("roster_ids") != roster_ids:
        _fail("book roster ID order differs from lineup order")
    if book.get("roster_ids_sha256") != canonical_sha256(roster_ids):
        _fail("book roster ID order SHA-256 differs")
    book_sha256 = _digest(
        book.get("book_sha256"), label="adopted book SHA-256"
    )
    return {
        "schema_version": BOOK_SCHEMA_VERSION,
        "arm_id": arm_id,
        "complete": True,
        "player_bridge_identity": bridge_identity,
        "player_bridge": bridge,
        "slot_order": list(DK_SLOT_ORDER),
        "roster_ids": roster_ids,
        "roster_ids_sha256": canonical_sha256(roster_ids),
        "lineups": lineups,
        "book_sha256": book_sha256,
    }


def validate_week1_adopted_book_v1(value: object) -> dict[str, object]:
    """Validate and normalize one canonical, DK-legal exact-K80 book."""

    book = _normalized_book(value)
    retained_hash = book.pop("book_sha256")
    if retained_hash != canonical_sha256(book):
        _fail("adopted book SHA-256 differs")
    book["book_sha256"] = retained_hash
    return book


def build_week1_adopted_book_v1(
    *,
    arm_id: str,
    player_bridge_identity: object,
    player_bridge: object,
    lineups: object,
) -> dict[str, object]:
    """Seal one ordered lineup book using only frozen DK player facts."""

    bridge = _player_bridge(player_bridge)
    bridge_identity = _bridge_identity(player_bridge_identity)
    if bridge_identity["sha256"] != canonical_sha256(bridge):
        _fail("player bridge identity does not bind the frozen bridge")
    bridge_by_id = {str(row["player_id"]): row for row in bridge}
    retained_lineups = _lineups(lineups, bridge=bridge_by_id)
    roster_ids = [str(row["lineup_id"]) for row in retained_lineups]
    body: dict[str, object] = {
        "schema_version": BOOK_SCHEMA_VERSION,
        "arm_id": arm_id,
        "complete": True,
        "player_bridge_identity": bridge_identity,
        "player_bridge": bridge,
        "slot_order": list(DK_SLOT_ORDER),
        "roster_ids": roster_ids,
        "roster_ids_sha256": canonical_sha256(roster_ids),
        "lineups": retained_lineups,
    }
    body["book_sha256"] = canonical_sha256(body)
    return validate_week1_adopted_book_v1(body)


def _object_identity(value: object, *, label: str) -> dict[str, object]:
    identity = _mapping(value, label=label)
    _exact_fields(identity, _OBJECT_IDENTITY_FIELDS, label=label)
    try:
        uri = _prelock_uri(identity.get("uri"), label=label)
    except Exception as exc:
        raise Week1AdoptedPairOperatorError(f"{label} URI differs") from exc
    if not uri.startswith(adopted_pair.GOVERNED_ARTIFACT_PREFIX):
        _fail(f"{label} URI is outside the governed Week-1 prefix")
    generation = identity.get("generation")
    if type(generation) not in {str, int}:
        _fail(f"{label} generation must be a positive decimal")
    generation_text = str(generation)
    if not generation_text.isdigit() or int(generation_text) < 1:
        _fail(f"{label} generation must be a positive decimal")
    return {
        "uri": uri,
        "generation": generation_text,
        "sha256": _digest(identity.get("sha256"), label=f"{label} SHA-256"),
        "bytes": _positive_integer(identity.get("bytes"), label=f"{label} bytes"),
    }


def _arm_metadata(value: object, *, label: str) -> dict[str, object]:
    metadata = _mapping(value, label=label)
    if "book_artifact" in metadata or "roster_ids" in metadata:
        _fail(f"{label} must omit publisher-owned book fields")
    return metadata


def _bound_arm(
    metadata: Mapping[str, object],
    *,
    artifact: Mapping[str, object],
    roster_ids: Sequence[str],
) -> dict[str, object]:
    return {
        **dict(metadata),
        "book_artifact": dict(artifact),
        "roster_ids": list(roster_ids),
    }


def _source_artifact_identities(
    arm: Mapping[str, object], *, label: str
) -> list[tuple[str, dict[str, object]]]:
    sources: list[tuple[str, dict[str, object]]] = []
    for field, value in arm.items():
        if field.endswith("_artifact") and field != "book_artifact":
            sources.append((field, _object_identity(value, label=f"{label} {field}")))
    return sources


def _reopen_source_artifacts(
    store: ImmutableObjectStore,
    *,
    arm: Mapping[str, object],
    label: str,
    frozen_at: str,
    lock_at: str,
) -> None:
    for field, identity in _source_artifact_identities(arm, label=label):
        try:
            receipt = _read_raw(
                store, identity=identity, label=f"{label} {field}"
            )
            _assert_created_before(
                receipt, lock_at, label=f"{label} {field}"
            )
            if _timestamp(
                receipt["created_at"], label=f"{label} {field} creation time"
            ) > _timestamp(frozen_at, label="pair frozen-at"):
                _fail(f"{label} {field} was created after the pair freeze")
        except Exception as exc:
            raise Week1AdoptedPairOperatorError(
                f"{label} {field} exact reopen failed"
            ) from exc


def _read_book(
    store: ImmutableObjectStore,
    *,
    identity: Mapping[str, object],
    arm_id: str,
    frozen_at: str,
    lock_at: str,
) -> dict[str, object]:
    try:
        receipt = _read_json(
            store, identity=identity, label=f"{arm_id} adopted book"
        )
        _assert_created_before(receipt, lock_at, label=f"{arm_id} adopted book")
        if _timestamp(
            receipt["created_at"], label=f"{arm_id} book creation time"
        ) < _timestamp(frozen_at, label="pair frozen-at"):
            _fail(f"{arm_id} adopted book predates the pair freeze")
        book = validate_week1_adopted_book_v1(receipt["value"])
    except Exception as exc:
        raise Week1AdoptedPairOperatorError(
            f"{arm_id} adopted-book exact reopen failed"
        ) from exc
    if book["arm_id"] != arm_id:
        _fail(f"{arm_id} artifact contains another arm")
    return {**receipt, "book": book}


def read_week1_adopted_pair_v1(
    *,
    store: ImmutableObjectStore,
    manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    """Exact-reopen the manifest, books, and every bound source artifact."""

    expected_manifest_identity = _object_identity(
        manifest_identity, label="Week-1 adopted-pair manifest"
    )
    try:
        manifest_receipt = _read_json(
            store,
            identity=expected_manifest_identity,
            label="Week-1 adopted-pair manifest",
        )
        manifest = adopted_pair.validate_week1_adopted_pair_v1(
            manifest_receipt["value"]
        )
        lock_at = str(manifest["authority"]["lock_utc"])
        frozen_at = str(manifest["authority"]["frozen_at"])
        _assert_created_before(
            manifest_receipt, lock_at, label="Week-1 adopted-pair manifest"
        )
        if _timestamp(
            manifest_receipt["created_at"], label="manifest creation time"
        ) < _timestamp(frozen_at, label="pair frozen-at"):
            _fail("Week-1 adopted-pair manifest predates the pair freeze")
    except Exception as exc:
        raise Week1AdoptedPairOperatorError(
            "Week-1 adopted-pair manifest exact reopen failed"
        ) from exc

    books: dict[str, dict[str, object]] = {}
    for role, arm_id in (
        ("paid", adopted_pair.PAID_ARM_ID),
        ("shadow", adopted_pair.SHADOW_ARM_ID),
    ):
        arm = _mapping(manifest[role], label=f"manifest {role} arm")
        book_receipt = _read_book(
            store,
            identity=arm["book_artifact"],
            arm_id=arm_id,
            frozen_at=frozen_at,
            lock_at=lock_at,
        )
        book = book_receipt["book"]
        if (
            book_receipt["identity"] != arm["book_artifact"]
            or book["roster_ids"] != arm["roster_ids"]
            or book["player_bridge_identity"] != arm["player_bridge_identity"]
        ):
            _fail(f"{arm_id} book membership/bridge differs from manifest")
        _reopen_source_artifacts(
            store,
            arm=arm,
            label=arm_id,
            frozen_at=frozen_at,
            lock_at=lock_at,
        )
        books[role] = book_receipt

    manifest_created_at = _timestamp(
        manifest_receipt["created_at"], label="manifest creation time"
    )
    if any(
        _timestamp(
            books[role]["created_at"], label=f"{role} book creation time"
        ) > manifest_created_at
        for role in ("paid", "shadow")
    ):
        _fail("Week-1 adopted-pair manifest predates a bound book")

    if (
        books["paid"]["book"]["player_bridge"]
        != books["shadow"]["book"]["player_bridge"]
    ):
        _fail("paid/shadow frozen player bridges differ")

    return {
        "manifest_identity": manifest_receipt["identity"],
        "manifest_storage_created_at": manifest_receipt["created_at"],
        "manifest": manifest,
        "paid_book_identity": books["paid"]["identity"],
        "paid_book_storage_created_at": books["paid"]["created_at"],
        "paid_book": books["paid"]["book"],
        "shadow_book_identity": books["shadow"]["identity"],
        "shadow_book_storage_created_at": books["shadow"]["created_at"],
        "shadow_book": books["shadow"]["book"],
    }


def _dummy_artifact_identity(*, uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def validate_week1_adopted_pair_publication_v1(
    value: object,
) -> dict[str, object]:
    """Validate the compact receipt returned by the create-once publisher."""

    receipt = _mapping(value, label="adopted-pair publication receipt")
    _exact_fields(
        receipt,
        _PUBLICATION_FIELDS,
        label="adopted-pair publication receipt",
    )
    if (
        receipt.get("schema_version") != PUBLICATION_SCHEMA_VERSION
        or receipt.get("complete") is not True
        or receipt.get("independent_exact_reopen") is not True
    ):
        _fail("adopted-pair publication fixed claims differ")
    identities = {
        field: _object_identity(receipt.get(field), label=field)
        for field in (
            "manifest_identity",
            "paid_book_identity",
            "shadow_book_identity",
        )
    }
    if len({identity["uri"] for identity in identities.values()}) != 3:
        _fail("publication receipt object URIs alias")
    created_at = {
        field: _timestamp_text(receipt.get(field), label=field)
        for field in (
            "manifest_storage_created_at",
            "paid_book_storage_created_at",
            "shadow_book_storage_created_at",
        )
    }
    lock_at = _timestamp(
        adopted_pair.WEEK1_LOCK_UTC, label="Week-1 lock"
    )
    parsed_created_at = {
        field: _timestamp(timestamp, label=field)
        for field, timestamp in created_at.items()
    }
    if any(created >= lock_at for created in parsed_created_at.values()):
        _fail("publication receipt contains an object created at/after lock")
    if parsed_created_at["manifest_storage_created_at"] < max(
        parsed_created_at["paid_book_storage_created_at"],
        parsed_created_at["shadow_book_storage_created_at"],
    ):
        _fail("publication manifest predates one of its bound books")
    publication_sha256 = _digest(
        receipt.get("publication_sha256"), label="publication SHA-256"
    )
    normalized: dict[str, object] = {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "complete": True,
        **identities,
        **created_at,
        "independent_exact_reopen": True,
    }
    if publication_sha256 != canonical_sha256(normalized):
        _fail("publication SHA-256 differs")
    normalized["publication_sha256"] = publication_sha256
    return normalized


def publish_week1_adopted_pair_v1(
    *,
    store: ImmutableObjectStore,
    authority: object,
    recipe: object,
    paid_arm_metadata: object,
    shadow_arm_metadata: object,
    paid_book: object,
    shadow_book: object,
    paid_book_uri: str,
    shadow_book_uri: str,
    manifest_uri: str,
    observed_at: datetime | str,
) -> dict[str, object]:
    """Create once, then independently exact-reopen the complete pair."""

    try:
        paid = validate_week1_adopted_book_v1(paid_book)
        shadow = validate_week1_adopted_book_v1(shadow_book)
    except Exception as exc:
        raise Week1AdoptedPairOperatorError(
            "adopted books failed semantic preflight"
        ) from exc
    if (
        paid["arm_id"] != adopted_pair.PAID_ARM_ID
        or shadow["arm_id"] != adopted_pair.SHADOW_ARM_ID
        or paid["player_bridge_identity"] != shadow["player_bridge_identity"]
        or paid["player_bridge"] != shadow["player_bridge"]
    ):
        _fail("paid/shadow book arm or player-bridge authority differs")

    paid_metadata = _arm_metadata(
        paid_arm_metadata, label="D800 paid arm metadata"
    )
    shadow_metadata = _arm_metadata(
        shadow_arm_metadata, label="D400 shadow arm metadata"
    )
    try:
        uris = [
            _prelock_uri(paid_book_uri, label="D800 paid book"),
            _prelock_uri(shadow_book_uri, label="D400 shadow book"),
            _prelock_uri(manifest_uri, label="adopted-pair manifest"),
        ]
        if any(
            not uri.startswith(adopted_pair.GOVERNED_ARTIFACT_PREFIX)
            for uri in uris
        ):
            _fail("publication target is outside the governed Week-1 prefix")
        if len(set(uris)) != 3:
            _fail("paid/shadow/manifest target URIs alias")
        observed = _timestamp(observed_at, label="publication observed-at")
        lock = _timestamp(
            adopted_pair.WEEK1_LOCK_UTC, label="Week-1 lock"
        )
        if observed >= lock:
            _fail("publication observed-at is at or after Week-1 lock")
    except Week1AdoptedPairOperatorError:
        raise
    except Exception as exc:
        raise Week1AdoptedPairOperatorError(
            "publication URI/clock preflight failed"
        ) from exc

    all_targets = set(uris)
    source_uris = {
        identity["uri"]
        for arm, label in (
            (paid_metadata, adopted_pair.PAID_ARM_ID),
            (shadow_metadata, adopted_pair.SHADOW_ARM_ID),
        )
        for _field, identity in _source_artifact_identities(arm, label=label)
    }
    if all_targets & source_uris:
        _fail("publication target aliases a bound source artifact")

    paid_raw = canonical_json_bytes_v1(paid)
    shadow_raw = canonical_json_bytes_v1(shadow)
    dummy_paid = _dummy_artifact_identity(uri=uris[0], raw=paid_raw)
    dummy_shadow = _dummy_artifact_identity(uri=uris[1], raw=shadow_raw)
    try:
        preflight_pair = adopted_pair.build_week1_adopted_pair_v1(
            authority=authority,
            recipe=recipe,
            paid=_bound_arm(
                paid_metadata,
                artifact=dummy_paid,
                roster_ids=paid["roster_ids"],
            ),
            shadow=_bound_arm(
                shadow_metadata,
                artifact=dummy_shadow,
                roster_ids=shadow["roster_ids"],
            ),
        )
    except Exception as exc:
        raise Week1AdoptedPairOperatorError(
            "adopted-pair contract preflight failed"
        ) from exc
    lock_at = str(preflight_pair["authority"]["lock_utc"])
    frozen_at = str(preflight_pair["authority"]["frozen_at"])
    if observed < _timestamp(frozen_at, label="pair frozen-at"):
        _fail("publication observed-at precedes the pair freeze")

    _reopen_source_artifacts(
        store,
        arm=paid_metadata,
        label=adopted_pair.PAID_ARM_ID,
        frozen_at=frozen_at,
        lock_at=lock_at,
    )
    _reopen_source_artifacts(
        store,
        arm=shadow_metadata,
        label=adopted_pair.SHADOW_ARM_ID,
        frozen_at=frozen_at,
        lock_at=lock_at,
    )

    try:
        paid_publication = _publish_json(
            store,
            uri=uris[0],
            value=paid,
            label="D800 paid adopted book",
            not_before=frozen_at,
            must_precede=lock_at,
        )
        shadow_publication = _publish_json(
            store,
            uri=uris[1],
            value=shadow,
            label="D400 shadow adopted book",
            not_before=frozen_at,
            must_precede=lock_at,
        )
        pair = adopted_pair.build_week1_adopted_pair_v1(
            authority=authority,
            recipe=recipe,
            paid=_bound_arm(
                paid_metadata,
                artifact=paid_publication["identity"],
                roster_ids=paid["roster_ids"],
            ),
            shadow=_bound_arm(
                shadow_metadata,
                artifact=shadow_publication["identity"],
                roster_ids=shadow["roster_ids"],
            ),
        )
        manifest_publication = _publish_json(
            store,
            uri=uris[2],
            value=pair,
            label="Week-1 adopted-pair manifest",
            not_before=frozen_at,
            must_precede=lock_at,
        )
        reopened = read_week1_adopted_pair_v1(
            store=store,
            manifest_identity=manifest_publication["identity"],
        )
    except Exception as exc:
        if isinstance(exc, Week1AdoptedPairOperatorError):
            raise
        raise Week1AdoptedPairOperatorError(
            "adopted-pair storage publication/reopen failed"
        ) from exc
    if reopened["manifest"] != pair:
        _fail("independent adopted-pair manifest reopen differs")

    body: dict[str, object] = {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "complete": True,
        "manifest_identity": manifest_publication["identity"],
        "paid_book_identity": paid_publication["identity"],
        "shadow_book_identity": shadow_publication["identity"],
        "manifest_storage_created_at": manifest_publication["created_at"],
        "paid_book_storage_created_at": paid_publication["created_at"],
        "shadow_book_storage_created_at": shadow_publication["created_at"],
        "independent_exact_reopen": True,
    }
    body["publication_sha256"] = canonical_sha256(body)
    return validate_week1_adopted_pair_publication_v1(body)


__all__ = [
    "BOOK_SCHEMA_VERSION",
    "DK_SLOT_ORDER",
    "GCSImmutableObjectStore",
    "ImmutableObjectStore",
    "PUBLICATION_SCHEMA_VERSION",
    "Week1AdoptedPairOperatorError",
    "build_week1_adopted_book_v1",
    "publish_week1_adopted_pair_v1",
    "read_week1_adopted_pair_v1",
    "validate_week1_adopted_book_v1",
    "validate_week1_adopted_pair_publication_v1",
]
