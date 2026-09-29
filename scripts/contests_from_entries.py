#!/usr/bin/env python3
"""Build the week's private contests.json from the operator's DraftKings entries export (DKEntries*.csv).

  python scripts/contests_from_entries.py --entries <DKEntries.csv> --details <contest-details.json> --out contests.json \\
      [--group <Sunday-main draft group id>] [--exclude-group <id>]...

One contests.json row per contest: name (a short label derived from the DK contest name: milly / sat / supersat / wildcat /
ffwc / huddle / other, suffixed to stay unique), contest_id, entries (the export's row count for it), keep (= entries), fee,
dk_name, draft_group. Contests whose draft group is not the Sunday main group (a Thu-Mon Classic, a Showdown) are
written to <out>.other.json and printed, never into the main file: the Sunday chain must not lay them out. The main
draft group is --group when given, else the group holding the most contests; the file refuses (exit 2) if the
details file lacks a contest or its draftGroupId, or if a contest id repeats with two names.

The export holds entry keys and any already-filled lineups: it stays private (never committed); this script reads only
the four header columns and writes none of them.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path


def short_label(dk_name: str) -> str:
    n = dk_name.lower()
    if "wild card" in n or "wildcat" in n:
        return "wildcat"
    if "super satellite" in n or "supersat" in n:
        return "supersat"
    if "world championship" in n or "ffwc" in n:
        return "ffwc"
    if "satellite" in n or "qualifier" in n:
        return "sat"
    if "millionaire" in n and "ticket" not in n:
        return "milly"
    if "huddle" in n:
        return "huddle"
    if "play-action" in n or "play action" in n:
        return "playaction"
    return re.sub(r"[^a-z0-9]+", "", n.split("[")[0])[:12] or "contest"


def read_export(path: Path) -> OrderedDict:
    """{contest_id: {dk_name, fee, entries}} from the export's first four columns; a repeated id must keep one name."""
    out: OrderedDict = OrderedDict()
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    head = [h.strip() for h in rows[0][:4]]
    if head != ["Entry ID", "Contest Name", "Contest ID", "Entry Fee"]:
        raise SystemExit(f"{path}: unexpected header {head}")
    for r in rows[1:]:
        if len(r) < 4 or not r[2].strip():
            continue
        cid, name, fee = r[2].strip(), r[1].strip(), r[3].strip().replace("$", "").replace(",", "")
        rec = out.setdefault(cid, {"dk_name": name, "fee": float(fee or 0), "entries": 0})
        if rec["dk_name"] != name:
            raise SystemExit(f"contest {cid} appears with two names: {rec['dk_name']!r} / {name!r}")
        rec["entries"] += 1
    if not out:
        raise SystemExit(f"{path}: no entries")
    return out


def build(export: OrderedDict, details: dict, group: str | None, exclude: set[str]) -> tuple[list[dict], list[dict], str]:
    missing = [cid for cid in export if cid not in details or not details[cid].get("draftGroupId")]
    if missing:
        raise SystemExit(f"details file lacks a contest or its draftGroupId: {missing}")
    groups = Counter(str(details[cid]["draftGroupId"]) for cid in export)
    main = group or groups.most_common(1)[0][0]
    counts: Counter = Counter()
    main_rows, other_rows = [], []
    for cid, rec in export.items():
        g = str(details[cid]["draftGroupId"])
        base = short_label(rec["dk_name"])
        counts[base] += 1
        label = base if counts[base] == 1 else f"{base}{counts[base]}"
        row = {"name": label, "contest_id": cid, "entries": rec["entries"], "keep": rec["entries"], "fee": rec["fee"],
               "dk_name": rec["dk_name"], "draft_group": g}
        (other_rows if (g != main or g in exclude) else main_rows).append(row)
    return main_rows, other_rows, main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--entries", type=Path, required=True); ap.add_argument("--details", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True); ap.add_argument("--group"); ap.add_argument("--exclude-group", action="append", default=[])
    a = ap.parse_args(argv)
    export = read_export(a.entries)
    details = json.loads(a.details.read_text())
    main_rows, other_rows, group = build(export, details, a.group, set(a.exclude_group))
    a.out.write_text(json.dumps(main_rows, indent=2) + "\n")
    print(f"main draft group {group}: {len(main_rows)} contests, {sum(r['entries'] for r in main_rows)} entries -> {a.out}")
    for r in main_rows:
        print(f"  {r['name']:12s} {r['contest_id']} x{r['entries']:<3d} {r['dk_name'][:60]}")
    if other_rows:
        other = a.out.with_suffix(".other.json"); other.write_text(json.dumps(other_rows, indent=2) + "\n")
        print(f"NOT on the main slate ({len(other_rows)} contests, {sum(r['entries'] for r in other_rows)} entries) -> {other}:")
        for r in other_rows:
            print(f"  {r['name']:12s} {r['contest_id']} x{r['entries']:<3d} group {r['draft_group']} {r['dk_name'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
