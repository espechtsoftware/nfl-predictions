from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
from pathlib import Path
from typing import Any, Mapping

import pytest

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate,
)
from nfl_dfs.research import (
    corpus_r6_matchup_capture_plan_outer_candidate_authority_v3 as capture,
)
from nfl_dfs.research import corpus_r6_matchup_capture_plan_v1 as capture_v1
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from tests import test_corpus_r6_matchup_capture_plan_v1 as fixture_v1


def _digest(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _identity_for_body(body: object, *, uri: str) -> dict[str, object]:
    raw = source.canonical_json_bytes(body)
    return {
        "uri": uri,
        "generation": str(int(_digest(uri)[:12], 16) + 1),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _rehash(plan: dict[str, object]) -> None:
    plan.pop("capture_plan_sha256", None)
    plan["capture_plan_sha256"] = capture.canonical_sha256(plan)


def _fixture(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    base = fixture_v1._fixture()
    prefix = (
        f"gs://{candidate.OUTPUT_BUCKET}/{candidate.OUTPUT_NAMESPACE}/"
        "fixture-run-1234/"
    )
    outer = fixture_v1._opaque_identity("catalog-recovery-outer")
    outer["uri"] = candidate.recovery.OUTER_ATTESTATION_URI
    binding: dict[str, object] = {
        "catalog_recovery_outer_identity": outer,
        "catalog_recovery_outer_attestation_sha256": _digest(
            "outer-internal"
        ),
        "catalog_recovery_code_and_lock_binding": {
            "outer_attestation_identity": outer,
            "outer_attestation_sha256": _digest("outer-internal"),
        },
        "catalog_inner_object_count": 110,
        "catalog_inner_object_manifest_sha256": _digest("inner-manifest"),
        "catalog_inner_replay_receipt_identity": base["replay"]["identity"],
        "catalog_inner_replay_receipt_sha256": base["replay"]["body"][
            "replay_receipt_sha256"
        ],
        "catalog_inner_release_identity": base["catalogs"]["identity"],
        "catalog_inner_release_sha256": base["catalogs"]["body"][
            "release_sha256"
        ],
    }
    binding["candidate_implementation_binding_sha256"] = (
        source.canonical_sha256(binding)
    )
    root: dict[str, object] = {
        "schema_version": candidate.RELEASE_SCHEMA,
        "target_uri": f"{prefix}{candidate.ROOT_FILENAME}",
        "catalog_recovery_outer_identity": outer,
        "catalog_recovery_outer_attestation_sha256": binding[
            "catalog_recovery_outer_attestation_sha256"
        ],
        "catalog_recovery_candidate_binding": binding,
        "catalog_inner_object_count": 110,
        "catalog_inner_object_manifest_sha256": binding[
            "catalog_inner_object_manifest_sha256"
        ],
        "catalog_replay_receipt_identity": base["replay"]["identity"],
        "catalog_replay_receipt_sha256": base["replay"]["body"][
            "replay_receipt_sha256"
        ],
        "catalog_release_identity": base["catalogs"]["identity"],
        "catalog_release_sha256": base["catalogs"]["body"][
            "release_sha256"
        ],
        "candidate_release_identity": base["candidates"]["identity"],
        "candidate_release_sha256": base["candidates"]["body"][
            "accepted_candidate_release_sha256"
        ],
        "candidate_authority_release_sha256": _digest("candidate-root"),
        "candidate_population_authority": True,
        "exact_occurrence_provenance_authority": True,
        "authoritative_reopen_required": True,
        "structure_only_validation_authority": False,
        "catalog_recovery_outer_read_before_any_inner_read": True,
        "complete": True,
        "legacy_root_published": False,
        "published_total_object_count": candidate.TOTAL_OBJECT_COUNT,
    }
    root.pop("candidate_authority_release_sha256")
    root["candidate_authority_release_sha256"] = source.canonical_sha256(root)
    root_identity = _identity_for_body(root, uri=str(root["target_uri"]))
    reopened = candidate.ReopenedFixedG0CandidateAuthorityV2(
        root=root,
        root_identity=root_identity,
        authority_bundle={"fixture": True},
        candidate_release=base["candidates"]["body"],
        candidate_release_identity=base["candidates"]["identity"],
    )
    raw_by_identity = {
        source.canonical_json_bytes(base["replay"]["identity"]): (
            source.canonical_json_bytes(base["replay"]["body"])
        ),
        source.canonical_json_bytes(base["catalogs"]["identity"]): (
            source.canonical_json_bytes(base["catalogs"]["body"])
        ),
    }
    events: list[tuple[str, object]] = []

    def reopen(root_value: object, **_kwargs: object):
        events.append(("candidate-reopen", deepcopy(root_value)))
        return reopened

    def read_exact(identity: Mapping[str, object]) -> bytes:
        events.append(("inner-read", deepcopy(dict(identity))))
        return raw_by_identity[source.canonical_json_bytes(identity)]

    implementation_commit = "a" * 40
    implementation_raw = {
        path: f"fixture:{path}\n".encode()
        for path in capture.CAPTURE_SUCCESSOR_IMPLEMENTATION_PATHS
    }
    measurements = [{
        "relative_path": path,
        "sha256": sha256(implementation_raw[path]).hexdigest(),
        "bytes": len(implementation_raw[path]),
    } for path in capture.CAPTURE_SUCCESSOR_IMPLEMENTATION_PATHS]

    def measure(**kwargs: object):
        bound = kwargs.get("bound_commit_sha")
        return (implementation_commit if bound is None else bound), deepcopy(
            measurements
        )

    monkeypatch.setattr(
        candidate, "reopen_fixed_g0_candidate_authority_release_v2", reopen
    )
    monkeypatch.setattr(capture, "_measure_implementation", measure)
    return {
        "base": base,
        "root": root,
        "root_identity": root_identity,
        "reopened": reopened,
        "read_exact": read_exact,
        "events": events,
        "implementation_commit": implementation_commit,
        "implementation_raw": implementation_raw,
        "measurements": measurements,
    }


def _build(fixture: Mapping[str, Any]) -> dict[str, object]:
    base = fixture["base"]
    return capture.build_capture_plan_lock_v3(
        adapter_final_release_lock_commit_sha=base["final_lock_commit"],
        adapter_final_release_lock_raw=base["final_lock_raw"],
        candidate_authority_root_identity=fixture["root_identity"],
        repository_root=Path("/fixture/repository"),
        read_exact=fixture["read_exact"],
        git_head=lambda _root: fixture["implementation_commit"],
        git_blob=lambda _root, _commit, path: fixture["implementation_raw"][path],
        git_status=lambda _root, _paths: b"",
        upstream_source_release=base["upstream"]["body"],
        upstream_source_release_identity=base["upstream"]["identity"],
        upstream_pack_row_objects=base["upstream"]["rows"],
        producer_id="r6-matchup-component-producer-v1",
        producer_release_id="r6-matchup-component-panel-v1",
        producer_namespace=fixture_v1.PRODUCER_NAMESPACE,
    )


def _validate(
    plan: Mapping[str, object], fixture: Mapping[str, Any],
) -> dict[str, object]:
    base = fixture["base"]
    return capture.validate_capture_plan_against_prerequisites_v3(
        plan,
        repository_root=Path("/fixture/repository"),
        read_exact=fixture["read_exact"],
        git_head=lambda _root: fixture["implementation_commit"],
        git_blob=lambda _root, _commit, path: fixture["implementation_raw"][path],
        git_status=lambda _root, _paths: b"",
        adapter_final_release_lock_commit_sha=base["final_lock_commit"],
        adapter_final_release_lock_raw=base["final_lock_raw"],
        upstream_source_release=base["upstream"]["body"],
        upstream_source_release_identity=base["upstream"]["identity"],
        upstream_pack_row_objects=base["upstream"]["rows"],
    )


def test_builder_exposes_only_outer_bound_candidate_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    parameters = inspect.signature(capture.build_capture_plan_lock_v3).parameters

    assert "candidate_authority_root_identity" in parameters
    for forbidden in (
        "fixed_g0_replay_receipt",
        "fixed_g0_replay_receipt_identity",
        "catalog_release",
        "catalog_release_identity",
        "accepted_candidate_release",
        "accepted_candidate_release_identity",
        "implementation_commit_sha",
        "implementation_measurements",
    ):
        assert forbidden not in parameters
    assert [event[0] for event in fixture["events"]] == [
        "candidate-reopen", "inner-read", "inner-read"
    ]
    assert plan["catalog_recovery_outer_identity"] == fixture["root"][
        "catalog_recovery_outer_identity"
    ]
    assert plan["fixed_g0_candidate_authority_root_identity"] == fixture[
        "root_identity"
    ]
    assert plan["candidate_authority_v1_root_accepted"] is False
    assert plan["inner_compatibility_inputs_derived_from_candidate_root"] is True
    assert plan["capture_successor_remote_exact_read_performed"] is True
    assert "lock_builder_cloud_read_performed" not in plan
    assert capture.validate_capture_plan_lock_v3(plan) == plan

    validator_parameters = inspect.signature(
        capture.validate_capture_plan_against_prerequisites_v3
    ).parameters
    for forbidden in (
        "fixed_g0_replay_receipt",
        "fixed_g0_replay_receipt_identity",
        "catalog_release",
        "catalog_release_identity",
        "accepted_candidate_release",
        "accepted_candidate_release_identity",
    ):
        assert forbidden not in validator_parameters


def test_deep_validator_reopens_root_and_byte_rebuilds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    assert _validate(plan, fixture) == plan
    assert [event[0] for event in fixture["events"]] == [
        "candidate-reopen", "inner-read", "inner-read",
        "candidate-reopen", "inner-read", "inner-read",
    ]


def test_coherent_root_substitution_is_structure_only_and_fails_reopen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    changed = deepcopy(plan)
    alternate = deepcopy(fixture["root_identity"])
    alternate["uri"] = str(alternate["uri"]).replace(
        "fixture-run-1234", "alternate-run-9876"
    )
    alternate["generation"] = str(int(str(alternate["generation"])) + 1)
    changed["fixed_g0_candidate_authority_root_identity"] = alternate
    changed["fixed_g0_candidate_authority_root_sha256"] = _digest(
        "alternate-root"
    )
    _rehash(changed)

    assert capture.validate_capture_plan_lock_v3(changed) == changed
    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error,
        match="root binding differs",
    ):
        _validate(changed, fixture)


def test_coherent_outer_substitution_fails_candidate_root_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    changed = deepcopy(plan)
    alternate = deepcopy(changed["catalog_recovery_outer_identity"])
    alternate["generation"] = str(int(str(alternate["generation"])) + 1)
    changed["catalog_recovery_outer_identity"] = alternate
    changed["catalog_recovery_outer_attestation_sha256"] = _digest(
        "alternate-outer"
    )
    changed_binding = deepcopy(changed["catalog_recovery_candidate_binding"])
    changed_binding["catalog_recovery_outer_identity"] = alternate
    changed_binding["catalog_recovery_outer_attestation_sha256"] = changed[
        "catalog_recovery_outer_attestation_sha256"
    ]
    changed_binding["catalog_recovery_code_and_lock_binding"][
        "outer_attestation_identity"
    ] = alternate
    changed_binding["catalog_recovery_code_and_lock_binding"][
        "outer_attestation_sha256"
    ] = changed["catalog_recovery_outer_attestation_sha256"]
    changed_binding.pop("candidate_implementation_binding_sha256")
    changed_binding["candidate_implementation_binding_sha256"] = (
        source.canonical_sha256(changed_binding)
    )
    changed["catalog_recovery_candidate_binding"] = changed_binding
    _rehash(changed)

    assert capture.validate_capture_plan_lock_v3(changed) == changed
    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error,
        match="outer/root differ",
    ):
        _validate(changed, fixture)


def test_candidate_binding_self_hash_tamper_fails_structure_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    changed = deepcopy(plan)
    changed_binding = deepcopy(changed["catalog_recovery_candidate_binding"])
    changed_binding["candidate_implementation_binding_sha256"] = _digest(
        "alternate-candidate-binding"
    )
    changed["catalog_recovery_candidate_binding"] = changed_binding
    _rehash(changed)

    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error,
        match="projection differs",
    ):
        capture.validate_capture_plan_lock_v3(changed)


def test_inherited_v1_implementation_cannot_fork_successor_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    changed = deepcopy(plan)
    changed["implementation_commit_sha"] = "c" * 40
    changed["source_v2_code_identity"]["source_commit_sha"] = "c" * 40
    changed["component_producer_code_identity"]["source_commit_sha"] = "c" * 40
    _rehash(changed)

    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error,
        match="v1 implementation projection differs",
    ):
        capture.validate_capture_plan_lock_v3(changed)


def test_candidate_reopen_failure_precedes_inner_and_legacy_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    fixture["events"].clear()
    build_calls = 0

    def fail_reopen(*_args: object, **_kwargs: object) -> object:
        fixture["events"].append(("candidate-reopen", None))
        raise ValueError("candidate unavailable")

    def legacy_build(**_kwargs: object) -> dict[str, object]:
        nonlocal build_calls
        build_calls += 1
        return {}

    monkeypatch.setattr(
        candidate, "reopen_fixed_g0_candidate_authority_release_v2", fail_reopen
    )
    monkeypatch.setattr(capture_v1, "build_capture_plan_lock_v1", legacy_build)
    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error,
        match="candidate-authority v2 exact reopen failed",
    ):
        _build(fixture)
    assert fixture["events"] == [("candidate-reopen", None)]
    assert build_calls == 0


def test_tracked_reopen_preserves_adapter_final_and_g0_git_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    raw_plan = capture.canonical_json_bytes(plan) + b"\n"
    plan_commit = "b" * 40
    blob_by_key: dict[tuple[str, str], bytes] = {
        (plan_commit, capture.CAPTURE_PLAN_LOCK_PATH): raw_plan,
    }
    for row in plan["capture_successor_implementation_measurements"]:
        blob_by_key[(
            str(plan["capture_successor_implementation_commit_sha"]),
            str(row["relative_path"]),
        )] = fixture["implementation_raw"][str(row["relative_path"])]
    final_binding = plan["adapter_final_release_lock_binding"]
    blob_by_key[(
        str(final_binding["commit_sha"]), str(final_binding["relative_path"])
    )] = fixture["base"]["final_lock_raw"]
    fixed = capture_v1.fixed_g0_authority_binding_v1()
    g0_raw = Path(str(fixed["g0_lock_relative_path"])).read_bytes()
    blob_by_key[(
        str(fixed["evidence_source_commit_sha"]),
        str(fixed["g0_lock_relative_path"]),
    )] = g0_raw
    reads: list[tuple[str, str]] = []

    def read_blob(commit: str, path: str) -> bytes:
        reads.append((commit, path))
        return blob_by_key[(commit, path)]

    def current(path: str) -> dict[str, object]:
        matches = [raw for (_commit, item_path), raw in blob_by_key.items()
                   if item_path == path]
        assert len(matches) == 1
        return fixture_v1._secure_observation(path, matches[0])

    assert capture.reopen_capture_plan_lock_from_git_v3(
        plan_commit_sha=plan_commit,
        plan_file_sha256=sha256(raw_plan).hexdigest(),
        plan_file_bytes=len(raw_plan),
        read_git_blob=read_blob,
        secure_read_current=current,
        repository_clean=True,
    ) == plan
    assert (
        str(final_binding["commit_sha"]), str(final_binding["relative_path"])
    ) in reads
    assert (
        str(fixed["evidence_source_commit_sha"]),
        str(fixed["g0_lock_relative_path"]),
    ) in reads


def test_tracked_reopen_rejects_successor_code_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    plan = _build(fixture)
    raw_plan = capture.canonical_json_bytes(plan) + b"\n"
    first = plan["capture_successor_implementation_measurements"][0]
    expected_by_path = {
        capture.CAPTURE_PLAN_LOCK_PATH: raw_plan,
        **fixture["implementation_raw"],
    }

    def read_blob(_commit: str, path: str) -> bytes:
        return expected_by_path[path]

    def current(path: str) -> dict[str, object]:
        raw = expected_by_path[path]
        if path == first["relative_path"]:
            raw += b"drift"
        return fixture_v1._secure_observation(path, raw)

    with pytest.raises(
        capture.CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error,
        match="exact-byte replay differs",
    ):
        capture.reopen_capture_plan_lock_from_git_v3(
            plan_commit_sha="b" * 40,
            plan_file_sha256=sha256(raw_plan).hexdigest(),
            plan_file_bytes=len(raw_plan),
            read_git_blob=read_blob,
            secure_read_current=current,
            repository_clean=True,
        )
