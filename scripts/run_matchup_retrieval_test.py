"""Run the frozen paired retrieval test (see matchup_retrieval_test).

Default-off: --execute plus MATCHUP_TAIL_MODEL_ENABLED=1.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ENABLE_ENV = "MATCHUP_TAIL_MODEL_ENABLED"
CANONICAL_PANEL = "20260811-pitclean-e80-k1-role12union-a12ab31"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", default=CANONICAL_PANEL)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute or os.environ.get(ENABLE_ENV) != "1":
        print(
            f"execution requires literal --execute and {ENABLE_ENV}=1",
            file=sys.stderr,
        )
        return 2
    if args.output.exists() or args.output.is_symlink():
        print(f"refused: output exists: {args.output}", file=sys.stderr)
        return 2

    from nfl_dfs import bq
    from nfl_dfs.research.matchup_retrieval_test import run_paired_test
    from nfl_dfs.research.winner_registry import canonical_json_bytes

    evidence = bq.query_df(
        f"SELECT * FROM `{bq.settings.features}.lineup_matchup_evidence` "
        "WHERE panel_run_id = @panel",
        {"panel": args.panel},
    )
    receipt = run_paired_test(evidence)
    receipt["panel_run_id"] = args.panel
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json_bytes(receipt) + b"\n")
    print(json.dumps({
        "primary_sleeve": {
            key: receipt["primary_sleeve"][key]
            for key in (
                "mean_weekly_max_delta", "slate_wins", "slate_ties",
                "slate_losses",
            )
        },
        "weeks_ge_200": receipt["primary_sleeve"]["weeks_ge_200"],
        "weeks_ge_194": receipt["primary_sleeve"]["weeks_ge_194"],
        "nomination_bar_met": receipt["primary_nomination_bar_met"],
        "secondary_blend_mean_delta": receipt["secondary_blend"][
            "mean_weekly_max_delta"
        ],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
