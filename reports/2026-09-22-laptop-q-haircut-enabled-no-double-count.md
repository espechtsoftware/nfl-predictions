# Q_HAIRCUT=0.80 is live and correctly placed: the prop market does not already price Questionable risk

Following `c5ce397e` (haircut enabled at 0.80).

## Live configuration, verified on the job

`project-slate`: env `Q_HAIRCUT='0.80'`, image `sha256:98efdfa6…7c27df9` (the digest verified in
`564c8e71`), updated 20:06 UTC. 0.80 is inside (0, 1], so the fail-closed guard will not trip.

## The question that mattered once it was on

In `run_projections.project()` the haircut is applied **after** the market blend (blend at line
397, haircut at 485). The 0.80 was measured on **model-only** projections. For a Questionable
player with a prop line, 55% of the served value is the betting market; **if books already shade
Questionable players, a post-blend 0.80 discounts that part twice.**

It matters because most build-time Questionable players *are* prop-priced:

| 2026 W1–2 skill players | n | with a prop line |
|---|---:|---:|
| never designated | 1,157 | 61.0% |
| **Questionable at some pre-lock pull** | **124** | **83.1%** |
| still Questionable at the final pull | 15 | 13.3% |
| Doubtful/Out at some pull | 433 | 18.5% |

(The 15 still listed Questionable at the final pull mostly had no props; players who were
Questionable during the week and then cleared mostly did. The haircut acts on status at build
time, so the 124 is the relevant group.)

## The test: do books shade Questionable props?

From `div_shadow`, which records the model value and the market value side by side for
prop-sourced players:

| group | n | model | market | **market / model** |
|---|---:|---:|---:|---:|
| never designated | 342 | 11.53 | 10.07 | **0.874** |
| **Questionable at some pull** | 59 | 11.08 | 9.59 | **0.865** |
| Doubtful/Out at some pull | 11 | 10.87 | 9.14 | 0.841 |

**The market's discount relative to our model is the same for Questionable players as for healthy
ones** (0.865 vs 0.874). Books are not pricing the Questionable designation into these lines any
more than the model is. The blend therefore inherits the same un-priced Questionable risk from
both halves, and **a post-blend 0.80 is correct, not a double count.**

Caveats: n = 59 over two weeks; props are pulled on Saturday, so a player's designation can still
change after his line is posted.

## Logged

While building this, a filter written as `status IS NULL` for healthy players returned nothing:
**`dk_salaries.status` stores the string `"None"`, not NULL.** README data deficiency row added.
Python status checks in the money path are unaffected; SQL written by the next person may not be.
