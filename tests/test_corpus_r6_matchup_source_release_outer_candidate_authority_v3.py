from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
from pathlib import Path
from typing import Any, Mapping

import pytest

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate_authority,
)
from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as release_v1
from nfl_dfs.research import (
    corpus_r6_matchup_source_release_candidate_authority_v2 as legacy_release_v2,
)
from nfl_dfs.research import (
    corpus_r6_matchup_source_release_outer_candidate_authority_v3 as release_v3,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from tests import test_corpus_r6_matchup_source_release_v1 as base_test


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _root_identity() -> dict[str, object]:
    return base_test._opaque_identity("candidate-v2-root", generation=880_001)


def _reopened_authority(
    base_root: Mapping[str, object],
    producer_release: Mapping[str, object],
) -> candidate_authority.ReopenedFixedG0CandidateAuthorityV2:
    entries: list[dict[str, object]] = []
    for ordinal, member_value in enumerate(base_root["entries"]):
        member = dict(member_value)
        artifact = {
            "source_task_ordinal": ordinal,
            "candidate_artifact_sha256": _digest(f"artifact-{ordinal}"),
            "candidate_count": source.ENTRY_BUDGET,
            "ordered_candidate_ids_sha256": _digest(
                f"ordered-candidates-{ordinal}"
            ),
        }
        entries.append({
            "source_task_ordinal": ordinal,
            "task_id": member["task_id"],
            "slate": member["slate"],
            "catalog_identity": member["catalog_identity"],
            "candidate_artifact": artifact,
            "candidate_artifact_identity": member["candidate_artifact_identity"],
            "candidate_count": artifact["candidate_count"],
            "ordered_candidate_ids_sha256": artifact[
                "ordered_candidate_ids_sha256"
            ],
        })
    candidate_release = {
        "task_count": source.TASK_COUNT,
        "entries": entries,
        "accepted_candidate_release_sha256": _digest("candidate-release"),
    }
    root_identity = _root_identity()
    root = {
        "target_uri": root_identity["uri"],
        "candidate_authority_release_sha256": _digest("candidate-v2-root"),
        "candidate_release_identity": base_root[
            "accepted_candidate_release_identity"
        ],
        "candidate_release_sha256": candidate_release[
            "accepted_candidate_release_sha256"
        ],
        "catalog_replay_receipt_identity": producer_release[
            "catalog_replay_receipt_identity"
        ],
        "catalog_replay_receipt_sha256": _digest("catalog-replay"),
        "candidate_population_authority": True,
        "exact_occurrence_provenance_authority": True,
        "authoritative_reopen_required": True,
        "structure_only_validation_authority": False,
        "complete": True,
    }
    return candidate_authority.ReopenedFixedG0CandidateAuthorityV2(
        root=root,
        root_identity=root_identity,
        authority_bundle={"fixture": "candidate-v2-bundle"},
        candidate_release=candidate_release,
        candidate_release_identity=dict(
            base_root["accepted_candidate_release_identity"]
        ),
    )


def _rehash(value: Mapping[str, object], field: str) -> dict[str, object]:
    return base_test._rehash(value, field)


def _adapt_capture_binding(
    fixture: dict[str, Any], binding: Mapping[str, object],
) -> None:
    retained = dict(binding)
    fixture["capture_plan_binding"] = retained
    results: list[dict[str, object]] = []
    identities: list[dict[str, object]] = []
    for result_value, identity_value in zip(
        fixture["operator_results"],
        fixture["operator_result_identities"],
        strict=True,
    ):
        result = deepcopy(dict(result_value))
        result["capture_plan_binding"] = retained
        result = _rehash(result, "matchup_operator_result_sha256")
        identity = dict(identity_value)
        identities.append(base_test._identity(
            result,
            uri=str(identity["uri"]),
            generation=int(str(identity["generation"])),
        ))
        results.append(result)
    fixture["operator_results"] = results
    fixture["operator_result_identities"] = identities


def _state(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    fixture = base_test._fixture()
    capture_plan = {
        "upstream_source_release_identity": fixture["producer_release"][
            "upstream_source_release_identity"
        ],
        "upstream_source_release_sha256": _digest("seven-pack-release"),
    }
    provisional_receipt = {
        "capture_plan": capture_plan,
        "capture_plan_sha256": _digest("capture-plan-v3"),
        "capture_plan_lock_relative_path": (
            "reports/corpus-r6-matchup-runs/fixture/capture-plan-v3.json"
        ),
        "capture_plan_observed_commit_sha": "a" * 40,
    }
    capture_binding = release_v3._capture_plan_file_binding(
        provisional_receipt
    )
    _adapt_capture_binding(fixture, capture_binding)
    base_root = release_v1.build_matchup_source_release_v1(**fixture)
    reopened = _reopened_authority(base_root, fixture["producer_release"])
    materialized_identities = [fixture["producer_release_identity"]]
    component_v1_receipt = {
        "materialized_object_count": len(materialized_identities),
        "materialized_object_identities": materialized_identities,
        "materialized_object_identity_manifest_sha256": source.canonical_sha256(
            materialized_identities
        ),
        "producer_release_identity": fixture["producer_release_identity"],
    }
    receipt = {
        **provisional_receipt,
        "outer_candidate_component_publication_receipt_sha256": _digest(
            "component-v3-receipt"
        ),
        "fixed_g0_candidate_authority_root_identity": reopened.root_identity,
        "fixed_g0_candidate_authority_root_sha256": reopened.root[
            "candidate_authority_release_sha256"
        ],
        "accepted_candidate_release_identity": reopened.candidate_release_identity,
        "accepted_candidate_release_sha256": reopened.candidate_release[
            "accepted_candidate_release_sha256"
        ],
        "catalog_replay_receipt_identity": reopened.root[
            "catalog_replay_receipt_identity"
        ],
        "catalog_replay_receipt_sha256": reopened.root[
            "catalog_replay_receipt_sha256"
        ],
        "catalog_release_identity": fixture["producer_release"][
            "catalog_release_identity"
        ],
        "catalog_release_sha256": _digest("catalog-release"),
        "producer_release_identity": fixture["producer_release_identity"],
        "producer_release_sha256": fixture["producer_release"][
            "producer_release_sha256"
        ],
        "component_successor_implementation_commit_sha": "b" * 40,
        "component_successor_implementation_measurements": [],
        "component_publication_receipt": component_v1_receipt,
    }
    component_result = {
        "publication_receipt": receipt,
        "component_publication_result": {
            "publication_receipt": component_v1_receipt,
            "offline_panel": {
                "accepted_candidate_release": reopened.candidate_release,
                "accepted_candidate_release_identity": (
                    reopened.candidate_release_identity
                ),
                "producer_release": fixture["producer_release"],
                "producer_release_identity": fixture[
                    "producer_release_identity"
                ],
            },
        },
    }
    monkeypatch.setattr(
        release_v3.component_publication_v3,
        "validate_component_publication_against_outer_candidate_authority_v3",
        lambda value, **_kwargs: deepcopy(dict(value)),
    )
    monkeypatch.setattr(
        release_v3.component_publication_v3,
        "validate_component_publication_outer_candidate_authority_receipt_v3",
        lambda value: deepcopy(dict(value)),
    )
    monkeypatch.setattr(
        release_v3,
        "_reopen_candidate_authority",
        lambda **_kwargs: reopened,
    )
    binding = {
        "candidate_authority_root_identity": reopened.root_identity,
        "candidate_authority_root_sha256": reopened.root[
            "candidate_authority_release_sha256"
        ],
        "accepted_candidate_release_identity": reopened.candidate_release_identity,
        "accepted_candidate_release_sha256": reopened.candidate_release[
            "accepted_candidate_release_sha256"
        ],
        "entries": reopened.candidate_release["entries"],
        "capture_plan_v3_sha256": receipt["capture_plan_sha256"],
        "component_publication_v3_receipt_sha256": receipt[
            "outer_candidate_component_publication_receipt_sha256"
        ],
        "component_publication_v3_receipt": receipt,
        "upstream_source_release_sha256": capture_plan[
            "upstream_source_release_sha256"
        ],
    }
    return {
        "fixture": fixture,
        "base_root": base_root,
        "reopened": reopened,
        "receipt": receipt,
        "component_result": component_result,
        "binding": binding,
    }


def _callbacks(
    read_exact: object = lambda _identity: b"unreachable",
) -> dict[str, object]:
    return {
        "repository_root": Path("/fixture/repository"),
        "read_exact": read_exact,
        "git_head": lambda _root: "a" * 40,
        "git_blob": lambda _root, _commit, _path: b"fixture",
        "git_status": lambda _root, _paths: b"",
    }


def _source_inputs(state: Mapping[str, Any]) -> dict[str, object]:
    fixture = state["fixture"]
    return {
        key: value
        for key, value in fixture.items()
        if key not in {"producer_release", "producer_release_identity"}
    } | {
        "upstream_source_release": {"fixture": "seven-pack"},
        "upstream_source_release_identity": fixture["producer_release"][
            "upstream_source_release_identity"
        ],
        "upstream_pack_row_objects": [],
    }


def _build(state: Mapping[str, Any]) -> dict[str, object]:
    return release_v3.build_matchup_source_release_outer_candidate_authority_v3(
        component_publication_candidate_authority_result=state[
            "component_result"
        ],
        **_callbacks(),
        **_source_inputs(state),
    )


def test_public_build_accepts_only_complete_v3_component_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(monkeypatch)
    parameters = inspect.signature(
        release_v3.build_matchup_source_release_outer_candidate_authority_v3
    ).parameters
    assert "component_publication_candidate_authority_result" in parameters
    assert "upstream_source_release_identity" in parameters
    assert "candidate_authority_root_identity" not in parameters
    assert "producer_release" not in parameters
    root = _build(state)
    assert root["schema_version"] == (
        release_v3.MATCHUP_SOURCE_RELEASE_OUTER_CANDIDATE_AUTHORITY_SCHEMA
    )
    assert len(root["entries"]) == source.TASK_COUNT
    assert root["capture_plan_binding"] == release_v3._capture_plan_file_binding(
        state["receipt"]
    )
    assert release_v3.validate_matchup_source_release_outer_candidate_authority_v3(
        root
    ) == root


def test_component_deep_reopen_reads_every_materialized_leaf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bodies: list[object] = [
        {"fixture": "component-leaf"},
        {"fixture": "component-producer-root"},
    ]
    identities = [
        base_test._identity(
            body,
            uri=f"gs://fixture-component/materialized-{ordinal}.json",
            generation=881_000 + ordinal,
        )
        for ordinal, body in enumerate(bodies)
    ]
    receipt = {
        "component_publication_receipt": {
            "materialized_object_count": len(identities),
            "materialized_object_identities": identities,
            "materialized_object_identity_manifest_sha256": (
                source.canonical_sha256(identities)
            ),
            "producer_release_identity": identities[-1],
        }
    }
    monkeypatch.setattr(
        release_v3.component_publication_v3,
        "validate_component_publication_outer_candidate_authority_receipt_v3",
        lambda value: deepcopy(dict(value)),
    )
    raw_by_uri = {
        str(identity["uri"]): source.canonical_json_bytes(body)
        for identity, body in zip(identities, bodies, strict=True)
    }
    reads: list[str] = []

    def read_exact(identity: Mapping[str, object]) -> bytes:
        uri = str(identity["uri"])
        reads.append(uri)
        return raw_by_uri[uri]

    proof = release_v3._reopen_all_component_materialized_objects_v3(
        receipt, read_exact=read_exact
    )
    assert reads == [str(identity["uri"]) for identity in identities]
    assert proof["materialized_object_count"] == len(identities)
    assert proof[
        "all_component_materialized_objects_generation_exact_reopened"
    ] is True

    del raw_by_uri[str(identities[-1]["uri"])]
    with pytest.raises(
        release_v3.CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error,
        match="exact reopen failed",
    ):
        release_v3._reopen_all_component_materialized_objects_v3(
            receipt, read_exact=read_exact
        )


@pytest.mark.parametrize("legacy_kind", ["v1", "v2"])
def test_structure_validator_rejects_legacy_source_roots(
    legacy_kind: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(monkeypatch)
    if legacy_kind == "v1":
        legacy = state["base_root"]
    else:
        legacy = _build(state)
        legacy["schema_version"] = (
            legacy_release_v2.MATCHUP_SOURCE_RELEASE_CANDIDATE_AUTHORITY_SCHEMA
        )
        legacy = _rehash(
            legacy, "matchup_source_release_candidate_authority_sha256"
        )
    with pytest.raises(
        release_v3.CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error
    ):
        release_v3.validate_matchup_source_release_outer_candidate_authority_v3(
            legacy
        )


@pytest.mark.parametrize("predecessor", ["capture-plan", "producer"])
def test_structure_validator_rejects_rehashed_base_predecessor_substitution(
    predecessor: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(monkeypatch)
    base = deepcopy(state["base_root"])
    if predecessor == "capture-plan":
        changed = dict(base["capture_plan_binding"])
        changed["commit_sha"] = "f" * 40
        base["capture_plan_binding"] = changed
    else:
        changed_identity = dict(base["producer_release_identity"])
        changed_identity["generation"] = str(
            int(str(changed_identity["generation"])) + 1
        )
        base["producer_release_identity"] = changed_identity
        entries = []
        for member_value in base["entries"]:
            member = deepcopy(dict(member_value))
            member["producer_release_identity"] = changed_identity
            entries.append(_rehash(member, "matchup_source_member_sha256"))
        base["entries"] = entries
        base["entry_manifest_sha256"] = source.canonical_sha256(entries)
    base = _rehash(base, "matchup_source_release_sha256")
    forged = release_v3._build_release_v3(
        base_release=base, binding=state["binding"]
    )
    with pytest.raises(
        release_v3.CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error,
        match="fixed binding differs",
    ):
        release_v3.validate_matchup_source_release_outer_candidate_authority_v3(
            forged
        )


def test_public_publish_full_replays_all_54_then_creates_only_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(monkeypatch)
    store = base_test._Store()
    fixture = state["fixture"]
    store.seed(fixture["producer_release"], fixture["producer_release_identity"])
    reopened_ordinals: list[int] = []
    monkeypatch.setattr(
        release_v1,
        "_reopen_validated_matchup_source_release_ordinal_v1",
        lambda **kwargs: reopened_ordinals.append(int(kwargs["ordinal"])) or {},
    )
    result = release_v3.publish_matchup_source_release_outer_candidate_authority_root_last_v3(
        component_publication_candidate_authority_result=state[
            "component_result"
        ],
        **_callbacks(store.read),
        **_source_inputs(state),
        publish_create_once=store.publish,
    )
    root_uri = f"{result['release']['namespace']}{release_v3.ROOT_FILENAME}"
    assert reopened_ordinals == list(range(source.TASK_COUNT))
    assert [event for event in store.events if event[0] == "publish"] == [
        ("publish", root_uri)
    ]
    assert result["release_identity"]["uri"] == root_uri


def test_public_publish_late_source_failure_creates_no_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(monkeypatch)
    store = base_test._Store()
    fixture = state["fixture"]
    store.seed(fixture["producer_release"], fixture["producer_release_identity"])

    def deep(**kwargs: object) -> dict[str, object]:
        if kwargs["ordinal"] == source.TASK_COUNT - 1:
            raise release_v1.CorpusR6MatchupSourceReleaseV1Error("late failure")
        return {}

    monkeypatch.setattr(
        release_v1, "_reopen_validated_matchup_source_release_ordinal_v1", deep
    )
    with pytest.raises(
        release_v3.CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error,
        match="late failure",
    ):
        release_v3.publish_matchup_source_release_outer_candidate_authority_root_last_v3(
            component_publication_candidate_authority_result=state[
                "component_result"
            ],
            **_callbacks(store.read),
            **_source_inputs(state),
            publish_create_once=store.publish,
        )
    assert all(event[0] != "publish" for event in store.events)


def test_public_ordinal_replays_v3_predecessors_and_returns_selected_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(monkeypatch)
    root = _build(state)
    store = base_test._Store()
    root_identity = base_test._identity(
        root,
        uri=f"{root['namespace']}{release_v3.ROOT_FILENAME}",
        generation=990_001,
    )
    store.seed(root, root_identity)
    store.seed(
        state["fixture"]["producer_release"],
        state["fixture"]["producer_release_identity"],
    )
    original_parse = release_v3._parse_exact
    upstream_identity = root["upstream_source_release_identity"]
    pack_identities = [
        base_test._opaque_identity(f"pack-{index}", generation=991_000 + index)
        for index in range(len(source.PACK_IDS))
    ]
    upstream_body = {
        "packs": [
            {"exact_rows_identity": identity} for identity in pack_identities
        ]
    }

    def parse_exact(
        identity: Mapping[str, object], **kwargs: object,
    ) -> dict[str, object]:
        if dict(identity) == dict(root_identity):
            return original_parse(identity, **kwargs)
        if dict(identity) == dict(upstream_identity):
            return upstream_body
        if any(dict(identity) == row for row in pack_identities):
            return {}
        raise AssertionError("unexpected exact read")

    monkeypatch.setattr(release_v3, "_parse_exact", parse_exact)
    monkeypatch.setattr(
        source,
        "validate_upstream_release_v1",
        lambda *_args, **_kwargs: {
            "upstream_release_sha256": root["upstream_source_release_sha256"]
        },
    )
    receipt = state["receipt"]
    monkeypatch.setattr(
        release_v3.component_publication_v3,
        "_tracked_plan_and_adapter_lock",
        lambda *_args, **_kwargs: (
            receipt["capture_plan"],
            receipt["capture_plan_observed_commit_sha"],
            b"adapter",
        ),
    )
    monkeypatch.setattr(
        release_v3.component_publication_v3,
        "_deep_validate_plan",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(
        release_v3.component_publication_v3,
        "_measure_implementation",
        lambda **_kwargs: (
            receipt["component_successor_implementation_commit_sha"],
            receipt["component_successor_implementation_measurements"],
        ),
    )
    ordinal = 17
    artifact = state["reopened"].candidate_release["entries"][ordinal][
        "candidate_artifact"
    ]
    deep = {
        "producer_release": state["fixture"]["producer_release"],
        "producer_release_entry": state["fixture"]["producer_release"][
            "entries"
        ][ordinal],
        "structural_catalog": {"fixture": "catalog"},
        "structural_players": [],
        "candidate_artifact": artifact,
        "producer_receipt": {},
        "input_bundle": {},
        "source_export": {},
        "capture_receipt": {},
        "operator_result": {},
        "annotation_rows": [],
    }
    monkeypatch.setattr(
        release_v1,
        "_reopen_validated_matchup_source_release_ordinal_v1",
        lambda **_kwargs: deep,
    )
    result = release_v3.reopen_matchup_source_release_outer_candidate_authority_ordinal_v3(
        release_identity=root_identity,
        source_task_ordinal=ordinal,
        **_callbacks(store.read),
    )
    assert result["release"]["schema_version"] == (
        release_v3.MATCHUP_SOURCE_RELEASE_OUTER_CANDIDATE_AUTHORITY_SCHEMA
    )
    assert result["member"]["source_task_ordinal"] == ordinal
    assert result["candidate_authority_binding"][
        "selected_artifact_exact_reopened"
    ] is True
    assert (
        "read",
        str(state["fixture"]["producer_release_identity"]["uri"]),
    ) in store.events
