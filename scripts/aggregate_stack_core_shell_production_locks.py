#!/usr/bin/env python3
"""Strictly aggregate the 54 outcome-free production-form roster locks."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import json
import math
from pathlib import Path
import re

from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS, REPORT_THRESHOLDS
from nfl_dfs.analysis.stack_core_shell import BEAM_LIMIT, CORE_LIMIT, PROPOSAL_LIMIT, SHELL_LIMIT
from nfl_dfs.analysis.stack_core_shell_historical import LOCK_VERSION
from aggregate_stack_core_shell_support_census import load_expected_artifact_ledger
from run_stack_core_shell_production_lock import (
    HISTORICAL_PROTOCOL,
    HISTORICAL_PROTOCOL_SHA256,
    RUN_ID,
    SCORE_FREE_COMPLETION_URI,
    SCORE_FREE_REPORT_URI,
)
from stack_core_shell_sources import SOURCE_PANELS, REPAIR_PANEL, validate_local_sources


REPORT_VERSION = "stack-core-shell-production-lock-report-v1"
SHARD_VERSION = "stack-core-shell-production-lock-shard-v1"
FORBIDDEN_KEYS = {
    "actual", "actual_score", "actual_rank", "actual_ownership", "payout",
    "contest_rank", "selected_rank", "labels_complete", "exception_counts",
}


def _assert_no_outcome(value: object, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"stack-core/shell lock outcome field at {path}.{key}")
            _assert_no_outcome(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_outcome(child, f"{path}[{index}]")


def _rosters(value: object, expected: int, name: str) -> list[tuple[str, ...]]:
    if not isinstance(value, list) or len(value) != expected:
        raise ValueError(f"stack-core/shell lock {name} count differs")
    rows = []
    for roster in value:
        if not isinstance(roster, list) or len(roster) != 9 or \
                roster != sorted(str(player) for player in roster) or \
                len(set(roster)) != 9:
            raise ValueError(f"stack-core/shell lock {name} roster differs")
        rows.append(tuple(roster))
    if len(set(rows)) != expected:
        raise ValueError(f"stack-core/shell lock {name} repeats")
    return rows


def _validate_rank(value: object, name: str) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "covariance", "correlation",
    }:
        raise ValueError(f"stack-core/shell lock {name} rank differs")
    for row in value.values():
        if not isinstance(row, Mapping) or set(row) != {
            "participation_ratio", "entropy_effective_rank",
            "top_five_variance_share",
        } or any(not math.isfinite(float(number)) for number in row.values()):
            raise ValueError(f"stack-core/shell lock {name} rank is invalid")


def validate_lock(lock: Mapping[str, object], season: int, week: int) -> None:
    required = {
        "version", "uses_realized_outcomes", "actual_scores_queried",
        "mechanical_valid", "season", "week", "blocks", "worlds_per_block",
        "candidate_budget", "selected_entries", "candidate_rosters",
        "selected_rosters", "simulated_threshold_counts", "structure",
        "score_effective_rank", "component_library", "proposal_counts",
        "beam_candidates", "proposal_candidates", "proposal_rosters",
        "proposal_components", "admitted_proposal_rosters",
        "admitted_proposals",
    }
    if set(lock) != required or lock.get("version") != LOCK_VERSION or \
            lock.get("uses_realized_outcomes") is not False or \
            lock.get("actual_scores_queried") is not False or \
            lock.get("mechanical_valid") is not True or \
            lock.get("season") != season or lock.get("week") != week or \
            lock.get("blocks") != list(REGISTERED_BLOCKS) or \
            lock.get("worlds_per_block") != 10_000 or \
            lock.get("selected_entries") != 80 or \
            lock.get("beam_candidates") != BEAM_LIMIT or \
            lock.get("proposal_candidates") != PROPOSAL_LIMIT:
        raise ValueError("stack-core/shell production lock contract differs")
    budget = lock.get("candidate_budget")
    if not isinstance(budget, int) or budget < 80:
        raise ValueError("stack-core/shell production lock budget differs")
    candidate = lock.get("candidate_rosters")
    selected = lock.get("selected_rosters")
    if not isinstance(candidate, Mapping) or set(candidate) != {"control", "treatment"} or \
            not isinstance(selected, Mapping) or set(selected) != {"control", "treatment"}:
        raise ValueError("stack-core/shell production lock book layers differ")
    books = {
        "candidate": {
            arm: _rosters(candidate[arm], budget, f"{arm} candidate")
            for arm in ("control", "treatment")
        },
        "selected": {
            arm: _rosters(selected[arm], 80, f"{arm} selected")
            for arm in ("control", "treatment")
        },
    }
    for arm in ("control", "treatment"):
        if not set(books["selected"][arm]) <= set(books["candidate"][arm]):
            raise ValueError("stack-core/shell selected book leaves candidates")
    proposals = _rosters(lock.get("proposal_rosters"), PROPOSAL_LIMIT, "proposal")
    admitted_count = lock.get("admitted_proposals")
    if not isinstance(admitted_count, int) or not 0 <= admitted_count <= PROPOSAL_LIMIT:
        raise ValueError("stack-core/shell admitted proposal count differs")
    admitted = _rosters(
        lock.get("admitted_proposal_rosters"), admitted_count, "admitted proposal",
    )
    control = set(books["candidate"]["control"])
    treatment = set(books["candidate"]["treatment"])
    if control & set(proposals) or set(admitted) != treatment - control or \
            not set(admitted) <= set(proposals) or \
            len(control & treatment) + admitted_count != budget:
        raise ValueError("stack-core/shell proposal admission identity differs")

    library = lock.get("component_library")
    if not isinstance(library, Mapping) or set(library) != {
        "source_lineups", "decompositions", "discovered_cores",
        "discovered_shells", "retained_cores", "retained_shells",
        "core_qb_counts", "core_game_counts", "cores", "shells",
    } or library.get("source_lineups") != budget or \
            library.get("retained_cores") != CORE_LIMIT or \
            library.get("retained_shells") != SHELL_LIMIT or \
            len(library.get("cores", [])) != CORE_LIMIT or \
            len(library.get("shells", [])) != SHELL_LIMIT or \
            sum(library.get("core_qb_counts", {}).values()) != CORE_LIMIT or \
            sum(library.get("core_game_counts", {}).values()) != CORE_LIMIT or \
            max(library.get("core_qb_counts", {}).values(), default=CORE_LIMIT + 1) > 4 or \
            max(library.get("core_game_counts", {}).values(), default=CORE_LIMIT + 1) > 8:
        raise ValueError("stack-core/shell component library differs")
    core_ids: set[tuple[str, ...]] = set()
    shell_ids: set[tuple[str, ...]] = set()
    observed_qbs: Counter[str] = Counter()
    observed_games: Counter[str] = Counter()
    for kind, count in (("cores", 4), ("shells", 5)):
        seen = set()
        for component in library[kind]:
            required_component = {"players", "rank", "parent"}
            if kind == "cores":
                required_component |= {"qb", "game"}
            players = tuple(component.get("players", ()))
            parent = tuple(component.get("parent", ()))
            if set(component) != required_component or len(players) != count or \
                    list(players) != sorted(players) or len(set(players)) != count or \
                    len(parent) != 9 or list(parent) != sorted(parent) or \
                    tuple(parent) not in control or not set(players) <= set(parent) or \
                    len(component.get("rank", ())) != 7 or any(
                        not math.isfinite(float(number))
                        for number in component.get("rank", ())
                    ):
                raise ValueError("stack-core/shell component receipt differs")
            if kind == "cores" and (
                component.get("qb") not in players or not component.get("game")
            ):
                raise ValueError("stack-core/shell core identity differs")
            seen.add(players)
            if kind == "cores":
                observed_qbs[str(component["qb"])] += 1
                observed_games[str(component["game"])] += 1
        if len(seen) != len(library[kind]):
            raise ValueError("stack-core/shell component identity repeats")
        if kind == "cores":
            core_ids = seen
        else:
            shell_ids = seen
    if dict(sorted(observed_qbs.items())) != library["core_qb_counts"] or \
            dict(sorted(observed_games.items())) != library["core_game_counts"]:
        raise ValueError("stack-core/shell component cap receipt differs")

    proposal_components = lock.get("proposal_components")
    covered_pairs: set[tuple[str, str]] = set()
    if not isinstance(proposal_components, list) or \
            len(proposal_components) != PROPOSAL_LIMIT:
        raise ValueError("stack-core/shell proposal component count differs")
    for index, row in enumerate(proposal_components):
        core = tuple(row.get("core", ()))
        shell = tuple(row.get("shell", ()))
        roster = tuple(row.get("roster", ()))
        new_pairs = {
            tuple(sorted((left, right))) for left in core for right in shell
        } - covered_pairs
        if set(row) != {"roster", "core", "shell", "rank"} or \
                roster != proposals[index] or core not in core_ids or \
                shell not in shell_ids or set(core) & set(shell) or \
                set(roster) != set(core) | set(shell) or \
                len(row.get("rank", ())) != 7 or any(
                    not math.isfinite(float(number)) for number in row.get("rank", ())
                ) or (index > 0 and not new_pairs):
            raise ValueError("stack-core/shell proposal component receipt differs")
        covered_pairs.update(new_pairs)

    expected_lines = {str(int(line)) for line in REPORT_THRESHOLDS}
    thresholds = lock.get("simulated_threshold_counts")
    structure = lock.get("structure")
    ranks = lock.get("score_effective_rank")
    if not isinstance(thresholds, Mapping) or not isinstance(structure, Mapping) or \
            not isinstance(ranks, Mapping) or set(thresholds) != {"candidate", "selected"} or \
            set(structure) != {"candidate", "selected"} or \
            set(ranks) != {"candidate", "selected"}:
        raise ValueError("stack-core/shell lock diagnostic layers differ")
    expected_structure = {
        "unique_players", "unique_player_pairs", "unique_qb_stack_cores",
        "unique_dominant_games",
    }
    for layer in ("candidate", "selected"):
        if set(thresholds[layer]) != {"control", "treatment"} or \
                set(structure[layer]) != {"control", "treatment"} or \
                set(ranks[layer]) != {"control", "treatment"}:
            raise ValueError("stack-core/shell lock diagnostic books differ")
        for arm in ("control", "treatment"):
            values = thresholds[layer][arm]
            if set(values) != expected_lines or any(
                not isinstance(number, int) or not 0 <= number <= 50_000
                for number in values.values()
            ) or set(structure[layer][arm]) != expected_structure or any(
                not isinstance(number, int) or number < 1
                for number in structure[layer][arm].values()
            ):
                raise ValueError("stack-core/shell lock diagnostic receipt differs")
            _validate_rank(ranks[layer][arm], f"{layer}/{arm}")
    counts = lock.get("proposal_counts")
    if not isinstance(counts, Mapping) or set(counts) != {
        "legal_crosses", "existing_control_crosses", "duplicate_crosses",
        "unique_recombinants", "covered_core_shell_pairs",
    } or any(not isinstance(number, int) or number < 0 for number in counts.values()) or \
            counts["unique_recombinants"] < BEAM_LIMIT or \
            counts["covered_core_shell_pairs"] != len(covered_pairs) or \
            len(covered_pairs) < 59:
        raise ValueError("stack-core/shell lock proposal counts differ")


def aggregate(shard_paths: Sequence[Path]) -> dict[str, object]:
    paths = [Path(path) for path in shard_paths]
    if len(paths) != 54 or len(set(paths)) != 54:
        raise ValueError("stack-core/shell locks require 54 unique shards")
    shards = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    for shard in shards:
        _assert_no_outcome(shard)
    shards.sort(key=lambda row: (int(row.get("season", 0)), int(row.get("week", 0))))
    grid = [(season, week) for season in (2023, 2024, 2025) for week in range(1, 19)]
    if [(row.get("season"), row.get("week")) for row in shards] != grid:
        raise ValueError("stack-core/shell lock slate grid differs")
    expected_hashes = validate_local_sources()
    expected_artifacts = load_expected_artifact_ledger()
    first = shards[0]
    common = {
        key: first.get(key) for key in (
            "code_sha", "analysis_image", "historical_protocol_sha256",
            "source_hashes", "source_panels", "scorefree_license",
        )
    }
    license_value = common["scorefree_license"]
    if not re.fullmatch(r"[0-9a-f]{40}", str(common["code_sha"])) or \
            not re.fullmatch(r".+@sha256:[0-9a-f]{64}", str(common["analysis_image"])) or \
            common["historical_protocol_sha256"] != HISTORICAL_PROTOCOL_SHA256 or \
            common["source_hashes"] != expected_hashes or \
            common["source_panels"] != list(SOURCE_PANELS) or \
            not isinstance(license_value, Mapping) or \
            license_value.get("report", {}).get("uri") != SCORE_FREE_REPORT_URI or \
            license_value.get("completion", {}).get("uri") != SCORE_FREE_COMPLETION_URI or \
            license_value.get("disposition") != "stack-core-shell-shadow-licensed":
        raise ValueError("stack-core/shell lock common identity differs")
    required_shard = {
        "version", "run_id", "uses_realized_outcomes", "actual_scores_queried",
        "production_change_licensed", "historical_scoring_licensed", "season",
        "week", "code_sha", "analysis_image", "historical_protocol_sha256",
        "source_hashes", "source_panels", "scorefree_license",
        "artifact_receipts", "lock",
    }
    locks = []
    artifacts = []
    artifact_count = 0
    for shard in shards:
        if set(shard) != required_shard or shard.get("version") != SHARD_VERSION or \
                shard.get("run_id") != RUN_ID or \
                shard.get("uses_realized_outcomes") is not False or \
                shard.get("actual_scores_queried") is not False or \
                shard.get("production_change_licensed") is not False or \
                shard.get("historical_scoring_licensed") is not True or any(
                    shard.get(key) != value for key, value in common.items()
                ):
            raise ValueError("stack-core/shell lock shard identity differs")
        season, week = int(shard["season"]), int(shard["week"])
        receipts = shard.get("artifact_receipts")
        if not isinstance(receipts, list) or len(receipts) != 5:
            raise ValueError("stack-core/shell lock artifact grid differs")
        for index, (block, receipt) in enumerate(zip(REGISTERED_BLOCKS, receipts, strict=True)):
            expected = expected_artifacts[(season, week, block)]
            canonical = SOURCE_PANELS[index]
            raw_panel = REPAIR_PANEL if (season, week, block) == (2025, 1, "R3") else canonical
            exact = {
                "block": block, "source_panel": raw_panel,
                "canonical_panel": canonical,
                "candidate_rows": int(expected["candidate_rows"]),
                "uri": expected["uri"], "sha256": expected["sha256"],
                "generation": str(expected["generation"]),
                "updated": expected["updated"], "bytes": int(expected["bytes"]),
            }
            if receipt != exact:
                raise ValueError("stack-core/shell lock artifact receipt differs")
            artifact_count += 1
            artifacts.append(receipt)
        lock = shard.get("lock")
        if not isinstance(lock, Mapping):
            raise ValueError("stack-core/shell lock payload differs")
        validate_lock(lock, season, week)
        locks.append(lock)
    if artifact_count != 270:
        raise ValueError("stack-core/shell lock artifact population differs")
    return {
        "version": REPORT_VERSION,
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "actual_scores_queried": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": True,
        "historical_protocol_path": str(HISTORICAL_PROTOCOL),
        **common,
        "mechanical": {
            "seasons": [2023, 2024, 2025], "slates": 54,
            "source_artifacts": 270, "all_valid": True,
            "rosters_locked_before_actual_query": True,
        },
        "artifact_receipts": artifacts,
        "locks": locks,
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
        raise RuntimeError("immutable stack-core/shell lock report exists")
    output.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print("STACK_CORE_SHELL_PRODUCTION_LOCKS_AGGREGATED")


if __name__ == "__main__":
    main()
