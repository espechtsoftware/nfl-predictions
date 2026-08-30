from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
from pathlib import Path
from typing import Any, Mapping

import pytest

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v1 as candidate_v1,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_outer_candidate_authority_v3 as component,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_v1 as publication_v1,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from tests import (
    test_corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate_fixture,
)
from tests import (
    test_corpus_r6_matchup_capture_plan_outer_candidate_authority_v3 as capture_fixture,
)
from tests import (
    test_corpus_r6_matchup_component_publication_candidate_authority_v2 as v2_fixture,
)
from tests import (
    test_corpus_r6_fixed_g0_candidate_authority_release_v1 as store_fixture,
)


def _digest(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _implementation_measurements() -> list[dict[str, object]]:
    return [{
        "relative_path": path,
        "sha256": _digest(path),
        "bytes": len(path.encode()),
    } for path in component.COMPONENT_SUCCESSOR_IMPLEMENTATION_PATHS]


def _rehash_v1(value: dict[str, object]) -> None:
    value.pop("component_publication_receipt_sha256", None)
    value["component_publication_receipt_sha256"] = source.canonical_sha256(
        value
    )


def _fixture(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    capture_state = capture_fixture._fixture(monkeypatch)
    plan = capture_fixture._build(capture_state)
    reopened = capture_state["reopened"]
    binding = component.capture._candidate_binding(
        reopened, expected_root_identity=capture_state["root_identity"]
    )
    events: list[str] = []
    implementation_commit = "d" * 40
    measurements = _implementation_measurements()

    def tracked(plan_value: object, **_kwargs: object):
        events.append("tracked-plan")
        assert plan_value == plan
        return deepcopy(plan), implementation_commit, b"adapter-lock\n"

    def shallow(**_kwargs: object) -> dict[str, object]:
        events.append("shallow-root")
        return deepcopy(binding["root"])

    def open_candidate(**_kwargs: object):
        events.append("deep-candidate")
        return reopened, deepcopy(binding)

    def deep_plan(**_kwargs: object) -> dict[str, object]:
        events.append("deep-plan")
        return deepcopy(plan)

    inner = {
        "receipt": capture_state["base"]["replay"]["body"],
        "receipt_identity": capture_state["base"]["replay"]["identity"],
        "catalog_release": capture_state["base"]["catalogs"]["body"],
        "catalog_release_identity": capture_state["base"]["catalogs"][
            "identity"
        ],
        "structural_catalogs": [],
        "candidate_release": reopened.candidate_release,
        "candidate_release_identity": reopened.candidate_release_identity,
    }

    def derive(**_kwargs: object) -> dict[str, object]:
        events.append("derive-inner")
        return deepcopy(inner)

    def measure(**kwargs: object):
        events.append("measure")
        retained = kwargs.get("bound_commit_sha")
        return (
            implementation_commit if retained is None else retained,
            deepcopy(measurements),
        )

    upstream_identity = deepcopy(plan["upstream_source_release_identity"])

    def publish_v1(**kwargs: object) -> dict[str, object]:
        events.append("v1-publish")
        receipt = v2_fixture._v1_receipt(
            catalog_replay_identity=kwargs["fixed_g0_replay_receipt_identity"],
            catalog_release_identity=kwargs["catalog_release_identity"],
            candidate_release_identity=kwargs[
                "accepted_candidate_release_identity"
            ],
        )
        receipt.update({
            "producer_id": plan["producer_id"],
            "producer_release_id": plan["producer_release_id"],
            "producer_namespace": plan["producer_namespace"],
            "upstream_source_release_identity": upstream_identity,
        })
        _rehash_v1(receipt)
        return {
            "publication_receipt": receipt,
            "offline_panel": {
                "fixed_g0_replay_receipt_identity": kwargs[
                    "fixed_g0_replay_receipt_identity"
                ],
                "catalog_release_identity": kwargs["catalog_release_identity"],
                "accepted_candidate_release": kwargs[
                    "accepted_candidate_release"
                ],
                "accepted_candidate_release_identity": kwargs[
                    "accepted_candidate_release_identity"
                ],
            },
        }

    def durable(**kwargs: object) -> dict[str, object]:
        events.append("durable-full-reopen")
        return deepcopy(kwargs["component_result"]["offline_panel"])

    monkeypatch.setattr(component, "_tracked_plan_and_adapter_lock", tracked)
    monkeypatch.setattr(
        component, "_shallow_reopen_candidate_root_before_inner", shallow
    )
    monkeypatch.setattr(component, "_open_candidate", open_candidate)
    monkeypatch.setattr(component, "_deep_validate_plan", deep_plan)
    monkeypatch.setattr(component, "_derive_inner_inputs", derive)
    monkeypatch.setattr(component, "_measure_implementation", measure)
    monkeypatch.setattr(
        publication_v1, "publish_all_54_component_release_v1", publish_v1
    )
    monkeypatch.setattr(
        component.durable_v2, "_durable_validate_full_result", durable
    )
    return {
        "plan": plan,
        "root_identity": capture_state["root_identity"],
        "events": events,
        "binding": binding,
        "reopened": reopened,
        "upstream_identity": upstream_identity,
        "adapter_raw": capture_state["base"]["final_lock_raw"],
    }


def _publish(fixture: Mapping[str, Any]) -> dict[str, object]:
    return component.publish_all_54_component_release_outer_candidate_authority_v3(
        candidate_authority_root_identity=fixture["root_identity"],
        capture_plan=fixture["plan"],
        repository_root=Path("/fixture/repository"),
        git_head=lambda _root: "d" * 40,
        git_blob=lambda _root, _commit, _path: b"fixture",
        git_status=lambda _root, _paths: b"",
        upstream_source_release={"fixture": "upstream"},
        upstream_source_release_identity=fixture["upstream_identity"],
        upstream_pack_row_objects=[],
        publish_create_once=lambda _uri, _raw: {},
        read_exact=lambda _identity: b"fixture",
    )


def test_public_api_has_only_candidate_root_and_capture_plan_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    result = _publish(fixture)
    parameters = inspect.signature(
        component.publish_all_54_component_release_outer_candidate_authority_v3
    ).parameters
    assert "candidate_authority_root_identity" in parameters
    assert "capture_plan" in parameters
    for forbidden in (
        "fixed_g0_replay_receipt",
        "fixed_g0_replay_receipt_identity",
        "catalog_release",
        "catalog_release_identity",
        "structural_catalogs",
        "accepted_candidate_release",
        "accepted_candidate_release_identity",
        "adapter_final_release_lock_raw",
        "producer_code_identity",
        "producer_id",
        "producer_release_id",
        "producer_namespace",
    ):
        assert forbidden not in parameters
    receipt = result["publication_receipt"]
    assert receipt["catalog_recovery_outer_identity"] == fixture["binding"][
        "outer_identity"
    ]
    assert receipt["capture_plan"] == fixture["plan"]
    assert receipt["capture_plan_deep_validated"] is True
    assert receipt["all_v1_outputs_exact_reopened_before_return"] is True


def test_publish_orders_shallow_root_and_outer_equality_before_v1_and_reopens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    _publish(fixture)
    events = fixture["events"]
    assert events[:7] == [
        "tracked-plan",
        "shallow-root",
        "deep-candidate",
        "deep-plan",
        "derive-inner",
        "measure",
        "v1-publish",
    ]
    assert events[-1] == "durable-full-reopen"
    assert events.index("durable-full-reopen") > events.index("v1-publish")


def test_candidate_root_mismatch_fails_before_any_storage_reopen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    alternate = deepcopy(fixture["root_identity"])
    alternate["generation"] = str(int(str(alternate["generation"])) + 1)
    with pytest.raises(
        component.CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error,
        match="differs from tracked capture plan before reopen",
    ):
        component.publish_all_54_component_release_outer_candidate_authority_v3(
            candidate_authority_root_identity=alternate,
            capture_plan=fixture["plan"],
            repository_root=Path("/fixture/repository"),
            git_head=lambda _root: "d" * 40,
            git_blob=lambda _root, _commit, _path: b"fixture",
            git_status=lambda _root, _paths: b"",
            upstream_source_release={},
            upstream_source_release_identity=fixture["upstream_identity"],
            upstream_pack_row_objects=[],
            publish_create_once=lambda _uri, _raw: {},
            read_exact=lambda _identity: b"fixture",
        )
    assert fixture["events"] == ["tracked-plan"]


def test_tracked_plan_derives_adapter_lock_without_caller_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    tracked_plan_and_adapter_lock = component._tracked_plan_and_adapter_lock
    fixture = _fixture(monkeypatch)
    plan = fixture["plan"]
    plan_raw = source.canonical_json_bytes(plan) + b"\n"
    plan_path = tmp_path / component.capture.CAPTURE_PLAN_LOCK_PATH
    plan_path.parent.mkdir(parents=True)
    plan_path.write_bytes(plan_raw)
    adapter = plan["adapter_final_release_lock_binding"]
    adapter_raw = fixture["adapter_raw"]

    def git_blob(_root: Path, commit: str, path: str) -> bytes:
        if path == component.capture.CAPTURE_PLAN_LOCK_PATH:
            return plan_raw
        assert commit == adapter["commit_sha"]
        assert path == adapter["relative_path"]
        return adapter_raw

    reopened, observed_commit, reopened_adapter = (
        tracked_plan_and_adapter_lock(
            plan,
            repository_root=tmp_path,
            git_head=lambda _root: "e" * 40,
            git_blob=git_blob,
            git_status=lambda _root, paths: (
                b"" if paths == (component.capture.CAPTURE_PLAN_LOCK_PATH,) else b"x"
            ),
        )
    )
    assert reopened == plan
    assert observed_commit == "e" * 40
    assert reopened_adapter == adapter_raw


def test_shallow_root_rejects_outer_mismatch_before_candidate_inner_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = store_fixture.MemoryExactStore()
    state = candidate_fixture._install_core_fixture(monkeypatch, store=store)
    root, root_identity = candidate_fixture._publish(store, state)
    plan = {
        "fixed_g0_candidate_authority_root_identity": root_identity,
        "fixed_g0_candidate_authority_root_sha256": root[
            "candidate_authority_release_sha256"
        ],
        "catalog_recovery_outer_identity": root[
            "catalog_recovery_outer_identity"
        ],
        "catalog_recovery_outer_attestation_sha256": root[
            "catalog_recovery_outer_attestation_sha256"
        ],
        "catalog_recovery_candidate_binding": root[
            "catalog_recovery_candidate_binding"
        ],
        "catalog_inner_object_count": root["catalog_inner_object_count"],
        "catalog_inner_object_manifest_sha256": root[
            "catalog_inner_object_manifest_sha256"
        ],
        "fixed_g0_replay_receipt_identity": root[
            "catalog_replay_receipt_identity"
        ],
        "fixed_g0_replay_receipt_sha256": root[
            "catalog_replay_receipt_sha256"
        ],
        "catalog_release_identity": root["catalog_release_identity"],
        "catalog_release_sha256": root["catalog_release_sha256"],
        "fixed_g0_candidate_root_candidate_release_identity": root[
            "candidate_release_identity"
        ],
        "fixed_g0_candidate_root_candidate_release_sha256": root[
            "candidate_release_sha256"
        ],
    }
    store.read_calls.clear()
    changed = deepcopy(plan)
    changed["catalog_recovery_outer_attestation_sha256"] = _digest(
        "alternate-outer"
    )
    with pytest.raises(
        component.CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error,
        match="before inner read",
    ):
        component._shallow_reopen_candidate_root_before_inner(
            root_identity=root_identity,
            plan=changed,
            read_exact=store.read_exact,
        )
    assert store.read_calls == [root_identity["uri"]]


def test_shallow_root_rejects_legacy_v1_uri_without_read() -> None:
    reads: list[str] = []
    identity = candidate_fixture._identity("legacy-component-root")
    identity["uri"] = (
        f"gs://{candidate_v1.OUTPUT_BUCKET}/{candidate_v1.OUTPUT_NAMESPACE}/"
        "legacy-run-1234/candidate-authority-release.json"
    )
    with pytest.raises(
        component.CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error,
        match="legacy root rejected",
    ):
        component._shallow_reopen_candidate_root_before_inner(
            root_identity=identity,
            plan={},
            read_exact=lambda value: reads.append(str(value["uri"])) or b"x",
        )
    assert reads == []


def test_outer_receipt_tamper_fails_structurally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    result = _publish(fixture)
    changed = deepcopy(result["publication_receipt"])
    changed["catalog_recovery_outer_attestation_sha256"] = _digest(
        "attacker-outer"
    )
    changed.pop("outer_candidate_component_publication_receipt_sha256")
    changed["outer_candidate_component_publication_receipt_sha256"] = (
        source.canonical_sha256(changed)
    )
    with pytest.raises(
        component.CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error,
        match="binding differs",
    ):
        component.validate_component_publication_outer_candidate_authority_receipt_v3(
            changed
        )


def test_create_once_collision_returns_no_v3_receipt_or_durable_reopen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)

    def collision(**_kwargs: object) -> dict[str, object]:
        fixture["events"].append("v1-collision")
        raise publication_v1.CorpusR6MatchupComponentPublicationV1Error(
            "create-once collision before producer root"
        )

    monkeypatch.setattr(
        publication_v1, "publish_all_54_component_release_v1", collision
    )
    with pytest.raises(
        component.CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error,
        match="create-once collision",
    ):
        _publish(fixture)
    assert "durable-full-reopen" not in fixture["events"]


def test_authoritative_validator_rejects_receipt_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    result = _publish(fixture)
    with pytest.raises(
        component.CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error,
        match="result fields differ",
    ):
        component.validate_component_publication_against_outer_candidate_authority_v3(
            result["publication_receipt"],
            repository_root=Path("/fixture/repository"),
            read_exact=lambda _identity: b"fixture",
            git_head=lambda _root: "d" * 40,
            git_blob=lambda _root, _commit, _path: b"fixture",
            git_status=lambda _root, _paths: b"",
            upstream_source_release={},
            upstream_source_release_identity=fixture["upstream_identity"],
            upstream_pack_row_objects=[],
        )
