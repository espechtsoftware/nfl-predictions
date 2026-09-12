# R6 Scheduler and Matchup Source-Batch Independent Review

**Date:** 2026-08-27
**Review type:** Read-only adversarial design and implementation review
**Disposition:** One P0 authority defect blocks treating the matchup source batch as a trusted publication. Two P1 defects block strong runtime-lineage and bounded-publication claims. The legal scheduler remains an honest generic, promotion-ineligible building block, but it is not yet an outcome-free feasible-optimum benchmark.

## 1. Executive verdict

The reviewed slice has several strong fail-closed properties: it replays the candidate authority before publication, uses create-once leaf publication, reopens dependent objects, publishes roots last, and does not directly read realized outcomes, world matrices, or result-object bodies in the matchup source-batch path.

However, the trusted matchup publisher does not actually replay the capture plan's authoritative Git predecessor chain. It validates the current plan file and accepts caller-supplied bytes for the adapter final-release lock. That leaves a coherent-splice path in the most important source-authority seam. Until this is corrected, the batch root cannot honestly certify that its plan, adapter lock, G0 authority, implementation measurements, and Git origin came from one trusted generation-pinned lineage.

The implementation also measures dependency files in the worktree but calls the result an executed dependency closure without proving that those files are the Python modules actually loaded in memory. Publication reads are bounded and precharged, but writes are not cumulatively precharged or restricted to an exact expected URI inventory. These are P1 issues because they weaken runtime identity and bounded side-effect claims even after the P0 authority seam is repaired.

The legal scheduler/release slice is materially more conservative in its claims. It explicitly marks caller-provided matrix data as unattested and promotion-ineligible and labels its quantities as certified bounds rather than exact optima. That honesty should be preserved. It should not be promoted to a true-top-200 or feasible-optimum benchmark until a trusted point-in-time source/code/bank adapter and exact or independently certified comparison are added.

## 2. Scope and review constraints

The review covered exactly these implementation files:

- `src/nfl_dfs/research/corpus_r6_legal_scheduler_v1.py`
- `src/nfl_dfs/research/corpus_r6_legal_scheduler_release_v1.py`
- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py`
- `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v2.py`

And these focused tests:

- `tests/test_corpus_r6_legal_scheduler_v1.py`
- `tests/test_corpus_r6_legal_scheduler_release_v1.py`
- `tests/test_corpus_r6_matchup_batch_candidate_authority_v1.py`

Supporting source was inspected only where needed to evaluate the authority seam, especially:

- `src/nfl_dfs/research/corpus_r6_matchup_capture_plan_candidate_authority_v2.py`
- `src/nfl_dfs/research/corpus_r6_matchup_capture_plan_v1.py`
- `src/nfl_dfs/research/corpus_r6_matchup_component_publication_v1.py`

This was a read-only review. No code or `HANDOFF.md` was changed, no tests were run, and no cloud storage, outcomes, world bodies, or result bodies were accessed.

## 3. Severity summary

| ID | Severity | Finding | Release consequence |
|---|---|---|---|
| F1 | P0 | Trusted batch publication substitutes caller-supplied final-lock bytes for authoritative Git predecessor replay | Blocks trusted source-batch publication and promotion |
| F2 | P1 | “Executed dependency closure” proves worktree blobs, not the Python code actually loaded and executed | Blocks strong runtime/code-lineage claims |
| F3 | P1 | Publication writes lack cumulative precharge and exact-URI accounting | Blocks complete bounded-side-effect and exact-inventory claims |
| F4 | P2 | Persisted crash/resume language is broader than the implementation's same-commit reopening rule | Requires either narrower claims or a cross-commit reopening design |
| F5 | P2 | Focused tests bypass the production trust seam and omit adversarial partial-publication recovery | Leaves the highest-risk paths unproved |
| C1 | Capability limit | Generic legal scheduler accepts unattested caller matrix data and computes certified bounds, not exact feasible optima | Must remain descriptive and promotion-ineligible |

## 4. Findings

### F1 — P0: the trusted publisher does not replay the capture plan's authoritative Git predecessor chain

#### Evidence

`_trusted_capture_plan_lock_v1` reads and structurally validates only the current capture-plan file and checks the current repository HEAD:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:839-876`

The validator it invokes is explicitly structure-only:

- `src/nfl_dfs/research/corpus_r6_matchup_capture_plan_candidate_authority_v2.py:265-267`

The public batch API nevertheless accepts the adapter final-release lock's claimed commit and raw bytes from its caller:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:3073-3085`

Those caller values are passed into the internal build path:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:3120-3138`

They are then consumed by `_validate_plan_with_cached_authority` rather than being independently derived from the trusted Git lineage:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:1435-1496`

An existing authoritative helper already demonstrates the required stronger operation: it exact-reads the plan, every implementation measurement, the adapter final lock, and the G0 lock from claimed Git/current bytes:

- `src/nfl_dfs/research/corpus_r6_matchup_capture_plan_v1.py:1592-1671`

The reviewed batch publisher does not call that helper.

#### Why this matters

A tracked plan and a caller-selected final-lock byte string can be made internally coherent without proving that the subordinate final lock came from the plan's claimed Git predecessor or that its own G0 lineage is authoritative. Structural hashes prevent accidental corruption; they do not establish origin. This permits a law/plan/final-lock/code lineage splice at the publication boundary.

Because the terminal batch root presents this lineage as trusted authority, this is a P0 defect rather than merely missing metadata.

#### Required correction

1. Make `_trusted_capture_plan_lock_v1` invoke `reopen_capture_plan_lock_from_git_v1` through fixed, no-follow Git adapters.
2. Derive the adapter final-lock commit, raw bytes, G0 lock, and implementation measurements internally from the reopened authority.
3. Remove `adapter_final_release_lock_commit_sha` and `adapter_final_release_lock_raw` from the public trusted publication API.
4. Preserve the existing exact remote prerequisite preflight before backend construction or publication.
5. Bind the resulting replay receipt into the batch root and validate it during deep reopen.

#### Required adversarial test

Construct a plan and caller-supplied final lock that are structurally self-consistent but come from different commits or predecessor chains. The public trusted entry point must reject them without constructing the backend or publishing any object. Then prove that the same bytes succeed only when independently reopened from the plan-pinned Git lineage.

### F2 — P1: the “executed dependency closure” proves disk files, not loaded runtime code

#### Evidence

The dependency replay hashes and validates repository files:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:1323-1397`

The code-identity check likewise reasons about repository/source identity:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:1116-1177`

The orchestration subsequently calls mutable imported module globals:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:2840-2975`

The resulting root calls the measurement an executed dependency closure and makes associated claims:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:2090-2095`
- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:2132-2143`

No reviewed check binds `module.__file__`, `module.__spec__.origin`, loaded code objects, import-cache state, interpreter/image identity, or a fresh-process execution environment to the measured files.

The focused test itself demonstrates the distinction by monkeypatching callable module globals while the disk dependency closure remains unchanged:

- `tests/test_corpus_r6_matchup_batch_candidate_authority_v1.py:908-1030`

#### Why this matters

A clean, correctly hashed source tree does not prove that the process is executing those files. A stale import cache, editable installation from another path, injected module, or monkeypatched global can execute behavior not represented by the worktree closure. Calling this an executed closure overstates what the evidence proves.

#### Required correction

1. Run the trusted publication in a fresh, generation-pinned process or immutable image.
2. Before backend construction, verify canonical module origins for every executable dependency.
3. Bind interpreter/image identity, loaded module origins, and dependency measurements into a runtime attestation.
4. Make the terminal root reference that attestation and revalidate it during trusted reopen.
5. Until this is implemented, rename the field and claim to “source/worktree dependency closure” and keep runtime execution identity explicitly unattested.

#### Required adversarial test

Load or inject a dependency from a path whose repository file hashes still match the expected closure. The trusted entry point must deny execution before backend construction. Repeat for a monkeypatched callable, stale import, and mismatched image/runtime attestation.

### F3 — P1: writes are not cumulatively precharged or restricted to an exact URI inventory

#### Evidence

`GenerationPinnedGCSBatchTransportV1` maintains bounded read accounting:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:541-667`

`publish_create_once` enforces per-object limits and a three-attempt retry, but it does not maintain an atomic cumulative write-operation or write-byte budget:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:770-815`

Writes are authorized by broad prefixes rather than a precomputed exact URI set:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:776-781`

The public construction path supplies those prefix authorities:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:3103-3105`

The terminal root does not contain a transport work receipt or a complete exact inventory of every expected component, triple, receipt, member, source root, and batch-root URI:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:2069-2145`

#### Why this matters

The current fixed loops bound normal execution, but the transport itself does not fail closed against a regression, duplicated phase, injected runtime behavior, or altered loop that performs additional writes under an allowed prefix. Per-object retry limits are not equivalent to a cumulative side-effect budget. A broad-prefix authorization also cannot prove that the final published object set is exactly the planned inventory.

#### Required correction

1. Compute the complete expected URI inventory before backend construction.
2. Restrict each publication phase to its exact URI set, or to a phase-specific allowlist whose exact contents are rooted in the plan.
3. Atomically precharge cumulative write operations and bytes before each backend call, including failed conditional attempts.
4. Persist an immutable work receipt containing attempted operations, bytes, exact URI inventory, and completion state.
5. Require exact-set completion and exact reopen before any source or terminal root is published.
6. Bind the work receipt and inventory identity into the terminal root.

#### Required adversarial test

Attempt an extra write under an otherwise allowed prefix, exceed the cumulative operation limit through retries, and exceed the cumulative byte limit. Each case must fail before the backend call. Also omit one expected object and add one unexpected object; both exact-inventory checks must fail before root publication.

### F4 — P2: persisted recovery claims are broader than the same-commit implementation

#### Evidence

The capture-plan binding requires the current HEAD to equal the plan commit:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:1085-1112`

Dependency replay repeats that current-HEAD equality rule:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:1343-1352`

Deep reopen repeats both bindings:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:2403-2438`

The terminal claims describe partial resume/rebuild without stating the same-commit limitation:

- `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:2138-2143`

#### Why this matters

A partially published prefix cannot be resumed or deeply reopened after the repository advances to a later clean commit, even when every relevant implementation byte is unchanged. The operator must restore the original commit checkout. That can be a valid and desirable safety policy, but the persisted claim currently sounds more general than the actual contract.

#### Required correction

Choose and document one of two coherent contracts:

- **Same-commit-only recovery:** retain exact HEAD equality, explicitly persist that limitation, and require restoration of the original clean checkout for resume/reopen.
- **Immutable historical recovery:** reopen all required bytes from the original commit, prove allowed ancestry to the current validator, and bind an independent current-validator attestation without substituting current worktree files for historical authority.

Do not silently mix the two models.

#### Required tests

For same-commit-only recovery, show that an identical-tree later commit is rejected and that restoring the original commit allows exact resume. For historical recovery, show exact old-commit replay plus current-validator attestation and reject non-ancestor or byte-mismatched history.

### F5 — P2: focused coverage bypasses the production trust seam and omits adversarial crash/resume

#### Evidence

The public API test checks parameter names rather than exercising trusted publication:

- `tests/test_corpus_r6_matchup_batch_candidate_authority_v1.py:776-793`

The primary 54-task test enters a private injectable helper and monkeypatches candidate reopening, plan/binding validation, code validation, dependency replay, component publication, leaf operation, and source-root behavior:

- `tests/test_corpus_r6_matchup_batch_candidate_authority_v1.py:796-1030`

That test is useful for orchestration structure and ordering but cannot prove the real Git/GCS authority seam it replaces.

The reviewed batch tests do not inject a crash after each publication phase and then prove an exact-equal resume. They also do not prove rejection of an unequal preexisting object at every phase.

The legal release retry coverage exercises an already-complete rerun:

- `tests/test_corpus_r6_legal_scheduler_release_v1.py:333-355`

It does not cover receipt-only recovery or a crash immediately before root-last publication.

#### Why this matters

The strongest production claims are currently least represented in the focused tests. Extensive monkeypatching can prove pure orchestration logic while masking errors in authority reopening, capability denial timing, loaded-code identity, create-once collision behavior, and partial-publication recovery.

#### Required test program

Add a hermetic public-seam suite with fixed fake Git and generation-pinned object-store adapters. It must cover:

1. Authoritative capture-plan predecessor reopening and coherent-splice rejection.
2. Dirty worktree, wrong HEAD, wrong module origin, and runtime substitution denial before backend construction.
3. Crash after component publication, leaf receipt, triple/member publication, source-root publication, and immediately before terminal root publication.
4. Exact-equal resume at every crash point.
5. Unequal create-once collision at every object type.
6. Proof that source roots and the terminal root are published only after the exact subordinate inventory is reopened.
7. Cumulative read/write precharge and exact-URI inventory rejection.
8. Same-commit versus historical-commit recovery semantics, whichever contract is selected.

## 5. Capability boundary: legal scheduler and release

The reviewed legal scheduler is a generic scheduling/release primitive, not yet a trusted scientific benchmark.

The release accepts a caller-selected source identity/configuration and reads caller-provided `player_scores_micro` values:

- `src/nfl_dfs/research/corpus_r6_legal_scheduler_release_v1.py:522-529`
- `src/nfl_dfs/research/corpus_r6_legal_scheduler_release_v1.py:598-716`
- `src/nfl_dfs/research/corpus_r6_legal_scheduler_release_v1.py:1028-1067`

It correctly records that the caller assertion is not source attestation and remains promotion-ineligible:

- `src/nfl_dfs/research/corpus_r6_legal_scheduler_release_v1.py:253-261`
- `src/nfl_dfs/research/corpus_r6_legal_scheduler_release_v1.py:952-989`
- `src/nfl_dfs/research/corpus_r6_legal_scheduler_release_v1.py:1153-1173`

The scheduler reports certified upper/lower-bound quantities rather than claiming exact optima:

- `src/nfl_dfs/research/corpus_r6_legal_scheduler_v1.py:710-757`
- `src/nfl_dfs/research/corpus_r6_legal_scheduler_v1.py:1125-1198`

No reviewed path establishes an exact-optimum benchmark, a trusted point-in-time matrix authority, or an ex-ante development/validation/test bank split. Therefore:

- The scheduler may be used for descriptive engineering, bounded scheduling, and non-promotable diagnostics.
- Its outputs must not be described as true-top-200, exact feasible optima, outcome-free strategy evidence, or promotion-grade comparison evidence.
- Promotion requires a trusted point-in-time source and code adapter, plan-owned bank membership, a frozen stopping law, and either an exact solver or an independently checkable optimality certificate.

This is a capability limit, not evidence of dishonest current labeling. The current conservative labels are a verified strength and should remain fail-closed.

## 6. Verified clean findings

The following properties were supported by the reviewed code and should be preserved during remediation:

1. **Candidate authority is exactly replayed before publication.**
   - `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:2772-2785`

2. **Component publication performs exact provenance preflight before the first write.**
   - `src/nfl_dfs/research/corpus_r6_matchup_component_publication_v1.py:166-180`
   - `src/nfl_dfs/research/corpus_r6_matchup_component_publication_v1.py:395-427`

3. **Leaf objects use create-once publication and are exactly reopened before dependent publication.**
   - `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v2.py:91-115`
   - `src/nfl_dfs/research/corpus_r6_matchup_source_operator_v2.py:167-213`

4. **Source roots precede the terminal batch root, and the terminal root is published last with create-once semantics.**
   - `src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py:2957-3013`

5. **Persisted wrappers do not claim promotion or outcome authority.** The batch/operator and legal release preserve false promotion/outcome-authority posture.

6. **No reviewed matchup source-batch path directly reads world-matrix, realized-outcome, or result-object bodies.** The generic scheduler opens only its configured matrix and explicitly leaves that source unattested.

7. **Scheduler language distinguishes certified bounds from exact optima.** This avoids a scientifically material overclaim.

## 7. Remediation order

The safest order is:

1. **Close F1 first.** Replace caller self-attestation with authoritative generation/Git-pinned capture-plan predecessor replay and remove caller-supplied final-lock bytes from the trusted API.
2. **Close F2 before strengthening any execution claim.** Bind loaded runtime/module origin to the measured dependency closure, preferably in a fresh immutable process/image.
3. **Close F3 before broad publication.** Add exact URI planning, cumulative atomic write precharge, immutable work receipts, and exact-inventory completion gates.
4. **Resolve F4 contract language.** Choose same-commit-only or immutable historical recovery and align code, root claims, operator documentation, and tests.
5. **Build the F5 public-seam adversarial suite.** Exercise the real fixed adapters and every crash/collision boundary without monkeypatching away trust decisions.
6. **Only then extend scheduler capability.** Add a separate trusted point-in-time matrix/bank/code authority and exact benchmark path. Do not weaken the existing generic scheduler's promotion-ineligible labeling to do so.

## 8. Minimum release gates

The matchup source-batch slice should not be treated as trusted or promotion-capable until all of the following are true:

- The plan and every predecessor lock are independently reopened from a single generation/Git-pinned lineage.
- No trusted public API accepts subordinate authority bytes or hashes that it can derive itself.
- Capability and lineage validation complete before backend construction.
- Loaded executable origin is bound to the code/dependency identity claimed by the root.
- Reads and writes are both atomically precharged against plan-owned cumulative limits.
- Every permissible publication URI is known before publication and the completed set is exact.
- Crash recovery is proved at each root-last boundary with exact-equal resume and unequal-collision rejection.
- Recovery semantics across Git commits are explicit and tested.
- Deep reopen replays all of these authorities and exact inventories without caller substitution.

Separately, scheduler output must remain descriptive and promotion-ineligible until:

- Matrix/source authority is independently point-in-time pinned.
- Strategy and bank membership are plan-owned and frozen ex ante.
- Development, validation, and test banks are disjoint and authoritative.
- The stopping law is frozen before results.
- Exact optimality or an independently checkable certificate supports any feasible-optimum claim.

## 9. Scientific and operational interpretation

The reviewed work is useful infrastructure, but the trust labels must track what is actually proved.

- The matchup batch currently proves substantial structural consistency and careful root-last publication, but not one unspliceable authoritative lineage or one attested loaded runtime.
- The scheduler currently proves bounded calculations over the supplied matrix, not that the matrix is outcome-free, point-in-time authoritative, or an exact representation of the feasible lineup universe.
- Neither limitation prevents descriptive research. Both limitations prevent promotion-grade causal or comparative conclusions.
- Repairing these seams should strengthen authority without slowing ordinary experimentation: trusted authority can be frozen once, while many strategy runs consume that immutable authority without redeployment.

## 10. Review provenance

This report records an independent adversarial review of the listed untracked Lane 4 scheduler/source-batch slice as it existed on 2026-08-27. It intentionally separates defects from capability limits and records clean findings so corrective work does not discard protections that are already present.

No test result is asserted by this report. Validation of the report file itself is limited to line/word count, SHA-256, and whitespace checking as requested.
