"""Trusted 54-slate, outcome-free R6 matchup-source batch orchestration.

The predecessor modules deliberately separate candidate authority, capture
planning, component production, per-slate source publication, and terminal
source authority.  This module supplies the missing operational seam without
weakening those boundaries:

* the trusted public entrypoint loads the sole clean tracked capture-plan lock;
* its terminal fixed-G0 candidate root and predecessors are replayed once;
* exact object reads are content-identity cached for the whole invocation;
* a tracked candidate-rooted capture plan is replayed against the cached
  authority and its immutable prerequisites;
* the plan's adapter-final-lock, implementation and G0 predecessors are read
  internally from real Git/current no-follow bytes, never supplied by a caller;
* loaded module origins, critical callable code and immutable image identity
  are bound to the measured clean dependency closure;
* every possible output URI is enumerated before a write client exists, and
  every backend attempt is charged against invocation-wide operation/byte
  limits before the backend call;
* the complete 54-slate component panel is produced and deeply reopened;
* source export/capture receipt/operator result triples are published in
  ordinal order and cross-bound to the authoritative candidate artifacts;
* the candidate-rooted source release is built, all 54 members are deeply
  reopened, and published root-last; and
* bounded per-slate batch receipts are published before one terminal batch
  root, which is always the final create-once request.

The public publication boundary accepts only a run ID: no candidate root,
capture-plan body, final-lock bytes, prerequisite bodies, Git callback,
repository path, or code identity.  It derives those values through no-follow
worktree reads, fixed real-Git adapters and generation-pinned object identities.
It also constructs its own fixed-project GCS transports; callers cannot replace
the exact reader, exact URI capability or create-once writer.  Private
injectable helpers exist only for hermetic contract tests and do not grant an
external trust boundary.

The cached-authority helpers intentionally compose the already hardened
private reducers from the successor modules.  Their exact Git identities are
therefore part of the tracked capture plan and batch code bindings.  This
avoids repeating the expensive candidate predecessor replay while preserving
all byte, candidate, catalog, producer, and source checks.

No public function accepts candidate bodies, selected candidate identities,
scores, outcomes, selector outputs, graph writes, fill/retrieval policy,
promotion decisions, deployments, or production-policy authority.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import importlib
import inspect
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
from threading import Lock
from types import CodeType
from typing import Final

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v1 as candidate_authority,
)
from nfl_dfs.research import (
    corpus_r6_matchup_capture_plan_candidate_authority_v2 as capture_v2,
)
from nfl_dfs.research import corpus_r6_matchup_capture_plan_v1 as capture_v1
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_candidate_authority_v2
    as component_v2,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_v1 as component_v1,
)
from nfl_dfs.research import corpus_r6_matchup_source_operator_v2 as operator_v2
from nfl_dfs.research import (
    corpus_r6_matchup_source_release_candidate_authority_v2 as release_v2,
)
from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as release_v1
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


BATCH_RELEASE_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-candidate-authority/v1"
)
BATCH_MEMBER_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-member-candidate-authority/v1"
)
PUBLICATION_MODE: Final = (
    "create_once_component_receipt_then_members_then_source_root_then_"
    "work_receipt_then_batch_root"
)
OUTPUT_BUCKET: Final = candidate_authority.OUTPUT_BUCKET
OUTPUT_NAMESPACE: Final = "research/corpus-r6-matchup-source-batches"
ROOT_FILENAME: Final = "matchup-source-batch-release.json"
COMPONENT_RECEIPT_FILENAME: Final = (
    "component-publication-candidate-authority-receipt.json"
)
PUBLICATION_WORK_RECEIPT_FILENAME: Final = "publication-work-receipt.json"
MAX_EXACT_READ_CACHE_BYTES: Final = 128 * 1024 * 1024
MAX_EXACT_OBJECT_BYTES: Final = 512 * 1024 * 1024
MAX_EXACT_READ_INVOCATION_BYTES: Final = 64 * 1024 * 1024 * 1024
MAX_EXACT_READ_OPERATIONS: Final = 200_000
MAX_CREATE_ONCE_INVOCATION_BYTES: Final = 64 * 1024 * 1024 * 1024
EXACT_READ_BUDGET_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-exact-read-budget/v1"
)
OUTPUT_URI_INVENTORY_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-output-uri-inventory/v1"
)
PUBLICATION_WORK_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-publication-work-receipt/v1"
)
CREATE_ONCE_BUDGET_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-create-once-budget/v1"
)
RUNTIME_ATTESTATION_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-loaded-runtime-attestation/v1"
)
CAPTURE_PLAN_GIT_REPLAY_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-capture-plan-git-replay/v1"
)
BATCH_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py"
)
DEPENDENCY_CLOSURE_SCHEMA: Final = (
    "corpus-r6-matchup-source-batch-executed-dependency-closure/v1"
)
CREATE_ONCE_RESUME_POLICY: Final = (
    "same_source_commit_only;restore_exact_clean_commit_before_resume;"
    "generation_exact_reopen_and_byte_equality;different_bytes_fail_closed;"
    "complete_graph_rebuilt_before_terminal_root"
)
REPOSITORY_ROOT: Final = Path(__file__).absolute().parents[3]
GIT_EXECUTABLE: Final = Path("/usr/bin/git")
PRODUCTION_PROJECT: Final = "nfl-predictions-503414"
PRODUCTION_GCS_API_ENDPOINT: Final = "https://storage.googleapis.com"
PRODUCTION_GCS_UNIVERSE_DOMAIN: Final = "googleapis.com"
FORBIDDEN_GCS_ENDPOINT_ENV_VARS: Final = (
    "STORAGE_EMULATOR_HOST",
    "API_ENDPOINT_OVERRIDE",
)
CREATE_ONCE_ATTEMPTS: Final = 3
IMAGE_DIGEST_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_IMAGE_DIGEST"
IMAGE_REFERENCE_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_IMAGE_REFERENCE"
IMAGE_SOURCE_COMMIT_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_IMAGE_SOURCE_COMMIT"
PUBLISH_ENABLE_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_BATCH_PUBLISH"

# This is the fixed repository-local Python dependency closure reachable from
# the batch's authority-bearing modules at v1.  It is intentionally explicit:
# adding, removing, or moving a local dependency is a reviewed schema change,
# not something a dirty worktree can silently teach the publisher at runtime.
EXECUTED_DEPENDENCY_MODULE_PATHS: Final = (
    "src/nfl_dfs/optimizer/lineup.py",
    "src/nfl_dfs/research/corpus_artifact_source_authority.py",
    "src/nfl_dfs/research/corpus_batch_retrieval_runner_v2.py",
    "src/nfl_dfs/research/corpus_extreme_tail_census.py",
    "src/nfl_dfs/research/corpus_extreme_tail_panel_execution.py",
    "src/nfl_dfs/research/corpus_extreme_tail_panel_release.py",
    "src/nfl_dfs/research/corpus_extreme_tail_retrieval_suite.py",
    "src/nfl_dfs/research/corpus_extreme_tail_support_switch.py",
    "src/nfl_dfs/research/corpus_legal_feasibility.py",
    "src/nfl_dfs/research/corpus_parametric_batch.py",
    "src/nfl_dfs/research/corpus_parametric_snapshot.py",
    "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_release_v1.py",
    "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_v1.py",
    BATCH_MODULE_PATH,
    "src/nfl_dfs/research/corpus_r6_matchup_capture_plan_candidate_authority_v2.py",
    "src/nfl_dfs/research/corpus_r6_matchup_capture_plan_v1.py",
    "src/nfl_dfs/research/corpus_r6_matchup_component_producer_v1.py",
    (
        "src/nfl_dfs/research/"
        "corpus_r6_matchup_component_publication_candidate_authority_v2.py"
    ),
    "src/nfl_dfs/research/corpus_r6_matchup_component_publication_v1.py",
    operator_v2.OPERATOR_MODULE_PATH,
    "src/nfl_dfs/research/corpus_r6_matchup_source_release_candidate_authority_v2.py",
    "src/nfl_dfs/research/corpus_r6_matchup_source_release_v1.py",
    "src/nfl_dfs/research/corpus_r6_matchup_source_v1.py",
    "src/nfl_dfs/research/corpus_r6_matchup_source_v2.py",
    "src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_adapter_v1.py",
    "src/nfl_dfs/research/corpus_r6_player_catalog_fixed_g0_projection_successor_v1.py",
    "src/nfl_dfs/research/corpus_r6_player_catalog_v1.py",
    "src/nfl_dfs/research/corpus_r6_v2_one_slate_execution.py",
    "src/nfl_dfs/research/corpus_retrieval_engine.py",
    "src/nfl_dfs/research/corpus_v12_import.py",
    "src/nfl_dfs/research/corpus_v12_panel_index.py",
    "src/nfl_dfs/research/effective_policy_rule_inventory.py",
    "src/nfl_dfs/research/lr8_exact_solvers.py",
    "src/nfl_dfs/research/lr8_historical_arm.py",
    "src/nfl_dfs/research/lr8_later_period_source.py",
    "src/nfl_dfs/research/lr8_training_source.py",
    "src/nfl_dfs/research/object_identity.py",
    "src/nfl_dfs/research/residual_world_columns.py",
    "src/nfl_dfs/research/residual_world_run_context.py",
)

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,80}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY_RELATIVE_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
GitHead = candidate_authority.GitHead
GitBlob = candidate_authority.GitBlob
GitStatus = candidate_authority.GitStatus


class CorpusR6MatchupBatchCandidateAuthorityV1Error(ValueError):
    """The 54-slate candidate-authority batch failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupBatchCandidateAuthorityV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    return source.canonical_json_bytes(value)


def canonical_sha256(value: object) -> str:
    return source.canonical_sha256(value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "outcome_freedom_status": {
            "independent_source_lineage_attested": False,
            "outcome_free_authority": False,
            "promotion_eligible": False,
            "unattested_by_this_batch_boundary": True,
        },
        "promotion_eligible": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def output_prefix_for_run_v1(run_id: object) -> str:
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("batch run ID must be 8..81 lowercase letters/digits/hyphens")
    return f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{run_id}/"


def _output_uri_inventory_v1(
    *, run_id: object, plan_value: object
) -> dict[str, object]:
    """Derive every permitted output URI before constructing a write client."""
    run = str(run_id)
    prefix = output_prefix_for_run_v1(run)
    try:
        plan = capture_v2.validate_capture_plan_lock_v2(plan_value)
    except capture_v2.CorpusR6MatchupCapturePlanCandidateAuthorityV2Error as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(str(exc)) from exc
    producer_namespace = str(plan["producer_namespace"])
    entries_by_uri: dict[str, dict[str, object]] = {}

    def retain(uri: str, *, phase: str) -> None:
        _gcs_parts_v1(uri)
        prior = entries_by_uri.get(uri)
        entry = {"uri": uri, "phase": phase}
        if prior is not None and prior != entry:
            _fail("one output URI is assigned to different publication phases")
        entries_by_uri[uri] = entry

    registry = source.frozen_role_registry_v2()
    roles = _sequence(registry["roles"], label="frozen role registry")
    tasks = _sequence(plan["source_task_bindings"], label="capture-plan tasks")
    if len(tasks) != source.TASK_COUNT:
        _fail("output inventory requires exactly 54 capture-plan tasks")
    for ordinal, task_value in enumerate(tasks):
        task = _mapping(task_value, label=f"capture-plan task[{ordinal}]")
        slate_id = str(task["slate"]["slate_id"])
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
        # The schedule-spine URI is the role-0/period-0 slice above.  Retaining
        # it again proves the two fixed producers agree on one semantic URI.
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
    retain(
        f"{producer_namespace}producer-release.json",
        phase="component-producer-root",
    )
    retain(
        f"{prefix}{COMPONENT_RECEIPT_FILENAME}",
        phase="batch-component-receipt",
    )
    for ordinal, task_value in enumerate(tasks):
        task = _mapping(task_value, label=f"capture-plan task[{ordinal}]")
        slate_id = str(task["slate"]["slate_id"])
        task_prefix = f"{prefix}source-task-{ordinal:02d}-{slate_id}/"
        for filename in (
            "matchup-source-export.json",
            "matchup-capture-receipt.json",
            "matchup-operator-result.json",
        ):
            retain(f"{task_prefix}{filename}", phase="source-triple")
        retain(f"{task_prefix}batch-member.json", phase="batch-member")
    retain(
        f"{prefix}{release_v2.ROOT_FILENAME}", phase="source-release-root"
    )
    retain(
        f"{prefix}{PUBLICATION_WORK_RECEIPT_FILENAME}",
        phase="preterminal-publication-work-receipt",
    )
    terminal_root_uri = f"{prefix}{ROOT_FILENAME}"
    retain(terminal_root_uri, phase="terminal-batch-root")
    entries = sorted(entries_by_uri.values(), key=lambda value: str(value["uri"]))
    uris = [str(value["uri"]) for value in entries]
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
        "publication_work_receipt_uri": (
            f"{prefix}{PUBLICATION_WORK_RECEIPT_FILENAME}"
        ),
        "terminal_root_uri": terminal_root_uri,
        "inventory_derived_before_write_client_construction": True,
        "broad_prefix_write_authority_allowed": False,
        "unexpected_uri_backend_call_possible": False,
    }
    body["output_uri_inventory_sha256"] = canonical_sha256(body)
    return _normalize_output_uri_inventory_v1(body)


def _normalize_output_uri_inventory_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="output URI inventory")
    expected_fields = {
        "schema_version", "run_id", "namespace", "producer_namespace",
        "entries", "uris", "uri_count", "uri_manifest_sha256",
        "entry_manifest_sha256", "publication_work_receipt_uri",
        "terminal_root_uri",
        "inventory_derived_before_write_client_construction",
        "broad_prefix_write_authority_allowed",
        "unexpected_uri_backend_call_possible", "output_uri_inventory_sha256",
    }
    if set(item) != expected_fields:
        _fail("output URI inventory fields differ")
    retained = _digest(
        item["output_uri_inventory_sha256"], label="output inventory hash"
    )
    unhashed = dict(item)
    del unhashed["output_uri_inventory_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("output URI inventory self-hash differs")
    expected = _output_uri_inventory_v1_unchecked_reference_v1(item)
    if canonical_json_bytes(expected) != canonical_json_bytes(item):
        _fail("output URI inventory fixed law differs")
    return dict(item)


def _output_uri_inventory_v1_unchecked_reference_v1(
    item: Mapping[str, object],
) -> dict[str, object]:
    """Normalize a built inventory without recursively rebuilding the plan."""
    entries_raw = _sequence(item["entries"], label="output inventory entries")
    entries: list[dict[str, object]] = []
    allowed_phases = {
        "component-producer-object", "component-producer-root",
        "batch-component-receipt", "source-triple", "batch-member",
        "source-release-root", "preterminal-publication-work-receipt",
        "terminal-batch-root",
    }
    for ordinal, value in enumerate(entries_raw):
        entry = _mapping(value, label=f"output inventory entry[{ordinal}]")
        if (
            set(entry) != {"uri", "phase"}
            or type(entry["uri"]) is not str
            or entry["phase"] not in allowed_phases
        ):
            _fail("output inventory entry differs")
        _gcs_parts_v1(entry["uri"])
        entries.append(entry)
    uris = _sequence(item["uris"], label="output inventory URIs")
    if (
        any(type(uri) is not str for uri in uris)
        or uris != sorted(uris)
        or len(uris) != len(set(uris))
        or entries != sorted(entries, key=lambda value: str(value["uri"]))
        or uris != [entry["uri"] for entry in entries]
    ):
        _fail("output inventory exact URI set differs")
    run_id = str(item["run_id"])
    prefix = output_prefix_for_run_v1(run_id)
    normalized = dict(item)
    normalized["entries"] = entries
    normalized["uris"] = uris
    if (
        item["schema_version"] != OUTPUT_URI_INVENTORY_SCHEMA
        or item["namespace"] != prefix
        or type(item["producer_namespace"]) is not str
        or not str(item["producer_namespace"]).endswith("/")
        or item["uri_count"] != len(uris)
        or item["uri_manifest_sha256"] != canonical_sha256(uris)
        or item["entry_manifest_sha256"] != canonical_sha256(entries)
        or item["publication_work_receipt_uri"]
        != f"{prefix}{PUBLICATION_WORK_RECEIPT_FILENAME}"
        or item["terminal_root_uri"] != f"{prefix}{ROOT_FILENAME}"
        or item["inventory_derived_before_write_client_construction"] is not True
        or item["broad_prefix_write_authority_allowed"] is not False
        or item["unexpected_uri_backend_call_possible"] is not False
    ):
        _fail("output URI inventory fixed law differs")
    return normalized


def _public_batch_root_identity_v1(value: object) -> dict[str, object]:
    """Validate the fixed batch namespace before any caller-selected read."""
    identity = _identity(value, label="public batch release root")
    bucket, name = _gcs_parts_v1(identity["uri"])
    namespace_prefix = f"{OUTPUT_NAMESPACE}/"
    if bucket != OUTPUT_BUCKET or not name.startswith(namespace_prefix):
        _fail("batch release root escapes the fixed source-batch namespace")
    suffix = name[len(namespace_prefix):]
    parts = suffix.split("/")
    if len(parts) != 2 or parts[1] != ROOT_FILENAME:
        _fail("batch release root differs from the fixed root object law")
    run_id = parts[0]
    if (
        _RUN_ID.fullmatch(run_id) is None
        or identity["uri"] != f"{output_prefix_for_run_v1(run_id)}{ROOT_FILENAME}"
    ):
        _fail("batch release root differs from the fixed run namespace law")
    return identity


def _canonical_repository_relative_path(value: object, *, label: str) -> str:
    if type(value) is not str or _REPOSITORY_RELATIVE_PATH.fullmatch(value) is None:
        _fail(f"{label} must be one canonical repository-relative path")
    path = Path(value)
    if (
        path.is_absolute()
        or value != path.as_posix()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        _fail(f"{label} must be one canonical repository-relative path")
    return value


def _trusted_repository_root_v1() -> Path:
    """Return the code-owned checkout root or fail on any path alias."""
    root = REPOSITORY_ROOT
    try:
        before = os.lstat(root)
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "trusted repository root is absent"
        ) from exc
    if (
        not root.is_absolute()
        or resolved != root
        or stat.S_ISLNK(before.st_mode)
        or not stat.S_ISDIR(before.st_mode)
    ):
        _fail("trusted repository root is not one canonical nonsymlink directory")
    return root


def _secure_read_repository_file_v1(
    repository_root: Path,
    relative_path: object,
    *,
    label: str,
) -> bytes:
    """Read one regular worktree inode with no followed path components.

    Directory file descriptors keep the path walk stable.  The before/after
    inode metadata check rejects in-place mutation while the bytes are read.
    This is the filesystem half of the Git-blob/current-byte equality law.
    """
    relative = _canonical_repository_relative_path(relative_path, label=label)
    try:
        root_before = os.lstat(repository_root)
        resolved = repository_root.resolve(strict=True)
    except OSError as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"{label} repository root is absent"
        ) from exc
    if (
        not repository_root.is_absolute()
        or resolved != repository_root
        or stat.S_ISLNK(root_before.st_mode)
        or not stat.S_ISDIR(root_before.st_mode)
        or not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_DIRECTORY")
    ):
        _fail(f"{label} repository root/path cannot be read without symlinks")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        directory_flags |= os.O_CLOEXEC
        file_flags |= os.O_CLOEXEC
    opened_directories: list[int] = []
    file_fd: int | None = None
    try:
        opened_directories.append(os.open(repository_root, directory_flags))
        opened_root = os.fstat(opened_directories[0])
        root_identity_fields = ("st_dev", "st_ino", "st_mode", "st_nlink")
        if any(
            getattr(root_before, field) != getattr(opened_root, field)
            for field in root_identity_fields
        ):
            _fail(f"{label} repository root changed before secure traversal")
        for component in Path(relative).parts[:-1]:
            opened_directories.append(
                os.open(
                    component,
                    directory_flags,
                    dir_fd=opened_directories[-1],
                )
            )
            current_stat = os.fstat(opened_directories[-1])
            if not stat.S_ISDIR(current_stat.st_mode):
                _fail(f"{label} parent is not a regular directory")
        file_fd = os.open(
            Path(relative).parts[-1],
            file_flags,
            dir_fd=opened_directories[-1],
        )
        opened = os.fstat(file_fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            _fail(f"{label} is not one unaliased regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(file_fd)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(
            getattr(opened, field) != getattr(after, field)
            for field in stable_fields
        ):
            _fail(f"{label} changed while being read")
        raw = b"".join(chunks)
        if len(raw) != opened.st_size or not raw:
            _fail(f"{label} byte count differs")
        root_after = os.lstat(repository_root)
        if any(
            getattr(opened_root, field) != getattr(root_after, field)
            for field in root_identity_fields
        ):
            _fail(f"{label} repository root changed during secure traversal")
        return raw
    except OSError as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"{label} secure read failed"
        ) from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        for directory_fd in reversed(opened_directories):
            os.close(directory_fd)


def _clean_git_environment_v1() -> dict[str, str]:
    # Use an allowlist, not a denylist: Git has many repository, object,
    # replacement-ref, config and execution environment redirects.  None is
    # inherited across this authority boundary.
    return {
        "PATH": os.defpath,
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
    }


def _run_trusted_git_v1(repository_root: Path, arguments: Sequence[str]) -> bytes:
    root = _trusted_repository_root_v1()
    if repository_root != root or any(type(value) is not str for value in arguments):
        _fail("trusted Git invocation escaped the code-owned repository")
    try:
        git_stat = os.lstat(GIT_EXECUTABLE)
    except OSError as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "fixed Git executable is absent"
        ) from exc
    if (
        stat.S_ISLNK(git_stat.st_mode)
        or not stat.S_ISREG(git_stat.st_mode)
        or git_stat.st_nlink != 1
        or not os.access(GIT_EXECUTABLE, os.X_OK)
    ):
        _fail("fixed Git executable is not one executable regular file")
    try:
        completed = subprocess.run(
            [
                str(GIT_EXECUTABLE),
                "--no-replace-objects",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-C",
                str(root),
                *arguments,
            ],
            cwd=root,
            env=_clean_git_environment_v1(),
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "trusted Git invocation failed"
        ) from exc
    return completed.stdout


def _trusted_git_head_v1(repository_root: Path) -> str:
    raw = _run_trusted_git_v1(
        repository_root, ["rev-parse", "--verify", "HEAD^{commit}"]
    )
    try:
        value = raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "trusted Git HEAD is not ASCII"
        ) from exc
    if _COMMIT.fullmatch(value) is None or raw != f"{value}\n".encode("ascii"):
        _fail("trusted Git HEAD differs")
    top = _run_trusted_git_v1(
        repository_root, ["rev-parse", "--show-toplevel"]
    )
    try:
        top_path = Path(top.decode("utf-8").strip())
    except UnicodeDecodeError as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "trusted Git top-level path is not UTF-8"
        ) from exc
    if top != f"{top_path}\n".encode("utf-8") or top_path != repository_root:
        _fail("trusted Git checkout root differs")
    return value


def _trusted_git_blob_v1(
    repository_root: Path, commit_sha: str, relative_path: str,
) -> bytes:
    if _COMMIT.fullmatch(commit_sha) is None:
        _fail("trusted Git blob commit differs")
    path = _canonical_repository_relative_path(
        relative_path, label="trusted Git blob path"
    )
    raw = _run_trusted_git_v1(
        repository_root, ["show", "--no-ext-diff", f"{commit_sha}:{path}"]
    )
    if not raw:
        _fail("trusted Git blob is empty")
    return raw


def _trusted_git_status_v1(
    repository_root: Path, relative_paths: Sequence[str],
) -> bytes:
    paths = [
        _canonical_repository_relative_path(value, label="trusted Git status path")
        for value in relative_paths
    ]
    if not paths or len(paths) != len(set(paths)):
        _fail("trusted Git status path set differs")
    return _run_trusted_git_v1(
        repository_root,
        ["status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
    )


def _gcs_parts_v1(uri: object) -> tuple[str, str]:
    if type(uri) is not str or not uri.startswith("gs://"):
        _fail("GCS URI differs")
    remainder = uri[5:]
    if "/" not in remainder or "//" in remainder or ".." in remainder:
        _fail("GCS URI differs")
    bucket, name = remainder.split("/", 1)
    if not bucket or not name:
        _fail("GCS URI differs")
    return bucket, name


def _gcs_not_found_v1(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    return (
        code == 404
        or callable(code) and code() == 404
        or type(exc).__name__ == "NotFound"
    )


class GenerationPinnedGCSBatchTransportV1:
    """Pinned reader and exact-inventory, precharged create-once writer."""

    __slots__ = (
        "_client",
        "_completed_write_uris",
        "_expected_write_uris",
        "_max_object_bytes",
        "_max_invocation_read_bytes",
        "_max_invocation_write_bytes",
        "_max_read_operations",
        "_read_bytes_reserved",
        "_read_charges",
        "_read_lock",
        "_read_operations_reserved",
        "_write_bytes_reserved",
        "_write_charges",
        "_write_lock",
        "_write_operations_reserved",
    )

    def __init__(
        self,
        client: object,
        *,
        expected_write_uris: Sequence[str] = (),
        max_object_bytes: int = MAX_EXACT_OBJECT_BYTES,
        max_invocation_read_bytes: int = MAX_EXACT_READ_INVOCATION_BYTES,
        max_read_operations: int = MAX_EXACT_READ_OPERATIONS,
        max_invocation_write_bytes: int = MAX_CREATE_ONCE_INVOCATION_BYTES,
    ) -> None:
        if (
            getattr(client, "project", None) != PRODUCTION_PROJECT
            or str(getattr(client, "api_endpoint", "")).rstrip("/")
            != PRODUCTION_GCS_API_ENDPOINT
            or getattr(client, "universe_domain", None)
            != PRODUCTION_GCS_UNIVERSE_DOMAIN
            or getattr(client, "_is_emulator_set", None) is not False
        ):
            _fail("GCS client differs from the fixed genuine production endpoint")
        for value, ceiling, label in (
            (max_object_bytes, MAX_EXACT_OBJECT_BYTES, "object byte"),
            (
                max_invocation_read_bytes,
                MAX_EXACT_READ_INVOCATION_BYTES,
                "invocation byte",
            ),
            (max_read_operations, MAX_EXACT_READ_OPERATIONS, "operation"),
        ):
            if type(value) is not int or not 1 <= value <= ceiling:
                _fail(f"GCS exact-read {label} bound differs")
        if max_object_bytes > max_invocation_read_bytes:
            _fail("GCS per-object byte bound exceeds the invocation byte bound")
        if (
            type(max_invocation_write_bytes) is not int
            or not 1 <= max_invocation_write_bytes
            <= MAX_CREATE_ONCE_INVOCATION_BYTES
            or max_object_bytes > max_invocation_write_bytes
        ):
            _fail("GCS create-once invocation byte bound differs")
        uris: list[str] = []
        for value in expected_write_uris:
            if type(value) is not str:
                _fail("GCS expected write URI differs")
            _gcs_parts_v1(value)
            uris.append(value)
        if (
            len(uris) != len(set(uris))
            or uris != sorted(uris)
        ):
            _fail("GCS expected write URI inventory is not unique and sorted")
        self._client = client
        self._expected_write_uris = tuple(uris)
        self._max_object_bytes = max_object_bytes
        self._max_invocation_read_bytes = max_invocation_read_bytes
        self._max_invocation_write_bytes = max_invocation_write_bytes
        self._max_read_operations = max_read_operations
        self._read_bytes_reserved = 0
        self._read_operations_reserved = 0
        self._read_charges: list[dict[str, object]] = []
        self._read_lock = Lock()
        self._write_bytes_reserved = 0
        self._write_operations_reserved = 0
        self._write_charges: list[dict[str, object]] = []
        self._completed_write_uris: set[str] = set()
        self._write_lock = Lock()

    @property
    def expected_write_uris(self) -> tuple[str, ...]:
        return self._expected_write_uris

    def _reserve_write_attempt_v1(
        self, *, uri: str, byte_count: int, attempt: int
    ) -> None:
        """Atomically charge a failed-or-successful upload before the backend."""
        if (
            uri not in self._expected_write_uris
            or type(byte_count) is not int
            or not 1 <= byte_count <= self._max_object_bytes
            or type(attempt) is not int
            or not 1 <= attempt <= CREATE_ONCE_ATTEMPTS
        ):
            _fail("GCS create-once write charge differs from exact inventory")
        with self._write_lock:
            next_operations = self._write_operations_reserved + 1
            next_bytes = self._write_bytes_reserved + byte_count
            max_operations = len(self._expected_write_uris) * CREATE_ONCE_ATTEMPTS
            if (
                next_operations > max_operations
                or next_bytes > self._max_invocation_write_bytes
            ):
                _fail("GCS cumulative create-once invocation budget exhausted")
            charge: dict[str, object] = {
                "ordinal": self._write_operations_reserved,
                "uri": uri,
                "attempt": attempt,
                "bytes": byte_count,
                "charged_before_backend_call": True,
                "failed_attempts_remain_charged": True,
            }
            charge["write_charge_sha256"] = canonical_sha256(charge)
            self._write_operations_reserved = next_operations
            self._write_bytes_reserved = next_bytes
            self._write_charges.append(charge)

    def write_budget_receipt(self) -> dict[str, object]:
        with self._write_lock:
            completed = sorted(self._completed_write_uris)
            pending = sorted(set(self._expected_write_uris) - set(completed))
            body: dict[str, object] = {
                "schema_version": CREATE_ONCE_BUDGET_SCHEMA,
                "expected_write_uris": list(self._expected_write_uris),
                "expected_write_uri_manifest_sha256": canonical_sha256(
                    list(self._expected_write_uris)
                ),
                "expected_write_uri_count": len(self._expected_write_uris),
                "max_write_operations": (
                    len(self._expected_write_uris) * CREATE_ONCE_ATTEMPTS
                ),
                "max_invocation_write_bytes": self._max_invocation_write_bytes,
                "write_operations_reserved": self._write_operations_reserved,
                "write_bytes_reserved": self._write_bytes_reserved,
                "write_charges": [dict(value) for value in self._write_charges],
                "write_charge_manifest_sha256": canonical_sha256(
                    self._write_charges
                ),
                "completed_write_uris": completed,
                "completed_write_uri_manifest_sha256": canonical_sha256(completed),
                "pending_write_uris": pending,
                "pending_write_uri_manifest_sha256": canonical_sha256(pending),
                "all_backend_writes_charged_before_call": True,
                "failed_attempts_remain_charged": True,
                "unexpected_uri_backend_call_possible": False,
                "per_invocation_only": True,
                "cross_process_durable_ledger": False,
            }
        body["publication_work_receipt_sha256"] = canonical_sha256(body)
        return body

    def require_completed_exactly_v1(
        self, *, completed_uris: Sequence[str], pending_uris: Sequence[str]
    ) -> None:
        expected_completed = sorted(completed_uris)
        expected_pending = sorted(pending_uris)
        if (
            len(expected_completed) != len(set(expected_completed))
            or len(expected_pending) != len(set(expected_pending))
            or set(expected_completed) & set(expected_pending)
            or sorted(expected_completed + expected_pending)
            != list(self._expected_write_uris)
        ):
            _fail("GCS publication completion partition differs from inventory")
        with self._write_lock:
            if (
                sorted(self._completed_write_uris) != expected_completed
                or sorted(
                    set(self._expected_write_uris)
                    - self._completed_write_uris
                ) != expected_pending
            ):
                _fail("GCS publication completion state differs from inventory")

    def _reserve_payload_read_v1(
        self,
        *,
        uri: str,
        generation: str | None,
        byte_count: int,
        purpose: str,
    ) -> None:
        if (
            type(byte_count) is not int
            or not 1 <= byte_count <= self._max_object_bytes
        ):
            _fail("GCS exact-read object exceeds its fixed byte bound")
        with self._read_lock:
            next_operations = self._read_operations_reserved + 1
            next_bytes = self._read_bytes_reserved + byte_count
            if (
                next_operations > self._max_read_operations
                or next_bytes > self._max_invocation_read_bytes
            ):
                _fail("GCS cumulative exact-read invocation budget exhausted")
            body: dict[str, object] = {
                "ordinal": self._read_operations_reserved,
                "uri": uri,
                "generation": generation,
                "bytes": byte_count,
                "purpose": purpose,
                "charged_before_payload_access": True,
                "failed_reads_remain_charged": True,
            }
            body["read_charge_sha256"] = canonical_sha256(body)
            self._read_operations_reserved = next_operations
            self._read_bytes_reserved = next_bytes
            self._read_charges.append(body)

    def read_budget_receipt(self) -> dict[str, object]:
        with self._read_lock:
            body: dict[str, object] = {
                "schema_version": EXACT_READ_BUDGET_SCHEMA,
                "ledger_kind": "genuine-production-gcs-transport",
                "max_object_bytes": self._max_object_bytes,
                "max_invocation_read_bytes": self._max_invocation_read_bytes,
                "max_read_operations": self._max_read_operations,
                "read_bytes_reserved": self._read_bytes_reserved,
                "read_operations_reserved": self._read_operations_reserved,
                "read_charges": [dict(value) for value in self._read_charges],
                "read_charge_manifest_sha256": canonical_sha256(
                    self._read_charges
                ),
                "all_payload_reads_charged_before_access": True,
                "failed_reads_remain_charged": True,
                "per_invocation_only": True,
                "cross_process_durable_ledger": False,
            }
        body["exact_read_budget_sha256"] = canonical_sha256(body)
        return body

    def read_exact(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="generation-pinned GCS object")
        bucket_name, object_name = _gcs_parts_v1(identity["uri"])
        generation = int(str(identity["generation"]))
        self._reserve_payload_read_v1(
            uri=str(identity["uri"]),
            generation=str(identity["generation"]),
            byte_count=int(identity["bytes"]),
            purpose="generation-pinned-exact-read",
        )
        try:
            blob = self._client.bucket(bucket_name).blob(
                object_name, generation=generation
            )
            blob.reload(if_generation_match=generation)
        except Exception as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
                "generation-pinned GCS metadata read failed"
            ) from exc
        # The caller identity was the pre-access reservation.  Require GCS
        # metadata to fit that exact reservation before any payload transfer;
        # a coherently underreported identity must never induce a larger read.
        if (
            str(getattr(blob, "generation", "")) != identity["generation"]
            or type(getattr(blob, "size", None)) is not int
            or blob.size != identity["bytes"]
            or not 1 <= blob.size <= self._max_object_bytes
        ):
            _fail("generation-pinned GCS metadata exceeds or differs from reservation")
        try:
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
                "generation-pinned GCS read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail("generation-pinned GCS content identity differs")
        return raw

    def _resolve_current_v1(
        self, uri: str, *, absent_ok: bool, precharged_bytes: int | None = None
    ) -> tuple[dict[str, object], bytes] | None:
        bucket_name, object_name = _gcs_parts_v1(uri)
        try:
            current = self._client.bucket(bucket_name).blob(object_name)
            current.reload()
        except Exception as exc:
            if absent_ok and _gcs_not_found_v1(exc):
                return None
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
                "current GCS object resolution failed"
            ) from exc
        generation = str(current.generation)
        if not generation.isdigit() or generation.startswith("0"):
            _fail("current GCS generation differs")
        current_size = getattr(current, "size", None)
        if type(current_size) is not int or not 1 <= current_size <= (
            self._max_object_bytes
        ):
            _fail("current GCS object exceeds its fixed byte bound")
        if precharged_bytes is None:
            self._reserve_payload_read_v1(
                uri=uri,
                generation=generation,
                byte_count=current_size,
                purpose="create-once-current-generation-reopen",
            )
        elif current_size > precharged_bytes:
            _fail("current GCS object exceeds its precharged reopen bytes")
        try:
            pinned = self._client.bucket(bucket_name).blob(
                object_name, generation=int(generation)
            )
            pinned.reload(if_generation_match=int(generation))
            raw = pinned.download_as_bytes(if_generation_match=int(generation))
        except Exception as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
                "current GCS generation exact reopen failed"
            ) from exc
        if (
            type(raw) is not bytes
            or not raw
            or str(pinned.generation) != generation
            or getattr(pinned, "size", None) != current_size
            or len(raw) != current_size
        ):
            _fail("current GCS generation is empty")
        return (
            {
                "uri": uri,
                "generation": generation,
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            raw,
        )

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if (
            type(uri) is not str
            or type(raw) is not bytes
            or not raw
            or len(raw) > self._max_object_bytes
            or uri not in self._expected_write_uris
        ):
            _fail("create-once GCS publication request escapes exact URI inventory")
        with self._write_lock:
            if uri in self._completed_write_uris:
                _fail("create-once GCS URI was requested twice in one invocation")
        bucket_name, object_name = _gcs_parts_v1(uri)
        for attempt in range(1, CREATE_ONCE_ATTEMPTS + 1):
            # Reserve the exact-equality resume read before an upload can make
            # an object visible.  A larger collision is rejected from metadata
            # without downloading it; a smaller collision is overcharged.
            self._reserve_payload_read_v1(
                uri=uri,
                generation=None,
                byte_count=len(raw),
                purpose="create-once-attempt-exact-resume",
            )
            self._reserve_write_attempt_v1(
                uri=uri, byte_count=len(raw), attempt=attempt
            )
            try:
                blob = self._client.bucket(bucket_name).blob(object_name)
                blob.upload_from_string(
                    raw,
                    content_type="application/json",
                    if_generation_match=0,
                )
            except Exception:
                # A collision or ambiguous result is resolved only by a
                # generation-pinned byte comparison.  No overwrite is issued.
                pass
            reopened = self._resolve_current_v1(
                uri,
                absent_ok=True,
                precharged_bytes=len(raw),
            )
            if reopened is None:
                continue
            identity, existing = reopened
            if existing != raw:
                _fail("different bytes occupy a create-once GCS target")
            with self._write_lock:
                self._completed_write_uris.add(uri)
            return identity
        _fail("create-once GCS target remains absent after bounded attempts")


def _trusted_gcs_transport_v1(
    *, expected_write_uris: Sequence[str]
) -> GenerationPinnedGCSBatchTransportV1:
    if any(os.environ.get(name) for name in FORBIDDEN_GCS_ENDPOINT_ENV_VARS):
        _fail("GCS emulator or API endpoint override environment is forbidden")
    try:
        from google.cloud import storage

        client = storage.Client(
            project=PRODUCTION_PROJECT,
            client_options={"api_endpoint": PRODUCTION_GCS_API_ENDPOINT},
        )
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "trusted production GCS client initialization failed"
        ) from exc
    return GenerationPinnedGCSBatchTransportV1(
        client, expected_write_uris=expected_write_uris
    )


def _normalize_publication_work_receipt_v1(
    value: object, *, output_uri_inventory: Mapping[str, object]
) -> dict[str, object]:
    item = _mapping(value, label="publication work receipt")
    expected_fields = {
        "schema_version", "source_commit_sha", "output_uri_inventory",
        "output_uri_inventory_sha256", "transport_budget_snapshot",
        "transport_budget_snapshot_sha256", "completed_preterminal_uris",
        "completed_preterminal_uri_manifest_sha256",
        "receipt_and_terminal_root_pending_at_snapshot",
        "publication_work_receipt_uri", "terminal_root_uri",
        "all_subordinate_outputs_complete_before_receipt",
        "all_backend_writes_precharged_before_call",
        "same_commit_recovery_required", "publication_work_receipt_sha256",
    }
    if set(item) != expected_fields:
        _fail("publication work receipt fields differ")
    retained = _digest(
        item["publication_work_receipt_sha256"],
        label="publication work receipt hash",
    )
    unhashed = dict(item)
    del unhashed["publication_work_receipt_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("publication work receipt self-hash differs")
    inventory = _normalize_output_uri_inventory_v1(output_uri_inventory)
    embedded_inventory = _normalize_output_uri_inventory_v1(
        item["output_uri_inventory"]
    )
    snapshot = _mapping(
        item["transport_budget_snapshot"], label="transport budget snapshot"
    )
    snapshot = _normalize_create_once_budget_receipt_v1(
        snapshot, output_uri_inventory=inventory
    )
    snapshot_sha = _digest(
        item["transport_budget_snapshot_sha256"],
        label="transport budget snapshot hash",
    )
    if canonical_sha256(snapshot) != snapshot_sha:
        _fail("transport budget snapshot hash differs")
    completed = _sequence(
        item["completed_preterminal_uris"],
        label="completed preterminal URIs",
    )
    receipt_uri = str(inventory["publication_work_receipt_uri"])
    terminal_uri = str(inventory["terminal_root_uri"])
    pending = [receipt_uri, terminal_uri]
    expected_completed = sorted(set(inventory["uris"]) - set(pending))
    if (
        embedded_inventory != inventory
        or item["output_uri_inventory_sha256"]
        != inventory["output_uri_inventory_sha256"]
        or snapshot.get("schema_version") != CREATE_ONCE_BUDGET_SCHEMA
        or snapshot.get("expected_write_uris") != inventory["uris"]
        or snapshot.get("expected_write_uri_manifest_sha256")
        != inventory["uri_manifest_sha256"]
        or snapshot.get("completed_write_uris") != expected_completed
        or snapshot.get("pending_write_uris") != sorted(pending)
        or completed != expected_completed
        or item["completed_preterminal_uri_manifest_sha256"]
        != canonical_sha256(completed)
        or item["receipt_and_terminal_root_pending_at_snapshot"]
        != sorted(pending)
        or item["publication_work_receipt_uri"] != receipt_uri
        or item["terminal_root_uri"] != terminal_uri
        or type(item["source_commit_sha"]) is not str
        or _COMMIT.fullmatch(str(item["source_commit_sha"])) is None
        or any(
            item[field] is not True
            for field in (
                "all_subordinate_outputs_complete_before_receipt",
                "all_backend_writes_precharged_before_call",
                "same_commit_recovery_required",
            )
        )
    ):
        _fail("publication work receipt fixed law differs")
    normalized = dict(item)
    normalized["output_uri_inventory"] = inventory
    normalized["transport_budget_snapshot"] = snapshot
    normalized["completed_preterminal_uris"] = completed
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("publication work receipt canonical replay differs")
    return normalized


def _normalize_create_once_budget_receipt_v1(
    value: object, *, output_uri_inventory: Mapping[str, object]
) -> dict[str, object]:
    item = _mapping(value, label="create-once budget receipt")
    expected_fields = {
        "schema_version", "expected_write_uris",
        "expected_write_uri_manifest_sha256", "expected_write_uri_count",
        "max_write_operations", "max_invocation_write_bytes",
        "write_operations_reserved", "write_bytes_reserved", "write_charges",
        "write_charge_manifest_sha256", "completed_write_uris",
        "completed_write_uri_manifest_sha256", "pending_write_uris",
        "pending_write_uri_manifest_sha256",
        "all_backend_writes_charged_before_call", "failed_attempts_remain_charged",
        "unexpected_uri_backend_call_possible", "per_invocation_only",
        "cross_process_durable_ledger", "publication_work_receipt_sha256",
    }
    if set(item) != expected_fields:
        _fail("create-once budget receipt fields differ")
    retained = _digest(
        item["publication_work_receipt_sha256"],
        label="create-once budget receipt hash",
    )
    unhashed = dict(item)
    del unhashed["publication_work_receipt_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("create-once budget receipt self-hash differs")
    inventory = _normalize_output_uri_inventory_v1(output_uri_inventory)
    expected_uris = _sequence(
        item["expected_write_uris"], label="expected write URIs"
    )
    completed = _sequence(
        item["completed_write_uris"], label="completed write URIs"
    )
    pending = _sequence(item["pending_write_uris"], label="pending write URIs")
    charges_raw = _sequence(item["write_charges"], label="write charges")
    charges: list[dict[str, object]] = []
    attempts_by_uri: dict[str, list[int]] = {}
    for ordinal, value in enumerate(charges_raw):
        charge = _mapping(value, label=f"write charge[{ordinal}]")
        if set(charge) != {
            "ordinal", "uri", "attempt", "bytes",
            "charged_before_backend_call", "failed_attempts_remain_charged",
            "write_charge_sha256",
        }:
            _fail("write charge fields differ")
        retained_charge = _digest(
            charge["write_charge_sha256"], label="write charge hash"
        )
        unhashed_charge = dict(charge)
        del unhashed_charge["write_charge_sha256"]
        if (
            canonical_sha256(unhashed_charge) != retained_charge
            or charge["ordinal"] != ordinal
            or charge["uri"] not in expected_uris
            or type(charge["attempt"]) is not int
            or not 1 <= int(charge["attempt"]) <= CREATE_ONCE_ATTEMPTS
            or type(charge["bytes"]) is not int
            or not 1 <= int(charge["bytes"]) <= MAX_EXACT_OBJECT_BYTES
            or charge["charged_before_backend_call"] is not True
            or charge["failed_attempts_remain_charged"] is not True
        ):
            _fail("write charge fixed law differs")
        attempts_by_uri.setdefault(str(charge["uri"]), []).append(
            int(charge["attempt"])
        )
        charges.append(charge)
    if any(
        attempts != list(range(1, len(attempts) + 1))
        for attempts in attempts_by_uri.values()
    ):
        _fail("create-once retry attempt sequence differs")
    if (
        item["schema_version"] != CREATE_ONCE_BUDGET_SCHEMA
        or expected_uris != inventory["uris"]
        or item["expected_write_uri_manifest_sha256"]
        != inventory["uri_manifest_sha256"]
        or item["expected_write_uri_count"] != inventory["uri_count"]
        or item["max_write_operations"]
        != int(inventory["uri_count"]) * CREATE_ONCE_ATTEMPTS
        or type(item["max_invocation_write_bytes"]) is not int
        or not 1 <= int(item["max_invocation_write_bytes"])
        <= MAX_CREATE_ONCE_INVOCATION_BYTES
        or item["write_operations_reserved"] != len(charges)
        or item["write_bytes_reserved"]
        != sum(int(value["bytes"]) for value in charges)
        or int(item["write_bytes_reserved"])
        > int(item["max_invocation_write_bytes"])
        or item["write_charge_manifest_sha256"] != canonical_sha256(charges)
        or completed != sorted(completed)
        or pending != sorted(pending)
        or len(completed) != len(set(completed))
        or len(pending) != len(set(pending))
        or set(completed) & set(pending)
        or sorted(completed + pending) != expected_uris
        or any(uri not in attempts_by_uri for uri in completed)
        or any(uri in attempts_by_uri for uri in pending)
        or item["completed_write_uri_manifest_sha256"]
        != canonical_sha256(completed)
        or item["pending_write_uri_manifest_sha256"] != canonical_sha256(pending)
        or item["all_backend_writes_charged_before_call"] is not True
        or item["failed_attempts_remain_charged"] is not True
        or item["unexpected_uri_backend_call_possible"] is not False
        or item["per_invocation_only"] is not True
        or item["cross_process_durable_ledger"] is not False
    ):
        _fail("create-once budget receipt fixed law differs")
    normalized = dict(item)
    normalized["expected_write_uris"] = expected_uris
    normalized["completed_write_uris"] = completed
    normalized["pending_write_uris"] = pending
    normalized["write_charges"] = charges
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("create-once budget receipt canonical replay differs")
    return normalized


def _build_publication_work_receipt_v1(
    *,
    source_commit_sha: str,
    output_uri_inventory: Mapping[str, object],
    transport_budget_snapshot: Mapping[str, object],
) -> dict[str, object]:
    inventory = _normalize_output_uri_inventory_v1(output_uri_inventory)
    snapshot = _mapping(
        transport_budget_snapshot, label="transport budget snapshot"
    )
    pending = sorted([
        str(inventory["publication_work_receipt_uri"]),
        str(inventory["terminal_root_uri"]),
    ])
    completed = sorted(set(inventory["uris"]) - set(pending))
    body: dict[str, object] = {
        "schema_version": PUBLICATION_WORK_RECEIPT_SCHEMA,
        "source_commit_sha": source_commit_sha,
        "output_uri_inventory": inventory,
        "output_uri_inventory_sha256": inventory[
            "output_uri_inventory_sha256"
        ],
        "transport_budget_snapshot": snapshot,
        "transport_budget_snapshot_sha256": canonical_sha256(snapshot),
        "completed_preterminal_uris": completed,
        "completed_preterminal_uri_manifest_sha256": canonical_sha256(completed),
        "receipt_and_terminal_root_pending_at_snapshot": pending,
        "publication_work_receipt_uri": inventory[
            "publication_work_receipt_uri"
        ],
        "terminal_root_uri": inventory["terminal_root_uri"],
        "all_subordinate_outputs_complete_before_receipt": True,
        "all_backend_writes_precharged_before_call": True,
        "same_commit_recovery_required": True,
    }
    body["publication_work_receipt_sha256"] = canonical_sha256(body)
    return _normalize_publication_work_receipt_v1(
        body, output_uri_inventory=inventory
    )


def _trusted_capture_plan_lock_v1() -> tuple[
    dict[str, object], dict[str, object], dict[str, object], bytes
]:
    """Replay the tracked plan and every local predecessor from real Git.

    The returned final-lock bytes are derived from the plan-pinned Git blob;
    they are never accepted at the public publication boundary.
    """
    root = _trusted_repository_root_v1()
    head = _trusted_git_head_v1(root)
    path = capture_v2.CAPTURE_PLAN_LOCK_PATH
    current_raw = _secure_read_repository_file_v1(
        root, path, label="trusted capture-plan lock"
    )
    committed_raw = _trusted_git_blob_v1(root, head, path)
    if current_raw != committed_raw or _trusted_git_status_v1(root, [path]) != b"":
        _fail("trusted capture-plan lock differs from clean current HEAD")
    try:
        parsed = json.loads(current_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "trusted capture-plan lock is not canonical JSON"
        ) from exc
    if canonical_json_bytes(parsed) + b"\n" != current_raw:
        _fail("trusted capture-plan lock must be canonical JSON plus one newline")
    plan = capture_v2.validate_capture_plan_lock_v2(parsed)
    binding = {
        "commit_sha": head,
        "relative_path": path,
        "sha256": sha256(current_raw).hexdigest(),
        "bytes": len(current_raw),
        "capture_plan_sha256": plan["capture_plan_sha256"],
    }
    _validate_capture_plan_binding(
        plan=plan,
        capture_plan_binding=binding,
        repository_root=root,
        git_head=_trusted_git_head_v1,
        git_blob=_trusted_git_blob_v1,
        git_status=_trusted_git_status_v1,
    )
    replayed_paths: list[dict[str, object]] = []

    def replay(
        *, commit_sha: str, relative_path: str, expected_sha: str,
        expected_bytes: int, label: str,
    ) -> bytes:
        git_raw = _trusted_git_blob_v1(root, commit_sha, relative_path)
        current = _secure_read_repository_file_v1(root, relative_path, label=label)
        if (
            git_raw != current
            or len(git_raw) != expected_bytes
            or sha256(git_raw).hexdigest() != expected_sha
            or _trusted_git_status_v1(root, [relative_path]) != b""
        ):
            _fail(f"{label} Git/current predecessor replay differs")
        replayed_paths.append({
            "commit_sha": commit_sha,
            "relative_path": relative_path,
            "sha256": expected_sha,
            "bytes": expected_bytes,
        })
        return git_raw

    implementation_commit = str(plan["implementation_commit_sha"])
    for ordinal, measurement_value in enumerate(plan["implementation_measurements"]):
        measurement = _mapping(
            measurement_value, label=f"capture-plan implementation[{ordinal}]"
        )
        replay(
            commit_sha=implementation_commit,
            relative_path=str(measurement["relative_path"]),
            expected_sha=str(measurement["sha256"]),
            expected_bytes=int(measurement["bytes"]),
            label=f"capture-plan implementation[{ordinal}]",
        )
    final_binding = _mapping(
        plan["adapter_final_release_lock_binding"],
        label="adapter final release lock binding",
    )
    final_raw = replay(
        commit_sha=str(final_binding["commit_sha"]),
        relative_path=str(final_binding["relative_path"]),
        expected_sha=str(final_binding["sha256"]),
        expected_bytes=int(final_binding["bytes"]),
        label="adapter final release lock",
    )
    try:
        final_lock = capture_v1._validate_adapter_final_release_lock_raw(final_raw)
    except capture_v1.CorpusR6MatchupCapturePlanV1Error as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(str(exc)) from exc
    if final_lock["final_release_lock_sha256"] != final_binding["internal_sha256"]:
        _fail("adapter final release lock internal predecessor differs")
    fixed = _mapping(
        plan["fixed_g0_authority_binding"], label="fixed G0 authority binding"
    )
    g0_raw = replay(
        commit_sha=str(fixed["evidence_source_commit_sha"]),
        relative_path=str(fixed["g0_lock_relative_path"]),
        expected_sha=str(fixed["g0_lock_file_sha256"]),
        expected_bytes=int(fixed["g0_lock_file_bytes"]),
        label="accepted G0 lock",
    )
    try:
        g0 = json.loads(g0_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "accepted G0 lock is not canonical JSON"
        ) from exc
    if (
        canonical_json_bytes(g0) + b"\n" != g0_raw
        or g0.get("g0_authority_lock_sha256") != fixed["g0_lock_internal_sha256"]
    ):
        _fail("accepted G0 lock internal predecessor differs")
    if _trusted_git_head_v1(root) != head:
        _fail("trusted Git HEAD changed during predecessor replay")
    replay_body: dict[str, object] = {
        "schema_version": CAPTURE_PLAN_GIT_REPLAY_SCHEMA,
        "capture_plan_binding": binding,
        "adapter_final_release_lock_binding": dict(final_binding),
        "fixed_g0_lock_binding": {
            "commit_sha": fixed["evidence_source_commit_sha"],
            "relative_path": fixed["g0_lock_relative_path"],
            "sha256": fixed["g0_lock_file_sha256"],
            "bytes": fixed["g0_lock_file_bytes"],
            "internal_sha256": fixed["g0_lock_internal_sha256"],
        },
        "replayed_paths": replayed_paths,
        "replayed_path_manifest_sha256": canonical_sha256(replayed_paths),
        "caller_supplied_final_lock_bytes_allowed": False,
        "all_predecessor_git_blobs_equal_current_nofollow_bytes": True,
        "same_commit_recovery_required": True,
        "recovery_source_commit_sha": head,
    }
    replay_body["capture_plan_git_replay_sha256"] = canonical_sha256(replay_body)
    return plan, binding, replay_body, final_raw


def _trusted_remote_prerequisites_v1(
    *, plan: Mapping[str, object], read_exact: ReadExact
) -> dict[str, object]:
    """Generation-exact open every caller-free remote prerequisite."""
    fixed_receipt, fixed_receipt_identity = _parse_exact_json(
        plan["fixed_g0_replay_receipt_identity"],
        read_exact=read_exact,
        label="fixed-G0 replay receipt prerequisite",
    )
    catalog_release, catalog_release_identity = _parse_exact_json(
        plan["catalog_release_identity"],
        read_exact=read_exact,
        label="catalog release prerequisite",
    )
    upstream_release, upstream_release_identity = _parse_exact_json(
        plan["upstream_source_release_identity"],
        read_exact=read_exact,
        label="upstream source release prerequisite",
    )
    structural_catalogs: list[dict[str, object]] = []
    for ordinal, task_value in enumerate(plan["source_task_bindings"]):
        task = _mapping(task_value, label=f"capture-plan task[{ordinal}]")
        body, identity = _parse_exact_json(
            task["catalog_identity"],
            read_exact=read_exact,
            label=f"structural catalog prerequisite[{ordinal}]",
        )
        if identity != task["catalog_identity"]:
            _fail("structural catalog prerequisite identity differs")
        structural_catalogs.append(body)
    upstream_pack_row_objects: list[dict[str, object]] = []
    for ordinal, pack_value in enumerate(plan["upstream_pack_bindings"]):
        pack = _mapping(pack_value, label=f"upstream pack[{ordinal}]")
        body, identity = _parse_exact_json(
            pack["exact_rows_identity"],
            read_exact=read_exact,
            label=f"upstream exact rows prerequisite[{ordinal}]",
        )
        if identity != pack["exact_rows_identity"]:
            _fail("upstream exact rows prerequisite identity differs")
        upstream_pack_row_objects.append(body)
    return {
        "fixed_g0_replay_receipt": fixed_receipt,
        "fixed_g0_replay_receipt_identity": fixed_receipt_identity,
        "catalog_release": catalog_release,
        "catalog_release_identity": catalog_release_identity,
        "structural_catalogs": structural_catalogs,
        "upstream_source_release": upstream_release,
        "upstream_source_release_identity": upstream_release_identity,
        "upstream_pack_row_objects": upstream_pack_row_objects,
        "all_remote_prerequisites_generation_exact_reopened": True,
    }


def _normalize_capture_plan_git_replay_v1(
    value: object, *, plan: Mapping[str, object] | None,
    capture_plan_binding: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="capture-plan Git replay")
    expected_fields = {
        "schema_version", "capture_plan_binding",
        "adapter_final_release_lock_binding", "fixed_g0_lock_binding",
        "replayed_paths", "replayed_path_manifest_sha256",
        "caller_supplied_final_lock_bytes_allowed",
        "all_predecessor_git_blobs_equal_current_nofollow_bytes",
        "same_commit_recovery_required", "recovery_source_commit_sha",
        "capture_plan_git_replay_sha256",
    }
    if set(item) != expected_fields:
        _fail("capture-plan Git replay fields differ")
    retained = _digest(
        item["capture_plan_git_replay_sha256"],
        label="capture-plan Git replay hash",
    )
    unhashed = dict(item)
    del unhashed["capture_plan_git_replay_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("capture-plan Git replay self-hash differs")
    paths = _sequence(item["replayed_paths"], label="replayed predecessor paths")
    normalized_paths: list[dict[str, object]] = []
    for ordinal, path_value in enumerate(paths):
        path = _mapping(path_value, label=f"replayed path[{ordinal}]")
        if set(path) != {"commit_sha", "relative_path", "sha256", "bytes"}:
            _fail("replayed predecessor path fields differ")
        if (
            type(path["commit_sha"]) is not str
            or _COMMIT.fullmatch(str(path["commit_sha"])) is None
            or type(path["relative_path"]) is not str
            or type(path["bytes"]) is not int
            or int(path["bytes"]) < 1
        ):
            _fail("replayed predecessor path binding differs")
        _digest(path["sha256"], label="replayed predecessor SHA")
        normalized_paths.append(path)
    final_binding = _mapping(
        item["adapter_final_release_lock_binding"],
        label="replayed adapter final lock",
    )
    fixed_binding = _mapping(
        item["fixed_g0_lock_binding"], label="replayed fixed G0 lock"
    )
    for binding_value, label in (
        (final_binding, "adapter final release lock binding"),
        (fixed_binding, "fixed G0 lock binding"),
    ):
        if set(binding_value) != {
            "commit_sha", "relative_path", "sha256", "bytes", "internal_sha256"
        }:
            _fail(f"{label} fields differ")
        if (
            type(binding_value["commit_sha"]) is not str
            or _COMMIT.fullmatch(str(binding_value["commit_sha"])) is None
            or type(binding_value["relative_path"]) is not str
            or type(binding_value["bytes"]) is not int
            or int(binding_value["bytes"]) < 1
        ):
            _fail(f"{label} differs")
        _digest(binding_value["sha256"], label=f"{label} SHA")
        _digest(binding_value["internal_sha256"], label=f"{label} internal SHA")
    plan_fixed = (
        _mapping(
            plan["fixed_g0_authority_binding"], label="plan fixed G0 binding"
        )
        if plan is not None
        else None
    )
    expected_paths = None
    if plan is not None and plan_fixed is not None:
        expected_paths = [
            {
                "commit_sha": plan["implementation_commit_sha"],
                "relative_path": measurement["relative_path"],
                "sha256": measurement["sha256"],
                "bytes": measurement["bytes"],
            }
            for measurement in plan["implementation_measurements"]
        ]
        expected_paths.extend([
            {
                "commit_sha": final_binding["commit_sha"],
                "relative_path": final_binding["relative_path"],
                "sha256": final_binding["sha256"],
                "bytes": final_binding["bytes"],
            },
            {
                "commit_sha": plan_fixed["evidence_source_commit_sha"],
                "relative_path": plan_fixed["g0_lock_relative_path"],
                "sha256": plan_fixed["g0_lock_file_sha256"],
                "bytes": plan_fixed["g0_lock_file_bytes"],
            },
        ])
    if (
        item["schema_version"] != CAPTURE_PLAN_GIT_REPLAY_SCHEMA
        or item["capture_plan_binding"] != capture_plan_binding
        or (
            plan is not None
            and final_binding != plan["adapter_final_release_lock_binding"]
        )
        or (
            plan_fixed is not None
            and fixed_binding != {
                "commit_sha": plan_fixed["evidence_source_commit_sha"],
                "relative_path": plan_fixed["g0_lock_relative_path"],
                "sha256": plan_fixed["g0_lock_file_sha256"],
                "bytes": plan_fixed["g0_lock_file_bytes"],
                "internal_sha256": plan_fixed["g0_lock_internal_sha256"],
            }
        )
        or item["replayed_path_manifest_sha256"]
        != canonical_sha256(normalized_paths)
        or (expected_paths is not None and normalized_paths != expected_paths)
        or item["caller_supplied_final_lock_bytes_allowed"] is not False
        or item["all_predecessor_git_blobs_equal_current_nofollow_bytes"]
        is not True
        or item["same_commit_recovery_required"] is not True
        or item["recovery_source_commit_sha"]
        != capture_plan_binding["commit_sha"]
    ):
        _fail("capture-plan Git replay fixed law differs")
    normalized = dict(item)
    normalized["replayed_paths"] = normalized_paths
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("capture-plan Git replay canonical replay differs")
    return normalized


@dataclass
class ExactReadCacheV1:
    """Identity-conflict-detecting, bounded invocation-local byte cache."""

    reader: ReadExact
    max_cached_bytes: int = MAX_EXACT_READ_CACHE_BYTES
    max_object_bytes: int = MAX_EXACT_OBJECT_BYTES
    max_invocation_read_bytes: int = MAX_EXACT_READ_INVOCATION_BYTES
    max_read_operations: int = MAX_EXACT_READ_OPERATIONS

    def __post_init__(self) -> None:
        if not callable(self.reader):
            _fail("exact-read cache requires a reader")
        if (
            type(self.max_cached_bytes) is not int
            or not 1 <= self.max_cached_bytes <= MAX_EXACT_READ_CACHE_BYTES
        ):
            _fail("exact-read cache byte bound must be a positive integer")
        for value, ceiling, label in (
            (self.max_object_bytes, MAX_EXACT_OBJECT_BYTES, "object byte"),
            (
                self.max_invocation_read_bytes,
                MAX_EXACT_READ_INVOCATION_BYTES,
                "invocation byte",
            ),
            (self.max_read_operations, MAX_EXACT_READ_OPERATIONS, "operation"),
        ):
            if type(value) is not int or not 1 <= value <= ceiling:
                _fail(f"exact-read cache {label} bound differs")
        if self.max_object_bytes > self.max_invocation_read_bytes:
            _fail("exact-read cache object bound exceeds invocation byte bound")
        self._identities: dict[tuple[str, str], dict[str, object]] = {}
        self._objects: OrderedDict[tuple[str, str], bytes] = OrderedDict()
        self._lock = Lock()
        self._read_charges: list[dict[str, object]] = []
        self.read_bytes_reserved = 0
        self.read_operations_reserved = 0
        self.cached_bytes = 0
        self.hit_count = 0
        self.miss_count = 0
        self.eviction_count = 0
        self.oversize_bypass_count = 0

    def read(self, identity_value: Mapping[str, object]) -> bytes:
        identity = _identity(identity_value, label="cached exact object")
        key = (str(identity["uri"]), str(identity["generation"]))
        byte_count = int(identity["bytes"])
        if byte_count > self.max_object_bytes:
            _fail("exact-read cache object exceeds its fixed byte bound")
        with self._lock:
            previous_identity = self._identities.get(key)
            if previous_identity is not None and previous_identity != identity:
                _fail("same URI/generation was requested with different identity")
            raw = self._objects.get(key)
            if raw is not None:
                self._objects.move_to_end(key)
                self.hit_count += 1
                return raw
            next_operations = self.read_operations_reserved + 1
            next_bytes = self.read_bytes_reserved + byte_count
            if (
                next_operations > self.max_read_operations
                or next_bytes > self.max_invocation_read_bytes
            ):
                _fail("exact-read cache cumulative invocation budget exhausted")
            charge: dict[str, object] = {
                "ordinal": self.read_operations_reserved,
                "uri": identity["uri"],
                "generation": identity["generation"],
                "bytes": byte_count,
                "purpose": "cache-miss-exact-read",
                "charged_before_payload_access": True,
                "failed_reads_remain_charged": True,
            }
            charge["read_charge_sha256"] = canonical_sha256(charge)
            self._identities[key] = identity
            self.read_operations_reserved = next_operations
            self.read_bytes_reserved = next_bytes
            self._read_charges.append(charge)
            self.miss_count += 1
            try:
                raw = self.reader(identity)
            except Exception as exc:
                raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
                    "exact object read failed"
                ) from exc
            if (
                type(raw) is not bytes
                or len(raw) != identity["bytes"]
                or sha256(raw).hexdigest() != identity["sha256"]
            ):
                _fail("exact object content identity differs")
            if len(raw) <= self.max_cached_bytes:
                while (
                    self._objects
                    and self.cached_bytes + len(raw) > self.max_cached_bytes
                ):
                    _, evicted = self._objects.popitem(last=False)
                    self.cached_bytes -= len(evicted)
                    self.eviction_count += 1
                self._objects[key] = raw
                self.cached_bytes += len(raw)
            else:
                self.oversize_bypass_count += 1
            return raw

    @property
    def unique_object_count(self) -> int:
        return len(self._identities)

    def budget_receipt(self) -> dict[str, object]:
        with self._lock:
            body: dict[str, object] = {
                "schema_version": EXACT_READ_BUDGET_SCHEMA,
                "ledger_kind": "exact-read-cache",
                "max_object_bytes": self.max_object_bytes,
                "max_invocation_read_bytes": self.max_invocation_read_bytes,
                "max_read_operations": self.max_read_operations,
                "read_bytes_reserved": self.read_bytes_reserved,
                "read_operations_reserved": self.read_operations_reserved,
                "read_charges": [dict(value) for value in self._read_charges],
                "read_charge_manifest_sha256": canonical_sha256(
                    self._read_charges
                ),
                "all_payload_reads_charged_before_access": True,
                "failed_reads_remain_charged": True,
                "per_invocation_only": True,
                "cross_process_durable_ledger": False,
            }
        body["exact_read_budget_sha256"] = canonical_sha256(body)
        return body


def _parse_exact_json(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"{label} exact reopen failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    try:
        body = _mapping(json.loads(raw.decode("utf-8")), label=label)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"{label} must be canonical JSON"
        ) from exc
    if canonical_json_bytes(body) != raw:
        _fail(f"{label} canonical bytes differ")
    return body, identity


def _publish_json(
    body: Mapping[str, object],
    *,
    uri: str,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    raw = canonical_json_bytes(body)
    try:
        identity = _identity(
            publish_create_once(uri, raw), label=f"published {label}"
        )
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"{label} create-once publication failed"
        ) from exc
    if identity["uri"] != uri:
        _fail(f"published {label} URI differs")
    reopened, reopened_identity = _parse_exact_json(
        identity, read_exact=read_exact, label=f"published {label}"
    )
    if canonical_json_bytes(reopened) != raw:
        _fail(f"published {label} exact reopen differs")
    return reopened, reopened_identity


def _validate_capture_plan_binding(
    *,
    plan: Mapping[str, object],
    capture_plan_binding: Mapping[str, object],
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    try:
        binding = release_v1._capture_plan_binding(capture_plan_binding)
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(str(exc)) from exc
    if binding["relative_path"] != capture_v2.CAPTURE_PLAN_LOCK_PATH:
        _fail("capture-plan binding path differs from candidate-authority lock")
    try:
        head = git_head(repository_root)
        raw = git_blob(
            repository_root, binding["commit_sha"], binding["relative_path"]
        )
        current_raw = _secure_read_repository_file_v1(
            repository_root,
            binding["relative_path"],
            label="capture-plan current file",
        )
        status = git_status(repository_root, [binding["relative_path"]])
        final_head = git_head(repository_root)
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "capture-plan Git replay failed"
        ) from exc
    expected_raw = canonical_json_bytes(plan) + b"\n"
    if (
        head != binding["commit_sha"]
        or final_head != head
        or type(raw) is not bytes
        or raw != expected_raw
        or current_raw != raw
        or len(raw) != binding["bytes"]
        or sha256(raw).hexdigest() != binding["sha256"]
        or binding["capture_plan_sha256"] != plan["capture_plan_sha256"]
        or status != b""
    ):
        _fail("capture-plan Git/current exact-byte binding differs")
    return binding


def _validate_code_identity(
    identity_value: Mapping[str, object],
    *,
    expected_path: str,
    repair_sha256: object | None,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> tuple[dict[str, str], dict[str, object]]:
    try:
        primary = source.normalize_code_identity_v2(
            identity_value, expected_module_path=expected_path,
            label=f"{expected_path} code identity",
        )
        head = git_head(repository_root)
        primary_raw = git_blob(
            repository_root, primary["source_commit_sha"], expected_path
        )
        head_raw = git_blob(repository_root, head, expected_path)
        current_raw = _secure_read_repository_file_v1(
            repository_root, expected_path, label=f"{expected_path} current code"
        )
        status = git_status(repository_root, [expected_path])
        final_head = git_head(repository_root)
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"{expected_path} Git code replay failed"
        ) from exc
    if (
        type(head) is not str
        or _COMMIT.fullmatch(head) is None
        or final_head != head
        or type(primary_raw) is not bytes
        or not primary_raw
        or sha256(primary_raw).hexdigest() != primary["module_sha256"]
        or type(head_raw) is not bytes
        or current_raw != head_raw
        or type(current_raw) is not bytes
        or not current_raw
        or status != b""
    ):
        _fail(f"{expected_path} primary/current code binding differs")
    current_sha = sha256(current_raw).hexdigest()
    repair = None
    if current_sha != primary["module_sha256"]:
        repair = _digest(repair_sha256, label=f"{expected_path} repair SHA")
        if repair != current_sha:
            _fail(f"{expected_path} repair SHA differs from current Git blob")
    elif repair_sha256 is not None:
        _fail(f"{expected_path} repair SHA is unnecessary")
    effective = {
        "source_commit_sha": head,
        "module_path": expected_path,
        "module_sha256": current_sha,
    }
    binding = {
        "primary_code_identity": primary,
        "repair_sha256": repair,
        "effective_code_identity": effective,
    }
    return effective, binding


def _normalize_code_binding(
    value: object, *, expected_path: str, label: str,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {
        "primary_code_identity", "repair_sha256", "effective_code_identity"
    }:
        _fail(f"{label} fields differ")
    try:
        primary = source.normalize_code_identity_v2(
            item["primary_code_identity"],
            expected_module_path=expected_path,
            label=f"{label} primary",
        )
        effective = source.normalize_code_identity_v2(
            item["effective_code_identity"],
            expected_module_path=expected_path,
            label=f"{label} effective",
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(str(exc)) from exc
    repair = item["repair_sha256"]
    if repair is None:
        if effective != primary:
            _fail(f"{label} changes code without a repair SHA")
    else:
        retained_repair = _digest(repair, label=f"{label} repair SHA")
        if (
            effective["module_sha256"] != retained_repair
            or effective["module_sha256"] == primary["module_sha256"]
        ):
            _fail(f"{label} repair binding differs")
        repair = retained_repair
    normalized = {
        "primary_code_identity": primary,
        "repair_sha256": repair,
        "effective_code_identity": effective,
    }
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail(f"{label} canonical replay differs")
    return normalized


def _derive_clean_head_code_identity_v1(
    *,
    expected_path: str,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, str]:
    """Derive, rather than accept, one clean current code identity."""
    try:
        head = git_head(repository_root)
        raw = git_blob(repository_root, head, expected_path)
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"{expected_path} clean code identity derivation failed"
        ) from exc
    identity = {
        "source_commit_sha": head,
        "module_path": expected_path,
        "module_sha256": sha256(raw).hexdigest(),
    }
    effective, binding = _validate_code_identity(
        identity,
        expected_path=expected_path,
        repair_sha256=None,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if binding["primary_code_identity"] != effective:
        _fail(f"{expected_path} clean code identity unexpectedly needs repair")
    return effective


def _normalize_dependency_closure(value: object) -> dict[str, object]:
    item = _mapping(value, label="executed dependency closure")
    expected_fields = {
        "schema_version",
        "source_commit_sha",
        "module_paths",
        "module_code_identities",
        "module_code_identity_manifest_sha256",
        "all_head_blobs_match_current_bytes",
        "all_scoped_paths_clean",
        "dependency_closure_sha256",
    }
    if set(item) != expected_fields:
        _fail("executed dependency closure fields differ")
    retained = _digest(
        item["dependency_closure_sha256"], label="dependency closure hash"
    )
    unhashed = dict(item)
    del unhashed["dependency_closure_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("executed dependency closure self-hash differs")
    commit = item["source_commit_sha"]
    if type(commit) is not str or _COMMIT.fullmatch(commit) is None:
        _fail("dependency closure commit must be lowercase 40-hex")
    paths = _sequence(item["module_paths"], label="dependency module paths")
    if (
        any(type(path) is not str for path in paths)
        or paths != list(EXECUTED_DEPENDENCY_MODULE_PATHS)
        or len(paths) != len(set(paths))
        or paths != sorted(paths)
    ):
        _fail("executed dependency module path closure differs")
    raw_identities = _sequence(
        item["module_code_identities"], label="dependency code identities"
    )
    if len(raw_identities) != len(paths):
        _fail("executed dependency identity count differs")
    identities: list[dict[str, str]] = []
    for path, identity_value in zip(paths, raw_identities, strict=True):
        try:
            identity = source.normalize_code_identity_v2(
                identity_value,
                expected_module_path=path,
                label=f"dependency code identity {path}",
            )
        except source.CorpusR6MatchupSourceV2Error as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(str(exc)) from exc
        if identity["source_commit_sha"] != commit:
            _fail("dependency code identity commit differs from closure")
        identities.append(identity)
    normalized = dict(item)
    normalized["module_paths"] = paths
    normalized["module_code_identities"] = identities
    if (
        item["schema_version"] != DEPENDENCY_CLOSURE_SCHEMA
        or item["module_code_identity_manifest_sha256"]
        != canonical_sha256(identities)
        or item["all_head_blobs_match_current_bytes"] is not True
        or item["all_scoped_paths_clean"] is not True
        or canonical_json_bytes(normalized) != canonical_json_bytes(item)
    ):
        _fail("executed dependency closure fixed law differs")
    return normalized


def _replay_executed_dependency_closure(
    *,
    expected_commit_sha: object,
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Bind every local Python dependency to clean current HEAD bytes."""
    expected_commit = str(expected_commit_sha)
    if _COMMIT.fullmatch(expected_commit) is None:
        _fail("dependency closure expected commit must be lowercase 40-hex")
    if (
        tuple(sorted(EXECUTED_DEPENDENCY_MODULE_PATHS))
        != EXECUTED_DEPENDENCY_MODULE_PATHS
        or len(EXECUTED_DEPENDENCY_MODULE_PATHS)
        != len(set(EXECUTED_DEPENDENCY_MODULE_PATHS))
    ):
        _fail("fixed executed dependency path closure is not canonical")
    try:
        head = git_head(repository_root)
        status = git_status(
            repository_root, list(EXECUTED_DEPENDENCY_MODULE_PATHS)
        )
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "executed dependency Git status replay failed"
        ) from exc
    if head != expected_commit or status != b"":
        _fail("executed dependency closure is not clean at the fixed Git HEAD")
    identities: list[dict[str, str]] = []
    for path in EXECUTED_DEPENDENCY_MODULE_PATHS:
        try:
            head_raw = git_blob(repository_root, expected_commit, path)
            current_raw = _secure_read_repository_file_v1(
                repository_root, path, label=f"executed dependency {path}"
            )
        except Exception as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
                f"executed dependency byte replay failed for {path}"
            ) from exc
        if (
            type(head_raw) is not bytes
            or not head_raw
            or type(current_raw) is not bytes
            or current_raw != head_raw
        ):
            _fail(f"executed dependency current bytes differ for {path}")
        identities.append({
            "source_commit_sha": expected_commit,
            "module_path": path,
            "module_sha256": sha256(head_raw).hexdigest(),
        })
    try:
        final_head = git_head(repository_root)
        final_status = git_status(
            repository_root, list(EXECUTED_DEPENDENCY_MODULE_PATHS)
        )
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "executed dependency final Git replay failed"
        ) from exc
    if final_head != expected_commit or final_status != b"":
        _fail("executed dependency closure changed during byte replay")
    body: dict[str, object] = {
        "schema_version": DEPENDENCY_CLOSURE_SCHEMA,
        "source_commit_sha": expected_commit,
        "module_paths": list(EXECUTED_DEPENDENCY_MODULE_PATHS),
        "module_code_identities": identities,
        "module_code_identity_manifest_sha256": canonical_sha256(identities),
        "all_head_blobs_match_current_bytes": True,
        "all_scoped_paths_clean": True,
    }
    body["dependency_closure_sha256"] = canonical_sha256(body)
    return _normalize_dependency_closure(body)


def _module_name_for_path_v1(path: str) -> str:
    if not path.startswith("src/") or not path.endswith(".py"):
        _fail("runtime module path is not one src Python module")
    return path[4:-3].replace("/", ".")


def _critical_loaded_callables_v1() -> tuple[tuple[object, str, str], ...]:
    return (
        (sys.modules[__name__], (
            "_publish_matchup_source_batch_candidate_authority_with_adapters_v1"
        ), BATCH_MODULE_PATH),
        (sys.modules[__name__], "_publish_component_with_cached_authority", (
            BATCH_MODULE_PATH
        )),
        (sys.modules[__name__], (
            "_publish_terminal_source_release_with_cached_authority"
        ), BATCH_MODULE_PATH),
        (sys.modules[__name__], "_build_batch_root", BATCH_MODULE_PATH),
        (sys.modules[__name__], "_publish_json", BATCH_MODULE_PATH),
        (
            sys.modules[__name__],
            "validate_batch_release_structure_v1",
            BATCH_MODULE_PATH,
        ),
        (
            candidate_authority,
            "reopen_fixed_g0_candidate_authority_release_v1",
            "src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_release_v1.py",
        ),
        *(
            (
                capture_v2,
                attribute,
                "src/nfl_dfs/research/"
                "corpus_r6_matchup_capture_plan_candidate_authority_v2.py",
            )
            for attribute in (
                "_authority_binding",
                "_base_projection",
                "_upgrade",
                "validate_capture_plan_lock_v2",
            )
        ),
        *(
            (
                capture_v1,
                attribute,
                "src/nfl_dfs/research/corpus_r6_matchup_capture_plan_v1.py",
            )
            for attribute in (
                "_pack_bindings",
                "_validate_adapter_final_release_lock_raw",
                "_validate_upstream_release",
                "validate_capture_plan_against_prerequisites_v1",
            )
        ),
        (component_v1, "publish_all_54_component_release_v1", (
            "src/nfl_dfs/research/corpus_r6_matchup_component_publication_v1.py"
        )),
        *(
            (
                component_v2,
                attribute,
                "src/nfl_dfs/research/"
                "corpus_r6_matchup_component_publication_candidate_authority_v2.py",
            )
            for attribute in (
                "_build_receipt",
                "_candidate_binding",
                "_durable_validate_full_result",
                "_validate_publication_result",
                "validate_component_publication_candidate_authority_receipt_v2",
            )
        ),
        (operator_v2, "publish_matchup_source_triple_v2", (
            "src/nfl_dfs/research/corpus_r6_matchup_source_operator_v2.py"
        )),
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
                "build_matchup_capture_receipt_v2",
                "build_matchup_operator_result_v2",
                "build_matchup_source_export_v2",
                "build_matchup_source_release_v1",
            )
        ),
        *(
            (
                release_v2,
                attribute,
                "src/nfl_dfs/research/"
                "corpus_r6_matchup_source_release_candidate_authority_v2.py",
            )
            for attribute in (
                "_build_release_v2",
                "_candidate_authority_binding",
                "_project_release_v1",
                "_selected_candidate_binding",
                "validate_matchup_source_release_candidate_authority_v2",
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
            )
        ),
        *(
            (
                catalog_v1,
                attribute,
                "src/nfl_dfs/research/corpus_r6_player_catalog_v1.py",
            )
            for attribute in (
                "expected_slate_for_source_task",
                "task_id_for_source_task",
            )
        ),
    )


def _code_constant_fingerprint_v1(value: object) -> object:
    if isinstance(value, CodeType):
        return {"code": _code_object_fingerprint_v1(value)}
    if isinstance(value, tuple):
        return {"tuple": [_code_constant_fingerprint_v1(row) for row in value]}
    if isinstance(value, frozenset):
        rows = [_code_constant_fingerprint_v1(row) for row in value]
        return {"frozenset": sorted(rows, key=canonical_json_bytes)}
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, slice):
        return {
            "slice": [
                _code_constant_fingerprint_v1(value.start),
                _code_constant_fingerprint_v1(value.stop),
                _code_constant_fingerprint_v1(value.step),
            ]
        }
    if value is None or value is Ellipsis or isinstance(
        value, (bool, int, float, complex, str)
    ):
        return {"type": type(value).__name__, "repr": repr(value)}
    _fail("loaded callable contains an unsupported code constant")


def _code_object_fingerprint_v1(code: CodeType) -> dict[str, object]:
    return {
        "argcount": code.co_argcount,
        "posonlyargcount": code.co_posonlyargcount,
        "kwonlyargcount": code.co_kwonlyargcount,
        "nlocals": code.co_nlocals,
        "stacksize": code.co_stacksize,
        "flags": code.co_flags,
        "code_hex": code.co_code.hex(),
        "constants": [
            _code_constant_fingerprint_v1(value) for value in code.co_consts
        ],
        "names": list(code.co_names),
        "varnames": list(code.co_varnames),
        "filename": code.co_filename,
        "name": code.co_name,
        "qualname": code.co_qualname,
        "firstlineno": code.co_firstlineno,
        "linetable_hex": code.co_linetable.hex(),
        "exceptiontable_hex": code.co_exceptiontable.hex(),
        "freevars": list(code.co_freevars),
        "cellvars": list(code.co_cellvars),
    }


def _compiled_callable_code_sha256_v1(
    *, expected_path: str, expected_qualname: str
) -> str:
    expected_filename = str((REPOSITORY_ROOT / expected_path).resolve(strict=True))
    raw = _secure_read_repository_file_v1(
        REPOSITORY_ROOT,
        expected_path,
        label=f"compiled loaded callable {expected_qualname}",
    )
    try:
        module_code = compile(
            raw,
            expected_filename,
            "exec",
            dont_inherit=True,
            optimize=sys.flags.optimize,
        )
    except (SyntaxError, ValueError, TypeError) as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"measured source cannot compile for {expected_qualname}"
        ) from exc
    matches: list[CodeType] = []
    pending = [module_code]
    while pending:
        code = pending.pop()
        if code.co_qualname == expected_qualname:
            matches.append(code)
        pending.extend(
            value for value in code.co_consts if isinstance(value, CodeType)
        )
    if len(matches) != 1:
        _fail(f"measured source callable is not unique for {expected_qualname}")
    return canonical_sha256(_code_object_fingerprint_v1(matches[0]))


def _normalize_runtime_attestation_v1(
    value: object, *, dependency_closure: Mapping[str, object]
) -> dict[str, object]:
    item = _mapping(value, label="loaded runtime attestation")
    expected_fields = {
        "schema_version", "source_commit_sha", "python_implementation",
        "python_version", "python_executable", "image_reference",
        "image_digest", "image_source_commit_sha", "loaded_modules",
        "loaded_module_manifest_sha256", "critical_callables",
        "critical_callable_manifest_sha256", "all_module_origins_canonical",
        "all_loaded_sources_match_dependency_closure",
        "all_critical_callables_bound_to_measured_modules",
        "immutable_image_identity_environment_required",
        "runtime_attestation_sha256",
    }
    if set(item) != expected_fields:
        _fail("loaded runtime attestation fields differ")
    retained = _digest(
        item["runtime_attestation_sha256"], label="runtime attestation hash"
    )
    unhashed = dict(item)
    del unhashed["runtime_attestation_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("loaded runtime attestation self-hash differs")
    closure = _normalize_dependency_closure(dependency_closure)
    commit = str(closure["source_commit_sha"])
    modules_raw = _sequence(item["loaded_modules"], label="loaded modules")
    modules: list[dict[str, object]] = []
    closure_by_path = {
        str(value["module_path"]): value
        for value in closure["module_code_identities"]
    }
    for ordinal, value in enumerate(modules_raw):
        module = _mapping(value, label=f"loaded module[{ordinal}]")
        if set(module) != {
            "module_name", "module_path", "module_origin",
            "source_commit_sha", "module_sha256",
        }:
            _fail("loaded module attestation fields differ")
        path = str(module["module_path"])
        expected = closure_by_path.get(path)
        origin = str(module["module_origin"])
        origin_path = Path(origin)
        if (
            expected is None
            or module["module_name"] != _module_name_for_path_v1(path)
            or not origin_path.is_absolute()
            or origin_path.as_posix() != origin
            or not origin.endswith(f"/{path}")
            or module["source_commit_sha"] != commit
            or module["module_sha256"] != expected["module_sha256"]
        ):
            _fail("loaded module differs from measured dependency closure")
        modules.append(module)
    callables_raw = _sequence(
        item["critical_callables"], label="critical loaded callables"
    )
    callables: list[dict[str, object]] = []
    for ordinal, value in enumerate(callables_raw):
        callable_item = _mapping(value, label=f"critical callable[{ordinal}]")
        if set(callable_item) != {
            "module_name", "attribute", "qualname", "code_filename",
            "code_sha256", "committed_source_code_sha256",
            "loaded_code_matches_committed_source",
        }:
            _fail("critical callable attestation fields differ")
        if (
            type(callable_item["module_name"]) is not str
            or type(callable_item["attribute"]) is not str
            or type(callable_item["qualname"]) is not str
            or type(callable_item["code_filename"]) is not str
        ):
            _fail("critical callable attestation text differs")
        _digest(callable_item["code_sha256"], label="critical callable code SHA")
        _digest(
            callable_item["committed_source_code_sha256"],
            label="committed critical callable code SHA",
        )
        if (
            callable_item["code_sha256"]
            != callable_item["committed_source_code_sha256"]
            or callable_item["loaded_code_matches_committed_source"] is not True
        ):
            _fail("critical callable differs from committed measured source")
        callables.append(callable_item)
    module_origin_by_path = {
        str(value["module_path"]): str(value["module_origin"])
        for value in modules
    }
    expected_callable_origins = {
        (_module_name_for_path_v1(path), attribute): module_origin_by_path[path]
        for _module, attribute, path in _critical_loaded_callables_v1()
    }
    image_digest = str(item["image_digest"])
    if (
        not image_digest.startswith("sha256:")
        or _SHA256.fullmatch(image_digest[7:]) is None
        or type(item["image_reference"]) is not str
        or not str(item["image_reference"]).endswith(f"@{image_digest}")
        or item["image_source_commit_sha"] != commit
        or item["source_commit_sha"] != commit
        or modules != sorted(modules, key=lambda value: str(value["module_path"]))
        or len(modules) != len(EXECUTED_DEPENDENCY_MODULE_PATHS)
        or item["loaded_module_manifest_sha256"] != canonical_sha256(modules)
        or callables
        != sorted(
            callables,
            key=lambda value: (str(value["module_name"]), str(value["attribute"])),
        )
        or item["critical_callable_manifest_sha256"]
        != canonical_sha256(callables)
        or {
            (str(value["module_name"]), str(value["attribute"]))
            for value in callables
        } != set(expected_callable_origins)
        or any(
            value["code_filename"]
            != expected_callable_origins[(
                str(value["module_name"]), str(value["attribute"])
            )]
            for value in callables
        )
        or any(
            item[field] is not True
            for field in (
                "all_module_origins_canonical",
                "all_loaded_sources_match_dependency_closure",
                "all_critical_callables_bound_to_measured_modules",
                "immutable_image_identity_environment_required",
            )
        )
    ):
        _fail("loaded runtime attestation fixed law differs")
    normalized = dict(item)
    normalized["loaded_modules"] = modules
    normalized["critical_callables"] = callables
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("loaded runtime attestation canonical replay differs")
    return normalized


def _build_loaded_runtime_attestation_v1(
    *, dependency_closure: Mapping[str, object]
) -> dict[str, object]:
    """Bind loaded modules/callables and immutable image to measured bytes."""
    closure = _normalize_dependency_closure(dependency_closure)
    commit = str(closure["source_commit_sha"])
    image_digest = os.environ.get(IMAGE_DIGEST_ENV, "")
    image_reference = os.environ.get(IMAGE_REFERENCE_ENV, "")
    image_commit = os.environ.get(IMAGE_SOURCE_COMMIT_ENV, "")
    if (
        not image_digest.startswith("sha256:")
        or _SHA256.fullmatch(image_digest[7:]) is None
        or not image_reference.endswith(f"@{image_digest}")
        or image_commit != commit
    ):
        _fail("immutable image runtime environment differs from clean Git HEAD")
    closure_by_path = {
        str(value["module_path"]): value
        for value in closure["module_code_identities"]
    }
    loaded_modules: list[dict[str, object]] = []
    for path in EXECUTED_DEPENDENCY_MODULE_PATHS:
        module_name = _module_name_for_path_v1(path)
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
                f"loaded dependency import failed for {module_name}"
            ) from exc
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None)
        module_file = getattr(module, "__file__", None)
        expected_origin = (REPOSITORY_ROOT / path).resolve(strict=True)
        try:
            actual_origin = Path(str(origin)).resolve(strict=True)
            actual_file = Path(str(module_file)).resolve(strict=True)
        except OSError as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
                f"loaded module origin is absent for {module_name}"
            ) from exc
        if (
            sys.modules.get(module_name) is not module
            or actual_origin != expected_origin
            or actual_file != expected_origin
            or getattr(module, "__name__", None) != module_name
        ):
            _fail(f"loaded module origin differs for {module_name}")
        expected = closure_by_path[path]
        current_raw = _secure_read_repository_file_v1(
            REPOSITORY_ROOT, path, label=f"loaded module {module_name}"
        )
        if sha256(current_raw).hexdigest() != expected["module_sha256"]:
            _fail(f"loaded module source differs for {module_name}")
        loaded_modules.append({
            "module_name": module_name,
            "module_path": path,
            "module_origin": str(expected_origin),
            "source_commit_sha": commit,
            "module_sha256": expected["module_sha256"],
        })
    loaded_modules.sort(key=lambda value: str(value["module_path"]))
    critical_callables: list[dict[str, object]] = []
    for module, attribute, expected_path in _critical_loaded_callables_v1():
        function = getattr(module, attribute, None)
        expected_module = _module_name_for_path_v1(expected_path)
        expected_filename = str((REPOSITORY_ROOT / expected_path).resolve(strict=True))
        if (
            not inspect.isfunction(function)
            or function.__module__ != expected_module
            or Path(function.__code__.co_filename).resolve(strict=True)
            != Path(expected_filename)
        ):
            _fail(f"critical loaded callable differs for {expected_module}.{attribute}")
        code_sha256 = canonical_sha256(
            _code_object_fingerprint_v1(function.__code__)
        )
        committed_code_sha256 = _compiled_callable_code_sha256_v1(
            expected_path=expected_path,
            expected_qualname=function.__code__.co_qualname,
        )
        if code_sha256 != committed_code_sha256:
            _fail(
                f"critical loaded callable differs from measured source for "
                f"{expected_module}.{attribute}"
            )
        critical_callables.append({
            "module_name": expected_module,
            "attribute": attribute,
            "qualname": function.__qualname__,
            "code_filename": expected_filename,
            "code_sha256": code_sha256,
            "committed_source_code_sha256": committed_code_sha256,
            "loaded_code_matches_committed_source": True,
        })
    critical_callables.sort(
        key=lambda value: (str(value["module_name"]), str(value["attribute"]))
    )
    body: dict[str, object] = {
        "schema_version": RUNTIME_ATTESTATION_SCHEMA,
        "source_commit_sha": commit,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_executable": str(Path(sys.executable).resolve(strict=True)),
        "image_reference": image_reference,
        "image_digest": image_digest,
        "image_source_commit_sha": image_commit,
        "loaded_modules": loaded_modules,
        "loaded_module_manifest_sha256": canonical_sha256(loaded_modules),
        "critical_callables": critical_callables,
        "critical_callable_manifest_sha256": canonical_sha256(
            critical_callables
        ),
        "all_module_origins_canonical": True,
        "all_loaded_sources_match_dependency_closure": True,
        "all_critical_callables_bound_to_measured_modules": True,
        "immutable_image_identity_environment_required": True,
    }
    body["runtime_attestation_sha256"] = canonical_sha256(body)
    return _normalize_runtime_attestation_v1(
        body, dependency_closure=closure
    )


def _revalidate_publisher_runtime_with_current_v1(
    *,
    publisher_attestation: Mapping[str, object],
    current_attestation: Mapping[str, object],
    dependency_closure: Mapping[str, object],
) -> dict[str, object]:
    publisher = _normalize_runtime_attestation_v1(
        publisher_attestation, dependency_closure=dependency_closure
    )
    current = _normalize_runtime_attestation_v1(
        current_attestation, dependency_closure=dependency_closure
    )
    publisher_modules = {
        str(value["module_path"]): str(value["module_sha256"])
        for value in publisher["loaded_modules"]
    }
    current_modules = {
        str(value["module_path"]): str(value["module_sha256"])
        for value in current["loaded_modules"]
    }
    publisher_callables = {
        (str(value["module_name"]), str(value["attribute"])): {
            "qualname": value["qualname"],
            "code_sha256": value["code_sha256"],
        }
        for value in publisher["critical_callables"]
    }
    current_callables = {
        (str(value["module_name"]), str(value["attribute"])): {
            "qualname": value["qualname"],
            "code_sha256": value["code_sha256"],
        }
        for value in current["critical_callables"]
    }
    if (
        publisher["source_commit_sha"] != current["source_commit_sha"]
        or publisher["python_implementation"] != current["python_implementation"]
        or publisher["python_version"] != current["python_version"]
        or publisher_modules != current_modules
        or publisher_callables != current_callables
    ):
        _fail("current runtime does not revalidate publisher loaded execution")
    body: dict[str, object] = {
        "publisher_runtime_attestation_sha256": publisher[
            "runtime_attestation_sha256"
        ],
        "current_runtime_attestation_sha256": current[
            "runtime_attestation_sha256"
        ],
        "source_commit_sha": current["source_commit_sha"],
        "module_source_identities_equal": True,
        "critical_callable_code_identities_equal": True,
        "python_runtime_equal": True,
        "publisher_image_digest": publisher["image_digest"],
        "current_image_digest": current["image_digest"],
        "same_image_digest_required_for_read_only_reopen": False,
        "same_source_commit_required": True,
    }
    body["runtime_revalidation_sha256"] = canonical_sha256(body)
    return body


def _validate_plan_code_against_dependency_closure_v1(
    *,
    plan: Mapping[str, object],
    dependency_closure: Mapping[str, object],
) -> None:
    """Prove the tracked plan's scientific source bytes are those executed."""
    closure = _normalize_dependency_closure(dependency_closure)
    by_path = {
        str(identity["module_path"]): identity
        for identity in closure["module_code_identities"]
    }
    for field, expected_path in (
        ("source_v2_code_identity", capture_v1.SOURCE_V2_MODULE_PATH),
        (
            "component_producer_code_identity",
            capture_v1.COMPONENT_PRODUCER_MODULE_PATH,
        ),
    ):
        try:
            planned = source.normalize_code_identity_v2(
                plan[field],
                expected_module_path=expected_path,
                label=f"capture plan {field}",
            )
        except source.CorpusR6MatchupSourceV2Error as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(str(exc)) from exc
        executed = by_path.get(expected_path)
        if (
            executed is None
            or executed["module_path"] != planned["module_path"]
            or executed["module_sha256"] != planned["module_sha256"]
        ):
            _fail(f"capture plan {field} differs from executed source bytes")


def _validate_plan_with_cached_authority(
    plan_value: object,
    *,
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV1,
    adapter_final_release_lock_commit_sha: str,
    adapter_final_release_lock_raw: bytes,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Repeat the v2 prerequisite proof using the cached authority object."""
    try:
        plan = capture_v2.validate_capture_plan_lock_v2(plan_value)
        base = capture_v2._base_projection(plan)
        rebuilt_base = capture_v1.validate_capture_plan_against_prerequisites_v1(
            base,
            adapter_final_release_lock_commit_sha=(
                adapter_final_release_lock_commit_sha
            ),
            adapter_final_release_lock_raw=adapter_final_release_lock_raw,
            fixed_g0_replay_receipt=fixed_g0_replay_receipt,
            fixed_g0_replay_receipt_identity=fixed_g0_replay_receipt_identity,
            catalog_release=catalog_release,
            catalog_release_identity=catalog_release_identity,
            accepted_candidate_release=reopened.candidate_release,
            accepted_candidate_release_identity=(
                reopened.candidate_release_identity
            ),
            upstream_source_release=upstream_source_release,
            upstream_source_release_identity=upstream_source_release_identity,
            upstream_pack_row_objects=upstream_pack_row_objects,
        )
        binding = capture_v2._authority_binding(
            reopened,
            expected_root_identity=plan[
                "fixed_g0_candidate_authority_root_identity"
            ],
            expected_candidate_release_identity=plan[
                "accepted_candidate_release_identity"
            ],
            expected_candidate_release_sha256=plan[
                "accepted_candidate_release_sha256"
            ],
            expected_catalog_receipt_identity=plan[
                "fixed_g0_replay_receipt_identity"
            ],
            expected_catalog_receipt_sha256=plan[
                "fixed_g0_replay_receipt_sha256"
            ],
        )
        rebuilt = capture_v2._upgrade(rebuilt_base, binding=binding)
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"capture-plan cached-authority replay failed: {exc}"
        ) from exc
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(plan):
        _fail("capture plan differs from cached candidate authority")
    return plan


def _publish_component_with_cached_authority(
    *,
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV1,
    candidate_authority_root_identity: Mapping[str, object],
    producer_id: str,
    producer_release_id: str,
    producer_namespace: str,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    structural_catalogs: Sequence[Mapping[str, object]],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    producer_code_identity: Mapping[str, object],
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Run the v2 component publication proof without reopening candidates."""
    try:
        binding = component_v2._candidate_binding(
            reopened,
            expected_root_identity=candidate_authority_root_identity,
            expected_catalog_replay_receipt_identity=(
                fixed_g0_replay_receipt_identity
            ),
            expected_catalog_replay_receipt_sha256=fixed_g0_replay_receipt[
                "replay_receipt_sha256"
            ],
            expected_catalog_release_identity=catalog_release_identity,
            expected_catalog_release_sha256=catalog_release["release_sha256"],
        )
        v1_result = component_v1.publish_all_54_component_release_v1(
            producer_id=producer_id,
            producer_release_id=producer_release_id,
            producer_namespace=producer_namespace,
            fixed_g0_replay_receipt=fixed_g0_replay_receipt,
            fixed_g0_replay_receipt_identity=fixed_g0_replay_receipt_identity,
            catalog_release=catalog_release,
            catalog_release_identity=catalog_release_identity,
            structural_catalogs=structural_catalogs,
            accepted_candidate_release=reopened.candidate_release,
            accepted_candidate_release_identity=(
                reopened.candidate_release_identity
            ),
            upstream_source_release=upstream_source_release,
            upstream_source_release_identity=upstream_source_release_identity,
            upstream_pack_row_objects=upstream_pack_row_objects,
            producer_code_identity=producer_code_identity,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
        )
        _, v1_receipt, panel = component_v2._validate_publication_result(
            v1_result,
            reopened=reopened,
            binding=binding,
            supplied_catalog_release_identity=catalog_release_identity,
        )
        receipt = component_v2._build_receipt(
            binding=binding, v1_receipt=v1_receipt
        )
        result = {
            "publication_receipt": receipt,
            "component_publication_result": {
                "publication_receipt": v1_receipt,
                "offline_panel": panel,
            },
        }
        durable_panel = component_v2._durable_validate_full_result(
            receipt=receipt,
            component_result=result["component_publication_result"],
            read_exact=read_exact,
        )
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"component cached-authority publication failed: {exc}"
        ) from exc
    result["component_publication_result"]["offline_panel"] = durable_panel
    return result


def _validate_component_receipt_with_cached_authority(
    receipt_value: object,
    *,
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV1,
    plan: Mapping[str, object],
) -> dict[str, object]:
    """Bind the durable component receipt to the cached root and plan."""
    try:
        receipt = (
            component_v2.validate_component_publication_candidate_authority_receipt_v2(
                receipt_value
            )
        )
        binding = component_v2._candidate_binding(
            reopened,
            expected_root_identity=receipt["candidate_authority_root_identity"],
            expected_catalog_replay_receipt_identity=receipt[
                "catalog_replay_receipt_identity"
            ],
            expected_catalog_replay_receipt_sha256=receipt[
                "catalog_replay_receipt_sha256"
            ],
            expected_catalog_release_identity=receipt["catalog_release_identity"],
            expected_catalog_release_sha256=receipt["catalog_release_sha256"],
            expected_candidate_release_identity=receipt[
                "accepted_candidate_release_identity"
            ],
            expected_candidate_release_sha256=receipt[
                "accepted_candidate_release_sha256"
            ],
        )
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"component publication receipt authority replay failed: {exc}"
        ) from exc
    if any(receipt[field] != expected for field, expected in binding.items()):
        _fail("component publication receipt differs from candidate authority")
    v1_receipt = _mapping(
        receipt["component_publication_receipt"],
        label="nested component publication receipt",
    )
    if (
        v1_receipt["producer_id"] != plan["producer_id"]
        or v1_receipt["producer_release_id"] != plan["producer_release_id"]
        or v1_receipt["producer_namespace"] != plan["producer_namespace"]
        or v1_receipt["fixed_g0_replay_receipt_identity"]
        != plan["fixed_g0_replay_receipt_identity"]
        or v1_receipt["catalog_release_identity"]
        != plan["catalog_release_identity"]
        or v1_receipt["accepted_candidate_release_identity"]
        != plan["accepted_candidate_release_identity"]
        or v1_receipt["upstream_source_release_identity"]
        != plan["upstream_source_release_identity"]
        or receipt["component_publication_receipt_sha256"]
        != v1_receipt["component_publication_receipt_sha256"]
        or receipt["producer_release_identity"]
        != v1_receipt["producer_release_identity"]
        or receipt["producer_release_sha256"]
        != v1_receipt["producer_release_sha256"]
    ):
        _fail("component publication receipt differs from tracked capture plan")
    return receipt


def _durable_reopen_component_receipt(
    receipt_value: object,
    *,
    receipt_identity: Mapping[str, object],
    expected_uri: str,
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV1,
    plan: Mapping[str, object],
    producer_release: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    receipt = _validate_component_receipt_with_cached_authority(
        receipt_value, reopened=reopened, plan=plan
    )
    normalized_identity = _identity(
        receipt_identity, label="component publication receipt"
    )
    if normalized_identity["uri"] != expected_uri:
        _fail("component publication receipt URI differs")
    v1_receipt = _mapping(
        receipt["component_publication_receipt"],
        label="nested component publication receipt",
    )
    identities = [
        *_sequence(
            v1_receipt["upstream_provenance_identities"],
            label="component upstream provenance identities",
        ),
        *_sequence(
            v1_receipt["materialized_object_identities"],
            label="component materialized object identities",
        ),
    ]
    for ordinal, identity_value in enumerate(identities):
        identity = _identity(
            identity_value, label=f"component durable object[{ordinal}]"
        )
        try:
            raw = read_exact(identity)
        except Exception as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
                f"component durable object[{ordinal}] exact reopen failed"
            ) from exc
        if (
            type(raw) is not bytes
            or len(raw) != identity["bytes"]
            or sha256(raw).hexdigest() != identity["sha256"]
        ):
            _fail(f"component durable object[{ordinal}] identity differs")
    upstream_release, upstream_identity = _parse_exact_json(
        plan["upstream_source_release_identity"],
        read_exact=read_exact,
        label="tracked upstream source release",
    )
    pack_bindings = _sequence(
        plan["upstream_pack_bindings"], label="tracked upstream pack bindings"
    )
    pack_rows = [
        _parse_exact_json(
            _mapping(binding, label=f"tracked upstream pack[{ordinal}]")[
                "exact_rows_identity"
            ],
            read_exact=read_exact,
            label=f"tracked upstream pack rows[{ordinal}]",
        )[0]
        for ordinal, binding in enumerate(pack_bindings)
    ]
    try:
        validated_upstream, validated_upstream_identity = (
            capture_v1._validate_upstream_release(
                value=upstream_release,
                identity=upstream_identity,
                pack_row_objects=pack_rows,
                expected_fixed_source_root_identity=plan[
                    "fixed_g0_replay_receipt_identity"
                ],
            )
        )
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"tracked upstream source replay failed: {exc}"
        ) from exc
    if (
        validated_upstream_identity != plan["upstream_source_release_identity"]
        or validated_upstream["upstream_release_sha256"]
        != plan["upstream_source_release_sha256"]
        or capture_v1._pack_bindings(validated_upstream) != pack_bindings
    ):
        _fail("tracked upstream source differs from capture plan")
    producer_identity = _identity(
        v1_receipt["producer_release_identity"], label="component producer root"
    )
    if (
        producer_identity != receipt["producer_release_identity"]
        or canonical_json_bytes(producer_release)
        != read_exact(producer_identity)
        or producer_release["producer_release_sha256"]
        != receipt["producer_release_sha256"]
    ):
        _fail("component receipt differs from exact producer root")
    return receipt


def _publish_terminal_source_release_with_cached_authority(
    *,
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV1,
    component_result: Mapping[str, object],
    release_id: str,
    namespace: str,
    capture_plan_binding: Mapping[str, object],
    triples: Sequence[Mapping[str, object]],
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Build/deep-reopen/publish source-v2 root using cached candidates."""
    component = _mapping(
        component_result["component_publication_result"],
        label="component publication result",
    )
    panel = _mapping(component["offline_panel"], label="component offline panel")
    receipt = _mapping(
        component_result["publication_receipt"],
        label="candidate-authority component receipt",
    )
    rows = [_mapping(value, label="source triple") for value in triples]
    if len(rows) != source.TASK_COUNT:
        _fail("terminal source release requires exactly 54 triples")
    try:
        base = release_v1.build_matchup_source_release_v1(
            release_id=release_id,
            namespace=namespace,
            capture_plan_binding=capture_plan_binding,
            producer_release=panel["producer_release"],
            producer_release_identity=panel["producer_release_identity"],
            source_exports=[row["source_export"] for row in rows],
            source_export_identities=[
                row["source_export_identity"] for row in rows
            ],
            capture_receipts=[row["capture_receipt"] for row in rows],
            capture_receipt_identities=[
                row["capture_receipt_identity"] for row in rows
            ],
            operator_results=[row["operator_result"] for row in rows],
            operator_result_identities=[
                row["operator_result_identity"] for row in rows
            ],
        )
        binding = release_v2._candidate_authority_binding(
            reopened,
            expected_root_identity=receipt["candidate_authority_root_identity"],
        )
        producer = release_v1._producer_release_shape(
            panel["producer_release"], identity=panel["producer_release_identity"]
        )
        if (
            producer["accepted_candidate_release_identity"]
            != binding["accepted_candidate_release_identity"]
            or producer["catalog_replay_receipt_identity"]
            != binding["catalog_replay_receipt_identity"]
            or producer["catalog_release_identity"]
            != binding["catalog_release_identity"]
        ):
            _fail("component producer differs from cached candidate authority")
        root = release_v2._build_release_v2(base_release=base, binding=binding)
        root = release_v2.validate_matchup_source_release_candidate_authority_v2(
            root
        )
        producer_reopened = release_v1._producer_release_shape(
            release_v1._parse_exact(
                panel["producer_release_identity"],
                read_exact=read_exact,
                label="component producer release",
            ),
            identity=panel["producer_release_identity"],
        )
        for ordinal in range(source.TASK_COUNT):
            deep = release_v1._reopen_validated_matchup_source_release_ordinal_v1(
                release=base,
                ordinal=ordinal,
                read_exact=read_exact,
                producer_release=producer_reopened,
            )
            release_v2._selected_candidate_binding(
                root=root,
                member=root["entries"][ordinal],
                reopened=reopened,
                ordinal=ordinal,
                source_candidate_artifact=deep["candidate_artifact"],
            )
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"terminal source release deep replay failed: {exc}"
        ) from exc
    root_uri = f"{root['namespace']}{release_v2.ROOT_FILENAME}"
    reopened_root, root_identity = _publish_json(
        root,
        uri=root_uri,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="candidate-authority source release",
    )
    validated = release_v2.validate_matchup_source_release_candidate_authority_v2(
        reopened_root
    )
    if validated != root:
        _fail("candidate-authority source root exact reopen differs")
    return {"release": root, "release_identity": root_identity}


def _batch_member(
    *,
    ordinal: int,
    candidate_root_identity: Mapping[str, object],
    candidate_root_sha256: str,
    capture_plan_task: Mapping[str, object],
    candidate_entry: Mapping[str, object],
    component_entry: Mapping[str, object],
    triple: Mapping[str, object],
) -> dict[str, object]:
    candidate = _mapping(candidate_entry, label=f"candidate entry[{ordinal}]")
    plan_task = _mapping(
        capture_plan_task, label=f"capture-plan task[{ordinal}]"
    )
    component = _mapping(component_entry, label=f"component entry[{ordinal}]")
    row = _mapping(triple, label=f"source triple[{ordinal}]")
    if (
        candidate.get("source_task_ordinal") != ordinal
        or plan_task.get("source_task_ordinal") != ordinal
        or component.get("source_task_ordinal") != ordinal
        or row.get("source_task_ordinal") != ordinal
        or candidate.get("task_id") != row.get("task_id")
        or plan_task.get("task_id") != candidate.get("task_id")
        or plan_task.get("slate") != candidate.get("slate")
        or plan_task.get("catalog_identity") != candidate.get("catalog_identity")
        or plan_task.get("candidate_artifact_identity")
        != candidate.get("candidate_artifact_identity")
        or candidate.get("slate") != component.get("slate")
        or candidate.get("slate") != row.get("slate")
        or candidate.get("catalog_identity") != component.get("catalog_identity")
        or candidate.get("candidate_artifact_identity")
        != row.get("candidate_artifact_identity")
    ):
        _fail(f"batch ordinal {ordinal} candidate/component/source binding differs")
    body: dict[str, object] = {
        "schema_version": BATCH_MEMBER_SCHEMA,
        "source_task_ordinal": ordinal,
        "task_id": candidate["task_id"],
        "slate": candidate["slate"],
        "candidate_authority_root_identity": _identity(
            candidate_root_identity, label="candidate-authority root"
        ),
        "candidate_authority_root_sha256": candidate_root_sha256,
        "capture_plan_task_binding_sha256": canonical_sha256(plan_task),
        "catalog_identity": candidate["catalog_identity"],
        "candidate_artifact_identity": candidate["candidate_artifact_identity"],
        "candidate_artifact_sha256": candidate["candidate_artifact"][
            "candidate_artifact_sha256"
        ],
        "candidate_count": candidate["candidate_count"],
        "ordered_candidate_ids_sha256": candidate[
            "ordered_candidate_ids_sha256"
        ],
        "input_bundle_identity": component["input_bundle_identity"],
        "producer_receipt_identity": component["producer_receipt_identity"],
        "source_export_identity": row["source_export_identity"],
        "source_export_sha256": row["source_export"][
            "matchup_source_export_sha256"
        ],
        "capture_receipt_identity": row["capture_receipt_identity"],
        "capture_receipt_sha256": row["capture_receipt"][
            "matchup_capture_receipt_sha256"
        ],
        "operator_result_identity": row["operator_result_identity"],
        "operator_result_sha256": row["operator_result"][
            "matchup_operator_result_sha256"
        ],
        "annotation_row_count": row["source_export"]["annotation_row_count"],
        "support_preflight_passed": component["support_preflight_passed"],
        "candidate_component_source_cross_binding_verified": True,
        "all_source_objects_exact_reopened": True,
        **_policy(),
    }
    body["batch_member_sha256"] = canonical_sha256(body)
    return validate_batch_member_v1(body, expected_ordinal=ordinal)


def validate_batch_member_v1(
    value: object, *, expected_ordinal: int,
) -> dict[str, object]:
    if (
        type(expected_ordinal) is not int
        or not 0 <= expected_ordinal < source.TASK_COUNT
    ):
        _fail("batch member expected ordinal must be in 0..53")
    item = _mapping(value, label=f"batch member[{expected_ordinal}]")
    expected_fields = {
        "schema_version", "source_task_ordinal", "task_id", "slate",
        "candidate_authority_root_identity",
        "candidate_authority_root_sha256", "catalog_identity",
        "capture_plan_task_binding_sha256",
        "candidate_artifact_identity", "candidate_artifact_sha256",
        "candidate_count", "ordered_candidate_ids_sha256",
        "input_bundle_identity", "producer_receipt_identity",
        "source_export_identity", "source_export_sha256",
        "capture_receipt_identity", "capture_receipt_sha256",
        "operator_result_identity", "operator_result_sha256",
        "annotation_row_count", "support_preflight_passed",
        "candidate_component_source_cross_binding_verified",
        "all_source_objects_exact_reopened", *_policy().keys(),
        "batch_member_sha256",
    }
    if set(item) != expected_fields:
        _fail("batch member fields differ")
    retained = _digest(item["batch_member_sha256"], label="batch member hash")
    unhashed = dict(item)
    del unhashed["batch_member_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("batch member self-hash differs")
    for field, expected in _policy().items():
        if item.get(field) != expected:
            _fail("batch member claims forbidden authority")
    normalized = dict(item)
    for field in (
        "candidate_authority_root_identity", "catalog_identity",
        "candidate_artifact_identity", "input_bundle_identity",
        "producer_receipt_identity", "source_export_identity",
        "capture_receipt_identity", "operator_result_identity",
    ):
        normalized[field] = _identity(item[field], label=f"batch member {field}")
    for field in (
        "candidate_authority_root_sha256", "candidate_artifact_sha256",
        "capture_plan_task_binding_sha256",
        "ordered_candidate_ids_sha256", "source_export_sha256",
        "capture_receipt_sha256", "operator_result_sha256",
    ):
        normalized[field] = _digest(item[field], label=f"batch member {field}")
    if (
        item["schema_version"] != BATCH_MEMBER_SCHEMA
        or item["source_task_ordinal"] != expected_ordinal
        or item["task_id"]
        != catalog_v1.task_id_for_source_task(expected_ordinal)
        or item["slate"]
        != catalog_v1.expected_slate_for_source_task(expected_ordinal)
        or type(item["candidate_count"]) is not int
        or item["candidate_count"] < source.ENTRY_BUDGET
        or type(item["annotation_row_count"]) is not int
        or item["annotation_row_count"] < 0
        or item["support_preflight_passed"] is not True
        or item["candidate_component_source_cross_binding_verified"] is not True
        or item["all_source_objects_exact_reopened"] is not True
        or canonical_json_bytes(normalized) != canonical_json_bytes(item)
    ):
        _fail("batch member fixed law differs")
    return normalized


def _build_batch_root(
    *,
    run_id: str,
    prefix: str,
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV1,
    plan: Mapping[str, object],
    capture_plan_binding: Mapping[str, object],
    capture_plan_git_replay: Mapping[str, object],
    dependency_closure: Mapping[str, object],
    runtime_attestation: Mapping[str, object],
    output_uri_inventory: Mapping[str, object],
    publication_work_receipt: Mapping[str, object],
    publication_work_receipt_identity: Mapping[str, object],
    component_receipt: Mapping[str, object],
    component_receipt_identity: Mapping[str, object],
    producer_release: Mapping[str, object],
    producer_release_identity: Mapping[str, object],
    source_release: Mapping[str, object],
    source_release_identity: Mapping[str, object],
    member_identities: Sequence[Mapping[str, object]],
    members: Sequence[Mapping[str, object]],
    orchestrator_code_binding: Mapping[str, object],
    operator_code_binding: Mapping[str, object],
) -> dict[str, object]:
    root = _mapping(reopened.root, label="candidate-authority root")
    retained_dependency_closure = _normalize_dependency_closure(
        dependency_closure
    )
    retained_capture_replay = _normalize_capture_plan_git_replay_v1(
        capture_plan_git_replay,
        plan=plan,
        capture_plan_binding=capture_plan_binding,
    )
    retained_runtime = _normalize_runtime_attestation_v1(
        runtime_attestation, dependency_closure=retained_dependency_closure
    )
    retained_inventory = _normalize_output_uri_inventory_v1(
        output_uri_inventory
    )
    retained_work_receipt = _normalize_publication_work_receipt_v1(
        publication_work_receipt,
        output_uri_inventory=retained_inventory,
    )
    retained_work_receipt_identity = _identity(
        publication_work_receipt_identity,
        label="publication work receipt",
    )
    retained_component_receipt = _mapping(
        component_receipt, label="component receipt"
    )
    retained_component_receipt_identity = _identity(
        component_receipt_identity, label="component receipt"
    )
    retained_producer_release = _mapping(
        producer_release, label="producer release"
    )
    retained_producer_release_identity = _identity(
        producer_release_identity, label="producer release"
    )
    retained_source_release = _mapping(
        source_release, label="source release"
    )
    retained_source_release_identity = _identity(
        source_release_identity, label="source release"
    )
    identities = [
        _identity(value, label=f"batch member[{ordinal}]")
        for ordinal, value in enumerate(member_identities)
    ]
    retained_members = [
        validate_batch_member_v1(value, expected_ordinal=ordinal)
        for ordinal, value in enumerate(members)
    ]
    if (
        len(identities) != source.TASK_COUNT
        or len(retained_members) != source.TASK_COUNT
    ):
        _fail("batch root requires exactly 54 member receipts")
    descriptors = [
        {
            "source_task_ordinal": ordinal,
            "task_id": member["task_id"],
            "slate": member["slate"],
            "candidate_count": member["candidate_count"],
            "annotation_row_count": member["annotation_row_count"],
            "capture_plan_task_binding_sha256": member[
                "capture_plan_task_binding_sha256"
            ],
            "batch_member_identity": identities[ordinal],
            "batch_member_sha256": member["batch_member_sha256"],
        }
        for ordinal, member in enumerate(retained_members)
    ]
    body: dict[str, object] = {
        "schema_version": BATCH_RELEASE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "run_id": run_id,
        "namespace": prefix,
        "candidate_authority_root_identity": reopened.root_identity,
        "candidate_authority_root_sha256": root[
            "candidate_authority_release_sha256"
        ],
        "accepted_candidate_release_identity": (
            reopened.candidate_release_identity
        ),
        "accepted_candidate_release_sha256": reopened.candidate_release[
            "accepted_candidate_release_sha256"
        ],
        "capture_plan_binding": dict(capture_plan_binding),
        "capture_plan_sha256": plan["capture_plan_sha256"],
        "capture_plan_git_replay": retained_capture_replay,
        "capture_plan_git_replay_sha256": retained_capture_replay[
            "capture_plan_git_replay_sha256"
        ],
        "source_v2_code_identity": plan["source_v2_code_identity"],
        "component_producer_code_identity": plan[
            "component_producer_code_identity"
        ],
        "operator_code_binding": dict(operator_code_binding),
        "orchestrator_code_binding": dict(orchestrator_code_binding),
        "executed_dependency_closure": retained_dependency_closure,
        "executed_dependency_closure_sha256": retained_dependency_closure[
            "dependency_closure_sha256"
        ],
        "loaded_runtime_attestation": retained_runtime,
        "loaded_runtime_attestation_sha256": retained_runtime[
            "runtime_attestation_sha256"
        ],
        "output_uri_inventory": retained_inventory,
        "output_uri_inventory_sha256": retained_inventory[
            "output_uri_inventory_sha256"
        ],
        "publication_work_receipt_identity": retained_work_receipt_identity,
        "publication_work_receipt_sha256": retained_work_receipt[
            "publication_work_receipt_sha256"
        ],
        "catalog_release_identity": retained_component_receipt[
            "catalog_release_identity"
        ],
        "catalog_release_sha256": retained_component_receipt[
            "catalog_release_sha256"
        ],
        "upstream_source_release_identity": plan[
            "upstream_source_release_identity"
        ],
        "upstream_source_release_sha256": plan[
            "upstream_source_release_sha256"
        ],
        "component_publication_receipt_identity": (
            retained_component_receipt_identity
        ),
        "component_publication_receipt_sha256": retained_component_receipt[
            "candidate_authority_component_publication_receipt_sha256"
        ],
        "producer_release_identity": retained_producer_release_identity,
        "producer_release_sha256": retained_producer_release[
            "producer_release_sha256"
        ],
        "source_release_identity": retained_source_release_identity,
        "source_release_sha256": retained_source_release[
            "matchup_source_release_candidate_authority_sha256"
        ],
        "task_count": source.TASK_COUNT,
        "total_candidate_count": sum(
            int(member["candidate_count"]) for member in retained_members
        ),
        "total_annotation_row_count": sum(
            int(member["annotation_row_count"]) for member in retained_members
        ),
        "members": descriptors,
        "member_identity_manifest_sha256": canonical_sha256(identities),
        "member_descriptor_manifest_sha256": canonical_sha256(descriptors),
        "candidate_authority_full_replay_count": 1,
        "candidate_authority_exact_read_cache_enabled": True,
        "all_54_component_tasks_materialized": True,
        "all_54_source_triples_materialized": True,
        "all_54_member_receipts_exact_reopened": True,
        "terminal_source_release_exact_reopened": True,
        "create_once_resume_policy": CREATE_ONCE_RESUME_POLICY,
        "partial_prefix_exact_equal_resume_allowed": True,
        "every_returned_generation_exact_reopened_before_dependents": True,
        "different_bytes_collision_rejected": True,
        "resume_rebuilds_complete_graph_before_terminal_root": True,
        "same_commit_recovery_required": True,
        "recovery_source_commit_sha": capture_plan_binding["commit_sha"],
        "caller_supplied_final_lock_bytes_allowed": False,
        "loaded_runtime_and_image_attested": True,
        "exact_output_uri_inventory_enforced": True,
        "invocation_write_operations_and_bytes_precharged": True,
        "root_create_once_requested_last": True,
        **_policy(),
    }
    body["batch_release_sha256"] = canonical_sha256(body)
    return validate_batch_release_structure_v1(body)


def validate_batch_release_structure_v1(value: object) -> dict[str, object]:
    """Validate the bounded root; this alone grants no source authority."""
    item = _mapping(value, label="matchup source batch release")
    expected_fields = {
        "schema_version", "publication_mode", "run_id", "namespace",
        "candidate_authority_root_identity", "candidate_authority_root_sha256",
        "accepted_candidate_release_identity",
        "accepted_candidate_release_sha256", "capture_plan_binding",
        "capture_plan_sha256", "capture_plan_git_replay",
        "capture_plan_git_replay_sha256", "source_v2_code_identity",
        "component_producer_code_identity", "operator_code_binding",
        "orchestrator_code_binding", "executed_dependency_closure",
        "executed_dependency_closure_sha256", "loaded_runtime_attestation",
        "loaded_runtime_attestation_sha256", "output_uri_inventory",
        "output_uri_inventory_sha256", "publication_work_receipt_identity",
        "publication_work_receipt_sha256", "catalog_release_identity",
        "catalog_release_sha256", "upstream_source_release_identity",
        "upstream_source_release_sha256",
        "component_publication_receipt_identity",
        "component_publication_receipt_sha256", "producer_release_identity",
        "producer_release_sha256", "source_release_identity",
        "source_release_sha256", "task_count", "total_candidate_count",
        "total_annotation_row_count", "members",
        "member_identity_manifest_sha256", "member_descriptor_manifest_sha256",
        "candidate_authority_full_replay_count",
        "candidate_authority_exact_read_cache_enabled",
        "all_54_component_tasks_materialized",
        "all_54_source_triples_materialized",
        "all_54_member_receipts_exact_reopened",
        "terminal_source_release_exact_reopened",
        "create_once_resume_policy",
        "partial_prefix_exact_equal_resume_allowed",
        "every_returned_generation_exact_reopened_before_dependents",
        "different_bytes_collision_rejected",
        "resume_rebuilds_complete_graph_before_terminal_root",
        "same_commit_recovery_required", "recovery_source_commit_sha",
        "caller_supplied_final_lock_bytes_allowed",
        "loaded_runtime_and_image_attested",
        "exact_output_uri_inventory_enforced",
        "invocation_write_operations_and_bytes_precharged",
        "root_create_once_requested_last", *_policy().keys(),
        "batch_release_sha256",
    }
    if set(item) != expected_fields:
        _fail("batch release fields differ")
    retained = _digest(item["batch_release_sha256"], label="batch release hash")
    unhashed = dict(item)
    del unhashed["batch_release_sha256"]
    if canonical_sha256(unhashed) != retained:
        _fail("batch release self-hash differs")
    for field, expected in _policy().items():
        if item.get(field) != expected:
            _fail("batch release claims forbidden authority")
    prefix = output_prefix_for_run_v1(item.get("run_id"))
    descriptors = _sequence(item.get("members"), label="batch members")
    if len(descriptors) != source.TASK_COUNT:
        _fail("batch release requires exactly 54 member descriptors")
    normalized_descriptors: list[dict[str, object]] = []
    member_ids: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    total_candidates = 0
    total_annotations = 0
    for ordinal, value_descriptor in enumerate(descriptors):
        descriptor = _mapping(value_descriptor, label=f"member descriptor[{ordinal}]")
        if set(descriptor) != {
            "source_task_ordinal", "task_id", "slate", "candidate_count",
            "annotation_row_count", "capture_plan_task_binding_sha256",
            "batch_member_identity",
            "batch_member_sha256",
        }:
            _fail("batch member descriptor fields differ")
        identity = _identity(
            descriptor["batch_member_identity"],
            label=f"batch member descriptor[{ordinal}]",
        )
        expected_task_id = catalog_v1.task_id_for_source_task(ordinal)
        expected_slate = catalog_v1.expected_slate_for_source_task(ordinal)
        slate = _mapping(descriptor["slate"], label="descriptor slate")
        slate_id = str(expected_slate["slate_id"])
        expected_uri = (
            f"{prefix}source-task-{ordinal:02d}-{slate_id}/batch-member.json"
        )
        key = (str(identity["uri"]), str(identity["generation"]))
        if (
            descriptor["source_task_ordinal"] != ordinal
            or descriptor["task_id"] != expected_task_id
            or slate != expected_slate
            or identity["uri"] != expected_uri
            or key in seen
            or type(descriptor["candidate_count"]) is not int
            or descriptor["candidate_count"] < source.ENTRY_BUDGET
            or type(descriptor["annotation_row_count"]) is not int
            or descriptor["annotation_row_count"] < 0
        ):
            _fail("batch member descriptor order/identity differs")
        seen.add(key)
        _digest(descriptor["batch_member_sha256"], label="batch member SHA")
        _digest(
            descriptor["capture_plan_task_binding_sha256"],
            label="capture-plan task binding SHA",
        )
        normalized = dict(descriptor)
        normalized["batch_member_identity"] = identity
        normalized_descriptors.append(normalized)
        member_ids.append(identity)
        total_candidates += int(descriptor["candidate_count"])
        total_annotations += int(descriptor["annotation_row_count"])
    normalized = dict(item)
    for field in (
        "candidate_authority_root_identity",
        "accepted_candidate_release_identity", "catalog_release_identity",
        "upstream_source_release_identity", "producer_release_identity",
        "source_release_identity", "component_publication_receipt_identity",
        "publication_work_receipt_identity",
    ):
        normalized[field] = _identity(item[field], label=f"batch release {field}")
    for field in (
        "candidate_authority_root_sha256", "accepted_candidate_release_sha256",
        "capture_plan_sha256", "catalog_release_sha256",
        "upstream_source_release_sha256",
        "component_publication_receipt_sha256",
        "executed_dependency_closure_sha256", "producer_release_sha256",
        "source_release_sha256", "member_identity_manifest_sha256",
        "member_descriptor_manifest_sha256", "capture_plan_git_replay_sha256",
        "loaded_runtime_attestation_sha256", "output_uri_inventory_sha256",
        "publication_work_receipt_sha256",
    ):
        normalized[field] = _digest(item[field], label=f"batch release {field}")
    try:
        normalized["capture_plan_binding"] = release_v1._capture_plan_binding(
            item["capture_plan_binding"]
        )
        normalized["source_v2_code_identity"] = source.normalize_code_identity_v2(
            item["source_v2_code_identity"],
            expected_module_path=capture_v1.SOURCE_V2_MODULE_PATH,
            label="batch source-v2 code identity",
        )
        normalized["component_producer_code_identity"] = (
            source.normalize_code_identity_v2(
                item["component_producer_code_identity"],
                expected_module_path=capture_v1.COMPONENT_PRODUCER_MODULE_PATH,
                label="batch component-producer code identity",
            )
        )
    except (
        release_v1.CorpusR6MatchupSourceReleaseV1Error,
        source.CorpusR6MatchupSourceV2Error,
    ) as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(str(exc)) from exc
    normalized["operator_code_binding"] = _normalize_code_binding(
        item["operator_code_binding"],
        expected_path=operator_v2.OPERATOR_MODULE_PATH,
        label="operator code binding",
    )
    normalized["orchestrator_code_binding"] = _normalize_code_binding(
        item["orchestrator_code_binding"],
        expected_path=BATCH_MODULE_PATH,
        label="orchestrator code binding",
    )
    normalized["executed_dependency_closure"] = _normalize_dependency_closure(
        item["executed_dependency_closure"]
    )
    normalized["capture_plan_git_replay"] = (
        _normalize_capture_plan_git_replay_v1(
            item["capture_plan_git_replay"],
            plan=None,
            capture_plan_binding=normalized["capture_plan_binding"],
        )
    )
    normalized["loaded_runtime_attestation"] = _normalize_runtime_attestation_v1(
        item["loaded_runtime_attestation"],
        dependency_closure=normalized["executed_dependency_closure"],
    )
    normalized["output_uri_inventory"] = _normalize_output_uri_inventory_v1(
        item["output_uri_inventory"]
    )
    normalized["members"] = normalized_descriptors
    dependency_identities = {
        str(identity["module_path"]): identity
        for identity in normalized["executed_dependency_closure"][
            "module_code_identities"
        ]
    }
    source_release_identity = normalized["source_release_identity"]
    component_receipt_identity = normalized[
        "component_publication_receipt_identity"
    ]
    work_receipt_identity = normalized["publication_work_receipt_identity"]
    inventory = normalized["output_uri_inventory"]
    runtime_attestation = normalized["loaded_runtime_attestation"]
    if (
        item["schema_version"] != BATCH_RELEASE_SCHEMA
        or item["publication_mode"] != PUBLICATION_MODE
        or item["namespace"] != prefix
        or normalized["capture_plan_binding"]["relative_path"]
        != capture_v2.CAPTURE_PLAN_LOCK_PATH
        or normalized["capture_plan_binding"]["capture_plan_sha256"]
        != item["capture_plan_sha256"]
        or item["capture_plan_git_replay_sha256"]
        != normalized["capture_plan_git_replay"][
            "capture_plan_git_replay_sha256"
        ]
        or normalized["executed_dependency_closure"]["source_commit_sha"]
        != normalized["capture_plan_binding"]["commit_sha"]
        or normalized["operator_code_binding"]["effective_code_identity"][
            "source_commit_sha"
        ] != normalized["executed_dependency_closure"]["source_commit_sha"]
        or normalized["orchestrator_code_binding"]["effective_code_identity"][
            "source_commit_sha"
        ] != normalized["executed_dependency_closure"]["source_commit_sha"]
        or normalized["operator_code_binding"]["effective_code_identity"][
            "module_sha256"
        ]
        != dependency_identities[operator_v2.OPERATOR_MODULE_PATH][
            "module_sha256"
        ]
        or normalized["orchestrator_code_binding"]["effective_code_identity"][
            "module_sha256"
        ] != dependency_identities[BATCH_MODULE_PATH]["module_sha256"]
        or normalized["source_v2_code_identity"]["module_sha256"]
        != dependency_identities[capture_v1.SOURCE_V2_MODULE_PATH][
            "module_sha256"
        ]
        or normalized["component_producer_code_identity"]["module_sha256"]
        != dependency_identities[capture_v1.COMPONENT_PRODUCER_MODULE_PATH][
            "module_sha256"
        ]
        or source_release_identity["uri"]
        != f"{prefix}{release_v2.ROOT_FILENAME}"
        or component_receipt_identity["uri"]
        != f"{prefix}{COMPONENT_RECEIPT_FILENAME}"
        or item["executed_dependency_closure_sha256"]
        != normalized["executed_dependency_closure"][
            "dependency_closure_sha256"
        ]
        or item["loaded_runtime_attestation_sha256"]
        != runtime_attestation["runtime_attestation_sha256"]
        or runtime_attestation["source_commit_sha"]
        != normalized["capture_plan_binding"]["commit_sha"]
        or item["output_uri_inventory_sha256"]
        != inventory["output_uri_inventory_sha256"]
        or inventory["run_id"] != item["run_id"]
        or inventory["namespace"] != prefix
        or work_receipt_identity["uri"]
        != inventory["publication_work_receipt_uri"]
        or inventory["terminal_root_uri"] != f"{prefix}{ROOT_FILENAME}"
        or item["task_count"] != source.TASK_COUNT
        or item["total_candidate_count"] != total_candidates
        or item["total_annotation_row_count"] != total_annotations
        or item["member_identity_manifest_sha256"] != canonical_sha256(member_ids)
        or item["member_descriptor_manifest_sha256"]
        != canonical_sha256(normalized_descriptors)
        or item["candidate_authority_full_replay_count"] != 1
        or any(
            item[field] is not True
            for field in (
                "candidate_authority_exact_read_cache_enabled",
                "all_54_component_tasks_materialized",
                "all_54_source_triples_materialized",
                "all_54_member_receipts_exact_reopened",
                "terminal_source_release_exact_reopened",
                "partial_prefix_exact_equal_resume_allowed",
                "every_returned_generation_exact_reopened_before_dependents",
                "different_bytes_collision_rejected",
                "resume_rebuilds_complete_graph_before_terminal_root",
                "same_commit_recovery_required",
                "loaded_runtime_and_image_attested",
                "exact_output_uri_inventory_enforced",
                "invocation_write_operations_and_bytes_precharged",
                "root_create_once_requested_last",
            )
        )
        or item["recovery_source_commit_sha"]
        != normalized["capture_plan_binding"]["commit_sha"]
        or item["caller_supplied_final_lock_bytes_allowed"] is not False
        or item["create_once_resume_policy"] != CREATE_ONCE_RESUME_POLICY
        or canonical_json_bytes(normalized) != canonical_json_bytes(item)
    ):
        _fail("batch release fixed law differs")
    return normalized


def _reopen_batch_with_cached_authority(
    *,
    root: Mapping[str, object],
    root_identity: Mapping[str, object],
    reopened: candidate_authority.ReopenedFixedG0CandidateAuthorityV1,
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> None:
    """Deep-reopen the terminal source graph and every bounded member."""
    if (
        root["candidate_authority_root_identity"] != reopened.root_identity
        or root["candidate_authority_root_sha256"]
        != reopened.root["candidate_authority_release_sha256"]
        or root["accepted_candidate_release_identity"]
        != reopened.candidate_release_identity
        or root["accepted_candidate_release_sha256"]
        != reopened.candidate_release["accepted_candidate_release_sha256"]
    ):
        _fail("batch root differs from exact-reopened candidate authority")
    binding = _mapping(root["capture_plan_binding"], label="capture-plan binding")
    try:
        plan_raw = git_blob(
            repository_root, binding["commit_sha"], binding["relative_path"]
        )
        plan_parsed = json.loads(plan_raw.decode("utf-8"))
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            "tracked capture-plan reopen failed"
        ) from exc
    if canonical_json_bytes(plan_parsed) + b"\n" != plan_raw:
        _fail("tracked capture plan must be canonical JSON plus one newline")
    plan = capture_v2.validate_capture_plan_lock_v2(plan_parsed)
    _validate_capture_plan_binding(
        plan=plan,
        capture_plan_binding=binding,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if (
        plan["capture_plan_sha256"] != root["capture_plan_sha256"]
        or plan["fixed_g0_candidate_authority_root_identity"]
        != reopened.root_identity
    ):
        _fail("tracked capture plan differs from batch/candidate root")
    replay = _normalize_capture_plan_git_replay_v1(
        root["capture_plan_git_replay"],
        plan=plan,
        capture_plan_binding=binding,
    )
    if replay["capture_plan_git_replay_sha256"] != root[
        "capture_plan_git_replay_sha256"
    ]:
        _fail("capture-plan Git replay differs from batch root")
    expected_inventory = _output_uri_inventory_v1(
        run_id=root["run_id"], plan_value=plan
    )
    if expected_inventory != root["output_uri_inventory"]:
        _fail("output URI inventory differs from tracked plan")
    dependency_closure = _replay_executed_dependency_closure(
        expected_commit_sha=binding["commit_sha"],
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if dependency_closure != root["executed_dependency_closure"]:
        _fail("executed dependency closure differs from batch root")
    _normalize_runtime_attestation_v1(
        root["loaded_runtime_attestation"],
        dependency_closure=dependency_closure,
    )
    _validate_plan_code_against_dependency_closure_v1(
        plan=plan, dependency_closure=dependency_closure
    )
    operator_binding = _mapping(
        root["operator_code_binding"], label="operator code binding"
    )
    operator_effective, operator_rebuilt = _validate_code_identity(
        operator_binding["primary_code_identity"],
        expected_path=operator_v2.OPERATOR_MODULE_PATH,
        repair_sha256=operator_binding["repair_sha256"],
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    orchestrator_binding = _mapping(
        root["orchestrator_code_binding"], label="orchestrator code binding"
    )
    _, orchestrator_rebuilt = _validate_code_identity(
        orchestrator_binding["primary_code_identity"],
        expected_path=BATCH_MODULE_PATH,
        repair_sha256=orchestrator_binding["repair_sha256"],
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if (
        operator_rebuilt != operator_binding
        or orchestrator_rebuilt != orchestrator_binding
    ):
        _fail("batch code binding canonical replay differs")
    source_root_body, source_root_identity = _parse_exact_json(
        root["source_release_identity"],
        read_exact=read_exact,
        label="candidate-authority source release",
    )
    source_root = release_v2.validate_matchup_source_release_candidate_authority_v2(
        source_root_body
    )
    if (
        source_root_identity != root["source_release_identity"]
        or source_root_identity["uri"]
        != f"{root['namespace']}{release_v2.ROOT_FILENAME}"
        or source_root[
            "matchup_source_release_candidate_authority_sha256"
        ] != root["source_release_sha256"]
        or source_root["candidate_authority_root_identity"]
        != reopened.root_identity
        or source_root["operator_code_identity"] != operator_effective
        or source_root["release_id"] != root["run_id"]
        or source_root["namespace"] != root["namespace"]
        or source_root["capture_plan_binding"] != binding
        or source_root["catalog_release_identity"]
        != plan["catalog_release_identity"]
        or source_root["accepted_candidate_release_identity"]
        != reopened.candidate_release_identity
        or source_root["upstream_source_release_identity"]
        != plan["upstream_source_release_identity"]
    ):
        _fail("terminal source release differs from batch authority")
    base_release = release_v2._project_release_v1(source_root)
    producer_body = release_v1._parse_exact(
        source_root["producer_release_identity"],
        read_exact=read_exact,
        label="component producer release",
    )
    producer = release_v1._producer_release_shape(
        producer_body, identity=source_root["producer_release_identity"]
    )
    if (
        source_root["producer_release_identity"]
        != root["producer_release_identity"]
        or producer["producer_release_sha256"] != root["producer_release_sha256"]
        or producer["producer_release_sha256"]
        != source_root["producer_release_sha256"]
        or producer["catalog_release_identity"]
        != plan["catalog_release_identity"]
        or producer["accepted_candidate_release_identity"]
        != reopened.candidate_release_identity
        or producer["upstream_source_release_identity"]
        != plan["upstream_source_release_identity"]
        or producer["producer_code_identity"]
        != plan["component_producer_code_identity"]
    ):
        _fail("exact producer release differs from batch/plan/source authority")
    component_receipt_body, component_receipt_identity = _parse_exact_json(
        root["component_publication_receipt_identity"],
        read_exact=read_exact,
        label="component publication receipt",
    )
    component_receipt = _durable_reopen_component_receipt(
        component_receipt_body,
        receipt_identity=component_receipt_identity,
        expected_uri=f"{root['namespace']}{COMPONENT_RECEIPT_FILENAME}",
        reopened=reopened,
        plan=plan,
        producer_release=producer,
        read_exact=read_exact,
    )
    if (
        component_receipt_identity
        != root["component_publication_receipt_identity"]
        or component_receipt[
            "candidate_authority_component_publication_receipt_sha256"
        ] != root["component_publication_receipt_sha256"]
        or component_receipt["producer_release_identity"]
        != root["producer_release_identity"]
        or component_receipt["producer_release_sha256"]
        != root["producer_release_sha256"]
    ):
        _fail("component publication receipt differs from batch root")
    work_receipt_body, work_receipt_identity = _parse_exact_json(
        root["publication_work_receipt_identity"],
        read_exact=read_exact,
        label="publication work receipt",
    )
    work_receipt = _normalize_publication_work_receipt_v1(
        work_receipt_body,
        output_uri_inventory=expected_inventory,
    )
    if (
        work_receipt_identity != root["publication_work_receipt_identity"]
        or work_receipt["publication_work_receipt_sha256"]
        != root["publication_work_receipt_sha256"]
        or work_receipt["source_commit_sha"] != binding["commit_sha"]
    ):
        _fail("publication work receipt differs from batch root")
    candidate_entries = _sequence(
        reopened.candidate_release["entries"], label="candidate entries"
    )
    plan_tasks = _sequence(plan["source_task_bindings"], label="capture-plan tasks")
    descriptors = _sequence(root["members"], label="batch member descriptors")
    member_bodies: list[dict[str, object]] = []
    member_identities: list[dict[str, object]] = []
    candidate_root_sha = _digest(
        reopened.root["candidate_authority_release_sha256"],
        label="candidate-authority root SHA",
    )
    for ordinal, descriptor_value in enumerate(descriptors):
        descriptor = _mapping(
            descriptor_value, label=f"batch member descriptor[{ordinal}]"
        )
        member_body, member_identity = _parse_exact_json(
            descriptor["batch_member_identity"],
            read_exact=read_exact,
            label=f"batch member[{ordinal}]",
        )
        member = validate_batch_member_v1(
            member_body, expected_ordinal=ordinal
        )
        source_member = source_root["entries"][ordinal]
        candidate_entry = candidate_entries[ordinal]
        if (
            member_identity != descriptor["batch_member_identity"]
            or member["batch_member_sha256"]
            != descriptor["batch_member_sha256"]
            or member["task_id"] != descriptor["task_id"]
            or member["slate"] != descriptor["slate"]
            or member["candidate_count"] != descriptor["candidate_count"]
            or member["annotation_row_count"]
            != descriptor["annotation_row_count"]
            or member["capture_plan_task_binding_sha256"]
            != descriptor["capture_plan_task_binding_sha256"]
            or member["capture_plan_task_binding_sha256"]
            != canonical_sha256(plan_tasks[ordinal])
            or member["candidate_artifact_identity"]
            != candidate_entry["candidate_artifact_identity"]
            or source_member["candidate_artifact_identity"]
            != member["candidate_artifact_identity"]
            or source_member["source_export_identity"]
            != member["source_export_identity"]
            or source_member["capture_receipt_identity"]
            != member["capture_receipt_identity"]
            or source_member["operator_result_identity"]
            != member["operator_result_identity"]
        ):
            _fail(f"batch member[{ordinal}] differs from terminal source graph")
        deep = release_v1._reopen_validated_matchup_source_release_ordinal_v1(
            release=base_release,
            ordinal=ordinal,
            read_exact=read_exact,
            producer_release=producer,
        )
        release_v2._selected_candidate_binding(
            root=source_root,
            member=source_member,
            reopened=reopened,
            ordinal=ordinal,
            source_candidate_artifact=deep["candidate_artifact"],
        )
        component_entry = {
            "source_task_ordinal": ordinal,
            "slate": source_member["slate"],
            "catalog_identity": source_member["catalog_identity"],
            "input_bundle_identity": source_member["input_bundle_identity"],
            "producer_receipt_identity": source_member[
                "producer_receipt_identity"
            ],
            "support_preflight_passed": deep["producer_receipt"][
                "support_preflight_passed"
            ],
        }
        triple = {
            "source_task_ordinal": ordinal,
            "task_id": source_member["task_id"],
            "slate": source_member["slate"],
            "source_export": deep["source_export"],
            "source_export_identity": source_member["source_export_identity"],
            "capture_receipt": deep["capture_receipt"],
            "capture_receipt_identity": source_member[
                "capture_receipt_identity"
            ],
            "operator_result": deep["operator_result"],
            "operator_result_identity": source_member[
                "operator_result_identity"
            ],
            "candidate_artifact_identity": source_member[
                "candidate_artifact_identity"
            ],
        }
        expected_member = _batch_member(
            ordinal=ordinal,
            candidate_root_identity=reopened.root_identity,
            candidate_root_sha256=candidate_root_sha,
            capture_plan_task=plan_tasks[ordinal],
            candidate_entry=candidate_entry,
            component_entry=component_entry,
            triple=triple,
        )
        if member != expected_member:
            _fail(f"batch member[{ordinal}] exact reconstruction differs")
        member_bodies.append(member)
        member_identities.append(member_identity)
    expected_root = _build_batch_root(
        run_id=str(root["run_id"]),
        prefix=str(root["namespace"]),
        reopened=reopened,
        plan=plan,
        capture_plan_binding=binding,
        capture_plan_git_replay=replay,
        dependency_closure=dependency_closure,
        runtime_attestation=root["loaded_runtime_attestation"],
        output_uri_inventory=expected_inventory,
        publication_work_receipt=work_receipt,
        publication_work_receipt_identity=work_receipt_identity,
        component_receipt=component_receipt,
        component_receipt_identity=component_receipt_identity,
        producer_release=producer,
        producer_release_identity=source_root["producer_release_identity"],
        source_release=source_root,
        source_release_identity=source_root_identity,
        member_identities=member_identities,
        members=member_bodies,
        orchestrator_code_binding=orchestrator_binding,
        operator_code_binding=operator_binding,
    )
    if root != expected_root:
        _fail("terminal batch root exact reconstruction differs")
    if root_identity["uri"] != f"{root['namespace']}{ROOT_FILENAME}":
        _fail("batch root identity differs from fixed namespace law")


def _reopen_matchup_source_batch_candidate_authority_with_adapters_v1(
    *,
    batch_release_identity: Mapping[str, object],
    repository_root: Path,
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Independently exact-reopen the batch with one candidate-root replay."""
    trusted_root_identity = _public_batch_root_identity_v1(
        batch_release_identity
    )
    cache = ExactReadCacheV1(read_exact)
    root_body, root_identity = _parse_exact_json(
        trusted_root_identity,
        read_exact=cache.read,
        label="terminal matchup source batch root",
    )
    root = validate_batch_release_structure_v1(root_body)
    try:
        reopened = candidate_authority.reopen_fixed_g0_candidate_authority_release_v1(
            root["candidate_authority_root_identity"],
            repository_root=repository_root,
            read_exact=cache.read,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"candidate-authority one-time replay failed: {exc}"
        ) from exc
    _reopen_batch_with_cached_authority(
        root=root,
        root_identity=root_identity,
        reopened=reopened,
        repository_root=repository_root,
        read_exact=cache.read,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    return {
        "batch_release": root,
        "batch_release_identity": root_identity,
        "source_release_identity": root["source_release_identity"],
        "candidate_authority_full_replay_count": 1,
        "exact_read_unique_object_count": cache.unique_object_count,
        "exact_read_cache_hit_count": cache.hit_count,
        "exact_read_cache_current_bytes": cache.cached_bytes,
        "exact_read_cache_byte_limit": cache.max_cached_bytes,
        "exact_read_cache_eviction_count": cache.eviction_count,
        "exact_read_cache_oversize_bypass_count": cache.oversize_bypass_count,
        "exact_read_budget_receipt": cache.budget_receipt(),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }


def _publish_matchup_source_batch_candidate_authority_with_adapters_v1(
    *,
    run_id: str,
    candidate_authority_root_identity: Mapping[str, object],
    capture_plan: Mapping[str, object],
    capture_plan_binding: Mapping[str, object],
    capture_plan_git_replay: Mapping[str, object],
    adapter_final_release_lock_commit_sha: str,
    adapter_final_release_lock_raw: bytes,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    structural_catalogs: Sequence[Mapping[str, object]],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    operator_code_identity: Mapping[str, object],
    orchestrator_code_identity: Mapping[str, object],
    repository_root: Path,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    output_uri_inventory: Mapping[str, object],
    publication_transport: GenerationPinnedGCSBatchTransportV1,
    reopened_candidate_authority: (
        candidate_authority.ReopenedFixedG0CandidateAuthorityV1 | None
    ) = None,
    runtime_attestation: Mapping[str, object] | None = None,
    operator_repair_sha256: str | None = None,
    orchestrator_repair_sha256: str | None = None,
) -> dict[str, object]:
    """Publish one complete 54-slate batch; the batch root is requested last."""
    prefix = output_prefix_for_run_v1(run_id)
    if (
        type(publication_transport) is not GenerationPinnedGCSBatchTransportV1
        or getattr(publish_create_once, "__self__", None) is not publication_transport
        or getattr(publish_create_once, "__func__", None)
        is not GenerationPinnedGCSBatchTransportV1.publish_create_once
        or getattr(read_exact, "__self__", None) is not publication_transport
        or getattr(read_exact, "__func__", None)
        is not GenerationPinnedGCSBatchTransportV1.read_exact
    ):
        _fail("trusted batch requires its concrete exact-inventory transport")
    cache = ExactReadCacheV1(read_exact)
    inventory = _normalize_output_uri_inventory_v1(output_uri_inventory)
    if inventory != _output_uri_inventory_v1(
        run_id=run_id, plan_value=capture_plan
    ):
        _fail("supplied output URI inventory differs from capture plan")
    if publication_transport.expected_write_uris != tuple(inventory["uris"]):
        _fail("concrete transport capability differs from output inventory")
    if reopened_candidate_authority is None:
        try:
            reopened = (
                candidate_authority.reopen_fixed_g0_candidate_authority_release_v1(
                    candidate_authority_root_identity,
                    repository_root=repository_root,
                    read_exact=cache.read,
                    git_head=git_head,
                    git_blob=git_blob,
                    git_status=git_status,
                )
            )
        except Exception as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
                f"candidate-authority one-time replay failed: {exc}"
            ) from exc
    else:
        if (
            type(reopened_candidate_authority)
            is not candidate_authority.ReopenedFixedG0CandidateAuthorityV1
            or reopened_candidate_authority.root_identity
            != _identity(
                candidate_authority_root_identity,
                label="preflight candidate-authority root",
            )
        ):
            _fail("preflight candidate-authority replay differs")
        reopened = reopened_candidate_authority
    plan = _validate_plan_with_cached_authority(
        capture_plan,
        reopened=reopened,
        adapter_final_release_lock_commit_sha=adapter_final_release_lock_commit_sha,
        adapter_final_release_lock_raw=adapter_final_release_lock_raw,
        fixed_g0_replay_receipt=fixed_g0_replay_receipt,
        fixed_g0_replay_receipt_identity=fixed_g0_replay_receipt_identity,
        catalog_release=catalog_release,
        catalog_release_identity=catalog_release_identity,
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
    )
    if (
        plan["fixed_g0_candidate_authority_root_identity"]
        != reopened.root_identity
    ):
        _fail("capture plan uses a different candidate-authority root")
    plan_binding = _validate_capture_plan_binding(
        plan=plan,
        capture_plan_binding=capture_plan_binding,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    operator_identity, operator_binding = _validate_code_identity(
        operator_code_identity,
        expected_path=operator_v2.OPERATOR_MODULE_PATH,
        repair_sha256=operator_repair_sha256,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    _, orchestrator_binding = _validate_code_identity(
        orchestrator_code_identity,
        expected_path=BATCH_MODULE_PATH,
        repair_sha256=orchestrator_repair_sha256,
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    dependency_closure = _replay_executed_dependency_closure(
        expected_commit_sha=plan_binding["commit_sha"],
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    _validate_plan_code_against_dependency_closure_v1(
        plan=plan, dependency_closure=dependency_closure
    )
    retained_capture_replay = _normalize_capture_plan_git_replay_v1(
        capture_plan_git_replay,
        plan=plan,
        capture_plan_binding=plan_binding,
    )
    retained_runtime = (
        _build_loaded_runtime_attestation_v1(
            dependency_closure=dependency_closure
        )
        if runtime_attestation is None
        else _normalize_runtime_attestation_v1(
            runtime_attestation, dependency_closure=dependency_closure
        )
    )
    component_result = _publish_component_with_cached_authority(
        reopened=reopened,
        candidate_authority_root_identity=candidate_authority_root_identity,
        producer_id=str(plan["producer_id"]),
        producer_release_id=str(plan["producer_release_id"]),
        producer_namespace=str(plan["producer_namespace"]),
        fixed_g0_replay_receipt=fixed_g0_replay_receipt,
        fixed_g0_replay_receipt_identity=fixed_g0_replay_receipt_identity,
        catalog_release=catalog_release,
        catalog_release_identity=catalog_release_identity,
        structural_catalogs=structural_catalogs,
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
        producer_code_identity=plan["component_producer_code_identity"],
        publish_create_once=publish_create_once,
        read_exact=cache.read,
    )
    component_receipt = _validate_component_receipt_with_cached_authority(
        component_result["publication_receipt"],
        reopened=reopened,
        plan=plan,
    )
    reopened_component_receipt, component_receipt_identity = _publish_json(
        component_receipt,
        uri=f"{prefix}{COMPONENT_RECEIPT_FILENAME}",
        publish_create_once=publish_create_once,
        read_exact=cache.read,
        label="component publication receipt",
    )
    if (
        _validate_component_receipt_with_cached_authority(
            reopened_component_receipt,
            reopened=reopened,
            plan=plan,
        )
        != component_receipt
    ):
        _fail("component publication receipt exact reopen differs")
    panel = component_result["component_publication_result"]["offline_panel"]
    candidate_entries = _sequence(
        reopened.candidate_release["entries"], label="candidate entries"
    )
    component_entries = _sequence(panel["entries"], label="component entries")
    bundles = _sequence(panel["input_bundles"], label="component bundles")
    bundle_ids = _sequence(
        panel["input_bundle_identities"], label="component bundle identities"
    )
    producer_receipts = _sequence(
        panel["producer_receipts"], label="component producer receipts"
    )
    producer_receipt_ids = _sequence(
        panel["producer_receipt_identities"],
        label="component producer receipt identities",
    )
    plan_tasks = _sequence(plan["source_task_bindings"], label="capture-plan tasks")
    groups = (
        candidate_entries, component_entries, bundles, bundle_ids,
        producer_receipts, producer_receipt_ids, list(structural_catalogs),
        plan_tasks,
    )
    if any(len(group) != source.TASK_COUNT for group in groups):
        _fail("batch inputs do not form one exact 54-task lattice")
    triples: list[dict[str, object]] = []
    members: list[dict[str, object]] = []
    member_identities: list[dict[str, object]] = []
    candidate_root_sha = _digest(
        reopened.root["candidate_authority_release_sha256"],
        label="candidate-authority root SHA",
    )
    for ordinal in range(source.TASK_COUNT):
        candidate_entry = _mapping(
            candidate_entries[ordinal], label=f"candidate entry[{ordinal}]"
        )
        slate_id = str(candidate_entry["slate"]["slate_id"])
        task_prefix = f"{prefix}source-task-{ordinal:02d}-{slate_id}/"
        try:
            triple = operator_v2.publish_matchup_source_triple_v2(
                source_task_ordinal=ordinal,
                output_prefix=task_prefix,
                capture_plan_binding=plan_binding,
                operator_code_identity=operator_identity,
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
                read_exact=cache.read,
            )
        except operator_v2.CorpusR6MatchupSourceOperatorV2Error as exc:
            raise CorpusR6MatchupBatchCandidateAuthorityV1Error(str(exc)) from exc
        member = _batch_member(
            ordinal=ordinal,
            candidate_root_identity=reopened.root_identity,
            candidate_root_sha256=candidate_root_sha,
            capture_plan_task=plan_tasks[ordinal],
            candidate_entry=candidate_entry,
            component_entry=component_entries[ordinal],
            triple=triple,
        )
        reopened_member, member_identity = _publish_json(
            member,
            uri=f"{task_prefix}batch-member.json",
            publish_create_once=publish_create_once,
            read_exact=cache.read,
            label=f"batch member[{ordinal}]",
        )
        validate_batch_member_v1(reopened_member, expected_ordinal=ordinal)
        triples.append(triple)
        members.append(member)
        member_identities.append(member_identity)
    pre_source_root_closure = _replay_executed_dependency_closure(
        expected_commit_sha=plan_binding["commit_sha"],
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if pre_source_root_closure != dependency_closure:
        _fail("executed dependency closure changed before source-root publication")
    source_root_uri = f"{prefix}{release_v2.ROOT_FILENAME}"
    receipt_uri = str(inventory["publication_work_receipt_uri"])
    terminal_uri = str(inventory["terminal_root_uri"])
    pre_source_completed = [
        uri for uri in inventory["uris"]
        if uri not in {source_root_uri, receipt_uri, terminal_uri}
    ]
    publication_transport.require_completed_exactly_v1(
        completed_uris=pre_source_completed,
        pending_uris=[source_root_uri, receipt_uri, terminal_uri],
    )
    source_release_result = _publish_terminal_source_release_with_cached_authority(
        reopened=reopened,
        component_result=component_result,
        release_id=run_id,
        namespace=prefix,
        capture_plan_binding=plan_binding,
        triples=triples,
        publish_create_once=publish_create_once,
        read_exact=cache.read,
    )
    expected_preterminal = [
        uri for uri in inventory["uris"] if uri not in {receipt_uri, terminal_uri}
    ]
    publication_transport.require_completed_exactly_v1(
        completed_uris=expected_preterminal,
        pending_uris=[receipt_uri, terminal_uri],
    )
    budget_snapshot = publication_transport.write_budget_receipt()
    publication_work_receipt = _build_publication_work_receipt_v1(
        source_commit_sha=str(plan_binding["commit_sha"]),
        output_uri_inventory=inventory,
        transport_budget_snapshot=budget_snapshot,
    )
    reopened_work_receipt, publication_work_receipt_identity = _publish_json(
        publication_work_receipt,
        uri=receipt_uri,
        publish_create_once=publish_create_once,
        read_exact=cache.read,
        label="publication work receipt",
    )
    if reopened_work_receipt != publication_work_receipt:
        _fail("publication work receipt exact reopen differs")
    completed_before_terminal = [
        uri for uri in inventory["uris"] if uri != terminal_uri
    ]
    publication_transport.require_completed_exactly_v1(
        completed_uris=completed_before_terminal,
        pending_uris=[terminal_uri],
    )
    pre_batch_root_closure = _replay_executed_dependency_closure(
        expected_commit_sha=plan_binding["commit_sha"],
        repository_root=repository_root,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if pre_batch_root_closure != dependency_closure:
        _fail("executed dependency closure changed before batch-root publication")
    batch_root = _build_batch_root(
        run_id=run_id,
        prefix=prefix,
        reopened=reopened,
        plan=plan,
        capture_plan_binding=plan_binding,
        capture_plan_git_replay=retained_capture_replay,
        dependency_closure=dependency_closure,
        runtime_attestation=retained_runtime,
        output_uri_inventory=inventory,
        publication_work_receipt=publication_work_receipt,
        publication_work_receipt_identity=publication_work_receipt_identity,
        component_receipt=component_receipt,
        component_receipt_identity=component_receipt_identity,
        producer_release=panel["producer_release"],
        producer_release_identity=panel["producer_release_identity"],
        source_release=source_release_result["release"],
        source_release_identity=source_release_result["release_identity"],
        member_identities=member_identities,
        members=members,
        orchestrator_code_binding=orchestrator_binding,
        operator_code_binding=operator_binding,
    )
    # This is intentionally the final create-once request in the invocation.
    reopened_root, batch_root_identity = _publish_json(
        batch_root,
        uri=f"{prefix}{ROOT_FILENAME}",
        publish_create_once=publish_create_once,
        read_exact=cache.read,
        label="terminal matchup source batch root",
    )
    validated_root = validate_batch_release_structure_v1(reopened_root)
    if validated_root != batch_root:
        _fail("terminal batch root exact reopen differs")
    publication_transport.require_completed_exactly_v1(
        completed_uris=inventory["uris"], pending_uris=[]
    )
    return {
        "batch_release": batch_root,
        "batch_release_identity": batch_root_identity,
        "source_release_identity": source_release_result["release_identity"],
        "result_panel": {
            "run_id": run_id,
            "task_count": source.TASK_COUNT,
            "total_candidate_count": batch_root["total_candidate_count"],
            "total_annotation_row_count": batch_root[
                "total_annotation_row_count"
            ],
            "member_descriptors": batch_root["members"],
            "source_release_identity": source_release_result[
                "release_identity"
            ],
            "batch_release_identity": batch_root_identity,
            "candidate_authority_full_replay_count": 1,
            "exact_read_unique_object_count": cache.unique_object_count,
            "exact_read_cache_hit_count": cache.hit_count,
            "exact_read_cache_current_bytes": cache.cached_bytes,
            "exact_read_cache_byte_limit": cache.max_cached_bytes,
            "exact_read_cache_eviction_count": cache.eviction_count,
            "exact_read_cache_oversize_bypass_count": (
                cache.oversize_bypass_count
            ),
            "exact_read_budget_receipt": cache.budget_receipt(),
            "create_once_write_budget_receipt": (
                publication_transport.write_budget_receipt()
            ),
            "outcome_columns_read": [],
            "uses_realized_outcomes": False,
        },
    }


def reopen_matchup_source_batch_candidate_authority_v1(
    *,
    batch_release_identity: Mapping[str, object],
) -> dict[str, object]:
    """Deep-reopen through the sole clean tracked plan and real Git checkout.

    Callers choose the batch root to inspect, but cannot choose the candidate
    authority, capture plan, repository, Git answers, or code identities used
    to grant authority.  Those bindings are reconstructed from the terminal
    root and the fixed tracked plan with the code-owned Git adapters.
    """
    root = _trusted_repository_root_v1()
    _plan, _binding, _git_replay, _final_raw = _trusted_capture_plan_lock_v1()
    transport = _trusted_gcs_transport_v1(expected_write_uris=())
    result = _reopen_matchup_source_batch_candidate_authority_with_adapters_v1(
        batch_release_identity=batch_release_identity,
        repository_root=root,
        read_exact=transport.read_exact,
        git_head=_trusted_git_head_v1,
        git_blob=_trusted_git_blob_v1,
        git_status=_trusted_git_status_v1,
    )
    result["gcs_transport_read_budget_receipt"] = (
        transport.read_budget_receipt()
    )
    current_runtime = _build_loaded_runtime_attestation_v1(
        dependency_closure=result["batch_release"][
            "executed_dependency_closure"
        ]
    )
    result["current_validator_runtime_attestation"] = current_runtime
    result["publisher_runtime_revalidation"] = (
        _revalidate_publisher_runtime_with_current_v1(
            publisher_attestation=result["batch_release"][
                "loaded_runtime_attestation"
            ],
            current_attestation=current_runtime,
            dependency_closure=result["batch_release"][
                "executed_dependency_closure"
            ],
        )
    )
    return result


def publish_matchup_source_batch_candidate_authority_v1(
    *,
    run_id: str,
) -> dict[str, object]:
    """Publish from the sole clean tracked plan and its already-existing root.

    The fixed capture-plan lock is loaded from clean current HEAD through a
    no-follow worktree read and an immutable Git-blob comparison.  Its pinned
    candidate-authority root is then generation-exact reopened and fully
    replayed before any output publication.  The candidate root must already
    exist; this function has no candidate builder, fallback, or caller-selected
    identity seam.

    Partial create-once prefixes are resumable only by returning the existing
    generation and proving byte equality on exact reopen.  A different-byte
    collision fails before a dependent object or terminal batch root is made.
    """
    if os.environ.get(PUBLISH_ENABLE_ENV) != "1":
        _fail(f"publication is default-off; set {PUBLISH_ENABLE_ENV}=1")
    plan, binding, git_replay, final_lock_raw = _trusted_capture_plan_lock_v1()
    root = _trusted_repository_root_v1()
    dependency_closure = _replay_executed_dependency_closure(
        expected_commit_sha=binding["commit_sha"],
        repository_root=root,
        git_head=_trusted_git_head_v1,
        git_blob=_trusted_git_blob_v1,
        git_status=_trusted_git_status_v1,
    )
    _validate_plan_code_against_dependency_closure_v1(
        plan=plan, dependency_closure=dependency_closure
    )
    runtime_attestation = _build_loaded_runtime_attestation_v1(
        dependency_closure=dependency_closure
    )
    operator_identity = _derive_clean_head_code_identity_v1(
        expected_path=operator_v2.OPERATOR_MODULE_PATH,
        repository_root=root,
        git_head=_trusted_git_head_v1,
        git_blob=_trusted_git_blob_v1,
        git_status=_trusted_git_status_v1,
    )
    orchestrator_identity = _derive_clean_head_code_identity_v1(
        expected_path=BATCH_MODULE_PATH,
        repository_root=root,
        git_head=_trusted_git_head_v1,
        git_blob=_trusted_git_blob_v1,
        git_status=_trusted_git_status_v1,
    )
    inventory = _output_uri_inventory_v1(run_id=run_id, plan_value=plan)
    # Use a write-incapable client to exact-open the entire remote authority
    # graph before the exact output capability is even constructed.
    preflight_transport = _trusted_gcs_transport_v1(expected_write_uris=())
    prerequisites = _trusted_remote_prerequisites_v1(
        plan=plan, read_exact=preflight_transport.read_exact
    )
    try:
        preflight_authority = (
            candidate_authority.reopen_fixed_g0_candidate_authority_release_v1(
                plan["fixed_g0_candidate_authority_root_identity"],
                repository_root=root,
                read_exact=preflight_transport.read_exact,
                git_head=_trusted_git_head_v1,
                git_blob=_trusted_git_blob_v1,
                git_status=_trusted_git_status_v1,
            )
        )
    except Exception as exc:
        raise CorpusR6MatchupBatchCandidateAuthorityV1Error(
            f"pre-write candidate authority replay failed: {exc}"
        ) from exc
    _validate_plan_with_cached_authority(
        plan,
        reopened=preflight_authority,
        adapter_final_release_lock_commit_sha=str(
            plan["adapter_final_release_lock_binding"]["commit_sha"]
        ),
        adapter_final_release_lock_raw=final_lock_raw,
        fixed_g0_replay_receipt=prerequisites["fixed_g0_replay_receipt"],
        fixed_g0_replay_receipt_identity=prerequisites[
            "fixed_g0_replay_receipt_identity"
        ],
        catalog_release=prerequisites["catalog_release"],
        catalog_release_identity=prerequisites["catalog_release_identity"],
        upstream_source_release=prerequisites["upstream_source_release"],
        upstream_source_release_identity=prerequisites[
            "upstream_source_release_identity"
        ],
        upstream_pack_row_objects=prerequisites["upstream_pack_row_objects"],
    )
    transport = _trusted_gcs_transport_v1(
        expected_write_uris=inventory["uris"]
    )
    result = _publish_matchup_source_batch_candidate_authority_with_adapters_v1(
        run_id=run_id,
        candidate_authority_root_identity=plan[
            "fixed_g0_candidate_authority_root_identity"
        ],
        capture_plan=plan,
        capture_plan_binding=binding,
        capture_plan_git_replay=git_replay,
        adapter_final_release_lock_commit_sha=(
            str(plan["adapter_final_release_lock_binding"]["commit_sha"])
        ),
        adapter_final_release_lock_raw=final_lock_raw,
        fixed_g0_replay_receipt=prerequisites["fixed_g0_replay_receipt"],
        fixed_g0_replay_receipt_identity=prerequisites[
            "fixed_g0_replay_receipt_identity"
        ],
        catalog_release=prerequisites["catalog_release"],
        catalog_release_identity=prerequisites["catalog_release_identity"],
        structural_catalogs=prerequisites["structural_catalogs"],
        upstream_source_release=prerequisites["upstream_source_release"],
        upstream_source_release_identity=prerequisites[
            "upstream_source_release_identity"
        ],
        upstream_pack_row_objects=prerequisites["upstream_pack_row_objects"],
        operator_code_identity=operator_identity,
        orchestrator_code_identity=orchestrator_identity,
        repository_root=root,
        git_head=_trusted_git_head_v1,
        git_blob=_trusted_git_blob_v1,
        git_status=_trusted_git_status_v1,
        publish_create_once=transport.publish_create_once,
        read_exact=transport.read_exact,
        output_uri_inventory=inventory,
        publication_transport=transport,
        reopened_candidate_authority=preflight_authority,
        runtime_attestation=runtime_attestation,
    )
    result["gcs_transport_read_budget_receipt"] = (
        transport.read_budget_receipt()
    )
    result["gcs_preflight_read_budget_receipt"] = (
        preflight_transport.read_budget_receipt()
    )
    result["gcs_transport_write_budget_receipt"] = (
        transport.write_budget_receipt()
    )
    return result


def validate_matchup_source_batch_candidate_authority_v1() -> dict[str, object]:
    """Local, outcome-blind validation with no cloud client or write capability."""
    plan, binding, git_replay, _final_raw = _trusted_capture_plan_lock_v1()
    root = _trusted_repository_root_v1()
    dependency_closure = _replay_executed_dependency_closure(
        expected_commit_sha=binding["commit_sha"],
        repository_root=root,
        git_head=_trusted_git_head_v1,
        git_blob=_trusted_git_blob_v1,
        git_status=_trusted_git_status_v1,
    )
    _validate_plan_code_against_dependency_closure_v1(
        plan=plan, dependency_closure=dependency_closure
    )
    runtime = _build_loaded_runtime_attestation_v1(
        dependency_closure=dependency_closure
    )
    return {
        "capture_plan_binding": binding,
        "capture_plan_git_replay": git_replay,
        "executed_dependency_closure": dependency_closure,
        "loaded_runtime_attestation": runtime,
        "caller_supplied_final_lock_bytes_allowed": False,
        "same_commit_recovery_required": True,
        "cloud_client_constructed": False,
        "cloud_write_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }


__all__ = [
    "BATCH_MEMBER_SCHEMA",
    "BATCH_MODULE_PATH",
    "BATCH_RELEASE_SCHEMA",
    "COMPONENT_RECEIPT_FILENAME",
    "CAPTURE_PLAN_GIT_REPLAY_SCHEMA",
    "CREATE_ONCE_BUDGET_SCHEMA",
    "CREATE_ONCE_RESUME_POLICY",
    "CorpusR6MatchupBatchCandidateAuthorityV1Error",
    "DEPENDENCY_CLOSURE_SCHEMA",
    "EXACT_READ_BUDGET_SCHEMA",
    "EXECUTED_DEPENDENCY_MODULE_PATHS",
    "FORBIDDEN_GCS_ENDPOINT_ENV_VARS",
    "IMAGE_DIGEST_ENV",
    "IMAGE_REFERENCE_ENV",
    "IMAGE_SOURCE_COMMIT_ENV",
    "ExactReadCacheV1",
    "GenerationPinnedGCSBatchTransportV1",
    "OUTPUT_BUCKET",
    "OUTPUT_NAMESPACE",
    "OUTPUT_URI_INVENTORY_SCHEMA",
    "PUBLICATION_WORK_RECEIPT_FILENAME",
    "PUBLICATION_WORK_RECEIPT_SCHEMA",
    "PUBLICATION_MODE",
    "PUBLISH_ENABLE_ENV",
    "PRODUCTION_PROJECT",
    "PRODUCTION_GCS_API_ENDPOINT",
    "PRODUCTION_GCS_UNIVERSE_DOMAIN",
    "REPOSITORY_ROOT",
    "ROOT_FILENAME",
    "RUNTIME_ATTESTATION_SCHEMA",
    "canonical_json_bytes",
    "canonical_sha256",
    "output_prefix_for_run_v1",
    "publish_matchup_source_batch_candidate_authority_v1",
    "reopen_matchup_source_batch_candidate_authority_v1",
    "validate_matchup_source_batch_candidate_authority_v1",
    "validate_batch_member_v1",
    "validate_batch_release_structure_v1",
]
