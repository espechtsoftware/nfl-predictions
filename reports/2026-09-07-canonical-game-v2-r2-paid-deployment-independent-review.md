# Canonical-game v2 R2 paid/deployment independent review

Date: 2026-09-07  
Reviewed commit: `a6007f2fd6cc5aca662489994a5f1d590b26f164`  
Required parent: `a5e39f7362114430278e9473d7096a16ee3da061`  
Review scope: paid-v3 execution evidence and Cloud Build/Cloud Run release
authority only  
Verdict: **HOLD**

## Executive disposition

The commit is the required direct child and it contains several sound
improvements: the image source is fetched from an exact pushed commit, runtime
code does not depend on a Git checkout, paid-v3 uses an immutable image URI,
the simulation validator names the registered five seed pairs and the
10,000-by-five world dose, and the deployment helper does inspect real Cloud
Build and Cloud Run records.

It is not safe to build, deploy, or use for paid output yet. Two independent
adversarial reproductions defeat the claimed authentication boundaries:

1. a typed, supposedly immutable engine receipt can be changed after issue,
   rehashed, and accepted with different score-relevant request facts and
   wholly different model/feature/note hashes; and
2. the provider build-law validator accepts Cloud Build step fields that can
   allow the focused tests to fail without failing the build.

There are two additional release-boundary blockers: Cloud Run traffic is
mutated before the revision/traffic attestation is performed, and the paid
runtime never consumes the resulting attestation. These are narrow release
mechanics defects. They do not call for any change to the science, canonical
game policy, DK legality, Neo4j, or the frozen Week-1 v1/v2 paths.

No pytest invocation was made in this review. The serial test lane was left to
the production coordinator because the static and lightweight adversarial
checks were already decisive. No cloud call, build, deployment, paid-entry
operation, Neo4j mutation, outcome read, or implementation edit occurred.

## P0-1: the engine receipt is mutable and validates coordinated restatements

`PaidClassicEngineReceiptV3` describes itself as immutable, but its sole slot
is publicly assignable (`paid_classic_book_v3.py:113-130`). Its hash is an
ordinary unkeyed SHA over its own claims. After a typed receipt has been issued,
code can replace `_payload_json` with any newly self-consistent JSON body.
Neither the type check at lines 949-950 nor the self-hash check at lines
963-965 distinguishes those bytes from the originally issued bytes.

The terminal validator independently checks a few claims against the catalog
and selected roster, but it does not receive the actual server request as an
independent authority. In particular, lines 1187-1236 validate tail line,
field size, contest limit, and leverage by deriving one claimed field from
other fields in the same receipt. A coordinated change therefore passes. The
model, feature, and note validators similarly check shape, digest syntax, and
cross-block consistency, not the originally observed artifacts.

### Reproduction A: restate the score-relevant request

Using the exact commit's own valid catalog/book/receipt fixture, this review:

1. changed `requested_tail_line` and `tail_line` from 194 to 210;
2. changed `field_size` to 832,000;
3. recomputed `receipt_sha256` with the production canonical hash;
4. assigned the JSON back to the already typed receipt; and
5. called `validate_paid_classic_book_v3`.

The exact output was:

```text
ACCEPTED_RESTATED_REQUEST 210.0 210.0 832000
```

The accepted lineups were generated under the old request. This directly
defeats the request/tail binding; it is not merely a cosmetic mutation.

### Reproduction B: restate model, feature, and note evidence

The same method replaced, consistently across all five blocks and both model
families:

- every serialized model-member hash (with each inner artifact rehashed);
- every model-input feature-frame hash; and
- every before/effective component-note hash.

After recomputing the outer hash, terminal paid validation again accepted:

```text
ACCEPTED_COORDINATED_RECEIPT_RESTATEMENT \
c0189cbf9c936063d252e51e37e46bee1abcf88182debd5cef5c2bd57e79c7a8
```

This means the current tests establish detection of isolated inconsistent
edits, but not authentication of the facts observed during execution. The
module-private issuer sentinel does not repair this: the payload of an already
issued object is mutable, and Python underscore names are not an authority
boundary in any case.

### Required repair

Use an independently derived pre-execution authority plus an immutable
post-execution result, rather than asking the terminal boundary to trust facts
carried on each lineup:

1. Before generation, create a closed, canonical execution-authority object
   from the server's actual `LineupRequest`, joined catalog, exact construction
   preset, exact policy environment, locks/bans/theses, objective, contest
   context, seed pairs, and world dose. The paid export boundary must receive
   or independently reconstruct this object; it must not reconstruct expected
   request facts from the receipt being tested.
2. Have the engine return one typed result containing an immutable lineup tuple
   and immutable canonical receipt bytes. Do not attach the sole authority to
   mutable `Lineup` instances. Prevent ordinary post-issue assignment and do
   not expose an issuer capability through the public module surface.
3. Compare every receipt request/policy/constraint field byte-for-byte with the
   independent execution authority. Add coordinated-restatement negatives for
   tail/field/leverage, construction, notes, preferences, models, and feature
   frames—not only one-field inconsistency tests.
4. If model/feature/note hashes are to be called independently authenticated,
   bind them to retained exact-object identities or to immutable engine-result
   evidence that the terminal boundary receives independently. Otherwise label
   them honestly as engine observations, not independently reopened facts.
5. Bind the five native candidate/world blocks and their ordered combined
   matrix (at least dimensions plus streaming digests and selected-index/order
   identity). A count of 50,000 alone does not prove which 50,000 worlds were
   judged.

The important minimal gate is that the two reproductions above must fail even
when every attacker-controlled inner and outer hash is recomputed.

## P0-2: the build-law projection erases test-bypass fields

`_reviewed_build_law` retains only `id`, `name`, `entrypoint`, `args`, `dir`,
and `env` from each step and only `steps`/`images` at the top level
(`paid_classic_deployment_v3.py:86-108`). Provider/user-configurable fields
outside that allowlist disappear from both sides before comparison. The
validator therefore does not authenticate the exact committed build law.

This matters directly for the test gate. Cloud Build step controls such as
`allowExitCodes`/`allowFailure` can make a failing focused-test step compatible
with overall build `SUCCESS`. `waitFor` can also change the reviewed sequential
ordering. `secretEnv`, `volumes`, `script`, step `timeout`, service account,
available secrets, and material build options are likewise outside the
comparison.

### Reproduction

A synthetic provider record copied from the exact committed YAML was changed
only by adding:

```yaml
# focused-production-boundary-tests
allowExitCodes: [1, 2, 5]

# build-image-from-exact-source
waitFor: ["-"]

# top level
serviceAccount: projects/attacker/serviceAccounts/other@example.invalid
```

The provider status remained `SUCCESS`, as it legitimately could when the
focused test exits with an allowed code. The production validator returned:

```text
ACCEPTED_UNREVIEWED_PROVIDER_FIELDS 12345678-1234-1234-1234-123456789abc
```

### Required repair

Normalize provider-added observational fields separately from user-controlled
configuration, then closed-world compare all user-controlled build semantics.
At minimum:

- require absent/default equality for `allowExitCodes`, `allowFailure`,
  `waitFor`, `script`, `secretEnv`, `volumes`, per-step `timeout`, and
  `automapSubstitutions`;
- bind top-level `timeout`, `options` (including machine type and substitution
  behavior), `serviceAccount`, `secrets`/`availableSecrets`, declared images,
  and relevant substitutions;
- explicitly prove prepare -> tests -> image build -> image smoke ordering;
  and
- add one refusal test per bypass class, especially a `SUCCESS` provider record
  whose test step carries `allowExitCodes`.

Do not solve this by ignoring all provider-added fields indiscriminately;
timing/status output can be projected away, but every caller-configurable
execution field needs equality or an explicit forbidden/default rule.

## P0-3: deployment changes serving traffic before it can attest the release

The helper authenticates the build before mutation, which is good. It then runs
`gcloud run deploy` without `--no-traffic` (`deploy_paid_boundary_v3_image.sh:
74-77`). Only after that mutation does it describe the service/revision and run
the Ready/environment/100%-traffic checks (lines 79-90).

If any post-deployment check fails—provider schema drift, wrong environment,
wrong revision identity, traffic mismatch, or local receipt failure—the shell
exits but the newly deployed revision may already be serving 100% of traffic.
`set -e` is not rollback. The process therefore fails after, rather than before,
the risky state change.

### Required repair

Use a staged cutover:

1. deploy the immutable digest with `--no-traffic` and a unique revision;
2. reopen and authenticate that revision, its exact environment, image digest,
   Ready state, project/region/service identity, and causal creation after the
   successful build;
3. publish a durable create-once pre-activation receipt;
4. move traffic to the authenticated revision;
5. reopen exact service state and require one exact 100% traffic target; and
6. on any final failure, restore the previously captured traffic assignment or
   keep the paid boundary externally disabled.

The helper should not report success merely because a local file was written.

## P0-4: the provider attestation is not consumed by the paid boundary

The post-deploy attestation is written to a caller-selected local path with
`Path.open("x")`. Repository search shows its validator is used only by its own
module and tests. The paid app builds its runtime authority solely from five
environment strings (`app/main.py:3535-3539`), and
`build_paid_classic_catalog_v3` checks only their syntax and internal digest/URI
agreement. It receives no attestation URI, generation, byte length, SHA, service
record identity, traffic fact, or activation state.

Consequently, a manual or alternate deployment with plausible strings and the
platform-provided `K_REVISION` can reach the same paid-v3 code path without ever
running the provider attestor. The attestation is an operator-side note, not a
paid execution authority. It is also nondurable unless a later human separately
commits or uploads it.

### Required repair

Make the provider decision a durable, generation-pinned authority that the
money path actually consumes. One workable two-phase design is:

- publish the authenticated build/revision pre-activation receipt create-once
  in the production authority bucket;
- pass its exact URI/generation/SHA/bytes to the revision;
- have paid-v3 reopen and validate those exact bytes against its runtime
  source/build/image/revision identity; and
- after traffic cutover, publish a distinct provider traffic attestation and
  gate money endpoints through a small external activation record or provider
  check bound to that revision.

Avoid a self-referential scheme in which changing the attestation environment
creates a new revision with a different identity. The build authority and
traffic activation are naturally separate stages.

## P1 hardening after the four blockers

These items should be repaired in the same narrow deployment class sweep, but
they need not drive a separate redesign:

- Parse provider timestamps and require build create < build finish <= revision
  creation. Current code checks only non-empty strings.
- Bind project and region plus immutable provider UIDs/self-links, not only
  service/revision display names.
- Require a canonical traffic list: exact types, no duplicate revision rows,
  total traffic exactly 100, and the attested revision as the sole target.
  Current code only sums percentages for matching rows.
- A self-hash is not provenance. `validate_paid_classic_deployment_attestation_v3`
  accepts any internally rehashed document unless it is reopened from a
  separately authenticated create-once object.
- Pin the intended production service name rather than accepting any
  syntactically valid service argument for a money release.

## What passed static review

- `a6007f2f` is a direct child of the required `a5e39f73` parent.
- The reviewed Docker image obtains `IMAGE_SOURCE_COMMIT_SHA` from the build
  argument and runtime paid code does not invoke Git.
- Cloud Build's prepare step fetches and checks out the exact full commit into
  a clean detached checkout; the submitted workstation context is not the
  application source.
- The deployment command uses an immutable `@sha256` image URI.
- The normal simulation receipt validator names the exact five registered seed
  pairs, 10,000 worlds per block, and 50,000 combined worlds.
- The app rejects p50/p90 simulation objectives that the current simulation
  law does not implement and requires positive certified sigma before paid
  confidence ranking.

These positives should be preserved verbatim through the repair.

## Final gate and next action

Keep commit `a6007f2f` unmerged, unbuilt, undeployed, and unusable for paid
bytes. Produce one narrow direct-child repair that:

1. makes the execution request an independent terminal authority and defeats
   coordinated receipt restatement;
2. authenticates every build field capable of bypassing or reordering tests;
3. stages revision validation before traffic; and
4. makes a durable provider activation authority mandatory at the paid route.

Then rerun the existing focused suites plus the exact coordinated-restatement,
allowed-exit-code, pre-build-revision, multi-traffic, and missing-activation
negatives described here. A candidate-only, no-paid-output smoke on the real
projection/model/feature authorities should be the final pre-release check.
