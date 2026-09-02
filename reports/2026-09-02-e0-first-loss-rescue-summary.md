# E0 first-loss and rescue summary

**Date:** 2026-09-02  
**Evidence class:** descriptive development only  
**Decision authority:** none

## Adopted implementation boundary

Scoring, lineup generation, selection, and the active experiment queue remain
untouched. E0 is used now as a read-only evidence layer. The next graph surface
will be additive, summary-only, and based on production's
`corpus-graph-vnext/v2` contract. React is optional presentation work and is not
on the critical path. The observatory branch will not be merged wholesale, and
the full candidate population will not be forced through the observatory v1
capacity contract.

The queried local load is the receipt-bound E0 slice with plan SHA-256
`e852521d97d3cb37d8e46c6336694f003114b72aa9908277ee7783a1fe1b6821`.
It contains 4,258 E0 nodes and 8,623 E0 relationships. The source adapter
reconciled 199,244 candidates, 378,000 generation visits, 432 final-fit books,
and 34,560 final-fit selections before materializing only the 279 persisted
lineups scoring at least 200 DK points plus full-population denominator nodes.
No lineup was rescored for this analysis.

## What E0 establishes now

- 29 of 54 slates had at least one 200+ lineup in the eligible corpus.
- Only 10 of those 29 opportunity slates had a 200+ lineup captured by at least
  one final-fit strategy.
- Of 279 distinct 200+ eligible lineups, 38 were selected by at least one
  final-fit strategy and 241 were missed by every final-fit strategy.
- Therefore the first **observable** loss for those 241 lineups is retrieval.
  E0 does not prove that retrieval is their first causal loss across the whole
  pipeline because attempted generation, legality rejection, deduplication,
  and admission transitions are not present as separate complete stages.

### Final-fit strategy summary

`Mean hindsight rescue` is the persisted eligible-corpus maximum minus the
selected-book maximum, averaged over all 54 slates. It is a hindsight diagnostic,
not a forecast, promised gain, or sum of independently recoverable lineup deltas.

| Final-fit strategy | Mean selected weekly max | Mean eligible-corpus max | Mean hindsight rescue | Slates with positive rescue | Eligible 200+ but selected below 200 | Selected weeks 200+ |
|---|---:|---:|---:|---:|---:|---:|
| block-supported-tail-ladder-v1 | 178.435 | 202.662 | 24.227 | 49 | 23 | 6 |
| tail-ladder-200-210-220-v1 | 178.435 | 202.662 | 24.227 | 49 | 23 | 6 |
| strict-230-coverage-v1 | 177.462 | 202.662 | 25.200 | 49 | 22 | 7 |
| regime-robust-ladder-v1 | 177.103 | 202.662 | 25.559 | 49 | 22 | 7 |
| coverage-194-v1 | 176.882 | 202.662 | 25.780 | 50 | 23 | 6 |
| expected-max-v1 | 176.537 | 202.662 | 26.125 | 51 | 23 | 6 |
| strict-200-coverage-v1 | 176.359 | 202.662 | 26.303 | 51 | 23 | 6 |
| mean-score-v1 | 176.003 | 202.662 | 26.660 | 50 | 23 | 6 |

This is strong evidence that retrieval remains a large research target on this
historical panel. It is not evidence that a forward selector can recover 24–27
points: `202.662` is the outcome-known maximum of the eligible corpus.

### Descriptive structure of captured versus missed 200+ lineups

| Group | Lineups | Mean score | Mean salary | Mean QB teammates | Bring-back rate | Four-plus same-game rate |
|---|---:|---:|---:|---:|---:|---:|
| Captured by any final-fit strategy | 38 | 213.212 | 49,797 | 2.211 | 60.5% | 73.7% |
| Missed by every final-fit strategy | 241 | 209.048 | 49,710 | 1.651 | 68.5% | 52.7% |

These are selection-conditioned descriptions, not causal recommendations. In
particular, the captured group having more QB teammates and more concentrated
games may reflect what the current selectors already reward. The lower
bring-back rate among captured lineups is a useful hypothesis for crossed
testing, consistent with the no-bring-back tail-sleeve work, but this table
does not authorize a rule change.

### Generation-arm high-score density

Every arm has 54,000 recorded visits. The rate below is persisted 200+ lineup
visits per 1,000 visits on this E0 panel.

| Generation arm | 200+ visits | 200+ visits per 1,000 |
|---|---:|---:|
| allow-rb-vs-dst | 94 | 1.741 |
| incumbent | 93 | 1.722 |
| allow-two-rb | 91 | 1.685 |
| remove-salary-floor | 88 | 1.630 |
| remove-bring-back | 80 | 1.481 |
| remove-qb-stack | 75 | 1.389 |
| remove-all-five-shared-constraints | 53 | 0.981 |

This old-panel result does not contradict the newer context-matched tail sleeve:
the E0 arm removes a construction law globally, while PREREG-053/055 apply a
bounded sleeve with world coverage preserved. It reinforces the need to retain
arm, sleeve location, world block, and selection policy as separate coordinates.

## Summary architecture: v2 lineage plus the bounded E0 outcome companion

Production's `corpus-graph-vnext/v2` is deliberately outcome-closed: it rejects
the `realized` namespace, outcome nodes/edges, and outcome-like property names.
The 200+ and rescue quantities above are outcome-derived. They must **not** be
smuggled into v2 `MetricSet` or `Evaluation` nodes merely by giving them neutral
names or setting authority flags false.

The selective integration therefore has two explicit parts:

### Outcome-free v2 projection

1. `prelock_funnel_census`: complete candidate, visit, book, and selection
   counts; strategy and source identities; no realized threshold counts.
2. `lineage_coverage_summary`: a positive list of stages actually observed,
   stages missing, exact source identities, and the earliest stage that the
   evidence can localize without outcomes.
3. `strategy_lineage_summary`: fill/admission/retrieval identities and bounded
   stage-transition counts once the complete pre-lock trace exists.

These may map to v2 `Evaluation`, `MetricSet`, `Cohort`, `SourceArtifact`, and
`VerificationReceipt` vocabulary with every authority flag false.

### Existing E0 historical-outcome summary

1. `outcome_funnel_summary`: 200+ opportunity, captured, and missed counts;
   opportunity and converted slate counts.
2. `strategy_rescue_summary`: per-strategy selected maximum, eligible-corpus
   maximum, selector regret, threshold capture, and counts of positive-rescue
   slates. Any summed one-lineup counterfactual must be named
   `sum_individual_rescue_deltas` and explicitly marked non-joint.
3. `phenotype_capture_summary`: captured-versus-missed distributions with
   denominators and missingness, never individual roster output.
4. `generation_yield_summary`: arm and arm-by-block visit denominators and
   realized high-score yields.

For now these remain queries over the already accepted, separately labelled E0
historical slice. A future reviewed outcome-summary companion contract (or a
new graph schema version with an exact `OutcomeRelease` boundary) may project
them more broadly; v2 itself must not be weakened. A read API may return the two
envelopes side by side only if their schema/evidence classes remain distinct.
It should return bounded summaries, never lineup enumeration. Do not add a
winner claim or promotion edge. The existing legacy UI and route remain the
default until a later additive React preview reaches parity.

## Required lineage extension

The highest-value next artifact is a complete, immutable pre-lock candidate
trace for every attempted candidate, not only delivered candidates. Each row
needs stable roster identity and explicit transitions for:

1. attempted generation;
2. DraftKings legality evaluation and rejection reason;
3. deduplication;
4. corpus admission and admission reason/preset;
5. eligibility for each retrieval strategy;
6. selector score, rank, and selected/not-selected decision; and
7. pre-lock feature/belief version identities from a strict allowlist.

That trace must be frozen before outcome access. Post-outcome settlement joins
by exact roster identity in a separate reader. With those two artifacts, a
first-loss query can assign each valuable lineup to exactly one earliest stage,
and a rescue query can report one-at-a-time counterfactual deltas without
misrepresenting their sum as jointly achievable. Until that extension exists,
E0 supports exact retrieval-loss descriptions but not complete pipeline-loss
attribution.
