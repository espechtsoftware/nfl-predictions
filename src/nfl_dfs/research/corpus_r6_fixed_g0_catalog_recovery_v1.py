"""Reviewed recovery authority for the fixed-G0 structural catalog.

This module deliberately separates four states:

* a clean-commit, read-only task-0 reality smoke;
* a tracked review lock binding that smoke and the two consumed predecessors;
* a later tracked final lock licensing exactly recovery attempt three; and
* a terminal outer attestation published only after the deterministic inner
  catalog receipt has been exact-reopened.

The first state has no cloud-write capability.  The review lock alone has no
publication authority.  Only a validated final lock can mint the in-process
capability accepted by the mutation boundary.  The outer attestation is the
object a downstream consumer must pin; the older inner receipt remains a
non-authoritative deterministic projection.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
from types import MappingProxyType
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_projection_successor_v1 as successor
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog


class CorpusR6FixedG0CatalogRecoveryV1Error(RuntimeError):
    """Recovery evidence, authority, transport, or replay differs."""


REVIEW_LOCK_SCHEMA: Final = "corpus-r6-fixed-g0-catalog-recovery-review-lock/v2"
FINAL_LOCK_SCHEMA: Final = "corpus-r6-fixed-g0-catalog-recovery-final-lock/v2"
SMOKE_EVIDENCE_SCHEMA: Final = (
    "corpus-r6-fixed-g0-catalog-recovery-task0-smoke-evidence/v2"
)
EMPTY_PREFIX_EVIDENCE_SCHEMA: Final = (
    "corpus-r6-fixed-g0-catalog-empty-prefix-evidence/v2"
)
ATTEMPT_SCHEMA: Final = "corpus-r6-fixed-g0-catalog-recovery-attempt/v2"
OUTER_ATTESTATION_SCHEMA: Final = (
    "corpus-r6-fixed-g0-catalog-recovery-attestation/v2"
)
FOCUSED_TEST_RECEIPT_SCHEMA: Final = (
    "corpus-r6-fixed-g0-catalog-recovery-focused-test-receipt/v2"
)

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]
RECOVERY_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_fixed_g0_catalog_recovery_v1.py"
)
RUNNER_PATH: Final = "scripts/run_corpus_r6_fixed_g0_catalog_recovery_v1.py"
SCRIPTS_INIT_PATH: Final = "scripts/__init__.py"
FOCUSED_WRAPPER_PATH: Final = (
    "scripts/run_corpus_r6_fixed_g0_catalog_recovery_focused_v1.py"
)
NFL_DFS_INIT_PATH: Final = "src/nfl_dfs/__init__.py"
RESEARCH_INIT_PATH: Final = "src/nfl_dfs/research/__init__.py"
RECOVERY_TEST_PATH: Final = "tests/test_run_corpus_r6_fixed_g0_catalog_recovery_v1.py"
SUCCESSOR_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_player_catalog_fixed_g0_projection_successor_v1.py"
)
SUCCESSOR_TEST_PATH: Final = (
    "tests/test_corpus_r6_player_catalog_fixed_g0_projection_successor_v1.py"
)
IMPLEMENTATION_PATHS: Final = (
    adapter.FIXED_ADAPTER_MODULE_PATH,
    adapter.FIXED_ADAPTER_TEST_PATH,
    adapter.FIXED_CATALOG_MODULE_PATH,
    adapter.FIXED_BATCH_MODULE_PATH,
    SUCCESSOR_MODULE_PATH,
    SUCCESSOR_TEST_PATH,
    RECOVERY_MODULE_PATH,
    SCRIPTS_INIT_PATH,
    RUNNER_PATH,
    FOCUSED_WRAPPER_PATH,
    NFL_DFS_INIT_PATH,
    RESEARCH_INIT_PATH,
    RECOVERY_TEST_PATH,
)

SMOKE_EVIDENCE_PATH: Final = (
    "reports/2026-08-27-r6-fixed-g0-catalog-recovery-task0-smoke.json"
)
EMPTY_PREFIX_EVIDENCE_PATH: Final = (
    "reports/2026-08-27-r6-fixed-g0-catalog-empty-prefix-evidence.json"
)
FOCUSED_TEST_OUTPUT_PATH: Final = (
    "reports/2026-08-27-r6-fixed-g0-catalog-recovery-focused-test-junit.xml"
)
FOCUSED_TEST_RECEIPT_PATH: Final = (
    "reports/2026-08-27-r6-fixed-g0-catalog-recovery-focused-test-receipt.json"
)
FOCUSED_TEST_RUNTIME_JUNIT_PATH: Final = (
    "/tmp/r6-fixed-g0-catalog-recovery-focused-test-junit.xml"
)
REVIEW_LOCK_PATH: Final = (
    "reports/2026-08-27-r6-fixed-g0-catalog-recovery-review-lock.json"
)
FINAL_LOCK_PATH: Final = (
    "reports/2026-08-27-r6-fixed-g0-catalog-recovery-final-lock.json"
)
ATTEMPT_PATH: Final = (
    "reports/2026-08-27-r6-fixed-g0-catalog-recovery-attempt-3.json"
)

ENABLE_ENV: Final = "R6_FIXED_G0_CATALOG_RECOVERY_ENABLED"
OUTER_ATTESTATION_FILENAME: Final = (
    "fixed-g0-catalog-recovery-attestation-v2.json"
)
OUTER_ATTESTATION_URI: Final = (
    f"{adapter.FIXED_CATALOG_NAMESPACE}{OUTER_ATTESTATION_FILENAME}"
)
EXPECTED_INNER_OBJECT_COUNT: Final = catalog.TASK_COUNT * 2 + 2
EXPECTED_TOTAL_OBJECT_COUNT: Final = EXPECTED_INNER_OBJECT_COUNT + 1
RECOVERY_ATTEMPT_ORDINAL: Final = 3
MAXIMUM_LIFETIME_PROJECTION_ATTEMPTS: Final = 3
DURABLE_REMOTE_REF: Final = "refs/remotes/origin/main"

SMOKE_COMMAND: Final = (
    ".venv/bin/python",
    RUNNER_PATH,
    "smoke",
)
PUBLISH_COMMAND: Final = (
    ".venv/bin/python",
    RUNNER_PATH,
    "publish",
    "--execute",
)
ATTEMPT_MARKER_COMMAND: Final = (
    ".venv/bin/python",
    RUNNER_PATH,
    "build-attempt-marker",
    "--output",
    ATTEMPT_PATH,
    "--build",
)
REOPEN_COMMAND: Final = (
    ".venv/bin/python",
    RUNNER_PATH,
    "reopen",
)
FOCUSED_TEST_COMMAND: Final = (
    ".venv/bin/python",
    "-I",
    FOCUSED_WRAPPER_PATH,
    "-c",
    "/dev/null",
    "-p",
    "no:cacheprovider",
    "--noconftest",
    "--rootdir=.",
    "-q",
    "--tb=short",
    f"--junitxml={FOCUSED_TEST_RUNTIME_JUNIT_PATH}",
    adapter.FIXED_ADAPTER_TEST_PATH,
    SUCCESSOR_TEST_PATH,
    RECOVERY_TEST_PATH,
)
FOCUSED_TEST_CLASSNAMES: Final = (
    "tests.test_corpus_r6_player_catalog_fixed_g0_adapter_v1",
    "tests.test_corpus_r6_player_catalog_fixed_g0_projection_successor_v1",
    "tests.test_run_corpus_r6_fixed_g0_catalog_recovery_v1",
)
FOCUSED_TESTCASE_COUNT_BY_CLASSNAME: Final = {
    FOCUSED_TEST_CLASSNAMES[0]: 125,
    FOCUSED_TEST_CLASSNAMES[1]: 26,
    FOCUSED_TEST_CLASSNAMES[2]: 50,
}
FOCUSED_TESTCASE_COUNT: Final = 201
FOCUSED_TESTCASE_INVENTORY_SHA256: Final = (
    "96df8fda2fc03c87d0a0fedde17266063e2c37614ccec1a3e460d18562ea16bd"
)

_SHA = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.+-]+Z")

_FALSE_AUTHORITY_FIELDS: Final = (
    "analytical_authority",
    "automatic_retry_licensed",
    "corpus_fill_licensed",
    "corpus_retrieval_licensed",
    "decision_authority",
    "deployment_authority",
    "fill_authority",
    "graph_mutation_licensed",
    "historical_scoring_authority",
    "historical_scoring_licensed",
    "live_strategy_authority",
    "production_change_licensed",
    "production_policy_authority",
    "promotion_authority",
    "publication_authority",
    "r6_source_authority",
    "retrieval_authority",
    "selection_authority",
)


@dataclass(frozen=True, slots=True)
class HistoricalEvidenceBindingV1:
    role: str
    commit_sha: str
    relative_path: str
    sha256: str
    bytes: int
    schema_version: str | None = None
    internal_field: str | None = None
    internal_sha256: str | None = None


HISTORICAL_EVIDENCE: Final = (
    HistoricalEvidenceBindingV1(
        role="original_projection_final_lock",
        commit_sha=successor.OLD_FINAL_LOCK_COMMIT,
        relative_path=successor.OLD_FINAL_LOCK_PATH,
        sha256=successor.OLD_FINAL_LOCK_SHA256,
        bytes=successor.OLD_FINAL_LOCK_BYTES,
        schema_version=successor.OLD_FINAL_LOCK_SCHEMA,
        internal_field="final_release_lock_sha256",
        internal_sha256=successor.OLD_FINAL_LOCK_INTERNAL_SHA256,
    ),
    HistoricalEvidenceBindingV1(
        role="successor_projection_final_lock",
        commit_sha="3c60aca22adbea768f24c3248385a44523dbb9bf",
        relative_path=successor.FINAL_LOCK_PATH,
        sha256="c73de3901ccb3eb228aeb1a18a9b28d9a833ab66632abc0763d94782b408eb32",
        bytes=7852,
        schema_version=successor.FINAL_LOCK_SCHEMA,
        internal_field="projection_successor_final_lock_sha256",
        internal_sha256=(
            "0c9cf97589ade08b92487b6cca51d8c91643dc06912510d0d608f870a8d6715f"
        ),
    ),
    HistoricalEvidenceBindingV1(
        role="consumed_successor_attempt_2",
        commit_sha="5d7061dd81c51897bbf101b1d85c2480e3094f2e",
        relative_path=successor.PROJECTION_ATTEMPT_PATH,
        sha256="8af71640248bbb67d4210227a529c450fb1645c0b76a01e8dd24b7d8c1c3abdc",
        bytes=3907,
        schema_version=successor.PROJECTION_ATTEMPT_SCHEMA,
        internal_field="projection_successor_attempt_sha256",
        internal_sha256=(
            "fef7b15fe1c5b4c566153f2f7d22b130f519ee012f49a35690294c4f25a0a02c"
        ),
    ),
    HistoricalEvidenceBindingV1(
        role="successor_attempt_2_carrier_schema_failure",
        commit_sha="5d7061dd81c51897bbf101b1d85c2480e3094f2e",
        relative_path=(
            "reports/2026-08-26-r6-catalog-successor-attempt-2-"
            "carrier-schema-failure.md"
        ),
        sha256="13ac388fa2813070b107b3f545477404b6cac85008480c86a50d367e6305d50f",
        bytes=3094,
    ),
)


@dataclass(frozen=True, slots=True)
class PublicationCapabilityV1:
    """Resolved Git evidence; never publication authority by itself."""

    current_clean_commit_sha: str
    implementation_commit_sha: str
    implementation_measurements: tuple[Mapping[str, object], ...]
    review_lock_commit_sha: str
    review_lock_file: Mapping[str, object]
    review_lock_internal_sha256: str
    final_lock_commit_sha: str
    final_lock_file: Mapping[str, object]
    final_lock_internal_sha256: str
    review_lock: Mapping[str, object]
    final_lock: Mapping[str, object]
    base_adapter_review: adapter.AdapterReviewBindingV1
    capability_sha256: str


@dataclass(frozen=True, slots=True)
class TrackedAttemptBindingV1:
    """Resolved tracked attempt evidence; not publication authority by itself."""

    reopened_at_commit_sha: str
    marker_commit_sha: str
    marker: Mapping[str, object]
    marker_file: Mapping[str, object]
    marker_internal_sha256: str


def _fail(message: str) -> None:
    raise CorpusR6FixedG0CatalogRecoveryV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryV1Error(str(exc)) from exc


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


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{label} must be one nonempty canonical string")
    return value


def _sha(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if _SHA.fullmatch(retained) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return retained


def _commit(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if _COMMIT.fullmatch(retained) is None:
        _fail(f"{label} must be one full lowercase commit SHA")
    return retained


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _exact_keys(value: Mapping[str, object], keys: frozenset[str], *, label: str) -> None:
    if frozenset(value) != keys:
        _fail(f"{label} fields differ")


def _false_authorities(value: Mapping[str, object], *, label: str) -> None:
    differing = [field for field in _FALSE_AUTHORITY_FIELDS if value.get(field) is not False]
    if differing:
        _fail(f"{label} carries non-false authorities {differing}")


def _self_hash(value: Mapping[str, object], field: str) -> dict[str, object]:
    body = dict(value)
    body[field] = canonical_sha256(body)
    return body


def _validate_self_hash(value: Mapping[str, object], *, field: str, label: str) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    if retained != canonical_sha256({key: item for key, item in value.items() if key != field}):
        _fail(f"{label} self-hash differs")
    return retained


def _parse_json(raw: object, *, label: str, allow_newline: bool = True) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    retained = raw[:-1] if allow_newline and raw.endswith(b"\n") else raw
    try:
        parsed = batch.parse_canonical_json_bytes(retained, label=label)
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryV1Error(str(exc)) from exc
    return _mapping(parsed, label=label)


def normalize_file_binding(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, frozenset({"relative_path", "sha256", "bytes"}), label=label)
    path = _string(item["relative_path"], label=f"{label}.relative_path")
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts or candidate.as_posix() != path:
        _fail(f"{label} path must be one canonical repository-relative path")
    return {
        "relative_path": path,
        "sha256": _sha(item["sha256"], label=f"{label}.sha256"),
        "bytes": _exact_int(item["bytes"], label=f"{label}.bytes", minimum=1),
    }


def file_binding(path: str, raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail("file binding requires nonempty exact bytes")
    normalized = normalize_file_binding(
        {"relative_path": path, "sha256": sha256(raw).hexdigest(), "bytes": len(raw)},
        label="file binding",
    )
    return normalized


_FOCUSED_TEST_RECEIPT_FIELDS: Final = frozenset({
    "schema_version",
    "implementation_commit_sha",
    "implementation_measurements_sha256",
    "command",
    "exit_code",
    "pass_count",
    "failure_count",
    "error_count",
    "skipped_count",
    "testcase_count_by_classname",
    "testcase_count",
    "testcase_inventory",
    "testcase_scope_sha256",
    "output_file",
    "completed_at_utc",
    "passed",
    "complete",
    *_FALSE_AUTHORITY_FIELDS,
    "focused_test_receipt_sha256",
})


def build_focused_test_receipt_v1(
    *,
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    output_file: Mapping[str, object],
    exact_output_raw: bytes,
) -> dict[str, object]:
    commit = _commit(implementation_commit_sha, label="focused-test implementation commit")
    measurements = normalize_implementation_measurements_v1(
        implementation_measurements
    )
    output = normalize_file_binding(output_file, label="focused-test output file")
    if file_binding(FOCUSED_TEST_OUTPUT_PATH, exact_output_raw) != output:
        _fail("focused-test JUnit binding differs")
    try:
        root = ET.fromstring(exact_output_raw)
    except ET.ParseError as exc:
        raise CorpusR6FixedG0CatalogRecoveryV1Error(
            "focused-test JUnit is not well-formed"
        ) from exc
    suites = [root] if root.tag == "testsuite" else list(root)
    if root.tag not in {"testsuite", "testsuites"} or len(suites) != 1 or suites[0].tag != "testsuite":
        _fail("focused-test JUnit suite shape differs")
    suite = suites[0]
    total = _exact_int(int(suite.attrib.get("tests", "-1")), label="JUnit tests", minimum=1)
    failures = _exact_int(int(suite.attrib.get("failures", "-1")), label="JUnit failures")
    errors = _exact_int(int(suite.attrib.get("errors", "-1")), label="JUnit errors")
    skipped = _exact_int(int(suite.attrib.get("skipped", "-1")), label="JUnit skipped")
    passed = total - failures - errors - skipped
    cases = list(suite.iter("testcase"))
    observed_failures = sum(case.find("failure") is not None for case in cases)
    observed_errors = sum(case.find("error") is not None for case in cases)
    observed_skipped = sum(case.find("skipped") is not None for case in cases)
    counts_by_classname = {
        classname: sum(
            case.attrib.get("classname") == classname for case in cases
        )
        for classname in FOCUSED_TEST_CLASSNAMES
    }
    observed_classnames = {case.attrib.get("classname") for case in cases}
    timestamp = _string(suite.attrib.get("timestamp"), label="focused-test completed_at_utc")
    if (
        output["relative_path"] != FOCUSED_TEST_OUTPUT_PATH
        or len(cases) != total
        or observed_failures != failures
        or observed_errors != errors
        or observed_skipped != skipped
        or skipped != 0
        or observed_classnames != set(FOCUSED_TEST_CLASSNAMES)
        or counts_by_classname != FOCUSED_TESTCASE_COUNT_BY_CLASSNAME
        or total != FOCUSED_TESTCASE_COUNT
        or failures != 0
        or errors != 0
        or passed < 1
        or not timestamp
    ):
        _fail("focused-test passing receipt semantics differ")
    testcase_inventory = sorted([
        {
            "classname": case.attrib.get("classname"),
            "name": case.attrib.get("name"),
        }
        for case in cases
    ], key=lambda row: (str(row["classname"]), str(row["name"])))
    if len(set((row["classname"], row["name"]) for row in testcase_inventory)) != len(testcase_inventory):
        _fail("focused-test JUnit testcase inventory repeats")
    if canonical_sha256(testcase_inventory) != FOCUSED_TESTCASE_INVENTORY_SHA256:
        _fail("focused-test JUnit differs from the exact reviewed 201-case inventory")
    return _self_hash({
        "schema_version": FOCUSED_TEST_RECEIPT_SCHEMA,
        "implementation_commit_sha": commit,
        "implementation_measurements_sha256": canonical_sha256(measurements),
        "command": list(FOCUSED_TEST_COMMAND),
        "exit_code": 0,
        "pass_count": passed,
        "failure_count": 0,
        "error_count": 0,
        "skipped_count": skipped,
        "testcase_count_by_classname": counts_by_classname,
        "testcase_count": len(testcase_inventory),
        "testcase_inventory": testcase_inventory,
        "testcase_scope_sha256": canonical_sha256(testcase_inventory),
        "output_file": output,
        "completed_at_utc": timestamp,
        "passed": True,
        "complete": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }, "focused_test_receipt_sha256")


def validate_focused_test_receipt_v1(
    value: object,
    *,
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    exact_output_raw: bytes,
) -> dict[str, object]:
    item = _mapping(value, label="focused-test receipt")
    _exact_keys(item, _FOCUSED_TEST_RECEIPT_FIELDS, label="focused-test receipt")
    _validate_self_hash(
        item, field="focused_test_receipt_sha256", label="focused-test receipt"
    )
    _false_authorities(item, label="focused-test receipt")
    output_file = file_binding(FOCUSED_TEST_OUTPUT_PATH, exact_output_raw)
    expected = build_focused_test_receipt_v1(
        implementation_commit_sha=implementation_commit_sha,
        implementation_measurements=implementation_measurements,
        output_file=output_file,
        exact_output_raw=exact_output_raw,
    )
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("focused-test receipt differs from exact passing replay")
    return expected


def _read_tracked_exact(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    commit: str,
    binding: Mapping[str, object],
    label: str,
) -> bytes:
    normalized = normalize_file_binding(binding, label=label)
    try:
        raw = repository.read_tracked(commit, str(normalized["relative_path"]))
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryV1Error(f"{label} tracked read failed") from exc
    if (
        type(raw) is not bytes
        or len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        _fail(f"{label} differs from its tracked binding")
    return raw


def require_git_ancestor_v1(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    ancestor_commit_sha: str,
    descendant_commit_sha: str,
    label: str,
) -> None:
    ancestor = _commit(ancestor_commit_sha, label=f"{label} ancestor")
    descendant = _commit(descendant_commit_sha, label=f"{label} descendant")
    try:
        repository._run(
            ["merge-base", "--is-ancestor", ancestor, descendant],
            label=f"{label} ancestry",
        )
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryV1Error(
            f"{label} Git ancestry differs"
        ) from exc


def tracked_file_introduction_commit_v1(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    current_head: str,
    relative_path: str,
) -> str:
    head = _commit(current_head, label="tracked-file current head")
    normalize_file_binding(
        {"relative_path": relative_path, "sha256": "0" * 64, "bytes": 1},
        label="tracked-file introduction path",
    )
    try:
        raw = repository._run(
            [
                "log",
                "--format=%H",
                "--diff-filter=A",
                "-n1",
                head,
                "--",
                relative_path,
            ],
            label="tracked-file introduction",
        )
        commit = raw.decode("ascii").strip()
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryV1Error(
            "tracked-file introduction commit lookup failed"
        ) from exc
    return _commit(commit, label="tracked-file introduction commit")


def require_commit_reachable_from_remote_v1(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    commit_sha: str,
) -> None:
    commit = _commit(commit_sha, label="durable remote commit")
    try:
        raw = repository._run(
            ["rev-parse", "--verify", DURABLE_REMOTE_REF],
            label="durable remote reference",
        )
        remote_commit = _commit(
            raw.decode("ascii").strip(), label="durable remote reference commit"
        )
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryV1Error(
            "remote reference census failed"
        ) from exc
    require_git_ancestor_v1(
        repository,
        ancestor_commit_sha=commit,
        descendant_commit_sha=remote_commit,
        label="attempt-to-durable-origin-main",
    )


def historical_evidence_manifest_v1() -> list[dict[str, object]]:
    return [
        {
            "role": row.role,
            "commit_sha": row.commit_sha,
            "file": {
                "relative_path": row.relative_path,
                "sha256": row.sha256,
                "bytes": row.bytes,
            },
            "schema_version": row.schema_version,
            "internal_field": row.internal_field,
            "internal_sha256": row.internal_sha256,
        }
        for row in HISTORICAL_EVIDENCE
    ]


def reopen_historical_evidence_v1(
    repository: adapter.SubprocessGitRepositoryV1,
) -> list[dict[str, object]]:
    manifest = historical_evidence_manifest_v1()
    for ordinal, (row, expected) in enumerate(zip(manifest, HISTORICAL_EVIDENCE, strict=True)):
        commit = _commit(row["commit_sha"], label=f"historical[{ordinal}] commit")
        raw = _read_tracked_exact(
            repository,
            commit=commit,
            binding=_mapping(row["file"], label=f"historical[{ordinal}] file"),
            label=f"historical evidence[{ordinal}]",
        )
        if expected.schema_version is not None:
            parsed = _parse_json(raw, label=f"historical evidence[{ordinal}]")
            if parsed.get("schema_version") != expected.schema_version:
                _fail(f"historical evidence[{ordinal}] schema differs")
            assert expected.internal_field is not None
            assert expected.internal_sha256 is not None
            if parsed.get(expected.internal_field) != expected.internal_sha256:
                _fail(f"historical evidence[{ordinal}] internal identity differs")
        if expected.role == "consumed_successor_attempt_2":
            parsed = _parse_json(raw, label="consumed successor attempt")
            if (
                parsed.get("projection_attempt_ordinal") != 2
                or parsed.get("maximum_projection_attempt_count") != 2
                or parsed.get("lifetime_projection_attempt_count_after_reservation") != 2
                or parsed.get("corrected_projection_rerun_license_consumed") is not True
                or parsed.get("third_projection_attempt_licensed") is not False
                or parsed.get("gcs_mutation_count") != 0
                or parsed.get("cloud_contact_performed") is not False
                or parsed.get("outcome_columns_read") != []
                or parsed.get("uses_realized_outcomes") is not False
            ):
                _fail("consumed successor attempt semantics differ")
    return manifest


def resolve_base_adapter_review_v1(
    repository: adapter.SubprocessGitRepositoryV1,
) -> adapter.AdapterReviewBindingV1:
    """Reopen historical evidence and recover only the immutable base review."""
    reopen_historical_evidence_v1(repository)
    original = HISTORICAL_EVIDENCE[0]
    original_raw = _read_tracked_exact(
        repository,
        commit=original.commit_sha,
        binding={
            "relative_path": original.relative_path,
            "sha256": original.sha256,
            "bytes": original.bytes,
        },
        label="original final lock for base adapter review",
    )
    original_lock = successor._validate_old_final_lock(
        successor._parse_json(original_raw, label="original final lock")
    )
    base_review = successor._adapter_review_from_old_final(original_lock)
    adapter._reopen_adapter_review_binding_v1(
        review=base_review, read_tracked=repository.read_tracked
    )
    return base_review


def measure_implementation_v1(
    repository: adapter.SubprocessGitRepositoryV1,
    commit_sha: str,
) -> list[dict[str, object]]:
    commit = _commit(commit_sha, label="implementation commit")
    rows = [
        file_binding(path, repository.read_tracked(commit, path))
        for path in IMPLEMENTATION_PATHS
    ]
    if [row["relative_path"] for row in rows] != list(IMPLEMENTATION_PATHS):
        _fail("implementation measurement order differs")
    return rows


def normalize_implementation_measurements_v1(value: object) -> list[dict[str, object]]:
    rows = [
        normalize_file_binding(row, label=f"implementation[{ordinal}]")
        for ordinal, row in enumerate(_sequence(value, label="implementation measurements"))
    ]
    if [row["relative_path"] for row in rows] != list(IMPLEMENTATION_PATHS):
        _fail("implementation measurement paths differ")
    by_path = {str(row["relative_path"]): row for row in rows}
    catalog_row = by_path[adapter.FIXED_CATALOG_MODULE_PATH]
    if (
        catalog_row["sha256"] != adapter.FIXED_CATALOG_MODULE_SHA256
        or catalog_row["bytes"] != adapter.FIXED_CATALOG_MODULE_BYTES
    ):
        _fail("fixed catalog derivation dependency differs")
    return rows


def reopen_implementation_v1(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    implementation_commit_sha: str,
    measurements: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    commit = _commit(implementation_commit_sha, label="reviewed implementation commit")
    normalized = normalize_implementation_measurements_v1(measurements)
    for ordinal, row in enumerate(normalized):
        _read_tracked_exact(
            repository,
            commit=commit,
            binding=row,
            label=f"reviewed implementation[{ordinal}]",
        )
    return normalized


def verify_current_implementation_v1(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    current_head: str,
    reviewed_measurements: Sequence[Mapping[str, object]],
) -> None:
    expected = normalize_implementation_measurements_v1(reviewed_measurements)
    current = measure_implementation_v1(repository, current_head)
    if current != expected:
        _fail("current clean implementation differs from reviewed bytes")


def verify_module_origins_v1(
    repository_root: Path,
    *,
    runner_file: Path,
) -> dict[str, str]:
    root = repository_root.resolve()
    expected = {
        "batch": root / adapter.FIXED_BATCH_MODULE_PATH,
        "catalog": root / adapter.FIXED_CATALOG_MODULE_PATH,
        "adapter": root / adapter.FIXED_ADAPTER_MODULE_PATH,
        "successor": root / SUCCESSOR_MODULE_PATH,
        "recovery": root / RECOVERY_MODULE_PATH,
        "runner": root / RUNNER_PATH,
    }
    observed = {
        "batch": Path(str(batch.__file__)).resolve(),
        "catalog": Path(str(catalog.__file__)).resolve(),
        "adapter": Path(str(adapter.__file__)).resolve(),
        "successor": Path(str(successor.__file__)).resolve(),
        "recovery": Path(__file__).resolve(),
        "runner": runner_file.resolve(),
    }
    differing = [role for role in expected if observed[role] != expected[role].resolve()]
    if differing:
        _fail(f"runtime module origins differ for {differing}")
    # Persist checkout-independent paths.  The equality check above is against
    # absolute resolved paths, so this is evidence of the check rather than an
    # environment-specific path leak.
    return {
        role: expected_path.relative_to(root).as_posix()
        for role, expected_path in expected.items()
    }


def expected_module_origins_v1() -> dict[str, str]:
    return {
        "batch": adapter.FIXED_BATCH_MODULE_PATH,
        "catalog": adapter.FIXED_CATALOG_MODULE_PATH,
        "adapter": adapter.FIXED_ADAPTER_MODULE_PATH,
        "successor": SUCCESSOR_MODULE_PATH,
        "recovery": RECOVERY_MODULE_PATH,
        "runner": RUNNER_PATH,
    }


_EMPTY_PREFIX_FIELDS: Final = frozenset({
    "schema_version",
    "checked_at_utc",
    "source_commit_sha",
    "implementation_measurements_sha256",
    "catalog_namespace",
    "terminal_receipt_uri",
    "terminal_receipt_present",
    "prefix_object_count",
    "prefix_object_metadata",
    "prefix_object_metadata_sha256",
    "generation_bound_metadata_listing_performed",
    "cloud_mutation_performed",
    "world_matrix_bodies_read",
    "world_schedule_bodies_read",
    "result_object_bodies_read",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_FALSE_AUTHORITY_FIELDS,
    "empty_prefix_evidence_sha256",
})


def normalize_prefix_inventory_v1(value: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(_sequence(value, label="prefix inventory")):
        row = _mapping(raw_row, label=f"prefix inventory[{ordinal}]")
        _exact_keys(
            row,
            frozenset({"uri", "generation", "bytes"}),
            label=f"prefix inventory[{ordinal}]",
        )
        uri = _string(row["uri"], label=f"prefix inventory[{ordinal}].uri")
        generation = _string(
            row["generation"], label=f"prefix inventory[{ordinal}].generation"
        )
        if (
            not uri.startswith(adapter.FIXED_CATALOG_NAMESPACE)
            or not generation.isdigit()
            or generation.startswith("0")
        ):
            _fail(f"prefix inventory[{ordinal}] identity differs")
        rows.append({
            "uri": uri,
            "generation": generation,
            "bytes": _exact_int(
                row["bytes"], label=f"prefix inventory[{ordinal}].bytes", minimum=1
            ),
        })
    ordered = sorted(rows, key=lambda row: str(row["uri"]))
    if rows != ordered or len({str(row["uri"]) for row in rows}) != len(rows):
        _fail("prefix inventory order/uniqueness differs")
    return rows


def prefix_inventory_from_identities_v1(
    identities: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows = []
    for ordinal, raw_identity in enumerate(identities):
        identity = adapter._normalized_identity(
            raw_identity, label=f"prefix expected identity[{ordinal}]"
        )
        rows.append({
            "uri": identity["uri"],
            "generation": identity["generation"],
            "bytes": identity["bytes"],
        })
    return normalize_prefix_inventory_v1(
        sorted(rows, key=lambda row: str(row["uri"]))
    )


def build_empty_prefix_evidence_v1(
    *,
    checked_at_utc: str,
    source_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    observed_prefix_inventory: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    timestamp = _string(checked_at_utc, label="empty-prefix checked_at_utc")
    commit = _commit(source_commit_sha, label="empty-prefix source commit")
    measurements = normalize_implementation_measurements_v1(
        implementation_measurements
    )
    inventory = normalize_prefix_inventory_v1(observed_prefix_inventory)
    if _UTC.fullmatch(timestamp) is None:
        _fail("empty-prefix timestamp differs")
    if inventory:
        _fail("empty-prefix census found existing catalog objects")
    return _self_hash({
        "schema_version": EMPTY_PREFIX_EVIDENCE_SCHEMA,
        "checked_at_utc": timestamp,
        "source_commit_sha": commit,
        "implementation_measurements_sha256": canonical_sha256(measurements),
        "catalog_namespace": adapter.FIXED_CATALOG_NAMESPACE,
        "terminal_receipt_uri": (
            f"{adapter.FIXED_CATALOG_NAMESPACE}{adapter.REPLAY_RECEIPT_FILENAME}"
        ),
        "terminal_receipt_present": False,
        "prefix_object_count": 0,
        "prefix_object_metadata": inventory,
        "prefix_object_metadata_sha256": canonical_sha256(inventory),
        "generation_bound_metadata_listing_performed": True,
        "cloud_mutation_performed": False,
        "world_matrix_bodies_read": False,
        "world_schedule_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }, "empty_prefix_evidence_sha256")


def validate_empty_prefix_evidence_v1(
    value: object,
    *,
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    item = _mapping(value, label="empty-prefix evidence")
    _exact_keys(item, _EMPTY_PREFIX_FIELDS, label="empty-prefix evidence")
    _validate_self_hash(
        item, field="empty_prefix_evidence_sha256", label="empty-prefix evidence"
    )
    _false_authorities(item, label="empty-prefix evidence")
    timestamp = _string(item["checked_at_utc"], label="empty-prefix checked_at_utc")
    if _UTC.fullmatch(timestamp) is None:
        _fail("empty-prefix timestamp differs")
    commit = _commit(item["source_commit_sha"], label="empty-prefix source commit")
    if commit != _commit(
        implementation_commit_sha, label="expected empty-prefix implementation commit"
    ):
        _fail("empty-prefix implementation commit differs")
    expected_measurements_sha256 = canonical_sha256(
        normalize_implementation_measurements_v1(implementation_measurements)
    )
    if item["implementation_measurements_sha256"] != expected_measurements_sha256:
        _fail("empty-prefix implementation measurements differ")
    expected = build_empty_prefix_evidence_v1(
        checked_at_utc=timestamp,
        source_commit_sha=commit,
        implementation_measurements=implementation_measurements,
        observed_prefix_inventory=[],
    )
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("empty-prefix evidence differs from zero-object read-only census")
    return expected


def source_read_allowlist_v1(
    *,
    pins: adapter.ReplayPinsV1,
    task_ordinals: Sequence[int],
    exact_panel_raw: bytes,
) -> list[dict[str, object]]:
    ordinals = tuple(task_ordinals)
    if (
        not ordinals
        or tuple(sorted(set(ordinals))) != ordinals
        or any(ordinal < 0 or ordinal >= catalog.TASK_COUNT for ordinal in ordinals)
    ):
        _fail("source read-allowlist task ordinals differ")
    lane_ordinals = sorted({
        int(catalog.expected_lane_for_source_task(ordinal)["lane_ordinal"])
        for ordinal in ordinals
    })
    panel_identity = adapter._normalized_identity(
        pins.panel_identity, label="planned source panel identity"
    )
    if (
        type(exact_panel_raw) is not bytes
        or len(exact_panel_raw) != panel_identity["bytes"]
        or sha256(exact_panel_raw).hexdigest() != panel_identity["sha256"]
    ):
        _fail("planned source panel body differs from its fixed identity")
    panel = _parse_json(exact_panel_raw, label="planned source panel")
    normalized_panel, _, _ = adapter._validate_panel(
        panel, normalized_pins=adapter._normalize_pins(pins)
    )
    members = _sequence(
        normalized_panel["accepted_slates"], label="planned source panel members"
    )
    identities = [
        pins.panel_identity,
        *(pins.lane_terminal_identities[ordinal] for ordinal in lane_ordinals),
        *(pins.lane_completion_identities[ordinal] for ordinal in lane_ordinals),
        pins.later_source_identity,
        pins.source_completion_identity,
        *(
            identity
            for ordinal in ordinals
            for identity in (
                _mapping(
                    members[ordinal], label=f"planned panel member[{ordinal}]"
                )["task_acceptance_identity"],
                _mapping(
                    members[ordinal], label=f"planned panel member[{ordinal}]"
                )["carrier_identity"],
            )
        ),
    ]
    return [
        adapter._normalized_identity(identity, label=f"source read root[{ordinal}]")
        for ordinal, identity in enumerate(identities)
    ]


def planned_inner_output_uris_v1() -> tuple[str, ...]:
    """Closed, deterministic 110-object output surface in publication order."""
    uris: list[str] = []
    for source_ordinal in range(catalog.TASK_COUNT):
        slate = catalog.expected_slate_for_source_task(source_ordinal)
        children = catalog._catalog_child_uris(
            adapter.FIXED_CATALOG_NAMESPACE,
            source_task_ordinal=source_ordinal,
            slate_id=str(slate["slate_id"]),
        )
        uris.extend((children["derivation"], children["catalog"]))
    uris.extend((
        f"{adapter.FIXED_CATALOG_NAMESPACE}catalog-release.json",
        f"{adapter.FIXED_CATALOG_NAMESPACE}{adapter.REPLAY_RECEIPT_FILENAME}",
    ))
    if len(uris) != EXPECTED_INNER_OBJECT_COUNT or len(set(uris)) != len(uris):
        _fail("fixed inner output URI plan differs")
    return tuple(uris)


class TransportAuditV1:
    """Exact allowlisted reads plus read/write accounting."""

    def __init__(
        self,
        base: adapter.GenerationTransportV1,
        *,
        mode: str,
        allowed_read_identities: Sequence[Mapping[str, object]],
        panel_task_ordinals: Sequence[int] = (),
        planned_output_uris: Sequence[str] = (),
    ) -> None:
        if mode not in {"read_only", "publish"}:
            _fail("transport audit mode differs")
        self.base = base
        self.mode = mode
        self.allowed_read_identities: dict[tuple[str, str], dict[str, object]] = {}
        for ordinal, raw_identity in enumerate(allowed_read_identities):
            self._allow_identity(raw_identity, label=f"initial read allowlist[{ordinal}]")
        self.panel_task_ordinals = tuple(panel_task_ordinals)
        if self.panel_task_ordinals and (
            tuple(sorted(set(self.panel_task_ordinals))) != self.panel_task_ordinals
            or any(
                ordinal < 0 or ordinal >= catalog.TASK_COUNT
                for ordinal in self.panel_task_ordinals
            )
        ):
            _fail("transport panel task ordinals differ")
        self.reload_identities: list[dict[str, object]] = []
        self.download_identities: list[dict[str, object]] = []
        self.denied_read_attempts: list[dict[str, str]] = []
        self.current_resolution_uris: list[str] = []
        self.current_resolution_identities: list[dict[str, object]] = []
        self.create_attempt_uris: list[str] = []
        self.created_uris: set[str] = set()
        self.reopened_uris: set[str] = set()
        self.pending_created_uris: set[str] = set()
        self.pending_reopened_uris: set[str] = set()
        self.planned_output_uris = tuple(planned_output_uris)
        if mode == "publish":
            if self.planned_output_uris != planned_inner_output_uris_v1():
                _fail("publish transport requires the exact 110-inner URI plan")
        elif self.planned_output_uris:
            _fail("read-only transport cannot carry an output URI plan")
        self.outer_uri_active = False
        self.expected_create_sha256_by_uri: dict[str, str] = {}
        self.expected_create_bytes_by_uri: dict[str, int] = {}
        self.ambiguous_create_recovered_uris: list[str] = []
        self.unknown_not_absent_uris: list[str] = []

    def activate_outer_after_pre_root_v1(self) -> None:
        if self.mode != "publish" or self.outer_uri_active:
            _fail("outer output activation state differs")
        if set(self.created_uris) | set(self.reopened_uris) != set(self.planned_output_uris):
            _fail("outer output cannot activate before all 110 inner URIs are exact-opened")
        self.outer_uri_active = True

    def _require_planned_output_uri(self, uri: str) -> None:
        if uri in self.planned_output_uris:
            return
        if uri == OUTER_ATTESTATION_URI and self.outer_uri_active:
            return
        _fail("output URI is outside the active exact publication plan")

    def bind_planned_read_identities_v1(
        self, identities: Sequence[Mapping[str, object]]
    ) -> None:
        """One-way bind an exact plan after the fixed panel bootstrap read."""
        panel = adapter._normalized_identity(
            adapter.FIXED_PINS.panel_identity, label="fixed bootstrap panel"
        )
        if (
            self.reload_identities != [panel]
            or self.download_identities != [panel]
            or set(self.allowed_read_identities) != {
                (str(panel["uri"]), str(panel["generation"]))
            }
        ):
            _fail("source read plan was not bound immediately after panel bootstrap")
        for ordinal, identity in enumerate(identities):
            self._allow_identity(identity, label=f"bound source read plan[{ordinal}]")

    def bind_attested_output_identities_v1(
        self, identities: Sequence[Mapping[str, object]]
    ) -> None:
        """Bind only exact catalog identities from an already validated outer root."""
        if not any(
            identity.get("uri") == OUTER_ATTESTATION_URI
            for identity in self.download_identities
        ):
            _fail("outer root must be exact-read before its manifest is bound")
        normalized = [
            adapter._normalized_identity(
                value, label=f"attested output plan[{ordinal}]"
            )
            for ordinal, value in enumerate(identities)
        ]
        if tuple(str(identity["uri"]) for identity in normalized) != planned_inner_output_uris_v1():
            _fail("outer manifest URI tuple differs from the fixed inner plan")
        for ordinal, identity in enumerate(normalized):
            if not str(identity["uri"]).startswith(adapter.FIXED_CATALOG_NAMESPACE):
                _fail("attested output plan escapes the fixed catalog namespace")
            self._allow_identity(identity, label=f"attested output plan[{ordinal}]")

    def bind_expected_create_v1(self, uri: str, raw: bytes) -> None:
        self._require_planned_output_uri(uri)
        if type(raw) is not bytes or not raw:
            _fail("planned output body binding requires nonempty exact bytes")
        body_sha = sha256(raw).hexdigest()
        prior_sha = self.expected_create_sha256_by_uri.get(uri)
        prior_bytes = self.expected_create_bytes_by_uri.get(uri)
        if (
            prior_sha is not None
            and (prior_sha != body_sha or prior_bytes != len(raw))
        ):
            _fail("planned output URI was rebound to different deterministic bytes")
        self.expected_create_sha256_by_uri[uri] = body_sha
        self.expected_create_bytes_by_uri[uri] = len(raw)

    def _require_expected_create_binding(self, uri: str) -> None:
        if (
            uri not in self.expected_create_sha256_by_uri
            or uri not in self.expected_create_bytes_by_uri
        ):
            _fail("output URI/body was not prebound before storage contact")

    def _allow_identity(self, value: object, *, label: str) -> dict[str, object]:
        identity = adapter._normalized_identity(value, label=label)
        key = (str(identity["uri"]), str(identity["generation"]))
        prior = self.allowed_read_identities.get(key)
        if prior is not None and prior != identity:
            _fail("read allowlist identity collision differs")
        self.allowed_read_identities[key] = identity
        return identity

    def _required_allowed(self, uri: str, generation: str) -> dict[str, object]:
        key = (uri, generation)
        identity = self.allowed_read_identities.get(key)
        if identity is None:
            self.denied_read_attempts.append({"uri": uri, "generation": generation})
            _fail("generation read is outside the exact runtime allowlist")
        return identity

    def reload_generation(self, uri: str, generation: str) -> Mapping[str, object]:
        expected = self._required_allowed(uri, generation)
        observed = adapter._normalized_identity(
            self.base.reload_generation(uri, generation),
            label="allowlisted generation reload",
        )
        if observed != expected:
            _fail("allowlisted generation reload identity differs")
        self.reload_identities.append(observed)
        return observed

    def download_generation(self, uri: str, generation: str) -> bytes:
        expected = self._required_allowed(uri, generation)
        raw = self.base.download_generation(uri, generation)
        if (
            type(raw) is not bytes
            or len(raw) != expected["bytes"]
            or sha256(raw).hexdigest() != expected["sha256"]
        ):
            _fail("allowlisted generation body differs from its exact identity")
        self.download_identities.append(expected)
        if (
            uri in self.pending_created_uris | self.pending_reopened_uris
            and (
                self.expected_create_sha256_by_uri.get(uri)
                != sha256(raw).hexdigest()
                or self.expected_create_bytes_by_uri.get(uri) != len(raw)
            )
        ):
            _fail("resolved output body differs from its prebound expectation")
        if uri in self.pending_created_uris:
            self.pending_created_uris.remove(uri)
            self.created_uris.add(uri)
        if uri in self.pending_reopened_uris:
            self.pending_reopened_uris.remove(uri)
            self.reopened_uris.add(uri)
        return raw

    def resolve_current(self, uri: str) -> Mapping[str, object]:
        if self.mode != "publish":
            _fail("read-only transport forbids current-generation resolution")
        result = self._resolve_planned_current_accounted(uri)
        self._allow_identity(result, label="resumed output read identity")
        self.pending_reopened_uris.add(uri)
        return result

    def _resolve_planned_current_accounted(self, uri: str) -> dict[str, object]:
        self._require_planned_output_uri(uri)
        self._require_expected_create_binding(uri)
        self.current_resolution_uris.append(uri)
        result = adapter._normalized_identity(
            self.base.resolve_current(uri), label="resolved current output identity"
        )
        if result["uri"] != uri:
            _fail("resolved current output URI differs")
        self.current_resolution_identities.append(result)
        return result

    def create_if_absent(
        self, uri: str, raw: bytes, precondition: int,
    ) -> Mapping[str, object]:
        if self.mode != "publish":
            _fail("read-only transport forbids object creation")
        if (
            type(raw) is not bytes
            or not raw
            or precondition != 0
        ):
            _fail("output create request differs before transport contact")
        self._require_planned_output_uri(uri)
        self._require_expected_create_binding(uri)
        body_sha = sha256(raw).hexdigest()
        if (
            self.expected_create_sha256_by_uri[uri] != body_sha
            or self.expected_create_bytes_by_uri[uri] != len(raw)
        ):
            _fail("planned output bytes differ from their prebound expectation")
        self.create_attempt_uris.append(uri)
        try:
            created = self.base.create_if_absent(uri, raw, precondition)
        except adapter.ObjectAlreadyExistsV1Error:
            raise
        except Exception:
            try:
                created = self._resolve_planned_current_accounted(uri)
            except Exception:
                self.unknown_not_absent_uris.append(uri)
                _fail("create outcome is unknown-not-absent")
            resolved = adapter._normalized_identity(
                created, label="ambiguous-create resolved identity"
            )
            if (
                resolved["uri"] != uri
                or resolved["sha256"] != body_sha
                or resolved["bytes"] != len(raw)
            ):
                _fail("ambiguous-create collision identity differs")
            self._allow_identity(resolved, label="ambiguous-create read identity")
            self.pending_reopened_uris.add(uri)
            self.ambiguous_create_recovered_uris.append(uri)
            return resolved
        result = adapter._normalized_identity(created, label="created output identity")
        if (
            result["uri"] != uri
            or result["sha256"] != sha256(raw).hexdigest()
            or result["bytes"] != len(raw)
        ):
            _fail("created output identity differs")
        self._allow_identity(result, label="created output read identity")
        self.pending_created_uris.add(uri)
        return result

    def transport(self) -> adapter.GenerationTransportV1:
        return adapter.GenerationTransportV1(
            reload_generation=self.reload_generation,
            download_generation=self.download_generation,
            resolve_current=self.resolve_current,
            create_if_absent=self.create_if_absent,
            bind_expected_create=self.bind_expected_create_v1,
        )

    def snapshot_v1(self) -> dict[str, object]:
        namespace = adapter.FIXED_CATALOG_NAMESPACE
        created = sorted(uri for uri in self.created_uris if uri.startswith(namespace))
        reopened = sorted(
            uri for uri in self.reopened_uris
            if uri.startswith(namespace) and uri not in self.created_uris
        )
        touched = sorted(set(created) | set(reopened))
        count = len(touched)
        if count == 0:
            state = "no_output_object_contact"
        elif count < EXPECTED_INNER_OBJECT_COUNT:
            state = "partial_inner_namespace"
        elif count == EXPECTED_INNER_OBJECT_COUNT:
            state = "expected_inner_uris_touched_outer_unseen"
        elif count == EXPECTED_TOTAL_OBJECT_COUNT:
            state = "expected_uri_surface_touched_prefix_unverified"
        else:
            state = "unexpected_output_surface"
        return {
            "mode": self.mode,
            "generation_reload_count": len(self.reload_identities),
            "generation_download_count": len(self.download_identities),
            "generation_reload_identities": self.reload_identities,
            "generation_reload_manifest_sha256": canonical_sha256(
                self.reload_identities
            ),
            "generation_download_identities": self.download_identities,
            "generation_download_manifest_sha256": canonical_sha256(
                self.download_identities
            ),
            "allowed_read_identities": sorted(
                self.allowed_read_identities.values(),
                key=lambda identity: (
                    str(identity["uri"]), str(identity["generation"])
                ),
            ),
            "denied_read_attempts": self.denied_read_attempts,
            "current_resolution_count": len(self.current_resolution_uris),
            "current_resolution_uris": list(self.current_resolution_uris),
            "current_resolution_identities": self.current_resolution_identities,
            "current_resolution_identity_manifest_sha256": canonical_sha256(
                self.current_resolution_identities
            ),
            "create_attempt_count": len(self.create_attempt_uris),
            "created_count": len(created),
            "reopened_count": len(reopened),
            "touched_output_object_count": count,
            "created_uri_manifest_sha256": canonical_sha256(created),
            "reopened_uri_manifest_sha256": canonical_sha256(reopened),
            "touched_uri_manifest_sha256": canonical_sha256(touched),
            "partial_state": state,
            "write_capability_enabled": self.mode == "publish",
            "planned_output_uris": list(self.planned_output_uris),
            "outer_uri_active": self.outer_uri_active,
            "expected_create_sha256_by_uri": dict(sorted(self.expected_create_sha256_by_uri.items())),
            "expected_create_bytes_by_uri": dict(sorted(self.expected_create_bytes_by_uri.items())),
            "ambiguous_create_recovered_uris": self.ambiguous_create_recovered_uris,
            "unknown_not_absent_uris": self.unknown_not_absent_uris,
        }


_TRANSPORT_AUDIT_FIELDS: Final = frozenset({
    "mode",
    "generation_reload_count",
    "generation_download_count",
    "generation_reload_identities",
    "generation_reload_manifest_sha256",
    "generation_download_identities",
    "generation_download_manifest_sha256",
    "allowed_read_identities",
    "denied_read_attempts",
    "current_resolution_count",
    "current_resolution_uris",
    "current_resolution_identities",
    "current_resolution_identity_manifest_sha256",
    "create_attempt_count",
    "created_count",
    "reopened_count",
    "touched_output_object_count",
    "created_uri_manifest_sha256",
    "reopened_uri_manifest_sha256",
    "touched_uri_manifest_sha256",
    "partial_state",
    "write_capability_enabled",
    "planned_output_uris",
    "outer_uri_active",
    "expected_create_sha256_by_uri",
    "expected_create_bytes_by_uri",
    "ambiguous_create_recovered_uris",
    "unknown_not_absent_uris",
})


def validate_read_only_smoke_transport_audit_v1(value: object) -> dict[str, object]:
    audit = _mapping(value, label="smoke transport audit")
    _exact_keys(audit, _TRANSPORT_AUDIT_FIELDS, label="smoke transport audit")
    reload_identities = [
        adapter._normalized_identity(row, label=f"smoke reload identity[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(audit["generation_reload_identities"], label="smoke reload identities")
        )
    ]
    download_identities = [
        adapter._normalized_identity(row, label=f"smoke download identity[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(audit["generation_download_identities"], label="smoke download identities")
        )
    ]
    allowed_identities = [
        adapter._normalized_identity(row, label=f"smoke allowed identity[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(audit["allowed_read_identities"], label="smoke allowed identities")
        )
    ]
    reload_count = len(reload_identities)
    download_count = len(download_identities)
    empty_manifest_sha256 = canonical_sha256([])
    expected = {
        "mode": "read_only",
        "generation_reload_count": reload_count,
        "generation_download_count": download_count,
        "generation_reload_identities": reload_identities,
        "generation_reload_manifest_sha256": canonical_sha256(reload_identities),
        "generation_download_identities": download_identities,
        "generation_download_manifest_sha256": canonical_sha256(download_identities),
        "allowed_read_identities": allowed_identities,
        "denied_read_attempts": [],
        "current_resolution_count": 0,
        "current_resolution_uris": [],
        "current_resolution_identities": [],
        "current_resolution_identity_manifest_sha256": empty_manifest_sha256,
        "create_attempt_count": 0,
        "created_count": 0,
        "reopened_count": 0,
        "touched_output_object_count": 0,
        "created_uri_manifest_sha256": empty_manifest_sha256,
        "reopened_uri_manifest_sha256": empty_manifest_sha256,
        "touched_uri_manifest_sha256": empty_manifest_sha256,
        "partial_state": "no_output_object_contact",
        "write_capability_enabled": False,
        "planned_output_uris": [],
        "outer_uri_active": False,
        "expected_create_sha256_by_uri": {},
        "expected_create_bytes_by_uri": {},
        "ambiguous_create_recovered_uris": [],
        "unknown_not_absent_uris": [],
    }
    if canonical_json_bytes(audit) != canonical_json_bytes(expected):
        _fail("smoke transport was not capability-read-only")
    return expected


_SMOKE_FIELDS: Final = frozenset({
    "schema_version",
    "mode",
    "source_commit_sha",
    "implementation_measurements",
    "implementation_measurements_sha256",
    "module_origins",
    "catalog_namespace",
    "source_task_ordinals",
    "task_acceptance_body_count",
    "carrier_body_count",
    "structural_player_count",
    "pin_set_sha256",
    "generation_pinned_input_identities",
    "generation_pinned_input_manifest_sha256",
    "transport_audit",
    "read_only_transport_enforced",
    "cloud_mutation_performed",
    "world_matrix_bodies_read",
    "world_schedule_bodies_read",
    "result_object_bodies_read",
    "outcome_columns_read",
    "uses_realized_outcomes",
    "full_projection_publication_licensed",
    *_FALSE_AUTHORITY_FIELDS,
    "complete",
    "smoke_evidence_sha256",
})


def build_smoke_evidence_v1(
    *,
    source_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    module_origins: Mapping[str, object],
    inputs: adapter.ReplayedProjectionInputsV1,
    transport_audit: Mapping[str, object],
) -> dict[str, object]:
    commit = _commit(source_commit_sha, label="smoke source commit")
    measurements = normalize_implementation_measurements_v1(implementation_measurements)
    origins = _mapping(module_origins, label="smoke module origins")
    if origins != expected_module_origins_v1():
        _fail("smoke module origins differ")
    if (
        inputs.source_task_ordinals != (0,)
        or inputs.task_acceptance_body_count != 1
        or inputs.carrier_body_count != 1
        or len(inputs.structural_players) != 1
        or not inputs.structural_players[0]
        or len(inputs.task_evidence_bindings) != 1
    ):
        _fail("smoke task-0 replay coverage differs")
    evidence = _mapping(inputs.task_evidence_bindings[0], label="smoke task evidence")
    identities = [
        adapter._normalized_identity(
            inputs.tracked_root_binding["panel_object_identity"], label="smoke panel"
        ),
        adapter._normalized_identity(inputs.lane_terminal_identities[0], label="smoke lane terminal"),
        adapter._normalized_identity(inputs.lane_completion_identities[0], label="smoke lane completion"),
        adapter._normalized_identity(inputs.later_source_identity, label="smoke later source"),
        adapter._normalized_identity(inputs.source_completion_identity, label="smoke source completion"),
        adapter._normalized_identity(evidence["task_acceptance_identity"], label="smoke acceptance"),
        adapter._normalized_identity(evidence["carrier_identity"], label="smoke carrier"),
    ]
    if any(
        str(identity["uri"]).startswith(adapter.FIXED_CATALOG_NAMESPACE)
        for identity in identities
    ):
        _fail("smoke input identity overlaps the recovery output namespace")
    pin_set_sha256 = _sha(inputs.pin_set_sha256, label="smoke pin-set SHA")
    audit = validate_read_only_smoke_transport_audit_v1(transport_audit)
    read_identities = [identities[0], *identities]
    expected_allowed = sorted(
        identities,
        key=lambda identity: (str(identity["uri"]), str(identity["generation"])),
    )
    if (
        audit["generation_reload_identities"] != read_identities
        or audit["generation_download_identities"] != read_identities
        or audit["allowed_read_identities"] != expected_allowed
        or audit["denied_read_attempts"] != []
    ):
        _fail("smoke exact read allowlist/manifest differs")
    return _self_hash({
        "schema_version": SMOKE_EVIDENCE_SCHEMA,
        "mode": "read-only-real-task0-smoke",
        "source_commit_sha": commit,
        "implementation_measurements": measurements,
        "implementation_measurements_sha256": canonical_sha256(measurements),
        "module_origins": origins,
        "catalog_namespace": adapter.FIXED_CATALOG_NAMESPACE,
        "source_task_ordinals": [0],
        "task_acceptance_body_count": 1,
        "carrier_body_count": 1,
        "structural_player_count": len(inputs.structural_players[0]),
        "pin_set_sha256": pin_set_sha256,
        "generation_pinned_input_identities": identities,
        "generation_pinned_input_manifest_sha256": canonical_sha256(identities),
        "transport_audit": audit,
        "read_only_transport_enforced": True,
        "cloud_mutation_performed": False,
        "world_matrix_bodies_read": False,
        "world_schedule_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "full_projection_publication_licensed": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        "complete": True,
    }, "smoke_evidence_sha256")


def validate_smoke_evidence_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="recovery smoke evidence")
    _exact_keys(item, _SMOKE_FIELDS, label="recovery smoke evidence")
    retained = _validate_self_hash(item, field="smoke_evidence_sha256", label="recovery smoke evidence")
    _false_authorities(item, label="recovery smoke evidence")
    measurements = normalize_implementation_measurements_v1(item["implementation_measurements"])
    origins = _mapping(item["module_origins"], label="smoke module origins")
    source_commit = _commit(item["source_commit_sha"], label="smoke source commit")
    pin_set_sha256 = _sha(item["pin_set_sha256"], label="smoke pin-set SHA")
    identities = [
        adapter._normalized_identity(row, label=f"smoke input identity[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(item["generation_pinned_input_identities"], label="smoke identities")
        )
    ]
    audit = validate_read_only_smoke_transport_audit_v1(item["transport_audit"])
    if any(
        str(identity["uri"]).startswith(adapter.FIXED_CATALOG_NAMESPACE)
        for identity in identities
    ):
        _fail("smoke input identity overlaps the recovery output namespace")
    expected_allowed = sorted(
        identities,
        key=lambda identity: (str(identity["uri"]), str(identity["generation"])),
    )
    read_identities = [identities[0], *identities]
    if (
        retained != item["smoke_evidence_sha256"]
        or item["schema_version"] != SMOKE_EVIDENCE_SCHEMA
        or item["mode"] != "read-only-real-task0-smoke"
        or item["implementation_measurements_sha256"] != canonical_sha256(measurements)
        or origins != expected_module_origins_v1()
        or item["catalog_namespace"] != adapter.FIXED_CATALOG_NAMESPACE
        or item["source_task_ordinals"] != [0]
        or item["task_acceptance_body_count"] != 1
        or item["carrier_body_count"] != 1
        or type(item["structural_player_count"]) is not int
        or item["structural_player_count"] < 1
        or len(identities) != 7
        or item["generation_pinned_input_manifest_sha256"] != canonical_sha256(identities)
        or audit["generation_reload_identities"] != read_identities
        or audit["generation_download_identities"] != read_identities
        or audit["allowed_read_identities"] != expected_allowed
        or audit["denied_read_attempts"] != []
        or item["read_only_transport_enforced"] is not True
        or item["cloud_mutation_performed"] is not False
        or item["world_matrix_bodies_read"] is not False
        or item["world_schedule_bodies_read"] is not False
        or item["result_object_bodies_read"] is not False
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
        or item["full_projection_publication_licensed"] is not False
        or item["complete"] is not True
    ):
        _fail("recovery smoke evidence semantics differ")
    normalized = dict(item)
    normalized["source_commit_sha"] = source_commit
    normalized["implementation_measurements"] = measurements
    normalized["module_origins"] = origins
    normalized["pin_set_sha256"] = pin_set_sha256
    normalized["generation_pinned_input_identities"] = identities
    normalized["transport_audit"] = audit
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("recovery smoke evidence canonical replay differs")
    return normalized


def _review_false_fields() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def build_review_lock_v1(
    *,
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    smoke_evidence_file: Mapping[str, object],
    smoke_evidence: Mapping[str, object],
    empty_prefix_evidence_file: Mapping[str, object],
    empty_prefix_evidence: Mapping[str, object],
    focused_test_receipt_file: Mapping[str, object],
    focused_test_receipt: Mapping[str, object],
    focused_test_output_raw: bytes,
    independent_review_disposition: str,
    p0_open_count: int,
    p1_open_count: int,
    p2_open_count: int,
) -> dict[str, object]:
    commit = _commit(implementation_commit_sha, label="review implementation commit")
    measurements = normalize_implementation_measurements_v1(implementation_measurements)
    smoke_file = normalize_file_binding(smoke_evidence_file, label="review smoke file")
    empty_file = normalize_file_binding(empty_prefix_evidence_file, label="review empty-prefix file")
    focused_receipt_file = normalize_file_binding(
        focused_test_receipt_file, label="review focused-test receipt file"
    )
    focused = validate_focused_test_receipt_v1(
        focused_test_receipt,
        implementation_commit_sha=commit,
        implementation_measurements=measurements,
        exact_output_raw=focused_test_output_raw,
    )
    focused_output_file = file_binding(
        FOCUSED_TEST_OUTPUT_PATH, focused_test_output_raw
    )
    smoke = validate_smoke_evidence_v1(smoke_evidence)
    empty = validate_empty_prefix_evidence_v1(
        empty_prefix_evidence,
        implementation_commit_sha=commit,
        implementation_measurements=measurements,
    )
    disposition = _string(independent_review_disposition, label="review disposition")
    counts = (p0_open_count, p1_open_count, p2_open_count)
    if (
        smoke_file["relative_path"] != SMOKE_EVIDENCE_PATH
        or empty_file["relative_path"] != EMPTY_PREFIX_EVIDENCE_PATH
        or focused_receipt_file["relative_path"] != FOCUSED_TEST_RECEIPT_PATH
        or smoke["source_commit_sha"] != commit
        or smoke["implementation_measurements"] != measurements
        or disposition != "approve"
        or counts != (0, 0, 0)
    ):
        _fail("recovery review prerequisites differ")
    body = {
        "schema_version": REVIEW_LOCK_SCHEMA,
        "implementation_commit_sha": commit,
        "implementation_measurements": measurements,
        "implementation_measurements_sha256": canonical_sha256(measurements),
        "historical_evidence": historical_evidence_manifest_v1(),
        "historical_evidence_manifest_sha256": canonical_sha256(historical_evidence_manifest_v1()),
        "smoke_evidence_file": smoke_file,
        "smoke_evidence_sha256": smoke["smoke_evidence_sha256"],
        "empty_prefix_evidence_file": empty_file,
        "empty_prefix_evidence_sha256": empty["empty_prefix_evidence_sha256"],
        "focused_test_receipt_file": focused_receipt_file,
        "focused_test_receipt_sha256": focused["focused_test_receipt_sha256"],
        "focused_test_output_file": focused_output_file,
        "focused_test_command": list(FOCUSED_TEST_COMMAND),
        "focused_test_pass_count": focused["pass_count"],
        "focused_test_passed": True,
        "independent_review_disposition": "approve",
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "real_task0_smoke_passed": True,
        "smoke_was_capability_read_only": True,
        "prior_projection_attempt_count": 2,
        "prior_projection_mutation_count": 0,
        "recovery_attempt_ordinal": RECOVERY_ATTEMPT_ORDINAL,
        "maximum_lifetime_projection_attempts": MAXIMUM_LIFETIME_PROJECTION_ATTEMPTS,
        "smoke_command": list(SMOKE_COMMAND),
        "attempt_marker_command": list(ATTEMPT_MARKER_COMMAND),
        "publish_command": list(PUBLISH_COMMAND),
        "reopen_command": list(REOPEN_COMMAND),
        "catalog_namespace": adapter.FIXED_CATALOG_NAMESPACE,
        "expected_inner_object_count": EXPECTED_INNER_OBJECT_COUNT,
        "expected_total_object_count": EXPECTED_TOTAL_OBJECT_COUNT,
        "outer_attestation_uri": OUTER_ATTESTATION_URI,
        "review_lock_alone_licenses_publication": False,
        "final_lock_required_before_cloud_client": True,
        "gcs_mutation_licensed": False,
        "world_matrix_bodies_read": False,
        "world_schedule_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **_review_false_fields(),
    }
    return _self_hash(body, "recovery_review_lock_sha256")


def validate_review_lock_v1(
    value: object,
    *,
    smoke_evidence: Mapping[str, object],
    empty_prefix_evidence: Mapping[str, object],
    focused_test_receipt: Mapping[str, object],
    focused_test_output_raw: bytes,
) -> dict[str, object]:
    item = _mapping(value, label="recovery review lock")
    _validate_self_hash(item, field="recovery_review_lock_sha256", label="recovery review lock")
    _false_authorities(item, label="recovery review lock")
    expected = build_review_lock_v1(
        implementation_commit_sha=str(item.get("implementation_commit_sha")),
        implementation_measurements=_sequence(item.get("implementation_measurements"), label="review measurements"),
        smoke_evidence_file=_mapping(item.get("smoke_evidence_file"), label="review smoke file"),
        smoke_evidence=smoke_evidence,
        empty_prefix_evidence_file=_mapping(item.get("empty_prefix_evidence_file"), label="review empty file"),
        empty_prefix_evidence=empty_prefix_evidence,
        focused_test_receipt_file=_mapping(
            item.get("focused_test_receipt_file"),
            label="review focused receipt file",
        ),
        focused_test_receipt=focused_test_receipt,
        focused_test_output_raw=focused_test_output_raw,
        independent_review_disposition=str(item.get("independent_review_disposition")),
        p0_open_count=item.get("p0_open_count"),
        p1_open_count=item.get("p1_open_count"),
        p2_open_count=item.get("p2_open_count"),
    )
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("recovery review lock differs from deterministic replay")
    return expected


def build_final_lock_v1(
    *,
    review_lock_commit_sha: str,
    review_lock_file: Mapping[str, object],
    review_lock: Mapping[str, object],
    publication_approved: bool,
) -> dict[str, object]:
    review_commit = _commit(review_lock_commit_sha, label="review-lock commit")
    review_file = normalize_file_binding(review_lock_file, label="final review-lock file")
    review = _mapping(review_lock, label="validated review lock")
    review_internal = _sha(
        review.get("recovery_review_lock_sha256"), label="review-lock internal SHA"
    )
    if review_file["relative_path"] != REVIEW_LOCK_PATH or publication_approved is not True:
        _fail("final-lock publication approval differs")
    body = {
        "schema_version": FINAL_LOCK_SCHEMA,
        "implementation_commit_sha": review["implementation_commit_sha"],
        "implementation_measurements": review["implementation_measurements"],
        "implementation_measurements_sha256": review["implementation_measurements_sha256"],
        "review_lock_commit_sha": review_commit,
        "review_lock_file": review_file,
        "review_lock_internal_sha256": review_internal,
        "historical_evidence": review["historical_evidence"],
        "historical_evidence_manifest_sha256": review["historical_evidence_manifest_sha256"],
        "smoke_evidence_file": review["smoke_evidence_file"],
        "smoke_evidence_sha256": review["smoke_evidence_sha256"],
        "empty_prefix_evidence_file": review["empty_prefix_evidence_file"],
        "empty_prefix_evidence_sha256": review["empty_prefix_evidence_sha256"],
        "focused_test_receipt_file": review["focused_test_receipt_file"],
        "focused_test_receipt_sha256": review["focused_test_receipt_sha256"],
        "focused_test_output_file": review["focused_test_output_file"],
        "focused_test_command": review["focused_test_command"],
        "focused_test_pass_count": review["focused_test_pass_count"],
        "independent_review_disposition": review["independent_review_disposition"],
        "p0_open_count": 0,
        "p1_open_count": 0,
        "p2_open_count": 0,
        "real_task0_smoke_passed": True,
        "current_clean_git_required": True,
        "module_origin_verification_required": True,
        "publication_enable_environment_variable": ENABLE_ENV,
        "publication_enable_environment_value": "1",
        "publish_command": list(PUBLISH_COMMAND),
        "attempt_marker_command": list(ATTEMPT_MARKER_COMMAND),
        "reopen_command": list(REOPEN_COMMAND),
        "attempt_marker_relative_path": ATTEMPT_PATH,
        "attempt_marker_schema": ATTEMPT_SCHEMA,
        "attempt_marker_create_once_before_cloud_client": True,
        "attempt_marker_tracked_clean_before_publication": True,
        "attempt_marker_remote_reachability_required": True,
        "prior_projection_attempt_count": 2,
        "prior_projection_mutation_count": 0,
        "recovery_attempt_ordinal": RECOVERY_ATTEMPT_ORDINAL,
        "maximum_lifetime_projection_attempts": MAXIMUM_LIFETIME_PROJECTION_ATTEMPTS,
        "catalog_namespace": adapter.FIXED_CATALOG_NAMESPACE,
        "expected_inner_object_count": EXPECTED_INNER_OBJECT_COUNT,
        "expected_total_object_count": EXPECTED_TOTAL_OBJECT_COUNT,
        "outer_attestation_uri": OUTER_ATTESTATION_URI,
        "inner_receipt_exact_reopen_before_outer_required": True,
        "outer_attestation_root_last_required": True,
        "downstream_outer_identity_pin_required": True,
        "create_once_only": True,
        "overwrite_licensed": False,
        "catalog_projection_gcs_create_once_licensed": True,
        "request_authoritative_inner_publication": False,
        "world_matrix_bodies_read": False,
        "world_schedule_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **_review_false_fields(),
    }
    return _self_hash(body, "recovery_final_lock_sha256")


def validate_final_lock_v1(
    value: object,
    *,
    review_lock_commit_sha: str,
    review_lock_file: Mapping[str, object],
    review_lock: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="recovery final lock")
    _validate_self_hash(item, field="recovery_final_lock_sha256", label="recovery final lock")
    _false_authorities(item, label="recovery final lock")
    expected = build_final_lock_v1(
        review_lock_commit_sha=review_lock_commit_sha,
        review_lock_file=review_lock_file,
        review_lock=review_lock,
        publication_approved=True,
    )
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("recovery final lock differs from deterministic replay")
    return expected


def _load_bound_support_files(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    commit_sha: str,
    implementation_commit_sha: str,
    implementation_measurements: Sequence[Mapping[str, object]],
    smoke_file: Mapping[str, object],
    empty_file: Mapping[str, object],
    focused_receipt_file: Mapping[str, object],
    focused_output_file: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object], bytes]:
    smoke_raw = _read_tracked_exact(
        repository, commit=commit_sha, binding=smoke_file, label="tracked smoke evidence"
    )
    empty_raw = _read_tracked_exact(
        repository, commit=commit_sha, binding=empty_file, label="tracked empty-prefix evidence"
    )
    focused_receipt_raw = _read_tracked_exact(
        repository,
        commit=commit_sha,
        binding=focused_receipt_file,
        label="tracked focused-test receipt",
    )
    focused_output_raw = _read_tracked_exact(
        repository,
        commit=commit_sha,
        binding=focused_output_file,
        label="tracked focused-test output",
    )
    return (
        validate_smoke_evidence_v1(_parse_json(smoke_raw, label="tracked smoke evidence")),
        validate_empty_prefix_evidence_v1(
            _parse_json(empty_raw, label="tracked empty-prefix evidence"),
            implementation_commit_sha=implementation_commit_sha,
            implementation_measurements=implementation_measurements,
        ),
        _parse_json(focused_receipt_raw, label="tracked focused-test receipt"),
        focused_output_raw,
    )


def resolve_review_lock_v1(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    review_lock_commit_sha: str,
    current_head: str,
) -> tuple[dict[str, object], dict[str, object]]:
    review_commit = _commit(review_lock_commit_sha, label="review-lock commit")
    head = _commit(current_head, label="current clean head")
    raw = repository.read_tracked(review_commit, REVIEW_LOCK_PATH)
    review_file = file_binding(REVIEW_LOCK_PATH, raw)
    # The final-lock commit may advance HEAD, but it may not replace the
    # already-reviewed lock bytes.
    _read_tracked_exact(
        repository,
        commit=head,
        binding=review_file,
        label="current retained recovery review lock",
    )
    candidate = _parse_json(raw, label="tracked recovery review lock")
    candidate_implementation_commit = _commit(
        candidate.get("implementation_commit_sha"),
        label="candidate review implementation commit",
    )
    candidate_measurements = normalize_implementation_measurements_v1(
        candidate.get("implementation_measurements")
    )
    smoke_file = _mapping(candidate.get("smoke_evidence_file"), label="review smoke file")
    empty_file = _mapping(candidate.get("empty_prefix_evidence_file"), label="review empty file")
    focused_receipt_file = _mapping(
        candidate.get("focused_test_receipt_file"),
        label="review focused receipt file",
    )
    focused_output_file = _mapping(
        candidate.get("focused_test_output_file"), label="review focused output file"
    )
    smoke, empty, focused_receipt, focused_output_raw = _load_bound_support_files(
        repository,
        commit_sha=review_commit,
        implementation_commit_sha=candidate_implementation_commit,
        implementation_measurements=candidate_measurements,
        smoke_file=smoke_file,
        empty_file=empty_file,
        focused_receipt_file=focused_receipt_file,
        focused_output_file=focused_output_file,
    )
    review = validate_review_lock_v1(
        candidate,
        smoke_evidence=smoke,
        empty_prefix_evidence=empty,
        focused_test_receipt=focused_receipt,
        focused_test_output_raw=focused_output_raw,
    )
    implementation_commit = _commit(
        review["implementation_commit_sha"],
        label="review-lock implementation commit",
    )
    require_git_ancestor_v1(
        repository,
        ancestor_commit_sha=implementation_commit,
        descendant_commit_sha=review_commit,
        label="implementation-to-review",
    )
    require_git_ancestor_v1(
        repository,
        ancestor_commit_sha=review_commit,
        descendant_commit_sha=head,
        label="review-to-current",
    )
    reopen_historical_evidence_v1(repository)
    measurements = reopen_implementation_v1(
        repository,
        implementation_commit_sha=implementation_commit,
        measurements=_sequence(review["implementation_measurements"], label="review measurements"),
    )
    verify_current_implementation_v1(
        repository, current_head=head, reviewed_measurements=measurements
    )
    return review, review_file


def resolve_final_capability_v1(
    repository: adapter.SubprocessGitRepositoryV1,
    *,
    final_lock_commit_sha: str,
    current_head: str,
) -> PublicationCapabilityV1:
    final_commit = _commit(final_lock_commit_sha, label="final-lock commit")
    head = _commit(current_head, label="current final-lock head")
    final_raw = repository.read_tracked(final_commit, FINAL_LOCK_PATH)
    final_file = file_binding(FINAL_LOCK_PATH, final_raw)
    _read_tracked_exact(
        repository,
        commit=head,
        binding=final_file,
        label="current retained recovery final lock",
    )
    final_candidate = _parse_json(final_raw, label="tracked recovery final lock")
    review_commit = _commit(
        final_candidate.get("review_lock_commit_sha"),
        label="final-lock bound review commit",
    )
    review, review_file = resolve_review_lock_v1(
        repository,
        review_lock_commit_sha=review_commit,
        current_head=head,
    )
    final = validate_final_lock_v1(
        final_candidate,
        review_lock_commit_sha=review_commit,
        review_lock_file=review_file,
        review_lock=review,
    )
    require_git_ancestor_v1(
        repository,
        ancestor_commit_sha=review_commit,
        descendant_commit_sha=final_commit,
        label="review-to-final",
    )
    require_git_ancestor_v1(
        repository,
        ancestor_commit_sha=final_commit,
        descendant_commit_sha=head,
        label="final-to-current",
    )
    base_review = resolve_base_adapter_review_v1(repository)
    measurements = tuple(
        _sequence(final["implementation_measurements"], label="final measurements")
    )
    capability_body = {
        "current_clean_commit_sha": head,
        "implementation_commit_sha": str(final["implementation_commit_sha"]),
        "implementation_measurements": list(measurements),
        "review_lock_commit_sha": review_commit,
        "review_lock_file": review_file,
        "review_lock_internal_sha256": str(review["recovery_review_lock_sha256"]),
        "final_lock_commit_sha": final_commit,
        "final_lock_file": final_file,
        "final_lock_internal_sha256": str(final["recovery_final_lock_sha256"]),
        "review_lock_sha256": canonical_sha256(review),
        "final_lock_sha256": canonical_sha256(final),
    }
    return PublicationCapabilityV1(
        current_clean_commit_sha=head,
        implementation_commit_sha=str(final["implementation_commit_sha"]),
        implementation_measurements=measurements,
        review_lock_commit_sha=review_commit,
        review_lock_file=MappingProxyType(dict(review_file)),
        review_lock_internal_sha256=str(review["recovery_review_lock_sha256"]),
        final_lock_commit_sha=final_commit,
        final_lock_file=MappingProxyType(dict(final_file)),
        final_lock_internal_sha256=str(final["recovery_final_lock_sha256"]),
        review_lock=MappingProxyType(dict(review)),
        final_lock=MappingProxyType(dict(final)),
        base_adapter_review=base_review,
        capability_sha256=canonical_sha256(capability_body),
    )


def _validate_capability_v1(capability: object) -> PublicationCapabilityV1:
    if not isinstance(capability, PublicationCapabilityV1):
        _fail("catalog recovery publication capability differs")
    current_head = _commit(
        capability.current_clean_commit_sha, label="capability current clean commit"
    )
    implementation_commit = _commit(
        capability.implementation_commit_sha, label="capability implementation commit"
    )
    measurements = normalize_implementation_measurements_v1(
        capability.implementation_measurements
    )
    review_commit = _commit(
        capability.review_lock_commit_sha, label="capability review-lock commit"
    )
    review_file = normalize_file_binding(
        capability.review_lock_file, label="capability review-lock file"
    )
    review_internal = _sha(
        capability.review_lock_internal_sha256,
        label="capability review-lock internal SHA",
    )
    final_commit = _commit(
        capability.final_lock_commit_sha, label="capability final-lock commit"
    )
    final_file = normalize_file_binding(
        capability.final_lock_file, label="capability final-lock file"
    )
    final_internal = _sha(
        capability.final_lock_internal_sha256,
        label="capability final-lock internal SHA",
    )
    review = _mapping(capability.review_lock, label="capability review lock")
    final = _mapping(capability.final_lock, label="capability final lock")
    capability_body = {
        "current_clean_commit_sha": current_head,
        "implementation_commit_sha": implementation_commit,
        "implementation_measurements": measurements,
        "review_lock_commit_sha": review_commit,
        "review_lock_file": review_file,
        "review_lock_internal_sha256": review_internal,
        "final_lock_commit_sha": final_commit,
        "final_lock_file": final_file,
        "final_lock_internal_sha256": final_internal,
        "review_lock_sha256": canonical_sha256(review),
        "final_lock_sha256": canonical_sha256(final),
    }
    if (
        capability.capability_sha256 != canonical_sha256(capability_body)
        or review.get("recovery_review_lock_sha256") != review_internal
        or final.get("recovery_final_lock_sha256") != final_internal
        or final.get("implementation_commit_sha") != implementation_commit
        or final.get("implementation_measurements") != measurements
        or final.get("review_lock_commit_sha") != review_commit
        or final.get("review_lock_file") != review_file
        or final.get("review_lock_internal_sha256") != review_internal
        or final.get("catalog_projection_gcs_create_once_licensed") is not True
        or final.get("request_authoritative_inner_publication") is not False
        or final.get("outer_attestation_root_last_required") is not True
        or final.get("recovery_attempt_ordinal") != RECOVERY_ATTEMPT_ORDINAL
        or final.get("maximum_lifetime_projection_attempts")
        != MAXIMUM_LIFETIME_PROJECTION_ATTEMPTS
    ):
        _fail("catalog recovery final capability semantics differ")
    return capability


def validate_resolved_authority_v1(capability: object) -> PublicationCapabilityV1:
    return _validate_capability_v1(capability)


def build_attempt_marker_v1(
    *,
    capability: PublicationCapabilityV1,
    require_final_lock_at_head: bool = True,
) -> dict[str, object]:
    validated = _validate_capability_v1(capability)
    if (
        require_final_lock_at_head
        and validated.current_clean_commit_sha != validated.final_lock_commit_sha
    ):
        _fail("attempt marker must be built directly from the final-lock commit")
    body = {
        "schema_version": ATTEMPT_SCHEMA,
        "attempt_id": "fixed-g0-catalog-recovery-attempt-3",
        "attempt_relative_path": ATTEMPT_PATH,
        "projection_attempt_ordinal": RECOVERY_ATTEMPT_ORDINAL,
        "projection_attempt_count_before_reservation": 2,
        "lifetime_projection_attempt_count_after_reservation": 3,
        "maximum_projection_attempt_count": MAXIMUM_LIFETIME_PROJECTION_ATTEMPTS,
        "marker_build_parent_commit_sha": validated.final_lock_commit_sha,
        "implementation_commit_sha": validated.implementation_commit_sha,
        "implementation_measurements": list(validated.implementation_measurements),
        "implementation_measurements_sha256": canonical_sha256(
            list(validated.implementation_measurements)
        ),
        "review_lock_commit_sha": validated.review_lock_commit_sha,
        "review_lock_file": dict(validated.review_lock_file),
        "review_lock_internal_sha256": validated.review_lock_internal_sha256,
        "final_lock_commit_sha": validated.final_lock_commit_sha,
        "final_lock_file": dict(validated.final_lock_file),
        "final_lock_internal_sha256": validated.final_lock_internal_sha256,
        "historical_evidence_manifest_sha256": validated.final_lock[
            "historical_evidence_manifest_sha256"
        ],
        "marker_build_command": list(ATTEMPT_MARKER_COMMAND),
        "publication_command": list(PUBLISH_COMMAND),
        "catalog_namespace": adapter.FIXED_CATALOG_NAMESPACE,
        "outer_attestation_uri": OUTER_ATTESTATION_URI,
        "expected_inner_object_count": EXPECTED_INNER_OBJECT_COUNT,
        "expected_total_object_count": EXPECTED_TOTAL_OBJECT_COUNT,
        "state": "reserved-after-final-lock-before-cloud-client",
        "reserved_before_cloud_client_construction": True,
        "commit_and_remote_reachability_required_before_publication": True,
        "cloud_client_constructed": False,
        "cloud_contact_performed": False,
        "gcs_mutation_count": 0,
        "local_attempt_marker_create_count": 1,
        "additional_projection_attempt_licensed": False,
        "request_authoritative_inner_publication": False,
        "overwrite_licensed": False,
        "world_matrix_bodies_read": False,
        "world_schedule_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **_review_false_fields(),
    }
    return _self_hash(body, "recovery_attempt_sha256")


def validate_attempt_marker_v1(
    value: object,
    *,
    capability: PublicationCapabilityV1,
) -> dict[str, object]:
    item = _mapping(value, label="recovery attempt marker")
    _validate_self_hash(item, field="recovery_attempt_sha256", label="recovery attempt marker")
    _false_authorities(item, label="recovery attempt marker")
    expected = build_attempt_marker_v1(
        capability=capability, require_final_lock_at_head=False
    )
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("recovery attempt marker differs from exact capability")
    return expected


def resolve_tracked_attempt_binding_v1(
    *,
    repository: adapter.SubprocessGitRepositoryV1,
    current_head: str,
) -> tuple[PublicationCapabilityV1, TrackedAttemptBindingV1]:
    head = _commit(current_head, label="tracked-attempt current head")
    try:
        raw = repository.read_tracked(head, ATTEMPT_PATH)
    except Exception as exc:
        raise CorpusR6FixedG0CatalogRecoveryV1Error(
            "tracked recovery attempt three is absent"
        ) from exc
    marker_file = file_binding(ATTEMPT_PATH, raw)
    candidate = _parse_json(raw, label="tracked recovery attempt marker")
    final_commit = _commit(
        candidate.get("final_lock_commit_sha"),
        label="attempt-marker final-lock commit",
    )
    capability = resolve_final_capability_v1(
        repository,
        final_lock_commit_sha=final_commit,
        current_head=head,
    )
    marker = validate_attempt_marker_v1(candidate, capability=capability)
    marker_commit = tracked_file_introduction_commit_v1(
        repository,
        current_head=head,
        relative_path=ATTEMPT_PATH,
    )
    require_git_ancestor_v1(
        repository,
        ancestor_commit_sha=capability.final_lock_commit_sha,
        descendant_commit_sha=marker_commit,
        label="final-to-attempt",
    )
    require_git_ancestor_v1(
        repository,
        ancestor_commit_sha=marker_commit,
        descendant_commit_sha=head,
        label="attempt-to-current",
    )
    require_commit_reachable_from_remote_v1(
        repository, commit_sha=marker_commit
    )
    _read_tracked_exact(
        repository,
        commit=marker_commit,
        binding=marker_file,
        label="introduced tracked recovery attempt marker",
    )
    binding = TrackedAttemptBindingV1(
        reopened_at_commit_sha=head,
        marker_commit_sha=marker_commit,
        marker=MappingProxyType(dict(marker)),
        marker_file=MappingProxyType(dict(marker_file)),
        marker_internal_sha256=str(marker["recovery_attempt_sha256"]),
    )
    return capability, binding


def validate_tracked_attempt_binding_v1(
    binding: object,
    *,
    capability: PublicationCapabilityV1,
) -> TrackedAttemptBindingV1:
    validated_capability = _validate_capability_v1(capability)
    if (
        not isinstance(binding, TrackedAttemptBindingV1)
        or binding.reopened_at_commit_sha
        != validated_capability.current_clean_commit_sha
        or _commit(
            binding.marker_commit_sha, label="tracked attempt-marker commit"
        )
        != binding.marker_commit_sha
    ):
        _fail("tracked recovery attempt binding differs")
    marker = validate_attempt_marker_v1(
        _mapping(binding.marker, label="tracked attempt marker"),
        capability=validated_capability,
    )
    marker_file = normalize_file_binding(
        binding.marker_file, label="tracked attempt-marker file"
    )
    expected_raw = canonical_json_bytes(marker) + b"\n"
    if (
        marker_file != file_binding(ATTEMPT_PATH, expected_raw)
        or binding.marker_internal_sha256 != marker["recovery_attempt_sha256"]
    ):
        _fail("tracked recovery attempt bytes differ")
    return binding


def ordered_inner_object_manifest_v1(
    *,
    release_identity: Mapping[str, object],
    release: Mapping[str, object],
    receipt_identity: Mapping[str, object],
) -> list[dict[str, object]]:
    normalized_release_identity = adapter._normalized_identity(
        release_identity, label="inner release identity"
    )
    normalized_receipt_identity = adapter._normalized_identity(
        receipt_identity, label="inner receipt identity"
    )
    validated_release = catalog.validate_release_v1(
        release,
        expected_catalog_namespace=adapter.FIXED_CATALOG_NAMESPACE,
    )
    rows: list[dict[str, object]] = []
    for source_ordinal, raw_entry in enumerate(
        _sequence(validated_release["entries"], label="inner release entries")
    ):
        entry = _mapping(raw_entry, label=f"inner release entry[{source_ordinal}]")
        rows.extend((
            {
                "object_ordinal": len(rows),
                "role": "catalog_derivation_receipt",
                "source_task_ordinal": source_ordinal,
                "identity": adapter._normalized_identity(
                    entry["derivation_receipt_identity"],
                    label=f"derivation[{source_ordinal}]",
                ),
            },
            {
                "object_ordinal": len(rows) + 1,
                "role": "player_catalog",
                "source_task_ordinal": source_ordinal,
                "identity": adapter._normalized_identity(
                    entry["catalog_identity"], label=f"catalog[{source_ordinal}]"
                ),
            },
        ))
    rows.extend((
        {
            "object_ordinal": len(rows),
            "role": "catalog_release",
            "source_task_ordinal": None,
            "identity": normalized_release_identity,
        },
        {
            "object_ordinal": len(rows) + 1,
            "role": "inner_replay_receipt",
            "source_task_ordinal": None,
            "identity": normalized_receipt_identity,
        },
    ))
    uris = [str(row["identity"]["uri"]) for row in rows]
    if (
        len(rows) != EXPECTED_INNER_OBJECT_COUNT
        or [row["object_ordinal"] for row in rows] != list(range(EXPECTED_INNER_OBJECT_COUNT))
        or len(set(uris)) != EXPECTED_INNER_OBJECT_COUNT
        or any(not uri.startswith(adapter.FIXED_CATALOG_NAMESPACE) for uri in uris)
        or rows[-2]["identity"] != normalized_release_identity
        or rows[-1]["identity"] != normalized_receipt_identity
    ):
        _fail("inner object manifest coverage/order differs")
    return rows


def normalize_inner_object_manifest_v1(
    value: object,
    *,
    release_identity: Mapping[str, object],
    receipt_identity: Mapping[str, object],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    source_rows = _sequence(value, label="outer inner-object manifest")
    if len(source_rows) != EXPECTED_INNER_OBJECT_COUNT:
        _fail("outer inner-object manifest count differs")
    for ordinal, value_row in enumerate(source_rows):
        row = _mapping(value_row, label=f"outer inner-object manifest[{ordinal}]")
        _exact_keys(
            row,
            frozenset({"object_ordinal", "role", "source_task_ordinal", "identity"}),
            label=f"outer inner-object manifest[{ordinal}]",
        )
        if row["object_ordinal"] != ordinal:
            _fail("outer inner-object manifest ordinal differs")
        if ordinal < catalog.TASK_COUNT * 2:
            source_ordinal = ordinal // 2
            expected_role = (
                "catalog_derivation_receipt" if ordinal % 2 == 0 else "player_catalog"
            )
            if (
                row["source_task_ordinal"] != source_ordinal
                or row["role"] != expected_role
            ):
                _fail("outer inner-object manifest task order differs")
        else:
            expected_role = (
                "catalog_release"
                if ordinal == EXPECTED_INNER_OBJECT_COUNT - 2
                else "inner_replay_receipt"
            )
            if row["source_task_ordinal"] is not None or row["role"] != expected_role:
                _fail("outer inner-object manifest root order differs")
        rows.append({
            "object_ordinal": ordinal,
            "role": row["role"],
            "source_task_ordinal": row["source_task_ordinal"],
            "identity": adapter._normalized_identity(
                row["identity"], label=f"outer inner identity[{ordinal}]"
            ),
        })
    release_id = adapter._normalized_identity(
        release_identity, label="outer manifest release identity"
    )
    receipt_id = adapter._normalized_identity(
        receipt_identity, label="outer manifest receipt identity"
    )
    uris = [str(row["identity"]["uri"]) for row in rows]
    if (
        len(set(uris)) != EXPECTED_INNER_OBJECT_COUNT
        or any(not uri.startswith(adapter.FIXED_CATALOG_NAMESPACE) for uri in uris)
        or rows[-2]["identity"] != release_id
        or rows[-1]["identity"] != receipt_id
    ):
        _fail("outer inner-object manifest identity coverage differs")
    return rows


_OUTER_FIELDS: Final = frozenset({
    "schema_version",
    "attestation_id",
    "catalog_namespace",
    "outer_attestation_uri",
    "attempt_marker_commit_sha",
    "implementation_commit_sha",
    "implementation_measurements",
    "implementation_measurements_sha256",
    "review_lock_commit_sha",
    "review_lock_file",
    "review_lock_internal_sha256",
    "final_lock_commit_sha",
    "final_lock_file",
    "final_lock_internal_sha256",
    "historical_evidence",
    "historical_evidence_manifest_sha256",
    "smoke_evidence_file",
    "smoke_evidence_sha256",
    "empty_prefix_evidence_file",
    "empty_prefix_evidence_sha256",
    "attempt_marker",
    "attempt_marker_file",
    "attempt_marker_sha256",
    "inner_catalog_release_identity",
    "inner_catalog_release_sha256",
    "inner_replay_receipt_identity",
    "inner_replay_receipt_sha256",
    "inner_object_manifest",
    "inner_object_manifest_sha256",
    "inner_object_count",
    "expected_terminal_prefix_object_count",
    "inner_receipt_exact_reopened_before_outer_publication",
    "all_inner_catalogs_exact_reopened",
    "outer_attestation_published_last",
    "downstream_must_pin_outer_identity",
    "inner_receipt_self_authorizing",
    "create_once_only",
    "overwrite_licensed",
    "request_authoritative_inner_publication",
    "world_matrix_bodies_read",
    "world_schedule_bodies_read",
    "result_object_bodies_read",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_FALSE_AUTHORITY_FIELDS,
    "recovery_attestation_sha256",
})


def build_outer_attestation_v1(
    *,
    capability: PublicationCapabilityV1,
    attempt_binding: TrackedAttemptBindingV1,
    release_identity: Mapping[str, object],
    release: Mapping[str, object],
    replay_receipt_identity: Mapping[str, object],
    replay_receipt: Mapping[str, object],
) -> dict[str, object]:
    validated = _validate_capability_v1(capability)
    tracked_attempt = validate_tracked_attempt_binding_v1(
        attempt_binding, capability=validated
    )
    attempt = _mapping(tracked_attempt.marker, label="outer attempt marker")
    attempt_file = normalize_file_binding(
        tracked_attempt.marker_file, label="outer attempt file"
    )
    attempt_commit = _commit(
        tracked_attempt.marker_commit_sha, label="outer attempt-marker commit"
    )
    expected_attempt_file = file_binding(
        ATTEMPT_PATH, canonical_json_bytes(attempt) + b"\n"
    )
    manifest = ordered_inner_object_manifest_v1(
        release_identity=release_identity,
        release=release,
        receipt_identity=replay_receipt_identity,
    )
    release_id = adapter._normalized_identity(release_identity, label="outer inner release")
    receipt_id = adapter._normalized_identity(replay_receipt_identity, label="outer inner receipt")
    receipt = _mapping(replay_receipt, label="outer inner replay receipt")
    receipt_internal = _validate_self_hash(
        receipt,
        field="replay_receipt_sha256",
        label="outer inner replay receipt",
    )
    validated_release = catalog.validate_release_v1(
        release,
        expected_catalog_namespace=adapter.FIXED_CATALOG_NAMESPACE,
    )
    release_raw = canonical_json_bytes(validated_release)
    receipt_raw = canonical_json_bytes(receipt)
    if (
        attempt_file != expected_attempt_file
        or release_id["sha256"] != sha256(release_raw).hexdigest()
        or release_id["bytes"] != len(release_raw)
        or receipt_id["sha256"] != sha256(receipt_raw).hexdigest()
        or receipt_id["bytes"] != len(receipt_raw)
        or receipt_internal != receipt["replay_receipt_sha256"]
        or receipt.get("catalog_release_identity") != release_id
        or receipt.get("catalog_release_sha256") != validated_release["release_sha256"]
    ):
        _fail("outer attestation inner chain differs")
    body = {
        "schema_version": OUTER_ATTESTATION_SCHEMA,
        "attestation_id": "fixed-g0-catalog-recovery-v2",
        "catalog_namespace": adapter.FIXED_CATALOG_NAMESPACE,
        "outer_attestation_uri": OUTER_ATTESTATION_URI,
        "attempt_marker_commit_sha": attempt_commit,
        "implementation_commit_sha": validated.implementation_commit_sha,
        "implementation_measurements": list(validated.implementation_measurements),
        "implementation_measurements_sha256": canonical_sha256(
            list(validated.implementation_measurements)
        ),
        "review_lock_commit_sha": validated.review_lock_commit_sha,
        "review_lock_file": dict(validated.review_lock_file),
        "review_lock_internal_sha256": validated.review_lock_internal_sha256,
        "final_lock_commit_sha": validated.final_lock_commit_sha,
        "final_lock_file": dict(validated.final_lock_file),
        "final_lock_internal_sha256": validated.final_lock_internal_sha256,
        "historical_evidence": validated.final_lock["historical_evidence"],
        "historical_evidence_manifest_sha256": validated.final_lock[
            "historical_evidence_manifest_sha256"
        ],
        "smoke_evidence_file": validated.final_lock["smoke_evidence_file"],
        "smoke_evidence_sha256": validated.final_lock["smoke_evidence_sha256"],
        "empty_prefix_evidence_file": validated.final_lock[
            "empty_prefix_evidence_file"
        ],
        "empty_prefix_evidence_sha256": validated.final_lock[
            "empty_prefix_evidence_sha256"
        ],
        "attempt_marker": attempt,
        "attempt_marker_file": attempt_file,
        "attempt_marker_sha256": attempt["recovery_attempt_sha256"],
        "inner_catalog_release_identity": release_id,
        "inner_catalog_release_sha256": validated_release["release_sha256"],
        "inner_replay_receipt_identity": receipt_id,
        "inner_replay_receipt_sha256": receipt_internal,
        "inner_object_manifest": manifest,
        "inner_object_manifest_sha256": canonical_sha256(manifest),
        "inner_object_count": EXPECTED_INNER_OBJECT_COUNT,
        "expected_terminal_prefix_object_count": EXPECTED_TOTAL_OBJECT_COUNT,
        "inner_receipt_exact_reopened_before_outer_publication": True,
        "all_inner_catalogs_exact_reopened": True,
        "outer_attestation_published_last": True,
        "downstream_must_pin_outer_identity": True,
        "inner_receipt_self_authorizing": False,
        "create_once_only": True,
        "overwrite_licensed": False,
        "request_authoritative_inner_publication": False,
        "world_matrix_bodies_read": False,
        "world_schedule_bodies_read": False,
        "result_object_bodies_read": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **_review_false_fields(),
    }
    return _self_hash(body, "recovery_attestation_sha256")


def validate_outer_attestation_v1(
    value: object,
    *,
    capability: PublicationCapabilityV1,
    attempt_binding: TrackedAttemptBindingV1,
) -> dict[str, object]:
    item = _mapping(value, label="catalog recovery outer attestation")
    _exact_keys(item, _OUTER_FIELDS, label="catalog recovery outer attestation")
    _validate_self_hash(
        item, field="recovery_attestation_sha256", label="catalog recovery outer attestation"
    )
    _false_authorities(item, label="catalog recovery outer attestation")
    validated = _validate_capability_v1(capability)
    tracked_attempt = validate_tracked_attempt_binding_v1(
        attempt_binding, capability=validated
    )
    measurements = normalize_implementation_measurements_v1(item.get("implementation_measurements"))
    release_identity = adapter._normalized_identity(
        item.get("inner_catalog_release_identity"), label="outer inner release identity"
    )
    receipt_identity = adapter._normalized_identity(
        item.get("inner_replay_receipt_identity"), label="outer inner receipt identity"
    )
    release_sha256 = _sha(
        item.get("inner_catalog_release_sha256"), label="outer inner release SHA"
    )
    receipt_sha256 = _sha(
        item.get("inner_replay_receipt_sha256"), label="outer inner receipt SHA"
    )
    manifest = normalize_inner_object_manifest_v1(
        item.get("inner_object_manifest"),
        release_identity=release_identity,
        receipt_identity=receipt_identity,
    )
    attempt = validate_attempt_marker_v1(
        _mapping(item.get("attempt_marker"), label="outer attempt marker"),
        capability=validated,
    )
    attempt_file = normalize_file_binding(
        item.get("attempt_marker_file"), label="outer attempt-marker file"
    )
    expected_attempt_file = file_binding(
        ATTEMPT_PATH, canonical_json_bytes(attempt) + b"\n"
    )
    review_file = normalize_file_binding(
        item.get("review_lock_file"), label="outer review-lock file"
    )
    final_file = normalize_file_binding(
        item.get("final_lock_file"), label="outer final-lock file"
    )
    smoke_file = normalize_file_binding(
        item.get("smoke_evidence_file"), label="outer smoke-evidence file"
    )
    empty_file = normalize_file_binding(
        item.get("empty_prefix_evidence_file"), label="outer empty-prefix file"
    )
    if (
        item.get("schema_version") != OUTER_ATTESTATION_SCHEMA
        or item.get("attestation_id") != "fixed-g0-catalog-recovery-v2"
        or item.get("catalog_namespace") != adapter.FIXED_CATALOG_NAMESPACE
        or item.get("outer_attestation_uri") != OUTER_ATTESTATION_URI
        or item.get("attempt_marker_commit_sha")
        != tracked_attempt.marker_commit_sha
        or item.get("implementation_commit_sha") != validated.implementation_commit_sha
        or measurements != list(validated.implementation_measurements)
        or item.get("implementation_measurements_sha256") != canonical_sha256(measurements)
        or item.get("review_lock_commit_sha") != validated.review_lock_commit_sha
        or review_file != dict(validated.review_lock_file)
        or item.get("review_lock_internal_sha256") != validated.review_lock_internal_sha256
        or item.get("final_lock_commit_sha") != validated.final_lock_commit_sha
        or final_file != dict(validated.final_lock_file)
        or item.get("final_lock_internal_sha256") != validated.final_lock_internal_sha256
        or item.get("historical_evidence") != validated.final_lock["historical_evidence"]
        or item.get("historical_evidence_manifest_sha256")
        != validated.final_lock["historical_evidence_manifest_sha256"]
        or smoke_file != validated.final_lock["smoke_evidence_file"]
        or item.get("smoke_evidence_sha256")
        != validated.final_lock["smoke_evidence_sha256"]
        or empty_file != validated.final_lock["empty_prefix_evidence_file"]
        or item.get("empty_prefix_evidence_sha256")
        != validated.final_lock["empty_prefix_evidence_sha256"]
        or attempt_file != expected_attempt_file
        or item.get("attempt_marker_sha256") != attempt["recovery_attempt_sha256"]
        or item.get("inner_catalog_release_identity") != release_identity
        or item.get("inner_catalog_release_sha256") != release_sha256
        or item.get("inner_replay_receipt_identity") != receipt_identity
        or item.get("inner_replay_receipt_sha256") != receipt_sha256
        or item.get("inner_object_manifest") != manifest
        or item.get("inner_object_manifest_sha256") != canonical_sha256(manifest)
        or item.get("inner_object_count") != EXPECTED_INNER_OBJECT_COUNT
        or len(manifest) != EXPECTED_INNER_OBJECT_COUNT
        or item.get("expected_terminal_prefix_object_count")
        != EXPECTED_TOTAL_OBJECT_COUNT
        or item.get("inner_receipt_exact_reopened_before_outer_publication") is not True
        or item.get("all_inner_catalogs_exact_reopened") is not True
        or item.get("outer_attestation_published_last") is not True
        or item.get("downstream_must_pin_outer_identity") is not True
        or item.get("inner_receipt_self_authorizing") is not False
        or item.get("create_once_only") is not True
        or item.get("overwrite_licensed") is not False
        or item.get("request_authoritative_inner_publication") is not False
        or item.get("world_matrix_bodies_read") is not False
        or item.get("world_schedule_bodies_read") is not False
        or item.get("result_object_bodies_read") is not False
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
    ):
        _fail("catalog recovery outer attestation semantics differ")
    return item


def _reopen_outer_structure_v1(
    *,
    outer_identity: Mapping[str, object],
    capability: PublicationCapabilityV1,
    attempt_binding: TrackedAttemptBindingV1,
    transport: adapter.GenerationTransportV1,
) -> dict[str, object]:
    identity = adapter._normalized_identity(outer_identity, label="catalog recovery outer identity")
    if identity["uri"] != OUTER_ATTESTATION_URI:
        _fail("catalog recovery outer URI differs")
    raw = adapter.read_generation_exact_v1(identity, transport=transport)
    attestation = validate_outer_attestation_v1(
        _parse_json(raw, label="catalog recovery outer attestation"),
        capability=capability,
        attempt_binding=attempt_binding,
    )
    return {"outer_identity": identity, "outer_attestation": attestation}


def write_local_raw_create_once_v1(
    *,
    repository_root: Path,
    relative_path: str,
    raw: bytes,
) -> dict[str, object]:
    """Atomically create or exact-resume one local authority artifact."""
    root = repository_root.resolve()
    binding = normalize_file_binding(
        {"relative_path": relative_path, "sha256": "0" * 64, "bytes": 1},
        label="local create-once output",
    )
    output = (root / str(binding["relative_path"])).resolve()
    if root not in output.parents:
        _fail("local create-once output escapes repository")
    output.parent.mkdir(parents=True, exist_ok=True)
    if type(raw) is not bytes or not raw:
        _fail("local create-once output bytes differ")

    def reopen_existing() -> dict[str, object]:
        try:
            with output.open("rb") as handle:
                observed = handle.read(len(raw) + 1)
                trailing = handle.read(1)
        except OSError as exc:
            raise CorpusR6FixedG0CatalogRecoveryV1Error(
                f"local create-once output cannot be reopened: {relative_path}"
            ) from exc
        if trailing or observed != raw:
            _fail(f"local create-once output collision differs: {relative_path}")
        return file_binding(relative_path, raw)

    if output.exists():
        return reopen_existing()

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), 0o644)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError:
            return reopen_existing()
        directory_descriptor = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return file_binding(relative_path, raw)


def write_local_create_once_v1(
    *,
    repository_root: Path,
    relative_path: str,
    body: Mapping[str, object],
) -> dict[str, object]:
    return write_local_raw_create_once_v1(
        repository_root=repository_root,
        relative_path=relative_path,
        raw=canonical_json_bytes(body) + b"\n",
    )


__all__ = [
    "ATTEMPT_MARKER_COMMAND",
    "ATTEMPT_PATH",
    "ATTEMPT_SCHEMA",
    "EMPTY_PREFIX_EVIDENCE_PATH",
    "EMPTY_PREFIX_EVIDENCE_SCHEMA",
    "ENABLE_ENV",
    "EXPECTED_INNER_OBJECT_COUNT",
    "EXPECTED_TOTAL_OBJECT_COUNT",
    "FINAL_LOCK_PATH",
    "FINAL_LOCK_SCHEMA",
    "FOCUSED_TEST_COMMAND",
    "FOCUSED_TEST_OUTPUT_PATH",
    "FOCUSED_TEST_RECEIPT_PATH",
    "FOCUSED_TEST_RECEIPT_SCHEMA",
    "FOCUSED_TEST_CLASSNAMES",
    "HISTORICAL_EVIDENCE",
    "IMPLEMENTATION_PATHS",
    "OUTER_ATTESTATION_SCHEMA",
    "OUTER_ATTESTATION_URI",
    "PUBLISH_COMMAND",
    "PublicationCapabilityV1",
    "RECOVERY_MODULE_PATH",
    "REOPEN_COMMAND",
    "REVIEW_LOCK_PATH",
    "REVIEW_LOCK_SCHEMA",
    "RUNNER_PATH",
    "SMOKE_COMMAND",
    "SMOKE_EVIDENCE_PATH",
    "SMOKE_EVIDENCE_SCHEMA",
    "TrackedAttemptBindingV1",
    "TransportAuditV1",
    "CorpusR6FixedG0CatalogRecoveryV1Error",
    "build_attempt_marker_v1",
    "build_empty_prefix_evidence_v1",
    "build_final_lock_v1",
    "build_focused_test_receipt_v1",
    "build_outer_attestation_v1",
    "build_review_lock_v1",
    "build_smoke_evidence_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "expected_module_origins_v1",
    "file_binding",
    "historical_evidence_manifest_v1",
    "measure_implementation_v1",
    "normalize_file_binding",
    "normalize_implementation_measurements_v1",
    "normalize_prefix_inventory_v1",
    "ordered_inner_object_manifest_v1",
    "planned_inner_output_uris_v1",
    "reopen_historical_evidence_v1",
    "prefix_inventory_from_identities_v1",
    "require_git_ancestor_v1",
    "require_commit_reachable_from_remote_v1",
    "resolve_base_adapter_review_v1",
    "resolve_tracked_attempt_binding_v1",
    "resolve_final_capability_v1",
    "resolve_review_lock_v1",
    "source_read_allowlist_v1",
    "tracked_file_introduction_commit_v1",
    "validate_attempt_marker_v1",
    "validate_empty_prefix_evidence_v1",
    "validate_final_lock_v1",
    "validate_focused_test_receipt_v1",
    "validate_outer_attestation_v1",
    "validate_resolved_authority_v1",
    "validate_review_lock_v1",
    "validate_smoke_evidence_v1",
    "validate_tracked_attempt_binding_v1",
    "verify_current_implementation_v1",
    "verify_module_origins_v1",
    "write_local_create_once_v1",
    "write_local_raw_create_once_v1",
]
