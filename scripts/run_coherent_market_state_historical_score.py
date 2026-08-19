#!/usr/bin/env python3
"""Run the frozen coherent market-state realized-score diagnostic once."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from google.cloud import bigquery, storage
import numpy as np
import pandas as pd

from aggregate_coherent_market_state_scorefree import aggregate as aggregate_scorefree
from coherent_market_state_sources import (
    PROJECT,
    REPAIR_PANEL,
    SOURCE_PANELS,
)
from nfl_dfs.analysis.coherent_market_state_historical import (
    CANONICAL_FOLD,
    VERSION,
    aggregate_historical,
    score_slate,
)
from run_cbwu_seed_order_audit import _query, _upload_create_only


RUN_ID = "20260817-coherent-market-state-historical-score-v1"
UPSTREAM_RUN_ID = "20260816-coherent-market-state-scorefree-v1"
UPSTREAM_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/coherent-market-state-runs/"
    f"{UPSTREAM_RUN_ID}"
)
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    f"coherent-market-state-historical-score-runs/{RUN_ID}"
)
UPSTREAM_RECEIPT_URI = f"{OUTPUT_PREFIX}/upstream-receipt.json"
OUTPUT_URI = f"{OUTPUT_PREFIX}/report.json"
PROTOCOL = Path(
    "reports/2026-08-17-coherent-market-state-historical-score-protocol.md"
)
PROTOCOL_SHA256 = (
    "80d85a6af930ee7640ce0e2733a5aee4293cdf3c6102f7659b2d991671464274"
)
SOURCE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = f"{PROJECT}.nfl_predictions.slate_player_features"

SOURCE_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, players, actual_score
FROM `{SOURCE_TABLE}`
WHERE (
  panel_run_id IN UNNEST(@source_panels)
  AND NOT (panel_run_id=@r3_panel AND season=2025 AND week=1)
) OR (
  panel_run_id=@repair_panel AND season=2025 AND week=1
)
ORDER BY panel_run_id, season, week, cand_ix
"""
PLAYER_SQL = f"""
SELECT season, week, id AS player_id, actual
FROM `{PLAYER_TABLE}`
WHERE panel_run_id=@r0_panel AND season IN (2023, 2024, 2025)
ORDER BY season, week, player_id
"""


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("coherent-state historical GCS URI must name one object")
    bucket, marker, name = uri[5:].partition("/")
    if not marker or not bucket or not name or ".." in name.split("/"):
        raise ValueError("coherent-state historical GCS URI is invalid")
    return bucket, name


def _content_identity(receipt: Mapping[str, Any]) -> tuple:
    """Representation-free object identity (CLAUDE.md frozen-chain rule 2):
    uri/generation/sha256/bytes. `updated` strings and any extra keys are
    representations and must never fail a gate."""
    return (
        str(receipt["uri"]), str(receipt["generation"]),
        str(receipt["sha256"]), int(receipt["bytes"]),
    )


def _tree_drift(left: Any, right: Any, path: str = "$") -> list[str]:
    """JSON paths where two aggregates differ. Floats compare by value at
    1e-12 relative/absolute tolerance (cross-image re-derivation must not
    require bit-exact float arithmetic); everything else compares exactly.
    """
    import math

    if isinstance(left, bool) or isinstance(right, bool):
        return [] if left == right else [f"{path}:{left!r}!={right!r}"]
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        lf, rf = float(left), float(right)
        if math.isnan(lf) and math.isnan(rf):
            return []
        if math.isclose(lf, rf, rel_tol=1e-12, abs_tol=1e-12):
            return []
        return [f"{path}:{left!r}!={right!r}"]
    if isinstance(left, dict) and isinstance(right, dict):
        drift: list[str] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                drift.append(f"{path}.{key}:missing")
            else:
                drift.extend(_tree_drift(left[key], right[key], f"{path}.{key}"))
        return drift
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [f"{path}:len {len(left)}!={len(right)}"]
        drift = []
        for index, (a, b) in enumerate(zip(left, right)):
            drift.extend(_tree_drift(a, b, f"{path}[{index}]"))
        return drift
    return [] if left == right else [f"{path}:{left!r}!={right!r}"]


def _download_json(
    client: storage.Client, uri: str,
) -> tuple[dict, dict[str, Any], bytes]:
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    raw = blob.download_as_bytes()
    blob.reload()
    return json.loads(raw), {
        "uri": uri,
        "generation": str(blob.generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "updated": blob.updated.isoformat() if blob.updated else "",
    }, raw


def _validate_object_receipt(value: Mapping[str, object], uri: str) -> None:
    if set(value) != {"uri", "generation", "sha256", "bytes", "updated"} or \
            value.get("uri") != uri or \
            not str(value.get("generation", "")).isdigit() or \
            not re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256", ""))) or \
            not isinstance(value.get("bytes"), int) or int(value["bytes"]) <= 0 or \
            not isinstance(value.get("updated"), str):
        raise RuntimeError("coherent-state historical object receipt differs")


def _validate_scorefree_execution(
    metadata: Mapping[str, object], row: Mapping[str, object],
    *, code_sha: str, image: str,
) -> None:
    season, week = int(row["season"]), int(row["week"])
    job = f"coherent-state-s{season}-w{week}-v1"
    uri = f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json"
    execution = str(row["execution"])
    if row != {
        "season": season, "week": week, "job": job,
        "execution": execution, "uri": uri,
    } or not execution.startswith(job + "-") or \
            metadata.get("metadata", {}).get("name") != execution:
        raise RuntimeError("coherent-state historical accepted execution differs")
    status = metadata.get("status", {})
    completed = [
        value for value in status.get("conditions", [])
        if value.get("type") == "Completed"
    ]
    if len(completed) != 1 or completed[0].get("status") != "True" or \
            int(status.get("succeededCount") or 0) != 1 or \
            int(status.get("failedCount") or 0) != 0 or \
            not status.get("completionTime"):
        raise RuntimeError("coherent-state historical accepted status differs")
    spec = metadata.get("spec", {})
    task = spec.get("template", {}).get("spec", {})
    containers = task.get("containers", [])
    if spec.get("parallelism") != 1 or spec.get("taskCount") != 1 or \
            len(containers) != 1:
        raise RuntimeError("coherent-state historical accepted task shape differs")
    container = containers[0]
    env = {
        value.get("name"): str(value.get("value", ""))
        for value in container.get("env", [])
    }
    if container.get("image") != image or container.get("command") != ["python"] or \
            container.get("args") != [
                "scripts/run_coherent_market_state_scorefree.py",
                "--season", str(season), "--week", str(week),
                "--output-uri", uri,
            ] or env != {"CODE_SHA": code_sha, "ANALYSIS_IMAGE": image} or \
            container.get("resources", {}).get("limits") != {
                "cpu": "4", "memory": "16Gi",
            } or task.get("maxRetries") != 0 or \
            str(task.get("timeoutSeconds")) != "14400" or \
            task.get("serviceAccountName") != \
            "817589974517-compute@developer.gserviceaccount.com":
        raise RuntimeError("coherent-state historical accepted contract differs")


def _validate_upstream_receipt(receipt: Mapping[str, object]) -> None:
    fixed = {
        "version": "coherent-market-state-historical-upstream-receipt-v1",
        "run_id": UPSTREAM_RUN_ID,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": True,
        "primary_executions": 54,
        "accepted_execution_count": 54,
        "slates": 54,
        "folds": 270,
    }
    if any(receipt.get(key) != value for key, value in fixed.items()) or \
            not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("code_sha", ""))) or \
            not re.fullmatch(
                r".+@sha256:[0-9a-f]{64}", str(receipt.get("image", "")),
            ):
        raise RuntimeError("coherent-state historical upstream identity differs")
    hashes = receipt.get("strict_harvest_sha256")
    required_hashes = {
        "manifest", "primary_executions", "retry_executions",
        "accepted_executions", "attempt_resolution", "completion",
        "execution_metadata", "object_metadata", "shards", "report",
        "report_upload",
    }
    if not isinstance(hashes, Mapping) or set(hashes) != required_hashes or any(
        not re.fullmatch(r"[0-9a-f]{64}", str(value))
        for value in hashes.values()
    ):
        raise RuntimeError("coherent-state historical strict harvest differs")
    report = receipt.get("report_object")
    if not isinstance(report, Mapping):
        raise RuntimeError("coherent-state historical report receipt differs")
    _validate_object_receipt(report, f"{UPSTREAM_PREFIX}/report.json")
    shards = receipt.get("shard_objects")
    if not isinstance(shards, list) or len(shards) != 54:
        raise RuntimeError("coherent-state historical shard receipt grid differs")
    expected = [
        (season, week)
        for season in (2023, 2024, 2025) for week in range(1, 19)
    ]
    if [(row.get("season"), row.get("week")) for row in shards] != expected:
        raise RuntimeError("coherent-state historical shard order differs")
    for row in shards:
        season, week = int(row["season"]), int(row["week"])
        if set(row) != {
            "season", "week", "uri", "generation", "sha256", "bytes", "updated",
        }:
            raise RuntimeError("coherent-state historical shard receipt differs")
        _validate_object_receipt(
            {key: value for key, value in row.items() if key not in {"season", "week"}},
            f"{UPSTREAM_PREFIX}/slate-{season}-{week}.json",
        )
    executions = receipt.get("accepted_executions")
    metadata = receipt.get("execution_metadata")
    if not isinstance(executions, list) or len(executions) != 54 or \
            not isinstance(metadata, Mapping) or len(metadata) != 54:
        raise RuntimeError("coherent-state historical execution receipt grid differs")
    if [(row.get("season"), row.get("week")) for row in executions] != expected or \
            set(metadata) != {str(row.get("execution")) for row in executions}:
        raise RuntimeError("coherent-state historical execution receipt order differs")
    for row in executions:
        _validate_scorefree_execution(
            metadata[str(row["execution"])], row,
            code_sha=str(receipt["code_sha"]), image=str(receipt["image"]),
        )


def _source_params() -> list[bigquery.QueryParameter]:
    return [
        bigquery.ArrayQueryParameter(
            "source_panels", "STRING", list(SOURCE_PANELS),
        ),
        bigquery.ScalarQueryParameter("r3_panel", "STRING", SOURCE_PANELS[3]),
        bigquery.ScalarQueryParameter("repair_panel", "STRING", REPAIR_PANEL),
    ]


def _actual_maps(players: pd.DataFrame) -> dict[tuple[int, int], dict[str, float]]:
    if players.empty or players.duplicated(["season", "week", "player_id"]).any():
        raise RuntimeError("coherent-state historical player outcomes differ")
    maps = {}
    for (season, week), group in players.groupby(["season", "week"], sort=True):
        values = pd.to_numeric(group.actual, errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise RuntimeError("coherent-state historical player outcome is non-finite")
        maps[(int(season), int(week))] = {
            str(player_id): float(actual)
            for player_id, actual in zip(group.player_id, values, strict=True)
        }
    expected = {
        (season, week)
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    if set(maps) != expected:
        raise RuntimeError("coherent-state historical player slate grid differs")
    return maps


def _validate_actual_parity(
    sources: pd.DataFrame,
    actual_maps: Mapping[tuple[int, int], Mapping[str, float]],
) -> dict[str, object]:
    if len(sources) != 68_199:
        raise RuntimeError("coherent-state historical parity row count differs")
    malformed = 0
    missing = 0
    errors = []
    for row in sources.itertuples(index=False):
        roster = [value for value in str(row.players).split(",") if value]
        if len(roster) != 9 or len(set(roster)) != 9:
            malformed += 1
            continue
        actual = actual_maps[(int(row.season), int(row.week))]
        absent = [value for value in roster if value not in actual]
        missing += len(absent)
        if absent:
            continue
        reconstructed = float(sum(actual[value] for value in roster))
        errors.append(abs(reconstructed - float(row.actual_score)))
    maximum = float(max(errors, default=float("inf")))
    if malformed or missing or len(errors) != len(sources) or maximum > 1e-9:
        raise RuntimeError("coherent-state historical actual-score parity differs")
    return {
        "registered_candidate_rows": len(sources),
        "slots_per_roster": 9,
        "malformed_rosters": malformed,
        "missing_player_outcomes": missing,
        "compared_rows": len(errors),
        "maximum_absolute_error": maximum,
        "absolute_tolerance": 1e-9,
        "relative_tolerance": 0.0,
        "source_storage_type": "FLOAT",
    }


def run(upstream_receipt_uri: str, output_uri: str) -> dict:
    if upstream_receipt_uri != UPSTREAM_RECEIPT_URI or output_uri != OUTPUT_URI:
        raise RuntimeError("coherent-state historical input/output identity differs")
    if not PROTOCOL.is_file() or sha256(PROTOCOL.read_bytes()).hexdigest() != \
            PROTOCOL_SHA256:
        raise RuntimeError("coherent-state historical protocol differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("coherent-state historical code/image is required")

    gcs = storage.Client(project=PROJECT)
    receipt, receipt_object, _ = _download_json(gcs, upstream_receipt_uri)
    _validate_upstream_receipt(receipt)
    shard_payloads = []
    downloaded_receipts = []
    with TemporaryDirectory() as raw_temp:
        temp = Path(raw_temp)
        paths = []
        for expected in receipt["shard_objects"]:
            payload, object_receipt, raw = _download_json(gcs, expected["uri"])
            # Content identity (CLAUDE.md frozen-chain rule 2): compare
            # uri/generation/sha256/bytes; `updated` is a representation.
            if _content_identity(object_receipt) != _content_identity(expected):
                raise RuntimeError(
                    "coherent-state historical shard object changed: "
                    f"{expected['season']}-{expected['week']} "
                    f"live={_content_identity(object_receipt)} "
                    f"receipt={_content_identity(expected)}")
            path = temp / f"slate-{expected['season']}-{expected['week']}.json"
            path.write_bytes(raw)
            paths.append(path)
            shard_payloads.append(payload)
            downloaded_receipts.append({
                "season": expected["season"], "week": expected["week"],
                **object_receipt,
            })
        reproduced = aggregate_scorefree(paths)
    upstream_report, report_object, _ = _download_json(
        gcs, f"{UPSTREAM_PREFIX}/report.json",
    )
    # Diagnostic fail-closed gate (2026-08-18 kqw47: the combined
    # condition raised without naming its leg, and the failure could not
    # be reproduced outside the container). Each leg now reports itself,
    # and the cross-image re-aggregation compares floats at 1e-12
    # relative tolerance — bit-exact float re-derivation across image
    # builds is not a sound requirement, value equality is.
    if _content_identity(report_object) != _content_identity(
            receipt["report_object"]):
        raise RuntimeError(
            "coherent-state historical upstream aggregate changed: "
            f"report object live={_content_identity(report_object)} "
            f"receipt={_content_identity(receipt['report_object'])}")
    drift = _tree_drift(reproduced, upstream_report)
    if drift:
        raise RuntimeError(
            "coherent-state historical upstream aggregate changed: "
            f"re-aggregation differs at {drift[:8]}")
    if upstream_report.get("historical_scoring_licensed") is not True:
        raise RuntimeError(
            "coherent-state historical upstream aggregate changed: "
            "report is not licensed for historical scoring")
    if reproduced.get("code_sha") != receipt["code_sha"] or \
            reproduced.get("analysis_image") != receipt["image"]:
        raise RuntimeError("coherent-state historical upstream source differs")

    # Outcomes are queried only after the complete upstream population has
    # independently reproduced and validated.
    bq = bigquery.Client(project=PROJECT)
    sources = _query(bq, SOURCE_SQL, _source_params())
    players = _query(bq, PLAYER_SQL, [bigquery.ScalarQueryParameter(
        "r0_panel", "STRING", SOURCE_PANELS[0],
    )])
    actual_maps = _actual_maps(players)
    parity = _validate_actual_parity(sources, actual_maps)
    rows = []
    for shard in shard_payloads:
        season, week = int(shard["season"]), int(shard["week"])
        folds = shard["slate"]["folds"]
        selected = [row for row in folds if row.get("heldout_block") == CANONICAL_FOLD]
        if len(selected) != 1:
            raise RuntimeError("coherent-state historical canonical fold grid differs")
        rows.append(score_slate(selected[0], actual_maps[(season, week)]))
        print("COHERENT_MARKET_STATE_HISTORICAL_SLATE_COMPLETE", season, week, flush=True)
    result = aggregate_historical(rows)
    result.update({
        "run_id": RUN_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "scorer_code_sha": code_sha,
        "scorer_image": image,
        "upstream": {
            "run_id": UPSTREAM_RUN_ID,
            "code_sha": receipt["code_sha"],
            "image": receipt["image"],
            "receipt_object": receipt_object,
            "strict_harvest_sha256": receipt["strict_harvest_sha256"],
            "report_object": report_object,
            "shard_objects": downloaded_receipts,
            "scorefree_gate_passed": upstream_report["gate"][
                "passes_scorefree_gate"
            ],
        },
        "native_actual_score_parity": parity,
    })
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("COHERENT_MARKET_STATE_HISTORICAL_RESULT " + json.dumps({
        "gate": result["gate"], "output": upload,
    }, sort_keys=True))
    return {**result, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-receipt-uri", required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.upstream_receipt_uri, args.output_uri)


if __name__ == "__main__":
    main()
