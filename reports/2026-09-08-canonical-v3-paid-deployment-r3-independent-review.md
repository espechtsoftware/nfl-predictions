# Canonical-v3 paid/deployment bounded R3 independent review

Date: 2026-09-08

Reviewed candidate: `999204cc42602a43b8f94df12bbeb590db37ff40`

Candidate branch: `origin/codex/canonical-v3-paid-r3-repair-20260908`

Exact parent / repaired R2: `7fbcf5c310185e7ce5d6aa183485318bf0bbe10a`

R2 HOLD authority: production-main commit
`12532ec6842967e4b0cece0740e32fbb068aa29b`, report
`reports/2026-09-08-canonical-v3-paid-deployment-r2-independent-review.md`

Review branch: `codex/canonical-v3-paid-r3-independent-review-20260908`

Disposition: **HOLD**

## Executive disposition

R3 closes the R2 traffic-timing defect on the ordinary live-object path. The
pretraffic object is now only a deployment authorization. Every executable
paid-v3 path additionally reads a separate final object, whose closed payload
contains the exact deployment-authorization identity and an authenticated
attestation for the intended Ready revision at 100% provider traffic. The
executable failure test also establishes the required state for the principal
R2 adversary: if final attestation fails after traffic moved and rollback also
fails, no final object is published and the runtime remains closed.

The candidate nevertheless does not implement the **create-once** part of the
final money authority. Its preflight asks only whether a *current* object is
present, its conditional create permits recreation whenever no current object
exists, and runtime resolves whatever generation is current at the fixed URI.
A deletion or soft deletion therefore resets the apparent absence state and a
second final generation can become the accepted money authority. An
independent adversarial probe demonstrated that two distinct, internally
valid final authorities at consecutive generations of the same URI are both
accepted by the unchanged runtime environment.

That is a release blocker because the R2 repair contract did not ask merely
for an atomic non-overwrite against one live generation. It asked for a
create-once external posttraffic fact to be the sole money decision. R3 makes
the object posttraffic, but leaves its identity replaceable. The exact
candidate is therefore held from integration, build, deployment, activation,
and paid use pending the bounded R4 below.

No cloud, provider, build, deployment, GCS, graph, scoring, outcome,
contest-entry, or paid action occurred in this review.

## Scope and exact ancestry

The remote candidate identity was reproduced exactly and its sole parent is
the reviewed R2:

```text
999204cc42602a43b8f94df12bbeb590db37ff40
  7fbcf5c310185e7ce5d6aa183485318bf0bbe10a
```

The R2-to-R3 source delta is confined to:

- `scripts/deploy_paid_boundary_v3_image.sh`;
- `src/nfl_dfs/optimizer/paid_classic_deployment_v3.py`;
- `src/nfl_dfs/app/week1_operating_book_api.py`;
- the two focused test modules; and
- candidate documentation.

`src/nfl_dfs/optimizer/paid_classic_book_v3.py`,
`src/nfl_dfs/app/main.py`, and `cloudbuild.paid-boundary-v3.yaml` retain their
exact R2 Git blob identities. Function-source hashes independently confirmed
that the accepted R2 build-law normalizer, provider build validator,
deployment attestor, and retained-attestation validator are byte-identical.
There is no scoring, generation, selection, objective, world construction,
money-policy, frozen v1/v2, or Neo4j change in this delta.

## Accepted R3 repair: authority separation and posttraffic content

The R2 timing HOLD is substantively repaired apart from create-once identity.

1. `deployment-authorization.json` uses a distinct pretraffic schema. It binds
   the exact no-traffic staging attestation and names the future runtime
   revision, but its validator cannot satisfy the final money schema.
2. The active no-traffic revision carries only the exact generation, byte
   count, and SHA-256 of that deployment authorization. A pretraffic object by
   itself causes the money reopen to fail because `activation.json` is absent.
3. After traffic moves, the provider attestor requires one Ready service and
   revision, the intended revision as `latestReadyRevisionName`, and exactly
   one 100% traffic row for that revision. The final authority embeds that
   complete attestation and cross-binds project, region, build, source commit,
   image, service, revision, and deployment-authorization identity.
4. `reopen_paid_classic_activation_authority_v3` first exact-reads the
   environment-pinned deployment authorization, then resolves and validates
   the separate final object. Neither pretraffic schema nor rehashed
   zero-traffic content can pass final validation.
5. Dynamic `/lineups/paid-v3`, `/lineups/paid-v3.csv`, and
   `/lineups/entries/paid-v3.csv` all reach
   `_paid_classic_catalog_v3`, which reopens that final gate before generation.
   The Week-1 `/week1/operating-book-v2` successor calls the same final-gate
   function. Downstream receipts bind the final object's observed identity,
   not the pretraffic object's identity.

The injectable readers are test seams only; production callers omit them and
use the GCS implementations.

## Accepted R3 repair: final-attestation plus rollback failure

The shell order is now safe for the exact R2 adversary:

1. prove the final URI apparently absent;
2. stage the zero-traffic and authorized runtime revisions;
3. arm rollback before changing traffic;
4. attest the active revision and 100% traffic;
5. construct the final authority; and
6. publish the final authority only after all prior checks pass.

The committed executable-shell test runs the actual wrapper with local
provider stubs. It makes the traffic operation succeed, makes final
attestation exit 47, and makes provider rollback exit 53. The observed state
has the traffic mutation and rollback attempt, but no final gate and no final
receipt. Since runtime independently requires the final gate, money remains
closed even though traffic restoration could not be authenticated.

Disarming rollback immediately before the atomic final create is acceptable
for state safety. At that point the validated bytes already exist locally and
the conditional provider operation can produce either no current gate or the
complete validated gate; it cannot expose partial bytes. A nonzero/ambiguous
upload result is still operationally awkward because the wrapper does not
reconcile which safe branch occurred, but that is not the R2 money-safety
blocker.

## Remaining P0: the final authority is replaceable, not create-once

### Executable behavior

`require_paid_classic_final_activation_absent_v3` delegates to
`_probe_current_gcs_generation_v3`. That implementation creates the live blob
handle and calls only `blob.reload()`. `NotFound` is treated as pristine. It
does not enumerate exact-name versions, noncurrent generations, or
soft-deleted generations.

The publisher later uses:

```text
gcloud storage cp --if-generation-match=0 .../activation.json
```

That precondition is atomic against an object that is currently live, but a
deleted or soft-deleted generation is not a current generation. Once the live
object is deleted, the same condition permits another generation at the same
name. The early current-only probe reaches the same incorrect conclusion.

Runtime has the complementary weakness. `_read_current_gcs_final_activation_v3`
reloads the current blob, snapshots that generation, and downloads it exactly.
This correctly prevents a read-time race within one request, but there is no
external immutable identity for the final object and no unique-generation
census. Consequently runtime accepts a later current generation if its
payload validates.

### Independent reproduction

The review constructed the candidate's valid final envelope, then constructed
a second valid envelope for the same policy-derived URI with a distinct
provider-record hash and a consecutive generation. The runtime environment
and exact pretraffic deployment authorization were held constant. Both were
accepted:

```json
{
  "same_fixed_uri": true,
  "two_sequential_current_generations_accepted": [
    {
      "generation": "987654322",
      "authority_sha256": "20f4c37b71ff0c7e18f6ffc2cbc1bf7ef9f065a4a6cca1c1a283ffe27be3df4a"
    },
    {
      "generation": "987654323",
      "authority_sha256": "614dc0e9441d71cd5d0a44d022ce3c438adfd2c5c991fca020d5b6fb9552fdc1"
    }
  ]
}
```

This is not a hash-collision claim and it does not require a malformed
payload. It demonstrates that the runtime law is "accept the presently live,
self-consistent final object" rather than "accept the sole create-once final
fact." The provider writer remains the trust boundary, but an accidental
delete/retry or privileged replacement can change the money authority without
changing the running revision's immutable environment.

### Why this blocks release

The final activation object is the only fact which changes the runtime from
deny to allow. Its uniqueness therefore cannot be inferred from a current-only
lookup. The repository already distinguishes live state from full generation
and soft-delete state in create-once workflows because deleting a live object
does not erase its history. A money gate must meet at least that same standard.

The green candidate tests cover current exists, current absent, and provider
lookup uncertainty. Their injected probe has the type `Callable[[str], str |
None]`, so it cannot even represent multiple or soft-deleted generations. No
test exercises delete-then-recreate or two successive valid current
generations.

## Bounded R4 repair contract

Preserve every accepted R2 law and the R3 two-stage/posttraffic design. Change
only final-object uniqueness and its tests:

1. Replace the current-only absence probe with an exact-name inventory that
   accounts for every visible live, noncurrent, and soft-deleted generation.
   Before the first Cloud Run mutation, require the union to be empty. Any
   permission, pagination, representation, or provider uncertainty fails
   closed.
2. Immediately before final publication, repeat that exact inventory under
   the deployment's existing single-writer/launch authority, then retain the
   atomic `if-generation-match=0` create.
3. After publication, exact-reopen the provider-returned generation and prove
   its URI, generation, bytes, and SHA-256. Retain that identity in the
   deployment receipt/transcript.
4. At runtime, resolve the final URI through the same unique-generation law:
   exactly one live generation and no noncurrent or soft-deleted generation
   may exist. Then download that one generation exactly and validate the R3
   final payload. A delete, recreation, second generation, tombstone, or
   incomplete inventory must close money output.
5. Add provider-realistic adversaries for: one soft-deleted generation and no
   live object; one soft-deleted generation plus a recreated live object; two
   generations; pagination/permission uncertainty; and a race/collision at
   conditional publication. Also rerun the existing traffic-success plus
   final-attestation-and-rollback-failure shell test.
6. Do not modify engine receipts, native/combined world laws, build law,
   scoring, generation, selection, policy constants, frozen v1/v2 behavior,
   or graph semantics.

An equivalently strong provider-enforced immutability design is acceptable,
but it must be executable and independently tested. A comment, IAM assumption,
current-only `NotFound`, or `if-generation-match=0` by itself is not evidence
that the money authority has only one historical generation.

## Non-blocking observations

- The active-traffic archive at `activation.json.traffic.json` still uses
  `--no-clobber` and is not exact-reopened. The final authority embeds the
  locally validated traffic receipt, so this does not bypass runtime, but a
  stale archive after a failed attempt could disagree with the final gate.
  Exact create/reopen would improve durable provenance after the P0 repair.
- The final conditional upload is not reconciled after an ambiguous nonzero
  return. Both possible provider states are money-safe under the validated
  payload assumption, but a small read-only reconciliation would make the
  deployment disposition and retained transcript unambiguous.
- The R2 legacy-route clarification remains: paid-v2 and the old Week-1 route
  are not v3-gated. They must not be described as v3 money routes unless
  retired or denied at ingress. This was not a basis for either HOLD.

## Independent validation

Static/adversarial work preceded pytest. It established:

- exact direct-child ancestry and clean candidate checkout;
- `git diff --check` clean;
- shell syntax for both paid build/deploy wrappers;
- AST parsing for all modified Python/test modules;
- four-step Cloud Build shape, 3600-second timeout/queue TTL, and exact service
  account;
- registry-v2 check: 117 observations, four source artifacts, expected
  `candidate_only_unadjudicated` state;
- exact R2 Git-blob retention for the paid-v3 book, application router, and
  Cloud Build contract; and
- the two-successive-final-generation runtime reproduction above.

A fresh machine-wide census immediately before each serial pytest invocation
found no other `python -m pytest` process. Results:

```text
focused R3 surface:              131 passed in 9.06s
exact Cloud Build release gate:  281 passed in 24.09s
```

These greens validate the posttraffic and rollback repairs. They do not test
historical create-once identity and therefore do not change the HOLD.

## Exact next action

Return a bounded R4 implementing the six-item final-object repair contract,
then independently review its exact tip before any integration, build,
deployment, activation, or paid use. Do not reopen accepted R2 engine/world/
build work and do not alter scoring or selection to repair this release
mechanic.
