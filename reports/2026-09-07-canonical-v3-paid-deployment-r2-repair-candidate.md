# Canonical-v3 paid/deployment bounded R2 repair candidate

Date: 2026-09-07

Held candidate repaired: `3c51fd3fb5cf6f3c52dfc9f1762661b94e1a67c9`

Required parent of held candidate: `a6007f2fd6cc5aca662489994a5f1d590b26f164`

Independent HOLD source:
`reports/2026-09-07-canonical-v3-paid-deployment-repair-independent-review.md`
on production `origin/main`

Repair branch: `codex/canonical-v3-paid-r2-repair-20260908`

Disposition: **review candidate only; do not merge, build, deploy, load, score,
or use for paid output before independent review**

## Executive disposition

This is a narrow repair of the exact held candidate. It closes the four P0
classes and associated P1 hardening identified by the independent HOLD:

1. the engine now returns one detached immutable result to the application and
   terminal paid-v3 export requires that exact result plus the independently
   constructed pre-execution authority;
2. simulation world evidence binds all five native candidate/world blocks, the
   exact ordered combined candidate/world matrix, and the selector's actual
   indices and roster order;
3. Cloud Build validation accepts the observed shape and exact documented
   defaults of a retained provider record while continuing to authenticate all
   caller-controlled execution semantics; and
4. paid activation is one exact generation-pinned GCS object, inline authority
   input is removed, the active Week-1 v2 money CSV uses the same gate, and
   ambiguous traffic mutation is reconciled or rolled back from a complete
   provider export.

The repair does not alter scoring, lineup objectives, the adopted money policy,
experiment defaults, frozen v1/v2 algorithms, or canonical-v3 Neo4j semantics.
It does not perform any cloud, graph, deployment, load, scoring, outcome, entry,
or other paid action.

## P0-1: immutable engine result and terminal authority

### Repair

- `PaidClassicEngineResultV3` now contains canonical JSON only. It retains a
  detached snapshot of selected roster/objective identities, the engine receipt
  bytes, the exact world binding, and a result hash. It retains no `Lineup` or
  mutable player mapping.
- Result and receipt fields reject ordinary assignment after issue. The result
  issuer capability is private to the module and no public result-construction
  method is exported.
- `build_sim_lineups` returns the actual result created at the engine boundary.
  `_build_classic` captures that object before presentation enrichment,
  confidence ranking, or leverage annotation. The app no longer reconstructs a
  result after those steps.
- The MILP path likewise seals its result immediately after optimization and
  before presentation ranking.
- All transformed paid-v3 validators and both CSV exporters require a typed
  execution authority and typed engine result. There are no optional defaults.
- The separately frozen exact-projection Week-1 materialization uses an
  explicit deterministic compatibility validator. That validator refuses
  engine authorities and transformation receipts, and dynamic paid generation
  cannot call it accidentally.
- The terminal receipt binds both the engine-result hash and world-binding
  hash.

Presentation ranking may reorder the live `Lineup` objects. That does not
weaken the engine claim: the result authenticates the exact selected
roster/objective set, while the world manifest independently retains the
engine's selected index and roster order. This preserves the existing money
ranking policy without claiming that ranking was part of the simulator.

### Adversarial coverage

- ordinary post-issue receipt and result assignment is refused;
- player/objective mutation after engine return is refused at terminal export;
- omission of either execution authority or engine result is refused;
- coordinated request restatement is refused even after recomputing all
  attacker-controlled hashes; and
- the normalized application route has a positive terminal result comparison.

## P0-1: exact native and combined world identity

### Repair

The simulation engine now records a canonical
`paid-classic-world-binding/v2` manifest containing:

- the exact registered label/projection-seed/role-seed identity for each native
  block;
- each native block's ordered player IDs and ordered nine-player candidate
  rosters;
- matrix shape, NumPy dtype string, and SHA-256 over contiguous C-order bytes
  for native candidate totals and player-world draws;
- the exact combined world-block order, player order, candidate order, matrix
  identities, and world count; and
- actual selected indices in selector order plus the corresponding ordered
  roster identities.

Validation enforces exact schemas, seed order, shared player-row order,
candidate uniqueness and membership, matrix dimensions, the multiplicative
world-dose relationship, selected-index uniqueness and bounds, and exact
index-to-roster correspondence. Simulation cannot issue a receipt without this
manifest. MILP uses an explicit zero-world identity rather than placeholder
digests.

### Adversarial coverage

Rehashed mutations of matrix shape, candidate/player order, selected indices,
and selected roster order all fail. A syntactically valid arbitrary hash is not
enough to change any structural relationship carried by the engine result.

## P0-2: provider-realistic closed-world build law

### Repair

- Provider observations such as `name`, `startTime`, `artifacts`, timing,
  status, and result fields are projected separately from reviewed execution
  law.
- Only exact documented provider defaults observed in the retained
  `gcloud builds describe` shape are normalized when absent from the reviewed
  YAML: `options.logging=LEGACY` and `options.pool={}`.
- Every step preserves and compares `id`, image, entry point, arguments,
  directory, environment, script, secrets, volumes, timeout, dependencies,
  allowed exit codes/failure, and automatic substitutions.
- Top-level timeout, queue TTL, options, service account, secrets, available
  secrets, substitutions, and image declarations are compared closed-world.
- The build contract now states the production service account and queue TTL
  explicitly. The build and deploy wrappers pin production project, region,
  repository/service, and authority bucket.
- Provider build identity, project, terminal status, timestamps, exact source
  commit, exact tag substitution, output digest, image repository, and the
  complete normalized build law must all agree before a Cloud Run mutation.

### Adversarial coverage

One refusal case exists for each step bypass class named by the HOLD, including
a `SUCCESS` record with `allowExitCodes`. Separate cases cover top-level
timeout, queue TTL, machine type, service account, secrets, available secrets,
extra substitutions, and images. The positive fixture carries retained
provider observations and expanded defaults.

## P0-4: exact activation authority and Week-1 boundary

### Repair

- Runtime accepts only the all-or-nothing activation identity
  `{uri, generation, sha256, bytes}`. It performs an exact-generation read,
  checks downloaded byte length and hash, parses the object, and validates it
  against runtime project, region, build, source commit, immutable image,
  service, and revision.
- The former `PAID_V3_ACTIVATION_AUTHORITY_JSON` production fallback was
  removed. Provider attestations reject that variable if it is present.
- Activation URI is pinned to the production authority bucket, service, and
  authorized revision. The authority's nested staging attestation is fully
  reopened and cross-compared field by field; its provider timestamps must be
  causally ordered and it cannot claim an activation-object identity.
- The deployment creates a no-traffic staging revision and provider
  attestation, then creates one no-clobber external activation authorization
  naming a distinct predeclared runtime revision. Its exact remote coordinates
  are reopened before that revision is created. This avoids a revision/object
  self-reference.
- Staging explicitly removes any inherited generation/hash/byte or inline
  activation variables. Both service and revision records are checked for
  stale exact coordinates. The active revision must carry all four exact
  coordinates.
- `load_week1_operating_book_export_v2` reopens the same exact activation
  object before joining or rendering the active Week-1 v2 CSV. The exporter
  includes the exact activation identity in its terminal receipt. The frozen
  v1 materialization implementation remains byte-compatible; this repair is to
  the active v2 successor identified by the HOLD.

### Adversarial coverage

Missing/partial exact identities, wrong bytes/hash, a non-object payload,
unrelated nested attestations with recomputed hashes, stale staging
coordinates, inline activation JSON, and active-revision coordinate drift all
fail closed. The Week-1 active v2 route refuses missing activation identity.

## P0-3/P1: staged cutover and fail-closed ambiguity

### Repair

- Project, region, service, authority bucket, revision derivation, and build
  image repository are policy constants rather than environment choices.
- Cloud Run provider identity requires exact namespace, resource-kind
  self-link, UID, location, observed generation, Ready status, and revision
  name. Build create/finish and revision creation timestamps are parsed as
  timezone-aware values and required to be causally ordered.
- Traffic validation requires integer percentages, unique revision rows, total
  100%, and exactly one 100% target for an active attestation. A no-traffic
  attestation requires zero traffic on the named revision.
- Before creating either no-traffic revision, the deployer records both the
  service JSON and full provider export. Rollback uses the provider export so
  the previous template, configuration, traffic, and tag semantics are not
  reconstructed by hand.
- `ROLLBACK_ARMED=1` is set before `update-traffic`. A nonzero update return is
  treated as ambiguous: the exact provider state is reopened and authenticated.
  Only an exact 100% target continues; any other state restores the previous
  provider export and authenticates the restored traffic.
- ERR, INT, and TERM paths all invoke the same rollback while armed. Final
  service/revision attestation and durable no-clobber traffic receipt occur
  before rollback is disarmed.

## Changed surface

- `cloudbuild.paid-boundary-v3.yaml`
- `scripts/build_paid_boundary_v3_image.sh`
- `scripts/deploy_paid_boundary_v3_image.sh`
- `src/nfl_dfs/app/main.py`
- `src/nfl_dfs/app/week1_operating_book_api.py`
- `src/nfl_dfs/inference/live_lineups.py`
- `src/nfl_dfs/inference/week1_operating_book_export.py`
- `src/nfl_dfs/optimizer/paid_classic_book_v3.py`
- `src/nfl_dfs/optimizer/paid_classic_deployment_v3.py`
- focused tests for the paid book, deployment, and Week-1 API/export.

No Neo4j implementation or graph contract is changed.

## Validation

A fresh machine-wide process census immediately before each serial pytest run
showed no other `python -m pytest` process.

Focused repaired surface, with explicit source path and no cache provider:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/erich/projects/nfl-predictions/.venv/bin/python -m pytest \
  -q -o addopts='' -p no:cacheprovider \
  tests/test_paid_classic_book_v3.py \
  tests/test_paid_classic_deployment_v3.py \
  tests/test_week1_operating_book_api.py \
  tests/test_week1_operating_book_export.py

127 passed in 6.32s
```

The exact focused release-gate module list from
`cloudbuild.paid-boundary-v3.yaml`:

```text
277 passed in 20.65s
```

Additional checks:

- `scripts/build_winner_registry_v2.py --check`: verified, 117 observations,
  four source artifacts, registry remains candidate-only/unadjudicated;
- `git diff --check`: pass;
- `bash -n` for both paid build/deployment wrappers: pass; and
- Python compilation of every modified Python/test module: pass.

Ruff and Black are not installed in the repository virtual environment; no
package installation was performed merely to add an unreviewed tool.

## Scope boundaries and next action

No Cloud Build was submitted. No Cloud Run service, revision, traffic, GCS
object, graph, lineup, score, outcome, contest entry, or paid artifact was read
or mutated as part of this repair. Provider documents used by tests are local
fixtures.

The next action is an independent review of the commit containing this report
against the original HOLD reproductions and the new adversarial cases. If and
only if that review accepts the candidate, production may decide whether to
merge it and run the separately authorized candidate-only pre-lock smoke. A
review acceptance is not itself authority to build, deploy, enable a money
route, or emit paid bytes.
