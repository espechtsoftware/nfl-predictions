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
from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as release_v1
from nfl_dfs.research import (
    corpus_r6_matchup_source_release_candidate_authority_v2 as release_v2,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from tests import test_corpus_r6_matchup_source_release_v1 as base_test


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _root_identity(label: str = "candidate-root") -> dict[str, object]:
    uri = (
        f"gs://{candidate_authority.OUTPUT_BUCKET}/"
        f"{candidate_authority.OUTPUT_NAMESPACE}/fixture-run-001/"
        f"{candidate_authority.ROOT_FILENAME}"
    )
    return {
        "uri": uri,
        "generation": "880001",
        "sha256": _digest(label),
        "bytes": 12345,
    }


def _reopened_authority(
    base_root: Mapping[str, object],
    producer_release: Mapping[str, object],
    *,
    root_identity: Mapping[str, object] | None = None,
) -> candidate_authority.ReopenedFixedG0CandidateAuthorityV1:
    retained_root_identity = dict(root_identity or _root_identity())
    entries: list[dict[str, object]] = []
    for ordinal, member in enumerate(base_root["entries"]):
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
            "candidate_artifact_identity": member[
                "candidate_artifact_identity"
            ],
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
    root = {
        "target_uri": retained_root_identity["uri"],
        "candidate_authority_release_sha256": _digest("candidate-root-internal"),
        "candidate_release_identity": base_root[
            "accepted_candidate_release_identity"
        ],
        "candidate_release_sha256": candidate_release[
            "accepted_candidate_release_sha256"
        ],
        "catalog_replay_receipt_identity": producer_release[
            "catalog_replay_receipt_identity"
        ],
        "catalog_replay_receipt_sha256": _digest("catalog-replay-internal"),
        "candidate_population_authority": True,
        "exact_occurrence_provenance_authority": True,
        "authoritative_reopen_required": True,
        "structure_only_validation_authority": False,
        "complete": True,
    }
    return candidate_authority.ReopenedFixedG0CandidateAuthorityV1(
        root=root,
        root_identity=retained_root_identity,
        authority_bundle={"fixture": "authority-bundle"},
        candidate_release=candidate_release,
        candidate_release_identity=base_root[
            "accepted_candidate_release_identity"
        ],
    )


def _callbacks() -> dict[str, object]:
    return {
        "repository_root": Path("."),
        "read_exact": lambda identity: b"unreachable",
        "git_head": lambda root: "a" * 40,
        "git_blob": lambda root, commit, path: b"unreachable",
        "git_status": lambda root, paths: b"",
    }


def _build_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], dict[str, object], Any, dict[str, object]]:
    fixture = base_test._fixture()
    base_root = release_v1.build_matchup_source_release_v1(**fixture)
    reopened = _reopened_authority(
        base_root, fixture["producer_release"]
    )
    monkeypatch.setattr(
        release_v2,
        "_reopen_candidate_authority",
        lambda **kwargs: reopened,
    )
    component_result = {
        "publication_receipt": {
            "candidate_authority_root_identity": reopened.root_identity,
            "candidate_authority_root_sha256": reopened.root[
                "candidate_authority_release_sha256"
            ],
            "accepted_candidate_release_identity": (
                reopened.candidate_release_identity
            ),
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
            "catalog_release_sha256": _digest("catalog-release-internal"),
        },
        "component_publication_result": {
            "publication_receipt": {"fixture": "v1-receipt"},
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
        release_v2.component_publication_v2,
        "validate_component_publication_against_candidate_authority_v2",
        lambda value, **kwargs: value,
    )
    return fixture, base_root, reopened, component_result


def _source_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in fixture.items()
        if key not in {"producer_release", "producer_release_identity"}
    }


def _build(
    fixture: Mapping[str, Any],
    *,
    component_result: Mapping[str, object],
) -> dict[str, object]:
    return release_v2.build_matchup_source_release_candidate_authority_v2(
        component_publication_candidate_authority_result=component_result,
        **_callbacks(),
        **_source_fixture(fixture),
    )


def _rehash_member(member: Mapping[str, object]) -> dict[str, object]:
    body = deepcopy(dict(member))
    body.pop("matchup_source_member_candidate_authority_sha256", None)
    body["matchup_source_member_candidate_authority_sha256"] = (
        source.canonical_sha256(body)
    )
    return body


def _rehash_root(root: Mapping[str, object]) -> dict[str, object]:
    body = deepcopy(dict(root))
    body.pop("matchup_source_release_candidate_authority_sha256", None)
    body["matchup_source_release_candidate_authority_sha256"] = (
        source.canonical_sha256(body)
    )
    return body


def test_public_apis_accept_only_full_v2_component_candidate_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, _, _, component_result = _build_fixture(monkeypatch)
    for function in (
        release_v2.build_matchup_source_release_candidate_authority_v2,
        release_v2.publish_matchup_source_release_candidate_authority_root_last_v2,
    ):
        parameters = inspect.signature(function).parameters
        assert "component_publication_candidate_authority_result" in parameters
        assert "candidate_authority_root_identity" not in parameters
        assert "producer_release" not in parameters
        assert "producer_release_identity" not in parameters
        assert "accepted_candidate_release" not in parameters
        assert "accepted_candidate_release_identity" not in parameters
        assert "candidate_artifact" not in parameters
    root = _build(fixture, component_result=component_result)
    assert root["schema_version"] == (
        release_v2.MATCHUP_SOURCE_RELEASE_CANDIDATE_AUTHORITY_SCHEMA
    )
    assert release_v2.validate_matchup_source_release_candidate_authority_v2(
        root
    ) == root
    assert len(root["entries"]) == source.TASK_COUNT
    assert all(
        member["schema_version"]
        == release_v2.MATCHUP_SOURCE_MEMBER_CANDIDATE_AUTHORITY_SCHEMA
        and member["candidate_authority_root_identity"]
        == root["candidate_authority_root_identity"]
        and member["accepted_candidate_release_identity"]
        == root["accepted_candidate_release_identity"]
        for member in root["entries"]
    )
    with pytest.raises(
        release_v2.CorpusR6MatchupSourceReleaseCandidateAuthorityV2Error,
        match="component publication result fields differ",
    ):
        _build(
            fixture,
            component_result=component_result["component_publication_result"],
        )


def test_late_candidate_artifact_substitution_fails_all_54_cross_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, base_root, _, component_result = _build_fixture(monkeypatch)
    changed_result = deepcopy(component_result)
    changed_release = changed_result["component_publication_result"][
        "offline_panel"
    ]["accepted_candidate_release"]
    changed_release["entries"][53]["candidate_artifact_identity"] = (
        base_test._opaque_identity("alternate-candidate-53", generation=990053)
    )
    with pytest.raises(
        release_v2.CorpusR6MatchupSourceReleaseCandidateAuthorityV2Error,
        match="candidate-authority entry differs from source member",
    ):
        _build(fixture, component_result=changed_result)
    assert base_root["entries"][53]["candidate_artifact_identity"] != (
        changed_release["entries"][53]["candidate_artifact_identity"]
    )


def test_reopener_returns_v2_root_member_and_exact_candidate_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, base_root, reopened, component_result = _build_fixture(monkeypatch)
    root = _build(fixture, component_result=component_result)
    store = base_test._Store()
    root_identity = base_test._identity(
        root,
        uri=f"{root['namespace']}{release_v2.ROOT_FILENAME}",
        generation=990001,
    )
    store.seed(root, root_identity)
    ordinal = 17
    selected_artifact = reopened.candidate_release["entries"][ordinal][
        "candidate_artifact"
    ]
    deep = {
        "release": base_root,
        "member": base_root["entries"][ordinal],
        "producer_release": fixture["producer_release"],
        "producer_release_entry": fixture["producer_release"]["entries"][ordinal],
        "structural_catalog": {"fixture": "catalog"},
        "structural_players": [{"id": "p01"}],
        "candidate_artifact": selected_artifact,
        "producer_receipt": {"fixture": "producer-receipt"},
        "input_bundle": {"fixture": "input-bundle"},
        "source_export": {"fixture": "source-export"},
        "capture_receipt": {"fixture": "capture-receipt"},
        "operator_result": {"fixture": "operator-result"},
        "annotation_rows": [{"gsis_id": "p01"}],
    }
    monkeypatch.setattr(
        release_v1,
        "_reopen_validated_matchup_source_release_ordinal_v1",
        lambda **kwargs: deep,
    )
    result = release_v2.reopen_matchup_source_release_candidate_authority_ordinal_v2(
        release_identity=root_identity,
        source_task_ordinal=ordinal,
        repository_root=Path("."),
        read_exact=store.read,
        git_head=lambda root_path: "a" * 40,
        git_blob=lambda root_path, commit, path: b"unreachable",
        git_status=lambda root_path, paths: b"",
    )
    assert set(result) == {
        "release_identity", "release", "member", "producer_release",
        "producer_release_entry", "structural_catalog", "structural_players",
        "candidate_artifact", "producer_receipt", "input_bundle",
        "source_export", "capture_receipt", "operator_result",
        "annotation_rows", "candidate_authority_binding",
    }
    assert result["release"]["schema_version"] == (
        release_v2.MATCHUP_SOURCE_RELEASE_CANDIDATE_AUTHORITY_SCHEMA
    )
    assert result["member"]["schema_version"] == (
        release_v2.MATCHUP_SOURCE_MEMBER_CANDIDATE_AUTHORITY_SCHEMA
    )
    binding = result["candidate_authority_binding"]
    assert set(binding) == release_v2._CANDIDATE_BINDING_FIELDS
    assert binding["candidate_artifact_identity"] == result["member"][
        "candidate_artifact_identity"
    ]


def test_selected_candidate_binding_rejects_catalog_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, _, reopened, component_result = _build_fixture(monkeypatch)
    root = _build(fixture, component_result=component_result)
    ordinal = 22
    member = deepcopy(root["entries"][ordinal])
    member["catalog_identity"] = base_test._opaque_identity(
        "alternate-selected-catalog", generation=991022
    )
    with pytest.raises(
        release_v2.CorpusR6MatchupSourceReleaseCandidateAuthorityV2Error,
        match="artifact differs from source member",
    ):
        release_v2._selected_candidate_binding(
            root=root,
            member=member,
            reopened=reopened,
            ordinal=ordinal,
            source_candidate_artifact=reopened.candidate_release["entries"][
                ordinal
            ]["candidate_artifact"],
        )


def test_reopener_rejects_candidate_root_or_selected_artifact_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, base_root, reopened, component_result = _build_fixture(monkeypatch)
    root = _build(fixture, component_result=component_result)
    store = base_test._Store()
    root_identity = base_test._identity(
        root,
        uri=f"{root['namespace']}{release_v2.ROOT_FILENAME}",
        generation=990002,
    )
    store.seed(root, root_identity)
    ordinal = 9
    deep = {
        "candidate_artifact": {
            "source_task_ordinal": ordinal,
            "candidate_artifact_sha256": _digest("different-artifact"),
        },
        **{
            key: {"fixture": key}
            for key in (
                "producer_release", "producer_release_entry",
                "structural_catalog", "producer_receipt", "input_bundle",
                "source_export", "capture_receipt", "operator_result",
            )
        },
        "structural_players": [],
        "annotation_rows": [],
        "release": base_root,
        "member": base_root["entries"][ordinal],
    }
    monkeypatch.setattr(
        release_v1,
        "_reopen_validated_matchup_source_release_ordinal_v1",
        lambda **kwargs: deep,
    )
    with pytest.raises(
        release_v2.CorpusR6MatchupSourceReleaseCandidateAuthorityV2Error,
        match="artifact differs from source member",
    ):
        release_v2.reopen_matchup_source_release_candidate_authority_ordinal_v2(
            release_identity=root_identity,
            source_task_ordinal=ordinal,
            repository_root=Path("."),
            read_exact=store.read,
            git_head=lambda root_path: "a" * 40,
            git_blob=lambda root_path, commit, path: b"unreachable",
            git_status=lambda root_path, paths: b"",
        )

    changed_root = deepcopy(root)
    alternate = base_test._opaque_identity(
        "alternate-authority-root", generation=990099
    )
    changed_root["candidate_authority_root_identity"] = alternate
    for offset, member in enumerate(changed_root["entries"]):
        member["candidate_authority_root_identity"] = alternate
        changed_root["entries"][offset] = _rehash_member(member)
    changed_root["entry_manifest_sha256"] = source.canonical_sha256(
        changed_root["entries"]
    )
    changed_root = _rehash_root(changed_root)
    changed_identity = base_test._identity(
        changed_root,
        uri=f"{root['namespace']}{release_v2.ROOT_FILENAME}",
        generation=990003,
    )
    store.seed(changed_root, changed_identity)
    with pytest.raises(
        release_v2.CorpusR6MatchupSourceReleaseCandidateAuthorityV2Error,
        match="candidate-authority reopened root binding differs",
    ):
        release_v2.reopen_matchup_source_release_candidate_authority_ordinal_v2(
            release_identity=changed_identity,
            source_task_ordinal=ordinal,
            repository_root=Path("."),
            read_exact=store.read,
            git_head=lambda root_path: "a" * 40,
            git_blob=lambda root_path, commit, path: b"unreachable",
            git_status=lambda root_path, paths: b"",
        )


def test_late_source_deep_failure_prevents_v2_root_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, _, _, component_result = _build_fixture(monkeypatch)
    store = base_test._Store()
    store.seed(
        fixture["producer_release"], fixture["producer_release_identity"]
    )
    attempted: list[int] = []

    def deep_reopen(**values: object) -> dict[str, object]:
        ordinal = int(values["ordinal"])
        attempted.append(ordinal)
        if ordinal == source.TASK_COUNT - 1:
            raise release_v1.CorpusR6MatchupSourceReleaseV1Error(
                "late deep dependency differs"
            )
        return {}

    monkeypatch.setattr(
        release_v1,
        "_reopen_validated_matchup_source_release_ordinal_v1",
        deep_reopen,
    )
    callbacks = _callbacks()
    callbacks["read_exact"] = store.read
    with pytest.raises(
        release_v2.CorpusR6MatchupSourceReleaseCandidateAuthorityV2Error,
        match="late deep dependency differs",
    ):
        release_v2.publish_matchup_source_release_candidate_authority_root_last_v2(
            component_publication_candidate_authority_result=component_result,
            **callbacks,
            **_source_fixture(fixture),
            publish_create_once=store.publish,
        )
    assert attempted == list(range(source.TASK_COUNT))
    assert all(event[0] != "publish" for event in store.events)


def test_component_authority_failure_prevents_v2_root_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, _, _, component_result = _build_fixture(monkeypatch)
    store = base_test._Store()

    def reject_component(*_args: object, **_kwargs: object) -> object:
        raise (
            release_v2.component_publication_v2.
            CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error(
                "nested materialized leaf bytes differ"
            )
        )

    monkeypatch.setattr(
        release_v2.component_publication_v2,
        "validate_component_publication_against_candidate_authority_v2",
        reject_component,
    )
    with pytest.raises(
        release_v2.CorpusR6MatchupSourceReleaseCandidateAuthorityV2Error,
        match="nested materialized leaf bytes differ",
    ):
        release_v2.publish_matchup_source_release_candidate_authority_root_last_v2(
            component_publication_candidate_authority_result=component_result,
            **_callbacks(),
            **_source_fixture(fixture),
            publish_create_once=store.publish,
        )
    assert all(event[0] != "publish" for event in store.events)
