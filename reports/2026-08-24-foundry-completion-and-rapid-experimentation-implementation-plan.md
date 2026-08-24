# Foundry completion, simplification, and rapid-experimentation implementation plan

**Date:** 2026-08-24
**Status:** implementation-ready plan; execution begins only after both active
v12 lanes have reached their terminal, independently verified batch state
**Primary objective:** turn the current Foundry foundation into a reusable
system that can rapidly compare how the corpus is populated and how an
exact-size tournament portfolio is selected, while preserving trustworthy
point-in-time, held-out, and promotion boundaries
**Decision authority:** this document authorizes no change to the active v12
run, no realized-outcome read, no production-money-policy change, and no
deletion of existing evidence

## 1. Executive decision

The project should complete the active v12 batch exactly as launched, preserve
it as a replayable baseline, and then make two changes in parallel:

1. **Correct and run the immediate retrieval/evaluation path.** Repair the R6
   adapter before any R6 realized-outcome read, run all registered selectors
   on held-out-safe candidate universes, retain exact books and traces, and
   produce the first complete fill-versus-retrieval comparisons from the
   accepted v12 artifacts.
2. **Replace deployment-per-experiment with release-once/run-by-manifest.**
   Certify stable Foundry science/verifier releases and a renewable deployment
   attestation once. Thereafter, supported fill,
   admission, retrieval, threshold, weight, fold, and entry-budget variations
   must be configuration-only experiments that require no image build, job
   deployment, IAM rewrite, Scheduler census, or source-matrix regeneration.

The scientific work then proceeds on top of that reusable surface:

- score and characterize every available corpus lineup;
- learn from both realized Millionaire Maker winners and simulated/realized
  corpus tails without treating either as a universal template;
- add boom, topology, role, receiver/defender matchup, ownership, duplication,
  and field-relative context as separately testable features and sleeves;
- compare population and retrieval causally through shared snapshots, worlds,
  and budgets;
- retain raw matrices and authoritative facts in GCS/BigQuery;
- project compact relationships, presets, experiments, and metrics into the
  dedicated Neo4j research database;
- expose the full experiment and evidence trail in the React web UI; and
- require outer-fold and prospective evidence before changing live entries.

The intended end state is not a single hard-coded “winner model.” It is a
continuously operating research Foundry in which a new supported hypothesis can
move from a manifest to reproducible comparative results in minutes or hours,
while promotion remains deliberately slower and harder.

## 2. Source documents and reconciliation

This plan consolidates and supersedes the execution sequencing, but not the
scientific findings, in:

- [the offseason fill/selection roadmap](./2026-08-22-offseason-corpus-fill-and-selection-roadmap.md);
- [the Foundry roadmap adaptation](./2026-08-22-foundry-roadmap-adaptation.md);
- [the independent Foundry code review](./2026-08-22-foundry-code-review.md);
- [the R6 preregistration](./2026-08-22-r6-set-level-matchup-retrieval-prereg.md);
- [the receiver/defender matchup implementation plan](./2026-08-22-receiver-defender-matchup-intelligence-implementation-plan.md);
- [the corpus population review](./2026-08-21-corpus-population-review.md);
- [the corpus retrieval-engine report](./2026-08-21-corpus-retrieval-engine-v1.md);
- [the artifact-supported source authority](./2026-08-21-corpus-artifact-supported-source-authority-v1.md); and
- [the legal-feasibility authority](./2026-08-21-corpus-legal-feasibility-authority-v1.md).

Where those documents conflict, this plan makes the following explicit
decisions:

1. v12 remains a **fill-ablation baseline under one fixed selector**, not a
   completed fill-by-retrieval factorial.
2. The current R6 specification/runner pair is **not executable as a valid
   registered result** because the runner omits four required selectors and
   does not make candidate identity held-out-safe. It must receive a formal
   disposition and a corrected, freshly frozen successor before actuals are
   read.

   > **[v12 operator review — 2026-08-24]** Verified in code, all three
   > defects are real: `corpus_batch_retrieval_runner.py` line 250 slices
   > `frozen_retrieval_strategies_v2(80)[4:]` (only the last 3 of 7 laws
   > run); its books dict stores only `book_size`/`admission`/
   > `strategy_sha256` plus coverage aggregates — no selected lineup IDs
   > and no marginal traces; and the union pool applies no candidate-origin
   > mask, so a lineup first generated in the held-out block can enter
   > selection (score columns are sliced to discovery, identities are not).
   > Note the frozen runner already self-labels its output
   > `evidence_tier: "exploratory-pre-comparison"` and
   > `adoption_authority: False`, which supports the "non-executable, not
   > failed" disposition framing. The disposition should also carry forward
   > the R6 prereg's five outcome-blind namespace amendments and its
   > v12a/v12b substrate bindings so the amendment chain stays auditable.
3. A failed frozen evaluation closes that exact strategy/version/dose
   hypothesis on that evaluation set. It does not close exploratory research
   on a whole signal family,
   algorithm family, objective, or materially different cross-fitted design.
4. A 194-point threshold remains a continuity diagnostic. It is not the
   definition of a Millionaire Maker win and must not be the universal
   optimization or promotion objective.
5. Exact implementation and evidence replay remain strict, but scientific
   identity is separated from deployment, IAM, UI, graph, and wrapper identity.
6. Existing v1 artifacts and readers remain immutable and replayable. The
   simplified system is introduced under explicit **Foundry Next** schema IDs
   rather than by rewriting accepted history. Avoid the bare name “Foundry
   v2,” because existing parametric/retrieval schemas already use v2 while the
   active operational batch is v12.

## 3. Hard boundary around the active v12 run

No implementation work in this plan may mutate, rebind, relaunch, or reinterpret
the active v12 lanes. Until both lanes finish:

- do not change their manifests, images, namespaces, service accounts, IAM
  conditions, task ordering, solver options, environment files, or acceptance
  procedures;
- do not launch a replacement producer or verifier for an already consumed
  task;
- do not read R6 realized outcomes or use partial v12 metrics to choose an R6
  correction;
- do not write Neo4j scenario evidence claiming that the panel is complete;
- do not delete or compact any v6-v12 local or GCS evidence; and
- do not mix current-main code into an already bound v12 execution.

### Gate G0 — v12 terminal preservation

Implementation may begin only after the deployment owner has durably recorded:

- both lane manifests and their exact object identities;
- every task’s verifier acceptance or terminal failure;
- for each lane, either its valid completeness-gated finish-batch receipt or
  an immutable terminal non-completion disposition that enumerates every
  accepted, failed, absent, and never-launched task;
- the accepted panel membership and explicit missing-task list, if any;
- immutable identities of all per-arm rosters, score hashes, selected books,
  solver evidence, and verification receipts;
- one combined v12 panel index binding lane A and lane B without altering
  either lane;
- current branch/commit, Cloud Build IDs, image digests, Cloud Run execution
  IDs, and unresolved exceptions in HANDOFF.md; and
- a read-only backup/index sufficient to reconstruct the panel without relying
  on the workstation.

If a lane is incomplete, preserve it honestly. Do not forge a completeness
receipt, substitute slates, or silently weaken the acceptance rule. Foundry
Next may ingest the accepted subset only through the terminal non-completion
disposition, and every report must carry the exact accepted denominator.

> **[v12 operator review — 2026-08-24]** Status at review time: both lanes
> mid-flight and healthy — lane A 17/28 and lane B 16/26 tasks
> VERIFIER-ACCEPTED, zero failures or interventions since fan-out; ETA for
> both terminal states is the early hours of 2026-08-25 UTC. The §3
> boundary is being observed. Ownership handshake for G0: this deployment
> session will produce the per-lane finish-batch receipts (or terminal
> dispositions), the combined panel index, and the HANDOFF terminal
> record; implementing lanes must consume those artifacts, never
> regenerate them.

## 4. Definition of done

Foundry Next is complete only when all of the following are true:

1. A new supported fill or retrieval preset is submitted as a canonical
   manifest; no source edit, image build, Cloud Run job deployment, IAM
   mutation, or Scheduler census occurs.
2. The same manifest and input identities reproduce byte-identical lineup
   identities, score hashes, selected books, and selection traces.
3. A transient platform failure can be retried under an append-only attempt
   ledger without changing scientific identity or discarding valid completed
   shards.
4. Exploratory, preregistered retrospective, genuinely confirmatory reserved/
   prospective, and production-promotion runs have distinct authority flags
   and storage namespaces.
5. Every unique lineup used by an experiment is scored across every registered
   world; missing rows, truncated matrices, and mixed world identities fail
   closed.
6. Held-out evaluation excludes both held-out score columns and candidates
   whose identity was discovered only in the held-out block.
7. Fill comparisons use the same worlds, solve budget, and retrieval policy;
   retrieval comparisons use the same candidate snapshot and entry budget.
8. The complete registered selector suite runs—not an undocumented slice—and
   exact selected identities plus marginal traces are retained.
9. Realized grading is performed only after books are frozen and reports
   lineup score, weekly maximum, threshold ladders, and, when available,
   contest rank, duplication, payout, and ROI.
10. Neo4j can be deleted and rebuilt from authoritative evidence without
    changing results; it cannot authorize runs or production policy.
11. The React UI clearly separates simulated, realized, held-out, exploratory,
    retrospective, confirmatory, limited-deployment, and promoted evidence and
    can explain why each lineup was admitted and selected.
12. No strategy changes live entries without an explicit reviewed Tier-P
    limited-deployment or promotion receipt and operator action.

## 5. Operating model: three authority tiers

| Tier | Permitted data and purpose | Required controls | Explicitly forbidden |
|---|---|---|---|
| **E — exploratory** | Immutable simulated worlds, cached corpus artifacts, and already-viewed development outcomes; rapid hypothesis generation and parameter search | Canonical manifest, deterministic replay, PIT feature contract, complete provenance, legal lineups, development/held-out labels, no-promotion flag | Calling results unbiased confirmation; reading reserved outer/prospective outcomes; changing live policy |
| **V — frozen evaluation** | A frozen nominated suite on retrospective, genuinely reserved historical, or prospective data, with the evidence class stated explicitly | Frozen scientific manifest, candidate-identity-safe folds, equal budgets, multiplicity plan, exact books/traces, one controlled outcome grade | Calling a reused/adaptively studied historical panel confirmatory; post-read tuning, cell substitution, undocumented selector/admission changes, automatic promotion |
| **P — production deployment/promotion** | Pre-lock books, a frozen retrospective risk packet for limited deployment, and later prospective contest outcomes | Full science/verifier evidence, PIT and availability checks, export rehearsal, shadow/incumbent comparison, rollback, explicit limited-deployment/promotion receipt and operator approval | Outcome-driven pre-lock mutation, graph-driven auto-activation, silent fallback |

The historical-outcome lease applies to controlled unblinding in Tier V/P. It
does not serialize Tier E simulation, cached score-matrix analysis, graph/UI
materialization, or already-labeled development work.

Cross-fitting protects a model application from direct row/column leakage; it
does not erase the fact that 2023–2025 slates and outcomes have already shaped
this project. R6-v2 and subsequent 54-slate grades must therefore be labeled
**preregistered retrospective evaluation**, not fresh confirmation. Only a
genuinely untouched historical holdout, if one exists and is documented, or
prospective 2026 pre-lock books can carry confirmatory evidence.

> **[v12 operator review — 2026-08-24]** Consistent with the ledger, and
> worth binding explicitly: system-study Addendum 95's preregistered
> reopening condition licensed a selector revisit only on a genuinely new
> pre-lock signal with evaluation frozen before new outcomes are seen —
> which is exactly what the R6 matchup admission is — while forbidding
> retrospective tuning on the same 107/54 slates as panel mining. This
> plan's "preregistered retrospective, not confirmatory" label is a
> compatible tightening of that condition, not a contradiction. Cite
> Addendum 95 in R6-v2 so the continuity is auditable.

## 6. Target architecture

The target data and control flow is:

    Immutable science + verifier releases
              |
              v
    Canonical experiment manifest ----> immutable source/world identities
              |
              v
    Parallel fill generation or accepted cached super-pool
              |
              v
    Canonical lineup snapshot + score/event sidecars
              |
              +----> admission preset
              |          |
              |          v
              +----> set-level retrieval preset
                         |
                         v
                 exact selected book + marginal trace
                         |
                +--------+---------+
                |                  |
                v                  v
       simulated/cross-fit     outcome grader
          measurements          after freeze
                |                  |
                +--------+---------+
                         v
               immutable accepted evidence in GCS
                         |
               +---------+----------+
               |                    |
               v                    v
       BigQuery fact projection   Neo4j projection
                                      |
                                      v
                                  React UI

Exact Foundry-produced content is authoritative as immutable, content-addressed
GCS JSON/Parquet plus create-once acceptance/release pointers. BigQuery tables,
Neo4j, API materializations, and the UI are release-bound, rebuildable query
projections. Existing source datasets may remain authoritative in BigQuery,
but their generation/snapshot IDs and query/content receipts become immutable
manifest inputs. Neither a query projection nor the UI is a run controller.

## 7. Versioned contracts

### 7.1 Science, verifier, and deployment releases

Introduce three related contracts rather than embedding renewable cloud state
inside scientific identity.

The canonical `foundry-science-release/v1` contains:

- release ID and semantic version;
- source commit and exact hashes of score-affecting engine components only;
- producer image digest;
- Python, solver binary, solver options, and dependency-lock identities;
- supported fill-method, admission-method, retrieval-method, and objective IDs;
- typed parameter schemas and domains for each method;
- source-universe and world-artifact schema versions;
- deterministic seed, ordering, tie-break, canonicalization, and numeric laws;
- real-artifact smoke receipt;
- unit/integration/equivalence test receipts;
- authority flags, including no outcome-read and no production authority; and
- release deprecation/supersession state.

The independently built `foundry-verifier-release/v1` binds verifier code,
image, dependencies, poison/equivalence fixtures, supported science-release
range, and independent-build receipt.

The renewable `foundry-deployment-attestation/v1` binds exact Cloud Run job
UID/spec, producer/verifier/analysis image digests, service accounts, custom
roles, bucket policies, expiry/drift rules, and its bounded infrastructure
audit. A run contract binds this attestation; the experiment’s scientific
digest binds only the science release. The acceptance/evidence identity binds
the compatible verifier release and deployment attestation, so a verifier-only
repair cannot silently change a verdict but also does not redefine unchanged
producer science.

Only a change to score-affecting code, the solver, dependencies, supported
method implementation, or a parameter schema requires a new science release.
Documentation, UI, Neo4j, orchestration wrappers, thresholds already inside a
declared domain, weights, folds, budgets, or preset combinations do not.

### 7.2 Experiment manifest

Introduce a canonical foundry-experiment-manifest/v1 containing:

- experiment ID, tier E/V/P, purpose, owner, and created time;
- science-release and compatible verifier-release identities;
- required deployment-attestation compatibility, bound concretely by the run
  contract rather than the scientific digest;
- exact slate/source/player-universe/world-matrix identities;
- development, discovery, validation, and outer-fold assignments;
- one or more fill presets;
- one or more admissions;
- one or more retrieval presets;
- entry budgets and threshold/objective parameters;
- solver/generation budget and compute ceiling;
- deterministic seeds and task ordering;
- comparison cells and paired baselines;
- outcome-read policy and reserved namespace;
- expected output namespace;
- retry classes and maximum attempts;
- required receipt and metric families;
- predeclared missing-data behavior;
- exploratory/confirmation/promotion authority flags; and
- canonical full-manifest hash plus a scientific-manifest hash that excludes
  verifier/deployment evidence but includes every score/book-affecting field.

The manifest accepts only registered method IDs and typed, bounded values.
Arbitrary environment variables, code snippets, SQL, Cypher, filesystem paths,
or unregistered plugin behavior are rejected.

### 7.3 Attempt and acceptance records

Separate a logical task from physical attempts:

- each attempt has a unique immutable attempt ID and append-only event ledger;
- completed shards are content-addressed and reusable;
- platform failures, preemption, network errors, and worker loss may retry with
  the identical task input and seed;
- solver non-optimality, inconsistent evidence, illegal rosters, input drift,
  or deterministic replay mismatch are scientific failures and never
  auto-retry as though nothing happened;
- no attempt may overwrite a prior object;
- exactly one independently verified result can acquire the task’s accepted
  pointer;
- competing valid attempts must have identical canonical scientific payloads
  and scientific-result digests or the task fails closed; attempt IDs,
  timestamps, heartbeats, infrastructure logs, and receipt envelopes are
  expected to differ; and
- a batch completion binds accepted task pointers, not the absence of failed
  infrastructure attempts.

### 7.4 Semantic identity versus execution identity

The scientific identity includes the science release (and therefore its
producer image), source, worlds, candidate law, objective, parameters, seed,
budgets, admission, retrieval, tie-breaks, and fold assignment. The evidence
identity additionally binds the compatible verifier release and acceptance
receipts. Execution identity includes the deployment attestation, job, service
account, attempt, timestamps, and infrastructure evidence.

All three are retained. An execution or verifier repair may proceed under the
same scientific identity only when an explicit equivalence test proves that
scientific output semantics are unchanged. Otherwise it is a new science
release or experiment.

## 8. Workstream A — close and index v12 without reinterpretation

### A1. Finish both lanes

Use only the existing lane runbooks and accepted recovery procedures. Complete
producer, verifier and task acceptance, then obtain either a valid
completeness-gated finish-batch receipt or an immutable terminal
non-completion disposition for each lane.

### A2. Build a combined read-only panel index

After both lane terminal receipts/dispositions exist, publish one small
create-once index that:

- binds both lane terminal receipt/disposition identities;
- lists every accepted slate exactly once;
- retains original task and lane ordinals;
- records failures and exclusions explicitly;
- binds all seven arm results per accepted task;
- asserts no realized outcome was used;
- carries no promotion authority; and
- does not copy or rewrite the underlying artifacts.

### A3. Preserve diagnostics separately

Keep v6-v11 artifacts as diagnostic evidence. Mark them outside the v12 panel
and prevent registry/UI aggregation from silently mixing them with accepted
v12 tasks.

### A4. Exit criteria

- both lanes are terminal;
- the combined index passes a full exact-read replay;
- accepted slate count equals the union with no duplicate slate identities;
- no object under v12 has been overwritten;
- all v12 result/verification identities remain reachable; and
- HANDOFF.md contains the definitive terminal state and next action.

## 9. Workstream B — correct R6 before any realized read

The current R6 document must be closed with a disposition stating that it could
not be executed as registered. This is not a negative result for matchup
intelligence; it is a protocol/implementation mismatch discovered before the
realized read.

The disposition must enumerate all known blockers: the implemented strategy
slice runs only three of seven laws; held-out-only candidate identities can
enter selection; aggregate output omits exact selected IDs and marginal traces;
and there is no durable CLI, publisher/transport, or completion receipt capable
of freezing the registered books. Preserve the frozen runner and protocol as
evidence—do not edit them into apparent compliance.

### B1. Correct the selector surface

Create a **new versioned batch retrieval runner/command** so that each admitted
candidate universe runs all seven registered laws:

1. coverage-194-v1;
2. strict-200-coverage-v1;
3. tail-ladder-200-210-220-v1;
4. mean-score-v1 negative control;
5. expected-max-v1;
6. block-supported-tail-ladder-v1; and
7. regime-robust-ladder-v1.

The successor must not contain the current strategy slice that runs only the
final three laws. Generate the required strategy list from one registry rather
than duplicating names or counts in runner, tests, preregistration, graph, and
UI code. Leave the legacy runner byte-preserved for replay and disposition.

### B2. Make candidate identities held-out-safe

For every evaluation fold:

- score-based selection sees only discovery/training world columns;
- fold eligibility is exactly `origin_mask ∩ training_blocks != ∅`, using
  every recorded occurrence of the lineup, and that admitted universe is
  called the **fold-eligible union**, not full union;
- a lineup first generated only in the held-out block is excluded even if its
  discovery-column scores can be reconstructed;
- every score-derived admission/retrieval input—tail posterior, dominance,
  novelty, scenario cluster, score correlation, LCB and source rank—is
  recomputed from training blocks only; no global score sidecar may feed a
  fold;
- every provenance-derived input used for admission, matching, ranking,
  stratification or ties—source-arm support, occurrence/duplicate counts,
  first occurrence, generator recurrence, block/visit ordinals—is recomputed
  only from training occurrences; held-out mask bits are visible solely to the
  exclusion/audit layer;
- tie metadata is fold-local or derived only from stable roster identity; a
  global first-occurrence ordinal is forbidden;
- rotate the held-out block so R4 is not repeatedly consumed as permanent
  development data; and
- retain candidate-origin block masks and exclusion counts in the receipt.

The minimum implementation is a corrected R0-R3/R4 split compatible with the
accepted retrieval engine. The preferred implementation is five-fold
block-rotated cross-fitting, followed by season/slate outer folds for realized
evaluation.

### B3. Fix admission completeness

The matchup-top-200 admission currently risks favoring a lineup supported by
one high-edge annotated player over a broadly supported lineup. The corrected
manifest must specify:

- eligible positions and player roles;
- minimum annotated-player count or minimum receiver-opportunity share;
- how continuous edge components are aggregated;
- how missing components affect eligibility and uncertainty;
- explicit missing—not zero—semantics;
- deterministic ties;
- the admission cap and fallback when fewer than the cap qualify; and
- source/version/completeness identities for every annotation.

Run the fold-eligible union as the operational paired control. Treat matchup
admission as one hypothesis, not as an established truth.

Also freeze a **score-blind size-matched admission control** before any outcome
read. It must select the same number of candidates as matchup admission using
  only stable roster identity, slate, training-fold source-arm support,
  matchup-annotation
availability/completeness bins, and other explicitly registered score-free
strata—not matchup values or simulated/realized scores. Default to 32
deterministic hash-seeded replicates; an outcome-blind runtime benchmark may
change that count only before R6-v2 is frozen. Every replicate book is frozen
and realized-graded. This separates evidence for matchup information from the
generic effects of reducing pool size or altering source-arm composition.

> **[v12 operator review — 2026-08-24]** Make the runtime benchmark an
> explicit named Wave 1A step, not an option. Rough final-fit book count
> at the default: (7 laws × 2 admissions + 32 neutral replicates) ≈ 46
> books × 54 slates ≈ 2,500 greedy exact-80 selections over per-slate
> unions, before fold-level books. Realized grading of those books is
> cheap; generating them is the unknown — the v2 selector's
> memory/runtime at union scale was already an open benchmark item before
> this plan. Freeze the replicate count only after that measurement.

### B4. Align thresholds and comparison universes

- Choose strict greater-than versus greater-than-or-equal semantics once per
  threshold and enforce them consistently in algorithms, metrics, tests, graph,
  UI, and preregistration.
- Apply baseline and challenger selectors to the exact same cross-arm union
  when measuring retrieval effects.
- Do not compare a new selector on the union with an incumbent book selected
  separately inside one arm and call the difference retrieval-only.
- Bind the complete admitted candidate IDs and score-matrix hash before
  selection.

### B5. Retain complete evidence

For every slate, admission, fold, and selector, retain:

- ordered admitted candidate IDs;
- excluded candidate IDs with deterministic reason codes;
- exact selected 80 IDs;
- every marginal choice trace and tie-break value;
- objective before/gain/after values;
- per-block and threshold contribution vectors;
- full input hashes and candidate/world dimensions;
- simulated discovery and held-out metric vectors;
- overlap/correlation/redundancy diagnostics; and
- runtime/memory/cost measurements.

Aggregate receipts are not sufficient.

### B6. Freeze R6-v2

After the corrected runner passes real-artifact outcome-blind smoke and before
realized outcomes are read:

- write a new R6-v2 protocol;
- bind the accepted v12 panel index;
- bind the exact science/verifier releases, deployment attestation and
  experiment manifest;
- list every selector-by-admission cell;
- predeclare primary and secondary metrics and multiplicity handling;
- predeclare missing-task and missing-annotation behavior;
- state that v1 was non-executable, not failed;
- freeze all selected books and their hashes; and
- acquire the historical-outcome lease only for the subsequent grade.

The 14 selector × admission cells are an execution lattice, not 14 primary
hypotheses. R6-v2 freezes these inferential roles:

- **primary mechanism hypothesis:** under `coverage-194-v1`, matchup-top-200
  outperforms the preregistered score-blind, size/composition-matched control
  distribution on the panel-level net count of slates whose best-of-book
  realized score is at least 194;
- **primary statistic:** observed matchup panel statistic minus the median
  neutral-replicate statistic, plus the one-sided empirical neutral-reference
  rank
  `(1 + neutral replicates at least as good as matchup) / (R + 1)`;
- **primary decision rule with 32 replicates:** the matchup statistic exceeds
  the neutral median by at least two slates, its empirical rank is at most
  3/33, its ≥200 count is not below the neutral median, and no season’s ≥194
  count is more than one below the neutral median; this is a retrospective
  nomination signal, not proof of a population-level p-value;
- **key operational secondary:** the same selector’s matchup-top-200 versus
  all-block union contrast, retaining ≥200 and per-season harm guards;
- **other selector contrasts:** secondary with the frozen multiplicity law;
  `mean-score-v1` remains a negative control and is never promoted as a
  primary tournament selector; and
- **mechanism interpretation:** without the neutral contrast, the result may
  describe which admission operated better but cannot attribute the gain to
  matchup information.

The empirical neutral-reference rank is descriptive, not automatically a
randomization-test p-value. R6-v2 may label it inferential only if it separately
predeclares and satisfies a conditional exchangeability/null-permutation law,
runs the complete admission-plus-selector under every assignment, and freezes
its alpha/support decision rule.

Five-fold cross-fitting produces unbiased-with-respect-to-simulation-fold
descriptive evidence, but not five independent historical observations. After
parameters and inferential roles are frozen, construct **one realized-grade
book per selector/admission/neutral replicate** by refitting once on all five
simulated blocks and the all-block candidate union. This all-block final-fit
law uses no realized outcome, is distinct from each fold-eligible evaluation
book, and must be bound before any actual-score access.

### B7. Tests and exit criteria

Required tests include:

- all seven laws appear under both admission modes;
- size-matched controls have exactly the matchup candidate count, cannot read
  score or matchup fields, and replay identically from their registered seed;
- deleting or reordering a registry law fails compatibility tests;
- an R4-only candidate can never enter R0-R3 selection;
- every derived score feature and tie input is fold-local or identity-only;
- five-fold candidate-origin exclusion works for each held-out block;
- same-union controls are byte-identical before selector dispatch;
- strict threshold boundary fixtures;
- sparse and missing matchup annotation fixtures;
- selected IDs and traces replay exactly;
- no outcome-bearing source can be imported or read; and
- one accepted real v12 task replays end to end before panel fan-out.

R6-v2 is ready for realized grading only when every registered final-fit
primary, secondary, negative-control, and neutral-replicate book exists and is
immutable. If any v12 actual-score source is accessed before then—even for an
arm-only grade—every later R6-v2 comparison on that panel is labeled
exploratory rather than preregistered retrospective evaluation.

## 10. Workstream C — simplify governance without weakening trust

### C1. Amend repository policy into the three tiers

Update CLAUDE.md and README.md so they no longer describe every research run as
an isolated, preregistered, clean-image, one-shot deployment. The revised rules
must say:

- Tier E exploration is allowed on designated development data and cached
  simulated artifacts;
- Tier E results are always labeled exploratory and carry no promotion
  authority;
- Tier V freezes a complete nominated family once and protects its evaluation
  folds/outcome read;
- Tier P retains the existing strict deployment, prospective, and operator
  gates;
- “one active historical experiment” means one active controlled unblinding,
  not one active outcome-blind compute chain;
- “no retrospective tuning” means no confirmatory claim from tuned-on data,
  not a prohibition against learning from explicitly designated development
  data;
- a failed test closes the exact preset/version/dose on that evaluation set,
  not every future materially different hypothesis; and
- 194 is a diagnostic threshold rather than the project’s definition of
  tournament success.

Preserve the standing rules for real-artifact smoke, content identity,
point-in-time data, walk-forward evaluation, complete lineup legality, and
audit before verdict.

### C2. Move stale operational history out of CLAUDE.md

The August 5 narrative contains machine- and experiment-specific “never”
instructions that can be mistaken for permanent policy. Move it to a dated
archive and keep CLAUDE.md focused on current repository-wide rules.

Replace the blanket prohibition on parallel agents with an explicit resource
rule:

- no concurrent CPU/RAM-heavy local simulations or parallel test workers on
  the crash-prone workstation;
- lightweight read-only analysis, editing, and cloud-bounded orchestration may
  proceed in parallel; and
- local resource ceilings should be measured and stated, not inferred from the
  word “agent.”

> **[v12 operator review — 2026-08-24]** Endorsed, with one addition from
> live experience: this week a 7-worker local rehearsal had to be killed
> on sight under the standing rule, and the box's HYPERVISOR_ERROR
> history is real. The rewritten rule should keep a hard default —
> "when unsure whether a workload is heavy, run it serial or in cloud" —
> so the burden of proof stays on parallelism, and it should state the
> measured ceiling rather than leaving it to per-session judgment.

Clarify that BigQuery is the operational warehouse while a dedicated Neo4j
database is allowed as a rebuildable research index.

### C3. Make HANDOFF.md current rather than encyclopedic

Keep HANDOFF.md to roughly 200–300 lines:

- current branch and commit;
- current running/terminal work;
- durable cloud and artifact IDs;
- completed milestone summary;
- unresolved risks;
- exact next actions; and
- links to dated archives and machine-generated run ledgers.

Move prior narratives to reports/handoff-archive/YYYY-MM-DD.md without deleting
history. Define “material milestone” as a build/release, launch, terminal
result, accepted verdict, blocker, actual handoff, or production mutation—not
every diagnostic poll or micro-fix.

### C4. Keep large run evidence out of worker images and Git history

GCS remains the authority for raw execution captures, solver shards, score
sidecars, and large receipts. The repository retains:

- small canonical indexes;
- final accepted completion/decision receipts;
- schemas and protocol documents;
- code and tests; and
- links plus content identities for large external evidence.

Do not copy the entire reports directory into a worker image. Remove run-output
trees from Docker build contexts and use selective COPY statements or a narrow
build context. Existing evidence is preserved; this is a forward storage rule,
not permission to delete it.

### C5. Exit criteria

- policy documents define E/V/P consistently;
- no valid Tier E manifest invokes the historical-outcome lease;
- current state is discoverable from the first page of HANDOFF.md;
- archived v1 evidence remains linked and replayable;
- a worker image contains no historical run directory or UI bundle; and
- governance tests assert authority behavior rather than obsolete prose or
  duplicated constant counts.

## 11. Workstream D — split and certify the reusable engine

### D1. Avoid a second parallel implementation

Foundry Next should wrap the proven cores through new versioned entry points
rather than duplicate or mutate frozen legacy behavior:

- corpus_legal_feasibility.py remains the legal generation/scoring core;
- corpus_legal_feasibility_verifier.py remains the independent verifier;
- corpus_retrieval_engine.py remains the selector catalog and set-objective
  implementation;
- corpus_parametric_snapshot.py remains the v1 artifact adapter;
- corpus_realized_grading.py remains the point-score grader until contest
  ranking is added; and
- existing v1 readers remain unchanged for replay.

Create a thin Foundry Next manifest/catalog/execution layer. Existing v1/v12
modules, commands, validators, and readers remain byte-compatible for evidence
replay. Prefer consolidating new contracts over adding another family of
single-purpose transports.

### D2. Split build and runtime components

Produce independently versioned components:

1. **foundry-worker:** legal population, scoring, score/event sidecars;
2. **foundry-verifier:** independent reconstruction and verification, with no
   producer solve call;
3. **foundry-analysis:** retrieval, phenotype, realized grading, registry and
   Neo4j materialization; and
4. **nfl-dfs-live-optimizer:** the existing user-facing Classic/Showdown solve
   capability and CBC runtime behind an authenticated, bounded service
   contract; and
5. **nfl-dfs-app:** read/API orchestration and compiled React UI, with no CBC.

The worker must not rebuild because the UI, Neo4j query catalog, documentation,
or an outcome grader changed. The app must not package CBC, source matrices,
solver evidence, or the reports tree. During migration, the current monolithic
app image retains `optimize_many`/`optimize_many_showdown`; remove CBC only after
the live-optimizer service passes authenticated request/response parity,
latency, failure/fallback, and rollback tests. The verifier should share only
the minimum schema/math utilities necessary for true independent replay.

### D3. Narrow build gates

At science/verifier-release time:

- run unit and property tests for the component being released;
- run one real-artifact outcome-blind smoke;
- run producer/verifier equivalence and poison fixtures;
- pin the solver and dependency lock;
- build immutable component images;
- publish the science/verifier release manifests; and
- retain a full release test receipt.

At experiment time:

- validate the canonical manifest against the existing release;
- exact-read source identities;
- launch the stable job with the manifest URI and task index; and
- do not rebuild or redeploy.

UI, graph, documentation, and analysis-only releases have their own focused
gates.

### D4. Semantic component hashing

Replace full-repository or unrelated-file hashes in the scientific common law
with a generated semantic component inventory:

- legal roster constraints;
- objective implementation;
- world schedule implementation;
- score computation;
- canonical roster/instance/slot/legality identity laws;
- selector implementations;
- numeric/tie laws; and
- schema definitions.

Record Dockerfiles, cloudbuild files, scripts, and the full commit as execution
provenance, but do not make a UI or runbook byte change alter the science hash.

### D5. v1 compatibility and migration

- Add a v12-import adapter that creates a Foundry Next canonical lineup
  snapshot by
  exact-reading accepted v1/v12 artifacts and reconstructing score sidecars.
- Verify every reconstructed v12 score hash and selected book.
- Publish a compatibility receipt proving the new snapshot is an exact
  projection, not a new population.
- Keep v1 decoders and tests indefinitely or until an explicit evidence
  retention review authorizes archival.
- Do not republish or relabel v12 as though it had been produced natively by
  Foundry Next.

### D6. Suggested code touchpoints

Prefer these changes:

- leave corpus_parametric_batch.py and its v12 validators intact; add a new
  versioned manifest executor that calls proven core functions through a
  compatibility adapter;
- add a new versioned retrieval runner and method/preset catalog adjacent to
  corpus_retrieval_engine.py while preserving the frozen R6 runner;
- add a reusable Foundry Next manifest executor instead of changing
  scripts/run_corpus_parametric_transport.py; retain that v1 command for
  replay;
- add one CLI entry point for manifest validation, launch, status, acceptance,
  and replay;
- update corpus_expansion_build.py and the corpus Docker/cloudbuild files to
  component-specific builds; and
- generate strategy/parameter compatibility fixtures from the catalogs.

### D7. Exit criteria

- a documentation, graph, or UI commit does not change worker/verifier
  scientific identity;
- a threshold/weight/preset change inside an existing typed domain requires no
  image build;
- v12 compatibility replay is exact;
- producer and verifier images can be built and released independently;
- no runtime imports code from an unpinned installed copy; and
- every active science release has a real-artifact smoke and independent
  verification receipt.

## 12. Workstream E — stable security and deployment

### E1. Pre-provision stable principals

Use dedicated, stable service accounts:

- producer: read immutable source/world roots and create attempt objects under
  the Foundry output root;
- verifier: read accepted producer/source objects and create verification
  objects;
- outcome grader: read the isolated outcome source plus frozen books and create
  grade objects;
- analysis/graph loader: read accepted evidence and write only the dedicated
  analysis/Neo4j projection boundary; and
- app: read only bounded UI projections.

No experiment should require rewriting IAM conditions from one versioned
prefix to another. Use a stable research root with create-only object
preconditions and manifest-scoped application checks.

### E2. Attest infrastructure per deployment release

At release/deployment change:

- capture exact service-account, custom-role, bucket-policy, job UID/spec, and
  image evidence;
- verify public access prevention and absence of unintended principals;
- verify the dedicated Foundry jobs are not Scheduler targets;
- publish one bounded deployment attestation; and
- re-attest only on policy/job/image drift or expiry.

At each experiment:

- verify the attestation identity and current exact job/image;
- check no conflicting active execution for the same logical task;
- launch with the canonical manifest;
- do not run Cloud Asset analysis or an all-project/all-region Scheduler census.

### E3. Reusable Cloud Run task arrays

Use existing job quota rather than creating per-experiment jobs. Configure:

- one producer task array over slates/shards;
- one verifier task array after producer acceptance prerequisites exist;
- task index from Cloud Run rather than one shell environment file per lane;
- configurable bounded parallelism after a quota, memory, and cost probe;
- maxRetries=0 at the platform if application-level attempt control is used;
  or a tightly bounded platform retry only if attempt identity remains explicit;
- no automatic retry of scientific failures; and
- exact task status/attempt records.

The first performance target is 6–12 concurrent slate tasks if resource and
quota tests permit. Do not hard-code that number; record the benchmark and
choose the highest safe value.

Before declaring job updates unnecessary, probe whether the deployed Cloud Run
generation supports execution-level task-count and parallelism overrides with
the required identity guarantees. If parallelism is job-spec-only, choose one
of two tested designs: a stable upper-bound task job whose workers acquire
manifest-scoped semaphore slots, or stable one-task workers launched by a
resumable bounded controller. Preset experiments still must not patch a shared
job spec.

> **[v12 operator review — 2026-08-24]** From live operation of both v12
> lanes: per-execution `--args` overrides work today on
> `gcloud run jobs execute` (that is how every task launches), but task
> count and parallelism are job-spec fields in our deployed generation —
> plan on the fallback branch. The one-task-workers-plus-resumable-
> controller design is effectively what the current lane driver already
> is, so it is the lower-risk evolution. Also relevant to E1/E3
> capacity: a JobsPerProject quota preference (1,000 → 1,250,
> us-central1) was submitted 2026-08-20 and was still reconciling at
> last check; the update-only job-reuse law stands regardless.

### E4. Checkpoint and resume

Generation already produces deterministic units. Persist:

- completed visit/arm/block shards;
- shard scientific input hash;
- exact solver evidence and roster result;
- parent aggregation ordering;
- failure class and retry eligibility; and
- heartbeat/progress counters.

A restarted task reuses exact valid shards and recomputes only absent or
invalid ones. Parent aggregation remains canonical and order-independent even
if workers finish out of order.

### E5. Performance objectives

These are initial engineering objectives, to be confirmed by benchmark:

- manifest validation to launch-ready: no more than 15 minutes;
- retrieval-only full accepted panel: target no more than 2 hours on approved
  compute;
- single-slate retrieval iteration: target minutes;
- full new fill panel after parallelization/checkpointing: target same working
  day, with a stretch goal near 6–8 hours;
- UI/Neo4j projection refresh from accepted aggregates: target under 30
  minutes; and
- zero image builds, deployments, or IAM mutations for configuration-only
  experiments.

Scientific exactness governs if a target is missed. Performance targets never
license approximate or incomplete results without an explicit method ID.

### E6. Observability

Expose one run-status surface containing:

- release/manifest/task/attempt IDs;
- queued/running/succeeded/failed/verified counts;
- current arm/block/visit;
- shard reuse and recomputation counts;
- solver timeouts and optimality failures separately;
- throughput, memory, CPU, estimated completion, and cost;
- artifact publication and verifier lag; and
- links to exact receipts.

Monitoring must be read-only and must not require parsing mutable workstation
logs to reconstruct authoritative state.

### E7. Exit criteria

- two concurrent experiments can use the stable infrastructure without IAM
  changes or namespace collision;
- an injected platform failure resumes and produces the same accepted hash;
- an injected solver/evidence mismatch fails closed;
- task-array results aggregate canonically regardless of completion order;
- app, analysis, producer, verifier, and outcome principals cannot cross their
  intended data boundaries; and
- the old per-version IAM-move scripts are marked legacy after v12 evidence is
  safely indexed.

## 13. Workstream F — canonical lineup and experiment evidence

### F1. Separate roster, instance, export, and evaluation identities

Do not force several meanings into one lineup ID. Define:

- **roster_id:** contest format/draft group plus the canonical sorted set of
  nine normalized draftable/player IDs; this is the stable scientific roster
  identity used for cross-arm deduplication, overlap, winner matching and
  outcome scoring;
- **lineup_instance_id:** roster_id plus the exact slate/source/pricing
  snapshot in which the roster was generated or evaluated;
- **slot_assignment_id:** lineup_instance_id plus ordered DK slot assignments,
  used for optimizer/export parity when equivalent FLEX assignments exist;
- **legality_evaluation_id:** lineup_instance_id plus legality-law and pricing
  identities and the resulting legal/salary facts; and
- an explicit canonical encoding version for each identity.

Salary corrections, legality-law changes, or FLEX reorderings must not fragment
the same roster_id. Every generator, scorer, selector, outcome grader, graph
node, and UI route must state which identity it consumes and provide verified
mappings among them.

### F2. Canonical lineup snapshot

For each slate/fill snapshot retain one immutable base row per unique roster
instance with:

- lineup and slate/source-universe IDs;
- nine roster slots, player IDs, teams, positions, salary and projection
  snapshot; and
- roster/instance/slot/legality encoding versions and mapping receipt.

Do not mutate or widen base lineup rows for each new experiment. Store
separate, immutable fact products:

- CorpusMembership as the sole authority for snapshot/fill/generator/source-arm
  provenance, occurrence masks, first occurrence, duplicate count and solve
  cost;
- LineupFeatureMeasurement for structure, novelty, boom, role, matchup,
  coverage and ownership values plus feature/source/support release;
- SimulationScore for world vector identity/hash, sparse event bitmaps and
  discovery/held-out summaries;
- AdmissionMembership for eligible/excluded rank and reason;
- BookMembership for exact selected roster, ordinal and book;
- SelectionTrace for marginal objective contributions and tie evidence; and
- OutcomeProjection for authorized realized/contest facts.

Write these products create-once under content type/schema/season/slate/release
partitions in immutable GCS Parquet/JSON. Define clustering/sort keys and
content hashes in each release. BigQuery tables are append-only,
release-partitioned query projections with one reviewed current-release pointer;
they never become a second mutable content authority. Do not put 50,000-value
arrays in Neo4j or the UI projection.

### F3. Keep score semantics distinct

Never combine these into one unlabeled positive:

- simulated lineup-world score greater than a threshold;
- realized historical lineup score greater than a threshold;
- Millionaire Maker winner membership;
- top-N contest rank;
- profitable/positive-ROI entry; and
- selected-book membership.

Every metric and feature must carry outcome kind, threshold comparison,
world/fold, source, and authority.

### F4. Event sidecars

For efficient retrieval and phenotype analysis retain:

- threshold bitmaps at 187, 194, 200, 210, 220, 230, and 240;
- block-specific event counts;
- expected-maximum score vectors or compressed sorted signatures;
- outcome-space correlation/redundancy signatures;
- candidate-origin block masks; and
- exact pointers back to the full matrix.

Sidecars are derived and independently hash-verified against the full matrix.

### F5. Source-universe correction

v12 is conditional on the artifact-supported player universe and must remain
labeled that way. Build a separate source-universe-v2 work package:

1. reconstruct the complete historical DraftKings salary/draftable universe
   for each slate;
2. reconcile active, inactive, known-out, missing-projection, and salary-only
   players;
3. establish PIT projection/world-draw authority for every eligible player;
4. for every affected slate, generate a complete new world release across the
   entire corrected eligible-player universe using one dependence-preserving
   draw; never append only missing player rows to an existing matrix;
5. publish an exact coverage report and missingness reasons;
6. run a paired artifact-supported versus complete-universe diagnostic; and
7. never silently append new players to v12 artifacts.

If complete historical support is impossible, preserve the bounded source
scope and carry it into every comparison rather than imputing unsupported
players as zero.

### F6. Exit criteria

- every accepted lineup maps to exactly one roster_id and the correct
  snapshot-specific instance/export/evaluation identities;
- every accepted lineup is scored in every registered world;
- full score hashes reproduce from pinned player worlds;
- event sidecars reproduce their matrix counts exactly;
- simulated and realized fields cannot be confused by schema;
- candidate origin supports held-out-safe retrieval; and
- source-universe completeness is explicit per slate.

## 14. Workstream G — population: learn how to fill the corpus

The population system must maximize useful, distinguishable tournament-tail
support per fixed compute budget. It must not assume that one world optimum, one
winner shape, one boom family, or one stack topology is universally correct.

### G1. Preserve v12 as F0 diagnostic evidence

Use v12 to measure the causal effect of the five registered feasibility
constraints under its exact world schedule and fixed selector. Report:

- unique legal lineups per arm;
- duplicate-generation rates;
- solve success/runtime;
- simulated threshold support and block breadth;
- realized corpus ceiling after the one-read grade;
- winner/top-tail phenotype coverage;
- source-arm overlap and novel support; and
- selected conversion under the fixed selector and all corrected retrieval
  selectors.

Do not call the remove-all-five arm rule-free, and do not promote a relaxed
rule solely from simulated support.

### G2. Build the neutral super-pool

Create one broad, mechanically fixed source pool per slate containing:

- v12 incumbent and relaxation-arm lineups;
- existing legal historical corpus lineups with valid source provenance;
- bounded existing generator families;
- newly implemented near-optimal/unique-fill alternatives; and
- explicitly tagged topology, phenotype, and novelty sleeves.

Deduplicate once by roster_id while retaining all source lineage.
Score each unique lineup once against each world matrix. Retrieval experiments
then operate on immutable admissions over this snapshot and do not regenerate
the simulation law.

Before union, require one compatible contest format, player/source universe,
and complete world release for the slate. A roster containing an unscored
player fails the gate; it is never imputed as zero. Candidates generated from
R blocks retain complete origin masks. Candidates created independently of R
worlds receive an explicit predeclared block-independent origin class and may
be fold-eligible only under that registered law. Any lineup admitted because
its realized score, contest rank, payout, or winner identity was already known
is quarantined as analysis-only and can never enter a retrieval experiment.

The super-pool is not itself a live book. It is a research substrate.

### G3. Initial fill preset catalog

Implement these preset families as typed manifest configurations:

| Preset | Purpose | Initial method |
|---|---|---|
| F0-incumbent | Paired control | Existing production-compatible families and house rules |
| F1-tail-family | Preserve supported simulated-tail supply | More boom/tail-oriented solves while retaining an incumbent component |
| F2-winner-support | Cover structures the incumbent excludes | Bounded soft sleeves over QB teammate 0/1/2/3+, bring-back 0/1, game concentration 2/3/4/5+, and salary/ownership shapes |
| F3-phenotype-conditional | Generate toward portable high-tail traits | Cross-fitted soft bonuses/quotas from realized/simulated phenotype models; no player/team identities |
| F4-hybrid | Hedge simulator misspecification | Fixed mixture of F1, F2, F3 and novelty/residual-scenario candidates |
| F-negative | Establish mechanism | Equal-budget ablations removing one sleeve/feature/dose at a time |

Presets must specify exact solve counts per sleeve and an equal-budget paired
control. Do not infer causality by allowing one preset more solves or more
unique retries unless the estimand is explicitly compute efficiency.

### G4. Replace one-optimum-per-high-total-world as the only generator

Register and compare several generation method IDs:

1. **world-optimum:** current exact optimum, retained as a control;
2. **near-optimal enumeration:** no-good/exclusion solves within an exact
   objective gap or top-K count;
3. **unique-fill:** continue deterministic solves until a fixed unique count or
   compute ceiling is reached;
4. **portfolio column generation:** propose lineups by marginal scenario value
   against the already generated pool;
5. **stratified-world generation:** sample/allocate across world regimes rather
   than only the highest total-slate-draw worlds;
6. **tail-event targeted generation:** target worlds/scenarios not already
   covered by the source pool; and
7. **topology/phenotype sleeves:** soft quotas/bonuses for support missing from
   the neutral pool.

Each method retains its objective, solve evidence, compute use, duplicate
yield, and source attribution.

### G5. Test the world-schedule heuristic

The current top-200-by-total-slate-draw schedule may favor broad inflation
rather than concentrated tournament-winning scenarios. Compare, at equal
world/solve budget:

- current total-slate-draw ranking;
- stratified quantiles of slate total;
- high projected lineup-ceiling worlds;
- game-regime strata;
- residual/uncovered-event worlds;
- block-balanced sampling; and
- a deterministic mixed schedule.

World schedules are outcome-blind and frozen per experiment. Evaluate their
unique tail support and conversion, not just their simulated pool ceiling.

### G6. Trait families available to population models

Only PIT, identity-free or appropriately hierarchical features may transfer to
future slates:

- projection and simulated quantiles;
- boom probability and multi-player boom structure;
- QB teammate and bring-back topology;
- team/game concentration and dispersion;
- salary allocation and unused salary;
- role/usage/vacated opportunity;
- receiver/RB/QB matchup edge and source completeness;
- opponent positional concessions;
- ownership shape and leverage when PIT projections exist;
- estimated duplication and lineup-template popularity;
- player-score and lineup-outcome correlation;
- historical high-tail posterior with cross-fitting;
- winner-support posterior with same-slate controls;
- novelty relative to incumbent/high-exposure regions; and
- uncertainty/support count.

Player, team, game, and historical-outcome identities may be used for audit and
matching but never as transferable coefficients.

### G7. Population metrics

For every slate and fill preset retain:

- total solves and wall/CPU cost;
- unique legal lineups and unique yield per 1,000 solves/CPU-hour;
- duplicate and near-duplicate rate;
- structural and phenotype coverage;
- source/family contribution;
- simulated threshold events and block support;
- expected pool maximum and event-regime breadth;
- realized corpus ceiling C and threshold ladder;
- best-source attribution;
- winner/top-tail support with matched denominators;
- new useful candidates absent from F0;
- candidates admitted/selected by each retrieval policy; and
- C minus selected-book maximum S.

### G8. Population acceptance criteria

A fill challenger advances from E to V only if:

- it is non-vacuous and adds legal unique candidates;
- equal-budget comparison is exact;
- its support is not confined to one slate/block/season;
- it improves at least one registered tail/set utility without a predeclared
  unacceptable loss;
- the benefit survives at least two materially different retrieval policies or
  is explicitly nominated as an interaction-specific fill;
- it is not driven solely by player/team identity;
- source coverage and missingness are acceptable; and
- the complete lineup snapshot, scores, and provenance replay exactly.

## 15. Workstream H — retrieval: learn how to select the portfolio

Retrieval is a two-stage portfolio decision:

1. **admission** forms an eligible shortlist from the immutable source pool; and
2. **set selection** chooses the exact-size book by marginal contribution,
   accounting for scenario redundancy.

### H1. Baseline selector catalog

Retain all seven current methods:

- coverage-194 as a continuity diagnostic;
- strict >200 coverage;
- 200/210/220 tail ladder;
- mean-score individual ranking as a negative control;
- expected book maximum;
- block-supported tail ladder; and
- regime-robust/leximin ladder.

Parameterize, within registered domains:

- final entry budget, initially 20/40/80/150 as supported contest sizes;
- thresholds and strictness;
- threshold weights;
- discovery/held-out blocks;
- utility transform;
- tie-break order; and
- runtime/memory ceiling.

Exact-80 remains the principal historical comparator until a contest-specific
budget is registered, but it is no longer a code-level universal law.

> **[v12 operator review — 2026-08-24]** The supported budget list
> (20/40/80/150) omits the budgets the project actually recorded for
> Week 1: the standing contest-mix memory is 3 qualifiers × 14 entries
> plus 4 Millionaire Maker entries (with an ambiguous "never <15 per
> contest" rider that the Week-1 packet must resolve). Register 4 and 14
> as first-class entry budgets now, and upgrade §J3's prefix maxima at
> 4/14 from optional to required for any book intended to inform the
> Week-1 decision — K6 already forbids treating an exact-80 book as
> validation for other budgets.

### H2. New retrieval candidates

Add only after clear semantic definitions and tests:

1. **tail-LCB:** marginal utility based on a genuine shrunk/lower-confidence
   tail rate, not a support-count heuristic mislabeled as an LCB;
2. **expected contest-relative maximum:** utility against a slate-specific
   winning/rank threshold distribution;
3. **duplication-adjusted expected payout:** expected payout net of ties and
   duplicated lineups when field data are available;
4. **scenario-cluster coverage:** marginal value across learned tail-event
   regimes;
5. **correlation-aware expected max:** discourage redundant score vectors while
   preserving true complementarities;
6. **hybrid support:** simulated set utility plus bounded cross-fitted
   realized-tail/winner-support admission or tie-break; and
7. **robust ensemble book:** a fixed allocation across materially distinct
   selectors when no single method dominates outer folds.

Every new method must have an interpretable marginal trace and negative-control
fixture.

### H3. Admission catalog

Initial admissions should include:

- fold-eligible union during cross-fit evaluation and all-block union for the
  frozen final fit;
- deterministic score-blind size-matched controls for every bounded
  signal-based admission;
- fill-preset-specific pool;
- simulated-tail support minimum;
- cross-fitted realized-tail posterior;
- winner-support topology sleeve;
- boom-supported;
- matchup-supported with completeness gate;
- ownership/leverage/duplication-aware;
- Pareto/dominance pruning;
- novelty/residual-scenario; and
- fixed mixtures reserving a minimum incumbent share.

Admission may remove useful complementary lineups; every bounded shortlist must
be paired against the correct fold-eligible/all-block union and report
discarded-oracle diagnostics.

### H4. Set utility rather than top-80 probabilities

Primary selectors must maximize:

    J(S) = sum over scenarios q(scenario) times
           u(max score among lineups in S for that scenario)

or a registered contest-equity analogue. Candidate choice is marginal gain
from adding one lineup to the current set. Individual tail probabilities,
winner-likeness scores, matchup scores, and ownership are admissions,
constraints, weights, or tie-breaks—not replacements for portfolio utility.

### H5. Fill-by-admission-by-retrieval evaluation

The system has three decision axes, so the final nominated comparison uses a
registered 2×2×2 design:

- fill F0 incumbent versus F1 challenger;
- admission A0 incumbent/full versus A1 challenger; and
- retrieval R0 incumbent versus R1 challenger.

The eight cells F0A0R0 through F1A1R1 identify all three main effects, the
fill×admission, fill×retrieval and admission×retrieval interactions, and the
three-way interaction. If compute requires staged screening, first run the
three one-axis contrasts F1A0R0, F0A1R0 and F0A0R1 against F0A0R0, but do not
label a matchup-universe change a retrieval effect.

All cells share source slate, worlds, seeds, legality, and final entry budget.
Fill comparisons have equal solve budgets. Admission comparisons start from
the identical source snapshot. Retrieval comparisons have identical admitted
candidate IDs and score vectors.

Do not blindly execute the full Cartesian product of every exploratory preset.
Tier E may screen broadly; Tier V freezes a bounded family containing the
baseline, one nominated joint strategy, and one materially distinct fallback.

### H6. Retrieval metrics

Retain per slate/fold:

- objective value and marginal-gain sequence;
- simulated book maximum mean/quantiles;
- threshold event coverage by block;
- unique event/scenario clusters;
- selected pairwise score correlation and effective rank;
- roster overlap and exposure concentration;
- source/fill/admission representation;
- pool ceiling C, selected maximum S, and conversion gap C-S;
- held-out metrics with candidate identity exclusion;
- realized weekly maximum and threshold ladder;
- contest rank/ROI/duplication when available; and
- sensitivity to each selected lineup and leave-one-lineup-out utility.

### H7. Retrieval acceptance criteria

A selector advances only if:

- it produces the exact registered book size and unique legal lineups;
- its trace independently replays every choice;
- it uses no held-out candidate identities or score columns;
- it is compared on the same pool as its baseline;
- its gain is not one-block, one-slate, or one-season dependent;
- it improves the registered portfolio endpoint rather than only individual
  classification;
- fold-eligible/all-block union versus bounded-admission opportunity cost is
  reported;
- threshold/weight sensitivity was contained inside development folds; and
- outer/prospective evidence meets the frozen gate.

## 16. Workstream I — high-score, winner, matchup, and correlation intelligence

### I1. Maintain separate cohorts

Build queryable cohorts for:

- all unique corpus lineups;
- simulated >194/>200/>210/>220/>230/>240 lineup-world events;
- realized historical >194/>200/>210/>220 lineups;
- weekly realized corpus maxima;
- selected books by preset;
- verified Millionaire Maker winners;
- same-slate matched controls;
- prospective 2026 contest entries; and
- full contest-field/top-rank cohorts when standings exist.

Every analysis reports lineup, slate, season, world-block, and source support.
Lineup-world event count is never treated as the independent sample size.

### I2. Reconcile the winner authority before winner modeling

Create a dedicated winner-release work package before any winner-support model
is trained:

1. inventory the known 68-row winner collection with source, contest, slate,
   draft-group, season/week, roster and score identities;
2. preserve the governed 51-winner analytic subset as a distinct, immutable
   release rather than silently expanding or replacing it;
3. map every accepted roster to roster_id and record unresolved player,
   contest, slate, duplicate/correction and legality cases with reason codes;
4. distinguish verified winner roster/score facts from partial ownership,
   payout, field and article-derived annotations;
5. publish exact accepted/excluded/unresolved counts and source hashes for both
   releases;
6. test that no row is silently dropped, deduplicated across different
   contests, or promoted from anecdote to fact; and
7. require every analysis/UI result to state which winner release and
   denominator it uses.

Winner membership remains outcome data. It may support cross-fitted historical
analysis and small hedge sleeves under the outcome firewall, but it never
enters a future-slate feature unless transformed into a PIT-available,
identity-free rule.

### I3. Feature families to analyze

For winners and corpus-tail cohorts measure:

- roster topology and stack/bring-back shape;
- team/game concentration, dispersion, and correlations;
- salary allocation;
- projection, boom and upper-tail quantiles;
- role, route, target, rushing, red-zone, and opportunity state;
- opponent positional concessions;
- receiver alignment, shell fit, defender quality, and matchup edge;
- easy-coverage continuous score, Boolean, count, role, and completeness;
- player pair/team/game recurrence with shrinkage;
- ownership, leverage, chalk shape, and estimated duplication;
- generator/fill origin and recurrence across source panels;
- world regime and block support;
- outcome-space lineup correlation and scenario complementarity; and
- missing-data/source-quality patterns.

### I4. Matched denominators and portability

“X percent of winners had trait T” is incomplete. Always report:

- same-slate eligible-lineup prevalence;
- matched-control prevalence;
- enrichment/lift with uncertainty;
- season/slate support;
- sensitivity to player identity removal;
- source coverage and missingness; and
- whether the association appears in simulated tail, realized corpus tail,
  winners, or more than one evidence regime.

Use hierarchical shrinkage for sparse pairs and interactions. A relationship
appearing repeatedly on one slate is one-slate evidence.

### I5. Complete the matchup program

The receiver/RB/QB PIT and annotation foundations already implemented must be
reopened and validated against the exact accepted source identities. Then:

1. expand annotations across every accepted v12 slate and every canonical
   lineup;
2. reproduce source completeness for Fantasy Points, SIS, PFR, roles, and
   defender crosswalks;
3. run player-level nested models and matched winner/control analyses;
4. compare simulated and realized tail enrichment;
5. retain continuous component scores and explicit missingness;
6. prohibit factual receiver-to-defender assignment claims without a direct
   assignment source;
7. nominate at most one bounded matchup interaction for a fill sleeve and one
   for admission; and
8. test the complete 2×2×2 fill/admission/retrieval interaction rather than
   rerunning the closed
   twelve-candidate coverage arm.

The implementation and UI detail remains governed by
[the receiver/defender plan](./2026-08-22-receiver-defender-matchup-intelligence-implementation-plan.md).

### I6. Pairing and correlation analysis

Produce both structural and outcome-space measures:

- player pair and trio enrichment with same-slate denominators;
- QB-receiver, bring-back, RB-RB, WR-WR, DST/opponent and game-stack cells;
- correlation of full world-score vectors;
- joint threshold-event overlap and conditional tail lift;
- scenario-cluster co-membership;
- selected exposure and effective portfolio rank; and
- realized pair performance with season-level shrinkage.

Roster overlap is a descriptive proxy, not the correlation target.

### I7. Transfer rules

A trait can affect fill/admission only when:

- it is available point-in-time on future slates;
- it is defined without historical identity leakage;
- its support and missingness meet a registered minimum;
- its coefficient/dose is selected inside development folds;
- its contribution survives an ablation;
- the portfolio selector converts it into set-level improvement; and
- the graph/UI label its evidence regime and uncertainty.

Winner-only traits receive small hedge sleeves until realized/prospective
evidence supports more. Simulated-tail-only traits remain simulator-support
sleeves. Discordance is information to preserve, not something to hide by
averaging.

## 17. Workstream J — realized outcomes and contest equity

### J1. Preserve the existing v1 grader

The existing realized grader is a replayable authority for the original v12
arm books. Do not change its accepted v1 behavior. Run it only after:

- the complete v12 panel index exists;
- every original arm book is frozen;
- every intended R6-v2 primary, secondary, negative-control and neutral book is
  frozen before **any** v12 actual-score access;
- the exact outcome query and lease are registered; and
- the grader can prove complete player/lineup coverage.

If an arm-only grade occurs first, it is still a read of the panel’s outcomes.
Later R6-v2 grades may be computed, but their evidence class becomes
exploratory.

> **[v12 operator review — 2026-08-24]** This is the plan's single most
> consequential sequencing change versus the standing operational plan,
> and it needs an explicit operator decision. The deployment session had
> planned an immediate post-completion arm-level realized grade (the
> "scores Tuesday morning" commitment). Under this rule that read would
> demote every later R6-v2 comparison on the panel to exploratory. The
> two coherent options: **(a)** hold the single read until R6-v2 books are
> frozen — preserves the preregistered-retrospective class for the matchup
> evaluation at the cost of roughly one focused day (Wave 1A); **(b)**
> grade the seven arm books immediately — delivers the F0 fill-ablation
> scorecard a day earlier and forfeits R6-v2's preregistered label. My
> recommendation is (a), with one mitigation the plan should make
> explicit: B1–B5 code and tests touch nothing in the active v12 run, so
> they can be written outcome-blind against already-accepted slate
> artifacts while the lanes finish, compressing the critical path so the
> realized read may still land within the original timeline. Whichever
> option the operator picks, record it as a dated decision before the
> first actual-score access.

### J2. Add an arbitrary-book v2 grader

Implement a new grader that accepts:

- a canonical catalog of immutable books from any registered fill/admission/
  retrieval cell;
- the complete distinct lineup union so each realized lineup is scored once;
- one outcome-source receipt;
- lineup/source/slate identities;
- exact salary/legality context;
- expected book size and membership hash; and
- metric definitions.

It then projects one canonical realized lineup score into every book. It must
never regenerate or choose a book after actuals are available.

### J3. Required point-score metrics

For every slate/cell/book report:

- realized score for every lineup;
- weekly selected maximum S;
- complete corpus ceiling C;
- conversion gap C-S;
- count of selected and corpus lineups at 187, 194, 200, 210, 220, 230 and
  240;
- selected lineup’s rank within the canonical source corpus;
- gap to the known winner score when available;
- best supplying fill/arm/generator;
- exact paired deltas against registered baselines;
- book overlap and composition; and
- optional prefix maxima for operational entry budgets such as 4, 14, 20, 40,
  80 and 150.

### J4. Historical contest limitations

The project does not have a complete historical contest-entry population for
the old Millionaire Maker slates. Therefore:

- historical field rank, duplication, payout and ROI remain unavailable unless
  a complete, independently validated contest file exists;
- winner score gaps are not substitutes for field-rank distributions;
- ownership alone is not a field lineup sample; and
- UI/API/graph fields must say unavailable rather than infer authoritative
  values from a proxy.

### J5. Prospective full-field collection

For every target 2026 contest:

1. register contest identity, entry fee, entry count, payout ladder, draft
   group, lock, and intended entry budget;
2. freeze pre-lock salary, projection, ownership, matchup, and book artifacts;
3. capture the complete settled standings before DraftKings removes them;
4. archive raw source bytes and a create-once source receipt;
5. publish a versioned capture decision that points to exactly one accepted
   capture and marks corrected predecessors superseded without overwriting
   them;
6. validate entry count, unique entry IDs, roster length, canonical player IDs,
   score/rank ordering, ownership reconciliation, duplicates, and payout totals;
7. write accepted contest entries/ownership/payout tables;
8. treat settled per-entry DraftKings `Winnings` as the observed payout
   authority; compute the frozen payout-ladder/tie-split reconstruction as a
   validation value and fail/reconcile when they disagree;
9. grade submitted and shadow books; and
10. publish a distinct outcome-release receipt for graph/UI.

### J6. Contest-equity metrics

Once complete contest fields exist, add:

- counterfactual rank and percentile;
- top 10, top 100, top 1%, and top 0.1% indicators;
- exact-roster duplicate count and tie group;
- payout after tie splitting;
- entry-level and book-level ROI;
- maximum payout;
- score/rank/payout regret relative to the best corpus lineup;
- ownership and duplication calibration; and
- payout sensitivity to contest size/structure.

Contest equity must be contest-specific. A selector optimized for one payout
curve or entry budget is not silently transferred to another.

For a shadow lineup that was not actually entered, freeze a counterfactual
insertion law before settlement: evaluate both individual insertion and the
registered book’s simultaneous insertion; count pre-existing identical
rosters; apply the contest’s score-tie/rank law; specify displaced ranks; and
split the payout across the resulting tie group. Label these as
counterfactual estimates, never observed winnings. Submitted-entry outcomes
remain a separate estimand.

Raw standings may contain public contestant names and persistent entry IDs.
Keep raw records in the restricted outcome store. BigQuery research
projections, Neo4j and the UI receive aggregates plus salted release-scoped
identifiers (and explicitly operator-owned entry markers) only—never public
contestant names or raw entry records.

### J7. Outcome firewall

- Outcome tables and grade namespaces are inaccessible to producer, admission,
  and retrieval principals.
- Live/pre-lock feature contracts reject actual score, realized ownership,
  field rank, payout, winner membership, and post-lock timestamps.
- Tier E development views containing outcomes live in an analysis namespace
  and cannot be imported by production construction code.
- Every grade binds frozen book identities created before its outcome read.

### J8. Exit criteria

- every distinct graded lineup has one authoritative realized score;
- every frozen book is graded without post-read mutation;
- point metrics reconcile across v1/v2 for original arm books;
- unavailable contest metrics remain explicitly unavailable;
- complete prospective fields reproduce standings ranks and payout totals;
- accepted/superseded capture pointers and observed-versus-reconstructed
  payout reconciliation replay exactly; and
- one outcome release can rebuild graph/UI outcome views exactly.

## 18. Workstream K — statistical evaluation and decision laws

### K1. Units and folds

- Primary paired unit: slate.
- Outer dependency block: season.
- World blocks support simulator robustness but are not independent historical
  observations.
- Lineup-world events support within-slate mechanics but never inflate the
  historical sample size.
- R blocks rotate for simulated cross-fitting.
- Seasons/slates rotate for historical model/preset development.
- Prospective 2026 contests remain the final unseen tier.

### K2. Exploration

Tier E may:

- use already-viewed outcomes;
- compare broad preset grids;
- tune doses/weights inside declared development folds;
- run sensitivity and mechanism ablations; and
- nominate hypotheses.

It must publish complete tried-preset metadata so the UI cannot present the
best result without the search context.

### K3. Frozen evaluation family

Before Tier V outcome evaluation:

- freeze baseline, one primary nominee, and at most one materially distinct
  fallback;
- freeze metrics and adverse-effect limits;
- freeze complete books;
- state missing-slate behavior;
- reserve outer/prospective data;
- register multiplicity handling; and
- record the exploratory search family from which nominees arose.

The 54-slate v12 panel is explicitly retrospective because its seasons and
related outcomes have informed project design. A report may use the same
frozen mechanics, but it earns the label confirmatory only on a documented
untouched holdout or on prospective pre-lock books.

### K4. Required reports

For every frozen evaluation comparison report:

- weekly vectors, not only aggregate means;
- mean and median paired maximum delta;
- wins/ties/losses;
- exact threshold transitions;
- season-stratified paired bootstrap or randomization interval;
- leave-one-slate and leave-one-season influence;
- maximum single-slate share of total gain;
- per-season counts/deltas;
- book overlap and distinctness;
- C, S and C-S;
- simulated cross-fit and realized results side by side; and
- multiplicity-adjusted secondary metrics.

### K5. Initial nomination gate

Until field/rank/payout data support a better frozen gate, a Week-1 historical
nominee should:

- improve mean paired weekly maximum;
- achieve at least a net +2 slates at 200 or above;
- not reduce 210- or 220-plus slate count;
- not worsen any season by more than one 200-plus slate;
- not derive more than half its positive aggregate gain from one slate;
- improve held-out simulated expected maximum or registered tail utility
  without depending on one R block;
- pass equal-budget, PIT, legality, completeness, and deterministic replay; and
- retain an incumbent fallback when optional matchup/ownership data are
  missing.

This is a nomination gate, not proof of profitability. If intervals remain
compatible with no improvement, the challenger may run as a shadow but is not
described as proven.

### K6. Week-1 operating decision

The historical nomination gate does not by itself replace the incumbent. Use
this frozen policy:

- if the challenger passes the nomination gate, the operator may issue a
  reviewed **Tier-P limited-deployment receipt** for a predeclared capped
  allocation—default 20% of entries—with the incumbent receiving the rest;
  without that receipt, the challenger is shadow-only;
- historical replay must grade the actual exact-N composite portfolio against
  an exact-N incumbent portfolio: exact integer sleeves, joint uniqueness,
  overlap/collision replacement order, and challenger marginal choices
  conditional on the incumbent sleeve—not merely a standalone N-lineup
  challenger followed by a 20% allocation;
- if intervals are inconclusive, exact-budget evidence is absent, or any
  required PIT source/completeness/verification/export check fails, the
  challenger is shadow-only and all submitted entries use the incumbent;
- the manifest states exact integer counts, collision/overlap handling, and a
  machine-evaluable fallback receipt before lock;
- an exact-80 historical book is never treated as validation for an exact-20
  or exact-150 contest without rerunning and grading that budget; and
- Week-1 settlement cannot change entries already submitted or establish
  promotion by itself.

Any allocation above the cap or full replacement requires the later reviewed
promotion receipt below.

### K7. Later promotion objective

As complete field data accumulate, replace fixed-score promotion with
contest-relative endpoints:

- probability of top-N/top-percentile finish;
- duplication-adjusted expected payout;
- book ROI distribution;
- catastrophic downside and concentration;
- calibration of field/duplication assumptions; and
- prospective performance over multiple slates.

Keep 194/200/210/220 as interpretable diagnostics.

Before Week 1, freeze the prospective scaling law to prevent optional stopping.
The default protocol has two possible scheduled reviews—after 8 and 16 complete
eligible target contests—with one-sided alpha 0.025 allocated to each look and
no unscheduled promotion read. Predeclare exactly one next promotable target
dose—default 50% challenger—and freeze an exact-N shadow composite at that dose
before every contest locks. Full replacement requires its own prospectively
frozen 100% target-dose protocol; evidence from a 20% or 50% sleeve cannot
authorize 100%. The protocol requires:

- complete field capture and exact-N counterfactual grades for incumbent,
  deployed dose and the predeclared target-dose composite on every counted
  contest, totaling at least 8×N target-dose book entries at the first look;
- primary endpoint: target-dose versus exact-N incumbent mean paired
  duplication-adjusted book-ROI delta, with the registered
  season/contest-stratified interval lower bound above zero;
- harm guards: nonnegative median best-entry contest-percentile delta, no
  registered catastrophic-downside breach, and no contest-structure stratum
  worse beyond its frozen tolerance;
- secondary endpoints controlled by the frozen multiplicity family and never
  substituted for a failed primary;
- missing/incomplete standings do not count toward sample size; more than the
  frozen missing-capture allowance makes the review inconclusive; and
- a maximum look schedule and terminal inconclusive/reject rules. If the first
  look does not cross its boundary, allocation remains capped/shadow until the
  second; after the second, no scale-up occurs without a newly prospective
  protocol.

Every promotion receipt is capped at the highest exact allocation dose tested
under that frozen protocol. Portfolio construction, joint uniqueness,
collisions and conditional marginal selection are recomputed at each target
dose; they are never extrapolated from the deployed sleeve.

The final protocol may choose stricter horizons/boundaries before Week 1, but
may not weaken or change them after the first eligible contest locks.

## 19. Workstream L — strategy registry and knowledge graph

### L1. Registry axes

The canonical registry must treat these as separate versioned objects:

- ScienceRelease;
- VerifierRelease;
- DeploymentAttestation;
- SourceUniverse;
- WorldRelease;
- FillPreset;
- AdmissionPreset;
- RetrievalPreset;
- MetricDefinition;
- FoldDefinition;
- ExperimentManifest;
- ExperimentCell;
- ExperimentRun;
- Evaluation;
- StrategyBundle;
- CandidateSnapshot;
- SelectedBook;
- WinnerRelease;
- OutcomeRelease;
- MetricSet; and
- PromotionDecision.

Admission must not remain hidden inside retrieval. Final entry budget and
objective parameters belong to the retrieval preset or experiment cell rather
than global constants. A StrategyBundle is the exact versioned subject of a
deployment/promotion decision: fill + admission + retrieval + entry budget +
integer sleeves + fallbacks + source requirements + science release.

### L2. Dedicated Neo4j authority boundary

Use a dedicated corpus-research database/instance. Immutable accepted GCS
evidence remains content-authoritative; BigQuery is a rebuildable query
projection. Neo4j stores:

- compact identities and relationships;
- all accepted lineup identities only in a release explicitly declared
  full-lineup;
- lineup-player edges;
- preset/experiment/book lineage;
- phenotype/trait membership and support;
- selected/admitted/generated relationships;
- metrics and uncertainty;
- contest/winner/outcome links after authorized grading; and
- pointers to exact GCS/BigQuery evidence.

Neo4j must not store:

- full 50,000-world matrices;
- raw licensed Fantasy Points or SIS rows;
- raw standings files;
- credentials;
- mutable active-policy pointers; or
- an execution command queue.

### L3. Graph model

Recommended nodes:

- Slate, Contest, SlateSnapshot, PlayerSlate, TeamSlate, Game;
- WorldRelease, CorpusSnapshot, Lineup, SelectedBook;
- ScienceRelease, VerifierRelease, DeploymentAttestation, FillPreset,
  AdmissionPreset, RetrievalPreset;
- ExperimentRun, ExperimentCell, Evaluation, StrategyBundle, Fold, MetricSet;
- Trait, Cohort, WinnerRelease, WinnerObservation, OutcomeGrade;
- SourceArtifact, VerificationReceipt, Attempt; and
- PromotionDecision.

Recommended relationships:

- DERIVED_FROM, USES_SOURCE, USES_WORLD_RELEASE;
- GENERATED_BY, MEMBER_OF_CORPUS, SUPPLIED_BY_ARM;
- CONTAINS_PLAYER, PLAYS_FOR, IN_GAME;
- HAS_TRAIT, MEMBER_OF_COHORT;
- ADMITTED_BY, SELECTED_BY, MEMBER_OF_BOOK;
- EVALUATED_IN, HAS_METRIC, PAIRED_AGAINST;
- GRADED_IN_CONTEST, DERIVED_FROM_OUTCOME;
- OBSERVED_IN_WINNER_RELEASE, EVALUATES_BUNDLE, DECIDES_ON_BUNDLE;
- RETRIED_AS, VERIFIED_BY; and
- HAS_INFERRED_DEFENDER_EXPOSURE.

Do not create a factual COVERED_BY relationship without a direct assignment
source.

### L4. Cardinality and storage policy

The registry’s current three-lineup-per-arm sample is insufficient for corpus
intelligence. A post-v12 capacity receipt must choose exactly one graph schema:

- **full-lineup release:** one node per accepted roster plus the relationships
  below, permitted only when a full-scale load stays below the preregistered
  heap/disk safety fraction, rebuild deadline, and p95 query budget; or
- **summary-only release:** preset/run/book/cohort/trait aggregates and selected
  roster detail only, with full-corpus lineup/network endpoints visibly
  unavailable.

For a full-lineup release, use:

- one Lineup node per canonical accepted lineup;
- nine bounded lineup-player relationships;
- compact structural/trait measurements;
- admitted/selected relationships for registered experiments;
- sparse tail/cohort memberships;
- score/event object pointers rather than per-world graph nodes; and
- query-specific summary nodes when the full relationship would be
  unnecessarily quadratic.

Run the cardinality/byte/load/query census before provisioning and freeze its
thresholds in the capacity receipt. Do not infer production capacity from
task-0 fixtures or silently load a partial “full” graph.

### L5. Loader and release

- Provision TLS and separate bootstrap/writer/reader credentials.
- Validate graph schema and uniqueness constraints.
- Stream evidence rather than constructing a full in-memory plan.
- Load through deterministic batched UNWIND transactions.
- Publish checkpoint receipts and one terminal load receipt.
- Validate exact node/edge/property/namespace counts and source-pointer hashes.
- Use blue/green graph releases or namespaces.
- Before writing any new node/relationship family, publish a versioned graph
  deployment manifest that binds the predecessor content release, exact
  allowlisted namespaces, schema/constraint migration, source release, and
  authorized outcome scope. Realized namespaces remain closed until the
  corresponding OutcomeRelease is accepted.
- Compare a canonical query-result hash suite before switching the UI pointer.
- Prove a zero-state rebuild yields the same terminal census and query hashes.

### L6. Query catalog

Provide parameterized, bounded queries for:

1. fill-by-admission-by-retrieval metric comparison;
2. 2×2×2 fill/admission/retrieval decomposition and interactions;
3. candidate funnel from solves to realized tail;
4. lineup provenance and why-selected trace;
5. winner versus matched-control trait enrichment;
6. simulated versus realized tail concordance;
7. matchup/easy-coverage distributions and completeness;
8. player/pair/team/game tail relationships;
9. outcome-space redundancy and portfolio clusters;
10. source quality/missingness by slate/season;
11. science/verifier/deployment/preset/run lineage and attempts;
12. contest rank/duplication/payout when available; and
13. promotion status and evidence gaps.

No client-provided Cypher is permitted.

### L7. Exit criteria

- graph release rebuilds deterministically from GCS/BigQuery;
- every metric resolves to an exact source identity;
- no raw matrix/licensed/outcome body appears in graph properties;
- conflicting identities fail, identical reloads are idempotent;
- reader cannot write and loader cannot activate production policy;
- query results reconcile with canonical fixtures; and
- graph failure cannot block Foundry computation or lineup export.

## 20. Workstream M — FastAPI and React product

### M1. Decouple product deployment from science

The web application gets a separate image and release cadence. UI/API changes
must not alter the Foundry worker/verifier image or science identity.

### M2. Versioned read APIs

Keep the current bounded projection endpoint for compatibility, then add
paginated endpoints such as:

- /api/v1/foundry/status
- /api/v1/foundry/releases
- /api/v1/foundry/presets
- /api/v1/foundry/experiments
- /api/v1/foundry/runs
- /api/v1/foundry/evaluations
- /api/v1/foundry/strategy-bundles
- /api/v1/foundry/winner-releases
- /api/v1/foundry/experiments/{id}/metrics
- /api/v1/foundry/books/{id}
- /api/v1/foundry/slates/{slate}/lineups/{lineup}
- /api/v1/foundry/cohorts/compare
- /api/v1/foundry/traits/enrichment
- /api/v1/foundry/lineup-network
- /api/v1/foundry/source-coverage
- /api/v1/foundry/receipts/{id}

Every response carries:

- API schema/version and response type;
- data/graph release identity;
- winner-release identity whenever a winner observation/cohort/denominator is
  present;
- generated time and staleness;
- evidence tier and authority;
- simulated/realized scope;
- discovery/evaluation fold;
- denominators and missingness;
- exact metric definition; and
- source/provenance link.

Enforce catalogued queries, Pydantic schemas, pagination, row/byte/time limits,
bounded filters, ETag/content-hash caching, and no arbitrary Cypher.

Within `/api/v1`, additive optional fields require contract tests and a dated
deprecation notice; removing/renaming fields or changing metric semantics
requires `/api/v2` or a new versioned response media type. Data-release changes
never substitute for API-contract versioning.

The app authenticates users and authorizes research, outcome, and operator
views separately. `/receipts/{id}` resolves only to an allowlisted sanitized
metadata projection—identity, type, status, hashes, time and redacted
provenance—not raw receipt bodies. Source links are opaque application routes,
not bucket paths, and the app receives no general evidence-bucket or licensed
source access.

Publish each UI materialization under an immutable `ui-release/<id>` prefix.
A generation-matched operational pointer selects the active verified release
without changing scientific evidence; every pointer transition has a
create-once activation/rollback decision. Replace the current fixed
`CORPUS_RESEARCH_UI_PROJECTION_PATH` gradually with this pointer contract,
retaining it as migration fallback. The app caches the last verified release,
shows its age during graph/materializer outage, warns after the registered
staleness target, and disables affected drilldowns rather than serving an
unverified newer projection.

### M3. React implementation

The current vendored React 18/HTM page may remain as the compatibility shell
while the proper frontend is completed. Standardize the target Vite scaffold
on one reviewed React major—React 19—removing mixed React 18 runtime assets only
after parity. The target is:

- React + TypeScript;
- one React/runtime version, committed package-lock.json, and reproducible
  npm ci;
- Vite or the repository’s selected deterministic bundler;
- generated typed API clients or checked response schemas;
- one reviewed visualization library;
- a Node build stage that copies only compiled assets into the app image;
- no Node runtime in production; and
- reversible route-by-route cutover after parity.

Parity covers every current route and action: Season, Lineups, Defense,
Market, Watchlist, About, Corpus Research, live Classic/Showdown construction,
downloads, empty/error states and navigation. Add deep-route refresh handling,
base/static URL tests, and a wheel/container packaging test proving compiled
assets declared through pyproject.toml are present. Remove legacy JS/CSS only
after route/action parity, optimizer-service parity and a tested rollback.

Frontend build tooling belongs only to the app image and must not restore the
old deployment coupling.

### M4. Required views

1. **Readiness/status:** accepted slates, missing cells, verifier state,
   outcome readiness, graph/UI release, and current authority.
2. **Experiment matrix:** fill × admission × retrieval heatmap with selectable
   metric/fold/season.
3. **Paired outcomes:** per-slate deltas, win/tie/loss, season summaries,
   influence and uncertainty.
4. **Tail curves:** 187–240 thresholds, expected maximum and contest-relative
   metrics.
5. **Candidate funnel:** visits → unique → admitted → selected → realized
   thresholds.
6. **2×2×2 decomposition:** fill, admission, retrieval, all interactions, and
   C, S and C-S.
7. **Cohort comparison:** winners, matched controls, simulated tail, realized
   corpus tail and selected books with denominators.
8. **Trait explorer:** boom, topology, role, matchup, ownership, salary,
   pairs/correlation and missingness.
9. **Lineup detail:** roster, salary, provenance, source arms, simulated
   distribution, annotations, selection trace and realized outcome.
10. **Matchup views:** role × defense map, lineup matchup strip, inferred
    defender involvement, source-grain labels.
11. **Portfolio structure:** score-correlation/event clusters, roster overlap,
    exposures and effective rank.
12. **Strategy lineage:** preset → experiment → snapshot → book → grade →
    decision.
13. **Source quality:** completeness by slate/season/source/grain.
14. **Contest outcomes:** rank, duplication, payout and ROI only when complete.

### M5. Visual truth rules

- Simulated, realized, exploratory, retrospective, held-out, prospective,
  limited-deployment and promoted evidence use distinct persistent badges.
- Every chart exposes its denominator and source release.
- Missing data render as missing/partial, never as zero.
- A 194 metric is not labeled a win probability.
- Inferred defender exposure uses dashed/qualified relationships.
- Small samples and unstable effects show uncertainty/support.
- A graph or projection outage shows last verified release and stale time.

### M6. UI tests and exit criteria

- npm ci, typecheck, unit tests and production build pass;
- API/OpenAPI contract tests pass;
- component tests cover loading, empty, partial, stale, missing and
  unauthorized states;
- browser smoke covers major routes and responsive layouts;
- fixture chart values exactly match API payloads;
- authorized read-only outcome projections are tested, while no route can
  bypass the outcome lease/unblinding boundary, mutate outcomes, or activate a
  production strategy;
- app stays healthy when Neo4j is unavailable and marks Foundry drilldowns
  degraded; and
- legacy routes are removed only after parity and a reversible cutover.

## 21. Workstream N — user workflow, automation, and observability

### N1. Preset, run, evaluation, and promotion lifecycles

Keep lifecycle state on the object that actually changes:

- **Preset:** draft → validated → immutable versioned → superseded. One preset
  may participate in many experiments and never becomes “graded.”
- **ExperimentManifest:** draft → frozen/published → cancelled/superseded.
- **Run:** planned → running → terminal accepted/failed, with immutable
  attempts and one accepted result pointer per logical task.
- **Evaluation:** books frozen → graded → accepted/rejected/inconclusive
  disposition, with evidence class and outcome release.
- **StrategyBundle:** nominated → shadow candidate → Tier-P limited-deployment
  approved (optional capped allocation) → fully promoted or
  rejected/superseded. Every nonzero real allocation and every scale change
  requires its own operator-approved Tier-P receipt.

No graph/UI action changes lifecycle state without a create-once authoritative
registry receipt.

### N2. Run workflow

Provide one documented CLI/API workflow:

- validate-manifest;
- plan/dry-run;
- publish-manifest create-once;
- launch;
- status;
- resume eligible failures;
- verify;
- finish;
- materialize evidence;
- register;
- project graph/UI; and
- grade outcomes under a separate explicit command.

Dry-run performs zero writes and reports:

- task/cell count;
- source/world reads;
- estimated compute/storage;
- supported methods and parameter values;
- fold/candidate-origin rules;
- output paths;
- outcome authority; and
- expected receipts.

### N3. Automatic experiment recording

Every experiment automatically records:

- all requested presets, including failed/poor exploratory ones;
- engine and input identities;
- exact task/cell lattice;
- authority tier;
- status and attempts;
- metrics and uncertainty;
- selected books/traces;
- artifacts;
- costs/runtime; and
- disposition.

This prevents manual survivorship bias and lets the knowledge graph answer
which strategies were tried, when, on what data, and with what result.

### N4. Monitoring and alerts

Metrics:

- manifest validation failures;
- task queue/running/accepted/failed/verifier counts;
- slate/cell latency;
- solver optimality/timeouts;
- lineup-world throughput;
- shard cache/reuse;
- retrieval runtime/memory;
- outcome grade completeness;
- Neo4j load throughput/failures;
- UI projection age;
- API p95/error rate;
- prospective standings capture; and
- storage/compute cost by experiment.

Alerts:

- immutable artifact mismatch;
- nondeterministic attempt digests;
- scientific failure;
- stalled heartbeat;
- incomplete registered cell lattice;
- outcome read before books are frozen;
- stale graph/UI projection;
- failed graph release comparison;
- missing post-contest standings capture; and
- unauthorized policy/permission drift.

Operational telemetry is not part of the scientific digest.

### N5. Telemetry contract

Define `foundry-run-event/v1` with event ID, run/experiment/logical-task/
attempt IDs, stage, state, monotonic sequence, event and observed timestamps,
heartbeat/progress counters, resource/cost labels, failure class, artifact
pointer and schema version. Append canonical state-transition events to a
durable GCS ledger; Cloud Logging/Monitoring is a convenient non-authoritative
transport and alert source. Terminal state comes only from immutable accepted
or failure receipts.

Freeze stage-specific stale thresholds for generation, verification,
retrieval, grading, graph loading and UI materialization; define aggregation,
deduplication, clock-skew, retention and late-event laws. Attach experiment,
task and attempt attribution as Cloud Run labels where supported and always in
event payloads, so per-experiment cost remains reconstructible on shared jobs.

## 22. Implementation sequence and parallel tracks

The estimates below are focused engineering ranges, not promises. The first
corrected comparative scores are deliberately separated from the larger
platform/product program.

After Gate G0, use non-overlapping ownership lanes:

- **evidence custodian:** terminal v12 index/disposition, outcome lease and
  HANDOFF authority; only this lane writes v12-derived acceptance indexes;
- **retrieval/science:** new R6 runner, fold safety, books, traces, statistics
  and grading contracts;
- **engine/platform:** Foundry Next schemas, component releases, jobs,
  checkpoints, principals and telemetry;
- **data/intelligence:** canonical evidence, winner/source reconciliation,
  fill/admission features, matchups and contest capture; and
- **product:** graph release, API, immutable UI materialization and React.

Each lane owns separate new files/namespaces, publishes a contract before a
consumer integrates it, and never edits another lane’s frozen artifact to make
integration pass. Merge in dependency order: evidence → science contracts →
accepted facts → graph/API projections → UI.

### Wave 0 — terminal boundary and seal

**Dependency:** active v12 lanes become terminal.
**Estimated focused work:** several hours after terminal state.

1. Complete Gate G0.
2. Publish the combined v12 panel index from both terminal lane
   receipts/dispositions.
3. Preserve v6-v11 diagnostics separately.
4. Confirm no R6 realized outcome has been read.
5. Create the R6 non-result disposition.

**Exit:** immutable, replayable v12 substrate; no ambiguity about R6.

### Wave 1A — first trustworthy simulated books and comparative scores

**Critical path:** B1–B7 and the minimum F1–F4 contracts.
**Estimated focused work:** same working day if artifacts match expected
schemas. This requires one narrow corrected `foundry-analysis` image/release
and stable reusable analysis job because the corrected runner is not inside the
immutable v12 image; it does **not** rebuild, redeploy, or mutate the v12
generator.

> **[v12 operator review — 2026-08-24]** The real-artifact outcome-blind
> smoke in step 8 is the load-bearing step — treat it as non-negotiable.
> Of the thirteen v6→v12 image spins this cycle, several were consumed by
> composite code paths that had only ever run against synthetic fixtures
> before meeting real artifacts in cloud. The "same working day" estimate
> is achievable only if the smoke runs against an already-accepted v12
> slate before the release is certified, and if the B1–B5 authoring
> starts during the remaining lane hours (it is v12-inert). Two dialects
> exist in the accepted artifacts (`variant_result_objects` retrieval
> carriers versus `variant_results` parametric carriers) — the D5 import
> adapter must handle both; `corpus_parametric_snapshot.py` already does.

1. Implement the new all-seven runner while preserving the frozen runner.
2. Add complete origin masks and held-out-safe cross-fitting.
3. Add the primary score-blind size/composition-matched control family.
4. Retain exact fold books, final-fit books and marginal traces.
5. Add durable CLI/publisher/completion receipt.
6. Implement the minimal D5 v12-import compatibility adapter once and require
   both R6 reconstruction and later Foundry Next import to use it.
7. Build/certify the narrow analysis release and bind its stable execution job.
8. Smoke one real accepted v12 slate outcome-blind.
9. Materialize/reconstruct the accepted slate super-pools through that adapter.
10. Run the full registered simulated surface and freeze final-fit books.
11. Publish initial comparative simulated metrics to bounded files/API
    projection.

### Wave 1B — governed realized grading

**Dependency:** every intended arm/R6/neutral book is frozen before the first
v12 actual-score access. **Critical path:** J1–J3 plus the R6-v2 outcome law.

1. Implement and reconcile the arbitrary-book grader against v1 arm books.
2. Freeze the outcome query, complete book catalog and evidence label.
3. Acquire the historical-outcome lease if authorized.
4. Grade every frozen book once and publish the retrospective scorecard.
5. Release the lease and record the one-read disposition.

Neo4j and the full React application do not block Wave 1.

### Wave 2 — reusable manifest engine and deployment simplification

**Tracks:** C, D, E and the non-UI core of N1–N5 in parallel with Wave 1
after v12 seal.
**Estimated focused work:** 2–4 focused days.

1. Define E/V/P policy and versioned contracts.
2. Create science/verifier releases, deployment attestations and method
   catalogs.
3. Implement logical tasks, attempts, acceptance pointers and checkpoints.
4. Split images/build gates and exclude reports from contexts.
5. Pre-provision stable service accounts/jobs.
6. Implement task arrays, bounded parallelism and resumable controller.
7. Import v12 through the compatibility adapter.
8. Implement canonical preset/run/evaluation/bundle lifecycle receipts,
   CLI/status and the durable run-event/heartbeat ledger.
9. Prove configuration-only execution, status, retry and cost attribution end
   to end.

**Exit:** new supported preset → manifest → result without deployment.

### Wave 3 — canonical evidence and deep intelligence

**Tracks:** F, G, H and I.
**Estimated focused work:** 3–7 focused days plus bounded compute.

1. Publish canonical lineup/membership/simulation/trace products.
2. Reconcile the 68-row winner collection and governed 51-winner analytic
   release before winner modeling.
3. Expand winner, realized/simulated tail, boom, matchup, pairing and
   correlation features across all accepted slates.
4. Complete source-universe coverage diagnosis.
5. Implement F0–F4 and negative fill presets.
6. Implement admissions and all current retrieval policies.
7. Add near-optimal, unique-fill, scenario and portfolio-column generation.
8. Run Tier E screens and nominate bounded Tier V families.

**Exit:** jointly designed fill/admission/retrieval candidates with complete
mechanism and support evidence.

### Wave 4 — Neo4j, API and UI

**Tracks:** L, M and graph/UI projections plus alerts from N; the registry,
run workflow and telemetry core already exist from Wave 2.
**Estimated focused work:** 3–6 focused days, with basic views earlier.

1. Provision and secure the dedicated graph.
2. Publish the graph namespace/migration authorization and choose full-lineup
   versus summary-only schema from the capacity benchmark.
3. Load release/preset/run/snapshot/book lineage and metrics.
4. If authorized by capacity, add chunked full-lineup/trait relationships.
5. Add versioned paginated APIs and immutable UI-release pointer/fallback.
6. Finish React 19/TypeScript parity for every legacy route and action.
7. Split the live optimizer only after service parity and rollback tests.
8. Add deep phenotype/matchup/network/source-quality views.
9. Prove zero-state graph rebuild and UI degradation behavior.

**Exit:** complete, trustworthy research observatory that does not control
science or live policy.

### Wave 5 — historical nomination and Week-1 release

1. Freeze a bounded retrospective Tier V comparison family.
2. Run outer season/slate evaluation and one controlled grade.
3. Nominate at most one primary and one distinct fallback.
4. Rehearse stored-slate generation through legal DK CSV.
5. Freeze Week-1 source, science release, exact entry budget, presets,
   machine-evaluable fallbacks, integer allocation, books and tie laws by T-3.
6. Issue an explicit Tier-P limited-deployment receipt for any nonzero
   challenger allocation; otherwise mark it shadow-only.
7. Run incumbent and capped/shadow challenger from the same pre-lock snapshot.
8. Capture complete contest standings/payout after settlement.
9. Grade fill, admission and retrieval separately before Week-2 changes.

## 23. Critical-path priority

If time becomes constrained, execute in this order:

1. seal v12;
2. disposition and correct R6;
3. publish simulated comparative books/traces and scores;
4. freeze every final-fit/neutral book, then run realized grading;
5. make retrieval configuration-only;
6. publish canonical evidence tables;
7. implement/compare high-value fill and admission presets;
8. expose basic API/UI comparisons;
9. load Neo4j deep intelligence;
10. complete contest-field/payout features prospectively.

Do not delay items 1–5 for graph design, visual polish, or a complete field
model. Do not skip held-out safety, exact books, or outcome freezing to gain
speed.

## 24. File-level implementation map

This is a planning map; the implementing model should confirm exact call
graphs before editing.

| Area | Existing files to preserve/refactor | Likely new or versioned surface |
|---|---|---|
| Governance | CLAUDE.md, README.md, AGENTS.md, HANDOFF.md | docs/foundry-governance.md, dated handoff archives |
| Engine contracts | corpus_parametric_batch.py, corpus_batch_evidence_contract.py | Foundry Next science/verifier/deployment/preset/experiment/attempt/book contracts |
| Generation/scoring | corpus_legal_feasibility.py | manifest adapter, checkpointed task executor, method catalog |
| Independent verification | corpus_legal_feasibility_verifier.py | versioned accepted-task/run verifier and science-release compatibility verifier |
| v12 import | corpus_parametric_snapshot.py | v12 panel index and canonical super-pool adapter |
| Retrieval | corpus_retrieval_engine.py, corpus_batch_retrieval_runner.py | corrected versioned batch runner, publisher and completion |
| Realized grading | corpus_realized_grading.py, corpus_realized_*transport.py | arbitrary-book grader and contest-equity grade |
| Phenotypes | corpus_gt200_analysis.py, b1_corpus_tail.py | canonical lineup evidence and feature/cohort builders |
| Matchups | receiver_matchup_*, rb_qb_matchup_*, matchup_tail_model.py | all-slate annotation adapter and guarded admission/fill features |
| Registry | corpus_strategy_registry.py, corpus_strategy_registry_release.py | distinct admission objects and generic cell/book releases |
| Graph | corpus_retrieval_neo4j.py, corpus_neo4j_extensions.py, corpus_neo4j_transport.py | streaming/chunked loader, matchup/contest projections, query catalog |
| API | app/corpus_research.py, corpus_research_ui_bridge.py | paginated store/service and versioned response schemas |
| React | app/static/corpus_research.js/css, frontend scaffold, pyproject.toml | React 19 TypeScript/Vite app, package-lock.json, packaged compiled bundle and legacy parity suite |
| Deployment | Dockerfile.corpus-research-expansion, cloudbuild.corpus-research-expansion.yaml, run_corpus_parametric_transport.py | split Dockerfiles/builds, stable manifest runner/controller and authenticated live-optimizer service |
| Ops | scripts/foundry/*, chain_status.sh | generic CLI/status, legacy v12 archive marker |
| SQL/data | existing raw/features/predictions DDL | research lineup/simulation/trace/outcome/contest products |

Foundry Next should use a coherent package boundary rather than continuing
to add version-specific shell files and 1,000-line transports. Keep legacy
commands for evidence replay, not for new experiment development.

## 25. Validation matrix

### Contract and configuration

- unknown methods/parameters/types/domains fail before launch;
- preset order does not change semantic hashes;
- canonical JSON rejects duplicates and nonfinite values;
- E/V/P authority combinations are valid and mutually enforced;
- engine/preset/experiment/book identities compose and replay.

### Source and PIT

- exact-generation reads and content hashes;
- complete source-universe coverage report;
- future/post-lock columns and timestamps rejected;
- missing optional sources remain missing;
- licensed raw rows never leave approved stores.

### Generation and solver

- DK legality and salary/roster constraints;
- solver optimum and tie/second-best evidence;
- producer/verifier independent agreement;
- near-optimal/no-good/unique-fill laws;
- identical results across parallelism and retry;
- no completion-order influence.

### Scoring and evidence

- every unique lineup × every registered world;
- roster/instance/slot/legality identity mapping and cross-arm deduplication;
- row/player/world ordering and dtype/shape checks;
- event sidecars exactly reproduce matrices;
- v12 imported hashes match accepted artifacts;
- tampering and truncation fail closed.

### Admission and retrieval

- all registered methods run;
- exact entry count and uniqueness;
- held-out candidate identities and scores excluded;
- all score-derived features and tie metadata are fold-local/identity-only;
- matchup admission is compared with deterministic size/composition-matched
  score-blind controls;
- same-pool retrieval comparisons;
- equal-budget fill comparisons;
- complete marginal trace replay;
- missing matchup support and admission cap behavior;
- negative controls behave as designed.

### Realized and contest grading

- books frozen before outcome access;
- each distinct lineup scored once;
- original arm grades agree across v1/v2;
- outcome schema isolated;
- standings/rank/duplicate/payout reconciliation;
- accepted/superseded capture and observed/counterfactual payout laws;
- raw contestant identifiers cannot enter graph/UI projections;
- partial contest data cannot produce rank/ROI claims.

### Registry, graph and UI

- complete release preflight before writes;
- graph namespace migration authorization and full-versus-summary schema gate;
- idempotent graph rebuild and conflicting-identity rejection;
- no forbidden raw/matrix/outcome fields;
- API bounds, schemas and query catalog;
- chart/fixture parity and authority labels;
- stale/degraded graph behavior;
- no run/policy mutation route.

### Operations

- fault injection at producer/verifier/publisher/graph stages;
- bounded eligible retry and non-retriable failure;
- task-array quota and cost benchmark;
- heartbeat/stall detection;
- no IAM change or deployment during a preset experiment;
- clean rollback/fallback rehearsal.

## 26. Risk register

| Risk | Consequence | Mitigation |
|---|---|---|
| v12 contamination | Invalidates the expensive baseline | Gate G0; no in-place repair; derived Foundry Next namespace only |
| R6 mislabeled as valid | False matchup conclusion | Formal non-result disposition and freshly frozen R6-v2 |
| Matchup gain is only shortlist pruning | False mechanism claim | Size/composition-matched score-blind controls and one frozen panel statistic |
| Held-out identity leakage | Optimistic simulated evaluation | Complete origin masks and fold-specific candidate exclusion |
| Parameter freedom becomes panel mining | Overfit strategy | E/V/P tiers, full tried-grid registry, outer/prospective confirmation |
| Retry enables cherry-picking | Biased acceptance | Logical task identity, bounded failure classes, accepted digest equality |
| Parallel nondeterminism | Unreproducible books | Content-based IDs/ties, canonical aggregation, parity tests |
| Stable IAM is too broad | Security exposure | Dedicated buckets/principals, create-only outputs, periodic drift audit |
| Incomplete player universe | Missing high-tail lineups | Separate source-universe-v2, explicit scope, no silent imputation |
| Simulator misspecification | Optimizes unreal worlds | Mixed fill sleeves, realized cross-fitting, contest-relative/prospective grade |
| Winner overfitting | Copies sparse historical quirks | Same-slate controls, shrinkage, no identity coefficients, hedge doses |
| Winner authority mismatch | Wrong denominator or roster facts | Reconcile 68-row collection and immutable governed 51-winner release |
| Matchup source sparsity | Misleading favorable counts | Continuous scores, completeness gates, missingness and grain labels |
| Large matrix/graph scale | Cost or memory failures | Chunked GCS matrices, sparse bitmaps, graph summaries, capacity benchmark |
| Graph becomes authority | Unsafe feedback loop | Rebuildable read-only projection, no run/promotion controls |
| Contest-data privacy leak | Exposes names or persistent entry IDs | Restricted raw store; aggregates and salted release-scoped IDs only |
| UI overstates results | Bad operator decision | Authority badges, denominators, definitions, uncertainty and source links |
| Missing historical fields | False rank/ROI claims | Explicit unavailable state; prospective complete capture |
| Build coupling returns | Slow iteration | Split images, component inventories, config-only manifests |
| Evidence bloats Git/images | Slow builds and confusion | GCS authority, small indexes, selective build context, archived handoff |
| Optional source outage Week 1 | Missing/changed lineups | Frozen deterministic incumbent fallback and rehearsal |

## 27. Week-1 release packet

Complete by T-3 days:

- science/verifier release IDs, images and deployment-attestation ID;
- exact source/as-of and source-universe identities;
- contest and final entry budget;
- exact-N composite-versus-incumbent historical replay, integer sleeves, joint
  uniqueness, collision/replacement and conditional-selection laws;
- incumbent, challenger and fallback fill/admission/retrieval preset IDs;
- model/feature/annotation versions;
- missing-data fallbacks;
- machine-evaluable fallback triggers and shadow-only rule;
- candidate and book hashes;
- deterministic tie and ordering laws;
- legality, uniqueness, availability and DK export receipt;
- stored-slate end-to-end rehearsal;
- historical outer-fold scorecard;
- known limitations and unavailable contest metrics;
- rollback instruction;
- no-change boundary after freeze; and
- explicit operator decision/authority, including a Tier-P limited-deployment
  receipt for every nonzero challenger allocation.

On Week 1:

- generate incumbent and challenger from the same snapshot;
- retain all source candidates, scores, books and traces;
- fall back exactly as frozen if an optional source is unavailable;
- do not allow the graph/UI to mutate the books;
- download complete target-contest standings and payout evidence immediately
  after settlement; and
- append the outcome before proposing Week-2 adjustments.

## 28. Handoff and implementation instructions

The implementing model should:

1. read the current HANDOFF.md immediately before any action because v12 status
   will have changed since this plan was written;
2. verify Gate G0 rather than assuming “tests completed” means both valid
   completeness receipts or terminal non-completion dispositions exist;
3. inspect and preserve the dirty worktree and all concurrent-agent changes;
4. begin with the R6 disposition and corrected real-artifact smoke;
5. use apply_patch for repository edits and targeted tests;
6. stage/commit only owned files, update HANDOFF.md at phase exits, and push
   durable milestones when safe;
7. never alter accepted v1/v12 artifacts or validators to make new code pass;
8. prefer generated catalogs/contracts over duplicated hard-coded counts;
9. keep the first-score path independent from Neo4j/UI; and
10. stop and report if a required realized outcome has already been read or an
    accepted artifact identity differs from this plan’s assumptions.

## 29. Immediate next actions after v12 terminal acceptance

The first implementing turn should perform only these actions:

1. exact-read both lane terminal receipts/dispositions and create the combined
   panel census;
2. write the R6 non-executable disposition with proof of no realized read;
3. write tests that fail on the existing three-selector slice and R4-only
   candidate leakage;
4. implement a new all-seven dispatch, complete origin masks, fold-local
   derived inputs, exact book/trace publication, and a small durable CLI;
5. add and test score-blind size-matched admission controls;
6. run focused offline tests;
7. build/certify the narrow analysis release and run one outcome-blind
   real-v12-slate smoke;
8. freeze R6-v2: its 14-cell execution lattice, single primary mechanism
   contrast, secondary family, all-block final-fit law and every neutral
   replicate;
9. execute the corrected retrieval suite from cached v12 artifacts;
10. publish exact books and comparative simulated metrics; and
11. only after verifying every intended book, authorize the governed realized
    grade.

This sequence produces trustworthy comparative scores quickly and establishes
the substrate for every later fill, matchup, graph and UI improvement.
