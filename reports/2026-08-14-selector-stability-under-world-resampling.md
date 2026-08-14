# Selector stability under world resampling

Date: 2026-08-14. A proposal for consideration, in response to the question of
whether running the 80-entry selection more than once and reranking would add
anything.

**No code was changed.** This is a design note and a protocol sketch. It
proposes a diagnostic first and a selector change only conditionally.

---

## 1. Which version of the idea is redundant, and which is not

**Redundant.** Re-running the same greedy selector on the same 30,000 worlds is
deterministic and returns the identical 80. Re-ranking *within* an already-chosen
80 is also empty: all 80 are submitted and the objective is the maximum over
them, so their order carries no information — unless entries are destined for
contests with different field sizes, which is the separate per-contest slicing
question.

**Not redundant.** Resampling the *world set*, re-running the unchanged
selector, and using the resulting instability. That is a different proposal and
it has a specific theoretical grounding.

## 2. Why the selector is expected to be unstable at the margin

Greedy coverage makes roughly eighty sequential argmax decisions over estimates
that are themselves sample statistics. Argmax over noisy estimates is
systematically biased toward items whose value was **overestimated** by
sampling error — the optimizer's curse. The bias is largest where the estimates
are thinnest.

The estimates get thin quickly, because greedy does not rank on total support —
it ranks on **marginal** coverage given everything already selected.

Illustrative arithmetic on the production configuration (to be replaced by
measurement):

| stage | new worlds covered | binomial SE | relative |
|---|---:|---:|---:|
| total support at 194, ~2% of 30,000 | ~600 | ~24 | ±4% |
| marginal gain around pick 20 | ~300 | ~17 | ±6% |
| marginal gain around pick 60 | ~100 | ~10 | **±10%** |

By the back half of the book, the difference in marginal gain between the top
few contenders is plausibly smaller than the sampling error on that difference.
If so, **a substantial fraction of the selected 80 is being chosen by Monte
Carlo noise rather than by the objective.**

That is a claim about the current selector that has never been measured, and it
is cheap to measure.

## 3. Proposed diagnostic — do this first

**Objective.** Quantify how much of the 80-entry book is a deliberate choice
and how much is sampling noise, holding candidates fixed.

1. For each slate, take the persisted candidate × world score artifact. Do not
   re-simulate and do not regenerate candidates.
2. Draw `B` world resamples. Two options, and I would report both:
   **disjoint halves** (cleanest interpretation — two independent selections
   from non-overlapping evidence) and **bootstrap resamples of the world
   columns** (more resamples, correlated).
3. Run the **unchanged** greedy selector on each resample, at the unchanged 194
   line, to the unchanged 80 entries.
4. Report, per slate and pooled:
   - **selection frequency** per candidate across the `B` runs;
   - the count of candidates selected in ≥ 90%, ≥ 50%, and < 50% of runs;
   - **mean pairwise overlap** of the 80 across resample pairs;
   - overlap as a function of **greedy rank position** — the prediction is that
     early picks are stable and late picks are not, and the crossover point is
     the interesting number;
   - the same three statistics restricted to candidates that carry the slate's
     realized maximum, as a mandatory descriptive diagnostic only.

**What each outcome means, stated in advance:**

- Mean pairwise overlap near 80/80 → the selector is stable, the noise concern
  is closed cheaply, and §4 should not be built.
- Overlap materially below 80 → the effective number of *deliberately chosen*
  entries is smaller than 80. That has consequences beyond this proposal: it
  bears on the entries-per-slate question, and it means part of any arm-to-arm
  difference is reshuffling of noise-selected slots rather than mechanism.

This is score-free in construction. It reads realized outcomes only for the
final descriptive item, which should be reported separately and cannot select
anything.

## 4. Proposed selector change — only if §3 shows instability

**Do not use membership voting.** Taking the 80 most frequently selected
candidates breaks complementarity: two candidates can both be frequently
selected while covering the same worlds, and avoiding exactly that is what
greedy exists to do.

The correct construction is **bagged value estimates inside the greedy loop**:

> At each greedy step, compute each remaining candidate's marginal coverage on
> each of the `B` resamples, average (or shrink) those estimates, and select the
> argmax of the averaged value. Then update the covered set and repeat.

This de-noises each decision while preserving complementarity, and it is the
same relationship bagging has to unstable decision trees. The objective it
approximates — expected marginal coverage across world samples — is also
arguably better aligned with the real target than coverage on one particular
sample.

Design constraints to freeze before running:

- `B`, the resampling scheme, and the shrinkage rule are fixed in advance and
  may not be tuned on lineup outcomes;
- the selection line stays at 194 and the entry count stays at 80, so the only
  varying factor is the value estimate;
- determinism must be preserved — a fixed resampling seed, and the same
  deterministic tie-break order the current selector uses;
- the arm is a **selector** change, so it must declare that channel explicitly
  and be judged against the incumbent under the standing tail-first order.

## 5. Honest ceiling

This cannot solve the primary problem, and the protocol should say so before it
runs.

Selection is **saturated at the extreme thresholds** — selected counts equal the
pool oracle at 220, 230 and 240 on the adopted book. No selector change can
move those, because the selector is already taking every extreme candidate the
generator produces.

The available room is the 194–210 band, where a real gap exists: 18 selected
versus 22 in the pool at 200, and 12 versus 13 at 210. So the realistic upside
is part of a roughly four-week gap at 200 and perhaps one week at 210.

**Worth doing; will not address the 240 problem.** The diagnostic in §3 is the
surer payoff and it retains value even if §4 is never built.

## 6. How this differs from the multi-seed factorial already running

These are different questions and should not be conflated:

| | varies | isolates |
|---|---|---|
| multi-seed `C0W0` vs `C0WU` | world sample **across seeds** | world-sample sufficiency, but candidate generation also changes across seeds |
| **this proposal** | world sample **within one seed**, candidates held fixed | **selector stability alone** |

The multi-seed contrast cannot separate "more worlds helped the selector" from
"a different seed generated different candidates." Resampling within a fixed
candidate set isolates the selector cleanly, and it is far cheaper — no new
executions, no re-simulation.

Run alongside, not instead. If both are available, the pair decomposes the
world-sample effect into a generation component and a selection component.

## 7. Cost

Near zero. The candidate × world artifacts are already persisted and already
loaded by the effective-rank diagnostic; the selector already runs. `B`
re-selections per slate on resampled columns of an existing matrix is a local
or single-job computation with no simulation, no candidate generation, and no
new data.

---

## Recommendation

1. Run §3 as a score-free diagnostic against the current incumbent, with the
   interpretation frozen in advance.
2. Build §4 only if §3 shows material instability, and freeze `B`, the
   resampling scheme and the shrinkage rule before any lineup outcome is read.
3. State the §5 ceiling in the protocol so a modest result at 200 is not read as
   a failure and a null at 240 is not read as a surprise.
