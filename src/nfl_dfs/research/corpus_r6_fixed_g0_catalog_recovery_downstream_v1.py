"""Read-only downstream authority for the fixed-G0 catalog recovery root.

The catalog recovery publisher is frozen by its own reviewed implementation
measurements, so downstream support must not modify that module after its
outer attestation has been published.  This successor supplies the missing
consumer seam.  It accepts one generation-pinned outer identity, exact-reads
that object first, validates it against the tracked recovery lock/attempt
chain, and derives every inner identity exclusively from the validated outer.

This module deliberately exposes no create, overwrite, delete, graph,
outcome, scoring, selection, promotion, or deployment operation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from types import MappingProxyType
from typing import Final

from nfl_dfs.research import corpus_r6_fixed_g0_catalog_recovery_v1 as recovery
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter


DOWNSTREAM_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-fixed-g0-catalog-recovery-downstream-authority/v1"
)
DOWNSTREAM_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_fixed_g0_catalog_recovery_downstream_v1.py"
)

ReadExact = Callable[[Mapping[str, object]], bytes]


class CorpusR6FixedG0CatalogRecoveryDownstreamV1Error(ValueError):
    """The read-only outer-to-inner authority replay failed closed."""


@dataclass(frozen=True, slots=True)
class ReopenedFixedG0CatalogRecoveryAuthorityV1:
    """Validated outer authority; all inner identities are derived fields."""

    outer_identity: Mapping[str, object]
    outer_attestation: Mapping[str, object]
    outer_attestation_sha256: str
    inner_replay_receipt_identity: Mapping[str, object]
    inner_catalog_release_identity: Mapping[str, object]
    inner_object_manifest: tuple[Mapping[str, object], ...]
    recovery_code_and_lock_binding: Mapping[str, object]
    read_order: tuple[str, ...]
    inner_object_bodies_read: bool
    write_capability_exposed: bool


def _fail(message: str) -> None:
    raise CorpusR6FixedG0CatalogRecoveryDownstreamV1Error(message)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return adapter._normalized_identity(value, label=label)
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryDownstreamV1Error(str(exc)) from exc


def _deep_freeze(value: object) -> object:
    """Recursively freeze the validated authority before returning it."""

    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            _fail("catalog recovery returned authority keys differ")
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _mapping_proxy(value: Mapping[str, object]) -> Mapping[str, object]:
    frozen = _deep_freeze(value)
    if not isinstance(frozen, Mapping):
        _fail("catalog recovery returned authority object differs")
    return frozen


def _read_outer_exact_v1(
    *, outer_identity: Mapping[str, object], read_exact: ReadExact
) -> dict[str, object]:
    identity = _identity(outer_identity, label="catalog recovery outer identity")
    if identity["uri"] != recovery.OUTER_ATTESTATION_URI:
        _fail("catalog recovery outer URI differs")
    if not callable(read_exact):
        _fail("catalog recovery outer reader differs")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryDownstreamV1Error(
            "catalog recovery outer generation-exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail("catalog recovery outer exact object identity differs")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6FixedG0CatalogRecoveryDownstreamV1Error(
            "catalog recovery outer is not canonical JSON"
        ) from exc
    if not isinstance(parsed, Mapping) or recovery.canonical_json_bytes(parsed) != raw:
        _fail("catalog recovery outer canonical bytes differ")
    return dict(parsed)


def reopen_with_resolved_recovery_authority_v1(
    *,
    outer_identity: Mapping[str, object],
    capability: recovery.PublicationCapabilityV1,
    attempt_binding: recovery.TrackedAttemptBindingV1,
    read_exact: ReadExact,
) -> ReopenedFixedG0CatalogRecoveryAuthorityV1:
    """Exact-open the outer first using an already Git-resolved authority.

    This lower-level function exists so hermetic tests and successor builders
    can reuse the same read-order boundary.  It still validates both resolved
    authority objects and exposes no storage mutation callback.
    """

    try:
        validated_capability = recovery.validate_resolved_authority_v1(capability)
        validated_attempt = recovery.validate_tracked_attempt_binding_v1(
            attempt_binding, capability=validated_capability
        )
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryDownstreamV1Error(
            "tracked catalog recovery authority replay failed"
        ) from exc

    retained_identity = _identity(
        outer_identity, label="catalog recovery outer identity"
    )
    outer_candidate = _read_outer_exact_v1(
        outer_identity=retained_identity, read_exact=read_exact
    )
    try:
        outer = recovery.validate_outer_attestation_v1(
            outer_candidate,
            capability=validated_capability,
            attempt_binding=validated_attempt,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryDownstreamV1Error(
            "catalog recovery outer attestation validation failed"
        ) from exc

    receipt_identity = _identity(
        outer["inner_replay_receipt_identity"],
        label="outer-derived replay receipt identity",
    )
    release_identity = _identity(
        outer["inner_catalog_release_identity"],
        label="outer-derived catalog release identity",
    )
    manifest = tuple(
        _mapping_proxy(dict(row)) for row in outer["inner_object_manifest"]
    )
    if (
        len(manifest) != recovery.EXPECTED_INNER_OBJECT_COUNT
        or dict(manifest[-2]["identity"]) != release_identity
        or dict(manifest[-1]["identity"]) != receipt_identity
    ):
        _fail("catalog recovery outer-derived inner manifest differs")

    code_and_lock_binding = {
        "schema_version": DOWNSTREAM_AUTHORITY_SCHEMA,
        "outer_attestation_identity": retained_identity,
        "outer_attestation_sha256": outer["recovery_attestation_sha256"],
        "implementation_commit_sha": outer["implementation_commit_sha"],
        "implementation_measurements_sha256": outer[
            "implementation_measurements_sha256"
        ],
        "review_lock_commit_sha": outer["review_lock_commit_sha"],
        "review_lock_internal_sha256": outer["review_lock_internal_sha256"],
        "final_lock_commit_sha": outer["final_lock_commit_sha"],
        "final_lock_internal_sha256": outer["final_lock_internal_sha256"],
        "attempt_marker_commit_sha": outer["attempt_marker_commit_sha"],
        "attempt_marker_sha256": outer["attempt_marker_sha256"],
        "capability_sha256": validated_capability.capability_sha256,
        "inner_authority_derived_only_from_validated_outer": True,
        "write_capability_exposed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return ReopenedFixedG0CatalogRecoveryAuthorityV1(
        outer_identity=_mapping_proxy(retained_identity),
        outer_attestation=_mapping_proxy(outer),
        outer_attestation_sha256=str(outer["recovery_attestation_sha256"]),
        inner_replay_receipt_identity=_mapping_proxy(receipt_identity),
        inner_catalog_release_identity=_mapping_proxy(release_identity),
        inner_object_manifest=manifest,
        recovery_code_and_lock_binding=_mapping_proxy(code_and_lock_binding),
        read_order=("catalog_recovery_outer",),
        inner_object_bodies_read=False,
        write_capability_exposed=False,
    )


def reopen_fixed_g0_catalog_recovery_authority_v1(
    *,
    repository_root: Path,
    outer_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> ReopenedFixedG0CatalogRecoveryAuthorityV1:
    """Production read-only entrypoint using the clean tracked lock chain."""

    repository = adapter.SubprocessGitRepositoryV1(repository_root)
    try:
        current_head = repository.require_current_clean_head()
        capability, attempt_binding = recovery.resolve_tracked_attempt_binding_v1(
            repository=repository,
            current_head=current_head,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryDownstreamV1Error(
            "catalog recovery tracked production authority resolution failed"
        ) from exc
    return reopen_with_resolved_recovery_authority_v1(
        outer_identity=outer_identity,
        capability=capability,
        attempt_binding=attempt_binding,
        read_exact=read_exact,
    )


__all__ = [
    "CorpusR6FixedG0CatalogRecoveryDownstreamV1Error",
    "DOWNSTREAM_AUTHORITY_SCHEMA",
    "DOWNSTREAM_MODULE_PATH",
    "ReadExact",
    "ReopenedFixedG0CatalogRecoveryAuthorityV1",
    "reopen_fixed_g0_catalog_recovery_authority_v1",
    "reopen_with_resolved_recovery_authority_v1",
]
