#!/usr/bin/env python3
"""Run one immutable control-only stack-core/shell support shard."""

from __future__ import annotations

import argparse
import json
import os
import re

from google.cloud import bigquery, storage
import numpy as np

from nfl_dfs.analysis.constraint_lattice import (
    REGISTERED_BLOCKS,
    _roster_rows,
    build_training_control,
)
from run_cbwu_seed_order_audit import _upload_create_only
from stack_core_shell_sources import (
    PROJECT,
    PROTOCOL_SHA256,
    SOURCE_PANELS,
    load_slate_sources,
    validate_local_sources,
)


RUN_ID = "20260816-stack-core-shell-control-support-census-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/stack-core-shell-support-runs/"
    f"{RUN_ID}"
)
SUPPORT_THRESHOLDS = (194.0, 210.0, 220.0, 230.0)


def _tail_counts(
    lineups, player_ids, heldout_row_draws,
) -> dict[str, int]:
    draws = np.asarray(heldout_row_draws, dtype=np.float32)
    if draws.ndim != 2 or draws.shape[0] != len(player_ids) or \
            draws.shape[1] != 10_000 or not np.isfinite(draws).all():
        raise RuntimeError("stack-core/shell support heldout worlds differ")
    rows = _roster_rows(lineups, player_ids)
    if rows.shape != (len(lineups), 9):
        raise RuntimeError("stack-core/shell support roster grid differs")
    maxima = np.max(draws[rows].sum(axis=1, dtype=np.float32), axis=0)
    return {
        f"{threshold:g}": int(np.count_nonzero(maxima >= threshold))
        for threshold in SUPPORT_THRESHOLDS
    }


def _heldout_control_counts(control: dict[str, object]) -> dict[str, object]:
    candidates = list(control["candidate_lineups"])
    selected = list(control["control_lineups"])
    if len(candidates) != int(control["candidate_budget"]) or \
            len(candidates) < 80 or len(selected) != 80:
        raise RuntimeError("stack-core/shell support control shape differs")
    player_ids = tuple(control["player_ids"])
    draws = control["heldout_row_draws"]
    return {
        "worlds": 10_000,
        "control_entries": 80,
        "candidate_budget": len(candidates),
        "training_union_candidates": int(control["training_union_candidates"]),
        "threshold_counts": {
            "candidate": _tail_counts(candidates, player_ids, draws),
            "selected": _tail_counts(selected, player_ids, draws),
        },
    }


def run(season: int, week: int, output_uri: str) -> dict:
    expected_uri = f"{OUTPUT_PREFIX}/slate-{season}-{week}.json"
    if season not in {2023, 2024, 2025} or week not in range(1, 19) or \
            output_uri != expected_uri:
        raise RuntimeError("stack-core/shell support shard identity differs")
    source_hashes = validate_local_sources()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("stack-core/shell support code/image is required")

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
            "STACK_CORE_SHELL_SUPPORT_FOLD_COMPLETE",
            season,
            week,
            heldout,
            flush=True,
        )

    payload = {
        "version": "stack-core-shell-control-support-shard-v1",
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
        "protocol_sha256": PROTOCOL_SHA256,
        "source_hashes": source_hashes,
        "source_panels": list(SOURCE_PANELS),
        "artifact_receipts": artifact_receipts,
        "folds": folds,
    }
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("STACK_CORE_SHELL_SUPPORT_SHARD_COMPLETE", season, week, flush=True)
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
