"""Priority-first dealing: the book's rows re-ordered so the ranks his priority contests read hold the rows that look most
like what wins there (the operator 2026-10-07: "Let's try to do this one this week"; the outside reviewer's class-E
proposal, logged on review/outside-fill-order-20261006 §4; the frozen W2-4 harm screen
reports/2026-10-07-priority-deal-harm-screen.md, 27a1957b).

The book does not change, only its order. The head layout deals ranks in book order, so the order IS the deal: on his
Week-5 plan (Rev5, his order of 10-07: "two mega 4444 satellites / midseason warmup / 555 / WFFC / 333 / Showdown mega /
everything else") the priority contests read ranks 1-22 (MEGA 1-2, Warm Up 3-5, $555 6-11 and 3-4, FFWC $490 12, $333
13-21, Showdown MEGA 22) and only the $20 Millionaire supersats read 23-26.

ONE pure function (the reviewer, 10-07: the lab copies it verbatim, text sha asserted, and checks its parity): no frame,
no file, no globals beyond the constants below. The standard library only.
"""
from __future__ import annotations

QB_STACK_MIN = 2            # QB teammates for the +2
CHEAP_MAX_SALARY = 4000     # a cheap player's salary is strictly below this
CHEAP_MIN_COUNT = 2         # cheap non-DST players for the +1


def priority_order(rows, pos, team, opp, salary, block_positions=(), return_scores=False):
    """The priority-first order of a book.

    rows: the book's rows in book order, each a sequence of player ids; pos / team / opp / salary: mappings from a player
    id (as it appears in rows) to his DraftKings position, team, opponent and salary. A row's score (pre-lock, from the
    row itself; the definitions of scripts/priority_field_monitor.py, the evidence's source):
      +2  the QB has QB_STACK_MIN (2) or more teammates: players on his team other than the QB and the DST, FLEX included;
      +1  a bring-back: 1 or more non-DST players on the QB's opponent;
      +1  CHEAP_MIN_COUNT (2) or more non-DST players with a salary under CHEAP_MAX_SALARY (4,000).
    The order (the reviewer's block rule, c9028505): the rows at block_positions (0-based; a live term block's) keep
    their positions; every other row is sorted among the other positions by score, highest first, ties keeping the book
    order (a stable sort). Returns the permutation p (new position j holds the row at old position p[j]), or (p, scores)
    with return_scores=True. Raises ValueError on a row without exactly one QB or a block position outside the book, and
    KeyError on a player id a mapping lacks."""
    scores = []
    for r in rows:
        ids = [str(x) for x in r]
        qbs = [x for x in ids if str(pos[x]) == "QB"]
        if len(qbs) != 1:
            raise ValueError(f"a row must hold exactly one QB (got {len(qbs)}): {ids}")
        qb_team, qb_opp = str(team[qbs[0]]), str(opp[qbs[0]])
        stack = sum(1 for x in ids if str(team[x]) == qb_team and str(pos[x]) not in ("QB", "DST"))
        bring = sum(1 for x in ids if str(team[x]) == qb_opp and str(pos[x]) != "DST")
        cheap = sum(1 for x in ids if str(pos[x]) != "DST" and float(salary[x]) < CHEAP_MAX_SALARY)
        scores.append(2 * (stack >= QB_STACK_MIN) + (bring >= 1) + (cheap >= CHEAP_MIN_COUNT))
    n = len(scores)
    fixed = set(block_positions)
    if any(isinstance(f, bool) or not isinstance(f, int) or not 0 <= f < n for f in fixed):
        raise ValueError(f"block positions must be integers in 0..{n - 1} (got {sorted(fixed, key=str)})")
    free = [i for i in range(n) if i not in fixed]
    ranked = sorted(free, key=lambda i: (-scores[i], i))
    perm = list(range(n))
    for slot, i in zip(free, ranked):
        perm[slot] = i
    return (perm, scores) if return_scores else perm
