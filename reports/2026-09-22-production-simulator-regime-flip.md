# The simulator's ranking flips sign between weeks — and five instruments say so

Third production report of 2026-09-22. It answers the laptop's cash-objective proposal
from `2c8ae45b`, and in doing so identifies why almost nothing in this programme
replicates across the two slates we have.

---

## The direct answer to the cash-objective proposal

Selected K lineups from the same pool by simulated **P(score ≥ cash line)** instead of
expected-max, and scored them against the real field. The test was made deliberately
**optimistic**: it was handed the *true* realized cash line, which no pre-lock method
would know. If it fails with the answer supplied, it fails.

| | cash line (field top 20%) | delivered emax book | **cash objective** | random K | simulator's own claim |
|---|---:|---:|---:|---:|---:|
| **Week 1** | 166.36 | 27.8% | **53.3%** | 19.3% | 0.123 |
| **Week 2** | 137.98 | 6.2% | **0.0%** | 4.9% | **0.569** |

Week 1 it is excellent — 53.3% clear against 19.3% for random, P(random ≥) = 0.0%, and
95.6% versus 48.6% at the field median. Week 2 it is worse than random and worse than
doing nothing: **zero of 97 cleared**, while the simulator assigned that book a 56.9%
chance of clearing. The proposal is not refuted; it is *regime-dependent*, which is
worse, because we cannot tell the regime in advance.

## Why: the simulator's ranking is inverted in Week 2

Binning the whole pool by simulated P(≥ cash line) against the realized rate:

| decile of simulated P | W1 predicted → realized | W2 predicted → realized |
|---|---|---|
| 1 (least confident) | 0.014 → **0.071** | 0.152 → **0.065** |
| 5 | 0.041 → 0.141 | 0.291 → 0.056 |
| 10 (most confident) | 0.102 → **0.481** | 0.472 → **0.013** |
| **Spearman** | **+0.255** | **−0.094** |
| pool level | 0.048 predicted / 0.194 realized | 0.307 predicted / 0.049 realized |

Week 1 is monotonically increasing — under-confident in level by about 4×, but correctly
*ordered*, which is all construction needs. Week 2 is monotonically **inverted**: the
most confident decile hit at 1.3% and the least confident at 6.5%, with the level
over-predicting by about 6×. Both the calibration and the ranking flipped sign.

## Five instruments, one pattern

Everything measured over these two slates shows the same shape, which is why individual
levers keep failing to replicate:

| instrument | Week 1 | Week 2 |
|---|---|---|
| selector vs random, on best | beats random (P=24.5%) | **loses** to random (P=58.5%) |
| exposure caps, on best | −1.06 | +26.58 |
| within-book ordering, corr with realized | **+0.28** | **−0.16** |
| cash objective vs random | +34pp | **−4.9pp** |
| simulator calibration, Spearman | **+0.255** | **−0.094** |

These are not five findings. They are one finding measured five ways: **in Week 1 the
simulator's rankings carried signal; in Week 2 they were anti-informative.** Any lever
that reads simulated rankings inherits that coin flip, and a two-slate sample cannot
tell us which regime is typical — still less which one Week 3 will be.

## What follows for Week 3

**Do not adopt a new simulator-dependent lever this week**, the cash objective included.
On this evidence its expected value is roughly zero and its variance is enormous: it
would have been the best thing we ever ran in Week 1 and the worst in Week 2.

**The incumbent dual expected-max is the most regime-robust option tested.** It was
never catastrophic — 27.8% and 6.2% at the cash line, at or above random in both weeks —
whereas the cash objective swung from 53.3% to 0.0%. That is an argument for leaving the
selector alone, not for liking it.

**Prefer the levers that do not read the simulator at all.** The Doubtful exclusion and
the availability-conditioned quarterback repair in the companion reports are correctness
fixes; they work in either regime because they remove players who will not play rather
than re-rank players who will. That is the whole reason to favour them this week.

**And the real target is the world model.** Retrieval, selection and generation have each
now been measured and are not the binding constraint; a simulator whose ranking sign is
unstable across consecutive weeks is. That is a research programme, not a Week-3 change.

## Scope

Two slates, and the regime flip is precisely the claim that two slates cannot settle —
n=2 means we have one week of each regime and no way to estimate their frequency. What
the two slates *do* establish is that the flip happens at all, which is enough to argue
against betting a week on any simulator-ranked lever.
