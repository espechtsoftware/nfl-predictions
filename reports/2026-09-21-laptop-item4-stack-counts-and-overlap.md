# Laptop review item 4: stack counts reproduced, overlap figure corrected

Answering item 4 of `handoffs/2026-09-21-laptop-postmortem-review-round1.md`:

> Verify the claimed stack counts: prior frozen delivery review counted 87
> depth-2, 8 depth-3, 2 depth-4. Define whether stack depth includes TE/FLEX/RB
> before reporting 100% depth-2. Check pairwise overlap definition: six heavy
> exposures make the reported 1.60 worth reconciling directly from canonical
> nine-player sets.

Computed from the canonical nine-player sets in
`receipts/2026-09-21-week2-post-mortem/our-97-results.csv`, joined to
`player-signals-week2.csv` for position and team. **All 97 lineups parsed, zero
unmatched player names.**

## 1. Your counts reproduce exactly. The disagreement is purely definitional.

Counting **receivers only** (QB + same-team WR/TE):

| depth | lineups | share |
|---|---|---|
| 3 | **87** | 89.7% |
| 4 | **8** | 8.2% |
| 5 | **2** | 2.1% |

**87 / 8 / 2 — identical to your frozen delivery review.** The labels differ by
one because you count *teammates* and we counted *QB + teammates*. Same lineups,
same partition, two conventions.

**Proposed convention, so this cannot recur:** report stack depth as the number
of players from the quarterback's team **including the quarterback**, and state
the pass-catcher/RB inclusion rule alongside it. A bare "depth-2" is ambiguous
in exactly the way that produced this exchange.

## 2. "100% depth-2" is wrong under either convention

The modal bucket is **89.7%**, not 100%. Eight lineups carry one more
pass-catcher and two carry two more. That is a real spread, and flattening it
to 100% hides the eight-plus-two tail that a stack study would care about most.

## 3. Including RB changes the picture materially — your question was the right one

Counting **all skill** (QB + same-team WR/TE/**RB**):

| depth | lineups | share |
|---|---|---|
| 3 | 46 | 47.4% |
| 4 | 45 | 46.4% |
| 5 | 4 | 4.1% |
| 6 | 2 | 2.1% |

**Nearly half the book carries a same-team running back that the
receivers-only count makes invisible.** The receivers-only view says the book is
overwhelmingly one shape (89.7% at a single depth); the all-skill view says it
is split almost evenly between two. Any conclusion about stack concentration
depends entirely on which was used, which is why the definition has to be
stated before the number.

## 4. The 1.60 overlap figure does not reproduce

Mean pairwise overlap across all C(97,2) = 4,656 pairs of canonical
nine-player sets:

| definition | mean overlap |
|---|---|
| **all 9 including DST (canonical)** | **1.421** |
| 8 skill, DST excluded | 1.185 |
| first 30 rows only | 1.244 |
| first 30, DST excluded | 1.051 |

**None of the four reproduces 1.60.** The canonical answer is **1.421**. We are
not claiming to know where 1.60 came from — only that we could not obtain it
from the delivered book under any natural definition, and that the published
figure should be corrected to 1.421 with the definition stated.

Full distribution (canonical): 895 pairs share **0** players, 1,862 share 1,
1,227 share 2, 460 share 3, 149 share 4, 55 share 5, and **8 pairs share 6**.
That long right tail is presumably the "six heavy exposures" you flagged — it is
real, but it sits on a mean well below the reported one.

## 5. Unrelated, but useful to the lab: `mean25` exists on our side

`player-signals-week2.csv` carries a **`mean25`** column (with `n25` alongside
it). The lab's forecast-perturbation view 3 is currently blocked because
`mean25` exists nowhere in the nfl2 tree, and they correctly made it fail closed
rather than substitute `mean_projection`. If that column is the same quantity,
production can supply it and the history-blend arm becomes runnable instead of
being dropped to three arms. Worth one confirmation between you before anyone
builds around it.

## Remaining items from your review

Items 1, 2, 3, 5, 6 and 7 are open on our side. Item 8 is substantially covered
by today's work — `HANDOFF.md` now carries deployed image identities, completed
versus pending fixes, and unresolved risks, and
`reports/2026-09-21-silent-failure-traps.md` covers the end-to-end rehearsal
hazards. Item 6 (all entrants stratified by entry count, salary and contest,
rather than winner-only) is the one we are best placed to do next, since it
needs `nfl_raw.contest_entries` — say if you would rather take it.
