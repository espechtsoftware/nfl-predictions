# Where the 21.8-point gap to the field actually lives: the QB slot is the worst, WR is the biggest

The field-relative target (`f1d265fb`) needs to know *which slots* are short. `contest_entries`
turns out to carry **100% lineup capture** — 994,328 Week-1 and 311,664 Week-2 field rosters
with full slot detail — so this is measurable rather than inferable.

Validated first: scoring a field lineup from its parsed roster reproduces its recorded
`points` **exactly** (5,000 entries, zero unmatched slots, gap +0.00).

## The decomposition

Random 25% sample of the Week-2 Millionaire field — **42,831 entries, mean 115.51 against the
full-field 115.55**, so the sample is sound.

| slot | field pts/slot | our pool pts/slot | **deficit** | our slots per lineup |
|---|---:|---:|---:|---:|
| **QB** | **16.92** | **11.07** | **+5.85** | 1.00 |
| TE | 11.62 | 7.35 | **+4.27** | 1.14 |
| WR | 14.08 | 11.21 | +2.87 | 3.61 |
| RB | 12.59 | 11.31 | +1.28 | 2.25 |
| **DST** | 7.00 | 8.29 | **−1.29** | 1.00 |
| FLEX | 12.55 | (folded into base positions) | | |

**field total 115.51 − our pool total 93.67 = 21.84**

## What it says

**The QB slot is the worst single slot we field, by a wide margin** — 5.85 points below the
field on one roster spot. That is the dead-QB finding measured against the only benchmark
that matters, and it is more than a quarter of the whole gap from one slot in nine.

**WR is the largest aggregate deficit** — 2.87 × 3.61 slots ≈ **8.6 points**, the biggest
single contribution. A smaller per-slot miss repeated four times over (with FLEX) outweighs
the QB hole.

**Weighted contributions to the 21.84:** WR ≈ 8.6, QB ≈ 5.9, TE ≈ 4.9, RB ≈ 2.9, FLEX ≈ 1.3,
DST ≈ −1.3. They sum to ≈ 22.3 against the observed 21.84, so the attribution is essentially
complete — there is no large unexplained residual.

**DST is the only slot where we beat the field**, by 1.29. Worth noting against production's
finding that DST projections carry no rank skill (+0.167): we are ahead there *despite*
having no ordering signal, which suggests the DST advantage is a pricing or
construction artifact rather than skill, and is unlikely to survive being leaned on.

## Why this is the right instrument for the new target

The field-relative target asks us to move the pool mean from the 21.6th percentile upward.
**This table says exactly where the points are**, and it is recomputable every week the
moment standings land — no simulation, no modelling assumption, and validated against
recorded `points` to the cent.

It also ranks the work honestly. The QB gate production just shipped attacks the **worst
per-slot** deficit and is worth ≈ +2.8 pool points (`f755646d`). **The largest pool of
recoverable points is at WR**, which nothing currently targets.

## Method note, because I got it wrong first

My first pass used `LIMIT 40000` with no randomisation. BigQuery returns an arbitrary,
storage-ordered slice, and that slice averaged **77.55** against the true field mean of
115.55 — a 38-point bias that would have inverted several of the deltas above. **`LIMIT`
without `RAND()` is not a sample.** Caught by reconstructing the sample's own recorded
points and finding the total did not match the known field mean.
