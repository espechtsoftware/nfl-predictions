#!/usr/bin/env python3
"""Render the frozen create-only same-law capacity generation manifest."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

from nfl_dfs.research.same_law_capacity_generation import (
    generation_schedule,
)


RUN_ID = "20260817-same-law-capacity-curve-v1"
PROTOCOL = Path("reports/2026-08-17-same-law-capacity-curve-protocol.md")
PROTOCOL_SHA256 = "fbde9ba133ff09bcf7c019bf2232be407e6599397258742392b5501e82047128"
SEED_LEDGER = Path("reports/2026-08-17-same-law-capacity-curve-seeds.csv")
SEED_LEDGER_SHA256 = "5838185cb2851a38c139d37959ea655a68dcd1aef534d804285f398586eae6fb"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def render_manifest(
    *,
    protocol: Path = PROTOCOL,
    seed_ledger: Path = SEED_LEDGER,
) -> dict[str, object]:
    if not protocol.is_file() or _sha(protocol) != PROTOCOL_SHA256:
        raise ValueError("capacity generation protocol is missing or changed")
    if not seed_ledger.is_file() or _sha(seed_ledger) != SEED_LEDGER_SHA256:
        raise ValueError("capacity generation seed ledger is missing or changed")
    schedule = generation_schedule(pd.read_csv(seed_ledger))
    receipts = [cell.receipt() for cell in schedule]
    return {
        "version": "same-law-capacity-generation-manifest-v1",
        "run_id": RUN_ID,
        "protocol_path": str(protocol),
        "protocol_sha256": PROTOCOL_SHA256,
        "seed_ledger_path": str(seed_ledger),
        "seed_ledger_sha256": SEED_LEDGER_SHA256,
        "primary_executions": 135,
        "new_books": 45,
        "seasons": [2023, 2024, 2025],
        "canary": receipts[0],
        "remaining_cells_released_before_canary": 0,
        "max_active_executions": 10,
        "max_task_retries": 0,
        "max_external_replacements_per_cell": 1,
        "uses_realized_outcomes": False,
        "candidate_identity_opened_before_strict_harvest": False,
        "capacity_statistic_opened_before_strict_harvest": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "schedule": receipts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("immutable capacity generation manifest already exists")
    value = render_manifest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print("CAPACITY_GENERATION_MANIFEST_RENDERED", len(value["schedule"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
