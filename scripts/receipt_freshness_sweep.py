#!/usr/bin/env python3
"""Flag any artifact receipt that records reading data from before the week it is for.

Detection for the staleness class found 2026-09-21, when every Week-2 composite
ordering was discovered to have scored Week-2 lineups against the last Week-1
projection batch and Week-1 props. The tool did not fail: the projection join is
by player, not by week, so it returned last week's numbers and the receipt's
coverage block read a healthy 134 of 149. The only trace was a timestamp.

That trace is mechanical, so check it every week instead of relying on someone
reading a receipt. Run this over the week's output directory once the build has
finished, before uploading anything:

  python scripts/receipt_freshness_sweep.py --dir /home/erich/week3-sunday \\
      --after 2026-09-22

Exit 0 when every recorded input is at or after --after; exit 1 and list the
offenders otherwise. Read-only.

Set --after to the start of the week's own data window, normally the Monday
before that week's games. Fields that legitimately look backwards -- prior-season
points per game, trailing-window features, backup history -- are skipped by name;
extend --benign if a new one appears.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import date

DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
DEFAULT_BENIGN = ("dk_ppg", "prior", "_l4", "_l6", "_l8", "last_season", "backup", "history",
                  "season_to_date", "career")
LIST_SCAN_LIMIT = 200


def walk(obj, path=""):
    """Yield (dotted path, string value) for every string in a JSON document."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:LIST_SCAN_LIMIT]):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def first_date(text):
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def scan_document(data, after, benign=DEFAULT_BENIGN):
    """Return [(path, date)] for recorded inputs older than `after`."""
    out = []
    for path, value in walk(data):
        low = path.lower()
        if any(b in low for b in benign):
            continue
        d = first_date(value)
        if d is not None and d < after:
            out.append((path, d))
    return out


def sweep(root, after, benign=DEFAULT_BENIGN):
    """Scan every JSON receipt under `root`. Returns (findings, files_scanned)."""
    root = pathlib.Path(root)
    findings, scanned = [], 0
    for f in sorted(set(list(root.glob("*.json")) + list(root.glob("*/*.json")))):
        try:
            data = json.loads(f.read_text())
        except (ValueError, OSError):
            continue
        scanned += 1
        for path, d in scan_document(data, after, benign):
            findings.append({"artifact": f.parent.name or f.name, "file": str(f),
                             "field": path, "date": d.isoformat()})
    return findings, scanned


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="the week's output directory")
    ap.add_argument("--after", required=True, help="ISO date starting the week's data window")
    ap.add_argument("--benign", action="append", default=[],
                    help="extra path substring to skip; repeatable")
    ap.add_argument("--json", dest="as_json", action="store_true")
    a = ap.parse_args(argv)

    try:
        after = date.fromisoformat(a.after)
    except ValueError:
        ap.error(f"--after must be an ISO date, got {a.after!r}")
    root = pathlib.Path(a.dir)
    if not root.is_dir():
        ap.error(f"--dir {root} is not a directory")

    findings, scanned = sweep(root, after, DEFAULT_BENIGN + tuple(a.benign))
    if a.as_json:
        print(json.dumps({"dir": str(root), "after": a.after, "scanned": scanned,
                          "findings": findings}, indent=2))
    else:
        print(f"scanned {scanned} receipts under {root}, window starts {after}\n")
        if not findings:
            print("  OK: every recorded input is at or after the window start")
        else:
            seen = {}
            for f in findings:
                seen.setdefault((f["artifact"], f["field"]), set()).add(f["date"])
            for (art, field), dates in sorted(seen.items()):
                print(f"  STALE  {art:<46} {field:<42} {sorted(dates)}")
            print(f"\n  {len(findings)} stale input reference(s) across "
                  f"{len({f['artifact'] for f in findings})} artifact(s).")
            print("  An artifact that read data from before its own week is the "
                  "2026-09-21 class: check which slice the tool selected.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
