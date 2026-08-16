#!/usr/bin/env python3
"""Assemble 54 mechanically sharded ATLAS MVP slates and apply frozen gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from google.cloud import storage

from aggregate_atlas_matched_diversity_mvp import aggregate
from run_atlas_matched_diversity_mvp import (
    PROJECT,
    SHARDED_OUTPUT_PREFIX,
    _upload_create_only,
)


def assemble(paths: list[Path]) -> list[dict]:
    if len(paths) != 54:
        raise ValueError("ATLAS MVP sharded assembly requires exactly 54 reports")
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    expected = {
        (season, week) for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    keyed = {}
    for report in reports:
        rows = report.get("slates", [])
        key = (int(report.get("season", 0)), int(report.get("shard_week", 0)))
        if report.get("version") != "atlas-matched-diversity-mvp-v1" or \
                report.get("uses_realized_outcomes") is not False or \
                len(rows) != 1 or \
                (int(rows[0].get("season", 0)), int(rows[0].get("week", 0))) != key:
            raise ValueError("ATLAS MVP shard report identity differs")
        if key in keyed:
            raise ValueError("ATLAS MVP shard grid contains a duplicate")
        keyed[key] = report
    if set(keyed) != expected:
        raise ValueError("ATLAS MVP shard grid is incomplete")
    if len({report["code_sha"] for report in reports}) != 1 or \
            len({report["analysis_image"] for report in reports}) != 1 or \
            len({json.dumps(report["source_hashes"], sort_keys=True)
                 for report in reports}) != 1:
        raise ValueError("ATLAS MVP shard code/image/source bindings differ")
    seasons = []
    for season in (2023, 2024, 2025):
        first = keyed[(season, 1)]
        rows = [keyed[(season, week)]["slates"][0] for week in range(1, 19)]
        if any(row.get("mechanical_valid") is not True or
               row.get("uses_realized_outcomes") is not False for row in rows):
            raise ValueError("ATLAS MVP shard contains an invalid slate")
        seasons.append({
            "version": "atlas-matched-diversity-mvp-v1",
            "uses_realized_outcomes": False,
            "season": season,
            "code_sha": first["code_sha"],
            "analysis_image": first["analysis_image"],
            "source_hashes": first["source_hashes"],
            "slates": rows,
        })
    return seasons


def write_aggregate(paths: list[Path], output_dir: Path, output_prefix: str) -> dict:
    if output_prefix != SHARDED_OUTPUT_PREFIX:
        raise ValueError("ATLAS MVP sharded output prefix differs")
    if not output_dir.is_dir():
        raise ValueError("ATLAS MVP sharded local output directory is absent")
    gcs = storage.Client(project=PROJECT)
    season_reports = assemble(paths)
    season_paths = []
    uploads = {}
    for report in season_reports:
        season = int(report["season"])
        path = output_dir / f"season-{season}.json"
        if path.exists():
            raise ValueError("ATLAS MVP sharded season output already exists")
        raw = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
        path.write_bytes(raw)
        uploads[f"season-{season}"] = _upload_create_only(
            gcs, f"{output_prefix}/season-{season}.json", raw,
        )
        season_paths.append(path)
    report = aggregate(season_paths)
    report_path = output_dir / "report.json"
    if report_path.exists():
        raise ValueError("ATLAS MVP sharded aggregate output already exists")
    raw = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    report_path.write_bytes(raw)
    uploads["report"] = _upload_create_only(
        gcs, f"{output_prefix}/report.json", raw,
    )
    return {"report": report, "uploads": uploads}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-report", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-prefix", required=True)
    args = parser.parse_args()
    result = write_aggregate(
        [Path(value) for value in args.shard_report],
        Path(args.output_dir), args.output_prefix,
    )
    print("ATLAS_MVP_SHARDED_AGGREGATE " + json.dumps({
        "gate": result["report"]["gate"], "uploads": result["uploads"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
