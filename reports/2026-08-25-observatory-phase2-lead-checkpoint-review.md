# Observatory Phase 2 lead checkpoint review

**Decision date:** 2026-08-25  
**Reviewed worktree:** `/home/erich/projects/nfl-predictions-observatory`  
**Reviewed branch:** `feature/neo4j-react-observatory`  
**Reviewed head:** `12116044c5ca479f2838ab91e43cfb78f9884327`  
**Decision:** **APPROVE WITH REQUIRED FIXES**

The isolated branch is clean and pushed, leaves the legacy UI and production
routes untouched, and did not access cloud, Neo4j, governed outcomes, IAM, or
deployment surfaces. There is no P0 finding. The assistant may resume for one
corrective Phase 1–2 commit and then proceed to fixture-backed, bounded Phase
3 read-API work. React cutover, live Neo4j, governed-outcome consumption,
deployment, and production activation remain withheld.

## Required P1 corrections before Phase 3

### 1. Mirror the real Core grade-report contract

The fixture in `frontend/src/api/types.ts`,
`frontend/src/fixtures/gradeReport.ts`, and
`frontend/src/pages/GradeReportPreview.tsx` uses the real schema name
`core-v1-human-readable-grade-report/v1` for a materially different payload.
The authoritative producer is `scripts/report_core_v1_grade.py`; its census is
pinned in `tests/test_report_core_v1_grade.py`.

Required correction:

- mirror the authoritative report schema exactly;
- preserve `uses_realized_outcomes: true` inside the report payload;
- represent the actual 12 strategies across three budgets, yielding 36
  absolute summaries rather than 12 invented fill/budget rows;
- retain exact micro-DK/rational fields, completion/root/outcome identities,
  arrays, and authority flags from the producer contract; and
- keep `synthetic-fixture` plus “fixture construction did not read outcomes”
  in a separate UI evidence wrapper. Do not make the governed report claim
  outcome blindness merely because its displayed values are synthetic.

### 2. Make the projection contract schema-accurate and deeply guarded

`SourceProjectionReceipt` in `frontend/src/api/types.ts` does not mirror the
v2 receipt produced by
`src/nfl_dfs/research/corpus_strategy_registry.py`. The guard in
`frontend/src/api/guards.ts` currently accepts nested source/query receipts as
generic objects. Malformed payloads can therefore classify as ready and then
fail when `CorpusResearch.tsx` dereferences missing fields.

Required correction:

- model every required v2 source-receipt authority and outcome field;
- validate the full nested status, source receipt, query receipt, view rows,
  identities, reason codes, query names, and row counts;
- enforce cross-object bindings among required views, query receipts, source
  identities, and projection identities;
- classify malformed nested data as `schema-mismatch` before rendering;
- add adversarial mutation tests for missing/mistyped nested fields,
  mismatched names/counts/identities, and malformed rows; and
- browser-side cryptographic hash recomputation may remain out of scope, but
  the browser must never imply it performed that verification.

## Required wording and scope corrections

- Relabel the current UI as a **table/foundation slice**, not full Corpus
  Research parity. The legacy page still owns interactive heatmap, paired
  chart, coverage/diversity scatter, promotion timeline, lineage, network
  controls, and named scenarios. Keep the legacy route intact through the
  later visualization and route-parity gates.
- Distinguish transport/network failure from schema mismatch. Preserve both
  partial and stale truth when they coexist rather than allowing stale state
  to hide missing views.
- Derive evidence tier per displayed product or section; do not hard-code a
  page-wide tier that could mislabel mixed evidence.
- Correct the checkpoint report's proposed route snippet before later use
  (`_Path` is undefined), and do not add the route until nested wheel assets
  are packaged and tested.
- Add pagination or virtualization before any endpoint can expose the full
  100,000-row cap. Do not render the cap directly into the DOM.
- Accessibility, keyboard, responsive, deep-refresh, and base-path claims
  require corresponding tests before acceptance.

## Validation required for the corrective commit

Run serially and report exact results:

1. `npm run typecheck`
2. `npm test`
3. `npm run build`
4. a clean-lock reproduction using `npm ci` followed by the project check
5. the focused offline Python Corpus Research UI contract test
6. `git diff --check`

No new chart/router dependency is authorized at this checkpoint. No live
graph, cloud, outcome, IAM, or deployment action is authorized.

## Phase 3 authorization after correction

Once the corrective commit is clean, pushed, and its evidence packet is
updated, the assistant may implement only fixture-backed bounded GET APIs and
offline graph projection/contracts under the original workstream plan. The
next lead checkpoint remains mandatory before any integration switch, live
Neo4j operation, governed artifact read, or deployment.
