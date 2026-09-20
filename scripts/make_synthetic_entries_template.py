#!/usr/bin/env python3
"""Write a SYNTHETIC DraftKings entries export for rehearsals: one row per reserved entry from contests.json with fake
entry ids (9xxxxxxxxx), empty roster cells and DK's column layout. Carries no real entry key, cookie or user data.
  python make_synthetic_entries_template.py contests.json OUT.csv"""
import csv, json, sys
c = json.load(open(sys.argv[1])); c = c if isinstance(c, list) else c["contests"]
hdr = ["Entry ID", "Contest Name", "Contest ID", "Entry Fee", "QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
eid = 9000000001
with open(sys.argv[2], "w", newline="") as h:
    w = csv.writer(h); w.writerow(hdr)
    for x in c:
        for _ in range(int(x["entries"])):
            w.writerow([str(eid), f"SYNTHETIC {x.get('name')}", str(x["contest_id"]), "$0", *([""] * 9)]); eid += 1
print(f"synthetic template: {eid - 9000000001} entry rows across {len(c)} contests -> {sys.argv[2]}")
