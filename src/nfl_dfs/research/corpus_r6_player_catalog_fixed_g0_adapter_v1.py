"""Fixed-G0, outcome-blind adapter for R6 structural catalog projections.

This module is the transport and replay boundary above
``corpus_r6_player_catalog_v1``.  It pins one reviewed Git commit and the exact
G0 panel, lane, source-completion, and later-source identities.  Remote bytes
arrive only through generation-specific injected readers; publication arrives
only through an atomic create-if-absent seam.

The adapter never reads world NPZ bodies, outcomes, a bucket listing, or a
"latest" object.  Its release and replay receipt remain explicitly
non-authoritative.  A later execution manifest must pin the exact replay-
receipt identity before any production source authority can exist.

Two tracked locks keep the real-artifact boundary honest.  A preliminary
review lock can authorize only one read-only task-0 smoke and one fixed local
receipt.  A later final lock must replay that receipt and the unchanged code
measurements before the 54-task create-once projection entry can construct a
cloud client.  Neither lock grants scoring, fill, retrieval, or source
authority.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from types import MappingProxyType
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog


ADAPTER_SCHEMA: Final = "corpus-r6-player-catalog-fixed-g0-replay/v1"
ADAPTER_REVIEW_LOCK_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-adapter-review-lock/v3"
)
TASK0_REAL_ARTIFACT_SMOKE_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-task0-real-artifact-smoke/v1"
)
TASK0_REAL_ARTIFACT_SMOKE_V2_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-task0-real-artifact-smoke/v2"
)
TASK0_REAL_ARTIFACT_SMOKE_ATTEMPT_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-task0-real-artifact-smoke-attempt/v1"
)
TASK0_REAL_ARTIFACT_SMOKE_ATTEMPT_V2_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-task0-real-artifact-smoke-attempt/v2"
)
TASK0_SMOKE_RECOVERY_REVIEW_LOCK_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-task0-smoke-recovery-review-lock/v1"
)
FINAL_RELEASE_LOCK_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-final-release-lock/v1"
)
FIXED_SOURCE_COMMIT_SHA: Final = "168bc70a9793dce729d7e7e0a5d809b046a7a254"
FIXED_G0_LOCK_PATH: Final = (
    "reports/corpus-parametric-runs/"
    "20260823-foundry-production-v12-panel-index/g0-authority-lock-v1.json"
)
FIXED_G0_LOCK_FILE_SHA256: Final = (
    "3feef892bf4410c579118e808c26f1d3f69cdedc9053c2919fccc19d81e65dad"
)
FIXED_G0_LOCK_FILE_BYTES: Final = 3027
FIXED_G0_LOCK_INTERNAL_SHA256: Final = (
    "d3efdb18755dc81b5a5c51964bd308ea346f2a239ad7a4279d62ce127d08dc5b"
)
FIXED_G0_LOCK_ID: Final = (
    "foundry-v12-g0:"
    "3a61840d1a74e8b8ae90e51ea3621350fec37dc0af0112942b90b63bd6d87f31"
)
FIXED_CATALOG_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_player_catalog_v1.py"
)
FIXED_CATALOG_MODULE_SHA256: Final = (
    "5da7905f3caa620597f22bfb348a12d099709feb26a409ecec8c5578c03d99b7"
)
FIXED_CATALOG_MODULE_BYTES: Final = 68934
FIXED_ADAPTER_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_adapter_v1.py"
)
FIXED_ADAPTER_TEST_PATH: Final = (
    "tests/test_corpus_r6_player_catalog_fixed_g0_adapter_v1.py"
)
FIXED_BATCH_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_parametric_batch.py"
)
FIXED_ADAPTER_REVIEW_LOCK_PATH: Final = (
    "reports/2026-08-26-r6-player-catalog-fixed-g0-adapter-review-lock.json"
)
FIXED_TASK0_SMOKE_RECEIPT_PATH: Final = (
    "reports/2026-08-26-r6-player-catalog-fixed-g0-task0-real-artifact-smoke.json"
)
FIXED_TASK0_SMOKE_ATTEMPT_PATH: Final = (
    "reports/2026-08-26-r6-player-catalog-fixed-g0-task0-real-artifact-smoke-attempt.json"
)
FIXED_TASK0_SMOKE_ATTEMPT_V2_PATH: Final = (
    "reports/2026-08-26-r6-player-catalog-fixed-g0-"
    "task0-real-artifact-smoke-attempt-v2.json"
)
FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_PATH: Final = (
    "reports/2026-08-26-r6-fixed-g0-task0-smoke-"
    "preclient-recovery-amendment.md"
)
FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_SHA256: Final = (
    "a53e9a2cf973a2ee29631a4743faff1c99aa6698c91106c66e1d67349dcab82c"
)
FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_BYTES: Final = 3646
FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH: Final = (
    "reports/2026-08-26-r6-player-catalog-fixed-g0-"
    "task0-smoke-recovery-review-lock.json"
)
FIXED_TASK0_SMOKE_ATTEMPT_V1_SHA256: Final = (
    "35d2a32334f7b06074a8f37245042881f4dd100796e3093b1e09639a6d81ae48"
)
FIXED_TASK0_SMOKE_ATTEMPT_V1_BYTES: Final = 3278
FIXED_TASK0_SMOKE_ATTEMPT_V1_INTERNAL_SHA256: Final = (
    "2e3adc38313f2811cf7d245e77d7838915cb9602cc416e3c581e20d029d57eff"
)
FIXED_FINAL_RELEASE_LOCK_PATH: Final = (
    "reports/2026-08-26-r6-player-catalog-fixed-g0-final-release-lock.json"
)
FIXED_FOCUSED_TEST_FAILURE_SUMMARY_PATH: Final = (
    "reports/2026-08-26-r6-fixed-g0-focused-test-failure-summary.md"
)
FIXED_FOCUSED_TEST_CORRECTION_ADDENDUM_PATH: Final = (
    "reports/2026-08-26-r6-fixed-g0-focused-test-correction-addendum.md"
)
FIXED_SECOND_FOCUSED_TEST_CORRECTION_PATH: Final = (
    "reports/2026-08-26-r6-fixed-g0-second-focused-test-correction-addendum.md"
)
FIXED_FINAL_CORRECTIVE_FOCUSED_TEST_OUTPUT_PATH: Final = (
    "reports/2026-08-26-r6-fixed-g0-final-corrective-focused-test-output.txt"
)
FIXED_ADAPTER_IMPLEMENTATION_PATHS: Final = (
    FIXED_ADAPTER_MODULE_PATH,
    FIXED_ADAPTER_TEST_PATH,
    FIXED_CATALOG_MODULE_PATH,
    FIXED_BATCH_MODULE_PATH,
)
FIXED_FOCUSED_TEST_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "pytest",
    "-q",
    FIXED_ADAPTER_TEST_PATH,
)
FIXED_TASK0_SMOKE_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_adapter_v1",
    "preflight-task0",
    "--preflight",
)
FIXED_TASK0_SMOKE_V2_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_adapter_v1",
    "preflight-task0-v2",
    "--preflight",
)
FIXED_TASK0_SMOKE_RECOVERY_LOCK_BUILD_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_adapter_v1",
    "build-task0-smoke-recovery-lock",
    "--output",
    FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH,
    "--static-review-approved",
    "--build",
)
FIXED_PRELIMINARY_LOCK_BUILD_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_adapter_v1",
    "build-preliminary-lock",
    "--output",
    FIXED_ADAPTER_REVIEW_LOCK_PATH,
    "--focused-test-passed",
    "--static-review-approved",
    "--build",
)
FIXED_FINAL_LOCK_BUILD_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_adapter_v1",
    "build-final-lock",
    "--output",
    FIXED_FINAL_RELEASE_LOCK_PATH,
    "--static-review-approved",
    "--publication-approved",
    "--build",
)
FIXED_PROJECTION_RELEASE_COMMAND: Final = (
    ".venv/bin/python",
    "-m",
    "nfl_dfs.research.corpus_r6_player_catalog_fixed_g0_adapter_v1",
    "publish-projection",
    "--execute",
)
REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]
PRODUCTION_PROJECT: Final = "nfl-predictions-503414"
PRODUCTION_ENABLE_ENV: Final = "R6_FIXED_G0_ADAPTER_PRODUCTION_ENABLED"
FIXED_PANEL_ID: Final = (
    "v12:ef445e2b31a7756609b458753dc064318b58ea2912e9277071c08fd0d07392e0"
)
FIXED_PANEL_INDEX_SHA256: Final = (
    "479b65bb40fcab6ba6721431718c8e2e95fc0a28a4354f1e7b3b1e205c69b094"
)
FIXED_CATALOG_NAMESPACE: Final = (
    "gs://nfl-predictions-503414-corpus-source/research/source/"
    "20260826-r6-player-catalog-fixed-g0-v1/"
)
FIXED_RELEASE_ID: Final = "r6-player-catalog-fixed-g0-projection-v1"
REPLAY_RECEIPT_FILENAME: Final = "fixed-g0-replay-receipt.json"

FIXED_PANEL_IDENTITY: Final = MappingProxyType({
    "uri": (
        "gs://nfl-predictions-503414-corpus-parametric/research/"
        "corpus-parametric-research/panels/20260823-foundry-production-v12/"
        "foundry-v12-combined-panel-index-v1.json"
    ),
    "generation": "1787663639938214",
    "sha256": "4d41acd9277e525cd8521071b62390281c442d6324db1e3f5812bf59920c16f9",
    "bytes": 209279,
})
FIXED_LANE_TERMINAL_IDENTITIES: Final = (
    MappingProxyType({
        "uri": (
            "gs://nfl-predictions-503414-corpus-parametric/research/"
            "corpus-parametric-research/batches/"
            "20260823-corpus-parametric-production-batch-v12a/"
            "governance/batch-acceptance.json"
        ),
        "generation": "1787656756640443",
        "sha256": (
            "a0ed809dc6480c93c301e3022c4adcc173ef285b8673e76174cf81f43b5c4397"
        ),
        "bytes": 1316197,
    }),
    MappingProxyType({
        "uri": (
            "gs://nfl-predictions-503414-corpus-parametric/research/"
            "corpus-parametric-research/batches/"
            "20260823-corpus-parametric-production-batch-v12b/"
            "governance/batch-acceptance.json"
        ),
        "generation": "1787663188263409",
        "sha256": (
            "9823eaa9a51062a6a437af22d1f6a5e0444f080191dd7ab6aad37b46f32f1e53"
        ),
        "bytes": 1222287,
    }),
)
FIXED_LANE_COMPLETION_IDENTITIES: Final = (
    MappingProxyType({
        "uri": (
            "gs://nfl-predictions-503414-corpus-parametric/research/"
            "corpus-parametric-research/batches/"
            "20260823-corpus-parametric-production-batch-v12a/"
            "governance/batch-completion.json"
        ),
        "generation": "1787656753894822",
        "sha256": (
            "21ccdf2121c34883aad7441443af5f5c06a579422c15aa409c25eb7a3f91f503"
        ),
        "bytes": 22272,
    }),
    MappingProxyType({
        "uri": (
            "gs://nfl-predictions-503414-corpus-parametric/research/"
            "corpus-parametric-research/batches/"
            "20260823-corpus-parametric-production-batch-v12b/"
            "governance/batch-completion.json"
        ),
        "generation": "1787663184829090",
        "sha256": (
            "254502f5d3e7440e188283de744709183b719b23a7b4a2eab746c5f47ce8872f"
        ),
        "bytes": 20796,
    }),
)
FIXED_SOURCE_COMPLETION_IDENTITY: Final = MappingProxyType({
    "uri": (
        "gs://nfl-predictions-503414-corpus-source/research/source/"
        "20260821-corpus-artifact-source-authority-v3/source/"
        "artifact-source-authority-completion.json"
    ),
    "generation": "1787367915631771",
    "sha256": "2d3a97e524fb0f592f0c57ed67643a84281fc97203e348f01031e3c356bded6c",
    "bytes": 383554,
})
FIXED_LATER_SOURCE_IDENTITY: Final = MappingProxyType({
    "uri": (
        "gs://nfl-predictions-503414-corpus-source/research/source/"
        "20260821-corpus-artifact-source-authority-v3/source/"
        "later-source-freeze.json"
    ),
    "generation": "1787367678830738",
    "sha256": "c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a",
    "bytes": 4566802,
})

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
_WORLD_ROLES: Final = tuple(f"world_artifact_r{index}" for index in range(5))
_PARAMETER_SET_COUNT: Final = len(batch.PARAMETER_SET_ORDER)

_TASK_ACCEPTANCE_BODY_FIELDS: Final = frozenset({
    "schema_version",
    "accepted_at_utc",
    "transport_contract",
    "retrieval_task0_prerequisite_identity",
    "task_index",
    "task_sha256",
    "producer_close",
    "science_terminal",
    "task_result",
    "verifier_worker_completion",
    "independent_verification",
    "independent_verification_sha256",
    "verifier_terminal_execution",
    "terminal_governance_census",
    "evidence_object_count",
    "complete_evidence_receipt",
    "independent_verification_complete",
    "strict_verifier_terminal_success",
    "accepted",
    "partial_result",
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
    "task_acceptance_sha256",
})
_TASK_ACCEPTANCE_FALSE_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
)
_TASK_CARRIER_BODY_FIELDS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "batch_manifest_identity",
    "batch_id",
    "batch_manifest_sha256",
    "parameter_schema_sha256",
    "common_law_sha256",
    "task_index",
    "task_sha256",
    "slate_id",
    "world_artifact_receipts",
    "world_artifact_receipt_set_sha256",
    "artifact_source_authority_task_sha256",
    "code_source",
    "immutable_image",
    "source_receipts",
    "source_receipt_set_sha256",
    "later_source_freeze_manifest_sha256",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "effective_policy_inventory_identity",
    "effective_policy_inventory_sha256",
    "effective_policy_rule_universe_sha256",
    "effective_policy_inventory_source_set_sha256",
    "effective_policy_classified_input_projection_sha256",
    "world_schedule",
    "world_seed",
    "solver",
    "execution",
    "variant_results",
    "task_result_sha256",
})
_TASK_CARRIER_ARM_FIELDS: Final = frozenset({
    "ordinal",
    "parameter_set_id",
    "parameter_set_sha256",
    "effective_policy_receipt",
    "result_object",
})

_ADAPTER_REVIEW_FALSE_FIELDS: Final = tuple(catalog.FALSE_AUTHORITY_FIELDS)
_ADAPTER_REVIEW_LOCK_FIELDS: Final = frozenset({
    "schema_version",
    "evidence_source_commit_sha",
    "implementation_commit_sha",
    "implementation_measurements",
    "focused_test_command",
    "focused_test_invocation_count",
    "focused_test_first_failed_invocation_count",
    "focused_test_second_failed_invocation_count",
    "focused_test_final_corrective_invocation_count",
    "focused_test_total_invocation_count",
    "focused_test_total_invocation_count_max",
    "focused_test_passed",
    "first_failed_pytest_exit_code",
    "first_failed_failure_count",
    "first_failed_common_exception",
    "second_failed_pytest_exit_code",
    "second_failed_failure_count",
    "second_failed_exception_classes",
    "final_corrective_pytest_exit_code",
    "first_focused_test_failure_summary_file",
    "first_focused_test_correction_addendum_file",
    "second_focused_test_correction_file",
    "final_corrective_focused_test_output_file",
    "independent_static_review_passed",
    "p0_open_count",
    "p1_open_count",
    "p2_open_count",
    "current_clean_git_required",
    "review_scope",
    "task0_real_artifact_smoke_reviewed",
    "cloud_read_only_smoke_licensed",
    "local_tracked_smoke_receipt_create_once_licensed",
    "local_tracked_smoke_attempt_create_once_licensed",
    "projection_only_publication_reviewed",
    "full_projection_release_licensed",
    "gcs_mutation_licensed",
    "uses_realized_outcomes",
    *_ADAPTER_REVIEW_FALSE_FIELDS,
    "adapter_review_lock_sha256",
})
_IMPLEMENTATION_MEASUREMENT_FIELDS: Final = frozenset({
    "relative_path", "sha256", "bytes",
})
_ADAPTER_REVIEW_BINDING_FIELDS: Final = frozenset({
    "review_lock_commit_sha",
    "implementation_commit_sha",
    "review_lock_relative_path",
    "review_lock_file_sha256",
    "review_lock_file_bytes",
    "review_lock_internal_sha256",
    "implementation_measurements",
})
_TASK0_SMOKE_ATTEMPT_FALSE_FIELDS: Final = tuple(catalog.FALSE_AUTHORITY_FIELDS)
_TASK0_SMOKE_ATTEMPT_FIELDS: Final = frozenset({
    "schema_version",
    "command",
    "attempt_relative_path",
    "success_receipt_relative_path",
    "adapter_review_binding",
    "implementation_measurements",
    "invocation_count",
    "state",
    "preliminary_review_reopened_before_reservation",
    "reserved_before_cloud_contact",
    "cloud_read_performed",
    "cloud_mutation_executed",
    "gcs_publication_count",
    "local_attempt_marker_create_count",
    "full_projection_release_licensed",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_TASK0_SMOKE_ATTEMPT_FALSE_FIELDS,
    "task0_real_artifact_smoke_attempt_sha256",
})
_TASK0_SMOKE_RECOVERY_LOCK_FIELDS: Final = frozenset({
    "schema_version",
    "implementation_commit_sha",
    "implementation_measurements",
    "recovery_amendment_measurement",
    "v1_attempt_measurement",
    "v1_attempt_internal_sha256",
    "v1_review_binding",
    "v1_invocation_count",
    "v1_exit_before_gcs_client_construction",
    "v1_exit_before_cloud_read",
    "v1_failure_classification",
    "v1_cloud_read_count",
    "v1_cloud_mutation_count",
    "v1_gcs_publication_count",
    "v1_outcomes_read",
    "v1_success_receipt_absent",
    "v2_command",
    "v2_invocation_count_max",
    "lifetime_invocation_count_max",
    "third_invocation_allowed",
    "v2_marker_create_once_before_client",
    "v2_success_receipt_path",
    "independent_static_review_passed",
    "p0_open_count",
    "p1_open_count",
    "p2_open_count",
    "cloud_read_only_smoke_licensed",
    "gcs_mutation_licensed",
    "uses_realized_outcomes",
    *_TASK0_SMOKE_ATTEMPT_FALSE_FIELDS,
    "task0_smoke_recovery_review_lock_sha256",
})
_TASK0_SMOKE_ATTEMPT_V2_FIELDS: Final = frozenset({
    "schema_version",
    "command",
    "attempt_relative_path",
    "success_receipt_relative_path",
    "recovery_review_lock_file",
    "recovery_review_lock_internal_sha256",
    "v1_attempt_measurement",
    "v1_attempt_internal_sha256",
    "adapter_review_binding",
    "implementation_measurements",
    "v1_invocation_count",
    "v2_invocation_count",
    "lifetime_invocation_count",
    "state",
    "reserved_before_gcs_client_construction",
    "cloud_read_performed",
    "cloud_mutation_executed",
    "gcs_publication_count",
    "local_attempt_marker_create_count",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_TASK0_SMOKE_ATTEMPT_FALSE_FIELDS,
    "task0_real_artifact_smoke_attempt_v2_sha256",
})
_TASK0_SMOKE_FALSE_FIELDS: Final = tuple(catalog.FALSE_AUTHORITY_FIELDS)
_TASK0_SMOKE_RECEIPT_FIELDS: Final = frozenset({
    "schema_version",
    "command",
    "receipt_relative_path",
    "invocation_count",
    "passed",
    "evidence_source_commit_sha",
    "pin_set_sha256",
    "adapter_review_binding",
    "implementation_measurements",
    "task0_smoke_attempt_file",
    "task0_smoke_attempt_internal_sha256",
    "source_task_ordinals",
    "tracked_root_binding",
    "generation_pinned_input_identities",
    "generation_pinned_input_count",
    "task0_task_acceptance_identity",
    "task0_task_acceptance_sha256",
    "task0_carrier_identity",
    "task0_carrier_sha256",
    "task_acceptance_body_count",
    "task_acceptance_body_manifest_sha256",
    "carrier_body_count",
    "carrier_body_manifest_sha256",
    "task0_derivation_receipt",
    "task0_derivation_sha256",
    "task0_source_evidence_exact_reopened",
    "task0_derivation_validated",
    "gcs_read_performed",
    "gcs_mutation_executed",
    "gcs_publication_count",
    "local_tracked_receipt_create_count",
    "source_completion_artifact_bodies_reopened",
    "world_matrix_bodies_reopened",
    "result_object_bodies_reopened",
    "full_projection_release_licensed",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_TASK0_SMOKE_FALSE_FIELDS,
    "task0_real_artifact_smoke_sha256",
})
_FINAL_RELEASE_FALSE_FIELDS: Final = tuple(catalog.FALSE_AUTHORITY_FIELDS)
_FINAL_RELEASE_LOCK_FIELDS: Final = frozenset({
    "schema_version",
    "evidence_source_commit_sha",
    "implementation_commit_sha",
    "implementation_measurements",
    "preliminary_review_lock_commit_sha",
    "preliminary_review_lock_file",
    "preliminary_review_lock_internal_sha256",
    "task0_smoke_receipt_file",
    "task0_smoke_receipt_internal_sha256",
    "task0_smoke_attempt_file",
    "task0_smoke_attempt_internal_sha256",
    "task0_smoke_command",
    "task0_smoke_invocation_count",
    "task0_smoke_passed",
    "independent_static_review_passed",
    "p0_open_count",
    "p1_open_count",
    "p2_open_count",
    "current_clean_git_required",
    "required_source_task_count",
    "required_task_acceptance_body_reopen_count",
    "required_carrier_body_reopen_count",
    "projection_only_publication_reviewed",
    "projection_only_publication_licensed",
    "projection_release_command",
    "production_enable_environment_variable",
    "production_enable_environment_value",
    "gcs_create_once_required",
    "gcs_overwrite_licensed",
    "world_matrix_bodies_read",
    "result_object_bodies_read",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_FINAL_RELEASE_FALSE_FIELDS,
    "final_release_lock_sha256",
})

ReadTracked = Callable[[str, str], bytes]
ReloadGeneration = Callable[[str, str], Mapping[str, object]]
DownloadGeneration = Callable[[str, str], bytes]
ResolveCurrent = Callable[[str], Mapping[str, object]]
CreateIfAbsent = Callable[[str, bytes, int], Mapping[str, object]]


class CorpusR6FixedG0AdapterV1Error(ValueError):
    """Fixed-G0 replay or immutable transport failed closed."""


class ObjectNotFoundV1Error(LookupError):
    """Transport reports that no current generation exists for one URI."""


class ObjectAlreadyExistsV1Error(FileExistsError):
    """Atomic create lost a race to an existing immutable object."""


@dataclass(frozen=True, slots=True)
class GenerationTransportV1:
    """Injected generation-specific storage operations.

    A production implementation must map ``create_if_absent`` to an atomic
    absence precondition such as ``if_generation_match=0``.  The adapter
    always passes literal zero and never permits an overwrite path.
    """

    reload_generation: ReloadGeneration
    download_generation: DownloadGeneration
    resolve_current: ResolveCurrent
    create_if_absent: CreateIfAbsent


@dataclass(frozen=True, slots=True)
class ReplayPinsV1:
    """Closed immutable identities for one non-authoritative replay."""

    source_commit_sha: str
    g0_lock_path: str
    g0_lock_sha256: str
    g0_lock_bytes: int
    g0_lock_internal_sha256: str
    g0_lock_id: str
    catalog_module_path: str
    catalog_module_sha256: str
    catalog_module_bytes: int
    panel_id: str
    panel_index_sha256: str
    panel_identity: Mapping[str, object]
    lane_terminal_identities: Sequence[Mapping[str, object]]
    lane_completion_identities: Sequence[Mapping[str, object]]
    source_completion_identity: Mapping[str, object]
    later_source_identity: Mapping[str, object]
    catalog_namespace: str


@dataclass(frozen=True, slots=True)
class AdapterReviewBindingV1:
    """Exact tracked review evidence for these adapter and test bytes."""

    review_lock_commit_sha: str
    implementation_commit_sha: str
    review_lock_relative_path: str
    review_lock_file_sha256: str
    review_lock_file_bytes: int
    review_lock_internal_sha256: str
    implementation_measurements: Sequence[Mapping[str, object]]


@dataclass(frozen=True, slots=True)
class ReplayedProjectionInputsV1:
    """Derived structural projections; none grants source authority."""

    pin_set_sha256: str
    source_task_ordinals: tuple[int, ...]
    tracked_root_binding: Mapping[str, object]
    member_bindings: tuple[Mapping[str, object], ...]
    source_catalog_bindings: tuple[Mapping[str, object], ...]
    completion_bindings: tuple[Mapping[str, object], ...]
    structural_players: tuple[tuple[Mapping[str, object], ...], ...]
    derivation_code_identity: Mapping[str, object]
    catalog_namespace: str
    source_completion_internal_sha256: str
    later_source_internal_sha256: str
    official_publication_receipt_file: Mapping[str, object]
    official_publication_receipt_sha256: str
    adapter_review_binding: Mapping[str, object]
    task_acceptance_body_manifest_sha256: str
    carrier_body_manifest_sha256: str
    task_acceptance_body_count: int
    carrier_body_count: int
    task_evidence_bindings: tuple[Mapping[str, object], ...]
    lane_terminal_identities: tuple[Mapping[str, object], ...]
    lane_completion_identities: tuple[Mapping[str, object], ...]
    later_source_identity: Mapping[str, object]
    source_completion_identity: Mapping[str, object]


FIXED_PINS: Final = ReplayPinsV1(
    source_commit_sha=FIXED_SOURCE_COMMIT_SHA,
    g0_lock_path=FIXED_G0_LOCK_PATH,
    g0_lock_sha256=FIXED_G0_LOCK_FILE_SHA256,
    g0_lock_bytes=FIXED_G0_LOCK_FILE_BYTES,
    g0_lock_internal_sha256=FIXED_G0_LOCK_INTERNAL_SHA256,
    g0_lock_id=FIXED_G0_LOCK_ID,
    catalog_module_path=FIXED_CATALOG_MODULE_PATH,
    catalog_module_sha256=FIXED_CATALOG_MODULE_SHA256,
    catalog_module_bytes=FIXED_CATALOG_MODULE_BYTES,
    panel_id=FIXED_PANEL_ID,
    panel_index_sha256=FIXED_PANEL_INDEX_SHA256,
    panel_identity=FIXED_PANEL_IDENTITY,
    lane_terminal_identities=FIXED_LANE_TERMINAL_IDENTITIES,
    lane_completion_identities=FIXED_LANE_COMPLETION_IDENTITIES,
    source_completion_identity=FIXED_SOURCE_COMPLETION_IDENTITY,
    later_source_identity=FIXED_LATER_SOURCE_IDENTITY,
    catalog_namespace=FIXED_CATALOG_NAMESPACE,
)


def _fail(message: str) -> None:
    raise CorpusR6FixedG0AdapterV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FixedG0AdapterV1Error(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        _fail(f"{label} fields differ")


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{label} must be one nonempty canonical string")
    return value


def _sha(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _SHA256.fullmatch(result) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return result


def _commit(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _COMMIT.fullmatch(result) is None:
        _fail(f"{label} must be one lowercase full commit SHA")
    return result


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _parse_canonical_json(
    raw: object, *, label: str, allow_one_newline: bool = False,
) -> dict[str, object]:
    if type(raw) is not bytes:
        _fail(f"{label} must be exact bytes")
    retained = raw
    if allow_one_newline and retained.endswith(b"\n"):
        retained = retained[:-1]
    try:
        parsed = batch.parse_canonical_json_bytes(retained, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FixedG0AdapterV1Error(str(exc)) from exc
    return _mapping(parsed, label=label)


def _parse_transport_canonical_json(raw: object, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        _fail(f"{label} must be newline-canonical transport JSON")
    return _parse_canonical_json(raw, label=label, allow_one_newline=True)


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    unhashed = {key: item for key, item in value.items() if key != field}
    if retained != canonical_sha256(unhashed):
        _fail(f"{label} self-hash differs")
    return retained


def _validate_transport_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    unhashed = {key: item for key, item in value.items() if key != field}
    expected = sha256(canonical_json_bytes(unhashed) + b"\n").hexdigest()
    if retained != expected:
        _fail(f"{label} transport self-hash differs")
    return retained


def _normalized_identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return catalog.normalize_object_identity(value, label=label)
    except catalog.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6FixedG0AdapterV1Error(str(exc)) from exc


def _normalize_prefix(value: object) -> str:
    prefix = _string(value, label="catalog namespace")
    tail = prefix.removeprefix("gs://")
    bucket, separator, object_name = tail.partition("/")
    pieces = object_name.removesuffix("/").split("/")
    if (
        not prefix.startswith("gs://")
        or not bucket
        or not separator
        or not object_name
        or not prefix.endswith("/")
        or "//" in object_name
        or any(piece in {"", ".", ".."} for piece in pieces)
    ):
        _fail("catalog namespace must be one canonical GCS prefix")
    return prefix


def read_generation_exact_v1(
    identity: Mapping[str, object], *, transport: GenerationTransportV1,
) -> bytes:
    """Reload and download only the requested immutable generation."""
    expected = _normalized_identity(identity, label="generation-specific identity")
    try:
        reloaded = transport.reload_generation(
            str(expected["uri"]), str(expected["generation"])
        )
    except Exception as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            "generation-specific reload failed"
        ) from exc
    observed = _normalized_identity(reloaded, label="reloaded object identity")
    if observed != expected:
        _fail("generation-specific reload returned a different identity")
    try:
        raw = transport.download_generation(
            str(expected["uri"]), str(expected["generation"])
        )
    except Exception as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            "generation-specific download failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != expected["bytes"]
        or sha256(raw).hexdigest() != expected["sha256"]
    ):
        _fail("generation-specific bytes differ from their exact identity")
    return raw


def publish_create_once_resumable_v1(
    uri: str,
    raw: bytes,
    *,
    transport: GenerationTransportV1,
) -> dict[str, object]:
    """Create once, accepting an occupied URI only when bytes are identical."""
    retained_uri = _string(uri, label="create-once URI")
    if not retained_uri.startswith("gs://") or retained_uri.endswith("/"):
        _fail("create-once URI must name one GCS object")
    if type(raw) is not bytes or not raw:
        _fail("create-once body must be nonempty bytes")

    try:
        current = transport.resolve_current(retained_uri)
    except ObjectNotFoundV1Error:
        current = None
    except Exception as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            "create-once current-generation resolution failed"
        ) from exc
    if current is not None:
        identity = _normalized_identity(current, label="occupied object identity")
        if identity["uri"] != retained_uri:
            _fail("occupied object resolver returned a different URI")
        if read_generation_exact_v1(identity, transport=transport) != raw:
            _fail("occupied create-once object has different bytes")
        return identity

    try:
        created = transport.create_if_absent(retained_uri, raw, 0)
    except ObjectAlreadyExistsV1Error:
        try:
            winner = transport.resolve_current(retained_uri)
        except Exception as exc:
            raise CorpusR6FixedG0AdapterV1Error(
                "create-once collision winner could not be resolved"
            ) from exc
        identity = _normalized_identity(winner, label="collision winner identity")
        if identity["uri"] != retained_uri:
            _fail("create-once collision winner returned a different URI")
        if read_generation_exact_v1(identity, transport=transport) != raw:
            _fail("create-once collision winner has different bytes")
        return identity
    except Exception as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            "atomic create-if-absent failed"
        ) from exc

    identity = _normalized_identity(created, label="created object identity")
    if identity["uri"] != retained_uri:
        _fail("create-if-absent returned a different URI")
    if read_generation_exact_v1(identity, transport=transport) != raw:
        _fail("new create-once object differs after exact reopen")
    return identity


_FILE_BINDING_FIELDS: Final = frozenset({"relative_path", "sha256", "bytes"})
_G0_LANE_FIELDS: Final = frozenset({
    "lane_ordinal",
    "lane_id",
    "terminal_receipt_file",
    "terminal_receipt_identity",
})
_G0_FALSE_FIELDS: Final = (
    "analytical_authority",
    "automatic_retry_licensed",
    "corpus_fill_licensed",
    "decision_authority",
    "graph_mutation_licensed",
    "historical_scoring_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "promotion_authority",
    "r6_freeze_authority",
    "uses_realized_outcomes",
)
_G0_FIELDS: Final = frozenset({
    "schema_version",
    "lock_id",
    "official_publication_receipt_file",
    "publication_receipt_sha256",
    "lane_terminal_receipts",
    "ordered_terminal_receipt_identities_sha256",
    "panel_uri",
    "panel_object_identity",
    "panel_id",
    "panel_index_sha256",
    "accepted_slate_count",
    "review_and_git_commit_required_before_prepare",
    *_G0_FALSE_FIELDS,
    "g0_authority_lock_sha256",
})
_PUBLICATION_FALSE_FIELDS: Final = (
    "analytical_authority",
    "automatic_retry_licensed",
    "corpus_fill_licensed",
    "decision_authority",
    "graph_mutation_licensed",
    "historical_scoring_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "promotion_authority",
    "uses_realized_outcomes",
)
_PUBLICATION_FIELDS: Final = frozenset({
    "schema_version",
    "mode",
    "panel_uri",
    "panel_object_identity",
    "panel_content_sha256",
    "panel_content_bytes",
    "panel_id",
    "panel_index_sha256",
    "lane_count",
    "accepted_slate_count",
    "published",
    "exact_input_replay_verified",
    *_PUBLICATION_FALSE_FIELDS,
    "publication_receipt_sha256",
})
_LOCAL_LANE_FIELDS: Final = frozenset({
    "schema_version",
    "batch_mode",
    "task_count",
    "matrix_cell_count",
    "batch_completion",
    "batch_acceptance",
    "final_output_inventory_sha256",
    "final_output_object_count",
    "complete",
    "accepted",
})
_PANEL_FALSE_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
)
_PANEL_FIELDS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "panel_id",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "lane_count",
    "lanes",
    "accepted_slate_count",
    "accepted_slates",
    "exclusions",
    "failures",
    "missing_tasks",
    "coverage",
    *_PANEL_FALSE_FIELDS,
    "panel_index_sha256",
})
_PANEL_LANE_FIELDS: Final = frozenset({
    "lane_ordinal",
    "lane_id",
    "terminal_receipt_identity",
    "batch_completion_identity",
    "batch_id",
    "batch_mode",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "source_task_offset",
    "expected_task_count",
    "accepted_task_count",
    "accepted_task_ordinals",
    "task_acceptance_identities_sha256",
    "carrier_identities_sha256",
    "complete",
})
_PANEL_MEMBER_FIELDS: Final = frozenset({
    "slate_id",
    "lane_ordinal",
    "lane_id",
    "task_ordinal",
    "source_task_ordinal",
    "source_task_authority_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "arms",
})
_PANEL_ARM_FIELDS: Final = frozenset({
    "arm_ordinal", "parameter_set_id", "result_identity",
})
_PANEL_COVERAGE_FIELDS: Final = frozenset({
    "expected_task_count",
    "accepted_task_count",
    "excluded_task_count",
    "failed_task_count",
    "missing_task_count",
    "complete",
})
_LANE_TERMINAL_FALSE_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
)
_LANE_TERMINAL_FIELDS: Final = frozenset({
    "schema_version",
    "accepted_at_utc",
    "transport_contract",
    "retrieval_task0_prerequisite_identity",
    "batch_mode",
    "batch_completion",
    "task_acceptances",
    "task_count",
    "parameter_set_count",
    "matrix_cell_count",
    "output_inventory_before_batch_acceptance",
    "output_inventory_before_batch_acceptance_sha256",
    "output_object_count_before_batch_acceptance",
    "complete",
    "accepted",
    "partial_result",
    "independent_verification_complete_for_every_task",
    *_LANE_TERMINAL_FALSE_FIELDS,
    "batch_acceptance_sha256",
})
_BATCH_COMPLETION_FIELDS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "batch_manifest_identity",
    "batch_id",
    "batch_manifest_sha256",
    "parameter_schema_sha256",
    "common_law_sha256",
    "later_source_freeze_manifest_sha256",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "effective_policy_classified_input_projection_sha256",
    "coverage",
    "task_results",
    "batch_completion_sha256",
})
_BATCH_COVERAGE_FIELDS: Final = frozenset({
    "task_count", "parameter_set_count", "matrix_cell_count", "complete",
})
_BATCH_TASK_FIELDS: Final = frozenset({
    "task_index",
    "task_sha256",
    "artifact_source_authority_task_sha256",
    "world_artifact_receipt_set_sha256",
    "task_result_sha256",
    "task_result_object",
})
_SOURCE_COMPLETION_FALSE_FIELDS: Final = (
    "historical_scoring_licensed",
    "production_change_licensed",
    "live_strategy_authority",
)
_SOURCE_COMPLETION_FIELDS: Final = frozenset({
    "schema",
    "authority_scope",
    "registration_object",
    "registration_sha256",
    "later_source_freeze_object",
    "later_source_freeze_manifest_sha256",
    "salary_diagnostic_object",
    "salary_diagnostic_sha256",
    "task_count",
    "world_blocks",
    "worlds_per_block",
    "artifact_count",
    "artifact_stream_order",
    "artifact_receipt_manifest_sha256",
    "artifact_validation_manifest_sha256",
    "tasks",
    "task_manifest_sha256",
    "salary_coverage_summary",
    "artifact_supported_universe_complete",
    "complete_dk_salary_coverage_claimed",
    "complete_dk_salary_universe_claimed",
    "salary_coverage_is_predeclared_query_relative",
    "salary_query_result_independently_verified",
    "salary_only_players_have_world_draws",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_SOURCE_COMPLETION_FALSE_FIELDS,
    "completion_sha256",
})
_SOURCE_TASK_FIELDS: Final = frozenset({
    "task_index",
    "season",
    "week",
    "slate_id",
    "universe_scope",
    "registration_sha256",
    "later_source_freeze_manifest_sha256",
    "salary_diagnostic_sha256",
    "catalog_sha256",
    "catalog_player_count",
    "catalog_player_ids_sha256",
    "incumbent_candidates_sha256",
    "world_artifact_receipts",
    "world_artifact_receipt_set_sha256",
    "world_artifact_validations",
    "world_artifact_validation_set_sha256",
    "salary_coverage",
    "complete_dk_salary_universe_claimed",
    "task_source_authority_sha256",
})
_LATER_SOURCE_FALSE_FIELDS: Final = (
    "uses_realized_outcomes",
    "candidate_or_lineup_scores_read",
    "b1_inputs_used",
    "a2a_inputs_used",
    "production_inputs_used",
    "historical_scoring_licensed",
    "production_change_licensed",
)
_LATER_SOURCE_FIELDS: Final = frozenset({
    "schema",
    "protocol_id",
    "runtime_identity",
    "base_source_lock_sha256",
    "base_source_lock_object",
    "base_source_version",
    "base_source_run_id",
    "source_panels",
    "canonical_incumbent_panel",
    "seasons",
    "weeks",
    "slate_count",
    "artifact_count",
    "world_blocks",
    "worlds_per_block",
    "source_query",
    "slates",
    "repaired_2025_w1_r3_sha256",
    "hard_constraints",
    *_LATER_SOURCE_FALSE_FIELDS,
    "freeze_sha256",
})
_SOURCE_SLATE_FIELDS: Final = frozenset({
    "season",
    "week",
    "slate_id",
    "catalog",
    "catalog_sha256",
    "incumbent_candidates",
    "incumbent_candidates_sha256",
    "artifact_receipts",
    "artifact_receipts_sha256",
})
_SOURCE_QUERY_FIELDS: Final = frozenset({
    "candidate_table",
    "catalog_table",
    "source_snapshot_at",
    "candidate_query",
    "catalog_query",
    "selected_columns",
    "realized_columns_selected",
})
_QUERY_RECEIPT_FIELDS: Final = frozenset({
    "job_id",
    "location",
    "sql_sha256",
    "parameters_sha256",
    "created",
    "started",
    "ended",
    "total_bytes_processed",
    "cache_hit",
    "error_result",
})
_SOURCE_RUNTIME_FIELDS: Final = frozenset({"run_id", "code_sha", "image", "job"})
_SOURCE_ARTIFACT_FIELDS: Final = frozenset({
    "season",
    "week",
    "block",
    "panel_run_id",
    "candidate_rows",
    "uri",
    "generation",
    "sha256",
    "bytes",
    "updated",
})
_SALARY_COVERAGE_FIELDS: Final = frozenset({
    "salary_player_count",
    "salary_player_ids_sha256",
    "artifact_supported_player_count",
    "artifact_supported_player_ids_sha256",
    "artifact_supported_in_salary_count",
    "salary_only_player_count",
    "salary_only_player_ids_sha256",
    "artifact_only_player_count",
    "artifact_only_player_ids_sha256",
    "artifact_equals_salary_diagnostic",
    "salary_only_players_have_world_draws",
    "coverage_is_predeclared_query_relative",
    "query_result_independently_verified",
    "complete_dk_salary_coverage_claimed",
})
_COVERAGE_SUMMARY_FIELDS: Final = frozenset({
    "task_count",
    "exact_match_task_count",
    "artifact_player_slate_count",
    "salary_player_slate_count",
    "salary_only_player_slate_count",
    "coverage_numerator_artifact_player_slates",
    "coverage_denominator_salary_player_slates",
    "diagnostic_required",
    "diagnostic_grants_world_draws",
    "coverage_is_predeclared_query_relative",
    "query_result_independently_verified",
    "complete_dk_salary_coverage_claimed",
})
_ARTIFACT_VALIDATION_FIELDS: Final = frozenset({
    "artifact_ordinal",
    "role",
    "object",
    "candidate_rows",
    "player_count",
    "ordered_player_ids_sha256",
    "player_set_sha256",
    "npz_fields",
    "player_draws_dtype",
    "player_draws_shape",
    "world_count",
    "player_set_matches_catalog",
    "uses_realized_outcomes",
})
_REPLAY_FALSE_FIELDS: Final = (
    *catalog.FALSE_AUTHORITY_FIELDS,
    "analytical_authority",
    "automatic_retry_licensed",
)
_REPLAY_RECEIPT_FIELDS: Final = frozenset({
    "schema_version",
    "replay_id",
    "replay_scope",
    "pin_set_sha256",
    "tracked_root_binding",
    "official_publication_receipt_file",
    "official_publication_receipt_sha256",
    "adapter_review_binding",
    "lane_terminal_identities",
    "lane_completion_identities",
    "later_source_freeze_identity",
    "later_source_freeze_manifest_sha256",
    "artifact_source_authority_completion_identity",
    "artifact_source_authority_completion_sha256",
    "derivation_code_identity",
    "catalog_namespace",
    "catalog_release_identity",
    "catalog_release_sha256",
    "task_count",
    "task_acceptance_body_count",
    "task_acceptance_body_manifest_sha256",
    "carrier_body_count",
    "carrier_body_manifest_sha256",
    "member_binding_manifest_sha256",
    "source_catalog_binding_manifest_sha256",
    "completion_binding_manifest_sha256",
    "structural_catalog_manifest_sha256",
    "catalog_identity_manifest_sha256",
    "accepted_panel_index_projection_only",
    "fresh_task_or_arm_body_revalidation_performed",
    "task_acceptance_bodies_reopened",
    "carrier_bodies_reopened",
    "source_completion_artifact_bodies_reopened",
    "world_matrix_bodies_reopened",
    "result_object_bodies_reopened",
    "execution_manifest_pin_required",
    "self_authorizing",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_REPLAY_FALSE_FIELDS,
    "replay_receipt_sha256",
})


def _normalize_file_binding(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, _FILE_BINDING_FIELDS, label=label)
    path = _string(item["relative_path"], label=f"{label}.relative_path")
    if path.startswith("/") or any(
        part in {"", ".", ".."} for part in path.split("/")
    ):
        _fail(f"{label}.relative_path differs")
    return {
        "relative_path": path,
        "sha256": _sha(item["sha256"], label=f"{label}.sha256"),
        "bytes": _exact_int(item["bytes"], label=f"{label}.bytes", minimum=1),
    }


def _require_fixed_catalog_runtime_measurement_v1(
    measurements: Sequence[Mapping[str, object]],
) -> None:
    by_path = {str(row["relative_path"]): row for row in measurements}
    catalog_measurement = by_path.get(FIXED_CATALOG_MODULE_PATH)
    if (
        catalog_measurement is None
        or catalog_measurement["sha256"] != FIXED_CATALOG_MODULE_SHA256
        or catalog_measurement["bytes"] != FIXED_CATALOG_MODULE_BYTES
        or FIXED_BATCH_MODULE_PATH not in by_path
    ):
        _fail("reviewed runtime dependency measurements differ")


def _normalize_adapter_review_binding(
    value: AdapterReviewBindingV1,
) -> dict[str, object]:
    if not isinstance(value, AdapterReviewBindingV1):
        _fail("adapter review binding must use AdapterReviewBindingV1")
    measurements = [
        _normalize_file_binding(row, label=f"adapter measurement[{ordinal}]")
        for ordinal, row in enumerate(value.implementation_measurements)
    ]
    if [row["relative_path"] for row in measurements] != list(
        FIXED_ADAPTER_IMPLEMENTATION_PATHS
    ):
        _fail("adapter review implementation paths differ")
    lock_path = _string(
        value.review_lock_relative_path, label="adapter review lock path"
    )
    if lock_path != FIXED_ADAPTER_REVIEW_LOCK_PATH:
        _fail("adapter review lock path differs")
    return {
        "review_lock_commit_sha": _commit(
            value.review_lock_commit_sha,
            label="adapter review lock commit",
        ),
        "implementation_commit_sha": _commit(
            value.implementation_commit_sha,
            label="adapter implementation commit",
        ),
        "review_lock_relative_path": lock_path,
        "review_lock_file_sha256": _sha(
            value.review_lock_file_sha256,
            label="adapter review lock file SHA",
        ),
        "review_lock_file_bytes": _exact_int(
            value.review_lock_file_bytes,
            label="adapter review lock file bytes",
            minimum=1,
        ),
        "review_lock_internal_sha256": _sha(
            value.review_lock_internal_sha256,
            label="adapter review lock internal SHA",
        ),
        "implementation_measurements": measurements,
    }


def _normalize_embedded_adapter_review_binding_v1(
    value: object,
) -> dict[str, object]:
    item = _mapping(value, label="embedded adapter review binding")
    _exact_keys(
        item,
        _ADAPTER_REVIEW_BINDING_FIELDS,
        label="embedded adapter review binding",
    )
    return _normalize_adapter_review_binding(AdapterReviewBindingV1(
        review_lock_commit_sha=_commit(
            item["review_lock_commit_sha"], label="embedded review-lock commit"
        ),
        implementation_commit_sha=_commit(
            item["implementation_commit_sha"],
            label="embedded implementation commit",
        ),
        review_lock_relative_path=_string(
            item["review_lock_relative_path"],
            label="embedded review-lock path",
        ),
        review_lock_file_sha256=_sha(
            item["review_lock_file_sha256"],
            label="embedded review-lock file SHA",
        ),
        review_lock_file_bytes=_exact_int(
            item["review_lock_file_bytes"],
            label="embedded review-lock file bytes",
            minimum=1,
        ),
        review_lock_internal_sha256=_sha(
            item["review_lock_internal_sha256"],
            label="embedded review-lock internal SHA",
        ),
        implementation_measurements=tuple(
            _sequence(
                item["implementation_measurements"],
                label="embedded implementation measurements",
            )
        ),
    ))


def _normalize_pins(pins: ReplayPinsV1) -> dict[str, object]:
    if not isinstance(pins, ReplayPinsV1):
        _fail("replay pins must use ReplayPinsV1")
    lane_terminals = [
        _normalized_identity(value, label=f"pinned lane terminal[{ordinal}]")
        for ordinal, value in enumerate(pins.lane_terminal_identities)
    ]
    lane_completions = [
        _normalized_identity(value, label=f"pinned lane completion[{ordinal}]")
        for ordinal, value in enumerate(pins.lane_completion_identities)
    ]
    if len(lane_terminals) != 2 or len(lane_completions) != 2:
        _fail("fixed replay requires exactly two lane identities")
    result = {
        "source_commit_sha": _commit(
            pins.source_commit_sha, label="pinned source commit"
        ),
        "g0_lock_path": _string(pins.g0_lock_path, label="pinned G0 lock path"),
        "g0_lock_sha256": _sha(
            pins.g0_lock_sha256, label="pinned G0 lock file SHA"
        ),
        "g0_lock_bytes": _exact_int(
            pins.g0_lock_bytes, label="pinned G0 lock bytes", minimum=1
        ),
        "g0_lock_internal_sha256": _sha(
            pins.g0_lock_internal_sha256, label="pinned G0 internal SHA"
        ),
        "g0_lock_id": _string(pins.g0_lock_id, label="pinned G0 lock ID"),
        "catalog_module_path": _string(
            pins.catalog_module_path, label="pinned catalog module path"
        ),
        "catalog_module_sha256": _sha(
            pins.catalog_module_sha256, label="pinned catalog module SHA"
        ),
        "catalog_module_bytes": _exact_int(
            pins.catalog_module_bytes,
            label="pinned catalog module bytes",
            minimum=1,
        ),
        "panel_id": _string(pins.panel_id, label="pinned panel ID"),
        "panel_index_sha256": _sha(
            pins.panel_index_sha256, label="pinned panel-index SHA"
        ),
        "panel_identity": _normalized_identity(
            pins.panel_identity, label="pinned panel identity"
        ),
        "lane_terminal_identities": lane_terminals,
        "lane_completion_identities": lane_completions,
        "source_completion_identity": _normalized_identity(
            pins.source_completion_identity,
            label="pinned source-completion identity",
        ),
        "later_source_identity": _normalized_identity(
            pins.later_source_identity, label="pinned later-source identity"
        ),
        "catalog_namespace": _normalize_prefix(pins.catalog_namespace),
    }
    if len({
        str(result["panel_identity"]["uri"]),
        *(str(value["uri"]) for value in lane_terminals),
        *(str(value["uri"]) for value in lane_completions),
        str(result["source_completion_identity"]["uri"]),
        str(result["later_source_identity"]["uri"]),
    }) != 7:
        _fail("pinned semantic object URIs overlap")
    return result


def _read_tracked_exact(
    *,
    commit: str,
    path: str,
    expected_sha256: str,
    expected_bytes: int,
    read_tracked: ReadTracked,
    label: str,
) -> bytes:
    try:
        raw = read_tracked(commit, path)
    except Exception as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            f"{label} committed read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != expected_bytes
        or sha256(raw).hexdigest() != expected_sha256
    ):
        _fail(f"{label} differs from its pinned committed bytes")
    return raw


def build_preliminary_adapter_review_lock_v1(
    *,
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    first_focused_test_failure_summary_file: Mapping[str, object],
    first_focused_test_correction_addendum_file: Mapping[str, object],
    second_focused_test_correction_file: Mapping[str, object],
    final_corrective_focused_test_output_file: Mapping[str, object],
    focused_test_passed: bool,
    independent_static_review_passed: bool,
) -> dict[str, object]:
    """Build the one exact smoke-only preliminary lock without performing I/O."""
    implementation_commit = _commit(
        implementation_commit_sha, label="preliminary implementation commit"
    )
    measurements = [
        _normalize_file_binding(row, label=f"preliminary implementation[{ordinal}]")
        for ordinal, row in enumerate(implementation_measurements)
    ]
    if [row["relative_path"] for row in measurements] != list(
        FIXED_ADAPTER_IMPLEMENTATION_PATHS
    ):
        _fail("preliminary implementation measurement order differs")
    _require_fixed_catalog_runtime_measurement_v1(measurements)
    failure_summary = _normalize_file_binding(
        first_focused_test_failure_summary_file,
        label="first focused-test failure summary",
    )
    correction_addendum = _normalize_file_binding(
        first_focused_test_correction_addendum_file,
        label="first focused-test correction addendum",
    )
    second_correction = _normalize_file_binding(
        second_focused_test_correction_file,
        label="second focused-test correction",
    )
    final_corrective_output = _normalize_file_binding(
        final_corrective_focused_test_output_file,
        label="final corrective focused-test output",
    )
    if (
        failure_summary["relative_path"]
        != FIXED_FOCUSED_TEST_FAILURE_SUMMARY_PATH
        or correction_addendum["relative_path"]
        != FIXED_FOCUSED_TEST_CORRECTION_ADDENDUM_PATH
        or second_correction["relative_path"]
        != FIXED_SECOND_FOCUSED_TEST_CORRECTION_PATH
        or final_corrective_output["relative_path"]
        != FIXED_FINAL_CORRECTIVE_FOCUSED_TEST_OUTPUT_PATH
    ):
        _fail("focused-test correction evidence paths differ")
    if focused_test_passed is not True:
        _fail("one focused test pass is required for the preliminary lock")
    if independent_static_review_passed is not True:
        _fail("static approval is required for the preliminary lock")
    body: dict[str, object] = {
        "schema_version": ADAPTER_REVIEW_LOCK_SCHEMA,
        "evidence_source_commit_sha": FIXED_SOURCE_COMMIT_SHA,
        "implementation_commit_sha": implementation_commit,
        "implementation_measurements": measurements,
        "focused_test_command": list(FIXED_FOCUSED_TEST_COMMAND),
        "focused_test_invocation_count": 3,
        "focused_test_first_failed_invocation_count": 1,
        "focused_test_second_failed_invocation_count": 1,
        "focused_test_final_corrective_invocation_count": 1,
        "focused_test_total_invocation_count": 3,
        "focused_test_total_invocation_count_max": 3,
        "focused_test_passed": True,
        "first_failed_pytest_exit_code": 1,
        "first_failed_failure_count": 27,
        "first_failed_common_exception": (
            "CorpusR6FixedG0AdapterV1Error: task evidence[0] carrier differs"
        ),
        "second_failed_pytest_exit_code": 1,
        "second_failed_failure_count": 13,
        "second_failed_exception_classes": [
            "task-0 real-artifact smoke receipt differs",
            "fixed-G0 fixture pin mismatch before intended boundary",
        ],
        "final_corrective_pytest_exit_code": 0,
        "first_focused_test_failure_summary_file": failure_summary,
        "first_focused_test_correction_addendum_file": correction_addendum,
        "second_focused_test_correction_file": second_correction,
        "final_corrective_focused_test_output_file": final_corrective_output,
        "independent_static_review_passed": True,
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "current_clean_git_required": True,
        "review_scope": "read-only-task0-real-artifact-smoke-only",
        "task0_real_artifact_smoke_reviewed": True,
        "cloud_read_only_smoke_licensed": True,
        "local_tracked_smoke_receipt_create_once_licensed": True,
        "local_tracked_smoke_attempt_create_once_licensed": True,
        "projection_only_publication_reviewed": False,
        "full_projection_release_licensed": False,
        "gcs_mutation_licensed": False,
        "uses_realized_outcomes": False,
        **{field: False for field in _ADAPTER_REVIEW_FALSE_FIELDS},
    }
    body["adapter_review_lock_sha256"] = canonical_sha256(body)
    return body


def validate_preliminary_adapter_review_lock_candidate_v1(
    value: object,
    *,
    expected_implementation_commit_sha: str,
    expected_implementation_measurements: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Purely replay one candidate against the deterministic lock builder."""
    item = _mapping(value, label="adapter review lock candidate")
    _exact_keys(
        item, _ADAPTER_REVIEW_LOCK_FIELDS, label="adapter review lock candidate"
    )
    _false_fields(
        item,
        _ADAPTER_REVIEW_FALSE_FIELDS,
        label="adapter review lock candidate",
    )
    _validate_self_hash(
        item,
        field="adapter_review_lock_sha256",
        label="adapter review lock candidate",
    )
    expected = build_preliminary_adapter_review_lock_v1(
        implementation_commit_sha=expected_implementation_commit_sha,
        implementation_measurements=expected_implementation_measurements,
        first_focused_test_failure_summary_file=_mapping(
            item["first_focused_test_failure_summary_file"],
            label="candidate first focused-test failure summary",
        ),
        first_focused_test_correction_addendum_file=_mapping(
            item["first_focused_test_correction_addendum_file"],
            label="candidate first focused-test correction addendum",
        ),
        second_focused_test_correction_file=_mapping(
            item["second_focused_test_correction_file"],
            label="candidate second focused-test correction",
        ),
        final_corrective_focused_test_output_file=_mapping(
            item["final_corrective_focused_test_output_file"],
            label="candidate final corrective focused-test output",
        ),
        focused_test_passed=True,
        independent_static_review_passed=True,
    )
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("adapter review lock candidate differs")
    return expected


def _validate_adapter_review_lock_v1(
    value: object,
    *,
    normalized_review: Mapping[str, object],
    read_tracked: ReadTracked,
) -> dict[str, object]:
    item = validate_preliminary_adapter_review_lock_candidate_v1(
        value,
        expected_implementation_commit_sha=str(
            normalized_review["implementation_commit_sha"]
        ),
        expected_implementation_measurements=_sequence(
            normalized_review["implementation_measurements"],
            label="reviewed implementation measurements",
        ),
    )
    rows = list(item["implementation_measurements"])
    if item["adapter_review_lock_sha256"] != (
        normalized_review["review_lock_internal_sha256"]
    ):
        _fail("adapter review lock identity differs")
    implementation_commit = str(normalized_review["implementation_commit_sha"])
    for ordinal, measurement in enumerate(rows):
        _read_tracked_exact(
            commit=implementation_commit,
            path=str(measurement["relative_path"]),
            expected_sha256=str(measurement["sha256"]),
            expected_bytes=int(measurement["bytes"]),
            read_tracked=read_tracked,
            label=f"reviewed adapter implementation[{ordinal}]",
        )
    for field, path, label in (
        (
            "first_focused_test_failure_summary_file",
            FIXED_FOCUSED_TEST_FAILURE_SUMMARY_PATH,
            "focused-test failure summary",
        ),
        (
            "first_focused_test_correction_addendum_file",
            FIXED_FOCUSED_TEST_CORRECTION_ADDENDUM_PATH,
            "focused-test correction addendum",
        ),
        (
            "second_focused_test_correction_file",
            FIXED_SECOND_FOCUSED_TEST_CORRECTION_PATH,
            "second focused-test correction",
        ),
        (
            "final_corrective_focused_test_output_file",
            FIXED_FINAL_CORRECTIVE_FOCUSED_TEST_OUTPUT_PATH,
            "final corrective focused-test output",
        ),
    ):
        binding = _normalize_file_binding(item[field], label=label)
        if binding["relative_path"] != path:
            _fail(f"{label} path differs")
        _read_tracked_exact(
            commit=implementation_commit,
            path=path,
            expected_sha256=str(binding["sha256"]),
            expected_bytes=int(binding["bytes"]),
            read_tracked=read_tracked,
            label=label,
        )
    return item


def _reopen_adapter_review_binding_v1(
    *,
    review: AdapterReviewBindingV1,
    read_tracked: ReadTracked,
) -> dict[str, object]:
    normalized = _normalize_adapter_review_binding(review)
    raw = _read_tracked_exact(
        commit=str(normalized["review_lock_commit_sha"]),
        path=str(normalized["review_lock_relative_path"]),
        expected_sha256=str(normalized["review_lock_file_sha256"]),
        expected_bytes=int(normalized["review_lock_file_bytes"]),
        read_tracked=read_tracked,
        label="tracked adapter review lock",
    )
    lock = _validate_adapter_review_lock_v1(
        _parse_canonical_json(
            raw, label="tracked adapter review lock", allow_one_newline=True
        ),
        normalized_review=normalized,
        read_tracked=read_tracked,
    )
    return {
        **normalized,
        "review_lock": lock,
    }


def _false_fields(
    value: Mapping[str, object], fields: Sequence[str], *, label: str,
) -> None:
    differing = [field for field in fields if value.get(field) is not False]
    if differing:
        _fail(f"{label} carries non-false authorities {differing}")


def _validate_g0_lock(
    value: object, *, normalized_pins: Mapping[str, object]
) -> dict[str, object]:
    item = _mapping(value, label="tracked G0 lock")
    _exact_keys(item, _G0_FIELDS, label="tracked G0 lock")
    _false_fields(item, _G0_FALSE_FIELDS, label="tracked G0 lock")
    internal = _validate_self_hash(
        item, field="g0_authority_lock_sha256", label="tracked G0 lock"
    )
    panel_identity = _normalized_identity(
        item["panel_object_identity"], label="G0 panel identity"
    )
    lane_rows = _sequence(
        item["lane_terminal_receipts"], label="G0 lane terminal receipts"
    )
    if len(lane_rows) != 2:
        _fail("tracked G0 lock must contain exactly two lanes")
    normalized_lanes: list[dict[str, object]] = []
    terminal_identities: list[dict[str, object]] = []
    for ordinal, raw_lane in enumerate(lane_rows):
        lane = _mapping(raw_lane, label=f"G0 lane[{ordinal}]")
        _exact_keys(lane, _G0_LANE_FIELDS, label=f"G0 lane[{ordinal}]")
        expected_lane = "v12a" if ordinal == 0 else "v12b"
        identity = _normalized_identity(
            lane["terminal_receipt_identity"],
            label=f"G0 lane[{ordinal}] terminal identity",
        )
        file_binding = _normalize_file_binding(
            lane["terminal_receipt_file"], label=f"G0 lane[{ordinal}] file"
        )
        if (
            lane["lane_ordinal"] != ordinal
            or lane["lane_id"] != expected_lane
            or identity
            != normalized_pins["lane_terminal_identities"][ordinal]
        ):
            _fail(f"tracked G0 lane[{ordinal}] differs from its fixed pin")
        normalized_lanes.append({
            "lane_ordinal": ordinal,
            "lane_id": expected_lane,
            "terminal_receipt_file": file_binding,
            "terminal_receipt_identity": identity,
        })
        terminal_identities.append(identity)
    official_file = _normalize_file_binding(
        item["official_publication_receipt_file"],
        label="G0 official publication receipt file",
    )
    if (
        item["schema_version"] != catalog.G0_AUTHORITY_LOCK_SCHEMA
        or item["lock_id"] != normalized_pins["g0_lock_id"]
        or internal != normalized_pins["g0_lock_internal_sha256"]
        or panel_identity != normalized_pins["panel_identity"]
        or item["panel_uri"] != panel_identity["uri"]
        or item["panel_id"] != normalized_pins["panel_id"]
        or item["panel_index_sha256"]
        != normalized_pins["panel_index_sha256"]
        or item["accepted_slate_count"] != catalog.TASK_COUNT
        or item["review_and_git_commit_required_before_prepare"] is not True
        or item["ordered_terminal_receipt_identities_sha256"]
        != canonical_sha256(terminal_identities)
    ):
        _fail("tracked G0 lock differs from the fixed replay surface")
    normalized = dict(item)
    normalized["official_publication_receipt_file"] = official_file
    normalized["lane_terminal_receipts"] = normalized_lanes
    normalized["panel_object_identity"] = panel_identity
    return normalized


def _validate_publication_receipt(
    value: object,
    *,
    normalized_pins: Mapping[str, object],
    lock: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="fixed panel publication receipt")
    _exact_keys(item, _PUBLICATION_FIELDS, label="fixed panel publication receipt")
    _false_fields(
        item, _PUBLICATION_FALSE_FIELDS, label="fixed panel publication receipt"
    )
    internal = _validate_self_hash(
        item,
        field="publication_receipt_sha256",
        label="fixed panel publication receipt",
    )
    panel_identity = _normalized_identity(
        item["panel_object_identity"], label="publication panel identity"
    )
    if (
        item["schema_version"] != "foundry-v12-panel-index-publication/v1"
        or item["mode"] != "create_once"
        or item["published"] is not True
        or item["exact_input_replay_verified"] is not True
        or panel_identity != normalized_pins["panel_identity"]
        or item["panel_uri"] != panel_identity["uri"]
        or item["panel_content_sha256"] != panel_identity["sha256"]
        or item["panel_content_bytes"] != panel_identity["bytes"]
        or item["panel_id"] != normalized_pins["panel_id"]
        or item["panel_index_sha256"]
        != normalized_pins["panel_index_sha256"]
        or item["lane_count"] != 2
        or item["accepted_slate_count"] != catalog.TASK_COUNT
        or internal != lock["publication_receipt_sha256"]
    ):
        _fail("fixed panel publication receipt differs")
    normalized = dict(item)
    normalized["panel_object_identity"] = panel_identity
    return normalized


def _validate_local_lane_envelope(
    value: object,
    *,
    ordinal: int,
    normalized_pins: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label=f"fixed local lane[{ordinal}] envelope")
    _exact_keys(
        item, _LOCAL_LANE_FIELDS, label=f"fixed local lane[{ordinal}] envelope"
    )
    expected_lane = catalog.expected_lane_for_source_task(0 if ordinal == 0 else 28)
    expected_count = 28 if ordinal == 0 else 26
    completion_identity = _normalized_identity(
        item["batch_completion"], label=f"local lane[{ordinal}] completion"
    )
    terminal_identity = _normalized_identity(
        item["batch_acceptance"], label=f"local lane[{ordinal}] acceptance"
    )
    if (
        item["schema_version"] != "corpus-parametric-batch-accepted/v1"
        or item["batch_mode"]
        != ("lane-a-28-task" if ordinal == 0 else "lane-b-26-task")
        or item["task_count"] != expected_count
        or item["matrix_cell_count"] != expected_count * _PARAMETER_SET_COUNT
        or item["complete"] is not True
        or item["accepted"] is not True
        or _SHA256.fullmatch(str(item["final_output_inventory_sha256"])) is None
        or type(item["final_output_object_count"]) is not int
        or item["final_output_object_count"] < 1
        or completion_identity
        != normalized_pins["lane_completion_identities"][ordinal]
        or terminal_identity
        != normalized_pins["lane_terminal_identities"][ordinal]
        or expected_lane["lane_ordinal"] != ordinal
    ):
        _fail(f"fixed local lane[{ordinal}] envelope differs")
    normalized = dict(item)
    normalized["batch_completion"] = completion_identity
    normalized["batch_acceptance"] = terminal_identity
    return normalized


def _validate_panel_arm(
    value: object, *, source_ordinal: int, arm_ordinal: int,
) -> dict[str, object]:
    item = _mapping(
        value, label=f"panel member[{source_ordinal}] arm[{arm_ordinal}]"
    )
    _exact_keys(
        item,
        _PANEL_ARM_FIELDS,
        label=f"panel member[{source_ordinal}] arm[{arm_ordinal}]",
    )
    identity = _normalized_identity(
        item["result_identity"],
        label=f"panel member[{source_ordinal}] arm[{arm_ordinal}] result",
    )
    if (
        item["arm_ordinal"] != arm_ordinal
        or item["parameter_set_id"] != batch.PARAMETER_SET_ORDER[arm_ordinal]
    ):
        _fail(f"panel member[{source_ordinal}] arm order differs")
    return {
        "arm_ordinal": arm_ordinal,
        "parameter_set_id": batch.PARAMETER_SET_ORDER[arm_ordinal],
        "result_identity": identity,
    }


def _validate_panel_member(
    value: object, *, source_ordinal: int,
) -> tuple[dict[str, object], dict[str, object]]:
    item = _mapping(value, label=f"panel member[{source_ordinal}]")
    _exact_keys(item, _PANEL_MEMBER_FIELDS, label=f"panel member[{source_ordinal}]")
    expected_lane = catalog.expected_lane_for_source_task(source_ordinal)
    expected_slate = catalog.expected_slate_for_source_task(source_ordinal)
    acceptance = _normalized_identity(
        item["task_acceptance_identity"],
        label=f"panel member[{source_ordinal}] acceptance",
    )
    carrier = _normalized_identity(
        item["carrier_identity"], label=f"panel member[{source_ordinal}] carrier"
    )
    arms_raw = _sequence(item["arms"], label=f"panel member[{source_ordinal}] arms")
    if len(arms_raw) != _PARAMETER_SET_COUNT:
        _fail(f"panel member[{source_ordinal}] arm count differs")
    arms = [
        _validate_panel_arm(
            raw_arm, source_ordinal=source_ordinal, arm_ordinal=arm_ordinal
        )
        for arm_ordinal, raw_arm in enumerate(arms_raw)
    ]
    if (
        item["source_task_ordinal"] != source_ordinal
        or item["slate_id"] != expected_slate["slate_id"]
        or item["lane_id"] != expected_lane["lane_id"]
        or item["lane_ordinal"] != expected_lane["lane_ordinal"]
        or item["task_ordinal"] != expected_lane["task_ordinal"]
    ):
        _fail(f"panel member[{source_ordinal}] frozen order differs")
    source_sha = _sha(
        item["source_task_authority_sha256"],
        label=f"panel member[{source_ordinal}] source authority SHA",
    )
    normalized_member = {
        "slate_id": expected_slate["slate_id"],
        **expected_lane,
        "source_task_ordinal": source_ordinal,
        "source_task_authority_sha256": source_sha,
        "task_acceptance_identity": acceptance,
        "carrier_identity": carrier,
        "arms": arms,
    }
    if canonical_json_bytes(normalized_member) != canonical_json_bytes(item):
        _fail(f"panel member[{source_ordinal}] canonical projection differs")
    binding = catalog.normalize_member_binding({
        "lane_id": expected_lane["lane_id"],
        "lane_ordinal": expected_lane["lane_ordinal"],
        "task_ordinal": expected_lane["task_ordinal"],
        "source_task_ordinal": source_ordinal,
        "task_id": catalog.task_id_for_source_task(source_ordinal),
        "slate_id": expected_slate["slate_id"],
        "accepted_slate_membership_sha256": canonical_sha256(item),
        "task_acceptance_identity": acceptance,
        "carrier_identity": carrier,
        "source_task_authority_sha256": source_sha,
    })
    return normalized_member, binding


def _validate_panel(
    value: object, *, normalized_pins: Mapping[str, object]
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Validate the panel-index projection without reopening task/arm bodies."""
    item = _mapping(value, label="fixed G0 panel")
    _exact_keys(item, _PANEL_FIELDS, label="fixed G0 panel")
    _false_fields(item, _PANEL_FALSE_FIELDS, label="fixed G0 panel")
    internal = _validate_self_hash(
        item, field="panel_index_sha256", label="fixed G0 panel"
    )
    completion_identity = _normalized_identity(
        item["artifact_source_authority_completion"],
        label="panel source-completion identity",
    )
    completion_internal = _sha(
        item["artifact_source_authority_completion_sha256"],
        label="panel source-completion internal SHA",
    )
    lane_values = _sequence(item["lanes"], label="fixed G0 panel lanes")
    member_values = _sequence(
        item["accepted_slates"], label="fixed G0 panel members"
    )
    if len(lane_values) != 2 or len(member_values) != catalog.TASK_COUNT:
        _fail("fixed G0 panel coverage differs")

    members: list[dict[str, object]] = []
    bindings: list[dict[str, object]] = []
    for source_ordinal, raw_member in enumerate(member_values):
        member, binding = _validate_panel_member(
            raw_member, source_ordinal=source_ordinal
        )
        members.append(member)
        bindings.append(binding)
    acceptance_keys = [
        canonical_sha256(member["task_acceptance_identity"])
        for member in members
    ]
    carrier_keys = [
        canonical_sha256(member["carrier_identity"]) for member in members
    ]
    arm_keys = [
        canonical_sha256(arm["result_identity"])
        for member in members
        for arm in member["arms"]
    ]
    if (
        len(set(acceptance_keys)) != catalog.TASK_COUNT
        or len(set(carrier_keys)) != catalog.TASK_COUNT
        or len(set(arm_keys)) != catalog.TASK_COUNT * _PARAMETER_SET_COUNT
    ):
        _fail("fixed panel member object identities repeat")

    lanes: list[dict[str, object]] = []
    for lane_ordinal, raw_lane in enumerate(lane_values):
        lane = _mapping(raw_lane, label=f"fixed panel lane[{lane_ordinal}]")
        _exact_keys(
            lane, _PANEL_LANE_FIELDS, label=f"fixed panel lane[{lane_ordinal}]"
        )
        lane_id = "v12a" if lane_ordinal == 0 else "v12b"
        batch_mode = (
            "lane-a-28-task" if lane_ordinal == 0 else "lane-b-26-task"
        )
        source_offset = 0 if lane_ordinal == 0 else 28
        expected_count = 28 if lane_ordinal == 0 else 26
        lane_members = members[source_offset:source_offset + expected_count]
        terminal = _normalized_identity(
            lane["terminal_receipt_identity"],
            label=f"panel lane[{lane_ordinal}] terminal",
        )
        completion = _normalized_identity(
            lane["batch_completion_identity"],
            label=f"panel lane[{lane_ordinal}] completion",
        )
        if (
            lane["lane_ordinal"] != lane_ordinal
            or lane["lane_id"] != lane_id
            or lane["batch_mode"] != batch_mode
            or lane["source_task_offset"] != source_offset
            or lane["expected_task_count"] != expected_count
            or lane["accepted_task_count"] != expected_count
            or lane["accepted_task_ordinals"] != list(range(expected_count))
            or lane["complete"] is not True
            or terminal
            != normalized_pins["lane_terminal_identities"][lane_ordinal]
            or completion
            != normalized_pins["lane_completion_identities"][lane_ordinal]
            or completion_identity
            != normalized_pins["source_completion_identity"]
            or lane["artifact_source_authority_completion"]
            != completion_identity
            or lane["artifact_source_authority_completion_sha256"]
            != completion_internal
            or lane["task_acceptance_identities_sha256"]
            != canonical_sha256([
                member["task_acceptance_identity"] for member in lane_members
            ])
            or lane["carrier_identities_sha256"]
            != canonical_sha256([
                member["carrier_identity"] for member in lane_members
            ])
        ):
            _fail(f"fixed panel lane[{lane_ordinal}] differs")
        normalized_lane = dict(lane)
        normalized_lane["terminal_receipt_identity"] = terminal
        normalized_lane["batch_completion_identity"] = completion
        normalized_lane["artifact_source_authority_completion"] = (
            completion_identity
        )
        lanes.append(normalized_lane)

    coverage = _mapping(item["coverage"], label="fixed panel coverage")
    _exact_keys(coverage, _PANEL_COVERAGE_FIELDS, label="fixed panel coverage")
    terminal_identities = [lane["terminal_receipt_identity"] for lane in lanes]
    if (
        item["schema_version"] != "foundry-v12-combined-panel-index/v1"
        or item["publication_mode"] != "create_once"
        or item["panel_id"] != normalized_pins["panel_id"]
        or item["panel_id"] != f"v12:{canonical_sha256(terminal_identities)}"
        or internal != normalized_pins["panel_index_sha256"]
        or item["lane_count"] != 2
        or item["accepted_slate_count"] != catalog.TASK_COUNT
        or item["exclusions"] != []
        or item["failures"] != []
        or item["missing_tasks"] != []
        or coverage != {
            "expected_task_count": catalog.TASK_COUNT,
            "accepted_task_count": catalog.TASK_COUNT,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        }
    ):
        _fail("fixed G0 panel identity/coverage differs")
    normalized = dict(item)
    normalized["artifact_source_authority_completion"] = completion_identity
    normalized["lanes"] = lanes
    normalized["accepted_slates"] = members
    normalized["coverage"] = coverage
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("fixed G0 panel canonical projection differs")
    return normalized, bindings, lanes


def _validate_lane_terminal(
    value: object,
    *,
    lane_ordinal: int,
    normalized_pins: Mapping[str, object],
    panel_lane: Mapping[str, object],
    panel_members: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    item = _mapping(value, label=f"fixed lane[{lane_ordinal}] terminal")
    _exact_keys(
        item,
        _LANE_TERMINAL_FIELDS,
        label=f"fixed lane[{lane_ordinal}] terminal",
    )
    _false_fields(
        item,
        _LANE_TERMINAL_FALSE_FIELDS,
        label=f"fixed lane[{lane_ordinal}] terminal",
    )
    _validate_transport_self_hash(
        item,
        field="batch_acceptance_sha256",
        label=f"fixed lane[{lane_ordinal}] terminal",
    )
    expected_count = 28 if lane_ordinal == 0 else 26
    expected_mode = "lane-a-28-task" if lane_ordinal == 0 else "lane-b-26-task"
    completion_identity = _normalized_identity(
        item["batch_completion"], label=f"lane[{lane_ordinal}] completion"
    )
    acceptances = [
        _normalized_identity(
            raw, label=f"lane[{lane_ordinal}] task acceptance[{ordinal}]"
        )
        for ordinal, raw in enumerate(
            _sequence(
                item["task_acceptances"],
                label=f"lane[{lane_ordinal}] task acceptances",
            )
        )
    ]
    expected_acceptances = [
        _mapping(member, label="panel member")["task_acceptance_identity"]
        for member in panel_members
    ]
    transport_contract = _normalized_identity(
        item["transport_contract"],
        label=f"lane[{lane_ordinal}] transport contract",
    )
    prerequisite = _normalized_identity(
        item["retrieval_task0_prerequisite_identity"],
        label=f"lane[{lane_ordinal}] prerequisite",
    )
    inventory = _sequence(
        item["output_inventory_before_batch_acceptance"],
        label=f"lane[{lane_ordinal}] output inventory",
    )
    normalized_inventory: list[dict[str, object]] = []
    prior_inventory_key: tuple[str, str] | None = None
    for inventory_ordinal, raw_row in enumerate(inventory):
        row = _mapping(
            raw_row,
            label=f"lane[{lane_ordinal}] inventory[{inventory_ordinal}]",
        )
        _exact_keys(
            row,
            frozenset({"uri", "generation", "bytes"}),
            label=f"lane[{lane_ordinal}] inventory[{inventory_ordinal}]",
        )
        uri = _string(row["uri"], label="inventory URI")
        generation = _string(row["generation"], label="inventory generation")
        size = _exact_int(row["bytes"], label="inventory bytes", minimum=1)
        key = (uri, generation)
        if (
            not uri.startswith("gs://")
            or not generation.isdigit()
            or generation.startswith("0")
            or (prior_inventory_key is not None and key <= prior_inventory_key)
        ):
            _fail(f"lane[{lane_ordinal}] output inventory order differs")
        prior_inventory_key = key
        normalized_inventory.append({
            "uri": uri, "generation": generation, "bytes": size,
        })
    required_inventory = [
        completion_identity,
        *acceptances,
        *(
            _mapping(member, label="panel member")["carrier_identity"]
            for member in panel_members
        ),
    ]
    inventory_keys = {
        (row["uri"], row["generation"], row["bytes"])
        for row in normalized_inventory
    }
    if (
        item["schema_version"] != "corpus-parametric-batch-acceptance/v1"
        or item["batch_mode"] != expected_mode
        or item["task_count"] != expected_count
        or item["parameter_set_count"] != _PARAMETER_SET_COUNT
        or item["matrix_cell_count"] != expected_count * _PARAMETER_SET_COUNT
        or item["complete"] is not True
        or item["accepted"] is not True
        or item["partial_result"] is not False
        or item["independent_verification_complete_for_every_task"] is not True
        or completion_identity
        != normalized_pins["lane_completion_identities"][lane_ordinal]
        or completion_identity != panel_lane["batch_completion_identity"]
        or acceptances != expected_acceptances
        or len(acceptances) != expected_count
        or len({canonical_sha256(identity) for identity in acceptances})
        != expected_count
        or transport_contract == prerequisite
        or item["output_object_count_before_batch_acceptance"]
        != len(normalized_inventory)
        or item["output_inventory_before_batch_acceptance_sha256"]
        != sha256(canonical_json_bytes(normalized_inventory) + b"\n").hexdigest()
        or any(
            (identity["uri"], identity["generation"], identity["bytes"])
            not in inventory_keys
            for identity in required_inventory
        )
    ):
        _fail(f"fixed lane[{lane_ordinal}] terminal differs")
    normalized = dict(item)
    normalized["transport_contract"] = transport_contract
    normalized["retrieval_task0_prerequisite_identity"] = prerequisite
    normalized["batch_completion"] = completion_identity
    normalized["task_acceptances"] = acceptances
    normalized["output_inventory_before_batch_acceptance"] = normalized_inventory
    return normalized


def _validate_batch_completion(
    value: object,
    *,
    lane_ordinal: int,
    normalized_pins: Mapping[str, object],
    panel_lane: Mapping[str, object],
    panel_members: Sequence[Mapping[str, object]],
    terminal: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label=f"fixed lane[{lane_ordinal}] completion")
    _exact_keys(
        item,
        _BATCH_COMPLETION_FIELDS,
        label=f"fixed lane[{lane_ordinal}] completion",
    )
    _validate_self_hash(
        item,
        field="batch_completion_sha256",
        label=f"fixed lane[{lane_ordinal}] completion",
    )
    coverage = _mapping(
        item["coverage"], label=f"fixed lane[{lane_ordinal}] completion coverage"
    )
    _exact_keys(
        coverage,
        _BATCH_COVERAGE_FIELDS,
        label=f"fixed lane[{lane_ordinal}] completion coverage",
    )
    expected_count = 28 if lane_ordinal == 0 else 26
    source_identity = _normalized_identity(
        item["artifact_source_authority_completion"],
        label=f"lane[{lane_ordinal}] source completion",
    )
    manifest_identity = _normalized_identity(
        item["batch_manifest_identity"],
        label=f"lane[{lane_ordinal}] batch manifest",
    )
    raw_results = _sequence(
        item["task_results"], label=f"fixed lane[{lane_ordinal}] completion tasks"
    )
    if len(raw_results) != expected_count:
        _fail(f"fixed lane[{lane_ordinal}] completion task coverage differs")
    results: list[dict[str, object]] = []
    for task_ordinal, raw_result in enumerate(raw_results):
        result = _mapping(
            raw_result,
            label=f"lane[{lane_ordinal}] completion task[{task_ordinal}]",
        )
        _exact_keys(
            result,
            _BATCH_TASK_FIELDS,
            label=f"lane[{lane_ordinal}] completion task[{task_ordinal}]",
        )
        carrier = _normalized_identity(
            result["task_result_object"],
            label=f"lane[{lane_ordinal}] task[{task_ordinal}] carrier",
        )
        member = _mapping(panel_members[task_ordinal], label="panel member")
        if (
            result["task_index"] != task_ordinal
            or carrier != member["carrier_identity"]
            or result["artifact_source_authority_task_sha256"]
            != member["source_task_authority_sha256"]
        ):
            _fail(
                f"lane[{lane_ordinal}] completion task[{task_ordinal}] differs"
            )
        for field in (
            "task_sha256",
            "artifact_source_authority_task_sha256",
            "world_artifact_receipt_set_sha256",
            "task_result_sha256",
        ):
            _sha(
                result[field],
                label=(
                    f"lane[{lane_ordinal}] completion task[{task_ordinal}].{field}"
                ),
            )
        normalized_result = dict(result)
        normalized_result["task_result_object"] = carrier
        results.append(normalized_result)
    if (
        item["schema_version"] != "corpus-parametric-batch-completion-v2"
        or item["publication_mode"] != "create_once"
        or coverage != {
            "task_count": expected_count,
            "parameter_set_count": _PARAMETER_SET_COUNT,
            "matrix_cell_count": expected_count * _PARAMETER_SET_COUNT,
            "complete": True,
        }
        or source_identity != normalized_pins["source_completion_identity"]
        or source_identity
        != panel_lane["artifact_source_authority_completion"]
        or item["artifact_source_authority_completion_sha256"]
        != panel_lane["artifact_source_authority_completion_sha256"]
        or terminal["batch_completion"]
        != normalized_pins["lane_completion_identities"][lane_ordinal]
        or item["batch_id"] != panel_lane["batch_id"]
    ):
        _fail(f"fixed lane[{lane_ordinal}] completion differs")
    for field in (
        "batch_manifest_sha256",
        "parameter_schema_sha256",
        "common_law_sha256",
        "later_source_freeze_manifest_sha256",
        "artifact_source_authority_completion_sha256",
        "effective_policy_classified_input_projection_sha256",
    ):
        _sha(item[field], label=f"lane[{lane_ordinal}] completion.{field}")
    normalized = dict(item)
    normalized["batch_manifest_identity"] = manifest_identity
    normalized["artifact_source_authority_completion"] = source_identity
    normalized["coverage"] = coverage
    normalized["task_results"] = results
    return normalized


def _reopen_task_acceptance_and_carrier_v1(
    *,
    source_ordinal: int,
    member: Mapping[str, object],
    terminal: Mapping[str, object],
    completion: Mapping[str, object],
    completion_task: Mapping[str, object],
    source_completion_task: Mapping[str, object],
    expected_world_identities: Sequence[Mapping[str, object]],
    normalized_pins: Mapping[str, object],
    transport: GenerationTransportV1,
) -> dict[str, object]:
    """Exact-reopen one accepted task's two small governance bodies only."""
    expected_lane = catalog.expected_lane_for_source_task(source_ordinal)
    expected_slate = catalog.expected_slate_for_source_task(source_ordinal)
    task_ordinal = int(expected_lane["task_ordinal"])
    acceptance_identity = _normalized_identity(
        member["task_acceptance_identity"],
        label=f"task evidence[{source_ordinal}] acceptance identity",
    )
    carrier_identity = _normalized_identity(
        member["carrier_identity"],
        label=f"task evidence[{source_ordinal}] carrier identity",
    )
    acceptance = _parse_transport_canonical_json(
        read_generation_exact_v1(acceptance_identity, transport=transport),
        label=f"task evidence[{source_ordinal}] acceptance",
    )
    _exact_keys(
        acceptance,
        _TASK_ACCEPTANCE_BODY_FIELDS,
        label=f"task evidence[{source_ordinal}] acceptance",
    )
    acceptance_internal = _validate_transport_self_hash(
        acceptance,
        field="task_acceptance_sha256",
        label=f"task evidence[{source_ordinal}] acceptance",
    )
    _false_fields(
        acceptance,
        _TASK_ACCEPTANCE_FALSE_FIELDS,
        label=f"task evidence[{source_ordinal}] acceptance",
    )
    for field in (
        "producer_close",
        "science_terminal",
        "task_result",
        "verifier_worker_completion",
        "independent_verification",
    ):
        _normalized_identity(
            acceptance[field],
            label=f"task evidence[{source_ordinal}] acceptance.{field}",
        )
    _mapping(
        acceptance["verifier_terminal_execution"],
        label=f"task evidence[{source_ordinal}] terminal execution",
    )
    _mapping(
        acceptance["terminal_governance_census"],
        label=f"task evidence[{source_ordinal}] terminal census",
    )
    if (
        acceptance["schema_version"] != "corpus-parametric-task-acceptance/v1"
        or not str(acceptance["accepted_at_utc"]).endswith("Z")
        or acceptance["transport_contract"] != terminal["transport_contract"]
        or acceptance["retrieval_task0_prerequisite_identity"]
        != terminal["retrieval_task0_prerequisite_identity"]
        or acceptance["task_index"] != task_ordinal
        or acceptance["task_sha256"] != completion_task["task_sha256"]
        or acceptance["task_result"] != carrier_identity
        or acceptance_identity != terminal["task_acceptances"][task_ordinal]
        or carrier_identity != completion_task["task_result_object"]
        or acceptance["evidence_object_count"] != 140
        or acceptance["complete_evidence_receipt"] is not True
        or acceptance["independent_verification_complete"] is not True
        or acceptance["strict_verifier_terminal_success"] is not True
        or acceptance["accepted"] is not True
        or acceptance["partial_result"] is not False
    ):
        _fail(f"task evidence[{source_ordinal}] acceptance differs")
    _sha(
        acceptance["independent_verification_sha256"],
        label=f"task evidence[{source_ordinal}] verification SHA",
    )

    carrier = _parse_canonical_json(
        read_generation_exact_v1(carrier_identity, transport=transport),
        label=f"task evidence[{source_ordinal}] carrier",
    )
    _exact_keys(
        carrier,
        _TASK_CARRIER_BODY_FIELDS,
        label=f"task evidence[{source_ordinal}] carrier",
    )
    carrier_internal = _validate_self_hash(
        carrier,
        field="task_result_sha256",
        label=f"task evidence[{source_ordinal}] carrier",
    )
    manifest_identity = _normalized_identity(
        carrier["batch_manifest_identity"],
        label=f"task evidence[{source_ordinal}] batch manifest",
    )
    source_completion_identity = _normalized_identity(
        carrier["artifact_source_authority_completion"],
        label=f"task evidence[{source_ordinal}] source completion",
    )
    _normalized_identity(
        carrier["effective_policy_inventory_identity"],
        label=f"task evidence[{source_ordinal}] policy inventory",
    )
    sources_raw = _mapping(
        carrier["source_receipts"],
        label=f"task evidence[{source_ordinal}] source receipts",
    )
    if set(sources_raw) != set(batch.SOURCE_RECEIPT_ROLES):
        _fail(f"task evidence[{source_ordinal}] source receipt roles differ")
    sources = {
        role: _normalized_identity(
            sources_raw[role],
            label=f"task evidence[{source_ordinal}] source receipt {role}",
        )
        for role in batch.SOURCE_RECEIPT_ROLES
    }
    worlds_raw = _mapping(
        carrier["world_artifact_receipts"],
        label=f"task evidence[{source_ordinal}] world receipts",
    )
    if set(worlds_raw) != set(batch.TASK_WORLD_SOURCE_ROLES):
        _fail(f"task evidence[{source_ordinal}] world receipt roles differ")
    worlds = {
        role: _normalized_identity(
            worlds_raw[role],
            label=f"task evidence[{source_ordinal}] world receipt {role}",
        )
        for role in batch.TASK_WORLD_SOURCE_ROLES
    }
    expected_worlds = {
        role: _normalized_identity(
            expected_world_identities[ordinal],
            label=f"task evidence[{source_ordinal}] expected world {role}",
        )
        for ordinal, role in enumerate(batch.TASK_WORLD_SOURCE_ROLES)
    }
    raw_arms = _sequence(
        carrier["variant_results"],
        label=f"task evidence[{source_ordinal}] carrier arms",
    )
    panel_arms = _sequence(
        member["arms"], label=f"task evidence[{source_ordinal}] panel arms"
    )
    if len(raw_arms) != _PARAMETER_SET_COUNT or len(panel_arms) != len(raw_arms):
        _fail(f"task evidence[{source_ordinal}] arm coverage differs")
    for arm_ordinal, (raw_arm, raw_panel_arm) in enumerate(
        zip(raw_arms, panel_arms, strict=True)
    ):
        arm = _mapping(
            raw_arm, label=f"task evidence[{source_ordinal}] arm[{arm_ordinal}]"
        )
        _exact_keys(
            arm,
            _TASK_CARRIER_ARM_FIELDS,
            label=f"task evidence[{source_ordinal}] arm[{arm_ordinal}]",
        )
        panel_arm = _mapping(raw_panel_arm, label="panel arm")
        result_identity = _normalized_identity(
            arm["result_object"],
            label=f"task evidence[{source_ordinal}] arm[{arm_ordinal}] result",
        )
        _normalized_identity(
            arm["effective_policy_receipt"],
            label=f"task evidence[{source_ordinal}] arm[{arm_ordinal}] policy",
        )
        if (
            arm["ordinal"] != arm_ordinal
            or arm["parameter_set_id"] != batch.PARAMETER_SET_ORDER[arm_ordinal]
            or panel_arm["arm_ordinal"] != arm_ordinal
            or panel_arm["parameter_set_id"]
            != batch.PARAMETER_SET_ORDER[arm_ordinal]
            or panel_arm["result_identity"] != result_identity
        ):
            _fail(f"task evidence[{source_ordinal}] arm binding differs")
        _sha(
            arm["parameter_set_sha256"],
            label=f"task evidence[{source_ordinal}] arm parameter SHA",
        )
    for field in (
        "batch_manifest_sha256",
        "parameter_schema_sha256",
        "common_law_sha256",
        "source_receipt_set_sha256",
        "later_source_freeze_manifest_sha256",
        "artifact_source_authority_completion_sha256",
        "effective_policy_inventory_sha256",
        "effective_policy_rule_universe_sha256",
        "effective_policy_inventory_source_set_sha256",
        "effective_policy_classified_input_projection_sha256",
    ):
        _sha(carrier[field], label=f"task evidence[{source_ordinal}].{field}")
    expected_world_set_sha256 = canonical_sha256(worlds)
    if worlds != expected_worlds:
        _fail(f"task evidence[{source_ordinal}] world identities differ")
    if (
        carrier["world_artifact_receipt_set_sha256"]
        != expected_world_set_sha256
        or completion_task["world_artifact_receipt_set_sha256"]
        != expected_world_set_sha256
    ):
        _fail(f"task evidence[{source_ordinal}] world receipt set hash differs")
    if (
        carrier["schema_version"] != batch.TASK_RESULT_SCHEMA
        or carrier["publication_mode"] != "create_once"
        or carrier["task_index"] != task_ordinal
        or carrier["slate_id"] != expected_slate["slate_id"]
        or carrier["task_sha256"] != completion_task["task_sha256"]
        or carrier_internal != completion_task["task_result_sha256"]
        or carrier["artifact_source_authority_task_sha256"]
        != source_completion_task["task_source_authority_sha256"]
        or carrier["artifact_source_authority_task_sha256"]
        != completion_task["artifact_source_authority_task_sha256"]
        or sources != {"later_source_freeze": normalized_pins["later_source_identity"]}
        or carrier["source_receipt_set_sha256"] != canonical_sha256(sources)
        or carrier["later_source_freeze_manifest_sha256"]
        != completion["later_source_freeze_manifest_sha256"]
        or source_completion_identity
        != normalized_pins["source_completion_identity"]
        or carrier["artifact_source_authority_completion_sha256"]
        != completion["artifact_source_authority_completion_sha256"]
        or manifest_identity != completion["batch_manifest_identity"]
        or carrier["batch_id"] != completion["batch_id"]
        or carrier["batch_manifest_sha256"] != completion["batch_manifest_sha256"]
        or carrier["parameter_schema_sha256"]
        != completion["parameter_schema_sha256"]
        or carrier["common_law_sha256"] != completion["common_law_sha256"]
        or carrier["effective_policy_classified_input_projection_sha256"]
        != completion["effective_policy_classified_input_projection_sha256"]
        or not isinstance(carrier["code_source"], Mapping)
        or not isinstance(carrier["immutable_image"], Mapping)
        or not isinstance(carrier["solver"], Mapping)
        or not isinstance(carrier["execution"], Mapping)
        or not isinstance(carrier["world_schedule"], Sequence)
        or isinstance(carrier["world_schedule"], (str, bytes))
        or type(carrier["world_seed"]) is not int
    ):
        _fail(f"task evidence[{source_ordinal}] carrier differs")
    return {
        "source_task_ordinal": source_ordinal,
        "task_acceptance_identity": acceptance_identity,
        "task_acceptance_sha256": acceptance_internal,
        "carrier_identity": carrier_identity,
        "carrier_sha256": carrier_internal,
    }


def _validate_source_artifact(
    value: object, *, source_ordinal: int, block_ordinal: int,
) -> tuple[dict[str, object], dict[str, object]]:
    item = _mapping(
        value, label=f"later-source slate[{source_ordinal}] artifact[{block_ordinal}]"
    )
    _exact_keys(
        item,
        _SOURCE_ARTIFACT_FIELDS,
        label=f"later-source slate[{source_ordinal}] artifact[{block_ordinal}]",
    )
    slate = catalog.expected_slate_for_source_task(source_ordinal)
    block = _WORLD_BLOCKS[block_ordinal]
    identity = _normalized_identity(
        {key: item[key] for key in ("uri", "generation", "sha256", "bytes")},
        label=f"later-source slate[{source_ordinal}] artifact[{block_ordinal}]",
    )
    if (
        item["season"] != slate["season"]
        or item["week"] != slate["week"]
        or item["block"] != block
        or item["panel_run_id"]
        != f"20260815-atlas-money-worlds-r{block_ordinal}-v1"
        or type(item["candidate_rows"]) is not int
        or item["candidate_rows"] < 1
        or type(item["updated"]) is not str
        or not item["updated"]
    ):
        _fail(
            f"later-source slate[{source_ordinal}] artifact[{block_ordinal}] differs"
        )
    normalized = dict(item)
    normalized.update(identity)
    return normalized, identity


def _validate_later_source(
    value: object, *, normalized_pins: Mapping[str, object]
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[list[dict[str, object]]],
    list[list[dict[str, object]]],
]:
    item = _mapping(value, label="fixed later-source freeze")
    _exact_keys(item, _LATER_SOURCE_FIELDS, label="fixed later-source freeze")
    _false_fields(
        item, _LATER_SOURCE_FALSE_FIELDS, label="fixed later-source freeze"
    )
    internal = _validate_self_hash(
        item, field="freeze_sha256", label="fixed later-source freeze"
    )
    base_identity = _normalized_identity(
        item["base_source_lock_object"], label="later-source base lock"
    )
    if item["base_source_lock_sha256"] != base_identity["sha256"]:
        _fail("later-source base lock hash differs")
    runtime = _mapping(item["runtime_identity"], label="later-source runtime")
    _exact_keys(runtime, _SOURCE_RUNTIME_FIELDS, label="later-source runtime")
    for field in _SOURCE_RUNTIME_FIELDS:
        _string(runtime[field], label=f"later-source runtime.{field}")
    query = _mapping(item["source_query"], label="later-source query")
    _exact_keys(query, _SOURCE_QUERY_FIELDS, label="later-source query")
    candidate_query = _mapping(
        query["candidate_query"], label="later-source candidate query"
    )
    catalog_query = _mapping(
        query["catalog_query"], label="later-source catalog query"
    )
    _exact_keys(
        candidate_query,
        _QUERY_RECEIPT_FIELDS,
        label="later-source candidate query",
    )
    _exact_keys(
        catalog_query,
        _QUERY_RECEIPT_FIELDS,
        label="later-source catalog query",
    )
    for label, receipt in (
        ("candidate", candidate_query),
        ("catalog", catalog_query),
    ):
        for field in ("sql_sha256", "parameters_sha256"):
            _sha(receipt[field], label=f"later-source {label} query.{field}")
        for field in ("job_id", "location", "created", "started", "ended"):
            _string(receipt[field], label=f"later-source {label} query.{field}")
        if (
            type(receipt["total_bytes_processed"]) is not int
            or receipt["total_bytes_processed"] < 0
            or receipt["cache_hit"] is not False
            or receipt["error_result"] is not None
        ):
            _fail(f"later-source {label} query receipt differs")
    selected_columns = _mapping(
        query["selected_columns"], label="later-source selected columns"
    )
    _exact_keys(
        selected_columns,
        frozenset({"candidates", "catalog"}),
        label="later-source selected columns",
    )
    expected_candidate_columns = sorted({
        "panel_run_id",
        "season",
        "week",
        "cand_ix",
        "players",
        "score_artifact_uri",
        "score_artifact_sha256",
    })
    expected_catalog_columns = sorted({
        "season", "week", *catalog.PLAYER_FIELD_ORDER,
    })
    if (
        query["candidate_table"]
        != "nfl-predictions-503414.nfl_predictions.replay_candidates_staging"
        or query["catalog_table"]
        != "nfl-predictions-503414.nfl_predictions.slate_player_features"
        or type(query["source_snapshot_at"]) is not str
        or not query["source_snapshot_at"]
        or selected_columns["candidates"] != expected_candidate_columns
        or selected_columns["catalog"] != expected_catalog_columns
        or query["realized_columns_selected"] != []
        or candidate_query["job_id"] != f"{runtime['run_id']}-r0-candidates"
        or catalog_query["job_id"] != f"{runtime['run_id']}-full-catalog"
        or candidate_query["location"] != "US"
        or catalog_query["location"] != "US"
    ):
        _fail("later-source query/column boundary differs")

    raw_slates = _sequence(item["slates"], label="later-source slates")
    if len(raw_slates) != catalog.TASK_COUNT:
        _fail("later-source slate coverage differs")
    normalized_slates: list[dict[str, object]] = []
    players_by_slate: list[list[dict[str, object]]] = []
    artifacts_by_slate: list[list[dict[str, object]]] = []
    for source_ordinal, raw_slate in enumerate(raw_slates):
        slate_item = _mapping(
            raw_slate, label=f"later-source slate[{source_ordinal}]"
        )
        _exact_keys(
            slate_item,
            _SOURCE_SLATE_FIELDS,
            label=f"later-source slate[{source_ordinal}]",
        )
        expected_slate = catalog.expected_slate_for_source_task(source_ordinal)
        players = catalog.normalize_structural_players(slate_item["catalog"])
        if any(player["salary"] <= 0 for player in players):
            _fail(f"later-source slate[{source_ordinal}] salary differs")
        player_ids = [player["id"] for player in players]
        incumbents = _sequence(
            slate_item["incumbent_candidates"],
            label=f"later-source slate[{source_ordinal}] incumbents",
        )
        artifacts_raw = _sequence(
            slate_item["artifact_receipts"],
            label=f"later-source slate[{source_ordinal}] artifacts",
        )
        if len(artifacts_raw) != len(_WORLD_BLOCKS):
            _fail(f"later-source slate[{source_ordinal}] artifact coverage differs")
        normalized_artifacts: list[dict[str, object]] = []
        artifact_identities: list[dict[str, object]] = []
        for block_ordinal, raw_artifact in enumerate(artifacts_raw):
            normalized_artifact, identity = _validate_source_artifact(
                raw_artifact,
                source_ordinal=source_ordinal,
                block_ordinal=block_ordinal,
            )
            normalized_artifacts.append(normalized_artifact)
            artifact_identities.append(identity)
        if (
            {
                "season": slate_item["season"],
                "week": slate_item["week"],
                "slate_id": slate_item["slate_id"],
            }
            != expected_slate
            or slate_item["catalog_sha256"] != canonical_sha256(players)
            or slate_item["incumbent_candidates_sha256"]
            != canonical_sha256(incumbents)
            or slate_item["artifact_receipts_sha256"]
            != canonical_sha256(normalized_artifacts)
        ):
            _fail(f"later-source slate[{source_ordinal}] binding differs")
        if any(
            not isinstance(roster, Sequence)
            or isinstance(roster, (str, bytes))
            or len(roster) != 9
            or any(type(player_id) is not str for player_id in roster)
            or len(set(roster)) != 9
            or not set(roster) <= set(player_ids)
            for roster in incumbents
        ) or len(incumbents) < 88 or len({tuple(row) for row in incumbents}) != len(
            incumbents
        ):
            _fail(f"later-source slate[{source_ordinal}] incumbents differ")
        normalized_slate = dict(slate_item)
        normalized_slate["catalog"] = players
        normalized_slate["incumbent_candidates"] = incumbents
        normalized_slate["artifact_receipts"] = normalized_artifacts
        normalized_slates.append(normalized_slate)
        players_by_slate.append(players)
        artifacts_by_slate.append(artifact_identities)

    flat_artifacts = [
        identity for identities in artifacts_by_slate for identity in identities
    ]
    if (
        len({str(identity["uri"]) for identity in flat_artifacts})
        != catalog.TASK_COUNT * len(_WORLD_BLOCKS)
        or base_identity["uri"]
        in {str(identity["uri"]) for identity in flat_artifacts}
    ):
        _fail("later-source artifact object identities repeat/overlap")

    if (
        item["schema"] != "lr8-later-period-source-freeze-v1"
        or item["protocol_id"] != "20260820-lr8-historical-residual-columns-v1"
        or item["base_source_version"]
        != "production-law-dependence-source-lock-v1"
        or item["base_source_run_id"]
        != "20260817-production-law-dependence-source-lock-v1"
        or item["source_panels"]
        != [f"20260815-atlas-money-worlds-r{index}-v1" for index in range(5)]
        or item["canonical_incumbent_panel"]
        != "20260815-atlas-money-worlds-r0-v1"
        or item["seasons"] != [2023, 2024, 2025]
        or item["weeks"] != list(range(1, 19))
        or item["slate_count"] != catalog.TASK_COUNT
        or item["artifact_count"] != catalog.TASK_COUNT * len(_WORLD_BLOCKS)
        or item["world_blocks"] != list(_WORLD_BLOCKS)
        or item["worlds_per_block"] != 10_000
        or item["hard_constraints"] != "dk_nfl_classic_only"
        or base_identity != {
            "uri": (
                "gs://nfl-predictions-503414-raw/research/"
                "production-law-dependence-runs/"
                "20260817-production-law-dependence-source-lock-v1/"
                "source-lock.json"
            ),
            "generation": "1786950155692968",
            "sha256": (
                "7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c"
            ),
            "bytes": 1_341_911,
        }
        or item["repaired_2025_w1_r3_sha256"]
        != "7eaef50c890150f6cdc329e80e4d68f08b4a8d2aac402fa5a51ba9ce4f860805"
    ):
        _fail("later-source fixed identity/lattice differs")
    repaired_artifact = normalized_slates[36]["artifact_receipts"][3]
    if repaired_artifact["sha256"] != item["repaired_2025_w1_r3_sha256"]:
        _fail("later-source repaired 2025-W1/R3 artifact differs")
    normalized = dict(item)
    normalized["base_source_lock_object"] = base_identity
    normalized["runtime_identity"] = runtime
    normalized["source_query"] = dict(query)
    normalized["slates"] = normalized_slates
    normalized["freeze_sha256"] = internal
    return normalized, normalized_slates, players_by_slate, artifacts_by_slate


def _validate_source_completion(
    value: object,
    *,
    normalized_pins: Mapping[str, object],
    later_source: Mapping[str, object],
    later_slates: Sequence[Mapping[str, object]],
    source_artifacts: Sequence[Sequence[Mapping[str, object]]],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    item = _mapping(value, label="fixed artifact-source completion")
    _exact_keys(
        item, _SOURCE_COMPLETION_FIELDS, label="fixed artifact-source completion"
    )
    _false_fields(
        item,
        _SOURCE_COMPLETION_FALSE_FIELDS,
        label="fixed artifact-source completion",
    )
    internal = _validate_self_hash(
        item,
        field="completion_sha256",
        label="fixed artifact-source completion",
    )
    registration_identity = _normalized_identity(
        item["registration_object"], label="completion registration"
    )
    source_identity = _normalized_identity(
        item["later_source_freeze_object"], label="completion later source"
    )
    salary_identity = _normalized_identity(
        item["salary_diagnostic_object"], label="completion salary diagnostic"
    )
    if (
        source_identity != normalized_pins["later_source_identity"]
        or item["later_source_freeze_manifest_sha256"]
        != later_source["freeze_sha256"]
        or len({
            registration_identity["uri"],
            source_identity["uri"],
            salary_identity["uri"],
        }) != 3
        or item["registration_sha256"] == registration_identity["sha256"]
        or item["later_source_freeze_manifest_sha256"]
        == source_identity["sha256"]
        or item["salary_diagnostic_sha256"] == salary_identity["sha256"]
    ):
        _fail("artifact-source completion common identities differ")
    for field in (
        "registration_sha256",
        "later_source_freeze_manifest_sha256",
        "salary_diagnostic_sha256",
        "artifact_receipt_manifest_sha256",
        "artifact_validation_manifest_sha256",
        "task_manifest_sha256",
    ):
        _sha(item[field], label=f"artifact-source completion.{field}")

    raw_tasks = _sequence(item["tasks"], label="artifact-source completion tasks")
    if len(raw_tasks) != catalog.TASK_COUNT:
        _fail("artifact-source completion task coverage differs")
    tasks: list[dict[str, object]] = []
    receipt_manifest: list[dict[str, object]] = []
    validation_manifest: list[dict[str, object]] = []
    for source_ordinal, raw_task in enumerate(raw_tasks):
        task = _mapping(
            raw_task, label=f"artifact-source completion task[{source_ordinal}]"
        )
        _exact_keys(
            task,
            _SOURCE_TASK_FIELDS,
            label=f"artifact-source completion task[{source_ordinal}]",
        )
        task_internal = _validate_self_hash(
            task,
            field="task_source_authority_sha256",
            label=f"artifact-source completion task[{source_ordinal}]",
        )
        expected_slate = catalog.expected_slate_for_source_task(source_ordinal)
        later_slate = _mapping(
            later_slates[source_ordinal], label="later-source slate"
        )
        receipts = _mapping(
            task["world_artifact_receipts"],
            label=f"completion task[{source_ordinal}] artifact receipts",
        )
        validations = _mapping(
            task["world_artifact_validations"],
            label=f"completion task[{source_ordinal}] artifact validations",
        )
        _exact_keys(
            receipts,
            frozenset(_WORLD_ROLES),
            label=f"completion task[{source_ordinal}] artifact receipts",
        )
        _exact_keys(
            validations,
            frozenset(_WORLD_ROLES),
            label=f"completion task[{source_ordinal}] artifact validations",
        )
        normalized_receipts = {
            role: _normalized_identity(
                receipts[role],
                label=f"completion task[{source_ordinal}] {role}",
            )
            for role in _WORLD_ROLES
        }
        expected_receipts = {
            role: dict(source_artifacts[source_ordinal][role_ordinal])
            for role_ordinal, role in enumerate(_WORLD_ROLES)
        }
        normalized_validations: dict[str, object] = {}
        for role_ordinal, role in enumerate(_WORLD_ROLES):
            validation = _mapping(
                validations[role],
                label=f"completion task[{source_ordinal}] {role} validation",
            )
            _exact_keys(
                validation,
                _ARTIFACT_VALIDATION_FIELDS,
                label=f"completion task[{source_ordinal}] {role} validation",
            )
            validation_identity = _normalized_identity(
                validation["object"],
                label=f"completion task[{source_ordinal}] {role} validation object",
            )
            expected_ordinal = source_ordinal * len(_WORLD_ROLES) + role_ordinal
            if (
                validation["artifact_ordinal"] != expected_ordinal
                or validation["role"] != role
                or validation_identity != normalized_receipts[role]
                or validation["candidate_rows"]
                != later_slates[source_ordinal]["artifact_receipts"][role_ordinal][
                    "candidate_rows"
                ]
                or validation["player_count"]
                != len(later_slates[source_ordinal]["catalog"])
                or validation["ordered_player_ids_sha256"]
                != task["catalog_player_ids_sha256"]
                or validation["player_set_sha256"]
                != task["catalog_player_ids_sha256"]
                or validation["npz_fields"]
                != sorted({
                    "cand_ix", "totals", "tail_line", "player_ids",
                    "player_draws",
                })
                or validation["player_draws_dtype"] != "float32"
                or validation["player_draws_shape"]
                != [len(later_slates[source_ordinal]["catalog"]), 10_000]
                or validation["world_count"] != 10_000
                or validation["player_set_matches_catalog"] is not True
                or validation["uses_realized_outcomes"] is not False
            ):
                _fail(
                    f"completion task[{source_ordinal}] {role} validation differs"
                )
            normalized_validation = dict(validation)
            normalized_validation["object"] = validation_identity
            normalized_validations[role] = normalized_validation
            receipt_manifest.append({
                "artifact_ordinal": expected_ordinal,
                "task_index": source_ordinal,
                "role": role,
                "object": normalized_receipts[role],
            })
            validation_manifest.append(normalized_validation)
        coverage = _mapping(
            task["salary_coverage"],
            label=f"completion task[{source_ordinal}] salary coverage",
        )
        _exact_keys(
            coverage,
            _SALARY_COVERAGE_FIELDS,
            label=f"completion task[{source_ordinal}] salary coverage",
        )
        count_fields = (
            "salary_player_count",
            "artifact_supported_player_count",
            "artifact_supported_in_salary_count",
            "salary_only_player_count",
            "artifact_only_player_count",
        )
        if any(type(coverage[field]) is not int or coverage[field] < 0 for field in count_fields):
            _fail(f"completion task[{source_ordinal}] salary counts differ")
        if (
            task["task_index"] != source_ordinal
            or {
                "season": task["season"],
                "week": task["week"],
                "slate_id": task["slate_id"],
            }
            != expected_slate
            or task["universe_scope"] != catalog.UNIVERSE_SCOPE
            or task["registration_sha256"] != item["registration_sha256"]
            or task["later_source_freeze_manifest_sha256"]
            != later_source["freeze_sha256"]
            or task["salary_diagnostic_sha256"]
            != item["salary_diagnostic_sha256"]
            or task["catalog_sha256"] != later_slate["catalog_sha256"]
            or task["catalog_player_count"] != len(later_slate["catalog"])
            or task["catalog_player_ids_sha256"]
            != canonical_sha256([player["id"] for player in later_slate["catalog"]])
            or task["incumbent_candidates_sha256"]
            != later_slate["incumbent_candidates_sha256"]
            or normalized_receipts != expected_receipts
            or task["world_artifact_receipt_set_sha256"]
            != canonical_sha256(normalized_receipts)
            or task["world_artifact_validation_set_sha256"]
            != canonical_sha256(normalized_validations)
            or task["complete_dk_salary_universe_claimed"] is not False
            or coverage["artifact_supported_player_count"]
            != task["catalog_player_count"]
            or coverage["artifact_supported_player_ids_sha256"]
            != task["catalog_player_ids_sha256"]
            or coverage["artifact_only_player_count"] != 0
            or coverage["artifact_supported_in_salary_count"]
            != task["catalog_player_count"]
            or coverage["salary_player_count"]
            != coverage["artifact_supported_in_salary_count"]
            + coverage["salary_only_player_count"]
            or coverage["artifact_only_player_ids_sha256"]
            != canonical_sha256([])
            or coverage["artifact_equals_salary_diagnostic"]
            is not (coverage["salary_only_player_count"] == 0)
            or coverage["salary_only_players_have_world_draws"] is not False
            or coverage["coverage_is_predeclared_query_relative"] is not True
            or coverage["query_result_independently_verified"] is not False
            or coverage["complete_dk_salary_coverage_claimed"] is not False
        ):
            _fail(f"artifact-source completion task[{source_ordinal}] differs")
        for field in (
            "salary_player_ids_sha256",
            "artifact_supported_player_ids_sha256",
            "salary_only_player_ids_sha256",
            "artifact_only_player_ids_sha256",
        ):
            _sha(
                coverage[field],
                label=f"completion task[{source_ordinal}] coverage.{field}",
            )
        normalized_task = dict(task)
        normalized_task["world_artifact_receipts"] = normalized_receipts
        normalized_task["world_artifact_validations"] = normalized_validations
        normalized_task["salary_coverage"] = coverage
        normalized_task["task_source_authority_sha256"] = task_internal
        tasks.append(normalized_task)

    summary = _mapping(
        item["salary_coverage_summary"], label="completion coverage summary"
    )
    _exact_keys(summary, _COVERAGE_SUMMARY_FIELDS, label="completion coverage summary")
    if (
        item["schema"]
        != "corpus-artifact-supported-source-authority-completion/v1"
        or item["authority_scope"] != catalog.UNIVERSE_SCOPE
        or item["task_count"] != catalog.TASK_COUNT
        or item["world_blocks"] != list(_WORLD_BLOCKS)
        or item["worlds_per_block"] != 10_000
        or item["artifact_count"] != catalog.TASK_COUNT * len(_WORLD_BLOCKS)
        or item["artifact_stream_order"]
        != "task-index-major_then-r0-r1-r2-r3-r4"
        or item["task_manifest_sha256"] != canonical_sha256(tasks)
        or item["artifact_receipt_manifest_sha256"]
        != canonical_sha256(receipt_manifest)
        or item["artifact_validation_manifest_sha256"]
        != canonical_sha256(validation_manifest)
        or item["artifact_supported_universe_complete"] is not True
        or item["complete_dk_salary_coverage_claimed"] is not False
        or item["complete_dk_salary_universe_claimed"] is not False
        or item["salary_coverage_is_predeclared_query_relative"] is not True
        or item["salary_query_result_independently_verified"] is not False
        or item["salary_only_players_have_world_draws"] is not False
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
        or summary != {
            "task_count": catalog.TASK_COUNT,
            "exact_match_task_count": sum(
                task["salary_coverage"]["artifact_equals_salary_diagnostic"]
                is True
                for task in tasks
            ),
            "artifact_player_slate_count": sum(
                task["salary_coverage"]["artifact_supported_player_count"]
                for task in tasks
            ),
            "salary_player_slate_count": sum(
                task["salary_coverage"]["salary_player_count"] for task in tasks
            ),
            "salary_only_player_slate_count": sum(
                task["salary_coverage"]["salary_only_player_count"]
                for task in tasks
            ),
            "coverage_numerator_artifact_player_slates": sum(
                task["salary_coverage"]["artifact_supported_player_count"]
                for task in tasks
            ),
            "coverage_denominator_salary_player_slates": sum(
                task["salary_coverage"]["salary_player_count"] for task in tasks
            ),
            "diagnostic_required": True,
            "diagnostic_grants_world_draws": False,
            "coverage_is_predeclared_query_relative": True,
            "query_result_independently_verified": False,
            "complete_dk_salary_coverage_claimed": False,
        }
    ):
        _fail("artifact-source completion identity/license differs")
    normalized = dict(item)
    normalized["registration_object"] = registration_identity
    normalized["later_source_freeze_object"] = source_identity
    normalized["salary_diagnostic_object"] = salary_identity
    normalized["tasks"] = tasks
    normalized["salary_coverage_summary"] = summary
    normalized["completion_sha256"] = internal
    return normalized, tasks


def _derive_pinned_projection_inputs_v1(
    *,
    pins: ReplayPinsV1,
    adapter_review: AdapterReviewBindingV1,
    read_tracked: ReadTracked,
    transport: GenerationTransportV1,
    task_evidence_ordinals: Sequence[int] | None = None,
) -> ReplayedProjectionInputsV1:
    if task_evidence_ordinals is None:
        source_ordinals = tuple(range(catalog.TASK_COUNT))
    else:
        source_ordinals = tuple(task_evidence_ordinals)
        if source_ordinals != (0,) or any(
            type(value) is not int for value in source_ordinals
        ):
            _fail("restricted fixed-G0 replay must select exactly task 0")
    selected_lanes = tuple(sorted({
        int(catalog.expected_lane_for_source_task(value)["lane_ordinal"])
        for value in source_ordinals
    }))
    normalized_pins = _normalize_pins(pins)
    normalized_review = _reopen_adapter_review_binding_v1(
        review=adapter_review, read_tracked=read_tracked
    )
    source_commit = str(normalized_pins["source_commit_sha"])
    lock_raw = _read_tracked_exact(
        commit=source_commit,
        path=str(normalized_pins["g0_lock_path"]),
        expected_sha256=str(normalized_pins["g0_lock_sha256"]),
        expected_bytes=int(normalized_pins["g0_lock_bytes"]),
        read_tracked=read_tracked,
        label="fixed G0 lock",
    )
    code_raw = _read_tracked_exact(
        commit=source_commit,
        path=str(normalized_pins["catalog_module_path"]),
        expected_sha256=str(normalized_pins["catalog_module_sha256"]),
        expected_bytes=int(normalized_pins["catalog_module_bytes"]),
        read_tracked=read_tracked,
        label="fixed catalog derivation code",
    )
    if not code_raw:
        _fail("fixed catalog derivation code is empty")
    lock = _validate_g0_lock(
        _parse_canonical_json(
            lock_raw, label="fixed G0 lock", allow_one_newline=True
        ),
        normalized_pins=normalized_pins,
    )

    official_binding = _mapping(
        lock["official_publication_receipt_file"],
        label="G0 official publication file binding",
    )
    official_raw = _read_tracked_exact(
        commit=source_commit,
        path=str(official_binding["relative_path"]),
        expected_sha256=str(official_binding["sha256"]),
        expected_bytes=int(official_binding["bytes"]),
        read_tracked=read_tracked,
        label="fixed panel publication receipt",
    )
    official_receipt = _validate_publication_receipt(
        _parse_canonical_json(
            official_raw,
            label="fixed panel publication receipt",
            allow_one_newline=True,
        ),
        normalized_pins=normalized_pins,
        lock=lock,
    )
    for lane_ordinal, raw_binding in enumerate(lock["lane_terminal_receipts"]):
        lane_binding = _mapping(raw_binding, label=f"G0 lane[{lane_ordinal}]")
        file_binding = _mapping(
            lane_binding["terminal_receipt_file"],
            label=f"G0 lane[{lane_ordinal}] file",
        )
        raw_local = _read_tracked_exact(
            commit=source_commit,
            path=str(file_binding["relative_path"]),
            expected_sha256=str(file_binding["sha256"]),
            expected_bytes=int(file_binding["bytes"]),
            read_tracked=read_tracked,
            label=f"fixed local lane[{lane_ordinal}] envelope",
        )
        _validate_local_lane_envelope(
            _parse_canonical_json(
                raw_local,
                label=f"fixed local lane[{lane_ordinal}] envelope",
                allow_one_newline=True,
            ),
            ordinal=lane_ordinal,
            normalized_pins=normalized_pins,
        )

    panel = _parse_canonical_json(
        read_generation_exact_v1(
            normalized_pins["panel_identity"], transport=transport
        ),
        label="fixed G0 panel",
    )
    normalized_panel, member_bindings, panel_lanes = _validate_panel(
        panel, normalized_pins=normalized_pins
    )
    panel_members = _sequence(
        normalized_panel["accepted_slates"], label="normalized panel members"
    )
    lane_terminals: dict[int, dict[str, object]] = {}
    lane_completions: dict[int, dict[str, object]] = {}
    for lane_ordinal in selected_lanes:
        source_offset = 0 if lane_ordinal == 0 else 28
        expected_count = 28 if lane_ordinal == 0 else 26
        members = [
            _mapping(value, label="panel member")
            for value in panel_members[
                source_offset:source_offset + expected_count
            ]
        ]
        terminal = _validate_lane_terminal(
            _parse_transport_canonical_json(
                read_generation_exact_v1(
                    normalized_pins["lane_terminal_identities"][lane_ordinal],
                    transport=transport,
                ),
                label=f"fixed lane[{lane_ordinal}] terminal",
            ),
            lane_ordinal=lane_ordinal,
            normalized_pins=normalized_pins,
            panel_lane=panel_lanes[lane_ordinal],
            panel_members=members,
        )
        lane_terminals[lane_ordinal] = terminal
        completion = _validate_batch_completion(
            _parse_canonical_json(
                read_generation_exact_v1(
                    normalized_pins["lane_completion_identities"][lane_ordinal],
                    transport=transport,
                ),
                label=f"fixed lane[{lane_ordinal}] completion",
            ),
            lane_ordinal=lane_ordinal,
            normalized_pins=normalized_pins,
            panel_lane=panel_lanes[lane_ordinal],
            panel_members=members,
            terminal=terminal,
        )
        lane_completions[lane_ordinal] = completion

    later_source, later_slates, players_by_slate, source_artifacts = (
        _validate_later_source(
            _parse_canonical_json(
                read_generation_exact_v1(
                    normalized_pins["later_source_identity"], transport=transport
                ),
                label="fixed later-source freeze",
            ),
            normalized_pins=normalized_pins,
        )
    )
    source_completion, completion_tasks = _validate_source_completion(
        _parse_canonical_json(
            read_generation_exact_v1(
                normalized_pins["source_completion_identity"], transport=transport
            ),
            label="fixed artifact-source completion",
        ),
        normalized_pins=normalized_pins,
        later_source=later_source,
        later_slates=later_slates,
        source_artifacts=source_artifacts,
    )
    source_internal = str(later_source["freeze_sha256"])
    completion_internal = str(source_completion["completion_sha256"])
    if (
        normalized_panel["artifact_source_authority_completion_sha256"]
        != completion_internal
        or any(
            lane["artifact_source_authority_completion_sha256"]
            != completion_internal
            or lane["later_source_freeze_manifest_sha256"] != source_internal
            for lane in lane_completions.values()
        )
    ):
        _fail("panel/lane source-completion hash chain differs")

    task_evidence: list[dict[str, object]] = []
    for source_ordinal in source_ordinals:
        expected_lane = catalog.expected_lane_for_source_task(source_ordinal)
        lane_ordinal = int(expected_lane["lane_ordinal"])
        task_ordinal = int(expected_lane["task_ordinal"])
        task_evidence.append(_reopen_task_acceptance_and_carrier_v1(
            source_ordinal=source_ordinal,
            member=_mapping(panel_members[source_ordinal], label="panel member"),
            terminal=lane_terminals[lane_ordinal],
            completion=lane_completions[lane_ordinal],
            completion_task=_mapping(
                lane_completions[lane_ordinal]["task_results"][task_ordinal],
                label="lane completion task",
            ),
            source_completion_task=_mapping(
                completion_tasks[source_ordinal], label="source completion task"
            ),
            expected_world_identities=source_artifacts[source_ordinal],
            normalized_pins=normalized_pins,
            transport=transport,
        ))
    if (
        len(task_evidence) != len(source_ordinals)
        or len({
            canonical_sha256(row["task_acceptance_identity"])
            for row in task_evidence
        }) != len(source_ordinals)
        or len({
            canonical_sha256(row["carrier_identity"])
            for row in task_evidence
        }) != len(source_ordinals)
    ):
        _fail("task acceptance/carrier exact-reopen coverage differs")

    tracked_root = catalog.normalize_tracked_root_binding({
        "g0_authority_lock_schema": lock["schema_version"],
        "g0_authority_lock_relative_path": normalized_pins["g0_lock_path"],
        "g0_authority_lock_file_sha256": normalized_pins["g0_lock_sha256"],
        "g0_authority_lock_sha256": lock["g0_authority_lock_sha256"],
        "source_commit_sha": source_commit,
        "panel_object_identity": normalized_pins["panel_identity"],
        "panel_index_sha256": normalized_panel["panel_index_sha256"],
        "accepted_slate_count": catalog.TASK_COUNT,
    })
    code_identity = catalog.normalize_code_identity({
        "source_commit_sha": source_commit,
        "module_path": normalized_pins["catalog_module_path"],
        "module_sha256": normalized_pins["catalog_module_sha256"],
    })
    source_bindings: list[dict[str, object]] = []
    completion_bindings: list[dict[str, object]] = []
    structural_players: list[tuple[Mapping[str, object], ...]] = []
    for source_ordinal in source_ordinals:
        later_slate = _mapping(later_slates[source_ordinal], label="later slate")
        completion_task = _mapping(
            completion_tasks[source_ordinal], label="completion task"
        )
        member = member_bindings[source_ordinal]
        expected_slate = catalog.expected_slate_for_source_task(source_ordinal)
        players = catalog.normalize_structural_players(
            players_by_slate[source_ordinal]
        )
        player_ids_sha = canonical_sha256([player["id"] for player in players])
        if (
            member["source_task_authority_sha256"]
            != completion_task["task_source_authority_sha256"]
            or later_slate["catalog_sha256"]
            != completion_task["catalog_sha256"]
            or len(players) != completion_task["catalog_player_count"]
            or player_ids_sha != completion_task["catalog_player_ids_sha256"]
        ):
            _fail(f"fixed source projection[{source_ordinal}] chain differs")
        source_binding = catalog.normalize_source_catalog_binding({
            "later_source_freeze_identity": normalized_pins[
                "later_source_identity"
            ],
            "later_source_freeze_manifest_sha256": source_internal,
            "source_task_ordinal": source_ordinal,
            "slate": expected_slate,
            "catalog_sha256": later_slate["catalog_sha256"],
            "catalog_player_count": len(players),
            "catalog_player_ids_sha256": player_ids_sha,
        })
        completion_binding = catalog.normalize_completion_binding({
            "artifact_source_authority_completion_identity": normalized_pins[
                "source_completion_identity"
            ],
            "artifact_source_authority_completion_sha256": completion_internal,
            "later_source_freeze_identity": normalized_pins[
                "later_source_identity"
            ],
            "later_source_freeze_manifest_sha256": source_internal,
            "source_task_ordinal": source_ordinal,
            "slate": expected_slate,
            "universe_scope": catalog.UNIVERSE_SCOPE,
            "task_source_authority_sha256": completion_task[
                "task_source_authority_sha256"
            ],
            "catalog_sha256": completion_task["catalog_sha256"],
            "catalog_player_count": completion_task["catalog_player_count"],
            "catalog_player_ids_sha256": completion_task[
                "catalog_player_ids_sha256"
            ],
        })
        derivation = catalog.build_derivation_receipt_v1(
            tracked_root_binding=tracked_root,
            accepted_member_binding=member,
            source_catalog_binding=source_binding,
            artifact_source_completion_binding=completion_binding,
            structural_players=players,
            derivation_code_identity=code_identity,
        )
        catalog.validate_derivation_receipt_v1(
            derivation,
            expected_tracked_root_binding=tracked_root,
            expected_member_binding=member,
            expected_source_catalog_binding=source_binding,
            expected_completion_binding=completion_binding,
            expected_derivation_code_identity=code_identity,
        )
        source_bindings.append(source_binding)
        completion_bindings.append(completion_binding)
        structural_players.append(tuple(players))

    normalized_namespace = str(normalized_pins["catalog_namespace"])
    input_uris = {
        str(normalized_pins["panel_identity"]["uri"]),
        *(str(value["uri"]) for value in normalized_pins["lane_terminal_identities"]),
        *(str(value["uri"]) for value in normalized_pins["lane_completion_identities"]),
        str(normalized_pins["source_completion_identity"]["uri"]),
        str(normalized_pins["later_source_identity"]["uri"]),
    }
    if any(uri.startswith(normalized_namespace) for uri in input_uris):
        _fail("catalog namespace overlaps a frozen replay input")
    return ReplayedProjectionInputsV1(
        pin_set_sha256=canonical_sha256({
            "fixed_evidence_pins": normalized_pins,
            "source_task_ordinals": list(source_ordinals),
            "adapter_review_binding": {
                key: value for key, value in normalized_review.items()
                if key != "review_lock"
            },
        }),
        source_task_ordinals=source_ordinals,
        tracked_root_binding=tracked_root,
        member_bindings=tuple(
            member_bindings[ordinal] for ordinal in source_ordinals
        ),
        source_catalog_bindings=tuple(source_bindings),
        completion_bindings=tuple(completion_bindings),
        structural_players=tuple(structural_players),
        derivation_code_identity=code_identity,
        catalog_namespace=normalized_namespace,
        source_completion_internal_sha256=completion_internal,
        later_source_internal_sha256=source_internal,
        official_publication_receipt_file=official_binding,
        official_publication_receipt_sha256=str(
            official_receipt["publication_receipt_sha256"]
        ),
        adapter_review_binding={
            key: value for key, value in normalized_review.items()
            if key != "review_lock"
        },
        task_acceptance_body_manifest_sha256=canonical_sha256([
            {
                "source_task_ordinal": row["source_task_ordinal"],
                "identity": row["task_acceptance_identity"],
                "self_hash": row["task_acceptance_sha256"],
            }
            for row in task_evidence
        ]),
        carrier_body_manifest_sha256=canonical_sha256([
            {
                "source_task_ordinal": row["source_task_ordinal"],
                "identity": row["carrier_identity"],
                "self_hash": row["carrier_sha256"],
            }
            for row in task_evidence
        ]),
        task_acceptance_body_count=len(task_evidence),
        carrier_body_count=len(task_evidence),
        task_evidence_bindings=tuple(task_evidence),
        lane_terminal_identities=tuple(
            normalized_pins["lane_terminal_identities"][ordinal]
            for ordinal in selected_lanes
        ),
        lane_completion_identities=tuple(
            normalized_pins["lane_completion_identities"][ordinal]
            for ordinal in selected_lanes
        ),
        later_source_identity=normalized_pins["later_source_identity"],
        source_completion_identity=normalized_pins[
            "source_completion_identity"
        ],
    )


def derive_fixed_g0_projection_inputs_v1(
    *, read_tracked: ReadTracked, transport: GenerationTransportV1,
) -> ReplayedProjectionInputsV1:
    """Remain closed until the separate tracked adapter review lock exists."""
    del read_tracked, transport
    _fail(
        "fixed-G0 public replay is blocked pending its tracked adapter review "
        "lock; use the closed production entry after independent approval"
    )


def _task0_generation_input_identities_v1(
    *,
    inputs: ReplayedProjectionInputsV1,
    evidence: Mapping[str, object],
) -> list[dict[str, object]]:
    if (
        inputs.source_task_ordinals != (0,)
        or len(inputs.lane_terminal_identities) != 1
        or len(inputs.lane_completion_identities) != 1
    ):
        _fail("task-0 smoke input selection differs")
    return [
        _normalized_identity(
            inputs.tracked_root_binding["panel_object_identity"],
            label="smoke panel identity",
        ),
        _normalized_identity(
            inputs.lane_terminal_identities[0],
            label="smoke lane terminal identity",
        ),
        _normalized_identity(
            inputs.lane_completion_identities[0],
            label="smoke lane completion identity",
        ),
        _normalized_identity(
            inputs.later_source_identity, label="smoke later-source identity"
        ),
        _normalized_identity(
            inputs.source_completion_identity,
            label="smoke source-completion identity",
        ),
        _normalized_identity(
            evidence["task_acceptance_identity"],
            label="smoke task acceptance identity",
        ),
        _normalized_identity(
            evidence["carrier_identity"], label="smoke carrier identity"
        ),
    ]


def _build_task0_smoke_attempt_v1(
    *, adapter_review_binding: Mapping[str, object],
) -> dict[str, object]:
    review = _normalize_embedded_adapter_review_binding_v1(
        adapter_review_binding
    )
    body: dict[str, object] = {
        "schema_version": TASK0_REAL_ARTIFACT_SMOKE_ATTEMPT_SCHEMA,
        "command": list(FIXED_TASK0_SMOKE_COMMAND),
        "attempt_relative_path": FIXED_TASK0_SMOKE_ATTEMPT_PATH,
        "success_receipt_relative_path": FIXED_TASK0_SMOKE_RECEIPT_PATH,
        "adapter_review_binding": review,
        "implementation_measurements": review["implementation_measurements"],
        "invocation_count": 1,
        "state": "attempt-reserved-after-review-before-cloud-contact",
        "preliminary_review_reopened_before_reservation": True,
        "reserved_before_cloud_contact": True,
        "cloud_read_performed": False,
        "cloud_mutation_executed": False,
        "gcs_publication_count": 0,
        "local_attempt_marker_create_count": 1,
        "full_projection_release_licensed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _TASK0_SMOKE_ATTEMPT_FALSE_FIELDS},
    }
    body["task0_real_artifact_smoke_attempt_sha256"] = canonical_sha256(body)
    return body


def _validate_task0_smoke_attempt_v1(
    value: object,
    *, expected_adapter_review_binding: Mapping[str, object] | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="task-0 real-artifact smoke attempt")
    _exact_keys(
        item,
        _TASK0_SMOKE_ATTEMPT_FIELDS,
        label="task-0 real-artifact smoke attempt",
    )
    _false_fields(
        item,
        _TASK0_SMOKE_ATTEMPT_FALSE_FIELDS,
        label="task-0 real-artifact smoke attempt",
    )
    retained = _validate_self_hash(
        item,
        field="task0_real_artifact_smoke_attempt_sha256",
        label="task-0 real-artifact smoke attempt",
    )
    review = _normalize_embedded_adapter_review_binding_v1(
        item["adapter_review_binding"]
    )
    measurements = [
        _normalize_file_binding(
            row, label=f"smoke-attempt implementation[{ordinal}]"
        )
        for ordinal, row in enumerate(
            _sequence(
                item["implementation_measurements"],
                label="smoke-attempt implementation measurements",
            )
        )
    ]
    _require_fixed_catalog_runtime_measurement_v1(measurements)
    expected = _build_task0_smoke_attempt_v1(adapter_review_binding=review)
    if (
        item["schema_version"] != TASK0_REAL_ARTIFACT_SMOKE_ATTEMPT_SCHEMA
        or item["command"] != list(FIXED_TASK0_SMOKE_COMMAND)
        or item["attempt_relative_path"] != FIXED_TASK0_SMOKE_ATTEMPT_PATH
        or item["success_receipt_relative_path"]
        != FIXED_TASK0_SMOKE_RECEIPT_PATH
        or item["implementation_measurements"] != measurements
        or measurements != review["implementation_measurements"]
        or type(item["invocation_count"]) is not int
        or item["invocation_count"] != 1
        or item["state"] != "attempt-reserved-after-review-before-cloud-contact"
        or item["preliminary_review_reopened_before_reservation"] is not True
        or item["reserved_before_cloud_contact"] is not True
        or item["cloud_read_performed"] is not False
        or item["cloud_mutation_executed"] is not False
        or type(item["gcs_publication_count"]) is not int
        or item["gcs_publication_count"] != 0
        or type(item["local_attempt_marker_create_count"]) is not int
        or item["local_attempt_marker_create_count"] != 1
        or item["full_projection_release_licensed"] is not False
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
        or retained != expected["task0_real_artifact_smoke_attempt_sha256"]
        or canonical_json_bytes(item) != canonical_json_bytes(expected)
    ):
        _fail("task-0 real-artifact smoke attempt differs")
    if expected_adapter_review_binding is not None and review != (
        _normalize_embedded_adapter_review_binding_v1(
            expected_adapter_review_binding
        )
    ):
        _fail("task-0 smoke attempt review binding differs")
    return expected


def build_task0_smoke_recovery_review_lock_v1(
    *,
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    v1_attempt_raw: bytes,
    independent_static_review_passed: bool,
) -> dict[str, object]:
    """Build the pure reviewed boundary for one pre-client v2 correction."""
    implementation_commit = _commit(
        implementation_commit_sha, label="smoke-recovery implementation commit"
    )
    measurements = [
        _normalize_file_binding(
            row, label=f"smoke-recovery implementation[{ordinal}]"
        )
        for ordinal, row in enumerate(implementation_measurements)
    ]
    if [row["relative_path"] for row in measurements] != list(
        FIXED_ADAPTER_IMPLEMENTATION_PATHS
    ):
        _fail("smoke-recovery implementation measurement order differs")
    _require_fixed_catalog_runtime_measurement_v1(measurements)
    if (
        type(v1_attempt_raw) is not bytes
        or len(v1_attempt_raw) != FIXED_TASK0_SMOKE_ATTEMPT_V1_BYTES
        or sha256(v1_attempt_raw).hexdigest()
        != FIXED_TASK0_SMOKE_ATTEMPT_V1_SHA256
    ):
        _fail("preserved v1 smoke-attempt bytes differ")
    v1_attempt = _validate_task0_smoke_attempt_v1(
        _parse_canonical_json(
            v1_attempt_raw,
            label="preserved v1 smoke attempt",
            allow_one_newline=True,
        )
    )
    if (
        v1_attempt["task0_real_artifact_smoke_attempt_sha256"]
        != FIXED_TASK0_SMOKE_ATTEMPT_V1_INTERNAL_SHA256
        or independent_static_review_passed is not True
    ):
        _fail("smoke-recovery v1 history or static review differs")
    body: dict[str, object] = {
        "schema_version": TASK0_SMOKE_RECOVERY_REVIEW_LOCK_SCHEMA,
        "implementation_commit_sha": implementation_commit,
        "implementation_measurements": measurements,
        "recovery_amendment_measurement": {
            "relative_path": FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_PATH,
            "sha256": FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_SHA256,
            "bytes": FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_BYTES,
        },
        "v1_attempt_measurement": {
            "relative_path": FIXED_TASK0_SMOKE_ATTEMPT_PATH,
            "sha256": FIXED_TASK0_SMOKE_ATTEMPT_V1_SHA256,
            "bytes": FIXED_TASK0_SMOKE_ATTEMPT_V1_BYTES,
        },
        "v1_attempt_internal_sha256": (
            FIXED_TASK0_SMOKE_ATTEMPT_V1_INTERNAL_SHA256
        ),
        "v1_review_binding": v1_attempt["adapter_review_binding"],
        "v1_invocation_count": 1,
        "v1_exit_before_gcs_client_construction": True,
        "v1_exit_before_cloud_read": True,
        "v1_failure_classification": (
            "incomplete-temporary-venv-google-storage-import-failure"
        ),
        "v1_cloud_read_count": 0,
        "v1_cloud_mutation_count": 0,
        "v1_gcs_publication_count": 0,
        "v1_outcomes_read": False,
        "v1_success_receipt_absent": True,
        "v2_command": list(FIXED_TASK0_SMOKE_V2_COMMAND),
        "v2_invocation_count_max": 1,
        "lifetime_invocation_count_max": 2,
        "third_invocation_allowed": False,
        "v2_marker_create_once_before_client": True,
        "v2_success_receipt_path": FIXED_TASK0_SMOKE_RECEIPT_PATH,
        "independent_static_review_passed": True,
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "cloud_read_only_smoke_licensed": True,
        "gcs_mutation_licensed": False,
        "uses_realized_outcomes": False,
        **{field: False for field in _TASK0_SMOKE_ATTEMPT_FALSE_FIELDS},
    }
    body["task0_smoke_recovery_review_lock_sha256"] = canonical_sha256(body)
    return body


def validate_task0_smoke_recovery_review_lock_v1(
    value: object,
    *,
    expected_implementation_commit_sha: str,
    expected_implementation_measurements: Sequence[Mapping[str, object]],
    expected_v1_attempt_raw: bytes,
) -> dict[str, object]:
    item = _mapping(value, label="task-0 smoke-recovery review lock")
    _exact_keys(
        item,
        _TASK0_SMOKE_RECOVERY_LOCK_FIELDS,
        label="task-0 smoke-recovery review lock",
    )
    _false_fields(
        item,
        _TASK0_SMOKE_ATTEMPT_FALSE_FIELDS,
        label="task-0 smoke-recovery review lock",
    )
    _validate_self_hash(
        item,
        field="task0_smoke_recovery_review_lock_sha256",
        label="task-0 smoke-recovery review lock",
    )
    expected = build_task0_smoke_recovery_review_lock_v1(
        implementation_commit_sha=expected_implementation_commit_sha,
        implementation_measurements=expected_implementation_measurements,
        v1_attempt_raw=expected_v1_attempt_raw,
        independent_static_review_passed=True,
    )
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("task-0 smoke-recovery review lock differs")
    return expected


def _build_task0_smoke_attempt_v2(
    *,
    recovery_review_lock: Mapping[str, object],
    recovery_review_lock_file: Mapping[str, object],
    v1_attempt_raw: bytes,
) -> dict[str, object]:
    lock = _mapping(
        recovery_review_lock, label="task-0 smoke-recovery review lock"
    )
    _exact_keys(
        lock,
        _TASK0_SMOKE_RECOVERY_LOCK_FIELDS,
        label="task-0 smoke-recovery review lock",
    )
    lock_sha = _validate_self_hash(
        lock,
        field="task0_smoke_recovery_review_lock_sha256",
        label="task-0 smoke-recovery review lock",
    )
    lock_file = _normalize_file_binding(
        recovery_review_lock_file, label="smoke-recovery review-lock file"
    )
    if lock_file["relative_path"] != FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH:
        _fail("smoke-recovery review-lock path differs")
    if (
        len(v1_attempt_raw) != FIXED_TASK0_SMOKE_ATTEMPT_V1_BYTES
        or sha256(v1_attempt_raw).hexdigest()
        != FIXED_TASK0_SMOKE_ATTEMPT_V1_SHA256
    ):
        _fail("preserved v1 smoke-attempt bytes differ")
    body: dict[str, object] = {
        "schema_version": TASK0_REAL_ARTIFACT_SMOKE_ATTEMPT_V2_SCHEMA,
        "command": list(FIXED_TASK0_SMOKE_V2_COMMAND),
        "attempt_relative_path": FIXED_TASK0_SMOKE_ATTEMPT_V2_PATH,
        "success_receipt_relative_path": FIXED_TASK0_SMOKE_RECEIPT_PATH,
        "recovery_review_lock_file": lock_file,
        "recovery_review_lock_internal_sha256": lock_sha,
        "v1_attempt_measurement": lock["v1_attempt_measurement"],
        "v1_attempt_internal_sha256": lock["v1_attempt_internal_sha256"],
        "adapter_review_binding": lock["v1_review_binding"],
        "implementation_measurements": lock["implementation_measurements"],
        "v1_invocation_count": 1,
        "v2_invocation_count": 1,
        "lifetime_invocation_count": 2,
        "state": "v2-attempt-reserved-after-recovery-lock-before-client",
        "reserved_before_gcs_client_construction": True,
        "cloud_read_performed": False,
        "cloud_mutation_executed": False,
        "gcs_publication_count": 0,
        "local_attempt_marker_create_count": 1,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _TASK0_SMOKE_ATTEMPT_FALSE_FIELDS},
    }
    body["task0_real_artifact_smoke_attempt_v2_sha256"] = canonical_sha256(body)
    return body


def _validate_task0_smoke_attempt_v2(
    value: object,
    *,
    expected_recovery_review_lock: Mapping[str, object],
    expected_recovery_review_lock_file: Mapping[str, object],
    expected_v1_attempt_raw: bytes,
) -> dict[str, object]:
    item = _mapping(value, label="task-0 real-artifact smoke attempt v2")
    _exact_keys(
        item,
        _TASK0_SMOKE_ATTEMPT_V2_FIELDS,
        label="task-0 real-artifact smoke attempt v2",
    )
    _false_fields(
        item,
        _TASK0_SMOKE_ATTEMPT_FALSE_FIELDS,
        label="task-0 real-artifact smoke attempt v2",
    )
    _validate_self_hash(
        item,
        field="task0_real_artifact_smoke_attempt_v2_sha256",
        label="task-0 real-artifact smoke attempt v2",
    )
    expected = _build_task0_smoke_attempt_v2(
        recovery_review_lock=expected_recovery_review_lock,
        recovery_review_lock_file=expected_recovery_review_lock_file,
        v1_attempt_raw=expected_v1_attempt_raw,
    )
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("task-0 real-artifact smoke attempt v2 differs")
    return expected


def _task0_smoke_attempt_file_binding_v1(
    *, adapter_review_binding: Mapping[str, object],
) -> tuple[dict[str, object], str]:
    attempt = _build_task0_smoke_attempt_v1(
        adapter_review_binding=adapter_review_binding
    )
    raw = canonical_json_bytes(attempt) + b"\n"
    return (
        {
            "relative_path": FIXED_TASK0_SMOKE_ATTEMPT_PATH,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        str(attempt["task0_real_artifact_smoke_attempt_sha256"]),
    )


def _build_task0_real_artifact_smoke_receipt_v1(
    *, inputs: ReplayedProjectionInputsV1,
) -> dict[str, object]:
    if (
        inputs.source_task_ordinals != (0,)
        or len(inputs.member_bindings) != 1
        or len(inputs.source_catalog_bindings) != 1
        or len(inputs.completion_bindings) != 1
        or len(inputs.structural_players) != 1
        or len(inputs.task_evidence_bindings) != 1
        or inputs.task_acceptance_body_count != 1
        or inputs.carrier_body_count != 1
    ):
        _fail("task-0 smoke requires one exact selected source task")
    evidence = _mapping(
        inputs.task_evidence_bindings[0], label="task-0 smoke evidence"
    )
    if evidence.get("source_task_ordinal") != 0:
        _fail("task-0 smoke evidence ordinal differs")
    derivation = catalog.build_derivation_receipt_v1(
        tracked_root_binding=inputs.tracked_root_binding,
        accepted_member_binding=inputs.member_bindings[0],
        source_catalog_binding=inputs.source_catalog_bindings[0],
        artifact_source_completion_binding=inputs.completion_bindings[0],
        structural_players=inputs.structural_players[0],
        derivation_code_identity=inputs.derivation_code_identity,
    )
    derivation = catalog.validate_derivation_receipt_v1(
        derivation,
        expected_tracked_root_binding=inputs.tracked_root_binding,
        expected_member_binding=inputs.member_bindings[0],
        expected_source_catalog_binding=inputs.source_catalog_bindings[0],
        expected_completion_binding=inputs.completion_bindings[0],
        expected_derivation_code_identity=inputs.derivation_code_identity,
    )
    generation_inputs = _task0_generation_input_identities_v1(
        inputs=inputs, evidence=evidence
    )
    implementation_measurements = [
        _normalize_file_binding(row, label=f"smoke implementation[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(
                inputs.adapter_review_binding["implementation_measurements"],
                label="smoke implementation measurements",
            )
        )
    ]
    _require_fixed_catalog_runtime_measurement_v1(implementation_measurements)
    attempt_file, attempt_internal = _task0_smoke_attempt_file_binding_v1(
        adapter_review_binding=inputs.adapter_review_binding
    )
    body: dict[str, object] = {
        "schema_version": TASK0_REAL_ARTIFACT_SMOKE_SCHEMA,
        "command": list(FIXED_TASK0_SMOKE_COMMAND),
        "receipt_relative_path": FIXED_TASK0_SMOKE_RECEIPT_PATH,
        "invocation_count": 1,
        "passed": True,
        "evidence_source_commit_sha": inputs.derivation_code_identity[
            "source_commit_sha"
        ],
        "pin_set_sha256": inputs.pin_set_sha256,
        "adapter_review_binding": inputs.adapter_review_binding,
        "implementation_measurements": implementation_measurements,
        "task0_smoke_attempt_file": attempt_file,
        "task0_smoke_attempt_internal_sha256": attempt_internal,
        "source_task_ordinals": [0],
        "tracked_root_binding": inputs.tracked_root_binding,
        "generation_pinned_input_identities": generation_inputs,
        "generation_pinned_input_count": len(generation_inputs),
        "task0_task_acceptance_identity": evidence[
            "task_acceptance_identity"
        ],
        "task0_task_acceptance_sha256": evidence[
            "task_acceptance_sha256"
        ],
        "task0_carrier_identity": evidence["carrier_identity"],
        "task0_carrier_sha256": evidence["carrier_sha256"],
        "task_acceptance_body_count": inputs.task_acceptance_body_count,
        "task_acceptance_body_manifest_sha256": (
            inputs.task_acceptance_body_manifest_sha256
        ),
        "carrier_body_count": inputs.carrier_body_count,
        "carrier_body_manifest_sha256": inputs.carrier_body_manifest_sha256,
        "task0_derivation_receipt": derivation,
        "task0_derivation_sha256": derivation["derivation_sha256"],
        "task0_source_evidence_exact_reopened": True,
        "task0_derivation_validated": True,
        "gcs_read_performed": True,
        "gcs_mutation_executed": False,
        "gcs_publication_count": 0,
        "local_tracked_receipt_create_count": 1,
        "source_completion_artifact_bodies_reopened": False,
        "world_matrix_bodies_reopened": False,
        "result_object_bodies_reopened": False,
        "full_projection_release_licensed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _TASK0_SMOKE_FALSE_FIELDS},
    }
    body["task0_real_artifact_smoke_sha256"] = canonical_sha256(body)
    return body


def _build_task0_real_artifact_smoke_receipt_v2(
    *, inputs: ReplayedProjectionInputsV1, v2_attempt: Mapping[str, object],
) -> dict[str, object]:
    attempt = _mapping(v2_attempt, label="task-0 smoke attempt v2")
    _exact_keys(
        attempt,
        _TASK0_SMOKE_ATTEMPT_V2_FIELDS,
        label="task-0 smoke attempt v2",
    )
    _validate_self_hash(
        attempt,
        field="task0_real_artifact_smoke_attempt_v2_sha256",
        label="task-0 smoke attempt v2",
    )
    base = _build_task0_real_artifact_smoke_receipt_v1(inputs=inputs)
    body = {
        key: value
        for key, value in base.items()
        if key != "task0_real_artifact_smoke_sha256"
    }
    attempt_raw = canonical_json_bytes(attempt) + b"\n"
    body.update({
        "schema_version": TASK0_REAL_ARTIFACT_SMOKE_V2_SCHEMA,
        "command": list(FIXED_TASK0_SMOKE_V2_COMMAND),
        "invocation_count": 2,
        "task0_smoke_attempt_file": {
            "relative_path": FIXED_TASK0_SMOKE_ATTEMPT_V2_PATH,
            "sha256": sha256(attempt_raw).hexdigest(),
            "bytes": len(attempt_raw),
        },
        "task0_smoke_attempt_internal_sha256": attempt[
            "task0_real_artifact_smoke_attempt_v2_sha256"
        ],
    })
    body["task0_real_artifact_smoke_sha256"] = canonical_sha256(body)
    return body


def _validate_task0_real_artifact_smoke_receipt_v1(
    value: object,
    *,
    expected_adapter_review_binding: Mapping[str, object] | None = None,
    expected_inputs: ReplayedProjectionInputsV1 | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="task-0 real-artifact smoke receipt")
    _exact_keys(
        item,
        _TASK0_SMOKE_RECEIPT_FIELDS,
        label="task-0 real-artifact smoke receipt",
    )
    _false_fields(
        item,
        _TASK0_SMOKE_FALSE_FIELDS,
        label="task-0 real-artifact smoke receipt",
    )
    retained = _validate_self_hash(
        item,
        field="task0_real_artifact_smoke_sha256",
        label="task-0 real-artifact smoke receipt",
    )
    review = _normalize_embedded_adapter_review_binding_v1(
        item["adapter_review_binding"]
    )
    measurements = [
        _normalize_file_binding(row, label=f"smoke implementation[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(
                item["implementation_measurements"],
                label="smoke implementation measurements",
            )
        )
    ]
    _require_fixed_catalog_runtime_measurement_v1(measurements)
    attempt_file = _normalize_file_binding(
        item["task0_smoke_attempt_file"], label="smoke attempt file"
    )
    expected_attempt_file, expected_attempt_internal = (
        _task0_smoke_attempt_file_binding_v1(
            adapter_review_binding=review
        )
    )
    derivation = catalog.validate_derivation_receipt_v1(
        item["task0_derivation_receipt"]
    )
    member = _mapping(
        derivation["accepted_member_binding"], label="smoke accepted member"
    )
    source = _mapping(
        derivation["source_catalog_binding"], label="smoke source catalog"
    )
    completion = _mapping(
        derivation["artifact_source_completion_binding"],
        label="smoke source completion",
    )
    code = _mapping(
        derivation["derivation_code_identity"], label="smoke code identity"
    )
    root = _mapping(
        derivation["tracked_root_binding"], label="smoke tracked root"
    )
    acceptance_identity = _normalized_identity(
        item["task0_task_acceptance_identity"],
        label="smoke task acceptance identity",
    )
    carrier_identity = _normalized_identity(
        item["task0_carrier_identity"], label="smoke carrier identity"
    )
    generation_inputs = [
        _normalized_identity(row, label=f"smoke generation input[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(
                item["generation_pinned_input_identities"],
                label="smoke generation inputs",
            )
        )
    ]
    if expected_inputs is None:
        fixed_pins = _normalize_pins(FIXED_PINS)
        expected_source_commit = str(fixed_pins["source_commit_sha"])
        expected_generation_inputs = [
            _normalized_identity(
                fixed_pins["panel_identity"], label="fixed panel identity"
            ),
            _normalized_identity(
                _sequence(
                    fixed_pins["lane_terminal_identities"],
                    label="fixed lane terminal identities",
                )[0],
                label="fixed lane-0 terminal identity",
            ),
            _normalized_identity(
                _sequence(
                    fixed_pins["lane_completion_identities"],
                    label="fixed lane completion identities",
                )[0],
                label="fixed lane-0 completion identity",
            ),
            _normalized_identity(
                fixed_pins["later_source_identity"],
                label="fixed later-source identity",
            ),
            _normalized_identity(
                fixed_pins["source_completion_identity"],
                label="fixed source-completion identity",
            ),
            acceptance_identity,
            carrier_identity,
        ]
        expected_code = {
            "source_commit_sha": fixed_pins["source_commit_sha"],
            "module_path": fixed_pins["catalog_module_path"],
            "module_sha256": fixed_pins["catalog_module_sha256"],
        }
    else:
        expected_source_commit = str(
            expected_inputs.derivation_code_identity["source_commit_sha"]
        )
        expected_generation_inputs = _task0_generation_input_identities_v1(
            inputs=expected_inputs,
            evidence={
                "task_acceptance_identity": acceptance_identity,
                "carrier_identity": carrier_identity,
            },
        )
        expected_code = dict(expected_inputs.derivation_code_identity)
    task_acceptance_sha = _sha(
        item["task0_task_acceptance_sha256"],
        label="smoke task acceptance self-hash",
    )
    carrier_sha = _sha(
        item["task0_carrier_sha256"], label="smoke carrier self-hash"
    )
    retained_pin_set = _sha(
        item["pin_set_sha256"], label="task-0 smoke pin-set SHA"
    )
    if expected_inputs is None:
        expected_pin_set = canonical_sha256({
            "fixed_evidence_pins": fixed_pins,
            "source_task_ordinals": [0],
            "adapter_review_binding": review,
        })
    else:
        expected_pin_set = expected_inputs.pin_set_sha256
    if (
        item["schema_version"] != TASK0_REAL_ARTIFACT_SMOKE_SCHEMA
        or item["command"] != list(FIXED_TASK0_SMOKE_COMMAND)
        or item["receipt_relative_path"] != FIXED_TASK0_SMOKE_RECEIPT_PATH
        or type(item["invocation_count"]) is not int
        or item["invocation_count"] != 1
        or item["passed"] is not True
        or item["evidence_source_commit_sha"] != expected_source_commit
        or retained_pin_set != expected_pin_set
        or item["source_task_ordinals"] != [0]
        or item["implementation_measurements"] != measurements
        or measurements != review["implementation_measurements"]
        or attempt_file != expected_attempt_file
        or item["task0_smoke_attempt_internal_sha256"]
        != expected_attempt_internal
        or generation_inputs != expected_generation_inputs
        or type(item["generation_pinned_input_count"]) is not int
        or item["generation_pinned_input_count"] != 7
        or derivation["source_task_ordinal"] != 0
        or derivation["task_ordinal"] != 0
        or derivation["task_id"] != catalog.task_id_for_source_task(0)
        or item["tracked_root_binding"] != root
        or root["source_commit_sha"] != expected_source_commit
        or (
            expected_inputs is None
            and root["g0_authority_lock_relative_path"]
            != fixed_pins["g0_lock_path"]
        )
        or (
            expected_inputs is None
            and root["g0_authority_lock_file_sha256"]
            != fixed_pins["g0_lock_sha256"]
        )
        or (
            expected_inputs is None
            and root["g0_authority_lock_sha256"]
            != fixed_pins["g0_lock_internal_sha256"]
        )
        or root["panel_object_identity"] != expected_generation_inputs[0]
        or member["task_acceptance_identity"] != acceptance_identity
        or member["carrier_identity"] != carrier_identity
        or source["later_source_freeze_identity"]
        != expected_generation_inputs[3]
        or completion["artifact_source_authority_completion_identity"]
        != expected_generation_inputs[4]
        or code != expected_code
        or item["task0_derivation_sha256"] != derivation["derivation_sha256"]
        or type(item["task_acceptance_body_count"]) is not int
        or item["task_acceptance_body_count"] != 1
        or item["task_acceptance_body_manifest_sha256"]
        != canonical_sha256([{
            "source_task_ordinal": 0,
            "identity": acceptance_identity,
            "self_hash": task_acceptance_sha,
        }])
        or type(item["carrier_body_count"]) is not int
        or item["carrier_body_count"] != 1
        or item["carrier_body_manifest_sha256"] != canonical_sha256([{
            "source_task_ordinal": 0,
            "identity": carrier_identity,
            "self_hash": carrier_sha,
        }])
        or item["task0_source_evidence_exact_reopened"] is not True
        or item["task0_derivation_validated"] is not True
        or item["gcs_read_performed"] is not True
        or item["gcs_mutation_executed"] is not False
        or type(item["gcs_publication_count"]) is not int
        or item["gcs_publication_count"] != 0
        or type(item["local_tracked_receipt_create_count"]) is not int
        or item["local_tracked_receipt_create_count"] != 1
        or item["source_completion_artifact_bodies_reopened"] is not False
        or item["world_matrix_bodies_reopened"] is not False
        or item["result_object_bodies_reopened"] is not False
        or item["full_projection_release_licensed"] is not False
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
    ):
        _fail("task-0 real-artifact smoke receipt differs")
    if expected_adapter_review_binding is not None and review != (
        _normalize_embedded_adapter_review_binding_v1(
            expected_adapter_review_binding
        )
    ):
        _fail("task-0 smoke review binding differs")
    normalized = dict(item)
    normalized["adapter_review_binding"] = review
    normalized["implementation_measurements"] = measurements
    normalized["task0_smoke_attempt_file"] = attempt_file
    normalized["tracked_root_binding"] = root
    normalized["generation_pinned_input_identities"] = generation_inputs
    normalized["task0_task_acceptance_identity"] = acceptance_identity
    normalized["task0_carrier_identity"] = carrier_identity
    normalized["task0_derivation_receipt"] = derivation
    normalized["task0_real_artifact_smoke_sha256"] = retained
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("task-0 real-artifact smoke canonical replay differs")
    if expected_inputs is not None and normalized != (
        _build_task0_real_artifact_smoke_receipt_v1(inputs=expected_inputs)
    ):
        _fail("task-0 smoke differs from this exact artifact replay")
    return normalized


def _run_task0_real_artifact_smoke_v1(
    *,
    pins: ReplayPinsV1,
    adapter_review: AdapterReviewBindingV1,
    read_tracked: ReadTracked,
    transport: GenerationTransportV1,
) -> dict[str, object]:
    inputs = _derive_pinned_projection_inputs_v1(
        pins=pins,
        adapter_review=adapter_review,
        read_tracked=read_tracked,
        transport=transport,
        task_evidence_ordinals=(0,),
    )
    receipt = _build_task0_real_artifact_smoke_receipt_v1(inputs=inputs)
    return _validate_task0_real_artifact_smoke_receipt_v1(
        receipt,
        expected_adapter_review_binding=inputs.adapter_review_binding,
        expected_inputs=inputs,
    )


def _transport_read_exact(
    transport: GenerationTransportV1,
) -> Callable[[Mapping[str, object]], bytes]:
    return lambda identity: read_generation_exact_v1(identity, transport=transport)


def _transport_publish_create_once(
    transport: GenerationTransportV1,
) -> Callable[[str, bytes], Mapping[str, object]]:
    return lambda uri, raw: publish_create_once_resumable_v1(
        uri, raw, transport=transport
    )


def _build_replay_receipt_v1(
    *,
    inputs: ReplayedProjectionInputsV1,
    release_identity: Mapping[str, object],
    release: Mapping[str, object],
) -> dict[str, object]:
    normalized_release_identity = _normalized_identity(
        release_identity, label="fixed-G0 catalog release"
    )
    normalized_release = catalog.validate_release_v1(
        release,
        expected_tracked_root_binding=inputs.tracked_root_binding,
        expected_catalog_namespace=inputs.catalog_namespace,
    )
    entries = _sequence(
        normalized_release["entries"], label="fixed-G0 release entries"
    )
    if (
        normalized_release["release_id"] != FIXED_RELEASE_ID
        or normalized_release_identity["uri"]
        != f"{inputs.catalog_namespace}catalog-release.json"
        or normalized_release["derivation_code_identity"]
        != inputs.derivation_code_identity
    ):
        _fail("fixed-G0 release identity/code differs")
    catalog_identities = [
        _mapping(entry, label="release entry")["catalog_identity"]
        for entry in entries
    ]
    body: dict[str, object] = {
        "schema_version": ADAPTER_SCHEMA,
        "replay_id": "fixed-g0-r6-player-catalog-projection-v1",
        "replay_scope": (
            "accepted-panel-index-projection-rooted-in-frozen-g0-evidence"
        ),
        "pin_set_sha256": inputs.pin_set_sha256,
        "tracked_root_binding": inputs.tracked_root_binding,
        "official_publication_receipt_file": (
            inputs.official_publication_receipt_file
        ),
        "official_publication_receipt_sha256": (
            inputs.official_publication_receipt_sha256
        ),
        "adapter_review_binding": inputs.adapter_review_binding,
        "lane_terminal_identities": list(inputs.lane_terminal_identities),
        "lane_completion_identities": list(inputs.lane_completion_identities),
        "later_source_freeze_identity": inputs.later_source_identity,
        "later_source_freeze_manifest_sha256": (
            inputs.later_source_internal_sha256
        ),
        "artifact_source_authority_completion_identity": (
            inputs.source_completion_identity
        ),
        "artifact_source_authority_completion_sha256": (
            inputs.source_completion_internal_sha256
        ),
        "derivation_code_identity": inputs.derivation_code_identity,
        "catalog_namespace": inputs.catalog_namespace,
        "catalog_release_identity": normalized_release_identity,
        "catalog_release_sha256": normalized_release["release_sha256"],
        "task_count": catalog.TASK_COUNT,
        "task_acceptance_body_count": inputs.task_acceptance_body_count,
        "task_acceptance_body_manifest_sha256": (
            inputs.task_acceptance_body_manifest_sha256
        ),
        "carrier_body_count": inputs.carrier_body_count,
        "carrier_body_manifest_sha256": inputs.carrier_body_manifest_sha256,
        "member_binding_manifest_sha256": canonical_sha256(
            list(inputs.member_bindings)
        ),
        "source_catalog_binding_manifest_sha256": canonical_sha256(
            list(inputs.source_catalog_bindings)
        ),
        "completion_binding_manifest_sha256": canonical_sha256(
            list(inputs.completion_bindings)
        ),
        "structural_catalog_manifest_sha256": canonical_sha256([
            list(players) for players in inputs.structural_players
        ]),
        "catalog_identity_manifest_sha256": canonical_sha256(
            catalog_identities
        ),
        "accepted_panel_index_projection_only": True,
        "fresh_task_or_arm_body_revalidation_performed": True,
        "task_acceptance_bodies_reopened": True,
        "carrier_bodies_reopened": True,
        "source_completion_artifact_bodies_reopened": False,
        "world_matrix_bodies_reopened": False,
        "result_object_bodies_reopened": False,
        "execution_manifest_pin_required": True,
        "self_authorizing": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _REPLAY_FALSE_FIELDS},
    }
    body["replay_receipt_sha256"] = canonical_sha256(body)
    return body


def _validate_replay_receipt_v1(
    value: object,
    *,
    inputs: ReplayedProjectionInputsV1,
    release_identity: Mapping[str, object],
    release: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="fixed-G0 replay receipt")
    _exact_keys(item, _REPLAY_RECEIPT_FIELDS, label="fixed-G0 replay receipt")
    retained = _validate_self_hash(
        item, field="replay_receipt_sha256", label="fixed-G0 replay receipt"
    )
    _false_fields(item, _REPLAY_FALSE_FIELDS, label="fixed-G0 replay receipt")
    expected = _build_replay_receipt_v1(
        inputs=inputs, release_identity=release_identity, release=release
    )
    if (
        item["schema_version"] != ADAPTER_SCHEMA
        or item["accepted_panel_index_projection_only"] is not True
        or item["fresh_task_or_arm_body_revalidation_performed"] is not True
        or item["task_acceptance_bodies_reopened"] is not True
        or item["carrier_bodies_reopened"] is not True
        or item["source_completion_artifact_bodies_reopened"] is not False
        or item["world_matrix_bodies_reopened"] is not False
        or item["result_object_bodies_reopened"] is not False
        or item["task_acceptance_body_count"] != catalog.TASK_COUNT
        or item["carrier_body_count"] != catalog.TASK_COUNT
        or item["execution_manifest_pin_required"] is not True
        or item["self_authorizing"] is not False
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
        or retained != expected["replay_receipt_sha256"]
        or canonical_json_bytes(item) != canonical_json_bytes(expected)
    ):
        _fail("fixed-G0 replay receipt differs from exact replay")
    return expected


def _publish_pinned_projection_release_v1(
    *,
    pins: ReplayPinsV1,
    adapter_review: AdapterReviewBindingV1,
    read_tracked: ReadTracked,
    transport: GenerationTransportV1,
    request_authoritative_publication: bool = False,
) -> dict[str, object]:
    if request_authoritative_publication is not False:
        _fail(
            "fixed-G0 projection publication cannot authorize a final release; "
            "a later execution manifest must pin this receipt"
        )
    inputs = _derive_pinned_projection_inputs_v1(
        pins=pins,
        adapter_review=adapter_review,
        read_tracked=read_tracked,
        transport=transport,
    )
    if (
        inputs.source_task_ordinals != tuple(range(catalog.TASK_COUNT))
        or len(inputs.member_bindings) != catalog.TASK_COUNT
        or len(inputs.source_catalog_bindings) != catalog.TASK_COUNT
        or len(inputs.completion_bindings) != catalog.TASK_COUNT
        or len(inputs.structural_players) != catalog.TASK_COUNT
        or inputs.task_acceptance_body_count != catalog.TASK_COUNT
        or inputs.carrier_body_count != catalog.TASK_COUNT
    ):
        _fail("fixed-G0 projection publication requires all 54 exact tasks")
    derivations: list[dict[str, object]] = []
    for source_ordinal in range(catalog.TASK_COUNT):
        derivation = catalog.build_derivation_receipt_v1(
            tracked_root_binding=inputs.tracked_root_binding,
            accepted_member_binding=inputs.member_bindings[source_ordinal],
            source_catalog_binding=inputs.source_catalog_bindings[source_ordinal],
            artifact_source_completion_binding=(
                inputs.completion_bindings[source_ordinal]
            ),
            structural_players=inputs.structural_players[source_ordinal],
            derivation_code_identity=inputs.derivation_code_identity,
        )
        catalog.validate_derivation_receipt_v1(
            derivation,
            expected_tracked_root_binding=inputs.tracked_root_binding,
            expected_member_binding=inputs.member_bindings[source_ordinal],
            expected_source_catalog_binding=(
                inputs.source_catalog_bindings[source_ordinal]
            ),
            expected_completion_binding=inputs.completion_bindings[source_ordinal],
            expected_derivation_code_identity=inputs.derivation_code_identity,
        )
        derivations.append(derivation)

    read_exact = _transport_read_exact(transport)
    publish_create_once = _transport_publish_create_once(transport)
    catalog_identities: list[dict[str, object]] = []
    for source_ordinal, derivation in enumerate(derivations):
        published = catalog.publish_catalog_pair_create_once_v1(
            output_prefix=inputs.catalog_namespace,
            derivation_receipt=derivation,
            structural_players=inputs.structural_players[source_ordinal],
            publish_create_once=publish_create_once,
            read_exact=read_exact,
            request_authoritative_publication=False,
        )
        catalog_identities.append(_normalized_identity(
            published["player_catalog_identity"],
            label=f"published player catalog[{source_ordinal}]",
        ))
    release_identity = catalog.publish_release_create_once_v1(
        output_prefix=inputs.catalog_namespace,
        release_id=FIXED_RELEASE_ID,
        expected_tracked_root_binding=inputs.tracked_root_binding,
        expected_member_bindings=inputs.member_bindings,
        expected_source_catalog_bindings=inputs.source_catalog_bindings,
        expected_completion_bindings=inputs.completion_bindings,
        expected_derivation_code_identity=inputs.derivation_code_identity,
        player_catalog_identities=catalog_identities,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        request_authoritative_publication=False,
    )
    reopened = catalog.reopen_release_v1(
        release_identity=release_identity,
        expected_catalog_namespace=inputs.catalog_namespace,
        expected_tracked_root_binding=inputs.tracked_root_binding,
        expected_member_bindings=inputs.member_bindings,
        expected_source_catalog_bindings=inputs.source_catalog_bindings,
        expected_completion_bindings=inputs.completion_bindings,
        expected_derivation_code_identity=inputs.derivation_code_identity,
        read_exact=read_exact,
    )
    release = _mapping(reopened["release"], label="fixed-G0 catalog release")
    receipt = _build_replay_receipt_v1(
        inputs=inputs, release_identity=release_identity, release=release
    )
    receipt_identity = publish_create_once_resumable_v1(
        f"{inputs.catalog_namespace}{REPLAY_RECEIPT_FILENAME}",
        canonical_json_bytes(receipt),
        transport=transport,
    )
    reopened_receipt = _parse_canonical_json(
        read_generation_exact_v1(receipt_identity, transport=transport),
        label="fixed-G0 replay receipt",
    )
    validated_receipt = _validate_replay_receipt_v1(
        reopened_receipt,
        inputs=inputs,
        release_identity=release_identity,
        release=release,
    )
    return {
        "catalog_release_identity": _normalized_identity(
            release_identity, label="fixed-G0 catalog release"
        ),
        "replay_receipt_identity": _normalized_identity(
            receipt_identity, label="fixed-G0 replay receipt"
        ),
        "replay_receipt": validated_receipt,
    }


def publish_fixed_g0_projection_release_v1(
    *,
    read_tracked: ReadTracked,
    transport: GenerationTransportV1,
    request_authoritative_publication: bool = False,
) -> dict[str, object]:
    """Remain closed until the separate tracked adapter review lock exists."""
    del read_tracked, transport, request_authoritative_publication
    _fail(
        "fixed-G0 public publication is blocked pending its tracked adapter "
        "review lock; use the closed production entry after approval"
    )


def _reopen_pinned_replay_receipt_v1(
    *,
    pins: ReplayPinsV1,
    adapter_review: AdapterReviewBindingV1,
    replay_receipt_identity: Mapping[str, object],
    read_tracked: ReadTracked,
    transport: GenerationTransportV1,
) -> dict[str, object]:
    inputs = _derive_pinned_projection_inputs_v1(
        pins=pins,
        adapter_review=adapter_review,
        read_tracked=read_tracked,
        transport=transport,
    )
    receipt_identity = _normalized_identity(
        replay_receipt_identity, label="fixed-G0 replay receipt"
    )
    if receipt_identity["uri"] != (
        f"{inputs.catalog_namespace}{REPLAY_RECEIPT_FILENAME}"
    ):
        _fail("fixed-G0 replay receipt URI differs from its namespace")
    receipt = _parse_canonical_json(
        read_generation_exact_v1(receipt_identity, transport=transport),
        label="fixed-G0 replay receipt",
    )
    release_identity = _normalized_identity(
        receipt.get("catalog_release_identity"),
        label="receipt catalog release",
    )
    reopened = catalog.reopen_release_v1(
        release_identity=release_identity,
        expected_catalog_namespace=inputs.catalog_namespace,
        expected_tracked_root_binding=inputs.tracked_root_binding,
        expected_member_bindings=inputs.member_bindings,
        expected_source_catalog_bindings=inputs.source_catalog_bindings,
        expected_completion_bindings=inputs.completion_bindings,
        expected_derivation_code_identity=inputs.derivation_code_identity,
        read_exact=_transport_read_exact(transport),
    )
    release = _mapping(reopened["release"], label="fixed-G0 catalog release")
    validated = _validate_replay_receipt_v1(
        receipt,
        inputs=inputs,
        release_identity=release_identity,
        release=release,
    )
    return {
        "replay_receipt_identity": receipt_identity,
        "replay_receipt": validated,
        "catalog_release_identity": release_identity,
        "catalog_release": release,
    }


def reopen_fixed_g0_replay_receipt_v1(
    *,
    replay_receipt_identity: Mapping[str, object],
    read_tracked: ReadTracked,
    transport: GenerationTransportV1,
) -> dict[str, object]:
    """Remain closed until the separate tracked adapter review lock exists."""
    del replay_receipt_identity, read_tracked, transport
    _fail(
        "fixed-G0 public reopen is blocked pending its tracked adapter review "
        "lock; use the closed production entry after approval"
    )


class SubprocessGitRepositoryV1:
    """Exact-commit Git reader with a closed current-clean production gate."""

    def __init__(self, repository_root: Path | None = None) -> None:
        root = repository_root or Path(__file__).resolve().parents[3]
        self.repository_root = root.resolve()

    def _run(self, args: Sequence[str], *, label: str) -> bytes:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(self.repository_root),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            raise CorpusR6FixedG0AdapterV1Error(f"{label} Git read failed")
        return completed.stdout

    def require_current_clean_head(self) -> str:
        root_raw = self._run(
            ["rev-parse", "--show-toplevel"], label="repository root"
        )
        try:
            observed_root = Path(root_raw.decode("utf-8").strip()).resolve()
        except UnicodeError as exc:
            raise CorpusR6FixedG0AdapterV1Error(
                "repository root is not UTF-8"
            ) from exc
        if observed_root != self.repository_root:
            _fail("production repository root differs")
        status = self._run(
            ["status", "--porcelain=v1", "--untracked-files=all"],
            label="repository status",
        )
        if status != b"":
            _fail("production repository must be tracked-clean including untracked")
        head_raw = self._run(
            ["rev-parse", "--verify", "HEAD"], label="repository HEAD"
        )
        try:
            head = head_raw.decode("ascii").strip()
        except UnicodeError as exc:
            raise CorpusR6FixedG0AdapterV1Error(
                "repository HEAD is not ASCII"
            ) from exc
        return _commit(head, label="production repository HEAD")

    def read_tracked(self, commit: str, path: str) -> bytes:
        retained_commit = _commit(commit, label="Git object commit")
        binding = _normalize_file_binding(
            {"relative_path": path, "sha256": "0" * 64, "bytes": 1},
            label="Git object path",
        )
        return self._run(
            ["cat-file", "-p", f"{retained_commit}:{binding['relative_path']}"],
            label="tracked object",
        )


def _split_gcs_uri_v1(uri: str) -> tuple[str, str]:
    retained = _string(uri, label="GCS object URI")
    tail = retained.removeprefix("gs://")
    bucket, marker, name = tail.partition("/")
    if (
        not retained.startswith("gs://")
        or not marker
        or not bucket
        or not name
        or name.endswith("/")
        or "//" in name
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        _fail("GCS object URI differs")
    return bucket, name


class GCSGenerationBackendV1:
    """Google Cloud Storage generation-pinned reads and atomic creates."""

    def __init__(
        self,
        client: object,
        *,
        not_found_error: type[BaseException],
        precondition_failed_error: type[BaseException],
    ) -> None:
        self._client = client
        self._not_found_error = not_found_error
        self._precondition_failed_error = precondition_failed_error
        self._download_cache: dict[tuple[str, str], bytes] = {}

    @classmethod
    def from_default_client(cls) -> "GCSGenerationBackendV1":
        try:
            from google.api_core.exceptions import NotFound, PreconditionFailed
            from google.cloud import storage
        except ImportError as exc:
            raise CorpusR6FixedG0AdapterV1Error(
                "Google Cloud Storage client is unavailable"
            ) from exc
        return cls(
            storage.Client(project=PRODUCTION_PROJECT),
            not_found_error=NotFound,
            precondition_failed_error=PreconditionFailed,
        )

    def _blob(self, uri: str, generation: str | None = None) -> object:
        bucket_name, object_name = _split_gcs_uri_v1(uri)
        bucket = self._client.bucket(bucket_name)
        if generation is None:
            return bucket.blob(object_name)
        retained = _string(generation, label="GCS generation")
        if not retained.isdigit() or retained.startswith("0"):
            _fail("GCS generation differs")
        return bucket.blob(object_name, generation=int(retained))

    @staticmethod
    def _blob_generation(blob: object) -> str:
        generation = getattr(blob, "generation", None)
        retained = str(generation) if generation is not None else ""
        if not retained.isdigit() or retained.startswith("0"):
            _fail("GCS response omitted an exact positive generation")
        return retained

    def _download_pinned(self, uri: str, generation: str) -> bytes:
        blob = self._blob(uri, generation)
        raw = blob.download_as_bytes(if_generation_match=int(generation))
        if type(raw) is not bytes or not raw:
            _fail("GCS generation download returned non-bytes or empty content")
        return raw

    def reload_generation(self, uri: str, generation: str) -> Mapping[str, object]:
        blob = self._blob(uri, generation)
        try:
            blob.reload(if_generation_match=int(generation))
        except self._not_found_error as exc:
            raise ObjectNotFoundV1Error((uri, generation)) from exc
        observed_generation = self._blob_generation(blob)
        if observed_generation != generation:
            _fail("GCS generation-specific metadata drifted")
        raw = self._download_pinned(uri, generation)
        self._download_cache[(uri, generation)] = raw
        return {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def download_generation(self, uri: str, generation: str) -> bytes:
        key = (uri, generation)
        if key in self._download_cache:
            return self._download_cache[key]
        try:
            return self._download_pinned(uri, generation)
        except self._not_found_error as exc:
            raise ObjectNotFoundV1Error(key) from exc

    def resolve_current(self, uri: str) -> Mapping[str, object]:
        blob = self._blob(uri)
        try:
            blob.reload()
        except self._not_found_error as exc:
            raise ObjectNotFoundV1Error(uri) from exc
        generation = self._blob_generation(blob)
        raw = self._download_pinned(uri, generation)
        self._download_cache[(uri, generation)] = raw
        return {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def create_if_absent(
        self, uri: str, raw: bytes, precondition: int,
    ) -> Mapping[str, object]:
        if (
            type(precondition) is not int
            or precondition != 0
            or type(raw) is not bytes
            or not raw
        ):
            _fail("GCS create requires one nonempty body and generation-match zero")
        blob = self._blob(uri)
        try:
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
        except self._precondition_failed_error as exc:
            raise ObjectAlreadyExistsV1Error(uri) from exc
        generation = self._blob_generation(blob)
        reopened = self._download_pinned(uri, generation)
        if reopened != raw:
            _fail("new GCS object differs at its returned generation")
        self._download_cache[(uri, generation)] = reopened
        return {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(reopened).hexdigest(),
            "bytes": len(reopened),
        }

    def transport(self) -> GenerationTransportV1:
        return GenerationTransportV1(
            reload_generation=self.reload_generation,
            download_generation=self.download_generation,
            resolve_current=self.resolve_current,
            create_if_absent=self.create_if_absent,
        )


def _adapter_review_binding_from_raw_v1(
    *, raw: bytes, review_lock_commit_sha: str,
) -> AdapterReviewBindingV1:
    lock = _parse_canonical_json(
        raw, label="current adapter review lock", allow_one_newline=True
    )
    internal = _validate_self_hash(
        lock,
        field="adapter_review_lock_sha256",
        label="current adapter review lock",
    )
    measurements = _sequence(
        lock.get("implementation_measurements"),
        label="current adapter implementation measurements",
    )
    return AdapterReviewBindingV1(
        review_lock_commit_sha=_commit(
            review_lock_commit_sha, label="adapter review-lock commit"
        ),
        implementation_commit_sha=_commit(
            lock.get("implementation_commit_sha"),
            label="reviewed implementation commit",
        ),
        review_lock_relative_path=FIXED_ADAPTER_REVIEW_LOCK_PATH,
        review_lock_file_sha256=sha256(raw).hexdigest(),
        review_lock_file_bytes=len(raw),
        review_lock_internal_sha256=internal,
        implementation_measurements=tuple(
            _normalize_file_binding(
                row, label=f"current adapter measurement[{ordinal}]"
            )
            for ordinal, row in enumerate(measurements)
        ),
    )


def _require_current_implementation_matches_review_v1(
    *,
    repository: SubprocessGitRepositoryV1,
    head: str,
    normalized_review: Mapping[str, object],
) -> None:
    rows = _sequence(
        normalized_review["implementation_measurements"],
        label="current reviewed implementation measurements",
    )
    for ordinal, raw_measurement in enumerate(rows):
        measurement = _normalize_file_binding(
            raw_measurement, label=f"current implementation[{ordinal}]"
        )
        current_raw = repository.read_tracked(
            head, str(measurement["relative_path"])
        )
        if (
            len(current_raw) != measurement["bytes"]
            or sha256(current_raw).hexdigest() != measurement["sha256"]
        ):
            _fail(f"current implementation[{ordinal}] differs from review")


def _resolve_current_adapter_review_v1(
    repository: SubprocessGitRepositoryV1,
) -> tuple[str, AdapterReviewBindingV1]:
    head = repository.require_current_clean_head()
    try:
        raw = repository.read_tracked(head, FIXED_ADAPTER_REVIEW_LOCK_PATH)
    except Exception as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            "tracked adapter review lock is absent; production remains blocked"
        ) from exc
    binding = _adapter_review_binding_from_raw_v1(
        raw=raw, review_lock_commit_sha=head
    )
    normalized = _reopen_adapter_review_binding_v1(
        review=binding, read_tracked=repository.read_tracked
    )
    _require_current_implementation_matches_review_v1(
        repository=repository, head=head, normalized_review=normalized
    )
    return head, binding


def _validate_preliminary_review_raw_against_binding_v1(
    *, raw: bytes, normalized_review: Mapping[str, object],
) -> dict[str, object]:
    if type(raw) is not bytes:
        _fail("preliminary review lock bytes differ")
    candidate = validate_preliminary_adapter_review_lock_candidate_v1(
        _parse_canonical_json(
            raw, label="preliminary adapter review lock", allow_one_newline=True
        ),
        expected_implementation_commit_sha=str(
            normalized_review["implementation_commit_sha"]
        ),
        expected_implementation_measurements=_sequence(
            normalized_review["implementation_measurements"],
            label="preliminary implementation measurements",
        ),
    )
    if (
        normalized_review["review_lock_relative_path"]
        != FIXED_ADAPTER_REVIEW_LOCK_PATH
        or normalized_review["review_lock_file_sha256"]
        != sha256(raw).hexdigest()
        or normalized_review["review_lock_file_bytes"] != len(raw)
        or normalized_review["review_lock_internal_sha256"]
        != candidate["adapter_review_lock_sha256"]
    ):
        _fail("preliminary review lock file binding differs")
    return candidate


def _build_final_release_lock_with_expected_smoke_inputs_v1(
    *,
    preliminary_review: AdapterReviewBindingV1,
    preliminary_review_raw: bytes,
    smoke_attempt_raw: bytes,
    smoke_receipt_raw: bytes,
    independent_static_review_passed: bool,
    publication_approved: bool,
    expected_smoke_inputs: ReplayedProjectionInputsV1 | None = None,
) -> dict[str, object]:
    """Build the deterministic 54-release lock from exact tracked inputs."""
    if independent_static_review_passed is not True:
        _fail("static approval is required for the final release lock")
    if publication_approved is not True:
        _fail("publication approval is required for the final release lock")
    review = _normalize_adapter_review_binding(preliminary_review)
    _validate_preliminary_review_raw_against_binding_v1(
        raw=preliminary_review_raw, normalized_review=review
    )
    attempt = _validate_task0_smoke_attempt_v1(
        _parse_canonical_json(
            smoke_attempt_raw,
            label="final-lock task-0 smoke attempt",
            allow_one_newline=True,
        ),
        expected_adapter_review_binding=review,
    )
    smoke = _validate_task0_real_artifact_smoke_receipt_v1(
        _parse_canonical_json(
            smoke_receipt_raw,
            label="final-lock task-0 smoke receipt",
            allow_one_newline=True,
        ),
        expected_adapter_review_binding=review,
        expected_inputs=expected_smoke_inputs,
    )
    body: dict[str, object] = {
        "schema_version": FINAL_RELEASE_LOCK_SCHEMA,
        "evidence_source_commit_sha": FIXED_SOURCE_COMMIT_SHA,
        "implementation_commit_sha": review["implementation_commit_sha"],
        "implementation_measurements": review["implementation_measurements"],
        "preliminary_review_lock_commit_sha": review["review_lock_commit_sha"],
        "preliminary_review_lock_file": {
            "relative_path": FIXED_ADAPTER_REVIEW_LOCK_PATH,
            "sha256": sha256(preliminary_review_raw).hexdigest(),
            "bytes": len(preliminary_review_raw),
        },
        "preliminary_review_lock_internal_sha256": review[
            "review_lock_internal_sha256"
        ],
        "task0_smoke_receipt_file": {
            "relative_path": FIXED_TASK0_SMOKE_RECEIPT_PATH,
            "sha256": sha256(smoke_receipt_raw).hexdigest(),
            "bytes": len(smoke_receipt_raw),
        },
        "task0_smoke_receipt_internal_sha256": smoke[
            "task0_real_artifact_smoke_sha256"
        ],
        "task0_smoke_attempt_file": {
            "relative_path": FIXED_TASK0_SMOKE_ATTEMPT_PATH,
            "sha256": sha256(smoke_attempt_raw).hexdigest(),
            "bytes": len(smoke_attempt_raw),
        },
        "task0_smoke_attempt_internal_sha256": attempt[
            "task0_real_artifact_smoke_attempt_sha256"
        ],
        "task0_smoke_command": list(FIXED_TASK0_SMOKE_COMMAND),
        "task0_smoke_invocation_count": 1,
        "task0_smoke_passed": True,
        "independent_static_review_passed": True,
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "current_clean_git_required": True,
        "required_source_task_count": catalog.TASK_COUNT,
        "required_task_acceptance_body_reopen_count": catalog.TASK_COUNT,
        "required_carrier_body_reopen_count": catalog.TASK_COUNT,
        "projection_only_publication_reviewed": True,
        "projection_only_publication_licensed": True,
        "projection_release_command": list(FIXED_PROJECTION_RELEASE_COMMAND),
        "production_enable_environment_variable": PRODUCTION_ENABLE_ENV,
        "production_enable_environment_value": "1",
        "gcs_create_once_required": True,
        "gcs_overwrite_licensed": False,
        "world_matrix_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _FINAL_RELEASE_FALSE_FIELDS},
    }
    body["final_release_lock_sha256"] = canonical_sha256(body)
    return _validate_final_release_lock_v1(
        body,
        preliminary_review=preliminary_review,
        preliminary_review_raw=preliminary_review_raw,
        smoke_attempt_raw=smoke_attempt_raw,
        smoke_receipt_raw=smoke_receipt_raw,
        expected_smoke_inputs=expected_smoke_inputs,
    )


def build_final_release_lock_v1(
    *,
    preliminary_review: AdapterReviewBindingV1,
    preliminary_review_raw: bytes,
    smoke_attempt_raw: bytes,
    smoke_receipt_raw: bytes,
    independent_static_review_passed: bool,
    publication_approved: bool,
) -> dict[str, object]:
    """Build only the production FIXED_PINS final-lock candidate."""
    return _build_final_release_lock_with_expected_smoke_inputs_v1(
        preliminary_review=preliminary_review,
        preliminary_review_raw=preliminary_review_raw,
        smoke_attempt_raw=smoke_attempt_raw,
        smoke_receipt_raw=smoke_receipt_raw,
        independent_static_review_passed=independent_static_review_passed,
        publication_approved=publication_approved,
        expected_smoke_inputs=None,
    )


def _validate_final_release_lock_v1(
    value: object,
    *,
    preliminary_review: AdapterReviewBindingV1,
    preliminary_review_raw: bytes,
    smoke_attempt_raw: bytes,
    smoke_receipt_raw: bytes,
    expected_smoke_inputs: ReplayedProjectionInputsV1 | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="fixed-G0 final release lock")
    _exact_keys(
        item, _FINAL_RELEASE_LOCK_FIELDS, label="fixed-G0 final release lock"
    )
    _false_fields(
        item,
        _FINAL_RELEASE_FALSE_FIELDS,
        label="fixed-G0 final release lock",
    )
    retained = _validate_self_hash(
        item,
        field="final_release_lock_sha256",
        label="fixed-G0 final release lock",
    )
    normalized_review = _normalize_adapter_review_binding(preliminary_review)
    _validate_preliminary_review_raw_against_binding_v1(
        raw=preliminary_review_raw, normalized_review=normalized_review
    )
    measurements = [
        _normalize_file_binding(row, label=f"release implementation[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(
                item["implementation_measurements"],
                label="release implementation measurements",
            )
        )
    ]
    _require_fixed_catalog_runtime_measurement_v1(measurements)
    preliminary_file = _normalize_file_binding(
        item["preliminary_review_lock_file"],
        label="preliminary review-lock file",
    )
    attempt_file = _normalize_file_binding(
        item["task0_smoke_attempt_file"], label="task-0 smoke attempt file"
    )
    smoke_file = _normalize_file_binding(
        item["task0_smoke_receipt_file"], label="task-0 smoke receipt file"
    )
    attempt = _validate_task0_smoke_attempt_v1(
        _parse_canonical_json(
            smoke_attempt_raw,
            label="tracked task-0 smoke attempt",
            allow_one_newline=True,
        ),
        expected_adapter_review_binding=normalized_review,
    )
    smoke_receipt = _validate_task0_real_artifact_smoke_receipt_v1(
        _parse_canonical_json(
            smoke_receipt_raw,
            label="tracked task-0 smoke receipt",
            allow_one_newline=True,
        ),
        expected_adapter_review_binding=normalized_review,
        expected_inputs=expected_smoke_inputs,
    )
    if (
        item["schema_version"] != FINAL_RELEASE_LOCK_SCHEMA
        or item["evidence_source_commit_sha"] != FIXED_SOURCE_COMMIT_SHA
        or item["implementation_commit_sha"]
        != normalized_review["implementation_commit_sha"]
        or measurements != normalized_review["implementation_measurements"]
        or item["preliminary_review_lock_commit_sha"]
        != normalized_review["review_lock_commit_sha"]
        or preliminary_file != {
            "relative_path": FIXED_ADAPTER_REVIEW_LOCK_PATH,
            "sha256": sha256(preliminary_review_raw).hexdigest(),
            "bytes": len(preliminary_review_raw),
        }
        or item["preliminary_review_lock_internal_sha256"]
        != normalized_review["review_lock_internal_sha256"]
        or attempt_file != {
            "relative_path": FIXED_TASK0_SMOKE_ATTEMPT_PATH,
            "sha256": sha256(smoke_attempt_raw).hexdigest(),
            "bytes": len(smoke_attempt_raw),
        }
        or item["task0_smoke_attempt_internal_sha256"]
        != attempt["task0_real_artifact_smoke_attempt_sha256"]
        or smoke_file != {
            "relative_path": FIXED_TASK0_SMOKE_RECEIPT_PATH,
            "sha256": sha256(smoke_receipt_raw).hexdigest(),
            "bytes": len(smoke_receipt_raw),
        }
        or item["task0_smoke_receipt_internal_sha256"]
        != smoke_receipt["task0_real_artifact_smoke_sha256"]
        or item["task0_smoke_command"] != list(FIXED_TASK0_SMOKE_COMMAND)
        or type(item["task0_smoke_invocation_count"]) is not int
        or item["task0_smoke_invocation_count"] != 1
        or item["task0_smoke_passed"] is not True
        or item["independent_static_review_passed"] is not True
        or any(
            type(item[field]) is not int or item[field] != 0
            for field in ("p0_open_count", "p1_open_count", "p2_open_count")
        )
        or item["current_clean_git_required"] is not True
        or type(item["required_source_task_count"]) is not int
        or item["required_source_task_count"] != catalog.TASK_COUNT
        or type(item["required_task_acceptance_body_reopen_count"]) is not int
        or item["required_task_acceptance_body_reopen_count"]
        != catalog.TASK_COUNT
        or type(item["required_carrier_body_reopen_count"]) is not int
        or item["required_carrier_body_reopen_count"] != catalog.TASK_COUNT
        or item["projection_only_publication_reviewed"] is not True
        or item["projection_only_publication_licensed"] is not True
        or item["projection_release_command"]
        != list(FIXED_PROJECTION_RELEASE_COMMAND)
        or item["production_enable_environment_variable"]
        != PRODUCTION_ENABLE_ENV
        or item["production_enable_environment_value"] != "1"
        or item["gcs_create_once_required"] is not True
        or item["gcs_overwrite_licensed"] is not False
        or item["world_matrix_bodies_read"] is not False
        or item["result_object_bodies_read"] is not False
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
    ):
        _fail("fixed-G0 final release approval or identity differs")
    normalized = dict(item)
    normalized["implementation_measurements"] = measurements
    normalized["preliminary_review_lock_file"] = preliminary_file
    normalized["task0_smoke_attempt_file"] = attempt_file
    normalized["task0_smoke_receipt_file"] = smoke_file
    normalized["final_release_lock_sha256"] = retained
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("fixed-G0 final release lock canonical replay differs")
    return normalized


def validate_final_release_lock_candidate_v1(
    value: object,
    *,
    preliminary_review: AdapterReviewBindingV1,
    preliminary_review_raw: bytes,
    smoke_attempt_raw: bytes,
    smoke_receipt_raw: bytes,
) -> dict[str, object]:
    """Replay only a production FIXED_PINS final-lock candidate."""
    return _validate_final_release_lock_v1(
        value,
        preliminary_review=preliminary_review,
        preliminary_review_raw=preliminary_review_raw,
        smoke_attempt_raw=smoke_attempt_raw,
        smoke_receipt_raw=smoke_receipt_raw,
        expected_smoke_inputs=None,
    )


def _resolve_current_final_release_lock_v1(
    repository: SubprocessGitRepositoryV1,
    *,
    expected_smoke_inputs: ReplayedProjectionInputsV1 | None = None,
) -> tuple[str, AdapterReviewBindingV1, dict[str, object]]:
    head = repository.require_current_clean_head()
    try:
        final_raw = repository.read_tracked(head, FIXED_FINAL_RELEASE_LOCK_PATH)
    except Exception as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            "tracked final release lock is absent; 54-slate production remains blocked"
        ) from exc
    final_candidate = _parse_canonical_json(
        final_raw, label="current final release lock", allow_one_newline=True
    )
    preliminary_commit = _commit(
        final_candidate.get("preliminary_review_lock_commit_sha"),
        label="final lock preliminary review commit",
    )
    preliminary_file = _normalize_file_binding(
        final_candidate.get("preliminary_review_lock_file"),
        label="final lock preliminary review file",
    )
    if preliminary_file["relative_path"] != FIXED_ADAPTER_REVIEW_LOCK_PATH:
        _fail("final lock preliminary review path differs")
    preliminary_raw = _read_tracked_exact(
        commit=preliminary_commit,
        path=FIXED_ADAPTER_REVIEW_LOCK_PATH,
        expected_sha256=str(preliminary_file["sha256"]),
        expected_bytes=int(preliminary_file["bytes"]),
        read_tracked=repository.read_tracked,
        label="preliminary adapter review lock",
    )
    _read_tracked_exact(
        commit=head,
        path=FIXED_ADAPTER_REVIEW_LOCK_PATH,
        expected_sha256=str(preliminary_file["sha256"]),
        expected_bytes=int(preliminary_file["bytes"]),
        read_tracked=repository.read_tracked,
        label="current preliminary adapter review lock",
    )
    review = _adapter_review_binding_from_raw_v1(
        raw=preliminary_raw, review_lock_commit_sha=preliminary_commit
    )
    normalized_review = _reopen_adapter_review_binding_v1(
        review=review, read_tracked=repository.read_tracked
    )
    _require_current_implementation_matches_review_v1(
        repository=repository, head=head, normalized_review=normalized_review
    )
    attempt_file = _normalize_file_binding(
        final_candidate.get("task0_smoke_attempt_file"),
        label="final lock task-0 smoke attempt file",
    )
    if attempt_file["relative_path"] != FIXED_TASK0_SMOKE_ATTEMPT_PATH:
        _fail("final lock task-0 smoke attempt path differs")
    attempt_raw = _read_tracked_exact(
        commit=head,
        path=FIXED_TASK0_SMOKE_ATTEMPT_PATH,
        expected_sha256=str(attempt_file["sha256"]),
        expected_bytes=int(attempt_file["bytes"]),
        read_tracked=repository.read_tracked,
        label="tracked task-0 real-artifact smoke attempt",
    )
    smoke_file = _normalize_file_binding(
        final_candidate.get("task0_smoke_receipt_file"),
        label="final lock task-0 smoke file",
    )
    if smoke_file["relative_path"] != FIXED_TASK0_SMOKE_RECEIPT_PATH:
        _fail("final lock task-0 smoke path differs")
    smoke_raw = _read_tracked_exact(
        commit=head,
        path=FIXED_TASK0_SMOKE_RECEIPT_PATH,
        expected_sha256=str(smoke_file["sha256"]),
        expected_bytes=int(smoke_file["bytes"]),
        read_tracked=repository.read_tracked,
        label="tracked task-0 real-artifact smoke receipt",
    )
    final_lock = _validate_final_release_lock_v1(
        final_candidate,
        preliminary_review=review,
        preliminary_review_raw=preliminary_raw,
        smoke_attempt_raw=attempt_raw,
        smoke_receipt_raw=smoke_raw,
        expected_smoke_inputs=expected_smoke_inputs,
    )
    return head, review, final_lock


def _fixed_absent_local_report_path_v1(
    relative_path: str, *, label: str,
) -> Path:
    """Return one fixed lexical target only while its whole path is safe."""
    repository_root = Path(REPOSITORY_ROOT)
    relative = Path(relative_path)
    if (
        not repository_root.is_absolute()
        or repository_root.is_symlink()
        or not repository_root.is_dir()
        or relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        _fail(f"{label} root/path differs")
    parent = repository_root
    for part in relative.parts[:-1]:
        parent = parent / part
        if parent.is_symlink() or not parent.is_dir():
            _fail(f"{label} parent is unsafe")
    target = parent / relative.parts[-1]
    if target.is_symlink() or target.exists():
        _fail(f"{label} already exists; invocation is consumed")
    return target


def _fixed_task0_smoke_attempt_path_v1() -> Path:
    return _fixed_absent_local_report_path_v1(
        FIXED_TASK0_SMOKE_ATTEMPT_PATH, label="task-0 smoke attempt"
    )


def _fixed_task0_smoke_attempt_v2_path_v1() -> Path:
    return _fixed_absent_local_report_path_v1(
        FIXED_TASK0_SMOKE_ATTEMPT_V2_PATH, label="task-0 smoke attempt v2"
    )


def _fixed_task0_smoke_recovery_lock_output_path_v1() -> Path:
    return _fixed_absent_local_report_path_v1(
        FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH,
        label="task-0 smoke-recovery review lock",
    )


def _fixed_task0_smoke_receipt_path_v1() -> Path:
    return _fixed_absent_local_report_path_v1(
        FIXED_TASK0_SMOKE_RECEIPT_PATH, label="task-0 smoke receipt"
    )


def _fixed_adapter_review_lock_output_path_v1() -> Path:
    return _fixed_absent_local_report_path_v1(
        FIXED_ADAPTER_REVIEW_LOCK_PATH, label="preliminary adapter review lock"
    )


def _fixed_final_release_lock_output_path_v1() -> Path:
    return _fixed_absent_local_report_path_v1(
        FIXED_FINAL_RELEASE_LOCK_PATH, label="final release lock"
    )


def _write_fixed_local_json_once_v1(
    *, path: Path, value: Mapping[str, object], label: str,
) -> None:
    raw = canonical_json_bytes(value) + b"\n"
    directory_fd: int | None = None
    file_fd: int | None = None
    try:
        directory_fd = os.open(
            path.parent,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        file_fd = os.open(
            path.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC,
            0o644,
            dir_fd=directory_fd,
        )
        written = 0
        while written < len(raw):
            count = os.write(file_fd, raw[written:])
            if count < 1:
                _fail(f"{label} write made no progress")
            written += count
        os.fsync(file_fd)
        # The attempt marker is the lifetime one-shot boundary.  Sync both
        # its bytes and the parent directory entry before any caller may
        # proceed to cloud contact.
        os.fsync(directory_fd)
    except FileExistsError as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            f"{label} create-once collision; invocation is consumed"
        ) from exc
    except OSError as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            f"{label} secure write failed; invocation is consumed"
        ) from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _measure_current_implementation_v1(
    *, repository: SubprocessGitRepositoryV1, head: str,
) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    for ordinal, relative_path in enumerate(FIXED_ADAPTER_IMPLEMENTATION_PATHS):
        try:
            raw = repository.read_tracked(head, relative_path)
        except Exception as exc:
            raise CorpusR6FixedG0AdapterV1Error(
                f"current implementation[{ordinal}] committed read failed"
            ) from exc
        if type(raw) is not bytes or not raw:
            _fail(f"current implementation[{ordinal}] bytes differ")
        measurements.append({
            "relative_path": relative_path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    _require_fixed_catalog_runtime_measurement_v1(measurements)
    return measurements


def _measure_current_tracked_file_v1(
    *,
    repository: SubprocessGitRepositoryV1,
    head: str,
    relative_path: str,
    label: str,
) -> dict[str, object]:
    try:
        raw = repository.read_tracked(head, relative_path)
    except Exception as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            f"{label} committed read failed"
        ) from exc
    if type(raw) is not bytes or not raw:
        _fail(f"{label} bytes differ")
    return {
        "relative_path": relative_path,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _adapter_review_binding_from_normalized_v1(
    value: Mapping[str, object],
) -> AdapterReviewBindingV1:
    normalized = _normalize_embedded_adapter_review_binding_v1(value)
    return AdapterReviewBindingV1(
        review_lock_commit_sha=str(normalized["review_lock_commit_sha"]),
        implementation_commit_sha=str(normalized["implementation_commit_sha"]),
        review_lock_relative_path=str(normalized["review_lock_relative_path"]),
        review_lock_file_sha256=str(normalized["review_lock_file_sha256"]),
        review_lock_file_bytes=int(normalized["review_lock_file_bytes"]),
        review_lock_internal_sha256=str(
            normalized["review_lock_internal_sha256"]
        ),
        implementation_measurements=tuple(
            _sequence(
                normalized["implementation_measurements"],
                label="embedded review implementation measurements",
            )
        ),
    )


def write_preliminary_adapter_review_lock_production_v1(
    *,
    output_relative_path: str,
    focused_test_passed: bool,
    independent_static_review_passed: bool,
) -> dict[str, object]:
    """Create the fixed local preliminary lock; never construct a cloud client."""
    if output_relative_path != FIXED_ADAPTER_REVIEW_LOCK_PATH:
        _fail("preliminary lock output path differs")
    output_path = _fixed_adapter_review_lock_output_path_v1()
    repository = SubprocessGitRepositoryV1()
    head = repository.require_current_clean_head()
    measurements = _measure_current_implementation_v1(
        repository=repository, head=head
    )
    failure_summary = _measure_current_tracked_file_v1(
        repository=repository,
        head=head,
        relative_path=FIXED_FOCUSED_TEST_FAILURE_SUMMARY_PATH,
        label="focused-test failure summary",
    )
    correction_addendum = _measure_current_tracked_file_v1(
        repository=repository,
        head=head,
        relative_path=FIXED_FOCUSED_TEST_CORRECTION_ADDENDUM_PATH,
        label="focused-test correction addendum",
    )
    second_correction = _measure_current_tracked_file_v1(
        repository=repository,
        head=head,
        relative_path=FIXED_SECOND_FOCUSED_TEST_CORRECTION_PATH,
        label="second focused-test correction",
    )
    final_corrective_output = _measure_current_tracked_file_v1(
        repository=repository,
        head=head,
        relative_path=FIXED_FINAL_CORRECTIVE_FOCUSED_TEST_OUTPUT_PATH,
        label="final corrective focused-test output",
    )
    lock = build_preliminary_adapter_review_lock_v1(
        implementation_commit_sha=head,
        implementation_measurements=measurements,
        first_focused_test_failure_summary_file=failure_summary,
        first_focused_test_correction_addendum_file=correction_addendum,
        second_focused_test_correction_file=second_correction,
        final_corrective_focused_test_output_file=final_corrective_output,
        focused_test_passed=focused_test_passed,
        independent_static_review_passed=independent_static_review_passed,
    )
    validate_preliminary_adapter_review_lock_candidate_v1(
        lock,
        expected_implementation_commit_sha=head,
        expected_implementation_measurements=measurements,
    )
    if output_path != _fixed_adapter_review_lock_output_path_v1():
        _fail("preliminary lock output path changed")
    _write_fixed_local_json_once_v1(
        path=output_path, value=lock, label="preliminary adapter review lock"
    )
    return lock


def write_final_release_lock_production_v1(
    *,
    output_relative_path: str,
    independent_static_review_passed: bool,
    publication_approved: bool,
) -> dict[str, object]:
    """Create the fixed final lock from tracked receipts without cloud access."""
    if output_relative_path != FIXED_FINAL_RELEASE_LOCK_PATH:
        _fail("final lock output path differs")
    output_path = _fixed_final_release_lock_output_path_v1()
    repository = SubprocessGitRepositoryV1()
    head = repository.require_current_clean_head()
    try:
        smoke_receipt_raw = repository.read_tracked(
            head, FIXED_TASK0_SMOKE_RECEIPT_PATH
        )
        smoke_attempt_raw = repository.read_tracked(
            head, FIXED_TASK0_SMOKE_ATTEMPT_PATH
        )
    except Exception as exc:
        raise CorpusR6FixedG0AdapterV1Error(
            "tracked task-0 smoke inputs are absent"
        ) from exc
    smoke_candidate = _mapping(
        _parse_canonical_json(
            smoke_receipt_raw,
            label="current task-0 smoke receipt",
            allow_one_newline=True,
        ),
        label="current task-0 smoke receipt",
    )
    review = _adapter_review_binding_from_normalized_v1(
        _mapping(
            smoke_candidate.get("adapter_review_binding"),
            label="current smoke review binding",
        )
    )
    normalized_review = _normalize_adapter_review_binding(review)
    preliminary_raw = _read_tracked_exact(
        commit=str(normalized_review["review_lock_commit_sha"]),
        path=FIXED_ADAPTER_REVIEW_LOCK_PATH,
        expected_sha256=str(normalized_review["review_lock_file_sha256"]),
        expected_bytes=int(normalized_review["review_lock_file_bytes"]),
        read_tracked=repository.read_tracked,
        label="tracked preliminary adapter review lock",
    )
    current_preliminary_raw = _read_tracked_exact(
        commit=head,
        path=FIXED_ADAPTER_REVIEW_LOCK_PATH,
        expected_sha256=str(normalized_review["review_lock_file_sha256"]),
        expected_bytes=int(normalized_review["review_lock_file_bytes"]),
        read_tracked=repository.read_tracked,
        label="current preliminary adapter review lock",
    )
    if current_preliminary_raw != preliminary_raw:
        _fail("current preliminary adapter review lock differs")
    _reopen_adapter_review_binding_v1(
        review=review, read_tracked=repository.read_tracked
    )
    _require_current_implementation_matches_review_v1(
        repository=repository, head=head, normalized_review=normalized_review
    )
    lock = build_final_release_lock_v1(
        preliminary_review=review,
        preliminary_review_raw=preliminary_raw,
        smoke_attempt_raw=smoke_attempt_raw,
        smoke_receipt_raw=smoke_receipt_raw,
        independent_static_review_passed=independent_static_review_passed,
        publication_approved=publication_approved,
    )
    if output_path != _fixed_final_release_lock_output_path_v1():
        _fail("final lock output path changed")
    _write_fixed_local_json_once_v1(
        path=output_path, value=lock, label="final release lock"
    )
    return lock


def _write_task0_smoke_attempt_once_v1(
    path: Path, attempt: Mapping[str, object],
) -> None:
    fixed_path = _fixed_task0_smoke_attempt_path_v1()
    if path != fixed_path:
        _fail("task-0 smoke attempt path differs")
    _validate_task0_smoke_attempt_v1(attempt)
    _write_fixed_local_json_once_v1(
        path=path, value=attempt, label="task-0 smoke attempt"
    )


def _write_task0_smoke_receipt_once_v1(
    path: Path, receipt: Mapping[str, object],
) -> None:
    fixed_path = _fixed_task0_smoke_receipt_path_v1()
    if path != fixed_path:
        _fail("task-0 smoke receipt path differs")
    _write_fixed_local_json_once_v1(
        path=path, value=receipt, label="task-0 smoke receipt"
    )


def write_task0_smoke_recovery_review_lock_production_v1(
    *, output_relative_path: str, independent_static_review_passed: bool,
) -> dict[str, object]:
    """Build one fixed local v2 recovery lock without constructing a client."""
    if output_relative_path != FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH:
        _fail("task-0 smoke-recovery lock output path differs")
    output_path = _fixed_task0_smoke_recovery_lock_output_path_v1()
    _fixed_task0_smoke_receipt_path_v1()
    repository = SubprocessGitRepositoryV1()
    head = repository.require_current_clean_head()
    measurements = _measure_current_implementation_v1(
        repository=repository, head=head
    )
    v1_raw = repository.read_tracked(head, FIXED_TASK0_SMOKE_ATTEMPT_PATH)
    amendment_raw = repository.read_tracked(
        head, FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_PATH
    )
    if (
        sha256(amendment_raw).hexdigest()
        != FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_SHA256
        or len(amendment_raw) != FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_BYTES
    ):
        _fail("task-0 smoke-recovery amendment differs")
    lock = build_task0_smoke_recovery_review_lock_v1(
        implementation_commit_sha=head,
        implementation_measurements=measurements,
        v1_attempt_raw=v1_raw,
        independent_static_review_passed=independent_static_review_passed,
    )
    _write_fixed_local_json_once_v1(
        path=output_path, value=lock, label="task-0 smoke-recovery review lock"
    )
    return lock


def _resolve_current_task0_smoke_recovery_review_v1(
    repository: SubprocessGitRepositoryV1,
) -> tuple[dict[str, object], dict[str, object], bytes, AdapterReviewBindingV1]:
    head = repository.require_current_clean_head()
    lock_raw = repository.read_tracked(
        head, FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH
    )
    v1_raw = repository.read_tracked(head, FIXED_TASK0_SMOKE_ATTEMPT_PATH)
    amendment_raw = repository.read_tracked(
        head, FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_PATH
    )
    if (
        len(amendment_raw) != FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_BYTES
        or sha256(amendment_raw).hexdigest()
        != FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_SHA256
    ):
        _fail("task-0 smoke-recovery amendment differs")
    lock_value = _mapping(
        _parse_canonical_json(
            lock_raw,
            label="task-0 smoke-recovery review lock",
            allow_one_newline=True,
        ),
        label="task-0 smoke-recovery review lock",
    )
    implementation_commit = _commit(
        lock_value.get("implementation_commit_sha"),
        label="smoke-recovery implementation commit",
    )
    measurements = [
        _normalize_file_binding(
            row, label=f"smoke-recovery implementation[{ordinal}]"
        )
        for ordinal, row in enumerate(
            _sequence(
                lock_value.get("implementation_measurements"),
                label="smoke-recovery implementation measurements",
            )
        )
    ]
    lock = validate_task0_smoke_recovery_review_lock_v1(
        lock_value,
        expected_implementation_commit_sha=implementation_commit,
        expected_implementation_measurements=measurements,
        expected_v1_attempt_raw=v1_raw,
    )
    for ordinal, measurement in enumerate(measurements):
        for commit, label in (
            (implementation_commit, "reviewed"),
            (head, "current"),
        ):
            _read_tracked_exact(
                commit=commit,
                path=str(measurement["relative_path"]),
                expected_sha256=str(measurement["sha256"]),
                expected_bytes=int(measurement["bytes"]),
                read_tracked=repository.read_tracked,
                label=f"{label} smoke-recovery implementation[{ordinal}]",
            )
    lock_file = {
        "relative_path": FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH,
        "sha256": sha256(lock_raw).hexdigest(),
        "bytes": len(lock_raw),
    }
    review = _adapter_review_binding_from_normalized_v1(
        _mapping(lock["v1_review_binding"], label="v1 review binding")
    )
    _reopen_adapter_review_binding_v1(
        review=review, read_tracked=repository.read_tracked
    )
    return lock, lock_file, v1_raw, review


def _write_task0_smoke_attempt_v2_once_v1(
    path: Path,
    attempt: Mapping[str, object],
    *,
    recovery_review_lock: Mapping[str, object],
    recovery_review_lock_file: Mapping[str, object],
    v1_attempt_raw: bytes,
) -> None:
    fixed_path = _fixed_task0_smoke_attempt_v2_path_v1()
    if path != fixed_path:
        _fail("task-0 smoke attempt v2 path differs")
    _validate_task0_smoke_attempt_v2(
        attempt,
        expected_recovery_review_lock=recovery_review_lock,
        expected_recovery_review_lock_file=recovery_review_lock_file,
        expected_v1_attempt_raw=v1_attempt_raw,
    )
    _write_fixed_local_json_once_v1(
        path=path, value=attempt, label="task-0 smoke attempt v2"
    )


def run_task0_real_artifact_smoke_production_v2() -> dict[str, object]:
    """Run only the reviewed v2 correction after reserving its own marker."""
    attempt_path = _fixed_task0_smoke_attempt_v2_path_v1()
    receipt_path = _fixed_task0_smoke_receipt_path_v1()
    repository = SubprocessGitRepositoryV1()
    lock, lock_file, v1_raw, review = (
        _resolve_current_task0_smoke_recovery_review_v1(repository)
    )
    attempt = _build_task0_smoke_attempt_v2(
        recovery_review_lock=lock,
        recovery_review_lock_file=lock_file,
        v1_attempt_raw=v1_raw,
    )
    _write_task0_smoke_attempt_v2_once_v1(
        attempt_path,
        attempt,
        recovery_review_lock=lock,
        recovery_review_lock_file=lock_file,
        v1_attempt_raw=v1_raw,
    )
    backend = GCSGenerationBackendV1.from_default_client()
    inputs = _derive_pinned_projection_inputs_v1(
        pins=FIXED_PINS,
        adapter_review=review,
        read_tracked=repository.read_tracked,
        transport=backend.transport(),
        task_evidence_ordinals=(0,),
    )
    receipt = _build_task0_real_artifact_smoke_receipt_v2(
        inputs=inputs, v2_attempt=attempt
    )
    _write_task0_smoke_receipt_once_v1(receipt_path, receipt)
    return receipt


def run_task0_real_artifact_smoke_production_v1() -> dict[str, object]:
    """Run the single reviewed read-only smoke and create its local receipt."""
    attempt_path = _fixed_task0_smoke_attempt_path_v1()
    receipt_path = _fixed_task0_smoke_receipt_path_v1()
    repository = SubprocessGitRepositoryV1()
    _, review = _resolve_current_adapter_review_v1(repository)
    attempt = _build_task0_smoke_attempt_v1(
        adapter_review_binding=_normalize_adapter_review_binding(review)
    )
    # The durable marker is the lifetime one-shot boundary.  It precedes even
    # client construction and every GCS observation, after the preliminary
    # tracked review lock has itself been exact-reopened.
    _write_task0_smoke_attempt_once_v1(attempt_path, attempt)
    backend = GCSGenerationBackendV1.from_default_client()
    receipt = _run_task0_real_artifact_smoke_v1(
        pins=FIXED_PINS,
        adapter_review=review,
        read_tracked=repository.read_tracked,
        transport=backend.transport(),
    )
    _write_task0_smoke_receipt_once_v1(receipt_path, receipt)
    return receipt


def _run_reviewed_fixed_g0_projection_release_v1(
    *,
    repository: SubprocessGitRepositoryV1,
    transport: GenerationTransportV1,
) -> dict[str, object]:
    _, review, _ = _resolve_current_final_release_lock_v1(repository)
    return _publish_pinned_projection_release_v1(
        pins=FIXED_PINS,
        adapter_review=review,
        read_tracked=repository.read_tracked,
        transport=transport,
        request_authoritative_publication=False,
    )


def run_reviewed_fixed_g0_projection_release_production_v1() -> dict[str, object]:
    """Closed live entry; the final 54-release lock precedes cloud creation."""
    if os.environ.get(PRODUCTION_ENABLE_ENV) != "1":
        _fail("fixed-G0 production adapter is parked")
    repository = SubprocessGitRepositoryV1()
    _, review, _ = _resolve_current_final_release_lock_v1(repository)
    backend = GCSGenerationBackendV1.from_default_client()
    return _publish_pinned_projection_release_v1(
        pins=FIXED_PINS,
        adapter_review=review,
        read_tracked=repository.read_tracked,
        transport=backend.transport(),
        request_authoritative_publication=False,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Closed fixed-G0 R6 player-catalog projection adapter"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    preliminary = subparsers.add_parser("build-preliminary-lock")
    preliminary.add_argument("--output", required=True)
    preliminary.add_argument(
        "--focused-test-passed", action="store_true", required=True
    )
    preliminary.add_argument(
        "--static-review-approved", action="store_true", required=True
    )
    preliminary.add_argument("--build", action="store_true", required=True)
    final = subparsers.add_parser("build-final-lock")
    final.add_argument("--output", required=True)
    final.add_argument(
        "--static-review-approved", action="store_true", required=True
    )
    final.add_argument(
        "--publication-approved", action="store_true", required=True
    )
    final.add_argument("--build", action="store_true", required=True)
    preflight = subparsers.add_parser("preflight-task0")
    preflight.add_argument("--preflight", action="store_true", required=True)
    recovery_lock = subparsers.add_parser("build-task0-smoke-recovery-lock")
    recovery_lock.add_argument("--output", required=True)
    recovery_lock.add_argument(
        "--static-review-approved", action="store_true", required=True
    )
    recovery_lock.add_argument("--build", action="store_true", required=True)
    preflight_v2 = subparsers.add_parser("preflight-task0-v2")
    preflight_v2.add_argument("--preflight", action="store_true", required=True)
    publish = subparsers.add_parser("publish-projection")
    publish.add_argument("--execute", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "status":
        print(json.dumps({
            "adapter_review_lock_path": FIXED_ADAPTER_REVIEW_LOCK_PATH,
            "task0_smoke_attempt_path": FIXED_TASK0_SMOKE_ATTEMPT_PATH,
            "task0_smoke_attempt_v2_path": FIXED_TASK0_SMOKE_ATTEMPT_V2_PATH,
            "task0_smoke_recovery_review_lock_path": (
                FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH
            ),
            "task0_smoke_receipt_path": FIXED_TASK0_SMOKE_RECEIPT_PATH,
            "final_release_lock_path": FIXED_FINAL_RELEASE_LOCK_PATH,
            "default_state": "parked",
            "explicit_execute_gate_required": True,
            "final_release_lock_required": True,
            "r6_source_authority": False,
            "uses_realized_outcomes": False,
        }, sort_keys=True, separators=(",", ":")))
        return 0
    if args.command == "build-preliminary-lock":
        result = write_preliminary_adapter_review_lock_production_v1(
            output_relative_path=args.output,
            focused_test_passed=args.focused_test_passed,
            independent_static_review_passed=args.static_review_approved,
        )
        print(canonical_json_bytes(result).decode("ascii"))
        return 0
    if args.command == "build-final-lock":
        result = write_final_release_lock_production_v1(
            output_relative_path=args.output,
            independent_static_review_passed=args.static_review_approved,
            publication_approved=args.publication_approved,
        )
        print(canonical_json_bytes(result).decode("ascii"))
        return 0
    if args.command == "preflight-task0":
        result = run_task0_real_artifact_smoke_production_v1()
        print(canonical_json_bytes(result).decode("ascii"))
        return 0
    if args.command == "build-task0-smoke-recovery-lock":
        result = write_task0_smoke_recovery_review_lock_production_v1(
            output_relative_path=args.output,
            independent_static_review_passed=args.static_review_approved,
        )
        print(canonical_json_bytes(result).decode("ascii"))
        return 0
    if args.command == "preflight-task0-v2":
        result = run_task0_real_artifact_smoke_production_v2()
        print(canonical_json_bytes(result).decode("ascii"))
        return 0
    if args.command != "publish-projection" or args.execute is not True:
        _fail("projection publication requires the explicit execute gate")
    result = run_reviewed_fixed_g0_projection_release_production_v1()
    print(canonical_json_bytes(result).decode("ascii"))
    return 0


__all__ = [
    "ADAPTER_SCHEMA",
    "ADAPTER_REVIEW_LOCK_SCHEMA",
    "FINAL_RELEASE_LOCK_SCHEMA",
    "TASK0_REAL_ARTIFACT_SMOKE_ATTEMPT_SCHEMA",
    "TASK0_REAL_ARTIFACT_SMOKE_ATTEMPT_V2_SCHEMA",
    "TASK0_REAL_ARTIFACT_SMOKE_SCHEMA",
    "TASK0_REAL_ARTIFACT_SMOKE_V2_SCHEMA",
    "TASK0_SMOKE_RECOVERY_REVIEW_LOCK_SCHEMA",
    "AdapterReviewBindingV1",
    "CorpusR6FixedG0AdapterV1Error",
    "FIXED_ADAPTER_REVIEW_LOCK_PATH",
    "FIXED_FINAL_LOCK_BUILD_COMMAND",
    "FIXED_FINAL_RELEASE_LOCK_PATH",
    "FIXED_FOCUSED_TEST_CORRECTION_ADDENDUM_PATH",
    "FIXED_FOCUSED_TEST_FAILURE_SUMMARY_PATH",
    "FIXED_PRELIMINARY_LOCK_BUILD_COMMAND",
    "FIXED_SECOND_FOCUSED_TEST_CORRECTION_PATH",
    "FIXED_FINAL_CORRECTIVE_FOCUSED_TEST_OUTPUT_PATH",
    "FIXED_PROJECTION_RELEASE_COMMAND",
    "FIXED_TASK0_SMOKE_RECEIPT_PATH",
    "FIXED_TASK0_SMOKE_ATTEMPT_PATH",
    "FIXED_TASK0_SMOKE_ATTEMPT_V2_PATH",
    "FIXED_TASK0_SMOKE_COMMAND",
    "FIXED_TASK0_SMOKE_V2_COMMAND",
    "FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_PATH",
    "FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_SHA256",
    "FIXED_TASK0_SMOKE_RECOVERY_AMENDMENT_BYTES",
    "FIXED_TASK0_SMOKE_RECOVERY_REVIEW_LOCK_PATH",
    "FIXED_TASK0_SMOKE_RECOVERY_LOCK_BUILD_COMMAND",
    "FIXED_CATALOG_NAMESPACE",
    "FIXED_G0_LOCK_PATH",
    "FIXED_LANE_COMPLETION_IDENTITIES",
    "FIXED_LANE_TERMINAL_IDENTITIES",
    "FIXED_LATER_SOURCE_IDENTITY",
    "FIXED_PANEL_IDENTITY",
    "FIXED_PINS",
    "FIXED_RELEASE_ID",
    "FIXED_SOURCE_COMPLETION_IDENTITY",
    "GenerationTransportV1",
    "GCSGenerationBackendV1",
    "ObjectAlreadyExistsV1Error",
    "ObjectNotFoundV1Error",
    "REPLAY_RECEIPT_FILENAME",
    "ReplayPinsV1",
    "ReplayedProjectionInputsV1",
    "SubprocessGitRepositoryV1",
    "derive_fixed_g0_projection_inputs_v1",
    "build_final_release_lock_v1",
    "build_preliminary_adapter_review_lock_v1",
    "build_task0_smoke_recovery_review_lock_v1",
    "publish_create_once_resumable_v1",
    "publish_fixed_g0_projection_release_v1",
    "read_generation_exact_v1",
    "reopen_fixed_g0_replay_receipt_v1",
    "run_reviewed_fixed_g0_projection_release_production_v1",
    "run_task0_real_artifact_smoke_production_v1",
    "run_task0_real_artifact_smoke_production_v2",
    "validate_final_release_lock_candidate_v1",
    "validate_preliminary_adapter_review_lock_candidate_v1",
    "validate_task0_smoke_recovery_review_lock_v1",
    "write_final_release_lock_production_v1",
    "write_preliminary_adapter_review_lock_production_v1",
    "write_task0_smoke_recovery_review_lock_production_v1",
]


if __name__ == "__main__":
    raise SystemExit(main())
