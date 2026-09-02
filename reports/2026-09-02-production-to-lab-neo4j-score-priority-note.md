# Production-to-lab note: turn graph findings into score-directed experiments

**Date:** 2026-09-02  
**Audience:** lab experiment team and production implementation team  
**Purpose:** remove ambiguity about what the E0/Neo4j findings should change

## Direction

The current graph has delivered useful hypotheses, but it has not reached its
highest-value use. The next priority is not additional UI work, a generic graph
redesign, or loading dense world-matrix cells into Neo4j. It is to explain why
promising candidates were undervalued or lost, then convert those explanations
into outcome-free, walk-forward generation/admission/selection treatments.

This direction does **not** interrupt experiment 087 or create a duplicate E0
experiment. It does change the content of 088 and the explicit queue after 088.

## Evidence motivating the work

- The current adopted D800_DEMAX K80 baseline is **181.456 mean weekly
  maximum** on the frozen 72-slate panel.
- The corresponding mean weekly D800 hindsight oracle is **194.505**, leaving
  **13.048 points of mean observed pool-to-book regret**. This is not a promised
  recoverable gain. The oracle uses realized outcomes and exists only to show
  that retrieval remains materially imperfect.
- On the separate 54-slate E0/R6 panel, the final-fit strategy union selected
  only **38 of 279** available 200+ lineups and converted **10 of 29** slates
  with a 200+ corpus opportunity. Those numbers are selection-conditioned
  diagnostics, not a causal selector estimate and not directly comparable to
  the D800 oracle.
- The E0 structural read shows that the legacy selector union is more
  concentrated than the high-score population. The lab's outcome-disabled
  D800 census independently shows that the adopted selector under-retains the
  minimum-concentration `2 catcher / 1 bring-back / 4 same-game` phenotype.
- Relaxed R6 construction arms supplied 169 exclusive 200+ lineups, including
  112 from the remove-bring-back and remove-QB-stack arms. This nominates
  fixed-budget supply/retention tests; it does not authorize restoring any hard
  construction rule or choosing weights from target-fold outcomes.

## Immediate queue effect

1. **Finish and read 087 without interruption.** It is the aligned same-D800-
   pool DEMAX-versus-WEMAX selector test and determines 088's exact control.
2. **Run 088 next.** Its leverage-calibration and minimum-concentration
   retention arms are the first decision-bearing tests produced by the graph
   findings. The lab owns this execution; production should not duplicate it.
3. **Keep participation work moving in parallel.** It addresses a different
   point-loss mechanism and should not be folded into the graph family.
4. **Build the data/lineage substrate in parallel without consuming a cloud
   efficacy lane.** This work enables the post-088 queue below.

Thus, “no queue change” is accurate only if it means no interruption or
reordering of 087 -> 088. It is not accurate if it means the graph findings
create no downstream score-directed work.

## Highest-value enabling deliverable

Finish one complete, immutable D800 pre-lock candidate-lineage package. For
every candidate and every applicable stage it must preserve:

1. proposal family, request and attempt outcome;
2. generated roster identity and all source tags;
3. legality, deduplication and admission decisions with closed reason codes;
4. eligibility for each selector;
5. dynamic selector marginal, rank, selected/not-selected decision and exact
   tie-break values;
6. post-selection replacement, final-book and prepared-entry transitions; and
7. exact code, configuration, player-pool, world/belief and artifact identity.

The trace freezes before outcome access. A separate reader joins settlement by
the exact slate/roster identity. Instrumentation enabled and disabled must
produce byte-identical candidate matrices, selected indices, book ordering and
entry output.

The lab owns complete candidate-trace emission from its historical D800
runners, including 087/088. Production owns publication of the compact R6
package and the live-production D800 identity/entry bridges. The lab already
has the fail-closed production-package adapter and should validate and accept
that package rather than independently reconstruct production data.

## Point-in-time feature overlay

Attach available, explicitly sourced pre-lock features for the full comparison
population, not merely the known high scorers:

- lineup structure, salary allocation and generator recurrence;
- simulated mean/q90/q95/q99, EMAX/WEMAX components and scenario coverage;
- projected ownership, leverage and duplication proxies;
- boom probability/class and role/target/opportunity features;
- participation probability with timestamp and missingness;
- player-pair correlation and co-boom summaries; and
- coverage/defender assignment, opponent allowance by receiver role, man/zone
  and route-fit summaries where point-in-time source authority exists.

Dense matrices remain in immutable object/columnar storage. Neo4j stores their
identities and derived relationship summaries. Missing features remain explicit
null/missingness states; they are not reconstructed after outcomes merely to
complete the schema.

Registry v2 is **not** a blocker for this corpus, lineage, admission, retrieval
or point-in-time trait work. It is required for authoritative target-contest
winner claims, not for analyzing generated candidates and settled corpus
lineups under their properly labelled evidence class.

## Required graph analyses

Once the lineage and feature package is accepted, emit reproducible cohorts and
query receipts for:

1. **First loss:** the earliest observed stage at which each settled valuable
   candidate was dropped—request/attempt/production within a declared finite
   universe, admission, selector eligibility, eligible-but-unselected,
   selected-then-replaced, or final-book/entry boundary. Never claim
   `NOT_GENERATED` when no finite candidate universe containing that lineup was
   frozen before generation.
2. **Phenotype recall:** candidate availability, retention and final-book recall
   by portable structure, belief, ownership, boom, participation, correlation
   and matchup feature families, with slate and generator exposure accounted
   for.
3. **Candidate rescue:** exact-K, one-candidate-at-a-time counterfactual rescue
   under the frozen pre-lock book and worlds. Report individual deltas; never
   sum them as jointly achievable.
4. **Calibration:** predicted versus settled upper-tail behavior by candidate
   family and phenotype, especially leverage and structural under-retention.

These reads nominate treatments. They do not directly promote a policy because
the same historical outcomes helped identify the hypotheses.

## Score-directed experiment sequence after 088

1. **Fixed-budget admission/retention (KG-3A):** compare current admission with
   prespecified family-stratified and novelty/exclusivity policies at identical
   generated and admitted counts, using the same downstream selector.
2. **Walk-forward learned phenotype selector (KG-5, same-pool first):** train on
   prior folds only using portable feature families; compare exact K80 books on
   the identical frozen candidate pool.
3. **Direct phenotype-based generator:** translate the frozen portable model
   into a deterministic legal-lineup objective at the same compute/delivered-
   unique budget, then pass both pools through identical admission and
   retrieval. Implementation may proceed in parallel, but its scientific read
   follows the same-pool reranker so generation and retrieval effects remain
   identifiable.
4. **Generation-law mixture (KG-2):** retain the separately planned bounded
   topology sleeves at fixed total solve/admission budgets. This is complementary
   to, not a substitute for, the intelligence chain above.
5. **Generation x admission x retrieval crossing (KG-6):** cross only the best
   frozen components. Do not add standalone point estimates arithmetically.

Every efficacy comparison uses the current objective ladder and reports raw
weekly maximum and 200/210/220/230 landmarks as diagnostics. Historical reads
remain development evidence; prospective 2026 entry/field/payout settlement is
the adoption authority.

## Completion test for this direction

This work is not complete merely because Neo4j is loadable or because summary
queries render in the API. It is complete when we can answer, with immutable
receipts, all four questions for a valuable lineup:

1. Was it generated, and by which pre-lock request/family?
2. If generated, where was it first removed?
3. Which pre-lock traits and belief components distinguished it from retained
   candidates after controlling for slate and exposure?
4. Did a preregistered walk-forward treatment using those traits improve the
   exact-K portfolio endpoint?

Until then, Neo4j has produced the first hypotheses, not exhausted the lineup
intelligence opportunity.
