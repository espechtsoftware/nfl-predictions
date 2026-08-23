# Review: exact-P generator census result

Date: 2026-08-16. **No code was changed. No outcome was queried.**

---

## 1. This is the most decisive result the project has produced in weeks

`native-generation-search-dominant`, with a clean three-way split:

| loss stage | slates |
|---|---:|
| exact P absent from the complete five-seed native union | **54** |
| exact P generated but removed by admission | **0** |
| invalid retained reconstruction | 0 |

Zero admission losses on 54 of 54 slates is about as unambiguous as a diagnosis
gets. Combined with all nine P players present in the native union on every
slate and only 24 of 486 slots thin, it removes eligibility, breadth and
admission as explanations in one pass.

**It also kills two of my own suggestions, and bounds a third.**

- **Pool admission is dead a second time.** It was already refuted by
  `H − P = 3.58`; the census refutes it again from a different direction — the
  players are all there, on every slate.
- **Constant-budget family reallocation is weakened.** I had argued that
  `lev` at 63.07% of primary budget with 8% of selections was the obvious
  reallocation target. But the census finds **no single structurally excluded
  family** — leverage, boom and EPI are eligible on all 54 slates. If no family
  is excluded, moving budget between families does not change the *character* of
  the sampling, only its mix. That suggestion should be downgraded.
- **The CBWU-OI construction reframe is correctly bounded** by consequence 2 of
  the result itself: it may improve the best retained native candidate, but it
  cannot recover exact P, because P is absent from the complete native discovery
  union. My reframe was worth making and its ceiling is now known.

## 2. The number that matters most: 4.76 mean swaps

Across a native union of **500–801 candidates per slate** (mean 579.80), the
nearest roster to exact P is a **median five swaps** away — sharing only four of
nine players. On 28 of 54 slates it is exactly five.

Put that beside the earlier real-winner assembly finding: the pool's closest
candidate to a known Millionaire winner contained **3.46 of nine** winning
players against **3.30 under an exposure-preserving random null.**

Two independent measurements, same conclusion: **the generator's proximity to
high-scoring rosters is approximately what undirected sampling would produce.**
Despite six families, stacking rules, leverage and boom tilts and five seeds, it
is not moving toward the optimum — it is sampling a structured distribution that
happens not to concentrate near it.

That is a stronger and more useful statement than "search-dominant" alone, and
it is the thing to carry into ATLAS and stack-core work.

## 3. One caveat on how far "search-dominant" licenses

Worth stating before the finding hardens, because it affects what the successor
mechanism should optimise.

**Exact P is a hindsight target.** It is defined by realized scores. So "the
generator never created exact P" is partly tautological — no pre-lock criterion
can aim at a roster defined by outcomes it cannot see. A perfect searcher
optimising the *simulated* objective would also miss P, because the simulated
objective and the realized outcome are close to uncorrelated at the candidate
level: the rank-skill census put `corr(sim-rank, regret)` at `+0.030`.

So the census establishes **that the combination was never created**. It does
not establish that a better search **could** have created it using only pre-lock
information.

The actionable question is therefore narrower than "search harder":

> Does a **pre-lock-identifiable** region exist whose lineups contain
> high-actual rosters more densely than the current sampling distribution does?

If yes, a directed search over that region is the mechanism. If no, then more
search on the existing criterion produces better *simulated* candidates and no
better *actual* ones — which is exactly the pattern a dozen closed arms already
exhibit.

This is not an objection to the disposition, which is correct. It is a
constraint on the successor design: **ATLAS should be evaluated on whether it
reaches a better `C`, never on whether it reaches P.**

## 4. A cheap diagnostic that separates search *capacity* from search *direction*

This is the one concrete thing I would add, and it is score-free.

**Scale the candidate budget roughly tenfold — 5,800 instead of 580 per slate —
using the unchanged six families and unchanged criteria, and measure only the
minimum swap distance to exact P.** No scores, no selection, no lineup
comparison.

- **If the distance falls materially** (say median 5 → 3), the constraint is
  **capacity**. The families do cover the relevant region; there simply are not
  enough draws. That makes budget, parallel seeds and search efficiency the
  lever, and it makes ATLAS's job tractable.
- **If the distance stays near 5**, the constraint is **direction**. The
  families' sampling distribution does not cover the region containing P at any
  budget, and no amount of the same sampling helps. That would mean the
  successor mechanism must change *what* is sampled, not *how much*.

These imply very different successor designs, and the census as it stands cannot
distinguish them — it measured one budget. The diagnostic is a single scaled
generation run with a distance computation, produces no score, and cannot
license an arm.

Note it also cross-checks §2: if 4.76 swaps really is the undirected-sampling
distance, a tenfold budget should move it only slightly, since max-overlap grows
roughly logarithmically in sample count.

## 5. Summary

| item | position |
|---|---|
| The disposition | Correct and unusually clean; admission and eligibility are eliminated |
| Pool admission | **Dead**, now from two independent directions |
| Family reallocation | **Downgraded** — no family is structurally excluded |
| CBWU-OI reframe | **Correctly bounded** by the result's own consequence 2 |
| 4.76 swaps | Matches the 3.46-vs-3.30 random-assembly null — the generator is not directed |
| Caveat | P is a hindsight target; evaluate successors on `C`, never on reaching P |
| **Recommended addition** | **Tenfold-budget min-swap diagnostic** to separate search capacity from search direction before ATLAS is specified |
