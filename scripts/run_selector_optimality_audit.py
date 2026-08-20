#!/usr/bin/env python3
"""Selector optimality-gap audit (queue A5, protocol
20260818-selector-optimality-gap-v1).

Measures how far the production greedy coverage selector sits from the
EXACT optimum of its own objective, on real registered candidate totals.
The boom-S null (2026-08-19) made this decisive: the pool ceiling rose
+9.06 while the selected book moved +1.34, so the question "is the
selector even optimal for the objective it optimizes?" now gates the
whole selection lane. A ~zero gap closes the selector-ALGORITHM family
permanently and points everything at the OBJECTIVE (SELECT_LADDER) and
the pool; a material gap licenses an exact/beam upgrade as a frozen arm.

Score-free: consumes only simulated candidate totals from the archived
artifacts. No realized outcome is read, so this needs no historical-
outcome lease and runs safely alongside an in-flight scored arm.

Per slate the audit stacks the five seed blocks' candidate totals (the
same matrix the production selector sees), runs greedy and exact CBC at
the production contract (80 entries, line 194), and records the gap.
Gaps are citable only where CBC returns Optimal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.research.selector_optimality_gap import (  # noqa: E402
    PROTOCOL_ID,
    OptimalityGapError,
    optimality_gap_report,
)

N_ENTRIES = 80
TAIL_LINE = 194.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int, default=0,
                        help="audit only the first N slates (0 = all)")
    parser.add_argument("--time-limit", type=int, default=600)
    parser.add_argument("--smoke", metavar="SEASON:WEEK")
    args = parser.parse_args(argv)
    if not args.smoke and args.output is None:
        parser.error("--output is required outside --smoke mode")

    manifest = json.loads(args.manifest.read_text())
    slates = sorted(
        ((int(m["season"]), int(m["week"]), [Path(p) for p in m["artifacts"]])
         for m in manifest),
        key=lambda row: (row[0], row[1]))
    if args.smoke:
        season, week = (int(x) for x in args.smoke.split(":"))
        slates = [s for s in slates if (s[0], s[1]) == (season, week)]
        if not slates:
            raise OptimalityGapError(f"{season} week {week} not in manifest")
    elif args.limit:
        slates = slates[: args.limit]

    per_block = []
    for season, week, paths in slates:
        for path in paths:
            with np.load(path) as artifact:
                if "totals" not in artifact.files:
                    raise OptimalityGapError(f"{path} lacks candidate totals")
                totals = np.asarray(artifact["totals"], dtype=np.float64)
            report = optimality_gap_report(
                totals, N_ENTRIES, TAIL_LINE,
                time_limit_seconds=args.time_limit)
            report.update({
                "season": season, "week": week, "block_file": path.name,
                "candidates": int(totals.shape[0]),
                "worlds": int(totals.shape[1]),
            })
            per_block.append(report)
            print(f"AUDITED {season}:{week} {path.name} "
                  f"greedy={report['greedy']['covered_worlds']} "
                  f"exact={report['exact']['covered_worlds']} "
                  f"gap={report['gap_worlds']} "
                  f"status={report['exact']['status']}")
            if args.smoke:
                print("SMOKE_OK citable="
                      f"{report['gap_citable']} "
                      f"coverable={report['exact']['coverable_worlds']}")
                return 0

    citable = [r for r in per_block if r["gap_citable"]]
    gaps = [int(r["gap_worlds"]) for r in citable]
    greedy_cov = [int(r["greedy"]["covered_worlds"]) for r in citable]
    summary = {
        "protocol_id": PROTOCOL_ID,
        "n_blocks": len(per_block),
        "n_citable": len(citable),
        "n_timed_out": len(per_block) - len(citable),
        "n_entries": N_ENTRIES,
        "line": TAIL_LINE,
        "gap_worlds_mean": (float(np.mean(gaps)) if gaps else None),
        "gap_worlds_max": (int(max(gaps)) if gaps else None),
        "n_blocks_with_any_gap": int(sum(g > 0 for g in gaps)),
        "greedy_covered_mean": (
            float(np.mean(greedy_cov)) if greedy_cov else None),
        "gap_fraction_of_greedy_mean": (
            float(np.mean([
                g / c for g, c in zip(gaps, greedy_cov) if c > 0
            ])) if gaps else None),
        "per_block": per_block,
        "uses_realized_outcomes": False,
        "fit_performed": False,
        "tuning_performed": False,
        "gate_decision": None,
        "production_change_licensed": False,
    }
    payload = json.dumps(
        summary, sort_keys=True, separators=(",", ":")).encode()
    with args.output.open("xb") as handle:
        handle.write(payload)
    digest = hashlib.sha256(payload).hexdigest()
    print(
        "SELECTOR_OPTIMALITY_COMPLETE",
        f"protocol={PROTOCOL_ID}",
        f"blocks={summary['n_blocks']}",
        f"citable={summary['n_citable']}",
        f"mean_gap={summary['gap_worlds_mean']}",
        f"output={args.output}",
        f"sha256={digest}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
