"""Bounded operator for the 2026 prospective generation-shadow program.

The scientific contracts live in
``prospective_generation_shadow_evaluation`` and
``prospective_generation_shadow_field_bridge``.  This module supplies the
missing operational seam around them:

* every authority is a canonical, create-once GCS object;
* every input is reopened by URI *and generation* and checked by bytes and
  SHA-256 before it is consumed;
* the suite manifest/terminal and its five immutable arm bundles are adapted
  directly into the evaluator's terminal pre-lock envelope;
* realized scores must already have been published by an independent scorer
  after lock; this operator only exact-reopens them, with a complete field
  bridge only when all required evidence exists; and
* weekly grades and season evaluations are observations only.  Nothing in
  this module changes production allocation, enables an arm, installs a
  scheduler, or mutates another Cloud Run job.

The module CLI is intentionally default-off.  Every mutating subcommand
requires ``--execute`` and uses one caller-supplied request file.  The pure
functions accept an :class:`ImmutableObjectStore`, which keeps the scientific
ordering testable without cloud access.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Final, Protocol

from . import prospective_generation_shadow_evaluation as evaluation
from . import prospective_generation_shadow_field_bridge as field_bridge
from .recourse_worlds import decode_recourse_world_artifact


PREREGISTRATION_PUBLICATION_SCHEMA: Final = (
    "prospective-generation-shadow-preregistration-publication/v1"
)
SEED_CROSSING_PUBLICATION_SCHEMA: Final = (
    "prospective-generation-shadow-seed-crossing-publication/v1"
)
PRELOCK_PUBLICATION_SCHEMA: Final = (
    "prospective-generation-shadow-prelock-publication/v1"
)
POSTLOCK_PUBLICATION_SCHEMA: Final = (
    "prospective-generation-shadow-postlock-publication/v1"
)
EVALUATION_PUBLICATION_SCHEMA: Final = (
    "prospective-generation-shadow-evaluation-publication/v1"
)

_ARM_ORDER: Final = tuple(evaluation.ARM_ORDER)
_FIELD_COMPONENT_NAMES: Final = (
    "payout_table",
    "field_rosters",
    "field_ownership",
    "participant_strength",
    "player_identity",
    "shadow_entry_mapping",
)
_PRELOCK_CARRIER_TOKENS: Final = (
    "/actual",
    "/outcome",
    "/postlock",
    "/post-lock",
    "/standings",
    "/payout",
    "/settlement",
)


class ProspectiveGenerationShadowOperatorError(RuntimeError):
    """An immutable publication or exact reopen failed closed."""


def _fail(message: str) -> None:
    raise ProspectiveGenerationShadowOperatorError(message)


def _canonical_bytes(value: object) -> bytes:
    return evaluation.canonical_json_bytes_v1(value)


def _canonical_sha256(value: object) -> str:
    return evaluation.canonical_sha256_v1(value)


def _with_hash(
    value: Mapping[str, object], *, field: str
) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    body[field] = _canonical_sha256(body)
    return body


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
    ):
        _fail(f"{label} must be an array")
    return list(value)


def _timestamp(value: object, *, label: str) -> datetime:
    if isinstance(value, datetime):
        retained = value
    elif isinstance(value, str):
        try:
            retained = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ProspectiveGenerationShadowOperatorError(
                f"{label} must be ISO-8601"
            ) from exc
    else:
        _fail(f"{label} must be an ISO-8601 timestamp")
    if retained.tzinfo is None or retained.utcoffset() is None:
        _fail(f"{label} must be timezone-aware")
    return retained.astimezone(timezone.utc)


def _timestamp_text(value: object, *, label: str) -> str:
    return _timestamp(value, label=label).isoformat()


def _gs_parts(uri: object) -> tuple[str, str]:
    raw = str(uri or "").strip()
    if not raw.startswith("gs://") or raw.endswith("/"):
        _fail("object URI must name one exact gs:// object")
    bucket, separator, name = raw[5:].partition("/")
    if (
        not separator
        or not bucket
        or not name
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        _fail("object URI is incomplete or unsafe")
    return bucket, name


def _object_uri(prefix: object, suffix: str) -> str:
    raw = str(prefix or "").strip().rstrip("/")
    _gs_parts(f"{raw}/placeholder")
    if not suffix or suffix.startswith("/") or ".." in suffix.split("/"):
        _fail("object suffix is unsafe")
    return f"{raw}/{suffix}"


def _prelock_uri(uri: object, *, label: str) -> str:
    raw = str(uri or "").strip()
    _gs_parts(raw)
    lowered = raw.lower()
    if any(token in lowered for token in _PRELOCK_CARRIER_TOKENS):
        _fail(f"{label} URI is an outcome/post-lock carrier")
    return raw


def _identity_key(value: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(value[field] for field in ("uri", "generation", "sha256", "bytes"))


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return evaluation.normalize_object_identity_v1(value, label=label)
    except Exception as exc:
        if isinstance(exc, ProspectiveGenerationShadowOperatorError):
            raise
        raise ProspectiveGenerationShadowOperatorError(str(exc)) from exc


class ImmutableObjectStore(Protocol):
    """Minimal exact-generation storage contract used by the operator."""

    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> Mapping[str, object]: ...

    def read_exact(
        self, *, identity: Mapping[str, object]
    ) -> Mapping[str, object]: ...


class GCSImmutableObjectStore:
    """Generation-pinned create-once Google Cloud Storage adapter."""

    def __init__(self, client=None) -> None:
        self._client = client

    @property
    def client(self):
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client

    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> Mapping[str, object]:
        bucket_name, object_name = _gs_parts(uri)
        blob = self.client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw,
                content_type=content_type,
                if_generation_match=0,
            )
        except Exception as exc:
            if exc.__class__.__name__ in {
                "AlreadyExists",
                "Conflict",
                "PreconditionFailed",
            }:
                raise ProspectiveGenerationShadowOperatorError(
                    f"create-once collision at {uri}; use a fresh run URI"
                ) from exc
            raise
        reload_blob = getattr(blob, "reload", None)
        if not callable(reload_blob):
            _fail("GCS create-once object cannot expose trusted metadata")
        reload_blob()
        generation = getattr(blob, "generation", None)
        created = getattr(blob, "time_created", None)
        if generation in (None, "") or created is None:
            _fail("GCS create-once object lacks generation/creation metadata")
        created_at = _timestamp_text(created, label="GCS object creation time")
        try:
            reopened = blob.download_as_bytes(
                if_generation_match=int(generation)
            )
        except TypeError:  # pragma: no cover - older client compatibility
            reopened = blob.download_as_bytes()
        if reopened != raw:
            _fail("GCS create-once exact reopen differs from published bytes")
        return {
            "identity": {
                "uri": uri,
                "generation": str(generation),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            "created_at": created_at,
        }

    def read_exact(
        self, *, identity: Mapping[str, object]
    ) -> Mapping[str, object]:
        expected = _identity(identity, label="GCS exact-read identity")
        bucket_name, object_name = _gs_parts(expected["uri"])
        generation = int(str(expected["generation"]))
        bucket = self.client.bucket(bucket_name)
        get_blob = getattr(bucket, "get_blob", None)
        blob = (
            get_blob(object_name, generation=generation)
            if callable(get_blob)
            else bucket.blob(object_name, generation=generation)
        )
        if blob is None:
            _fail("generation-pinned GCS object does not exist")
        actual_generation = getattr(blob, "generation", generation)
        if str(actual_generation) != str(generation):
            _fail("generation-pinned GCS reopen resolved another generation")
        try:
            raw = blob.download_as_bytes(if_generation_match=generation)
        except TypeError:  # pragma: no cover - older client compatibility
            raw = blob.download_as_bytes()
        created = getattr(blob, "time_created", None)
        if created is None:
            reload_blob = getattr(blob, "reload", None)
            if not callable(reload_blob):
                _fail("generation-pinned GCS object lacks creation metadata")
            reload_blob()
            created = getattr(blob, "time_created", None)
        if created is None:
            _fail("generation-pinned GCS object lacks creation metadata")
        if (
            len(raw) != int(expected["bytes"])
            or hashlib.sha256(raw).hexdigest() != expected["sha256"]
        ):
            _fail("generation-pinned GCS content identity differs")
        return {
            "identity": expected,
            "created_at": _timestamp_text(
                created, label="GCS exact-read creation time"
            ),
            "raw": raw,
        }


def _normalize_store_receipt(
    value: object,
    *,
    expected_identity: Mapping[str, object] | None,
    expected_raw: bytes,
    label: str,
) -> dict[str, object]:
    receipt = _mapping(value, label=f"{label} store receipt")
    if set(receipt) != {"identity", "created_at"}:
        _fail(f"{label} store receipt fields differ")
    identity = _identity(receipt.get("identity"), label=f"{label} identity")
    created = _timestamp_text(
        receipt.get("created_at"), label=f"{label} creation time"
    )
    if expected_identity is not None and identity != _identity(
        expected_identity, label=f"expected {label} identity"
    ):
        _fail(f"{label} store resolved another content identity")
    if (
        identity["sha256"] != hashlib.sha256(expected_raw).hexdigest()
        or identity["bytes"] != len(expected_raw)
    ):
        _fail(f"{label} store receipt does not bind exact bytes")
    return {"identity": identity, "created_at": created}


def _publish_raw(
    store: ImmutableObjectStore,
    *,
    uri: str,
    raw: bytes,
    content_type: str,
    label: str,
    not_before: datetime | str | None = None,
    must_precede: datetime | str | None = None,
) -> dict[str, object]:
    _gs_parts(uri)
    receipt = _normalize_store_receipt(
        store.publish_create_once(
            uri=uri, raw=raw, content_type=content_type
        ),
        expected_identity=None,
        expected_raw=raw,
        label=label,
    )
    created = _timestamp(receipt["created_at"], label=f"{label} creation time")
    if not_before is not None and created < _timestamp(
        not_before, label=f"{label} lower clock boundary"
    ):
        _fail(f"{label} was created before its allowed clock boundary")
    if must_precede is not None and created >= _timestamp(
        must_precede, label=f"{label} upper clock boundary"
    ):
        _fail(f"{label} was not created before its lock boundary")
    return receipt


def _publish_json(
    store: ImmutableObjectStore,
    *,
    uri: str,
    value: Mapping[str, object],
    label: str,
    not_before: datetime | str | None = None,
    must_precede: datetime | str | None = None,
) -> dict[str, object]:
    return _publish_raw(
        store,
        uri=uri,
        raw=_canonical_bytes(value),
        content_type="application/json",
        label=label,
        not_before=not_before,
        must_precede=must_precede,
    )


def _read_raw(
    store: ImmutableObjectStore,
    *,
    identity: Mapping[str, object],
    label: str,
) -> dict[str, object]:
    expected = _identity(identity, label=f"{label} identity")
    receipt = _mapping(
        store.read_exact(identity=expected), label=f"{label} exact reopen"
    )
    if set(receipt) != {"identity", "created_at", "raw"}:
        _fail(f"{label} exact-reopen fields differ")
    raw = receipt.get("raw")
    if not isinstance(raw, bytes):
        _fail(f"{label} exact reopen did not return bytes")
    normalized = _normalize_store_receipt(
        {key: receipt[key] for key in ("identity", "created_at")},
        expected_identity=expected,
        expected_raw=raw,
        label=label,
    )
    return {**normalized, "raw": raw}


def _read_json(
    store: ImmutableObjectStore,
    *,
    identity: Mapping[str, object],
    label: str,
    require_canonical: bool = True,
) -> dict[str, object]:
    receipt = _read_raw(store, identity=identity, label=label)
    try:
        parsed = json.loads(receipt["raw"])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProspectiveGenerationShadowOperatorError(
            f"{label} is not canonical JSON"
        ) from exc
    value = _mapping(parsed, label=label)
    if require_canonical and _canonical_bytes(value) != receipt["raw"]:
        _fail(f"{label} bytes are not the canonical JSON representation")
    return {**receipt, "value": value}


def _assert_created_before(
    receipt: Mapping[str, object], boundary: datetime | str, *, label: str
) -> None:
    if _timestamp(receipt["created_at"], label=f"{label} creation time") >= _timestamp(
        boundary, label=f"{label} boundary"
    ):
        _fail(f"{label} was not created before its frozen boundary")


def _assert_created_after(
    receipt: Mapping[str, object], boundary: datetime | str, *, label: str
) -> None:
    if _timestamp(receipt["created_at"], label=f"{label} creation time") <= _timestamp(
        boundary, label=f"{label} boundary"
    ):
        _fail(f"{label} was not created after slate lock")


def publish_preregistration_v1(
    *,
    store: ImmutableObjectStore,
    target_uri: str,
    registered_at: datetime | str,
    week1_lock_at: datetime | str,
    operational_k: int = 80,
) -> dict[str, object]:
    """Publish the one pre-Week-1 family rule with no adoption authority."""

    uri = _prelock_uri(target_uri, label="preregistration")
    preregistration = evaluation.build_preregistration_v1(
        registered_at=registered_at,
        week1_lock_at=week1_lock_at,
        operational_k=operational_k,
    )
    publication = _publish_json(
        store,
        uri=uri,
        value=preregistration,
        label="preregistration",
        not_before=registered_at,
        must_precede=week1_lock_at,
    )
    body = {
        "schema_version": PREREGISTRATION_PUBLICATION_SCHEMA,
        "preregistration_identity": publication["identity"],
        "preregistration_sha256": preregistration["preregistration_sha256"],
        "registered_at": preregistration["registered_at"],
        "week1_lock_at": preregistration["week1_lock_at"],
        "storage_created_at": publication["created_at"],
        "create_once": True,
        "automatic_adoption": False,
        "allocation_recommendation_allowed": False,
    }
    return _with_hash(body, field="publication_sha256")


def publish_seed_crossing_v1(
    *,
    store: ImmutableObjectStore,
    target_uri: str,
    fit_seed_identities: Mapping[str, Mapping[str, object]],
    world_seed_identities: Mapping[str, Mapping[str, object]],
    crossed_slot_identities: Mapping[str, Mapping[str, object]],
    must_precede: datetime | str,
) -> dict[str, object]:
    """Exact-reopen then publish the complete fit x world seed lattice."""

    uri = _prelock_uri(target_uri, label="seed crossing")
    referenced = [
        *fit_seed_identities.values(),
        *world_seed_identities.values(),
        *crossed_slot_identities.values(),
    ]
    seen: set[tuple[object, ...]] = set()
    for ordinal, raw_identity in enumerate(referenced):
        identity = _identity(raw_identity, label=f"seed artifact[{ordinal}]")
        key = _identity_key(identity)
        if key in seen:
            _fail("seed-crossing source authority is reused")
        seen.add(key)
        receipt = _read_raw(
            store, identity=identity, label=f"seed artifact[{ordinal}]"
        )
        _assert_created_before(
            receipt, must_precede, label=f"seed artifact[{ordinal}]"
        )
    crossing = evaluation.build_seed_crossing_v1(
        fit_seed_identities=fit_seed_identities,
        world_seed_identities=world_seed_identities,
        crossed_slot_identities=crossed_slot_identities,
    )
    publication = _publish_json(
        store,
        uri=uri,
        value=crossing,
        label="seed crossing",
        must_precede=must_precede,
    )
    body = {
        "schema_version": SEED_CROSSING_PUBLICATION_SCHEMA,
        "seed_crossing_identity": publication["identity"],
        "seed_crossing_sha256": crossing["seed_crossing_sha256"],
        "storage_created_at": publication["created_at"],
        "source_identity_count": len(referenced),
        "all_sources_exact_reopened": True,
        "crossing_design_complete": True,
        "crossing_execution_status": "not_evaluated",
        "crossed_generation_or_scoring_outputs_semantically_verified": False,
        "create_once": True,
        "uses_realized_outcomes": False,
        "automatic_adoption": False,
    }
    return _with_hash(body, field="publication_sha256")


def publish_prelock_terminal_from_suite_v1(
    *,
    store: ImmutableObjectStore,
    preregistration_identity: Mapping[str, object],
    seed_crossing_identity: Mapping[str, object],
    suite_manifest_identity: Mapping[str, object],
    suite_terminal_identity: Mapping[str, object],
    terminal_root_uri: str,
    terminal_envelope_uri: str,
    slate_id: str | None = None,
) -> dict[str, object]:
    """Adapt exact suite artifacts into the evaluator's terminal envelope."""

    root_uri = _prelock_uri(terminal_root_uri, label="terminal root")
    envelope_uri = _prelock_uri(
        terminal_envelope_uri, label="terminal envelope"
    )
    if root_uri == envelope_uri:
        _fail("terminal root and envelope require distinct create-once URIs")

    prereg_receipt = _read_json(
        store,
        identity=preregistration_identity,
        label="preregistration",
    )
    preregistration = evaluation.validate_preregistration_v1(
        prereg_receipt["value"]
    )
    seed_receipt = _read_json(
        store, identity=seed_crossing_identity, label="seed crossing"
    )
    seed_crossing = evaluation.validate_seed_crossing_v1(seed_receipt["value"])
    manifest_receipt = _read_json(
        store, identity=suite_manifest_identity, label="suite manifest"
    )
    terminal_receipt = _read_json(
        store, identity=suite_terminal_identity, label="suite terminal"
    )
    terminal_doc = terminal_receipt["value"]
    lock_at = terminal_doc.get("slate_lock_at")
    _timestamp(lock_at, label="suite slate lock")
    for label, receipt in (
        ("preregistration", prereg_receipt),
        ("seed crossing", seed_receipt),
        ("suite manifest", manifest_receipt),
        ("suite terminal", terminal_receipt),
    ):
        _assert_created_before(receipt, lock_at, label=label)

    terminal_gcs_receipt = {
        **terminal_receipt["identity"],
        "gcs_time_created": terminal_receipt["created_at"],
        "precedes_slate_lock": True,
        "create_only": True,
    }
    suite_authority = evaluation.build_suite_authority_v1(
        manifest=manifest_receipt["value"],
        terminal=terminal_doc,
        terminal_receipt=terminal_gcs_receipt,
        manifest_storage_created_at=manifest_receipt["created_at"],
        terminal_storage_created_at=terminal_receipt["created_at"],
    )

    decoded_arm_artifacts: dict[str, Mapping[str, object]] = {}
    for arm in _ARM_ORDER:
        identity = suite_authority["world_artifact_identities"][arm]
        raw_receipt = _read_raw(
            store, identity=identity, label=f"suite {arm} immutable bundle"
        )
        _assert_created_before(raw_receipt, lock_at, label=f"suite {arm} bundle")
        if _timestamp_text(
            raw_receipt["created_at"], label=f"suite {arm} external creation"
        ) != _timestamp_text(
            suite_authority["world_storage_created_at_by_arm"][arm],
            label=f"suite {arm} declared creation",
        ):
            _fail(f"suite {arm} trusted creation metadata differs")
        decoded_arm_artifacts[arm] = decode_recourse_world_artifact(
            raw_receipt["raw"], str(identity["sha256"])
        )

    # Reopen the audit and discovery banks as exact generation-pinned bytes.
    # Their scientific validators live in the suite authority; this layer
    # proves the declared objects actually exist before the terminal root.
    auxiliary_identities = [(
        "audit",
        suite_authority["independent_audit_world_artifact_identity"],
        suite_authority["independent_audit_world_storage_created_at"],
    )] + [
        (
            block,
            suite_authority["cross_law_discovery_world_artifact_identities"][
                block
            ],
            suite_authority["cross_law_discovery_world_storage_created_at"][
                block
            ],
        )
        for block in ("R0", "R1", "R2", "R3", "R4")
    ]
    decoded_audit_artifact: Mapping[str, object] | None = None
    for ordinal, (auxiliary_label, identity, expected_created) in enumerate(
        auxiliary_identities
    ):
        receipt = _read_raw(
            store,
            identity=identity,
            label=f"suite auxiliary world[{ordinal}]",
        )
        _assert_created_before(
            receipt, lock_at, label=f"suite auxiliary world[{ordinal}]"
        )
        if _timestamp_text(
            receipt["created_at"],
            label=f"suite auxiliary world[{ordinal}] external creation",
        ) != _timestamp_text(
            expected_created,
            label=f"suite auxiliary world[{ordinal}] declared creation",
        ):
            _fail("suite auxiliary trusted creation metadata differs")
        if auxiliary_label == "audit":
            decoded_audit_artifact = decode_recourse_world_artifact(
                receipt["raw"], str(identity["sha256"])
            )
    if decoded_audit_artifact is None:
        _fail("suite independent-audit artifact was not decoded")

    root = evaluation.build_terminal_prelock_root_from_suite_v2(
        preregistration=preregistration,
        seed_crossing=seed_crossing,
        suite_authority=suite_authority,
        decoded_arm_artifacts=decoded_arm_artifacts,
        decoded_audit_artifact=decoded_audit_artifact,
        slate_id=slate_id,
    )
    root_publication = _publish_json(
        store,
        uri=root_uri,
        value=root,
        label="terminal prelock root",
        not_before=root["frozen_at"],
        must_precede=root["lock_at"],
    )
    envelope = evaluation.bind_terminal_prelock_root_v1(
        root=root,
        uri=root_publication["identity"]["uri"],
        generation=root_publication["identity"]["generation"],
        storage_created_at=root_publication["created_at"],
    )
    evaluation.validate_terminal_prelock_root_v1(envelope)
    envelope_publication = _publish_json(
        store,
        uri=envelope_uri,
        value=envelope,
        label="terminal prelock envelope",
        not_before=root_publication["created_at"],
        must_precede=root["lock_at"],
    )
    body = {
        "schema_version": PRELOCK_PUBLICATION_SCHEMA,
        "season": root["season"],
        "week": root["week"],
        "slate_id": root["slate_id"],
        "lock_at": root["lock_at"],
        "preregistration_identity": prereg_receipt["identity"],
        "seed_crossing_identity": seed_receipt["identity"],
        "suite_manifest_identity": manifest_receipt["identity"],
        "suite_terminal_identity": terminal_receipt["identity"],
        "terminal_prelock_root_identity": root_publication["identity"],
        "terminal_prelock_root_sha256": root[
            "terminal_prelock_root_sha256"
        ],
        "terminal_prelock_envelope_identity": envelope_publication["identity"],
        "terminal_prelock_envelope_sha256": envelope[
            "terminal_prelock_envelope_sha256"
        ],
        "root_storage_created_at": root_publication["created_at"],
        "envelope_storage_created_at": envelope_publication["created_at"],
        "all_inputs_generation_pinned_and_exact_reopened": True,
        "all_outputs_create_once_and_prelock": True,
        "outcome_access_performed": False,
        "production_change_licensed": False,
        "automatic_adoption": False,
    }
    return _with_hash(body, field="publication_sha256")


def _load_prelock_envelope(
    store: ImmutableObjectStore,
    identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    receipt = _read_json(
        store,
        identity=identity,
        label="terminal prelock envelope",
    )
    root = evaluation.validate_terminal_prelock_root_v1(receipt["value"])
    created = _timestamp(
        receipt["created_at"], label="terminal-envelope storage creation"
    )
    if created >= _timestamp(root["lock_at"], label="slate lock"):
        _fail("terminal envelope object was not created before slate lock")
    if created < _timestamp(
        receipt["value"]["storage_created_at"],
        label="terminal-root storage creation",
    ):
        _fail("terminal envelope predates its embedded terminal root")
    return receipt, root


def _resolve_full_field_inputs(
    *,
    store: ImmutableObjectStore,
    field_inputs: Mapping[str, object] | None,
    lock_at: datetime | str,
) -> dict[str, object]:
    if field_inputs is None:
        return {}
    supplied = _mapping(field_inputs, label="complete-field inputs")
    expected = {
        "capture_manifest_identity",
        "capture_source_identity",
        "entry_fee_micro",
        "payout_table_rows",
        "participant_strength_rows",
        "player_identity_rows",
    }
    if set(supplied) != expected:
        _fail("complete-field input fields differ")
    manifest_receipt = _read_json(
        store,
        identity=_mapping(
            supplied["capture_manifest_identity"],
            label="capture-manifest identity",
        ),
        label="applied complete-field capture manifest",
        # ``capture_full_field`` archives a deterministic pretty-printed
        # receipt.  Its exact byte identity is authoritative even though its
        # representation is not this module's compact canonical JSON.
        require_canonical=False,
    )
    source_receipt = _read_raw(
        store,
        identity=_mapping(
            supplied["capture_source_identity"],
            label="capture-source identity",
        ),
        label="complete-field source CSV",
    )
    _assert_created_after(manifest_receipt, lock_at, label="capture manifest")
    _assert_created_after(source_receipt, lock_at, label="capture source")
    if _timestamp(
        manifest_receipt["created_at"], label="capture-manifest creation"
    ) < _timestamp(source_receipt["created_at"], label="capture-source creation"):
        _fail("capture receipt predates its complete-field source")
    manifest = manifest_receipt["value"]
    if "status" not in manifest:
        # The capture receipt is written only after both deterministic BQ
        # loads finish, while ``status=applied`` exists in the command return
        # rather than the archived body.  Exact presence at its own declared
        # receipt URI is therefore the durable apply fact.
        if manifest.get("receipt_uri") != manifest_receipt["identity"]["uri"]:
            _fail("capture receipt cannot prove applied publication")
        manifest = {**manifest, "status": "applied"}
    contest = _mapping(manifest.get("contest"), label="captured contest")
    source = _mapping(manifest.get("source"), label="captured field source")
    source_identity = source_receipt["identity"]
    if (
        source.get("uri") != source_identity["uri"]
        or source.get("sha256") != source_identity["sha256"]
        or source.get("bytes") != source_identity["bytes"]
    ):
        _fail("capture manifest does not bind the exact source generation")
    expected_entries = contest.get("expected_entries")
    if type(expected_entries) is not int or expected_entries < 2:
        _fail("capture manifest field size differs")
    # The public path validator reads a file.  The immutable operator already
    # has exact bytes, so invoke the same parser/validator directly rather
    # than writing outcome data to a temporary path.
    from ..ingest.ownership_import import _validate_full_field_payload

    validated_capture = _validate_full_field_payload(
        str(source_identity["uri"]),
        source_receipt["raw"],
        expected_entries=expected_entries,
    )
    return {
        "capture_manifest": manifest,
        "validated_capture": validated_capture,
        "capture_source_identity": source_identity,
        "entry_fee_micro": supplied["entry_fee_micro"],
        "payout_table_rows": _sequence(
            supplied["payout_table_rows"], label="payout table rows"
        ),
        "participant_strength_rows": _sequence(
            supplied["participant_strength_rows"],
            label="participant-strength rows",
        ),
        "player_identity_rows": _sequence(
            supplied["player_identity_rows"], label="player-identity rows"
        ),
    }


def publish_postlock_week_v1(
    *,
    store: ImmutableObjectStore,
    terminal_prelock_envelope_identity: Mapping[str, object],
    captured_at: datetime | str,
    realized_score_source_identity: Mapping[str, object],
    output_prefix_uri: str,
    field_inputs: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Publish an optional field bridge and grade from independent scores.

    The pre-lock authority is fully reopened and validated before the score
    source is exact-reopened and validated.  The operator cannot create its
    own truth authority.  A missing or incomplete field bundle yields a
    truthful raw-score-only grade; it never yields contest EV or allocation
    advice.
    """

    prefix = str(output_prefix_uri or "").strip().rstrip("/")
    _gs_parts(f"{prefix}/placeholder")
    envelope_receipt, root = _load_prelock_envelope(
        store, terminal_prelock_envelope_identity
    )
    captured = _timestamp(captured_at, label="realized outcome captured-at")
    lock = _timestamp(root["lock_at"], label="slate lock")
    if captured <= lock:
        _fail("realized outcomes must be captured after slate lock")

    score_receipt = _read_json(
        store,
        identity=realized_score_source_identity,
        label="independently published realized-score source",
    )
    _assert_created_after(
        score_receipt, lock, label="independently published realized-score source"
    )
    if str(score_receipt["identity"]["uri"]).startswith(f"{prefix}/"):
        _fail("realized-score source must be published outside the grader namespace")
    score_payload = _mapping(
        score_receipt["value"], label="independently published realized-score source"
    )
    expected_score_fields = {
        "schema_version", "season", "week", "slate_id", "captured_at",
        "producer_class", "independent_from_generation",
        "terminal_prelock_root_binding_present", "lineup_count",
        "lineup_rows", "lineup_rows_sha256",
    }
    score_rows = _sequence(
        score_payload.get("lineup_rows"), label="independent realized-score rows"
    )
    realized_score_micro_by_lineup_id: dict[str, int] = {}
    for ordinal, raw_row in enumerate(score_rows):
        row = _mapping(raw_row, label=f"independent realized-score row[{ordinal}]")
        if set(row) != {"lineup_id", "realized_score_micro"}:
            _fail("independent realized-score row fields differ")
        lineup_id = str(row.get("lineup_id") or "").strip()
        score = row.get("realized_score_micro")
        if not lineup_id or lineup_id in realized_score_micro_by_lineup_id:
            _fail("independent realized-score lineup IDs are empty or repeated")
        if type(score) is not int:
            _fail("independent realized score must use integer micro-points")
        realized_score_micro_by_lineup_id[lineup_id] = score
    if (
        set(score_payload) != expected_score_fields
        or score_payload.get("schema_version")
        != evaluation.REALIZED_SCORE_SOURCE_SCHEMA
        or score_payload.get("season") != root["season"]
        or score_payload.get("week") != root["week"]
        or score_payload.get("slate_id") != root["slate_id"]
        or score_payload.get("producer_class")
        != "independent-realized-lineup-score-source"
        or score_payload.get("independent_from_generation") is not True
        or score_payload.get("terminal_prelock_root_binding_present") is not False
        or score_payload.get("lineup_count") != len(score_rows)
        or score_payload.get("lineup_rows_sha256") != _canonical_sha256(score_rows)
        or _timestamp(
            score_payload.get("captured_at"), label="realized-score source captured-at"
        ) != captured
        or _timestamp(
            score_receipt["created_at"], label="realized-score source creation time"
        ) < captured
    ):
        _fail("independently published realized-score source contract differs")

    resolved_field_inputs = _resolve_full_field_inputs(
        store=store, field_inputs=field_inputs, lock_at=lock
    )
    preparation_or_raw = field_bridge.prepare_contest_field_bridge_v1(
        terminal_prelock_root=envelope_receipt["value"],
        captured_at=captured,
        realized_score_micro_by_lineup_id=realized_score_micro_by_lineup_id,
        realized_score_source_identity=score_receipt["identity"],
        **resolved_field_inputs,
    )
    component_publications: dict[str, dict[str, object]] = {}
    if preparation_or_raw.get("status") == (
        "ready-for-create-once-component-binding"
    ):
        payloads = _mapping(
            preparation_or_raw.get("component_payloads"),
            label="prepared field components",
        )
        if set(payloads) != set(_FIELD_COMPONENT_NAMES):
            _fail("prepared field-component registry differs")
        for name in _FIELD_COMPONENT_NAMES:
            publication = _publish_json(
                store,
                uri=_object_uri(prefix, f"field-components/{name}.json"),
                value=_mapping(payloads[name], label=f"{name} component"),
                label=f"{name} field component",
                not_before=captured,
            )
            component_publications[name] = publication
        bridge = field_bridge.bind_contest_field_bridge_v1(
            preparation=preparation_or_raw,
            component_identities={
                name: component_publications[name]["identity"]
                for name in _FIELD_COMPONENT_NAMES
            },
        )
    else:
        bridge = field_bridge.validate_contest_field_bridge_v1(
            preparation_or_raw
        )
    bridge = field_bridge.validate_contest_field_bridge_v1(bridge)
    bridge_publication = _publish_json(
        store,
        uri=_object_uri(prefix, "field-bridge.json"),
        value=bridge,
        label="contest-field bridge",
        not_before=captured,
    )

    outcome_payload = evaluation.build_outcome_source_payload_from_field_bridge_v1(
        terminal_prelock_root=envelope_receipt["value"],
        field_bridge=bridge,
    )
    outcome_publication = _publish_json(
        store,
        uri=_object_uri(prefix, "outcome-source.json"),
        value=outcome_payload,
        label="independent outcome source",
        not_before=captured,
    )
    snapshot = evaluation.build_outcome_snapshot_from_field_bridge_v1(
        terminal_prelock_root=envelope_receipt["value"],
        field_bridge=bridge,
        outcome_source_identity=outcome_publication["identity"],
    )
    snapshot_publication = _publish_json(
        store,
        uri=_object_uri(prefix, "outcome-snapshot.json"),
        value=snapshot,
        label="independent outcome snapshot",
        not_before=captured,
    )
    grade = evaluation.grade_realized_week_v1(
        terminal_prelock_root=envelope_receipt["value"],
        outcome_snapshot=snapshot,
    )
    grade_publication = _publish_json(
        store,
        uri=_object_uri(prefix, "weekly-grade.json"),
        value=grade,
        label="realized weekly grade",
        not_before=captured,
    )

    body = {
        "schema_version": POSTLOCK_PUBLICATION_SCHEMA,
        "season": root["season"],
        "week": root["week"],
        "slate_id": root["slate_id"],
        "captured_at": captured.isoformat(),
        "terminal_prelock_envelope_identity": envelope_receipt["identity"],
        "realized_score_source_identity": score_receipt["identity"],
        "field_bridge_identity": bridge_publication["identity"],
        "field_component_identities": {
            name: publication["identity"]
            for name, publication in component_publications.items()
        },
        "outcome_source_identity": outcome_publication["identity"],
        "outcome_snapshot_identity": snapshot_publication["identity"],
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "weekly_grade_identity": grade_publication["identity"],
        "weekly_grade_sha256": grade["weekly_grade_sha256"],
        "field_status": bridge["status"],
        "evidence_scope": bridge["evidence_scope"],
        "complete_contest_field_capture": bridge[
            "complete_contest_field_capture"
        ],
        "complete_field_rank_claim_allowed": bridge[
            "complete_field_rank_claim_allowed"
        ],
        "contest_ev_claim_allowed": bridge["contest_ev_claim_allowed"],
        "allocation_recommendation_allowed": False,
        "all_operator_outputs_create_once": True,
        "realized_score_source_exact_reopened_not_published_by_operator": True,
        "automatic_adoption": False,
        "production_change_licensed": False,
    }
    publication_terminal = _with_hash(body, field="publication_sha256")
    terminal_publication = _publish_json(
        store,
        uri=_object_uri(prefix, "publication-terminal.json"),
        value=publication_terminal,
        label="postlock publication terminal",
        not_before=grade_publication["created_at"],
    )
    return {
        **publication_terminal,
        "publication_terminal_identity": terminal_publication["identity"],
        "publication_terminal_storage_created_at": terminal_publication[
            "created_at"
        ],
    }


def publish_evaluation_v1(
    *,
    store: ImmutableObjectStore,
    preregistration_identity: Mapping[str, object],
    weekly_grade_identities: Sequence[Mapping[str, object]],
    target_uri: str,
) -> dict[str, object]:
    """Publish a versioned 1..N-week evaluation with no adoption action."""

    prereg_receipt = _read_json(
        store, identity=preregistration_identity, label="preregistration"
    )
    preregistration = evaluation.validate_preregistration_v1(
        prereg_receipt["value"]
    )
    grade_receipts = [
        _read_json(store, identity=identity, label=f"weekly grade[{ordinal}]")
        for ordinal, identity in enumerate(weekly_grade_identities)
    ]
    if not grade_receipts:
        _fail("evaluation requires at least one weekly grade identity")
    grades = [
        evaluation.validate_realized_week_grade_v1(receipt["value"])
        for receipt in grade_receipts
    ]
    result = evaluation.evaluate_prospective_shadow_v1(
        preregistration=preregistration,
        weekly_grades=grades,
    )
    lower_clock = max(
        _timestamp(receipt["created_at"], label="weekly-grade creation")
        for receipt in grade_receipts
    )
    publication = _publish_json(
        store,
        uri=str(target_uri),
        value=result,
        label="prospective season evaluation",
        not_before=lower_clock,
    )
    body = {
        "schema_version": EVALUATION_PUBLICATION_SCHEMA,
        "season": result["season"],
        "completed_week_count": result["completed_week_count"],
        "completed_weeks": result["completed_weeks"],
        "horizon": result["horizon"],
        "decision_scope": result["decision_scope"],
        "preregistration_identity": prereg_receipt["identity"],
        "weekly_grade_identities": [
            receipt["identity"] for receipt in grade_receipts
        ],
        "evaluation_identity": publication["identity"],
        "evaluation_sha256": result["evaluation_sha256"],
        "contest_ev_claim_allowed": result["contest_ev_claim_allowed"],
        "allocation_recommendation_allowed": False,
        "automatic_adoption": False,
        "human_decision_required": True,
    }
    return _with_hash(body, field="publication_sha256")


def _json_request(path: str) -> dict[str, object]:
    raw = Path(path).read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProspectiveGenerationShadowOperatorError(
            "operator request is not JSON"
        ) from exc
    return _mapping(value, label="operator request")


def _store_for_execute(execute: bool) -> ImmutableObjectStore:
    if execute is not True:
        _fail("operator mutation is default-off; pass --execute explicitly")
    return GCSImmutableObjectStore()


def _summary(result: Mapping[str, object]) -> dict[str, object]:
    retained = {
        key: result[key]
        for key in (
            "schema_version",
            "season",
            "week",
            "slate_id",
            "completed_week_count",
            "horizon",
            "decision_scope",
            "field_status",
            "evidence_scope",
            "contest_ev_claim_allowed",
            "allocation_recommendation_allowed",
            "automatic_adoption",
            "publication_sha256",
        )
        if key in result
    }
    for key in (
        "preregistration_identity",
        "seed_crossing_identity",
        "terminal_prelock_envelope_identity",
        "weekly_grade_identity",
        "evaluation_identity",
        "publication_terminal_identity",
    ):
        if key in result:
            retained[key] = result[key]
    return retained


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Create-once prospective generation-shadow operator"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prereg = subparsers.add_parser("preregister")
    prereg.add_argument("--target-uri", required=True)
    prereg.add_argument("--registered-at", required=True)
    prereg.add_argument("--week1-lock-at", required=True)
    prereg.add_argument("--operational-k", type=int, default=80)
    prereg.add_argument("--execute", action="store_true")

    for command in (
        "publish-seed-crossing",
        "freeze-week",
        "grade-week",
        "evaluate-season",
    ):
        child = subparsers.add_parser(command)
        child.add_argument("--request", required=True)
        child.add_argument("--execute", action="store_true")

    args = parser.parse_args(argv)
    store = _store_for_execute(bool(args.execute))
    if args.command == "preregister":
        result = publish_preregistration_v1(
            store=store,
            target_uri=args.target_uri,
            registered_at=args.registered_at,
            week1_lock_at=args.week1_lock_at,
            operational_k=args.operational_k,
        )
    else:
        request = _json_request(args.request)
        if args.command == "publish-seed-crossing":
            result = publish_seed_crossing_v1(store=store, **request)
        elif args.command == "freeze-week":
            result = publish_prelock_terminal_from_suite_v1(
                store=store, **request
            )
        elif args.command == "grade-week":
            result = publish_postlock_week_v1(store=store, **request)
        else:
            result = publish_evaluation_v1(store=store, **request)
    print(json.dumps(_summary(result), sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "EVALUATION_PUBLICATION_SCHEMA",
    "GCSImmutableObjectStore",
    "ImmutableObjectStore",
    "POSTLOCK_PUBLICATION_SCHEMA",
    "PRELOCK_PUBLICATION_SCHEMA",
    "PREREGISTRATION_PUBLICATION_SCHEMA",
    "ProspectiveGenerationShadowOperatorError",
    "SEED_CROSSING_PUBLICATION_SCHEMA",
    "main",
    "publish_evaluation_v1",
    "publish_postlock_week_v1",
    "publish_prelock_terminal_from_suite_v1",
    "publish_preregistration_v1",
    "publish_seed_crossing_v1",
]
