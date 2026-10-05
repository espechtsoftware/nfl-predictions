"""Chase-injury study, PART 2 (HINDSIGHT; descriptive): re-deals of the ENTERED Week-4 book (A1 = the entered union,
book sha 010df6c0) with Ja'Marr Chase's ENTRY exposure limited, scored on the real Week-4 contests by moneygate_score's
validated path. Any "less Chase" arm wins by construction in a week he left injured: this is NOT a decision basis. The
decision basis is study 1b (system study Addendum 123: an entry-level player cap halves the single-bust swing but costs
2.4-4.3 points of mean entry finish; no adoption).

Arms (the same 110 book rows; only the dealing of entries to rows changes):
  A1      the entered dealing
  CAP30   Chase in at most floor(0.30 x entries) entries      } in deal order (contests in plan order, ranks in order),
  CAP20   Chase in at most floor(0.20 x entries) entries      } an entry over the limit takes the next book row in solve
  STEER   Chase only in rows that also hold Joe Burrow        } order that is allowed, not already in that contest and,
                                                                in a contest the small-contest overlap rule governs
                                                                (mean track, 2-10 entries, M 5), shares <= 5 players with
                                                                every row already there; none fits -> the entry keeps its
                                                                row (counted as a miss)
    python scripts/moneygate_chase_hindsight.py
Prints multiples of fees, cashes, entries changed and misses (public); dollars stay in the private results.
"""
from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moneygate_score as MS  # noqa: E402

CHASE, BURROW = "Ja'Marr Chase", "Joe Burrow"
M_SHARED, CEILING = 5, 10


def governed(c: dict, n: int) -> bool:
    return str(c.get("track", "mean")) == "mean" and "ranks" not in c and 2 <= n <= CEILING


def redeal(contests: list[dict], layout: dict, book_names: list[frozenset], allowed) -> tuple[dict, int, int]:
    """allowed(row_index, chase_entries_so_far) -> bool. Returns (layout, entries changed, misses)."""
    out = copy.deepcopy(layout); count, changed, misses = 0, 0, 0
    for c in contests:
        cid = str(c["contest_id"]); rows = list(layout["contests"][cid]["rows"])
        gov = governed(c, len(rows)); chosen = []
        for r in rows:
            def ok(q):
                if q in chosen or not allowed(q, count):
                    return False
                return not gov or all(len(book_names[q] & book_names[x]) <= M_SHARED for x in chosen)
            pick = next((q for q in [r] + [q for q in range(len(book_names)) if q != r] if ok(q)), None)
            if pick is None:
                misses += 1; pick = r
            changed += int(pick != r); chosen.append(pick); count += int(CHASE in book_names[pick])
        out["contests"][cid]["rows"] = chosen
        out["contests"][cid]["lineups"] = [layout["_body"][q] for q in chosen]
    return out, changed, misses


def main() -> int:
    MS.require_reconcile([1, 2, 3, 4])
    cfg = MS.load_config(); W = MS.load_week(cfg, 4)
    a1 = json.loads((MS.BOOKS / "w4" / "A1" / "layout.json").read_text())
    union = Path(cfg["weeks"]["4"]["entered_union"])
    b = json.loads((union / "book.json").read_text())
    names = [frozenset(e["players"]) for e in b["entries"] + b["tail_sleeve"]]
    body = [list(r) for r in MS_read_book(MS.BOOKS / "w4" / "A1" / "run1" / "book.csv")]
    if len(names) != len(body):
        raise SystemExit(f"book.json rows {len(names)} != book.csv rows {len(body)}")
    # the two files must list the same lineups in the same order: map each DK id through the T-70 frame and compare
    bad = [i for i, (nm, ids) in enumerate(zip(names, body))
           if {MS.canon(x) for x in nm} != {MS.canon(W.name_of.get(str(d), "?")) for d in ids}]
    if bad:
        raise SystemExit(f"book.json and book.csv disagree on rows {bad[:5]} (of {len(bad)})")
    a1["_body"] = body
    contests = W.contests
    n = sum(len(a1["contests"][str(c["contest_id"])]["rows"]) for c in contests)
    arms = {"A1": (a1, 0, 0)}
    for tag, share in (("CAP30", 0.30), ("CAP20", 0.20)):
        cap = int(math.floor(share * n))
        arms[tag] = redeal(contests, a1, names, lambda q, cnt, cap=cap: CHASE not in names[q] or cnt + 1 <= cap)
    arms["STEER"] = redeal(contests, a1, names, lambda q, cnt: CHASE not in names[q] or BURROW in names[q])
    print("CHASE-INJURY STUDY, PART 2: HINDSIGHT re-deals of the entered W4 book (not a decision basis; see study 1b)")
    print(f"entries {n} in {len(contests)} plan contests; book rows {len(names)} (Chase in {sum(CHASE in r for r in names)}, "
          f"with Burrow {sum(CHASE in r and BURROW in r for r in names)})")
    for tag, (lay, changed, misses) in arms.items():
        lay = {k: v for k, v in lay.items() if k != "_body"}
        R = MS.score_book(W, lay)[0]
        chase_e = sum(CHASE in names[q] for c in contests for q in lay["contests"][str(c["contest_id"])]["rows"])
        print(f"  {tag:6s} Chase entries {chase_e:3d} ({chase_e / n:.3f}) | changed {changed:3d} misses {misses:3d} | multiple "
              f"{MS.multiple([R]):.3f} | ex-largest {MS.multiple([R], True):.3f} | cashes {sum(r.cashes for r in R.values())} | "
              f"mean entry pct {MS.mean_pct(R):.2f}")
    return 0


def MS_read_book(path: Path) -> list[list[str]]:
    import csv
    rows = list(csv.reader(open(path, newline="")))
    return rows[1:]


if __name__ == "__main__":
    raise SystemExit(main())
