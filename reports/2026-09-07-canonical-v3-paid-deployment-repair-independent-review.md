# Canonical-v3 paid/deployment repair independent review

Date: 2026-09-07  
Reviewed candidate: `3c51fd3fb5cf6f3c52dfc9f1762661b94e1a67c9`  
Required parent: `a6007f2fd6cc5aca662489994a5f1d590b26f164`  
Prior four-defect HOLD contract: commit `11e11dfc`,
`reports/2026-09-07-canonical-game-v2-r2-paid-deployment-independent-review.md`  
Review branch: `codex/canonical-v3-paid-repair-independent`  
Verdict: **HOLD**

## Executive disposition

The candidate is the exact direct child requested for review and its seven-file
delta is confined to paid-v3 evidence, application wiring, deployment mechanics,
focused tests, and the handoff. It does not change scoring algorithms, lineup
selection policy, construction defaults, or frozen v1/v2 implementation files.

There are real improvements:

- current dynamic paid-v3 routes construct a separate request/policy authority
  before generation;
- ordinary assignment to the new authority and engine-receipt wrappers is
  refused;
- the Cloud Build law now includes the previously erased step bypass fields;
- deployment uses an immutable image with `--no-traffic`, authenticates a Ready
  revision before cutover, reopens final traffic, and attempts rollback; and
- the paid-v3 application route fails closed when no activation document is
  configured.

The exact HOLD contract is nevertheless not closed. The engine result is not
retained across the engine boundary, exact world evidence is not authenticated,
the activation authority remains self-authorable and is not generation-pinned,
the active Week-1 money CSV bypasses it, and the provider build-law comparison
is incompatible with both the repository's own focused tests and the shape of a
real retained `gcloud builds describe` document.

The candidate's own focused release surface is red:

```text
61 passed, 11 failed
```

Because `cloudbuild.paid-boundary-v3.yaml` runs both failing modules, the exact
candidate cannot pass its committed build gate. No build, deployment, cloud
read/write, paid action, graph action, scoring run, or outcome access occurred
in this review.

## P0-1: the engine result still does not cross the engine boundary

The new pre-execution authority in `app/main.py:3653-3715` is a sound part of
the repair. Current dynamic paid routes create it before `_build_classic` and
pass it into terminal export. The terminal comparison at
`paid_classic_book_v3.py:1117-1130` therefore rejects the prior coordinated
tail/field/leverage restatement when that authority is supplied.

The post-execution half is not the retained result required by the HOLD:

1. `build_sim_lineups` constructs `engine_result` at
   `live_lineups.py:1175-1177`, discards the envelope, attaches only the receipt
   to each mutable `Lineup`, and returns `selected` at lines 1178-1180.
2. `_build_classic` subsequently mutates and ranks those objects
   (`app/main.py:2704-2733`).
3. The two dynamic paid routes manufacture a new result after `_build_classic`
   returns (`app/main.py:3723-3734` and `3975-3988`). It is therefore not the
   engine-returned result or independently retained execution bytes.
4. `PaidClassicEngineResultV3` is shallow: it stores a tuple of mutable
   `Lineup` objects whose player mappings remain mutable
   (`paid_classic_book_v3.py:169-179,257-262`).

The exact equality check is also not compatible with the module's own normal
authority reconstruction. `_reopen_paid_classic_book_v3` rewrites authoritative
names, salary-team aliases and provider schedule game IDs at lines 1569-1584,
then compares those reconstructed objects to the raw engine tuple at lines
1648-1656. A synthetic valid fixture sealed exactly as the app now does was
rejected with:

```text
paid-classic-book-boundary-v3-canonical-game:
typed engine result lineups differ from terminal book
```

This is consistent with the committed route test never reaching the new result
check: it first fails because its activation fixture was not updated.

Finally, the result and authority remain optional in the terminal API.
`_reopen_paid_classic_book_v3`, `validate_paid_classic_book_v3`,
`to_paid_dk_csv_v3`, and `fill_paid_entries_csv_v3` all default both arguments
to `None` (`paid_classic_book_v3.py:1482-1489,1648-1663,1725-1750,1785-1803`).
A transformed receipt can therefore still be exported without either
independent object by any caller that omits the options.

### Required repair

- Return one engine result from the engine and carry that exact object to the
  terminal boundary without re-creating it in the app.
- Snapshot canonical immutable lineup bytes or immutable roster/objective
  identities; do not retain references to mutable `Lineup`/dict objects.
- For every transformed paid-v3 path, require both the independent execution
  authority and engine result. Give deterministic exact-projection validation a
  separate explicit compatibility method rather than optional security inputs.
- Add end-to-end negatives for mutation between engine return, ranking, and
  export, plus a positive test that proves the real normalized paid route can
  pass the result comparison.

## P0-1: world identity is still a claim rather than exact evidence

The prior HOLD required the five native candidate/world blocks, the ordered
combined matrix, its interpretation, and selected-index/order identity.
The candidate does not yet provide that:

- `_issue_paid_classic_engine_receipt_v3` permits `world_binding=None` and then
  inserts `sha256([])` placeholders (`paid_classic_book_v3.py:1025-1085`). The
  committed simulation fixture uses that fallback
  (`tests/test_paid_classic_book_v3.py:294-330`).
- The validator checks only keys, nonnegative integer types, and 64-hex syntax
  (`paid_classic_book_v3.py:1267-1287`). It does not require the binding counts
  to equal the receipt/authority counts and cannot reopen any retained matrix.
- Live code hashes only `combined.row_draws.tobytes()` without dtype, shape,
  ordered player rows, ordered candidate rosters, or five native-block hashes
  (`live_lineups.py:1143-1150`).
- The field named `selected_index_order_sha256` hashes every candidate roster
  key and tag after sorting by roster key (`live_lineups.py:1151-1172`). It
  contains neither selected indices nor their selection order.

An adversarial synthetic reproduction changed only the world binding to zero
counts and arbitrary digests, recomputed the receipt hash, retained the original
independent request authority, and called terminal validation without the
optional result. Exact output:

```text
ACCEPTED_RESTATED_WORLD_BINDING {
  'block_count': 0,
  'worlds_per_block': 0,
  'selection_world_count': 0,
  'combined_matrix_sha256': '0000...0000',
  'selected_index_order_sha256': '1111...1111'
}
```

### Required repair

Bind and validate a canonical manifest containing each native block's ordered
candidate identities, matrix shape/dtype/hash and seed identity; the exact
combined candidate order and matrix identity; and actual selected indices in
selection order. Carry it in the immutable engine result, and require internal
count/shape relationships rather than syntax alone.

## P0-2: the build-law repair is closed-world but not provider-realistic

The security-relevant step fields from the prior report are now included at
`paid_classic_deployment_v3.py:100-109`; this closes the specific
`allowExitCodes`, `allowFailure`, `waitFor`, script, secret, volume, timeout and
automap projection hole.

The comparison cannot currently accept a normal provider record:

- Top-level unknown-field refusal at lines 125-145 fails on provider
  observations omitted from its allowlist. A retained real
  `gcloud builds describe` document in
  `reports/corpus-retrieval-runs/20260821-corpus-retrieval-engine-v1/task0/live-bfe2e48/build.json`
  contains `name`, `startTime`, and `artifacts`; all three are currently
  rejected.
- The same real record contains provider-expanded defaults such as
  `options.logging=LEGACY`, `options.pool={}`, and the default fully qualified
  `serviceAccount`. The validator compares these directly with the YAML's
  partial/absent values at lines 254-261 instead of normalizing documented
  provider defaults separately.
- The unchanged synthetic deployment fixture likewise omits the committed
  YAML's `timeout` and `options`, so all nominal build/deployment attestations
  fail before their intended assertions.

This is fail-closed, not a security bypass, but it is release-blocking: the
pre-mutation gate cannot authenticate the provider object it is designed to
consume.

### Required repair

Use a redacted retained provider fixture to define and test a versioned
normalization: project away provider-only observations, normalize documented
provider defaults, and closed-world compare every user-controlled execution
field. Update all positive and adversarial tests, including one `SUCCESS`
record carrying each test-bypass field.

## P0-4: activation is neither exact-object authority nor cross-bound evidence

The deployer sets only `PAID_V3_ACTIVATION_URI`
(`deploy_paid_boundary_v3_image.sh:94-98`). It never determines or injects the
final object's generation, byte length, or SHA. Runtime checks those values only
if optional environment variables happen to be present
(`app/main.py:3563-3581`). Consequently it reads the latest bytes at a URI, not
the exact `{uri,generation,sha256,bytes}` required by the HOLD contract.

There are two independent self-authoring paths:

1. When the URI is absent, `app/main.py:3587-3594` accepts a caller/deployer-
   authored `PAID_V3_ACTIVATION_AUTHORITY_JSON` environment value.
2. `validate_paid_classic_activation_authority_v3` checks the outer build,
   image, service and revision against runtime but only self-hash/shape checks
   its nested attestations (`paid_classic_deployment_v3.py:457-500`). It never
   requires the nested build ID, source commit, image, service, revision or
   activation URI to equal the outer/runtime values.

A synthetic authority with correct outer runtime strings but wholly unrelated,
self-hashed inner build/revision/service records was accepted:

```text
ACCEPTED_UNRELATED_NESTED_ATTESTATIONS other-service cccccccccccccccccccccccccccccccccccccccc
```

The active Week-1 v2 money download bypasses activation as well. Its exporter
builds a v3 catalog with the default empty activation hash and calls
`validate_paid_classic_book_v3` without execution/deployment authorities
(`week1_operating_book_export.py:324-337,381-386`). The app serves those bytes
from `/week1/operating-book-v2.csv` (`app/main.py:3026-3049`).

### Required repair

- Make exact GCS identity mandatory on all active money routes; remove the
  inline JSON fallback from production behavior.
- Solve the two-stage/self-reference problem with a distinct externally bound
  activation pointer or equivalent authority whose final exact generation,
  SHA and bytes are available to the money gate.
- Cross-compare every nested attestation identity and URI with the outer
  authority and runtime identity; parse and order its timestamps during reopen.
- Apply the same activation boundary to the active Week-1 CSV, or explicitly
  retire/disable that money route until it can satisfy the boundary.

## P0-3 and remaining deployment hardening

The staged order is materially better: immutable deploy with `--no-traffic`,
pre-activation provider validation, create-once pre-receipt, explicit 100%
traffic move, final provider reopen, then activation publication.

One ambiguous-mutation gap remains. `ROLLBACK_ARMED=1` is set only after
`gcloud run services update-traffic` returns success
(`deploy_paid_boundary_v3_image.sh:119-123`). If the provider applies the
traffic change but the command returns an ambiguous nonzero result, the ERR
trap sees rollback disabled. Signals are not trapped, and reconstructed
rollback drops any prior tag semantics. At minimum the helper must reconcile
provider traffic after an ambiguous return before deciding that no rollback is
needed. Missing activation still disables paid-v3, but it does not prove the
requested traffic restoration.

The earlier P1 project/region/provider UID binding is also still absent, and
the intended production service is caller-selected rather than pinned.

## Focused validation

The required fresh process census was empty immediately before pytest:

```text
ps -eo pid=,etimes=,comm=,args= |
  awk '$3 ~ /python/ && $0 ~ /-m pytest/ {print}'
# no output
```

One serial invocation used the repository virtual environment and explicit
source path:

```text
PYTHONPATH="$PWD/src:$PWD" \
  /home/erich/projects/nfl-predictions/.venv/bin/python -m pytest \
  -q -o addopts='' -p no:cacheprovider \
  tests/test_paid_classic_book_v3.py \
  tests/test_paid_classic_deployment_v3.py
```

Result: **61 passed, 11 failed in 6.97 seconds**.

Failure classes:

- one paid-v3 application-route test now fails because no activation authority
  fixture is supplied;
- nominal build evidence and deployment attestation fail because the provider
  fixture does not reproduce `timeout`/`options` from the reviewed YAML;
- seven later drift checks fail at that same earlier build-law mismatch rather
  than reaching the condition they purport to test; and
- the retained-attestation test also fails before it can create an attestation.

The Cloud Build contract itself names both failed modules in its mandatory
focused-test step. Therefore this is not merely optional test cleanup.

Static checks passed:

- `git diff --check` for the exact parent-to-candidate delta;
- `bash -n scripts/deploy_paid_boundary_v3_image.sh`;
- Python compilation of all changed Python/test files; and
- YAML parsing and four-step build-contract shape.

## Final decision

**HOLD** exact `3c51fd3fb5cf6f3c52dfc9f1762661b94e1a67c9` from build,
deployment, activation, integration, and paid use. Do not integrate this repair
or the dependent canonical-v3/Neo4j lineage yet. Return a narrow R2 that keeps
the accepted improvements, closes the exact engine/world/activation authority
boundaries above, and makes the committed release tests green against a
provider-realistic fixture.
