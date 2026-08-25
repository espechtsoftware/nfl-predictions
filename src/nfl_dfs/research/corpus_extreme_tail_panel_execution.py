"""Outcome-blind execution and release seam for the frozen T230 panel.

The companion :mod:`corpus_extreme_tail_panel_release` module freezes the
54-member input panel, immutable implementation image, four selector laws,
world dose, budgets, support switch, and deterministic per-slate output URIs.
This module consumes that authority without redefining it.  It exact-reads one
manifest member, reconstructs the accepted Foundry v12 carrier, runs the
support census and four-law selector suite, and retains the support-switched
books.  A separate finalizer exact-reads all 54 create-once acceptances and
per-slate results before applying the frozen 216/270 and 44/54 arithmetic.

No function reads realized outcomes, lists object-store prefixes, retries a
scientific run, mutates a graph, grades a historical contest, or grants
analytical, promotion, decision, or production authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import ast
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import stat
import sys
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_extreme_tail_panel_release as manifest_contract
from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as suite
from nfl_dfs.research import corpus_extreme_tail_support_switch as support
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as accepted
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw


MANIFEST_FILENAME: Final = "foundry-t230-panel-execution-manifest-v1.json"
AUTHORITY_FILENAME: Final = "foundry-t230-panel-execution-authority-v1.json"
PANEL_RELEASE_FILENAME: Final = "foundry-t230-panel-release-v1.json"
WORKER_RUNTIME_FILENAME: Final = "foundry-t230-worker-runtime-v1.json"
VERIFIER_RUNTIME_FILENAME: Final = "foundry-t230-verifier-runtime-v1.json"
IMAGE_EVIDENCE_FILENAME: Final = "foundry-t230-image-evidence-v1.json"
IMAGE_EVIDENCE_SCHEMA: Final = "foundry-t230-image-evidence/v1"
RUNTIME_MEASUREMENT_SCHEMA: Final = "foundry-t230-runtime-measurement/v1"
WORKER_IMPLEMENTATION_SCHEMA: Final = "foundry-t230-worker-implementation/v1"
VERIFIER_IMPLEMENTATION_SCHEMA: Final = "foundry-t230-verifier-implementation/v1"
EXECUTION_AUTHORITY_SCHEMA: Final = "foundry-t230-execution-authority/v1"
SLATE_RESULT_SCHEMA: Final = "foundry-t230-slate-analysis/v1"
SLATE_ACCEPTANCE_SCHEMA: Final = "foundry-t230-slate-acceptance/v1"
PANEL_RELEASE_SCHEMA: Final = "foundry-t230-panel-release/v1"
PUBLICATION_MODE: Final = "create_once"
PANEL_PUBLICATION_RECEIPT_SCHEMA: Final = (
    "foundry-v12-panel-index-publication/v1"
)
G0_AUTHORITY_LOCK_SCHEMA: Final = "foundry-v12-g0-authority-lock/v1"
FROZEN_G0_PANEL_URI: Final = (
    "gs://nfl-predictions-503414-corpus-parametric/research/"
    "corpus-parametric-research/panels/20260823-foundry-production-v12/"
    "foundry-v12-combined-panel-index-v1.json"
)
FROZEN_G0_PUBLICATION_RECEIPT_PATH: Final = Path(
    "/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/"
    "20260823-foundry-production-v12-panel-index/panel-index-live/published.json"
)
FROZEN_G0_LANE_RECEIPT_PATHS: Final = (
    Path(
        "/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/"
        "20260823-foundry-production-v12a/transport-live-v12a/batch-accepted.json"
    ),
    Path(
        "/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/"
        "20260823-foundry-production-v12b/transport-live-v12b/batch-accepted.json"
    ),
)
FROZEN_G0_AUTHORITY_LOCK_PATH: Final = Path(
    "/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/"
    "20260823-foundry-production-v12-panel-index/g0-authority-lock-v1.json"
)
FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH: Final = (
    "reports/corpus-parametric-runs/"
    "20260823-foundry-production-v12-panel-index/g0-authority-lock-v1.json"
)
EXPECTED_BAKED_IMAGE_EVIDENCE_PATH: Final = Path(
    "/etc/nfl-dfs/foundry-t230-image-evidence-v1.json"
)

AUTHORITATIVE_SLATE_COUNT: Final = 54
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
WORLDS_PER_BLOCK: Final = 10_000
WORLD_COUNT: Final = len(WORLD_BLOCKS) * WORLDS_PER_BLOCK
ENTRY_BUDGETS: Final = (4, 14, 80)
RANKING_DEPTH: Final = 80
FOLD_GATE_TOTAL: Final = 270
FINAL_GATE_TOTAL: Final = 54
FOLD_PASS_MINIMUM: Final = 216
FINAL_PASS_MINIMUM: Final = 44

_IMPLEMENTATION_PATHS: Final = (
    "src/nfl_dfs/research/corpus_extreme_tail_panel_execution.py",
    "scripts/run_corpus_extreme_tail_panel_v1.py",
    "src/nfl_dfs/research/__init__.py",
    "src/nfl_dfs/optimizer/lineup.py",
    "src/nfl_dfs/research/corpus_artifact_source_authority.py",
    "src/nfl_dfs/research/corpus_batch_retrieval_runner_v2.py",
    "src/nfl_dfs/research/corpus_r6_v2_one_slate_execution.py",
    "src/nfl_dfs/research/corpus_v12_import.py",
    "src/nfl_dfs/research/corpus_extreme_tail_census.py",
    "src/nfl_dfs/research/corpus_extreme_tail_retrieval_suite.py",
    "src/nfl_dfs/research/corpus_extreme_tail_support_switch.py",
    "src/nfl_dfs/research/corpus_extreme_tail_panel_release.py",
    "src/nfl_dfs/research/corpus_legal_feasibility.py",
    "src/nfl_dfs/research/corpus_v12_panel_index.py",
    "src/nfl_dfs/research/corpus_parametric_batch.py",
    "src/nfl_dfs/research/corpus_parametric_snapshot.py",
    "src/nfl_dfs/research/corpus_retrieval_engine.py",
    "src/nfl_dfs/research/effective_policy_rule_inventory.py",
    "src/nfl_dfs/research/lr8_exact_solvers.py",
    "src/nfl_dfs/research/lr8_historical_arm.py",
    "src/nfl_dfs/research/lr8_later_period_source.py",
    "src/nfl_dfs/research/lr8_training_source.py",
    "src/nfl_dfs/research/object_identity.py",
    "src/nfl_dfs/research/residual_world_columns.py",
    "src/nfl_dfs/research/residual_world_run_context.py",
)
_CRITICAL_CALLABLE_SPECS: Final = (
    (_IMPLEMENTATION_PATHS[0], "measure_t230_runtime_v1"),
    (_IMPLEMENTATION_PATHS[0], "execute_t230_panel_slate_v1"),
    (_IMPLEMENTATION_PATHS[0], "verify_t230_panel_slate_v1"),
    (_IMPLEMENTATION_PATHS[0], "build_t230_panel_release_v1"),
    (_IMPLEMENTATION_PATHS[1], "GCSExactCreateOnceStore.read"),
    (_IMPLEMENTATION_PATHS[1], "GCSExactCreateOnceStore.publish_create_once"),
    (_IMPLEMENTATION_PATHS[5], "build_fit_candidate_view"),
    (_IMPLEMENTATION_PATHS[6], "reconstruct_one_accepted_v12_slate"),
    (_IMPLEMENTATION_PATHS[7], "reopen_v12_task"),
    (_IMPLEMENTATION_PATHS[7], "reconstruct_v12_task"),
    (_IMPLEMENTATION_PATHS[8], "build_extreme_tail_support_census"),
    (_IMPLEMENTATION_PATHS[9], "run_extreme_tail_retrieval_suite_v1"),
    (_IMPLEMENTATION_PATHS[10], "build_extreme_tail_support_switched_policy_v1"),
    (_IMPLEMENTATION_PATHS[11], "build_t230_panel_execution_manifest_v1"),
    (_IMPLEMENTATION_PATHS[11], "validate_t230_panel_execution_manifest_v1"),
    (_IMPLEMENTATION_PATHS[13], "derive_v12_lane_input"),
    (_IMPLEMENTATION_PATHS[13], "reopen_v12_panel_index"),
    (_IMPLEMENTATION_PATHS[14], "normalize_object_identity"),
    (_IMPLEMENTATION_PATHS[14], "canonical_json_bytes"),
    (_IMPLEMENTATION_PATHS[16], "validate_retrieval_strategy_v2"),
    (_IMPLEMENTATION_PATHS[23], "validate_unlicensed_scientific_payload"),
)
_RUNTIME_ROLES: Final = ("worker", "verifier")
_WORKER_IMPLEMENTATION_BODY: Final = {
    "schema_version": WORKER_IMPLEMENTATION_SCHEMA,
    "implementation_id": "t230-panel-worker-recompute-v1",
    "role": "worker",
    "implementation_paths": list(_IMPLEMENTATION_PATHS),
    "entrypoint": "execute_t230_panel_slate_v1",
    "output_kind": "nonterminal-result-only",
    "science_call_order": [
        "reconstruct_one_accepted_v12_slate",
        "build_extreme_tail_support_census",
        "run_extreme_tail_retrieval_suite_v1",
        "build_extreme_tail_support_switched_policy_v1",
    ],
    "world_blocks": list(WORLD_BLOCKS),
    "worlds_per_block": WORLDS_PER_BLOCK,
    "entry_budgets": list(ENTRY_BUDGETS),
    "ranking_depth": RANKING_DEPTH,
    "realized_outcomes_read": False,
    "acceptance_authority": False,
}
_VERIFIER_IMPLEMENTATION_BODY: Final = {
    "schema_version": VERIFIER_IMPLEMENTATION_SCHEMA,
    "implementation_id": "t230-panel-independent-verifier-recompute-v1",
    "role": "verifier",
    "implementation_paths": list(_IMPLEMENTATION_PATHS),
    "entrypoint": "verify_t230_panel_slate_v1",
    "input_policy": "exact-read-authoritative-inputs-and-nonterminal-result",
    "verification_law": "independent-full-reconstruction-and-byte-equality",
    "science_call_order": [
        "reconstruct_one_accepted_v12_slate",
        "build_extreme_tail_support_census",
        "run_extreme_tail_retrieval_suite_v1",
        "build_extreme_tail_support_switched_policy_v1",
    ],
    "world_blocks": list(WORLD_BLOCKS),
    "worlds_per_block": WORLDS_PER_BLOCK,
    "entry_budgets": list(ENTRY_BUDGETS),
    "ranking_depth": RANKING_DEPTH,
    "realized_outcomes_read": False,
    "outcome_verdict_authority": False,
}
# Independent protocol literals.  Import-time/public-contract replay fails if
# either declarative implementation law drifts under the same implementation id.
EXPECTED_WORKER_IMPLEMENTATION_SHA256: Final = (
    "62dfe722cdc2af28f3cb9b9df8fa693b4312263b770c89fbfa1af830de62b81d"
)
EXPECTED_VERIFIER_IMPLEMENTATION_SHA256: Final = (
    "118532c1752845e96254343242db13e6fd75c0e2f5d54901794c6da34dfcb851"
)

_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
)
_PANEL_RECEIPT_FALSE_FIELDS: Final = tuple(
    field for field in _FALSE_AUTHORITY_FIELDS if field != "r6_freeze_authority"
)
_PANEL_PUBLICATION_RECEIPT_KEYS: Final = frozenset({
    "schema_version",
    "mode",
    "panel_uri",
    "panel_id",
    "panel_object_identity",
    "panel_content_sha256",
    "panel_content_bytes",
    "panel_index_sha256",
    "lane_count",
    "accepted_slate_count",
    "exact_input_replay_verified",
    "published",
    *_PANEL_RECEIPT_FALSE_FIELDS,
    "publication_receipt_sha256",
})
_SECURE_FILE_BINDING_KEYS: Final = frozenset({
    "path", "sha256", "bytes", "owner_uid", "mode_octal"
})
_G0_LANE_LOCK_KEYS: Final = frozenset({
    "lane_ordinal",
    "lane_id",
    "terminal_receipt_file",
    "terminal_receipt_identity",
})
_G0_AUTHORITY_LOCK_KEYS: Final = frozenset({
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
    *_FALSE_AUTHORITY_FIELDS,
    "g0_authority_lock_sha256",
})
_G0_GIT_BINDING_KEYS: Final = frozenset({
    "path",
    "relative_path",
    "source_commit_sha",
    "sha256",
    "bytes",
    "owner_uid",
    "mode_octal",
    "g0_authority_lock_sha256",
    "tracked_at_head",
    "clean_at_head",
})
_IMAGE_EVIDENCE_KEYS: Final = frozenset({
    "schema_version",
    "source_commit_sha",
    "immutable_image",
    "implementation_files",
    "implementation_files_sha256",
    "critical_callables",
    "critical_callables_sha256",
    "runtime_facts",
    "build_provenance",
    "release_image_evidence",
    *_FALSE_AUTHORITY_FIELDS,
    "image_evidence_sha256",
})
_IMAGE_FILE_KEYS: Final = frozenset({"path", "sha256", "bytes"})
_RUNTIME_MEASUREMENT_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "role",
    "implementation_contract",
    "implementation_sha256",
    "measured_source_commit_sha",
    "immutable_image",
    "image_evidence_identity",
    "image_evidence_sha256",
    "measured_files",
    "measured_files_sha256",
    "measured_callables",
    "measured_callables_sha256",
    "runtime_facts",
    "g0_authority_lock_git_binding",
    "g0_authority_lock_git_binding_sha256",
    "git_status_porcelain_sha256",
    "critical_paths_clean",
    "process_instance",
    "process_instance_sha256",
    "checkout_matches_git_blobs",
    "local_image_evidence_matches_pinned_bytes",
    "release_runtime_verified",
    *_FALSE_AUTHORITY_FIELDS,
    "runtime_measurement_sha256",
})
_EXECUTION_AUTHORITY_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "execution_authority_id",
    "manifest_identity",
    "manifest_id",
    "execution_manifest_sha256",
    "panel_publication_receipt_binding",
    "panel_publication_receipt_sha256",
    "g0_authority_lock_git_binding",
    "g0_authority_lock_git_binding_sha256",
    "g0_authority_lock_sha256",
    "fixed_lane_receipt_bindings",
    "fixed_lane_receipt_bindings_sha256",
    "panel_object_identity",
    "panel_index_sha256",
    "image_evidence_identity",
    "image_evidence_sha256",
    "worker_implementation_sha256",
    "verifier_implementation_sha256",
    "runtime_facts",
    "source_commit_sha",
    "immutable_image",
    "output_prefix",
    "panel_publication_cloud_attested",
    "simulated_execution_only",
    *_FALSE_AUTHORITY_FIELDS,
    "execution_authority_sha256",
})
_RESULT_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "execution_mode",
    "execution_authority_identity",
    "execution_authority_sha256",
    "manifest_identity",
    "manifest_id",
    "execution_manifest_sha256",
    "source_ordinal",
    "slate_id",
    "source_member_sha256",
    "source_task_authority_sha256",
    "result_uri",
    "acceptance_uri",
    "worker_runtime_binding",
    "input_artifact_bindings",
    "science_contract_bindings",
    "configuration",
    "verification",
    "support_observation",
    "reconstruction_receipt",
    "support_census",
    "extreme_tail_suite",
    "support_switched_policy",
    *_FALSE_AUTHORITY_FIELDS,
    "t230_slate_result_sha256",
})
_ACCEPTANCE_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "execution_authority_identity",
    "execution_authority_sha256",
    "manifest_identity",
    "manifest_id",
    "execution_manifest_sha256",
    "source_ordinal",
    "slate_id",
    "source_member_sha256",
    "result_identity",
    "result_uri",
    "acceptance_uri",
    "t230_slate_result_sha256",
    "support_census_sha256",
    "extreme_tail_suite_sha256",
    "support_switched_policy_sha256",
    "support_observation",
    "worker_runtime_binding",
    "verifier_runtime_binding",
    "verification",
    *_FALSE_AUTHORITY_FIELDS,
    "t230_slate_acceptance_sha256",
})
_PANEL_RELEASE_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "execution_authority_identity",
    "execution_authority_sha256",
    "manifest_identity",
    "manifest_id",
    "execution_manifest_sha256",
    "panel_object_identity",
    "panel_id",
    "panel_index_sha256",
    "source_commit_sha",
    "immutable_image",
    "output_prefix",
    "panel_release_uri",
    "verifier_runtime_binding",
    "source_member_count",
    "accepted_slate_count",
    "ordered_slate_acceptances",
    "ordered_slate_acceptances_sha256",
    "ordered_result_identities_sha256",
    "support_fraction",
    "fold_boundary",
    "final_fit_boundary",
    "joint_support_boundary_passed",
    "literal_coverage_ge_230_generally_supported",
    "verification",
    *_FALSE_AUTHORITY_FIELDS,
    "t230_panel_release_sha256",
})


class CorpusExtremeTailPanelExecutionError(ValueError):
    """The frozen T230 panel cannot be executed or released exactly."""


ReadExact = Callable[[Mapping[str, object]], bytes]
GitHead = Callable[[Path], str]
GitBlob = Callable[[Path, str, str], bytes]
GitStatus = Callable[[Path, Sequence[str]], bytes]


@dataclass(frozen=True)
class _ExecutionContext:
    manifest_identity: dict[str, object]
    manifest: dict[str, object]
    panel: dict[str, object]


@dataclass(frozen=True)
class _AuthorityContext:
    authority_identity: dict[str, object]
    authority: dict[str, object]
    execution: _ExecutionContext


def _fail(message: str) -> None:
    raise CorpusExtremeTailPanelExecutionError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusExtremeTailPanelExecutionError(
            f"{label} must be a generation-pinned object identity"
        ) from exc


def _image(value: object, *, label: str) -> dict[str, str]:
    try:
        return batch.normalize_image_identity(value, label=label)
    except Exception as exc:
        raise CorpusExtremeTailPanelExecutionError(
            f"{label} must be one digest-pinned image identity"
        ) from exc


def _parse_json(raw: bytes, *, label: str) -> dict[str, object]:
    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        body: dict[str, object] = {}
        for key, value in rows:
            if key in body:
                _fail(f"{label} contains duplicate key {key!r}")
            body[key] = value
        return body

    def reject_constant(value: str) -> object:
        _fail(f"{label} contains non-finite value {value}")

    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusExtremeTailPanelExecutionError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    return dict(_mapping(parsed, label=label))


def _exact_read_json(
    value: object,
    *,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(value, label=f"{label} identity")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} bytes differ from the exact object identity")
    body = _parse_json(raw, label=label)
    if batch.canonical_json_bytes(body) != raw:
        _fail(f"{label} is not canonical JSON bytes")
    return identity, body


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    remainder = {key: item for key, item in value.items() if key != field}
    if batch.canonical_sha256(remainder) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _false_authorities(value: Mapping[str, object], *, label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if value.get(field) is not False:
            _fail(f"{label}.{field} must be false")


def _nested_false_authorities(value: object, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _FALSE_AUTHORITY_FIELDS and item is not False:
                _fail(f"{label}.{key} must be false")
            _nested_false_authorities(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _nested_false_authorities(item, label=f"{label}[{ordinal}]")


def _guard_nested_authority_keys(value: object, *, label: str) -> None:
    """Reject invented authority surfaces before any retained science is used.

    Registered false-authority fields are allowed only at ``False``.  Exact
    authoritative source-lineage keys owned by frozen upstream contracts are
    allowed; outcome/verdict authority synonyms and unregistered licence or
    authority keys fail closed even when their value is ``False``.
    """
    allowed_upstream = {
        "artifact_source_authority_completion",
        "artifact_source_authority_completion_sha256",
        "dose_authority",
        "source_authority",
        "source_authority_sha256",
        "source_task_authority_sha256",
        "task_authority_sha256",
    }
    registered_local_false = {
        "acceptance_authority",
        "outcome_verdict_authority",
    }
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = key.lower()
            if key in _FALSE_AUTHORITY_FIELDS:
                if item is not False:
                    _fail(f"{label}.{key} must be false")
            elif key in registered_local_false:
                if item is not False:
                    _fail(f"{label}.{key} must be false")
            elif (
                "outcome_authority" in normalized
                or "verdict_authority" in normalized
                or normalized.endswith("_licensed")
                or (
                    normalized.endswith("_authority")
                    and key not in allowed_upstream
                )
            ):
                _fail(f"{label}.{key} is an unregistered authority surface")
            _guard_nested_authority_keys(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _guard_nested_authority_keys(item, label=f"{label}[{ordinal}]")


def _commit(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase 40-character Git SHA")
    return value


def _implementation_contract(role: str) -> dict[str, object]:
    if role == "worker":
        body = dict(_WORKER_IMPLEMENTATION_BODY)
        expected = EXPECTED_WORKER_IMPLEMENTATION_SHA256
    elif role == "verifier":
        body = dict(_VERIFIER_IMPLEMENTATION_BODY)
        expected = EXPECTED_VERIFIER_IMPLEMENTATION_SHA256
    else:
        _fail("runtime role must be worker or verifier")
    actual = batch.canonical_sha256(body)
    if actual != expected:
        _fail(f"frozen {role} implementation contract drifted")
    body["implementation_sha256"] = actual
    return body


def frozen_t230_worker_implementation_v1() -> dict[str, object]:
    """Return the literal, self-verifying worker implementation contract."""
    return _implementation_contract("worker")


def frozen_t230_verifier_implementation_v1() -> dict[str, object]:
    """Return the literal, self-verifying independent verifier contract."""
    return _implementation_contract("verifier")


def _runtime_facts() -> dict[str, object]:
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_cache_tag": sys.implementation.cache_tag,
        "python_executable_name": Path(sys.executable).name,
        "numpy_version": np.__version__,
        "numpy_float64_dtype": np.dtype(np.float64).str,
        "numpy_int64_dtype": np.dtype(np.int64).str,
        "byteorder": sys.byteorder,
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
    }


def _callable_node(tree: ast.AST, qualified_name: str) -> ast.AST:
    parts = qualified_name.split(".")
    scope = list(getattr(tree, "body", []))
    node: ast.AST | None = None
    for ordinal, part in enumerate(parts):
        candidates = [
            item for item in scope
            if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == part
        ]
        if len(candidates) != 1:
            _fail(f"critical callable {qualified_name!r} is not unique")
        node = candidates[0]
        if ordinal < len(parts) - 1:
            if not isinstance(node, ast.ClassDef):
                _fail(f"critical callable scope {qualified_name!r} differs")
            scope = list(node.body)
    if node is None or not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        _fail(f"critical callable {qualified_name!r} is not a function")
    return node


def _critical_callable_rows(
    files: Mapping[str, bytes],
) -> list[dict[str, object]]:
    parsed: dict[str, tuple[str, ast.AST]] = {}
    rows: list[dict[str, object]] = []
    for relative_path, qualified_name in _CRITICAL_CALLABLE_SPECS:
        if relative_path not in files:
            _fail("critical callable file is absent from measured implementation")
        if relative_path not in parsed:
            try:
                text = files[relative_path].decode("utf-8")
                parsed[relative_path] = (text, ast.parse(text, filename=relative_path))
            except (UnicodeDecodeError, SyntaxError) as exc:
                raise CorpusExtremeTailPanelExecutionError(
                    f"critical implementation file {relative_path} is not parseable"
                ) from exc
        text, tree = parsed[relative_path]
        node = _callable_node(tree, qualified_name)
        segment = ast.get_source_segment(text, node)
        if type(segment) is not str or not segment:
            _fail(f"critical callable {qualified_name!r} source is unavailable")
        raw = segment.encode("utf-8")
        rows.append({
            "path": relative_path,
            "qualified_name": qualified_name,
            "source_sha256": sha256(raw).hexdigest(),
            "source_bytes": len(raw),
        })
    return rows


def _measure_process_instance() -> dict[str, object]:
    pid = os.getpid()
    try:
        stat_raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="ascii"
        ).strip()
        namespace_inode = os.stat("/proc/self/ns/pid").st_ino
    except (OSError, UnicodeError) as exc:
        raise CorpusExtremeTailPanelExecutionError(
            "local process instance evidence is unavailable"
        ) from exc
    closing = stat_raw.rfind(")")
    fields_after_command = stat_raw[closing + 2 :].split()
    if closing < 1 or len(fields_after_command) < 20:
        _fail("local process stat evidence differs")
    start_ticks_text = fields_after_command[19]
    if not start_ticks_text.isdigit():
        _fail("local process start ticks differ")
    body = {
        "evidence_class": "linux-proc-pid-start-boot-v1",
        "pid": pid,
        "process_start_ticks": int(start_ticks_text),
        "boot_id": boot_id,
        "pid_namespace_inode": namespace_inode,
    }
    body["process_instance_sha256"] = batch.canonical_sha256(body)
    return body


def _validate_image_evidence(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="immutable image evidence"))
    _exact_keys(item, _IMAGE_EVIDENCE_KEYS, label="immutable image evidence")
    _false_authorities(item, label="immutable image evidence")
    _guard_nested_authority_keys(item, label="immutable image evidence")
    _validate_self_hash(
        item, field="image_evidence_sha256", label="immutable image evidence"
    )
    source_commit = _commit(
        item.get("source_commit_sha"), label="image evidence source commit"
    )
    image = _image(item.get("immutable_image"), label="image evidence image")
    rows = _sequence(
        item.get("implementation_files"), label="image evidence files"
    )
    if len(rows) != len(_IMPLEMENTATION_PATHS):
        _fail("image evidence must bind every frozen implementation file")
    normalized_rows: list[dict[str, object]] = []
    for ordinal, expected_path in enumerate(_IMPLEMENTATION_PATHS):
        row = dict(_mapping(rows[ordinal], label=f"image file[{ordinal}]"))
        _exact_keys(row, _IMAGE_FILE_KEYS, label=f"image file[{ordinal}]")
        if (
            row.get("path") != expected_path
            or type(row.get("bytes")) is not int
            or int(row["bytes"]) < 1
        ):
            _fail("image evidence implementation file order/size differs")
        _sha(row.get("sha256"), label=f"image file[{ordinal}] SHA")
        normalized_rows.append(row)
    if (
        item.get("schema_version") != IMAGE_EVIDENCE_SCHEMA
        or item.get("release_image_evidence") is not True
        or item.get("implementation_files_sha256")
        != batch.canonical_sha256(normalized_rows)
    ):
        _fail("immutable image evidence frozen surface differs")
    callable_rows = _sequence(
        item.get("critical_callables"), label="image critical callables"
    )
    if (
        len(callable_rows) != len(_CRITICAL_CALLABLE_SPECS)
        or item.get("critical_callables_sha256")
        != batch.canonical_sha256(callable_rows)
    ):
        _fail("immutable image critical-callable catalog differs")
    for ordinal, ((expected_path, expected_name), value) in enumerate(
        zip(_CRITICAL_CALLABLE_SPECS, callable_rows, strict=True)
    ):
        row = _mapping(value, label=f"image critical callable[{ordinal}]")
        if frozenset(row) != {
            "path", "qualified_name", "source_sha256", "source_bytes"
        } or (
            row.get("path") != expected_path
            or row.get("qualified_name") != expected_name
            or type(row.get("source_bytes")) is not int
            or int(row["source_bytes"]) < 1
        ):
            _fail("immutable image critical-callable row differs")
        _sha(row.get("source_sha256"), label="image critical callable SHA")
    if item.get("runtime_facts") != _runtime_facts():
        _fail("immutable image runtime facts differ from this runtime")
    provenance = _mapping(
        item.get("build_provenance"), label="image build provenance"
    )
    if frozenset(provenance) != {
        "builder_id",
        "source_commit_sha",
        "immutable_image_digest",
        "implementation_files_sha256",
        "critical_callables_sha256",
        "runtime_facts_sha256",
    } or (
        provenance.get("builder_id")
        != "cloud-build-immutable-image-evidence-v1"
        or provenance.get("source_commit_sha") != source_commit
        or provenance.get("immutable_image_digest") != image["digest"]
        or provenance.get("implementation_files_sha256")
        != item.get("implementation_files_sha256")
        or provenance.get("critical_callables_sha256")
        != item.get("critical_callables_sha256")
        or provenance.get("runtime_facts_sha256")
        != batch.canonical_sha256(item.get("runtime_facts"))
    ):
        _fail("immutable image build provenance differs")
    return item


def runtime_measurement_uri_for_output_prefix(
    output_prefix: str, *, role: str, source_ordinal: int | None = None
) -> str:
    if type(output_prefix) is not str or not output_prefix.endswith("/"):
        _fail("output prefix must be one canonical trailing-slash prefix")
    if role not in _RUNTIME_ROLES:
        _fail("runtime role must be worker or verifier")
    filename = (
        WORKER_RUNTIME_FILENAME if role == "worker" else VERIFIER_RUNTIME_FILENAME
    )
    if source_ordinal is None:
        return output_prefix + "runtime/templates/" + filename
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("runtime source ordinal must be one exact integer in 0..53")
    return output_prefix + f"slates/{source_ordinal:02d}/runtime/" + filename


def image_evidence_uri_for_output_prefix(output_prefix: str) -> str:
    if type(output_prefix) is not str or not output_prefix.endswith("/"):
        _fail("output prefix must be one canonical trailing-slash prefix")
    return output_prefix + "runtime/" + IMAGE_EVIDENCE_FILENAME


def _secure_read_regular_file(
    path: Path, *, label: str
) -> tuple[bytes, dict[str, object]]:
    """Read one owner-controlled file through no-follow directory FDs.

    The final file and every parent component are opened with ``O_NOFOLLOW``.
    The open descriptor, its directory entry, link count, owner, safe mode and
    stable metadata are checked before any bytes can become authority.
    """
    if (
        not path.is_absolute()
        or path.name in {"", ".", ".."}
        or not hasattr(os, "O_NOFOLLOW")
    ):
        _fail(f"{label} must be one absolute no-follow regular file")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory_fd: int | None = None
    file_fd: int | None = None
    try:
        directory_fd = os.open("/", directory_flags)
        for component in path.parts[1:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(path.name, file_flags, dir_fd=directory_fd)
        before = os.fstat(file_fd)
        entry = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        mode = stat.S_IMODE(before.st_mode)
        unsafe_mode_bits = 0o7000 | 0o0111 | 0o0022
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(entry.st_mode)
            or (before.st_dev, before.st_ino) != (entry.st_dev, entry.st_ino)
            or before.st_nlink != 1
            or entry.st_nlink != 1
            or before.st_uid != os.geteuid()
            or entry.st_uid != os.geteuid()
            or not (mode & 0o400)
            or mode & unsafe_mode_bits
        ):
            _fail(f"{label} owner/mode/link/regular-file checks failed")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks)
        after = os.fstat(file_fd)
        if (
            not raw
            or len(raw) != before.st_size
            or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
        ):
            _fail(f"{label} changed during its no-follow read")
        binding = {
            "path": str(path),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
            "owner_uid": before.st_uid,
            "mode_octal": f"{mode:04o}",
        }
        return raw, binding
    except CorpusExtremeTailPanelExecutionError:
        raise
    except OSError as exc:
        raise CorpusExtremeTailPanelExecutionError(
            f"{label} no-follow read failed"
        ) from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _read_local_exact(path: Path, *, label: str) -> bytes:
    return _secure_read_regular_file(path, label=label)[0]


def measure_t230_runtime_v1(
    *,
    role: str,
    output_prefix: str,
    repository_root: Path,
    image_evidence_identity: Mapping[str, object],
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Measure checkout bytes and an image-baked evidence receipt.

    Only the fixed image-baked path can confer release eligibility.  A missing
    or differing baked file, or a dirty critical path, produces mechanics-only
    evidence and can never issue a slate acceptance or aggregate release.
    """
    contract = _implementation_contract(role)
    normalized_evidence_identity, evidence_body = _exact_read_json(
        image_evidence_identity,
        read_exact=read_exact,
        label="generation-pinned image evidence",
    )
    evidence = _validate_image_evidence(evidence_body)
    if normalized_evidence_identity["uri"] != image_evidence_uri_for_output_prefix(
        output_prefix
    ):
        _fail("image evidence URI differs from the deterministic run prefix")
    if not repository_root.is_absolute() or not repository_root.is_dir():
        _fail("repository root must be one absolute directory")
    measured_commit = _commit(git_head(repository_root), label="measured Git HEAD")
    if measured_commit != evidence["source_commit_sha"]:
        _fail("measured Git HEAD differs from immutable image evidence")
    _lock, g0_git_binding = _tracked_g0_authority_lock_v1(
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if g0_git_binding["source_commit_sha"] != measured_commit:
        _fail("tracked G0 authority lock commit differs from measured Git HEAD")
    expected_rows = _sequence(
        evidence["implementation_files"], label="image evidence files"
    )
    rows: list[dict[str, object]] = []
    measured_file_bytes: dict[str, bytes] = {}
    for ordinal, relative_path in enumerate(_IMPLEMENTATION_PATHS):
        path = repository_root / relative_path
        raw = _read_local_exact(path, label=f"implementation file[{ordinal}]")
        committed_raw = git_blob(repository_root, measured_commit, relative_path)
        if type(committed_raw) is not bytes or committed_raw != raw:
            _fail("checked-out implementation bytes differ from measured Git blob")
        row = {
            "path": relative_path,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if row != expected_rows[ordinal]:
            _fail("checked-out implementation bytes differ from image evidence")
        rows.append(row)
        measured_file_bytes[relative_path] = raw
    measured_callables = _critical_callable_rows(measured_file_bytes)
    if (
        measured_callables != evidence["critical_callables"]
        or batch.canonical_sha256(measured_callables)
        != evidence["critical_callables_sha256"]
    ):
        _fail("measured critical callable sources differ from image evidence")
    status_raw = git_status(repository_root, _IMPLEMENTATION_PATHS)
    if type(status_raw) is not bytes:
        _fail("critical-path Git status must be exact bytes")
    critical_paths_clean = status_raw == b""
    local_match = False
    if EXPECTED_BAKED_IMAGE_EVIDENCE_PATH.exists():
        local_raw = _read_local_exact(
            EXPECTED_BAKED_IMAGE_EVIDENCE_PATH, label="baked image evidence"
        )
        expected_raw = batch.canonical_json_bytes(evidence)
        if local_raw not in {expected_raw, expected_raw + b"\n"}:
            _fail("baked image evidence bytes differ from generation-pinned evidence")
        local_match = True
    process_instance = _measure_process_instance()
    release_verified = local_match and critical_paths_clean
    body: dict[str, object] = {
        "schema_version": RUNTIME_MEASUREMENT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "role": role,
        "implementation_contract": contract,
        "implementation_sha256": contract["implementation_sha256"],
        "measured_source_commit_sha": measured_commit,
        "immutable_image": evidence["immutable_image"],
        "image_evidence_identity": normalized_evidence_identity,
        "image_evidence_sha256": evidence["image_evidence_sha256"],
        "measured_files": rows,
        "measured_files_sha256": batch.canonical_sha256(rows),
        "measured_callables": measured_callables,
        "measured_callables_sha256": batch.canonical_sha256(measured_callables),
        "runtime_facts": _runtime_facts(),
        "g0_authority_lock_git_binding": g0_git_binding,
        "g0_authority_lock_git_binding_sha256": batch.canonical_sha256(
            g0_git_binding
        ),
        "git_status_porcelain_sha256": sha256(status_raw).hexdigest(),
        "critical_paths_clean": critical_paths_clean,
        "process_instance": process_instance,
        "process_instance_sha256": process_instance["process_instance_sha256"],
        "checkout_matches_git_blobs": True,
        "local_image_evidence_matches_pinned_bytes": local_match,
        "release_runtime_verified": release_verified,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["runtime_measurement_sha256"] = batch.canonical_sha256(body)
    return body


def validate_t230_runtime_measurement_v1(
    value: object,
    *,
    role: str,
    output_prefix: str,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    item = dict(_mapping(value, label=f"{role} runtime measurement"))
    _exact_keys(item, _RUNTIME_MEASUREMENT_KEYS, label="runtime measurement")
    _false_authorities(item, label="runtime measurement")
    _guard_nested_authority_keys(item, label="runtime measurement")
    _validate_self_hash(
        item, field="runtime_measurement_sha256", label="runtime measurement"
    )
    expected = measure_t230_runtime_v1(
        role=role,
        output_prefix=output_prefix,
        repository_root=repository_root,
        image_evidence_identity=_mapping(
            item.get("image_evidence_identity"), label="image evidence identity"
        ),
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail(f"{role} runtime measurement differs from fresh local replay")
    return expected


def _validate_published_runtime_measurement_v1(
    value: object,
    *,
    role: str,
    output_prefix: str,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Replay durable runtime facts without pretending an exited PID is live."""
    item = dict(_mapping(value, label=f"published {role} runtime measurement"))
    _exact_keys(item, _RUNTIME_MEASUREMENT_KEYS, label="runtime measurement")
    _false_authorities(item, label="runtime measurement")
    _guard_nested_authority_keys(item, label="runtime measurement")
    _validate_self_hash(
        item, field="runtime_measurement_sha256", label="runtime measurement"
    )
    contract = _implementation_contract(role)
    if (
        item.get("schema_version") != RUNTIME_MEASUREMENT_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
        or item.get("role") != role
        or item.get("implementation_contract") != contract
        or item.get("implementation_sha256") != contract["implementation_sha256"]
        or item.get("runtime_facts") != _runtime_facts()
        or item.get("checkout_matches_git_blobs") is not True
        or item.get("critical_paths_clean") is not True
        or item.get("release_runtime_verified") is not True
        or item.get("local_image_evidence_matches_pinned_bytes") is not True
    ):
        _fail(f"published {role} runtime frozen surface differs")
    evidence_identity, evidence_body = _exact_read_json(
        item.get("image_evidence_identity"),
        read_exact=read_exact,
        label="published runtime image evidence",
    )
    evidence = _validate_image_evidence(evidence_body)
    if (
        evidence_identity["uri"] != image_evidence_uri_for_output_prefix(output_prefix)
        or item.get("image_evidence_sha256") != evidence.get("image_evidence_sha256")
        or item.get("immutable_image") != evidence.get("immutable_image")
        or item.get("measured_source_commit_sha") != evidence.get("source_commit_sha")
        or item.get("measured_files") != evidence.get("implementation_files")
        or item.get("measured_files_sha256")
        != evidence.get("implementation_files_sha256")
        or item.get("measured_callables") != evidence.get("critical_callables")
        or item.get("measured_callables_sha256")
        != evidence.get("critical_callables_sha256")
        or item.get("git_status_porcelain_sha256") != sha256(b"").hexdigest()
    ):
        _fail(f"published {role} runtime code/image lineage differs")
    g0_binding = dict(
        _mapping(
            item.get("g0_authority_lock_git_binding"),
            label="published runtime G0 lock binding",
        )
    )
    _exact_keys(
        g0_binding, _G0_GIT_BINDING_KEYS, label="published runtime G0 lock binding"
    )
    _secure_file_lock_projection(
        {key: g0_binding[key] for key in _SECURE_FILE_BINDING_KEYS},
        label="published runtime G0 lock file",
    )
    if (
        g0_binding.get("path") != str(FROZEN_G0_AUTHORITY_LOCK_PATH)
        or g0_binding.get("relative_path")
        != FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH
        or g0_binding.get("source_commit_sha")
        != item.get("measured_source_commit_sha")
        or g0_binding.get("tracked_at_head") is not True
        or g0_binding.get("clean_at_head") is not True
        or item.get("g0_authority_lock_git_binding_sha256")
        != batch.canonical_sha256(g0_binding)
    ):
        _fail(f"published {role} runtime G0 lock lineage differs")
    _sha(
        g0_binding.get("g0_authority_lock_sha256"),
        label="published runtime G0 lock SHA",
    )
    process = dict(_mapping(item.get("process_instance"), label="process instance"))
    if frozenset(process) != {
        "evidence_class",
        "pid",
        "process_start_ticks",
        "boot_id",
        "pid_namespace_inode",
        "process_instance_sha256",
    }:
        _fail("process instance fields differ")
    _validate_self_hash(
        process, field="process_instance_sha256", label="process instance"
    )
    if (
        process.get("evidence_class") != "linux-proc-pid-start-boot-v1"
        or type(process.get("pid")) is not int
        or int(process["pid"]) < 1
        or type(process.get("process_start_ticks")) is not int
        or int(process["process_start_ticks"]) < 1
        or type(process.get("boot_id")) is not str
        or not process["boot_id"]
        or type(process.get("pid_namespace_inode")) is not int
        or int(process["pid_namespace_inode"]) < 1
        or item.get("process_instance_sha256")
        != process.get("process_instance_sha256")
    ):
        _fail("process instance evidence differs")
    return item


def manifest_uri_for_output_prefix(output_prefix: str) -> str:
    """Derive the sole execution-manifest URI under a frozen output prefix."""
    if type(output_prefix) is not str or not output_prefix.endswith("/"):
        _fail("output prefix must be one canonical trailing-slash prefix")
    return output_prefix + MANIFEST_FILENAME


def authority_uri_for_output_prefix(output_prefix: str) -> str:
    """Derive the sole release-bearing execution-authority URI."""
    if type(output_prefix) is not str or not output_prefix.endswith("/"):
        _fail("output prefix must be one canonical trailing-slash prefix")
    return output_prefix + AUTHORITY_FILENAME


def panel_release_uri_for_output_prefix(output_prefix: str) -> str:
    """Derive the sole aggregate-release URI under a frozen output prefix."""
    if type(output_prefix) is not str or not output_prefix.endswith("/"):
        _fail("output prefix must be one canonical trailing-slash prefix")
    return output_prefix + PANEL_RELEASE_FILENAME


def _replay_raw_published_v12_panel_v1(
    *, read_exact: ReadExact
) -> tuple[dict[str, object], dict[str, object], dict[str, object], list[dict[str, object]]]:
    """Mechanically replay the raw G0 files; this alone grants no authority."""
    receipt_raw, receipt_file_binding = _secure_read_regular_file(
        FROZEN_G0_PUBLICATION_RECEIPT_PATH,
        label="fixed G0 publication receipt",
    )
    receipt_body = _parse_json(receipt_raw, label="v12 panel publication receipt")
    canonical_receipt = batch.canonical_json_bytes(receipt_body)
    if receipt_raw not in {canonical_receipt, canonical_receipt + b"\n"}:
        _fail("fixed G0 publication receipt is not canonical local JSON")
    receipt = dict(_mapping(receipt_body, label="v12 panel publication receipt"))
    _exact_keys(
        receipt,
        _PANEL_PUBLICATION_RECEIPT_KEYS,
        label="v12 panel publication receipt",
    )
    _validate_self_hash(
        receipt,
        field="publication_receipt_sha256",
        label="v12 panel publication receipt",
    )
    for field in _PANEL_RECEIPT_FALSE_FIELDS:
        if receipt.get(field) is not False:
            _fail(f"v12 panel publication receipt.{field} must be false")
    if (
        receipt.get("schema_version") != PANEL_PUBLICATION_RECEIPT_SCHEMA
        or receipt.get("mode") != "create_once"
        or receipt.get("published") is not True
        or receipt.get("exact_input_replay_verified") is not True
        or receipt.get("lane_count") != 2
        or receipt.get("accepted_slate_count") != AUTHORITATIVE_SLATE_COUNT
    ):
        _fail("v12 panel publication receipt is not the published 54-slate receipt")
    panel_identity = _identity(
        receipt.get("panel_object_identity"), label="published v12 panel identity"
    )
    if panel_identity["uri"] != FROZEN_G0_PANEL_URI:
        _fail("published v12 panel URI differs from the frozen G0 runbook")
    _, panel_body = _exact_read_json(
        panel_identity, read_exact=read_exact, label="published v12 panel"
    )
    if (
        panel_identity["uri"] != receipt.get("panel_uri")
        or panel_identity["sha256"] != receipt.get("panel_content_sha256")
        or panel_identity["bytes"] != receipt.get("panel_content_bytes")
        or panel_body.get("panel_id") != receipt.get("panel_id")
        or panel_body.get("panel_index_sha256")
        != receipt.get("panel_index_sha256")
        or panel_body.get("lane_count") != receipt.get("lane_count")
        or panel_body.get("accepted_slate_count")
        != receipt.get("accepted_slate_count")
    ):
        _fail("v12 panel publication receipt differs from its exact panel bytes")
    lanes = _sequence(panel_body.get("lanes"), label="published panel lanes")
    if len(lanes) != 2:
        _fail("published panel must retain exactly two lane rows")
    terminal_identities = [
        _identity(
            _mapping(value, label=f"published panel lane[{ordinal}]").get(
                "terminal_receipt_identity"
            ),
            label=f"published panel lane[{ordinal}] terminal identity",
        )
        for ordinal, value in enumerate(lanes)
    ]
    semantic_panel_id = "v12:" + batch.canonical_sha256(terminal_identities)
    if (
        panel_body.get("panel_id") != semantic_panel_id
        or receipt.get("panel_id") != semantic_panel_id
    ):
        _fail("published v12 panel semantic ID differs from ordered terminals")
    lane_inputs: list[dict[str, object]] = []
    lane_receipt_bindings: list[dict[str, object]] = []
    try:
        for lane_ordinal, lane_value in enumerate(lanes):
            lane = _mapping(lane_value, label=f"published panel lane[{lane_ordinal}]")
            lane_path = FROZEN_G0_LANE_RECEIPT_PATHS[lane_ordinal]
            lane_raw, lane_file_binding = _secure_read_regular_file(
                lane_path, label=f"fixed G0 lane[{lane_ordinal}] receipt"
            )
            lane_body = _parse_json(lane_raw, label=f"fixed lane[{lane_ordinal}] receipt")
            if lane_raw not in {
                batch.canonical_json_bytes(lane_body),
                batch.canonical_json_bytes(lane_body) + b"\n",
            }:
                _fail("fixed G0 lane receipt is not canonical local JSON")
            if (
                frozenset(lane_body) != {
                    "schema_version", "batch_mode", "task_count",
                    "matrix_cell_count", "batch_completion", "batch_acceptance",
                    "final_output_inventory_sha256", "final_output_object_count",
                    "complete", "accepted",
                }
                or lane_body.get("schema_version")
                != "corpus-parametric-batch-accepted/v1"
                or lane_body.get("batch_mode") != lane.get("batch_mode")
                or lane_body.get("task_count") != lane.get("expected_task_count")
                or lane_body.get("matrix_cell_count")
                != int(lane.get("expected_task_count", -1))
                * len(batch.PARAMETER_SET_ORDER)
                or lane_body.get("batch_completion")
                != lane.get("batch_completion_identity")
                or lane_body.get("complete") is not True
                or lane_body.get("accepted") is not True
            ):
                _fail("fixed G0 lane terminal envelope differs")
            terminal_identity = _identity(
                lane_body.get("batch_acceptance"),
                label=f"fixed lane[{lane_ordinal}] terminal identity",
            )
            if terminal_identity != lane.get("terminal_receipt_identity"):
                _fail("published panel lane differs from frozen local terminal")
            lane_receipt_bindings.append({
                **lane_file_binding,
                "lane_ordinal": lane_ordinal,
                "terminal_receipt_identity": terminal_identity,
            })
            lane_inputs.append(panel_index.derive_v12_lane_input(
                lane_ordinal=lane_ordinal,
                lane_id=str(lane.get("lane_id")),
                terminal_receipt_identity=_mapping(
                    lane.get("terminal_receipt_identity"),
                    label="lane terminal receipt identity",
                ),
                read_exact=read_exact,
            ))
        reopened = panel_index.reopen_v12_panel_index(
            panel_index_identity=panel_identity,
            lane_inputs=lane_inputs,
            read_exact=read_exact,
        )
    except Exception as exc:
        raise CorpusExtremeTailPanelExecutionError(
            f"authoritative v12 panel publication replay failed: {exc}"
        ) from exc
    if batch.canonical_json_bytes(reopened) != batch.canonical_json_bytes(panel_body):
        _fail("published v12 panel differs after two-lane authoritative replay")
    receipt_binding = {
        **receipt_file_binding,
        "publication_receipt_sha256": receipt["publication_receipt_sha256"],
    }
    return receipt_binding, receipt, dict(reopened), lane_receipt_bindings


def _secure_file_lock_projection(value: object, *, label: str) -> dict[str, object]:
    item = dict(_mapping(value, label=label))
    _exact_keys(item, _SECURE_FILE_BINDING_KEYS, label=label)
    if (
        type(item.get("path")) is not str
        or not str(item["path"]).startswith("/")
        or type(item.get("bytes")) is not int
        or int(item["bytes"]) < 1
        or type(item.get("owner_uid")) is not int
        or int(item["owner_uid"]) < 0
        or type(item.get("mode_octal")) is not str
        or len(str(item["mode_octal"])) != 4
        or any(character not in "01234567" for character in str(item["mode_octal"]))
    ):
        _fail(f"{label} secure file metadata differs")
    _sha(item.get("sha256"), label=f"{label} SHA")
    return item


def build_g0_authority_lock_v1(*, read_exact: ReadExact) -> dict[str, object]:
    """Build the reviewable lock from the official post-G0 raw files.

    This builder is mechanics-only.  Its output becomes execution input only
    after it is reviewed, committed at the literal lock path, clean at HEAD,
    and replayed by :func:`replay_published_v12_panel_v1`.
    """
    receipt_binding, receipt, published_panel, lane_bindings = (
        _replay_raw_published_v12_panel_v1(read_exact=read_exact)
    )
    receipt_file = _secure_file_lock_projection(
        {key: receipt_binding[key] for key in _SECURE_FILE_BINDING_KEYS},
        label="official publication receipt file",
    )
    lanes = _sequence(published_panel.get("lanes"), label="published panel lanes")
    lane_rows: list[dict[str, object]] = []
    terminal_identities: list[dict[str, object]] = []
    for ordinal, (lane_value, binding_value) in enumerate(
        zip(lanes, lane_bindings, strict=True)
    ):
        lane = _mapping(lane_value, label=f"published panel lane[{ordinal}]")
        binding = _mapping(binding_value, label=f"lane binding[{ordinal}]")
        file_binding = _secure_file_lock_projection(
            {key: binding[key] for key in _SECURE_FILE_BINDING_KEYS},
            label=f"lane terminal receipt file[{ordinal}]",
        )
        terminal = _identity(
            binding.get("terminal_receipt_identity"),
            label=f"lane terminal identity[{ordinal}]",
        )
        terminal_identities.append(terminal)
        lane_rows.append({
            "lane_ordinal": ordinal,
            "lane_id": lane.get("lane_id"),
            "terminal_receipt_file": file_binding,
            "terminal_receipt_identity": terminal,
        })
    semantic_panel_id = "v12:" + batch.canonical_sha256(terminal_identities)
    seed = {
        "official_publication_receipt_file": receipt_file,
        "lane_terminal_receipts": lane_rows,
        "panel_object_identity": receipt["panel_object_identity"],
    }
    body: dict[str, object] = {
        "schema_version": G0_AUTHORITY_LOCK_SCHEMA,
        "lock_id": "foundry-v12-g0:" + batch.canonical_sha256(seed),
        "official_publication_receipt_file": receipt_file,
        "publication_receipt_sha256": receipt["publication_receipt_sha256"],
        "lane_terminal_receipts": lane_rows,
        "ordered_terminal_receipt_identities_sha256": batch.canonical_sha256(
            terminal_identities
        ),
        "panel_uri": FROZEN_G0_PANEL_URI,
        "panel_object_identity": receipt["panel_object_identity"],
        "panel_id": semantic_panel_id,
        "panel_index_sha256": receipt["panel_index_sha256"],
        "accepted_slate_count": AUTHORITATIVE_SLATE_COUNT,
        "review_and_git_commit_required_before_prepare": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["g0_authority_lock_sha256"] = batch.canonical_sha256(body)
    return body


def validate_g0_authority_lock_v1(
    value: object, *, read_exact: ReadExact
) -> dict[str, object]:
    item = dict(_mapping(value, label="G0 authority lock"))
    _exact_keys(item, _G0_AUTHORITY_LOCK_KEYS, label="G0 authority lock")
    _false_authorities(item, label="G0 authority lock")
    _guard_nested_authority_keys(item, label="G0 authority lock")
    _validate_self_hash(
        item, field="g0_authority_lock_sha256", label="G0 authority lock"
    )
    if (
        item.get("schema_version") != G0_AUTHORITY_LOCK_SCHEMA
        or item.get("panel_uri") != FROZEN_G0_PANEL_URI
        or item.get("accepted_slate_count") != AUTHORITATIVE_SLATE_COUNT
        or item.get("review_and_git_commit_required_before_prepare") is not True
    ):
        _fail("G0 authority lock frozen surface differs")
    _secure_file_lock_projection(
        item.get("official_publication_receipt_file"),
        label="locked official publication receipt file",
    )
    lane_rows = _sequence(
        item.get("lane_terminal_receipts"), label="locked lane terminal receipts"
    )
    if len(lane_rows) != 2:
        _fail("G0 authority lock must bind exactly two lane receipts")
    for ordinal, value in enumerate(lane_rows):
        row = dict(_mapping(value, label=f"locked lane[{ordinal}]"))
        _exact_keys(row, _G0_LANE_LOCK_KEYS, label=f"locked lane[{ordinal}]")
        if row.get("lane_ordinal") != ordinal or row.get("lane_id") not in {
            "v12a", "v12b"
        }:
            _fail("G0 authority lock lane order differs")
        _secure_file_lock_projection(
            row.get("terminal_receipt_file"),
            label=f"locked lane file[{ordinal}]",
        )
        _identity(
            row.get("terminal_receipt_identity"),
            label=f"locked lane terminal identity[{ordinal}]",
        )
    expected = build_g0_authority_lock_v1(read_exact=read_exact)
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("G0 authority lock differs from exact raw-file/panel replay")
    return expected


def _tracked_g0_authority_lock_v1(
    *,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> tuple[dict[str, object], dict[str, object]]:
    raw, file_binding = _secure_read_regular_file(
        FROZEN_G0_AUTHORITY_LOCK_PATH, label="tracked G0 authority lock"
    )
    body = _parse_json(raw, label="tracked G0 authority lock")
    if raw != batch.canonical_json_bytes(body) + b"\n":
        _fail("tracked G0 authority lock must be canonical JSON plus one newline")
    commit = _commit(git_head(repository_root), label="G0 lock Git HEAD")
    try:
        committed_raw = git_blob(
            repository_root, commit, FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH
        )
        status_raw = git_status(
            repository_root, (FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH,)
        )
    except Exception as exc:
        raise CorpusExtremeTailPanelExecutionError(
            "G0 authority lock is not tracked at current HEAD"
        ) from exc
    if type(committed_raw) is not bytes or committed_raw != raw:
        _fail("G0 authority lock bytes differ from current Git HEAD")
    if type(status_raw) is not bytes or status_raw != b"":
        _fail("G0 authority lock must be clean at current Git HEAD")
    lock = validate_g0_authority_lock_v1(body, read_exact=read_exact)
    binding = {
        **file_binding,
        "relative_path": FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH,
        "source_commit_sha": commit,
        "g0_authority_lock_sha256": lock["g0_authority_lock_sha256"],
        "tracked_at_head": True,
        "clean_at_head": True,
    }
    _exact_keys(binding, _G0_GIT_BINDING_KEYS, label="G0 lock Git binding")
    return lock, binding


def replay_published_v12_panel_v1(
    *,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
]:
    """Replay the panel only through its reviewed, tracked G0 lock."""
    lock, git_binding = _tracked_g0_authority_lock_v1(
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    receipt_binding, receipt, published_panel, lane_bindings = (
        _replay_raw_published_v12_panel_v1(read_exact=read_exact)
    )
    if (
        lock["official_publication_receipt_file"]
        != {key: receipt_binding[key] for key in _SECURE_FILE_BINDING_KEYS}
        or lock["panel_object_identity"] != receipt["panel_object_identity"]
        or lock["panel_id"] != published_panel["panel_id"]
    ):
        _fail("tracked G0 lock differs from replayed publication/panel")
    return receipt_binding, receipt, published_panel, lane_bindings, git_binding


def build_t230_execution_authority_v1(
    *,
    manifest_identity: Mapping[str, object],
    image_evidence_identity: Mapping[str, object],
    read_exact: ReadExact,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Bind the sole frozen local G0 receipt and measured implementation law."""
    receipt_binding, receipt, published_panel, lane_bindings, g0_git_binding = (
        replay_published_v12_panel_v1(
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    )
    normalized_manifest_identity, manifest = _exact_read_json(
        manifest_identity,
        read_exact=read_exact,
        label="T230 base execution manifest",
    )
    try:
        replayed_manifest = manifest_contract.validate_t230_panel_execution_manifest_v1(
            manifest,
            panel_index=published_panel,
            panel_index_identity=receipt["panel_object_identity"],
            source_commit_sha=str(manifest.get("source_commit_sha")),
            immutable_image=_mapping(
                manifest.get("immutable_image"), label="manifest immutable image"
            ),
            output_prefix=str(manifest.get("output_prefix")),
        )
    except Exception as exc:
        raise CorpusExtremeTailPanelExecutionError(
            f"T230 base manifest replay failed: {exc}"
        ) from exc
    if batch.canonical_json_bytes(replayed_manifest) != batch.canonical_json_bytes(
        manifest
    ):
        _fail("T230 base manifest differs after published-panel replay")
    output_prefix = str(manifest["output_prefix"])
    environment = measure_t230_runtime_v1(
        role="worker",
        output_prefix=output_prefix,
        repository_root=repository_root,
        image_evidence_identity=image_evidence_identity,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    normalized_evidence_identity = _identity(
        image_evidence_identity, label="image evidence identity"
    )
    if (
        normalized_manifest_identity["uri"] != manifest_uri_for_output_prefix(output_prefix)
        or environment["release_runtime_verified"] is not True
        or environment["implementation_sha256"]
        != EXPECTED_WORKER_IMPLEMENTATION_SHA256
        or environment["measured_source_commit_sha"] != manifest["source_commit_sha"]
        or environment["immutable_image"] != manifest["immutable_image"]
        or receipt["panel_object_identity"] != manifest["panel_object_identity"]
        or receipt["panel_index_sha256"] != manifest["panel_index_sha256"]
        or environment["g0_authority_lock_git_binding"] != g0_git_binding
    ):
        _fail("T230 authority manifest/publication/runtime lineage differs")
    seed = {
        "manifest_identity": normalized_manifest_identity,
        "panel_publication_receipt_binding": receipt_binding,
        "fixed_lane_receipt_bindings": lane_bindings,
        "g0_authority_lock_git_binding": g0_git_binding,
        "image_evidence_identity": normalized_evidence_identity,
    }
    body: dict[str, object] = {
        "schema_version": EXECUTION_AUTHORITY_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "execution_authority_id": "foundry-t230-authority:" + batch.canonical_sha256(seed),
        "manifest_identity": normalized_manifest_identity,
        "manifest_id": manifest["manifest_id"],
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "panel_publication_receipt_binding": receipt_binding,
        "panel_publication_receipt_sha256": receipt["publication_receipt_sha256"],
        "g0_authority_lock_git_binding": g0_git_binding,
        "g0_authority_lock_git_binding_sha256": batch.canonical_sha256(
            g0_git_binding
        ),
        "g0_authority_lock_sha256": g0_git_binding[
            "g0_authority_lock_sha256"
        ],
        "fixed_lane_receipt_bindings": lane_bindings,
        "fixed_lane_receipt_bindings_sha256": batch.canonical_sha256(lane_bindings),
        "panel_object_identity": receipt["panel_object_identity"],
        "panel_index_sha256": receipt["panel_index_sha256"],
        "image_evidence_identity": normalized_evidence_identity,
        "image_evidence_sha256": environment["image_evidence_sha256"],
        "worker_implementation_sha256": EXPECTED_WORKER_IMPLEMENTATION_SHA256,
        "verifier_implementation_sha256": EXPECTED_VERIFIER_IMPLEMENTATION_SHA256,
        "runtime_facts": environment["runtime_facts"],
        "source_commit_sha": manifest["source_commit_sha"],
        "immutable_image": manifest["immutable_image"],
        "output_prefix": output_prefix,
        "panel_publication_cloud_attested": False,
        "simulated_execution_only": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["execution_authority_sha256"] = batch.canonical_sha256(body)
    return body


def _reopen_authority_context(
    *,
    execution_authority_identity: Mapping[str, object],
    read_exact: ReadExact,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> _AuthorityContext:
    authority_identity, authority_body = _exact_read_json(
        execution_authority_identity,
        read_exact=read_exact,
        label="T230 execution authority",
    )
    authority = dict(_mapping(authority_body, label="T230 execution authority"))
    _exact_keys(authority, _EXECUTION_AUTHORITY_KEYS, label="T230 execution authority")
    _false_authorities(authority, label="T230 execution authority")
    _guard_nested_authority_keys(authority, label="T230 execution authority")
    _validate_self_hash(
        authority,
        field="execution_authority_sha256",
        label="T230 execution authority",
    )
    if (
        authority.get("schema_version") != EXECUTION_AUTHORITY_SCHEMA
        or authority.get("publication_mode") != PUBLICATION_MODE
        or authority.get("panel_publication_cloud_attested") is not False
        or authority.get("simulated_execution_only") is not True
        or authority_identity["uri"]
        != authority_uri_for_output_prefix(str(authority.get("output_prefix")))
    ):
        _fail("T230 execution authority frozen surface differs")
    expected = build_t230_execution_authority_v1(
        manifest_identity=_mapping(authority["manifest_identity"], label="manifest identity"),
        image_evidence_identity=_mapping(
            authority["image_evidence_identity"], label="image evidence identity"
        ),
        read_exact=read_exact,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if batch.canonical_json_bytes(authority) != batch.canonical_json_bytes(expected):
        _fail("T230 execution authority differs after complete replay")
    execution = _reopen_context(
        manifest_identity=_mapping(authority["manifest_identity"], label="manifest identity"),
        read_exact=read_exact,
    )
    return _AuthorityContext(
        authority_identity=authority_identity,
        authority=expected,
        execution=execution,
    )


def reopen_t230_execution_authority_v1(
    *,
    execution_authority_identity: Mapping[str, object],
    read_exact: ReadExact,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Exact-read and fully replay the release-bearing authority envelope."""
    return _reopen_authority_context(
        execution_authority_identity=execution_authority_identity,
        read_exact=read_exact,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    ).authority


def _reopen_context(
    *,
    manifest_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> _ExecutionContext:
    normalized_manifest_identity, manifest = _exact_read_json(
        manifest_identity,
        read_exact=read_exact,
        label="T230 execution manifest",
    )
    if normalized_manifest_identity["uri"] != manifest_uri_for_output_prefix(
        str(manifest.get("output_prefix"))
    ):
        _fail("execution manifest URI differs from its deterministic prefix")
    panel_identity = _identity(
        manifest.get("panel_object_identity"), label="published panel identity"
    )
    _, panel_body = _exact_read_json(
        panel_identity,
        read_exact=read_exact,
        label="published v12 panel",
    )
    try:
        replayed = manifest_contract.validate_t230_panel_execution_manifest_v1(
            manifest,
            panel_index=panel_body,
            panel_index_identity=panel_identity,
            source_commit_sha=str(manifest.get("source_commit_sha")),
            immutable_image=_mapping(
                manifest.get("immutable_image"), label="manifest image"
            ),
            output_prefix=str(manifest.get("output_prefix")),
        )
    except Exception as exc:
        raise CorpusExtremeTailPanelExecutionError(
            f"execution manifest replay failed: {exc}"
        ) from exc
    if batch.canonical_json_bytes(replayed) != batch.canonical_json_bytes(manifest):
        _fail("execution manifest differs after frozen-input replay")
    return _ExecutionContext(
        manifest_identity=normalized_manifest_identity,
        manifest=dict(replayed),
        panel=panel_body,
    )


def reopen_t230_panel_execution_manifest_v1(
    *,
    manifest_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-read and independently replay one prepared execution manifest."""
    return _reopen_context(
        manifest_identity=manifest_identity,
        read_exact=read_exact,
    ).manifest


def _source_member(
    context: _ExecutionContext, *, source_ordinal: int
) -> tuple[dict[str, object], dict[str, object]]:
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("source ordinal must be one exact integer in 0..53")
    members = _sequence(
        context.manifest.get("source_members"), label="manifest source members"
    )
    panel_members = _sequence(
        context.panel.get("accepted_slates"), label="panel accepted slates"
    )
    if len(members) != 54 or len(panel_members) != 54:
        _fail("manifest/panel source membership does not contain exactly 54 rows")
    member = dict(_mapping(members[source_ordinal], label="manifest source member"))
    panel_member = dict(
        _mapping(panel_members[source_ordinal], label="panel source member")
    )
    if (
        member.get("source_ordinal") != source_ordinal
        or panel_member.get("source_task_ordinal") != source_ordinal
        or member.get("slate_id") != panel_member.get("slate_id")
        or member.get("panel_member_sha256")
        != batch.canonical_sha256(panel_member)
        or member.get("source_task_authority_sha256")
        != panel_member.get("source_task_authority_sha256")
        or member.get("task_acceptance_identity")
        != panel_member.get("task_acceptance_identity")
        or member.get("carrier_identity") != panel_member.get("carrier_identity")
    ):
        _fail("manifest source member differs from the published panel row")
    return member, panel_member


def _world_ids(reconstructed: object) -> list[dict[str, object]]:
    prepared = getattr(reconstructed, "prepared", None)
    raw = _sequence(
        getattr(prepared, "world_ids", None), label="reconstructed world IDs"
    )
    if len(raw) != WORLD_COUNT:
        _fail("authoritative reconstruction must contain exactly 50,000 worlds")
    result: list[dict[str, object]] = []
    for flat_index, value in enumerate(raw):
        if isinstance(value, Mapping):
            block = value.get("block")
            index = value.get("index")
        else:
            block = getattr(value, "block", None)
            index = getattr(value, "index", None)
        expected_block = WORLD_BLOCKS[flat_index // WORLDS_PER_BLOCK]
        expected_index = flat_index % WORLDS_PER_BLOCK
        if block != expected_block or type(index) is not int or index != expected_index:
            _fail("reconstructed world IDs differ from exact R0..R4 block order")
        result.append({"block": expected_block, "index": expected_index})
    return result


def _support_observation(policy_value: object) -> dict[str, int]:
    try:
        policy = support._validate_policy_structure(policy_value)
    except Exception as exc:
        raise CorpusExtremeTailPanelExecutionError(
            f"support-switched policy structure failed: {exc}"
        ) from exc
    folds = _sequence(policy.get("folds"), label="support policy folds")
    final_fit = _mapping(policy.get("final_fit"), label="support policy final fit")
    if len(folds) != len(WORLD_BLOCKS):
        _fail("support policy must contain exactly five cross-fit gates")
    fold_passed = sum(
        _mapping(scope, label="support fold").get("support_gate", {}).get("passed")
        is True
        for scope in folds
    )
    final_passed = int(
        _mapping(final_fit.get("support_gate"), label="final support gate").get(
            "passed"
        )
        is True
    )
    return {
        "fold_gate_passed": fold_passed,
        "fold_gate_total": len(folds),
        "final_fit_gate_passed": final_passed,
        "final_fit_gate_total": 1,
    }


def _science_contract_bindings(manifest: Mapping[str, object]) -> dict[str, str]:
    world = _mapping(
        manifest.get("ordinary_r_world_contract"), label="world contract"
    )
    dose = _mapping(
        manifest.get("authoritative_generation_dose"), label="dose contract"
    )
    retrieval = _mapping(
        manifest.get("t230_retrieval_contract"), label="retrieval contract"
    )
    support_contract = _mapping(
        manifest.get("support_contract"), label="support contract"
    )
    return {
        "world_contract_sha256": _sha(
            world.get("world_contract_sha256"), label="world contract SHA"
        ),
        "generation_dose_sha256": _sha(
            dose.get("generation_dose_sha256"), label="generation dose SHA"
        ),
        "retrieval_contract_sha256": _sha(
            retrieval.get("retrieval_contract_sha256"),
            label="retrieval contract SHA",
        ),
        "strategy_registry_sha256": _sha(
            retrieval.get("strategy_registry_sha256"),
            label="strategy registry SHA",
        ),
        "selector_implementation_sha256": _sha(
            retrieval.get("selector_implementation_sha256"),
            label="selector implementation SHA",
        ),
        "support_contract_sha256": _sha(
            support_contract.get("support_contract_sha256"),
            label="support contract SHA",
        ),
    }


def _input_artifact_bindings(
    reconstructed_slate: accepted.AcceptedV12SlateReconstruction,
    *,
    panel_member: Mapping[str, object],
) -> dict[str, object]:
    imported_receipt = _mapping(
        reconstructed_slate.imported.compatibility_receipt,
        label="v12 compatibility import",
    )
    provenance = _mapping(
        reconstructed_slate.reconstructed.provenance,
        label="reconstructed provenance",
    )
    reconstruction = _mapping(
        reconstructed_slate.reconstructed.reconstruction_receipt,
        label="reconstruction receipt",
    )
    matrix = _mapping(reconstruction.get("matrix_binding"), label="matrix binding")
    score_shape = list(
        _sequence(matrix.get("shape"), label="reconstruction score shape")
    )
    if (
        len(score_shape) != 2
        or any(type(value) is not int or value < 1 for value in score_shape)
        or score_shape[1] != WORLD_COUNT
    ):
        _fail("reconstruction matrix must contain exact five-by-10,000 width")
    world_artifacts = dict(reconstructed_slate.world_artifact_identities)
    return {
        "panel_object_identity": dict(reconstructed_slate.panel_index_identity),
        "panel_index_sha256": _sha(
            reconstructed_slate.panel_index_sha256, label="panel index SHA"
        ),
        "accepted_slate_membership_sha256": batch.canonical_sha256(panel_member),
        "task_acceptance_identity": dict(
            reconstructed_slate.task_acceptance_identity
        ),
        "carrier_identity": dict(reconstructed_slate.carrier_identity),
        "later_source_freeze_identity": dict(
            reconstructed_slate.later_source_freeze_identity
        ),
        "world_artifact_identities": world_artifacts,
        "world_artifact_identity_set_sha256": batch.canonical_sha256(
            world_artifacts
        ),
        "compatibility_import_sha256": _sha(
            imported_receipt.get("compatibility_import_sha256"),
            label="compatibility import SHA",
        ),
        "candidate_provenance_sha256": _sha(
            provenance.get("candidate_provenance_sha256"),
            label="candidate provenance SHA",
        ),
        "reconstruction_sha256": _sha(
            reconstruction.get("reconstruction_sha256"),
            label="reconstruction SHA",
        ),
        "matrix_binding_sha256": _sha(
            matrix.get("matrix_binding_sha256"), label="matrix binding SHA"
        ),
        "score_matrix_sha256": _sha(
            matrix.get("score_matrix_sha256"), label="score matrix SHA"
        ),
        "lineup_ids_sha256": _sha(
            matrix.get("lineup_ids_sha256"), label="lineup IDs SHA"
        ),
        "world_ids_sha256": _sha(
            matrix.get("world_ids_sha256"), label="world IDs SHA"
        ),
        "score_shape": score_shape,
    }


def _runtime_receipt_binding(
    identity: Mapping[str, object],
    receipt: Mapping[str, object],
    *,
    role: str,
) -> dict[str, object]:
    if role not in _RUNTIME_ROLES or receipt.get("role") != role:
        _fail("runtime role must be worker or verifier")
    return {
        "role": role,
        "runtime_measurement_identity": dict(identity),
        "runtime_measurement_sha256": receipt["runtime_measurement_sha256"],
        "process_instance_sha256": receipt["process_instance_sha256"],
        "implementation_sha256": receipt["implementation_sha256"],
        "source_commit_sha": receipt["measured_source_commit_sha"],
        "immutable_image": receipt["immutable_image"],
        "release_runtime_verified": receipt["release_runtime_verified"],
    }


def _compute_t230_result(
    *,
    authority_context: _AuthorityContext,
    worker_runtime_identity: Mapping[str, object],
    worker_runtime_receipt: Mapping[str, object],
    source_ordinal: int,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Reconstruct and compute one exact result from authoritative inputs."""
    context = authority_context.execution
    member, panel_member = _source_member(context, source_ordinal=source_ordinal)
    worker_runtime = _runtime_receipt_binding(
        worker_runtime_identity, worker_runtime_receipt, role="worker"
    )
    try:
        reconstructed_slate = accepted.reconstruct_one_accepted_v12_slate(
            validated_panel_index=context.panel,
            panel_index_identity=context.manifest["panel_object_identity"],
            accepted_slate_membership=panel_member,
            task_acceptance_identity=member["task_acceptance_identity"],
            carrier_identity=member["carrier_identity"],
            read_exact=read_exact,
            require_authoritative=True,
        )
    except accepted.CorpusR6V2OneSlateExecutionError as exc:
        raise CorpusExtremeTailPanelExecutionError(str(exc)) from exc
    if (
        reconstructed_slate.slate_id != member["slate_id"]
        or batch.canonical_sha256(reconstructed_slate.accepted_slate_membership)
        != member["panel_member_sha256"]
        or reconstructed_slate.task_acceptance_identity
        != member["task_acceptance_identity"]
        or reconstructed_slate.carrier_identity != member["carrier_identity"]
    ):
        _fail("accepted reconstruction differs from manifest source membership")

    reconstructed = reconstructed_slate.reconstructed
    world_ids = _world_ids(reconstructed)
    scores = np.asarray(reconstructed.union_scores)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or scores.shape[1] != WORLD_COUNT
        or not scores.flags.c_contiguous
    ):
        _fail("accepted reconstruction lacks canonical float64 50,000-world matrix")
    try:
        support_census = census.build_extreme_tail_support_census(
            provenance=reconstructed.provenance,
            union_scores=scores,
            reconstruction_receipt=reconstructed.reconstruction_receipt,
            world_ids=world_ids,
            worlds_per_block=None,
            require_authoritative=True,
        )
        extreme_tail_suite = suite.run_extreme_tail_retrieval_suite_v1(
            provenance=reconstructed.provenance,
            union_scores=scores,
            reconstruction_receipt=reconstructed.reconstruction_receipt,
            entry_budgets=ENTRY_BUDGETS,
            worlds_per_block=None,
            require_authoritative=True,
        )
        support_policy = support.build_extreme_tail_support_switched_policy_v1(
            support_census=support_census,
            extreme_tail_suite=extreme_tail_suite,
            provenance=reconstructed.provenance,
            union_scores=scores,
            reconstruction_receipt=reconstructed.reconstruction_receipt,
            world_ids=world_ids,
            worlds_per_block=None,
            require_authoritative=True,
        )
    except (
        census.CorpusExtremeTailCensusError,
        suite.CorpusExtremeTailRetrievalSuiteError,
        support.CorpusExtremeTailSupportSwitchError,
    ) as exc:
        raise CorpusExtremeTailPanelExecutionError(str(exc)) from exc
    observation = _support_observation(support_policy)
    bindings = _input_artifact_bindings(
        reconstructed_slate, panel_member=panel_member
    )
    reconstruction_receipt = dict(_mapping(
        reconstructed.reconstruction_receipt, label="reconstruction receipt"
    ))
    body: dict[str, object] = {
        "schema_version": SLATE_RESULT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "execution_mode": "outcome-blind-simulated-t230-four-law-suite",
        "execution_authority_identity": authority_context.authority_identity,
        "execution_authority_sha256": authority_context.authority[
            "execution_authority_sha256"
        ],
        "manifest_identity": context.manifest_identity,
        "manifest_id": context.manifest["manifest_id"],
        "execution_manifest_sha256": context.manifest[
            "execution_manifest_sha256"
        ],
        "source_ordinal": source_ordinal,
        "slate_id": member["slate_id"],
        "source_member_sha256": member["panel_member_sha256"],
        "source_task_authority_sha256": member[
            "source_task_authority_sha256"
        ],
        "result_uri": member["result_uri"],
        "acceptance_uri": member["acceptance_uri"],
        "worker_runtime_binding": worker_runtime,
        "input_artifact_bindings": bindings,
        "science_contract_bindings": _science_contract_bindings(
            context.manifest
        ),
        "configuration": {
            "world_blocks": list(WORLD_BLOCKS),
            "worlds_per_block": WORLDS_PER_BLOCK,
            "world_count": WORLD_COUNT,
            "entry_budgets": list(ENTRY_BUDGETS),
            "ranking_depth": RANKING_DEPTH,
            "strategy_count": 4,
            "fold_count": 5,
            "final_fit_count": 1,
            "require_authoritative": True,
        },
        "verification": {
            "manifest_content_identity_replayed": True,
            "published_panel_content_identity_replayed": True,
            "source_membership_replayed": True,
            "carrier_and_source_content_replayed": True,
            "ordinary_r_matrix_replayed": True,
            "support_census_source_replay_verified": True,
            "four_law_suite_source_replay_verified": True,
            "support_switch_structure_verified": True,
            "runtime_source_and_image_verified": True,
            "realized_outcomes_read": False,
        },
        "support_observation": observation,
        "reconstruction_receipt": reconstruction_receipt,
        "support_census": dict(_mapping(support_census, label="support census")),
        "extreme_tail_suite": dict(
            _mapping(extreme_tail_suite, label="extreme-tail suite")
        ),
        "support_switched_policy": dict(
            _mapping(support_policy, label="support-switched policy")
        ),
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["t230_slate_result_sha256"] = batch.canonical_sha256(body)
    return _validate_t230_slate_result_structure(
        body,
        authority_context=authority_context,
        worker_runtime_identity=worker_runtime_identity,
        worker_runtime_receipt=worker_runtime_receipt,
        source_ordinal=source_ordinal,
    )


def execute_t230_panel_slate_v1(
    *,
    execution_authority_identity: Mapping[str, object],
    worker_runtime_measurement_identity: Mapping[str, object],
    source_ordinal: int,
    read_exact: ReadExact,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Worker process: compute one nonterminal outcome-blind result."""
    authority_context = _reopen_authority_context(
        execution_authority_identity=execution_authority_identity,
        read_exact=read_exact,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    worker_identity, worker_body = _exact_read_json(
        worker_runtime_measurement_identity,
        read_exact=read_exact,
        label="current worker runtime measurement",
    )
    worker = validate_t230_runtime_measurement_v1(
        worker_body,
        role="worker",
        output_prefix=str(authority_context.authority["output_prefix"]),
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if (
        worker_identity["uri"]
        != runtime_measurement_uri_for_output_prefix(
            str(authority_context.authority["output_prefix"]),
            role="worker",
            source_ordinal=source_ordinal,
        )
        or worker["release_runtime_verified"] is not True
        or worker["measured_source_commit_sha"]
        != authority_context.authority["source_commit_sha"]
        or worker["immutable_image"] != authority_context.authority["immutable_image"]
    ):
        _fail("current worker runtime differs from execution authority")
    return _compute_t230_result(
        authority_context=authority_context,
        worker_runtime_identity=worker_identity,
        worker_runtime_receipt=worker,
        source_ordinal=source_ordinal,
        read_exact=read_exact,
    )


def _validate_t230_slate_result_structure(
    value: object,
    *,
    authority_context: _AuthorityContext,
    worker_runtime_identity: Mapping[str, object],
    worker_runtime_receipt: Mapping[str, object],
    source_ordinal: int,
) -> dict[str, object]:
    context = authority_context.execution
    result = dict(_mapping(value, label="T230 slate result"))
    _exact_keys(result, _RESULT_KEYS, label="T230 slate result")
    _false_authorities(result, label="T230 slate result")
    _nested_false_authorities(result, label="T230 slate result")
    _guard_nested_authority_keys(result, label="T230 slate result")
    _validate_self_hash(
        result, field="t230_slate_result_sha256", label="T230 slate result"
    )
    member, panel_member = _source_member(context, source_ordinal=source_ordinal)
    expected_runtime = _runtime_receipt_binding(
        worker_runtime_identity, worker_runtime_receipt, role="worker"
    )
    if (
        result.get("schema_version") != SLATE_RESULT_SCHEMA
        or result.get("publication_mode") != PUBLICATION_MODE
        or result.get("execution_mode")
        != "outcome-blind-simulated-t230-four-law-suite"
        or result.get("execution_authority_identity")
        != authority_context.authority_identity
        or result.get("execution_authority_sha256")
        != authority_context.authority.get("execution_authority_sha256")
        or result.get("manifest_identity") != context.manifest_identity
        or result.get("manifest_id") != context.manifest.get("manifest_id")
        or result.get("execution_manifest_sha256")
        != context.manifest.get("execution_manifest_sha256")
        or result.get("source_ordinal") != source_ordinal
        or result.get("slate_id") != member.get("slate_id")
        or result.get("source_member_sha256")
        != member.get("panel_member_sha256")
        or result.get("source_task_authority_sha256")
        != member.get("source_task_authority_sha256")
        or result.get("result_uri") != member.get("result_uri")
        or result.get("acceptance_uri") != member.get("acceptance_uri")
        or result.get("worker_runtime_binding") != expected_runtime
    ):
        _fail("T230 slate result manifest/member/runtime binding differs")
    expected_configuration = {
        "world_blocks": list(WORLD_BLOCKS),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "world_count": WORLD_COUNT,
        "entry_budgets": list(ENTRY_BUDGETS),
        "ranking_depth": RANKING_DEPTH,
        "strategy_count": 4,
        "fold_count": 5,
        "final_fit_count": 1,
        "require_authoritative": True,
    }
    expected_verification = {
        "manifest_content_identity_replayed": True,
        "published_panel_content_identity_replayed": True,
        "source_membership_replayed": True,
        "carrier_and_source_content_replayed": True,
        "ordinary_r_matrix_replayed": True,
        "support_census_source_replay_verified": True,
        "four_law_suite_source_replay_verified": True,
        "support_switch_structure_verified": True,
        "runtime_source_and_image_verified": True,
        "realized_outcomes_read": False,
    }
    if (
        result.get("configuration") != expected_configuration
        or result.get("verification") != expected_verification
        or result.get("science_contract_bindings")
        != _science_contract_bindings(context.manifest)
    ):
        _fail("T230 slate result configuration/science verification differs")

    inputs = _mapping(
        result.get("input_artifact_bindings"), label="input artifact bindings"
    )
    if (
        inputs.get("panel_object_identity")
        != context.manifest.get("panel_object_identity")
        or inputs.get("panel_index_sha256")
        != context.manifest.get("panel_index_sha256")
        or inputs.get("accepted_slate_membership_sha256")
        != batch.canonical_sha256(panel_member)
        or inputs.get("task_acceptance_identity")
        != member.get("task_acceptance_identity")
        or inputs.get("carrier_identity") != member.get("carrier_identity")
    ):
        _fail("T230 slate result input artifact binding differs")
    score_shape = list(
        _sequence(inputs.get("score_shape"), label="input score shape")
    )
    if (
        len(score_shape) != 2
        or any(type(value) is not int or value < 1 for value in score_shape)
        or score_shape[1] != WORLD_COUNT
    ):
        _fail("T230 slate result input score shape differs")
    for field in (
        "compatibility_import_sha256",
        "candidate_provenance_sha256",
        "reconstruction_sha256",
        "matrix_binding_sha256",
        "score_matrix_sha256",
        "lineup_ids_sha256",
        "world_ids_sha256",
        "world_artifact_identity_set_sha256",
    ):
        _sha(inputs.get(field), label=f"input artifact bindings.{field}")
    _identity(
        inputs.get("later_source_freeze_identity"),
        label="later source freeze identity",
    )
    world_artifacts = _mapping(
        inputs.get("world_artifact_identities"), label="world artifact identities"
    )
    if (
        set(world_artifacts) != set(batch.TASK_WORLD_SOURCE_ROLES)
        or batch.canonical_sha256(world_artifacts)
        != inputs.get("world_artifact_identity_set_sha256")
    ):
        _fail("T230 slate result world artifact set differs")
    for role in batch.TASK_WORLD_SOURCE_ROLES:
        _identity(world_artifacts[role], label=f"world artifact {role}")

    reconstruction = _mapping(
        result.get("reconstruction_receipt"), label="reconstruction receipt"
    )
    _validate_self_hash(
        reconstruction,
        field="reconstruction_sha256",
        label="reconstruction receipt",
    )
    matrix = _mapping(reconstruction.get("matrix_binding"), label="matrix binding")
    if (
        reconstruction.get("reconstruction_sha256")
        != inputs.get("reconstruction_sha256")
        or matrix.get("matrix_binding_sha256")
        != inputs.get("matrix_binding_sha256")
        or matrix.get("score_matrix_sha256")
        != inputs.get("score_matrix_sha256")
        or matrix.get("lineup_ids_sha256") != inputs.get("lineup_ids_sha256")
        or matrix.get("world_ids_sha256") != inputs.get("world_ids_sha256")
        or matrix.get("shape") != inputs.get("score_shape")
    ):
        _fail("T230 slate result reconstruction/matrix binding differs")

    retained_census = _mapping(result.get("support_census"), label="support census")
    retained_suite = _mapping(
        result.get("extreme_tail_suite"), label="extreme-tail suite"
    )
    retained_policy = _mapping(
        result.get("support_switched_policy"), label="support-switched policy"
    )
    _validate_self_hash(
        retained_census,
        field="support_census_sha256",
        label="support census",
    )
    _validate_self_hash(
        retained_suite, field="suite_sha256", label="extreme-tail suite"
    )
    _validate_self_hash(
        retained_policy,
        field="support_switched_policy_sha256",
        label="support-switched policy",
    )
    census_input = _mapping(
        retained_census.get("input_binding"), label="census input binding"
    )
    suite_input = _mapping(
        retained_suite.get("input_binding"), label="suite input binding"
    )
    policy_input = _mapping(
        retained_policy.get("input_binding"), label="policy input binding"
    )
    expected_input = {
        "reconstruction_sha256": inputs["reconstruction_sha256"],
        "candidate_provenance_sha256": inputs["candidate_provenance_sha256"],
        "matrix_binding_sha256": inputs["matrix_binding_sha256"],
        "score_matrix_sha256": inputs["score_matrix_sha256"],
        "lineup_ids_sha256": inputs["lineup_ids_sha256"],
        "world_ids_sha256": inputs["world_ids_sha256"],
        "score_shape": inputs["score_shape"],
    }
    retrieval_contract = _mapping(
        context.manifest.get("t230_retrieval_contract"),
        label="manifest retrieval contract",
    )
    if (
        retained_census.get("schema_version") != census.CENSUS_SCHEMA
        or retained_suite.get("schema_version") != suite.SUITE_SCHEMA
        or retained_policy.get("schema_version") != support.POLICY_SCHEMA
        or census_input != expected_input
        or suite_input != expected_input
        or policy_input != expected_input
        or retained_census.get("world_basis", {}).get("worlds_per_block")
        != WORLDS_PER_BLOCK
        or retained_suite.get("worlds_per_block") != WORLDS_PER_BLOCK
        or retained_policy.get("worlds_per_block") != WORLDS_PER_BLOCK
        or retained_suite.get("entry_budgets") != list(ENTRY_BUDGETS)
        or retained_suite.get("ranking_depth") != RANKING_DEPTH
        or retained_suite.get("fold_count") != 5
        or retained_suite.get("books_per_scope") != 12
        or retained_suite.get("cross_fit_book_count") != 60
        or retained_suite.get("final_fit_book_count") != 12
        or retained_suite.get("strategy_registry")
        != retrieval_contract.get("strategy_registry")
        or retained_suite.get("strategy_registry_sha256")
        != retrieval_contract.get("strategy_registry_sha256")
        or retained_suite.get("selector_implementation_contract")
        != retrieval_contract.get("selector_implementation_contract")
        or retained_policy.get("entry_budgets") != list(ENTRY_BUDGETS)
        or retained_policy.get("ranking_depth") != RANKING_DEPTH
        or retained_policy.get("fold_gate_count") != 5
        or retained_policy.get("final_fit_gate_count") != 1
        or retained_policy.get("selected_book_count") != 18
        or retained_policy.get("require_authoritative") is not True
    ):
        _fail("T230 census/suite/support frozen surface differs")
    source_receipts = _mapping(
        retained_policy.get("source_receipts"), label="policy source receipts"
    )
    if (
        source_receipts.get("support_census_sha256")
        != retained_census.get("support_census_sha256")
        or source_receipts.get("extreme_tail_suite_sha256")
        != retained_suite.get("suite_sha256")
    ):
        _fail("T230 support policy does not bind the retained census/suite")
    observation = _support_observation(retained_policy)
    if result.get("support_observation") != observation:
        _fail("T230 slate result support observation differs")
    return result


def _runtime_from_binding(
    value: object,
    *,
    role: str,
    source_ordinal: int,
    authority_context: _AuthorityContext,
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    binding = dict(_mapping(value, label=f"{role} runtime binding"))
    if frozenset(binding) != {
        "role", "runtime_measurement_identity", "runtime_measurement_sha256",
        "process_instance_sha256", "implementation_sha256",
        "source_commit_sha", "immutable_image", "release_runtime_verified",
    }:
        _fail(f"{role} runtime binding fields differ")
    identity, body = _exact_read_json(
        binding.get("runtime_measurement_identity"),
        read_exact=read_exact,
        label=f"published {role} runtime measurement",
    )
    receipt = _validate_published_runtime_measurement_v1(
        body,
        role=role,
        output_prefix=str(authority_context.authority["output_prefix"]),
        read_exact=read_exact,
    )
    if (
        identity["uri"]
        != runtime_measurement_uri_for_output_prefix(
            str(authority_context.authority["output_prefix"]),
            role=role,
            source_ordinal=source_ordinal,
        )
        or binding != _runtime_receipt_binding(identity, receipt, role=role)
        or receipt["measured_source_commit_sha"]
        != authority_context.authority["source_commit_sha"]
        or receipt["immutable_image"] != authority_context.authority["immutable_image"]
        or receipt["image_evidence_identity"]
        != authority_context.authority["image_evidence_identity"]
        or receipt["implementation_sha256"]
        != authority_context.authority[f"{role}_implementation_sha256"]
        or receipt["g0_authority_lock_git_binding"]
        != authority_context.authority["g0_authority_lock_git_binding"]
    ):
        _fail(f"{role} runtime receipt differs from authority/member binding")
    return identity, receipt


def _assert_distinct_processes(
    worker: Mapping[str, object], verifier: Mapping[str, object]
) -> None:
    if (
        worker.get("process_instance_sha256")
        == verifier.get("process_instance_sha256")
        or worker.get("process_instance") == verifier.get("process_instance")
    ):
        _fail("worker and verifier must be distinct process instances")


def validate_t230_slate_result_v1(
    value: object,
    *,
    execution_authority_identity: Mapping[str, object],
    source_ordinal: int,
    read_exact: ReadExact,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Independently reconstruct and byte-compare a retained worker result."""
    context = _reopen_authority_context(
        execution_authority_identity=execution_authority_identity,
        read_exact=read_exact,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    raw = dict(_mapping(value, label="T230 slate result"))
    worker_identity, worker = _runtime_from_binding(
        raw.get("worker_runtime_binding"),
        role="worker",
        source_ordinal=source_ordinal,
        authority_context=context,
        read_exact=read_exact,
    )
    retained = _validate_t230_slate_result_structure(
        raw,
        authority_context=context,
        worker_runtime_identity=worker_identity,
        worker_runtime_receipt=worker,
        source_ordinal=source_ordinal,
    )
    expected = _compute_t230_result(
        authority_context=context,
        worker_runtime_identity=worker_identity,
        worker_runtime_receipt=worker,
        source_ordinal=source_ordinal,
        read_exact=read_exact,
    )
    if batch.canonical_json_bytes(retained) != batch.canonical_json_bytes(expected):
        _fail("T230 slate result differs from independent source recomputation")
    return expected


def _acceptance_from_verified_result(
    *,
    authority_context: _AuthorityContext,
    source_ordinal: int,
    result_identity: dict[str, object],
    result: Mapping[str, object],
    verifier_runtime_identity: Mapping[str, object],
    verifier_runtime_receipt: Mapping[str, object],
) -> dict[str, object]:
    context = authority_context.execution
    member, _ = _source_member(context, source_ordinal=source_ordinal)
    body: dict[str, object] = {
        "schema_version": SLATE_ACCEPTANCE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "execution_authority_identity": authority_context.authority_identity,
        "execution_authority_sha256": authority_context.authority[
            "execution_authority_sha256"
        ],
        "manifest_identity": context.manifest_identity,
        "manifest_id": context.manifest["manifest_id"],
        "execution_manifest_sha256": context.manifest[
            "execution_manifest_sha256"
        ],
        "source_ordinal": source_ordinal,
        "slate_id": member["slate_id"],
        "source_member_sha256": member["panel_member_sha256"],
        "result_identity": result_identity,
        "result_uri": member["result_uri"],
        "acceptance_uri": member["acceptance_uri"],
        "t230_slate_result_sha256": result["t230_slate_result_sha256"],
        "support_census_sha256": result["support_census"][
            "support_census_sha256"
        ],
        "extreme_tail_suite_sha256": result["extreme_tail_suite"][
            "suite_sha256"
        ],
        "support_switched_policy_sha256": result["support_switched_policy"][
            "support_switched_policy_sha256"
        ],
        "support_observation": result["support_observation"],
        "worker_runtime_binding": result["worker_runtime_binding"],
        "verifier_runtime_binding": _runtime_receipt_binding(
            verifier_runtime_identity, verifier_runtime_receipt, role="verifier"
        ),
        "verification": {
            "execution_authority_and_published_panel_replayed": True,
            "accepted_member_and_carrier_reconstructed": True,
            "result_content_identity_replayed": True,
            "support_census_independently_recomputed": True,
            "four_law_suite_independently_recomputed": True,
            "support_switch_books_and_ranks_independently_recomputed": True,
            "full_result_byte_equality_verified": True,
            "worker_and_verifier_runtime_distinct": True,
            "realized_outcomes_read": False,
        },
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["t230_slate_acceptance_sha256"] = batch.canonical_sha256(body)
    return body


def verify_t230_panel_slate_v1(
    *,
    execution_authority_identity: Mapping[str, object],
    source_ordinal: int,
    result_identity: Mapping[str, object],
    verifier_runtime_measurement_identity: Mapping[str, object],
    read_exact: ReadExact,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Independent verifier process: recompute before issuing acceptance."""
    authority_context = _reopen_authority_context(
        execution_authority_identity=execution_authority_identity,
        read_exact=read_exact,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    context = authority_context.execution
    member, _ = _source_member(context, source_ordinal=source_ordinal)
    normalized_result_identity, result_body = _exact_read_json(
        result_identity,
        read_exact=read_exact,
        label="published nonterminal T230 slate result",
    )
    if normalized_result_identity["uri"] != member["result_uri"]:
        _fail("published T230 result URI differs from deterministic membership")
    worker_identity, worker = _runtime_from_binding(
        result_body.get("worker_runtime_binding"),
        role="worker",
        source_ordinal=source_ordinal,
        authority_context=authority_context,
        read_exact=read_exact,
    )
    verifier_identity, verifier_body = _exact_read_json(
        verifier_runtime_measurement_identity,
        read_exact=read_exact,
        label="current verifier runtime measurement",
    )
    verifier = validate_t230_runtime_measurement_v1(
        verifier_body,
        role="verifier",
        output_prefix=str(authority_context.authority["output_prefix"]),
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if (
        verifier_identity["uri"] != runtime_measurement_uri_for_output_prefix(
            str(authority_context.authority["output_prefix"]),
            role="verifier",
            source_ordinal=source_ordinal,
        )
        or verifier["image_evidence_identity"]
        != authority_context.authority["image_evidence_identity"]
        or verifier["measured_source_commit_sha"]
        != authority_context.authority["source_commit_sha"]
        or verifier["immutable_image"] != authority_context.authority["immutable_image"]
        or verifier["implementation_sha256"]
        != authority_context.authority["verifier_implementation_sha256"]
    ):
        _fail("verifier runtime URI differs from deterministic member URI")
    _assert_distinct_processes(worker, verifier)
    retained = _validate_t230_slate_result_structure(
        result_body,
        authority_context=authority_context,
        worker_runtime_identity=worker_identity,
        worker_runtime_receipt=worker,
        source_ordinal=source_ordinal,
    )
    expected = _compute_t230_result(
        authority_context=authority_context,
        worker_runtime_identity=worker_identity,
        worker_runtime_receipt=worker,
        source_ordinal=source_ordinal,
        read_exact=read_exact,
    )
    if batch.canonical_json_bytes(retained) != batch.canonical_json_bytes(expected):
        _fail("published T230 result differs from verifier recomputation")
    return _acceptance_from_verified_result(
        authority_context=authority_context,
        source_ordinal=source_ordinal,
        result_identity=normalized_result_identity,
        result=expected,
        verifier_runtime_identity=verifier_identity,
        verifier_runtime_receipt=verifier,
    )


def _validate_acceptance_structure(
    value: object,
    *,
    authority_context: _AuthorityContext,
    source_ordinal: int,
    read_exact: ReadExact,
) -> dict[str, object]:
    context = authority_context.execution
    item = dict(_mapping(value, label="T230 slate acceptance"))
    _exact_keys(item, _ACCEPTANCE_KEYS, label="T230 slate acceptance")
    _false_authorities(item, label="T230 slate acceptance")
    _nested_false_authorities(item, label="T230 slate acceptance")
    _guard_nested_authority_keys(item, label="T230 slate acceptance")
    _validate_self_hash(
        item,
        field="t230_slate_acceptance_sha256",
        label="T230 slate acceptance",
    )
    member, _ = _source_member(context, source_ordinal=source_ordinal)
    result_identity, result_body = _exact_read_json(
        item.get("result_identity"),
        read_exact=read_exact,
        label="accepted T230 result",
    )
    worker_identity, worker = _runtime_from_binding(
        result_body.get("worker_runtime_binding"),
        role="worker",
        source_ordinal=source_ordinal,
        authority_context=authority_context,
        read_exact=read_exact,
    )
    verifier_identity, verifier = _runtime_from_binding(
        item.get("verifier_runtime_binding"),
        role="verifier",
        source_ordinal=source_ordinal,
        authority_context=authority_context,
        read_exact=read_exact,
    )
    _assert_distinct_processes(worker, verifier)
    result = _validate_t230_slate_result_structure(
        result_body,
        authority_context=authority_context,
        worker_runtime_identity=worker_identity,
        worker_runtime_receipt=worker,
        source_ordinal=source_ordinal,
    )
    recomputed = _compute_t230_result(
        authority_context=authority_context,
        worker_runtime_identity=worker_identity,
        worker_runtime_receipt=worker,
        source_ordinal=source_ordinal,
        read_exact=read_exact,
    )
    if batch.canonical_json_bytes(result) != batch.canonical_json_bytes(recomputed):
        _fail("accepted T230 result differs from verifier recomputation")
    expected = _acceptance_from_verified_result(
        authority_context=authority_context,
        source_ordinal=source_ordinal,
        result_identity=result_identity,
        result=recomputed,
        verifier_runtime_identity=verifier_identity,
        verifier_runtime_receipt=verifier,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("T230 slate acceptance differs from exact result replay")
    if (
        item.get("acceptance_uri") != member.get("acceptance_uri")
        or item.get("result_uri") != member.get("result_uri")
        or item.get("t230_slate_result_sha256")
        != result.get("t230_slate_result_sha256")
    ):
        _fail("T230 slate acceptance output/result binding differs")
    return item


def validate_t230_slate_acceptance_v1(
    value: object,
    *,
    execution_authority_identity: Mapping[str, object],
    source_ordinal: int,
    read_exact: ReadExact,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Exact-replay a per-slate acceptance and its published result."""
    context = _reopen_authority_context(
        execution_authority_identity=execution_authority_identity,
        read_exact=read_exact,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    return _validate_acceptance_structure(
        value,
        authority_context=context,
        source_ordinal=source_ordinal,
        read_exact=read_exact,
    )


def build_t230_panel_release_v1(
    *,
    execution_authority_identity: Mapping[str, object],
    finalizer_runtime_measurement_identity: Mapping[str, object],
    acceptance_identities: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Exact-replay all 54 acceptances and apply frozen support arithmetic."""
    authority_context = _reopen_authority_context(
        execution_authority_identity=execution_authority_identity,
        read_exact=read_exact,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    context = authority_context.execution
    finalizer_identity, finalizer_body = _exact_read_json(
        finalizer_runtime_measurement_identity,
        read_exact=read_exact,
        label="current panel finalizer runtime measurement",
    )
    finalizer = validate_t230_runtime_measurement_v1(
        finalizer_body,
        role="verifier",
        output_prefix=str(authority_context.authority["output_prefix"]),
        repository_root=repository_root,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if (
        finalizer_identity["uri"]
        != runtime_measurement_uri_for_output_prefix(
            str(authority_context.authority["output_prefix"]), role="verifier"
        )
        or finalizer["image_evidence_identity"]
        != authority_context.authority["image_evidence_identity"]
        or finalizer["measured_source_commit_sha"]
        != authority_context.authority["source_commit_sha"]
        or finalizer["immutable_image"] != authority_context.authority["immutable_image"]
    ):
        _fail("panel finalizer runtime differs from execution authority")
    verifier_runtime = _runtime_receipt_binding(
        finalizer_identity, finalizer, role="verifier"
    )
    raw_identities = _sequence(
        acceptance_identities, label="ordered T230 acceptance identities"
    )
    if len(raw_identities) != AUTHORITATIVE_SLATE_COUNT:
        _fail("panel release requires exactly 54 ordered acceptance identities")
    normalized_identities = [
        _identity(value, label=f"acceptance identity[{ordinal}]")
        for ordinal, value in enumerate(raw_identities)
    ]
    if len({tuple(value.items()) for value in normalized_identities}) != 54:
        _fail("panel release acceptance identities must be unique")

    rows: list[dict[str, object]] = []
    fold_passed = 0
    final_passed = 0
    result_identities: list[dict[str, object]] = []
    for source_ordinal, acceptance_identity in enumerate(normalized_identities):
        member, _ = _source_member(context, source_ordinal=source_ordinal)
        if acceptance_identity["uri"] != member["acceptance_uri"]:
            _fail("ordered acceptance identity URI differs from source ordinal")
        _, acceptance_body = _exact_read_json(
            acceptance_identity,
            read_exact=read_exact,
            label=f"T230 acceptance[{source_ordinal}]",
        )
        acceptance = _validate_acceptance_structure(
            acceptance_body,
            authority_context=authority_context,
            source_ordinal=source_ordinal,
            read_exact=read_exact,
        )
        observation = _mapping(
            acceptance.get("support_observation"), label="support observation"
        )
        if (
            observation.get("fold_gate_total") != 5
            or observation.get("final_fit_gate_total") != 1
            or type(observation.get("fold_gate_passed")) is not int
            or not 0 <= int(observation["fold_gate_passed"]) <= 5
            or type(observation.get("final_fit_gate_passed")) is not int
            or observation.get("final_fit_gate_passed") not in {0, 1}
        ):
            _fail("T230 acceptance support counts differ")
        fold_passed += int(observation["fold_gate_passed"])
        final_passed += int(observation["final_fit_gate_passed"])
        result_identity = dict(
            _mapping(acceptance["result_identity"], label="result identity")
        )
        result_identities.append(result_identity)
        rows.append({
            "source_ordinal": source_ordinal,
            "slate_id": member["slate_id"],
            "source_member_sha256": member["panel_member_sha256"],
            "acceptance_identity": acceptance_identity,
            "t230_slate_acceptance_sha256": acceptance[
                "t230_slate_acceptance_sha256"
            ],
            "result_identity": result_identity,
            "t230_slate_result_sha256": acceptance[
                "t230_slate_result_sha256"
            ],
            "support_observation": dict(observation),
        })
    fold_total = sum(
        int(row["support_observation"]["fold_gate_total"]) for row in rows
    )
    final_total = sum(
        int(row["support_observation"]["final_fit_gate_total"]) for row in rows
    )
    if fold_total != FOLD_GATE_TOTAL or final_total != FINAL_GATE_TOTAL:
        _fail("panel release does not contain exact 270/54 support gates")
    fold_supported = fold_passed >= FOLD_PASS_MINIMUM
    final_supported = final_passed >= FINAL_PASS_MINIMUM
    joint = fold_supported and final_supported
    body: dict[str, object] = {
        "schema_version": PANEL_RELEASE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "execution_authority_identity": authority_context.authority_identity,
        "execution_authority_sha256": authority_context.authority[
            "execution_authority_sha256"
        ],
        "manifest_identity": context.manifest_identity,
        "manifest_id": context.manifest["manifest_id"],
        "execution_manifest_sha256": context.manifest[
            "execution_manifest_sha256"
        ],
        "panel_object_identity": context.manifest["panel_object_identity"],
        "panel_id": context.manifest["panel_id"],
        "panel_index_sha256": context.manifest["panel_index_sha256"],
        "source_commit_sha": context.manifest["source_commit_sha"],
        "immutable_image": context.manifest["immutable_image"],
        "output_prefix": context.manifest["output_prefix"],
        "panel_release_uri": panel_release_uri_for_output_prefix(
            str(context.manifest["output_prefix"])
        ),
        "verifier_runtime_binding": verifier_runtime,
        "source_member_count": AUTHORITATIVE_SLATE_COUNT,
        "accepted_slate_count": len(rows),
        "ordered_slate_acceptances": rows,
        "ordered_slate_acceptances_sha256": batch.canonical_sha256(rows),
        "ordered_result_identities_sha256": batch.canonical_sha256(
            result_identities
        ),
        "support_fraction": {
            "numerator": 4,
            "denominator": 5,
            "comparison_operator": ">=",
            "integer_counts_only": True,
        },
        "fold_boundary": {
            "passed": fold_passed,
            "total": fold_total,
            "minimum_passed": FOLD_PASS_MINIMUM,
            "passed_times_denominator": fold_passed * 5,
            "total_times_numerator": fold_total * 4,
            "meets_boundary": fold_supported,
        },
        "final_fit_boundary": {
            "passed": final_passed,
            "total": final_total,
            "minimum_passed": FINAL_PASS_MINIMUM,
            "passed_times_denominator": final_passed * 5,
            "total_times_numerator": final_total * 4,
            "meets_boundary": final_supported,
        },
        "joint_support_boundary_passed": joint,
        "literal_coverage_ge_230_generally_supported": joint,
        "verification": {
            "execution_authority_and_published_panel_replayed": True,
            "all_54_acceptance_identities_replayed": True,
            "all_54_result_identities_replayed": True,
            "all_54_members_and_carriers_reconstructed": True,
            "all_54_science_surfaces_independently_recomputed": True,
            "all_source_ordinals_complete_and_ordered": True,
            "exact_270_fold_gates_verified": True,
            "exact_54_final_fit_gates_verified": True,
            "runtime_source_and_image_verified": True,
            "realized_outcomes_read": False,
        },
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["t230_panel_release_sha256"] = batch.canonical_sha256(body)
    return body


def validate_t230_panel_release_v1(
    value: object,
    *,
    execution_authority_identity: Mapping[str, object],
    finalizer_runtime_measurement_identity: Mapping[str, object],
    acceptance_identities: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Rebuild the authoritative-size outcome-blind panel release exactly."""
    item = dict(_mapping(value, label="T230 panel release"))
    _exact_keys(item, _PANEL_RELEASE_KEYS, label="T230 panel release")
    _false_authorities(item, label="T230 panel release")
    _nested_false_authorities(item, label="T230 panel release")
    _guard_nested_authority_keys(item, label="T230 panel release")
    _validate_self_hash(
        item, field="t230_panel_release_sha256", label="T230 panel release"
    )
    expected = build_t230_panel_release_v1(
        execution_authority_identity=execution_authority_identity,
        finalizer_runtime_measurement_identity=finalizer_runtime_measurement_identity,
        acceptance_identities=acceptance_identities,
        read_exact=read_exact,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("T230 panel release differs from 54-acceptance replay")
    return expected


__all__ = [
    "AUTHORITATIVE_SLATE_COUNT",
    "AUTHORITY_FILENAME",
    "CorpusExtremeTailPanelExecutionError",
    "ENTRY_BUDGETS",
    "FOLD_GATE_TOTAL",
    "FOLD_PASS_MINIMUM",
    "FINAL_GATE_TOTAL",
    "FINAL_PASS_MINIMUM",
    "MANIFEST_FILENAME",
    "EXECUTION_AUTHORITY_SCHEMA",
    "EXPECTED_BAKED_IMAGE_EVIDENCE_PATH",
    "EXPECTED_VERIFIER_IMPLEMENTATION_SHA256",
    "EXPECTED_WORKER_IMPLEMENTATION_SHA256",
    "FROZEN_G0_AUTHORITY_LOCK_PATH",
    "FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH",
    "FROZEN_G0_LANE_RECEIPT_PATHS",
    "FROZEN_G0_PANEL_URI",
    "FROZEN_G0_PUBLICATION_RECEIPT_PATH",
    "IMAGE_EVIDENCE_SCHEMA",
    "G0_AUTHORITY_LOCK_SCHEMA",
    "PANEL_RELEASE_FILENAME",
    "PANEL_RELEASE_SCHEMA",
    "PUBLICATION_MODE",
    "ReadExact",
    "RUNTIME_MEASUREMENT_SCHEMA",
    "SLATE_ACCEPTANCE_SCHEMA",
    "SLATE_RESULT_SCHEMA",
    "WORLDS_PER_BLOCK",
    "authority_uri_for_output_prefix",
    "build_g0_authority_lock_v1",
    "build_t230_execution_authority_v1",
    "build_t230_panel_release_v1",
    "execute_t230_panel_slate_v1",
    "frozen_t230_verifier_implementation_v1",
    "frozen_t230_worker_implementation_v1",
    "image_evidence_uri_for_output_prefix",
    "manifest_uri_for_output_prefix",
    "measure_t230_runtime_v1",
    "panel_release_uri_for_output_prefix",
    "replay_published_v12_panel_v1",
    "reopen_t230_execution_authority_v1",
    "reopen_t230_panel_execution_manifest_v1",
    "runtime_measurement_uri_for_output_prefix",
    "validate_t230_panel_release_v1",
    "validate_g0_authority_lock_v1",
    "validate_t230_runtime_measurement_v1",
    "validate_t230_slate_acceptance_v1",
    "validate_t230_slate_result_v1",
    "verify_t230_panel_slate_v1",
]
