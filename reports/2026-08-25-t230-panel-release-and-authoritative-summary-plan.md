# T230 panel release and authoritative-summary plan

**Date:** 2026-08-25
**Status:** outcome-blind implementation plan; execution waits for Gate G0 and
the accepted one-slate runtime/memory benchmark
**Purpose:** turn the one-slate T230 census, retrieval suite and support switch
into a trustworthy 54-slate release whose already-frozen books can be scored
without another method decision

## Decision

Use one immutable image, one frozen execution manifest, one create-once result
and acceptance receipt per accepted v12 slate, and one exact final join. Run at
most two cloud lanes concurrently; each lane processes its assigned slates
strictly sequentially and gives every slate a fresh process.

The existing structural panel-summary helper remains diagnostic only. It must
continue refusing authoritative mode until the exact panel/result join below
exists. Self-hashes alone do not prove panel membership, source replay or book
identity.

The local one-slate smoke envelope is also a diagnostic carrier, not a panel
publication authority. The panel runner must independently exact-read the
accepted carrier/source/world receipts and derive scope, block, universe and
membership commitments from those inputs. It may not promote a nested smoke
claim merely because all of its internal self-hashes replay.

## 1. Frozen execution manifest

Add `foundry-t230-panel-execution-manifest/v1` and publish it create-once before
any panel slate runs. It binds:

- the published panel object's URI, generation, SHA-256 and byte count;
- `panel_id`, `panel_index_sha256` and the ordered 54-member list hash;
- for source ordinals `0..53`, the exact `slate_id`, member hash, task-
  acceptance identity, carrier identity, deterministic result URI and
  deterministic acceptance-receipt URI;
- the seven source arms in canonical order;
- five R blocks, 10,000 worlds per block and authoritative `7 x 5 x 200` dose;
- the four T230 strategies and selector-implementation hashes;
- exact budgets `4/14/80` and one deterministic rank-80 prefix law;
- fold support: all four blocks nonzero and total `>=100`;
- final support: all five blocks nonzero and total `>=125`;
- panel support: exact `4/5` integer-cross-product law;
- source commit, immutable image digest and one output prefix; and
- false outcome, retry, mutation, analytical, promotion and decision
  authorities plus a canonical manifest self-hash.

No slate ID, threshold, strategy, budget or output URI is accepted as a
per-task override after this manifest freezes.

## 2. One accepted analysis result per slate

Implement a pure orchestration seam such as:

```python
build_and_replay_t230_slate_v1(...)
validate_t230_slate_result_structure_v1(...)
build_t230_slate_acceptance_v1(...)
```

For exactly one manifest ordinal it must:

1. exact-read the manifest and its generation-pinned panel object;
2. require the exact ordered membership at that ordinal;
3. call `reconstruct_one_accepted_v12_slate` through the accepted task and
   carrier identities;
4. build and byte-replay the 220/230/240/250 support census;
5. build and byte-replay the frozen four-law T230 suite once; and
6. build the support-switched policy, which itself replays the census and
   suite against the reconstruction.

Avoid a third expensive full-suite replay. After step 6, run an inexpensive
exact structural check over the newly built nested result. If necessary,
expose the current private policy structure validator as a public frozen
validator rather than recomputing selectors.

Every source/world identity, fold-scope hash, block hash, per-arm marginal and
pairwise overlap must be derived from that reconstruction. No first-observed
nested hash may establish its own reference truth. Exact schemas and exact
lineage-object equality are required at all publication boundaries.

The `foundry-t230-slate-analysis/v1` result retains:

- manifest and panel object identities and hashes;
- source ordinal, complete accepted membership and membership hash;
- task acceptance, carrier, source-freeze and five world identities;
- reconstruction receipt and common input binding;
- complete support census, four-law suite and support-switched policy;
- all nested self-hashes and replay-verification facts;
- exact final books for all four strategies at 4/14/80;
- required final-book `>=230` pair intersections/Jaccard and duplicate
  event-vector diagnostics; and
- false authority fields plus one result self-hash.

Publish with `if_generation_match=0`, then exact-reopen. Equal bytes at the
deterministic URI are an idempotent recovery. Different bytes are a hard
collision and never authorize recomputation under changed inputs.

Publish a small `foundry-t230-slate-acceptance/v1` beside the result. It binds
the result object identity, manifest/panel/member identities, reconstruction,
census, suite and policy hashes, exact fold/final/book counts, replay flags and
its own self-hash. This remote acceptance—not a free-form policy JSON—is the
only input admitted by the final panel join.

## 3. Authoritative 54-slate join

A local carrier ledger lists exactly 54 generation-pinned acceptance
identities in source-ordinal order. It is convenience transport only. The
finalizer exact-reads every remote acceptance and result; it never lists a
bucket, follows `latest`, or trusts a local policy body.

Add:

```python
build_t230_panel_release_v1(
    *,
    manifest_identity,
    acceptance_identities,
    read_exact,
)
```

It requires:

- exactly 54 ordered and unique panel members with ordinals `0..53`;
- exact member/slate/task/carrier equality to the published panel;
- unique deterministic acceptance/result identities;
- every result bound to the same manifest and panel generation;
- census, suite and policy sharing the same complete input binding;
- authoritative dose, width 10,000 and 50,000 score columns;
- five folds plus one distinct all-block fit per slate;
- exact 4/14/80 books and required pair-event diagnostics;
- unique reconstruction/census/suite/policy identities across slate members;
  and
- no fixture, outcome, mutation, retry, analytical, promotion or decision
  authority.

Only this join computes authoritative support:

- exactly 270 fold gates; literal support passes at `216/270`;
- exactly 54 final gates; literal support passes at `44/54`; and
- general literal-230 support requires both integer inequalities.

The create-once `foundry-t230-panel-release/v1` contains the ordered source
catalog and final-fit grade catalog for every frozen strategy/budget. It also
contains lineup IDs and rosters. The support-switched choice is a pointer to an
already frozen raw-suite book, never a new post-summary selection. The governed
scorer can therefore consume the release immediately without extraction or
method choice.

## 4. One CLI, three commands

```text
prepare       publish/reopen the exact execution manifest
run-slate     run one manifest source ordinal and publish/reopen result+acceptance
finish-panel  exact-read all 54 acceptances and publish/reopen the panel release
```

`run-slate` receives only the manifest identity and source ordinal. It never
accepts a caller-selected slate, strategy, threshold, budget or output URI.

## 5. Bounded execution

1. Complete Gate G0 and run the frozen `2023-w01` census smoke.
2. If memory/runtime is acceptable, run the full four-law suite on that same
   slate under `/usr/bin/time -v` before freezing the analysis image.
3. Publish the execution manifest once.
4. Reuse the existing 32-GiB job envelope with `maxRetries=0`.
5. Run two lanes: ordinals `0..27` and `28..53`; one fresh process per slate,
   strictly sequential within each lane.
6. Recover transport only by exact-reopening equal create-once objects. Never
   recompute under a changed manifest or after ambiguous partial publication.
7. Print only small acceptance identities to logs; publish large nested
   results directly.
8. Finish and publish the exact panel release, then freeze the intended grade
   catalog before any governed outcome access.

Neo4j and React consume the completed release afterward. Neither is on the
critical path to the first scores.

## 6. Required adversarial tests

- fixture receipt retagged as authoritative;
- 54 renamed clones of one slate;
- reordered, missing or duplicate source ordinals;
- cross-slate census/suite/policy splice;
- valid-looking but wrong source-book hash or selected IDs;
- wrong panel generation or membership hash;
- width, shape, dose and per-block opportunity drift;
- changed strategy/implementation/budget/output prefix after manifest freeze;
- equal-byte idempotent reopen and unequal-byte create-once collision;
- exact support boundaries: `215/270` fails, `216/270` passes; `43/54` fails,
  `44/54` passes; and
- any nested outcome/mutation/promotion/decision authority fails closed.

## Immediate implementation boundary

Do not build the cloud release before the real one-slate benchmark establishes
that the four-law suite fits the 32-GiB envelope with adequate headroom. The
manifest/result/acceptance/finalizer schemas and focused fixtures can be
implemented outcome-blind in advance; cloud launch and panel scale remain
gated by that measurement.
