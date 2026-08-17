"""Frozen source validation for the ATLAS hybrid historical-score v4 run."""

from __future__ import annotations

from typing import Any, Mapping

from nfl_dfs.research.atlas_repair6 import EXPECTED_CELLS, REPAIR6_RUN_ID
from nfl_dfs.research.atlas_repair6_hybrid import validate_hybrid_receipt


HISTORICAL_RUN_ID = "20260817-atlas-historical-score-diagnostic-v4"
HISTORICAL_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/atlas-historical-score-runs/"
    f"{HISTORICAL_RUN_ID}"
)
PROTOCOL_SHA256 = "a5834281678c5126cd95cdf241c1706af08d7f6329ea40e39c4fb078becd2bf8"


def validate_source_receipt(
    receipt: Mapping[str, Any], *, repair5_grid_command: str,
    repair6_grid_command: str,
) -> dict[str, Any]:
    return validate_hybrid_receipt(
        receipt, repair5_grid_command=repair5_grid_command,
        repair6_grid_command=repair6_grid_command,
    )


def validate_shard(
    shard: Mapping[str, Any], *, season: int, week: int, source: str,
    code_sha: str, image: str,
) -> dict[str, Any]:
    """Return the one declared score-free slate after mechanical validation."""
    if (season, week) not in EXPECTED_CELLS or source not in {"repair5", "repair6"}:
        raise RuntimeError("ATLAS historical v4 shard cell differs")
    if shard.get("version") != "atlas-matched-diversity-mvp-v1" or \
            shard.get("uses_realized_outcomes") is not False or \
            shard.get("code_sha") != code_sha or \
            shard.get("analysis_image") != image or \
            shard.get("season") != season or shard.get("shard_week") != week or \
            len(shard.get("slates", [])) != 1:
        raise RuntimeError("ATLAS historical v4 shard identity differs")
    row = shard["slates"][0]
    construction = row.get("construction", {})
    if row.get("season") != season or row.get("week") != week or \
            row.get("mechanical_valid") is not True or \
            row.get("uses_realized_outcomes") is not False or \
            int(row.get("global_atlas_additions") or 0) != 200 or \
            set(row.get("native_boom_counts", {}).values()) != {40} or \
            set(construction) != {"R0", "R1", "R2", "R3", "R4"}:
        raise RuntimeError("ATLAS historical v4 shard mechanics differ")
    for seed in ("R0", "R1", "R2", "R3", "R4"):
        enumeration = construction[seed].get("enumeration", {})
        proposals = enumeration.get("proposals", [])
        if enumeration.get("uses_realized_outcomes") is not False or \
                int(enumeration.get("candidate_count") or 0) != 40 or \
                len([item for item in proposals if item.get("accepted") is True]) != 40:
            raise RuntimeError("ATLAS historical v4 shard enumeration differs")
    for arm in ("P1", "P2"):
        value = row.get(arm, {})
        if int(value.get("candidate_budget") or 0) < 80 or \
                len(value.get("exact80_indices", [])) != 80 or \
                len(value.get("exact80_identities", [])) != 80:
            raise RuntimeError("ATLAS historical v4 exact-80 source differs")
    return row


__all__ = [
    "HISTORICAL_PREFIX", "HISTORICAL_RUN_ID", "PROTOCOL_SHA256",
    "validate_shard", "validate_source_receipt",
]
