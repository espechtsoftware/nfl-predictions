"""Guarded production batch for the complete R6 matchup source-v3 chain.

This is a new authority boundary.  It does not alter or reinterpret the
historical source-v2 batch.  The only publication input exposed by the public
API is a run ID.  The fixed-G0 candidate-authority-v2 root is obtained from a
tracked capture-plan-v3 lock, and all remaining inputs are derived from that
lock or from generation-pinned identities carried by it.

The publication order is deliberately strict:

1. exact-replay the tracked candidate-v2/capture-v3 prerequisites;
2. materialize and deep-reopen the complete component-v3 result;
3. create and exact-reopen all 54 source triples;
4. build, publish, and deep-reopen the source-release-v3 root;
5. in the publishing process, perform one complete v3 predecessor replay,
   then generation-exact reopen all 54 source members under those same frozen
   identities; and
6. publish one batch-v3 terminal root as the final create-once request.

That in-process replay is not an independent-process receipt.  The public
write-disabled reopener can be launched later, while process separation and
runtime-image provenance must be attested by the external build/job gate.

All possible output URIs are enumerated before a write-capable transport is
constructed.  The transport is the bounded, generation-pinned, create-once
production transport from the reviewed v1 batch *mechanics*; no v1 batch
authority, root, capture-plan schema, or source-release schema is accepted.
The terminal root binds the clean dependency closure, loaded runtime and
immutable image identity so an exact-equal resume requires the same clean
source commit and image.

No API in this module accepts or reads outcomes, scores, selector results,
retrieval decisions, graph mutations, deployments, or production-policy
authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate_v2,
)
from nfl_dfs.research import (
    corpus_r6_matchup_batch_candidate_authority_v1 as batch_mechanics,
)
from nfl_dfs.research import (
    corpus_r6_matchup_capture_plan_outer_candidate_authority_v3 as capture_v3,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_outer_candidate_authority_v3
    as component_v3,
)
from nfl_dfs.research import corpus_r6_matchup_source_operator_v2 as operator_v2
from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as release_v1
from nfl_dfs.research import (
    corpus_r6_matchup_source_release_outer_candidate_authority_v3 as release_v3,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


BATCH_RELEASE_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch/outer-candidate-authority-v3"
)
DEPENDENCY_CLOSURE_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-dependency-closure/v3"
)
RUNTIME_BINDING_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-runtime-binding/v3"
)
OUTPUT_URI_INVENTORY_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-output-uri-inventory/v3"
)
READ_BUDGET_CONTRACT_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-read-budget-contract/v3"
)
WRITE_BUDGET_CONTRACT_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-write-budget-contract/v3"
)
PRETERMINAL_COMPLETION_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-preterminal-completion/v3"
)
PUBLICATION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-publication-receipt/v3"
)
TASK0_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-task0-readiness/v3"
)
PUBLICATION_MODE: Final = (
    "create_once_components_then_source_triples_then_source_v3_root_then_"
    "batch_v3_root"
)
CREATE_ONCE_RESUME_POLICY: Final = (
    "same_clean_source_commit_and_image_only;generation_exact_reopen_and_"
    "byte_equality;different_bytes_fail_closed;complete_graph_rebuilt_before_"
    "terminal_root"
)

OUTPUT_BUCKET: Final = "nfl-predictions-503414-corpus-source"
OUTPUT_NAMESPACE: Final = "research/corpus-r6-matchup-source-batches-v3"
ROOT_FILENAME: Final = (
    "matchup-source-batch-outer-candidate-authority-v3.json"
)
BATCH_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_matchup_source_batch_outer_candidate_authority_v3.py"
)
CLI_MODULE_PATH: Final = "scripts/run_corpus_r6_matchup_source_batch_v3.py"
PRODUCTION_PROJECT: Final = batch_mechanics.PRODUCTION_PROJECT
REPOSITORY_ROOT: Final = batch_mechanics.REPOSITORY_ROOT

PUBLISH_ENABLE_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_BATCH_V3_PUBLISH"
IMAGE_DIGEST_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_DIGEST"
IMAGE_REFERENCE_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_REFERENCE"
IMAGE_SOURCE_COMMIT_ENV: Final = (
    "CORPUS_R6_MATCHUP_SOURCE_V3_IMAGE_SOURCE_COMMIT"
)

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,80}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_ROOT_URI = re.compile(
    rf"^gs://{re.escape(OUTPUT_BUCKET)}/{re.escape(OUTPUT_NAMESPACE)}/"
    r"(?P<run_id>[a-z0-9][a-z0-9-]{7,80})/"
    rf"{re.escape(ROOT_FILENAME)}$"
)

# The legacy list is reused only as a reviewed inventory of mechanics reached
# by the shared component/source reducers.  V3-specific candidate, capture,
# component, release, batch, and CLI code is added explicitly.  The tuple is
# fixed and sorted: changing it is a reviewed runtime schema change.
EXECUTED_DEPENDENCY_MODULE_PATHS: Final = tuple(sorted(set((
    *batch_mechanics.EXECUTED_DEPENDENCY_MODULE_PATHS,
    "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_v2.py",
    (
        "src/nfl_dfs/research/"
        "corpus_r6_fixed_g0_candidate_authority_release_v2.py"
    ),
    (
        "src/nfl_dfs/research/"
        "corpus_r6_fixed_g0_catalog_recovery_downstream_v1.py"
    ),
    "src/nfl_dfs/research/corpus_r6_fixed_g0_catalog_recovery_v1.py",
    capture_v3.CAPTURE_PLAN_MODULE_PATH,
    component_v3.COMPONENT_PUBLICATION_MODULE_PATH,
    (
        "src/nfl_dfs/research/"
        "corpus_r6_matchup_source_release_outer_candidate_authority_v3.py"
    ),
    (
        "src/nfl_dfs/research/"
        "corpus_r6_matchup_source_task0_v3.py"
    ),
    "scripts/run_corpus_r6_matchup_source_task0_v3.py",
    BATCH_MODULE_PATH,
    CLI_MODULE_PATH,
))))

_RUNTIME_MODULE_PATHS: Final = {
    "batch_v3": BATCH_MODULE_PATH,
    "candidate_release_v2": (
        "src/nfl_dfs/research/"
        "corpus_r6_fixed_g0_candidate_authority_release_v2.py"
    ),
    "capture_plan_v3": capture_v3.CAPTURE_PLAN_MODULE_PATH,
    "component_publication_v3": component_v3.COMPONENT_PUBLICATION_MODULE_PATH,
    "leaf_operator_v2": operator_v2.OPERATOR_MODULE_PATH,
    "source_release_v3": (
        "src/nfl_dfs/research/"
        "corpus_r6_matchup_source_release_outer_candidate_authority_v3.py"
    ),
}


def _critical_loaded_callables_v3() -> tuple[tuple[object, str, str], ...]:
    current = importlib.import_module(__name__)
    task0_v3 = importlib.import_module(
        "nfl_dfs.research.corpus_r6_matchup_source_task0_v3"
    )
    return (
        *(
            (current, attribute, BATCH_MODULE_PATH)
            for attribute in (
                "_build_batch_root_v3",
                "_build_runtime_binding_v3",
                "_callable_owner_module_name_v3",
                "_commit",
                "_critical_loaded_callables_v3",
                "_deep_reopen_batch_v3",
                "_deep_validate_capture_plan_v3",
                "_digest",
                "_exact_validate_all_source_members_v3",
                "_fail",
                "_identity",
                "_mapping",
                "_module_origin",
                "_normalize_dependency_closure",
                "_normalize_output_uri_inventory_v3",
                "_normalize_preterminal_completion_v3",
                "_normalize_read_budget_contract_v3",
                "_normalize_read_budget_receipt_v3",
                "_normalize_runtime_binding",
                "_normalize_task0_authorization_v3",
                "_normalize_write_budget_contract_v3",
                "_normalize_write_budget_receipt_v3",
                "_operator_code_identity",
                "_output_uri_inventory_v3",
                "_parse_exact_json",
                "_policy",
                "_preterminal_completion_v3",
                "_preterminal_root_evidence_v3",
                "_publish_json",
                "_publish_source_triples_v3",
                "_read_budget_contract_v3",
                "_sequence",
                "_trusted_capture_plan_v3",
                "_trusted_dependency_closure_v3",
                "_trusted_remote_prerequisites_v3",
                "_validate_local_context_v3",
                "_write_budget_contract_v3",
                "canonical_json_bytes",
                "canonical_sha256",
                "output_prefix_for_run_v3",
                "publish_matchup_source_batch_outer_candidate_authority_v3",
                "reopen_matchup_source_batch_outer_candidate_authority_v3",
                "validate_batch_release_structure_v3",
                "validate_matchup_source_batch_outer_candidate_authority_v3",
                "validate_matchup_source_batch_task0_readiness_v3",
            )
        ),
        (
            task0_v3,
            "validate_full_publication_authorization_v3",
            "src/nfl_dfs/research/corpus_r6_matchup_source_task0_v3.py",
        ),
        *(
            (
                candidate_v2,
                attribute,
                _RUNTIME_MODULE_PATHS["candidate_release_v2"],
            )
            for attribute in (
                "_assemble_bundle",
                "_build_root",
                "_bundle_lists",
                "_digest",
                "_exact_json",
                "_exact_keys",
                "_fail",
                "_identity",
                "_integer",
                "_mapping",
                "_object_descriptor",
                "_parse_canonical_json",
                "_policy",
                "_prefix_from_root_identity",
                "_publication_manifest",
                "_publish_json",
                "_scoped_reader",
                "_self_hash",
                "_sequence",
                "_thaw",
                "_with_hash",
                "canonical_json_bytes",
                "canonical_sha256",
                "output_prefix_for_run_v2",
                "publish_fixed_g0_candidate_authority_release_v2",
                "reopen_fixed_g0_candidate_authority_release_v2",
                "validate_fixed_g0_candidate_authority_release_structure_v2",
            )
        ),
        *(
            (capture_v3, attribute, _RUNTIME_MODULE_PATHS["capture_plan_v3"])
            for attribute in (
                "_base_projection",
                "_candidate_binding",
                "_commit",
                "_derived_inner_bodies",
                "_digest",
                "_exact_json",
                "_fail",
                "_identity",
                "_mapping",
                "_measure_implementation",
                "_normalize_measurements",
                "_open_candidate",
                "_require_implementation_projection",
                "_runtime_path",
                "_sequence",
                "_upgrade",
                "_validated_candidate_recovery_binding",
                "_with_hash",
                "build_capture_plan_lock_v3",
                "canonical_json_bytes",
                "canonical_sha256",
                "reopen_capture_plan_lock_from_git_v3",
                "validate_capture_plan_against_prerequisites_v3",
                "validate_capture_plan_lock_v3",
            )
        ),
        *(
            (
                component_v3,
                attribute,
                _RUNTIME_MODULE_PATHS["component_publication_v3"],
            )
            for attribute in (
                "_build_receipt",
                "_commit",
                "_compatibility_binding",
                "_deep_validate_plan",
                "_derive_inner_inputs",
                "_digest",
                "_fail",
                "_identity",
                "_mapping",
                "_measure_implementation",
                "_normalize_measurements",
                "_open_candidate",
                "_policy",
                "_read_regular_nofollow",
                "_require_plan_candidate_equality",
                "_runtime_path",
                "_sequence",
                "_shallow_reopen_candidate_root_before_inner",
                "_tracked_plan_and_adapter_lock",
                "_validate_v1_result",
                "canonical_json_bytes",
                "canonical_sha256",
                "publish_all_54_component_release_outer_candidate_authority_v3",
                "validate_component_publication_against_outer_candidate_authority_v3",
                "validate_component_publication_outer_candidate_authority_receipt_v3",
            )
        ),
        *(
            (operator_v2, attribute, _RUNTIME_MODULE_PATHS["leaf_operator_v2"])
            for attribute in (
                "_exact_json",
                "_fail",
                "_identity",
                "_mapping",
                "_publish_json",
                "publish_matchup_source_triple_v2",
            )
        ),
        *(
            (release_v3, attribute, _RUNTIME_MODULE_PATHS["source_release_v3"])
            for attribute in (
                "_build_member_v3",
                "_build_release_v3",
                "_build_with_component_authority",
                "_candidate_authority_binding",
                "_capture_plan_file_binding",
                "_digest",
                "_exact_int",
                "_exact_keys",
                "_fail",
                "_identity",
                "_mapping",
                "_parse_exact",
                "_project_member_v1",
                "build_matchup_source_release_outer_candidate_authority_v3",
                "_project_release_v1",
                "_reopen_all_component_materialized_objects_v3",
                "_reopen_candidate_authority",
                "_selected_candidate_binding",
                "_sequence",
                "_validate_hash",
                "_validate_member_v3",
                "_validated_component_authority",
                "_with_hash",
                "publish_matchup_source_release_outer_candidate_authority_root_last_v3",
                "reopen_matchup_source_release_outer_candidate_authority_ordinal_v3",
                "validate_matchup_source_release_outer_candidate_authority_v3",
            )
        ),
        *(
            (
                release_v1,
                attribute,
                "src/nfl_dfs/research/corpus_r6_matchup_source_release_v1.py",
            )
            for attribute in (
                "_capture_plan_binding",
                "_parse_exact",
                "_producer_release_shape",
                "_reopen_validated_matchup_source_release_ordinal_v1",
                "_validate_member",
                "build_matchup_capture_receipt_v2",
                "build_matchup_operator_result_v2",
                "build_matchup_source_export_v2",
                "build_matchup_source_release_v1",
                "validate_matchup_source_release_v1",
            )
        ),
        *(
            (
                component_v3.publication_v1,
                attribute,
                (
                    "src/nfl_dfs/research/"
                    "corpus_r6_matchup_component_publication_v1.py"
                ),
            )
            for attribute in (
                "publish_all_54_component_release_v1",
                "validate_component_publication_receipt_v1",
            )
        ),
        *(
            (
                source,
                attribute,
                "src/nfl_dfs/research/corpus_r6_matchup_source_v2.py",
            )
            for attribute in (
                "canonical_json_bytes",
                "canonical_sha256",
                "frozen_role_registry_v2",
                "normalize_code_identity_v2",
                "normalize_object_identity_v2",
                "validate_accepted_candidate_release_v1",
                "validate_upstream_release_v1",
            )
        ),
        *(
            (
                batch_mechanics,
                attribute,
                (
                    "src/nfl_dfs/research/"
                    "corpus_r6_matchup_batch_candidate_authority_v1.py"
                ),
            )
            for attribute in (
                "_code_object_fingerprint_v1",
                "_compiled_callable_code_sha256_v1",
                "_gcs_parts_v1",
                "_gcs_not_found_v1",
                "_identity",
                "_normalize_publication_work_receipt_v1",
                "_run_trusted_git_v1",
                "_secure_read_repository_file_v1",
                "_trusted_gcs_transport_v1",
                "_trusted_git_blob_v1",
                "_trusted_git_head_v1",
                "_trusted_git_status_v1",
                "_trusted_remote_prerequisites_v1",
                "_trusted_repository_root_v1",
                "canonical_sha256",
            )
        ),
        *(
            (
                batch_mechanics.GenerationPinnedGCSBatchTransportV1,
                attribute,
                (
                    "src/nfl_dfs/research/"
                    "corpus_r6_matchup_batch_candidate_authority_v1.py"
                ),
            )
            for attribute in (
                "__init__",
                "_reserve_payload_read_v1",
                "_reserve_write_attempt_v1",
                "_resolve_current_v1",
                "publish_create_once",
                "read_budget_receipt",
                "read_exact",
                "require_completed_exactly_v1",
                "write_budget_receipt",
            )
        ),
        *(
            (
                batch_mechanics.ExactReadCacheV1,
                attribute,
                (
                    "src/nfl_dfs/research/"
                    "corpus_r6_matchup_batch_candidate_authority_v1.py"
                ),
            )
            for attribute in (
                "__post_init__",
                "budget_receipt",
                "read",
            )
        ),
    )


class CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(ValueError):
    """The guarded source-v3 batch failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return source.canonical_json_bytes(value)
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _callable_owner_module_name_v3(owner: object) -> str:
    """Return the defining module for a module- or class-owned callable."""

    module_name = getattr(owner, "__module__", None)
    if type(module_name) is str:
        return module_name
    module_name = getattr(owner, "__name__", None)
    if type(module_name) is not str:
        _fail("source-v3 critical callable owner has no module name")
    return module_name


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _commit(value: object, *, label: str) -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 40-hex")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "world_matrix_bodies_read": False,
        # Candidate-v2 deliberately replays the inherited 54 world-schedule
        # bodies and 378 accepted arm-result bodies to reconstruct the exact
        # score-free population.  Do not mislabel those provenance reads as
        # absent merely because realized outcomes remain closed.
        "world_schedule_bodies_read": True,
        "accepted_arm_result_object_bodies_read": True,
        "accepted_task_result_and_carrier_bodies_reopened": True,
        "historical_grader_outcome_sources_read": False,
        "warehouse_outcome_sources_read": False,
        "scores_read": False,
        "score_columns_read": [],
        "promotion_eligible": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def output_prefix_for_run_v3(run_id: object) -> str:
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("source-v3 batch run ID must be 8..81 lowercase letters/digits/hyphens")
    return f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{run_id}/"


def _normalize_dependency_closure(value: object) -> dict[str, object]:
    item = _mapping(value, label="source-v3 dependency closure")
    fields = {
        "schema_version",
        "source_commit_sha",
        "module_paths",
        "module_code_identities",
        "module_code_identity_manifest_sha256",
        "repository_status_clean",
        "all_head_blobs_match_current_nofollow_bytes",
        "dependency_closure_sha256",
    }
    if set(item) != fields:
        _fail("source-v3 dependency closure fields differ")
    retained = _digest(
        item.get("dependency_closure_sha256"), label="dependency closure hash"
    )
    unhashed = dict(item)
    del unhashed["dependency_closure_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("source-v3 dependency closure self-hash differs")
    commit = _commit(item.get("source_commit_sha"), label="dependency commit")
    paths = _sequence(item.get("module_paths"), label="dependency paths")
    if paths != list(EXECUTED_DEPENDENCY_MODULE_PATHS):
        _fail("source-v3 fixed dependency path closure differs")
    identities = _sequence(
        item.get("module_code_identities"), label="dependency identities"
    )
    if len(identities) != len(paths):
        _fail("source-v3 dependency identity count differs")
    normalized_identities: list[dict[str, str]] = []
    for ordinal, (path, identity_value) in enumerate(
        zip(paths, identities, strict=True)
    ):
        try:
            identity = source.normalize_code_identity_v2(
                identity_value,
                expected_module_path=str(path),
                label=f"dependency identity[{ordinal}]",
            )
        except source.CorpusR6MatchupSourceV2Error as exc:
            raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
                str(exc)
            ) from exc
        if identity["source_commit_sha"] != commit:
            _fail("source-v3 dependency identity commit differs")
        normalized_identities.append(identity)
    normalized = dict(item)
    normalized["module_paths"] = paths
    normalized["module_code_identities"] = normalized_identities
    if (
        item.get("schema_version") != DEPENDENCY_CLOSURE_SCHEMA
        or item.get("module_code_identity_manifest_sha256")
        != canonical_sha256(normalized_identities)
        or item.get("repository_status_clean") is not True
        or item.get("all_head_blobs_match_current_nofollow_bytes") is not True
        or canonical_json_bytes(normalized) != canonical_json_bytes(item)
    ):
        _fail("source-v3 dependency closure fixed law differs")
    return normalized


def _trusted_dependency_closure_v3() -> dict[str, object]:
    """Bind the complete current execution closure to one clean Git HEAD."""

    try:
        root = batch_mechanics._trusted_repository_root_v1()
        head = batch_mechanics._trusted_git_head_v1(root)
        # Publication is allowed only from a completely clean worktree.  This
        # intentionally includes untracked files, not merely the fixed paths.
        whole_status = batch_mechanics._run_trusted_git_v1(
            root, ["status", "--porcelain=v1", "--untracked-files=all"]
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 clean Git boundary failed: {exc}"
        ) from exc
    if whole_status != b"":
        _fail("source-v3 publication requires a completely clean worktree")
    identities: list[dict[str, str]] = []
    for relative_path in EXECUTED_DEPENDENCY_MODULE_PATHS:
        try:
            current = batch_mechanics._secure_read_repository_file_v1(
                root,
                relative_path,
                label=f"source-v3 dependency {relative_path}",
            )
            committed = batch_mechanics._trusted_git_blob_v1(
                root, head, relative_path
            )
        except Exception as exc:
            raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
                f"source-v3 dependency replay failed: {relative_path}: {exc}"
            ) from exc
        if current != committed:
            _fail(f"source-v3 dependency differs from clean HEAD: {relative_path}")
        identities.append({
            "source_commit_sha": head,
            "module_path": relative_path,
            "module_sha256": sha256(current).hexdigest(),
        })
    body: dict[str, object] = {
        "schema_version": DEPENDENCY_CLOSURE_SCHEMA,
        "source_commit_sha": head,
        "module_paths": list(EXECUTED_DEPENDENCY_MODULE_PATHS),
        "module_code_identities": identities,
        "module_code_identity_manifest_sha256": canonical_sha256(identities),
        "repository_status_clean": True,
        "all_head_blobs_match_current_nofollow_bytes": True,
    }
    body["dependency_closure_sha256"] = canonical_sha256(body)
    return _normalize_dependency_closure(body)


def _module_origin(relative_path: str, module_name: str) -> str:
    try:
        module = importlib.import_module(module_name)
        origin = Path(str(module.__file__)).resolve(strict=True)
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"loaded module origin failed: {module_name}"
        ) from exc
    expected = (REPOSITORY_ROOT / relative_path).resolve(strict=True)
    if origin != expected:
        _fail(f"loaded module origin escaped clean closure: {module_name}")
    return relative_path


def _normalize_runtime_binding(
    value: object, *, dependency_closure: Mapping[str, object]
) -> dict[str, object]:
    closure = _normalize_dependency_closure(dependency_closure)
    item = _mapping(value, label="source-v3 runtime binding")
    fields = {
        "schema_version",
        "source_commit_sha",
        "dependency_closure_sha256",
        "image_digest",
        "image_reference",
        "image_source_commit_sha",
        "image_identity_source",
        "image_identity_environment_declared",
        "image_digest_runtime_provider_attested",
        "image_build_receipt_exact_reopened",
        "git_independent_runtime_receipt_required",
        "loaded_module_origins",
        "loaded_module_origin_manifest_sha256",
        "critical_callables",
        "critical_callable_manifest_sha256",
        "immutable_image_identity_required",
        "all_loaded_origins_match_clean_dependency_closure",
        "all_loaded_callable_code_matches_clean_dependency_closure",
        "same_clean_commit_and_image_required_for_resume",
        "runtime_binding_sha256",
    }
    if set(item) != fields:
        _fail("source-v3 runtime binding fields differ")
    retained = _digest(
        item.get("runtime_binding_sha256"), label="runtime binding hash"
    )
    unhashed = dict(item)
    del unhashed["runtime_binding_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("source-v3 runtime binding self-hash differs")
    digest = item.get("image_digest")
    reference = item.get("image_reference")
    if (
        type(digest) is not str
        or _IMAGE_DIGEST.fullmatch(digest) is None
        or type(reference) is not str
        or not reference.endswith(f"@{digest}")
        or len(reference) > 512
        or any(character.isspace() for character in reference)
    ):
        _fail("source-v3 immutable image identity differs")
    origins = _mapping(
        item.get("loaded_module_origins"), label="loaded module origins"
    )
    if origins != dict(sorted(_RUNTIME_MODULE_PATHS.items())):
        _fail("source-v3 loaded module origin set differs")
    callable_specs = _critical_loaded_callables_v3()
    expected_callable_qualnames = {
        (
            _callable_owner_module_name_v3(owner),
            attribute,
            relative_path,
        ): str(
            getattr(getattr(owner, attribute, None), "__qualname__", "") or ""
        )
        for owner, attribute, relative_path in callable_specs
    }
    if (
        len(expected_callable_qualnames) != len(callable_specs)
        or any(not value for value in expected_callable_qualnames.values())
    ):
        _fail("source-v3 critical callable specification is ambiguous")
    callables: list[dict[str, object]] = []
    for ordinal, value_callable in enumerate(
        _sequence(item.get("critical_callables"), label="critical callables")
    ):
        row = _mapping(value_callable, label=f"critical callable[{ordinal}]")
        if set(row) != {
            "module_name",
            "attribute",
            "module_path",
            "qualname",
            "loaded_code_sha256",
            "committed_source_code_sha256",
            "loaded_code_matches_committed_source",
        }:
            _fail("source-v3 critical callable fields differ")
        key = (
            str(row.get("module_name")),
            str(row.get("attribute")),
            str(row.get("module_path")),
        )
        expected_qualname = expected_callable_qualnames.get(key)
        _digest(
            row.get("loaded_code_sha256"), label="loaded callable code hash"
        )
        _digest(
            row.get("committed_source_code_sha256"),
            label="committed callable code hash",
        )
        if (
            expected_qualname is None
            or row.get("qualname") != expected_qualname
            or row["loaded_code_sha256"]
            != row["committed_source_code_sha256"]
            or row.get("loaded_code_matches_committed_source") is not True
        ):
            _fail("source-v3 critical callable binding differs")
        callables.append(row)
    if (
        len(callables) != len(expected_callable_qualnames)
        or callables != sorted(
            callables,
            key=lambda row: (
                str(row["module_name"]),
                str(row["attribute"]),
                str(row["module_path"]),
            ),
        )
        or {
            (
                str(row["module_name"]),
                str(row["attribute"]),
                str(row["module_path"]),
            )
            for row in callables
        }
        != set(expected_callable_qualnames)
    ):
        _fail("source-v3 critical callable set/order differs")
    if (
        item.get("schema_version") != RUNTIME_BINDING_SCHEMA
        or item.get("source_commit_sha") != closure["source_commit_sha"]
        or item.get("image_source_commit_sha") != closure["source_commit_sha"]
        or item.get("dependency_closure_sha256")
        != closure["dependency_closure_sha256"]
        or item.get("loaded_module_origin_manifest_sha256")
        != canonical_sha256(origins)
        or item.get("critical_callable_manifest_sha256")
        != canonical_sha256(callables)
        or item.get("image_identity_source") != "environment-declared"
        or item.get("image_identity_environment_declared") is not True
        or item.get("image_digest_runtime_provider_attested") is not False
        or item.get("image_build_receipt_exact_reopened") is not False
        or item.get("git_independent_runtime_receipt_required") is not True
        or item.get("immutable_image_identity_required") is not True
        or item.get("all_loaded_origins_match_clean_dependency_closure") is not True
        or item.get("all_loaded_callable_code_matches_clean_dependency_closure")
        is not True
        or item.get("same_clean_commit_and_image_required_for_resume") is not True
    ):
        _fail("source-v3 runtime binding fixed law differs")
    normalized = dict(item)
    normalized["loaded_module_origins"] = origins
    normalized["critical_callables"] = callables
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("source-v3 runtime binding canonical replay differs")
    return normalized


def _build_runtime_binding_v3(
    dependency_closure: Mapping[str, object]
) -> dict[str, object]:
    closure = _normalize_dependency_closure(dependency_closure)
    # The callable registry is itself part of the measured surface.  Measure
    # it before trusting the specifications it returns so a substituted
    # registry cannot coherently omit the substituted callable.  A later
    # provider/build receipt is still required to prove the declared image
    # digest; this local check closes only the loaded Python surface.
    registry = _critical_loaded_callables_v3
    registry_code = getattr(registry, "__code__", None)
    registry_qualname = getattr(registry, "__qualname__", None)
    expected_registry_filename = str(
        (REPOSITORY_ROOT / BATCH_MODULE_PATH).resolve(strict=True)
    )
    if (
        registry_code is None
        or type(registry_qualname) is not str
        or Path(str(registry_code.co_filename)).resolve(strict=True)
        != Path(expected_registry_filename)
    ):
        _fail("source-v3 critical callable registry origin differs")
    registry_loaded_sha = batch_mechanics.canonical_sha256(
        batch_mechanics._code_object_fingerprint_v1(registry_code)
    )
    try:
        registry_committed_sha = (
            batch_mechanics._compiled_callable_code_sha256_v1(
                expected_path=BATCH_MODULE_PATH,
                expected_qualname=registry_qualname,
            )
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 callable registry replay failed: {exc}"
        ) from exc
    if registry_loaded_sha != registry_committed_sha:
        _fail("source-v3 critical callable registry differs from clean source")
    callable_specs = registry()
    digest = os.environ.get(IMAGE_DIGEST_ENV)
    reference = os.environ.get(IMAGE_REFERENCE_ENV)
    image_commit = os.environ.get(IMAGE_SOURCE_COMMIT_ENV)
    if (
        type(digest) is not str
        or type(reference) is not str
        or type(image_commit) is not str
    ):
        _fail("source-v3 immutable image identity environment is incomplete")
    module_names = {
        "batch_v3": __name__,
        "candidate_release_v2": candidate_v2.__name__,
        "capture_plan_v3": capture_v3.__name__,
        "component_publication_v3": component_v3.__name__,
        "leaf_operator_v2": operator_v2.__name__,
        "source_release_v3": release_v3.__name__,
    }
    origins = {
        key: _module_origin(_RUNTIME_MODULE_PATHS[key], module_names[key])
        for key in sorted(module_names)
    }
    critical_callables: list[dict[str, object]] = []
    for owner, attribute, relative_path in callable_specs:
        loaded = getattr(owner, attribute, None)
        code = getattr(loaded, "__code__", None)
        qualname = getattr(loaded, "__qualname__", None)
        if code is None or type(qualname) is not str:
            _fail(f"source-v3 critical callable is not loaded: {attribute}")
        expected_filename = str((REPOSITORY_ROOT / relative_path).resolve(strict=True))
        if Path(str(code.co_filename)).resolve(strict=True) != Path(expected_filename):
            _fail(f"source-v3 critical callable origin differs: {attribute}")
        loaded_sha = batch_mechanics.canonical_sha256(
            batch_mechanics._code_object_fingerprint_v1(code)
        )
        try:
            committed_sha = batch_mechanics._compiled_callable_code_sha256_v1(
                expected_path=relative_path, expected_qualname=qualname
            )
        except Exception as exc:
            raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
                f"source-v3 committed callable replay failed: {attribute}: {exc}"
            ) from exc
        if loaded_sha != committed_sha:
            _fail(f"source-v3 loaded callable differs from clean source: {attribute}")
        critical_callables.append({
            "module_name": _callable_owner_module_name_v3(owner),
            "attribute": attribute,
            "module_path": relative_path,
            "qualname": qualname,
            "loaded_code_sha256": loaded_sha,
            "committed_source_code_sha256": committed_sha,
            "loaded_code_matches_committed_source": True,
        })
    critical_callables.sort(
        key=lambda row: (
            str(row["module_name"]),
            str(row["attribute"]),
            str(row["module_path"]),
        )
    )
    body: dict[str, object] = {
        "schema_version": RUNTIME_BINDING_SCHEMA,
        "source_commit_sha": closure["source_commit_sha"],
        "dependency_closure_sha256": closure["dependency_closure_sha256"],
        "image_digest": digest,
        "image_reference": reference,
        "image_source_commit_sha": image_commit,
        "image_identity_source": "environment-declared",
        "image_identity_environment_declared": True,
        "image_digest_runtime_provider_attested": False,
        "image_build_receipt_exact_reopened": False,
        "git_independent_runtime_receipt_required": True,
        "loaded_module_origins": origins,
        "loaded_module_origin_manifest_sha256": canonical_sha256(origins),
        "critical_callables": critical_callables,
        "critical_callable_manifest_sha256": canonical_sha256(
            critical_callables
        ),
        "immutable_image_identity_required": True,
        "all_loaded_origins_match_clean_dependency_closure": True,
        "all_loaded_callable_code_matches_clean_dependency_closure": True,
        "same_clean_commit_and_image_required_for_resume": True,
    }
    body["runtime_binding_sha256"] = canonical_sha256(body)
    return _normalize_runtime_binding(body, dependency_closure=closure)


def _trusted_capture_plan_v3(
    *, dependency_closure: Mapping[str, object]
) -> tuple[dict[str, object], dict[str, object], bytes]:
    closure = _normalize_dependency_closure(dependency_closure)
    root = batch_mechanics._trusted_repository_root_v1()
    head = str(closure["source_commit_sha"])
    path = capture_v3.CAPTURE_PLAN_LOCK_PATH
    try:
        current_raw = batch_mechanics._secure_read_repository_file_v1(
            root, path, label="tracked capture-plan-v3 lock"
        )
        committed_raw = batch_mechanics._trusted_git_blob_v1(root, head, path)
        parsed = json.loads(current_raw.decode("utf-8"))
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"tracked capture-plan-v3 replay failed: {exc}"
        ) from exc
    if current_raw != committed_raw or canonical_json_bytes(parsed) + b"\n" != current_raw:
        _fail("tracked capture-plan-v3 lock differs from canonical clean HEAD")
    try:
        plan = capture_v3.validate_capture_plan_lock_v3(parsed)
        replayed = capture_v3.reopen_capture_plan_lock_from_git_v3(
            plan_commit_sha=head,
            plan_file_sha256=sha256(current_raw).hexdigest(),
            plan_file_bytes=len(current_raw),
            read_git_blob=lambda commit, relative: (
                batch_mechanics._trusted_git_blob_v1(root, commit, relative)
            ),
            secure_read_current=lambda relative: (
                batch_mechanics._secure_read_repository_file_v1(
                    root, relative, label=f"capture-plan-v3 current {relative}"
                )
            ),
            repository_clean=True,
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"tracked capture-plan-v3 predecessor replay failed: {exc}"
        ) from exc
    if replayed != plan:
        _fail("tracked capture-plan-v3 exact replay differs")
    binding = {
        "commit_sha": head,
        "relative_path": path,
        "sha256": sha256(current_raw).hexdigest(),
        "bytes": len(current_raw),
        "capture_plan_sha256": plan["capture_plan_sha256"],
    }
    try:
        normalized_binding = release_v1._capture_plan_binding(binding)
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    return plan, normalized_binding, current_raw


def _output_uri_inventory_v3(
    *, run_id: object, plan_value: object
) -> dict[str, object]:
    """Enumerate every create target before a write client can exist."""

    # Never coerce caller input: an integer or another object must fail before
    # even a candidate output URI can be constructed.
    prefix = output_prefix_for_run_v3(run_id)
    if type(run_id) is not str:  # narrowed by the fail-closed call above
        _fail("source-v3 batch run ID must be a string")
    run = run_id
    try:
        plan = capture_v3.validate_capture_plan_lock_v3(plan_value)
    except capture_v3.CorpusR6MatchupCapturePlanOuterCandidateAuthorityV3Error as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            str(exc)
        ) from exc
    producer_namespace = str(plan["producer_namespace"])
    entries_by_uri: dict[str, dict[str, object]] = {}

    def retain(uri: str, *, phase: str) -> None:
        try:
            batch_mechanics._gcs_parts_v1(uri)
        except Exception as exc:
            raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
                f"source-v3 output URI differs: {exc}"
            ) from exc
        prior = entries_by_uri.get(uri)
        entry = {"uri": uri, "phase": phase}
        if prior is not None and prior != entry:
            _fail("one source-v3 output URI has conflicting publication phases")
        entries_by_uri[uri] = entry

    registry = source.frozen_role_registry_v2()
    roles = _sequence(registry["roles"], label="frozen role registry")
    tasks = _sequence(plan["source_task_bindings"], label="capture-plan tasks")
    if len(tasks) != source.TASK_COUNT:
        _fail("source-v3 output inventory requires exactly 54 tasks")
    for ordinal, task_value in enumerate(tasks):
        task = _mapping(task_value, label=f"capture-plan task[{ordinal}]")
        slate = _mapping(task["slate"], label=f"capture-plan slate[{ordinal}]")
        slate_id = str(slate["slate_id"])
        producer_prefix = (
            f"{producer_namespace}source-task-{ordinal:02d}-{slate_id}/producer/"
        )
        for role_value in roles:
            role = _mapping(role_value, label="frozen role")
            requirements = _sequence(
                role["period_requirements"], label="frozen role periods"
            )
            for period_ordinal, requirement_value in enumerate(requirements):
                requirement = _mapping(
                    requirement_value, label="frozen role period"
                )
                retain(
                    f"{producer_prefix}slices/{int(role['ordinal']):02d}-"
                    f"{period_ordinal:02d}-{requirement['slice_kind']}.json",
                    phase="component-producer-object",
                )
        retain(
            f"{producer_prefix}slices/00-00-schedule-games.json",
            phase="component-producer-object",
        )
        for filename in (
            "candidate-support-rows.json",
            "component-input-bundle.json",
            "component-producer-receipt.json",
        ):
            retain(
                f"{producer_prefix}{filename}",
                phase="component-producer-object",
            )
        task_prefix = f"{prefix}source-task-{ordinal:02d}-{slate_id}/"
        for filename in (
            "matchup-source-export.json",
            "matchup-capture-receipt.json",
            "matchup-operator-result.json",
        ):
            retain(f"{task_prefix}{filename}", phase="source-triple")
    retain(
        f"{producer_namespace}producer-release.json",
        phase="component-producer-root",
    )
    source_root_uri = f"{prefix}{release_v3.ROOT_FILENAME}"
    retain(source_root_uri, phase="source-release-v3-root")
    terminal_root_uri = f"{prefix}{ROOT_FILENAME}"
    retain(terminal_root_uri, phase="terminal-batch-v3-root")
    entries = sorted(entries_by_uri.values(), key=lambda row: str(row["uri"]))
    uris = [str(row["uri"]) for row in entries]
    body: dict[str, object] = {
        "schema_version": OUTPUT_URI_INVENTORY_SCHEMA,
        "run_id": run,
        "namespace": prefix,
        "producer_namespace": producer_namespace,
        "entries": entries,
        "uris": uris,
        "uri_count": len(uris),
        "uri_manifest_sha256": canonical_sha256(uris),
        "entry_manifest_sha256": canonical_sha256(entries),
        "source_release_root_uri": source_root_uri,
        "terminal_batch_root_uri": terminal_root_uri,
        "inventory_derived_before_write_client_construction": True,
        "broad_prefix_write_authority_allowed": False,
        "unexpected_uri_backend_call_possible": False,
    }
    body["output_uri_inventory_sha256"] = canonical_sha256(body)
    return _normalize_output_uri_inventory_v3(body)


def _normalize_output_uri_inventory_v3(value: object) -> dict[str, object]:
    item = _mapping(value, label="source-v3 output URI inventory")
    fields = {
        "schema_version",
        "run_id",
        "namespace",
        "producer_namespace",
        "entries",
        "uris",
        "uri_count",
        "uri_manifest_sha256",
        "entry_manifest_sha256",
        "source_release_root_uri",
        "terminal_batch_root_uri",
        "inventory_derived_before_write_client_construction",
        "broad_prefix_write_authority_allowed",
        "unexpected_uri_backend_call_possible",
        "output_uri_inventory_sha256",
    }
    if set(item) != fields:
        _fail("source-v3 output URI inventory fields differ")
    retained = _digest(
        item.get("output_uri_inventory_sha256"), label="output inventory hash"
    )
    unhashed = dict(item)
    del unhashed["output_uri_inventory_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("source-v3 output URI inventory self-hash differs")
    entries: list[dict[str, object]] = []
    allowed_phases = {
        "component-producer-object",
        "component-producer-root",
        "source-triple",
        "source-release-v3-root",
        "terminal-batch-v3-root",
    }
    for ordinal, value_entry in enumerate(
        _sequence(item.get("entries"), label="output inventory entries")
    ):
        entry = _mapping(value_entry, label=f"output inventory entry[{ordinal}]")
        if (
            set(entry) != {"uri", "phase"}
            or type(entry.get("uri")) is not str
            or entry.get("phase") not in allowed_phases
        ):
            _fail("source-v3 output inventory entry differs")
        batch_mechanics._gcs_parts_v1(entry["uri"])
        entries.append(entry)
    uris = _sequence(item.get("uris"), label="output inventory URIs")
    run_id = item.get("run_id")
    prefix = output_prefix_for_run_v3(run_id)
    if (
        any(type(uri) is not str for uri in uris)
        or entries != sorted(entries, key=lambda row: str(row["uri"]))
        or uris != [row["uri"] for row in entries]
        or uris != sorted(uris)
        or len(uris) != len(set(uris))
        or item.get("schema_version") != OUTPUT_URI_INVENTORY_SCHEMA
        or item.get("namespace") != prefix
        or type(item.get("producer_namespace")) is not str
        or not str(item["producer_namespace"]).endswith("/")
        or item.get("uri_count") != len(uris)
        or item.get("uri_manifest_sha256") != canonical_sha256(uris)
        or item.get("entry_manifest_sha256") != canonical_sha256(entries)
        or item.get("source_release_root_uri")
        != f"{prefix}{release_v3.ROOT_FILENAME}"
        or item.get("terminal_batch_root_uri") != f"{prefix}{ROOT_FILENAME}"
        or item.get("inventory_derived_before_write_client_construction") is not True
        or item.get("broad_prefix_write_authority_allowed") is not False
        or item.get("unexpected_uri_backend_call_possible") is not False
    ):
        _fail("source-v3 output URI inventory fixed law differs")
    normalized = dict(item)
    normalized["entries"] = entries
    normalized["uris"] = uris
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("source-v3 output URI inventory canonical replay differs")
    return normalized


def _parse_exact_json(
    identity_value: object,
    *,
    read_exact: batch_mechanics.ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"{label} generation-exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} content identity differs")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"{label} is not canonical JSON"
        ) from exc
    body = _mapping(parsed, label=label)
    if canonical_json_bytes(body) != raw:
        _fail(f"{label} canonical bytes differ")
    return body, identity


def _publish_json(
    body_value: Mapping[str, object],
    *,
    uri: str,
    publish_create_once: batch_mechanics.PublishCreateOnce,
    read_exact: batch_mechanics.ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    body = _mapping(body_value, label=label)
    raw = canonical_json_bytes(body)
    try:
        identity = _identity(
            publish_create_once(uri, raw), label=f"published {label}"
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"{label} create-once publication failed"
        ) from exc
    if identity["uri"] != uri:
        _fail(f"published {label} URI differs")
    reopened, reopened_identity = _parse_exact_json(
        identity, read_exact=read_exact, label=f"published {label}"
    )
    if reopened != body:
        _fail(f"published {label} exact reopen differs")
    return reopened, reopened_identity


def _trusted_remote_prerequisites_v3(
    *, plan: Mapping[str, object], read_exact: batch_mechanics.ReadExact
) -> dict[str, object]:
    # The helper is only a generation-pinned parser.  Its v1 name does not
    # grant v1 plan or batch authority; the returned bodies are immediately
    # replayed through capture/component v3 below.
    try:
        return batch_mechanics._trusted_remote_prerequisites_v1(
            plan=plan, read_exact=read_exact
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 generation-pinned prerequisite replay failed: {exc}"
        ) from exc


def _deep_validate_capture_plan_v3(
    *,
    plan: Mapping[str, object],
    prerequisites: Mapping[str, object],
    read_exact: batch_mechanics.ReadExact,
) -> dict[str, object]:
    root = batch_mechanics._trusted_repository_root_v1()
    adapter = _mapping(
        plan.get("adapter_final_release_lock_binding"),
        label="adapter final release lock binding",
    )
    try:
        adapter_raw = batch_mechanics._trusted_git_blob_v1(
            root, str(adapter["commit_sha"]), str(adapter["relative_path"])
        )
        return capture_v3.validate_capture_plan_against_prerequisites_v3(
            plan,
            repository_root=root,
            read_exact=read_exact,
            git_head=batch_mechanics._trusted_git_head_v1,
            git_blob=batch_mechanics._trusted_git_blob_v1,
            git_status=batch_mechanics._trusted_git_status_v1,
            adapter_final_release_lock_commit_sha=str(adapter["commit_sha"]),
            adapter_final_release_lock_raw=adapter_raw,
            upstream_source_release=prerequisites["upstream_source_release"],
            upstream_source_release_identity=prerequisites[
                "upstream_source_release_identity"
            ],
            upstream_pack_row_objects=prerequisites[
                "upstream_pack_row_objects"
            ],
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 capture-plan predecessor replay failed: {exc}"
        ) from exc


def _operator_code_identity(
    dependency_closure: Mapping[str, object]
) -> dict[str, str]:
    closure = _normalize_dependency_closure(dependency_closure)
    by_path = {
        str(row["module_path"]): row
        for row in closure["module_code_identities"]
    }
    try:
        return source.normalize_code_identity_v2(
            by_path[operator_v2.OPERATOR_MODULE_PATH],
            expected_module_path=operator_v2.OPERATOR_MODULE_PATH,
            label="source-v3 leaf operator code identity",
        )
    except (KeyError, source.CorpusR6MatchupSourceV2Error) as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            "source-v3 leaf operator is absent from the clean closure"
        ) from exc


def _publish_source_triples_v3(
    *,
    plan: Mapping[str, object],
    capture_plan_binding: Mapping[str, object],
    component_result: Mapping[str, object],
    prerequisites: Mapping[str, object],
    output_prefix: str,
    operator_code_identity: Mapping[str, object],
    publish_create_once: batch_mechanics.PublishCreateOnce,
    read_exact: batch_mechanics.ReadExact,
) -> list[dict[str, object]]:
    component = _mapping(
        component_result.get("component_publication_result"),
        label="component-v3 nested result",
    )
    panel = _mapping(component.get("offline_panel"), label="component-v3 panel")
    candidate_release = _mapping(
        panel.get("accepted_candidate_release"), label="candidate-v2 release"
    )
    candidate_entries = _sequence(
        candidate_release.get("entries"), label="candidate-v2 entries"
    )
    bundles = _sequence(panel.get("input_bundles"), label="component bundles")
    bundle_ids = _sequence(
        panel.get("input_bundle_identities"), label="component bundle identities"
    )
    producer_receipts = _sequence(
        panel.get("producer_receipts"), label="component producer receipts"
    )
    producer_receipt_ids = _sequence(
        panel.get("producer_receipt_identities"),
        label="component producer receipt identities",
    )
    structural_catalogs = _sequence(
        prerequisites.get("structural_catalogs"), label="structural catalogs"
    )
    plan_tasks = _sequence(plan.get("source_task_bindings"), label="plan tasks")
    groups = (
        candidate_entries,
        bundles,
        bundle_ids,
        producer_receipts,
        producer_receipt_ids,
        structural_catalogs,
        plan_tasks,
    )
    if any(len(group) != source.TASK_COUNT for group in groups):
        _fail("source-v3 triple inputs do not form an exact 54-task lattice")
    triples: list[dict[str, object]] = []
    for ordinal in range(source.TASK_COUNT):
        candidate_entry = _mapping(
            candidate_entries[ordinal], label=f"candidate entry[{ordinal}]"
        )
        plan_task = _mapping(plan_tasks[ordinal], label=f"plan task[{ordinal}]")
        slate = _mapping(candidate_entry["slate"], label=f"candidate slate[{ordinal}]")
        slate_id = str(slate["slate_id"])
        if (
            candidate_entry.get("source_task_ordinal") != ordinal
            or plan_task.get("source_task_ordinal") != ordinal
            or candidate_entry.get("task_id") != plan_task.get("task_id")
            or candidate_entry.get("slate") != plan_task.get("slate")
        ):
            _fail(f"source-v3 task lattice[{ordinal}] differs")
        task_prefix = f"{output_prefix}source-task-{ordinal:02d}-{slate_id}/"
        try:
            triple = operator_v2.publish_matchup_source_triple_v2(
                source_task_ordinal=ordinal,
                output_prefix=task_prefix,
                capture_plan_binding=capture_plan_binding,
                operator_code_identity=operator_code_identity,
                producer_release_identity=panel["producer_release_identity"],
                producer_receipt=producer_receipts[ordinal],
                producer_receipt_identity=producer_receipt_ids[ordinal],
                input_bundle=bundles[ordinal],
                input_bundle_identity=bundle_ids[ordinal],
                structural_catalog=structural_catalogs[ordinal],
                catalog_identity=candidate_entry["catalog_identity"],
                candidate_artifact_identity=candidate_entry[
                    "candidate_artifact_identity"
                ],
                publish_create_once=publish_create_once,
                read_exact=read_exact,
            )
        except operator_v2.CorpusR6MatchupSourceOperatorV2Error as exc:
            raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
                str(exc)
            ) from exc
        triples.append(triple)
    return triples


def _exact_validate_all_source_members_v3(
    *, source_release: Mapping[str, object],
    read_exact: batch_mechanics.ReadExact,
) -> dict[str, object]:
    """Exact-open all 54 source members after one full v3 deep replay.

    ``release_v3.reopen_*_ordinal_v3`` intentionally replays the complete
    candidate/capture/component predecessor graph for every call.  The batch
    invokes that public deep boundary once, then uses the already frozen root,
    accepted candidate release, and producer release to exact-validate every
    base source member.  This preserves full 54-member coverage without
    rebuilding the 54-slate candidate authority 54 times.
    """

    try:
        terminal = (
            release_v3.
            validate_matchup_source_release_outer_candidate_authority_v3(
                source_release
            )
        )
        candidate_body, candidate_identity = _parse_exact_json(
            terminal["accepted_candidate_release_identity"],
            read_exact=read_exact,
            label="source-v3 accepted candidate release",
        )
        candidate_release = source.validate_accepted_candidate_release_v1(
            candidate_body
        )
        producer_body, producer_identity = _parse_exact_json(
            terminal["producer_release_identity"],
            read_exact=read_exact,
            label="source-v3 producer release",
        )
        producer_release = release_v1._producer_release_shape(
            producer_body, identity=producer_identity
        )
        base_release = release_v3._project_release_v1(terminal)
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 shared predecessor exact reopen failed: {exc}"
        ) from exc
    candidate_entries = _sequence(
        candidate_release.get("entries"), label="accepted candidate entries"
    )
    members = _sequence(terminal.get("entries"), label="source-v3 members")
    if (
        candidate_identity != terminal["accepted_candidate_release_identity"]
        or candidate_release.get("accepted_candidate_release_sha256")
        != terminal["accepted_candidate_release_sha256"]
        or producer_identity != terminal["producer_release_identity"]
        or len(candidate_entries) != source.TASK_COUNT
        or len(members) != source.TASK_COUNT
    ):
        _fail("source-v3 shared predecessor lattice differs")
    rows: list[dict[str, object]] = []
    for ordinal in range(source.TASK_COUNT):
        member = _mapping(members[ordinal], label=f"source-v3 member[{ordinal}]")
        candidate_entry = _mapping(
            candidate_entries[ordinal], label=f"candidate entry[{ordinal}]"
        )
        artifact = _mapping(
            candidate_entry.get("candidate_artifact"),
            label=f"candidate artifact[{ordinal}]",
        )
        artifact_identity = _identity(
            candidate_entry.get("candidate_artifact_identity"),
            label=f"candidate artifact[{ordinal}]",
        )
        try:
            deep = release_v1._reopen_validated_matchup_source_release_ordinal_v1(
                release=base_release,
                ordinal=ordinal,
                read_exact=read_exact,
                producer_release=producer_release,
            )
        except Exception as exc:
            raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
                f"source-v3 member[{ordinal}] exact reopen failed: {exc}"
            ) from exc
        if (
            candidate_entry.get("source_task_ordinal") != ordinal
            or member.get("source_task_ordinal") != ordinal
            or candidate_entry.get("task_id") != member.get("task_id")
            or candidate_entry.get("slate") != member.get("slate")
            or candidate_entry.get("catalog_identity")
            != member.get("catalog_identity")
            or artifact_identity != member.get("candidate_artifact_identity")
            or artifact.get("source_task_ordinal") != ordinal
            or artifact.get("candidate_artifact_sha256")
            != member.get("candidate_artifact_sha256")
            or candidate_entry.get("candidate_count")
            != member.get("candidate_count")
            or candidate_entry.get("ordered_candidate_ids_sha256")
            != member.get("ordered_candidate_ids_sha256")
            or canonical_json_bytes(artifact)
            != canonical_json_bytes(deep["candidate_artifact"])
        ):
            _fail(f"source-v3 member[{ordinal}] candidate binding differs")
        rows.append({
            "source_task_ordinal": ordinal,
            "task_id": member["task_id"],
            "slate": member["slate"],
            "candidate_artifact_identity": artifact_identity,
            "source_export_identity": member["source_export_identity"],
            "capture_receipt_identity": member["capture_receipt_identity"],
            "operator_result_identity": member["operator_result_identity"],
            "member_sha256": member[
                "matchup_source_member_candidate_authority_sha256"
            ],
        })
    return {
        "schema_version": (
            "corpus-r6-matchup-source-batch-member-exact-replay/v3"
        ),
        "source_task_count": source.TASK_COUNT,
        "source_task_ordinals": list(range(source.TASK_COUNT)),
        "member_bindings_sha256": canonical_sha256(rows),
        "all_54_base_source_members_generation_exact_reopened": True,
        "shared_candidate_and_producer_identities_used": True,
    }


def _normalize_read_budget_receipt_v3(value: object) -> dict[str, object]:
    item = _mapping(value, label="source-v3 exact-read budget receipt")
    fields = {
        "schema_version",
        "ledger_kind",
        "max_object_bytes",
        "max_invocation_read_bytes",
        "max_read_operations",
        "read_bytes_reserved",
        "read_operations_reserved",
        "read_charges",
        "read_charge_manifest_sha256",
        "all_payload_reads_charged_before_access",
        "failed_reads_remain_charged",
        "per_invocation_only",
        "cross_process_durable_ledger",
        "exact_read_budget_sha256",
    }
    if set(item) != fields:
        _fail("source-v3 exact-read budget receipt fields differ")
    retained = _digest(
        item.get("exact_read_budget_sha256"), label="exact-read budget hash"
    )
    unhashed = dict(item)
    del unhashed["exact_read_budget_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("source-v3 exact-read budget receipt self-hash differs")
    charges: list[dict[str, object]] = []
    for ordinal, charge_value in enumerate(
        _sequence(item.get("read_charges"), label="exact-read charges")
    ):
        charge = _mapping(charge_value, label=f"exact-read charge[{ordinal}]")
        if set(charge) != {
            "ordinal",
            "uri",
            "generation",
            "bytes",
            "purpose",
            "charged_before_payload_access",
            "failed_reads_remain_charged",
            "read_charge_sha256",
        }:
            _fail("source-v3 exact-read charge fields differ")
        retained_charge = _digest(
            charge.get("read_charge_sha256"), label="exact-read charge hash"
        )
        charge_unhashed = dict(charge)
        del charge_unhashed["read_charge_sha256"]
        generation = charge.get("generation")
        byte_count = charge.get("bytes")
        if (
            canonical_sha256(charge_unhashed) != retained_charge
            or type(charge.get("ordinal")) is not int
            or charge.get("ordinal") != ordinal
            or type(charge.get("uri")) is not str
            or (
                generation is not None
                and (
                    type(generation) is not str
                    or not generation.isdigit()
                    or generation.startswith("0")
                )
            )
            or type(byte_count) is not int
            or not 1 <= byte_count <= batch_mechanics.MAX_EXACT_OBJECT_BYTES
            or charge.get("purpose")
            not in {
                "generation-pinned-exact-read",
                "create-once-attempt-exact-resume",
                "create-once-current-generation-reopen",
            }
            or charge.get("charged_before_payload_access") is not True
            or charge.get("failed_reads_remain_charged") is not True
        ):
            _fail("source-v3 exact-read charge fixed law differs")
        batch_mechanics._gcs_parts_v1(charge["uri"])
        charges.append(charge)
    if (
        item.get("schema_version") != batch_mechanics.EXACT_READ_BUDGET_SCHEMA
        or item.get("ledger_kind") != "genuine-production-gcs-transport"
        or type(item.get("max_object_bytes")) is not int
        or not 1
        <= int(item["max_object_bytes"])
        <= batch_mechanics.MAX_EXACT_OBJECT_BYTES
        or type(item.get("max_invocation_read_bytes")) is not int
        or not 1
        <= int(item["max_invocation_read_bytes"])
        <= batch_mechanics.MAX_EXACT_READ_INVOCATION_BYTES
        or item["max_object_bytes"] > item["max_invocation_read_bytes"]
        or type(item.get("max_read_operations")) is not int
        or not 1
        <= int(item["max_read_operations"])
        <= batch_mechanics.MAX_EXACT_READ_OPERATIONS
        or type(item.get("read_operations_reserved")) is not int
        or item.get("read_operations_reserved") != len(charges)
        or type(item.get("read_bytes_reserved")) is not int
        or item.get("read_bytes_reserved")
        != sum(int(charge["bytes"]) for charge in charges)
        or int(item["read_bytes_reserved"])
        > int(item["max_invocation_read_bytes"])
        or item.get("read_charge_manifest_sha256") != canonical_sha256(charges)
        or item.get("all_payload_reads_charged_before_access") is not True
        or item.get("failed_reads_remain_charged") is not True
        or item.get("per_invocation_only") is not True
        or item.get("cross_process_durable_ledger") is not False
    ):
        _fail("source-v3 exact-read budget receipt fixed law differs")
    normalized = dict(item)
    normalized["read_charges"] = charges
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("source-v3 exact-read budget receipt canonical replay differs")
    return normalized


def _normalize_write_budget_receipt_v3(
    value: object, *, output_uri_inventory: Mapping[str, object]
) -> dict[str, object]:
    inventory = _normalize_output_uri_inventory_v3(output_uri_inventory)
    item = _mapping(value, label="source-v3 create-once budget receipt")
    fields = {
        "schema_version",
        "expected_write_uris",
        "expected_write_uri_manifest_sha256",
        "expected_write_uri_count",
        "max_write_operations",
        "max_invocation_write_bytes",
        "write_operations_reserved",
        "write_bytes_reserved",
        "write_charges",
        "write_charge_manifest_sha256",
        "completed_write_uris",
        "completed_write_uri_manifest_sha256",
        "pending_write_uris",
        "pending_write_uri_manifest_sha256",
        "all_backend_writes_charged_before_call",
        "failed_attempts_remain_charged",
        "unexpected_uri_backend_call_possible",
        "per_invocation_only",
        "cross_process_durable_ledger",
        "publication_work_receipt_sha256",
    }
    if set(item) != fields:
        _fail("source-v3 create-once budget receipt fields differ")
    retained = _digest(
        item.get("publication_work_receipt_sha256"),
        label="create-once budget hash",
    )
    unhashed = dict(item)
    del unhashed["publication_work_receipt_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("source-v3 create-once budget receipt self-hash differs")
    expected = _sequence(
        item.get("expected_write_uris"), label="expected write URIs"
    )
    completed = _sequence(
        item.get("completed_write_uris"), label="completed write URIs"
    )
    pending = _sequence(item.get("pending_write_uris"), label="pending write URIs")
    if any(type(uri) is not str for uri in (*completed, *pending)):
        _fail("source-v3 create-once completion URI differs")
    charges: list[dict[str, object]] = []
    attempts_by_uri: dict[str, list[int]] = {}
    for ordinal, charge_value in enumerate(
        _sequence(item.get("write_charges"), label="create-once charges")
    ):
        charge = _mapping(charge_value, label=f"create-once charge[{ordinal}]")
        if set(charge) != {
            "ordinal",
            "uri",
            "attempt",
            "bytes",
            "charged_before_backend_call",
            "failed_attempts_remain_charged",
            "write_charge_sha256",
        }:
            _fail("source-v3 create-once charge fields differ")
        retained_charge = _digest(
            charge.get("write_charge_sha256"), label="create-once charge hash"
        )
        charge_unhashed = dict(charge)
        del charge_unhashed["write_charge_sha256"]
        if (
            canonical_sha256(charge_unhashed) != retained_charge
            or type(charge.get("ordinal")) is not int
            or charge.get("ordinal") != ordinal
            or charge.get("uri") not in expected
            or type(charge.get("attempt")) is not int
            or not 1 <= int(charge["attempt"]) <= batch_mechanics.CREATE_ONCE_ATTEMPTS
            or type(charge.get("bytes")) is not int
            or not 1
            <= int(charge["bytes"])
            <= batch_mechanics.MAX_EXACT_OBJECT_BYTES
            or charge.get("charged_before_backend_call") is not True
            or charge.get("failed_attempts_remain_charged") is not True
        ):
            _fail("source-v3 create-once charge fixed law differs")
        attempts_by_uri.setdefault(str(charge["uri"]), []).append(
            int(charge["attempt"])
        )
        charges.append(charge)
    if any(
        attempts != list(range(1, len(attempts) + 1))
        for attempts in attempts_by_uri.values()
    ):
        _fail("source-v3 create-once retry sequence differs")
    if (
        item.get("schema_version") != batch_mechanics.CREATE_ONCE_BUDGET_SCHEMA
        or expected != inventory["uris"]
        or item.get("expected_write_uri_manifest_sha256")
        != inventory["uri_manifest_sha256"]
        or type(item.get("expected_write_uri_count")) is not int
        or item.get("expected_write_uri_count") != inventory["uri_count"]
        or type(item.get("max_write_operations")) is not int
        or item.get("max_write_operations")
        != int(inventory["uri_count"]) * batch_mechanics.CREATE_ONCE_ATTEMPTS
        or type(item.get("max_invocation_write_bytes")) is not int
        or not 1
        <= int(item["max_invocation_write_bytes"])
        <= batch_mechanics.MAX_CREATE_ONCE_INVOCATION_BYTES
        or type(item.get("write_operations_reserved")) is not int
        or item.get("write_operations_reserved") != len(charges)
        or type(item.get("write_bytes_reserved")) is not int
        or item.get("write_bytes_reserved")
        != sum(int(charge["bytes"]) for charge in charges)
        or int(item["write_bytes_reserved"])
        > int(item["max_invocation_write_bytes"])
        or item.get("write_charge_manifest_sha256") != canonical_sha256(charges)
        or completed != sorted(completed)
        or pending != sorted(pending)
        or len(completed) != len(set(completed))
        or len(pending) != len(set(pending))
        or set(completed) & set(pending)
        or sorted(completed + pending) != expected
        or set(completed) != set(attempts_by_uri)
        or item.get("completed_write_uri_manifest_sha256")
        != canonical_sha256(completed)
        or item.get("pending_write_uri_manifest_sha256")
        != canonical_sha256(pending)
        or item.get("all_backend_writes_charged_before_call") is not True
        or item.get("failed_attempts_remain_charged") is not True
        or item.get("unexpected_uri_backend_call_possible") is not False
        or item.get("per_invocation_only") is not True
        or item.get("cross_process_durable_ledger") is not False
    ):
        _fail("source-v3 create-once budget receipt fixed law differs")
    normalized = dict(item)
    normalized.update({
        "expected_write_uris": expected,
        "completed_write_uris": completed,
        "pending_write_uris": pending,
        "write_charges": charges,
    })
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("source-v3 create-once budget receipt canonical replay differs")
    return normalized


def _normalize_read_budget_contract_v3(value: object) -> dict[str, object]:
    """Validate the retry-invariant read-budget law embedded in the root.

    The transport receipt is deliberately *not* part of the terminal object's
    content identity.  An exact-prefix retry necessarily performs a different
    sequence of generation-pinned reads, so embedding that invocation history
    would make a legitimate resume collide with the already-published root.
    """

    item = _mapping(value, label="source-v3 read-budget contract")
    fields = {
        "schema_version",
        "transport_ledger_schema",
        "transport_ledger_kind",
        "max_object_bytes",
        "max_invocation_read_bytes",
        "max_read_operations",
        "all_payload_reads_charged_before_access",
        "failed_reads_remain_charged",
        "generation_pinned_payload_reads_required",
        "per_invocation_only",
        "cross_process_durable_ledger",
        "read_budget_contract_sha256",
    }
    if set(item) != fields:
        _fail("source-v3 read-budget contract fields differ")
    retained = _digest(
        item.get("read_budget_contract_sha256"),
        label="read-budget contract hash",
    )
    unhashed = dict(item)
    del unhashed["read_budget_contract_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("source-v3 read-budget contract self-hash differs")
    if (
        item.get("schema_version") != READ_BUDGET_CONTRACT_SCHEMA
        or item.get("transport_ledger_schema")
        != batch_mechanics.EXACT_READ_BUDGET_SCHEMA
        or item.get("transport_ledger_kind")
        != "genuine-production-gcs-transport"
        or type(item.get("max_object_bytes")) is not int
        or item.get("max_object_bytes")
        != batch_mechanics.MAX_EXACT_OBJECT_BYTES
        or type(item.get("max_invocation_read_bytes")) is not int
        or item.get("max_invocation_read_bytes")
        != batch_mechanics.MAX_EXACT_READ_INVOCATION_BYTES
        or type(item.get("max_read_operations")) is not int
        or item.get("max_read_operations")
        != batch_mechanics.MAX_EXACT_READ_OPERATIONS
        or item.get("all_payload_reads_charged_before_access") is not True
        or item.get("failed_reads_remain_charged") is not True
        or item.get("generation_pinned_payload_reads_required") is not True
        or item.get("per_invocation_only") is not True
        or item.get("cross_process_durable_ledger") is not False
    ):
        _fail("source-v3 read-budget contract fixed law differs")
    return dict(item)


def _read_budget_contract_v3() -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": READ_BUDGET_CONTRACT_SCHEMA,
        "transport_ledger_schema": batch_mechanics.EXACT_READ_BUDGET_SCHEMA,
        "transport_ledger_kind": "genuine-production-gcs-transport",
        "max_object_bytes": batch_mechanics.MAX_EXACT_OBJECT_BYTES,
        "max_invocation_read_bytes": (
            batch_mechanics.MAX_EXACT_READ_INVOCATION_BYTES
        ),
        "max_read_operations": batch_mechanics.MAX_EXACT_READ_OPERATIONS,
        "all_payload_reads_charged_before_access": True,
        "failed_reads_remain_charged": True,
        "generation_pinned_payload_reads_required": True,
        "per_invocation_only": True,
        "cross_process_durable_ledger": False,
    }
    body["read_budget_contract_sha256"] = canonical_sha256(body)
    return _normalize_read_budget_contract_v3(body)


def _normalize_write_budget_contract_v3(
    value: object, *, output_uri_inventory: Mapping[str, object]
) -> dict[str, object]:
    """Validate the fixed create-once budget, independent of retry history."""

    inventory = _normalize_output_uri_inventory_v3(output_uri_inventory)
    item = _mapping(value, label="source-v3 write-budget contract")
    fields = {
        "schema_version",
        "transport_ledger_schema",
        "output_uri_inventory_sha256",
        "expected_write_uri_count",
        "expected_write_uri_manifest_sha256",
        "create_once_attempts_per_uri",
        "max_write_operations",
        "max_invocation_write_bytes",
        "all_backend_writes_charged_before_call",
        "failed_attempts_remain_charged",
        "unexpected_uri_backend_call_possible",
        "create_once_only",
        "exact_equal_existing_bytes_resume_allowed",
        "different_bytes_collision_rejected",
        "per_invocation_only",
        "cross_process_durable_ledger",
        "write_budget_contract_sha256",
    }
    if set(item) != fields:
        _fail("source-v3 write-budget contract fields differ")
    retained = _digest(
        item.get("write_budget_contract_sha256"),
        label="write-budget contract hash",
    )
    unhashed = dict(item)
    del unhashed["write_budget_contract_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("source-v3 write-budget contract self-hash differs")
    if (
        item.get("schema_version") != WRITE_BUDGET_CONTRACT_SCHEMA
        or item.get("transport_ledger_schema")
        != batch_mechanics.CREATE_ONCE_BUDGET_SCHEMA
        or item.get("output_uri_inventory_sha256")
        != inventory["output_uri_inventory_sha256"]
        or type(item.get("expected_write_uri_count")) is not int
        or item.get("expected_write_uri_count") != inventory["uri_count"]
        or item.get("expected_write_uri_manifest_sha256")
        != inventory["uri_manifest_sha256"]
        or type(item.get("create_once_attempts_per_uri")) is not int
        or item.get("create_once_attempts_per_uri")
        != batch_mechanics.CREATE_ONCE_ATTEMPTS
        or type(item.get("max_write_operations")) is not int
        or item.get("max_write_operations")
        != int(inventory["uri_count"]) * batch_mechanics.CREATE_ONCE_ATTEMPTS
        or type(item.get("max_invocation_write_bytes")) is not int
        or item.get("max_invocation_write_bytes")
        != batch_mechanics.MAX_CREATE_ONCE_INVOCATION_BYTES
        or item.get("all_backend_writes_charged_before_call") is not True
        or item.get("failed_attempts_remain_charged") is not True
        or item.get("unexpected_uri_backend_call_possible") is not False
        or item.get("create_once_only") is not True
        or item.get("exact_equal_existing_bytes_resume_allowed") is not True
        or item.get("different_bytes_collision_rejected") is not True
        or item.get("per_invocation_only") is not True
        or item.get("cross_process_durable_ledger") is not False
    ):
        _fail("source-v3 write-budget contract fixed law differs")
    return dict(item)


def _write_budget_contract_v3(
    output_uri_inventory: Mapping[str, object],
) -> dict[str, object]:
    inventory = _normalize_output_uri_inventory_v3(output_uri_inventory)
    body: dict[str, object] = {
        "schema_version": WRITE_BUDGET_CONTRACT_SCHEMA,
        "transport_ledger_schema": batch_mechanics.CREATE_ONCE_BUDGET_SCHEMA,
        "output_uri_inventory_sha256": inventory[
            "output_uri_inventory_sha256"
        ],
        "expected_write_uri_count": inventory["uri_count"],
        "expected_write_uri_manifest_sha256": inventory[
            "uri_manifest_sha256"
        ],
        "create_once_attempts_per_uri": batch_mechanics.CREATE_ONCE_ATTEMPTS,
        "max_write_operations": (
            int(inventory["uri_count"])
            * batch_mechanics.CREATE_ONCE_ATTEMPTS
        ),
        "max_invocation_write_bytes": (
            batch_mechanics.MAX_CREATE_ONCE_INVOCATION_BYTES
        ),
        "all_backend_writes_charged_before_call": True,
        "failed_attempts_remain_charged": True,
        "unexpected_uri_backend_call_possible": False,
        "create_once_only": True,
        "exact_equal_existing_bytes_resume_allowed": True,
        "different_bytes_collision_rejected": True,
        "per_invocation_only": True,
        "cross_process_durable_ledger": False,
    }
    body["write_budget_contract_sha256"] = canonical_sha256(body)
    return _normalize_write_budget_contract_v3(
        body, output_uri_inventory=inventory
    )


def _normalize_preterminal_completion_v3(
    value: object, *, output_uri_inventory: Mapping[str, object]
) -> dict[str, object]:
    inventory = _normalize_output_uri_inventory_v3(output_uri_inventory)
    item = _mapping(value, label="source-v3 preterminal completion")
    fields = {
        "schema_version",
        "output_uri_inventory_sha256",
        "completed_nonterminal_write_uri_count",
        "completed_nonterminal_write_uri_manifest_sha256",
        "pending_write_uri_count",
        "pending_write_uri",
        "pending_write_uri_manifest_sha256",
        "all_preterminal_outputs_completed",
        "terminal_batch_root_pending",
        "terminal_batch_root_create_once_requested_last",
        "preterminal_completion_sha256",
    }
    if set(item) != fields:
        _fail("source-v3 preterminal completion fields differ")
    retained = _digest(
        item.get("preterminal_completion_sha256"),
        label="preterminal completion hash",
    )
    unhashed = dict(item)
    del unhashed["preterminal_completion_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("source-v3 preterminal completion self-hash differs")
    terminal = str(inventory["terminal_batch_root_uri"])
    completed = sorted(set(inventory["uris"]) - {terminal})
    if (
        item.get("schema_version") != PRETERMINAL_COMPLETION_SCHEMA
        or item.get("output_uri_inventory_sha256")
        != inventory["output_uri_inventory_sha256"]
        or type(item.get("completed_nonterminal_write_uri_count")) is not int
        or item.get("completed_nonterminal_write_uri_count") != len(completed)
        or item.get("completed_nonterminal_write_uri_manifest_sha256")
        != canonical_sha256(completed)
        or type(item.get("pending_write_uri_count")) is not int
        or item.get("pending_write_uri_count") != 1
        or item.get("pending_write_uri") != terminal
        or item.get("pending_write_uri_manifest_sha256")
        != canonical_sha256([terminal])
        or item.get("all_preterminal_outputs_completed") is not True
        or item.get("terminal_batch_root_pending") is not True
        or item.get("terminal_batch_root_create_once_requested_last") is not True
    ):
        _fail("source-v3 preterminal completion fixed law differs")
    return dict(item)


def _preterminal_completion_v3(
    output_uri_inventory: Mapping[str, object],
) -> dict[str, object]:
    inventory = _normalize_output_uri_inventory_v3(output_uri_inventory)
    terminal = str(inventory["terminal_batch_root_uri"])
    completed = sorted(set(inventory["uris"]) - {terminal})
    body: dict[str, object] = {
        "schema_version": PRETERMINAL_COMPLETION_SCHEMA,
        "output_uri_inventory_sha256": inventory[
            "output_uri_inventory_sha256"
        ],
        "completed_nonterminal_write_uri_count": len(completed),
        "completed_nonterminal_write_uri_manifest_sha256": canonical_sha256(
            completed
        ),
        "pending_write_uri_count": 1,
        "pending_write_uri": terminal,
        "pending_write_uri_manifest_sha256": canonical_sha256([terminal]),
        "all_preterminal_outputs_completed": True,
        "terminal_batch_root_pending": True,
        "terminal_batch_root_create_once_requested_last": True,
    }
    body["preterminal_completion_sha256"] = canonical_sha256(body)
    return _normalize_preterminal_completion_v3(
        body, output_uri_inventory=inventory
    )


def _preterminal_root_evidence_v3(
    *,
    output_uri_inventory: Mapping[str, object],
    read_budget_receipt: Mapping[str, object],
    write_budget_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Project live ledgers to deterministic, retry-safe root evidence."""

    inventory = _normalize_output_uri_inventory_v3(output_uri_inventory)
    actual_read_budget = _normalize_read_budget_receipt_v3(
        read_budget_receipt
    )
    actual_write_budget = _normalize_write_budget_receipt_v3(
        write_budget_receipt,
        output_uri_inventory=inventory,
    )
    terminal_uri = str(inventory["terminal_batch_root_uri"])
    completed_before_root = sorted(
        set(inventory["uris"]) - {terminal_uri}
    )
    if (
        actual_read_budget["max_object_bytes"]
        != batch_mechanics.MAX_EXACT_OBJECT_BYTES
        or actual_read_budget["max_invocation_read_bytes"]
        != batch_mechanics.MAX_EXACT_READ_INVOCATION_BYTES
        or actual_read_budget["max_read_operations"]
        != batch_mechanics.MAX_EXACT_READ_OPERATIONS
        or actual_write_budget["max_invocation_write_bytes"]
        != batch_mechanics.MAX_CREATE_ONCE_INVOCATION_BYTES
        or actual_write_budget["max_write_operations"]
        != int(inventory["uri_count"])
        * batch_mechanics.CREATE_ONCE_ATTEMPTS
        or actual_write_budget["completed_write_uris"]
        != completed_before_root
        or actual_write_budget["pending_write_uris"] != [terminal_uri]
    ):
        _fail("source-v3 live preterminal budget/completion differs")
    read_contract = _read_budget_contract_v3()
    write_contract = _write_budget_contract_v3(inventory)
    completion = _preterminal_completion_v3(inventory)
    return {
        "read_budget_contract": read_contract,
        "read_budget_contract_sha256": read_contract[
            "read_budget_contract_sha256"
        ],
        "write_budget_contract": write_contract,
        "write_budget_contract_sha256": write_contract[
            "write_budget_contract_sha256"
        ],
        "preterminal_completion": completion,
        "preterminal_completion_sha256": completion[
            "preterminal_completion_sha256"
        ],
    }


def _normalize_task0_authorization_v3(
    value: object,
    *,
    expected_run_id: str,
    expected_capture_plan_binding: Mapping[str, object],
    expected_closure_sha256: str,
    expected_runtime_sha256: str,
) -> dict[str, object]:
    # Local import avoids a module-import cycle: the bounded task0 operator
    # reuses this module's exact plan/runtime machinery, while the terminal
    # source root must durably embed the task0 authorization it produced.
    from nfl_dfs.research import (  # pylint: disable=import-outside-toplevel
        corpus_r6_matchup_source_task0_v3 as task0_v3,
    )

    try:
        return task0_v3.revalidate_full_publication_authorization_provider_source_v3(
            value,
            expected_run_id=expected_run_id,
            expected_capture_plan_binding=expected_capture_plan_binding,
            expected_closure_sha256=expected_closure_sha256,
            expected_runtime_sha256=expected_runtime_sha256,
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 task0 full authorization differs: {exc}"
        ) from exc


def _build_batch_root_v3(
    *,
    run_id: str,
    capture_plan: Mapping[str, object],
    capture_plan_binding: Mapping[str, object],
    dependency_closure: Mapping[str, object],
    runtime_binding: Mapping[str, object],
    output_uri_inventory: Mapping[str, object],
    component_result: Mapping[str, object],
    source_release: Mapping[str, object],
    source_release_identity: Mapping[str, object],
    preterminal_read_budget_receipt: Mapping[str, object],
    preterminal_write_budget_receipt: Mapping[str, object],
    task0_authorization: Mapping[str, object],
) -> dict[str, object]:
    plan = capture_v3.validate_capture_plan_lock_v3(capture_plan)
    binding = release_v1._capture_plan_binding(capture_plan_binding)
    closure = _normalize_dependency_closure(dependency_closure)
    runtime = _normalize_runtime_binding(
        runtime_binding, dependency_closure=closure
    )
    inventory = _normalize_output_uri_inventory_v3(output_uri_inventory)
    authorization = _normalize_task0_authorization_v3(
        task0_authorization,
        expected_run_id=run_id,
        expected_capture_plan_binding=binding,
        expected_closure_sha256=str(closure["dependency_closure_sha256"]),
        expected_runtime_sha256=str(runtime["runtime_binding_sha256"]),
    )
    # Validate the live invocation ledgers before constructing the terminal
    # object, but do not embed their retry-dependent charge histories.  Only
    # the fixed limits/laws and deterministic preterminal completion state are
    # content-addressed by the root so an exact-equal prefix can be resumed.
    evidence = _preterminal_root_evidence_v3(
        output_uri_inventory=inventory,
        read_budget_receipt=preterminal_read_budget_receipt,
        write_budget_receipt=preterminal_write_budget_receipt,
    )
    try:
        component = (
            component_v3.
            validate_component_publication_outer_candidate_authority_receipt_v3(
                _mapping(component_result, label="component-v3 result")[
                    "publication_receipt"
                ]
            )
        )
        terminal = release_v3.validate_matchup_source_release_outer_candidate_authority_v3(
            source_release
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 terminal input validation failed: {exc}"
        ) from exc
    terminal_identity = _identity(
        source_release_identity, label="source-v3 terminal release"
    )
    terminal_raw = canonical_json_bytes(terminal)
    prefix = output_prefix_for_run_v3(run_id)
    if (
        binding["capture_plan_sha256"] != plan["capture_plan_sha256"]
        or inventory["run_id"] != run_id
        or inventory["namespace"] != prefix
        or inventory["producer_namespace"] != plan["producer_namespace"]
        or terminal_identity["uri"] != inventory["source_release_root_uri"]
        or terminal_identity["bytes"] != len(terminal_raw)
        or terminal_identity["sha256"] != sha256(terminal_raw).hexdigest()
        or terminal["namespace"] != prefix
        or terminal["candidate_authority_root_identity"]
        != plan["fixed_g0_candidate_authority_root_identity"]
        or terminal["component_publication_v3_receipt"] != component
    ):
        _fail("source-v3 batch terminal bindings differ")
    body: dict[str, object] = {
        "schema_version": BATCH_RELEASE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "run_id": run_id,
        "namespace": prefix,
        "candidate_authority_v2_root_identity": plan[
            "fixed_g0_candidate_authority_root_identity"
        ],
        "candidate_authority_v2_root_sha256": plan[
            "fixed_g0_candidate_authority_root_sha256"
        ],
        "capture_plan_v3_binding": binding,
        "capture_plan_v3_sha256": plan["capture_plan_sha256"],
        "component_publication_v3_receipt": component,
        "component_publication_v3_receipt_sha256": component[
            "outer_candidate_component_publication_receipt_sha256"
        ],
        "producer_release_identity": terminal["producer_release_identity"],
        "producer_release_sha256": terminal["producer_release_sha256"],
        "source_release_v3_identity": terminal_identity,
        "source_release_v3_sha256": terminal[
            "matchup_source_release_candidate_authority_sha256"
        ],
        "source_release_v3_entry_manifest_sha256": terminal[
            "entry_manifest_sha256"
        ],
        "executed_dependency_closure": closure,
        "executed_dependency_closure_sha256": closure[
            "dependency_closure_sha256"
        ],
        "runtime_binding": runtime,
        "runtime_binding_sha256": runtime["runtime_binding_sha256"],
        "task0_full_publication_authorization": authorization,
        "task0_full_publication_authorization_sha256": authorization[
            "task0_full_authorization_sha256"
        ],
        "task0_worker_execution_name": authorization[
            "worker_execution_name"
        ],
        "task0_verifier_execution_name": authorization[
            "verifier_execution_name"
        ],
        "task0_verifier_provider_receipt_sha256": authorization[
            "verifier_provider_receipt_sha256"
        ],
        "task0_verifier_provider_receipt_identity": authorization[
            "verifier_provider_receipt_identity"
        ],
        "output_uri_inventory": inventory,
        "output_uri_inventory_sha256": inventory[
            "output_uri_inventory_sha256"
        ],
        **evidence,
        "task_count": source.TASK_COUNT,
        "candidate_v2_capture_v3_component_v3_source_v3_chain_complete": True,
        "candidate_v2_full_predecessor_replayed_before_terminal": True,
        "capture_v3_deep_replayed_before_terminal": True,
        "component_v3_deep_replayed_before_terminal": True,
        "source_v3_one_complete_deep_predecessor_replay_before_terminal": True,
        "source_v3_all_ordinals_generation_exact_reopened_before_terminal": True,
        "all_output_uris_preenumerated_before_write_client": True,
        "all_payload_reads_generation_pinned_and_budgeted": True,
        "all_writes_create_once_and_budgeted": True,
        "source_v3_root_published_after_all_source_members": True,
        "batch_v3_root_create_once_requested_last": True,
        "partial_prefix_exact_equal_resume_allowed": True,
        "different_bytes_collision_rejected": True,
        "same_clean_commit_and_image_required_for_resume": True,
        "create_once_resume_policy": CREATE_ONCE_RESUME_POLICY,
        **_policy(),
    }
    body["batch_release_sha256"] = canonical_sha256(body)
    return validate_batch_release_structure_v3(body)


def validate_batch_release_structure_v3(value: object) -> dict[str, object]:
    """Validate terminal structure; deep authority still requires reopen."""

    item = _mapping(value, label="source-v3 batch root")
    fields = {
        "schema_version",
        "publication_mode",
        "run_id",
        "namespace",
        "candidate_authority_v2_root_identity",
        "candidate_authority_v2_root_sha256",
        "capture_plan_v3_binding",
        "capture_plan_v3_sha256",
        "component_publication_v3_receipt",
        "component_publication_v3_receipt_sha256",
        "producer_release_identity",
        "producer_release_sha256",
        "source_release_v3_identity",
        "source_release_v3_sha256",
        "source_release_v3_entry_manifest_sha256",
        "executed_dependency_closure",
        "executed_dependency_closure_sha256",
        "runtime_binding",
        "runtime_binding_sha256",
        "task0_full_publication_authorization",
        "task0_full_publication_authorization_sha256",
        "task0_worker_execution_name",
        "task0_verifier_execution_name",
        "task0_verifier_provider_receipt_sha256",
        "task0_verifier_provider_receipt_identity",
        "output_uri_inventory",
        "output_uri_inventory_sha256",
        "read_budget_contract",
        "read_budget_contract_sha256",
        "write_budget_contract",
        "write_budget_contract_sha256",
        "preterminal_completion",
        "preterminal_completion_sha256",
        "task_count",
        "candidate_v2_capture_v3_component_v3_source_v3_chain_complete",
        "candidate_v2_full_predecessor_replayed_before_terminal",
        "capture_v3_deep_replayed_before_terminal",
        "component_v3_deep_replayed_before_terminal",
        "source_v3_one_complete_deep_predecessor_replay_before_terminal",
        "source_v3_all_ordinals_generation_exact_reopened_before_terminal",
        "all_output_uris_preenumerated_before_write_client",
        "all_payload_reads_generation_pinned_and_budgeted",
        "all_writes_create_once_and_budgeted",
        "source_v3_root_published_after_all_source_members",
        "batch_v3_root_create_once_requested_last",
        "partial_prefix_exact_equal_resume_allowed",
        "different_bytes_collision_rejected",
        "same_clean_commit_and_image_required_for_resume",
        "create_once_resume_policy",
        *_policy().keys(),
        "batch_release_sha256",
    }
    if set(item) != fields:
        _fail("source-v3 batch root fields differ")
    retained = _digest(item.get("batch_release_sha256"), label="batch root hash")
    unhashed = dict(item)
    del unhashed["batch_release_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("source-v3 batch root self-hash differs")
    for field, expected in _policy().items():
        if item.get(field) != expected:
            _fail("source-v3 batch root claims forbidden authority")
    prefix = output_prefix_for_run_v3(item.get("run_id"))
    root_identity = _identity(
        item.get("candidate_authority_v2_root_identity"),
        label="candidate-authority-v2 root",
    )
    source_identity = _identity(
        item.get("source_release_v3_identity"), label="source-release-v3 root"
    )
    producer_identity = _identity(
        item.get("producer_release_identity"), label="producer release"
    )
    binding = release_v1._capture_plan_binding(
        item.get("capture_plan_v3_binding")
    )
    closure = _normalize_dependency_closure(
        item.get("executed_dependency_closure")
    )
    runtime = _normalize_runtime_binding(
        item.get("runtime_binding"), dependency_closure=closure
    )
    authorization = _normalize_task0_authorization_v3(
        item.get("task0_full_publication_authorization"),
        expected_run_id=str(item.get("run_id")),
        expected_capture_plan_binding=binding,
        expected_closure_sha256=str(closure["dependency_closure_sha256"]),
        expected_runtime_sha256=str(runtime["runtime_binding_sha256"]),
    )
    verifier_provider_identity = _identity(
        item.get("task0_verifier_provider_receipt_identity"),
        label="task0 verifier provider receipt",
    )
    inventory = _normalize_output_uri_inventory_v3(
        item.get("output_uri_inventory")
    )
    read_contract = _normalize_read_budget_contract_v3(
        item.get("read_budget_contract")
    )
    write_contract = _normalize_write_budget_contract_v3(
        item.get("write_budget_contract"),
        output_uri_inventory=inventory,
    )
    completion = _normalize_preterminal_completion_v3(
        item.get("preterminal_completion"),
        output_uri_inventory=inventory,
    )
    try:
        component = (
            component_v3.
            validate_component_publication_outer_candidate_authority_receipt_v3(
                item.get("component_publication_v3_receipt")
            )
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 batch component receipt differs: {exc}"
        ) from exc
    for field in (
        "candidate_authority_v2_root_sha256",
        "capture_plan_v3_sha256",
        "component_publication_v3_receipt_sha256",
        "producer_release_sha256",
        "source_release_v3_sha256",
        "source_release_v3_entry_manifest_sha256",
        "executed_dependency_closure_sha256",
        "runtime_binding_sha256",
        "task0_full_publication_authorization_sha256",
        "task0_verifier_provider_receipt_sha256",
        "output_uri_inventory_sha256",
        "read_budget_contract_sha256",
        "write_budget_contract_sha256",
        "preterminal_completion_sha256",
    ):
        _digest(item.get(field), label=f"batch root {field}")
    truth_fields = (
        "candidate_v2_capture_v3_component_v3_source_v3_chain_complete",
        "candidate_v2_full_predecessor_replayed_before_terminal",
        "capture_v3_deep_replayed_before_terminal",
        "component_v3_deep_replayed_before_terminal",
        "source_v3_one_complete_deep_predecessor_replay_before_terminal",
        "source_v3_all_ordinals_generation_exact_reopened_before_terminal",
        "all_output_uris_preenumerated_before_write_client",
        "all_payload_reads_generation_pinned_and_budgeted",
        "all_writes_create_once_and_budgeted",
        "source_v3_root_published_after_all_source_members",
        "batch_v3_root_create_once_requested_last",
        "partial_prefix_exact_equal_resume_allowed",
        "different_bytes_collision_rejected",
        "same_clean_commit_and_image_required_for_resume",
    )
    if (
        item.get("schema_version") != BATCH_RELEASE_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or item.get("namespace") != prefix
        or binding["relative_path"] != capture_v3.CAPTURE_PLAN_LOCK_PATH
        or binding["capture_plan_sha256"] != item["capture_plan_v3_sha256"]
        or root_identity
        != component["fixed_g0_candidate_authority_root_identity"]
        or item["candidate_authority_v2_root_sha256"]
        != component["fixed_g0_candidate_authority_root_sha256"]
        or item["component_publication_v3_receipt_sha256"]
        != component["outer_candidate_component_publication_receipt_sha256"]
        or producer_identity != component["producer_release_identity"]
        or item["producer_release_sha256"] != component["producer_release_sha256"]
        or source_identity["uri"] != inventory["source_release_root_uri"]
        or inventory["terminal_batch_root_uri"] != f"{prefix}{ROOT_FILENAME}"
        or inventory["run_id"] != item["run_id"]
        or item["executed_dependency_closure_sha256"]
        != closure["dependency_closure_sha256"]
        or binding["commit_sha"] != closure["source_commit_sha"]
        or item["runtime_binding_sha256"] != runtime["runtime_binding_sha256"]
        or item["task0_full_publication_authorization_sha256"]
        != authorization["task0_full_authorization_sha256"]
        or item["task0_worker_execution_name"]
        != authorization["worker_execution_name"]
        or item["task0_verifier_execution_name"]
        != authorization["verifier_execution_name"]
        or item["task0_verifier_provider_receipt_sha256"]
        != authorization["verifier_provider_receipt_sha256"]
        or verifier_provider_identity
        != authorization["verifier_provider_receipt_identity"]
        or item["output_uri_inventory_sha256"]
        != inventory["output_uri_inventory_sha256"]
        or read_contract != _read_budget_contract_v3()
        or item["read_budget_contract_sha256"]
        != read_contract["read_budget_contract_sha256"]
        or write_contract != _write_budget_contract_v3(inventory)
        or item["write_budget_contract_sha256"]
        != write_contract["write_budget_contract_sha256"]
        or completion != _preterminal_completion_v3(inventory)
        or item["preterminal_completion_sha256"]
        != completion["preterminal_completion_sha256"]
        or item.get("task_count") != source.TASK_COUNT
        or any(item.get(field) is not True for field in truth_fields)
        or item.get("create_once_resume_policy") != CREATE_ONCE_RESUME_POLICY
    ):
        _fail("source-v3 batch root fixed binding differs")
    normalized = dict(item)
    normalized.update({
        "candidate_authority_v2_root_identity": root_identity,
        "capture_plan_v3_binding": binding,
        "component_publication_v3_receipt": component,
        "producer_release_identity": producer_identity,
        "source_release_v3_identity": source_identity,
        "executed_dependency_closure": closure,
        "runtime_binding": runtime,
        "task0_full_publication_authorization": authorization,
        "task0_verifier_provider_receipt_identity": verifier_provider_identity,
        "output_uri_inventory": inventory,
        "read_budget_contract": read_contract,
        "write_budget_contract": write_contract,
        "preterminal_completion": completion,
    })
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("source-v3 batch root canonical replay differs")
    return normalized


def _validate_local_context_v3() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    bytes,
]:
    closure = _trusted_dependency_closure_v3()
    runtime = _build_runtime_binding_v3(closure)
    plan, binding, plan_raw = _trusted_capture_plan_v3(
        dependency_closure=closure
    )
    if binding["commit_sha"] != closure["source_commit_sha"]:
        _fail("capture-plan-v3 observed commit differs from execution closure")
    return closure, runtime, plan, binding, plan_raw


def validate_matchup_source_batch_outer_candidate_authority_v3() -> dict[str, object]:
    """Validate clean code, image, and tracked-plan bindings without cloud."""

    closure, runtime, plan, binding, _ = _validate_local_context_v3()
    inventory = _output_uri_inventory_v3(
        run_id="validate-source-v3-batch", plan_value=plan
    )
    return {
        "schema_version": "corpus-r6-matchup-source-batch-local-validation/v3",
        "complete": True,
        "capture_plan_v3_binding": binding,
        "candidate_authority_v2_root_identity": plan[
            "fixed_g0_candidate_authority_root_identity"
        ],
        "executed_dependency_closure": closure,
        "runtime_binding": runtime,
        "example_output_uri_inventory": inventory,
        "cloud_client_constructed": False,
        "cloud_write_performed": False,
        "task0_prerequisite_read_smoke_validated": False,
        **_policy(),
    }


def validate_matchup_source_batch_task0_readiness_v3() -> dict[str, object]:
    """Prerequisite-only read smoke; no source worker or verifier is run.

    This proves that task-0 candidate/capture prerequisites can be reopened.
    It is not a component/source task execution, source publication, or a
    distinct-process verifier receipt.
    """

    closure, runtime, plan, binding, _ = _validate_local_context_v3()
    try:
        transport = batch_mechanics._trusted_gcs_transport_v1(
            expected_write_uris=()
        )
        cache = batch_mechanics.ExactReadCacheV1(transport.read_exact)
        prerequisites = _trusted_remote_prerequisites_v3(
            plan=plan, read_exact=cache.read
        )
        _deep_validate_capture_plan_v3(
            plan=plan, prerequisites=prerequisites, read_exact=cache.read
        )
        reopened = candidate_v2.reopen_fixed_g0_candidate_authority_release_v2(
            plan["fixed_g0_candidate_authority_root_identity"],
            repository_root=REPOSITORY_ROOT,
            read_exact=cache.read,
            git_head=batch_mechanics._trusted_git_head_v1,
            git_blob=batch_mechanics._trusted_git_blob_v1,
            git_status=batch_mechanics._trusted_git_status_v1,
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 task-0 readiness replay failed: {exc}"
        ) from exc
    first = _mapping(
        _sequence(
            reopened.candidate_release["entries"], label="candidate entries"
        )[0],
        label="candidate entry[0]",
    )
    body: dict[str, object] = {
        "schema_version": TASK0_RECEIPT_SCHEMA,
        "complete": True,
        "smoke_scope": "candidate-v2-capture-v3-prerequisites-only",
        "prerequisite_target_source_task_ordinals": [0],
        "task_id": first["task_id"],
        "slate": first["slate"],
        "candidate_count": first["candidate_count"],
        "candidate_authority_v2_root_identity": reopened.root_identity,
        "capture_plan_v3_binding": binding,
        "executed_dependency_closure_sha256": closure[
            "dependency_closure_sha256"
        ],
        "runtime_binding_sha256": runtime["runtime_binding_sha256"],
        "candidate_v2_full_predecessor_replay_complete": True,
        "capture_v3_deep_replay_complete": True,
        "seven_pack_source_authority_exact_reopened": True,
        "component_source_worker_executed": False,
        "source_triple_worker_executed": False,
        "source_release_v3_published": False,
        "terminal_batch_v3_published": False,
        "distinct_process_verifier_executed": False,
        "real_source_worker_and_distinct_verifier_required": True,
        "write_capability_enabled": False,
        "cloud_mutation_performed": False,
        "exact_read_cache_receipt": cache.budget_receipt(),
        "transport_read_budget_receipt": transport.read_budget_receipt(),
        **_policy(),
    }
    body["task0_readiness_receipt_sha256"] = canonical_sha256(body)
    return body


def _deep_reopen_batch_v3(
    *,
    batch_release_identity: Mapping[str, object],
    read_exact: batch_mechanics.ReadExact,
    expected_closure: Mapping[str, object] | None = None,
    expected_runtime: Mapping[str, object] | None = None,
) -> dict[str, object]:
    body, identity = _parse_exact_json(
        batch_release_identity,
        read_exact=read_exact,
        label="source-v3 terminal batch root",
    )
    root = validate_batch_release_structure_v3(body)
    if identity["uri"] != f"{root['namespace']}{ROOT_FILENAME}":
        _fail("source-v3 terminal batch root URI differs")
    closure = (
        _trusted_dependency_closure_v3()
        if expected_closure is None
        else _normalize_dependency_closure(expected_closure)
    )
    runtime = (
        _build_runtime_binding_v3(closure)
        if expected_runtime is None
        else _normalize_runtime_binding(
            expected_runtime, dependency_closure=closure
        )
    )
    plan, binding, _ = _trusted_capture_plan_v3(dependency_closure=closure)
    inventory = _output_uri_inventory_v3(run_id=root["run_id"], plan_value=plan)
    if (
        root["executed_dependency_closure"] != closure
        or root["runtime_binding"] != runtime
        or root["capture_plan_v3_binding"] != binding
        or root["capture_plan_v3_sha256"] != plan["capture_plan_sha256"]
        or root["candidate_authority_v2_root_identity"]
        != plan["fixed_g0_candidate_authority_root_identity"]
        or root["output_uri_inventory"] != inventory
    ):
        _fail("source-v3 terminal batch root differs from clean runtime/plan")
    task0_authorization = _normalize_task0_authorization_v3(
        root["task0_full_publication_authorization"],
        expected_run_id=str(root["run_id"]),
        expected_capture_plan_binding=binding,
        expected_closure_sha256=str(closure["dependency_closure_sha256"]),
        expected_runtime_sha256=str(runtime["runtime_binding_sha256"]),
    )
    source_body, source_identity = _parse_exact_json(
        root["source_release_v3_identity"],
        read_exact=read_exact,
        label="source-release-v3 root",
    )
    terminal = release_v3.validate_matchup_source_release_outer_candidate_authority_v3(
        source_body
    )
    if (
        source_identity != root["source_release_v3_identity"]
        or terminal["matchup_source_release_candidate_authority_sha256"]
        != root["source_release_v3_sha256"]
        or terminal["entry_manifest_sha256"]
        != root["source_release_v3_entry_manifest_sha256"]
        or terminal["component_publication_v3_receipt"]
        != root["component_publication_v3_receipt"]
    ):
        _fail("source-release-v3 differs from terminal batch root")
    try:
        deep = (
            release_v3.
            reopen_matchup_source_release_outer_candidate_authority_ordinal_v3(
                release_identity=source_identity,
                source_task_ordinal=0,
                repository_root=REPOSITORY_ROOT,
                read_exact=read_exact,
                git_head=batch_mechanics._trusted_git_head_v1,
                git_blob=batch_mechanics._trusted_git_blob_v1,
                git_status=batch_mechanics._trusted_git_status_v1,
            )
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 complete predecessor reopen failed: {exc}"
        ) from exc
    if deep["release"] != terminal or deep["member"] != terminal["entries"][0]:
        _fail("source-v3 complete predecessor terminal projection differs")
    member_replay = _exact_validate_all_source_members_v3(
        source_release=terminal, read_exact=read_exact
    )
    return {
        "batch_release": root,
        "batch_release_identity": identity,
        "source_release_v3": terminal,
        "source_release_v3_identity": source_identity,
        "source_task_count": source.TASK_COUNT,
        "source_task_ordinals_reopened": list(range(source.TASK_COUNT)),
        "source_member_exact_replay": member_replay,
        "task0_full_publication_authorization": task0_authorization,
        "task0_full_publication_authorization_sha256": task0_authorization[
            "task0_full_authorization_sha256"
        ],
        "task0_worker_execution_name": task0_authorization[
            "worker_execution_name"
        ],
        "task0_verifier_execution_name": task0_authorization[
            "verifier_execution_name"
        ],
        "complete_v3_predecessor_replay_count": 1,
        "candidate_v2_capture_v3_component_v3_source_v3_deep_reopen_complete": True,
        "write_capability_enabled": False,
        "cloud_mutation_performed": False,
        **_policy(),
    }


def publish_matchup_source_batch_outer_candidate_authority_v3(
    *, run_id: str, task0_authorization: Mapping[str, object]
) -> dict[str, object]:
    """Publish the complete v3 chain and terminal batch root create-once."""

    # Validate exact type and syntax before local inventory construction,
    # cloud-client construction, or any possible create-once request.
    run_prefix = output_prefix_for_run_v3(run_id)
    if os.environ.get(PUBLISH_ENABLE_ENV) != "1":
        _fail(f"source-v3 publication requires {PUBLISH_ENABLE_ENV}=1")
    closure, runtime, plan, binding, _ = _validate_local_context_v3()
    authorization = _normalize_task0_authorization_v3(
        task0_authorization,
        expected_run_id=run_id,
        expected_capture_plan_binding=binding,
        expected_closure_sha256=str(closure["dependency_closure_sha256"]),
        expected_runtime_sha256=str(runtime["runtime_binding_sha256"]),
    )
    # This must happen before the write-capable transport exists.
    inventory = _output_uri_inventory_v3(run_id=run_id, plan_value=plan)
    try:
        transport = batch_mechanics._trusted_gcs_transport_v1(
            expected_write_uris=inventory["uris"]
        )
        cache = batch_mechanics.ExactReadCacheV1(transport.read_exact)
        prerequisites = _trusted_remote_prerequisites_v3(
            plan=plan, read_exact=cache.read
        )
        _deep_validate_capture_plan_v3(
            plan=plan, prerequisites=prerequisites, read_exact=cache.read
        )
        # The prerequisite replay is read-only and may be long.  Re-measure
        # the clean checkout and loaded authority callables immediately before
        # the first component create-once request rather than relying only on
        # the earlier process-start observation.
        prewrite_closure = _trusted_dependency_closure_v3()
        prewrite_runtime = _build_runtime_binding_v3(prewrite_closure)
        if prewrite_closure != closure or prewrite_runtime != runtime:
            _fail("source-v3 clean runtime changed before first publication")
        component_result = (
            component_v3.publish_all_54_component_release_outer_candidate_authority_v3(
                candidate_authority_root_identity=plan[
                    "fixed_g0_candidate_authority_root_identity"
                ],
                capture_plan=plan,
                repository_root=REPOSITORY_ROOT,
                git_head=batch_mechanics._trusted_git_head_v1,
                git_blob=batch_mechanics._trusted_git_blob_v1,
                git_status=batch_mechanics._trusted_git_status_v1,
                upstream_source_release=prerequisites[
                    "upstream_source_release"
                ],
                upstream_source_release_identity=prerequisites[
                    "upstream_source_release_identity"
                ],
                upstream_pack_row_objects=prerequisites[
                    "upstream_pack_row_objects"
                ],
                publish_create_once=transport.publish_create_once,
                read_exact=cache.read,
            )
        )
        component_result = (
            component_v3.validate_component_publication_against_outer_candidate_authority_v3(
                component_result,
                repository_root=REPOSITORY_ROOT,
                read_exact=cache.read,
                git_head=batch_mechanics._trusted_git_head_v1,
                git_blob=batch_mechanics._trusted_git_blob_v1,
                git_status=batch_mechanics._trusted_git_status_v1,
                upstream_source_release=prerequisites[
                    "upstream_source_release"
                ],
                upstream_source_release_identity=prerequisites[
                    "upstream_source_release_identity"
                ],
                upstream_pack_row_objects=prerequisites[
                    "upstream_pack_row_objects"
                ],
            )
        )
        triples = _publish_source_triples_v3(
            plan=plan,
            capture_plan_binding=binding,
            component_result=component_result,
            prerequisites=prerequisites,
            output_prefix=run_prefix,
            operator_code_identity=_operator_code_identity(closure),
            publish_create_once=transport.publish_create_once,
            read_exact=cache.read,
        )
        if len(triples) != source.TASK_COUNT:
            _fail("source-v3 publication did not materialize exactly 54 triples")
        refreshed_closure = _trusted_dependency_closure_v3()
        refreshed_runtime = _build_runtime_binding_v3(refreshed_closure)
        if refreshed_closure != closure or refreshed_runtime != runtime:
            _fail("source-v3 clean runtime changed before source-root publication")
        source_result = (
            release_v3.publish_matchup_source_release_outer_candidate_authority_root_last_v3(
                component_publication_candidate_authority_result=component_result,
                repository_root=REPOSITORY_ROOT,
                read_exact=cache.read,
                git_head=batch_mechanics._trusted_git_head_v1,
                git_blob=batch_mechanics._trusted_git_blob_v1,
                git_status=batch_mechanics._trusted_git_status_v1,
                upstream_source_release=prerequisites[
                    "upstream_source_release"
                ],
                upstream_source_release_identity=prerequisites[
                    "upstream_source_release_identity"
                ],
                upstream_pack_row_objects=prerequisites[
                    "upstream_pack_row_objects"
                ],
                release_id=run_id,
                namespace=run_prefix,
                capture_plan_binding=binding,
                source_exports=[row["source_export"] for row in triples],
                source_export_identities=[
                    row["source_export_identity"] for row in triples
                ],
                capture_receipts=[row["capture_receipt"] for row in triples],
                capture_receipt_identities=[
                    row["capture_receipt_identity"] for row in triples
                ],
                operator_results=[row["operator_result"] for row in triples],
                operator_result_identities=[
                    row["operator_result_identity"] for row in triples
                ],
                publish_create_once=transport.publish_create_once,
            )
        )
        source_root = release_v3.validate_matchup_source_release_outer_candidate_authority_v3(
            source_result["release"]
        )
        source_identity = _identity(
            source_result["release_identity"], label="published source-v3 root"
        )
        # One public v3 reopen exercises the complete candidate-v2 ->
        # capture-v3 -> component-v3 -> source-v3 predecessor graph.  Then
        # every source member is generation-exact reopened against that same
        # root/candidate/producer lattice without multiplying the complete
        # 54-slate candidate reconstruction by another factor of 54.
        deep = (
            release_v3.
            reopen_matchup_source_release_outer_candidate_authority_ordinal_v3(
                release_identity=source_identity,
                source_task_ordinal=0,
                repository_root=REPOSITORY_ROOT,
                read_exact=cache.read,
                git_head=batch_mechanics._trusted_git_head_v1,
                git_blob=batch_mechanics._trusted_git_blob_v1,
                git_status=batch_mechanics._trusted_git_status_v1,
            )
        )
        if deep["release"] != source_root or deep["member"] != source_root[
            "entries"
        ][0]:
            _fail("source-v3 complete predecessor terminal projection differs")
        member_replay = _exact_validate_all_source_members_v3(
            source_release=source_root, read_exact=cache.read
        )
        if member_replay["source_task_count"] != source.TASK_COUNT:
            _fail("source-v3 exact member replay count differs")
        terminal_uri = str(inventory["terminal_batch_root_uri"])
        completed_before_root = sorted(set(inventory["uris"]) - {terminal_uri})
        transport.require_completed_exactly_v1(
            completed_uris=completed_before_root,
            pending_uris=[terminal_uri],
        )
        refreshed_closure = _trusted_dependency_closure_v3()
        refreshed_runtime = _build_runtime_binding_v3(refreshed_closure)
        if refreshed_closure != closure or refreshed_runtime != runtime:
            _fail("source-v3 clean runtime changed before terminal batch root")
        batch_root = _build_batch_root_v3(
            run_id=run_id,
            capture_plan=plan,
            capture_plan_binding=binding,
            dependency_closure=closure,
            runtime_binding=runtime,
            output_uri_inventory=inventory,
            component_result=component_result,
            source_release=source_root,
            source_release_identity=source_identity,
            preterminal_read_budget_receipt=transport.read_budget_receipt(),
            preterminal_write_budget_receipt=transport.write_budget_receipt(),
            task0_authorization=authorization,
        )
        _, batch_identity = _publish_json(
            batch_root,
            uri=terminal_uri,
            publish_create_once=transport.publish_create_once,
            read_exact=cache.read,
            label="source-v3 terminal batch root",
        )
        transport.require_completed_exactly_v1(
            completed_uris=inventory["uris"], pending_uris=[]
        )
        same_process_reopen = _deep_reopen_batch_v3(
            batch_release_identity=batch_identity,
            read_exact=cache.read,
            expected_closure=closure,
            expected_runtime=runtime,
        )
    except CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error:
        raise
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 publication failed closed: {exc}"
        ) from exc
    receipt: dict[str, object] = {
        "schema_version": PUBLICATION_RECEIPT_SCHEMA,
        "complete": True,
        "run_id": run_id,
        "batch_release_identity": batch_identity,
        "source_release_v3_identity": source_identity,
        "task_count": source.TASK_COUNT,
        "task0_full_publication_authorization_sha256": authorization[
            "task0_full_authorization_sha256"
        ],
        "task0_verifier_provider_receipt_sha256": authorization[
            "verifier_provider_receipt_sha256"
        ],
        "task0_verifier_provider_receipt_identity": authorization[
            "verifier_provider_receipt_identity"
        ],
        "task0_worker_execution_name": authorization[
            "worker_execution_name"
        ],
        "task0_verifier_execution_name": authorization[
            "verifier_execution_name"
        ],
        "terminal_batch_root_requested_last": True,
        "same_process_deep_reopen_complete": same_process_reopen[
            "candidate_v2_capture_v3_component_v3_source_v3_deep_reopen_complete"
        ],
        "independent_process_deep_reopen_complete": False,
        "independent_process_deep_reopen_required": True,
        "publisher_process_reused_exact_read_cache": True,
        "exact_read_cache_budget_receipt": cache.budget_receipt(),
        "transport_read_budget_receipt": transport.read_budget_receipt(),
        "transport_write_budget_receipt": transport.write_budget_receipt(),
        "cloud_mutation_performed": True,
        "deployment_performed": False,
        "graph_mutation_performed": False,
        **_policy(),
    }
    receipt["publication_receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def reopen_matchup_source_batch_outer_candidate_authority_v3(
    *, batch_release_identity: Mapping[str, object]
) -> dict[str, object]:
    """Write-disabled reopen; external orchestration proves process separation."""

    identity = _identity(
        batch_release_identity, label="source-v3 terminal batch root"
    )
    match = _ROOT_URI.fullmatch(str(identity["uri"]))
    if match is None:
        _fail("source-v3 terminal batch root identity escapes fixed namespace")
    try:
        transport = batch_mechanics._trusted_gcs_transport_v1(
            expected_write_uris=()
        )
        cache = batch_mechanics.ExactReadCacheV1(transport.read_exact)
        result = _deep_reopen_batch_v3(
            batch_release_identity=identity, read_exact=cache.read
        )
    except CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error:
        raise
    except Exception as exc:
        raise CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error(
            f"source-v3 write-disabled reopen failed closed: {exc}"
        ) from exc
    result.update({
        "write_disabled_public_reopen_complete": True,
        "process_independence_attested_by_operator": False,
        "independent_process_receipt_required": True,
        "exact_read_cache_budget_receipt": cache.budget_receipt(),
        "transport_read_budget_receipt": transport.read_budget_receipt(),
    })
    return result


__all__ = [
    "BATCH_MODULE_PATH",
    "BATCH_RELEASE_SCHEMA",
    "CLI_MODULE_PATH",
    "CREATE_ONCE_RESUME_POLICY",
    "CorpusR6MatchupSourceBatchOuterCandidateAuthorityV3Error",
    "DEPENDENCY_CLOSURE_SCHEMA",
    "EXECUTED_DEPENDENCY_MODULE_PATHS",
    "IMAGE_DIGEST_ENV",
    "IMAGE_REFERENCE_ENV",
    "IMAGE_SOURCE_COMMIT_ENV",
    "OUTPUT_BUCKET",
    "OUTPUT_NAMESPACE",
    "OUTPUT_URI_INVENTORY_SCHEMA",
    "PRODUCTION_PROJECT",
    "PRETERMINAL_COMPLETION_SCHEMA",
    "PUBLICATION_MODE",
    "PUBLICATION_RECEIPT_SCHEMA",
    "PUBLISH_ENABLE_ENV",
    "READ_BUDGET_CONTRACT_SCHEMA",
    "ROOT_FILENAME",
    "RUNTIME_BINDING_SCHEMA",
    "TASK0_RECEIPT_SCHEMA",
    "WRITE_BUDGET_CONTRACT_SCHEMA",
    "canonical_json_bytes",
    "canonical_sha256",
    "output_prefix_for_run_v3",
    "publish_matchup_source_batch_outer_candidate_authority_v3",
    "reopen_matchup_source_batch_outer_candidate_authority_v3",
    "validate_batch_release_structure_v3",
    "validate_matchup_source_batch_outer_candidate_authority_v3",
    "validate_matchup_source_batch_task0_readiness_v3",
]
