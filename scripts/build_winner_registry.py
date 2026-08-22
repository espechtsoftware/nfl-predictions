"""Write the canonical self-hashed winner registry (roadmap P0.2).

Reads the tracked winner CSVs, reconciles them via
`nfl_dfs.research.winner_registry`, and writes the create-once registry
JSON. Refuses to overwrite an existing registry file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from nfl_dfs.research.winner_registry import (
    build_winner_registry,
    canonical_json_bytes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-root", type=Path, default=Path("reports"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        print(f"refused: output exists: {args.output}", file=sys.stderr)
        return 2
    registry = build_winner_registry(args.report_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json_bytes(registry) + b"\n")
    print(json.dumps({
        "contest_count": registry["contest_count"],
        "governed_cohort_count": registry["governed_cohort_count"],
        "winner_registry_sha256": registry["winner_registry_sha256"],
        "output": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
