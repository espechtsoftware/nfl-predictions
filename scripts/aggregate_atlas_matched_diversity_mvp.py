#!/usr/bin/env python3
"""Aggregate three frozen ATLAS MVP season reports and apply its gate."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
from google.cloud import storage

from nfl_dfs.analysis.atlas_matched_diversity import (
    REGISTERED_SEEDS,
    TAIL_GRID,
    aggregate_mvp_gate,
)

from run_atlas_matched_diversity_mvp import OUTPUT_PREFIX, _upload_create_only


OUTPUT_URI = f"{OUTPUT_PREFIX}/report.json"
STRUCTURE_FIELDS = (
    "unique_players", "unique_pairs", "unique_stack_cores",
    "unique_maximum_game_signatures", "player_entropy_effective_count",
    "player_simpson_effective_count", "mean_pairwise_roster_overlap",
)
RANK_FIELDS = (
    "covariance.participation_ratio", "covariance.entropy_effective_rank",
    "covariance.top_five_variance_share",
    "correlation.participation_ratio", "correlation.entropy_effective_rank",
    "correlation.top_five_variance_share",
)


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _ratio(treatment: float, control: float) -> float:
    if control == 0.0:
        return 1.0 if treatment >= 0.0 else float("-inf")
    return treatment / control


def _distribution(values) -> dict:
    array = np.asarray(list(values), dtype=float)
    if array.size == 0 or not np.isfinite(array).all():
        raise ValueError("ATLAS MVP aggregate distribution is invalid")
    return {
        "mean": float(array.mean()),
        "q10": float(np.quantile(array, 0.10)),
        "median": float(np.median(array)),
        "minimum": float(array.min()),
        "maximum": float(array.max()),
    }


def aggregate(paths: list[Path]) -> dict:
    if len(paths) != 3:
        raise ValueError("ATLAS MVP aggregate requires three season reports")
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    seasons = sorted(int(report.get("season", 0)) for report in reports)
    if seasons != [2023, 2024, 2025] or any(
        report.get("uses_realized_outcomes") is not False or
        report.get("version") != "atlas-matched-diversity-mvp-v1" or
        len(report.get("slates", [])) != 18 for report in reports
    ):
        raise ValueError("ATLAS MVP season report identity differs")
    if len({report["code_sha"] for report in reports}) != 1 or \
            len({report["analysis_image"] for report in reports}) != 1 or \
            len({json.dumps(report["source_hashes"], sort_keys=True)
                 for report in reports}) != 1:
        raise ValueError("ATLAS MVP season code/image/source receipts differ")
    rows = [row for report in reports for row in report["slates"]]
    gate = aggregate_mvp_gate(rows)

    tail_summary = {}
    for book in ("P0", "P1", "P2"):
        tail_summary[book] = {}
        for tier in ("candidate_pool_tail", "exact80_tail"):
            tail_summary[book][tier] = {
                f"{line:g}": _distribution(
                    row[book][tier]["aggregate"][f"{line:g}"] for row in rows
                ) for line in TAIL_GRID
            }
    per_season = {}
    for season in seasons:
        season_rows = [row for row in rows if int(row["season"]) == season]
        per_season[str(season)] = {
            tier: {
                f"{line:g}": _distribution(
                    row["P2"][tier]["aggregate"][f"{line:g}"]
                    - row["P1"][tier]["aggregate"][f"{line:g}"]
                    for row in season_rows
                ) for line in TAIL_GRID
            } for tier in ("candidate_pool_tail", "exact80_tail")
        }

    structure = {}
    for tier in ("candidate_structure", "exact80_structure"):
        structure[tier] = {}
        for field in STRUCTURE_FIELDS:
            control = [float(row["P1"][tier][field]) for row in rows]
            treatment = [float(row["P2"][tier][field]) for row in rows]
            structure[tier][field] = {
                "P1": _distribution(control),
                "P2": _distribution(treatment),
                "P2_over_P1": _distribution(
                    _ratio(right, left)
                    for left, right in zip(control, treatment, strict=True)
                ),
            }
        for field in RANK_FIELDS:
            family, metric = field.split(".", 1)
            control = [
                float(row["P1"][tier]["score_effective_rank"][family][metric])
                for row in rows
            ]
            treatment = [
                float(row["P2"][tier]["score_effective_rank"][family][metric])
                for row in rows
            ]
            structure[tier][f"score_effective_rank.{field}"] = {
                "P1": _distribution(control),
                "P2": _distribution(treatment),
                "P2_over_P1": _distribution(
                    _ratio(right, left)
                    for left, right in zip(control, treatment, strict=True)
                ),
            }
    preservation = {}
    for tier in ("candidate_pool_tail", "exact80_tail"):
        preservation[tier] = {}
        for line in TAIL_GRID:
            key = f"{line:g}"
            ratios = [
                _ratio(
                    float(row["P2"][tier]["aggregate"][key]),
                    float(row["P1"][tier]["aggregate"][key]),
                ) for row in rows
            ]
            preservation[tier][key] = {
                "raw_P2_over_P1": _distribution(ratios),
                "capped_at_one": _distribution(min(1.0, value) for value in ratios),
            }
    block_tail = {}
    for tier in ("candidate_pool_tail", "exact80_tail"):
        block_tail[tier] = {}
        for seed in REGISTERED_SEEDS:
            block_tail[tier][seed] = {}
            for line in TAIL_GRID:
                key = f"{line:g}"
                block_tail[tier][seed][key] = {
                    book: float(np.mean([
                        row[book][tier]["by_block"][seed][key] for row in rows
                    ])) for book in ("P0", "P1", "P2")
                }
    top_jaccard = {
        tier: _distribution(
            row["top20_player_jaccard_P1_P2"][tier] for row in rows
        ) for tier in ("candidate", "exact80")
    }
    return {
        "version": "atlas-matched-diversity-mvp-v1",
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_arm_licensed": False,
        "code_sha": reports[0]["code_sha"],
        "analysis_image": reports[0]["analysis_image"],
        "source_hashes": reports[0]["source_hashes"],
        "season_report_sha256": {
            str(report["season"]): _digest(path)
            for report, path in zip(reports, paths, strict=True)
        },
        "mechanical": {
            "seasons": seasons,
            "slates": len(rows),
            "all_valid": all(row["mechanical_valid"] is True for row in rows),
            "all_global_atlas_additions_200": all(
                int(row["global_atlas_additions"]) == 200 for row in rows
            ),
            "all_native_boom_counts_40": all(
                set(row["native_boom_counts"].values()) == {40} for row in rows
            ),
        },
        "gate": gate,
        "tail_grid": tail_summary,
        "tail_delta_by_season": per_season,
        "tail_by_pricing_excluded_block": block_tail,
        "structure": structure,
        "tail_preservation": preservation,
        "top20_player_jaccard_P1_P2": top_jaccard,
        "slates": rows,
        "consequence": (
            "licenses only a separately labeled 2026 pre-lock P0/P1/P2 shadow"
            if gate["passes_scorefree_gate"] else
            "closes ATLAS matched-diversity MVP v1; production remains unchanged"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season-report", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    if args.output_uri != OUTPUT_URI:
        raise SystemExit("ATLAS MVP aggregate output URI differs")
    output = Path(args.output)
    if output.exists():
        raise SystemExit("ATLAS MVP aggregate local output already exists")
    report = aggregate([Path(value) for value in args.season_report])
    raw = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    output.write_bytes(raw)
    upload = _upload_create_only(
        storage.Client(project="nfl-predictions-503414"), args.output_uri, raw,
    )
    print("ATLAS_MVP_AGGREGATE_RESULT " + json.dumps({
        "gate": report["gate"], "output": upload,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
