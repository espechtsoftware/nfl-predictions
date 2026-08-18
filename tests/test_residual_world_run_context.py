from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from nfl_dfs.research.residual_world_run_context import (
    AMENDMENT_ID,
    AMENDMENT_SHA256,
    CBC_SHA256,
    CBC_VERSION,
    EXTERNAL_ATTESTATION_BOUNDARY,
    PROTOCOL_ID,
    PROTOCOL_SHA256,
    PULP_COIN_MODULE_SHA256,
    PULP_MODULE_SHA256,
    PULP_VERSION,
    PYTHON_VERSION,
    RUN_CONTEXT_SCHEMA,
    ResidualRunContext,
    build_residual_run_context,
    derive_source_lock_sha256,
    recompute_residual_run_context_binding,
    residual_run_context_json,
    residual_run_context_payload,
    residual_run_context_sha256,
    residual_world_run_context_sha256,
    validate_residual_run_context,
    validate_residual_run_context_binding,
)


CODE_COMMIT = "1" * 40
CODE_ARCHIVE_SHA = "2" * 64
FILE_LOCK_SHA = "3" * 64
DATA_LOCK_SHA = "4" * 64
IMAGE_SHA = "5" * 64
CBC_SHA = CBC_SHA256
IMAGE_URI = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/research/residual-world"
    f"@sha256:{IMAGE_SHA}"
)


def _context(**overrides: object) -> ResidualRunContext:
    values: dict[str, object] = {
        "code_commit": CODE_COMMIT,
        "code_archive_sha256": CODE_ARCHIVE_SHA,
        "source_file_lock_sha256": FILE_LOCK_SHA,
        "source_data_lock_sha256": DATA_LOCK_SHA,
        "image_uri": IMAGE_URI,
        "image_sha256": IMAGE_SHA,
        "python_version": "3.14.4",
        "cbc_sha256": CBC_SHA,
    }
    values.update(overrides)
    return build_residual_run_context(**values)  # type: ignore[arg-type]


def test_context_binds_frozen_protocol_runtime_and_source_identities() -> None:
    context = _context()
    payload = residual_run_context_payload(context)

    assert context.schema == RUN_CONTEXT_SCHEMA
    assert context.external_attestation_boundary == EXTERNAL_ATTESTATION_BOUNDARY
    assert (context.protocol_id, context.protocol_sha256) == (
        PROTOCOL_ID,
        PROTOCOL_SHA256,
    )
    assert (context.amendment_id, context.amendment_sha256) == (
        AMENDMENT_ID,
        AMENDMENT_SHA256,
    )
    assert (context.pulp_version, context.cbc_version) == (
        PULP_VERSION,
        CBC_VERSION,
    )
    assert context.pulp_module_sha256 == PULP_MODULE_SHA256
    assert context.pulp_coin_module_sha256 == PULP_COIN_MODULE_SHA256
    assert context.source_lock_sha256 == derive_source_lock_sha256(
        source_file_lock_sha256=FILE_LOCK_SHA,
        source_data_lock_sha256=DATA_LOCK_SHA,
    )
    assert "image_uri" not in payload
    assert context.image_sha256 == IMAGE_SHA
    assert payload["code_commit"] == CODE_COMMIT
    assert payload["code_archive_sha256"] == CODE_ARCHIVE_SHA
    assert payload["source_file_lock_sha256"] == FILE_LOCK_SHA
    assert payload["source_data_lock_sha256"] == DATA_LOCK_SHA
    assert payload["cbc_sha256"] == CBC_SHA
    assert payload["python_version"] == PYTHON_VERSION
    assert payload["uses_realized_outcomes"] is False
    assert payload["production_change_licensed"] is False
    assert payload["historical_scoring_licensed"] is False


def test_context_is_frozen_and_sha_is_canonical_and_stable() -> None:
    context = _context()
    with pytest.raises(FrozenInstanceError):
        context.code_commit = "7" * 40  # type: ignore[misc]

    payload = residual_run_context_payload(context)
    reversed_payload = dict(reversed(list(payload.items())))
    reconstructed = validate_residual_run_context(reversed_payload)

    assert reconstructed == context
    assert residual_run_context_json(reconstructed) == residual_run_context_json(context)
    assert context.sha256 == residual_run_context_sha256(context)
    assert context.scientific_sha256 == context.sha256
    assert residual_world_run_context_sha256(context) == context.sha256
    assert context.sha256 == (
        "8f61f800468d9ced5b41b64e22b260a67d24a8520fa4349dd21e28f7568c4866"
    )
    assert b"/tmp/" not in residual_run_context_json(context)


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_payload_rejects_missing_or_extra_fields(mutation: str) -> None:
    payload = residual_run_context_payload(_context())
    if mutation == "missing":
        payload.pop("code_archive_sha256")
    else:
        payload["execution_name"] = "mutable-operational-value"
    with pytest.raises(ValueError, match="frozen allowlist"):
        validate_residual_run_context(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "residual-world-run-context-latest"),
        ("protocol_id", "wrong-protocol"),
        ("protocol_sha256", "a" * 64),
        ("amendment_id", "wrong-amendment"),
        ("amendment_sha256", "b" * 64),
        ("external_attestation_boundary", "self-attested"),
        ("python_version", "3.14.3"),
        ("pulp_version", "3.3.1"),
        ("cbc_version", "2.10"),
        ("cbc_sha256", "6" * 64),
        ("pulp_module_sha256", "c" * 64),
        ("pulp_coin_module_sha256", "d" * 64),
    ],
)
def test_context_rejects_nonfrozen_protocol_or_solver_identity(
    field: str, value: object
) -> None:
    with pytest.raises(ValueError, match=field):
        replace(_context(), **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("code_archive_sha256", "a" * 63),
        ("source_file_lock_sha256", "A" * 64),
        ("source_data_lock_sha256", "sha256:" + "b" * 64),
        ("source_lock_sha256", "/tmp/source-lock.json"),
        ("image_sha256", "c" * 65),
        ("cbc_sha256", "not-a-hash"),
    ],
)
def test_context_rejects_noncanonical_hashes(field: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError), match=field):
        replace(_context(), **{field: value})


@pytest.mark.parametrize(
    "commit",
    ["main", "1" * 39, "A" * 40, "sha1:" + "1" * 40, None],
)
def test_context_rejects_mutable_or_nonexact_code_commit(commit: object) -> None:
    with pytest.raises((TypeError, ValueError), match="code_commit"):
        replace(_context(), code_commit=commit)


@pytest.mark.parametrize(
    "image_uri",
    [
        "us.gcr.io/project/image:latest",
        "us.gcr.io/project/image@sha256:short",
        f"https://us.gcr.io/project/image@sha256:{IMAGE_SHA}",
        f"us.gcr.io/project/image@sha256:{IMAGE_SHA}?tag=latest",
        f"US.GCR.IO/project/image@sha256:{IMAGE_SHA}",
        f"us.gcr.io/project/../image@sha256:{IMAGE_SHA}",
    ],
)
def test_context_rejects_mutable_or_malformed_image_reference(image_uri: str) -> None:
    with pytest.raises(ValueError, match="image_uri"):
        _context(image_uri=image_uri)


def test_context_rejects_image_digest_mismatch() -> None:
    with pytest.raises(ValueError, match="digest"):
        build_residual_run_context(
            code_commit=CODE_COMMIT,
            code_archive_sha256=CODE_ARCHIVE_SHA,
            source_file_lock_sha256=FILE_LOCK_SHA,
            source_data_lock_sha256=DATA_LOCK_SHA,
            image_sha256="7" * 64,
            python_version="3.14.4",
            cbc_sha256=CBC_SHA,
            image_uri=IMAGE_URI,
        )


@pytest.mark.parametrize("version", ["3.14", "Python 3.14.4", "3.14.4+", "", 3144])
def test_context_requires_exact_python_runtime_string(version: object) -> None:
    with pytest.raises((TypeError, ValueError), match="python_version"):
        replace(_context(), python_version=version)


@pytest.mark.parametrize(
    "field",
    [
        "uses_realized_outcomes",
        "production_change_licensed",
        "historical_scoring_licensed",
    ],
)
@pytest.mark.parametrize("value", [True, 0, None, "false"])
def test_no_license_flags_require_literal_false(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        replace(_context(), **{field: value})


def test_context_rejects_unbound_component_source_locks() -> None:
    with pytest.raises(ValueError, match="does not bind"):
        replace(_context(), source_lock_sha256="7" * 64)

    with pytest.raises(ValueError, match="does not bind"):
        replace(_context(), source_data_lock_sha256="8" * 64)


def test_builder_rejects_wrong_explicit_combined_source_lock() -> None:
    with pytest.raises(ValueError, match="does not bind"):
        _context(source_lock_sha256="9" * 64)


def test_registry_uri_is_validated_but_not_scientific_identity() -> None:
    first = _context(image_uri=IMAGE_URI)
    second = _context(
        image_uri=(
            "us.gcr.io/other-project/other-repository/other-image"
            f"@sha256:{IMAGE_SHA}"
        )
    )
    without_uri = _context(image_uri=None)

    assert residual_run_context_payload(first) == residual_run_context_payload(second)
    assert residual_run_context_payload(first) == residual_run_context_payload(without_uri)
    assert first.sha256 == second.sha256 == without_uri.sha256
    with pytest.raises(ValueError, match="frozen allowlist"):
        validate_residual_run_context(
            {**residual_run_context_payload(first), "image_uri": IMAGE_URI}
        )


def test_recomputed_binding_accepts_only_exact_payload_and_sha() -> None:
    context = _context()
    payload, digest = recompute_residual_run_context_binding(context)
    assert digest == context.sha256
    assert validate_residual_run_context_binding(
        context,
        expected_payload=dict(reversed(list(payload.items()))),
        expected_sha256=digest,
    ) is context

    stale_payload = dict(payload)
    stale_payload["code_commit"] = "a" * 40
    with pytest.raises(ValueError, match="payload differs"):
        validate_residual_run_context_binding(
            context,
            expected_payload=stale_payload,
            expected_sha256=digest,
        )
    with pytest.raises(ValueError, match="SHA-256 differs"):
        validate_residual_run_context_binding(
            context,
            expected_payload=payload,
            expected_sha256="a" * 64,
        )


def test_payload_rejects_nonmapping_and_nonliteral_fixed_string() -> None:
    with pytest.raises(TypeError, match="mapping"):
        validate_residual_run_context([])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="protocol_id"):
        replace(_context(), protocol_id=123)  # type: ignore[arg-type]
