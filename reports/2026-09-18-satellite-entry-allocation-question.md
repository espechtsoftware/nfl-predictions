# How should 97 entries be spread over 12 contests? (2026-09-18 — DECIDED: keep the authorized layout)

**Status: SETTLED 2026-09-18 04:30Z. Both agents agreed to KEEP the authorized layout; the operator endorsed going with
the reviewing agent's position. `contests.json` is unchanged (12 contests, 97 entries, no block flags) and no code path
was altered. The reasoning is in the final two sections; in short, each satellite awards 25 tickets with a 17–20
per-user entry limit, so the governing quantity is expected tickets, which correlation between our own entries cannot
improve.** Original framing follows.

**Status when written: open question, nothing deployed.** The layout in force is unchanged (`top`: every contest receives the vetted
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

**Confidence: moderate, raised by the historical test below.** The simulated and realized estimates agree in direction
and magnitude across 65 slates. It remains an allocation choice, not a scoring claim, and no preregistered test backs
it.


## Historical test on REALIZED outcomes (added 2026-09-18, at the operator's request)

The measurement above came from simulated worlds. This section uses realized DK points only.

### 65 historical slates (PREREG-097 bank 970, D3200 K80 books, 2021–2024)

Same five contest sizes (16/16/10/10/10), same two layouts, scored on what actually happened:

| cutoff | CURRENT: slates with ≥1 seat | mean seats | DISJOINT: slates with ≥1 seat | mean seats |
|---|---:|---:|---:|---:|
| 180 | 29.2 % | 1.32 | **52.3 %** | 1.08 |
| **190** | 16.9 % | 0.75 | **35.4 %** | 0.54 |
| 200 | 7.7 % | 0.34 | **16.9 %** | 0.23 |
| 210 | 3.1 % | 0.15 | **7.7 %** | 0.12 |
| 220 | 1.5 % | 0.08 | **3.1 %** | 0.05 |

Disjoint blocks **roughly double the share of weeks with at least one seat at every line**, and give up about a quarter
to a third of the mean seat count. The realized numbers agree with the simulated ones in direction and in rough
magnitude, which is reassuring: the simulator was not driving this conclusion.

### Week 1 2026 alone — and why it is a perfect illustration, not evidence

The two real Week-1 books give **opposite answers**:

| book (80 lineups, entered order) | best | CURRENT seats @190 | DISJOINT seats @190 | block bests |
|---|---:|---:|---:|---|
| v4b (scratch-swaps only, the better book) | 210.1 | **5** | 2 | 205.8, 187.1, 182.5, 180.7, 210.1 |
| v6b (what was actually entered) | 189.7 | 0 (@180: 0) | 0 (@180: **4**) | 179.3, 182.3, 189.7, 180.7, 188.3 |

With v4b the top block held a 205.8, so repeating it would have won **all five seats** while disjoint blocks won two.
With v6b the top block topped out at 179.3 and would have won **nothing** at the 180 line, while disjoint blocks would
have won four. That is the variance story in one week: repeating the best block is all-or-nothing, and which way it
falls is not predictable in advance.

### What this changes

It strengthens the recommendation without changing its basis. The historical record says disjoint blocks roughly double
the frequency of winning at least one seat and cost about 30 % of expected seats — the same trade the simulation
showed. The decision still hinges on whether the fifth seat is worth as much as the first. It is not a scoring
improvement and must not be described as one.

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

## The operator's third option: keep the core, swap a low-dollar player (tested 2026-09-18)

He proposed a middle way: enter the best lineup's *core* several times, changing one cheap player each time, so the
entries are related but not identical. Tested on the same 65 historical slates with realized DK points. Variants were
built the way one would live: take the rank-1 roster, replace the chosen slot with the highest-projected legal
alternative at the same position under the $50,000 cap (mean 103 alternatives available per slate; the cheapest skill
slot averaged $3,420 and was a WR or TE in 64 of 65 slates).

Each option below is one block of ten entries:

| block of 10 entries | mean best score | ≥180 | ≥190 | ≥200 |
|---|---:|---:|---:|---:|
| the single best lineup, 10 copies | 126.2 | 3.1 % | 3.1 % | 3.1 % |
| core + 9 **cheap**-player swaps | 135.4 | 7.7 % | 4.6 % | 3.1 % |
| core + 9 **expensive**-player swaps | 137.6 | 6.2 % | 3.1 % | 3.1 % |
| core + 4 cheap + 5 expensive swaps | 139.4 | 7.7 % | 4.6 % | 3.1 % |
| **the book's own ranks 1–10** | **165.1** | **24.6 %** | **13.8 %** | **6.2 %** |

**The idea works in the direction he expected but by far too little.** Swapping one player lifts the block's best score
by 9–13 points over ten copies of one lineup, and it does decorrelate slightly — but the book's own ten lineups are 30
points better and hit 180 three times as often. Swapping the expensive slot is no better than the cheap one: the
variance that produces a 190 comes from the *whole* expensive core booming together, and every variant shares it.

A supporting fact from the same books: **the selector already refuses to do this.** Across 65 slates the average number
of book lineups that differ from rank 1 by exactly one player is **0.0** (0.1 within two players). Greedy expected-max
selection deliberately avoids near-duplicates, because a lineup that succeeds in the same worlds as one you already
hold adds almost nothing to the chance that *something* hits. The core-plus-swap family is precisely the set the
selector discards, and the historical record says it is right to.

**Consequence for the satellite question:** this does not become a third allocation option. The live choice remains
between repeating the book's top block and giving each satellite its own block. If the operator's underlying wish is
"entries that are related but not identical", the book's ranks 1–10 already are that — they share players heavily while
succeeding in different worlds, which is the property that matters.

## DECISION INPUT THE REVIEWER ASKED FOR: the actual DraftKings rules (2026-09-18 04:15Z)

The laptop agent declined to endorse disjoint blocks and asked, correctly, for the real payout and field rules before
any allocation decision. Pulled from `nfl_raw.dk_contest_fills` (the host loop's lobby poll), newest row per contest:

| contest | fee | tickets awarded | entries now | max field | per-user entry limit |
|---|---:|---:|---:|---:|---:|
| SUPERSat to $20 Milly (a) | $0.25 | **25** | 753 | 2,378 | 20 |
| SUPERSat to $20 Milly (b) | $0.25 | **25** | 828 | 2,378 | 20 |
| SUPERSat to $20 Milly $1 (a/b/c) | $1 | **25** each | 206 / 233 / 202 | 594 | 17 |
| FFWC Qualifier SUPERSat | $1 | **4** | 10 | 85 | 2 |
| SUPERSatellite to $555 Milly | $19 | **2** | 20 | 68 | 2 |

**This invalidates my metric, exactly as the reviewer argued.** Every satellite awards *multiple* tickets and allows up
to 17–20 entries per user, so several of my own entries can win tickets in the *same* contest. "Seats" is therefore not
capped at one per contest, and the quantity that matters is **the expected number of my entries that finish in the
ticket places** — which is a sum of per-entry probabilities and is therefore **unaffected by correlation between my
entries**. Diversifying cannot improve it; it can only lower it by using weaker lineups.

Recomputed with the real ticket counts and fields (cutoffs interpolated from the Week-1 Millionaire field's
percentile-to-score curve, the only measured field we hold):

| | expected tickets — CURRENT (each takes ranks 1..N) | expected tickets — DISJOINT | P(≥1 ticket) CURRENT | P(≥1) DISJOINT |
|---|---:|---:|---:|---:|
| fields as they stand now | **3.79** | 2.63 | 0.515 | 0.638 |
| if the contests fill | **1.66** | 1.12 | 0.252 | 0.377 |

Disjoint blocks cost **~30 % of expected tickets** and buy **~12 points of probability of at least one**. With 25
tickets on offer per contest and a per-user limit of 17–20, tickets are close to linearly valuable up to a number far
beyond what we can win, so the case for reliability over quantity is much weaker than I assumed when I thought each
contest could yield at most one seat.

## Revised recommendation (operating agent): KEEP the current layout

I withdraw the disjoint-blocks recommendation for the satellites. On the real rules the current layout is better on the
objective that fits them, and the reviewer's objection (2) — that my P(any) comparison was structurally guaranteed by
nesting top-16 inside top-62 — is also correct and explains why that metric looked so favourable.

The one remaining argument for disjoint blocks is a genuinely decreasing utility of tickets, i.e. if the operator would
value a first $20 Millionaire ticket highly and a fourth one at nearly nothing. That is his judgement, not ours, and it
should be stated as such rather than assumed from his entry counts. **Absent an explicit statement from him that later
tickets are near-worthless, keep the authorized layout.**

## Loose end closed: were the near-neighbour lineups available to the selector?

I claimed the selector "rejects" core-plus-swap lineups, on the evidence that no book lineup is one player from rank 1.
The reviewer objected that absence from the *book* proves rejection only if they existed in the *pool*. Checked on the
live Week-2 pool of 6,400 candidates: **zero** candidates are one player from the best lineup and **five** are two
players away, none selected. So the honest statement is the weaker one: **the generator does not produce near-duplicates
in the first place**, so the selector never has the chance to reject them. My original wording over-claimed and is
corrected here. The performance finding is unaffected: built explicitly, such variants scored far below the book's own
ranks 1–10.
