from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace

import pytest

from nfl_dfs.research import (
    corpus_r6_fixed_g0_catalog_recovery_downstream_v1 as downstream,
)


def _identity(uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1788047679701105",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _outer_body() -> dict[str, object]:
    release = {
        "uri": "gs://fixed/catalog-release.json",
        "generation": "11",
        "sha256": "1" * 64,
        "bytes": 10,
    }
    receipt = {
        "uri": "gs://fixed/replay-receipt.json",
        "generation": "12",
        "sha256": "2" * 64,
        "bytes": 11,
    }
    manifest = []
    for ordinal in range(downstream.recovery.EXPECTED_INNER_OBJECT_COUNT):
        if ordinal == downstream.recovery.EXPECTED_INNER_OBJECT_COUNT - 2:
            identity = release
        elif ordinal == downstream.recovery.EXPECTED_INNER_OBJECT_COUNT - 1:
            identity = receipt
        else:
            identity = {
                "uri": f"gs://fixed/{ordinal}.json",
                "generation": str(ordinal + 20),
                "sha256": f"{ordinal + 3:064x}",
                "bytes": ordinal + 1,
            }
        manifest.append({
            "object_ordinal": ordinal,
            "role": "test",
            "source_task_ordinal": None,
            "identity": identity,
        })
    return {
        "recovery_attestation_sha256": "a" * 64,
        "inner_catalog_release_identity": release,
        "inner_replay_receipt_identity": receipt,
        "inner_object_manifest": manifest,
        "implementation_commit_sha": "b" * 40,
        "implementation_measurements_sha256": "c" * 64,
        "review_lock_commit_sha": "d" * 40,
        "review_lock_internal_sha256": "e" * 64,
        "final_lock_commit_sha": "f" * 40,
        "final_lock_internal_sha256": "3" * 64,
        "attempt_marker_commit_sha": "4" * 40,
        "attempt_marker_sha256": "5" * 64,
    }


def _patch_authority(
    monkeypatch: pytest.MonkeyPatch, outer: dict[str, object]
) -> tuple[SimpleNamespace, SimpleNamespace]:
    capability = SimpleNamespace(capability_sha256="6" * 64)
    attempt = SimpleNamespace(marker_commit_sha="4" * 40)
    monkeypatch.setattr(
        downstream.recovery,
        "validate_resolved_authority_v1",
        lambda value: capability if value is capability else None,
    )
    monkeypatch.setattr(
        downstream.recovery,
        "validate_tracked_attempt_binding_v1",
        lambda value, *, capability: attempt,
    )
    monkeypatch.setattr(
        downstream.recovery,
        "validate_outer_attestation_v1",
        lambda value, *, capability, attempt_binding: outer,
    )
    return capability, attempt


def test_read_only_reopen_reads_outer_first_and_derives_inner_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer = _outer_body()
    raw = downstream.recovery.canonical_json_bytes(outer)
    identity = _identity(downstream.recovery.OUTER_ATTESTATION_URI, raw)
    capability, attempt = _patch_authority(monkeypatch, outer)
    reads: list[dict[str, object]] = []

    def read_exact(requested: dict[str, object]) -> bytes:
        reads.append(dict(requested))
        return raw

    reopened = downstream.reopen_with_resolved_recovery_authority_v1(
        outer_identity=identity,
        capability=capability,
        attempt_binding=attempt,
        read_exact=read_exact,
    )

    assert reads == [identity]
    assert reopened.read_order == ("catalog_recovery_outer",)
    assert reopened.inner_object_bodies_read is False
    assert reopened.write_capability_exposed is False
    assert dict(reopened.outer_identity) == identity
    assert dict(reopened.inner_catalog_release_identity) == outer[
        "inner_catalog_release_identity"
    ]
    assert dict(reopened.inner_replay_receipt_identity) == outer[
        "inner_replay_receipt_identity"
    ]
    assert len(reopened.inner_object_manifest) == 110
    assert reopened.recovery_code_and_lock_binding[
        "inner_authority_derived_only_from_validated_outer"
    ] is True
    with pytest.raises(TypeError):
        reopened.outer_attestation["inner_object_manifest"][0]["identity"][
            "uri"
        ] = "gs://mutated/value.json"
    with pytest.raises(TypeError):
        reopened.inner_object_manifest[0]["identity"]["uri"] = (
            "gs://mutated/value.json"
        )


def test_wrong_outer_uri_fails_before_reader_or_authority_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = b"{}"
    identity = _identity("gs://wrong/outer.json", raw)
    calls: list[str] = []
    monkeypatch.setattr(
        downstream.recovery,
        "validate_resolved_authority_v1",
        lambda value: calls.append("authority"),
    )
    with pytest.raises(
        downstream.CorpusR6FixedG0CatalogRecoveryDownstreamV1Error,
        match="outer URI differs",
    ):
        downstream._read_outer_exact_v1(
            outer_identity=identity,
            read_exact=lambda _identity: calls.append("read") or raw,
        )
    assert calls == []


def test_exact_identity_mismatch_fails_before_outer_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer = _outer_body()
    raw = downstream.recovery.canonical_json_bytes(outer)
    identity = _identity(downstream.recovery.OUTER_ATTESTATION_URI, raw)
    capability, attempt = _patch_authority(monkeypatch, outer)
    validator_calls: list[str] = []
    monkeypatch.setattr(
        downstream.recovery,
        "validate_outer_attestation_v1",
        lambda *args, **kwargs: validator_calls.append("outer") or outer,
    )
    with pytest.raises(
        downstream.CorpusR6FixedG0CatalogRecoveryDownstreamV1Error,
        match="exact object identity differs",
    ):
        downstream.reopen_with_resolved_recovery_authority_v1(
            outer_identity=identity,
            capability=capability,
            attempt_binding=attempt,
            read_exact=lambda _identity: raw + b"x",
        )
    assert validator_calls == []


def test_noncanonical_outer_bytes_fail_before_outer_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = b'{"z":1, "a":2}'
    identity = _identity(downstream.recovery.OUTER_ATTESTATION_URI, raw)
    capability, attempt = _patch_authority(monkeypatch, _outer_body())
    validator_calls: list[str] = []
    monkeypatch.setattr(
        downstream.recovery,
        "validate_outer_attestation_v1",
        lambda *args, **kwargs: validator_calls.append("outer"),
    )
    with pytest.raises(
        downstream.CorpusR6FixedG0CatalogRecoveryDownstreamV1Error,
        match="canonical bytes differ",
    ):
        downstream.reopen_with_resolved_recovery_authority_v1(
            outer_identity=identity,
            capability=capability,
            attempt_binding=attempt,
            read_exact=lambda _identity: raw,
        )
    assert validator_calls == []
