#!/usr/bin/env python3
"""Strictly aggregate the frozen constraint-lattice slate population."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
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
ROOT = Path(__file__).resolve().parents[1]
CBWU_REPORT = (
    ROOT / "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json"
)
CBWU_REPORT_SHA256 = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)
SOURCE_PANELS = tuple(
    f"20260813-sis-asoe-treatment-r{seed}-v1" for seed in range(5)
)
BLOCK_TO_PANEL = dict(zip(REGISTERED_BLOCKS, SOURCE_PANELS, strict=True))
FORENSIC_MANIFEST_SHA256 = (
    "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
)
EXPECTED_SOURCE_HASHES = {
    "reports/2026-08-16-constraint-lattice-scorefree-protocol.md":
        "f8591d24dd56749e5b56235f9636687fd41bd1a78991fdb60cfbb092ee65bf62",
    "reports/2026-08-16-constraint-lattice-source-and-execution-amendment.md":
        "35ea1f0dba3be5311631d51057c7667cb624bcdc19be75e2b202c57e297e8321",
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json":
        CBWU_REPORT_SHA256,
}
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


def load_expected_artifact_ledger() -> dict[tuple[int, int, str], dict]:
    """Load the exact 270-artifact ledger frozen by the passed CBWU-OI report."""
    raw = CBWU_REPORT.read_bytes()
    if sha256(raw).hexdigest() != CBWU_REPORT_SHA256:
        raise ValueError("constraint-lattice CBWU source report hash differs")
    report = json.loads(raw)
    if report.get("version") != "cbwu-order-invariant-repair-scorefree-v1" or \
            report.get("uses_realized_outcomes") is not False or \
            tuple(report.get("source_panels", ())) != SOURCE_PANELS or \
            report.get("forensic_manifest_sha256") != FORENSIC_MANIFEST_SHA256 or \
            report.get("aggregate", {}).get("passes_scorefree_gate") is not True or \
            report.get("aggregate", {}).get("slates") != 54:
        raise ValueError("constraint-lattice CBWU source report identity differs")
    artifacts = report.get("source_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 270:
        raise ValueError("constraint-lattice CBWU source ledger is incomplete")
    panel_to_block = {panel: block for block, panel in BLOCK_TO_PANEL.items()}
    ledger = {}
    for row in artifacts:
        panel = str(row.get("panel_run_id", ""))
        if panel not in panel_to_block:
            raise ValueError("constraint-lattice CBWU source panel differs")
        block = panel_to_block[panel]
        if row.get("seed") != REGISTERED_BLOCKS.index(block):
            raise ValueError("constraint-lattice CBWU source seed differs")
        key = (int(row["season"]), int(row["week"]), block)
        if key in ledger:
            raise ValueError("constraint-lattice CBWU source ledger repeats")
        ledger[key] = row
    expected = {
        (season, week, block)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
        for block in REGISTERED_BLOCKS
    }
    if set(ledger) != expected:
        raise ValueError("constraint-lattice CBWU source grid differs")
    return ledger


def _validate_fold(row: Mapping, season: int, week: int, block: str) -> None:
    if row.get("version") != VERSION or \
            row.get("uses_realized_outcomes") is not False or \
            row.get("mechanical_valid") is not True or \
            row.get("season") != season or row.get("week") != week or \
            row.get("heldout_block") != block or row.get("worlds") != 10_000 or \
            row.get("control_entries") != 80 or \
            row.get("treatment_entries") != 80:
        raise ValueError("constraint-lattice fold identity/mechanics differ")
    control_rosters = row.get("control_rosters")
    treatment_rosters = row.get("treatment_rosters")
    if not _roster_grid(control_rosters, rows=80) or \
            not _roster_grid(treatment_rosters, rows=80):
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
    candidate_rosters = row.get("control_candidate_rosters")
    source_rows = row.get("candidate_source_aggregation")
    if not isinstance(source_rows, list) or len(source_rows) != candidate_budget:
        raise ValueError("constraint-lattice source aggregation differs")
    for source, roster in zip(source_rows, candidate_rosters, strict=True):
        if sorted(source) != ["roster", "sources", "tags"] or \
                source["roster"] != roster or not source["sources"] or \
                source["sources"] != sorted(set(source["sources"])) or \
                not set(source["sources"]) <= set(training) or \
                not isinstance(source["tags"], list) or \
                not all(isinstance(tag, str) for tag in source["tags"]) or \
                source["tags"] != sorted(set(source["tags"])):
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
                not len(retained) <= item["attempted_worlds"] <= 10_000 or \
                not isinstance(item.get("duplicate_world_solutions"), int) or \
                not 0 <= item["duplicate_world_solutions"] <= item["attempted_worlds"] or \
                not isinstance(item.get("structurally_infeasible"), bool) or \
                not isinstance(item.get("elapsed_seconds"), (int, float)) or \
                not math.isfinite(float(item["elapsed_seconds"])) or \
                item["elapsed_seconds"] < 0:
            raise ValueError("constraint-lattice generation receipt differs")
        for retained_row in retained:
            if sorted(retained_row) != ["bound", "exact_score", "roster", "world"] or \
                    not isinstance(retained_row["world"], int) or \
                    not 0 <= retained_row["world"] < 10_000 or \
                    not isinstance(retained_row["roster"], list) or \
                    len(retained_row["roster"]) != 9 or \
                    len(set(map(str, retained_row["roster"]))) != 9 or \
                    not math.isfinite(float(retained_row["bound"])) or \
                    not math.isfinite(float(retained_row["exact_score"])):
                raise ValueError("constraint-lattice retained solve differs")
    raw_count = row.get("raw_exception_candidates")
    retained_count = row.get("retained_exception_candidates")
    new_count = row.get("new_exception_entries")
    if not isinstance(raw_count, int) or raw_count != sum(
            len(item["retained"]) for item in generation
    ) or raw_count > 40 or not isinstance(retained_count, int) or \
            not 0 <= retained_count <= 8 or not isinstance(new_count, int) or \
            not 0 <= new_count <= 8 or \
            not isinstance(row.get("elapsed_seconds"), (int, float)) or \
            not math.isfinite(float(row["elapsed_seconds"])) or \
            row["elapsed_seconds"] < 0:
        raise ValueError("constraint-lattice exception/runtime mechanics differ")
    ranking = row.get("candidate_ranking")
    admission = row.get("admission")
    if not isinstance(ranking, list) or len(ranking) != retained_count or \
            not isinstance(admission, Mapping) or \
            len(admission.get("admitted", ())) + len(admission.get("rejected", ())) \
            != retained_count or len(admission.get("admitted", ())) != new_count:
        raise ValueError("constraint-lattice ranking/admission mechanics differ")
    control_keys = {tuple(map(str, roster)) for roster in control_rosters}
    treatment_keys = {tuple(map(str, roster)) for roster in treatment_rosters}
    shared = len(control_keys & treatment_keys)
    if row.get("shared_rosters") != shared or new_count != 80 - shared or \
            set(row.get("exception_counts", {})) != set(CELL_ORDER) or \
            sum(int(value) for value in row["exception_counts"].values()) != new_count:
        raise ValueError("constraint-lattice treatment identity mechanics differ")


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
    expected_artifacts = load_expected_artifact_ledger()
    first = shards[0]
    common = {
        key: first.get(key) for key in (
            "run_id", "code_sha", "analysis_image", "source_hashes",
            "source_panels", "forensic_manifest_sha256", "protocol_receipt",
        )
    }
    if common["run_id"] != RUN_ID or \
            common["protocol_receipt"] != protocol_receipt() or \
            common["source_hashes"] != EXPECTED_SOURCE_HASHES or \
            tuple(common["source_panels"] or ()) != SOURCE_PANELS or \
            common["forensic_manifest_sha256"] != FORENSIC_MANIFEST_SHA256:
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
