# Monte Carlo review reconciliation

Date: 2026-08-13. Review of
`reports/2026-08-13-monte-carlo-review-and-seed-variance-protocol.md` against
the current code, accepted panel, and experiment ledger.

## Decision

Accept two recommendations now:

1. measure a five-replicate seed-only envelope for the current incumbent; and
2. measure the actual support-mask sparsity before relying on the prospective
   220-first portfolio.

Keep shared-factor stratification and antithetics as a research lead only. Do
not implement them until the ordinary-seed envelope is complete and an exact
latent-stratum definition proves known masses, preservation of the joint law,
and correct weighted portfolio coverage. No production policy or historical
arm disposition changes from this review.

## Corrections to the supplied review

### The production path has more than one seed

`replay_projections` currently defaults to seed 0, while the adopted direct
role-belief candidate branch separately defaults to `ROLE_BELIEF_SEED=7331`.
CE, Gumbel, and ensemble-member streams have their own fixed seeds but are not
active in the accepted incumbent (`N_CE=0`, `N_GUMBEL=0`, one model member).
The simulator itself consumes one sequential NumPy generator; the named
streams in `research/run_context.py` are provenance infrastructure, not yet
wired into that simulator. Therefore a valid incumbent replicate must bind a
fixed **pair** of baseline/role seeds. Calling one integer “the seed” would be
incomplete.

Feature-only arms usually retain the same initial simulator ranks, but “same
draws” is not universal: changes in component distributions or allocation can
change draw consumption and downstream worlds. Common-random-number protection
must be demonstrated per comparison, not inferred from the arm label.

### The fitted-K history was misstated

The PIT-clean fitted-K comparison did not have zero treatment weeks at 230 and
240 on its 54-slate evaluation panel. In high-to-low order, control was
`0/0/1/1/6/11/13` and fitted K was `1/1/1/2/3/4/10` at
`240/230/220/210/200/194/187`. The same 2023 Week 3 treatment roster scored
240.44 and supplied both new 230 and 240 clears. Across the then-current full
107-slate chain, the corresponding counts moved
`2/2/3/5/14/26/37 -> 3/3/3/6/11/19/34`.

After active-only TabPFN labels were accepted, the required terminal
revalidation compared multinomial with finite K on the new stack. It moved
`2/2/2/4/10/19/35 -> 2/2/2/6/14/23/35`, again in high-to-low order, and
retained `K=28.154043586960896`. These are different comparisons and must not
be merged into one count narrative.

The seed envelope may size how Monte Carlo-sensitive this incumbent is. Under
the frozen protocol it cannot retroactively reverse either recorded result.

### The 194 support masks are not in a generically “safe” regime

The review's support table was illustrative. Measurement on the accepted
panel finds selected candidates average 15.34 supporting worlds at 194, not
approximately 200. Individual masks are thin even at 194. The relevant
relative fact is that selected 220 support averages only 0.78 worlds—about
twenty times thinner than 194—and 42.25% of selected candidates have none.
Portfolio union coverage can still extract useful information from many thin
194 masks, and that selector has historical evidence; individual-mask
sparsity alone does not invalidate it.

### Stratification is not yet a drop-in repair

The possession simulator contains several coupled team factors, discrete
usage allocations, Poisson/binomial events, yardage, and touchdown allocation.
There is no single documented “shared game factor” with frozen stratum masses
whose conditional samples can simply replace ordinary worlds. Any
stratification experiment must first define the exact latent variables and
weights, then reproduce ordinary marginal and joint events before it can rank
lineups. Marginal invariance alone is necessary but not sufficient.

The review also rejects quasi-Monte Carlo and brute-force worlds too
categorically. QMC is low priority for this high-dimensional indicator
functional, but that is an empirical expectation rather than a theorem.
Increasing worlds remains an expensive but valid fallback: 40,000 ordinary
worlds should roughly halve Monte Carlo standard error at four times the
simulation cost.

## Resulting order

1. Complete the frozen incumbent seed envelope using the exact active-only,
   finite-K, position-scaled, direct-role stack.
2. Preserve the completed support audit as the mask-noise baseline.
3. Before live grading of the 220-first shadow, compare its 30,000-world mask
   stability across seeds or against a higher-world ordinary reference.
4. Only then decide whether ordinary additional worlds are sufficient or a
   rigorously weighted stratified estimator deserves a score-free test.
5. Integrate the measured envelope into the final forensic analysis; replace
   the old claim that a deterministic pipeline has no sampling variance.

