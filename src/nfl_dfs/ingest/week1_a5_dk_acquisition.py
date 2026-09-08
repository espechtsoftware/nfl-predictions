"""Governed DraftKings acquisition and read-only Week-1 source authority.

This module closes the trust-root seam left intentionally open by
``week1_a5_capture_contracts``.  Generic object storage proves that bytes are
immutable; it does not prove that DraftKings returned them.  A source claim is
recognized here only when a reviewed collector has written a root-last event
to a dedicated, create-only authority ledger and the read-only adapter can
reopen that event from its sole provider generation.

The live surface is deliberately default-off.  It has no injectable store,
transport, authority, locator, collector identity, or ledger writer.  The
review/test seam is private and exists only so the collector and its
adversaries can be exercised without contacting a provider.  Live pins remain
unset until this exact collector is independently reviewed and built into one
immutable image; consequently every live entry point fails before network or
storage contact today.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Final, Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from nfl_dfs.inference.generation_exposure import canonical_json_bytes, canonical_sha256
from nfl_dfs.ingest import week1_a5_capture_contracts as capture
from nfl_dfs.ingest import week1_a5_dk_acquisition_pins as live_pins

COLLECTOR_ALLOWLIST_SCHEMA: Final = "dk-a5-collector-allowlist/v1"
COLLECTOR_LEDGER_SCHEMA: Final = "dk-a5-collector-issuance-ledger/v1"
COLLECTOR_TRANSPORT_EVENT_SCHEMA: Final = "dk-a5-http-transport-event/v1"
COLLECTOR_SESSION_PROFILE: Final = "dk-playwright-storage-state-cookie-bridge/v1"
COLLECTOR_AUTHORITY_PROFILE: Final = capture.PROVIDER_ACQUISITION_AUTHORITY_PROFILE
MAX_REDIRECTS: Final = 5

LIVE_PROJECT: Final = "nfl-predictions-503414"
LIVE_EVIDENCE_BUCKET: Final = "nfl-predictions-503414-raw"
LIVE_EVIDENCE_PREFIX: Final = "week1/provider-acquisitions/v1"
LIVE_AUTHORITY_BUCKET: Final = "nfl-predictions-503414-dk-acquisition-authority"
LIVE_AUTHORITY_PREFIX: Final = "issuance/v1"
LIVE_PROVIDER_CAPTURE_PREFIX: Final = "week1/provider-captures/v1"
LIVE_SESSION_STATE_PATH: Final = Path(
    "/var/run/secrets/nfl-dfs/draftkings-storage-state.json"
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SERVICE_ACCOUNT = re.compile(
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam\.gserviceaccount\.com\Z"
)
_EVENT_ID = re.compile(r"dk-a5-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{32}\Z")
_IDENTITY_FIELDS = frozenset({"uri", "generation", "sha256", "bytes"})
_LOCATOR_PROJECTION_FIELDS = frozenset(
    {"redacted_locator", "locator_sha256", "query_parameter_names"}
)
_TRANSPORT_HOP_FIELDS = frozenset(
    {
        "ordinal",
        "status",
        "redacted_locator",
        "locator_sha256",
        "query_parameter_names",
        "redirect_target",
    }
)
_TRANSPORT_EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "request_method",
        "requested_locator",
        "effective_locator",
        "redirect_chain",
        "observed_at",
        "response_status",
        "response_content_type",
        "response_content_disposition",
        "session_profile",
        "body_sha256",
        "body_bytes",
    }
)
_DIRECT_OBJECT_MUTATOR_ROLES: Final = frozenset(
    {
        "roles/storage.admin",
        "roles/storage.legacyBucketOwner",
        "roles/storage.legacyBucketWriter",
        "roles/storage.legacyObjectOwner",
        "roles/storage.objectAdmin",
        "roles/storage.objectCreator",
        "roles/storage.objectUser",
    }
)
_DIRECT_OBJECT_VIEWER_ROLES: Final = frozenset(
    {
        "roles/storage.legacyBucketReader",
        "roles/storage.legacyObjectReader",
        "roles/storage.objectViewer",
    }
)
_REVIEWED_DIRECT_BUCKET_ROLES: Final = (
    _DIRECT_OBJECT_MUTATOR_ROLES | _DIRECT_OBJECT_VIEWER_ROLES
)


class Week1A5DraftKingsAcquisitionError(ValueError):
    """The governed DraftKings acquisition boundary failed closed."""


def _fail(message: str) -> None:
    raise Week1A5DraftKingsAcquisitionError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _exact(
    value: Mapping[str, object], fields: set[str] | frozenset[str], *, label: str
) -> None:
    if set(value) != set(fields):
        _fail(
            f"{label} fields differ: missing={sorted(set(fields) - set(value))} "
            f"unexpected={sorted(set(value) - set(fields))}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{label} must be a canonical nonempty string")
    return value


def _sha(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if _SHA.fullmatch(retained) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return retained


def _timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    text = _string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise Week1A5DraftKingsAcquisitionError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(f"{label} must include a UTC offset")
    parsed = parsed.astimezone(UTC)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact(item, _IDENTITY_FIELDS, label=label)
    uri = _string(item["uri"], label=f"{label}.uri")
    if not uri.startswith("gs://") or uri.endswith("/") or "/" not in uri[5:]:
        _fail(f"{label}.uri must name one generation-free gs:// object")
    generation = item["generation"]
    if type(generation) not in {str, int} or not str(generation).isdigit():
        _fail(f"{label}.generation must be numeric")
    size = item["bytes"]
    if type(size) is not int or size < 1:
        _fail(f"{label}.bytes must be a positive integer")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": _sha(item["sha256"], label=f"{label}.sha256"),
        "bytes": size,
    }


def _gs_parts(uri: str, *, label: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        _fail(f"{label} must be a gs:// URI")
    bucket, separator, name = uri[5:].partition("/")
    if not separator or not bucket or not name or name.startswith("/"):
        _fail(f"{label} must name one object")
    return bucket, name


def _assert_uri_scope(uri: str, *, bucket: str, prefix: str, label: str) -> None:
    actual_bucket, name = _gs_parts(uri, label=label)
    if actual_bucket != bucket or not name.startswith(f"{prefix.rstrip('/')}/"):
        _fail(f"{label} is outside its code-pinned bucket/prefix")


def _canonical_url(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    parsed = urlsplit(text)
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise Week1A5DraftKingsAcquisitionError(
            f"{label} has an invalid explicit port"
        ) from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        _fail(f"{label} must be one credential-free HTTPS locator")
    host = parsed.hostname.lower()
    port = f":{parsed_port}" if parsed_port is not None else ""
    path = parsed.path or "/"
    return urlunsplit(("https", f"{host}{port}", path, parsed.query, ""))


def _redact_url(value: str) -> dict[str, object]:
    """Retain routing structure without persisting signed query values."""

    canonical = _canonical_url(value, label="transport locator")
    parsed = urlsplit(canonical)
    query_names = sorted(
        {name for name, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    )
    redacted_query = urlencode([(name, "<redacted>") for name in query_names])
    return {
        "redacted_locator": urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, redacted_query, "")
        ),
        "locator_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "query_parameter_names": query_names,
    }


def _validate_redacted_locator(value: object, *, label: str) -> dict[str, object]:
    """Validate one locator projection without reconstructing secret query values."""

    item = _mapping(value, label=label)
    _exact(item, _LOCATOR_PROJECTION_FIELDS, label=label)
    locator = _canonical_url(item["redacted_locator"], label=f"{label}.locator")
    parsed = urlsplit(locator)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(query_value != "<redacted>" for _, query_value in pairs):
        _fail(f"{label} exposes or invents a query value")
    names_value = item["query_parameter_names"]
    if (
        isinstance(names_value, (str, bytes, bytearray))
        or not isinstance(names_value, Sequence)
        or any(type(name) is not str or not name for name in names_value)
    ):
        _fail(f"{label}.query_parameter_names must be an array of strings")
    names = list(names_value)
    if names != sorted(set(names)) or names != sorted({name for name, _ in pairs}):
        _fail(f"{label}.query_parameter_names differs from its redacted locator")
    expected_redaction = _redact_url(locator)
    if locator != expected_redaction["redacted_locator"]:
        _fail(f"{label}.redacted_locator is not canonical")
    return {
        "redacted_locator": locator,
        # This hashes the unredacted locator and therefore cannot be recomputed
        # from the projection.  It is retained only because the collector-only
        # ledger makes the projection authoritative.
        "locator_sha256": _sha(item["locator_sha256"], label=f"{label}.sha256"),
        "query_parameter_names": names,
    }


def _canonical_iam_value(value: object, *, label: str) -> object:
    """Retain an IAM condition without dropping provider-returned fields."""

    if value is None or type(value) in {str, int, bool}:
        return value
    if isinstance(value, Mapping):
        if any(type(key) is not str or not key for key in value):
            _fail(f"{label} must have canonical string keys")
        return {
            key: _canonical_iam_value(value[key], label=f"{label}.{key}")
            for key in sorted(value)
        }
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [
            _canonical_iam_value(item, label=f"{label}[{ordinal}]")
            for ordinal, item in enumerate(value)
        ]
    _fail(f"{label} contains a non-JSON IAM value")


def _normalize_iam_bindings(
    value: object, *, label: str
) -> tuple[dict[str, object], ...]:
    """Normalize the complete direct bucket policy without role projection."""

    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    retained: list[dict[str, object]] = []
    for ordinal, raw_binding in enumerate(value):
        binding = _mapping(raw_binding, label=f"{label}[{ordinal}]")
        if set(binding) not in ({"role", "members"}, {"role", "members", "condition"}):
            _fail(f"{label}[{ordinal}] has an unrecognized provider field")
        role = _string(binding["role"], label=f"{label}[{ordinal}].role")
        # The authority bucket is deliberately simple.  A custom or newly
        # introduced role is not guessed to be read-only: it stays HOLD until
        # an independently reviewed source revision understands its complete
        # permission set.
        if role not in _REVIEWED_DIRECT_BUCKET_ROLES:
            _fail(f"{label}[{ordinal}] contains an unreviewed bucket role")
        raw_members = binding["members"]
        if isinstance(raw_members, (str, bytes, bytearray)) or not isinstance(
            raw_members, Sequence
        ):
            _fail(f"{label}[{ordinal}].members must be an array")
        members = tuple(
            _string(member, label=f"{label}[{ordinal}].members")
            for member in raw_members
        )
        if members != tuple(sorted(set(members))):
            _fail(f"{label}[{ordinal}].members must be unique and sorted")
        item: dict[str, object] = {"role": role, "members": list(members)}
        if "condition" in binding:
            condition = _canonical_iam_value(
                binding["condition"], label=f"{label}[{ordinal}].condition"
            )
            if not isinstance(condition, Mapping) or not condition:
                _fail(f"{label}[{ordinal}].condition must be a nonempty object")
            item["condition"] = condition
        retained.append(item)
    encoded = [canonical_json_bytes(item) for item in retained]
    if encoded != sorted(set(encoded)):
        _fail(f"{label} must be unique and canonically sorted")
    return tuple(retained)


def _iam_policy_sha256(
    *, version: int, etag_base64: str, bindings: Sequence[Mapping[str, object]]
) -> str:
    return canonical_sha256(
        {
            "version": version,
            "etag_base64": etag_base64,
            "bindings": [dict(binding) for binding in bindings],
        }
    )


@dataclass(frozen=True)
class LocatorFamily:
    scheme: str
    host: str
    path_prefix: str
    port: int = 443

    def as_dict(self) -> dict[str, object]:
        return {
            "scheme": self.scheme,
            "host": self.host,
            "port": self.port,
            "path_prefix": self.path_prefix,
        }

    def accepts(self, locator: str) -> bool:
        parsed = urlsplit(_canonical_url(locator, label="effective locator"))
        return (
            parsed.scheme == self.scheme
            and parsed.hostname == self.host
            and (parsed.port or 443) == self.port
            and parsed.path.startswith(self.path_prefix)
        )


@dataclass(frozen=True)
class AcquisitionRule:
    profile: str
    method: str
    request_locator_kind: str
    media_type: str
    disposition: str
    effective_locator_families: tuple[LocatorFamily, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "method": self.method,
            "request_locator_kind": self.request_locator_kind,
            "media_type": self.media_type,
            "disposition": self.disposition,
            "effective_locator_families": [
                family.as_dict() for family in self.effective_locator_families
            ],
        }


@dataclass(frozen=True)
class CollectorGovernance:
    authority_bucket_metageneration: str
    retention_seconds: int
    retention_locked: bool
    versioning_enabled: bool
    uniform_bucket_level_access: bool
    iam_policy_version: int
    iam_policy_etag_base64: str
    iam_policy_sha256: str
    iam_policy_bindings: tuple[Mapping[str, object], ...]
    object_mutator_members: tuple[str, ...]
    object_viewer_members: tuple[str, ...]
    public_members: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "authority_bucket_metageneration": self.authority_bucket_metageneration,
            "retention_seconds": self.retention_seconds,
            "retention_locked": self.retention_locked,
            "versioning_enabled": self.versioning_enabled,
            "uniform_bucket_level_access": self.uniform_bucket_level_access,
            "iam_policy_version": self.iam_policy_version,
            "iam_policy_etag_base64": self.iam_policy_etag_base64,
            "iam_policy_sha256": self.iam_policy_sha256,
            "iam_policy_bindings": [dict(item) for item in self.iam_policy_bindings],
            "object_mutator_members": list(self.object_mutator_members),
            "object_viewer_members": list(self.object_viewer_members),
            "public_members": list(self.public_members),
        }


@dataclass(frozen=True)
class CollectorAllowlist:
    source_commit: str
    code_sha256: str
    image_digest: str
    collector_service_account: str
    authority_reader_service_account: str
    session_profile: str
    project: str
    evidence_bucket: str
    evidence_prefix: str
    authority_bucket: str
    authority_prefix: str
    provider_capture_prefix: str
    draft_group_id: str
    role_contest_ids: Mapping[str, str]
    rules: Mapping[str, AcquisitionRule]
    governance: CollectorGovernance
    allowlist_sha256: str

    def semantic_body(self) -> dict[str, object]:
        return {
            "schema_version": COLLECTOR_ALLOWLIST_SCHEMA,
            "source_commit": self.source_commit,
            "code_sha256": self.code_sha256,
            "image_digest": self.image_digest,
            "collector_service_account": self.collector_service_account,
            "authority_reader_service_account": self.authority_reader_service_account,
            "session_profile": self.session_profile,
            "project": self.project,
            "evidence_bucket": self.evidence_bucket,
            "evidence_prefix": self.evidence_prefix,
            "authority_bucket": self.authority_bucket,
            "authority_prefix": self.authority_prefix,
            "provider_capture_prefix": self.provider_capture_prefix,
            "draft_group_id": self.draft_group_id,
            "role_contest_ids": dict(sorted(self.role_contest_ids.items())),
            "rules": [self.rules[key].as_dict() for key in sorted(self.rules)],
            "governance": self.governance.as_dict(),
        }


@dataclass(frozen=True)
class TransportHop:
    locator: str
    status: int
    redirect_target: str | None


@dataclass(frozen=True)
class TransportEvent:
    body: bytes
    observed_at: str
    hops: tuple[TransportHop, ...]
    response_content_type: str
    response_content_disposition: str | None
    session_profile: str


@dataclass(frozen=True)
class CollectorIssuance:
    acquisition_receipt: dict[str, object]
    ledger_identity: dict[str, object]
    authority_event_id: str
    redacted_transport: dict[str, object]


@dataclass(frozen=True)
class _AuthorityReadBoundary:
    profiles: tuple[str, ...]
    phase: str
    publish_by: str
    not_after: datetime
    not_before: datetime | None


class _Transport(Protocol):
    def perform(self, *, method: str, locator: str) -> TransportEvent: ...


class _EvidenceStore(capture.ImmutableObjectStore, Protocol):
    pass


class _LedgerWriter(Protocol):
    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> Mapping[str, object]: ...

    def read_exact(self, *, identity: Mapping[str, object]) -> Mapping[str, object]: ...


class _LedgerReader(Protocol):
    def governance(self) -> Mapping[str, object]: ...

    def read_single_generation(self, *, uri: str) -> Mapping[str, object]: ...


def _module_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _validate_governance(value: object, *, label: str) -> CollectorGovernance:
    row = _mapping(value, label=label)
    fields = {
        "authority_bucket_metageneration",
        "retention_seconds",
        "retention_locked",
        "versioning_enabled",
        "uniform_bucket_level_access",
        "iam_policy_version",
        "iam_policy_etag_base64",
        "iam_policy_sha256",
        "iam_policy_bindings",
        "object_mutator_members",
        "object_viewer_members",
        "public_members",
    }
    _exact(row, fields, label=label)
    metageneration = _string(
        row["authority_bucket_metageneration"], label=f"{label}.metageneration"
    )
    if not metageneration.isdigit() or int(metageneration) < 1:
        _fail(f"{label}.metageneration must be positive")
    retention = row["retention_seconds"]
    if type(retention) is not int or retention < 604_800:
        _fail(f"{label}.retention_seconds must be at least seven days")
    for field in (
        "retention_locked",
        "versioning_enabled",
        "uniform_bucket_level_access",
    ):
        if row[field] is not True:
            _fail(f"{label}.{field} must be true")
    policy_version = row["iam_policy_version"]
    if type(policy_version) is not int or policy_version not in {1, 3}:
        _fail(f"{label}.iam_policy_version must be provider policy version 1 or 3")
    etag_base64 = _string(
        row["iam_policy_etag_base64"], label=f"{label}.iam_policy_etag_base64"
    )
    try:
        decoded_etag = base64.b64decode(etag_base64, validate=True)
    except (ValueError, TypeError) as exc:
        raise Week1A5DraftKingsAcquisitionError(
            f"{label}.iam_policy_etag_base64 must be canonical base64"
        ) from exc
    if not decoded_etag or base64.b64encode(decoded_etag).decode() != etag_base64:
        _fail(f"{label}.iam_policy_etag_base64 must be canonical base64")
    bindings = _normalize_iam_bindings(
        row["iam_policy_bindings"], label=f"{label}.iam_policy_bindings"
    )
    policy_sha = _sha(
        row["iam_policy_sha256"], label=f"{label}.iam_policy_sha256"
    )
    if policy_sha != _iam_policy_sha256(
        version=policy_version,
        etag_base64=etag_base64,
        bindings=bindings,
    ):
        _fail(f"{label}.iam_policy_sha256 differs from the complete IAM policy")
    member_fields: dict[str, tuple[str, ...]] = {}
    for field in ("object_mutator_members", "object_viewer_members", "public_members"):
        raw = row[field]
        if isinstance(raw, (str, bytes, bytearray)) or not isinstance(raw, Sequence):
            _fail(f"{label}.{field} must be an array")
        members = tuple(str(item) for item in raw)
        if tuple(sorted(set(members))) != members:
            _fail(f"{label}.{field} must be unique and sorted")
        member_fields[field] = members
    derived_mutators = tuple(
        sorted(
            {
                str(member)
                for binding in bindings
                if binding["role"] in _DIRECT_OBJECT_MUTATOR_ROLES
                for member in binding["members"]
            }
        )
    )
    derived_viewers = tuple(
        sorted(
            {
                str(member)
                for binding in bindings
                if binding["role"] in _DIRECT_OBJECT_VIEWER_ROLES
                for member in binding["members"]
            }
        )
    )
    derived_public = tuple(
        sorted(
            {
                str(member)
                for binding in bindings
                for member in binding["members"]
                if member in {"allUsers", "allAuthenticatedUsers"}
            }
        )
    )
    if member_fields["object_mutator_members"] != derived_mutators:
        _fail(f"{label}.object_mutator_members differs from the complete IAM policy")
    if member_fields["object_viewer_members"] != derived_viewers:
        _fail(f"{label}.object_viewer_members differs from the complete IAM policy")
    if member_fields["public_members"] != derived_public:
        _fail(f"{label}.public_members differs from the complete IAM policy")
    if member_fields["public_members"]:
        _fail(f"{label} must not grant public access")
    return CollectorGovernance(
        authority_bucket_metageneration=metageneration,
        retention_seconds=retention,
        retention_locked=True,
        versioning_enabled=True,
        uniform_bucket_level_access=True,
        iam_policy_version=policy_version,
        iam_policy_etag_base64=etag_base64,
        iam_policy_sha256=policy_sha,
        iam_policy_bindings=bindings,
        object_mutator_members=member_fields["object_mutator_members"],
        object_viewer_members=member_fields["object_viewer_members"],
        public_members=(),
    )


def _build_allowlist(
    *,
    source_commit: str,
    code_sha256: str,
    image_digest: str,
    collector_service_account: str,
    authority_reader_service_account: str,
    governance: CollectorGovernance,
    acceptance_effective_families: tuple[LocatorFamily, ...],
    standings_effective_families: tuple[LocatorFamily, ...],
    contest_detail_effective_families: tuple[LocatorFamily, ...] | None = None,
) -> CollectorAllowlist:
    if _COMMIT.fullmatch(source_commit) is None:
        _fail("collector source commit is not exact")
    _sha(code_sha256, label="collector code SHA")
    if _IMAGE.fullmatch(image_digest) is None:
        _fail("collector image is not immutable")
    for value, label in (
        (collector_service_account, "collector service account"),
        (authority_reader_service_account, "authority reader service account"),
    ):
        if _SERVICE_ACCOUNT.fullmatch(value) is None:
            _fail(f"{label} is not an exact service account")
    if not isinstance(governance, CollectorGovernance):
        _fail("collector governance must be its sealed repository type")
    governance = _validate_governance(
        governance.as_dict(), label="collector allowlist governance"
    )
    expected_creator = (f"serviceAccount:{collector_service_account}",)
    if governance.object_mutator_members != expected_creator:
        _fail("authority ledger has another direct object mutator")
    reader_member = f"serviceAccount:{authority_reader_service_account}"
    if reader_member not in governance.object_viewer_members:
        _fail("authority reader is not present in the exact viewer set")

    def validated_families(
        values: tuple[LocatorFamily, ...], *, label: str
    ) -> tuple[LocatorFamily, ...]:
        if not values or any(not isinstance(value, LocatorFamily) for value in values):
            _fail(f"{label} must be a nonempty exact locator-family tuple")
        semantic: list[tuple[str, str, int, str]] = []
        for value in values:
            if (
                value.scheme != "https"
                or value.host != value.host.lower()
                or not value.host
                or value.port != 443
                or value.path_prefix != value.path_prefix.strip()
                or not value.path_prefix.startswith("/")
            ):
                _fail(f"{label} contains a noncanonical locator family")
            semantic.append((value.scheme, value.host, value.port, value.path_prefix))
        if semantic != sorted(set(semantic)):
            _fail(f"{label} must be unique and sorted")
        return values

    acceptance_effective_families = validated_families(
        acceptance_effective_families, label="acceptance locator families"
    )
    standings_effective_families = validated_families(
        standings_effective_families, label="standings locator families"
    )
    detail_families = contest_detail_effective_families or (
        LocatorFamily(
            "https",
            "api.draftkings.com",
            capture.FINAL_FIELD_SOURCE_LOCATOR_PREFIX.split("api.draftkings.com", 1)[1],
        ),
    )
    detail_families = validated_families(
        detail_families, label="contest-detail locator families"
    )
    rules = {
        capture.ACCEPTANCE_ACQUISITION_PROFILE: AcquisitionRule(
            capture.ACCEPTANCE_ACQUISITION_PROFILE,
            "GET",
            "pinned-active-entry-download",
            "text/csv",
            "attachment-csv",
            acceptance_effective_families,
        ),
        capture.CONTEST_DETAIL_ACQUISITION_PROFILE: AcquisitionRule(
            capture.CONTEST_DETAIL_ACQUISITION_PROFILE,
            "GET",
            "contest-detail-by-id",
            "application/json",
            "none",
            detail_families,
        ),
        capture.STANDINGS_ACQUISITION_PROFILE: AcquisitionRule(
            capture.STANDINGS_ACQUISITION_PROFILE,
            "GET",
            "full-standings-by-id",
            "text/csv",
            "attachment-csv",
            standings_effective_families,
        ),
    }
    role_contest_ids = {
        role: pin.contest_id for role, pin in capture.A5_ROLE_TABLE.items()
    }
    provisional = CollectorAllowlist(
        source_commit=source_commit,
        code_sha256=code_sha256,
        image_digest=image_digest,
        collector_service_account=collector_service_account,
        authority_reader_service_account=authority_reader_service_account,
        session_profile=COLLECTOR_SESSION_PROFILE,
        project=LIVE_PROJECT,
        evidence_bucket=LIVE_EVIDENCE_BUCKET,
        evidence_prefix=LIVE_EVIDENCE_PREFIX,
        authority_bucket=LIVE_AUTHORITY_BUCKET,
        authority_prefix=LIVE_AUTHORITY_PREFIX,
        provider_capture_prefix=LIVE_PROVIDER_CAPTURE_PREFIX,
        draft_group_id=capture.EXPECTED_DRAFT_GROUP_ID,
        role_contest_ids=MappingProxyType(role_contest_ids),
        rules=MappingProxyType(rules),
        governance=governance,
        allowlist_sha256="0" * 64,
    )
    digest = canonical_sha256(provisional.semantic_body())
    return CollectorAllowlist(**{**provisional.__dict__, "allowlist_sha256": digest})


def live_collector_allowlist() -> CollectorAllowlist:
    """Return the immutable live allowlist, or fail before any provider use."""

    missing = [
        name
        for name, value in (
            ("collector source commit", live_pins.PINNED_COLLECTOR_SOURCE_COMMIT),
            ("collector code SHA", live_pins.PINNED_COLLECTOR_CODE_SHA256),
            ("collector image digest", live_pins.PINNED_COLLECTOR_IMAGE_DIGEST),
            ("collector service account", live_pins.PINNED_COLLECTOR_SERVICE_ACCOUNT),
            (
                "authority reader service account",
                live_pins.PINNED_AUTHORITY_READER_SERVICE_ACCOUNT,
            ),
            (
                "authority bucket metageneration",
                live_pins.PINNED_AUTHORITY_BUCKET_METAGENERATION,
            ),
            ("authority retention", live_pins.PINNED_AUTHORITY_RETENTION_SECONDS),
            (
                "authority IAM policy version",
                live_pins.PINNED_AUTHORITY_IAM_POLICY_VERSION,
            ),
            (
                "authority IAM policy etag",
                live_pins.PINNED_AUTHORITY_IAM_POLICY_ETAG_BASE64,
            ),
            (
                "authority IAM policy SHA",
                live_pins.PINNED_AUTHORITY_IAM_POLICY_SHA256,
            ),
            (
                "authority IAM policy bindings",
                live_pins.PINNED_AUTHORITY_IAM_POLICY_BINDINGS,
            ),
            (
                "acceptance effective locator families",
                live_pins.PINNED_ACCEPTANCE_EFFECTIVE_LOCATOR_FAMILIES,
            ),
            (
                "contest-detail effective locator families",
                live_pins.PINNED_CONTEST_DETAIL_EFFECTIVE_LOCATOR_FAMILIES,
            ),
            (
                "standings effective locator families",
                live_pins.PINNED_STANDINGS_EFFECTIVE_LOCATOR_FAMILIES,
            ),
            ("acceptance download locator", capture.PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR),
        )
        if value is None
    ]
    if missing:
        _fail("live DraftKings acquisition remains HOLD; missing " + ", ".join(missing))

    # The effective response/CDN families are populated only from the later
    # independently reviewed, redacted real-transport receipt.
    def families(
        raw: tuple[tuple[str, str, str], ...] | None,
    ) -> tuple[LocatorFamily, ...]:
        if raw is None:  # unreachable after the missing-pin gate above
            raise AssertionError("live locator families are absent")
        return tuple(LocatorFamily(*item) for item in raw)

    pinned_bindings = live_pins.PINNED_AUTHORITY_IAM_POLICY_BINDINGS
    if pinned_bindings is None:  # unreachable after the missing-pin gate
        raise AssertionError("live IAM bindings are absent")
    governance = _validate_governance(
        {
            "authority_bucket_metageneration": str(
                live_pins.PINNED_AUTHORITY_BUCKET_METAGENERATION
            ),
            "retention_seconds": int(live_pins.PINNED_AUTHORITY_RETENTION_SECONDS),
            "retention_locked": True,
            "versioning_enabled": True,
            "uniform_bucket_level_access": True,
            "iam_policy_version": live_pins.PINNED_AUTHORITY_IAM_POLICY_VERSION,
            "iam_policy_etag_base64": (
                live_pins.PINNED_AUTHORITY_IAM_POLICY_ETAG_BASE64
            ),
            "iam_policy_sha256": live_pins.PINNED_AUTHORITY_IAM_POLICY_SHA256,
            "iam_policy_bindings": list(pinned_bindings),
            "object_mutator_members": [
                f"serviceAccount:{live_pins.PINNED_COLLECTOR_SERVICE_ACCOUNT}"
            ],
            "object_viewer_members": sorted(
                {
                    f"serviceAccount:{live_pins.PINNED_COLLECTOR_SERVICE_ACCOUNT}",
                    f"serviceAccount:{live_pins.PINNED_AUTHORITY_READER_SERVICE_ACCOUNT}",
                }
            ),
            "public_members": [],
        },
        label="pinned live authority governance",
    )
    return _build_allowlist(
        source_commit=str(live_pins.PINNED_COLLECTOR_SOURCE_COMMIT),
        code_sha256=str(live_pins.PINNED_COLLECTOR_CODE_SHA256),
        image_digest=str(live_pins.PINNED_COLLECTOR_IMAGE_DIGEST),
        collector_service_account=str(live_pins.PINNED_COLLECTOR_SERVICE_ACCOUNT),
        authority_reader_service_account=str(
            live_pins.PINNED_AUTHORITY_READER_SERVICE_ACCOUNT
        ),
        governance=governance,
        acceptance_effective_families=families(
            live_pins.PINNED_ACCEPTANCE_EFFECTIVE_LOCATOR_FAMILIES
        ),
        contest_detail_effective_families=families(
            live_pins.PINNED_CONTEST_DETAIL_EFFECTIVE_LOCATOR_FAMILIES
        ),
        standings_effective_families=families(
            live_pins.PINNED_STANDINGS_EFFECTIVE_LOCATOR_FAMILIES
        ),
    )


def _request_locator(*, profile: str, role: str, policy: CollectorAllowlist) -> str:
    if profile not in policy.rules:
        _fail("acquisition profile is outside the exact allowlist")
    try:
        pin = capture.A5_ROLE_TABLE[role]
    except KeyError as exc:
        raise Week1A5DraftKingsAcquisitionError(
            "contest role is outside the exact A5 allowlist"
        ) from exc
    if policy.role_contest_ids.get(role) != pin.contest_id:
        _fail("collector role/contest allowlist is cross-wired")
    if profile == capture.ACCEPTANCE_ACQUISITION_PROFILE:
        if capture.PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR is None:
            _fail("live acceptance acquisition locator is not pinned")
        locator = capture.PINNED_ACCEPTANCE_DOWNLOAD_LOCATOR
    elif profile == capture.CONTEST_DETAIL_ACQUISITION_PROFILE:
        locator = f"{capture.FINAL_FIELD_SOURCE_LOCATOR_PREFIX}{pin.contest_id}"
    elif profile == capture.STANDINGS_ACQUISITION_PROFILE:
        locator = f"{capture.FINAL_STANDINGS_SOURCE_LOCATOR_PREFIX}{pin.contest_id}"
    else:  # already closed above
        raise AssertionError(profile)
    return _canonical_url(locator, label="collector request locator")


def _normalize_transport_event(
    value: TransportEvent,
    *,
    rule: AcquisitionRule,
    request_locator: str,
    policy: CollectorAllowlist,
) -> dict[str, object]:
    if not isinstance(value, TransportEvent):
        _fail("collector transport did not return its sealed event type")
    if not isinstance(value.body, bytes) or not value.body:
        _fail("collector transport response body is empty")
    observed_at, _ = _timestamp(value.observed_at, label="transport observed_at")
    if value.session_profile != policy.session_profile:
        _fail("transport session profile differs from the exact allowlist")
    if not value.hops:
        _fail("transport event has no response chain")
    hops: list[dict[str, object]] = []
    raw_locators: list[str] = []
    for ordinal, hop in enumerate(value.hops):
        if not isinstance(hop, TransportHop):
            _fail("transport redirect chain contains another type")
        locator = _canonical_url(hop.locator, label=f"transport hop {ordinal} locator")
        if type(hop.status) is not int or not 100 <= hop.status <= 599:
            _fail("transport hop status is invalid")
        target = (
            _canonical_url(
                urljoin(locator, hop.redirect_target),
                label=f"transport hop {ordinal} redirect target",
            )
            if hop.redirect_target is not None
            else None
        )
        if ordinal < len(value.hops) - 1:
            if hop.status not in {301, 302, 303, 307, 308} or target is None:
                _fail("nonterminal transport hop is not one explicit redirect")
        elif hop.status != 200 or target is not None:
            _fail("terminal transport hop must be a nonredirect HTTP 200")
        raw_locators.append(locator)
        redacted = _redact_url(locator)
        target_redacted = _redact_url(target) if target is not None else None
        hops.append(
            {
                "ordinal": ordinal,
                "status": hop.status,
                **redacted,
                "redirect_target": target_redacted,
            }
        )
    if raw_locators[0] != request_locator:
        _fail("transport chain does not start at the code-derived request locator")
    for ordinal, hop in enumerate(value.hops[:-1]):
        target = _canonical_url(
            urljoin(raw_locators[ordinal], str(hop.redirect_target)),
            label="redirect target",
        )
        if target != raw_locators[ordinal + 1]:
            _fail("transport redirect chain is discontinuous")
    for locator in raw_locators:
        if not any(
            family.accepts(locator) for family in rule.effective_locator_families
        ):
            _fail("transport locator is outside the profile's exact family allowlist")
    content_type = _string(
        value.response_content_type, label="transport response content type"
    ).lower()
    if content_type.split(";", 1)[0].strip() != rule.media_type:
        _fail("transport response media type differs from the exact profile")
    disposition = value.response_content_disposition
    if rule.disposition == "none":
        if disposition is not None:
            _fail("transport unexpectedly reports a download disposition")
    elif rule.disposition == "attachment-csv":
        lowered = _string(disposition, label="transport content disposition").lower()
        if "attachment" not in lowered or ".csv" not in lowered:
            _fail("transport download disposition is not an attached CSV")
    else:
        raise AssertionError(rule.disposition)
    return {
        "schema_version": COLLECTOR_TRANSPORT_EVENT_SCHEMA,
        "request_method": rule.method,
        "requested_locator": _redact_url(request_locator),
        "effective_locator": _redact_url(raw_locators[-1]),
        "redirect_chain": hops,
        "observed_at": observed_at,
        "response_status": 200,
        "response_content_type": content_type,
        "response_content_disposition": disposition,
        "session_profile": value.session_profile,
        "body_sha256": hashlib.sha256(value.body).hexdigest(),
        "body_bytes": len(value.body),
    }


def _validate_ledger_transport_event(
    value: object,
    *,
    policy: CollectorAllowlist,
    profile: str,
    role: str,
    receipt: Mapping[str, object],
    raw_identity: Mapping[str, object],
) -> dict[str, object]:
    """Revalidate the collector's complete redacted HTTP event projection."""

    event = _mapping(value, label="ledger transport event")
    _exact(event, _TRANSPORT_EVENT_FIELDS, label="ledger transport event")
    if event["schema_version"] != COLLECTOR_TRANSPORT_EVENT_SCHEMA:
        _fail("collector ledger transport-event schema differs")
    rule = policy.rules[profile]
    if event["request_method"] != rule.method:
        _fail("collector ledger request method differs from the exact allowlist")
    requested = _validate_redacted_locator(
        event["requested_locator"], label="transport requested locator"
    )
    expected_locator = _request_locator(profile=profile, role=role, policy=policy)
    if requested != _redact_url(expected_locator):
        _fail("collector ledger requested locator differs")
    effective = _validate_redacted_locator(
        event["effective_locator"], label="transport effective locator"
    )
    raw_chain = event["redirect_chain"]
    if (
        isinstance(raw_chain, (str, bytes, bytearray))
        or not isinstance(raw_chain, Sequence)
        or not raw_chain
    ):
        _fail("collector ledger redirect chain must be a nonempty array")
    chain: list[dict[str, object]] = []
    for ordinal, raw_hop in enumerate(raw_chain):
        hop = _mapping(raw_hop, label=f"transport redirect_chain[{ordinal}]")
        _exact(
            hop,
            _TRANSPORT_HOP_FIELDS,
            label=f"transport redirect_chain[{ordinal}]",
        )
        if hop["ordinal"] != ordinal:
            _fail("collector ledger redirect-chain ordinal differs")
        status = hop["status"]
        if type(status) is not int or not 100 <= status <= 599:
            _fail("collector ledger redirect-chain status is invalid")
        locator = _validate_redacted_locator(
            {key: hop[key] for key in _LOCATOR_PROJECTION_FIELDS},
            label=f"transport redirect_chain[{ordinal}].locator",
        )
        target = (
            _validate_redacted_locator(
                hop["redirect_target"],
                label=f"transport redirect_chain[{ordinal}].redirect_target",
            )
            if hop["redirect_target"] is not None
            else None
        )
        if ordinal < len(raw_chain) - 1:
            if status not in {301, 302, 303, 307, 308} or target is None:
                _fail("collector ledger nonterminal hop is not one redirect")
        elif status != 200 or target is not None:
            _fail("collector ledger terminal hop is not a nonredirect HTTP 200")
        if not any(
            family.accepts(str(locator["redacted_locator"]))
            for family in rule.effective_locator_families
        ):
            _fail("collector ledger redirect locator is outside the exact allowlist")
        chain.append({"locator": locator, "target": target, "status": status})
    if chain[0]["locator"] != requested or chain[-1]["locator"] != effective:
        _fail("collector ledger redirect-chain endpoints differ")
    for ordinal, hop in enumerate(chain[:-1]):
        if hop["target"] != chain[ordinal + 1]["locator"]:
            _fail("collector ledger redirect chain is discontinuous")
    observed_at, _ = _timestamp(event["observed_at"], label="transport observed_at")
    if observed_at != receipt["observed_at"]:
        _fail("collector ledger observation time differs from its receipt")
    if (
        event["response_status"] != 200
        or event["response_status"] != receipt["response_status"]
    ):
        _fail("collector ledger response status differs from its receipt")
    content_type = _string(
        event["response_content_type"], label="transport response content type"
    ).lower()
    if (
        content_type != receipt["response_content_type"]
        or content_type.split(";", 1)[0].strip() != rule.media_type
    ):
        _fail("collector ledger response media type differs")
    if event["response_content_disposition"] != receipt["response_content_disposition"]:
        _fail("collector ledger response disposition differs from its receipt")
    disposition = event["response_content_disposition"]
    if rule.disposition == "none":
        if disposition is not None:
            _fail("collector ledger unexpectedly records a download disposition")
    elif rule.disposition == "attachment-csv":
        lowered = _string(
            disposition, label="transport response content disposition"
        ).lower()
        if "attachment" not in lowered or ".csv" not in lowered:
            _fail("collector ledger disposition is not an attached CSV")
    else:  # pragma: no cover - construction closes this enum
        raise AssertionError(rule.disposition)
    if event["session_profile"] != policy.session_profile:
        _fail("collector ledger session profile differs from the exact allowlist")
    retained_raw = _identity(raw_identity, label="ledger transport raw identity")
    if (
        event["body_sha256"] != retained_raw["sha256"]
        or event["body_bytes"] != retained_raw["bytes"]
    ):
        _fail("collector ledger transport body differs from its raw object")
    return event


def _event_id(now: datetime | None = None) -> str:
    retained = (now or datetime.now(UTC)).astimezone(UTC)
    return f"dk-a5-{retained.strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(16)}"


def _publish_bytes(
    store: capture.ImmutableObjectStore,
    *,
    uri: str,
    raw: bytes,
    content_type: str,
    label: str,
) -> tuple[dict[str, object], str]:
    try:
        receipt = _mapping(
            store.publish_create_once(uri=uri, raw=raw, content_type=content_type),
            label=f"{label} publication receipt",
        )
    except Exception as exc:
        raise Week1A5DraftKingsAcquisitionError(
            f"{label} create-once publication failed"
        ) from exc
    _exact(receipt, {"identity", "created_at"}, label=f"{label} publication receipt")
    identity = _identity(receipt["identity"], label=f"{label} identity")
    if identity["uri"] != uri:
        _fail(f"{label} publisher returned another URI")
    if (
        identity["bytes"] != len(raw)
        or identity["sha256"] != hashlib.sha256(raw).hexdigest()
    ):
        _fail(f"{label} publisher returned a false content identity")
    reopened = _mapping(
        store.read_exact(identity=identity), label=f"{label} exact reopen"
    )
    _exact(reopened, {"identity", "created_at", "raw"}, label=f"{label} exact reopen")
    if _identity(reopened["identity"], label=f"reopened {label} identity") != identity:
        _fail(f"{label} exact reopen changed identity")
    if reopened["raw"] != raw:
        _fail(f"{label} exact reopen changed bytes")
    created_at, _ = _timestamp(reopened["created_at"], label=f"{label}.created_at")
    return identity, created_at


def _ledger_uri(
    policy: CollectorAllowlist, receipt_identity: Mapping[str, object]
) -> str:
    identity = _identity(receipt_identity, label="acquisition receipt identity")
    return (
        f"gs://{policy.authority_bucket}/{policy.authority_prefix}/"
        f"receipts/{identity['sha256']}/{identity['generation']}.json"
    )


def _provider_runtime_service_account() -> str:
    try:
        import requests

        response = requests.get(
            (
                "http://metadata.google.internal/computeMetadata/v1/instance/"
                "service-accounts/default/email"
            ),
            headers={"Metadata-Flavor": "Google"},
            timeout=2,
        )
        response.raise_for_status()
        runtime_service_account = response.text.strip()
    except Exception as exc:
        raise Week1A5DraftKingsAcquisitionError(
            "runtime identity cannot be read from provider metadata"
        ) from exc
    return runtime_service_account


def _collector_runtime_matches(policy: CollectorAllowlist) -> None:
    if _module_sha256() != policy.code_sha256:
        _fail("running collector module differs from its exact code allowlist")
    if os.environ.get("CODE_SHA") != policy.source_commit:
        _fail("running collector source commit differs from its exact allowlist")
    if os.environ.get("COLLECTOR_IMAGE_DIGEST") != policy.image_digest:
        _fail("running collector image differs from its exact allowlist")
    if _provider_runtime_service_account() != policy.collector_service_account:
        _fail("running collector identity differs from its exact allowlist")


def _authority_runtime_matches(policy: CollectorAllowlist) -> None:
    if _provider_runtime_service_account() != policy.authority_reader_service_account:
        _fail("running authority identity differs from its exact allowlist")


def _collect_with_reviewed_ports(
    *,
    policy: CollectorAllowlist,
    evidence_store: _EvidenceStore,
    ledger_writer: _LedgerWriter,
    transport: _Transport,
    profile: str,
    contest_role: str,
    authority_event_id: str,
) -> CollectorIssuance:
    """Private test seam for the exact production collector state machine."""

    if _EVENT_ID.fullmatch(authority_event_id) is None:
        _fail("collector event ID was not internally generated")
    if canonical_sha256(policy.semantic_body()) != policy.allowlist_sha256:
        _fail("collector allowlist semantic identity differs")
    request_locator = _request_locator(
        profile=profile, role=contest_role, policy=policy
    )
    rule = policy.rules[profile]
    pin = capture.A5_ROLE_TABLE[contest_role]
    event = transport.perform(method=rule.method, locator=request_locator)
    transport_projection = _normalize_transport_event(
        event, rule=rule, request_locator=request_locator, policy=policy
    )
    base = (
        f"gs://{policy.evidence_bucket}/{policy.evidence_prefix}/{authority_event_id}"
    )
    _assert_uri_scope(
        f"{base}/raw.bin",
        bucket=policy.evidence_bucket,
        prefix=policy.evidence_prefix,
        label="raw acquisition URI",
    )
    raw_identity, raw_created_at = _publish_bytes(
        evidence_store,
        uri=f"{base}/raw.bin",
        raw=event.body,
        content_type=transport_projection["response_content_type"],
        label="provider raw body",
    )
    trace = {
        "schema_version": capture.PROVIDER_TRANSPORT_TRACE_SCHEMA,
        "authority_event_id": authority_event_id,
        "request_method": rule.method,
        "canonical_locator": request_locator,
        "authenticated_surface": capture.PROVIDER_AUTHENTICATED_SURFACE,
        "observed_at": transport_projection["observed_at"],
        "response_status": transport_projection["response_status"],
        "response_content_type": transport_projection["response_content_type"],
        "response_content_disposition": transport_projection[
            "response_content_disposition"
        ],
        "collector_source_commit": policy.source_commit,
        "collector_code_sha256": policy.code_sha256,
        "collector_image_digest": policy.image_digest,
        "raw_object_identity": raw_identity,
    }
    trace_raw = canonical_json_bytes(trace)
    trace_identity, _ = _publish_bytes(
        evidence_store,
        uri=f"{base}/transport-trace.json",
        raw=trace_raw,
        content_type="application/json",
        label="provider transport trace",
    )
    acquisition = capture.seal_semantic_artifact(
        {
            "schema_version": capture.PROVIDER_ACQUISITION_SCHEMA,
            "authority_profile": capture.PROVIDER_ACQUISITION_AUTHORITY_PROFILE,
            "authority_event_id": authority_event_id,
            "acquisition_profile": profile,
            "source_system": "draftkings",
            "authenticated_surface": capture.PROVIDER_AUTHENTICATED_SURFACE,
            "request_method": rule.method,
            "canonical_locator": request_locator,
            "contest_role": pin.role,
            "contest_id": pin.contest_id,
            "draft_group_id": policy.draft_group_id,
            "observed_at": transport_projection["observed_at"],
            "response_status": transport_projection["response_status"],
            "response_content_type": transport_projection["response_content_type"],
            "response_content_disposition": transport_projection[
                "response_content_disposition"
            ],
            "collector_source_commit": policy.source_commit,
            "collector_code_sha256": policy.code_sha256,
            "collector_image_digest": policy.image_digest,
            "transport_trace_identity": trace_identity,
            "raw_object_identity": raw_identity,
            "raw_provider_created_at": raw_created_at,
        }
    )
    publication = capture.publish_semantic_artifact(
        evidence_store,
        uri=f"{base}/acquisition-receipt.json",
        artifact=acquisition,
    )
    receipt_identity = _identity(
        publication["artifact_identity"], label="acquisition receipt identity"
    )
    receipt_created_at = _string(
        publication["created_at"], label="acquisition receipt created_at"
    )
    ledger_body = capture.seal_semantic_artifact(
        {
            "schema_version": COLLECTOR_LEDGER_SCHEMA,
            "authority_profile": COLLECTOR_AUTHORITY_PROFILE,
            "authority_event_id": authority_event_id,
            "allowlist_sha256": policy.allowlist_sha256,
            "acquisition_profile": profile,
            "contest_role": pin.role,
            "contest_id": pin.contest_id,
            "draft_group_id": policy.draft_group_id,
            "collector_source_commit": policy.source_commit,
            "collector_code_sha256": policy.code_sha256,
            "collector_image_digest": policy.image_digest,
            "collector_service_account": policy.collector_service_account,
            "session_profile": policy.session_profile,
            "transport_event": transport_projection,
            "transport_trace_identity": trace_identity,
            "raw_object_identity": raw_identity,
            "acquisition_receipt_identity": receipt_identity,
            "acquisition_receipt_semantic_sha256": publication["semantic_sha256"],
            "acquisition_receipt_provider_created_at": receipt_created_at,
        }
    )
    ledger_raw = canonical_json_bytes(ledger_body)
    ledger_uri = _ledger_uri(policy, receipt_identity)
    _assert_uri_scope(
        ledger_uri,
        bucket=policy.authority_bucket,
        prefix=policy.authority_prefix,
        label="authority ledger URI",
    )
    ledger_identity, _ = _publish_bytes(
        ledger_writer,
        uri=ledger_uri,
        raw=ledger_raw,
        content_type="application/json",
        label="collector issuance ledger event",
    )
    return CollectorIssuance(
        acquisition_receipt={
            "artifact_identity": receipt_identity,
            "semantic_sha256": publication["semantic_sha256"],
        },
        ledger_identity=ledger_identity,
        authority_event_id=authority_event_id,
        redacted_transport=transport_projection,
    )


def _parse_semantic(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Week1A5DraftKingsAcquisitionError(f"{label} is not JSON") from exc
    item = _mapping(value, label=label)
    if canonical_json_bytes(item) != raw:
        _fail(f"{label} is not canonical JSON")
    retained = _sha(item.pop("semantic_sha256", None), label=f"{label}.semantic_sha256")
    if canonical_sha256(item) != retained:
        _fail(f"{label} semantic SHA differs")
    item["semantic_sha256"] = retained
    return item


def _read_exact_evidence(
    store: _EvidenceStore,
    identity: object,
    *,
    policy: CollectorAllowlist,
    label: str,
) -> tuple[dict[str, object], str, datetime, bytes]:
    retained = _identity(identity, label=f"{label} identity")
    _assert_uri_scope(
        str(retained["uri"]),
        bucket=policy.evidence_bucket,
        prefix=policy.evidence_prefix,
        label=f"{label} identity",
    )
    reopened = _mapping(
        store.read_exact(identity=retained), label=f"{label} exact read"
    )
    _exact(reopened, {"identity", "created_at", "raw"}, label=f"{label} exact read")
    if _identity(reopened["identity"], label=f"reopened {label} identity") != retained:
        _fail(f"{label} exact read changed identity")
    raw = reopened["raw"]
    if not isinstance(raw, bytes) or (
        len(raw) != retained["bytes"]
        or hashlib.sha256(raw).hexdigest() != retained["sha256"]
    ):
        _fail(f"{label} exact read changed bytes")
    created_at, created = _timestamp(
        reopened["created_at"], label=f"{label}.created_at"
    )
    return retained, created_at, created, raw


class _ProductionDraftKingsAcquisitionAuthority:
    """Read-only adapter over the collector-only create-once ledger.

    This class is an implementation detail, not a Python trust boundary.  The
    production trust boundary is the repository-owned live call graph, which
    constructs it with fixed stores, policy, runtime identity and an exact
    publication-time boundary.  Tests use one explicitly private seam.
    """

    __slots__ = (
        "__boundary",
        "__evidence",
        "__ledger",
        "__ledger_evidence",
        "__policy",
    )

    def __init__(
        self,
        *,
        evidence: _EvidenceStore,
        ledger: _LedgerReader,
        policy: CollectorAllowlist,
        boundary: _AuthorityReadBoundary,
    ) -> None:
        self.__evidence = evidence
        self.__ledger = ledger
        self.__policy = policy
        self.__boundary = boundary
        self.__ledger_evidence: dict[str, dict[str, object]] = {}

    def read_authenticated_acquisition(
        self, *, identity: Mapping[str, object]
    ) -> Mapping[str, object]:
        receipt_identity = _identity(identity, label="requested acquisition receipt")
        policy = self.__policy
        if canonical_sha256(policy.semantic_body()) != policy.allowlist_sha256:
            _fail("production authority allowlist semantic identity differs")
        _assert_uri_scope(
            str(receipt_identity["uri"]),
            bucket=policy.evidence_bucket,
            prefix=policy.evidence_prefix,
            label="requested acquisition receipt",
        )
        governance = _validate_governance(
            self.__ledger.governance(), label="live authority-ledger governance"
        )
        if governance != policy.governance:
            _fail("authority-ledger governance differs from its exact allowlist")
        ledger_uri = _ledger_uri(policy, receipt_identity)
        reopened_ledger = _mapping(
            self.__ledger.read_single_generation(uri=ledger_uri),
            label="authority ledger exact read",
        )
        _exact(
            reopened_ledger,
            {"identity", "created_at", "raw"},
            label="authority ledger exact read",
        )
        ledger_identity = _identity(
            reopened_ledger["identity"], label="authority ledger identity"
        )
        if ledger_identity["uri"] != ledger_uri:
            _fail("authority ledger returned another object")
        ledger_raw = reopened_ledger["raw"]
        if not isinstance(ledger_raw, bytes) or (
            len(ledger_raw) != ledger_identity["bytes"]
            or hashlib.sha256(ledger_raw).hexdigest() != ledger_identity["sha256"]
        ):
            _fail("authority ledger exact bytes differ")
        ledger_created_at, ledger_created = _timestamp(
            reopened_ledger["created_at"], label="authority ledger created_at"
        )
        event = _parse_semantic(ledger_raw, label="collector issuance ledger event")
        expected_fields = {
            "schema_version",
            "authority_profile",
            "authority_event_id",
            "allowlist_sha256",
            "acquisition_profile",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "collector_source_commit",
            "collector_code_sha256",
            "collector_image_digest",
            "collector_service_account",
            "session_profile",
            "transport_event",
            "transport_trace_identity",
            "raw_object_identity",
            "acquisition_receipt_identity",
            "acquisition_receipt_semantic_sha256",
            "acquisition_receipt_provider_created_at",
            "semantic_sha256",
        }
        _exact(event, expected_fields, label="collector issuance ledger event")
        if event["schema_version"] != COLLECTOR_LEDGER_SCHEMA:
            _fail("collector issuance ledger schema differs")
        if event["authority_profile"] != COLLECTOR_AUTHORITY_PROFILE:
            _fail("collector issuance authority profile differs")
        event_id = _string(event["authority_event_id"], label="authority event ID")
        if _EVENT_ID.fullmatch(event_id) is None:
            _fail("authority event ID differs from the collector format")
        if event["allowlist_sha256"] != policy.allowlist_sha256:
            _fail("collector issuance used another allowlist")
        if (
            _identity(
                event["acquisition_receipt_identity"], label="ledger receipt identity"
            )
            != receipt_identity
        ):
            _fail("collector ledger is cross-wired to another receipt generation")
        if (
            event["collector_source_commit"] != policy.source_commit
            or event["collector_code_sha256"] != policy.code_sha256
            or event["collector_image_digest"] != policy.image_digest
            or event["collector_service_account"] != policy.collector_service_account
            or event["session_profile"] != policy.session_profile
            or event["draft_group_id"] != policy.draft_group_id
        ):
            _fail("collector issuance identity differs from the exact allowlist")
        role = _string(event["contest_role"], label="ledger contest role")
        if policy.role_contest_ids.get(role) != event["contest_id"]:
            _fail("collector issuance role/contest is cross-wired")
        profile = _string(event["acquisition_profile"], label="ledger profile")
        if profile not in policy.rules:
            _fail("collector issuance profile is outside the exact allowlist")
        boundary = self.__boundary
        if profile not in boundary.profiles:
            _fail("collector issuance profile is outside this repository-owned read")
        if ledger_created > boundary.not_after:
            _fail("collector ledger was created after the exact publication cutoff")
        if boundary.phase == "prelock":
            _, lock = _timestamp(capture.EXPECTED_LOCK_UTC, label="A5 lock")
            if ledger_created >= lock:
                _fail("pre-lock collector ledger was not created strictly before lock")
        elif boundary.phase == "postlock":
            if boundary.not_before is None or ledger_created <= boundary.not_before:
                _fail("post-lock collector ledger was not created strictly after lock")
        else:  # pragma: no cover - the private constructor closes this enum
            raise AssertionError(boundary.phase)
        (
            reopened_receipt_identity,
            receipt_created_at,
            receipt_created,
            receipt_raw,
        ) = _read_exact_evidence(
            self.__evidence,
            receipt_identity,
            policy=policy,
            label="authority receipt",
        )
        if reopened_receipt_identity != receipt_identity:  # defensive clarity
            _fail("authority receipt exact reopen differs")
        if ledger_created < receipt_created:
            _fail("collector ledger predates the receipt it issues")
        if event["acquisition_receipt_provider_created_at"] != receipt_created_at:
            _fail("collector ledger receipt creation time differs")
        receipt = _parse_semantic(receipt_raw, label="authority acquisition receipt")
        if receipt["semantic_sha256"] != event["acquisition_receipt_semantic_sha256"]:
            _fail("collector ledger receipt semantic identity differs")
        pin = capture.A5_ROLE_TABLE[role]
        retained = capture._validate_acquisition_receipt_body(
            receipt, expected_profile=profile, pin=pin
        )
        if (
            retained["authority_event_id"] != event_id
            or retained["contest_id"] != event["contest_id"]
            or retained["draft_group_id"] != event["draft_group_id"]
            or retained["collector_source_commit"] != event["collector_source_commit"]
            or retained["collector_code_sha256"] != event["collector_code_sha256"]
            or retained["collector_image_digest"] != event["collector_image_digest"]
            or _identity(retained["raw_object_identity"], label="receipt raw identity")
            != _identity(event["raw_object_identity"], label="ledger raw identity")
            or _identity(
                retained["transport_trace_identity"], label="receipt trace identity"
            )
            != _identity(
                event["transport_trace_identity"], label="ledger trace identity"
            )
        ):
            _fail("collector ledger differs from its exact acquisition receipt")
        raw_identity = _identity(
            event["raw_object_identity"], label="ledger raw identity"
        )
        trace_identity = _identity(
            event["transport_trace_identity"], label="ledger trace identity"
        )
        _, raw_created_at, raw_created, raw = _read_exact_evidence(
            self.__evidence,
            raw_identity,
            policy=policy,
            label="authority-bound provider raw object",
        )
        _, _, trace_created, trace_raw = _read_exact_evidence(
            self.__evidence,
            trace_identity,
            policy=policy,
            label="authority-bound provider transport trace",
        )
        if raw_created_at != retained["raw_provider_created_at"]:
            _fail("collector raw-object provider creation time differs")
        if raw_created > receipt_created or trace_created > receipt_created:
            _fail("collector evidence was archived after its acquisition receipt")
        observed_at, observed = _timestamp(
            retained["observed_at"], label="authority acquisition observed_at"
        )
        if observed > raw_created or observed > trace_created:
            _fail("collector evidence archives predate the HTTP observation")
        try:
            trace_value = json.loads(trace_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Week1A5DraftKingsAcquisitionError(
                "authority-bound provider transport trace is not JSON"
            ) from exc
        trace = _mapping(trace_value, label="authority-bound provider transport trace")
        if canonical_json_bytes(trace) != trace_raw:
            _fail("authority-bound provider transport trace is not canonical JSON")
        trace_fields = {
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
        }
        _exact(
            trace,
            trace_fields,
            label="authority-bound provider transport trace",
        )
        expected_trace = {
            "schema_version": capture.PROVIDER_TRANSPORT_TRACE_SCHEMA,
            **{key: retained[key] for key in trace_fields if key != "schema_version"},
        }
        if trace != expected_trace:
            _fail("collector receipt differs from its exact transport trace")
        if raw_identity["sha256"] != hashlib.sha256(raw).hexdigest():
            _fail("collector raw object body hash differs")
        _validate_ledger_transport_event(
            event["transport_event"],
            policy=policy,
            profile=profile,
            role=role,
            receipt=retained,
            raw_identity=raw_identity,
        )
        # Retain the normalized value to make the time comparison explicit in
        # this authority rather than relying on the downstream P2 builder.
        if observed_at != retained["observed_at"]:  # pragma: no cover
            _fail("collector observation time is not canonical")
        # Reopen through the sole-generation reader after all dependent
        # evidence.  A timeless receipt is never enough: the same exact
        # provider generation and creation time must remain authoritative at
        # the end of every read.
        final_ledger = _mapping(
            self.__ledger.read_single_generation(uri=ledger_uri),
            label="authority ledger final exact read",
        )
        _exact(
            final_ledger,
            {"identity", "created_at", "raw"},
            label="authority ledger final exact read",
        )
        if (
            _identity(final_ledger["identity"], label="final authority ledger identity")
            != ledger_identity
            or _timestamp(
                final_ledger["created_at"], label="final authority ledger created_at"
            )[0]
            != ledger_created_at
            or final_ledger["raw"] != ledger_raw
        ):
            _fail("authority ledger changed during the authenticated read")
        final_governance = _validate_governance(
            self.__ledger.governance(),
            label="final live authority-ledger governance",
        )
        if final_governance != policy.governance:
            _fail("authority-ledger governance changed during the authenticated read")
        self.__ledger_evidence[event_id] = {
            "identity": ledger_identity,
            "created_at": ledger_created_at,
            "publish_by": boundary.publish_by,
        }
        return {
            "identity": receipt_identity,
            "created_at": receipt_created_at,
            "raw": receipt_raw,
            "authority_event_id": event_id,
        }

    def _ledger_evidence_for(self, event_id: str) -> dict[str, object]:
        """Internal publisher check; never part of the injected P2 protocol."""

        if event_id not in self.__ledger_evidence:
            _fail("derived capture did not authenticate its ledger in this call")
        return dict(self.__ledger_evidence[event_id])


def _authority_boundary(
    *, profiles: tuple[str, ...], phase: str, publish_by: object
) -> _AuthorityReadBoundary:
    if not profiles or profiles != tuple(sorted(set(profiles))):
        _fail("authority read profiles must be one exact sorted set")
    if any(profile not in _CAPTURE_PROFILES for profile in profiles):
        _fail("authority read profile is unsupported")
    publish_text, cutoff = capture._publish_by(
        publish_by,
        label="repository-owned authority publish_by",
        phase=phase,
    )
    _, lock = _timestamp(capture.EXPECTED_LOCK_UTC, label="A5 lock")
    expected = (
        (capture.ACCEPTANCE_ACQUISITION_PROFILE,)
        if phase == "prelock"
        else tuple(
            sorted(
                (
                    capture.CONTEST_DETAIL_ACQUISITION_PROFILE,
                    capture.STANDINGS_ACQUISITION_PROFILE,
                )
            )
        )
    )
    if profiles != expected:
        _fail("authority read profiles differ from the exact phase")
    return _AuthorityReadBoundary(
        profiles=profiles,
        phase=phase,
        publish_by=publish_text,
        not_after=cutoff,
        not_before=lock if phase == "postlock" else None,
    )


_CAPTURE_PROFILES: Final = frozenset(
    {
        capture.ACCEPTANCE_ACQUISITION_PROFILE,
        capture.CONTEST_DETAIL_ACQUISITION_PROFILE,
        capture.STANDINGS_ACQUISITION_PROFILE,
    }
)


def _authority_from_reviewed_ports(
    *,
    policy: CollectorAllowlist,
    evidence: _EvidenceStore,
    ledger: _LedgerReader,
    profiles: tuple[str, ...],
    phase: str,
    publish_by: object,
) -> capture.AuthenticatedProviderAcquisitionAuthority:
    """Private offline construction seam; never accepted by a live publisher."""

    return _ProductionDraftKingsAcquisitionAuthority(
        evidence=evidence,
        ledger=ledger,
        policy=policy,
        boundary=_authority_boundary(
            profiles=profiles,
            phase=phase,
            publish_by=publish_by,
        ),
    )


class _GcsExactStore:
    def __init__(self, *, client: object, bucket: str, prefix: str) -> None:
        self._client = client
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")

    def _blob(self, identity: Mapping[str, object]) -> object:
        retained = _identity(identity, label="GCS object identity")
        _assert_uri_scope(
            retained["uri"],
            bucket=self._bucket,
            prefix=self._prefix,
            label="GCS object identity",
        )
        _, name = _gs_parts(retained["uri"], label="GCS object identity")
        return self._client.bucket(self._bucket).blob(
            name, generation=int(retained["generation"])
        )

    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> Mapping[str, object]:
        _assert_uri_scope(
            uri, bucket=self._bucket, prefix=self._prefix, label="GCS publication URI"
        )
        _, name = _gs_parts(uri, label="GCS publication URI")
        blob = self._client.bucket(self._bucket).blob(name)
        blob.upload_from_string(raw, content_type=content_type, if_generation_match=0)
        blob.reload()
        if blob.time_created is None or blob.generation is None:
            _fail("GCS publication lacks provider generation/time")
        return {
            "identity": {
                "uri": uri,
                "generation": str(blob.generation),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            "created_at": blob.time_created.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
        }

    def read_exact(self, *, identity: Mapping[str, object]) -> Mapping[str, object]:
        retained = _identity(identity, label="GCS exact-read identity")
        blob = self._blob(retained)
        raw = blob.download_as_bytes(if_generation_match=int(retained["generation"]))
        blob.reload(if_generation_match=int(retained["generation"]))
        if blob.time_created is None or str(blob.generation) != retained["generation"]:
            _fail("GCS exact read lacks the requested generation/time")
        if (
            len(raw) != retained["bytes"]
            or hashlib.sha256(raw).hexdigest() != retained["sha256"]
        ):
            _fail("GCS exact-read content differs")
        return {
            "identity": retained,
            "created_at": blob.time_created.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "raw": raw,
        }


class _GcsProviderCaptureStore:
    """Read acquisition objects and write only the derived capture prefix."""

    def __init__(self, *, client: object, policy: CollectorAllowlist) -> None:
        self._acquisition_prefix = policy.evidence_prefix.rstrip("/")
        self._capture_prefix = policy.provider_capture_prefix.rstrip("/")
        self._reader = _GcsExactStore(
            client=client,
            bucket=policy.evidence_bucket,
            prefix=self._acquisition_prefix,
        )
        self._publisher = _GcsExactStore(
            client=client,
            bucket=policy.evidence_bucket,
            prefix=self._capture_prefix,
        )

    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> Mapping[str, object]:
        return self._publisher.publish_create_once(
            uri=uri, raw=raw, content_type=content_type
        )

    def read_exact(self, *, identity: Mapping[str, object]) -> Mapping[str, object]:
        uri = _identity(identity, label="provider-capture store identity")["uri"]
        _, name = _gs_parts(str(uri), label="provider-capture store identity")
        if name.startswith(f"{self._acquisition_prefix}/"):
            return self._reader.read_exact(identity=identity)
        if name.startswith(f"{self._capture_prefix}/"):
            return self._publisher.read_exact(identity=identity)
        _fail("provider-capture store read is outside its two exact prefixes")


class _GcsLedgerReader:
    def __init__(self, *, client: object, policy: CollectorAllowlist) -> None:
        self._client = client
        self._policy = policy

    def governance(self) -> Mapping[str, object]:
        bucket = self._client.bucket(self._policy.authority_bucket)
        bucket.reload()
        policy = bucket.get_iam_policy(requested_policy_version=3)
        raw_bindings: list[dict[str, object]] = []
        for binding in policy.bindings:
            item: dict[str, object] = {
                "role": binding.get("role"),
                "members": sorted(binding.get("members", ())),
            }
            if binding.get("condition") is not None:
                condition = binding["condition"]
                if not isinstance(condition, Mapping):
                    try:
                        condition = dict(condition)
                    except (TypeError, ValueError) as exc:
                        raise Week1A5DraftKingsAcquisitionError(
                            "authority IAM condition cannot be retained completely"
                        ) from exc
                item["condition"] = dict(condition)
            raw_bindings.append(item)
        raw_bindings.sort(key=canonical_json_bytes)
        bindings = _normalize_iam_bindings(
            raw_bindings, label="provider authority IAM bindings"
        )
        mutators = sorted(
            {
                str(member)
                for binding in bindings
                if binding["role"] in _DIRECT_OBJECT_MUTATOR_ROLES
                for member in binding["members"]
            }
        )
        viewers = sorted(
            {
                str(member)
                for binding in bindings
                if binding["role"] in _DIRECT_OBJECT_VIEWER_ROLES
                for member in binding["members"]
            }
        )
        public = sorted(
            {
                str(member)
                for binding in bindings
                for member in binding["members"]
                if member in {"allUsers", "allAuthenticatedUsers"}
            }
        )
        raw_etag = policy.etag
        if isinstance(raw_etag, bytes):
            etag_base64 = base64.b64encode(raw_etag).decode()
        elif type(raw_etag) is str:
            etag_base64 = raw_etag
        else:
            _fail("authority IAM policy lacks its provider etag")
        # Validate the provider representation now rather than allowing the
        # later policy hash to canonically bless malformed or empty ETags.
        try:
            decoded_etag = base64.b64decode(etag_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise Week1A5DraftKingsAcquisitionError(
                "authority IAM policy etag is not canonical base64"
            ) from exc
        if not decoded_etag or base64.b64encode(decoded_etag).decode() != etag_base64:
            _fail("authority IAM policy etag is not canonical base64")
        policy_version = int(policy.version or 1)
        iam_configuration = bucket.iam_configuration
        return {
            "authority_bucket_metageneration": str(bucket.metageneration),
            "retention_seconds": int(bucket.retention_period or 0),
            "retention_locked": bool(bucket.retention_policy_locked),
            "versioning_enabled": bool(bucket.versioning_enabled),
            "uniform_bucket_level_access": bool(
                iam_configuration.uniform_bucket_level_access_enabled
            ),
            "iam_policy_version": policy_version,
            "iam_policy_etag_base64": etag_base64,
            "iam_policy_sha256": _iam_policy_sha256(
                version=policy_version,
                etag_base64=etag_base64,
                bindings=bindings,
            ),
            "iam_policy_bindings": list(bindings),
            "object_mutator_members": mutators,
            "object_viewer_members": viewers,
            "public_members": public,
        }

    def read_single_generation(self, *, uri: str) -> Mapping[str, object]:
        _assert_uri_scope(
            uri,
            bucket=self._policy.authority_bucket,
            prefix=self._policy.authority_prefix,
            label="authority ledger lookup",
        )
        _, name = _gs_parts(uri, label="authority ledger lookup")
        bucket = self._client.bucket(self._policy.authority_bucket)
        versions = [
            blob
            for blob in self._client.list_blobs(bucket, prefix=name, versions=True)
            if blob.name == name
        ]
        if len(versions) != 1:
            _fail("authority ledger object does not have exactly one generation")
        blob = versions[0]
        if blob.generation is None:
            _fail("authority ledger generation is absent")
        raw = blob.download_as_bytes(if_generation_match=int(blob.generation))
        blob.reload(if_generation_match=int(blob.generation))
        if blob.time_created is None:
            _fail("authority ledger provider time is absent")
        return {
            "identity": {
                "uri": uri,
                "generation": str(blob.generation),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            "created_at": blob.time_created.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "raw": raw,
        }


class _RequestsSessionTransport:
    """Fixed authenticated cookie bridge; callers never supply a URL."""

    def __init__(
        self,
        *,
        storage_state_path: Path,
        session_profile: str,
        locator_families: tuple[LocatorFamily, ...],
    ) -> None:
        self._storage_state_path = storage_state_path
        self._session_profile = session_profile
        self._locator_families = locator_families

    def _admit_locator(self, locator: object, *, label: str) -> str:
        retained = _canonical_url(locator, label=label)
        if not any(family.accepts(retained) for family in self._locator_families):
            _fail(f"{label} is outside the exact family allowlist")
        return retained

    def perform(self, *, method: str, locator: str) -> TransportEvent:
        if method != "GET":
            _fail("DraftKings collector permits GET only")
        current = self._admit_locator(locator, label="initial request locator")
        try:
            import requests
        except ImportError as exc:  # pragma: no cover - base dependency
            raise Week1A5DraftKingsAcquisitionError("requests is unavailable") from exc
        try:
            state = json.loads(self._storage_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Week1A5DraftKingsAcquisitionError(
                "fixed DraftKings authenticated session state is unavailable"
            ) from exc
        cookies = state.get("cookies") if isinstance(state, Mapping) else None
        if not isinstance(cookies, list) or not cookies:
            _fail("fixed DraftKings session contains no cookies")
        session = requests.Session()
        admitted = 0
        for raw_cookie in cookies:
            if not isinstance(raw_cookie, Mapping):
                _fail("DraftKings session cookie shape differs")
            domain = str(raw_cookie.get("domain", "")).lstrip(".").lower()
            if not (domain == "draftkings.com" or domain.endswith(".draftkings.com")):
                continue
            name = str(raw_cookie.get("name", ""))
            value = str(raw_cookie.get("value", ""))
            if not name or not value:
                _fail("DraftKings session cookie is incomplete")
            session.cookies.set(
                name,
                value,
                domain=str(raw_cookie.get("domain")),
                path=str(raw_cookie.get("path") or "/"),
                secure=bool(raw_cookie.get("secure", True)),
            )
            admitted += 1
        if admitted < 1:
            _fail("fixed session contains no DraftKings-domain cookie")
        headers = {
            "Accept": "application/json,text/csv,*/*;q=0.1",
            "User-Agent": "nfl-dfs-governed-dk-collector/1",
        }
        seen: set[str] = set()
        hops: list[TransportHop] = []
        response: object | None = None
        redirect_statuses = {301, 302, 303, 307, 308}
        for redirect_count in range(MAX_REDIRECTS + 1):
            if current in seen:
                _fail("DraftKings redirect loop was rejected before another request")
            seen.add(current)
            response = session.get(
                current,
                allow_redirects=False,
                timeout=(10, 120),
                headers=headers,
            )
            if getattr(response, "history", ()):
                _fail("HTTP adapter followed an unreviewed redirect internally")
            response_url = self._admit_locator(
                str(response.url), label="provider response locator"
            )
            if response_url != current:
                _fail("provider response locator differs from the requested hop")
            status = int(response.status_code)
            location = response.headers.get("Location")
            if status in redirect_statuses:
                if type(location) is not str or not location:
                    _fail("DraftKings redirect omits its Location target")
                next_locator = self._admit_locator(
                    urljoin(current, location), label="redirect target"
                )
                hops.append(TransportHop(current, status, str(location)))
                if redirect_count == MAX_REDIRECTS:
                    _fail("DraftKings redirect count exceeds the exact bound")
                if next_locator in seen:
                    _fail("DraftKings redirect loop was rejected before another request")
                current = next_locator
                continue
            if 300 <= status <= 399:
                _fail("DraftKings returned an unsupported redirect status")
            if location is not None:
                _fail("nonredirect DraftKings response contains a redirect target")
            hops.append(TransportHop(current, status, None))
            break
        if response is None or not hops:  # pragma: no cover - loop is nonempty
            raise AssertionError("transport did not issue its initial request")
        body = bytes(response.content)
        observed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        final_path = urlsplit(str(response.url)).path.lower()
        if any(marker in final_path for marker in ("/login", "/signin", "/register")):
            _fail("DraftKings request terminated on an authentication surface")
        return TransportEvent(
            body=body,
            observed_at=observed,
            hops=tuple(hops),
            response_content_type=str(response.headers.get("Content-Type", "")),
            response_content_disposition=(
                str(response.headers["Content-Disposition"])
                if "Content-Disposition" in response.headers
                else None
            ),
            session_profile=self._session_profile,
        )


def _google_storage_client(project: str) -> object:
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - optional GCP dependency
        raise Week1A5DraftKingsAcquisitionError(
            'install GCP support with `pip install -e ".[gcp]"`'
        ) from exc
    return storage.Client(project=project)


def _live_acquisition_authority(
    *,
    policy: CollectorAllowlist,
    client: object,
    profiles: tuple[str, ...],
    phase: str,
    publish_by: object,
) -> _ProductionDraftKingsAcquisitionAuthority:
    """Build the private live adapter from repository-owned dependencies."""

    evidence = _GcsExactStore(
        client=client, bucket=policy.evidence_bucket, prefix=policy.evidence_prefix
    )
    ledger = _GcsLedgerReader(client=client, policy=policy)
    return _ProductionDraftKingsAcquisitionAuthority(
        evidence=evidence,
        ledger=ledger,
        policy=policy,
        boundary=_authority_boundary(
            profiles=profiles,
            phase=phase,
            publish_by=publish_by,
        ),
    )


def _verify_derived_publication_after_ledgers(
    *,
    authority: _ProductionDraftKingsAcquisitionAuthority,
    publication: Mapping[str, object],
    event_ids: Sequence[str],
    publish_by: object,
    phase: str,
) -> dict[str, object]:
    retained = _mapping(publication, label="derived capture publication")
    _exact(
        retained,
        {"artifact_identity", "semantic_sha256", "created_at"},
        label="derived capture publication",
    )
    created_at, created = _timestamp(
        retained["created_at"], label="derived capture provider creation time"
    )
    publish_text, cutoff = capture._publish_by(
        publish_by,
        label="derived capture publish_by",
        phase=phase,
    )
    if created > cutoff:
        _fail("derived capture was created after its exact publication cutoff")
    for event_id in event_ids:
        ledger = authority._ledger_evidence_for(event_id)
        if ledger["publish_by"] != publish_text:
            _fail("derived capture and authority ledger use another cutoff")
        _, ledger_created = _timestamp(
            ledger["created_at"], label="derived capture ledger creation time"
        )
        if ledger_created > created:
            _fail("derived capture predates an authority ledger it depends on")
        _identity(ledger["identity"], label="derived capture authority ledger identity")
    retained["created_at"] = created_at
    return retained


def run_live_authenticated_acquisition(
    *,
    acquisition_profile: str,
    contest_role: str,
    execute_live_acquisition: bool = False,
) -> CollectorIssuance:
    """Run one fixed collector event; default-off before every side effect."""

    if execute_live_acquisition is not True:
        _fail("live DraftKings acquisition is default-off")
    policy = live_collector_allowlist()
    _collector_runtime_matches(policy)
    client = _google_storage_client(policy.project)
    ledger_reader = _GcsLedgerReader(client=client, policy=policy)
    observed_governance = _validate_governance(
        ledger_reader.governance(), label="pre-acquisition authority governance"
    )
    if observed_governance != policy.governance:
        _fail("authority-ledger governance differs before provider acquisition")
    evidence = _GcsExactStore(
        client=client, bucket=policy.evidence_bucket, prefix=policy.evidence_prefix
    )
    ledger = _GcsExactStore(
        client=client, bucket=policy.authority_bucket, prefix=policy.authority_prefix
    )
    if acquisition_profile not in policy.rules:
        _fail("acquisition profile is outside the exact allowlist")
    transport = _RequestsSessionTransport(
        storage_state_path=LIVE_SESSION_STATE_PATH,
        session_profile=policy.session_profile,
        locator_families=policy.rules[acquisition_profile].effective_locator_families,
    )
    return _collect_with_reviewed_ports(
        policy=policy,
        evidence_store=evidence,
        ledger_writer=ledger,
        transport=transport,
        profile=acquisition_profile,
        contest_role=contest_role,
        authority_event_id=_event_id(),
    )


def publish_live_acceptance_provider_capture_v2(
    *,
    contest_role: str,
    acquisition_receipt: object,
    publish_by: object,
    execute_live_publication: bool = False,
) -> dict[str, object]:
    """Publish one derived pre-lock capture through only the fixed authority."""

    if execute_live_publication is not True:
        _fail("live provider-capture publication is default-off")
    policy = live_collector_allowlist()
    _authority_runtime_matches(policy)
    client = _google_storage_client(policy.project)
    store = _GcsProviderCaptureStore(client=client, policy=policy)
    authority = _live_acquisition_authority(
        policy=policy,
        client=client,
        profiles=(capture.ACCEPTANCE_ACQUISITION_PROFILE,),
        phase="prelock",
        publish_by=publish_by,
    )
    artifact = capture.build_acceptance_provider_capture_v2(
        store=store,
        acquisition_authority=authority,
        contest_role=contest_role,
        acquisition_receipt=acquisition_receipt,
        publish_by=publish_by,
    )
    event_id = str(artifact["acquisition_authority_event_id"])
    publication = capture.publish_semantic_artifact(
        store,
        uri=(
            f"gs://{policy.evidence_bucket}/{policy.provider_capture_prefix}/"
            f"acceptance/{contest_role}/{event_id}.json"
        ),
        artifact=artifact,
        not_after=publish_by,
    )
    return _verify_derived_publication_after_ledgers(
        authority=authority,
        publication=publication,
        event_ids=(event_id,),
        publish_by=publish_by,
        phase="prelock",
    )


def publish_live_final_field_provider_capture_v2(
    *,
    contest_role: str,
    provider_acquisition_receipt: object,
    standings_acquisition_receipt: object,
    publish_by: object,
    execute_live_publication: bool = False,
) -> dict[str, object]:
    """Publish one derived settled capture through only the fixed authority."""

    if execute_live_publication is not True:
        _fail("live provider-capture publication is default-off")
    policy = live_collector_allowlist()
    _authority_runtime_matches(policy)
    client = _google_storage_client(policy.project)
    store = _GcsProviderCaptureStore(client=client, policy=policy)
    authority = _live_acquisition_authority(
        policy=policy,
        client=client,
        profiles=tuple(
            sorted(
                (
                    capture.CONTEST_DETAIL_ACQUISITION_PROFILE,
                    capture.STANDINGS_ACQUISITION_PROFILE,
                )
            )
        ),
        phase="postlock",
        publish_by=publish_by,
    )
    artifact = capture.build_final_field_provider_capture_v2(
        store=store,
        acquisition_authority=authority,
        contest_role=contest_role,
        provider_acquisition_receipt=provider_acquisition_receipt,
        standings_acquisition_receipt=standings_acquisition_receipt,
        publish_by=publish_by,
    )
    event_id = str(artifact["provider_authority_event_id"])
    publication = capture.publish_semantic_artifact(
        store,
        uri=(
            f"gs://{policy.evidence_bucket}/{policy.provider_capture_prefix}/"
            f"final-field/{contest_role}/{event_id}.json"
        ),
        artifact=artifact,
        not_before=capture.EXPECTED_LOCK_UTC,
        not_after=publish_by,
    )
    return _verify_derived_publication_after_ledgers(
        authority=authority,
        publication=publication,
        event_ids=(
            str(artifact["provider_authority_event_id"]),
            str(artifact["standings_authority_event_id"]),
        ),
        publish_by=publish_by,
        phase="postlock",
    )


__all__ = [
    "CollectorIssuance",
    "Week1A5DraftKingsAcquisitionError",
    "live_collector_allowlist",
    "publish_live_acceptance_provider_capture_v2",
    "publish_live_final_field_provider_capture_v2",
    "run_live_authenticated_acquisition",
]
