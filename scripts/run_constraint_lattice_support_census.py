#!/usr/bin/env python3
"""Run one immutable control-only constraint-lattice support-census shard."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from google.cloud import bigquery, storage
import numpy as np

from nfl_dfs.analysis.constraint_lattice import (
    REGISTERED_BLOCKS,
    build_training_control,
)
from run_cbwu_seed_order_audit import _upload_create_only
from run_constraint_lattice_scorefree import (
    FORENSIC_MANIFEST_SHA256,
    PROJECT,
    SOURCE_PANELS,
    load_slate_sources,
    validate_local_sources,
)


RUN_ID = "20260816-constraint-lattice-control-support-census-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/constraint-lattice-support-runs/"
    f"{RUN_ID}"
)
PROTOCOL = Path(
    "reports/2026-08-16-constraint-lattice-control-support-census-protocol.md"
)
PROTOCOL_SHA256 = (
    "11e97d5e94a11808b4838396c6fe59ff327a65a9ae260223138657db8d2a1a17"
)
DISTRIBUTION_AMENDMENT = Path(
    "reports/2026-08-16-constraint-lattice-support-distribution-amendment.md"
)
DISTRIBUTION_AMENDMENT_SHA256 = (
    "9bdfd3b24aa42616425138e1fed437fecbeae1d9b9c02606bbe9cde8202bb6e8"
)
SUPPORT_THRESHOLDS = (194.0, 210.0, 220.0, 230.0)


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def validate_support_sources() -> dict[str, str]:
    source_hashes = validate_local_sources()
    if not PROTOCOL.is_file() or _file_sha(PROTOCOL) != PROTOCOL_SHA256:
        raise RuntimeError("constraint-lattice support protocol differs")
    if not DISTRIBUTION_AMENDMENT.is_file() or \
            _file_sha(DISTRIBUTION_AMENDMENT) != DISTRIBUTION_AMENDMENT_SHA256:
        raise RuntimeError("constraint-lattice support distribution amendment differs")
    return {
        **source_hashes,
        str(PROTOCOL): PROTOCOL_SHA256,
        str(DISTRIBUTION_AMENDMENT): DISTRIBUTION_AMENDMENT_SHA256,
    }


def _heldout_control_counts(control: dict[str, object]) -> dict[str, object]:
    lineups = list(control["control_lineups"])
    player_ids = tuple(control["player_ids"])
    draws = np.asarray(control["heldout_row_draws"], dtype=np.float32)
    if len(lineups) != 80 or draws.ndim != 2 or draws.shape[0] != len(player_ids) \
            or draws.shape[1] != 10_000 or not np.isfinite(draws).all():
        raise RuntimeError("constraint-lattice support control shape differs")
    player_index = {str(value): index for index, value in enumerate(player_ids)}
    if len(player_index) != len(player_ids):
        raise RuntimeError("constraint-lattice support player IDs repeat")
    try:
        rows = np.asarray([
            [player_index[str(value)] for value in sorted(lineup.ids, key=str)]
            for lineup in lineups
        ], dtype=np.int64)
    except KeyError as exc:
        raise RuntimeError(
            "constraint-lattice support roster leaves player universe"
        ) from exc
    if rows.shape != (80, 9) or len({tuple(row) for row in rows.tolist()}) != 80:
        raise RuntimeError("constraint-lattice support control roster grid differs")
    totals = draws[rows].sum(axis=1, dtype=np.float32)
    maxima = np.max(totals, axis=0)
    return {
        "worlds": 10_000,
        "control_entries": 80,
        "candidate_budget": int(control["candidate_budget"]),
        "training_union_candidates": int(control["training_union_candidates"]),
        "threshold_counts": {
            f"{threshold:g}": int(np.count_nonzero(maxima >= threshold))
            for threshold in SUPPORT_THRESHOLDS
        },
    }


def run(season: int, week: int, output_uri: str) -> dict:
    expected_uri = f"{OUTPUT_PREFIX}/slate-{season}-{week}.json"
    if season not in {2023, 2024, 2025} or week not in range(1, 19) or \
            output_uri != expected_uri:
        raise RuntimeError("constraint-lattice support shard identity differs")
    source_hashes = validate_support_sources()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("constraint-lattice support code/image is required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    books, artifact_receipts = load_slate_sources(
        bq, gcs, season=season, week=week,
    )
    folds = []
    for heldout in REGISTERED_BLOCKS:
        control = build_training_control(
            books, heldout, expected_worlds_per_block=10_000, tail_line=194.0,
        )
        folds.append({
            "heldout_block": heldout,
            "training_blocks": list(control["training_blocks"]),
            **_heldout_control_counts(control),
        })
        print(
            "CONSTRAINT_LATTICE_SUPPORT_FOLD_COMPLETE",
            season,
            week,
            heldout,
            flush=True,
        )

    payload = {
        "version": "constraint-lattice-control-support-shard-v1",
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "treatment_constructed": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "season": season,
        "week": week,
        "code_sha": code_sha,
        "analysis_image": image,
        "source_hashes": source_hashes,
        "source_panels": list(SOURCE_PANELS),
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "artifact_receipts": artifact_receipts,
        "folds": folds,
    }
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("CONSTRAINT_LATTICE_SUPPORT_SHARD_COMPLETE", season, week, flush=True)
    return {**payload, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.season, args.week, args.output_uri)


if __name__ == "__main__":
    main()
