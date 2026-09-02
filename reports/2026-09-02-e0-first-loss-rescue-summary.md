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
  final-fit strategy and 241 were absent from every observed final-fit book.
- The exact evidence class for those 241 is
  `FIRST_OBSERVED_ABSENCE_AT_FINAL_BOOK`. The E0 adapter synthesizes absence by
  set difference; it does not contain a source-emitted selector rejection or
  per-candidate eligibility/marginal trace. E0 therefore does not prove that
  retrieval is their first causal loss across the whole pipeline. Attempted
  generation, legality rejection, deduplication, and admission transitions are
  not present as separate complete stages.

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
| Absent from every observed final-fit book | 241 | 209.048 | 49,710 | 1.651 | 68.5% | 52.7% |

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

1. `outcome_funnel_summary`: 200+ opportunity, captured, and final-book-absence
   counts; opportunity and converted slate counts.
2. `strategy_rescue_summary`: per-strategy selected maximum, eligible-corpus
   maximum, selector regret, threshold capture, and counts of positive-rescue
   slates. Any summed one-lineup counterfactual must be named
   `sum_individual_rescue_deltas` and explicitly marked non-joint.
3. `generation_yield_summary`: arm and arm-by-block visit denominators and
   realized high-score yields.
4. A later `phenotype_capture_summary`: captured-versus-missed distributions
   with denominators and missingness, never individual roster output. The first
   bounded companion deliberately does not claim this additional surface.

Production `main` now contains the reviewed, fixed-identity
`corpus-r6-historical-realized-summary/v1` core for the first three surfaces.
It rebuilds from the exact 219-object E0 source set and remains a separate
schema. The create-once runner and isolated GET-only file surface are now
implemented. The first production artifact is
`reports/2026-09-02-r6-historical-realized-summary-v1.json`: 24,536 bytes,
file SHA-256
`ad348254d5aee023b7864ffb10ef4f70d4c3e4a415b3a097d8ea53ea9d1f94eb`,
and semantic summary SHA-256
`c5bd768eda8b4211a5ebe7aa48138246b3d659f94cb7c0981cc1fb578034d856`.
The API route is
`GET /api/corpus-research/historical-realized-summary`, reads the explicitly
configured absolute file on every request, revalidates the complete contract,
and returns `Cache-Control: no-store`. A production-file integration read
returned HTTP 200 and the exact semantic hash.

This artifact and endpoint do not mutate Neo4j, enumerate lineups, alter
scoring/selection, or grant promotion authority. v2 itself must not be
weakened. Any API returning the two envelopes side by side must preserve their
distinct schemas and evidence classes. Return bounded summaries, never lineup
enumeration. Do not add a winner claim or promotion edge. React remains
optional presentation work.

### Initial arm-by-world-block read from the bounded artifact

All 35 arm-by-block cells have an equal 10,800-visit denominator, so their raw
200+ visit rates are directly comparable as descriptions of this fixed panel.
The five highest cells are `remove-salary-floor/R1` (26, 0.241%),
`allow-rb-vs-dst/R1` (24, 0.222%), and a four-way neighborhood at 23
(0.213%) led by `allow-rb-vs-dst/R0`, `allow-two-rb/R0`, and incumbent R0/R1.
The weakest world block is R3 overall (69 of 75,600, 0.091%), compared with R0
(140, 0.185%), R1 (132, 0.175%), R2 (128, 0.169%), and R4 (105, 0.139%).

These cells are hypothesis coordinates, not independent experiments: the same
lineup can occur under multiple arms, the threshold is outcome-derived, and
the panel has already been opened. They justify preserving arm-by-block
lineage and testing bounded crossed allocations prospectively; they do not
justify replacing universal legality with a new hard-coded construction law.

## Required lineage extension

The highest-value next artifact is a complete, immutable pre-lock request and
candidate trace, not only a ledger of delivered candidates. Request/attempt
rows and roster-bearing candidate rows are distinct: an infeasible solver call
has no canonical roster to which a later outcome can honestly be joined. Each
successful roster occurrence needs stable identity and explicit transitions
for:

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

## Concrete pre-lock lineage implementation slice

This work is additive instrumentation, disabled by default, and must not change
candidate arrays, simulated totals, selector inputs, selected indices,
post-selector ordering, paid-entry output, or scoring. The first implementation
should cover one prospective shadow end to end before it is generalized.

### Do not invent one universal roster hash

Production currently has multiple valid identity laws over different ID
namespaces:

- `generation_exposure.roster_identity` hashes sorted internal `Lineup.ids`;
- prospective `lineup-v1` maps internal player IDs to slate-specific
  DraftKings draftable IDs before hashing; and
- historical E0 canonical lineup identity also binds the slate identity.

The trace must emit a versioned identity tuple and exact bridge, not relabel one
existing digest as globally canonical:

1. season, week, slate ID, and DraftKings draft-group ID;
2. nine sorted internal production player IDs plus namespace/version and hash;
3. nine sorted DraftKings draftable IDs plus namespace/version and hash;
4. the exact salary/player-catalog identity used for that mapping; and
5. experiment-specific aliases, including `lineup-v1` or E0 identity where
   applicable, together with their declared identity law.

Every candidate-stage row binds to this tuple. Post-lock settlement of an
entered lineup joins on `(contest_id, EntryID, mapped exact roster)`; a roster
digest alone is not authoritative evidence that we submitted the entry.

### Stage records and implementation seams

The minimum closed record set is one `RunHeader`, then one `ProposalRequest`
per requested family slot, one `SolveAttempt` per invocation/retry, one
`GeneratedOccurrence` per successful solve, one `DedupeDecision` per
occurrence, one `AdmissionDecision` for every applicable cap/combine/transform
stage, one `StrategyDecision` per effective candidate and retrieval strategy,
one `BookTransition` through post-selection/export ordering, and one
`PreparedEntry` per targeted Entry ID.

Implementation should proceed at these existing seams:

1. Extend the outcome-free solve ledger in
   `src/nfl_dfs/inference/generation_exposure.py` to every enabled generator
   family. It already records new, duplicate, infeasible, error, and exhausted
   attempts; `tail_select_lineups` currently fails closed for several families
   whose attempt capture is incomplete.
2. Capture the complete generated/deduplicated set and source tags at the
   native `CandidateBatch` boundary in `src/nfl_dfs/backtest/engine.py`, both
   before and after `candidate_transform`. Existing `candidate_capture` is a
   useful seam but is not a complete stage trace.
3. Add candidate-level, outcome-free transition rows to deterministic pool-cap
   and five-seed CBWU combine/admission steps. Record retained or dropped,
   rule/version, source family/seed, input/output ordinal, and a closed reason
   code. Existing aggregate retained/dropped tag counts are insufficient.
4. Instrument the selector during its actual greedy execution. For a selected
   candidate record selection rank, fresh-world marginal at that step,
   individual clear count, mean simulated total, phase, and deterministic
   tiebreak tuple. For a nonselected candidate record its individual statistics,
   final fresh-world count, eligibility, and terminal reason. Do not fabricate
   a single retrospective "greedy rank" for nonselected candidates: their
   marginal changes as the selected set changes.
5. Record raw selector rank separately from peak/thesis replacement,
   application confidence reordering, and exported rank. Collapsing these
   distinct transitions would misidentify the actual loss stage.
6. At the paid-entry boundary, freeze the filled DraftKings entries bytes and
   an exact `EntryID -> contest_id -> draftable-ID roster -> identity tuple`
   manifest. The current receipt proves set/order properties but does not
   preserve this row mapping; the notes download event is not submission or
   lock evidence.

The primary code areas are the player-pool/as-of receipt in
`src/nfl_dfs/inference/live_lineups.py`, generation and selection in
`src/nfl_dfs/backtest/engine.py`, CBWU admission in
`src/nfl_dfs/inference/multiseed_portfolio.py`, application ordering in
`src/nfl_dfs/app/main.py`, and paid assignment in
`src/nfl_dfs/optimizer/paid_classic_book_v2.py`.

Use closed enums rather than prose. At minimum distinguish produced,
infeasible, solver error, and exhausted requests; same-family, cross-family,
and cross-seed duplicates; retained versus pool-cap/quota/budget/transform
exclusions; selector coverage-phase, saturation-fill, ineligible, and
book-full outcomes; and post-selector retention, peak/thesis replacement, and
export-only reorder. Exact-roster deduplication is normally attribution rather
than lineup loss because one earlier copy survives.

### Freeze, graph, and settlement boundary

Freeze the detailed candidate-lineage object immediately after final book
construction and before any outcome-bearing block. Freeze the prepared-entry
object after paid fill. Bind both under a create-once terminal pre-lock root
whose trusted provider creation time precedes lock and which includes exact
implementation, configuration, player/catalog, belief/world, construction,
retrieval, and sidecar identities. Operational timings may live in a separate
envelope but not alter the semantic science hash.

Keep detailed candidate rows outside `corpus-graph-vnext/v2`. Project only
bounded outcome-free stage censuses, coverage declarations, strategy/source
receipts, and aggregate transition counts into v2. Its outcome firewall and
capacity limits remain unchanged, and generation/selection code must not import
a graph client. The separate post-settlement companion joins the frozen trace
to outcomes and contest facts.

The first-loss reader may then assign each settled, roster-identified valuable
lineup to exactly one earliest observed candidate state:

`failed legality/book boundary -> not admitted ->
selector-ineligible -> eligible/not selected -> selected then replaced ->
final book/not prepared -> prepared/not confirmed`.

Generation yield and infeasibility remain request-level summaries. A specific
lineup may be labelled `NOT_PRODUCED` only when a finite, predeclared roster
universe containing that exact lineup was frozen before generation; ordinary
optimizer requests do not establish that fact. Even then, `NOT_PRODUCED` is
relative to that bound universe, not to every legal lineup. Rescue reruns
restore one candidate at a time under exact K and the frozen pre-lock worlds.
Report `individual_counterfactual_delta`; never label the sum jointly
achievable or allow it to feed promotion/live policy.

### Minimum acceptance tests

- Instrumentation off/on produces byte-identical candidate-matrix hashes,
  selected indices, final book order, CSV bytes, and scoring-path outputs.
- Every enabled generator family reconciles request, attempt, occurrence, and
  terminal-status cardinalities; enabling an uninstrumented family fails.
- Fixtures cover infeasible/error/exhausted attempts, same/cross-family and
  cross-seed duplicates, pool-cap drop, quota/deficit retention, fixed-budget
  drop, transform exclusion, selector phases, and post-selector replacement.
- CBWU rows reproduce exact current combined order; selector rows reproduce
  selected order and each dynamic marginal; rank maps reproduce final export.
- Every generated roster has one unambiguous cross-namespace identity bridge;
  missing, extra, reordered, cross-slate, or ambiguous mappings fail closed.
- Outcome-like fields and post-lock reads fail before publication. Exact
  sidecar reopening reproduces the terminal root; retry is idempotent and
  differing/concurrent publication cannot overwrite it.
- Paid mapping proves exact EntryID order/K, roster equality, and CSV hash;
  settlement rejects EntryID, roster, or identity-scheme mismatches.
- v2 graph summary counts reconcile to the immutable trace while v2 continues
  to reject every realized-outcome field.
