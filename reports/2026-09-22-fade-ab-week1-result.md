# Week-1 chalk-fade A/B: thinner body, longer extreme tail, and a construction change that is almost total

First of the two slates. **Not a verdict** — the cap looked uniformly good on one slate this
morning and reversed on the second.

## Result

LEV=640 both arms. Identical frame, `PRODUCTION_STACK`, `PRODUCTION_ENV`, solver and dose.
The only difference is whether `proj_tourney` carries `− 25.0 × naive_ownership`.

| | control (as shipped) | fade (restored) | delta |
|---|---:|---:|---:|
| mean | 158.65 | 156.31 | **−2.33** |
| **best** | 218.50 | **225.22** | **+6.72** |
| ≥150 | 409 | 385 | −24 |
| ≥170 | 183 | 150 | −33 |
| ≥194 | 25 | 22 | −3 |
| runtime | 44.5 min | 44.8 min | — |

**Rosters shared between arms: 101 of 640 (16%).**

## What it looks like it is doing

**Trading body for extreme tail** — which is what a leverage lever is supposed to do. The
fade makes the average candidate worse and the density between 150 and 194 thinner, while
producing a better single best candidate.

The perturbation is tiny and the effect is not: `own_est` spans 0.0002–0.2544 as
within-position weights, so the fade is **mean 0.32 points, max 6.36**. A sub-half-point
average nudge rewrote **84% of the pool**. That settles one thing regardless of whether it
helps: the fade is a **construction** lever, not a valuation one.

## Three reasons this is not yet a case for shipping it

1. **One slate.** Same bar the cap failed. Week 2 is running on the laptop.
2. **The tail signal is mixed, not clean.** The single best rose +6.72, but the count of
   candidates ≥194 **fell** (25 → 22). "Better maximum" and "better tail" are not the same
   claim, and only the first is supported here.
3. **This measures the LEV candidate pool, not the entered book — and that gap matters
   more than it sounds.** The money path selects K from lev+boom by dual expected-max on
   *simulated* worlds. A 225.22 candidate only helps if the selector picks it, and this
   project has already established that the simulated tail is **anti-ranked** against
   realized outcomes (Week-2 P(≥194) deciles monotonically inverted; the book's simulated
   P(≥220) is 2.8× realized). So a pool whose best candidate is better is **not** the same
   as a book whose best lineup is better. I did not measure the thing that pays.

## What would actually settle it

Re-running selection over lev+boom for both arms and comparing the **selected book's**
realized best. That needs the boom arm and the world banks for each pool, which means a
fuller regeneration than either of us has run. It is the right next experiment and it is
not a four-day job.

## Incidental, and relevant to a live operator question

Both arms took ~44.5 minutes at LEV=640 on the workstation (i9-9900K). The laptop projected
**~9 minutes** for the same dose on a *larger* frame. If their measured time confirms it,
the laptop is ~5× faster on the workload that dominates Saturday's build, and the operator's
"can the laptop do it alone" question resolves to "the laptop should do it".

Reproduce: `reports/fade-ab/fade_ab.py`, `fade_ab_w1.json`, `fade_ab_w1.log`.
