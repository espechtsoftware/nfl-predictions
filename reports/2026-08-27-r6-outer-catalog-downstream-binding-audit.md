# R6 outer-catalog downstream binding audit

Date: 2026-08-27

Status: read-only design audit; no implementation or publication authority

Scope: fixed-G0 catalog recovery, fixed-G0 candidate authority, matchup
source-v2 capture/component/source/batch consumers, and the final one-slate
consumer

## Executive conclusion

The downstream chain is not yet bound to the new fixed-G0 catalog recovery
outer attestation.

The recovery contract is explicit: the outer attestation is the object a
downstream consumer must pin, and the older inner replay receipt is only a
non-authoritative deterministic projection
(`src/nfl_dfs/research/corpus_r6_fixed_g0_catalog_recovery_v1.py:13-15`).
The current candidate authority does the opposite. It accepts the old inner
receipt identity, validates that receipt as the terminal catalog authority,
derives the catalog release from it, and publishes a candidate root that
contains no outer identity. Every capture, component, source, batch, and
one-slate consumer that exact-reopens the candidate root therefore inherits
the old trust boundary.

This is a lineage-authority defect, not evidence that any currently published
lineup, score, or realized outcome is wrong. The safe correction is a schema
successor applied from the top of the chain downward:

```text
fixed recovery outer generation
        |
        | exact reopen + tracked recovery replay
        v
candidate authority root
        |
        | generation-pinned transitive binding
        v
capture plan -> component receipt -> source root -> batch root
                                                    |
                                                    v
                                           one-slate consumer
```

The minimum trustworthy rule is:

> No authoritative API accepts an inner receipt or catalog-release identity
> independently. It exact-reopens the fixed outer generation first and derives
> every inner identity from that validated outer body.

Do not publish another candidate/source root under the old schema. Freeze the
outer schema and its read-only downstream reopener first; then migrate the
candidate root, followed by each consumer in dependency order.

## Scope and method

This audit inspected the following implementation chain:

- `corpus_r6_fixed_g0_catalog_recovery_v1.py`
- `corpus_r6_fixed_g0_candidate_authority_v1.py`
- `corpus_r6_fixed_g0_candidate_authority_release_v1.py`
- `corpus_r6_matchup_capture_plan_candidate_authority_v2.py`
- `corpus_r6_matchup_component_publication_candidate_authority_v2.py`
- `corpus_r6_matchup_source_release_candidate_authority_v2.py`
- `corpus_r6_matchup_batch_candidate_authority_v1.py`
- `corpus_r6_matchup_source_operator_v2.py`
- `corpus_r6_matchup_source_v2.py`
- `corpus_r6_v2_matchup_candidate_authority_consumer_v2.py`
- their focused test modules

The audit was source-only. It did not access cloud objects, catalogs, world
matrices, historical outcomes, scores, production state, or graph storage. It
did not run tests or modify code. Line references describe the inspected
shared worktree. The recovery module was still an in-flight untracked schema;
for that file the named symbol is authoritative if later edits shift lines.

## The new outer contract

The current recovery draft has the right semantic direction:

- `_OUTER_FIELDS` carries the outer URI; implementation, review-lock,
  final-lock, and tracked-attempt bindings; exact inner release/receipt
  identities and internal hashes; and the ordered inner-object manifest
  (`corpus_r6_fixed_g0_catalog_recovery_v1.py:2161-2208`).
- `build_outer_attestation_v1` derives the inner identities and binds the
  inner receipt to the release (`:2211-2312`).
- It explicitly sets `downstream_must_pin_outer_identity=true` and
  `inner_receipt_self_authorizing=false` (`:2300-2301`).
- `validate_outer_attestation_v1` replays the tracked capability and attempt
  binding and validates the full outer semantics (`:2315-2423`).
- `exact_reopen_outer_attestation_v1` requires the outer identity, resolved
  capability, tracked attempt binding, and generation transport
  (`:2426-2442`).

The last point is the first downstream dependency. Candidate authority owns
generic `read_exact` and Git callbacks, while the current recovery reopener
expects recovery-specific capability, attempt-binding, and transport objects.
Before changing candidate code, expose one read-only recovery adapter that can
reconstruct those bindings from tracked Git evidence and generation-exact
reopen the outer without granting publication authority.

The outer currently records
`expected_terminal_prefix_object_count`, not an observed namespace census
(`:2192`, `:2295-2296`, `:2404-2407`). That wording is appropriate: a
constant expected count is a schema law, not proof that a cloud LIST observed
exactly that many objects.

## Exact old-inner trust map

### 1. Fixed-G0 candidate core: root authority defect

File: `src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_v1.py`

- The module documentation calls the fixed-URI inner receipt the licensed
  terminal catalog input (`:15-18`).
- `_reopen_catalog_terminal_authority` accepts
  `catalog_replay_receipt_identity`, exact-reads it, requires the legacy
  `fixed-g0-replay-receipt.json` URI, validates its fields, and returns it as
  authority (`:259-406`).
- `_reopen_catalog_panel` accepts the catalog release identity obtained from
  that receipt and requires the release to equal the receipt's identity and
  internal SHA (`:629-672`). It then reopens all structural catalogs.
- `_derive_material` accepts the old inner identity and calls both paths
  (`:1307-1378`).
- The resulting material records the old successor final-lock binding,
  inner receipt identity/SHA, and catalog-release identity/SHA, but no recovery
  outer identity (`:1444-1463`).
- The slate and panel derivation receipts repeat the old inner lineage
  (`:1511-1527`, `:1711-1732`).
- All three public authority functions still take the old inner identity:
  `derive_fixed_g0_candidate_material_v1` (`:1481-1495`),
  `build_fixed_g0_candidate_authority_v1` (`:1578-1595`), and
  `validate_fixed_g0_candidate_authority_v1` (`:1774-1849`).

Required correction: replace the authority role of
`_reopen_catalog_terminal_authority` with a recovery-outer reopen. Derive the
inner receipt and release identities only from the validated outer. The inner
bodies may remain validated compatibility projections, but they must never be
independently supplied authority inputs.

### 2. Candidate terminal release: old lineage is published

File:
`src/nfl_dfs/research/corpus_r6_fixed_g0_candidate_authority_release_v1.py`

- `_ROOT_FIELDS` contains `catalog_replay_receipt_identity` and SHA but no
  recovery outer identity or SHA (`:87-120`).
- `_build_root` copies those fields from the panel (`:624-637`).
- Structure validation hardcodes the legacy inner receipt URI
  (`:676-738`).
- The publisher accepts and passes the old inner identity into both candidate
  derivation and candidate authority construction (`:832-907`).
- The authoritative reopener obtains the old inner identity from the root and
  supplies it directly to core validation (`:1001-1103`).

Required correction: create a new candidate-root schema. It must carry the
outer object identity and outer internal attestation SHA, require the one fixed
outer URI, and reject the old root schema. Publish accepts only the outer
identity. Reopen must read and validate the outer before it reads any inner
object.

### 3. Candidate-rooted capture plan: caller still supplies inner bodies

File:
`src/nfl_dfs/research/corpus_r6_matchup_capture_plan_candidate_authority_v2.py`

- The module imports candidate authority but not recovery (`:25-29`).
- `_authority_binding` compares the candidate root's old inner receipt
  identity and SHA (`:133-218`).
- `_reopen_candidate_authority` compares plan
  `fixed_g0_replay_receipt_*` fields to that old root (`:328-366`).
- `build_capture_plan_lock_v2` publicly accepts the inner receipt body and
  identity plus catalog-release body and identity, then feeds all four into
  the v1 plan builder (`:369-437`).
- `validate_capture_plan_against_prerequisites_v2` repeats the same caller
  inputs during validation (`:440-505`).

Required correction: add outer identity/SHA successor fields and derive the
v1 compatibility receipt/release inputs from the exact-reopened candidate
authority. Remove the four public old-inner/release arguments. The existing
v1 plan projection can retain its inner fields only as values derived from the
outer-bound candidate root.

The configured tracked lock path is
`reports/corpus-r6-matchup-runs/20260826-r6-matchup-source-v2/capture-plan-candidate-authority-v2-lock.json`
(`:41-45`). That file did not exist in the inspected tracked reports. It must
be created only after a new outer-bound candidate root exists.

### 4. Component publication successor: receipt duplicates old authority

File:
`src/nfl_dfs/research/corpus_r6_matchup_component_publication_candidate_authority_v2.py`

- `_RECEIPT_FIELDS` stores candidate root/release plus the old inner receipt
  and catalog release, but no outer (`:47-74`).
- `_candidate_binding` derives and compares the old receipt and release from
  the candidate root/panel (`:128-252`).
- `_validate_publication_result` validates v1 output against those old
  identities (`:255-292`).
- The public publisher still accepts caller receipt/release bodies and
  identities (`:433-523`).
- Durable validation exact-reads the old receipt and release before replaying
  the component graph (`:694-763`).
- The final v2 validator compares the receipt's old identities back to the
  candidate root (`:1015-1067`).

Required correction: bind the component receipt to outer identity/SHA. Derive
all v1 compatibility inputs from the candidate reopen, remove caller-provided
receipt/release arguments, and require component outer == candidate-root outer
before opening any inner predecessor.

### 5. Candidate-rooted source release: old binding is propagated transitively

File:
`src/nfl_dfs/research/corpus_r6_matchup_source_release_candidate_authority_v2.py`

- Root/member additional fields carry candidate authority but omit the outer
  (`:46-82`).
- `_candidate_authority_binding` returns the old inner receipt identity/SHA
  from the candidate root (`:202-270`).
- `_build_release_v2` embeds the candidate-root binding but no direct outer
  binding (`:406-463`).
- `_validated_component_authority` carries the component receipt's old inner
  receipt/release identities and SHAs (`:466-575`).
- `_build_with_component_authority` compares the producer's old inner fields
  to that binding (`:592-655`).
- The ordinal reopener gets catalog authority only by reopening the candidate
  root; it compares candidate root/release fields but has no explicit outer
  equality check (`:1040-1090`).

Required correction: add outer identity/SHA to the top-level source root and
compare component, candidate, and source outer bindings during build and
ordinal reopen. Duplicating the outer on every member is not required for
security because members are hashed into the root; it may still be useful for
audit ergonomics.

### 6. Trusted 54-slate batch: public seam still accepts old inner data

File:
`src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py`

- Imports include candidate/capture/component/source successors but not the
  recovery module (`:54-74`).
- `_validate_plan_with_cached_authority`,
  `_publish_component_with_cached_authority`, and component validation accept
  or compare old receipt/release identities (`:1435-1629`).
- Component/source cross-checks continue to use the old inner/release lineage
  (`:1747-1804`, `:2381-2516`).
- `_build_batch_root` stores the catalog-release identity/SHA but no outer
  binding (`:2000-2147`).
- The batch reopener reopens the candidate root but cannot check an outer
  field absent from that root (`:2681-2723`).
- The public publisher accepts caller-provided inner receipt body/identity and
  catalog-release body/identity (`:3073-3147`).

Required correction: add the recovery module to the fixed executed dependency
closure, add outer identity/SHA to the batch root, remove public old-inner and
release arguments, and derive those compatibility bodies once from the cached
candidate-authority reopen.

### 7. Base source-v2 reducers: compatibility only, not authority

File: `src/nfl_dfs/research/corpus_r6_matchup_source_v2.py`

The base component bundle, producer receipt, and producer release contracts
model the old receipt/release identities at `:3471-3580`, `:3766-3805`,
`:3982-4052`, `:4373-4403`, and `:4588-4650`.

This module explicitly says its builders canonicalize facts supplied by an
outer producer and do not make them authoritative (`:1-17`). Therefore the
minimal migration does not require redesigning these reducers immediately.
They may remain compatibility projections if every authority-bearing wrapper
derives their arguments from an outer-reopened candidate root. They must not
be promoted into a public authority seam.

### 8. Leaf operator and final consumer: transitive consumers

`corpus_r6_matchup_source_operator_v2.py` does not decide catalog authority.
It describes the batch orchestrator as its intended authority-bearing caller
and accepts already validated producer/catalog/candidate identities
(`:1-14`, `:118-160`). No independent outer reopener belongs in this leaf.

`corpus_r6_v2_matchup_candidate_authority_consumer_v2.py` trusts the source
release ordinal reopener. Its candidate binding field set contains candidate
root/release/artifact identities but no outer (`:59-71`), and it invokes the
source reopener at `:296-348`. Once the source reopener returns an outer
binding, the consumer should carry and compare it so a terminal result has an
explicit audit trail.

## Moving-HEAD and code-identity semantics

### Candidate root

The candidate output namespace itself is fixed and run-scoped, not
caller-elevated:

- bucket/namespace and run-ID law:
  `corpus_r6_fixed_g0_candidate_authority_release_v1.py:45-60`
- prefix construction and root namespace validation: `:219-238`

The code/Git binding is weaker. Candidate `_ROOT_FIELDS` does not contain a
candidate implementation commit or code measurements (`:87-120`). The
authoritative reopener accepts `git_head` and replays through whatever commit
that callback currently returns (`:1001-1103`). The predecessor G0 replay
explicitly reads current HEAD and requires the G0 lock to match it
(`corpus_extreme_tail_panel_execution.py:1777-1803`). The resulting panel
receipt records `g0_source_commit_sha`
(`corpus_r6_fixed_g0_candidate_authority_v1.py:1711-1732`), so a moved HEAD is
likely to fail closed during byte reconstruction. However, the terminal root
does not advertise the required commit, and candidate core/release code bytes
are not independently measured by that root.

The schema successor should pin:

- candidate publication commit;
- candidate core and release module paths, bytes, and SHA-256 values;
- the recovery outer's implementation/review/final/attempt bindings; and
- the fixed G0 source commit already present in the panel.

The reopener should either replay exact Git blobs at the pinned commit while
allowing a clean descendant checkout, or explicitly require current HEAD to
equal the pinned commit. It must not silently derive scientific identity from
an unspecified moving HEAD.

### Source and batch roots

The base source root carries a capture-plan binding and operator code identity
(`corpus_r6_matchup_source_release_v1.py:1090-1151`). The capture-plan binding
contains an immutable commit, path, file SHA, bytes, and internal plan SHA
(`:270-287`).

The batch root goes further: it stores the capture-plan binding and an
executed-dependency closure (`corpus_r6_matchup_batch_candidate_authority_v1.py:2084-2094`),
and validation requires the plan commit, dependency closure commit, operator
commit, and orchestrator commit to agree (`:2315-2343`). Its trusted plan
loader still requires the lock to equal clean current HEAD (`:839-876`). Thus
the batch is operationally checkout-sensitive, but it does not silently embed
an unrecorded moving commit in its terminal root.

After adding the recovery import, include it in
`EXECUTED_DEPENDENCY_MODULE_PATHS` (`:120-167`) so the outer validator actually
executed by the batch is covered by the same commit/byte closure.

## Count and namespace semantics

No downstream candidate/source/batch root currently claims an observed cloud
namespace census.

- Candidate root task/arm/candidate totals are derived from exact body
  descriptors (`candidate_authority_release_v1.py:615-661`) and validated
  against the 54 descriptor bodies (`:753-828`).
- Source root task count and entry manifest are derived from its 54 members
  (`source_release_candidate_authority_v2.py:406-463`) and validated from the
  root body (`:779-873`).
- Batch root member and total counts are derived from the 54 member receipts
  (`batch_candidate_authority_v1.py:2041-2147`).
- `exact_read_unique_object_count` is returned only as reopen telemetry, not
  stored as namespace authority (`:2724-2735`).

These are graph/body completeness claims, not LIST evidence. Preserve that
distinction. If an observed namespace census is ever required, it needs a
separate trusted listing boundary, fixed prefix, listing receipt, and exact
object-identity set comparison. Do not rename the recovery outer's
`expected_terminal_prefix_object_count` into language implying an observed
census unless that proof exists.

The standalone source publisher accepts a normalized output namespace, while
the trusted batch derives its run-scoped prefix from code. That is acceptable
only because standalone structure is not candidate authority and the batch
root checks its fixed namespace. The outer migration must not introduce a
caller-selected catalog, candidate, or privileged production namespace.

## Minimal outer-binding migration design

### Phase 0: freeze a read-only recovery authority API

Add one recovery API with this conceptual result:

```python
{
    "outer_identity": generation_pinned_identity,
    "outer_attestation": validated_outer_body,
    "inner_replay_receipt_identity": identity_from_outer,
    "inner_catalog_release_identity": identity_from_outer,
    "recovery_code_and_lock_binding": validated_binding,
}
```

It must:

1. require the fixed outer URI;
2. resolve the reviewed final capability and tracked attempt from Git;
3. generation-exact read the outer identity;
4. validate canonical bytes, object SHA/bytes, outer self-hash, lock chain,
   attempt chain, and fixed outcome-denial policy;
5. return inner identities only from the validated outer;
6. grant no create, overwrite, delete, promotion, outcome, or production
   capability.

Do not make downstream callers instantiate a mutation-capable transport merely
to validate an existing outer object. A read-only adapter may reuse the same
validators, but its public type should communicate that it cannot publish.

### Phase 1: candidate core schema successor

Change the candidate authority inputs and lineage:

- replace `catalog_replay_receipt_identity` public parameters with
  `catalog_recovery_outer_identity`;
- exact-reopen outer first;
- exact-read the inner receipt and release only using identities extracted
  from the outer;
- require their object identities, internal self-hashes, and release linkage
  to equal the outer fields;
- require every catalog identity reopened by candidate derivation to equal the
  ordered outer inner-object manifest;
- retain legacy inner fields only under explicit derived/projection semantics;
- add outer identity, outer internal SHA, and recovery code/lock binding to
  material, slate receipt, panel receipt, and authority bundle; and
- pin candidate implementation code as described above.

Read order is a security property:

```text
outer -> derive inner receipt identity -> read inner receipt
      -> derive inner release identity -> read inner release
      -> derive catalog identities -> read catalogs
```

No inner read may occur before outer validation.

### Phase 2: candidate terminal release schema successor

- require outer identity/SHA in `_ROOT_FIELDS`;
- require the fixed outer URI;
- bind candidate code identity/commit;
- accept outer identity only in publish;
- reject legacy root schema during authoritative reopen;
- reopen outer before candidate release, panel, or per-slate objects; and
- reconstruct the terminal root byte-for-byte from all predecessors.

Publish a new run-scoped candidate root only after this reopener passes.

### Phase 3: capture-plan successor and tracked lock

- add outer identity/SHA fields;
- remove caller receipt/release bodies and identities;
- derive v1 projection inputs from the reopened candidate root;
- require plan outer == candidate root outer;
- measure the exact implementation commit/files; and
- create and commit the tracked capture-plan lock only after the new candidate
  root exists.

### Phase 4: component publication successor

- add outer identity/SHA to the v2 publication receipt;
- remove public old-inner/release inputs;
- derive compatibility inputs from the candidate reopen;
- require component outer == candidate outer before inner reads;
- preserve root-last/create-once mechanics; and
- exact-reopen the full component result before returning it.

### Phase 5: source release successor

- add outer identity/SHA to the source root;
- derive it from the validated component/candidate chain;
- require source == component == candidate outer;
- repeat the equality during ordinal reopen; and
- return the outer binding to the one-slate consumer.

Root-level storage is sufficient; member duplication is optional.

### Phase 6: trusted batch and final consumer

- add the recovery module to the executed dependency closure;
- add outer identity/SHA to the batch root;
- remove public receipt/release inputs;
- derive them once from the cached candidate reopen;
- require plan/component/source/batch outer equality;
- retain exactly one cached outer/candidate full replay per invocation;
- publish the batch root last; and
- include/compare outer identity/SHA in the final consumer result binding.

## Dependency order and release gates

| Order | Deliverable | Gate before advancing |
|---:|---|---|
| 0 | Stable recovery outer schema and read-only downstream reopener | Fixed URI, tracked capability/attempt replay, exact generation reopen, honest expected-count semantics |
| 1 | Candidate core successor | Outer-first read log; no public inner authority parameter; full manifest agreement |
| 2 | Candidate terminal root successor | Root binds outer and candidate code; legacy root rejected; full predecessor replay passes |
| 3 | Real create-once candidate root | Published root exact-reopens independently; no overwrite/fallback |
| 4 | Capture-plan successor and tracked lock | Lock binds exact candidate root + outer; implementation files measured |
| 5 | Component publication successor | Receipt outer equals plan/candidate outer; all outputs exact-reopened |
| 6 | Source root successor | Source/component/candidate outer equality; all 54 ordinal reopens pass |
| 7 | Trusted batch successor | Dependency closure includes recovery; public API has no inner seam; root published last |
| 8 | Final consumer integration | Source/candidate/scored-axis binding plus explicit outer equality |

Do not publish a downstream root before the immediate predecessor's new schema
has an independent exact reopener. Do not reuse an old candidate root or old
capture-plan lock under the new schema by relabeling it.

## Adversarial test matrix

| Layer | Adversarial case | Required result |
|---|---|---|
| Recovery | Missing outer generation | Fail before any inner read |
| Recovery | Correct URI with alternate generation/hash/bytes | Fail exact identity validation |
| Recovery | Wrong outer URI under same namespace | Fail fixed-URI law |
| Recovery | Changed review/final/attempt lock binding | Fail tracked recovery replay |
| Recovery | Outer names alternate inner receipt or release | Fail before accepting inner authority |
| Recovery | Outer internal SHA or manifest changed and rehashed coherently | Fail independent lock/manifest binding |
| Recovery | Outcome/production/promotion flag changed | Fail policy validation |
| Candidate core | Caller supplies only legacy inner receipt | Public signature rejects/does not expose seam |
| Candidate core | Outer read callback log is not first | Test fails; read order is mandatory |
| Candidate core | Inner identity differs from outer after exact reopen | Fail before catalog consumption |
| Candidate core | Release body SHA differs from outer | Fail before catalog consumption |
| Candidate core | Catalog manifest omits, duplicates, or reorders a member | Fail full manifest agreement |
| Candidate core | Candidate implementation bytes differ from pinned Git blob | Fail code identity replay |
| Candidate release | Old v1 root body supplied to new reopener | Fail schema validation |
| Candidate release | Root outer identity/SHA tampered and root rehashed | Fail predecessor reconstruction |
| Candidate release | Current HEAD moves | Follow explicit policy: pinned-blob replay succeeds on allowed clean descendant, or exact-pinned-HEAD gate fails early |
| Capture plan | Plan outer differs from candidate root outer | Fail prerequisite validation |
| Capture plan | Public builder exposes inner receipt/release arguments | Signature test fails |
| Component | Receipt outer differs from candidate root outer | Fail before v1 inner replay |
| Component | Caller attempts alternate inner receipt/release | No public seam; fail signature/binding test |
| Source | Component/candidate/source outer mismatch | Fail build and ordinal reopen |
| Source | Root outer changed and root rehashed | Fail candidate predecessor replay |
| Batch | Public publisher exposes inner receipt/release arguments | Signature test fails |
| Batch | Recovery module absent from dependency closure | Closure validation fails |
| Batch | Plan/component/source/batch outer mismatch | Fail before terminal root publication |
| Batch | Reopen reads outer/candidate authority more than once | Cache-count assertion fails |
| Batch | Partial prefix contains different bytes | Fail create-once collision; no dependent write |
| Consumer | Reopened source outer differs from result binding | Fail before retrieval law execution |

### Existing focused tests to update

- `tests/test_corpus_r6_fixed_g0_candidate_authority_v1.py:1675+` currently
  asserts the external old inner receipt identity requirement. Replace it with
  an outer-only authority and read-order test.
- `tests/test_corpus_r6_fixed_g0_candidate_authority_release_v1.py:282-283`
  builds roots with old inner fields. Add required outer/code fields and an old
  schema rejection case.
- `tests/test_corpus_r6_matchup_capture_plan_candidate_authority_v2.py:62-83`
  and `:289+` use/tamper old root receipt fields. Replace with outer equality
  and public-signature cases.
- `tests/test_corpus_r6_matchup_component_publication_candidate_authority_v2.py:129-144`
  and `:673-683` bind/tamper old inner fields. Add outer-first and no-caller-
  inner tests.
- `tests/test_corpus_r6_matchup_source_release_candidate_authority_v2.py:141-145`
  constructs old receipt bindings. Add source/component/candidate outer
  mismatch cases.
- `tests/test_corpus_r6_matchup_batch_candidate_authority_v1.py:806-813` and
  `:1039-1048` pass old inner/release inputs. Replace with outer-derived cached
  authority and dependency-closure tests.
- Final consumer coverage belongs in
  `tests/test_corpus_r6_v2_matchup_source_release_consumer_v1.py:682+`.

## Completion criteria

The migration is complete only when all of the following are true:

1. The recovery outer schema and read-only downstream API are stable.
2. The candidate publisher accepts only a generation-pinned outer identity.
3. Candidate derivation reads and validates the outer before any inner object.
4. Candidate material, panel, bundle, and terminal root bind the same outer.
5. Candidate implementation code is commit/byte pinned in the root.
6. Capture plan, component receipt, source root, batch root, and final consumer
   all bind the same outer identity/SHA.
7. No authority-bearing public API accepts an independently chosen inner
   receipt or catalog release.
8. The batch executed dependency closure includes the recovery validator.
9. Legacy roots fail closed under successor authoritative reopeners.
10. Every layer passes the adversarial mismatch/read-order tests above.
11. A real candidate root exists before the tracked capture-plan lock is
    created.
12. Publication remains create-once, exact-reopened, and root-last.

## Explicit non-goals

This migration does not:

- change candidate generation, corpus population, selector, scoring, or
  promotion laws;
- read world matrices, result objects, realized outcomes, or scores;
- authorize Neo4j or production graph mutation;
- require a cloud namespace LIST unless an observed census becomes an
  explicit separate requirement;
- make the base source-v2 compatibility reducers authoritative; or
- permit caller-selected catalog, candidate, source, production, or other
  privileged namespaces.

The purpose is narrower and critical: make the entire source-v2 lineage prove
that it descends from the reviewed recovery outer generation rather than from
the old inner receipt that the recovery contract explicitly declares
non-authoritative.
