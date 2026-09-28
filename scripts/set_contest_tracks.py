#!/usr/bin/env python3
"""Set each contest's selection track and the tail dealing order (reviewer revision, operator 2026-09-28, item 1):
the class selector owns every contest except the small $20 satellites, so `track` is `tail` unless the contest's field
(from dk_contest_details.py) is at most --mean-max-field entries (default 20: the 11-entry satellites). Tail contests are
then re-ordered by their `priority` (1 = dealt first: Millionaire, $125 FFWC sat, $4,444, wildcats, supersats, FFWC
qualifier) because enter_layout deals sleeve rows to tail contests in file order. Names are never consulted.

  python scripts/set_contest_tracks.py --contests contests.json --details contest-details-YYYYMMDD.json [--write]
      [--mean-max-field 20]

OPERATOR DECISION 2026-09-28 10:07 (configuration A): every contest is on the MAIN track and LIVE_SELECTOR=class orders
the whole book over the head layout (Week 3 rehearsal: 33 paid vs 24 for all-tail-by-priority, which hands the $2
satellites the last class rows). That is `--all-main`: `track: mean` on every contest (mean = the main track name the
layout knows; the class selector is what orders it), no priority needed, TAIL_SLEEVE becomes 0. The tail/priority rule
above stays available for a week that wants a separate sleeve.

Without --write it prints the decision and the deal order and changes nothing. With --write it rewrites contests.json in
place (a `.bak` copy first), keeping every other field. It refuses (exit 2) when a contest is missing from the details
file, its field size or ladder is missing, a tail contest has no integer `priority`, two tail contests share one, or a
`track_override` is not mean|tail -- never a silent default. `track_override` keeps the operator's choice, disclosed.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def paid_places(details: dict) -> int | None:
    tiers = details.get("payoutSummary") or []
    if not tiers:
        return None
    return max(int(t["maxPosition"]) for t in tiers)


def decide(contests: list[dict], details: dict, mean_max_field: int, all_main: bool = False) -> tuple[list[dict], list[str], list[str]]:
    """Returns (contests in the new file order, printout lines, problems). Mean contests keep file order and come first;
    tail contests follow, sorted by priority. With all_main every contest is main-track (track "mean") in file order."""
    decided, lines, problems = [], [], []
    for c in contests:
        cid = str(c["contest_id"]); d = details.get(cid)
        if d is None:
            problems.append(f"{cid} ({c.get('name')}): not in the details file"); continue
        field = d.get("max") or d.get("maximumEntries") or d.get("entries")
        places = paid_places(d)
        if not field or places is None:
            problems.append(f"{cid} ({c.get('name')}): field size or ladder missing"); continue
        rule = "mean" if (all_main or int(field) <= mean_max_field) else "tail"
        override = None if all_main else c.get("track_override")
        if all_main and c.get("track_override") not in (None, "mean"):
            problems.append(f"{cid} ({c.get('name')}): track_override {c.get('track_override')!r} contradicts --all-main"); continue
        if override is not None and override not in ("mean", "tail"):
            problems.append(f"{cid} ({c.get('name')}): track_override must be mean or tail, got {override!r}"); continue
        track = override or rule
        n = dict(c); n["track"] = track
        n["line_percentile"] = round(100.0 * (1.0 - places / float(field)), 2)
        if track == "tail":
            p = c.get("priority")
            if not isinstance(p, int) or isinstance(p, bool):
                problems.append(f"{cid} ({c.get('name')}): tail contest needs an integer priority (1 = dealt first)"); continue
        note = f" (operator override; rule said {rule})" if override and override != rule else (" (operator override)" if override else "")
        decided.append(n)
        lines.append(f"{str(c.get('name')):14s} {cid} field {int(field):>7,} pays {places:>5} (line p{n['line_percentile']:.1f}) -> "
                     + ("main (class selector orders the book)" if all_main else track)
                     + (f" priority {c['priority']}" if track == "tail" else "") + note)
    if problems:
        return list(contests), lines, problems
    tails = [c for c in decided if c["track"] == "tail"]
    seen: dict[int, str] = {}
    for c in tails:
        if c["priority"] in seen:
            problems.append(f"priority {c['priority']} is shared by {seen[c['priority']]} and {c.get('name')}")
        seen[c["priority"]] = str(c.get("name"))
    if problems:
        return list(contests), lines, problems
    out = [c for c in decided if c["track"] == "mean"] + sorted(tails, key=lambda c: c["priority"])
    cursor = 1
    for c in out:
        if c["track"] == "tail":
            lines.append(f"deal: sleeve rows {cursor}-{cursor + int(c['entries']) - 1} -> {c.get('name')} (priority {c['priority']})")
            cursor += int(c["entries"])
    return out, lines, problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--contests", type=Path, required=True)
    ap.add_argument("--details", type=Path, required=True)
    ap.add_argument("--mean-max-field", type=int, default=20, help="a field at most this size stays on the mean track (the 11-entry $20 satellites)")
    ap.add_argument("--all-main", action="store_true", help="configuration A (operator 2026-09-28): every contest on the main track; LIVE_SELECTOR=class orders the book")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    raw = json.loads(a.contests.read_text()); contests = raw if isinstance(raw, list) else raw["contests"]
    details = json.loads(a.details.read_text())
    out, lines, problems = decide(contests, details, a.mean_max_field, all_main=a.all_main)
    for ln in lines:
        print(ln)
    if problems:
        print("TRACKS NOT SET: " + "; ".join(problems), file=sys.stderr); return 2
    n_tail = [c for c in out if c["track"] == "tail"]
    if a.all_main:
        print(f"configuration A: {len(out)} contests ({sum(int(c['entries']) for c in out)} entries) all on the main track; "
              f"TAIL_SLEEVE=0, LIVE_SELECTOR=class, ENTER_LAYOUT=head, ENTER_ORDER=greedy")
    print(f"{len(n_tail)} tail contests ({sum(int(c['entries']) for c in n_tail)} sleeve rows), "
          f"{len(out) - len(n_tail)} mean contests ({sum(int(c['entries']) for c in out if c['track'] == 'mean')} entries; BOOK_ENTRIES = the layout's mean rows, floor 1)")
    if a.write:
        shutil.copy(a.contests, a.contests.with_suffix(a.contests.suffix + ".bak"))
        payload = out if isinstance(raw, list) else {**raw, "contests": out}
        a.contests.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"wrote {a.contests} (backup {a.contests.with_suffix(a.contests.suffix + '.bak')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
