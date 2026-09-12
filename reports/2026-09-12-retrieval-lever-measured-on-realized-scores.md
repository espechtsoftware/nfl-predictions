# The retrieval gap is real and large. Re-ranking does not touch it.

**Date:** 2026-09-12 · **Data:** PREREG-086 r2 sealed cohort, 72 slates, realized
scores already joined (no new outcome opened) · **Status:** measured

## Result

Two selection laws were frozen before any outcome was opened: `incumbent` and
`corrected_hsim_v0.14`. Both pick a K20/K80 book from the same candidate pool.
On **realized** scores across 72 slates:

```
D800_STANDARD        incumbent   corrected_hsim   delta
  K20                   167.97          167.68    -0.29   95% CI (-4.65, +4.32)   30/72 slates
  K80                   181.52          181.20    -0.32   95% CI (-3.77, +3.11)   29/72 slates
D400_PLUS_MINIMAL_COMPLETION
  K20                   167.92          167.50    -0.43
  K80                   180.13          180.06    -0.06
```

Selector choice is worth **nothing measurable**. The interval straddles zero and
the win rate is a coin flip.

## The part that matters

The two world models were not neutral about this. Each predicted a large
advantage for its own selector, on held-out simulated worlds:

```
selected by incumbent,      evaluated under incumbent        k20 174.44
selected by corrected_hsim, evaluated under incumbent        k20 169.06   -5.4
selected by incumbent,      evaluated under corrected_hsim   k20 184.32
selected by corrected_hsim, evaluated under corrected_hsim   k20 191.86   +7.5
```

Each simulator scores its own selector 5-7 points higher. **That confidence does
not survive contact with realized outcomes, where the difference is 0.3 points
in the other direction.** Each model is measuring its own agreement with itself.

This is the instrument-explanation trap in its purest form: the lever moved, the
ranking was not inverted, but the objective the simulator optimises is not the
functional that realized scoring rewards.

## Meanwhile the gap is not noise

```
K20 retrieval gap (pool oracle - book) = 26.28   95% slate-clustered CI (22.78, 29.89)
```

26 points per slate sit in candidates we **already generate** and fail to
retrieve. The gap is solid; what is absent is any evidence that ranking rules
built on these world models can reach it.

## What this means for the queue

- **This strengthens, not contradicts, the standing ledger position** that
  selection is closed *for the current simulator and static feature set*. It adds
  realized-outcome evidence on a fresh 72-slate cohort, and it isolates the
  reason: the candidates are present, the ranker cannot see which ones matter.
- **The FP/SIS 2x2 ablation is testing a narrower lever than it appears.** It
  asks whether paid sources change *retrieval*. The evidence here says the
  retrieval bottleneck is the world model's ability to identify good candidates,
  not the rule used to order them. Paid sources could still help by improving the
  world model itself -- a different mechanism, and the one worth stating in the
  hypothesis before that chain is unblocked.
- **A better ranker is not the next experiment.** A better *discriminator* --
  something that separates the 26-point candidates from their neighbours before
  ranking -- is.

## Method note

No new outcome was opened. The realized scores for this cohort were already
joined in the 2026-09-12 efficacy read, and both selection laws were fixed before
that read, so this is a two-arm comparison of frozen rules and not a selector
search over opened outcomes. Intervals are paired and clustered on the slate,
since candidates within a slate share a game script.

Rejected approach, recorded so it is not repeated: evaluating new rules against
the discovery matrix would have meant pulling ~62 GB of matrices to the
workstation. That is against the design -- downstream workers derive their one
matrix from the registry in-cloud -- and unnecessary, because the frozen
selector comparison already existed in the sealed shards.

---

# Addendum: entries are the lever, and the tail splits in two

Same cohort, same already-joined realized scores, no new outcome opened.

## More entries is the only lever that moved

```
K20 -> K80 (60 more entries):  +13.55 pts   95% slate-clustered CI (+10.61, +16.68)
                               54/72 slates improved, interval clears zero
```

Against the other levers measured on this cohort:

```
more entries (K20 -> K80)            +13.55   CI (+10.61, +16.68)   POSITIVE
minimal-core completion (PREREG-086)  +0.57   CI ( -1.70,  +2.97)   zero
selector law (incumbent vs corrected) -0.29   CI ( -4.65,  +4.32)   zero
```

Entries are ~24x the completion mechanism and ~46x the selector choice, and are
the only one whose interval excludes zero. K80 closes **52%** of the K20
retrieval gap; 12.73 points remain above it.

## The tail splits into two different problems

Clears out of 72 slates, which is the functional the program actually gates on:

```
  line    K20    K80   pool    K20->K80
   187     13     28     50         +15
   194      8     17     35          +9
   200      7     14     25          +7
   210      3      5     14          +2
   220      1      1      2          +0
   230      0      0      1          +0
```

At the 194 line, going from 20 to 80 entries **more than doubles** clears, 8 to
17. The pool holds 35, so even K80 leaves half the available clears unretrieved.

Above ~220 the picture inverts completely. K20 gets 1, K80 gets 1, and the whole
pool holds 2. Extra entries buy nothing because **the candidates do not exist**.
PREREG-086 saw the same thing from the supply side: neither arm supplied a
230-point candidate in 72 slates.

So the Neo4j "supply AND retrieval" framing resolves into a threshold:

- **below ~210 the binding constraint is retrieval** -- the candidates are in the
  pool and the book does not contain them. More entries is the proven lever.
- **above ~220 the binding constraint is supply** -- no ranking rule and no entry
  count can retrieve a candidate that was never generated.

Testing retrieval levers against the extreme tail is therefore measuring an
empty set, which is consistent with every tail-targeted arm in the ledger
returning zero. A tail-supply mechanism must be shown to *generate* 220+
candidates before any selector or entry-count change can matter there.

## Caveats

- Entry count is a bankroll and contest-structure decision, not a model change.
  This measures the lineup-scoring consequence only; it says nothing about ROI
  under entry fees and payout curves, which is where the decision actually lives.
- These are 72 slates from 2021-2024 on one candidate corpus. The +13.55 is a
  within-cohort measurement, not a prospective claim.
- K80 here is the book the frozen selector produced, not the best possible 80.

---

# Addendum 2: how much signal the ranker actually has

The book does contain real signal. It is just far too thin to close a 26-point
gap. Measured against the correct null -- selecting the same number of
candidates at random from the same pool:

```
              retrieves the realized-best candidate
  K20 (2.5% of pool)   6/72 =  8.3%   random 2.5%   lift 3.33x   p=0.0094
  K80 (10%  of pool)  14/72 = 19.4%   random 10.0%  lift 1.94x   p=0.0113
```

Pool is 799 candidates per slate.

Two things follow, and they pull in opposite directions.

**The ranker is not noise.** Both lifts are significant at p<0.02. "Selection is
closed" should not be read as "the selector has no signal" -- it demonstrably
beats chance at finding the single best candidate.

**But the signal is thin and it dilutes.** A 3.33x lift on a 2.5% base still
misses the best candidate in 92% of slates, and the lift decays to 1.94x by K80.
The discriminative power is concentrated in a very short prefix and washes out
almost immediately.

That reconciles the two results in this report. A selector swap moves nothing
(-0.29) not because ranking is worthless, but because both laws share the same
thin signal: they disagree about ordering while agreeing about which candidates
are plausible at all. Changing the rule reshuffles a shortlist drawn from the
same weak discriminator.

## What would have to be true for a retrieval lever to pay

To close even half the remaining 12.7 points above K80, a discriminator would
need roughly to double the K80 retrieval rate, from 19% to ~40%. Nothing
measured on this cohort moves it by more than a couple of points. That is the
bar any proposed reranker, feature family or paid source should be asked to
clear BEFORE it is built into a chain -- it is cheap to state and cheap to
falsify, unlike a full ablation.

A paid-source ablation is worth running only if the hypothesis is that the
source improves the WORLD MODEL -- the thing producing the 3.33x -- not that it
improves the ranking rule applied on top of it. Those are different mechanisms
and only the first has headroom here.

---

# Addendum 3: every lever measured here lives below the Millionaire winning line

Joining the 68 tracked Millionaire winners (`real_winner_overlap.load_known_winner_rows`)
to the cohort gives 34 overlapping slates (2023-2024; the winner file does not
cover 2021-2022). Verified before use: **scoring is identical** (my `actual`
minus `winner_actual`: mean -0.024, median 0.000, 4/229 off by >1 pt) and the
**slate universe matches** (295/306 winner players resolve; the 11 misses are
initial-ambiguity and one wrong initial in the winner file, not absent players).

```
WOULD OUR BEST ENTRY HAVE WON?   (>= the actual winning score, 34 slates)
  K20    0/34        margin to line, mean -67.3
  K80    0/34                              -50.8
  pool   0/34  (best of 799 candidates)    -38.2

pool-oracle margin: min -82.2  q25 -47.5  median -36.5  q75 -26.8  max -6.2
within 10 pts: 1/34   within 20 pts: 4/34
closest: 2023-w02, line 193.9, pool 187.7  (the lowest winning line in the join)
```

## What the 194 line is, and is not

The ledger is explicit and my data confirms it to the decimal:

```
                              2019   2023   2024   2025     (winner file, n=17 each)
actual winning line, median  251.6  233.2  232.5  239.3
actual winning line, min     221.6  193.9  178.3  193.9
share of Millys won >= 237    76%    41%    29%    53%
share of Millys won >= 194   100%    94%    88%    94%
```

`194` is the **minimum** 2025 winning line (ledger: "Line 194 (min 2025
winning line): median N ~824k"). `237` is the **average** winning line (ledger:
"median N ~10^15. Effectively unreachable"). The program replays against 194
because 237 cannot be reached with this candidate pool, and it tracks a >=237
column that reads 0/17 in every season since 2022. This is not an anchoring
error; it is a known ceiling, and the cohort here re-measures it on realized
scores: **0/34, median 36.5 points short.**

## Consequence for the three levers

```
pool oracle, mean            194.25   <- ceiling of the current generator
K80 book, mean               181.52
K20 book, mean               167.97
Milly winning line, median   ~233-239
```

The entire band in which entries (+13.55), retrieval (26.3-pt gap) and
completion (+0.57) operate sits **below the easiest Milly week in most
seasons**. They change *placement* -- how high a best entry finishes -- and
that is real money under a steep payout curve. They do not change the
probability of winning, which on this evidence is approximately zero for every
lever measured.

Winning is a **supply** problem at ~237+, exactly where the tail-split analysis
above found the pool holds a 230+ candidate in 1 of 72 slates. No selector,
entry count or completion mechanism can retrieve a candidate that was never
generated.

## The one thing that would turn placement into dollars

Whether +13.55 at K80 is worth 60 entry fees depends on the payout curve and
the field's score-to-rank mapping, and **that data does not exist**:
`contest_entries` has never received a row and DK purges standings after ~4
days. The Week-1 Monday/Tuesday standings capture is therefore load-bearing for
the only lever this session found -- it is the first opportunity to price
placement rather than assume it.
