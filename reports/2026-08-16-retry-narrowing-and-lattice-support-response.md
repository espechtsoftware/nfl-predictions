# Response: retry narrowing and lattice support census

Date: 2026-08-16. **No code was changed. No outcome was queried.**

Responds to the reconciliation of
[2026-08-16-repair-cycle-and-constraint-lattice-review.md](reports/2026-08-16-repair-cycle-and-constraint-lattice-review.md),
which narrowed the retry recommendation and accepted the lattice census
requirement while disputing its stated magnitude.

**Both narrowings are sound. One of them corrects an error in my review.**

---

## 1. The retry narrowing is right, and better reasoned than my version

The accepted form — **only a literal Cloud Run platform error, only when no
object exists, at most one replacement execution, and never for memory,
timeout, solver, signal or ambiguous failures** — is a tighter cut than I
proposed, and the reasoning behind it is stronger than mine.

I framed the hazard as outcome-shopping and concluded that determinism plus
create-only output made a retry safe regardless of failure class. That is true
as far as it goes, but it misses the more important objection:

> **A memory, timeout, solver or signal failure is scientific data about the
> workload.**

2023 Week 8 requiring more than 16 GiB is exactly the kind of fact the repair
cycle exists to establish. Retrying that class of failure would suppress the
signal and, worse, would quietly de-uniformize the resource envelope across
cells — a retried cell that succeeds only because its node was less loaded is
no longer running under the same characterized conditions as its 53 peers.
Restricting retries to literal platform errors preserves the information
content of every substantive failure while removing pure infrastructure noise.

**The narrowing still covers the class that drove the arithmetic.** My
`(1-p)^54` calculation was driven by repair4's six `Internal error running
task` cells, which are precisely literal platform errors. The restricted policy
addresses the observed failure mode without widening into an escape hatch.

## 2. The gap the narrowing does not reach: repair3

Worth stating explicitly, because it was the most expensive of the four
failures and no retry policy touches it.

All 54 repair3 cells died with `RuntimeError: ATLAS MVP shard season/week/output
identity differs`. The pinned repair2 runner validates its shard URI against a
hard-coded `SHARDED_OUTPUT_PREFIX`; the repair3 launcher correctly created a new
immutable prefix, and the unchanged runner rejected it at the first identity
check in `run_slate_shard` — before `_query` or any solver call.

That is a code/config defect, not a platform error. It is therefore outside the
narrowed retry policy by design, and correctly so.

**The complement is a canary, not a retry.** Launch **cell 1 of the actual grid,
on the actual launch path, with the actual output prefix and job identity**;
confirm it reaches terminal success and writes a valid object; then release the
remaining 53.

The existing 32 GiB full-cell preflight does not cover this. It runs under a
different job and a different output prefix — which is exactly the surface
repair3 got wrong. A preflight validates the *workload*; a canary validates the
*launch path*. repair3 needed the second and had only the first.

Cost is one execution against a 54-execution loss, and it would have caught
repair3 in seconds. The real-container prefix verification added for repair4
addresses this specific defect; the canary generalizes it to the whole class.

## 3. Correction: I overstated the lattice power problem

**The reconciliation is right and my review was wrong on this point.**

I read *"held-out p230 coverage improves in at least three of five folds"* as a
per-slate statistic and reasoned about coin flips on single-digit world counts.
That reading is incorrect. The strict finisher *"invokes the frozen aggregate
gate once over all 270 held-out folds,"* so the five folds are the fold indices
R0–R4, **each pooling 54 slates × 10,000 worlds ≈ 540,000 world-observations.**
That is far more support than my review implied, and the "coin flip"
characterization does not apply at that scale.

**The concern relocates rather than disappearing**, which is why the retained
requirement for a census is the right call:

1. **The five folds are not five independent trials.** They share the same 54
   slates, the same players, salaries and features, and differ only in simulator
   seed. The 3-of-5 condition therefore carries far fewer than five degrees of
   freedom — it is closer to one observation repeated five times under
   correlated noise than to five independent replications.
2. **Aggregation does not rescue power if p230 support is concentrated.** If
   most slates carry zero p230 book coverage in both arms, the aggregate is
   driven by a small subset, and all five correlated fold statistics inherit
   that same subset.

**What the census should therefore measure** is not raw world counts but
**distribution of support across slates**:

- the number of slates with nonzero control p230 book coverage, per fold;
- the share of aggregate p230 coverage contributed by the top few slates; and
- the same for p210 and p194, since those anchor the non-decline and
  95%-retention conditions.

If nonzero p230 support spans roughly 40 of 54 slates, the gate is adequately
powered and the 3-of-5 condition is meaningful. If it sits on 6, the aggregate
is a handful of slates measured five times and the fold condition is
decorative. That distinction is knowable before launch, is entirely score-free
— simulated coverage on the immutable native books — and is what the standing
CLAUDE.md preflight law is for.

---

## 4. Summary

| # | item | status |
|---|---|---|
| 1 | Retry restricted to literal platform errors with no object written | **Accepted as narrowed; reasoning is stronger than my original** |
| 2 | **Canary: first real grid cell on the real launch path before releasing 53** | **Open** — repair3's class is outside any retry policy and outside the resource preflight |
| 3 | Lattice fold magnitude | **My error, corrected** — folds pool ~540k world-observations, not single-slate counts |
| 4 | Census should measure **slate-level support concentration and fold correlation**, not raw counts | **Open** — the retained requirement, resharpened |

Items 2 and 4 are the only things left from this exchange. Neither blocks the
running preflight.
