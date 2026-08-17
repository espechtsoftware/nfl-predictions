#!/usr/bin/env python3
"""Strictly seal the score-free ATLAS repair5/repair6 hybrid population."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from google.cloud import storage

from nfl_dfs.research.atlas_historical_v3_sources import loads_json, parse_kv
from nfl_dfs.research.atlas_repair6 import (
    EXPECTED_CELLS,
    REPAIR5_RUN_ID,
    REPAIR6_RUN_ID,
    canonical_json,
)
from nfl_dfs.research.atlas_repair6_hybrid import (
    PROOF_PREFIX,
    REPAIR5_CODE_SHA,
    REPAIR5_IMAGE,
    REPAIR5_PREFIX,
    REPAIR6_PREFIX,
    validate_hybrid_receipt,
)
from render_atlas_matched_diversity_repair4_command import render
from run_cbwu_seed_order_audit import _parse_gcs


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
ROOT = Path(__file__).resolve().parents[1]
REPAIR5 = ROOT / "reports/atlas-matched-diversity-runs" / REPAIR5_RUN_ID
OUT = ROOT / "reports/atlas-matched-diversity-runs" / REPAIR6_RUN_ID


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = loads_json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"ATLAS repair6 JSON source differs: {path}")
    return value


def _verify(path: Path, receipt: Path | None = None) -> None:
    receipt = receipt or path.with_suffix(".sha256")
    expected = f"{_sha(path)}  {path}\n"
    if not receipt.is_file() or receipt.read_text(encoding="utf-8") != expected:
        raise RuntimeError(f"ATLAS repair6 hash receipt differs: {path}")


def _execution(name: str) -> dict[str, Any]:
    raw = subprocess.run([
        "gcloud", "run", "jobs", "executions", "describe", name,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ], check=True, text=True, capture_output=True).stdout
    value = loads_json(raw)
    if not isinstance(value, dict):
        raise RuntimeError("ATLAS repair6 execution metadata differs")
    return value


def _job_executions(job: str) -> list[str]:
    proc = subprocess.run([
        "gcloud", "run", "jobs", "executions", "list", "--job", job,
        "--project", PROJECT, "--region", REGION,
        "--format=value(metadata.name)",
    ], text=True, capture_output=True)
    if proc.returncode:
        lowered = proc.stderr.lower()
        if "not found" in lowered or "does not exist" in lowered:
            return []
        proc.check_returncode()
    rows = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if len(rows) != len(set(rows)):
        raise RuntimeError("ATLAS repair6 duplicate execution census entry")
    return sorted(rows)


def _inventory(client: storage.Client, prefix: str) -> list[str]:
    bucket_name, name = _parse_gcs(prefix)
    stem = name.rstrip("/") + "/"
    return sorted(
        f"gs://{bucket_name}/{blob.name}"
        for blob in client.list_blobs(bucket_name, prefix=stem)
    )


def _object(client: storage.Client, uri: str) -> dict[str, Any]:
    bucket_name, name = _parse_gcs(uri)
    blob = client.bucket(bucket_name).blob(name)
    blob.reload()
    if blob.generation is None or blob.size is None or int(blob.size) <= 0:
        raise RuntimeError(f"ATLAS repair6 object metadata differs: {uri}")
    generation = int(blob.generation)
    raw = blob.download_as_bytes(if_generation_match=generation)
    if len(raw) != int(blob.size):
        raise RuntimeError(f"ATLAS repair6 object size differs: {uri}")
    return {
        "uri": uri, "generation": str(generation), "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(), "md5_hash": str(blob.md5_hash or ""),
        "crc32c": str(blob.crc32c or ""),
        "updated": blob.updated.isoformat() if blob.updated else "",
    }


def finish() -> dict[str, Any]:
    paths = {
        "manifest": OUT / "manifest.txt",
        "classification": OUT / "eligibility-classification.json",
        "proof": OUT / "code-diff-proof.json",
        "eligible": OUT / "eligible-cells.txt",
        "canary": OUT / "canary-completion.txt",
        "canary_ledger": OUT / "canary-executions.txt",
        "repair6_ledger": OUT / "repair6-executions.txt",
        "grid_release": OUT / "repair6-grid-release.txt",
        "repair5_census": REPAIR5 / "terminal-census.json",
        "repair5_primary": REPAIR5 / "executions.txt",
        "repair5_inventory": REPAIR5 / "terminal-census-object-inventory.txt",
    }
    for name, path in paths.items():
        if not path.is_file():
            raise RuntimeError(f"ATLAS repair6 hybrid source missing ({name}): {path}")
    for name in (
        "hybrid-accepted-executions.txt", "hybrid-population-receipt.json",
        "hybrid-completion.txt", "hybrid-finish.sha256",
        "hybrid-execution-metadata", "hybrid-object-metadata",
    ):
        if (OUT / name).exists():
            raise RuntimeError("ATLAS repair6 immutable hybrid harvest exists")
    for key in (
        "manifest", "classification", "proof", "eligible", "canary_ledger",
        "repair6_ledger", "grid_release", "repair5_census", "repair5_inventory",
    ):
        _verify(paths[key])
    canary_hashes = OUT / "canary-finish.sha256"
    sealed_canary = {
        fields[1]: fields[0]
        for fields in (
            line.split(maxsplit=1)
            for line in canary_hashes.read_text(encoding="utf-8").splitlines()
        ) if len(fields) == 2
    } if canary_hashes.is_file() else {}
    if sealed_canary.get(str(paths["canary"])) != _sha(paths["canary"]):
        raise RuntimeError("ATLAS repair6 canary completion is not sealed")

    manifest = parse_kv(paths["manifest"])
    canary = parse_kv(paths["canary"])
    release = parse_kv(paths["grid_release"])
    classification = _load(paths["classification"])
    census = _load(paths["repair5_census"])
    if manifest.get("hybrid_finisher_sha256") != _sha(Path(__file__)) or \
            manifest.get("hybrid_source_sha256") != _sha(
                ROOT / "src/nfl_dfs/research/atlas_repair6_hybrid.py"
            ):
        raise RuntimeError("ATLAS repair6 hybrid implementation differs")
    if canary.get("disposition") != "repair6-dual-canary-passes" or \
            release.get("uses_realized_outcomes") != "false" or \
            classification.get("disposition") != "repair6-dual-canary-licensed" or \
            classification.get("repair6_launch_licensed") is not True or \
            census.get("version") != "atlas-matched-diversity-repair5-terminal-census-v1" or \
            census.get("executions") != 54 or census.get("terminal_failed", 0) < 1 or \
            census.get("scientific_result_valid") is not False or \
            census.get("execution_ledger_sha256") != _sha(paths["repair5_primary"]):
        raise RuntimeError("ATLAS repair6 hybrid disposition source differs")

    primary_rows = [line.split() for line in paths["repair5_primary"].read_text(
        encoding="utf-8").splitlines() if line.strip()]
    r6_rows = [line.split() for line in paths["repair6_ledger"].read_text(
        encoding="utf-8").splitlines() if line.strip()]
    eligible_rows = [line.split() for line in paths["eligible"].read_text(
        encoding="utf-8").splitlines() if line.strip()]
    if len(primary_rows) != 54 or any(len(row) != 5 for row in primary_rows) or \
            any(len(row) != 6 for row in r6_rows) or \
            any(len(row) != 6 for row in eligible_rows):
        raise RuntimeError("ATLAS repair6 hybrid source ledger differs")
    eligible_cells = {(int(row[0]), int(row[1])) for row in eligible_rows}
    r6_by_cell = {(int(row[0]), int(row[1])): row for row in r6_rows}
    if not eligible_cells or set(r6_by_cell) != eligible_cells or \
            len(r6_by_cell) != len(r6_rows) or \
            len(eligible_cells) != len(classification["eligible_tiebreak_failures"]):
        raise RuntimeError("ATLAS repair6 eligible execution population differs")
    classified_eligible = {
        (int(row["season"]), int(row["week"])): row
        for row in classification["eligible_tiebreak_failures"]
    }
    if set(classified_eligible) != eligible_cells:
        raise RuntimeError("ATLAS repair6 eligible classification grid differs")
    for row in eligible_rows:
        season, week, primary_execution, world, job, uri = row
        classified = classified_eligible[(int(season), int(week))]
        if classified.get("primary_execution") != primary_execution or \
                str(classified.get("world")) != world or \
                job != f"atlas-md-s{season}-w{week}-r6" or \
                uri != f"{REPAIR6_PREFIX}/slate-{season}-{week}.json":
            raise RuntimeError("ATLAS repair6 eligible classification binding differs")

    accepted = []
    for primary in primary_rows:
        season, week, r5_job, primary_execution, r5_uri = primary
        cell = (int(season), int(week))
        if cell in eligible_cells:
            r6 = r6_by_cell[cell]
            if r6[:3] != [season, week, primary_execution] or \
                    r6[3] != f"atlas-md-s{season}-w{week}-r6" or \
                    r6[5] != f"{REPAIR6_PREFIX}/slate-{season}-{week}.json":
                raise RuntimeError("ATLAS repair6 replacement binding differs")
            accepted.append([season, week, "repair6", r6[3], r6[4], r6[5]])
        else:
            accepted.append([season, week, "repair5", r5_job, primary_execution, r5_uri])
    if {(int(row[0]), int(row[1])) for row in accepted} != set(EXPECTED_CELLS):
        raise RuntimeError("ATLAS repair6 accepted population is not exact 54")

    pending = OUT / ".hybrid-finish-pending"
    if pending.exists():
        raise RuntimeError("ATLAS repair6 pending hybrid harvest exists")
    pending.mkdir()
    accepted_path = pending / "hybrid-accepted-executions.txt"
    accepted_path.write_text("".join(" ".join(row) + "\n" for row in accepted),
                             encoding="utf-8")
    execution_dir = pending / "hybrid-execution-metadata"
    object_dir = pending / "hybrid-object-metadata"
    execution_dir.mkdir()
    object_dir.mkdir()
    execution_metadata = {}
    objects = {}
    for row in accepted:
        key = f"{row[0]}-{row[1]}"
        if row[2] == "repair5":
            source = REPAIR5 / "terminal-census-execution-metadata" / \
                f"season-{row[0]}-week-{row[1]}.json"
            value = _load(source)
        else:
            value = _execution(row[4])
        execution_metadata[key] = value
        (execution_dir / f"season-{row[0]}-week-{row[1]}.json").write_bytes(
            canonical_json(value)
        )

    client = storage.Client(project=PROJECT)
    inventories = {
        "repair5": _inventory(client, REPAIR5_PREFIX),
        "repair6": _inventory(client, REPAIR6_PREFIX),
        "proof": _inventory(client, PROOF_PREFIX),
    }
    repair5_local_inventory = [line.strip() for line in paths[
        "repair5_inventory"].read_text(encoding="utf-8").splitlines() if line.strip()]
    if inventories["repair5"] != sorted(repair5_local_inventory):
        raise RuntimeError("ATLAS repair6 live repair5 inventory differs from census")
    for row in accepted:
        key = f"{row[0]}-{row[1]}"
        value = _object(client, row[5])
        objects[key] = value
        (object_dir / f"season-{row[0]}-week-{row[1]}.json").write_bytes(
            canonical_json(value)
        )

    job_names = {}
    for season, week in EXPECTED_CELLS:
        for suffix in ("r5", "r6"):
            job = f"atlas-md-s{season}-w{week}-{suffix}"
            job_names[job] = _job_executions(job)
    proof_job = "atlas-md-s2023-w1-r6-proof"
    job_names[proof_job] = _job_executions(proof_job)
    canary_rows = [line.split() for line in paths["canary_ledger"].read_text(
        encoding="utf-8").splitlines() if line.strip()]
    proof_rows = [row for row in canary_rows if row[0] == "proof"]
    if len(proof_rows) != 1:
        raise RuntimeError("ATLAS repair6 proof execution source differs")

    receipt = {
        "version": "atlas-repair6-hybrid-population-receipt-v1",
        "run_id": REPAIR6_RUN_ID, "repair5_run_id": REPAIR5_RUN_ID,
        "repair5_prefix": REPAIR5_PREFIX, "repair6_prefix": REPAIR6_PREFIX,
        "proof_prefix": PROOF_PREFIX,
        "protocol_sha256": manifest["protocol_sha256"],
        "repair5_code_sha": REPAIR5_CODE_SHA, "repair5_image": REPAIR5_IMAGE,
        "repair6_code_sha": manifest["code_sha"],
        "repair6_image": manifest["image"],
        "repair5_terminal_census_sha256": _sha(paths["repair5_census"]),
        "eligibility_classification_sha256": _sha(paths["classification"]),
        "code_diff_proof_sha256": _sha(paths["proof"]),
        "dual_canary_completion_sha256": _sha(paths["canary"]),
        "repair6_grid_release_sha256": _sha(paths["grid_release"]),
        "accepted_execution_ledger_sha256": _sha(accepted_path),
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "effect_fields_inspected": False,
        "production_change_licensed": False,
        "disposition": "valid-complete-repair6-hybrid-population",
        "cells": 54,
        "eligible_cells": [[s, w] for s, w in sorted(eligible_cells)],
        "repair5_primary_rows": primary_rows,
        "accepted_rows": accepted, "execution_metadata": execution_metadata,
        "objects": objects, "job_execution_names": job_names,
        "prefix_inventories": inventories,
        "proof_execution": proof_rows[0][4],
    }
    validate_hybrid_receipt(
        receipt, repair5_grid_command=render(REPAIR5_PREFIX),
        repair6_grid_command=render(REPAIR6_PREFIX),
    )
    receipt_path = pending / "hybrid-population-receipt.json"
    receipt_path.write_bytes(canonical_json(receipt))
    completion = pending / "hybrid-completion.txt"
    completion.write_text("\n".join((
        f"run_id={REPAIR6_RUN_ID}",
        "disposition=valid-complete-repair6-hybrid-population",
        "cells=54", f"repair5_cells={54 - len(eligible_cells)}",
        f"repair6_cells={len(eligible_cells)}",
        f"receipt_sha256={_sha(receipt_path)}",
        "uses_realized_outcomes=false", "candidate_or_lineup_scores_read=false",
        "effect_fields_inspected=false", "historical_scoring_licensed=true",
        "production_change_licensed=false",
    )) + "\n", encoding="utf-8")
    ledger = pending / "hybrid-finish.sha256"
    files = [accepted_path, receipt_path, completion,
             *sorted(execution_dir.glob("*.json")),
             *sorted(object_dir.glob("*.json"))]
    ledger.write_text("".join(
        f"{_sha(path)}  {OUT / path.relative_to(pending)}\n" for path in files
    ), encoding="utf-8")
    for source in pending.iterdir():
        source.rename(OUT / source.name)
    pending.rmdir()
    return {
        "disposition": "valid-complete-repair6-hybrid-population",
        "repair5_cells": 54 - len(eligible_cells),
        "repair6_cells": len(eligible_cells),
    }


def main() -> None:
    print("ATLAS_REPAIR6_HYBRID_FINISHED " + json.dumps(
        finish(), sort_keys=True,
    ))


if __name__ == "__main__":
    main()
