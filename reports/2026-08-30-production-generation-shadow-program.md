# 2026 production generation-and-retrieval shadow program

**Date:** 2026-08-30
**Status:** implementation complete and locally validated; immutable image/job
installation and the Week 1 prelock freeze remain pending; no shadow has been
launched
**Design inputs:** the amended lab recommendations and the independent
production review in
`../nfl2/handoffs/PRODUCTION-TEST-RECOMMENDATIONS-2026-08-30-REVIEW.md`

## Executive decision

The production program will not encode the conclusion “boom-first wins.” The
current evidence supports the narrower and more useful conclusion that
boom-first improves candidate supply. Production's exact 54-slate replay
raised the candidate-pool ceiling by 3.377 DraftKings points but raised the
selected K80 weekly maximum by only 1.256 points, with an uncertainty interval
that includes zero, while selector regret worsened by 2.121 points.

The 2026 test therefore separates two stages:

1. **generation:** which lineups enter the candidate corpus; and
2. **retrieval:** how effectively a fixed, score-blind selector converts that
   frozen corpus into the K80 book.

Every prospective book is frozen before slate lock. Realized outcomes and
contest fields enter only through a separately produced post-settlement
snapshot. No positive point estimate automatically changes the money policy.

## Frozen primary design

All counts below are per R0--R4 10,000-world block. Five blocks are run per
slate. The role-12 sleeve and every other incumbent auxiliary family remain
unchanged in every block.

| Arm | Leverage | Base-law boom | Discovery-law boom | Core solves/block | Status |
|---|---:|---:|---:|---:|---|
| incumbent-160-40 | 160 | 40 | 0 | 200 | exact sentinel |
| boom-first-40-160 | 40 | 160 | 0 | 200 | primary treatment |
| cross-law-40-100-60 | 40 | 100 | 60 | 200 | exploratory nomination |
| boom-dose-40-360 | 40 | 360 | 0 | 400 | unequal-resource, lower hierarchy |
| ceiling-all-boom-0-200 | 0 | 0 | 200 | 200 | optional historical near-miss |

The equal-budget arms therefore request 1,000 core solves per slate, not 200.
The dose arm requests 2,000 and is never reported as an equal-compute effect.
The all-boom arm is disclosed as historically unpassed and is frozen before
Week 1; it cannot be added after early results are visible.

### Generation by retrieval crossing

The exact incumbent and boom-first candidate pools are each selected twice:

| Frozen candidate population | Incumbent coverage-194 K80 | Production cap-4-prefix-then-fill K80 |
|---|---|---|
| incumbent-160-40 | primary sentinel | retrieval interaction cell |
| boom-first-40-160 | primary treatment | retrieval interaction cell |

The crossing requests zero additional candidate solves and uses the same
frozen pool and common 50,000-world base selection bank within each row. The
cap-4 implementation uses strict `>200`, `>210`, and `>220` weights of
`1/4/12`, production tie breaks, a hard maximum four-player overlap prefix,
and unconstrained production-ladder completion only after the hard prefix has
no feasible candidate.

Cap engagement is measured directly at every greedy rank: excluded candidate
counts, ranks where the unconstrained choice became infeasible, changed
choices, book overlap, and membership/order changes. Prefix exhaustion is
explicitly not used as a proxy for engagement.

## Cross-law discovery safeguards

Cross-law copies the lab's mathematical transform into production; it does
not import or call the lab package. It applies the widened game/team coupling
only to the 60 discovery generation visits in each block. The player-level
marginal value multisets are restored bit-for-bit by rank transport, and DST
rows are untouched.

Before the arm is considered a valid freeze, its outcome-free trace must bind:

- bitwise player marginals;
- team/game co-boom and cross-team dependence under both laws;
- world-rank displacement and correlation;
- exact and eight-of-nine near duplicates, novelty, yield, failures, and
  solve duration;
- DraftKings legality, salary, stack, lock, and construction-preset receipts;
- deterministic seed derivation; and
- immutable base, discovery, and independent-audit world identities.

Discovery worlds are used only to propose candidates. Every candidate and
selected book is scored under the untouched base bank. A separate 10,000-world
audit bank is used for diagnostics only and requests no candidate solves.
Every calibration probability for incumbent and cap-4 K20/K40/K80 books is
recomputed from this audit bank; selection-bank tails are never presented as
independent calibration.

## Exposure and immutable pre-lock evidence

Every solve request, including a duplicate, infeasible solve, error, exhausted
attempt, or retry, receives a ledger row. The row retains family, block,
requested ordinal, visit/world identity, retry lineage, terminal status,
canonical nine-player roster when one exists, and measured duration. The suite
receipts natural uniqueness, collisions, failures, family yield, and wall time
per family and block.

For each slate the runner creates immutable, create-only artifacts for all five
arm bundles, the five cross-law discovery banks, the independent audit bank,
one manifest, and one terminal root. Google Cloud Storage's object generation
and server-side creation timestamp must prove that each authoritative object
preceded slate lock. The terminal root is not produced after a partial or late
run.

## Outcome boundary and evaluation

The post-settlement grader receives the validated pre-lock terminal root and a
generation-pinned score artifact already published by an independent scorer.
The grader exact-reopens but cannot author or publish that truth source. It
cannot accept caller-supplied books, candidate pools, score maps, prefixes,
arm lists, or decision rules.

Required score reporting is:

- realized weekly maximum at K20, K40, and K80;
- hits at 194, 200, 210, 220, 230, and 240;
- candidate-pool oracle and selector regret;
- the complete 2 x 2 generation/retrieval cells and their interaction;
- simulated-versus-realized calibration at 194, 210, and 220, explicitly
  labelled descriptive because simulated tails are not calibrated; and
- field rank/percentile, duplicate evidence, and payout evidence only when a
  complete contest-field authority exists.

### Frozen decision clocks

- **Weeks 1--7:** accrual only.
- **Exactly Week 8:** integrity and severe-harm review only. It may stop a
  broken or catastrophically harmful arm, but it cannot promote an arm for
  efficacy.
- **Weeks 9--17:** continued accrual; no new decision checkpoint.
- **Full 18-week season:** first prospective efficacy estimate with a
  slate-paired 95% uncertainty interval. A positive point estimate does not
  authorize automatic adoption.

The preregistration freezes a two-point minimum practically important mean
effect, a 50% win-rate criterion, no loss of 230/240 hit weeks, and a
minus-20-point single-slate catastrophic guard. These are family-level rules;
they are not tuned separately after observing an arm.

## Complete contest-field prerequisite

A score snapshot may remain raw-score-only if a complete field cannot be
captured, but then neither contest EV nor contest allocation may be claimed.
Contest utility requires an immutable field authority containing:

- contest identity, field size, entry fee, and payout-table identity;
- every permitted entry roster, score, rank, duplicate group, and actual
  split payout;
- field ownership and a declared participant-strength measure; and
- an exact mapping of every frozen shadow lineup to matching field entries.

Actual observations are kept distinct from counterfactual placement. A shadow
lineup that was not entered has no actual rank or payout; a score-derived
counterfactual rank is separately named and cannot be presented as actual EV.
Even a complete field permits a contest-EV claim only when every frozen lineup
in the claimed book was actually entered and its duplication/split payout was
independently reconciled. Complete-field counterfactual ranks alone never do.

## Review disposition

| Review item | Production disposition |
|---|---|
| Include the 54-slate production result and uncertainty | adopted; supply improvement and selected-book uncertainty are separated |
| Make retrieval core | adopted as the exact zero-solve 2 x 2 crossing |
| Correct cap-4 “inert” claim | adopted; direct choice/exclusion trace replaces prefix exhaustion |
| State counts in production units | adopted per block and per five-block slate |
| Eight-week efficacy is invalid | adopted; Week 8 is safety/integrity only |
| Freeze arm hierarchy | adopted in registry and preregistration |
| Require cross-law influence trace | adopted as a fail-closed pre-lock receipt |
| Add 230/240 and field utility | adopted |
| Make full-field capture mandatory for EV | adopted; raw-score-only fallback is explicit |
| Scope house-rule evidence | adopted; incumbent construction is a test preset, not a universal law |
| Narrow closed families | adopted; only exact tested implementations are excluded |
| Source publication is not source value | adopted; paid-source value still requires a separately frozen on/off ablation |
| Add compact current-science index to `HANDOFF.md` | required before release commit |

## Separate tests below the core hierarchy

Construction-preset and paid-source on/off ablations are deliberately not
smuggled into the primary generation estimand. They remain independently named
tests after the exact generation/retrieval pair is operational. Source
publication proves availability and point-in-time provenance only. Each paid
source must also retain an outcome-free trace of availability, staleness,
missingness, served-feature change, model-marginal change, candidate turnover,
and selected-book turnover before any lineup-value claim is made.

The crossed fit-seed by world-seed diagnostic is also a separate mechanism
test. The current contract freezes the exact 2 x 2 design lattice but labels
execution `not_evaluated`; arbitrary labelled objects are not evidence that
the four crossed fits/scores ran. A future executed diagnostic must bind the
actual generation/scoring outputs before reporting seed sensitivity.

## Current release gates

The suite-to-terminal evaluator, audit-bank calibration, field-rank/EV
separation, independent score-source seam, exact source inventory and bounded
operator are implemented and pass the focused local matrix. The remaining
operational gates are:

1. settle, commit and push the exact release cohort;
2. build the digest-pinned image from that pushed commit archive;
3. install the dedicated unscheduled Cloud Run job without launching it;
4. publish the create-once Week 1 preregistration before lock; and
5. run one outcome-blind live-input smoke early enough to measure full-suite
   wall time and preserve a safe pre-lock margin.

Deployment and execution are separate operations. Installing the immutable
job cannot implicitly launch a slate experiment.
