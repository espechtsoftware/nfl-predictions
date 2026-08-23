# Correction: CBWU-OI is an admission change, not a comparison repair

Date: 2026-08-16. Correction to
`reports/2026-08-16-cbwu-book-instability-and-tie-break-opportunity.md`, plus a
reframe of what CBWU-OI is actually worth measuring.
**No code was changed. No outcome was queried.**

---

## 1. What I got wrong, and how

When the CBWU order-invariant work was first described, I inferred it was a
comparison-and-tolerance fix — changing *how* results are compared rather than
*what* is computed — and said so hedged: *"the name suggests this is a
comparison-and-tolerance fix."*

In the follow-up document I **dropped the hedge and made it a premise**,
labelling the perturbation "floating-point comparison order only" in a
comparison table and building an entire argument on it.

That is the failure: an inference I had correctly flagged as an inference became
an unverified premise one document later. The actual change replaced
**first-source quota/fill admission** with **complete-union cross-scoring and
score-free admission** — so the candidate pool changed, and the selected book
changed as a consequence.

## 2. What that invalidates

**2.1 The headline comparison is invalid.** I placed these side by side:

| perturbation | overlap of 80 |
|---|---:|
| disjoint-half world resampling | 54.28 |
| CBWU-OI | 33.19 |

and concluded that "numerical comparison order perturbs the book more than
genuinely different simulation evidence does."

Resampling holds the **pool fixed** and varies **world evidence**. CBWU-OI
changes **admission logic**, so pool *and* scoring differ. These are different
perturbations, not two magnitudes of the same one, and the comparison carries no
meaning. **Retract it.**

**2.2 The flat-objective conclusion does not follow.** Two books differing on 47
of 80 entries while both passing a coverage gate is unremarkable when their
pools differ — different pools produce different books, and both can cover
worlds well. The claim that "the coverage objective does not discriminate among
a large set of 80-subsets" was not established by this evidence.

**2.3 The tie-break opportunity loses its evidence base, but is not dead.** It
rested on "many coverage-equivalent books exist," which CBWU-OI does not
demonstrate.

What survives is the **selector resampling** result, which *is* like-for-like:
same pool, same candidates, only the world sample resampled, giving 54.28/80
disjoint-half overlap with roughly 26 of 80 slots differing under independent
evidence, and 1.28pp measured coverage optimism. That supports **near-indifference
among a subset of slots** — a materially weaker claim than "the objective is
flat," and any tie-break proposal must be scoped to it and rest on it alone.

**2.4 My exact-P baseline concern was misplaced.** I raised the risk of the
census landing against a "third configuration." That assumed CBWU-OI would flow
into the chain. Since production was not changed and the census still targets the
canonical CBWU baseline, the forensic, the census and production all reference
the same configuration and are internally consistent. The correct statement is
the conditional one already recorded: **if CBWU-OI were ever promoted, P/C/S and
the census would require revalidation.**

**2.5 What survives unchanged.** The cross-environment byte-reproduction check
before Week 1. The determinism guarantee rests on identical confirmation runs
*within* an environment, and the live serving infrastructure is not the replay
panel environment. That recommendation stands on its own and is unaffected by
this correction.

---

## 3. The reframe: CBWU-OI belongs in the construction layer

This is the part worth acting on.

If CBWU-OI replaces first-source quota/fill admission with complete-union
cross-scoring and score-free admission, then **it is a candidate-admission
mechanism, not a repair.** Admission is generation, and the forensic puts
**78.99 of the ~88 lost points in the construction layer** — combinations never
built from players already in the pool.

That makes the interesting question different from the one currently framed.
"Does the book differ, and would production need revalidation?" is a governance
question with a known answer. The scientific question is:

> **Does the CBWU-OI pool close any of the `P − C` gap?**

### What to measure, using machinery that already exists

The forensic already computes each of these for the canonical pool. Recompute
them for the CBWU-OI pool:

1. **The `C` layer** — best generated candidate per slate, and its threshold
   counts. This is the direct test. Canonical `C` is 8/6/3/1/0 at
   200/210/220/230/240 against a `P` of 52/50/50/47/44.
2. **Distance to the exact-P oracle** — minimum player swaps from any candidate
   in the pool to the P-oracle. Canonical work has this at a mean of 5.15 swaps
   for the recourse comparison; the equivalent for the pool is the construction
   analogue.
3. **Structural reach** — whether CBWU-OI admits candidates in regions the
   canonical pool does not: games spanned, largest team block, stack shape,
   positional spend, salary distribution.
4. **Pool size and budget** — admission changes are budget-relevant. If CBWU-OI
   admits *more* candidates, any `C` improvement is partly a budget effect and
   must be reported as added-budget discovery, per the CE and role-union
   precedent.

### Both outcomes are informative

- **If `C` moves** — this is the only intervention in the construction layer
  anyone has measured, and it arrived incidentally from a repair. That would
  make it the most important open lead in the project, and it would deserve a
  properly frozen fixed-budget protocol rather than promotion off a repair
  branch.
- **If `C` does not move** — that is a substantive finding too. It would say
  admission **breadth** is not the binding constraint, and the construction gap
  is about **composition** rather than **inclusion** — i.e. the generator has
  access to the right candidates and fails to assemble them, rather than failing
  to consider them. That would sharpen the exact-P constraint census
  considerably, by ruling out one of its two candidate explanations before it
  runs.

Either way this is a better use of the CBWU-OI artifact than a
revalidation checklist, and it costs only recomputation over a pool that already
exists.

---

## 4. Summary

| item | status |
|---|---|
| "Numerical order perturbs more than real evidence" | **Retracted** — invalid comparison |
| "The coverage objective is flat" | **Not established** by this evidence |
| Coverage-neutral tie-break lever | **Weakened** — must rest on the 54.28/80 resampling result alone, scoped to near-indifferent slots |
| exact-P third-configuration risk | **Withdrawn** — production unchanged, census targets canonical CBWU, internally consistent |
| Cross-environment byte-reproduction check | **Stands** — unaffected by this correction |
| **New:** measure CBWU-OI's pool against `P − C` | **Recommended** — it is a construction-layer intervention and that is where 79 of 88 points are |
