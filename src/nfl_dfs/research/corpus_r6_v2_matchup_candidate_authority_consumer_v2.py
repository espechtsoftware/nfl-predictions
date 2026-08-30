"""One-slate R6-v2 consumer for the candidate-rooted matchup source.

The only matchup/candidate source selector accepted by the public entry point
is a generation-pinned terminal outer-candidate-authority v3 source-release
root plus its ordinal.  The source-release v3 reopener derives and fully
replays the fixed-G0 candidate-authority-v2 root, exact-opens the selected
accepted-candidate artifact, and
replays the complete matchup-source lineage.  This consumer then proves that
the exact candidate and roster order in that artifact is the row order of the
reconstructed score matrix before running any retrieval law.

This module is offline-only.  It owns no cloud client, outcome reader, scorer,
publisher, graph mutation, promotion, or production decision, and every
downstream authority flag it emits is false.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_candidate_population_scored_union_v1 as candidate_union,
)
from nfl_dfs.research import (
    corpus_r6_matchup_source_release_outer_candidate_authority_v3 as source_release_v3,
)
from nfl_dfs.research import (
    corpus_r6_v2_matchup_source_release_consumer_v1 as mechanics,
)
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as execution_v1
from nfl_dfs.research import residual_world_columns as rw


RESULT_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-authority-consumer-result/v2"
)
AUTHORITATIVE_EXECUTION_MODE: Final = (
    "candidate-rooted-source-v3-authoritative-dose-one-slate-mechanics"
)
FIXTURE_EXECUTION_MODE: Final = (
    "candidate-rooted-source-v3-fixture-dose-one-slate-mechanics"
)
SOURCE_PROJECTION_SCHEMA: Final = (
    "corpus-r6-v2-matchup-candidate-authority-runner-projection/v2"
)
_REOPENED_FIELDS: Final = frozenset({
    "release_identity",
    "release",
    "member",
    "producer_release",
    "producer_release_entry",
    "structural_catalog",
    "structural_players",
    "candidate_artifact",
    "producer_receipt",
    "input_bundle",
    "source_export",
    "capture_receipt",
    "operator_result",
    "annotation_rows",
    "candidate_authority_binding",
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


class CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(ValueError):
    """The candidate-rooted source cannot be bound to the scored slate."""


def _fail(message: str) -> None:
    raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(str(exc)) from exc


def _sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _validated_candidate_binding(
    reopened: Mapping[str, object],
    *,
    scored_union_binding: Mapping[str, object],
) -> dict[str, object]:
    binding = _mapping(
        reopened.get("candidate_authority_binding"),
        label="candidate-authority binding",
    )
    if set(binding) != _CANDIDATE_BINDING_FIELDS:
        _fail("candidate-authority binding fields differ")
    normalized = dict(binding)
    for field, label in (
        ("candidate_authority_root_identity", "candidate-authority root"),
        ("accepted_candidate_release_identity", "accepted candidate release"),
        ("candidate_artifact_identity", "accepted candidate artifact"),
    ):
        normalized[field] = _identity(binding[field], label=label)
    for field, label in (
        ("candidate_authority_root_sha256", "candidate-authority root SHA"),
        ("accepted_candidate_release_sha256", "candidate release SHA"),
        ("candidate_artifact_sha256", "candidate artifact SHA"),
        ("ordered_candidate_ids_sha256", "ordered candidate IDs SHA"),
    ):
        normalized[field] = _sha(binding[field], label=label)
    if (
        type(binding.get("candidate_count")) is not int
        or int(binding["candidate_count"]) < 1
        or any(
            binding.get(field) is not True
            for field in (
                "candidate_root_full_predecessor_replay_verified",
                "selected_artifact_exact_reopened",
                "selected_artifact_matches_source_member",
            )
        )
    ):
        _fail("candidate-authority binding verification differs")

    release = _mapping(reopened.get("release"), label="candidate-rooted release")
    member = _mapping(reopened.get("member"), label="candidate-rooted member")
    artifact = _mapping(
        reopened.get("candidate_artifact"), label="accepted candidate artifact"
    )
    union = _mapping(
        scored_union_binding, label="candidate scored-union binding"
    )
    if (
        release.get("schema_version")
        != source_release_v3.MATCHUP_SOURCE_RELEASE_OUTER_CANDIDATE_AUTHORITY_SCHEMA
        or member.get("schema_version")
        != source_release_v3.MATCHUP_SOURCE_MEMBER_OUTER_CANDIDATE_AUTHORITY_SCHEMA
        or release.get("candidate_authority_root_identity")
        != normalized["candidate_authority_root_identity"]
        or member.get("candidate_authority_root_identity")
        != normalized["candidate_authority_root_identity"]
        or release.get("candidate_authority_root_sha256")
        != normalized["candidate_authority_root_sha256"]
        or member.get("candidate_authority_root_sha256")
        != normalized["candidate_authority_root_sha256"]
        or release.get("accepted_candidate_release_identity")
        != normalized["accepted_candidate_release_identity"]
        or member.get("accepted_candidate_release_identity")
        != normalized["accepted_candidate_release_identity"]
        or release.get("accepted_candidate_release_sha256")
        != normalized["accepted_candidate_release_sha256"]
        or member.get("accepted_candidate_release_sha256")
        != normalized["accepted_candidate_release_sha256"]
        or member.get("candidate_artifact_identity")
        != normalized["candidate_artifact_identity"]
        or member.get("candidate_artifact_sha256")
        != normalized["candidate_artifact_sha256"]
        or member.get("candidate_count") != normalized["candidate_count"]
        or member.get("ordered_candidate_ids_sha256")
        != normalized["ordered_candidate_ids_sha256"]
        or any(
            member.get(field) is not True
            for field in (
                "candidate_root_full_predecessor_replay_verified",
                "selected_artifact_exact_reopened",
                "selected_artifact_matches_source_member",
            )
        )
        or release.get("candidate_root_full_predecessor_replay_verified")
        is not True
        or artifact.get("candidate_artifact_sha256")
        != normalized["candidate_artifact_sha256"]
        or artifact.get("source_task_ordinal") != member.get("source_task_ordinal")
        or artifact.get("candidate_count") != normalized["candidate_count"]
        or artifact.get("ordered_candidate_ids_sha256")
        != normalized["ordered_candidate_ids_sha256"]
        or union.get("candidate_artifact_sha256")
        != normalized["candidate_artifact_sha256"]
        or union.get("candidate_count") != normalized["candidate_count"]
        or union.get("ordered_candidate_ids_sha256")
        != normalized["ordered_candidate_ids_sha256"]
    ):
        _fail("candidate authority differs from source member or scored union")
    if batch.canonical_json_bytes(normalized) != batch.canonical_json_bytes(binding):
        _fail("candidate-authority binding canonical replay differs")
    return normalized


def execute_r6_v2_matchup_candidate_authority_ordinal_v2(
    *,
    validated_panel_index: Mapping[str, object],
    panel_index_identity: Mapping[str, object],
    accepted_slate_membership: Mapping[str, object],
    task_acceptance_identity: Mapping[str, object],
    carrier_identity: Mapping[str, object],
    matchup_source_release_identity: Mapping[str, object],
    source_task_ordinal: int,
    repository_root: Path,
    read_exact: source_release_v3.ReadExact,
    git_head: source_release_v3.GitHead,
    git_blob: source_release_v3.GitBlob,
    git_status: source_release_v3.GitStatus,
    minimum_supported_players: int = 2,
    minimum_completeness: float = 0.5,
    admission_m: int = mechanics.runner.DEFAULT_ADMISSION_M,
    neutral_replicates: int = mechanics.runner.DEFAULT_NEUTRAL_REPLICATES,
    neutral_seed_root: str = "r6-v2-neutral-v1",
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Exact-open one candidate-rooted source ordinal and run all R6-v2 laws."""
    try:
        ordinal = mechanics._exact_ordinal(
            source_task_ordinal, label="source task ordinal"
        )
    except mechanics.CorpusR6V2MatchupSourceReleaseConsumerV1Error as exc:
        raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(str(exc)) from exc
    if (
        not isinstance(repository_root, Path)
        or not callable(read_exact)
        or not callable(git_head)
        or not callable(git_blob)
        or not callable(git_status)
    ):
        _fail("candidate-rooted exact repository/read contract differs")
    release_identity = _identity(
        matchup_source_release_identity,
        label="candidate-rooted matchup source release",
    )
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    if require_authoritative and (
        admission_m != mechanics.runner.DEFAULT_ADMISSION_M
        or worlds_per_block is not None
    ):
        _fail("authoritative source-v3 execution cannot override registered doses")
    try:
        accepted = execution_v1.reconstruct_one_accepted_v12_slate(
            validated_panel_index=validated_panel_index,
            panel_index_identity=panel_index_identity,
            accepted_slate_membership=accepted_slate_membership,
            task_acceptance_identity=task_acceptance_identity,
            carrier_identity=carrier_identity,
            read_exact=read_exact,
            require_authoritative=require_authoritative,
        )
    except execution_v1.CorpusR6V2OneSlateExecutionError as exc:
        raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(str(exc)) from exc
    try:
        accepted_task, accepted_catalog = mechanics._accepted_task_and_catalog(
            accepted
        )
    except mechanics.CorpusR6V2MatchupSourceReleaseConsumerV1Error as exc:
        raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(str(exc)) from exc
    reconstructed = accepted.reconstructed
    provenance = _mapping(
        reconstructed.provenance, label="accepted candidate provenance"
    )
    reconstruction_receipt = _mapping(
        reconstructed.reconstruction_receipt, label="reconstruction receipt"
    )
    provenance_slate = _mapping(
        provenance.get("slate"), label="accepted provenance slate"
    )
    expected_task = {
        **accepted_task,
        "season": provenance_slate.get("season"),
        "week": provenance_slate.get("week"),
    }
    if (
        accepted_task.get("source_task_ordinal") != ordinal
        or accepted_task.get("slate_id") != provenance_slate.get("slate_id")
        or accepted.slate_id != provenance_slate.get("slate_id")
    ):
        _fail("requested source ordinal differs from accepted panel membership")
    try:
        reopen_source_ordinal = (
            source_release_v3
            .reopen_matchup_source_release_outer_candidate_authority_ordinal_v3
        )
        reopened = reopen_source_ordinal(
            release_identity=release_identity,
            source_task_ordinal=ordinal,
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except (
        source_release_v3.CorpusR6MatchupSourceReleaseOuterCandidateAuthorityV3Error
    ) as exc:
        raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(str(exc)) from exc
    if set(reopened) != _REOPENED_FIELDS:
        _fail("candidate-rooted source reopener fields differ")
    try:
        mechanics._reject_outcome_carriers(
            reopened, label="candidate-rooted exact source reopen"
        )
    except mechanics.CorpusR6V2MatchupSourceReleaseConsumerV1Error as exc:
        raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(str(exc)) from exc
    try:
        projection = mechanics._source_projection_from_exact_reopen(
            reopened,
            expected_ordinal=ordinal,
            expected_task=expected_task,
            accepted_catalog=accepted_catalog,
            expected_release_schema=(
                source_release_v3.MATCHUP_SOURCE_RELEASE_OUTER_CANDIDATE_AUTHORITY_SCHEMA
            ),
            expected_reopened_fields=_REOPENED_FIELDS,
        )
    except mechanics.CorpusR6V2MatchupSourceReleaseConsumerV1Error as exc:
        raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(str(exc)) from exc
    if projection.source_release_identity != release_identity:
        _fail("candidate-rooted reopener returned a different root identity")
    try:
        scored_union_binding = (
            candidate_union.bind_authorized_candidate_artifact_to_scored_union_v1(
                candidate_artifact=reopened["candidate_artifact"],
                provenance=provenance,
                union_scores=reconstructed.union_scores,
                reconstruction_receipt=reconstruction_receipt,
            )
        )
    except candidate_union.CorpusR6CandidatePopulationScoredUnionV1Error as exc:
        raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(str(exc)) from exc
    candidate_binding = _validated_candidate_binding(
        reopened, scored_union_binding=scored_union_binding
    )
    try:
        summary = mechanics._build_matchup_summary(
            provenance=provenance,
            projection=projection,
            accepted_catalog=accepted_catalog,
            minimum_supported_players=minimum_supported_players,
            minimum_completeness=minimum_completeness,
        )
    except mechanics.CorpusR6V2MatchupSourceReleaseConsumerV1Error as exc:
        raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(str(exc)) from exc
    surface_inputs = {
        "provenance": provenance,
        "union_scores": reconstructed.union_scores,
        "reconstruction_receipt": reconstruction_receipt,
        "matchup_summary": summary,
        "admission_m": admission_m,
        "neutral_replicates": neutral_replicates,
        "neutral_seed_root": neutral_seed_root,
        "worlds_per_block": worlds_per_block,
        "require_authoritative": require_authoritative,
    }
    try:
        retained_surface = mechanics._build_retrieval_surface(**surface_inputs)
        surface = mechanics._validate_retrieval_surface(
            retained_surface, **surface_inputs
        )
    except mechanics.CorpusR6V2MatchupSourceReleaseConsumerV1Error as exc:
        raise CorpusR6V2MatchupCandidateAuthorityConsumerV2Error(str(exc)) from exc

    release = _mapping(reopened["release"], label="candidate-rooted release")
    member = _mapping(reopened["member"], label="candidate-rooted member")
    source_projection: dict[str, object] = {
        "schema_version": SOURCE_PROJECTION_SCHEMA,
        "source_task_ordinal": ordinal,
        "slate": projection.slate,
        "source_release_identity": projection.source_release_identity,
        "source_release_sha256": release[
            "matchup_source_release_candidate_authority_sha256"
        ],
        "source_member_sha256": member[
            "matchup_source_member_candidate_authority_sha256"
        ],
        "base_source_release_sha256": release[
            "base_matchup_source_release_sha256"
        ],
        "base_source_member_sha256": member[
            "base_matchup_source_member_sha256"
        ],
        "source_export_identity": projection.source_export_identity,
        "source_export_sha256": member["source_export_sha256"],
        "capture_receipt_identity": projection.capture_receipt_identity,
        "capture_receipt_sha256": member["capture_receipt_sha256"],
        "catalog_identity": projection.catalog_identity,
        "producer_receipt_identity": _identity(
            member["producer_receipt_identity"], label="producer receipt"
        ),
        "input_bundle_identity": _identity(
            member["input_bundle_identity"], label="component input bundle"
        ),
        "operator_result_identity": _identity(
            member["operator_result_identity"], label="source operator result"
        ),
        "operator_result_sha256": _sha(
            member["operator_result_sha256"], label="source operator result SHA"
        ),
        "candidate_authority_binding": candidate_binding,
        "candidate_population_scored_union_binding": scored_union_binding,
        "accepted_catalog_structural_sha256": batch.canonical_sha256(
            accepted_catalog
        ),
        "annotation_rows_sha256": reopened["source_export"][
            "annotation_rows_sha256"
        ],
        "matchup_evidence_class": mechanics.REQUIRED_SOURCE_EVIDENCE_CLASS,
        "uses_realized_outcomes": False,
    }
    source_projection["source_projection_sha256"] = batch.canonical_sha256(
        source_projection
    )
    body: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "execution_mode": (
            AUTHORITATIVE_EXECUTION_MODE
            if require_authoritative
            else FIXTURE_EXECUTION_MODE
        ),
        "slate_id": accepted.slate_id,
        "source_task_ordinal": ordinal,
        "panel_index_identity": accepted.panel_index_identity,
        "panel_index_sha256": accepted.panel_index_sha256,
        "accepted_slate_membership": accepted.accepted_slate_membership,
        "accepted_slate_membership_sha256": batch.canonical_sha256(
            accepted.accepted_slate_membership
        ),
        "accepted_task_binding": accepted_task,
        "accepted_task_binding_sha256": batch.canonical_sha256(accepted_task),
        "task_acceptance_identity": accepted.task_acceptance_identity,
        "carrier_identity": accepted.carrier_identity,
        "later_source_freeze_identity": accepted.later_source_freeze_identity,
        "world_artifact_identities": accepted.world_artifact_identities,
        "world_artifact_identity_set_sha256": batch.canonical_sha256(
            accepted.world_artifact_identities
        ),
        "matchup_source_projection": source_projection,
        "configuration": {
            "minimum_supported_players": minimum_supported_players,
            "minimum_completeness": float(minimum_completeness),
            "admission_m": admission_m,
            "neutral_replicates": neutral_replicates,
            "neutral_seed_root": neutral_seed_root,
            "worlds_per_block": (
                rw.WORLDS_PER_BLOCK if worlds_per_block is None else worlds_per_block
            ),
            "require_authoritative": require_authoritative,
        },
        "verification": {
            "candidate_rooted_source_release_exact_reopened": True,
            "source_member_selected_only_by_ordinal": True,
            "source_mechanics_predecessor_replay_verified": True,
            "candidate_root_full_predecessor_replay_verified": True,
            "selected_candidate_artifact_exact_reopened": True,
            "authorized_candidate_order_matches_scored_matrix_verified": True,
            "source_catalog_matches_accepted_v12_verified": True,
            "source_task_matches_accepted_v12_verified": True,
            "full_seven_law_fold_final_surface_canonical_replay_verified": True,
            "canonical_authoritative_dose_verified": require_authoritative,
        },
        "output_hashes": {
            "candidate_provenance_sha256": provenance[
                "candidate_provenance_sha256"
            ],
            "reconstruction_sha256": reconstruction_receipt[
                "reconstruction_sha256"
            ],
            "candidate_population_scored_union_binding_sha256": (
                scored_union_binding[
                    "candidate_population_scored_union_binding_sha256"
                ]
            ),
            "matchup_summary_sha256": summary["matchup_summary_sha256"],
            "retrieval_surface_sha256": surface["retrieval_surface_sha256"],
            "source_projection_sha256": source_projection[
                "source_projection_sha256"
            ],
        },
        "reconstruction_receipt": reconstruction_receipt,
        "matchup_summary": summary,
        "retrieval_surface": surface,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in mechanics._FALSE_AUTHORITY_FIELDS},
    }
    body["task_result_sha256"] = batch.canonical_sha256(body)
    return body


def validate_r6_v2_matchup_candidate_authority_ordinal_result_v2(
    value: Mapping[str, object],
    **inputs: object,
) -> dict[str, object]:
    """Reopen all roots and independently regenerate a retained result."""
    rebuilt = execute_r6_v2_matchup_candidate_authority_ordinal_v2(
        **inputs  # type: ignore[arg-type]
    )
    if batch.canonical_json_bytes(value) != batch.canonical_json_bytes(rebuilt):
        _fail("candidate-rooted one-slate consumer canonical replay differs")
    return rebuilt


__all__ = [
    "CorpusR6V2MatchupCandidateAuthorityConsumerV2Error",
    "RESULT_SCHEMA",
    "SOURCE_PROJECTION_SCHEMA",
    "execute_r6_v2_matchup_candidate_authority_ordinal_v2",
    "validate_r6_v2_matchup_candidate_authority_ordinal_result_v2",
]
