"""Production transport law for the outcome-blind Foundry T230 panel.

This module is deliberately outside the selector/scoring implementation.  It
freezes the one production prefix and compute envelope, binds a digest-first
image to a real source checkout, materializes the post-image evidence bytes at
the core runner's fixed no-follow path, and journals every create-once write by
known URI.  It never lists a bucket, resolves ``latest``, reads outcomes, or
changes a lineup, rank, book, support threshold, or prospective shadow.

The journal permits recovery only when a deterministic pre-publication intent
already binds the target URI and exact bytes.  Recovery performs one exact-name
metadata lookup, immediately pins the returned generation, and byte-verifies
it.  A missing intent or unequal byte is terminal; automatic relaunch remains
forbidden.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Final, Protocol

from nfl_dfs.research import corpus_extreme_tail_panel_execution as execution
from nfl_dfs.research import corpus_parametric_batch as batch


TRANSPORT_SCHEMA: Final = "foundry-t230-production-transport/v1"
SOURCE_SNAPSHOT_SCHEMA: Final = "foundry-t230-source-snapshot/v1"
COMPUTE_GATE_SCHEMA: Final = "foundry-t230-numeric-compute-gate/v1"
BENCHMARK_SCHEMA: Final = "foundry-t230-mechanics-benchmark/v1"
BENCHMARK_DISPOSITION_SCHEMA: Final = (
    "foundry-t230-benchmark-disposition/v1"
)
BENCHMARK_EXECUTION_TERMINAL_SCHEMA: Final = (
    "foundry-t230-benchmark-execution-terminal/v1"
)
PREFREEZE_SMOKE_TIME_BINDING_SCHEMA: Final = (
    "foundry-t230-prefreeze-smoke-time-binding/v1"
)
PREFREEZE_SMOKE_EXECUTION_SCHEMA: Final = (
    "foundry-t230-prefreeze-smoke-execution/v1"
)
PREFREEZE_SMOKE_LAUNCH_SCHEMA: Final = (
    "foundry-t230-prefreeze-smoke-launch/v1"
)
PREFREEZE_RELEASE_GATE_SCHEMA: Final = (
    "foundry-t230-prefreeze-release-gate/v1"
)
BENCHMARK_ABORT_SCHEMA: Final = "foundry-t230-benchmark-terminal-abort/v1"
COMPUTE_RELEASE_SCHEMA: Final = "foundry-t230-compute-release/v1"
TIME_V_PARSER_SCHEMA: Final = "foundry-t230-gnu-time-v-parser/v2"
PUBLICATION_INTENT_SCHEMA: Final = "foundry-t230-publication-intent/v1"
PUBLICATION_COMPLETION_SCHEMA: Final = (
    "foundry-t230-publication-completion/v1"
)
STAGE_RECEIPT_SCHEMA: Final = "foundry-t230-stage-receipt/v1"
STAGE_START_SCHEMA: Final = "foundry-t230-stage-start/v1"
LAUNCH_REQUEST_SCHEMA: Final = "foundry-t230-launch-request/v1"
JOB_CONFIG_SCHEMA: Final = "foundry-t230-cloud-run-job-config/v1"
LANE_LEDGER_SCHEMA: Final = "foundry-t230-lane-receipt-ledger/v1"
IMAGE_EVIDENCE_PUBLICATION_BINDING_SCHEMA: Final = (
    "foundry-t230-image-evidence-publication-binding/v1"
)

RUN_ID: Final = "20260825-foundry-t230-production-v1"
PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
OUTPUT_PREFIX: Final = (
    "gs://nfl-predictions-503414-corpus-parametric/research/"
    "corpus-parametric-research/t230/"
    "20260825-foundry-t230-production-v1/"
)
TRANSPORT_PREFIX: Final = OUTPUT_PREFIX + "transport/"
PREFREEZE_OUTPUT_PREFIX: Final = (
    "gs://nfl-predictions-503414-corpus-parametric/research/"
    "corpus-parametric-research/t230-prefreeze/"
    "20260825-foundry-t230-production-v1/"
)
PREFREEZE_JOURNAL_PREFIX: Final = PREFREEZE_OUTPUT_PREFIX + "publication-journal/"
TRANSPORT_CONTRACT_URI: Final = TRANSPORT_PREFIX + "transport-contract-v1.json"
COMPUTE_RELEASE_URI: Final = TRANSPORT_PREFIX + "compute-release-v1.json"
RAW_TIME_V_URI: Final = TRANSPORT_PREFIX + "benchmark/gnu-time-v.raw.txt"
BENCHMARK_URI: Final = TRANSPORT_PREFIX + "benchmark/benchmark-v1.json"
BENCHMARK_DISPOSITION_URI: Final = (
    TRANSPORT_PREFIX + "benchmark/disposition-v1.json"
)
BENCHMARK_EXECUTION_TERMINAL_URI: Final = (
    TRANSPORT_PREFIX + "benchmark/execution-terminal-v1.json"
)
BENCHMARK_ABORT_URI: Final = TRANSPORT_PREFIX + "benchmark/terminal-abort-v1.json"
PREFREEZE_SMOKE_RECEIPT_URI: Final = (
    PREFREEZE_OUTPUT_PREFIX + "rule1-smoke-v1.json"
)
PREFREEZE_SMOKE_TIME_V_URI: Final = (
    PREFREEZE_OUTPUT_PREFIX + "rule1-smoke-gnu-time-v.raw.txt"
)
PREFREEZE_SMOKE_EXECUTION_URI: Final = (
    PREFREEZE_OUTPUT_PREFIX + "rule1-smoke-execution-v1.json"
)
PREFREEZE_SMOKE_LAUNCH_URI: Final = (
    PREFREEZE_OUTPUT_PREFIX + "rule1-smoke-launch-v1.json"
)
JOURNAL_PREFIX: Final = TRANSPORT_PREFIX + "publication-journal/"
BENCHMARK_COMMAND: Final = "bash scripts/run_t230_benchmark_worker_v1.sh"
PREFREEZE_SMOKE_TIMED_COMMAND: Final = (
    "python scripts/run_corpus_extreme_tail_t230_prefreeze_smoke_v1.py "
    "--execute --receipt-output /tmp/foundry-t230-prefreeze-smoke-v1.json"
)
PREFREEZE_SMOKE_WORKER_COMMAND: Final = (
    "bash scripts/run_t230_prefreeze_smoke_worker_v1.sh"
)

REPOSITORY_ROOT: Final = Path(
    "/home/erich/projects/nfl-predictions"
)
SOURCE_SNAPSHOT_PATH: Final = Path(
    "/opt/nfl-dfs/foundry-t230-source-snapshot-v1.json"
)
RUNTIME_EVIDENCE_PATH: Final = execution.EXPECTED_BAKED_IMAGE_EVIDENCE_PATH

LANE_A_JOB: Final = "atlas-minimal-c-s2023-w1-v1"
LANE_B_JOB: Final = "atlas-cbc-32g-full-2023-w8-v1"
LANE_CONTRACT: Final = (
    {
        "lane_ordinal": 0,
        "lane_id": "t230-a",
        "reuse_job": LANE_A_JOB,
        "source_ordinals": list(range(0, 28)),
    },
    {
        "lane_ordinal": 1,
        "lane_id": "t230-b",
        "reuse_job": LANE_B_JOB,
        "source_ordinals": list(range(28, 54)),
    },
)

CPU_LIMIT: Final = 8
MEMORY_LIMIT_MIB: Final = 32 * 1024
MAX_PEAK_RSS_KIB: Final = 24 * 1024 * 1024
MIN_RSS_HEADROOM_KIB: Final = 8 * 1024 * 1024
MAX_WALL_TIME_MILLIS: Final = 18_000_000
TASK_TIMEOUT_SECONDS: Final = 21_600
MIN_TIMEOUT_HEADROOM_SECONDS: Final = 900
MIN_TIMEOUT_HEADROOM_FRACTION_NUMERATOR: Final = 1
MIN_TIMEOUT_HEADROOM_FRACTION_DENOMINATOR: Final = 5
MAX_OUTER_WORKER_WALL_DELTA_MILLIS: Final = 120_000
MAX_OUTER_WORKER_RSS_DELTA_KIB: Final = 2 * 1024 * 1024
MAX_CONCURRENT_LANES: Final = 2
MAX_RETRIES: Final = 0

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

_LOCAL_G0_RECEIPT_PATHS: Final = (
    str(execution.FROZEN_G0_PUBLICATION_RECEIPT_PATH.relative_to(REPOSITORY_ROOT)),
    *(str(path.relative_to(REPOSITORY_ROOT)) for path in execution.FROZEN_G0_LANE_RECEIPT_PATHS),
)
SOURCE_SNAPSHOT_PATHS: Final = tuple(dict.fromkeys((
    *execution._IMPLEMENTATION_PATHS,
    *execution.PREFREEZE_SMOKE_IMPLEMENTATION_PATHS,
    execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH,
    *_LOCAL_G0_RECEIPT_PATHS,
    "reports/2026-08-25-t230-production-transport-amendment.md",
    "src/nfl_dfs/research/corpus_extreme_tail_panel_transport.py",
    "scripts/run_corpus_extreme_tail_panel_transport_v1.py",
    "scripts/run_t230_benchmark_worker_v1.sh",
    "scripts/run_t230_prefreeze_smoke_worker_v1.sh",
    "scripts/cloud_corpus_extreme_tail_panel_v1_reuse.sh",
    "Dockerfile.foundry-t230",
    "cloudbuild.foundry-t230.yaml",
)))
_TRACKED_SOURCE_SNAPSHOT_PATHS: Final = tuple(
    path for path in SOURCE_SNAPSHOT_PATHS if path not in _LOCAL_G0_RECEIPT_PATHS
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_IMAGE = re.compile(r"[^\s@]+@sha256:[0-9a-f]{64}")
_EXECUTION = re.compile(r"[a-z][a-z0-9-]{0,61}[a-z0-9]-[a-z0-9]{5}")

_TIME_V_LABELS: Final = (
    "Command being timed",
    "User time (seconds)",
    "System time (seconds)",
    "Percent of CPU this job got",
    "Elapsed (wall clock) time (h:mm:ss or m:ss)",
    "Average shared text size (kbytes)",
    "Average unshared data size (kbytes)",
    "Average stack size (kbytes)",
    "Average total size (kbytes)",
    "Maximum resident set size (kbytes)",
    "Average resident set size (kbytes)",
    "Major (requiring I/O) page faults",
    "Minor (reclaiming a frame) page faults",
    "Voluntary context switches",
    "Involuntary context switches",
    "Swaps",
    "File system inputs",
    "File system outputs",
    "Socket messages sent",
    "Socket messages received",
    "Signals delivered",
    "Page size (bytes)",
    "Exit status",
)
_TIME_V_PARSER_BODY: Final = {
    "schema_version": TIME_V_PARSER_SCHEMA,
    "parser_id": "strict-complete-gnu-time-v-wall-rss-exit-v2",
    "encoding": "utf-8",
    "required_labels": list(_TIME_V_LABELS),
    "duplicate_labels_allowed": False,
    "elapsed_precision": "integer-milliseconds-no-rounding",
    "unrecognized_lines_ignored": False,
    "non_mechanics_text_allowed": False,
}
EXPECTED_TIME_V_PARSER_SHA256: Final = (
    "065181d51b71a9ff18a0c118feb758bf567f18f99450b1c23faece4c5747fb14"
)


class T230TransportError(RuntimeError):
    """The production T230 transport failed closed."""


class JournalObjectExists(T230TransportError):
    """A create-with-generation-zero operation met an existing object."""


class JournalBackend(Protocol):
    """The only object-store operations licensed to the journal."""

    def read(self, identity: Mapping[str, object]) -> bytes: ...

    def read_known_uri(self, uri: str) -> tuple[Mapping[str, object], bytes]: ...

    def create(self, uri: str, raw: bytes) -> Mapping[str, object]: ...


def _fail(message: str) -> None:
    raise T230TransportError(message)


def canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise T230TransportError("value is not canonical JSON") from exc


def strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    def unique(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                raise ValueError(f"duplicate key {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite value {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise T230TransportError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        _fail(f"{label} must be one object")
    return value


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    if field in result:
        _fail(f"{field} cannot be caller supplied")
    result[field] = sha256(canonical_json(result)).hexdigest()
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> None:
    retained = value.get(field)
    if not isinstance(retained, str) or _SHA256.fullmatch(retained) is None:
        _fail(f"{label} hash differs")
    body = {key: item for key, item in value.items() if key != field}
    if sha256(canonical_json(body)).hexdigest() != retained:
        _fail(f"{label} self-hash differs")


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise T230TransportError(f"{label} identity differs") from exc


def _image(value: object, *, label: str) -> dict[str, str]:
    try:
        return batch.normalize_image_identity(value, label=label)
    except Exception as exc:
        raise T230TransportError(f"{label} must be digest pinned") from exc


def _false_authorities(value: Mapping[str, object], *, label: str) -> None:
    for field in _FALSE_AUTHORITY_FIELDS:
        if value.get(field) is not False:
            _fail(f"{label}.{field} must be false")


def frozen_compute_gate_v1() -> dict[str, object]:
    body = {
        "schema_version": COMPUTE_GATE_SCHEMA,
        "cpu_limit": CPU_LIMIT,
        "memory_limit_mib": MEMORY_LIMIT_MIB,
        "max_peak_rss_kib": MAX_PEAK_RSS_KIB,
        "minimum_rss_headroom_kib": MIN_RSS_HEADROOM_KIB,
        "max_wall_time_millis": MAX_WALL_TIME_MILLIS,
        "task_timeout_seconds": TASK_TIMEOUT_SECONDS,
        "minimum_timeout_headroom_seconds": MIN_TIMEOUT_HEADROOM_SECONDS,
        "minimum_timeout_headroom_fraction": {
            "numerator": MIN_TIMEOUT_HEADROOM_FRACTION_NUMERATOR,
            "denominator": MIN_TIMEOUT_HEADROOM_FRACTION_DENOMINATOR,
        },
        "max_outer_worker_wall_delta_millis": (
            MAX_OUTER_WORKER_WALL_DELTA_MILLIS
        ),
        "max_outer_worker_peak_rss_delta_kib": (
            MAX_OUTER_WORKER_RSS_DELTA_KIB
        ),
        "max_concurrent_lanes": MAX_CONCURRENT_LANES,
        "max_retries": MAX_RETRIES,
        "benchmark_source_ordinal": 0,
        "worker_science_invocation_count": 54,
        "independent_verifier_science_invocation_count": 54,
        "finalizer_science_invocation_count": 0,
        "total_science_invocation_count": 108,
        "additional_science_invocations_licensed": False,
        "benchmark_result_fields_hidden": [
            "rank", "book", "support_observation", "comparative_effect",
        ],
        "gate_arithmetic": "integer-only-inclusive-upper-bounds",
    }
    return _self_hash(body, "compute_gate_sha256")


def validate_compute_gate_v1(value: object) -> dict[str, object]:
    expected = frozen_compute_gate_v1()
    if not isinstance(value, Mapping) or canonical_json(value) != canonical_json(expected):
        _fail("numeric compute gate differs from the frozen production gate")
    return expected


def _regular_file_bytes(path: Path, *, label: str) -> bytes:
    if not path.is_absolute():
        _fail(f"{label} must be absolute")
    try:
        if path.is_symlink() or not path.is_file():
            _fail(f"{label} must be a regular non-symlink file")
        raw = path.read_bytes()
    except T230TransportError:
        raise
    except OSError as exc:
        raise T230TransportError(f"{label} read failed") from exc
    if not raw:
        _fail(f"{label} cannot be empty")
    return raw


def build_source_snapshot_v1(
    *, repository_root: Path, source_commit_sha: str
) -> dict[str, object]:
    if not repository_root.is_absolute() or not repository_root.is_dir():
        _fail("source snapshot repository root differs")
    if not isinstance(source_commit_sha, str) or _COMMIT.fullmatch(source_commit_sha) is None:
        _fail("source snapshot commit differs")
    rows: list[dict[str, object]] = []
    for ordinal, relative in enumerate(SOURCE_SNAPSHOT_PATHS):
        raw = _regular_file_bytes(
            repository_root / relative, label=f"source snapshot file[{ordinal}]"
        )
        rows.append({
            "path": relative,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    body = {
        "schema_version": SOURCE_SNAPSHOT_SCHEMA,
        "source_commit_sha": source_commit_sha,
        "repository_root": str(REPOSITORY_ROOT),
        "files": rows,
        "files_sha256": sha256(canonical_json(rows)).hexdigest(),
        "file_count": len(rows),
        "contains_real_git_checkout": True,
        "contains_literal_g0_runtime_receipts": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "source_snapshot_sha256")


def validate_source_snapshot_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("source snapshot must be one object")
    item = dict(value)
    expected_keys = {
        "schema_version", "source_commit_sha", "repository_root", "files",
        "files_sha256", "file_count", "contains_real_git_checkout",
        "contains_literal_g0_runtime_receipts", *_FALSE_AUTHORITY_FIELDS,
        "source_snapshot_sha256",
    }
    if set(item) != expected_keys:
        _fail("source snapshot fields differ")
    _validate_self_hash(item, field="source_snapshot_sha256", label="source snapshot")
    _false_authorities(item, label="source snapshot")
    rows = item.get("files")
    if not isinstance(rows, list) or len(rows) != len(SOURCE_SNAPSHOT_PATHS):
        _fail("source snapshot file count differs")
    normalized: list[dict[str, object]] = []
    for ordinal, expected_path in enumerate(SOURCE_SNAPSHOT_PATHS):
        row = rows[ordinal]
        if not isinstance(row, Mapping) or set(row) != {"path", "sha256", "bytes"}:
            _fail("source snapshot file row differs")
        if (
            row.get("path") != expected_path
            or not isinstance(row.get("sha256"), str)
            or _SHA256.fullmatch(str(row["sha256"])) is None
            or type(row.get("bytes")) is not int
            or int(row["bytes"]) < 1
        ):
            _fail(f"source snapshot file[{ordinal}] differs")
        normalized.append(dict(row))
    if (
        item.get("schema_version") != SOURCE_SNAPSHOT_SCHEMA
        or not isinstance(item.get("source_commit_sha"), str)
        or _COMMIT.fullmatch(str(item["source_commit_sha"])) is None
        or item.get("repository_root") != str(REPOSITORY_ROOT)
        or item.get("file_count") != len(normalized)
        or item.get("files_sha256") != sha256(canonical_json(normalized)).hexdigest()
        or item.get("contains_real_git_checkout") is not True
        or item.get("contains_literal_g0_runtime_receipts") is not True
    ):
        _fail("source snapshot frozen surface differs")
    return item


def validate_runtime_source_snapshot_v1(
    value: object, *, repository_root: Path
) -> dict[str, object]:
    snapshot = validate_source_snapshot_v1(value)
    if repository_root != REPOSITORY_ROOT or not (repository_root / ".git").is_dir():
        _fail("runtime source snapshot is not in the literal real Git checkout")
    rows = {str(row["path"]): row for row in snapshot["files"]}
    for path in SOURCE_SNAPSHOT_PATHS:
        raw = _regular_file_bytes(
            repository_root / path, label=f"runtime source snapshot file {path}"
        )
        row = rows[path]
        if len(raw) != row["bytes"] or sha256(raw).hexdigest() != row["sha256"]:
            _fail(f"runtime source snapshot file drifted: {path}")
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repository_root,
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout.decode("ascii").strip()
        status = subprocess.run(
            [
                "git", "status", "--porcelain=v1", "--untracked-files=all",
                "--", *_TRACKED_SOURCE_SNAPSHOT_PATHS,
            ],
            cwd=repository_root, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        if head != snapshot["source_commit_sha"] or status != b"":
            _fail("runtime source snapshot Git HEAD/status differs")
        for path in _TRACKED_SOURCE_SNAPSHOT_PATHS:
            committed = subprocess.run(
                ["git", "show", f"{head}:{path}"], cwd=repository_root,
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ).stdout
            if committed != _regular_file_bytes(
                repository_root / path,
                label=f"runtime committed source snapshot file {path}",
            ):
                _fail(f"runtime committed source snapshot bytes differ: {path}")
    except T230TransportError:
        raise
    except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        raise T230TransportError("runtime source snapshot Git replay failed") from exc
    return snapshot


@dataclass(frozen=True)
class SnapshotGitAdapter:
    """Real-checkout callbacks constrained by the baked exact source snapshot."""

    repository_root: Path
    snapshot: Mapping[str, object]

    def _rows(self) -> dict[str, Mapping[str, object]]:
        retained = validate_source_snapshot_v1(self.snapshot)
        return {str(row["path"]): row for row in retained["files"]}

    def _verified(self, relative_path: str) -> bytes:
        row = self._rows().get(relative_path)
        if row is None:
            _fail(f"source snapshot does not license {relative_path}")
        raw = _regular_file_bytes(
            self.repository_root / relative_path,
            label=f"source snapshot runtime file {relative_path}",
        )
        if len(raw) != row["bytes"] or sha256(raw).hexdigest() != row["sha256"]:
            _fail(f"source snapshot runtime file drifted: {relative_path}")
        return raw

    def git_head(self, repository_root: Path) -> str:
        if repository_root != self.repository_root or not (repository_root / ".git").is_dir():
            _fail("runtime is not the literal real Git checkout")
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository_root,
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            retained = completed.stdout.decode("ascii").strip()
        except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
            raise T230TransportError("runtime Git HEAD failed") from exc
        if retained != validate_source_snapshot_v1(self.snapshot)["source_commit_sha"]:
            _fail("runtime Git HEAD differs from the baked source snapshot")
        return retained

    def git_blob(
        self, repository_root: Path, commit: str, relative_path: str
    ) -> bytes:
        if repository_root != self.repository_root or commit != self.git_head(repository_root):
            _fail("runtime Git blob commit differs")
        try:
            completed = subprocess.run(
                ["git", "show", f"{commit}:{relative_path}"],
                cwd=repository_root, check=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise T230TransportError("runtime Git blob read failed") from exc
        expected = self._verified(relative_path)
        if completed.stdout != expected:
            _fail(f"runtime Git blob differs: {relative_path}")
        return completed.stdout

    def git_status(
        self, repository_root: Path, relative_paths: Sequence[str]
    ) -> bytes:
        if repository_root != self.repository_root:
            _fail("runtime Git status root differs")
        retained_paths = tuple(relative_paths)
        if (
            not retained_paths
            or len(set(retained_paths)) != len(retained_paths)
            or any(
                relative not in _TRACKED_SOURCE_SNAPSHOT_PATHS
                for relative in retained_paths
            )
        ):
            _fail("runtime Git status path set is outside the baked snapshot")
        for relative in retained_paths:
            self._verified(relative)
        try:
            completed = subprocess.run(
                [
                    "git", "status", "--porcelain=v1", "--untracked-files=all",
                    "--", *retained_paths,
                ],
                cwd=repository_root, check=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise T230TransportError("runtime Git status failed") from exc
        if completed.stdout != b"":
            _fail("runtime critical Git paths are dirty")
        return completed.stdout


def build_image_evidence_v1(
    *, repository_root: Path, source_snapshot: Mapping[str, object], immutable_image: object
) -> dict[str, object]:
    snapshot = validate_source_snapshot_v1(source_snapshot)
    image = _image(immutable_image, label="post-build immutable image")
    rows_by_path = {str(row["path"]): dict(row) for row in snapshot["files"]}
    implementation_rows = [rows_by_path[path] for path in execution._IMPLEMENTATION_PATHS]
    file_bytes = {
        path: _regular_file_bytes(
            repository_root / path, label=f"image evidence file {path}"
        )
        for path in execution._IMPLEMENTATION_PATHS
    }
    for path, raw in file_bytes.items():
        row = rows_by_path[path]
        if len(raw) != row["bytes"] or sha256(raw).hexdigest() != row["sha256"]:
            _fail(f"post-build implementation bytes drifted: {path}")
    callables = execution._critical_callable_rows(file_bytes)
    runtime_facts = execution._runtime_facts()
    body = {
        "schema_version": execution.IMAGE_EVIDENCE_SCHEMA,
        "source_commit_sha": snapshot["source_commit_sha"],
        "immutable_image": image,
        "implementation_files": implementation_rows,
        "implementation_files_sha256": batch.canonical_sha256(implementation_rows),
        "critical_callables": callables,
        "critical_callables_sha256": batch.canonical_sha256(callables),
        "runtime_facts": runtime_facts,
        "build_provenance": {
            "builder_id": "cloud-build-immutable-image-evidence-v1",
            "source_commit_sha": snapshot["source_commit_sha"],
            "immutable_image_digest": image["digest"],
            "implementation_files_sha256": batch.canonical_sha256(
                implementation_rows
            ),
            "critical_callables_sha256": batch.canonical_sha256(callables),
            "runtime_facts_sha256": batch.canonical_sha256(runtime_facts),
        },
        "release_image_evidence": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["image_evidence_sha256"] = batch.canonical_sha256(body)
    try:
        return execution._validate_image_evidence(body)
    except Exception as exc:
        raise T230TransportError(f"post-build image evidence differs: {exc}") from exc


def _validate_image_evidence_structural_v1(
    value: object,
) -> dict[str, object]:
    """Validate D-produced evidence without comparing controller runtimes."""
    item = dict(execution._mapping(value, label="structural image evidence"))
    execution._exact_keys(
        item, execution._IMAGE_EVIDENCE_KEYS, label="structural image evidence"
    )
    execution._false_authorities(item, label="structural image evidence")
    execution._guard_nested_authority_keys(
        item, label="structural image evidence"
    )
    execution._validate_self_hash(
        item,
        field="image_evidence_sha256",
        label="structural image evidence",
    )
    source_commit = execution._commit(
        item.get("source_commit_sha"), label="structural evidence commit"
    )
    image = execution._image(
        item.get("immutable_image"), label="structural evidence image"
    )
    files = execution._sequence(
        item.get("implementation_files"), label="structural evidence files"
    )
    if len(files) != len(execution._IMPLEMENTATION_PATHS):
        _fail("structural image evidence file count differs")
    normalized_files: list[dict[str, object]] = []
    for ordinal, expected_path in enumerate(execution._IMPLEMENTATION_PATHS):
        row = dict(
            execution._mapping(files[ordinal], label=f"evidence file[{ordinal}]")
        )
        execution._exact_keys(
            row, execution._IMAGE_FILE_KEYS, label=f"evidence file[{ordinal}]"
        )
        if (
            row.get("path") != expected_path
            or type(row.get("bytes")) is not int
            or int(row["bytes"]) < 1
        ):
            _fail("structural image evidence file row differs")
        execution._sha(row.get("sha256"), label="evidence file SHA")
        normalized_files.append(row)
    callables = execution._sequence(
        item.get("critical_callables"), label="structural evidence callables"
    )
    if len(callables) != len(execution._CRITICAL_CALLABLE_SPECS):
        _fail("structural image evidence callable count differs")
    for ordinal, ((expected_path, expected_name), raw_row) in enumerate(
        zip(execution._CRITICAL_CALLABLE_SPECS, callables, strict=True)
    ):
        row = execution._mapping(
            raw_row, label=f"structural evidence callable[{ordinal}]"
        )
        if (
            frozenset(row)
            != {"path", "qualified_name", "source_sha256", "source_bytes"}
            or row.get("path") != expected_path
            or row.get("qualified_name") != expected_name
            or type(row.get("source_bytes")) is not int
            or int(row["source_bytes"]) < 1
        ):
            _fail("structural image evidence callable row differs")
        execution._sha(row.get("source_sha256"), label="evidence callable SHA")
    runtime_facts = execution._mapping(
        item.get("runtime_facts"), label="structural evidence runtime facts"
    )
    provenance = execution._mapping(
        item.get("build_provenance"), label="structural evidence provenance"
    )
    if (
        item.get("schema_version") != execution.IMAGE_EVIDENCE_SCHEMA
        or item.get("release_image_evidence") is not True
        or item.get("implementation_files_sha256")
        != batch.canonical_sha256(normalized_files)
        or item.get("critical_callables_sha256")
        != batch.canonical_sha256(callables)
        or frozenset(provenance)
        != {
            "builder_id", "source_commit_sha", "immutable_image_digest",
            "implementation_files_sha256", "critical_callables_sha256",
            "runtime_facts_sha256",
        }
        or provenance.get("builder_id")
        != "cloud-build-immutable-image-evidence-v1"
        or provenance.get("source_commit_sha") != source_commit
        or provenance.get("immutable_image_digest") != image["digest"]
        or provenance.get("implementation_files_sha256")
        != item.get("implementation_files_sha256")
        or provenance.get("critical_callables_sha256")
        != item.get("critical_callables_sha256")
        or provenance.get("runtime_facts_sha256")
        != batch.canonical_sha256(runtime_facts)
    ):
        _fail("structural image evidence frozen surface differs")
    return item


def build_image_evidence_publication_binding_v1(
    *,
    source_snapshot: Mapping[str, object],
    immutable_image: object,
    image_evidence: Mapping[str, object],
) -> dict[str, object]:
    """Bind the digest-postdated evidence before its generation exists.

    The binding is intentionally independent of the future GCS generation.
    Its self-hash can therefore journal the create-once evidence publication,
    after which the full transport contract binds the returned exact identity.
    """
    snapshot = validate_source_snapshot_v1(source_snapshot)
    image = _image(immutable_image, label="evidence publication image")
    evidence = _validate_image_evidence_structural_v1(image_evidence)
    raw = canonical_json(evidence)
    if (
        evidence.get("source_commit_sha") != snapshot["source_commit_sha"]
        or evidence.get("immutable_image") != image
    ):
        _fail("evidence publication source/image binding differs")
    body = {
        "schema_version": IMAGE_EVIDENCE_PUBLICATION_BINDING_SCHEMA,
        "run_id": RUN_ID,
        "source_snapshot_sha256": snapshot["source_snapshot_sha256"],
        "source_commit_sha": snapshot["source_commit_sha"],
        "immutable_image": image,
        "target_uri": execution.image_evidence_uri_for_output_prefix(
            OUTPUT_PREFIX
        ),
        "expected_sha256": sha256(raw).hexdigest(),
        "expected_bytes": len(raw),
        "generation_not_known_before_create": True,
        "bucket_list_allowed": False,
        "latest_alias_allowed": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "image_evidence_publication_binding_sha256")


def _runtime_mount_contract() -> dict[str, object]:
    return {
        "volume_type": "in-memory",
        "volume_name": "foundry-t230-runtime-evidence",
        "mount_path": str(RUNTIME_EVIDENCE_PATH.parent),
        "target_path": str(RUNTIME_EVIDENCE_PATH),
        "materialization": "generation-pinned-download-then-o_nofollow-create",
        "target_mode_octal": "0400",
        "target_owner": "root",
        "target_owner_uid": 0,
        "symlink_allowed": False,
        "gcs_fuse_allowed": False,
        "secret_projection_allowed": False,
        "exact_remote_local_bytes_required": True,
    }


def _transport_contract_body_v1(
    *,
    source_commit_sha: str,
    source_snapshot_sha256: str,
    immutable_image: object,
    image_evidence_identity: Mapping[str, object],
    prefreeze_release_gate: Mapping[str, object],
) -> dict[str, object]:
    if _COMMIT.fullmatch(source_commit_sha) is None:
        _fail("transport source commit differs")
    if _SHA256.fullmatch(source_snapshot_sha256) is None:
        _fail("transport source snapshot hash differs")
    image = _image(immutable_image, label="transport immutable image")
    evidence = _identity(image_evidence_identity, label="image evidence")
    smoke_gate = validate_prefreeze_release_gate_v1(prefreeze_release_gate)
    if evidence["uri"] != execution.image_evidence_uri_for_output_prefix(OUTPUT_PREFIX):
        _fail("image evidence URI differs from the canonical output prefix")
    if (
        smoke_gate["source_commit_sha"] != source_commit_sha
        or smoke_gate["immutable_candidate_image"] != image
    ):
        _fail("prefreeze release gate source/image differs")
    body = {
        "schema_version": TRANSPORT_SCHEMA,
        "run_id": RUN_ID,
        "project": PROJECT,
        "region": REGION,
        "repository_root": str(REPOSITORY_ROOT),
        "source_commit_sha": source_commit_sha,
        "source_snapshot_sha256": source_snapshot_sha256,
        "source_snapshot_path": str(SOURCE_SNAPSHOT_PATH),
        "immutable_image": image,
        "image_evidence_identity": evidence,
        "prefreeze_release_gate": smoke_gate,
        "prefreeze_release_evidence": {
            "output_prefix": PREFREEZE_OUTPUT_PREFIX,
            "journal_prefix": PREFREEZE_JOURNAL_PREFIX,
            "launch_uri": PREFREEZE_SMOKE_LAUNCH_URI,
            "smoke_receipt_uri": PREFREEZE_SMOKE_RECEIPT_URI,
            "raw_time_v_uri": PREFREEZE_SMOKE_TIME_V_URI,
            "execution_projection_uri": PREFREEZE_SMOKE_EXECUTION_URI,
            "separate_from_canonical_t230_output_prefix": True,
            "canonical_t230_object_created_before_release_gate": False,
        },
        "output_prefix": OUTPUT_PREFIX,
        "transport_contract_uri": TRANSPORT_CONTRACT_URI,
        "compute_release_uri": COMPUTE_RELEASE_URI,
        "compute_gate": frozen_compute_gate_v1(),
        "benchmark_release": {
            "raw_time_v_uri": RAW_TIME_V_URI,
            "disposition_uri": BENCHMARK_DISPOSITION_URI,
            "execution_terminal_uri": BENCHMARK_EXECUTION_TERMINAL_URI,
            "benchmark_uri": BENCHMARK_URI,
            "compute_release_uri": COMPUTE_RELEASE_URI,
            "parser_implementation_sha256": EXPECTED_TIME_V_PARSER_SHA256,
            "scale_out_before_compute_release_allowed": False,
            "raw_time_v_generation_pinned": True,
            "raw_ready_and_terminal_abort_mutually_exclusive": True,
            "disposition_published_before_raw_time_v": True,
            "terminal_abort_requires_exact_execution_projection": True,
            "image_digest_bound": True,
            "timed_command": BENCHMARK_COMMAND,
            "worker_stage_and_result_bound": True,
            "partial_transaction_terminal_abort_uri": BENCHMARK_ABORT_URI,
            "worker_without_raw_time_requires_new_run_id": True,
            "raw_time_present_partial_transaction_resumable": True,
            "science_relaunch_during_resume_allowed": False,
        },
        "lanes": [dict(row) for row in LANE_CONTRACT],
        "runtime_mount": _runtime_mount_contract(),
        "publication_recovery": {
            "journal_prefix": JOURNAL_PREFIX,
            "intent_before_target": True,
            "direct_known_uri_recovery_only": True,
            "generation_pin_immediately_after_metadata_lookup": True,
            "bucket_list_allowed": False,
            "latest_alias_allowed": False,
            "equal_bytes_required": True,
            "different_bytes_terminal": True,
        },
        "launcher": {
            "max_concurrent_lanes": 2,
            "sequential_within_lane": True,
            "worker_and_verifier_are_distinct_executions": True,
            "finalizer_is_distinct_execution": True,
            "task_count_per_execution": 1,
            "parallelism_per_execution": 1,
            "max_retries": 0,
            "caller_selected_ordinal_allowed": False,
            "runtime_attempt_ordinal": 0,
            "durable_launch_request_before_cloud_execution": True,
            "launch_request_journal_proof_required_at_runtime": True,
            "exact_live_job_config_receipt_required_before_launch": True,
            "relaunch_after_consumed_request_allowed": False,
            "cloud_task_index": 0,
            "cloud_task_attempt": 0,
            "cloud_task_count": 1,
            "runtime_image_must_equal_contract_digest": True,
            "predecessor_chain_exactly_bound": True,
            "both_lane_controller_processes_always_joined": True,
        },
        "prospective_k20_modified": False,
        "support_rank_book_effect_fields_exposed_by_transport_before_panel_release": (
            False
        ),
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "transport_contract_sha256")


def build_transport_contract_v1(
    *,
    source_snapshot: Mapping[str, object],
    immutable_image: object,
    image_evidence_identity: Mapping[str, object],
    prefreeze_release_gate: Mapping[str, object],
) -> dict[str, object]:
    snapshot = validate_source_snapshot_v1(source_snapshot)
    return _transport_contract_body_v1(
        source_commit_sha=str(snapshot["source_commit_sha"]),
        source_snapshot_sha256=str(snapshot["source_snapshot_sha256"]),
        immutable_image=immutable_image,
        image_evidence_identity=image_evidence_identity,
        prefreeze_release_gate=prefreeze_release_gate,
    )


def validate_transport_contract_v1(value: object) -> dict[str, object]:
    """Structurally validate the self-contained controller contract."""
    if not isinstance(value, Mapping):
        _fail("transport contract must be one object")
    item = dict(value)
    _validate_self_hash(item, field="transport_contract_sha256", label="transport contract")
    _false_authorities(item, label="transport contract")
    expected = _transport_contract_body_v1(
        source_commit_sha=str(item.get("source_commit_sha", "")),
        source_snapshot_sha256=str(item.get("source_snapshot_sha256", "")),
        immutable_image=item.get("immutable_image"),
        image_evidence_identity=item.get("image_evidence_identity", {}),
        prefreeze_release_gate=item.get("prefreeze_release_gate", {}),
    )
    if canonical_json(item) != canonical_json(expected):
        _fail("transport contract differs from its frozen structural law")
    return item


def validate_transport_contract_against_baked_snapshot_v1(
    value: object,
) -> dict[str, object]:
    """Require the runtime image's real checkout and baked source snapshot."""
    item = validate_transport_contract_v1(value)
    snapshot_raw = _regular_file_bytes(SOURCE_SNAPSHOT_PATH, label="baked source snapshot")
    snapshot = validate_runtime_source_snapshot_v1(
        strict_json(snapshot_raw, label="baked source snapshot"),
        repository_root=REPOSITORY_ROOT,
    )
    expected = build_transport_contract_v1(
        source_snapshot=snapshot,
        immutable_image=item.get("immutable_image"),
        image_evidence_identity=item.get("image_evidence_identity", {}),
        prefreeze_release_gate=item.get("prefreeze_release_gate", {}),
    )
    if canonical_json(item) != canonical_json(expected):
        _fail("transport contract differs from its baked/image inputs")
    return item


def materialize_image_evidence_v1(
    *,
    raw: bytes,
    identity: Mapping[str, object],
    target: Path | None = None,
) -> dict[str, object]:
    if target is None:
        target = RUNTIME_EVIDENCE_PATH
    retained = _identity(identity, label="materialized image evidence")
    if (
        retained["uri"] != execution.image_evidence_uri_for_output_prefix(OUTPUT_PREFIX)
        or len(raw) != retained["bytes"]
        or sha256(raw).hexdigest() != retained["sha256"]
    ):
        _fail("materialized image evidence remote identity differs")
    body = strict_json(raw, label="materialized image evidence")
    try:
        execution._validate_image_evidence(body)
    except Exception as exc:
        raise T230TransportError(f"materialized image evidence is invalid: {exc}") from exc
    if target != RUNTIME_EVIDENCE_PATH or not hasattr(os, "O_NOFOLLOW"):
        _fail("image evidence target must be the literal no-follow runtime path")
    required_owner_uid = (
        0
        if target == execution.EXPECTED_BAKED_IMAGE_EVIDENCE_PATH
        else os.geteuid()
    )
    if (
        target == execution.EXPECTED_BAKED_IMAGE_EVIDENCE_PATH
        and os.geteuid() != 0
    ):
        _fail("production image evidence must be materialized by root")
    directory_fd: int | None = None
    file_fd: int | None = None
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        directory_fd = os.open("/", flags)
        for component in target.parts[1:-1]:
            try:
                next_fd = os.open(component, flags, dir_fd=directory_fd)
            except FileNotFoundError:
                os.mkdir(component, mode=0o700, dir_fd=directory_fd)
                next_fd = os.open(component, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        try:
            file_fd = os.open(
                target.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o400,
                dir_fd=directory_fd,
            )
        except FileExistsError:
            retained_raw, binding = execution._secure_read_regular_file(
                target, label="retained runtime image evidence"
            )
            if retained_raw != raw or binding["mode_octal"] != "0400":
                _fail("retained runtime image evidence differs")
            if binding["owner_uid"] != required_owner_uid:
                _fail("retained runtime image evidence owner differs")
            return {**binding, "remote_identity": retained}
        os.fchmod(file_fd, 0o400)
        offset = 0
        while offset < len(raw):
            written = os.write(file_fd, raw[offset:])
            if written < 1:
                _fail("runtime image evidence write made no progress")
            offset += written
        os.fsync(file_fd)
        info = os.fstat(file_fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != required_owner_uid
            or stat.S_IMODE(info.st_mode) != 0o400
            or info.st_size != len(raw)
        ):
            _fail("runtime image evidence owner/mode/link checks failed")
    except T230TransportError:
        raise
    except OSError as exc:
        raise T230TransportError("runtime image evidence materialization failed") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)
    retained_raw, binding = execution._secure_read_regular_file(
        target, label="new runtime image evidence"
    )
    if retained_raw != raw:
        _fail("runtime image evidence differs after secure reopen")
    return {**binding, "remote_identity": retained}


def _journal_uri(target_uri: str, expected_sha256: str, suffix: str) -> str:
    if not isinstance(target_uri, str):
        _fail("journal target URI differs")
    if target_uri.startswith(OUTPUT_PREFIX):
        journal_prefix = JOURNAL_PREFIX
    elif target_uri.startswith(PREFREEZE_OUTPUT_PREFIX):
        journal_prefix = PREFREEZE_JOURNAL_PREFIX
    else:
        _fail("journal target must be below one frozen output prefix")
    if not isinstance(expected_sha256, str) or _SHA256.fullmatch(
        expected_sha256
    ) is None:
        _fail("journal expected SHA-256 differs")
    if suffix not in {"intent", "completion"}:
        _fail("journal suffix differs")
    key = sha256(target_uri.encode("utf-8")).hexdigest()
    return f"{journal_prefix}{key}/{expected_sha256}.{suffix}.json"


def _exact_create_or_recover(
    backend: JournalBackend, *, uri: str, raw: bytes
) -> tuple[dict[str, object], bool]:
    created = True
    try:
        identity = _identity(backend.create(uri, raw), label="created object")
    except JournalObjectExists:
        created = False
        current_identity, current_raw = backend.read_known_uri(uri)
        identity = _identity(current_identity, label="recovered known-URI object")
        if current_raw != raw:
            _fail("known-URI recovery bytes differ")
    pinned = backend.read(identity)
    if pinned != raw or len(pinned) != identity["bytes"] or sha256(pinned).hexdigest() != identity["sha256"]:
        _fail("created/recovered object differs on generation-pinned reopen")
    return identity, created


@dataclass
class RecoverablePublisher:
    backend: JournalBackend
    publication_binding_sha256: str

    def publish(
        self, *, target_uri: str, raw: bytes, transition_id: str
    ) -> dict[str, object]:
        if (
            not isinstance(self.publication_binding_sha256, str)
            or _SHA256.fullmatch(self.publication_binding_sha256) is None
            or not isinstance(transition_id, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,95}", transition_id)
            or not isinstance(raw, bytes)
            or not raw
        ):
            _fail("recoverable publication inputs differ")
        intent_body = _self_hash({
            "schema_version": PUBLICATION_INTENT_SCHEMA,
            "run_id": RUN_ID,
            "transition_id": transition_id,
            "publication_binding_sha256": self.publication_binding_sha256,
            "target_uri": target_uri,
            "expected_sha256": sha256(raw).hexdigest(),
            "expected_bytes": len(raw),
            "automatic_retry_licensed": False,
            "bucket_list_used": False,
            "latest_alias_used": False,
        }, "publication_intent_sha256")
        intent_raw = canonical_json(intent_body)
        expected_sha256 = str(intent_body["expected_sha256"])
        intent_uri = _journal_uri(target_uri, expected_sha256, "intent")
        try:
            intent_identity = _identity(
                self.backend.create(intent_uri, intent_raw),
                label="created publication intent",
            )
            retained_intent = intent_body
        except JournalObjectExists:
            retained_identity_raw, retained_raw = self.backend.read_known_uri(
                intent_uri
            )
            intent_identity = _identity(
                retained_identity_raw, label="recovered publication intent"
            )
            if self.backend.read(intent_identity) != retained_raw:
                _fail("recovered publication intent differs on pinned reopen")
            retained_intent = strict_json(
                retained_raw, label="recovered publication intent"
            )
            _validate_self_hash(
                retained_intent,
                field="publication_intent_sha256",
                label="recovered publication intent",
            )
            comparable = {
                key: value for key, value in retained_intent.items()
                if key not in {"transition_id", "publication_intent_sha256"}
            }
            requested = {
                key: value for key, value in intent_body.items()
                if key not in {"transition_id", "publication_intent_sha256"}
            }
            if (
                comparable != requested
                or not isinstance(retained_intent.get("transition_id"), str)
                or not re.fullmatch(
                    r"[a-z0-9][a-z0-9-]{0,95}",
                    str(retained_intent["transition_id"]),
                )
            ):
                _fail("recovered publication intent binding differs")
        if self.backend.read(intent_identity) != canonical_json(retained_intent):
            _fail("publication intent differs on generation-pinned reopen")
        target_identity, target_created = _exact_create_or_recover(
            self.backend, uri=target_uri, raw=raw
        )
        completion_body = _self_hash({
            "schema_version": PUBLICATION_COMPLETION_SCHEMA,
            "run_id": RUN_ID,
            "transition_id": retained_intent["transition_id"],
            "publication_binding_sha256": self.publication_binding_sha256,
            "intent_identity": intent_identity,
            "target_identity": target_identity,
            "target_sha256_verified": True,
            "target_generation_pinned": True,
            "automatic_retry_licensed": False,
            "bucket_list_used": False,
            "latest_alias_used": False,
        }, "publication_completion_sha256")
        completion_identity, _completion_created = _exact_create_or_recover(
            self.backend,
            uri=_journal_uri(target_uri, expected_sha256, "completion"),
            raw=canonical_json(completion_body),
        )
        return {
            "intent_identity": intent_identity,
            "target_identity": target_identity,
            "completion_identity": completion_identity,
            "target_created": target_created,
        }


def recover_completed_publication(
    *,
    backend: JournalBackend,
    target_uri: str,
    publication_binding_sha256: str,
) -> tuple[dict[str, object], bytes]:
    """Recover one completed known target without listing or trusting latest."""
    if not isinstance(publication_binding_sha256, str) or _SHA256.fullmatch(
        publication_binding_sha256
    ) is None:
        _fail("recovery publication binding hash differs")
    # Resolve the one deterministic target name, immediately pin its returned
    # generation, and use the exact target SHA to address its journal.  This
    # permits a later attempt after an intent-only crash without listing old
    # abandoned intents or introducing a mutable "current" journal pointer.
    known_target_identity, known_target_raw = backend.read_known_uri(target_uri)
    known_target = _identity(known_target_identity, label="known recovery target")
    if (
        known_target["uri"] != target_uri
        or backend.read(known_target) != known_target_raw
        or len(known_target_raw) != known_target["bytes"]
        or sha256(known_target_raw).hexdigest() != known_target["sha256"]
    ):
        _fail("known recovery target differs on pinned reopen")
    expected_sha256 = str(known_target["sha256"])
    completion_identity_raw, completion_raw = backend.read_known_uri(
        _journal_uri(target_uri, expected_sha256, "completion")
    )
    completion_identity = _identity(
        completion_identity_raw, label="recovery completion"
    )
    if backend.read(completion_identity) != completion_raw:
        _fail("recovery completion differs on pinned reopen")
    completion = strict_json(completion_raw, label="recovery completion")
    if set(completion) != {
        "schema_version", "run_id", "transition_id",
        "publication_binding_sha256", "intent_identity", "target_identity",
        "target_sha256_verified", "target_generation_pinned",
        "automatic_retry_licensed", "bucket_list_used", "latest_alias_used",
        "publication_completion_sha256",
    }:
        _fail("recovery completion fields differ")
    _validate_self_hash(
        completion,
        field="publication_completion_sha256",
        label="recovery completion",
    )
    if (
        completion.get("schema_version") != PUBLICATION_COMPLETION_SCHEMA
        or completion.get("run_id") != RUN_ID
        or completion.get("publication_binding_sha256")
        != publication_binding_sha256
        or completion.get("target_sha256_verified") is not True
        or completion.get("target_generation_pinned") is not True
        or completion.get("automatic_retry_licensed") is not False
        or completion.get("bucket_list_used") is not False
        or completion.get("latest_alias_used") is not False
    ):
        _fail("recovery completion frozen surface differs")
    target_identity = _identity(
        completion.get("target_identity"), label="recovery target"
    )
    if target_identity != known_target:
        _fail("recovery target identity differs from direct known-URI pin")
    target_raw = backend.read(target_identity)
    if (
        len(target_raw) != target_identity["bytes"]
        or sha256(target_raw).hexdigest() != target_identity["sha256"]
    ):
        _fail("recovery target differs on pinned reopen")
    intent_identity = _identity(
        completion.get("intent_identity"), label="recovery intent"
    )
    intent_raw = backend.read(intent_identity)
    intent = strict_json(intent_raw, label="recovery intent")
    if set(intent) != {
        "schema_version", "run_id", "transition_id",
        "publication_binding_sha256", "target_uri", "expected_sha256",
        "expected_bytes", "automatic_retry_licensed", "bucket_list_used",
        "latest_alias_used", "publication_intent_sha256",
    }:
        _fail("recovery intent fields differ")
    _validate_self_hash(
        intent, field="publication_intent_sha256", label="recovery intent"
    )
    if (
        intent_identity["uri"]
        != _journal_uri(target_uri, expected_sha256, "intent")
        or intent.get("schema_version") != PUBLICATION_INTENT_SCHEMA
        or intent.get("run_id") != RUN_ID
        or intent.get("publication_binding_sha256")
        != publication_binding_sha256
        or intent.get("transition_id") != completion.get("transition_id")
        or intent.get("target_uri") != target_uri
        or intent.get("expected_sha256") != target_identity["sha256"]
        or intent.get("expected_bytes") != target_identity["bytes"]
        or intent.get("automatic_retry_licensed") is not False
        or intent.get("bucket_list_used") is not False
        or intent.get("latest_alias_used") is not False
    ):
        _fail("recovery intent/target binding differs")
    return target_identity, target_raw


def recover_or_complete_publication(
    *,
    backend: JournalBackend,
    target_uri: str,
    publication_binding_sha256: str,
) -> tuple[dict[str, object], bytes]:
    """Recover a target even when its create succeeded before completion.

    The exact target name is resolved once and pinned.  Its content hash
    deterministically names the only admissible intent/completion pair; no
    bucket listing, mutable alias, or caller-selected candidate is involved.
    """
    try:
        return recover_completed_publication(
            backend=backend,
            target_uri=target_uri,
            publication_binding_sha256=publication_binding_sha256,
        )
    except FileNotFoundError:
        target_identity_raw, target_raw = backend.read_known_uri(target_uri)
        target_identity = _identity(
            target_identity_raw, label="partial-publication target"
        )
        if (
            backend.read(target_identity) != target_raw
            or len(target_raw) != target_identity["bytes"]
            or sha256(target_raw).hexdigest() != target_identity["sha256"]
        ):
            _fail("partial-publication target differs on pinned reopen")
        intent_uri = _journal_uri(
            target_uri, str(target_identity["sha256"]), "intent"
        )
        intent_identity_raw, intent_raw = backend.read_known_uri(intent_uri)
        intent_identity = _identity(
            intent_identity_raw, label="partial-publication intent"
        )
        if backend.read(intent_identity) != intent_raw:
            _fail("partial-publication intent differs on pinned reopen")
        intent = strict_json(intent_raw, label="partial-publication intent")
        _validate_self_hash(
            intent,
            field="publication_intent_sha256",
            label="partial-publication intent",
        )
        if (
            intent.get("schema_version") != PUBLICATION_INTENT_SCHEMA
            or intent.get("run_id") != RUN_ID
            or intent.get("publication_binding_sha256")
            != publication_binding_sha256
            or intent.get("target_uri") != target_uri
            or intent.get("expected_sha256") != target_identity["sha256"]
            or intent.get("expected_bytes") != target_identity["bytes"]
            or not isinstance(intent.get("transition_id"), str)
        ):
            _fail("partial-publication intent binding differs")
        RecoverablePublisher(
            backend, publication_binding_sha256
        ).publish(
            target_uri=target_uri,
            raw=target_raw,
            transition_id=str(intent["transition_id"]),
        )
        return recover_completed_publication(
            backend=backend,
            target_uri=target_uri,
            publication_binding_sha256=publication_binding_sha256,
        )


def validate_publication_proof_v1(
    *,
    target_identity: Mapping[str, object],
    intent_identity: Mapping[str, object],
    completion_identity: Mapping[str, object],
    publication_binding_sha256: str,
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    """Validate a supplied exact intent/target/completion chain without listing."""
    target = _identity(target_identity, label="publication-proof target")
    intent_id = _identity(intent_identity, label="publication-proof intent")
    completion_id = _identity(
        completion_identity, label="publication-proof completion"
    )
    if (
        not isinstance(publication_binding_sha256, str)
        or _SHA256.fullmatch(publication_binding_sha256) is None
        or intent_id["uri"]
        != _journal_uri(str(target["uri"]), str(target["sha256"]), "intent")
        or completion_id["uri"]
        != _journal_uri(
            str(target["uri"]), str(target["sha256"]), "completion"
        )
    ):
        _fail("publication-proof deterministic identity differs")
    target_raw = read_exact(target)
    intent_raw = read_exact(intent_id)
    completion_raw = read_exact(completion_id)
    if (
        len(target_raw) != target["bytes"]
        or sha256(target_raw).hexdigest() != target["sha256"]
    ):
        _fail("publication-proof target content differs")
    intent = strict_json(intent_raw, label="publication-proof intent")
    completion = strict_json(completion_raw, label="publication-proof completion")
    if set(intent) != {
        "schema_version", "run_id", "transition_id",
        "publication_binding_sha256", "target_uri", "expected_sha256",
        "expected_bytes", "automatic_retry_licensed", "bucket_list_used",
        "latest_alias_used", "publication_intent_sha256",
    } or set(completion) != {
        "schema_version", "run_id", "transition_id",
        "publication_binding_sha256", "intent_identity", "target_identity",
        "target_sha256_verified", "target_generation_pinned",
        "automatic_retry_licensed", "bucket_list_used", "latest_alias_used",
        "publication_completion_sha256",
    }:
        _fail("publication-proof fields differ")
    _validate_self_hash(
        intent, field="publication_intent_sha256", label="publication-proof intent"
    )
    _validate_self_hash(
        completion,
        field="publication_completion_sha256",
        label="publication-proof completion",
    )
    if (
        intent.get("schema_version") != PUBLICATION_INTENT_SCHEMA
        or intent.get("run_id") != RUN_ID
        or intent.get("publication_binding_sha256")
        != publication_binding_sha256
        or intent.get("target_uri") != target["uri"]
        or intent.get("expected_sha256") != target["sha256"]
        or intent.get("expected_bytes") != target["bytes"]
        or not isinstance(intent.get("transition_id"), str)
        or re.fullmatch(
            r"[a-z0-9][a-z0-9-]{0,95}", str(intent.get("transition_id"))
        ) is None
        or intent.get("automatic_retry_licensed") is not False
        or intent.get("bucket_list_used") is not False
        or intent.get("latest_alias_used") is not False
        or completion.get("schema_version") != PUBLICATION_COMPLETION_SCHEMA
        or completion.get("run_id") != RUN_ID
        or completion.get("transition_id") != intent.get("transition_id")
        or completion.get("publication_binding_sha256")
        != publication_binding_sha256
        or completion.get("intent_identity") != intent_id
        or completion.get("target_identity") != target
        or completion.get("target_sha256_verified") is not True
        or completion.get("target_generation_pinned") is not True
        or completion.get("automatic_retry_licensed") is not False
        or completion.get("bucket_list_used") is not False
        or completion.get("latest_alias_used") is not False
    ):
        _fail("publication-proof chain differs")
    return {
        "intent_identity": intent_id,
        "target_identity": target,
        "completion_identity": completion_id,
    }


def _stage_uri(operation: str, source_ordinal: int | None) -> str:
    if operation == "prepare" and source_ordinal is None:
        return TRANSPORT_PREFIX + "stages/prepare.json"
    if operation == "finish-panel" and source_ordinal is None:
        return TRANSPORT_PREFIX + "stages/finish-panel.json"
    if operation in {"run-slate", "verify-slate"} and type(source_ordinal) is int:
        lane_for_source_ordinal(source_ordinal)
        return (
            TRANSPORT_PREFIX
            + f"stages/{operation}/{source_ordinal:02d}.json"
        )
    _fail("stage operation/source ordinal combination differs")


def stage_start_uri(
    operation: str,
    source_ordinal: int | None,
    runtime_attempt_ordinal: int,
) -> str:
    _stage_uri(operation, source_ordinal)
    if (
        type(runtime_attempt_ordinal) is not int
        or not 0 <= runtime_attempt_ordinal <= execution.MAX_RUNTIME_ATTEMPT_ORDINAL
    ):
        _fail("stage-start attempt ordinal differs")
    member = "panel" if source_ordinal is None else f"{source_ordinal:02d}"
    return (
        TRANSPORT_PREFIX
        +
        f"stage-starts/{operation}/{member}/"
        f"attempt-{runtime_attempt_ordinal:02d}.json"
    )


def launch_request_uri(
    operation: str, source_ordinal: int | None
) -> str:
    _stage_uri(operation, source_ordinal)
    member = "panel" if source_ordinal is None else f"{source_ordinal:02d}"
    return TRANSPORT_PREFIX + f"launch-requests/{operation}/{member}.json"


def job_config_uri(job: str) -> str:
    if job not in {LANE_A_JOB, LANE_B_JOB}:
        _fail("job-config job differs")
    return TRANSPORT_PREFIX + f"job-configs/{job}.json"


def build_job_config_v1(
    *,
    transport_contract_identity: Mapping[str, object],
    transport_contract: Mapping[str, object],
    observed_config: Mapping[str, object],
    job: str,
) -> dict[str, object]:
    """Bind one exact post-configure Cloud Run describe projection."""
    contract = validate_transport_contract_v1(transport_contract)
    contract_identity = _identity(
        transport_contract_identity, label="job-config transport contract"
    )
    contract_raw = canonical_json(contract)
    if (
        contract_identity["uri"] != TRANSPORT_CONTRACT_URI
        or contract_identity["sha256"] != sha256(contract_raw).hexdigest()
        or contract_identity["bytes"] != len(contract_raw)
    ):
        _fail("job-config transport contract identity differs")
    job_config_uri(job)
    if not isinstance(observed_config, Mapping):
        _fail("observed job config must be one object")
    observed = dict(observed_config)
    volume = observed.get("runtime_evidence_volume")
    if (
        set(observed) != {
            "job", "image", "service_account", "cpu", "memory",
            "task_count", "parallelism", "max_retries",
            "task_timeout_seconds", "runtime_evidence_volume",
            "cloud_describe_exactly_validated",
        }
        or observed.get("job") != job
        or observed.get("image") != contract["immutable_image"]["uri"]
        or not isinstance(observed.get("service_account"), str)
        or re.fullmatch(
            r"[a-z0-9][a-z0-9.-]{4,62}@[a-z0-9.-]+\.gserviceaccount\.com",
            str(observed.get("service_account")),
        ) is None
        or observed.get("cpu") != "8"
        or observed.get("memory") != "32Gi"
        or observed.get("task_count") != 1
        or observed.get("parallelism") != 1
        or observed.get("max_retries") != 0
        or observed.get("task_timeout_seconds") != TASK_TIMEOUT_SECONDS
        or observed.get("cloud_describe_exactly_validated") is not True
        or volume != {
            "type": "in-memory",
            "name": "foundry-t230-runtime-evidence",
            "size_limit": "1Mi",
            "mount_path": "/etc/nfl-dfs",
        }
    ):
        _fail("observed Cloud Run job config differs")
    body = {
        "schema_version": JOB_CONFIG_SCHEMA,
        "run_id": RUN_ID,
        "transport_contract_identity": contract_identity,
        "transport_contract_sha256": contract["transport_contract_sha256"],
        "job": job,
        "observed_config": observed,
        "observed_config_sha256": sha256(canonical_json(observed)).hexdigest(),
        "job_config_uri": job_config_uri(job),
        "exact_live_describe_validated": True,
        "required_before_launch_request": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "job_config_sha256")


def reopen_job_config_v1(
    *,
    job_config_identity: Mapping[str, object],
    transport_contract_identity: Mapping[str, object],
    transport_contract: Mapping[str, object],
    job: str,
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    identity = _identity(job_config_identity, label="job config")
    if identity["uri"] != job_config_uri(job):
        _fail("job-config URI differs")
    raw = read_exact(identity)
    body = strict_json(raw, label="job config")
    observed = body.get("observed_config")
    if not isinstance(observed, Mapping):
        _fail("job observed config differs")
    expected = build_job_config_v1(
        transport_contract_identity=transport_contract_identity,
        transport_contract=transport_contract,
        observed_config=observed,
        job=job,
    )
    if (
        raw != canonical_json(expected)
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail("job config differs after exact replay")
    return expected


def _expected_stage_predecessor_uris(
    operation: str, source_ordinal: int | None
) -> list[str]:
    _stage_uri(operation, source_ordinal)
    if operation == "prepare":
        return []
    if operation == "verify-slate":
        return [_stage_uri("run-slate", source_ordinal)]
    if operation == "run-slate" and source_ordinal in {0, 28}:
        return [_stage_uri("prepare", None)]
    if operation == "run-slate":
        return [_stage_uri("verify-slate", int(source_ordinal) - 1)]
    return [lane_ledger_uri(0), lane_ledger_uri(1)]


def build_launch_request_v1(
    *,
    transport_contract_identity: Mapping[str, object],
    transport_contract: Mapping[str, object],
    operation: str,
    source_ordinal: int | None,
    predecessor_identities: Sequence[Mapping[str, object]],
    job_config_identity: Mapping[str, object],
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    """Consume the sole globally durable permission to launch one stage."""
    contract = validate_transport_contract_v1(transport_contract)
    contract_identity = _identity(
        transport_contract_identity, label="launch transport contract"
    )
    contract_raw = canonical_json(contract)
    if (
        contract_identity["uri"] != TRANSPORT_CONTRACT_URI
        or contract_identity["sha256"] != sha256(contract_raw).hexdigest()
        or contract_identity["bytes"] != len(contract_raw)
    ):
        _fail("launch transport contract identity differs")
    predecessors = [
        _identity(value, label=f"launch predecessor[{ordinal}]")
        for ordinal, value in enumerate(predecessor_identities)
    ]
    if [str(value["uri"]) for value in predecessors] != (
        _expected_stage_predecessor_uris(operation, source_ordinal)
    ):
        _fail("launch predecessor identities differ")
    if operation in {"prepare", "finish-panel"}:
        job = LANE_A_JOB
    else:
        job = str(lane_for_source_ordinal(int(source_ordinal))["reuse_job"])
    config_identity = _identity(job_config_identity, label="launch job config")
    config = reopen_job_config_v1(
        job_config_identity=config_identity,
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        job=job,
        read_exact=read_exact,
    )
    body = {
        "schema_version": LAUNCH_REQUEST_SCHEMA,
        "run_id": RUN_ID,
        "transport_contract_identity": contract_identity,
        "transport_contract_sha256": contract["transport_contract_sha256"],
        "operation": operation,
        "source_ordinal": source_ordinal,
        "runtime_attempt_ordinal": 0,
        "reuse_job": job,
        "job_config_identity": config_identity,
        "job_config_sha256": config["job_config_sha256"],
        "immutable_image": contract["immutable_image"],
        "predecessor_identities": predecessors,
        "predecessor_identities_sha256": sha256(
            canonical_json(predecessors)
        ).hexdigest(),
        "launch_request_uri": launch_request_uri(operation, source_ordinal),
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "request_consumed_even_if_execution_response_is_ambiguous": True,
        "relaunch_allowed": False,
        "bucket_list_used": False,
        "latest_alias_used": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "launch_request_sha256")


def reopen_launch_request_v1(
    *,
    launch_request_identity: Mapping[str, object],
    transport_contract_identity: Mapping[str, object],
    transport_contract: Mapping[str, object],
    operation: str,
    source_ordinal: int | None,
    predecessor_identities: Sequence[Mapping[str, object]],
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    """Exact-replay the create-before-execute permission for one stage."""
    identity = _identity(launch_request_identity, label="stage launch request")
    if identity["uri"] != launch_request_uri(operation, source_ordinal):
        _fail("stage launch-request URI differs")
    raw = read_exact(identity)
    retained = strict_json(raw, label="stage launch request")
    retained_job_config = retained.get("job_config_identity")
    if not isinstance(retained_job_config, Mapping):
        _fail("stage launch job-config identity differs")
    expected = build_launch_request_v1(
        transport_contract_identity=transport_contract_identity,
        transport_contract=transport_contract,
        operation=operation,
        source_ordinal=source_ordinal,
        predecessor_identities=predecessor_identities,
        job_config_identity=retained_job_config,
        read_exact=read_exact,
    )
    expected_raw = canonical_json(expected)
    if (
        not isinstance(raw, bytes)
        or raw != expected_raw
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail("stage launch request differs after exact replay")
    return expected


def recover_publication_proof_v1(
    *,
    backend: JournalBackend,
    target_uri: str,
    publication_binding_sha256: str,
) -> tuple[dict[str, object], bytes]:
    """Recover one completed journal and return its exact three-object proof."""
    target, raw = recover_or_complete_publication(
        backend=backend,
        target_uri=target_uri,
        publication_binding_sha256=publication_binding_sha256,
    )
    intent_identity, _intent_raw = backend.read_known_uri(
        _journal_uri(target_uri, str(target["sha256"]), "intent")
    )
    completion_identity, _completion_raw = backend.read_known_uri(
        _journal_uri(target_uri, str(target["sha256"]), "completion")
    )
    proof = validate_publication_proof_v1(
        target_identity=target,
        intent_identity=intent_identity,
        completion_identity=completion_identity,
        publication_binding_sha256=publication_binding_sha256,
        read_exact=backend.read,
    )
    return proof, raw


def build_stage_start_v1(
    *,
    transport_contract_sha256: str,
    operation: str,
    source_ordinal: int | None,
    runtime_attempt_ordinal: int,
    cloud_execution_name: str,
    cloud_job: str,
    cloud_task_index: int,
    cloud_task_attempt: int,
    cloud_task_count: int,
    runtime_image: object,
    launch_request_identity: Mapping[str, object],
    launch_publication_proof: Mapping[str, object],
    predecessor_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    uri = stage_start_uri(operation, source_ordinal, runtime_attempt_ordinal)
    if operation in {"prepare", "finish-panel"}:
        reuse_job = LANE_A_JOB
    else:
        reuse_job = str(lane_for_source_ordinal(int(source_ordinal))["reuse_job"])
    role = {
        "prepare": "preparer",
        "run-slate": "worker",
        "verify-slate": "verifier",
        "finish-panel": "finalizer",
    }[operation]
    normalized_predecessors = [
        _identity(value, label=f"stage predecessor[{ordinal}]")
        for ordinal, value in enumerate(predecessor_identities)
    ]
    expected_predecessor_uris = _expected_stage_predecessor_uris(
        operation, source_ordinal
    )
    if [str(value["uri"]) for value in normalized_predecessors] != (
        expected_predecessor_uris
    ):
        _fail("stage-start predecessor chain differs")
    image = _image(runtime_image, label="stage runtime image")
    launch_identity = _identity(
        launch_request_identity, label="stage launch request"
    )
    if not isinstance(launch_publication_proof, Mapping):
        _fail("stage launch publication proof differs")
    proof = {
        field: _identity(
            launch_publication_proof.get(field),
            label=f"stage launch publication {field}",
        )
        for field in ("intent_identity", "target_identity", "completion_identity")
    }
    if (
        not isinstance(transport_contract_sha256, str)
        or _SHA256.fullmatch(transport_contract_sha256) is None
        or runtime_attempt_ordinal != 0
        or not isinstance(cloud_execution_name, str)
        or _EXECUTION.fullmatch(cloud_execution_name) is None
        or not cloud_execution_name.startswith(reuse_job + "-")
        or cloud_job != reuse_job
        or cloud_task_index != 0
        or cloud_task_attempt != 0
        or cloud_task_count != 1
        or launch_identity["uri"] != launch_request_uri(operation, source_ordinal)
        or proof["target_identity"] != launch_identity
        or proof["intent_identity"]["uri"]
        != _journal_uri(
            str(launch_identity["uri"]), str(launch_identity["sha256"]), "intent"
        )
        or proof["completion_identity"]["uri"]
        != _journal_uri(
            str(launch_identity["uri"]),
            str(launch_identity["sha256"]),
            "completion",
        )
    ):
        _fail("stage-start mechanics inputs differ")
    body = {
        "schema_version": STAGE_START_SCHEMA,
        "run_id": RUN_ID,
        "transport_contract_sha256": transport_contract_sha256,
        "operation": operation,
        "source_ordinal": source_ordinal,
        "runtime_attempt_ordinal": runtime_attempt_ordinal,
        "cloud_execution_name": cloud_execution_name,
        "cloud_job": cloud_job,
        "cloud_task_index": cloud_task_index,
        "cloud_task_attempt": cloud_task_attempt,
        "cloud_task_count": cloud_task_count,
        "runtime_image": image,
        "launch_request_identity": launch_identity,
        "launch_publication_proof": proof,
        "runtime_uid": 0,
        "reuse_job": reuse_job,
        "execution_role": role,
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "stage_start_uri": uri,
        "predecessor_identities": normalized_predecessors,
        "predecessor_identities_sha256": sha256(
            canonical_json(normalized_predecessors)
        ).hexdigest(),
        "cloud_runtime_environment_attested": True,
        "configuration_fields_declared_not_runtime_environment": [
            "parallelism", "max_retries",
        ],
        "automatic_retry_licensed": False,
        "bucket_list_used": False,
        "latest_alias_used": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "stage_start_sha256")


def validate_stage_start_v1(
    value: object,
    *,
    transport_contract_sha256: str,
    operation: str,
    source_ordinal: int | None,
    runtime_attempt_ordinal: int,
    cloud_execution_name: str,
    cloud_job: str,
    cloud_task_index: int,
    cloud_task_attempt: int,
    cloud_task_count: int,
    runtime_image: object,
    launch_request_identity: Mapping[str, object],
    launch_publication_proof: Mapping[str, object],
    predecessor_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("stage start must be one object")
    expected = build_stage_start_v1(
        transport_contract_sha256=transport_contract_sha256,
        operation=operation,
        source_ordinal=source_ordinal,
        runtime_attempt_ordinal=runtime_attempt_ordinal,
        cloud_execution_name=cloud_execution_name,
        cloud_job=cloud_job,
        cloud_task_index=cloud_task_index,
        cloud_task_attempt=cloud_task_attempt,
        cloud_task_count=cloud_task_count,
        runtime_image=runtime_image,
        launch_request_identity=launch_request_identity,
        launch_publication_proof=launch_publication_proof,
        predecessor_identities=predecessor_identities,
    )
    if canonical_json(value) != canonical_json(expected):
        _fail("stage start differs from its exact launch binding")
    return expected


def reopen_stage_launch_authority_v1(
    *,
    stage_start: Mapping[str, object],
    transport_contract_sha256: str,
    operation: str,
    source_ordinal: int | None,
    runtime_attempt_ordinal: int,
    cloud_execution_name: str,
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    """Replay a stage start through its launch journal, contract, and job config."""
    start = validate_stage_start_v1(
        stage_start,
        transport_contract_sha256=transport_contract_sha256,
        operation=operation,
        source_ordinal=source_ordinal,
        runtime_attempt_ordinal=runtime_attempt_ordinal,
        cloud_execution_name=cloud_execution_name,
        cloud_job=str(stage_start.get("cloud_job", "")),
        cloud_task_index=stage_start.get("cloud_task_index"),
        cloud_task_attempt=stage_start.get("cloud_task_attempt"),
        cloud_task_count=stage_start.get("cloud_task_count"),
        runtime_image=stage_start.get("runtime_image"),
        launch_request_identity=stage_start.get("launch_request_identity", {}),
        launch_publication_proof=stage_start.get(
            "launch_publication_proof", {}
        ),
        predecessor_identities=stage_start.get("predecessor_identities", []),
    )
    launch_identity = _identity(
        start["launch_request_identity"], label="stage launch authority request"
    )
    proof = start["launch_publication_proof"]
    validate_publication_proof_v1(
        target_identity=launch_identity,
        intent_identity=proof["intent_identity"],
        completion_identity=proof["completion_identity"],
        publication_binding_sha256=transport_contract_sha256,
        read_exact=read_exact,
    )
    launch_raw = read_exact(launch_identity)
    retained_launch = strict_json(launch_raw, label="stage launch authority request")
    contract_identity = _identity(
        retained_launch.get("transport_contract_identity"),
        label="stage launch authority contract",
    )
    contract_raw = read_exact(contract_identity)
    contract = validate_transport_contract_v1(
        strict_json(contract_raw, label="stage launch authority contract")
    )
    if (
        contract_identity["uri"] != TRANSPORT_CONTRACT_URI
        or contract_identity["sha256"] != sha256(contract_raw).hexdigest()
        or contract_identity["bytes"] != len(contract_raw)
        or contract.get("transport_contract_sha256")
        != transport_contract_sha256
    ):
        _fail("stage launch authority contract differs")
    request = reopen_launch_request_v1(
        launch_request_identity=launch_identity,
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        operation=operation,
        source_ordinal=source_ordinal,
        predecessor_identities=start["predecessor_identities"],
        read_exact=read_exact,
    )
    return {
        "stage_start": start,
        "launch_publication_proof": proof,
        "launch_request": request,
        "transport_contract_identity": contract_identity,
    }


def build_benchmark_execution_terminal_v1(
    *,
    transport_contract_identity: Mapping[str, object],
    transport_contract: Mapping[str, object],
    worker_stage_receipt_identity: Mapping[str, object],
    observed_terminal: Mapping[str, object],
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    """Bind the terminal Cloud execution and its exact mechanics envelope."""
    contract = validate_transport_contract_v1(transport_contract)
    contract_identity = _identity(
        transport_contract_identity,
        label="benchmark terminal transport contract",
    )
    contract_raw = canonical_json(contract)
    if (
        contract_identity["uri"] != TRANSPORT_CONTRACT_URI
        or contract_identity["sha256"] != sha256(contract_raw).hexdigest()
        or contract_identity["bytes"] != len(contract_raw)
        or read_exact(contract_identity) != contract_raw
    ):
        _fail("benchmark terminal transport contract differs")
    worker_identity = _identity(
        worker_stage_receipt_identity,
        label="benchmark terminal worker stage",
    )
    worker_raw = read_exact(worker_identity)
    worker = validate_stage_receipt_v1(
        strict_json(worker_raw, label="benchmark terminal worker stage"),
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
    )
    start_identity = _identity(
        worker["stage_start_identity"],
        label="benchmark terminal worker start",
    )
    start = strict_json(
        read_exact(start_identity), label="benchmark terminal worker start"
    )
    launch = reopen_stage_launch_authority_v1(
        stage_start=start,
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
        runtime_attempt_ordinal=0,
        cloud_execution_name=str(worker["cloud_execution_name"]),
        read_exact=read_exact,
    )["launch_request"]
    job_config_identity = _identity(
        launch["job_config_identity"],
        label="benchmark terminal job config",
    )
    job = str(launch["reuse_job"])
    config = reopen_job_config_v1(
        job_config_identity=job_config_identity,
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        job=job,
        read_exact=read_exact,
    )
    if not isinstance(observed_terminal, Mapping):
        _fail("benchmark terminal observation must be one object")
    observed = dict(observed_terminal)
    expected_config = dict(config["observed_config"])
    config_projection = {
        field: observed.get(field) for field in expected_config
    }
    if (
        set(observed) != {
            *expected_config,
            "execution_name",
            "completed_status",
            "completion_time",
            "cloud_execution_describe_exactly_validated",
        }
        or observed.get("execution_name") != worker["cloud_execution_name"]
        or _EXECUTION.fullmatch(str(observed.get("execution_name", ""))) is None
        or observed.get("completed_status") not in {"True", "False"}
        or not isinstance(observed.get("completion_time"), str)
        or not 10 <= len(str(observed["completion_time"])) <= 64
        or not str(observed["completion_time"]).endswith("Z")
        or observed.get("cloud_execution_describe_exactly_validated") is not True
        or config_projection != expected_config
    ):
        _fail("benchmark terminal Cloud execution projection differs")
    body = {
        "schema_version": BENCHMARK_EXECUTION_TERMINAL_SCHEMA,
        "run_id": RUN_ID,
        "transport_contract_identity": contract_identity,
        "transport_contract_sha256": contract["transport_contract_sha256"],
        "worker_stage_receipt_identity": worker_identity,
        "worker_stage_receipt_sha256": worker["stage_receipt_sha256"],
        "worker_stage_start_identity": start_identity,
        "worker_cloud_execution_name": worker["cloud_execution_name"],
        "job_config_identity": job_config_identity,
        "job_config_sha256": config["job_config_sha256"],
        "observed_terminal": observed,
        "observed_terminal_sha256": sha256(
            canonical_json(observed)
        ).hexdigest(),
        "terminal_status_proved": True,
        "mechanics_only": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "benchmark_execution_terminal_sha256")


def reopen_benchmark_execution_terminal_v1(
    *,
    benchmark_execution_terminal_identity: Mapping[str, object],
    transport_contract_identity: Mapping[str, object],
    transport_contract: Mapping[str, object],
    worker_stage_receipt_identity: Mapping[str, object],
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    identity = _identity(
        benchmark_execution_terminal_identity,
        label="benchmark execution terminal",
    )
    if identity["uri"] != BENCHMARK_EXECUTION_TERMINAL_URI:
        _fail("benchmark execution terminal URI differs")
    raw = read_exact(identity)
    retained = strict_json(raw, label="benchmark execution terminal")
    observed = retained.get("observed_terminal")
    if not isinstance(observed, Mapping):
        _fail("benchmark execution terminal observation differs")
    expected = build_benchmark_execution_terminal_v1(
        transport_contract_identity=transport_contract_identity,
        transport_contract=transport_contract,
        worker_stage_receipt_identity=worker_stage_receipt_identity,
        observed_terminal=observed,
        read_exact=read_exact,
    )
    if (
        raw != canonical_json(expected)
        or identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
    ):
        _fail("benchmark execution terminal differs after exact replay")
    return expected


def build_stage_receipt_v1(
    *,
    transport_contract_sha256: str,
    operation: str,
    source_ordinal: int | None,
    runtime_attempt_ordinal: int | None,
    cloud_execution_name: str,
    stage_start_identity: Mapping[str, object],
    core_workflow_receipt: Mapping[str, object],
    exposed_identities: Mapping[str, Mapping[str, object]],
    wall_time_millis: int | None,
    peak_rss_kib: int | None,
) -> dict[str, object]:
    measurement_recorded = (
        type(wall_time_millis) is int and type(peak_rss_kib) is int
    )
    if (
        not isinstance(transport_contract_sha256, str)
        or _SHA256.fullmatch(transport_contract_sha256) is None
        or not isinstance(cloud_execution_name, str)
        or _EXECUTION.fullmatch(cloud_execution_name) is None
        or (wall_time_millis is None) != (peak_rss_kib is None)
        or (
            wall_time_millis is not None
            and (
                type(wall_time_millis) is not int
                or type(peak_rss_kib) is not int
            )
        )
        or (
            measurement_recorded
            and (int(wall_time_millis) < 0 or int(peak_rss_kib) < 0)
        )
    ):
        _fail("stage receipt mechanics inputs differ")
    _stage_uri(operation, source_ordinal)
    if (
        type(runtime_attempt_ordinal) is not int
        or not 0 <= runtime_attempt_ordinal <= execution.MAX_RUNTIME_ATTEMPT_ORDINAL
    ):
        _fail("stage runtime attempt ordinal differs")
    if not isinstance(core_workflow_receipt, Mapping):
        _fail("core workflow receipt differs")
    start_identity = _identity(stage_start_identity, label="stage start")
    if start_identity["uri"] != stage_start_uri(
        operation, source_ordinal, int(runtime_attempt_ordinal)
    ):
        _fail("stage-start identity URI differs")
    allowed_identity_fields = {
        "prepare": {"execution_authority_identity", "manifest_identity"},
        "run-slate": {"worker_runtime_measurement_identity", "result_identity"},
        "verify-slate": {
            "verifier_runtime_measurement_identity", "acceptance_identity",
        },
        "finish-panel": {
            "finalizer_runtime_measurement_identity", "panel_release_identity",
        },
    }[operation]
    if set(exposed_identities) != allowed_identity_fields:
        _fail("stage exposed identity set differs")
    normalized_identities = {
        field: _identity(exposed_identities[field], label=f"stage {field}")
        for field in sorted(allowed_identity_fields)
    }
    body = {
        "schema_version": STAGE_RECEIPT_SCHEMA,
        "run_id": RUN_ID,
        "transport_contract_sha256": transport_contract_sha256,
        "operation": operation,
        "source_ordinal": source_ordinal,
        "runtime_attempt_ordinal": runtime_attempt_ordinal,
        "cloud_execution_name": cloud_execution_name,
        "stage_start_identity": start_identity,
        "core_workflow_receipt_sha256": sha256(
            canonical_json(core_workflow_receipt)
        ).hexdigest(),
        "exposed_identities": normalized_identities,
        "wall_time_millis": wall_time_millis,
        "peak_rss_kib": peak_rss_kib,
        "compute_measurement_recorded": measurement_recorded,
        "support_rank_book_effect_fields_withheld": True,
        "stage_complete": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "stage_receipt_sha256")


def validate_stage_receipt_v1(
    value: object,
    *,
    transport_contract_sha256: str,
    operation: str,
    source_ordinal: int | None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("stage receipt must be one object")
    item = dict(value)
    _validate_self_hash(item, field="stage_receipt_sha256", label="stage receipt")
    _false_authorities(item, label="stage receipt")
    if (
        item.get("schema_version") != STAGE_RECEIPT_SCHEMA
        or item.get("run_id") != RUN_ID
        or item.get("transport_contract_sha256") != transport_contract_sha256
        or item.get("operation") != operation
        or item.get("source_ordinal") != source_ordinal
        or type(item.get("compute_measurement_recorded")) is not bool
        or item.get("support_rank_book_effect_fields_withheld") is not True
        or item.get("stage_complete") is not True
    ):
        _fail("stage receipt frozen surface differs")
    _stage_uri(operation, source_ordinal)
    # Rebuild through the public constructor so fields, role-specific identity
    # sets, attempts and mechanics types cannot be widened on recovery.
    expected = build_stage_receipt_v1(
        transport_contract_sha256=transport_contract_sha256,
        operation=operation,
        source_ordinal=source_ordinal,
        runtime_attempt_ordinal=item.get("runtime_attempt_ordinal"),
        cloud_execution_name=str(item.get("cloud_execution_name", "")),
        stage_start_identity=item.get("stage_start_identity", {}),
        core_workflow_receipt={
            "retained_sha256_only": item.get("core_workflow_receipt_sha256")
        },
        exposed_identities=item.get("exposed_identities", {}),
        wall_time_millis=item.get("wall_time_millis"),
        peak_rss_kib=item.get("peak_rss_kib"),
    )
    if set(item) != set(expected):
        _fail("stage receipt fields differ")
    # The constructor above hashes its synthetic receipt carrier, so compare
    # every structural field except the already-validated core receipt hash
    # and resulting stage self-hash.
    for field, retained in expected.items():
        if field in {"core_workflow_receipt_sha256", "stage_receipt_sha256"}:
            continue
        if item.get(field) != retained:
            _fail(f"stage receipt field differs: {field}")
    core_hash = item.get("core_workflow_receipt_sha256")
    if not isinstance(core_hash, str) or _SHA256.fullmatch(core_hash) is None:
        _fail("stage core workflow receipt hash differs")
    return item


def validate_stage_predecessor_inputs_v1(
    *,
    transport_contract_sha256: str,
    operation: str,
    source_ordinal: int | None,
    predecessor_identities: Sequence[Mapping[str, object]],
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> list[dict[str, object]]:
    """Validate exact predecessor content before consuming launch permission."""
    predecessors = [
        _identity(value, label=f"stage predecessor[{ordinal}]")
        for ordinal, value in enumerate(predecessor_identities)
    ]
    if [str(value["uri"]) for value in predecessors] != (
        _expected_stage_predecessor_uris(operation, source_ordinal)
    ):
        _fail("stage predecessor identity order differs")
    if operation == "prepare":
        return predecessors
    if operation == "finish-panel":
        for lane_ordinal, identity in enumerate(predecessors):
            reopen_lane_ledger_v1(
                lane_ledger_identity=identity,
                transport_contract_sha256=transport_contract_sha256,
                lane_ordinal=lane_ordinal,
                read_exact=read_exact,
            )
        return predecessors
    if operation == "verify-slate":
        predecessor_operation = "run-slate"
        predecessor_ordinal = source_ordinal
    elif source_ordinal in {0, 28}:
        predecessor_operation = "prepare"
        predecessor_ordinal = None
    else:
        predecessor_operation = "verify-slate"
        predecessor_ordinal = int(source_ordinal) - 1
    identity = predecessors[0]
    raw = read_exact(identity)
    receipt = validate_stage_receipt_v1(
        strict_json(raw, label="stage predecessor receipt"),
        transport_contract_sha256=transport_contract_sha256,
        operation=predecessor_operation,
        source_ordinal=predecessor_ordinal,
    )
    start_identity = _identity(
        receipt["stage_start_identity"], label="stage predecessor start"
    )
    start_raw = read_exact(start_identity)
    start = strict_json(start_raw, label="stage predecessor start")
    reopen_stage_launch_authority_v1(
        stage_start=start,
        transport_contract_sha256=transport_contract_sha256,
        operation=predecessor_operation,
        source_ordinal=predecessor_ordinal,
        runtime_attempt_ordinal=int(receipt["runtime_attempt_ordinal"]),
        cloud_execution_name=str(receipt["cloud_execution_name"]),
        read_exact=read_exact,
    )
    return predecessors


def lane_ledger_uri(lane_ordinal: int) -> str:
    if type(lane_ordinal) is not int or lane_ordinal not in {0, 1}:
        _fail("lane ordinal must be zero or one")
    return TRANSPORT_PREFIX + f"lanes/lane-{lane_ordinal}.json"


def build_lane_ledger_v1(
    *,
    transport_contract_sha256: str,
    lane_ordinal: int,
    stage_receipt_identities: Sequence[Mapping[str, object]],
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    if type(lane_ordinal) is not int or lane_ordinal not in {0, 1}:
        _fail("lane ledger ordinal differs")
    lane = dict(LANE_CONTRACT[lane_ordinal])
    ordinals = list(lane["source_ordinals"])
    if len(stage_receipt_identities) != len(ordinals) * 2:
        _fail("lane ledger requires worker+verifier receipts for every ordinal")
    rows: list[dict[str, object]] = []
    execution_names: set[str] = set()
    previous_verifier_identity: dict[str, object] | None = None
    for offset, source_ordinal in enumerate(ordinals):
        worker_identity = _identity(
            stage_receipt_identities[offset * 2], label="lane worker receipt"
        )
        verifier_identity = _identity(
            stage_receipt_identities[offset * 2 + 1], label="lane verifier receipt"
        )
        if (
            worker_identity["uri"] != _stage_uri("run-slate", source_ordinal)
            or verifier_identity["uri"]
            != _stage_uri("verify-slate", source_ordinal)
        ):
            _fail("lane stage receipt URI/order differs")
        worker_raw = read_exact(worker_identity)
        verifier_raw = read_exact(verifier_identity)
        if not isinstance(worker_raw, bytes) or not isinstance(verifier_raw, bytes):
            _fail("lane stage exact read differs")
        worker = validate_stage_receipt_v1(
            strict_json(worker_raw, label="lane worker receipt"),
            transport_contract_sha256=transport_contract_sha256,
            operation="run-slate",
            source_ordinal=source_ordinal,
        )
        verifier = validate_stage_receipt_v1(
            strict_json(verifier_raw, label="lane verifier receipt"),
            transport_contract_sha256=transport_contract_sha256,
            operation="verify-slate",
            source_ordinal=source_ordinal,
        )
        starts: dict[str, dict[str, object]] = {}
        for operation, receipt in (("run-slate", worker), ("verify-slate", verifier)):
            start_identity = _identity(
                receipt["stage_start_identity"], label="lane stage start"
            )
            start_raw = read_exact(start_identity)
            if not isinstance(start_raw, bytes):
                _fail("lane stage-start exact read differs")
            start = strict_json(start_raw, label="lane stage start")
            starts[operation] = reopen_stage_launch_authority_v1(
                stage_start=start,
                transport_contract_sha256=transport_contract_sha256,
                operation=operation,
                source_ordinal=source_ordinal,
                runtime_attempt_ordinal=int(receipt["runtime_attempt_ordinal"]),
                cloud_execution_name=str(receipt["cloud_execution_name"]),
                read_exact=read_exact,
            )["stage_start"]
        worker_predecessors = starts["run-slate"]["predecessor_identities"]
        verifier_predecessors = starts["verify-slate"][
            "predecessor_identities"
        ]
        if verifier_predecessors != [worker_identity]:
            _fail("verifier start does not bind the exact worker receipt")
        if previous_verifier_identity is None:
            prepare_identity = _identity(
                worker_predecessors[0], label="lane prepare predecessor"
            )
            prepare_raw = read_exact(prepare_identity)
            prepare_receipt = validate_stage_receipt_v1(
                strict_json(prepare_raw, label="lane prepare predecessor"),
                transport_contract_sha256=transport_contract_sha256,
                operation="prepare",
                source_ordinal=None,
            )
            prepare_start_identity = _identity(
                prepare_receipt["stage_start_identity"],
                label="lane prepare stage start",
            )
            prepare_start = strict_json(
                read_exact(prepare_start_identity),
                label="lane prepare stage start",
            )
            reopen_stage_launch_authority_v1(
                stage_start=prepare_start,
                transport_contract_sha256=transport_contract_sha256,
                operation="prepare",
                source_ordinal=None,
                runtime_attempt_ordinal=int(
                    prepare_receipt["runtime_attempt_ordinal"]
                ),
                cloud_execution_name=str(
                    prepare_receipt["cloud_execution_name"]
                ),
                read_exact=read_exact,
            )
        elif worker_predecessors != [previous_verifier_identity]:
            _fail("worker start does not bind the prior verifier receipt")
        worker_execution = str(worker["cloud_execution_name"])
        verifier_execution = str(verifier["cloud_execution_name"])
        if worker_execution == verifier_execution:
            _fail("worker and verifier must be distinct cloud executions")
        execution_names.update((worker_execution, verifier_execution))
        acceptance_identity = _identity(
            verifier["exposed_identities"]["acceptance_identity"],
            label="lane acceptance",
        )
        rows.append({
            "source_ordinal": source_ordinal,
            "worker_stage_receipt_identity": worker_identity,
            "verifier_stage_receipt_identity": verifier_identity,
            "worker_cloud_execution_name": worker_execution,
            "verifier_cloud_execution_name": verifier_execution,
            "acceptance_identity": acceptance_identity,
        })
        previous_verifier_identity = verifier_identity
    if len(execution_names) != len(rows) * 2:
        _fail("lane cloud executions must be globally unique within the lane")
    body = {
        "schema_version": LANE_LEDGER_SCHEMA,
        "run_id": RUN_ID,
        "transport_contract_sha256": transport_contract_sha256,
        "lane": lane,
        "ordered_stage_rows": rows,
        "ordered_stage_rows_sha256": sha256(canonical_json(rows)).hexdigest(),
        "accepted_source_ordinals": ordinals,
        "accepted_slate_count": len(rows),
        "worker_verifier_distinct": True,
        "sequential_lane_predecessor_chain_verified": True,
        "support_rank_book_effect_fields_withheld": True,
        "complete": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "lane_ledger_sha256")


def reopen_lane_ledger_v1(
    *,
    lane_ledger_identity: Mapping[str, object],
    transport_contract_sha256: str,
    lane_ordinal: int,
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    identity = _identity(lane_ledger_identity, label="lane ledger")
    if identity["uri"] != lane_ledger_uri(lane_ordinal):
        _fail("lane ledger URI differs")
    raw = read_exact(identity)
    if not isinstance(raw, bytes):
        _fail("lane ledger exact read differs")
    item = strict_json(raw, label="lane ledger")
    _validate_self_hash(item, field="lane_ledger_sha256", label="lane ledger")
    _false_authorities(item, label="lane ledger")
    rows = item.get("ordered_stage_rows")
    if not isinstance(rows, list):
        _fail("lane ledger stage rows differ")
    identities: list[Mapping[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            _fail("lane ledger row differs")
        identities.extend((
            row.get("worker_stage_receipt_identity", {}),
            row.get("verifier_stage_receipt_identity", {}),
        ))
    expected = build_lane_ledger_v1(
        transport_contract_sha256=transport_contract_sha256,
        lane_ordinal=lane_ordinal,
        stage_receipt_identities=identities,
        read_exact=read_exact,
    )
    if canonical_json(item) != canonical_json(expected):
        _fail("lane ledger differs after full stage replay")
    return item


def validate_finalizer_execution_distinct_v1(
    *,
    transport_contract_sha256: str,
    finalizer_cloud_execution_name: str,
    lane_ledger_identities: Sequence[Mapping[str, object]],
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> tuple[dict[str, object], dict[str, object]]:
    """Prove 108 unique worker/verifier executions plus a fresh finalizer."""
    if len(lane_ledger_identities) != 2:
        _fail("finalizer distinctness requires both ordered lane ledgers")
    ledgers = tuple(
        reopen_lane_ledger_v1(
            lane_ledger_identity=lane_ledger_identities[lane_ordinal],
            transport_contract_sha256=transport_contract_sha256,
            lane_ordinal=lane_ordinal,
            read_exact=read_exact,
        )
        for lane_ordinal in range(2)
    )
    execution_names: list[str] = []
    for ledger in ledgers:
        rows = ledger["ordered_stage_rows"]
        for row in rows:
            execution_names.extend((
                str(row["worker_cloud_execution_name"]),
                str(row["verifier_cloud_execution_name"]),
            ))
    if (
        len(execution_names) != 108
        or len(set(execution_names)) != 108
        or finalizer_cloud_execution_name in set(execution_names)
    ):
        _fail("finalizer/worker/verifier cloud executions are not globally unique")
    return ledgers


def frozen_time_v_parser_contract_v1() -> dict[str, object]:
    body = dict(_TIME_V_PARSER_BODY)
    actual = sha256(canonical_json(body)).hexdigest()
    if actual != EXPECTED_TIME_V_PARSER_SHA256:
        _fail("frozen GNU time parser contract drifted")
    return {**body, "parser_implementation_sha256": actual}


def _elapsed_millis(value: str) -> int:
    pieces = value.strip().split(":")
    if len(pieces) not in {2, 3} or any(not piece for piece in pieces):
        _fail("GNU time elapsed value differs")
    hours = 0
    if len(pieces) == 3:
        if not pieces[0].isdigit():
            _fail("GNU time elapsed hours differ")
        hours = int(pieces.pop(0))
    if not pieces[0].isdigit() or "." not in pieces[1]:
        _fail("GNU time elapsed minutes/seconds differ")
    minutes = int(pieces[0])
    seconds, fraction = pieces[1].split(".", 1)
    if (
        not seconds.isdigit()
        or not fraction.isdigit()
        or not 1 <= len(fraction) <= 3
        or minutes >= 60
        or int(seconds) >= 60
    ):
        _fail("GNU time elapsed value differs")
    return (
        ((hours * 60 + minutes) * 60 + int(seconds)) * 1000
        + int(fraction.ljust(3, "0"))
    )


def _parse_gnu_time_v_for_command_v1(
    raw: bytes, *, expected_command: str
) -> dict[str, object]:
    frozen_time_v_parser_contract_v1()
    if (
        not isinstance(expected_command, str)
        or not expected_command
        or "\n" in expected_command
        or "\r" in expected_command
    ):
        _fail("GNU time expected command differs")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise T230TransportError("GNU time output is not UTF-8") from exc
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        matches = [
            label for label in _TIME_V_LABELS
            if stripped.startswith(label + ":")
        ]
        if len(matches) != 1:
            _fail("GNU time contains an unknown or ambiguous line")
        label = matches[0]
        value = stripped[len(label) + 1 :].strip()
        if label in values:
            _fail(f"GNU time {label} label repeats")
        if not value:
            _fail(f"GNU time {label} value is empty")
        values[label] = value
    if set(values) != set(_TIME_V_LABELS):
        _fail("GNU time complete mechanics label set differs")
    command = values["Command being timed"]
    if len(command) < 2 or command[0] != '"' or command[-1] != '"':
        _fail("GNU time command label differs")
    command = command[1:-1]
    elapsed = values["Elapsed (wall clock) time (h:mm:ss or m:ss)"]
    rss = values["Maximum resident set size (kbytes)"]
    exit_code = values["Exit status"]
    for label in ("User time (seconds)", "System time (seconds)"):
        if re.fullmatch(r"[0-9]+\.[0-9]+", values[label]) is None:
            _fail(f"GNU time {label} value differs")
    if re.fullmatch(
        r"[0-9]+%", values["Percent of CPU this job got"]
    ) is None:
        _fail("GNU time CPU-percent value differs")
    integer_labels = set(_TIME_V_LABELS) - {
        "Command being timed",
        "User time (seconds)",
        "System time (seconds)",
        "Percent of CPU this job got",
        "Elapsed (wall clock) time (h:mm:ss or m:ss)",
    }
    if any(not values[label].isdigit() for label in integer_labels):
        _fail("GNU time integer mechanics value differs")
    if (
        command != expected_command
        or not rss.isdigit()
        or not exit_code.isdigit()
    ):
        _fail("GNU time numeric fields differ")
    return {
        "timed_command": command,
        "wall_time_millis": _elapsed_millis(elapsed),
        "peak_rss_kib": int(rss),
        "exit_code": int(exit_code),
    }


def parse_gnu_time_v_v1(raw: bytes) -> dict[str, object]:
    return _parse_gnu_time_v_for_command_v1(
        raw, expected_command=BENCHMARK_COMMAND
    )


def parse_prefreeze_smoke_time_v_v1(raw: bytes) -> dict[str, object]:
    return _parse_gnu_time_v_for_command_v1(
        raw, expected_command=PREFREEZE_SMOKE_TIMED_COMMAND
    )


def _prefreeze_numeric_projection_v1(
    measurement: Mapping[str, object],
) -> dict[str, object]:
    wall = measurement.get("wall_time_millis")
    rss = measurement.get("peak_rss_kib")
    if type(wall) is not int or type(rss) is not int:
        _fail("prefreeze smoke timing fields differ")
    timeout_headroom = TASK_TIMEOUT_SECONDS - ((int(wall) + 999) // 1000)
    rss_headroom = MEMORY_LIMIT_MIB * 1024 - int(rss)
    if (
        measurement.get("timed_command") != PREFREEZE_SMOKE_TIMED_COMMAND
        or measurement.get("exit_code") != 0
        or not 1 <= int(wall) <= MAX_WALL_TIME_MILLIS
        or not 1 <= int(rss) <= MAX_PEAK_RSS_KIB
        or rss_headroom < MIN_RSS_HEADROOM_KIB
        or timeout_headroom < MIN_TIMEOUT_HEADROOM_SECONDS
        or TASK_TIMEOUT_SECONDS
        * 1000
        * MIN_TIMEOUT_HEADROOM_FRACTION_DENOMINATOR
        < int(wall)
        * (
            MIN_TIMEOUT_HEADROOM_FRACTION_DENOMINATOR
            + MIN_TIMEOUT_HEADROOM_FRACTION_NUMERATOR
        )
    ):
        _fail("prefreeze smoke does not pass the frozen numeric gate")
    return {
        "wall_time_millis": int(wall),
        "peak_rss_kib": int(rss),
        "rss_headroom_kib": rss_headroom,
        "timeout_headroom_seconds": timeout_headroom,
        "exit_code": 0,
        "compute_gate_sha256": frozen_compute_gate_v1()["compute_gate_sha256"],
        "numeric_gate_passed": True,
    }


def build_prefreeze_smoke_launch_v1(
    *,
    panel_object_identity: Mapping[str, object],
    source_commit_sha: str,
    immutable_candidate_image: Mapping[str, object],
    service_account: str,
) -> dict[str, object]:
    panel_identity = _identity(
        panel_object_identity, label="prefreeze smoke launch panel"
    )
    image = _image(
        immutable_candidate_image, label="prefreeze smoke launch image"
    )
    if (
        panel_identity["uri"] != execution.FROZEN_G0_PANEL_URI
        or not isinstance(source_commit_sha, str)
        or _COMMIT.fullmatch(source_commit_sha) is None
        or not isinstance(service_account, str)
        or re.fullmatch(
            r"[a-z0-9][a-z0-9.-]{4,62}@[a-z0-9.-]+\.gserviceaccount\.com",
            service_account,
        ) is None
    ):
        _fail("prefreeze smoke launch binding differs")
    body = {
        "schema_version": PREFREEZE_SMOKE_LAUNCH_SCHEMA,
        "run_id": RUN_ID,
        "panel_object_identity": panel_identity,
        "source_commit_sha": source_commit_sha,
        "immutable_candidate_image": image,
        "job": execution.PREFREEZE_SMOKE_CLOUD_RUN_JOB,
        "service_account": service_account,
        "cpu": "8",
        "memory": "32Gi",
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": TASK_TIMEOUT_SECONDS,
        "command": PREFREEZE_SMOKE_WORKER_COMMAND,
        "only_target_creator_may_launch": True,
        "relaunch_after_consumption_allowed": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "prefreeze_smoke_launch_sha256")


def validate_prefreeze_smoke_launch_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("prefreeze smoke launch must be one object")
    item = dict(value)
    _validate_self_hash(
        item,
        field="prefreeze_smoke_launch_sha256",
        label="prefreeze smoke launch",
    )
    _false_authorities(item, label="prefreeze smoke launch")
    expected = build_prefreeze_smoke_launch_v1(
        panel_object_identity=item.get("panel_object_identity", {}),
        source_commit_sha=str(item.get("source_commit_sha", "")),
        immutable_candidate_image=item.get("immutable_candidate_image", {}),
        service_account=str(item.get("service_account", "")),
    )
    if canonical_json(item) != canonical_json(expected):
        _fail("prefreeze smoke launch frozen surface differs")
    return item


def build_prefreeze_smoke_time_binding_v1(
    *,
    smoke_receipt_identity: Mapping[str, object],
    smoke_receipt: Mapping[str, object],
    raw_time_v: bytes,
) -> dict[str, object]:
    receipt_identity = _identity(
        smoke_receipt_identity, label="prefreeze smoke receipt"
    )
    receipt = execution.validate_t230_prefreeze_smoke_receipt_v1(
        smoke_receipt,
        expected_panel_object_identity=smoke_receipt.get(
            "panel_object_identity", {}
        ),
        expected_source_commit_sha=str(smoke_receipt.get("source_commit_sha", "")),
        expected_immutable_candidate_image=smoke_receipt.get(
            "immutable_candidate_image", {}
        ),
        require_release_runtime=True,
    )
    receipt_raw = canonical_json(receipt)
    if (
        receipt_identity["uri"] != PREFREEZE_SMOKE_RECEIPT_URI
        or receipt_identity["sha256"] != sha256(receipt_raw).hexdigest()
        or receipt_identity["bytes"] != len(receipt_raw)
    ):
        _fail("prefreeze smoke receipt identity differs")
    measurement = parse_prefreeze_smoke_time_v_v1(raw_time_v)
    numeric = _prefreeze_numeric_projection_v1(measurement)
    body = {
        "schema_version": PREFREEZE_SMOKE_TIME_BINDING_SCHEMA,
        "run_id": RUN_ID,
        "smoke_receipt_identity": receipt_identity,
        "prefreeze_smoke_receipt_sha256": receipt[
            "prefreeze_smoke_receipt_sha256"
        ],
        "runtime_binding_sha256": receipt["runtime_binding_sha256"],
        "source_commit_sha": receipt["source_commit_sha"],
        "immutable_candidate_image": receipt["immutable_candidate_image"],
        "panel_object_identity": receipt["panel_object_identity"],
        "target_uri": PREFREEZE_SMOKE_TIME_V_URI,
        "expected_sha256": sha256(raw_time_v).hexdigest(),
        "expected_bytes": len(raw_time_v),
        "parser_contract": frozen_time_v_parser_contract_v1(),
        "timed_command": PREFREEZE_SMOKE_TIMED_COMMAND,
        **numeric,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "prefreeze_smoke_time_binding_sha256")


_PREFREEZE_OBSERVED_EXECUTION_KEYS: Final = {
    "job", "image", "service_account", "cpu", "memory", "task_count",
    "parallelism", "max_retries", "task_timeout_seconds", "command",
    "args", "configured_environment", "volumes", "secrets",
    "cloud_job_describe_exactly_validated", "execution_name",
    "completed_status", "completion_time",
    "cloud_execution_describe_exactly_validated",
}


def build_prefreeze_smoke_execution_v1(
    *,
    smoke_launch_identity: Mapping[str, object],
    smoke_launch: Mapping[str, object],
    smoke_receipt_identity: Mapping[str, object],
    smoke_receipt: Mapping[str, object],
    smoke_time_v_identity: Mapping[str, object],
    smoke_time_v: bytes,
    observed_execution: Mapping[str, object],
) -> dict[str, object]:
    launch = validate_prefreeze_smoke_launch_v1(smoke_launch)
    launch_identity = _identity(
        smoke_launch_identity, label="prefreeze execution smoke launch"
    )
    launch_raw = canonical_json(launch)
    receipt = execution.validate_t230_prefreeze_smoke_receipt_v1(
        smoke_receipt,
        expected_panel_object_identity=smoke_receipt.get(
            "panel_object_identity", {}
        ),
        expected_source_commit_sha=str(smoke_receipt.get("source_commit_sha", "")),
        expected_immutable_candidate_image=smoke_receipt.get(
            "immutable_candidate_image", {}
        ),
        require_release_runtime=True,
    )
    receipt_identity = _identity(
        smoke_receipt_identity, label="prefreeze execution smoke receipt"
    )
    time_identity = _identity(
        smoke_time_v_identity, label="prefreeze execution GNU time"
    )
    time_binding = build_prefreeze_smoke_time_binding_v1(
        smoke_receipt_identity=receipt_identity,
        smoke_receipt=receipt,
        raw_time_v=smoke_time_v,
    )
    if (
        time_identity["uri"] != PREFREEZE_SMOKE_TIME_V_URI
        or time_identity["sha256"] != sha256(smoke_time_v).hexdigest()
        or time_identity["bytes"] != len(smoke_time_v)
    ):
        _fail("prefreeze execution GNU time identity differs")
    if not isinstance(observed_execution, Mapping):
        _fail("prefreeze observed execution must be one object")
    observed = dict(observed_execution)
    runtime = dict(receipt["runtime_binding"])
    service_account = observed.get("service_account")
    if (
        launch_identity["uri"] != PREFREEZE_SMOKE_LAUNCH_URI
        or launch_identity["sha256"] != sha256(launch_raw).hexdigest()
        or launch_identity["bytes"] != len(launch_raw)
        or launch["source_commit_sha"] != receipt["source_commit_sha"]
        or launch["immutable_candidate_image"]
        != receipt["immutable_candidate_image"]
        or launch["panel_object_identity"] != receipt["panel_object_identity"]
        or launch["job"] != runtime["cloud_run_job"]
        or launch["service_account"] != observed.get("service_account")
        or set(observed) != _PREFREEZE_OBSERVED_EXECUTION_KEYS
        or observed.get("job") != execution.PREFREEZE_SMOKE_CLOUD_RUN_JOB
        or observed.get("job") != runtime["cloud_run_job"]
        or observed.get("execution_name") != runtime["cloud_run_execution"]
        or not isinstance(observed.get("execution_name"), str)
        or _EXECUTION.fullmatch(str(observed["execution_name"])) is None
        or observed.get("image") != receipt["immutable_candidate_image"]["uri"]
        or not isinstance(service_account, str)
        or re.fullmatch(
            r"[a-z0-9][a-z0-9.-]{4,62}@[a-z0-9.-]+\.gserviceaccount\.com",
            str(service_account),
        ) is None
        or observed.get("cpu") != "8"
        or observed.get("memory") != "32Gi"
        or observed.get("task_count") != 1
        or observed.get("parallelism") != 1
        or observed.get("max_retries") != 0
        or observed.get("task_timeout_seconds") != TASK_TIMEOUT_SECONDS
        or observed.get("command") != ["bash"]
        or observed.get("args")
        != ["scripts/run_t230_prefreeze_smoke_worker_v1.sh"]
        or observed.get("configured_environment")
        != {
            "FOUNDRY_T230_PREFREEZE_SMOKE_ENABLED": "1",
            "FOUNDRY_T230_PRODUCTION_TRANSPORT_ENABLED": "1",
            "T230_PREFREEZE_CANDIDATE_IMAGE": receipt[
                "immutable_candidate_image"
            ]["uri"],
        }
        or observed.get("volumes") != []
        or observed.get("secrets") != []
        or observed.get("cloud_job_describe_exactly_validated") is not True
        or observed.get("completed_status") != "True"
        or not isinstance(observed.get("completion_time"), str)
        or not str(observed["completion_time"]).endswith("Z")
        or observed.get("cloud_execution_describe_exactly_validated") is not True
        or runtime.get("cloud_run_task_index") != 0
        or runtime.get("cloud_run_task_attempt") != 0
        or runtime.get("cloud_run_task_count") != 1
    ):
        _fail("prefreeze smoke Cloud execution envelope differs")
    body = {
        "schema_version": PREFREEZE_SMOKE_EXECUTION_SCHEMA,
        "run_id": RUN_ID,
        "smoke_launch_identity": launch_identity,
        "prefreeze_smoke_launch_sha256": launch[
            "prefreeze_smoke_launch_sha256"
        ],
        "smoke_receipt_identity": receipt_identity,
        "prefreeze_smoke_receipt_sha256": receipt[
            "prefreeze_smoke_receipt_sha256"
        ],
        "smoke_time_v_identity": time_identity,
        "prefreeze_smoke_time_binding_sha256": time_binding[
            "prefreeze_smoke_time_binding_sha256"
        ],
        "runtime_binding_sha256": receipt["runtime_binding_sha256"],
        "source_commit_sha": receipt["source_commit_sha"],
        "immutable_candidate_image": receipt["immutable_candidate_image"],
        "panel_object_identity": receipt["panel_object_identity"],
        "job": observed["job"],
        "execution_name": observed["execution_name"],
        "service_account": service_account,
        "cpu": "8",
        "memory": "32Gi",
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "task_timeout_seconds": TASK_TIMEOUT_SECONDS,
        "command": PREFREEZE_SMOKE_WORKER_COMMAND,
        "configured_environment_sha256": sha256(
            canonical_json(observed["configured_environment"])
        ).hexdigest(),
        "volumes": [],
        "secrets": [],
        "completed_status": "True",
        "completion_time": observed["completion_time"],
        "cloud_job_describe_exactly_validated": True,
        "cloud_execution_describe_exactly_validated": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "prefreeze_smoke_execution_sha256")


def validate_prefreeze_smoke_execution_v1(
    value: object,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("prefreeze smoke execution must be one object")
    item = dict(value)
    required = {
        "schema_version", "run_id", "smoke_receipt_identity",
        "smoke_launch_identity", "prefreeze_smoke_launch_sha256",
        "prefreeze_smoke_receipt_sha256", "smoke_time_v_identity",
        "prefreeze_smoke_time_binding_sha256", "runtime_binding_sha256",
        "source_commit_sha", "immutable_candidate_image",
        "panel_object_identity", "job", "execution_name", "service_account",
        "cpu", "memory", "task_count", "parallelism", "max_retries",
        "task_timeout_seconds", "command", "configured_environment_sha256",
        "volumes", "secrets", "completed_status", "completion_time",
        "cloud_job_describe_exactly_validated",
        "cloud_execution_describe_exactly_validated", *_FALSE_AUTHORITY_FIELDS,
        "prefreeze_smoke_execution_sha256",
    }
    if set(item) != required:
        _fail("prefreeze smoke execution fields differ")
    _validate_self_hash(
        item,
        field="prefreeze_smoke_execution_sha256",
        label="prefreeze smoke execution",
    )
    _false_authorities(item, label="prefreeze smoke execution")
    if (
        item.get("schema_version") != PREFREEZE_SMOKE_EXECUTION_SCHEMA
        or item.get("run_id") != RUN_ID
        or _identity(
            item.get("smoke_launch_identity"),
            label="prefreeze execution smoke launch",
        )["uri"] != PREFREEZE_SMOKE_LAUNCH_URI
        or _identity(
            item.get("smoke_receipt_identity"),
            label="prefreeze execution smoke receipt",
        )["uri"] != PREFREEZE_SMOKE_RECEIPT_URI
        or _identity(
            item.get("smoke_time_v_identity"),
            label="prefreeze execution GNU time",
        )["uri"] != PREFREEZE_SMOKE_TIME_V_URI
        or any(
            not isinstance(item.get(field), str)
            or _SHA256.fullmatch(str(item[field])) is None
            for field in (
                "prefreeze_smoke_receipt_sha256",
                "prefreeze_smoke_launch_sha256",
                "prefreeze_smoke_time_binding_sha256",
                "runtime_binding_sha256",
                "configured_environment_sha256",
            )
        )
        or not isinstance(item.get("source_commit_sha"), str)
        or _COMMIT.fullmatch(str(item["source_commit_sha"])) is None
        or _image(
            item.get("immutable_candidate_image"),
            label="prefreeze execution candidate image",
        ) != item.get("immutable_candidate_image")
        or _identity(
            item.get("panel_object_identity"),
            label="prefreeze execution panel",
        )["uri"] != execution.FROZEN_G0_PANEL_URI
        or item.get("job") != execution.PREFREEZE_SMOKE_CLOUD_RUN_JOB
        or not isinstance(item.get("execution_name"), str)
        or _EXECUTION.fullmatch(str(item["execution_name"])) is None
        or not isinstance(item.get("service_account"), str)
        or re.fullmatch(
            r"[a-z0-9][a-z0-9.-]{4,62}@[a-z0-9.-]+\.gserviceaccount\.com",
            str(item.get("service_account")),
        ) is None
        or item.get("cpu") != "8"
        or item.get("memory") != "32Gi"
        or item.get("task_count") != 1
        or item.get("parallelism") != 1
        or item.get("max_retries") != 0
        or item.get("task_timeout_seconds") != TASK_TIMEOUT_SECONDS
        or item.get("command") != PREFREEZE_SMOKE_WORKER_COMMAND
        or item.get("configured_environment_sha256")
        != sha256(canonical_json({
            "FOUNDRY_T230_PREFREEZE_SMOKE_ENABLED": "1",
            "FOUNDRY_T230_PRODUCTION_TRANSPORT_ENABLED": "1",
            "T230_PREFREEZE_CANDIDATE_IMAGE": item[
                "immutable_candidate_image"
            ]["uri"],
        })).hexdigest()
        or item.get("volumes") != []
        or item.get("secrets") != []
        or item.get("completed_status") != "True"
        or not isinstance(item.get("completion_time"), str)
        or not str(item["completion_time"]).endswith("Z")
        or item.get("cloud_job_describe_exactly_validated") is not True
        or item.get("cloud_execution_describe_exactly_validated") is not True
    ):
        _fail("prefreeze smoke execution frozen surface differs")
    return item


def build_prefreeze_release_gate_v1(
    *,
    expected_panel_object_identity: Mapping[str, object],
    expected_source_commit_sha: str,
    expected_immutable_candidate_image: Mapping[str, object],
    smoke_launch_identity: Mapping[str, object],
    smoke_launch: Mapping[str, object],
    smoke_receipt_identity: Mapping[str, object],
    smoke_receipt: Mapping[str, object],
    smoke_time_v_identity: Mapping[str, object],
    smoke_time_v: bytes,
    smoke_execution_identity: Mapping[str, object],
    smoke_execution: Mapping[str, object],
) -> dict[str, object]:
    launch = validate_prefreeze_smoke_launch_v1(smoke_launch)
    launch_identity = _identity(
        smoke_launch_identity, label="release-gate smoke launch"
    )
    launch_raw = canonical_json(launch)
    receipt = execution.validate_t230_prefreeze_smoke_receipt_v1(
        smoke_receipt,
        expected_panel_object_identity=expected_panel_object_identity,
        expected_source_commit_sha=expected_source_commit_sha,
        expected_immutable_candidate_image=expected_immutable_candidate_image,
        require_release_runtime=True,
    )
    receipt_identity = _identity(
        smoke_receipt_identity, label="release-gate smoke receipt"
    )
    receipt_raw = canonical_json(receipt)
    time_identity = _identity(
        smoke_time_v_identity, label="release-gate GNU time"
    )
    execution_identity = _identity(
        smoke_execution_identity, label="release-gate smoke execution"
    )
    projection = validate_prefreeze_smoke_execution_v1(smoke_execution)
    projection_raw = canonical_json(projection)
    time_binding = build_prefreeze_smoke_time_binding_v1(
        smoke_receipt_identity=receipt_identity,
        smoke_receipt=receipt,
        raw_time_v=smoke_time_v,
    )
    numeric = _prefreeze_numeric_projection_v1(
        parse_prefreeze_smoke_time_v_v1(smoke_time_v)
    )
    if (
        launch_identity["uri"] != PREFREEZE_SMOKE_LAUNCH_URI
        or launch_identity["sha256"] != sha256(launch_raw).hexdigest()
        or launch_identity["bytes"] != len(launch_raw)
        or launch["source_commit_sha"] != receipt["source_commit_sha"]
        or launch["immutable_candidate_image"]
        != receipt["immutable_candidate_image"]
        or launch["panel_object_identity"] != receipt["panel_object_identity"]
        or projection["smoke_launch_identity"] != launch_identity
        or projection["prefreeze_smoke_launch_sha256"]
        != launch["prefreeze_smoke_launch_sha256"]
        or receipt_identity["uri"] != PREFREEZE_SMOKE_RECEIPT_URI
        or receipt_identity["sha256"] != sha256(receipt_raw).hexdigest()
        or receipt_identity["bytes"] != len(receipt_raw)
        or time_identity["uri"] != PREFREEZE_SMOKE_TIME_V_URI
        or time_identity["sha256"] != sha256(smoke_time_v).hexdigest()
        or time_identity["bytes"] != len(smoke_time_v)
        or execution_identity["uri"] != PREFREEZE_SMOKE_EXECUTION_URI
        or execution_identity["sha256"] != sha256(projection_raw).hexdigest()
        or execution_identity["bytes"] != len(projection_raw)
        or projection["smoke_receipt_identity"] != receipt_identity
        or projection["smoke_time_v_identity"] != time_identity
        or projection["prefreeze_smoke_receipt_sha256"]
        != receipt["prefreeze_smoke_receipt_sha256"]
        or projection["prefreeze_smoke_time_binding_sha256"]
        != time_binding["prefreeze_smoke_time_binding_sha256"]
        or projection["runtime_binding_sha256"]
        != receipt["runtime_binding_sha256"]
        or projection["source_commit_sha"] != receipt["source_commit_sha"]
        or projection["immutable_candidate_image"]
        != receipt["immutable_candidate_image"]
        or projection["panel_object_identity"] != receipt["panel_object_identity"]
        or projection["execution_name"]
        != receipt["runtime_binding"]["cloud_run_execution"]
    ):
        _fail("prefreeze release-gate accepted chain differs")
    body = {
        "schema_version": PREFREEZE_RELEASE_GATE_SCHEMA,
        "run_id": RUN_ID,
        "smoke_id": execution.PREFREEZE_SMOKE_ID,
        "source_ordinal": execution.PREFREEZE_SMOKE_SOURCE_ORDINAL,
        "slate_id": execution.PREFREEZE_SMOKE_SLATE_ID,
        "source_commit_sha": receipt["source_commit_sha"],
        "immutable_candidate_image": receipt["immutable_candidate_image"],
        "panel_object_identity": receipt["panel_object_identity"],
        "smoke_launch_identity": launch_identity,
        "prefreeze_smoke_launch_sha256": launch[
            "prefreeze_smoke_launch_sha256"
        ],
        "smoke_receipt_identity": receipt_identity,
        "prefreeze_smoke_receipt_sha256": receipt[
            "prefreeze_smoke_receipt_sha256"
        ],
        "runtime_binding_sha256": receipt["runtime_binding_sha256"],
        "smoke_time_v_identity": time_identity,
        "prefreeze_smoke_time_binding_sha256": time_binding[
            "prefreeze_smoke_time_binding_sha256"
        ],
        "smoke_execution_identity": execution_identity,
        "prefreeze_smoke_execution_sha256": projection[
            "prefreeze_smoke_execution_sha256"
        ],
        "cloud_execution_name": projection["execution_name"],
        "service_account": projection["service_account"],
        "numeric_gate": numeric,
        "exact_four_law_shared_call_chain_executed": True,
        "candidate_image_rebuild_after_smoke_allowed": False,
        "image_evidence_publication_licensed": True,
        "transport_contract_publication_licensed": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "prefreeze_release_gate_sha256")


def validate_prefreeze_release_gate_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("prefreeze release gate must be one object")
    item = dict(value)
    required = {
        "schema_version", "run_id", "smoke_id", "source_ordinal",
        "slate_id", "source_commit_sha", "immutable_candidate_image",
        "panel_object_identity", "smoke_receipt_identity",
        "smoke_launch_identity", "prefreeze_smoke_launch_sha256",
        "prefreeze_smoke_receipt_sha256", "runtime_binding_sha256",
        "smoke_time_v_identity", "prefreeze_smoke_time_binding_sha256",
        "smoke_execution_identity", "prefreeze_smoke_execution_sha256",
        "cloud_execution_name", "service_account", "numeric_gate",
        "exact_four_law_shared_call_chain_executed",
        "candidate_image_rebuild_after_smoke_allowed",
        "image_evidence_publication_licensed",
        "transport_contract_publication_licensed", *_FALSE_AUTHORITY_FIELDS,
        "prefreeze_release_gate_sha256",
    }
    if set(item) != required:
        _fail("prefreeze release gate fields differ")
    _validate_self_hash(
        item,
        field="prefreeze_release_gate_sha256",
        label="prefreeze release gate",
    )
    _false_authorities(item, label="prefreeze release gate")
    numeric = item.get("numeric_gate")
    if not isinstance(numeric, Mapping):
        _fail("prefreeze release numeric gate differs")
    expected_numeric_keys = {
        "wall_time_millis", "peak_rss_kib", "rss_headroom_kib",
        "timeout_headroom_seconds", "exit_code", "compute_gate_sha256",
        "numeric_gate_passed",
    }
    if (
        item.get("schema_version") != PREFREEZE_RELEASE_GATE_SCHEMA
        or item.get("run_id") != RUN_ID
        or item.get("smoke_id") != execution.PREFREEZE_SMOKE_ID
        or item.get("source_ordinal") != 0
        or item.get("slate_id") != execution.PREFREEZE_SMOKE_SLATE_ID
        or not isinstance(item.get("source_commit_sha"), str)
        or _COMMIT.fullmatch(str(item["source_commit_sha"])) is None
        or _image(
            item.get("immutable_candidate_image"),
            label="prefreeze release candidate image",
        ) != item.get("immutable_candidate_image")
        or _identity(
            item.get("smoke_launch_identity"),
            label="prefreeze release smoke launch",
        )["uri"] != PREFREEZE_SMOKE_LAUNCH_URI
        or _identity(
            item.get("panel_object_identity"), label="prefreeze release panel"
        )["uri"] != execution.FROZEN_G0_PANEL_URI
        or _identity(
            item.get("smoke_receipt_identity"),
            label="prefreeze release smoke receipt",
        )["uri"] != PREFREEZE_SMOKE_RECEIPT_URI
        or _identity(
            item.get("smoke_time_v_identity"),
            label="prefreeze release GNU time",
        )["uri"] != PREFREEZE_SMOKE_TIME_V_URI
        or _identity(
            item.get("smoke_execution_identity"),
            label="prefreeze release execution",
        )["uri"] != PREFREEZE_SMOKE_EXECUTION_URI
        or any(
            not isinstance(item.get(field), str)
            or _SHA256.fullmatch(str(item[field])) is None
            for field in (
                "prefreeze_smoke_launch_sha256",
                "prefreeze_smoke_receipt_sha256", "runtime_binding_sha256",
                "prefreeze_smoke_time_binding_sha256",
                "prefreeze_smoke_execution_sha256",
            )
        )
        or not isinstance(item.get("cloud_execution_name"), str)
        or _EXECUTION.fullmatch(str(item["cloud_execution_name"])) is None
        or not isinstance(item.get("service_account"), str)
        or re.fullmatch(
            r"[a-z0-9][a-z0-9.-]{4,62}@[a-z0-9.-]+\.gserviceaccount\.com",
            str(item.get("service_account")),
        ) is None
        or set(numeric) != expected_numeric_keys
        or numeric.get("compute_gate_sha256")
        != frozen_compute_gate_v1()["compute_gate_sha256"]
        or numeric.get("numeric_gate_passed") is not True
        or numeric.get("exit_code") != 0
        or type(numeric.get("wall_time_millis")) is not int
        or not 1 <= int(numeric["wall_time_millis"]) <= MAX_WALL_TIME_MILLIS
        or type(numeric.get("peak_rss_kib")) is not int
        or not 1 <= int(numeric["peak_rss_kib"]) <= MAX_PEAK_RSS_KIB
        or numeric.get("rss_headroom_kib")
        != MEMORY_LIMIT_MIB * 1024 - int(numeric["peak_rss_kib"])
        or int(numeric["rss_headroom_kib"]) < MIN_RSS_HEADROOM_KIB
        or type(numeric.get("timeout_headroom_seconds")) is not int
        or numeric.get("timeout_headroom_seconds")
        != TASK_TIMEOUT_SECONDS
        - ((int(numeric["wall_time_millis"]) + 999) // 1000)
        or int(numeric["timeout_headroom_seconds"])
        < MIN_TIMEOUT_HEADROOM_SECONDS
        or TASK_TIMEOUT_SECONDS
        * 1000
        * MIN_TIMEOUT_HEADROOM_FRACTION_DENOMINATOR
        < int(numeric["wall_time_millis"])
        * (
            MIN_TIMEOUT_HEADROOM_FRACTION_DENOMINATOR
            + MIN_TIMEOUT_HEADROOM_FRACTION_NUMERATOR
        )
        or item.get("exact_four_law_shared_call_chain_executed") is not True
        or item.get("candidate_image_rebuild_after_smoke_allowed") is not False
        or item.get("image_evidence_publication_licensed") is not True
        or item.get("transport_contract_publication_licensed") is not True
    ):
        _fail("prefreeze release gate frozen surface differs")
    return item


def _read_known_pinned_v1(
    backend: JournalBackend, *, uri: str, label: str
) -> tuple[dict[str, object], bytes]:
    retained_identity, retained_raw = backend.read_known_uri(uri)
    identity = _identity(retained_identity, label=label)
    if backend.read(identity) != retained_raw:
        _fail(f"{label} differs on generation-pinned reopen")
    return identity, retained_raw


def recover_prefreeze_smoke_launch_v1(
    *,
    backend: JournalBackend,
    expected_panel_object_identity: Mapping[str, object],
    expected_source_commit_sha: str,
    expected_immutable_candidate_image: Mapping[str, object],
) -> dict[str, object]:
    launch_identity, launch_raw = _read_known_pinned_v1(
        backend,
        uri=PREFREEZE_SMOKE_LAUNCH_URI,
        label="known prefreeze smoke launch",
    )
    launch = validate_prefreeze_smoke_launch_v1(
        strict_json(launch_raw, label="known prefreeze smoke launch")
    )
    if (
        launch["panel_object_identity"]
        != _identity(
            expected_panel_object_identity,
            label="expected prefreeze smoke launch panel",
        )
        or launch["source_commit_sha"] != expected_source_commit_sha
        or launch["immutable_candidate_image"]
        != _image(
            expected_immutable_candidate_image,
            label="expected prefreeze smoke launch image",
        )
    ):
        _fail("prefreeze smoke launch expected binding differs")
    recovered_identity, recovered_raw = recover_or_complete_publication(
        backend=backend,
        target_uri=PREFREEZE_SMOKE_LAUNCH_URI,
        publication_binding_sha256=str(launch["prefreeze_smoke_launch_sha256"]),
    )
    if recovered_identity != launch_identity or recovered_raw != launch_raw:
        _fail("prefreeze smoke launch journal recovery differs")
    return {"smoke_launch_identity": launch_identity, "smoke_launch": launch}


def recover_prefreeze_smoke_receipt_v1(
    *,
    backend: JournalBackend,
    expected_panel_object_identity: Mapping[str, object],
    expected_source_commit_sha: str,
    expected_immutable_candidate_image: Mapping[str, object],
) -> dict[str, object]:
    receipt_identity, receipt_raw = _read_known_pinned_v1(
        backend,
        uri=PREFREEZE_SMOKE_RECEIPT_URI,
        label="known prefreeze smoke receipt",
    )
    receipt = execution.validate_t230_prefreeze_smoke_receipt_v1(
        strict_json(receipt_raw, label="known prefreeze smoke receipt"),
        expected_panel_object_identity=expected_panel_object_identity,
        expected_source_commit_sha=expected_source_commit_sha,
        expected_immutable_candidate_image=expected_immutable_candidate_image,
        require_release_runtime=True,
    )
    recovered_receipt_identity, recovered_receipt_raw = (
        recover_or_complete_publication(
            backend=backend,
            target_uri=PREFREEZE_SMOKE_RECEIPT_URI,
            publication_binding_sha256=str(
                receipt["prefreeze_smoke_receipt_sha256"]
            ),
        )
    )
    if (
        recovered_receipt_identity != receipt_identity
        or recovered_receipt_raw != receipt_raw
    ):
        _fail("prefreeze smoke receipt journal recovery differs")
    return {
        "smoke_receipt_identity": receipt_identity,
        "smoke_receipt": receipt,
    }


def recover_prefreeze_smoke_inputs_v1(
    *,
    backend: JournalBackend,
    expected_panel_object_identity: Mapping[str, object],
    expected_source_commit_sha: str,
    expected_immutable_candidate_image: Mapping[str, object],
) -> dict[str, object]:
    receipt_retained = recover_prefreeze_smoke_receipt_v1(
        backend=backend,
        expected_panel_object_identity=expected_panel_object_identity,
        expected_source_commit_sha=expected_source_commit_sha,
        expected_immutable_candidate_image=expected_immutable_candidate_image,
    )
    receipt_identity = receipt_retained["smoke_receipt_identity"]
    receipt = receipt_retained["smoke_receipt"]
    time_identity, time_raw = _read_known_pinned_v1(
        backend,
        uri=PREFREEZE_SMOKE_TIME_V_URI,
        label="known prefreeze smoke GNU time",
    )
    time_binding = build_prefreeze_smoke_time_binding_v1(
        smoke_receipt_identity=receipt_identity,
        smoke_receipt=receipt,
        raw_time_v=time_raw,
    )
    recovered_time_identity, recovered_time_raw = recover_or_complete_publication(
        backend=backend,
        target_uri=PREFREEZE_SMOKE_TIME_V_URI,
        publication_binding_sha256=str(
            time_binding["prefreeze_smoke_time_binding_sha256"]
        ),
    )
    if recovered_time_identity != time_identity or recovered_time_raw != time_raw:
        _fail("prefreeze smoke GNU-time journal recovery differs")
    return {
        "smoke_receipt_identity": receipt_identity,
        "smoke_receipt": receipt,
        "smoke_time_v_identity": time_identity,
        "smoke_time_v": time_raw,
        "smoke_time_binding": time_binding,
    }


def resolve_prefreeze_release_gate_v1(
    *,
    backend: JournalBackend,
    expected_panel_object_identity: Mapping[str, object],
    expected_source_commit_sha: str,
    expected_immutable_candidate_image: Mapping[str, object],
) -> dict[str, object]:
    launch = recover_prefreeze_smoke_launch_v1(
        backend=backend,
        expected_panel_object_identity=expected_panel_object_identity,
        expected_source_commit_sha=expected_source_commit_sha,
        expected_immutable_candidate_image=expected_immutable_candidate_image,
    )
    inputs = recover_prefreeze_smoke_inputs_v1(
        backend=backend,
        expected_panel_object_identity=expected_panel_object_identity,
        expected_source_commit_sha=expected_source_commit_sha,
        expected_immutable_candidate_image=expected_immutable_candidate_image,
    )
    projection_identity, projection_raw = _read_known_pinned_v1(
        backend,
        uri=PREFREEZE_SMOKE_EXECUTION_URI,
        label="known prefreeze smoke execution",
    )
    projection = validate_prefreeze_smoke_execution_v1(
        strict_json(projection_raw, label="known prefreeze smoke execution")
    )
    recovered_projection_identity, recovered_projection_raw = (
        recover_or_complete_publication(
            backend=backend,
            target_uri=PREFREEZE_SMOKE_EXECUTION_URI,
            publication_binding_sha256=str(
                projection["prefreeze_smoke_execution_sha256"]
            ),
        )
    )
    if (
        recovered_projection_identity != projection_identity
        or recovered_projection_raw != projection_raw
    ):
        _fail("prefreeze smoke execution journal recovery differs")
    gate = build_prefreeze_release_gate_v1(
        expected_panel_object_identity=expected_panel_object_identity,
        expected_source_commit_sha=expected_source_commit_sha,
        expected_immutable_candidate_image=expected_immutable_candidate_image,
        smoke_launch_identity=launch["smoke_launch_identity"],
        smoke_launch=launch["smoke_launch"],
        smoke_receipt_identity=inputs["smoke_receipt_identity"],
        smoke_receipt=inputs["smoke_receipt"],
        smoke_time_v_identity=inputs["smoke_time_v_identity"],
        smoke_time_v=inputs["smoke_time_v"],
        smoke_execution_identity=projection_identity,
        smoke_execution=projection,
    )
    return {
        "prefreeze_release_gate": gate,
        "smoke_launch_identity": launch["smoke_launch_identity"],
        "smoke_receipt_identity": inputs["smoke_receipt_identity"],
        "smoke_time_v_identity": inputs["smoke_time_v_identity"],
        "smoke_execution_identity": projection_identity,
    }


def reopen_contract_prefreeze_release_gate_v1(
    *, transport_contract: Mapping[str, object], backend: JournalBackend
) -> dict[str, object]:
    contract = validate_transport_contract_v1(transport_contract)
    retained = resolve_prefreeze_release_gate_v1(
        backend=backend,
        expected_panel_object_identity=contract["prefreeze_release_gate"][
            "panel_object_identity"
        ],
        expected_source_commit_sha=str(contract["source_commit_sha"]),
        expected_immutable_candidate_image=contract["immutable_image"],
    )
    if canonical_json(retained["prefreeze_release_gate"]) != canonical_json(
        contract["prefreeze_release_gate"]
    ):
        _fail("transport contract prefreeze release gate differs on exact replay")
    return retained


def build_benchmark_disposition_v1(
    *,
    transport_contract_identity: Mapping[str, object],
    transport_contract: Mapping[str, object],
    worker_stage_receipt_identity: Mapping[str, object],
    state: str,
    raw_time_v_binding: Mapping[str, object] | None,
    raw_time_v: bytes | None,
    benchmark_execution_terminal_identity: Mapping[str, object] | None,
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    """Choose exactly one terminal benchmark path under one create-once URI."""
    contract = validate_transport_contract_v1(transport_contract)
    contract_identity = _identity(
        transport_contract_identity, label="benchmark disposition contract"
    )
    contract_raw = canonical_json(contract)
    if (
        contract_identity["uri"] != TRANSPORT_CONTRACT_URI
        or contract_identity["sha256"] != sha256(contract_raw).hexdigest()
        or contract_identity["bytes"] != len(contract_raw)
        or read_exact(contract_identity) != contract_raw
    ):
        _fail("benchmark disposition contract differs")
    worker_identity = _identity(
        worker_stage_receipt_identity,
        label="benchmark disposition worker stage",
    )
    worker_raw = read_exact(worker_identity)
    worker = validate_stage_receipt_v1(
        strict_json(worker_raw, label="benchmark disposition worker stage"),
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
    )
    if (
        worker_identity["uri"] != _stage_uri("run-slate", 0)
        or worker.get("runtime_attempt_ordinal") != 0
    ):
        _fail("benchmark disposition worker binding differs")
    worker_start_identity = _identity(
        worker["stage_start_identity"],
        label="benchmark disposition worker start",
    )
    worker_start = strict_json(
        read_exact(worker_start_identity),
        label="benchmark disposition worker start",
    )
    reopen_stage_launch_authority_v1(
        stage_start=worker_start,
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
        runtime_attempt_ordinal=0,
        cloud_execution_name=str(worker["cloud_execution_name"]),
        read_exact=read_exact,
    )
    if state == "raw-ready":
        if worker.get("compute_measurement_recorded") is not True:
            _fail("raw-ready disposition requires the timed worker measurement")
        if not isinstance(raw_time_v_binding, Mapping):
            _fail("raw-ready disposition raw binding differs")
        raw_binding = dict(raw_time_v_binding)
        if (
            set(raw_binding) != {"uri", "sha256", "bytes"}
            or raw_binding.get("uri") != RAW_TIME_V_URI
            or not isinstance(raw_binding.get("sha256"), str)
            or _SHA256.fullmatch(str(raw_binding["sha256"])) is None
            or type(raw_binding.get("bytes")) is not int
            or int(raw_binding["bytes"]) < 1
            or not isinstance(raw_time_v, bytes)
            or len(raw_time_v) != raw_binding["bytes"]
            or sha256(raw_time_v).hexdigest() != raw_binding["sha256"]
            or benchmark_execution_terminal_identity is not None
        ):
            _fail("benchmark disposition raw time-v differs")
        parse_gnu_time_v_v1(raw_time_v)
        try:
            raw_time_v_utf8 = raw_time_v.decode("utf-8")
        except UnicodeDecodeError as exc:  # pragma: no cover - parser precedes
            raise T230TransportError(
                "benchmark disposition raw time-v is not UTF-8"
            ) from exc
        terminal_identity = None
        scale_out_path_retained = True
    elif state == "terminal-abort":
        if raw_time_v_binding is not None or raw_time_v is not None:
            _fail("terminal benchmark disposition cannot retain raw time-v")
        terminal_identity = _identity(
            benchmark_execution_terminal_identity,
            label="benchmark disposition execution terminal",
        )
        reopen_benchmark_execution_terminal_v1(
            benchmark_execution_terminal_identity=terminal_identity,
            transport_contract_identity=contract_identity,
            transport_contract=contract,
            worker_stage_receipt_identity=worker_identity,
            read_exact=read_exact,
        )
        raw_binding = None
        raw_time_v_utf8 = None
        scale_out_path_retained = False
    else:
        _fail("benchmark disposition state differs")
    body = {
        "schema_version": BENCHMARK_DISPOSITION_SCHEMA,
        "run_id": RUN_ID,
        "transport_contract_identity": contract_identity,
        "transport_contract_sha256": contract["transport_contract_sha256"],
        "worker_stage_receipt_identity": worker_identity,
        "worker_stage_receipt_sha256": worker["stage_receipt_sha256"],
        "worker_stage_start_identity": worker["stage_start_identity"],
        "worker_cloud_execution_name": worker["cloud_execution_name"],
        "state": state,
        "raw_time_v_binding": raw_binding,
        "raw_time_v_utf8": raw_time_v_utf8,
        "benchmark_execution_terminal_identity": terminal_identity,
        "scale_out_path_retained": scale_out_path_retained,
        "single_create_once_decision_uri": BENCHMARK_DISPOSITION_URI,
        "opposite_disposition_can_coexist": False,
        "decision_published_before_raw_time_v": True,
        "worker_zero_relaunch_allowed": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "benchmark_disposition_sha256")


def build_benchmark_v1(
    *,
    transport_contract_identity: Mapping[str, object],
    transport_contract: Mapping[str, object],
    worker_stage_receipt_identity: Mapping[str, object],
    benchmark_disposition_identity: Mapping[str, object],
    raw_time_v_identity: Mapping[str, object],
    raw_time_v: bytes,
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    contract = validate_transport_contract_v1(transport_contract)
    contract_identity = _identity(
        transport_contract_identity, label="benchmark transport contract"
    )
    contract_raw = canonical_json(contract)
    if (
        contract_identity["uri"] != TRANSPORT_CONTRACT_URI
        or contract_identity["sha256"] != sha256(contract_raw).hexdigest()
        or contract_identity["bytes"] != len(contract_raw)
        or read_exact(contract_identity) != contract_raw
    ):
        _fail("benchmark transport contract identity/content differs")
    image = _image(contract["immutable_image"], label="benchmark image")
    evidence = _identity(
        contract["image_evidence_identity"], label="benchmark evidence"
    )
    evidence_raw = read_exact(evidence)
    evidence_body = _validate_image_evidence_structural_v1(
        strict_json(evidence_raw, label="benchmark image evidence")
    )
    if (
        evidence_body.get("immutable_image") != image
        or evidence_body.get("source_commit_sha")
        != contract["source_commit_sha"]
    ):
        _fail("benchmark image evidence contract binding differs")
    worker_identity = _identity(
        worker_stage_receipt_identity, label="benchmark worker stage receipt"
    )
    if worker_identity["uri"] != _stage_uri("run-slate", 0):
        _fail("benchmark worker stage receipt URI differs")
    worker_raw = read_exact(worker_identity)
    worker = validate_stage_receipt_v1(
        strict_json(worker_raw, label="benchmark worker stage receipt"),
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
    )
    if (
        len(worker_raw) != worker_identity["bytes"]
        or sha256(worker_raw).hexdigest() != worker_identity["sha256"]
        or worker.get("runtime_attempt_ordinal") != 0
        or worker.get("compute_measurement_recorded") is not True
    ):
        _fail("benchmark worker stage identity/measurement differs")
    worker_runtime_identity = _identity(
        worker["exposed_identities"]["worker_runtime_measurement_identity"],
        label="benchmark worker runtime measurement",
    )
    worker_result_identity = _identity(
        worker["exposed_identities"]["result_identity"],
        label="benchmark worker result",
    )
    worker_runtime_raw = read_exact(worker_runtime_identity)
    worker_result_raw = read_exact(worker_result_identity)
    if (
        not isinstance(worker_runtime_raw, bytes)
        or len(worker_runtime_raw) != worker_runtime_identity["bytes"]
        or sha256(worker_runtime_raw).hexdigest()
        != worker_runtime_identity["sha256"]
        or not isinstance(worker_result_raw, bytes)
        or len(worker_result_raw) != worker_result_identity["bytes"]
        or sha256(worker_result_raw).hexdigest()
        != worker_result_identity["sha256"]
    ):
        _fail("benchmark worker runtime/result exact replay differs")
    try:
        execution._validate_published_runtime_measurement_v1(
            strict_json(
                worker_runtime_raw, label="benchmark worker runtime measurement"
            ),
            role="worker",
            output_prefix=OUTPUT_PREFIX,
            read_exact=read_exact,
        )
    except Exception as exc:
        raise T230TransportError(
            f"benchmark worker runtime mechanics replay failed: {exc}"
        ) from exc
    disposition_identity = _identity(
        benchmark_disposition_identity, label="benchmark disposition"
    )
    disposition_raw = read_exact(disposition_identity)
    decision_raw_identity = _identity(
        raw_time_v_identity, label="benchmark disposition raw time-v"
    )
    expected_disposition = build_benchmark_disposition_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        worker_stage_receipt_identity=worker_identity,
        state="raw-ready",
        raw_time_v_binding={
            "uri": decision_raw_identity["uri"],
            "sha256": decision_raw_identity["sha256"],
            "bytes": decision_raw_identity["bytes"],
        },
        raw_time_v=raw_time_v,
        benchmark_execution_terminal_identity=None,
        read_exact=read_exact,
    )
    if (
        disposition_identity["uri"] != BENCHMARK_DISPOSITION_URI
        or disposition_raw != canonical_json(expected_disposition)
        or len(disposition_raw) != disposition_identity["bytes"]
        or sha256(disposition_raw).hexdigest() != disposition_identity["sha256"]
    ):
        _fail("benchmark disposition differs from raw-ready decision")
    start_identity = _identity(
        worker["stage_start_identity"], label="benchmark worker stage start"
    )
    start_raw = read_exact(start_identity)
    start_body = strict_json(start_raw, label="benchmark worker stage start")
    start = reopen_stage_launch_authority_v1(
        stage_start=start_body,
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
        runtime_attempt_ordinal=0,
        cloud_execution_name=str(worker["cloud_execution_name"]),
        read_exact=read_exact,
    )["stage_start"]
    raw_identity = _identity(raw_time_v_identity, label="benchmark raw time-v")
    if (
        raw_identity["uri"] != RAW_TIME_V_URI
        or raw_identity["bytes"] != len(raw_time_v)
        or raw_identity["sha256"] != sha256(raw_time_v).hexdigest()
        or evidence["uri"]
        != execution.image_evidence_uri_for_output_prefix(OUTPUT_PREFIX)
    ):
        _fail("benchmark raw/image evidence identity differs")
    measurement = parse_gnu_time_v_v1(raw_time_v)
    worker_wall = int(worker["wall_time_millis"])
    worker_rss = int(worker["peak_rss_kib"])
    if (
        int(measurement["wall_time_millis"]) < worker_wall
        or int(measurement["wall_time_millis"]) - worker_wall
        > MAX_OUTER_WORKER_WALL_DELTA_MILLIS
        or int(measurement["peak_rss_kib"]) < worker_rss
        or int(measurement["peak_rss_kib"]) - worker_rss
        > MAX_OUTER_WORKER_RSS_DELTA_KIB
    ):
        _fail("GNU time evidence differs from the bound worker measurement")
    body = {
        "schema_version": BENCHMARK_SCHEMA,
        "run_id": RUN_ID,
        "source_ordinal": 0,
        "transport_contract_identity": contract_identity,
        "transport_contract_sha256": contract["transport_contract_sha256"],
        "source_commit_sha": contract["source_commit_sha"],
        "immutable_image": image,
        "image_evidence_identity": evidence,
        "worker_implementation_sha256": execution.EXPECTED_WORKER_IMPLEMENTATION_SHA256,
        "worker_stage_receipt_identity": worker_identity,
        "benchmark_disposition_identity": disposition_identity,
        "benchmark_disposition_sha256": expected_disposition[
            "benchmark_disposition_sha256"
        ],
        "worker_stage_receipt_sha256": worker["stage_receipt_sha256"],
        "worker_stage_start_identity": start_identity,
        "worker_stage_start_sha256": start["stage_start_sha256"],
        "worker_cloud_execution_name": worker["cloud_execution_name"],
        "worker_wall_time_millis": worker_wall,
        "worker_peak_rss_kib": worker_rss,
        "worker_runtime_measurement_identity": worker_runtime_identity,
        "worker_result_identity": worker_result_identity,
        "raw_time_v_identity": raw_identity,
        "raw_time_v_sha256": raw_identity["sha256"],
        "parser_contract": frozen_time_v_parser_contract_v1(),
        "parser_implementation_sha256": EXPECTED_TIME_V_PARSER_SHA256,
        **measurement,
        "result_fields_inspected": [],
        "mechanics_only": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "benchmark_sha256")


def validate_benchmark_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("mechanics benchmark must be one object")
    item = dict(value)
    _validate_self_hash(item, field="benchmark_sha256", label="mechanics benchmark")
    required = {
        "schema_version", "run_id", "source_ordinal", "immutable_image",
        "transport_contract_identity", "transport_contract_sha256",
        "source_commit_sha",
        "image_evidence_identity", "worker_implementation_sha256",
        "benchmark_disposition_identity", "benchmark_disposition_sha256",
        "worker_stage_receipt_identity", "worker_stage_receipt_sha256",
        "worker_stage_start_identity", "worker_stage_start_sha256",
        "worker_cloud_execution_name", "worker_runtime_measurement_identity",
        "worker_result_identity",
        "worker_wall_time_millis", "worker_peak_rss_kib",
        "raw_time_v_identity", "raw_time_v_sha256", "parser_contract",
        "parser_implementation_sha256",
        "timed_command", "wall_time_millis", "peak_rss_kib", "exit_code",
        "result_fields_inspected", "mechanics_only", *_FALSE_AUTHORITY_FIELDS,
        "benchmark_sha256",
    }
    if set(item) != required:
        _fail("mechanics benchmark fields differ")
    _false_authorities(item, label="mechanics benchmark")
    wall = item.get("wall_time_millis")
    rss = item.get("peak_rss_kib")
    timeout_headroom = TASK_TIMEOUT_SECONDS - ((int(wall) + 999) // 1000) if type(wall) is int else -1
    # Keep all gate arithmetic explicit and integer-only.  The equivalent
    # multiplication below avoids floating-point rounding in the 20% law.
    if (
        item.get("schema_version") != BENCHMARK_SCHEMA
        or item.get("run_id") != RUN_ID
        or item.get("source_ordinal") != 0
        or _identity(
            item.get("transport_contract_identity"),
            label="benchmark transport contract",
        )["uri"] != TRANSPORT_CONTRACT_URI
        or not isinstance(item.get("transport_contract_sha256"), str)
        or _SHA256.fullmatch(str(item["transport_contract_sha256"])) is None
        or not isinstance(item.get("source_commit_sha"), str)
        or _COMMIT.fullmatch(str(item["source_commit_sha"])) is None
        or item.get("immutable_image") is None
        or _image(item["immutable_image"], label="benchmark image") != item["immutable_image"]
        or _identity(item.get("image_evidence_identity"), label="benchmark evidence")["uri"]
        != execution.image_evidence_uri_for_output_prefix(OUTPUT_PREFIX)
        or item.get("worker_implementation_sha256")
        != execution.EXPECTED_WORKER_IMPLEMENTATION_SHA256
        or _identity(
            item.get("benchmark_disposition_identity"),
            label="benchmark disposition",
        )["uri"] != BENCHMARK_DISPOSITION_URI
        or not isinstance(item.get("benchmark_disposition_sha256"), str)
        or _SHA256.fullmatch(str(item["benchmark_disposition_sha256"])) is None
        or _identity(
            item.get("worker_stage_receipt_identity"),
            label="benchmark worker stage receipt",
        )["uri"] != _stage_uri("run-slate", 0)
        or not isinstance(item.get("worker_stage_receipt_sha256"), str)
        or _SHA256.fullmatch(str(item["worker_stage_receipt_sha256"])) is None
        or _identity(
            item.get("worker_stage_start_identity"),
            label="benchmark worker stage start",
        )["uri"] != stage_start_uri("run-slate", 0, 0)
        or not isinstance(item.get("worker_stage_start_sha256"), str)
        or _SHA256.fullmatch(str(item["worker_stage_start_sha256"])) is None
        or not isinstance(item.get("worker_cloud_execution_name"), str)
        or _EXECUTION.fullmatch(str(item["worker_cloud_execution_name"])) is None
        or _identity(
            item.get("worker_runtime_measurement_identity"),
            label="benchmark worker runtime",
        )["uri"]
        != execution.runtime_measurement_uri_for_output_prefix(
            OUTPUT_PREFIX,
            role="worker",
            source_ordinal=0,
            runtime_attempt_ordinal=0,
        )
        or _identity(
            item.get("worker_result_identity"),
            label="benchmark worker result",
        )["uri"] == ""
        or type(item.get("worker_wall_time_millis")) is not int
        or type(item.get("worker_peak_rss_kib")) is not int
        or int(item["worker_wall_time_millis"]) < 1
        or int(item["worker_peak_rss_kib"]) < 1
        or _identity(item.get("raw_time_v_identity"), label="benchmark raw time-v")[
            "uri"
        ] != RAW_TIME_V_URI
        or item.get("raw_time_v_sha256")
        != item["raw_time_v_identity"]["sha256"]
        or item.get("parser_contract") != frozen_time_v_parser_contract_v1()
        or item.get("parser_implementation_sha256")
        != EXPECTED_TIME_V_PARSER_SHA256
        or item.get("timed_command") != BENCHMARK_COMMAND
        or type(wall) is not int
        or type(rss) is not int
        or int(wall) < int(item["worker_wall_time_millis"])
        or int(wall) - int(item["worker_wall_time_millis"])
        > MAX_OUTER_WORKER_WALL_DELTA_MILLIS
        or int(rss) < int(item["worker_peak_rss_kib"])
        or int(rss) - int(item["worker_peak_rss_kib"])
        > MAX_OUTER_WORKER_RSS_DELTA_KIB
        or not 1 <= int(wall) <= MAX_WALL_TIME_MILLIS
        or not 1 <= int(rss) <= MAX_PEAK_RSS_KIB
        or MEMORY_LIMIT_MIB * 1024 - int(rss) < MIN_RSS_HEADROOM_KIB
        or timeout_headroom < MIN_TIMEOUT_HEADROOM_SECONDS
        or TASK_TIMEOUT_SECONDS * 1000 * MIN_TIMEOUT_HEADROOM_FRACTION_DENOMINATOR
        < int(wall) * (
            MIN_TIMEOUT_HEADROOM_FRACTION_DENOMINATOR
            + MIN_TIMEOUT_HEADROOM_FRACTION_NUMERATOR
        )
        or item.get("exit_code") != 0
        or item.get("result_fields_inspected") != []
        or item.get("mechanics_only") is not True
    ):
        _fail("mechanics benchmark does not pass the frozen numeric gate")
    return item


def build_benchmark_terminal_abort_v1(
    *,
    transport_contract_identity: Mapping[str, object],
    transport_contract: Mapping[str, object],
    worker_stage_receipt_identity: Mapping[str, object],
    benchmark_disposition_identity: Mapping[str, object],
    benchmark_execution_terminal_identity: Mapping[str, object],
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    """Seal the run when worker zero finished but its time-v transaction did not."""
    contract = validate_transport_contract_v1(transport_contract)
    contract_identity = _identity(
        transport_contract_identity, label="benchmark abort contract"
    )
    contract_raw = canonical_json(contract)
    if (
        contract_identity["uri"] != TRANSPORT_CONTRACT_URI
        or contract_identity["sha256"] != sha256(contract_raw).hexdigest()
        or contract_identity["bytes"] != len(contract_raw)
        or read_exact(contract_identity) != contract_raw
    ):
        _fail("benchmark abort contract identity differs")
    worker_identity = _identity(
        worker_stage_receipt_identity, label="benchmark abort worker stage"
    )
    worker_raw = read_exact(worker_identity)
    worker = validate_stage_receipt_v1(
        strict_json(worker_raw, label="benchmark abort worker stage"),
        transport_contract_sha256=str(contract["transport_contract_sha256"]),
        operation="run-slate",
        source_ordinal=0,
    )
    if (
        worker_identity["uri"] != _stage_uri("run-slate", 0)
        or worker.get("runtime_attempt_ordinal") != 0
    ):
        _fail("benchmark abort worker binding differs")
    disposition_identity = _identity(
        benchmark_disposition_identity, label="benchmark abort disposition"
    )
    disposition_raw = read_exact(disposition_identity)
    expected_disposition = build_benchmark_disposition_v1(
        transport_contract_identity=contract_identity,
        transport_contract=contract,
        worker_stage_receipt_identity=worker_identity,
        state="terminal-abort",
        raw_time_v_binding=None,
        raw_time_v=None,
        benchmark_execution_terminal_identity=(
            benchmark_execution_terminal_identity
        ),
        read_exact=read_exact,
    )
    if (
        disposition_identity["uri"] != BENCHMARK_DISPOSITION_URI
        or disposition_raw != canonical_json(expected_disposition)
    ):
        _fail("benchmark abort disposition differs")
    body = {
        "schema_version": BENCHMARK_ABORT_SCHEMA,
        "run_id": RUN_ID,
        "transport_contract_identity": contract_identity,
        "transport_contract_sha256": contract["transport_contract_sha256"],
        "worker_stage_receipt_identity": worker_identity,
        "worker_stage_receipt_sha256": worker["stage_receipt_sha256"],
        "worker_stage_start_identity": worker["stage_start_identity"],
        "worker_result_identity": worker["exposed_identities"]["result_identity"],
        "benchmark_disposition_identity": disposition_identity,
        "benchmark_disposition_sha256": expected_disposition[
            "benchmark_disposition_sha256"
        ],
        "benchmark_execution_terminal_identity": _identity(
            benchmark_execution_terminal_identity,
            label="benchmark abort execution terminal",
        ),
        "raw_time_v_identity": None,
        "compute_release_identity": None,
        "benchmark_transaction_recoverable": False,
        "scale_out_licensed": False,
        "relaunch_worker_zero_allowed": False,
        "new_frozen_run_id_and_output_prefix_required": True,
        "terminal": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "benchmark_terminal_abort_sha256")


def build_compute_release_v1(
    *,
    benchmark_identity: Mapping[str, object],
    benchmark: Mapping[str, object],
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    retained = validate_benchmark_v1(benchmark)
    identity = _identity(benchmark_identity, label="benchmark")
    if (
        identity["uri"] != BENCHMARK_URI
        or identity["sha256"] != sha256(canonical_json(retained)).hexdigest()
        or identity["bytes"] != len(canonical_json(retained))
    ):
        _fail("benchmark identity/content differs")
    raw_identity = _identity(
        retained["raw_time_v_identity"], label="compute-release raw time-v"
    )
    raw = read_exact(raw_identity)
    if (
        not isinstance(raw, bytes)
        or sha256(raw).hexdigest() != raw_identity["sha256"]
        or len(raw) != raw_identity["bytes"]
        or parse_gnu_time_v_v1(raw)
        != {
            "timed_command": retained["timed_command"],
            "wall_time_millis": retained["wall_time_millis"],
            "peak_rss_kib": retained["peak_rss_kib"],
            "exit_code": retained["exit_code"],
        }
    ):
        _fail("compute release does not replay raw GNU time evidence")
    contract_identity = _identity(
        retained["transport_contract_identity"],
        label="compute-release transport contract",
    )
    contract_raw = read_exact(contract_identity)
    worker_identity = _identity(
        retained["worker_stage_receipt_identity"],
        label="compute-release worker stage",
    )
    expected_benchmark = build_benchmark_v1(
        transport_contract_identity=contract_identity,
        transport_contract=strict_json(
            contract_raw, label="compute-release transport contract"
        ),
        worker_stage_receipt_identity=worker_identity,
        benchmark_disposition_identity=_identity(
            retained["benchmark_disposition_identity"],
            label="compute-release benchmark disposition",
        ),
        raw_time_v_identity=raw_identity,
        raw_time_v=raw,
        read_exact=read_exact,
    )
    if canonical_json(retained) != canonical_json(expected_benchmark):
        _fail("compute release benchmark differs from exact stage/contract replay")
    body = {
        "schema_version": COMPUTE_RELEASE_SCHEMA,
        "run_id": RUN_ID,
        "output_prefix": OUTPUT_PREFIX,
        "compute_gate": frozen_compute_gate_v1(),
        "transport_contract_identity": contract_identity,
        "transport_contract_sha256": retained["transport_contract_sha256"],
        "benchmark_identity": identity,
        "benchmark_sha256": retained["benchmark_sha256"],
        "benchmark_disposition_identity": retained[
            "benchmark_disposition_identity"
        ],
        "benchmark_disposition_sha256": retained[
            "benchmark_disposition_sha256"
        ],
        "raw_time_v_identity": raw_identity,
        "worker_stage_receipt_identity": worker_identity,
        "parser_implementation_sha256": EXPECTED_TIME_V_PARSER_SHA256,
        "scale_out_licensed": True,
        "support_or_book_fields_inspected": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _self_hash(body, "compute_release_sha256")


def reopen_compute_release_v1(
    *,
    compute_release_identity: Mapping[str, object],
    read_exact: Callable[[Mapping[str, object]], bytes],
) -> dict[str, object]:
    identity = _identity(compute_release_identity, label="compute release")
    if identity["uri"] != COMPUTE_RELEASE_URI:
        _fail("compute release URI differs")
    raw = read_exact(identity)
    if not isinstance(raw, bytes):
        _fail("compute release exact read differs")
    body = strict_json(raw, label="compute release")
    benchmark_identity = _identity(
        body.get("benchmark_identity"), label="compute release benchmark"
    )
    benchmark_raw = read_exact(benchmark_identity)
    if not isinstance(benchmark_raw, bytes):
        _fail("compute release benchmark exact read differs")
    expected = build_compute_release_v1(
        benchmark_identity=benchmark_identity,
        benchmark=strict_json(benchmark_raw, label="compute release benchmark"),
        read_exact=read_exact,
    )
    if canonical_json(body) != canonical_json(expected):
        _fail("compute release differs after raw benchmark replay")
    return expected


def lane_for_source_ordinal(source_ordinal: int) -> dict[str, object]:
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("source ordinal must be one exact integer in 0..53")
    for row in LANE_CONTRACT:
        if source_ordinal in row["source_ordinals"]:
            return dict(row)
    _fail("source ordinal is outside both fixed lanes")


__all__ = [
    "BENCHMARK_ABORT_URI",
    "BENCHMARK_COMMAND",
    "BENCHMARK_DISPOSITION_URI",
    "BENCHMARK_EXECUTION_TERMINAL_URI",
    "BENCHMARK_SCHEMA",
    "BENCHMARK_URI",
    "COMPUTE_RELEASE_URI",
    "EXPECTED_TIME_V_PARSER_SHA256",
    "JournalBackend",
    "JournalObjectExists",
    "LANE_CONTRACT",
    "MAX_RETRIES",
    "OUTPUT_PREFIX",
    "PREFREEZE_OUTPUT_PREFIX",
    "PREFREEZE_SMOKE_EXECUTION_URI",
    "PREFREEZE_SMOKE_LAUNCH_URI",
    "PREFREEZE_SMOKE_RECEIPT_URI",
    "PREFREEZE_SMOKE_TIME_V_URI",
    "RAW_TIME_V_URI",
    "REPOSITORY_ROOT",
    "RUNTIME_EVIDENCE_PATH",
    "RecoverablePublisher",
    "RUN_ID",
    "SOURCE_SNAPSHOT_PATH",
    "SOURCE_SNAPSHOT_PATHS",
    "SnapshotGitAdapter",
    "T230TransportError",
    "TRANSPORT_CONTRACT_URI",
    "build_compute_release_v1",
    "build_benchmark_v1",
    "build_benchmark_disposition_v1",
    "build_benchmark_execution_terminal_v1",
    "build_benchmark_terminal_abort_v1",
    "build_image_evidence_v1",
    "build_image_evidence_publication_binding_v1",
    "build_lane_ledger_v1",
    "build_job_config_v1",
    "build_launch_request_v1",
    "build_prefreeze_release_gate_v1",
    "build_prefreeze_smoke_execution_v1",
    "build_prefreeze_smoke_launch_v1",
    "build_prefreeze_smoke_time_binding_v1",
    "build_source_snapshot_v1",
    "build_stage_receipt_v1",
    "build_stage_start_v1",
    "build_transport_contract_v1",
    "canonical_json",
    "frozen_compute_gate_v1",
    "frozen_time_v_parser_contract_v1",
    "lane_for_source_ordinal",
    "lane_ledger_uri",
    "launch_request_uri",
    "job_config_uri",
    "materialize_image_evidence_v1",
    "parse_gnu_time_v_v1",
    "parse_prefreeze_smoke_time_v_v1",
    "recover_completed_publication",
    "recover_or_complete_publication",
    "recover_publication_proof_v1",
    "recover_prefreeze_smoke_inputs_v1",
    "recover_prefreeze_smoke_launch_v1",
    "recover_prefreeze_smoke_receipt_v1",
    "reopen_benchmark_execution_terminal_v1",
    "reopen_compute_release_v1",
    "reopen_lane_ledger_v1",
    "reopen_launch_request_v1",
    "reopen_job_config_v1",
    "reopen_stage_launch_authority_v1",
    "reopen_contract_prefreeze_release_gate_v1",
    "resolve_prefreeze_release_gate_v1",
    "strict_json",
    "stage_start_uri",
    "validate_benchmark_v1",
    "validate_compute_gate_v1",
    "validate_finalizer_execution_distinct_v1",
    "validate_source_snapshot_v1",
    "validate_runtime_source_snapshot_v1",
    "validate_stage_receipt_v1",
    "validate_stage_predecessor_inputs_v1",
    "validate_stage_start_v1",
    "validate_publication_proof_v1",
    "validate_prefreeze_release_gate_v1",
    "validate_prefreeze_smoke_execution_v1",
    "validate_prefreeze_smoke_launch_v1",
    "validate_transport_contract_against_baked_snapshot_v1",
    "validate_transport_contract_v1",
]
