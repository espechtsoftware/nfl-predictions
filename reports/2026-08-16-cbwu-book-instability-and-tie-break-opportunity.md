# CBWU order-invariance: what the 33.19/80 overlap means

Date: 2026-08-16. Review of the quantified CBWU order-invariant repair result.
**No code was changed. No outcome was queried.**

---

## 1. The recording decision is right

A repair that changes roughly **47 of 80** entries is a **policy change**, not a
repair, regardless of the score-free coverage gate passing on every slate.
Recording that production cannot inherit it without downstream revalidation is
the correct call and matches the standing law: a changed component does not
carry forward the verdicts measured against its predecessor.

## 2. The instability is larger than the resampling diagnostic measured

Two independent perturbations of the same selector, side by side:

| perturbation | overlap of 80 | what varied |
|---|---:|---|
| disjoint-half world resampling | 54.28 | genuinely different simulation evidence |
| **order-invariant comparison repair** | **33.19** | **floating-point comparison order only** |

**A numerical comparison change perturbs the book more than different world
evidence does.**

That is the headline finding here, and it is stronger than either measurement
alone. It says the selector operates on an objective surface flat enough across
many candidates that numerical noise dominates real signal in the majority of
slots.

The coverage gate reinforces it rather than contradicting it: **it passed on
every slate.** Two books differing on 59% of their entries achieve equivalent
world coverage. That is not a defect in either book — it is direct evidence that
**the coverage objective does not discriminate among a large set of
80-subsets.**

This also retroactively explains three separate observations that were
previously filed as unrelated:

- selector resampling instability (54.28/80 disjoint-half overlap);
- selection saturation at 220+ (selected equals pool oracle);
- the repeated failure of selector variants — reranker, LSE, sharp-LSE,
  QB-concentration, dollars-objective — to move anything.

All three are consequences of a flat objective. A flat objective cannot be
improved by a better search over the same criterion; it can only be improved by
adding a criterion.

## 3. Reproducibility, not correctness, is the live question

If the differing entries are float-level ties, neither book is more correct. But
the two differ in a property that matters: **the new book is order-invariant and
the old one was not.**

The old adopted book's composition was therefore conditional on summation order,
which is in turn conditional on frame construction and potentially on CPU
dispatch.

The project's determinism guarantee rests on "three identical confirmation runs
to the decimal." That establishes reproducibility **within** an environment. The
existence of this repair implies it may not hold **across** environments.

**Recommendation:** verify before Week 1 whether the current production book
reproduces byte-identically on the live serving infrastructure, which is not the
same environment as the replay panels. If it does not, that is a more
consequential finding than the repair itself — it would mean the submitted
lineups are environment-dependent.

## 4. The forensic implication is narrower than feared — but confirm the scope

The decomposition layers depend on the selected book differently:

| layer | depends on selection? | status |
|---|---|---|
| **H** — full player universe | no | unaffected |
| **P** — candidate-pool union | no | unaffected *if repair is selection-only* |
| **C** — best generated candidate | no | unaffected *if repair is selection-only* |
| **S** — best selected entry | **yes** | affected; `C − S = 5.007`, the smallest layer |

So the forensic's central conclusion — **construction 78.99 points, selection
5.01** — **survives**, because the two dominant quantities do not depend on
which 80 entries were chosen. That is genuinely reassuring and worth stating
explicitly in the reconciliation, since the natural first reaction to "the book
changed by 47 entries" is to assume the whole forensic is compromised.

**The scope question that must be answered explicitly:** CBWU is a *candidate*
and *world* union. If order-invariance changes which candidates enter the pool,
or how they are cross-scored across seeds, then **C and P move as well** and the
reassurance above does not hold.

- If the repair is **selection-only** — record that, and the forensic stands with
  only the `S` layer restated.
- If it touches **union or cross-scoring** — the pool changed, and `P`, `C` and
  the P-oracle distance measurements need re-running against the repaired
  configuration before the exact-P census lands.

This should be settled before the corrected exact-P census is launched, or that
census will be the third analysis measured against a different configuration
than the ones it is compared to.

## 5. The opportunity this exposes: coverage-neutral tie-breaking

If many 80-subsets tie on coverage, then **the tie-break is doing substantial
work with no principle behind it** — currently floating-point order, and after
the repair, deterministic but still arbitrary.

That is a free lever in a layer otherwise described as saturated. Among
coverage-equivalent books, ties could be broken deliberately toward an objective
the current criterion does not express:

- **Recourse flexibility** — prefer books whose late-game slots are more
  swappable, or whose entries are more decisively alive-or-dead by the first
  swap point. This is the "polarised early risk" property the recourse framing
  predicts, obtainable at zero coverage cost.
- **Roster diversity** — prefer the tied book with lower pairwise overlap,
  directly raising the effective independent-bet count.
- **Duplication avoidance** — prefer entries the field is less likely to
  submit, once contest standings exist to estimate it.

The gate has already demonstrated that such choices are **coverage-neutral** —
that is precisely what "passed on every slate while overlapping only 33.19/80"
means.

**Honest bound:** this cannot help at 220+, where selected already equals the
pool oracle. Its room is the `C − S = 5.007` gap at 194–210, plus whatever the
non-coverage objective is independently worth. It is not a solution to the
79-point construction problem.

But it is the first genuinely new lever in the selection layer since that layer
was declared saturated, and it costs nothing, because it operates only where the
objective is already indifferent.

## 6. Summary

| # | point |
|---|---|
| 1 | Recording CBWU as non-inheritable without revalidation is correct |
| 2 | **33.19/80 versus 54.28/80** — numerical order perturbs the book more than real evidence does; the coverage objective is flat |
| 3 | Verify the production book reproduces **across environments**, not only within one |
| 4 | The forensic's headline survives; **confirm whether the repair is selection-only** before the corrected exact-P census launches |
| 5 | **Coverage-neutral tie-breaking** is a free, previously unavailable lever — bounded, but new |
