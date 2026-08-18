"""Fail-closed scientific run identity for residual-world research.

This module is deliberately pure and offline.  It does not discover git state,
build an archive, read a source lock, locate CBC, or inspect an image.  Those
operations belong to a separately reviewed launcher.  Instead, the caller must
provide every already-frozen identity and this module validates and binds the
values into one immutable, path-free scientific payload.

The payload is an explicit allowlist.  Generic dataclass serialization is not
used, because silently adding a field to a scientific identity would make old
and new executions incomparable.  No method in this module can license a cloud
run, historical scoring, or a production change.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final, Mapping


RUN_CONTEXT_SCHEMA: Final = "residual-world-run-context-v1"
EXTERNAL_ATTESTATION_BOUNDARY: Final = "reviewed-launcher-required"

PROTOCOL_ID: Final = "20260817-residual-world-column-generation-scorefree-v1"
PROTOCOL_SHA256: Final = (
    "db02c7bb7994ea887ad32a935f3188bc78384c3c4b97a3dc712f3ffd2a8fc02a"
)
AMENDMENT_ID: Final = "20260817-residual-world-exact-solver-selector-v1"
AMENDMENT_SHA256: Final = (
    "a13c09eb6e4ea1e4f0515a0aa4b750614a020fc930d3d1d9e53b1bfe787042ff"
)

PULP_VERSION: Final = "3.3.2"
CBC_VERSION: Final = "2.10.3"
PYTHON_VERSION: Final = "3.14.4"
CBC_SHA256: Final = (
    "2e17077752aa52b06385ad248c9e90bb4f1ce34038c34c94e1012ca6adea5cc7"
)

# Frozen by the independent retained-MPS review.  ``pulp_module_sha256`` is
# the reviewed writer implementation at ``pulp/mps_lp.py``; the second value
# is the reviewed COIN/CBC adapter at ``pulp/apis/coin_api.py``.
PULP_MODULE_SHA256: Final = (
    "e6ec5badbfb1ecd389a94c4e4c67db267cab492a7c69c011a2490fa0a5e8fd78"
)
PULP_COIN_MODULE_SHA256: Final = (
    "c412dbbc9c871b31137972071ed31837a29f1ecdd1ca8b705b1e14d14ffda26d"
)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_PYTHON_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_IMAGE_SEGMENT = r"[a-z0-9]+(?:[._-][a-z0-9]+)*"
_IMAGE_URI_RE = re.compile(
    rf"^(?:{_IMAGE_SEGMENT}/)+{_IMAGE_SEGMENT}@sha256:(?P<digest>[0-9a-f]{{64}})$"
)

_PAYLOAD_FIELDS: Final = (
    "schema",
    "protocol_id",
    "protocol_sha256",
    "amendment_id",
    "amendment_sha256",
    "external_attestation_boundary",
    "code_commit",
    "code_archive_sha256",
    "source_file_lock_sha256",
    "source_data_lock_sha256",
    "source_lock_sha256",
    "image_sha256",
    "python_version",
    "pulp_version",
    "cbc_version",
    "cbc_sha256",
    "pulp_module_sha256",
    "pulp_coin_module_sha256",
    "uses_realized_outcomes",
    "production_change_licensed",
    "historical_scoring_licensed",
)


def _canonical_json_bytes(value: object) -> bytes:
    """Return the frozen canonical JSON representation (without a newline)."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _require_literal_string(name: str, value: object) -> str:
    if type(value) is not str:  # bool/int subclasses must not be coerced.
        raise TypeError(f"{name} must be a literal string")
    return value


def _require_sha256(name: str, value: object) -> str:
    text = _require_literal_string(name, value)
    if _HASH_RE.fullmatch(text) is None:
        raise ValueError(f"{name} must be exactly 64 lowercase hexadecimal characters")
    return text


def derive_source_lock_sha256(
    *, source_file_lock_sha256: str, source_data_lock_sha256: str
) -> str:
    """Bind the independent source-file and source-data lock identities.

    This digest is only a scientific binding of two already-created lock
    artifacts.  It is not a source-lock implementation and does not attest to
    either artifact's contents.
    """

    file_sha = _require_sha256("source_file_lock_sha256", source_file_lock_sha256)
    data_sha = _require_sha256("source_data_lock_sha256", source_data_lock_sha256)
    payload = {
        "schema": "residual-world-source-lock-binding-v1",
        "source_data_lock_sha256": data_sha,
        "source_file_lock_sha256": file_sha,
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class ResidualRunContext:
    """Immutable, allowlisted scientific identity for one residual-world run."""

    schema: str
    protocol_id: str
    protocol_sha256: str
    amendment_id: str
    amendment_sha256: str
    external_attestation_boundary: str
    code_commit: str
    code_archive_sha256: str
    source_file_lock_sha256: str
    source_data_lock_sha256: str
    source_lock_sha256: str
    image_sha256: str
    python_version: str
    pulp_version: str
    cbc_version: str
    cbc_sha256: str
    pulp_module_sha256: str
    pulp_coin_module_sha256: str
    uses_realized_outcomes: bool
    production_change_licensed: bool
    historical_scoring_licensed: bool

    def __post_init__(self) -> None:
        _validate_context_values(self)

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ResidualRunContext":
        """Construct from an exact allowlisted payload, rejecting schema drift."""

        if not isinstance(payload, Mapping):
            raise TypeError("residual run context payload must be a mapping")
        keys = set(payload.keys())
        expected = set(_PAYLOAD_FIELDS)
        if keys != expected:
            missing = sorted(expected - keys)
            extra = sorted(keys - expected, key=str)
            raise ValueError(
                "residual run context payload fields differ from the frozen allowlist: "
                f"missing={missing}, extra={extra}"
            )
        return cls(**{name: payload[name] for name in _PAYLOAD_FIELDS})  # type: ignore[arg-type]

    @property
    def sha256(self) -> str:
        return residual_run_context_sha256(self)

    @property
    def scientific_sha256(self) -> str:
        return self.sha256


def _validate_context_values(context: ResidualRunContext) -> None:
    exact_strings = {
        "schema": RUN_CONTEXT_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "amendment_id": AMENDMENT_ID,
        "amendment_sha256": AMENDMENT_SHA256,
        "external_attestation_boundary": EXTERNAL_ATTESTATION_BOUNDARY,
        "python_version": PYTHON_VERSION,
        "pulp_version": PULP_VERSION,
        "cbc_version": CBC_VERSION,
        "cbc_sha256": CBC_SHA256,
        "pulp_module_sha256": PULP_MODULE_SHA256,
        "pulp_coin_module_sha256": PULP_COIN_MODULE_SHA256,
    }
    for name, expected in exact_strings.items():
        value = _require_literal_string(name, getattr(context, name))
        if value != expected:
            raise ValueError(f"{name} must equal frozen value {expected!r}")

    code_commit = _require_literal_string("code_commit", context.code_commit)
    if _COMMIT_RE.fullmatch(code_commit) is None:
        raise ValueError("code_commit must be an exact 40-character lowercase git commit")

    for name in (
        "code_archive_sha256",
        "source_file_lock_sha256",
        "source_data_lock_sha256",
        "source_lock_sha256",
        "image_sha256",
    ):
        _require_sha256(name, getattr(context, name))

    expected_source_lock = derive_source_lock_sha256(
        source_file_lock_sha256=context.source_file_lock_sha256,
        source_data_lock_sha256=context.source_data_lock_sha256,
    )
    if context.source_lock_sha256 != expected_source_lock:
        raise ValueError(
            "source_lock_sha256 does not bind the exact source-file and source-data locks"
        )

    # The runtime is exact rather than a range.  Keep the syntax check separate
    # from the frozen-value check so malformed and merely unsupported values
    # both fail closed with a useful field name.
    python_version = _require_literal_string("python_version", context.python_version)
    if _PYTHON_VERSION_RE.fullmatch(python_version) is None:
        raise ValueError("python_version must be an exact major.minor.micro runtime string")

    for name in (
        "uses_realized_outcomes",
        "production_change_licensed",
        "historical_scoring_licensed",
    ):
        if getattr(context, name) is not False:
            raise ValueError(f"{name} must be the literal boolean false")


def build_residual_run_context(
    *,
    code_commit: str,
    code_archive_sha256: str,
    source_file_lock_sha256: str,
    source_data_lock_sha256: str,
    image_sha256: str,
    python_version: str,
    cbc_sha256: str,
    image_uri: str | None = None,
    source_lock_sha256: str | None = None,
    pulp_version: str = PULP_VERSION,
    cbc_version: str = CBC_VERSION,
    pulp_module_sha256: str = PULP_MODULE_SHA256,
    pulp_coin_module_sha256: str = PULP_COIN_MODULE_SHA256,
) -> ResidualRunContext:
    """Build a frozen context from identities supplied by a future launcher.

    Protocol/amendment identities and the three false license flags are not
    caller-configurable.  ``source_lock_sha256`` may be repeated explicitly by
    a launcher; when omitted it is deterministically derived from the two
    required component locks.  Either path is validated identically.

    ``image_uri`` is optional operational evidence.  When supplied, its digest
    must equal ``image_sha256``; the registry/repository spelling is deliberately
    discarded and never enters the scientific context.  The caller must retain
    that URI in the separately reviewed operational receipt.  Similarly, this
    function binds caller-supplied archive and lock hashes but does not create or
    attest those artifacts; that remains a launcher gate.
    """

    combined_source_lock = derive_source_lock_sha256(
        source_file_lock_sha256=source_file_lock_sha256,
        source_data_lock_sha256=source_data_lock_sha256,
    )
    image_digest = _require_sha256("image_sha256", image_sha256)
    if image_uri is not None:
        image_reference = _require_literal_string("image_uri", image_uri)
        image_match = _IMAGE_URI_RE.fullmatch(image_reference)
        if image_match is None:
            raise ValueError(
                "image_uri must be a lowercase immutable registry reference ending "
                "in @sha256:<64 lowercase hex>"
            )
        if image_match.group("digest") != image_digest:
            raise ValueError("image_uri digest and image_sha256 differ")
    return ResidualRunContext(
        schema=RUN_CONTEXT_SCHEMA,
        protocol_id=PROTOCOL_ID,
        protocol_sha256=PROTOCOL_SHA256,
        amendment_id=AMENDMENT_ID,
        amendment_sha256=AMENDMENT_SHA256,
        external_attestation_boundary=EXTERNAL_ATTESTATION_BOUNDARY,
        code_commit=code_commit,
        code_archive_sha256=code_archive_sha256,
        source_file_lock_sha256=source_file_lock_sha256,
        source_data_lock_sha256=source_data_lock_sha256,
        source_lock_sha256=(
            combined_source_lock if source_lock_sha256 is None else source_lock_sha256
        ),
        image_sha256=image_digest,
        python_version=python_version,
        pulp_version=pulp_version,
        cbc_version=cbc_version,
        cbc_sha256=cbc_sha256,
        pulp_module_sha256=pulp_module_sha256,
        pulp_coin_module_sha256=pulp_coin_module_sha256,
        uses_realized_outcomes=False,
        production_change_licensed=False,
        historical_scoring_licensed=False,
    )


def validate_residual_run_context(
    context: ResidualRunContext | Mapping[str, object],
) -> ResidualRunContext:
    """Return a validated immutable context, rejecting extra/missing fields."""

    if isinstance(context, ResidualRunContext):
        _validate_context_values(context)
        return context
    return ResidualRunContext.from_payload(context)


def residual_run_context_payload(
    context: ResidualRunContext | Mapping[str, object],
) -> dict[str, object]:
    """Return the explicit scientific payload in its frozen field allowlist."""

    validated = validate_residual_run_context(context)
    return {name: getattr(validated, name) for name in _PAYLOAD_FIELDS}


def residual_run_context_json(
    context: ResidualRunContext | Mapping[str, object],
) -> bytes:
    """Return canonical path-independent scientific JSON bytes."""

    return _canonical_json_bytes(residual_run_context_payload(context))


def residual_run_context_sha256(
    context: ResidualRunContext | Mapping[str, object],
) -> str:
    return hashlib.sha256(residual_run_context_json(context)).hexdigest()


def recompute_residual_run_context_binding(
    context: ResidualRunContext | Mapping[str, object],
) -> tuple[dict[str, object], str]:
    """Rebuild the allowlisted payload and its digest from first principles."""

    payload = residual_run_context_payload(context)
    return payload, hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def validate_residual_run_context_binding(
    context: ResidualRunContext | Mapping[str, object],
    *,
    expected_payload: Mapping[str, object],
    expected_sha256: str,
) -> ResidualRunContext:
    """Fail closed unless a stored payload/hash equals a fresh reconstruction.

    This is the final-serialization helper for the residual core.  It rejects a
    stale stored payload even when its separately supplied hash happens to be a
    well-formed digest, and it rejects a stored hash even when the payload is
    current.
    """

    expected_digest = _require_sha256("expected_sha256", expected_sha256)
    validated = validate_residual_run_context(context)
    reconstructed_payload, reconstructed_sha = recompute_residual_run_context_binding(
        validated
    )
    stored = validate_residual_run_context(expected_payload)
    stored_payload = residual_run_context_payload(stored)
    if stored_payload != reconstructed_payload:
        raise ValueError("stored residual run context payload differs from reconstruction")
    if expected_digest != reconstructed_sha:
        raise ValueError("stored residual run context SHA-256 differs from reconstruction")
    return validated


# Explicit longer alias for callers that prefer the experiment-qualified name.
residual_world_run_context_sha256 = residual_run_context_sha256


__all__ = [
    "AMENDMENT_ID",
    "AMENDMENT_SHA256",
    "CBC_VERSION",
    "CBC_SHA256",
    "EXTERNAL_ATTESTATION_BOUNDARY",
    "PROTOCOL_ID",
    "PROTOCOL_SHA256",
    "PULP_COIN_MODULE_SHA256",
    "PULP_MODULE_SHA256",
    "PULP_VERSION",
    "PYTHON_VERSION",
    "RUN_CONTEXT_SCHEMA",
    "ResidualRunContext",
    "build_residual_run_context",
    "derive_source_lock_sha256",
    "residual_run_context_json",
    "residual_run_context_payload",
    "residual_run_context_sha256",
    "residual_world_run_context_sha256",
    "recompute_residual_run_context_binding",
    "validate_residual_run_context_binding",
    "validate_residual_run_context",
]
