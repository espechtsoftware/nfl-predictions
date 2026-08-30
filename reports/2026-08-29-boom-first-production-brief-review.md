# Boom-first production brief: architecture and scientific review

**Date:** 2026-08-29  
**Reviewed brief:** `../nfl2/handoffs/PRODUCTION-BRIEF-boom-first-2026-08-29.md`  
**Brief SHA-256:** `d439225a53318a923d19e1f83adee14a70fb52427ee252d664ebbd9a7c76f377`  
**Valid verdict SHA-256:** `200fb2dded67680c8906caf6c9708b67007af86a646245ff4352b373471726c3`  
**Disposition:** **accept the hypothesis; run the matched production-shaped
historical test immediately after the bounded launch-hardening patch.**

## Executive judgment

This is one of the strongest generation findings available to the project.
The proposed change is simple and causal: at the same 200 attempted solves per
slate, shift allocation from 160 leverage / 40 per-world optima to 40 leverage
/ 160 per-world optima.  The corrected experiment reports:

| Endpoint | Control | Boom-first | Paired change | Stability |
|---|---:|---:|---:|---|
| K100 mean weekly max | 177.728 | 184.291 | **+6.563** | 95% season-clustered CI [4.905, 8.101]; 66W/23L; every LOSO positive |
| K80 mean weekly max | 177.362 | 182.180 | **+4.819** | CI [3.444, 6.032]; 60W/29L; every LOSO positive |

The K100 210+ count rose from 4 to 10 weeks and the 220+ count from 1 to 5
across 89 development slates.  The signal survived corrected production-style
centering, three independent banks, and leave-one-season-out analysis.  It is
not a fragile single-cell win.

The result is not yet a production default because the lab did not include
this repository's full CBWU union, role/EPI candidate families, DST world
model or fade re-estimation.  Those omissions affect both candidate supply
and retrieval.  They make the lab effect size non-transferable, but they do
not erase the strong direction evidence.

## What the production test must estimate

The estimand is the effect of **candidate solve allocation only**:

- control: leverage 160, boom 40, frozen role 12;
- treatment: leverage 40, boom 160, the same frozen role 12;
- same total leverage-plus-boom requested solves: 200;
- same production source snapshots and simulated player worlds;
- same explicit incumbent construction preset;
- same natural uniqueness semantics, with no synthetic padding;
- same common-world coverage-194 selector and exact K80;
- realized scoring only after all 54 score-free task results and the terminal
  root are immutable.

`PROSPECTIVE_SHADOW_ID`, run names and provenance fields may differ.  No model,
centering, ordering, selector, stack, salary-floor, overlap or role-policy
change belongs inside this pair.  In particular, the concurrent migration to
"only DraftKings legality is universal" must be tested in a separate crossing
after this allocation effect is measured under the incumbent construction
preset.

Natural uniqueness means the two arms can end with different unique pool
sizes even though requested solves are equal.  That is part of the treatment,
not a defect to hide.  The report must show attempts, failures, family counts,
unique counts, collisions and wall time per arm.  A lineup produced by both a
role solve and a boom solve is one roster with both provenance tags; it must
not abort the slate or be duplicated as padding.

## Review of the external evidence

### Strong features

- The treatment was preregistered before the realized read.
- Common random numbers were used within slate, with an independent selection
  bank and deterministic per-slate seeds.
- The primary uncertainty calculation clusters by season.
- All five leave-one-season-out deltas are positive: 5.881 to 7.320 at K100.
- The corrected centering enlarged rather than erased the effect.
- The measured mechanism is consistent with this project's earlier all-boom
  direction, while preserving a leverage sleeve and fixed solve count.
- Boom-first improved the candidate-pool oracle materially; increased regret
  indicates a downstream retrieval opportunity rather than evidence against
  the generator.
- Lab diagnostic 036 gives a plausible mechanism: modeled 194+ rates were
  0.78% versus 0.58% realized for boom rosters, but 0.69% versus 0.25% for
  leverage rosters.  Per-world optima therefore had materially better tail
  calibration than leverage candidates, even though leverage had the higher
  realized mean.  Boom-first may improve the corpus partly by reallocating
  work toward the better-calibrated tail family.

### Limits and cautions

- The 89-slate development panel excludes sealed 2025 and differs from the
  production 54-slate 2023--2025 score surface.
- Equal solve count is not necessarily equal wall time.  Runtime and failure
  rates must be reported.
- The lab's valid compact verdict contains the K100 primary result.  The K80
  result is supported by the accompanying report/handoff, whose packaging is
  concatenated rather than valid single-object JSON.  Production must rely on
  its own immutable result schema rather than copying that packaging.
- No payout, duplication or contest-field utility was directly measured.
- The optional 400-solve `lev40/boom360` result changes compute budget and has
  a much smaller incremental effect.  It is a separate dose arm, not part of
  the first matched pair.
- Boom-first and cap-4 retrieval may partially correct the same simulator
  overconfidence.  Their historical gains cannot be assumed additive, and a
  cap must not be carried to a new population without measuring whether and
  how it changes the selected book.

## Post-review update: PREREG-016 result and mechanism correction

The lab's preregistered law-level analog has now completed on three banks and
89 development slates.  The frozen preregistration SHA-256 is
`c7e480c78a56fb159a535c42e95a6c8e42a69884ad572ae7160f47798b4d26e0`;
the committed result is sibling-repository commit
`b32c30a7b32672ae17c922af8420597b64709005`, and the compact report SHA-256
is `03b3027239ce64554e4048b9600d6b4c9276e4d7540e26c7260eb50b032a97a6`.
It is a structural analog, not an exact production-selector replay: the lab
uses different rungs, weights, tie rules, world count and candidate
population.

The primary result is null.  At K80, coverage-194 scored 182.654 mean weekly
maximum; the cap-4 ladder scored 182.459, a -0.195 change with the 98.75%
family-wise season-clustered interval [-1.197, 0.984].  Its three bank deltas
were -0.820, +0.679 and -0.444.  This is direct evidence against treating
cap-4 as a population-independent selector improvement.

An independent reopen and aggregation of all 54 immutable task objects found
267 unique slate-bank cells.  It also corrects the shorthand claim that the
cap was "inert" because the constrained prefix averaged 79.2 of 80:

- the prefix reached 80 on 264/267 cells and exhausted at 9, 10 or 12 only on
  the three banks of 2022 Week 16;
- nevertheless, cap-4 and the uncapped ladder shared only 64.25/80 selected
  lineups on average (range 48--78) and were identical on 0/267 cells;
- cap-4 therefore changed selection materially even when it did not force an
  unconstrained completion;
- versus the uncapped ladder, mean simulated P(max >=194) fell from 0.35544 to
  0.34551 and P(max >=210) from 0.14557 to 0.13769, while realized mean weekly
  maximum also fell from 182.755 to 182.459;
- the calibration picture is threshold-dependent: cap-4 raised realized
  194+ incidence from 0.25468 to 0.26966 despite the lower modeled
  probability, but did not raise realized 210+ incidence.  The single-rung
  cap-4 coverage arm showed the clearest modeled-falls/realized-rises
  direction (182.935, +0.281 versus control), but its interval [-0.709,
  1.913] spans zero.

The defensible interpretation is therefore narrower than either "diversity
won" or "the cap never bound."  The cap is an active regularizer whose score
effect depends on the candidate population and threshold.  Production's
181.361 result remains the historical leader on its redundant sieved
eight-book union, but cap-4 is not justified as the selector for a pure
boom-first pool.  Foundry must persist constrained-choice divergence,
candidate rejections/feasible-pool trajectory, prefix exhaustion and
completion, book overlap, population redundancy, modeled threshold
probabilities and realized calibration residuals; prefix length alone cannot
identify whether the cap changed the book.

## Production implementation review

The current isolated implementation has the right scientific spine:

- the arm difference is exactly 160/40 versus 40/160;
- score-blind source snapshots are create-once frozen, including the repaired
  2025 Week 1 source;
- control reproduction requires exact ordered rosters and world totals;
- both arms use identical modeled worlds and an explicit incumbent preset;
- selection is common-world CBWU at exact K80 and line 194;
- grading is a separate command that reopens the immutable terminal before
  opening the historical outcome snapshot.

Focused independent validation passed 8/8 science tests and 7/7 operator
tests.  The implementation must not launch until these bounded trust gaps are
closed:

1. Add a manifest-bound provider layer with configure, launch and status.
   Collection must query the provider itself and prove one execution reached
   exact 54/54 success under the expected immutable job UID/configuration.
2. Add a real-artifact, no-publish task-0 preflight and require its receipt
   before the full launch.  A publishing `task` command is not a smoke test.
3. Add a dedicated bounded Docker/Cloud Build recipe that compiles, runs the
   focused tests, runs network-isolated synthetic smokes, and binds the clean
   commit, image digest, build receipt, service account and reused job UID into
   the manifest.
4. Bind every task result to its exact manifest task: ordinal, slate,
   generation snapshot SHA, later-source identity, commit, image, job and the
   one execution ID.
5. Deep-validate native receipts, requested and completed allocations,
   failures, timing, construction receipt, selected-book membership, season,
   week and science summaries before terminal publication.
6. Treat role/boom collisions as disclosed multi-provenance deduplication,
   not a task failure.  Add a collision regression test.
7. Retain and verify the actual `CandidateBatch` construction-preset receipt,
   require snapshot URI equality as well as SHA equality, validate nonnegative
   timing maps, and bind grading to the historical-outcome lease.

These repairs protect a single expensive result from being ambiguous.  They
do not change the scientific arm and should be completed as one narrow patch,
followed by focused validation, one immutable build, one no-publish smoke and
one 54-task launch.

## Decision sequence

1. Complete and independently re-review the bounded hardening patch.
2. Run one real, no-publish task-0 smoke from the immutable image.
3. Launch the exact 54-slate pair once.  Do not relaunch a live or successful
   execution.
4. Seal the score-free terminal at exact 54/54, restore the reused job, then
   grade against the already-frozen historical outcome snapshot.
5. Report the paired control/treatment results at K80: mean and median weekly
   max, 194/200/210/220/230 counts, per-season deltas, W/L, candidate-pool
   oracle, regret, unique yield, failures and runtime.  Also report modeled
   versus realized exceedance calibration by candidate family and selected
   book; this tests whether allocation improves tail calibration rather than
   only candidate volume.
6. If boom-first improves the primary K80 mean without degrading the frozen
   tournament-tail guard, make `lev40-boom160` an explicit generation preset.
   Do not automatically attach cap-4.  Run a frozen population-by-selector
   crossing: uncapped versus cap-4 retrieval on the incumbent redundant union,
   the pure boom-first pool and their disclosed combined union.  Report cap
   engagement and calibration diagnostics alongside score; treat a cell in
   which the cap changes few or no choices as a mechanism failure, not a win.
7. Only then test the 400-solve dose and the legality-only construction preset
   as separate factorial cells.

## Bottom line

The lab finding merits immediate production-shaped confirmation.  The most
important strategic implication is that the corpus may benefit more from
many exact optima across distinct high-scoring worlds than from repeatedly
perturbing one tournament objective.  The newly measured 181.361 cap-4 result
is a separate, population-specific retrieval finding.  The lab replication
shows that cap-4 materially changes a boom-first book but does not improve its
primary realized mean, so production must test population and selector as a
factorial rather than assume a two-stage recipe.  Their separate historical
gains must never be added.
