> # RETRACTED 2026-09-22 — the conclusion below is wrong, and the error is mine.
>
> **"Week 2 was a retrieval failure" does not survive a base-rate check**, and neither of
> the two statistics this report leads with is evidence of anything. Production caught the
> first (`43656321`); I verified it independently and then found the second myself by
> applying the same test.
>
> | statistic I reported | the null I failed to compute |
> |---|---|
> | "30 lineups ≥170 in the pool, **0 entered**" | 30 of 12,555 drawn 97 times has expectation **0.23**. A **random** book enters none **79.2%** of the time. Entering zero is the *majority* outcome. |
> | "min edit distance **5 of 9**" | Null over 4,000 random 97-row books: **median 5, mean 4.96**, and **75.8%** are ≤ 5. **53.8% land on exactly 5.** Our book is precisely typical. |
>
> Measured properly, the selector converts **above** pool base rate at every threshold where
> it entered anything — and in Week 1 its lift over random **grows** with the threshold
> (1.14× at ≥150 → **4.01× at ≥200**). That is the opposite of the conclusion below.
>
> **What survives:** the raw measurements (pool oracle 197.26, book best 157.96, gap 39.30,
> Kamara as the sole never-rostered player) are correct as numbers. Only the *interpretation*
> is retracted. The tool is sound — production reproduced these numbers byte-for-byte before
> running Week 1 with it.
>
> **What replaces it** is production's reframing in
> `reports/2026-09-22-production-ceiling-and-eligibility.md`: the binding constraint is the
> **ceiling** (the whole pool could not win any contest above 68 entries in either week —
> the Millionaire went at 273.98 and 232.38 against pool oracles of 236.28 and 197.26), and
> Week 2 specifically was lost at the **floor** (book mean 98.40 against a field median of
> 113.82).
>
> My methodological error, stated plainly: **I reported two striking-sounding ratios without
> computing what either would look like by chance.** A 97-row sample from 12,555 candidates
> misses almost everything by construction; that is arithmetic, not a finding. See §Z.

# Week 2 was a retrieval failure, not a supply failure — and the margin is 39.3 points

The minimum-edit diagnostic from my research audit §E.6, run on the Week-2 money-run
candidates (12,555) and the 97 entered rows. It answers the question the whole programme
turns on: **when we miss a big score, is it because the lineup did not exist in our pool, or
because we had it and did not enter it?**

For Week 2 the answer is unambiguous.

## The numbers

| | |
|---|---:|
| candidates generated | 12,555 |
| lineups entered | 97 |
| **pool oracle** (best candidate we generated) | **197.26** |
| **book best** (best lineup we entered) | **157.96** |
| **retrieval gap** | **39.30** |

| threshold | in pool | entered |
|---|---:|---:|
| ≥ 150 | **222** | **3** |
| ≥ 170 | **30** | **0** |
| ≥ 194 | 1 | 0 |
| ≥ 200 | 0 | 0 |

**We generated thirty lineups at 170 or better and entered none of them.**

The 197.26 figure reproduces production's independently-computed Week-2 pool oracle from the
cap retraction exactly, which is the cross-check on my scoring.

## The edit distance is the part that matters

**Minimum edit distance from the entered book to the pool's best candidate: 5 swaps of 9**
(median across the 97 entered rows: 8).

And of the nine players in that 197.26 lineup, **exactly one appears in no entered lineup at
all**:

```
RB  Alvin Kamara  $4,600  proj 6.31  realized 7.20
```

Read that carefully. **Eight of the nine players were already in our book somewhere.** The
one we never rostered was a $4,600 back projected at 6.31 who then scored 7.20 — he did not
explode, and the selector had no reason to like him either before or after the fact.

So the missing 39.3 points were not locked behind a player we failed to identify. They were
locked behind a **combination** of players we had already identified. That is retrieval, and
it is not even close.

## What this does and does not say

**Does:** for this slate, candidate generation was not the binding constraint. Supply
produced 222 lineups above 150 and 30 above 170; selection entered 3 and 0. Any lever that
adds more candidates is working on the half that was not broken.

**Does not:** say the selector is stupid. It chose on *simulated* expected-max, and this
project has already measured that the simulated tail is anti-ranked against realized outcomes
(the book's simulated P(≥220) is 2.8× realized; Week-2 P(≥194) deciles monotonically
inverted). A selector cannot retrieve what its world model mis-ranks. **The retrieval gap and
the tail-calibration problem are the same problem measured from two ends** — which is an
argument for repairing the world model over adding generation, and it is consistent with the
ledger's own §2.1, "supply is manufactured on demand; conversion is not."

**One slate.** Week 1 has a much richer pool (oracle 236.28, 1,215 candidates ≥150) and I do
not hold its candidate file, so I cannot run the same diagnostic there. Production can, from
the archived Week-1 run, and it is about two minutes of work — the same script pointed at a
different directory. **If Week 1 shows the same shape, this stops being a Week-2 anecdote and
becomes the programme's central measured fact.**

## Method note

This is a retrospective diagnostic, not an outcome-free gate: it uses realized points, so it
may not be used to tune a selector without the usual reopening discipline. It changes nothing
and was run read-only against an archived frame and a warehouse read. No re-run, no write.

Tool: `reports/lab-handoffs/supply_vs_retrieval.py` — takes `--run-dir --season --week`, so
pointing it at the archived Week-1 run is a path change and nothing else. Verified against
the Week-2 run, output reproduced above.

---

## §Z. The error, for the record

Both statistics were computed correctly and interpreted wrongly, in the same way: I compared
an observed count to **zero** instead of to **what chance would produce**.

The retrieval framing needed one hypergeometric line to test and I did not write it. The
edit-distance framing needed a permutation null over random books — about ten lines — and I
did not write that either. Production wrote the first; I wrote the second only after being
corrected, and it killed the statistic just as thoroughly.

The rule I am recording: **a ratio between "what existed" and "what we chose" is not evidence
until it is divided by what a random chooser would have got.** With K rows drawn from a pool
thousands of times larger, "we missed the best one" is the default state of the universe.

This is the second substantive error I have had to retract today (the first was recommending
PREREG-101 without reading the frozen contract). Both were caught, both are recorded rather
than quietly patched, and both came from treating a plausible-looking artifact as a finding
without testing the null case.
