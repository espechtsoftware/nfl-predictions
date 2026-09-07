# Canonical-game v2 independent-review R2 repairs

Date: 2026-09-07
Exact parent: `a5e39f7362114430278e9473d7096a16ee3da061`
Repair branch: `fix/canonical-game-policy-v2-20260907`
Disposition: local repair candidate; no build, deployment, paid-entry access,
Neo4j mutation, cloud mutation, or push is authorized by this work.

## R2 disposition

This pass supersedes the earlier five-HOLD implementation record retained
below. It addresses the independent review of `a5e39f73` without changing the
frozen Week-1 v1 path, paid-v2, ordinary nonpaid generation, or scientific
generation/admission/selection policy.

### Engine-produced transformation evidence

The pre-execution object is now only an opaque, catalog-derived projection
authority. Callers cannot attach a transformation mapping and have it accepted
as evidence. The simulation engine creates one immutable receipt after the
five seed books have been combined and the final selected book exists; the
MILP path likewise creates its receipt only after optimization.

The receipt binds and the paid validator independently reopens:

- the exact registered R0--R4 projection/role seed pairs;
- exactly 10,000 worlds per block and 50,000 combined selection worlds;
- the exact in-memory serialized model-member hashes and registered model
  versions for both model families;
- one coherent row/column/value hash of the exact point-in-time feature frame
  handed to every model family;
- component-note before/effective hashes and preference source/application or
  explicit disabled state;
- locks, bans, satisfied portfolio theses, the full effective construction
  receipt, request context and effective contest policy;
- the complete effective MILP pool where applicable; and
- the final selected player objectives, independent of lineup order.

Arbitrary dictionaries attached to lineups fail. Hash-valid but semantically
altered engine receipts fail on seeds, world dose, model artifact/version,
feature snapshot, note/preference state, constraints, construction, request,
policy environment, or final objectives. Exact catalog objectives that were
not transformed retain a validator-issued deterministic proof; this narrow
case preserves the existing Week-1 v2 artifact path without allowing a caller
to claim an executed transformation.

### Distribution authority and confidence

The joined paid catalog now preserves `proj_p50`, `proj_p90`, and `proj_std` as
an all-or-none certified distribution set and includes them in the projection
batch identity. Values must be finite, sigma must be positive, and p50 cannot
exceed p90. Certified point, p50, and p90 objectives execute through MILP.
The currently certified simulation law explicitly rejects p50/p90 requests
instead of raising `AttributeError` or silently substituting another objective.
A money-bound book without positive certified sigma fails before confidence
ranking, eliminating the former near-zero confidence degeneration.

### Provider-authenticated build and deployment

`paid_classic_deployment_v3.py` validates the actual Cloud Build provider
record against the exact reviewed YAML law, including expanded source/image
substitutions, successful terminal timestamps, the built repository, and the
resolved digest. `deploy_paid_boundary_v3_image.sh` runs that full build check
before any serving mutation. After deployment it reopens the Cloud Run service
and revision provider records and writes one exclusive-create attestation that
binds:

- Cloud Build ID and full source commit;
- built digest and deployed immutable `@sha256` URI;
- service and running revision identity;
- observed generations and Ready conditions;
- exact runtime release environment; and
- 100% traffic on the attested revision.

This replaces syntax-only release claims with provider-observed evidence. The
helper was not executed during this repair.

### Suite-first Neo4j evidence authentication

Canonical retrieval loading authenticates the exact suite manifest before it
accepts completion/result/graph schema or artifact paths. It derives those
contracts from the suite version, authenticates the snapshot/task binding, and
reopens the execution contract, prefix claim, runtime IAM evidence, launch
intent, launch-consumption ledger, execution-name ledger, terminal execution,
and exact inventory. Generation-pinned canonical-v3 loading calls the public
engine validator with `replay=True`, so the exact five source world artifacts
are reopened rather than merely checking derived graph counts. A v3 suite
cannot be repackaged with v1 completion/result/graph objects. Registered legacy
v1 behavior remains explicit and unchanged.

### Policy inventory and current validation state

The canonical-game v7 inventory now classifies the added build/revision inputs
as infrastructure-only and pins every changed active source. It regenerates as:

- inventory SHA-256:
  `de290be1ef2f65014919bc57b775e4de13d1a4153d8bd9221bc88847e9e44c25`;
- source-set SHA-256:
  `93da1da1473772733a5eff3cf1d30d6fcd83eba3e533f58c2e9390b5ddb64b37`;
- rule-universe SHA-256:
  `0de128a919dff6d39283ba1ee5390110fbf3eb5d11a6d0348dc43307b58289b4`;
- classified-input projection SHA-256:
  `28173788062fdbad85cf77d33ee35cea06ecc391b31fb3ddf7c49f12a18af3f7`;
- 65 rules, 134 classified keys, and 290 direct input read sites.

Static checks are green: source/test compilation, `bash -n` for both paid
helpers, Cloud Build YAML parsing, fatal Ruff checks across modified Python,
full Ruff on the new deployment module/tests, inventory regeneration, and
`git diff --check`.

The production lead explicitly released the shared serial pytest lane before
the focused validation began. Tests were run one process at a time, with a
fresh process census before each invocation:

- **87 passed**: paid-v3 engine/validator/deployment, Week-1 v2 export, and
  Week-1 API compatibility;
- **90 passed effectively**: retrieval engine, canonical Neo4j and transport.
  The first run was 89 passed plus one test-only failure because the new
  replay assertion monkeypatched a nonexistent internal function name; the
  hook was corrected to the public `validate_retrieval_task_result` API and
  that one affected test then passed;
- **111 passed**: live multiseed, multiseed portfolio, production policy,
  paid-v2 and canonical-game-v2 compatibility;
- **57 passed**: application compatibility, with one unrelated Starlette
  deprecation warning; and
- **19 passed**: effective-policy inventory.

That is **364 passing tests**, zero product failures, and no unresolved test
failure. The serial pytest lane was explicitly released immediately afterward.

## Earlier five-HOLD repair record (superseded by R2 above)

## Why this repair exists

Independent review confirmed five release-blocking defects in the canonical-game
successor. The fixes below are deliberately narrow. They do not change the
accepted canonical game normalization, missing-ID behavior, neutral legality
policy, role scope, or the frozen Week-1 v1 path.

## Implemented repairs

### 1. Paid-v3 source and image authentication

`cloudbuild.paid-boundary-v3.yaml` no longer builds the caller's uploaded
worktree while merely accepting a 40-character string. It initializes a fresh
release checkout, fetches the exact pushed commit from the production origin,
checks out detached, proves the full HEAD, proves the repository is not shallow,
and requires a clean tree before and after focused validation. The Docker build
runs only in that authenticated checkout and uses a commit-specific tag.

`scripts/build_paid_boundary_v3_image.sh` is the only new submit helper. It
requires the requested commit to equal local `origin/main`, archives only the
committed Cloud Build contract, submits it, resolves the resulting image digest
from the durable Cloud Build record, and reports both the immutable image URI
and `IMAGE_DIGEST`. The helper has not been executed here.

### 2. Paid-v3 terminal provenance

Paid-v3 now fails closed unless runtime supplies:

- full `IMAGE_SOURCE_COMMIT_SHA` (`40` lowercase hexadecimal characters); and
- immutable `IMAGE_DIGEST` (`sha256:` plus 64 lowercase hexadecimal characters).

The joined catalog identity, validation/export receipts, prepared-entry capture,
and paid-v3 CSV response headers bind both values. The response also binds the
coherent projection-batch SHA and projection-derivation identity.

### 3. One coherent projection authority for generation

The paid-v3 routes now reopen the current point-in-time projection batch before
generation and build from that same catalog. They do not call the generic
per-player-latest projection read after certification.

- The deterministic input frame is reconstructed from the certified joined
  catalog.
- Simulation is restricted to certified player IDs. Its modeled correlated
  distributions are recentered on the certified batch means before tournament
  transforms; DST means come from the same authority.
- The selected objective may legitimately differ from raw `proj_points` after
  the bound simulation/MILP tournament transform. Such a lineup is accepted
  only with a derivation receipt binding the batch, full source commit, image
  digest, mode, seeds/world law, policy environment, construction receipt, and
  other effective transform inputs.
- Every selected player must still resolve in the certified batch-backed joined
  catalog. Mixed derivations fail closed. Receipts bind the selected objective
  values as well as the transform.

The Week-1 v2 rendering path continues to perform its independent salary,
projection, schedule, and semantic-game audit and now carries the same runtime
release coordinates. Week-1 v1 remains unchanged.

The canonical-game v7 effective-policy inventory was regenerated for the four
changed active-source files and now explicitly classifies the two release
coordinates as infrastructure-only inputs. Its current identities are:

- inventory SHA-256: `57ee7318d831fc443e66a971a26118b6b50973484bef257a3aa1d10573799d38`;
- source-set SHA-256: `7e713c527150718db74b9e4a709ef7e0d5e59ea83c4ccb97d6bbebc9bff52b81`;
- rule-universe SHA-256: `7c4548e363e8b931f3ef6cacd3914b932f13ebdc9326b03ff3616226cf66d552`;
  and
- classified-input projection SHA-256:
  `76cc09d86dc9d5be15b1aa6dfd50d261137a262a689713093631d350ae68d644`
  (`132` classified keys and `288` direct read sites).

### 4. Retrieval terminal path

The real transport now writes its single task terminal receipt to
`governance/terminal-receipt.json`, the path required by the Neo4j loader. Tests
derive the loader input from the producer's path constructor so these contracts
cannot drift independently again.

### 5. Canonical retrieval-v3 semantic replay

Canonical completion/task/graph v2 evidence now requires exactly seven
strategies. Legacy graph-v1 retains its registered four-or-seven compatibility.

For graph-v2, count and endpoint checks are no longer sufficient. The loader
requires an authenticated exact-object reader, reopens the generation-pinned
suite, snapshot, lineup, matrix/event, selection, and analytic evidence, and
uses the versioned retrieval-v3 validator in `replay=False` mode to reconstruct
and compare the canonical graph semantics byte for byte. This validates node
IDs, properties, candidates, populations, memberships, strategy identities and
metrics, selected targets/ranks, artifact pointers, and topology without
replaying source world artifacts or storing large matrices in Neo4j.

The governed Neo4j transport now expects seven canonical-v3 selections and the
standalone loader accepts explicit exact-object bodies for the same fail-closed
semantic replay. Compact analytic schema handling is versioned rather than
hard-coded to v1.

## Validation

Focused tests were run serially only after checking that no co-tenant pytest
process was active:

- `65 passed` — paid-v3, Week-1 v2, Week-1 API, and actual retrieval transport;
- `55 passed` — canonical retrieval Neo4j and governed Neo4j transport,
  including genuine engine-v3 evidence reconstruction;
- `63 passed` — live multiseed compatibility and canonical-game policy v2; and
- `57 passed` — application regression (`1` unrelated Starlette deprecation
  warning).

Total: `240 passed`, zero failures.

In addition:

- every changed Python file compiles;
- `bash -n scripts/build_paid_boundary_v3_image.sh` passes;
- the paid-v3 Cloud Build YAML parses and its step/image identities match;
- canonical-game v7 source identity and its classified-input projection
  regenerate successfully from the changed tree;
- `git diff --check` passes; and
- no cloud, paid-entry, or Neo4j operation was performed.

## Remaining release actions

This commit must remain unpushed until independent root review. A later approved
release must use the exact committed helper, retain the Cloud Build ID and
immutable digest, deploy by immutable image URI, and set `IMAGE_DIGEST` to the
resolved digest. Paid-v3 intentionally refuses to emit money-bound bytes if
either runtime coordinate is absent or malformed.
