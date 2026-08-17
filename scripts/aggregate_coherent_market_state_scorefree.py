#!/usr/bin/env python3
"""Strictly aggregate the frozen coherent market-state shard population."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence

from coherent_market_state_sources import (
    CBWU_REPORT,
    CBWU_REPORT_SHA256,
    EXECUTION_PROTOCOL,
    EXECUTION_PROTOCOL_SHA256,
    PROTOCOL,
    PROTOCOL_SHA256,
    REPAIR_COMPLETION,
    REPAIR_COMPLETION_SHA256,
    REPAIR_EXECUTION,
    REPAIR_EXECUTION_SHA256,
    REPAIR_PANEL,
    REPAIR_VALIDATION,
    REPAIR_VALIDATION_SHA256,
    SOURCE_PANELS,
    SUPPORT,
    SUPPORT_SHA256,
    TRANSFER_REPORT,
    TRANSFER_REPORT_SHA256,
)
from nfl_dfs.analysis.coherent_market_state import (
    ADDITION_COUNT,
    REGISTERED_BLOCKS,
    REPORT_SCOPES,
    REPORT_THRESHOLDS,
    STATE_ORDER,
    TEAM_LIMIT,
    VERSION,
    aggregate_heldout_gate,
    protocol_receipt,
)


SHARD_VERSION = "coherent-market-state-scorefree-shard-v1"
REPORT_VERSION = "coherent-market-state-scorefree-report-v1"
RUN_ID = "20260816-coherent-market-state-scorefree-v1"
EXPECTED_SOURCE_HASHES = {
    str(PROTOCOL): PROTOCOL_SHA256,
    str(SUPPORT): SUPPORT_SHA256,
    str(EXECUTION_PROTOCOL): EXECUTION_PROTOCOL_SHA256,
    str(TRANSFER_REPORT): TRANSFER_REPORT_SHA256,
    str(CBWU_REPORT): CBWU_REPORT_SHA256,
    str(REPAIR_VALIDATION): REPAIR_VALIDATION_SHA256,
    str(REPAIR_EXECUTION): REPAIR_EXECUTION_SHA256,
    str(REPAIR_COMPLETION): REPAIR_COMPLETION_SHA256,
}
FORBIDDEN_KEYS = {
    "actual", "actual_score", "actual_rank", "actual_ownership",
    "selected_rank", "payout", "contest_rank", "labels_complete",
}


def _assert_no_outcomes(value, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"coherent-state outcome field at {path}.{key}")
            _assert_no_outcomes(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_outcomes(child, f"{path}[{index}]")


def _roster_grid(value, *, rows: int) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == rows
        and all(
            isinstance(roster, list) and len(roster) == 9
            and len(set(map(str, roster))) == 9
            for roster in value
        )
        and len({tuple(sorted(map(str, roster))) for roster in value}) == rows
    )


def _validate_thresholds(value: Mapping) -> None:
    expected = {f"{threshold:g}" for threshold in REPORT_THRESHOLDS}
    if set(value) != expected or any(
        not isinstance(count, int) or count < 0 for count in value.values()
    ):
        raise ValueError("coherent-state threshold grid differs")


def _validate_fold(row: Mapping, season: int, week: int, block: str) -> None:
    if row.get("version") != VERSION or \
            row.get("uses_realized_outcomes") is not False or \
            row.get("mechanical_valid") is not True or \
            row.get("season") != season or row.get("week") != week or \
            row.get("heldout_block") != block or row.get("worlds") != 10_000 or \
            row.get("control_entries") != 80 or \
            row.get("treatment_entries") != 80 or \
            row.get("removed_candidates") != ADDITION_COUNT or \
            row.get("added_candidates") != ADDITION_COUNT:
        raise ValueError("coherent-state fold identity/mechanics differ")
    budget = row.get("candidate_budget")
    if not isinstance(budget, int) or budget < 80 or not _roster_grid(
        row.get("control_candidate_rosters"), rows=budget,
    ) or not _roster_grid(row.get("treatment_candidate_rosters"), rows=budget) or \
            not _roster_grid(row.get("control_selected_rosters"), rows=80) or \
            not _roster_grid(row.get("treatment_selected_rosters"), rows=80):
        raise ValueError("coherent-state candidate/selected roster grid differs")
    if row.get("shared_candidates") != budget - ADDITION_COUNT:
        raise ValueError("coherent-state fixed-budget identity overlap differs")

    training = row.get("training_blocks")
    if training != [value for value in REGISTERED_BLOCKS if value != block]:
        raise ValueError("coherent-state training-block identity differs")
    teams = row.get("team_states")
    if not isinstance(teams, list) or len(teams) != TEAM_LIMIT or \
            len({item.get("team") for item in teams}) != TEAM_LIMIT or any(
                not isinstance(item.get("disagreement"), (int, float))
                or not math.isfinite(float(item["disagreement"]))
                or float(item["disagreement"]) < 0
                or not item.get("qb_id")
                or len(item.get("covered_player_ids", ())) < 3
                for item in teams
            ):
        raise ValueError("coherent-state team receipt differs")
    expected_teams = [item["team"] for item in teams]

    additions = row.get("added")
    if not isinstance(additions, list) or len(additions) != ADDITION_COUNT or \
            Counter((item.get("team"), item.get("state")) for item in additions) != \
            Counter({
                (team, state): 2
                for team in expected_teams for state in STATE_ORDER
            }) or any(
                item.get("state_index") not in {1, 2}
                or item.get("anchor_block") not in training
                or not isinstance(item.get("anchor_world"), int)
                or not 0 <= item["anchor_world"] < 10_000
                or not _roster_grid([item.get("roster")], rows=1)
                for item in additions
            ):
        raise ValueError("coherent-state addition grid differs")
    removals = row.get("removed")
    if not isinstance(removals, list) or len(removals) != ADDITION_COUNT or any(
        not _roster_grid([item.get("roster")], rows=1)
        or len(item.get("training_tail_rank", ())) != 7
        or not item.get("sources") or not isinstance(item.get("tags"), list)
        for item in removals
    ):
        raise ValueError("coherent-state removal grid differs")

    generation = row.get("generation")
    if not isinstance(generation, list) or sum(
        item.get("accepted") is True for item in generation
    ) != ADDITION_COUNT or Counter(
        (item.get("team"), item.get("state"))
        for item in generation if item.get("accepted") is True
    ) != Counter({
        (team, state): 2 for team in expected_teams for state in STATE_ORDER
    }) or any(
        item.get("team") not in expected_teams
        or item.get("state") not in STATE_ORDER
        or item.get("anchor_block") not in training
        or not isinstance(item.get("anchor_rank"), int)
        or not 1 <= item["anchor_rank"] <= 64
        or not isinstance(item.get("elapsed_seconds"), (int, float))
        or not math.isfinite(float(item["elapsed_seconds"]))
        or item["elapsed_seconds"] < 0
        for item in generation
    ):
        raise ValueError("coherent-state generation receipt differs")
    accepted_rosters = [
        item.get("roster") for item in generation if item.get("accepted") is True
    ]
    if not _roster_grid(accepted_rosters, rows=ADDITION_COUNT):
        raise ValueError("coherent-state generated roster identities differ")

    counts = row.get("threshold_counts")
    if not isinstance(counts, Mapping) or set(counts) != set(REPORT_SCOPES):
        raise ValueError("coherent-state threshold scopes differ")
    for scope in REPORT_SCOPES:
        if set(counts[scope]) != {"control", "treatment"}:
            raise ValueError("coherent-state threshold books differ")
        for book in ("control", "treatment"):
            _validate_thresholds(counts[scope][book])
    structure = row.get("structure")
    effective_rank = row.get("effective_rank")
    for scope in REPORT_SCOPES:
        if set(structure.get(scope, {})) != {"control", "treatment"} or \
                set(effective_rank.get(scope, {})) != {"control", "treatment"}:
            raise ValueError("coherent-state structure/rank books differ")
        for book in ("control", "treatment"):
            if set(structure[scope][book]) != {
                "unique_players", "unique_player_pairs",
                "unique_qb_stack_cores", "unique_dominant_games",
            } or any(
                not isinstance(value, int) or value <= 0
                for value in structure[scope][book].values()
            ):
                raise ValueError("coherent-state structure receipt differs")
            rank = effective_rank[scope][book]
            if set(rank) != {"covariance", "correlation"}:
                raise ValueError("coherent-state effective rank differs")


def aggregate(shard_paths: Sequence[Path]) -> dict:
    paths = [Path(path) for path in shard_paths]
    if len(paths) != 54 or len(set(paths)) != 54:
        raise ValueError("coherent-state aggregate requires 54 unique shards")
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
        raise ValueError("coherent-state shard season/week grid differs")

    first = shards[0]
    common = {
        key: first.get(key) for key in (
            "run_id", "code_sha", "analysis_image", "source_hashes",
            "source_panels", "protocol_receipt",
        )
    }
    if common["run_id"] != RUN_ID or \
            common["source_hashes"] != EXPECTED_SOURCE_HASHES or \
            tuple(common["source_panels"] or ()) != SOURCE_PANELS or \
            common["protocol_receipt"] != protocol_receipt():
        raise ValueError("coherent-state aggregate identity differs")

    all_folds = []
    artifact_receipts = []
    slate_times = []
    selected_additions = Counter()
    for shard in shards:
        if shard.get("version") != SHARD_VERSION or \
                shard.get("uses_realized_outcomes") is not False or \
                shard.get("production_change_licensed") is not False or \
                shard.get("historical_scoring_licensed") is not False or any(
                    shard.get(key) != value for key, value in common.items()
                ):
            raise ValueError("coherent-state shard binding differs")
        season, week = int(shard["season"]), int(shard["week"])
        slate = shard.get("slate", {})
        if slate.get("version") != VERSION or \
                slate.get("uses_realized_outcomes") is not False or \
                slate.get("production_change_licensed") is not False or \
                slate.get("season") != season or slate.get("week") != week or \
                not isinstance(slate.get("elapsed_seconds"), (int, float)) or \
                slate["elapsed_seconds"] < 0:
            raise ValueError("coherent-state slate binding differs")
        folds = slate.get("folds")
        if not isinstance(folds, list) or len(folds) != 5 or [
            row.get("heldout_block") for row in folds
        ] != list(REGISTERED_BLOCKS):
            raise ValueError("coherent-state slate fold grid differs")
        for block, fold in zip(REGISTERED_BLOCKS, folds, strict=True):
            _validate_fold(fold, season, week, block)
            selected_additions.update({
                "total": int(fold["selected_additions"]),
                **{
                    f"state:{key}": int(value)
                    for key, value in fold["selected_additions_by_state"].items()
                },
                **{
                    f"team:{key}": int(value)
                    for key, value in fold["selected_additions_by_team"].items()
                },
            })
            all_folds.append(fold)
        receipts = shard.get("artifact_receipts")
        if not isinstance(receipts, list) or len(receipts) != 5 or [
            row.get("block") for row in receipts
        ] != list(REGISTERED_BLOCKS):
            raise ValueError("coherent-state artifact receipt grid differs")
        for block, receipt in zip(REGISTERED_BLOCKS, receipts, strict=True):
            expected_panel = (
                REPAIR_PANEL
                if block == "R3" and season == 2025 and week == 1
                else SOURCE_PANELS[REGISTERED_BLOCKS.index(block)]
            )
            if receipt.get("source_panel") != expected_panel or \
                    receipt.get("canonical_panel") != SOURCE_PANELS[
                        REGISTERED_BLOCKS.index(block)
                    ] or not isinstance(receipt.get("candidate_rows"), int) or \
                    receipt["candidate_rows"] < 80 or \
                    not str(receipt.get("uri", "")).startswith("gs://") or \
                    len(str(receipt.get("sha256", ""))) != 64 or \
                    not str(receipt.get("generation", "")).isdigit() or \
                    int(receipt.get("bytes", 0)) <= 0:
                raise ValueError("coherent-state artifact receipt differs")
        artifact_receipts.extend(receipts)
        slate_times.append(float(slate["elapsed_seconds"]))
    if len(artifact_receipts) != 270 or len({
        (row["block"], row["uri"], str(row["generation"]))
        for row in artifact_receipts
    }) != 270:
        raise ValueError("coherent-state artifact population differs")

    gate = aggregate_heldout_gate(all_folds)
    return {
        "version": REPORT_VERSION,
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": True,
        **common,
        "mechanical": {
            "seasons": [2023, 2024, 2025],
            "slates": 54,
            "heldout_folds": 270,
            "source_artifacts": 270,
            "added_candidates": 270 * ADDITION_COUNT,
            "removed_candidates": 270 * ADDITION_COUNT,
            "all_valid": True,
        },
        "selected_addition_conversion": dict(sorted(selected_additions.items())),
        "runtime_seconds": {
            "mean_slate": mean(slate_times),
            "max_slate": max(slate_times),
            "sum": sum(slate_times),
        },
        "source_artifacts": artifact_receipts,
        "gate": gate,
        "consequence": (
            "The frozen score-free gate licenses a separately labeled 2026 "
            "pre-lock shadow only. The separately frozen historical scorer "
            "runs after every mechanically valid harvest regardless of gate."
            if gate["passes_scorefree_gate"] else
            "The exact coherent market-state score-free family fails and is "
            "closed. The separately frozen historical scorer still runs to "
            "avoid effect-selected disclosure."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-report", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = aggregate([Path(value) for value in args.shard_report])
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
