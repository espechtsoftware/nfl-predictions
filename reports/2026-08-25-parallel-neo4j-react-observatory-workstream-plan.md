# Parallel Neo4j and React Research Observatory Workstream Plan

**Date:** 2026-08-25

**Status:** ready to delegate after the execution-isolation gate in Section
6.1; implementation is intentionally separated from the active T230/Core/R6
scoring chain

**Primary objective:** let a second assistant build the research observatory in
parallel without delaying, changing, or endangering the first historical
scores

## 1. Executive decision

Yes, a second assistant would be helpful now. The best parallel assignment is
the Neo4j research projection, its bounded read API, and the compiled React
application that visualizes Foundry evidence.

This work is useful because it has a large, well-defined surface that is mostly
independent of the active computation path. It is also risky if it is allowed
to overlap that path. The delegated assistant therefore owns an **offline,
read-only observatory workstream**. The lead assistant continues to own:

- the frozen 54-slate/T230 execution;
- Core historical scoring and outcome control;
- the corrected R6 matchup-source seam;
- changes to lineup generation, admission, retrieval, or evaluation logic;
- cloud execution, production releases, and activation decisions; and
- the authoritative `HANDOFF.md` integration on the live branch.

The plan may be shared immediately. The delegated assistant may begin only
after the execution-isolation gate in Section 6.1 is satisfied, and its first
assignment stops after Phase 2. Later phases require the checkpoints described
below. It must always stop for lead review before provisioning a live graph,
loading cloud evidence, changing an application deployment, or removing any
legacy UI.

This separation preserves the fastest route to actual historical scores. The
observatory consumes accepted evidence after it exists; it is not on the
critical path that produces the evidence.

## 2. What the finished capability should provide

The finished system should let us answer, with exact release identity and
without relying on memory or prose notes:

1. Which fill preset created each corpus and why?
2. Which admission preset decided what was eligible for selection?
3. Which retrieval preset selected the submitted or evaluated book?
4. Which exact combination of fill, admission, retrieval, entry budget,
   science release, sources, and fallback rules constituted a strategy?
5. How did otherwise-comparable strategies perform by slate, season, fold,
   score threshold, realized result, and uncertainty?
6. Which lineup traits were enriched among Millionaire Maker winners,
   simulated high scorers, realized high scorers, and selected portfolios?
7. Which players, pairs, team/game structures, boom traits, coverage/matchup
   traits, ownership traits, and correlation structures recur in the useful
   tails?
8. Why was a particular lineup generated, admitted, selected, or rejected?
9. Are apparent improvements robust across held-out slates, or are they only
   retrospective/exploratory associations?
10. Which source gaps, unknown classifications, small samples, or stale
    projections weaken a conclusion?

The product must support aggressive experimentation while remaining honest
about evidence. It should make it easy to discover a promising strategy, but
it must never silently promote one or describe a retrospective association as
a proven forward-looking edge.

## 3. Architectural boundary

The observatory is a rebuildable read model, not a second source of truth and
not a control plane.

```text
 immutable GCS receipts/artifacts        governed BigQuery facts
                 |                                |
                 +------------+-------------------+
                              |
                    release-bound projector
                              |
              +---------------+----------------+
              |                                |
      dedicated Neo4j namespace       immutable UI projection
       compact relationships          / cached fallback release
              |                                |
              +-----------+--------------------+
                          |
                 bounded FastAPI reads
                          |
                 React research UI
```

The direction is one way. Nothing in React, FastAPI, or Neo4j may:

- launch a Foundry run;
- modify a fill, admission, or retrieval preset;
- change an active strategy pointer;
- acquire an outcome lease or unblind outcomes;
- write to the authoritative evidence buckets;
- change production allocation; or
- substitute graph contents for an immutable source receipt.

Immutable accepted GCS evidence remains content-authoritative. BigQuery is the
operational fact/query layer. Neo4j is a release-bound relationship
projection. A graph release must be disposable and deterministically
rebuildable from its exact inputs.

## 4. The experiment model the graph must represent

### 4.1 Keep corpus population and corpus selection separate

The model must preserve three distinct decisions:

1. **FillPreset** — how candidates are created and placed into a corpus.
2. **AdmissionPreset** — which corpus members are eligible for a book and any
   gating, deduplication, quota, or feasibility law applied before retrieval.
3. **RetrievalPreset** — how an entry-budget-sized portfolio is selected from
   admitted candidates.

A **StrategyBundle** binds immutable versions of all three plus the entry
budget, integer sleeves, fallbacks, required sources, science release, and
verifier release. This is the unit that an evaluation compares and a later
promotion decision may consider.

```text
FillPreset ------> CorpusSnapshot
                        |
AdmissionPreset -> CandidateSnapshot
                        |
RetrievalPreset -> SelectedBook
                        |
                        v
                  Evaluation / MetricSet
```

Do not collapse these stages into a generic `strategy_name`. We need to learn
whether an improvement came from populating a better corpus, admitting a
better candidate set, retrieving a better portfolio, or an interaction among
them.

### 4.2 Core graph entities

The target graph vocabulary is:

- `Slate`, `Contest`, `SlateSnapshot`, `PlayerSlate`, `TeamSlate`, `Game`;
- `WorldRelease`, `CorpusSnapshot`, `CandidateSnapshot`, `Lineup`,
  `SelectedBook`;
- `ScienceRelease`, `VerifierRelease`, `DeploymentAttestation`;
- `FillPreset`, `AdmissionPreset`, `RetrievalPreset`, `StrategyBundle`;
- `ExperimentRun`, `ExperimentCell`, `Evaluation`, `Fold`, `MetricSet`;
- `Trait`, `Cohort`, `WinnerRelease`, `WinnerObservation`, `OutcomeRelease`,
  `OutcomeGrade`;
- `SourceArtifact`, `VerificationReceipt`, `Attempt`; and
- `PromotionDecision`.

Important relationships include:

- `DERIVED_FROM`, `USES_SOURCE`, `USES_WORLD_RELEASE`;
- `GENERATED_BY`, `SUPPLIED_BY_ARM`, `MEMBER_OF_CORPUS`;
- `CONTAINS_PLAYER`, `PLAYS_FOR`, `IN_GAME`;
- `HAS_TRAIT`, `MEMBER_OF_COHORT`;
- `ADMITTED_BY`, `SELECTED_BY`, `MEMBER_OF_BOOK`;
- `EVALUATED_IN`, `HAS_METRIC`, `PAIRED_AGAINST`;
- `GRADED_IN_CONTEST`, `DERIVED_FROM_OUTCOME`;
- `OBSERVED_IN_WINNER_RELEASE`, `EVALUATES_BUNDLE`;
- `RETRIED_AS`, `VERIFIED_BY`, `DECIDES_ON_BUNDLE`; and
- `HAS_INFERRED_DEFENDER_EXPOSURE`.

Never create a factual `COVERED_BY` relationship from an inferred matchup.
Inferred defender involvement must remain explicitly qualified and visually
distinct from a sourced direct assignment.

### 4.3 Traits and comparisons

Traits should be versioned definitions, not unlabelled booleans. At minimum,
support these families when authoritative producers become available:

- boom classification and its component evidence;
- receiver role and alignment;
- team/game topology, stacks, bring-backs, and positional construction;
- salary and ownership structure;
- player, pair, team, and game correlation;
- projected and realized scoring distribution features;
- defense-versus-role and coverage/matchup features;
- source completeness and inference status; and
- portfolio overlap, event exposure, and outcome-space redundancy.

Each comparison must carry the cohort definition, denominator, missing count,
fold, evidence class, release identity, uncertainty/support, and exact metric
definition. Missing values are never converted to zero.

## 5. Current repository state

The delegated assistant is extending a meaningful foundation, not starting
from scratch.

### 5.1 Existing Neo4j and projection foundation

Relevant implementation already exists in:

- `src/nfl_dfs/research/corpus_retrieval_neo4j.py`;
- `src/nfl_dfs/research/corpus_neo4j_extensions.py`;
- `src/nfl_dfs/research/corpus_neo4j_transport.py`;
- `src/nfl_dfs/research/corpus_research_ui_bridge.py`;
- `src/nfl_dfs/research/corpus_strategy_registry.py`;
- `cypher/corpus_retrieval_neo4j_schema.cypher`;
- `cypher/corpus_retrieval_analysis_queries.cypher`; and
- the corresponding loader/transport CLIs and focused tests.

The transport already establishes important principles: exact-generation
source reads, deployment/TLS/principal binding, allowlisted namespaces,
idempotent load receipts, compact analytics, and a terminal census. It does
not make Neo4j authoritative and does not put world matrices or raw outcomes
in the graph.

The present Cypher storage layer is deliberately generic: nodes use the
`CorpusRetrievalEntity` label and relationships use `CORPUS_RELATION`. A
guarded `append_population_phenotypes` builder exists, but population is not
wired through the governed transport manifest, plan, receipts, CLI, query
catalog, or UI. Retrieval/parametric projection support should not be mistaken
for an end-to-end population-intelligence release.

The current strategy registry is also narrower than the target model. It is
primarily a v12-era seven-fill, one-exact-80-retrieval, three-lineup sample. It
does not yet model all of `AdmissionPreset`, `ExperimentManifest`,
`ExperimentCell`, `Evaluation`, `StrategyBundle`, `SelectedBook`, `Fold`, and
the needed terminal release identities. Those are explicit vNext additions,
not facts that may be inferred from the existing registry.

The current foundation is described in
`reports/2026-08-21-corpus-research-neo4j-foundation.md`. It is an offline,
focused-green foundation. It does **not** prove that a live Neo4j endpoint,
secret, complete release load, capacity choice, or production graph pointer
exists.

### 5.2 Existing API and UI

- `src/nfl_dfs/app/corpus_research.py` provides a receipt-bound, read-only
  projection contract and the `/corpus-research`,
  `/api/corpus-research/status`, and `/api/corpus-research/projection` routes.
- `src/nfl_dfs/app/static/corpus_research.js` is a sizeable React 18 UMD + HTM
  compatibility page mounted into server-generated HTML.
- `src/nfl_dfs/app/static/corpus_research.css` and vendored React/HTM assets
  support that compatibility page.
- `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, and `index.html`
  establish a React 19/TypeScript/Vite target, but there is currently no
  `frontend/src/` implementation and no committed `package-lock.json`.
- `src/nfl_dfs/app/main.py` still serves several server-generated application
  routes. React route/action parity has not been established.
- Vite currently emits nested assets below
  `src/nfl_dfs/app/static/app/`, while `pyproject.toml` has not yet proved those
  nested files are included in a built package.
- No current application Dockerfile contains a frontend build stage; copying
  `src/` is not proof of a reproducible React build.

Therefore, “React replacement complete” and “Neo4j operational” would both be
incorrect descriptions of the present state.

### 5.3 Governing design

The deeper requirements remain in Workstreams L and M of
`reports/2026-08-24-foundry-completion-and-rapid-experimentation-implementation-plan.md`.
This plan turns those requirements into a parallel implementation assignment;
it does not weaken them.

## 6. Isolation and file ownership

### 6.1 Hard execution-isolation gate

`CLAUDE.md` records repeated local `HYPERVISOR_ERROR` crashes and therefore
forbids parallel local agents, parallel pytest, and local simulations. Git
isolation does not override that compute-safety law.

The delegated assistant may start under exactly one of these conditions:

1. it has a separate machine or genuinely separate remote execution
   environment and a separate clone, with no shared writable worktree; or
2. the lead assistant has paused local work and explicitly handed the local
   workstation to the delegated assistant as its sole active agent.

A second VS Code window, process, terminal, Git branch, or worktree on this
same workstation is **not** sufficient. On this workstation, do not run two
agents at once even if both tasks seem light, and never overlap npm, pytest,
or other local builds. Cloud jobs may continue remotely, but only one local
agent operates and monitors them.

If separate compute is unavailable, queue this plan and execute it serially
after the lead announces the local handoff point. This affects timing, not the
value or architecture of the workstream.

### 6.2 Work in a separate clone or worktree

Do not work in the lead assistant's dirty live worktree. At the start of the
assignment:

1. fetch without changing the live branch;
2. create a dedicated branch and worktree from the exact lead-approved
   `origin/main` commit;
3. record that base commit in the workstream log; and
4. keep commits narrowly scoped so the lead can review or cherry-pick them.

The lead may advance `origin/main` while a cloud release completes, so the
delegated assistant must obtain and record the approved base commit immediately
before creating the clone/worktree. Do not assume a hash quoted in an earlier
chat or report is still current.

Suggested branch name:

```text
feature/neo4j-react-observatory
```

### 6.3 Files the delegated assistant may own

Through the first mandatory checkpoint, the safe ownership set is intentionally
narrow:

- `frontend/**`;
- generated compiled assets only under
  `src/nfl_dfs/app/static/app/**` in the isolated clone/worktree; they may not
  overwrite another static subtree and are not proof of package inclusion;
- new fixture and frontend test files;
- a proposal or new module for observatory read models that does not alter the
  existing API router; and
- a dedicated workstream progress/report file.

After the Phase 2 lead checkpoint, ownership may expand one reviewed commit at
a time to:

- new `src/nfl_dfs/app/foundry_api.py` and
  `src/nfl_dfs/app/foundry_read_models.py` modules;
- a minimal reviewed router seam in the existing app;
- new graph-vNext contract/adapter modules and focused tests;
- existing Neo4j extension/transport/query files only for the separately
  reviewed population-v3 wiring phase;
- application packaging files only in the packaging phase; and
- existing compatibility UI files only at a final, reversible cutover.

Changes to a listed existing file are not automatically correct; they still
require contract preservation and focused tests.

### 6.4 Files and systems that are out of scope

The delegated assistant must not edit or operate:

- `cloudbuild.foundry-t230.yaml`;
- `Dockerfile.foundry-t230`;
- the active T230, G0, panel, or scoring run directories;
- `scripts/cloud_core_v1_score_chain.sh` or its tests;
- `src/nfl_dfs/research/corpus_r6_matchup_source_v1.py` or its tests;
- active Foundry environment scripts;
- `Dockerfile.corpus-research-expansion` and
  `cloudbuild.corpus-research-expansion.yaml` during the initial parallel
  assignment;
- current graph transport and registry modules during Phases 0–2;
- frozen evaluation manifests, catalog identities, books, or outcome leases;
- Cloud Run jobs, Cloud Build releases, production graph pointers, IAM,
  Secret Manager, BigQuery outcomes, or GCS authoritative artifacts; or
- any live deployment.

Do not perform an IAM census. Do not inspect or expose secret values. Do not
load governed outcomes merely to make a UI fixture realistic.

Because `HANDOFF.md` is authoritative, progress may not live only in chat or a
workstream report. At every material milestone and before every pause, the
delegated assistant must add a clearly labeled Neo4j/React workstream update
to the tracked `HANDOFF.md` on its own branch, commit it with the associated
work, and push whenever possible. It must also send the lead the exact
branch/commit, validations, unresolved risks, and next action. The lead will
reconcile that chronological handoff section when integrating the branch;
neither assistant edits the other's live worktree.

## 7. Work phases

Each phase ends with a commit and a reviewable evidence summary. Do not begin a
live-infrastructure action simply because an earlier offline phase passes.

### Phase 0 — Contract inventory and parity map

Read `README.md`, `CLAUDE.md`, `HANDOFF.md`, the foundation report, and
Workstreams L/M of the 2026-08-24 implementation plan. Then produce:

- a route/action inventory for Season, Lineups, Defense, Market, Watchlist,
  About, Corpus Research, Classic, Showdown, downloads, and navigation;
- a current API/projection schema inventory;
- a Neo4j node/relationship/query inventory;
- an explicit list of fixture-only, accepted, absent, and gated data;
- a list of current packaging/deployment seams; and
- a small decision record for the frontend routing approach and charting
  library.

Do not infer that a route or graph family works because a source file exists.
Record the focused test or fixture that proves each capability.

**Exit:** parity matrix and contract map reviewed by the lead; no production
code needs to change in this phase.

### Phase 1 — Reproducible React foundation

Complete the existing React 19/TypeScript/Vite scaffold:

- create `frontend/src/` with an application entry point, router, page shell,
  error boundary, shared loading/empty/error/stale states, and test setup;
- generate and commit `frontend/package-lock.json` from the pinned manifest;
- keep exactly one React/runtime version in the compiled application;
- create strict TypeScript response types or generated schemas for the
  existing corpus-research status/projection API;
- add deterministic fixture payloads representing ready, loading, empty,
  partial, stale, degraded, unauthorized, and schema-mismatch states;
- preserve Vite base `/static/app/` and output under
  `src/nfl_dfs/app/static/app`;
- test deep-route asset resolution and production base paths; and
- document the exact Node/npm versions used for the lock and build.

Add a synthetic, schema-accurate fixture for the eventual
`core-v1-human-readable-grade-report/v1` product input. This is the safest
initial score contract: it can represent the frozen 12 strategies, entry
budgets 4/14/80, score thresholds 180/194/200/210/220/230/240/250, book
max/mean/median, threshold hits, C-S conversion gap, paired weekly/season
deltas, and leave-one-out sensitivity. Contest rank, duplication, payout, and
ROI remain explicitly unavailable until complete field/payout evidence exists.

The product lane may use synthetic report fixtures now. Later it may consume
only a custodian-supplied, terminal accepted report/materialization identity.
It must never call the Core outcome reader, acquire an outcome lease, or read a
grade work directory directly.

The charting choice must be pinned, React-19 compatible, accessible, testable,
and justified for bundle size. If that cannot be established offline, build
the page structure and tables first and leave the additional dependency for a
lead-reviewed follow-up. Do not mix another React UMD runtime into the new
bundle.

**Exit:** from a clean checkout, `npm ci`, typecheck, unit tests, and the
production build are reproducible; compiled assets exist without requiring a
Node runtime in the Python application container.

### Phase 2 — Corpus Research parity as the first React slice

Reimplement the current Corpus Research page first because it already has a
bounded read-only projection contract and directly supports Foundry research.

Required first-slice behavior:

- readiness and current-authority banner;
- exact source/graph/UI release identity and staleness;
- preset registry and fill/admission/retrieval distinction;
- strategy lineage;
- paired held-out fill/retrieval comparison;
- lineup-player-team-game traversal;
- registry firewall/census status;
- loading, empty, partial, stale, degraded, error, and unauthorized states;
- persistent evidence badges; and
- links back to sanitized provenance metadata rather than raw bucket paths.

Keep the React 18/HTM page and server route as a fallback. Before the mandatory
checkpoint, do not edit the FastAPI route or existing compatibility assets.
Deliver the compiled page plus a minimal proposed reversible integration diff
in the workstream report. Route/feature-switch integration happens only after
lead review. Do not delete or overwrite the fallback.

**Exit:** fixture values render exactly, existing projection validation remains
green, keyboard/responsive behavior is covered, and switching back to the
compatibility page is trivial.

**Mandatory lead checkpoint:** stop here and send a review packet before
changing backend contracts or broadening route ownership.

### Phase 3 — Versioned, bounded Foundry read API

After lead approval, add a `/api/v1/foundry` read model. Prefer small Pydantic
schemas, a repository/projection protocol, and fixture-backed contract tests
over coupling route handlers directly to a Neo4j driver.

Prioritized endpoints are:

- `/api/v1/foundry/status`;
- `/api/v1/foundry/releases`;
- `/api/v1/foundry/presets`;
- `/api/v1/foundry/strategy-bundles`;
- `/api/v1/foundry/experiments` and `/experiments/{id}/metrics`;
- `/api/v1/foundry/runs` and `/evaluations`;
- `/api/v1/foundry/books/{id}`;
- `/api/v1/foundry/cohorts/compare`;
- `/api/v1/foundry/traits/enrichment`;
- `/api/v1/foundry/slates/{slate}/lineups/{lineup}`;
- `/api/v1/foundry/lineup-network`;
- `/api/v1/foundry/source-coverage`; and
- `/api/v1/foundry/receipts/{id}`.

Every successful response must include:

- API schema/version and response type;
- data, graph, and UI release identity as applicable;
- winner-release identity whenever a winner cohort or denominator appears;
- generation time, verified time, age, and staleness state;
- evidence tier/authority and simulated-versus-realized scope;
- discovery/evaluation fold;
- denominator, missingness, and uncertainty/support;
- exact metric definition; and
- sanitized source/provenance references.

Enforce parameterized catalogued queries, cursor pagination, row/byte/time
limits, bounded filters, ETag/content-hash caching, and response-size tests.
Reject arbitrary Cypher. `/receipts/{id}` returns only allowlisted sanitized
metadata, never a raw receipt body. The API must remain healthy and visibly
degraded when Neo4j is absent.

**Exit:** OpenAPI/contract tests are frozen, query parameters are bounded, no
write path exists, and old `/api/corpus-research/*` consumers still work.

### Phase 4 — Extend the Neo4j release projection offline

Build adapters from accepted fixture receipts into the graph vocabulary. Start
summary-only; do not assume a full-lineup graph is affordable.

Required work:

1. Version schema and constraint migrations.
2. Extend the allowlisted query catalog for strategy decomposition, funnel,
   lineage, traits, cohorts, matchups, networks, source quality, and promotion
   evidence gaps.
3. Define a deployment/load manifest binding the exact predecessor graph
   release, allowed namespaces, schema version, source releases, and outcome
   scope.
4. Stream deterministic batched `UNWIND` transactions rather than building a
   full in-memory load plan.
5. Make identical reloads idempotent and conflicting identities fail closed.
6. Produce checkpoint receipts and a terminal node/edge/property/namespace
   census.
7. Create canonical query fixtures and expected content hashes.
8. Prove a zero-state rebuild produces the same census and query hashes.
9. Preserve source pointers as exact immutable identities; never follow a
   mutable “latest” pointer while building a graph release.
10. Keep the `realized` namespace closed unless an authorized accepted
    `OutcomeRelease` is explicitly supplied later by the lead.

T230, Core, and R6 adapters should initially accept terminal identity-bound
fixtures or an injected source protocol. Do not read live work-in-progress
run directories or invent terminal evidence while those chains are active.

The cleanest first graph backlog is population-v3 wiring: connect the existing
guarded population phenotype builder to a versioned load manifest, deterministic
plan, per-task/terminal receipts, CLI, bounded queries, and UI read model. Do
this only after the lead checkpoint and in a separate commit from schema/model
expansion so its authorization and outcome firewall can be reviewed clearly.

**Exit:** offline fixture load/reload/rebuild and canonical query results pass;
there is still no live graph write.

### Phase 5 — Capacity decision and graph mode

Before a live graph is provisioned, create a capacity estimator and a signed
capacity receipt for one of two honest modes:

- **full-lineup release:** every declared accepted lineup, nine bounded
  lineup-player relationships per lineup, compact features, sparse
  cohort/trait membership, and selected/admitted relationships; or
- **summary-only release:** strategy/run/book/cohort/trait aggregates and
  selected-lineup details, with full-corpus traversal explicitly unavailable.

The estimator must use real accepted release counts supplied by the lead, not
task-0 or three-lineup fixtures. Pre-register:

- node, relationship, and property counts;
- estimated and observed bytes;
- heap/disk safety fractions;
- batch size and load deadline;
- zero-state rebuild deadline;
- canonical query p50/p95 budgets; and
- the threshold that forces summary-only mode.

Never label a partial graph “full.” World matrices, per-world graph nodes, and
dense quadratic pair networks remain outside Neo4j in both modes.

**Exit:** lead approves full-lineup or summary-only mode from the capacity
receipt. No provisioning happens within this phase.

### Phase 6 — Research visualizations

Build the following views against versioned fixture/API contracts:

1. **Readiness:** accepted slates, missing cells, verifier status, outcome
   readiness, graph/UI release, stale age, and current authority.
2. **Experiment matrix:** fill × admission × retrieval heatmap, filterable by
   metric, fold, season, entry budget, and evidence class.
3. **Paired outcomes:** per-slate deltas, win/tie/loss counts, season summary,
   influence, and uncertainty.
4. **Tail curves:** thresholds 187–240, expected maximum, and contest-relative
   metrics without describing 194 as a win probability.
5. **Candidate funnel:** generated/visited → unique → admitted → selected →
   realized thresholds.
6. **Decomposition:** main effects and interactions for fill, admission, and
   retrieval, including C, S, and C-S where defined.
7. **Cohort comparison:** winners, matched controls, simulated tail, realized
   corpus tail, and selected books with denominators.
8. **Trait explorer:** boom, topology, role, matchup, coverage, ownership,
   salary, pairs/correlation, missingness, and support.
9. **Lineup detail:** roster, salary, provenance, source arms, simulated
   distribution, annotations, selection trace, and authorized outcome.
10. **Matchups:** defense-versus-role map, lineup matchup strip, inferred
    defender involvement, source grain, and unknowns.
11. **Portfolio structure:** score/event clusters, roster overlap, exposures,
    and effective rank.
12. **Strategy lineage:** preset → experiment → snapshot → book → grade →
    decision.
13. **Source quality:** completeness by slate, season, source, grain, and
    temporal eligibility.
14. **Contest outcomes:** rank, duplication, payout, and ROI only when complete
    and authorized.

All charts must show denominator and source release. Simulated, realized,
exploratory, retrospective, held-out, prospective, limited-deployment, and
promoted evidence get persistent distinct labels. Unknown or missing is shown
as unknown or partial, never zero. Small samples and unstable effects show
support/uncertainty. Inferred coverage relationships use qualified labels and
dashed styling.

**Exit:** chart values reconcile exactly to fixtures/API payloads, evidence
labels survive navigation and filtering, and partial/missing states cannot be
mistaken for negative results.

### Phase 7 — Route parity and reversible React cutover

Migrate the remaining application routes one bounded slice at a time:

- Season;
- Lineups;
- Defense;
- Market;
- Watchlist;
- About;
- live Classic and Showdown construction;
- downloads and optimizer-service actions; and
- navigation, errors, and deep-route refresh.

For every slice, record existing inputs/actions, create contract tests, build
the React equivalent, run side-by-side parity, and retain a rollback. Do not
remove server-rendered or vendored compatibility assets until every current
route/action—including downloads and optimizer behavior—has a tested
equivalent and the lead approves removal. `/docs` remains FastAPI's API
documentation route.

**Exit:** route/action parity matrix is fully green, deep refresh and static
base paths work, responsive/browser smoke passes, and rollback is tested.

### Phase 8 — Offline packaging and release rehearsal

Add the frontend build only to the web application image/build path:

- deterministic Node build stage;
- copy compiled assets into the Python application artifact;
- no Node runtime in production;
- wheel/container test proves declared compiled assets are present;
- app starts when Neo4j is unavailable;
- last verified projection and age remain visible during graph failure;
- invalid/newer unverified projections are rejected; and
- rollback selects the previous verified UI release.

Do not modify the Foundry worker or verifier image. UI changes must not trigger
a science-worker rebuild.

**Exit:** local/offline image rehearsal and artifact inventory pass. Stop
before pushing an image or changing a service.

## 8. Live deployment gate

The delegated assistant must stop and obtain explicit lead approval before any
of the following:

- provisioning a dedicated Neo4j instance/database;
- creating or changing network access, TLS, principals, secrets, or IAM;
- reading accepted cloud evidence for a real load;
- opening a realized/outcome namespace;
- publishing or activating a graph/UI release pointer;
- building or deploying a production application image;
- changing Cloud Run configuration;
- deleting legacy UI assets; or
- adding any mutation/control endpoint.

At that gate the lead will supply exact accepted evidence identities and decide
whether current scoring work is sufficiently frozen to integrate the branch.

If approved later, the live design uses a dedicated corpus-research graph with
separate bootstrap, loader, and reader identities, TLS, blue/green release
namespaces, an immutable activation receipt, and canonical query-hash
comparison before pointer movement. The application reader cannot write; the
loader cannot activate production policy.

## 9. Validation protocol

Follow repository compute safety: run one pytest module at a time. Do not run
the entire repository suite merely to validate this workstream.

Python modules should be run individually as relevant, for example:

```text
pytest -q tests/test_corpus_retrieval_neo4j.py
pytest -q tests/test_corpus_neo4j_transport.py
pytest -q tests/test_corpus_research_ui_bridge.py
pytest -q tests/test_corpus_research_ui.py
pytest -q tests/test_corpus_expansion_build.py
pytest -q tests/test_foundry_api_v1.py
```

The final filename is illustrative until the new API test is added. New test
modules also run one at a time.

Frontend validation from `frontend/` is:

```text
npm ci
npm run typecheck
npm test
npm run build
```

Also require:

- build from a clean checkout using the committed lock;
- fixture-to-chart numeric reconciliation;
- OpenAPI/schema compatibility tests;
- pagination/row/byte/time-limit tests;
- forbidden Cypher and write-query rejection tests;
- identical graph reload/idempotence tests;
- conflicting identity rejection tests;
- zero-state rebuild census/query-hash tests;
- app-without-Neo4j degradation test;
- static asset/wheel/container inventory test;
- deep-route refresh and base-URL test;
- accessibility checks for tables, charts, focus order, and non-color labels;
  and
- whitespace/diff checks before each commit.

Do not claim a live integration test passed when only an injected runner,
fixture, or mocked graph was exercised. Label each validation level exactly.

## 10. Deliverables

The delegated workstream should produce:

1. route/action/API/graph parity and gap inventory;
2. committed React 19/TypeScript source and `package-lock.json`;
3. typed API contracts, fixtures, and component tests;
4. React Corpus Research parity with a reversible fallback;
5. versioned bounded `/api/v1/foundry` read endpoints;
6. versioned Neo4j schema, constraints, projection adapter, and query catalog;
7. graph capacity estimator and full-versus-summary decision receipt;
8. the required research views and persistent evidence labels;
9. deterministic graph rebuild and canonical query-hash evidence;
10. web-app-only packaging and offline release rehearsal;
11. a concise operator/readme update; and
12. a handoff packet with branch/commits, validation output, assumptions,
    blockers, and exact next action.

No deliverable is “production deployed” until the live deployment gate is
separately authorized and completed.

## 11. Overall acceptance criteria

This workstream is acceptable when:

- it has no diff in the active T230/Core/R6 science or operator paths;
- corpus fill, admission, and retrieval remain distinct versioned concepts;
- every displayed result resolves to exact accepted source identity;
- graph contents are deterministically rebuildable and non-authoritative;
- no world matrix, raw licensed row, raw outcome body, credential, or mutable
  policy pointer appears in graph properties or browser payloads;
- arbitrary Cypher and graph writes are impossible through the application;
- the application remains available and honestly degraded without Neo4j;
- all results expose denominator, missingness, evidence class, fold, and
  release identity;
- historical/exploratory evidence is visibly distinct from held-out or
  prospective evidence;
- React is reproducibly built from one pinned runtime and ships without Node;
- every migrated route/action has parity and rollback evidence;
- the first-score path was never blocked on the graph or UI; and
- the lead can integrate each phase as a small, reviewable commit series.

## 12. Immediate assignment for the second assistant

The recommended initial assignment is deliberately bounded:

1. Satisfy the hard execution-isolation gate: use a separate machine/remote
   clone, or wait for an explicit exclusive local handoff.
2. Create an isolated clone/worktree from the lead-confirmed `origin/main`
   commit.
3. Complete Phase 0 and commit the parity/contract inventory.
4. Complete Phase 1's reproducible React foundation.
5. Complete Phase 2's fixture-backed Corpus Research React parity while
   preserving the existing compatibility page.
6. Run only the relevant sequential Python modules and frontend checks.
7. Update and commit the branch's tracked `HANDOFF.md`.
8. Send the lead a review packet and **stop at the Phase 2 checkpoint**.

This produces useful visible progress quickly, tests the frontend deployment
assumption that previously caused difficulty, and avoids guessing at backend
contracts before the current T230/Core evidence has terminal identities.

After lead acceptance, the same assistant can proceed through the API,
offline graph projection, capacity decision, deeper visualizations, route
parity, and offline packaging phases. Live graph provisioning and deployment
remain a separate explicit decision.

## 13. Required progress report format

At every material milestone or pause, report:

```text
Workstream: Neo4j/React observatory
Base commit:
Branch and latest commit:
Phase completed:
Files changed:
Validations run, one module/command at a time:
Fixture/offline/live level of each validation:
Authoritative identities consumed (if any):
Material assumptions:
Unresolved risks/blockers:
Files intentionally not touched:
Next concrete action:
Lead approval required before next action: yes/no, with reason
```

Never leave a critical decision, source identity, test result, or blocker only
in chat or a temporary file.

## 14. Stop conditions

Stop, preserve the branch, and report to the lead if:

- the required change crosses into an active T230/Core/R6 file;
- a source artifact lacks an immutable identity or terminal acceptance;
- a fixture would require governed outcomes to be accessed;
- graph capacity cannot be honestly classified as full or summary-only;
- React parity requires changing live optimizer behavior;
- package installation or build requires an unreviewed dependency/version
  change;
- an API response cannot expose its denominator, missingness, or provenance;
- a requested action would write to cloud infrastructure or production; or
- the worktree base conflicts materially with new lead commits.

These are coordination gates, not reasons to abandon the work. Preserve the
smallest completed, independently reviewable increment and hand it back.
