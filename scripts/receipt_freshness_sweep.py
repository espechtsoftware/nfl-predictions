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

Only DECLARED inputs are scanned (O-24, 2026-10-04): the receipts the Sunday chain
itself writes or reads, listed in DECLARED_INPUTS below. The sweep used to read every
JSON file under the week directory, so comparison-only captures saved there (a
LineStar payload carrying 2025 period history) printed "STALE INPUTS DETECTED -- DO
NOT UPLOAD" on the live sheet minutes before lock. Undeclared files are counted on
one informational line, never reported as stale. A new artifact family the chain
starts writing must be added to DECLARED_INPUTS (or passed with --declared);
--all restores the scan-everything audit for a manual look.
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
# The Sunday chain's inputs and artifacts, as paths relative to the week directory (one pattern per path component; a
# pattern matches only paths of its own depth). Writers: run_week_build.sh (build-inputs), sunday_build_host.sh (per
# RUN_TAG: lever audits, ordering shadows, upload receipts, ownership receipts, cash/week-3 shadows, vetted, composite,
# hybrid15, exposure caps, refinement-2 paper bundle), sunday_after_build.sh (after-<tag>, ENTER), and the operator's
# contests.json, which every build reads.
DECLARED_INPUTS = (
    "build-inputs-*.json",
    "lever-audit-*.json", "ordering_shadows-*.json", "upload-*.receipt.json", "ownership_*.receipt.json",
    "cash-shadow-*/*.json", "shadow-*/*.json", "vetted-*/*.json", "composite-*/*.json", "hybrid15-*/*.json",
    "exposure-caps-*/*.json", "paper-r2-*/*.json",
    "after-*/*.json", "ENTER/*.json",
    "contests.json",
)


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


def candidates(root):
    """Every JSON file the sweep can see: the week directory and one level below it."""
    root = pathlib.Path(root)
    return sorted(set(list(root.glob("*.json")) + list(root.glob("*/*.json"))))


def is_declared(root, path, declared):
    """True when `path` (under `root`) matches one of the declared patterns at the pattern's own depth."""
    rel = pathlib.PurePosixPath(pathlib.Path(path).relative_to(root).as_posix())
    return any(len(rel.parts) == len(pathlib.PurePosixPath(p).parts) and rel.match(p) for p in declared)


def undeclared(root, declared=DECLARED_INPUTS):
    """JSON files under `root` that are not declared inputs (reported for information, never swept)."""
    root = pathlib.Path(root)
    return [f for f in candidates(root) if not is_declared(root, f, declared)]


def sweep(root, after, benign=DEFAULT_BENIGN, declared=None):
    """Scan the JSON receipts under `root`: only those matching `declared` patterns, or every one when `declared` is
    None (the manual --all audit). Returns (findings, files_scanned)."""
    root = pathlib.Path(root)
    findings, scanned = [], 0
    for f in candidates(root):
        if declared is not None and not is_declared(root, f, declared):
            continue
        if f.name.startswith("class_model"):
            # a fitted MODEL, not a data input: its weeks[].lock are the training weeks and fitted_utc is the Monday
            # refit, both legitimately before the week's window (2026-09-29 sweep item 8). The build audit checks the
            # model's sha256 separately.
            continue
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
    ap.add_argument("--declared", action="append", default=[],
                    help="extra declared input pattern relative to --dir (e.g. 'newtool-*/*.json'); repeatable")
    ap.add_argument("--all", dest="scan_all", action="store_true",
                    help="scan EVERY JSON file under --dir, declared or not (a manual audit; never the Sunday chain)")
    ap.add_argument("--json", dest="as_json", action="store_true")
    a = ap.parse_args(argv)

    try:
        after = date.fromisoformat(a.after)
    except ValueError:
        ap.error(f"--after must be an ISO date, got {a.after!r}")
    root = pathlib.Path(a.dir)
    if not root.is_dir():
        ap.error(f"--dir {root} is not a directory")

    declared = None if a.scan_all else DECLARED_INPUTS + tuple(a.declared)
    findings, scanned = sweep(root, after, DEFAULT_BENIGN + tuple(a.benign), declared)
    ignored = [] if declared is None else undeclared(root, declared)
    if a.as_json:
        print(json.dumps({"dir": str(root), "after": a.after, "scanned": scanned,
                          "scope": "all" if declared is None else "declared",
                          "ignored_undeclared": [str(f) for f in ignored],
                          "findings": findings}, indent=2))
    else:
        scope = "every JSON file (--all)" if declared is None else "declared inputs"
        print(f"scanned {scanned} receipts ({scope}) under {root}, window starts {after}")
        if ignored:
            names = sorted({f.relative_to(root).parts[0] for f in ignored})
            print(f"  not scanned: {len(ignored)} undeclared JSON file(s), not inputs of the chain: "
                  f"{', '.join(names[:6])}{' ...' if len(names) > 6 else ''}")
        print()
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
