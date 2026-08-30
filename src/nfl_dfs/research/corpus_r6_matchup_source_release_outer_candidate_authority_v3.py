"""Terminal R6 matchup release rooted in the complete v3 authority chain.

The v1 terminal release authenticates the producer and every selected source
member, but its candidate predecessor is the accepted-release identity carried
by the producer.  This successor removes the remaining population- and
source-substitution seams.  Its public APIs accept only the complete v3
component-publication result plus its exact seven-pack predecessor.  They invoke
that result's hardened exact validator, which full-reopens the generation-
pinned fixed-G0 candidate root plus every component predecessor and output;
then they derive the producer solely from its validated offline panel,
cross-bind all 54 candidate artifacts to the source members, deep-replay all
54 v1 source members, and only then create the one v3 terminal root.

The ordinal reopener generation-exact reopens every component materialized
object, repeats candidate and seven-pack predecessor replay, and returns a
flattened v3 root/member plus the validated v1 mechanics objects.  It owns no
cloud client, outcome reader, scorer, graph mutation, deployment, or decision
authority.  Structure-only validation is never candidate authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
from typing import Final

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate_authority,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_outer_candidate_authority_v3
    as component_publication_v3,
)
from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as release_v1
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


MATCHUP_SOURCE_RELEASE_OUTER_CANDIDATE_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-matchup-source-release/outer-candidate-authority-v3"
)
MATCHUP_SOURCE_MEMBER_OUTER_CANDIDATE_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-matchup-source-release-member/outer-candidate-authority-v3"
)
ROOT_FILENAME: Final = "matchup-source-release-outer-candidate-authority-v3.json"
TASK_COUNT: Final = source.TASK_COUNT

_MEMBER_ADDITIONAL_FIELDS: Final = frozenset({
    "candidate_authority_root_identity",
    "candidate_authority_root_sha256",
    "accepted_candidate_release_identity",
    "accepted_candidate_release_sha256",
    "candidate_artifact_sha256",
    "candidate_count",
    "ordered_candidate_ids_sha256",
    "candidate_root_full_predecessor_replay_verified",
    "selected_artifact_exact_reopened",
    "selected_artifact_matches_source_member",
    "base_matchup_source_member_sha256",
})
_ROOT_ADDITIONAL_FIELDS: Final = frozenset({
    "candidate_authority_root_identity",
    "candidate_authority_root_sha256",
    "accepted_candidate_release_sha256",
    "candidate_root_full_predecessor_replay_verified",
    "all_candidate_artifacts_match_source_members",
    "candidate_authority_exact_reopen_required",
    "candidate_authority_structure_only_authority",
    "base_entry_manifest_sha256",
    "base_matchup_source_release_sha256",
    "capture_plan_v3_sha256",
    "component_publication_v3_receipt_sha256",
    "component_publication_v3_receipt",
    "upstream_source_release_sha256",
    "candidate_authority_v2_exact_reopened",
    "capture_plan_v3_exact_reopened",
    "component_publication_v3_exact_reopened",
    "seven_pack_source_authority_exact_reopened",
})
_CANDIDATE_BINDING_FIELDS: Final = frozenset({
    "candidate_authority_root_identity",
    "candidate_authority_root_sha256",
    "accepted_candidate_release_identity",
    "accepted_candidate_release_sha256",
    "candidate_artifact_identity",
    "candidate_artifact_sha256",
    "candidate_count",
    "ordered_candidate_ids_sha256",
    "candidate_root_full_predecessor_replay_verified",
    "selected_artifact_exact_reopened",
    "selected_artifact_matches_source_member",
})


class CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(ValueError):
    """The candidate-rooted terminal source release failed closed."""


ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
GitHead = candidate_authority.GitHead
GitBlob = candidate_authority.GitBlob
GitStatus = candidate_authority.GitStatus


def _fail(message: str) -> None:
    raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc


def _digest(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        _fail(f"{label} fields differ")


def _with_hash(
    value: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    if field in value:
        _fail(f"{field} must not be supplied before hashing")
    result = dict(value)
    result[field] = source.canonical_sha256(result)
    return result


def _validate_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label} self-hash")
    body = dict(value)
    del body[field]
    if source.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _parse_exact(
    identity: Mapping[str, object], *, read_exact: ReadExact, label: str,
) -> dict[str, object]:
    try:
        return release_v1._parse_exact(
            identity, read_exact=read_exact, label=label
        )
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc


def _reopen_all_component_materialized_objects_v3(
    component_receipt_value: Mapping[str, object],
    *,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Generation-exact reopen every component leaf named by the v1 receipt.

    The outer v3 receipt proves how the component publication was derived, but
    its embedded v1 materialized-object manifest is the byte authority for the
    producer leaves.  A later source-v3 reopen must touch every one of those
    generation-pinned identities; replaying only the plan and implementation
    measurements is not a deep component-publication reopen.
    """

    try:
        component_receipt = (
            component_publication_v3.
            validate_component_publication_outer_candidate_authority_receipt_v3(
                component_receipt_value
            )
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            f"component-publication v3 receipt replay failed: {exc}"
        ) from exc
    v1_receipt = _mapping(
        component_receipt.get("component_publication_receipt"),
        label="embedded component-publication v1 receipt",
    )
    identities = [
        _identity(value, label=f"component materialized object[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            v1_receipt.get("materialized_object_identities"),
            label="component materialized object identities",
        ))
    ]
    count = _exact_int(
        v1_receipt.get("materialized_object_count"),
        label="component materialized object count",
        minimum=1,
    )
    manifest_sha = _digest(
        v1_receipt.get("materialized_object_identity_manifest_sha256"),
        label="component materialized object identity manifest SHA",
    )
    producer_identity = _identity(
        v1_receipt.get("producer_release_identity"),
        label="component producer release",
    )
    if (
        count != len(identities)
        or source.canonical_sha256(identities) != manifest_sha
        or identities[-1] != producer_identity
        or len({str(identity["uri"]) for identity in identities}) != count
    ):
        _fail("component materialized object manifest differs")
    for ordinal, identity in enumerate(identities):
        label = f"component materialized object[{ordinal}]"
        try:
            raw = read_exact(identity)
        except Exception as exc:
            raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
                f"{label} exact reopen failed"
            ) from exc
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail(f"{label} exact content identity differs")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
                f"{label} must be canonical JSON"
            ) from exc
        if source.canonical_json_bytes(parsed) != raw:
            _fail(f"{label} canonical bytes differ")
    return {
        "materialized_object_count": count,
        "materialized_object_identity_manifest_sha256": manifest_sha,
        "all_component_materialized_objects_generation_exact_reopened": True,
        "all_component_materialized_object_bodies_canonical_json": True,
    }


def _capture_plan_file_binding(
    component_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Derive the exact tracked v3 plan-file binding used by source workers."""
    receipt = _mapping(
        component_receipt, label="component-publication v3 receipt"
    )
    plan = _mapping(receipt.get("capture_plan"), label="capture plan")
    plan_raw = source.canonical_json_bytes(plan) + b"\n"
    try:
        return release_v1._capture_plan_binding({
            "commit_sha": receipt.get("capture_plan_observed_commit_sha"),
            "relative_path": receipt.get("capture_plan_lock_relative_path"),
            "sha256": sha256(plan_raw).hexdigest(),
            "bytes": len(plan_raw),
            "capture_plan_sha256": receipt.get("capture_plan_sha256"),
        })
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            f"component capture-plan file binding differs: {exc}"
        ) from exc


def _reopen_candidate_authority(
    *,
    candidate_authority_root_identity: Mapping[str, object],
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> candidate_authority.ReopenedFixedG0CandidateAuthorityV2:
    try:
        return candidate_authority.reopen_fixed_g0_candidate_authority_release_v2(
            candidate_authority_root_identity,
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            f"candidate-authority full predecessor replay failed: {exc}"
        ) from exc


def _candidate_authority_binding(
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV2,
    *,
    expected_root_identity: Mapping[str, object],
) -> dict[str, object]:
    root = _mapping(reopened.root, label="candidate-authority root")
    root_identity = _identity(
        reopened.root_identity, label="reopened candidate-authority root"
    )
    expected_identity = _identity(
        expected_root_identity, label="expected candidate-authority root"
    )
    candidate_release = _mapping(
        reopened.candidate_release, label="reopened accepted candidate release"
    )
    candidate_release_identity = _identity(
        reopened.candidate_release_identity,
        label="reopened accepted candidate release",
    )
    root_sha = _digest(
        root.get("candidate_authority_release_sha256"),
        label="candidate-authority root SHA",
    )
    candidate_release_sha = _digest(
        candidate_release.get("accepted_candidate_release_sha256"),
        label="accepted candidate release SHA",
    )
    if (
        root_identity != expected_identity
        or root.get("target_uri") != root_identity["uri"]
        or root.get("candidate_release_identity")
        != candidate_release_identity
        or root.get("candidate_release_sha256") != candidate_release_sha
        or root.get("candidate_population_authority") is not True
        or root.get("exact_occurrence_provenance_authority") is not True
        or root.get("authoritative_reopen_required") is not True
        or root.get("structure_only_validation_authority") is not False
        or root.get("complete") is not True
    ):
        _fail("candidate-authority reopened root binding differs")
    entries = _sequence(
        candidate_release.get("entries"), label="accepted candidate entries"
    )
    if (
        len(entries) != TASK_COUNT
        or candidate_release.get("task_count") != TASK_COUNT
        or any(
            _mapping(entry, label=f"candidate entry[{ordinal}]").get(
                "source_task_ordinal"
            ) != ordinal
            for ordinal, entry in enumerate(entries)
        )
    ):
        _fail("candidate-authority release differs from fixed 54-entry order")
    return {
        "candidate_authority_root_identity": root_identity,
        "candidate_authority_root_sha256": root_sha,
        "accepted_candidate_release_identity": candidate_release_identity,
        "accepted_candidate_release_sha256": candidate_release_sha,
        "catalog_replay_receipt_identity": _identity(
            root.get("catalog_replay_receipt_identity"),
            label="candidate-authority catalog replay receipt",
        ),
        "catalog_replay_receipt_sha256": _digest(
            root.get("catalog_replay_receipt_sha256"),
            label="candidate-authority catalog replay receipt SHA",
        ),
        "entries": entries,
    }


def _project_member_v1(value: Mapping[str, object]) -> dict[str, object]:
    item = _mapping(value, label="candidate-rooted source member")
    body = {
        key: nested
        for key, nested in item.items()
        if key not in _MEMBER_ADDITIONAL_FIELDS
        and key
        not in {
            "schema_version",
            "matchup_source_member_candidate_authority_sha256",
        }
    }
    body.update({
        "schema_version": release_v1.MATCHUP_SOURCE_MEMBER_SCHEMA,
        "matchup_source_member_sha256": item[
            "base_matchup_source_member_sha256"
        ],
    })
    try:
        return release_v1._validate_member(
            body, expected_ordinal=int(item["source_task_ordinal"])
        )
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc


def _project_release_v1(value: Mapping[str, object]) -> dict[str, object]:
    item = _mapping(value, label="candidate-rooted source release")
    entries = [
        _project_member_v1(_mapping(entry, label="candidate-rooted member"))
        for entry in _sequence(item["entries"], label="candidate-rooted members")
    ]
    body = {
        key: nested
        for key, nested in item.items()
        if key not in _ROOT_ADDITIONAL_FIELDS
        and key
        not in {
            "schema_version",
            "entries",
            "entry_manifest_sha256",
            "matchup_source_release_candidate_authority_sha256",
        }
    }
    body.update({
        "schema_version": release_v1.MATCHUP_SOURCE_RELEASE_SCHEMA,
        "entries": entries,
        "entry_manifest_sha256": item["base_entry_manifest_sha256"],
        "matchup_source_release_sha256": item[
            "base_matchup_source_release_sha256"
        ],
    })
    try:
        return release_v1.validate_matchup_source_release_v1(body)
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc


def _build_member_v3(
    *,
    base_member: Mapping[str, object],
    candidate_entry: Mapping[str, object],
    binding: Mapping[str, object],
) -> dict[str, object]:
    base = _mapping(base_member, label="base source member")
    entry = _mapping(candidate_entry, label="candidate-authority entry")
    artifact = _mapping(
        entry.get("candidate_artifact"), label="candidate-authority artifact"
    )
    artifact_identity = _identity(
        entry.get("candidate_artifact_identity"),
        label="candidate-authority artifact identity",
    )
    artifact_sha = _digest(
        artifact.get("candidate_artifact_sha256"),
        label="candidate artifact SHA",
    )
    if (
        entry.get("source_task_ordinal") != base.get("source_task_ordinal")
        or entry.get("task_id") != base.get("task_id")
        or entry.get("slate") != base.get("slate")
        or entry.get("catalog_identity") != base.get("catalog_identity")
        or artifact_identity != base.get("candidate_artifact_identity")
        or artifact.get("source_task_ordinal")
        != base.get("source_task_ordinal")
        or entry.get("candidate_count") != artifact.get("candidate_count")
        or entry.get("ordered_candidate_ids_sha256")
        != artifact.get("ordered_candidate_ids_sha256")
    ):
        _fail("candidate-authority entry differs from source member")
    body = {
        key: nested
        for key, nested in base.items()
        if key not in {"schema_version", "matchup_source_member_sha256"}
    }
    body.update({
        "schema_version": MATCHUP_SOURCE_MEMBER_OUTER_CANDIDATE_AUTHORITY_SCHEMA,
        "candidate_authority_root_identity": binding[
            "candidate_authority_root_identity"
        ],
        "candidate_authority_root_sha256": binding[
            "candidate_authority_root_sha256"
        ],
        "accepted_candidate_release_identity": binding[
            "accepted_candidate_release_identity"
        ],
        "accepted_candidate_release_sha256": binding[
            "accepted_candidate_release_sha256"
        ],
        "candidate_artifact_sha256": artifact_sha,
        "candidate_count": _exact_int(
            entry.get("candidate_count"), label="candidate count", minimum=1
        ),
        "ordered_candidate_ids_sha256": _digest(
            entry.get("ordered_candidate_ids_sha256"),
            label="ordered candidate IDs SHA",
        ),
        "candidate_root_full_predecessor_replay_verified": True,
        "selected_artifact_exact_reopened": True,
        "selected_artifact_matches_source_member": True,
        "base_matchup_source_member_sha256": base[
            "matchup_source_member_sha256"
        ],
    })
    return _with_hash(
        body, field="matchup_source_member_candidate_authority_sha256"
    )


def _build_release_v3(
    *,
    base_release: Mapping[str, object],
    binding: Mapping[str, object],
) -> dict[str, object]:
    base = release_v1.validate_matchup_source_release_v1(base_release)
    if base["accepted_candidate_release_identity"] != binding[
        "accepted_candidate_release_identity"
    ]:
        _fail("base source release differs from candidate-authority release")
    candidate_entries = _sequence(
        binding["entries"], label="candidate-authority entries"
    )
    members = [
        _build_member_v3(
            base_member=base["entries"][ordinal],
            candidate_entry=candidate_entries[ordinal],
            binding=binding,
        )
        for ordinal in range(TASK_COUNT)
    ]
    body = {
        key: nested
        for key, nested in base.items()
        if key
        not in {
            "schema_version",
            "entries",
            "entry_manifest_sha256",
            "matchup_source_release_sha256",
        }
    }
    body.update({
        "schema_version": MATCHUP_SOURCE_RELEASE_OUTER_CANDIDATE_AUTHORITY_SCHEMA,
        "candidate_authority_root_identity": binding[
            "candidate_authority_root_identity"
        ],
        "candidate_authority_root_sha256": binding[
            "candidate_authority_root_sha256"
        ],
        "accepted_candidate_release_sha256": binding[
            "accepted_candidate_release_sha256"
        ],
        "candidate_root_full_predecessor_replay_verified": True,
        "all_candidate_artifacts_match_source_members": True,
        "candidate_authority_exact_reopen_required": True,
        "candidate_authority_structure_only_authority": False,
        "task_count": TASK_COUNT,
        "entries": members,
        "entry_manifest_sha256": source.canonical_sha256(members),
        "base_entry_manifest_sha256": base["entry_manifest_sha256"],
        "base_matchup_source_release_sha256": base[
            "matchup_source_release_sha256"
        ],
        "capture_plan_v3_sha256": binding["capture_plan_v3_sha256"],
        "component_publication_v3_receipt_sha256": binding[
            "component_publication_v3_receipt_sha256"
        ],
        "component_publication_v3_receipt": binding[
            "component_publication_v3_receipt"
        ],
        "upstream_source_release_sha256": binding[
            "upstream_source_release_sha256"
        ],
        "candidate_authority_v2_exact_reopened": True,
        "capture_plan_v3_exact_reopened": True,
        "component_publication_v3_exact_reopened": True,
        "seven_pack_source_authority_exact_reopened": True,
    })
    return _with_hash(
        body, field="matchup_source_release_candidate_authority_sha256"
    )


def _validated_component_authority(
    *,
    component_publication_candidate_authority_result: Mapping[str, object],
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    try:
        validated = (
            component_publication_v3.
            validate_component_publication_against_outer_candidate_authority_v3(
                component_publication_candidate_authority_result,
                repository_root=repository_root,
                read_exact=read_exact,
                git_head=git_head,
                git_blob=git_blob,
                git_status=git_status,
                upstream_source_release=upstream_source_release,
                upstream_source_release_identity=upstream_source_release_identity,
                upstream_pack_row_objects=upstream_pack_row_objects,
            )
        )
    except (
        component_publication_v3.
        CorpusR6MatchupComponentPublicationOuterCandidateAuthorityV3Error
    ) as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    result = _mapping(
        validated, label="candidate-authority component publication result"
    )
    if set(result) != {"publication_receipt", "component_publication_result"}:
        _fail("candidate-authority component publication result fields differ")
    receipt = _mapping(
        result["publication_receipt"],
        label="candidate-authority component publication receipt",
    )
    component = _mapping(
        result["component_publication_result"],
        label="nested component publication result",
    )
    if set(component) != {"publication_receipt", "offline_panel"}:
        _fail("nested component publication result fields differ")
    panel = _mapping(component["offline_panel"], label="validated offline panel")
    candidate_release = _mapping(
        panel.get("accepted_candidate_release"),
        label="validated accepted candidate release",
    )
    candidate_release_identity = _identity(
        panel.get("accepted_candidate_release_identity"),
        label="validated accepted candidate release",
    )
    candidate_release_sha = _digest(
        candidate_release.get("accepted_candidate_release_sha256"),
        label="validated accepted candidate release SHA",
    )
    entries = _sequence(
        candidate_release.get("entries"),
        label="validated accepted candidate entries",
    )
    if (
        len(entries) != TASK_COUNT
        or candidate_release.get("task_count") != TASK_COUNT
        or any(
            _mapping(entry, label=f"candidate entry[{ordinal}]").get(
                "source_task_ordinal"
            ) != ordinal
            for ordinal, entry in enumerate(entries)
        )
        or receipt.get("accepted_candidate_release_identity")
        != candidate_release_identity
        or receipt.get("accepted_candidate_release_sha256")
        != candidate_release_sha
    ):
        _fail("validated component result differs from candidate release")
    binding = {
        "candidate_authority_root_identity": _identity(
            receipt.get("fixed_g0_candidate_authority_root_identity"),
            label="validated candidate-authority root",
        ),
        "candidate_authority_root_sha256": _digest(
            receipt.get("fixed_g0_candidate_authority_root_sha256"),
            label="validated candidate-authority root SHA",
        ),
        "accepted_candidate_release_identity": candidate_release_identity,
        "accepted_candidate_release_sha256": candidate_release_sha,
        "catalog_replay_receipt_identity": _identity(
            receipt.get("catalog_replay_receipt_identity"),
            label="validated catalog replay receipt",
        ),
        "catalog_replay_receipt_sha256": _digest(
            receipt.get("catalog_replay_receipt_sha256"),
            label="validated catalog replay receipt SHA",
        ),
        "catalog_release_identity": _identity(
            receipt.get("catalog_release_identity"),
            label="validated catalog release",
        ),
        "catalog_release_sha256": _digest(
            receipt.get("catalog_release_sha256"),
            label="validated catalog release SHA",
        ),
        "capture_plan_v3_sha256": _digest(
            receipt.get("capture_plan_sha256"),
            label="validated capture-plan v3 SHA",
        ),
        "component_publication_v3_receipt_sha256": _digest(
            receipt.get("outer_candidate_component_publication_receipt_sha256"),
            label="validated component-publication v3 receipt SHA",
        ),
        "component_publication_v3_receipt": receipt,
        "upstream_source_release_sha256": _digest(
            _mapping(receipt.get("capture_plan"), label="capture plan").get(
                "upstream_source_release_sha256"
            ),
            label="validated seven-pack source release SHA",
        ),
        "source_capture_plan_binding": _capture_plan_file_binding(receipt),
        "entries": entries,
    }
    producer_release = _mapping(
        panel.get("producer_release"), label="validated producer release"
    )
    producer_release_identity = _identity(
        panel.get("producer_release_identity"),
        label="validated producer release",
    )
    return (
        result,
        binding,
        producer_release,
        producer_release_identity,
        panel,
    )


def _build_with_component_authority(
    *,
    component_publication_candidate_authority_result: Mapping[str, object],
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    release_id: str,
    namespace: str,
    capture_plan_binding: Mapping[str, object],
    source_exports: Sequence[Mapping[str, object]],
    source_export_identities: Sequence[Mapping[str, object]],
    capture_receipts: Sequence[Mapping[str, object]],
    capture_receipt_identities: Sequence[Mapping[str, object]],
    operator_results: Sequence[Mapping[str, object]],
    operator_result_identities: Sequence[Mapping[str, object]],
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    (
        _,
        binding,
        producer_release,
        producer_release_identity,
        _,
    ) = _validated_component_authority(
        component_publication_candidate_authority_result=(
            component_publication_candidate_authority_result
        ),
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
    )
    if release_v1._capture_plan_binding(capture_plan_binding) != binding[
        "source_capture_plan_binding"
    ]:
        _fail("caller capture-plan binding differs from tracked capture-plan v3")
    base_release = release_v1.build_matchup_source_release_v1(
        release_id=release_id,
        namespace=namespace,
        capture_plan_binding=capture_plan_binding,
        producer_release=producer_release,
        producer_release_identity=producer_release_identity,
        source_exports=source_exports,
        source_export_identities=source_export_identities,
        capture_receipts=capture_receipts,
        capture_receipt_identities=capture_receipt_identities,
        operator_results=operator_results,
        operator_result_identities=operator_result_identities,
    )
    producer = release_v1._producer_release_shape(
        producer_release, identity=producer_release_identity
    )
    if (
        producer.get("accepted_candidate_release_identity")
        != binding["accepted_candidate_release_identity"]
        or producer.get("catalog_replay_receipt_identity")
        != binding["catalog_replay_receipt_identity"]
        or producer.get("catalog_release_identity")
        != binding["catalog_release_identity"]
    ):
        _fail("producer release differs from candidate-authority predecessors")
    root = _build_release_v3(base_release=base_release, binding=binding)
    return root, base_release, producer, producer_release_identity


def build_matchup_source_release_outer_candidate_authority_v3(
    *,
    component_publication_candidate_authority_result: Mapping[str, object],
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    release_id: str,
    namespace: str,
    capture_plan_binding: Mapping[str, object],
    source_exports: Sequence[Mapping[str, object]],
    source_export_identities: Sequence[Mapping[str, object]],
    capture_receipts: Sequence[Mapping[str, object]],
    capture_receipt_identities: Sequence[Mapping[str, object]],
    operator_results: Sequence[Mapping[str, object]],
    operator_result_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build v3 only from the exact-validated full v3 component result."""
    root, _, _, _ = _build_with_component_authority(
        component_publication_candidate_authority_result=(
            component_publication_candidate_authority_result
        ),
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
        release_id=release_id,
        namespace=namespace,
        capture_plan_binding=capture_plan_binding,
        source_exports=source_exports,
        source_export_identities=source_export_identities,
        capture_receipts=capture_receipts,
        capture_receipt_identities=capture_receipt_identities,
        operator_results=operator_results,
        operator_result_identities=operator_result_identities,
    )
    return validate_matchup_source_release_outer_candidate_authority_v3(root)


def _validate_member_v3(
    value: object, *, expected_ordinal: int,
) -> dict[str, object]:
    item = _mapping(value, label=f"candidate-rooted member[{expected_ordinal}]")
    base = _project_member_v1(item)
    expected_fields = frozenset({
        *(
            key
            for key in base
            if key not in {"schema_version", "matchup_source_member_sha256"}
        ),
        "schema_version",
        *_MEMBER_ADDITIONAL_FIELDS,
        "matchup_source_member_candidate_authority_sha256",
    })
    _exact_keys(item, expected_fields, label="candidate-rooted source member")
    _validate_hash(
        item,
        field="matchup_source_member_candidate_authority_sha256",
        label="candidate-rooted source member",
    )
    normalized = dict(item)
    normalized.update({
        "candidate_authority_root_identity": _identity(
            item["candidate_authority_root_identity"],
            label="member candidate-authority root",
        ),
        "candidate_authority_root_sha256": _digest(
            item["candidate_authority_root_sha256"],
            label="member candidate-authority root SHA",
        ),
        "accepted_candidate_release_identity": _identity(
            item["accepted_candidate_release_identity"],
            label="member accepted candidate release",
        ),
        "accepted_candidate_release_sha256": _digest(
            item["accepted_candidate_release_sha256"],
            label="member accepted candidate release SHA",
        ),
        "candidate_artifact_sha256": _digest(
            item["candidate_artifact_sha256"],
            label="member candidate artifact SHA",
        ),
        "candidate_count": _exact_int(
            item["candidate_count"], label="member candidate count", minimum=1
        ),
        "ordered_candidate_ids_sha256": _digest(
            item["ordered_candidate_ids_sha256"],
            label="member ordered candidate IDs SHA",
        ),
        "base_matchup_source_member_sha256": _digest(
            item["base_matchup_source_member_sha256"],
            label="base source member SHA",
        ),
    })
    if (
        item["schema_version"]
        != MATCHUP_SOURCE_MEMBER_OUTER_CANDIDATE_AUTHORITY_SCHEMA
        or base["source_task_ordinal"] != expected_ordinal
        or item["candidate_artifact_identity"]
        != base["candidate_artifact_identity"]
        or item["base_matchup_source_member_sha256"]
        != base["matchup_source_member_sha256"]
        or any(
            item[field] is not True
            for field in (
                "candidate_root_full_predecessor_replay_verified",
                "selected_artifact_exact_reopened",
                "selected_artifact_matches_source_member",
            )
        )
        or source.canonical_json_bytes(normalized)
        != source.canonical_json_bytes(item)
    ):
        _fail("candidate-rooted source member fixed binding differs")
    return normalized


def validate_matchup_source_release_outer_candidate_authority_v3(
    value: object,
) -> dict[str, object]:
    """Validate v3 structure; exact candidate authority still must reopen."""
    item = _mapping(value, label="candidate-rooted source release")
    if (
        item.get("schema_version")
        != MATCHUP_SOURCE_RELEASE_OUTER_CANDIDATE_AUTHORITY_SCHEMA
    ):
        _fail("candidate-rooted source release schema differs")
    raw_entries = _sequence(item.get("entries"), label="candidate-rooted entries")
    if len(raw_entries) != TASK_COUNT:
        _fail("candidate-rooted source release requires exactly 54 entries")
    entries = [
        _validate_member_v3(entry, expected_ordinal=ordinal)
        for ordinal, entry in enumerate(raw_entries)
    ]
    base = _project_release_v1({**item, "entries": entries})
    expected_fields = frozenset({
        *(
            key
            for key in base
            if key
            not in {
                "schema_version",
                "entries",
                "entry_manifest_sha256",
                "matchup_source_release_sha256",
            }
        ),
        "schema_version",
        "entries",
        "entry_manifest_sha256",
        *_ROOT_ADDITIONAL_FIELDS,
        "matchup_source_release_candidate_authority_sha256",
    })
    _exact_keys(item, expected_fields, label="candidate-rooted source release")
    _validate_hash(
        item,
        field="matchup_source_release_candidate_authority_sha256",
        label="candidate-rooted source release",
    )
    root_identity = _identity(
        item["candidate_authority_root_identity"],
        label="source release candidate-authority root",
    )
    root_sha = _digest(
        item["candidate_authority_root_sha256"],
        label="source release candidate-authority root SHA",
    )
    accepted_identity = _identity(
        item["accepted_candidate_release_identity"],
        label="source release accepted candidate release",
    )
    accepted_sha = _digest(
        item["accepted_candidate_release_sha256"],
        label="source release accepted candidate release SHA",
    )
    try:
        component_receipt = (
            component_publication_v3.
            validate_component_publication_outer_candidate_authority_receipt_v3(
                item["component_publication_v3_receipt"]
            )
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            f"embedded component-publication v3 receipt differs: {exc}"
        ) from exc
    source_capture_plan_binding = _capture_plan_file_binding(component_receipt)
    normalized = dict(item)
    normalized.update({
        "candidate_authority_root_identity": root_identity,
        "candidate_authority_root_sha256": root_sha,
        "accepted_candidate_release_identity": accepted_identity,
        "accepted_candidate_release_sha256": accepted_sha,
        "base_entry_manifest_sha256": _digest(
            item["base_entry_manifest_sha256"],
            label="base entry manifest SHA",
        ),
        "base_matchup_source_release_sha256": _digest(
            item["base_matchup_source_release_sha256"],
            label="base source release SHA",
        ),
        "capture_plan_v3_sha256": _digest(
            item["capture_plan_v3_sha256"], label="capture-plan v3 SHA"
        ),
        "component_publication_v3_receipt_sha256": _digest(
            item["component_publication_v3_receipt_sha256"],
            label="component-publication v3 receipt SHA",
        ),
        "upstream_source_release_sha256": _digest(
            item["upstream_source_release_sha256"],
            label="seven-pack source release SHA",
        ),
        "component_publication_v3_receipt": component_receipt,
        "entries": entries,
    })
    if (
        item["schema_version"]
        != MATCHUP_SOURCE_RELEASE_OUTER_CANDIDATE_AUTHORITY_SCHEMA
        or item["task_count"] != TASK_COUNT
        or item["entry_manifest_sha256"] != source.canonical_sha256(entries)
        or item["base_entry_manifest_sha256"] != base["entry_manifest_sha256"]
        or item["base_matchup_source_release_sha256"]
        != base["matchup_source_release_sha256"]
        or base["accepted_candidate_release_identity"] != accepted_identity
        or item["component_publication_v3_receipt_sha256"]
        != component_receipt[
            "outer_candidate_component_publication_receipt_sha256"
        ]
        or item["capture_plan_v3_sha256"]
        != component_receipt["capture_plan_sha256"]
        or base["capture_plan_binding"] != source_capture_plan_binding
        or base["producer_release_identity"]
        != component_receipt["producer_release_identity"]
        or base["producer_release_sha256"]
        != component_receipt["producer_release_sha256"]
        or base["catalog_release_identity"]
        != component_receipt["catalog_release_identity"]
        or accepted_identity
        != component_receipt["accepted_candidate_release_identity"]
        or accepted_sha
        != component_receipt["accepted_candidate_release_sha256"]
        or base["upstream_source_release_identity"]
        != component_receipt["capture_plan"]["upstream_source_release_identity"]
        or item["upstream_source_release_sha256"]
        != component_receipt["capture_plan"]["upstream_source_release_sha256"]
        or root_identity
        != component_receipt["fixed_g0_candidate_authority_root_identity"]
        or root_sha
        != component_receipt["fixed_g0_candidate_authority_root_sha256"]
        or item["candidate_root_full_predecessor_replay_verified"] is not True
        or item["all_candidate_artifacts_match_source_members"] is not True
        or item["candidate_authority_exact_reopen_required"] is not True
        or item["candidate_authority_structure_only_authority"] is not False
        or any(
            item[field] is not True
            for field in (
                "candidate_authority_v2_exact_reopened",
                "capture_plan_v3_exact_reopened",
                "component_publication_v3_exact_reopened",
                "seven_pack_source_authority_exact_reopened",
            )
        )
        or any(
            member["candidate_authority_root_identity"] != root_identity
            or member["candidate_authority_root_sha256"] != root_sha
            or member["accepted_candidate_release_identity"]
            != accepted_identity
            or member["accepted_candidate_release_sha256"] != accepted_sha
            for member in entries
        )
        or source.canonical_json_bytes(normalized)
        != source.canonical_json_bytes(item)
    ):
        _fail("candidate-rooted source release fixed binding differs")
    return normalized


def publish_matchup_source_release_outer_candidate_authority_root_last_v3(
    *,
    component_publication_candidate_authority_result: Mapping[str, object],
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    release_id: str,
    namespace: str,
    capture_plan_binding: Mapping[str, object],
    source_exports: Sequence[Mapping[str, object]],
    source_export_identities: Sequence[Mapping[str, object]],
    capture_receipts: Sequence[Mapping[str, object]],
    capture_receipt_identities: Sequence[Mapping[str, object]],
    operator_results: Sequence[Mapping[str, object]],
    operator_result_identities: Sequence[Mapping[str, object]],
    publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Full-replay candidate and source graphs, then create only the v3 root."""
    (
        root,
        base_release,
        producer_release,
        producer_release_identity,
    ) = _build_with_component_authority(
        component_publication_candidate_authority_result=(
            component_publication_candidate_authority_result
        ),
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
        release_id=release_id,
        namespace=namespace,
        capture_plan_binding=capture_plan_binding,
        source_exports=source_exports,
        source_export_identities=source_export_identities,
        capture_receipts=capture_receipts,
        capture_receipt_identities=capture_receipt_identities,
        operator_results=operator_results,
        operator_result_identities=operator_result_identities,
    )
    root = validate_matchup_source_release_outer_candidate_authority_v3(root)
    producer_reopened = release_v1._producer_release_shape(
        _parse_exact(
            producer_release_identity,
            read_exact=read_exact,
            label="component producer release",
        ),
        identity=producer_release_identity,
    )
    if source.canonical_json_bytes(producer_reopened) != (
        source.canonical_json_bytes(producer_release)
    ):
        _fail("component producer release exact-reopened bytes differ")
    try:
        for ordinal in range(TASK_COUNT):
            release_v1._reopen_validated_matchup_source_release_ordinal_v1(
                release=base_release,
                ordinal=ordinal,
                read_exact=read_exact,
                producer_release=producer_reopened,
            )
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    root_raw = source.canonical_json_bytes(root)
    root_uri = f"{root['namespace']}{ROOT_FILENAME}"
    try:
        root_identity = _identity(
            publish_create_once(root_uri, root_raw),
            label="published candidate-rooted source release",
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            "candidate-rooted source release publication failed"
        ) from exc
    if root_identity["uri"] != root_uri:
        _fail("published candidate-rooted source release URI differs")
    reopened_root = validate_matchup_source_release_outer_candidate_authority_v3(
        _parse_exact(
            root_identity,
            read_exact=read_exact,
            label="published candidate-rooted source release",
        )
    )
    if reopened_root != root:
        _fail("published candidate-rooted source release exact replay differs")
    return {"release": root, "release_identity": root_identity}


def _selected_candidate_binding(
    *,
    root: Mapping[str, object],
    member: Mapping[str, object],
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV2,
    ordinal: int,
    source_candidate_artifact: Mapping[str, object],
) -> dict[str, object]:
    candidate_release = _mapping(
        reopened.candidate_release, label="reopened accepted candidate release"
    )
    entry = _mapping(
        candidate_release["entries"][ordinal],
        label="selected candidate-authority entry",
    )
    artifact = _mapping(
        entry["candidate_artifact"], label="selected candidate-authority artifact"
    )
    artifact_identity = _identity(
        entry["candidate_artifact_identity"],
        label="selected candidate-authority artifact",
    )
    artifact_sha = _digest(
        artifact["candidate_artifact_sha256"],
        label="selected candidate artifact SHA",
    )
    if (
        entry["source_task_ordinal"] != ordinal
        or entry["task_id"] != member["task_id"]
        or entry["slate"] != member["slate"]
        or entry["catalog_identity"] != member["catalog_identity"]
        or artifact_identity != member["candidate_artifact_identity"]
        or artifact["source_task_ordinal"] != ordinal
        or artifact_sha != member["candidate_artifact_sha256"]
        or entry["candidate_count"] != member["candidate_count"]
        or entry["ordered_candidate_ids_sha256"]
        != member["ordered_candidate_ids_sha256"]
        or source.canonical_json_bytes(artifact)
        != source.canonical_json_bytes(source_candidate_artifact)
    ):
        _fail("selected candidate-authority artifact differs from source member")
    binding = {
        "candidate_authority_root_identity": root[
            "candidate_authority_root_identity"
        ],
        "candidate_authority_root_sha256": root[
            "candidate_authority_root_sha256"
        ],
        "accepted_candidate_release_identity": root[
            "accepted_candidate_release_identity"
        ],
        "accepted_candidate_release_sha256": root[
            "accepted_candidate_release_sha256"
        ],
        "candidate_artifact_identity": artifact_identity,
        "candidate_artifact_sha256": artifact_sha,
        "candidate_count": entry["candidate_count"],
        "ordered_candidate_ids_sha256": entry[
            "ordered_candidate_ids_sha256"
        ],
        "candidate_root_full_predecessor_replay_verified": True,
        "selected_artifact_exact_reopened": True,
        "selected_artifact_matches_source_member": True,
    }
    _exact_keys(
        binding, _CANDIDATE_BINDING_FIELDS, label="selected candidate binding"
    )
    return binding


def reopen_matchup_source_release_outer_candidate_authority_ordinal_v3(
    *,
    release_identity: Mapping[str, object],
    source_task_ordinal: int,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Reopen v3 by ordinal and replay component, candidate, and seven-pack."""
    ordinal = _exact_int(
        source_task_ordinal, label="source release ordinal"
    )
    if ordinal >= TASK_COUNT:
        _fail("source release ordinal must be in 0..53")
    normalized_release_identity = _identity(
        release_identity, label="candidate-rooted source release"
    )
    root = validate_matchup_source_release_outer_candidate_authority_v3(
        _parse_exact(
            normalized_release_identity,
            read_exact=read_exact,
            label="candidate-rooted source release",
        )
    )
    if normalized_release_identity["uri"] != f"{root['namespace']}{ROOT_FILENAME}":
        _fail("candidate-rooted source release URI differs from namespace")
    upstream_identity = _identity(
        root["upstream_source_release_identity"],
        label="seven-pack source release",
    )
    upstream_body = _parse_exact(
        upstream_identity,
        read_exact=read_exact,
        label="seven-pack source release",
    )
    raw_packs = _sequence(upstream_body.get("packs"), label="seven-pack entries")
    if len(raw_packs) != len(source.PACK_IDS):
        _fail("seven-pack source release does not contain exactly seven packs")
    pack_rows = [
        _parse_exact(
            _identity(
                _mapping(pack, label=f"seven-pack entry[{index}]").get(
                    "exact_rows_identity"
                ),
                label=f"seven-pack rows[{index}]",
            ),
            read_exact=read_exact,
            label=f"seven-pack rows[{index}]",
        )
        for index, pack in enumerate(raw_packs)
    ]
    try:
        upstream = source.validate_upstream_release_v1(
            upstream_body, pack_row_objects=pack_rows
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            f"seven-pack source authority replay failed: {exc}"
        ) from exc
    if upstream["upstream_release_sha256"] != root[
        "upstream_source_release_sha256"
    ]:
        _fail("seven-pack source release SHA differs from terminal binding")
    component_receipt = root["component_publication_v3_receipt"]
    _reopen_all_component_materialized_objects_v3(
        component_receipt, read_exact=read_exact
    )
    try:
        plan, _, adapter_raw = component_publication_v3._tracked_plan_and_adapter_lock(
            component_receipt["capture_plan"],
            repository_root=repository_root,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
            bound_plan_commit_sha=str(
                component_receipt["capture_plan_observed_commit_sha"]
            ),
        )
        component_publication_v3._deep_validate_plan(
            plan=plan,
            adapter_raw=adapter_raw,
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
            upstream_source_release=upstream,
            upstream_source_release_identity=upstream_identity,
            upstream_pack_row_objects=pack_rows,
        )
        implementation_commit, measurements = (
            component_publication_v3._measure_implementation(
                repository_root=repository_root,
                git_head=git_head,
                git_blob=git_blob,
                git_status=git_status,
                bound_commit_sha=str(
                    component_receipt[
                        "component_successor_implementation_commit_sha"
                    ]
                ),
            )
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            f"capture/component v3 predecessor replay failed: {exc}"
        ) from exc
    if (
        implementation_commit
        != component_receipt["component_successor_implementation_commit_sha"]
        or measurements
        != component_receipt["component_successor_implementation_measurements"]
    ):
        _fail("component-publication v3 implementation binding differs")
    reopened_candidate = _reopen_candidate_authority(
        candidate_authority_root_identity=root[
            "candidate_authority_root_identity"
        ],
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    candidate_binding = _candidate_authority_binding(
        reopened_candidate,
        expected_root_identity=root["candidate_authority_root_identity"],
    )
    if (
        candidate_binding["candidate_authority_root_sha256"]
        != root["candidate_authority_root_sha256"]
        or candidate_binding["accepted_candidate_release_identity"]
        != root["accepted_candidate_release_identity"]
        or candidate_binding["accepted_candidate_release_sha256"]
        != root["accepted_candidate_release_sha256"]
    ):
        _fail("candidate-rooted source release differs from exact authority root")
    base_release = _project_release_v1(root)
    try:
        deep = release_v1._reopen_validated_matchup_source_release_ordinal_v1(
            release=base_release,
            ordinal=ordinal,
            read_exact=read_exact,
        )
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    member = root["entries"][ordinal]
    selected_binding = _selected_candidate_binding(
        root=root,
        member=member,
        reopened=reopened_candidate,
        ordinal=ordinal,
        source_candidate_artifact=deep["candidate_artifact"],
    )
    return {
        "release_identity": normalized_release_identity,
        "release": root,
        "member": member,
        "producer_release": deep["producer_release"],
        "producer_release_entry": deep["producer_release_entry"],
        "structural_catalog": deep["structural_catalog"],
        "structural_players": deep["structural_players"],
        "candidate_artifact": deep["candidate_artifact"],
        "producer_receipt": deep["producer_receipt"],
        "input_bundle": deep["input_bundle"],
        "source_export": deep["source_export"],
        "capture_receipt": deep["capture_receipt"],
        "operator_result": deep["operator_result"],
        "annotation_rows": deep["annotation_rows"],
        "candidate_authority_binding": selected_binding,
    }


__all__ = [
    "CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error",
    "MATCHUP_SOURCE_MEMBER_OUTER_CANDIDATE_AUTHORITY_SCHEMA",
    "MATCHUP_SOURCE_RELEASE_OUTER_CANDIDATE_AUTHORITY_SCHEMA",
    "ROOT_FILENAME",
    "build_matchup_source_release_outer_candidate_authority_v3",
    "publish_matchup_source_release_outer_candidate_authority_root_last_v3",
    "reopen_matchup_source_release_outer_candidate_authority_ordinal_v3",
    "validate_matchup_source_release_outer_candidate_authority_v3",
]
