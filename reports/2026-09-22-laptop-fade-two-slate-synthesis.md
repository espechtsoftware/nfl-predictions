# The chalk fade across both slates: it does not replicate, on either metric

Week 1 is production's (`57c6871b`), Week 2 is mine (`eafd0d9c`). Matched dose LEV=640,
matched design, deliberately matched so slate and dose are not confounded the way they were
in the cap retraction. Both arms of each pair share one frame, solver and stack.

## The pair

| | Week 1 mean | Week 1 best | Week 2 mean | Week 2 best |
|---|---:|---:|---:|---:|
| control | 158.65 | 218.50 | 74.42 | **137.70** |
| fade | 156.31 | **225.22** | **76.67** | 135.86 |
| **delta** | **−2.33** | **+6.72** | **+2.25** | **−1.84** |

**The two slates disagree on both metrics, with the signs exactly crossed.** Week 1 trades
body for tail — worse mean, better best, which is what a leverage lever is supposed to do.
Week 2 does the opposite — better mean, worse best, which is what a leverage lever is *not*
supposed to do.

**This is the same shape as the exposure cap**, twelve hours later: uniformly good on one
slate, reversed on the next, with the direction flipping rather than merely shrinking. The
standard the cap failed this morning is the standard the fade fails this afternoon.

## What both slates DO agree on, and it is worth keeping

The perturbation is tiny and the reordering is near-total.

| | fade mean | fade max | rosters shared |
|---|---:|---:|---:|
| Week 1 | 0.320 | 6.360 | 101 / 640 (**16%**) |
| Week 2 | 0.291 | 4.195 | 95 / 640 (**14.8%**) |

A sub-half-point average nudge rewrites **84–85% of the pool on both slates**. That is a
stable, replicated fact about the lever's *mechanism*: **the fade is a construction lever,
not a valuation one.** It decides which lineups exist, and it does so almost totally.

That matters beyond this experiment. A lever this sensitive will produce a large,
noisy-looking delta on any single slate in whichever direction that slate happens to favour,
which is precisely the signature of something that will keep failing replication while
looking impressive each time.

## Two reasons not to read the Week-1 tail result as encouraging

1. **Production already flagged it and I agree:** the single best rose +6.72 while the count
   of candidates ≥194 *fell*, 25 → 22. "Better maximum" and "better tail" are different
   claims and only the first is supported.
2. **Neither of us measured the thing that pays.** Both arms measure the **LEV candidate
   pool**, not the entered book. The money path selects K from lev+boom by dual expected-max
   on *simulated* worlds — and this project has already established the simulated tail is
   anti-ranked against realized outcomes (the book's simulated P(≥220) is 2.8× realized).
   **A better best candidate is not a better book** unless the selector finds it, and the
   evidence says the selector is worst exactly where this candidate lives.

## My Week-2 arm has a specific confound worth stating again

The Week-2 frame predates the Doubtful exclusion, so its pool contains players who could not
play — the control's top lineup by objective holds Zay Flowers at $6,700 for 0.0. The fade
was asked to improve a pool whose dominant defect was availability, not chalk. Week 1's
frame (`e7255e9`) has the same property. **Neither slate tests the fade on the universe the
money path will actually use from now on.**

## Recommendation

**Do not ship the fade on this evidence.** Two slates, opposite signs on both metrics, and
neither measures the selected book. That is weaker than the cap's evidence was, and the cap
was retracted.

**Do not close it either.** The mechanism finding is real and replicated — near-total
construction change from a sub-point perturbation — and it has never been tested in the only
configuration that matters: **post-Doubtful-fix universe, selection over lev+boom, scored on
the selected book's realized best.** That is one well-specified experiment, not a programme,
and it is the version worth preregistering if anyone wants an answer rather than another
pair of crossed signs.

**Cost, measured not projected:** ~15.5 min per arm at LEV=640 on this machine, so a
four-arm version is about an hour here. The selection stage is the part that needs design,
not the compute.
