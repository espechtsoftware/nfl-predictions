#!/usr/bin/env python3
"""Strictly aggregate the control-only constraint-lattice support census."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path

from aggregate_constraint_lattice_scorefree import load_expected_artifact_ledger
from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS
from run_constraint_lattice_scorefree import (
    FORENSIC_MANIFEST_SHA256,
    SOURCE_PANELS,
)
from run_constraint_lattice_support_census import (
    PROTOCOL,
    PROTOCOL_SHA256,
    RUN_ID,
    SUPPORT_THRESHOLDS,
    validate_support_sources,
)


SHARD_VERSION = "constraint-lattice-control-support-shard-v1"
REPORT_VERSION = "constraint-lattice-control-support-report-v1"
AGGREGATE_MINIMUM = 540
POSITIVE_SLATE_MINIMUM = 41
ANCHOR_ORDER = (230, 220, 210)
FORBIDDEN_KEYS = {
    "actual_score", "actual_rank", "actual_ownership", "selected_rank",
    "payout", "contest_rank", "labels_complete", "exception_counts",
    "candidate_ranking", "admission", "treatment_entries",
    "treatment_rosters", "threshold_deltas",
}


def _assert_no_forbidden(value, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(
                    f"constraint-lattice support forbidden field at {path}.{key}"
                )
            _assert_no_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden(child, f"{path}[{index}]")


def _expected_source_hashes() -> dict[str, str]:
    return validate_support_sources()


def aggregate(shard_paths: Sequence[Path]) -> dict[str, object]:
    paths = [Path(path) for path in shard_paths]
    if len(paths) != 54 or len(set(paths)) != 54:
        raise ValueError("constraint-lattice support requires 54 unique shards")
    shards = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    for shard in shards:
        _assert_no_forbidden(shard)
    shards.sort(key=lambda row: (int(row["season"]), int(row["week"])))
    expected_grid = [
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]
    if [(row.get("season"), row.get("week")) for row in shards] != expected_grid:
        raise ValueError("constraint-lattice support slate grid differs")

    expected_artifacts = load_expected_artifact_ledger()
    expected_hashes = _expected_source_hashes()
    first = shards[0]
    common = {
        key: first.get(key) for key in (
            "run_id", "code_sha", "analysis_image", "source_hashes",
            "source_panels", "forensic_manifest_sha256",
        )
    }
    if common["run_id"] != RUN_ID or \
            common["source_hashes"] != expected_hashes or \
            tuple(common["source_panels"] or ()) != SOURCE_PANELS or \
            common["forensic_manifest_sha256"] != FORENSIC_MANIFEST_SHA256:
        raise ValueError("constraint-lattice support common identity differs")

    counts = {
        block: {str(threshold): [] for threshold in map(int, SUPPORT_THRESHOLDS)}
        for block in REGISTERED_BLOCKS
    }
    artifact_population = []
    cell_rows = []
    for shard in shards:
        if set(shard) != {
            "version", "run_id", "uses_realized_outcomes",
            "effect_fields_inspected", "treatment_constructed",
            "production_change_licensed", "historical_scoring_licensed",
            "season", "week", "code_sha", "analysis_image", "source_hashes",
            "source_panels", "forensic_manifest_sha256", "artifact_receipts",
            "folds",
        } or shard.get("version") != SHARD_VERSION or \
                shard.get("uses_realized_outcomes") is not False or \
                shard.get("effect_fields_inspected") is not False or \
                shard.get("treatment_constructed") is not False or \
                shard.get("production_change_licensed") is not False or \
                shard.get("historical_scoring_licensed") is not False or any(
                    shard.get(key) != value for key, value in common.items()
                ):
            raise ValueError("constraint-lattice support shard contract differs")
        season, week = int(shard["season"]), int(shard["week"])
        receipts = shard.get("artifact_receipts")
        if not isinstance(receipts, list) or len(receipts) != 5 or \
                [row.get("block") for row in receipts] != list(REGISTERED_BLOCKS):
            raise ValueError("constraint-lattice support artifact grid differs")
        for block, receipt in zip(REGISTERED_BLOCKS, receipts, strict=True):
            expected = expected_artifacts[(season, week, block)]
            exact = {
                "block": block,
                "source_panel": expected["panel_run_id"],
                "candidate_rows": int(expected["candidate_rows"]),
                "uri": expected["uri"],
                "sha256": expected["sha256"],
                "generation": str(expected["generation"]),
                "updated": expected["updated"],
                "bytes": int(expected["bytes"]),
            }
            if receipt != exact:
                raise ValueError("constraint-lattice support artifact receipt differs")
            artifact_population.append(receipt)

        folds = shard.get("folds")
        if not isinstance(folds, list) or len(folds) != 5 or \
                [row.get("heldout_block") for row in folds] != list(REGISTERED_BLOCKS):
            raise ValueError("constraint-lattice support fold grid differs")
        for block, fold in zip(REGISTERED_BLOCKS, folds, strict=True):
            expected_training = [name for name in REGISTERED_BLOCKS if name != block]
            if set(fold) != {
                "heldout_block", "training_blocks", "worlds", "control_entries",
                "candidate_budget", "training_union_candidates", "threshold_counts",
            } or fold.get("training_blocks") != expected_training or \
                    fold.get("worlds") != 10_000 or \
                    fold.get("control_entries") != 80 or \
                    not isinstance(fold.get("candidate_budget"), int) or \
                    fold["candidate_budget"] < 80 or \
                    not isinstance(fold.get("training_union_candidates"), int) or \
                    fold["training_union_candidates"] < fold["candidate_budget"]:
                raise ValueError("constraint-lattice support fold mechanics differ")
            threshold_counts = fold.get("threshold_counts")
            if not isinstance(threshold_counts, Mapping) or \
                    set(threshold_counts) != {str(int(v)) for v in SUPPORT_THRESHOLDS}:
                raise ValueError("constraint-lattice support threshold grid differs")
            exact_counts = {}
            for threshold in map(int, SUPPORT_THRESHOLDS):
                value = threshold_counts[str(threshold)]
                if not isinstance(value, int) or not 0 <= value <= 10_000:
                    raise ValueError("constraint-lattice support count differs")
                counts[block][str(threshold)].append(value)
                exact_counts[str(threshold)] = value
            cell_rows.append({
                "season": season,
                "week": week,
                "heldout_block": block,
                "worlds": 10_000,
                "control_entries": 80,
                "candidate_budget": fold["candidate_budget"],
                "threshold_counts": exact_counts,
            })

    if len(cell_rows) != 270 or len(artifact_population) != 270:
        raise ValueError("constraint-lattice support population differs")
    by_block = {}
    for block in REGISTERED_BLOCKS:
        by_block[block] = {}
        for threshold in map(int, SUPPORT_THRESHOLDS):
            values = counts[block][str(threshold)]
            by_block[block][str(threshold)] = {
                "events": int(sum(values)),
                "worlds": 540_000,
                "positive_slates": int(sum(value > 0 for value in values)),
                "slates": 54,
            }
    global_counts = {
        str(threshold): {
            "events": int(sum(
                by_block[block][str(threshold)]["events"]
                for block in REGISTERED_BLOCKS
            )),
            "worlds": 2_700_000,
            "positive_cells": int(sum(
                value > 0
                for block in REGISTERED_BLOCKS
                for value in counts[block][str(threshold)]
            )),
            "cells": 270,
        }
        for threshold in map(int, SUPPORT_THRESHOLDS)
    }
    adequate = {
        str(threshold): all(
            by_block[block][str(threshold)]["events"] >= AGGREGATE_MINIMUM
            and by_block[block][str(threshold)]["positive_slates"] >=
            POSITIVE_SLATE_MINIMUM
            for block in REGISTERED_BLOCKS
        )
        for threshold in ANCHOR_ORDER
    }
    selected_anchor = next(
        (threshold for threshold in ANCHOR_ORDER if adequate[str(threshold)]),
        None,
    )
    dispositions = {
        230: "p230-supported-original-gate-complete",
        220: "reanchor-required-p220",
        210: "reanchor-required-p210",
        None: "terminal-insufficient-support",
    }
    return {
        "version": REPORT_VERSION,
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "treatment_constructed": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "protocol_sha256": PROTOCOL_SHA256,
        "protocol_path": str(PROTOCOL),
        **common,
        "mechanical": {
            "seasons": [2023, 2024, 2025],
            "slates": 54,
            "heldout_folds": 270,
            "worlds_per_fold": 10_000,
            "source_artifacts": 270,
            "all_valid": True,
        },
        "support_law": {
            "aggregate_events_minimum_per_block": AGGREGATE_MINIMUM,
            "positive_slates_minimum_per_block": POSITIVE_SLATE_MINIMUM,
            "anchor_order": list(ANCHOR_ORDER),
        },
        "counts_by_block": by_block,
        "global_counts": global_counts,
        "adequate_by_threshold": adequate,
        "selected_anchor": selected_anchor,
        "disposition": dispositions[selected_anchor],
        "cells": cell_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-report", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = aggregate(args.shard_report)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "report.json"
    if output.exists():
        raise RuntimeError("immutable constraint-lattice support report exists")
    output.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print("CONSTRAINT_LATTICE_SUPPORT_AGGREGATED", report["disposition"])


if __name__ == "__main__":
    main()
