from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
from pathlib import Path
from typing import Any, Mapping

import pytest

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v1 as candidate_authority,
)
from nfl_dfs.research import (
    corpus_r6_matchup_capture_plan_candidate_authority_v2 as plan_v2,
)
from nfl_dfs.research import corpus_r6_matchup_capture_plan_v1 as plan_v1
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


def _digest(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _identity(uri: str, label: str) -> dict[str, object]:
    raw = source.canonical_json_bytes({"fixture": label})
    return {
        "uri": uri,
        "generation": str(int(_digest(label)[:10], 16)),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _fixture(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    prefix = (
        f"gs://{candidate_authority.OUTPUT_BUCKET}/"
        f"{candidate_authority.OUTPUT_NAMESPACE}/fixture-run-1234/"
    )
    root_identity = _identity(
        f"{prefix}{candidate_authority.ROOT_FILENAME}", "candidate-root"
    )
    candidate_identity = _identity(
        f"{prefix}{candidate_authority.CANDIDATE_RELEASE_FILENAME}",
        "candidate-release",
    )
    catalog_identity = _identity(
        "gs://fixture-catalog/fixed-g0-replay-receipt.json", "catalog"
    )
    release_sha = _digest("candidate-release-internal")
    catalog_sha = _digest("catalog-internal")
    root_sha = _digest("candidate-root-internal")
    candidate_release = {
        "accepted_candidate_release_sha256": release_sha,
        "fixture": True,
    }
    root = {
        "target_uri": root_identity["uri"],
        "candidate_authority_release_sha256": root_sha,
        "candidate_release_identity": candidate_identity,
        "candidate_release_sha256": release_sha,
        "catalog_replay_receipt_identity": catalog_identity,
        "catalog_replay_receipt_sha256": catalog_sha,
        "candidate_population_authority": True,
        "exact_occurrence_provenance_authority": True,
        "authoritative_reopen_required": True,
        "structure_only_validation_authority": False,
        "complete": True,
    }
    reopened = candidate_authority.ReopenedFixedG0CandidateAuthorityV1(
        root=root,
        root_identity=root_identity,
        authority_bundle={"fixture": True},
        candidate_release=candidate_release,
        candidate_release_identity=candidate_identity,
    )
    base_keys = frozenset({
        "schema_version",
        "capture_plan_id",
        "capture_plan_scope",
        "capture_plan_lock_relative_path",
        "fixed_g0_replay_receipt_identity",
        "fixed_g0_replay_receipt_sha256",
        "accepted_candidate_release_identity",
        "accepted_candidate_release_sha256",
        "capture_plan_sha256",
    })
    monkeypatch.setattr(plan_v2, "_PLAN_FIELDS", frozenset({
        *base_keys,
        *plan_v2._SUCCESSOR_FIELDS,
    }))
    reopen_calls: list[Mapping[str, object]] = []
    base_build_calls: list[dict[str, object]] = []

    def reopen(root_value: Mapping[str, object], **_kwargs: object):
        reopen_calls.append(dict(root_value))
        return reopened

    def validate_base(value: object) -> dict[str, object]:
        assert isinstance(value, Mapping)
        item = dict(value)
        assert set(item) == set(base_keys)
        retained = item.pop("capture_plan_sha256")
        assert retained == plan_v1.canonical_sha256(item)
        assert item["schema_version"] == plan_v1.CAPTURE_PLAN_SCHEMA
        assert item["capture_plan_id"] == plan_v1.CAPTURE_PLAN_ID
        assert item["capture_plan_scope"] == plan_v1.CAPTURE_PLAN_SCOPE
        assert item["capture_plan_lock_relative_path"] == plan_v1.CAPTURE_PLAN_LOCK_PATH
        item["capture_plan_sha256"] = retained
        return item

    def build_base(**kwargs: object) -> dict[str, object]:
        base_build_calls.append(dict(kwargs))
        body = {
            "schema_version": plan_v1.CAPTURE_PLAN_SCHEMA,
            "capture_plan_id": plan_v1.CAPTURE_PLAN_ID,
            "capture_plan_scope": plan_v1.CAPTURE_PLAN_SCOPE,
            "capture_plan_lock_relative_path": plan_v1.CAPTURE_PLAN_LOCK_PATH,
            "fixed_g0_replay_receipt_identity": kwargs[
                "fixed_g0_replay_receipt_identity"
            ],
            "fixed_g0_replay_receipt_sha256": catalog_sha,
            "accepted_candidate_release_identity": kwargs[
                "accepted_candidate_release_identity"
            ],
            "accepted_candidate_release_sha256": release_sha,
        }
        body["capture_plan_sha256"] = plan_v1.canonical_sha256(body)
        return validate_base(body)

    monkeypatch.setattr(
        candidate_authority,
        "reopen_fixed_g0_candidate_authority_release_v1",
        reopen,
    )
    monkeypatch.setattr(plan_v1, "validate_capture_plan_lock_v1", validate_base)
    monkeypatch.setattr(plan_v1, "build_capture_plan_lock_v1", build_base)
    monkeypatch.setattr(
        plan_v1,
        "validate_capture_plan_against_prerequisites_v1",
        lambda value, **_kwargs: validate_base(value),
    )
    return {
        "root_identity": root_identity,
        "candidate_identity": candidate_identity,
        "candidate_release": candidate_release,
        "catalog_identity": catalog_identity,
        "catalog_sha": catalog_sha,
        "root_sha": root_sha,
        "release_sha": release_sha,
        "root": root,
        "reopened": reopened,
        "reopen_calls": reopen_calls,
        "base_build_calls": base_build_calls,
    }


def _build(fixture: Mapping[str, Any]) -> dict[str, object]:
    return plan_v2.build_capture_plan_lock_v2(
        adapter_final_release_lock_commit_sha="1" * 40,
        adapter_final_release_lock_raw=b"fixture\n",
        fixed_g0_replay_receipt={"fixture": True},
        fixed_g0_replay_receipt_identity=fixture["catalog_identity"],
        catalog_release={"fixture": True},
        catalog_release_identity=_identity(
            "gs://fixture-catalog/catalog-release.json", "catalog-release"
        ),
        candidate_authority_root_identity=fixture["root_identity"],
        repository_root=Path("/fixture"),
        read_exact=lambda _identity: b"fixture",
        git_head=lambda _root: "1" * 40,
        git_blob=lambda _root, _commit, _path: b"fixture",
        git_status=lambda _root, _paths: b"",
        upstream_source_release={"fixture": True},
        upstream_source_release_identity=_identity(
            "gs://fixture-upstream/upstream-release.json", "upstream"
        ),
        upstream_pack_row_objects=[],
        implementation_commit_sha="2" * 40,
        implementation_measurements=[],
        producer_id="fixture-producer",
        producer_release_id="fixture-release",
        producer_namespace="gs://fixture-producer/output/",
    )


def _validate_exact(
    plan: Mapping[str, object], fixture: Mapping[str, Any],
) -> dict[str, object]:
    return plan_v2.validate_capture_plan_against_prerequisites_v2(
        plan,
        repository_root=Path("/fixture"),
        read_exact=lambda _identity: b"fixture",
        git_head=lambda _root: "1" * 40,
        git_blob=lambda _root, _commit, _path: b"fixture",
        git_status=lambda _root, _paths: b"",
        adapter_final_release_lock_commit_sha="1" * 40,
        adapter_final_release_lock_raw=b"fixture\n",
        fixed_g0_replay_receipt={"fixture": True},
        fixed_g0_replay_receipt_identity=fixture["catalog_identity"],
        catalog_release={"fixture": True},
        catalog_release_identity=_identity(
            "gs://fixture-catalog/catalog-release.json", "catalog-release"
        ),
        upstream_source_release={"fixture": True},
        upstream_source_release_identity=_identity(
            "gs://fixture-upstream/upstream-release.json", "upstream"
        ),
        upstream_pack_row_objects=[],
    )


def _rehash(plan: dict[str, object]) -> None:
    plan["capture_plan_sha256"] = plan_v2.canonical_sha256({
        key: value for key, value in plan.items() if key != "capture_plan_sha256"
    })


def test_builder_accepts_only_root_identity_and_exact_reopens_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    parameters = inspect.signature(plan_v2.build_capture_plan_lock_v2).parameters
    assert "candidate_authority_root_identity" in parameters
    assert "accepted_candidate_release" not in parameters
    assert "accepted_candidate_release_identity" not in parameters
    assert fixture["reopen_calls"] == [fixture["root_identity"]]
    assert fixture["base_build_calls"][0]["accepted_candidate_release"] == (
        fixture["candidate_release"]
    )
    assert fixture["base_build_calls"][0][
        "accepted_candidate_release_identity"
    ] == fixture["candidate_identity"]
    assert plan["fixed_g0_candidate_authority_root_identity"] == fixture[
        "root_identity"
    ]
    assert plan["fixed_g0_candidate_root_exact_reopened"] is True
    assert plan["exact_occurrence_provenance_binding_verified"] is True
    assert plan["candidate_authority_structure_only_authority"] is False
    assert plan_v2.validate_capture_plan_lock_v2(plan) == plan


def test_exact_validator_reopens_internal_root_not_a_caller_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    assert _validate_exact(plan, fixture) == plan
    assert fixture["reopen_calls"] == [
        fixture["root_identity"],
        fixture["root_identity"],
    ]


def test_coherent_structure_only_root_substitution_fails_exact_reopen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    changed = deepcopy(plan)
    alternate_prefix = (
        f"gs://{candidate_authority.OUTPUT_BUCKET}/"
        f"{candidate_authority.OUTPUT_NAMESPACE}/alternate-run-9/"
    )
    changed_root = _identity(
        f"{alternate_prefix}{candidate_authority.ROOT_FILENAME}", "alternate-root"
    )
    changed_candidate = _identity(
        f"{alternate_prefix}{candidate_authority.CANDIDATE_RELEASE_FILENAME}",
        "alternate-candidate",
    )
    changed["fixed_g0_candidate_authority_root_identity"] = changed_root
    changed["fixed_g0_candidate_root_candidate_release_identity"] = changed_candidate
    changed["accepted_candidate_release_identity"] = changed_candidate
    _rehash(changed)
    assert plan_v2.validate_capture_plan_lock_v2(changed) == changed
    with pytest.raises(
        plan_v2.CorpusR6MatchupCapturePlanCandidateAuthorityV2Error,
        match="root binding differs",
    ):
        _validate_exact(changed, fixture)


def test_build_rejects_candidate_root_on_different_catalog_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    fixture["root"]["catalog_replay_receipt_identity"] = _identity(
        "gs://fixture-catalog/other-replay.json", "other-catalog"
    )
    with pytest.raises(
        plan_v2.CorpusR6MatchupCapturePlanCandidateAuthorityV2Error,
        match="different catalog roots",
    ):
        _build(fixture)


def test_root_reopen_failure_never_calls_legacy_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)

    def fail_reopen(*_args: object, **_kwargs: object) -> object:
        raise ValueError("missing generation")

    monkeypatch.setattr(
        candidate_authority,
        "reopen_fixed_g0_candidate_authority_release_v1",
        fail_reopen,
    )
    with pytest.raises(
        plan_v2.CorpusR6MatchupCapturePlanCandidateAuthorityV2Error,
        match="exact reopen failed",
    ):
        _build(fixture)
    assert fixture["base_build_calls"] == []
