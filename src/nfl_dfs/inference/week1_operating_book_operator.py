"""Create-once publication boundary for the 2026 Week-1 operating book.

The generation-shadow terminal envelope is the only accepted source.  It is
read by exact object identity, converted to the frozen K80/K100 roster book,
published before slate lock, and then reopened in a separate store read.  No
outcome, cap-4, Tier-3, contest-entry, UI, or policy-mutation behavior lives at
this boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import re
from typing import Final

from .generation_exposure import canonical_sha256
from . import prospective_generation_shadow_evaluation as shadow_evaluation
from .prospective_generation_shadow_operator import (
    ImmutableObjectStore,
    _assert_created_before,
    _load_prelock_envelope,
    _prelock_uri,
    _publish_json,
    _read_json,
    _timestamp,
)
from .week1_operating_book import WEEK1_DEADLINE_UTC
from .week1_operating_roster_materializer import (
    TERMINAL_AUTHORITY_MODE,
    build_week1_operating_roster_materialization_v1,
    validate_week1_operating_roster_materialization_v1,
)


SCHEMA_VERSION: Final = "week1-operating-book-publication/v1"
SUPPORTED_K: Final = (80, 100)
WEEK1_SEASON: Final = 2026
WEEK1_WEEK: Final = 1
WEEK1_DRAFT_GROUP_ID: Final = "151307"
WEEK1_SLATE_ID: Final = f"dk-{WEEK1_DRAFT_GROUP_ID}"
_SLATE_CONTEXT_FIELDS: Final = {
    "season",
    "week",
    "draft_group_id",
    "run_id",
    "code_sha",
    "slate_lock_at",
}

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class Week1OperatingBookOperatorError(RuntimeError):
    """The exact pre-lock publication chain failed closed."""


def _fail(message: str) -> None:
    raise Week1OperatingBookOperatorError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be a string-keyed mapping")
    return dict(value)


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        identity = shadow_evaluation.normalize_object_identity_v1(
            value, label=label
        )
        _prelock_uri(identity["uri"], label=label)
        return identity
    except Exception as exc:
        raise Week1OperatingBookOperatorError(
            f"{label} differs"
        ) from exc


def _timestamp_text(value: object, *, label: str) -> str:
    try:
        return _timestamp(value, label=label).isoformat()
    except Exception as exc:
        raise Week1OperatingBookOperatorError(
            f"{label} differs"
        ) from exc


def validate_week1_operating_book_publication_v1(
    value: object,
) -> dict[str, object]:
    """Validate the self-contained publication receipt."""

    receipt = _mapping(value, label="Week-1 publication receipt")
    fields = {
        "schema_version",
        "complete",
        "k",
        "source_terminal_prelock_envelope_identity",
        "source_terminal_prelock_root_identity",
        "source_storage_created_at",
        "source_root_storage_created_at",
        "slate_id",
        "target_uri",
        "materialization_identity",
        "materialization_storage_created_at",
        "materialization_sha256",
        "suite_authority_sha256",
        "operating_contract_sha256",
        "adapter_envelope_sha256",
        "selected_lineup_ids_sha256",
        "source_membership_books_sha256",
        "slate_context",
        "lock_at",
        "create_once",
        "independent_exact_reopen",
        "cap4_used",
        "tier3_used",
        "uses_realized_outcomes",
        "outcome_fields",
        "publication_receipt_sha256",
    }
    if set(receipt) != fields:
        _fail("Week-1 publication receipt fields differ")
    retained_hash = _digest(
        receipt.get("publication_receipt_sha256"),
        label="publication receipt SHA-256",
    )
    unhashed = dict(receipt)
    unhashed.pop("publication_receipt_sha256")
    if retained_hash != canonical_sha256(unhashed):
        _fail("Week-1 publication receipt hash differs")

    source_identity = _identity(
        receipt.get("source_terminal_prelock_envelope_identity"),
        label="source terminal envelope identity",
    )
    root_identity = _identity(
        receipt.get("source_terminal_prelock_root_identity"),
        label="source terminal root identity",
    )
    output_identity = _identity(
        receipt.get("materialization_identity"),
        label="materialization identity",
    )
    k = receipt.get("k")
    context = _mapping(receipt.get("slate_context"), label="slate context")
    lock_at = _timestamp(
        receipt.get("lock_at"), label="publication slate lock"
    )
    source_created = _timestamp(
        receipt.get("source_storage_created_at"),
        label="source storage-created-at",
    )
    root_created = _timestamp(
        receipt.get("source_root_storage_created_at"),
        label="source root storage-created-at",
    )
    output_created = _timestamp(
        receipt.get("materialization_storage_created_at"),
        label="materialization storage-created-at",
    )
    for field in (
        "materialization_sha256",
        "suite_authority_sha256",
        "operating_contract_sha256",
        "adapter_envelope_sha256",
        "selected_lineup_ids_sha256",
        "source_membership_books_sha256",
    ):
        _digest(receipt.get(field), label=field)
    if (
        receipt.get("schema_version") != SCHEMA_VERSION
        or receipt.get("complete") is not True
        or type(k) is not int
        or k not in SUPPORTED_K
        or set(context) != _SLATE_CONTEXT_FIELDS
        or context.get("season") != WEEK1_SEASON
        or context.get("week") != WEEK1_WEEK
        or str(context.get("draft_group_id")) != WEEK1_DRAFT_GROUP_ID
        or context.get("slate_lock_at")
        != _timestamp_text(WEEK1_DEADLINE_UTC, label="Week-1 deadline")
        or receipt.get("slate_id") != WEEK1_SLATE_ID
        or receipt.get("target_uri") != output_identity["uri"]
        or context.get("slate_lock_at") != receipt.get("lock_at")
        or not root_created <= source_created <= output_created < lock_at
        or receipt.get("create_once") is not True
        or receipt.get("independent_exact_reopen") is not True
        or receipt.get("cap4_used") is not False
        or receipt.get("tier3_used") is not False
        or receipt.get("uses_realized_outcomes") is not False
        or receipt.get("outcome_fields") != []
        or len({
            root_identity["uri"], source_identity["uri"], output_identity["uri"]
        }) != 3
    ):
        _fail("Week-1 publication fixed pre-lock law differs")
    return receipt


def publish_week1_operating_book_v1(
    *,
    store: ImmutableObjectStore,
    terminal_prelock_envelope_identity: Mapping[str, object],
    target_uri: str,
    k: int,
    observed_at: datetime | str | None = None,
) -> dict[str, object]:
    """Publish and independently reopen one exact Week-1 operating book."""

    if type(k) is not int or k not in SUPPORTED_K:
        _fail(f"K must be one of {SUPPORTED_K}")
    uri = _prelock_uri(target_uri, label="Week-1 operating book")
    try:
        source, root = _load_prelock_envelope(
            store, terminal_prelock_envelope_identity
        )
    except Exception as exc:
        raise Week1OperatingBookOperatorError(
            "terminal prelock envelope/root exact reopen failed"
        ) from exc
    lock_at = root["lock_at"]
    try:
        _assert_created_before(
            source, lock_at, label="terminal prelock envelope"
        )
    except Exception as exc:
        raise Week1OperatingBookOperatorError(
            "terminal prelock envelope timing differs"
        ) from exc
    suite = _mapping(root.get("suite_authority"), label="root suite authority")
    manifest = _mapping(suite.get("manifest"), label="suite manifest")
    expected_lock = _timestamp_text(
        WEEK1_DEADLINE_UTC, label="Week-1 deadline"
    )
    if (
        root.get("season") != WEEK1_SEASON
        or root.get("week") != WEEK1_WEEK
        or root.get("slate_id") != WEEK1_SLATE_ID
        or lock_at != expected_lock
        or manifest.get("season") != WEEK1_SEASON
        or manifest.get("week") != WEEK1_WEEK
        or str(manifest.get("draft_group_id")) != WEEK1_DRAFT_GROUP_ID
        or manifest.get("slate_lock_at") != expected_lock
    ):
        _fail("terminal authority is not the frozen 2026 Week-1 main slate")
    preflight_time = (
        datetime.now(timezone.utc)
        if observed_at is None
        else _timestamp(observed_at, label="publication preflight time")
    )
    if preflight_time >= _timestamp(lock_at, label="slate lock"):
        _fail("Week-1 operating book cannot be published at or after lock")

    try:
        materialization = build_week1_operating_roster_materialization_v1(
            k=k, terminal_prelock_root=source["value"]
        )
        validate_week1_operating_roster_materialization_v1(materialization)
    except Exception as exc:
        raise Week1OperatingBookOperatorError(
            "Week-1 roster materialization failed"
        ) from exc
    context = _mapping(
        materialization.get("slate_context"), label="materialized slate context"
    )
    if context.get("slate_lock_at") != lock_at:
        _fail("materialization and terminal slate locks differ")

    try:
        publication = _publish_json(
            store,
            uri=uri,
            value=materialization,
            label="Week-1 operating-book materialization",
            not_before=source["created_at"],
            must_precede=lock_at,
        )
        reopened = _read_json(
            store,
            identity=publication["identity"],
            label="Week-1 operating-book materialization",
        )
    except Week1OperatingBookOperatorError:
        raise
    except Exception as exc:
        raise Week1OperatingBookOperatorError(
            "Week-1 operating-book storage publication/reopen failed"
        ) from exc
    if reopened["value"] != materialization:
        _fail("independent operating-book reopen differs from publication")
    try:
        validate_week1_operating_roster_materialization_v1(reopened["value"])
    except Exception as exc:
        raise Week1OperatingBookOperatorError(
            "independent operating-book reopen validation failed"
        ) from exc

    adapter = _mapping(
        materialization.get("adapter_envelope"), label="adapter envelope"
    )
    compositor = _mapping(
        adapter.get("compositor_receipt"), label="compositor receipt"
    )
    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "complete": True,
        "k": k,
        "source_terminal_prelock_envelope_identity": source["identity"],
        "source_terminal_prelock_root_identity": source["value"]["identity"],
        "source_storage_created_at": _timestamp_text(
            source["created_at"], label="source storage-created-at"
        ),
        "source_root_storage_created_at": _timestamp_text(
            source["value"]["storage_created_at"],
            label="source root storage-created-at",
        ),
        "slate_id": root["slate_id"],
        "target_uri": uri,
        "materialization_identity": publication["identity"],
        "materialization_storage_created_at": _timestamp_text(
            publication["created_at"],
            label="materialization storage-created-at",
        ),
        "materialization_sha256": materialization["materialization_sha256"],
        "suite_authority_sha256": materialization[
            "suite_authority_sha256"
        ],
        "operating_contract_sha256": compositor["contract_sha256"],
        "adapter_envelope_sha256": materialization[
            "adapter_envelope_sha256"
        ],
        "selected_lineup_ids_sha256": materialization[
            "selected_lineup_ids_sha256"
        ],
        "source_membership_books_sha256": materialization[
            "source_membership_books_sha256"
        ],
        "slate_context": context,
        "lock_at": lock_at,
        "create_once": True,
        "independent_exact_reopen": True,
        "cap4_used": False,
        "tier3_used": False,
        "uses_realized_outcomes": False,
        "outcome_fields": [],
    }
    body["publication_receipt_sha256"] = canonical_sha256(body)
    return validate_week1_operating_book_publication_v1(body)


def read_week1_operating_book_v1(
    *,
    store: ImmutableObjectStore,
    materialization_identity: Mapping[str, object],
) -> dict[str, object]:
    """Exact-reopen and rederive the sole Week-1 UI/CSV authority.

    The materialization identity is necessary but not sufficient.  The
    deployed read also exact-opens its bound terminal-root generation,
    validates that root body, reconstructs the terminal envelope from trusted
    root metadata, and deterministically rebuilds the complete materialization.
    This makes a valid source terminal an independently reopened predecessor
    of every UI/CSV response instead of trusting a self-consistent output
    object in isolation.
    """

    try:
        receipt = _read_json(
            store,
            identity=materialization_identity,
            label="Week-1 operating-book materialization",
        )
        identity = _identity(
            receipt["identity"], label="Week-1 materialization identity"
        )
        materialization = validate_week1_operating_roster_materialization_v1(
            receipt["value"]
        )
    except Exception as exc:
        raise Week1OperatingBookOperatorError(
            "Week-1 operating-book exact read failed"
        ) from exc
    context = _mapping(
        materialization.get("slate_context"), label="materialized slate context"
    )
    expected_lock = _timestamp_text(
        WEEK1_DEADLINE_UTC, label="Week-1 deadline"
    )
    if (
        materialization.get("authority_mode") != TERMINAL_AUTHORITY_MODE
        or set(context) != _SLATE_CONTEXT_FIELDS
        or context.get("season") != WEEK1_SEASON
        or context.get("week") != WEEK1_WEEK
        or str(context.get("draft_group_id")) != WEEK1_DRAFT_GROUP_ID
        or context.get("slate_lock_at") != expected_lock
    ):
        _fail("materialization is not the frozen 2026 Week-1 main slate")
    created_at = _timestamp_text(
        receipt["created_at"], label="materialization storage-created-at"
    )
    materialization_created = _timestamp(
        created_at, label="materialization storage-created-at"
    )
    if materialization_created >= _timestamp(
        expected_lock, label="Week-1 deadline"
    ):
        _fail("materialization was not created before the Week-1 deadline")

    binding = _mapping(
        materialization.get("terminal_root_binding"),
        label="materialization terminal-root binding",
    )
    try:
        root_identity = _identity(
            binding.get("terminal_prelock_object_identity"),
            label="materialization terminal-root identity",
        )
        root_receipt = _read_json(
            store,
            identity=root_identity,
            label="materialization-bound terminal prelock root",
        )
        root = shadow_evaluation.validate_terminal_prelock_root_body_v1(
            root_receipt["value"]
        )
        rebuilt_envelope = shadow_evaluation.bind_terminal_prelock_root_v1(
            root=root,
            uri=str(root_identity["uri"]),
            generation=str(root_identity["generation"]),
            storage_created_at=root_receipt["created_at"],
        )
        rebuilt_materialization = (
            build_week1_operating_roster_materialization_v1(
                k=int(materialization["k"]),
                terminal_prelock_root=rebuilt_envelope,
            )
        )
        validate_week1_operating_roster_materialization_v1(
            rebuilt_materialization
        )
    except Exception as exc:
        raise Week1OperatingBookOperatorError(
            "Week-1 terminal-root exact reopen/rebuild failed"
        ) from exc
    root_created = _timestamp(
        root_receipt["created_at"], label="terminal-root storage-created-at"
    )
    if (
        root_identity["uri"] == identity["uri"]
        or root.get("terminal_prelock_root_sha256")
        != binding.get("terminal_prelock_root_sha256")
        or rebuilt_envelope.get("terminal_prelock_envelope_sha256")
        != binding.get("terminal_prelock_envelope_sha256")
        or root.get("suite_authority_sha256")
        != materialization.get("suite_authority_sha256")
        or root.get("season") != WEEK1_SEASON
        or root.get("week") != WEEK1_WEEK
        or root.get("slate_id") != WEEK1_SLATE_ID
        or root.get("lock_at") != expected_lock
        or not root_created < materialization_created
        or rebuilt_materialization != materialization
    ):
        _fail("materialization differs from its exact terminal-root authority")
    return {
        "identity": identity,
        "storage_created_at": created_at,
        "materialization": materialization,
    }


__all__ = [
    "SCHEMA_VERSION",
    "SUPPORTED_K",
    "Week1OperatingBookOperatorError",
    "publish_week1_operating_book_v1",
    "read_week1_operating_book_v1",
    "validate_week1_operating_book_publication_v1",
]
