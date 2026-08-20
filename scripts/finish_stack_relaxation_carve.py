#!/usr/bin/env python3
"""Strict, ledger-only harvest for the frozen A3 stack-relaxation grid.

This program has no launch, retry, deploy, cancel, BigQuery, or upload path.
It proves the frozen 54-execution population and exact GCS object inventory
before downloading any scientific body.  A create-once provenance addendum
binds the launcher's incorrect chain-source receipt to the actual source and
pins this mechanical finisher before the first result body is opened.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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

from google.cloud import storage


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research.paired_max_stats import (  # noqa: E402
    paired_weekly_max_report,
)


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
RUN_ID = "20260819-stack-relaxation-carve-v1"
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    f"stack-relaxation-carve-runs/{RUN_ID}"
)
DEFAULT_OUT = ROOT / "reports/stack-relaxation-carve-runs" / RUN_ID
DEFAULT_PROVENANCE = (
    ROOT / "reports/2026-08-20-stack-relaxation-carve-provenance-addendum.json"
)
PENDING_NAME = ".strict-harvest.pending"


@dataclass(frozen=True)
class FrozenRun:
    run_id: str = RUN_ID
    output_prefix: str = PREFIX
    code_sha: str = "5ced3d3f7fed83a3a5f68670c946b0f70bf3ece2"
    image: str = (
        "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
        "nfl-dfs@sha256:"
        "0bee6350966981985ae1721454c1a7753e2ca7a9278cac43fd2cd8a52b90ee47"
    )
    build_id: str = "7b638c3f-3327-411d-adcb-222c77efcfdf"
    protocol_sha256: str = (
        "3bc1ace97dc0eb5120a16e961aad2d84f4258f008c1f3a9da8a7f5c80866e7bf"
    )
    runner_sha256: str = (
        "4f1df879dff94523d628d7d6d57c81d45d8cc0cfcb87c15c794c3e7d1620698d"
    )
    upload_helper_sha256: str = (
        "b32cdf8d0d8d342640a05f92f17e6d8a2f8f0ae554aab00c1454c43071695c00"
    )
    recorded_chain_sha256: str = (
        "585b0edee9f4eadc876a5446930c2bbff046af11886c3a5e74cb9d4bdf684f51"
    )
    actual_chain_sha256: str = (
        "ab2771312423596594afc93db09662818bb80c1eb545930d5209c9883b170731"
    )
    original_manifest_sha256: str = (
        "6d822d6434aff3f16e00ac7e78216bcf583558abedbe93b0372683ba12edcbe7"
    )
    execution_ledger_sha256: str = (
        "8355974533586b549ba11bca0302b7ebc3ae792094283bb40645e7c6841ebc6f"
    )
    launch_receipt_sha256: str = (
        "8f883eed18dad935459f211bcd821a8dacadde284e6c4d9170ac5e6bb399df5b"
    )
    job: str = "atlas-minimal-c-s2023-w1-v1"
    job_uid: str = "d6e4b8c1-5950-46b7-8869-7e34dbf29ad2"
    job_generation: str = "8"
    service_account: str = (
        "817589974517-compute@developer.gserviceaccount.com"
    )


FROZEN = FrozenRun()


@dataclass(frozen=True)
class Cell:
    season: int
    week: int
    job: str
    execution: str
    uri: str

    @property
    def stem(self) -> str:
        return f"slate-{self.season}-{self.week}.json"


ExecutionLoader = Callable[[str], dict[str, Any]]
InventoryLoader = Callable[[str], Mapping[str, dict[str, Any]]]
Downloader = Callable[[str, dict[str, Any]], bytes]
GitSourceLoader = Callable[[Path, str, str], bytes]


def _sha_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"A3 {label} is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"A3 {label} is not an object: {path}")
    return value


def _read_manifest(path: Path) -> dict[str, str]:
    rows = [line for line in path.read_text(encoding="utf-8").splitlines()]
    if any("=" not in line for line in rows) or not rows:
        raise RuntimeError("A3 launch manifest differs")
    pairs = [line.split("=", 1) for line in rows]
    if len({key for key, _ in pairs}) != len(pairs):
        raise RuntimeError("A3 launch manifest contains duplicate keys")
    return dict(pairs)


def _read_ledger(path: Path, frozen: FrozenRun) -> list[Cell]:
    raw_rows = path.read_text(encoding="utf-8").splitlines()
    if len(raw_rows) != 54 or any(not line.strip() for line in raw_rows):
        raise RuntimeError("A3 execution ledger is not exact 54")
    cells: list[Cell] = []
    for line in raw_rows:
        fields = line.split()
        if len(fields) != 5:
            raise RuntimeError("A3 execution ledger row differs")
        season, week, job, execution, uri = fields
        if not season.isdigit() or not week.isdigit():
            raise RuntimeError("A3 execution ledger cell differs")
        cells.append(Cell(int(season), int(week), job, execution, uri))
    expected = [(season, week) for season in (2023, 2024, 2025)
                for week in range(1, 19)]
    if [(cell.season, cell.week) for cell in cells] != expected:
        raise RuntimeError("A3 execution ledger lattice differs")
    if len({cell.execution for cell in cells}) != 54 or \
            len({cell.uri for cell in cells}) != 54:
        raise RuntimeError("A3 execution ledger identity is not unique")
    for cell in cells:
        expected_uri = (
            f"{frozen.output_prefix}/slate-{cell.season}-{cell.week}.json"
        )
        if cell.job != frozen.job or \
                not cell.execution.startswith(frozen.job + "-") or \
                cell.uri != expected_uri:
            raise RuntimeError("A3 execution ledger binding differs")
    return cells


def _parse_checksum_ledger(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise RuntimeError(f"A3 checksum ledger differs: {path}")
        rows.append((match.group(1), match.group(2)))
    if not rows:
        raise RuntimeError(f"A3 checksum ledger is empty: {path}")
    return rows


def _validate_launch_receipt(
    out: Path, manifest_path: Path, ledger_path: Path, frozen: FrozenRun,
) -> None:
    receipt = out / "launch.sha256"
    if not receipt.is_file() or _sha(receipt) != frozen.launch_receipt_sha256:
        raise RuntimeError("A3 launch checksum receipt differs")
    rows = _parse_checksum_ledger(receipt)
    expected = {
        str(manifest_path.resolve()): frozen.original_manifest_sha256,
        str(ledger_path.resolve()): frozen.execution_ledger_sha256,
    }
    got = {str(Path(name).resolve()): digest for digest, name in rows}
    if got != expected:
        raise RuntimeError("A3 launch checksum bindings differ")
    for name, digest in got.items():
        if _sha(Path(name)) != digest:
            raise RuntimeError("A3 launch source changed after receipt")


def _git_blob(root: Path, code_sha: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), "show", f"{code_sha}:{relative}"],
        check=True, capture_output=True,
    ).stdout


def _validate_provenance(
    *, root: Path, manifest: dict[str, str],
    provenance_path: Path, frozen: FrozenRun,
    git_source_loader: GitSourceLoader,
) -> bytes:
    addendum = _load_json(provenance_path, label="provenance addendum")
    fixed: dict[str, object] = {
        "version": "stack-relaxation-carve-provenance-addendum-v1",
        "run_id": frozen.run_id,
        "attestation_scope": (
            "mechanical-source-identity-correction-before-scientific-harvest"
        ),
        "original_manifest_sha256": frozen.original_manifest_sha256,
        "original_execution_ledger_sha256": frozen.execution_ledger_sha256,
        "original_launch_receipt_sha256": frozen.launch_receipt_sha256,
        "code_sha": frozen.code_sha,
        "build_id": frozen.build_id,
        "image": frozen.image,
        "protocol_sha256": frozen.protocol_sha256,
        "runner_sha256": frozen.runner_sha256,
        "upload_helper_sha256": frozen.upload_helper_sha256,
        "manifest_recorded_chain_path": "scripts/cloud_all_boom_s_chain.sh",
        "manifest_recorded_chain_sha256": frozen.recorded_chain_sha256,
        "actual_chain_path": "scripts/cloud_stack_carve_chain.sh",
        "actual_chain_sha256": frozen.actual_chain_sha256,
        "actual_chain_at_code_sha256": frozen.actual_chain_sha256,
        "finisher_path": "scripts/finish_stack_relaxation_carve.py",
        "aggregation_source": "scripts/cloud_stack_carve_chain.sh:144-232",
        "correction_is_metadata_only": True,
        "cell_rerun_licensed": False,
        "scientific_result_body_inspected_before_freeze": False,
        "watcher_stopped_before_harvest": True,
        "cloud_execution_cancelled": False,
        "aggregate_preexisting": False,
        "historical_outcome_lease_object_present_during_audit": False,
        "logical_outcome_lane_remains_occupied_until_strict_harvest": True,
        "uploaded_body_contains_upload_receipt": False,
        "production_change_licensed": False,
    }
    if set(addendum) != set(fixed) | {"finisher_sha256"} or \
            any(addendum.get(key) != value for key, value in fixed.items()) or \
            addendum.get("finisher_sha256") != _sha(Path(__file__)):
        raise RuntimeError("A3 provenance addendum differs")
    source_bindings = {
        "reports/2026-08-19-stack-relaxation-carve-protocol.md":
            frozen.protocol_sha256,
        "scripts/run_stack_relaxation_carve.py": frozen.runner_sha256,
        "scripts/run_cbwu_seed_order_audit.py": frozen.upload_helper_sha256,
        "scripts/cloud_all_boom_s_chain.sh": frozen.recorded_chain_sha256,
        "scripts/cloud_stack_carve_chain.sh": frozen.actual_chain_sha256,
    }
    for relative, expected in source_bindings.items():
        local = root / relative
        if not local.is_file() or _sha(local) != expected:
            raise RuntimeError(f"A3 frozen source differs: {relative}")
        committed = git_source_loader(root, frozen.code_sha, relative)
        if _sha_bytes(committed) != expected:
            raise RuntimeError(f"A3 committed source differs: {relative}")
    if manifest.get("chain_sha256") != frozen.recorded_chain_sha256:
        raise RuntimeError("A3 recorded chain defect differs from addendum")
    raw = provenance_path.read_bytes()
    if not raw:
        raise RuntimeError("A3 provenance addendum is empty")
    return raw


def _validate_sources(
    out: Path, provenance_path: Path, frozen: FrozenRun,
    *, root: Path, git_source_loader: GitSourceLoader,
) -> tuple[dict[str, str], list[Cell], bytes]:
    manifest_path = out / "manifest.txt"
    ledger_path = out / "executions.txt"
    if not manifest_path.is_file() or not ledger_path.is_file():
        raise RuntimeError("A3 launch receipt is incomplete")
    if _sha(manifest_path) != frozen.original_manifest_sha256 or \
            _sha(ledger_path) != frozen.execution_ledger_sha256:
        raise RuntimeError("A3 immutable launch receipt differs")
    manifest = _read_manifest(manifest_path)
    expected_manifest = {
        "run_id": frozen.run_id,
        "image": frozen.image,
        "code_sha": frozen.code_sha,
        "build_id": frozen.build_id,
        "output_prefix": frozen.output_prefix,
        "protocol_sha256": frozen.protocol_sha256,
        "runner_sha256": frozen.runner_sha256,
        "chain_sha256": frozen.recorded_chain_sha256,
        "quota_note": f"reused job {frozen.job} (frozen-chain rule 5)",
        "uses_realized_outcomes": "true",
        "production_change_licensed": "false",
        "predeclared_prior": "uncertain-modest-dose",
        "cells": "54",
        "canary": "2023-1",
    }
    if manifest != expected_manifest:
        raise RuntimeError("A3 launch manifest differs")
    cells = _read_ledger(ledger_path, frozen)
    _validate_launch_receipt(out, manifest_path, ledger_path, frozen)
    provenance_raw = _validate_provenance(
        root=root, manifest=manifest,
        provenance_path=provenance_path, frozen=frozen,
        git_source_loader=git_source_loader,
    )
    return manifest, cells, provenance_raw


def _execution_metadata(name: str) -> dict[str, Any]:
    raw = subprocess.run([
        "gcloud", "run", "jobs", "executions", "describe", name,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ], check=True, text=True, capture_output=True).stdout
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError("A3 execution metadata is not an object")
    return value


def _as_count(value: object) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("A3 execution counter is malformed") from exc


def _validate_execution(
    metadata: dict[str, Any], cell: Cell, frozen: FrozenRun,
) -> None:
    meta = metadata.get("metadata", {})
    labels = meta.get("labels", {})
    status = metadata.get("status", {})
    conditions = status.get("conditions", [])
    completed = [row for row in conditions if row.get("type") == "Completed"]
    generation = meta.get("generation")
    if meta.get("name") != cell.execution or generation != 1 or \
            labels.get("run.googleapis.com/job") != cell.job or \
            labels.get("run.googleapis.com/jobUid") != frozen.job_uid or \
            labels.get("run.googleapis.com/jobGeneration") != \
            frozen.job_generation or status.get("observedGeneration") != 1:
        raise RuntimeError(f"A3 execution identity differs: {cell.execution}")
    if len(completed) != 1 or completed[0].get("status") != "True" or \
            _as_count(status.get("succeededCount")) != 1 or \
            _as_count(status.get("failedCount")) != 0 or \
            _as_count(status.get("cancelledCount")) != 0 or \
            _as_count(status.get("retriedCount")) != 0 or \
            not status.get("completionTime"):
        raise RuntimeError(
            f"A3 execution is not strict terminal success: {cell.execution}"
        )
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError(f"A3 execution task shape differs: {cell.execution}")
    container = containers[0]
    env_rows = container.get("env", [])
    env = {row.get("name"): str(row.get("value", "")) for row in env_rows}
    expected_args = [
        "scripts/run_stack_relaxation_carve.py",
        "--season", str(cell.season), "--week", str(cell.week),
        "--output-uri", cell.uri,
    ]
    if len(env) != len(env_rows) or env != {
        "CODE_SHA": frozen.code_sha, "ANALYSIS_IMAGE": frozen.image,
    } or container.get("image") != frozen.image or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or \
            container.get("resources", {}).get("limits") != {
                "cpu": "4", "memory": "16Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "7200" or \
            task.get("serviceAccountName") != frozen.service_account:
        raise RuntimeError(
            f"A3 execution contract differs: {cell.execution}"
        )


def _gcs_parts(uri: str) -> tuple[str, str]:
    match = re.fullmatch(r"gs://([^/]+)/(.+)", uri)
    if match is None:
        raise RuntimeError("A3 GCS URI differs")
    return match.group(1), match.group(2)


class _StorageReader:
    def __init__(self) -> None:
        self.client = storage.Client(project=PROJECT)

    def inventory(self, prefix: str) -> dict[str, dict[str, Any]]:
        bucket_name, object_prefix = _gcs_parts(prefix)
        stem = object_prefix.rstrip("/") + "/"
        result: dict[str, dict[str, Any]] = {}
        for blob in self.client.list_blobs(bucket_name, prefix=stem):
            blob.reload()
            uri = f"gs://{bucket_name}/{blob.name}"
            if uri in result:
                raise RuntimeError("A3 live object inventory contains duplicates")
            result[uri] = {
                "uri": uri,
                "generation": str(blob.generation or ""),
                "metageneration": str(blob.metageneration or ""),
                "size": int(blob.size or 0),
                "md5_hash": str(blob.md5_hash or ""),
                "crc32c": str(blob.crc32c or ""),
                "etag": str(blob.etag or ""),
                "time_created": (
                    blob.time_created.isoformat() if blob.time_created else ""
                ),
                "updated": blob.updated.isoformat() if blob.updated else "",
            }
        return result

    def download(self, uri: str, metadata: dict[str, Any]) -> bytes:
        bucket_name, name = _gcs_parts(uri)
        generation = int(str(metadata["generation"]))
        blob = self.client.bucket(bucket_name).blob(name, generation=generation)
        raw = blob.download_as_bytes(if_generation_match=generation)
        blob.reload(if_generation_match=generation)
        if str(blob.generation) != str(metadata["generation"]) or \
                str(blob.metageneration) != str(metadata["metageneration"]) or \
                int(blob.size or -1) != int(metadata["size"]) or \
                len(raw) != int(metadata["size"]):
            raise RuntimeError(f"A3 object changed during download: {uri}")
        return raw


def _validate_inventory(
    inventory: Mapping[str, dict[str, Any]], cells: list[Cell],
) -> dict[str, dict[str, Any]]:
    expected = {cell.uri for cell in cells}
    if set(inventory) != expected:
        missing = sorted(expected - set(inventory))
        extra = sorted(set(inventory) - expected)
        raise RuntimeError(
            f"A3 live object inventory differs: missing={len(missing)} "
            f"extra={len(extra)}"
        )
    validated: dict[str, dict[str, Any]] = {}
    for cell in cells:
        value = dict(inventory[cell.uri])
        generation = str(value.get("generation", ""))
        metageneration = str(value.get("metageneration", ""))
        try:
            size = int(value.get("size", 0))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"A3 object size differs: {cell.uri}") from exc
        if value.get("uri") != cell.uri or not generation.isdigit() or \
                metageneration != "1" or size <= 0:
            raise RuntimeError(f"A3 object metadata differs: {cell.uri}")
        value["generation"] = generation
        value["metageneration"] = metageneration
        value["size"] = size
        validated[cell.uri] = value
    return validated


def _finite(value: object, *, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"A3 cell {label} is not numeric") from exc
    if not math.isfinite(number):
        raise RuntimeError(f"A3 cell {label} is not finite")
    return number


def _validate_arm(arm: object, *, recovery: bool, label: str) -> dict[str, Any]:
    if not isinstance(arm, dict):
        raise RuntimeError(f"A3 cell {label} arm differs")
    _finite(arm.get("c_score"), label=f"{label}.c_score")
    _finite(arm.get("pool_mean"), label=f"{label}.pool_mean")
    if not isinstance(arm.get("pool_unique"), int) or arm["pool_unique"] <= 0:
        raise RuntimeError(f"A3 cell {label}.pool_unique differs")
    if recovery:
        if arm.get("s_score") is not None or \
                arm.get("selected_mean") is not None or \
                arm.get("four_seed_recovery") is not True:
            raise RuntimeError(f"A3 recovery {label} endpoint differs")
    else:
        _finite(arm.get("s_score"), label=f"{label}.s_score")
        _finite(arm.get("selected_mean"), label=f"{label}.selected_mean")
        if arm.get("four_seed_recovery") is not None:
            raise RuntimeError(f"A3 non-recovery {label} marker differs")
    thresholds = arm.get("thresholds")
    expected_lines = {str(line) for line in (187, 194, 200, 210, 220, 230, 240)}
    if not isinstance(thresholds, dict) or set(thresholds) != expected_lines or \
            any(not isinstance(value, int) or value < 0
                for value in thresholds.values()):
        raise RuntimeError(f"A3 cell {label} threshold receipt differs")
    return arm


def _validate_cell(raw: bytes, cell: Cell, frozen: FrozenRun) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"A3 cell body is invalid JSON: {cell.stem}") from exc
    if not isinstance(value, dict) or \
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode() != raw:
        raise RuntimeError(f"A3 cell body is not canonical: {cell.stem}")
    fixed = {
        "version": "stack-relaxation-carve-v1",
        "run_id": frozen.run_id,
        "season": cell.season,
        "week": cell.week,
        "code_sha": frozen.code_sha,
        "image": frozen.image,
        "protocol_sha256": frozen.protocol_sha256,
        "treatment_levers": {"OPEN_BOOM_SOLVES": "8"},
        "smoke": False,
        "uses_realized_outcomes": True,
        "production_change_licensed": False,
        "cross_run_reproduction": True,
    }
    if any(value.get(key) != expected for key, expected in fixed.items()) or \
            "upload" in value:
        raise RuntimeError(f"A3 cell identity differs: {cell.stem}")
    recovery = (cell.season, cell.week) == (2025, 1)
    if value.get("recovery_four_seed_slate") is not (True if recovery else None):
        raise RuntimeError(f"A3 recovery marker differs: {cell.stem}")
    seeds = value.get("seeds")
    expected_blocks = [0, 1, 2, 4] if recovery else [0, 1, 2, 3, 4]
    if not isinstance(seeds, list) or \
            [seed.get("block") for seed in seeds
             if isinstance(seed, dict)] != expected_blocks or \
            len(seeds) != len(expected_blocks):
        raise RuntimeError(f"A3 seed population differs: {cell.stem}")
    open_total = 0
    for seed in seeds:
        reproduction = seed.get("reproduction")
        census = seed.get("open_census")
        artifact = seed.get("artifact")
        if not isinstance(reproduction, dict) or \
                reproduction.get("mode") != \
                "bq-identities-and-artifact-totals" or \
                _finite(reproduction.get("max_total_delta"),
                        label="reproduction.max_total_delta") > 1e-6 or \
                not isinstance(census, dict) or \
                not isinstance(census.get("n"), int) or census["n"] < 0 or \
                not isinstance(artifact, dict) or \
                not str(artifact.get("generation", "")).isdigit() or \
                not isinstance(artifact.get("bytes"), int) or \
                artifact["bytes"] <= 0 or \
                not re.fullmatch(r"[0-9a-f]{64}",
                                 str(artifact.get("sha256", ""))):
            raise RuntimeError(f"A3 seed receipt differs: {cell.stem}")
        generated = reproduction.get("generated_candidates")
        registered = reproduction.get("registered_candidates")
        artifact_n = reproduction.get("artifact_candidates")
        if not all(isinstance(item, int) and item > 0
                   for item in (generated, registered, artifact_n)) or \
                generated != registered or generated != artifact_n or \
                seed.get("native_count") != registered or \
                seed.get("treatment_count") != generated or \
                not isinstance(seed.get("shortfall"), int) or \
                seed["shortfall"] < 0:
            raise RuntimeError(f"A3 seed budget receipt differs: {cell.stem}")
        open_total += census["n"]
    if open_total <= 0 or value.get("open_candidates_total") != open_total:
        raise RuntimeError(f"A3 open-candidate gate differs: {cell.stem}")
    if abs(_finite(value.get("actual_parity_max_delta"),
                   label="actual_parity_max_delta")) > 1e-9:
        raise RuntimeError(f"A3 actual parity differs: {cell.stem}")
    control = _validate_arm(value.get("control"), recovery=recovery,
                            label="control")
    treatment = _validate_arm(value.get("treatment"), recovery=recovery,
                              label="treatment")
    delta_c = _finite(value.get("paired_delta_c"), label="paired_delta_c")
    if abs(delta_c - (
        float(treatment["c_score"]) - float(control["c_score"])
    )) > 1e-9:
        raise RuntimeError(f"A3 paired C delta differs: {cell.stem}")
    if recovery:
        if "paired_delta_s" in value or \
                "selected_book_intersection" in value or \
                "open_selected_count" in value:
            raise RuntimeError(f"A3 recovery selection receipt differs: {cell.stem}")
    else:
        delta_s = _finite(value.get("paired_delta_s"), label="paired_delta_s")
        if abs(delta_s - (
            float(treatment["s_score"]) - float(control["s_score"])
        )) > 1e-9 or \
                not isinstance(value.get("selected_book_intersection"), int) or \
                not 0 <= value["selected_book_intersection"] <= 80 or \
                not isinstance(value.get("open_selected_count"), int) or \
                not 0 <= value["open_selected_count"] <= 80:
            raise RuntimeError(f"A3 selected-book receipt differs: {cell.stem}")
    winner_overlap = value.get("winner_overlap")
    if winner_overlap is not None:
        if not isinstance(winner_overlap, dict) or \
                not {"control", "treatment"} <= set(winner_overlap):
            raise RuntimeError(f"A3 winner-overlap receipt differs: {cell.stem}")
        for arm in ("control", "treatment"):
            block = winner_overlap[arm]
            if not isinstance(block, dict):
                raise RuntimeError(
                    f"A3 winner-overlap arm differs: {cell.stem}"
                )
            _finite(block.get("max_minus_null"),
                    label=f"winner_overlap.{arm}.max_minus_null")
    return value


def _aggregate(
    cells: list[tuple[Cell, bytes, dict[str, Any]]], frozen: FrozenRun,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    control_s: list[float] = []
    treatment_s: list[float] = []
    overlap: dict[str, list[float]] = {"control": [], "treatment": []}
    # Preserve the original launcher's lexical path order exactly.
    for cell, raw, receipt in sorted(cells, key=lambda row: row[0].stem):
        row = {
            "season": cell.season,
            "week": cell.week,
            "paired_delta_c": float(receipt["paired_delta_c"]),
            "control": receipt["control"],
            "treatment": receipt["treatment"],
            "selected_book_intersection": receipt.get(
                "selected_book_intersection"
            ),
            "winner_overlap": receipt.get("winner_overlap"),
            "open_candidates_total": receipt.get("open_candidates_total"),
            "open_selected_count": receipt.get("open_selected_count"),
            "open_census": [seed.get("open_census")
                            for seed in receipt.get("seeds", [])],
            "sha256": _sha_bytes(raw),
        }
        if receipt.get("paired_delta_s") is not None:
            row["paired_delta_s"] = float(receipt["paired_delta_s"])
            control_s.append(float(receipt["control"]["s_score"]))
            treatment_s.append(float(receipt["treatment"]["s_score"]))
            winner = receipt.get("winner_overlap") or {}
            for arm in ("control", "treatment"):
                if arm in winner:
                    overlap[arm].append(float(winner[arm]["max_minus_null"]))
        rows.append(row)
    if len(rows) != 54 or len(control_s) != 53:
        raise RuntimeError("A3 aggregate population differs")
    coprimary = paired_weekly_max_report(control_s, treatment_s)
    deltas = [treatment - control
              for control, treatment in zip(control_s, treatment_s)]
    return {
        "run_id": frozen.run_id,
        "predeclared_prior": "favorable-c-cleared-s-uncertain",
        "uses_realized_outcomes": True,
        "production_change_licensed": False,
        "n_slates": len(rows),
        "n_paired_s": len(deltas),
        "mean_paired_delta_s": sum(deltas) / len(deltas),
        "treatment_better_s": sum(delta > 0 for delta in deltas),
        "control_better_s": sum(delta < 0 for delta in deltas),
        "tied_s": sum(delta == 0 for delta in deltas),
        "mean_control_s": sum(control_s) / len(control_s),
        "mean_treatment_s": sum(treatment_s) / len(treatment_s),
        "selected_threshold_grid": {
            str(line): {
                "control": sum(score >= line for score in control_s),
                "treatment": sum(score >= line for score in treatment_s),
            }
            for line in (187, 194, 200, 210, 220, 230, 240)
        },
        "coprimary": coprimary,
        "winner_overlap_max_minus_null_mean": {
            arm: (sum(values) / len(values) if values else None)
            for arm, values in overlap.items()
        },
        "open_candidates_total": sum(
            row.get("open_candidates_total") or 0 for row in rows
        ),
        "open_selected_total": sum(
            row.get("open_selected_count") or 0 for row in rows
        ),
        "slates_with_open_in_book": sum(
            1 for row in rows if (row.get("open_selected_count") or 0) > 0
        ),
        "per_slate": rows,
    }


def _write_new(path: Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o644)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)


def _hash_ledger(paths: list[Path], *, base: Path) -> bytes:
    return "".join(
        f"{_sha(path)}  {path.relative_to(base)}\n" for path in sorted(paths)
    ).encode()


def _validate_hash_ledger(path: Path, *, base: Path, expected: set[str]) -> None:
    rows = _parse_checksum_ledger(path)
    if {name for _, name in rows} != expected or len(rows) != len(expected):
        raise RuntimeError(f"A3 completed checksum population differs: {path.name}")
    for digest, name in rows:
        candidate = base / name
        try:
            candidate.resolve().relative_to(base.resolve())
        except ValueError as exc:
            raise RuntimeError("A3 checksum path escapes the run directory") from exc
        if not candidate.is_file() or _sha(candidate) != digest:
            raise RuntimeError(f"A3 completed artifact differs: {name}")


def _validate_complete(out: Path) -> dict[str, Any]:
    expected_cells = {
        f"cells/slate-{season}-{week}.json"
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    expected_exec = {
        f"execution-metadata/slate-{season}-{week}.json"
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    expected_objects = {
        f"object-metadata/slate-{season}-{week}.json"
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    for name, expected in (
        ("cells.sha256", expected_cells),
        ("execution-metadata.sha256", expected_exec),
        ("object-metadata.sha256", expected_objects),
    ):
        _validate_hash_ledger(out / name, base=out, expected=expected)
    finish_expected = {
        "manifest.txt", "executions.txt", "launch.sha256",
        "provenance-addendum.json", "cells.sha256",
        "execution-metadata.sha256", "object-metadata.sha256",
        "aggregate-report.json", "completion.txt",
    }
    _validate_hash_ledger(
        out / "finish.sha256", base=out, expected=finish_expected,
    )
    completion = dict(
        line.split("=", 1)
        for line in (out / "completion.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        if "=" in line
    )
    if completion.get("run_id") != RUN_ID or \
            completion.get("disposition") != \
            "strict-harvest-complete-awaiting-preregistered-read" or \
            completion.get("executions") != "54" or \
            completion.get("objects") != "54" or \
            completion.get("scientific_bodies") != "54" or \
            completion.get("uses_realized_outcomes") != "true" or \
            completion.get("production_change_licensed") != "false" or \
            completion.get("cell_rerun_licensed") != "false" or \
            completion.get("historical_outcome_lease_released") != "false" or \
            completion.get("aggregate_sha256") != _sha(
                out / "aggregate-report.json"
            ):
        raise RuntimeError("A3 completion receipt differs")
    return {
        "status": "already-complete",
        "run_id": RUN_ID,
        "aggregate_sha256": completion["aggregate_sha256"],
    }


def finish(
    out: Path = DEFAULT_OUT,
    provenance_path: Path = DEFAULT_PROVENANCE,
    *,
    frozen: FrozenRun = FROZEN,
    root: Path = ROOT,
    execution_loader: ExecutionLoader | None = None,
    inventory_loader: InventoryLoader | None = None,
    downloader: Downloader | None = None,
    git_source_loader: GitSourceLoader = _git_blob,
) -> dict[str, Any]:
    if (out / "finish.sha256").is_file():
        return _validate_complete(out)
    finals = [
        "provenance-addendum.json", "execution-metadata", "object-metadata",
        "cells", "aggregate-report.json", "completion.txt", "cells.sha256",
        "execution-metadata.sha256", "object-metadata.sha256",
    ]
    if any((out / name).exists() for name in finals) or \
            (out / PENDING_NAME).exists():
        raise RuntimeError("A3 partial or immutable strict harvest exists")
    _manifest, cells, provenance_raw = _validate_sources(
        out, provenance_path, frozen, root=root,
        git_source_loader=git_source_loader,
    )
    if execution_loader is None:
        execution_loader = _execution_metadata
    reader: _StorageReader | None = None
    if inventory_loader is None or downloader is None:
        reader = _StorageReader()
    if inventory_loader is None:
        assert reader is not None
        inventory_loader = reader.inventory
    if downloader is None:
        assert reader is not None
        downloader = reader.download

    # Complete every execution and object metadata gate before opening body 1.
    execution_values: dict[tuple[int, int], dict[str, Any]] = {}
    for cell in cells:
        metadata = execution_loader(cell.execution)
        _validate_execution(metadata, cell, frozen)
        execution_values[(cell.season, cell.week)] = metadata
    inventory = _validate_inventory(inventory_loader(frozen.output_prefix), cells)

    pending = out / PENDING_NAME
    pending.mkdir()
    execution_dir = pending / "execution-metadata"
    object_dir = pending / "object-metadata"
    cells_dir = pending / "cells"
    execution_dir.mkdir()
    object_dir.mkdir()
    cells_dir.mkdir()
    (pending / "provenance-addendum.json").write_bytes(provenance_raw)
    for cell in cells:
        (execution_dir / cell.stem).write_bytes(_canonical_json(
            execution_values[(cell.season, cell.week)]
        ))
        (object_dir / cell.stem).write_bytes(_canonical_json(
            inventory[cell.uri]
        ))

    harvested: list[tuple[Cell, bytes, dict[str, Any]]] = []
    for cell in cells:
        raw = downloader(cell.uri, inventory[cell.uri])
        if len(raw) != int(inventory[cell.uri]["size"]):
            raise RuntimeError(f"A3 downloaded object size differs: {cell.uri}")
        receipt = _validate_cell(raw, cell, frozen)
        (cells_dir / cell.stem).write_bytes(raw)
        harvested.append((cell, raw, receipt))

    report = _aggregate(harvested, frozen)
    report_raw = _canonical_json(report)
    (pending / "aggregate-report.json").write_bytes(report_raw)
    aggregate_sha = _sha_bytes(report_raw)
    completion_raw = (
        "\n".join((
            f"validated_at={datetime.now(timezone.utc).isoformat()}",
            f"run_id={frozen.run_id}",
            "disposition=strict-harvest-complete-awaiting-preregistered-read",
            "executions=54", "objects=54", "scientific_bodies=54",
            f"aggregate_sha256={aggregate_sha}",
            f"execution_ledger_sha256={frozen.execution_ledger_sha256}",
            f"provenance_addendum_sha256={_sha_bytes(provenance_raw)}",
            "uses_realized_outcomes=true",
            "production_change_licensed=false",
            "cell_rerun_licensed=false",
            "historical_outcome_lease_released=false",
        )) + "\n"
    ).encode()
    (pending / "completion.txt").write_bytes(completion_raw)
    (pending / "cells.sha256").write_bytes(_hash_ledger(
        list(cells_dir.glob("*.json")), base=pending,
    ))
    (pending / "execution-metadata.sha256").write_bytes(_hash_ledger(
        list(execution_dir.glob("*.json")), base=pending,
    ))
    (pending / "object-metadata.sha256").write_bytes(_hash_ledger(
        list(object_dir.glob("*.json")), base=pending,
    ))

    for name in finals:
        source = pending / name
        if not source.exists() or (out / name).exists():
            raise RuntimeError("A3 strict-harvest publication target differs")
        source.rename(out / name)
    finish_sources = [
        out / "manifest.txt", out / "executions.txt", out / "launch.sha256",
        out / "provenance-addendum.json", out / "cells.sha256",
        out / "execution-metadata.sha256", out / "object-metadata.sha256",
        out / "aggregate-report.json", out / "completion.txt",
    ]
    _write_new(out / "finish.sha256", _hash_ledger(finish_sources, base=out))
    pending.rmdir()
    result = _validate_complete(out)
    result["status"] = "completed"
    print(
        "STACK_RELAXATION_CARVE_STRICTLY_HARVESTED",
        f"run_id={frozen.run_id}", f"sha256={aggregate_sha}",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--provenance-addendum", type=Path, default=DEFAULT_PROVENANCE,
    )
    args = parser.parse_args()
    finish(args.output_dir, args.provenance_addendum)


if __name__ == "__main__":
    main()
