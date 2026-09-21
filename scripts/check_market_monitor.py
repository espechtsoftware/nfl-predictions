#!/usr/bin/env python3
"""Read-only check of the live market-source monitor (operator directive 2026-09-20: any stand-in is monitored).

  python scripts/check_market_monitor.py --season 2026 --week 3 [--max-age-minutes 120] [--min-props-share 0.30]

Reads the latest project-slate batch in nfl_predictions.market_source_log and prints its age, the source counts and
the model-only players; exits 1 (FAIL) when the table is absent, the week has no batch, the batch is older than
--max-age-minutes, fewer than --min-props-share of the non-DST rows are prop-sourced, or any row carries the source
unmatched_in_feed (which a written batch can never contain). Run it before every Saturday build and Sunday chain.
"""
import argparse, sys
from datetime import datetime, timezone

sys.path.insert(0, __import__("pathlib").Path(__file__).resolve().parents[1].joinpath("src").as_posix())
from nfl_dfs.inference.market_monitor import assess_batch  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
ap.add_argument("--path", default="project-slate"); ap.add_argument("--max-age-minutes", type=float, default=120.0)
ap.add_argument("--min-props-share", type=float, default=0.30)
a = ap.parse_args()
from google.api_core.exceptions import NotFound
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
try:
    rows = query_df(f"""SELECT generated_at, gsis_id, display_name, position, source, market_points, proj_points
                        FROM `{settings.predictions}.market_source_log`
                        WHERE season = {a.season} AND week = {a.week} AND path = '{a.path}'
                        QUALIFY generated_at = MAX(generated_at) OVER ()""")
except NotFound:
    print("FAIL market monitor: nfl_predictions.market_source_log does not exist (the repaired image has not run)"); sys.exit(1)
verdict = assess_batch(rows, now=datetime.now(timezone.utc), max_age_minutes=a.max_age_minutes, min_props_share=a.min_props_share)
print(verdict["line"])
for name in verdict["model_only_names"][:40]: print(f"  model-only: {name}")
sys.exit(0 if verdict["ok"] else 1)
