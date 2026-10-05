#!/usr/bin/env python3
"""Rehearse own_shadow writes against a SCRATCH copy of the altered table (2026-10-05).

Proves, before any image is deployed, that the writer column is additive in both orders:
  1. a LEGACY-format generation (no writer/run_type: what every older image writes), and
  2. a NEW-format generation (writer + run_type, built by ownership_shadow_frame),
both through nfl_dfs.bq.load_dataframe(WRITE_APPEND) -- the exact load path
live_lineups._log_ownership_shadow uses -- into a scratch table created LIKE the real
own_shadow (so it carries the ALTERed schema). The real table is never written; the script
refuses any destination that is not an own_shadow_rehearsal_* scratch table.

Usage (after the ALTER):
    PYTHONPATH=src python scripts/own_shadow_write_rehearsal.py --scratch own_shadow_rehearsal_20261007
Cleanup (printed at the end, also safe to run on failure):
    bq rm -f -t nfl-predictions-503414:nfl_predictions.own_shadow_rehearsal_20261007
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

import pandas as pd

SCRATCH = re.compile(r"^own_shadow_rehearsal_[0-9]{8}$")
WRITER = "rehearsal_scratch"


def frames(stamp: datetime) -> tuple[pd.DataFrame, pd.DataFrame]:
    from nfl_dfs.inference.own_shadow import ownership_shadow_frame

    pool = pd.DataFrame({"gsis_id": ["00-rehearsal"], "name": ["Rehearsal Row"],
                         "pos": ["QB"], "salary": [5000]})
    new = ownership_shadow_frame(pool, [0.1], "naive", 2026, 0, booster_own=None,
                                 writer=WRITER, run_type="rehearsal", generated_at=stamp)
    legacy = new.drop(columns=["writer", "run_type"])
    return legacy, new


def run(scratch: str, *, load=None, query=None, now=None) -> dict:
    if not SCRATCH.fullmatch(scratch):
        raise SystemExit(f"refusing destination {scratch!r}: only own_shadow_rehearsal_YYYYMMDD")
    from nfl_dfs.config import settings

    if load is None or query is None:
        from nfl_dfs.bq import load_dataframe, query_df
        load, query = load or load_dataframe, query or query_df
    dataset = settings.predictions  # "<project>.nfl_predictions"
    real = f"{dataset}.own_shadow"
    table = f"{dataset}.{scratch}"
    schema = query(f"SELECT column_name FROM `{dataset}`"
                   f".INFORMATION_SCHEMA.COLUMNS WHERE table_name = 'own_shadow'")
    columns = set(schema.column_name)
    if not {"writer", "run_type"} <= columns:
        raise SystemExit("own_shadow lacks writer/run_type: run the ALTER first")
    query(f"CREATE TABLE `{table}` LIKE `{real}`")
    legacy, new = frames(now or datetime.now(timezone.utc))
    load(legacy, table, write_disposition="WRITE_APPEND")
    load(new, table, write_disposition="WRITE_APPEND")
    got = query(f"SELECT IFNULL(writer, '<NULL>') AS writer, run_type, COUNT(*) AS n "
                f"FROM `{table}` GROUP BY 1, 2 ORDER BY 1")
    result = {row.writer: (row.run_type, int(row.n)) for row in got.itertuples()}
    ok = result.get("<NULL>", (None, 0))[1] == 1 and result.get(WRITER) == ("rehearsal", 1)
    return {"table": table, "rows": result, "ok": ok}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scratch", required=True)
    a = ap.parse_args()
    try:
        out = run(a.scratch)
        print(out)
        print("PASS" if out["ok"] else "FAIL: expected one legacy (NULL) row and one "
              f"{WRITER}/rehearsal row")
        return 0 if out["ok"] else 1
    finally:
        from nfl_dfs.config import settings
        print(f"cleanup: bq rm -f -t {settings.predictions.replace('.', ':', 1)}.{a.scratch}")


if __name__ == "__main__":
    sys.exit(main())
