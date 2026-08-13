# Monte Carlo review: seed variance, tail-mask noise, and stratification

Date: 2026-08-13. Response to whether Monte Carlo methods would help.
**No code was changed.**

---

## Framing

The system already is a Monte Carlo system: 10,000 worlds per slate, with both
candidate generation (MILP over drawn worlds) and selection (coverage over world
support masks) consuming them. So the question is not whether to adopt Monte
Carlo but **which Monte Carlo work is missing**, given that the objective is an
extreme upper tail and every recent decision has turned on one or two events.

Three items follow, in priority order. The first is a measurement the program
has never taken and I would put it ahead of the remaining research queue.

---

## 1. The seed-variance envelope has never been measured

### The gap

A search of `reports/2026-07-25-system-study.md` and every tracked report finds
**no measurement of repeated-seed variance on the production path.** The only
occurrence is in `reports/emerging-technologies-plan.md`, where five fixed
independent seeds appear as a *proposed gate criterion* for the
importance-sampling estimator that was subsequently closed. It was never run
against the live stack.

Consequence: **every arm comparison in this program is one seed versus one
seed, with no recorded noise floor.**

### Why determinism does not cover this

The ledger correctly celebrates that the pipeline is deterministic — "three
identical confirmation runs to the decimal" — and that property is what makes
exact comparison possible. But determinism is *reproducibility*, not
*stability*. Same seed → same answer says nothing about the dispersion of
outcomes across seeds.

### Why common random numbers only partly protect

Co-running control and treatment on the same image with the same seed is
common-random-numbers variance reduction, and it is genuinely effective — for
arms that leave the draw *consumption pattern* unchanged.

But the ledger itself records the limit: **"RNG stream order changes rebase
everything."** Any arm that changes how draws are consumed — Dirichlet
allocation, the G2 Gumbel factor, a TD/production ledger, member-sampled worlds —
causes the streams to diverge downstream of the change. From that point the
comparison carries full seed noise, not paired noise.

That distinction maps onto the adoption record:

| arm type | CRN protection | examples |
|---|---|---|
| feature-only (same draws, different means) | mostly holds | route share, SCHED, team-QB, SIS bundles |
| mechanism (changes draw consumption) | **lost downstream** | fitted-K allocation, G2 Gumbel, member-sample, TD ledger |

The fitted-usage adoption — a mechanism change, promoted on `2→3` at 240 and
`2→3` at 230, with zero weeks at both thresholds on the evaluation panel — is
precisely the case where the protection does not apply.

### Protocol

**Objective.** Establish the seed-only dispersion of the tail grid for the
current production incumbent, so that mechanism-arm differences can be read
against a noise floor.

1. **Fix everything except the seed.** Same immutable image, same code SHA, same
   feature caches, same registry, same fitted `K`, same per-position served
   scales, same selector line, same entry count, same panel and slate set.
2. **Five replicate runs** at five preregistered seeds, declared before any run.
   Use the evaluation panel (2023–2025, 54 slates) if a full 107-slate replicate
   set is too expensive; state which was used.
3. **Report** for each replicate: the full `240/230/220/210/200/194/187`
   selected grid, mean and median weekly best, and the pool-oracle grid. Then
   across replicates report the min–max range and standard deviation of each
   count, and the paired week-level disagreement (how many of the 54 slates
   change their selected best by more than 5 points across seeds).
4. **Also report portfolio churn**: the mean pairwise overlap of the selected
   80 across seed pairs. If two seeds share only 60 of 80 entries, that is the
   scale of arbitrary variation inside every book that has been compared.
5. **Preregister the interpretation before looking.** If the seed-only range at
   210+ spans two or more weeks, then every mechanism arm decided by a
   one-or-two-week difference at those thresholds — including the fitted-K
   adoption — is inside the noise floor, and the tail-first law needs an
   explicit noise-floor clause. If the range is under one week, the adoption
   record stands as-is and this closes a real doubt cheaply.
6. **Consequence rule.** This measurement may not reverse any recorded
   disposition on its own. Its output is a **noise floor to be reported
   alongside every future exact-80 comparison**, in the same way a standard
   error accompanies an estimate. Retroactive relabelling of closed arms is
   explicitly out of scope.

Cost is five replicate panels — the cheapest thing in this document relative to
what it would settle.

---

## 2. The extreme support masks may be dominated by Monte Carlo noise

A candidate's support count at threshold *t* is a binomial draw over 10,000
worlds. Illustrative arithmetic, to be replaced by measurement:

| true P(≥ t) | expected worlds | SE | relative error |
|---:|---:|---:|---:|
| 0.020 (≈194) | 200 | 14.0 | ±7% |
| 0.005 (≈210) | 50 | 7.1 | ±14% |
| 0.002 (≈220) | 20 | 4.5 | ±22% |
| 0.0002 (≈240) | 2 | 1.4 | ±70% |

The adopted 194 selector sits in the safe regime. But the frozen
`tail-first-v6` extreme book selects **lexicographically on the 220 mask
first**, and coverage selection rewards *distinct covered worlds* — a world
covered because of draw noise counts exactly as much as one covered because of
genuine support.

**Recommended:** before that book is graded prospectively, measure the actual
per-candidate support counts at 210 and 220 on real slates, and report the
implied binomial standard error and the fraction of candidates whose 220 support
is below, say, 30 worlds. If most candidates sit at single-digit or low-double-digit
counts, the lexicographic 220 ordering is substantially arbitrary and should be
either re-based on a lower threshold or supported by more worlds specifically for
that book.

This is also the cleanest explanation available for why the extreme-selector
family has produced so little: it may be sorting on noise.

---

## 3. Stratification is the variance reduction that is actually available

The importance-sampling path (roadmap Priority 5) was correctly closed: CE
weights are not a valid change of measure, and no exact density ratio over the
possession simulator's latent variables was writable.

**Stratified sampling on the shared game factor does not need a density ratio.**
Because the strata are constructed rather than inferred, their probabilities are
known exactly by design, so the reweighted estimator is unbiased without any
likelihood-ratio machinery. Force a preregistered fraction of worlds into the
high-scoring region that produces 240+ lineups, reweight by known stratum mass,
and the number of usable tail worlds rises sharply at the same total cost.

This is a genuinely different proposal from the closed one, and it is the
standard remedy for exactly this problem. It directly addresses §2: more worlds
where the tail lives means less noise in the 210/220 masks without proportionally
more compute.

Two design notes:

- **Stratify on the game factor, not on lineup score.** Stratifying on the
  outcome being estimated reintroduces the circularity the CE critique
  identified. The game factor is an input, drawn before any lineup exists.
- **Verify marginal invariance.** Reweighting must leave every player's marginal
  distribution unchanged; that is a mechanical check of the same kind already
  used on the shaping path, and it should be a gate rather than an assumption.

Antithetic variates on the shared factor are a cheaper partial measure worth
pairing with stratification.

---

## What is not worth doing

- **Quasi-Monte Carlo (Sobol/Halton).** Real gains for smooth, low-dimensional
  integrals. The functionals here are indicator masks over a several-hundred-
  dimensional player space, which is where QMC's advantage disappears.
- **Brute-force more worlds as the primary fix.** A √n improvement: 40,000
  worlds halves the error at four times the cost. Worth doing *selectively* for
  the extreme-tail book if §2 shows a problem, but stratification buys more per
  unit of compute.
- **Replacing the simulator with a different sampler.** The sampler is not the
  problem; G0 showed the *dependence structure* is. More or better draws from a
  near-independent copula produce more precise estimates of the wrong quantity.

---

## The Monte Carlo that does not exist yet

Simulating the opponent field — 160k entries, their duplication, and the
resulting rank and payout distribution — is the same machinery pointed at the
objective rather than at the beliefs. It remains the largest unbuilt piece and
is gated on 2026 standings.

---

## Recommended order

1. **§1 seed-variance envelope.** Five replicates, fixed everything else,
   interpretation preregistered, output is a reported noise floor rather than a
   re-adjudication. Ahead of the remaining research queue.
2. **§2 support-mask noise measurement**, before the extreme-tail book is graded
   prospectively.
3. **§3 stratification**, if §2 confirms the tail masks are thin — with marginal
   invariance as a gate.
