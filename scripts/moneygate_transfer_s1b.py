"""Study-1b TRANSFER CHECK (descriptive; production prereg reports/2026-10-05-prereg-study1b-entry-player-cap.md, notes
1-4): A1 (the current system, as dealt) vs EA (A1's SAME book, its mean-track entries re-dealt by the study's frozen
assignment cap at 30% of the mean-track entries) on the REAL 2026 W1-4 pools, contests, fields and ladders, scored by
moneygate_score's validated path (the A0 known-answer gate passed exactly; this script only imports it).

EA's re-deal is imported from the lab experiment itself (nfl2 production/s1b-entry-cap-20261005,
experiments/s1b_entry_cap.py: assignment_cap and governed), so it is byte-for-byte the panel's rule. Tail-track
contests are untouched (the panel dealt the mean track only). EW is NOT built here: it needs an entry-weighted ban mode
in union_reselect (production money-path code) and failed the panel on cost, so it is not an adoption candidate
(reviewer, 2026-10-05). Direction: finish pct = share of the contest field an entry beats (higher = better); every
difference is EA - A1. Week 4 motivated the study and is flagged. Not decision-bearing.

    S1B_LAB=<nfl2 s1b worktree> python scripts/moneygate_transfer_s1b.py
"""
from __future__ import annotations

import copy
import csv
import importlib.util
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moneygate_score as MS  # noqa: E402

LAB = Path(os.environ.get("S1B_LAB", Path.home() / "projects" / ".nfl2-worktrees" / "s1b-entry-cap-20261005"))
LEVEL = 0.30


def lab_rule():
    sys.path.insert(0, str(LAB / "src")); sys.path.insert(0, str(LAB / "experiments"))
    spec = importlib.util.spec_from_file_location("s1b_entry_cap", LAB / "experiments" / "s1b_entry_cap.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def ea_layout(S, w: int, a1: dict) -> tuple[dict, dict]:
    """A1's layout with its mean-track entries re-dealt by the frozen assignment cap. Returns (layout, stats)."""
    contests = json.loads((MS.BOOKS / f"w{w}" / "contests.json").read_text())
    rows = list(csv.reader(open(MS.BOOKS / f"w{w}" / "A1" / "run1" / "book.csv", newline="")))
    hdr, body = rows[0], rows[1:]
    if hdr[-1].strip().upper() != "DST":
        raise SystemExit(f"W{w}: unexpected book header {hdr}")
    dst_ids = {r[-1] for r in body}
    mean = [c for c in contests if str(c.get("track", "mean")) == "mean"]
    ranks = [list(a1["contests"][str(c["contest_id"])]["rows"]) for c in mean]
    n = sum(len(r) for r in ranks)
    cap = int(math.floor(LEVEL * n))
    new, misses = S.assignment_cap(body, mean, ranks, cap, dst_ids)
    out = copy.deepcopy(a1); out["arm"] = "EA"
    for c, rr in zip(mean, new):
        out["contests"][str(c["contest_id"])].update(rows=rr, lineups=[body[i] for i in rr])

    def maxexp(rk):
        cnt = Counter(p for r in rk for i in r for p in body[i] if p not in dst_ids)
        return max(cnt.values())
    changed = sum(a != b for x, y in zip(ranks, new) for a, b in zip(x, y))
    return out, {"mean_entries": n, "cap": cap, "misses": misses, "changed": changed,
                 "max_A1": maxexp(ranks), "max_EA": maxexp(new)}


def main() -> int:
    S = lab_rule()
    assert S.OVERLAP_CEILING == 10 and S.SMALL_MAX_SHARED == 5
    MS.require_reconcile([1, 2, 3, 4])
    cfg = MS.load_config()
    weeks = [1, 2, 3, 4]
    data = {w: MS.load_week(cfg, w) for w in weeks}
    a1 = {w: json.loads((MS.BOOKS / f"w{w}" / "A1" / "layout.json").read_text()) for w in weeks}
    ea, st = {}, {}
    for w in weeks:
        ea[w], st[w] = ea_layout(S, w, a1[w])
    res = {"A1": {w: MS.score_book(data[w], a1[w])[0] for w in weeks}, "EA": {w: MS.score_book(data[w], ea[w])[0] for w in weeks}}
    print("STUDY-1b TRANSFER CHECK (descriptive): EA - A1 on the real 2026 W1-4 contests; higher pct = better; "
          "W4 motivated the study; EW not built (no adoption candidate)")
    print("lab rule:", LAB, " A1 book sha:", {w: a1[w]["book_sha256"][:8] for w in weeks})
    tot = {"up": 0, "down": 0}
    for w in weeks:
        A, E = res["A1"][w], res["EA"][w]
        zero = {a: sum(1 for r in res[a][w].values() if r.cashes == 0) for a in ("A1", "EA")}
        up = sum(E[c].pct.mean() > A[c].pct.mean() for c in A); dn = sum(E[c].pct.mean() < A[c].pct.mean() for c in A)
        tot["up"] += up; tot["down"] += dn
        s = st[w]
        print(f"W{w}{' (motivating)' if w == 4 else ''}: mean-track entries {s['mean_entries']} cap {s['cap']} | misses "
              f"{s['misses']} ({s['misses'] / s['mean_entries']:.3f}) | entries changed {s['changed']} | max player entries "
              f"A1 {s['max_A1']} EA {s['max_EA']} | multiple A1 {MS.multiple([A]):.3f} EA {MS.multiple([E]):.3f} | ex-largest "
              f"{MS.multiple([A], True):.3f} vs {MS.multiple([E], True):.3f} | cashes {sum(r.cashes for r in A.values())} vs "
              f"{sum(r.cashes for r in E.values())} | mean entry pct {MS.mean_pct(A):.4f} vs {MS.mean_pct(E):.4f} | contests "
              f"with no cash {zero['A1']} vs {zero['EA']} of {len(A)} | contests EA above/below A1 {up}/{dn}")
    for ws, lab in (((1, 2, 3, 4), "W1-4"), ((1, 2, 3), "W1-3 (excl. motivating W4)")):
        A = [res["A1"][w] for w in ws]; E = [res["EA"][w] for w in ws]
        wm = lambda X: sum(MS.mean_pct(x) * sum(r.n for r in x.values()) for x in X) / sum(r.n for x in X for r in x.values())  # noqa: E731
        print(f"{lab}: multiple A1 {MS.multiple(A):.3f} EA {MS.multiple(E):.3f}; ex-largest {MS.multiple(A, True):.3f} vs "
              f"{MS.multiple(E, True):.3f}; mean entry pct {wm(A):.4f} vs {wm(E):.4f}; misses "
              f"{sum(st[w]['misses'] for w in ws)}/{sum(st[w]['mean_entries'] for w in ws)}")
    print(f"contests EA above / below A1 (W1-4, contest-level, anti-conservative): {tot['up']} / {tot['down']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
