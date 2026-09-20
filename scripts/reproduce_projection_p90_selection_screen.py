#!/usr/bin/env python3
"""Run the same frozen selector screen using each player's served p90.

This is a separate diagnostic from the mean-projection floor experiment.  It
reuses the exact candidate masks and selector, but substitutes `proj_p90` for
`proj` only when identifying the weakest non-DST player.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from google.cloud import bigquery

from reproduce_projection_floor_selection_screen import (
    CANDIDATE_SQL,
    PANEL,
    PROJECT,
    DATASET,
    query_df,
    screen,
)


P90_FEATURE_SQL = f"""
SELECT season, week, id, pos, proj_p90 AS proj
FROM `{PROJECT}.{DATASET}.slate_player_features`
WHERE panel_run_id = @panel_id
  AND research_eligible = TRUE
ORDER BY season, week, id
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--panel", default=PANEL)
    args = parser.parse_args()
    if args.panel != PANEL:
        raise SystemExit(f"refusing non-frozen panel: {args.panel}")
    client = bigquery.Client(project=PROJECT, location="US")
    candidates = query_df(client, CANDIDATE_SQL, args.panel)
    features = query_df(client, P90_FEATURE_SQL, args.panel)
    result = screen(candidates, features)
    result.update(
        {
            "floor_variable": "served proj_p90",
            "project": PROJECT,
            "dataset": DATASET,
            "candidate_query_sha256": hashlib.sha256(CANDIDATE_SQL.encode()).hexdigest(),
            "feature_query_sha256": hashlib.sha256(P90_FEATURE_SQL.encode()).hexdigest(),
            "selection_scope": "selection-only filter on frozen historical candidate pool; weakest non-DST served proj_p90; masks/p_line/sim_mean only",
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
