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
