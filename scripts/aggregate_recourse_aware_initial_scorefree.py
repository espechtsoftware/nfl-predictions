#!/usr/bin/env python3
"""Strictly aggregate the frozen recourse-aware initial-book population."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS
from nfl_dfs.analysis.recourse_aware_initial import (
    ALTERNATIVE_CAP,
    TAILS,
    VERSION,
    aggregate_scorefree_folds,
)

from aggregate_constraint_lattice_scorefree import (
    EXPECTED_SOURCE_HASHES as LATTICE_SOURCE_HASHES,
    load_expected_artifact_ledger,
)
from run_recourse_aware_initial_scorefree import (
    CBWU_REPORT_SHA256,
    EXECUTION_PROTOCOL,
    EXECUTION_PROTOCOL_SHA256,
    FORENSIC_MANIFEST_SHA256,
    RUN_ID,
    SCIENCE_PROTOCOL,
    SCIENCE_PROTOCOL_SHA256,
    SOURCE_PANELS,
)


SHARD_VERSION = "recourse-aware-initial-book-scorefree-shard-v1"
REPORT_VERSION = "recourse-aware-initial-book-scorefree-report-v1"
EXPECTED_SOURCE_HASHES = {
    **LATTICE_SOURCE_HASHES,
    str(SCIENCE_PROTOCOL): SCIENCE_PROTOCOL_SHA256,
    str(EXECUTION_PROTOCOL): EXECUTION_PROTOCOL_SHA256,
}
FORBIDDEN_KEYS = {
    "actual_score", "final_score", "actual_rank", "actual_ownership",
    "selected_rank", "contest_rank", "payout", "roi", "labels_complete",
}


def _assert_no_outcomes(value, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"recourse-aware outcome field at {path}.{key}")
            _assert_no_outcomes(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_outcomes(child, f"{path}[{index}]")


def _roster_grid(value, *, rows: int) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == rows
        and all(
            isinstance(roster, list)
            and roster == sorted(map(str, roster))
            and len(roster) == 9
            and len(set(roster)) == 9
            for roster in value
        )
        and len({tuple(roster) for roster in value}) == rows
    )


def _validate_metric_book(value: Mapping, candidate_budget: int) -> None:
    if value.get("version") != VERSION or \
            value.get("uses_realized_outcomes") is not False or \
            value.get("entries") != 80 or value.get("worlds") != 10_000:
        raise ValueError("recourse-aware metric-book identity differs")
    expected_tails = {str(int(threshold)) for threshold in TAILS}
    for family in ("initial_coverage", "reachable_union_coverage"):
        coverage = value.get(family)
        if not isinstance(coverage, Mapping) or set(coverage) != expected_tails:
            raise ValueError("recourse-aware metric-book tail grid differs")
        previous = None
        for threshold in sorted((int(raw) for raw in coverage), reverse=True):
            row = coverage[str(threshold)]
            if not isinstance(row, Mapping) or set(row) != {"events", "rate"}:
                raise ValueError("recourse-aware metric-book tail row differs")
            events, rate = row["events"], row["rate"]
            if type(events) is not int or not 0 <= events <= 10_000 or \
                    not isinstance(rate, (int, float)) or not math.isfinite(rate) or \
                    not np.isclose(rate, events / 10_000, rtol=0.0, atol=1e-12) or \
                    (previous is not None and events < previous):
                raise ValueError("recourse-aware metric-book tail value differs")
            previous = events
    reachable = value.get("reachable_alternatives")
    alternatives = value.get("alternatives_per_entry")
    if type(reachable) is not int or not 1 <= reachable <= candidate_budget or \
            not isinstance(alternatives, Mapping) or set(alternatives) != {
                "minimum", "median", "mean", "maximum"
            }:
        raise ValueError("recourse-aware alternative breadth differs")
    minimum, median_value, mean_value, maximum = (
        alternatives["minimum"], alternatives["median"],
        alternatives["mean"], alternatives["maximum"],
    )
    if type(minimum) is not int or type(maximum) is not int or \
            not 1 <= minimum <= median_value <= maximum <= ALTERNATIVE_CAP or \
            not minimum <= mean_value <= maximum:
        raise ValueError("recourse-aware alternative distribution differs")

    locked_counts = value.get("locked_slot_count_distribution")
    slot_counts = value.get("locked_slot_index_distribution")
    if not isinstance(locked_counts, Mapping) or set(locked_counts) != {
        str(index) for index in range(10)
    } or not isinstance(slot_counts, Mapping) or set(slot_counts) != {
        str(index) for index in range(9)
    } or any(type(raw) is not int or raw < 0 for raw in locked_counts.values()) or \
            any(type(raw) is not int or raw < 0 for raw in slot_counts.values()) or \
            sum(locked_counts.values()) != 80:
        raise ValueError("recourse-aware locked-slot distribution differs")
    locked_total = sum(
        index * locked_counts[str(index)] for index in range(10)
    )
    if sum(slot_counts.values()) != locked_total:
        raise ValueError("recourse-aware locked-slot total differs")
    players = value.get("locked_player_frequency")
    if not isinstance(players, list) or players != sorted(
        players, key=lambda row: str(row.get("player_id", ""))
    ) or len({str(row.get("player_id", "")) for row in players}) != len(players) or \
            any(
                set(row) != {"player_id", "entries"}
                or not str(row["player_id"])
                or type(row["entries"]) is not int
                or not 1 <= row["entries"] <= 80
                for row in players
            ) or sum(row["entries"] for row in players) != locked_total:
        raise ValueError("recourse-aware locked-player distribution differs")
    signatures = value.get("locked_signature_frequency")
    if not isinstance(signatures, list) or not signatures or \
            sum(int(row.get("entries", 0)) for row in signatures) != 80 or \
            value.get("distinct_locked_slot_signatures") != len(signatures):
        raise ValueError("recourse-aware locked-signature distribution differs")
    canonical = []
    for row in signatures:
        signature = row.get("signature")
        if set(row) != {"signature", "entries"} or \
                type(row["entries"]) is not int or row["entries"] <= 0 or \
                not isinstance(signature, list) or len(signature) > 9 or any(
                    not isinstance(item, list) or len(item) != 2
                    or type(item[0]) is not int or not 0 <= item[0] < 9
                    or not str(item[1]) for item in signature
                ) or len({item[0] for item in signature}) != len(signature) or \
                len({str(item[1]) for item in signature}) != len(signature):
            raise ValueError("recourse-aware locked signature is malformed")
        canonical.append(tuple((item[0], str(item[1])) for item in signature))
    if canonical != sorted(canonical) or len(set(canonical)) != len(canonical):
        raise ValueError("recourse-aware locked signature order differs")


def _validate_fold(row: Mapping, season: int, week: int, block: str) -> None:
    candidate_budget = row.get("candidate_budget")
    expected_training = [value for value in REGISTERED_BLOCKS if value != block]
    if row.get("version") != VERSION or \
            row.get("uses_realized_outcomes") is not False or \
            row.get("season") != season or row.get("week") != week or \
            row.get("heldout_block") != block or \
            row.get("training_blocks") != expected_training or \
            type(candidate_budget) is not int or candidate_budget < 80 or \
            row.get("alternative_cap") != ALTERNATIVE_CAP:
        raise ValueError("recourse-aware fold identity/mechanics differ")
    control = row.get("control")
    treatment = row.get("treatment")
    if not isinstance(control, Mapping) or not isinstance(treatment, Mapping):
        raise ValueError("recourse-aware fold metric books are absent")
    _validate_metric_book(control, candidate_budget)
    _validate_metric_book(treatment, candidate_budget)
    control_rosters = row.get("control_selected_rosters")
    treatment_rosters = row.get("treatment_selected_rosters")
    if not _roster_grid(control_rosters, rows=80) or \
            not _roster_grid(treatment_rosters, rows=80):
        raise ValueError("recourse-aware fold exact-80 roster grid differs")
    overlap = len({tuple(value) for value in control_rosters} & {
        tuple(value) for value in treatment_rosters
    })
    if row.get("selected_identity_overlap") != overlap or \
            not np.isclose(
                row.get("selected_identity_jaccard", -1),
                overlap / (160 - overlap),
                rtol=0.0,
                atol=1e-12,
            ):
        raise ValueError("recourse-aware selected identity overlap differs")


def aggregate(shard_paths: Sequence[Path]) -> dict:
    paths = [Path(path) for path in shard_paths]
    if len(paths) != 54 or len(set(paths)) != 54:
        raise ValueError("recourse-aware aggregate requires 54 unique shards")
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
        raise ValueError("recourse-aware shard season/week grid differs")
    expected_artifacts = load_expected_artifact_ledger()
    first = shards[0]
    common = {
        key: first.get(key) for key in (
            "run_id", "code_sha", "analysis_image", "source_hashes",
            "source_panels", "forensic_manifest_sha256", "cbwu_report_sha256",
        )
    }
    if common != {
        "run_id": RUN_ID,
        "code_sha": common["code_sha"],
        "analysis_image": common["analysis_image"],
        "source_hashes": EXPECTED_SOURCE_HASHES,
        "source_panels": list(SOURCE_PANELS),
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "cbwu_report_sha256": CBWU_REPORT_SHA256,
    } or not isinstance(common["code_sha"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", common["code_sha"],
    ) or not isinstance(common["analysis_image"], str) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", common["analysis_image"],
    ):
        raise ValueError("recourse-aware aggregate identity differs")

    all_folds = []
    artifact_receipts = []
    for shard in shards:
        if shard.get("version") != SHARD_VERSION or \
                shard.get("uses_realized_outcomes") is not False or \
                shard.get("production_change_licensed") is not False or \
                shard.get("historical_scoring_licensed") is not False or any(
                    shard.get(key) != value for key, value in common.items()
                ):
            raise ValueError("recourse-aware shard binding differs")
        season, week = int(shard["season"]), int(shard["week"])
        decision = pd.Timestamp(shard.get("decision_time"))
        if decision.tzinfo is None or decision.tz_convert(
            "America/New_York"
        ).strftime("%H:%M") != "15:55":
            raise ValueError("recourse-aware decision time differs")
        folds = shard.get("folds")
        if not isinstance(folds, list) or len(folds) != 5 or [
            row.get("heldout_block") for row in folds
        ] != list(REGISTERED_BLOCKS):
            raise ValueError("recourse-aware shard fold grid differs")
        for block, fold in zip(REGISTERED_BLOCKS, folds, strict=True):
            _validate_fold(fold, season, week, block)
            all_folds.append(fold)
        receipts = shard.get("artifact_receipts")
        if not isinstance(receipts, list) or len(receipts) != 5 or [
            row.get("block") for row in receipts
        ] != list(REGISTERED_BLOCKS):
            raise ValueError("recourse-aware artifact receipt grid differs")
        for block, receipt in zip(REGISTERED_BLOCKS, receipts, strict=True):
            expected = expected_artifacts[(season, week, block)]
            exact = {
                "source_panel": expected["panel_run_id"],
                "candidate_rows": int(expected["candidate_rows"]),
                "uri": expected["uri"],
                "sha256": expected["sha256"],
                "generation": str(expected["generation"]),
                "updated": expected["updated"],
                "bytes": int(expected["bytes"]),
            }
            if receipt.get("block") != block or any(
                receipt.get(key) != value for key, value in exact.items()
            ):
                raise ValueError("recourse-aware artifact receipt differs")
        artifact_receipts.extend(receipts)
    if len(all_folds) != 270 or len(artifact_receipts) != 270 or len({
        (row["block"], row["uri"], row["generation"])
        for row in artifact_receipts
    }) != 270:
        raise ValueError("recourse-aware aggregate source population differs")

    report = aggregate_scorefree_folds(all_folds)
    if report.get("version") != REPORT_VERSION:
        raise ValueError("recourse-aware aggregate report version differs")
    return {
        **report,
        "run_id": RUN_ID,
        **{key: value for key, value in common.items() if key != "run_id"},
        "source_artifacts": artifact_receipts,
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
    print("RECOURSE_INITIAL_AGGREGATE_VALIDATED", result["disposition"])


if __name__ == "__main__":
    main()
