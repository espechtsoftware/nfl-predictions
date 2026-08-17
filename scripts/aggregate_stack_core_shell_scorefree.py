#!/usr/bin/env python3
"""Strictly aggregate the score-free stack-core x shell treatment grid."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import math
from pathlib import Path
import re

from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS, REPORT_THRESHOLDS
from nfl_dfs.analysis.stack_core_shell import (
    BEAM_LIMIT,
    CORE_LIMIT,
    PROPOSAL_LIMIT,
    SHELL_LIMIT,
    VERSION,
    aggregate_gate,
)
from aggregate_stack_core_shell_support_census import (
    load_expected_artifact_ledger,
)
from run_stack_core_shell_scorefree import (
    RUN_ID,
    SUPPORT_RUN_ID,
    SUPPORT_URI,
)
from stack_core_shell_sources import (
    PROTOCOL,
    PROTOCOL_SHA256,
    REPAIR_PANEL,
    SOURCE_PANELS,
    validate_local_sources,
)


REPORT_VERSION = "stack-core-shell-scorefree-report-v1"
SHARD_VERSION = "stack-core-shell-scorefree-shard-v1"
FORBIDDEN_KEYS = {
    "actual_score", "actual_rank", "actual_ownership", "selected_rank",
    "payout", "contest_rank", "labels_complete", "exception_counts",
}


def _assert_no_forbidden(value, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(
                    f"stack-core/shell forbidden field at {path}.{key}"
                )
            _assert_no_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden(child, f"{path}[{index}]")


def _validate_rosters(rows, expected: int, name: str) -> None:
    if not isinstance(rows, list) or len(rows) != expected:
        raise ValueError(f"stack-core/shell {name} roster count differs")
    normalized = []
    for roster in rows:
        if not isinstance(roster, list) or len(roster) != 9 or \
                len({str(value) for value in roster}) != 9:
            raise ValueError(f"stack-core/shell {name} roster differs")
        normalized.append(tuple(str(value) for value in roster))
    if len(set(normalized)) != expected:
        raise ValueError(f"stack-core/shell {name} roster identity repeats")


def _finite_rank(value: Mapping, name: str) -> None:
    if set(value) != {"covariance", "correlation"}:
        raise ValueError(f"stack-core/shell {name} effective rank differs")
    for row in value.values():
        if set(row) != {
            "participation_ratio", "entropy_effective_rank",
            "top_five_variance_share",
        } or any(not math.isfinite(float(number)) for number in row.values()):
            raise ValueError(f"stack-core/shell {name} effective rank is invalid")


def _validate_fold(
    row: Mapping,
    *,
    season: int,
    week: int,
    block: str,
) -> None:
    required = {
        "version", "uses_realized_outcomes", "mechanical_valid", "season",
        "week", "heldout_block", "worlds", "candidate_budget",
        "selected_entries", "candidate_shared_rosters", "candidate_new_rosters",
        "selected_shared_rosters", "selected_new_rosters", "admitted_proposals",
        "proposal_counts", "threshold_counts", "structure",
        "score_effective_rank", "candidate_control_rosters",
        "candidate_treatment_rosters", "selected_control_rosters",
        "selected_treatment_rosters", "training_blocks",
        "training_union_candidates", "component_library", "beam_candidates",
        "proposal_candidates", "proposals", "elapsed_seconds",
    }
    if set(row) != required or row.get("version") != VERSION or \
            row.get("uses_realized_outcomes") is not False or \
            row.get("mechanical_valid") is not True or \
            row.get("season") != season or row.get("week") != week or \
            row.get("heldout_block") != block or row.get("worlds") != 10_000 or \
            row.get("selected_entries") != 80 or \
            row.get("training_blocks") != [
                name for name in REGISTERED_BLOCKS if name != block
            ] or not isinstance(row.get("elapsed_seconds"), (int, float)) or \
            not math.isfinite(float(row["elapsed_seconds"])) or \
            float(row["elapsed_seconds"]) < 0:
        raise ValueError("stack-core/shell fold identity differs")
    budget = row.get("candidate_budget")
    if not isinstance(budget, int) or budget < 80 or \
            not isinstance(row.get("training_union_candidates"), int) or \
            row["training_union_candidates"] < budget:
        raise ValueError("stack-core/shell candidate budget differs")
    if row.get("candidate_shared_rosters") + row.get("candidate_new_rosters") != budget or \
            row.get("selected_shared_rosters") + row.get("selected_new_rosters") != 80 or \
            not 0 <= row.get("admitted_proposals", -1) <= PROPOSAL_LIMIT:
        raise ValueError("stack-core/shell treatment overlap differs")
    _validate_rosters(row["candidate_control_rosters"], budget, "candidate control")
    _validate_rosters(row["candidate_treatment_rosters"], budget, "candidate treatment")
    _validate_rosters(row["selected_control_rosters"], 80, "selected control")
    _validate_rosters(row["selected_treatment_rosters"], 80, "selected treatment")
    candidate_control = {tuple(value) for value in row["candidate_control_rosters"]}
    candidate_treatment = {
        tuple(value) for value in row["candidate_treatment_rosters"]
    }
    selected_control = {tuple(value) for value in row["selected_control_rosters"]}
    selected_treatment = {tuple(value) for value in row["selected_treatment_rosters"]}
    if len(candidate_control & candidate_treatment) != row["candidate_shared_rosters"] or \
            len(candidate_treatment - candidate_control) != row["candidate_new_rosters"] or \
            len(selected_control & selected_treatment) != row["selected_shared_rosters"] or \
            len(selected_treatment - selected_control) != row["selected_new_rosters"] or \
            len(candidate_treatment - candidate_control) != row["admitted_proposals"] or \
            not selected_control <= candidate_control or \
            not selected_treatment <= candidate_treatment:
        raise ValueError("stack-core/shell roster overlap receipt differs")

    library = row.get("component_library")
    if not isinstance(library, Mapping) or set(library) != {
        "source_lineups", "decompositions", "discovered_cores",
        "discovered_shells", "retained_cores", "retained_shells",
        "core_qb_counts", "core_game_counts", "cores", "shells",
    } or library.get("source_lineups") != budget or \
            library.get("retained_cores") != CORE_LIMIT or \
            library.get("retained_shells") != SHELL_LIMIT or \
            len(library.get("cores", [])) != CORE_LIMIT or \
            len(library.get("shells", [])) != SHELL_LIMIT or \
            not isinstance(library.get("decompositions"), int) or \
            library["decompositions"] < CORE_LIMIT or \
            not isinstance(library.get("discovered_cores"), int) or \
            library["discovered_cores"] < CORE_LIMIT or \
            not isinstance(library.get("discovered_shells"), int) or \
            library["discovered_shells"] < SHELL_LIMIT or \
            not isinstance(library.get("core_qb_counts"), Mapping) or \
            not isinstance(library.get("core_game_counts"), Mapping) or \
            sum(library["core_qb_counts"].values()) != CORE_LIMIT or \
            sum(library["core_game_counts"].values()) != CORE_LIMIT or \
            max(library["core_qb_counts"].values()) > 4 or \
            max(library["core_game_counts"].values()) > 8:
        raise ValueError("stack-core/shell component library differs")
    for component in library["cores"]:
        if set(component) != {"players", "rank", "parent", "qb", "game"} or \
                len(component["players"]) != 4 or len(set(component["players"])) != 4 or \
                len(component["parent"]) != 9 or len(set(component["parent"])) != 9 or \
                len(component["rank"]) != 7 or not component["qb"] or not component["game"] or \
                any(not math.isfinite(float(value)) for value in component["rank"]):
            raise ValueError("stack-core/shell core receipt differs")
    for component in library["shells"]:
        if set(component) != {"players", "rank", "parent"} or \
                len(component["players"]) != 5 or len(set(component["players"])) != 5 or \
                len(component["parent"]) != 9 or len(set(component["parent"])) != 9 or \
                len(component["rank"]) != 7 or any(
                    not math.isfinite(float(value)) for value in component["rank"]
                ):
            raise ValueError("stack-core/shell shell receipt differs")
    if len({tuple(value["players"]) for value in library["cores"]}) != CORE_LIMIT or \
            len({tuple(value["players"]) for value in library["shells"]}) != SHELL_LIMIT:
        raise ValueError("stack-core/shell component identity repeats")
    if row.get("beam_candidates") != BEAM_LIMIT or \
            row.get("proposal_candidates") != PROPOSAL_LIMIT or \
            len(row.get("proposals", [])) != PROPOSAL_LIMIT:
        raise ValueError("stack-core/shell proposal book differs")
    proposals = row["proposals"]
    if len({tuple(value.get("roster", ())) for value in proposals}) != PROPOSAL_LIMIT or any(
        set(value) != {"roster", "core", "shell", "rank"}
        or len(value["roster"]) != 9 or value["roster"] != sorted(value["roster"])
        or len(value["core"]) != 4
        or len(value["shell"]) != 5
        or set(value["core"]) & set(value["shell"])
        or set(value["roster"]) != set(value["core"]) | set(value["shell"])
        or tuple(value["roster"]) in candidate_control
        or len(value["rank"]) != 7
        or any(not math.isfinite(float(number)) for number in value["rank"])
        for value in proposals
    ):
        raise ValueError("stack-core/shell proposal receipt differs")
    proposal_rosters = {tuple(value["roster"]) for value in proposals}
    if not candidate_treatment - candidate_control <= proposal_rosters:
        raise ValueError("stack-core/shell admitted proposal binding differs")
    proposal_counts = row.get("proposal_counts")
    if not isinstance(proposal_counts, Mapping) or set(proposal_counts) != {
        "legal_crosses", "existing_control_crosses", "duplicate_crosses",
        "unique_recombinants", "covered_core_shell_pairs",
    } or any(not isinstance(value, int) or value < 0 for value in proposal_counts.values()) or \
            proposal_counts["unique_recombinants"] < BEAM_LIMIT or \
            proposal_counts["legal_crosses"] < \
            proposal_counts["unique_recombinants"] or \
            proposal_counts["covered_core_shell_pairs"] < \
            (20 + PROPOSAL_LIMIT - 1):
        raise ValueError("stack-core/shell proposal counts differ")

    thresholds = row.get("threshold_counts")
    if not isinstance(thresholds, Mapping) or set(thresholds) != {
        "candidate", "selected",
    }:
        raise ValueError("stack-core/shell threshold layer differs")
    expected_lines = {str(int(line)) for line in REPORT_THRESHOLDS}
    for layer in ("candidate", "selected"):
        if set(thresholds[layer]) != {"control", "treatment"}:
            raise ValueError("stack-core/shell threshold book differs")
        for book in ("control", "treatment"):
            values = thresholds[layer][book]
            if set(values) != expected_lines or any(
                not isinstance(value, int) or not 0 <= value <= 10_000
                for value in values.values()
            ):
                raise ValueError("stack-core/shell threshold count differs")
    structure = row.get("structure")
    expected_structure = {
        "unique_players", "unique_player_pairs", "unique_qb_stack_cores",
        "unique_dominant_games",
    }
    if not isinstance(structure, Mapping) or set(structure) != {
        "candidate", "selected",
    }:
        raise ValueError("stack-core/shell structure layers differ")
    for layer in ("candidate", "selected"):
        if set(structure[layer]) != {"control", "treatment"}:
            raise ValueError("stack-core/shell structure books differ")
        for values in structure[layer].values():
            if set(values) != expected_structure or any(
                not isinstance(value, int) or value < 1 for value in values.values()
            ):
                raise ValueError("stack-core/shell structure reach differs")
    ranks = row.get("score_effective_rank")
    if not isinstance(ranks, Mapping) or set(ranks) != {"candidate", "selected"}:
        raise ValueError("stack-core/shell rank layers differ")
    for layer in ("candidate", "selected"):
        if set(ranks[layer]) != {"control", "treatment"}:
            raise ValueError("stack-core/shell rank books differ")
        for book, value in ranks[layer].items():
            _finite_rank(value, f"{layer}/{book}")


def aggregate(shard_paths: Sequence[Path]) -> dict[str, object]:
    paths = [Path(path) for path in shard_paths]
    if len(paths) != 54 or len(set(paths)) != 54:
        raise ValueError("stack-core/shell requires 54 unique shards")
    shards = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    for shard in shards:
        _assert_no_forbidden(shard)
    shards.sort(key=lambda row: (int(row["season"]), int(row["week"])))
    grid = [(season, week) for season in (2023, 2024, 2025) for week in range(1, 19)]
    if [(row.get("season"), row.get("week")) for row in shards] != grid:
        raise ValueError("stack-core/shell slate grid differs")
    expected_hashes = validate_local_sources()
    expected_artifacts = load_expected_artifact_ledger()
    first = shards[0]
    common = {
        key: first.get(key) for key in (
            "run_id", "code_sha", "analysis_image", "protocol_sha256",
            "source_hashes", "source_panels", "support_receipt",
        )
    }
    support = common["support_receipt"]
    if common.get("run_id") != RUN_ID or \
            not re.fullmatch(r"[0-9a-f]{40}", str(common["code_sha"])) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", str(common["analysis_image"])) or \
            common.get("protocol_sha256") != PROTOCOL_SHA256 or \
            common.get("source_hashes") != expected_hashes or \
            common.get("source_panels") != list(SOURCE_PANELS) or \
            not isinstance(support, Mapping) or support.get("uri") != SUPPORT_URI or \
            not re.fullmatch(r"[0-9a-f]{64}", str(support.get("sha256", ""))) or \
            support.get("selected_anchor") not in {230, 220, 210} or \
            support.get("disposition") != {
                230: "p230-supported-stack-core-shell-treatment-licensed",
                220: "p220-supported-stack-core-shell-treatment-licensed",
                210: "p210-supported-stack-core-shell-treatment-licensed",
            }[support.get("selected_anchor")]:
        raise ValueError("stack-core/shell common identity differs")
    required_shard = {
        "version", "run_id", "uses_realized_outcomes",
        "candidate_or_lineup_scores_read", "treatment_constructed",
        "effect_fields_generated", "production_change_licensed",
        "historical_scoring_licensed", "season", "week", "code_sha",
        "analysis_image", "protocol_sha256", "source_hashes", "source_panels",
        "support_receipt", "artifact_receipts", "slate",
    }
    folds = []
    artifacts = []
    for shard in shards:
        if set(shard) != required_shard or shard.get("version") != SHARD_VERSION or \
                shard.get("uses_realized_outcomes") is not False or \
                shard.get("candidate_or_lineup_scores_read") is not False or \
                shard.get("treatment_constructed") is not True or \
                shard.get("effect_fields_generated") is not True or \
                shard.get("production_change_licensed") is not False or \
                shard.get("historical_scoring_licensed") is not False or any(
                    shard.get(key) != value for key, value in common.items()
                ):
            raise ValueError("stack-core/shell shard contract differs")
        season, week = int(shard["season"]), int(shard["week"])
        receipts = shard.get("artifact_receipts")
        if not isinstance(receipts, list) or len(receipts) != 5 or \
                [row.get("block") for row in receipts] != list(REGISTERED_BLOCKS):
            raise ValueError("stack-core/shell artifact grid differs")
        for index, (block, receipt) in enumerate(
            zip(REGISTERED_BLOCKS, receipts, strict=True)
        ):
            expected = expected_artifacts[(season, week, block)]
            canonical = SOURCE_PANELS[index]
            raw_panel = REPAIR_PANEL if (season, week, block) == (2025, 1, "R3") \
                else canonical
            exact = {
                "block": block, "source_panel": raw_panel,
                "canonical_panel": canonical,
                "candidate_rows": int(expected["candidate_rows"]),
                "uri": expected["uri"], "sha256": expected["sha256"],
                "generation": str(expected["generation"]),
                "updated": expected["updated"], "bytes": int(expected["bytes"]),
            }
            if receipt != exact:
                raise ValueError("stack-core/shell artifact receipt differs")
            artifacts.append(receipt)
        slate = shard.get("slate")
        if not isinstance(slate, Mapping) or set(slate) != {
            "version", "uses_realized_outcomes", "season", "week", "folds",
            "elapsed_seconds",
        } or slate.get("version") != VERSION or \
                slate.get("uses_realized_outcomes") is not False or \
                slate.get("season") != season or slate.get("week") != week or \
                not isinstance(slate.get("elapsed_seconds"), (int, float)) or \
                not math.isfinite(float(slate["elapsed_seconds"])) or \
                float(slate["elapsed_seconds"]) < 0:
            raise ValueError("stack-core/shell slate receipt differs")
        slate_folds = slate.get("folds")
        if not isinstance(slate_folds, list) or len(slate_folds) != 5 or \
                [row.get("heldout_block") for row in slate_folds] != \
                list(REGISTERED_BLOCKS):
            raise ValueError("stack-core/shell fold grid differs")
        for block, row in zip(REGISTERED_BLOCKS, slate_folds, strict=True):
            _validate_fold(row, season=season, week=week, block=block)
            folds.append(row)
    if len(folds) != 270 or len(artifacts) != 270:
        raise ValueError("stack-core/shell population differs")
    gate = aggregate_gate(folds, selected_anchor=int(support["selected_anchor"]))
    return {
        "version": REPORT_VERSION,
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "treatment_constructed": True,
        "effect_fields_inspected": True,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "protocol_path": str(PROTOCOL),
        **common,
        "mechanical": {
            "seasons": [2023, 2024, 2025], "slates": 54,
            "heldout_folds": 270, "worlds_per_fold": 10_000,
            "source_artifacts": 270, "all_valid": True,
        },
        "gate": gate,
        "cells": folds,
        "disposition": gate["disposition"],
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
        raise RuntimeError("immutable stack-core/shell report exists")
    output.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print("STACK_CORE_SHELL_AGGREGATED", report["disposition"])


if __name__ == "__main__":
    main()
