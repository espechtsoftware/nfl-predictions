#!/usr/bin/env python3
"""Monday: score a week's choose_entries record (R4 vs book order R0) on the REAL contest's standings, and add the pair
to the cumulative paired tally (study 32's frozen §5: R4 is a reversible class-S step with a paired R0-vs-R4 shadow).

    python scripts/score_entry_choice.py --choice <choose_entries --out json> --standings <contest-standings-<id>.csv>
        --entered R4|R0|none --tally <private tally.jsonl> [--week 6]

Each set is scored from realized player points (the standings' player table: Player, FPTS; every player must resolve)
against the contest's real entries (Points). A lineup's rank = 1 + the entries scoring at least as much (ties count as
losses, as in the study); the set HITS when its best lineup ranks within the record's S (the places paying >= his line).
The set he actually entered is in the standings itself: one occurrence of each of its lineups' scores is removed from the
field before ranking (--entered). Descriptive monitoring, no verdict rule: the REVIEW POINT is after 8 paired contests,
when the decision on keeping R4 is put to the operator with this tally. Private output (dollars and standings stay out
of tracked files).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nfl_dfs.names import norm_name  # noqa: E402

REVIEW_AFTER = 8


def read_standings(path: Path) -> tuple[np.ndarray, dict[str, float]]:
    """(every entry's Points, {normalised player name: FPTS}) from a DraftKings contest-standings CSV."""
    with Path(path).open(newline="", encoding="utf-8-sig") as h:
        rows = list(csv.reader(h))
    head = rows[0]
    ip, ipl, ifp = head.index("Points"), head.index("Player"), head.index("FPTS")
    pts = np.array([float(r[ip]) for r in rows[1:] if len(r) > ip and r[ip].strip() != ""])
    fpts: dict[str, float] = {}
    dup: set[str] = set()
    for r in rows[1:]:
        if len(r) > ifp and r[ipl].strip():
            k = norm_name(r[ipl].strip())
            if k in fpts:
                dup.add(k)
            fpts[k] = float(r[ifp] or 0.0)
    for k in dup:                                              # a slate-wide name collision cannot be resolved
        fpts.pop(k, None)
    return pts, fpts


def lineup_scores(names: list[list[str]], fpts: dict[str, float]) -> list[float]:
    miss = sorted({n for lu in names for n in lu if norm_name(n) not in fpts})
    if miss:
        raise SystemExit(f"REFUSED: no realized points for {miss[:8]} (every player of both sets must resolve)")
    return [round(sum(fpts[norm_name(n)] for n in lu), 2) for lu in names]


def rank_in(field: np.ndarray, score: float) -> int:
    """1 + the entries scoring at least `score` (ties count as losses)."""
    return 1 + int((field >= score).sum())


def score_sets(field: np.ndarray, r4: list[float], r0: list[float], S: int, entered: str) -> dict:
    f = np.sort(field)
    for sc in {"R4": r4, "R0": r0}.get(entered, []):          # the entered lineups are in the standings: drop one each
        j = np.searchsorted(f, sc, side="left")
        if j < len(f) and abs(f[j] - sc) < 1e-6:
            f = np.delete(f, j)
    out = {}
    for k, sc in (("R4", r4), ("R0", r0)):
        best = max(sc)
        out[k] = {"scores": sc, "best": best, "best_rank": rank_in(f, best), "best_pct": float(np.searchsorted(f, best, side="left") / len(f))}
        out[k]["hit"] = out[k]["best_rank"] <= S
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--choice", type=Path, required=True); ap.add_argument("--standings", type=Path, required=True)
    ap.add_argument("--entered", choices=["R4", "R0", "none"], required=True); ap.add_argument("--tally", type=Path, required=True)
    ap.add_argument("--week", type=int)
    a = ap.parse_args(argv)
    ch = json.loads(a.choice.read_text())
    field, fpts = read_standings(a.standings)
    res = score_sets(field, lineup_scores(ch["R4_names"], fpts), lineup_scores(ch["R0_names"], fpts), int(ch["S"]), a.entered)
    rec = {"week": a.week, "contest_id": ch.get("contest_id"), "contest": ch.get("contest"), "m": ch["m"], "K": ch.get("K"),
           "S": ch["S"], "N_real": int(len(field)), "entered": a.entered, "R4": res["R4"], "R0": res["R0"],
           "scored_utc": datetime.now(timezone.utc).isoformat()}
    prev = [json.loads(x) for x in a.tally.read_text().splitlines() if x.strip()] if a.tally.exists() else []
    if any(p.get("contest_id") == rec["contest_id"] and p.get("week") == rec["week"] for p in prev):
        raise SystemExit(f"contest {rec['contest_id']} week {rec['week']} is already in {a.tally}")
    with a.tally.open("a") as h:
        h.write(json.dumps(rec) + "\n")
    allr = prev + [rec]
    d = sum(int(r["R4"]["hit"]) - int(r["R0"]["hit"]) for r in allr)
    print(f"{rec['contest'] or rec['contest_id']} (m {rec['m']}, K {rec['K']}, S {rec['S']}, field {rec['N_real']}; entered {a.entered}):"
          f" R4 best rank {res['R4']['best_rank']} ({'HIT' if res['R4']['hit'] else 'miss'}), R0 best rank {res['R0']['best_rank']}"
          f" ({'HIT' if res['R0']['hit'] else 'miss'})")
    print(f"PAIRED TALLY: {len(allr)} contest(s); R4 hits {sum(r['R4']['hit'] for r in allr)}, R0 hits {sum(r['R0']['hit'] for r in allr)};"
          f" R4 - R0 = {d:+d}. Review point: after {REVIEW_AFTER} paired contests the decision on keeping R4 goes to the"
          f" operator with this tally ({max(0, REVIEW_AFTER - len(allr))} to go). Descriptive; no verdict rule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
