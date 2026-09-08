# Canonical-v3 paid/deployment bounded R2 independent review

Date: 2026-09-08  
Reviewed candidate: `7fbcf5c310185e7ce5d6aa183485318bf0bbe10a`  
Candidate branch: `origin/codex/canonical-v3-paid-r2-repair-20260908`  
Exact parent / held R1: `3c51fd3fb5cf6f3c52dfc9f1762661b94e1a67c9`  
Prior independent HOLD:
`reports/2026-09-07-canonical-v3-paid-deployment-repair-independent-review.md`
on production commit `0ea47c90`  
Review branch: `codex/canonical-v3-paid-r2-independent-review-20260908`  
Disposition: **HOLD**

## Executive disposition

The bounded R2 closes most of the prior HOLD well and its committed tests are
green. In particular:

- one detached immutable engine result now crosses the actual simulation or
  MILP engine boundary and is required with the independently constructed
  pre-execution authority at every transformed paid-v3 terminal API;
- the simulation result binds the five native candidate/world blocks, their
  exact matrix identities and orders, the combined matrix/order, and the
  selector's actual indices and selected-roster order;
- provider Cloud Build evidence is normalized against the retained provider
  shape without projecting away caller-controlled bypass fields; and
- the runtime accepts only an exact-generation activation object and no longer
  accepts inline activation JSON. The active Week-1 v2 successor uses the same
  exact-object gate.

The deployment/activation boundary nevertheless remains one step early. The
object which enables the paid runtime is deliberately created from a staging
revision that has **zero traffic**, before the authorized runtime revision
exists and before traffic is moved. The later active-revision provider
attestation and `*.traffic.json` receipt are never consumed by the runtime.
Consequently the paid boundary can accept requests as soon as traffic reaches
the pre-authorized revision, before the final provider attestation is made;
and a post-cutover attestation or rollback failure can leave the revision
serving with a still-valid activation object. This does not satisfy the prior
P0-3/P0-4 requirement that the provider activation decision gate money output
or that a failed cutover leave the boundary externally disabled.

The exact candidate is therefore held from integration, build, deployment,
activation, and paid use. This is a narrow release-mechanics HOLD, not a
rejection of the engine/world/build work and not a request to alter scoring,
selection, generation, the money policy, Neo4j, or frozen v1/v2 algorithms.

No cloud, graph, deployment, load, scoring, outcome, contest-entry, or paid
action occurred in this review.

## Scope and ancestry

The candidate is the exact direct child of the held commit:

```text
7fbcf5c310185e7ce5d6aa183485318bf0bbe10a
  3c51fd3fb5cf6f3c52dfc9f1762661b94e1a67c9
```

The delta is confined to the paid-v3 build/deploy contract, paid-v3 engine and
application evidence, the Week-1 v2 successor gate, focused tests, and durable
documentation. Source review found no change to scoring formulas, candidate
budgets, selector objectives, adopted policy constants, or canonical-v3 graph
semantics.

## Accepted repair 1: immutable engine result and independent request authority

This part of the prior HOLD is closed.

- `build_sim_lineups` now returns `(selected, engine_result)` only for the
  typed paid-authority path. `_build_classic` captures that exact result before
  confidence ranking and presentation annotation; it no longer recreates a
  result after the engine returns.
- The MILP path seals its result immediately after optimization and before
  ranking/annotation.
- `PaidClassicEngineResultV3` contains detached canonical JSON for the selected
  roster/objective set, receipt bytes, world binding, and result hash. It
  retains no mutable `Lineup` or player mapping, and ordinary assignment to
  receipt/result payloads is refused.
- Dynamic validation and both transformed exporters require a typed execution
  authority and typed engine result. The deterministic Week-1 compatibility
  path is a separate named method which refuses those transformed-engine
  authorities.
- The terminal validator independently compares every request, policy,
  constraint, seed, and dose field in the engine receipt to the server-created
  execution authority. It also compares the immutable engine result to the
  terminal roster/objective set and exact receipt bytes.

The positive normalized application/MILP tests pass, and the negatives for
post-engine player/objective mutation, missing authorities, and coordinated
request restatement fail closed as intended.

## Accepted repair 2: native and combined world identity

This part of the prior HOLD is also closed.

For each registered native block the issued manifest retains:

- exact label, projection seed, and role seed;
- ordered player IDs and ordered nine-player candidate identities;
- exact shape, NumPy dtype string, and C-order byte SHA-256 for candidate
  totals and player draws.

The combined identity retains the exact world-block order, player order,
candidate order, matrix identities, selected indices in selector order, and
the selected roster identities at those indices. Validation enforces the
five-block dose relationships, common player ordering, dimensions,
uniqueness/membership, index bounds, and exact index-to-roster mapping. MILP
uses an explicit no-world identity rather than placeholder hashes.

The manifest stores identities rather than full multi-gigabyte matrices; that
is appropriate for this boundary because the detached result is issued inside
the engine from the matrices it just consumed. The prior syntactic arbitrary-
hash fallback is gone for simulation.

## Accepted repair 3: provider-realistic closed-world Cloud Build law

The prior build-law blocker is closed on the inspected surface.

- Provider observations (`name`, status/timing, artifacts, results, and
  similar output fields) are projected separately.
- Every reviewed step execution field is compared, including
  `allowExitCodes`, `allowFailure`, `waitFor`, script, secrets, volumes,
  timeout, and automatic substitutions.
- Top-level timeout, queue TTL, options, service account, secrets,
  substitutions, and image declaration are closed-world compared.
- Only the two provider defaults demonstrated by the retained record are
  normalized when absent from the reviewed YAML:
  `options.logging=LEGACY` and `options.pool={}`.
- Build project, ID, source commit, exact tag substitution, one output digest,
  repository, create/finish time order, and full normalized law are checked
  before Cloud Run mutation.

The repository's retained `gcloud builds describe` document contains the
provider-only `name`, `startTime`, and `artifacts` fields plus the same
`LEGACY`/empty-pool defaults. The candidate's positive provider-shape test and
one-negative-per-bypass cases all pass.

## Remaining P0: activation is authorized before traffic is attested

### Executable sequence

`scripts/deploy_paid_boundary_v3_image.sh` performs this order:

1. create and authenticate a staging revision with no traffic;
2. write `staging-pre-activation.json`;
3. create `activation.json` from that zero-traffic staging receipt, naming a
   future runtime revision which does not yet exist;
4. upload and exact-reopen that activation object;
5. create the future runtime revision with the activation object's exact
   `{uri,generation,sha256,bytes}` in its environment;
6. attest that runtime revision while it still has no traffic;
7. move 100% traffic to it;
8. make the final active-revision attestation and upload
   `activation.json.traffic.json`.

The runtime money paths perform only step 4's activation-object reopen. A
repository search finds no application/runtime consumer of the step 8 traffic
receipt. The activation payload contains the zero-traffic staging attestation
and a future revision name, but no provider record for that future revision
and no active-traffic attestation.

### Independent reproduction

Using the candidate's own provider fixture and production validator, the
review created the exact activation object from the staging receipt and
reopened it as the future runtime before supplying any active provider record.
The exact output was:

```json
{"authority_contains_active_provider_attestation": false,
 "authorized_runtime_revision": "nfl-dfs-app-paidv3-aaaaaaaa-12345678",
 "runtime_reopen_accepted": true,
 "staging_activation_stage": "pre-activation",
 "staging_provider_traffic_percent": 0}
```

This is intended by the implementation, not a test-fixture accident: the
committed positive activation test performs the same pre-traffic construction
and accepts it.

### Why this is release-blocking

The prior HOLD required the durable provider decision to be consumed by the
money boundary, and its staged-cutover requirement said that any final failure
must restore prior traffic **or keep the paid boundary externally disabled**.
The present order proves neither condition:

- immediately after `update-traffic` applies, the runtime already has a valid
  activation object, while the final active provider attestation has not yet
  run;
- if final service/revision attestation fails, there is a window in which paid
  bytes can be served from a revision not yet terminally attested;
- if rollback also fails, the pre-created activation object remains valid and
  the active revision can remain at 100% traffic; and
- even on a clean run, the final `*.traffic.json` is durable evidence only. It
  is not an input to the runtime's allow/deny decision.

Arming rollback before the traffic command and reconciling an ambiguous
nonzero return are both good repairs. They reduce the failure window, but an
attempted compensating mutation is not the fail-closed gate that the prior
contract required.

### Required narrow R3 repair

Preserve the accepted R2 work and change only activation/cutover mechanics:

1. distinguish a pre-traffic **deployment authorization** from the object that
   enables money output;
2. keep the candidate runtime's money endpoints disabled while it is staged
   and while traffic is first reconciled;
3. only after authenticating the exact active revision and canonical 100%
   provider traffic, publish or expose a create-once external activation fact
   that the runtime consumes; and
4. on any post-traffic failure, prove either exact former traffic restoration
   or revocation/absence of the external money gate. Do not leave a valid
   pre-created money authorization as the fallback state.

The exact implementation may use a final external gate lookup, a further
disabled-to-enabled revision stage, or another non-self-referential design.
What matters is the invariant: no paid response can pass solely on evidence
created before the serving revision and provider traffic were authenticated.

Add one adversarial test that makes `update-traffic` apply, then forces the
final provider attestation and rollback to fail. The paid runtime must reject
under the resulting retained state. Also prove the successful path consumes
the post-traffic activation fact rather than merely archiving it.

## Non-blocking route-boundary clarification

The candidate correctly gates `/week1/operating-book-v2(.csv)`, which is the
active successor named by the prior review. The older
`/week1/operating-book.csv` and paid-v2 endpoints remain callable and can emit
CSV without the v3 activation object. The review does not require changing
their frozen algorithms, but before claiming that *all* money-output routes are
activation-gated, production should explicitly retire/deny those legacy routes
at the application or ingress boundary, or label them non-money/replay-only.
This ambiguity is not the basis of the R2 HOLD.

## Independent validation

Static/adversarial review was completed before pytest. Checks passed:

- exact direct-child ancestry and scoped diff;
- `git diff --check` for the candidate delta;
- Python compilation of every modified Python/test module;
- `bash -n` for both build/deploy wrappers; and
- YAML parse, four-step shape, queue-TTL and service-account assertions.

A fresh machine-wide census immediately before each serial pytest command
showed no other `python -m pytest` process.

Focused repaired surface:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/erich/projects/nfl-predictions/.venv/bin/python -m pytest \
  -q -o addopts='' -p no:cacheprovider \
  tests/test_paid_classic_book_v3.py \
  tests/test_paid_classic_deployment_v3.py \
  tests/test_week1_operating_book_api.py \
  tests/test_week1_operating_book_export.py

127 passed in 6.83s
```

Exact focused release-gate list from `cloudbuild.paid-boundary-v3.yaml`:

```text
277 passed in 20.67s
```

Registry-v2 check passed with 117 observations, four source artifacts, and the
expected `candidate_only_unadjudicated` status. The green suites are meaningful
evidence for the accepted repairs; they do not test the post-traffic runtime
gate invariant described above.

## Final decision

**HOLD** exact `7fbcf5c310185e7ce5d6aa183485318bf0bbe10a` from integration,
build, deployment, activation, and paid use. Return a narrow R3 which preserves
the accepted engine/world/build repair and moves the runtime allow decision
behind authenticated active-revision/traffic state. After an independent
review of that delta, the separately authorized candidate-only pre-lock smoke
may proceed; a code review is not itself authority for cloud or paid action.
