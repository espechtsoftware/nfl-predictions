from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
from pathlib import Path
from typing import Any

import pytest

from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_release_v1 as release_v1
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_release_v2 as release
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v2 as core
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from tests import test_corpus_r6_fixed_g0_candidate_authority_release_v1 as fixture_v1


RUN_ID = "20260829-fixed-g0-candidate-authority-v2"


def _identity(label: str) -> dict[str, object]:
    raw = f"fixture:{label}".encode()
    return {
        "uri": f"gs://fixture/{label}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _rehash(body: dict[str, object], field: str) -> None:
    body.pop(field, None)
    body[field] = release.canonical_sha256(body)


def _binding(
    *,
    catalog_receipt_identity: dict[str, object],
    catalog_release_identity: dict[str, object],
) -> dict[str, object]:
    outer = _identity("catalog-recovery-outer")
    outer["uri"] = release.recovery.OUTER_ATTESTATION_URI
    read_classes = core._read_class_attestation()
    return core._with_hash({
        "schema_version": core.CANDIDATE_IMPLEMENTATION_BINDING_SCHEMA,
        "catalog_recovery_outer_identity": outer,
        "catalog_recovery_outer_attestation_sha256": sha256(
            b"outer-internal"
        ).hexdigest(),
        "catalog_recovery_code_and_lock_binding": {
            "schema_version": "fixture-recovery-binding/v1",
            "outer_attestation_identity": outer,
            "write_capability_exposed": False,
            "outcome_columns_read": [],
            "uses_realized_outcomes": False,
        },
        "catalog_inner_object_count": 110,
        "catalog_inner_object_manifest_sha256": sha256(
            b"inner-manifest"
        ).hexdigest(),
        "catalog_inner_replay_receipt_identity": catalog_receipt_identity,
        "catalog_inner_replay_receipt_sha256": fixture_v1._digest(
            "catalog-replay-receipt"
        ),
        "catalog_inner_release_identity": catalog_release_identity,
        "catalog_inner_release_sha256": sha256(
            b"catalog-release-internal"
        ).hexdigest(),
        "candidate_implementation_commit_sha": "1" * 40,
        "candidate_implementation_measurements": [{
            "relative_path": path,
            "sha256": sha256(path.encode()).hexdigest(),
            "bytes": len(path.encode()),
        } for path in core.CANDIDATE_IMPLEMENTATION_PATHS],
        "candidate_implementation_measurements_sha256": sha256(
            b"fixture-measurements"
        ).hexdigest(),
        "inner_authority_derived_only_from_validated_outer": True,
        "catalog_recovery_outer_read_before_any_inner_read": True,
        "legacy_catalog_root_accepted_as_authority": False,
        "read_class_attestation": read_classes,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }, field="candidate_implementation_binding_sha256")


def _v2_bundle(
    *,
    run_id: str,
    namespace: str,
    artifacts: list[dict[str, object]],
    artifact_identities: list[dict[str, object]],
    catalog_receipt_identity: dict[str, object],
    catalog_release_identity: dict[str, object],
    panel_identity: dict[str, object],
    binding: dict[str, object],
) -> dict[str, object]:
    bundle_v1 = fixture_v1._fake_bundle(
        run_id=run_id,
        namespace=namespace,
        artifacts=artifacts,
        artifact_identities=artifact_identities,
        catalog_receipt_identity=catalog_receipt_identity,
        panel_identity=panel_identity,
    )
    panel = bundle_v1["panel_derivation_receipt"]
    panel["catalog_release_identity"] = catalog_release_identity
    panel["catalog_release_sha256"] = sha256(b"catalog-release-internal").hexdigest()
    panel["g0_source_commit_sha"] = "4" * 40
    _rehash(panel, "panel_derivation_sha256")
    bundle_v1["panel_derivation_receipt"] = panel
    _rehash(bundle_v1, "candidate_authority_bundle_sha256")
    return core._upgrade_bundle(bundle_v1, binding=binding)


def _install_core_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    store: fixture_v1.MemoryExactStore,
) -> dict[str, Any]:
    artifacts = [
        fixture_v1._candidate_artifact(ordinal)
        for ordinal in range(source.TASK_COUNT)
    ]
    catalog_receipt_identity = store.force(
        "gs://fixture/catalog-replay-receipt.json",
        b'{"fixture":"catalog-replay"}',
    )
    panel_identity = store.force(
        "gs://fixture/fixed-g0-panel.json",
        b'{"fixture":"fixed-g0-panel"}',
    )
    catalog_release_identity = _identity("catalog-release")
    binding = _binding(
        catalog_receipt_identity=catalog_receipt_identity,
        catalog_release_identity=catalog_release_identity,
    )
    state: dict[str, Any] = {
        "artifacts": artifacts,
        "catalog_receipt_identity": catalog_receipt_identity,
        "panel_identity": panel_identity,
        "catalog_release_identity": catalog_release_identity,
        "binding": binding,
        "expected_bundle": None,
        "derive_calls": 0,
        "build_calls": 0,
        "validate_calls": 0,
        "outer_calls": 0,
    }

    def derive(**kwargs: Any) -> dict[str, object]:
        state["derive_calls"] += 1
        assert kwargs["catalog_recovery_outer_identity"] == binding[
            "catalog_recovery_outer_identity"
        ]
        body: dict[str, object] = {
            "schema_version": core.MATERIAL_SCHEMA,
            "task_count": source.TASK_COUNT,
            "candidate_artifacts": deepcopy(artifacts),
            "candidate_artifact_manifest_sha256": release.canonical_sha256(
                artifacts
            ),
            "catalog_recovery_outer_identity": binding[
                "catalog_recovery_outer_identity"
            ],
            "catalog_recovery_outer_attestation_sha256": binding[
                "catalog_recovery_outer_attestation_sha256"
            ],
            "catalog_recovery_candidate_binding": binding,
            "read_class_attestation": binding["read_class_attestation"],
        }
        _rehash(body, "candidate_material_sha256")
        return body

    def build(
        *,
        release_id: str,
        namespace: str,
        candidate_artifact_identities: list[dict[str, object]],
        **kwargs: Any,
    ) -> dict[str, object]:
        state["build_calls"] += 1
        assert kwargs["catalog_recovery_outer_identity"] == binding[
            "catalog_recovery_outer_identity"
        ]
        result = _v2_bundle(
            run_id=release_id,
            namespace=namespace,
            artifacts=deepcopy(artifacts),
            artifact_identities=deepcopy(candidate_artifact_identities),
            catalog_receipt_identity=deepcopy(catalog_receipt_identity),
            catalog_release_identity=deepcopy(catalog_release_identity),
            panel_identity=deepcopy(panel_identity),
            binding=deepcopy(binding),
        )
        state["expected_bundle"] = deepcopy(result)
        return result

    def validate(value: object, **kwargs: Any) -> dict[str, object]:
        state["validate_calls"] += 1
        assert kwargs["catalog_recovery_outer_identity"] == binding[
            "catalog_recovery_outer_identity"
        ]
        expected = state["expected_bundle"]
        if expected is None or release.canonical_json_bytes(value) != (
            release.canonical_json_bytes(expected)
        ):
            raise core.CorpusR6FixedG0CandidateAuthorityV2Error(
                "fixture deep replay differs"
            )
        return deepcopy(expected)

    def open_outer(**kwargs: Any) -> tuple[None, dict[str, object]]:
        state["outer_calls"] += 1
        if kwargs["catalog_recovery_outer_identity"] != binding[
            "catalog_recovery_outer_identity"
        ]:
            raise core.CorpusR6FixedG0CandidateAuthorityV2Error(
                "fixture outer differs"
            )
        return None, deepcopy(binding)

    monkeypatch.setattr(core, "derive_fixed_g0_candidate_material_v2", derive)
    monkeypatch.setattr(core, "build_fixed_g0_candidate_authority_v2", build)
    monkeypatch.setattr(core, "validate_fixed_g0_candidate_authority_v2", validate)
    monkeypatch.setattr(core, "_open_outer_and_binding", open_outer)
    return state


def _callbacks(store: fixture_v1.MemoryExactStore) -> dict[str, Any]:
    return {
        "repository_root": Path("/fixture/repository"),
        "read_exact": store.read_exact,
        "git_head": lambda _root: "1" * 40,
        "git_blob": lambda _root, _commit, _path: b"fixture",
        "git_status": lambda _root, _paths: b"",
    }


def _publish(
    store: fixture_v1.MemoryExactStore, state: dict[str, Any],
) -> tuple[dict[str, object], dict[str, object]]:
    return release.publish_fixed_g0_candidate_authority_release_v2(
        run_id=RUN_ID,
        catalog_recovery_outer_identity=state["binding"][
            "catalog_recovery_outer_identity"
        ],
        publish_create_once=store.create_once,
        **_callbacks(store),
    )


@pytest.fixture
def published(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    store = fixture_v1.MemoryExactStore()
    state = _install_core_fixture(monkeypatch, store=store)
    root, root_identity = _publish(store, state)
    return {
        "store": store,
        "state": state,
        "root": root,
        "root_identity": root_identity,
    }


def test_exact_165_object_root_last_publication(
    published: dict[str, Any],
) -> None:
    store = published["store"]
    root = published["root"]
    prefix = release.output_prefix_for_run_v2(RUN_ID)
    assert len(store.create_calls) == 165
    assert store.create_calls[-1] == f"{prefix}{release.ROOT_FILENAME}"
    assert release_v1.ROOT_FILENAME not in store.create_calls
    assert root["published_non_root_object_count"] == 164
    assert root["published_total_object_count"] == 165
    assert root["published_legacy_root_count"] == 0
    assert root["legacy_root_published"] is False
    assert len(root["non_root_publication_manifest"]) == 164
    assert root["candidate_population_authority"] is True
    assert root["exact_occurrence_provenance_authority"] is True


def test_deep_reopen_reconstructs_terminal_root_exactly(
    published: dict[str, Any],
) -> None:
    store = published["store"]
    state = published["state"]
    store.read_calls.clear()
    reopened = release.reopen_fixed_g0_candidate_authority_release_v2(
        published["root_identity"],
        **_callbacks(store),
    )
    assert reopened.root == published["root"]
    assert reopened.authority_bundle == state["expected_bundle"]
    assert state["outer_calls"] == 1
    assert state["validate_calls"] == 1
    assert store.read_calls[0].endswith(release.ROOT_FILENAME)
    first_lineage = reopened.authority_bundle["lineage_sidecars"][0]
    assert first_lineage["candidates"][0]["occurrences"][0][
        "parameter_set_id"
    ] == "baseline"


def test_legacy_root_uri_rejected_without_any_read() -> None:
    reads: list[str] = []
    legacy_identity = _identity("legacy-root")
    legacy_identity["uri"] = (
        f"gs://{release_v1.OUTPUT_BUCKET}/{release_v1.OUTPUT_NAMESPACE}/"
        "20260829-legacy/candidate-authority-release.json"
    )
    with pytest.raises(
        release.CorpusR6FixedG0CandidateAuthorityReleaseV2Error,
        match="legacy root rejected",
    ):
        release.reopen_fixed_g0_candidate_authority_release_v2(
            legacy_identity,
            repository_root=Path("/fixture"),
            read_exact=lambda identity: reads.append(str(identity["uri"])) or b"x",
            git_head=lambda _root: "1" * 40,
            git_blob=lambda _root, _commit, _path: b"x",
            git_status=lambda _root, _paths: b"",
        )
    assert reads == []


def test_legacy_schema_at_v2_uri_rejected_before_outer_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = fixture_v1.MemoryExactStore()
    prefix = release.output_prefix_for_run_v2(RUN_ID)
    raw = release.canonical_json_bytes({"schema_version": release_v1.RELEASE_SCHEMA})
    root_identity = store.force(f"{prefix}{release.ROOT_FILENAME}", raw)
    outer_called = False

    def open_outer(**_kwargs: Any) -> tuple[None, dict[str, object]]:
        nonlocal outer_called
        outer_called = True
        return None, {}

    monkeypatch.setattr(core, "_open_outer_and_binding", open_outer)
    with pytest.raises(
        release.CorpusR6FixedG0CandidateAuthorityReleaseV2Error,
        match="legacy root schema rejected",
    ):
        release.reopen_fixed_g0_candidate_authority_release_v2(
            root_identity, **_callbacks(store)
        )
    assert store.read_calls == [root_identity["uri"]]
    assert outer_called is False


def test_root_outer_mismatch_is_rejected_structurally(
    published: dict[str, Any],
) -> None:
    changed = deepcopy(published["root"])
    changed["catalog_recovery_outer_identity"] = _identity("wrong-outer")
    _rehash(changed, "candidate_authority_release_sha256")
    with pytest.raises(
        release.CorpusR6FixedG0CandidateAuthorityReleaseV2Error,
        match="outer binding",
    ):
        release.validate_fixed_g0_candidate_authority_release_structure_v2(
            changed
        )


def test_public_publisher_has_no_inner_or_payload_bypass() -> None:
    parameters = inspect.signature(
        release.publish_fixed_g0_candidate_authority_release_v2
    ).parameters
    assert "catalog_recovery_outer_identity" in parameters
    for forbidden in (
        "catalog_replay_receipt_identity",
        "catalog_release_identity",
        "candidate_artifacts",
        "candidate_artifact_identities",
        "lineage_sidecars",
        "namespace",
        "output_prefix",
    ):
        assert forbidden not in parameters
