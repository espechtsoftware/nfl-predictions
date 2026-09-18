"""Verify a staged ENTER/ bundle before it is published (2026-09-17 review finding 5).

Usage: verify_enter_bundle.py contests.json STAGE_DIR
Exit 0 only when every configured contest has exactly one per-contest file whose row count equals its configured
entry count and whose every row carries nine non-empty lineup cells. Prints one line either way; the caller keeps the
previous bundle on failure.
"""
from __future__ import annotations

import csv
import glob
import json
import pathlib
import sys


def main(contests_path: str, stage: str) -> int:
    contests = json.load(open(contests_path))
    stage_dir = pathlib.Path(stage)
    bad: list[str] = []
    total = 0
    for c in contests:
        pat = f"ENTER-{c['name']}-{c['contest_id']}-*-entries-KEEP-first-*.csv"
        files = sorted(glob.glob(str(stage_dir / pat)))
        if len(files) != 1:
            bad.append(f"{c['name']}-{c['contest_id']}: {len(files)} files match {pat}")
            continue
        with open(files[-1], newline="") as handle:
            rows = list(csv.reader(handle))[1:]
        if len(rows) != int(c["entries"]):
            bad.append(f"{c['name']}: {len(rows)} rows, configured {c['entries']}")
        for i, row in enumerate(rows, start=1):
            cells = [x.strip() for x in row[:9]]
            if len(cells) != 9 or any(not x for x in cells):
                bad.append(f"{c['name']} row {i}: {sum(1 for x in cells if x)}/9 lineup cells")
                break
        total += len(rows)
    if bad:
        print("staged bundle INVALID: " + "; ".join(bad), file=sys.stderr)
        return 1
    print(f"staged bundle verified: {len(contests)} contests, {total} entry rows, every row 9/9 cells")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_enter_bundle.py contests.json STAGE_DIR")
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
