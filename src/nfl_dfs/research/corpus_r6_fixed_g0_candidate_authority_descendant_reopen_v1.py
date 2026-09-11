"""Deep-reopen the fixed-G0 candidate root from a durable descendant.

The published candidate-v2 root retained a catalog-recovery capability hash
whose input included the clean repository HEAD used during publication.  That
HEAD is operational context, not an immutable predecessor: resolving the same
unchanged lock chain at a later clean descendant therefore changes only that
hash and the enclosing candidate-binding self-hash.

This adapter accepts exactly that one representation drift.  It independently
resolves the catalog-recovery capability at both the candidate root's bound
implementation commit and the current clean durable descendant, proves their
lock/code projections identical, projects only the replay-HEAD capability
hash, and then performs the complete candidate-v2 predecessor replay.  It
does not expose publication, outcome, scoring, graph, or policy capability.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Final

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as release,
)
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as core_v1
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v2 as core
from nfl_dfs.research import corpus_r6_fixed_g0_catalog_recovery_v1 as recovery
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import (
    corpus_r6_player_catalog_fixed_g0_adapter_v1 as catalog_adapter,
)

ADAPTER_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_fixed_g0_candidate_authority_descendant_reopen_v1.py"
)


class CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(ValueError):
    """The descendant-safe exact reopener failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return deepcopy(dict(value))


def _capability_stable_projection(
    capability: recovery.PublicationCapabilityV1,
) -> dict[str, object]:
    """Return every capability-hash input except the replay-time HEAD."""

    validated = recovery.validate_resolved_authority_v1(capability)
    return {
        "implementation_commit_sha": validated.implementation_commit_sha,
        "implementation_measurements": [
            dict(row) for row in validated.implementation_measurements
        ],
        "review_lock_commit_sha": validated.review_lock_commit_sha,
        "review_lock_file": dict(validated.review_lock_file),
        "review_lock_internal_sha256": validated.review_lock_internal_sha256,
        "final_lock_commit_sha": validated.final_lock_commit_sha,
        "final_lock_file": dict(validated.final_lock_file),
        "final_lock_internal_sha256": validated.final_lock_internal_sha256,
        "review_lock_sha256": recovery.canonical_sha256(dict(validated.review_lock)),
        "final_lock_sha256": recovery.canonical_sha256(dict(validated.final_lock)),
    }


def _attempt_stable_projection(
    attempt: recovery.TrackedAttemptBindingV1,
    *,
    capability: recovery.PublicationCapabilityV1,
) -> dict[str, object]:
    """Return every tracked-attempt field except its replay-time HEAD."""

    validated = recovery.validate_tracked_attempt_binding_v1(
        attempt, capability=capability
    )
    return {
        "marker_commit_sha": validated.marker_commit_sha,
        "marker": dict(validated.marker),
        "marker_file": dict(validated.marker_file),
        "marker_internal_sha256": validated.marker_internal_sha256,
    }


def validate_replay_head_only_binding_drift_v1(
    *,
    retained_binding: Mapping[str, object],
    descendant_binding: Mapping[str, object],
    historical_capability_sha256: str,
    descendant_capability_sha256: str,
) -> dict[str, object]:
    """Prove a candidate binding differs only by replay-time capability SHA.

    The immutable retained binding is returned.  Both enclosing self-hashes
    are validated, and an exact projection is required; coherent drift in any
    other field is rejected even when the caller recomputes its self-hash.
    """

    retained = _mapping(retained_binding, label="retained candidate binding")
    descendant = _mapping(descendant_binding, label="descendant candidate binding")
    try:
        core._validate_hash(
            retained,
            field="candidate_implementation_binding_sha256",
            label="retained candidate binding",
        )
        core._validate_hash(
            descendant,
            field="candidate_implementation_binding_sha256",
            label="descendant candidate binding",
        )
        historical_sha = core._digest(
            historical_capability_sha256,
            label="historical recovery capability SHA",
        )
        descendant_sha = core._digest(
            descendant_capability_sha256,
            label="descendant recovery capability SHA",
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            str(exc)
        ) from exc
    retained_recovery = _mapping(
        retained.get("catalog_recovery_code_and_lock_binding"),
        label="retained recovery binding",
    )
    descendant_recovery = _mapping(
        descendant.get("catalog_recovery_code_and_lock_binding"),
        label="descendant recovery binding",
    )
    if (
        retained_recovery.get("capability_sha256") != historical_sha
        or descendant_recovery.get("capability_sha256") != descendant_sha
    ):
        _fail("candidate binding capability SHA differs from resolved authority")

    projected = deepcopy(retained)
    projected_recovery = _mapping(
        projected.get("catalog_recovery_code_and_lock_binding"),
        label="projected recovery binding",
    )
    projected_recovery["capability_sha256"] = descendant_sha
    projected["catalog_recovery_code_and_lock_binding"] = projected_recovery
    projected.pop("candidate_implementation_binding_sha256", None)
    projected["candidate_implementation_binding_sha256"] = source.canonical_sha256(
        projected
    )
    if projected != descendant:
        _fail("candidate binding drift exceeds replay-time capability SHA")
    return retained


def _resolve_replay_heads(
    *,
    repository_root: Path,
    bound_head: str,
) -> tuple[
    str,
    recovery.PublicationCapabilityV1,
    recovery.TrackedAttemptBindingV1,
    recovery.PublicationCapabilityV1,
    recovery.TrackedAttemptBindingV1,
]:
    """Resolve the same tracked recovery chain at original and current HEAD."""

    repository = catalog_adapter.SubprocessGitRepositoryV1(repository_root)
    try:
        current_head = repository.require_current_clean_head()
        recovery.require_git_ancestor_v1(
            repository,
            ancestor_commit_sha=bound_head,
            descendant_commit_sha=current_head,
            label="candidate-bound-head-to-current",
        )
        recovery.require_commit_reachable_from_remote_v1(
            repository, commit_sha=bound_head
        )
        recovery.require_commit_reachable_from_remote_v1(
            repository, commit_sha=current_head
        )
        historical_capability, historical_attempt = (
            recovery.resolve_tracked_attempt_binding_v1(
                repository=repository, current_head=bound_head
            )
        )
        descendant_capability, descendant_attempt = (
            recovery.resolve_tracked_attempt_binding_v1(
                repository=repository, current_head=current_head
            )
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate replay Git boundary differs: {exc}"
        ) from exc
    if (
        historical_capability.current_clean_commit_sha != bound_head
        or descendant_capability.current_clean_commit_sha != current_head
        or _capability_stable_projection(historical_capability)
        != _capability_stable_projection(descendant_capability)
        or _attempt_stable_projection(
            historical_attempt, capability=historical_capability
        )
        != _attempt_stable_projection(
            descendant_attempt, capability=descendant_capability
        )
    ):
        _fail("catalog recovery authority changed beyond its replay-time HEAD")
    return (
        current_head,
        historical_capability,
        historical_attempt,
        descendant_capability,
        descendant_attempt,
    )


def reopen_fixed_g0_candidate_authority_from_descendant_v1(
    root_identity: object,
    *,
    repository_root: Path,
    read_exact: core.ReadExact,
    git_head: core.GitHead,
    git_blob: core.GitBlob,
    git_status: core.GitStatus,
) -> release.ReopenedFixedG0CandidateAuthorityV2:
    """Deep-replay candidate-v2 while accepting only replay-HEAD hash drift."""

    retained_root_identity = release._identity(
        root_identity, label="candidate-authority v2 root identity"
    )
    prefix, run_id = release._prefix_from_root_identity(retained_root_identity)
    output_reader = release._scoped_reader(read_exact=read_exact, prefix=prefix)
    root_body, reopened_root_identity = release._exact_json(
        retained_root_identity,
        read_exact=output_reader,
        label="candidate-authority v2 terminal root",
    )
    if root_body.get("schema_version") != release.RELEASE_SCHEMA:
        _fail("candidate-authority legacy root schema rejected")
    try:
        root = release.validate_fixed_g0_candidate_authority_release_structure_v2(
            root_body
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate-authority v2 root structure differs: {exc}"
        ) from exc
    if root.get("target_uri") != reopened_root_identity["uri"]:
        _fail("candidate-authority v2 root outer identity differs")

    retained_binding = _mapping(
        root.get("catalog_recovery_candidate_binding"),
        label="retained candidate binding",
    )
    try:
        bound_head = core._commit(
            retained_binding.get("candidate_implementation_commit_sha"),
            label="candidate implementation bound head",
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            str(exc)
        ) from exc
    (
        current_head,
        historical_capability,
        _historical_attempt,
        descendant_capability,
        _descendant_attempt,
    ) = _resolve_replay_heads(repository_root=repository_root, bound_head=bound_head)
    try:
        callback_head = core._commit(
            git_head(repository_root), label="candidate callback current HEAD"
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate callback Git boundary differs: {exc}"
        ) from exc
    if callback_head != current_head:
        _fail("candidate callback and durable current HEAD differ")

    try:
        authority, descendant_binding = core._open_outer_and_binding(
            repository_root=repository_root,
            catalog_recovery_outer_identity=root["catalog_recovery_outer_identity"],
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
            candidate_implementation_commit_sha=bound_head,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate outer/code exact replay failed: {exc}"
        ) from exc
    validate_replay_head_only_binding_drift_v1(
        retained_binding=retained_binding,
        descendant_binding=descendant_binding,
        historical_capability_sha256=historical_capability.capability_sha256,
        descendant_capability_sha256=descendant_capability.capability_sha256,
    )

    candidate_release_body, candidate_release_identity = release._exact_json(
        root["candidate_release_identity"],
        read_exact=output_reader,
        label="accepted candidate release",
    )
    try:
        candidate_release = source.validate_accepted_candidate_release_v1(
            candidate_release_body
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"accepted candidate release differs: {exc}"
        ) from exc
    panel, panel_identity = release._exact_json(
        root["panel_derivation_identity"],
        read_exact=output_reader,
        label="outer-bound panel receipt",
    )
    artifacts: list[dict[str, object]] = []
    sidecars: list[dict[str, object]] = []
    receipts: list[dict[str, object]] = []
    artifact_identities: list[dict[str, object]] = []
    sidecar_identities: list[dict[str, object]] = []
    receipt_identities: list[dict[str, object]] = []
    for ordinal, raw_descriptor in enumerate(
        release._sequence(root["objects"], label="objects")
    ):
        descriptor = release._mapping(
            raw_descriptor, label=f"object descriptor[{ordinal}]"
        )
        artifact_body, artifact_identity = release._exact_json(
            descriptor["candidate_artifact_identity"],
            read_exact=output_reader,
            label=f"candidate artifact[{ordinal}]",
        )
        artifact = source.validate_accepted_candidate_artifact_v1(artifact_body)
        sidecar, sidecar_identity = release._exact_json(
            descriptor["lineage_sidecar_identity"],
            read_exact=output_reader,
            label=f"lineage sidecar[{ordinal}]",
        )
        receipt, receipt_identity = release._exact_json(
            descriptor["slate_derivation_identity"],
            read_exact=output_reader,
            label=f"outer-bound slate receipt[{ordinal}]",
        )
        expected_descriptor = release._object_descriptor(
            prefix=prefix,
            source_task_ordinal=ordinal,
            artifact=artifact,
            artifact_identity=artifact_identity,
            sidecar=sidecar,
            sidecar_identity=sidecar_identity,
            receipt=receipt,
            receipt_identity=receipt_identity,
        )
        if source.canonical_json_bytes(descriptor) != source.canonical_json_bytes(
            expected_descriptor
        ):
            _fail(f"object descriptor[{ordinal}] body binding differs")
        artifacts.append(artifact)
        sidecars.append(sidecar)
        receipts.append(receipt)
        artifact_identities.append(artifact_identity)
        sidecar_identities.append(sidecar_identity)
        receipt_identities.append(receipt_identity)

    bundle = release._assemble_bundle(
        candidate_release=candidate_release,
        artifacts=artifacts,
        sidecars=sidecars,
        receipts=receipts,
        panel=panel,
    )
    try:
        core._require_bundle_binding(bundle, expected_binding=retained_binding)
        guarded_reader, require_complete_catalog_replay = (
            core._outer_manifest_gated_reader(
                authority=authority, read_exact=read_exact
            )
        )
        projected_v1 = core._downgrade_bundle(bundle)
        validated_v1 = core_v1.validate_fixed_g0_candidate_authority_v1(
            projected_v1,
            repository_root=repository_root,
            catalog_replay_receipt_identity=(authority.inner_replay_receipt_identity),
            read_exact=guarded_reader,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
        require_complete_catalog_replay()
        validated_panel = core._mapping(
            validated_v1.get("panel_derivation_receipt"),
            label="validated v1 panel",
        )
        material_projection = {
            "slate_predecessor_bindings": [
                {"catalog_binding": receipt["catalog_binding"]}
                for receipt in core._sequence(
                    validated_v1.get("slate_derivation_receipts"),
                    label="validated v1 slate receipts",
                )
            ],
            "catalog_release_identity": validated_panel["catalog_release_identity"],
            "catalog_release_sha256": validated_panel["catalog_release_sha256"],
            "catalog_replay_receipt_identity": validated_panel[
                "catalog_replay_receipt_identity"
            ],
            "catalog_replay_receipt_sha256": validated_panel[
                "catalog_replay_receipt_sha256"
            ],
        }
        core._require_outer_manifest(authority=authority, material=material_projection)
        rebuilt_bundle = core._upgrade_bundle(validated_v1, binding=retained_binding)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate-authority v2 predecessor replay failed: {exc}"
        ) from exc
    if source.canonical_json_bytes(rebuilt_bundle) != source.canonical_json_bytes(
        bundle
    ):
        _fail("candidate-authority v2 bundle differs from predecessor replay")

    expected_root = release._build_root(
        prefix=prefix,
        run_id=run_id,
        bundle=rebuilt_bundle,
        candidate_release_identity=candidate_release_identity,
        panel_identity=panel_identity,
        artifact_identities=artifact_identities,
        sidecar_identities=sidecar_identities,
        receipt_identities=receipt_identities,
    )
    if source.canonical_json_bytes(root) != source.canonical_json_bytes(expected_root):
        _fail("candidate-authority v2 root predecessor replay differs")
    return release.ReopenedFixedG0CandidateAuthorityV2(
        root=root,
        root_identity=reopened_root_identity,
        authority_bundle=rebuilt_bundle,
        candidate_release=candidate_release,
        candidate_release_identity=candidate_release_identity,
    )


__all__ = [
    "ADAPTER_MODULE_PATH",
    "CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error",
    "reopen_fixed_g0_candidate_authority_from_descendant_v1",
    "validate_replay_head_only_binding_drift_v1",
]
