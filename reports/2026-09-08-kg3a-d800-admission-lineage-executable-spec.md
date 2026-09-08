# KG-3A D800 admission-lineage audit and executable specification

**Date:** 2026-09-08  
**Branch:** `codex/kg3a-admission-lineage`  
**Scope:** additive, outcome-boundary-preserving preparation only; no scoring,
selector, generation, deployment, graph, or cloud changes

## Decision

Do **not** spend a historical score lane on KG-3A as if it diagnoses an
existing D800 admission loss. The adopted lab D800 funnel has no candidate
admission or pool-cap step. Every successfully delivered unique candidate is
passed to the selector. Consequently, for the current D800 funnel:

```text
delivered unique candidates == admitted candidates == selector-eligible candidates
```

and the candidate-level first-loss count at admission is exactly zero by
construction. A high-scoring D800 candidate that exists in the delivered pool
but is absent from K80 was first observed lost at **selection**, not admission.
Generation requests that end infeasible, in error, exhausted, or as duplicates
remain request/occurrence yield outcomes; they are not roster-identified
admission losses.

This is not a reason to abandon fixed-budget admission generally. It means
KG-3A becomes relevant only when a broader candidate union is intentionally
compressed to a fixed budget before the selector. That is a new intervention,
not a missing baseline trace field.

The immediate score-directed route for the existing D800 pool remains the
same-pool selector/feature work. If a broader union is introduced, use the
contract below to test its admission policies at identical counts.

## Evidence audited

### Lab D800 trace

Current lab `origin/main` contains the frozen PREREG-066 / experiment 095
candidate trace:

- `experiments/095_generation_retrieval_crossing.py` generates each 800-solve
  pool, globally deduplicates delivered lineups, constructs the decision
  matrix over the entire delivered pool, and runs DEMAX and NOV directly on
  that pool;
- `src/nfl2/kg/candidate_trace.py` writes one row per delivered unique
  candidate with exact full-roster SHA-256, family tag, salary, pre-lock
  simulated mean/q99, and selection membership/rank;
- `scripts/lab_lineage_census.py` states and checks the funnel invariant:
  `t3_unique_occurrences == t4_admitted == len(trace)`, with no admission cap
  and no post-selector replacement; and
- `scripts/prereg066_lineage.py` reconstructs the candidate-only CTRL and
  REDIST D800 lineage after recursively stripping outcome blocks.

The accepted 095 result also confirms the scientific issue: the redistributed
pool created more high scorers, but the incumbent retrieval converted little
of that supply. That is selection evidence, not admission evidence.

### Production lineage and admission infrastructure

Production already has two relevant, non-overlapping systems:

1. `src/nfl_dfs/inference/prelock_candidate_lineage_v1.py` plus
   `prelock_lineage_settlement_v2.py` implement a rich live/pre-lock trace and
   an exact-roster post-lock first-loss reader. The current runtime adapter is
   for the five-seed CBWU/coverage path, not lab D800/DEMAX.
2. `src/nfl_dfs/research/corpus_r6_broad_admission_tournament_v1.py` implements
   A250/A500 fixed-budget admission on the combined R6 union. It already has
   score-free reference, source-quota/disagreement, and walk-forward direct
   admission machinery. It is not a D800 adapter, and its failed E4 operation
   did not produce a sealed score verdict.

Neither should be duplicated or relabelled as current-D800 admission.

## Exact current-artifact limitations

The frozen 095 artifacts are sufficient to produce a **candidate-complete
delivered-unique/selection trace** and to prove zero baseline admission loss.
They are not sufficient to claim the complete production v1 lineage contract:

1. Candidate trace rows contain the roster hash but not the nine player IDs,
   positions, or the internal-to-DraftKings identity bridge. Candidate-level
   novelty, pair, matchup, and paid-entry joins therefore cannot be reproduced
   from the trace alone.
2. The saved `ledger_*` block is an aggregate receipt, not one immutable row
   per proposal request, solve attempt, occurrence, and dedupe decision.
3. There is no admission decision because D800 has no admission stage.
4. DEMAX-specific dynamic marginal/tie-break rows are not preserved for every
   candidate; the trace preserves selection membership and selected rank.
5. These are outcome-disabled historical reconstructions. They must not be
   backdated or described as provider-timestamped live pre-lock artifacts.

Because these are source-artifact omissions, a production-only adapter cannot
truthfully synthesize the missing fields. No regeneration or outcome-known
imputation is authorized by this specification.

## Deliverable A: seal the existing D800 baseline lineage census

The lab can complete this immediately without another score run. For each
accepted 095 bank/result object, execute the already-implemented outcome-free
extract and census on the immutable object bytes.

The accepted efficacy run prefixes are:

- `095b690r1-20260904T164737Z`;
- `095b691r1-20260904T165019Z`; and
- `095b692r1-20260904T180305Z`.

From a clean lab checkout containing the accepted PREREG-066 source, the
aggregate census entry point is:

```bash
PYTHONPATH=src python scripts/lab_lineage_census.py \
  095_generation_retrieval_crossing \
  095b690r1-20260904T164737Z \
  095b691r1-20260904T165019Z \
  095b692r1-20260904T180305Z
```

For each exact downloaded result envelope, create the candidate-only artifact
before opening its outcome-bearing blocks:

```bash
PYTHONPATH=src python scripts/prereg066_lineage.py \
  path/to/exact-result-envelope.json \
  --out results/prereg066_lineage/exact-result-envelope.json
```

The coordinator must bind every local input to its provider generation, byte
size, and SHA-256 first; bare run-prefix discovery is not an acceptance
identity. The existing scripts may be wrapped to enforce that manifest, but
their frozen 095 input or output semantics must not be edited in place.

Required outputs:

1. `prereg066-lineage/v1` candidate-only JSON/JSONL, one row per
   `(run_id, season, week, bank, generation_arm, roster_sha256)`;
2. `lab-lineage-census/v1`, explicitly recording:
   - requested solves and aggregate terminal outcomes;
   - delivered unique candidates;
   - `admitted = delivered unique`;
   - selector-eligible candidates;
   - selected and eligible-unselected counts; and
   - no post-selector replacement;
3. exact input object generations, byte sizes, SHA-256s, source commit, image
   digest, run IDs, trace hashes, and output hashes; and
4. a post-settlement exact `(slate_id, roster_sha256)` join, kept in a separate
   reader artifact, reporting high-score counts by:
   - `REQUEST/YIELD_ONLY` (aggregate, never roster-localized),
   - `ADMISSION` (must be zero for baseline D800),
   - `ELIGIBLE_NOT_SELECTED`, and
   - `FINAL_BOOK`.

Required fail-closed checks:

- all 54 result objects and all declared slates exist;
- candidate hashes are unique within `(bank, slate, generation pool)`;
- DEMAX and comparator traces cover identical candidates within a generation
  pool;
- selected ranks are exactly `1..K`, with no duplicate selected hash;
- `delivered == trace rows == admitted == selector eligible`;
- outcome-like fields are stripped before the candidate artifact is read;
- the settlement join rejects duplicate, missing, extra, wrong-slate, or
  mismatched roster hashes; and
- output reopening reproduces every canonical hash.

This deliverable answers the routing question. It does not require Neo4j and
does not mutate it. Neo4j may later index its bounded summary.

## Deliverable B: extend future D800 traces at the source

For the next frozen D800 cohort, extend the lab runner additively before any
outcome access. Preserve scoring and selected indices byte-for-byte with trace
emission disabled versus enabled.

Each delivered unique candidate row must add:

```json
{
  "internal_player_ids": ["nine", "sorted", "ids"],
  "internal_id_namespace": "versioned namespace",
  "roster_sha256": "full 64-hex existing roster hash",
  "source_request_ids": ["request ids"],
  "source_occurrence_ids": ["occurrence ids"],
  "dedupe_dispositions": ["closed enum values"],
  "admission_stage_id": "d800-identity-admission-v1",
  "admission_disposition": "RETAINED",
  "admission_reason": "NO_POOL_CAP_ALL_UNIQUE_RETAINED",
  "selector_eligible": true,
  "selector_decision": "SELECTED or ELIGIBLE_NOT_SELECTED",
  "selector_rank": null,
  "selector_terminal_marginal": null
}
```

The `selector_rank` is populated only for selected candidates. A dynamic
DEMAX marginal may be populated only when captured during the actual greedy
execution. Do not fabricate a retrospective rank or marginal for unselected
candidates.

Also emit one row for every proposal request and solve attempt with a closed
status (`PRODUCED`, `DUPLICATE`, `INFEASIBLE`, `SOLVER_ERROR`, or
`EXHAUSTED_NOT_ATTEMPTED`). Failed requests have no roster identity. A
duplicate occurrence points to the surviving roster and is attribution, not a
lineup loss.

If a DraftKings/live bridge is needed, production separately supplies the
salary-catalog identity and exact internal-to-draftable mapping. Historical
lab lineage must not invent that bridge.

## Deliverable C: KG-3A only when a real fixed-budget cap exists

Freeze KG-3A only against a generated union whose delivered-unique count is
strictly greater than a predeclared admission budget on every tested slate.
The first bounded choice should reuse the existing **A500** contract rather
than create a new budget grid. If any slate has fewer than 500 eligible unique
candidates, fail the cohort before outcomes; do not vary the budget by slate.

Hold constant across every arm:

- generated union bytes and candidate order;
- exact candidate count before admission;
- admitted count = 500;
- downstream candidate matrix/worlds;
- downstream selector, K, tie-breaks, and resource envelope; and
- settlement and reporting code.

The minimum arm family is:

1. **Reference A500:** the existing score-free modeled-tail reference law.
2. **Source-quota/disagreement A500:** the existing score-free quota law.
3. **Optional walk-forward A500:** include only if its model and all target-
   slate features were frozen from prior seasons before target outcomes.

Do not add a generic novelty arm until the trace contains roster player IDs
and its distance law is frozen. Do not use target-slate realized outcomes to
choose candidates or tune quotas. Do not compare A500 with admit-all and call
the difference an admission-policy effect; equal admitted count is the
estimand.

### Candidate-level admission artifact

Emit one decision per candidate per arm:

```json
{
  "slate_id": "2022-w08",
  "bank": 690,
  "candidate_id": "versioned roster identity",
  "admission_arm": "modeled-tail-reference",
  "admission_budget": 500,
  "input_ordinal": 17,
  "disposition": "RETAINED or REJECTED",
  "reason": "RETAINED_REFERENCE_RANK or DROPPED_FIXED_BUDGET",
  "admission_rank": 42,
  "tie_break": ["frozen", "ordered", "values"]
}
```

Rejected rows have `admission_rank = null`. The arm must contain exactly one
decision for every generated unique candidate, exactly 500 retained decisions,
and no unknown reason.

### Reader-only retention grade

After the admission artifacts are frozen, join outcomes by exact roster
identity and report at 194/200/210/220/230:

- generated candidate count;
- generated high-score candidate count;
- admitted high-score candidate count;
- high-score recall (`admitted / generated`);
- high-score first-loss-at-admission count;
- maximum realized score retained by the admission policy;
- realized score of the best rejected candidate;
- source/family and recurrence strata for retained versus rejected rows; and
- exact overlap/Jaccard between admission arms.

These are **retention** diagnostics. They do not claim that the retained oracle
is selectable or that the gap to the 205.793 hindsight union is recoverable.
Only after the same downstream selector is run on every A500 arm may the
registered book endpoint be compared.

## Implementation ownership and smallest code delta

1. **Lab:** seal Deliverable A from existing 095 objects; add Deliverable B at
   its D800 runner/trace source; run Deliverable C only after a frozen contract.
2. **Production:** review hashes/cardinalities and supply a live DraftKings
   identity bridge only for a prospective production D800 run.
3. **Do not change:** production scoring, generation, selectors, live policy,
   deployment, graph schema/state, or the frozen v1 lineage contract.
4. **Reuse:** the existing production A250/A500 admission implementation and
   its validators if/when the D800/broader-union source adapter can satisfy the
   input schema. Do not fork a second admission algorithm.

## Acceptance and routing

The baseline census is accepted when it proves, for every D800 cell:

```text
delivered_unique == admitted == selector_eligible
first_loss_at_admission == 0
selected + eligible_not_selected == selector_eligible
```

Then route immediately:

- Existing D800 missed high scorers -> selector calibration/reranking and
  candidate-rescue diagnostics, not KG-3A.
- A new broader union loses valuable candidates at its A500 cap -> run the
  fixed-budget KG-3A crossing using the existing admission laws.
- A new broader union contains no credible extra supply -> return to
  generation, not admission tuning.

## Exact blocker to a production implementation today

Production does not possess a source artifact that simultaneously contains:

1. the full D800 delivered candidate rows with nine player IDs;
2. request/attempt/occurrence/dedupe rows;
3. an actual fixed-budget admission stage; and
4. the DEMAX dynamic selector trace.

The lab 095 artifacts provide candidate hashes and selection membership but
not items 1–3 in the required form. Production's rich v1 schema is tied to a
different CBWU/coverage runtime and cannot encode DEMAX faithfully without a
new schema revision. Synthesizing the missing fields would create false
lineage. Therefore this work stops at the executable source contract and
routes the current D800 finding to selection; it does not add a misleading
adapter or launch an unidentifiable experiment.
