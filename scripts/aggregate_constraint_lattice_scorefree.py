#!/usr/bin/env python3
"""Strictly aggregate the frozen constraint-lattice slate population."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence

from nfl_dfs.analysis.constraint_lattice import (
    CELL_ORDER,
    REGISTERED_BLOCKS,
    REPORT_THRESHOLDS,
    VERSION,
    aggregate_heldout_gate,
    protocol_receipt,
)


SHARD_VERSION = "constraint-lattice-scorefree-shard-v1"
REPORT_VERSION = "constraint-lattice-scorefree-report-v1"
RUN_ID = "20260816-constraint-lattice-scorefree-v1"
FORBIDDEN_KEYS = {
    "actual_score", "actual_rank", "actual_ownership", "selected_rank",
    "payout", "contest_rank", "labels_complete",
}


def _assert_no_outcomes(value, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"constraint-lattice outcome field at {path}.{key}")
            _assert_no_outcomes(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_outcomes(child, f"{path}[{index}]")


def _roster_grid(value, *, rows: int) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == rows
        and all(isinstance(roster, list) and len(roster) == 9
                and len(set(map(str, roster))) == 9 for roster in value)
        and len({tuple(sorted(map(str, roster))) for roster in value}) == rows
    )


def _validate_fold(row: Mapping, season: int, week: int, block: str) -> None:
    if row.get("version") != VERSION or \
            row.get("uses_realized_outcomes") is not False or \
            row.get("mechanical_valid") is not True or \
            row.get("season") != season or row.get("week") != week or \
            row.get("heldout_block") != block or row.get("worlds") != 10_000 or \
            row.get("control_entries") != 80 or \
            row.get("treatment_entries") != 80:
        raise ValueError("constraint-lattice fold identity/mechanics differ")
    if not _roster_grid(row.get("control_rosters"), rows=80) or \
            not _roster_grid(row.get("treatment_rosters"), rows=80):
        raise ValueError("constraint-lattice exact-80 roster grid differs")
    candidate_budget = row.get("candidate_budget")
    if not isinstance(candidate_budget, int) or candidate_budget < 80 or \
            not _roster_grid(
                row.get("control_candidate_rosters"), rows=candidate_budget,
            ):
        raise ValueError("constraint-lattice control candidate grid differs")
    training = row.get("training_blocks")
    expected_training = [value for value in REGISTERED_BLOCKS if value != block]
    if training != expected_training:
        raise ValueError("constraint-lattice training-block identity differs")
    source_rows = row.get("candidate_source_aggregation")
    if not isinstance(source_rows, list) or len(source_rows) != candidate_budget:
        raise ValueError("constraint-lattice source aggregation differs")
    for source in source_rows:
        if sorted(source) != ["roster", "sources", "tags"] or \
                len(source["roster"]) != 9 or not source["sources"] or \
                not set(source["sources"]) <= set(training) or \
                not isinstance(source["tags"], list):
            raise ValueError("constraint-lattice source receipt is malformed")
    generation = row.get("generation")
    if not isinstance(generation, list) or len(generation) != 20 or {
        (item.get("cell"), item.get("source_block")) for item in generation
    } != {(cell, source) for cell in CELL_ORDER for source in training}:
        raise ValueError("constraint-lattice generation grid differs")
    for item in generation:
        retained = item.get("retained")
        if not isinstance(retained, list) or len(retained) > 2 or \
                not isinstance(item.get("attempted_worlds"), int) or \
                item["attempted_worlds"] < len(retained) or \
                not isinstance(item.get("elapsed_seconds"), (int, float)) or \
                item["elapsed_seconds"] < 0:
            raise ValueError("constraint-lattice generation receipt differs")
    if row.get("raw_exception_candidates", 41) > 40 or \
            row.get("retained_exception_candidates", 9) > 8 or \
            row.get("new_exception_entries", 9) > 8 or \
            not isinstance(row.get("elapsed_seconds"), (int, float)) or \
            row["elapsed_seconds"] < 0:
        raise ValueError("constraint-lattice exception/runtime mechanics differ")


def aggregate(shard_paths: Sequence[Path]) -> dict:
    paths = [Path(path) for path in shard_paths]
    if len(paths) != 54 or len(set(paths)) != 54:
        raise ValueError("constraint-lattice aggregate requires 54 unique shards")
    shards = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    for shard in shards:
        _assert_no_outcomes(shard)
    shards.sort(key=lambda row: (int(row["season"]), int(row["week"])))
    expected_grid = [
        (season, week)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
    ]
    if [(row.get("season"), row.get("week")) for row in shards] != expected_grid:
        raise ValueError("constraint-lattice shard season/week grid differs")
    first = shards[0]
    common = {
        key: first.get(key) for key in (
            "run_id", "code_sha", "analysis_image", "source_hashes",
            "source_panels", "forensic_manifest_sha256", "protocol_receipt",
        )
    }
    if common["run_id"] != RUN_ID or common["protocol_receipt"] != protocol_receipt():
        raise ValueError("constraint-lattice aggregate identity differs")

    all_folds = []
    artifact_receipts = []
    slate_times = []
    admitted = Counter()
    for shard in shards:
        if shard.get("version") != SHARD_VERSION or \
                shard.get("uses_realized_outcomes") is not False or \
                shard.get("production_change_licensed") is not False or \
                shard.get("historical_scoring_licensed") is not False or any(
                    shard.get(key) != value for key, value in common.items()
                ):
            raise ValueError("constraint-lattice shard binding differs")
        season, week = int(shard["season"]), int(shard["week"])
        slate = shard.get("slate", {})
        if slate.get("version") != VERSION or \
                slate.get("uses_realized_outcomes") is not False or \
                slate.get("season") != season or slate.get("week") != week or \
                not isinstance(slate.get("elapsed_seconds"), (int, float)) or \
                slate["elapsed_seconds"] < 0:
            raise ValueError("constraint-lattice slate binding differs")
        folds = slate.get("folds")
        if not isinstance(folds, list) or len(folds) != 5 or \
                [row.get("heldout_block") for row in folds] != list(REGISTERED_BLOCKS):
            raise ValueError("constraint-lattice slate fold grid differs")
        for block, fold in zip(REGISTERED_BLOCKS, folds, strict=True):
            _validate_fold(fold, season, week, block)
            admitted.update(
                item["cell"] for item in fold["admission"]["admitted"]
            )
            all_folds.append(fold)
        receipts = shard.get("artifact_receipts")
        if not isinstance(receipts, list) or len(receipts) != 5 or \
                [row.get("block") for row in receipts] != list(REGISTERED_BLOCKS):
            raise ValueError("constraint-lattice artifact receipt grid differs")
        for receipt in receipts:
            if receipt.get("source_panel") not in common["source_panels"] or \
                    not receipt.get("uri", "").startswith("gs://") or \
                    len(str(receipt.get("sha256", ""))) != 64 or \
                    not str(receipt.get("generation", "")).isdigit() or \
                    receipt.get("candidate_rows", 0) < 80:
                raise ValueError("constraint-lattice artifact receipt differs")
        artifact_receipts.extend(receipts)
        slate_times.append(float(slate["elapsed_seconds"]))

    if len(artifact_receipts) != 270 or len({
        (row["block"], row["uri"], row["generation"])
        for row in artifact_receipts
    }) != 270:
        raise ValueError("constraint-lattice artifact population differs")
    gate = aggregate_heldout_gate(all_folds)
    threshold_by_season = {}
    for season in (2023, 2024, 2025):
        rows = [row for row in all_folds if int(row["season"]) == season]
        threshold_by_season[str(season)] = {
            book: {
                f"{threshold:g}": sum(
                    int(row["threshold_counts"][book][f"{threshold:g}"])
                    for row in rows
                )
                for threshold in REPORT_THRESHOLDS
            }
            for book in ("control", "treatment")
        }
    return {
        "version": REPORT_VERSION,
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        **common,
        "mechanical": {
            "seasons": [2023, 2024, 2025],
            "slates": 54,
            "heldout_folds": 270,
            "source_artifacts": 270,
            "all_valid": True,
        },
        "runtime_seconds": {
            "mean_per_slate": float(mean(slate_times)),
            "maximum_per_slate": float(max(slate_times)),
            "total": float(sum(slate_times)),
        },
        "admitted_exceptions_by_cell": {
            cell: int(admitted[cell]) for cell in CELL_ORDER
        },
        "threshold_counts_by_season": threshold_by_season,
        "gate": gate,
        "shards": shards,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-report", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = aggregate([Path(value) for value in args.shard_report])
    Path(args.output).write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print("CONSTRAINT_LATTICE_AGGREGATE_VALIDATED", result["gate"]["passes_scorefree_gate"])


if __name__ == "__main__":
    main()
