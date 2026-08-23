#!/usr/bin/env python3
"""Prepare the default-off corpus-parametric batch foundation.

This is a score-free, outcome-blind preparer.  It translates one accepted,
generation-pinned retrieval task-0 terminal into the prerequisite consumed by
``run_corpus_parametric_transport.py``; replays the complete 54-slate/270-NPZ
source-authority publication without LIST; registers immutable common law; and
publishes either an independent one-task smoke foundation or the complete
54-task production manifest and evidence contract.

The batch output namespace deliberately contains only the batch manifest and
evidence contract.  Every preparer-owned object is written under a separate
``corpus-parametric-research`` foundation namespace.  All writes are
create-only.  A partial namespace is terminal and cannot be resumed or
replaced.  No function in this module reads outcomes, launches compute, fills
the corpus, mutates a graph, or changes production policy.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Final, Protocol


ROOT: Final = Path(__file__).resolve().parents[1]
SRC: Final = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nfl_dfs.research import corpus_artifact_source_authority as source_authority  # noqa: E402
from nfl_dfs.research import corpus_batch_evidence_contract as evidence  # noqa: E402
from nfl_dfs.research import corpus_legal_feasibility as legal  # noqa: E402
from nfl_dfs.research import corpus_parametric_batch as batch  # noqa: E402
from nfl_dfs.research import corpus_retrieval_engine as retrieval  # noqa: E402
from nfl_dfs.research import effective_policy_rule_inventory as policy_inventory  # noqa: E402
from nfl_dfs.research import lr8_later_period_source as later  # noqa: E402
from nfl_dfs.research import residual_world_columns as rw  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
ENABLE_ENV: Final = "CORPUS_PARAMETRIC_BATCH_PREPARER_ENABLED"
PREPLAN_SCHEMA: Final = "corpus-parametric-batch-preplan/v1"
PREFIX_CLAIM_SCHEMA: Final = "corpus-parametric-foundation-prefix-claim/v1"
PUBLICATION_SCHEMA: Final = "corpus-parametric-foundation-publication/v1"
RETRIEVAL_PREREQUISITE_SCHEMA: Final = (
    "corpus-retrieval-task0-accepted-prerequisite/v1"
)
WORKSTREAM: Final = "corpus-parametric-research"
RESERVED_POPULATION_WORKSTREAM: Final = "corpus-population-research"
PRODUCTION_TASK_COUNT: Final = 54
# Exactly three production lattices are legal: the full 54-slate batch,
# and the two v7 half-batch lanes (source tasks 0-27 and 28-53) that run
# concurrently on two reused jobs. Enumerated forms, never arbitrary
# subsets — the lane split is a fixed design choice, not a tunable.
PRODUCTION_TASK_LATTICES: Final = (
    tuple(range(PRODUCTION_TASK_COUNT)),
    tuple(range(0, 28)),
    tuple(range(28, PRODUCTION_TASK_COUNT)),
)
SMOKE_TASK_COUNT: Final = 1
ARTIFACT_COUNT: Final = 270
WORLD_SCHEDULE_SCHEMA: Final = "corpus-ranked-world-schedule/v1"
MAX_JSON_BYTES: Final = 512 * 1024 * 1024

COMMON_LAW_ROLES: Final = (
    "code_source",
    "world_schedule",
    "objective",
    "generator_families",
    "unique_fill",
    "deduplication",
    "admission",
    "cbwu",
    "selector",
    "line_194",
    "exact_80",
)
MECHANISM_ROLES: Final = COMMON_LAW_ROLES[2:]
QUERY_ROLES: Final = (
    "r0_candidates", "artifact_catalog", "salary_player_ids",
)

_SHA = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_BUILD = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}"
)
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_ID = re.compile(r"[a-z0-9][a-z0-9._:-]{2,159}")
_RETRIEVAL_TERMINAL_KEYS: Final = frozenset({
    "schema_version", "finished_at_utc", "execution_contract", "prefix_claim",
    "runtime_iam_evidence", "launch_intent", "launch_ledger",
    "execution_name_ledger", "execution", "suite_manifest_identity",
    "snapshot_manifest_identity", "task_index", "task_id", "result_object",
    "task_result_sha256", "batch_completion", "batch_completion_sha256",
    "post_terminal_job", "output_inventory_before_terminal",
    "output_inventory_before_terminal_sha256", "one_execution", "attempt_zero",
    "retry_count", "generation_pinned_replay",
    "successful_deployment_remains_parked", "uses_realized_outcomes",
    "bigquery_access_licensed", "corpus_fill_licensed",
    "live_policy_access_licensed", "production_change_licensed",
    "terminal_receipt_sha256",
})
_TERMINAL_GOVERNANCE_FIELDS: Final = (
    "execution_contract", "prefix_claim", "runtime_iam_evidence",
    "launch_intent", "launch_ledger", "execution_name_ledger",
)


class CorpusParametricPreparationError(RuntimeError):
    """The immutable batch foundation failed closed."""


class ObjectStore(Protocol):
    """Exact-name, generation-aware object boundary; deliberately no LIST."""

    def read(self, identity: Mapping[str, object]) -> bytes: ...

    def resolve_optional(
        self, uri: str,
    ) -> tuple[dict[str, object], bytes] | None: ...

    def publish(
        self, uri: str, raw: bytes, media_type: str = "application/json",
    ) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class SourceFoundation:
    publication_identity: dict[str, object]
    publication: dict[str, object]
    completion_identity: dict[str, object]
    completion: dict[str, object]
    source_freeze_identity: dict[str, object]
    source_freeze: dict[str, object]
    task_rows: tuple[dict[str, object], ...]
    schedule_rows: tuple[dict[str, object], ...]
    exact_artifact_get_count: int


def canonical_json_bytes(value: object) -> bytes:
    """Canonical JSON used by the preparer (no trailing newline)."""
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusParametricPreparationError(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _transport_json_bytes(value: object) -> bytes:
    """Freeze the transport consumer's newline-terminated JSON contract."""
    return canonical_json_bytes(value) + b"\n"


def _transport_sha256(value: object) -> str:
    return sha256(_transport_json_bytes(value)).hexdigest()


def _duplicate_safe(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CorpusParametricPreparationError(
                f"canonical JSON repeats key {key!r}"
            )
        result[key] = value
    return result


def parse_canonical_json_bytes(
    raw: bytes, *, label: str, trailing_newline: bool = False,
) -> object:
    if type(raw) is not bytes or not raw or len(raw) > MAX_JSON_BYTES:
        raise CorpusParametricPreparationError(f"{label} bytes differ")
    expected_raw = raw[:-1] if trailing_newline and raw.endswith(b"\n") else raw
    if trailing_newline and not raw.endswith(b"\n"):
        raise CorpusParametricPreparationError(f"{label} newline differs")
    try:
        value = json.loads(
            expected_raw.decode("utf-8"), object_pairs_hook=_duplicate_safe,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CorpusParametricPreparationError(
                    f"{label} contains non-finite {value}"
                )
            ),
        )
    except CorpusParametricPreparationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusParametricPreparationError(
            f"{label} is not valid JSON"
        ) from exc
    rebuilt = _transport_json_bytes(value) if trailing_newline else canonical_json_bytes(value)
    if rebuilt != raw:
        raise CorpusParametricPreparationError(f"{label} is not canonical JSON")
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusParametricPreparationError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if type(value) is not list:
        raise CorpusParametricPreparationError(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        raise CorpusParametricPreparationError(f"{label} fields differ")


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        raise CorpusParametricPreparationError(f"{label} must be nonempty text")
    return value


def _timestamp(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _UTC.fullmatch(result) is None:
        raise CorpusParametricPreparationError(f"{label} must be UTC seconds")
    try:
        datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise CorpusParametricPreparationError(f"{label} differs") from exc
    return result


def _gcs_prefix(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    tail = result.removeprefix("gs://")
    bucket_name, marker, object_name = tail.partition("/")
    if (
        not result.startswith("gs://") or not bucket_name or not marker
        or not object_name or not result.endswith("/") or "//" in object_name
        or any(token in result for token in ("\\", "?", "#", "\0"))
    ):
        raise CorpusParametricPreparationError(f"{label} must be a GCS prefix")
    return result


def normalize_identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusParametricPreparationError(f"{label} differs") from exc


def identity_for_bytes(uri: str, generation: str, raw: bytes) -> dict[str, object]:
    return normalize_identity({
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }, label="object identity")


def _read_exact(
    storage: ObjectStore, identity: object, *, label: str,
) -> tuple[dict[str, object], bytes]:
    normalized = normalize_identity(identity, label=label)
    raw = storage.read(normalized)
    if type(raw) is not bytes or (
        len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        raise CorpusParametricPreparationError(f"{label} retained bytes differ")
    return normalized, raw


def _publish_exact(
    storage: ObjectStore, uri: str, raw: bytes, *, label: str,
) -> dict[str, object]:
    identity = normalize_identity(
        storage.publish(uri, raw, "application/json"), label=f"{label} publish",
    )
    if identity["uri"] != uri:
        raise CorpusParametricPreparationError(f"{label} publish URI differs")
    reopened_identity, reopened = _read_exact(storage, identity, label=label)
    if reopened != raw:
        raise CorpusParametricPreparationError(f"{label} reopen differs")
    return reopened_identity


def _self_hashed(
    body: Mapping[str, object], *, field: str, transport: bool = False,
) -> dict[str, object]:
    if field in body:
        raise CorpusParametricPreparationError("self-hash field already exists")
    digest = _transport_sha256(body) if transport else canonical_sha256(body)
    return {**body, field: digest}


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
    transport: bool = False,
) -> None:
    retained = value.get(field)
    if type(retained) is not str or _SHA.fullmatch(retained) is None:
        raise CorpusParametricPreparationError(f"{label} self-hash differs")
    body = {key: value[key] for key in value if key != field}
    actual = _transport_sha256(body) if transport else canonical_sha256(body)
    if actual != retained:
        raise CorpusParametricPreparationError(f"{label} self-hash differs")


def solver_probe() -> dict[str, object]:
    """Return the exact CBC authority from this client-free runtime."""
    try:
        authority = legal._cbc_runtime_authority()
        return batch._normalize_solver(authority)
    except Exception as exc:
        raise CorpusParametricPreparationError(
            "runtime CBC authority cannot be established"
        ) from exc


_PREPLAN_KEYS: Final = frozenset({
    "schema_version", "mode", "workstream", "foundation_id", "batch_id",
    "created_at_utc", "accepted_at_utc", "foundation_prefix",
    "batch_output_prefix", "retrieval_terminal_identity",
    "source_publication_completion_identity", "source_task_indexes",
    "code_source", "solver", "world_seed", "publish_task_requests",
    "default_off", "outcome_columns_read", "uses_realized_outcomes",
    "historical_scoring_licensed", "corpus_fill_licensed",
    "live_strategy_authority", "production_change_licensed", "preplan_sha256",
})


def validate_preplan(
    value: object, *, repository_root: Path = ROOT,
    solver_probe_fn: Callable[[], Mapping[str, object]] = solver_probe,
) -> dict[str, object]:
    """Validate all local/configuration authority before any storage write."""
    item = dict(_mapping(value, label="parametric preplan"))
    _exact_keys(item, _PREPLAN_KEYS, label="parametric preplan")
    _validate_self_hash(item, field="preplan_sha256", label="parametric preplan")
    mode = _string(item["mode"], label="preplan mode")
    if mode not in {"production", "smoke"}:
        raise CorpusParametricPreparationError("preplan mode differs")
    foundation_id = _string(item["foundation_id"], label="foundation id")
    batch_id = _string(item["batch_id"], label="batch id")
    if _ID.fullmatch(foundation_id) is None or _ID.fullmatch(batch_id) is None:
        raise CorpusParametricPreparationError("preplan ID differs")
    marker = "production" if mode == "production" else "smoke"
    if marker not in foundation_id or marker not in batch_id:
        raise CorpusParametricPreparationError(
            "mode must be explicit in foundation and batch IDs"
        )
    foundation_prefix = _gcs_prefix(
        item["foundation_prefix"], label="foundation prefix"
    )
    output_prefix = _gcs_prefix(
        item["batch_output_prefix"], label="batch output prefix"
    )
    if (
        not foundation_prefix.endswith(f"/{foundation_id}/")
        or not output_prefix.endswith(f"/{batch_id}/")
        or foundation_prefix.startswith(output_prefix)
        or output_prefix.startswith(foundation_prefix)
        or WORKSTREAM not in foundation_prefix
        or WORKSTREAM not in output_prefix
        or RESERVED_POPULATION_WORKSTREAM in foundation_prefix
        or RESERVED_POPULATION_WORKSTREAM in output_prefix
    ):
        raise CorpusParametricPreparationError(
            "preparer and batch namespaces are not independent parametric research"
        )
    indexes_raw = _sequence(item["source_task_indexes"], label="source task indexes")
    indexes = list(indexes_raw)
    allowed = (
        PRODUCTION_TASK_LATTICES if mode == "production" else ([0],)
    )
    if indexes not in [list(rows) for rows in allowed] or any(
        type(index) is not int for index in indexes
    ):
        raise CorpusParametricPreparationError(
            f"{mode} source task lattice differs"
        )
    code_source = dict(_mapping(item["code_source"], label="code source"))
    image = batch.normalize_image_identity(
        code_source.get("immutable_image"), label="preplan immutable image"
    )
    if (
        type(code_source.get("source_commit_sha")) is not str
        or _COMMIT.fullmatch(str(code_source["source_commit_sha"])) is None
        or type(code_source.get("cloud_build_id")) is not str
        or _BUILD.fullmatch(str(code_source["cloud_build_id"])) is None
    ):
        raise CorpusParametricPreparationError("code/build identity differs")
    try:
        normalized_code, _ = legal._validate_code_source_body(
            code_source, repository_root=repository_root, immutable_image=image,
        )
    except Exception as exc:
        raise CorpusParametricPreparationError(
            "preplan code/image/build bytes drifted"
        ) from exc
    try:
        retained_solver = batch._normalize_solver(item["solver"])
        runtime_solver = batch._normalize_solver(solver_probe_fn())
    except Exception as exc:
        raise CorpusParametricPreparationError("preplan solver differs") from exc
    if retained_solver != runtime_solver:
        raise CorpusParametricPreparationError(
            "preplan CBC authority differs from immutable runtime"
        )
    if (
        item["schema_version"] != PREPLAN_SCHEMA
        or item["workstream"] != WORKSTREAM
        or item["default_off"] is not True
        or item["publish_task_requests"] not in {True, False}
        or type(item["publish_task_requests"]) is not bool
        or type(item["world_seed"]) is not int or item["world_seed"] < 0
        or item["outcome_columns_read"] != []
        or any(item[field] is not False for field in (
            "uses_realized_outcomes", "historical_scoring_licensed",
            "corpus_fill_licensed", "live_strategy_authority",
            "production_change_licensed",
        ))
    ):
        raise CorpusParametricPreparationError("preplan authority differs")
    _timestamp(item["created_at_utc"], label="preplan created timestamp")
    _timestamp(item["accepted_at_utc"], label="retrieval acceptance timestamp")
    item["retrieval_terminal_identity"] = normalize_identity(
        item["retrieval_terminal_identity"], label="retrieval terminal identity"
    )
    item["source_publication_completion_identity"] = normalize_identity(
        item["source_publication_completion_identity"],
        label="source publication completion identity",
    )
    if (
        item["retrieval_terminal_identity"]["uri"]
        == item["source_publication_completion_identity"]["uri"]
    ):
        raise CorpusParametricPreparationError("input authorities overlap")
    item["code_source"] = normalized_code
    item["solver"] = retained_solver
    item["source_task_indexes"] = indexes
    return item


def build_preplan(**values: object) -> dict[str, object]:
    """Convenience builder; validation still requires explicit runtime authority."""
    body = {"schema_version": PREPLAN_SCHEMA, **values}
    return _self_hashed(body, field="preplan_sha256")


def _retrieval_terminal(
    raw: bytes, *, terminal_identity: Mapping[str, object], storage: ObjectStore,
    retrieval_module: ModuleType | object,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    parse = getattr(retrieval_module, "parse_canonical_json_bytes")
    core_bytes = getattr(retrieval_module, "canonical_json_bytes")
    core_sha = getattr(retrieval_module, "canonical_sha256")
    terminal_value = parse(raw, label="retrieval terminal receipt")
    terminal = dict(_mapping(terminal_value, label="retrieval terminal receipt"))
    _exact_keys(terminal, _RETRIEVAL_TERMINAL_KEYS, label="retrieval terminal receipt")
    terminal_body = {
        key: terminal[key] for key in terminal if key != "terminal_receipt_sha256"
    }
    if (
        terminal["schema_version"] != "corpus-retrieval-transport-terminal/v1"
        or terminal["terminal_receipt_sha256"] != core_sha(terminal_body)
        or terminal["task_index"] != 0
        or terminal["one_execution"] is not True
        or terminal["attempt_zero"] is not True
        or terminal["retry_count"] != 0
        or terminal["generation_pinned_replay"] is not True
        or terminal["successful_deployment_remains_parked"] is not True
        or any(terminal[field] is not False for field in (
            "uses_realized_outcomes", "bigquery_access_licensed",
            "corpus_fill_licensed", "live_policy_access_licensed",
            "production_change_licensed",
        ))
    ):
        raise CorpusParametricPreparationError(
            "retrieval terminal is not accepted task-0 success"
        )
    suite_identity = normalize_identity(
        terminal["suite_manifest_identity"], label="retrieval suite identity"
    )
    snapshot_identity = normalize_identity(
        terminal["snapshot_manifest_identity"], label="retrieval snapshot identity"
    )
    result_identity = normalize_identity(
        terminal["result_object"], label="retrieval task result identity"
    )
    completion_identity = normalize_identity(
        terminal["batch_completion"], label="retrieval completion identity"
    )
    identities = (
        terminal_identity, suite_identity, snapshot_identity,
        result_identity, completion_identity,
    )
    if len({normalize_identity(row, label="retrieval identity")["uri"] for row in identities}) != 5:
        raise CorpusParametricPreparationError("retrieval identities overlap")
    _, suite_raw = _read_exact(storage, suite_identity, label="retrieval suite")
    _, snapshot_raw = _read_exact(storage, snapshot_identity, label="retrieval snapshot")
    _, result_raw = _read_exact(storage, result_identity, label="retrieval task result")
    _, completion_raw = _read_exact(
        storage, completion_identity, label="retrieval completion"
    )
    suite = getattr(retrieval_module, "validate_suite_manifest")(
        parse(suite_raw, label="retrieval suite")
    )
    snapshot = getattr(retrieval_module, "validate_snapshot_manifest")(
        parse(snapshot_raw, label="retrieval snapshot")
    )
    if (
        core_bytes(suite) != suite_raw or core_bytes(snapshot) != snapshot_raw
        or len(suite["tasks"]) != 1 or len(snapshot["tasks"]) != 1
        or suite["tasks"][0]["task_index"] != 0
        or snapshot["tasks"][0]["task_index"] != 0
        or suite["snapshot_manifest_identity"] != snapshot_identity
    ):
        raise CorpusParametricPreparationError(
            "retrieval suite/snapshot is not exact task-0 coverage"
        )
    result_value = parse(result_raw, label="retrieval task result")
    result = getattr(retrieval_module, "validate_retrieval_task_result")(
        published_result={
            "authority": result_value, "object_identity": result_identity,
        },
        suite_manifest=suite,
        suite_manifest_identity=suite_identity,
        snapshot_manifest=snapshot,
        snapshot_manifest_identity=snapshot_identity,
        read_object=storage.read,
        replay=True,
    )
    coverage = _mapping(result["coverage"], label="retrieval task coverage")
    expected_result_licenses = {
        "analytics_authority": True,
        "corpus_fill_authority": False,
        "historical_outcome_read_authority": False,
        "live_money_policy_authority": False,
        "production_default_change_authority": False,
    }
    if (
        core_bytes(result) != result_raw
        or result["task_index"] != 0
        or coverage.get("world_count") != 50_000
        or coverage.get("every_unique_lineup_scored_in_every_world") is not True
        or coverage.get("lineup_world_score_count")
        != coverage.get("unique_lineup_count") * coverage.get("world_count")
        or coverage.get("strategy_count") != 4
        or coverage.get("all_strategies_exact_budget") is not True
        or result.get("licenses") != expected_result_licenses
    ):
        raise CorpusParametricPreparationError(
            "retrieval task result lacks complete 50k every-lineup coverage"
        )
    completion_value = parse(completion_raw, label="retrieval completion")
    completion = getattr(
        retrieval_module, "validate_retrieval_batch_completion"
    )(
        completion_value,
        suite_manifest=suite,
        suite_manifest_identity=suite_identity,
        snapshot_manifest=snapshot,
        snapshot_manifest_identity=snapshot_identity,
        published_results=[{
            "authority": result, "object_identity": result_identity,
        }],
        read_object=storage.read,
    )
    expected_completion_licenses = {
        "analytical_graph_projection_ready": True,
        "corpus_fill_authority": False,
        "historical_outcome_read_authority": False,
        "live_money_policy_authority": False,
        "production_default_change_authority": False,
    }
    completion_coverage = _mapping(
        completion["coverage"], label="retrieval completion coverage"
    )
    if (
        core_bytes(completion) != completion_raw
        or completion_coverage.get("task_count") != 1
        or completion_coverage.get("all_tasks_complete") is not True
        or len(completion["task_results"]) != 1
        or completion["task_results"][0]["task_result_object"] != result_identity
        or completion.get("licenses") != expected_completion_licenses
    ):
        raise CorpusParametricPreparationError(
            "retrieval completion lacks exact task-0 coverage"
        )
    execution = _mapping(terminal["execution"], label="retrieval execution")
    counters = _mapping(execution.get("counters"), label="retrieval counters")
    post_job = _mapping(
        terminal["post_terminal_job"], label="retrieval post-terminal job"
    )
    result_execution = _mapping(result["execution"], label="result execution")
    if (
        terminal["suite_manifest_identity"] != suite_identity
        or terminal["snapshot_manifest_identity"] != snapshot_identity
        or terminal["result_object"] != result_identity
        or terminal["batch_completion"] != completion_identity
        or terminal["task_id"] != suite["tasks"][0]["task_id"]
        or terminal["task_result_sha256"] != result["task_result_sha256"]
        or terminal["batch_completion_sha256"]
        != completion["batch_completion_sha256"]
        or execution.get("task_count") != 1
        or execution.get("attempt") != 0
        or execution.get("retry_count") != 0
        or execution.get("state") != "True"
        or counters != {
            "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
        }
        or result_execution.get("execution_id") != execution.get("execution_id")
        or result_execution.get("execution_name") != execution.get("execution_name")
        or result_execution.get("attempt") != 0
        or result_execution.get("retry_count") != 0
        or result_execution.get("mode") != "cloud-run-task"
        or post_job.get("uid") != execution.get("job_uid")
        or post_job.get("generation") != execution.get("job_generation")
        or post_job.get("observed_generation") != post_job.get("generation")
    ):
        raise CorpusParametricPreparationError(
            "retrieval terminal/result execution binding differs"
        )
    _timestamp(terminal["finished_at_utc"], label="retrieval terminal timestamp")
    inventory_rows = _sequence(
        terminal["output_inventory_before_terminal"],
        label="retrieval terminal inventory",
    )
    if terminal["output_inventory_before_terminal_sha256"] != core_sha(list(inventory_rows)):
        raise CorpusParametricPreparationError("retrieval terminal inventory hash differs")
    required = {
        (row["uri"], row["generation"], row["bytes"])
        for row in (suite_identity, result_identity, completion_identity)
    }
    observed: list[tuple[object, object, object]] = []
    for raw_row in inventory_rows:
        row = _mapping(raw_row, label="retrieval terminal inventory row")
        _exact_keys(row, frozenset({"uri", "generation", "bytes"}), label="retrieval inventory row")
        observed.append((row["uri"], row["generation"], row["bytes"]))
    if observed != sorted(observed) or len(observed) != len(set(observed)) or not required.issubset(set(observed)):
        raise CorpusParametricPreparationError("retrieval terminal inventory differs")
    for field in _TERMINAL_GOVERNANCE_FIELDS:
        _read_exact(storage, terminal[field], label=f"retrieval terminal {field}")
    return suite_identity, snapshot_identity, result_identity, completion_identity, result


def bridge_retrieval_task0(
    *, storage: ObjectStore, terminal_identity: object, accepted_at_utc: str,
    retrieval_module: ModuleType | object = retrieval,
) -> tuple[dict[str, object], bytes]:
    """Replay the entire accepted retrieval task-0 graph and translate it."""
    terminal_id, terminal_raw = _read_exact(
        storage, terminal_identity, label="retrieval terminal identity"
    )
    suite_id, snapshot_id, result_id, completion_id, _ = _retrieval_terminal(
        terminal_raw, terminal_identity=terminal_id, storage=storage,
        retrieval_module=retrieval_module,
    )
    body = {
        "schema_version": RETRIEVAL_PREREQUISITE_SCHEMA,
        "accepted_at_utc": _timestamp(
            accepted_at_utc, label="retrieval acceptance timestamp"
        ),
        "task_index": 0,
        "suite_manifest_identity": suite_id,
        "snapshot_manifest_identity": snapshot_id,
        "task_result_object": result_id,
        "terminal_receipt": terminal_id,
        "completion_receipt": completion_id,
        "accepted": True,
        "complete_result": True,
        "partial_result": False,
        "partial_object_count": 0,
        "every_unique_lineup_scored_in_every_world": True,
        "generation_pinned_replay": True,
        "uses_realized_outcomes": False,
        "corpus_fill_licensed": False,
    }
    prerequisite = _self_hashed(
        body, field="acceptance_sha256", transport=True,
    )
    return prerequisite, _transport_json_bytes(prerequisite)


@lru_cache(maxsize=1)
def _source_transport_module() -> ModuleType:
    path = ROOT / "scripts" / "prepare_corpus_artifact_source_authority.py"
    spec = importlib.util.spec_from_file_location(
        "_corpus_artifact_source_transport_for_batch", path
    )
    if spec is None or spec.loader is None:
        raise CorpusParametricPreparationError(
            "source-authority transport module is unavailable"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _parse_source_json(raw: bytes, *, label: str) -> object:
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_duplicate_safe,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CorpusParametricPreparationError(
                    f"{label} contains non-finite {value}"
                )
            ),
        )
    except CorpusParametricPreparationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusParametricPreparationError(f"{label} JSON differs") from exc
    return value


def _schedule_row(
    *, prepared: later.PreparedLaterSlate, local_task_index: int,
    task_row: Mapping[str, object], freeze_sha256: str,
    ranker: Callable[..., Sequence[object]],
) -> dict[str, object]:
    schedule = tuple(ranker(prepared, visits_per_block=legal.VISITS_PER_BLOCK))
    blocks: list[dict[str, object]] = []
    flattened: list[dict[str, object]] = []
    for block_name in rw.WORLD_BLOCKS:
        indices = [
            int(world.index) for world in schedule if world.block == block_name
        ]
        if (
            len(indices) != legal.VISITS_PER_BLOCK
            or len(indices) != len(set(indices))
            or any(index < 0 or index >= rw.WORLDS_PER_BLOCK for index in indices)
        ):
            raise CorpusParametricPreparationError(
                f"world schedule {block_name} dose differs"
            )
        blocks.append({"block": block_name, "world_indices": indices})
        flattened.extend({"block": block_name, "index": index} for index in indices)
    return {
        "task_index": local_task_index,
        "season": task_row["season"],
        "week": task_row["week"],
        "slate_id": task_row["slate_id"],
        "later_source_freeze_manifest_sha256": freeze_sha256,
        "world_artifact_receipt_set_sha256": task_row[
            "world_artifact_receipt_set_sha256"
        ],
        "blocks": blocks,
        "visit_schedule_sha256": legal.canonical_sha256(flattened),
    }


def build_world_schedule(schedule_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Build the exact registered top-200 R0..R4 schedule body."""
    rows = [dict(row) for row in schedule_rows]
    if not rows or [row.get("task_index") for row in rows] != list(range(len(rows))):
        raise CorpusParametricPreparationError("world schedule task lattice differs")
    return {
        "schema": WORLD_SCHEDULE_SCHEMA,
        "method": "top-total-slate-player-draw-desc",
        "score_accumulator": "float64-sum-of-all-slate-player-draws",
        "tie_break": "world-index-ascending-stable",
        "block_order": list(rw.WORLD_BLOCKS),
        "source_worlds_per_block": rw.WORLDS_PER_BLOCK,
        "visits_per_block": legal.VISITS_PER_BLOCK,
        "slates": rows,
    }


def load_source_authority(
    *, storage: ObjectStore, publication_identity: object,
    source_task_indexes: Sequence[int],
    source_transport_module: ModuleType | object | None = None,
    authority_module: ModuleType | object = source_authority,
    later_module: ModuleType | object = later,
    ranker: Callable[..., Sequence[object]] = legal.canonical_visit_schedule,
) -> SourceFoundation:
    """Exact-reopen and replay source publication, captures, and all 270 NPZs."""
    transport = source_transport_module or _source_transport_module()
    publication_id, publication_raw = _read_exact(
        storage, publication_identity, label="source publication completion"
    )
    try:
        publication = getattr(
            transport, "validate_publication_completion_bytes"
        )(publication_raw)
    except Exception as exc:
        raise CorpusParametricPreparationError(
            "source publication completion failed replay"
        ) from exc
    if (
        publication.get("task_count") != PRODUCTION_TASK_COUNT
        or publication.get("artifact_count") != ARTIFACT_COUNT
        or publication.get("artifact_list_used") is not False
        or publication.get("uses_realized_outcomes") is not False
    ):
        raise CorpusParametricPreparationError("source publication scope differs")
    direct_fields = (
        "prefix_claim", "registration_object", "later_source_freeze_object",
        "salary_diagnostic_object", "source_authority_completion_object",
    )
    reopened: dict[str, tuple[dict[str, object], bytes]] = {}
    for field in direct_fields:
        reopened[field] = _read_exact(
            storage, publication[field], label=f"source publication {field}"
        )
    for role in QUERY_ROLES:
        capture = _mapping(
            publication["query_captures"][role], label=f"source capture {role}"
        )
        reopened[f"capture:{role}"] = _read_exact(
            storage, capture["object"], label=f"source capture {role}"
        )
    registration_raw = reopened["registration_object"][1]
    registration_value = _parse_source_json(
        registration_raw, label="source registration"
    )
    try:
        registration = getattr(authority_module, "validate_registration")(
            registration_value
        )
    except Exception as exc:
        raise CorpusParametricPreparationError(
            "source registration failed replay"
        ) from exc
    if getattr(authority_module, "canonical_json_bytes")(registration) != registration_raw:
        raise CorpusParametricPreparationError("source registration bytes differ")
    query_identities = {
        "r0_candidates": registration["source_queries"]["r0_candidates"],
        "artifact_catalog": registration["source_queries"]["artifact_catalog"],
        "salary_player_ids": registration["salary_universe_query"],
    }
    for role in QUERY_ROLES:
        capture_raw = reopened[f"capture:{role}"][1]
        capture_value = getattr(transport, "parse_canonical_json_bytes")(
            capture_raw, label=f"source capture {role}"
        )
        try:
            capture = getattr(transport, "validate_query_capture")(
                capture_value, role=role, query_identity=query_identities[role],
                registered_at=registration["registered_at"],
            )
        except Exception as exc:
            raise CorpusParametricPreparationError(
                f"source capture {role} failed replay"
            ) from exc
        published_capture = publication["query_captures"][role]
        if any(capture[key] != published_capture[key] for key in (
            "row_count", "rows_sha256", "capture_sha256",
        )):
            raise CorpusParametricPreparationError(
                f"source capture {role} publication binding differs"
            )
    source_identity = reopened["later_source_freeze_object"][0]
    source_raw = reopened["later_source_freeze_object"][1]
    source_value = _parse_source_json(source_raw, label="later source freeze")
    try:
        source_freeze = getattr(later_module, "validate_source_freeze")(
            source_value,
            expected_freeze_sha256=publication[
                "later_source_freeze_manifest_sha256"
            ],
        )
    except Exception as exc:
        raise CorpusParametricPreparationError(
            "later-source freeze failed replay"
        ) from exc
    if getattr(later_module, "canonical_json")(source_freeze) != source_raw:
        raise CorpusParametricPreparationError("later-source freeze bytes differ")
    completion_identity = reopened["source_authority_completion_object"][0]
    completion_raw = reopened["source_authority_completion_object"][1]
    try:
        completion = getattr(authority_module, "validate_completion_bytes")(
            completion_raw
        )
    except Exception as exc:
        raise CorpusParametricPreparationError(
            "source-authority completion failed replay"
        ) from exc
    if (
        completion.get("completion_sha256")
        != publication["source_authority_completion_sha256"]
        or completion.get("later_source_freeze_object") != source_identity
        or completion.get("later_source_freeze_manifest_sha256")
        != publication["later_source_freeze_manifest_sha256"]
        or completion.get("task_count") != PRODUCTION_TASK_COUNT
        or completion.get("artifact_count") != ARTIFACT_COUNT
    ):
        raise CorpusParametricPreparationError(
            "source completion/publication binding differs"
        )
    selected = list(source_task_indexes)
    allowed_selected = [
        list(rows) for rows in (*PRODUCTION_TASK_LATTICES, (0,))
    ]
    if (
        selected not in allowed_selected
        or len(completion["tasks"]) != PRODUCTION_TASK_COUNT
        or len(source_freeze["slates"]) != PRODUCTION_TASK_COUNT
    ):
        raise CorpusParametricPreparationError("selected source task lattice differs")
    selected_local = {source_index: local for local, source_index in enumerate(selected)}
    schedule_rows: list[dict[str, object]] = []
    get_count = 0

    def artifact_stream() -> Iterator[object]:
        nonlocal get_count
        for source_index, (task_row, source_slate) in enumerate(zip(
            completion["tasks"], source_freeze["slates"], strict=True,
        )):
            if (
                task_row["task_index"] != source_index
                or source_slate["season"] != task_row["season"]
                or source_slate["week"] != task_row["week"]
                or source_slate["slate_id"] != task_row["slate_id"]
            ):
                raise CorpusParametricPreparationError(
                    f"source task[{source_index}] alias differs"
                )
            retained_by_block: dict[str, bytes] = {}
            for role, block_name, source_receipt in zip(
                batch.TASK_WORLD_SOURCE_ROLES, rw.WORLD_BLOCKS,
                source_slate["artifact_receipts"], strict=True,
            ):
                expected_identity = {
                    key: source_receipt[key]
                    for key in ("uri", "generation", "sha256", "bytes")
                }
                if expected_identity != task_row["world_artifact_receipts"][role]:
                    raise CorpusParametricPreparationError(
                        f"source task[{source_index}] {role} alias differs"
                    )
                reopened_identity, raw = _read_exact(
                    storage, expected_identity,
                    label=f"source artifact[{source_index}] {role}",
                )
                get_count += 1
                if source_index in selected_local:
                    retained_by_block[block_name] = raw
                yield getattr(authority_module, "RetainedArtifactBody")(
                    task_index=source_index, role=role,
                    identity=reopened_identity, raw=raw,
                )
            if source_index in selected_local:
                try:
                    prepared = getattr(later_module, "prepare_later_slate")(
                        source_freeze,
                        expected_source_freeze_sha256=source_freeze["freeze_sha256"],
                        season=task_row["season"], week=task_row["week"],
                        artifact_bodies=retained_by_block,
                    )
                except Exception as exc:
                    raise CorpusParametricPreparationError(
                        f"source task[{source_index}] matrices failed replay"
                    ) from exc
                schedule_rows.append(_schedule_row(
                    prepared=prepared,
                    local_task_index=selected_local[source_index],
                    task_row=task_row,
                    freeze_sha256=source_freeze["freeze_sha256"],
                    ranker=ranker,
                ))

    try:
        rebuilt_completion = getattr(
            authority_module, "verify_artifact_supported_source_authority"
        )(
            later_source_freeze_bytes=source_raw,
            later_source_freeze_object=source_identity,
            registration_bytes=registration_raw,
            registration_object=reopened["registration_object"][0],
            salary_diagnostic_bytes=reopened["salary_diagnostic_object"][1],
            salary_diagnostic_object=reopened["salary_diagnostic_object"][0],
            artifact_bodies=iter(artifact_stream()),
        )
    except CorpusParametricPreparationError:
        raise
    except Exception as exc:
        raise CorpusParametricPreparationError(
            "source authority scientific replay failed"
        ) from exc
    if rebuilt_completion != completion_raw or get_count != ARTIFACT_COUNT:
        raise CorpusParametricPreparationError(
            "source authority exact 54/270 replay differs"
        )
    schedule_rows.sort(key=lambda row: int(row["task_index"]))
    if [row["task_index"] for row in schedule_rows] != list(range(len(selected))):
        raise CorpusParametricPreparationError("world schedule coverage differs")
    return SourceFoundation(
        publication_identity=publication_id,
        publication=dict(publication),
        completion_identity=completion_identity,
        completion=dict(completion),
        source_freeze_identity=source_identity,
        source_freeze=dict(source_freeze),
        task_rows=tuple(dict(completion["tasks"][index]) for index in selected),
        schedule_rows=tuple(schedule_rows),
        exact_artifact_get_count=get_count,
    )


def _foundation_uris(plan: Mapping[str, object]) -> dict[str, object]:
    prefix = str(plan["foundation_prefix"])
    batch_prefix = str(plan["batch_output_prefix"])
    common = {
        role: f"{prefix}common-law/{role}.json" for role in COMMON_LAW_ROLES
    }
    requests = [
        f"{prefix}task-requests/task-{index:04d}.json"
        for index in range(len(plan["source_task_indexes"]))
    ] if plan["publish_task_requests"] else []
    return {
        "prefix_claim": f"{prefix}governance/prefix-claim.json",
        "preplan": f"{prefix}governance/preplan.json",
        "retrieval_prerequisite": (
            f"{prefix}governance/retrieval-task0-accepted-prerequisite.json"
        ),
        "inventory": f"{prefix}common-law/effective-policy-inventory.json",
        "common_law": common,
        "task_requests": requests,
        "manifest": f"{batch_prefix}governance/batch-manifest.json",
        "evidence": f"{batch_prefix}governance/pre-run-evidence-contract.json",
        "publication": f"{prefix}governance/publication-completion.json",
    }


def _flat_output_uris(uris: Mapping[str, object]) -> list[str]:
    return [
        str(uris["prefix_claim"]), str(uris["preplan"]),
        str(uris["retrieval_prerequisite"]), str(uris["inventory"]),
        *[str(value) for value in uris["common_law"].values()],
        *[str(value) for value in uris["task_requests"]],
        str(uris["manifest"]), str(uris["evidence"]), str(uris["publication"]),
    ]


def _inventory_body(repository_root: Path) -> dict[str, object]:
    try:
        generated = policy_inventory.generate_effective_policy_rule_inventory(
            repository_root
        )
        return policy_inventory.validate_effective_policy_rule_inventory(
            generated, repository_root
        )
    except Exception as exc:
        raise CorpusParametricPreparationError(
            "effective-policy inventory failed regeneration"
        ) from exc


def _task_inputs(
    *, plan: Mapping[str, object], source: SourceFoundation,
) -> list[dict[str, object]]:
    output_prefix = str(plan["batch_output_prefix"])
    rows: list[dict[str, object]] = []
    for local_index, source_row in enumerate(source.task_rows):
        slate_id = str(source_row["slate_id"])
        task_prefix = f"{output_prefix}tasks/task-{local_index:04d}-{slate_id}/"
        rows.append({
            "task_index": local_index,
            "slate_id": slate_id,
            "season": source_row["season"],
            "week": source_row["week"],
            "result_receipt_uri": f"{task_prefix}result/task-result.json",
            "variant_output_prefix": f"{task_prefix}variants/",
            "world_artifact_receipts": source_row["world_artifact_receipts"],
            "world_artifact_receipt_set_sha256": source_row[
                "world_artifact_receipt_set_sha256"
            ],
            "artifact_source_authority_task_sha256": source_row[
                "task_source_authority_sha256"
            ],
        })
    return rows


def _common_bodies(
    *, plan: Mapping[str, object], source: SourceFoundation,
    repository_root: Path = ROOT,
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    bodies = {
        "code_source": dict(plan["code_source"]),
        "world_schedule": build_world_schedule(source.schedule_rows),
    }
    for role in MECHANISM_ROLES:
        bodies[role] = dict(legal._REGISTERED_MECHANISM_BODIES[role])
    if tuple(bodies) != COMMON_LAW_ROLES:
        raise CorpusParametricPreparationError("common-law role lattice differs")
    inventory = _inventory_body(repository_root)
    return bodies, inventory


def _synthetic_identity(uri: str, raw: bytes, ordinal: int) -> dict[str, object]:
    return identity_for_bytes(uri, str(ordinal + 1), raw)


def _common_law(
    *, plan: Mapping[str, object], source: SourceFoundation,
    common_identities: Mapping[str, Mapping[str, object]],
    inventory_identity: Mapping[str, object], inventory: Mapping[str, object],
) -> dict[str, object]:
    source_receipts = {"later_source_freeze": source.source_freeze_identity}
    return {
        **{role: dict(common_identities[role]) for role in COMMON_LAW_ROLES},
        "immutable_image": dict(plan["code_source"]["immutable_image"]),
        "source_receipts": source_receipts,
        "source_receipt_set_sha256": batch.canonical_sha256(source_receipts),
        "later_source_freeze_manifest_sha256": source.source_freeze[
            "freeze_sha256"
        ],
        "artifact_source_authority_completion": source.completion_identity,
        "artifact_source_authority_completion_sha256": source.completion[
            "completion_sha256"
        ],
        "effective_policy_inventory_identity": dict(inventory_identity),
        "effective_policy_inventory_sha256": inventory["inventory_sha256"],
        "effective_policy_rule_universe_sha256": inventory[
            "rule_universe_sha256"
        ],
        "effective_policy_inventory_source_set_sha256": inventory[
            "source_set_sha256"
        ],
        "effective_policy_classified_input_projection_sha256": inventory[
            "classified_input_projection_sha256"
        ],
        "world_seed": plan["world_seed"],
        "solve_budget": {
            "solve_attempts_per_seed": batch.SOLVE_ATTEMPTS_PER_BLOCK,
            "worlds_per_block": batch.WORLDS_PER_BLOCK,
            "solver_timeout_seconds": batch.SOLVER_TIMEOUT_SECONDS,
            "candidate_entry_budget": batch.MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION,
            "selected_entry_budget": batch.SELECTED_ENTRY_BUDGET,
        },
        "solver": dict(plan["solver"]),
        "retry_law": {"max_attempts_per_task": 1, "max_retries": 0},
        "fresh_model_state_per_parameter_set": True,
        "worker_environment_inheritance": False,
        "worker_graph_mutation": False,
    }


def _preflight(
    *, plan: Mapping[str, object], source: SourceFoundation,
    prerequisite_raw: bytes, common_bodies: Mapping[str, Mapping[str, object]],
    inventory: Mapping[str, object], uris: Mapping[str, object],
) -> None:
    common_raw = {
        role: legal.canonical_json_bytes(body)
        for role, body in common_bodies.items()
    }
    synthetic_common = {
        role: _synthetic_identity(
            str(uris["common_law"][role]), common_raw[role], ordinal,
        )
        for ordinal, role in enumerate(COMMON_LAW_ROLES)
    }
    inventory_raw = legal.canonical_json_bytes(inventory)
    synthetic_inventory = _synthetic_identity(
        str(uris["inventory"]), inventory_raw, len(COMMON_LAW_ROLES),
    )
    common_law = _common_law(
        plan=plan, source=source, common_identities=synthetic_common,
        inventory_identity=synthetic_inventory, inventory=inventory,
    )
    try:
        manifest = batch.build_batch_manifest(
            batch_id=str(plan["batch_id"]),
            created_at_utc=str(plan["created_at_utc"]),
            output_prefix=str(plan["batch_output_prefix"]),
            common_law=common_law,
            tasks=_task_inputs(plan=plan, source=source),
        )
        expected_count = (
            PRODUCTION_TASK_COUNT if plan["mode"] == "production" else SMOKE_TASK_COUNT
        )
        if len(manifest["tasks"]) != expected_count:
            raise CorpusParametricPreparationError("preflight task count differs")
        manifest_raw = batch.canonical_json_bytes(manifest)
        manifest_identity = _synthetic_identity(
            str(uris["manifest"]), manifest_raw, 1000,
        )
        contract = evidence.build_corpus_batch_evidence_contract(
            batch_manifest=manifest, batch_manifest_identity=manifest_identity,
        )
        evidence.validate_corpus_batch_evidence_contract(
            contract, batch_manifest=manifest,
            batch_manifest_identity=manifest_identity,
        )
        parse_canonical_json_bytes(
            prerequisite_raw, label="retrieval prerequisite", trailing_newline=True,
        )
    except CorpusParametricPreparationError:
        raise
    except Exception as exc:
        raise CorpusParametricPreparationError(
            "batch/evidence preflight failed before first write"
        ) from exc


def _build_claim(
    *, plan: Mapping[str, object], planned_uris: Sequence[str],
) -> dict[str, object]:
    body = {
        "schema_version": PREFIX_CLAIM_SCHEMA,
        "foundation_id": plan["foundation_id"],
        "workstream": WORKSTREAM,
        "mode": plan["mode"],
        "foundation_prefix": plan["foundation_prefix"],
        "batch_output_prefix": plan["batch_output_prefix"],
        "preplan_sha256": plan["preplan_sha256"],
        "planned_object_uris": list(planned_uris),
        "planned_object_uri_set_sha256": canonical_sha256(list(planned_uris)),
        "pre_outcome_registration": True,
        "create_once": True,
        "resume_licensed": False,
        "replace_licensed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "corpus_fill_licensed": False,
        "production_change_licensed": False,
    }
    return _self_hashed(body, field="prefix_claim_sha256")


def _build_publication(
    *, plan: Mapping[str, object], claim_identity: Mapping[str, object],
    preplan_identity: Mapping[str, object], prerequisite_identity: Mapping[str, object],
    source: SourceFoundation, common_identities: Mapping[str, Mapping[str, object]],
    inventory_identity: Mapping[str, object], manifest_identity: Mapping[str, object],
    evidence_identity: Mapping[str, object],
    task_request_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    body = {
        "schema_version": PUBLICATION_SCHEMA,
        "foundation_id": plan["foundation_id"],
        "batch_id": plan["batch_id"],
        "mode": plan["mode"],
        "workstream": WORKSTREAM,
        "reserved_independent_workstream": RESERVED_POPULATION_WORKSTREAM,
        "created_at_utc": plan["created_at_utc"],
        "preplan_sha256": plan["preplan_sha256"],
        "prefix_claim": dict(claim_identity),
        "preplan_object": dict(preplan_identity),
        "full_manifest": dict(manifest_identity),
        "full_evidence_contract": dict(evidence_identity),
        "accepted_retrieval_prerequisite": dict(prerequisite_identity),
        "source_publication_authority": dict(source.publication_identity),
        "source_authority_completion": dict(source.completion_identity),
        "source_freeze": dict(source.source_freeze_identity),
        "common_law_objects": {
            role: dict(common_identities[role]) for role in COMMON_LAW_ROLES
        },
        "effective_policy_inventory": dict(inventory_identity),
        "task_requests": [dict(row) for row in task_request_identities],
        "task_count": len(source.task_rows),
        "parameter_arm_count": len(batch.PARAMETER_SET_ORDER),
        "source_task_count": PRODUCTION_TASK_COUNT,
        "source_artifact_count": ARTIFACT_COUNT,
        "source_artifact_exact_get_count": source.exact_artifact_get_count,
        "idempotent": True,
        "create_once": True,
        "runtime_iam_authority": False,
        "launch_authority": False,
        "outcome_read_authority": False,
        "historical_scoring_authority": False,
        "corpus_fill_authority": False,
        "corpus_population_authority": False,
        "live_strategy_authority": False,
        "graph_mutation_authority": False,
        "production_change_authority": False,
        "production_policy_change_authority": False,
        "automatic_policy_feedback": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return _self_hashed(body, field="publication_sha256")


def validate_publication(
    value: object, *, plan: Mapping[str, object], publication_uri: str,
) -> dict[str, object]:
    item = dict(_mapping(value, label="foundation publication"))
    expected_keys = frozenset({
        "schema_version", "foundation_id", "batch_id", "mode", "workstream",
        "reserved_independent_workstream", "created_at_utc", "preplan_sha256",
        "prefix_claim", "preplan_object", "full_manifest",
        "full_evidence_contract", "accepted_retrieval_prerequisite",
        "source_publication_authority", "source_authority_completion",
        "source_freeze", "common_law_objects", "effective_policy_inventory",
        "task_requests", "task_count", "parameter_arm_count",
        "source_task_count", "source_artifact_count",
        "source_artifact_exact_get_count", "idempotent", "create_once",
        "runtime_iam_authority", "launch_authority", "outcome_read_authority",
        "historical_scoring_authority", "corpus_fill_authority",
        "corpus_population_authority", "live_strategy_authority",
        "graph_mutation_authority", "production_change_authority",
        "production_policy_change_authority", "automatic_policy_feedback",
        "outcome_columns_read", "uses_realized_outcomes", "publication_sha256",
    })
    _exact_keys(item, expected_keys, label="foundation publication")
    _validate_self_hash(item, field="publication_sha256", label="foundation publication")
    expected_task_count = PRODUCTION_TASK_COUNT if plan["mode"] == "production" else 1
    if (
        item["schema_version"] != PUBLICATION_SCHEMA
        or item["foundation_id"] != plan["foundation_id"]
        or item["batch_id"] != plan["batch_id"]
        or item["mode"] != plan["mode"]
        or item["workstream"] != WORKSTREAM
        or item["reserved_independent_workstream"] != RESERVED_POPULATION_WORKSTREAM
        or item["preplan_sha256"] != plan["preplan_sha256"]
        or item["task_count"] != expected_task_count
        or item["parameter_arm_count"] != 7
        or item["source_task_count"] != 54
        or item["source_artifact_count"] != 270
        or item["source_artifact_exact_get_count"] != 270
        or item["idempotent"] is not True or item["create_once"] is not True
        or item["outcome_columns_read"] != []
        or any(item[field] is not False for field in (
            "runtime_iam_authority", "launch_authority", "outcome_read_authority",
            "historical_scoring_authority", "corpus_fill_authority",
            "corpus_population_authority", "live_strategy_authority",
            "graph_mutation_authority", "production_change_authority",
            "production_policy_change_authority", "automatic_policy_feedback",
            "uses_realized_outcomes",
        ))
    ):
        raise CorpusParametricPreparationError("foundation publication authority differs")
    for key in (
        "prefix_claim", "preplan_object", "full_manifest", "full_evidence_contract",
        "accepted_retrieval_prerequisite", "source_publication_authority",
        "source_authority_completion", "source_freeze", "effective_policy_inventory",
    ):
        item[key] = normalize_identity(item[key], label=f"publication {key}")
    common = _mapping(item["common_law_objects"], label="publication common law")
    _exact_keys(common, frozenset(COMMON_LAW_ROLES), label="publication common law")
    item["common_law_objects"] = {
        role: normalize_identity(common[role], label=f"publication common {role}")
        for role in COMMON_LAW_ROLES
    }
    requests = _sequence(item["task_requests"], label="publication task requests")
    expected_requests = expected_task_count if plan["publish_task_requests"] else 0
    if len(requests) != expected_requests:
        raise CorpusParametricPreparationError("publication task request count differs")
    item["task_requests"] = [
        normalize_identity(row, label="publication task request") for row in requests
    ]
    uris = _foundation_uris(plan)
    expected_identity_uris = {
        "prefix_claim": uris["prefix_claim"],
        "preplan_object": uris["preplan"],
        "full_manifest": uris["manifest"],
        "full_evidence_contract": uris["evidence"],
        "accepted_retrieval_prerequisite": uris["retrieval_prerequisite"],
        "effective_policy_inventory": uris["inventory"],
    }
    if (
        publication_uri != uris["publication"]
        or any(
            item[field]["uri"] != expected_uri
            for field, expected_uri in expected_identity_uris.items()
        )
        or item["source_publication_authority"]
        != plan["source_publication_completion_identity"]
        or any(
            item["common_law_objects"][role]["uri"]
            != uris["common_law"][role]
            for role in COMMON_LAW_ROLES
        )
        or [row["uri"] for row in item["task_requests"]]
        != list(uris["task_requests"])
    ):
        raise CorpusParametricPreparationError(
            "foundation publication deterministic URI/input binding differs"
        )
    return item


def _reopen_completed(
    *, storage: ObjectStore, plan: Mapping[str, object],
    publication_identity: Mapping[str, object], publication_raw: bytes,
) -> dict[str, object]:
    publication = validate_publication(
        parse_canonical_json_bytes(publication_raw, label="foundation publication"),
        plan=plan, publication_uri=str(publication_identity["uri"]),
    )
    preplan_raw = _read_exact(
        storage, publication["preplan_object"], label="publication preplan_object"
    )[1]
    if preplan_raw != canonical_json_bytes(plan):
        raise CorpusParametricPreparationError("published preplan differs")
    claim_raw = _read_exact(
        storage, publication["prefix_claim"], label="publication prefix_claim"
    )[1]
    claim = dict(_mapping(
        parse_canonical_json_bytes(claim_raw, label="foundation prefix claim"),
        label="foundation prefix claim",
    ))
    _validate_self_hash(
        claim, field="prefix_claim_sha256", label="foundation prefix claim"
    )
    expected_uris = _flat_output_uris(_foundation_uris(plan))
    if (
        claim.get("schema_version") != PREFIX_CLAIM_SCHEMA
        or claim.get("preplan_sha256") != plan["preplan_sha256"]
        or claim.get("planned_object_uris") != expected_uris
        or claim.get("planned_object_uri_set_sha256")
        != canonical_sha256(expected_uris)
        or claim.get("pre_outcome_registration") is not True
        or claim.get("create_once") is not True
        or claim.get("resume_licensed") is not False
        or claim.get("replace_licensed") is not False
    ):
        raise CorpusParametricPreparationError("published prefix claim differs")
    for key in (
        "full_manifest", "full_evidence_contract",
        "accepted_retrieval_prerequisite", "source_publication_authority",
        "source_authority_completion", "source_freeze", "effective_policy_inventory",
    ):
        _read_exact(storage, publication[key], label=f"publication {key}")
    for identity in publication["common_law_objects"].values():
        _read_exact(storage, identity, label="publication common law")
    for identity in publication["task_requests"]:
        _read_exact(storage, identity, label="publication task request")
    manifest_id, manifest_raw = _read_exact(
        storage, publication["full_manifest"], label="published manifest"
    )
    manifest = batch.validate_batch_manifest(
        batch.parse_canonical_json_bytes(manifest_raw, label="published manifest")
    )
    common = manifest["common_law"]
    if (
        len(manifest["tasks"]) != publication["task_count"]
        or any(
            common[role] != publication["common_law_objects"][role]
            for role in COMMON_LAW_ROLES
        )
        or common["effective_policy_inventory_identity"]
        != publication["effective_policy_inventory"]
        or common["artifact_source_authority_completion"]
        != publication["source_authority_completion"]
        or common["source_receipts"]["later_source_freeze"]
        != publication["source_freeze"]
    ):
        raise CorpusParametricPreparationError("published manifest task count differs")
    _, evidence_raw = _read_exact(
        storage, publication["full_evidence_contract"], label="published evidence"
    )
    evidence.validate_corpus_batch_evidence_contract_bytes(
        evidence_raw, batch_manifest=manifest, batch_manifest_identity=manifest_id,
    )
    prerequisite_raw = _read_exact(
        storage, publication["accepted_retrieval_prerequisite"],
        label="published retrieval prerequisite",
    )[1]
    prerequisite = _mapping(parse_canonical_json_bytes(
        prerequisite_raw, label="published retrieval prerequisite",
        trailing_newline=True,
    ), label="published retrieval prerequisite")
    _validate_self_hash(
        prerequisite, field="acceptance_sha256",
        label="published retrieval prerequisite", transport=True,
    )
    if prerequisite.get("schema_version") != RETRIEVAL_PREREQUISITE_SCHEMA:
        raise CorpusParametricPreparationError("retrieval prerequisite schema differs")
    return publication


def require_execute_gate(*, execute: bool, environ: Mapping[str, str]) -> None:
    if execute is not True or environ.get(ENABLE_ENV) != "1":
        raise CorpusParametricPreparationError(
            f"execution requires literal --execute and {ENABLE_ENV}=1"
        )


def execute_preparer(
    *, preplan: object, execute: bool, environ: Mapping[str, str],
    storage_factory: Callable[[], ObjectStore], repository_root: Path = ROOT,
    solver_probe_fn: Callable[[], Mapping[str, object]] = solver_probe,
    retrieval_module: ModuleType | object = retrieval,
    source_transport_module: ModuleType | object | None = None,
) -> dict[str, object]:
    """Prepare and create-once publish one smoke or production foundation."""
    require_execute_gate(execute=execute, environ=environ)
    plan = validate_preplan(
        preplan, repository_root=repository_root, solver_probe_fn=solver_probe_fn,
    )
    storage = storage_factory()
    _prerequisite, prerequisite_raw = bridge_retrieval_task0(
        storage=storage,
        terminal_identity=plan["retrieval_terminal_identity"],
        accepted_at_utc=str(plan["accepted_at_utc"]),
        retrieval_module=retrieval_module,
    )
    source = load_source_authority(
        storage=storage,
        publication_identity=plan["source_publication_completion_identity"],
        source_task_indexes=plan["source_task_indexes"],
        source_transport_module=source_transport_module,
    )
    uris = _foundation_uris(plan)
    common_bodies, inventory = _common_bodies(
        plan=plan, source=source, repository_root=repository_root,
    )
    _preflight(
        plan=plan, source=source, prerequisite_raw=prerequisite_raw,
        common_bodies=common_bodies, inventory=inventory, uris=uris,
    )
    revalidated_plan = validate_preplan(
        plan, repository_root=repository_root, solver_probe_fn=solver_probe_fn,
    )
    if canonical_json_bytes(revalidated_plan) != canonical_json_bytes(plan):
        raise CorpusParametricPreparationError(
            "preplan authority drifted during input replay"
        )
    planned_uris = _flat_output_uris(uris)
    existing = {uri: storage.resolve_optional(uri) for uri in planned_uris}
    present = [uri for uri, value in existing.items() if value is not None]
    if present:
        if len(present) != len(planned_uris):
            raise CorpusParametricPreparationError(
                "partial preparer namespace is terminal; resume/replace forbidden"
            )
        publication_identity, publication_raw = existing[str(uris["publication"])]  # type: ignore[misc]
        publication = _reopen_completed(
            storage=storage, plan=plan,
            publication_identity=publication_identity,
            publication_raw=publication_raw,
        )
        return {
            "schema_version": "corpus-parametric-foundation-result/v1",
            "status": "already-complete",
            "publication": publication,
            "publication_identity": publication_identity,
        }
    claim = _build_claim(plan=plan, planned_uris=planned_uris)
    claim_identity = _publish_exact(
        storage, str(uris["prefix_claim"]), canonical_json_bytes(claim),
        label="foundation prefix claim",
    )
    preplan_identity = _publish_exact(
        storage, str(uris["preplan"]), canonical_json_bytes(plan),
        label="foundation preplan",
    )
    prerequisite_identity = _publish_exact(
        storage, str(uris["retrieval_prerequisite"]), prerequisite_raw,
        label="retrieval accepted prerequisite",
    )
    common_identities: dict[str, dict[str, object]] = {}
    for role in COMMON_LAW_ROLES:
        raw = legal.canonical_json_bytes(common_bodies[role])
        common_identities[role] = _publish_exact(
            storage, str(uris["common_law"][role]), raw,
            label=f"common law {role}",
        )
    inventory_raw = legal.canonical_json_bytes(inventory)
    inventory_identity = _publish_exact(
        storage, str(uris["inventory"]), inventory_raw,
        label="effective-policy inventory",
    )
    common_law = _common_law(
        plan=plan, source=source, common_identities=common_identities,
        inventory_identity=inventory_identity, inventory=inventory,
    )
    manifest = batch.build_batch_manifest(
        batch_id=str(plan["batch_id"]),
        created_at_utc=str(plan["created_at_utc"]),
        output_prefix=str(plan["batch_output_prefix"]),
        common_law=common_law,
        tasks=_task_inputs(plan=plan, source=source),
    )
    expected_count = PRODUCTION_TASK_COUNT if plan["mode"] == "production" else 1
    if len(manifest["tasks"]) != expected_count:
        raise CorpusParametricPreparationError("published task count differs")
    manifest_raw = batch.canonical_json_bytes(manifest)
    manifest_identity = _publish_exact(
        storage, str(uris["manifest"]), manifest_raw, label="batch manifest",
    )
    manifest = batch.validate_batch_manifest(
        batch.parse_canonical_json_bytes(
            _read_exact(storage, manifest_identity, label="batch manifest")[1],
            label="batch manifest",
        )
    )
    contract = evidence.build_corpus_batch_evidence_contract(
        batch_manifest=manifest, batch_manifest_identity=manifest_identity,
    )
    contract_raw = evidence.canonical_json_bytes(contract)
    evidence_identity = _publish_exact(
        storage, str(uris["evidence"]), contract_raw,
        label="batch evidence contract",
    )
    evidence.validate_corpus_batch_evidence_contract_identity(
        contract, evidence_identity, batch_manifest=manifest,
        batch_manifest_identity=manifest_identity,
    )
    task_request_identities: list[dict[str, object]] = []
    if plan["publish_task_requests"]:
        for index, uri in enumerate(uris["task_requests"]):
            request = batch.build_task_request(
                batch_manifest=manifest,
                batch_manifest_identity=manifest_identity,
                task_index=index,
            )
            task_request_identities.append(_publish_exact(
                storage, str(uri), batch.canonical_json_bytes(request),
                label=f"task request {index}",
            ))
    publication = _build_publication(
        plan=plan, claim_identity=claim_identity,
        preplan_identity=preplan_identity,
        prerequisite_identity=prerequisite_identity, source=source,
        common_identities=common_identities,
        inventory_identity=inventory_identity,
        manifest_identity=manifest_identity, evidence_identity=evidence_identity,
        task_request_identities=task_request_identities,
    )
    publication_identity = _publish_exact(
        storage, str(uris["publication"]), canonical_json_bytes(publication),
        label="foundation publication",
    )
    reopened = _reopen_completed(
        storage=storage, plan=plan,
        publication_identity=publication_identity,
        publication_raw=_read_exact(
            storage, publication_identity, label="foundation publication"
        )[1],
    )
    return {
        "schema_version": "corpus-parametric-foundation-result/v1",
        "status": "created",
        "publication": reopened,
        "publication_identity": publication_identity,
    }


class GCSStorage:
    """Exact-generation GCS implementation; it exposes no inventory method."""

    def __init__(self, *, project: str = PROJECT) -> None:
        try:
            from google.cloud import storage as gcs
        except ImportError as exc:
            raise CorpusParametricPreparationError(
                "google-cloud-storage is required only for execute"
            ) from exc
        self._client = gcs.Client(project=project)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        tail = uri.removeprefix("gs://")
        bucket_name, marker, object_name = tail.partition("/")
        if not uri.startswith("gs://") or not marker or not bucket_name or not object_name:
            raise CorpusParametricPreparationError("GCS URI differs")
        return bucket_name, object_name

    def read(self, identity: Mapping[str, object]) -> bytes:
        normalized = normalize_identity(identity, label="GCS read identity")
        bucket_name, object_name = self._parts(str(normalized["uri"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=int(str(normalized["generation"]))
        )
        try:
            return bytes(blob.download_as_bytes(
                if_generation_match=int(str(normalized["generation"]))
            ))
        except Exception as exc:
            raise CorpusParametricPreparationError(
                "generation-pinned GCS GET failed"
            ) from exc

    def resolve_optional(
        self, uri: str,
    ) -> tuple[dict[str, object], bytes] | None:
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.reload()
        except Exception as exc:
            if exc.__class__.__name__ == "NotFound":
                return None
            raise CorpusParametricPreparationError("exact-name GCS HEAD failed") from exc
        identity = {
            "uri": uri,
            "generation": str(blob.generation),
            "sha256": "0" * 64,
            "bytes": int(blob.size),
        }
        raw = bytes(blob.download_as_bytes(if_generation_match=int(blob.generation)))
        identity["sha256"] = sha256(raw).hexdigest()
        return normalize_identity(identity, label="resolved GCS object"), raw

    def publish(
        self, uri: str, raw: bytes, media_type: str = "application/json",
    ) -> dict[str, object]:
        bucket_name, object_name = self._parts(uri)
        blob = self._client.bucket(bucket_name).blob(object_name)
        try:
            blob.upload_from_string(
                raw, content_type=media_type, if_generation_match=0,
            )
            blob.reload()
        except Exception as exc:
            raise CorpusParametricPreparationError(
                "create-only GCS publication failed"
            ) from exc
        return identity_for_bytes(uri, str(blob.generation), raw)


def _load_preplan(path: Path) -> object:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusParametricPreparationError("preplan cannot be read") from exc
    return parse_canonical_json_bytes(raw, label="preplan")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    sub = value.add_subparsers(dest="command", required=True)
    sub.add_parser("parked")
    sub.add_parser("solver-probe")
    for name in ("validate", "dry-run"):
        command = sub.add_parser(name)
        command.add_argument("--preplan", required=True, type=Path)
    execute = sub.add_parser("execute")
    preplan_source = execute.add_mutually_exclusive_group(required=True)
    preplan_source.add_argument("--preplan", type=Path)
    preplan_source.add_argument("--preplan-uri")
    execute.add_argument("--preplan-generation")
    execute.add_argument("--preplan-sha256")
    execute.add_argument("--preplan-bytes", type=int)
    execute.add_argument("--execute", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "parked":
        print(json.dumps({"status": "parked", "default_off": True}, sort_keys=True))
        return 0
    if args.command == "solver-probe":
        print(canonical_json_bytes(solver_probe()).decode("utf-8"))
        return 0
    if args.command in {"validate", "dry-run"}:
        plan_value = _load_preplan(args.preplan)
        plan = validate_preplan(plan_value)
        result = {
            "schema_version": "corpus-parametric-preparer-dry-run/v1",
            "command": args.command,
            "mode": plan["mode"],
            "task_count": len(plan["source_task_indexes"]),
            "parameter_arm_count": len(batch.PARAMETER_SET_ORDER),
            "planned_uris": _flat_output_uris(_foundation_uris(plan)),
            "client_constructed": False,
            "writes_performed": 0,
            "default_off": True,
            "uses_realized_outcomes": False,
        }
        print(canonical_json_bytes(result).decode("utf-8"))
        return 0
    require_execute_gate(execute=args.execute, environ=os.environ)
    retained_storage: ObjectStore | None = None
    if args.preplan_uri is not None:
        if (
            args.preplan_generation is None
            or args.preplan_sha256 is None
            or args.preplan_bytes is None
        ):
            raise CorpusParametricPreparationError(
                "generation-pinned preplan URI requires generation/SHA/bytes"
            )
        retained_storage = GCSStorage()
        preplan_identity = normalize_identity({
            "uri": args.preplan_uri,
            "generation": args.preplan_generation,
            "sha256": args.preplan_sha256,
            "bytes": args.preplan_bytes,
        }, label="execute preplan identity")
        plan_raw = _read_exact(
            retained_storage, preplan_identity, label="execute preplan"
        )[1]
        plan_value = parse_canonical_json_bytes(plan_raw, label="execute preplan")
    else:
        if any(value is not None for value in (
            args.preplan_generation, args.preplan_sha256, args.preplan_bytes,
        )):
            raise CorpusParametricPreparationError(
                "local preplan cannot be combined with object identity fields"
            )
        plan_value = _load_preplan(args.preplan)
    result = execute_preparer(
        preplan=plan_value, execute=args.execute, environ=os.environ,
        storage_factory=(
            (lambda: retained_storage)
            if retained_storage is not None else GCSStorage
        ),
    )
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CorpusParametricPreparationError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


__all__ = [
    "ARTIFACT_COUNT", "CorpusParametricPreparationError", "ENABLE_ENV",
    "GCSStorage", "PREPLAN_SCHEMA", "PRODUCTION_TASK_COUNT",
    "PUBLICATION_SCHEMA", "RETRIEVAL_PREREQUISITE_SCHEMA",
    "SMOKE_TASK_COUNT", "SourceFoundation", "WORKSTREAM",
    "bridge_retrieval_task0", "build_preplan", "build_world_schedule",
    "canonical_json_bytes", "canonical_sha256", "execute_preparer",
    "identity_for_bytes", "load_source_authority", "main", "parser",
    "require_execute_gate", "solver_probe", "validate_preplan",
    "validate_publication",
]
