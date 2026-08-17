#!/usr/bin/env python3
"""Strictly aggregate the control-only stack-core/shell support census."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import math
from pathlib import Path
import re

from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS
from run_stack_core_shell_support_census import (
    RUN_ID,
    SUPPORT_THRESHOLDS,
)
from stack_core_shell_sources import (
    PROTOCOL,
    PROTOCOL_SHA256,
    REPAIR_PANEL,
    SOURCE_PANELS,
    TRANSFER_REPORT,
    validate_local_sources,
)


SHARD_VERSION = "stack-core-shell-control-support-shard-v1"
REPORT_VERSION = "stack-core-shell-control-support-report-v1"
AGGREGATE_MINIMUM = 540
POSITIVE_SLATE_MINIMUM = 41
ANCHOR_ORDER = (230, 220, 210)
LAYERS = ("candidate", "selected")
FORBIDDEN_KEYS = {
    "actual_score", "actual_rank", "actual_ownership", "selected_rank",
    "payout", "contest_rank", "labels_complete", "exception_counts",
    "candidate_ranking", "admission", "treatment_entries",
    "treatment_rosters", "threshold_deltas", "proposals",
}


def _assert_no_forbidden(value, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(
                    f"stack-core/shell support forbidden field at {path}.{key}"
                )
            _assert_no_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden(child, f"{path}[{index}]")


def _support_distribution(values: Sequence[int]) -> dict[str, object]:
    if len(values) != 54 or any(value < 0 for value in values):
        raise ValueError("stack-core/shell support distribution differs")
    total = int(sum(values))
    ordered = sorted((int(value) for value in values), reverse=True)
    positive = sorted(value for value in ordered if value > 0)
    shares = [value / total for value in values] if total else []
    hhi = float(sum(value * value for value in shares)) if shares else None
    middle = len(positive) // 2
    median = None
    if positive:
        median = (
            float(positive[middle])
            if len(positive) % 2
            else float(positive[middle - 1] + positive[middle]) / 2.0
        )
    return {
        "events": total,
        "worlds": 540_000,
        "positive_slates": len(positive),
        "slates": 54,
        "top_1_event_share": float(sum(ordered[:1]) / total) if total else None,
        "top_3_event_share": float(sum(ordered[:3]) / total) if total else None,
        "top_5_event_share": float(sum(ordered[:5]) / total) if total else None,
        "top_10_event_share": float(sum(ordered[:10]) / total) if total else None,
        "herfindahl": hhi,
        "effective_slates": float(1.0 / hhi) if hhi else None,
        "median_positive_events": median,
        "max_slate_events": max(ordered) if ordered else 0,
    }


def _pearson(left: Sequence[int], right: Sequence[int]) -> float | None:
    if len(left) != 54 or len(right) != 54:
        raise ValueError("stack-core/shell support correlation vector differs")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_delta = [value - left_mean for value in left]
    right_delta = [value - right_mean for value in right]
    denominator = math.sqrt(
        sum(value * value for value in left_delta)
        * sum(value * value for value in right_delta)
    )
    if denominator == 0:
        return None
    return float(
        sum(a * b for a, b in zip(left_delta, right_delta, strict=True))
        / denominator
    )


def load_expected_artifact_ledger() -> dict[tuple[int, int, str], dict]:
    transfer = json.loads(TRANSFER_REPORT.read_text(encoding="utf-8"))
    if transfer.get("uses_realized_outcomes") is not False or \
            tuple(transfer.get("source_panels", ())) != SOURCE_PANELS:
        raise ValueError("stack-core/shell transfer source differs")
    ledger = {}
    for row in transfer.get("source_artifacts", []):
        seed = int(row["seed"])
        block = REGISTERED_BLOCKS[seed]
        key = (int(row["season"]), int(row["week"]), block)
        if key in ledger:
            raise ValueError("stack-core/shell transfer artifact repeats")
        ledger[key] = row
    if len(ledger) != 270:
        raise ValueError("stack-core/shell transfer artifact grid differs")
    return ledger


def _correlations(
    vectors: Mapping[str, Sequence[int]],
) -> dict[str, object]:
    pairs = []
    finite = []
    for left_index, left in enumerate(REGISTERED_BLOCKS):
        for right in REGISTERED_BLOCKS[left_index + 1:]:
            value = _pearson(vectors[left], vectors[right])
            pairs.append({"left": left, "right": right, "pearson": value})
            if value is not None:
                finite.append(value)
    return {
        "pairs": pairs,
        "finite_pairs": len(finite),
        "mean_correlation": float(sum(finite) / len(finite)) if finite else None,
        "mean_absolute_correlation": (
            float(sum(abs(value) for value in finite) / len(finite))
            if finite else None
        ),
        "max_absolute_correlation": (
            float(max(abs(value) for value in finite)) if finite else None
        ),
        "diagnostic_only": True,
        "folds_are_independent": False,
    }


def aggregate(shard_paths: Sequence[Path]) -> dict[str, object]:
    paths = [Path(path) for path in shard_paths]
    if len(paths) != 54 or len(set(paths)) != 54:
        raise ValueError("stack-core/shell support requires 54 unique shards")
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
        raise ValueError("stack-core/shell support slate grid differs")

    expected_artifacts = load_expected_artifact_ledger()
    expected_hashes = validate_local_sources()
    first = shards[0]
    common = {
        key: first.get(key) for key in (
            "run_id", "code_sha", "analysis_image", "protocol_sha256",
            "source_hashes", "source_panels",
        )
    }
    if common != {
        "run_id": RUN_ID,
        "code_sha": common["code_sha"],
        "analysis_image": common["analysis_image"],
        "protocol_sha256": PROTOCOL_SHA256,
        "source_hashes": expected_hashes,
        "source_panels": list(SOURCE_PANELS),
    } or not re.fullmatch(r"[0-9a-f]{40}", str(common["code_sha"])) or \
            not re.fullmatch(
                r".+@sha256:[0-9a-f]{64}", str(common["analysis_image"]),
            ):
        raise ValueError("stack-core/shell support common identity differs")

    counts = {
        layer: {
            block: {str(int(line)): [] for line in SUPPORT_THRESHOLDS}
            for block in REGISTERED_BLOCKS
        }
        for layer in LAYERS
    }
    cells = []
    artifact_population = []
    required_keys = {
        "version", "run_id", "uses_realized_outcomes",
        "effect_fields_inspected", "treatment_constructed",
        "production_change_licensed", "historical_scoring_licensed",
        "season", "week", "code_sha", "analysis_image", "protocol_sha256",
        "source_hashes", "source_panels", "artifact_receipts", "folds",
    }
    for shard in shards:
        if set(shard) != required_keys or shard.get("version") != SHARD_VERSION or \
                shard.get("uses_realized_outcomes") is not False or \
                shard.get("effect_fields_inspected") is not False or \
                shard.get("treatment_constructed") is not False or \
                shard.get("production_change_licensed") is not False or \
                shard.get("historical_scoring_licensed") is not False or any(
                    shard.get(key) != value for key, value in common.items()
                ):
            raise ValueError("stack-core/shell support shard contract differs")
        season, week = int(shard["season"]), int(shard["week"])
        receipts = shard.get("artifact_receipts")
        if not isinstance(receipts, list) or len(receipts) != 5 or \
                [row.get("block") for row in receipts] != list(REGISTERED_BLOCKS):
            raise ValueError("stack-core/shell support artifact grid differs")
        for block, receipt in zip(REGISTERED_BLOCKS, receipts, strict=True):
            expected = expected_artifacts[(season, week, block)]
            canonical = SOURCE_PANELS[REGISTERED_BLOCKS.index(block)]
            raw_panel = (
                REPAIR_PANEL
                if (season, week, block) == (2025, 1, "R3")
                else canonical
            )
            exact = {
                "block": block,
                "source_panel": raw_panel,
                "canonical_panel": canonical,
                "candidate_rows": int(expected["candidate_rows"]),
                "uri": expected["uri"],
                "sha256": expected["sha256"],
                "generation": str(expected["generation"]),
                "updated": expected["updated"],
                "bytes": int(expected["bytes"]),
            }
            if receipt != exact:
                raise ValueError("stack-core/shell support artifact receipt differs")
            artifact_population.append(receipt)

        folds = shard.get("folds")
        if not isinstance(folds, list) or len(folds) != 5 or \
                [row.get("heldout_block") for row in folds] != list(REGISTERED_BLOCKS):
            raise ValueError("stack-core/shell support fold grid differs")
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
                raise ValueError("stack-core/shell support fold mechanics differ")
            threshold_counts = fold.get("threshold_counts")
            if not isinstance(threshold_counts, Mapping) or \
                    set(threshold_counts) != set(LAYERS):
                raise ValueError("stack-core/shell support layer grid differs")
            exact_counts = {}
            for layer in LAYERS:
                values = threshold_counts[layer]
                if not isinstance(values, Mapping) or set(values) != {
                    str(int(line)) for line in SUPPORT_THRESHOLDS
                }:
                    raise ValueError("stack-core/shell support threshold grid differs")
                exact_counts[layer] = {}
                for line in map(int, SUPPORT_THRESHOLDS):
                    value = values[str(line)]
                    if not isinstance(value, int) or not 0 <= value <= 10_000:
                        raise ValueError("stack-core/shell support count differs")
                    counts[layer][block][str(line)].append(value)
                    exact_counts[layer][str(line)] = value
            cells.append({
                "season": season,
                "week": week,
                "heldout_block": block,
                "worlds": 10_000,
                "control_entries": 80,
                "candidate_budget": fold["candidate_budget"],
                "threshold_counts": exact_counts,
            })

    if len(cells) != 270 or len(artifact_population) != 270:
        raise ValueError("stack-core/shell support population differs")
    distributions = {
        layer: {
            block: {
                str(line): {
                    **_support_distribution(counts[layer][block][str(line)]),
                    "slate_counts": [
                        {"season": season, "week": week, "events": int(value)}
                        for (season, week), value in zip(
                            expected_grid,
                            counts[layer][block][str(line)],
                            strict=True,
                        )
                    ],
                }
                for line in map(int, SUPPORT_THRESHOLDS)
            }
            for block in REGISTERED_BLOCKS
        }
        for layer in LAYERS
    }
    correlations = {
        layer: {
            str(line): _correlations({
                block: counts[layer][block][str(line)]
                for block in REGISTERED_BLOCKS
            })
            for line in map(int, SUPPORT_THRESHOLDS)
        }
        for layer in LAYERS
    }
    adequate = {
        str(anchor): all(
            distributions[layer][block][str(anchor)]["events"] >=
            AGGREGATE_MINIMUM
            and distributions[layer][block][str(anchor)]["positive_slates"] >=
            POSITIVE_SLATE_MINIMUM
            for layer in LAYERS for block in REGISTERED_BLOCKS
        )
        for anchor in ANCHOR_ORDER
    }
    selected_anchor = next(
        (anchor for anchor in ANCHOR_ORDER if adequate[str(anchor)]), None,
    )
    dispositions = {
        230: "p230-supported-stack-core-shell-treatment-licensed",
        220: "p220-supported-stack-core-shell-treatment-licensed",
        210: "p210-supported-stack-core-shell-treatment-licensed",
        None: "terminal-insufficient-stack-core-shell-support",
    }
    global_counts = {
        layer: {
            str(line): {
                "events": int(sum(
                    distributions[layer][block][str(line)]["events"]
                    for block in REGISTERED_BLOCKS
                )),
                "worlds": 2_700_000,
                "positive_cells": int(sum(
                    value > 0
                    for block in REGISTERED_BLOCKS
                    for value in counts[layer][block][str(line)]
                )),
                "cells": 270,
            }
            for line in map(int, SUPPORT_THRESHOLDS)
        }
        for layer in LAYERS
    }
    return {
        "version": REPORT_VERSION,
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "effect_fields_inspected": False,
        "treatment_constructed": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "protocol_path": str(PROTOCOL),
        "protocol_sha256": PROTOCOL_SHA256,
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
            "layers_required": list(LAYERS),
            "aggregate_events_minimum_per_block": AGGREGATE_MINIMUM,
            "positive_slates_minimum_per_block": POSITIVE_SLATE_MINIMUM,
            "anchor_order": list(ANCHOR_ORDER),
        },
        "counts_by_layer_and_block": distributions,
        "fold_correlation_by_layer_and_threshold": correlations,
        "global_counts": global_counts,
        "adequate_by_threshold": adequate,
        "selected_anchor": selected_anchor,
        "disposition": dispositions[selected_anchor],
        "cells": cells,
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
        raise RuntimeError("immutable stack-core/shell support report exists")
    output.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print("STACK_CORE_SHELL_SUPPORT_AGGREGATED", report["disposition"])


if __name__ == "__main__":
    main()
