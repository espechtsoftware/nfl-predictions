#!/usr/bin/env python3
"""Forensically close the already-opened A3 result without mutating science.

This is intentionally not the original strict harvester.  The A3 cell bodies
and aggregate were opened and committed before that harvester ran.  This tool
describes all executions and objects first, generation-pins every download,
requires exact equality with the original Git-tracked result, independently
rebuilds the aggregate, and publishes only local provenance evidence plus an
operational v2 lane release.  It has no launch, retry, BigQuery, upload,
cancel, delete, or scientific-write path.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Mapping

from google.api_core.exceptions import NotFound
from google.cloud import storage


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import finish_stack_relaxation_carve as strict  # noqa: E402


RUN_ID = strict.RUN_ID
NEXT_RUN_ID = "20260820-a7-select-ladder-phase-s-incumbent-v1"
RESULT_COMMIT = "56b09e960e5445cc7cd54c22eceef7cb5e7ec8c0"
RESULT_REPORT = ROOT / "reports/2026-08-20-stack-relaxation-carve-results.md"
RESULT_REPORT_SHA256 = (
    "b8ae2d2684baa8a236e5e0cfeb31eec27d9b1a8697702d11cb30c16724cbe7ae"
)
AGGREGATE_SHA256 = (
    "2e08a551d116dc385b92ef123be3a6bb8296c71a75c822797d04c71bd669afdc"
)
CLOSURE_PROTOCOL = (
    ROOT / "reports/2026-08-20-a3-post-open-forensic-closure-protocol.md"
)
CLOSURE_PROTOCOL_SHA256 = (
    "502c9c2c70ac0aa99ea5873c7fa99999557cd6f2aac5f6c95bfde1b33351e22b"
)
STRICT_FINISHER = ROOT / "scripts/finish_stack_relaxation_carve.py"
STRICT_FINISHER_SHA256 = (
    "c43505f61008dd217395ba21f6f485c9a87a72fd72a581123f68c565df2addf2"
)
STRICT_TEST = ROOT / "tests/test_finish_stack_relaxation_carve.py"
STRICT_TEST_SHA256 = (
    "13a6359b1d4165737f9b9b38755d5e6924f15d946b410a6801ee4b499204a191"
)
PREOPEN_ADDENDUM = (
    ROOT / "reports/2026-08-20-stack-relaxation-carve-provenance-addendum.json"
)
PREOPEN_ADDENDUM_SHA256 = (
    "fb2ad4f3239f08ef17e35f71e10fbfa1471b48e2b18c9be77730ade3594c4860"
)
DEFAULT_OUT = strict.DEFAULT_OUT
CLOSURE_NAME = "post-open-forensic-closure"
PENDING_NAME = ".post-open-forensic-closure.pending"
RELEASE_NAME = "logical-release.json"
LEASE_URI = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)
IMPLEMENTATION_PATH = "scripts/close_stack_relaxation_carve_post_open.py"
IMPLEMENTATION_TEST_PATH = "tests/test_close_stack_relaxation_carve_post_open.py"
PAIRED_STATS_RELATIVE = "src/nfl_dfs/research/paired_max_stats.py"
PAIRED_STATS_PATH = ROOT / PAIRED_STATS_RELATIVE
PAIRED_STATS_SHA256 = (
    "9d2f5e9e56492c187c50d089e493d8b94a494fa474b87e1534ab34b963cbf090"
)
IMPLEMENTATION_FREEZE = (
    ROOT / "reports/2026-08-20-a3-post-open-forensic-closure-implementation-freeze.json"
)


ExecutionLoader = Callable[[str], dict[str, Any]]
InventoryLoader = Callable[[str], Mapping[str, dict[str, Any]]]
Downloader = Callable[[str, dict[str, Any]], bytes]
LeaseAbsenceLoader = Callable[[], dict[str, str]]
GitLoader = Callable[[str, str], bytes]


def _sha_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ) + "\n"
    ).encode()


def _no_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def _unique_pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_json(raw: bytes, *, label: str, canonical: bool = True) -> dict[str, Any]:
    try:
        value = json.loads(
            raw, object_pairs_hook=_unique_pairs, parse_constant=_no_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"A3 recovery {label} is invalid JSON") from exc
    if not isinstance(value, dict) or (canonical and _canonical(value) != raw):
        raise RuntimeError(f"A3 recovery {label} is not canonical")
    return value


def _write_or_validate(path: Path, raw: bytes) -> None:
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise RuntimeError(f"A3 recovery create-once target differs: {path}")
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)


def _git_blob(commit: str, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{commit}:{relative}"],
        check=True, capture_output=True,
    )
    return result.stdout


def _head() -> str:
    value = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True, text=True, capture_output=True,
    ).stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise RuntimeError("A3 recovery HEAD identity differs")
    return value


def _exact_int(value: object, *, label: str, absent_zero: bool = False) -> int:
    if absent_zero and value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"A3 recovery {label} is not an exact nonnegative integer")
    return value


def _utc_timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"A3 recovery {label} differs")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(f"A3 recovery {label} differs") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RuntimeError(f"A3 recovery {label} differs")
    return parsed


def _validate_execution_exact(
    metadata: dict[str, Any], cell: strict.Cell,
    frozen: strict.FrozenRun,
) -> None:
    strict._validate_execution(metadata, cell, frozen)
    meta = metadata.get("metadata")
    status = metadata.get("status")
    spec = metadata.get("spec")
    if not all(isinstance(value, dict) for value in (meta, status, spec)):
        raise RuntimeError("A3 recovery execution object shape differs")
    if _exact_int(meta.get("generation"), label="execution generation") != 1 or \
            _exact_int(status.get("observedGeneration"),
                       label="observed generation") != 1 or \
            _exact_int(status.get("succeededCount"),
                       label="succeeded count") != 1:
        raise RuntimeError("A3 recovery execution terminal counters differ")
    for key in ("failedCount", "cancelledCount", "retriedCount"):
        if _exact_int(status.get(key), label=key, absent_zero=True) != 0:
            raise RuntimeError("A3 recovery execution terminal counters differ")
    task = spec.get("template", {}).get("spec", {})
    if _exact_int(spec.get("parallelism"), label="parallelism") != 1 or \
            _exact_int(spec.get("taskCount"), label="taskCount") != 1 or \
            _exact_int(task.get("maxRetries"), label="maxRetries") != 0:
        raise RuntimeError("A3 recovery execution task integers differ")


def _implementation_identity(
    git_loader: GitLoader = _git_blob, freeze_path: Path = IMPLEMENTATION_FREEZE,
) -> dict[str, Any]:
    if not freeze_path.is_file():
        raise RuntimeError("A3 recovery implementation freeze is absent")
    raw = freeze_path.read_bytes()
    try:
        freeze_relative = str(freeze_path.relative_to(ROOT))
    except ValueError as exc:
        raise RuntimeError("A3 recovery implementation freeze path differs") from exc
    try:
        tracked_freeze = git_loader(_head(), freeze_relative)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("A3 recovery implementation freeze is not tracked") from exc
    if tracked_freeze != raw:
        raise RuntimeError("A3 recovery implementation freeze differs from HEAD")
    freeze = _parse_json(raw, label="implementation freeze")
    if set(freeze) != {
        "version", "run_id", "status", "source_commit", "implementation",
        "operator_approved", "frozen_at", "manifest_contains_realized_outcomes",
        "cell_rerun_licensed", "scientific_retest_licensed",
        "production_change_licensed",
    }:
        raise RuntimeError("A3 recovery implementation freeze fields differ")
    fixed = {
        "version": "stack-relaxation-carve-post-open-implementation-freeze-v1",
        "run_id": RUN_ID,
        "status": "frozen-for-post-open-forensic-closure",
        "operator_approved": True,
        "manifest_contains_realized_outcomes": False,
        "cell_rerun_licensed": False,
        "scientific_retest_licensed": False,
        "production_change_licensed": False,
    }
    if any(_canonical(freeze.get(key)) != _canonical(expected)
           for key, expected in fixed.items()) or \
            re.fullmatch(r"[0-9a-f]{40}", str(
                freeze.get("source_commit", "")
            )) is None:
        raise RuntimeError("A3 recovery implementation freeze differs")
    _utc_timestamp(freeze.get("frozen_at"), label="implementation freeze timestamp")
    implementation = freeze.get("implementation")
    paths = {
        "script": (ROOT / IMPLEMENTATION_PATH, IMPLEMENTATION_PATH),
        "tests": (ROOT / IMPLEMENTATION_TEST_PATH, IMPLEMENTATION_TEST_PATH),
        "protocol": (CLOSURE_PROTOCOL, str(CLOSURE_PROTOCOL.relative_to(ROOT))),
    }
    if not isinstance(implementation, dict) or set(implementation) != set(paths):
        raise RuntimeError("A3 recovery frozen implementation population differs")
    commit = str(freeze["source_commit"])
    normalized: dict[str, dict[str, str]] = {}
    for key, (path, relative) in paths.items():
        row = implementation.get(key)
        if not isinstance(row, dict) or set(row) != {"path", "sha256"} or \
                row.get("path") != relative or re.fullmatch(
                    r"[0-9a-f]{64}", str(row.get("sha256", ""))
                ) is None:
            raise RuntimeError("A3 recovery frozen implementation row differs")
        if not path.is_file():
            raise RuntimeError(f"A3 recovery committed implementation is absent: {relative}")
        local = path.read_bytes()
        try:
            committed = git_loader(commit, relative)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"A3 recovery implementation is not committed: {relative}"
            ) from exc
        if local != committed:
            raise RuntimeError(f"A3 recovery implementation differs from freeze: {relative}")
        if _sha_bytes(local) != row["sha256"]:
            raise RuntimeError(f"A3 recovery implementation SHA differs: {relative}")
        normalized[key] = {"path": relative, "sha256": row["sha256"]}
    if normalized["protocol"]["sha256"] != CLOSURE_PROTOCOL_SHA256:
        raise RuntimeError("A3 recovery protocol SHA differs")
    return {
        "source_commit": commit,
        "freeze_manifest_path": freeze_relative,
        "freeze_manifest_sha256": _sha_bytes(raw),
        "implementation": normalized,
        "operator_approved": True,
        "frozen_at": freeze["frozen_at"],
    }


def _validate_frozen_inputs(
    out: Path, *, git_loader: GitLoader = _git_blob,
) -> tuple[list[strict.Cell], dict[str, str]]:
    fixed = (
        (STRICT_FINISHER, STRICT_FINISHER_SHA256, "strict finisher"),
        (STRICT_TEST, STRICT_TEST_SHA256, "strict finisher tests"),
        (PREOPEN_ADDENDUM, PREOPEN_ADDENDUM_SHA256, "pre-open addendum"),
        (CLOSURE_PROTOCOL, CLOSURE_PROTOCOL_SHA256, "closure protocol"),
        (RESULT_REPORT, RESULT_REPORT_SHA256, "result report"),
        (out / "aggregate-report.json", AGGREGATE_SHA256, "aggregate"),
        (PAIRED_STATS_PATH, PAIRED_STATS_SHA256, "paired statistics source"),
    )
    for path, expected, label in fixed:
        if not path.is_file() or _sha(path) != expected:
            raise RuntimeError(f"A3 recovery {label} differs")
    cells = strict._read_ledger(out / "executions.txt", strict.FROZEN)
    expected_names = {cell.stem for cell in cells}
    cell_dir = out / "cells"
    if not cell_dir.is_dir() or {path.name for path in cell_dir.iterdir()} != expected_names:
        raise RuntimeError("A3 recovery committed cell inventory differs")
    tracked: list[str] = [
        str((out / "aggregate-report.json").relative_to(ROOT)),
        str(RESULT_REPORT.relative_to(ROOT)),
    ] + [str((cell_dir / cell.stem).relative_to(ROOT)) for cell in cells]
    for relative in tracked:
        local = (ROOT / relative).read_bytes()
        try:
            committed = git_loader(RESULT_COMMIT, relative)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"A3 recovery result is absent at result commit: {relative}") from exc
        if local != committed:
            raise RuntimeError(f"A3 recovery result differs from original commit: {relative}")
    for relative in (
        str(STRICT_FINISHER.relative_to(ROOT)),
        str(STRICT_TEST.relative_to(ROOT)),
        str(PREOPEN_ADDENDUM.relative_to(ROOT)),
    ):
        try:
            git_loader(RESULT_COMMIT, relative)
        except subprocess.CalledProcessError:
            pass
        else:
            raise RuntimeError("A3 recovery pre-open material chronology differs")
    for commit in (strict.FROZEN.code_sha, RESULT_COMMIT):
        try:
            paired_statistics = git_loader(commit, PAIRED_STATS_RELATIVE)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "A3 recovery paired statistics source is absent from frozen history"
            ) from exc
        if _sha_bytes(paired_statistics) != PAIRED_STATS_SHA256:
            raise RuntimeError(
                "A3 recovery paired statistics source differs from frozen history"
            )
    strict._validate_sources(
        out, PREOPEN_ADDENDUM, strict.FROZEN, root=ROOT,
        git_source_loader=lambda root, commit, relative: git_loader(commit, relative),
    )
    return cells, _implementation_identity(git_loader)


def _hash_ledger(paths: list[Path], *, base: Path) -> bytes:
    return "".join(
        f"{_sha(path)}  {path.relative_to(base)}\n" for path in sorted(paths)
    ).encode()


def _cell_ledger(out: Path, cells: list[strict.Cell]) -> bytes:
    return "".join(
        f"{_sha(out / 'cells' / cell.stem)}  cells/{cell.stem}\n"
        for cell in cells
    ).encode()


def _validate_ledger(path: Path, *, base: Path, expected: set[str]) -> None:
    rows = strict._parse_checksum_ledger(path)
    if len(rows) != len(expected) or {name for _, name in rows} != expected:
        raise RuntimeError(f"A3 recovery ledger population differs: {path.name}")
    for digest, name in rows:
        candidate = base / name
        try:
            candidate.resolve().relative_to(base.resolve())
        except ValueError as exc:
            raise RuntimeError("A3 recovery ledger path escapes closure") from exc
        if not candidate.is_file() or _sha(candidate) != digest:
            raise RuntimeError(f"A3 recovery ledger target differs: {name}")


def _validate_evidence_inventory(directory: Path) -> None:
    expected_metadata = {
        f"slate-{season}-{week}.json"
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    expected_top = {
        "execution-metadata", "object-metadata", "cells.sha256",
        "execution-metadata.sha256", "object-metadata.sha256",
        "closure.json", "closure.sha256",
    }
    if not directory.is_dir() or directory.is_symlink() or {
        path.name for path in directory.iterdir()
    } != expected_top:
        raise RuntimeError("A3 recovery evidence inventory differs")
    for name in ("execution-metadata", "object-metadata"):
        metadata_dir = directory / name
        if not metadata_dir.is_dir() or metadata_dir.is_symlink() or {
            path.name for path in metadata_dir.iterdir()
        } != expected_metadata or any(
            not path.is_file() or path.is_symlink()
            for path in metadata_dir.iterdir()
        ):
            raise RuntimeError("A3 recovery evidence inventory differs")


def _completion_body(
    *, out: Path, implementation: dict[str, str], cell_ledger_sha: str,
    execution_ledger_sha: str, object_ledger_sha: str,
    closed_at: str,
) -> dict[str, Any]:
    return {
        "version": "stack-relaxation-carve-post-open-forensic-closure-v1",
        "run_id": RUN_ID,
        "status": "post-open-forensic-closure-complete",
        "closure_mode": "post-open-forensic-provenance-recovery",
        "protocol_sha256": CLOSURE_PROTOCOL_SHA256,
        "protocol_deviation_disclosed": True,
        "scientific_result_opened_before_strict_harvest": True,
        "recovery_reads_already_opened_realized_outcomes": True,
        "strict_harvest_completed_before_read": False,
        "original_result_commit": RESULT_COMMIT,
        "prior_arm_disposition": "negative-closed-at-this-dose",
        "result_report": {
            "path": str(RESULT_REPORT.relative_to(ROOT)),
            "sha256": RESULT_REPORT_SHA256,
        },
        "aggregate": {
            "path": str((out / "aggregate-report.json").relative_to(ROOT)),
            "sha256": AGGREGATE_SHA256,
            "bytes": (out / "aggregate-report.json").stat().st_size,
            "recomputed_byte_identical": True,
        },
        "cells": {
            "count": 54,
            "ledger_sha256": cell_ledger_sha,
            "git_byte_identity": True,
            "remote_generation_byte_identity": True,
        },
        "launch": {
            "manifest_sha256": strict.FROZEN.original_manifest_sha256,
            "execution_ledger_sha256": strict.FROZEN.execution_ledger_sha256,
            "launch_receipt_sha256": strict.FROZEN.launch_receipt_sha256,
        },
        "preopen_material": {
            "finisher_sha256": STRICT_FINISHER_SHA256,
            "tests_sha256": STRICT_TEST_SHA256,
            "addendum_sha256": PREOPEN_ADDENDUM_SHA256,
            "was_untracked_at_result_commit": True,
        },
        "closure_implementation": implementation,
        "executions": {
            "count": 54,
            "metadata_ledger_sha256": execution_ledger_sha,
            "all_strict_terminal": True,
        },
        "objects": {
            "count": 54,
            "metadata_ledger_sha256": object_ledger_sha,
            "exact_inventory": True,
            "generation_pinned": True,
        },
        "cell_rerun_licensed": False,
        "scientific_retest_licensed": False,
        "production_change_licensed": False,
        "shadow_adoption_licensed": False,
        "a3_result_transport_to_a7_licensed": False,
        "closed_at": closed_at,
    }


def _validate_closure(
    out: Path, *, implementation: dict[str, str] | None = None,
) -> dict[str, Any]:
    closure_dir = out / CLOSURE_NAME
    if not closure_dir.is_dir():
        raise RuntimeError("A3 recovery closure is absent")
    _validate_evidence_inventory(closure_dir)
    expected_exec = {
        f"execution-metadata/slate-{season}-{week}.json"
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    expected_objects = {
        f"object-metadata/slate-{season}-{week}.json"
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    _validate_ledger(
        closure_dir / "execution-metadata.sha256", base=closure_dir,
        expected=expected_exec,
    )
    _validate_ledger(
        closure_dir / "object-metadata.sha256", base=closure_dir,
        expected=expected_objects,
    )
    cells = strict._read_ledger(out / "executions.txt", strict.FROZEN)
    if (closure_dir / "cells.sha256").read_bytes() != _cell_ledger(out, cells):
        raise RuntimeError("A3 recovery cell ledger differs")
    closure = _parse_json(
        (closure_dir / "closure.json").read_bytes(), label="closure",
    )
    expected_keys = {
        "version", "run_id", "status", "closure_mode", "protocol_sha256",
        "protocol_deviation_disclosed",
        "scientific_result_opened_before_strict_harvest",
        "recovery_reads_already_opened_realized_outcomes",
        "strict_harvest_completed_before_read", "original_result_commit",
        "prior_arm_disposition", "result_report", "aggregate", "cells",
        "launch", "preopen_material", "closure_implementation",
        "executions", "objects", "cell_rerun_licensed",
        "scientific_retest_licensed", "production_change_licensed",
        "shadow_adoption_licensed", "a3_result_transport_to_a7_licensed",
        "closed_at",
    }
    if set(closure) != expected_keys:
        raise RuntimeError("A3 recovery closure fields differ")
    if closure.get("version") != \
            "stack-relaxation-carve-post-open-forensic-closure-v1" or \
            closure.get("run_id") != RUN_ID or \
            closure.get("status") != "post-open-forensic-closure-complete" or \
            closure.get("closure_mode") != \
            "post-open-forensic-provenance-recovery" or \
            closure.get("original_result_commit") != RESULT_COMMIT or \
            closure.get("prior_arm_disposition") != \
            "negative-closed-at-this-dose" or \
            closure.get("protocol_deviation_disclosed") is not True or \
            closure.get("scientific_result_opened_before_strict_harvest") is not True or \
            closure.get("recovery_reads_already_opened_realized_outcomes") is not True or \
            closure.get("strict_harvest_completed_before_read") is not False:
        raise RuntimeError("A3 recovery closure identity differs")
    for key in (
        "cell_rerun_licensed", "scientific_retest_licensed",
        "production_change_licensed", "shadow_adoption_licensed",
        "a3_result_transport_to_a7_licensed",
    ):
        if closure.get(key) is not False:
            raise RuntimeError("A3 recovery closure license differs")
    expected_nested = {
        "result_report": {
            "path": str(RESULT_REPORT.relative_to(ROOT)),
            "sha256": RESULT_REPORT_SHA256,
        },
        "aggregate": {
            "path": str((out / "aggregate-report.json").relative_to(ROOT)),
            "sha256": AGGREGATE_SHA256,
            "bytes": (out / "aggregate-report.json").stat().st_size,
            "recomputed_byte_identical": True,
        },
        "cells": {
            "count": 54,
            "ledger_sha256": _sha(closure_dir / "cells.sha256"),
            "git_byte_identity": True,
            "remote_generation_byte_identity": True,
        },
        "launch": {
            "manifest_sha256": strict.FROZEN.original_manifest_sha256,
            "execution_ledger_sha256": strict.FROZEN.execution_ledger_sha256,
            "launch_receipt_sha256": strict.FROZEN.launch_receipt_sha256,
        },
        "preopen_material": {
            "finisher_sha256": STRICT_FINISHER_SHA256,
            "tests_sha256": STRICT_TEST_SHA256,
            "addendum_sha256": PREOPEN_ADDENDUM_SHA256,
            "was_untracked_at_result_commit": True,
        },
        "executions": {
            "count": 54,
            "metadata_ledger_sha256": _sha(
                closure_dir / "execution-metadata.sha256"
            ),
            "all_strict_terminal": True,
        },
        "objects": {
            "count": 54,
            "metadata_ledger_sha256": _sha(
                closure_dir / "object-metadata.sha256"
            ),
            "exact_inventory": True,
            "generation_pinned": True,
        },
    }
    if any(_canonical(closure.get(key)) != _canonical(value)
           for key, value in expected_nested.items()):
        raise RuntimeError("A3 recovery closure evidence differs")
    if implementation is not None and \
            _canonical(closure.get("closure_implementation")) != \
            _canonical(implementation):
        raise RuntimeError("A3 recovery closure implementation differs")
    _utc_timestamp(closure.get("closed_at"), label="closure timestamp")
    expected_finish = {
        "cells.sha256", "execution-metadata.sha256",
        "object-metadata.sha256", "closure.json",
    }
    _validate_ledger(
        closure_dir / "closure.sha256", base=closure_dir,
        expected=expected_finish,
    )
    return closure


def _lease_absence() -> dict[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", LEASE_URI)
    assert match is not None
    client = storage.Client(project=strict.PROJECT)
    blob = client.bucket(match.group(1)).blob(match.group(2))
    try:
        blob.reload()
    except NotFound:
        return {
            "uri": LEASE_URI,
            "state": "absent",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        raise RuntimeError(
            "A3 recovery historical-outcome lease absence is ambiguous"
        ) from exc
    raise RuntimeError("A3 recovery historical-outcome lease is present")


def _release_body(
    *, closure: dict[str, Any], closure_sha: str,
    lease: dict[str, str], released_at: str,
) -> dict[str, Any]:
    if set(lease) != {"uri", "state", "checked_at"} or \
            lease.get("uri") != LEASE_URI or lease.get("state") != "absent" or \
            not lease.get("checked_at"):
        raise RuntimeError("A3 recovery lease absence attestation differs")
    return {
        "version": "stack-relaxation-carve-logical-release-v2",
        "run_id": RUN_ID,
        "status": (
            "released-for-next-historical-arm-after-post-open-forensic-closure"
        ),
        "next_run_id": NEXT_RUN_ID,
        "closure_mode": "post-open-forensic-provenance-recovery",
        "strict_harvest_completed_before_read": False,
        "post_open_forensic_closure_complete": True,
        "forensic_closure_sha256": closure_sha,
        "forensic_closure_receipt": closure,
        "original_result_commit": RESULT_COMMIT,
        "aggregate_sha256": AGGREGATE_SHA256,
        "result_report_sha256": RESULT_REPORT_SHA256,
        "prior_arm_disposition": "negative-closed-at-this-dose",
        "historical_outcome_lease_clear": True,
        "historical_outcome_lease_state": "absent",
        "historical_outcome_lease_absence_checked_at": lease["checked_at"],
        "operator_approved": True,
        "released_at": released_at,
        "cell_rerun_licensed": False,
        "scientific_retest_licensed": False,
        "production_change_licensed": False,
        "shadow_adoption_licensed": False,
        "a3_result_transport_to_a7_licensed": False,
    }


def _validate_release_value(
    out: Path, release: dict[str, Any], *,
    implementation: dict[str, str] | None = None,
) -> dict[str, Any]:
    closure_sha = _sha(out / CLOSURE_NAME / "closure.json")
    expected_keys = {
        "version", "run_id", "status", "next_run_id", "closure_mode",
        "strict_harvest_completed_before_read",
        "post_open_forensic_closure_complete", "forensic_closure_sha256",
        "forensic_closure_receipt",
        "original_result_commit", "aggregate_sha256", "result_report_sha256",
        "prior_arm_disposition", "historical_outcome_lease_clear",
        "historical_outcome_lease_state",
        "historical_outcome_lease_absence_checked_at", "operator_approved",
        "released_at", "cell_rerun_licensed", "scientific_retest_licensed",
        "production_change_licensed", "shadow_adoption_licensed",
        "a3_result_transport_to_a7_licensed",
    }
    if set(release) != expected_keys:
        raise RuntimeError("A3 recovery logical release fields differ")
    embedded = release.get("forensic_closure_receipt")
    if not isinstance(embedded, dict) or \
            _canonical(embedded) != (out / CLOSURE_NAME / "closure.json").read_bytes():
        raise RuntimeError("A3 recovery embedded forensic closure differs")
    exact = {
        "version": "stack-relaxation-carve-logical-release-v2",
        "run_id": RUN_ID,
        "status": (
            "released-for-next-historical-arm-after-post-open-forensic-closure"
        ),
        "next_run_id": NEXT_RUN_ID,
        "closure_mode": "post-open-forensic-provenance-recovery",
        "strict_harvest_completed_before_read": False,
        "post_open_forensic_closure_complete": True,
        "forensic_closure_sha256": closure_sha,
        "forensic_closure_receipt": _validate_closure(
            out, implementation=implementation,
        ),
        "original_result_commit": RESULT_COMMIT,
        "aggregate_sha256": AGGREGATE_SHA256,
        "result_report_sha256": RESULT_REPORT_SHA256,
        "prior_arm_disposition": "negative-closed-at-this-dose",
        "historical_outcome_lease_clear": True,
        "historical_outcome_lease_state": "absent",
        "operator_approved": True,
        "cell_rerun_licensed": False,
        "scientific_retest_licensed": False,
        "production_change_licensed": False,
        "shadow_adoption_licensed": False,
        "a3_result_transport_to_a7_licensed": False,
    }
    if any(_canonical(release.get(key)) != _canonical(value)
           for key, value in exact.items()):
        raise RuntimeError("A3 recovery logical release differs")
    closed_at = _utc_timestamp(
        embedded.get("closed_at"), label="embedded closure timestamp",
    )
    absence_at = _utc_timestamp(
        release.get("historical_outcome_lease_absence_checked_at"),
        label="lease absence timestamp",
    )
    released_at = _utc_timestamp(
        release.get("released_at"), label="logical release timestamp",
    )
    if not closed_at <= absence_at <= released_at:
        raise RuntimeError("A3 recovery logical release chronology differs")
    return release


def _validate_release(
    out: Path, *, implementation: dict[str, str] | None = None,
) -> dict[str, Any]:
    path = out / RELEASE_NAME
    release = _parse_json(path.read_bytes(), label="logical release")
    return _validate_release_value(
        out, release, implementation=implementation,
    )


def _validate_inventory_exact(
    inventory: Mapping[str, dict[str, Any]], cells: list[strict.Cell],
) -> dict[str, dict[str, Any]]:
    validated = strict._validate_inventory(inventory, cells)
    for cell in cells:
        metadata = inventory[cell.uri]
        generation = metadata.get("generation")
        size = metadata.get("size")
        if not isinstance(generation, str) or re.fullmatch(
            r"[1-9][0-9]*", generation,
        ) is None or metadata.get("metageneration") != "1" or \
                isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise RuntimeError(f"A3 recovery object metadata differs: {cell.uri}")
    return validated


def close(
    out: Path = DEFAULT_OUT, *, operator_approved: bool,
    execution_loader: ExecutionLoader | None = None,
    inventory_loader: InventoryLoader | None = None,
    downloader: Downloader | None = None,
    lease_absence_loader: LeaseAbsenceLoader = _lease_absence,
    git_loader: GitLoader = _git_blob,
) -> dict[str, Any]:
    if not operator_approved:
        raise RuntimeError("A3 recovery operator approval is required")
    cells, implementation = _validate_frozen_inputs(out, git_loader=git_loader)
    if (out / RELEASE_NAME).is_file():
        _validate_closure(out, implementation=implementation)
        return {
            "status": "already-released",
            "release": _validate_release(out, implementation=implementation),
        }
    final = out / CLOSURE_NAME
    pending = out / PENDING_NAME
    if final.exists() and pending.exists():
        raise RuntimeError("A3 recovery final and pending closure both exist")
    if final.is_dir():
        closure = _validate_closure(out, implementation=implementation)
    else:
        pending.mkdir(exist_ok=True)
        execution_dir = pending / "execution-metadata"
        object_dir = pending / "object-metadata"
        execution_dir.mkdir(exist_ok=True)
        object_dir.mkdir(exist_ok=True)
        if execution_loader is None:
            execution_loader = strict._execution_metadata
        reader: strict._StorageReader | None = None
        if inventory_loader is None or downloader is None:
            reader = strict._StorageReader()
        if inventory_loader is None:
            assert reader is not None
            inventory_loader = reader.inventory
        if downloader is None:
            assert reader is not None
            downloader = reader.download

        execution_values: dict[tuple[int, int], dict[str, Any]] = {}
        for cell in cells:
            metadata = execution_loader(cell.execution)
            _validate_execution_exact(metadata, cell, strict.FROZEN)
            execution_values[(cell.season, cell.week)] = metadata
        inventory = _validate_inventory_exact(
            inventory_loader(strict.FROZEN.output_prefix), cells,
        )

        # Body 1 is opened only after every execution and the exact inventory
        # have passed. Existing scientific bytes are compared, never written.
        harvested: list[tuple[strict.Cell, bytes, dict[str, Any]]] = []
        for cell in cells:
            remote = downloader(cell.uri, inventory[cell.uri])
            local = out / "cells" / cell.stem
            if remote != local.read_bytes():
                raise RuntimeError(
                    f"A3 recovery remote body differs from result commit: {cell.stem}"
                )
            receipt = strict._validate_cell(remote, cell, strict.FROZEN)
            harvested.append((cell, remote, receipt))
            _write_or_validate(
                execution_dir / cell.stem,
                _canonical(execution_values[(cell.season, cell.week)]),
            )
            _write_or_validate(
                object_dir / cell.stem, _canonical(inventory[cell.uri]),
            )
        rebuilt = strict._canonical_json(strict._aggregate(harvested, strict.FROZEN))
        if rebuilt != (out / "aggregate-report.json").read_bytes():
            raise RuntimeError("A3 recovery aggregate replay differs")

        cell_ledger = _cell_ledger(out, cells)
        exec_ledger = _hash_ledger(list(execution_dir.glob("*.json")), base=pending)
        object_ledger = _hash_ledger(list(object_dir.glob("*.json")), base=pending)
        _write_or_validate(pending / "cells.sha256", cell_ledger)
        _write_or_validate(pending / "execution-metadata.sha256", exec_ledger)
        _write_or_validate(pending / "object-metadata.sha256", object_ledger)
        closed_at = datetime.now(timezone.utc).isoformat()
        if (pending / "closure.json").is_file():
            closed_at = str(_parse_json(
                (pending / "closure.json").read_bytes(), label="pending closure",
            ).get("closed_at", ""))
        body = _completion_body(
            out=out, implementation=implementation,
            cell_ledger_sha=_sha_bytes(cell_ledger),
            execution_ledger_sha=_sha_bytes(exec_ledger),
            object_ledger_sha=_sha_bytes(object_ledger),
            closed_at=closed_at,
        )
        _write_or_validate(pending / "closure.json", _canonical(body))
        finish_sources = [
            pending / "cells.sha256", pending / "execution-metadata.sha256",
            pending / "object-metadata.sha256", pending / "closure.json",
        ]
        _write_or_validate(
            pending / "closure.sha256", _hash_ledger(finish_sources, base=pending),
        )
        _validate_evidence_inventory(pending)
        pending.rename(final)
        closure = _validate_closure(out, implementation=implementation)

    lease = lease_absence_loader()
    release = _release_body(
        closure=closure, closure_sha=_sha(final / "closure.json"), lease=lease,
        released_at=datetime.now(timezone.utc).isoformat(),
    )
    _validate_release_value(out, release, implementation=implementation)
    _write_or_validate(out / RELEASE_NAME, _canonical(release))
    validated = _validate_release(out, implementation=implementation)
    print(
        "STACK_RELAXATION_CARVE_POST_OPEN_CLOSED",
        f"run_id={RUN_ID}", f"closure_sha256={_sha(final / 'closure.json')}",
    )
    return {"status": "released", "closure": closure, "release": validated}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--operator-approved", action="store_true")
    args = parser.parse_args()
    close(args.output_dir, operator_approved=args.operator_approved)


if __name__ == "__main__":
    main()
