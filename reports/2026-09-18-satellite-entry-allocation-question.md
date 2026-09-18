# How should 97 entries be spread over 12 contests? (2026-09-18, decision pending)

**Status: open question, nothing deployed.** The layout in force is unchanged (`top`: every contest receives the vetted
book's ranks 1..N). The code now *supports* per-contest blocks (`"block": true` in `contests.json`), but no contest sets
it and `contests.json` is reverted to the shipped configuration. Written for the reviewing agent on the laptop and for
the operator; the operator asked the two agents to agree a recommendation.

## The situation

Week 2 reserves **97 entries across 12 contests** (fees $246). Under the `top` layout every contest independently
receives the best N lineups of the 90-lineup book, so:

- only **23 distinct lineups** are used; ranks 24–90 of the book are never entered;
- lineup #1 appears in **all 12 contests**, #2 in 9, #3–#5 in 7 each;
- **62 of the 97 entries are the five satellite contests** (16 + 16 + 10 + 10 + 10), each currently holding ranks 1..N,
  so those five outcomes are perfectly correlated in score — they differ only in which field they meet.

Within a contest this is right and unchanged: every entry in a contest is a different lineup. The question is only
whether the *satellites* should repeat the same best block or take disjoint blocks of the book.

## The measurement

Computed on the corrected Week-2 rehearsal book's own 20,000 simulated worlds (run
`20260917T150719330879Z-e7255e9`, production-law projections). "Seat" = that contest's block contains a lineup at or
above the cutoff. Week-1's Millionaire top-4% line was ≈ 192 points, so 190 is the honest middle row.

| cutoff | CURRENT — all five take ranks 1..N | | PROPOSED — disjoint blocks (1–16, 17–32, 33–42, 43–52, 53–62) | |
|---|---:|---:|---:|---:|
| | P(≥1 seat) | E[seats] | P(≥1 seat) | E[seats] |
| 180 | 0.594 | 2.73 | 0.776 | 2.37 |
| **190** | **0.415** | **1.88** | **0.610** | **1.57** |
| 200 | 0.265 | 1.18 | 0.433 | 0.95 |
| 210 | 0.155 | 0.69 | 0.275 | 0.53 |

Block quality decays slowly: E[max] by block is 187.1, 184.2, 177.1, 176.2, 177.0. The later blocks are ~10 points
worse, not catastrophically so.

**The trade is unambiguous and goes both ways:** repeating the best block wins ~20 % more expected seats; disjoint
blocks raise the probability of winning *at least one* seat by ~20 percentage points (0.415 → 0.610 at the 190 line).

## Why this is a judgement call, not an optimisation

It hinges on what a satellite seat is worth to this operator, and the two framings disagree:

1. **Seats are linearly valuable** ($20 Millionaire entry each; five seats = five entries). Then maximise E[seats] and
   **keep the current layout**.
2. **Seats have decreasing value.** The ledger's own evidence says the Millionaire is the contest this book is worst
   suited to: the top-1,000 line was 228.2 in Week 1 and our K80 book clears 220 in ~1 week of 72. The operator also
   cut his Millionaire entries from 4 to 1 this week for exactly that reason. Under that view a fifth seat into a
   contest we rarely compete in is worth much less than the first, and **reliability wins**.

There is a third possibility neither framing covers: if satellite seats are worth little *because the Millionaire is a
bad fit*, the sharper question is whether 62 of 97 entries belong in satellites at all. That is a bankroll decision and
explicitly the operator's, not ours.

## My recommendation (operating agent)

**Disjoint blocks for the five satellites, `top` unchanged for the other seven contests.** Reasons: the operator's own
revealed preference this week is that Millionaire entries have low marginal value to him; converting one or two seats
reliably matches that better than a 41 % chance of five and a 59 % chance of none; and the quality cost is ~10 points
of block ceiling, which is small next to the 20-point swing in P(≥1). It also puts 62 rather than 23 of the book's
lineups to work, which is the only way the deeper book earns anything.

**Confidence: moderate.** This is one week's simulated worlds, the simulator's tail is known to be optimistic, and no
preregistered test backs it. It is an allocation choice, not a scoring claim.

## Question for the reviewing agent

1. Do you agree the decision hinges on the marginal value of a seat, and that framing 2 fits this operator's stated
   position?
2. Is there an error in the estimate? In particular: the five satellites meet *different fields*, which the calculation
   ignores by using one score cutoff for all five; and the 190 cutoff is borrowed from a Millionaire field, not a
   satellite field. Does either materially change the ordering?
3. Would you allocate differently, e.g. two satellites on the top block and three on distinct blocks, or blocks chosen
   for diversity rather than by rank?
4. Anything you would want measured before Saturday that is cheap.

Reply on your review branch; whichever way we agree, it is a one-line change per contest in `contests.json` with no
code change, and it must be settled before the Saturday 10:30 CT build so the ENTER bundle is built once.
