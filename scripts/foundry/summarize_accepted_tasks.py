"""Summarize accepted Foundry lane tasks slate by slate (outcome-blind).

Reads a lane run directory's driver receipts, reopens every accepted
task's carrier and seven per-arm variant results by exact identity, and
prints one row per slate with per-arm coverage and uniqueness counts.
Reads ONLY generation-pinned governance/evidence objects; no realized
outcome, no score body. Safe to run at any time while a lane fan-out is
in flight — it reports whatever is accepted so far.

Usage: python scripts/foundry/summarize_accepted_tasks.py --lane a|b
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nfl_dfs.research.corpus_neo4j_transport import (
    GoogleCloudObjectStore,
    ObjectIdentity,
)
from nfl_dfs.research.corpus_parametric_snapshot import (
    read_task_variant_results,
)

ROOT = Path("/home/erich/projects/nfl-predictions")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True, choices=("a", "b"))
    parser.add_argument("--project", default="nfl-predictions-503414")
    args = parser.parse_args()
    run_dir = ROOT / (
        f"reports/corpus-parametric-runs/20260823-foundry-production-"
        f"v8{args.lane}/transport-live-v8{args.lane}"
    )
    tasks_dir = run_dir / "tasks"
    closed = sorted(tasks_dir.glob("*-producer-closed.json"))
    accepted = {
        path.name.split("-")[0]
        for path in tasks_dir.glob("*-verifier-accepted.json")
    }
    if not closed:
        print(f"lane {args.lane}: no closed producer tasks yet")
        return 0
    store = GoogleCloudObjectStore(project=args.project)

    def read_exact(identity: dict[str, object]) -> bytes:
        return store.read_exact(ObjectIdentity(
            uri=str(identity["uri"]),
            generation=str(identity["generation"]),
            sha256=str(identity["sha256"]),
            bytes=int(identity["bytes"]),
        ))

    print(
        "task slate            accepted arms "
        "unique(min..max) selected optimal"
    )
    for path in closed:
        ordinal = path.name.split("-")[0]
        receipt = json.loads(path.read_bytes())
        carrier_identity = receipt["task_result"]
        _, variants = read_task_variant_results(
            read_exact(carrier_identity),
            carrier_identity=carrier_identity,
            read_exact=read_exact,
        )
        slate = variants[0]["slate"]
        uniques = [v["coverage"]["unique_candidates"] for v in variants]
        selected = {v["coverage"]["selected_entries"] for v in variants}
        optimal = sum(v["coverage"]["optimal_visits"] for v in variants)
        print(
            f"{ordinal}  {slate['season']}-w{slate['week']:02d} "
            f"{'yes' if ordinal in accepted else 'NO ':>3}     "
            f"{len(variants)}    "
            f"{min(uniques)}..{max(uniques)}        "
            f"{sorted(selected)}   {optimal}/7000"
        )
    print(
        f"lane {args.lane}: {len(closed)} closed, "
        f"{len(accepted)} verifier-accepted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
