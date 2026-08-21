#!/usr/bin/env python3
"""Default-off operational runner for real LR8 2023--2025 construction.

The three commands are intentionally transport-thin:

* ``freeze-source`` performs two fixed, outcome-free BigQuery reads and binds
  them to the generation-pinned 270-artifact source lock;
* ``construct-cell`` generation-reads five retained NPZs and the earlier fit,
  then runs one smoke or one full A/B slate with exact CBC evidence; and
* ``aggregate`` consumes a terminal-harvester-created manifest of exactly 54
  generation-pinned cell objects and publishes the 108-book freeze.

This file does not launch or poll Cloud Run, acquire an outcome lease, query a
realized column, or score a lineup.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from nfl_dfs.research import lr8_exact_solvers as exact  # noqa: E402
from nfl_dfs.research import lr8_label_fit_adapter as label_fit  # noqa: E402
from nfl_dfs.research import lr8_later_period_source as later  # noqa: E402
import run_atlas_minimal_world_selection_c as atlas_source  # noqa: E402
import run_a2a_rank_factor_split_census as a2a_source  # noqa: E402
import run_lr8_training_source as source_transport  # noqa: E402


ENABLED_ENV = "LR8_LATER_PERIOD_ENABLED"
PROJECT = "nfl-predictions-503414"
LOCATION = "US"
# Reuse the already exercised, outcome-blind ATLAS source seam rather than
# defining a third source population.  The query SHA receipts below bind the
# LR8 all-slate projection of these exact table contracts.
CANDIDATE_TABLE = later.CANDIDATE_TABLE
CATALOG_TABLE = later.CATALOG_TABLE
if later.R0_PANEL != atlas_source.SOURCE_PANEL_IDS[0]:
    raise RuntimeError("LR8 canonical R0 differs from the ATLAS source contract")
CANDIDATE_SQL = later.CANDIDATE_SQL
CATALOG_SQL = later.CATALOG_SQL
if (
    CANDIDATE_TABLE != atlas_source.CAND_TABLE
    or CATALOG_TABLE != atlas_source.SNAPSHOT_TABLE
    or (
        later.BASE_SOURCE_URI,
        later.BASE_SOURCE_GENERATION,
        later.BASE_SOURCE_SHA256,
        later.BASE_SOURCE_BYTES,
    )
    != (
        a2a_source.SOURCE_LOCK_URI,
        a2a_source.SOURCE_LOCK_GENERATION,
        a2a_source.SOURCE_LOCK_SHA256,
        a2a_source.SOURCE_LOCK_BYTES,
    )
):
    raise RuntimeError("LR8 later source authority differs from retained sources")

_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_GENERATION = re.compile(r"[1-9][0-9]*")
_IMAGE = re.compile(r".+@sha256:[0-9a-f]{64}")


class LR8LaterRunnerError(RuntimeError):
    """The default-off operational LR8 later-period runner failed closed."""


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite constant {value}")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw, object_pairs_hook=unique, parse_constant=reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise LR8LaterRunnerError(f"{label} is not strict JSON") from exc
    if not isinstance(value, dict):
        raise LR8LaterRunnerError(f"{label} must be a JSON object")
    return value


def _identity_args(args: argparse.Namespace) -> dict[str, object]:
    if (
        args.project != PROJECT
        or _HEX40.fullmatch(args.code_sha or "") is None
        or _IMAGE.fullmatch(args.image or "") is None
        or not isinstance(args.job, str)
        or not args.job
        or not isinstance(args.run_id, str)
        or not args.run_id
    ):
        raise LR8LaterRunnerError("LR8 later-period runtime identity differs")
    return {
        "run_id": args.run_id,
        "code_sha": args.code_sha,
        "image": args.image,
        "job": args.job,
    }


def _enabled(args: argparse.Namespace) -> None:
    if args.execute is not True or os.environ.get(ENABLED_ENV) != "1":
        raise LR8LaterRunnerError(
            f"--execute and {ENABLED_ENV}=1 are both required"
        )


def _parts(uri: str) -> tuple[str, str]:
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        raise LR8LaterRunnerError("object URI must use gs://")
    bucket, marker, name = uri.removeprefix("gs://").partition("/")
    if not bucket or not marker or not name or ".." in name.split("/"):
        raise LR8LaterRunnerError("object URI is malformed")
    return bucket, name


def _receipt_from_args(args: argparse.Namespace, prefix: str) -> dict[str, object]:
    uri = getattr(args, f"{prefix}_uri")
    generation = getattr(args, f"{prefix}_generation")
    digest = getattr(args, f"{prefix}_sha256")
    size = getattr(args, f"{prefix}_bytes")
    if (
        not isinstance(uri, str)
        or _GENERATION.fullmatch(generation or "") is None
        or _HEX64.fullmatch(digest or "") is None
        or type(size) is not int
        or size <= 0
    ):
        raise LR8LaterRunnerError(f"{prefix} object identity differs")
    return {"uri": uri, "generation": generation, "sha256": digest, "bytes": size}


def _load(storage_client: object, receipt: Mapping[str, object]) -> bytes:
    uri = str(receipt["uri"])
    generation = int(str(receipt["generation"]))
    bucket, name = _parts(uri)
    try:
        blob = storage_client.bucket(bucket).blob(  # type: ignore[attr-defined]
            name, generation=generation
        )
        blob.reload(if_generation_match=generation)
        raw = blob.download_as_bytes(if_generation_match=generation)
    except Exception as exc:
        raise LR8LaterRunnerError("generation-pinned object read failed") from exc
    if (
        str(blob.generation) != str(generation)
        or len(raw) != receipt["bytes"]
        or _sha(raw) != receipt["sha256"]
    ):
        raise LR8LaterRunnerError("generation-pinned object bytes differ")
    return raw


def _publish(storage_client: object, uri: str, raw: bytes) -> dict[str, object]:
    try:
        published = source_transport._default_publish(  # noqa: SLF001
            storage_client, uri, raw
        )
    except Exception as exc:
        raise LR8LaterRunnerError("create-once publication failed") from exc
    receipt = dict(published.receipt)
    if (
        published.reopened_raw != raw
        or receipt.get("uri") != uri
        or receipt.get("sha256") != _sha(raw)
        or receipt.get("bytes") != len(raw)
    ):
        raise LR8LaterRunnerError("create-once publication receipt differs")
    return receipt


def _iso(value: object, *, label: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise LR8LaterRunnerError(f"{label} timestamp differs")
    return value.astimezone(timezone.utc).isoformat()


def _query(
    client: object, *, sql: str, job_id: str, source_snapshot_at: str,
) -> tuple[tuple[dict[str, object], ...], dict[str, object]]:
    from google.cloud import bigquery

    parameters = [
        bigquery.ScalarQueryParameter("r0_panel", "STRING", later.R0_PANEL),
        bigquery.ScalarQueryParameter(
            "source_snapshot_at", "TIMESTAMP", source_snapshot_at
        ),
    ]
    parameter_payload = later.source_parameter_payload(source_snapshot_at)
    sql_sha = _sha(sql.encode("utf-8"))
    params_sha = later.canonical_sha256(parameter_payload)
    try:
        job = client.query(  # type: ignore[attr-defined]
            sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=parameters, use_query_cache=False
            ),
            job_id=job_id,
            location=LOCATION,
            job_retry=None,
        )
        result = job.result()
        rows = tuple(
            dict(row.items()) if hasattr(row, "items") else dict(row)
            for row in result
        )
    except Exception as exc:
        raise LR8LaterRunnerError("outcome-blind source query failed") from exc
    receipt = {
        "job_id": job.job_id,
        "location": job.location,
        "sql_sha256": sql_sha,
        "parameters_sha256": params_sha,
        "created": _iso(job.created, label="query created"),
        "started": _iso(job.started, label="query started"),
        "ended": _iso(job.ended, label="query ended"),
        "total_bytes_processed": int(job.total_bytes_processed or 0),
        "cache_hit": job.cache_hit,
        "error_result": job.error_result,
    }
    return rows, receipt


def freeze_source(args: argparse.Namespace) -> dict[str, object]:
    _enabled(args)
    identity = _identity_args(args)
    from google.cloud import bigquery, storage

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    base_receipt = _receipt_from_args(args, "base_source")
    base_raw = _load(gcs, base_receipt)
    base = _strict_json(base_raw, label="retained 270-artifact source lock")
    expected_base = {
        "uri": a2a_source.SOURCE_LOCK_URI,
        "generation": a2a_source.SOURCE_LOCK_GENERATION,
        "sha256": a2a_source.SOURCE_LOCK_SHA256,
        "bytes": a2a_source.SOURCE_LOCK_BYTES,
    }
    if base_receipt != expected_base:
        raise LR8LaterRunnerError("retained source-lock object identity differs")
    try:
        a2a_source._validate_source_lock(base)  # noqa: SLF001
    except RuntimeError as exc:
        raise LR8LaterRunnerError("retained source-lock body differs") from exc
    snapshot = datetime.now(timezone.utc).isoformat()
    candidates, candidate_query = _query(
        bq,
        sql=CANDIDATE_SQL,
        job_id=f"{args.run_id}-r0-candidates",
        source_snapshot_at=snapshot,
    )
    catalog, catalog_query = _query(
        bq,
        sql=CATALOG_SQL,
        job_id=f"{args.run_id}-full-catalog",
        source_snapshot_at=snapshot,
    )
    freeze = later.build_source_freeze(
        base_source_lock=base,
        base_source_lock_object=base_receipt,
        base_source_lock_sha256=str(base_receipt["sha256"]),
        r0_candidate_rows=candidates,
        full_catalog_rows=catalog,
        query_provenance={
            "candidate_query": candidate_query,
            "catalog_query": catalog_query,
            "candidate_table": CANDIDATE_TABLE,
            "catalog_table": CATALOG_TABLE,
            "source_snapshot_at": snapshot,
        },
        runtime_identity=identity,
    )
    raw = later.canonical_json(freeze)
    receipt = _publish(gcs, args.output_uri, raw)
    return {
        "status": "LR8_LATER_SOURCE_FROZEN",
        "freeze_sha256": freeze["freeze_sha256"],
        "object": receipt,
    }


def _load_source_and_fit(args: argparse.Namespace, storage_client: object):
    source_receipt = _receipt_from_args(args, "source")
    source_body = _strict_json(
        _load(storage_client, source_receipt), label="LR8 later source freeze"
    )
    source = later.validate_source_freeze(
        source_body, expected_freeze_sha256=args.source_freeze_sha256
    )
    fit_receipt = _receipt_from_args(args, "fit")
    fit_body = _strict_json(
        _load(storage_client, fit_receipt), label="LR8 earlier label/fit freeze"
    )
    fit = label_fit.validate_label_fit_freeze(
        fit_body, expected_freeze_sha256=args.fit_freeze_sha256
    )
    return source, source_receipt, fit, fit_receipt


def _validated_smoke_authority(
    args: argparse.Namespace, storage_client: object,
) -> dict[str, object]:
    receipt = _receipt_from_args(args, "smoke")
    body = later.validate_construction_cell(
        _strict_json(_load(storage_client, receipt), label="LR8 later source smoke"),
        expected_cell_sha256=args.smoke_cell_sha256,
        mode="smoke",
    )
    terminal_receipt = _receipt_from_args(args, "smoke_terminal")
    terminal = _strict_json(
        _load(storage_client, terminal_receipt),
        label="LR8 later source smoke terminal",
    )
    if terminal.get("terminal_sha256") != args.smoke_terminal_manifest_sha256:
        raise LR8LaterRunnerError("smoke terminal manifest hash differs")
    authority = {
        "object": receipt,
        "smoke_sha256": body["cell_sha256"],
        "source_freeze_sha256": body["source_freeze_sha256"],
        "anatomy_artifact_sha256": body["anatomy_artifact_sha256"],
        "terminal": terminal,
        "terminal_object": terminal_receipt,
    }
    validated = later.validate_smoke_authority(
        authority,
        source_freeze_sha256=str(body["source_freeze_sha256"]),
        anatomy_artifact_sha256=str(body["anatomy_artifact_sha256"]),
    )
    for key in ("execution_metadata_object", "finish_ledger_object"):
        _load(storage_client, validated["terminal"][key])
    return validated


def _smoke_authority(args: argparse.Namespace, storage_client: object):
    if args.mode == "smoke":
        return None
    return _validated_smoke_authority(args, storage_client)


def construct_cell(args: argparse.Namespace) -> dict[str, object]:
    _enabled(args)
    _identity_args(args)
    from google.cloud import storage

    gcs = storage.Client(project=PROJECT)
    source, _, fit, _ = _load_source_and_fit(args, gcs)
    index = args.cell_index
    if type(index) is not int or not 0 <= index < len(later.EXPECTED_SLATE_KEYS):
        raise LR8LaterRunnerError("construction cell index differs")
    season, week = later.EXPECTED_SLATE_KEYS[index]
    if args.mode == "smoke" and index != 0:
        raise LR8LaterRunnerError("real-source smoke must use cell index zero")
    source_row = source["slates"][index]
    artifact_bodies = {}
    for receipt in source_row["artifact_receipts"]:
        artifact_bodies[str(receipt["block"])] = _load(gcs, {
            key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")
        })
    prepared = later.prepare_later_slate(
        source,
        expected_source_freeze_sha256=args.source_freeze_sha256,
        season=season,
        week=week,
        artifact_bodies=artifact_bodies,
    )
    authority = _smoke_authority(args, gcs)
    evidence_root = args.evidence_root.resolve()
    if not evidence_root.is_absolute() or evidence_root.exists():
        raise LR8LaterRunnerError("evidence root must be absent and absolute")
    fold_roots = {fold: evidence_root / fold.lower() for fold in ("A", "B")}
    for root in fold_roots.values():
        root.mkdir(parents=True, exist_ok=False)
    prefix = args.output_uri.rsplit("/", 1)[0]

    def publish(uri: str, raw: bytes):
        return source_transport._default_publish(gcs, uri, raw)  # noqa: SLF001

    pricing_steps = {}
    for fold in ("A", "B"):
        evidence_publisher = source_transport._evidence_publisher(  # noqa: SLF001
            evidence_root=fold_roots[fold],
            output_root=f"{prefix}/solver-evidence/{fold.lower()}",
            publish=publish,
        )
        pricing_steps[fold] = exact.make_pricing_step(
            evidence_root=fold_roots[fold], publish_evidence=evidence_publisher
        )
    cell = later.run_construction_cell(
        prepared,
        anatomy_artifact=fit["anatomy_artifact"],
        pricing_steps=pricing_steps,
        mode=args.mode,
        smoke_authority=authority,
    )
    raw = later.canonical_json(cell)
    receipt = _publish(gcs, args.output_uri, raw)
    return {
        "status": "LR8_LATER_SMOKE_COMPLETE" if args.mode == "smoke"
        else "LR8_LATER_CELL_COMPLETE",
        "season": season,
        "week": week,
        "cell_sha256": cell["cell_sha256"],
        "object": receipt,
    }


def aggregate(args: argparse.Namespace) -> dict[str, object]:
    _enabled(args)
    _identity_args(args)
    from google.cloud import storage

    gcs = storage.Client(project=PROJECT)
    try:
        manifest_raw = args.cell_manifest.read_bytes()
    except OSError as exc:
        raise LR8LaterRunnerError("terminal cell manifest is unreadable") from exc
    if _sha(manifest_raw) != args.cell_manifest_sha256:
        raise LR8LaterRunnerError("terminal cell manifest hash differs")
    manifest = _strict_json(manifest_raw, label="terminal cell manifest")
    if set(manifest) != {"schema", "strict_terminal_success", "cells"} or (
        manifest["schema"] != "lr8-later-terminal-cell-manifest-v1"
        or manifest["strict_terminal_success"] is not True
        or not isinstance(manifest["cells"], list)
        or len(manifest["cells"]) != len(later.EXPECTED_SLATE_KEYS)
    ):
        raise LR8LaterRunnerError("terminal cell manifest fields differ")
    receipts = manifest["cells"]
    cells = [
        _strict_json(_load(gcs, receipt), label="terminal construction cell")
        for receipt in receipts
    ]
    source_receipt = _receipt_from_args(args, "source")
    source = later.validate_source_freeze(
        _strict_json(
            _load(gcs, source_receipt), label="LR8 later source freeze"
        ),
        expected_freeze_sha256=args.source_freeze_sha256,
    )
    fit_receipt = _receipt_from_args(args, "fit")
    fit = label_fit.validate_label_fit_freeze(
        _strict_json(_load(gcs, fit_receipt), label="LR8 earlier label/fit freeze"),
        expected_freeze_sha256=args.fit_freeze_sha256,
    )
    if fit["anatomy_artifact_sha256"] != args.anatomy_artifact_sha256:
        raise LR8LaterRunnerError("aggregate anatomy artifact pin differs")
    authority = _validated_smoke_authority(args, gcs)
    freeze = later.aggregate_book_freeze(
        cells,
        cell_objects=receipts,
        source_freeze=source,
        source_freeze_object=source_receipt,
        anatomy_freeze=fit,
        anatomy_freeze_sha256=args.fit_freeze_sha256,
        anatomy_freeze_object=fit_receipt,
        smoke_authority=authority,
    )
    raw = later.canonical_json(freeze)
    receipt = _publish(gcs, args.output_uri, raw)
    return {
        "status": "LR8_LATER_108_BOOK_FREEZE_COMPLETE",
        "freeze_sha256": freeze["freeze_sha256"],
        "object": receipt,
    }


def _object_args(
    parser: argparse.ArgumentParser, prefix: str, *, required: bool = True,
) -> None:
    label = prefix.replace("_", "-")
    parser.add_argument(f"--{label}-uri", required=required)
    parser.add_argument(f"--{label}-generation", required=required)
    parser.add_argument(f"--{label}-sha256", required=required)
    parser.add_argument(f"--{label}-bytes", type=int, required=required)


def _runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze-source")
    _runtime_args(freeze)
    _object_args(freeze, "base_source")
    freeze.add_argument("--output-uri", required=True)

    cell = commands.add_parser("construct-cell")
    _runtime_args(cell)
    cell.add_argument("--mode", choices=("smoke", "full"), required=True)
    cell.add_argument("--cell-index", type=int, required=True)
    cell.add_argument("--evidence-root", type=Path, required=True)
    cell.add_argument("--output-uri", required=True)
    _object_args(cell, "source")
    cell.add_argument("--source-freeze-sha256", required=True)
    _object_args(cell, "fit")
    cell.add_argument("--fit-freeze-sha256", required=True)
    # A smoke creates the authority; a full cell consumes it.  argparse cannot
    # make these flags conditionally required, so the runtime boundary enforces
    # their presence through ``_receipt_from_args`` only in full mode.
    _object_args(cell, "smoke", required=False)
    cell.add_argument("--smoke-cell-sha256")
    _object_args(cell, "smoke_terminal", required=False)
    cell.add_argument("--smoke-terminal-manifest-sha256")

    final = commands.add_parser("aggregate")
    _runtime_args(final)
    final.add_argument("--cell-manifest", type=Path, required=True)
    final.add_argument("--cell-manifest-sha256", required=True)
    final.add_argument("--output-uri", required=True)
    _object_args(final, "source")
    final.add_argument("--source-freeze-sha256", required=True)
    _object_args(final, "fit")
    final.add_argument("--fit-freeze-sha256", required=True)
    final.add_argument("--anatomy-artifact-sha256", required=True)
    _object_args(final, "smoke")
    final.add_argument("--smoke-cell-sha256", required=True)
    _object_args(final, "smoke_terminal")
    final.add_argument("--smoke-terminal-manifest-sha256", required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "freeze-source":
        result = freeze_source(args)
    elif args.command == "construct-cell":
        result = construct_cell(args)
    elif args.command == "aggregate":
        result = aggregate(args)
    else:  # pragma: no cover
        raise LR8LaterRunnerError("LR8 later-period command differs")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
