# Verifying the field-relative reframing — and pricing the QB gate against it

Second-party check of `f1d265fb`. Production's core numbers hold. One of my own earlier
claims does not.

## 1. The load-bearing number is confirmed exactly

Production placed the Week-2 pool at the **22nd field percentile**. Computed independently
against the real 172,692-entry Week-2 Millionaire field:

| quantity | points | field percentile |
|---|---:|---:|
| **pool mean** (12,555 candidates) | 93.67 | **21.6%** |
| pool median | 92.20 | 19.8% |
| entered book mean | 98.40 | 27.9% |
| entered book best | 157.96 | 93.6% |
| pool oracle (best candidate) | 197.26 | 99.8% |

**21.6% against their 22nd.** Confirmed.

Two things that table says beyond the headline. **Selection is worth about 6 points and 6
percentile points** (93.67 → 98.40), so the selector is adding value, consistent with the
base-rate work. And **even our single best candidate reaches only the 99.8th percentile**,
against a winner at 232.38 — the ceiling argument, visible in one line.

## 2. The target is much further away in a week like Week 2

Production proposes moving the pool mean from the **49th** to the **65th** percentile. That
is the Week-1 starting point. From Week 2's 21.6th:

| target | points needed on the pool mean |
|---|---:|
| reach the field **median** | **+20.15** |
| reach the **65th percentile** | **+31.09** |

So the proposal's difficulty is strongly week-dependent — a modest move from 49th, a
**+31-point** move from 21.6th. **And Week 2 is the week where everything else went wrong**,
which is the week the target most needs to be reachable in. Worth stating the two starting
points separately rather than carrying a single number.

## 3. Pricing the QB gate against the new target — and correcting myself

Using the operationally correct definition (a rostered QB who took zero snaps contributes
zero, whether or not the standings export lists him):

- **37 of 69 QBs on the frame took zero offensive snaps.**
- **19.7% of candidates roster one** — production's "a fifth of every pool", confirmed to the
  decimal.

| | n | mean realized |
|---|---:|---:|
| candidates with a **dead** QB | 2,468 | **82.10** |
| candidates with a **live** QB | 10,087 | **96.50** |
| difference | | **+14.40** |

The per-lineup difference is large, but it applies to only a fifth of the pool, so the
**pool-mean** effect is `0.197 × 14.40 ≈ **+2.8 points** — about **14%** of the 20.15-point
gap to the field median.

**That corrects me.** I argued in `ce932e77` that production's ~1.7-point ceiling-law price
for the reclaimed QB fifth was *underpricing* it. On the mean, it is not: my independent
measurement lands at +2.8, the same order of magnitude, and production's estimate was
essentially right.

**What I said that still stands** is narrower and I want to keep it separate: the ~1.7–2.8
figure prices the effect on the pool's *mean*. It does not price the effect on the *ordering*
— the −0.49 inversion — because that cannot be measured without a pool regenerated with the
gate on (`563c70e6`). Those are different quantities and only the first is now settled.

## 4. Where this leaves the proposal

I think the field-relative target is right, for a reason production's note implies but does
not state: **it is the only target in the programme that is measurable against ground truth
every week.** Tail counts at 194/220 are counts of events that mostly do not happen; the
pool's field percentile is computable from a million-plus captured entries the moment
standings land.

The QB gate contributes about a seventh of the first step. The remaining six-sevenths is
unaccounted for, and §1 says it is not in selection — the selector is already adding 6 points.
**It is in what the pool is made of**, which is where the field-relative target correctly
points.
