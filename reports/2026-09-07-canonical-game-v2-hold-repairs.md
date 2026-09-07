# Canonical-game v2 HOLD repairs

Date: 2026-09-07
Reviewed source: `72c5fbe2d2d2c5caa4cf413a3704fc660062b331`
Repair branch: `fix/canonical-game-policy-v2-20260907`
Disposition: local repair candidate; no build, deployment, paid-entry access,
Neo4j mutation, cloud mutation, or push is authorized by this work.

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
