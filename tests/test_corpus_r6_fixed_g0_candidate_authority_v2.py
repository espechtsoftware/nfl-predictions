from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as v1
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v2 as core
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


def _identity(label: str) -> dict[str, object]:
    raw = f"fixture:{label}".encode()
    return {
        "uri": f"gs://fixture/{label}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _catalog_identity(label: str) -> dict[str, object]:
    identity = _identity(label)
    identity["uri"] = f"{v1.catalog_adapter.FIXED_CATALOG_NAMESPACE}{label}.json"
    return identity


def _manifest() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    bindings: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for ordinal in range(source.TASK_COUNT):
        derivation = _catalog_identity(f"derivation-{ordinal}")
        catalog = _catalog_identity(f"catalog-{ordinal}")
        bindings.append({
            "derivation_identity": derivation,
            "catalog_identity": catalog,
        })
        rows.extend((
            {
                "object_ordinal": len(rows),
                "role": "catalog_derivation_receipt",
                "source_task_ordinal": ordinal,
                "identity": derivation,
            },
            {
                "object_ordinal": len(rows) + 1,
                "role": "player_catalog",
                "source_task_ordinal": ordinal,
                "identity": catalog,
            },
        ))
    release = _catalog_identity("catalog-release")
    receipt = _catalog_identity("catalog-replay-receipt")
    rows.extend((
        {
            "object_ordinal": 108,
            "role": "catalog_release",
            "source_task_ordinal": None,
            "identity": release,
        },
        {
            "object_ordinal": 109,
            "role": "inner_replay_receipt",
            "source_task_ordinal": None,
            "identity": receipt,
        },
    ))
    return bindings, rows


def _authority(
    *, outer: dict[str, object] | None = None,
    mutate_manifest: bool = False,
) -> SimpleNamespace:
    _, rows = _manifest()
    if mutate_manifest:
        rows[17]["identity"] = _catalog_identity("wrong-catalog")
    return SimpleNamespace(
        outer_identity=outer or _identity("catalog-recovery-outer"),
        outer_attestation={
            "inner_replay_receipt_sha256": sha256(
                b"catalog-replay-internal"
            ).hexdigest(),
            "inner_catalog_release_sha256": sha256(
                b"catalog-release-internal"
            ).hexdigest(),
        },
        outer_attestation_sha256=sha256(b"outer-internal").hexdigest(),
        inner_replay_receipt_identity=rows[-1]["identity"],
        inner_catalog_release_identity=rows[-2]["identity"],
        inner_object_manifest=tuple(rows),
        recovery_code_and_lock_binding={
            "schema_version": "fixture-recovery-binding/v1",
            "outer_attestation_identity": outer or _identity(
                "catalog-recovery-outer"
            ),
            "write_capability_exposed": False,
            "outcome_columns_read": [],
            "uses_realized_outcomes": False,
        },
        read_order=("catalog_recovery_outer",),
        inner_object_bodies_read=False,
        write_capability_exposed=False,
    )


def _material() -> dict[str, object]:
    bindings, rows = _manifest()
    body: dict[str, object] = {
        "schema_version": v1.MATERIAL_SCHEMA,
        "task_count": source.TASK_COUNT,
        "candidate_artifacts": [],
        "candidate_artifact_manifest_sha256": source.canonical_sha256([]),
        "slate_predecessor_bindings": [
            {"catalog_binding": binding} for binding in bindings
        ],
        "catalog_release_identity": rows[-2]["identity"],
        "catalog_release_sha256": sha256(b"catalog-release-internal").hexdigest(),
        "catalog_replay_receipt_identity": rows[-1]["identity"],
        "catalog_replay_receipt_sha256": sha256(
            b"catalog-replay-internal"
        ).hexdigest(),
    }
    body["candidate_material_sha256"] = source.canonical_sha256(body)
    return body


def _measurement() -> tuple[str, list[dict[str, object]]]:
    rows = [{
        "relative_path": path,
        "sha256": sha256(path.encode()).hexdigest(),
        "bytes": len(path.encode()),
    } for path in core.CANDIDATE_IMPLEMENTATION_PATHS]
    return "1" * 40, rows


def _consume_outer_catalog_sequence(
    reader: Any, authority: SimpleNamespace,
) -> None:
    reader(authority.inner_replay_receipt_identity)
    reader(authority.inner_catalog_release_identity)
    manifest = list(authority.inner_object_manifest)
    for ordinal in range(source.TASK_COUNT):
        reader(manifest[ordinal * 2 + 1]["identity"])
        reader(manifest[ordinal * 2]["identity"])


def _install_outer(
    monkeypatch: pytest.MonkeyPatch,
    *,
    authority: SimpleNamespace,
    log: list[str] | None = None,
) -> None:
    def reopen(**kwargs: Any) -> SimpleNamespace:
        if log is not None:
            log.append("outer")
        if kwargs["outer_identity"] != authority.outer_identity:
            raise ValueError("wrong outer identity")
        return authority

    monkeypatch.setattr(
        core.recovery_downstream,
        "reopen_fixed_g0_catalog_recovery_authority_v1",
        reopen,
    )
    monkeypatch.setattr(
        core,
        "_measure_candidate_implementation_v2",
        lambda **_kwargs: _measurement(),
    )


def _callbacks() -> dict[str, Any]:
    return {
        "repository_root": Path("/fixture/repository"),
        "read_exact": lambda _identity: b"unused",
        "git_head": lambda _root: "1" * 40,
        "git_blob": lambda _root, _commit, _path: b"unused",
        "git_status": lambda _root, _paths: b"",
    }


def test_outer_is_opened_before_inherited_inner_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    authority = _authority()
    _install_outer(monkeypatch, authority=authority, log=log)

    def derive(**kwargs: Any) -> dict[str, object]:
        log.append("inner")
        assert kwargs["catalog_replay_receipt_identity"] == (
            authority.inner_replay_receipt_identity
        )
        _consume_outer_catalog_sequence(kwargs["read_exact"], authority)
        return _material()

    monkeypatch.setattr(v1, "derive_fixed_g0_candidate_material_v1", derive)
    retained = core.derive_fixed_g0_candidate_material_v2(
        catalog_recovery_outer_identity=authority.outer_identity,
        **_callbacks(),
    )
    assert log == ["outer", "inner"]
    assert retained["schema_version"] == core.MATERIAL_SCHEMA
    assert retained["catalog_recovery_outer_identity"] == authority.outer_identity
    assert retained["catalog_inner_object_count"] == 110
    assert retained["read_class_attestation"][
        "accepted_task_result_and_carrier_bodies_reopened"
    ] is True
    assert retained["read_class_attestation"]["world_matrix_bodies_read"] is False


def test_wrong_outer_fails_before_v1_is_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    _install_outer(monkeypatch, authority=authority)
    called = False

    def derive(**_kwargs: Any) -> dict[str, object]:
        nonlocal called
        called = True
        return _material()

    monkeypatch.setattr(v1, "derive_fixed_g0_candidate_material_v1", derive)
    with pytest.raises(
        core.CorpusR6FixedG0CandidateAuthorityV2Error,
        match="outer authoritative reopen failed",
    ):
        core.derive_fixed_g0_candidate_material_v2(
            catalog_recovery_outer_identity=_identity("wrong-outer"),
            **_callbacks(),
        )
    assert called is False


def test_all_110_manifest_identities_are_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority(mutate_manifest=True)
    _install_outer(monkeypatch, authority=authority)
    monkeypatch.setattr(
        v1,
        "derive_fixed_g0_candidate_material_v1",
        lambda **kwargs: (
            _consume_outer_catalog_sequence(kwargs["read_exact"], authority)
            or _material()
        ),
    )
    with pytest.raises(
        core.CorpusR6FixedG0CandidateAuthorityV2Error,
        match="110-object manifest",
    ):
        core.derive_fixed_g0_candidate_material_v2(
            catalog_recovery_outer_identity=authority.outer_identity,
            **_callbacks(),
        )


def test_candidate_implementation_code_drift_fails_closed(
    tmp_path: Path,
) -> None:
    tracked: dict[str, bytes] = {}
    for path in core.CANDIDATE_IMPLEMENTATION_PATHS:
        full = tmp_path / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(f"clean:{path}".encode())
        tracked[path] = full.read_bytes()
    drift_path = core.CANDIDATE_IMPLEMENTATION_PATHS[1]
    tracked[drift_path] = b"different tracked bytes"
    with pytest.raises(
        core.CorpusR6FixedG0CandidateAuthorityV2Error,
        match="code drift",
    ):
        core._measure_candidate_implementation_v2(
            repository_root=tmp_path,
            git_head=lambda _root: "2" * 40,
            git_blob=lambda _root, _commit, path: tracked[path],
            git_status=lambda _root, _paths: b"",
        )


def test_pinned_implementation_blob_reopens_on_clean_descendant(
    tmp_path: Path,
) -> None:
    tracked: dict[str, bytes] = {}
    for path in core.CANDIDATE_IMPLEMENTATION_PATHS:
        full = tmp_path / path
        full.parent.mkdir(parents=True, exist_ok=True)
        raw = f"stable:{path}".encode()
        full.write_bytes(raw)
        tracked[path] = raw
    bound_commit = "2" * 40
    retained_commit, measurements = core._measure_candidate_implementation_v2(
        repository_root=tmp_path,
        git_head=lambda _root: "3" * 40,
        git_blob=lambda _root, commit, path: (
            tracked[path] if commit == bound_commit else b"wrong commit"
        ),
        git_status=lambda _root, _paths: b"",
        implementation_commit_sha=bound_commit,
    )
    assert retained_commit == bound_commit
    assert len(measurements) == len(core.CANDIDATE_IMPLEMENTATION_PATHS)


def test_bundle_outer_mismatch_rejected_before_inherited_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    _install_outer(monkeypatch, authority=authority)
    _, binding = core._open_outer_and_binding(
        catalog_recovery_outer_identity=authority.outer_identity,
        **_callbacks(),
    )
    minimal_v1: dict[str, object] = {
        "schema_version": v1.AUTHORITY_BUNDLE_SCHEMA,
        "candidate_release": {},
        "candidate_artifacts": [],
        "candidate_artifact_manifest_sha256": source.canonical_sha256([]),
        "lineage_sidecars": [],
        "lineage_sidecar_manifest_sha256": source.canonical_sha256([]),
        "slate_derivation_receipts": [],
        "slate_derivation_manifest_sha256": source.canonical_sha256([]),
        "panel_derivation_receipt": {},
        "task_count": 0,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    minimal_v1["candidate_authority_bundle_sha256"] = source.canonical_sha256(
        minimal_v1
    )
    # Build a structurally self-hashed v2 envelope, then make its outer binding
    # coherent to a different outer so the expected-current comparison is the
    # first failing authority check.
    bad_binding = deepcopy(binding)
    bad_binding.pop("candidate_implementation_binding_sha256")
    bad_binding["catalog_recovery_outer_identity"] = _identity("other-outer")
    bad_binding["candidate_implementation_binding_sha256"] = (
        source.canonical_sha256(bad_binding)
    )
    item = {
        "schema_version": core.AUTHORITY_BUNDLE_SCHEMA,
        "catalog_recovery_candidate_binding": bad_binding,
        "catalog_recovery_outer_identity": bad_binding[
            "catalog_recovery_outer_identity"
        ],
        "catalog_recovery_outer_attestation_sha256": bad_binding[
            "catalog_recovery_outer_attestation_sha256"
        ],
        "read_class_attestation": bad_binding["read_class_attestation"],
        "slate_derivation_receipts": [],
        "panel_derivation_receipt": {},
    }
    item["candidate_authority_bundle_sha256"] = source.canonical_sha256(item)
    called = False

    def validate(**_kwargs: Any) -> dict[str, object]:
        nonlocal called
        called = True
        return minimal_v1

    monkeypatch.setattr(v1, "validate_fixed_g0_candidate_authority_v1", validate)
    with pytest.raises(
        core.CorpusR6FixedG0CandidateAuthorityV2Error,
        match="outer/code binding differs",
    ):
        core.validate_fixed_g0_candidate_authority_v2(
            item,
            catalog_recovery_outer_identity=authority.outer_identity,
            **_callbacks(),
        )
    assert called is False


def test_build_then_deep_validate_is_exact_v1_projection_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority()
    _install_outer(monkeypatch, authority=authority)
    bindings, rows = _manifest()
    receipts: list[dict[str, object]] = []
    panel_rows: list[dict[str, object]] = []
    for ordinal, catalog_binding in enumerate(bindings):
        receipt: dict[str, object] = {
            "schema_version": v1.SLATE_DERIVATION_SCHEMA,
            "source_task_ordinal": ordinal,
            "catalog_binding": catalog_binding,
            "outcome_columns_read": [],
            "uses_realized_outcomes": False,
        }
        receipt["slate_derivation_sha256"] = source.canonical_sha256(receipt)
        receipts.append(receipt)
        panel_rows.append({
            "source_task_ordinal": ordinal,
            "slate_derivation_sha256": receipt["slate_derivation_sha256"],
        })
    panel: dict[str, object] = {
        "schema_version": v1.PANEL_DERIVATION_SCHEMA,
        "catalog_release_identity": rows[-2]["identity"],
        "catalog_release_sha256": sha256(b"catalog-release-internal").hexdigest(),
        "catalog_replay_receipt_identity": rows[-1]["identity"],
        "catalog_replay_receipt_sha256": sha256(
            b"catalog-replay-internal"
        ).hexdigest(),
        "slates": panel_rows,
        "slate_derivation_manifest_sha256": source.canonical_sha256(receipts),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    panel["panel_derivation_sha256"] = source.canonical_sha256(panel)
    bundle_v1: dict[str, object] = {
        "schema_version": v1.AUTHORITY_BUNDLE_SCHEMA,
        "candidate_release": {"fixture": True},
        "candidate_artifacts": [],
        "candidate_artifact_manifest_sha256": source.canonical_sha256([]),
        "lineage_sidecars": [],
        "lineage_sidecar_manifest_sha256": source.canonical_sha256([]),
        "slate_derivation_receipts": receipts,
        "slate_derivation_manifest_sha256": source.canonical_sha256(receipts),
        "panel_derivation_receipt": panel,
        "task_count": source.TASK_COUNT,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    bundle_v1["candidate_authority_bundle_sha256"] = source.canonical_sha256(
        bundle_v1
    )
    expected_v1 = deepcopy(bundle_v1)

    def build(**kwargs: Any) -> dict[str, object]:
        assert kwargs["catalog_replay_receipt_identity"] == rows[-1]["identity"]
        _consume_outer_catalog_sequence(kwargs["read_exact"], authority)
        return deepcopy(expected_v1)

    def validate(value: object, **kwargs: Any) -> dict[str, object]:
        assert kwargs["catalog_replay_receipt_identity"] == rows[-1]["identity"]
        _consume_outer_catalog_sequence(kwargs["read_exact"], authority)
        assert source.canonical_json_bytes(value) == source.canonical_json_bytes(
            expected_v1
        )
        return deepcopy(expected_v1)

    monkeypatch.setattr(v1, "build_fixed_g0_candidate_authority_v1", build)
    monkeypatch.setattr(v1, "validate_fixed_g0_candidate_authority_v1", validate)
    built = core.build_fixed_g0_candidate_authority_v2(
        release_id="fixture-release",
        namespace="gs://fixture/output/",
        catalog_recovery_outer_identity=authority.outer_identity,
        candidate_artifact_identities=[],
        **_callbacks(),
    )
    validated = core.validate_fixed_g0_candidate_authority_v2(
        built,
        catalog_recovery_outer_identity=authority.outer_identity,
        **_callbacks(),
    )
    assert validated == built
    assert len(validated["slate_derivation_receipts"]) == source.TASK_COUNT
    assert all(
        receipt["catalog_recovery_candidate_binding"]
        == validated["catalog_recovery_candidate_binding"]
        for receipt in validated["slate_derivation_receipts"]
    )


def test_alternate_inner_release_is_rejected_before_backing_read() -> None:
    authority = _authority()
    backing_reads: list[dict[str, object]] = []
    guarded, _require_complete = core._outer_manifest_gated_reader(
        authority=authority,
        read_exact=lambda identity: backing_reads.append(dict(identity)) or b"fixture",
    )
    guarded(authority.inner_replay_receipt_identity)
    alternate_release = _catalog_identity("alternate-release")
    with pytest.raises(
        core.CorpusR6FixedG0CandidateAuthorityV2Error,
        match="outer-derived exact sequence",
    ):
        guarded(alternate_release)
    assert backing_reads == [authority.inner_replay_receipt_identity]


def test_v2_public_apis_expose_only_outer_catalog_input() -> None:
    import inspect

    for function in (
        core.derive_fixed_g0_candidate_material_v2,
        core.build_fixed_g0_candidate_authority_v2,
        core.validate_fixed_g0_candidate_authority_v2,
    ):
        parameters = inspect.signature(function).parameters
        assert "catalog_recovery_outer_identity" in parameters
        assert "catalog_replay_receipt_identity" not in parameters
        assert "catalog_release_identity" not in parameters
