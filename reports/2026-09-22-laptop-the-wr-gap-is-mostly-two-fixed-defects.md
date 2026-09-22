# The WR gap is mostly two defects already fixed — correcting "nothing targets it"

In `1df45606` I decomposed the Week-2 field gap by slot and wrote that **WR is the largest
recoverable pool (~8.6 of 21.8 points) and nothing currently targets it.** Decomposing the WR
slot by player shows the second half of that sentence is wrong.

## Exposure against the field (Week-2 Millionaire, random 25% sample, 43,203 lineups)

Per-lineup exposure, ours vs field (WR slots only):

| we overweight | ours | field | proj | scored |
|---|---:|---:|---:|---:|
| **Zay Flowers** | **0.32** | **0.00** | 22.57 | **0.0** |
| **Justin Jefferson** | **0.49** | 0.18 | 25.29 | **8.5** |
| Kalif Raymond | 0.18 | 0.04 | 7.96 | 9.0 |
| Ladd McConkey | 0.11 | 0.01 | 17.23 | 6.5 |

| we underweight | ours | field | proj | scored |
|---|---:|---:|---:|---:|
| George Pickens | 0.06 | 0.17 | 14.29 | 10.0 |
| Jalen Coker | 0.05 | 0.14 | 11.93 | 14.6 |
| CeeDee Lamb | 0.10 | 0.17 | 16.55 | 38.3 |
| Garrett Wilson | 0.06 | 0.12 | 14.83 | 16.7 |

The field put **zero** weight on Flowers. We put a third of a slot per lineup on him.

## How much of the gap is those two

| | WR pts/slot |
|---|---:|
| field | 14.06 |
| ours, all WRs | 11.21 |
| **ours, excluding Flowers and Jefferson** | **12.95** |

They hold **22.2%** of our WR slots and account for **61% of the per-slot WR gap** (2.85 → 1.11).
Per lineup, the WR deficit falls from **10.3 to 4.0 points** without them.

## Both are already repaired for Week 3

- **Flowers** was Doubtful — removed at eligibility by nfl2 `69f98a7` (13/13 Doubtful
  player-weeks took zero snaps).
- **Jefferson**'s 25.29 was the DK-PPG stand-in lifting a model value of **18.07** at 55% weight
  (`a2fdb2a9`) — removed by props-or-nothing `82739685`.

So the WR slot *is* targeted: by fixes that shipped before I wrote that it wasn't. The honest
residual is **~1.1 points per WR slot, ~4 points per lineup** — ordinary receiver selection
against the field, spread across mid-priced players (Pickens, Coker, Wilson, Lamb). That residual
is genuinely untargeted, and it is about a fifth of the whole field gap rather than the 40% I
implied.

## The pattern across today's decompositions

Every slot-level deficit I have traced on Week 2 resolves, mostly, into the same few named
availability and pricing defects: dead backup QBs (QB slot), Flowers (WR, availability),
Jefferson (WR, stand-in pricing). **Week 2's gap to the field was concentrated in a handful of
players whose projections were wrong for known reasons, all now addressed.** That is good news for
Week 3 and a warning about reading Week 2 as representative: one slate, and its worst defects are
already gone.

Caveat: the counterfactual replaces the two players' slots with our own non-Flowers/Jefferson WR
average, a simple estimate rather than a re-optimised pool. One slate.
