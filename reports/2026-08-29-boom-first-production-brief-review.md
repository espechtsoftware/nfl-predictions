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
  overconfidence.  Their historical gains must be crossed and measured; they
  cannot be assumed additive.

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
   tournament-tail guard, make `lev40-boom160` an explicit generation preset
   and cross it with the new cap-4-prefix-then-fill retrieval winner.
7. Only then test the 400-solve dose and the legality-only construction preset
   as separate factorial cells.

## Bottom line

The lab finding merits immediate production-shaped confirmation.  The most
important strategic implication is that the corpus may benefit more from
many exact optima across distinct high-scoring worlds than from repeatedly
perturbing one tournament objective.  Combined with the newly measured
181.361 complete-union retrieval result, it gives the project a concrete
two-stage path: improve rare-tail supply with boom-first, then retrieve it
with the explicit cap-4-prefix-then-fill book.  The crossed result remains a
hypothesis until both stages are measured together; their separate gains must
not simply be added.
