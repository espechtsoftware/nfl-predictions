# Canonical-v3 paid/deployment bounded R4 repair candidate

Date: 2026-09-08

Exact repaired R3: `999204cc42602a43b8f94df12bbeb590db37ff40`

Independent R3 HOLD: production-main commit
`680c7aa120c5400779d849a13b03f24c2670c720`, report
`reports/2026-09-08-canonical-v3-paid-deployment-r3-independent-review.md`

Repair branch: `codex/canonical-v3-paid-r4-repair-20260908`

Disposition: **review candidate only; do not merge, build, deploy, change
traffic, publish/load a graph, score, read outcomes, or use for paid output
before independent review**

## Executive disposition

This is the bounded final-object R4 requested by the independent R3 HOLD. It
preserves the accepted R2 engine-result, world-binding, provider-build, and
deployment-attestation laws and the accepted R3 pretraffic/posttraffic
authority separation. It does not change scoring, generation, selection,
money policy, experiment defaults, frozen v1/v2 algorithms, or canonical-v3
Neo4j semantics.

The final `activation.json` money authority is no longer treated as absent or
unique from its current live object alone. Deployment and runtime now consume
the same complete exact-name provider census: live objects, all
versioned/noncurrent generations, and all soft-deleted generations. A new
publication is permitted only when every view is empty. Runtime permits money
output only when exactly one live generation exists and no noncurrent or
soft-deleted generation exists.

The final publisher retains `if_generation_match=0`, captures the generation
returned by that successful provider call, recenses the name, exact-reopens
that returned generation, proves exact URI/generation/bytes/SHA-256, and
recenses again. Its closed companion receipt retains the exact identity,
unique-generation census, create precondition, create-now fact, and receipt
hash. The deployment transcript prints that exact identity.

## Historical uniqueness and runtime repair

- `read_paid_classic_final_generation_census_v3` fully materializes all three
  provider iterators. A later-page failure is therefore a failed census, not
  a truncated success. Prefix neighbors such as `activation.json.traffic.json`
  are excluded by exact object name.
- Census validation is closed-schema and canonical. Missing categories,
  invalid/ambiguous generation representations, duplicates, overlap between
  categories, or disagreement between the live and all-version views fail
  closed.
- The deployer performs the census before its first Cloud Run mutation and
  repeats it after final authority construction. The final publisher performs
  one more census immediately before the atomic create.
- The publisher accepts creator status only from a normally returned
  `upload_from_string(..., if_generation_match=0)` call. It never converts a
  collision or ambiguous exception into a creator receipt.
- After publication, the provider-returned generation must be the sole live
  and sole historical generation. Only that exact generation is reloaded and
  downloaded; its bytes must equal the already authenticated local authority.
  A second complete census must remain identical before a publication receipt
  is returned.
- Every runtime money reopen performs the same unique-generation census before
  the exact download and again after semantic validation. A deleted object, a
  tombstone, a recreated live generation, a noncurrent generation, a second
  generation, or a census/read race closes the request.
- The environment remains pinned to the exact pretraffic deployment
  authorization, as required to build the runtime revision without
  self-reference. It cannot substitute for the separately censused final
  posttraffic authority.

## Adversarial coverage

Provider-realistic in-memory Storage clients exercise:

- a soft-deleted generation with no live object;
- a recreated live generation alongside a soft-deleted generation;
- a live generation alongside a noncurrent prior generation;
- exact-name filtering when the traffic archive shares the URI prefix;
- provider permission failure and failure after partial iterator consumption;
- invalid, overlapping, duplicated, missing, and noncanonical census fields;
- an atomic create collision which leaves no creator receipt;
- a second generation appearing immediately after the conditional create;
- exact reopening of the provider-returned generation and binding its
  URI/generation/bytes/SHA-256 into the closed publication receipt; and
- a generation change between the runtime's pre-read and post-read censuses.

The existing real-shell adversary remains in the release gate: traffic moves,
final attestation fails, rollback also fails, and no final gate is published.
The deploy-order check now also requires both complete absence censuses and
the reviewed provider publisher after rollback is disarmed.

## Changed surface

- `scripts/deploy_paid_boundary_v3_image.sh`
- `src/nfl_dfs/optimizer/paid_classic_deployment_v3.py`
- `src/nfl_dfs/app/week1_operating_book_api.py` (reader type annotation only)
- `tests/test_paid_classic_deployment_v3.py`
- this report and `HANDOFF.md`

No accepted engine, combined/native world, build-law, scoring, selector,
generator, policy, graph, or experiment-default module is changed.

## Validation

The globally first-positioned PREREG-074 R23 gate ran first. After its explicit
release, a fresh machine-wide census immediately before each R4 invocation
showed no other Python pytest process. Both R4 gates ran serially with explicit
`PYTHONPATH`, bytecode disabled, repository addopts disabled, and the cache
provider disabled.

Focused repaired surface:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/erich/projects/nfl-predictions/.venv/bin/python -m pytest \
  -q -o addopts='' -p no:cacheprovider \
  tests/test_paid_classic_book_v3.py \
  tests/test_paid_classic_deployment_v3.py \
  tests/test_week1_operating_book_api.py \
  tests/test_week1_operating_book_export.py

148 passed in 7.78s
```

The exact 13-module release-gate list in
`cloudbuild.paid-boundary-v3.yaml` passed **298/298 in 21.10 seconds**.
The serial lane was explicitly released to the waiting R23 reviewer
immediately afterward.

An earlier focused invocation found one assertion bug in the new static
shell-order test: it selected the import inside the first census block instead
of the second prepublication block. No executable defect was implicated. The
assertion start point was corrected, and the complete focused gate was rerun
from a fresh empty census to the terminal result above.

Static checks already completed:

- Python compilation of every changed Python/test module;
- `bash -n scripts/deploy_paid_boundary_v3_image.sh`;
- `git diff --check`; and
- Ruff on the changed surface, with only the R3 module's retained timezone and
  broad fail-closed reader findings remaining.

## Remaining operational requirements and non-blocking observations

- The governed authority bucket must allow the deployment and runtime service
  identities to list exact-name live, versioned, and soft-deleted objects. It
  must have a soft-delete policy which makes the soft-deleted provider view
  queryable. Missing policy or permission intentionally fails closed. This
  candidate made no bucket or IAM change and performed no provider read.
- Historical uniqueness is proved over every generation the provider retains
  and exposes. The deployment retains its existing single-writer/launch
  authority; this code does not grant a second writer.
- The active-traffic archive remains a non-money provenance sidecar and is not
  part of runtime authorization. Its R3 no-clobber/exact-reopen observation
  remains non-blocking.
- Paid-v2 and the legacy Week-1 route remain outside the v3 authority and must
  not be described as v3-gated unless separately retired or denied at ingress.

## Scope boundary and next action

No Cloud Build was submitted. No Cloud Run service, revision, traffic, GCS
object, Neo4j graph, lineup, score, outcome, contest entry, or paid artifact
was read or mutated. Provider mutations in tests are local in-memory fixtures
only.

After the fresh-census serial gates are green, push the exact candidate and
obtain an independent review against the R3 HOLD reproduction. Do not merge or
take a cloud/paid action merely because the local gates pass.
