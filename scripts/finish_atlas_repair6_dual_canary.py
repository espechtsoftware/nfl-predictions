#!/usr/bin/env python3
"""Strictly finish the score-free ATLAS repair6 dual canary."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping, Sequence

from google.cloud import storage

from nfl_dfs.research.atlas_historical_v3_sources import parse_kv
from nfl_dfs.research.atlas_repair6 import REPAIR5_RUN_ID, REPAIR6_RUN_ID, canonical_json
from render_atlas_matched_diversity_repair4_command import render
from run_cbwu_seed_order_audit import _parse_gcs


PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/atlas-matched-diversity-runs" / REPAIR6_RUN_ID
REPAIR5 = ROOT / "reports/atlas-matched-diversity-runs" / REPAIR5_RUN_ID
PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    f"{REPAIR6_RUN_ID}"
)
PROOF_PREFIX = PREFIX + "-proof"
PROTOCOL = ROOT / "reports/2026-08-17-atlas-repair6-identity-tiebreak-extension-protocol.md"
PROTOCOL_SHA256 = "b4a98543b1dcd776d50ae00e380fbc695346debb0de6452131fdfd0ba7c2820a"
REPAIR5_W1_URI = (
    "gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/"
    f"{REPAIR5_RUN_ID}/slate-2023-1.json"
)
REPAIR5_W1_GENERATION = "1786971235274440"
REPAIR5_W1_EXECUTION = "atlas-md-s2023-w1-r5-45nvf"


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _execution(name: str) -> dict[str, Any]:
    raw = subprocess.run([
        "gcloud", "run", "jobs", "executions", "describe", name,
        "--project", PROJECT, "--region", REGION, "--format=json",
    ], check=True, text=True, capture_output=True).stdout
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError("ATLAS repair6 execution metadata differs")
    return value


def _job_executions(job: str) -> list[str]:
    raw = subprocess.run([
        "gcloud", "run", "jobs", "executions", "list", "--job", job,
        "--project", PROJECT, "--region", REGION,
        "--format=value(metadata.name)",
    ], check=True, text=True, capture_output=True).stdout
    return sorted(line.strip() for line in raw.splitlines() if line.strip())


def _validate_execution(
    value: Mapping[str, Any], row: Sequence[str], manifest: Mapping[str, str],
    grid_command: str,
) -> None:
    role, season, week, job, execution, uri = row
    if value.get("metadata", {}).get("name") != execution:
        raise RuntimeError("ATLAS repair6 canary execution identity differs")
    spec = value.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError("ATLAS repair6 canary task shape differs")
    container = containers[0]
    env = {item.get("name"): str(item.get("value", ""))
           for item in container.get("env", [])}
    expected_args = [
        "-c", grid_command, "--season", season, "--week", week,
        "--output-uri", uri,
    ]
    if container.get("image") != manifest["image"] or \
            container.get("command") != ["python"] or \
            container.get("args") != expected_args or env != {
                "CODE_SHA": manifest["code_sha"],
                "ANALYSIS_IMAGE": manifest["image"],
            } or container.get("resources", {}).get("limits") != {
                "cpu": "8", "memory": "32Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "43200" or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError("ATLAS repair6 canary execution contract differs")
    status = value.get("status", {})
    completed = [item for item in status.get("conditions", [])
                 if item.get("type") == "Completed"]
    if len(completed) != 1 or completed[0].get("status") != "True" or \
            int(status.get("succeededCount") or 0) != 1 or \
            int(status.get("failedCount") or 0) != 0 or \
            int(status.get("cancelledCount") or 0) != 0 or \
            not status.get("completionTime"):
        raise RuntimeError(f"ATLAS repair6 {role} canary did not succeed")


def _object(
    client: storage.Client, uri: str, *, generation: str | None = None,
) -> tuple[dict[str, Any], bytes]:
    bucket_name, name = _parse_gcs(uri)
    blob = client.bucket(bucket_name).blob(
        name, generation=int(generation) if generation else None,
    )
    blob.reload()
    if blob.generation is None or blob.size is None or int(blob.size) <= 0:
        raise RuntimeError(f"ATLAS repair6 object metadata differs: {uri}")
    actual_generation = str(blob.generation)
    if generation is not None and actual_generation != generation:
        raise RuntimeError(f"ATLAS repair6 object generation differs: {uri}")
    raw = blob.download_as_bytes(if_generation_match=int(actual_generation))
    if len(raw) != int(blob.size):
        raise RuntimeError(f"ATLAS repair6 object size differs: {uri}")
    return {
        "uri": uri, "generation": actual_generation, "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(), "md5_hash": str(blob.md5_hash or ""),
        "crc32c": str(blob.crc32c or ""),
        "updated": blob.updated.isoformat() if blob.updated else "",
    }, raw


def _inventory(client: storage.Client, prefix: str) -> list[str]:
    bucket_name, name = _parse_gcs(prefix)
    stem = name.rstrip("/") + "/"
    return sorted(
        f"gs://{bucket_name}/{blob.name}"
        for blob in client.list_blobs(bucket_name, prefix=stem)
    )


def _verify_hash_receipt(path: Path) -> None:
    receipt = path.with_suffix(".sha256")
    expected = f"{_file_sha(path)}  {path}\n"
    if not receipt.is_file() or receipt.read_text(encoding="utf-8") != expected:
        raise RuntimeError(f"ATLAS repair6 source receipt differs: {path}")


def finish() -> dict[str, Any]:
    manifest_path = OUT / "manifest.txt"
    ledger_path = OUT / "canary-executions.txt"
    build_path = OUT / "build-metadata.json"
    for path in (manifest_path, ledger_path, build_path):
        if not path.is_file():
            raise RuntimeError(f"ATLAS repair6 canary launch receipt missing: {path}")
    final_names = (
        "canary-execution-metadata", "canary-object-metadata",
        "byte-equivalence.json", "canary-completion.txt", "canary-finish.sha256",
    )
    if any((OUT / name).exists() for name in final_names):
        raise RuntimeError("ATLAS repair6 immutable canary harvest exists")
    manifest = parse_kv(manifest_path)
    expected_manifest = {
        "run_id": REPAIR6_RUN_ID, "output_prefix": PREFIX,
        "proof_prefix": PROOF_PREFIX, "protocol_sha256": PROTOCOL_SHA256,
        "tasks": "1", "parallelism": "1", "cpu": "8", "memory": "32Gi",
        "timeout_seconds": "43200", "max_retries": "0",
        "uses_realized_outcomes": "false",
        "production_change_licensed": "false",
        "repair5_w1_uri": REPAIR5_W1_URI,
        "repair5_w1_generation": REPAIR5_W1_GENERATION,
        "repair5_w1_execution": REPAIR5_W1_EXECUTION,
    }
    if any(manifest.get(key) != value for key, value in expected_manifest.items()) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", manifest.get("image", "")) or \
            not re.fullmatch(r"[0-9a-f]{40}", manifest.get("code_sha", "")) or \
            _file_sha(PROTOCOL) != PROTOCOL_SHA256:
        raise RuntimeError("ATLAS repair6 canary manifest differs")
    source_paths = {
        "launcher_sha256": ROOT / "scripts/cloud_atlas_repair6_dual_canary.sh",
        "finisher_sha256": ROOT / "scripts/finish_atlas_repair6_dual_canary.py",
    }
    if any(manifest.get(key) != _file_sha(path)
           for key, path in source_paths.items()):
        raise RuntimeError("ATLAS repair6 canary source differs")
    _verify_hash_receipt(manifest_path)
    _verify_hash_receipt(ledger_path)
    if not (OUT / "build-metadata.sha256").is_file() or \
            (OUT / "build-metadata.sha256").read_text(encoding="utf-8") != \
            f"{_file_sha(build_path)}  {build_path}\n":
        raise RuntimeError("ATLAS repair6 build receipt differs")
    rows = [line.split() for line in ledger_path.read_text(
        encoding="utf-8").splitlines() if line.strip()]
    expected_rows = {
        "defect": ("2023", "7", "atlas-md-s2023-w7-r6", f"{PREFIX}/slate-2023-7.json"),
        "proof": ("2023", "1", "atlas-md-s2023-w1-r6-proof", f"{PROOF_PREFIX}/slate-2023-1.json"),
    }
    if len(rows) != 2 or any(len(row) != 6 for row in rows) or \
            {row[0] for row in rows} != set(expected_rows):
        raise RuntimeError("ATLAS repair6 dual-canary ledger differs")
    by_role = {row[0]: row for row in rows}
    for role, (season, week, job, uri) in expected_rows.items():
        row = by_role[role]
        if tuple(row[1:4]) != (season, week, job) or row[5] != uri or \
                not row[4].startswith(job + "-") or \
                _job_executions(job) != [row[4]]:
            raise RuntimeError("ATLAS repair6 dual-canary execution population differs")
    grid_command = render(PREFIX)
    if manifest.get("grid_command_sha256") != sha256(
            grid_command.encode()).hexdigest():
        raise RuntimeError("ATLAS repair6 canary command differs")

    pending = OUT / ".canary-finish-pending"
    if pending.exists():
        raise RuntimeError("ATLAS repair6 pending canary harvest exists")
    pending.mkdir()
    execution_dir = pending / "canary-execution-metadata"
    object_dir = pending / "canary-object-metadata"
    execution_dir.mkdir()
    object_dir.mkdir()
    execution_metadata = {}
    for role, row in by_role.items():
        value = _execution(row[4])
        _validate_execution(value, row, manifest, grid_command)
        execution_metadata[role] = value
        (execution_dir / f"{role}.json").write_bytes(canonical_json(value))

    client = storage.Client(project=PROJECT)
    if _inventory(client, PREFIX) != [by_role["defect"][5]] or \
            _inventory(client, PROOF_PREFIX) != [by_role["proof"][5]]:
        raise RuntimeError("ATLAS repair6 dual-canary object population differs")
    defect_meta, _defect_raw = _object(client, by_role["defect"][5])
    proof_meta, proof_raw = _object(client, by_role["proof"][5])
    repair5_meta, repair5_raw = _object(
        client, REPAIR5_W1_URI, generation=REPAIR5_W1_GENERATION,
    )
    repair5_local_meta = _load(REPAIR5 / "canary-object-metadata.json")
    if str(repair5_local_meta.get("generation")) != REPAIR5_W1_GENERATION or \
            int(repair5_local_meta.get("size") or 0) != len(repair5_raw) or \
            repair5_local_meta.get("storage_url") != \
            f"{REPAIR5_W1_URI}#{REPAIR5_W1_GENERATION}":
        raise RuntimeError("ATLAS repair6 repair5 proof source metadata differs")
    for role, value in (("defect", defect_meta), ("proof", proof_meta),
                        ("repair5-week1", repair5_meta)):
        (object_dir / f"{role}.json").write_bytes(canonical_json(value))
    equivalent = proof_raw == repair5_raw
    equivalence = {
        "version": "atlas-repair6-byte-equivalence-v1",
        "repair5": repair5_meta, "repair6_proof": proof_meta,
        "bytes_equal": equivalent,
        "sha256_equal": proof_meta["sha256"] == repair5_meta["sha256"],
        "json_parsed": False, "effect_fields_inspected": False,
        "uses_realized_outcomes": False,
    }
    (pending / "byte-equivalence.json").write_bytes(canonical_json(equivalence))
    if not equivalent or not equivalence["sha256_equal"]:
        raise RuntimeError("ATLAS repair6 no-change canary is not byte-identical")
    completion = pending / "canary-completion.txt"
    completion.write_text("\n".join((
        f"run_id={REPAIR6_RUN_ID}",
        "disposition=repair6-dual-canary-passes",
        f"defect_execution={by_role['defect'][4]}",
        f"proof_execution={by_role['proof'][4]}",
        f"defect_object_generation={defect_meta['generation']}",
        f"defect_object_bytes={defect_meta['bytes']}",
        f"defect_object_sha256={defect_meta['sha256']}",
        f"proof_object_generation={proof_meta['generation']}",
        f"proof_bytes_sha256={proof_meta['sha256']}",
        "repair5_repair6_week1_byte_identical=true",
        "object_json_parsed=false", "effect_fields_inspected=false",
        "uses_realized_outcomes=false", "production_change_licensed=false",
    )) + "\n", encoding="utf-8")
    for source in (*sorted(execution_dir.glob("*.json")),
                   *sorted(object_dir.glob("*.json")),
                   pending / "byte-equivalence.json", completion):
        final = OUT / source.relative_to(pending)
        with (pending / "canary-finish.sha256").open("a", encoding="utf-8") as handle:
            handle.write(f"{_file_sha(source)}  {final}\n")
    for source in pending.iterdir():
        source.rename(OUT / source.name)
    pending.rmdir()
    return {
        "disposition": "repair6-dual-canary-passes",
        "defect_execution": by_role["defect"][4],
        "proof_execution": by_role["proof"][4],
    }


def main() -> None:
    print("ATLAS_REPAIR6_DUAL_CANARY_FINISHED " + json.dumps(
        finish(), sort_keys=True,
    ))


if __name__ == "__main__":
    main()
